#!/usr/bin/env python3
"""WebKit-engine boot smoke for the SelahCue operator webview (audit #10).

The committed behavioural gate (`operator_headless.py`) drives Blink (headless Chrome).
Tauri actually ships on WebKit — WebKitGTK (Linux) / WKWebView (macOS). This loads the
real `dist/` under Playwright's WebKit (JavaScriptCore/WebCore, the same core Tauri uses)
and asserts the app BOOTS without a JS error and the console-render path runs — catching an
engine-specific JS/API break the Blink gate cannot. A minimal boot smoke, not the full
66-check port (that stays on the fast Chrome gate).

Runs on macOS (dev) + Linux (CI). If Playwright/WebKit is unavailable this exits 0 with a
LOUD skip UNLESS SELAHCUE_WEBKIT_REQUIRE=1 (set in CI), which turns a missing engine into a
hard failure so the gate can never silently no-op. SELAHCUE_OPERATOR_DIST overrides the
webview path (e.g. a mutated copy in a test).
"""
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.environ.get("SELAHCUE_OPERATOR_DIST") or os.path.join(
    _REPO, "implementation", "desktop", "crates", "selahcue-operator", "dist"
)
REQUIRE = os.environ.get("SELAHCUE_WEBKIT_REQUIRE") == "1"

def skip_or_fail(msg):
    """A missing WebKit engine is a hard fail under REQUIRE (CI), else a loud dev-box skip."""
    if REQUIRE:
        print("FAIL: SELAHCUE_WEBKIT_REQUIRE=1 but " + msg)
        sys.exit(3)
    print("=" * 68)
    print("!! WEBKIT SMOKE SKIPPED — " + msg)
    print("!! (CI runs it with SELAHCUE_WEBKIT_REQUIRE=1)")
    print("=" * 68)
    sys.exit(0)


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    skip_or_fail("Playwright not installed (pip install playwright && playwright install webkit)")


def _realistic_transcript_segments(count):
    """A deterministic, mixed character-length segment list approximating real speech (performance
    review, Vera V-1/V-2): ~10% short 8-30 char utterances, ~70% medium 40-140, ~15% long 140-260,
    ~5% very long 260-420 "utterance-level final" segments — the same distribution and generator
    shape `scripts/operator_headless.py`'s own realistic fixture uses, so both engines exercise the
    same regime. No randomness, so a run reproduces identically."""
    filler = (
        "the quick brown fox jumps over the lazy dog near the riverbank at dawn while "
        "the choir softly hums an old familiar hymn before the sermon begins "
    )
    segs = []
    for i in range(count):
        m = i % 20
        if m < 2:
            length = 8 + (i % 23)
        elif m < 16:
            length = 40 + (i % 101)
        elif m < 19:
            length = 140 + (i % 121)
        else:
            length = 260 + (i % 161)
        text = "Segment " + str(i) + ": "
        while len(text) < length:
            text += filler
        segs.append({"id": 20000 + i, "start_ms": i * 3000, "end_ms": i * 3000 + 2500, "text": text[:length]})
    return segs


# Realistic-width/content-size control (performance review, Vera V-1/V-2): a 1520x984 REAL
# viewport (the operator's own default, tauri.conf.json) with a realistic mixed-length transcript
# is where Vera measured the estimate-only virtualizer failing (blank scroll frames, unreachable
# last segment) — this is what makes a real-WebKit run exercise that regime rather than only the
# small, uniform-text fixture the boot-smoke checks below already use.
REALISTIC_SEGMENT_COUNT = 1200
REALISTIC_SEGMENTS = _realistic_transcript_segments(REALISTIC_SEGMENT_COUNT)
REALISTIC_LAST_SEG_ID = REALISTIC_SEGMENTS[-1]["id"]

