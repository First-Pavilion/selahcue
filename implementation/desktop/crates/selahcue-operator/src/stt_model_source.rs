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
//! This closes these two variables only. It does not make "no environment variable can change
//! which model bytes are loaded" true: `SELAHCUE_STT_CACHE` (and `HOME`, `LOCALAPPDATA`,
//! `XDG_CACHE_HOME`, which place the default cache) move the cache directory, and the loader
//! hashes the cached file on one open and hands whisper.cpp the path for a second open. That
//! pre-dates this module and is tracked in ClickUp 17tnw2b9dby
//! (https://app.clickup.com/t/17tnw2b9dby).
//!
//! # What a release build does when either variable is present
//!
//! "Present" means present in the environment, read with `var_os`: an empty value or a value that
//! is not valid UTF-8 counts. A release build ignores both variables, writes one fixed line to
//! stderr (once per process, because `stt_ready` is polled) and uses the pinned model, which
//! `selahcue_stt::fetch_model_phased` verifies against the hash compiled into the app (FR-156).
//! The line names the variables but never their values: a path is not a secret, but it can carry
//! a username, and the hash is the caller's input. (Other, older `SelahCue STT:` lines in
//! `listening.rs` do print the model and cache paths; that is unchanged.)
//!
//! Where that line can be seen: for certain, in a terminal that runs the binary directly
//! (`target/release/selahcue-operator`). `make launch` on macOS goes through
//! `scripts/run_operator_macapp.sh`, which starts the `.app` with `open -n -W` and no stderr
//! redirect; that script's own comments say the app's stderr then goes to the macOS unified log,
//! not a terminal, and it prints a `log stream` command to watch it. The Windows installer's build
//! is a GUI-subsystem process with no console, so a user of the shipped app does not see the line.
//!
//! In a debug build the same presence rule applies: an empty `SELAHCUE_STT_MODEL` is an override
//! to the empty path (the loader then fails to find it), and a hash that is not valid UTF-8 is
//! treated as missing, so the loader refuses with [`MISSING_HASH_MESSAGE`].
//!
//! # How the gate is built, and why this way
//!
//! Everything outside this file reaches the variables through one function,
//! [`model_source_from_env`], which `listening.rs` (the worker) and `main.rs` (`stt_ready`) call.
//! The names, the decision ([`resolve`]) and the notice are private to this module. Inside it:
//!
//! - [`resolve`] is pure and takes the build profile as an argument, so a test can run both arms
//!   in one test binary.
//! - [`resolution_from_env`] is the only place that passes the real profile
//!   ([`BuildProfile::of_this_build`]) and the real environment.
//! - [`announce`] writes the notice at most once; [`source_and_announce`] joins the two, and
//!   [`model_source_from_env`] passes it the process-wide flag and stderr.
//!
//! That is the same shape as the repo's other development-only reads: `dev_env::
//! should_load_env_file`, `selahcue_cloud::openai::direct_key_permitted` and
//! `selahcue_stt_cloud::credential::developer_key_permitted`.
//!
//! A test that only restated `cfg!(debug_assertions)` would prove nothing about the call site
//! (the lesson of 17tnw2b9aga, PR #224). Three things address that here:
//!
//! - `this_build_honours_the_override_iff_it_is_a_debug_build` sets the variables and calls
//!   [`resolution_from_env`] itself. It runs in debug in every operator test line and in release
//!   in the `--release` operator test line `make ci` and CI's `operator-native` job already run
//!   (`cargo test --features dev-keys,openai-notes --release`). A hardcoded or inverted profile
//!   at the call site fails one of those two runs.
//! - This module is compiled for every test build, not only with `stt` (the same widening as
//!   `transcription_route`), which is what lets that existing release line, which does not build
//!   whisper.cpp, run the test.
//! - `no_other_source_file_names_the_override_variables` fails if any other file in `src/` spells
//!   either variable name as a string literal or names this module's private constants. The
//!   constants being private already makes a read through them a compile error outside this file;
//!   the scan catches the next step (someone widening them to read them elsewhere). It matches
//!   text, so a name assembled at run time (`concat!`, `format!`) or a walk over
//!   `std::env::vars()` would get past it; that is a review rule, not a gate.
//!
//! # What this does NOT guard against
//!
//! `cfg!(debug_assertions)` is a build setting, and several build settings turn it back on under
//! `--release`, in which case a "release" binary honours the override and the release wiring test
//! above passes on its debug arm without noticing. Known routes:
//!
//! - `RUSTFLAGS` (or `CARGO_ENCODED_RUSTFLAGS`) carrying `-C debug-assertions`
//! - `CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS=true`
//! - `[profile.release] debug-assertions = true`, including the inline form
//!   `[profile]` with `release = { debug-assertions = true }`
//! - a cargo config with `rustflags = ["-C", "debug-assertions"]` (no value) or
//!   `-Cdebug-assertions=y`, including the legacy `.cargo/config` filename or a config in a parent
//!   directory or `$CARGO_HOME`
//!
//! `scripts/import_guards.sh` refuses some spellings of the manifest and config routes and says of
//! itself "THIS IS NOT THE GATE": it matches text and cannot see the environment. Nothing in this
//! repo checks the shipped binary for this today; an effect-level check is tracked in ClickUp
//! 17tnw2b9dbz (https://app.clickup.com/t/17tnw2b9dbz).
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
use std::io::Write;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};

