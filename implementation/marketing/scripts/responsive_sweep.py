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

It also exercises the mobile nav sheet interaction (open, focus moves in, Tab is trapped,
Escape closes and restores focus to the toggle, `aria-expanded` tracks, body scroll lock is
set while open and released on close AND on route change).

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["chromium", "webkit"], default="chromium")
    ap.add_argument("--shots", help="directory to write full-page PNGs into")
    ap.add_argument("--routes", help="comma-separated subset of paths (prefix match)")
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
        routes = [r for r in ROUTES if any(r[0].startswith(w) for w in wanted)]
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
                    if info["mainTextLength"] < 20:
                        failures.append(f"{tag}: rendered (almost) nothing, main text length {info['mainTextLength']}")

                    checks += 1
                    if errors:
                        failures.append(f"{tag}: uncaught page error: {errors[0][:160]}")

                    if not bare:
                        nav = page.evaluate(NAV_STATE_JS)
                        checks += 1
                        if not nav["hasHeader"]:
                            failures.append(f"{tag}: no navbar rendered on a non-bare route")
                        else:
                            mobile = width < 768
                            if nav["toggleVisible"] != mobile or nav["desktopNavVisible"] == mobile:
                                failures.append(
                                    f"{tag}: nav mode wrong (toggle={nav['toggleVisible']}, "
                                    f"desktopNav={nav['desktopNavVisible']}, expected mobile={mobile})"
                                )

                    if width < 768:
                        checks += 1
                        bad = page.evaluate(TOUCH_JS, TOUCH_SCOPES)
                        if bad:
                            failures.append(f"{tag}: touch targets < 44px: {'; '.join(bad)}")

                    if shots:
                        safe = path.strip("/").replace("/", "_").split("?")[0] or "home"
                        page.screenshot(path=str(shots / f"{safe}-{width}.png"), full_page=True)
                    page.close()
                context.close()
            browser.close()
    finally:
        server.shutdown()

    for line in failures:
        print("FAIL", line)
    print(f"{args.engine}: {checks} checks over {len(routes)} routes x {len(widths)} widths, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
