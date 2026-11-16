//! GPU parity observer controls using fake operations and a controlled child.

#![allow(clippy::unwrap_used)]

#[path = "support/parity_diagnostics.rs"]
mod parity_diagnostics;

use parity_diagnostics::{observe_construct, observe_readback, parse_native_tid, Case, Observer};
use std::cell::{Cell, RefCell};
use std::io;
use std::panic::{catch_unwind, panic_any, AssertUnwindSafe};
use std::path::Path;
use std::process::{self, Command, Stdio};

const PREFIX: &str = "selahcue_gpu_parity";
const CHILD_ENV: &str = "SELAHCUE_GPU_PARITY_DIAGNOSTICS_TEST_CHILD";
const CHILD_EXIT: i32 = 86;

fn field<'a>(record: &'a str, name: &str) -> Option<&'a str> {
    record
        .split_ascii_whitespace()
        .skip(1)
        .filter_map(|part| part.split_once('='))
        .find_map(|(key, value)| (key == name).then_some(value))
}

fn record_check(record: &str, case: &str, stage: &str, generation: &str) {
    assert_eq!(record.split_ascii_whitespace().next(), Some(PREFIX));
    assert_eq!(field(record, "case"), Some(case));
    assert_eq!(field(record, "stage"), Some(stage));
    assert_eq!(field(record, "generation"), Some(generation));
}

fn recording_writer(records: &RefCell<Vec<String>>) -> impl FnMut(&[u8]) -> io::Result<()> + '_ {
    |record| {
        records
            .borrow_mut()
            .push(String::from_utf8(record.to_vec()).unwrap());
        Ok(())
    }
}

#[test]
fn constructor_none_emits_enter_and_none() {
    let records = RefCell::new(Vec::new());
    let mut observer = Observer::with_writer(Case::Ssim, true, recording_writer(&records));
    let enter_count = Cell::new(0);
    let result = observe_construct(&mut observer, 1, || {
        enter_count.set(records.borrow().len());
        None::<u8>
    });

    assert_eq!(result, None);
    assert_eq!(
        enter_count.get(),
        1,
        "constructor enter must precede the operation"
    );
    let records = records.borrow();
    assert_eq!(records.len(), 2, "constructor enter and none required");
    record_check(&records[0], "ssim", "constructor_enter", "1");
    record_check(&records[1], "ssim", "constructor_none", "1");
}

#[test]
fn readback_returns_original_bytes_and_emits_byte_count() {
    let records = RefCell::new(Vec::new());
    let mut observer = Observer::with_writer(Case::DeviceLoss, true, recording_writer(&records));
    let pixels = vec![7, 14, 21, 28];
    let original_buffer = pixels.as_ptr();
    let enter_count = Cell::new(0);
    let result = observe_readback(&mut observer, 2, 1, || {
        enter_count.set(records.borrow().len());
        pixels
    });

    assert_eq!(result, [7, 14, 21, 28]);
    assert_eq!(result.as_ptr(), original_buffer);
    assert_eq!(enter_count.get(), 1, "render enter must precede readback");
    let records = records.borrow();
    assert_eq!(
        records.len(),
        2,
        "render enter and readback return required"
    );
    record_check(&records[0], "device_loss", "render_enter", "2");
    record_check(&records[1], "device_loss", "readback_returned", "2");
    assert_eq!(field(&records[0], "scene"), Some("1"));
    assert_eq!(field(&records[1], "scene"), Some("1"));
    assert_eq!(field(&records[1], "bytes"), Some("4"));
}

#[test]
fn constructor_panic_propagates_with_enter_only() {
    let records = RefCell::new(Vec::new());
    let mut observer = Observer::with_writer(Case::Ssim, true, recording_writer(&records));
    let panic = catch_unwind(AssertUnwindSafe(|| {
        observe_construct(&mut observer, 1, || -> Option<u8> { panic_any(37_u8) })
    }))
    .unwrap_err();

    assert_eq!(panic.downcast_ref::<u8>(), Some(&37));
    let records = records.borrow();
    assert_eq!(records.len(), 1, "a panicking constructor emits enter only");
    record_check(&records[0], "ssim", "constructor_enter", "1");
}

