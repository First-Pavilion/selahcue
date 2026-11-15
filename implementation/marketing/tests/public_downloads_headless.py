#!/usr/bin/env python3
"""Verify the built public download route using synthetic manifest and navigation fixtures."""
import argparse
import http.server
import json
import threading
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HOST = 'https://selahcue-installers.sfo3.digitaloceanspaces.com'
VERSION = '0.0.0-synthetic'
HASH = 'a' * 64
TARGETS = [
    ('windows-x64', 'x64', 'exe', 'Windows x64'),
    ('macos-arm64', 'arm64', 'dmg', 'macOS Apple silicon (arm64)'),
    ('macos-x64', 'x64', 'dmg', 'macOS Intel (x64)'),
    ('ubuntu-24.04-x64', 'x64', 'deb', 'Ubuntu 24.04 x64'),
]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'dist'), **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        # Prevent preconnects and resource loads from escaping the loopback fixture.
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
        super().end_headers()

    def do_GET(self):
        if self.path == '/releases/current.json' and self.headers.get('X-Synthetic-Stall') == '1':
            threading.Event().wait(8)
            self.close_connection = True
            return
        if self.path in ('/download', '/pilot-privacy'):
            self.path = '/index.html'
        return super().do_GET()


def fixture():
    records = []
    for target, arch, ext, _ in TARGETS:
        filename = f'Synthetic-{target}.{ext}'
        mac = target.startswith('macos')
        records.append({
            'target': target,
            'architectures': [arch],
            'url': f'{HOST}/Synthetic/{VERSION}/{HASH}/{filename}',
            'filename': filename,
            'size_bytes': 123456,
            'sha256': HASH,
            'app_signature': 'ad_hoc' if mac else 'not_applicable',
            'package_signature': 'unsigned',
            'notarization': 'not_notarized' if mac else 'not_applicable',
            'publisher': None,
        })
    return {'schema_version': 1, 'status': 'published', 'release_id': 'synthetic-release',
            'version': VERSION, 'source_commit': 'b' * 40, 'artifacts': records}


