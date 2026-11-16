use std::io::{self, Write};
use std::path::Path;

#[derive(Clone, Copy)]
pub(super) enum Case {
    Ssim,
    DeviceLoss,
}

pub(super) struct Observer<W> {
    _case: Case,
    _enabled: bool,
    _writer: W,
}

impl<W: FnMut(&[u8]) -> io::Result<()>> Observer<W> {
    pub(super) fn with_writer(case: Case, enabled: bool, writer: W) -> Self {
        Self {
            _case: case,
            _enabled: enabled,
            _writer: writer,
        }
    }

    pub(super) fn case_enter(&mut self) {}
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
    _observer: &mut Observer<impl FnMut(&[u8]) -> io::Result<()>>,
    _generation: u8,
    operation: impl FnOnce() -> Option<T>,
) -> Option<T> {
    operation()
}

pub(super) fn observe_readback(
    _observer: &mut Observer<impl FnMut(&[u8]) -> io::Result<()>>,
    _generation: u8,
    _scene: usize,
    operation: impl FnOnce() -> Vec<u8>,
) -> Vec<u8> {
    operation()
}

// Callable seam for the parser controls. The checkpoint leaves all identity unknown.
#[allow(dead_code)]
pub(super) fn parse_native_tid(_target: Option<&Path>) -> Option<u32> {
    None
}
