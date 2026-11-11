//! Practical local-file publication. Native Save authorizes the selected name, not an
//! inode CAS. Refuse observed changes; same-user namespace/content races, hardware and
//! crash durability remain outside the pre-commit preservation guarantee. No fallback
//! ever deletes/truncates the target. Windows is limited to local fixed NTFS.
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
    use std::os::windows::{fs::OpenOptionsExt, io::AsRawHandle};
    use windows_sys::Win32::Storage::FileSystem::*;
    let file = fs::OpenOptions::new()
        .read(true)
        .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS)
        .open(path)?;
    let mut info: BY_HANDLE_FILE_INFORMATION = unsafe { std::mem::zeroed() };
    // SAFETY: live file handle and writable correctly-sized output; File owns closure.
    if unsafe { GetFileInformationByHandle(file.as_raw_handle() as _, &mut info) } == 0 {
        return Err(io::Error::last_os_error());
    }
    let directory = info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY != 0;
    if info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE) != 0
        || (!directory && info.nNumberOfLinks != 1)
    {
        return Err(refused());
    }
    Ok(Observation {
        identity: (
            info.dwVolumeSerialNumber as u64,
            ((info.nFileIndexHigh as u64) << 32) | info.nFileIndexLow as u64,
        ),
        size: ((info.nFileSizeHigh as u64) << 32) | info.nFileSizeLow as u64,
        modified: ((info.ftLastWriteTime.dwHighDateTime as u128) << 32)
            | info.ftLastWriteTime.dwLowDateTime as u128,
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
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::Storage::FileSystem::*;
    let mut info: BY_HANDLE_FILE_INFORMATION = unsafe { std::mem::zeroed() };
    // SAFETY: File owns a live handle and info is a valid writable output.
    if unsafe { GetFileInformationByHandle(file.as_raw_handle() as _, &mut info) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok((
        info.dwVolumeSerialNumber as u64,
        ((info.nFileIndexHigh as u64) << 32) | info.nFileIndexLow as u64,
    ))
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
            use windows_sys::Win32::Storage::FileSystem::{MoveFileExW, MOVEFILE_REPLACE_EXISTING};
            let _ = (old, new);
            let old = wide(stage);
            let new = wide(target);
            // SAFETY: terminated native paths, no copy/delayed/remove fallback flags.
            if unsafe {
                MoveFileExW(
                    old.as_ptr(),
                    new.as_ptr(),
                    if replace {
                        MOVEFILE_REPLACE_EXISTING
                    } else {
                        0
                    },
                )
            } == 0
            {
                Err(io::Error::last_os_error())
            } else {
                Ok(())
            }
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
    let complete = observe(&stage.path)?;
    if complete.identity != identity || complete.size != bytes.len() as u64 {
        return Err(refused());
    }
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
fn wide(path: &Path) -> Vec<u16> {
    use std::os::windows::ffi::OsStrExt;
    path.as_os_str().encode_wide().chain(Some(0)).collect()
}
#[cfg(windows)]
fn check_volume(path: &Path) -> io::Result<()> {
    use std::path::Prefix;
    use windows_sys::Win32::Storage::FileSystem::*;
    use windows_sys::Win32::System::WindowsProgramming::DRIVE_FIXED;
    if !matches!(path.components().next(), Some(Component::Prefix(p)) if matches!(p.kind(), Prefix::Disk(_) | Prefix::VerbatimDisk(_)))
    {
        return Err(refused());
    }
    let path = wide(path);
    let mut root = vec![0u16; 32768];
    let mut format = [0u16; 32];
    // SAFETY: all pointers refer to appropriately-sized buffers for the duration of calls.
    unsafe {
        if GetVolumePathNameW(path.as_ptr(), root.as_mut_ptr(), root.len() as u32) == 0
            || GetDriveTypeW(root.as_ptr()) != DRIVE_FIXED
        {
            return Err(refused());
        }
        if GetVolumeInformationW(
            root.as_ptr(),
            std::ptr::null_mut(),
            0,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            format.as_mut_ptr(),
            format.len() as u32,
        ) == 0
        {
            return Err(refused());
        }
    }
    let end = format.iter().position(|&c| c == 0).ok_or_else(refused)?;
    if String::from_utf16_lossy(&format[..end]) != "NTFS" {
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
