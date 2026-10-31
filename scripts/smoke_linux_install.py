#!/usr/bin/env python3
"""Exercise real installed Tauri IPC; never substitute the demo bridge or print endpoint tokens."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

SCRIPT = """const done = arguments[arguments.length - 1];
if (!window.__TAURI__ || !window.__TAURI__.core) { done(false); }
else { window.__TAURI__.core.invoke('host_connected').then(v => done(v === true)).catch(() => done(false)); }
"""


def request(base, path, body=None, method=None):
    raw = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=raw,
                                 headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=20) as reply:
        result = json.load(reply)
    value = result.get("value")
    if isinstance(value, dict) and value.get("error"):
        raise RuntimeError("Installed-app WebDriver command failed")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application", type=Path, required=True)
    args = parser.parse_args()
    application = args.application.resolve(strict=True)
    if not application.is_file() or not (application.parent / "selahcue-output").is_file():
        raise RuntimeError("Installed operator and real output sibling are required")
    if os.environ.get("LD_LIBRARY_PATH") or os.environ.get("LD_PRELOAD"):
        raise RuntimeError("Developer loader overrides cannot be installation evidence")
    base = "http://127.0.0.1:4444"
    session = None
    with tempfile.TemporaryDirectory(prefix="selahcue-installed-smoke-") as temp:
        env = dict(os.environ)
        for key in list(env):
            if key.startswith(("SELAHCUE_", "DYLD_", "NDI_")) or key in ("OPENAI_API_KEY", "DEEPGRAM_API_KEY"):
                env.pop(key)
        private = Path(temp)
        # Isolate test state without altering HOME or reading an existing operator session.
        for key, name in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                          ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache"),
                          ("XDG_RUNTIME_DIR", "runtime")):
            (private / name).mkdir(mode=0o700)
            env[key] = str(private / name)
        # Public fixture for this ephemeral encrypted test store, never a provider credential.
        env["SELAHCUE_PASSPHRASE"] = "ci-only-ephemeral-install-smoke"
        # Do not upload raw driver/app logs: only the boolean assertion is evidence here.
        with tempfile.TemporaryFile() as log:
            driver = subprocess.Popen(["tauri-driver", "--port", "4444"], env=env,
                                      stdout=log, stderr=log, start_new_session=True)
            try:
                for _ in range(60):
                    if driver.poll() is not None:
                        raise RuntimeError("tauri-driver exited before becoming ready")
                    try:
                        request(base, "/status")
                        break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.25)
                else:
                    raise RuntimeError("tauri-driver readiness timeout")
                value = request(base, "/session", {"capabilities": {"alwaysMatch": {
                    "tauri:options": {"application": str(application)}}}})
                session = value["sessionId"]
                connected = False
                for _ in range(80):
                    connected = request(base, f"/session/{session}/execute/async",
                                        {"script": SCRIPT, "args": []}) is True
                    if connected:
                        break
                    time.sleep(0.25)
                if not connected:
                    raise RuntimeError("Installed operator did not connect to its real audience backend; demo fallback is not acceptance")
                print("Installed operator real host_connected IPC: true (no mocked bridge).")
                request(base, f"/session/{session}", method="DELETE")
                session = None
                # Teardown below also kills any session-owned child processes. Actual
                # normal-close/no-orphan acceptance remains a separate device check.
            finally:
                if session:
                    try:
                        request(base, f"/session/{session}", method="DELETE")
                    except (OSError, RuntimeError):
                        pass
                try:
                    os.killpg(driver.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    driver.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(driver.pid, signal.SIGKILL)
                    driver.wait(timeout=5)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        # Avoid response bodies, raw logs, endpoint descriptors and credential values.
        reason = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        print(f"Installed Linux IPC smoke failed: {reason}", file=sys.stderr)
        sys.exit(1)
