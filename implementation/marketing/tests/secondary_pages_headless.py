#!/usr/bin/env python3
"""Real-browser checks for the nine secondary pages (ClickUp 17tnw2b2cez).

`tests/secondaryPages.test.ts` reads the source and server-renders the views. This drives the BUILT
site (`dist/`) in a real browser, because what it cannot see is what the Figma audit found wrong:
computed size and colour, where a box lands, the order Tab visits things in, whether a focus ring is
drawn, whether the whole featured card is one link, whether the page scrolls sideways. Every number
quoted next to a check is a Figma value from `docs/design/visual-parity/marketing/figma-style/*.json`
or an accessibility floor (WCAG AA 4.5:1 for normal text).

Usage (from implementation/marketing, after `npm run build`):
    /usr/bin/python3 tests/secondary_pages_headless.py [--engine chromium|webkit|both] [--shots DIR]

Needs Playwright and an engine, and the network for Inter. If either is missing this exits 0 with a
LOUD skip unless SELAHCUE_HEADLESS_REQUIRE=1, which makes a missing engine a hard failure.

This file is not wired into `npm test` (that globs `tests/*.test.ts`) or CI: that needs a `package.json`
script and a workflow line, which are outside this ticket's footprint (reported to the coordinator).

Exit codes: 0 pass (or loud skip), 1 a check failed, 2 infrastructure problem, 3 a required engine is unavailable.
"""

from __future__ import annotations

import argparse
import http.server
import mimetypes
import os
import re
import socketserver
import sys
import threading
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETING = HERE.parent
DIST = Path(os.environ.get("SELAHCUE_MARKETING_DIST") or (MARKETING / "dist"))
REQUIRE = os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1"

# Colours as `getComputedStyle` writes them, from tokens.css.
BASE = "rgb(11, 13, 18)"  # --sc-base
SURFACE = "rgb(20, 22, 29)"  # --sc-surface
ELEVATED = "rgb(28, 31, 40)"  # --sc-elevated
PRIMARY = "rgb(110, 92, 240)"  # --sc-primary
TEXT = "rgb(244, 246, 251)"  # --sc-text
SECONDARY = "rgb(167, 174, 190)"  # --sc-text-secondary
PREVIEW = "rgb(53, 192, 138)"  # --sc-preview
WARN = "rgb(245, 165, 36)"  # --sc-warn


class Checks:
    """Counts every assertion, so a check that silently stops running changes the total."""

    def __init__(self, engine: str) -> None:
        self.engine = engine
        self.count = 0
        self.failures: list[str] = []

    def ok(self, cond: object, message: str) -> bool:
        self.count += 1
        if not cond:
            self.failures.append(f"[{self.engine}] {message}")
        return bool(cond)

    def eq(self, got: object, want: object, what: str) -> bool:
        return self.ok(got == want, f"{what}: got {got!r}, want {want!r}")

    def near(self, got: float, want: float, tol: float, what: str) -> bool:
        return self.ok(abs(got - want) <= tol, f"{what}: got {got:.2f}, want {want} (+/-{tol})")


# ---------------------------------------------------------------------------------- static server


class SpaHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        rel = urllib.parse.unquote(urllib.parse.urlparse(self.path).path).lstrip("/")
        root = os.path.realpath(DIST)
        target = os.path.realpath(os.path.join(root, rel))
        inside = target == root or target.startswith(root + os.sep)
        if not (inside and os.path.isfile(target)):
            if os.path.splitext(rel)[1]:
                self.send_error(404)
                return
            target = os.path.join(root, "index.html")
        body = Path(target).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def serve() -> tuple[socketserver.TCPServer, int]:
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SpaHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


# ---------------------------------------------------------------------------------- browser helpers

FONT_WEIGHTS = (400, 500, 600, 700)

BOX_JS = """(sel) => { const e = document.querySelector(sel); if (!e) return null;
  const r = e.getBoundingClientRect(); return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height, right: r.right + scrollX, bottom: r.bottom + scrollY }; }"""

STYLE_JS = """([sel, pseudo, props]) => { const e = document.querySelector(sel); if (!e) return null;
  const c = getComputedStyle(e, pseudo || null); const o = {}; for (const p of props) o[p] = c.getPropertyValue(p); return o; }"""

# The colour of the nearest opaque background behind an element (walking up through transparent ancestors).
BACKDROP_JS = """(sel) => { let e = document.querySelector(sel); while (e) { const b = getComputedStyle(e).backgroundColor;
  const m = b.match(/[\\d.]+/g); if (m && (m.length < 4 || Number(m[3]) > 0.99)) return b; e = e.parentElement; } return 'rgb(11, 13, 18)'; }"""

