//! Developer AI provider keys, read from the repo-root `.env` — **developer builds only**.
//!
//! # This is scaffolding, and it has a known replacement
//!
//! A provider key sitting on an engineer's workstation is exactly the thing that must never
//! ship. Nothing here is the design; it is the shortest honest path to having the two AI
//! features work at all while the platform side is built. The destinations are already agreed
//! and already ticketed:
//!
//! * **Deepgram** — the desktop asks the SelahCue platform for a short-lived, server-minted
//!   grant token (`POST /v1/stt/session`) and streams with that. Our Deepgram key never leaves
//!   our server and never reaches a workstation.
//! * **Sermon notes** — generation stays **proxied** through the SelahCue platform API, so the
//!   OpenAI key lives server-side and the desktop authenticates as an account, not as us.
//!
//! When either of those lands, its half of this module goes with it. Do not build anything new
//! on top of this, and do not extend it into a general configuration mechanism.
//!
//! # How to delete it — eight edits across seven files
//!
//! "It is designed to be deleted" is the whole justification for this module existing at all, so
//! the removal has to be written down rather than left as an exercise (Cody, PR #18 F10). Grep
//! for `dev-keys`, `dev_env` and `.env.sample`; the complete set today is:
//!
//! 1. `selahcue-operator/src/dev_env.rs` — this file; delete it.
//! 2. `selahcue-operator/src/main.rs` — the `mod dev_env;` declaration and its doc comment.
//! 3. `selahcue-operator/src/main.rs` — the `dev_env::load();` call at the top of `fn main`.
//! 4. `selahcue-operator/Cargo.toml` — the `dev-keys` entry in `[features]` and its comment.
//! 5. `Makefile` — the `cargo test $(OP) --features dev-keys` line in the `ci` target.
//! 6. `.github/workflows/ci.yml` — the `Clippy (dev-keys)` and `Test (dev-keys)` steps in the
//!    `operator` job, and the comment above them.
//! 7. `.env.sample` — delete it.
//! 8. `.gitignore` — the `!.env.sample` negation and its comment. **Leave `.env` ignored.**
//!
//! Deleting 1-4 without 5-6 leaves CI invoking a feature that no longer exists, which fails the
//! operator job on all three runners. Do them together.
//!
//! **Two comments outside that list will go stale and no grep for `dev_env` will find them.**
//! `selahcue-cloud`'s `direct_notes_provider` and `selahcue-stt-cloud`'s `Credential::new` both
//! trim before testing presence, and both explain that leniency by reference to this loader's
//! "absent means absent" guarantee. When this module goes, those comments are describing a
//! promise nobody makes any more — and the leniency they justify becomes load-bearing rather
//! than redundant. Re-word them; do not delete the trimming.
//!
//! # Why it is behind a feature, and why that feature can never ship
//!
//! Every line that opens a file lives behind `dev-keys`, which is **off by default**. Without
//! the feature the loader does not exist in the compiled artefact at all — not disabled at
//! runtime, not short-circuited, absent — so a release build cannot pick a key up from a stray
//! `.env` on the machine it happens to run on.
//!
//! A `dev-keys` build is additionally unshippable for a second, independent reason:
//! [`REPO_ROOT_ENV_FILE`] is resolved from `CARGO_MANIFEST_DIR` at compile time, so such a
//! binary carries the build machine's source path. That is deliberate. It means a
//! `dev-keys` artefact is obviously a developer artefact if one is ever found in the wild.
//!
//! # Why this is an allowlist and not a dotenv crate
//!
//! `scripts/dev_key_not_in_release.sh` records, at length, that a **runtime configuration
//! loader** is the one route its byte scan cannot close: a loader that obtains key material at
//! run time puts no literal key in the artefact, so the scan reports OK. The rule that closes
//! it is a review-enforced "no config loader in `selahcue-licensing`".
//!
//! This module is a runtime configuration loader. It is therefore written to be the smallest
//! possible one:
//!
//! * It lives in the operator **binary**, not in a library crate, so nothing can take it as a
//!   dependency and no other crate's guarantees are widened by it.
//! * It will only ever set — **or unset** — the three names in [`LOADABLE`]. Every other assignment in the file is
//!   parsed and then thrown away. It cannot be used to inject an arbitrary environment.
//! * It never sets a variable to an empty value, so a missing key stays missing and the feature
//!   that needs it can say which one — instead of handing a provider an empty credential and
//!   surfacing an authentication error for what is really a configuration mistake.
//! * An already-exported variable wins. The file fills gaps; it does not override the
//!   environment the operator was launched with.
//!
//! # What the two AI lanes consume
//!
//! Ordinary process environment variables, set before Tauri starts. Neither lane parses a file:
//!
//! ```text
//! std::env::var("DEEPGRAM_API_KEY")   // 86akby4yz — Deepgram streaming transcription
//! std::env::var("OPENAI_API_KEY")     // 86akby7d8 — OpenAI sermon notes
//! std::env::var("SELAHCUE_OPENAI_MODEL") // 86akby7d8 — QA model switch, NOT a credential
//! ```
//!
//! Absent means absent: `env::var` returns `NotPresent`, never `Ok("")`. A lane that needs a key
//! it cannot find should refuse to start and name the variable.
//!
//! That holds for **every** name this loader reports as missing, including one you exported blank
//! yourself before launching — such a variable is actively **cleared**, because reporting a key
//! missing while leaving an empty string in the environment makes the startup message a lie. The
//! only environment value this loader ever removes is a blank one for a name it is reporting
//! missing; a real credential you exported is never touched (see [`load_from`]).
//!
//! Do not weaken this on the grounds that consumers trim defensively. They do — and at least one
//! of them documents that leniency as unnecessary *because of this guarantee*, so tidying it away
//! on the strength of that comment would make the defect live again.

/// Deepgram's own name for its API key, used unchanged so a developer who already has one
/// exported for `deepgram`'s CLI or SDK needs no second spelling. Consumed by 86akby4yz.
#[cfg(any(feature = "dev-keys", test))]
pub const DEEPGRAM_API_KEY: &str = "DEEPGRAM_API_KEY";

/// OpenAI's own name for its API key, for the same reason. Consumed by 86akby7d8.
#[cfg(any(feature = "dev-keys", test))]
pub const OPENAI_API_KEY: &str = "OPENAI_API_KEY";

/// The GPT model sermon-note generation should ask for. Consumed by 86akby7d8.
///
/// **This is the third name, and it is not a credential — which is the whole basis on which the
/// allowlist was widened to admit it.** The owner asked for physical QA to be able to switch
/// between `gpt-5.6-luna` and `gpt-5.6-terra` without a rebuild. The alternative was to leave it
/// out and read it from the environment anyway, which would have been strictly worse: the loader
/// would read the line from `.env`, discard it, and QA would see the default model while
/// believing they had changed it — a silent no-op that looks exactly like success.
///
/// So the widening is the *fix* for that footgun rather than a convenience. The rule the list
/// exists to enforce is unchanged: a name gets in only when leaving it out would produce a
/// misleading outcome, and it is reviewed on that basis. Note what it is not — it carries no
/// secret, so admitting it does not enlarge the credential surface the module docs are about.
#[cfg(any(feature = "dev-keys", test))]
pub const SELAHCUE_OPENAI_MODEL: &str = "SELAHCUE_OPENAI_MODEL";

