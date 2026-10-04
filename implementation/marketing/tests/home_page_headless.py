#!/usr/bin/env python3
"""Real-browser checks for the Home page (ClickUp 17tnw2b2cex).

`tests/homeView.test.ts` and `tests/homeAnchor.test.ts` read the source, server-render the page and drive
the cold-load anchor correction with a stand-in browser. This drives the BUILT page (`dist/`) in a real
browser, because what they cannot see is exactly what the Figma audit measured: computed size, weight and
colour, where a box lands, how tall a button really is, where Tab goes, what assistive technology is told,
and where a #fragment actually puts the section under the sticky bar.

Every number is a Figma value from `docs/design/visual-parity/marketing/figma-style/home.json` (frame
468:125), quoted next to its check. The harness (`scripts/visual_parity.py --suite marketing`) compares the
whole page against the frame; this is the part of that comparison a failing test can pin.

Usage (from implementation/marketing, after `npm run build`):
    python3 tests/home_page_headless.py [--engine chromium|webkit|both]

Needs Playwright and an engine. If either is missing this exits 0 with a LOUD skip unless
SELAHCUE_HEADLESS_REQUIRE=1, which makes a missing engine a hard failure so a gate can never silently
no-op. A stale `dist/` (older than `src/`) is refused, as the harness does.

Exit codes: 0 pass (or loud skip), 1 a check failed, 2 infrastructure problem, 3 a required engine is
unavailable.
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
DIST = MARKETING / "dist"
SRC = MARKETING / "src"
REQUIRE = os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1"

# Colours as getComputedStyle writes them, from tokens.css.
SURFACE = "rgb(20, 22, 29)"  # --sc-surface
BASE = "rgb(11, 13, 18)"  # --sc-base
BORDER = "rgb(38, 42, 52)"  # --sc-border
PRIMARY = "rgb(110, 92, 240)"  # --sc-primary
TEXT = "rgb(244, 246, 251)"  # --sc-text
SECONDARY = "rgb(167, 174, 190)"  # --sc-text-secondary


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):  # a page closed mid-response is routine
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


class SpaHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dist/ with a fallback to index.html for client-routed paths."""

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


def newest_mtime(root: Path) -> float:
    return max((p.stat().st_mtime for p in root.rglob("*") if p.is_file()), default=0.0)


class Run:
    def __init__(self, engine: str):
        self.engine = engine
        self.checks = 0
        self.failures: list[str] = []

    def check(self, ok: bool, what: str) -> None:
        self.checks += 1
        if not ok:
            self.failures.append(what)
            print(f"  FAIL [{self.engine}] {what}")

    def eq(self, got, want, what: str) -> None:
        self.check(got == want, f"{what}: got {got!r}, want {want!r}")

    def near(self, got, want, tol: float, what: str) -> None:
        self.check(isinstance(got, (int, float)) and abs(got - want) <= tol, f"{what}: got {got!r}, want {want} +-{tol}")


