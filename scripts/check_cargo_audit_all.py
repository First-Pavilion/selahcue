#!/usr/bin/env python3
"""Self-test for scripts/cargo_audit_all.sh (the script behind `make audit`, 17tnw2b9ax3).

    check_cargo_audit_all.py --self-test     exit 0 when every case behaves, 1 otherwise

`make audit` exists so a RustSec vulnerability cannot hide when hosted CI is down. A gate like that
is only worth having if it can not print PASS when it should not, so this drives the REAL script
against throwaway git repositories with a stub standing in for `cargo`, offline (no network, no
cargo-audit, no advisory database), and asserts the exit status and the audit trail for each way the
script could lie:

  * a vulnerable root among clean ones must fail, with every root still run and the bad one named;
  * a missing cargo-audit, no Cargo.lock at all, a `.gitmodules`, a newline in a lock's path, a
    tracked lock deleted from the working tree, a local `audit.toml` that can silently ignore
    advisories, and an `[alias] audit = ...` that makes `cargo audit` run something else must each
    exit 2 ("could not check") and audit nothing, never 0;
  * only a file named exactly `Cargo.lock` is a root (`NotCargo.lock` and `untracked.Cargo.lock`
    are not), a gitignored lock is not, and an untracked-but-not-ignored one is;
  * a directory whose name starts with `-`, has a space, or is non-ASCII is audited as itself, not
    as the repository root (the false PASS this script used to give for a `-dir`).

The stub prints a `cargo-audit` version line for `audit --version`, as the real tool does, so the
script's alias check has something real to look at. It takes its instructions from marker files in
the directory it is run in: `FAIL` makes `audit` exit non-zero, `ALIAS` makes `audit --version`
print a plain `cargo` version (what an `[alias]` to `version` would do).

It also holds the Makefile half of the same promise, with `make -n ci` (a dry run: no network, no
builds): the audit is the LAST gate of `make ci`, so it can never hide an earlier gate (make stops at
the first failing line); `AUDIT=skip` is the one documented offline opt-out and is LOUD (a message on
stderr, repeated in the closing banner) and never silent; an unrecognised `AUDIT` value is never
treated as a skip (and the banner agrees with the branch about which values those are); `make audit`
itself ignores the opt-out; nothing in the Makefile may swallow a failing audit (a `-` prefix on the
audit line, a `.IGNORE` target), and `make -i` makes the closing banner say errors were ignored.

The script must also be stoppable: SIGINT, SIGTERM and SIGHUP end it with 130, 143 and 129 and remove
its temporary file, instead of being absorbed by a trap that lets the audit carry on to "OK".

Standard library only; needs `git`, `make` and a POSIX `sh`, so it is skipped on Windows (as CI does).
"""

import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "cargo_audit_all.sh")
# The shell the script runs under. CI's Linux runner has dash as sh; set CARGO_AUDIT_ALL_SHELL=dash
# (or bash) to try the same cases under another shell.
SHELL_UNDER_TEST = os.environ.get("CARGO_AUDIT_ALL_SHELL", "sh")

STUB = """#!/bin/sh
# Stand-in for `cargo`. Only `cargo audit ...` is understood.
[ "$1" = "audit" ] || { echo "fakecargo: unexpected args: $*" >&2; exit 99; }
if [ "${2:-}" = "--version" ]; then
  [ -n "${FAKE_NO_AUDIT:-}" ] && { echo "error: no such command: audit" >&2; exit 101; }
  if [ -n "${FAKE_ALIAS_ENV:-}" ]; then
    echo "warning: user-defined alias 'audit' is shadowing an external subcommand found at: '/x/cargo-audit'" >&2
    echo "error: unexpected argument '--version' found" >&2
    exit 1
  fi
  if [ -e ALIASWARN ]; then
    echo "warning: user-defined alias 'audit' is shadowing an external subcommand found at: '/x/cargo-audit'" >&2
  fi
  if [ -e ALIAS ]; then echo "cargo 9.9.9 (fake)"; exit 0; fi
  echo "cargo-audit-audit 0.0.0-fake"
  exit 0
fi
echo "fakecargo audit in: $(pwd)"
pwd >> "$FAKE_LOG"
if [ -n "${FAKE_SLEEP:-}" ]; then sleep "$FAKE_SLEEP"; fi
if [ -e FAIL ]; then exit "${FAKE_RC:-1}"; fi
exit 0
"""

# A cargo that records that it was run at all (then behaves like a passing cargo-audit). Proves a bad
# CARGO_HOME / HOME is refused BEFORE cargo is invoked: with a relative HOME a rustup-managed cargo
# starts installing a toolchain into the current directory.
TRIPWIRE_STUB = """#!/bin/sh
echo "cargo was run: $*" >> "$FAKE_TRIPWIRE"
if [ "$1" = "audit" ] && [ "${2:-}" = "--version" ]; then echo "cargo-audit-audit 0.0.0-fake"; exit 0; fi
exit 0
"""

# A cargo whose `audit` always fails, but which identifies itself as cargo-audit, so the script gets
# as far as running it. Used to prove a failing audit is not swallowed on the way out through make.
FAILING_STUB = """#!/bin/sh
if [ "$1" = "audit" ] && [ "${2:-}" = "--version" ]; then echo "cargo-audit-audit 0.0.0-fake"; exit 0; fi
if [ "$1" = "audit" ]; then echo "fakecargo: 1 vulnerability found" >&2; exit 1; fi
exit 99
"""