/// **The only names this loader will ever set.** Not a default, not a starting point — the
/// complete set. An assignment in `.env` for any other name is read and discarded, which is what
/// keeps this from being a general "inject an arbitrary environment from a file" mechanism. See
/// the module docs for why that distinction is load-bearing rather than tidy.
///
/// # The standing rule for adding a name
///
/// **Categorical: this loader never carries a credential name beyond the two it exists for.** New
/// credentials go through the platform path. There is no exception process, because an exception
/// process is how a two-name allowlist becomes a general environment injector one justified case
/// at a time.
///
/// **Per addition**, a non-credential name may be added only when *leaving it out would produce a
/// misleading outcome* — not merely an inconvenient one — and the addition must, in a single
/// commit: name its consumer, show that its failure mode on a hostile value is bounded and
/// honest, move every pin and posture statement that describes the old shape, and pass security
/// review before merge.
///
/// **There is no numeric cap, deliberately — a maximum invites filling to it.** The real bound is
/// this module's deletion date. Pressure to add a fourth name is evidence that the value belongs
/// in `ProvidersSettings` (persisted, operator-visible, surviving the loader) rather than here;
/// 86akbzxyc already puts model choice there. This whole mechanism is scaffolding for the
/// developer-key phase and dies with it.
///
/// [`SELAHCUE_OPENAI_MODEL`] is the third name and the only entry that is **not** a credential. It
/// was admitted because omitting it was the more dangerous option: the loader would have read the
/// line from `.env`, discarded it, and left physical QA switching models with no effect and no
/// signal — a silent no-op indistinguishable from success. Its scope is exactly that: physical-QA
/// convenience for the developer-key phase.
///
/// **Note the widening grows the CLEAR set, not just the write set.** Since `aeddf2d` the loader
/// `remove_var`s a name it reports missing, so a blank `SELAHCUE_OPENAI_MODEL=` in `.env` will
/// **unset** any value the operator was launched with. Harmless for a model name — it falls back
/// to the compiled default — but "the loader may unset this variable" is the surprising half of
/// admitting any future name, and it is the half to check first.
#[cfg(any(feature = "dev-keys", test))]
const LOADABLE: [&str; 3] = [DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL];

/// Pin the premise at compile time, beside the constant, per the repo's testing rules. Several
/// tests hard-code what they expect the allowlist to contain -- most importantly
/// `NEVER_EXPORTED`, which cannot see a name it was never told to look for. Widening the
/// allowlist must therefore break the build here and force those to be revisited, rather than
/// quietly making them vacuous.
///
/// It did exactly that when the third name was added (86akby7d8): this assertion failed the build,
/// and all eleven hard-coded expectations it guards were revisited one by one rather than the
/// change being discovered later.
///
/// **The property this proves — that a widening cannot be silent — IS the control.** A widening
/// that merely updates this number to make the build pass has defeated it. If you are changing
/// this line, the question to answer is not "what number makes it compile" but "which assertions
/// downstream now describe a shape that no longer exists".
#[cfg(any(feature = "dev-keys", test))]
const _: () = assert!(LOADABLE.len() == 3);

/// The repo-root `.env`, resolved at **compile time** from this crate's manifest directory
/// (`<root>/implementation/desktop/crates/selahcue-operator` — four levels down).
///
/// Compile-time rather than a runtime search for `.git` because it is deterministic and cannot
/// be redirected by the working directory the operator happens to be launched from. The cost is
/// that the build machine's source path is baked into the binary, which is acceptable — and
/// useful — only because this constant exists solely in a `dev-keys` build.
#[cfg(feature = "dev-keys")]
const REPO_ROOT_ENV_FILE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../../../.env");

/// What a load attempt did, in variable **names** only.
///
/// The redaction here is structural rather than careful. Every field holds `&'static str`,
/// while a value read from the file is either a `&str` borrowed from the file's contents or the
/// owned `String` that borrow is copied into. Neither is `'static`, so no value can be stored
/// in this type at all. Deriving `Debug` here is therefore safe, where deriving it on [`Plan`],
/// which does hold values, would not be.
///
/// Stated precisely because the weaker-sounding version is the true one: this is not a claim
/// that nothing in the module is `&'static str` (the message literals are), it is a claim that
/// no path exists from file contents into these three fields.
/// What became of the file itself. Carries no path and no content — see [`Report`] for why the
/// types here are deliberately incapable of holding either.
#[cfg(any(feature = "dev-keys", test))]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum FileState {
    /// Read successfully (including a legitimately empty file).
    Loaded,
    /// Not there. The normal state for a fresh clone.
    Absent,
    /// Present but unreadable — bad permissions, or not valid UTF-8.
    ///
    /// Distinguished from `Absent` because collapsing the two produces the single most
    /// misleading thing this module could say: "add your key to the repo-root .env" to a
    /// developer whose key is already in it and whose file simply could not be parsed
    /// (Quinn, PR #18 D2).
    Unreadable,
}

#[cfg(any(feature = "dev-keys", test))]
#[derive(Debug, Clone, PartialEq, Eq)]
struct Report {
    /// Whether the loader ran at all. `false` in a build without `dev-keys`.
    enabled: bool,
    /// Names now readable from the process environment, whether this loader set them or they
    /// were already exported.
    resolved: Vec<&'static str>,
    /// Names still absent. These are what the startup message has to name.
    missing: Vec<&'static str>,
    /// What became of the `.env` itself, so the message can tell "you have not written one yet"
    /// apart from "yours could not be read".
    file: FileState,
}

/// The decision a load would make, before anything is written to the process environment.
///
/// Separated from the write so the whole decision is testable as a pure function — no process
/// environment, no temporary files, no ordering between tests.
#[cfg(any(feature = "dev-keys", test))]
struct Plan {
    /// Names to write, with their values. **This is real key material.** It is why `Debug` is
    /// implemented by hand below instead of derived.
    to_set: Vec<(&'static str, String)>,
    /// Names already in the environment, which `.env` must not clobber.
    kept: Vec<&'static str>,
    /// Names neither exported nor supplied by the file.
    missing: Vec<&'static str>,
}

/// Hand-written so a key value cannot reach a log line, a panic message or a `dbg!` through the
/// one route people forget. `#[derive(Debug)]` here would print the values verbatim.
#[cfg(any(feature = "dev-keys", test))]
impl std::fmt::Debug for Plan {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let names: Vec<&'static str> = self.to_set.iter().map(|(name, _)| *name).collect();
        f.debug_struct("Plan")
            .field("to_set", &names)
            .field("kept", &self.kept)
            .field("missing", &self.missing)
            .finish()
    }
}

