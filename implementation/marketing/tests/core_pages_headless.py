#!/usr/bin/env python3
"""Real-browser checks for the four core pages (ClickUp 17tnw2b2cey): Pricing, Features, Download, About.

`tests/corePages.test.ts` reads the source and server-renders the pages. This drives the REAL production
bundle (`dist/`) in a real browser, because what the node test cannot see is what the Figma audit found
wrong: where a box lands and how big it is, whether the arrow keys move the billing toggle and its focus,
whether a disabled button can be tabbed to, whether text on the gradient band holds its contrast, and
whether the page scrolls sideways. Every size below is a Figma value from
`docs/design/visual-parity/marketing/figma-style/*.json`, quoted next to its check, with a tolerance that
says what it is (1.5px for rounding, a wider one where wording legitimately changes a height).

Usage (from implementation/marketing):
    npm run build
    python3 tests/core_pages_headless.py [--engine chromium|webkit|both] [--shots DIR]

Not wired into `npm test` or CI on purpose (it needs a browser and a build; wiring is the CI ticket
17tnw2b2fum, as for `scripts/shared_components_headless.py`). Run it by hand, as the contract records.

Needs Playwright and an engine, and the network for Inter (without it the text wraps differently and a few
height checks may move; those are marked). If Playwright is missing this exits 0 with a LOUD skip unless
SELAHCUE_HEADLESS_REQUIRE=1, which makes it a hard failure so a gate can never silently no-op.

Exit codes: 0 pass (or loud skip), 1 a check failed, 2 infrastructure problem, 3 a required engine is
unavailable.
"""

from __future__ import annotations

import argparse
import http.server
import json
import math
import os
import re
import socketserver
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETING = HERE.parent
DIST = Path(os.environ.get("SELAHCUE_MARKETING_DIST") or (MARKETING / "dist"))
REQUIRE = os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1"

WIDTHS = [320, 375, 768, 1024, 1440]
ROUTES = ["/pricing", "/features", "/download", "/about"]


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):  # noqa: D401
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


class SpaHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dist/ with the SPA fallback to index.html for client-routed paths."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802
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


FAILURES: list[str] = []
CHECKS = 0
# WebKit on macOS does not Tab to links and buttons unless Option is held (Safari's own setting); Chromium does.
TAB = "Tab"


