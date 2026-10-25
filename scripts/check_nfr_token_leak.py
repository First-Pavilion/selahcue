#!/usr/bin/env python3
"""Guards 17tnw2b9aga: the REAL release output window must not write its live Operator bearer token
to its own stdout/stderr.

`scripts/measure_nfr.sh` (`make nfr`, run by CI under xvfb) already starts the real release host with
stdout and stderr redirected into a log file -- exactly the "token ends up in a log" scenario the
ticket is about -- while the host's endpoint file holds the live token. So this check is the
process-level half of the guarantee: the in-process unit tests (`connect_banner_token_tests` in
`selahcue-desktop`) read back the banner stream the host is handed, but they cannot see a stray
`println!` elsewhere in the process; this reads what the real process actually wrote.

    check_nfr_token_leak.py <endpoint-file> <host-log-file>   exit 0 clean, 1 leaked/unusable, 2 usage
    check_nfr_token_leak.py --self-test                       exit 0 when every case behaves

It fails closed. A clean verdict needs two positive controls first, so it cannot pass vacuously:

  * the endpoint file names a token of at least MIN_TOKEN_LEN characters (the host's tokens are 64
    hex characters; a missing or tiny token would make "the log does not contain it" meaningless,
    and the empty string is a substring of everything), and
  * the log contains the startup banner (BANNER_MARKER), i.e. it really is the host's output and
    the banner really was written before we looked.

The token itself is NEVER printed, not even on failure: the message says only that it leaked and
where. (Printing it would put the credential into the very CI log this check exists to protect.)

Needs only the Python standard library, no cargo and no display, so the self-test runs anywhere.
"""

import json
import os
import secrets
import shutil
import sys
import tempfile

# The line `write_connect_banner` (selahcue-desktop/src/main.rs) opens with. If the banner is ever
# reworded this check goes red with the message below rather than passing on an empty log.
BANNER_MARKER = "remote control ready"
MIN_TOKEN_LEN = 32
USAGE = "usage: check_nfr_token_leak.py <endpoint-file> <host-log-file> | --self-test"


def check(endpoint_path, log_path):
    """Return (ok, message). The message never contains the token."""
    try:
        with open(endpoint_path, encoding="utf-8") as f:
            descriptor = json.load(f)
    except (OSError, ValueError) as e:
        return False, "cannot read the endpoint file %s (%s)" % (endpoint_path, type(e).__name__)
    token = descriptor.get("token") if isinstance(descriptor, dict) else None
    if not isinstance(token, str) or len(token) < MIN_TOKEN_LEN:
        return False, (
            "the endpoint file has no usable token (missing, not a string, or shorter than %d "
            "characters), so the leak check would be vacuous" % MIN_TOKEN_LEN
        )
    try:
        with open(log_path, "rb") as f:
            log = f.read().decode("utf-8", errors="replace")
    except OSError as e:
        return False, "cannot read the host log %s (%s)" % (log_path, type(e).__name__)
    if BANNER_MARKER not in log:
        return False, (
            "the host log %s does not contain the startup banner (%r), so a clean result would "
            "prove nothing. Was the banner reworded, or did the host not start?"
            % (log_path, BANNER_MARKER)
        )
    if token in log:
        return False, (
            "LEAK: the live Operator bearer token from the endpoint file appears in the host's "
            "stdout/stderr log %s. The token is not printed here on purpose." % log_path
        )
    return True, "the live Operator token is absent from the host log (%d chars checked)" % len(token)


def _self_test():
    failures = []
    tmp = tempfile.mkdtemp(prefix="selahcue-nfr-leak-selftest-")
    try:
        token = secrets.token_hex(32)  # 64 hex characters, like the host's
        banner = (
            "\n  SelahCue - remote control ready\n"
            "  device  : operator-shell   role : Operator (host shell); token: in the endpoint file (0600)\n"
        )

        def write(name, text):
            path = os.path.join(tmp, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return path

        endpoint = write("endpoint.json", json.dumps({"addr": "127.0.0.1:1", "token": token}))
        clean = write("clean.log", banner)
        leak_in_command = write(
            "leak-cmd.log", banner + "      127.0.0.1:1 pin operator-shell %s next\n" % token
        )
        leak_on_stderr = write("leak-err.log", banner + "boom: token=%s\n" % token)

        def expect(name, got, want_ok, must_mention=None):
            ok, message = got
            if ok != want_ok:
                failures.append("%s: expected ok=%s, got ok=%s (%s)" % (name, want_ok, ok, message))
            if token in message:
                failures.append("%s: the message contained the token itself" % name)
            if must_mention and must_mention not in message:
                failures.append("%s: message should mention %r, got %r" % (name, must_mention, message))

        expect("a. leaking log (paste-ready command)", check(endpoint, leak_in_command), False, "LEAK")
        expect("a2. leaking log (token elsewhere)", check(endpoint, leak_on_stderr), False, "LEAK")
        expect("b. clean log", check(endpoint, clean), True)
        expect(
            "c. clean log WITHOUT the banner (positive control)",
            check(endpoint, write("nobanner.log", "unrelated output\n")),
            False,
            "startup banner",
        )
        expect(
            "c2. empty log (positive control)", check(endpoint, write("empty.log", "")), False, "banner"
        )
        expect(
            "d. short token",
            check(write("short.json", json.dumps({"token": "abc"})), clean),
            False,
            "no usable token",
        )
        expect(
            "d2. empty token (the empty string is a substring of everything)",
            check(write("empty-token.json", json.dumps({"token": ""})), clean),
            False,
            "no usable token",
        )
        expect(
            "d3. no token field",
            check(write("notoken.json", json.dumps({"addr": "x"})), clean),
            False,
            "no usable token",
        )
        expect(
            "d4. token of the wrong type",
            check(write("numtoken.json", json.dumps({"token": 12345678901234567890123456789012345})), clean),
            False,
            "no usable token",
        )
        expect("d5. missing endpoint file", check(os.path.join(tmp, "nope.json"), clean), False, "endpoint")
        expect("d6. endpoint file that is not JSON", check(write("junk.json", "{not json"), clean), False)
        expect("d7. missing log file", check(endpoint, os.path.join(tmp, "nope.log")), False, "host log")
        # A non-UTF-8 byte in the log must not crash the check (the host's output is not guaranteed UTF-8).
        raw = os.path.join(tmp, "binary.log")
        with open(raw, "wb") as f:
            f.write(banner.encode("utf-8") + b"\xff\xfe junk\n" + token.encode("ascii") + b"\n")
        expect("e. leak next to non-UTF-8 bytes", check(endpoint, raw), False, "LEAK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for line in failures:
            print("SELF-TEST FAIL: " + line, file=sys.stderr)
        return 1
    print("check_nfr_token_leak self-test: all cases behave")
    return 0


def main(argv):
    if argv[1:] == ["--self-test"]:
        return _self_test()
    if len(argv) != 3:
        print(USAGE, file=sys.stderr)
        return 2
    ok, message = check(argv[1], argv[2])
    print(("   OK: " if ok else "FAIL: ") + message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
