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


def _phased_transcript_segments(count, id_base):
    """Three back-to-back length regimes (short/long/medium thirds) — the same PHASED shape
    `scripts/operator_headless.py`'s own "TR regime-change" fixture uses. A fresh jump anywhere in
    a fixture that interleaves lengths evenly lands near whatever average ratio the calibration
    already learned near the top, which is exactly why V-6 never showed up on the evenly-mixed
    `_realistic_transcript_segments` fixture above. A regime-change fixture is what's needed to
    force `avgRatio` to move meaningfully mid-transcript — the precondition this round's Home/End
    race (QA finding) and V-10 (PageDown/PageUp/Space) both need to reproduce."""
    filler = (
        "the quick brown fox jumps over the lazy dog near the riverbank at dawn while "
        "the choir softly hums an old familiar hymn before the sermon begins "
    )
    third = count // 3
    segs = []
    for i in range(count):
        if i < third:
            length = 8 + (i % 23)
        elif i < 2 * third:
            length = 260 + (i % 161)
        else:
            length = 40 + (i % 101)
        text = "Segment " + str(i) + ": "
        while len(text) < length:
            text += filler
        segs.append({"id": id_base + i, "start_ms": i * 3000, "end_ms": i * 3000 + 2500, "text": text[:length]})
    return segs


PHASED_SEGMENT_COUNT = 3000
PHASED_SEGMENTS = _phased_transcript_segments(PHASED_SEGMENT_COUNT, 40000)
PHASED_FIRST_SEG_ID = PHASED_SEGMENTS[0]["id"]
PHASED_LAST_SEG_ID = PHASED_SEGMENTS[-1]["id"]

# Uniform-LONG fixture for V-11 (a tail-pin render that GROWS the ratio): every segment is long
# enough that narrowing `#tr-detail-view` (done in the V-11 check below) makes the real wrapped
# line count exceed the 88-chars/line estimate everywhere, so `avgRatio` moves away from its
# un-measured default of 1 the very first time ANY row is measured — including a tail-pin render
# reached on a fresh open with no prior scrolling, which is exactly the precondition V-11 needs.
def _uniform_long_segments(count, id_base, length):
    filler = (
        "the quick brown fox jumps over the lazy dog near the riverbank at dawn while "
        "the choir softly hums an old familiar hymn before the sermon begins "
    )
    segs = []
    for i in range(count):
        text = "Segment " + str(i) + ": "
        while len(text) < length:
            text += filler
        segs.append({"id": id_base + i, "start_ms": i * 3000, "end_ms": i * 3000 + 2500, "text": text[:length]})
    return segs


