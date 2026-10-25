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

Standard library only; needs `git` and a POSIX `sh`, so it is skipped on Windows (as CI does).
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "cargo_audit_all.sh")
# The shell the script runs under. CI's Linux runner has dash as sh; set CARGO_AUDIT_ALL_SHELL=dash
# (or bash) to try the same cases under another shell.
SHELL_UNDER_TEST = os.environ.get("CARGO_AUDIT_ALL_SHELL", "sh")

STUB = """#!/bin/sh
# Stand-in for `cargo`. Only `cargo audit ...` is understood.
[ "$1" = "audit" ] || { echo "fakecargo: unexpected args: $*" >&2; exit 99; }
if [ "${2:-}" = "--version" ]; then
  [ -n "${FAKE_NO_AUDIT:-}" ] && { echo "error: no such command: audit" >&2; exit 101; }
  if [ -e ALIAS ]; then echo "cargo 9.9.9 (fake)"; exit 0; fi
  echo "cargo-audit-audit 0.0.0-fake"
  exit 0
fi
echo "fakecargo audit in: $(pwd)"
pwd >> "$FAKE_LOG"
if [ -e FAIL ]; then exit "${FAKE_RC:-1}"; fi
exit 0
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
        os.makedirs(self.repo)
        os.makedirs(self.cargo_home)
        with open(self.stub, "w") as f:
            f.write(STUB)
        os.chmod(self.stub, os.stat(self.stub).st_mode | stat.S_IXUSR)
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

    def lock(self, rel_dir, *, fail=False, alias=False, track=True, name="Cargo.lock"):
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
        if track:
            self._git("add", "--", os.path.relpath(path, self.repo))
        return path

    def write(self, rel, text=""):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return path

    def run(self, cargo=None, repo_arg=True, **env_extra):
        """Run the script; returns (exit code, combined output, [directories the stub audited])."""
        open(self.log, "w").close()
        env = self.env(CARGO=cargo or self.stub, **env_extra)
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
    fx.lock(u"café/crate", fail=True)
    fx.lock("plain")
    rc, out, audited = fx.run()
    expect(rc == 1, "non-ASCII dir: a vulnerable lock must exit 1, got %d" % rc, out)
    names = [unicodedata.normalize("NFC", n) for n in fx.audited_rel(audited)]
    expect(names == [u"café/crate", "plain"], "non-ASCII dir: both roots must be audited, got %r" % names, out)


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
