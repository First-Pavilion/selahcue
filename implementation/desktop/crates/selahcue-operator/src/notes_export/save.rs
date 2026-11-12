//! Practical local-file publication. Native Save authorizes the selected name, not an
//! inode CAS. Refuse observed changes; same-user namespace/content races, hardware and
//! crash durability remain outside the pre-commit preservation guarantee. No fallback
//! ever deletes/truncates the target. Windows is limited to local fixed NTFS and
//! valid Unicode paths (unpaired UTF-16 is refused before I/O). Very long mounted
//! volume roots may be conservatively refused by the safe volume-query buffer.
use super::{ExportError, MAX_PDF_BYTES};
use std::{
    fs::{self, File},
    io::{self, Write},
    path::{Component, Path, PathBuf},
};

#[derive(Clone, Debug, PartialEq, Eq)]
struct Observation {
    identity: (u64, u64),
    size: u64,
    modified: u128,
    directory: bool,
}
fn refused() -> io::Error {
    io::Error::other("PDF destination is unavailable or changed")
}

#[cfg(unix)]
fn observe(path: &Path) -> io::Result<Observation> {
    use std::os::unix::fs::MetadataExt;
    let m = fs::symlink_metadata(path)?;
    if m.file_type().is_symlink() || !(m.is_dir() || m.is_file()) || (m.is_file() && m.nlink() != 1)
    {
        return Err(refused());
    }
    Ok(Observation {
        identity: (m.dev(), m.ino()),
        size: m.len(),
        modified: ((m.mtime() as u128) << 64) | m.mtime_nsec() as u128,
        directory: m.is_dir(),
    })
}
#[cfg(windows)]
fn observe(path: &Path) -> io::Result<Observation> {
    use std::os::windows::fs::OpenOptionsExt;
    use windows_sys::Win32::Storage::FileSystem::*;
    let file = fs::OpenOptions::new()
        .read(true)
        .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS)
        .open(path)?;
    let info = winapi_util::file::information(&file)?;
    let attributes = info.file_attributes();
    let directory = attributes & u64::from(FILE_ATTRIBUTE_DIRECTORY) != 0;
    if attributes & u64::from(FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE) != 0
        || (!directory && info.number_of_links() != 1)
    {
        return Err(refused());
    }
    Ok(Observation {
        identity: (info.volume_serial_number(), info.file_index()),
        size: info.file_size(),
        // The safe wrapper represents an all-zero FILETIME as None; preserve zero.
        modified: u128::from(info.last_write_time().unwrap_or(0)),
        directory,
    })
}
#[cfg(unix)]
fn file_identity(file: &File) -> io::Result<(u64, u64)> {
    use std::os::unix::fs::MetadataExt;
    let m = file.metadata()?;
    Ok((m.dev(), m.ino()))
}
#[cfg(windows)]
fn file_identity(file: &File) -> io::Result<(u64, u64)> {
    let info = winapi_util::file::information(file)?;
    Ok((info.volume_serial_number(), info.file_index()))
}
fn optional_target(path: &Path) -> io::Result<Option<Observation>> {
    match observe(path) {
        Ok(o) if !o.directory => Ok(Some(o)),
        Ok(_) => Err(refused()),
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(e),
    }
}

