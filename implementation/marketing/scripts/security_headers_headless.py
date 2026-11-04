#!/usr/bin/env python3
"""Fail closed against the shipping nginx image, never the Vite preview server.

CI builds/runs the image first. No font interception: the real Google stylesheet
and font must load under CSP. Only same-origin API data is stubbed; no live accounts.
"""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

def routes():
    paths = re.findall(r"path: '([^']+)'", (ROOT / 'src/router/index.ts').read_text())
    result = [p.replace(':id', 'csp-test-customer') for p in paths if 'pathMatch' not in p]
    # Enumerate the actual corpus rather than one representative dynamic article.
    script = """import { blogPosts } from './src/lib/content/blog.ts';
import { docsArticles } from './src/lib/content/docs.ts';
import { supportArticles } from './src/lib/content/support.ts';
console.log(JSON.stringify([...blogPosts.map(p=>'/blog/'+p.slug), ...docsArticles.map(p=>'/docs/'+p.category+'/'+p.slug), ...supportArticles.map(p=>'/support/'+p.category+'/'+p.slug)]));"""
    result += json.loads(subprocess.check_output(['node', '--input-type=module', '-e', script], cwd=ROOT, text=True))
    return sorted(set(result + ['/blog/missing-csp-article', '/docs/missing/article', '/support/missing/article', '/csp-not-found']))

def graphql(route):
    if route.request.method == 'GET':
        return route.fulfill(status=204, headers={'Set-Cookie': 'csrftoken=csp; Path=/'})
    body = route.request.post_data or ''
    if 'AccountViewer' in body:
        payload = {'data': {'accountViewer': {'surface': 'account', 'actorId': 'csp', 'orgId': 'csp'}}}
    else:
        payload = {'errors': [{'message': 'Test fixture', 'extensions': {'code': 'VALIDATION_FAILED'}}], 'data': None}
    route.fulfill(status=200, content_type='application/json', body=json.dumps(payload))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    for attempt in range(40):
        try:
            with urlopen(base, timeout=2) as response:
                policy = response.headers.get('Content-Security-Policy')
            break
        except URLError:
            if attempt == 39:
                raise
            time.sleep(.25)
    assert policy and "script-src 'self'" in policy, 'Missing enforced production CSP'
    all_routes = routes()
    with sync_playwright() as pw:
        for name in ('chromium', 'webkit'):
            browser = getattr(pw, name).launch(headless=True)
            context = browser.new_context()
            context.route('**/graphql/**', graphql)
            context.add_init_script("""window.cspViolations = [];
                document.addEventListener('securitypolicyviolation', e => window.cspViolations.push({directive:e.effectiveDirective, uri:e.blockedURI}));""")
            page = context.new_page()
            font_responses = []
            page.on('response', lambda response: font_responses.append(response.status) if response.url.startswith('https://fonts.gstatic.com/') else None)
            for index, path in enumerate(all_routes):
                response = page.goto(base + path, wait_until='networkidle')
                assert response and response.status == 200, (name, path, 'SPA response')
                assert response.headers.get('content-security-policy') == policy, (name, path, 'CSP')
                page.wait_for_function("document.querySelector('#app')?.innerText.trim().length > 20")
                page.evaluate('document.fonts.ready')
                if index % 20 == 0:
                    print(f'{name}: rendered {index + 1}/{len(all_routes)} routes', flush=True)
                assert not page.evaluate('window.cspViolations'), (name, path, page.evaluate('window.cspViolations'))
            # Fonts are a real browser fetch, never replaced with fixtures or silently skipped.
            assert page.evaluate("document.fonts.check('16px Inter')"), (name, 'Inter failed to load')
            assert page.evaluate("[...document.fonts].some(f => f.family === 'Inter' && f.status === 'loaded')"), (name, 'Inter font face absent')
            assert font_responses and all(status == 200 for status in font_responses), (name, 'real font response', font_responses)
            # Same-origin scripted auth and mobile scroll-lock use the real built app.
            page.goto(base + '/signin', wait_until='networkidle')
            page.get_by_label('Email', exact=True).fill('tester@example.org')
            page.get_by_label('Password', exact=True).fill('TestPassword123!')
            with page.expect_request('**/graphql/**'):
                page.get_by_role('button', name='Sign in', exact=True).click()
            page.wait_for_function("document.querySelector('form')?.getAttribute('aria-busy') === 'false'")
            assert not page.evaluate('window.cspViolations'), (name, 'auth submit CSP')
            page.set_viewport_size({'width': 375, 'height': 812})
            page.goto(base + '/features', wait_until='networkidle')
            page.get_by_role('button', name='Menu', exact=True).click()
            page.get_by_role('dialog', name='Site menu').wait_for(state='visible')
            page.get_by_role('button', name='Close menu', exact=True).click()
            assert not page.evaluate('window.cspViolations'), (name, 'mobile style CSP')
            asset = page.locator('script[src]').first.get_attribute('src')
            for path in (asset, '/assets/csp-missing.js', '/50x.html'):
                response = context.request.get(base + path)
                assert response.headers.get('content-security-policy') == policy, (name, path, 'header inheritance')
            # Real enforcement probe: execution must be refused, and the browser must emit
            # the violation. Merely finding a header would not establish protection.
            page.evaluate("""() => { const s=document.createElement('script'); s.textContent='window.cspProbeExecuted=true'; document.head.append(s); }""")
            page.wait_for_function('window.cspViolations.length > 0')
            assert page.evaluate('window.cspProbeExecuted !== true')
            assert any(v['directive'] == 'script-src-elem' and v['uri'] == 'inline' for v in page.evaluate('window.cspViolations'))
            print(f'{name}: {len(all_routes)} routes, real fonts, document/asset/error CSP, blocked inline script PASS', flush=True)
            browser.close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
