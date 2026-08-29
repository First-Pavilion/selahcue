#!/usr/bin/env python3
"""On-demand WebKit RENDER probe for the plan-lifecycle states (86ak8467m).

Not part of `make ci`, and deliberately so: this is the counterpart to
`operator_webkit_smoke.py` (which CI runs as a BOOT smoke) for the one thing neither
gate can see — LAYOUT under the engine Tauri actually ships on. The committed
behavioural gate drives Blink and asserts ELEMENTS; this drives WebKit
(JavaScriptCore/WebCore, WKWebView's core) and asserts GEOMETRY, and writes
screenshots so the states can be looked at rather than only asserted.

It earns its place in `scripts/` because it caught a defect both gates missed: view-only
hid the ADD ITEM column but not its GRID TRACK, so the run sheet rendered inside the
220px palette column with every title truncated. A resolved-track assertion is now in the
fast gate, but the class of defect is only visible here.

Run it after any change to the plan surface's layout:

    python3 scripts/operator_plan_webkit_probe.py

Requires Playwright + WebKit (`pip install playwright && playwright install webkit`).
Screenshots land in WK_OUT (default: a temp directory printed on exit).

Asserts the layout invariants the Blink gate structurally cannot see:

  - no control collapses to zero width (the flex-<select> family of failures)
  - the page never scrolls horizontally
  - the dialog's content fits the dialog (no clipped textarea / template list)
  - the summary panel's last element is reachable inside its scroll container

Screenshots are written so the states can be looked at, not only asserted.
"""
import os
import sys
import pathlib
import tempfile
from playwright.sync_api import sync_playwright

REPO = pathlib.Path(__file__).resolve().parent.parent
DIST = REPO / "implementation/desktop/crates/selahcue-operator/dist"
OUT = pathlib.Path(os.environ.get("WK_OUT") or tempfile.mkdtemp(prefix="selahcue-wk-"))
OUT.mkdir(parents=True, exist_ok=True)

STUB = r"""
window.__calls = [];
var PL_ITEMS = [
  { id: 301, kind: "song",         title: "Great Are You Lord", is_live: false, is_staged: false, owner: "Ada", planned_secs: 300 },
  { id: 302, kind: "scripture",    title: "Romans 8:28",        is_live: false, is_staged: false, owner: "Sam", planned_secs: 120 },
  { id: 303, kind: "slide_group",  title: "Sermon: The Waiting", is_live: false, is_staged: false, owner: "Pastor J" },
  { id: 304, kind: "announcement", title: "Welcome and notices", is_live: false, is_staged: false }
];
var V = { plan_name: "Sunday AM Service", items: PL_ITEMS,
  live_index: null, staged_index: null, blackout: false, timer: null,
  outputs: [], displays: [], translations: ["KJV", "WEB"], theme: "classic", themes: ["classic"],
  saved_themes: [], screen_themes: [],
  publish: { revision: 7, published_revision: 5, version: 4, changed: true },
  plan_templates: [ { id: "sunday-morning", name: "Sunday Morning", items: 5 },
                    { id: "midweek", name: "Midweek Gathering", items: 4 } ] };
var T = { background:{r:8,g:10,b:20,a:255},
  title:{x_permille:60,y_permille:150,w_permille:880,h_permille:110,align_h:"center",align_v:"middle",size_permille:48,line_height_permille:1200,color:{r:242,g:181,b:60,a:255},fit:"shrink_to_fit",visible:true},
  body:{x_permille:60,y_permille:280,w_permille:880,h_permille:560,align_h:"center",align_v:"middle",size_permille:78,line_height_permille:1150,color:{r:255,g:255,b:255,a:255},fit:"shrink_to_fit",visible:true} };
window.__TAURI__ = { core: { invoke: function(cmd, args){
  window.__calls.push({cmd:cmd, args:args});
  if (cmd === "builtin_themes") return Promise.resolve([{name:"Classic", theme:JSON.parse(JSON.stringify(T))}]);
  if (cmd === "system_fonts") return Promise.resolve([]);
  if (cmd === "view") return Promise.resolve(JSON.parse(JSON.stringify(V)));
  if (cmd === "deck_list") return Promise.resolve({decks:[{id:2,name:"Sermon Deck",slides:24}]});
  if (cmd === "preview_theme") return Promise.resolve({rgba: btoa("\x00\x00\x00\xff"), w:1, h:1});
  if (cmd === "publish_plan" || cmd === "new_plan" || cmd === "template_plan" ||
      cmd === "duplicate_plan" || cmd === "import_plan") return Promise.resolve(JSON.parse(JSON.stringify(V)));
  return Promise.resolve(null);
}}, event: { listen: function(){ return Promise.resolve(function(){}); } } };
window.__V = V;
"""

