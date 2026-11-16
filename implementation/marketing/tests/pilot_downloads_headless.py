#!/usr/bin/env python3
"""P14 actual built Vue pilot journey. All ready configuration/form responses are fixtures.
No remote form submission, Google Sheet write, provider operation or installer download.
Requires Playwright Chromium and WebKit; missing engines are failures, never silent skips.
Run after npm run build: python3 tests/pilot_downloads_headless.py --shots /tmp/pilot-shots
"""
import argparse
import copy
import http.server
import json
import socketserver
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'dist'), **kwargs)
    def log_message(self, *args):
        pass
    def do_GET(self):
        if not (ROOT / 'dist' / self.path.split('?')[0].lstrip('/')).is_file():
            self.path = '/index.html'
        return super().do_GET()

def fixture():
    return {'schema_version': 1, 'enabled': True, 'form_origin': 'https://registration.example.org',
        'notice': {'approved': True, 'version': 'fixture-v1', 'url': 'https://selahcue.example.org/pilot-privacy', 'data_owner': 'Fixture coordinator', 'retention_days': 180},
        'entries': [{'platform': platform, 'architecture': arch, 'version': '0.1.0-pilot.1', 'release_id': 'fixture-1', 'expires_at': '2027-04-30T23:59:59Z', 'available': True, 'registration_url': 'https://registration.example.org/form/fixture-' + platform.lower()}
            for platform, arch in [('Windows', 'x64'), ('Ubuntu', 'x64'), ('macOS', 'arm64')]]}

