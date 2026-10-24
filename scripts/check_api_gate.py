#!/usr/bin/env python3
"""Self-test for `make api-install` / `make api-check` and scripts/api_venv.py (ClickUp 86ak5rjh7, API half).

`make ci` runs the Django API gate through `make api-check`. A gate that cannot go red, or that quietly
skips, or that installs packages by surprise, is worse than no gate, so this script tests the TARGETS'
LOGIC, not the API's tests: it copies the real Makefile and the real helper into a scratch repo that holds
a tiny fake `implementation/api` (a stand-in `manage.py`, a stand-in `pytest` package, and an in-tree
PEP 660 build backend, so nothing is downloaded) and runs the targets there under each situation they
have to handle. One case, `ci_yml_commands_match_makefile`, also reads the REAL .github/workflows/ci.yml.

Why a fake API and not the real one: the real suite takes minutes and the install needs the network. What
matters here is whether the targets refuse, build, reuse, rebuild, propagate a failing exit code and
refuse to skip. The REAL suite is exercised by `make ci` itself.

Each case is a function whose first docstring line says what it pins; `--list` prints them, `--only NAME`
runs one (an unknown name is an error), and the script fails if no case ran or the count is wrong.

`--mutation-proof` breaks the Makefile and the helper on purpose, one thing at a time, and requires the
named case to go red for each. Run it after any edit to the api targets or scripts/api_venv.py: a case
that stays green when the behaviour it names is removed guards nothing. It prints the counts it measured.

Needs Python >= 3.12 to build the scratch venvs (CI pins 3.14): `API_PYTHON` or the same `python3.14` the
Makefile defaults to. Not found is an error, never a skip. The script itself is 3.9-compatible because
`make ci` runs it with the system `python3`.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"
HELPER = REPO / "scripts" / "api_venv.py"
CI_YML = REPO / ".github" / "workflows" / "ci.yml"

VENV_NAME = ".venv-api-check"
STAMP_NAME = ".selahcue-api-installed"
MARKER_NAME = ".selahcue-api-check-venv"

# Variables that must never reach the test commands, whatever the caller exported.
LEAKY = ["SQL_ENGINE", "SQL_HOST", "CACHE_URL", "CELERY_BROKER_URL", "SECRET_KEY", "PYTHONPATH"]

# Differences between the Makefile's commands and the CI job's that are known and intended:
# `-rfEs` makes pytest print skip reasons and failures by name. (The psycopg install and the Postgres
# environment variables are other `run:`/`env:` content of the CI job, which this comparison ignores.)
ALLOWED_MAKEFILE_EXTRA = ["-rfEs"]

BACKEND = textwrap.dedent(
    '''\
    """In-tree PEP 660 backend: an editable install with no network and no setuptools."""
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
            name + ".dist-info/METADATA": "Metadata-Version: 2.1\\nName: selahcue-api\\nVersion: 0.0.0\\nProvides-Extra: dev\\nRequires-Dist: extradep; extra == 'dev'\\n",
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

# A local wheel that the fake API's `dev` extra requires. pip finds it through PIP_FIND_LINKS with PIP_NO_INDEX,
# so nothing is downloaded, and the fakes fail if it is missing: that is how a dropped `[dev]` shows up.
EXTRA_DEP = "extradep"


def build_wheelhouse(directory):
    import zipfile
    directory.mkdir(parents=True, exist_ok=True)
    name = "%s-1.0" % EXTRA_DEP
    files = {
        "%s.py" % EXTRA_DEP: "",
        name + ".dist-info/METADATA": "Metadata-Version: 2.1\nName: %s\nVersion: 1.0\n" % EXTRA_DEP,
        name + ".dist-info/WHEEL": "Wheel-Version: 1.0\nGenerator: fake\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    with zipfile.ZipFile(str(directory / (name + "-py3-none-any.whl")), "w") as z:
        for path, body in files.items():
            z.writestr(path, body)
        z.writestr(name + ".dist-info/RECORD", "".join("%s,,\n" % p for p in files) + name + ".dist-info/RECORD,,\n")


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
    dev = ["extradep"]
    """
)

# Both fakes log "<tool> <args> prefix=<sys.prefix>" (so a case can prove the venv's interpreter ran them)
# and fail if the caller's environment leaked in or SQL_DATABASE is not the in-memory database.
GUARD = textwrap.dedent(
    """\
    import os
    import sys

    with open("calls.log", "a") as f:
        f.write("TOOL " + " ".join(sys.argv[1:]) + " prefix=" + sys.prefix + "\\n")
    leaked = [k for k in %r if k in os.environ]
    if leaked:
        print("FAILED env leak: " + ",".join(leaked))
        sys.exit(1)
    try:
        import extradep  # noqa: F401
    except ImportError:
        print("FAILED the dev extra was not installed (extradep missing)")
        sys.exit(1)
    if os.environ.get("SQL_DATABASE") != ":memory:":
        print("FAILED SQL_DATABASE is %%r, not ':memory:'" %% os.environ.get("SQL_DATABASE"))
        sys.exit(1)
    """
) % (LEAKY,)

MANAGE = GUARD.replace("TOOL", "manage") + textwrap.dedent(
    """\
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

FAKE_PYTEST = GUARD.replace("TOOL", "pytest") + textwrap.dedent(
    """\
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
    """The interpreter the scratch venvs are built from: API_PYTHON, else python3.14/13/12 on PATH."""
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
             "cannot build the scratch venvs. This is an error, not a skip -- `make api-install` needs it too.")