struct Parent {
    path: PathBuf,
    components: Vec<(PathBuf, Observation)>,
    #[cfg(unix)]
    fd: File,
}
impl Parent {
    fn open(path: &Path) -> io::Result<Self> {
        if !path.is_absolute() {
            return Err(refused());
        }
        #[cfg(windows)]
        check_volume(path)?;
        let mut current = PathBuf::new();
        let mut components = Vec::new();
        #[cfg(unix)]
        let mut fd = File::open("/")?;
        for component in path.components() {
            match component {
                Component::ParentDir | Component::CurDir => return Err(refused()),
                Component::Normal(name) => {
                    #[cfg(unix)]
                    {
                        fd = rustix::fs::openat(
                            &fd,
                            name,
                            rustix::fs::OFlags::RDONLY
                                | rustix::fs::OFlags::DIRECTORY
                                | rustix::fs::OFlags::NOFOLLOW
                                | rustix::fs::OFlags::CLOEXEC,
                            rustix::fs::Mode::empty(),
                        )?
                        .into();
                    }
                    current.push(name);
                }
                _ => current.push(component.as_os_str()),
            }
            // A Windows prefix alone isn't a rooted directory; inspect after RootDir.
            if !current.is_absolute() {
                continue;
            }
            let observed = observe(&current)?;
            if !observed.directory {
                return Err(refused());
            }
            components.push((current.clone(), observed));
        }
        let parent = Self {
            path: path.to_path_buf(),
            components,
            #[cfg(unix)]
            fd,
        };
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            let opened = parent.fd.metadata()?;
            if parent.components.last().map(|(_, o)| o.identity)
                != Some((opened.dev(), opened.ino()))
            {
                return Err(refused());
            }
        }
        Ok(parent)
    }
    fn recheck(&self, full: bool) -> io::Result<()> {
        for (index, (path, before)) in self.components.iter().enumerate() {
            let now = observe(path)?;
            if if full && index + 1 == self.components.len() {
                now != *before
            } else {
                now.identity != before.identity || !now.directory
            } {
                return Err(refused());
            }
        }
        Ok(())
    }
    fn after_create(&mut self) -> io::Result<()> {
        // Our sibling creation changes the immediate parent's size/mtime. Revalidate all
        // identities, then record that expected change for the final full observation.
        self.recheck(false)?;
        if let Some((path, o)) = self.components.last_mut() {
            *o = observe(path)?;
        }
        Ok(())
    }
    fn create(&self, name: &std::ffi::OsStr) -> io::Result<File> {
        #[cfg(unix)]
        {
            Ok(rustix::fs::openat(
                &self.fd,
                name,
                rustix::fs::OFlags::WRONLY
                    | rustix::fs::OFlags::CREATE
                    | rustix::fs::OFlags::EXCL
                    | rustix::fs::OFlags::NOFOLLOW
                    | rustix::fs::OFlags::CLOEXEC,
                rustix::fs::Mode::RUSR | rustix::fs::Mode::WUSR,
            )?
            .into())
        }
        #[cfg(windows)]
        {
            fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(self.path.join(name))
        }
    }
    fn remove(&self, name: &std::ffi::OsStr) -> io::Result<()> {
        #[cfg(unix)]
        {
            rustix::fs::unlinkat(&self.fd, name, rustix::fs::AtFlags::empty()).map_err(Into::into)
        }
        #[cfg(windows)]
        {
            fs::remove_file(self.path.join(name))
        }
    }
    fn publish(&self, stage: &Path, target: &Path, replace: bool) -> io::Result<()> {
        let old = stage.file_name().ok_or_else(refused)?;
        let new = target.file_name().ok_or_else(refused)?;
        #[cfg(any(target_os = "macos", target_os = "linux"))]
        {
            if replace {
                rustix::fs::renameat(&self.fd, old, &self.fd, new).map_err(Into::into)
            } else {
                rustix::fs::renameat_with(
                    &self.fd,
                    old,
                    &self.fd,
                    new,
                    rustix::fs::RenameFlags::NOREPLACE,
                )
                .map_err(Into::into)
            }
        }
        #[cfg(all(unix, not(any(target_os = "macos", target_os = "linux"))))]
        {
            let _ = (old, new, replace);
            Err(refused())
        }
        #[cfg(windows)]
        {
            let _ = (old, new);
            // Exactly one move: no copy, delayed-delete, attribute change or fallback.
            winsafe::MoveFileEx(
                windows_path(stage)?,
                Some(windows_path(target)?),
                if replace {
                    winsafe::co::MOVEFILE::REPLACE_EXISTING
                } else {
                    // This exact WinSafe release derives Default as zero flags.
                    winsafe::co::MOVEFILE::default()
                },
            )
            .map_err(|e| io::Error::from_raw_os_error(e.raw() as i32))
        }
    }
}
struct Stage<'a> {
    parent: &'a Parent,
    path: PathBuf,
    identity: (u64, u64),
    committed: bool,
}
impl Drop for Stage<'_> {
    fn drop(&mut self) {
        if !self.committed
            && self.parent.recheck(false).is_ok()
            && observe(&self.path).is_ok_and(|o| !o.directory && o.identity == self.identity)
        {
            if let Some(name) = self.path.file_name() {
                if self.parent.remove(name).is_err() {
                    eprintln!("PDF export: owned staging-file cleanup failed");
                }
            }
        }
    }
}