MEASURE_JS = r"""
() => {
  const q = (s, root = document) => root.querySelector(s);
  const qa = (s, root = document) => [...root.querySelectorAll(s)];
  const cs = (e) => getComputedStyle(e);
  const box = (e) => { const r = e.getBoundingClientRect(); return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height }; };
  const sec = (c) => q('section.' + c);
  const pad = (e) => ({ top: parseFloat(cs(e).paddingTop), bottom: parseFloat(cs(e).paddingBottom) });
  const font = (e) => ({ size: cs(e).fontSize, weight: cs(e).fontWeight, lh: cs(e).lineHeight, ls: cs(e).letterSpacing, color: cs(e).color });
  const out = { vw: innerWidth, docOverflowX: document.documentElement.scrollWidth > innerWidth };
  const hero = sec('hero-section');
  out.heroPad = pad(hero);
  out.h1 = font(q('h1', hero));
  out.heroSub = font(q('.hero-subtitle', hero));
  out.heroTrust = font(q('.hero-trust', hero));
  out.eyebrow = box(q('.hero-eyebrow', hero));
  out.eyebrowFont = font(q('.hero-eyebrow', hero));
  const hb = qa('.hero-actions .ui-button', hero);
  out.heroButtons = hb.map((b) => ({ label: b.textContent.trim(), h: box(b).h, tag: b.tagName, disabled: b.disabled === true }));
  out.consoleBox = box(q('.console-mockup', hero));
  out.consoleRole = q('.console-mockup', hero).getAttribute('role');
  out.features = { container: box(q('.container', sec('features-section'))), grid: box(q('.features-grid')), cards: qa('.feature-card').map((c) => box(c)), pad: pad(sec('features-section')) };
  out.featureTitle = font(q('.feature-card .card-title'));
  out.featureDesc = font(q('.feature-card .card-desc'));
  const rel = sec('reliability-section');
  out.rel = { box: box(rel), bg: cs(rel).backgroundColor, bt: cs(rel).borderTopWidth, bb: cs(rel).borderBottomWidth, bc: cs(rel).borderTopColor, pad: pad(rel), cardBg: cs(q('.pillar-card', rel)).backgroundColor, cards: qa('.pillar-card', rel).map((c) => box(c)), h2: font(q('h2', rel)), title: font(q('.pillar-title', rel)), tiles: qa('.icon-box', rel).map((t) => cs(t).backgroundColor), tileBox: box(q('.icon-box', rel)) };
  const out2 = sec('outputs-section');
  out.outputs = { pad: pad(out2), text: box(q('.outputs-content', out2)), win: box(q('.output-window', out2)), h2: font(q('h2', out2)), body: font(q('.outputs-body', out2)) };
  const steps = sec('steps-section');
  out.steps = { id: steps.id, pad: pad(steps), cards: qa('.step-card', steps).map((c) => box(c)), marker: font(q('.step-marker', steps)), markerBg: cs(q('.step-marker', steps)).backgroundColor, markerR: cs(q('.step-marker', steps)).borderRadius, title: font(q('.step-title', steps)), body: font(q('.step-body', steps)) };
  const pr = sec('pricing-section');
  out.pricing = { pad: pad(pr), cards: qa('.pricing-card', pr).map((c) => box(c)), h2: font(q('h2', pr)) };
  const te = sec('testimonials-section');
  out.testimonials = { bg: cs(te).backgroundColor, bt: cs(te).borderTopWidth, pad: pad(te), cards: qa('.testimonial-card', te).map((c) => ({ ...box(c), bg: cs(c).backgroundColor })), h2: font(q('h2', te)), quote: font(q('blockquote', te)), name: font(q('.author-name', te)), role: font(q('.author-role', te)), avatars: qa('.avatar-circle', te).map((a) => ({ bg: cs(a).backgroundColor, color: cs(a).color, w: box(a).w })) };
  const faq = sec('faq-section');
  out.faq = { pad: pad(faq), h2: font(q('h2', faq)), list: box(q('.faq-wrapper', faq)), q: font(q('.faq-question', faq)), a: font(q('.faq-answer p', faq)) };
  const cta = sec('final-cta-section');
  const card = q('.final-cta-card', cta);
  out.cta = { pad: pad(cta), card: box(card), radius: cs(card).borderRadius, bgImage: cs(card).backgroundImage.slice(0, 40), shadow: cs(card).boxShadow, h2: font(q('h2', cta)), sub: font(q('.cta-subtitle', cta)), buttons: qa('.ui-button', cta).map((b) => ({ label: b.textContent.trim(), h: box(b).h, w: box(b).w })) };
  out.headings = qa('main h1, main h2, main h3, main h4, main h5, main h6').map((h) => ({ level: +h.tagName[1], text: h.textContent.trim().slice(0, 40) }));
  out.images = qa('main [role=img]').map((e) => ({ label: e.getAttribute('aria-label'), hasHeading: !!e.querySelector('h1,h2,h3,h4,h5,h6'), focusable: !!e.querySelector('a,button,input,[tabindex]') }));
  out.emptyIcons = qa('main svg').filter((s) => s.getAttribute('aria-hidden') !== 'true').length;
  return out;
}
"""

