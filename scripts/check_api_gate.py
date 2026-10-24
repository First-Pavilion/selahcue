#!/usr/bin/env python3
"""Self-test for the Makefile's `api-check` target (ClickUp 86ak5rjh7, API half).

`make ci` now runs the Django API gate through `make api-check`. A gate that cannot go red, or that
quietly skips, is worse than no gate, so this script tests the TARGET'S LOGIC, not the API's tests: it
copies the real Makefile into a scratch repo that holds a tiny fake `implementation/api` (a stand-in
`manage.py`, a stand-in `pytest` package, and an in-tree PEP 660 build backend, so nothing is
downloaded) and runs `make api-check` there under each situation the gate has to handle.

Why a fake API and not the real one: the real suite takes about two minutes and needs the network
for its pinned dependencies. What matters here is whether the Makefile builds the venv, rebuilds
it when it should, propagates a failing exit code, and refuses to skip. The REAL suite is exercised
by `make ci` itself.

Cases (each one a named function; `--only NAME` runs one):

  fresh_worktree_builds_venv_and_passes   no venv beforehand: build it, run all three commands, exit 0
  second_run_reuses_the_venv              no rebuild, stamp untouched
  postgres_redis_skips_are_stated         the output says the Postgres/Redis-only tests skip locally
  failing_test_goes_red                   non-zero, the failing test is named
  missing_migration_goes_red              non-zero, and pytest is NOT reached
  system_check_failure_goes_red           non-zero, and the later commands are NOT reached
  missing_pytest_fails_loudly             a dependency absent from the venv is an error, not a skip
  missing_interpreter_fails_loudly        no usable Python: non-zero, fix named, no venv, no stamp
  old_interpreter_fails_loudly            Python below 3.12: non-zero, fix named, no venv, no stamp
  failed_install_leaves_no_stamp          install fails: non-zero, no stamp; the next run retries
  changed_pyproject_rebuilds_the_venv     pyproject.toml newer than the stamp: rebuild
  wrong_tree_venv_is_refused              a venv installed from another checkout: non-zero, named
  ambient_database_env_is_scrubbed        SQL_ENGINE in the caller's environment cannot reach the run
  venv_path_cannot_be_overridden          `make api-check API_VENV=/elsewhere` does not move the venv
  runs_from_another_working_directory     `make -C <repo> api-check` from an unrelated cwd works
  makefile_from_wrong_directory_is_loud   `make -f <repo>/Makefile` from another cwd fails, not skips
  ci_target_runs_api_check                the REAL Makefile's `make -n ci` lists api-check, after
                                          marketing-check, exits 0, and creates nothing
  help_lists_api_check                    `make help` names the target and the skip

`--mutation-proof` breaks the Makefile on purpose, one thing at a time, and requires the named
case to go red for each. Run it after any edit to the target; a case that stays green when the
behaviour it names is removed guards nothing.

Needs Python >= 3.12 to build the scratch venv (CI pins 3.14): `API_PYTHON` or the same
`python3.14` the Makefile defaults to. Not found is an error, never a skip. The script itself is
3.9-compatible because `make ci` runs it with the system `python3`.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"

BACKEND = textwrap.dedent(
    '''\
    """In-tree PEP 660 backend: an editable install with no network and no setuptools."""
    import base64
    import hashlib
    import os
    import zipfile

    HERE = os.path.dirname(os.path.abspath(__file__))


    def get_requires_for_build_editable(config_settings=None):
        return []


    def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
        if os.path.exists(os.path.join(HERE, "BREAK_INSTALL")):
            raise RuntimeError("BREAK_INSTALL present: simulated failed install")
        name = "selahcue_api-0.0.0"
        files = {
            "selahcue_api_editable.pth": HERE + "\\n",
            name + ".dist-info/METADATA": "Metadata-Version: 2.1\\nName: selahcue-api\\nVersion: 0.0.0\\nProvides-Extra: dev\\n",
            name + ".dist-info/WHEEL": "Wheel-Version: 1.0\\nGenerator: fake\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n",
        }
        record = "".join("%s,,\\n" % p for p in files) + name + ".dist-info/RECORD,,\\n"
        wheel = name + "-py3-none-any.whl"
        with zipfile.ZipFile(os.path.join(wheel_directory, wheel), "w") as z:
            for p, body in files.items():
                z.writestr(p, body)
            z.writestr(name + ".dist-info/RECORD", record)
        return wheel
    '''
)

PYPROJECT = textwrap.dedent(
    """\
    [build-system]
    requires = []
    build-backend = "fakebackend"
    backend-path = ["."]

    [project]
    name = "selahcue-api"
    version = "0.0.0"

    [project.optional-dependencies]
    dev = []
    """
)

# `manage.py check` / `makemigrations --check --noinput`, with failure switches and a call log.
MANAGE = textwrap.dedent(
    """\
    import os
    import sys

    with open("calls.log", "a") as f:
        f.write("manage " + " ".join(sys.argv[1:]) + "\\n")
    if sys.argv[1:2] == ["check"]:
        print("System check identified no issues (0 silenced).")
        sys.exit(1 if os.path.exists("FAIL_CHECK") else 0)
    if sys.argv[1:2] == ["makemigrations"]:
        if os.path.exists("MISSING_MIGRATION"):
            print("Migrations for 'accounts': 0004_x.py")
            sys.exit(1)
        print("No changes detected")
        sys.exit(0)
    sys.exit(2)
    """
)

# `python -m pytest`: fails if the caller's SQL_ENGINE leaked in, or tests/test_broken.py exists.
FAKE_PYTEST = textwrap.dedent(
    """\
    import os
    import sys

    with open("calls.log", "a") as f:
        f.write("pytest " + " ".join(sys.argv[1:]) + "\\n")
    if "SQL_ENGINE" in os.environ:
        print("FAILED env leak: SQL_ENGINE=" + os.environ["SQL_ENGINE"])
        sys.exit(1)
    if os.path.exists("tests/test_broken.py"):
        print("FAILED tests/test_broken.py::test_it - assert False")
        print("1 failed, 3 passed")
        sys.exit(1)
    print("3 passed, 4 skipped in 0.01s")
    """
)


class CaseFailed(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise CaseFailed(msg)


def find_python():
    """The interpreter the scratch venv is built from: API_PYTHON, else python3.14/13/12 on PATH."""
    candidates = [os.environ.get("API_PYTHON")] if os.environ.get("API_PYTHON") else []
    candidates += ["python3.14", "python3.13", "python3.12"]
    for c in candidates:
        path = shutil.which(c)
        if not path:
            continue
        ok = subprocess.run([path, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"])
        if ok.returncode == 0:
            return path
    sys.exit("check_api_gate: no Python >= 3.12 found (tried API_PYTHON, python3.14, 3.13, 3.12): "
             "cannot build the scratch venv. This is an error, not a skip -- the Makefile gate needs it too.")


class Repo:
    """A scratch repo root: the Makefile under test plus a fake implementation/api."""

    def __init__(self, parent, makefile_text, python, name="repo"):
        self.root = Path(parent) / name
        self.api = self.root / "implementation" / "api"
        self.python = python
        (self.api / "selahcue_api").mkdir(parents=True)
        (self.api / "tests").mkdir()
        (self.api / "pytest").mkdir()
        (self.root / "Makefile").write_text(makefile_text)
        (self.api / "pyproject.toml").write_text(PYPROJECT)
        (self.api / "fakebackend.py").write_text(BACKEND)
        (self.api / "manage.py").write_text(MANAGE)
        (self.api / "selahcue_api" / "__init__.py").write_text("")
        (self.api / "pytest" / "__init__.py").write_text("")
        (self.api / "pytest" / "__main__.py").write_text(FAKE_PYTEST)
        (self.api / "tests" / "test_ok.py").write_text("")
        self.venv = self.api / ".venv"
        self.stamp = self.venv / ".selahcue-api-installed"

    def calls(self):
        log = self.api / "calls.log"
        return log.read_text().splitlines() if log.exists() else []

    def make(self, *args, python=None, env=None, cwd=None, makefile=None, timeout=600):
        e = dict(os.environ)
        for k in ("API_PYTHON", "SQL_ENGINE", "MAKEFLAGS", "MAKELEVEL", "MFLAGS"):
            e.pop(k, None)
        e.update(env or {})
        cmd = ["make"]
        cmd += ["-f", str(makefile)] if makefile else ["-C", str(self.root)]
        cmd += list(args)
        cmd.append("API_PYTHON=%s" % (python or self.python))
        p = subprocess.run(cmd, cwd=str(cwd or self.root), env=e, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr


def new_repo(ctx, name="repo"):
    return Repo(ctx["tmp"], ctx["makefile_text"], ctx["python"], name)


def built_repo(ctx):
    """The shared repo with a venv already built (builds it on first use)."""
    r = ctx.get("shared")
    if r is None:
        r = ctx["shared"] = new_repo(ctx, "shared")
        rc, out = r.make("api-check")
        check(rc == 0, "could not build the shared fixture venv:\n" + out)
    for f in ("FAIL_CHECK", "MISSING_MIGRATION", "BREAK_INSTALL"):
        (r.api / f).unlink(missing_ok=True)
    (r.api / "tests" / "test_broken.py").unlink(missing_ok=True)
    (r.api / "calls.log").unlink(missing_ok=True)
    return r


# --- cases ---------------------------------------------------------------------------------------


def fresh_worktree_builds_venv_and_passes(ctx):
    r = new_repo(ctx, "fresh")
    check(not r.venv.exists(), "fixture should start with no venv")
    rc, out = r.make("api-check")
    check(rc == 0, "exit %d, expected 0:\n%s" % (rc, out))
    check("building implementation/api/.venv" in out, "no build message:\n" + out)
    check(r.stamp.exists(), "no install stamp after a successful build")
    check(r.calls() == ["manage check", "manage makemigrations --check --noinput",
                        "pytest tests -q -rfEs"], "wrong commands or order: %r" % r.calls())
    check("3 passed" in out, "pytest result not shown:\n" + out)
    ctx["fresh"] = r


def second_run_reuses_the_venv(ctx):
    r = ctx.get("fresh") or built_repo(ctx)
    before = r.stamp.stat().st_mtime_ns
    rc, out = r.make("api-check")
    check(rc == 0, "exit %d:\n%s" % (rc, out))
    check("building" not in out, "venv was rebuilt on a second run:\n" + out)
    check(r.stamp.stat().st_mtime_ns == before, "stamp was rewritten on a second run")


def postgres_redis_skips_are_stated(ctx):
    r = built_repo(ctx)
    rc, out = r.make("api-check")
    check(rc == 0, out)
    check("Postgres or Redis" in out and "SKIP" in out, "output does not say the Postgres/Redis tests skip:\n" + out)
    check("-rfEs" in out, "pytest is not asked to print skip reasons and failures (-rfEs)")


def failing_test_goes_red(ctx):
    r = built_repo(ctx)
    (r.api / "tests" / "test_broken.py").write_text("")
    rc, out = r.make("api-check")
    check(rc != 0, "a failing test still exited 0:\n" + out)
    check("test_broken.py::test_it" in out, "the failing test is not named:\n" + out)


def missing_migration_goes_red(ctx):
    r = built_repo(ctx)
    (r.api / "MISSING_MIGRATION").write_text("")
    rc, out = r.make("api-check")
    check(rc != 0, "a missing migration still exited 0:\n" + out)
    check(not any(c.startswith("pytest") for c in r.calls()), "pytest ran after the migration check failed")
    check(any(c.startswith("manage makemigrations --check") for c in r.calls()), "makemigrations --check never ran")


def system_check_failure_goes_red(ctx):
    r = built_repo(ctx)
    (r.api / "FAIL_CHECK").write_text("")
    rc, out = r.make("api-check")
    check(rc != 0, "a failing system check still exited 0:\n" + out)
    check(r.calls() == ["manage check"], "later commands ran after the system check failed: %r" % r.calls())


def missing_pytest_fails_loudly(ctx):
    r = built_repo(ctx)
    shutil.move(str(r.api / "pytest"), str(r.api / "pytest.off"))
    try:
        rc, out = r.make("api-check")
    finally:
        shutil.move(str(r.api / "pytest.off"), str(r.api / "pytest"))
    check(rc != 0, "a missing pytest still exited 0:\n" + out)
    check("No module named pytest" in out, "the missing dependency is not reported:\n" + out)


def missing_interpreter_fails_loudly(ctx):
    r = new_repo(ctx, "nopython")
    rc, out = r.make("api-check", python="/nonexistent/python3.14")
    check(rc != 0, "no interpreter still exited 0:\n" + out)
    check("is not on PATH" in out and "API_PYTHON" in out, "the error does not name the fix:\n" + out)
    check(not r.venv.exists() and not r.stamp.exists(), "a venv or stamp was left behind")


def old_interpreter_fails_loudly(ctx):
    r = new_repo(ctx, "oldpython")
    fake = Path(ctx["tmp"]) / "oldpython3"
    # Behaves as a real interpreter that reports itself as 3.9: only the version differs, so a
    # Makefile that stops CHECKING the version goes on to build a venv instead of failing for another reason.
    fake.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  --version) echo 'Python 3.9.0' ;;\n"
        '  -c) exec %s -c "import sys; sys.version_info = (3, 9, 0, \'final\', 0)\n$2" ;;\n'
        '  *) exec %s "$@" ;;\n'
        "esac\n" % (ctx["python"], ctx["python"])
    )
    fake.chmod(0o755)
    rc, out = r.make("api-check", python=str(fake))
    check(rc != 0, "an old interpreter still exited 0:\n" + out)
    check("too old" in out and "3.9.0" in out, "the error does not say the interpreter is too old:\n" + out)
    check(not r.venv.exists() and not r.stamp.exists(), "a venv or stamp was left behind")


def failed_install_leaves_no_stamp(ctx):
    r = new_repo(ctx, "badinstall")
    (r.api / "BREAK_INSTALL").write_text("")
    rc, out = r.make("api-check")
    check(rc != 0, "a failed install still exited 0:\n" + out)
    check(not r.stamp.exists(), "a failed install left a stamp, so the next run would trust a broken venv")
    check(not any(c.startswith("pytest") for c in r.calls()), "pytest ran after a failed install")
    (r.api / "BREAK_INSTALL").unlink()
    rc, out = r.make("api-check")
    check(rc == 0, "the run after a failed install did not retry and pass:\n" + out)
    check(r.stamp.exists(), "no stamp after the retry")


def changed_pyproject_rebuilds_the_venv(ctx):
    r = built_repo(ctx)
    future = time.time() + 5
    os.utime(str(r.api / "pyproject.toml"), (future, future))
    rc, out = r.make("api-check")
    check(rc == 0, out)
    check("building implementation/api/.venv" in out, "a newer pyproject.toml did not rebuild the venv:\n" + out)
    # leave the shared fixture consistent: the stamp must now be newer than pyproject.toml again
    now = time.time()
    os.utime(str(r.api / "pyproject.toml"), (now - 10, now - 10))


def wrong_tree_venv_is_refused(ctx):
    a = built_repo(ctx)
    b = new_repo(ctx, "othertree")
    past = time.time() - 100
    os.utime(str(b.api / "pyproject.toml"), (past, past))
    os.symlink(str(a.venv), str(b.venv))  # B "has" a venv, but it was installed from A
    rc, out = b.make("api-check")
    check(rc != 0, "a venv installed from another checkout was accepted:\n" + out)
    check("not from this checkout" in out, "the wrong-tree refusal is not explained:\n" + out)
    check(b.calls() == [], "commands ran against the wrong tree: %r" % b.calls())


def ambient_database_env_is_scrubbed(ctx):
    r = built_repo(ctx)
    rc, out = r.make("api-check", env={"SQL_ENGINE": "django.db.backends.postgresql"})
    check(rc == 0, "SQL_ENGINE in the caller's environment reached the run:\n" + out)


def venv_path_cannot_be_overridden(ctx):
    r = new_repo(ctx, "override")
    elsewhere = Path(ctx["tmp"]) / "elsewhere-venv"
    rc, out = r.make("api-check", "API_VENV=%s" % elsewhere)
    check(rc == 0, out)
    check(r.stamp.exists(), "the venv was not built at implementation/api/.venv")
    check(not elsewhere.exists(), "API_VENV on the command line moved the venv (and `venv --clear` with it)")


def runs_from_another_working_directory(ctx):
    r = built_repo(ctx)
    other = Path(ctx["tmp"]) / "elsewhere-cwd"
    other.mkdir(exist_ok=True)
    rc, out = r.make("api-check", cwd=other)
    check(rc == 0, "make -C <repo> api-check failed from another cwd:\n" + out)
    check(len(r.calls()) == 3, "not all three commands ran: %r" % r.calls())


def makefile_from_wrong_directory_is_loud(ctx):
    r = built_repo(ctx)
    other = Path(ctx["tmp"]) / "elsewhere-cwd2"
    other.mkdir(exist_ok=True)
    rc, out = r.make("api-check", cwd=other, makefile=r.root / "Makefile")
    check(rc != 0, "`make -f` from a directory that is not the repo root exited 0:\n" + out)
    check(r.calls() == [], "commands ran from the wrong directory: %r" % r.calls())


def ci_target_runs_api_check(ctx):
    """Against the REAL tree, not the fixture: the wiring into `make ci`."""
    mk = Path(ctx["makefile_path"])
    before = (REPO / "implementation" / "api" / ".venv").exists()
    p = subprocess.run(["make", "-n", "-f", str(mk), "ci"], cwd=str(REPO), capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MAKELEVEL", "MFLAGS")})
    out = p.stdout + p.stderr
    check(p.returncode == 0, "make -n ci exit %d:\n%s" % (p.returncode, out[-2000:]))
    lines = [l for l in out.splitlines() if "--no-print-directory" in l]
    names = [l.split()[-1] for l in lines]
    check("api-check" in names, "make ci does not call api-check: %r" % names)
    check("marketing-check" in names and names.index("marketing-check") < names.index("api-check"),
          "api-check is not after marketing-check: %r" % names)
    check((REPO / "implementation" / "api" / ".venv").exists() == before, "make -n ci created a venv (not a dry run)")


def help_lists_api_check(ctx):
    p = subprocess.run(["make", "-f", str(ctx["makefile_path"]), "help"], cwd=str(REPO), capture_output=True,
                       text=True)
    out = p.stdout + p.stderr
    line = [l for l in out.splitlines() if "api-check" in l]
    check(p.returncode == 0 and line, "make help does not list api-check:\n" + out)
    check("SKIP" in line[0], "the help line does not say the Postgres/Redis tests skip: %r" % line[0])


CASES = [
    fresh_worktree_builds_venv_and_passes,
    second_run_reuses_the_venv,
    postgres_redis_skips_are_stated,
    failing_test_goes_red,
    missing_migration_goes_red,
    system_check_failure_goes_red,
    missing_pytest_fails_loudly,
    missing_interpreter_fails_loudly,
    old_interpreter_fails_loudly,
    failed_install_leaves_no_stamp,
    changed_pyproject_rebuilds_the_venv,
    wrong_tree_venv_is_refused,
    ambient_database_env_is_scrubbed,
    venv_path_cannot_be_overridden,
    runs_from_another_working_directory,
    makefile_from_wrong_directory_is_loud,
    ci_target_runs_api_check,
    help_lists_api_check,
]


def run_cases(makefile_path, only=None, quiet=False):
    """Returns {case name: None (pass) or failure text}."""
    python = find_python()
    results = {}
    with tempfile.TemporaryDirectory(prefix="check_api_gate_") as tmp:
        ctx = {"tmp": tmp, "python": python, "makefile_path": str(makefile_path),
               "makefile_text": Path(makefile_path).read_text()}
        for fn in CASES:
            if only and fn.__name__ not in only:
                continue
            try:
                fn(ctx)
                results[fn.__name__] = None
                if not quiet:
                    print("  ok   %s" % fn.__name__)
            except CaseFailed as e:
                results[fn.__name__] = str(e)
                if not quiet:
                    print("  FAIL %s\n%s" % (fn.__name__, textwrap.indent(str(e), "       ")))
            except Exception as e:  # a crashing case is a failing case, never a skip
                results[fn.__name__] = "crashed: %r" % (e,)
                if not quiet:
                    print("  FAIL %s: crashed: %r" % (fn.__name__, e))
    return results


# (what is broken, [(old, new) text replacements applied to the Makefile], the case that must go red).
# Each `old` must occur exactly once, so a refactor that moves the line breaks the proof loudly.
MUTATIONS = [
    ('pytest failure swallowed', [('-m pytest tests -q -rfEs', '-m pytest tests -q -rfEs || true')], 'failing_test_goes_red'),
    ('migration check removed', [('\tcd $(API) && $(API_ENV) "$(API_VPY)" manage.py makemigrations --check --noinput\n', '')], 'missing_migration_goes_red'),
    ('system check removed', [('\tcd $(API) && $(API_ENV) "$(API_VPY)" manage.py check\n', '')], 'system_check_failure_goes_red'),
    ('environment scrub removed', [('API_ENV    := env -i PATH="$$PATH" HOME="$$HOME" TMPDIR="$$TMPDIR" LANG="$$LANG" LC_ALL="$$LC_ALL"', 'API_ENV    :=')], 'ambient_database_env_is_scrubbed'),
    ('stamp written before the install', [('\tcd $(API) && "$(API_VPY)" -m pip install --disable-pip-version-check --quiet -e ".[dev]"\n\ttouch $@\n', '\ttouch $@\n\tcd $(API) && "$(API_VPY)" -m pip install --disable-pip-version-check --quiet -e ".[dev]"\n')], 'failed_install_leaves_no_stamp'),
    ('pyproject prerequisite removed', [('$(API_STAMP): $(API)/pyproject.toml', '$(API_STAMP):')], 'changed_pyproject_rebuilds_the_venv'),
    ('wrong-tree assertion neutered', [('assert root in p.parents', 'assert 1')], 'wrong_tree_venv_is_refused'),
    ('interpreter version check removed', [("sys.exit(0 if sys.version_info >= (3, 12) else 1)' || {", "sys.exit(0)' || {")], 'old_interpreter_fails_loudly'),
    ('interpreter presence check removed', [('@command -v $(API_PYTHON) >/dev/null 2>&1 || {', '@true || {')], 'missing_interpreter_fails_loudly'),
    ('override removed', [('override API_VENV := $(API)/.venv', 'API_VENV := $(API)/.venv')], 'venv_path_cannot_be_overridden'),
    ('skip statement removed', [('Tests that need Postgres or Redis', 'Some tests')], 'postgres_redis_skips_are_stated'),
    ('api-check dropped from ci', [('\t$(MAKE_RECURSE) --no-print-directory api-check\n', '')], 'ci_target_runs_api_check'),
    ('skip text dropped from help', [('(the Postgres/Redis-only tests SKIP here; CI runs them)', '')], 'help_lists_api_check'),
    ('CURDIR dropped (cwd-relative venv python)', [('API_VPY    := $(CURDIR)/$(API_VENV)/bin/python', 'API_VPY    := $(API_VENV)/bin/python')], 'runs_from_another_working_directory'),
    ('stamp never written (every run rebuilds)', [('\ttouch $@\n\napi-check', '\ttrue\n\napi-check')], 'fresh_worktree_builds_venv_and_passes'),
    (
        "Makefile resolves its own directory instead of the cwd",
        [
            ("API        := implementation/api", "API        := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))/implementation/api"),
            ("API_VPY    := $(CURDIR)/$(API_VENV)/bin/python", "API_VPY    := $(API_VENV)/bin/python"),
        ],
        "makefile_from_wrong_directory_is_loud",
    ),
]


def mutation_proof():
    original = MAKEFILE.read_text()
    failures = []
    with tempfile.TemporaryDirectory(prefix="check_api_gate_mut_") as tmp:
        print("baseline (unmutated Makefile):")
        base = run_cases(MAKEFILE, quiet=True)
        bad = [n for n, r in base.items() if r]
        if bad:
            sys.exit("baseline is not green, so a mutation result would mean nothing: %s" % bad)
        print("  all %d cases green" % len(base))
        for label, pairs, case in MUTATIONS:
            text = original
            broken = [o for o, _ in pairs if text.count(o) != 1]
            if broken:
                failures.append("%s: the text to mutate does not occur exactly once: %r" % (label, broken[0][:60]))
                print("  BROKEN PROOF %s" % label)
                continue
            for o, n in pairs:
                text = text.replace(o, n)
            mutated = Path(tmp) / "Makefile.mutated"
            mutated.write_text(text)
            res = run_cases(mutated, only=[case], quiet=True)
            if res.get(case) is None:
                failures.append("%s: case %s stayed GREEN with the behaviour removed" % (label, case))
                print("  NOT CAUGHT   %-45s -> %s" % (label, case))
            else:
                print("  caught       %-45s -> %s" % (label, case))
    if failures:
        print("\nMUTATION PROOF FAILED:\n  " + "\n  ".join(failures))
        return 1
    print("\nmutation proof: every mutation was caught (%d)" % len(MUTATIONS))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true", help="run every case against the Makefile")
    ap.add_argument("--only", action="append", help="run only this case (repeatable)")
    ap.add_argument("--mutation-proof", action="store_true", help="break the Makefile on purpose; each case must go red")
    ap.add_argument("--makefile", default=str(MAKEFILE), help="Makefile under test (default: the repo's)")
    args = ap.parse_args()
    if args.mutation_proof:
        return mutation_proof()
    if not args.self_test and not args.only:
        ap.error("pass --self-test or --mutation-proof")
    res = run_cases(args.makefile, only=args.only)
    failed = [n for n, r in res.items() if r]
    print("check_api_gate: %d cases, %d failed" % (len(res), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
