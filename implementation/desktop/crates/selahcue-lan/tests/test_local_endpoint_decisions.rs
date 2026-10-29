//! Portable directory-kind policy; no filesystem or Unix-only imports.
use selahcue_lan::local_endpoint::{judge_dir_kind, DirError, REFUSE_SYMLINKED_DIRS};

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