LUMINANCE_JS = """([fg, bg]) => { const parse = (s) => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const L = (rgb) => 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
  const a = L(parse(fg)), b = L(parse(bg)); return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); }"""

FOCUS_JS = """() => { const a = document.activeElement; if (!a || a === document.body) return null;
  return (a.getAttribute('aria-label') || (a.labels && a.labels[0] && a.labels[0].innerText.replace('*', '').trim()) ||
    (a.innerText || '').trim().slice(0, 40) || a.getAttribute('placeholder') || a.tagName).replace(/\\s+/g, ' '); }"""


def box(page, sel: str) -> dict:
    got = page.evaluate(BOX_JS, sel)
    if got is None:
        raise LookupError(f"nothing matches {sel!r}")
    return got


def cs(page, sel: str, props: list[str], pseudo: str | None = None) -> dict:
    got = page.evaluate(STYLE_JS, [sel, pseudo, props])
    if got is None:
        raise LookupError(f"nothing matches {sel!r}")
    return got


def ratio(page, fg: str, bg: str) -> float:
    return page.evaluate(LUMINANCE_JS, [fg, bg])


def text_contrast(page, sel: str) -> float:
    return ratio(page, cs(page, sel, ["color"])["color"], page.evaluate(BACKDROP_JS, sel))


def open_page(page, base: str, path: str, ready: str, attempts: int = 2) -> None:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            page.goto(base + path, wait_until="load", timeout=45000)
            page.wait_for_selector(ready, timeout=45000)
            page.evaluate(
                """async (weights) => { await Promise.all(weights.map((w) => document.fonts.load(`${w} 16px Inter`))); await document.fonts.ready; }""",
                list(FONT_WEIGHTS),
            )
            page.wait_for_function("document.getAnimations().every((a) => a.playState !== 'running')", timeout=5000)
            widen_for_scrollbar(page)
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            print(f"NOTE: opening {path} failed on attempt {attempt}/{attempts}: {str(exc).splitlines()[0][:120]}")
    raise RuntimeError(f"{path} did not open after {attempts} attempts") from last



def widen_for_scrollbar(page) -> None:
    """WebKit reserves a 12px classic scrollbar (the site styles `::-webkit-scrollbar` at 12px) that Chromium
    headless does not, so the LAYOUT viewport there is 1428 in a 1440 window and every Figma width reads 6px off.
    The Figma frames are 1440 wide: when the window is the default 1440, widen it by the bar so the layout is 1440."""
    size = page.viewport_size
    if size and size["width"] == 1440:
        bar = page.evaluate("window.innerWidth - document.documentElement.clientWidth")
        if bar > 0:
            page.set_viewport_size({"width": 1440 + bar, "height": size["height"]})
            page.wait_for_timeout(150)


def press_tab(page, c: Checks) -> None:
    """Tab the way a keyboard user of this engine does (macOS WebKit needs Option+Tab to reach buttons and links)."""
    alt = c.engine == "webkit" and sys.platform == "darwin"
    page.keyboard.press("Alt+Tab" if alt else "Tab")


def focus_order(page, c: Checks, start_selector: str, steps: int) -> list[str]:
    """Focus `start_selector`'s predecessor by focusing it and pressing Tab `steps` times; returns what held focus each time."""
    page.focus(start_selector)
    seen = [page.evaluate(FOCUS_JS)]
    for _ in range(steps):
        press_tab(page, c)
        seen.append(page.evaluate(FOCUS_JS))
    return seen


# ---------------------------------------------------------------------------------- the checks


