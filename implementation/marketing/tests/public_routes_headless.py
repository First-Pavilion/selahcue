#!/usr/bin/env python3
"""Verify public acquisition against the built SPA with loopback-only account fixtures."""
import argparse
import json
import re
import threading
from http.cookies import CookieError, SimpleCookie
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from core_pages_headless import DIST, Server, SpaHandler

DOWNLOAD = '/download#public-downloads'
CSRF_PATH = '/graphql/csrf'
ACCOUNT_PATH = '/graphql/account'
SYNTHETIC_CSRF = 'synthetic'
VERIFY_QUERY = 'mutation VerifyEmail($token: String!) { verifyEmail(token: $token) { verified } }'
VERIFY_CASES = (
    ('verify-success', 'synthetic-success', {'data': {'verifyEmail': {'verified': True}}}),
    ('verify-invalid', 'synthetic-invalid', {'errors': [{'extensions': {'code': 'VALIDATION_FAILED'}}]}),
)
EXPECTED_RECEIPTS = [('bootstrap', 200), *((label, 200, True, True) for label, _, _ in VERIFY_CASES)]
EXCLUDED = (
    '/admin', '/admin/', '/admin/customers', '/admin/customers/example/',
    '/admin/users', '/admin/subscriptions', '/admin/licenses', '/admin/affiliates',
    '/admin/payouts', '/admin/settings', '/admin/unknown/nested/',
    '/affiliates/dashboard', '/affiliates/dashboard/', '/affiliates/referrals',
    '/affiliates/payouts', '/affiliates/resources', '/affiliates/settings', '/affiliates/help',
    '/affiliates/unknown/deeper/',
)


class LocalSpaHandler(SpaHandler):
    def end_headers(self):
        self.send_header(
            'Content-Security-Policy',
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:",
        )
        super().end_headers()

    def send_fixture_json(self, status, value, set_cookie=False):
        body = json.dumps(value, separators=(',', ':')).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        if set_cookie:
            # HTTP loopback only. Production uses Secure outside debug.
            self.send_header('Set-Cookie', f'csrftoken={SYNTHETIC_CSRF}; Path=/; SameSite=Strict')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != CSRF_PATH:
            if urlsplit(self.path).path.startswith('/graphql/'):
                self.send_error(404)
                return
            return super().do_GET()
        with self.server.receipt_lock:
            status = 409 if self.server.receipts else 200
            self.send_fixture_json(status, {'ready': status == 200}, set_cookie=status == 200)
            self.server.receipts.append(('bootstrap', status))

    def read_verification(self, token):
        lengths = self.headers.get_all('Content-Length', [])
        if (len(lengths) != 1 or not re.fullmatch(r'[0-9]{1,4}', lengths[0])
                or not 0 < int(lengths[0]) <= 1024
                or self.headers.get('Transfer-Encoding') is not None
                or self.headers.get_content_type() != 'application/json'):
            return False
        length = int(lengths[0])
        body = self.rfile.read(length)
        if len(body) != length:
            return False
        try:
            data = json.loads(body)
        except (ValueError, RecursionError):
            return False
        return (isinstance(data, dict) and set(data) == {'query', 'variables'}
                and isinstance(data['query'], str) and ' '.join(data['query'].split()) == VERIFY_QUERY
                and data['variables'] == {'token': token})

    def has_csrf_cookie(self):
        values = self.headers.get_all('Cookie', [])
        if len(values) != 1:
            return False
        # Require an unambiguous token if a request supplies multiple cookies.
        names = [part.partition('=')[0].strip() for part in values[0].split(';')]
        if names.count('csrftoken') != 1:
            return False
        try:
            cookie = SimpleCookie(values[0]).get('csrftoken')
        except CookieError:
            return False
        return cookie is not None and cookie.value == SYNTHETIC_CSRF

    def do_POST(self):
        if self.path != ACCOUNT_PATH:
            self.send_error(404)
            return
        with self.server.receipt_lock:
            receipts = self.server.receipts
            index = len(receipts) - 1
            if not 0 <= index < len(VERIFY_CASES) or receipts != EXPECTED_RECEIPTS[:len(receipts)]:
                receipts.append(('unexpected-account-post', 400))
                self.send_error(400)
                return
            label, token, response = VERIFY_CASES[index]
            has_cookie = self.has_csrf_cookie()
            has_header = self.headers.get_all('X-CSRFToken', []) == [SYNTHETIC_CSRF]
            if not self.read_verification(token):
                status = 400
            elif not (has_cookie and has_header):
                status = 403
            else:
                status = 200
            receipts.append((label, status, has_cookie, has_header))
            if status != 200:
                self.send_error(status)
                return
            self.send_fixture_json(status, response)


