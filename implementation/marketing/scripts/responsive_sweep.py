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
    scrim, link tap, history navigation, and the viewport growing past 768px; and the sheet's
    document-level keydown handler is gone afterwards: a cancelable Escape dispatched on
    <body> must come back not-defaultPrevented);
  * the footer (collapsed sections on mobile with working `aria-expanded` toggles, 2x2 on
    tablet, 4 across on desktop, and following a LIVE resize across 768 in both directions);
  * the confirm dialog and toast on a phone (both `position: fixed`, so the scrollWidth
    check cannot see them overflow);
  * both sides of every breakpoint (767/768, 1199/1200): the layout that renders must be the
    one the media query selects (nav, footer, home feature grid, pricing grid);
  * the signed-in navbar (Account / Sign out) still fits one row at tablet widths;
  * `prefers-reduced-motion: reduce` actually removes the sheet's animation (with a
    positive control proving the probe can see it under normal motion).

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
    # Every link in main. Inline links inside running prose are exempted in TOUCH_JS (WCAG
    # 2.5.8's inline exception), so this holds standalone links -- the auth cards'
    # "Create an account" / "Back to sign in", card actions, "View all" -- to 44px.
    "main a",
]

# Which layout the browser ACTUALLY chose, straight from the same media query the CSS uses.
# Comparing against `width < 768` instead would be wrong in exactly one case: WebKit counts
# a classic scrollbar (main.css restyles `::-webkit-scrollbar`, which forces one on macOS)
# inside the viewport the media query sees, so a 768px window is, correctly, a mobile
# layout there. The breakpoint is the contract; the window size is only how we get to it.
IS_MOBILE_JS = "matchMedia('(max-width: 767.98px)').matches"

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
  out.edge = [];
  for (const el of document.querySelectorAll('body *')) {
    if (out.clipped.length >= 8 || out.edge.length >= 8) break;
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
    // Text hard against the screen edge means a missing gutter: nothing overflows, so the
    // checks above pass, but it reads as broken. Backgrounds are not leaves, so full-bleed
    // bands are fine; only actual text/controls are held to a margin.
    if (hasText || el.tagName === 'BUTTON' || el.tagName === 'A') {
      if ((r.left < 8 || r.right > vw - 8) && r.width < vw - 16 && !scrollsX(el)) out.edge.push(describe(el));
    }
  }
  // ---- facts judged in Python against the breakpoint the browser actually chose ----
  const mobile = matchMedia('(max-width: 767.98px)').matches;
  const desktop = matchMedia('(min-width: 1200px)').matches;
  out.mode = mobile ? 'mobile' : desktop ? 'desktop' : 'tablet';
  out.gutterToken = getComputedStyle(document.documentElement).getPropertyValue('--page-gutter').trim();

  const mainEl = document.querySelector('main');
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  // GUTTER, measured on the page rather than read from source: any box in <main> that spans
  // the viewport edge to edge and carries horizontal padding IS a page container, whatever
  // it is called. Its padding must be the design's gutter for this breakpoint. (A regex for
  // `.container` missed a view that hard-coded 24px on a differently-named root.)
  out.fullBleed = [];
  // INPUT TEXT: below 768px a text field under 16px makes iOS Safari zoom the page on focus.
  out.smallInputs = [];
  // SCROLL REGIONS: anything that scrolls sideways must be reachable by keyboard.
  out.unfocusableScrollers = [];
  if (mainEl) {
    for (const e of mainEl.querySelectorAll('*')) {
      const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      if (e.closest('[aria-hidden=true]')) continue;
      const r = e.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const scroller = cs.overflowX === 'auto' || cs.overflowX === 'scroll';

      const pl = parseFloat(cs.paddingLeft), pr = parseFloat(cs.paddingRight);
      if (!scroller && Math.abs(r.left) < 0.5 && Math.abs(r.right - vw) < 0.5 && (pl > 0 || pr > 0)) {
        out.fullBleed.push(`${describe(e)} padding ${pl}/${pr}`);
      }

      if (mobile && /^(INPUT|SELECT|TEXTAREA)$/.test(e.tagName)) {
        const t = (e.getAttribute('type') || 'text').toLowerCase();
        if (!/^(checkbox|radio|range|submit|button|reset|file|color|hidden|image)$/.test(t) && parseFloat(cs.fontSize) < 16) {
          out.smallInputs.push(`${describe(e)} font-size ${cs.fontSize}`);
        }
      }

      // A region that scrolls sideways must be reachable by keyboard. When it wraps a TABLE the
      // wrapper itself must be the focusable thing: a link inside one cell is not what makes
      // the region scrollable by keyboard, and which cells hold links changes with the data
      // (it is how a DataTable that lost its tabindex kept passing). Judged only where it
      // actually scrolls, so a component that adds the tab stop only when it overflows (the
      // legal tables do) is as acceptable as one that always has it.
      if (scroller && e.scrollWidth > e.clientWidth + 1) {
        const tab = e.getAttribute('tabindex');
        const selfFocusable = tab !== null && parseInt(tab, 10) >= 0;
        const wrapsTable = !!e.querySelector('table');
        if (!selfFocusable && (wrapsTable || !e.querySelector(FOCUSABLE))) {
          out.unfocusableScrollers.push(describe(e) + (wrapsTable ? ' (wraps a table)' : ''));
        }
      }
    }
  }
  // PRO FIRST (design 8d): below 1200px the pricing cards are one column with the popular plan
  // leading. Compared in visual order, not DOM order.
  const cards = [...document.querySelectorAll('.pricing-card')].filter((c) => c.getBoundingClientRect().height > 0);
  out.pricingFirstIsPopular = null;
  if (cards.length) {
    const ordered = cards.slice().sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top || a.getBoundingClientRect().left - b.getBoundingClientRect().left);
    out.pricingFirstIsPopular = ordered[0].classList.contains('popular');
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
      // Visually hidden until focused (a clipped 1x1 skip link) is not a touch target.
      if (r.width <= 1 && r.height <= 1) continue;
      // Inline links inside running prose are exempt (WCAG 2.5.8 inline exception).
      if (el.tagName === 'A' && cs.display === 'inline' && el.closest('p, li, dd, blockquote, label')) continue;
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
    appInert: document.getElementById('app') ? document.getElementById('app').hasAttribute('inert') : null,
    activeIsBody: active === document.body || active === document.documentElement,
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


