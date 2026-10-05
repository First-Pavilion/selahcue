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
    """ClickUp 17tnw2b0x3h: the page draws no plan, price, comparison table, billing toggle or FAQ. Plan names, prices and limits are
    the API catalogue's data, so until it serves them the page says "Plans and prices have not been published yet." and nothing else."""
    print(f"[{engine}] pricing")
    go(page, base, "/pricing")
    headings_ok(page, "pricing")

    for selector, what in (
        (".pricing-card", "a plan card"),
        (".pricing-grid", "a plan grid"),
        (".comparison-table", "a comparison table"),
        ("[role=radiogroup]", "a billing toggle"),
        (".faq-section", "a FAQ"),
        ("main .ui-button", "a plan button"),
    ):
        check(f"pricing: no {what}", page.query_selector(selector) is None, selector)

    text = page.inner_text("main") if page.query_selector("main") else page.inner_text("body")
    check("pricing: no price figure is shown", "$" not in text, "a dollar sign is on the page")
    check("pricing: the empty state says plans and prices are not published yet", page.query_selector(".plans-empty") is not None and "have not been published yet" in page.inner_text(".plans-empty"), "")
    levels = page.evaluate("[...document.querySelectorAll('main h1, main h2')].map((h) => h.tagName)")
    check("pricing: the page's own headings are one h1 and one h2 (so the footer h3s do not follow an h1)", levels == ["H1", "H2"], str(levels))


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