class AcquisitionServer(Server):
    def __init__(self):
        super().__init__(('127.0.0.1', 0), LocalSpaHandler)
        self.receipts = []
        self.receipt_lock = threading.Lock()


def run(engine, server):
    base = f'http://127.0.0.1:{server.server_address[1]}'
    browser = engine.launch()
    browser_version = browser.version
    context = browser.new_context(viewport={'width': 1440, 'height': 900},
                                  service_workers='block', reduced_motion='reduce')
    unexpected, errors = [], []
    manifest_requests = []
    tab_key = 'Alt+Tab' if engine.name == 'webkit' else 'Tab'

    def fixture(route):
        request = route.request
        url = urlsplit(request.url)
        if (request.method, request.url) in (('GET', base + CSRF_PATH), ('POST', base + ACCOUNT_PATH)):
            route.continue_()
        elif request.url == base + '/releases/current.json' and request.method == 'GET':
            manifest_requests.append(request.url)
            route.continue_()
        elif (request.url.startswith(base + '/') and request.method == 'GET' and
              not url.path.startswith('/graphql/') and
              (request.is_navigation_request() or url.path in ('/favicon.ico', '/selahcue-logo.png')
               or url.path.startswith(('/assets/', '/fonts/', '/icons/')))):
            route.continue_()
        else:
            unexpected.append((request.method, request.url))
            route.abort()

    def assert_scrolled_to_downloads():
        expect(page.locator('#public-downloads [role=status]')).to_contain_text(
            'Desktop installers are not available to download yet',
        )
        page.wait_for_function("""() => {
            const panel = document.querySelector('#public-downloads').getBoundingClientRect();
            const nav = document.querySelector('#app header').getBoundingClientRect();
            return panel.top >= nav.bottom - 1 && panel.top <= nav.bottom + 32;
        }""")
        expect(page.locator('#public-downloads').get_by_role('link')).to_have_count(0)

    def tab_to(target):
        for _ in range(20):
            if target.evaluate("(element) => element === document.activeElement"):
                break
            page.keyboard.press(tab_key)
        expect(target).to_be_focused()
        assert target.evaluate("element => element.matches(':focus-visible')")

    context.route('**/*', fixture)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        for path in EXCLUDED:
            response = page.goto(base + path)
            assert response and response.status == 200, 'expected the local SPA fixture, which serves the shell'
            expect(page.get_by_role('heading', level=1)).to_have_text("We couldn't find that page")
            expect(page).to_have_url(base + path)
            expect(page.get_by_role('link', name='Go to the home page')).to_have_attribute('href', '/')
        page.goto(base + '/affiliates')
        expect(page.locator('main')).to_contain_text('The affiliate program is not open yet.')
        expect(page.locator("main a[href^='/affiliates/'], main a[href='/signin']")).to_have_count(0)
        print(f'  {len(EXCLUDED)} former portal paths reach the SPA catch-all. Closed affiliate landing remains.')

        for width in (1440, 375):
            page.set_viewport_size({'width': width, 'height': 900})
            page.goto(base + '/')
            if width == 375:
                menu = page.get_by_role('button', name='Menu')
                tab_to(menu)
                page.keyboard.press('Enter')
            primary = page.get_by_role('navigation', name='Primary')
            link = primary.get_by_role('link', name='Download', exact=True)
            expect(link).to_have_attribute('href', DOWNLOAD)
            tab_to(link)
            page.keyboard.press('Enter')
            expect(page).to_have_url(base + DOWNLOAD)
            assert_scrolled_to_downloads()
            if width == 375:
                expect(page.get_by_role('dialog')).to_have_count(0)
            else:
                footer_link = page.locator('footer').get_by_role('link', name='Download', exact=True)
                expect(footer_link).to_have_attribute('href', DOWNLOAD)
            print(f'  {width}px navbar download opens the public installer section using the keyboard.')

        page.goto(base + '/')
        page.goto(base + '/download#pilot-downloads')
        expect(page).to_have_url(base + '/download#pilot-downloads')
        assert_scrolled_to_downloads()
        assert len(manifest_requests) == 3, manifest_requests

        page.goto(base + '/pricing')
        expect(page.locator('main')).to_contain_text(
            '20 cloud transcription minutes and 1 sermon note per church per week',
        )
        signup = page.locator('main').get_by_role('link', name='Create an account')
        expect(signup).to_have_attribute('href', '/signup')
        tab_to(signup)
        page.keyboard.press('Enter')
        expect(page).to_have_url(base + '/signup')
        expect(page.locator('form input[type=email]')).to_be_visible()

        page.goto(base + '/verify?token=synthetic-success')
        verified = page.get_by_role('heading', name='Email address verified')
        expect(verified).to_be_focused()
        expect(page.locator('main')).to_contain_text('sign in and activate your device')
        expect(page.locator('main')).not_to_contain_text(re.compile(r'licen[cs]e (is active|has been issued)', re.I))
        download = page.get_by_role('link', name='View downloads')
        expect(download).to_have_attribute('href', DOWNLOAD)
        tab_to(download)
        page.keyboard.press('Enter')
        expect(page).to_have_url(base + DOWNLOAD)
        assert_scrolled_to_downloads()
        print('  Legacy download bookmark and verification success land at the public installer cards.')

        page.goto(base + '/verify?token=synthetic-invalid')
        expect(page.get_by_role('heading', name="This verification link didn't work")).to_be_focused()
        expect(page.locator('main')).to_contain_text('may have expired')
        expect(page.get_by_role('button', name='Send a new verification link')).to_be_visible()
        page.goto(base + '/verify')
        expect(page.get_by_role('heading', name='This page needs a verification link')).to_be_visible()
        expect(page.get_by_role('button', name='Send a verification link')).to_be_visible()

        assert server.receipts == EXPECTED_RECEIPTS, server.receipts
        assert len(manifest_requests) == 4, manifest_requests
        assert not unexpected, unexpected
        assert not errors, errors
        print('  Signup reached. Invalid/expired and missing verification preserve recovery. Only the synthetic account fixture and the public manifest received API requests.')
    finally:
        browser.close()
        # Only response status and expected cookie/header matches, never raw request values.
        print(f'  {engine.name} {browser_version} loopback receipts: {server.receipts}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', default='both', choices=('both', 'chromium', 'webkit'))
    args = parser.parse_args()
    assert (DIST / 'index.html').is_file(), 'Build the marketing bundle before running this test'
    assets = sorted((DIST / 'assets').glob('*.js'))
    assert assets, 'Expected Vite JavaScript assets'
    mock_chunks = [asset.name for asset in assets if re.match(r'Admin|Affiliate(?!sView-)|PilotDownloads', asset.name)]
    assert not mock_chunks, f'Public build contains mock portal chunks: {mock_chunks}'

    with sync_playwright() as playwright:
        for name in ('chromium', 'webkit') if args.engine == 'both' else (args.engine,):
            with AcquisitionServer() as server:
                threading.Thread(target=server.serve_forever, daemon=True).start()
                try:
                    print(f'[{name}] public acquisition and direct routes', flush=True)
                    run(getattr(playwright, name), server)
                finally:
                    server.shutdown()
    print('PASS: public acquisition, archived download URL, verification and route exclusions')


if __name__ == '__main__':
    main()
