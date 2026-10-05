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
            # Every number below is a height or width of text in Inter. A fallback face would move them all and fail for the
            # wrong reason (or pass for it), so a page where Inter did not load in every weight is a failure, said plainly.
            loaded = page.evaluate("[400, 500, 600, 700].every((w) => document.fonts.check(`${w} 16px Inter`))")
            if not loaded:
                raise RuntimeError(f"Inter did not load in every weight on {path}: the measurements would describe a fallback font (is the network up?)")
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
    # ClickUp 17tnw2b0x3h: ONE method card, the email address. The Discord and enterprise cards claimed channels that do not exist.
    n = page.locator(".method-card").count()
    c.eq(n, 1, "contact: one method card (the confirmed email address)")
    ys = [page.locator(".method-card").nth(i).bounding_box() for i in range(n)]
    for i, b in enumerate(ys):
        c.near(b["height"], 99, 1.5, f"contact: method card {i} height (Figma 99)")
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
    # The form sends nothing, so Send is disabled and a visible note says so (ClickUp 17tnw2b0x3h).
    c.eq(page.locator(".contact-form button[disabled]").count(), 1, "contact: Send is disabled until a send exists")
    note = page.locator("#send-note")
    c.ok(note.count() == 1 and "not available yet" in note.inner_text().lower(), "contact: a visible note says the form is not available yet")
    c.ok(text_contrast(page, "#send-note") >= 4.5, f"contact: the note passes AA ({text_contrast(page, '#send-note'):.2f}:1)")
    c.eq(page.locator(".contact-form .ui-button").last.get_attribute("aria-describedby"), "send-note", "contact: Send is described by the note")
    # placeholders and the counter take the secondary ink (contact-13)
    ph = cs(page, ".contact-form input", ["color"], pseudo="::placeholder")["color"]
    c.eq(ph, SECONDARY, "contact: placeholder ink is --sc-text-secondary")
    inp_bg = page.evaluate(BACKDROP_JS, ".contact-form input")
    c.ok(ratio(page, ph, inp_bg) >= 4.5, f"contact: placeholder passes AA ({ratio(page, ph, inp_bg):.2f}:1)")
    c.ok(text_contrast(page, ".char-count") >= 4.5, f"contact: counter passes AA ({text_contrast(page, '.char-count'):.2f}:1)")
    # Tab order: the four fields, then PAST the disabled Send to the one email link
    order = focus_order(page, c, ".contact-form input >> nth=0", 4)
    c.eq(
        order[:4],
        ["Full name", "Email", "Church / organization", "How can we help?"],
        "contact: Tab visits the form fields first",
    )
    c.ok(order[4] and "@" in order[4], f"contact: then skips the disabled Send to the email link ({order[4]!r})")
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


def settle_scroll(page) -> None:
    """The site scrolls smoothly, so a Tab that moves the page is still moving it when the call returns: wait until it stops."""
    last = None
    for _ in range(50):
        y = page.evaluate("scrollY")
        if y == last:
            return
        last = y
        page.wait_for_timeout(120)


def press_with_mouse(page, locator, edge: str) -> None:
    """Press and release the REAL mouse on a button, `edge` ('top' or 'bottom') 8px inside it.

    The button's position is read when the mouse arrives, as a person's eye does. The point is 8px inside the edge the
    button moves AWAY from when an error line appears (top) or disappears (bottom), so a shift of an error line (23 to
    27px) always carries the button out from under the pointer: a click that reaches the button is the fix working, not luck.
    """
    locator.scroll_into_view_if_needed()
    b = locator.bounding_box()
    x = b["x"] + b["width"] / 2
    y = b["y"] + 8 if edge == "top" else b["y"] + b["height"] - 8
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.up()


