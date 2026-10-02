#!/usr/bin/env python3
"""Run headless Chrome on one page (`--dump-dom`) WITHOUT ever waiting on its pipes (17tnw2b1f32).

Used by `scripts/operator_headless.py`; written so the other headless launchers can adopt it.

THE BUG THIS REPLACES. The gate used `subprocess.run(..., capture_output=True, timeout=90)`.
`capture_output` makes stdout/stderr PIPES and `run()` does not return until BOTH reach EOF, i.e.
until every process that inherited them has closed them. Chrome's own helpers do inherit them and
outlive the browser: `chrome_crashpad_handler` (ppid 1, its own process group; seen live while
writing this) and the two `GoogleUpdater` processes Vera caught holding the stderr pipe with `lsof`
(ticket 17tnw2b1f32). So a Chrome that had exited normally, having printed a complete result,
still made the gate sit out the full 90 s and report `FAIL: headless Chrome timed out (infra)`.
It hit `main` and PRs in 3 of 28 runs for one reviewer and 4 of 12 for another (same ticket).

THE FIX, and why each part is shaped as it is:

1. stdout and stderr go to FILES in a private work dir, and the gate waits on the BROWSER PID only.
   A file has no EOF to wait for, so a helper that keeps the descriptor open can no longer delay
   anything, no matter which of the two streams it holds or whether it escaped our process group.
   (Sending stderr to DEVNULL alone would not do: nothing proves the helpers only hold stderr.)
   stderr is kept, not discarded, but only its LAST `STDERR_TAIL_BYTES` are ever read, so a
   chatty browser costs disk for at most one timeout and never memory.
2. A timeout of the BROWSER is still a failure, always. Nothing here looks at partial output to
   rescue a Chrome that did not exit: a hung browser that already printed a complete block is
   reported as `timed_out` and the gate exits 2, exactly as before (`hang` in `self_test`).
3. Chrome is started in its own session/process group (`start_new_session`), and the whole group
   is SIGKILLed on a timeout AND at the end of every run, so the GPU/utility helpers of a hung or
   a finished browser cannot outlive it. The crashpad handler and the updater are NOT in that
   group (they escape it) and are deliberately left alone: the first exits by itself when the
   browser goes, the second is Google's shared updater service, not ours to kill.
   Known, accepted race: the group id is the browser's PID, and a PID is only reusable once every
   member of its group is gone, so the final `killpg` can only ever hit our own stragglers; the
   residual window (the group emptying and the PID being recycled into a new group leader between
   two adjacent statements) is not worth a `waitid(WNOWAIT)` dance.
   A SIGTERM handler turns "the gate was killed" into a normal unwind, because a browser in its
   own session no longer shares the gate's fate when only the gate is signalled.
4. Every file the run itself creates (page, captured output) lives in ONE private directory that
   is removed in `finally`, on every path including a timeout and an exception.

WHAT IS DELIBERATELY NOT DONE, with the measurement behind it (Google Chrome 154, macOS, this
gate's real page, `--virtual-time-budget=75000`):

* No `--user-data-dir`. The ticket proposed a throwaway profile. On this Mac every fresh-profile
  run with output captured to files (7 of 7: bare x3, +`--no-first-run`,
  +`--disable-background-networking`, and a profile pre-seeded with a `First Run` sentinel plus all
  three hardening flags on the gate's real page; all three hardening flags on a trivial page)
  printed a COMPLETE result and then never exited. The same real page with the default profile
  exited in 5-6 s every time (12 of 12). The one fresh-profile run that did exit was a bare profile
  on a trivial page. A throwaway profile would have turned this flaky false red into a permanent
  real one. `self_test` pins the absence.
* No TMPDIR redirection. Chrome on macOS ignores `$TMPDIR` for the dirs below: with `TMPDIR`
  pointed at a private folder nothing was ever written there (sampled every 50 ms through a run)
  while the same entries still appeared in the real temp dir.

WHAT THE LEAK ACTUALLY WAS, and what is done about it. With a 75 s virtual-time budget Chrome's
background timers fire during the run and leave two kinds of entries in the real temp dir:
`.com.google.Chrome.<rand>` (a CRX3 download) and `com.google.Chrome.chrome_chrome_url_fetcher_.<rand>`
(a directory holding one downloaded payload). `--disable-background-networking` removes the first
(2 of 2 runs per variant, with and without the other flags); NO flag tried removes the second
(`--disable-component-update`, `--disable-sync`, `--metrics-recording-only`, ... each tried).
So the second is removed by name after the run, narrowly: only a DIRECTORY, owned by us, whose
name matches that exact pattern, and which did NOT exist before this launch. NEVER widen this to
`.com.google.Chrome.*`: those are the live renderer temp files of whatever Chrome the user has open
(`lsof` showed fd 14 of every renderer of the user's own browser on them), and deleting one is
damage, not cleanup.
"""
import collections
import contextlib
import io
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