UNIFORM_LONG_COUNT = 400
UNIFORM_LONG_SEGMENTS = _uniform_long_segments(UNIFORM_LONG_COUNT, 50000, 300)
UNIFORM_LONG_LAST_SEG_ID = UNIFORM_LONG_SEGMENTS[-1]["id"]

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
  // id:5 is the PHASED (regime-change) fixture and id:6 the uniform-LONG/narrow-column fixture,
  // both added this round for the Home/End race, V-10 and V-11 checks below — see their own
  // comments for why an evenly-mixed fixture cannot exercise those.
  if (cmd === "transcript_list") return Promise.resolve([
    {id:1, label:"Sunday Service", provider:"manual", started_at_ms:1722760800000, ended_at_ms:1722764460000, segment_count:1},
    {id:4, label:"Realistic Long Service", provider:"manual", started_at_ms:1728700000000, ended_at_ms:1728700000000 + __REALISTIC_SEGMENT_COUNT__ * 3000, segment_count:__REALISTIC_SEGMENT_COUNT__},
    {id:5, label:"Regime Change Service", provider:"manual", started_at_ms:1730000000000, ended_at_ms:1730000000000 + __PHASED_SEGMENT_COUNT__ * 3000, segment_count:__PHASED_SEGMENT_COUNT__},
    {id:6, label:"Uniform Long Service", provider:"manual", started_at_ms:1731000000000, ended_at_ms:1731000000000 + __UNIFORM_LONG_COUNT__ * 3000, segment_count:__UNIFORM_LONG_COUNT__}
  ]);
  if (cmd === "transcript_get" && args && args.id === 4) return Promise.resolve({
    id:4, label:"Realistic Long Service", provider:"manual", started_at_ms:1728700000000, ended_at_ms:1728700000000 + __REALISTIC_SEGMENT_COUNT__ * 3000,
    notes_generated:false, segments: __REALISTIC_SEGMENTS_JSON__
  });
  if (cmd === "transcript_get" && args && args.id === 5) return Promise.resolve({
    id:5, label:"Regime Change Service", provider:"manual", started_at_ms:1730000000000, ended_at_ms:1730000000000 + __PHASED_SEGMENT_COUNT__ * 3000,
    notes_generated:false, segments: __PHASED_SEGMENTS_JSON__
  });
  if (cmd === "transcript_get" && args && args.id === 6) return Promise.resolve({
    id:6, label:"Uniform Long Service", provider:"manual", started_at_ms:1731000000000, ended_at_ms:1731000000000 + __UNIFORM_LONG_COUNT__ * 3000,
    notes_generated:false, segments: __UNIFORM_LONG_SEGMENTS_JSON__
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
    .replace("__PHASED_SEGMENT_COUNT__", str(PHASED_SEGMENT_COUNT))
    .replace("__PHASED_SEGMENTS_JSON__", json.dumps(PHASED_SEGMENTS))
    .replace("__UNIFORM_LONG_COUNT__", str(UNIFORM_LONG_COUNT))
    .replace("__UNIFORM_LONG_SEGMENTS_JSON__", json.dumps(UNIFORM_LONG_SEGMENTS))
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
            # ADR-0026 D1: the global `avgRatio` scalar this check used to read is deleted —
            # replaced by an exact per-row Fenwick-tree metric with no single ratio to inspect.
            # `__trMeasuredCount` is the direct successor: "did real measurement actually happen".
            tr_ratio_moved = page2.evaluate(
                "() => window.__trMeasuredCount ? window.__trMeasuredCount() > 50 : false"
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

        # === Home/End reach the true edges natively (ADR-0026 rev 2): this block used to reproduce
        # a QA-found race between Home/End's own `jumpScrollTop` fix and the scroll-anchor
        # compensation it was built alongside — a manual jump's own scrollTop write fired a native
        # async 'scroll' event that scheduled a SECOND, independent recomputeWindow() next frame,
        # which could un-pin a render that had just correctly landed at the true start/end. Under
        # ADR-0026 D3 that entire apparatus (`jumpScrollTop`/`suppressCompensation`/the five-key
        # `keydown` handler) is deleted outright: Home/End now run their NATIVE default action, and
        # nothing in this file ever schedules a second, independent recompute off the back of its
        # own write — D2 means nothing writes scrollTop reactively in the first place, so the race
        # this block used to reproduce is unreachable by construction, not merely defended against.
        # What this block now proves is the positive claim ADR-0026's spike measured: a native
        # keyboard jump reaches the TRUE edge exactly, and the right content becomes visible, even
        # from deep in a length regime the D1 metric estimated wrong — i.e. native scroll anchoring
        # (D2) correctly settles the view, with no help from this file. Same setup as before
        # (calibrate deep in one length regime via REAL wheel scrolling, wheel back until the
        # mounted window overlaps the eventual target, then a single real trusted keypress) because
        # that is still the regime where a compensation bug would show up if D2 were ever silently
        # reintroduced.
        tr_kb_errors = []
        tr_home_landed = tr_home_visible = tr_end_landed = tr_end_visible2 = False
        try:
            page3 = browser.new_page(viewport={"width": 1520, "height": 984})
            page3.on("pageerror", lambda e: tr_kb_errors.append(str(e)))
            page3.add_init_script(STUB)
            page3.goto("file://" + os.path.join(DIST, "index.html"))
            page3.wait_for_function(HAS_RENDER, timeout=8000)
            page3.click("#app-menu-btn")
            page3.wait_for_selector('.nav-item[data-surface="transcripts"]', state="visible", timeout=8000)
            page3.click('.nav-item[data-surface="transcripts"]')
            page3.wait_for_function(
                "() => document.querySelectorAll('#tr-list .tr-card').length >= 3", timeout=8000
            )
            page3.click('#tr-list .tr-card[data-id="5"] .tr-card-open')
            page3.wait_for_function(
                "() => window.__trRenderedRowCount && window.__trRenderedRowCount() > 0", timeout=8000
            )
            page3.hover("#tr-detail-log")
            # Calibrate deep in the long-text middle third via real wheel scrolling.
            for _ in range(40):
                page3.mouse.wheel(0, 800)
                page3.wait_for_timeout(15)
            page3.wait_for_timeout(100)

            # --- Home: real wheel back up until the mounted window overlaps [0, 150).
            for _ in range(400):
                page3.mouse.wheel(0, -120)
                page3.wait_for_timeout(12)
                b = page3.evaluate("() => window.__trWindowBounds()")
                if b["start"] < 150:
                    break
            page3.click("#tr-detail-log")
            page3.keyboard.press("Home")
            page3.wait_for_timeout(300)
            tr_home_landed = page3.evaluate(
                "() => document.getElementById('tr-detail-log').scrollTop"
            ) == 0
            home_visible = page3.evaluate("() => window.__trVisibleSegIds()")
            tr_home_visible = str(PHASED_FIRST_SEG_ID) in (home_visible or [])

            # --- End: real wheel back down until the mounted window overlaps the tail.
            for _ in range(400):
                page3.mouse.wheel(0, 120)
                page3.wait_for_timeout(12)
                b = page3.evaluate("() => window.__trWindowBounds()")
                if b["end"] > PHASED_SEGMENT_COUNT - 150:
                    break
            page3.click("#tr-detail-log")
            page3.keyboard.press("End")
            page3.wait_for_timeout(300)
            end_scrolltop = page3.evaluate("() => document.getElementById('tr-detail-log').scrollTop")
            end_max = page3.evaluate(
                "() => Math.max(0, document.getElementById('tr-detail-log').scrollHeight -"
                " document.getElementById('tr-detail-log').clientHeight)"
            )
            tr_end_landed = abs(end_scrolltop - end_max) <= 2
            end_visible = page3.evaluate("() => window.__trVisibleSegIds()")
            tr_end_visible2 = str(PHASED_LAST_SEG_ID) in (end_visible or [])
            page3.close()
        except Exception as e:  # noqa: BLE001 — any failure here is itself the finding
            tr_kb_errors.append(str(e).splitlines()[0])

        # === V-10, now native by construction (ADR-0026 rev 2, WebKit): PageDown/PageUp/Space used
        # to travel only a fraction of a page whenever the press crossed a render boundary, because
        # real WebKit runs a genuine multi-frame keyboard-scroll ANIMATION for these keys, and this
        # file's own scrollTop write (the old anchor/ratio compensation, reacting to the render the
        # press triggered) cancelled that animation mid-flight — the spike behind ADR-0026 proved
        # this is true of ANY script scrollTop write, including a no-op. Under D2/D3 there is no
        # interception and no compensation write left to cancel anything: these keys run their pure
        # native default action, and native scroll anchoring (not this file) settles the view if a
        # newly-measured row above the viewport shifts content. Presses ONE AT A TIME with waits
        # (matching Vera's own original repro shape) and asserts every press travels WITHIN 10% of
        # the browser's own derived native step — not bit-exact equality, because native anchoring
        # reacting to a newly-measured row can legitimately add a small correction on top of the
        # raw native step (the same "breathing" this file already documents and accepts elsewhere),
        # but a real cancellation is nowhere close: Vera measured actual pre-fix failures at
        # 171-330px against a 748px step (23-44%, roughly a third to a fifth of the true step),
        # nothing like the ~1-2% variance a healthy press shows. `expected_step` is this test's OWN
        # independent computation of WebKit's real internal `ScrollableArea::PageStep` formula
        # (clientHeight minus a fixed overlap, floored at 87.5% of clientHeight) — transcripts.js no
        # longer computes this at all (the deleted `pageStepPx()`); the browser does, natively.
        tr_pk_errors = []
        tr_pagedown_ok = tr_pageup_ok = tr_space_ok = False
        tr_pagedown_deltas = tr_pageup_deltas = tr_space_deltas = []
        try:
            page4 = browser.new_page(viewport={"width": 1520, "height": 984})
            page4.on("pageerror", lambda e: tr_pk_errors.append(str(e)))
            page4.add_init_script(STUB)
            page4.goto("file://" + os.path.join(DIST, "index.html"))
            page4.wait_for_function(HAS_RENDER, timeout=8000)
            page4.click("#app-menu-btn")
            page4.wait_for_selector('.nav-item[data-surface="transcripts"]', state="visible", timeout=8000)
            page4.click('.nav-item[data-surface="transcripts"]')
            page4.wait_for_function(
                "() => document.querySelectorAll('#tr-list .tr-card').length >= 3", timeout=8000
            )
            page4.click('#tr-list .tr-card[data-id="5"] .tr-card-open')
            page4.wait_for_function(
                "() => window.__trRenderedRowCount && window.__trRenderedRowCount() > 0", timeout=8000
            )
            page4.click("#tr-detail-log")
            expected_step = page4.evaluate(
                "() => { var h = document.getElementById('tr-detail-log').clientHeight;"
                " return Math.max(h - 40, Math.round(h * 0.875)); }"
            )

            def presses(key, count, sign):
                # 60ms between presses was sized for the pre-M1 file's INSTANT jumpScrollTop
                # (no animation at all, so 60ms was ample settle time). Under ADR-0026 these keys
                # run WebKit's genuine multi-frame native scroll animation (spike C2 — traced at
                # ~300ms for Home/End), so a press arriving before the previous one's animation
                # has settled reads a MID-ANIMATION sample, not a per-press delta — exactly the
                # kind of irregular reading a real user could never produce by pressing keys at a
                # normal cadence. 400ms is the wait this ticket's own M1 spike (ADR-0026 rev 2 go/
                # no-go) validated as reliably clearing that animation on both engines.
                deltas = []
                prev = page4.evaluate("() => document.getElementById('tr-detail-log').scrollTop")
                for _ in range(count):
                    page4.keyboard.press(key)
                    page4.wait_for_timeout(400)
                    cur = page4.evaluate("() => document.getElementById('tr-detail-log').scrollTop")
                    deltas.append((cur - prev) * sign)
                    prev = cur
                return deltas

            tr_pagedown_deltas = presses("PageDown", 14, 1)
            tr_pageup_deltas = presses("PageUp", 6, -1)
            page4.evaluate("() => window.__trScrollToFraction(0.02)")
            page4.wait_for_timeout(50)
            tr_space_deltas = presses("Space", 8, 1)

            def within_tolerance(deltas):
                return len(deltas) > 0 and all(
                    expected_step * 0.9 <= d <= expected_step * 1.1 for d in deltas
                )

            tr_pagedown_ok = within_tolerance(tr_pagedown_deltas)
            tr_pageup_ok = within_tolerance(tr_pageup_deltas)
            tr_space_ok = within_tolerance(tr_space_deltas)
            page4.close()
        except Exception as e:  # noqa: BLE001 — any failure here is itself the finding
            tr_pk_errors.append(str(e).splitlines()[0])

        # === V-11, closed by construction under D1 (Vera, Low, WebKit): a tail-pin render that
        # GROWS the (formerly global) ratio used to be able to leave the view short of the true
        # end — the pin's whole point is "the true last segment is always reachable," which a
        # scrollTop computed BEFORE that growth could not guarantee, and the pre-M1 file's fix was
        # a `scrollTop` RE-ASSERTION write after the pin's own measurement pass. ADR-0026 D2
        # deletes that re-assertion outright (it is one of the writes the "component never writes
        # scrollTop" invariant forbids) — this now works because D1's per-row metric is exact and
        # local (I2): measuring the tail's real heights never needs correcting anything ABOVE it,
        # so there is nothing left for a re-assertion to fix. Narrows the log column so every row's
        # REAL wrapped-line count exceeds the 88-chars/line estimate, then jumps straight to End on
        # a FRESH open (no prior scroll) so the very FIRST measurement is the tail itself, the exact
        # precondition this used to need a script write to handle correctly.
        tr_v11_errors = []
        tr_v11_at_true_end = tr_v11_last_visible = False
        try:
            page5 = browser.new_page(viewport={"width": 1520, "height": 984})
            page5.on("pageerror", lambda e: tr_v11_errors.append(str(e)))
            page5.add_init_script(STUB)
            page5.goto("file://" + os.path.join(DIST, "index.html"))
            page5.wait_for_function(HAS_RENDER, timeout=8000)
            page5.click("#app-menu-btn")
            page5.wait_for_selector('.nav-item[data-surface="transcripts"]', state="visible", timeout=8000)
            page5.click('.nav-item[data-surface="transcripts"]')
            page5.wait_for_function(
                "() => document.querySelectorAll('#tr-list .tr-card').length >= 4", timeout=8000
            )
            page5.click('#tr-list .tr-card[data-id="6"] .tr-card-open')
            page5.wait_for_function(
                "() => window.__trRenderedRowCount && window.__trRenderedRowCount() > 0", timeout=8000
            )
            page5.evaluate(
                "() => { var v = document.getElementById('tr-detail-view');"
                " v.style.maxWidth = 'none'; v.style.width = '340px'; }"
            )
            page5.wait_for_timeout(50)
            page5.click("#tr-detail-log")
            page5.keyboard.press("End")
            page5.wait_for_timeout(300)
            v11_scrolltop = page5.evaluate("() => document.getElementById('tr-detail-log').scrollTop")
            v11_max = page5.evaluate(
                "() => Math.max(0, document.getElementById('tr-detail-log').scrollHeight -"
                " document.getElementById('tr-detail-log').clientHeight)"
            )
            tr_v11_at_true_end = abs(v11_scrolltop - v11_max) <= 1
            v11_visible = page5.evaluate("() => window.__trVisibleSegIds()")
            tr_v11_last_visible = str(UNIFORM_LONG_LAST_SEG_ID) in (v11_visible or [])
            page5.close()
        except Exception as e:  # noqa: BLE001 — any failure here is itself the finding
            tr_v11_errors.append(str(e).splitlines()[0])

        # === V-12, closed by construction (Vera, Low, WebKit): Shift+End should extend a text
        # selection to the end (or at minimum leave an existing selection alone), never silently
        # collapse it into a scroll-only jump. The pre-M1 file needed an explicit `!ev.shiftKey`
        # guard in its keydown handler to get this right; ADR-0026 D3 deletes the handler entirely,
        # so every modifier combination — Shift included — is simply the browser's own native
        # behaviour with nothing left to intercept it. This regression-tests that native behaviour
        # directly, the same as before.
        tr_v12_errors = []
        tr_v12_selection_preserved = False
        try:
            page6 = browser.new_page(viewport={"width": 1520, "height": 984})
            page6.on("pageerror", lambda e: tr_v12_errors.append(str(e)))
            page6.add_init_script(STUB)
            page6.goto("file://" + os.path.join(DIST, "index.html"))
            page6.wait_for_function(HAS_RENDER, timeout=8000)
            page6.click("#app-menu-btn")
            page6.wait_for_selector('.nav-item[data-surface="transcripts"]', state="visible", timeout=8000)
            page6.click('.nav-item[data-surface="transcripts"]')
            page6.wait_for_function(
                "() => document.querySelectorAll('#tr-list .tr-card').length >= 3", timeout=8000
            )
            page6.click('#tr-list .tr-card[data-id="5"] .tr-card-open')
            page6.wait_for_function(
                "() => window.__trRenderedRowCount && window.__trRenderedRowCount() > 0", timeout=8000
            )
            page6.click("#tr-detail-log")
            make_selection_js = (
                "(id) => { var row = window.__trRowFor(id); var t = row.querySelector('.tr-line-txt').firstChild;"
                " var sel = window.getSelection(); sel.removeAllRanges(); var r = document.createRange();"
                " r.setStart(t, 0); r.setEnd(t, Math.min(5, t.length)); sel.addRange(r);"
                " return sel.toString().length; }"
            )
            before_len = page6.evaluate(make_selection_js, PHASED_FIRST_SEG_ID)
            page6.keyboard.down("Shift")
            page6.keyboard.press("End")
            page6.keyboard.up("Shift")
            page6.wait_for_timeout(200)
            after_len = page6.evaluate("() => window.getSelection().toString().length")
            tr_v12_selection_preserved = before_len > 0 and after_len >= before_len
            page6.close()
        except Exception as e:  # noqa: BLE001 — any failure here is itself the finding
            tr_v12_errors.append(str(e).splitlines()[0])

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
    checks.append((tr_ratio_moved, "Transcripts realistic-width: a real number of rows were measured and folded into the exact D1 height metric on real WebKit"))
    checks.append((tr_last_visible, "Transcripts realistic-width: a real 'End' keypress mounts the LAST segment of a realistic-width, realistic-length transcript"))
    checks.append((tr_end_visible, "Transcripts realistic-width: the last segment is actually VISIBLE after a real scroll-to-end (Vera V-1: previously 0/8 attempts) — the real scroll path, not a test hook"))

    checks.append((not tr_kb_errors, "Transcripts Home/End native: exercised on real WebKit with a regime-calibrated jump, no exception"
                   + (" — " + "; ".join(tr_kb_errors) if tr_kb_errors else "")))
    checks.append((tr_home_landed, "Transcripts Home/End native: a real Home keypress after calibrating on a DIFFERENT length regime lands scrollTop exactly at 0 (ADR-0026: native default action, no interception left to race)"))
    checks.append((tr_home_visible, "Transcripts Home/End native: the true FIRST segment is actually visible after that real Home keypress"))
    checks.append((tr_end_landed, "Transcripts Home/End native: a real End keypress after calibrating on a DIFFERENT length regime lands scrollTop exactly at the true max (ADR-0026: native default action + native scroll anchoring, no cascaded recompute to un-pin it)"))
    checks.append((tr_end_visible2, "Transcripts Home/End native: the true LAST segment is actually visible after that real End keypress"))

    checks.append((not tr_pk_errors, "Transcripts V-10: PageDown/PageUp/Space exercised on real WebKit, no exception"
                   + (" — " + "; ".join(tr_pk_errors) if tr_pk_errors else "")))
    checks.append((tr_pagedown_ok, "Transcripts V-10: every real PageDown press travels within 10% of the derived native step (Vera: previously 5/14 fell to 23-44% of it on WebKit) — deltas " + str(tr_pagedown_deltas)))
    checks.append((tr_pageup_ok, "Transcripts V-10: every real PageUp press travels within 10% of the derived native step — deltas " + str(tr_pageup_deltas)))
    checks.append((tr_space_ok, "Transcripts V-10: every real Space press travels within 10% of the derived native step (Vera: previously 4/8 fell to 23-44% of it on WebKit) — deltas " + str(tr_space_deltas)))

    checks.append((not tr_v11_errors, "Transcripts V-11: tail-growth exercised on real WebKit, no exception"
                   + (" — " + "; ".join(tr_v11_errors) if tr_v11_errors else "")))
    checks.append((tr_v11_at_true_end, "Transcripts V-11: a fresh-open End keypress whose OWN tail-pin render grows avgRatio still lands scrollTop exactly at the (recalculated) true end"))
    checks.append((tr_v11_last_visible, "Transcripts V-11: the true last segment is actually visible after that fresh-open End keypress"))

    checks.append((not tr_v12_errors, "Transcripts V-12: Shift+End modifier exercised on real WebKit, no exception"
                   + (" — " + "; ".join(tr_v12_errors) if tr_v12_errors else "")))
    checks.append((tr_v12_selection_preserved, "Transcripts V-12: a real Shift+End keypress over an active text selection preserves/extends it rather than silently collapsing it via our own scroll jump"))

    for passed, msg in checks:
        print(("PASS" if passed else "FAIL") + ": " + msg)
    fails = sum(1 for passed, _ in checks if not passed)
    print("=== WebKit smoke: %d checks, %d FAIL ===" % (len(checks), fails))
    sys.exit(1 if fails else 0)


main()