def check_contact(page, c: Checks, base: str) -> None:
    open_page(page, base, "/contact", ".contact-form-card")
    form, cards = box(page, ".contact-form-card"), box(page, ".method-cards")
    # 497:145 form card 604 wide at x96, 497:166 cards 604 wide at x740 (the form is LEFT, in Figma's column order)
    c.near(form["x"], 96, 1, "contact: form card x (Figma 96)")
    c.near(form["w"], 604, 1, "contact: form card width (Figma 604)")
    c.near(cards["x"], 740, 1, "contact: cards column x (Figma 740)")
    c.near(cards["w"], 604, 1, "contact: cards column width (Figma 604)")
    c.near(box(page, ".contact-form-card")["y"], box(page, ".method-cards")["y"], 1, "contact: both columns start at the same top")
    n = page.locator(".method-card").count()
    c.eq(n, 3, "contact: three method cards")
    ys = [page.locator(".method-card").nth(i).bounding_box() for i in range(n)]
    for i, b in enumerate(ys):
        c.near(b["height"], 99, 1.5, f"contact: method card {i} height (Figma 99)")
    c.near(ys[1]["y"] - (ys[0]["y"] + ys[0]["height"]), 16, 1, "contact: 16px between method cards (Figma 16)")
    tile = cs(page, ".method-icon", ["width", "height", "border-top-left-radius"])
    c.eq((tile["width"], tile["height"], tile["border-top-left-radius"]), ("46px", "46px", "12px"), "contact: icon tile 46x46 r12 (Figma 497:168)")
    h = page.locator(".method-card h2").first
    c.eq(h.evaluate("e => getComputedStyle(e).fontSize"), "16.5px", "contact: card title 16.5px (Figma)")
    for i in range(3):
        c.near(page.locator(".contact-form input").nth(i).bounding_box()["height"], 44, 0.6, f"contact: field {i} is 44px high (Figma 497:149)")
    c.near(page.locator(".contact-form textarea").bounding_box()["height"], 120, 0.6, "contact: textarea 120 high (Figma 497:161)")
    send = page.locator(".contact-form .ui-button").last.bounding_box()
    c.near(send["height"], 49, 0.6, "contact: Send button 49 high (Figma 497:163)")
    c.near(send["width"], 540, 1.5, "contact: Send button fills the card (Figma 540)")
    # placeholders and the counter take the secondary ink (contact-13)
    ph = cs(page, ".contact-form input", ["color"], pseudo="::placeholder")["color"]
    c.eq(ph, SECONDARY, "contact: placeholder ink is --sc-text-secondary")
    inp_bg = page.evaluate(BACKDROP_JS, ".contact-form input")
    c.ok(ratio(page, ph, inp_bg) >= 4.5, f"contact: placeholder passes AA ({ratio(page, ph, inp_bg):.2f}:1)")
    c.ok(text_contrast(page, ".char-count") >= 4.5, f"contact: counter passes AA ({text_contrast(page, '.char-count'):.2f}:1)")
    # Tab order: form first (Figma), then the cards
    order = focus_order(page, c, ".contact-form input >> nth=0", 7)
    c.eq(
        order[:5],
        ["Full name", "Email", "Church / organization", "How can we help?", "Send message"],
        "contact: Tab visits the form fields and the button first",
    )
    c.ok(all(x and ("@" in x or x.startswith(("Join", "Schedule"))) for x in order[5:8]), f"contact: then the three card links ({order[5:8]})")
    # validation on blur, and the 100 character limit
    page.reload(wait_until="load")
    page.wait_for_selector(".contact-form-card")
    page.focus(".contact-form input >> nth=0")
    press_tab(page, c)
    c.ok("Name is required" in page.locator(".contact-form").inner_text(), "contact: leaving an empty required field shows its error (blur validation)")
    page.fill(".contact-form input >> nth=0", "a" * 101)
    press_tab(page, c)
    c.ok("100 characters or fewer" in page.locator(".contact-form").inner_text(), "contact: a 101-character name is refused")
    c.eq(page.locator("form[aria-label='Contact us']").count(), 1, "contact: the form is named Contact us")
    c.eq(page.locator("[aria-required='true']").count(), 3, "contact: three fields are aria-required")


def check_support(page, c: Checks, base: str) -> None:
    open_page(page, base, "/support", ".search-input")
    s = box(page, ".search-input")
    c.near(s["w"], 620, 1, "support: search 620 wide (Figma 498:144)")
    c.near(s["h"], 52, 0.6, "support: search 52 high")
    c.eq(cs(page, ".search-input", ["border-top-left-radius"])["border-top-left-radius"], "14px", "support: search radius 14")
    c.eq(cs(page, ".search-input", ["color"], pseudo="::placeholder")["color"], SECONDARY, "support: placeholder is --sc-text-secondary, not the browser grey")
    c.ok(text_contrast(page, ".cat-count") >= 4.5, "support: article counts pass AA")
    cards = [page.locator(".category-card").nth(i).bounding_box() for i in range(3)]
    c.near(cards[0]["width"], 400, 1, "support: category card 400 wide (Figma 498:151)")
    c.near(cards[1]["x"] - (cards[0]["x"] + cards[0]["width"]), 24, 1, "support: 24px between cards")
    c.eq(cs(page, ".category-card", ["border-top-left-radius"])["border-top-left-radius"], "18px", "support: card radius 18")
    c.eq(page.locator(".cat-icon svg").count(), 6, "support: six SVG icon tiles")
    band = box(page, ".articles-band")
    c.near(band["w"], 1440, 1, "support: the article list sits in a full-width band")
    c.near(box(page, ".articles-panel")["w"], 880, 1, "support: the grouped panel is 880 wide (Figma 498:195)")
    # keyboard: Tab to the search box draws a 2px primary ring
    page.focus("body")
    for _ in range(40):
        press_tab(page, c)
        if page.evaluate("document.activeElement && document.activeElement.classList.contains('search-input')"):
            break
    o = cs(page, ".search-input", ["outline-style", "outline-width", "outline-color"])
    c.eq((o["outline-style"], o["outline-width"], o["outline-color"]), ("solid", "2px", PRIMARY), "support: keyboard focus on the search draws a 2px brand ring")
    # typing replaces the browse sections with results in the same panel, and announces the count
    page.fill(".search-input", "phone")
    page.wait_for_selector("#results-heading")
    c.eq(page.locator(".categories-grid").count(), 0, "support: results replace the category grid")
    c.ok(page.locator(".articles-panel .article-row").count() >= 1, "support: matching articles are listed as whole-row links")
    c.ok("match" in page.locator("[role=status]").inner_text(), "support: the status region announces the result count")
    # a Start here row is one link: clicking its far-left edge opens the article
    page.fill(".search-input", "")
    page.wait_for_selector(".articles-band .article-row")
    row = page.locator(".article-row").first
    row.scroll_into_view_if_needed()
    b = row.bounding_box()
    page.mouse.click(b["x"] + 6, b["y"] + b["height"] / 2)
    page.wait_for_url(re.compile(r"/support/[a-z-]+/[a-z-]+"))
    c.ok(True, "support: the whole row is the link")