/// Names a local model file to load instead of the pinned download. Development builds only.
/// Private, and compiled only into tests: production code spells the name out once, in
/// [`resolution_from_env`] (its doc says why), and nothing outside this file may read it.
#[cfg(test)]
const MODEL_VAR: &str = "SELAHCUE_STT_MODEL";
/// The SHA-256 the `SELAHCUE_STT_MODEL` file must match. Development builds only. Private and
/// test-only, like `MODEL_VAR`.
#[cfg(test)]
const MODEL_SHA_VAR: &str = "SELAHCUE_STT_MODEL_SHA256";

/// What the loader reports when a debug build has `SELAHCUE_STT_MODEL` but no usable
/// `SELAHCUE_STT_MODEL_SHA256`.
pub(crate) const MISSING_HASH_MESSAGE: &str =
    "SELAHCUE_STT_MODEL is set; also set SELAHCUE_STT_MODEL_SHA256 to the file's SHA-256 in hex \
     (integrity gate, FR-156)";

/// The one line a release build writes when either variable is present. A constant on purpose:
/// it cannot carry the path or the hash the caller supplied.
const RELEASE_IGNORES_OVERRIDE_NOTICE: &str =
    "SelahCue STT: SELAHCUE_STT_MODEL or SELAHCUE_STT_MODEL_SHA256 is set, but this is a release \
     build, which ignores both (they are a development-only override). Using the pinned, \
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
    /// A developer's local file (debug builds only). `sha256` is `None` when the hash variable is
    /// unset or not valid UTF-8; the loader refuses that case with [`MISSING_HASH_MESSAGE`].
    DeveloperOverride {
        path: PathBuf,
        sha256: Option<String>,
    },
}

/// What [`resolve`] decided, plus the line to print, if any.
#[derive(Debug, Clone, PartialEq, Eq)]
struct Resolution {
    source: ModelSource,
    notice: Option<&'static str>,
}