def check(name: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL {name}: {detail}")


def near(name: str, got: float, want: float, tol: float = 1.5) -> None:
    check(name, abs(got - want) <= tol, f"got {got:.1f}, Figma draws {want} (tolerance {tol})")


def rect(page, selector: str, index: int = 0):
    """Box of the index-th match, in page coordinates, or None."""
    return page.evaluate(
        """([sel, i]) => {
          const el = document.querySelectorAll(sel)[i];
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height};
        }""",
        [selector, index],
    )


def rects(page, selector: str):
    return page.evaluate(
        """(sel) => [...document.querySelectorAll(sel)].map((el) => {
          const r = el.getBoundingClientRect();
          return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height};
        })""",
        selector,
    )


def go(page, base: str, path: str, width: int = 1440, height: int = 1000) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{base}{path}", wait_until="load")
    page.wait_for_selector("h1")
    # Inter and the page's own transitions settle before anything is measured.
    page.evaluate("document.fonts.ready.then(() => true)")
    page.wait_for_timeout(250)


def luminance(rgb) -> float:
    def f(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def parse_rgb(s: str):
    m = re.findall(r"[\d.]+", s)
    return tuple(float(x) for x in m[:3])


def gradient_colour_at(box, stops, point):
    """The colour of a CSS `linear-gradient(135deg, a, b)` at a page point inside `box`."""
    theta = math.radians(135)
    sx, sy = math.sin(theta), -math.cos(theta)
    length = abs(box["w"] * math.sin(theta)) + abs(box["h"] * math.cos(theta))
    cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
    t = 0.5 + ((point[0] - cx) * sx + (point[1] - cy) * sy) / length
    t = max(0.0, min(1.0, t))
    a, b = stops
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


# ---------------------------------------------------------------------------------------------- pages


def headings_ok(page, name: str) -> None:
    levels = page.evaluate("[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map((h) => +h.tagName[1])")
    check(f"{name}: one h1", levels.count(1) == 1, str(levels))
    check(f"{name}: first heading is the h1", levels[:1] == [1], str(levels))
    jumps = [(a, b) for a, b in zip(levels, levels[1:]) if b > a + 1]
    check(f"{name}: the outline never skips a level (pricing-bug-01, download-bug-01)", not jumps, f"{jumps} in {levels}")


def hero_lead_ok(page, name: str, figma_height: float) -> None:
    """The subline's height is its line count: copy that runs a line long moves every section below it."""
    lead = rect(page, ".hero-lead")
    check(f"{name}: the hero has a subline", lead is not None, "")
    if lead:
        near(f"{name}: the hero subline is {figma_height:g} tall, as many lines as Figma draws", lead["h"], figma_height, 1)


def check_pricing(page, base: str, engine: str) -> None:
    print(f"[{engine}] pricing")
    go(page, base, "/pricing")
    headings_ok(page, "pricing")
    hero_lead_ok(page, "pricing", 54)  # Figma 483:139

    # Figma 483:149: three 400px cards 24 apart from x=96; Pro (2px border) is taller, tops aligned.
    cards = rects(page, ".pricing-card")
    check("pricing: three plan cards", len(cards) == 3, str(len(cards)))
    if len(cards) == 3:
        for i, (c, x) in enumerate(zip(cards, (96, 520, 944))):
            near(f"pricing: card {i + 1} is 400 wide", c["w"], 400)
            near(f"pricing: card {i + 1} starts at x={x}", c["x"], x)
        check("pricing: card tops are equal", len({round(c['y']) for c in cards}) == 1, str([c["y"] for c in cards]))
        check("pricing: Pro is taller than Free (top-aligned grid, as drawn)", cards[1]["h"] > cards[0]["h"], str([c["h"] for c in cards]))

    text = page.inner_text("main") if page.query_selector("main") else page.inner_text("body")
    check("pricing: no price figure is shown", "$" not in text, "a dollar sign is on the page")

    # Plan buttons: Free to /download, Platinum to /contact, Pro disabled and out of the tab order.
    buttons = page.evaluate(
        """() => [...document.querySelectorAll('.pricing-card .ui-button')].map((b) => ({
          tag: b.tagName.toLowerCase(), href: b.getAttribute('href'), disabled: b.disabled === true,
          text: b.innerText.trim(), height: b.getBoundingClientRect().height, width: b.getBoundingClientRect().width}))"""
    )
    check("pricing: Free goes to /download", buttons[0]["href"] == "/download", str(buttons[0]))
    check("pricing: Pro is a disabled button", buttons[1]["tag"] == "button" and buttons[1]["disabled"], str(buttons[1]))
    # /contact shows "Message Received" without sending anything (contact-04, -06, -07, 17tnw2b0x3h), so Platinum
    # has no destination until that form sends: a disabled button, like Pro (review round 1, Cody B1).
    check("pricing: Platinum is a disabled button (the contact form does not send)", buttons[2]["tag"] == "button" and buttons[2]["disabled"], str(buttons[2]))
    check("pricing: no plan button links to /contact", all(b["href"] != "/contact" for b in buttons), str(buttons))
    near("pricing: plan button is 340 wide (Figma 483:157)", buttons[0]["width"], 340)

    # The billing toggle: a named radio group, one tab stop, arrows move choice AND focus.
    group = page.query_selector("[role=radiogroup]")
    check("pricing: the billing toggle is a radio group with a name", bool(group and group.get_attribute("aria-label")), "")
    pill = rect(page, "[role=radiogroup]")
    if pill:
        near("pricing: the pill is 42 tall (Figma 483:143)", pill["h"], 42)
        near("pricing: the pill sits at y=399", pill["y"], 399, 2)
    seg = rects(page, "[role=radio]")
    if seg:
        near("pricing: a segment is 34 tall (Figma 483:145)", seg[0]["h"], 34)

    def state():
        return page.evaluate(
            """() => ({checked: [...document.querySelectorAll('[role=radio]')].map((r) => r.getAttribute('aria-checked')),
                      tab: [...document.querySelectorAll('[role=radio]')].map((r) => r.tabIndex),
                      active: document.activeElement && document.activeElement.textContent.trim(),
                      note: (document.querySelector('.billing-note') || {}).textContent || ''})"""
        )

    # The live note is in the accessibility tree from the first render, only invisible (a region that is
    # display:none until its text arrives is often not announced: Cody N6).
    note = page.evaluate(
        """() => { const n = document.querySelector('.billing-note'); const cs = getComputedStyle(n);
                    return {role: n.getAttribute('role'), live: n.getAttribute('aria-live'), display: cs.display, visibility: cs.visibility, text: n.textContent}; }"""
    )
    check("pricing: the empty billing note is rendered (not display: none) and is a polite status region", note["role"] == "status" and note["live"] == "polite" and note["display"] != "none" and note["visibility"] == "visible" and note["text"] == "", str(note))
    s = state()
    check("pricing: Monthly is the drawn state", s["checked"] == ["true", "false"], str(s))
    check("pricing: only the checked radio is in the tab order", s["tab"] == [0, -1], str(s))
    # A chord is the browser's, not the toggle's (Quinn N1): Alt+Left and Alt+Right are Back and Forward, Cmd+Left and
    # Cmd+Right the same on a Mac, Ctrl+Home and Ctrl+End jump to the page's ends, Shift+arrow extends a selection.
    # Each must reach the browser: not default-prevented, and the choice unchanged.
    page.focus("[role=radio][aria-checked=true]")
    chords = page.evaluate(
        """() => {
          const out = [];
          const el = document.querySelector('[role=radio][aria-checked=true]');
          const checked = () => [...document.querySelectorAll('[role=radio]')].map((r) => r.getAttribute('aria-checked')).join();
          for (const [key, mod] of [['ArrowRight', 'altKey'], ['ArrowLeft', 'altKey'], ['ArrowRight', 'metaKey'], ['ArrowLeft', 'metaKey'],
                                    ['Home', 'ctrlKey'], ['End', 'ctrlKey'], ['ArrowRight', 'shiftKey'], ['ArrowLeft', 'shiftKey']]) {
            const ev = new KeyboardEvent('keydown', {key, bubbles: true, cancelable: true, [mod]: true});
            el.dispatchEvent(ev);
            out.push({chord: mod + '+' + key, prevented: ev.defaultPrevented, checked: checked()});
          }
          return out;
        }"""
    )
    for c in chords:
        check(f"pricing: {c['chord']} is left to the browser (not prevented, choice unchanged)", (not c["prevented"]) and c["checked"] == "true,false", str(c))
    page.focus("[role=radio][aria-checked=true]")
    page.keyboard.press("ArrowRight")
    ring = page.evaluate("(() => { const cs = getComputedStyle(document.activeElement); return [cs.outlineStyle, cs.outlineWidth]; })()")
    check("pricing: the focused radio shows a 2px ring after a key press (keyboard focus is visible)", ring == ["solid", "2px"], str(ring))
    s = state()
    check("pricing: ArrowRight chooses Annual and moves focus to it", s["checked"] == ["false", "true"] and s["active"] == "Annual", str(s))
    check("pricing: choosing Annual says it is not available, and shows no price", "not available yet" in s["note"].lower(), str(s))
    page.keyboard.press("ArrowRight")
    s = state()
    check("pricing: ArrowRight wraps to Monthly", s["checked"] == ["true", "false"] and s["active"] == "Monthly", str(s))
    page.keyboard.press("End")
    check("pricing: End goes to the last option", state()["checked"] == ["false", "true"], str(state()))
    page.keyboard.press("Home")
    check("pricing: Home goes to the first option", state()["checked"] == ["true", "false"], str(state()))
    page.keyboard.press("ArrowLeft")
    check("pricing: ArrowLeft wraps to the last option", state()["checked"] == ["false", "true"], str(state()))
    after = page.evaluate("document.body.innerText")
    check("pricing: choosing Annual still shows no price", "$" not in after, "")
    page.keyboard.press("Home")

    # Tab order: the toggle is ONE stop, and the disabled Pro button is skipped.
    page.focus("[role=radio][aria-checked=true]")
    stops = []
    for _ in range(4):
        page.keyboard.press(TAB)
        stops.append(page.evaluate("(document.activeElement.getAttribute('aria-label') || document.activeElement.innerText || '').trim().slice(0, 40)"))
    check("pricing: Tab goes to Free, then skips Pro and Platinum (both disabled) to the table", stops[0] == "Download free" and "Plan comparison" in stops[1] and "Talk to us" not in stops and "Get Pro" not in stops, str(stops))

    # The comparison card: 1040 wide at x=200, 45px header band, 48px rows (Figma 484:126/127/135).
    card = rect(page, ".comparison-card")
    if card:
        near("pricing: the comparison card is 1040 wide", card["w"], 1040)
        near("pricing: the comparison card starts at x=200", card["x"], 200)
    head = rect(page, ".comparison-table thead tr")
    if head:
        near("pricing: the header band is 45 tall", head["h"], 45)
    body_rows = rects(page, ".comparison-table tbody tr")
    check("pricing: the table has body rows", len(body_rows) >= 6, str(len(body_rows)))
    for i, r in enumerate(body_rows):
        near(f"pricing: table row {i + 1} is 48 tall", r["h"], 48)
    ths = rects(page, ".comparison-table thead th")
    if len(ths) == 4:
        near("pricing: the Free column is 150 wide (Figma 484:129)", ths[1]["w"], 150)
    ticks = page.evaluate(
        """() => [...document.querySelectorAll('.comparison-table td svg.yes')].map((s) => getComputedStyle(s).color)"""
    )
    check("pricing: a tick is drawn in the success green, not the inherited white", bool(ticks) and all(c == "rgb(53, 192, 138)" for c in ticks), str(set(ticks)))


def check_features(page, base: str, engine: str) -> None:
    print(f"[{engine}] features")
    go(page, base, "/features")
    headings_ok(page, "features")
    hero_lead_ok(page, "features", 90)  # Figma 485:139
    rows = rects(page, ".feature-row")
    check("features: six rows", len(rows) == 6, str(len(rows)))
    for i, r in enumerate(rows):
        # Figma 486:124: 336px (40 / 256 / 40). The paragraph is never taller than the panel, so wording cannot move it.
        near(f"features: row {i + 1} is 336 tall", r["h"], 336, 3)
    panels = rects(page, ".feature-panel")
    for i, p in enumerate(panels):
        near(f"features: panel {i + 1} is 548 wide", p["w"], 548)
        near(f"features: panel {i + 1} is 256 tall", p["h"], 256)
        near(f"features: panel {i + 1} is at x={796 if i % 2 == 0 else 96}", p["x"], 796 if i % 2 == 0 else 96)
    copy = rects(page, ".row-copy")
    for i, c in enumerate(copy):
        near(f"features: text column {i + 1} is 644 wide", c["w"], 644)
    tiles = rects(page, ".panel-tile")
    for i, t in enumerate(tiles):
        near(f"features: icon tile {i + 1} is 60x60", t["w"], 60)
    hidden = page.evaluate("[...document.querySelectorAll('.feature-panel')].every((p) => p.getAttribute('aria-hidden') === 'true')")
    check("features: the skeleton panels are hidden from assistive technology", hidden, "")
    band = rect(page, ".cta-band")
    if band:
        near("features: the closing band is 1248 wide", band["w"], 1248)
        near("features: the closing band is 337 tall", band["h"], 337, 3)
    btns = rects(page, ".cta-band .ui-button")
    if len(btns) == 2:
        near("features: Download free is 49 tall (Figma 486:350)", btns[0]["h"], 49, 0.6)
        near("features: See pricing is 47 tall, not stretched to 49 (Figma 486:352)", btns[1]["h"], 47, 0.6)
    check_band_contrast(page, "features")


def check_band_contrast(page, name: str) -> None:
    """Text on the gradient band: the harness reports a gradient backdrop as `unknown`, so it is computed here."""
    info = page.evaluate(
        """() => {
          const band = document.querySelector('.cta-band');
          if (!band) return null;
          const box = (el) => { const r = el.getBoundingClientRect(); return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height}; };
          const texts = [...band.querySelectorAll('h2, p')].map((el) => ({box: box(el), colour: getComputedStyle(el).color,
            size: parseFloat(getComputedStyle(el).fontSize), weight: +getComputedStyle(el).fontWeight, name: el.tagName}));
          return {box: box(band), image: getComputedStyle(band).backgroundImage, texts};
        }"""
    )
    if not info:
        check(f"{name}: the closing band exists", False, "")
        return
    stops = [parse_rgb(s) for s in re.findall(r"rgb\([^)]*\)", info["image"])][:2]
    check(f"{name}: the band's gradient has two stops to read", len(stops) == 2, info["image"])
    if len(stops) != 2:
        return
    for t in info["texts"]:
        b = t["box"]
        corners = [(b["x"], b["y"]), (b["x"] + b["w"], b["y"]), (b["x"], b["y"] + b["h"]), (b["x"] + b["w"], b["y"] + b["h"])]
        worst = min(contrast(parse_rgb(t["colour"]), gradient_colour_at(info["box"], stops, p)) for p in corners)
        large = t["size"] >= 24 or (t["size"] >= 18.66 and t["weight"] >= 700)
        need = 3.0 if large else 4.5
        check(f"{name}: {t['name']} on the band holds {need}:1 at its worst corner", worst >= need, f"{worst:.2f}:1 at {t['size']}px")


def check_download(page, base: str, engine: str) -> None:
    print(f"[{engine}] download")
    go(page, base, "/download")
    headings_ok(page, "download")
    hero_lead_ok(page, "download", 60)  # Figma 487:139
    cards = rects(page, ".platform-card")
    check("download: two platform cards", len(cards) == 2, str(len(cards)))
    for i, c in enumerate(cards):
        near(f"download: card {i + 1} is 610 wide (Figma 487:147)", c["w"], 610)
        near(f"download: card {i + 1} is 316 tall", c["h"], 316, 2)
    acts = page.evaluate(
        """() => [...document.querySelectorAll('.platform-action')].map((b) => {
          const r = b.getBoundingClientRect(); const cs = getComputedStyle(b);
          return {w: r.width, h: r.height, radius: cs.borderTopLeftRadius, disabled: b.disabled, aria: b.getAttribute('aria-disabled'),
                  text: b.innerText.trim()};
        })"""
    )
    for a in acts:
        near(f"download: '{a['text']}' is 546 wide (Figma 487:156)", a["w"], 546, 2)
        near(f"download: '{a['text']}' is 47 tall", a["h"], 47, 0.6)
        check(f"download: '{a['text']}' has a 12px radius", a["radius"] == "12px", a["radius"])
        check(f"download: '{a['text']}' is still disabled (PR 134)", a["disabled"] and a["aria"] == "true", str(a))
    page.focus("body")
    stops = []
    for _ in range(16):
        page.keyboard.press(TAB)
        stops.append(page.evaluate("(document.activeElement.innerText || '').trim().slice(0, 30)"))
    check("download: Tab never lands on a disabled download or store button", not any(("Download for" in s or "Coming soon" in s) for s in stops), str(stops))
    req = rects(page, ".req-card")
    check("download: two requirement cards", len(req) == 2, str(len(req)))
    for i, c in enumerate(req):
        near(f"download: requirement card {i + 1} is 610 wide (Figma 488:127)", c["w"], 610)
        near(f"download: requirement card {i + 1} is 349 tall", c["h"], 349, 2)
    rows = rects(page, ".req-row")
    for i, r in enumerate(rows):
        near(f"download: requirement row {i + 1} is 38 tall", r["h"], 38, 1)
    fill = page.evaluate("getComputedStyle(document.querySelector('.requirements-section')).backgroundColor")
    check("download: the requirements band has a fill (the token is defined)", fill == "rgb(20, 22, 29)", fill)
    mock = rect(page, ".controller-mock")
    if mock:
        near("download: the controller mock is 280 wide (Figma 489:154)", mock["w"], 280)
        near("download: the controller mock is 305 tall", mock["h"], 305, 2)
    check("download: no placeholder phone", page.query_selector(".phone-mockup") is None, "")
    steps = rects(page, ".step-card")
    for i, c in enumerate(steps):
        near(f"download: step {i + 1} is 400 wide (Figma 489:177)", c["w"], 400)
        near(f"download: step {i + 1} is 197 tall", c["h"], 197, 2)
    heading_levels = page.evaluate("[...document.querySelectorAll('.step-card h3')].length")
    check("download: the three step titles are h3", heading_levels == 3, str(heading_levels))


def check_about(page, base: str, engine: str) -> None:
    print(f"[{engine}] about")
    go(page, base, "/about")
    headings_ok(page, "about")
    hero_lead_ok(page, "about", 90)  # Figma 496:139
    story = rects(page, ".story-layout > *")
    if len(story) == 2:
        near("about: the story's heading column starts at x=96", story[0]["x"], 96)
        near("about: the story's text column starts at x=748 (Figma 496:147)", story[1]["x"], 748, 2)
        near("about: the story's text column is 596 wide", story[1]["w"], 596, 2)
    band = rect(page, ".values-band")
    if band:
        near("about: the values band is full width", band["w"], 1440)
    cards = rects(page, ".value-card")
    check("about: four value cards in one row", len(cards) == 4 and len({round(c["y"]) for c in cards}) == 1, str([c["y"] for c in cards]))
    for i, c in enumerate(cards):
        near(f"about: value card {i + 1} is 294 wide (Figma 496:154)", c["w"], 294)
        near(f"about: value card {i + 1} is 222 tall", c["h"], 222, 2)
    cta = rect(page, ".cta-band")
    if cta:
        near("about: the closing band is 1248 wide", cta["w"], 1248)
    check_band_contrast(page, "about")


def check_no_sideways_scroll(page, base: str, engine: str) -> None:
    print(f"[{engine}] no horizontal scroll")
    for route in ROUTES:
        for width in WIDTHS:
            go(page, base, route, width=width)
            over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check(f"{route} at {width}: no horizontal page scroll", over <= 0, f"{over}px wider than the window")
    # Pro first below 1200 (design 8d), three across above it: the responsive sweep reads the same.
    go(page, base, "/pricing", width=768)
    first_popular = page.evaluate("[...document.querySelectorAll('.pricing-card')].sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0].classList.contains('popular')")
    check("pricing at 768: the popular plan leads", first_popular, "")
    go(page, base, "/pricing", width=375)
    scroller = page.evaluate("(() => { const s = document.querySelector('.table-scroll'); return {sw: s.scrollWidth, cw: s.clientWidth}; })()")
    check("pricing at 375: the table scrolls inside its own card, never the page", scroller["sw"] >= scroller["cw"], str(scroller))


def main() -> int:
    global TAB
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", choices=["chromium", "webkit", "both"], default="both")
    ap.add_argument("--shots", help="write a full-page screenshot of every page and engine here")
    ap.add_argument("--require", action="store_true", help="a missing Playwright or engine is a failure, not a skip (npm run test:core)")
    args = ap.parse_args()
    global REQUIRE
    if args.require:
        REQUIRE = True

    if not (DIST / "index.html").is_file():
        print(f"FAIL: {DIST} has no build. Run `npm run build` first.")
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if REQUIRE:
            print("FAIL: SELAHCUE_HEADLESS_REQUIRE=1 but Playwright is not importable by this python")
            return 3
        print("=" * 68)
        print("!! CORE PAGES CHECK SKIPPED -- Playwright is not importable by this python")
        print("!! (set SELAHCUE_HEADLESS_REQUIRE=1 to make this a failure)")
        print("=" * 68)
        return 0

    server = Server(("127.0.0.1", 0), SpaHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    engines = ["chromium", "webkit"] if args.engine == "both" else [args.engine]

    try:
        with sync_playwright() as pw:
            for engine in engines:
                TAB = "Alt+Tab" if engine == "webkit" else "Tab"
                try:
                    browser = getattr(pw, engine).launch()
                except Exception as exc:  # noqa: BLE001
                    if REQUIRE:
                        print(f"FAIL: {engine} is required and cannot launch: {exc}")
                        return 3
                    print(f"!! {engine} unavailable, skipped: {exc}")
                    continue
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                # The account API is not under test; nothing here needs the network except Inter.
                context.route("**/graphql/**", lambda r: r.fulfill(status=204, body=""))
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                try:
                    check_pricing(page, base, engine)
                    check_features(page, base, engine)
                    check_download(page, base, engine)
                    check_about(page, base, engine)
                    check_no_sideways_scroll(page, base, engine)
                    check(f"{engine}: no page error on any page", not errors, "; ".join(errors[:3]))
                    if args.shots:
                        out = Path(args.shots)
                        out.mkdir(parents=True, exist_ok=True)
                        for route in ROUTES:
                            go(page, base, route)
                            page.screenshot(path=str(out / f"{route.strip('/')}.{engine}.png"), full_page=True)
                finally:
                    browser.close()
    finally:
        server.shutdown()

    print(f"\n{CHECKS} checks, {len(FAILURES)} failed")
    for f in FAILURES:
        print(f"  - {f}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