def check_docs(page, c: Checks, base: str) -> None:
    open_page(page, base, "/docs", ".docs-sidebar")
    sb, main = box(page, ".docs-sidebar"), box(page, ".docs-content")
    c.near(sb["w"], 248, 1, "docs: sidebar 248 wide (Figma 499:145)")
    c.near(sb["x"], 96, 1, "docs: sidebar x 96")
    c.near(main["x"] - sb["right"], 40, 1, "docs: 40px between the sidebar and the content (Figma)")
    c.near(main["w"], 960, 2, "docs: content column 960 (Figma 499:172)")
    cur = page.locator(".docs-sidebar .nav-item[aria-current]")
    c.eq(cur.count(), 1, "docs: exactly one sidebar item is current")
    c.eq(cur.first.get_attribute("aria-current"), "location", "docs: it is aria-current=location")
    c.ok("is-active" in (cur.first.get_attribute("class") or ""), "docs: and it is the visibly active one")
    c.eq(cs(page, ".docs-sidebar .nav-item.is-active", ["font-weight", "background-color"])["background-color"], ELEVATED, "docs: active item on the elevated fill (Figma 499:148)")
    page.locator(".docs-sidebar .nav-item").nth(1).click()
    page.wait_for_function("location.hash === '#display-outputs'")
    c.eq(page.locator(".docs-sidebar .nav-item[aria-current]").count(), 1, "docs: after a click there is still exactly one current item")
    c.eq(page.locator(".docs-sidebar .nav-item[aria-current]").first.inner_text().strip(), "Display & Outputs", "docs: and it is the one clicked")
    c.eq(page.locator(".docs-sidebar .nav-item.is-active").count(), 1, "docs: one visibly active item after a click")
    c.ok(text_contrast(page, ".group-label") >= 4.5, "docs: group labels pass AA")
    # Forced colors (Windows High Contrast) deletes box-shadows and replaces fills with the canvas colour but keeps
    # borders: the current item must still be marked there. Chromium applies the emulation; WebKit reports it and
    # does not apply it, so there the check is skipped with a note (as the shared-components script does).
    if c.engine == "chromium":
        page.emulate_media(forced_colors="active")
        page.wait_for_timeout(150)
        cur = cs(page, ".docs-sidebar .nav-item.is-active", ["border-left-width", "border-left-style", "border-left-color", "background-color", "box-shadow"])
        rest = cs(page, ".docs-sidebar .nav-item:not(.is-active)", ["border-left-width"])
        c.eq((cur["border-left-width"], cur["border-left-style"]), ("3px", "solid"), "docs (forced colors): the current item keeps a 3px border")
        c.eq(rest["border-left-width"], "0px", "docs (forced colors): the other items have none")
        c.ok(cur["border-left-color"] != cur["background-color"], f"docs (forced colors): the border differs from the item's own fill ({cur['border-left-color']} against {cur['background-color']})")
        c.eq(cur["box-shadow"], "none", "docs (forced colors): and no shadow is what carries it")
        page.emulate_media(forced_colors="none")
    else:
        print(f"NOTE [{c.engine}]: this engine does not apply forced colors; the forced-colors check on the docs marker is skipped")
    tiles = page.locator(".topic-tile")
    c.eq(tiles.count(), 6, "docs: six topic tiles")
    c.near(tiles.first.bounding_box()["width"], 471, 1.5, "docs: tile 471 wide (Figma 499:186)")
    # a tile whose description fits one line is 83 high. The first row stretches to the first category's two-line
    # description (the content layer's words), so the second row is the one that shows the frame's height.
    c.near(tiles.nth(2).bounding_box()["height"], 83, 1.5, "docs: tile 83 high (Figma 499:186)")
    c.ok((page.locator(".start-button").get_attribute("href") or "").startswith("/docs/"), "docs: Start guide goes to a real article")
    # the hero sits above the split and is centred
    h1 = box(page, ".hero-title")
    c.near(h1["x"] + h1["w"] / 2, 720, 2, "docs: the title is centred on the page")