TAB_JS = r"""
() => {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  const cs = getComputedStyle(a);
  return {
    label: (a.getAttribute('aria-label') || a.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40),
    tag: a.tagName,
    inMain: !!a.closest('main'),
    outlineStyle: cs.outlineStyle,
    outlineWidth: parseFloat(cs.outlineWidth),
    disabled: a.disabled === true,
  };
}
"""

TARGET_TOP_JS = r"""
(id) => { const e = document.getElementById(id); return e ? e.getBoundingClientRect().top : null; }
"""


def measure(page, width: int, height: int = 900):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(BASE_URL + "/", wait_until="networkidle")
    page.evaluate("document.fonts && document.fonts.ready")
    page.wait_for_timeout(300)
    return page.evaluate(MEASURE_JS)


BASE_URL = ""


def run_engine(p, engine_name: str) -> Run:
    r = Run(engine_name)
    browser = getattr(p, engine_name).launch()
    try:
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page_errors: list[str] = []
        page = context.new_page()
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        # ------------------------------------------------------------------ 1440: the designed layout
        m = measure(page, 1440)
        r.check(not m["docOverflowX"], "no horizontal scroll at 1440")

        # Figma 469:124: padding 96 above, 72 below; H1 60/64 Bold, 0 tracking; sub 19/29 muted; trust 13.5.
        r.eq(m["heroPad"], {"top": 96, "bottom": 72}, "hero padding (469:124)")
        r.eq((m["h1"]["size"], m["h1"]["weight"], m["h1"]["lh"], m["h1"]["ls"]), ("60px", "700", "64px", "normal"), "H1 60/64 Bold (469:128)")
        r.eq((m["heroSub"]["size"], m["heroSub"]["lh"]), ("19px", "29px"), "hero sub 19/29 (469:129)")
        r.eq(m["heroSub"]["color"], SECONDARY, "hero sub ink is --sc-text-secondary, not an off-token grey")
        r.eq(m["h1"]["color"], TEXT, "H1 ink is --sc-text, not pure white")
        r.eq((m["heroTrust"]["size"], m["heroTrust"]["lh"]), ("13.5px", "16px"), "trust line 13.5 (469:136)")
        r.near(m["eyebrow"]["h"], 32, 0.5, "hero eyebrow pill is 32px tall (469:125)")
        r.near(m["eyebrow"]["w"], 272, 3, "hero eyebrow pill is 272px wide (469:125)")
        # 469:131 is 49 tall (solid), 469:133 is 47 (quiet); the row is centred so neither is stretched.
        hb = {b["label"]: b for b in m["heroButtons"]}
        r.eq(hb.get("Download free", {}).get("h"), 49, "hero Download free is 49px (469:131)")
        r.eq(hb.get("Watch 2-min demo", {}).get("h"), 47, "hero Watch 2-min demo is 47px, not stretched to 49 (469:133; PR 172 review)")
        r.eq(hb.get("Watch 2-min demo", {}).get("tag"), "BUTTON", "the demo control is a button")
        r.eq(hb.get("Watch 2-min demo", {}).get("disabled"), True, "the demo button is disabled (nothing to play yet)")
        # 470:124: 1140 x 348 at x=150.
        r.near(m["consoleBox"]["w"], 1140, 0.5, "console mock is 1140 wide (470:124)")
        r.near(m["consoleBox"]["h"], 348, 0.5, "console mock is 348 tall (470:124)")
        r.near(m["consoleBox"]["x"], 150, 0.5, "console mock starts at x=150")
        r.eq(m["consoleRole"], "img", "the console mock is one image for assistive technology")

        # 472:129: grid 1248 wide, cards 402 x 218, 20 apart, padding 88.
        f = m["features"]
        r.near(f["grid"]["w"], 1248, 0.5, "feature grid is 1248 wide (472:129): the shared container, 96px gutters")
        r.near(f["container"]["w"], 1440, 0.5, "the container is the frame, 1440 (main.css .container)")
        r.check(all(abs(c["h"] - 218) <= 0.5 for c in f["cards"]), f"feature cards are 218 tall (472:130): {[c['h'] for c in f['cards']]}")
        r.check(all(abs(c["w"] - 402.67) <= 0.7 for c in f["cards"]), f"feature cards are 402 wide (472:130): {[round(c['w'], 1) for c in f['cards']]}")
        r.near(f["cards"][1]["x"] - (f["cards"][0]["x"] + f["cards"][0]["w"]), 20, 0.5, "feature cards are 20 apart (472:129)")
        r.eq(f["pad"], {"top": 88, "bottom": 88}, "Features padding 88 (472:124)")
        r.eq((m["featureTitle"]["size"], m["featureTitle"]["weight"]), ("18.5px", "600"), "feature title 18.5/600 (472:132)")
        r.eq((m["featureDesc"]["size"], m["featureDesc"]["lh"], m["featureDesc"]["color"]), ("14.5px", "22px", SECONDARY), "feature blurb 14.5/22 muted (472:133)")

        # 474:124: a full-width band, #171b22 with 1px edges, padding 90, cards on base, 28 apart.
        rel = m["rel"]
        r.near(rel["box"]["w"], 1440, 0.5, "Reliability is a full-width band (474:124)")
        r.eq((rel["bg"], rel["bt"], rel["bb"], rel["bc"]), (SURFACE, "1px", "1px", BORDER), "Reliability band fill and 1px edge rules (474:124)")
        r.near(rel["box"]["h"], 651, 1, "Reliability section is 651 tall (474:124)")
        r.eq(rel["cardBg"], BASE, "pillar cards sit on the base ground (474:130)")
        r.check(all(abs(c["h"] - 223) <= 0.5 for c in rel["cards"]), f"pillar cards are 223 tall (474:130): {[c['h'] for c in rel['cards']]}")
        r.eq((rel["h2"]["size"], rel["h2"]["weight"], rel["h2"]["lh"]), ("42px", "700", "48px"), "Reliability title 42/48 Bold (474:126)")
        r.eq((rel["title"]["size"], rel["title"]["weight"]), ("20px", "600"), "pillar title 20/600 (474:132)")
        r.eq(rel["tiles"], [PRIMARY, "rgb(53, 192, 138)", "rgb(245, 165, 36)"], "pillar tiles are filled brand, preview, warn (474:131/138/145)")
        r.near(rel["tileBox"]["w"], 46, 0.5, "pillar tile is 46px (474:131)")

        # 475:124: padding 90; text column 470, window 706 x 306 at gap 72, columns centred.
        o = m["outputs"]
        r.eq(o["pad"], {"top": 90, "bottom": 90}, "Showcase padding 90 (475:124)")
        r.near(o["text"]["w"], 470, 0.5, "showcase text column is 470 wide (475:125)")
        r.near(o["win"]["w"], 706, 0.5, "output window is 706 wide (475:142)")
        r.near(o["win"]["h"], 306, 0.5, "output window is 306 tall (475:142)")
        r.near(o["win"]["x"] - (o["text"]["x"] + o["text"]["w"]), 72, 0.5, "showcase columns are 72 apart (475:124)")
        r.near(o["text"]["h"], 336, 1, "showcase text column is 336 tall (475:125)")
        r.near(o["win"]["y"] - o["text"]["y"], 15, 1, "the window sits 15px below the text top: Figma centres the columns (475:142 against 475:125)")
        r.eq((o["h2"]["size"], o["h2"]["weight"], o["h2"]["lh"]), ("40px", "700", "46px"), "showcase title 40/46 Bold (475:127)")

        # 476:124: padding 88; cards 397.3 x 232, 28 apart; marker a 46px brand circle, white 21/700.
        s = m["steps"]
        r.eq(s["id"], "how-it-works", "the steps section has id how-it-works (the nav link's target)")
        r.eq(s["pad"], {"top": 88, "bottom": 88}, "How it works padding 88 (476:124)")
        r.check(all(abs(c["h"] - 232) <= 0.5 for c in s["cards"]), f"step cards are 232 tall (476:130): {[c['h'] for c in s['cards']]}")
        r.check(all(abs(c["w"] - 397.33) <= 0.7 for c in s["cards"]), f"step cards are 397.3 wide (476:130): {[round(c['w'], 1) for c in s['cards']]}")
        r.eq((s["markerBg"], s["markerR"]), (PRIMARY, "999px"), "step marker is a brand circle (476:131)")
        r.eq((s["marker"]["size"], s["marker"]["weight"]), ("21px", "700"), "step numeral 21/700 (476:132)")
        r.eq((s["title"]["size"], s["title"]["weight"]), ("21px", "600"), "step title 21/600 (476:133)")
        r.eq((s["body"]["size"], s["body"]["lh"]), ("15px", "23px"), "step body 15/23 (476:134)")

        # 477:124: padding 90; cards 400 wide, 24 apart.
        pr = m["pricing"]
        r.eq(pr["pad"], {"top": 90, "bottom": 90}, "Pricing padding 90 (477:124)")
        r.check(all(abs(c["w"] - 400) <= 0.5 for c in pr["cards"]), f"plan cards are 400 wide (477:130): {[c['w'] for c in pr['cards']]}")
        r.near(pr["cards"][1]["x"] - (pr["cards"][0]["x"] + pr["cards"][0]["w"]), 24, 0.5, "plan cards are 24 apart (477:129)")

        # 478:124: a full-width band; cards 400 on base, radius 16, 24 apart; avatar 42; quote 17/26; title 38.
        t = m["testimonials"]
        r.eq((t["bg"], t["bt"]), (SURFACE, "1px"), "Testimonials band fill and edge (478:124)")
        r.check(all(c["bg"] == BASE for c in t["cards"]), "testimonial cards sit on the base ground (478:129)")
        r.check(all(abs(c["w"] - 400) <= 0.5 for c in t["cards"]), f"testimonial cards are 400 wide (478:129): {[c['w'] for c in t['cards']]}")
        r.eq((t["h2"]["size"], t["h2"]["weight"]), ("38px", "700"), "Testimonials title 38 Bold (478:126)")
        r.eq((t["quote"]["size"], t["quote"]["lh"], t["quote"]["color"]), ("17px", "26px", TEXT), "quote 17/26 in the primary ink (478:130)")
        r.eq((t["name"]["size"], t["name"]["weight"]), ("14.5px", "600"), "name 14.5/600 (478:133)")
        r.eq((t["role"]["size"], t["role"]["color"]), ("12.5px", SECONDARY), "role 12.5 muted (478:135)")
        r.check(all(abs(a["w"] - 42) <= 0.5 for a in t["avatars"]), "avatars are 42px (478:132)")
        # The dark initials on the green and gold fills (Figma's white is 2.3:1 and 2.0:1; audit home-44).
        r.eq([a["color"] for a in t["avatars"]], ["rgb(255, 255, 255)", BASE, BASE], "initials: white on the brand fill, dark on green and gold")

        # 478:153: padding 90; title 38; the list 780 wide.
        q = m["faq"]
        r.eq(q["pad"], {"top": 90, "bottom": 90}, "FAQ padding 90 (478:153)")
        r.eq((q["h2"]["size"], q["h2"]["weight"]), ("38px", "700"), "FAQ title 38 Bold (478:154)")
        r.near(q["list"]["w"], 780, 0.5, "FAQ list is 780 wide (478:155)")
        r.eq((q["q"]["size"], q["q"]["weight"]), ("18px", "600"), "FAQ question 18/600 (478:158)")
        r.eq((q["a"]["size"], q["a"]["lh"]), ("15.5px", "24px"), "FAQ answer 15.5/24 (478:160)")

        # 479:125: card 1248 x 337, radius 24, the brand gradient, no shadow; H2 44/50; buttons 167x49 and 137x47.
        c = m["cta"]
        r.eq(c["pad"], {"top": 90, "bottom": 90}, "Final CTA padding 90 (479:124)")
        r.near(c["card"]["w"], 1248, 0.5, "final CTA card is 1248 wide (479:125)")
        r.near(c["card"]["h"], 337, 1, "final CTA card is 337 tall (479:125)")
        r.eq((c["radius"], c["shadow"]), ("24px", "none"), "final CTA card radius 24 and no shadow (479:125)")
        r.check(c["bgImage"].startswith("linear-gradient"), f"final CTA card is the gradient token: {c['bgImage']}")
        r.eq((c["h2"]["size"], c["h2"]["lh"], c["h2"]["weight"]), ("44px", "50px", "700"), "final CTA title 44/50 Bold (479:127)")
        r.eq(c["sub"]["size"], "19px", "final CTA sub 19px (479:130)")
        bl = {b["label"]: b for b in c["buttons"]}
        r.eq(bl.get("Download free", {}).get("h"), 49, "CTA Download free is 49px (479:129)")
        r.eq(bl.get("See pricing", {}).get("h"), 47, "CTA See pricing is 47px (479:131)")

        # Semantics: one h1, no skipped level, the mocks are named images with no heading or tab stop inside.
        lv = [h["level"] for h in m["headings"]]
        r.eq(lv.count(1), 1, "one h1 in main")
        r.check(all(b <= a + 1 for a, b in zip(lv, lv[1:])), f"no heading level is skipped in main: {lv}")
        r.eq(len(m["images"]), 2, "two role=img mocks")
        r.check(all(i["label"] and not i["hasHeading"] and not i["focusable"] for i in m["images"]), f"each mock is named and holds no heading or tab stop: {m['images']}")
        r.eq(m["emptyIcons"], 0, "every svg in main is aria-hidden")

        # What assistive technology reads from the console and the output window.
        snap = page.locator("main").aria_snapshot()
        r.check('img "SelahCue operator console showing a Preview and a Live scripture slide"' in snap, "the aria snapshot names the console image")
        r.check("PSALM 46:10" not in snap and "JOHN 3:16" not in snap and "+ Add output" not in snap, "the aria snapshot does not read the mock's fake UI text")

        # ------------------------------------------------------------------ keyboard
        page.goto(BASE_URL + "/", wait_until="networkidle")
        page.evaluate("window.scrollTo(0, 0); document.activeElement && document.activeElement.blur()")
        seen: list[dict] = []
        # WebKit on macOS does not Tab to links and buttons unless Option is held; Chromium takes plain Tab.
        tab = "Alt+Tab" if engine_name == "webkit" else "Tab"
        for _ in range(40):
            page.keyboard.press(tab)
            st = page.evaluate(TAB_JS)
            if st is None:
                break
            seen.append(st)
        in_main = [s for s in seen if s["inMain"]]
        labels = [s["label"] for s in in_main]
        want = [
            "Download free",  # hero (the disabled demo button is skipped)
            "Download free",  # the Free plan (the Pro button is disabled, skipped)
            "Talk to us",
            "Do I need an internet connection?",
            "Which platforms are supported?",
            "Can I use my own songs, slides, and designs?",
            "What is NDI, and do I need it?",
            "How does billing work?",
            "Download free",  # the final band
            "See pricing",
        ]
        r.eq(labels, [w[:40] for w in want], "Tab order through the page body")
        r.check(all(s["outlineStyle"] != "none" and s["outlineWidth"] >= 2 for s in in_main), f"every Tab stop in the page body shows a focus ring: {[(s['label'], s['outlineStyle'], s['outlineWidth']) for s in in_main if s['outlineStyle'] == 'none' or s['outlineWidth'] < 2]}")
        r.check(not any(s["disabled"] for s in seen), "Tab never lands on a disabled button")

        # ------------------------------------------------------------------ the anchor, cold and from another page
        # The navbar bar is 79px; the router leaves 16px more (router/scroll.ts), so the section lands at 95.
        def cold(hash_: str):
            """A real cold load: a fresh page, because a hash-only goto on the same page is not one."""
            fresh = context.new_page()
            errors: list[str] = []
            fresh.on("pageerror", lambda e: errors.append(str(e)))
            fresh.goto(BASE_URL + "/" + hash_, wait_until="networkidle")
            fresh.evaluate("document.fonts && document.fonts.ready")
            fresh.wait_for_timeout(1500)  # the router scroll is smooth; let it, and the one font correction, finish
            return fresh, errors

        fresh, errors = cold("#how-it-works")
        r.near(fresh.evaluate(TARGET_TOP_JS, "how-it-works"), 95, 2, "a cold load of /#how-it-works puts the section 95px from the top, clear of the 79px bar")
        r.eq(errors, [], "a cold load of /#how-it-works raises no page error")
        fresh.close()
        for hash_ in ("#1abc", "#%", "#%E0%A4%A", "#nope"):
            fresh, errors = cold(hash_)
            r.eq(errors, [], f"a cold load of /{hash_} raises no page error")
            r.near(fresh.evaluate("window.scrollY"), 0, 1, f"a cold load of /{hash_} (no such element) stays at the top")
            fresh.close()
        page.goto(BASE_URL + "/pricing", wait_until="networkidle")
        page.evaluate("document.fonts && document.fonts.ready")
        page.get_by_role("link", name="How it works").first.click()
        page.wait_for_url("**/#how-it-works")
        page.wait_for_timeout(1200)
        r.near(page.evaluate(TARGET_TOP_JS, "how-it-works"), 95, 2, "the navbar's How it works, clicked on /pricing, lands on the section clear of the bar")

        # ------------------------------------------------------------------ the other widths
        for w in (768, 375):
            mm = measure(page, w)
            r.check(not mm["docOverflowX"], f"no horizontal scroll at {w}")
            r.eq(mm["consoleRole"], "img", f"the console mock is still one image at {w}")
            hbm = {b["label"]: b for b in mm["heroButtons"]}
            r.check(hbm.get("Download free", {}).get("h", 0) >= 44, f"hero buttons clear the 44px touch target at {w}")
            lv = [h["level"] for h in mm["headings"]]
            r.check(all(b <= a + 1 for a, b in zip(lv, lv[1:])), f"no heading level is skipped at {w}")
        r.eq(page_errors, [], "no page error in the whole run")
    finally:
        browser.close()
    return r