# The same __TAURI__ stub the Chrome harness uses, so app.js boots + the render path runs.
STUB = r"""
window.__calls = [];
var V = { plan_name:"Svc", items:[{id:1,kind:"scripture",title:"Genesis 1:13",is_live:true,is_staged:true}],
  live_index:0, staged_index:0, blackout:false, timer:null, staged_scripture:"Genesis 1:13",
  live_scripture:"Genesis 1:13", live_free_text:null, outputs:[], displays:[], translations:["KJV"],
  theme:"classic", themes:["classic"], saved_themes:[], screen_themes:[] };
var T = { background:{r:8,g:10,b:20,a:255},
  title:{x_permille:60,y_permille:150,w_permille:880,h_permille:110,align_h:"center",align_v:"middle",size_permille:48,line_height_permille:1200,color:{r:242,g:181,b:60,a:255},fit:"shrink_to_fit",visible:true},
  body:{x_permille:60,y_permille:280,w_permille:880,h_permille:560,align_h:"center",align_v:"middle",size_permille:78,line_height_permille:1150,color:{r:255,g:255,b:255,a:255},fit:"shrink_to_fit",visible:true} };
window.__TAURI__ = { core: { invoke: function(cmd, args){
  window.__calls.push({cmd:cmd, args:args});
  if (cmd === "builtin_themes") return Promise.resolve([{name:"Classic", theme:JSON.parse(JSON.stringify(T))}]);
  if (cmd === "system_fonts") return Promise.resolve([]);
  if (cmd === "view") return Promise.resolve(JSON.parse(JSON.stringify(V)));
  if (cmd === "preview_theme") return Promise.resolve({rgba: btoa("\x00\x00\x00\xff"), w:1, h:1});
  if (cmd === "render_console") return Promise.resolve({available:true,
     preview:{w:2,h:1,rgba:btoa("\xff\x00\x00\xff\x00\xff\x00\xff")},
     live:{w:2,h:1,rgba:btoa("\x00\x00\xff\xff\xff\xff\x00\xff")}});
  if (cmd === "operator_state" || cmd === "state") return Promise.resolve({});
  // Transcripts (86akcffvt / FR-130 core slice): enough for a real-WebKit check that the
  // surface's flex layout + [hidden]-attribute toggling (list <-> detail) actually paints —
  // exactly the class of trap (flex collapse, an author `display` beating `[hidden]`) this
  // console has hit before on WKWebView specifically and never on Blink.
  // id:4 is the realistic-width/content-size fixture (performance review, Vera V-1/V-2) — a
  // second, independent entry alongside id:1's small fixture; the boot-smoke checks below still
  // pick the FIRST `.tr-card-open` (id:1), so adding this does not disturb them.
  if (cmd === "transcript_list") return Promise.resolve([
    {id:1, label:"Sunday Service", provider:"manual", started_at_ms:1722760800000, ended_at_ms:1722764460000, segment_count:1},
    {id:4, label:"Realistic Long Service", provider:"manual", started_at_ms:1728700000000, ended_at_ms:1728700000000 + __REALISTIC_SEGMENT_COUNT__ * 3000, segment_count:__REALISTIC_SEGMENT_COUNT__}
  ]);
  if (cmd === "transcript_get" && args && args.id === 4) return Promise.resolve({
    id:4, label:"Realistic Long Service", provider:"manual", started_at_ms:1728700000000, ended_at_ms:1728700000000 + __REALISTIC_SEGMENT_COUNT__ * 3000,
    notes_generated:false, segments: __REALISTIC_SEGMENTS_JSON__
  });
  if (cmd === "transcript_get") return Promise.resolve({
    id:1, label:"Sunday Service", provider:"manual", started_at_ms:1722760800000, ended_at_ms:1722764460000,
    notes_generated:false, segments:[{id:101, start_ms:0, end_ms:4000, text:"Good morning, church."}]
  });
  return Promise.resolve(null);
} } };
"""
STUB = (
    STUB.replace("__REALISTIC_SEGMENT_COUNT__", str(REALISTIC_SEGMENT_COUNT))
    .replace("__REALISTIC_SEGMENTS_JSON__", json.dumps(REALISTIC_SEGMENTS))
)

HAS_RENDER = (
    "() => { var s = document.querySelector('#preview-panel .surface');"
    " return !!(s && s.classList.contains('has-render')); }"
)