def check_changelog(page, c: Checks, base: str) -> None:
    open_page(page, base, "/changelog", ".release-card")
    r = box(page, ".release-card")
    c.near(r["w"], 900, 1, "changelog: release card 900 wide (Figma 501:145)")
    c.near(r["x"], 270, 1, "changelog: release card x 270")
    c.eq(cs(page, ".release-card", ["border-top-left-radius"])["border-top-left-radius"], "20px", "changelog: card radius 20")
    labels = page.locator(".change-label")
    c.eq(labels.first.evaluate("e => getComputedStyle(e).textTransform"), "none", "changelog: label pills are sentence case (Figma)")
    c.eq(page.locator(".is-new .change-label").first.evaluate("e => getComputedStyle(e).color"), PREVIEW, "changelog: New is green")
    c.eq(page.locator(".is-improved .change-label").first.evaluate("e => getComputedStyle(e).color"), TEXT, "changelog: Improved takes the accent badge ink (--sc-text until Uma picks one)")
    c.eq(page.locator(".is-fixed .change-label").first.evaluate("e => getComputedStyle(e).color"), WARN, "changelog: Fixed is amber")
    d = cs(page, ".release-date", ["font-size", "color"])
    c.eq((d["font-size"], d["color"]), ("14px", SECONDARY), "changelog: date 14px secondary (Figma 501:150)")
    c.ok(text_contrast(page, ".release-date") >= 4.5, "changelog: the date passes AA")
    c.near(box(page, ".change-label")["h"], 21, 0.6, "changelog: label pill 21 high (Figma 501:154)")
    dot = cs(page, ".change-dot", ["width", "height"])
    c.eq((dot["width"], dot["height"]), ("6px", "6px"), "changelog: 6px dot")


def check_blog(page, c: Checks, base: str) -> None:
    open_page(page, base, "/blog", ".featured-card")
    f = box(page, ".featured-card")
    c.near(f["w"], 1248, 1, "blog: featured card 1248 wide (Figma 502:145)")
    c.near(f["h"], 348, 3, "blog: featured card about 348 high")
    c.eq(cs(page, ".featured-card", ["border-top-left-radius"])["border-top-left-radius"], "22px", "blog: featured radius 22")
    m = box(page, ".featured-media")
    c.near(m["w"], 584, 1, "blog: media panel 584 wide (Figma 502:146)")
    c.near(m["h"], 300, 1, "blog: media panel 300 high")
    cards = [page.locator(".blog-card").nth(i).bounding_box() for i in range(3)]
    c.near(cards[0]["width"], 400, 1, "blog: grid card 400 wide (Figma 502:160)")
    c.near(cards[1]["x"] - (cards[0]["x"] + cards[0]["width"]), 24, 1, "blog: 24px between cards")
    c.eq(cs(page, ".blog-card", ["border-top-left-radius"])["border-top-left-radius"], "18px", "blog: card radius 18")
    c.near(box(page, ".card-media")["h"], 150, 1, "blog: thumbnail panel 150 high (Figma 502:161)")
    c.ok(text_contrast(page, ".card-meta") >= 4.5, "blog: card meta passes AA")
    c.eq(cs(page, ".card-meta", ["font-size"])["font-size"], "12.5px", "blog: card meta 12.5px")
    # the featured card is ONE link, stretched: its title takes focus and the click anywhere on the card goes to the post
    page.focus("body")
    for _ in range(40):
        press_tab(page, c)
        if page.evaluate("document.activeElement && document.activeElement.classList.contains('featured-link')"):
            break
    c.ok(page.evaluate("document.activeElement.classList.contains('featured-link')"), "blog: the featured title is a tab stop")
    ring = page.evaluate("getComputedStyle(document.activeElement, '::after').outlineStyle")
    c.eq(ring, "solid", "blog: keyboard focus draws a ring round the whole card")
    page.locator(".featured-card").scroll_into_view_if_needed()
    b = page.locator(".featured-card").bounding_box()
    page.mouse.click(b["x"] + b["width"] - 20, b["y"] + b["height"] - 20)
    page.wait_for_url(re.compile(r"/blog/why-offline-first"))
    c.ok(True, "blog: clicking the card's empty corner opens the post (one stretched link)")


