#!/usr/bin/env python3
"""Real-browser checks for the five shared components (ClickUp 17tnw2b2cew).

`tests/sharedComponents.test.ts` reads the source and server-renders the components. This
drives the SAME components in a real browser, because what it cannot see is exactly what the
Figma audit found wrong: computed colour and size, where a box lands, whether Tab goes where
the design says, whether a collapsed answer is really gone from the accessibility tree, where
focus goes when a dialog opens and closes.

It builds `tests/gallery/` (every state of every component on one page; not shipped) with
Vite, serves the folder, and drives it with Playwright. Every number below is a Figma value
from `docs/design/visual-parity/marketing/figma-style/*.json`, quoted next to its check.

Usage (from implementation/marketing):
    python3 scripts/shared_components_headless.py [--engine chromium|webkit|both] [--shots DIR]
    python3 scripts/shared_components_headless.py --dump-defaults FILE            # record computed styles
    python3 scripts/shared_components_headless.py --compare-defaults FILE         # diff against a recording

"The default look of every existing form is unchanged" is proved by recording the defaults
section (and the default dialogs) from the audit branch's components (`--gallery-src` points the
build at another checkout's `src`) and diffing the recording against this branch.

Needs Playwright and an engine (`pip install playwright && playwright install chromium webkit`)
and the network for Inter. If either is missing this exits 0 with a LOUD skip unless
SELAHCUE_HEADLESS_REQUIRE=1, which makes a missing engine a hard failure so a gate can never
silently no-op.

Exit codes: 0 pass (or loud skip), 1 a check failed, 2 infrastructure problem, 3 a required
engine is unavailable.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETING = HERE.parent
GALLERY_CONFIG = MARKETING / "tests" / "gallery" / "vite.config.ts"
REQUIRE = os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1"

# Colours as `getComputedStyle` writes them, from tokens.css.
ELEVATED = "rgb(28, 31, 40)"  # --sc-elevated
BASE = "rgb(11, 13, 18)"  # --sc-base
SURFACE = "rgb(20, 22, 29)"  # --sc-surface
BORDER = "rgb(38, 42, 52)"  # --sc-border
PRIMARY = "rgb(110, 92, 240)"  # --sc-primary
TEXT = "rgb(244, 246, 251)"  # --sc-text
SECONDARY = "rgb(167, 174, 190)"  # --sc-text-secondary
PREVIEW = "rgb(53, 192, 138)"  # --sc-preview
WARN = "rgb(245, 165, 36)"  # --sc-warn
LIVE = "rgb(255, 77, 77)"  # --sc-live
OVERRIDE_INK = "rgb(165, 180, 252)"  # #a5b4fc, set on the gallery's override block


def skip_or_fail(reason: str) -> int:
    if REQUIRE:
        print(f"FAIL (required): {reason}")
        return 3
    print("=" * 78)
    print(f"SKIPPED (loud): {reason}")
    print("Set SELAHCUE_HEADLESS_REQUIRE=1 to make this a failure. Nothing was checked.")
    print("=" * 78)
    return 0


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


# --------------------------------------------------------------------------------- browser helpers

STYLE_JS = """([sel, props]) => {
  const e = document.querySelector(sel);
  if (!e) return null;
  const c = getComputedStyle(e);
  const r = e.getBoundingClientRect();
  const o = { x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, bottom: r.bottom, text: (e.innerText || '').trim() };
  for (const p of props) o[p] = c.getPropertyValue(p);
  return o;
}"""

SNAPSHOT_JS = """(rootSel) => {
  const root = document.querySelector(rootSel);
  if (!root) return null;
  const PROPS = ['font-size','font-weight','line-height','letter-spacing','color','background-color',
    'border-top-width','border-top-color','border-top-style','border-radius','padding-top','padding-right',
    'padding-bottom','padding-left','margin-top','margin-bottom','display','flex-direction','gap','text-align',
    'opacity','box-shadow','cursor','text-transform','overflow-y','position'];
  const out = [];
  for (const e of [root, ...root.querySelectorAll('*')]) {
    const c = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    const o = { tag: e.tagName.toLowerCase(), w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 };
    for (const p of PROPS) o[p] = c.getPropertyValue(p);
    out.push(o);
  }
  return out;
}"""

LUMINANCE_JS = """([fg, bg]) => {
  const parse = (s) => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const L = (rgb) => 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
  const a = L(parse(fg)), b = L(parse(bg));
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}"""


def style(page, sel: str, props: list[str] | None = None) -> dict:
    got = page.evaluate(STYLE_JS, [sel, props or []])
    if got is None:
        raise LookupError(f"nothing matches {sel!r}")
    return got


def settle(page) -> None:
    """No transition or animation running: a rect measured mid-slide is a wrong rect."""
    page.wait_for_function(
        "document.getAnimations().every((a) => a.playState !== 'running')", timeout=5000
    )


def active(page) -> str:
    return page.evaluate(
        """() => { const a = document.activeElement; if (!a) return '(none)';
          return a.getAttribute('aria-label') || a.id || (a.innerText || '').trim().slice(0, 30) || a.tagName; }"""
    )


def tab(page, c: "Checks", shift: bool = False) -> None:
    """Press Tab the way a keyboard user of this engine does.

    Safari and Playwright's WebKit on macOS only Tab to text fields unless a system setting
    ("Press Tab to highlight each item") is on; Option+Tab is the documented way to reach
    buttons and links there. Chromium and WebKit elsewhere Tab to every control.
    """
    alt = c.engine == "webkit" and sys.platform == "darwin"
    page.keyboard.press(("Alt+" if alt else "") + ("Shift+Tab" if shift else "Tab"))


def contrast(page, fg: str, bg: str) -> float:
    return page.evaluate(LUMINANCE_JS, [fg, bg])


# ------------------------------------------------------------------------------------------ checks


def check_badges(page, c: Checks) -> None:
    def badge(case: str, name: str, extra: list[str] | None = None) -> dict:
        return style(
            page,
            f'[data-case="{case}"] [data-badge="{name}"]',
            ["font-size", "font-weight", "letter-spacing", "line-height", "color", "background-color",
             "padding-top", "padding-right", "padding-left", "border-top-width", "text-transform", *(extra or [])],
        )

    f = badge("badges", "featured")
    # careers 503:140: 12px/700, ls 1.2, pad 6/12 (5/11 + the 1px border), fill #1e232c, h27, uppercase
    c.eq(f["font-size"], "12px", "featured (page eyebrow pill) font-size")
    c.eq(f["font-weight"], "700", "featured font-weight")
    c.eq(f["letter-spacing"], "1.2px", "featured letter-spacing (0.1em of 12px)")
    c.eq((f["padding-top"], f["padding-right"], f["border-top-width"]), ("5px", "11px", "1px"), "featured padding + border = 6/12")
    c.near(f["h"], 27, 0.5, "featured height (Figma 27)")
    c.eq(f["background-color"], ELEVATED, "featured fill is the elevated surface")
    c.eq(f["text-transform"], "uppercase", "featured is uppercase")
    c.eq(f["color"], PRIMARY, "featured ink keeps today's --sc-primary until Uma picks one (D)")

    e = badge("badges", "eyebrow")
    # home 13/700 ls 0.3 uppercase, no pill
    c.eq((e["font-size"], e["font-weight"], e["letter-spacing"]), ("13px", "700", "0.3px"), "eyebrow 13px/700, 0.3px")
    c.eq(e["background-color"], "rgba(0, 0, 0, 0)", "eyebrow has no fill (it is plain text, not a pill)")
    c.eq((e["padding-top"], e["padding-left"], e["border-top-width"]), ("0px", "0px", "0px"), "eyebrow has no padding or border")
    c.eq(e["color"], TEXT, "eyebrow ink is the readable --sc-text it rendered before (accessible)")

    a = badge("badges", "accent")
    c.eq(a["background-color"], ELEVATED, "accent is a chip on the elevated surface")
    c.eq((a["font-weight"], a["font-size"]), ("700", "10.5px"), "accent is bold, sm scale")
    c.eq(a["color"], TEXT, "accent ink is the readable --sc-text (accessible) until Uma picks one")

    w = badge("badges", "warn")
    c.eq((w["color"], w["background-color"]), (WARN, ELEVATED), "warn is amber on the elevated surface (changelog Fixed)")

    p = badge("badges", "preview-sm")
    # changelog tags / PAID 10.5/700 ls .6, h21, fill #1e232c
    c.eq((p["font-size"], p["font-weight"], p["letter-spacing"]), ("10.5px", "700", "0.6px"), "preview sm is 10.5px/700, 0.6px (PAID)")
    c.near(p["h"], 21, 0.5, "preview sm height (Figma PAID 21)")
    c.eq(p["background-color"], ELEVATED, "preview fill is the elevated surface (account-12)")
    c.eq(p["color"], PREVIEW, "preview ink stays the mapped --sc-preview")
    m = badge("badges", "preview-md")
    c.eq((m["font-size"], m["letter-spacing"]), ("11px", "0.7px"), "preview md is 11px/0.7px (ACTIVE)")
    c.near(m["h"], 23, 0.5, "preview md height (Figma ACTIVE 23)")

    for name in ("live", "ready", "ndi", "new"):
        s = badge("badges", name)
        c.eq(s["font-weight"], "700", f"{name} shares the bold badge scale")
        c.ok(s["background-color"] != "rgba(0, 0, 0, 0)", f"{name} still has its tone fill")

    # the ONE ink property: set on an ancestor, it re-inks featured, accent and eyebrow together
    for name in ("featured", "accent", "eyebrow"):
        c.eq(badge("badges-ink", name)["color"], OVERRIDE_INK, f"--ui-badge-ink on an ancestor re-inks {name}")


def check_faq(page, c: Checks) -> None:
    case = '[data-case="faq-plain"]'
    snap = lambda: page.locator(case).aria_snapshot()  # noqa: E731

    n = page.locator(f"{case} .faq-question").count()
    c.eq(n, 5, "plain accordion has five questions")
    for i in range(n):
        q = page.locator(f"{case} .faq-question").nth(i)
        a = page.locator(f"{case} .faq-answer-wrapper").nth(i)
        c.eq(q.get_attribute("aria-controls"), a.get_attribute("id"), f"question {i} aria-controls is its answer's id")
        c.eq(a.get_attribute("role"), "region", f"answer {i} is a region")
        c.eq(a.get_attribute("aria-labelledby"), q.get_attribute("id"), f"answer {i} is labelled by its question")
        c.eq(q.get_attribute("aria-expanded"), "true" if i == 0 else "false", f"question {i} aria-expanded")
        vis = a.evaluate("e => getComputedStyle(e).visibility")
        c.eq(vis, "visible" if i == 0 else "hidden", f"answer {i} computed visibility")

    tree = snap()
    c.ok("The first answer is long" in tree, "the OPEN answer is in the accessibility tree")
    for text in ("The second answer.", "The third answer.", "The fifth answer."):
        c.ok(text not in tree, f"collapsed answer {text!r} is NOT in the accessibility tree")
    # the plain Figma "+" is a 22px glyph (home-39)
    # offsetWidth: the open one is rotated 45 degrees, which widens its bounding box
    icon_w = page.locator(f"{case} .toggle-icon").first.evaluate("e => e.getBoundingClientRect().width / (e.classList.contains('rotated') ? Math.SQRT2 : 1)")
    c.near(icon_w, 22, 0.5, "toggle icon width (22px)")
    c.eq(page.locator(f"{case} .toggle-icon").first.get_attribute("aria-hidden"), "true", "toggle icon is hidden from assistive technology")

    # open the second: the first closes, the tree follows
    page.locator(f"{case} .faq-question").nth(1).click()
    page.wait_for_function(
        "(c) => getComputedStyle(document.querySelectorAll(c + ' .faq-answer-wrapper')[1]).visibility === 'visible'"
        " && getComputedStyle(document.querySelectorAll(c + ' .faq-answer-wrapper')[0]).visibility === 'hidden'",
        arg=case, timeout=3000,
    )
    tree = snap()
    c.ok("The second answer." in tree, "after opening it, the second answer is in the accessibility tree")
    c.ok("The first answer is long" not in tree, "after closing it, the first answer left the accessibility tree")
    c.eq(page.locator(f"{case} .faq-question").nth(1).get_attribute("aria-expanded"), "true", "aria-expanded follows the click")

    # keyboard: Enter and Space toggle a focused question
    third = page.locator(f"{case} .faq-question").nth(2)
    third.focus()
    page.keyboard.press("Enter")
    c.eq(third.get_attribute("aria-expanded"), "true", "Enter opens a question")
    page.keyboard.press("Space")
    c.eq(third.get_attribute("aria-expanded"), "false", "Space closes it again")

    # BOXED (Affiliates 542:199)
    case = '[data-case="faq-boxed"]'
    box = style(page, f"{case} .faq-accordion", ["border-top-width", "border-top-color", "border-radius", "background-color"])
    c.near(box["w"], 880, 0.5, "boxed card is 880 wide")
    c.near(box["x"] - style(page, case)["x"], 80, 1, "boxed card is centred in its container")
    c.eq((box["border-top-width"], box["border-top-color"], box["border-radius"]), ("1px", BORDER, "16px"), "boxed card: 1px --sc-border, radius 16")
    c.eq(box["background-color"], BASE, "boxed card fill is --sc-base")
    q0 = style(page, f"{case} .faq-question", ["padding-top", "padding-left", "font-size", "font-weight"])
    c.eq((q0["padding-top"], q0["padding-left"]), ("18px", "22px"), "boxed row padding 18px 22px")
    c.eq((q0["font-size"], q0["font-weight"]), ("16px", "600"), "boxed question 16px/600")
    items = page.locator(f"{case} .faq-item")
    h = [items.nth(i).bounding_box()["height"] for i in range(items.count())]
    c.near(h[1], 55, 1.5, "boxed closed row height (Figma 55, plus its 1px rule)")
    c.near(h[0], 113, 2.5, "boxed open row with a two-line answer (Figma 113, plus its 1px rule)")
    ans = style(page, f"{case} .faq-answer p", ["font-size", "line-height", "padding-left"])
    c.eq((ans["font-size"], ans["line-height"], ans["padding-left"]), ("15px", "23px", "22px"), "boxed answer 15px/23px at 22px")
    ic = style(page, f"{case} .toggle-icon", ["stroke-width"])
    # the svg is 16px so the plus inside it (two thirds of the box) draws 10.7px across; the open icon is rotated
    c.near(ic["w"] / 1.4142, 16, 0.5, "boxed icon box is 16px (plus 10.5px across, Figma 10.5)")
    c.eq(ic["stroke-width"], "2.25px", "boxed icon stroke is 2.25 units, drawn 1.5px")


def check_pricing(page, c: Checks) -> None:
    settle(page)  # the accordion above has just finished (or is finishing) a collapse: it moves everything below it
    cards = page.locator('[data-case="pricing"] .pricing-card')
    c.eq(cards.count(), 3, "three plan cards")
    rects = [cards.nth(i).bounding_box() for i in range(3)]
    for i, r in enumerate(rects):
        c.near(r["width"], 400, 0.5, f"card {i} width (Figma 400)")
    c.near(rects[0]["y"], rects[1]["y"], 0.5, "cards are TOP-aligned even in a grid that says stretch")
    c.near(rects[0]["y"], rects[2]["y"], 0.5, "free and church tops agree")
    c.near(rects[0]["height"], rects[2]["height"], 1.0, "free and church are the same height")
    c.ok(rects[1]["height"] > rects[0]["height"] + 80, "the popular plan is taller than its neighbours, as drawn")
    c.near(rects[0]["height"], 408, 3, "free card height (Figma 408)")

    for i, name in enumerate(("free", "pro", "church")):
        st = cards.nth(i).evaluate(
            """e => { const c = getComputedStyle(e); return { r: c.borderTopLeftRadius, bw: c.borderTopWidth, bc: c.borderTopColor,
              pl: c.paddingLeft, pt: c.paddingTop, pb: c.paddingBottom, bg: c.backgroundColor, sh: c.boxShadow, bi: c.backgroundImage }; }"""
        )
        popular = name == "pro"
        c.eq(st["r"], "18px", f"{name} radius 18")
        c.eq((st["bw"], st["bc"]), (("2px", PRIMARY) if popular else ("1px", BORDER)), f"{name} border (popular: 2px primary)")
        c.eq(st["bg"], SURFACE, f"{name} fill is --sc-surface (no hard-coded hex)")
        c.eq(st["sh"], "none", f"{name} has no glow or shadow")
        c.eq(st["bi"], "none", f"{name} has no gradient")
        # Figma measures padding to the OUTER edge: 32/30 (popular 34/30/32/30)
        c.near(float(st["pl"][:-2]) + float(st["bw"][:-2]), 30, 0.1, f"{name} left padding + border = 30")
        c.near(float(st["pt"][:-2]) + float(st["bw"][:-2]), 34 if popular else 32, 0.1, f"{name} top padding + border")
        c.near(float(st["pb"][:-2]) + float(st["bw"][:-2]), 32, 0.1, f"{name} bottom padding + border = 32")

        card = cards.nth(i)
        cb = rects[i]
        name_box = card.locator(".plan-name").bounding_box()
        c.near(name_box["x"] - cb["x"], 30, 0.6, f"{name} content starts 30px in (Figma)")
        cta = card.locator(".cta-wrapper .ui-button")
        cta_box = cta.bounding_box()
        cs = cta.evaluate("e => { const c = getComputedStyle(e); return { r: c.borderTopLeftRadius, fs: c.fontSize, fw: c.fontWeight }; }")
        c.near(cta_box["width"], 340, 0.6, f"{name} call to action is the card's full inner width (340)")
        c.near(cta_box["height"], 44, 0.5, f"{name} call to action is 44px tall")
        c.eq((cs["r"], cs["fs"], cs["fw"]), ("11px", "15px", "600"), f"{name} call to action radius 11, 15px/600")
        div = card.locator(".features-divider").bounding_box()
        c.ok(cta_box["y"] + cta_box["height"] < div["y"], f"{name} call to action is ABOVE the divider")
        feats = card.locator(".features-list li").count()
        ticks = card.locator("svg.check-icon")
        c.eq(ticks.count(), feats, f"{name}: one SVG tick per feature")
        c.eq(ticks.first.evaluate("e => getComputedStyle(e).color"), PREVIEW, f"{name} tick is --sc-preview")
        tick_box = ticks.first.bounding_box()
        c.near(tick_box["width"], 17, 0.5, f"{name} tick box 17 wide (text starts at +27)")
        if not popular:
            c.near(div["y"] - (cta_box["y"] + cta_box["height"]), 18, 1.0, f"{name} divider is 18px under the call to action")

    pro = cards.nth(1)
    chip = pro.locator(".plan-chip")
    chip_box = chip.bounding_box()
    hdr = pro.locator(".plan-header").bounding_box()
    nm = pro.locator(".plan-name").bounding_box()
    c.near(chip_box["height"], 22, 0.6, "MOST POPULAR chip is 22 tall (Figma 483:180)")
    c.near(chip_box["x"] + chip_box["width"], hdr["x"] + hdr["width"], 0.6, "the chip is right-aligned in the header row")
    c.near((chip_box["y"] + chip_box["height"] / 2), (nm["y"] + nm["height"] / 2), 2.0,
           f"chip and plan name share a line (header {hdr['y']:.1f}+{hdr['height']:.1f}, name {nm['y']:.1f}+{nm['height']:.1f}, chip {chip_box['y']:.1f}+{chip_box['height']:.1f})")
    cst = chip.evaluate("e => { const c = getComputedStyle(e); return { fs: c.fontSize, fw: c.fontWeight, ls: c.letterSpacing, bg: c.backgroundColor, pos: c.position }; }")
    c.eq((cst["fs"], cst["fw"], cst["ls"]), ("10px", "700", "0.1px"), "chip is 10px/700 with +0.1px tracking")
    c.eq(cst["bg"], ELEVATED, "chip is on the elevated surface (a pill, not bare text)")
    c.eq(cst["pos"], "static", "chip is in the flow (not floating over the border)")

    # honest call to action: links for free and church, a disabled, explained button for pro
    for i, href in ((0, "/download"), (2, "/contact")):
        a = cards.nth(i).locator(".cta-wrapper a")
        c.eq(a.count(), 1, f"card {i} call to action is a link")
        c.eq(a.get_attribute("href"), href, f"card {i} link destination")
    btn = pro.locator(".cta-wrapper button")
    c.eq(btn.count(), 1, "pro without a destination renders one button")
    c.ok(btn.is_disabled(), "that button is disabled (a dead enabled button is the bug)")
    note_id = btn.get_attribute("aria-describedby")
    c.ok(note_id and page.locator(f"#{note_id}").inner_text().strip() == "Not available yet", "the disabled button is described by a visible 'Not available yet'")

    # keyboard: Tab goes link to link and skips the disabled button
    cards.nth(0).locator(".cta-wrapper a").focus()
    tab(page, c)
    c.eq(active(page), "Talk to us", "Tab from Download free lands on Talk to us (the disabled Get Pro is skipped)")


def check_formfield(page, c: Checks) -> None:
    settle(page)
    case = '[data-case="signin-fields"]'
    # signin 505:137: "Forgot?" in the label row, right-aligned; tab order Email, Password, Forgot, Sign in
    label = style(page, f"{case} label[for='s-password']")
    link = style(page, f'{case} [data-probe="forgot"]', ["font-size", "font-weight", "color"])
    wrapper = style(page, f"{case} #s-password")
    c.near((link["y"] + link["h"] / 2), (label["y"] + label["h"] / 2), 4, "Forgot? is on the label's row")
    c.ok(link["x"] > label["x"] + label["w"], "Forgot? is to the right of the label")
    c.near(link["right"], wrapper["right"], 1.0, "Forgot? is flush with the field's right edge")
    c.eq((link["font-size"], link["font-weight"], link["color"]), ("13px", "500", PRIMARY), "Forgot? is 13px/500 in the link colour")
    c.eq(page.locator(f'{case} [data-probe="forgot"]').get_attribute("aria-label"), "Forgot your password?", "Forgot? keeps its full accessible name")

    page.locator(f"{case} #s-email").focus()
    order = [active(page)]
    for _ in range(4):
        tab(page, c)
        order.append(active(page))
    c.eq(order, ["s-email", "s-password", "Show password", "Forgot your password?", "Sign in"],
         "tab order is Email, Password, (show), Forgot, Sign in")

    # reset 747:173: the word Show, 12.5/500, ends 16px from the field's edge; errors begin with a cross
    case = '[data-case="reset-fields"]'
    tog = style(page, f"{case} #r-new ~ .password-toggle", ["font-size", "font-weight", "color"])
    inp = style(page, f"{case} #r-new", ["padding-right"])
    c.eq(tog["text"], "Show", "the toggle draws the word Show")
    c.eq((tog["font-size"], tog["font-weight"], tog["color"]), ("12.5px", "500", SECONDARY), "Show is 12.5px/500 in the secondary ink")
    c.near(tog["h"], 44, 0.5, "the toggle's hit area is 44px tall (handoff 12)")
    text_right = page.evaluate(
        """sel => { const s = document.querySelector(sel); const r = document.createRange(); r.selectNodeContents(s);
          return r.getBoundingClientRect().right; }""",
        f"{case} #r-new ~ .password-toggle .reveal-text",
    )
    c.near(inp["right"] - text_right, 16, 1.5, "Show ends 16px from the field's edge (Figma)")
    c.eq(inp["padding-right"], "64px", "the field leaves room, so a long password never runs under Show")
    btn = page.locator(f"{case} #r-new ~ .password-toggle")
    c.eq((btn.get_attribute("aria-label"), btn.get_attribute("aria-pressed")), ("Show password", "false"), "toggle keeps its accessible name and pressed state")
    btn.click()
    c.eq(btn.inner_text().strip(), "Hide", "clicking draws Hide")
    c.eq(btn.get_attribute("aria-pressed"), "true", "aria-pressed follows")
    c.eq(page.locator(f"{case} #r-new").get_attribute("type"), "text", "the password is revealed")
    c.eq(btn.get_attribute("aria-label"), "Hide password", "the name says what the next press does")
    btn.click()
    c.eq(page.locator(f"{case} #r-new").get_attribute("type"), "password", "and hidden again")

    err = style(page, f"{case} #r-new-error", ["font-size", "font-weight", "line-height", "color"])
    c.ok(err["text"].startswith("✕ Password must be at least 10 characters."), "the error begins with the visible cross, then the message")
    c.eq((err["font-size"], err["font-weight"], err["line-height"]), ("12.5px", "500", "17px"), "error is 12.5px/500 on a 17px line")
    c.eq(err["color"], LIVE, "error ink is the live red")
    c.near(err["x"], style(page, f"{case} #r-new")["x"], 1.0, "the message starts flush with the field's edge (Figma x=541)")
    c.eq(page.locator(f"{case} #r-new-error").get_attribute("role"), "alert", "the error is still an alert")
    c.eq(page.locator(f"{case} #r-new-error .error-glyph").get_attribute("aria-hidden"), "true", "the glyph is hidden from screen readers")
    c.eq(page.locator(f"{case} #r-new-error svg").count(), 0, "no icon beside the cross")


def open_dialog(page, opener: str) -> None:
    # By keyboard: focus the opener, press Enter. A mouse click would not focus a button in Safari,
    # so there would be nothing to return focus to; the keyboard path is also the one that matters.
    page.locator(opener).focus()
    page.keyboard.press("Enter")
    page.wait_for_selector(".dialog-card")
    settle(page)
    page.wait_for_timeout(60)  # nextTick focus, after the Transition has inserted the card


def check_dialogs(page, c: Checks, shots: Path | None) -> None:
    # ---- the existing centred dialog: same look, now with modal behaviour
    open_dialog(page, "#open-centered")
    card = style(page, ".dialog-card", ["max-width", "text-align"])
    c.eq(card["max-width"], "440px", "default dialog is still 440px")
    c.eq(card["text-align"], "center", "default dialog is still centred")
    c.eq(active(page), "Keep active", "initial focus is the safe action (Cancel)")
    c.eq(page.evaluate("getComputedStyle(document.body).overflow"), "hidden", "page scroll is locked while open")
    labelled = page.evaluate("""() => { const d = document.querySelector('.dialog-card');
      return [document.getElementById(d.getAttribute('aria-labelledby'))?.innerText, document.getElementById(d.getAttribute('aria-describedby'))?.innerText]; }""")
    c.eq(labelled[0], "Deactivate this device?", "aria-labelledby is the title")
    c.ok(labelled[1] and labelled[1].startswith("Are you sure"), "aria-describedby is the description")

    seq = [active(page)]
    for _ in range(3):
        tab(page, c)
        seq.append(active(page))
    c.eq(seq, ["Keep active", "Deactivate", "Keep active", "Deactivate"], "Tab is trapped: it cycles Cancel, Confirm, Cancel")
    tab(page, c, shift=True)
    tab(page, c, shift=True)
    c.eq(active(page), "Deactivate", "Shift+Tab from Cancel wraps to Confirm")
    page.evaluate("document.querySelector('#open-left').focus()")
    page.wait_for_timeout(30)
    c.ok(page.evaluate("document.querySelector('.dialog-card').contains(document.activeElement)"), "focus pushed outside the dialog is brought back in")
    page.keyboard.press("Escape")
    page.wait_for_selector(".dialog-card", state="detached")
    c.eq(page.locator("#last-event").inner_text(), "cancel", "Escape is Cancel")
    c.eq(page.evaluate("document.activeElement.id"), "open-centered", "focus returns to what opened the dialog")
    c.ok(page.evaluate("getComputedStyle(document.body).overflow") != "hidden", "page scroll is released on close")

    # scrim click cancels and returns focus too
    open_dialog(page, "#open-centered")
    page.mouse.click(8, 8)
    page.wait_for_selector(".dialog-card", state="detached")
    c.eq(page.evaluate("document.activeElement.id"), "open-centered", "closing by the scrim also returns focus")

    # ---- type-to-confirm: Cancel still takes the first focus
    open_dialog(page, "#open-type")
    c.eq(active(page), "Keep my plan", "type-to-confirm: initial focus is still Cancel, not the field")
    tab(page, c)
    c.eq(page.evaluate("document.activeElement.tagName"), "INPUT", "Tab from Cancel wraps to the field (Confirm is disabled)")
    page.keyboard.type("cancel")
    tab(page, c)
    tab(page, c)
    c.eq(active(page), "Cancel subscription", "once typed, Confirm joins the cycle")
    page.keyboard.press("Enter")
    page.wait_for_selector(".dialog-card", state="detached")
    c.eq(page.locator("#last-event").inner_text(), "confirm", "Enter on Confirm confirms")
    c.eq(page.evaluate("document.activeElement.id"), "open-type", "focus returns after a confirm as well")

    # ---- the devices confirm (D2 754:242)
    open_dialog(page, "#open-left")
    if shots:
        page.screenshot(path=str(shots / "dialog-left-1440.png"))
    dlg = style(page, ".dialog-card", ["padding-top", "padding-right", "padding-bottom", "padding-left", "background-color",
                                        "border-top-width", "border-top-color", "border-radius", "text-align", "row-gap"])
    c.near(dlg["w"], 420, 0.5, "devices dialog is 420 wide (Figma 420)")
    c.eq((dlg["padding-top"], dlg["padding-right"], dlg["padding-bottom"], dlg["padding-left"]), ("28px", "28px", "24px", "28px"), "padding 28/28/24/28")
    c.eq(dlg["background-color"], ELEVATED, "fill is --sc-elevated")
    c.eq((dlg["border-top-width"], dlg["border-top-color"], dlg["border-radius"]), ("1px", BORDER, "16px"), "1px --sc-border, radius 16")
    c.eq(dlg["text-align"], "left", "left-aligned")
    c.eq(dlg["row-gap"], "16px", "16px between blocks")
    scrim = style(page, ".dialog-scrim", ["background-color", "backdrop-filter"])
    c.eq(scrim["background-color"], "rgba(11, 13, 18, 0.72)", "scrim is --sc-base at 72%")
    c.ok(scrim["backdrop-filter"] in ("none", ""), "no blur (none is drawn)")
    c.eq(active(page), "Keep active", "devices dialog: initial focus is Keep active")

    g = style(page, ".dialog-glyph", ["font-size", "font-weight", "color"])
    c.eq((g["text"], g["font-size"], g["font-weight"], g["color"]), ("!", "30px", "700", WARN), "the bare ! is 30/700 in the warn tone")
    c.eq(page.locator(".dialog-icon-wrapper").count(), 0, "no disc")
    title = style(page, ".dialog-title", ["font-size", "font-weight"])
    c.eq((title["font-size"], title["font-weight"]), ("18px", "600"), "title 18/600")
    desc = style(page, ".dialog-desc", ["font-size", "line-height", "color"])
    c.eq((desc["font-size"], desc["line-height"], desc["color"]), ("14px", "20px", SECONDARY), "body 14/20 in the secondary ink")
    banner = style(page, ".dialog-banner")
    actions = style(page, ".dialog-actions")
    hint = style(page, ".dialog-hint", ["font-size", "color"])
    c.near(title["y"] - g["bottom"], 16, 1.0, "16px from the ! to the title")
    c.near(desc["y"] - title["bottom"], 16, 1.0, "16px from the title to the text")
    c.near(banner["y"] - desc["bottom"], 16, 1.0, "16px from the text to the banner")
    c.near(actions["y"] - banner["bottom"], 16, 1.0, "16px from the banner to the buttons")
    c.near(hint["y"] - actions["bottom"], 16, 1.0, "16px from the buttons to the hint")
    c.eq((hint["text"], hint["font-size"], hint["color"]), ("Esc keeps the device active.", "12px", SECONDARY), "hint 12px in the secondary ink")
    c.ok(page.locator(".dialog-banner [data-probe='banner']").count() == 1, "the banner slot content is rendered")

    cancel = style(page, ".dialog-cancel", ["border-top-width", "border-top-color", "border-radius", "background-color", "font-size", "font-weight", "color"])
    confirm = style(page, ".confirm-btn", ["border-radius", "background-color", "color", "font-size", "font-weight"])
    c.near(cancel["w"], 177, 1.0, "Cancel is 177 wide (Figma 177)")
    c.near(confirm["w"], 177, 1.0, "Confirm is 177 wide (Figma 177)")
    c.near(cancel["h"], 44, 0.5, "buttons are 44 tall (drawn 41; every target is held to 44)")
    # 1.5px computes to 1px at a device pixel ratio of 1 (a border is snapped to whole device pixels)
    c.ok(cancel["border-top-width"] in ("1px", "1.5px") and cancel["border-top-color"] == PRIMARY and cancel["border-radius"] == "10px",
         f"Cancel: 1.5px brand ring, radius 10 (got {cancel['border-top-width']}, {cancel['border-top-color']}, {cancel['border-radius']})")
    c.eq(cancel["background-color"], "rgba(0, 0, 0, 0)", "Cancel is transparent")
    c.eq((confirm["border-radius"], confirm["background-color"]), ("10px", LIVE), "Confirm: radius 10 on the live fill")
    c.eq((confirm["font-size"], confirm["font-weight"]), ("14px", "600"), "buttons 14/600")
    ratio = contrast(page, confirm["color"], confirm["background-color"])
    c.ok(ratio >= 4.5, f"Confirm label contrast on the live red is {ratio:.2f}:1 (AA needs 4.5; Figma's white is 3.3)")
    c.eq(confirm["color"], BASE, "Confirm label is the accessible dark ink until Uma picks one (D, account-31)")
    page.keyboard.press("Escape")
    page.wait_for_selector(".dialog-card", state="detached")
    c.eq(page.evaluate("document.activeElement.id"), "open-left", "devices dialog returns focus on Escape")


def check_narrow(browser, base: str, c: Checks, shots: Path | None) -> None:
    ctx = browser.new_context(viewport={"width": 375, "height": 800}, has_touch=True)
    page = ctx.new_page()
    page.goto(f"{base}/index.html", wait_until="load")
    page.wait_for_selector('[data-case="dialogs"]')
    open_dialog(page, "#open-left")
    dlg = style(page, ".dialog-card")
    c.ok(dlg["x"] >= 0 and dlg["right"] <= 375 and dlg["bottom"] <= 800, "375px: the devices dialog is fully on screen")
    cancel, confirm = style(page, ".dialog-cancel"), style(page, ".confirm-btn")
    c.ok(cancel["h"] >= 43.5 and confirm["h"] >= 43.5, "375px: both buttons are at least 44px tall")
    c.ok(confirm["y"] < cancel["y"], "375px: the buttons stack, the safe action last in the DOM and lowest on screen")
    c.near(confirm["w"], dlg["w"] - 40 - 2, 1.5, "375px: stacked buttons take the card's inner width")
    c.eq(page.evaluate("(() => { const s = document.querySelector('.dialog-scrim'); return s.scrollWidth <= s.clientWidth; })()"), True, "375px: the dialog does not overflow its scrim")
    if shots:
        page.screenshot(path=str(shots / "dialog-left-375.png"))
    page.keyboard.press("Escape")
    ctx.close()


def snapshot_defaults(page) -> dict:
    """Computed styles of everything that existed BEFORE this ticket: the default fields and the two default dialogs."""
    out: dict[str, object] = {"fields": page.evaluate(SNAPSHOT_JS, '[data-case="defaults"]')}
    for name, opener in (("dialog-default", "#open-centered"), ("dialog-type", "#open-type")):
        open_dialog(page, opener)
        page.evaluate("document.activeElement && document.activeElement.blur()")  # focus ring is not part of the look
        out[name] = page.evaluate(SNAPSHOT_JS, ".dialog-scrim")
        page.mouse.click(8, 8)
        page.wait_for_selector(".dialog-card", state="detached")
    return out


def diff_defaults(got: dict, want: dict) -> list[str]:
    problems: list[str] = []
    for key in sorted(set(got) | set(want)):
        a, b = got.get(key), want.get(key)
        if not isinstance(a, list) or not isinstance(b, list):
            problems.append(f"{key}: missing on one side")
            continue
        if len(a) != len(b):
            problems.append(f"{key}: {len(a)} elements now, {len(b)} in the recording")
            continue
        for i, (x, y) in enumerate(zip(a, b)):
            for prop in sorted(set(x) | set(y)):
                if x.get(prop) != y.get(prop):
                    problems.append(f"{key}[{i}] <{x.get('tag')}> {prop}: now {x.get(prop)!r}, was {y.get(prop)!r}")
    return problems


# ------------------------------------------------------------------------------------------- driver


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D401, ANN002
        return


def build_gallery(gallery_src: str | None) -> int:
    env = dict(os.environ)
    if gallery_src:
        env["GALLERY_SRC"] = gallery_src
    npx = "npx"
    proc = subprocess.run([npx, "vite", "build", "--config", str(GALLERY_CONFIG)], cwd=MARKETING, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2000:], proc.stderr[-2000:])
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["chromium", "webkit", "both"], default="chromium")
    ap.add_argument("--shots", help="directory for screenshots of the devices dialog (1440 and 375)")
    ap.add_argument("--gallery-src", help="build the gallery against this src directory instead of ./src")
    ap.add_argument("--dump-defaults", help="record the default-look computed styles to this file, then exit")
    ap.add_argument("--compare-defaults", help="diff the default-look computed styles against this recording")
    ap.add_argument("--no-build", action="store_true", help="reuse node_modules/.tmp/gallery")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return skip_or_fail("Playwright not installed (pip install playwright && playwright install chromium webkit)")

    out_dir = Path(os.environ.get("GALLERY_OUT") or (MARKETING / "node_modules" / ".tmp" / "gallery"))
    if not args.no_build:
        if build_gallery(args.gallery_src) != 0:
            print("INFRA: the gallery did not build")
            return 2
    if not (out_dir / "index.html").exists():
        print(f"INFRA: {out_dir}/index.html missing")
        return 2

    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    handler = functools.partial(QuietHandler, directory=str(out_dir))
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    engines = ["chromium", "webkit"] if args.engine == "both" else [args.engine]
    all_failures: list[str] = []
    total = 0
    try:
        with sync_playwright() as pw:
            for engine in engines:
                try:
                    browser = getattr(pw, engine).launch()
                except Exception as exc:  # noqa: BLE001 -- any launch failure is "engine unavailable"
                    return skip_or_fail(f"{engine} could not launch ({str(exc).splitlines()[0]})")
                c = Checks(engine)
                ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = ctx.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                page.goto(f"{base}/index.html", wait_until="load")
                page.wait_for_selector('[data-case="pricing"] .pricing-card')
                if not page.evaluate("document.fonts.check('600 16px Inter')"):
                    page.evaluate("document.fonts.load('600 16px Inter')")
                    page.wait_for_timeout(1500)
                if not page.evaluate("document.fonts.check('600 16px Inter')"):
                    print(f"NOTE [{engine}]: Inter did not load (no network?); text-width-dependent numbers may drift")
                settle(page)

                if args.dump_defaults:
                    Path(args.dump_defaults).write_text(json.dumps(snapshot_defaults(page), indent=1))
                    print(f"recorded the default look to {args.dump_defaults}")
                    browser.close()
                    return 0

                if args.compare_defaults:
                    want = json.loads(Path(args.compare_defaults).read_text())
                    problems = diff_defaults(snapshot_defaults(page), want)
                    c.ok(not problems, f"the default look changed in {len(problems)} computed values")
                    c.failures.extend(f"[{engine}]   {p}" for p in problems[:40])
                    elements = sum(len(v) for v in want.values() if isinstance(v, list))
                    print(f"[{engine}] compared {elements} elements' computed styles against the recording")
                else:
                    for fn in (check_badges, check_faq, check_pricing, check_formfield):
                        try:
                            fn(page, c)
                        except Exception as exc:  # noqa: BLE001 -- an aborted check is a failure, not a crash
                            c.failures.append(f"[{engine}] {fn.__name__} aborted: {str(exc).splitlines()[0][:240]}")
                    try:
                        check_dialogs(page, c, shots if engine == engines[0] else None)
                        check_narrow(browser, base, c, shots if engine == engines[0] else None)
                    except Exception as exc:  # noqa: BLE001
                        c.failures.append(f"[{engine}] dialogs aborted: {str(exc).splitlines()[0][:240]}")
                    c.ok(not errors, f"page errors: {errors[:3]}")

                total += c.count
                all_failures.extend(c.failures)
                print(f"[{engine}] {c.count} checks, {len(c.failures)} failure line(s)")
                browser.close()
    finally:
        server.shutdown()

    for f in all_failures:
        print("FAIL " + f)
    print(f"=== shared components [{'+'.join(engines)}]: {total} checks, {len(all_failures)} failure line(s) ===")
    return 1 if all_failures else 0


if __name__ == "__main__":
    sys.exit(main())