def main():
    errors = []
    with sync_playwright() as p:
        try:
            browser = p.webkit.launch()
        except Exception as e:  # noqa: BLE001 — the WebKit browser binary is not installed
            skip_or_fail(
                "WebKit browser not installed (run: playwright install webkit) — "
                + str(e).splitlines()[0]
            )
        page = browser.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(STUB)
        page.goto("file://" + os.path.join(DIST, "index.html"))
        # Poll (bounded) for the boot render to COMPLETE on WebKit.
        try:
            page.wait_for_function(HAS_RENDER, timeout=8000)
        except Exception as e:  # noqa: BLE001 — any wait failure is a boot failure
            errors.append("boot render never completed on WebKit: " + str(e).splitlines()[0])
        calls = page.evaluate("window.__calls ? window.__calls.map(c => c.cmd) : []")
        has_render = page.evaluate(HAS_RENDER)
        canvas_ok = page.evaluate(
            "() => { var c = document.getElementById('preview-canvas');"
            " return !!c && c.width === 2 && c.height === 1; }"
        )

        # Transcripts (86akcffvt): a real-WebKit check of the list <-> detail [hidden] toggle over
        # a flex layout — computed style, never `.hidden` alone (the documented WKWebView trap).
        tr_errors = []
        try:
            # The nav item lives in the app menu, closed by default (#app-menu { display: none }
            # until .open) — open it first, a real click, matching an actual WebKit user.
            page.click('#app-menu-btn')
            page.wait_for_selector('.nav-item[data-surface="transcripts"]', state="visible", timeout=8000)
            page.click('.nav-item[data-surface="transcripts"]')
            page.wait_for_function(
                "() => document.querySelectorAll('#tr-list .tr-card').length >= 1", timeout=8000
            )
            tr_list_visible = page.evaluate(
                "() => getComputedStyle(document.getElementById('tr-list-view')).display !== 'none'"
            )
            page.click('#tr-list .tr-card-open')
            page.wait_for_function(
                "() => document.getElementById('tr-detail-log').textContent.indexOf('Good morning') >= 0",
                timeout=8000,
            )
            tr_detail_visible = page.evaluate(
                "() => getComputedStyle(document.getElementById('tr-detail-view')).display !== 'none'"
            )
            tr_list_hidden_now = page.evaluate(
                "() => getComputedStyle(document.getElementById('tr-list-view')).display === 'none'"
            )
        except Exception as e:  # noqa: BLE001 — any failure here is itself the finding
            tr_errors.append(str(e).splitlines()[0])
            tr_list_visible = tr_detail_visible = tr_list_hidden_now = False

        # === Realistic-width/content-size regression control (performance review, Vera V-1/V-2):
        # a REAL 1520x984 viewport (the operator's own default window, tauri.conf.json) with a
        # realistic mixed-length transcript, driven by REAL WebKit input (a real mouse wheel, a
        # real "End" keypress) rather than the `__trScrollToFraction` test-hook shortcut — this is
        # the "real scroll path" the performance review specifically asked to verify on real
        # WebKit, which the Blink `operator_headless.py` gate structurally cannot: headless Chrome
        # under `--virtual-time-budget` drives no real `requestAnimationFrame` (Vera's own
        # finding), so that gate exercises the fix's MATH via its own test hooks while this one
        # exercises the full production onScroll -> rAF -> recomputeWindow path end to end.
        # Mutation-verified: reverting transcripts.js to its pre-fix estimate-only scrollTop
        # mapping turns tr_last_visible/tr_end_visible/tr_ratio_moved RED — see the ticket's
        # evidence for the recorded run.
        tr_real_errors = []
        tr_mid_visible = tr_ratio_moved = tr_last_visible = tr_end_visible = False
        try:
            page2 = browser.new_page(viewport={"width": 1520, "height": 984})
            page2.on("pageerror", lambda e: tr_real_errors.append(str(e)))
            page2.add_init_script(STUB)
            page2.goto("file://" + os.path.join(DIST, "index.html"))
            page2.wait_for_function(HAS_RENDER, timeout=8000)
            page2.click("#app-menu-btn")
            page2.wait_for_selector('.nav-item[data-surface="transcripts"]', state="visible", timeout=8000)
            page2.click('.nav-item[data-surface="transcripts"]')
            page2.wait_for_function(
                "() => document.querySelectorAll('#tr-list .tr-card').length >= 2", timeout=8000
            )
            page2.click('#tr-list .tr-card[data-id="4"] .tr-card-open')
            page2.wait_for_function(
                "() => !document.getElementById('tr-detail-view').hidden && "
                "document.getElementById('tr-detail-title').textContent.indexOf('Realistic Long Service') === 0",
                timeout=8000,
            )
            page2.wait_for_function(
                "() => window.__trRenderedRowCount && window.__trRenderedRowCount() > 0", timeout=8000
            )

            # Real trusted mouse-wheel steps over the log (page.mouse.wheel, not a dispatched
            # synthetic event) — confirms no blank frame partway through scrolling, the direct
            # measure of Vera's "median scroll frame <50% covered" finding, and that the
            # measured-height calibration ratio actually moved on a SECOND engine.
            page2.hover("#tr-detail-log")
            for _ in range(15):
                page2.mouse.wheel(0, 400)
                page2.wait_for_timeout(30)
            page2.wait_for_timeout(150)
            tr_mid_visible = page2.evaluate(
                "() => window.__trVisibleSegIds ? window.__trVisibleSegIds().length > 0 : false"
            )
            tr_ratio_moved = page2.evaluate(
                "() => window.__trAvgRatio ? Math.abs(window.__trAvgRatio() - 1) > 0.05 : false"
            )

            # Real "scroll to end" via a real trusted "End" keypress on the focused, natively
            # keyboard-scrollable log region (tabindex=0, NFR-019) — the real scroll path, not the
            # `__trScrollToFraction` test hook.
            page2.click("#tr-detail-log")
            page2.keyboard.press("End")
            page2.wait_for_timeout(300)
            tr_end_visible = page2.evaluate(
                "(id) => { var ids = window.__trVisibleSegIds ? window.__trVisibleSegIds() : [];"
                " return ids.indexOf(String(id)) !== -1; }",
                REALISTIC_LAST_SEG_ID,
            )
            tr_last_visible = page2.evaluate(
                "(id) => !!(window.__trRowFor && window.__trRowFor(id))", REALISTIC_LAST_SEG_ID
            )
            page2.close()
        except Exception as e:  # noqa: BLE001 — any failure here is itself the finding
            tr_real_errors.append(str(e).splitlines()[0])

        browser.close()

    checks = []
    checks.append((not errors, "no uncaught JS error on WebKit boot"
                   + (" — " + "; ".join(errors) if errors else "")))
    checks.append(("view" in calls, "boot poll ran on WebKit (view invoked)"))
    checks.append(("render_console" in calls, "console render path ran on WebKit (render_console invoked)"))
    checks.append((has_render, "preview panel reached has-render on WebKit"))
    checks.append((canvas_ok, "preview canvas drawn 2x1 on WebKit (base64 RGBA decode + putImageData work)"))
    checks.append((not tr_errors, "Transcripts: nav + list + detail exercised on WebKit with no exception"
                   + (" — " + "; ".join(tr_errors) if tr_errors else "")))
    checks.append((tr_list_visible, "Transcripts: the list view paints on WebKit (computed display, not just .hidden)"))
    checks.append((tr_detail_visible, "Transcripts: opening a transcript paints the flex-based detail view on WebKit (computed display)"))
    checks.append((tr_list_hidden_now, "Transcripts: the list view is actually display:none on WebKit once the detail view is showing — [hidden] wins over the flex display (the documented WKWebView trap)"))
    checks.append((not tr_real_errors, "Transcripts realistic-width: exercised on real WebKit at 1520x984 with real input, no exception"
                   + (" — " + "; ".join(tr_real_errors) if tr_real_errors else "")))
    checks.append((tr_mid_visible, "Transcripts realistic-width: after real mouse-wheel scrolling, at least one row is VISIBLE (not a blank frame — Vera V-1)"))
    checks.append((tr_ratio_moved, "Transcripts realistic-width: the height calibration ratio moved away from the un-measured default of 1 on real WebKit"))
    checks.append((tr_last_visible, "Transcripts realistic-width: a real 'End' keypress mounts the LAST segment of a realistic-width, realistic-length transcript"))
    checks.append((tr_end_visible, "Transcripts realistic-width: the last segment is actually VISIBLE after a real scroll-to-end (Vera V-1: previously 0/8 attempts) — the real scroll path, not a test hook"))

    for passed, msg in checks:
        print(("PASS" if passed else "FAIL") + ": " + msg)
    fails = sum(1 for passed, _ in checks if not passed)
    print("=== WebKit smoke: %d checks, %d FAIL ===" % (len(checks), fails))
    sys.exit(1 if fails else 0)


main()