def check_careers(page, c: Checks, base: str) -> None:
    open_page(page, base, "/careers", ".culture-card")
    h1 = cs(page, ".hero-title", ["font-size", "line-height", "font-weight"])
    c.eq((h1["font-size"], h1["line-height"], h1["font-weight"]), ("50px", "56px", "700"), "careers: h1 50/56/700 (Figma 503:139)")
    c.near(box(page, ".hero-title")["w"], 498, 12, "careers: h1 about 498 wide, two lines")
    cards = [page.locator(".culture-card").nth(i).bounding_box() for i in range(4)]
    c.near(cards[0]["width"], 294, 1, "careers: culture card 294 wide (Figma 503:146)")
    c.near(cards[1]["x"] - (cards[0]["x"] + cards[0]["width"]), 24, 1, "careers: 24px between culture cards")
    tile = cs(page, ".culture-icon", ["width", "height", "border-top-left-radius"])
    c.eq((tile["width"], tile["height"], tile["border-top-left-radius"]), ("50px", "50px", "13px"), "careers: icon tile 50x50 r13 (Figma 503:147)")
    band = box(page, ".roles-band")
    c.near(band["x"], 0, 1, "careers: roles band starts at the left edge")
    c.near(band["w"], 1440, 1, "careers: roles band is full-bleed")
    c.near(box(page, ".roles-list")["w"], 940, 1, "careers: role list 940 wide (Figma 503:175)")
    c.near(box(page, ".roles-list")["x"], 250, 1, "careers: role list x 250")
    tag = cs(page, ".role-tag", ["font-size", "font-weight", "color", "background-color"])
    c.eq((tag["font-size"], tag["font-weight"], tag["color"], tag["background-color"]), ("12px", "500", SECONDARY, ELEVATED), "careers: tag pill 12/500 secondary on elevated (Figma 503:180)")
    c.near(box(page, ".role-tag")["h"], 25, 0.6, "careers: tag pill 25 high")
    c.ok(text_contrast(page, ".role-tag") >= 4.5, "careers: the tags pass AA (careers-05)")
    c.near(page.locator(".role-row").first.bounding_box()["height"], 95, 3, "careers: role row about 95 high (Figma 503:176)")
    names = [page.locator(".role-row a").nth(i).inner_text().replace("\n", " ") for i in range(page.locator(".role-row a").count())]
    c.eq(len(set(names)), 3, f"careers: the three Apply links have different names ({names})")


def check_legal(page, c: Checks, base: str, path: str, label: str) -> None:
    open_page(page, base, path, ".legal-title")
    t = cs(page, ".legal-title", ["font-size", "font-weight", "line-height", "margin-top", "margin-bottom"])
    c.eq((t["font-size"], t["font-weight"], t["line-height"]), ("44px", "700", "50px"), f"{label}: title 44/700/50 (Figma 504:139)")
    c.eq((t["margin-top"], t["margin-bottom"]), ("16px", "16px"), f"{label}: 16px above and below the title")
    nav = page.evaluate("document.querySelector('.navbar-header').getBoundingClientRect().bottom")
    pill = box(page, ".legal-header .ui-badge")
    c.near(pill["y"] - nav, 96, 2, f"{label}: the pill sits 96px under the navbar (Figma 175 - 79)")
    c.eq(cs(page, ".legal-header", ["border-bottom-width"])["border-bottom-width"], "0px", f"{label}: no rule under the header")
    c.eq(page.locator(".legal-header .ui-badge").inner_text().strip(), "LEGAL", f"{label}: the pill reads LEGAL")
    pc = cs(page, ".legal-header .ui-badge", ["background-color", "font-size", "font-weight"])
    c.eq((pc["background-color"], pc["font-size"], pc["font-weight"]), (ELEVATED, "12px", "700"), f"{label}: the page pill, not the green status badge")
    h = cs(page, ".sec-main", ["font-size", "font-weight", "line-height", "color"])
    c.eq((h["font-size"], h["font-weight"], h["line-height"]), ("20px", "600", "26px"), f"{label}: section heading 20/600/26 (Figma)")
    c.eq(cs(page, ".sec-main .sec-num", ["color"])["color"], h["color"], f"{label}: the section number takes the heading ink")
    p = cs(page, ".lb-p", ["font-size", "line-height"])
    c.eq((p["font-size"], p["line-height"]), ("16px", "26px"), f"{label}: body 16/26 (Figma)")
    # Figma draws one 780 column (504:144). The contents sidebar is build-only; the shell is sized so the text beside it is
    # that 780 at 1440, not the 764 a 1120 shell left (review round 1, Cody M13).
    c.near(box(page, ".legal-text")["w"], 780, 1, f"{label}: the text column measures 780 at 1440 (Figma 504:144)")
    c.near(box(page, ".toc-col")["w"], 260, 1, f"{label}: beside a 260 contents column")
    c.ok(page.locator(".toc-link").count() >= 10, f"{label}: the contents sidebar is still there")
    if page.locator(".ll-item").count():
        m = cs(page, ".ll-item", ["padding-left"])
        mk = cs(page, ".ll-item", ["background-color", "left", "width"], pseudo="::before")
        c.eq(mk["background-color"], PRIMARY, f"{label}: list marker is the primary dot (Figma 504:233)")
        c.eq((m["padding-left"], mk["width"]), ("15px", "5px"), f"{label}: marker 5px, text 15px in")