#[test]
fn writer_error_preserves_readback_and_attempts_both_events() {
    let attempts = Cell::new(0);
    let mut observer = Observer::with_writer(Case::DeviceLoss, true, |_| {
        attempts.set(attempts.get() + 1);
        Err(io::Error::from(io::ErrorKind::BrokenPipe))
    });
    let mut reads = 0;
    let result = observe_readback(&mut observer, 1, 1, || {
        reads += 1;
        vec![42]
    });

    assert_eq!(result, [42]);
    assert_eq!(reads, 1);
    assert_eq!(
        attempts.get(),
        2,
        "try each record once despite writer errors"
    );
}

#[test]
#[ignore = "subprocess entry point"]
fn abrupt_exit_child() {
    if !matches!(std::env::var(CHILD_ENV).as_deref(), Ok("1")) {
        return;
    }
    let mut observer = Observer::for_case(Case::Ssim);
    observer.case_enter();
    let _ = observe_construct(&mut observer, 1, || -> Option<()> {
        eprintln!("captured by libtest");
        process::exit(CHILD_EXIT);
    });
}

#[test]
fn constructor_enter_survives_abrupt_child_exit_on_linux() {
    if !cfg!(target_os = "linux") {
        return;
    }
    let child = Command::new(std::env::current_exe().unwrap())
        .args(["--exact", "abrupt_exit_child", "--ignored"])
        .env_remove("RUST_TEST_NOCAPTURE")
        .env(CHILD_ENV, "1")
        .env("SELAHCUE_GPU_PARITY_DIAGNOSTICS", "1")
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let pid = child.id().to_string();
    let output = child.wait_with_output().unwrap();

    assert_eq!(output.status.code(), Some(CHILD_EXIT));
    let stderr = std::str::from_utf8(&output.stderr).unwrap();
    assert!(!stderr.contains("captured by libtest"));
    let records: Vec<_> = stderr
        .lines()
        .filter(|record| record.starts_with(PREFIX))
        .collect();
    assert_eq!(
        records.len(),
        2,
        "direct case and constructor enter must survive exit"
    );
    assert_eq!(field(records[0], "stage"), Some("case_enter"));
    assert_eq!(field(records[0], "case"), Some("ssim"));
    assert_eq!(field(records[0], "seq"), Some("1"));
    assert_eq!(field(records[0], "exe"), Some("null"));
    record_check(records[1], "ssim", "constructor_enter", "1");
    assert_eq!(field(records[1], "seq"), Some("2"));
    for record in records {
        assert_eq!(field(record, "pid"), Some(pid.as_str()));
        let tid = field(record, "tid").unwrap();
        assert!(tid == "null" || tid.parse::<i32>().is_ok_and(|tid| tid > 0));
        assert!(field(record, "utc_us").unwrap().parse::<u64>().unwrap() > 0);
    }
}

#[test]
fn disabled_observer_runs_the_operation_without_writing() {
    let writes = Cell::new(0);
    let mut observer = Observer::with_writer(Case::Ssim, false, |_| {
        writes.set(writes.get() + 1);
        Ok(())
    });
    observer.case_enter();
    let mut calls = 0;
    let result = observe_construct(&mut observer, 1, || {
        calls += 1;
        Some(23)
    });
    assert_eq!(result, Some(23));
    assert_eq!(calls, 1);
    assert_eq!(writes.get(), 0);
}

#[test]
fn readback_panic_propagates_with_enter_only() {
    let records = RefCell::new(Vec::new());
    let mut observer = Observer::with_writer(Case::DeviceLoss, true, recording_writer(&records));
    let panic = catch_unwind(AssertUnwindSafe(|| {
        observe_readback(&mut observer, 2, 1, || panic_any(73_u8))
    }))
    .unwrap_err();

    assert_eq!(panic.downcast_ref::<u8>(), Some(&73));
    let records = records.borrow();
    assert_eq!(records.len(), 1, "a panicking readback emits enter only");
    record_check(&records[0], "device_loss", "render_enter", "2");
}

