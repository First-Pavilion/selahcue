#!/usr/bin/env python3
"""Real strict-CSP fixtures for the shipping gate's three locator waits.

No app/network fixtures replace the separate68-route production-image gate.
"""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from security_headers_headless import (
    CSP_OBSERVER, wait_for_auth_settled, wait_for_csp_violation, wait_for_rendered_app,
)

ROOT = Path(__file__).resolve().parents[1]


def must_refuse(wait, page, label):
    try:
        wait(page, timeout=150)
    except AssertionError:
        return label
    raise AssertionError(f'{label}: wait accepted an incomplete condition')


def main():
    policy = re.search(r'add_header Content-Security-Policy "([^"]+)" always;',
                       (ROOT / 'nginx.conf').read_text()).group(1)
    results = []
    with sync_playwright() as pw:
        for engine in ('chromium', 'webkit'):
            browser = getattr(pw, engine).launch(headless=True)
            try:
                context = browser.new_context()
                context.add_init_script(CSP_OBSERVER)
                def serve(route):
                    if route.request.url.endswith('/fixture.js'):
                        route.fulfill(content_type='application/javascript', body="""
                            document.querySelector('button')?.addEventListener('click', () => {
                                setTimeout(() => {
                                    document.querySelector('form').setAttribute('aria-busy','false');
                                    document.querySelector('#app').innerText='123456789012345678901';
                                }, 50);
                            });""")
                    else:
                        form = '' if route.request.url.endswith('/missing') else '<form aria-busy="true"><button type="button">Settle</button></form>'
                        route.fulfill(content_type='text/html', headers={'Content-Security-Policy': policy},
                                      body='<main id="app">  12345678901234567890  </main>' + form + '<script src="/fixture.js"></script>')
                context.route('https://csp-wait.test/**', serve)
                page = context.new_page()
                page.goto('https://csp-wait.test/')
                negative = [must_refuse(wait_for_rendered_app, page, '20trimmed characters'),
                            must_refuse(wait_for_auth_settled, page, 'busy form'),
                            must_refuse(wait_for_csp_violation, page, 'no CSP event')]
                page.get_by_role('button', name='Settle', exact=True).click()
                wait_for_rendered_app(page)
                wait_for_auth_settled(page)
                assert page.locator('#app').inner_text().strip() == '123456789012345678901'
                assert page.evaluate('window.cspViolations') == []
                page.evaluate("""() => { const s=document.createElement('script');
                    s.textContent='window.fixtureInlineRan=true'; document.head.append(s); }""")
                wait_for_csp_violation(page)
                assert page.evaluate('window.fixtureInlineRan !== true')
                assert any(v['directive'] == 'script-src-elem' and v['uri'] == 'inline'
                           for v in page.evaluate('window.cspViolations'))
                page.goto('https://csp-wait.test/missing')
                negative.append(must_refuse(wait_for_auth_settled, page, 'missing form'))
                results.append({'engine': engine, 'positive': ['21trimmed characters', 'settled form', 'real blocked inline violation'], 'negative': negative})
            finally:
                browser.close()
    print(json.dumps(results, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
