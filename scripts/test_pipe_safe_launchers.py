#!/usr/bin/env python3
"""Caller regressions for17tnw2b1wpc; no Chrome, Cargo or executable TMPDIR needed.

Run: python3 scripts/test_pipe_safe_launchers.py
Only the executable boundary/time budget is substituted. Each real caller still
constructs its command, runs the real shared lifecycle and parses its own output.
Removing a migration restores the inherited-stderr wait or leaks its helper;
ignoring timed_out lets complete-looking hung output pass.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import headless_chrome as h  # noqa: E402

FAKE = r'''import json, os, subprocess, sys, time
from pathlib import Path
root = Path(os.environ["PIPE_FIXTURE"])
(root / "command.json").write_text(json.dumps({"args":sys.argv[1:], "visual_out":os.environ.get("SELAHCUE_VISUAL_OUT")}))
(root / "browser.pid").write_text(str(os.getpid()))
mode = os.environ["PIPE_MODE"]
helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
(root / "helper.pid").write_text(str(helper.pid))
if "native" in mode and "missing" not in mode:
    out = Path(os.environ["SELAHCUE_VISUAL_OUT"])
    (out / "one.png").write_bytes(b"fixture: parsing only, no pixel claim")
    (out / "index.json").write_text(json.dumps({"engine":"fake CPU renderer", "captures":[{"slug":"one", "file":"one.png", "width":2,"height":3,"ink":1}]}))
    print("test result: ok. 1 passed", flush=True)
elif "missing" in mode:
    print("no protocol result", flush=True)
elif "version" in mode:
    print("Chrome fixture 1", flush=True)
elif "probe" in mode:
    print("VPPROBE1200x713ENDPROBE", flush=True)
else:
    print("<pre>RESULTS\nPASS: fixture\nDONE(1)</pre>", flush=True)
    print('VPDATA{"ok":true,"regions":[],"viewport":{"w":1200,"h":800}}VPEND', flush=True)
(root / "emitted").write_text("complete fixture output flushed")
if "hang" in mode:
    time.sleep(60)
if "crash" in mode:
    sys.exit(7)
'''


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(kind, root):
    """Executed in its own process so legacy no-timeout code is bounded by the test."""
    root = Path(root)
    fake = root / "fake.py"
    fake.write_text(FAKE)
    work = root / "work"
    work.mkdir()
    tempfile.tempdir = str(work)
    os.environ.update(PIPE_FIXTURE=str(root), PIPE_MODE=kind)
    real_popen = subprocess.Popen
    real_run = subprocess.run
    requested = []

    def popen(argv, *args, **kwargs):
        if argv[0] in ("fixture-chrome", "cargo"):
            argv = [sys.executable, str(fake)] + list(argv[1:])
        return real_popen(argv, *args, **kwargs)

    def legacy_run(argv, *args, **kwargs):
        if argv[0] in ("fixture-chrome", "cargo"):
            requested.append(kwargs.get("timeout"))
            kwargs["timeout"] = 2 if "hang" in kind else 8
        return real_run(argv, *args, **kwargs)

    def browser(chrome, page_html, flags, timeout, **kwargs):
        requested.append(timeout)
        return real_browser(chrome, page_html, flags, 2 if "hang" in kind else 8, **kwargs)

    def command(argv, timeout, **kwargs):
        requested.append(timeout)
        return real_command(argv, 2 if "hang" in kind else 8, **kwargs)

    real_browser = h.run_headless_chrome
    real_command = getattr(h, "run_command", None)
    stdout = io.StringIO()
    result = {}
    start = time.monotonic()
    try:
        with mock.patch.object(subprocess, "Popen", popen), mock.patch.object(subprocess, "run", legacy_run), mock.patch.object(h, "run_headless_chrome", browser), contextlib.redirect_stdout(stdout):
            with contextlib.ExitStack() as stack:
                if real_command:
                    stack.enter_context(mock.patch.object(h, "run_command", command))
                if kind.startswith("auth"):
                    module = load("auth_pipe_test", HERE.parent / "implementation/marketing/scripts/auth_pages_headless.py")
                    dist = root / "dist"
                    dist.mkdir()
                    (dist / "index.html").write_text("fixture")
                    module.DIST = dist
                    module.check_bundle_is_current = lambda: None
                    module.find_chrome = lambda: "fixture-chrome"
                    # Keep real result parsing/count/equivalence assertions: incomplete
                    # fixture evidence must reach the existing refusal, never a false pass.
                    module.SCENARIOS = [("fixture", "/verify?token=fixture")]
                    module.CHROME_HEADLESS_ROOTS = []
                    result["value"] = module.main()
                elif kind.startswith("native"):
                    module = load("native_pipe_test", HERE / "vp_capture_native.py")
                    catalogue = root / "surfaces.json"
                    catalogue.write_text(json.dumps({"native":[{"slug":"one", "width":2,"height":3}]}))
                    with mock.patch.object(sys, "argv", [str(module.__file__), "--out", str(root / "out"), "--surfaces", str(catalogue)]):
                        result["value"] = module.main()
                else:
                    module = load("web_pipe_test", HERE / "vp_capture_web.py")
                    if kind.startswith("version"):
                        result["value"] = module.chrome_version("fixture-chrome")
                    elif kind.startswith("capture"):
                        _, data, errors = module.capture_blink("fixture-chrome", (0,87), "", {"slug":"fixture", "width":1200,"height":800}, str(root))
                        result["value"] = {"data":data, "errors":errors}
                    elif kind.startswith("probe"):
                        result["value"] = module.probe_window_chrome("fixture-chrome")
                    else:
                        page = root / "source page.html"
                        page.write_text("fixture source preserved")
                        result["value"] = module._run_chrome("fixture-chrome", str(page), (1200,800), 2, 9000, screenshot=str(root / "shot.png"))
    except BaseException as exc:
        result["exception"] = type(exc).__name__
        result["exception_text"] = str(exc)
        if isinstance(exc, subprocess.TimeoutExpired):
            result["exception_cmd"] = exc.cmd
    result.update(elapsed=time.monotonic()-start, output=stdout.getvalue(), requested=requested, leftovers=[p.name for p in work.iterdir()])
    (root / "result.json").write_text(json.dumps(result))


class OperatorViewport(unittest.TestCase):
    def test_operator_passes_an_explicit_viewport_to_the_real_launcher_boundary(self):
        """An omitted/duplicated viewport must fail even if Chrome's default happens to match."""
        captured = {}

        class ReachedLauncher(Exception):
            pass

        def capture(chrome, page_html, flags, timeout, **kwargs):
            captured.update(chrome=chrome, html=page_html, flags=flags, timeout=timeout)
            raise ReachedLauncher

        with mock.patch.dict(os.environ, {"CHROME_BIN":sys.executable}), mock.patch.object(h, "self_test", return_value=[]), mock.patch.object(h, "run_headless_chrome", capture), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ReachedLauncher):
                runpy.run_path(str(HERE / "operator_headless.py"), run_name="__main__")
        self.assertEqual([flag for flag in captured["flags"] if flag.startswith("--window-size")], ["--window-size=800,600"])
        self.assertIn("--headless=new", captured["flags"])
        self.assertIn("--virtual-time-budget=90000", captured["flags"])
        self.assertIn("CSSOM-PARSE-03", captured["html"])
        self.assertEqual(captured["timeout"], 90)


