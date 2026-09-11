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
  if (cmd === "transcript_list") return Promise.resolve([
    {id:1, label:"Sunday Service", provider:"manual", started_at_ms:1722760800000, ended_at_ms:1722764460000, segment_count:1}
  ]);
  if (cmd === "transcript_get") return Promise.resolve({
    id:1, label:"Sunday Service", provider:"manual", started_at_ms:1722760800000, ended_at_ms:1722764460000,
    notes_generated:false, segments:[{id:101, start_ms:0, end_ms:4000, text:"Good morning, church."}]
  });
  return Promise.resolve(null);
} } };
"""

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

    for passed, msg in checks:
        print(("PASS" if passed else "FAIL") + ": " + msg)
    fails = sum(1 for passed, _ in checks if not passed)
    print("=== WebKit smoke: %d checks, %d FAIL ===" % (len(checks), fails))
    sys.exit(1 if fails else 0)


main()
