#!/usr/bin/env python3
"""Real cold-route loading/CLS regression for 17tnw2b2g24.

Build first. Requires Playwright Chromium (no silent skip). Each context is fresh;
route chunks are held until pending DOM is inspected, then genuinely released.
--record-baseline saves resolved short-page geometry before the product fix.
--baseline compares that geometry after the fix. --output retains every sample.
SELAHCUE_MARKETING_DIST can select an isolated production mutant output.
"""
import argparse
import json
import re
import socketserver
import statistics
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

import auth_pages_headless as auth
import responsive_sweep as sweep

OBSERVE = """(() => {
  window.__layout = { cls: 0, entries: [] };
  let start = 0, last = 0, session = 0;
  new PerformanceObserver(list => {
    for (const e of list.getEntries()) {
      if (e.hadRecentInput) continue;
      if (e.startTime - last > 1000 || e.startTime - start > 5000) {
        start = e.startTime; session = 0;
      }
      last = e.startTime; session += e.value;
      window.__layout.cls = Math.max(window.__layout.cls, session);
      window.__layout.entries.push({ value: e.value, time: e.startTime,
        sources: (e.sources || []).map(s => ({ node: s.node && s.node.className,
          before: s.previousRect.toJSON(), after: s.currentRect.toJSON() })) });
    }
  }).observe({ type: 'layout-shift', buffered: true });
})()"""

SNAPSHOT = """() => {
  const main = document.querySelector('.main-content');
  const footer = document.querySelector('.app-shell > footer');
  const status = document.querySelector('.loading');
  const nav = document.querySelector('.navbar-header');
  const box = el => el ? { top: el.getBoundingClientRect().top,
    height: el.getBoundingClientRect().height } : null;
  let contrast = null;
  if (status) {
    const rgb = s => s.match(/[\\d.]+/g).slice(0,3).map(Number);
    const lum = s => rgb(s).map(c => { c /= 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; })
      .reduce((v, c, i) => v + c * [.2126,.7152,.0722][i], 0);
    let bg = status;
    while (bg.parentElement && getComputedStyle(bg).backgroundColor === 'rgba(0, 0, 0, 0)') bg = bg.parentElement;
    const a = lum(getComputedStyle(status).color), b = lum(getComputedStyle(bg).backgroundColor);
    contrast = (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
  }
  return { width: innerWidth, height: innerHeight, overflow: document.documentElement.scrollWidth > innerWidth,
    main: box(main), mainMinimum: main && getComputedStyle(main).minHeight,
    footer: box(footer), footerVisibility: footer && getComputedStyle(footer).visibility, nav: box(nav), status: box(status), contrast,
    statusVisible: !!status && getComputedStyle(status).visibility === 'visible' && status.getBoundingClientRect().height > 0,
    statusRole: status && status.getAttribute('role'), statusText: status && status.textContent,
    statusFocused: status && document.activeElement === status,
    loadingMinimum: status && getComputedStyle(status).minHeight,
    layout: window.__layout };
}"""


