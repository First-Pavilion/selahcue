#!/usr/bin/env python3
"""The virtualenv behind `make api-install` / `make api-check` (ClickUp 86ak5rjh7, API half).

Two subcommands, both called from the Makefile, both run with the system `python3` (3.9-compatible):

  install   Build the venv and `pip install -e ".[dev]"` into it. The ONLY command that installs, and it
            is run on purpose, by name. `make ci` and `make api-check` never call it.
  verify    Refuse, with a message that names `make api-install`, unless the venv exists, is ours, is
            current and imports the API from THIS checkout. Prints the venv's Python version.

Inputs come from the environment, not from shell text, so a value with spaces or metacharacters is
data and never code: API_PYTHON (the interpreter `install` builds from; `verify` also compares it).
Paths come as arguments from Makefile variables that are `override`-protected.

WHY EACH GUARD EXISTS (every one has a case in scripts/check_api_gate.py and a mutation that removes it):

  * A directory name only this target uses (`.venv-api-check`), and a marker file inside it. `install`
    only ever `--clear`s a directory that carries the marker; anything else at that path is refused,
    never wiped. A developer's own `.venv` is a different name and is never touched.
  * A symlink at the venv path is refused. A link can point at another checkout's venv, whose
    third-party packages came from another tree's pyproject.toml.
  * The stamp is written LAST and records the interpreter version and the SHA-256 of pyproject.toml.
    `verify` recomputes both: a changed dependency pin or a different interpreter is a refusal, a
    content-neutral `touch` is not. An interrupted install leaves no stamp, so it is never trusted.
  * `install` takes a lock directory, so two first runs at once cannot both rewrite the venv.
  * `verify` imports `selahcue_api` with `python -I` and requires the exact file under this checkout's
    implementation/api, so a venv installed from another checkout is refused. (Not because it would
    test that checkout's code: the cwd and pytest.ini's `pythonpath = .` win on sys.path. Because its
    third-party packages were resolved from ANOTHER tree's pyproject.toml.)

WHAT IT DOES NOT PROMISE: `pip install` runs with the developer's full environment (pip needs HOME, proxy
and certificate settings), not the scrubbed one the three test commands get. Direct dependencies are pinned
exactly and the build backend is pinned in pyproject.toml's [build-system]; transitive dependencies are
neither locked nor hashed, so the venv holds whatever resolved on the day it was built while CI re-resolves
on every run. Until the hash-locked requirements file of ClickUp 17tnw2az0kw lands, the two can differ.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MARKER = ".selahcue-api-check-venv"
STAMP = ".selahcue-api-installed"
MIN_VERSION = (3, 12)


def die(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def venv_python(venv):
    return venv / "bin" / "python"


def pyproject_sha(api):
    return hashlib.sha256((api / "pyproject.toml").read_bytes()).hexdigest()


def interpreter_version(exe):
    """('3.14.5', (3, 14)) for the interpreter at `exe`, or None if it cannot be run."""
    try:
        p = subprocess.run([str(exe), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
                           capture_output=True, text=True)
    except OSError:
        return None
    if p.returncode != 0 or not p.stdout.strip():
        return None
    full = p.stdout.strip()
    parts = full.split(".")
    return full, (int(parts[0]), int(parts[1]))


def requested_interpreter():
    raw = os.environ.get("API_PYTHON", "")
    if not raw.strip():
        die("API_PYTHON is empty -- the API venv needs Python 3.14 (CI pins 3.14; pyproject needs >=3.12).\n"
            "  Set it to an interpreter: make api-install API_PYTHON=/path/to/python3.14")
    exe = shutil.which(raw)
    if exe is None:
        die("'%s' is not on PATH -- the API venv needs Python 3.14 (CI pins 3.14; pyproject needs >=3.12).\n"
            "  Install it (macOS: brew install python@3.14), or run: make api-install API_PYTHON=/path/to/python3.13"
            % raw)
    return exe


def check_venv_path(venv):
    if os.path.islink(str(venv)):
        die("%s is a symlink -- refusing to use or rebuild a linked virtualenv (it may belong to another checkout).\n"
            "  Remove the link, then run: make api-install" % venv)


def cmd_install(api, venv):
    exe = requested_interpreter()
    found = interpreter_version(exe)
    if found is None:
        die("'%s' could not be run to report its version." % exe)
    full, major_minor = found
    if major_minor < MIN_VERSION:
        die("Python %s is too old -- implementation/api needs Python >=3.12 (CI pins 3.14).\n"
            "  Run: make api-install API_PYTHON=/path/to/python3.14" % full)
    check_venv_path(venv)
    exists = venv.exists()
    if exists and not (venv.is_dir() and (venv / MARKER).is_file()):
        die("%s exists but was not created by `make api-install` (no %s inside) -- refusing to clear it.\n"
            "  Move or delete it yourself if you are sure, then run: make api-install" % (venv, MARKER))
    lock = Path(str(venv) + ".lock")
    try:
        os.mkdir(str(lock))
    except FileExistsError:
        die("%s exists: another `make api-install` is running, or a previous one was killed.\n"
            "  If none is running, remove that directory and run again." % lock)
    try:
        print("api-install: building %s with Python %s and running pip install -e \".[dev]\" "
              "(needs the network; direct dependencies are pinned, transitive ones are not locked)" % (venv, full))
        args = [exe, "-m", "venv"] + (["--clear"] if exists else []) + [str(venv)]
        subprocess.run(args, check=True)
        (venv / MARKER).write_text("created by make api-install\n")
        subprocess.run([str(venv_python(venv)), "-m", "pip", "install", "--disable-pip-version-check", "--quiet",
                        "-e", ".[dev]"], cwd=str(api), check=True)
        (venv / STAMP).write_text(json.dumps({"python": full, "pyproject_sha256": pyproject_sha(api)}) + "\n")
    except subprocess.CalledProcessError as e:
        die("`%s` failed (exit %d); the venv is incomplete and has no stamp, so api-check will not trust it.\n"
            "  Fix the cause (network?) and run: make api-install" % (" ".join(map(str, e.cmd[:4])), e.returncode))
    finally:
        shutil.rmtree(str(lock), ignore_errors=True)
    print("api-install: done -- Python %s in %s" % (full, venv))


def cmd_verify(api, venv):
    again = "Run: make api-install  (a deliberate install; `make ci` and `make api-check` never install)"
    check_venv_path(venv)
    if not venv.is_dir():
        die("%s does not exist.\n  %s" % (venv, again))
    if not (venv / MARKER).is_file():
        die("%s was not created by `make api-install` (no %s inside).\n  %s" % (venv, MARKER, again))
    try:
        stamp = json.loads((venv / STAMP).read_text())
    except (OSError, ValueError):
        die("%s has no valid install stamp: the install was interrupted or never finished.\n  %s" % (venv, again))
    py = venv_python(venv)
    actual = interpreter_version(py)
    if actual is None:
        die("%s cannot run: its interpreter is gone or broken.\n  %s" % (py, again))
    if stamp.get("python") != actual[0]:
        die("the venv was built with Python %s but now runs Python %s (the interpreter changed in place).\n  %s"
            % (stamp.get("python"), actual[0], again))
    wanted = os.environ.get("API_PYTHON", "").strip()
    if wanted:
        exe = shutil.which(wanted)
        found = interpreter_version(exe) if exe else None
        if found is not None and found[1] != actual[1]:
            die("the venv was built with Python %s.%s but API_PYTHON is Python %s.%s.\n  %s"
                % (actual[1][0], actual[1][1], found[1][0], found[1][1], again))
    if stamp.get("pyproject_sha256") != pyproject_sha(api):
        die("implementation/api/pyproject.toml changed since the venv was installed (dependency pins may differ).\n  %s"
            % again)
    code = ("import pathlib, selahcue_api; p = pathlib.Path(selahcue_api.__file__).resolve(); "
            "root = pathlib.Path('.').resolve(); "
            "assert p == root / 'selahcue_api' / '__init__.py', "
            "'selahcue_api imports from %s, not from this checkout (%s)' % (p, root)")
    r = subprocess.run([str(py), "-I", "-c", code], cwd=str(api), capture_output=True, text=True)
    if r.returncode != 0:
        die("the venv was installed from another checkout (its packages came from another tree's pyproject.toml):\n"
            "  %s\n  %s" % (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "import failed", again))
    print("api-check: venv %s, Python %s" % (venv, actual[0]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["install", "verify"])
    ap.add_argument("--api", required=True, help="implementation/api")
    ap.add_argument("--venv", required=True, help="the venv directory (inside --api)")
    args = ap.parse_args()
    api = Path(args.api).resolve()
    venv = Path(args.venv)
    venv = (Path.cwd() / venv) if not venv.is_absolute() else venv
    if not (api / "pyproject.toml").is_file():
        die("%s has no pyproject.toml -- run make from the repository root." % api)
    (cmd_install if args.command == "install" else cmd_verify)(api, venv)


if __name__ == "__main__":
    main()
