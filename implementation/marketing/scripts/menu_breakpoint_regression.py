#!/usr/bin/env python3
"""Native menu navigation and modal recovery at the scrollbar-sensitive breakpoint."""
from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

import auth_pages_headless as auth
import responsive_sweep as sweep


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=['chromium', 'webkit', 'both'], default='both')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    stale = auth.check_bundle_is_current()
    if stale:
        raise RuntimeError(stale)
    results = []
    server = sweep.Server(('127.0.0.1', 0), sweep.SpaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        with sync_playwright() as pw:
            for engine in (['chromium', 'webkit'] if args.engine == 'both' else [args.engine]):
                browser = getattr(pw, engine).launch()
                try:
                    for width in (320, 768):
                        context = browser.new_context(viewport={'width': width, 'height': 900})
                        try:
                            page = context.new_page()
                            page.goto(base + '/')
                            page.locator('.home').wait_for()
                            page.evaluate('document.fonts.ready')
                            menu = page.get_by_role('button', name='Menu', exact=True)
                            record = {'engine': engine, 'width': width, 'checks': []}

                            def check(value, name):
                                if not value:
                                    raise AssertionError(f'{engine}/{width}: {name}')
                                record['checks'].append(name)

                            def released():
                                return page.evaluate("() => document.documentElement.style.overflow === '' && document.body.style.overflow === '' && !document.querySelector('#app').hasAttribute('inert')")

                            if not menu.is_visible():
                                check(not page.evaluate("matchMedia('(max-width: 767.98px)').matches"), 'desktop matches rendered control')
                                page.locator('.desktop-nav a[href="/pricing"]').click()
                                page.wait_for_url('**/pricing')
                                check(released(), 'desktop navigation leaves no modal locks')
                                results.append(record)
                                continue

                            def opened():
                                menu.click()
                                page.locator('#mobile-nav-sheet').wait_for(state='visible')
                                page.get_by_role('button', name='Close menu', exact=True).wait_for()
                                check(page.locator('.mobile-toggle').get_attribute('aria-expanded') == 'true', 'open survives media change')
                                check(page.evaluate("document.documentElement.style.overflow === 'hidden' && document.body.style.overflow === 'hidden' && document.querySelector('#app').hasAttribute('inert')"), 'scroll and inert held')

                            def closed():
                                page.locator('#mobile-nav-sheet').wait_for(state='detached')
                                check(released(), 'close restores scroll and inert')

                            opened()
                            check(page.evaluate("document.activeElement?.getAttribute('aria-label') === 'Close menu'"), 'focus enters modal')
                            page.keyboard.press('Shift+Tab')
                            check(page.evaluate("!!document.activeElement?.closest('#mobile-nav-sheet')"), 'reverse Tab stays in modal')
                            page.keyboard.press('Tab')
                            check(page.evaluate("document.activeElement?.getAttribute('aria-label') === 'Close menu'"), 'Tab wraps to first control')
                            page.locator('#mobile-nav-sheet a[href="/pricing"]').click()
                            page.wait_for_url('**/pricing')
                            closed()
                            check(page.url.endswith('/pricing'), 'native Pricing click navigates')
                            opened()
                            page.keyboard.press('Escape')
                            closed()
                            check(page.evaluate("document.activeElement?.getAttribute('aria-label') === 'Menu'"), 'Escape restores opener focus')
                            opened()
                            if engine == 'webkit' and width == 768:
                                page.wait_for_function("!matchMedia('(max-width: 767.98px)').matches")
                                check(page.locator('.mobile-toggle').get_attribute('aria-expanded') == 'true', 'locked WebKit query false before resize')
                            page.set_viewport_size({'width': 1024, 'height': 900})
                            closed()
                            check(page.locator('.desktop-nav').is_visible(), 'actual growth switches to desktop')
                            page.set_viewport_size({'width': width, 'height': 900})
                            menu.wait_for(state='visible')
                            opened()
                            page.go_back()
                            page.wait_for_url(base + '/')
                            closed()
                            opened()
                            page.get_by_role('button', name='Close menu', exact=True).click()
                            closed()
                            opened()
                            page.mouse.click(4, 450)
                            closed()
                            opened()
                            page.evaluate("window.dispatchEvent(new Event('pagehide'))")
                            closed()
                            opened()
                            page.evaluate("document.querySelector('#app').__vue_app__.unmount()")
                            check(released(), 'unmount releases modal locks')
                            results.append(record)
                        finally:
                            context.close()
                finally:
                    browser.close()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    report = {'result': 'PASS', 'scenarios': results, 'checks': sum(len(r['checks']) for r in results)}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
