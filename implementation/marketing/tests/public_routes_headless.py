#!/usr/bin/env python3
"""Verify public acquisition against the built SPA with loopback-only account fixtures."""
import argparse
import json
import re
import threading
from http.cookies import CookieError, SimpleCookie
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright

from core_pages_headless import DIST, Server, SpaHandler

DOWNLOAD = '/download#public-downloads'
CSRF_PATH = '/graphql/csrf'
ACCOUNT_PATH = '/graphql/account'
SYNTHETIC_CSRF = 'SyntheticCsrfToken0123456789AbCd'
VERIFY_QUERY = 'mutation VerifyEmail($token: String!) { verifyEmail(token: $token) { verified } }'
VERIFY_CASES = (
    ('verify-success', 'synthetic-success', {'data': {'verifyEmail': {'verified': True}}}),
    ('verify-invalid', 'synthetic-invalid', {'errors': [{'extensions': {'code': 'VALIDATION_FAILED'}}]}),
)
BOOTSTRAP_RECEIPT = ('bootstrap', 200)
EXPECTED_POST_RECEIPTS = [(label, 200, True, True) for label, _, _ in VERIFY_CASES]
PENDING_AUTH_CASES = (
    ('/verify', 'VerifyView'), ('/reset', 'ResetView'),
    ('/VeRiFy/', 'VerifyView'), ('/ReSeT/', 'ResetView'),
)
PENDING_AUTH_TIMEOUT_MS = 10_000
DEPARTURE_PATH = '/__public_routes_auth_departure__'
EXCLUDED = (
    '/admin', '/admin/', '/admin/customers', '/admin/customers/example/',
    '/admin/users', '/admin/subscriptions', '/admin/licenses', '/admin/affiliates',
    '/admin/payouts', '/admin/settings', '/admin/unknown/nested/',
    '/affiliates/dashboard', '/affiliates/dashboard/', '/affiliates/referrals',
    '/affiliates/payouts', '/affiliates/resources', '/affiliates/settings', '/affiliates/help',
    '/affiliates/unknown/deeper/',
)


CSRF_TRACE_PREFIX = 'PUBLIC_ACQUISITION_CSRF '
CSRF_TRACE_LIMIT = 32
HEADER_STATES = ('absent', 'mismatch', 'duplicate', 'match')
COOKIE_PHASES = ('before-bootstrap', 'bootstrap-pending', 'bootstrap-resolved', 'bootstrap-rejected', 'after-post')