def fake_interpreter(real, path, version_tuple):
    """A script that behaves as the real interpreter but reports itself as `version_tuple`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    banner = "Python %d.%d.%d" % version_tuple
    path.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  --version) echo '%s' ;;\n"
        '  -c) exec "%s" -c "import sys; sys.version_info = (%d, %d, %d, \'final\', 0)\n$2" ;;\n'
        '  *) exec "%s" "$@" ;;\n'
        "esac\n" % (banner, real, version_tuple[0], version_tuple[1], version_tuple[2], real)
    )
    path.chmod(0o755)
    return str(path)


class Repo:
    """A scratch repo root: the Makefile and helper under test plus a fake implementation/api."""

    def __init__(self, parent, makefile_text, helper_text, python, name, wheelhouse):
        self.root = Path(parent) / name
        self.wheelhouse = wheelhouse
        self.api = self.root / "implementation" / "api"
        self.python = python
        (self.api / "selahcue_api").mkdir(parents=True)
        (self.api / "tests").mkdir()
        (self.api / "pytest").mkdir()
        (self.root / "scripts").mkdir()
        (self.root / "Makefile").write_text(makefile_text)
        (self.root / "scripts" / "api_venv.py").write_text(helper_text)
        self.pyproject = self.api / "pyproject.toml"
        self.pyproject.write_text(PYPROJECT)
        (self.api / "fakebackend.py").write_text(BACKEND)
        (self.api / "manage.py").write_text(MANAGE)
        (self.api / "selahcue_api" / "__init__.py").write_text("")
        (self.api / "pytest" / "__init__.py").write_text("")
        (self.api / "pytest" / "__main__.py").write_text(FAKE_PYTEST)
        (self.api / "tests" / "test_ok.py").write_text("")
        self.venv = self.api / VENV_NAME
        self.stamp = self.venv / STAMP_NAME
        self.marker = self.venv / MARKER_NAME

    def log_lines(self):
        log = self.api / "calls.log"
        return log.read_text().splitlines() if log.exists() else []

    def calls(self):
        return [l.rsplit(" prefix=", 1)[0] for l in self.log_lines()]

    def prefixes(self):
        return set(os.path.realpath(l.rsplit(" prefix=", 1)[1]) for l in self.log_lines())

    def reset(self):
        for f in ("FAIL_CHECK", "MISSING_MIGRATION", "BREAK_INSTALL", "calls.log"):
            (self.api / f).unlink(missing_ok=True)
        (self.api / "tests" / "test_broken.py").unlink(missing_ok=True)

    def make(self, *args, python=None, env=None, cwd=None, makefile=None, timeout=600):
        """`python=None` passes this fixture's interpreter, `python=False` passes none at all."""
        e = dict(os.environ)
        for k in ["API_PYTHON", "MAKEFLAGS", "MAKELEVEL", "MFLAGS", "SQL_DATABASE"] + LEAKY:
            e.pop(k, None)
        e["PIP_NO_INDEX"] = "1"  # pip install runs with the developer's environment: here, offline
        e["PIP_FIND_LINKS"] = str(self.wheelhouse)
        e.update(env or {})
        cmd = ["make"]
        cmd += ["-f", str(makefile)] if makefile else ["-C", str(self.root)]
        cmd += list(args)
        if python is not False:
            cmd.append("API_PYTHON=%s" % (self.python if python is None else python))
        p = subprocess.run(cmd, cwd=str(cwd or self.root), env=e, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr

    def install(self, **kw):
        return self.make("api-install", **kw)

    def check_gate(self, **kw):
        return self.make("api-check", **kw)


def new_repo(ctx, name):
    return Repo(ctx["tmp"], ctx["makefile_text"], ctx["helper_text"], ctx["python"], name, ctx["wheelhouse"])


def installed_repo(ctx, name):
    r = new_repo(ctx, name)
    rc, out = r.install()
    check(rc == 0, "could not install the fixture venv:\n" + out)
    return r


def shared_repo(ctx):
    """The shared repo with a venv installed (installed on first use), reset to a clean state."""
    r = ctx.get("shared")
    if r is None:
        r = ctx["shared"] = installed_repo(ctx, "shared")
    r.reset()
    return r


# --- success shapes ------------------------------------------------------------------------------------


def api_check_refuses_without_a_venv(ctx):
    """api-check on a fresh worktree refuses, names `make api-install`, installs nothing, runs nothing."""
    r = new_repo(ctx, "norvenv")
    rc, out = r.check_gate()
    check(rc != 0, "api-check passed with no venv:\n" + out)
    check("make api-install" in out, "the refusal does not name `make api-install`:\n" + out)
    check(not r.venv.exists(), "api-check created a venv (it must never install)")
    check(r.calls() == [], "commands ran with no venv: %r" % r.calls())


def install_then_check_passes(ctx):
    """Fresh worktree: api-install builds the venv, then api-check runs the three commands, in the venv."""
    r = new_repo(ctx, "fresh")
    rc, out = r.install()
    check(rc == 0, "api-install exit %d:\n%s" % (rc, out))
    check(r.stamp.exists() and r.marker.exists(), "no stamp or marker after a successful install")
    rc, out = r.check_gate()
    check(rc == 0, "api-check exit %d:\n%s" % (rc, out))
    check(r.calls() == ["manage check", "manage makemigrations --check --noinput", "pytest tests -q -rfEs"],
          "wrong commands or order: %r" % r.calls())
    check(r.prefixes() == {os.path.realpath(str(r.venv))},
          "the commands did not run under the venv's interpreter: %r" % r.prefixes())
    check("3 passed" in out, "pytest result not shown:\n" + out)
    check("Python 3." in out, "the venv's Python version is not printed:\n" + out)


def second_check_reuses_the_venv(ctx):
    """A second api-check neither rebuilds nor touches the venv."""
    r = shared_repo(ctx)
    before = (r.stamp.stat().st_mtime_ns, r.marker.stat().st_mtime_ns)
    for _ in range(2):
        rc, out = r.check_gate()
        check(rc == 0, "exit %d:\n%s" % (rc, out))
        check("building" not in out, "the venv was rebuilt by api-check:\n" + out)
    check((r.stamp.stat().st_mtime_ns, r.marker.stat().st_mtime_ns) == before, "api-check rewrote the venv's files")


def api_install_rebuilds_cleanly(ctx):
    """A second api-install clears the old venv (a leftover package is gone) and the result still passes."""
    r = installed_repo(ctx, "rebuild")
    leftover = r.venv / "leftover-package.txt"
    leftover.write_text("x")
    rc, out = r.install()
    check(rc == 0, out)
    check(not leftover.exists(), "a rebuild kept a leftover from the old venv (--clear dropped?)")
    rc, out = r.check_gate()
    check(rc == 0, out)


def api_check_output_states_the_skips(ctx):
    """The output says the Postgres/Redis-only tests skip locally, and asks pytest for reasons and failures."""
    r = shared_repo(ctx)
    rc, out = r.check_gate()
    check(rc == 0, out)
    check("Postgres or Redis" in out and "SKIP" in out, "output does not say the Postgres/Redis tests skip:\n" + out)
    check("-rfEs" in out, "pytest is not asked to print skip reasons and failures (-rfEs)")


def default_interpreter_is_python3_14(ctx):
    """With no API_PYTHON given, api-install looks for `python3.14` on PATH (the default reaches the helper)."""
    r = new_repo(ctx, "defaultpy")
    shim = Path(ctx["tmp"]) / "shim-bin"
    shim.mkdir(exist_ok=True)
    link = shim / "python3.14"
    if not link.exists():
        link.symlink_to(ctx["python"])
        fake_interpreter(ctx["python"], shim / "python3", (3, 9, 0))  # a default of plain `python3` would pick this
    rc, out = r.install(python=False, env={"PATH": "%s%s%s" % (shim, os.pathsep, os.environ["PATH"])})
    check(rc == 0, "api-install did not find python3.14 by default:\n" + out)


# --- going red -----------------------------------------------------------------------------------------


def failing_test_goes_red(ctx):
    """A failing test: non-zero, the test is named."""
    r = shared_repo(ctx)
    (r.api / "tests" / "test_broken.py").write_text("")
    rc, out = r.check_gate()
    check(rc != 0, "a failing test still exited 0:\n" + out)
    check("test_broken.py::test_it" in out, "the failing test is not named:\n" + out)


def missing_migration_goes_red(ctx):
    """A model without a migration: non-zero, and pytest is not reached."""
    r = shared_repo(ctx)
    (r.api / "MISSING_MIGRATION").write_text("")
    rc, out = r.check_gate()
    check(rc != 0, "a missing migration still exited 0:\n" + out)
    check(not any(c.startswith("pytest") for c in r.calls()), "pytest ran after the migration check failed")
    check(any(c.startswith("manage makemigrations --check") for c in r.calls()), "makemigrations --check never ran")


def system_check_failure_goes_red(ctx):
    """A failing `manage.py check`: non-zero, the later commands do not run."""
    r = shared_repo(ctx)
    (r.api / "FAIL_CHECK").write_text("")
    rc, out = r.check_gate()
    check(rc != 0, "a failing system check still exited 0:\n" + out)
    check(r.calls() == ["manage check"], "later commands ran after the system check failed: %r" % r.calls())


def missing_pytest_fails_loudly(ctx):
    """A dependency absent from the venv is an error, never a skip."""
    r = shared_repo(ctx)
    shutil.move(str(r.api / "pytest"), str(r.api / "pytest.off"))
    try:
        rc, out = r.check_gate()
    finally:
        shutil.move(str(r.api / "pytest.off"), str(r.api / "pytest"))
    check(rc != 0, "a missing pytest still exited 0:\n" + out)
    check("No module named pytest" in out, "the missing dependency is not reported:\n" + out)


# --- refusing a venv that is not trustworthy -----------------------------------------------------------


def changed_pyproject_is_refused(ctx):
    """pyproject.toml changed since the install: api-check refuses and names api-install; nothing runs."""
    r = shared_repo(ctx)
    original = r.pyproject.read_text()
    try:
        r.pyproject.write_text(original + "\n# a dependency pin changed\n")
        rc, out = r.check_gate()
    finally:
        r.pyproject.write_text(original)
    check(rc != 0, "a changed pyproject.toml was accepted:\n" + out)
    check("make api-install" in out and "pyproject.toml changed" in out, "the refusal is not actionable:\n" + out)
    check(r.calls() == [], "commands ran against a stale venv: %r" % r.calls())


def touching_pyproject_does_not_refuse(ctx):
    """A content-neutral `touch` of pyproject.toml is not a refusal (the stamp holds a hash, not a time)."""
    r = shared_repo(ctx)
    future = time.time() + 30
    os.utime(str(r.pyproject), (future, future))
    rc, out = r.check_gate()
    check(rc == 0, "a touch alone caused a refusal:\n" + out)
    os.utime(str(r.pyproject), (time.time() - 10, time.time() - 10))


def interpreter_changed_in_place_is_refused(ctx):
    """The venv's interpreter no longer matches the one it was built with: refused."""
    r = shared_repo(ctx)
    original = r.stamp.read_text()
    try:
        r.stamp.write_text(original.replace('"python": "', '"python": "9.'))
        rc, out = r.check_gate()
    finally:
        r.stamp.write_text(original)
    check(rc != 0, "a changed interpreter was accepted:\n" + out)
    check("interpreter changed" in out and "make api-install" in out, "the refusal is not actionable:\n" + out)
    check(r.calls() == [], "commands ran: %r" % r.calls())


def api_python_of_another_version_is_refused(ctx):
    """API_PYTHON names a different Python minor than the venv was built with: refused."""
    r = shared_repo(ctx)
    other = fake_interpreter(ctx["python"], Path(ctx["tmp"]) / "py399" / "python3", (3, 99, 0))
    rc, out = r.check_gate(python=other)
    check(rc != 0, "a venv built with another Python was accepted:\n" + out)
    check("API_PYTHON" in out and "make api-install" in out, "the refusal is not actionable:\n" + out)
    check(r.calls() == [], "commands ran: %r" % r.calls())


def incomplete_install_is_refused(ctx):
    """A venv with no stamp (an interrupted install) is refused, not trusted."""
    r = installed_repo(ctx, "nostamp")
    r.stamp.unlink()
    rc, out = r.check_gate()
    check(rc != 0, "a venv with no stamp was accepted:\n" + out)
    check("make api-install" in out, out)
    check(r.calls() == [], "commands ran: %r" % r.calls())


def wrong_tree_venv_is_refused(ctx):
    """A venv installed from another checkout (a copy of its directory) is refused and explained."""
    a = shared_repo(ctx)
    b = new_repo(ctx, "othertree")
    shutil.copytree(str(a.venv), str(b.venv), symlinks=True)
    rc, out = b.check_gate()
    check(rc != 0, "a venv installed from another checkout was accepted:\n" + out)
    check("another checkout" in out, "the wrong-tree refusal is not explained:\n" + out)
    check(b.calls() == [], "commands ran against the wrong tree: %r" % b.calls())


def symlinked_venv_is_refused(ctx):
    """A symlink at the venv path is refused by both targets, even when its stamp is older than pyproject."""
    a = shared_repo(ctx)
    b = new_repo(ctx, "linked")
    future = time.time() + 100
    os.utime(str(b.pyproject), (future, future))  # the linked stamp is OLDER than pyproject.toml
    os.symlink(str(a.venv), str(b.venv))
    stamp_before = a.stamp.stat().st_mtime_ns
    rc, out = b.check_gate()
    check(rc != 0 and "symlink" in out, "api-check accepted a symlinked venv:\n" + out)
    rc, out = b.install()
    check(rc != 0 and "symlink" in out, "api-install rebuilt through a symlink:\n" + out)
    check(a.stamp.exists() and a.stamp.stat().st_mtime_ns == stamp_before, "the linked-to venv was modified")
    check(b.calls() == [], "commands ran: %r" % b.calls())


def foreign_directory_is_never_cleared(ctx):
    """A directory at the venv path without our marker is refused, never wiped; a developer's own .venv is untouched."""
    r = new_repo(ctx, "foreign")
    r.venv.mkdir()
    (r.venv / "keep.txt").write_text("a developer's file")
    rc, out = r.install()
    check(rc != 0, "api-install cleared a directory it did not create:\n" + out)
    check((r.venv / "keep.txt").exists(), "api-install deleted a foreign file")
    check("not created by" in out, "the refusal does not say why:\n" + out)
    own = new_repo(ctx, "owndotvenv")
    (own.api / ".venv").mkdir()
    (own.api / ".venv" / "keep.txt").write_text("my venv")
    rc, out = own.install()
    check(rc == 0, out)
    check((own.api / ".venv" / "keep.txt").exists(), "a developer's own .venv was touched by api-install")


def concurrent_install_is_refused(ctx):
    """While another api-install holds the lock, a second one refuses and leaves the venv alone."""
    r = installed_repo(ctx, "locked")
    lock = Path(str(r.venv) + ".lock")
    lock.mkdir()
    before = r.stamp.stat().st_mtime_ns
    rc, out = r.install()
    check(rc != 0 and "another" in out, "a second install ran while the lock was held:\n" + out)
    check(r.stamp.exists() and r.stamp.stat().st_mtime_ns == before, "the venv was modified under the lock")


# --- failed installs and bad interpreters --------------------------------------------------------------


def failed_install_leaves_no_stamp_and_retries(ctx):
    """A failed install: non-zero, no stamp, api-check will not trust it; the next api-install retries."""
    r = new_repo(ctx, "badinstall")
    (r.api / "BREAK_INSTALL").write_text("")
    rc, out = r.install()
    check(rc != 0, "a failed install still exited 0:\n" + out)
    check(not r.stamp.exists(), "a failed install left a stamp")
    rc, out = r.check_gate()
    check(rc != 0 and "make api-install" in out, "api-check trusted a half-built venv:\n" + out)
    (r.api / "BREAK_INSTALL").unlink()
    rc, out = r.install()
    check(rc == 0, "the install after a failed one did not retry and pass:\n" + out)
    rc, out = r.check_gate()
    check(rc == 0, out)


def failed_rebuild_from_a_good_venv_is_not_trusted(ctx):
    """A failed rebuild over a working venv leaves it untrusted (no stale stamp), until a rebuild succeeds."""
    r = installed_repo(ctx, "badrebuild")
    (r.api / "BREAK_INSTALL").write_text("")
    rc, out = r.install()
    check(rc != 0, out)
    check(not r.stamp.exists(), "the old stamp survived a failed rebuild")
    rc, out = r.check_gate()
    check(rc != 0, "api-check trusted a venv whose rebuild failed:\n" + out)
    (r.api / "BREAK_INSTALL").unlink()
    rc, out = r.install()
    check(rc == 0, out)
    rc, out = r.check_gate()
    check(rc == 0, out)


def missing_interpreter_fails_loudly(ctx):
    """No usable interpreter: non-zero, fix named, no venv."""
    r = new_repo(ctx, "nopython")
    rc, out = r.install(python="/nonexistent/python3.14")
    check(rc != 0, "no interpreter still exited 0:\n" + out)
    check("is not on PATH" in out and "API_PYTHON" in out, "the error does not name the fix:\n" + out)
    check(not r.venv.exists(), "a venv was left behind")


def empty_interpreter_fails_loudly(ctx):
    """An empty API_PYTHON: non-zero with its own message, no venv."""
    r = new_repo(ctx, "emptypython")
    rc, out = r.install(python="")
    check(rc != 0 and "API_PYTHON is empty" in out, "an empty API_PYTHON was not reported:\n" + out)
    check(not r.venv.exists(), "a venv was left behind")


def blank_interpreter_never_refreshes_a_stale_venv(ctx):
    """Empty and whitespace-only API_PYTHON fail loudly and leave a stale venv stale (no false green)."""
    r = installed_repo(ctx, "blank")
    original = r.pyproject.read_text()
    r.pyproject.write_text(original + "\n# pin changed\n")
    stamp_before = r.stamp.read_text(), r.stamp.stat().st_mtime_ns
    # `API_PYTHON=` on the command line reaches the helper empty (Make strips the blanks); whitespace-only
    # can only arrive through the environment, so both routes are exercised.
    routes = (("API_PYTHON= on the command line", {"python": ""}),
              ("API_PYTHON='   ' in the environment", {"python": False, "env": {"API_PYTHON": "   "}}))
    for label, kw in routes:
        rc, out = r.install(**kw)
        check(rc != 0 and "API_PYTHON is empty" in out, "%s was not rejected as empty:\n%s" % (label, out))
        check((r.stamp.read_text(), r.stamp.stat().st_mtime_ns) == stamp_before, "%s refreshed the stamp" % label)
        rc, out = r.check_gate(**kw)
        check(rc != 0 and "make api-install" in out, "the stale venv passed with %s:\n%s" % (label, out))
        check(r.calls() == [], "commands ran against a stale venv: %r" % r.calls())


def api_recipes_do_not_start_with_a_user_variable(ctx):
    """No recipe line of the api targets starts with an expansion the user sets: an empty value would become `-c ...`."""
    in_api, bad = False, []
    for line in ctx["makefile_text"].splitlines():
        if re.match(r"^api-(install|check):", line):
            in_api = True
            continue
        if in_api and not line.startswith("\t"):
            in_api = False
        if in_api and re.match(r"^\t[@+-]*\$\((API_PYTHON)\)", line):
            bad.append(line)
    check(not bad, "recipe lines start with a user-settable variable (empty would run `-c`, and `-` ignores errors): %r" % bad)


def broken_venv_is_refused_with_the_fix(ctx):
    """A venv whose interpreter is gone or dangling: refused naming `make api-install`, never a raw sh error."""
    for name, make_dangling in (("gone", False), ("dangling", True)):
        r = installed_repo(ctx, "broken-" + name)
        py = r.venv / "bin" / "python"
        py.unlink()
        if make_dangling:
            os.symlink(str(Path(ctx["tmp"]) / "nowhere" / "python"), str(py))
        rc, out = r.check_gate()
        check(rc != 0, "a venv with %s interpreter was accepted:\n%s" % (name, out))
        check("make api-install" in out, "the refusal for a %s interpreter does not name the fix:\n%s" % (name, out))
        check("Error 127" not in out and "No such file" not in out and "Traceback" not in out,
              "a raw error instead of a refusal for a %s interpreter:\n%s" % (name, out))
        check(r.calls() == [], "commands ran: %r" % r.calls())


def old_interpreter_fails_loudly(ctx):
    """Python below 3.12: non-zero, fix named, no venv."""
    r = new_repo(ctx, "oldpython")
    old = fake_interpreter(ctx["python"], Path(ctx["tmp"]) / "py39" / "python3", (3, 9, 0))
    rc, out = r.install(python=old)
    check(rc != 0, "an old interpreter still exited 0:\n" + out)
    check("too old" in out and "3.9.0" in out, "the error does not say the interpreter is too old:\n" + out)
    check(not r.venv.exists(), "a venv was left behind")


def interpreter_path_with_spaces_works(ctx):
    """An interpreter path containing spaces is data: it works."""
    r = new_repo(ctx, "spaces")
    spaced = fake_interpreter(ctx["python"], Path(ctx["tmp"]) / "dir with spaces" / "python3", (3, 14, 0))
    rc, out = r.install(python=spaced)
    check(rc == 0, "an interpreter path with spaces failed:\n" + out)


def shell_metacharacters_in_interpreter_are_not_run(ctx):
    """API_PYTHON='x; touch PWNED' fails loudly and runs nothing."""
    r = new_repo(ctx, "metachar")
    rc, out = r.install(python="x; touch PWNED")
    check(rc != 0, "a hostile API_PYTHON still exited 0:\n" + out)
    check(not any(p.exists() for p in (r.root / "PWNED", r.api / "PWNED", Path(ctx["tmp"]) / "PWNED")),
          "shell metacharacters in API_PYTHON were executed")


# --- environment and variables -------------------------------------------------------------------------


def ambient_environment_is_scrubbed(ctx):
    """The caller's SQL_ENGINE/CACHE_URL/SECRET_KEY/PYTHONPATH/... never reach the commands; the DB is in memory."""
    r = shared_repo(ctx)
    env = dict((k, "leak-" + k) for k in LEAKY)
    env["SQL_DATABASE"] = "/some/developer/db.sqlite3"
    rc, out = r.check_gate(env=env)
    check(rc == 0, "the caller's environment reached the run (or SQL_DATABASE was not :memory:):\n" + out)


def makefile_variables_cannot_be_overridden(ctx):
    """API, API_VPY, API_ENV, API_VENV, API_HELPER on the command line change nothing, for both targets."""
    r = shared_repo(ctx)
    decoy = Path(ctx["tmp"]) / "decoy"
    decoy.mkdir(exist_ok=True)
    (decoy / "pyproject.toml").write_text(PYPROJECT)
    overrides = ["API=%s" % decoy, "API_VPY=/usr/bin/true", "API_ENV=", "API_VENV=%s/v" % decoy, "API_HELPER=true"]
    rc, out = r.make("api-check", *overrides)
    check(rc == 0, "api-check with overrides failed:\n" + out)
    check(len(r.calls()) >= 3 and r.prefixes() == {os.path.realpath(str(r.venv))},
          "an override changed what ran: %r %r" % (r.calls(), r.prefixes()))
    fresh = new_repo(ctx, "overrides")
    rc, out = fresh.make("api-install", *overrides)
    check(rc == 0, out)
    check(fresh.stamp.exists(), "api-install did not build at implementation/api/%s" % VENV_NAME)
    check(not (decoy / VENV_NAME).exists() and not (decoy / "v").exists(), "an override moved the venv")


# --- where it runs, and how it is wired ----------------------------------------------------------------


def runs_from_another_working_directory(ctx):
    """`make -C <repo> api-check` from an unrelated cwd works."""
    r = shared_repo(ctx)
    other = Path(ctx["tmp"]) / "elsewhere-cwd"
    other.mkdir(exist_ok=True)
    rc, out = r.check_gate(cwd=other)
    check(rc == 0, "make -C <repo> api-check failed from another cwd:\n" + out)
    check(len(r.calls()) == 3, "not all three commands ran: %r" % r.calls())


def wrong_directory_never_passes_silently(ctx):
    """`make -f <repo>/Makefile` from another cwd either runs all three commands or fails having run none."""
    r = shared_repo(ctx)
    other = Path(ctx["tmp"]) / "elsewhere-cwd2"
    other.mkdir(exist_ok=True)
    rc, out = r.check_gate(cwd=other, makefile=r.root / "Makefile")
    ran = len(r.calls())
    check((rc == 0 and ran == 3) or (rc != 0 and ran == 0),
          "from the wrong directory: exit %d with %d commands run (a silent or partial pass):\n%s" % (rc, ran, out))


def make_env():
    return {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MAKELEVEL", "MFLAGS")}


def ci_target_includes_api_check(ctx):
    """Against the REAL tree: `make -n ci` exits 0, includes api-check and this self-test, never api-install."""
    venv = REPO / "implementation" / "api" / VENV_NAME
    before = venv.exists()
    p = subprocess.run(["make", "-n", "-f", ctx["makefile_path"], "ci"], cwd=str(REPO), capture_output=True,
                       text=True, env=make_env())
    out = p.stdout + p.stderr
    check(p.returncode == 0, "make -n ci exit %d:\n%s" % (p.returncode, out[-2000:]))
    names = [l.split()[-1] for l in out.splitlines() if "--no-print-directory" in l]
    check("api-check" in names, "make ci does not call api-check: %r" % names)
    check("api-install" not in names, "make ci calls api-install: it must never install")
    check("scripts/check_api_gate.py --self-test" in out, "make ci does not run this self-test")
    check(venv.exists() == before, "make -n ci created the venv (not a dry run)")


def help_descriptions(out):
    """{target: description} from `make help` output (ANSI colour codes stripped)."""
    found = {}
    for line in re.sub(r"\x1b\[[0-9;]*m", "", out).splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            found[parts[0]] = parts[1]
    return found


def help_lists_the_api_targets(ctx):
    """`make help` lists api-install and api-check, says the Postgres/Redis tests skip, and the ci line lists limits."""
    p = subprocess.run(["make", "-f", ctx["makefile_path"], "help"], cwd=str(REPO), capture_output=True, text=True,
                       env=make_env())
    check(p.returncode == 0, p.stdout + p.stderr)
    h = help_descriptions(p.stdout)
    check("SKIP" in h.get("api-check", "") and "api-install" in h.get("api-check", ""),
          "api-check help line lacks the skip or the install hint: %r" % h.get("api-check"))
    check("network" in h.get("api-install", ""), "api-install help line is missing or lacks the network: %r" % h.get("api-install"))
    check("NOT covered" in h.get("ci", ""), "the ci help line does not list what it does not cover: %r" % h.get("ci"))


def api_commands_from_ci(text):
    """The `python manage.py ...` / `python -m pytest ...` run: lines of ci.yml's `api` job, in order."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.rstrip() == "  api:"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^  \S", lines[i])), len(lines))
    cmds = []
    for l in lines[start:end]:
        m = re.match(r"^\s*run:\s*python (manage\.py .+|-m pytest .+)$", l)
        if m:
            cmds.append(m.group(1).strip())
    return cmds


def api_commands_from_makefile(text):
    cmds = []
    for l in text.splitlines():
        m = re.match(r'^\tcd \$\(API\) && \$\(API_ENV\) "\$\(API_VPY\)" (manage\.py .+|-m pytest .+)$', l)
        if m:
            c = m.group(1)
            for extra in ALLOWED_MAKEFILE_EXTRA:
                c = c.replace(" " + extra, "")
            cmds.append(c.strip())
    return cmds


def ci_yml_commands_match_makefile(ctx):
    """The three commands in the Makefile and in ci.yml's `api` job are the same, in the same order."""
    ci = api_commands_from_ci(CI_YML.read_text())
    mk = api_commands_from_makefile(ctx["makefile_text"])
    check(ci, "found no `python manage.py`/`python -m pytest` run: lines in ci.yml's api job -- did the job move?")
    check(len(mk) == 3, "the Makefile does not have exactly three API commands: %r" % mk)
    check(ci == mk, "the Makefile and ci.yml's api job disagree:\n  Makefile: %r\n  ci.yml:   %r" % (mk, ci))
    # Positive control: the comparison must see a doctored ci.yml as different.
    doctored = CI_YML.read_text().replace("makemigrations --check --noinput", "makemigrations --check")
    check(api_commands_from_ci(doctored) != mk, "the comparison cannot tell a changed ci.yml from the Makefile")


def only_with_an_unknown_name_fails(ctx):
    """The runner itself: `--only nosuchcase` exits non-zero instead of reporting 0 cases."""
    p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--only", "nosuchcase"],
                       capture_output=True, text=True)
    check(p.returncode != 0, "an unknown --only name exited 0:\n" + p.stdout + p.stderr)


CASES = [
    api_check_refuses_without_a_venv,
    install_then_check_passes,
    second_check_reuses_the_venv,
    api_install_rebuilds_cleanly,
    api_check_output_states_the_skips,
    default_interpreter_is_python3_14,
    blank_interpreter_never_refreshes_a_stale_venv,
    api_recipes_do_not_start_with_a_user_variable,
    broken_venv_is_refused_with_the_fix,
    failing_test_goes_red,
    missing_migration_goes_red,
    system_check_failure_goes_red,
    missing_pytest_fails_loudly,
    changed_pyproject_is_refused,
    touching_pyproject_does_not_refuse,
    interpreter_changed_in_place_is_refused,
    api_python_of_another_version_is_refused,
    incomplete_install_is_refused,
    wrong_tree_venv_is_refused,
    symlinked_venv_is_refused,
    foreign_directory_is_never_cleared,
    concurrent_install_is_refused,
    failed_install_leaves_no_stamp_and_retries,
    failed_rebuild_from_a_good_venv_is_not_trusted,
    missing_interpreter_fails_loudly,
    empty_interpreter_fails_loudly,
    old_interpreter_fails_loudly,
    interpreter_path_with_spaces_works,
    shell_metacharacters_in_interpreter_are_not_run,
    ambient_environment_is_scrubbed,
    makefile_variables_cannot_be_overridden,
    runs_from_another_working_directory,
    wrong_directory_never_passes_silently,
    ci_target_includes_api_check,
    help_lists_the_api_targets,
    ci_yml_commands_match_makefile,
    only_with_an_unknown_name_fails,
]


def run_cases(makefile_path, helper_path, only=None, quiet=False):
    """Returns {case name: None (pass) or failure text}."""
    python = find_python()
    results = {}
    with tempfile.TemporaryDirectory(prefix="check_api_gate_") as tmp:
        ctx = {"tmp": tmp, "python": python, "makefile_path": str(makefile_path),
               "makefile_text": Path(makefile_path).read_text(), "helper_text": Path(helper_path).read_text(),
               "wheelhouse": Path(tmp) / "wheelhouse"}
        build_wheelhouse(ctx["wheelhouse"])
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


# (what is broken, file, [(old, new) or (old, new, count) replacements], the case that must go red).
# Each `old` must occur exactly `count` (default 1) times, so a refactor that moves the line breaks the
# proof loudly instead of silently proving nothing.
M, H = "Makefile", "scripts/api_venv.py"
_ENV = 'env -i PATH="$$PATH" HOME="$$HOME" TMPDIR="$$TMPDIR" LANG="$$LANG" LC_ALL="$$LC_ALL" SQL_DATABASE=:memory:'
_STAMP_LINE = '(venv / STAMP).write_text(json.dumps({"python": full, "pyproject_sha256": pyproject_sha(api)}) + "\\n")'
MUTATIONS = [
    ("pytest failure swallowed", M, [("-m pytest tests -q -rfEs", "-m pytest tests -q -rfEs || true")], "failing_test_goes_red"),
    ("migration check removed", M, [('\tcd $(API) && $(API_ENV) "$(API_VPY)" manage.py makemigrations --check --noinput\n', "")],
     "missing_migration_goes_red"),
    ("system check removed", M, [('\tcd $(API) && $(API_ENV) "$(API_VPY)" manage.py check\n', "")], "system_check_failure_goes_red"),
    ("environment scrub removed", M, [("override API_ENV    := " + _ENV, "override API_ENV    :=")], "ambient_environment_is_scrubbed"),
    ("scrub only unsets SQL_ENGINE", M, [(_ENV, "env -u SQL_ENGINE SQL_DATABASE=:memory:")], "ambient_environment_is_scrubbed"),
    ("in-memory database dropped", M, [('LC_ALL="$$LC_ALL" SQL_DATABASE=:memory:', 'LC_ALL="$$LC_ALL"')], "ambient_environment_is_scrubbed"),
    ("override removed from API_VPY", M, [("override API_VPY    :=", "API_VPY    :=")], "makefile_variables_cannot_be_overridden"),
    ("override removed from API_ENV", M, [("override API_ENV    :=", "API_ENV    :=")], "makefile_variables_cannot_be_overridden"),
    ("override removed from API", M, [("override API        :=", "API        :=")], "makefile_variables_cannot_be_overridden"),
    ("override removed from API_VENV", M, [("override API_VENV   :=", "API_VENV   :=")], "makefile_variables_cannot_be_overridden"),
    ("override removed from API_HELPER", M, [("override API_HELPER :=", "API_HELPER :=")], "makefile_variables_cannot_be_overridden"),
    ("api-check dropped from ci", M, [("\t$(MAKE_RECURSE) --no-print-directory api-check\n", "")], "ci_target_includes_api_check"),
    ("ci calls api-install", M, [("\t$(MAKE_RECURSE) --no-print-directory api-check\n",
                                  "\t$(MAKE_RECURSE) --no-print-directory api-install\n\t$(MAKE_RECURSE) --no-print-directory api-check\n")],
     "ci_target_includes_api_check"),
    ("api-check installs instead of verifying", M, [("$(API_HELPER) verify", "$(API_HELPER) install")], "api_check_refuses_without_a_venv"),
    ("skip text dropped from help", M, [("the Postgres/Redis-only tests SKIP here, CI runs them", "")], "help_lists_the_api_targets"),
    ("ci help drops the limits", M, [("NOT covered:", "")], "help_lists_the_api_targets"),
    ("skip statement removed", M, [("Tests that need Postgres or Redis", "Some tests")], "api_check_output_states_the_skips"),
    ("CURDIR dropped (cwd-relative venv python)", M, [("override API_VPY    := $(CURDIR)/$(API_VENV)/bin/python", "override API_VPY    := $(API_VENV)/bin/python")],
     "runs_from_another_working_directory"),
    ("commands use the system python3, not the venv", M, [('"$(API_VPY)" -m pytest', "python3 -m pytest")], "install_then_check_passes"),
    ("migration flag dropped from the Makefile only", M, [("manage.py makemigrations --check --noinput\n", "manage.py makemigrations --check\n")],
     "ci_yml_commands_match_makefile"),
    ("errors ignored on every api-check line", M, [("\t$(API_HELPER) verify", "\t-$(API_HELPER) verify"),
                                                   ("\tcd $(API) && $(API_ENV)", "\t-cd $(API) && $(API_ENV)", 3)],
     "wrong_directory_never_passes_silently"),
    ("default interpreter exported before it is defined", M, [("API_PYTHON ?= python3.14\nexport API_PYTHON\n", "export API_PYTHON\nAPI_PYTHON ?= python3.14\n")],
     "default_interpreter_is_python3_14"),
    ("stamp written before the install", H, [("        " + _STAMP_LINE + "\n", ""),
                                             ('        subprocess.run([str(venv_python(venv)), "-m", "pip"',
                                              "        " + _STAMP_LINE + '\n        subprocess.run([str(venv_python(venv)), "-m", "pip"')],
     "failed_install_leaves_no_stamp_and_retries"),
    ("stamp written before the install (rebuild)", H, [("        " + _STAMP_LINE + "\n", ""),
                                                       ('        subprocess.run([str(venv_python(venv)), "-m", "pip"',
                                                        "        " + _STAMP_LINE + '\n        subprocess.run([str(venv_python(venv)), "-m", "pip"')],
     "failed_rebuild_from_a_good_venv_is_not_trusted"),
    ("--clear dropped", H, [('(["--clear"] if exists else [])', "[]")], "api_install_rebuilds_cleanly"),
    ("marker check before clearing removed", H, [("    if exists and not (venv.is_dir() and (venv / MARKER).is_file()):", "    if False:")],
     "foreign_directory_is_never_cleared"),
    ("symlink refusal removed", H, [("    if os.path.islink(str(venv)):", "    if False:")], "symlinked_venv_is_refused"),
    ("pyproject hash check removed", H, [('    if stamp.get("pyproject_sha256") != pyproject_sha(api):', "    if False:")], "changed_pyproject_is_refused"),
    ("pyproject check refuses every time", H, [('    if stamp.get("pyproject_sha256") != pyproject_sha(api):', "    if True:")],
     "touching_pyproject_does_not_refuse"),
    ("interpreter-in-place check removed", H, [('    if stamp.get("python") != actual[0]:', "    if False:")], "interpreter_changed_in_place_is_refused"),
    ("API_PYTHON mismatch check removed", H, [("        if found is not None and found[1] != actual[1]:", "        if False:")],
     "api_python_of_another_version_is_refused"),
    ("missing stamp trusted (a matching one is made up)", H,
     [('        die("%s has no valid install stamp',
       '        stamp = {"python": interpreter_version(venv_python(venv))[0], "pyproject_sha256": pyproject_sha(api)}\n'
       '        (lambda *a: None)("%s has no valid install stamp')],
     "incomplete_install_is_refused"),
    ("wrong-tree assertion neutered", H, [("assert p == root / 'selahcue_api' / '__init__.py', ", "assert 1, ")], "wrong_tree_venv_is_refused"),
    ("install lock removed", H, [("        os.mkdir(str(lock))", "        pass")], "concurrent_install_is_refused"),
    ("interpreter version check removed", H, [("    if major_minor < MIN_VERSION:", "    if False:")], "old_interpreter_fails_loudly"),
    ("interpreter presence check removed", H, [("    if exe is None:", "    if False:")], "missing_interpreter_fails_loudly"),
    ("API_PYTHON spliced into shell text", M, [("\t$(API_HELPER) install", "\t$(API_PYTHON) -c pass; $(API_HELPER) install")],
     "shell_metacharacters_in_interpreter_are_not_run"),
    ("api-check rewrites the stamp", H, [('    print("api-check: venv %s, Python %s" % (venv, actual[0]))',
                                         '    print("api-check: venv %s, Python %s" % (venv, actual[0]))\n    os.utime(str(venv / STAMP), None)')],
     "second_check_reuses_the_venv"),
    ("whitespace-only API_PYTHON accepted as set", H, [("    if not raw.strip():", "    if not raw:")], "blank_interpreter_never_refreshes_a_stale_venv"),
    ("recipe starts with the user's API_PYTHON", M, [("\t$(API_HELPER) install", "\t$(API_PYTHON) -c pass; $(API_HELPER) install")],
     "api_recipes_do_not_start_with_a_user_variable"),
    ("interpreter-gone check removed", H, [("    if actual is None:", "    if False:")], "broken_venv_is_refused_with_the_fix"),
    ("[dev] extra dropped from the pip install", H, [('"-e", ".[dev]"', '"-e", "."')], "install_then_check_passes"),
    ("--self-test line removed from ci", M, [("\tpython3 scripts/check_api_gate.py --self-test\n", "")], "ci_target_includes_api_check"),
    ("default interpreter is plain python3", M, [("API_PYTHON ?= python3.14", "API_PYTHON ?= python3")], "default_interpreter_is_python3_14"),
    ("empty API_PYTHON check removed", H, [("    if not raw.strip():", "    if False:")], "empty_interpreter_fails_loudly"),
]


def apply_mutation(tmp, mutation, makefile_text, helper_text):
    label, which, pairs, _case = mutation
    text = makefile_text if which == M else helper_text
    for pair in pairs:
        old, new = pair[0], pair[1]
        count = pair[2] if len(pair) > 2 else 1
        if text.count(old) != count:
            return None, "%s: the text to mutate occurs %d times, not %d: %r" % (label, text.count(old), count, old[:70])
        text = text.replace(old, new)
    mk, hp = Path(tmp) / "Makefile.mutated", Path(tmp) / "api_venv.mutated.py"
    mk.write_text(text if which == M else makefile_text)
    hp.write_text(text if which == H else helper_text)
    return (mk, hp), None


def mutation_proof():
    makefile_text, helper_text = MAKEFILE.read_text(), HELPER.read_text()
    failures, caught = [], 0
    with tempfile.TemporaryDirectory(prefix="check_api_gate_mut_") as tmp:
        base = run_cases(MAKEFILE, HELPER, quiet=True)
        bad = [n for n, r in base.items() if r]
        print("baseline (unmutated): %d cases, %d red" % (len(base), len(bad)))
        if bad:
            sys.exit("baseline is not green, so a mutation result would mean nothing: %s" % bad)
        covered = set(m[3] for m in MUTATIONS)
        for m in MUTATIONS:
            paths, err = apply_mutation(tmp, m, makefile_text, helper_text)
            if err:
                failures.append(err)
                print("  BROKEN PROOF %s" % m[0])
                continue
            res = run_cases(paths[0], paths[1], only=[m[3]], quiet=True)
            if res.get(m[3]) is None:
                failures.append("%s: case %s stayed GREEN with the behaviour removed" % (m[0], m[3]))
                print("  NOT CAUGHT   %-55s -> %s" % (m[0], m[3]))
            else:
                caught += 1
                print("  caught       %-55s -> %s" % (m[0], m[3]))
        uncovered = [c.__name__ for c in CASES if c.__name__ not in covered]
        print("cases with no mutation aimed at them (%d): %s" % (len(uncovered), ", ".join(uncovered)))
    if failures:
        print("\nMUTATION PROOF FAILED:\n  " + "\n  ".join(failures))
        return 1
    print("\nmutation proof: %d of %d mutations caught" % (caught, len(MUTATIONS)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true", help="run every case")
    ap.add_argument("--only", action="append", help="run only this case (repeatable)")
    ap.add_argument("--list", action="store_true", help="list the cases and what each pins")
    ap.add_argument("--mutation-proof", action="store_true", help="break the Makefile and helper on purpose; each case must go red")
    ap.add_argument("--makefile", default=str(MAKEFILE), help="Makefile under test (default: the repo's)")
    ap.add_argument("--helper", default=str(HELPER), help="scripts/api_venv.py under test (default: the repo's)")
    args = ap.parse_args()
    names = [c.__name__ for c in CASES]
    if args.list:
        for c in CASES:
            print("%-52s %s" % (c.__name__, (c.__doc__ or "").strip().splitlines()[0]))
        return 0
    if args.mutation_proof:
        return mutation_proof()
    if not args.self_test and not args.only:
        ap.error("pass --self-test, --only NAME, --list or --mutation-proof")
    unknown = [n for n in (args.only or []) if n not in names]
    if unknown:
        print("check_api_gate: unknown case(s): %s (see --list)" % ", ".join(unknown))
        return 2
    res = run_cases(args.makefile, args.helper, only=args.only)
    failed = [n for n, r in res.items() if r]
    expected = len(set(args.only)) if args.only else len(CASES)
    if not res or len(res) != expected:
        print("check_api_gate: ran %d cases, expected %d" % (len(res), expected))
        return 1
    print("check_api_gate: %d cases, %d failed" % (len(res), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