/// Decide the model source from the profile and the two variables as `var_os` returns them
/// (`None` = absent).
fn resolve(profile: BuildProfile, model: Option<OsString>, sha256: Option<OsString>) -> Resolution {
    if profile == BuildProfile::Release {
        // Never honoured here, whatever was set. Say so whenever either variable is present,
        // empty or not, valid UTF-8 or not.
        let anything_present = model.is_some() || sha256.is_some();
        return Resolution {
            source: ModelSource::Pinned,
            notice: anything_present.then_some(RELEASE_IGNORES_OVERRIDE_NOTICE),
        };
    }
    match model {
        Some(path) => Resolution {
            source: ModelSource::DeveloperOverride {
                path: PathBuf::from(path),
                // A hash that is not UTF-8 cannot be hex, so it is treated as missing.
                sha256: sha256.and_then(|s| s.into_string().ok()),
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
/// The names are written out here rather than taken from the test-only `MODEL_VAR` /
/// `MODEL_SHA_VAR` constants, so the repo's env-documentation check
/// (`implementation/api/tests/test_deployment_env_docs.py`, which matches
/// `env::var_os("NAME")` with a literal name) still sees these two reads against
/// `deployments.md` section 3a. The wiring test sets the variables through the constants and
/// expects this function to see them, so a literal that drifted from its constant fails it.
fn resolution_from_env() -> Resolution {
    resolve(
        BuildProfile::of_this_build(),
        std::env::var_os("SELAHCUE_STT_MODEL"),
        std::env::var_os("SELAHCUE_STT_MODEL_SHA256"),
    )
}

/// Write `notice` to `out` unless `printed` says it was already written. Returns whether it wrote.
/// `None` writes nothing and does not use up the one write.
fn announce(notice: Option<&str>, printed: &AtomicBool, out: &mut impl Write) -> bool {
    let Some(notice) = notice else {
        return false;
    };
    if printed.swap(true, Ordering::Relaxed) {
        return false;
    }
    // Advisory: a closed or broken stderr must not stop the model loading.
    let _ = writeln!(out, "{notice}");
    true
}

/// Announce the resolution's notice (if any) and hand back its source.
fn source_and_announce(
    resolution: Resolution,
    printed: &AtomicBool,
    out: &mut impl Write,
) -> ModelSource {
    announce(resolution.notice, printed, out);
    resolution.source
}

/// Set once the release notice has been written, so a polled caller writes it at most once.
static NOTICE_PRINTED: AtomicBool = AtomicBool::new(false);

/// The model source the worker and the readiness check use: the only way into this module from
/// outside it. Writes the release notice to stderr the first time it applies in this process.
pub(crate) fn model_source_from_env() -> ModelSource {
    source_and_announce(
        resolution_from_env(),
        &NOTICE_PRINTED,
        &mut std::io::stderr(),
    )
}

/// Test-only access to the two variables, for tests elsewhere in the crate that must set or clear
/// them. Compiled only into test binaries, so production code cannot use it to read them. Callers
/// hold `crate::env_locked()`.
#[cfg(test)]
pub(crate) mod test_support {
    use super::{MODEL_SHA_VAR, MODEL_VAR};
    use std::ffi::{OsStr, OsString};

    /// Set both variables.
    pub(crate) fn set_override(path: impl AsRef<OsStr>, sha256: &str) {
        std::env::set_var(MODEL_VAR, path);
        std::env::set_var(MODEL_SHA_VAR, sha256);
    }

    /// Remove both variables.
    pub(crate) fn clear_override() {
        std::env::remove_var(MODEL_VAR);
        std::env::remove_var(MODEL_SHA_VAR);
    }

    /// The two variables as they stand (`None` = absent), model first.
    pub(crate) fn override_vars() -> (Option<OsString>, Option<OsString>) {
        (std::env::var_os(MODEL_VAR), std::env::var_os(MODEL_SHA_VAR))
    }
}

#[cfg(test)]
mod tests {
    use super::test_support::{clear_override, set_override};
    use super::*;

    const PATH: &str = "/Users/someone/models/candidate.bin";
    const SHA: &str = "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69";

    fn set() -> Option<OsString> {
        Some(OsString::from(PATH))
    }

    fn sha() -> Option<OsString> {
        Some(OsString::from(SHA))
    }

    /// Bytes that are not valid UTF-8 (unix only: Windows `OsString`s are built from UTF-16).
    #[cfg(unix)]
    fn not_utf8() -> OsString {
        use std::os::unix::ffi::OsStringExt;
        OsString::from_vec(vec![b'/', b't', 0xff, 0xfe])
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
    fn a_release_build_treats_an_empty_value_as_present() {
        let r = resolve(BuildProfile::Release, Some(OsString::new()), None);
        assert_eq!(r.source, ModelSource::Pinned);
        assert_eq!(
            r.notice,
            Some(RELEASE_IGNORES_OVERRIDE_NOTICE),
            "an empty SELAHCUE_STT_MODEL is still set; a release build should say it ignored it"
        );
    }

    #[cfg(unix)]
    #[test]
    fn a_release_build_notices_a_lone_hash_that_is_not_utf8() {
        let r = resolve(BuildProfile::Release, None, Some(not_utf8()));
        assert_eq!(r.source, ModelSource::Pinned);
        assert_eq!(r.notice, Some(RELEASE_IGNORES_OVERRIDE_NOTICE));
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

    /// The wording itself. `SELAHCUE_STT_MODEL` is a prefix of `SELAHCUE_STT_MODEL_SHA256`, so the
    /// first check looks for the shorter name followed by a space.
    #[test]
    fn the_release_notice_names_each_variable_and_says_release_builds_ignore_them() {
        let n = RELEASE_IGNORES_OVERRIDE_NOTICE;
        assert!(
            n.contains(&format!("{MODEL_VAR} ")),
            "the notice must name SELAHCUE_STT_MODEL on its own: {n}"
        );
        assert!(
            n.contains(MODEL_SHA_VAR),
            "the notice must name the hash variable: {n}"
        );
        assert!(n.contains("release build"), "the notice must say why: {n}");
        assert!(
            n.contains("ignores"),
            "the notice must say what happens: {n}"
        );
        assert!(
            n.contains("pinned"),
            "the notice must say what is used instead: {n}"
        );
        assert!(
            !n.contains("are set"),
            "either variable can be set on its own, so the notice must not say both are: {n}"
        );
    }

    /// The loader's refusal names both variables, the long one on its own.
    #[test]
    fn the_missing_hash_message_names_both_variables() {
        assert!(MISSING_HASH_MESSAGE.starts_with(&format!("{MODEL_VAR} ")));
        assert!(MISSING_HASH_MESSAGE.contains(MODEL_SHA_VAR));
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

    #[cfg(unix)]
    #[test]
    fn a_debug_build_treats_a_hash_that_is_not_utf8_as_missing() {
        let r = resolve(BuildProfile::Debug, set(), Some(not_utf8()));
        assert_eq!(
            r.source,
            ModelSource::DeveloperOverride {
                path: PathBuf::from(PATH),
                sha256: None,
            }
        );
    }

    #[test]
    fn a_debug_build_treats_an_empty_model_value_as_an_override_to_the_empty_path() {
        let r = resolve(BuildProfile::Debug, Some(OsString::new()), sha());
        assert_eq!(
            r.source,
            ModelSource::DeveloperOverride {
                path: PathBuf::new(),
                sha256: Some(SHA.to_string()),
            }
        );
    }

    #[test]
    fn a_debug_build_without_the_variables_uses_the_pinned_model() {
        let r = resolve(BuildProfile::Debug, None, None);
        assert_eq!(r.source, ModelSource::Pinned);
        assert_eq!(r.notice, None);
    }

    #[test]
    fn the_notice_is_written_once_and_is_exactly_the_fixed_line() {
        let printed = AtomicBool::new(false);
        let mut out = Vec::new();
        assert!(announce(
            Some(RELEASE_IGNORES_OVERRIDE_NOTICE),
            &printed,
            &mut out
        ));
        assert!(
            !announce(Some(RELEASE_IGNORES_OVERRIDE_NOTICE), &printed, &mut out),
            "a second call must not write again (stt_ready is polled)"
        );
        assert_eq!(
            String::from_utf8(out).expect("utf-8"),
            format!("{RELEASE_IGNORES_OVERRIDE_NOTICE}\n"),
            "two calls must write exactly one line, and only the fixed text"
        );
    }

    #[test]
    fn nothing_to_announce_writes_nothing_and_keeps_the_one_write() {
        let printed = AtomicBool::new(false);
        let mut out = Vec::new();
        assert!(!announce(None, &printed, &mut out));
        assert!(out.is_empty(), "None wrote something: {out:?}");
        assert!(
            announce(Some(RELEASE_IGNORES_OVERRIDE_NOTICE), &printed, &mut out),
            "a None must not use up the one write"
        );
    }

    /// The release path end to end, short of the real environment: the decision, then the write.
    /// What reaches the output is exactly the fixed line, so neither the path nor the hash.
    #[test]
    fn the_release_path_writes_the_notice_and_returns_the_pinned_model() {
        let printed = AtomicBool::new(false);
        let mut out = Vec::new();
        let source = source_and_announce(
            resolve(BuildProfile::Release, set(), sha()),
            &printed,
            &mut out,
        );
        assert_eq!(source, ModelSource::Pinned);
        let text = String::from_utf8(out).expect("utf-8");
        assert_eq!(text, format!("{RELEASE_IGNORES_OVERRIDE_NOTICE}\n"));
        assert!(!text.contains(PATH) && !text.contains(SHA));
    }

    #[test]
    fn the_debug_path_writes_nothing() {
        let printed = AtomicBool::new(false);
        let mut out = Vec::new();
        let source = source_and_announce(
            resolve(BuildProfile::Debug, set(), sha()),
            &printed,
            &mut out,
        );
        assert!(matches!(source, ModelSource::DeveloperOverride { .. }));
        assert!(out.is_empty(), "a debug build wrote: {out:?}");
    }

    /// Restores both variables when the test ends, including on a failed assertion, so a failure
    /// here cannot leave them set for the next test that takes `ENV_LOCK`.
    struct OverrideVars;

    impl OverrideVars {
        fn set(path: impl AsRef<std::ffi::OsStr>, sha: &str) -> Self {
            set_override(path, sha);
            OverrideVars
        }
    }

    impl Drop for OverrideVars {
        fn drop(&mut self) {
            clear_override();
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

    /// The real entry point reads both variables with `var_os`, so values that are not UTF-8 are
    /// seen rather than silently dropped: in debug a non-UTF-8 model path is honoured (the old
    /// `std::env::var` read in `load_recognizer` ignored it), in release a non-UTF-8 hash on its
    /// own still produces the notice.
    #[cfg(unix)]
    #[test]
    fn the_real_entry_point_sees_values_that_are_not_utf8() {
        let _env_guard = crate::env_locked();
        let _vars = OverrideVars::set(not_utf8(), SHA);
        let r = resolution_from_env();
        if cfg!(debug_assertions) {
            assert_eq!(
                r.source,
                ModelSource::DeveloperOverride {
                    path: PathBuf::from(not_utf8()),
                    sha256: Some(SHA.to_string()),
                },
                "a non-UTF-8 SELAHCUE_STT_MODEL was dropped: the model read is not var_os"
            );
        } else {
            assert_eq!(r.source, ModelSource::Pinned);
        }

        clear_override();
        std::env::set_var(MODEL_SHA_VAR, not_utf8());
        let r = resolution_from_env();
        assert_eq!(r.source, ModelSource::Pinned);
        if cfg!(debug_assertions) {
            assert_eq!(
                r.notice, None,
                "a lone hash variable means nothing in debug"
            );
        } else {
            assert_eq!(
                r.notice,
                Some(RELEASE_IGNORES_OVERRIDE_NOTICE),
                "a non-UTF-8 hash on its own was not seen: the hash read is not var_os"
            );
        }
    }

    /// The wrapper the worker and `stt_ready` call returns exactly what [`resolution_from_env`]
    /// decided, so nothing between the decision and its callers can change the answer.
    #[test]
    fn the_callers_entry_point_returns_the_decision_from_the_real_environment() {
        let _env_guard = crate::env_locked();
        let _vars = OverrideVars::set(PATH, SHA);
        assert_eq!(
            super::test_support::override_vars(),
            (Some(OsString::from(PATH)), Some(OsString::from(SHA))),
            "premise: the test helper set both variables"
        );
        assert_eq!(model_source_from_env(), resolution_from_env().source);
        drop(_vars);
        assert_eq!(
            super::test_support::override_vars(),
            (None, None),
            "the test helper must clear both variables on drop"
        );
        assert_eq!(
            model_source_from_env(),
            ModelSource::Pinned,
            "with neither variable set every build uses the pinned model"
        );
    }

    /// Whether `line` would let a file outside this module read the variables: it spells either
    /// name as the start of a string literal, or names this module's private constants as whole
    /// identifiers (the way a read through a widened constant would look).
    fn names_an_override_variable(line: &str) -> bool {
        let is_ident = |c: char| c.is_ascii_alphanumeric() || c == '_';
        let has_word = |word: &str| {
            line.match_indices(word).any(|(i, _)| {
                let before = line[..i].chars().next_back();
                let after = line[i + word.len()..].chars().next();
                !before.is_some_and(is_ident) && !after.is_some_and(is_ident)
            })
        };
        line.contains("\"SELAHCUE_STT_MODEL") || has_word("MODEL_VAR") || has_word("MODEL_SHA_VAR")
    }

    /// Positive control for the scan below: it catches a direct read of either variable, a local
    /// constant holding a name, and a read through this module's constants (which today also
    /// fails to compile because they are private), and leaves prose and look-alike names alone.
    #[test]
    fn the_source_scan_catches_each_way_of_naming_the_variables() {
        let flagged = [
            "let p = std::env::var(\"SELAHCUE_STT_MODEL\");",
            "const NAME: &str = \"SELAHCUE_STT_MODEL_SHA256\";",
            "let p = std::env::var_os(crate::stt_model_source::MODEL_VAR);",
            "use crate::stt_model_source::MODEL_SHA_VAR;",
            "    std::env::var(MODEL_VAR)",
        ];
        for line in flagged {
            assert!(names_an_override_variable(line), "missed: {line}");
        }
        let allowed = [
            "// `SELAHCUE_STT_MODEL` in a comment is fine",
            "let HF_MODEL_VARIANT = 1;",
            "std::env::set_var(MY_MODEL_VAR_X, p);",
            "stt_model_source::model_source_from_env()",
            "stt_model_source::MISSING_HASH_MESSAGE",
        ];
        for line in allowed {
            assert!(!names_an_override_variable(line), "false alarm: {line}");
        }
    }

    /// Every other file under `src/` must reach the variables through [`model_source_from_env`].
    #[test]
    fn no_other_source_file_names_the_override_variables() {
        let src = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
        let mut offenders = Vec::new();
        let mut scanned: Vec<String> = Vec::new();
        let mut dirs = vec![src];
        while let Some(dir) = dirs.pop() {
            for entry in std::fs::read_dir(&dir).expect("read src/") {
                let path = entry.expect("read a src/ entry").path();
                if path.is_dir() {
                    dirs.push(path);
                    continue;
                }
                let name = path
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or_default()
                    .to_string();
                if !name.ends_with(".rs") || name == "stt_model_source.rs" {
                    continue;
                }
                let text = std::fs::read_to_string(&path).expect("read a source file");
                for (n, line) in text.lines().enumerate() {
                    if names_an_override_variable(line) {
                        offenders.push(format!("{}:{}", path.display(), n + 1));
                    }
                }
                scanned.push(name);
            }
        }
        // Premise: the two files that consume this module were actually read, so an empty
        // offender list means "none found", not "nothing scanned".
        for consumer in ["listening.rs", "main.rs"] {
            assert!(
                scanned.iter().any(|n| n == consumer),
                "premise: the scan did not read {consumer}; it read {scanned:?}"
            );
        }
        assert!(
            scanned.len() >= 10,
            "premise: the scan read the crate's sources ({} files)",
            scanned.len()
        );
        assert!(
            offenders.is_empty(),
            "these lines name {MODEL_VAR} or {MODEL_SHA_VAR} (as a string literal or through this \
             module's constants) outside stt_model_source.rs; go through model_source_from_env() \
             so a release build keeps ignoring them: {offenders:?}"
        );
    }
}