CSRF_TRACE_JS = r"""
({ origin, csrfPath, accountPath, token, prefix, limit }) => {
  if (location.origin !== origin || location.pathname !== '/verify') return;
  let count = 0;
  let phase = 'before-bootstrap';
  function emit(event) {
    if (count > limit) return;
    try {
      console.debug(prefix + JSON.stringify(count === limit ? ['overflow'] : event));
    } catch {
      // A diagnostic failure must never affect the request or cookie getter.
    }
    count++;
  }

  function propertyOwner(object, name) {
    for (let owner = object; owner; owner = Object.getPrototypeOf(owner)) {
      if (Object.hasOwn(owner, name)) return owner;
    }
    return null;
  }

  let cookieHook = false;
  try {
    const owner = propertyOwner(document, 'cookie');
    const descriptor = owner && Object.getOwnPropertyDescriptor(owner, 'cookie');
    if (descriptor?.configurable && typeof descriptor.get === 'function') {
      const originalGet = descriptor.get;
      Object.defineProperty(owner, 'cookie', {
        ...descriptor,
        get() {
          const value = Reflect.apply(originalGet, this, []);
          if (this === document && typeof value === 'string') {
            const match = value.split(';').some(part => part.trim() === 'csrftoken=' + token);
            emit(['cookie-read', phase, match]);
          }
          return value;
        },
      });
      cookieHook = true;
    }
  } catch {
    // Report unavailable rather than replace the original read path.
  }
  emit(['hook', 'cookie', cookieHook]);

  function headerState(headers) {
    if (headers === undefined) return 'absent';
    // graphqlRequest supplies a plain header record. Do not create or modify a Request.
    if (!headers || Object.getPrototypeOf(headers) !== Object.prototype) return 'unavailable';
    const matches = Object.entries(headers).filter(([name]) => name.toLowerCase() === 'x-csrftoken');
    if (matches.length === 0) return 'absent';
    if (matches.length > 1) return 'duplicate';
    return matches[0][1] === token ? 'match' : 'mismatch';
  }

  let fetchHook = false;
  try {
    const owner = propertyOwner(window, 'fetch');
    const descriptor = owner && Object.getOwnPropertyDescriptor(owner, 'fetch');
    if (typeof descriptor?.value === 'function') {
      const originalFetch = descriptor.value;
      Object.defineProperty(owner, 'fetch', {
        ...descriptor,
        value: function (...args) {
          const [input, init] = args;
          const bootstrap = init?.method === 'GET' && (input === csrfPath || input === origin + csrfPath);
          if (bootstrap) {
            phase = 'bootstrap-pending';
            emit(['bootstrap-start']);
          } else if (init?.method === 'POST' && (input === accountPath || input === origin + accountPath)) {
            try {
              emit(['post-header', headerState(init.headers)]);
            } catch {
              emit(['post-header', 'unavailable']);
            }
            phase = 'after-post';
          }

          let result;
          try {
            result = Reflect.apply(originalFetch, this, args);
          } catch (error) {
            if (bootstrap) {
              phase = 'bootstrap-rejected';
              emit(['bootstrap-threw']);
            }
            throw error;
          }
          if (bootstrap) {
            // Attach an observation only. The app receives the exact original Promise.
            try {
              result.then(
                response => {
                  phase = 'bootstrap-resolved';
                  emit(['bootstrap-resolved', response.status]);
                },
                () => {
                  phase = 'bootstrap-rejected';
                  emit(['bootstrap-rejected']);
                },
              );
            } catch {
              emit(['bootstrap-observer-unavailable']);
            }
          }
          return result;
        },
      });
      fetchHook = true;
    }
  } catch {
    // An unavailable hook is a diagnostic limitation, not a test result.
  }
  emit(['hook', 'fetch', fetchHook]);
}
"""


class CsrfTrace:
    def __init__(self):
        self.events = []
        self.overflow = False
        self.lock = threading.Lock()

    def add(self, event):
        with self.lock:
            if event == ['overflow'] or len(self.events) == CSRF_TRACE_LIMIT:
                self.overflow = True
            else:
                self.events.append(event)

    def on_console(self, message):
        if not message.text.startswith(CSRF_TRACE_PREFIX):
            return
        payload = message.text[len(CSRF_TRACE_PREFIX):]
        if len(payload) > 128:
            return
        try:
            event = json.loads(payload)
        except (ValueError, RecursionError):
            return
        if not isinstance(event, list):
            return
        match event:
            case ['hook', 'cookie' | 'fetch', flag] if type(flag) is bool:
                self.add(event)
            case ['cookie-read', phase, flag] if phase in COOKIE_PHASES and type(flag) is bool:
                self.add(event)
            case ['bootstrap-start' | 'bootstrap-rejected' | 'bootstrap-threw'
                  | 'bootstrap-observer-unavailable' | 'overflow']:
                self.add(event)
            case ['bootstrap-resolved', status] if type(status) is int and (status == 0 or 100 <= status <= 599):
                self.add(event)
            case ['post-header', state] if state in (*HEADER_STATES, 'unavailable'):
                self.add(event)

    def render(self):
        with self.lock:
            return json.dumps({'events': self.events, 'overflow': self.overflow}, separators=(',', ':'))


def csrf_header_state(values):
    if not values:
        return 'absent'
    if len(values) > 1:
        return 'duplicate'
    return 'match' if values[0] == SYNTHETIC_CSRF else 'mismatch'


