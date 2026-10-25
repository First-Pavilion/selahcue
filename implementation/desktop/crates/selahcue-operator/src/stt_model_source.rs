//! Which on-device speech model file the operator loads: the pinned, hash-checked model it
//! downloads itself, or a developer's local file named by `SELAHCUE_STT_MODEL` (17tnw2b0prh).
//!
//! # Why the override is development-only
//!
//! `SELAHCUE_STT_MODEL` plus `SELAHCUE_STT_MODEL_SHA256` swap the speech model for any local
//! file. The file is checked only against the hash supplied by the same caller, so the check
//! proves the file is the one the caller meant, not that it is a model SelahCue ships. Before this
//! module the two variables worked in every build, including the installer
//! (`.github/workflows/windows-installer.yml` builds `cargo tauri build --features stt`), so
//! anyone who could set an environment variable for the operator's process could make a shipped
//! build transcribe a service with a model of their choosing. The owner-approved decision
//! (delivery plan, 2026-10-25) is that a release build ignores both variables; there is no
//! allow-list of hashes and the risk is not merely documented.
//!
//! # What a release build does when the variables are set
//!
//! It ignores them, prints one fixed line on stderr (once per process, because `stt_ready` is
//! polled), and uses the pinned model, which `selahcue_stt::fetch_model_phased` verifies against
//! the hash compiled into the app (FR-156). The line names the variables but never their values:
//! a path is not a secret, but it can carry a username, and the hash is the caller's input.
//!
//! # How the gate is built, and why this way
//!
//! [`resolve`] is pure and takes the build profile as an argument, so a test can run both arms in
//! one test binary. [`resolution_from_env`] is the only caller that supplies the real profile and
//! the real environment; `listening.rs` (the worker) and `main.rs` (`stt_ready`) go through
//! [`model_source_from_env`], which wraps it. That is the same shape as the repo's other
//! development-only reads: `dev_env::should_load_env_file`, `selahcue_cloud::openai::
//! direct_key_permitted` and `selahcue_stt_cloud::credential::developer_key_permitted`.
//!
//! A test that only restated `cfg!(debug_assertions)` would prove nothing about the call site
//! (the lesson of 17tnw2b9aga, PR #224). Three things close that here:
//!
//! - `this_build_honours_the_override_iff_it_is_a_debug_build` sets both variables and calls
//!   [`resolution_from_env`] itself. It runs in debug in every operator test line and in release
//!   in the `--release` operator test line `make ci` and CI's `operator-native` job already run
//!   (`cargo test --features dev-keys,openai-notes --release`). A hardcoded or inverted profile
//!   at the call site fails one of those two runs.
//! - This module is compiled for every test build, not only with `stt` (the same widening as
//!   `transcription_route`), which is what lets that existing release line, which does not build
//!   whisper.cpp, run the test.
//! - `no_other_source_file_names_the_override_variables` fails if any other file in `src/` spells
//!   either variable name as a string literal, so a new direct `std::env::var(...)` read cannot
//!   bypass this module unnoticed.
//!
//! Stated limit, the same as every sibling guard: an explicit `[profile.release]
//! debug-assertions = true` or a `RUSTFLAGS` override turns `cfg!(debug_assertions)` back on
//! under `--release`. `scripts/import_guards.sh` refuses the first in any committed manifest or
//! cargo config; nothing in the repo can see the second.
//!
//! # Why not a Cargo feature
//!
//! The repo's other development-only capabilities (`dev-keys`, `openai-notes`, `cloud-stt`) are
//! whole features tagged `RELEASE: UNSAFE` and stripped by the Makefile's `release-ai-guard`.
//! The override is not a feature: it is one read inside `stt`, which is `RELEASE: SAFE` and is
//! what users install. A new `RELEASE: UNSAFE` feature would still need this profile check (the
//! Makefile does not see a bare `cargo build --release --features ...`, which is why each of those
//! three features also carries a profile check), would add a feature to the launch-reachability
//! registry, and `make test-stt-real-model` (a release test) would have had to enable a
//! release-unsafe feature to keep working.

use std::ffi::OsString;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};

/// Names a local model file to load instead of the pinned download. Development builds only.
pub(crate) const MODEL_VAR: &str = "SELAHCUE_STT_MODEL";
/// The SHA-256 the [`MODEL_VAR`] file must match. Development builds only.
pub(crate) const MODEL_SHA_VAR: &str = "SELAHCUE_STT_MODEL_SHA256";