class Server(socketserver.ThreadingTCPServer):
    """Threaded: a browser keeps connections open and a single-threaded server can stall on one.

    A client that goes away mid-response (a page closed during the run) is routine, not an
    error worth a traceback.
    """

    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):  # noqa: D401
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


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

    # CLASSIC SCROLLBARS SKEW THE BREAKPOINT IN WEBKIT. main.css restyles `::-webkit-scrollbar`,
    # which forces a 12px classic scrollbar even on macOS, and WebKit counts it inside the
    # width media queries see. A 768px window therefore flips between tablet (page short, no
    # scrollbar) and mobile (page tall, scrollbar) depending on content height, so exactly at
    # a breakpoint the CSS and a later `matchMedia` can disagree about the same page. The real
    # targets (phones, iPads) use overlay scrollbars, so neutralise the classic one here and a
    # viewport width means the same thing in both engines. Nothing else about the page changes.
    context.add_init_script(
        """(() => {
          const add = () => {
            const s = document.createElement('style');
            s.textContent = '::-webkit-scrollbar { display: none !important; width: 0 !important; height: 0 !important; }';
            document.documentElement.appendChild(s);
          };
          if (document.documentElement) add();
          else new MutationObserver((_, o) => { if (document.documentElement) { o.disconnect(); add(); } }).observe(document, { childList: true });
        })();"""
    )
    context.route("**/graphql/**", graphql)
    context.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    context.route("**/fonts.gstatic.com/**", lambda r: r.abort())


def sheet_state(page):
    return page.evaluate(SHEET_STATE_JS)


# Every finite animation/transition has finished (infinite ones, like the LIVE badge pulse,
# are decoration and never settle). Waiting on THIS, not on a sleep, is what makes a
# measurement taken straight after a load/open/close independent of machine load: a card
# measured mid `slideUp` is 0.97-scaled, so a 44px control reads 43px and fails for no reason.
SETTLE_JS = """() => document.getAnimations({ subtree: true }).every(
  (a) => a.playState !== 'running' || (a.effect && a.effect.getComputedTiming().iterations === Infinity)
)"""