def post_receipts(receipts):
    return [receipt for receipt in receipts if receipt[0] != 'bootstrap']


def assert_acquisition_receipts(receipts):
    assert receipts and receipts[0] == BOOTSTRAP_RECEIPT, receipts
    assert all(receipt == BOOTSTRAP_RECEIPT for receipt in receipts if receipt[0] == 'bootstrap'), receipts
    assert post_receipts(receipts) == EXPECTED_POST_RECEIPTS, receipts


class LocalSpaHandler(SpaHandler):
    def end_headers(self):
        self.send_header(
            'Content-Security-Policy',
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:",
        )
        super().end_headers()

    def send_fixture_json(self, status, value, set_csrf=False):
        body = json.dumps(value, separators=(',', ':')).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        if set_csrf:
            # HTTP loopback only. Production uses Secure outside debug.
            self.send_header('Set-Cookie', f'csrftoken={SYNTHETIC_CSRF}; Path=/; SameSite=Strict')
            self.send_header('X-CSRFToken', SYNTHETIC_CSRF)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != CSRF_PATH:
            if urlsplit(self.path).path.startswith('/graphql/'):
                self.send_error(404)
                return
            return super().do_GET()
        with self.server.receipt_lock:
            self.send_fixture_json(200, {'ready': True}, set_csrf=True)
            self.server.receipts.append(BOOTSTRAP_RECEIPT)
            if self.server.csrf_trace is not None:
                self.server.csrf_trace.add(['server-bootstrap', 200])

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
            posts = post_receipts(receipts)
            index = len(posts)
            if (not receipts or receipts[0] != BOOTSTRAP_RECEIPT
                    or index >= len(VERIFY_CASES) or posts != EXPECTED_POST_RECEIPTS[:index]):
                receipts.append(('unexpected-account-post', 400))
                self.send_error(400)
                return
            label, token, response = VERIFY_CASES[index]
            has_cookie = self.has_csrf_cookie()
            header = csrf_header_state(self.headers.get_all('X-CSRFToken', []))
            has_header = header == 'match'
            if not self.read_verification(token):
                status = 400
            elif not (has_cookie and has_header):
                status = 403
            else:
                status = 200
            receipts.append((label, status, has_cookie, has_header))
            if self.server.csrf_trace is not None:
                self.server.csrf_trace.add(['server-post', status, has_cookie, header])
            if status != 200:
                self.send_error(status)
                return
            self.send_fixture_json(status, response)


class AcquisitionServer(Server):
    def __init__(self):
        super().__init__(('127.0.0.1', 0), LocalSpaHandler)
        self.receipts = []
        self.receipt_lock = threading.Lock()
        self.csrf_trace = None


