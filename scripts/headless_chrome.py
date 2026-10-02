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
   chatty browser costs disk for at most one timeout and never memory. stdout is read WHOLE, on
   purpose: it is the DOM dump and the result block sits inside it, so a cap would have to pick an
   arbitrary point to give up at. Real Chrome writes about 2 MB there; the old `capture_output`
   path held it whole too. Measured by Quinn on PR #153: a pathological 150 MB of stdout peaks at
   about 318 MB of RSS (539 MB before), and the 150 MB of STDERR that used to cost 550 MB now costs
   57 MB. That is the trade-off, accepted because the page is our own and the stream is not chatty.
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
4. Signals. A browser in its own session no longer shares the gate's fate when only the gate is
   signalled, so SIGTERM, SIGHUP (a closed terminal) and SIGINT unwind through the same cleanup
   (`_SignalGuard`). Three rules, each found by a reviewer:
   * A signal that lands while the browser is being CREATED must not interrupt that: the handler
     would unwind with `proc` still None and orphan a browser nobody can kill (Quinn: reproduced
     deterministically, and it made the self-test itself flaky at ~10x CPU overload). It is held
     in software and delivered the moment `proc` exists. It is NOT held with `pthread_sigmask`:
     a blocked mask is inherited across fork/exec, so Chrome and every helper it starts would run
     with SIGTERM/SIGHUP blocked (verified, a child printed [1, 15] as its blocked set).
   * A signal during CLEANUP must never abandon it (Cody, Shadow: a second SIGTERM mid-`rmtree`
     left the work dir and the group behind). Once a signal has been acted on, or while cleaning
     up, later ones are recorded and only honoured AFTER cleanup has finished.
   * Each cleanup step is guarded on its own, so one failing step cannot skip the rest or turn
     the verdict into a traceback.
   What cannot be handled: SIGKILL of the gate itself. A browser in its own session then outlives
   it; a healthy `--dump-dom` run exits by itself (bounded by the virtual-time budget), a hung one
   persists until killed by hand. The old gate shared the terminal's session and so died with it
   on a hangup; that case is now covered by the SIGHUP handler.
5. Every file the run itself creates (page, captured output) lives in ONE private directory that
   is removed in `finally`, on every path including a timeout and an exception, and the
   directory is created INSIDE the `try` so a failure or a signal right after creation cannot
   leak it.