/// One matching pair of surrounding quotes removed, if there is one.
#[cfg(any(feature = "dev-keys", test))]
fn unquote(value: &str) -> Option<&str> {
    for quote in ['"', '\''] {
        if value.len() >= 2 && value.starts_with(quote) && value.ends_with(quote) {
            return Some(&value[1..value.len() - 1]);
        }
    }
    None
}

/// The value an assignment carries, with an inline comment removed.
///
/// `KEY=abc # my dev key` used to export the literal `abc # my dev key` and report the key
/// AVAILABLE — the provider then rejects it and the developer is debugging an authentication
/// error caused by a comment (Quinn, PR #18 D3). That is precisely the "confusing authentication
/// error instead of a clear configuration one" this module exists to avoid.
///
/// A comment must be preceded by whitespace, so a `#` **inside** a credential is only dropped
/// when it genuinely looks like a comment. And a **quoted** value is taken verbatim: quoting is
/// how a developer says "this `#` is part of my key".
#[cfg(any(feature = "dev-keys", test))]
fn value_of(raw: &str) -> &str {
    let trimmed = raw.trim();
    if let Some(inner) = unquote(trimmed) {
        return inner;
    }
    for (i, c) in trimmed.char_indices() {
        if c == '#' && trimmed[..i].ends_with(char::is_whitespace) {
            return trimmed[..i].trim_end();
        }
    }
    trimmed
}

/// Every well-formed `NAME=VALUE` assignment in `contents`, in file order, with **no allowlist
/// applied**.
///
/// Deliberately minimal: comments, blank lines, an optional `export ` prefix, and one layer of
/// surrounding quotes. No escape sequences, no `${...}` interpolation, no multi-line values. A
/// richer parser would be more surface area for a module whose whole purpose is to be deleted,
/// and none of the extra syntax buys a developer anything when the value is a flat API key.
///
/// This is the single definition of "what the file says" — [`plan`] consumes exactly this, and
/// so does the control that proves the allowlist rejects a name rather than failing to parse it.
#[cfg(any(feature = "dev-keys", test))]
fn assignments(contents: &str) -> Vec<(&str, &str)> {
    let mut out = Vec::new();
    for raw in contents.trim_start_matches('\u{feff}').lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let line = match line.strip_prefix("export ") {
            Some(rest) => rest.trim_start(),
            None => line,
        };
        let Some((name, value)) = line.split_once('=') else {
            continue;
        };
        let name = name.trim();
        if name.is_empty() {
            continue;
        }
        out.push((name, value_of(value)));
    }
    out
}

/// What a load of `contents` would do, given `already_set` to say which names the process
/// environment already carries.
///
/// Pure: it decides and reports, it does not act. **All four rules live here** — the allowlist,
/// "an exported variable wins", "a blank value is not a key" and "a NUL-bearing value is not a
/// key". [`load_from`] applies this selection verbatim and re-checks nothing.
///
/// An earlier revision of this comment claimed the write boundary re-checked the allowlist. It
/// does not, and no such code was ever written — the fix for Sana's F1 was a test, not a runtime
/// filter. A comment describing a control that does not exist is worse than no comment, because
/// the next reader trusts it (Cody, PR #18 F9).
///
/// The re-check was declined deliberately: a filter in `load_from` would **invert the failure
/// mode**, silently absorbing a future widening of the write loop and leaving the contradiction
/// latent, where a test fails loudly. So the guarantee for every rule above is a test that
/// asserts its effect on the **process environment** after `load_from` has run, never merely on
/// the [`Plan`] this function returns. F1 and F8 are both what happens when a rule has only the
/// latter.
#[cfg(any(feature = "dev-keys", test))]
fn plan(contents: &str, already_set: impl Fn(&str) -> bool) -> Plan {
    let found = assignments(contents);
    let mut planned = Plan {
        to_set: Vec::new(),
        kept: Vec::new(),
        missing: Vec::new(),
    };
    for name in LOADABLE {
        if already_set(name) {
            planned.kept.push(name);
            continue;
        }
        // Last assignment wins, the way a shell sourcing the file would behave.
        let value = found
            .iter()
            .rev()
            .find(|(found_name, _)| *found_name == name)
            .map(|(_, value)| *value);
        match value {
            // Two ways a value is not a key:
            //
            // * whitespace-only -- setting it would hand a provider an empty credential and turn
            //   a configuration mistake into an authentication error; and
            // * NUL-bearing -- `std::env::set_var` PANICS on a value containing a NUL byte, and
            //   the panic message embeds the ENTIRE value. Since the whole point of this module
            //   is that the value is a live credential, that panic would print a real secret to
            //   stderr. A NUL cannot appear in a key any provider would issue, so treating it as
            //   absent loses nothing and the operator reports the variable as missing by name.
            //   (Sana, PR #18 F2. The bytes reach us because NUL is valid UTF-8, so
            //   `read_to_string` accepts a `.env` containing one.)
            Some(value) if !value.trim().is_empty() && !value.contains('\0') => {
                planned.to_set.push((name, value.to_string()));
            }
            _ => planned.missing.push(name),
        }
    }
    planned
}

/// The post-write summary: which allowlisted names are now readable, and which are not.
#[cfg(any(feature = "dev-keys", test))]
fn report_of(planned: &Plan, enabled: bool, file: FileState) -> Report {
    let resolved = LOADABLE
        .into_iter()
        .filter(|name| {
            planned.to_set.iter().any(|(set, _)| set == name) || planned.kept.contains(name)
        })
        .collect();
    Report {
        enabled,
        resolved,
        missing: planned.missing.clone(),
        file,
    }
}

/// The lines to print at startup. **Names only** — see [`Report`] for why that is structural.
///
/// A missing key gets its own line naming that exact variable, because "some credential is
/// missing" sends a developer to the wrong file.
#[cfg(any(feature = "dev-keys", test))]
fn startup_lines(report: &Report) -> Vec<String> {
    if !report.enabled {
        return Vec::new();
    }
    let mut lines = Vec::new();
    if !report.resolved.is_empty() {
        lines.push(format!(
            "selahcue dev-keys: {} available (repo-root .env or the environment).",
            report.resolved.join(", ")
        ));
    }
    if report.file == FileState::Unreadable {
        lines.push(
            "selahcue dev-keys: the repo-root .env could not be read — bad permissions, or not \
             valid UTF-8. It was treated as EMPTY, so any keys it does contain were ignored. Fix \
             the file; do not add them again."
                .to_string(),
        );
    }
    for name in &report.missing {
        // The advice has to match the situation. Telling someone to add a key to a file that
        // already has it, because the file could not be parsed, is the most misleading thing
        // this module could say (Quinn, PR #18 D2).
        let advice = match report.file {
            FileState::Unreadable => "Fix the unreadable .env above rather than re-adding it.",
            _ => "Add it to the repo-root .env (see .env.sample).",
        };
        lines.push(format!(
            "selahcue dev-keys: {name} is not set. {advice} It is left unset rather than empty, \
             so the feature that needs it will refuse to start instead of sending an empty \
             credential."
        ));
    }
    lines
}

