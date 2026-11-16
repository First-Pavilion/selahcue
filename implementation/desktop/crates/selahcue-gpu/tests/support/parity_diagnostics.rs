use std::fmt;
use std::io::{self, Cursor, Write};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

const RECORDS_PER_CASE: u8 = 48;
const RECORD_BYTES: usize = 256;

pub(super) enum Case {
    Ssim,
    DeviceLoss,
}

impl Case {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Ssim => "ssim",
            Self::DeviceLoss => "device_loss",
        }
    }
}

pub(super) enum Stage {
    CaseEnter,
    ConstructorEnter(u8),
    ConstructorSome(u8),
    ConstructorNone(u8),
    RenderEnter {
        generation: u8,
        scene: usize,
    },
    ReadbackReturned {
        generation: u8,
        scene: usize,
        bytes: usize,
    },
    SceneAssertionPassed {
        generation: u8,
        scene: usize,
    },
    LossEnter,
    LossReturned,
    FirstDropEnter,
    FirstDropReturned,
    CallbackObserved,
    AssertionsPassed(u8),
    Overflow,
}

impl fmt::Display for Stage {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::CaseEnter => f.write_str("case_enter"),
            Self::ConstructorEnter(generation) => {
                write!(f, "constructor_enter generation={generation}")
            }
            Self::ConstructorSome(generation) => {
                write!(f, "constructor_some generation={generation}")
            }
            Self::ConstructorNone(generation) => {
                write!(f, "constructor_none generation={generation}")
            }
            Self::RenderEnter { generation, scene } => {
                write!(f, "render_enter generation={generation} scene={scene}")
            }
            Self::ReadbackReturned {
                generation,
                scene,
                bytes,
            } => {
                write!(
                    f,
                    "readback_returned generation={generation} scene={scene} bytes={bytes}"
                )
            }
            Self::SceneAssertionPassed { generation, scene } => {
                write!(
                    f,
                    "scene_assertion_passed generation={generation} scene={scene}"
                )
            }
            Self::LossEnter => f.write_str("loss_enter generation=1"),
            Self::LossReturned => f.write_str("loss_returned generation=1"),
            Self::FirstDropEnter => f.write_str("first_drop_enter generation=1"),
            Self::FirstDropReturned => f.write_str("first_drop_returned generation=1"),
            Self::CallbackObserved => f.write_str("callback_observed generation=1"),
            Self::AssertionsPassed(generation) => {
                write!(f, "assertions_passed generation={generation}")
            }
            Self::Overflow => f.write_str("overflow"),
        }
    }
}

pub(super) struct Observer<W> {
    case: Case,
    enabled: bool,
    sequence: u8,
    writer: W,
}

impl<W: FnMut(&[u8]) -> io::Result<()>> Observer<W> {
    pub(super) fn with_writer(case: Case, enabled: bool, writer: W) -> Self {
        Self {
            case,
            enabled,
            sequence: 0,
            writer,
        }
    }

    pub(super) fn case_enter(&mut self) {
        self.record(Stage::CaseEnter);
    }

    pub(super) fn record(&mut self, stage: Stage) {
        if !self.enabled || self.sequence == RECORDS_PER_CASE {
            return;
        }

        // Count attempts even on an I/O error. Only the last slot can hold overflow.
        self.sequence += 1;
        let stage = if self.sequence == RECORDS_PER_CASE {
            Stage::Overflow
        } else {
            stage
        };

        // One bounded line per writer call, with no partial line on encoding error.
        // The two cases each allow 48 lines, so their combined ceiling is 24 KiB.
        let mut record = [0_u8; RECORD_BYTES];
        let mut line = Cursor::new(&mut record[..]);
        if self.encode_record(stage, &mut line).is_ok() {
            let length = line.position() as usize;
            let _ = (self.writer)(&record[..length]);
        }
    }

    fn encode_record(&self, stage: Stage, line: &mut impl Write) -> io::Result<()> {
        let case = self.case.as_str();
        let seq = self.sequence;
        let pid = std::process::id();
        let utc = SystemTime::now().duration_since(UNIX_EPOCH);
        write!(
            line,
            "selahcue_gpu_parity case={case} seq={seq} pid={pid} tid="
        )?;
        match native_tid() {
            Some(tid) => write!(line, "{tid}")?,
            None => line.write_all(b"null")?,
        }
        match utc {
            Ok(elapsed) => write!(line, " utc_us={}", elapsed.as_micros())?,
            Err(_) => line.write_all(b" utc_us=null")?,
        }
        write!(line, " stage={stage}")?;
        if matches!(stage, Stage::CaseEnter) {
            let executable = std::env::current_exe().ok();
            let basename = executable
                .as_deref()
                .and_then(parity_basename)
                .unwrap_or("null");
            write!(line, " exe={basename}")?;
        }
        line.write_all(b"\n")
    }
}

impl Observer<fn(&[u8]) -> io::Result<()>> {
    pub(super) fn for_case(case: Case) -> Self {
        let enabled = cfg!(target_os = "linux")
            && std::env::var_os("SELAHCUE_GPU_PARITY_DIAGNOSTICS").as_deref()
                == Some(std::ffi::OsStr::new("1"));
        Self::with_writer(case, enabled, |record| io::stderr().write_all(record))
    }
}

pub(super) fn observe_construct<T>(
    observer: &mut Observer<impl FnMut(&[u8]) -> io::Result<()>>,
    generation: u8,
    operation: impl FnOnce() -> Option<T>,
) -> Option<T> {
    observer.record(Stage::ConstructorEnter(generation));
    let result = operation();
    observer.record(if result.is_some() {
        Stage::ConstructorSome(generation)
    } else {
        Stage::ConstructorNone(generation)
    });
    result
}

pub(super) fn observe_readback(
    observer: &mut Observer<impl FnMut(&[u8]) -> io::Result<()>>,
    generation: u8,
    scene: usize,
    operation: impl FnOnce() -> Vec<u8>,
) -> Vec<u8> {
    observer.record(Stage::RenderEnter { generation, scene });
    let pixels = operation();
    observer.record(Stage::ReadbackReturned {
        generation,
        scene,
        bytes: pixels.len(),
    });
    pixels
}

fn native_tid() -> Option<u32> {
    if !cfg!(target_os = "linux") {
        return None;
    }
    // Resolve this on the emitting thread. The process ID alone cannot identify it.
    let target = std::fs::read_link("/proc/thread-self").ok();
    parse_native_tid(target.as_deref())
}

pub(super) fn parse_native_tid(target: Option<&Path>) -> Option<u32> {
    fn task_number(value: &str) -> Option<u32> {
        if !value.bytes().all(|byte| byte.is_ascii_digit()) {
            return None;
        }
        value
            .parse()
            .ok()
            .filter(|n| (1..=2_147_483_647).contains(n))
    }

    let mut components = target?.to_str()?.split('/');
    task_number(components.next()?)?;
    if components.next()? != "task" {
        return None;
    }
    let tid = task_number(components.next()?)?;
    components.next().is_none().then_some(tid)
}

pub(super) fn parity_basename(path: &Path) -> Option<&str> {
    let name = path.file_name()?.to_str()?;
    let hash = name.strip_prefix("test_parity-")?;
    (hash.len() == 16
        && hash
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase()))
    .then_some(name)
}