class Callers(unittest.TestCase):
    def run_case(self, kind):
        with tempfile.TemporaryDirectory(prefix="selahcue-pipe-callers-") as folder:
            root = Path(folder)
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", kind, folder], stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                try:
                    out, err = proc.communicate(timeout=12)
                except subprocess.TimeoutExpired:
                    self.fail("caller did not finish while its completed command's helper held stderr")
                self.assertEqual(proc.returncode, 0, (out,err))
                data = json.loads((root / "result.json").read_text())
                command = json.loads((root / "command.json").read_text())
                self.assertTrue((root / "emitted").is_file(), "fake did not finish writing protocol output; case proves no completed-output behavior")
                # Before test teardown, check the production cleanup actually killed
                # our in-group helper. The test's own cleanup is not evidence.
                pids = [int(p.read_text()) for p in root.glob("*.pid")]
                deadline = time.monotonic()+1
                while any(h._pid_alive(pid) for pid in pids) and time.monotonic()<deadline:
                    time.sleep(.02)
                data["alive"] = [pid for pid in pids if h._pid_alive(pid)]
                print(json.dumps({"case":kind, "elapsed":data["elapsed"], "requested":data["requested"], "leftovers":data["leftovers"], "alive":data["alive"], "exception":data.get("exception"), "value":data.get("value") if not isinstance(data.get("value"), str) else "text"}), flush=True)
                return data, command
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.communicate()
                for path in root.glob("*.pid"):
                    try:
                        os.kill(int(path.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def clean(self, data):
        self.assertEqual(data["leftovers"], [], data)
        self.assertEqual(data["alive"], [], data)

    def test_finished_callers_do_not_wait_for_inherited_stderr(self):
        for kind, timeout in (("auth",90),("probe",60),("web",180),("native",600),("version",20)):
            with self.subTest(caller=kind):
                data, command = self.run_case(kind)
                self.assertLess(data["elapsed"], 2, data)
                self.assertNotIn("exception", data, data)
                self.assertEqual(data["requested"], [timeout])
                self.clean(data)
                if kind == "auth":
                    self.assertEqual(data["value"], 4)  # genuine fixture coverage refusal
                    self.assertIn("expected exactly", data["output"])
                    self.assertRegex(command["args"][-1], r"^http://127\.0\.0\.1:\d+/verify\?token=fixture&__scenario=fixture$")
                    self.assertIn("--window-size=1440,900", command["args"])
                    self.assertIn("--virtual-time-budget=8000", command["args"])
                elif kind == "probe":
                    self.assertEqual(data["value"], [0,87])
                elif kind == "web":
                    self.assertIn("DONE(1)", data["value"])
                    self.assertIn("--force-device-scale-factor=2", command["args"])
                    self.assertIn("--virtual-time-budget=9000", command["args"])
                    self.assertTrue(any(a.startswith("--screenshot=") for a in command["args"]))
                    self.assertTrue(command["args"][-1].startswith("file://"))
                elif kind == "version":
                    self.assertEqual(data["value"], "Chrome fixture 1")
                    self.assertEqual(command["args"], ["--version"])
                else:
                    self.assertEqual(data["value"], 0, data)
                    self.assertEqual(command["args"], ["test","--manifest-path",str(HERE.parent / "implementation/desktop/Cargo.toml"),"-p","selahcue-present","--test","visual_parity_render","export_captures_when_the_harness_asks_for_them","--","--nocapture"])
                    self.assertTrue(command["visual_out"].endswith("/out"))
                if kind not in ("native", "version"):
                    self.assertNotIn("--user-data-dir", " ".join(command["args"]))
                    self.assertIn("--dump-dom", command["args"])

    def test_complete_looking_hangs_are_failures_and_cleaned(self):
        for kind in ("auth-hang", "probe-hang", "web-hang", "native-hang", "capture-hang"):
            with self.subTest(caller=kind):
                data, _ = self.run_case(kind)
                self.clean(data)
                if kind.startswith("auth"):
                    self.assertEqual(data.get("value"), 2, data)
                    self.assertIn("FAIL: headless Chrome timed out on scenario fixture (infra)",data["output"])
                elif kind.startswith("native"):
                    self.assertEqual(data.get("value"), 1, data)
                    self.assertIn("FAIL: the native capture target timed out (infra)",data["output"])
                elif kind.startswith("capture"):
                    self.assertEqual(data.get("value"), {"data":{"ok":False,"errors":["timeout"],"regions":[]}, "errors":["headless Chrome timed out"]}, data)
                else:
                    self.assertEqual(data.get("exception"), "TimeoutExpired", data)
                    self.assertIsInstance(data.get("exception_cmd"), list, data)
                    self.assertEqual(data["exception_cmd"][0], "fixture-chrome")
                    self.assertIn("--dump-dom", data["exception_cmd"])
                    self.assertTrue(data["exception_cmd"][-1].startswith("file://"))

    def test_missing_protocol_results_keep_existing_failures(self):
        for kind in ("auth-missing", "probe-missing", "native-missing"):
            with self.subTest(caller=kind):
                data, _ = self.run_case(kind)
                self.clean(data)
                if kind.startswith("auth"):
                    self.assertEqual(data.get("value"), 2, data)
                    self.assertIn("NO RESULTS BLOCK for scenario fixture", data["output"])
                elif kind.startswith("probe"):
                    self.assertEqual(data.get("exception"), "SystemExit", data)
                    self.assertEqual(data["exception_text"], "vp_capture_web: could not probe the headless viewport delta")
                else:
                    self.assertEqual(data.get("value"), 2, data)
                    self.assertIn("FAIL: the capture target ran but wrote no index.json to ", data["output"])

    def test_plain_command_does_not_sweep_browser_litter(self):
        # Native commands must not acquire browser flags or filesystem authority.
        # A matching directory created during this plain command is not Chrome's.
        with tempfile.TemporaryDirectory(prefix="selahcue-plain-command-") as folder:
            marker = Path(folder) / "com.google.Chrome.chrome_chrome_url_fetcher_.AbCd12"
            result = h.run_command([sys.executable, "-c", "import os,sys; os.mkdir(sys.argv[1]); print('complete')", str(marker)], timeout=10, tmp_root=folder)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(result.timed_out)
            self.assertEqual(result.stdout.strip(), "complete")
            self.assertEqual(list(Path(folder).iterdir()), [marker])

    def test_native_nonzero_exit_keeps_existing_failure(self):
        data, _ = self.run_case("native-crash")
        self.clean(data)
        self.assertEqual(data.get("value"), 1, data)
        self.assertIn("FAIL: the native capture target did not pass (exit 7)", data["output"])


if __name__ == "__main__":
    if len(sys.argv)>1 and sys.argv[1] == "--worker":
        worker(sys.argv[2],sys.argv[3])
    else:
        unittest.main()