def run(engine, base, shots):
    browser = engine.launch()
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    mode = {'value': fixture()}
    pending = []
    mode['value'] = 'pending'
    def config(route):
        if mode['value'] == 'pending':
            pending.append(route)
        elif mode['value'] == 'error':
            route.fulfill(status=503, content_type='application/json', body='{}')
        else:
            route.fulfill(content_type='application/json', body=json.dumps(mode['value']))
    page.route('**/pilot-downloads.json', config)
    page.emulate_media(reduced_motion='reduce')
    page.goto(base + '/')
    page.locator('.hero-section').get_by_role('link', name='View pilot downloads').click()
    panel = page.locator('#pilot-downloads')
    action = panel.get_by_role('link', name='Continue to registration', exact=True)
    expect(panel).to_contain_text('Checking pilot availability')
    expect(panel.get_by_role('button', name='Continue to registration', exact=True)).to_be_disabled()
    assert len(pending) == 1
    mode['value'] = fixture()
    pending[0].fulfill(content_type='application/json', body=json.dumps(mode['value']))
    expect(action).to_be_visible()
    page.wait_for_function("document.querySelector('#pilot-heading').getBoundingClientRect().top >= document.querySelector('header').getBoundingClientRect().bottom")
    expect(panel).to_contain_text('2027-04-30 23:59:59 UTC')
    expect(panel).to_contain_text('internet access and consent')
    expect(panel).to_contain_text('core offline controls remain available')
    expect(panel).to_contain_text('Fixture coordinator')
    expect(panel).to_contain_text('180 days')
    expect(page.locator('button', has_text='Download for Windows')).to_be_disabled()
    expect(page.locator('button', has_text='Download for macOS')).to_be_disabled()
    first = action.get_attribute('href')
    query = parse_qs(urlparse(first).query)
    assert set(query) == {'registration_id', 'platform'} and query['platform'] == ['Windows']
    page.reload()
    expect(action).to_have_attribute('href', first)
    page.get_by_label('Operating system').focus()
    page.keyboard.press('Tab')
    expect(page.get_by_label('Processor architecture')).to_be_focused()
    page.get_by_label('Operating system').select_option('Ubuntu')
    expect(action).to_have_attribute('href', __import__('re').compile('.*platform=Ubuntu$'))
    page.get_by_label('Operating system').select_option('macOS')
    expect(panel.get_by_role('button', name='Continue to registration', exact=True)).to_be_disabled()
    page.get_by_label('Processor architecture').select_option('arm64')
    expect(action).to_be_visible()
    assert parse_qs(urlparse(action.get_attribute('href')).query)['platform'] == ['macOS']
    page.get_by_label('Operating system').select_option('Windows')
    page.get_by_label('Processor architecture').select_option('x64')
    expect(action).to_have_attribute('href', first)
    panel.get_by_role('button', name='Start a new registration', exact=True).click()
    expect(action).not_to_have_attribute('href', first)
    next_href = action.get_attribute('href')
    navigated = []
    def form(route):
        navigated.append(route.request.url)
        route.fulfill(content_type='text/html', body='<h1>Fixture hosted form only</h1>')
    page.route('https://registration.example.org/**', form)
    action.focus()
    page.keyboard.press('Enter')
    expect(page.get_by_role('heading', name='Fixture hosted form only')).to_be_visible()
    assert navigated == [next_href]
    page.goto(base + '/download#pilot-downloads')
    expect(action).to_have_attribute('href', next_href)
    for width in [320, 375, 768, 1440]:
        page.set_viewport_size({'width': width, 'height': 1000})
        panel.scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), str(width) + ' overflow'
        if width in [375, 1440]:
            page.screenshot(path=str(shots / (engine.name + '-ready-' + str(width) + '.png')), full_page=True)
    mode['value'] = {'schema_version': 1, 'enabled': False}
    page.reload()
    expect(panel).to_contain_text('Pilot registration is not open yet')
    expect(panel.locator('a')).to_have_count(0)
    mode['value'] = 'error'
    page.reload()
    expect(panel).to_contain_text('couldn’t check pilot availability')
    expect(panel.locator('a')).to_have_count(0)
    mode['value'] = fixture()
    panel.get_by_role('button', name='Retry availability check').click()
    expect(action).to_be_visible()
    mode['value'] = fixture()
    mode['value']['notice']['approved'] = False
    page.reload()
    expect(panel).to_contain_text('couldn’t check pilot availability')
    expect(panel.locator('a')).to_have_count(0)
    mode['value'] = fixture()
    for item in mode['value']['entries']:
        item['expires_at'] = '2026-01-01T00:00:00Z'
    page.reload()
    expect(panel).to_contain_text('This pilot package has expired')
    expect(panel.get_by_role('button', name='Continue to registration', exact=True)).to_be_disabled()
    # Runtime expiry without navigation, including interval-driven removal of href.
    mode['value'] = fixture()
    page.clock.install(time=datetime(2027, 4, 30, 23, 59, 58, tzinfo=timezone.utc))
    page.reload()
    expect(action).to_be_visible()
    page.clock.fast_forward(2500)
    expect(panel).to_contain_text('This pilot package has expired')
    expect(panel.get_by_role('button', name='Continue to registration', exact=True)).to_be_disabled()
    assert not errors, errors
    context.close()
    # Session storage unavailable: no silent identity replacement, no navigable form.
    blocked = browser.new_context(viewport={'width': 375, 'height': 900})
    p = blocked.new_page()
    p.add_init_script("Object.defineProperty(window, 'sessionStorage', {get(){throw new Error('storage blocked')}})")
    p.route('**/pilot-downloads.json', lambda route: route.fulfill(content_type='application/json', body=json.dumps(fixture())))
    p.goto(base + '/download#pilot-downloads')
    expect(p.get_by_role('alert')).to_contain_text('couldn’t safely retain')
    expect(p.locator('#pilot-downloads').get_by_role('button', name='Continue to registration', exact=True)).to_be_disabled()
    blocked.close()
    browser.close()
    print(engine.name + ': PASS ready/selection/keyboard/navigation/retry/policy/expiry/storage/responsive fixture scenarios')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shots', type=Path, required=True)
    args = parser.parse_args()
    args.shots.mkdir(parents=True, exist_ok=True)
    with Server(('127.0.0.1', 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with sync_playwright() as playwright:
            for engine in [playwright.chromium, playwright.webkit]:
                run(engine, 'http://127.0.0.1:' + str(server.server_address[1]), args.shots)
        server.shutdown()
    print('PASS both required engines; all ready states were local fixtures, no live registration or download')
