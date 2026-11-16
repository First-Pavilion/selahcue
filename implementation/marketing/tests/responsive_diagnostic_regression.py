#!/usr/bin/env python3
"""Real-WebKit observation checks; synthetic controls are not app reproduction."""
import contextlib
import copy
import gc
import importlib.util
import io
import json
import sys
import subprocess
import tempfile
import types
from pathlib import Path
import unittest
import weakref
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'responsive_sweep', Path(__file__).resolve().parents[1] / 'scripts/responsive_sweep.py')
sweep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sweep)


class InertPlaywrightError(Exception):
    pass


class InertPlaywrightTimeout(InertPlaywrightError):
    pass


def inert_playwright_api():
    api = types.ModuleType('playwright.sync_api')
    api.Error = InertPlaywrightError
    api.TimeoutError = InertPlaywrightTimeout
    return api


PROBE_STATE = dict(elapsedMs=10078, totalPolls=2, lastResult=False, stopped=False,
                   earlyTimerEntries=0, periodicTimerEntries=0, lateTimerEntries=0)

CHRONOLOGY_PREFIX = 'WEBKIT_HOST_CHRONOLOGY '
PROBE_PREFIX = 'WEBKIT_SETTLE_PROBE '
FIRST_DOCUMENT = '0123456789abcdef0123456789abcdef'
OTHER_DOCUMENT = 'fedcba9876543210fedcba9876543210'


def protocol_record(kind, document=FIRST_DOCUMENT, **fields):
    return dict(version=1, kind=kind, document=document, **fields)


def probe_record(document=FIRST_DOCUMENT):
    return protocol_record('probe', document, outcome='snapshot', state=PROBE_STATE, gateResult=False)


def protocol_text(record):
    return PROBE_PREFIX + json.dumps(record, separators=(',', ':'))


