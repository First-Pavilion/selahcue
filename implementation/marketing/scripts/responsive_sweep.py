#!/usr/bin/env python3
"""Responsive sweep: every marketing-site route at every spec width, in a real browser.

GAP-07 (ClickUp 17tnw2b0q9g) acceptance: "No horizontal scroll at 320, 375, 768, 1024 and
1440px on any route". This serves the REAL production bundle from `dist/` (same SPA-fallback
server pattern as `auth_pages_headless.py`), drives it with Playwright, and for every
route x width asserts:

  1. `document.documentElement.scrollWidth <= window.innerWidth` -- the page itself does
     not scroll sideways. This reads the DOCUMENT, so an `overflow-x: hidden` painted on
     `body` to hide a symptom does not satisfy it: `scrollWidth` still reports the real
     content width. (Intentional scroll containers -- a wide table inside its own
     `overflow-x: auto` wrapper -- are fine; their content does not widen the document.)
  2. The route actually rendered something (the 404 page and an empty `<main>` are
     different failures; a blank page would otherwise pass check 1 trivially).
  3. Below 768px the hamburger is visible and the desktop nav is not; at/above 768px the
     reverse. (Skipped on bare routes, which have no nav.)
  4. Touch targets: every visible, in-flow link/button/input/select in the site chrome and
     in the mobile nav sheet is >= 44px in its smaller dimension at <768px -- see
     `TOUCH_SCOPES`. Inline text links inside running prose are exempt (WCAG 2.5.8
     inline exception), so only chrome and form controls are scoped.

It also exercises, in the real browser, the behaviours CSS alone cannot prove:

  * the mobile nav sheet (open, focus moves in, Tab/Shift+Tab are trapped, Escape closes
    and restores focus to the toggle, `aria-expanded` tracks, the sheet covers the whole
    viewport even after the header has gone `backdrop-filter` on scroll, and the page
    scroll lock is set while open and RELEASED on every way out: Escape, close button,
    scrim, link tap, history navigation, and the viewport growing past 768px);
  * the footer (collapsed sections on mobile with working `aria-expanded` toggles, 2x2 on
    tablet, 4 across on desktop);
  * the signed-in navbar (Account / Sign out) still fits one row at tablet widths.

On a failure it prints the offending elements (those whose right edge is past the
viewport and which are not inside a scroll container) so the cause is visible without a
second run.

Auth-gated routes are served a stubbed `/graphql/account` (a live `accountViewer`), so
`/account` renders its real content instead of bouncing to /signin. Google Fonts is
aborted: the run must not depend on the network, and the fallback stack is the more
demanding case (it is not narrower than Inter in practice, but a layout that only fits
with the web font is a layout that breaks on first paint).

Usage:
    npm run build
    python3 scripts/responsive_sweep.py [--engine chromium|webkit] [--shots DIR] [--routes /a,/b]

Needs Playwright (`pip install playwright && playwright install chromium webkit`). If it
is missing this exits 0 with a LOUD skip unless SELAHCUE_SWEEP_REQUIRE=1, which turns a
missing engine into a hard failure so a CI gate can never silently no-op.

Exit codes: 0 pass (or loud skip), 1 a check failed, 2 infrastructure problem (no dist,
a route failed to load), 3 required engine unavailable.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETING = HERE.parent
DIST = Path(os.environ.get("SELAHCUE_MARKETING_DIST") or (MARKETING / "dist"))
REQUIRE = os.environ.get("SELAHCUE_SWEEP_REQUIRE") == "1"

WIDTHS = [320, 375, 768, 1024, 1440]
HEIGHT = 800

# (path, bare). `bare` routes render no site nav/footer (meta.bare in the router).
ROUTES: list[tuple[str, bool]] = [
    ("/", False),
    ("/features", False),
    ("/pricing", False),
    ("/download", False),
    ("/about", False),
    ("/contact", False),
    ("/support", False),
    ("/docs", False),
    ("/changelog", False),
    ("/blog", False),
    ("/careers", False),
    ("/privacy", False),
    ("/terms", False),
    ("/affiliates", False),
    ("/signin", True),
    ("/signup", True),
    ("/forgot-password", True),
    ("/verify?token=sweep-token-0123456789", True),
    ("/reset?token=sweep-token-0123456789", True),
    ("/account", False),
    ("/affiliates/dashboard", False),
    ("/affiliates/referrals", False),
    ("/affiliates/payouts", False),
    ("/affiliates/resources", False),
    ("/affiliates/settings", False),
    ("/affiliates/help", False),
    ("/admin", False),
    ("/admin/customers", False),
    ("/admin/customers/cus_001", False),
    ("/admin/users", False),
    ("/admin/subscriptions", False),
    ("/admin/licenses", False),
    ("/admin/affiliates", False),
    ("/admin/payouts", False),
    ("/admin/settings", False),
    ("/this-route-does-not-exist", False),  # the 404
]

# Containers whose interactive descendants must be >= 44px tall/wide at <768px. Inline links
# in prose are deliberately not listed.
TOUCH_SCOPES = [
    ".navbar-header a, .navbar-header button",
    ".footer a",
    "main button, main input:not([type=checkbox]):not([type=radio]), main select, main textarea",
    "main .btn, main a.btn",
]

# Which layout the browser ACTUALLY chose, straight from the same media query the CSS uses.
# Comparing against `width < 768` instead would be wrong in exactly one case: WebKit counts
# a classic scrollbar (main.css restyles `::-webkit-scrollbar`, which forces one on macOS)
# inside the viewport the media query sees, so a 768px window is, correctly, a mobile
# layout there. The breakpoint is the contract; the window size is only how we get to it.
IS_MOBILE_JS = "matchMedia('(max-width: 767px)').matches"

PAGE_JS = r"""
() => {
  const vw = window.innerWidth;
  const doc = document.documentElement;
  const out = { vw, scrollWidth: doc.scrollWidth, bodyScrollWidth: document.body.scrollWidth, offenders: [] };

  const clipsX = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return true;
    }
    return false;
  };
  const describe = (el) => {
    const r = el.getBoundingClientRect();
    const cls = (el.className && el.className.baseVal === undefined ? String(el.className) : '').trim().split(/\s+/).slice(0, 3).join('.');
    return `${el.tagName.toLowerCase()}${cls ? '.' + cls : ''} [${Math.round(r.left)}..${Math.round(r.right)}]`;
  };
  if (doc.scrollWidth > vw) {
    for (const el of document.querySelectorAll('body *')) {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.position === 'fixed') continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (r.right > vw + 0.5 && !clipsX(el)) out.offenders.push(describe(el));
      if (out.offenders.length >= 12) break;
    }
  }
  // Content that is past the viewport edge but HIDDEN rather than scrolling: an
  // `overflow-x: hidden` wrapper makes scrollWidth look fine while text is cut off. Only
  // real scroll containers (auto/scroll) are allowed to hold content wider than the screen.
  const scrollsX = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll') return true;
    }
    return false;
  };
  out.clipped = [];
  for (const el of document.querySelectorAll('body *')) {
    if (out.clipped.length >= 8) break;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.pointerEvents === 'none') continue;
    if (cs.position === 'fixed') continue;
    if (el.closest('[aria-hidden=true]')) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    const isLeaf = hasText || /^(IMG|SVG|BUTTON|INPUT|SELECT|TEXTAREA|A)$/.test(el.tagName);
    if (!isLeaf) continue;
    if ((r.right > vw + 1 || r.left < -1) && !scrollsX(el)) out.clipped.push(describe(el));
  }
  const main = document.querySelector('main');
  out.mainTextLength = main ? main.innerText.trim().length : 0;
  out.title = (document.querySelector('h1') || {}).innerText || '';
  return out;
}
"""

NAV_STATE_JS = r"""
() => {
  const vis = (el) => !!el && getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().width > 0;
  return {
    hasHeader: !!document.querySelector('.navbar-header'),
    toggleVisible: vis(document.querySelector('.mobile-toggle')),
    desktopNavVisible: vis(document.querySelector('.desktop-nav')),
  };
}
"""

TOUCH_JS = r"""
(selectors) => {
  const bad = [];
  const seen = new Set();
  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      if (seen.has(el)) continue;
      seen.add(el);
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      if (el.closest('[hidden], [aria-hidden=true]')) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      // Inline links inside running prose are exempt (WCAG 2.5.8 inline exception).
      if (el.tagName === 'A' && cs.display === 'inline' && el.closest('p, li, dd, blockquote')) continue;
      if (Math.min(r.width, r.height) < 43.5) {
        const cls = (typeof el.className === 'string' ? el.className : '').trim().split(/\s+/).slice(0, 2).join('.');
        bad.push(`${el.tagName.toLowerCase()}${cls ? '.' + cls : ''} "${(el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 24)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
      }
    }
  }
  return bad.slice(0, 12);
}
"""


SHEET_STATE_JS = r"""
() => {
  const sheet = document.querySelector('#mobile-nav-sheet');
  const toggle = document.querySelector('.mobile-toggle');
  const r = sheet ? sheet.getBoundingClientRect() : null;
  const active = document.activeElement;
  return {
    open: !!sheet,
    expanded: toggle ? toggle.getAttribute('aria-expanded') : null,
    toggleLabel: toggle ? toggle.getAttribute('aria-label') : null,
    activeInSheet: !!(sheet && active && sheet.contains(active)),
    activeIsToggle: active === toggle,
    activeLabel: active ? (active.getAttribute('aria-label') || active.innerText || '').trim().slice(0, 30) : '',
    htmlOverflow: document.documentElement.style.overflow,
    bodyOverflow: document.body.style.overflow,
    sheetTop: r ? Math.round(r.top) : null,
    sheetBottom: r ? Math.round(r.bottom) : null,
    sheetRight: r ? Math.round(r.right) : null,
    innerHeight: window.innerHeight,
    innerWidth: window.innerWidth,
    role: sheet ? sheet.getAttribute('role') : null,
    modal: sheet ? sheet.getAttribute('aria-modal') : null,
    linkHeights: sheet ? [...sheet.querySelectorAll('.mobile-link')].map((a) => Math.round(a.getBoundingClientRect().height)) : [],
    cta: (() => { const c = sheet && sheet.querySelector('.sheet-cta'); if (!c) return null; const b = c.getBoundingClientRect(); return { bottom: Math.round(b.bottom), width: Math.round(b.width), sheetWidth: Math.round(r.width) - 40 }; })(),
  };
}
"""

FOOTER_STATE_JS = r"""
() => {
  const cols = [...document.querySelectorAll('.footer .link-column')];
  const vis = (el) => !!el && getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().height > 0;
  return {
    toggles: [...document.querySelectorAll('.footer .column-toggle')].map((b) => ({
      expanded: b.getAttribute('aria-expanded'),
      controlsVisible: vis(document.getElementById(b.getAttribute('aria-controls'))),
      height: Math.round(b.getBoundingClientRect().height),
    })),
    lefts: [...new Set(cols.map((c) => Math.round(c.getBoundingClientRect().left)))],
    linksVisible: [...document.querySelectorAll('.footer .footer-link')].filter(vis).length,
    linksTotal: document.querySelectorAll('.footer .footer-link').length,
  };
}
"""

NAV_ROW_JS = r"""
() => {
  const bar = document.querySelector('.navbar-container');
  const kids = [...bar.querySelectorAll('.brand, .desktop-nav a, .right-group > *')].filter((e) => e.getBoundingClientRect().width > 0);
  const tops = kids.map((e) => Math.round(e.getBoundingClientRect().top));
  const lastRight = Math.max(...kids.map((e) => e.getBoundingClientRect().right));
  return { barHeight: Math.round(bar.getBoundingClientRect().height), spread: Math.max(...tops) - Math.min(...tops), lastRight: Math.round(lastRight), vw: window.innerWidth, signedIn: !!document.querySelector('.signout-btn') };
}
"""

SESSION_HINT_INIT = """
localStorage.setItem('selahcue.session', JSON.stringify({role: 'owner', orgId: 'org_sweep', expiresAt: new Date(Date.now() + 864e5).toISOString()}));
"""


class SpaHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dist/ with SPA fallback to index.html for client-routed paths."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, *args):  # keep the run quiet
        pass

    def do_GET(self):  # noqa: N802 (stdlib naming)
        path = self.path.split("?", 1)[0]
        candidate = DIST / path.lstrip("/")
        if path != "/" and candidate.is_file():
            return super().do_GET()
        body = (DIST / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def skip_or_fail(msg: str) -> int:
    if REQUIRE:
        print(f"FAIL: SELAHCUE_SWEEP_REQUIRE=1 but {msg}")
        return 3
    print("=" * 68)
    print(f"!! RESPONSIVE SWEEP SKIPPED -- {msg}")
    print("!! (set SELAHCUE_SWEEP_REQUIRE=1 to make this a failure)")
    print("=" * 68)
    return 0


def install_stubs(context) -> None:
    """No network: abort fonts, answer the account API deterministically."""

    def graphql(route):
        req = route.request
        if req.method == "GET":  # /graphql/csrf bootstrap
            return route.fulfill(status=204, headers={"Set-Cookie": "csrftoken=sweep; Path=/"})
        body = req.post_data or ""
        if "AccountViewer" in body:
            payload = {"data": {"accountViewer": {"surface": "account", "actorId": "a", "orgId": "o"}}}
        else:
            payload = {"errors": [{"message": "stub", "extensions": {"code": "VALIDATION_FAILED"}}], "data": None}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    context.route("**/graphql/**", graphql)
    context.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    context.route("**/fonts.gstatic.com/**", lambda r: r.abort())


def sheet_state(page):
    return page.evaluate(SHEET_STATE_JS)


def check_nav_sheet(context, base: str, width: int, fail, count) -> None:
    """Drive the mobile nav sheet. Only meaningful below 768px."""
    tag = f"nav-sheet {width}px"
    page = context.new_page()
    page.goto(f"{base}/", wait_until="load")
    page.wait_for_selector(".mobile-toggle")
    page.wait_for_timeout(150)

    def expect(cond: bool, what: str) -> None:
        count()
        if not cond:
            fail(f"{tag}: {what}")

    def unlocked() -> bool:
        st = sheet_state(page)
        return st["htmlOverflow"] == "" and st["bodyOverflow"] == ""

    def open_sheet() -> dict:
        page.click(".mobile-toggle")
        page.wait_for_selector("#mobile-nav-sheet")
        page.wait_for_timeout(350)  # let the slide-in transition finish before measuring
        return sheet_state(page)

    # closed baseline
    st = sheet_state(page)
    expect(not st["open"], "sheet is rendered before it was opened")
    expect(st["expanded"] == "false" and st["toggleLabel"] == "Open menu", f"closed toggle a11y wrong: {st['expanded']}/{st['toggleLabel']}")
    expect(unlocked(), "scroll lock held while the sheet is closed")

    # scroll first, so the header is in its backdrop-filter state (a fixed child of a
    # backdrop-filtered element is clipped to it -- the sheet is teleported to avoid that)
    page.evaluate("window.scrollTo(0, 400)")
    page.wait_for_timeout(250)

    st = open_sheet()
    expect(st["open"], "sheet did not open on tap")
    expect(st["expanded"] == "true", f"aria-expanded not true when open: {st['expanded']}")
    expect(st["role"] == "dialog" and st["modal"] == "true", "sheet is not role=dialog aria-modal=true")
    expect(st["activeInSheet"], f"focus did not move into the sheet (on: {st['activeLabel']!r})")
    expect(st["htmlOverflow"] == "hidden" and st["bodyOverflow"] == "hidden", "page scroll not locked while open")
    expect(st["sheetTop"] == 0 and abs(st["sheetBottom"] - st["innerHeight"]) <= 1, f"sheet does not cover the viewport height ({st['sheetTop']}..{st['sheetBottom']} of {st['innerHeight']})")
    expect(st["sheetRight"] == st["innerWidth"], "sheet is not anchored to the right edge")
    expect(all(h >= 56 for h in st["linkHeights"]) and st["linkHeights"], f"sheet rows under 56px: {st['linkHeights']}")
    expect(st["cta"] is not None and st["cta"]["bottom"] <= st["innerHeight"], "Download CTA is not inside the viewport")
    expect(st["cta"] is not None and abs(st["cta"]["width"] - st["cta"]["sheetWidth"]) <= 2, "CTA is not full-width")
    expect(page.evaluate("window.scrollY") > 0, "scroll position was reset when the sheet opened")

    # Tab trap: tabbing more times than there are controls never leaves the sheet
    leaked = False
    for _ in range(14):
        page.keyboard.press("Tab")
        if not sheet_state(page)["activeInSheet"]:
            leaked = True
    expect(not leaked, "Tab escaped the sheet")
    page.keyboard.press("Shift+Tab")
    expect(sheet_state(page)["activeInSheet"], "Shift+Tab escaped the sheet")

    # Escape closes, restores focus to the toggle, releases the lock
    page.keyboard.press("Escape")
    page.wait_for_timeout(350)
    st = sheet_state(page)
    expect(not st["open"], "Escape did not close the sheet")
    expect(st["activeIsToggle"], f"focus not restored to the toggle after Escape (on: {st['activeLabel']!r})")
    expect(st["expanded"] == "false", "aria-expanded not false after Escape")
    expect(unlocked(), "scroll lock still held after Escape")

    # close button
    open_sheet()
    page.click(".sheet-close")
    page.wait_for_timeout(350)
    expect(not sheet_state(page)["open"] and unlocked(), "close button left the sheet open or the page locked")

    # scrim tap (left of the sheet)
    open_sheet()
    page.mouse.click(4, page.evaluate("window.innerHeight") / 2)
    page.wait_for_timeout(350)
    expect(not sheet_state(page)["open"] and unlocked(), "scrim tap left the sheet open or the page locked")

    # link tap navigates AND closes AND unlocks
    open_sheet()
    page.click("#mobile-nav-sheet >> text=Pricing")
    page.wait_for_url("**/pricing")
    page.wait_for_timeout(350)
    expect(not sheet_state(page)["open"] and unlocked(), "link tap left the sheet open or the page locked")

    # route change that did NOT come from the sheet (history back) while open
    open_sheet()
    page.go_back()
    page.wait_for_timeout(500)
    expect(not sheet_state(page)["open"] and unlocked(), "history navigation left the sheet open or the page locked")

    # viewport grows past the breakpoint while open: hidden by CSS, lock must be released
    open_sheet()
    page.set_viewport_size({"width": 1024, "height": HEIGHT})
    page.wait_for_timeout(350)
    expect(not sheet_state(page)["open"] and unlocked(), "growing past 768px left the page locked")
    page.set_viewport_size({"width": width, "height": HEIGHT})

    # reopening after all of that still works (no stuck state)
    st = open_sheet()
    expect(st["open"] and st["htmlOverflow"] == "hidden", "sheet cannot be reopened after the close paths")
    page.keyboard.press("Escape")
    page.wait_for_timeout(350)
    expect(unlocked(), "final close left the page locked")
    page.close()


def check_footer(context, base: str, width: int, fail, count) -> None:
    tag = f"footer {width}px"
    page = context.new_page()
    page.goto(f"{base}/privacy", wait_until="load")
    page.wait_for_selector(".footer")

    def expect(cond: bool, what: str) -> None:
        count()
        if not cond:
            fail(f"{tag}: {what}")

    st = page.evaluate(FOOTER_STATE_JS)
    if page.evaluate(IS_MOBILE_JS):
        expect(len(st["toggles"]) == 4, f"expected 4 collapsible headings, got {len(st['toggles'])}")
        expect(all(t["expanded"] == "false" and not t["controlsVisible"] for t in st["toggles"]), "sections are not collapsed by default on mobile")
        expect(all(t["height"] >= 44 for t in st["toggles"]), f"footer headings under 44px: {[t['height'] for t in st['toggles']]}")
        expect(len(st["lefts"]) == 1, f"mobile columns do not stack (distinct left edges: {st['lefts']})")
        page.locator(".footer .column-toggle").first.click()
        st = page.evaluate(FOOTER_STATE_JS)
        expect(st["toggles"][0]["expanded"] == "true" and st["toggles"][0]["controlsVisible"], "tapping a heading did not expand its section")
        expect(not st["toggles"][1]["controlsVisible"], "tapping one heading expanded another")
        page.locator(".footer .column-toggle").first.click()
        st = page.evaluate(FOOTER_STATE_JS)
        expect(st["toggles"][0]["expanded"] == "false" and not st["toggles"][0]["controlsVisible"], "second tap did not collapse the section")
        # expand everything so the touch-target audit sees every footer link
        for i in range(4):
            page.locator(".footer .column-toggle").nth(i).click()
        st = page.evaluate(FOOTER_STATE_JS)
        expect(st["linksVisible"] == st["linksTotal"], "expanding all sections did not show every link")
        bad = page.evaluate(TOUCH_JS, [".footer a", ".footer button"])
        expect(not bad, f"footer touch targets < 44px when expanded: {'; '.join(bad)}")
    else:
        expect(not st["toggles"], "desktop/tablet footer renders collapse controls")
        expect(st["linksVisible"] == st["linksTotal"], "desktop/tablet footer hides links")
        want = 4 if width >= 1200 else 2
        expect(len(st["lefts"]) == want, f"expected {want} column left edges at {width}px, got {st['lefts']}")
    page.close()


def check_signed_in_nav(context, base: str, width: int, fail, count) -> None:
    """The densest navbar state is signed-in at tablet width; it must stay on one row."""
    tag = f"signed-in nav {width}px"
    page = context.new_page()
    page.goto(f"{base}/pricing", wait_until="load")
    page.wait_for_selector(".navbar-header")
    page.wait_for_timeout(200)
    info = page.evaluate(NAV_ROW_JS)
    count()
    if not page.evaluate(IS_MOBILE_JS):
        if not info["signedIn"]:
            fail(f"{tag}: sweep could not establish the signed-in hint")
        elif info["spread"] > 6 or info["lastRight"] > info["vw"] - 8 or info["barHeight"] != 68:
            fail(f"{tag}: navbar wrapped or overflowed {info}")
    page.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["chromium", "webkit"], default="chromium")
    ap.add_argument("--shots", help="directory to write page screenshots into (tiled, 1400px per image)")
    ap.add_argument("--routes", help="comma-separated subset of paths (exact, or a whole-segment prefix)")
    ap.add_argument("--widths", help="comma-separated subset of widths")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return skip_or_fail("Playwright not installed (pip install playwright && playwright install chromium webkit)")

    if not (DIST / "index.html").exists():
        print(f"FAIL: {DIST}/index.html missing -- run `npm run build` first (infra)")
        return 2

    routes = ROUTES
    if args.routes:
        wanted = args.routes.split(",")
        # exact path, or a whole-segment prefix ("/admin" matches /admin/users, not /administer)
        routes = [
            r for r in ROUTES
            if any(r[0].split("?")[0] == w or (w != "/" and r[0].startswith(w.rstrip("/") + "/")) for w in wanted)
        ]
    widths = [int(w) for w in args.widths.split(",")] if args.widths else WIDTHS
    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), SpaHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    failures: list[str] = []
    checks = 0

    def bump() -> None:
        nonlocal checks
        checks += 1

    try:
        with sync_playwright() as pw:
            try:
                browser = getattr(pw, args.engine).launch()
            except Exception as exc:  # noqa: BLE001 -- any launch failure is "engine unavailable"
                return skip_or_fail(f"{args.engine} could not launch ({str(exc).splitlines()[0]})")

            for width in widths:
                context = browser.new_context(
                    viewport={"width": width, "height": HEIGHT},
                    has_touch=width < 768,
                    is_mobile=False,
                )
                install_stubs(context)
                for path, bare in routes:
                    page = context.new_page()
                    errors: list[str] = []
                    page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                    try:
                        page.goto(f"http://127.0.0.1:{port}{path}", wait_until="load", timeout=20000)
                        page.wait_for_selector("main *", timeout=10000)
                        page.wait_for_timeout(250)  # let the route's lazy chunk + first paint settle
                    except Exception as exc:  # noqa: BLE001
                        print(f"INFRA {args.engine} {width}px {path}: {str(exc).splitlines()[0]}")
                        return 2

                    info = page.evaluate(PAGE_JS)
                    tag = f"{args.engine} {width:>4}px {path}"

                    checks += 1
                    if info["scrollWidth"] > info["vw"]:
                        failures.append(
                            f"{tag}: horizontal scroll, scrollWidth {info['scrollWidth']} > {info['vw']}; "
                            f"offenders: {'; '.join(info['offenders']) or '(none found outside scroll containers)'}"
                        )

                    checks += 1
                    if info["clipped"]:
                        failures.append(f"{tag}: content past the viewport edge but clipped/hidden: {'; '.join(info['clipped'])}")

                    checks += 1
                    if info["mainTextLength"] < 20:
                        failures.append(f"{tag}: rendered (almost) nothing, main text length {info['mainTextLength']}")

                    checks += 1
                    if errors:
                        failures.append(f"{tag}: uncaught page error: {errors[0][:160]}")

                    is_mobile = page.evaluate(IS_MOBILE_JS)
                    if not bare:
                        nav = page.evaluate(NAV_STATE_JS)
                        checks += 1
                        if not nav["hasHeader"]:
                            failures.append(f"{tag}: no navbar rendered on a non-bare route")
                        else:
                            if nav["toggleVisible"] != is_mobile or nav["desktopNavVisible"] == is_mobile:
                                failures.append(
                                    f"{tag}: nav mode wrong (toggle={nav['toggleVisible']}, "
                                    f"desktopNav={nav['desktopNavVisible']}, expected mobile={is_mobile})"
                                )

                    if is_mobile:
                        checks += 1
                        bad = page.evaluate(TOUCH_JS, TOUCH_SCOPES)
                        if bad:
                            failures.append(f"{tag}: touch targets < 44px: {'; '.join(bad)}")

                    if shots:
                        safe = path.strip("/").replace("/", "_").split("?")[0] or "home"
                        # Tall pages are cut into viewport-friendly tiles: a 12,000px strip
                        # scaled to fit a screen is unreadable, which defeats looking at it.
                        total_h = page.evaluate("document.documentElement.scrollHeight")
                        tile = 1400
                        for i, top in enumerate(range(0, total_h, tile)):
                            page.screenshot(
                                path=str(shots / f"{safe}-{width}-{i:02d}.png"),
                                full_page=True,
                                clip={"x": 0, "y": top, "width": width, "height": min(tile, total_h - top)},
                            )
                    page.close()
                context.close()

                # ---- behaviours CSS cannot prove ------------------------------------
                base = f"http://127.0.0.1:{port}"
                if width < 768 and not args.routes:
                    ctx = browser.new_context(viewport={"width": width, "height": HEIGHT}, has_touch=True)
                    install_stubs(ctx)
                    check_nav_sheet(ctx, base, width, lambda m: failures.append("FAIL " + m), bump)
                    ctx.close()
                if not args.routes:
                    ctx = browser.new_context(viewport={"width": width, "height": HEIGHT}, has_touch=width < 768)
                    install_stubs(ctx)
                    check_footer(ctx, base, width, lambda m: failures.append("FAIL " + m), bump)
                    ctx.close()
                    ctx = browser.new_context(viewport={"width": width, "height": HEIGHT})
                    install_stubs(ctx)
                    ctx.add_init_script(SESSION_HINT_INIT)
                    check_signed_in_nav(ctx, base, width, lambda m: failures.append("FAIL " + m), bump)
                    ctx.close()
            browser.close()
    finally:
        server.shutdown()

    for line in failures:
        print(line if line.startswith("FAIL") else "FAIL " + line)
    print(f"{args.engine}: {checks} checks over {len(routes)} routes x {len(widths)} widths, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