# A cancelable Escape keydown dispatched on <body> AFTER the sheet is gone. The sheet's
# document-level handler calls preventDefault() on Escape, so if it is still attached the
# event comes back defaultPrevented -- a leaked listener swallowing Escape for the whole page.
ESCAPE_LEAK_JS = """() => {
  const e = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
  document.body.dispatchEvent(e);
  return e.defaultPrevented;
}"""

SETTLED_JS = """() => {
  const s = document.querySelector('#mobile-nav-sheet');
  if (!s) return false;
  const r = s.getBoundingClientRect();
  const running = document.getAnimations({ subtree: true }).some(
    (a) => a.playState === 'running' && a.effect && a.effect.getComputedTiming().duration > 1
  );
  return Math.abs(r.right - innerWidth) <= 0.5 && !running;
}"""


def check_nav_sheet(context, base: str, width: int, fail, count) -> None:
    """Drive the mobile nav sheet. Only meaningful below 768px.

    No fixed sleeps: every transition is waited for BY STATE (the sheet element attached and
    settled, or detached), because under load the leave transition took up to ~470ms and a
    350ms sleep made different checks fail on different runs. A step that throws is reported
    as a failure and the page is reset, so one broken step cannot cascade into a hang.
    """
    tag = f"nav-sheet {width}px"
    page = context.new_page()
    page.set_default_timeout(8000)
    page.goto(f"{base}/", wait_until="load")
    page.wait_for_selector(".mobile-toggle")

    def expect(cond: bool, what: str) -> None:
        count()
        if not cond:
            fail(f"{tag}: {what}")

    def released() -> bool:
        """Scroll lock AND inert back to rest, AND the sheet's document keydown listener gone."""
        st = sheet_state(page)
        if page.evaluate(ESCAPE_LEAK_JS):
            count()
            fail(f"{tag}: the sheet's document keydown handler is still attached after close (it swallowed a cancelable Escape)")
            return False
        return st["htmlOverflow"] == "" and st["bodyOverflow"] == "" and st["appInert"] is False

    def wait_closed() -> None:
        page.wait_for_selector("#mobile-nav-sheet", state="detached")

    def settle_open() -> dict:
        page.wait_for_selector("#mobile-nav-sheet", state="attached")
        page.wait_for_function(SETTLED_JS)
        return sheet_state(page)

    def open_sheet() -> dict:
        # If an earlier (already-reported) failure left the sheet open, the toggle is behind
        # the scrim and clicking it would hang; carry on from the open state instead.
        if not sheet_state(page)["open"]:
            page.click(".mobile-toggle")
        return settle_open()

    def reset() -> None:
        page.goto(f"{base}/", wait_until="load")
        page.wait_for_selector(".mobile-toggle")

    def step(name: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 -- a timeout here is a finding, not a crash
            count()
            fail(f"{tag}: step '{name}' aborted: {str(exc).splitlines()[0][:160]}")
            try:
                reset()
            except Exception:  # noqa: BLE001
                pass

    def closed_baseline() -> None:
        st = sheet_state(page)
        expect(not st["open"], "sheet is rendered before it was opened")
        expect(st["expanded"] == "false", f"closed toggle aria-expanded wrong: {st['expanded']}")
        expect(st["toggleLabel"] == "Menu", f"toggle needs ONE static name, got {st['toggleLabel']!r}")
        expect(released(), "scroll lock or inert held while the sheet is closed")

    def opened_state() -> None:
        # scroll first, so the header is in its backdrop-filter state (a fixed child of a
        # backdrop-filtered element is clipped to it -- the sheet is teleported to avoid that)
        page.evaluate("window.scrollTo(0, 400)")
        page.wait_for_function("window.scrollY > 10")
        st = open_sheet()
        expect(st["open"], "sheet did not open on tap")
        expect(st["expanded"] == "true", f"aria-expanded not true when open: {st['expanded']}")
        expect(st["toggleLabel"] == "Menu", f"toggle name changed while open: {st['toggleLabel']!r}")
        expect(st["role"] == "dialog" and st["modal"] == "true", "sheet is not role=dialog aria-modal=true")
        expect(st["activeInSheet"], f"focus did not move into the sheet (on: {st['activeLabel']!r})")
        expect(st["htmlOverflow"] == "hidden" and st["bodyOverflow"] == "hidden", "page scroll not locked while open")
        expect(st["appInert"] is True, "the page behind the sheet is not inert while it is open")
        expect(st["sheetTop"] == 0 and abs(st["sheetBottom"] - st["innerHeight"]) <= 1, f"sheet does not cover the viewport height ({st['sheetTop']}..{st['sheetBottom']} of {st['innerHeight']})")
        expect(st["sheetRight"] == st["innerWidth"], "sheet is not anchored to the right edge")
        expect(all(h >= 56 for h in st["linkHeights"]) and st["linkHeights"], f"sheet rows under 56px: {st['linkHeights']}")
        expect(st["cta"] is not None and st["cta"]["bottom"] <= st["innerHeight"], "Download CTA is not inside the viewport")
        expect(st["cta"] is not None and abs(st["cta"]["width"] - st["cta"]["sheetWidth"]) <= 2, "CTA is not full-width")
        expect(page.evaluate("window.scrollY") > 0, "scroll position was reset when the sheet opened")

    def tab_trap() -> None:
        leaked = False
        for _ in range(14):
            page.keyboard.press("Tab")
            if not sheet_state(page)["activeInSheet"]:
                leaked = True
        expect(not leaked, "Tab escaped the sheet")
        page.keyboard.press("Shift+Tab")
        expect(sheet_state(page)["activeInSheet"], "Shift+Tab escaped the sheet")

    def escape_closes() -> None:
        page.keyboard.press("Escape")
        wait_closed()
        st = sheet_state(page)
        expect(st["activeIsToggle"], f"focus not restored to the toggle after Escape (on: {st['activeLabel']!r})")
        expect(st["expanded"] == "false", "aria-expanded not false after Escape")
        expect(released(), "scroll lock or inert still held after Escape")

    def blank_click_then_keys() -> None:
        """REVIEW ITEM 1: a click on empty sheet space sends focus to <body>; Escape and the
        Tab trap must still work (a keydown handler on the sheet element goes deaf)."""
        open_sheet()
        page.click(".sheet-title")  # non-interactive strip inside the sheet
        st = sheet_state(page)
        expect(not st["activeInSheet"], "precondition: a blank click should have moved focus out of the sheet's controls")
        # Tab must pull focus back INTO the sheet (and keep it there), never out to the page/browser
        leaked = False
        for _ in range(8):
            page.keyboard.press("Tab")
            if not sheet_state(page)["activeInSheet"]:
                leaked = True
        expect(not leaked, "after a blank-area click, Tab left the sheet")
        page.click(".sheet-title")
        page.keyboard.press("Shift+Tab")
        expect(sheet_state(page)["activeInSheet"], "after a blank-area click, Shift+Tab did not return into the sheet")
        # and Escape still closes, restores focus to the hamburger, releases lock + inert
        page.click(".sheet-title")
        page.keyboard.press("Escape")
        wait_closed()
        st = sheet_state(page)
        expect(st["activeIsToggle"], f"after a blank-area click, Escape closed the sheet but focus is on {st['activeLabel']!r}")
        expect(released(), "after a blank-area click, Escape left the page locked or inert")

    def close_button() -> None:
        open_sheet()
        page.click(".sheet-close")
        wait_closed()
        expect(released(), "close button left the page locked or inert")

    def scrim_tap() -> None:
        open_sheet()
        page.mouse.click(4, page.evaluate("window.innerHeight") / 2)
        wait_closed()
        expect(released(), "scrim tap left the page locked or inert")

    def link_tap() -> None:
        open_sheet()
        page.click("#mobile-nav-sheet >> text=Pricing")
        page.wait_for_url("**/pricing")
        wait_closed()
        expect(released(), "link tap left the page locked or inert")

    def history_back() -> None:
        # a route change that did NOT come from the sheet, while it is open
        open_sheet()
        page.go_back()
        wait_closed()
        expect(released(), "history navigation left the page locked or inert")

    def resize_past_breakpoint() -> None:
        open_sheet()
        page.set_viewport_size({"width": 1024, "height": HEIGHT})
        try:
            wait_closed()
            expect(released(), "growing past 768px left the page locked or inert")
        finally:
            page.set_viewport_size({"width": width, "height": HEIGHT})

    def pagehide_releases() -> None:
        # bfcache / tab discard: the page can be frozen with the sheet open
        open_sheet()
        page.evaluate("window.dispatchEvent(new Event('pagehide'))")
        wait_closed()
        expect(released(), "pagehide left the page locked or inert")

    def reopen() -> None:
        st = open_sheet()
        expect(st["open"] and st["htmlOverflow"] == "hidden" and st["appInert"] is True, "sheet cannot be reopened after the close paths")
        page.keyboard.press("Escape")
        wait_closed()
        expect(released(), "final close left the page locked or inert")

    def unmount_releases() -> None:
        # Unmount WITHOUT a route change (the route watcher would close it first): tear the
        # whole Vue app down while the sheet is open and check nothing is left held.
        reset()
        open_sheet()
        page.evaluate("document.querySelector('#app').__vue_app__.unmount()")
        page.wait_for_function("document.documentElement.style.overflow === ''")
        st = sheet_state(page)
        expect(st["htmlOverflow"] == "" and st["bodyOverflow"] == "", "unmounting with the sheet open left the page scroll-locked")
        expect(st["appInert"] is False, "unmounting with the sheet open left #app inert")
        expect(not page.evaluate(ESCAPE_LEAK_JS), "unmounting with the sheet open left its document keydown handler attached")

    step("closed baseline", closed_baseline)
    step("open state", opened_state)
    step("tab trap", tab_trap)
    step("escape", escape_closes)
    step("blank-area click then Tab/Escape", blank_click_then_keys)
    step("close button", close_button)
    step("scrim tap", scrim_tap)
    step("link tap", link_tap)
    step("history back", history_back)
    step("resize past 768", resize_past_breakpoint)
    step("pagehide", pagehide_releases)
    step("reopen", reopen)
    step("unmount", unmount_releases)
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

    # LIVE RESIZE: the footer reads its mode from a media-query listener. Load at one side of
    # 768, cross to the other and back; after EACH resize the footer must be in the mode the
    # media query now says (a footer that never re-reads it stays collapsible on a desktop
    # window, or expanded on a phone). Waited for by state, not by a sleep.
    def footer_follows_media_query() -> str | None:
        probe = """() => {
          const mobile = matchMedia('(max-width: 767.98px)').matches;
          const f = document.querySelector('.footer');
          const toggles = document.querySelectorAll('.footer .column-toggle').length;
          const lefts = new Set([...document.querySelectorAll('.footer .link-column')].map((c) => Math.round(c.getBoundingClientRect().left))).size;
          const hidden = [...document.querySelectorAll('.footer .footer-link')].filter((a) => a.getBoundingClientRect().height === 0).length;
          const ok = mobile
            ? f.classList.contains('is-mobile') && toggles === 4 && lefts === 1
            : !f.classList.contains('is-mobile') && toggles === 0 && lefts >= 2 && hidden === 0;
          return ok;
        }"""
        try:
            page.wait_for_function(probe, timeout=3000)
            return None
        except Exception:  # noqa: BLE001
            return "stayed in the wrong mode"

    other = 1024 if page.evaluate(IS_MOBILE_JS) else 375
    count()
    if footer_follows_media_query():
        fail(f"{tag}: footer is not in the mode its media query selects on load")
    for step_width in (other, width):
        page.set_viewport_size({"width": step_width, "height": HEIGHT})
        count()
        wrong = footer_follows_media_query()
        if wrong:
            fail(f"{tag}: after a live resize to {step_width}px the footer {wrong} (media query listener not re-read)")
    # restore the starting state for the assertions below
    page.wait_for_function("document.querySelectorAll('.footer .link-column').length === 4")

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
    page.wait_for_function(SETTLE_JS)
    info = page.evaluate(NAV_ROW_JS)
    count()
    if not page.evaluate(IS_MOBILE_JS):
        if not info["signedIn"]:
            fail(f"{tag}: sweep could not establish the signed-in hint")
        elif info["spread"] > 6 or info["lastRight"] > info["vw"] - 8 or info["barHeight"] != 68:
            fail(f"{tag}: navbar wrapped or overflowed {info}")
    page.close()


def check_reduced_motion(browser, base: str, width: int, fail, count) -> None:
    """`prefers-reduced-motion: reduce` must remove the sheet's slide/fade and button transitions.

    A positive control runs first with normal motion: the probe (`document.getAnimations()`
    right after the tap) must SEE the slide-in there, otherwise "no animations under
    reduced motion" would be vacuously true.
    """
    tag = f"reduced-motion {width}px"

    def animations_after_open(reduced: bool) -> tuple[int, str]:
        ctx = browser.new_context(
            viewport={"width": width, "height": HEIGHT},
            has_touch=True,
            reduced_motion="reduce" if reduced else "no-preference",
        )
        install_stubs(ctx)
        page = ctx.new_page()
        page.goto(f"{base}/", wait_until="load")
        page.wait_for_selector(".mobile-toggle")
        page.wait_for_function(SETTLE_JS)
        # Tap, then sample over ~10 frames and keep the PEAK: WebKit starts Vue's enter
        # transition two frames after the click, so one immediate read would see nothing there
        # even under normal motion.
        n = page.evaluate(
            """async () => {
              document.querySelector('.mobile-toggle').click();
              let peak = 0;
              for (let i = 0; i < 10; i++) {
                await new Promise((r) => requestAnimationFrame(r));
                const running = document.getAnimations({ subtree: true }).filter(
                  (a) => a.playState === 'running' && a.effect && a.effect.getComputedTiming().duration > 1
                ).length;
                peak = Math.max(peak, running);
              }
              return peak;
            }"""
        )
        page.wait_for_selector("#mobile-nav-sheet")
        durations = page.evaluate(
            "[...document.querySelectorAll('.download-cta, .sheet-cta, .mobile-link')].map((e) => getComputedStyle(e).transitionDuration).join(',')"
        )
        ctx.close()
        return n, durations

    count()
    normal, _ = animations_after_open(False)
    if normal < 1:
        fail(f"{tag}: probe is blind -- normal motion showed no running animation after opening the sheet")
        return
    count()
    reduced, durations = animations_after_open(True)
    if reduced != 0:
        fail(f"{tag}: {reduced} animation(s) still running with prefers-reduced-motion: reduce")
    count()
    # Serialised differently per engine ("1e-05s" in Blink, "0.00001s" in WebKit): compare numerically.
    bad = [d for d in durations.split(",") if d and float(d.removesuffix("s")) > 0.0001]
    if bad:
        fail(f"{tag}: transition durations not neutralised under reduced motion: {bad[:4]}")


def check_overlays(context, base: str, width: int, fail, count) -> None:
    """Dialog and toast (both `position: fixed`, so neither can fail the scrollWidth check)."""
    tag = f"overlays {width}px"
    page = context.new_page()
    page.goto(f"{base}/account", wait_until="load")
    page.wait_for_selector(".portal-content", timeout=10000)

    def inside(sel: str) -> tuple[bool, str]:
        r = page.evaluate(
            """(sel) => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect();
              return {l: Math.round(b.left), r: Math.round(b.right), t: Math.round(b.top), b: Math.round(b.bottom), vw: innerWidth, vh: innerHeight}; }""",
            sel,
        )
        if r is None:
            return False, "not rendered"
        ok = r["l"] >= 0 and r["r"] <= r["vw"] and r["t"] >= 0 and r["b"] <= r["vh"]
        return ok, f"{r['l']}..{r['r']} x {r['t']}..{r['b']} in {r['vw']}x{r['vh']}"

    # confirm dialog
    page.get_by_role("button", name="Cancel Subscription").click()
    page.wait_for_selector(".dialog-card")
    # the card slides/scales in (`slideUp`); measure only once it has stopped
    page.wait_for_function("document.querySelector('.dialog-card').getAnimations().length === 0")
    count()
    ok, where = inside(".dialog-card")
    if not ok:
        fail(f"{tag}: confirm dialog is not fully on screen ({where})")
    count()
    bad = page.evaluate(TOUCH_JS, [".dialog-card button", ".dialog-card input"])
    if bad:
        fail(f"{tag}: dialog controls under 44px: {'; '.join(bad)}")
    page.keyboard.press("Escape")
    count()
    try:
        page.wait_for_selector(".dialog-card", state="detached")
    except Exception:  # noqa: BLE001
        fail(f"{tag}: Escape did not close the dialog")

    # toast
    page.locator(".btn-link").first.click()
    page.wait_for_selector(".toast-notification")
    # Vue starts the enter transition a frame AFTER the element exists, so "no animations" is
    # briefly true while the toast is still fully transparent and 20px low. Wait for it to be
    # fully opaque AND idle.
    page.wait_for_function(
        "(() => { const t = document.querySelector('.toast-notification'); "
        "return !!t && getComputedStyle(t).opacity === '1' && t.getAnimations().length === 0; })()"
    )
    count()
    ok, where = inside(".toast-notification")
    if not ok:
        fail(f"{tag}: toast is not fully on screen ({where})")
    page.close()


BOUNDARY_ROUTES = ["/", "/pricing", "/privacy", "/account", "/admin", "/affiliates/dashboard"]
BOUNDARY_WIDTHS = [767, 768, 1199, 1200]

BOUNDARY_JS = r"""
() => {
  const mobile = matchMedia('(max-width: 767.98px)').matches;
  const desktop = matchMedia('(min-width: 1200px)').matches;
  const cols = (sel) => { const els = [...document.querySelectorAll(sel)].filter((e) => e.getBoundingClientRect().height > 0);
    return els.length ? new Set(els.map((e) => Math.round(e.getBoundingClientRect().left))).size : null; };
  const vis = (el) => !!el && getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().width > 0;
  return {
    mode: mobile ? 'mobile' : desktop ? 'desktop' : 'tablet',
    iw: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    toggle: vis(document.querySelector('.mobile-toggle')),
    desktopNav: vis(document.querySelector('.desktop-nav')),
    footerToggles: document.querySelectorAll('.footer .column-toggle').length,
    footerCols: cols('.footer .link-column'),
    featureCols: cols('.features-grid > *'),
    pricingCols: cols('.pricing-grid > *'),
  };
}
"""


def check_boundaries(browser, base: str, engine: str, fail, count) -> None:
    """Render either side of every breakpoint (767/768, 1199/1200) and compare the layout
    that appears with the layout the MEDIA QUERY says should appear.

    This is the check that catches a breakpoint typed differently in two places: a CSS rule
    at 700 instead of 767.98 renders a desktop-ish layout at 767 while the JS (and this
    probe, which asks the browser the same question the CSS asks) says mobile.
    """
    for width in BOUNDARY_WIDTHS:
        ctx = browser.new_context(viewport={"width": width, "height": HEIGHT})
        install_stubs(ctx)
        for path in BOUNDARY_ROUTES:
            tag = f"boundary {engine} {width}px {path}"
            page = ctx.new_page()
            try:
                page.goto(f"{base}{path}", wait_until="load")
                page.wait_for_selector("main *")
                page.wait_for_function(SETTLE_JS)
                st = page.evaluate(BOUNDARY_JS)
            except Exception as exc:  # noqa: BLE001
                count()
                fail(f"{tag}: aborted: {str(exc).splitlines()[0][:160]}")
                page.close()
                continue
            mode = st["mode"]
            want_cols = {"mobile": 1, "tablet": 2, "desktop": 3}[mode]
            count()
            if st["scrollWidth"] > st["iw"]:
                fail(f"{tag}: horizontal scroll ({st['scrollWidth']} > {st['iw']})")
            count()
            if st["toggle"] != (mode == "mobile") or st["desktopNav"] == (mode == "mobile"):
                fail(f"{tag}: nav shows the wrong mode for {mode} (toggle={st['toggle']}, desktopNav={st['desktopNav']})")
            if st["footerCols"] is not None:
                count()
                want_footer = {"mobile": 1, "tablet": 2, "desktop": 4}[mode]
                if st["footerCols"] != want_footer or (st["footerToggles"] > 0) != (mode == "mobile"):
                    fail(f"{tag}: footer layout is not the {mode} one (columns={st['footerCols']}, want {want_footer}; collapse controls={st['footerToggles']})")
            if st["featureCols"] is not None:
                count()
                if st["featureCols"] != want_cols:
                    fail(f"{tag}: home feature grid has {st['featureCols']} columns, {mode} wants {want_cols}")
            if st["pricingCols"] is not None:
                count()
                want_pricing = 3 if mode == "desktop" else 1
                if st["pricingCols"] != want_pricing:
                    fail(f"{tag}: pricing grid has {st['pricingCols']} columns, {mode} wants {want_pricing}")
            page.close()
        ctx.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["chromium", "webkit"], default="chromium")
    ap.add_argument("--shots", help="directory to write page screenshots into (tiled, 1400px per image)")
    ap.add_argument("--routes", help="comma-separated subset of paths (exact, or a whole-segment prefix)")
    ap.add_argument("--widths", help="comma-separated subset of widths")
    ap.add_argument("--behaviours-only", action="store_true", help="skip the per-route layout sweep; run only the interaction checks")
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
    if args.behaviours_only:
        routes = []
    widths = [int(w) for w in args.widths.split(",")] if args.widths else WIDTHS
    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    server = Server(("127.0.0.1", 0), SpaHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    failures: list[str] = []
    checks = 0

    def bump() -> None:
        nonlocal checks
        checks += 1

    def guarded(fn, ctx, base, width) -> None:
        """Run a behaviour check; an exception inside it is a FAILURE, not a crash."""
        try:
            fn(ctx, base, width, lambda m: failures.append("FAIL " + m), bump)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"FAIL {fn.__name__} {width}px: check aborted: {str(exc).splitlines()[0][:200]}")

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
                        page.wait_for_function(SETTLE_JS, timeout=10000)  # lazy chunk painted, nothing mid-transition
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
                    if info["edge"]:
                        failures.append(f"{tag}: text/controls within 8px of the screen edge (missing gutter): {'; '.join(info['edge'])}")

                    expected_gutter = {"mobile": "20", "tablet": "48", "desktop": "24"}[info["mode"]]
                    checks += 1
                    if info["gutterToken"] != f"{expected_gutter}px":
                        failures.append(f"{tag}: --page-gutter is {info['gutterToken']!r}, design wants {expected_gutter}px at {info['mode']}")
                    checks += 1
                    # Bare auth/landing pages are exempt: their geometry is the auth handoff's
                    # own (a 92vw card in a 20px-padded page), not the marketing gutter.
                    wrong = [] if bare else [b for b in info["fullBleed"] if f"padding {expected_gutter}/{expected_gutter}" not in b]
                    if wrong:
                        failures.append(f"{tag}: page container padding is not the {expected_gutter}px {info['mode']} gutter: {'; '.join(wrong[:4])}")
                    checks += 1
                    if info["smallInputs"]:
                        failures.append(f"{tag}: text inputs under 16px on a phone (iOS zooms on focus): {'; '.join(info['smallInputs'][:4])}")
                    checks += 1
                    if info["unfocusableScrollers"]:
                        failures.append(f"{tag}: sideways-scrolling region not keyboard focusable: {'; '.join(info['unfocusableScrollers'][:4])}")
                    if info["pricingFirstIsPopular"] is not None and info["mode"] != "desktop":
                        checks += 1
                        if not info["pricingFirstIsPopular"]:
                            failures.append(f"{tag}: pricing cards are not Pro-first below 1200px (design 8d)")

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
                    guarded(check_nav_sheet, ctx, base, width)
                    ctx.close()
                if width == widths[-1] and not args.routes:
                    # boundary widths are their own matrix: run once per engine, after the standard widths
                    guarded(lambda c, b, w, f, n: check_boundaries(browser, b, args.engine, f, n), None, base, 0)
                if width < 768 and not args.routes:
                    ctx = browser.new_context(viewport={"width": width, "height": HEIGHT}, has_touch=True)
                    install_stubs(ctx)
                    guarded(check_overlays, ctx, base, width)
                    ctx.close()
                if width == 375 and not args.routes:
                    guarded(check_reduced_motion, browser, base, width)
                if not args.routes:
                    ctx = browser.new_context(viewport={"width": width, "height": HEIGHT}, has_touch=width < 768)
                    install_stubs(ctx)
                    guarded(check_footer, ctx, base, width)
                    ctx.close()
                    ctx = browser.new_context(viewport={"width": width, "height": HEIGHT})
                    install_stubs(ctx)
                    ctx.add_init_script(SESSION_HINT_INIT)
                    guarded(check_signed_in_nav, ctx, base, width)
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