/// Read `path` and export the allowlisted names it supplies.
///
/// **Only compiled with `dev-keys`.** The `cfg` split below is the whole control this ticket
/// exists to install: without the feature there is no `read_to_string` in the artefact.
#[cfg(feature = "dev-keys")]
fn load_from(path: &std::path::Path) -> Report {
    // An absent `.env` is a normal state, not an error: the repo ships it empty and a developer
    // who has not filled it in yet should get the named-variable message below, not a failure to
    // start. An UNREADABLE one is different and must not be silently folded into "absent" — see
    // [`FileState::Unreadable`].
    let (contents, file) = match std::fs::read_to_string(path) {
        Ok(contents) => (contents, FileState::Loaded),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => (String::new(), FileState::Absent),
        Err(_) => (String::new(), FileState::Unreadable),
    };
    let planned = plan(&contents, |name| {
        std::env::var_os(name).is_some_and(|value| !value.to_string_lossy().trim().is_empty())
    });
    for (name, value) in &planned.to_set {
        // Safe here in the only sense that matters for `set_var`: `load` is the first statement
        // of `main`, so no other thread exists yet to observe the environment mid-write.
        std::env::set_var(name, value);
    }
    // A name reported MISSING must actually BE missing. Without this, a variable exported blank
    // before launch and absent from the file survives untouched: `plan` rightly declines to treat
    // it as set, so the operator says "left unset rather than empty" while `env::var` hands a lane
    // `Ok("")` (Quinn, PR #18 D1). The message and the environment disagreed.
    //
    // The removal is precisely targeted: a name only reaches `missing` when the environment holds
    // nothing for it or holds something blank — anything non-blank became `kept` in `plan` and
    // never gets here. So this can only ever clear a blank value, never a real credential.
    //
    // NOTE FOR ANYONE RE-RUNNING THE MUTATION BATTERY. This loop makes one previously-biting
    // mutation stop biting, and that is not a weakened test. Re-deriving the write loop above
    // WITHOUT the blank check used to leave `DEEPGRAM_API_KEY=""` in the environment; now this
    // loop removes it again, because a blank name is in `missing`. The mutant is behaviour-
    // preserving — an equivalent mutant — so nothing can observe it and no test should claim to.
    // The blank rule is still pinned twice over, and removing EITHER mechanism alone is caught:
    // delete `plan`'s blank guard and both `a_blank_or_whitespace_value_leaves_the_variable_unset`
    // and `a_blank_value_is_never_exported_as_an_empty_string` go red; delete this loop and
    // `every_name_reported_missing_is_absent_from_the_environment` goes red.
    for name in &planned.missing {
        if std::env::var_os(name).is_some() {
            std::env::remove_var(name);
        }
    }
    report_of(&planned, true, file)
}

/// The build without `dev-keys`: no file is opened and nothing is exported.
///
/// Compiled **only under `cfg(test)`**, so that a plain release build carries neither this nor
/// the real one. It exists so the disabled case has something to call and can assert on the
/// process environment afterwards.
#[cfg(all(not(feature = "dev-keys"), test))]
fn load_from(_path: &std::path::Path) -> Report {
    Report {
        enabled: false,
        resolved: Vec::new(),
        missing: Vec::new(),
        file: FileState::Absent,
    }
}

/// Called as the first statement of `main`, before any thread exists.
///
/// With `dev-keys`: reads the repo-root `.env`, exports what it is allowed to, and prints a line
/// per missing variable. Without it: does nothing, and no `.env` reading is compiled in.
#[cfg(feature = "dev-keys")]
pub fn load() {
    let report = load_from(std::path::Path::new(REPO_ROOT_ENV_FILE));
    for line in startup_lines(&report) {
        eprintln!("{line}");
    }
}