def main() -> int:
    global BASE_URL
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", choices=["chromium", "webkit", "both"], default="both")
    args = ap.parse_args()
    engines = ["chromium", "webkit"] if args.engine == "both" else [args.engine]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        msg = "Playwright is not installed"
        if REQUIRE:
            print(f"FAIL: SELAHCUE_HEADLESS_REQUIRE=1 but {msg}")
            return 3
        print(f"!! HOME PAGE CHECKS SKIPPED -- {msg}\n!! (set SELAHCUE_HEADLESS_REQUIRE=1 to make this a failure)")
        return 0

    if not (DIST / "index.html").is_file():
        print("FAIL: dist/ is missing: run `npm run build` first")
        return 2
    if newest_mtime(SRC) > (DIST / "index.html").stat().st_mtime:
        print("FAIL: dist/ is older than src/: run `npm run build` first (a stale bundle would test last week's page)")
        return 2

    server = Server(("127.0.0.1", 0), SpaHandler)
    BASE_URL = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()

    failed = 0
    total = 0
    try:
        with sync_playwright() as p:
            for engine in engines:
                try:
                    run = run_engine(p, engine)
                except Exception as exc:  # an engine that is not installed raises on launch
                    if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
                        if REQUIRE:
                            print(f"FAIL: SELAHCUE_HEADLESS_REQUIRE=1 but {engine} is not installed")
                            return 3
                        print(f"!! {engine} SKIPPED -- not installed")
                        continue
                    raise
                total += run.checks
                failed += len(run.failures)
                print(f"{engine}: {run.checks} checks, {len(run.failures)} failed")
    finally:
        server.shutdown()
    print(json.dumps({"checks": total, "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
