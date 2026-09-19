//! `safe_extract_zip`'s own controls (FR-138, ClickUp 86ak0qmzv) — the write-to-disk-safe layer on
//! top of `zip.rs`'s already-tested bomb/ratio/entry-count controls (`test_zip.rs`).
//!
//! This file tests only what is NEW to `safe_extract`: name confinement (zip-slip) and symlink
//! refusal. The underlying container controls (entry-count cap, per-entry/whole-archive byte caps,
//! the ratio guard) are `zip.rs`'s own and are exercised there — repeating them here through this
//! seam would duplicate coverage without adding any, since both paths call the same
//! `Archive::read_entry`. One escalating-bomb case is kept here anyway, to prove the reuse is real
//! rather than assumed: if `safe_extract_zip` ever stopped calling the shared `read_entry` and grew
//! its own unbounded read, this is the test that would catch it.
//!
//! **The bar every test here is written to:** it must FAIL if the control it names is removed.

#![allow(clippy::unwrap_used)]

mod support;

use support::{deflate_lowish_ratio, unix_symlink, zip, Entry};

use selahcue_import::{limits, safe_extract_zip, ImportError, MemorySource, RefusalReason};

fn never() -> impl Fn() -> bool {
    || false
}

fn extract(bytes: Vec<u8>) -> Result<selahcue_import::SafeExtractResult, ImportError> {
    let mut src = MemorySource::new(bytes);
    safe_extract_zip(&mut src, &never())
}

fn reasons(result: &selahcue_import::SafeExtractResult) -> Vec<(&str, RefusalReason)> {
    result
        .refused
        .iter()
        .map(|r| (r.name.as_str(), r.reason))
        .collect()
}

// --- AC6: a legitimate archive extracts correctly, unchanged -------------------------------

#[test]
fn a_legitimate_archive_extracts_every_entry_under_a_safe_relative_path() {
    let archive = zip(&[
        Entry::stored("readme.txt", b"hello church"),
        Entry::deflated("media/image1.png", &[0x89, b'P', b'N', b'G', 1, 2, 3, 4]),
        Entry::stored("nested/dir/deep.txt", b"deep content"),
    ]);
    let result = extract(archive).expect("a well-formed archive must not abort");

    assert!(result.refused.is_empty(), "nothing legitimate is refused");
    assert_eq!(result.files.len(), 3);
    let by_path: std::collections::HashMap<&str, &[u8]> = result
        .files
        .iter()
        .map(|f| (f.relative_path.as_str(), f.bytes.as_slice()))
        .collect();
    assert_eq!(by_path.get("readme.txt"), Some(&b"hello church".as_slice()));
    assert_eq!(
        by_path.get("nested/dir/deep.txt"),
        Some(&b"deep content".as_slice())
    );
    assert_eq!(
        by_path.get("media/image1.png"),
        Some(&[0x89u8, b'P', b'N', b'G', 1, 2, 3, 4].as_slice())
    );
}

#[test]
fn an_empty_archive_extracts_nothing_and_is_not_an_error() {
    let result = extract(zip(&[])).expect("an empty archive is not an admission failure");
    assert!(result.files.is_empty());
    assert!(result.refused.is_empty());
}

// --- AC1: zip-slip — traversal and absolute names are refused, never written ----------------

#[test]
fn a_traversal_entry_is_refused_and_never_lands_in_files() {
    let archive = zip(&[
        Entry::stored("../../evil", b"payload"),
        Entry::stored("safe.txt", b"kept"),
    ]);
    let result = extract(archive).unwrap();

    assert_eq!(result.files.len(), 1, "only the legitimate entry lands");
    assert_eq!(result.files[0].relative_path, "safe.txt");
    assert_eq!(
        reasons(&result),
        vec![("../../evil", RefusalReason::UnsafeName)]
    );
}

#[test]
fn an_absolute_path_entry_is_refused() {
    let archive = zip(&[Entry::stored("/etc/passwd", b"root:x:0:0")]);
    let result = extract(archive).unwrap();

    assert!(result.files.is_empty());
    assert_eq!(
        reasons(&result),
        vec![("/etc/passwd", RefusalReason::UnsafeName)]
    );
}

#[test]
fn windows_shaped_traversal_and_drive_paths_are_also_refused() {
    let archive = zip(&[
        Entry::stored("..\\..\\evil", b"a"),
        Entry::stored("C:\\Windows\\evil.dll", b"b"),
    ]);
    let result = extract(archive).unwrap();
    assert!(result.files.is_empty());
    assert_eq!(result.refused.len(), 2);
    assert!(result
        .refused
        .iter()
        .all(|r| r.reason == RefusalReason::UnsafeName));
}

#[test]
fn a_mid_path_traversal_that_would_climb_out_after_several_safe_looking_segments_is_refused() {
    // The shape a naive "only check the start" implementation misses: legitimate-looking segments
    // followed by enough `..` to climb above wherever the shell ends up joining this path.
    let archive = zip(&[Entry::stored("a/b/../../../escape", b"x")]);
    let result = extract(archive).unwrap();
    assert!(result.files.is_empty());
    assert_eq!(
        reasons(&result),
        vec![("a/b/../../../escape", RefusalReason::UnsafeName)]
    );
}

// --- AC2: a symlink entry is refused, never followed or written ----------------------------