fails = []
def ok(cond, msg):
    print(("PASS: " if cond else "FAIL: ") + msg)
    if not cond:
        fails.append(msg)

with sync_playwright() as pw:
    b = pw.webkit.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(STUB)
    pg.goto("file://" + str(DIST / "index.html"))
    # Wait for the app to have BOOTED (its own poll ran) before driving it.
    pg.wait_for_function("() => window.__calls && window.__calls.some(c => c.cmd === 'view')", timeout=8000)
    pg.wait_for_timeout(200)
    pg.evaluate("() => document.querySelector('.nav-item[data-surface=\"plan\"]').click()")
    pg.wait_for_timeout(400)

    ok(not errs, "no uncaught JS error on WebKit with the lifecycle code loaded (%s)" % (errs[:1] or "none"))

    def no_hscroll(tag):
        v = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(v <= 0, "%s: the page does not scroll horizontally (overflow=%spx)" % (tag, v))

    def wide_enough(sel, tag, minw=60):
        r = pg.evaluate("(s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return {w:b.width, h:b.height}; }", sel)
        ok(r is not None and r["w"] >= minw and r["h"] >= 20,
           "%s: %s renders at a usable size (%s)" % (tag, sel, r))

    # --- 1. populated + published-and-changed summary ---------------------------------
    pg.evaluate("() => { planSelectedId = null; planRenderBuilder(window.__V); }")
    pg.wait_for_timeout(200)
    ok(pg.evaluate("() => !!document.getElementById('plan-pub-changed')"), "state 1: the change badge renders on WebKit")
    wide_enough("#plan-sum-publish", "state 1")
    wide_enough("#plan-sum-duplicate", "state 1")
    no_hscroll("state 1")
    # the panel's last element must be reachable inside the scroll container
    reach = pg.evaluate("""() => {
      const surf = document.getElementById('surface-plan');
      const last = document.querySelector('#plan-b-insp .plan-sum-hint');
      if (!surf || !last) return null;
      surf.scrollTop = surf.scrollHeight;
      const r = last.getBoundingClientRect();
      const bottom = surf.getBoundingClientRect().top + surf.clientHeight;
      const out = r.bottom - bottom;
      surf.scrollTop = 0;
      return out;
    }""")
    ok(reach is not None and reach <= 1,
       "state 1: the bottom of the taller Plan Summary is reachable inside the scroll container (overshoot=%spx)" % reach)
    pg.screenshot(path=str(OUT / "1-summary-changed.png"), full_page=False)

    # --- 2. empty state, all four starts ----------------------------------------------
    pg.evaluate("() => { const v = JSON.parse(JSON.stringify(window.__V)); v.items = []; planSelectedId = null; planRenderBuilder(v); }")
    pg.wait_for_timeout(150)
    for sel in ["#plan-empty-new", "#plan-empty-template", "#plan-empty-duplicate", "#plan-empty-import", "#plan-empty-bundle"]:
        wide_enough(sel, "state 2", minw=120)
    no_hscroll("state 2")
    pg.screenshot(path=str(OUT / "2-empty.png"))

    # --- 3. the template dialog -------------------------------------------------------
    pg.evaluate("() => document.getElementById('plan-empty-template').click()")
    pg.wait_for_timeout(200)
    fit = pg.evaluate("""() => {
      const dlg = document.querySelector('.pm-confirm');
      const list = document.querySelector('.plan-tpl-list');
      const inp = document.getElementById('pm-prompt-input');
      if (!dlg || !list || !inp) return null;
      const d = dlg.getBoundingClientRect(), l = list.getBoundingClientRect(), i = inp.getBoundingClientRect();
      return { dlgW: d.width, dlgH: d.height, listW: l.width, inpW: i.width,
               listOut: l.right - d.right, inpOut: i.right - d.right,
               rows: document.querySelectorAll('.plan-tpl-row').length,
               rowW: document.querySelector('.plan-tpl-row').getBoundingClientRect().width };
    }""")
    ok(fit is not None and fit["rows"] == 2 and fit["rowW"] > 200,
       "state 3: the template rows render at full width, not collapsed (%s)" % fit)
    ok(fit is not None and fit["listOut"] <= 1 and fit["inpOut"] <= 1,
       "state 3: the template list and the name field stay inside the dialog (%s)" % fit)
    pg.screenshot(path=str(OUT / "3-template-dialog.png"))
    pg.evaluate("() => document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}))")
    pg.wait_for_timeout(150)

    # --- 4. the import dialog ---------------------------------------------------------
    pg.evaluate("() => document.getElementById('plan-empty-import').click()")
    pg.wait_for_timeout(200)
    ta = pg.evaluate("""() => {
      const dlg = document.querySelector('.pm-confirm');
      const t = document.getElementById('plan-import-text');
      if (!dlg || !t) return null;
      const d = dlg.getBoundingClientRect(), r = t.getBoundingClientRect();
      return { w: r.width, h: r.height, out: r.right - d.right };
    }""")
    ok(ta is not None and ta["w"] > 200 and ta["h"] > 90 and ta["out"] <= 1,
       "state 4: the run-sheet textarea renders full width and tall enough to paste into (%s)" % ta)
    # the inline refusal must be visible, not clipped
    pg.evaluate("""() => {
      document.getElementById('pm-prompt-input').value = 'Imported';
      document.getElementById('plan-import-text').value = 'Sermon';
      document.querySelector('.pm-confirm .pm-confirm-actions .pm-btn-primary').click();
    }""")
    pg.wait_for_timeout(150)
    err = pg.evaluate("""() => {
      const e = document.getElementById('pm-prompt-error');
      if (!e || e.hidden) return null;
      const r = e.getBoundingClientRect();
      return { w: r.width, h: r.height, text: e.textContent.slice(0, 40) };
    }""")
    ok(err is not None and err["w"] > 100 and err["h"] > 8,
       "state 4: the inline refusal is laid out and visible, not a zero-height element (%s)" % err)
    pg.screenshot(path=str(OUT / "4-import-dialog.png"))
    pg.evaluate("() => document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}))")
    pg.wait_for_timeout(150)

    # --- 5. view-only -----------------------------------------------------------------
    pg.evaluate("""() => {
      const v = JSON.parse(JSON.stringify(window.__V));
      v.viewer = { role: 'viewer', can_edit: false };
      planSelectedId = null; planRenderBuilder(v);
    }""")
    pg.wait_for_timeout(150)
    vo = pg.evaluate("""() => ({
      badge: !!document.getElementById('plan-viewonly'),
      paletteDisplay: getComputedStyle(document.querySelector('#surface-plan .plan-palette')).display,
      publish: !!document.getElementById('plan-sum-publish'),
      handles: document.querySelectorAll('#plan-b-list .plan-b-handle').length,
      openLive: document.getElementById('plan-open-live').textContent.trim(),
      gridCols: getComputedStyle(document.querySelector('.plan-builder-grid')).gridTemplateColumns
    })""")
    ok(vo["badge"] and vo["paletteDisplay"] == "none" and not vo["publish"] and vo["handles"] == 0,
       "state 5: view-only hides the palette, the handles and Publish on WebKit (%s)" % vo)
    # The grid still declares three tracks; the hidden column must not leave a dead gap that
    # pushes the run sheet off-screen.
    no_hscroll("state 5")
    pg.screenshot(path=str(OUT / "5-view-only.png"))

    b.close()

print("\n=== WebKit plan-lifecycle render: %d check(s), %d FAIL ===" % (5, len(fails)))
print("screenshots in " + str(OUT))
sys.exit(1 if fails else 0)