def check_affiliates(page, c: Checks, base: str) -> None:
    open_page(page, base, "/affiliates", ".hero-ctas")
    a, b = page.locator(".hero-ctas > *").nth(0).bounding_box(), page.locator(".hero-ctas > *").nth(1).bounding_box()
    c.near(a["height"], 49, 0.6, "affiliates: Apply now 49 high (Figma 541:145)")
    c.near(b["height"], 49, 0.6, "affiliates: Affiliate sign in 49 high (Figma 541:147), the row stretches the quiet button")
    c.near(b["x"] - (a["x"] + a["width"]), 14, 1, "affiliates: 14px between the hero buttons")
    h1 = cs(page, ".hero-title", ["font-size", "line-height", "font-weight"])
    c.eq((h1["font-size"], h1["line-height"], h1["font-weight"]), ("54px", "60px", "700"), "affiliates: h1 54/60/700 (Figma 541:139)")
    hl = [page.locator(".highlight-card").nth(i).bounding_box() for i in range(4)]
    c.near(hl[0]["width"], 295.5, 1, "affiliates: stat card 295.5 wide (Figma 541:151)")
    c.near(hl[0]["height"], 122, 1.5, "affiliates: stat card 122 high")
    c.near(hl[1]["x"] - (hl[0]["x"] + hl[0]["width"]), 22, 1, "affiliates: 22px between stat cards")
    c.eq(cs(page, ".hl-value", ["font-size", "font-weight"])["font-size"], "34px", "affiliates: stat value 34px")
    steps = page.locator(".step-card")
    c.eq(steps.count(), 3, "affiliates: three step cards")
    c.near(steps.first.bounding_box()["width"], 400, 1, "affiliates: step card 400 wide (Figma 541:168)")
    c.near(box(page, ".steps-section")["w"], 1440, 1, "affiliates: How it works is a full-bleed band")
    c.near(page.locator(".audience-card").first.bounding_box()["width"], 295.5, 1, "affiliates: audience card 295.5 wide (Figma 542:127)")
    tile = cs(page, ".audience-card .cat-icon", ["width", "border-top-left-radius"])
    c.eq((tile["width"], tile["border-top-left-radius"]), ("50px", "14px"), "affiliates: audience tile 50 r14 (Figma 542:128)")
    c.eq(page.locator(".check-row").count(), 2, "affiliates: two checklist rows (the two the repo backs)")
    c.near(box(page, ".calc-card")["w"], 420, 1, "affiliates: the calculator takes the 420px right column (Figma 542:178)")
    c.ok(page.get_by_role("slider", name="Referred Active Churches:").count() == 1, "affiliates: the slider has an accessible name")
    faq = page.locator(".faq-accordion.is-boxed")
    c.eq(faq.count(), 1, "affiliates: the FAQ is the boxed card")
    c.near(faq.bounding_box()["width"], 880, 1, "affiliates: boxed FAQ 880 wide (Figma 542:199)")
    c.ok(page.locator(".faq-question[aria-controls]").count() >= 4, "affiliates: every question controls its answer")
    band = page.locator(".cta-band")
    c.ok("linear-gradient" in band.evaluate("e => getComputedStyle(e).backgroundImage"), "affiliates: the closing band is the gradient card")
    c.near(band.bounding_box()["width"], 1248, 1, "affiliates: closing band 1248 wide (Figma 542:227)")
    c.eq(cs(page, ".cta-band", ["border-top-left-radius"])["border-top-left-radius"], "24px", "affiliates: closing band radius 24")
    btn = cs(page, ".cta-band .ui-button", ["background-color", "color"])
    c.eq(btn["background-color"], "rgb(255, 255, 255)", "affiliates: the band button is white")
    c.near(box(page, ".cta-band .ui-button")["h"], 49, 0.6, "affiliates: band button 49 high")
    link = page.locator(".hero-ctas a").first
    c.eq(link.get_attribute("href"), "/contact", "affiliates: Apply now is the interim link to the contact page")
    # Affiliate sign in has no destination (the only affiliate pages are shells of sample data): a disabled button that says why
    c.eq(page.locator(".hero-ctas button[disabled]").count(), 1, "affiliates: Affiliate sign in is a disabled button")
    c.eq(page.locator(".hero-ctas a").count(), 1, "affiliates: and the hero has just the one link")
    c.ok("not available yet" in page.locator("#signin-note").inner_text().lower(), "affiliates: the reason is visible beside it")
    c.eq(page.get_by_role("button", name="Affiliate sign in").is_disabled(), True, "affiliates: the browser reports it disabled")
    bad = page.locator("main a[href^='/signin'], main a[href^='/affiliates/']").count()
    c.eq(bad, 0, "affiliates: no link on the page goes to the customer sign-in or into the affiliate portal shells")
    c.eq(page.locator(".cta-band button[disabled]").count(), 1, "affiliates: the band's Apply now is disabled")
    c.eq(page.locator(".cta-band a").count(), 0, "affiliates: and the band has no link")
    c.ok("not available yet" in page.locator("#apply-note").inner_text().lower(), "affiliates: with its reason visible")
    c.ok(text_contrast(page, "#signin-note") >= 4.5, "affiliates: the sign-in note passes AA")


