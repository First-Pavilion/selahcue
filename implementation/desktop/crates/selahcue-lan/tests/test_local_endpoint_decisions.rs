//! Portable directory-kind policy; no filesystem or Unix-only imports.
use selahcue_lan::local_endpoint::{
    current_uid, judge_dir_creation, judge_dir_kind, verify_private_dir, DirError,
    REFUSE_SYMLINKED_DIRS,
};

#[test]
fn only_unix_refuses_a_symlinked_directory_and_the_decision_is_pure() {
    assert_eq!(REFUSE_SYMLINKED_DIRS, cfg!(unix));
    // Unix: a symlink is refused, a directory passes, anything else is not a directory.
    assert_eq!(judge_dir_kind(true, false, true), Err(DirError::Symlink));
    assert_eq!(judge_dir_kind(true, true, true), Err(DirError::Symlink));
    assert_eq!(judge_dir_kind(false, true, true), Ok(()));
    assert_eq!(
        judge_dir_kind(false, false, true),
        Err(DirError::NotDirectory)
    );
    // Windows keeps its previous behaviour (directory check only): a symlink that resolves to a
    // directory is accepted, and the refusal flag is the only difference.
    assert_eq!(judge_dir_kind(true, true, false), Ok(()));
    assert_eq!(judge_dir_kind(false, true, false), Ok(()));
    assert_eq!(
        judge_dir_kind(false, false, false),
        Err(DirError::NotDirectory)
    );
}

#[test]
fn checked_missing_publishers_both_accept_the_winning_directory_creation() {
    let parent = tempfile::tempdir().expect("parent");
    let stage = parent.path().join("staging");
    let barrier = std::sync::Arc::new(std::sync::Barrier::new(2));
    let threads: Vec<_> = (0..2)
        .map(|_| {
            let stage = stage.clone();
            let barrier = barrier.clone();
            std::thread::spawn(move || {
                assert_eq!(
                    std::fs::symlink_metadata(&stage)
                        .expect_err("both observed missing")
                        .kind(),
                    std::io::ErrorKind::NotFound
                );
                barrier.wait();
                judge_dir_creation(std::fs::create_dir(&stage))
            })
        })
        .collect();
    let results: Vec<_> = threads
        .into_iter()
        .map(|t| t.join().expect("publisher"))
        .collect();
    assert_eq!(
        results.iter().filter(|result| **result == Ok(true)).count(),
        1
    );
    assert_eq!(
        results
            .iter()
            .filter(|result| **result == Ok(false))
            .count(),
        1
    );
    assert!(stage.is_dir());
}

#[test]
fn existing_entries_are_not_repaired_and_other_creation_errors_are_refused() {
    use std::io::{Error, ErrorKind};
    for kind in [
        ErrorKind::PermissionDenied,
        ErrorKind::NotFound,
        ErrorKind::InvalidInput,
    ] {
        assert_eq!(
            judge_dir_creation(Err(Error::from(kind))),
            Err(DirError::CreateFailed)
        );
    }
    let parent = tempfile::tempdir().expect("parent");
    let file = parent.path().join("staging");
    std::fs::write(&file, "precious").expect("existing file");
    // AlreadyExists only means the caller must VERIFY, not that the entry is safe.
    assert_eq!(judge_dir_creation(std::fs::create_dir(&file)), Ok(false));
    assert_eq!(
        verify_private_dir(&file, current_uid()),
        Err(DirError::NotDirectory)
    );
    assert_eq!(
        std::fs::read_to_string(&file).expect("untouched"),
        "precious"
    );
}