/// The one line a release build prints when either variable is set. A constant on purpose: it
/// cannot carry the path or the hash the caller supplied.
pub(crate) const RELEASE_IGNORES_OVERRIDE_NOTICE: &str =
    "SelahCue STT: SELAHCUE_STT_MODEL / SELAHCUE_STT_MODEL_SHA256 are set, but this is a release \
     build, which ignores them (they are a development-only override). Using the pinned, \
     hash-checked model.";

/// The profile this binary was compiled with, as far as the override is concerned.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum BuildProfile {
    /// `debug_assertions` on: `cargo run`, `cargo test`, `make launch`.
    Debug,
    /// `debug_assertions` off: `--release`, `make launch RELEASE=1`, the installer.
    Release,
}

impl BuildProfile {
    /// The profile of the running binary. The only place the real value is read.
    pub(crate) fn of_this_build() -> Self {
        if cfg!(debug_assertions) {
            BuildProfile::Debug
        } else {
            BuildProfile::Release
        }
    }
}

/// Where the model comes from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum ModelSource {
    /// The pinned asset in the model cache, downloaded on first use and verified against the hash
    /// compiled into the app.
    Pinned,
    /// A developer's local file. `sha256` is `None` when [`MODEL_SHA_VAR`] is unset; the loader
    /// refuses that case with its own message, as it always has.
    DeveloperOverride {
        path: PathBuf,
        sha256: Option<String>,
    },
}

/// What [`resolve`] decided, plus the line to print, if any.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Resolution {
    pub(crate) source: ModelSource,
    pub(crate) notice: Option<&'static str>,
}

/// Decide the model source from the profile and the two variables' values (`None` = unset).
pub(crate) fn resolve(
    profile: BuildProfile,
    model: Option<OsString>,
    sha256: Option<String>,
) -> Resolution {
    if profile == BuildProfile::Release {
        // Never honoured here, whatever was set. Say so only when something was set.
        let anything_set = model.is_some() || sha256.is_some();
        return Resolution {
            source: ModelSource::Pinned,
            notice: anything_set.then_some(RELEASE_IGNORES_OVERRIDE_NOTICE),
        };
    }
    match model {
        Some(path) => Resolution {
            source: ModelSource::DeveloperOverride {
                path: PathBuf::from(path),
                sha256,
            },
            notice: None,
        },
        None => Resolution {
            source: ModelSource::Pinned,
            notice: None,
        },
    }
}

/// [`resolve`] fed with this binary's real profile and the real process environment.
///
/// The names are written out here rather than passed as [`MODEL_VAR`] / [`MODEL_SHA_VAR`] so the
/// repo's env-documentation check (`implementation/api/tests/test_deployment_env_docs.py`, which
/// matches `env::var("NAME")` with a literal name) still sees these two reads against
/// `deployments.md` section 3a. The wiring test sets the variables through the constants and
/// expects this function to see both values, so a literal that drifted from its constant fails it.
pub(crate) fn resolution_from_env() -> Resolution {
    resolve(
        BuildProfile::of_this_build(),
        std::env::var_os("SELAHCUE_STT_MODEL"),
        std::env::var("SELAHCUE_STT_MODEL_SHA256").ok(),
    )
}

/// Set once the release notice has been printed, so a polled caller prints it at most once.
static NOTICE_PRINTED: AtomicBool = AtomicBool::new(false);

/// The model source the worker and the readiness check use. Prints the release notice on stderr
/// the first time it applies in this process.
pub(crate) fn model_source_from_env() -> ModelSource {
    let resolution = resolution_from_env();
    if let Some(notice) = resolution.notice {
        if !NOTICE_PRINTED.swap(true, Ordering::Relaxed) {
            eprintln!("{notice}");
        }
    }
    resolution.source
}

#[cfg(test)]
mod tests {
    use super::*;

    const PATH: &str = "/Users/someone/models/candidate.bin";
    const SHA: &str = "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69";

    fn set() -> Option<OsString> {
        Some(OsString::from(PATH))
    }

    fn sha() -> Option<String> {
        Some(SHA.to_string())
    }

