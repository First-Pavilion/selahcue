#!/usr/bin/env python3
"""Print the path of the loopback endpoint descriptor the output window publishes (17tnw2b9agb).

    python3 scripts/endpoint_path.py          prints the path and a newline, exit 0

The Makefile (`make launch`, `make remote`) and `scripts/measure_nfr.sh` (`make nfr`) need the same
path the host and the operator use. That path is chosen by `selahcue_lan::local_endpoint::resolve_dir`
(Rust); this script is its mirror for shell tooling and MUST give the same answer for the same
environment. `selahcue-lan/tests/test_local_endpoint.rs`
(`make_and_the_nfr_script_resolve_the_same_path_as_the_rust_code`) runs this script against the Rust
resolver on many environments so the two cannot drift.

The rule (Unix), first match wins:

  1. $XDG_RUNTIME_DIR, if it is absolute and private to the current user;
  2. the temp directory (see below), if it is already private to the current user (this is macOS,
     where $TMPDIR is a per-user 0700 directory, so macOS keeps its location);
  3. "selahcue" under $XDG_STATE_HOME (absolute) or $HOME/.local/state (HOME absolute), when that
     directory is private to the user and its parent is a real directory of the user's that group and
     other cannot write to, or when it does not exist yet and the nearest existing ancestor is such a
     directory (the host creates the missing parts, 0700);
  4. otherwise the "selahcue-UID" subdirectory of the temp directory (the shared-/tmp last resort).

The temp directory is what Rust's std::env::temp_dir() returns: $TMPDIR when set (an EMPTY $TMPDIR is
treated as /tmp); when unset, /tmp, except on macOS where it is the per-user Darwin temp directory
(confstr _CS_DARWIN_USER_TEMP_DIR), which is where an unset $TMPDIR lands.

"Private" is judged with lstat, never following a symlink and with trailing slashes removed first
(lstat("link/") follows the link): a real directory, owned by the effective uid, with no group or other
permission bits. On Windows the temp directory is already per-user.

This only RESOLVES. It creates nothing and reads nothing: the host creates the directory, and the
operator and the host check it again before every use. Dev tooling that uses this path
(`make remote`, `make nfr`, `make launch`) does not itself verify the directory's owner: it reads and
deletes the file as the same user who runs the host.
"""

import os
import stat
import sys
import tempfile

NAME = "selahcue-operator-endpoint.json"
_CS_DARWIN_USER_TEMP_DIR = 65537


def _lstat(path):
    return os.lstat(path.rstrip("/") or "/")


def _private(path, uid):
    try:
        st = _lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == uid and (st.st_mode & 0o077) == 0


def _closed_and_ours(path, uid):
    try:
        st = _lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == uid and (st.st_mode & 0o022) == 0


def _absolute(value):
    return value if value and os.path.isabs(value) else None


def _temp_dir():
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir is not None:
        return tmpdir or "/tmp"
    if sys.platform == "darwin":
        try:
            import ctypes

            buf = ctypes.create_string_buffer(1024)
            if ctypes.CDLL(None).confstr(_CS_DARWIN_USER_TEMP_DIR, buf, ctypes.c_size_t(1024)) > 0:
                return buf.value.decode()
        except Exception:
            pass
    return "/tmp"


def _state_base():
    base = _absolute(os.environ.get("XDG_STATE_HOME"))
    if base:
        return base
    home = _absolute(os.environ.get("HOME"))
    return os.path.join(home, ".local", "state") if home else None


def _nearest_existing_ancestor(path):
    current = os.path.dirname(path)
    while True:
        try:
            _lstat(current)
            return current
        except FileNotFoundError:
            pass
        except OSError:
            return None
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _state_dir_usable(path, uid):
    try:
        _lstat(path)
    except FileNotFoundError:
        ancestor = _nearest_existing_ancestor(path)
        return ancestor is not None and _closed_and_ours(ancestor, uid)
    except OSError:
        return False
    return _private(path, uid) and _closed_and_ours(os.path.dirname(path), uid)


def resolve_dir():
    if os.name != "posix":
        return tempfile.gettempdir()
    uid = os.geteuid()
    xdg = _absolute(os.environ.get("XDG_RUNTIME_DIR"))
    if xdg and _private(xdg, uid):
        return xdg
    temp = _temp_dir()
    if _private(temp, uid):
        return temp
    base = _state_base()
    if base:
        state = os.path.join(base, "selahcue")
        if _state_dir_usable(state, uid):
            return state
    return os.path.join(temp, "selahcue-%d" % uid)


def main():
    sys.stdout.write(os.path.join(resolve_dir(), NAME) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