pub(crate) fn save_pdf(path: &Path, bytes: &[u8]) -> Result<(), ExportError> {
    if bytes.len() > MAX_PDF_BYTES {
        return Err(ExportError::TooLarge);
    }
    save(path, bytes).map_err(|_| ExportError::Io)
}
fn save(path: &Path, bytes: &[u8]) -> io::Result<()> {
    // Validate the FULL selected name before any volume query, open or staging.
    #[cfg(windows)]
    windows_path(path)?;
    let mut parent = Parent::open(path.parent().ok_or_else(refused)?)?;
    if path.file_name().is_none() {
        return Err(refused());
    }
    let target_before = optional_target(path)?;
    let mut created = None;
    for _ in 0..16 {
        let mut random = [0u8; 16];
        getrandom::fill(&mut random).map_err(|_| refused())?;
        let name = format!(".selahcue-pdf-{:032x}.tmp", u128::from_ne_bytes(random));
        let stage_path = parent.path.join(&name);
        #[cfg(test)]
        hook(Event::Candidate, &stage_path, path)?;
        match parent.create(std::ffi::OsStr::new(&name)) {
            Ok(file) => {
                created = Some((stage_path, file));
                break;
            }
            Err(e) if e.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(e),
        }
    }
    let (stage_path, mut file) = created.ok_or_else(refused)?;
    let identity = file_identity(&file)?;
    // Install ownership cleanup before any fallible validation/write. Parent observations
    // update only the mutation caused by our own successful exclusive create.
    let update = parent.after_create();
    let mut stage = Stage {
        parent: &parent,
        path: stage_path,
        identity,
        committed: false,
    };
    update?;
    #[cfg(test)]
    hook(Event::Created, &stage.path, path)?;
    for chunk in bytes.chunks(8192) {
        file.write_all(chunk)?;
        #[cfg(test)]
        hook(Event::PartialWrite, &stage.path, path)?;
    }
    #[cfg(test)]
    hook(Event::Sync, &stage.path, path)?;
    file.sync_all()?;
    // Windows guarantees final last-write timestamps only after the writer closes.
    // Capture that baseline afterwards; the original open-file identity still guards it.
    #[cfg(windows)]
    drop(file); // sync_all reports errors; Rust drop is not a checked close.
    let complete = observe(&stage.path)?;
    if complete.identity != identity || complete.size != bytes.len() as u64 {
        return Err(refused());
    }
    #[cfg(not(windows))]
    drop(file); // sync_all reports errors; Rust drop is not a checked close.
    #[cfg(test)]
    hook(Event::Validate, &stage.path, path)?;
    parent.recheck(true)?;
    if optional_target(path)? != target_before || observe(&stage.path)? != complete {
        return Err(refused());
    }
    #[cfg(test)]
    hook(Event::Rename, &stage.path, path)?;
    parent.publish(&stage.path, path, target_before.is_some())?;
    stage.committed = true; // COMMIT: later diagnostics/cancellation can never turn this into failure.
    #[cfg(test)]
    {
        let _ = hook(Event::Committed, &stage.path, path);
    }
    Ok(())
}

#[cfg(windows)]
fn windows_path(path: &Path) -> io::Result<&str> {
    let text = path.to_str().ok_or_else(refused)?;
    if text.contains('\0') {
        return Err(refused());
    }
    Ok(text)
}
#[cfg(windows)]
fn validate_disk_path(path: &Path) -> io::Result<()> {
    use std::path::Prefix;
    if !path.is_absolute()
        || !matches!(path.components().next(), Some(Component::Prefix(p)) if matches!(p.kind(), Prefix::Disk(_) | Prefix::VerbatimDisk(_)))
        || path
            .components()
            .any(|c| matches!(c, Component::ParentDir | Component::CurDir))
    {
        return Err(refused());
    }
    Ok(())
}
#[cfg(windows)]
fn validate_volume_root(root: &str) -> io::Result<()> {
    // WinSafe's checked UTF-16 decoding exposes a diagnostic String on malformed
    // output. Accept only a rooted disk path before passing it to further APIs.
    windows_path(Path::new(root))?;
    validate_disk_path(Path::new(root))?;
    if !root.ends_with('\\') {
        return Err(refused());
    }
    Ok(())
}
#[cfg(windows)]
fn check_volume(path: &Path) -> io::Result<()> {
    validate_disk_path(path)?;
    // Query this destination, including mapped/mounted volumes; never assume C:.
    let root = winsafe::GetVolumePathName(windows_path(path)?).map_err(|_| refused())?;
    validate_volume_root(&root)?;
    if winsafe::GetDriveType(Some(&root)) != winsafe::co::DRIVE::FIXED {
        return Err(refused());
    }
    let mut format = String::new();
    winsafe::GetVolumeInformation(Some(&root), None, None, None, None, Some(&mut format))
        .map_err(|_| refused())?;
    if format != "NTFS" {
        return Err(refused());
    }
    Ok(())
}