def check_pending_auth_departure(browser, base, path, chunk):
    canary = 'synthetic-pending-auth-' + uuid4().hex
    chunk_url = re.compile(re.escape(base) + rf'/assets/{chunk}-[^/?]+\.js$')
    context = browser.new_context(service_workers='block')
    held_routes = []
    releasing = False
    api_requested = False
    unexpected_request = False
    diagnostic_retained = False

    def is_chunk(request):
        return request.method == 'GET' and chunk_url.fullmatch(request.url) is not None

    def fixture(route):
        nonlocal api_requested, unexpected_request
        request = route.request
        url_path = urlsplit(request.url).path
        if is_chunk(request):
            if releasing:
                route.abort('aborted')
            else:
                # Keep the matching import pending until departure has been inspected.
                held_routes.append(route)
        elif url_path.startswith('/graphql/'):
            api_requested = True
            route.abort()
        elif request.method == 'GET' and request.url == base + DEPARTURE_PATH and request.is_navigation_request():
            route.fulfill(
                content_type='text/html; charset=utf-8',
                body='<!doctype html><html><title>Departure fixture</title><p id="auth-departure">Arrived</p></html>',
            )
        elif (request.method == 'GET' and request.url.startswith(base + '/')
              and (request.is_navigation_request() or url_path in ('/favicon.ico', '/selahcue-logo.png')
                   or url_path.startswith(('/assets/', '/fonts/', '/icons/')))):
            route.continue_()
        else:
            unexpected_request = True
            route.abort()

    def observe_diagnostic(text):
        nonlocal diagnostic_retained
        diagnostic_retained |= canary in text

    stage = 'setting up the pending landing fixture'
    try:
        context.route('**/*', fixture)
        page = context.new_page()
        page.on('console', lambda message: observe_diagnostic(message.text))
        page.on('pageerror', lambda error: observe_diagnostic(str(error)))

        stage = 'waiting for the pending landing'
        with page.expect_request(is_chunk, timeout=PENDING_AUTH_TIMEOUT_MS):
            response = page.goto(
                f'{base}{path}?token={canary}&extra=remove#pending',
                wait_until='commit', timeout=PENDING_AUTH_TIMEOUT_MS,
            )
        assert response and response.ok, f'{path}: landing fixture failed'
        expect(page.locator('#app .loading[role=status]')).to_be_visible(timeout=PENDING_AUTH_TIMEOUT_MS)
        assert held_routes, f'{path}: lazy bundle was not held'
        assert page.locator('#app main h1').count() == 0, f'{path}: auth view mounted before departure'
        assert not api_requested, f'{path}: account API requested before auth view mount'

        stage = 'observing the pending landing'
        before = page.evaluate("""([path, canary]) => {
            document.documentElement.dataset.pendingAuthOriginal = 'yes';
            sessionStorage.setItem('public-routes-auth-continuity', 'same-tab');
            return {
                cleanAddress: location.pathname === path && !location.search && !location.hash,
                cleanHistory: !JSON.stringify(history.state).includes(canary),
                cleanDom: !document.documentElement.outerHTML.includes(canary),
            };
        }""", [path, canary])

        stage = 'navigating to the inert same-origin document'
        response = page.goto(base + DEPARTURE_PATH, wait_until='domcontentloaded', timeout=PENDING_AUTH_TIMEOUT_MS)
        assert response and response.ok, f'{path}: departure fixture failed'
        after = page.evaluate("""([path, canary]) => {
            function storageHasCanary(storage) {
                for (let index = 0; index < storage.length; index++) {
                    const key = storage.key(index);
                    if (key.includes(canary) || storage.getItem(key).includes(canary)) return true;
                }
                return false;
            }
            return {
                departed: location.pathname === path && document.querySelector('#auth-departure') !== null
                    && !document.documentElement.hasAttribute('data-pending-auth-original'),
                sameTab: sessionStorage.getItem('public-routes-auth-continuity') === 'same-tab',
                cleanScroll: !(sessionStorage.getItem('vue-router:scroll') || '').includes(canary),
                cleanSession: !storageHasCanary(sessionStorage),
                cleanLocal: !storageHasCanary(localStorage),
                cleanCookies: !document.cookie.includes(canary),
                cleanDom: !document.documentElement.outerHTML.includes(canary),
            };
        }""", [DEPARTURE_PATH, canary])
        assert after['departed'] and after['sameTab'], f'{path}: expected a new document in the original tab'

        assert after['cleanScroll'], f'{path}: token retained in sessionStorage[vue-router:scroll] after departure'
        assert after['cleanSession'], f'{path}: token retained in sessionStorage after departure'
        assert after['cleanLocal'], f'{path}: token retained in localStorage after departure'
        assert after['cleanCookies'], f'{path}: token retained in readable cookies after departure'
        assert before['cleanAddress'], f'{path}: pending landing did not scrub its query and hash'
        assert before['cleanHistory'], f'{path}: token retained in pending landing history state'
        assert before['cleanDom'] and after['cleanDom'], f'{path}: token retained in document content or attributes'
        assert not diagnostic_retained, f'{path}: token retained in console or page-error diagnostics'
        assert not api_requested, f'{path}: account API requested during pending departure'
        assert not unexpected_request, f'{path}: unexpected request during pending departure'
    except PlaywrightError as error:
        # Playwright's error text can include the original navigation URL.
        raise AssertionError(f'{path}: browser operation failed while {stage} ({type(error).__name__})') from None
    finally:
        releasing = True
        try:
            for route in held_routes:
                route.abort('aborted')
            context.unroute_all(behavior='wait')
        finally:
            context.close()