    #[test]
    fn a_release_build_ignores_the_override_and_uses_the_pinned_model() {
        let r = resolve(BuildProfile::Release, set(), sha());
        assert_eq!(
            r.source,
            ModelSource::Pinned,
            "a release build loaded a caller-chosen model file: the override must be \
             development-only (17tnw2b0prh)"
        );
        assert_eq!(r.notice, Some(RELEASE_IGNORES_OVERRIDE_NOTICE));
    }

    #[test]
    fn a_release_build_also_ignores_the_override_without_its_hash() {
        let r = resolve(BuildProfile::Release, set(), None);
        assert_eq!(r.source, ModelSource::Pinned);
        assert_eq!(r.notice, Some(RELEASE_IGNORES_OVERRIDE_NOTICE));
    }

    #[test]
    fn a_release_build_says_why_it_ignores_a_lone_hash_variable() {
        let r = resolve(BuildProfile::Release, None, sha());
        assert_eq!(r.source, ModelSource::Pinned);
        assert_eq!(
            r.notice,
            Some(RELEASE_IGNORES_OVERRIDE_NOTICE),
            "a release build with only the hash variable set should still say it is ignored"
        );
    }

    #[test]
    fn a_release_build_without_the_variables_prints_nothing() {
        let r = resolve(BuildProfile::Release, None, None);
        assert_eq!(r.source, ModelSource::Pinned);
        assert_eq!(
            r.notice, None,
            "nothing was set, so there is nothing to explain"
        );
    }

    #[test]
    fn the_release_notice_never_carries_the_callers_path_or_hash() {
        let notice = resolve(BuildProfile::Release, set(), sha())
            .notice
            .expect("premise: the release build explains why it ignored the variables");
        assert!(
            !notice.contains(PATH),
            "the notice printed the path: {notice}"
        );
        assert!(
            !notice.contains("someone"),
            "the notice printed a username: {notice}"
        );
        assert!(
            !notice.contains(SHA),
            "the notice printed the hash: {notice}"
        );
        assert!(
            notice.contains(MODEL_VAR) && notice.contains(MODEL_SHA_VAR),
            "the notice must name both variables so a developer knows what was ignored: {notice}"
        );
    }

    /// Positive control: without it, the release tests above would also pass for a resolver that
    /// ignored the override in every build, which would break development and evaluation work.
    #[test]
    fn a_debug_build_honours_the_override() {
        let r = resolve(BuildProfile::Debug, set(), sha());
        assert_eq!(
            r.source,
            ModelSource::DeveloperOverride {
                path: PathBuf::from(PATH),
                sha256: Some(SHA.to_string()),
            }
        );
        assert_eq!(r.notice, None);
    }

    #[test]
    fn a_debug_build_hands_a_missing_hash_to_the_loader_to_refuse() {
        let r = resolve(BuildProfile::Debug, set(), None);
        assert_eq!(
            r.source,
            ModelSource::DeveloperOverride {
                path: PathBuf::from(PATH),
                sha256: None,
            }
        );
    }

    #[test]
    fn a_debug_build_without_the_variables_uses_the_pinned_model() {
        let r = resolve(BuildProfile::Debug, None, None);
        assert_eq!(r.source, ModelSource::Pinned);
        assert_eq!(r.notice, None);
    }

    /// Restores both variables when the test ends, including on a failed assertion, so a failure
    /// here cannot leave them set for the next test that takes `ENV_LOCK`.
    struct OverrideVars;

    impl OverrideVars {
        fn set(path: &str, sha: &str) -> Self {
            std::env::set_var(MODEL_VAR, path);
            std::env::set_var(MODEL_SHA_VAR, sha);
            OverrideVars
        }
    }

    impl Drop for OverrideVars {
        fn drop(&mut self) {
            std::env::remove_var(MODEL_VAR);
            std::env::remove_var(MODEL_SHA_VAR);
        }
    }