WHAT IS DELIBERATELY NOT DONE, with the measurement behind it (Google Chrome 154, macOS, this
gate's real page, `--virtual-time-budget=75000`):

* No `--user-data-dir`. The ticket proposed a throwaway profile. On this Mac 7 of the 8
  fresh-profile runs with output captured to files (bare x3, +`--no-first-run`,
  +`--disable-background-networking`, and a profile pre-seeded with a `First Run` sentinel plus all
  three hardening flags on the gate's real page; all three hardening flags on a trivial page)
  printed a COMPLETE result and then never exited. The 8th, a bare profile on a trivial page,
  exited normally. The same real page with the default profile exited in 5-6 s every time (12 of
  12). A throwaway profile would have turned this flaky false red into a permanent real one.
  `self_test` pins the absence.
* No TMPDIR redirection. Chrome on macOS ignores `$TMPDIR` for the dirs below: with `TMPDIR`
  pointed at a private folder nothing was ever written there (sampled every 50 ms through a run)
  while the same entries still appeared in the real temp dir.

WHAT THE LEAK ACTUALLY WAS, and what is done about it. With a 75 s virtual-time budget Chrome's
background timers fire during the run and leave two kinds of entries in the real temp dir:
`.com.google.Chrome.<rand>` (a CRX3 download) and `com.google.Chrome.chrome_chrome_url_fetcher_.<rand>`
(a directory holding one downloaded payload). `--disable-background-networking` removes the first
(2 of 2 runs per variant, with and without the other flags); NO flag tried removes the second
(`--disable-component-update`, `--disable-sync`, `--metrics-recording-only`, ... each tried).
So the second is removed by name after the run, narrowly. A candidate must ALL of: match the exact
name (`fullmatch`), be a DIRECTORY (`lstat`, so a symlink is never followed), be owned by us, NOT
have existed before this launch, and not have been written to after our browser exited (a
directory with a newer mtime than the browser's exit belongs to some other process that is still
at work, so it is left alone). NEVER widen this to `.com.google.Chrome.*`: those are the live
renderer temp files of whatever Chrome the user has open (`lsof` showed fd 14 of every renderer of
the user's own browser on them), and deleting one is damage, not cleanup.
Residual risk, accepted and written down: attribution after the fact is impossible (the process
that created a dir is dead by the time we sweep), so a url-fetcher dir that ANOTHER Chrome created
and finished writing inside our run window looks exactly like ours and is removed too. That other
Chrome is either the user's own (its component download for that cycle fails and is retried on the
next scheduled check) or, more likely on a shared machine, another gate run overlapping this one
(harmless to both verdicts: the page is a `file://` stub). On Linux the name pattern does not
match, so the sweep does nothing there.
"""
import collections
import contextlib
import io
import json
import os
import re
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
_CHROME_URL_FETCHER_LITTER = re.compile(r"com\.google\.Chrome\.chrome_chrome_url_fetcher_\.[A-Za-z0-9]{4,12}")

# A candidate whose newest mtime is later than the browser's exit by more than this belongs to
# some other process (clock/filesystem timestamp jitter, not a design parameter).
_SWEEP_MTIME_SLACK_S = 0.05

ChromeRun = collections.namedtuple("ChromeRun", "stdout stderr_tail returncode timed_out elapsed pid")


def describe_exit(returncode):
    """A human reading of Chrome's exit status: `7`, `-11 (killed by SIGSEGV)`, `none (never exited)`."""
    if returncode is None:
        return "none (never exited)"
    if returncode < 0:
        try:
            return "%d (killed by %s)" % (returncode, signal.Signals(-returncode).name)
        except ValueError:
            return "%d (killed by signal %d)" % (returncode, -returncode)
    return str(returncode)


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


def _list_names(directory):
    """The names in `directory`, or None if it cannot be listed (a write-only temp dir works for the
    launch itself, so it must not be what fails the gate; without the listing there is nothing to
    attribute litter against, so the sweep is simply skipped)."""
    try:
        return set(os.listdir(directory))
    except OSError:
        return None


def _newest_mtime(path, st):
    """The newest mtime of the directory `path` (already lstat'ed as `st`) and its direct entries.
    A directory's own mtime only moves when entries are added or removed, not when one is written to."""
    newest = st.st_mtime
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    newest = max(newest, entry.stat(follow_symlinks=False).st_mtime)
                except OSError:
                    pass
    except OSError:
        pass
    return newest


def _sweep_chrome_litter(tmp_root, existed_before, browser_exited_at):
    """Remove the url-fetcher temp dirs this launch created. Returns the names removed."""
    removed = []
    if existed_before is None:
        return removed
    try:
        names = os.listdir(tmp_root)
    except OSError:
        return removed
    uid = os.getuid() if hasattr(os, "getuid") else None
    for name in names:
        if name in existed_before or not _CHROME_URL_FETCHER_LITTER.fullmatch(name):
            continue
        path = os.path.join(tmp_root, name)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if not stat.S_ISDIR(st.st_mode) or (uid is not None and st.st_uid != uid):
            continue
        if _newest_mtime(path, st) > browser_exited_at + _SWEEP_MTIME_SLACK_S:
            continue  # written to after our browser was gone: someone else's, and still at work
        shutil.rmtree(path, ignore_errors=True)
        removed.append(name)
    return removed


def _best_effort(what, fn, *args):
    """Run one cleanup step; whatever it raises must not skip the steps after it or replace the
    caller's result with a traceback."""
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001 - cleanup has to finish
        print("WARN: headless Chrome cleanup step %r failed: %r" % (what, exc), file=sys.stderr)
        return None


class _SignalGuard(object):
    """Turns SIGTERM / SIGHUP / SIGINT into a normal unwind, but only where unwinding is safe.

    `armed` is True only while the browser exists and has been assigned to `proc`. Outside that
    window (before launch, while the browser is being created, during cleanup) a signal is merely
    RECORDED; it is delivered the moment the guard is armed or, failing that, after cleanup. A
    signal that has already interrupted the run is acted on once: later ones are ignored, so the
    cleanup that follows can never be interrupted. See the module docstring, item 4.
    """

    _NAMES = ("SIGTERM", "SIGHUP", "SIGINT")

    def __init__(self):
        self._armed = False
        self._fired = False
        self._pending = None
        self._previous = {}

    def install(self):
        for name in self._NAMES:
            sig = getattr(signal, name, None)  # SIGHUP does not exist on Windows
            if sig is None:
                continue
            try:
                if signal.getsignal(sig) == signal.SIG_IGN:
                    continue  # ignored on purpose (`nohup`, a background job): immunity is the caller's choice
                self._previous[sig] = signal.signal(sig, self._handle)
            except (ValueError, OSError):
                return  # not the main thread: the caller owns signal handling

    def _handle(self, signum, frame):
        if self._fired:
            return
        if self._armed:
            self._interrupt(signum)
        elif self._pending is None:
            self._pending = signum

    def _interrupt(self, signum):
        self._fired = True
        self._armed = False
        self._pending = None
        if signum == getattr(signal, "SIGINT", None):
            raise KeyboardInterrupt()
        raise SystemExit(128 + signum)

    def raise_if_pending(self):
        if self._pending is not None and not self._fired:
            self._interrupt(self._pending)

    def arm(self):
        self._armed = True
        self.raise_if_pending()

    def disarm(self):
        self._armed = False

    def restore(self):
        previous, self._previous = self._previous, {}
        for sig, handler in previous.items():
            if handler is None:  # installed from C: nothing Python can put back
                continue
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass


def run_headless_chrome(chrome, page_html, flags, timeout, tmp_root=None):
    """Load `page_html` in headless Chrome, return a `ChromeRun`. See the module docstring.

    `flags` are the caller's own flags (`--headless=new`, budget, ...); the hardening flags, the
    `--dump-dom` and the page URL are appended here. `tmp_root` is where the private work dir is
    made and where url-fetcher litter is swept (default: the system temp dir).
    """
    tmp_root = tmp_root or tempfile.gettempdir()
    guard = _SignalGuard()
    workdir = None
    proc = None
    exited_at = None
    existed_before = None
    try:
        guard.install()
        existed_before = _list_names(tmp_root)
        workdir = tempfile.mkdtemp(prefix="selahcue-headless-", dir=tmp_root)
        page = os.path.join(workdir, "page.html")
        out_path = os.path.join(workdir, "chrome.stdout")
        err_path = os.path.join(workdir, "chrome.stderr")
        with open(page, "w", encoding="utf-8") as f:
            f.write(page_html)
        argv = [chrome] + list(flags) + list(CHROME_HARDENING_FLAGS) + ["--dump-dom", "file://" + page]
        popen_kwargs = {"start_new_session": True} if os.name == "posix" else {}
        timed_out = False
        returncode = None
        guard.raise_if_pending()  # told to stop before we started: do not start a browser for nothing
        started = time.time()
        with open(out_path, "wb") as out_f, open(err_path, "wb") as err_f:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f, **popen_kwargs)
            guard.arm()  # `proc` exists from here on, so a signal can safely unwind
            try:
                returncode = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_process_group(proc)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass  # SIGKILLed and still not reaped: nothing more a gate can do
        guard.disarm()
        exited_at = time.time()
        return ChromeRun(
            stdout=_read_text(out_path),
            stderr_tail=_read_tail(err_path, STDERR_TAIL_BYTES),
            returncode=returncode,
            timed_out=timed_out,
            elapsed=exited_at - started,
            pid=proc.pid,
        )
    finally:
        guard.disarm()  # nothing below may be interrupted by a signal
        if proc is not None:
            _best_effort("kill the process group", _kill_process_group, proc)
        if exited_at is None:
            exited_at = time.time()
        if workdir is not None and _best_effort("remove the work dir", _remove_tree, workdir) is False:
            print("WARN: could not remove headless Chrome work dir %s" % workdir, file=sys.stderr)
        _best_effort("sweep url-fetcher litter", _sweep_chrome_litter, tmp_root, existed_before, exited_at)
        guard.restore()
        guard.raise_if_pending()  # a signal that could not interrupt us is honoured, after cleanup


# ---------------------------------------------------------------------------------------------
# Self-test. Runs the REAL `run_headless_chrome` against fake browsers (python scripts), so every
# behaviour above is checked on the code path the gate uses, in a few seconds and without Chrome.
# Each scenario's comment names the defect it guards; every scenario was mutation-checked (the
# edit that must turn it red is in the PR description and on ClickUp 17tnw2b1f32).
# The fake is run as `python <script> <flags...>`, never as an executable file of its own: macOS
# scans each newly created executable on first run (~0.45 s), and a noexec temp dir would make the
# gate red with no Chrome involved.
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
try:
    with open(page_path) as f:
        record("page.html", f.read())
except OSError:
    pass  # a signalled launcher may already have removed its work dir; a browser must outlive that
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
elif KIND == "pass_term_proof_helper":
    # A helper in OUR group that IGNORES SIGTERM: only SIGKILL (the documented signal) removes it.
    record("helper", subprocess.Popen([sys.executable, "-c",
           "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(600)"]).pid)
    emit(PASS)
elif KIND == "ok_probe":
    emit(PASS)
elif KIND == "count_shrink":
    emit(PASS.replace("DONE(3)", "DONE(2)"))
elif KIND == "utf8_edges":
    # stdout: invalid UTF-8 before a complete block. stderr: 4097 bytes of 2-byte characters, so
    # the 4096-byte tail starts in the MIDDLE of a character.
    sys.stdout.buffer.write(b"\\xff\\xfe junk \\x80 bytes\\r\\n")
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(("\\u00e9" * 2048 + "a").encode("utf-8"))
    sys.stderr.buffer.flush()
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
    leak = os.path.join(root, "com.google.Chrome.chrome_chrome_url_fetcher_.NEWLEAK")
    os.makedirs(leak)
    with open(os.path.join(leak, "payload"), "w") as f:
        f.write("x")
    with open(os.path.join(root, ".com.google.Chrome.LIVEFILE"), "w") as f:
        f.write("a live renderer's temp file")
    os.makedirs(os.path.join(root, "scoped_dirKEEP"))
    os.makedirs(os.path.join(root, "com.google.Chrome.some_other_dir_.KEEPME"))
    # A symlink NAMED like the leak, pointing at a directory that must come through untouched.
    os.makedirs(os.path.join(root, "precious"))
    with open(os.path.join(root, "precious", "keep.txt"), "w") as f:
        f.write("do not delete")
    os.symlink(os.path.join(root, "precious"),
               os.path.join(root, "com.google.Chrome.chrome_chrome_url_fetcher_.LINKED"))
    # A url-fetcher dir some OTHER process was still writing to after this browser had exited:
    # its mtime is in the future, which is what "newer than our browser's exit" looks like.
    late = os.path.join(root, "com.google.Chrome.chrome_chrome_url_fetcher_.WRITTENLATER")
    os.makedirs(late)
    with open(os.path.join(late, "payload"), "w") as f:
        f.write("being downloaded")
    future = time.time() + 3600
    os.utime(os.path.join(late, "payload"), (future, future))
    os.utime(late, (future, future))
    # A name that only a loose match accepts: `$` also matches before a trailing newline.
    os.makedirs(os.path.join(root, "com.google.Chrome.chrome_chrome_url_fetcher_.NLDECOY\\n"))
    emit(PASS)
elif KIND == "stderr_flood":
    sys.stderr.write("x" * (3 * 1024 * 1024))
    sys.stderr.flush()
    emit(PASS)
else:
    sys.exit("unknown fake kind " + KIND)
'''


def self_test_supported():
    """The self-test needs POSIX process groups and signals; the gate itself is macOS/Linux only."""
    return os.name == "posix"


def _write_fake_chrome(root):
    """The ONE fake-browser script every scenario shares; it picks its behaviour from the
    FAKE_CHROME_CASE env var. The launcher runs it as `<this python> <script> <flags...>`."""
    path = os.path.join(root, "fake_chrome.py")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(_FAKE_CHROME_SRC)
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
            with open(os.path.join(pid_dir, key)) as f:
                text = f.read().strip()
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
        self.chrome = sys.executable
        self.script = _write_fake_chrome(root)
        self.case_json = json.dumps({"kind": kind, "pid_dir": self.pid_dir, "litter_root": self.tmp_root})

    def run(self, timeout, flags=("--headless=new", "--virtual-time-budget=1000"), html="<html>page</html>",
            default_tmp_root=False):
        """Run the launcher against this case's fake. `default_tmp_root` leaves `tmp_root` unset, as
        the real gate does, by pointing the system temp dir at this case's private one."""
        previous = os.environ.get("FAKE_CHROME_CASE")
        os.environ["FAKE_CHROME_CASE"] = self.case_json
        saved_tempdir = tempfile.tempdir
        if default_tmp_root:
            tempfile.tempdir = self.tmp_root
        try:
            return run_headless_chrome(self.chrome, html, [self.script] + list(flags), timeout,
                                       tmp_root=None if default_tmp_root else self.tmp_root)
        finally:
            tempfile.tempdir = saved_tempdir
            if previous is None:
                del os.environ["FAKE_CHROME_CASE"]
            else:
                os.environ["FAKE_CHROME_CASE"] = previous

    def gate_subprocess(self, preamble="", timeout=120):
        """Start a separate Python that runs the launcher against this case's fake, after running
        `preamble` (hooks that inject a signal at an exact point). Returns the Popen."""
        here = os.path.dirname(os.path.abspath(__file__))
        # The first three lines put the signal dispositions back to the defaults: a child of a
        # process run under `nohup`, or started as a shell background job, would otherwise inherit
        # "ignored" and the scenario would be testing the caller's choice, not the launcher.
        code = ("import os, signal, subprocess, sys\n"
                "signal.signal(signal.SIGINT, signal.default_int_handler)\n"
                "signal.signal(signal.SIGHUP, signal.SIG_DFL)\n"
                "signal.signal(signal.SIGTERM, signal.SIG_DFL)\n"
                "sys.path.insert(0, %r)\n"
                "import headless_chrome as h\n"
                "%s\n"
                "h.run_headless_chrome(%r, '<html></html>', [%r], timeout=%d, tmp_root=%r)\n"
                % (here, preamble, self.chrome, self.script, timeout, self.tmp_root))
        return subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=dict(os.environ, FAKE_CHROME_CASE=self.case_json))

    def leftovers(self, ignore=()):
        return sorted(n for n in os.listdir(self.tmp_root) if n not in ignore)


def self_test(verdict=None, expected_checks=3):
    """Check the launcher against fake browsers. Returns a list of problems (empty = all good).

    `verdict(run, expected_checks) -> exit code`, when given (the gate passes its own), is also
    asserted per scenario, so "exits 0 / 1 / 2 / 4" is proven through the gate's real mapping.
    Its printing is swallowed: a fake's `FAIL:` lines must never reach the gate's log. The caller
    must check `self_test_supported()` first: there is nothing to run without POSIX processes.
    """
    problems = []
    root = tempfile.mkdtemp(prefix="selahcue-headless-selftest-")
    spawned = []  # exact PIDs of every helper a fake started: killed at the end whatever happened
    gates = []    # every separate Python this test starts: killed at the end whatever happened
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

    def start_gate(case, preamble="", timeout=120):
        gate = case.gate_subprocess(preamble, timeout)
        gates.append(gate)
        return gate

    try:
        # 0. Pure helpers. A negative status used to print bare (`-11`).
        if describe_exit(-11) != "-11 (killed by SIGSEGV)" or describe_exit(7) != "7" \
                or describe_exit(None) != "none (never exited)":
            problems.append("describe_exit: got %r / %r / %r" % (describe_exit(-11), describe_exit(7),
                                                                  describe_exit(None)))

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
                            "after it has printed its result (17tnw2b1f32, 7 of 8 runs hung) - do not add it "
                            "back without re-measuring")
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

        # 2a. The documented kill is SIGKILL: a helper that ignores SIGTERM must still be gone.
        case = _Case(root, "pass_term_proof_helper")
        case.run(timeout=12)
        helpers = pids_of(case, "helper")
        if "helper" not in helpers:
            problems.append("SIGTERM-proof helper: the fake never started it, the scenario proves nothing")
        elif not _wait_dead(helpers["helper"]):
            problems.append("SIGTERM-proof helper: a helper ignoring SIGTERM outlived the run "
                            "(the group kill must be SIGKILL)")

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

        # The contract is "either direction": a floor (`>`) would pass the growth case above.
        case = _Case(root, "count_shrink")
        expect_code("check-count shrink", case.run(timeout=12), 4)

        case = _Case(root, "crash")
        run = case.run(timeout=12)
        if run.returncode != 7 or "boom: renderer crashed" not in run.stderr_tail:
            problems.append("crash: exit code / stderr were not captured (rc=%r, stderr=%r)"
                            % (run.returncode, run.stderr_tail))
        expect_code("crashed browser", run, 2)
        # What an operator reads on an infra failure: Chrome's exit code and its stderr tail.
        if verdict is not None:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                verdict(run, expected_checks)
            if "chrome exit code: 7" not in buf.getvalue() or "boom: renderer crashed" not in buf.getvalue():
                problems.append("crash message: the gate did not print Chrome's exit code and stderr "
                                "tail (got %r)" % buf.getvalue()[:300])

        # 8. AC3 on macOS: the url-fetcher dir THIS run created is swept; nothing else is. Must all
        #    survive: a dir that existed before the launch, a live renderer's `.com.google.Chrome.*`
        #    file, an unrelated `scoped_dir*` / `com.google.Chrome.*` dir, a SYMLINK named like the
        #    leak (and the directory it points at, with its file), and a url-fetcher dir some other
        #    process was still writing to after our browser had exited.
        case = _Case(root, "litter")
        preexisting = "com.google.Chrome.chrome_chrome_url_fetcher_.PREEXIST"
        os.makedirs(os.path.join(case.tmp_root, preexisting))
        run = case.run(timeout=12)
        want = sorted([preexisting, ".com.google.Chrome.LIVEFILE", "scoped_dirKEEP",
                       "com.google.Chrome.some_other_dir_.KEEPME", "precious",
                       "com.google.Chrome.chrome_chrome_url_fetcher_.LINKED",
                       "com.google.Chrome.chrome_chrome_url_fetcher_.WRITTENLATER",
                       "com.google.Chrome.chrome_chrome_url_fetcher_.NLDECOY\n"])
        if case.leftovers() != want:
            problems.append("litter sweep: expected exactly %s to remain in the temp root, found %s"
                            % (want, case.leftovers()))
        if not os.path.isfile(os.path.join(case.tmp_root, "precious", "keep.txt")):
            problems.append("litter sweep: followed a symlink and deleted what it pointed at")
        expect_code("litter", run, 0)

        # 8a. A temp dir that cannot be LISTED (write-only $TMPDIR) must not fail the launch: the
        #     old gate passed there. Without the listing there is nothing to attribute litter to.
        case = _Case(root, "pass_group_helper", tag="unlistable")
        real_listdir = os.listdir

        def deny_listing(path=".", *args, **kwargs):
            if os.fspath(path) == case.tmp_root:
                raise PermissionError(13, "Permission denied", path)
            return real_listdir(path, *args, **kwargs)

        os.listdir = deny_listing
        try:
            run = case.run(timeout=12)
        except Exception as exc:  # noqa: BLE001
            run = None
            problems.append("unlistable temp dir: the launch failed with %r" % (exc,))
        finally:
            os.listdir = real_listdir
        pids_of(case, "helper")
        if run is not None and "RESULTS" not in run.stdout:
            problems.append("unlistable temp dir: the result was lost")
        if case.leftovers():
            problems.append("unlistable temp dir: the run left %s" % case.leftovers())

        # 8b. The caller's temp dir is the system one (what the gate really passes: tmp_root=None).
        case = _Case(root, "pass_group_helper", tag="default_tmp_root")
        run = case.run(timeout=12, html=page_html, default_tmp_root=True)
        pids_of(case, "helper")
        if "RESULTS" not in run.stdout:
            problems.append("default tmp_root: the launcher did not return the result")
        if case.leftovers():
            problems.append("default tmp_root: the run left %s in the default temp dir" % case.leftovers())
        try:
            with open(os.path.join(case.pid_dir, "argv.json")) as f:
                page_url = json.loads(f.read())[-1]
        except (OSError, ValueError, IndexError):
            page_url = ""
        if not page_url.startswith("file://" + case.tmp_root + os.sep):
            problems.append("default tmp_root: the work dir was not made in the system temp dir (page %r)" % page_url)

        # 8c. One failing cleanup step must not skip the others or replace the result.
        case = _Case(root, "pass_group_helper", tag="cleanup_step_fails")
        real_kill = globals()["_kill_process_group"]

        def failing_kill(proc):
            raise RuntimeError("injected: the kill step blew up")

        globals()["_kill_process_group"] = failing_kill
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                run = case.run(timeout=12)
        except Exception as exc:  # noqa: BLE001
            run = None
            problems.append("cleanup step failure: the launcher raised %r instead of finishing its cleanup" % (exc,))
        finally:
            globals()["_kill_process_group"] = real_kill
        pids_of(case, "helper")  # the injected failure left it alive; the final cleanup kills it
        if run is not None and "RESULTS" not in run.stdout:
            problems.append("cleanup step failure: the result was lost")
        if case.leftovers():
            problems.append("cleanup step failure: later steps were skipped, left %s" % case.leftovers())

        # 9. Bounded memory: 3 MB of stderr must cost at most 4096 bytes of what we hold. The number
        #    is spelled out here so raising STDERR_TAIL_BYTES is a decision made in review.
        case = _Case(root, "stderr_flood")
        run = case.run(timeout=30)
        if len(run.stderr_tail) > 4096:
            problems.append("stderr flood: kept %d bytes of stderr, the cap is 4096" % len(run.stderr_tail))
        expect_code("stderr flood", run, 0)

        # 9a. Undecodable bytes must never become a traceback: junk before the block on stdout, and
        #     a stderr tail whose first byte falls in the middle of a character.
        case = _Case(root, "utf8_edges")
        run = case.run(timeout=12)
        if "RESULTS" not in run.stdout or len(run.stderr_tail) == 0:
            problems.append("utf8 edges: invalid UTF-8 / a mid-character stderr cut lost the result or the stderr")
        expect_code("utf8 edges", run, 0)

        # 9b. The caller's signal handlers are put back after a run (a later signal in the caller
        #     must not unwind through OUR handler).
        guarded = [getattr(signal, n) for n in _SignalGuard._NAMES if hasattr(signal, n)]
        originals = {sig: signal.getsignal(sig) for sig in guarded}
        sentinel = lambda signum, frame: None  # noqa: E731 - a distinct handler to be put back
        for sig in guarded:
            signal.signal(sig, sentinel)
        try:
            _Case(root, "ok_probe").run(timeout=12)
            for sig in guarded:
                if signal.getsignal(sig) is not sentinel:
                    problems.append("signal handlers: %s was not put back after the run" % signal.Signals(sig).name)
        finally:
            for sig, handler in originals.items():
                signal.signal(sig, handler)

        # 10. Killing the GATE must unwind through the same cleanup, whichever way it is told to
        #     stop: the browser lives in its own session, so it no longer shares the gate's fate on
        #     its own. SIGHUP is what a closed terminal sends (Cody, Quinn: it used to orphan the
        #     browser and leave the work dir). A SECOND signal lands inside the cleanup (injected
        #     deterministically at the work-dir removal): the cleanup must still finish (Shadow).
        #     The three gates run side by side; each one's fake is up before anything is signalled.
        signal_cases = [("SIGTERM", signal.SIGTERM, (128 + signal.SIGTERM,)),
                        ("SIGHUP", signal.SIGHUP, (128 + signal.SIGHUP,)),
                        ("SIGINT", signal.SIGINT, (130, -signal.SIGINT))]
        started_gates = []
        for sig_name, sig, want_status in signal_cases:
            case = _Case(root, "hang", tag="signal_" + sig_name)
            preamble = ("real = h._remove_tree\n"
                        "def hooked(path):\n"
                        "    os.kill(os.getpid(), %d)\n"
                        "    return real(path)\n"
                        "h._remove_tree = hooked\n" % int(sig))
            started_gates.append((sig_name, sig, want_status, case, start_gate(case, preamble)))
        for sig_name, sig, want_status, case, gate in started_gates:
            helpers = {}
            if _read_pid(case.pid_dir, "helper", seconds=30) is not None:
                helpers = pids_of(case, "self", "helper")
            if len(helpers) != 2:
                problems.append("%s: the fake never started, the scenario proves nothing" % sig_name)
                continue
            gate.send_signal(sig)
            try:
                status = gate.wait(timeout=30)
            except subprocess.TimeoutExpired:
                status = None
                problems.append("%s: the gate did not exit after the signal" % sig_name)
            if status is not None and status not in want_status:
                problems.append("%s: the gate exited %r instead of unwinding with %s" % (sig_name, status, want_status))
            for key, label in (("self", "browser"), ("helper", "helper in its group")):
                if not _wait_dead(helpers[key]):
                    problems.append("%s: the %s outlived the signalled gate" % (sig_name, label))
            if case.leftovers():
                problems.append("%s: the signalled gate left %s in its temp root (a second signal during "
                                "cleanup must not abandon it)" % (sig_name, case.leftovers()))

        # 10a. A signal that lands while the browser is being CREATED (`Popen` has made the child but
        #      has not returned) must not orphan it: the handler used to unwind with `proc` still
        #      None, so nobody killed the browser (Quinn, reproduced deterministically and as a
        #      flaky self-test at ~10x CPU overload). Injected by signalling from inside `Popen`.
        case = _Case(root, "hang", tag="signal_in_popen")
        preamble = ("real = subprocess.Popen\n"
                    "class SignalledPopen(real):\n"
                    "    def __init__(self, *a, **k):\n"
                    "        real.__init__(self, *a, **k)\n"
                    "        open(%r, 'w').write(str(self.pid))\n"
                    "        os.kill(os.getpid(), signal.SIGTERM)\n"
                    "subprocess.Popen = SignalledPopen\n" % os.path.join(case.pid_dir, "popen_pid"))
        gate = case.gate_subprocess(preamble, timeout=120)
        gates.append(gate)
        try:
            status = gate.wait(timeout=15)  # the browser never exits by itself: only an unwind ends this
        except subprocess.TimeoutExpired:
            status = None
            problems.append("signal during launch: the gate did not unwind promptly (the held signal was "
                            "never delivered once the browser existed)")
        pids_of(case, "self", "helper")
        browser = _read_pid(case.pid_dir, "popen_pid", seconds=5)
        if browser is None:
            problems.append("signal during launch: the browser was never created, the scenario proves nothing")
        else:
            spawned.append(browser)
            if status != 128 + signal.SIGTERM:
                problems.append("signal during launch: the gate exited %r instead of unwinding with %d"
                                % (status, 128 + signal.SIGTERM))
            if not _wait_dead(browser):
                problems.append("signal during launch: the browser it had just started was orphaned")
            if case.leftovers():
                problems.append("signal during launch: left %s in its temp root" % case.leftovers())

        # 10c. A signal that lands right after the work dir was CREATED must not leak it (the
        #      handler used to be installed after `mkdtemp`, outside the `try`, so this killed the
        #      gate with the dir still on disk and no handler to unwind). No browser is started.
        case = _Case(root, "hang", tag="signal_after_mkdtemp")
        preamble = ("real_mkdtemp = h.tempfile.mkdtemp\n"
                    "def mkdtemp_then_signal(*a, **k):\n"
                    "    path = real_mkdtemp(*a, **k)\n"
                    "    os.kill(os.getpid(), signal.SIGTERM)\n"
                    "    return path\n"
                    "h.tempfile.mkdtemp = mkdtemp_then_signal\n")
        gate = start_gate(case, preamble, timeout=20)
        try:
            status = gate.wait(timeout=30)
        except subprocess.TimeoutExpired:
            status = None
        if status != 128 + signal.SIGTERM:
            problems.append("signal after mkdtemp: the gate exited %r instead of unwinding with %d"
                            % (status, 128 + signal.SIGTERM))
        if case.leftovers():
            problems.append("signal after mkdtemp: the work dir leaked: %s" % case.leftovers())

        # 10b. A signal that arrives ONLY during cleanup is not swallowed: it is honoured once the
        #      cleanup has finished (the run itself had completed normally).
        case = _Case(root, "pass_group_helper", tag="signal_in_cleanup")
        preamble = ("real = h._remove_tree\n"
                    "def hooked(path):\n"
                    "    os.kill(os.getpid(), signal.SIGTERM)\n"
                    "    return real(path)\n"
                    "h._remove_tree = hooked\n")
        gate = start_gate(case, preamble, timeout=20)
        try:
            status = gate.wait(timeout=30)
        except subprocess.TimeoutExpired:
            status = None
        pids_of(case, "helper")
        if status != 128 + signal.SIGTERM:
            problems.append("signal during cleanup: the gate exited %r, the signal was swallowed instead of "
                            "being honoured after the cleanup" % (status,))
        if case.leftovers():
            problems.append("signal during cleanup: left %s in its temp root" % case.leftovers())

        # 10d. A signal the caller IGNORES on purpose (`nohup` ignores SIGHUP) stays ignored: the
        #      launcher must not replace that choice with its own unwind.
        case = _Case(root, "pass_group_helper", tag="signal_ignored")
        preamble = ("signal.signal(signal.SIGHUP, signal.SIG_IGN)\n"
                    "real = h._remove_tree\n"
                    "def hooked(path):\n"
                    "    os.kill(os.getpid(), signal.SIGHUP)\n"
                    "    return real(path)\n"
                    "h._remove_tree = hooked\n")
        gate = start_gate(case, preamble, timeout=20)
        try:
            status = gate.wait(timeout=30)
        except subprocess.TimeoutExpired:
            status = None
        pids_of(case, "helper")
        if status != 0:
            problems.append("ignored signal: the gate exited %r after a SIGHUP it had chosen to ignore" % (status,))
        if case.leftovers():
            problems.append("ignored signal: left %s in its temp root" % case.leftovers())
    finally:
        for gate in gates:
            if gate.poll() is None:
                gate.kill()
                gate.wait()
        for pid in spawned:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(root, ignore_errors=True)
    return problems


def main():
    if not self_test_supported():
        print("SKIP: headless-launch self-test not run: it needs POSIX process groups and signals "
              "(this gate is supported on macOS and Linux only)")
        return 0
    problems = self_test()
    for problem in problems:
        print("FAIL: headless-launch self-test (17tnw2b1f32) - " + problem)
    if problems:
        return 1
    print("PASS: headless-launch self-test (17tnw2b1f32)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
