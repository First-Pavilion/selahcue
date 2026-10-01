#!/usr/bin/env python3
"""Behavioural check for the blog / docs / support detail pages (GAP-08, 17tnw2b0q9h).

`npm test` pins the content source and the router's resolution under node. This proves what
node cannot: that the REAL production bundle in `dist/`, in a real browser, does the things
those pages promise.

  - an unknown slug shows the not-found page and KEEPS the visitor's URL (never a blank page);
  - each article sets its own `document.title` and meta description, follows an
    article -> article navigation, and gives the default title back on the index;
  - exactly one <h1>; breadcrumb and sidebar mark the current page; focus lands on the <h1>
    after in-app navigation but NOT on a direct load, so the skip link stays reachable;
  - a table-of-contents click scrolls the heading BELOW the sticky navbar (vue-router ignores
    CSS scroll-margin, so this is the regression a lexical test cannot see);
  - copy-to-clipboard announces its result and copies this page's URL;
  - the docs sidebar folds behind an aria-expanded button on a phone and refolds on navigation;
  - the support search filters, and says so when nothing matches.

Serves `dist/` over local HTTP with SPA fallback (the app uses createWebHistory).

Usage:
    npm run build && python3 scripts/article_pages_headless.py

Exit codes: 0 all passed (or Playwright/Chrome absent and not required); 1 a check FAILED;
2 no `dist/`; 3 SELAHCUE_HEADLESS_REQUIRE=1 but the browser is unavailable.
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = Path(os.environ.get("SELAHCUE_MARKETING_DIST") or (HERE.parent / "dist"))
REQUIRE = os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1"
SHOTS = os.environ.get("SELAHCUE_ARTICLE_SHOTS")  # optional dir for full-page screenshots

POST = "/blog/why-offline-first-matters-for-sunday-morning"
NEXT_POST_TITLE = "What your stage team sees on the stage display"


def skip_or_fail(msg: str) -> None:
    if REQUIRE:
        print("FAIL: SELAHCUE_HEADLESS_REQUIRE=1 but " + msg)
        sys.exit(3)
    print("=" * 68)
    print("!! ARTICLE-PAGE CHECK SKIPPED: " + msg)
    print("!! (set SELAHCUE_HEADLESS_REQUIRE=1 to make this a hard failure)")
    print("=" * 68)
    sys.exit(0)


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    skip_or_fail("Playwright is not installed (pip install playwright)")

if not (DIST / "index.html").is_file():
    print(f"FAIL: no build at {DIST} - run `npm run build` first")
    sys.exit(2)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(DIST), **k)

    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0]
        if not (DIST / path.lstrip("/")).is_file():
            self.path = "/index.html"  # SPA fallback
        return super().do_GET()

    def log_message(self, *a):  # quiet
        pass


results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail and not ok else ""))


def main() -> None:
    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()

    with sync_playwright() as p:
        try:
            try:
                browser = p.chromium.launch(channel="chrome")
            except Exception:
                browser = p.chromium.launch()
        except Exception as exc:  # no browser binary at all
            skip_or_fail(f"no Chromium available ({exc})")
            return

        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        pg = ctx.new_page()
        page_errors: list[str] = []
        pg.on("pageerror", lambda e: page_errors.append(str(e)))

        # ---- unknown slugs ------------------------------------------------------------
        for path in [
            "/blog/nope",
            "/docs/getting-started/nope",
            "/docs/nope/nope",
            "/support/troubleshooting/nope",
            "/docs/getting-started",  # a category prefix has no route of its own
        ]:
            pg.goto(base + path, wait_until="networkidle")
            check(
                f"unknown {path}: not-found page, URL kept",
                pg.url == base + path and pg.inner_text("h1").startswith("We couldn't find"),
                pg.url,
            )

        # ---- title / meta / focus across navigation -----------------------------------
        pg.goto(base + "/blog", wait_until="networkidle")
        default_title = pg.title()
        pg.click("text=Read story")
        pg.wait_for_url("**" + POST)
        pg.wait_for_timeout(300)
        check("article sets its own document.title", pg.title() == "Why offline-first matters for Sunday morning — SelahCue", pg.title())
        check("article sets its meta description", "desktop" in (pg.get_attribute("meta[name=description]", "content") or ""))
        check("focus moves to the <h1> after in-app navigation", pg.evaluate("document.activeElement.tagName") == "H1")
        check("exactly one <h1> on a blog post", pg.locator("h1").count() == 1)
        pg.click("a.pn-link.is-next")
        pg.wait_for_timeout(500)
        check("article -> article navigation keeps the NEW title", pg.title().startswith(NEXT_POST_TITLE), pg.title())
        pg.goto(base + "/blog", wait_until="networkidle")
        check("index page gets the default title back", pg.title() == default_title, pg.title())

        # ---- anchors clear the sticky navbar; copy link --------------------------------
        pg.goto(base + POST, wait_until="networkidle")
        pg.click("a.bp-toc-link:has-text('The desktop is in charge')")
        pg.wait_for_timeout(900)
        top = pg.evaluate("document.getElementById('sec-the-desktop-is-in-charge').getBoundingClientRect().top")
        check("toc click puts the hash in the URL", pg.url.endswith("#sec-the-desktop-is-in-charge"), pg.url)
        check("toc target lands below the 68px sticky navbar", 68 < top < 140, str(top))
        pg.click("text=Copy link")
        pg.wait_for_timeout(200)
        check("copy link announces its result", "copied" in pg.inner_text("[role=status]").lower())
        check("copy link copies this post's URL", pg.evaluate("navigator.clipboard.readText()").endswith(POST))

        # ---- docs article: skip link, landmarks, feedback ------------------------------
        pg.goto(base + "/docs/display-outputs/ndi-output", wait_until="networkidle")
        check("direct load does NOT steal focus into the article", pg.evaluate("document.activeElement.tagName") != "H1")
        pg.keyboard.press("Tab")
        tabs = 1
        while "da-skip" not in pg.evaluate("document.activeElement.className") and tabs < 25:
            pg.keyboard.press("Tab")
            tabs += 1
        check("'Skip to article' is reachable by Tab", "da-skip" in pg.evaluate("document.activeElement.className"), f"{tabs} tabs")
        check(
            "'Skip to article' is visible while focused",
            pg.evaluate("(()=>{const r=document.activeElement.getBoundingClientRect();return r.left>=0&&r.top>=60&&r.width>0})()"),
        )
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(200)
        check("'Skip to article' moves focus to the article", pg.evaluate("document.activeElement.id") == "docs-article")
        pg.click("button.da-btn:has-text('Yes')")
        check("'Was this helpful?' acknowledges", "Glad it helped" in pg.inner_text(".da-feedback"))
        check("exactly one <h1> on a docs article", pg.locator("h1").count() == 1)
        check("sidebar marks the current page", pg.locator("a[aria-current=page]").count() >= 1)
        check("breadcrumb marks the current page", pg.locator("nav[aria-label=Breadcrumb] [aria-current=page]").count() == 1)

        # ---- phone: sidebar folds ------------------------------------------------------
        phone = browser.new_context(viewport={"width": 375, "height": 800}).new_page()
        phone.goto(base + "/docs/display-outputs/ndi-output", wait_until="networkidle")
        btn = phone.locator("button.da-menu-btn")
        check("phone: docs menu starts folded", btn.get_attribute("aria-expanded") == "false" and not phone.locator("#docs-nav").is_visible())
        btn.click()
        check("phone: docs menu opens (aria-expanded true)", btn.get_attribute("aria-expanded") == "true" and phone.locator("#docs-nav").is_visible())
        phone.locator("#docs-nav details[open] a.da-link:not([aria-current])").first.click()
        phone.wait_for_timeout(500)
        check("phone: docs menu folds after navigating", not phone.locator("#docs-nav").is_visible())
        check("phone: docs article does not scroll sideways", not phone.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))

        # ---- support index search -------------------------------------------------------
        sp = ctx.new_page()
        sp.goto(base + "/support", wait_until="networkidle")
        sp.fill("input[type=search]", "ndi")
        sp.wait_for_timeout(200)
        body = sp.inner_text("body")
        check("support search filters the articles", "NDI toggle" in body and "Knowledge Base Categories" not in body)
        sp.fill("input[type=search]", "zzzz")
        sp.wait_for_timeout(200)
        check("support search says when nothing matches", "No help articles match" in sp.inner_text("body"))

        # ---- optional screenshots ------------------------------------------------------
        if SHOTS:
            out = Path(SHOTS)
            out.mkdir(parents=True, exist_ok=True)
            for width in (375, 1440):
                shot = browser.new_context(viewport={"width": width, "height": 900}).new_page()
                for name, path in [
                    ("blog-index", "/blog"),
                    ("blog-post", POST),
                    ("docs-index", "/docs"),
                    ("docs-article", "/docs/display-outputs/ndi-output"),
                    ("support-index", "/support"),
                    ("support-article", "/support/mobile-control/phone-wont-pair"),
                    ("not-found", "/blog/nope"),
                ]:
                    shot.goto(base + path, wait_until="networkidle")
                    shot.wait_for_timeout(300)
                    shot.screenshot(path=str(out / f"{name}-{width}.png"), full_page=True)

        check("no uncaught page errors", not page_errors, json.dumps(page_errors))
        browser.close()

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


main()