#[test]
fn a_unix_symlink_entry_is_refused_and_its_target_never_reaches_a_path() {
    let archive = zip(&[
        unix_symlink("link", "../../../../etc/passwd"),
        Entry::stored("safe.txt", b"kept"),
    ]);
    let result = extract(archive).unwrap();

    assert_eq!(result.files.len(), 1, "only the legitimate entry lands");
    assert_eq!(result.files[0].relative_path, "safe.txt");
    assert_eq!(reasons(&result), vec![("link", RefusalReason::Symlink)]);
}

#[test]
fn a_symlink_entry_with_an_otherwise_perfectly_safe_name_is_still_refused() {
    // The case that matters: a safe-looking NAME is not enough on its own. The entry's own
    // declared TYPE must also be checked, or a symlink named `media/photo.png` would sail through
    // `safe_relative_path` and only its content — a path this reader never resolves — would carry
    // the actual escape.
    let archive = zip(&[unix_symlink("media/photo.png", "/etc/shadow")]);
    let result = extract(archive).unwrap();
    assert!(result.files.is_empty());
    assert_eq!(
        reasons(&result),
        vec![("media/photo.png", RefusalReason::Symlink)]
    );
}

#[test]
fn an_entry_with_symlink_shaped_content_but_no_symlink_mode_bit_is_extracted_normally() {
    // The positive control for AC2: refusing must be driven by the archive's OWN declared type,
    // never by guessing from content that merely looks like a path. Without this control, a
    // constant "always refuse anything that looks like a symlink" could masquerade as the real
    // check.
    let archive = zip(&[Entry::stored("just-text.txt", b"../not/actually/a/symlink")]);
    let result = extract(archive).unwrap();
    assert!(result.refused.is_empty());
    assert_eq!(result.files.len(), 1);
    assert_eq!(result.files[0].relative_path, "just-text.txt");
}

// --- AC4: a zip bomb is refused before it can exhaust memory --------------------------------

#[test]
fn a_lying_header_bomb_is_stopped_by_the_streaming_counter_not_the_declared_size() {
    // Mirrors `test_zip.rs`'s own primary bomb case, through this seam: the declared size is a
    // lie the reader must not trust, so the entry is admitted past the cheap header check and
    // only refused once the ACTUAL produced bytes cross the per-entry cap. Proves `safe_extract`
    // is still driven by `Archive::read_entry`'s real accounting, not a bypassed shortcut.
    let bomb_payload = deflate_lowish_ratio(2 * limits::MAX_ENTRY_INFLATED_BYTES);
    let entry = Entry::raw_deflated("bomb.bin", bomb_payload, 1024); // lies: claims 1 KiB
    let result = extract(zip(&[entry])).unwrap();

    assert!(result.files.is_empty(), "the bomb must never be extracted");
    assert_eq!(result.refused.len(), 1);
    assert_eq!(result.refused[0].name, "bomb.bin");
    assert!(matches!(
        result.refused[0].reason,
        RefusalReason::EntryTooLarge | RefusalReason::RatioExceeded
    ));
}

#[test]
fn the_whole_archive_bomb_budget_aborts_extraction_entirely() {
    // The load-bearing whole-archive bound, exercised through `safe_extract` specifically so a
    // future change to this seam alone (e.g. calling a DIFFERENT read path that forgot to share
    // the running total) would be caught here even if `test_zip.rs` were untouched.
    let per_entry = limits::MAX_ENTRY_INFLATED_BYTES;
    let needed = limits::MAX_TOTAL_INFLATED_BYTES / per_entry + 1;
    let mut entries = Vec::new();
    for i in 0..needed {
        entries.push(Entry::raw_deflated(
            &format!("bomb{i}.bin"),
            deflate_lowish_ratio(per_entry),
            per_entry as u32,
        ));
    }
    let result = extract(zip(&entries));
    assert!(
        matches!(result, Err(ImportError::ArchiveTooLarge { .. })),
        "expected ArchiveTooLarge, got {result:?}"
    );
}

// --- AC5: every rejection is specific and the process never panics or crashes ---------------

#[test]
fn a_mixed_hostile_archive_reports_a_distinct_reason_per_entry_and_never_panics() {
    let archive = zip(&[
        Entry::stored("../escape", b"a"),
        unix_symlink("link", "/etc/passwd"),
        Entry::stored("legit.txt", b"kept"),
        Entry::stored("legit.txt", b"shadowed - duplicate name"),
    ]);
    let result = extract(archive).unwrap();

    assert_eq!(result.files.len(), 1);
    assert_eq!(result.files[0].relative_path, "legit.txt");
    assert_eq!(result.files[0].bytes, b"kept");

    let mut got = reasons(&result);
    got.sort();
    let mut want = vec![
        ("../escape", RefusalReason::UnsafeName),
        ("link", RefusalReason::Symlink),
        ("legit.txt", RefusalReason::Duplicate),
    ];
    want.sort();
    assert_eq!(got, want);
}

#[test]
fn cancellation_aborts_extraction_and_nothing_partially_lands() {
    let archive = zip(&[
        Entry::stored("first.txt", b"a"),
        Entry::stored("second.txt", b"b"),
        Entry::stored("third.txt", b"c"),
    ]);
    let mut src = MemorySource::new(archive);
    // Interior mutability so the closure can count calls: false for the first two checks
    // (before/inside entry 0), true from the third on — fires partway through, not at the very
    // start, so a real interruption mid-archive is exercised rather than an immediate no-op.
    let counter = std::cell::Cell::new(0u32);
    let cancel = move || {
        let n = counter.get() + 1;
        counter.set(n);
        n > 2
    };
    let result = safe_extract_zip(&mut src, &cancel);
    assert!(matches!(result, Err(ImportError::Cancelled)));
}