// Deterministic failpoints run inside the real helper on real files; absent in production.
#[cfg(test)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Event {
    Candidate,
    Created,
    PartialWrite,
    Sync,
    Validate,
    Rename,
    Committed,
}
#[cfg(test)]
type Hook = Box<dyn FnMut(Event, &Path, &Path) -> io::Result<()>>;
#[cfg(test)]
thread_local! { static HOOK: std::cell::RefCell<Option<Hook>> = const { std::cell::RefCell::new(None) }; }
#[cfg(test)]
fn hook(event: Event, stage: &Path, target: &Path) -> io::Result<()> {
    HOOK.with_borrow_mut(|h| match h {
        Some(f) => f(event, stage, target),
        None => Ok(()),
    })
}
#[cfg(test)]
pub(crate) fn with_hook<T>(
    f: impl FnMut(Event, &Path, &Path) -> io::Result<()> + 'static,
    run: impl FnOnce() -> T,
) -> T {
    struct Reset;
    impl Drop for Reset {
        fn drop(&mut self) {
            HOOK.with_borrow_mut(|h| *h = None);
        }
    }
    HOOK.with_borrow_mut(|h| *h = Some(Box::new(f)));
    let _reset = Reset;
    run()
}

#[cfg(all(test, windows))]
mod windows_notes_export_tests {
    use super::*;

    #[test]
    fn queried_root_must_be_absolute_disk_terminated_and_without_traversal() {
        for root in [r"C:\", r"C:\mounted\", r"\\?\C:\", r"\\?\C:\mounted\"] {
            assert!(validate_volume_root(root).is_ok(), "{root}");
        }
        for root in [
            "",
            "PARSING ERROR: invalid UTF-16",
            "C:",
            r"C:\mounted",
            r"\\server\share\",
            r"\\?\UNC\server\share\",
            r"\\.\C:\",
            r"C:\mounted\..\",
            "C:\\\0",
            r"relative\",
            r"\",
        ] {
            assert!(validate_volume_root(root).is_err(), "{root:?}");
        }
    }

    #[test]
    fn opened_file_identity_matches_reopened_path_and_detects_same_size_time_substitute() {
        let dir = tempfile::tempdir().expect("NTFS fixture");
        let path = dir.path().join("observed");
        fs::write(&path, b"original").expect("write");
        let file = File::open(&path).expect("open");
        let before = observe(&path).expect("observe");
        assert_eq!(
            file_identity(&file).expect("handle identity"),
            before.identity
        );
        let modified = file
            .metadata()
            .expect("metadata")
            .modified()
            .expect("mtime");
        drop(file);
        fs::rename(&path, path.with_extension("held")).expect("hold original");
        fs::write(&path, b"replaced").expect("same-size replacement");
        let replacement = fs::OpenOptions::new()
            .write(true)
            .open(&path)
            .expect("open replacement");
        replacement
            .set_times(std::fs::FileTimes::new().set_modified(modified))
            .expect("restore mtime");
        drop(replacement);
        let after = observe(&path).expect("observe replacement");
        assert_eq!(before.size, after.size);
        assert_eq!(before.modified, after.modified);
        assert_ne!(
            before.identity, after.identity,
            "size/time are not identity"
        );
        assert_eq!(
            file_identity(&File::open(&path).expect("reopen")).expect("new identity"),
            after.identity
        );
    }
}