/// The default build: a no-op, and deliberately a silent one. A binary without the feature must
/// behave exactly as it did before this module existed.
#[cfg(not(feature = "dev-keys"))]
pub fn load() {}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used)]
    use super::*;

    /// A value that could not plausibly be anything but this suite's own probe, so a "the value
    /// did not appear" assertion cannot pass by coincidence.
    const PROBE: &str = "dev-env-loader-probe-4a91c7";

    /// `set_var`/`remove_var` are process-global, so every test that touches them takes this
    /// first. Poisoning is recovered from rather than unwrapped: a panic in one such test should
    /// fail that test, not cascade into the others.
    ///
    /// Declared out here rather than inside `mod enabled` so the **disabled** build's test can
    /// take it too. It previously could not: the lock was feature-gated, so the one test that
    /// runs without `dev-keys` mutated the process environment unsynchronised while sibling
    /// tests were calling `std::env::temp_dir()` on other threads (Cody, PR #18 F11).
    static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn locked() -> std::sync::MutexGuard<'static, ()> {
        ENV_LOCK
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// A private temp file, unique per test and per run, matching the operator's house pattern
    /// (`media_store`, `deck_library`) so the suite is safe under `cargo test`'s parallelism.
    fn temp_env_file(tag: &str, contents: &str) -> std::path::PathBuf {
        use std::sync::atomic::{AtomicU64, Ordering};
        static N: AtomicU64 = AtomicU64::new(0);
        let dir = std::env::temp_dir().join(format!(
            "selahcue-dev-env-{}-{tag}-{}",
            std::process::id(),
            N.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join(".env");
        std::fs::write(&path, contents).unwrap();
        path
    }

    // ---- the allowlist -------------------------------------------------------------------

    #[test]
    fn only_the_allowlisted_names_are_taken_from_the_file() {
        // Every value is distinct so the assertion below pins the name-to-value BINDING, not
        // just the set of names. A loader that matched the wrong line would otherwise export
        // AWS_SECRET_ACCESS_KEY's value under DEEPGRAM_API_KEY and still satisfy a names-only
        // check.
        let contents = format!(
            "{DEEPGRAM_API_KEY}={PROBE}-dg\n\
             SELAHCUE_CLOUD_URL=https://example.invalid\n\
             PATH=/tmp/hostile\n\
             AWS_SECRET_ACCESS_KEY={PROBE}-aws\n"
        );

        // POSITIVE CONTROL, and the reason it consumes `assignments` rather than re-deciding:
        // without it, "the loader ignored PATH" is indistinguishable from "the parser never
        // understood the line". `plan` calls this same function, so mutating the parse breaks
        // the control too, instead of leaving it vouching for a parser that stopped working.
        let parsed = assignments(&contents);
        let parsed_names: Vec<&str> = parsed.iter().map(|(name, _)| *name).collect();
        assert_eq!(
            parsed_names,
            vec![
                DEEPGRAM_API_KEY,
                "SELAHCUE_CLOUD_URL",
                "PATH",
                "AWS_SECRET_ACCESS_KEY"
            ],
            "the parser did not understand all four assignments, so the allowlist assertion \
             below would pass without the allowlist doing any work"
        );

        let planned = plan(&contents, |_| false);
        assert_eq!(
            planned.to_set,
            vec![(DEEPGRAM_API_KEY, format!("{PROBE}-dg"))],
            "either a name outside LOADABLE was planned for export \u{2014} the loader is no \
             longer an allowlist and can inject an arbitrary environment from the file \u{2014} or \
             an allowlisted name was bound to some other line's value"
        );
    }

    #[test]
    fn every_allowlisted_name_is_taken_when_the_file_supplies_them() {
        let contents = format!(
            "{DEEPGRAM_API_KEY}={PROBE}-dg\n{OPENAI_API_KEY}={PROBE}-oa\n\
             {SELAHCUE_OPENAI_MODEL}=gpt-5.6-luna\n"
        );
        let planned = plan(&contents, |_| false);
        assert_eq!(
            planned.to_set,
            vec![
                (DEEPGRAM_API_KEY, format!("{PROBE}-dg")),
                (OPENAI_API_KEY, format!("{PROBE}-oa")),
                (SELAHCUE_OPENAI_MODEL, "gpt-5.6-luna".to_string()),
            ],
            "the allowlist is refusing names it is supposed to accept, which would make every \
             'was not taken' assertion in this file vacuous"
        );
        assert!(planned.missing.is_empty());
    }

    // ---- absence is absence, never an empty key ------------------------------------------

    #[test]
    fn a_blank_or_whitespace_value_leaves_the_variable_unset() {
        let blank = format!("{DEEPGRAM_API_KEY}=\n{OPENAI_API_KEY}=\"   \"\n");

        // POSITIVE CONTROL: the same two lines with real values are taken, so "not taken" below
        // is about the blank value and not about the lines being malformed.
        let filled = format!("{DEEPGRAM_API_KEY}={PROBE}\n{OPENAI_API_KEY}={PROBE}\n");
        assert_eq!(
            plan(&filled, |_| false).to_set.len(),
            2,
            "the fixture shape is no longer accepted at all, so the blank-value assertion below \
             proves nothing about blank values"
        );

        let planned = plan(&blank, |_| false);
        assert!(
            planned.to_set.is_empty(),
            "an empty or whitespace-only value was exported; a provider would reject it and \
             report an authentication error for what is really a missing key"
        );
        assert_eq!(
            planned.missing,
            vec![DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL],
            "a blank value must be reported as missing so the startup line can name it"
        );
    }

    #[test]
    fn an_inline_comment_does_not_become_part_of_the_key() {
        // POSITIVE CONTROL: the same value with no comment is taken whole, so the assertions
        // below are about comment handling and not about the parser dropping tails generally.
        assert_eq!(
            plan(&format!("{DEEPGRAM_API_KEY}={PROBE}\n"), |_| false).to_set,
            vec![(DEEPGRAM_API_KEY, PROBE.to_string())],
            "the plain value is no longer parsed whole, so the comment assertions prove nothing"
        );

        let commented = format!("{DEEPGRAM_API_KEY}={PROBE} # my dev key\n");
        assert_eq!(
            plan(&commented, |_| false).to_set,
            vec![(DEEPGRAM_API_KEY, PROBE.to_string())],
            "an inline comment was exported as part of the credential. The provider then rejects \
             it and the developer debugs an authentication error caused by a comment — the exact \
             confusion this module exists to prevent (Quinn, PR #18 D3)"
        );

        // A `#` with no whitespace before it is part of the value: keys do contain punctuation,
        // and only something that looks like a comment should be treated as one.
        let hashed = format!("{DEEPGRAM_API_KEY}=abc#def\n");
        assert_eq!(
            plan(&hashed, |_| false).to_set,
            vec![(DEEPGRAM_API_KEY, "abc#def".to_string())],
            "a `#` inside a credential was dropped; only whitespace-preceded `#` is a comment"
        );

        // Quoting is how a developer says "this `#` is mine".
        let quoted = format!("{DEEPGRAM_API_KEY}=\"{PROBE} # literal\"\n");
        assert_eq!(
            plan(&quoted, |_| false).to_set,
            vec![(DEEPGRAM_API_KEY, format!("{PROBE} # literal"))],
            "a quoted value must be taken verbatim, comment marker and all"
        );
    }

    #[test]
    fn a_nul_bearing_value_is_not_treated_as_a_key() {
        let hostile = format!("{DEEPGRAM_API_KEY}={PROBE}\0tail\n");

        // POSITIVE CONTROL: the same line without the NUL IS taken, so the rejection below is
        // about the NUL and not about the fixture being malformed.
        let benign = format!("{DEEPGRAM_API_KEY}={PROBE}tail\n");
        assert_eq!(
            plan(&benign, |_| false).to_set.len(),
            1,
            "the fixture shape is no longer accepted at all, so the NUL assertion below proves \
             nothing about NUL bytes"
        );

        let planned = plan(&hostile, |_| false);
        assert!(
            planned.to_set.is_empty(),
            "a NUL-bearing value was planned for export. std::env::set_var panics on one and \
             embeds the ENTIRE value in the panic message, so this would print a live \
             credential to stderr (Sana, PR #18 F2)"
        );
        assert_eq!(
            planned.missing,
            vec![DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL]
        );
    }

    #[test]
    fn an_absent_file_reports_both_names_missing_rather_than_failing() {
        let planned = plan("", |_| false);
        assert!(planned.to_set.is_empty());
        assert_eq!(
            planned.missing,
            vec![DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL]
        );
    }

    // ---- the environment wins over the file ----------------------------------------------

    #[test]
    fn an_already_exported_variable_is_not_clobbered_by_the_file() {
        let contents = format!("{DEEPGRAM_API_KEY}={PROBE}\n");

        // POSITIVE CONTROL: the identical file IS taken when the variable is unset, so the
        // assertion below is about `already_set` and not about the file being unreadable.
        assert_eq!(
            plan(&contents, |_| false).to_set.len(),
            1,
            "the file is not being taken even with nothing exported, so 'kept' below would hold \
             for the wrong reason"
        );

        let planned = plan(&contents, |name| name == DEEPGRAM_API_KEY);
        assert!(
            planned.to_set.is_empty(),
            "the file overwrote a variable the operator was launched with"
        );
        assert_eq!(planned.kept, vec![DEEPGRAM_API_KEY]);
        assert_eq!(
            planned.missing,
            vec![OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL],
            "an exported variable must count as resolved, not missing"
        );
    }

    // ---- no value ever escapes ------------------------------------------------------------

    #[test]
    fn the_startup_lines_name_the_missing_variable_and_carry_no_value() {
        let contents = format!("{DEEPGRAM_API_KEY}={PROBE}\n");
        let planned = plan(&contents, |_| false);
        let lines = startup_lines(&report_of(&planned, true, FileState::Loaded));

        // POSITIVE CONTROL: there is something to inspect and it names the exact variable.
        // Without this, "no value appeared" would also hold for an empty message.
        assert!(
            lines.iter().any(|line| line.contains(OPENAI_API_KEY)),
            "no startup line named the missing variable {OPENAI_API_KEY}; a developer gets a \
             generic failure instead of the name of the thing to fix. Lines were: {lines:?}"
        );
        assert!(
            lines.iter().any(|line| line.contains(DEEPGRAM_API_KEY)),
            "no startup line reported the variable that WAS resolved"
        );

        for line in &lines {
            assert!(
                !line.contains(PROBE),
                "a key value reached a startup line: {line}"
            );
        }
    }

    #[test]
    fn the_plan_debug_rendering_carries_names_but_no_values() {
        let contents = format!("{DEEPGRAM_API_KEY}={PROBE}\n");
        let planned = plan(&contents, |_| false);
        let rendered = format!("{planned:?}");

        // POSITIVE CONTROL: the rendering is not empty and does name the variable, so the
        // redaction assertion below is not satisfied by a Debug impl that prints nothing.
        assert!(
            rendered.contains(DEEPGRAM_API_KEY),
            "the Plan Debug rendering does not name the variable it planned, so the redaction \
             check below would pass for a Debug impl that had simply stopped working: {rendered}"
        );
        assert!(
            !rendered.contains(PROBE),
            "the key value appeared in Plan's Debug output; a derived Debug would leak it into \
             any log line, panic message or dbg! that touches a Plan: {rendered}"
        );
    }

    #[test]
    fn a_disabled_report_prints_nothing_at_all() {
        let report = Report {
            enabled: false,
            resolved: vec![DEEPGRAM_API_KEY],
            missing: vec![OPENAI_API_KEY],
            file: FileState::Loaded,
        };
        assert!(
            startup_lines(&report).is_empty(),
            "a build without dev-keys printed a startup line; the default build must behave \
             exactly as it did before this module existed"
        );
    }

    // ---- parsing details -------------------------------------------------------------------

    #[test]
    fn comments_blank_lines_export_prefixes_and_quotes_are_handled() {
        let contents = format!(
            "\u{feff}# a comment\n\
             \n\
             export {DEEPGRAM_API_KEY}=\"{PROBE}\"\n\
             #{OPENAI_API_KEY}={PROBE}-commented-out\n\
             not-an-assignment\n"
        );
        let planned = plan(&contents, |_| false);
        assert_eq!(
            planned.to_set,
            vec![(DEEPGRAM_API_KEY, PROBE.to_string())],
            "the quoted, export-prefixed assignment did not survive parsing, or the commented-out \
             one did"
        );
        assert_eq!(planned.missing, vec![OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL]);
    }

    // ---- the control this ticket exists to install -----------------------------------------

    /// The one that matters: a build **without** `dev-keys` must not read a key file.
    ///
    /// Mutation-verified by deleting the `cfg(all(not(feature = "dev-keys"), test))` no-op above
    /// and un-gating the real `load_from`, which is exactly "remove the feature guard". The
    /// process-environment assertion then fails.
    #[cfg(not(feature = "dev-keys"))]
    #[test]
    fn a_build_without_dev_keys_does_not_read_a_key_file() {
        let _guard = locked();
        let contents = format!("{DEEPGRAM_API_KEY}={PROBE}\n");
        let path = temp_env_file("disabled", &contents);

        // POSITIVE CONTROL: this file is one the loader WOULD act on. Without it, a clean
        // environment below would equally well mean the fixture was junk the loader could never
        // have taken — which is the shape of vacuous test this repo keeps finding.
        let planned = plan(&contents, |_| false);
        assert_eq!(
            planned.to_set,
            vec![(DEEPGRAM_API_KEY, PROBE.to_string())],
            "the fixture is no longer a file this loader would act on, so the assertion below \
             would hold even if a disabled build did read it"
        );

        // Establish the precondition rather than assuming it: a developer may well have the
        // real variable exported in their shell.
        std::env::remove_var(DEEPGRAM_API_KEY);

        let report = load_from(&path);

        assert!(
            std::env::var_os(DEEPGRAM_API_KEY).is_none(),
            "a build WITHOUT the dev-keys feature read {} and exported {DEEPGRAM_API_KEY}. That \
             is the entire control: a release build must not be able to pick a credential up \
             from a file on the machine it happens to run on.",
            path.display()
        );
        assert!(
            !report.enabled,
            "the disabled loader reported itself as having run"
        );
    }

    /// The mirror image, compiled only with the feature on: the keys really do become readable.
    ///
    /// Run by `cargo test --features dev-keys` (wired into `make ci`). It touches the process
    /// environment, but it can never race the disabled test above — the two live in mutually
    /// exclusive `cfg` blocks and are never in the same binary. Its own siblings are serialised
    /// through `ENV_LOCK`.
    #[cfg(feature = "dev-keys")]
    mod enabled {
        use super::*;

        #[test]
        fn a_dev_keys_build_makes_every_variable_readable() {
            let _guard = locked();
            let path = temp_env_file(
                "enabled",
                &format!(
                    "{DEEPGRAM_API_KEY}={PROBE}-dg\n{OPENAI_API_KEY}={PROBE}-oa\n\
                     {SELAHCUE_OPENAI_MODEL}=gpt-5.6-luna\n"
                ),
            );
            std::env::remove_var(DEEPGRAM_API_KEY);
            std::env::remove_var(OPENAI_API_KEY);
            std::env::remove_var(SELAHCUE_OPENAI_MODEL);

            let report = load_from(&path);

            assert_eq!(
                std::env::var(DEEPGRAM_API_KEY).ok(),
                Some(format!("{PROBE}-dg")),
                "{DEEPGRAM_API_KEY} is not readable by the rest of the application"
            );
            assert_eq!(
                std::env::var(OPENAI_API_KEY).ok(),
                Some(format!("{PROBE}-oa")),
                "{OPENAI_API_KEY} is not readable by the rest of the application"
            );
            // The model is NOT a credential, but it travels the same path, so it is asserted
            // readable exactly like the keys — a per-variable exception would be harder to reason
            // about than uniform handling.
            assert_eq!(
                std::env::var(SELAHCUE_OPENAI_MODEL).ok(),
                Some("gpt-5.6-luna".to_string()),
                "{SELAHCUE_OPENAI_MODEL} is not readable, so QA could not switch model"
            );
            assert_eq!(
                report.resolved,
                vec![DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL]
            );
            assert!(report.missing.is_empty());
            assert!(startup_lines(&report)
                .iter()
                .all(|line| !line.contains(PROBE)));

            std::env::remove_var(DEEPGRAM_API_KEY);
            std::env::remove_var(OPENAI_API_KEY);
            std::env::remove_var(SELAHCUE_OPENAI_MODEL);
        }

        #[test]
        fn a_missing_file_leaves_the_variables_unset_and_names_them_both() {
            let _guard = locked();
            let path = temp_env_file("absent", "").with_file_name("no-such-.env");
            std::env::remove_var(DEEPGRAM_API_KEY);
            std::env::remove_var(OPENAI_API_KEY);

            let report = load_from(&path);

            assert!(
                std::env::var_os(DEEPGRAM_API_KEY).is_none()
                    && std::env::var_os(OPENAI_API_KEY).is_none(),
                "a missing .env must leave the variables unset, never set to an empty string"
            );
            assert_eq!(
                report.missing,
                vec![DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL]
            );
            let lines = startup_lines(&report);
            assert!(lines.iter().any(|l| l.contains(DEEPGRAM_API_KEY)));
            assert!(lines.iter().any(|l| l.contains(OPENAI_API_KEY)));
        }

        /// Names that must NEVER reach the process environment from a `.env`.
        ///
        /// **Hard-coded on purpose — do not derive this from [`LOADABLE`].** Deriving it would
        /// make the list shrink exactly when someone widens the allowlist, so the test would go
        /// quiet at the one moment it needs to speak. Written out, widening `LOADABLE` to admit
        /// any of these turns the test below red.
        const NEVER_EXPORTED: [&str; 3] = [
            "AWS_SECRET_ACCESS_KEY",
            "SELAHCUE_CLOUD_URL",
            "SELAHCUE_DEV_ENV_UNALLOWLISTED_PROBE",
        ];

        /// The allowlist, asserted at the boundary that actually matters: the **process
        /// environment** after the real [`load_from`] has run.
        ///
        /// Every other allowlist assertion in this file consumes [`plan`]'s verdict, which pins
        /// the decision but says nothing about what crosses `std::env::set_var`. Sana's review of
        /// PR #18 (F1) demonstrated the gap: widening only the write loop, while leaving "an
        /// exported variable wins" and the blank-value rule untouched, kept the whole suite green
        /// at 78/78. Reproduced here before this test was written, and it is green — so the
        /// finding is real and this test is the thing that closes it.
        ///
        /// It deliberately reads `std::env::var_os` and never looks at a `Plan`, so it cannot be
        /// satisfied by re-reading the layer that was already guarded.
        #[test]
        fn no_unallowlisted_name_reaches_the_process_environment() {
            let _guard = locked();

            // PREMISE PIN, in the test as well as beside the constant. NEVER_EXPORTED is
            // hard-coded and structurally cannot see a name that was just admitted to the
            // allowlist, so a widening would otherwise leave this test green for the worst
            // possible reason. Changing the allowlist fails here first.
            // Compared as SLICES, not arrays. `assert_eq!` on two differently-sized arrays is a
            // type error, so widening the allowlist would fail to compile here and the message
            // below -- the one that tells the next person what to do -- would never be printed.
            assert_eq!(
                LOADABLE.as_slice(),
                [DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL].as_slice(),
                "the allowlist changed. NEVER_EXPORTED below is hard-coded and cannot see a \
                 newly admitted name -- revisit the two together before touching this assertion."
            );

            let mut contents = format!("{DEEPGRAM_API_KEY}={PROBE}-dg\n");
            for name in NEVER_EXPORTED {
                contents.push_str(&format!("{name}={PROBE}-hostile\n"));
            }
            let path = temp_env_file("hostile", &contents);

            std::env::remove_var(DEEPGRAM_API_KEY);
            for name in NEVER_EXPORTED {
                std::env::remove_var(name);
            }

            load_from(&path);

            // POSITIVE CONTROL FIRST. If the loader did not run -- wrong path, unreadable file,
            // a `load_from` that quietly does nothing -- then "the hostile names are absent"
            // holds for a reason that has nothing to do with the allowlist.
            assert_eq!(
                std::env::var(DEEPGRAM_API_KEY).ok(),
                Some(format!("{PROBE}-dg")),
                "the loader did not export the allowlisted key from this fixture, so the \
                 assertions below would pass whether or not the allowlist is enforced"
            );

            for name in NEVER_EXPORTED {
                assert!(
                    std::env::var_os(name).is_none(),
                    "{name} was exported into the process environment from a .env file. The \
                     allowlist is enforced when the plan is built but not where the write \
                     happens, so this loader can inject an arbitrary environment -- which is the \
                     one property that keeps it from widening the licensing dev-key bypass \
                     route documented in scripts/dev_key_not_in_release.sh."
                );
            }

            std::env::remove_var(DEEPGRAM_API_KEY);
            for name in NEVER_EXPORTED {
                std::env::remove_var(name);
            }
        }

        /// The blank-value rule, asserted where the effect happens.
        ///
        /// `a_blank_or_whitespace_value_leaves_the_variable_unset` pins this at the [`plan`]
        /// layer, which is necessary and was not sufficient: Cody re-derived the write loop
        /// keeping the allowlist, the NUL guard and exported-wins, and dropping **only** the
        /// blank check — the whole suite stayed green at 81/81 while `DEEPGRAM_API_KEY` was
        /// exported as an empty string and the startup line still called it missing (PR #18 F8).
        ///
        /// That is the F1 shape surviving in a sibling rule, so this is the same fix: read the
        /// **process environment** after the real `load_from`, never a `Plan`.
        ///
        /// The failure it guards is specifically `Ok("")` rather than `NotPresent`. A lane that
        /// gets an empty string sends an empty credential and is told it authenticated badly,
        /// when in truth nobody set the key.
        #[test]
        fn a_blank_value_is_never_exported_as_an_empty_string() {
            let _guard = locked();

            // Each case pairs the blank variable with a REAL value on the other one, so the
            // positive control comes from the very same file: "the blank one is unset" cannot
            // pass because `load_from` failed to run on this fixture at all.
            for (tag, contents, blank, filled, filled_value) in [
                (
                    "bare",
                    format!("{DEEPGRAM_API_KEY}=\n{OPENAI_API_KEY}={PROBE}-oa\n"),
                    DEEPGRAM_API_KEY,
                    OPENAI_API_KEY,
                    format!("{PROBE}-oa"),
                ),
                (
                    "quoted-whitespace",
                    format!("{DEEPGRAM_API_KEY}={PROBE}-dg\n{OPENAI_API_KEY}=\"   \"\n"),
                    OPENAI_API_KEY,
                    DEEPGRAM_API_KEY,
                    format!("{PROBE}-dg"),
                ),
            ] {
                let path = temp_env_file(tag, &contents);
                std::env::remove_var(DEEPGRAM_API_KEY);
                std::env::remove_var(OPENAI_API_KEY);

                let report = load_from(&path);

                // POSITIVE CONTROL FIRST.
                assert_eq!(
                    std::env::var(filled).ok(),
                    Some(filled_value.clone()),
                    "[{tag}] the loader did not export {filled} from this fixture, so the \
                     blank-value assertion below would hold for the wrong reason"
                );

                // The assertion that matters. Deliberately does not print the value: this is a
                // credential path, and `is_none()` vs `Some("")` is the whole distinction.
                assert!(
                    std::env::var_os(blank).is_none(),
                    "[{tag}] {blank} was exported from a blank value. env::var now returns \
                     Ok(\"\") instead of NotPresent, so a lane sends an empty credential and is \
                     told it authenticated badly, when nobody set the key at all."
                );

                // The environment and the startup message must agree. Cody's mutation made them
                // diverge -- exported, yet still reported missing -- and a divergence between
                // what the operator DID and what it SAYS is its own defect.
                assert!(
                    report.missing.contains(&blank),
                    "[{tag}] {blank} is absent from the environment but the startup report does \
                     not name it, so the operator would stay silent about a key nobody supplied"
                );

                std::env::remove_var(DEEPGRAM_API_KEY);
                std::env::remove_var(OPENAI_API_KEY);
            }
        }

        /// The invariant the module header actually states, asserted in general:
        /// **every name in `report.missing` is absent from the process environment.**
        ///
        /// Every other blank-value test calls `remove_var` first, which establishes the very
        /// precondition that makes its own assertion reachable. So the suite was not vacuous — it
        /// was **narrower than the claim it appeared to support** (Quinn, PR #18 D1). The state
        /// nothing covered: a variable exported **blank before launch** and absent from the file.
        /// `plan` correctly declines to treat it as set, so it lands in `missing` and the operator
        /// prints "It is left unset rather than empty" — while `env::var` still returns `Ok("")`,
        /// because the loader had no reason to touch a variable it was not going to write.
        ///
        /// This test deliberately does **not** remove the variables under test beforehand. That
        /// omission is the whole point.
        #[test]
        fn every_name_reported_missing_is_absent_from_the_environment() {
            let _guard = locked();

            // Exported blank before launch, and supplied by no file.
            std::env::set_var(DEEPGRAM_API_KEY, "");
            std::env::set_var(OPENAI_API_KEY, "   ");
            let path = temp_env_file("already-blank", "# nothing here\n");

            let report = load_from(&path);

            // POSITIVE CONTROL: both really are reported missing, so the loop below has something
            // to check. An empty `missing` would make it pass while asserting nothing.
            assert_eq!(
                report.missing,
                vec![DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL],
                "neither name was reported missing, so the invariant loop below is vacuous"
            );

            for name in &report.missing {
                assert!(
                    std::env::var_os(name).is_none(),
                    "{name} is reported MISSING but is still present in the environment. The \
                     startup line tells the developer it is 'left unset rather than empty', and \
                     the module header promises a lane `NotPresent` rather than Ok(\"\") — both \
                     are false in this state. A lane is then saved only by defensive trimming in \
                     selahcue-cloud and selahcue-stt-cloud, one of which documents that leniency \
                     as unnecessary BECAUSE of this guarantee."
                );
            }

            std::env::remove_var(DEEPGRAM_API_KEY);
            std::env::remove_var(OPENAI_API_KEY);
        }

        /// An unreadable `.env` must not be reported as an absent one.
        ///
        /// Folding the two together produces the most misleading thing this module could say:
        /// "add your key to the repo-root .env" to a developer whose key is already in it and
        /// whose file merely failed to parse (Quinn, PR #18 D2).
        #[test]
        fn an_unreadable_env_file_is_not_reported_as_a_missing_one() {
            let _guard = locked();
            std::env::remove_var(DEEPGRAM_API_KEY);
            std::env::remove_var(OPENAI_API_KEY);

            // A real `.env` carrying real keys — that just happens not to be valid UTF-8.
            let path = temp_env_file("unreadable", "");
            let mut bytes = format!("{DEEPGRAM_API_KEY}={PROBE}\n").into_bytes();
            bytes.push(0xff);
            bytes.extend_from_slice(b"\n");
            std::fs::write(&path, &bytes).unwrap();

            let report = load_from(&path);
            let lines = startup_lines(&report);

            assert_eq!(
                report.file,
                FileState::Unreadable,
                "a present-but-unparseable .env was classified as {:?}",
                report.file
            );
            assert!(
                lines.iter().any(|l| l.contains("could not be read")),
                "nothing told the developer the file failed to parse; they will add keys to a \
                 file that already has them. Lines were: {lines:?}"
            );
            assert!(
                lines
                    .iter()
                    .filter(|l| l.contains(DEEPGRAM_API_KEY))
                    .all(|l| !l.contains("Add it to the repo-root .env")),
                "the operator told the developer to add a key that is already in the file it \
                 could not read. Lines were: {lines:?}"
            );

            // POSITIVE CONTROL: the same names in a READABLE file give the ordinary advice, so
            // the assertion above is about the unreadable state and not about the wording having
            // been removed altogether.
            let ok_path = temp_env_file("readable", "# no keys here\n");
            let ok_lines = startup_lines(&load_from(&ok_path));
            assert!(
                ok_lines
                    .iter()
                    .any(|l| l.contains("Add it to the repo-root .env")),
                "the ordinary advice has disappeared entirely, so the check above passes for the \
                 wrong reason. Lines were: {ok_lines:?}"
            );

            std::env::remove_var(DEEPGRAM_API_KEY);
            std::env::remove_var(OPENAI_API_KEY);
        }

        /// A NUL-bearing value must not reach `set_var`, which panics with the **whole value** in
        /// the message (Sana, PR #18 F2). With real credentials in `.env`, that panic prints a
        /// live secret to stderr.
        ///
        /// The assertion that this test does not panic is the point; a panic here is a failure.
        #[test]
        fn a_nul_bearing_value_does_not_panic_and_is_not_exported() {
            let _guard = locked();
            let path = temp_env_file("nul", &format!("{DEEPGRAM_API_KEY}={PROBE}\0tail\n"));
            std::env::remove_var(DEEPGRAM_API_KEY);

            let report = load_from(&path);

            assert!(
                std::env::var_os(DEEPGRAM_API_KEY).is_none(),
                "a NUL-bearing value was exported; set_var would have panicked and printed the \
                 credential"
            );
            assert_eq!(
                report.missing,
                vec![DEEPGRAM_API_KEY, OPENAI_API_KEY, SELAHCUE_OPENAI_MODEL],
                "a NUL-bearing value must be reported as missing so the operator names it"
            );
            assert!(
                startup_lines(&report).iter().all(|l| !l.contains(PROBE)),
                "the rejected value reached a startup line"
            );
        }

        #[test]
        fn an_exported_variable_survives_the_file() {
            let _guard = locked();
            let path = temp_env_file(
                "exported",
                &format!("{DEEPGRAM_API_KEY}={PROBE}-from-file\n"),
            );
            std::env::set_var(DEEPGRAM_API_KEY, format!("{PROBE}-from-shell"));

            let report = load_from(&path);

            assert_eq!(
                std::env::var(DEEPGRAM_API_KEY).ok(),
                Some(format!("{PROBE}-from-shell")),
                "the .env overwrote a variable the operator was launched with"
            );
            assert!(report.resolved.contains(&DEEPGRAM_API_KEY));

            std::env::remove_var(DEEPGRAM_API_KEY);
        }
    }
}
