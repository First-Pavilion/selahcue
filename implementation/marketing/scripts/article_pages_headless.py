#!/usr/bin/env python3
"""Behavioural check for the blog / docs / support detail pages (GAP-08, 17tnw2b0q9h).

`npm test` pins the content source and the router's resolution under node. This proves what
node cannot: that the REAL production bundle in `dist/`, in a real browser, does the things
those pages promise.

  - the ENTRY chunk carries no article text and no citation paths (the corpus is lazy);
  - an unknown slug shows the not-found page, with ONE <main>, and leaves the address bar
    exactly as typed (including %20, %C3%A9, %2F and a malformed %ZZ), including when it is
    reached from another article (a param-only change, which no route guard sees);
  - every internal link on the three index pages and in all 28 article bodies navigates to a
    real page (and a real anchor), and every <a> has an href and is Tab-reachable (UiButton
    used to render router links with NO href);
  - each article sets its own title and description, article -> article follows, and the
    index gives the defaults back;
  - focus lands on the <h1> after in-app navigation but NOT on a direct load, so the skip link
    stays reachable; after "Skip to article", the next Tab stop is below the sticky navbar;
  - a table-of-contents click lands BELOW the sticky navbar, instantly under
    prefers-reduced-motion; the clearance equals the navbar's real height;
  - accessibility: clean heading names, unique anchor labels, no false aria-current, live
    regions present before they speak, focus after the feedback buttons, labelled landmarks,
    text and link contrast of the new markup (WCAG AA);
  - copy-to-clipboard, the phone sidebar fold, support search, one <h1>, new-tab links with
    rel="noopener noreferrer", the fixed "SelahCue Team" byline, no duplicate ids.

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
import re
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


ROUTER = "document.querySelector('#app').__vue_app__.config.globalProperties.$router"

# Effective text colour vs the nearest opaque background, as WCAG relative-luminance contrast.
CONTRAST_JS = """
(sel) => {
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(',').map((x) => parseFloat(x)); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const el = document.querySelector(sel); if (!el) return null;
  const fg = parse(getComputedStyle(el).color);
  let bg = null, n = el;
  while (n && n.nodeType === 1) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0.5) { bg = c; break; } n = n.parentElement; }
  if (!bg) bg = { r: 11, g: 13, b: 18, a: 1 };
  const a = lum(fg), b = lum(bg); const hi = Math.max(a, b), lo = Math.min(a, b);
  return (hi + 0.05) / (lo + 0.05);
}
"""


# Same rule as scripts/responsive_sweep.py's TOUCH_JS: visible, standalone interactive elements
# in <main> are at least 44px in their smaller dimension; an inline link in running prose is exempt.
TOUCH_JS = """
() => {
  const bad = [];
  for (const el of document.querySelectorAll('main a, main button')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (el.closest('[hidden], [aria-hidden=true]')) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.width <= 1 && r.height <= 1) continue;
    if (el.tagName === 'A' && cs.display === 'inline' && el.closest('p, li, dd, blockquote, label')) continue;
    if (Math.min(r.width, r.height) < 43.5) bad.push(el.tagName.toLowerCase() + '.' + String(el.className).split(' ')[0] + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  }
  return bad.slice(0, 12);
}
"""


def main() -> None:
    # THREADED: Chromium opens speculative idle connections, and a one-request-at-a-time
    # server lets one of them stall every later navigation until it times out.
    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = Server(("127.0.0.1", 0), Handler)
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

        # A loaded CI box or laptop can take well over Playwright's 30 s default to reach
        # `networkidle`; a generous bound keeps the gate about behaviour, not timing.
        def new_context(**kw):
            c = browser.new_context(**kw)
            c.set_default_timeout(60_000)
            c.set_default_navigation_timeout(120_000)
            return c

        # ---- the entry chunk stays small and clean --------------------------------------
        html = (DIST / "index.html").read_text(encoding="utf-8")
        entry_src = re.search(r'<script[^>]+type="module"[^>]+src="/(assets/[^"]+\.js)"', html)
        entry = (DIST / entry_src.group(1)).read_text(encoding="utf-8") if entry_src else ""
        check("entry chunk found", bool(entry), str(entry_src))
        check("entry chunk is under 120 kB (it was 161 kB with the corpus in it)", 0 < len(entry.encode()) < 120_000, str(len(entry.encode())))
        check("entry chunk carries no article text", "Connections drop" not in entry and "Stage theme" not in entry)
        check("entry chunk carries no citation paths or notes", "implementation/desktop/crates" not in entry and "supports:" not in entry)
        every_js = "".join(f.read_text(encoding="utf-8") for f in (DIST / "assets").glob("*.js"))
        check("no chunk anywhere carries a citation path", "implementation/desktop/crates" not in every_js)

        ctx = new_context(viewport={"width": 1440, "height": 900})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        pg = ctx.new_page()
        page_errors: list[str] = []
        pg.on("pageerror", lambda e: page_errors.append(str(e)))

        # ---- discover every real article from the three index pages ----------------------
        pg.goto(base + "/blog", wait_until="networkidle")
        blog_links = pg.eval_on_selector_all("main a[href^='/blog/']", "els => [...new Set(els.map(e => e.getAttribute('href')))]")
        pg.goto(base + "/docs", wait_until="networkidle")
        docs_links = pg.eval_on_selector_all("main a[href^='/docs/']", "els => [...new Set(els.map(e => e.getAttribute('href')))]")
        pg.goto(base + "/support", wait_until="networkidle")
        support_links = pg.eval_on_selector_all("main a[href^='/support/']", "els => [...new Set(els.map(e => e.getAttribute('href')))]")
        # The featured post is a UiButton link, the grid uses plain links; docs and support list everything.
        check("index pages link to every article (5 blog, 12 docs, 11 support)", len(set(blog_links)) >= 4 and len(docs_links) == 12 and len(support_links) == 11, f"{len(blog_links)}/{len(docs_links)}/{len(support_links)}")
        all_articles = sorted(set(blog_links + docs_links + support_links))

        # ---- every <a> has an href and can be reached by Tab -----------------------------
        for path in ["/blog", "/docs", "/support", POST, "/docs/display-outputs/ndi-output", "/support/mobile-control/phone-wont-pair"]:
            pg.goto(base + path, wait_until="networkidle")
            bad = pg.eval_on_selector_all("a", "els => els.filter(e => !e.getAttribute('href')).map(e => e.outerHTML.slice(0, 90))")
            check(f"{path}: every <a> has an href", not bad, str(bad))
            untabbable = pg.eval_on_selector_all("main a[href]", "els => els.filter(e => e.tabIndex < 0 && e.offsetParent !== null).map(e => e.outerHTML.slice(0, 90))")
            check(f"{path}: no visible link is removed from the Tab order", not untabbable, str(untabbable))

        pg.goto(base + "/support/mobile-control/phone-wont-pair", wait_until="networkidle")
        reached = False
        for _ in range(80):
            pg.keyboard.press("Tab")
            if "Contact support" in pg.evaluate("document.activeElement.textContent || ''"):
                reached = pg.evaluate("document.activeElement.tagName") == "A" and bool(pg.evaluate("document.activeElement.getAttribute('href')"))
                break
        check("Tab reaches the 'Contact support' button, as a real link", reached)
        pg.goto(base + "/blog", wait_until="networkidle")
        check("featured 'Read story' is a real link to the post", pg.locator("a:has-text('Read story')").get_attribute("href") == POST)
        pg.goto(base + "/support", wait_until="networkidle")
        check("support 'Start here' rows are real links", all(pg.eval_on_selector_all("a:has-text('Read article')", "els => els.map(e => !!e.getAttribute('href'))")))

        # ---- every internal link navigates somewhere real --------------------------------
        links_checked = 0
        dead: list[str] = []
        for page_path in ["/blog", "/docs", "/support"] + all_articles:
            pg.goto(base + page_path, wait_until="networkidle")
            hrefs = pg.eval_on_selector_all("main a[href^='/']", "els => [...new Set(els.map(e => e.getAttribute('href')))]")
            for h in hrefs:
                links_checked += 1
                result = pg.evaluate(
                    "async (h) => { await " + ROUTER + ".push(h); await new Promise(r => setTimeout(r, 120));"
                    " const hash = h.includes('#') ? h.split('#')[1] : '';"
                    " return { h1: (document.querySelector('h1') || {}).textContent || '', anchor: hash ? !!document.getElementById(hash) : true } }",
                    h,
                )
                if result["h1"].startswith("We couldn't find") or not result["anchor"]:
                    dead.append(f"{page_path} -> {h}")
        check(f"all {links_checked} internal links in the index and article pages resolve", links_checked > 100 and not dead, str(dead[:5]))

        # ---- unknown slugs ------------------------------------------------------------
        for path in [
            "/blog/nope",
            "/docs/getting-started/nope",
            "/docs/nope/nope",
            "/support/troubleshooting/nope",
            "/blog/a%20b",
            "/blog/%C3%A9",
            "/docs/x%2Fy/z",
            "/blog/%ZZ",
        ]:
            pg.goto(base + path, wait_until="networkidle")
            check(
                f"unknown {path}: not-found page, ONE <main>, address bar untouched",
                pg.url == base + path and pg.inner_text("h1").startswith("We couldn't find") and pg.locator("main").count() == 1,
                pg.url,
            )
        # A category-only prefix matches no article route and falls to the site catch-all. That
        # page predates this work and renders its own <main>, so only the URL and message are asserted.
        pg.goto(base + "/docs/getting-started", wait_until="networkidle")
        check("category-only prefix /docs/getting-started: site not-found page, address bar untouched", pg.url == base + "/docs/getting-started" and pg.inner_text("h1").startswith("We couldn't find"))
        pg.goto(base + "/blog/nope", wait_until="networkidle")
        check("unknown slug shows the site title and a non-empty description", pg.title().startswith("SelahCue") and len(pg.get_attribute("meta[name=description]", "content") or "") > 20, pg.title())

        # same-route PARAM change: article -> unknown slug (no route guard runs for this)
        for start, unknown in [(POST, "/blog/no-such-post"), ("/docs/display-outputs/ndi-output", "/docs/display-outputs/no-such"), ("/support/mobile-control/phone-wont-pair", "/support/mobile-control/no-such")]:
            pg.goto(base + start, wait_until="networkidle")
            pg.evaluate("async (u) => { await " + ROUTER + ".push(u); await new Promise(r => setTimeout(r, 200)) }", unknown)
            ok = pg.url.endswith(unknown) and pg.inner_text("h1").startswith("We couldn't find") and pg.locator("main").count() == 1
            default_title = pg.title().startswith("SelahCue \u2014") or pg.title().startswith("SelahCue —")
            check(f"{start} -> {unknown}: not-found, URL kept, ONE <main>", ok, pg.url)
            check(f"{start} -> {unknown}: title and description are the site defaults, not stale", default_title and len(pg.get_attribute("meta[name=description]", "content") or "") > 20, pg.title())
            pg.evaluate("async (u) => { await " + ROUTER + ".push(u); await new Promise(r => setTimeout(r, 200)) }", start)
            check(f"{start}: coming back from an unknown slug renders the article again", pg.locator("h1").count() == 1 and not pg.inner_text("h1").startswith("We couldn't find"))

        # ---- title / meta / focus across navigation -----------------------------------
        pg.goto(base + "/blog", wait_until="networkidle")
        default_title = pg.title()
        default_description = pg.get_attribute("meta[name=description]", "content")
        pg.click("text=Read story")
        pg.wait_for_url("**" + POST)
        pg.wait_for_timeout(300)
        check("article sets its own document.title", pg.title() == "Why offline-first matters for Sunday morning \u2014 SelahCue", pg.title())
        check("article sets its meta description", "desktop" in (pg.get_attribute("meta[name=description]", "content") or ""))
        check("focus moves to the <h1> after in-app navigation", pg.evaluate("document.activeElement.tagName") == "H1")
        check("exactly one <h1> on a blog post", pg.locator("h1").count() == 1)
        check("the byline names the team and nobody else", pg.inner_text(".bp-byline").startswith("SelahCue Team") and pg.inner_text(".bp-author-name") == "SelahCue Team")
        pg.click("a.pn-link.is-next")
        pg.wait_for_timeout(500)
        check("article -> article navigation keeps the NEW title", pg.title().startswith(NEXT_POST_TITLE), pg.title())
        pg.goto(base + "/blog", wait_until="networkidle")
        check("index page gets the default title back", pg.title() == default_title, pg.title())
        pg.click("text=Read story")
        pg.wait_for_url("**" + POST)
        pg.click("nav[aria-label=Breadcrumb] >> text=Blog")
        pg.wait_for_url("**/blog")
        check("leaving an article restores the default description too", pg.get_attribute("meta[name=description]", "content") == default_description)

        # ---- the default title is a constant, not whatever the first page left behind ------
        # Cold-load a page, let it set its OWN title and description (what /privacy does once
        # the legal pages land), and only then open an article, so the lazy article module loads
        # while the document shows that page's values. Leaving the article for the home page
        # must show the site defaults, not the first page's title.
        cold = ctx.new_page()
        cold.goto(base + "/privacy", wait_until="networkidle")
        cold.evaluate("document.title = 'SelahCue Privacy Policy'; document.querySelector('meta[name=description]').setAttribute('content', 'The privacy page description.')")
        cold.evaluate("async (u) => { await " + ROUTER + ".push(u); await new Promise(r => setTimeout(r, 300)) }", POST)
        check("cold-load /privacy, open an article: the article owns the title", cold.title().startswith("Why offline-first matters"), cold.title())
        cold.evaluate("async () => { await " + ROUTER + ".push('/'); await new Promise(r => setTimeout(r, 300)) }")
        check("...then the home page shows the SITE default title, not /privacy's", cold.title() == default_title, cold.title())
        check("...and the SITE default description, not /privacy's", cold.get_attribute("meta[name=description]", "content") == default_description, str(cold.get_attribute("meta[name=description]", "content")))
        cold.close()

        # ---- anchors clear the sticky navbar; instant under reduced motion ---------------
        pg.goto(base + POST, wait_until="networkidle")
        navbar_bottom = pg.evaluate("document.querySelector('header').getBoundingClientRect().bottom")
        margin = pg.evaluate("parseFloat(getComputedStyle(document.querySelector('.ab-hwrap > h2')).scrollMarginTop)")
        check("the anchor clearance is the navbar's real height plus a gap (CSS and navbar agree)", navbar_bottom + 8 <= margin <= navbar_bottom + 40, f"navbar bottom {navbar_bottom}, heading scroll-margin-top {margin}")
        check("focusable article controls carry the same clearance", abs(pg.evaluate("parseFloat(getComputedStyle(document.querySelector('.bp a[href]')).scrollMarginTop)") - margin) < 0.5)
        # A ROOT scroll-padding-top makes focusing a control in the STICKY navbar scroll the page to
        # the top (the control sits inside the padded band and cannot move clear of it, so the
        # browser scrolls as far as it can). That is what closing the mobile navigation sheet does
        # (focus returns to the menu button), and what Shift+Tab into the header does. So the page
        # must carry no root padding, and focusing a navbar control must leave the scroll alone.
        pg.evaluate("window.scrollTo(0, 500)")
        pg.wait_for_function("window.scrollY > 100")
        scroll_before = pg.evaluate("window.scrollY")
        pg.evaluate("document.querySelector('#app header a[href], #app header button').focus()")
        pg.wait_for_timeout(250)  # the browser's focus scroll is not always synchronous
        scroll_after = pg.evaluate("window.scrollY")
        check("the page has no non-zero root scroll-padding", pg.evaluate("parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0") == 0)
        check("focusing a control in the sticky navbar does not move the page (closing the mobile menu does exactly this)", abs(scroll_after - scroll_before) < 2, f"{scroll_before} -> {scroll_after}")
        pg.evaluate("window.scrollTo(0, 0)")
        pg.click("a.bp-toc-link:has-text('The desktop is in charge')")
        pg.wait_for_timeout(900)
        top = pg.evaluate("document.getElementById('sec-the-desktop-is-in-charge').getBoundingClientRect().top")
        check("toc click puts the hash in the URL", pg.url.endswith("#sec-the-desktop-is-in-charge"), pg.url)
        check("toc target lands below the sticky navbar", navbar_bottom < top < navbar_bottom + 60, f"top {top}, navbar bottom {navbar_bottom}")

        calm = new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        cp = calm.new_page()
        cp.goto(base + POST, wait_until="networkidle")
        cp.click("a.bp-toc-link:has-text('Autosave, so a crash')")
        cp.wait_for_timeout(60)
        top = cp.evaluate("document.getElementById('sec-autosave-so-a-crash-is-a-short-interruption').getBoundingClientRect().top")
        check("under prefers-reduced-motion the anchor scroll is instant (already in place 60 ms after the click)", navbar_bottom < top < navbar_bottom + 60, str(top))

        # ---- same-page hash links must not all claim to be the current page ---------------
        pg.goto(base + POST, wait_until="networkidle")
        check("blog: the table of contents has links, and none claims aria-current=page", pg.locator("a.bp-toc-link").count() >= 3 and pg.locator("a[href*='#'][aria-current=page]").count() == 0)
        pg.goto(base + "/docs", wait_until="networkidle")
        # `.sidebar-nav a.nav-item`, not bare `a.nav-item`: the site navbar's links share that class.
        topics = pg.locator("section.topic").count()
        sidebar = pg.locator(".sidebar-nav a.nav-item")
        check("docs index: the topic sidebar has one link per topic, and none claims aria-current=page", topics >= 6 and sidebar.count() == topics and pg.locator("a[href*='#'][aria-current=page]").count() == 0, f"{sidebar.count()} links, {topics} topics")

        # ---- accessibility of the article body ------------------------------------------
        pg.goto(base + "/docs/display-outputs/ndi-output", wait_until="networkidle")
        names = pg.eval_on_selector_all(".ab-h2, .ab-h3", "els => els.map(e => e.textContent.trim())")
        check("heading text is clean (no anchor glyph in the heading's name)", names and all(not n.endswith("#") for n in names), str(names[:3]))
        labels = pg.eval_on_selector_all("a.ab-anchor", "els => els.map(e => e.getAttribute('aria-label'))")
        check("every heading anchor has a UNIQUE, descriptive label", len(labels) == len(set(labels)) and all(l.startswith("Link to section: ") for l in labels) and len(labels) >= 3, str(labels[:3]))
        check("no same-page hash link claims aria-current=page", pg.locator("a[href*='#'][aria-current=page]").count() == 0)
        check("the docs sidebar is a labelled landmark", bool(pg.get_attribute("aside.da-side", "aria-label")))
        dup = pg.evaluate("(() => { const ids = [...document.querySelectorAll('[id]')].map(e => e.id); return ids.filter((x, i) => ids.indexOf(x) !== i) })()")
        check("no duplicate ids on a docs article", not dup, str(dup))
        check("exactly one <main> on a docs article", pg.locator("main").count() == 1)
        check("a live region for feedback exists BEFORE it speaks", pg.locator(".da-feedback-result[role=status]").count() == 1 and pg.inner_text(".da-feedback-result").strip() == "")
        pg.click("button.da-btn:has-text('Yes')")
        pg.wait_for_timeout(150)
        check("after 'Yes' focus moves to the thanks message, which reads 'Glad it helped.'", pg.evaluate("document.activeElement.className").startswith("da-feedback-result") and "Glad it helped" in pg.inner_text(".da-feedback-result"))

        for sel, label in [
            (".da-link[aria-current=page]", "docs sidebar current link"),
            (".da-all", "docs 'All documentation' link"),
            (".ab-callout.is-warning .ab-callout-title", "warning callout title"),
            (".ab-callout.is-info .ab-callout-title", "info callout title"),
            (".ab-callout-text", "callout text"),
            (".bc-link", "breadcrumb link"),
            (".da-edit", "suggest-an-edit link"),
            (".pn-dir", "prev/next label"),
            (".da-meta", "read-time line"),
        ]:
            ratio = pg.evaluate(CONTRAST_JS, sel)
            check(f"contrast >= 4.5:1: {label}", ratio is not None and ratio >= 4.5, f"{ratio}")
        pg.goto(base + "/docs/timers-plans/build-a-service-plan", wait_until="networkidle")
        ratio = pg.evaluate(CONTRAST_JS, ".ab-callout .it-link")
        check("contrast >= 4.5:1: a link inside a callout", ratio is not None and ratio >= 4.5, f"{ratio}")
        pg.goto(base + POST, wait_until="networkidle")
        for sel, label in [(".it-link", "inline link on the page background"), (".bp-link", "author-card link"), (".bp-byline", "byline"), (".bp-related-cat", "related category label"), (".bp-toc-link", "table-of-contents link")]:
            ratio = pg.evaluate(CONTRAST_JS, sel)
            check(f"contrast >= 4.5:1: blog {label}", ratio is not None and ratio >= 4.5, f"{ratio}")

        # ---- breadcrumbs land on a real anchor ------------------------------------------
        pg.goto(base + "/docs/display-outputs/ndi-output", wait_until="networkidle")
        pg.click("nav[aria-label=Breadcrumb] >> text=Display & Outputs")
        pg.wait_for_timeout(500)
        check("docs breadcrumb category link lands on an existing section", pg.url.endswith("/docs#display-outputs") and pg.evaluate("!!document.getElementById('display-outputs')"), pg.url)
        pg.goto(base + "/support/mobile-control/phone-wont-pair", wait_until="networkidle")
        pg.click("nav[aria-label=Breadcrumb] >> text=Mobile Control")
        pg.wait_for_timeout(500)
        check("support breadcrumb category link lands on an existing section", pg.url.endswith("/support#mobile-control") and pg.evaluate("!!document.getElementById('mobile-control')"), pg.url)

        # ---- anchors and copy-to-clipboard ------------------------------------------------
        pg.goto(base + POST, wait_until="networkidle")
        pg.click("text=Copy link")
        pg.wait_for_timeout(200)
        check("copy link announces its result", "copied" in pg.inner_text("[role=status]").lower())
        check("copy link copies this post's URL", pg.evaluate("navigator.clipboard.readText()").endswith(POST))

        # ---- new-tab links never hand over window.opener ----------------------------------
        weak = []
        for path in [POST, "/docs/display-outputs/ndi-output", "/support/mobile-control/phone-wont-pair", "/docs/mobile-control/pair-a-phone"]:
            pg.goto(base + path, wait_until="networkidle")
            weak += pg.eval_on_selector_all("a[target=_blank]", "els => els.filter(e => !/noopener/.test(e.rel) || !/noreferrer/.test(e.rel)).map(e => e.href)")
        check("every new-tab link carries rel=noopener noreferrer", not weak, str(weak))

        # ---- docs article: skip link, landmarks, focus is not hidden under the navbar -----
        pg.goto(base + "/docs/display-outputs/ndi-output", wait_until="networkidle")
        check("direct load does NOT steal focus into the article", pg.evaluate("document.activeElement.tagName") != "H1")
        pg.keyboard.press("Tab")
        tabs = 1
        while "da-skip" not in pg.evaluate("document.activeElement.className") and tabs < 25:
            pg.keyboard.press("Tab")
            tabs += 1
        check("'Skip to article' is reachable by Tab", "da-skip" in pg.evaluate("document.activeElement.className"), f"{tabs} tabs")
        check(
            "'Skip to article' is visible while focused and below the navbar",
            pg.evaluate("(()=>{const r=document.activeElement.getBoundingClientRect();return r.left>=0&&r.width>0&&r.top>=%f})()" % navbar_bottom),
        )
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(300)
        check("'Skip to article' moves focus to the article", pg.evaluate("document.activeElement.id") == "docs-article")
        pg.keyboard.press("Tab")
        pg.wait_for_timeout(200)
        focus_top = pg.evaluate("document.activeElement.getBoundingClientRect().top")
        check("the first Tab stop after the skip is not hidden under the sticky navbar (WCAG 2.4.11)", focus_top >= navbar_bottom - 1, f"top {focus_top}, navbar bottom {navbar_bottom}")
        check("breadcrumb marks the current page", pg.locator("nav[aria-label=Breadcrumb] [aria-current=page]").count() == 1)
        check("sidebar marks the current page", pg.locator("a.da-link[aria-current=page]").count() == 1)

        # ---- phone: sidebar folds ------------------------------------------------------
        phone = new_context(viewport={"width": 375, "height": 800}).new_page()
        phone.goto(base + "/docs/display-outputs/ndi-output", wait_until="networkidle")
        btn = phone.locator("button.da-menu-btn")
        check("phone: docs menu starts folded", btn.get_attribute("aria-expanded") == "false" and not phone.locator("#docs-nav").is_visible())
        btn.click()
        check("phone: docs menu opens (aria-expanded true)", btn.get_attribute("aria-expanded") == "true" and phone.locator("#docs-nav").is_visible())
        phone.locator("#docs-nav details[open] a.da-link:not([aria-current])").first.click()
        phone.wait_for_timeout(500)
        check("phone: docs menu folds after navigating", not phone.locator("#docs-nav").is_visible())
        check("phone: docs article does not scroll sideways", not phone.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
        for path in [POST, "/support/mobile-control/phone-wont-pair", "/blog", "/support"]:
            phone.goto(base + path, wait_until="networkidle")
            check(f"phone: {path} does not scroll sideways", not phone.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
        # 44px touch targets on the article pages (WCAG 2.5.8), measured the way the responsive
        # sweep measures them: every `main` link/button, bar a link inside running prose.
        for path in [POST, "/docs/display-outputs/ndi-output", "/support/mobile-control/phone-wont-pair"]:
            phone.goto(base + path, wait_until="networkidle")
            small = phone.evaluate(TOUCH_JS)
            check(f"phone: {path} has no touch target under 44px", not small, str(small[:4]))

        # ---- support index search -------------------------------------------------------
        sp = ctx.new_page()
        sp.goto(base + "/support", wait_until="networkidle")
        check("the search status region exists BEFORE anything is typed, and is empty", sp.locator("[role=status].sr-only").count() == 1 and sp.inner_text("[role=status].sr-only").strip() == "")
        sp.fill("input[type=search]", "ndi")
        sp.wait_for_timeout(200)
        body = sp.inner_text("body")
        check("support search filters the articles", "NDI toggle" in body and "Knowledge Base Categories" not in body)
        check("support search announces the count through the same region", "matches" in sp.locator("[role=status].sr-only").text_content())
        for q in ["pairing", "crash recovery", "stage display", "blackout", "phone pair", "NDI", "Pairing"]:
            sp.fill("input[type=search]", q)
            sp.wait_for_timeout(120)
            check(f"support search '{q}' finds something", "No help articles match" not in sp.inner_text("body"))
        sp.fill("input[type=search]", "zzzz")
        sp.wait_for_timeout(200)
        check("support search says when nothing matches", "No help articles match" in sp.locator("[role=status].sr-only").text_content())

        # ---- optional screenshots ------------------------------------------------------
        if SHOTS:
            out = Path(SHOTS)
            out.mkdir(parents=True, exist_ok=True)
            for width in (375, 1440):
                shot = new_context(viewport={"width": width, "height": 900}).new_page()
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
