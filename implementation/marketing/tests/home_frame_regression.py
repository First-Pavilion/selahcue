#!/usr/bin/env python3
"""Genuine DOM frame/overflow controls; only external window chrome is simulated.

No product styles or clientWidth/scrollWidth measurements are faked. Automatically
run by the Home both-engine gate with a 120-second subprocess bound.
"""
import contextlib
import io
import json
import threading

from playwright.sync_api import sync_playwright
import home_page_headless as home


class ChromeWindow:
    def __init__(self, page, reserve):
        self.page, self.reserve = page, reserve
        self.viewport_size = page.viewport_size
        self.requested_widths = []
        self.client_reads = []

    def set_viewport_size(self, size):
        self.viewport_size = dict(size)
        self.requested_widths.append(size['width'])
        self.page.set_viewport_size({**size, 'width': size['width'] - self.reserve})

    def evaluate(self, expression, *args):
        result = self.page.evaluate(expression, *args)
        if expression == 'document.documentElement.clientWidth':
            self.client_reads.append(result)
        return result

    def __getattr__(self, name):
        return getattr(self.page, name)


def strict_widths(measurement):
    result = home.Run('frame-regression')
    with contextlib.redirect_stdout(io.StringIO()):
        home.check_figma_widths(result, measurement)
    assert result.checks == 8, result.checks
    return result


def main():
    server = home.Server(('127.0.0.1', 0), home.SpaHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    home.BASE_URL = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = ChromeWindow(browser.new_page(), 0)
                home.catalogue.install(page.context)
                m = home.measure(page, 1440, figma_frame=True)
                assert page.evaluate('document.documentElement.clientWidth') == 1440
                assert page.requested_widths == [1440], page.requested_widths
                assert not strict_widths(m).failures
                print('ZERO_GAP: unchanged outer1440/client1440, eight strict widths PASS', flush=True)
            finally:
                browser.close()
            browser = pw.webkit.launch()
            try:
                context = browser.new_context(viewport={'width': 1440, 'height': 900})
                home.catalogue.install(context)
                raw = context.new_page()
                # Same external-window adapter as Core: reserve12 real viewport pixels.
                # A host's own native scrollbar may reserve up to12 additional pixels.
                page = ChromeWindow(raw, 12)
                baseline = home.measure(page, 1440)
                baseline_client = page.evaluate('document.documentElement.clientWidth')
                assert 1416 <= baseline_client <= 1428, baseline_client
                assert len(strict_widths(baseline).failures) == 8
                print(f'UNCOMPENSATED: client{baseline_client} rejects all eight original strict assertions', flush=True)
                page.requested_widths.clear()
                page.client_reads.clear()
                fixed = home.measure(page, 1440, figma_frame=True)
                # Native scrollbar reservation can change across navigations; prove the
                # helper uses this load's genuine measurement, not the previous load.
                measured = page.client_reads[0]
                assert 1416 <= measured <= 1428, measured
                assert page.evaluate('document.documentElement.clientWidth') == 1440
                assert page.requested_widths == [1440, 2880 - measured], page.requested_widths
                assert not strict_widths(fixed).failures
                positive = home.Run('nominal-widths')
                home.check_no_horizontal_scroll(positive, page, 1440)
                page.requested_widths.clear()
                widths = [320, 375, 768, 1024, 1440]
                for width in widths:
                    home.measure(page, width)
                    home.check_no_horizontal_scroll(positive, page, width)
                    assert width - 24 <= page.evaluate('document.documentElement.clientWidth') <= width - 12
                assert not positive.failures, positive.failures
                assert page.requested_widths == widths, page.requested_widths
                print('FRAME_AND_NOMINAL: client1440 strict widths PASS; exact nominal requests', widths, flush=True)
                # The fixture creates real overflow. innerWidth alone models outer chrome,
                # so comparing against it would wrongly accept the 1px and 12px negatives.
                for overflow in (0, 1, 12, 24):
                    context.route('**/home-overflow-fixture*', lambda route: route.fulfill(
                        content_type='text/html', body=f'<body style="margin:0"><h1>Overflow fixture</h1>'
                        f'<div style="width:calc(100% + {overflow}px);height:2000px"></div>'
                        '<script>Object.defineProperty(window,"innerWidth",'
                        '{get:()=>document.documentElement.clientWidth+12})</script>'))
                    for width in widths:
                        page.set_viewport_size({'width': width, 'height': 900})
                        page.goto(home.BASE_URL + '/home-overflow-fixture', wait_until='load')
                        if width == 1440:
                            home.fit_figma_frame(page)
                        actual = page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth')
                        assert actual == overflow, (width, overflow, actual)
                        if overflow in (1, 12):
                            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                        result = home.Run('actual-overflow-fixture')
                        with contextlib.redirect_stdout(io.StringIO()):
                            home.check_no_horizontal_scroll(result, page, width)
                        assert len(result.failures) == (1 if overflow else 0), (width, overflow, result.failures)
                    context.unroute('**/home-overflow-fixture*')
                print(json.dumps({'zero_gap': 'PASS', 'strict_frame_assertions': 8, 'nominal_widths': widths,
                                  'overflow_positive_controls': 5, 'real_overflow_rejections': 15,
                                  'overflow_deltas': [1, 12, 24]}), flush=True)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