#[test]
fn reserves_the_last_record_for_overflow_and_bounds_each_write() {
    let records = RefCell::new(Vec::new());
    let mut ssim = Observer::with_writer(Case::Ssim, true, recording_writer(&records));
    let mut loss = Observer::with_writer(Case::DeviceLoss, true, recording_writer(&records));
    for observer in [&mut ssim, &mut loss] {
        let offset = records.borrow().len();
        observer.case_enter();
        for _ in 0..23 {
            let pixels = observe_readback(observer, 1, 7, || vec![42; 230_400]);
            assert_eq!(pixels.len(), 230_400);
        }
        {
            let records = records.borrow();
            assert_eq!(records.len() - offset, 47, "47 ordinary records fit");
            assert_eq!(
                field(&records[offset + 46], "stage"),
                Some("readback_returned")
            );
            assert_eq!(field(&records[offset + 46], "seq"), Some("47"));
        }
        for _ in 0..2 {
            let pixels = observe_readback(observer, 1, 7, || vec![42]);
            assert_eq!(pixels, [42]);
        }
        let records = records.borrow();
        assert_eq!(records.len() - offset, 48, "only one overflow record fits");
        assert_eq!(field(&records[offset + 47], "stage"), Some("overflow"));
        assert_eq!(field(&records[offset + 47], "seq"), Some("48"));
    }
    let records = records.borrow();
    assert_eq!(records.len(), 96);
    assert!(records.iter().map(String::len).sum::<usize>() <= 24 * 1024);
    for record in &*records {
        assert!(record.is_ascii());
        assert!(record.len() <= 256);
        let line = record.strip_suffix('\n').unwrap();
        assert!(!line.contains(['\n', '\r']));
    }
}

#[test]
fn interleaved_cases_keep_independent_sequences() {
    let records = RefCell::new(Vec::new());
    let mut ssim = Observer::with_writer(Case::Ssim, true, recording_writer(&records));
    let mut loss = Observer::with_writer(Case::DeviceLoss, true, recording_writer(&records));
    ssim.case_enter();
    loss.case_enter();
    let original = Box::new(23);
    let address = std::ptr::from_ref(original.as_ref());
    let result = observe_construct(&mut ssim, 1, || Some(original)).unwrap();
    assert_eq!(std::ptr::from_ref(result.as_ref()), address);
    let pixels = observe_readback(&mut loss, 2, 1, || vec![42]);
    assert_eq!(pixels, [42]);

    let records = records.borrow();
    assert_eq!(records.len(), 6, "both cases emit their own records");
    let expected = [
        ("ssim", "case_enter", "1"),
        ("device_loss", "case_enter", "1"),
        ("ssim", "constructor_enter", "2"),
        ("ssim", "constructor_some", "3"),
        ("device_loss", "render_enter", "2"),
        ("device_loss", "readback_returned", "3"),
    ];
    for (record, (case, stage, seq)) in records.iter().zip(expected) {
        assert_eq!(field(record, "case"), Some(case));
        assert_eq!(field(record, "stage"), Some(stage));
        assert_eq!(field(record, "seq"), Some(seq));
    }
}

#[test]
fn native_tid_reads_the_thread_component_of_proc_link() {
    assert_eq!(parse_native_tid(Some(Path::new("123/task/456"))), Some(456));
    assert_eq!(
        parse_native_tid(Some(Path::new("1/task/2147483647"))),
        Some(2_147_483_647)
    );
}

#[test]
fn missing_or_malformed_native_tid_stays_unknown() {
    assert_eq!(parse_native_tid(None), None);
    for target in [
        "",
        "/proc/123/task/456",
        "123/thread/456",
        "123/task/",
        "123/task/0",
        "123/task/-2",
        "123/task/+2",
        "123/task/2147483648",
        "123/task/456/789",
        "123/task/456\n",
        "123/task/4x6",
        "123/task//456",
        "0/task/456",
        "unknown/task/456",
    ] {
        assert_eq!(
            parse_native_tid(Some(Path::new(target))),
            None,
            "{target:?}"
        );
    }
}
