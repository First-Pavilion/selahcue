//! Staging files for installs (feature `installed`).
//!
//! An install streams into a staging file, `<file>.tsv.gz.part`, and a receipt is written to a temp
//! file, `.installed.json.tmp`, before either is renamed into place. Three rules keep that safe in a
//! directory a user or another program can also write to:
//!
//! - **Created exclusively.** A staging file is made with `create_new` (`O_EXCL`), which fails if
//!   the path exists as anything, a symlink included, so a planted link is never followed or
//!   overwritten; the next free name (`.1.part`, `.2.part`, ...) is used instead.
//! - **Only what this call made is ever removed on failure.** [`Created`] is built from the path an
//!   exclusive create returned and removes exactly that file when dropped.
//! - **Cleanup is narrow, and skips installs in flight.** [`is_staging_name`] matches only the names
//!   above, so `movie.mp4.part` is never touched, and [`Inflight`] lists the staging files of
//!   installs that are running right now (in this process), which a cleanup must leave alone.
//!   Another PROCESS's staging files are not known to it: see `Registry::recover`.

use std::collections::HashSet;
use std::fs::{self, File, OpenOptions};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, MutexGuard};

use crate::catalog::validate_file_name;

/// How many staging names are tried before giving up (one per leftover or planted file).
const MAX_STAGING_NAMES: u32 = 16;
pub(crate) const STAGING_SUFFIX: &str = ".part";
pub(crate) const RECEIPT_TEMP_BASE: &str = ".installed.json";
pub(crate) const RECEIPT_TEMP_SUFFIX: &str = ".tmp";

/// A file this call created, removed on drop unless disarmed. It is only ever built from a path
/// returned by an exclusive create, so it can only remove what this call made.
pub(crate) struct Created {
    pub(crate) path: PathBuf,
    armed: bool,
}

impl Created {
    pub(crate) fn new(path: PathBuf) -> Created {
        Created { path, armed: true }
    }

    pub(crate) fn disarm(&mut self) {
        self.armed = false;
    }
}

impl Drop for Created {
    fn drop(&mut self) {
        if self.armed {
            let _ = fs::remove_file(&self.path);
        }
    }
}

/// Create a new file `dir/<base><suffix>` that must not already exist, trying `<base>.1<suffix>`,
/// `<base>.2<suffix>`, ... when a name is taken.
pub(crate) fn create_exclusive(
    dir: &Path,
    base: &str,
    suffix: &str,
) -> std::io::Result<(PathBuf, File)> {
    for attempt in 0..MAX_STAGING_NAMES {
        let name = if attempt == 0 {
            format!("{base}{suffix}")
        } else {
            format!("{base}.{attempt}{suffix}")
        };
        let path = dir.join(name);
        match OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(&path)
        {
            Ok(file) => return Ok((path, file)),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(e),
        }
    }
    Err(std::io::Error::new(
        std::io::ErrorKind::AlreadyExists,
        "no free staging file name",
    ))
}

/// Whether `name` is one of the files THIS module stages: `<file>.tsv.gz.part` or
/// `<file>.tsv.gz.<n>.part` (an install in flight), or `.installed.json.tmp` /
/// `.installed.json.<n>.tmp` (a receipt being written). Narrow on purpose: cleanup runs in a
/// directory a user can point elsewhere (`SELAHCUE_SCRIPTURE_DATA`), and `movie.mp4.part` is not
/// ours to delete.
pub(crate) fn is_staging_name(name: &str) -> bool {
    // Drop an optional `.<n>` attempt counter from the end of `stem`.
    fn without_counter(stem: &str) -> &str {
        match stem.rsplit_once('.') {
            Some((head, n)) if !n.is_empty() && n.bytes().all(|b| b.is_ascii_digit()) => head,
            _ => stem,
        }
    }
    if let Some(stem) = name.strip_suffix(STAGING_SUFFIX) {
        let file = without_counter(stem);
        return file.ends_with(".tsv.gz") && validate_file_name(file).is_ok();
    }
    if let Some(stem) = name.strip_suffix(RECEIPT_TEMP_SUFFIX) {
        return without_counter(stem) == RECEIPT_TEMP_BASE;
    }
    false
}

/// Flush a directory's entries to disk where the OS lets a program ask (best effort).
pub(crate) fn sync_dir(dir: &Path) {
    #[cfg(unix)]
    if let Ok(d) = File::open(dir) {
        let _ = d.sync_all();
    }
    #[cfg(not(unix))]
    let _ = dir;
}

/// The staging files of the installs running in this process right now. Creating a staging file
/// and listing it happen under one lock, and a cleanup holds the same lock while it deletes, so a
/// cleanup can never remove a file an install has just made but not yet listed.
#[derive(Default)]
pub(crate) struct Inflight {
    paths: Mutex<HashSet<PathBuf>>,
}

/// Removes its staging file from the in-flight list when dropped.
pub(crate) struct InflightGuard {
    list: Arc<Inflight>,
    path: PathBuf,
}

impl Drop for InflightGuard {
    fn drop(&mut self) {
        self.list.lock().remove(&self.path);
    }
}

impl Inflight {
    pub(crate) fn lock(&self) -> MutexGuard<'_, HashSet<PathBuf>> {
        self.paths.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Create a staging file for `base` in `dir` exclusively and list it as in flight.
    pub(crate) fn create_staging(
        list: &Arc<Inflight>,
        dir: &Path,
        base: &str,
    ) -> std::io::Result<(PathBuf, File, InflightGuard)> {
        let mut paths = list.lock();
        let (path, file) = create_exclusive(dir, base, STAGING_SUFFIX)?;
        paths.insert(path.clone());
        let guard = InflightGuard {
            list: Arc::clone(list),
            path: path.clone(),
        };
        Ok((path, file, guard))
    }
}