# Carried by every launch. `--disable-background-networking` is the one that removes the
# `.com.google.Chrome.*` CRX leak; the other two are the ticket's belt-and-braces (a first-run
# dialog or a component update must never be able to stall a headless run). NOT here:
# `--user-data-dir` (see the module docstring: it hangs Chrome on macOS).
CHROME_HARDENING_FLAGS = (
    "--no-first-run",
    "--disable-component-update",
    "--disable-background-networking",
)

# How much of Chrome's stderr is read back for diagnostics. Bounded on purpose.
STDERR_TAIL_BYTES = 4096

# The ONLY entry class swept from the real temp dir. See the module docstring before touching it.
_CHROME_URL_FETCHER_LITTER = re.compile(r"^com\.google\.Chrome\.chrome_chrome_url_fetcher_\.[A-Za-z0-9]{4,12}$")

ChromeRun = collections.namedtuple("ChromeRun", "stdout stderr_tail returncode timed_out elapsed pid")


def _kill_process_group(proc):
    """SIGKILL everything in the launched browser's process group (best effort, never raises)."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:  # pragma: no cover - non-POSIX: no group to kill, take the browser alone
            proc.kill()
    except OSError:
        # ProcessLookupError: the group is already empty. PermissionError: macOS reports a group
        # that holds only zombies this way. Both mean there is nothing left to kill.
        pass


def _remove_tree(path):
    """Remove `path` entirely; retry briefly because a just-killed helper can still be writing."""
    for _ in range(5):
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            return True
        time.sleep(0.2)
    return False


def _read_text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_tail(path, nbytes):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - nbytes))
        return f.read().decode("utf-8", errors="replace")


def _sweep_chrome_litter(tmp_root, existed_before):
    """Remove the url-fetcher temp dirs this launch created. Returns the names removed."""
    removed = []
    try:
        names = os.listdir(tmp_root)
    except OSError:
        return removed
    uid = os.getuid() if hasattr(os, "getuid") else None
    for name in names:
        if name in existed_before or not _CHROME_URL_FETCHER_LITTER.match(name):
            continue
        path = os.path.join(tmp_root, name)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if not stat.S_ISDIR(st.st_mode) or (uid is not None and st.st_uid != uid):
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed.append(name)
    return removed


def _raise_system_exit(signum, frame):
    raise SystemExit(128 + signum)


def run_headless_chrome(chrome, page_html, flags, timeout, tmp_root=None):
    """Load `page_html` in headless Chrome, return a `ChromeRun`. See the module docstring.

    `flags` are the caller's own flags (`--headless=new`, budget, ...); the hardening flags, the
    `--dump-dom` and the page URL are appended here. `tmp_root` is where the private work dir is
    made and where url-fetcher litter is swept (default: the system temp dir).
    """
    tmp_root = tmp_root or tempfile.gettempdir()
    existed_before = set(os.listdir(tmp_root))
    workdir = tempfile.mkdtemp(prefix="selahcue-headless-", dir=tmp_root)
    proc = None
    old_sigterm = None
    try:
        # A browser in its own session no longer dies with a signalled gate; unwind instead.
        try:
            old_sigterm = signal.signal(signal.SIGTERM, _raise_system_exit)
        except ValueError:  # not the main thread: the caller owns signal handling
            old_sigterm = None
        page = os.path.join(workdir, "page.html")
        out_path = os.path.join(workdir, "chrome.stdout")
        err_path = os.path.join(workdir, "chrome.stderr")
        with open(page, "w", encoding="utf-8") as f:
            f.write(page_html)
        argv = [chrome] + list(flags) + list(CHROME_HARDENING_FLAGS) + ["--dump-dom", "file://" + page]
        popen_kwargs = {"start_new_session": True} if os.name == "posix" else {}
        timed_out = False
        returncode = None
        started = time.time()
        with open(out_path, "wb") as out_f, open(err_path, "wb") as err_f:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f, **popen_kwargs)
            try:
                returncode = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_process_group(proc)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass  # SIGKILLed and still not reaped: nothing more a gate can do
        elapsed = time.time() - started
        return ChromeRun(
            stdout=_read_text(out_path),
            stderr_tail=_read_tail(err_path, STDERR_TAIL_BYTES),
            returncode=returncode,
            timed_out=timed_out,
            elapsed=elapsed,
            pid=proc.pid,
        )
    finally:
        if proc is not None:
            _kill_process_group(proc)
        if not _remove_tree(workdir):
            print("WARN: could not remove headless Chrome work dir %s" % workdir, file=sys.stderr)
        _sweep_chrome_litter(tmp_root, existed_before)
        if old_sigterm is not None:
            signal.signal(signal.SIGTERM, old_sigterm)


# ---------------------------------------------------------------------------------------------
# Self-test. Runs the REAL `run_headless_chrome` against fake browsers (python scripts), so every
# behaviour above is checked on the code path the gate uses, in a few seconds and without Chrome.
# Mutation-verified: see the PR for which edit each scenario turns red.
# ---------------------------------------------------------------------------------------------
_FAKE_CHROME_SRC = '''import json, os, subprocess, sys, time
CFG = json.loads(os.environ["FAKE_CHROME_CASE"])
KIND = CFG["kind"]
PID_DIR = CFG["pid_dir"]


def record(key, value):
    with open(os.path.join(PID_DIR, key), "w") as f:
        f.write(str(value))


def emit(text):
    sys.stdout.write(text)
    sys.stdout.flush()


page_path = sys.argv[-1][len("file://"):]
record("argv.json", json.dumps(sys.argv[1:]))
with open(page_path) as f:
    record("page.html", f.read())
SLEEPER = [sys.executable, "-c", "import time; time.sleep(600)"]
PASS = "<html><body><pre id=__r>RESULTS\\nPASS: a\\nPASS: b\\nPASS: c\\nDONE(3)</pre></body></html>\\n"

if KIND == "pass_group_helper":
    # A helper in OUR process group that inherits stdout+stderr and outlives the browser.
    record("helper", subprocess.Popen(SLEEPER).pid)
    emit(PASS)
elif KIND == "pass_escaped_helper":
    # The crashpad-handler / GoogleUpdater shape: it left our session, so no group kill reaches it.
    record("helper", subprocess.Popen(SLEEPER, start_new_session=True).pid)
    emit(PASS)
elif KIND == "fail_block":
    emit(PASS.replace("PASS: b", "FAIL: boom"))
elif KIND == "no_block":
    emit("<html><body>no results here</body></html>\\n")
elif KIND == "count_drift":
    emit(PASS.replace("DONE(3)", "DONE(4)"))
elif KIND == "crash":
    sys.stderr.write("boom: renderer crashed\\n")
    sys.exit(7)
elif KIND == "hang":
    # Prints a COMPLETE passing block and then never exits: must still be red.
    record("self", os.getpid())
    record("helper", subprocess.Popen(SLEEPER).pid)
    emit(PASS)
    time.sleep(600)
elif KIND == "litter":
    root = CFG["litter_root"]
    os.makedirs(os.path.join(root, "com.google.Chrome.chrome_chrome_url_fetcher_.NEWLEAK"))
    with open(os.path.join(root, "com.google.Chrome.chrome_chrome_url_fetcher_.NEWLEAK", "payload"), "w") as f:
        f.write("x")
    with open(os.path.join(root, ".com.google.Chrome.LIVEFILE"), "w") as f:
        f.write("a live renderer's temp file")
    os.makedirs(os.path.join(root, "scoped_dirKEEP"))
    os.makedirs(os.path.join(root, "com.google.Chrome.some_other_dir_.KEEPME"))
    emit(PASS)
elif KIND == "stderr_flood":
    sys.stderr.write("x" * (3 * 1024 * 1024))
    sys.stderr.flush()
    emit(PASS)
else:
    sys.exit("unknown fake kind " + KIND)
'''


def _write_fake_chrome(root):
    """The ONE fake-browser executable every scenario shares; it picks its behaviour from the
    FAKE_CHROME_CASE env var. One file, not one per scenario, on purpose: macOS scans every newly
    created executable the first time it is run (~0.45 s each, measured), which would more than
    double the self-test's wall time. It is a tiny shell wrapper around THIS interpreter because a
    `#!/usr/bin/env python3` shebang resolves to macOS's /usr/bin/python3 shim, slower again."""
    path = os.path.join(root, "fake-chrome")
    if not os.path.exists(path):
        script = path + ".py"
        with open(script, "w") as f:
            f.write(_FAKE_CHROME_SRC)
        with open(path, "w") as f:
            f.write("#!/bin/sh\nexec %s %s \"$@\"\n" % (shlex.quote(sys.executable), shlex.quote(script)))
        os.chmod(path, 0o755)
    return path


