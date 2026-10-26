#!/usr/bin/env python3
"""Print the path of the loopback endpoint descriptor the output window publishes (17tnw2b9agb).

    python3 scripts/endpoint_path.py          prints the path, no newline surprises, exit 0

The Makefile (`make launch`, `make remote`) and `scripts/measure_nfr.sh` (`make nfr`) need the same
path the host and the operator use. That path is chosen by `selahcue_lan::local_endpoint::resolve_dir`
(Rust); this script is its mirror for shell tooling and MUST give the same answer for the same
environment. `selahcue-lan/tests/test_local_endpoint.rs`
(`make_and_the_nfr_script_resolve_the_same_path_as_the_rust_code`) runs this script against the Rust
resolver on six environments so the two cannot drift.

The rule (Unix), first match wins:

  1. $XDG_RUNTIME_DIR, if it is absolute and private to the current user;
  2. the temp directory ($TMPDIR, else /tmp), if it is already private to the current user (this is
     macOS, where $TMPDIR is a per-user 0700 directory, so macOS keeps its location);
  3. otherwise the "selahcue-UID" subdirectory of the temp directory (Linux's shared /tmp).

"Private" is judged with lstat, never following a symlink: a real directory, owned by the effective
uid, with no group or other permission bits. On Windows the temp directory is already per-user.

This only RESOLVES. It creates nothing and reads nothing: the host creates the directory, and the
operator and the host check it again before every use.
"""

import os
import stat
import sys
import tempfile

NAME = "selahcue-operator-endpoint.json"


def _private(path, uid):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == uid and (st.st_mode & 0o077) == 0


def resolve_dir():
    if os.name != "posix":
        return tempfile.gettempdir()
    uid = os.geteuid()
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg and os.path.isabs(xdg) and _private(xdg, uid):
        return xdg
    temp = os.environ.get("TMPDIR") or "/tmp"
    if _private(temp, uid):
        return temp
    return os.path.join(temp, "selahcue-%d" % uid)


def main():
    sys.stdout.write(os.path.join(resolve_dir(), NAME) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