def norm(path):
    """Compare paths regardless of /tmp symlinks and macOS unicode normalisation."""
    return unicodedata.normalize("NFC", os.path.realpath(path))


class Fixture:
    """One throwaway git repository plus a stub cargo and an isolated HOME / CARGO_HOME."""

    def __init__(self):
        self.base = tempfile.mkdtemp(prefix="cargo-audit-all-selftest-")
        self.repo = os.path.join(self.base, "repo")
        self.home = os.path.join(self.base, "home")
        self.cargo_home = os.path.join(self.home, ".cargo")
        self.log = os.path.join(self.base, "audited.log")
        self.stub = os.path.join(self.base, "fakecargo.sh")
        self.failing_stub = os.path.join(self.base, "failingcargo.sh")
        self.tripwire_stub = os.path.join(self.base, "tripwirecargo.sh")
        self.tripwire = os.path.join(self.base, "tripwire.log")
        os.makedirs(self.repo)
        os.makedirs(self.cargo_home)
        for path, text in ((self.stub, STUB), (self.failing_stub, FAILING_STUB), (self.tripwire_stub, TRIPWIRE_STUB)):
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        open(self.log, "w").close()
        self._git("init", "-q")

    def _git(self, *args):
        subprocess.run(
            ["git", "-C", self.repo] + list(args),
            check=True,
            stdout=subprocess.DEVNULL,
            env=self.env(),
        )

    def env(self, **extra):
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.home,
            "CARGO_HOME": self.cargo_home,
            "FAKE_LOG": self.log,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        env.update(extra)
        return env

    def lock(self, rel_dir, *, fail=False, alias=False, aliaswarn=False, track=True, name="Cargo.lock"):
        """Create <rel_dir>/<name> (rel_dir "" is the repo root) and optionally `git add` it."""
        d = os.path.join(self.repo, rel_dir) if rel_dir else self.repo
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name)
        with open(path, "w") as f:
            f.write("# lock\n")
        if fail:
            open(os.path.join(d, "FAIL"), "w").close()
        if alias:
            open(os.path.join(d, "ALIAS"), "w").close()
        if aliaswarn:
            open(os.path.join(d, "ALIASWARN"), "w").close()
        if track:
            self._git("add", "--", os.path.relpath(path, self.repo))
        return path

    def write(self, rel, text=""):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return path

    def run(self, cargo=None, repo_arg=True, unset=(), **env_extra):
        """Run the script; returns (exit code, combined output, [directories the stub audited])."""
        open(self.log, "w").close()
        env = self.env(CARGO=cargo or self.stub, **env_extra)
        for key in unset:
            env.pop(key, None)
        cmd = [SHELL_UNDER_TEST, SCRIPT] + ([self.repo] if repo_arg else [])
        p = subprocess.run(
            cmd,
            cwd=self.base,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        with open(self.log) as f:
            audited = [norm(line.rstrip("\n")) for line in f if line.strip()]
        return p.returncode, p.stdout, audited

    def cleanup(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def audited_rel(self, audited):
        root = norm(self.repo)
        return sorted(os.path.relpath(a, root) for a in audited)


# "cafe" with an e-acute, built from a code point so this source file stays pure ASCII.
ACCENTED_DIR = "caf" + chr(0xE9)

FAILURES = []


def expect(cond, message, output=""):
    if not cond:
        FAILURES.append(message + ("\n    --- script output ---\n    " + output.replace("\n", "\n    ") if output else ""))


def case(fn):
    """Run one case in a fresh fixture, recording an exception as a failure."""
    fx = Fixture()
    try:
        fn(fx)
    except Exception as e:  # a crashing case is a failing case, not a skipped one
        FAILURES.append("%s raised %s: %s" % (fn.__name__, type(e).__name__, e))
    finally:
        fx.cleanup()


# --- cases -------------------------------------------------------------------------------------


def all_roots_clean_exit_0(fx):
    for d in ("a", "b/c", "d"):
        fx.lock(d)
    rc, out, audited = fx.run()
    expect(rc == 0, "clean roots: expected exit 0, got %d" % rc, out)
    expect(fx.audited_rel(audited) == ["a", "b/c", "d"], "clean roots: every root must be audited, got %r" % fx.audited_rel(audited), out)
    expect(out.count("PASS") == 3, "clean roots: expected three PASS lines", out)


def one_vulnerable_root_fails_but_every_root_runs(fx):
    fx.lock("a")
    fx.lock("bad/root", fail=True)
    fx.lock("c")
    rc, out, audited = fx.run()
    expect(rc == 1, "vulnerable root: expected exit 1, got %d" % rc, out)
    expect(fx.audited_rel(audited) == ["a", "bad/root", "c"], "vulnerable root: every root must still run, got %r" % fx.audited_rel(audited), out)
    expect("FAIL  bad/root" in out, "vulnerable root: the failing root must be named on a FAIL line", out)
    expect("PASS  a" in out and "PASS  c" in out, "vulnerable root: clean roots must still be reported PASS", out)
    expect(
        "did not pass (vulnerable, or could not be checked; see above)" in out,
        "vulnerable root: final line must say a root was vulnerable OR could not be checked",
        out,
    )


def any_nonzero_audit_status_is_a_failure(fx):
    # An advisory-fetch failure exits differently from a found vulnerability; both must fail.
    fx.lock("a", fail=True)
    rc, out, _ = fx.run(FAKE_RC="3")
    expect(rc == 1, "audit exit 3: expected overall exit 1, got %d" % rc, out)
    expect("FAIL  a" in out, "audit exit 3: root must be reported FAIL", out)


def missing_cargo_audit_is_exit_2(fx):
    fx.lock("a")
    rc, out, audited = fx.run(FAKE_NO_AUDIT="1")
    expect(rc == 2, "no cargo-audit: expected exit 2, got %d" % rc, out)
    expect(audited == [], "no cargo-audit: nothing may be audited", out)
    expect("cargo install cargo-audit" in out, "no cargo-audit: message must say how to install it", out)


def no_cargo_binary_at_all_is_exit_2(fx):
    fx.lock("a")
    rc, out, audited = fx.run(cargo=os.path.join(fx.base, "does-not-exist"))
    expect(rc == 2, "CARGO not executable: expected exit 2, got %d" % rc, out)
    expect(audited == [], "CARGO not executable: nothing may be audited", out)


def no_cargo_lock_is_exit_2(fx):
    fx.write("README.md", "x")
    fx._git("add", "README.md")
    rc, out, audited = fx.run()
    expect(rc == 2, "no Cargo.lock: expected exit 2 (never a clean pass for zero roots), got %d" % rc, out)
    expect(audited == [], "no Cargo.lock: nothing may be audited", out)


def alias_shadowing_audit_is_exit_2_and_audits_nothing(fx):
    fx.lock("a")
    fx.lock("b")
    fx.lock("c", alias=True)  # the LAST root is shadowed: a pre-pass must catch it before any root runs
    rc, out, audited = fx.run()
    expect(rc == 2, "alias: expected exit 2, got %d" % rc, out)
    expect(audited == [], "alias: no root may be audited when cargo audit is not cargo-audit, got %r" % audited, out)
    expect("alias" in out.lower(), "alias: the message must name the alias risk", out)


def audit_toml_in_cargo_home_is_exit_2(fx):
    fx.lock("a")
    with open(os.path.join(fx.cargo_home, "audit.toml"), "w") as f:
        f.write("[advisories]\nignore = []\n")
    rc, out, audited = fx.run()
    expect(rc == 2, "audit.toml in CARGO_HOME: expected exit 2, got %d" % rc, out)
    expect(audited == [], "audit.toml in CARGO_HOME: nothing may be audited", out)
    expect("audit.toml" in out, "audit.toml in CARGO_HOME: the message must name audit.toml", out)


def audit_toml_defaults_to_home_dot_cargo(fx):
    # With CARGO_HOME unset the script must look under $HOME/.cargo, as cargo-audit does.
    fx.lock("a")
    with open(os.path.join(fx.cargo_home, "audit.toml"), "w") as f:
        f.write("[advisories]\nignore = []\n")
    env = fx.env(CARGO=fx.stub)
    del env["CARGO_HOME"]
    p = subprocess.run([SHELL_UNDER_TEST, SCRIPT, fx.repo], cwd=fx.base, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    expect(p.returncode == 2, "audit.toml under $HOME/.cargo: expected exit 2, got %d" % p.returncode, p.stdout)


def audit_toml_in_repo_root_or_lock_dir_is_exit_2(fx):
    fx.lock("a")
    fx.write(".cargo/audit.toml", "[advisories]\nignore = []\n")
    rc, out, audited = fx.run()
    expect(rc == 2, "audit.toml in <repo>/.cargo: expected exit 2, got %d" % rc, out)
    expect(audited == [], "audit.toml in <repo>/.cargo: nothing may be audited", out)
    os.remove(os.path.join(fx.repo, ".cargo", "audit.toml"))
    fx.write("a/.cargo/audit.toml", "[advisories]\nignore = []\n")
    rc, out, audited = fx.run()
    expect(rc == 2, "audit.toml in <lock dir>/.cargo: expected exit 2, got %d" % rc, out)
    expect(audited == [], "audit.toml in <lock dir>/.cargo: nothing may be audited", out)


def only_a_file_named_exactly_cargo_lock_is_a_root(fx):
    fx.lock("real")
    # These match the pathspec '*Cargo.lock' but are not Cargo.lock. If they were audited the stub
    # would fail them (FAIL marker), so a leak shows up as exit 1 and as extra audited directories.
    fx.lock("notcargo", name="NotCargo.lock", fail=True)
    fx.lock("untracked", name="untracked.Cargo.lock", fail=True, track=False)
    rc, out, audited = fx.run()
    expect(rc == 0, "basename filter: expected exit 0, got %d" % rc, out)
    expect(fx.audited_rel(audited) == ["real"], "basename filter: only 'real' may be audited, got %r" % fx.audited_rel(audited), out)


def untracked_lock_counts_and_gitignored_lock_does_not(fx):
    fx.lock("tracked")
    fx.lock("fresh", track=False)  # untracked, not ignored: a brand new lock must still be audited
    fx.write(".gitignore", "ignored/\n")
    fx._git("add", ".gitignore")
    fx.lock("ignored", fail=True, track=False)
    rc, out, audited = fx.run()
    expect(rc == 0, "untracked/ignored: expected exit 0, got %d" % rc, out)
    expect(fx.audited_rel(audited) == ["fresh", "tracked"], "untracked/ignored: got %r" % fx.audited_rel(audited), out)


def top_level_dash_directory_is_audited_as_itself(fx):
    # `dirname` reads "-vuln/Cargo.lock" as an option, fails, and the old script then audited the
    # repository root and exited 0 with a blank name: a false PASS for a vulnerable lock.
    fx.lock("-vuln", fail=True)
    fx.write("README.md", "x")
    rc, out, audited = fx.run()
    expect(rc == 1, "-dir: a vulnerable lock under a '-' directory must exit 1 (not a false PASS), got %d" % rc, out)
    expect(fx.audited_rel(audited) == ["-vuln"], "-dir: must audit '-vuln', not the repo root, got %r" % fx.audited_rel(audited), out)
    expect("FAIL  -vuln" in out, "-dir: the root must be named", out)


def lock_at_the_repo_root_is_audited_as_the_repo_root(fx):
    fx.lock("")
    rc, out, audited = fx.run()
    expect(rc == 0, "repo-root lock: expected exit 0, got %d" % rc, out)
    expect(fx.audited_rel(audited) == ["."], "repo-root lock: got %r" % fx.audited_rel(audited), out)


def non_ascii_directory_is_audited_normally(fx):
    fx.lock(ACCENTED_DIR + "/crate", fail=True)
    fx.lock("plain")
    rc, out, audited = fx.run()
    expect(rc == 1, "non-ASCII dir: a vulnerable lock must exit 1, got %d" % rc, out)
    names = [unicodedata.normalize("NFC", n) for n in fx.audited_rel(audited)]
    expect(names == [ACCENTED_DIR + "/crate", "plain"], "non-ASCII dir: both roots must be audited, got %r" % names, out)


def directory_with_spaces_is_audited_normally(fx):
    fx.lock("my dir/sub dir", fail=True)
    rc, out, audited = fx.run()
    expect(rc == 1, "spaces: a vulnerable lock must exit 1, got %d" % rc, out)
    expect(fx.audited_rel(audited) == ["my dir/sub dir"], "spaces: got %r" % fx.audited_rel(audited), out)


def tracked_lock_deleted_from_the_working_tree_is_a_failure(fx):
    # Otherwise cargo-audit generates a fresh lock in that directory and audits THAT.
    fx.lock("a")
    gone = fx.lock("gone")
    fx.write("gone/Cargo.toml", "[package]\n")  # the directory still exists, as it would in a real crate
    os.remove(gone)
    rc, out, audited = fx.run()
    expect(rc != 0, "deleted lock: must not exit 0, got %d" % rc, out)
    expect("gone" in out and "missing" in out, "deleted lock: the message must name the missing lock", out)
    expect(audited == [], "deleted lock: nothing may be audited against a stale or regenerated lock, got %r" % audited, out)


def gitmodules_is_exit_2(fx):
    fx.lock("a")
    fx.write(".gitmodules", '[submodule "x"]\n\tpath = x\n\turl = https://example.invalid/x\n')
    rc, out, audited = fx.run()
    expect(rc == 2, ".gitmodules: expected exit 2, got %d" % rc, out)
    expect(audited == [], ".gitmodules: nothing may be audited", out)
    expect(".gitmodules" in out, ".gitmodules: the message must name it", out)


def newline_in_a_lock_path_is_exit_2(fx):
    fx.lock("evil\ndir")
    fx.lock("a")
    rc, out, audited = fx.run()
    expect(rc == 2, "newline in path: expected exit 2, got %d" % rc, out)
    expect(audited == [], "newline in path: nothing may be audited, got %r" % audited, out)
    expect("newline" in out.lower(), "newline in path: the message must say why", out)


def runs_from_the_script_default_when_given_no_argument(fx):
    # No repo argument: the script audits the checkout it lives in. Run a COPY of the script from a
    # repo that has the same relative layout (scripts/cargo_audit_all.sh) so this stays hermetic.
    fx.lock("a", fail=True)
    scripts = os.path.join(fx.repo, "scripts")
    os.makedirs(scripts)
    copy = os.path.join(scripts, "cargo_audit_all.sh")
    shutil.copyfile(SCRIPT, copy)
    p = subprocess.run(
        [SHELL_UNDER_TEST, copy],
        cwd=fx.base,
        env=fx.env(CARGO=fx.stub),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    expect(p.returncode == 1, "no argument: expected exit 1 from the vulnerable root, got %d" % p.returncode, p.stdout)


# --- Makefile half: `make -n ci` / `make -n audit` / `make help` -------------------------------------

AUDIT_CALL_SUFFIX = "--no-print-directory audit"


def make_dry_run(*args, audit_env=None):
    """`make -n <args>` in the repository root; returns (exit code, recipe lines, raw output).

    Recipe lines are the non-blank, non-comment lines make prints. The environment is scrubbed of
    everything that could carry an AUDIT setting in from the caller (an AUDIT variable, and the
    MAKEFLAGS that `make ci AUDIT=skip` hands to its children) so each case controls AUDIT itself.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("AUDIT", "MAKEFLAGS", "MFLAGS", "MAKELEVEL")}
    if audit_env is not None:
        env["AUDIT"] = audit_env
    p = subprocess.run(
        ["make", "-n"] + list(args),
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    lines = [l.strip() for l in p.stdout.splitlines() if l.strip() and not l.strip().startswith("#")]
    # Only the tail goes into a failure message: the whole dry run is 200 lines of unrelated gates.
    return p.returncode, lines, "...\n" + "\n".join(lines[-12:])


def audit_calls(lines):
    return [i for i, l in enumerate(lines) if l.endswith(AUDIT_CALL_SUFFIX)]


def only_banner_echoes_follow(lines, index):
    """After the audit step, nothing but the closing `echo` lines may remain."""
    return all(l.startswith("echo") for l in lines[index + 1 :])


def expect_audit_is_the_last_gate(lines, out, label):
    calls = audit_calls(lines)
    expect(len(calls) == 1, "%s: the audit must be invoked exactly once by `make ci`, found %d" % (label, len(calls)), out)
    if len(calls) != 1:
        return
    i = calls[0]
    expect(only_banner_echoes_follow(lines, i), "%s: only the closing banner echoes may follow the audit, got %r" % (label, lines[i + 1 :]), out)
    # Guard against the step being "last" only because the gates before it were deleted.
    before = " ".join(lines[:i])
    expect("flutter" in before and "cargo clippy" in before and "cargo test" in before, "%s: the audit must come AFTER the Flutter, clippy and test gates" % label, out)


def make_ci_runs_the_audit_as_its_last_gate(fx):
    rc, lines, out = make_dry_run("ci")
    expect(rc == 0, "make -n ci: expected exit 0, got %d" % rc, out)
    expect_audit_is_the_last_gate(lines, out, "AUDIT unset")
    expect(not any("SKIPPED" in l for l in lines), "AUDIT unset: nothing may mention a skip", out)
    expect("ALL GREEN" in lines[-1], "AUDIT unset: the closing banner must still say ALL GREEN", out)


def make_ci_empty_audit_value_runs_the_audit(fx):
    rc, lines, out = make_dry_run("ci", "AUDIT=")
    expect(rc == 0, "AUDIT= : expected exit 0, got %d" % rc, out)
    expect_audit_is_the_last_gate(lines, out, "AUDIT empty")
    expect(not any("SKIPPED" in l for l in lines), "AUDIT empty: nothing may mention a skip", out)


def make_ci_audit_skip_is_loud_and_skips_only_the_audit(fx):
    for how, args, audit_env in (("command line", ("ci", "AUDIT=skip"), None), ("environment", ("ci",), "skip")):
        label = "AUDIT=skip (%s)" % how
        rc, lines, out = make_dry_run(*args, audit_env=audit_env)
        expect(rc == 0, "%s: expected exit 0, got %d" % (label, rc), out)
        expect(audit_calls(lines) == [], "%s: the audit must NOT be invoked" % label, out)
        notices = [i for i, l in enumerate(lines) if "RustSec audit SKIPPED (AUDIT=skip)" in l]
        expect(len(notices) == 1, "%s: expected exactly one skip notice, found %d" % (label, len(notices)), out)
        if len(notices) == 1:
            expect(">&2" in lines[notices[0]], "%s: the notice must go to stderr" % label, out)
            expect("NOT checked" in lines[notices[0]], "%s: the notice must say vulnerabilities were not checked" % label, out)
            expect(only_banner_echoes_follow(lines, notices[0]), "%s: the notice must be the last gate, got %r" % (label, lines[notices[0] + 1 :]), out)
        expect("SKIPPED" in lines[-1] and "ALL GREEN" in lines[-1], "%s: the closing banner must repeat that the audit was skipped, got %r" % (label, lines[-1]), out)
        expect(any("cargo clippy" in l for l in lines) and "flutter" in " ".join(lines), "%s: every other gate must still be listed" % label, out)


def make_ci_unknown_audit_value_never_skips(fx):
    for value in ("0", "no", "skipp", "SKIP", "false", "skip x", "x skip", "skip skip"):
        label = "AUDIT=%s" % value
        rc, lines, out = make_dry_run("ci", "AUDIT=" + value)
        expect(rc == 0, "%s: expected exit 0 from the dry run, got %d" % (label, rc), out)
        expect_audit_is_the_last_gate(lines, out, label)
        expect(not any("SKIPPED" in l for l in lines), "%s: an unrecognised value must never be treated as a skip" % label, out)
        warned = [l for l in lines if "not understood" in l and ">&2" in l]
        expect(len(warned) == 1, "%s: expected one stderr warning that the value is not understood, found %d" % (label, len(warned)), out)


def make_ci_skip_and_warning_lines_really_run_and_never_fail(fx):
    # A dry run proves which branch is chosen, not that the printed shell line is valid. Run the
    # two notice lines the way make would, with sh, and check what they actually print and return.
    _, lines, out = make_dry_run("ci", "AUDIT=skip")
    skip = [l for l in lines if "RustSec audit SKIPPED (AUDIT=skip)" in l]
    _, lines2, out2 = make_dry_run("ci", "AUDIT=bogus")
    warn = [l for l in lines2 if "not understood" in l]
    expect(len(skip) == 1 and len(warn) == 1, "need exactly one skip line and one warning line to run", out + out2)
    for name, line, needle in (("skip notice", skip, "NOT checked"), ("unknown-value warning", warn, "not understood")):
        if len(line) != 1:
            continue
        p = subprocess.run(["sh", "-c", line[0]], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        expect(p.returncode == 0, "%s: must exit 0 (the opt-out must not fail the run), got %d" % (name, p.returncode), p.stderr)
        expect(p.stdout == "", "%s: must print nothing on stdout, got %r" % (name, p.stdout))
        expect(needle in p.stderr, "%s: must print %r on stderr, got %r" % (name, needle, p.stderr))
    if len(skip) == 1:
        p = subprocess.run(["sh", "-c", skip[0]], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        expect("make audit" in p.stderr, "skip notice: must tell the developer to run `make audit`, got %r" % p.stderr)


def make_audit_target_ignores_the_opt_out(fx):
    rc, lines, out = make_dry_run("audit", "AUDIT=skip")
    expect(rc == 0, "make -n audit AUDIT=skip: expected exit 0, got %d" % rc, out)
    expect(any("cargo_audit_all.sh" in l for l in lines), "make audit must still run the script when AUDIT=skip is given", out)
    expect(not any("SKIPPED" in l for l in lines), "make audit must not carry an opt-out", out)
    # A dry run cannot tell `sh scripts/cargo_audit_all.sh` from `if [ AUDIT = skip ]; then :; else ...`.
    # So run the REAL target, with the stub as cargo, against this checkout's own locks.
    git = subprocess.run(
        ["git", "-C", REPO, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*Cargo.lock"],
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    expected = sorted(os.path.dirname(f) or "." for f in git.stdout.split("\0") if f == "Cargo.lock" or f.endswith("/Cargo.lock"))
    open(fx.log, "w").close()
    p = subprocess.run(
        ["make", "-C", REPO, "audit", "AUDIT=skip", "CARGO=" + fx.stub],
        env=fx.env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    with open(fx.log) as f:
        audited = sorted(os.path.relpath(norm(l.rstrip("\n")), norm(REPO)) for l in f if l.strip())
    expect(p.returncode == 0, "make audit AUDIT=skip (stub cargo, real script): expected exit 0, got %d" % p.returncode, p.stdout[-600:])
    expect(expected != [] and audited == expected, "make audit AUDIT=skip must audit every root of this checkout %r, audited %r" % (expected, audited), p.stdout[-600:])
    expect("SKIPPED" not in p.stdout, "make audit AUDIT=skip must not skip anything", p.stdout[-600:])
    expect(p.stdout.count("PASS") == len(expected), "make audit AUDIT=skip: expected one PASS line per root", p.stdout[-600:])


def make_help_lists_audit_and_the_opt_out(fx):
    p = subprocess.run(["make", "help"], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    audit = [l for l in p.stdout.splitlines() if l.split()[:1] == ["audit"] or "[36maudit" in l]
    ci = [l for l in p.stdout.splitlines() if "[36mci " in l]
    expect(len(audit) == 1, "make help: expected one `audit` line, found %d" % len(audit), p.stdout)
    expect(len(ci) == 1 and "AUDIT=skip" in ci[0], "make help: the `ci` line must mention the AUDIT=skip opt-out", p.stdout)
    expect(len(audit) == 1 and "last step of `make ci`" in audit[0], "make help: the `audit` line must say it is the last step of `make ci`", p.stdout)


# --- cannot be stopped / cannot be fooled: signals, Makefile swallowing, CARGO_HOME, alias warnings ----


def _default_signals():
    # A background job of a non-interactive shell starts with SIGINT ignored, and an ignored signal
    # cannot be trapped; give the script the same defaults a terminal run has.
    for sig in (signal.SIGINT, signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, signal.SIG_DFL)


def signals_stop_the_script_and_clean_up(fx):
    # A trap that only removes the temp file lets the script carry on after the signal: it audited
    # every remaining root, printed OK and exited 0 (and Ctrl-C had to be pressed once per root).
    fx.lock("a")
    fx.lock("b")
    fx.lock("c")
    for name, sig, code in (("TERM", signal.SIGTERM, 143), ("INT", signal.SIGINT, 130), ("HUP", signal.SIGHUP, 129)):
        tmp = os.path.join(fx.base, "tmp-" + name)
        os.makedirs(tmp)
        open(fx.log, "w").close()
        proc = subprocess.Popen(
            [SHELL_UNDER_TEST, SCRIPT, fx.repo],
            cwd=fx.base,
            env=fx.env(CARGO=fx.stub, FAKE_SLEEP="2", TMPDIR=tmp),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            preexec_fn=_default_signals,
        )
        deadline = time.time() + 20
        while time.time() < deadline and os.path.getsize(fx.log) == 0:
            time.sleep(0.05)  # the first audit has started: the script is inside its loop
        started = os.path.getsize(fx.log) > 0
        proc.send_signal(sig)
        try:
            out, _ = proc.communicate(timeout=20)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            timed_out = True
        with open(fx.log) as f:
            audits = len([l for l in f if l.strip()])
        expect(started, "SIG%s: the first audit never started" % name, out)
        expect(not timed_out, "SIG%s: the script did not stop" % name, out)
        expect(proc.returncode == code, "SIG%s: expected exit %d, got %s" % (name, code, proc.returncode), out)
        expect("OK: every Cargo root passed" not in out, "SIG%s: a signalled run must never print the all-clear line" % name, out)
        expect(audits == 1, "SIG%s: the remaining roots must not be audited after the signal, %d were" % (name, audits), out)
        expect(os.listdir(tmp) == [], "SIG%s: the temporary file must be removed, found %r" % (name, os.listdir(tmp)), out)


def makefile_cannot_swallow_a_failing_audit(fx):
    with open(os.path.join(REPO, "Makefile")) as f:
        lines = f.read().splitlines()
    exact = "\t$(MAKE_RECURSE) --no-print-directory audit"
    calls = [l for l in lines if "--no-print-directory audit" in l and not l.lstrip().startswith("#")]
    expect(calls == [exact], "the audit line in the ci recipe must be exactly a tab and `$(MAKE_RECURSE) --no-print-directory audit` (no -, @- or +- prefix), found %r" % calls)
    ignore = [l for l in lines if re.match(r"\s*\.IGNORE\b", l)]
    expect(ignore == [], "the Makefile must not have an .IGNORE target (it makes make exit 0 past a failing audit), found %r" % ignore)
    targets = [i for i, l in enumerate(lines) if l.startswith("audit:")]
    expect(len(targets) == 1, "expected exactly one `audit:` target, found %d" % len(targets))
    if len(targets) == 1:
        recipe = lines[targets[0] + 1]
        expect(recipe == '\tCARGO="$(CARGO)" sh scripts/cargo_audit_all.sh', "the audit target's recipe line must have no ignore-errors prefix, got %r" % recipe)


def make_audit_fails_when_cargo_audit_fails(fx):
    # Behavioural twin of the text checks above: run the real target with a cargo whose audit fails.
    p = subprocess.run(
        ["make", "-C", REPO, "audit", "CARGO=" + fx.failing_stub],
        env=fx.env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    expect(p.returncode != 0, "make audit with a failing cargo audit must exit non-zero, got 0", p.stdout[-600:])
    expect("did not pass" in p.stdout, "make audit: the script itself must have run and reported the failure (not a precondition error)", p.stdout[-600:])
    expect("OK: every Cargo root passed" not in p.stdout, "make audit: a failing audit must never print the all-clear line", p.stdout[-600:])


def relative_cargo_home_is_exit_2(fx):
    # cargo-audit resolves a relative CARGO_HOME against the lock directory, the script against its
    # own cwd, so `<lockdir>/.cx/audit.toml` could silently ignore advisories while the script said PASS.
    fx.lock("a")
    fx.write("a/.cx/audit.toml", "[advisories]\nignore = []\n")
    for value in (".cx", "relative/home", "~/.cargo"):
        rc, out, audited = fx.run(CARGO_HOME=value)
        expect(rc == 2, "CARGO_HOME=%s: expected exit 2, got %d" % (value, rc), out)
        expect(audited == [], "CARGO_HOME=%s: nothing may be audited" % value, out)
        expect("CARGO_HOME" in out and "absolute" in out, "CARGO_HOME=%s: the message must say CARGO_HOME has to be absolute" % value, out)


def unset_or_relative_home_without_cargo_home_is_exit_2(fx):
    fx.lock("a")
    for label, kwargs in (("HOME unset", dict(unset=("HOME", "CARGO_HOME"))), ("HOME empty", dict(unset=("CARGO_HOME",), HOME="")), ("HOME relative", dict(unset=("CARGO_HOME",), HOME="rel/home"))):
        rc, out, audited = fx.run(**kwargs)
        expect(rc == 2, "%s: expected exit 2, got %d" % (label, rc), out)
        expect(audited == [], "%s: nothing may be audited" % label, out)
        expect("HOME" in out, "%s: the message must name HOME" % label, out)


def bad_environment_is_refused_before_cargo_runs(fx):
    fx.lock("a")
    cases = (
        ("relative CARGO_HOME", dict(CARGO_HOME="relative")),
        ("relative HOME", dict(HOME="rel/home", unset=("CARGO_HOME",))),
        ("unset HOME", dict(unset=("HOME", "CARGO_HOME"))),
    )
    for label, kwargs in cases:
        rc, out, _ = fx.run(cargo=fx.tripwire_stub, FAKE_TRIPWIRE=fx.tripwire, **kwargs)
        expect(rc == 2, "%s: expected exit 2, got %d" % (label, rc), out)
        expect(not os.path.exists(fx.tripwire), "%s: cargo must not be run at all before the environment is validated" % label, out)
        if os.path.exists(fx.tripwire):
            os.remove(fx.tripwire)
    # Positive control: with a good environment the very same stub IS run (so the tripwire can fire).
    rc, out, _ = fx.run(cargo=fx.tripwire_stub, FAKE_TRIPWIRE=fx.tripwire)
    expect(os.path.exists(fx.tripwire), "positive control: the tripwire stub must have been run with a good environment", out)


def absolute_or_empty_cargo_home_is_accepted(fx):
    fx.lock("a")
    rc, out, _ = fx.run(unset=("HOME",))  # CARGO_HOME (absolute) alone is enough
    expect(rc == 0, "absolute CARGO_HOME without HOME: expected exit 0, got %d" % rc, out)
    rc, out, _ = fx.run(CARGO_HOME="")  # empty means unset: falls back to $HOME/.cargo
    expect(rc == 0, "empty CARGO_HOME with a good HOME: expected exit 0, got %d" % rc, out)
    with open(os.path.join(fx.cargo_home, "audit.toml"), "w") as f:
        f.write("[advisories]\nignore = []\n")
    rc, out, audited = fx.run(CARGO_HOME="")
    expect(rc == 2 and audited == [], "empty CARGO_HOME must still look under $HOME/.cargo for audit.toml, got exit %d" % rc, out)


def alias_warning_on_stderr_is_exit_2(fx):
    # Cargo says so on stderr when an alias shadows the external subcommand. Even if stdout still
    # looks like cargo-audit, that warning means `cargo audit` is not (only) the tool.
    fx.lock("a")
    fx.lock("b", aliaswarn=True)
    rc, out, audited = fx.run()
    expect(rc == 2, "alias warning: expected exit 2, got %d" % rc, out)
    expect(audited == [], "alias warning: nothing may be audited, got %r" % audited, out)
    expect("alias" in out.lower() and "b" in out, "alias warning: the message must name the alias and the root", out)


def alias_that_breaks_the_global_check_is_named_as_an_alias(fx):
    fx.lock("a")
    rc, out, audited = fx.run(FAKE_ALIAS_ENV="1")
    expect(rc == 2, "environment alias: expected exit 2, got %d" % rc, out)
    expect(audited == [], "environment alias: nothing may be audited", out)
    expect("alias" in out.lower(), "environment alias: the message must say an alias is involved, not only that cargo audit is unavailable", out)


def make_ci_banner_admits_ignored_errors_under_make_i(fx):
    # `make -i` (the team reads whole logs with it) ignores a failing gate, audit included, and would
    # otherwise end on "ALL GREEN". Short, long and combined spellings must all be caught...
    for flags in (["-i"], ["--ignore-errors"], ["-i", "-k"], ["-ki"]):
        rc, lines, out = make_dry_run(*(flags + ["ci"]))
        expect(rc == 0, "make -n %s ci: expected exit 0, got %d" % (" ".join(flags), rc), out)
        expect("errors ignored (-i)" in lines[-1] and "ALL GREEN" not in lines[-1], "make %s: the closing banner must say errors were ignored and must not say ALL GREEN, got %r" % (" ".join(flags), lines[-1]), out)
    # ...and flags that merely contain the letter i somewhere (--no-print-directory) must not be.
    for flags in ([], ["-k"], ["--no-print-directory"], ["-s"]):
        rc, lines, out = make_dry_run(*(flags + ["ci"]))
        expect("ALL GREEN" in lines[-1] and "errors ignored" not in lines[-1], "make %s: the banner must be the plain ALL GREEN, got %r" % (" ".join(flags) or "(no flags)", lines[-1]), out)


CASES = [
    all_roots_clean_exit_0,
    one_vulnerable_root_fails_but_every_root_runs,
    any_nonzero_audit_status_is_a_failure,
    missing_cargo_audit_is_exit_2,
    no_cargo_binary_at_all_is_exit_2,
    no_cargo_lock_is_exit_2,
    alias_shadowing_audit_is_exit_2_and_audits_nothing,
    audit_toml_in_cargo_home_is_exit_2,
    audit_toml_defaults_to_home_dot_cargo,
    audit_toml_in_repo_root_or_lock_dir_is_exit_2,
    only_a_file_named_exactly_cargo_lock_is_a_root,
    untracked_lock_counts_and_gitignored_lock_does_not,
    top_level_dash_directory_is_audited_as_itself,
    lock_at_the_repo_root_is_audited_as_the_repo_root,
    non_ascii_directory_is_audited_normally,
    directory_with_spaces_is_audited_normally,
    tracked_lock_deleted_from_the_working_tree_is_a_failure,
    gitmodules_is_exit_2,
    newline_in_a_lock_path_is_exit_2,
    runs_from_the_script_default_when_given_no_argument,
    make_ci_runs_the_audit_as_its_last_gate,
    make_ci_empty_audit_value_runs_the_audit,
    make_ci_audit_skip_is_loud_and_skips_only_the_audit,
    make_ci_unknown_audit_value_never_skips,
    make_ci_skip_and_warning_lines_really_run_and_never_fail,
    make_audit_target_ignores_the_opt_out,
    make_help_lists_audit_and_the_opt_out,
    signals_stop_the_script_and_clean_up,
    makefile_cannot_swallow_a_failing_audit,
    make_audit_fails_when_cargo_audit_fails,
    relative_cargo_home_is_exit_2,
    unset_or_relative_home_without_cargo_home_is_exit_2,
    bad_environment_is_refused_before_cargo_runs,
    absolute_or_empty_cargo_home_is_accepted,
    alias_warning_on_stderr_is_exit_2,
    alias_that_breaks_the_global_check_is_named_as_an_alias,
    make_ci_banner_admits_ignored_errors_under_make_i,
]


def self_test():
    if not os.path.exists(SCRIPT):
        print("self-test: %s does not exist" % SCRIPT, file=sys.stderr)
        return 1
    for fn in CASES:
        case(fn)
    if FAILURES:
        print("check_cargo_audit_all --self-test: %d expectation(s) failed:" % len(FAILURES), file=sys.stderr)
        for f in FAILURES:
            print("  - " + f, file=sys.stderr)
        return 1
    print("check_cargo_audit_all --self-test: %d cases ok" % len(CASES))
    return 0


def main(argv):
    if argv == ["--self-test"]:
        return self_test()
    print("usage: check_cargo_audit_all.py --self-test", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