def _pid_alive(pid):
    """True if `pid` is a live process. A zombie counts as dead: it is only waiting to be reaped."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        state = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
        ).stdout.strip()
    except OSError:
        return True
    return bool(state) and not state.startswith("Z")


def _wait_dead(pid, seconds=5.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


def _read_pid(pid_dir, key, seconds=0.0):
    """The int recorded by the fake under `key`, or None. Polls up to `seconds`."""
    deadline = time.time() + seconds
    while True:
        try:
            text = open(os.path.join(pid_dir, key)).read().strip()
            if text.isdigit():
                return int(text)
        except OSError:
            pass
        if time.time() >= deadline:
            return None
        time.sleep(0.05)


class _Case(object):
    """One scenario's private directories (so assertions never see another scenario's files)."""

    def __init__(self, root, kind, tag=None):
        self.kind = kind
        base = os.path.join(root, tag or kind)
        self.pid_dir = os.path.join(base, "pids")
        self.tmp_root = os.path.join(base, "tmp")
        os.makedirs(self.pid_dir)
        os.makedirs(self.tmp_root)
        self.chrome = _write_fake_chrome(root)
        self.case_json = json.dumps({"kind": kind, "pid_dir": self.pid_dir, "litter_root": self.tmp_root})

    def run(self, timeout, flags=("--headless=new", "--virtual-time-budget=1000"), html="<html>page</html>"):
        previous = os.environ.get("FAKE_CHROME_CASE")
        os.environ["FAKE_CHROME_CASE"] = self.case_json
        try:
            return run_headless_chrome(self.chrome, html, flags, timeout, tmp_root=self.tmp_root)
        finally:
            if previous is None:
                del os.environ["FAKE_CHROME_CASE"]
            else:
                os.environ["FAKE_CHROME_CASE"] = previous

    def leftovers(self, ignore=()):
        return sorted(n for n in os.listdir(self.tmp_root) if n not in ignore)


def self_test(verdict=None, expected_checks=3):
    """Check the launcher against fake browsers. Returns a list of problems (empty = all good).

    `verdict(run, expected_checks) -> exit code`, when given (the gate passes its own), is also
    asserted per scenario, so "exits 0 / 1 / 2 / 4" is proven through the gate's real mapping.
    Its printing is swallowed: a fake's `FAIL:` lines must never reach the gate's log.
    """
    problems = []
    if os.name != "posix":
        print("SKIP: headless-launch self-test needs POSIX process groups (this gate runs on macOS/Linux)")
        return problems
    root = tempfile.mkdtemp(prefix="selahcue-headless-selftest-")
    spawned = []  # exact PIDs of every helper a fake started: killed at the end whatever happened
    here = os.path.dirname(os.path.abspath(__file__))
    page_html = "<html><body>the page handed to Chrome</body></html>"

    def code_of(run):
        if verdict is None:
            return None
        with contextlib.redirect_stdout(io.StringIO()):
            return verdict(run, expected_checks)

    def expect_code(name, run, want):
        got = code_of(run)
        if got is not None and got != want:
            problems.append("%s: the gate would exit %r, expected %d" % (name, got, want))

    def pids_of(case, *keys):
        found = {}
        for key in keys:
            pid = _read_pid(case.pid_dir, key)
            if pid is not None:
                spawned.append(pid)
                found[key] = pid
        return found

    try:
        # 1. AC1 (17tnw2b1f32): a complete passing block, then a helper in the browser's own group
        #    keeps the inherited stdout/stderr open. Must return promptly, must not time out, and
        #    must not leave that helper alive.
        case = _Case(root, "pass_group_helper")
        run = case.run(timeout=12, html=page_html)
        helpers = pids_of(case, "helper")
        name = "pass + helper in the browser's group"
        if run.timed_out:
            problems.append("%s: the launcher waited on the helper's descriptors until its %ds timeout "
                            "(the helper sleeps for 600 s)" % (name, 12))
        if "RESULTS" not in run.stdout:
            problems.append("%s: the complete result Chrome printed was lost" % name)
        if "helper" not in helpers:
            problems.append("%s: the fake never started its helper, the scenario proves nothing" % name)
        elif not _wait_dead(helpers["helper"]):
            problems.append("%s: the helper in the browser's process group outlived the run" % name)
        if case.leftovers():
            problems.append("%s: the run left %s in its temp root" % (name, case.leftovers()))
        expect_code(name, run, 0)
        # The argv the browser actually received. The absence of --user-data-dir is a DECISION, see
        # the module docstring: on macOS a fresh profile hangs Chrome after it prints its result.
        try:
            with open(os.path.join(case.pid_dir, "argv.json")) as f:
                argv = json.loads(f.read())
            with open(os.path.join(case.pid_dir, "page.html")) as f:
                handed = f.read()
        except (OSError, ValueError):
            argv, handed = [], None
        # Spelled out here, NOT read from CHROME_HARDENING_FLAGS: a test that iterates the constant
        # it is checking passes when a flag is deleted from it (found by mutation, 17tnw2b1f32).
        for flag in ("--headless=new", "--virtual-time-budget=1000", "--no-first-run",
                     "--disable-component-update", "--disable-background-networking"):
            if flag not in argv:
                problems.append("launch argv: %s was not passed to Chrome (got %s)" % (flag, argv))
        if any(a.startswith("--user-data-dir") for a in argv):
            problems.append("launch argv carries --user-data-dir: a fresh profile hangs headless Chrome on macOS "
                            "after it has printed its result (17tnw2b1f32, measured 7/7) - do not add it back "
                            "without re-measuring")
        if len(argv) < 2 or argv[-2] != "--dump-dom" or not argv[-1].startswith("file://"):
            problems.append("launch argv: expected `--dump-dom file://<page>` last, got %s" % argv[-2:])
        if handed != page_html:
            problems.append("launch: the page Chrome loaded is not the page the caller passed")

        # 2. The same, but the helper ESCAPED the group (what crashpad and GoogleUpdater do), so no
        #    group kill can reach it: only "do not wait on the pipes" can pass. The helper being
        #    alive afterwards is the control that this scenario really models an escape.
        case = _Case(root, "pass_escaped_helper")
        run = case.run(timeout=12)
        helpers = pids_of(case, "helper")
        name = "pass + helper that escaped the group"
        if run.timed_out:
            problems.append("%s: the launcher waited on the escaped helper's descriptors until its %ds timeout "
                            "(the helper sleeps for 600 s)" % (name, 12))
        if "helper" not in helpers or not _pid_alive(helpers["helper"]):
            problems.append("%s: control invalid - the escaped helper is not alive, so this scenario "
                            "no longer models crashpad/GoogleUpdater" % name)
        if case.leftovers():
            problems.append("%s: the run left %s in its temp root" % (name, case.leftovers()))
        expect_code(name, run, 0)

        # 3. AC2: a browser that PRINTS A COMPLETE BLOCK and then never exits is still a timeout:
        #    red, never rescued from its partial output. Browser AND helper must be gone, no temp dirs.
        name = "hung browser"
        for attempt, timeout in enumerate((3, 20)):
            case = _Case(root, "hang", tag="hang%d" % attempt)
            run = case.run(timeout=timeout)
            helpers = pids_of(case, "self", "helper")
            if len(helpers) == 2:
                break
            # A loaded machine can start the fake after a 3 s timeout: inconclusive, not a verdict.
        if len(helpers) != 2:
            problems.append("%s: the fake never started, the scenario proves nothing" % name)
        else:
            if not run.timed_out:
                problems.append("%s: a Chrome that never exits was not reported as timed out" % name)
            for key, label in (("self", "browser"), ("helper", "helper in its group")):
                if not _wait_dead(helpers[key]):
                    problems.append("%s: the %s was left running after the timeout" % (name, label))
            if case.leftovers():
                problems.append("%s: the run left %s in its temp root" % (name, case.leftovers()))
            expect_code(name, run, 2)

        # 4-7. The rest of the exit-code contract, through the same launcher.
        case = _Case(root, "fail_block")
        run = case.run(timeout=12)
        if run.timed_out:
            problems.append("failing block: timed out")
        expect_code("failing block", run, 1)

        case = _Case(root, "no_block")
        expect_code("no results block", case.run(timeout=12), 2)

        case = _Case(root, "count_drift")
        expect_code("check-count drift", case.run(timeout=12), 4)

        case = _Case(root, "crash")
        run = case.run(timeout=12)
        if run.returncode != 7 or "boom: renderer crashed" not in run.stderr_tail:
            problems.append("crash: exit code / stderr were not captured (rc=%r, stderr=%r)"
                            % (run.returncode, run.stderr_tail))
        expect_code("crashed browser", run, 2)

        # 8. AC3 on macOS: the url-fetcher dir THIS run created is swept; nothing else is. A dir that
        #    existed before the launch, a live renderer's `.com.google.Chrome.*` file and an unrelated
        #    `scoped_dir*` must all survive.
        case = _Case(root, "litter")
        preexisting = "com.google.Chrome.chrome_chrome_url_fetcher_.PREEXIST"
        os.makedirs(os.path.join(case.tmp_root, preexisting))
        run = case.run(timeout=12)
        want = sorted([preexisting, ".com.google.Chrome.LIVEFILE", "scoped_dirKEEP",
                       "com.google.Chrome.some_other_dir_.KEEPME"])
        if case.leftovers() != want:
            problems.append("litter sweep: expected exactly %s to remain in the temp root, found %s"
                            % (want, case.leftovers()))
        expect_code("litter", run, 0)

        # 9. Bounded memory: 3 MB of stderr must cost at most STDERR_TAIL_BYTES of what we hold.
        case = _Case(root, "stderr_flood")
        run = case.run(timeout=30)
        if len(run.stderr_tail) > STDERR_TAIL_BYTES:
            problems.append("stderr flood: kept %d bytes of stderr, the cap is %d"
                            % (len(run.stderr_tail), STDERR_TAIL_BYTES))
        expect_code("stderr flood", run, 0)

        # 10. Killing the GATE (SIGTERM) must unwind through the same cleanup: the browser lives in
        #     its own session, so it no longer shares the gate's fate on its own.
        case = _Case(root, "hang", tag="sigterm")
        code = ("import sys; sys.path.insert(0, %r); import headless_chrome as h; "
                "h.run_headless_chrome(%r, '<html></html>', [], timeout=120, tmp_root=%r)"
                % (here, case.chrome, case.tmp_root))
        gate = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=dict(os.environ, FAKE_CHROME_CASE=case.case_json))
        try:
            started = _read_pid(case.pid_dir, "helper", seconds=30)
            helpers = pids_of(case, "self", "helper")
            if started is None or len(helpers) != 2:
                problems.append("SIGTERM: the fake never started, the scenario proves nothing")
            else:
                gate.send_signal(signal.SIGTERM)
                try:
                    status = gate.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    status = None
                    problems.append("SIGTERM: the gate did not exit after SIGTERM")
                if status is not None and status != 128 + signal.SIGTERM:
                    problems.append("SIGTERM: the gate exited %r instead of unwinding with %d"
                                    % (status, 128 + signal.SIGTERM))
                for key, label in (("self", "browser"), ("helper", "helper in its group")):
                    if not _wait_dead(helpers[key]):
                        problems.append("SIGTERM: the %s outlived the signalled gate" % label)
                if case.leftovers():
                    problems.append("SIGTERM: the signalled gate left %s in its temp root" % case.leftovers())
        finally:
            if gate.poll() is None:
                gate.kill()
                gate.wait()
    finally:
        for pid in spawned:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(root, ignore_errors=True)
    return problems


def main():
    problems = self_test()
    for problem in problems:
        print("FAIL: headless-launch self-test (17tnw2b1f32) - " + problem)
    if problems:
        return 1
    print("PASS: headless-launch self-test (17tnw2b1f32)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
