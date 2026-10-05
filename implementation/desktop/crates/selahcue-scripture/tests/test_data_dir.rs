//! Where installed translations live: the app DATA directory, never the OS cache directory
//! (`selahcue_scripture::registry::default_data_dir`, feature `installed`).
//!
//! The OS may purge a cache directory at any time, so a translation a user downloaded there would
//! silently vanish. The data directory is `%LOCALAPPDATA%\selahcue\translations` on Windows,
//! `~/Library/Application Support/selahcue/translations` on macOS, and the XDG data directory on
//! Linux, with `SELAHCUE_SCRIPTURE_DATA` overriding it (tests, portable installs).
//!
//! These tests change process-wide environment variables, so they share one lock and restore what
//! they changed.
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use selahcue_scripture::registry::{default_data_dir, DATA_DIR_ENV};

static ENV_LOCK: Mutex<()> = Mutex::new(());

/// Sets variables for a test and puts every one back (set or unset) when dropped.
struct Env(Vec<(&'static str, Option<OsString>)>);

impl Env {
    fn set(vars: &[(&'static str, Option<&str>)]) -> Env {
        let saved = vars
            .iter()
            .map(|(k, _)| (*k, std::env::var_os(k)))
            .collect();
        for (k, v) in vars {
            match v {
                Some(v) => std::env::set_var(k, v),
                None => std::env::remove_var(k),
            }
        }
        Env(saved)
    }
}

impl Drop for Env {
    fn drop(&mut self) {
        for (k, v) in self.0.drain(..) {
            match v {
                Some(v) => std::env::set_var(k, v),
                None => std::env::remove_var(k),
            }
        }
    }
}

fn tail() -> PathBuf {
    Path::new("selahcue").join("translations")
}

#[test]
fn the_environment_override_wins_and_an_empty_one_is_ignored() {
    let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    // An absolute path (built from the temp directory so it is absolute on every platform).
    let elsewhere = std::env::temp_dir().join("selahcue-somewhere-else");
    let _env = Env::set(&[(DATA_DIR_ENV, Some(elsewhere.to_str().unwrap()))]);
    assert_eq!(DATA_DIR_ENV, "SELAHCUE_SCRIPTURE_DATA");
    assert_eq!(default_data_dir(), Some(elsewhere.clone()));
    drop(_env);

    // An empty value is "not set", not "the current directory".
    let _env = Env::set(&[(DATA_DIR_ENV, Some(""))]);
    assert_ne!(default_data_dir(), Some(PathBuf::from("")));
}

#[test]
fn a_relative_environment_override_is_refused_not_resolved_against_the_working_directory() {
    // A relative path would mean a different directory for every directory the process happens to be
    // started in: translations "disappear", and cleanup deletes files somewhere nobody chose. It is
    // refused outright, and does NOT fall back to the default directory either: the user asked for a
    // location and got a mistake, so nothing is read or written anywhere.
    let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    for relative in [
        "relative/dir",
        ".",
        "..",
        "./data",
        "data",
        "~/translations",
    ] {
        let _env = Env::set(&[(DATA_DIR_ENV, Some(relative))]);
        assert_eq!(
            default_data_dir(),
            None,
            "{relative:?} is not an absolute path"
        );
    }
    // Positive control: an absolute path is used as given, so the refusals above are about
    // relativeness and not about the variable.
    let absolute = std::env::temp_dir().join("selahcue-absolute");
    let _env = Env::set(&[(DATA_DIR_ENV, Some(absolute.to_str().unwrap()))]);
    assert_eq!(default_data_dir(), Some(absolute));
}

#[cfg(target_os = "macos")]
#[test]
fn on_macos_it_is_application_support_and_not_caches() {
    let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let _env = Env::set(&[(DATA_DIR_ENV, None), ("HOME", Some("/Users/someone"))]);
    let dir = default_data_dir().unwrap();
    assert_eq!(
        dir,
        Path::new("/Users/someone/Library/Application Support").join(tail())
    );
    assert!(!dir.to_string_lossy().contains("Caches"));
    drop(_env);
    let _env = Env::set(&[(DATA_DIR_ENV, None), ("HOME", None)]);
    assert_eq!(
        default_data_dir(),
        None,
        "no home directory means no data directory"
    );
}

#[cfg(target_os = "windows")]
#[test]
fn on_windows_it_is_local_app_data() {
    let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let _env = Env::set(&[
        (DATA_DIR_ENV, None),
        ("LOCALAPPDATA", Some("C:\\Users\\someone\\AppData\\Local")),
    ]);
    assert_eq!(
        default_data_dir().unwrap(),
        Path::new("C:\\Users\\someone\\AppData\\Local").join(tail())
    );
    drop(_env);
    let _env = Env::set(&[(DATA_DIR_ENV, None), ("LOCALAPPDATA", None)]);
    assert_eq!(default_data_dir(), None);
}

#[cfg(not(any(target_os = "macos", target_os = "windows")))]
#[test]
fn on_linux_it_is_the_xdg_data_directory_and_not_the_cache() {
    let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let _env = Env::set(&[
        (DATA_DIR_ENV, None),
        ("XDG_DATA_HOME", Some("/xdg/data")),
        ("XDG_CACHE_HOME", Some("/xdg/cache")),
        ("HOME", Some("/home/someone")),
    ]);
    assert_eq!(
        default_data_dir().unwrap(),
        Path::new("/xdg/data").join(tail())
    );
    drop(_env);

    // A relative or empty XDG_DATA_HOME is treated as unset, per the XDG spec.
    for xdg in ["relative/dir", ""] {
        let _env = Env::set(&[
            (DATA_DIR_ENV, None),
            ("XDG_DATA_HOME", Some(xdg)),
            ("HOME", Some("/home/someone")),
        ]);
        assert_eq!(
            default_data_dir().unwrap(),
            Path::new("/home/someone/.local/share").join(tail()),
            "XDG_DATA_HOME={xdg:?}"
        );
    }
    let _env = Env::set(&[
        (DATA_DIR_ENV, None),
        ("XDG_DATA_HOME", None),
        ("HOME", None),
    ]);
    assert_eq!(default_data_dir(), None);
}
