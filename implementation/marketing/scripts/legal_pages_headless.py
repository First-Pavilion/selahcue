#!/usr/bin/env python3
"""Real-browser check of the legal pages: /privacy and /terms.

Serves the REAL production bundle from `dist/` over a local HTTP server with SPA fallback
and drives it in headless Chrome (Playwright), at 320 / 375 / 768 / 1024 / 1440 px. It is
the counterpart to `tests/legal.test.ts`: that file pins the content pipeline and the
draft rule; this one proves the rendered page does what the pipeline says, in a real
layout engine.

Per page and width it asserts:
  * no horizontal scroll at page level (tables scroll inside their own container)
  * exactly one <h1>, and the document title is the page's
  * the draft banner is present and carries the required text
  * the highlighted placeholder chips equal the number of `{{...}}` the document holds
  * a robots `noindex` meta is present, and is GONE after navigating to a non-legal page
    (and survives a /privacy -> /terms navigation, where the new page is set up first)
  * the Contents sidebar: left of the text and sticky on desktop; stacked above the text
    and collapsed behind a toggle on a phone
  * every top-level section is in Contents, and a Contents click moves the URL hash,
    scrolls the section below the sticky navbar, and focuses it
  * a deep link (`/privacy#s-3-8`) loaded cold lands on that section below the navbar
  * scroll-spy marks the section being read
  * tables are named and have column and row headers; their scroll container is a focusable
    named region ONLY while the table overflows
  * rendered headings equal the typed content; Terms Part headings keep their dash; clause
    numbers are followed by a real space in the text a copy reads; the document's own banner
    notes are on the page; few landmarks, no unnamed aside
  * the skip link is clipped (inside the viewport at rest), visible on focus with >= 4.5:1
    contrast, and its target's first heading clears the navbar
  * anchors land ~88px below the top of the viewport (cold deep link, Contents click, a
    second click on the same entry, in-text link) WITH and WITHOUT a page-wide
    `scroll-padding-top` on html (what PR #135 adds): no double offset
  * observers: exactly one IntersectionObserver while a legal page is mounted, and every
    observer the page created is disconnected after leaving it
  * the browser console stays clean and no request fails

Expected counts and ids come from the real typed content (a `node` subprocess imports
`src/lib/legal/*`), never from a copy in this file.

Usage:
    npm run build && python3 scripts/legal_pages_headless.py [--shots DIR]

Chrome is resolved via CHROME_BIN, then Playwright's `chrome` channel, then Playwright's
bundled Chromium. If Playwright or a browser is absent this exits 0 with a loud SKIP unless
SELAHCUE_HEADLESS_REQUIRE=1, which turns it into a hard failure.

Exit codes:
    0  all checks passed (or skipped and not required)
    1  one or more checks FAILED
    2  infrastructure problem (no dist, node failed)
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETING = HERE.parent
DIST = Path(os.environ.get("SELAHCUE_MARKETING_DIST") or (MARKETING / "dist"))

WIDTHS = [(320, 800), (375, 812), (768, 1024), (1024, 800), (1440, 900)]
DESKTOP_MIN = 820  # the stacking breakpoint (handoff section 8)
NAVBAR_BOTTOM = 69  # sticky navbar: 68px + 1px border
DRAFT_NOTICE = "Draft, pending legal review. This page is not our final policy."

# The real values, from the real modules.
EXPECTATIONS_JS = r"""
import { privacyPolicy } from './src/lib/legal/privacy.generated.ts'
import { termsOfService } from './src/lib/legal/terms.generated.ts'
import { legalPageState, tableOfContents, legalTitle, allAnchorIds } from './src/lib/legal/document.ts'
const headingsOf = (doc) => {
  const out = [doc.title]
  if (doc.summary) out.push(doc.summary.title)
  for (const p of doc.parts) {
    if (p.label && p.title) out.push(`${p.label} — ${p.title}`)
    for (const s of p.sections) {
      out.push(`${s.number}. ${s.title}`)
      for (const c of s.children) out.push(`${c.number} ${c.title}`)
    }
  }
  return out
}
const out = {}
for (const [key, doc] of [['privacy', privacyPolicy], ['terms', termsOfService]]) {
  const s = legalPageState(doc)
  out[key] = {
    title: legalTitle(doc),
    h1: doc.title,
    draft: s.draft,
    noindex: s.noindex,
    placeholderCount: s.placeholderCount,
    tocIds: tableOfContents(doc).flatMap((g) => g.entries.map((e) => e.id)),
    anchorIds: allAnchorIds(doc),
    hasTables: key === 'privacy',
    headings: headingsOf(doc),
    hasParts: doc.parts.some((p) => p.label),
  }
}
console.log(JSON.stringify(out))
"""

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    if not ok:
        print(f"FAIL  {name}  {detail}")
    return bool(ok)


def expectations() -> dict:
    node = shutil.which("node") or "/opt/homebrew/bin/node"
    proc = subprocess.run(
        [node, "--input-type=module", "-e", EXPECTATIONS_JS],
        cwd=MARKETING,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        print("INFRA: node could not load the legal modules:\n" + proc.stderr)
        sys.exit(2)
    return json.loads(proc.stdout)


class SpaHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path != "/" and not (DIST / path.lstrip("/")).exists():
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, *args):  # quiet
        pass


def serve() -> tuple[socketserver.TCPServer, int]:
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SpaHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def launch(pw):
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin and os.path.exists(chrome_bin):
        return pw.chromium.launch(executable_path=chrome_bin, headless=True)
    try:
        return pw.chromium.launch(channel="chrome", headless=True)
    except Exception:
        return pw.chromium.launch(headless=True)


OBSERVER_TRACKER = """
(() => {
  const track = (name) => {
    const Native = window[name]
    if (!Native) return
    window.__obs = window.__obs || {}
    window.__obs[name] = { created: 0, live: new Set() }
    window[name] = class extends Native {
      constructor(...args) { super(...args); window.__obs[name].created++; window.__obs[name].live.add(this) }
      disconnect() { window.__obs[name].live.delete(this); return super.disconnect() }
    }
  }
  track('IntersectionObserver'); track('ResizeObserver')
})()
"""

# What PR #135 adds to the site: a page-wide scroll-padding-top on <html>. Injected before any
# page script so the legal pages are exercised next to it, not only on today's base.
PAGE_WIDE_SCROLL_PADDING = """
(() => {
  const add = () => { const s = document.createElement('style'); s.textContent = 'html { scroll-padding-top: 84px }'; (document.head || document.documentElement).appendChild(s) }
  if (document.head) add()
  else new MutationObserver((_, o) => { if (document.head) { add(); o.disconnect() } }).observe(document, { childList: true, subtree: true })
})()
"""


def new_page(browser, width: int, height: int, errors: list[str], scroll_padding: bool = False):
    ctx = browser.new_context(viewport={"width": width, "height": height})
    ctx.add_init_script(OBSERVER_TRACKER)
    if scroll_padding:
        ctx.add_init_script(PAGE_WIDE_SCROLL_PADDING)

    # Nothing outside localhost is fetched (the Google Fonts stylesheet is the only
    # external reference): fulfil it empty so a sandbox without network stays quiet and
    # a REAL request failure still shows.
    def handle(route):
        url = route.request.url
        if url.startswith("http://127.0.0.1"):
            return route.continue_()
        return route.fulfill(status=200, content_type="text/css", body="")

    ctx.route("**/*", handle)
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: errors.append(f"requestfailed: {r.url} {r.failure}"))
    return ctx, page


def hscroll(page) -> tuple[int, int]:
    return page.evaluate(
        "[Math.max(document.documentElement.scrollWidth, document.body.scrollWidth), document.documentElement.clientWidth]"
    )


def rect(page, selector: str) -> dict | None:
    return page.evaluate(
        """(sel) => { const e = document.querySelector(sel); if (!e) return null;
                      const r = e.getBoundingClientRect();
                      return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height}; }""",
        selector,
    )


def target_top(page, anchor_id: str) -> float | None:
    """Top of the visible thing an anchor stands for (the element after the zero-height span)."""
    return page.evaluate(
        """(id) => { const a = document.getElementById(id); const t = a && a.nextElementSibling;
                     return t ? t.getBoundingClientRect().top : null; }""",
        anchor_id,
    )


def live_observers(page) -> dict:
    return page.evaluate(
        "(() => { const o = window.__obs || {}; const r = {}; for (const k of Object.keys(o)) r[k] = [o[k].created, o[k].live.size]; return r })()"
    )


def luminance(rgb: str) -> float:
    import re as _re

    nums = [int(x) for x in _re.findall(r"\d+", rgb)[:3]]
    ch = []
    for v in nums:
        c = v / 255
        ch.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# The heading sits `--legal-anchor-offset` (68 navbar + 20 air = 88px) below the top edge.
ANCHOR_LOW, ANCHOR_HIGH = 82, 96


def stable_top(page, anchor_id: str, timeout_ms: int = 9000):
    """Where an anchor's target ends up once any (smooth) scroll has finished: read it until
    it stops moving, instead of guessing a delay that a loaded machine will outrun."""
    last = None
    same = 0
    waited = 0
    while waited < timeout_ms:
        t = target_top(page, anchor_id)
        if t is not None and last is not None and abs(t - last) < 0.5:
            same += 1
            if same >= 3:
                return t
        else:
            same = 0
        last = t
        page.wait_for_timeout(150)
        waited += 150
    return last


def wait_settled(page, ms: int = 900) -> None:
    page.wait_for_timeout(ms)  # smooth scroll + IntersectionObserver delivery


def run_page(browser, base: str, key: str, all_exp: dict, shots: Path | None, only: str = 'all', widths: list[int] | None = None) -> None:
    exp = all_exp[key]
    path = f"/{key}"
    sections = exp["tocIds"]
    for width, height in ([w for w in WIDTHS if widths is None or w[0] in widths] if only in ('all', 'pages') else []):
        tag = f"{key}@{width}"
        errors: list[str] = []
        ctx, page = new_page(browser, width, height, errors)
        page.goto(base + path, wait_until="networkidle")
        page.wait_for_selector("[data-legal-page]")
        desktop = width >= DESKTOP_MIN

        sw, cw = hscroll(page)
        check(f"{tag}: no horizontal scroll", sw <= cw, f"scrollWidth={sw} clientWidth={cw}")
        check(f"{tag}: exactly one h1", page.locator("h1").count() == 1, f"{page.locator('h1').count()}")
        check(f"{tag}: h1 is the document title", page.locator("h1").inner_text().strip() == exp["h1"])
        check(f"{tag}: document.title", page.title() == exp["title"], page.title())

        # draft treatment
        banner = page.locator("[data-draft-banner]")
        check(f"{tag}: draft banner present", banner.count() == 1)
        check(f"{tag}: banner says the page is not final", DRAFT_NOTICE in banner.inner_text(), banner.inner_text()[:120])
        chips = page.locator("[data-placeholder]").count()
        check(f"{tag}: placeholder chips == placeholders in the text", chips == exp["placeholderCount"], f"{chips} vs {exp['placeholderCount']}")
        chip_bg = page.evaluate("getComputedStyle(document.querySelector('[data-placeholder]')).backgroundColor")
        body_bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        check(f"{tag}: chips are visibly highlighted", chip_bg != body_bg and chip_bg != "rgba(0, 0, 0, 0)", f"{chip_bg} on {body_bg}")
        noindex = page.locator('meta[name="robots"][content="noindex"]').count()
        check(f"{tag}: noindex meta present (exactly one)", noindex == 1, f"{noindex}")

        # contents + layout
        links = page.locator(".toc-link")
        check(f"{tag}: every section is in Contents", links.count() == len(sections), f"{links.count()} vs {len(sections)}")
        missing = [s for s in sections if page.locator(f'[id="{s}"]').count() != 1]
        check(f"{tag}: every Contents target exists once", not missing, str(missing))

        toc = rect(page, ".toc")
        text = rect(page, "#legal-text")
        if desktop:
            check(f"{tag}: sidebar is left of the text", toc is not None and text is not None and toc["right"] <= text["left"] + 1, f"{toc} {text}")
            check(f"{tag}: Contents toggle hidden on desktop", not page.locator(".toc-toggle").is_visible())
            page.mouse.wheel(0, 1600)
            wait_settled(page, 400)
            toc2 = rect(page, ".toc")
            check(f"{tag}: sidebar is sticky below the navbar", toc2 is not None and NAVBAR_BOTTOM <= toc2["top"] <= 110, f"{toc2}")
            page.evaluate("window.scrollTo(0, 0)")
        else:
            check(f"{tag}: sidebar is stacked above the text", toc is not None and text is not None and toc["bottom"] <= text["top"] + 1, f"{toc} {text}")
            check(f"{tag}: Contents toggle visible on a phone", page.locator(".toc-toggle").is_visible())
            check(f"{tag}: Contents collapsed by default", not page.locator(".toc-list").is_visible())
            check(f"{tag}: toggle reports collapsed", page.locator(".toc-toggle").get_attribute("aria-expanded") == "false")
            page.locator(".toc-toggle").click()
            check(f"{tag}: toggle opens the list", page.locator(".toc-list").is_visible() and page.locator(".toc-toggle").get_attribute("aria-expanded") == "true")
            sw, cw = hscroll(page)
            check(f"{tag}: no horizontal scroll with Contents open", sw <= cw, f"{sw}/{cw}")
            page.locator(".toc-toggle").click()

        # tables: always named with headers; focusable named region ONLY while overflowing
        if exp["hasTables"]:
            tables = page.locator(".lt-table")
            check(f"{tag}: tables render", tables.count() >= 2, f"{tables.count()}")
            check(f"{tag}: every table is named and has column and row headers", page.evaluate(
                "[...document.querySelectorAll('.lt-table')].every(t => t.getAttribute('aria-label') && t.querySelectorAll('thead th[scope=col]').length > 0 && t.querySelectorAll('tbody th[scope=row]').length > 0)"))
            wait_settled(page, 300)
            rows = page.evaluate(
                """[...document.querySelectorAll('.lt-wrap')].map(w => ({
                     over: w.scrollWidth - w.clientWidth > 1,
                     role: w.getAttribute('role'), label: w.getAttribute('aria-label'), tab: w.getAttribute('tabindex')}))"""
            )
            ok = all((r["role"] == "region" and bool(r["label"]) and r["tab"] == "0") == r["over"]
                     and (r["over"] or (r["role"] is None and r["label"] is None and r["tab"] is None)) for r in rows)
            check(f"{tag}: a table wrapper is a focusable named region only while it overflows", ok, str(rows))
            if width <= 375:
                check(f"{tag}: on a phone the wide tables scroll inside their own container", all(r["over"] for r in rows), str(rows))
            if width >= 1440:
                check(f"{tag}: on a wide screen no table needs a tab stop", not any(r["over"] for r in rows), str(rows))

        # fidelity: rendered headings == typed content (Part headings keep their dash)
        headings = page.evaluate(
            "[document.querySelector('h1'), ...document.querySelectorAll('#legal-text h2, #legal-text h3')].map(h => h.innerText.replace(/\\s+/g, ' ').trim())"
        )
        # innerText applies CSS text-transform (Part headings are shown in capitals), so compare case-insensitively
        check(f"{tag}: rendered headings equal the typed content", [h.lower() for h in headings] == [h.lower() for h in exp["headings"]], f"{len(headings)} vs {len(exp['headings'])}: first diff {[(a, b) for a, b in zip(headings, exp['headings']) if a.lower() != b.lower()][:1]}")
        if exp["hasParts"]:
            check(f"{tag}: Part headings keep the dash", any(h.lower().startswith("part a — ") for h in headings), str(headings[:3]))
        clause = page.evaluate("(() => { const p = document.querySelector('.lb-clause'); return p ? p.innerText : '' })()")
        check(f"{tag}: a clause number is followed by a real space in the text", bool(__import__('re').match(r"^\d+\.\d+ \S", clause)), repr(clause[:30]))
        banner_text = page.locator("[data-draft-banner]").inner_text()
        check(f"{tag}: the document's own banner notes are on the page", "Status: Draft" in banner_text and "operates at launch" in banner_text, banner_text[:80])
        check(f"{tag}: no aside, one Contents nav, few named regions", page.locator("aside").count() == 0 and page.locator("nav[aria-label=Contents]").count() == 1 and page.locator("[aria-labelledby]").count() <= 3,
              f"aside={page.locator('aside').count()} labelled={page.locator('[aria-labelledby]').count()}")

        # skip link: clipped at rest (inside the viewport), visible on focus, readable
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")  # Playwright scrolled the page to click the phone Contents toggle
        rest = rect(page, ".skip-link")
        inside = rest is not None and rest["left"] >= 0 and rest["right"] <= width and rest["top"] >= 0
        check(f"{tag}: the skip link is inside the viewport at rest (clipped, not parked off-screen)", inside, str(rest))
        page.focus(".skip-link")
        on_focus = rect(page, ".skip-link")
        check(f"{tag}: the skip link is visible on focus", on_focus is not None and on_focus["width"] >= 100 and on_focus["height"] >= 20, str(on_focus))
        colors = page.evaluate("(() => { const s = getComputedStyle(document.querySelector('.skip-link')); return [s.color, s.backgroundColor] })()")
        ratio = contrast(colors[0], colors[1])
        check(f"{tag}: the focused skip link has >= 4.5:1 contrast", ratio >= 4.5, f"{ratio:.2f} {colors}")
        page.keyboard.press("Enter")
        wait_settled(page, 900)
        first = page.evaluate("(() => { const h = document.querySelector('#legal-text h2'); return h ? h.getBoundingClientRect().top : null })()")
        check(f"{tag}: after the skip link the first heading clears the navbar", first is not None and first >= NAVBAR_BOTTOM + 8, f"top={first}")
        check(f"{tag}: the skip link moves focus to the document text", page.evaluate("document.activeElement && document.activeElement.id") == "legal-text")
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")

        # deep link, cold load
        errors_cold: list[str] = []
        ctx2, page2 = new_page(browser, width, height, errors_cold)
        deep = exp["anchorIds"][len(exp["anchorIds"]) // 2]
        page2.goto(f"{base}{path}#{deep}", wait_until="networkidle")
        page2.wait_for_selector("[data-legal-page]")
        top = stable_top(page2, deep)
        check(f"{tag}: cold deep link #{deep} lands at ~88px (below the navbar, not under it, not double-offset)", top is not None and ANCHOR_LOW <= top <= ANCHOR_HIGH, f"top={top}")
        sw, cw = hscroll(page2)
        check(f"{tag}: no horizontal scroll after deep link", sw <= cw)
        check(f"{tag}: cold deep link console clean", not errors_cold, "; ".join(errors_cold[:3]))
        if shots and width in (375, 1440):
            page2.screenshot(path=str(shots / f"{key}-{width}-deeplink.png"))
        ctx2.close()

        # Contents click
        target = sections[len(sections) // 2]
        if not desktop:
            page.locator(".toc-toggle").click()
        page.locator(f'.toc-link[href="#{target}"]').click()
        wait_settled(page, 1400)
        check(f"{tag}: Contents click sets the URL hash", page.evaluate("location.hash") == f"#{target}", page.evaluate("location.hash"))
        top = stable_top(page, target)
        check(f"{tag}: Contents click lands the section at ~88px", top is not None and ANCHOR_LOW <= top <= ANCHOR_HIGH, f"top={top}")
        focused = page.evaluate("document.activeElement && document.activeElement.id")
        check(f"{tag}: Contents click focuses the section heading", focused == f"{target}-title", f"{focused}")
        if not desktop:
            check(f"{tag}: Contents collapses after a click", not page.locator(".toc-list").is_visible())
        active = page.locator(".toc-link.is-active")
        check(f"{tag}: scroll-spy marks the section being read", active.count() == 1 and active.get_attribute("href") == f"#{target}", f"{active.count()}")
        check(f"{tag}: active entry exposes aria-current", active.get_attribute("aria-current") == "location")

        # scroll-spy follows a scroll (not just a click)
        other = sections[2]
        # `instant`: the page sets `scroll-behavior: smooth`, and a smooth scroll that is
        # still in flight would make this a race against the machine's speed.
        page.evaluate(
            "(id) => { const a = document.getElementById(id); window.scrollTo({top: window.scrollY + a.getBoundingClientRect().top + 8, behavior: 'instant'}) }",
            other,
        )
        try:
            page.wait_for_function(
                "(h) => { const a = document.querySelector('.toc-link.is-active'); return a && a.getAttribute('href') === h }",
                arg=f"#{other}",
                timeout=4000,
            )
        except Exception:
            pass
        spy = page.locator(".toc-link.is-active").get_attribute("href")
        check(f"{tag}: scroll-spy follows plain scrolling", spy == f"#{other}", f"{spy} vs #{other}")

        # one in-text cross-reference
        ref = page.locator('#legal-text a[href^="#s-"]').first
        if ref.count():
            href = ref.get_attribute("href") or ""
            ref.scroll_into_view_if_needed()
            ref.click()
            rid = href[1:]
            top = stable_top(page, rid)
            check(f"{tag}: an in-text 'section N' link jumps to {rid} at ~88px", top is not None and ANCHOR_LOW <= top <= ANCHOR_HIGH, f"top={top}")

        if shots and width in (320, 375, 768, 1024, 1440):
            page.evaluate("window.scrollTo(0, 0)")
            wait_settled(page, 300)
            page.screenshot(path=str(shots / f"{key}-{width}-top.png"))
            page.screenshot(path=str(shots / f"{key}-{width}-full.png"), full_page=True) if width in (375, 1440) else None

        check(f"{tag}: console clean", not errors, "; ".join(errors[:3]))
        ctx.close()

    if only in ('all', 'nav'):
        run_navigation(browser, base, key, all_exp)


def run_navigation(browser, base: str, key: str, all_exp: dict) -> None:
    path = f"/{key}"
    # Navigation: noindex follows the page, including across Privacy -> Terms.
    errors = []
    ctx, page = new_page(browser, 1440, 900, errors)
    # Baseline: observers a NON-legal page (pricing) holds, so the legal page's own can be isolated.
    ctx_b, page_b = new_page(browser, 1440, 900, [])
    page_b.goto(base + "/pricing", wait_until="networkidle")
    page_b.wait_for_timeout(500)
    baseline = live_observers(page_b)
    ctx_b.close()
    page.goto(base + path, wait_until="networkidle")
    page.wait_for_selector("[data-legal-page]")
    page.wait_for_timeout(500)
    mounted = live_observers(page)
    d_io = mounted.get("IntersectionObserver", [0, 0])[1] - baseline.get("IntersectionObserver", [0, 0])[1]
    check(f"{key}: exactly one IntersectionObserver is live while the page is mounted", d_io == 1, f"delta={d_io} {mounted} vs {baseline}")
    default_title = None
    other_key = "terms" if key == "privacy" else "privacy"
    page.locator(f'footer a[href="/{other_key}"]').first.click()
    page.wait_for_selector("[data-legal-page]")
    page.wait_for_function(f"location.pathname === '/{other_key}'")
    page.wait_for_timeout(300)
    check(f"{key}->{other_key}: noindex survives the navigation", page.locator('meta[name="robots"][content="noindex"]').count() == 1, f"{page.locator('meta[name=robots]').count()}")
    check(f"{key}->{other_key}: title is the new page's", page.title() == all_exp[other_key]["title"], page.title())
    page.locator('footer a[href="/pricing"]').first.click()
    page.wait_for_function("location.pathname === '/pricing'")
    page.wait_for_timeout(300)
    check(f"{key}->pricing: noindex is removed on leaving the legal pages", page.locator('meta[name="robots"][data-legal-noindex]').count() == 0, f"{page.locator('meta[name=robots]').count()}")
    after = live_observers(page)
    leaked = {k: after[k][1] - baseline.get(k, [0, 0])[1] for k in after}
    check(f"{key}->pricing: every observer the legal pages created is disconnected after leaving", all(v == 0 for v in leaked.values()), f"{leaked} (after={after}, baseline={baseline})")
    default_title = page.title()
    check(f"{key}->pricing: title is no longer a legal title", all_exp["privacy"]["title"] not in default_title and all_exp["terms"]["title"] not in default_title, default_title)
    check(f"{key}: navigation console clean", not errors, "; ".join(errors[:3]))
    ctx.close()


def run_anchor_modes(browser, base: str, key: str, exp: dict) -> None:
    """Anchors land at ~88px next to a page-wide scroll-padding-top too (what PR #135 adds)."""
    sections = exp["tocIds"]
    for width, height in ((375, 812), (1440, 900)):
        tag = f"{key}@{width}+scroll-padding"
        errors: list[str] = []
        ctx, page = new_page(browser, width, height, errors, scroll_padding=True)
        page.goto(base + f"/{key}", wait_until="networkidle")
        page.wait_for_selector("[data-legal-page]")
        pad = page.evaluate("getComputedStyle(document.documentElement).scrollPaddingTop")
        check(f"{tag}: the page's own rule neutralises the injected html scroll-padding-top", pad in ("0px", "auto"), pad)
        ctx.close()

        ctx, page = new_page(browser, width, height, [], scroll_padding=True)
        deep = exp["anchorIds"][len(exp["anchorIds"]) // 2]
        page.goto(f"{base}/{key}#{deep}", wait_until="networkidle")
        page.wait_for_selector("[data-legal-page]")
        top = stable_top(page, deep)
        check(f"{tag}: cold deep link #{deep} lands at ~88px (no double offset)", top is not None and ANCHOR_LOW <= top <= ANCHOR_HIGH, f"top={top}")

        target = sections[len(sections) // 2]
        if width < DESKTOP_MIN:
            page.locator(".toc-toggle").click()
        page.locator(f'.toc-link[href="#{target}"]').click()
        top = stable_top(page, target)
        check(f"{tag}: Contents click lands at ~88px", top is not None and ANCHOR_LOW <= top <= ANCHOR_HIGH, f"top={top}")

        # a SECOND click on the same entry after scrolling away: the router will not navigate, so
        # the page scrolls itself; it must land in the same place
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        wait_settled(page, 300)
        if width < DESKTOP_MIN:
            page.locator(".toc-toggle").click()
        page.locator(f'.toc-link[href="#{target}"]').click()
        top = stable_top(page, target)
        check(f"{tag}: a second click on the same entry lands at ~88px", top is not None and ANCHOR_LOW <= top <= ANCHOR_HIGH, f"top={top}")

        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.focus(".skip-link")
        page.keyboard.press("Enter")
        wait_settled(page, 900)
        first = page.evaluate("(() => { const h = document.querySelector('#legal-text h2'); return h ? h.getBoundingClientRect().top : null })()")
        check(f"{tag}: the skip link lands the first heading below the navbar", first is not None and first >= NAVBAR_BOTTOM + 8, f"top={first}")
        check(f"{tag}: console clean", not errors, "; ".join(errors[:3]))
        ctx.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", type=Path, help="write screenshots into this directory")
    ap.add_argument("--widths", help="comma-separated subset of widths to run in the pages group (mutation proofs only)")
    ap.add_argument("--only", choices=["all", "pages", "anchors", "nav"], default="all", help="run one group of checks (all by default; a subset is for mutation proofs, never for CI)")
    args = ap.parse_args()

    if not (DIST / "index.html").exists():
        print(f"INFRA: {DIST}/index.html missing; run `npm run build` first")
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        msg = "playwright is not installed (pip install playwright)"
        if os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1":
            print("FAIL: " + msg)
            return 1
        print("SKIP: " + msg)
        return 0

    exp = expectations()
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    srv, port = serve()
    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as pw:
            try:
                browser = launch(pw)
            except Exception as e:  # no browser binary
                if os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1":
                    print(f"FAIL: could not launch Chrome: {e}")
                    return 1
                print(f"SKIP: could not launch Chrome: {e}")
                return 0
            for key in ("privacy", "terms"):
                run_page(browser, base, key, exp, args.shots, args.only, [int(w) for w in args.widths.split(',')] if args.widths else None)
                if args.only in ('all', 'anchors'):
                    run_anchor_modes(browser, base, key, exp[key])
            browser.close()
    finally:
        srv.shutdown()

    failed = [r for r in results if not r[1]]
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed, {len(results)} checks")
    if failed:
        for name, _, detail in failed:
            print(f"  FAIL {name}  {detail}")
        return 1
    print("PASS legal pages headless")
    return 0


if __name__ == "__main__":
    sys.exit(main())