def install_stubs(context):
    context.route('https://**', lambda route: route.abort())
    context.route('**/graphql/**', lambda route: route.fulfill(
        status=200, content_type='application/json', body='{"data":{"accountViewer":null}}'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--record-baseline', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--mode', choices=['all','pending','recovery'], default='all', help='all is the acceptance gate; targeted modes are for negative proofs')
    args = parser.parse_args()
    # The acceptance gate must never report against an old bundle. Targeted negative
    # modes deliberately allow retained mutant builds after source has been restored.
    if args.mode == 'all':
        stale = auth.check_bundle_is_current()
        if stale:
            raise RuntimeError(stale)
    failures, samples, short = [], [], {}
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None

    def check(condition, message):
        if not condition:
            failures.append(message)

    def run(browser, base, path, chunk, width, repetition):
        context = browser.new_context(viewport={'width': width, 'height': 900})
        context.add_init_script(OBSERVE)
        install_stubs(context)
        held = []
        context.route(re.compile(r'/assets/' + chunk + r'-[^/]+\.js(?:\?.*)?$'), lambda route: held.append(route))
        page = context.new_page()
        try:
            page.goto(base + path, wait_until='domcontentloaded')
            for _ in range(100):
                if held:
                    break
                page.wait_for_timeout(25)
            if not held:
                raise RuntimeError('Route chunk was never intercepted: ' + path)
            page.wait_for_timeout(700)
            pending = page.evaluate(SNAPSHOT)
            label = f'{path}@{width} run{repetition}'
            bare = path == '/signup'
            check(pending['width'] == width, label + ': wrong viewport')
            check(pending['status'] is not None and pending['statusVisible'], label + ': actual pending fallback is absent')
            check(pending['statusRole'] == 'status' and pending['statusText'] == 'Loading...', label + ': fallback must announce Loading...')
            check(pending['contrast'] is not None and pending['contrast'] >= 4.5, label + ': fallback contrast below 4.5')
            check(not pending['statusFocused'], label + ': fallback stole focus')
            check(not pending['overflow'], label + ': loading overflow')
            if bare:
                check(pending['nav'] is None and pending['footer'] is None, label + ': bare loading route exposes chrome')
            else:
                check(pending['footerVisibility'] == 'hidden', label + ': pending footer is not hidden')
                check(pending['footer'] is not None and pending['footer']['top'] >= pending['height'] - 1,
                      label + ': footer visible under fallback')
                check(pending['status'] is not None and pending['nav'] is not None and
                      pending['status']['height'] >= pending['height'] - pending['nav']['height'] - 1,
                      label + ': loading reservation missing')
            for request in held:
                request.continue_()
            page.locator('main h1').first.wait_for(state='visible')
            page.wait_for_timeout(700)
            resolved = page.evaluate(SNAPSHOT)
            check(resolved['status'] is None, label + ': loading reservation remains after resolution')
            check(not resolved['overflow'], label + ': resolved overflow')
            if bare:
                check(resolved['nav'] is None and resolved['footer'] is None, label + ': bare resolved route exposes chrome')
            if not bare:
                check(resolved['footerVisibility']=='visible',label + ': resolved footer remains hidden')
            if path in ('/pricing', '/changelog', '/not-a-real-page'):
                key = f'{path}@{width}'
                short[key] = {k: resolved[k] for k in ('main', 'mainMinimum', 'footer')}
                check(resolved['mainMinimum'] in ('auto','0px'), label + ': permanent main minimum introduced')
                check(abs(resolved['main']['top'] + resolved['main']['height'] - resolved['footer']['top']) <= 1,
                      label + ': footer no longer follows main')
                if baseline:
                    old = baseline[key]
                    check(resolved['mainMinimum'] == old['mainMinimum'], label + ': resolved main minimum changed')
                    check(all(abs(resolved[part][facet] - old[part][facet]) <= 1
                              for part, facet in [('main','height'), ('footer','top')]), label + ': short-page baseline geometry changed')
            sample = {'path': path, 'width': width, 'run': repetition, 'heldChunkObserved': True,
                      'pending': pending, 'resolved': resolved}
            samples.append(sample)
            print(json.dumps({'path': path, 'width': width, 'run': repetition,
                              'pendingStatus': pending['status'] is not None,
                              'pendingFooter': pending['footer'], 'cls': resolved['layout']['cls']}), flush=True)
        finally:
            context.close()

    def home_and_failure_checks(browser, base, width):
        context = browser.new_context(viewport={'width':width,'height':900})
        context.add_init_script(OBSERVE)
        install_stubs(context)
        page = context.new_page()
        try:
            page.goto(base + '/')
            page.locator('main h1').first.wait_for(state='visible')
            page.wait_for_timeout(700)
            eager = page.evaluate(SNAPSHOT)
            check(eager['layout']['cls'] < .1, f'Home@{width}: eager route gained a jump')
            check(eager['status'] is None, f'Home@{width}: loading remains on eager route')
            check(not eager['overflow'], f'Home@{width}: overflow')
            samples.append({'path':'/','width':width,'eager':eager})
        finally:
            context.close()
        context = browser.new_context(viewport={'width':width,'height':900})
        context.add_init_script(OBSERVE)
        install_stubs(context)
        held = []
        context.route(re.compile(r'/assets/PricingView-[^/]+\.js(?:\?.*)?$'), lambda route: held.append(route))
        page = context.new_page()
        try:
            page.goto(base + '/pricing',wait_until='domcontentloaded')
            for _ in range(100):
                if held: break
                page.wait_for_timeout(25)
            if not held: raise RuntimeError('Failure-path chunk never intercepted')
            page.wait_for_timeout(100)
            check(page.locator('.loading').count()==1,f'failed import@{width}: pending state was not reached')
            for request in held: request.abort('failed')
            page.wait_for_timeout(700)
            failed = page.evaluate(SNAPSHOT)
            check(failed['status'] is None,f'failed import@{width}: readiness rejection left loading stuck')
            check(failed['footerVisibility']=='visible',f'failed import@{width}: footer stays hidden after rejection')
            page.locator('.navbar-header a[href="/"]').first.click()
            page.wait_for_timeout(700)
            recovered = page.evaluate(SNAPSHOT)
            check(page.locator('main h1').count()>0 and recovered['status'] is None,
                  f'failed import@{width}: navbar Home navigation did not recover')
            samples.append({'path':'/pricing','width':width,'failedImport':failed,'recoveredHome':recovered})
        finally:
            context.close()

    with socketserver.ThreadingTCPServer(('127.0.0.1', 0), sweep.SpaHandler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_address[1]}'
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            browser_version = browser.version
            try:
                if args.mode == 'all':
                    for path, chunk in [('/pricing','PricingView'), ('/terms','TermsView')]:
                        for width in (375,1440):
                            for repetition in (1,2,3):
                                run(browser,base,path,chunk,width,repetition)
                    for width in (375,768,1440):
                        for path, chunk in [('/changelog','ChangelogView'),('/not-a-real-page','NotFoundView'),('/signup','SignUpView')]:
                            run(browser,base,path,chunk,width,1)
                    for width in (375,1440):
                        home_and_failure_checks(browser,base,width)
                    # Include the tablet breakpoint for both long routes without changing the 3-run CLS cells.
                    for path, chunk in [('/pricing','PricingView'),('/terms','TermsView')]:
                        run(browser,base,path,chunk,768,1)
                elif args.mode == 'pending':
                    run(browser,base,'/pricing','PricingView',375,1)
                else:
                    home_and_failure_checks(browser,base,375)
            finally:
                browser.close()
                server.shutdown()
    medians = {}
    if args.mode == 'all':
        for path in ('/pricing','/terms'):
            for width in (375,1440):
                values = [s['resolved']['layout']['cls'] for s in samples if s['path']==path and s['width']==width and 'resolved' in s]
                key = f'{path}@{width}'
                medians[key] = statistics.median(values)
                check(len(values)==3 and medians[key] < .1, key + ': CLS median must be below 0.1')
    if args.record_baseline:
        args.record_baseline.write_text(json.dumps(short,indent=2)+'\n')
    report = {'mode':args.mode,'chromiumVersion':browser_version,'viewportHeight':900,'minimumChunkDelayMs':700,'samples':samples,'medians':medians,'failures':failures}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'medians':medians,'failures':failures},indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