# The VM supplies only host/browser primitives. The init script, actual poll and
# failure probe are the production expressions shipped to Playwright.
NODE_PROBE_DRIVER = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const { init, poll, probe, scenarios } = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = scenarios.map((scenario) => {
  const lines = [];
  const context = vm.createContext({
    crypto: webcrypto,
    performance: { now: () => 0 },
    console: { debug(line) { lines.push(line); } },
    document: {
      readyState: 'complete', visibilityState: 'visible',
      getAnimations: () => [], querySelector: () => null,
    },
    addEventListener() {}, setTimeout: () => 1, clearTimeout() {},
    requestAnimationFrame: () => 1, cancelAnimationFrame() {},
  });
  vm.runInContext('window = self = globalThis; top = window;', context);
  vm.runInContext(init, context);
  if (scenario.poll) {
    vm.runInContext('(' + poll + ')()', context);
    vm.runInContext('(' + poll + ')()', context);
  }
  vm.runInContext(scenario.setup, context);
  let error = null;
  try { vm.runInContext('(' + probe + ')("WEBKIT_SETTLE_STATE ")', context); }
  catch (exception) { error = exception.message; }
  const stateAfterProbe = scenario.readStateAfterProbe
    ? vm.runInContext('window.__selahcueSettleState()', context)
    : undefined;
  return { records: lines.filter(line => line.startsWith('WEBKIT_SETTLE_PROBE ')),
           error, gateReads: context.gateReads, stateAfterProbe };
});
process.stdout.write(JSON.stringify(output));
"""


def run_protocol_js(scenarios):
    inputs = json.dumps(dict(init=sweep.SETTLE_DIAGNOSTIC_JS, poll=sweep.OBSERVED_SETTLE_JS,
                             probe=sweep.SETTLE_STATE_PROBE_JS, scenarios=scenarios)).encode()
    # Set the output cap in the child before exec. One combined bounded file avoids
    # pipe backpressure and prevents an erroneous producer exhausting capture memory.
    limit = 256 * 1024
    launcher = (
        "import os, resource, sys; "
        "limit = int(sys.argv[1]); resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit)); "
        "os.execvp('node', ['node', '-e', sys.argv[2]])"
    )
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(
            [sys.executable, '-I', '-B', '-c', launcher, str(limit), NODE_PROBE_DRIVER],
            input=inputs, stdout=output, stderr=subprocess.STDOUT, timeout=5,
        )
        output.seek(0)
        captured = output.read(limit)
    if result.returncode != 0:
        raise AssertionError(f'Node diagnostic control exited {result.returncode}: {captured[:512]!r}')
    return json.loads(captured)


class InertTimeoutPage:
    """Playwright boundary adapter for a single timed-out cell."""

    def __init__(self, first_document, before, during, faults):
        self.first_document, self.before, self.during = first_document, before, during
        self.faults = faults
        self.listeners = {}
        self.main_frame = types.SimpleNamespace(parent_frame=None)
        self.child_frame = types.SimpleNamespace(parent_frame=self.main_frame)
        self.clock = 0
        self.utc_offset = 1000
        self.waits = []

    def on(self, event, callback):
        if (event + '-registration' in self.faults
                or ('registration' in self.faults and event == 'framenavigated')):
            raise RuntimeError('private-listener-registration')
        self.listeners.setdefault(event, []).append(callback)

    def remove_listener(self, event, callback):
        self.listeners[event].remove(callback)
        if 'removal' in self.faults:
            raise RuntimeError('private-listener-removal')

    def dispatch(self, event, *args):
        for callback in tuple(self.listeners.get(event, ())):
            callback(*args)

    def emit(self, events):
        for event in events:
            if event == 'main-navigation':
                self.dispatch('framenavigated', self.main_frame)
            elif event == 'subframe-navigation':
                self.dispatch('framenavigated', self.child_frame)
            elif event in ('close', 'crash'):
                self.dispatch(event)
            elif event is None:
                self.dispatch('console', UnreadableConsoleMessage())
            else:
                self.dispatch('console', types.SimpleNamespace(type='debug', text=event))

    def add_init_script(self, *args):
        pass

    def goto(self, *args, **kwargs):
        self.emit(('main-navigation', 'subframe-navigation'))

    def wait_for_selector(self, *args, **kwargs):
        pass

    def wait_for_function(self, expression, **kwargs):
        self.waits.append((expression, kwargs))
        if expression == sweep.OBSERVED_SETTLE_JS:
            if self.first_document:
                self.emit((protocol_text(protocol_record('document', self.first_document)),))
            self.emit(self.before)
            # Simulate delivery after the existing generic observer cutoff without waiting.
            self.clock = 13
            if 'utc-step' in self.faults:
                self.utc_offset = 500
            if 'late-crash' in self.faults:
                self.dispatch('crash')
                self.clock = 14
                if 'duplicate-crash' in self.faults:
                    self.dispatch('crash')
            raise InertPlaywrightTimeout('ORIGINAL 10000ms failure')
        self.emit(self.during)
        raise InertPlaywrightError('private-error-channel-without-marker')


class UnreadableConsoleMessage:
    type = 'debug'

    @property
    def text(self):
        raise RuntimeError('private-console-read')


def run_receipt_main(first_document=FIRST_DOCUMENT, before=(), during=(), faults=()):
    page = InertTimeoutPage(first_document, before, during, faults)
    api = inert_playwright_api()
    context = types.SimpleNamespace(new_page=lambda: page)
    browser = types.SimpleNamespace(new_context=lambda **kwargs: context)
    disconnect = []
    def register_disconnect(event, callback):
        if 'disconnect-registration' in faults:
            raise RuntimeError('private-disconnect-registration')
        if event != 'disconnected':
            raise AssertionError(event)
        disconnect.append(callback)

    browser.on = register_disconnect

    @contextlib.contextmanager
    def playwright():
        try:
            yield types.SimpleNamespace(webkit=types.SimpleNamespace(launch=lambda: browser))
        finally:
            if 'unwind' in faults:
                page.clock = 16
                page.dispatch('close')
                page.clock = 17
                for callback in disconnect:
                    callback(browser)
                page.clock = 18

    api.sync_playwright = playwright
    server = types.SimpleNamespace(server_address=('127.0.0.1', 1234),
                                   serve_forever=lambda: None, shutdown=lambda: None)
    def time_ns():
        if 'clock-read' in faults and page.clock == 13:
            raise RuntimeError('private-clock')
        return (page.utc_offset + page.clock) * 10**9

    bindings = dict(Server=lambda *args: server,
                    threading=types.SimpleNamespace(Thread=lambda **kwargs:
                                                    types.SimpleNamespace(start=lambda: None)),
                    time=types.SimpleNamespace(
                        monotonic=lambda: page.clock,
                        monotonic_ns=lambda: page.clock * 10**9,
                        time_ns=time_ns,
                    ),
                    emit_browser_identity=lambda *args: None, install_stubs=lambda *args: None)
    if 'output' in faults:
        def refuse_line(_line):
            raise OSError('private-diagnostic-output')
        bindings['emit_diagnostic_line'] = refuse_line
    output = io.StringIO()
    with patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'),
                                  'playwright.sync_api': api}), \
            patch.dict(sweep.__dict__, bindings), \
            patch.object(Path, 'exists', return_value=True), \
            patch.object(sys, 'argv', ['sweep', '--engine', 'webkit', '--routes', '/signin',
                                       '--widths', '1024']), \
            contextlib.redirect_stdout(output):
        code = sweep.main()
    return code, output.getvalue(), page.waits


class InertSweepPage(InertTimeoutPage):
    def __init__(self, driver, ordinal, width):
        super().__init__(None, (), (), ())
        self.driver, self.ordinal, self.width = driver, ordinal, width

    def add_init_script(self, script):
        self.driver.record('page-init', script)

    def goto(self, url, **kwargs):
        self.driver.record('goto', url, kwargs)
        super().goto()
        if self.ordinal > 1 and self.driver.cell_refs:
            # Deliver old-page callbacks while the new page's original cell is active.
            self.driver.pages[-2].dispatch('crash')
            cell = self.driver.cell_refs[-1]()
            if cell is not None:
                self.driver.active_crashes_after_old_callbacks.append(cell.record['crash']['seen'])

    def wait_for_selector(self, selector, **kwargs):
        self.driver.record('selector', selector, kwargs)

    def wait_for_function(self, expression, **kwargs):
        self.driver.record('wait', expression, kwargs)
        if expression == sweep.OBSERVED_SETTLE_JS or expression == sweep.SETTLE_JS:
            if self.ordinal in self.driver.timeouts:
                raise InertPlaywrightTimeout('ORIGINAL 10000ms failure')
            return
        if expression != sweep.SETTLE_STATE_PROBE_JS:
            raise AssertionError('unexpected script')
        if self.ordinal in self.driver.timeouts:
            raise InertPlaywrightError('private-fake-probe')
        raise InertPlaywrightError('WEBKIT_SETTLE_STATE ' + json.dumps(PROBE_STATE))

    def evaluate(self, expression, *args):
        self.driver.record('evaluate', expression, args)
        if expression == sweep.PAGE_JS:
            if self.ordinal in self.driver.geometry_errors:
                raise self.driver.original
            mode, gutter = ('mobile', 20) if self.width < 768 else (
                ('tablet', 48) if self.width < 1200 else ('desktop', 24))
            return dict(scrollWidth=self.width, vw=self.width, clipped=[], edge=[], mode=mode,
                        gutterToken=f'{gutter}px', fullBleed=[], smallInputs=[], unfocusableScrollers=[],
                        pricingFirstIsPopular=None, mainTextLength=1 if self.ordinal in self.driver.assertions else 50)
        if expression == sweep.IS_MOBILE_JS:
            return self.width < 768
        if expression == sweep.NAV_STATE_JS:
            return dict(hasHeader=True, toggleVisible=self.width < 768, desktopNavVisible=self.width >= 768)
        if expression == sweep.TOUCH_JS:
            return []
        if expression.startswith('({header:'):
            return dict(header=False, footer=False)
        if 'How it works' in expression:
            return [None]
        raise AssertionError('unexpected script')

    def close(self):
        self.driver.record('page-close')
        self.dispatch('close')
        if self.ordinal in self.driver.page_close_errors:
            raise self.driver.original


class InertSweep:
    """Drive the real sweep and keep every fake page/listener alive through teardown."""

    def __init__(self, assertions=(), timeouts=(), geometry_errors=(), page_close_errors=(),
                 fail_at=None, behavior_disconnect=False):
        self.assertions, self.timeouts = assertions, timeouts
        self.geometry_errors, self.page_close_errors = geometry_errors, page_close_errors
        self.fail_at, self.behavior_disconnect = fail_at, behavior_disconnect
        self.original = RuntimeError('private-original-exception')
        self.pages, self.actions, self.cell_refs, self.live_counts = [], [], [], []
        self.unwind_live_counts = []
        self.active_crashes_after_old_callbacks = []
        self.output = io.StringIO()
        self.clock = 0
        self.disconnect = None

    def record(self, operation, *args):
        self.actions.append((operation, *args))
        self.clock += 1
        if operation == self.fail_at:
            raise self.original

    def begin_cell(self, observer, ordinal, route_index, width_index):
        cell = self.real_begin_cell(observer, ordinal, route_index, width_index)
        self.cell_refs.append(weakref.ref(cell))
        self.live_counts.append(sum(ref() is not None for ref in self.cell_refs))
        return cell

    def on(self, event, callback):
        if event != 'disconnected' or self.disconnect is not None:
            raise AssertionError(event)
        self.disconnect = callback

    def new_context(self, **kwargs):
        self.record('context', kwargs)

        def new_page():
            self.record('new-page')
            page = InertSweepPage(self, len(self.pages) + 1, kwargs['viewport']['width'])
            self.pages.append(page)
            return page

        return types.SimpleNamespace(new_page=new_page, close=lambda: self.record('context-close'),
                                     add_init_script=lambda script: self.record('context-init', script))

    def browser_close(self):
        self.record('browser-close')
        if self.disconnect:
            self.disconnect(self)

    def launch(self):
        self.record('launch')
        return types.SimpleNamespace(on=self.on, new_context=self.new_context, close=self.browser_close)

    @contextlib.contextmanager
    def playwright(self):
        self.record('playwright-enter')
        try:
            yield types.SimpleNamespace(webkit=types.SimpleNamespace(launch=self.launch),
                                        chromium=types.SimpleNamespace(launch=self.launch))
        finally:
            self.record('playwright-unwind')
            self.unwind_live_counts.append(sum(ref() is not None for ref in self.cell_refs))
            if self.pages:
                self.pages[-1].dispatch('close')
            if self.disconnect:
                self.disconnect(self)
            self.record('playwright-exit')

    def behavior(self, name):
        def check(*args):
            self.record(name)
            if name == 'check_nav_sheet' and self.behavior_disconnect and self.disconnect is not None:
                self.disconnect(self)
        return check

    def run(self, *args, engine='webkit', faults=None):
        api = inert_playwright_api()
        api.sync_playwright = self.playwright
        server = types.SimpleNamespace(server_address=('127.0.0.1', 1234),
                                       serve_forever=lambda: None,
                                       shutdown=lambda: self.record('shutdown'))
        bindings = dict(Server=lambda *args: server, REQUIRE=True,
                        threading=types.SimpleNamespace(Thread=lambda **kwargs:
                                                        types.SimpleNamespace(start=lambda: self.record('server-start'))),
                        time=types.SimpleNamespace(monotonic=lambda: self.clock / 1000,
                                                   monotonic_ns=lambda: self.clock * 10**6,
                                                   time_ns=lambda: (1000 + self.clock) * 10**6),
                        emit_browser_identity=lambda *args: self.record('identity'),
                        install_stubs=lambda *args: self.record('stubs'))
        for name in ('check_nav_sheet', 'check_boundaries', 'check_overlays', 'check_reduced_motion',
                     'check_footer', 'check_signed_in_nav'):
            bindings[name] = self.behavior(name)
        self.real_begin_cell = sweep.SweepChronology.begin_cell
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sweep.SweepChronology, 'begin_cell',
                                            lambda observer, *args: self.begin_cell(observer, *args)))
            for owner, name, replacement in faults or ():
                stack.enter_context(patch.object(owner, name, replacement))
            stack.enter_context(patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'),
                                                         'playwright.sync_api': api}))
            stack.enter_context(patch.dict(sweep.__dict__, bindings))
            stack.enter_context(patch.object(Path, 'exists', return_value=True))
            stack.enter_context(patch.object(sys, 'argv', ['sweep', '--engine', engine, *args]))
            stack.enter_context(contextlib.redirect_stdout(self.output))
            return sweep.main()


class HostChronologyInertRegression(unittest.TestCase):
    def terminal(self, output):
        lines = [line for line in output.splitlines(keepends=True) if line.startswith(CHRONOLOGY_PREFIX)]
        self.assertEqual(len(lines), 1, output)
        self.assertLessEqual(len(lines[0].encode('ascii')), 4096)
        return json.loads(lines[0].removeprefix(CHRONOLOGY_PREFIX))

    def test_late_timeout_records_first_receipts_through_playwright_unwind(self):
        code, output, waits = run_receipt_main(faults=('late-crash', 'unwind'))
        self.assertEqual(code, 2)
        self.assertEqual(waits, [
            (sweep.OBSERVED_SETTLE_JS, {'timeout': 10000}),
            (sweep.SETTLE_STATE_PROBE_JS, {'arg': 'WEBKIT_SETTLE_STATE ', 'timeout': 1000, 'polling': 100}),
        ])
        original = output.splitlines()[:3]
        self.assertEqual(original[0], 'INFRA webkit 1024px /signin: ORIGINAL 10000ms failure')
        self.assertTrue(original[1].startswith('WEBKIT_SETTLE_TRACE '))
        self.assertTrue(original[2].startswith('WEBKIT_SETTLE_STATE '))
        self.assertEqual(json.loads(original[1].split(' ', 1)[1])['outcome'], 'infra')
        self.assertEqual(json.loads(original[2].split(' ', 1)[1])['capture'], 'after-timeout')
        terminal = [line for line in output.splitlines() if line.startswith(CHRONOLOGY_PREFIX)]
        self.assertEqual(len(terminal), 1, 'expected one terminal host chronology after Playwright unwind')
        receipt = json.loads(terminal[0].removeprefix(CHRONOLOGY_PREFIX))
        self.assertEqual(receipt['outcome'], 'infra_failure')
        self.assertEqual(receipt['planned_cells'], 1)
        cell = receipt['failed_cell']
        self.assertEqual((cell['ordinal'], cell['route_index'], cell['width_index'], cell['kind']),
                         (1, 20, 4, 'infra'))
        self.assertIsNone(cell['page_close_start'])

        def at(seconds):
            return dict(utc_us=(1000 + seconds) * 10**6,
                        mono_before_us=seconds * 10**6, mono_after_us=seconds * 10**6)

        for name, second in (('cell_start', 0), ('settle_start', 0),
                             ('exception_catch', 14), ('probe_start', 14)):
            self.assertEqual(cell[name], at(second))
        self.assertEqual(cell['crash'], dict(armed=True, seen=True, stamp=at(13)))
        self.assertEqual(cell['close'], dict(armed=True, seen=True, stamp=at(16)))
        self.assertEqual(receipt['disconnect'], dict(armed=True, seen=True, active_ordinal=1, stamp=at(17)))
        self.assertEqual(receipt['sweep'], dict(sweep_start=at(0), browser_ready=at(0),
                                                teardown_start=at(14), teardown_end=at(18)))


    def test_failed_first_clock_and_wall_clock_step_never_reorder_or_replace_crash(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                faults = ('late-crash', 'unwind', 'duplicate-crash', 'utc-step')
                code, output, _ = run_receipt_main(faults=faults + (('clock-read',) if failed else ()))
                self.assertEqual(code, 2)
                receipt = self.terminal(output)
                cell = receipt['failed_cell']
                crash = cell['crash']
                self.assertTrue(crash['seen'])
                self.assertIs(receipt['observer_errors']['clock'], failed)
                if failed:
                    self.assertIsNone(crash['stamp'])
                else:
                    self.assertEqual(crash['stamp']['mono_before_us'], 13_000_000)
                    self.assertLess(crash['stamp']['utc_us'], cell['settle_start']['utc_us'])
                    self.assertLess(cell['settle_start']['mono_after_us'], crash['stamp']['mono_before_us'])
                    self.assertLess(crash['stamp']['mono_after_us'], cell['exception_catch']['mono_before_us'])

    def test_host_clock_samples_bracket_and_reject_invalid_values(self):
        cases = (
            ((1001, 1_999_999, 2001), dict(utc_us=1999, mono_before_us=1, mono_after_us=2)),
            ((2000, 1000, 1000), None),
            ((True, 1000, 1000), None),
            ((0, float('nan'), 0), None),
            ((0, -1, 0), None),
            ((0, 9_007_199_254_740_992_000, 0), None),
        )
        for values, expected in cases:
            with self.subTest(values=values):
                before, utc, after = values
                reads = []
                monos = iter((before, after))

                def mono():
                    reads.append('monotonic')
                    return next(monos)

                def wall():
                    reads.append('utc')
                    return utc

                with patch.object(sweep, 'time', types.SimpleNamespace(monotonic_ns=mono, time_ns=wall)):
                    self.assertEqual(sweep.sample_host_stamp(), expected)
                self.assertEqual(reads, ['monotonic', 'utc', 'monotonic'])

    def test_lifecycle_registration_failures_are_independent(self):
        for failing in ('crash', 'close', 'disconnect'):
            with self.subTest(failing=failing):
                code, output, _ = run_receipt_main(faults=('late-crash', 'unwind', failing + '-registration'))
                self.assertEqual(code, 2)
                receipt = self.terminal(output)
                self.assertTrue(receipt['observer_errors']['registration'])
                for kind, event in (('crash', receipt['failed_cell']['crash']),
                                    ('close', receipt['failed_cell']['close']),
                                    ('disconnect', receipt['disconnect'])):
                    self.assertIs(event['armed'], kind != failing)
                    self.assertIs(event['seen'], kind != failing)
                    self.assertIs(event['stamp'] is None, kind == failing)

    def test_full_matrix_preserves_actions_checks_and_bounded_old_listeners(self):
        driver = InertSweep(behavior_disconnect=True)
        self.assertEqual(driver.run(), 0)
        receipt = self.terminal(driver.output.getvalue())
        self.assertEqual(receipt['planned_cells'], 205)
        self.assertEqual(receipt['outcome'], 'pass')
        self.assertIsNone(receipt['failed_cell'])
        self.assertIsNone(receipt['disconnect']['active_ordinal'])
        self.assertTrue(receipt['disconnect']['seen'])
        self.assertEqual(receipt['sweep']['teardown_end']['mono_before_us']
                         - receipt['sweep']['teardown_start']['mono_after_us'], 3000)
        self.assertEqual([page.ordinal for page in driver.pages], list(range(1, 206)))
        self.assertEqual(driver.live_counts, [1] * 205)
        self.assertEqual(driver.active_crashes_after_old_callbacks, [False] * 204)
        self.assertEqual(driver.unwind_live_counts, [0])
        self.assertTrue(all(ref() is None for ref in driver.cell_refs))
        self.assertEqual(len(driver.pages), 205)
        for page in driver.pages:
            for kind in ('crash', 'close'):
                callback, = page.listeners[kind]
                diagnostic, = (slot.cell_contents for slot in callback.__closure__
                               if isinstance(slot.cell_contents, sweep.SettleDiagnostic))
                self.assertIsNone(diagnostic.chronology_cell)
        self.assert_full_actions(driver.actions)
        output = driver.output.getvalue().splitlines()
        self.assertEqual([line.split(' ', 1)[0] for line in output],
                         ['WEBKIT_SETTLE_STATE', 'WEBKIT_SETTLE_TRACE', 'WEBKIT_SETTLE_TRACE',
                          'WEBKIT_SETTLE_TRACE', 'WEBKIT_HOST_CHRONOLOGY', 'webkit:'])
        self.assertEqual(output[-1], 'webkit: 2137 checks over 41 routes x 5 widths, 0 failed')

    def assert_full_actions(self, actual):
        expected = [('server-start',), ('playwright-enter',), ('launch',), ('identity',)]

        def context(width, **options):
            expected.extend([('context', dict(viewport=dict(width=width, height=800), **options)), ('stubs',)])

        for width in (320, 375, 768, 1024, 1440):
            context(width, has_touch=width < 768, is_mobile=False)
            for path, bare in sweep.ROUTES:
                expected.extend([
                    ('new-page',), ('page-init', sweep.SETTLE_DIAGNOSTIC_JS),
                    ('goto', 'http://127.0.0.1:1234' + path, dict(wait_until='load', timeout=20000)),
                    ('selector', 'main > :not(.loading)', dict(timeout=10000)),
                    ('wait', sweep.OBSERVED_SETTLE_JS, dict(timeout=10000)),
                    ('evaluate', sweep.PAGE_JS, ()), ('evaluate', sweep.IS_MOBILE_JS, ()),
                ])
                if bare:
                    expected.append(('evaluate', "({header: !!document.querySelector('#app header.navbar-header'), footer: !!document.querySelector('#app footer')})", ()))
                else:
                    expected.append(('evaluate', sweep.NAV_STATE_JS, ()))
                    if path == '/':
                        expected.append(('evaluate', "(() => { const l = [...document.querySelectorAll('header .desktop-nav a')].find((a) => a.textContent.trim() === 'How it works'); return l ? [l.getAttribute('aria-current')] : null })()", ()))
                if width < 768:
                    expected.append(('evaluate', sweep.TOUCH_JS, (sweep.TOUCH_SCOPES,)))
                if (width, path) == (320, '/'):
                    expected.append(('wait', sweep.SETTLE_STATE_PROBE_JS,
                                     dict(arg='WEBKIT_SETTLE_STATE ', timeout=1000, polling=100)))
                expected.append(('page-close',))
            expected.append(('context-close',))
            if width < 768:
                for name in ('check_nav_sheet', 'check_overlays'):
                    context(width, has_touch=True)
                    expected.extend([(name,), ('context-close',)])
            if width == 375:
                expected.append(('check_reduced_motion',))
            if width == 1440:
                expected.append(('check_boundaries',))
            context(width, has_touch=width < 768)
            expected.extend([('check_footer',), ('context-close',)])
            context(width)
            expected.extend([('context-init', sweep.SESSION_HINT_INIT), ('check_signed_in_nav',), ('context-close',)])
        expected.extend([('browser-close',), ('playwright-unwind',), ('playwright-exit',), ('shutdown',)])
        self.assertEqual(actual, expected)

    def test_assertion_close_receipt_and_terminal_replacement_preserve_lifetime(self):
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                driver = InertSweep(assertions=(1, 2), timeouts=(3,) if timeout else ())
                self.assertEqual(driver.run('--routes', '/admin', '--widths', '601'), 2 if timeout else 1)
                receipt = self.terminal(driver.output.getvalue())
                cell = receipt['failed_cell']
                self.assertEqual(receipt['outcome'], 'infra_failure' if timeout else 'assertion_failure')
                self.assertEqual((cell['ordinal'], cell['route_index'], cell['width_index'], cell['kind']),
                                 (3, 34, None, 'infra') if timeout else (1, 32, None, 'assertion'))
                self.assertTrue(cell['close']['seen'])
                self.assertFalse(cell['crash']['seen'])
                self.assertLess(cell['cell_start']['mono_after_us'], cell['settle_start']['mono_before_us'])
                if timeout:
                    self.assertIsNone(cell['page_close_start'])
                    self.assertEqual(driver.live_counts, [1, 2, 2])
                    self.assertEqual(driver.unwind_live_counts, [1])
                    self.assertLess(receipt['sweep']['teardown_start']['mono_after_us'],
                                    cell['close']['stamp']['mono_before_us'])
                    self.assertEqual(receipt['disconnect']['active_ordinal'], 3)
                else:
                    self.assertEqual(cell['page_close_start']['mono_after_us'] + 1000,
                                     cell['close']['stamp']['mono_before_us'])
                    self.assertEqual(driver.live_counts, [1] + [2] * (len(driver.pages) - 1))
                    self.assertEqual(driver.unwind_live_counts, [1])
                    self.assertIsNone(receipt['disconnect']['active_ordinal'])
                gc.collect()
                self.assertTrue(all(ref() is None for ref in driver.cell_refs))

    def test_observer_faults_preserve_original_action_trace_exit_and_shutdown(self):
        args = ('--routes', '/signin', '--widths', '1024')

        def broken(*args, **kwargs):
            raise RuntimeError('private-observer-failure')

        write_line = sweep.emit_diagnostic_line

        def broken_terminal_writer(line):
            if line.startswith(CHRONOLOGY_PREFIX):
                broken()
            write_line(line)

        # Keep the baseline in-process and compare every browser action and argument.
        matrix = (
            ('constructor', (sweep, 'SweepChronology', broken)),
            ('cell constructor', (sweep, 'CellChronology', broken)),
            ('clock', (sweep, 'sample_host_stamp', broken)),
            ('writer', (sweep, 'emit_diagnostic_line', broken_terminal_writer)),
            ('disconnect registration', (InertSweep, 'on', broken)),
            ('cleanup', (sweep.SettleDiagnostic, 'detach_chronology', broken)),
            ('finally cleanup', (sweep.SweepChronology, 'release', broken)),
            ('finally mark', (sweep.SweepChronology, 'mark_sweep', broken)),
            ('finally emit', (sweep.SweepChronology, 'emit_terminal', broken)),
            ('serialization', (sweep, 'valid_host_chronology', broken)),
        )
        for expected_exit, configuration in ((0, {}), (2, {'timeouts': (1,)}),
                                             (None, {'geometry_errors': (1,)})):
            baseline = InertSweep(**configuration)
            if expected_exit is None:
                self.assert_original_exception(baseline, args)
            else:
                self.assertEqual(baseline.run(*args), expected_exit)
            for name, fault in matrix:
                with self.subTest(name=name, expected_exit=expected_exit):
                    driver = InertSweep(**configuration)
                    if expected_exit is None:
                        self.assert_original_exception(driver, args, faults=(fault,))
                    else:
                        self.assertEqual(driver.run(*args, faults=(fault,)), expected_exit)
                    self.assertEqual(driver.actions, baseline.actions)
                    self.assertEqual(driver.actions[-1], ('shutdown',))
                    self.assertNotIn('private-observer', driver.output.getvalue())
                    if name == 'serialization':
                        self.assertEqual(self.terminal(driver.output.getvalue()), self.fallback())

    def assert_original_exception(self, driver, args, **kwargs):
        with self.assertRaises(RuntimeError) as caught:
            driver.run(*args, **kwargs)
        self.assertIs(caught.exception, driver.original)

    def test_browser_page_and_context_unwind_errors_preserve_identity_and_order(self):
        args = ('--routes', '/signin', '--widths', '1024')
        for fail_at, page_close_errors in (('browser-close', ()), ('playwright-exit', ()), (None, (1,))):
            with self.subTest(fail_at=fail_at, page_close_errors=page_close_errors):
                driver = InertSweep(fail_at=fail_at, page_close_errors=page_close_errors)
                self.assert_original_exception(driver, args)
                self.assertEqual([action[0] for action in driver.actions[-3:]],
                                 ['playwright-unwind', 'playwright-exit', 'shutdown'])
                receipt = self.terminal(driver.output.getvalue())
                self.assertEqual(receipt['outcome'], 'exception')
                if page_close_errors:
                    self.assertEqual(driver.unwind_live_counts, [1])
                    self.assertEqual(receipt['failed_cell']['kind'], 'exception')
                    self.assertEqual(receipt['disconnect']['active_ordinal'], 1)
                    self.assertIsNone(driver.cell_refs[0](), 'retained original exception must not keep the cell alive')
                else:
                    self.assertIsNone(receipt['failed_cell'])
                self.assertLess(receipt['sweep']['teardown_start']['mono_after_us'],
                                receipt['sweep']['teardown_end']['mono_before_us'])

    def test_engine_unavailable_and_chromium_preserve_exits_and_scope(self):
        driver = InertSweep(fail_at='launch')
        self.assertEqual(driver.run('--behaviours-only'), 3)
        receipt = self.terminal(driver.output.getvalue())
        self.assertEqual((receipt['outcome'], receipt['planned_cells']), ('engine_unavailable', 0))
        self.assertIsNone(receipt['sweep']['browser_ready'])
        chromium = InertSweep()
        self.assertEqual(chromium.run('--routes', '/signin', '--widths', '1024', engine='chromium'), 0)
        self.assertNotIn(CHRONOLOGY_PREFIX, chromium.output.getvalue())
        self.assertIn(('wait', sweep.SETTLE_JS, dict(timeout=10000)), chromium.actions)

    @staticmethod
    def fallback():
        return dict(version=1, engine='webkit', outcome='unknown',
                    observer_errors=dict(clock=False, registration=False, serialization=True))

    def test_closed_schema_refuses_unknown_keys_types_and_secret_values(self):
        canary = 'https://private.example/?token=private-token#private-message'
        for name, mutate in (
            ('unknown sweep key', lambda host: host.sweep.update(private_url=canary)),
            ('nonfinite stamp', lambda host: host.sweep.update(sweep_start=dict(
                utc_us=float('nan'), mono_before_us=1, mono_after_us=2))),
            ('boolean count', lambda host: setattr(host, 'planned_cells', True)),
            ('invalid ordinal', lambda host: host.disconnect.update(active_ordinal=206)),
            ('invalid armed', lambda host: host.disconnect.update(armed=1)),
            ('unknown failure key', lambda host: host.retained.record.update(private_message=canary)),
            ('unknown failure kind', lambda host: host.retained.record.update(kind=canary)),
            ('reversed stamp', lambda host: host.sweep.update(sweep_start=dict(
                utc_us=1, mono_before_us=2, mono_after_us=1))),
            ('unbounded width', lambda host: host.retained.record.update(width_index=6)),
        ):
            with self.subTest(name=name):
                host = sweep.SweepChronology()
                host.configure([sweep.ROUTES[0]], [320])
                host.retain_failure(host.begin_cell(1, 1, 1), 'infra')
                mutate(host)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    host.emit_terminal('infra_failure')
                    host.emit_terminal(canary)
                self.assertEqual(self.terminal(output.getvalue()), self.fallback())
                self.assertNotIn('private', output.getvalue())

    def test_complete_line_byte_limit_includes_prefix_and_newline(self):
        dumps = json.dumps
        for byte_count in (4096, 4097):
            with self.subTest(byte_count=byte_count):
                host = sweep.SweepChronology()
                host.configure([], [320])
                output = io.StringIO()

                def padded(*args, **kwargs):
                    return dumps(*args, **kwargs).ljust(byte_count - len(CHRONOLOGY_PREFIX) - 1)

                with contextlib.redirect_stdout(output), patch.object(sweep.json, 'dumps', padded):
                    host.emit_terminal('pass')
                receipt = self.terminal(output.getvalue())
                if byte_count == 4096:
                    self.assertEqual(len(output.getvalue().encode('ascii')), 4096)
                    self.assertEqual(receipt['outcome'], 'pass')
                else:
                    self.assertEqual(receipt, self.fallback())

    def test_oversized_and_noncanonical_matrices_fall_back_without_changing_gate(self):
        for widths in ('320,320', '320,375,768,1024,1440,512'):
            with self.subTest(widths=widths):
                driver = InertSweep()
                self.assertEqual(driver.run('--widths', widths), 0)
                self.assertEqual(self.terminal(driver.output.getvalue()), self.fallback())
                self.assertEqual(len(driver.pages), 41 * len(widths.split(',')))


class ReceiptMainAssertions:
    def assert_timeout_receipt(self, **kwargs):
        code, output, waits = run_receipt_main(**kwargs)
        self.assertEqual(code, 2)
        self.assertEqual(waits, [
            (sweep.OBSERVED_SETTLE_JS, {'timeout': 10000}),
            (sweep.SETTLE_STATE_PROBE_JS, {'arg': 'WEBKIT_SETTLE_STATE ', 'timeout': 1000, 'polling': 100}),
        ])
        lines = output.splitlines()
        self.assertEqual(lines[0], 'INFRA webkit 1024px /signin: ORIGINAL 10000ms failure')
        self.assertNotIn('private-', output)
        self.assertNotIn(FIRST_DOCUMENT, output)
        self.assertNotIn(OTHER_DOCUMENT, output)
        if 'output' in kwargs.get('faults', ()):
            self.assertEqual(len(lines), 1)
            return None
        trace, = (line for line in lines if line.startswith('WEBKIT_SETTLE_TRACE '))
        state, = (line for line in lines if line.startswith('WEBKIT_SETTLE_STATE '))
        terminal, = (line for line in lines if line.startswith(CHRONOLOGY_PREFIX))
        self.assertEqual(lines, [lines[0], trace, state, terminal])
        self.assertEqual(json.loads(trace.split(' ', 1)[1])['outcome'], 'infra')
        receipt = json.loads(state.split(' ', 1)[1])
        self.assertEqual(receipt['capture'], 'after-timeout')
        self.assertEqual(receipt['outcome'], 'missing-marker')
        self.assertEqual(receipt['errorFamily'], 'playwright-error')
        self.assertIsNone(receipt['state'])
        self.assertIs(type(receipt['elapsedMs']), int)
        self.assertIn('observation', receipt, 'the timeout probe has no independent observation')
        self.assertEqual(set(receipt['observation']), {'console', 'documentMatch', 'lifecycle', 'rejected'})
        return receipt['observation']


class InertProbePage:
    def __init__(self, payload):
        self.payload = payload

    def wait_for_function(self, *args, **kwargs):
        raise InertPlaywrightError('Page.wait_for_function: Error: WEBKIT_SETTLE_STATE '
                                  + self.payload + '\nprivate-stack-detail')


def run_timeout_pipe_child(mode):
    """Real production main/stdout/shutdown; only browser/server boundaries are inert."""
    api = inert_playwright_api()

    class Page(InertProbePage):
        def on(self, *args):
            pass

        def add_init_script(self, *args):
            pass

        def goto(self, *args, **kwargs):
            pass

        def wait_for_selector(self, *args, **kwargs):
            pass

        def wait_for_function(self, expression, **kwargs):
            if expression == sweep.OBSERVED_SETTLE_JS:
                assert kwargs == {'timeout': 10000}
                raise InertPlaywrightTimeout('ORIGINAL 10000ms failure')
            return super().wait_for_function(expression, **kwargs)

    class Diagnostic(sweep.SettleDiagnostic):
        def emit(self, *args):
            # main has just flushed INFRA. Parent closes its reader before releasing us.
            assert sys.stdin.readline() == 'reader ready\n'
            if mode != 'probe-only' and mode != 'without-diagnostics':
                super().emit(*args)

    page = Page(json.dumps(PROBE_STATE))
    context = types.SimpleNamespace(new_page=lambda: page, close=lambda: None)
    browser = types.SimpleNamespace(new_context=lambda **kwargs: context, close=lambda: None)
    api.sync_playwright = lambda: contextlib.nullcontext(types.SimpleNamespace(
        webkit=types.SimpleNamespace(launch=lambda: browser)))
    server = types.SimpleNamespace(server_address=('127.0.0.1', 1234),
                                   serve_forever=lambda: None, shutdown=lambda: None)
    bindings = dict(Server=lambda *args: server, SettleDiagnostic=Diagnostic,
                    threading=types.SimpleNamespace(Thread=lambda **kwargs:
                                                    types.SimpleNamespace(start=lambda: None)),
                    emit_browser_identity=lambda *args: None, install_stubs=lambda *args: None)
    if mode == 'without-diagnostics':
        bindings['emit_settle_probe'] = lambda *args: None
    with patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'),
                                 'playwright.sync_api': api}), \
            patch.dict(sweep.__dict__, bindings), \
            patch.object(Path, 'exists', return_value=True), \
            patch.object(sys, 'argv', ['sweep', '--engine', 'webkit', '--routes', '/signin',
                                      '--widths', '1024']):
        # This must be a buffered pipe, not -u or a StringIO/print replacement.
        assert isinstance(sys.stdout, io.TextIOWrapper)
        assert isinstance(sys.stdout.buffer, io.BufferedWriter)
        return sweep.main()


class DiagnosticProbeInertRegression(ReceiptMainAssertions, unittest.TestCase):
    def test_probe_reports_each_getter_and_encoding_outcome(self):
        state = json.dumps(PROBE_STATE)
        cases = [
            ('delete window.__selahcueSettleState;', 'absent', None),
            ('window.__selahcueSettleState = 42;', 'non-callable', None),
            ("Object.defineProperty(window, '__selahcueSettleState', {get() {"
             " throw new Error('private-read'); }});", 'getter-threw', None),
            ("window.__selahcueSettleState = () => { throw new Error('private-call'); };",
             'getter-threw', None),
            (f"window.__selahcueSettleState = () => ({{...{state}, "
             "get totalPolls() { throw new Error('private-encoding'); }});",
             'encoding-failed', None),
            ('window.__selahcueSettleState = () => null;', 'nullish', None),
            ('window.__selahcueSettleState = () => undefined;', 'nullish', None),
            (f'window.__selahcueSettleState = () => ({state});', 'snapshot', PROBE_STATE),
        ]
        results = run_protocol_js([dict(poll=False, setup=setup) for setup, _, _ in cases])
        for (setup, outcome, expected_state), result in zip(cases, results):
            with self.subTest(setup=setup):
                self.assertEqual(len(result['records']), 1, 'missing or duplicate console probe record')
                self.assertIsNotNone(result['error'], 'the probe stopped using the error delivery channel')
                line = result['records'][0]
                self.assertNotIn('private-', line)
                body = line.removeprefix(PROBE_PREFIX)
                self.assertLessEqual(len(body.encode('ascii')), 768)
                probe = json.loads(body)
                self.assertRegex(probe['document'], r'^[0-9a-f]{32}$')
                self.assertEqual(probe, protocol_record('probe', probe['document'], outcome=outcome,
                                                        state=expected_state, gateResult=True))

    def test_first_actual_poll_identifies_each_document_once(self):
        # Removing the getter in document one must not remove that document's identity.
        results = run_protocol_js([
            dict(poll=True, setup='delete window.__selahcueSettleState;'),
            dict(poll=True, setup=''),
            dict(poll=False, setup=''),
        ])
        documents = []
        for result in results[:2]:
            self.assertEqual(len(result['records']), 2, 'expected one first-poll record followed by one probe')
            document, probe = [json.loads(line.removeprefix(PROBE_PREFIX)) for line in result['records']]
            nonce = document['document']
            self.assertRegex(nonce, r'^[0-9a-f]{32}$')
            self.assertEqual(document, protocol_record('document', nonce))
            self.assertEqual(probe['document'], nonce)
            documents.append(nonce)
        self.assertNotEqual(*documents)
        self.assertEqual(len(results[2]['records']), 1)
        self.assertEqual(json.loads(results[2]['records'][0].removeprefix(PROBE_PREFIX))['kind'], 'probe')

    def test_probe_rechecks_gate_once_without_mutating_poll_state(self):
        results = run_protocol_js([dict(poll=True, setup=setup, readStateAfterProbe=True) for setup in (
            "window.gateReads = 0; document.getAnimations = () => {"
            " ++window.gateReads;"
            " return [{playState:'running', effect:{getComputedTiming:() => ({iterations:1})}}]; };",
            "window.gateReads = 0; document.getAnimations = () => {"
            " ++window.gateReads; throw new Error('private-gate-read'); };",
        )])
        for result, label in zip(results, (False, 'read-error')):
            with self.subTest(label=label):
                self.assertEqual(len(result['records']), 2, 'no fresh gate result was delivered')
                probe = json.loads(result['records'][1].removeprefix(PROBE_PREFIX))
                self.assertEqual(probe['gateResult'], label)
                self.assertIs(type(probe['gateResult']), type(label))
                self.assertEqual(result['gateReads'], 1)
                self.assertEqual(probe['outcome'], 'snapshot')
                self.assertEqual(probe['state']['totalPolls'], 2)
                self.assertIs(probe['state']['lastResult'], True)
                live_state = result['stateAfterProbe']
                self.assertEqual(live_state['totalPolls'], 2)
                self.assertIs(live_state['lastResult'], True)
                self.assertNotIn('private-', result['records'][1])
                self.assertTrue(result['error'].startswith('WEBKIT_SETTLE_STATE '))

    def test_console_write_failure_preserves_legacy_error_delivery(self):
        # Lose the console channel only at probe time. The original error
        # channel must still deliver the snapshot from the observed polls.
        result, = run_protocol_js([dict(
            poll=True, setup="console.debug = () => { throw new Error('private-console-write'); };",
        )])
        self.assertEqual(len(result['records']), 1)
        self.assertTrue(result['error'].startswith('WEBKIT_SETTLE_STATE '))
        state = json.loads(result['error'].removeprefix('WEBKIT_SETTLE_STATE '))
        self.assertEqual(state['totalPolls'], 2)

    def test_timeout_receipt_survives_missing_marker_with_document_match(self):
        for first, probe, match in (
            (FIRST_DOCUMENT, FIRST_DOCUMENT, 'same'),
            (FIRST_DOCUMENT, OTHER_DOCUMENT, 'different'),
            (FIRST_DOCUMENT, None, 'unknown'),
            (None, FIRST_DOCUMENT, 'unknown'),
        ):
            with self.subTest(match=match, first_present=bool(first), probe_present=bool(probe)):
                observed = self.assert_timeout_receipt(first_document=first, during=(protocol_text(probe_record(probe)),))
                self.assertEqual(observed['documentMatch'], match)
                self.assertEqual(observed['console'], dict(outcome='snapshot', state=PROBE_STATE, gateResult=False))
                self.assertEqual(observed['rejected'], 0)

    def test_post_probe_receipt_records_lifecycle_after_generic_cutoff(self):
        observed = self.assert_timeout_receipt(
            before=('crash', 'subframe-navigation'),
            during=('close', 'main-navigation', 'crash', 'crash', 'subframe-navigation',
                    protocol_text(probe_record())),
        )
        self.assertEqual(observed['lifecycle'], {
            'before': {'close': 0, 'crash': 1, 'mainDocumentNavigation': 1},
            'during': {'close': 1, 'crash': 2, 'mainDocumentNavigation': 1},
        })
        self.assertEqual(observed['documentMatch'], 'same')

    def test_observer_faults_preserve_original_timeout_and_single_probe(self):
        for fault in ('registration', 'removal', 'output'):
            with self.subTest(fault=fault):
                self.assert_timeout_receipt(faults=(fault,), during=(None, protocol_text(probe_record())))

    def test_nonstandard_json_constants_are_syntax_refusals(self):
        # Default Python JSON parsing accepts these tokens, including nested ones.
        payloads = ('NaN', 'Infinity', '-Infinity', '{"elapsedMs":NaN}',
                    '{"nested":[Infinity]}', '{"nested":{"value":-Infinity}}')
        with patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'),
                                     'playwright.sync_api': inert_playwright_api()}):
            for payload in payloads:
                with self.subTest(payload=payload):
                    result = sweep.probe_settle_state(InertProbePage(payload))
                    self.assertEqual(result['outcome'], 'invalid-json')
                    self.assertIsNone(result['state'])
                    self.assertNotIn(payload, json.dumps(result))

    def test_valid_json_keeps_schema_null_and_snapshot_results(self):
        cases = [('"NaN"', 'invalid-state', None), ('"Infinity"', 'invalid-state', None),
                 ('"-Infinity"', 'invalid-state', None),
                 ('{"words":"NaN Infinity -Infinity"}', 'invalid-state', None),
                 ('{}', 'invalid-state', None), ('null', 'unavailable', None),
                 (json.dumps(PROBE_STATE), 'snapshot', PROBE_STATE)]
        with patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'),
                                     'playwright.sync_api': inert_playwright_api()}):
            for payload, outcome, state in cases:
                with self.subTest(payload=payload):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        sweep.emit_settle_probe(InertProbePage(payload), 'healthy-control')
                    receipt = output.getvalue()
                    self.assertTrue(receipt.startswith('WEBKIT_SETTLE_STATE '))
                    result = json.loads(receipt.split(' ', 1)[1])
                    self.assertEqual(result['capture'], 'healthy-control')
                    self.assertEqual(result['outcome'], outcome)
                    self.assertEqual(result['state'], state)
                    self.assertEqual(result['errorFamily'], 'playwright-error')
                    self.assertEqual(set(result), {'capture', 'outcome', 'state', 'errorFamily', 'elapsedMs'})
                    self.assertNotIn('private-stack-detail', receipt)
                    self.assertLess(len(receipt), 512)

    def test_real_pipe_closure_preserves_infrastructure_process_exit(self):
        driver = ("import runpy, sys; ns = runpy.run_path(sys.argv[1]); "
                  "sys.exit(ns['run_timeout_pipe_child'](sys.argv[2]))")
        for mode in ('without-diagnostics', 'probe-only', 'trace-and-probe', 'healthy-reader'):
            with self.subTest(mode=mode):
                process = subprocess.Popen(
                    [sys.executable, '-I', '-B', '-c', driver, str(Path(__file__).resolve()), mode],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                try:
                    # A finite helper thread prevents a regression from blocking on readline.
                    from concurrent.futures import ThreadPoolExecutor
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        first = executor.submit(process.stdout.readline)
                        try:
                            original = first.result(timeout=5)
                        except Exception:
                            process.kill()
                            raise
                    self.assertEqual(original, 'INFRA webkit 1024px /signin: ORIGINAL 10000ms failure\n')
                    if mode != 'healthy-reader':
                        process.stdout.close()
                    process.stdin.write('reader ready\n')
                    process.stdin.close()
                    code = process.wait(timeout=5)
                    stderr = process.stderr.read()
                    self.assertEqual(code, 2, stderr)
                    self.assertEqual(stderr, '')
                    if mode == 'healthy-reader':
                        remaining = process.stdout.read().splitlines()
                        trace, = (line for line in remaining if line.startswith('WEBKIT_SETTLE_TRACE '))
                        state, = (line for line in remaining if line.startswith('WEBKIT_SETTLE_STATE '))
                        terminal, = (line for line in remaining if line.startswith(CHRONOLOGY_PREFIX))
                        self.assertEqual(remaining, [trace, state, terminal])
                        self.assertEqual(json.loads(trace.split(' ', 1)[1])['outcome'], 'infra')
                        self.assertEqual(json.loads(terminal.removeprefix(CHRONOLOGY_PREFIX))['outcome'],
                                         'infra_failure')
                        receipt = json.loads(state.split(' ', 1)[1])
                        self.assertEqual(receipt['capture'], 'after-timeout')
                        self.assertEqual(receipt['outcome'], 'snapshot')
                        self.assertEqual(receipt['state'], PROBE_STATE)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
                    for stream in (process.stdin, process.stdout, process.stderr):
                        stream.close()


class DiagnosticLedgerPrivacy(ReceiptMainAssertions, unittest.TestCase):
    def test_untrusted_probe_protocol_refuses_invalid_records(self):
        good = probe_record()
        record = protocol_text(good)
        rejected = {
            'array': PROBE_PREFIX + '[]',
            'incomplete JSON': PROBE_PREFIX + '{',
            'repeated version': record.replace('"version":1', '"version":1,"version":1'),
            'repeated state field': record.replace('"totalPolls":2', '"totalPolls":2,"totalPolls":2'),
            'nonstandard NaN': record.replace('"totalPolls":2', '"totalPolls":NaN'),
            'nonstandard Infinity': record.replace('"elapsedMs":10078', '"elapsedMs":Infinity'),
            'non-ASCII suffix': record + '\u00a0',
            '769-byte body': record.ljust(len(PROBE_PREFIX) + 769),
            'boolean version': protocol_text({**good, 'version': True}),
            'unknown version': protocol_text({**good, 'version': 2}),
            'extra field': protocol_text({**good, 'note': 'private-raw-url-cookie-credential'}),
            'invalid nonce': protocol_text({**good, 'document': FIRST_DOCUMENT.upper()}),
            'unknown outcome': protocol_text({**good, 'outcome': 'private-error-secret'}),
            'integer gate result': protocol_text({**good, 'gateResult': 0}),
            'poll count overflow': protocol_text({**good, 'state': {**PROBE_STATE, 'totalPolls': 65536}}),
            'timer count overflow': protocol_text({**good, 'state': {**PROBE_STATE, 'lateTimerEntries': 2}}),
            'extra state field': protocol_text({**good, 'state': {**PROBE_STATE, 'extra': 'private-dom-content'}}),
            'snapshot without state': protocol_text({**good, 'state': None}),
            'state for a nullish outcome': protocol_text({**good, 'outcome': 'nullish'}),
            'late document record': protocol_text(protocol_record('document', OTHER_DOCUMENT)),
        }
        for label, invalid in rejected.items():
            with self.subTest(label=label):
                observed = self.assert_timeout_receipt(during=(invalid,))
                self.assertEqual(observed['rejected'], 1)
                self.assertIsNone(observed['console'])
                self.assertEqual(observed['documentMatch'], 'unknown')

    def test_probe_protocol_accepts_a_768_byte_body(self):
        padded = protocol_text(probe_record()).ljust(len(PROBE_PREFIX) + 768)
        observed = self.assert_timeout_receipt(during=(padded,))
        self.assertEqual(observed['rejected'], 0)
        self.assertEqual(observed['documentMatch'], 'same')
        self.assertEqual(observed['console'], dict(outcome='snapshot', gateResult=False, state=PROBE_STATE))

    def test_probe_protocol_retains_the_first_valid_probe_record(self):
        good = probe_record()
        observed = self.assert_timeout_receipt(during=(protocol_text(good), protocol_text({
            **good, 'document': OTHER_DOCUMENT, 'gateResult': True,
        })))
        self.assertEqual(observed['rejected'], 1)
        self.assertEqual(observed['documentMatch'], 'same')
        self.assertEqual(observed['console'], dict(outcome='snapshot', gateResult=False, state=PROBE_STATE))

    def test_post_probe_counters_saturate(self):
        observed = self.assert_timeout_receipt(
            during=['crash', PROBE_PREFIX + 'null'] * 65537,
        )
        self.assertEqual(observed['rejected'], 65535)
        self.assertEqual(observed['lifecycle']['during']['crash'], 65535)
        self.assertIsNone(observed['console'])
        self.assertEqual(observed['documentMatch'], 'unknown')

    def test_planned_route_metadata_omits_query_and_fragment_secrets(self):
        # Observation can be unavailable; safe metadata must still render without secrets.
        diagnostic = sweep.SettleDiagnostic(None, '/verify?token=private-control-secret#private-fragment', 375)
        payload = json.loads(diagnostic.render('infra', 0))
        self.assertEqual(payload['route'], '/verify')
        self.assertNotIn('private-control-secret', diagnostic.render('infra', 0))
        self.assertNotIn('private-fragment', diagnostic.render('infra', 0))


class DiagnosticRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global PlaywrightTimeoutError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.webkit.launch()
        sweep.emit_browser_identity(cls.browser)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_observer_records_actual_list_and_blog_cells(self):
        # A pathname whitelist dropping either actual failed cell must fail this test.
        for route, width in [('/admin/customers', 768), ('/blog', 375), ('/blog/no-such-post', 375),
                             ('/admin/customers/cus_001', 320)]:
            with self.subTest(route=route), self.browser.new_context(
                viewport={'width': width, 'height': 800}) as context:
                context.route('**/*', lambda route: route.fulfill(
                    content_type='text/html', body='<main><h1>Diagnostic control</h1></main>'))
                page = context.new_page()
                diagnostic = sweep.SettleDiagnostic(page, route, width)
                page.goto('http://diagnostic.invalid' + route, wait_until='load', timeout=20000)
                self.assertGreater(len(diagnostic.samples), 0, 'actual failed cell has no renderer observations')

    def test_trace_identifies_failed_cell_and_keeps_successes_quiet(self):
        with self.browser.new_context() as context:
            for path, width, failed, expected in [
                ('/blog/no-such-post', 375, False, False),
                ('/blog/no-such-post', 375, True, True),
                ('/blog', 375, False, True),
                ('/admin/customers', 768, False, True),
                ('/admin/customers/cus_001', 320, False, True),
            ]:
                page = context.new_page()
                diagnostic = sweep.SettleDiagnostic(page, path, width)
                diagnostic.stage('navigation-start')
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    diagnostic.finish(0, failed)
                self.assertEqual(bool(output.getvalue()), expected)
                if expected:
                    payload = json.loads(output.getvalue().split(' ', 1)[1])
                    self.assertEqual(payload['route'], path)
                    self.assertEqual(payload['viewport'], {'width': width, 'height': 800})
                    self.assertEqual(payload['stage'], 'navigation-start')
                    self.assertEqual(payload['outcome'], 'assertion-failed' if failed else 'settled')
                page.close()

    def test_untrusted_console_payload_and_ledger_remain_bounded(self):
        with self.browser.new_context() as context:
            page = context.new_page()
            diagnostic = sweep.SettleDiagnostic(page, '/blog/no-such-post', 375)
            for _ in range(40):
                diagnostic.observe('pageerror')
                diagnostic.stage('navigation-start')
            page.evaluate("console.debug('WEBKIT_SETTLE_SAMPLE ' + JSON.stringify({secret:'do not retain'}))")
            payload = json.loads(diagnostic.render('infra', 40))
            self.assertEqual(len(payload['events']), 24)
            self.assertEqual(len(payload['stages']), 8)
            self.assertEqual(payload['dropped']['events'], 16)
            self.assertEqual(payload['dropped']['samples'], 1)
            self.assertNotIn('secret', diagnostic.render('infra', 40))
            self.assertLessEqual(len(diagnostic.render('infra', 40).encode()), 32768)

    def test_first_poll_only_reads_animations_for_the_gate(self):
        with self.browser.new_context() as context:
            page = context.new_page()
            diagnostic = sweep.SettleDiagnostic(page, '/poll-control', 375)
            page.goto('data:text/html,<main><h1>Poll control</h1></main>')
            observed = page.evaluate(
                """(source) => {
                  const getAnimations = document.getAnimations.bind(document);
                  let reads = 0;
                  document.getAnimations = (...args) => { reads++; return getAnimations(...args); };
                  const settled = eval(source)();
                  return { settled, reads };
                }""", sweep.OBSERVED_SETTLE_JS,
            )
            self.assertEqual(observed, {'settled': True, 'reads': 1})
            marker = json.loads(diagnostic.render('settled', 0))['firstPoll']
            self.assertIsNotNone(marker)
            self.assertEqual(set(marker), {'elapsedMs', 'pollCount', 'lastPollResult', 'rafCompleted', 'rafPending', 'visibilityState'})
            self.assertTrue(marker['lastPollResult'])
            payload = json.loads(diagnostic.render('settled', 0))
            self.assertIsNone(payload['firstFramePoll'])
            self.assertIsNone(payload['earlyTimer'])

    def test_early_timer_reports_without_a_second_poll(self):
        with self.browser.new_context() as context:
            page = context.new_page()
            diagnostic = sweep.SettleDiagnostic(page, '/early-timer-control', 375)
            page.goto('data:text/html,<main><h1>Timer control</h1></main>')
            with page.expect_console_message(
                predicate=lambda message: message.text.startswith('WEBKIT_SETTLE_MARKER ')
                and '"event":"earlyTimer"' in message.text,
            ):
                page.evaluate("document.querySelector('h1').animate([{opacity:1},{opacity:0}], {duration:30000})")
                # Invoke one real predicate without scheduling a follow-up Playwright poll.
                self.assertFalse(page.evaluate(sweep.OBSERVED_SETTLE_JS))
            payload = json.loads(diagnostic.render('infra', 0))
            self.assertIsNone(payload['firstFramePoll'])
            self.assertEqual(payload['earlyTimer']['pollCount'], 1)
            self.assertFalse(payload['earlyTimer']['lastPollResult'])

    def test_pagehide_reports_why_observation_stopped_before_first_poll(self):
        with self.browser.new_context() as context:
            page = context.new_page()
            diagnostic = sweep.SettleDiagnostic(page, '/pagehide-control', 375)
            page.goto('data:text/html,<main><h1>Pagehide control</h1></main>')
            page.evaluate("dispatchEvent(new Event('pagehide'))")
            payload = json.loads(diagnostic.render('infra', 0))
            hidden = payload.get('pageHide')
            self.assertIsNotNone(hidden, 'no record of observation stopping on pagehide')
            self.assertEqual(hidden['pollCount'], 0)
            self.assertIsNone(hidden['lastPollResult'])
            self.assertTrue(page.evaluate(sweep.OBSERVED_SETTLE_JS))
            self.assertNotIn('firstPoll', diagnostic.markers)

    def test_separate_timer_reports_when_periodic_animation_snapshot_errors(self):
        with self.browser.new_context() as context:
            page = context.new_page()
            diagnostic = sweep.SettleDiagnostic(page, '/snapshot-error-control', 375)
            snapshot_events = []
            page.on('console', lambda message: snapshot_events.append(message.text))
            page.goto('data:text/html,<main><h1>Snapshot error control</h1></main>')
            with page.expect_console_message(
                predicate=lambda message: message.text == 'WEBKIT_SETTLE_SAMPLE {"observerError":true}',
                timeout=3000,
            ):
                page.evaluate("document.querySelector('h1').animate([{opacity:1},{opacity:0}], {duration:30000})")
                self.assertFalse(page.evaluate(sweep.OBSERVED_SETTLE_JS))
                # Model a diagnostic animation read failing independently of the gate.
                page.evaluate("() => { document.getAnimations = () => { throw new Error('private-snapshot-error'); }; }")
            payload = json.loads(diagnostic.render('infra', 0))
            start = payload.get('periodicSampleStart')
            self.assertIsNotNone(start, 'no marker reached the harness before the animation snapshot')
            self.assertEqual(payload['samples'][-1], {'observerError': True})
            start_index = next(index for index, event in enumerate(snapshot_events)
                               if event.startswith('WEBKIT_SETTLE_MARKER {"event":"periodicSampleStart",'))
            self.assertLess(start_index, snapshot_events.index('WEBKIT_SETTLE_SAMPLE {"observerError":true}'))
            if 'lateTimer' not in diagnostic.markers:
                page.wait_for_event(
                    'console', predicate=lambda message: message.text.startswith('WEBKIT_SETTLE_MARKER ')
                    and '"event":"lateTimer"' in message.text,
                    timeout=3000,
                )
            encoded = diagnostic.render('infra', 0)
            late = json.loads(encoded)['lateTimer']
            self.assertGreaterEqual(late['elapsedMs'], start['elapsedMs'])
            self.assertEqual(late['pollCount'], 1)
            self.assertFalse(late['lastPollResult'])
            self.assertNotIn('private-snapshot-error', encoded)

    def test_animation_observer_hides_unrecognized_labels_and_rejects_spoofed_labels(self):
        with self.browser.new_context() as context:
            page = context.new_page()
            diagnostic = sweep.SettleDiagnostic(page, '/animation-labels', 375)
            page.goto('data:text/html,<main><button>Private control</button></main>')
            page.evaluate(
                """() => {
                  const target = document.querySelector('button');
                  target.id = 'private-id';
                  target.className = 'private-class';
                  const style = document.createElement('style');
                  style.textContent = '@keyframes private-animation { to { opacity: .5 } }'
                    + '#private-id { animation: private-animation 30s; }';
                  document.head.append(style);
                }"""
            )
            page.wait_for_event('console', predicate=lambda m: m.text.startswith('WEBKIT_SETTLE_SAMPLE '))
            encoded = diagnostic.render('infra', 0)
            self.assertNotIn('private-', encoded)
            sample = json.loads(encoded)['samples'][-1]
            animation = sample['animations'][0]
            self.assertEqual(animation['type'], 'CSSAnimation')
            self.assertEqual(animation['animationName'], 'other')
            self.assertIs(type(animation['target']['id']), int)
            for field in ('type', 'animationName', 'transitionProperty', 'target'):
                spoofed = copy.deepcopy(sample)
                spoofed['animations'][0][field] = (
                    {**animation['target'], 'label': 'private-forged-target'}
                    if field == 'target' else 'private-forged-' + field
                )
                page.evaluate("(sample) => console.debug('WEBKIT_SETTLE_SAMPLE ' + JSON.stringify(sample))", spoofed)
            payload = json.loads(diagnostic.render('infra', 0))
            self.assertEqual(payload['dropped']['samples'], 4)
            self.assertNotIn('private-forged', json.dumps(payload))

    def test_first_poll_survives_output_byte_trimming(self):
        with self.browser.new_context() as context:
            page = context.new_page()
            diagnostic = sweep.SettleDiagnostic(page, '/trim-control', 375)
            page.goto('data:text/html,<main><h1>Trim control</h1></main>')
            page.wait_for_function(sweep.OBSERVED_SETTLE_JS, timeout=10000)
            page.evaluate(
                """() => {
                  for (let i = 0; i < 12; i++) {
                    const button = document.createElement('button');
                    document.querySelector('main').append(button);
                    button.animate([{opacity:1},{opacity:0}], {duration:31415.926535897932});
                  }
                }"""
            )
            page.wait_for_event('console', predicate=lambda m: m.text.startswith('WEBKIT_SETTLE_SAMPLE '))
            sample = diagnostic.samples[-1]
            self.assertEqual(len(sample['animations']), 12)
            first_poll = json.loads(diagnostic.render('infra', 0))['firstPoll']
            self.assertIsNotNone(first_poll)
            # Fill the actual console ledger with browser-derived, valid timer records.
            page.evaluate(
                """sample => {
                  for (let i = 3; i <= 13; i++) {
                    console.debug('WEBKIT_SETTLE_SAMPLE ' + JSON.stringify({...sample, sample: i}));
                  }
                }""", sample,
            )
            self.assertEqual(len(diagnostic.samples), 13)
            self.assertGreater(len(json.dumps(diagnostic.samples)), 32768)
            encoded = diagnostic.render('infra', 0)
            payload = json.loads(encoded)
            self.assertLessEqual(len(encoded.encode('ascii')), 32768)
            self.assertTrue(payload['truncated'])
            self.assertGreater(payload['dropped']['samples'], 0)
            self.assertEqual(payload['firstPoll'], first_poll)
            self.assertEqual(payload['samples'][-1]['sample'], 13)

    def test_real_finite_infinite_delayed_and_pending_animation_controls(self):
        with self.browser.new_context(viewport={'width': 375, 'height': 800}) as context:
            page = context.new_page()
            context.route('**/*', lambda route: route.fulfill(content_type='text/html', body='<main><button style="width:44px;height:44px">Control</button></main>'))
            page.goto('http://diagnostic.invalid/animation-control', wait_until='load')
            # A moving finite control blocks the original gate, then returns to its geometry.
            page.evaluate("window.finite = document.querySelector('button').animate([{transform:'scale(.5)'},{transform:'scale(.8)'}], {duration:1400})")
            self.assertFalse(page.evaluate(sweep.SETTLE_JS))
            self.assertLess(page.locator('button').bounding_box()['height'], 44)
            page.wait_for_function(sweep.OBSERVED_SETTLE_JS, timeout=10000)
            self.assertEqual(page.locator('button').bounding_box()['height'], 44)
            page.evaluate("window.decoration = document.body.animate([{opacity:1},{opacity:.9}], {duration:500,iterations:Infinity})")
            self.assertTrue(page.evaluate(sweep.SETTLE_JS))
            state = page.evaluate("window.delayed = document.querySelector('button').animate([{opacity:1},{opacity:.9}], {duration:100,delay:1400}); ({pending: delayed.pending, state: delayed.playState})")
            self.assertEqual(state['state'], 'running')
            self.assertTrue(state['pending'])
            self.assertFalse(page.evaluate(sweep.SETTLE_JS))
            page.wait_for_function(sweep.OBSERVED_SETTLE_JS, timeout=10000)

    def test_long_animation_timeout_records_its_own_poll_and_frames(self):
        with self.browser.new_context(viewport={'width': 375, 'height': 800}) as context:
            page = context.new_page()
            diagnostic = sweep.SettleDiagnostic(page, '/timeout-control', 375)
            page.goto('data:text/html,<main><button>Timeout control</button></main>')
            page.evaluate("window.long = document.querySelector('button').animate([{opacity:1},{opacity:.9}], {duration:30000})")
            self.assertFalse(page.evaluate(sweep.SETTLE_JS))
            self.assertEqual(page.evaluate('long.effect.getComputedTiming().iterations'), 1)
            with self.assertRaises(PlaywrightTimeoutError):
                page.wait_for_function(sweep.OBSERVED_SETTLE_JS, timeout=10000)
            payload = json.loads(diagnostic.render('infra', 0))
            first = payload['firstPoll']
            frame = payload['firstFramePoll']
            timer = payload['earlyTimer']
            self.assertFalse(first['lastPollResult'])
            self.assertEqual(frame['pollCount'], 2)
            self.assertFalse(frame['lastPollResult'])
            self.assertGreaterEqual(frame['elapsedMs'], first['elapsedMs'])
            self.assertGreaterEqual(timer['elapsedMs'] - first['elapsedMs'], 90)
            self.assertGreaterEqual(timer['pollCount'], 1)
            self.assertFalse(timer['lastPollResult'])
            self.assertTrue(any(
                not sample['predicate'] and sample['rafCompleted'] > 0
                and sample['pollCount'] > 1 and sample['lastPollResult'] is False
                and any(animation['timing'].get('duration') == 30000 and animation['playState'] == 'running'
                        for animation in sample['animations'])
                for sample in payload['samples']
            ))
            self.assertLessEqual(len(diagnostic.samples), 13)

    def test_missing_route_content_is_refused_at_existing_deadline(self):
        with self.browser.new_context() as context:
            page = context.new_page()
            context.route('**/*', lambda route: route.fulfill(content_type='text/html', body='<main><div class="loading">Loading</div></main>'))
            diagnostic = sweep.SettleDiagnostic(page, '/missing-control', 375)
            page.goto('http://diagnostic.invalid/missing-control', wait_until='load')
            with self.assertRaises(PlaywrightTimeoutError):
                page.wait_for_selector('main > :not(.loading)', timeout=10000)
            self.assertGreaterEqual(len(diagnostic.samples), 9)
            self.assertFalse(diagnostic.samples[-1]['contentPresent'])
            self.assertGreater(diagnostic.samples[-1]['rafCompleted'], 0)

    def test_harness_rejects_malformed_content_and_uncaught_page_errors(self):
        # Exercise the actual refusal reporting, rather than copying its condition here.
        with tempfile.TemporaryDirectory(prefix='selahcue-diagnostic-control-') as directory:
            dist = Path(directory)
            (dist / 'index.html').write_text('<main><p>x</p></main><script>throw new Error("diagnostic-control-error")</script>')
            driver = f"""
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('sweep', {str(Path(__file__).resolve().parents[1] / 'scripts/responsive_sweep.py')!r})
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)
sweep.DIST = Path({str(dist)!r})
sweep.ROUTES = [('/control', True)]
sweep.REQUIRE = True
sys.argv = ['responsive_sweep.py', '--engine', 'webkit', '--widths', '375', '--routes', '/control']
raise SystemExit(sweep.main())
"""
            result = subprocess.run([sys.executable, '-B', '-c', driver], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn('rendered (almost) nothing', result.stdout)
            self.assertIn('uncaught page error: diagnostic-control-error', result.stdout)
            trace = next(line for line in result.stdout.splitlines() if line.startswith('WEBKIT_SETTLE_TRACE '))
            payload = json.loads(trace.split(' ', 1)[1])
            self.assertEqual(payload['outcome'], 'assertion-failed')
            # This sample must come from the sweep's actual wait, after route content rendered.
            poll = payload['firstPoll']
            self.assertIsNotNone(poll, 'trace has no marker from the actual settlement wait')
            self.assertTrue(poll['lastPollResult'])
            self.assertEqual(poll['pollCount'], 1)
            self.assertEqual(payload['stages'][-3]['category'], 'settle-end')

    def test_legal_table_prose_reference_keeps_standalone_touch_controls_checked(self):
        ref = '<a class="li-link" href="#s-3-8">3.8</a>'
        non_inline = ref.replace('<a ', '<a style="display:inline-block" ')
        with self.browser.new_context(viewport={'width': 375, 'height': 800}) as context:
            page = context.new_page()
            for label, content, offenders in (
                ('adjacent prose', f'See the limits in section <!--v--> {ref}', []),
                ('standalone reference', ref, ['a.li-link "3.8"']),
                ('punctuation', f'({ref}).', ['a.li-link "3.8"']),
                ('separate control', f'See <button>Go</button> {ref}', ['button "Go"', 'a.li-link "3.8"']),
                ('non-inline reference', f'See {non_inline}', ['a.li-link "3.8"']),
                ('inline action', f'See {ref.replace("li-link", "li-link btn")}', ['a.li-link.btn "3.8"']),
            ):
                with self.subTest(label=label):
                    page.set_content(
                        '<style>button{width:25px;height:25px}</style><main>'
                        f'<table class="lt-table"><tbody><tr><td>{content}</td></tr></tbody></table></main>'
                    )
                    bounds = page.locator('a.li-link').bounding_box()
                    self.assertLess(min(bounds['width'], bounds['height']), 43.5, 'control must be undersized')
                    bad = page.evaluate(sweep.TOUCH_JS, sweep.TOUCH_SCOPES)
                    self.assertEqual([line.rsplit(' ', 1)[0] for line in bad], offenders)

    def test_existing_geometry_guards_detect_bad_controls(self):
        with self.browser.new_context(viewport={'width': 375, 'height': 800}) as context:
            page = context.new_page()
            page.set_content('<style>body{margin:0} .overflow{width:600px} .clip{overflow:hidden;width:375px} button{width:25px;height:25px}</style><main><div style="box-sizing:border-box;width:375px;padding:0 24px">Wrong gutter</div><div class="overflow">Overflow</div><div class="clip"><p style="width:600px">Clipped</p></div><button>Bad</button></main>')
            info = page.evaluate(sweep.PAGE_JS)
            self.assertGreater(info['scrollWidth'], info['vw'])
            self.assertTrue(info['offenders'])
            self.assertTrue(info['clipped'])
            self.assertTrue(info['edge'])
            self.assertTrue(info['fullBleed'])
            self.assertTrue(page.evaluate(sweep.TOUCH_JS, sweep.TOUCH_SCOPES))


if __name__ == '__main__':
    unittest.main(verbosity=2)