def check_contact_behaviour(page, c: Checks, base: str) -> None:
    """What the form DOES under a real mouse and keyboard (review round 2: Quinn Q2, Vera 1; ClickUp 17tnw2b0x3h)."""
    # Nothing is sent, so there is no success state to reach and no first-press submit to protect (the old Quinn Q1 checks).
    # What must hold instead: a press on the disabled Send does nothing, and no "received" or reply promise ever appears.
    open_page(page, base, "/contact", ".contact-form-card")
    page.fill(".contact-form input >> nth=0", "Ana")
    page.fill(".contact-form input >> nth=1", "jane@yourchurch.org")
    page.fill(".contact-form textarea", "Hello there")
    send = page.locator(".contact-form button").last
    c.eq(send.is_disabled(), True, "contact: the browser reports Send disabled")
    send.click(force=True)
    page.wait_for_timeout(1200)
    body = page.inner_text("main")
    c.ok("Message Received" not in body and "respond within" not in body.lower(), "contact: pressing the disabled Send shows no success card and no reply promise (the old timer is gone)")
    c.eq(page.locator(".success-state").count(), 0, "contact: and no success state exists")

    # Vera 1: the email check runs on blur, so a long value must not freeze the page. 2,000 characters of `a@` took about
    # 0.75s in the unguarded pattern; the cap makes it a few milliseconds.
    open_page(page, base, "/contact", ".contact-form-card")
    got = page.evaluate(
        """async () => { const el = document.querySelector('.contact-form input[type="email"]'); el.focus();
          el.value = 'a@'.repeat(1000); el.dispatchEvent(new Event('input', { bubbles: true }));
          const t0 = performance.now(); el.blur(); const ms = performance.now() - t0;
          await new Promise((r) => setTimeout(r, 60)); return { ms, text: document.querySelector('.contact-form').innerText }; }"""
    )
    c.ok(got["ms"] < 100, f"contact: leaving an email field holding 2,000 characters of a@ costs {got['ms']:.1f}ms (the unguarded pattern took ~750ms; limit 100)")
    c.ok("Please enter a valid email address" in got["text"], "contact: and that value is refused with the email message")

    # Q2: Tab from the last field jumps (past the disabled Send) DOWN-RIGHT to the email link; on a short window it must not stop
    # under the sticky navbar.
    size = page.viewport_size
    for height in (700, 800):
        page.set_viewport_size({"width": size["width"], "height": height})
        open_page(page, base, "/contact", ".contact-form-card")
        # The fault needs a link that is INSIDE the window but under the navbar (the browser scrolls only when a focus target is
        # outside the window, and it does not know the sticky navbar covers the top 79px). Built directly so it does not depend on
        # how this engine scrolls the walk: the last field is visible, the link is 40px from the top.
        page.evaluate(
            """() => { const l = document.querySelector('.method-link'); window.scrollTo({ top: l.getBoundingClientRect().top + scrollY - 40, behavior: 'instant' }); }"""
        )
        settle_scroll(page)
        page.locator(".contact-form textarea").focus()
        c.eq(page.evaluate(FOCUS_JS), "How can we help?", f"contact: at {height} high the last field holds focus")
        settle_scroll(page)
        press_tab(page, c)
        settle_scroll(page)
        got = page.evaluate(
            """() => { const a = document.activeElement, r = a.getBoundingClientRect();
              return { cls: a.className, top: r.top, bottom: r.bottom, nav: document.querySelector('header').getBoundingClientRect().bottom, vh: innerHeight }; }"""
        )
        c.ok("method-link" in got["cls"], f"contact: at {height} high, Tab from the last field reaches the email link past the disabled Send ({got['cls']!r})")
        c.ok(got["top"] >= got["nav"] - 1, f"contact: at {height} high the focused link is not under the sticky navbar (top {got['top']:.0f}, navbar ends {got['nav']:.0f}; WCAG 2.2 SC 2.4.11)")
        c.ok(got["bottom"] <= got["vh"], f"contact: and it is inside the window (bottom {got['bottom']:.0f} of {got['vh']})")
    page.set_viewport_size(size)


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
    """ClickUp 17tnw2b0x3h: nothing has shipped, so the page shows an empty state in the release card's frame (the invented
    releases are gone). The label, date and dot styling is covered with fixture releases by `tests/secondaryPages.test.ts`."""
    open_page(page, base, "/changelog", ".release-empty")
    r = box(page, ".release-empty")
    c.near(r["w"], 900, 1, "changelog: the empty state is as wide as a release card, 900 (Figma 501:145)")
    c.near(r["x"], 270, 1, "changelog: and sits at x 270")
    c.eq(cs(page, ".release-empty", ["border-top-left-radius"])["border-top-left-radius"], "20px", "changelog: radius 20")
    c.eq(page.locator(".release-card").count(), 0, "changelog: no release card is drawn")
    c.ok("no release notes yet" in page.locator(".empty-title").inner_text().lower(), "changelog: it says there are no release notes yet")
    c.ok(text_contrast(page, ".empty-text") >= 4.5, "changelog: the empty text passes AA")


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
    """ClickUp 17tnw2b0x3h: no role is open and the culture strip's company claims are gone, so the page is the hero and the roles
    band's empty line. The role rows and tags are covered with fixture roles by `tests/secondaryPages.test.ts`."""
    open_page(page, base, "/careers", ".roles-empty")
    h1 = cs(page, ".hero-title", ["font-size", "line-height", "font-weight"])
    c.eq((h1["font-size"], h1["line-height"], h1["font-weight"]), ("50px", "56px", "700"), "careers: h1 50/56/700 (Figma 503:139)")
    c.near(box(page, ".hero-title")["w"], 498, 12, "careers: h1 about 498 wide, two lines")
    c.eq(page.locator(".culture-card").count(), 0, "careers: no culture card")
    band = box(page, ".roles-band")
    c.near(band["x"], 0, 1, "careers: roles band starts at the left edge")
    c.near(band["w"], 1440, 1, "careers: roles band is full-bleed")
    c.eq(page.locator(".role-row").count(), 0, "careers: no role row")
    c.ok("no open roles" in page.locator(".roles-empty").inner_text().lower(), "careers: the band says there are no open roles")
    c.eq(page.locator("main a").count(), 0, "careers: and invites no application (no link on the page)")
    c.ok(text_contrast(page, ".roles-empty") >= 4.5, "careers: the empty line passes AA")


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
    """ClickUp 17tnw2b0x3h: no rate, window, threshold, payout rail, calculator, FAQ or apply flow (the programme is NOT-V1 and no
    application exists), so the page is the hero, two steps, the audiences and the checklist."""
    open_page(page, base, "/affiliates", ".hero-ctas")
    a = page.locator(".hero-ctas > *").nth(0).bounding_box()
    c.eq(page.locator(".hero-ctas > *").count(), 1, "affiliates: the hero has one button, Affiliate sign in (no Apply)")
    # Figma draws it at 49 beside the Apply button; with Apply gone the row no longer stretches it, so it is the outline button's own 47.
    c.near(a["height"], 47, 0.6, "affiliates: Affiliate sign in 47 high, its own size now that the Apply button it was stretched to match is gone")
    h1 = cs(page, ".hero-title", ["font-size", "line-height", "font-weight"])
    c.eq((h1["font-size"], h1["line-height"], h1["font-weight"]), ("54px", "60px", "700"), "affiliates: h1 54/60/700 (Figma 541:139)")
    c.eq(page.locator(".highlight-card").count(), 0, "affiliates: no stat cards")
    steps = page.locator(".step-card")
    c.eq(steps.count(), 2, "affiliates: two step cards (no apply step)")
    c.near(steps.nth(1).bounding_box()["x"] - (steps.nth(0).bounding_box()["x"] + steps.nth(0).bounding_box()["width"]), 24, 1, "affiliates: 24px between step cards")
    c.near(box(page, ".steps-section")["w"], 1440, 1, "affiliates: How it works is a full-bleed band")
    c.near(page.locator(".audience-card").first.bounding_box()["width"], 295.5, 1, "affiliates: audience card 295.5 wide (Figma 542:127)")
    tile = cs(page, ".audience-card .cat-icon", ["width", "border-top-left-radius"])
    c.eq((tile["width"], tile["border-top-left-radius"]), ("50px", "14px"), "affiliates: audience tile 50 r14 (Figma 542:128)")
    c.eq(page.locator(".check-row").count(), 2, "affiliates: two checklist rows (the two the repo backs)")
    c.eq(page.locator(".calc-card, input[type=range]").count(), 0, "affiliates: no earnings calculator")
    c.eq(page.locator(".faq-accordion, .faq-section").count(), 0, "affiliates: no FAQ")
    c.eq(page.locator(".cta-band, .cta-section").count(), 0, "affiliates: no closing Apply band")
    # Affiliate sign in has no destination (the only affiliate pages are shells of sample data): a disabled button that says why
    c.eq(page.locator(".hero-ctas button[disabled]").count(), 1, "affiliates: Affiliate sign in is a disabled button")
    c.eq(page.locator(".hero-ctas a").count(), 0, "affiliates: and the hero has no link at all")
    c.ok("not available yet" in page.locator("#signin-note").inner_text().lower(), "affiliates: the reason is visible beside it")
    c.eq(page.get_by_role("button", name="Affiliate sign in").is_disabled(), True, "affiliates: the browser reports it disabled")
    c.ok("not open yet" in page.locator(".hero-sub").inner_text().lower(), "affiliates: the hero says the programme is not open yet")
    bad = page.locator("main a[href^='/signin'], main a[href^='/affiliates/']").count()
    c.eq(bad, 0, "affiliates: no link on the page goes to the customer sign-in or into the affiliate portal shells")
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
    "contact-behaviour": check_contact_behaviour,
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
        srv.server_close()
    print("PASS secondary pages headless" if not failed else f"FAIL secondary pages headless ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
