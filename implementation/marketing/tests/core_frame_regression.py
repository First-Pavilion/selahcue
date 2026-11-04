#!/usr/bin/env python3
"""Real-DOM regression for core's Figma frame versus nominal-window contracts.

The adapter SIMULATES 12px of external browser chrome by reducing only the real
browser viewport behind the requested window size. It does not alter page styles
or fake DOM measurements. This is not a reproduction of native classic scrollbars.
Automatically run by the core gate when WebKit is selected (120s bound).
Standalone after building: python3 tests/core_frame_regression.py
"""
from __future__ import annotations

import contextlib
import io
import json
import threading

from playwright.sync_api import sync_playwright

import core_pages_headless as core


class ReservedChromeWindow:
    """Only the external window boundary is simulated; rendering stays real."""

    def __init__(self, page):
        self.page = page
        self.viewport_size = page.viewport_size
        self.requested_widths = []

    def set_viewport_size(self, size):
        self.viewport_size = dict(size)
        self.requested_widths.append(size['width'])
        self.page.set_viewport_size({**size, 'width': size['width'] - 12})

    def __getattr__(self, name):
        return getattr(self.page, name)


def main():
    server = core.Server(('127.0.0.1', 0), core.SpaHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        with sync_playwright() as pw:
            browser = pw.webkit.launch()
            try:
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                context.route('**/graphql/**', lambda r: r.fulfill(status=204, body=''))
                core.catalogue.install(context)
                page = ReservedChromeWindow(context.new_page())
                core.TAB = 'Alt+Tab'
                core.check_download(page, base, 'webkit-simulated-12px-external-chrome')
                geometry_failures = list(core.FAILURES)
                print('SIMULATED_CHROME_GEOMETRY', json.dumps({
                    'clientWidth': page.evaluate('document.documentElement.clientWidth'),
                    'card': core.rect(page, '.platform-card')['w'],
                    'action': core.rect(page, '.platform-action')['w'],
                    'step': core.rect(page, '.step-card')['w'],
                    'failures': geometry_failures,
                }), flush=True)
                assert not geometry_failures, geometry_failures
                assert page.evaluate('document.documentElement.clientWidth') == 1440

                page.requested_widths.clear()
                core.check_no_sideways_scroll(page, base, 'webkit-simulated-12px-external-chrome')
                assert not core.FAILURES, core.FAILURES
                assert page.requested_widths == [320, 375, 768, 1024, 1440] * 4
                assert page.viewport_size['width'] == 1440
                assert page.page.viewport_size['width'] == 1428
                assert page.evaluate('document.documentElement.clientWidth') <= 1428

                # This fixture also simulates an outer innerWidth including the 12px
                # chrome. Comparing to innerWidth would miss its real 12px overflow.
                # DOM clientWidth/scrollWidth stay genuine; product styles stay unchanged.
                context.route('**/overflow-fixture', lambda r: r.fulfill(
                    content_type='text/html', body='<body style="margin:0"><h1>Overflow fixture</h1>'
                    '<script>Object.defineProperty(window, "innerWidth", '
                    '{value:innerWidth + 12})</script>'
                    '<div style="width:calc(100% + 12px);height:1px"></div>'))
                with contextlib.redirect_stdout(io.StringIO()):
                    core.check_no_sideways_scroll(page, base + '/overflow-fixture#', 'overflow-negative')
                overflow_failures = core.FAILURES[len(geometry_failures):]
                assert len(overflow_failures) == 20, overflow_failures
                assert all('12px wider' in failure for failure in overflow_failures), overflow_failures
                print('FRAME_REGRESSION_PASS: exact geometry, 20 nominal widths, 20 overflow negatives', flush=True)
                context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
