#!/usr/bin/env python3
"""Real-WebKit observation checks; synthetic controls are not app reproduction."""
import contextlib
import importlib.util
import io
import json
import sys
import subprocess
import tempfile
from pathlib import Path
import unittest

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

SPEC = importlib.util.spec_from_file_location(
    'responsive_sweep', Path(__file__).resolve().parents[1] / 'scripts/responsive_sweep.py')
sweep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sweep)


class DiagnosticLedgerPrivacy(unittest.TestCase):
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

    def test_real_finite_infinite_delayed_and_pending_animation_controls(self):
        with self.browser.new_context(viewport={'width': 375, 'height': 800}) as context:
            page = context.new_page()
            context.route('**/*', lambda route: route.fulfill(content_type='text/html', body='<main><button style="width:44px;height:44px">Control</button></main>'))
            diagnostic = sweep.SettleDiagnostic(page, '/animation-control', 375)
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
            page.evaluate("window.long = document.querySelector('button').animate([{opacity:1},{opacity:.9}], {duration:30000})")
            self.assertFalse(page.evaluate(sweep.SETTLE_JS))
            self.assertEqual(page.evaluate('long.effect.getComputedTiming().iterations'), 1)
            with self.assertRaises(PlaywrightTimeoutError):
                page.wait_for_function(sweep.OBSERVED_SETTLE_JS, timeout=10000)
            self.assertTrue(any(not sample.get('predicate', True) and sample.get('rafCompleted', 0) > 0 and sample.get('pollCount', 0) > 1 and sample.get('lastPollResult') is False and any(animation['timing'].get('iterations') == 1 for animation in sample['animations']) for sample in diagnostic.samples))
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
            poll = next((sample for sample in payload['samples'] if sample.get('source') == 'settle-poll'), None)
            self.assertIsNotNone(poll, 'trace has no sample taken during the actual settlement wait')
            self.assertTrue(poll['contentPresent'])
            self.assertTrue(poll['predicate'])
            self.assertEqual(poll['pollCount'], 1)

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