    /// The wiring test. The tests above prove [`resolve`]; this one proves the real entry point
    /// passes the real profile and the real environment to it. It asserts whichever arm this
    /// binary was compiled for, and `make ci` / CI run it in both: debug in every operator test
    /// line, release in `cargo test --features dev-keys,openai-notes --release`. So a hardcoded
    /// `BuildProfile::Debug` (or an inverted `cfg!`) in [`BuildProfile::of_this_build`] fails the
    /// release run, and a hardcoded `Release` fails the debug run.
    #[test]
    fn this_build_honours_the_override_iff_it_is_a_debug_build() {
        let _env_guard = crate::env_locked();
        let _vars = OverrideVars::set(PATH, SHA);

        let r = resolution_from_env();

        if cfg!(debug_assertions) {
            assert_eq!(
                r.source,
                ModelSource::DeveloperOverride {
                    path: PathBuf::from(PATH),
                    sha256: Some(SHA.to_string()),
                },
                "a debug build stopped honouring SELAHCUE_STT_MODEL: development and evaluation \
                 work (docs/quality/EVAL-PLAN-stt-nigerian-accent.md) depend on it"
            );
            assert_eq!(r.notice, None);
        } else {
            assert_eq!(
                r.source,
                ModelSource::Pinned,
                "a RELEASE build honoured SELAHCUE_STT_MODEL from the real environment: the \
                 profile reaching resolve() is wrong (17tnw2b0prh)"
            );
            assert_eq!(r.notice, Some(RELEASE_IGNORES_OVERRIDE_NOTICE));
        }
    }

    /// The wrapper the worker and `stt_ready` call returns exactly what [`resolution_from_env`]
    /// decided, so nothing between the decision and its callers can change the answer.
    #[test]
    fn the_callers_entry_point_returns_the_decision_from_the_real_environment() {
        let _env_guard = crate::env_locked();
        let _vars = OverrideVars::set(PATH, SHA);
        assert_eq!(model_source_from_env(), resolution_from_env().source);
        drop(_vars);
        assert_eq!(
            model_source_from_env(),
            ModelSource::Pinned,
            "with neither variable set every build uses the pinned model"
        );
    }

    /// 1-based numbers of the lines in `text` that contain `needle`.
    fn lines_naming_the_variables(text: &str, needle: &str) -> Vec<usize> {
        text.lines()
            .enumerate()
            .filter(|(_, line)| line.contains(needle))
            .map(|(n, _)| n + 1)
            .collect()
    }

    /// Positive control for the scan below: it does catch both a direct read of either variable
    /// and a local constant holding the name, and leaves prose and the shared constants alone.
    #[test]
    fn the_source_scan_catches_a_direct_read_of_either_variable() {
        let needle = format!("\"{}", MODEL_VAR);
        let planted = "fn a() {}\n\
                       let p = std::env::var(\"SELAHCUE_STT_MODEL\");\n\
                       // `SELAHCUE_STT_MODEL` in a comment is fine\n\
                       const NAME: &str = \"SELAHCUE_STT_MODEL_SHA256\";\n\
                       std::env::set_var(MODEL_VAR, path);\n";
        assert_eq!(lines_naming_the_variables(planted, &needle), vec![2, 4]);
    }

    /// Every other file under `src/` must reach the variables through this module. A string
    /// literal spelling either name elsewhere is how a direct `std::env::var(...)` read would
    /// come back and bypass the release gate, so it fails here. The needle is built at run time so
    /// this file does not match itself; this file is skipped anyway.
    #[test]
    fn no_other_source_file_names_the_override_variables() {
        let src = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
        let needle = format!("\"{}", MODEL_VAR);
        let mut offenders = Vec::new();
        let mut scanned = 0usize;
        let mut dirs = vec![src];
        while let Some(dir) = dirs.pop() {
            for entry in std::fs::read_dir(&dir).expect("read src/") {
                let path = entry.expect("read a src/ entry").path();
                if path.is_dir() {
                    dirs.push(path);
                    continue;
                }
                if path.extension().and_then(|e| e.to_str()) != Some("rs")
                    || path.file_name().and_then(|n| n.to_str()) == Some("stt_model_source.rs")
                {
                    continue;
                }
                scanned += 1;
                let text = std::fs::read_to_string(&path).expect("read a source file");
                for n in lines_naming_the_variables(&text, &needle) {
                    offenders.push(format!("{}:{n}", path.display()));
                }
            }
        }
        // Positive control: listening.rs and main.rs (and more) were actually read, so an empty
        // offender list means "none found", not "nothing scanned".
        assert!(
            scanned >= 10,
            "premise: the scan read the crate's sources ({scanned} files)"
        );
        assert!(
            offenders.is_empty(),
            "these lines spell {MODEL_VAR} or {MODEL_SHA_VAR} as a string literal outside \
             stt_model_source.rs; read them through model_source_from_env() so a release build \
             keeps ignoring them: {offenders:?}"
        );
    }
}