def check_no_sideways_scroll(page, c: Checks, base: str) -> None:
    """The nine pages never scroll sideways at the three widths the ticket names."""
    for w in (375, 768, 1440):
        page.set_viewport_size({"width": w, "height": 900})
        for path in ("/contact", "/support", "/docs", "/changelog", "/blog", "/careers", "/privacy", "/terms", "/affiliates"):
            page.goto(base + path, wait_until="load", timeout=45000)
            page.wait_for_selector("main, #app > *")
            over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            c.ok(over <= 0, f"{path} at {w}px scrolls sideways by {over}px")
    page.set_viewport_size({"width": 1440, "height": 900})


GROUPS = {
    "contact": check_contact,
    "support": check_support,
    "docs": check_docs,
    "changelog": check_changelog,
    "blog": check_blog,
    "careers": check_careers,
    "affiliates": check_affiliates,
}


def run_engine(pw, engine: str, base: str, shots: Path | None, only: list[str] | None) -> Checks:
    c = Checks(engine)
    browser = (pw.chromium if engine == "chromium" else pw.webkit).launch()
    try:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e).splitlines()[0][:140]))
        for name, fn in GROUPS.items():
            if only and name not in only:
                continue
            try:
                fn(page, c, base)
            except Exception as exc:  # noqa: BLE001 -- a thrown error is a failed check, reported with its group
                c.ok(False, f"{name}: the group stopped with {type(exc).__name__}: {str(exc).splitlines()[0][:200]}")
            if shots:
                page.screenshot(path=str(shots / f"{engine}-{name}.png"), full_page=True)
        if not only or "legal" in only:
            for path, label in (("/privacy", "privacy"), ("/terms", "terms")):
                try:
                    check_legal(page, c, base, path, label)
                except Exception as exc:  # noqa: BLE001
                    c.ok(False, f"{label}: the group stopped with {type(exc).__name__}: {str(exc).splitlines()[0][:200]}")
        if not only or "scroll" in only:
            try:
                check_no_sideways_scroll(page, c, base)
            except Exception as exc:  # noqa: BLE001
                c.ok(False, f"scroll: the group stopped with {type(exc).__name__}: {str(exc).splitlines()[0][:200]}")
        c.eq(errors, [], "no page error was thrown in any page")
    finally:
        browser.close()
    return c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["chromium", "webkit", "both"], default="both")
    ap.add_argument("--shots", type=Path, help="write a full-page screenshot per group into this directory")
    ap.add_argument("--only", nargs="*", help="run only these groups (mutation proofs and debugging, never for a gate)")
    args = ap.parse_args()

    if not (DIST / "index.html").exists():
        print(f"INFRA: {DIST}/index.html missing; run `npm run build` first")
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if REQUIRE:
            print("FAIL (required): playwright is not installed")
            return 3
        print("SKIPPED (loud): playwright is not installed; nothing was checked")
        return 0
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)

    engines = ["chromium", "webkit"] if args.engine == "both" else [args.engine]
    srv, port = serve()
    base = f"http://127.0.0.1:{port}"
    failed = 0
    try:
        with sync_playwright() as pw:
            for engine in engines:
                try:
                    c = run_engine(pw, engine, base, args.shots, args.only)
                except Exception as exc:  # noqa: BLE001 -- the engine is not installed
                    if REQUIRE:
                        print(f"FAIL (required): {engine} could not run: {exc}")
                        return 3
                    print(f"SKIPPED (loud): {engine} could not run: {exc}")
                    continue
                print(f"[{engine}] {c.count} checks, {len(c.failures)} failed")
                for f in c.failures:
                    print(f"  FAIL {f}")
                failed += len(c.failures)
    finally:
        srv.shutdown()
    print("PASS secondary pages headless" if not failed else f"FAIL secondary pages headless ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