def run(engine, base):
    browser = engine.launch()
    context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                  service_workers='block', reduced_motion='reduce')
    requests, unexpected, navigations, errors = [], [], [], []
    manifest = fixture()
    state = {'mode': 'source'}
    selected = manifest['artifacts'][3]['url']

    def handle(route):
        request = route.request
        url = request.url
        if url == base + '/releases/current.json' and request.method == 'GET':
            requests.append(request.all_headers())
            mode = state['mode']
            if mode == 'source':
                route.continue_()
            elif mode == 'timeout':
                route.continue_(headers={**request.headers, 'X-Synthetic-Stall': '1'})
            elif mode in ('missing', 'error'):
                route.fulfill(status=404 if mode == 'missing' else 503, body='synthetic response body')
            else:
                route.fulfill(json=manifest if mode == 'published' else {
                    **manifest, 'artifacts': manifest['artifacts'][:3],
                })
        elif url == selected and request.method == 'GET' and request.is_navigation_request():
            navigations.append((url, request.all_headers()))
            route.fulfill(content_type='text/html', body='<h1>Synthetic installer navigation</h1>')
        elif (url.startswith(base + '/') and request.method == 'GET' and
              (urlsplit(url).path in ('/download', '/pilot-privacy', '/favicon.ico', '/selahcue-logo.png') or
               urlsplit(url).path.startswith(('/assets/', '/fonts/', '/icons/')))):
            route.continue_()
        else:
            unexpected.append((request.method, url, request.resource_type))
            route.abort()

    context.route('**/*', handle)
    context.add_init_script("""
        for (const name of ['localStorage', 'sessionStorage']) {
          Object.defineProperty(window, name, { get() { throw new Error('storage blocked') } })
        }
    """)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base + '/pilot-privacy')
    expect(page.get_by_role('heading', name='Pilot registration data notice')).to_be_visible()
    expect(page.locator('main')).to_contain_text('ARCHIVED PILOT NOTICE')
    expect(page.locator('main')).to_contain_text('Pilot registration is closed.')

    panel = page.locator('#public-downloads')
    retry = panel.get_by_role('button', name='Retry availability check')
    links = panel.get_by_role('link')
    page.goto(base + '/download#public-downloads')
    expect(panel.get_by_role('status')).to_contain_text('Desktop installers are not available to download yet')
    expect(links).to_have_count(0)
    expect(panel.get_by_role('button')).to_have_count(0)
    assert not context.cookies()

    context.add_cookies([{'name': 'synthetic_session', 'value': 'never-send',
                          'url': base + '/', 'httpOnly': True}])
    for mode in ['missing', 'partial', 'error']:
        state['mode'] = mode
        page.reload()
        expect(panel.get_by_role('status')).to_contain_text('couldn’t check installer availability')
        expect(links).to_have_count(0)
        expect(retry).to_be_visible()
        expect(panel).not_to_contain_text('synthetic response body')

    state['mode'] = 'timeout'
    page.reload()
    expect(panel.get_by_role('status')).to_contain_text('Checking installer availability')
    expect(links).to_have_count(0)
    expect(retry).to_be_visible(timeout=7500)

    retry.focus()
    expect(retry).to_be_focused()
    assert retry.evaluate("el => el.matches(':focus-visible')"), 'Retry lacks keyboard focus'
    for mode in ['partial', 'error']:
        state['mode'] = mode
        previous_requests = len(requests)
        page.keyboard.press('Enter')
        expect(panel.get_by_role('status')).to_contain_text('couldn’t check installer availability')
        expect(links).to_have_count(0)
        expect(retry).to_be_enabled()
        expect(retry).to_be_focused()
        assert retry.evaluate("el => el.matches(':focus-visible')"), f'Retry lost keyboard focus after {mode}'
        assert len(requests) == previous_requests + 1, requests

    state['mode'] = 'published'
    page.keyboard.press('Enter')
    expect(links).to_have_count(4)
    expect(panel.get_by_role('heading', name='Desktop installers')).to_be_focused()
    expect(panel.get_by_role('status')).to_contain_text(f'Version {VERSION}')
    for index, (_, _, _, label) in enumerate(TARGETS):
        link = panel.get_by_role('link', name='Download for ' + label, exact=True)
        expect(link).to_have_attribute('href', manifest['artifacts'][index]['url'])
        expect(link).to_have_attribute('referrerpolicy', 'no-referrer')
    assert panel.get_by_text(HASH, exact=True).count() == 4
    assert panel.get_by_text('123,456 bytes', exact=True).count() == 4
    assert panel.get_by_text('Ad hoc', exact=True).count() == 2
    assert panel.get_by_text('Not notarized', exact=True).count() == 2
    assert not navigations, 'Installer was opened automatically'

    for width in [320, 375, 768, 1440]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.wait_for_function('width => innerWidth === width && document.documentElement.scrollWidth <= width + 1',
                               arg=width)
        assert panel.locator('.platform-card').evaluate_all(
            'cards => cards.every(el => el.scrollWidth <= el.clientWidth + 1)'
        ), f'{width}px card overflow'

    ubuntu = panel.get_by_role('link', name='Download for Ubuntu 24.04 x64', exact=True)
    ubuntu.focus()
    expect(ubuntu).to_be_focused()
    assert ubuntu.evaluate("el => el.matches(':focus-visible')"), 'Installer link lacks keyboard focus'
    context.clear_cookies()
    page.keyboard.press('Enter')
    expect(page.get_by_role('heading', name='Synthetic installer navigation')).to_be_visible()
    assert len(navigations) == 1 and navigations[0][0] == selected, navigations
    assert {'referer', 'cookie', 'authorization'}.isdisjoint(navigations[0][1])
    assert len(requests) == 8, requests
    assert all('cookie' not in headers for headers in requests), requests
    assert not unexpected, unexpected
    assert not errors, errors
    version = browser.version
    context.close()
    browser.close()
    print(f'{engine.name} {version}: PASS archived notice; unpublished/missing/partial/HTTP-error/timeout; '
          'two failed keyboard retries, then successful retry and navigation; '
          '4 targets and disclosures, 320/375/768/1440px and request/cookie checks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=['chromium', 'webkit', 'both'], default='both')
    args = parser.parse_args()
    with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                names = ['chromium', 'webkit'] if args.engine == 'both' else [args.engine]
                for name in names:
                    run(getattr(playwright, name), f'http://127.0.0.1:{server.server_port}')
        finally:
            server.shutdown()