def run(engine, server):
    base = f'http://127.0.0.1:{server.server_address[1]}'
    browser = engine.launch()
    browser_version = browser.version
    context = browser.new_context(viewport={'width': 1440, 'height': 900},
                                  service_workers='block', reduced_motion='reduce')
    unexpected, errors = [], []
    manifest_requests = []
    tab_key = 'Alt+Tab' if engine.name == 'webkit' else 'Tab'
    if engine.name == 'webkit':
        server.csrf_trace = CsrfTrace()
    trace = server.csrf_trace

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
            '3 hours of cloud transcription and 5 sermon notes per church each week',
        )
        signup = page.locator('main').get_by_role('link', name='Create an account')
        expect(signup).to_have_attribute('href', '/signup')
        tab_to(signup)
        page.keyboard.press('Enter')
        expect(page).to_have_url(base + '/signup')
        expect(page.locator('form input[type=email]')).to_be_visible()

        if trace is not None:
            page.on('console', trace.on_console)
            settings = json.dumps({
                'origin': base, 'csrfPath': CSRF_PATH, 'accountPath': ACCOUNT_PATH,
                'token': SYNTHETIC_CSRF, 'prefix': CSRF_TRACE_PREFIX, 'limit': CSRF_TRACE_LIMIT,
            })
            page.add_init_script(f'({CSRF_TRACE_JS})({settings})')
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

        with server.receipt_lock:
            assert_acquisition_receipts(server.receipts)
        assert len(manifest_requests) == 4, manifest_requests
        assert not unexpected, unexpected
        assert not errors, errors
        print('  Signup reached. Invalid/expired and missing verification preserve recovery. Only the synthetic account fixture and the public manifest received API requests.')
        pending_errors = []
        for path, chunk in PENDING_AUTH_CASES:
            try:
                check_pending_auth_departure(browser, base, path, chunk)
            except AssertionError as error:
                pending_errors.append(str(error))
                print(f'  FAIL {error}', flush=True)
            else:
                print(f'  {path}: same-tab departure from the pending landing left no token in checked surfaces.')
        return pending_errors
    finally:
        try:
            # Emit before closing so a browser assertion or close failure cannot hide the trace.
            print(f'  {engine.name} {browser_version} loopback receipts: {server.receipts}', flush=True)
            if trace is not None:
                print(CSRF_TRACE_PREFIX + trace.render(), flush=True)
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', default='both', choices=('both', 'chromium', 'webkit'))
    args = parser.parse_args()
    assert (DIST / 'index.html').is_file(), 'Build the marketing bundle before running this test'
    assets = sorted((DIST / 'assets').glob('*.js'))
    assert assets, 'Expected Vite JavaScript assets'
    mock_chunks = [asset.name for asset in assets if re.match(r'Admin|Affiliate(?!sView-)|PilotDownloads', asset.name)]
    assert not mock_chunks, f'Public build contains mock portal chunks: {mock_chunks}'

    pending_errors = []
    with sync_playwright() as playwright:
        for name in ('chromium', 'webkit') if args.engine == 'both' else (args.engine,):
            with AcquisitionServer() as server:
                threading.Thread(target=server.serve_forever, daemon=True).start()
                try:
                    print(f'[{name}] public acquisition and direct routes', flush=True)
                    pending_errors.extend(f'{name} {error}' for error in run(getattr(playwright, name), server))
                finally:
                    server.shutdown()
    assert not pending_errors, '\n'.join(pending_errors)
    print('PASS: public acquisition, archived download URL, verification, route exclusions and pending auth departures')


if __name__ == '__main__':
    main()
