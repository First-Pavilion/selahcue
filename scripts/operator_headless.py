#!/usr/bin/env python3
"""Committed BEHAVIOURAL test for the SelahCue operator webview (audit follow-up #9).

Injects a window.__TAURI__ stub + a driver into a copy of the real dist/index.html,
runs it under headless Chrome (real layout/CSS/canvas), and parses the driver's
PASS/FAIL results. This is the CI-gated behavioural counterpart to the static
content pins in `test_tokens.rs` / `test_keymap.rs`: it exercises the actual JS
(console render, plan-dedup, transcript cap, Theme-Designer wiring), so a
behavioural regression fails CI rather than only a dev-time check.

Runs on macOS (dev) and Linux CI. Chrome is resolved via CHROME_BIN, then PATH
(google-chrome/chromium), then the macOS app bundle. If Chrome is absent this
exits 0 with a LOUD SKIP notice so `make ci` on a Chrome-less box still passes —
UNLESS SELAHCUE_HEADLESS_REQUIRE=1 (set in CI), which turns a missing Chrome into a
hard failure so the gate can never silently no-op.

FIDELITY NOTE (known gap): this drives Blink (headless Chrome), NOT the engine Tauri
actually ships on — WebKitGTK (Linux), WKWebView (macOS), WebView2 (Windows). It is
therefore a gate for BROWSER-PORTABLE DOM/JS LOGIC (the behaviours asserted here:
render/dedup/cap/wiring), not for engine-specific CSS/canvas quirks. A WebKit/WKWebView-
driven smoke would be a stronger fidelity check; tracked as an audit follow-up. The real
Tauri webview stays owner-run / dev-time.
"""
import shutil
import subprocess, tempfile, os, re, sys

# Repo-relative: this file lives in <repo>/scripts/, the webview in
# <repo>/implementation/desktop/crates/selahcue-operator/dist. SELAHCUE_OPERATOR_DIST
# overrides it (e.g. to point at a staged/built copy, or a mutated copy in a test).
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.environ.get("SELAHCUE_OPERATOR_DIST") or os.path.join(
    _REPO, "implementation", "desktop", "crates", "selahcue-operator", "dist"
)

# Floor on the number of checks the driver must run — so a driver regression that
# silently runs FEWER checks (and thus reports 0 FAIL) still fails. Set TIGHT to the
# real load-bearing count (no tautologies), so any single dropped check trips exit 4.
# Bump when adding checks; never lower it to mask a lost one.
EXPECTED_MIN_CHECKS = 99


def find_chrome():
    """Locate a Chrome/Chromium binary across dev (macOS) and CI (Linux)."""
    env = os.environ.get("CHROME_BIN")
    if env and os.path.exists(env):
        return env
    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
    ):
        found = shutil.which(name)
        if found:
            return found
    for path in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ):
        if os.path.exists(path):
            return path
    return None


CHROME = find_chrome()
if CHROME is None:
    require = os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1"
    msg = "no Chrome/Chromium found (set CHROME_BIN or install google-chrome)"
    if require:
        print("FAIL: SELAHCUE_HEADLESS_REQUIRE=1 but " + msg)
        sys.exit(3)
    # LOUD skip so it is never misread as "the webview gate passed" (e.g. under `make ci`,
    # whose final ALL-GREEN banner covers only the gates that actually ran). CI sets
    # SELAHCUE_HEADLESS_REQUIRE=1, so this graceful path is dev-box-only.
    print("=" * 68)
    print("!! WEBVIEW BEHAVIOURAL GATE SKIPPED — " + msg)
    print("!! (install Chrome or set CHROME_BIN to run it; CI runs it with REQUIRE=1)")
    print("=" * 68)
    sys.exit(0)

html = open(os.path.join(DIST, "index.html")).read()

STUB = r"""
<script>
  window.__calls = [];
  window.__ev = {};          // event name -> [handlers] (Tauri event stub)
  window.__startCtl = null;  // resolve/reject for a pending start_listening
  window.__renderAvailable = true; // flip to test the Remote/older-host text fallback
  // A REAL OperatorView so the boot render path (act->render->syncChrome->renderConsole) runs
  // exactly as in the app — the prior null stub masked the #7 render never firing on launch.
  var V = { plan_name:"Svc", items:[{id:1,kind:"scripture",title:"Genesis 1:13",is_live:true,is_staged:true}],
    live_index:0, staged_index:0, blackout:false, timer:null, staged_scripture:"Genesis 1:13",
    live_scripture:"Genesis 1:13", live_free_text:null,
    outputs:[{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080}],
    displays:[{key:"d1", name:"Main", width:1920, height:1080}], translations:["KJV"],
    theme:"classic", themes:["classic"], saved_themes:[], screen_themes:[],
    screens:[
      {screen:"main", role:"main", enabled:true, deletable:false, theme:null},
      {screen:"lower-third", role:"lower-third", enabled:true, deletable:false, theme:null},
      {screen:"stream", role:"stream", enabled:true, deletable:false, theme:null},
      {screen:"stage", role:"stage", enabled:true, deletable:false, theme:null}
    ] };
  var T = {
    background:{r:8,g:10,b:20,a:255},
    title:{x_permille:60,y_permille:150,w_permille:880,h_permille:110,align_h:"center",align_v:"middle",size_permille:48,line_height_permille:1200,color:{r:242,g:181,b:60,a:255},fit:"shrink_to_fit",visible:true},
    body:{x_permille:60,y_permille:280,w_permille:880,h_permille:560,align_h:"center",align_v:"middle",size_permille:78,line_height_permille:1150,color:{r:255,g:255,b:255,a:255},fit:"shrink_to_fit",visible:true}
  };
  window.__TAURI__ = { core: { invoke: function(cmd, args){
    window.__calls.push({cmd:cmd, args:args});
    if (cmd === "builtin_themes") return Promise.resolve([{name:"Classic", theme:JSON.parse(JSON.stringify(T))}]);
    if (cmd === "system_fonts") return Promise.resolve([]);
    if (cmd === "view") return Promise.resolve(JSON.parse(JSON.stringify(V)));
    if (cmd === "preview_theme") return Promise.resolve({rgba: btoa("\x00\x00\x00\xff"), w:1, h:1});
    if (cmd === "pick_image") return Promise.resolve("/tmp/picked.png");
    if (cmd === "render_console") return Promise.resolve(
      window.__renderAvailable
        ? {available:true,
           preview:{w:2,h:1,rgba:btoa("\xff\x00\x00\xff\x00\xff\x00\xff")},
           live:{w:2,h:1,rgba:btoa("\x00\x00\xff\xff\xff\xff\x00\xff")}}
        : {available:false});
    if (cmd === "render_screen") {
      // A distinct 2x1 RGBA frame per audience screen (86ajq321k), so the previews differ.
      var px = { "main": "\xff\x00\x00\xff\x00\x00\x00\xff",
                 "lower-third": "\x00\xff\x00\xff\x00\x00\x00\xff",
                 "stream": "\x00\x00\xff\xff\x00\x00\x00\xff" };
      return Promise.resolve({available:true, frame:{w:2, h:1, rgba: btoa(px[args.screen] || "\x33\x33\x33\xff\x00\x00\x00\xff")}});
    }
    if (cmd === "set_screen_enabled") {
      // Simulate an RBAC-denied / older-host rejection to exercise the no-lie revert.
      if (window.__rejectSetEnabled) return Promise.reject("denied");
      V.screens.forEach(function(s){ if (s.screen === args.screen) s.enabled = args.enabled; });
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "add_screen") {
      // Mint role-N (smallest N>=2 free), mirroring the host registry.
      var ids = V.screens.map(function(s){ return s.screen; });
      var n = 2; while (ids.indexOf(args.role + "-" + n) >= 0) n++;
      V.screens.push({screen: args.role + "-" + n, role: args.role, enabled:true, deletable:true, theme:null});
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "remove_screen") {
      V.screens = V.screens.filter(function(s){ return !(s.screen === args.screen && s.deletable); });
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "set_custom_theme") return Promise.resolve({});
    if (cmd === "save_theme") return Promise.resolve({saved_themes:[{name:args.name, theme_json:args.themeJson}]});
    if (cmd === "operator_state" || cmd === "state") return Promise.resolve({});
    // Listen control: start_listening stays PENDING until the test drives it, mirroring the
    // host worker that loads the model + opens the mic before signalling readiness.
    if (cmd === "start_listening") return new Promise(function(res, rej){ window.__startCtl = {resolve:res, reject:rej}; });
    if (cmd === "stop_listening") return Promise.resolve(null);
    if (cmd === "get_chapter") return Promise.resolve({
      reference: (args && args.reference) ? String(args.reference).replace(/:.*$/, "") : "Isaiah 61",
      translation: "KJV", translations: ["KJV"],
      verses: [[1, "verse one text"], [5, "verse five text"]],
      verse_start: 5, verse_end: null, prev: true, next: true,
    });
    if (cmd === "approve_detection" || cmd === "dismiss_detection" || cmd === "go_live")
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    return Promise.resolve(null);
  } },
  event: { listen: function(name, cb){ (window.__ev[name] = window.__ev[name] || []).push(cb); return Promise.resolve(function(){}); } } };
  window.__emit = function(name, payload){ (window.__ev[name] || []).forEach(function(cb){ cb({event:name, payload:payload}); }); };
</script>
"""

DRIVER = r"""
<pre id="__r" style="position:fixed;z-index:99999;background:#fff;color:#000"></pre>
<script>
  var R = [];
  function ok(c,m){ R.push((c?"PASS":"FAIL")+": "+m); }
  // The theme JSON captured by the LAST set_custom_theme (Apply) call.
  function applied(){
    document.getElementById("td-apply").click();
    var cs = window.__calls.filter(function(c){return c.cmd==="set_custom_theme";});
    return cs.length ? JSON.parse(cs[cs.length-1].args.themeJson) : null;
  }
  // Add Shape now opens a PICKER (86ajtwq24); choose a geometry (default Rectangle, which
  // keeps the pre-batch behaviour — a rect element with no `variant`).
  function addShape(kind){
    document.querySelector('.td-addbar button[data-add="shape"]').click();
    document.querySelector('#td-shape-row [data-shape="'+(kind||"rect")+'"]').click();
  }
  function el(id){ return document.getElementById(id); }
  var sleep=(ms)=>new Promise(function(r){setTimeout(r,ms);});
  // Poll a predicate up to `tries`×20ms of virtual time instead of a fixed sleep (audit #11):
  // the gate then waits exactly as long as the boot render needs and stays deterministic
  // (bounded) — a fixed sleep would spuriously RED the gate if app.js boot timing ever grew.
  var waitFor=async function(pred, tries){ tries=tries||150; for(var i=0;i<tries;i++){ if(pred()) return true; await sleep(20); } return pred(); };
  var hasRender=function(id){ var s=el(id) && el(id).querySelector(".surface"); return !!(s && s.classList.contains("has-render")); };
  async function run(){
    try {
      // === #7-FIX Preview/Live TRUE render (86ajtwq28) — must fire on BOOT (no nav-click) ===
      // Poll for the boot render to COMPLETE (panels reach has-render) rather than a fixed
      // sleep (audit #11); if it never fires, the poll times out and the checks below FAIL.
      await waitFor(function(){ return hasRender("preview-panel") && hasRender("live-panel"); });
      ok(window.__calls.some(function(c){return c.cmd==="render_console";}), "#7-fix render_console fires on BOOT (no nav-click crutch)");
      ok(el("preview-panel").querySelector(".surface").classList.contains("has-render"), "#7-fix Preview panel shows the true render on boot");
      ok(el("live-panel").querySelector(".surface").classList.contains("has-render"), "#7-fix Live panel shows the true render on boot");
      ok(el("preview-canvas").width===2 && el("preview-canvas").height===1, "#7 preview canvas drawn at the frame size");
      // M5: the tight-loop base64 decode (b64ToBytes) must be BYTE-EXACT — read the preview
      // canvas back and assert the two known stub pixels (red, then green).
      var pd = el("preview-canvas").getContext("2d").getImageData(0, 0, 2, 1).data;
      ok(pd[0]===255 && pd[1]===0 && pd[2]===0 && pd[3]===255 &&
         pd[4]===0 && pd[5]===255 && pd[6]===0 && pd[7]===255,
         "M5 tight base64 decode is byte-exact (preview pixels: " + Array.from(pd).join(",") + ")");
      // #1 the panels are 16:9-ish, NOT a collapsed strip (align-items:flex-start lets aspect-ratio apply).
      var pp = el("preview-panel");
      var ratio = pp.offsetWidth > 0 ? pp.offsetHeight / pp.offsetWidth : 0;
      ok(ratio > 0.35, "#1 preview panel is a 16:9-ish monitor, not a stretched strip (h/w=" + ratio.toFixed(2) + ")");
      // #2 the plan-item kind label truncates (nowrap) so it cannot overflow under the theme dropdown.
      var kindEl = document.querySelector(".item .kind");
      ok(kindEl && getComputedStyle(kindEl).whiteSpace === "nowrap", "#2 plan-item kind label truncates (nowrap), no overflow under the dropdown");
      // Read-only: rendering the console fired NO control command (never changes on air).
      var ctrl = window.__calls.filter(function(c){return ["next","go_live","clear","blackout","select","start_timer"].indexOf(c.cmd)>=0;}).length;
      ok(ctrl===0, "#7 rendering the preview fired no control command (read-only)");
      // available:false (a Remote host / older host) → text fallback, no canvas.
      window.__renderAvailable = false;
      document.querySelector('.nav-item[data-surface="console"]').click(); // re-schedule a render
      await waitFor(function(){ return !hasRender("preview-panel"); }); // poll for the fallback (audit #11)
      ok(!el("preview-panel").querySelector(".surface").classList.contains("has-render"), "#7 available:false → text fallback (no canvas)");
      window.__renderAvailable = true; // restore for the rest of the run

      // === audit L3: the Theme Designer loads LAZILY on first activation, not at boot ===
      ok(!window.__calls.some(function(c){return c.cmd==="builtin_themes";}),
         "L3 designer NOT loaded at boot (no builtin_themes before it is opened)");
      document.querySelector('.nav-item[data-surface="theme-designer"]').click(); // triggers the lazy load
      await sleep(80); // let the async builtin_themes / system_fonts resolve + build the designer
      ok(window.__calls.some(function(c){return c.cmd==="builtin_themes";}),
         "L3 designer loads on FIRST activation (builtin_themes fired after opening it)");

      // 86ajq3225 / Design 2.0: the background editor — a SEGMENTED type control switches
      // solid / gradient / image (Figma 317:142).
      var bgSeg = function(v){ return el("td-bg-type").querySelector('[data-bg="'+v+'"]'); };
      ok(bgSeg("solid").classList.contains("on") && !el("td-bg-solid").hidden,
         "bg: defaults to Solid with the colour picker shown");
      bgSeg("gradient").click();
      ok(!el("td-bg-gradient").hidden && el("td-bg-solid").hidden, "bg: Gradient shows the gradient controls");
      ok(bgSeg("gradient").classList.contains("on"), "bg: the Gradient segment is marked active");
      var bgG = applied().background;
      ok(!!bgG.from && !!bgG.to && bgG.direction==="vertical", "bg: the background serialises as a gradient {from,to,direction}");
      el("td-bg-dir").value = "horizontal"; el("td-bg-dir").dispatchEvent(new Event("change"));
      el("td-bg-to").value = "#ff0000"; el("td-bg-to").dispatchEvent(new Event("input"));
      var bgG2 = applied().background;
      ok(bgG2.direction==="horizontal" && bgG2.to.r===255 && bgG2.to.g===0, "bg: direction + to-colour update the gradient");
      bgSeg("image").click();
      ok(!el("td-bg-image").hidden, "bg: Image shows the image control");
      el("td-bg-img-pick").click();
      await sleep(30);
      ok(applied().background.source==="/tmp/picked.png", "bg: the image picker sets the background source");
      bgSeg("solid").click();
      el("td-bg").value = "#0a141e"; el("td-bg").dispatchEvent(new Event("input"));
      var bgS = applied().background;
      ok(typeof bgS.r==="number" && typeof bgS.from==="undefined" && typeof bgS.source==="undefined",
         "bg: Solid is a bare {r,g,b,a} colour (byte-compatible)");
      // Review MEDIUM fix: switching to Image must NOT write a malformed {source:""} — the
      // stored background stays a VALID shape (the previous solid) until a real source commits.
      bgSeg("image").click();
      var bgNoSrc = applied().background;
      ok(typeof bgNoSrc.source==="undefined" && typeof bgNoSrc.r==="number",
         "bg: switching to Image with no source keeps the valid solid bg (no malformed {source:''})");
      // The manual path field commits an image source (the no-native-dialog fallback, LOW fix).
      el("td-bg-img-path").value = "/host/bg.png"; el("td-bg-img-path").dispatchEvent(new Event("change"));
      ok(applied().background.source==="/host/bg.png", "bg: the manual path field commits an image source");

      // Design 2.0 TYPOGRAPHY (Figma 317:142): SIZE is a % field, LINE a multiplier field
      // (number fields, not sliders), and the Fit control is present + wired.
      el("td-size").value = "8.5"; el("td-size").dispatchEvent(new Event("input"));
      ok(applied().body.size_permille === 85, "typography: SIZE % field → size_permille (8.5% → 85)");
      el("td-lh").value = "1.30"; el("td-lh").dispatchEvent(new Event("input"));
      ok(applied().body.line_height_permille === 1300, "typography: LINE × field → line_height_permille (1.30 → 1300)");
      document.querySelector('#td-fit button[data-f="clip"]').click();
      ok(applied().body.fit === "clip", "typography: the Fit control sets the region fit");
      ok(document.querySelector('#td-fit button[data-f="clip"]').getAttribute("aria-pressed")==="true",
         "typography: the active Fit segment is marked");
      // Review fix: a BLANK number field must NOT commit (Number("")===0 would snap to the min);
      // an out-of-range value clamps the MODEL and `change` repopulates the FIELD to the clamp.
      el("td-size").value = "9.0"; el("td-size").dispatchEvent(new Event("input"));
      var szBefore = applied().body.size_permille;
      el("td-size").value = ""; el("td-size").dispatchEvent(new Event("input"));
      ok(applied().body.size_permille === szBefore, "typography: clearing SIZE does not snap the model to the min");
      el("td-size").value = "50"; el("td-size").dispatchEvent(new Event("input"));
      ok(applied().body.size_permille === 140, "typography: out-of-range SIZE clamps the model (50% → 140)");
      el("td-size").dispatchEvent(new Event("change"));
      ok(el("td-size").value === "14.0", "typography: SIZE field repopulates to the clamped value on change");

      // C-001: Add Shape → an element on tdTheme.elements, inspector shows, selection is element.
      addShape();
      ok(!el("td-el-inspector").hidden, "Add Shape shows the element inspector");
      ok(el("td-sel").classList.contains("is-element"), "selection box marks an element");
      var t1 = applied();
      ok(t1 && t1.elements && t1.elements.length===1 && t1.elements[0].kind==="shape", "shape element serialized (kind=shape)");
      ok(t1.elements[0].z===0 && t1.elements[0].opacity===255, "default z=0, opacity=255");
      ok(el("td-shape-row").hidden, "C-004 shape picker closes after choosing a kind");
      ok(t1.elements[0].variant===undefined, "C-004 a Rectangle pick omits `variant` (byte-identical JSON)");

      // C-003 arrange: add a 2nd shape (z=1), Send to back → z becomes min-1 = -1 (behind text).
      addShape();
      var t2 = applied();
      ok(t2.elements.length===2 && t2.elements[1].z===1, "second shape z=max+1=1");
      // The inspector "Arrange (z-order)" buttons were removed — z-order now lives on the LAYERS
      // panel (drag) + the Cmd/Ctrl+Shift+[ / ] chords. Cmd+Shift+[ = Send to back.
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"[",metaKey:true,shiftKey:true,bubbles:true}));
      var t3 = applied();
      ok(t3.elements[1].z===-1, "Send to back (Cmd+Shift+[) sets z=min-1=-1 (rewrites z, not the list)");
      ok(el("td-el-zchip").textContent.indexOf("Behind")>=0, "chip shows 'Behind text'");
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"]",metaKey:true,shiftKey:true,bubbles:true}));
      ok(applied().elements[1].z===1, "Bring to front (Cmd+Shift+]) sets z=max+1=1");

      // C-003 opacity: 50% → u8 128.
      el("td-el-op").value = 50; el("td-el-op").dispatchEvent(new Event("input"));
      ok(applied().elements[1].opacity===128, "opacity 50% maps to u8 128");

      // C-002 numeric X sync: set X=10.0% → x_permille=100.
      el("td-x").value = "10.0"; el("td-x").dispatchEvent(new Event("change"));
      ok(applied().elements[1].x_permille===100, "numeric X=10% → x_permille=100 (active element)");

      // C-002 keyboard move: ArrowRight nudges +10‰.
      var before = applied().elements[1].x_permille;
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowRight",bubbles:true}));
      ok(applied().elements[1].x_permille===before+10, "ArrowRight nudges +10 permille");

      // C-002 delete: two-click confirm removes the element.
      el("td-el-del").click(); el("td-el-del").click();
      ok(applied().elements.length===1, "two-click delete removes the element");

      // #1 native picker: Add Image → pick_image (stubbed) → an image element, NO path row.
      document.querySelector('.td-addbar button[data-add="image"]').click();
      await sleep(30);
      var ti = applied();
      ok(el("td-img-row").hidden, "#1 Add Image uses the native picker (no manual path row)");
      ok(ti.elements.some(function(e){return e.kind==="image" && e.source==="/tmp/picked.png";}), "#1 native picker adds an image with the chosen path");

      // 86ajq6j64: the TEXT add button is ENABLED and adds a text element; the inspector edits it.
      var textBtn = document.querySelector('.td-addbar button[data-add="text"]');
      ok(textBtn && !textBtn.disabled, "the Text add button is enabled (86ajq6j64)");
      textBtn.click();
      await sleep(30);
      var last = function(){ var e = applied().elements; return e[e.length-1]; };
      var txt = last();
      ok(txt && txt.kind==="text" && txt.text==="Text", "Add Text adds a text element with default content");
      ok(!el("td-el-text").hidden, "the text inspector shows for a text element");
      ok(el("td-el-shape").hidden && el("td-el-image").hidden, "shape/image inspectors hidden for a text element");
      ok(el("td-el-head").textContent.indexOf("Text")>=0, "the inspector head names it 'Text'");
      // Edit the content via the inspector.
      el("td-el-text-content").value = "Hello world";
      el("td-el-text-content").dispatchEvent(new Event("input"));
      ok(last().text==="Hello world", "the inspector edits the text content");
      // Size + alignment controls update the element.
      el("td-el-text-size").value = 12; el("td-el-text-size").dispatchEvent(new Event("input"));
      ok(last().size_permille===120, "size 12% → size_permille=120");
      el("td-el-text-align").value = "left"; el("td-el-text-align").dispatchEvent(new Event("change"));
      ok(last().align_h==="left", "the alignment select sets align_h");
      // Review fix: the content is CLIENT-bounded to the host cap (2000), so the UI can never
      // author a theme the host would reject (no false-success on Apply).
      el("td-el-text-content").value = "x".repeat(3000);
      el("td-el-text-content").dispatchEvent(new Event("input"));
      ok(last().text.length===2000, "an over-cap paste is truncated to 2000 chars on the client");
      // Clean up the text element so later element-count assertions are unaffected.
      el("td-el-del").click(); el("td-el-del").click();

      // FIX: click empty canvas deselects back to region editing.
      var bx = el("td-canvas-box").getBoundingClientRect();
      el("td-canvas-box").dispatchEvent(new PointerEvent("pointerdown",{clientX:bx.left+1,clientY:bx.top+1,bubbles:true}));
      ok(el("td-el-inspector").hidden, "click on empty canvas deselects back to regions");

      // FIX: Escape deselects (keyboard path).
      addShape();
      ok(!el("td-el-inspector").hidden, "element re-selected");
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}));
      ok(el("td-el-inspector").hidden, "Escape deselects the element");

      // FIX: delete-arm resets on selection change (no cross-element leak).
      addShape(); // A (selected)
      el("td-el-del").click(); // arm delete on A
      addShape(); // B auto-selected → tdSyncEl resets the arm + label
      ok(el("td-el-del").textContent==="Delete element", "delete arm/label reset on selection change");
      var nA = applied().elements.length;
      el("td-el-del").click(); // should ARM B (not delete), since the arm was reset
      ok(applied().elements.length===nA, "one click after a selection change does NOT delete (arm reset)");

      // Region regression: selecting a region hides the element inspector.
      document.querySelector('#td-region button[data-region="title"]').click();
      ok(el("td-el-inspector").hidden, "selecting a region hides the element inspector");
      ok(el("td-region").style.display!=="none", "region controls visible in region mode");

      // Make the designer laid out so getComputedStyle reflects the real CSS (the menu's
      // hide contract is CSS: .td-ctx[hidden]{display:none} vs .td-ctx{display:flex}).
      var tdSurf2=el("surface-theme-designer"); tdSurf2.style.display="block"; tdSurf2.classList.add("active");
      var cdisp=(id)=>getComputedStyle(el(id)).display;

      // #4 context menu: right-click opens it; Copy→Paste clones; Cmd+C/V; Delete.
      addShape();
      el("td-canvas-box").dispatchEvent(new MouseEvent("contextmenu",{clientX:40,clientY:40,bubbles:true}));
      ok(!el("td-ctx").hidden, "#4 right-click opens the context menu");
      ok(cdisp("td-ctx")!=="none", "#4 open menu is actually VISIBLE (computed display, not just attr)");
      el("td-ctx").querySelector('[data-ctx="copy"]').click();
      ok(el("td-ctx").hidden && cdisp("td-ctx")==="none", "#4 menu truly HIDDEN after close (the [hidden] guard works)");
      var nb = applied().elements.length;
      el("td-canvas-box").dispatchEvent(new MouseEvent("contextmenu",{clientX:40,clientY:40,bubbles:true}));
      el("td-ctx").querySelector('[data-ctx="paste"]').click();
      ok(applied().elements.length===nb+1, "#4 Copy then Paste clones the element (+1)");
      var n2 = applied().elements.length;
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"c",metaKey:true,bubbles:true}));
      el("td-sel").dispatchEvent(new KeyboardEvent("keydown",{key:"v",metaKey:true,bubbles:true}));
      ok(applied().elements.length===n2+1, "#4 Cmd+C then Cmd+V pastes a clone");
      var n3 = applied().elements.length;
      el("td-canvas-box").dispatchEvent(new MouseEvent("contextmenu",{clientX:40,clientY:40,bubbles:true}));
      el("td-ctx").querySelector('[data-ctx="delete"]').click();
      ok(applied().elements.length===n3-1, "#4 context-menu Delete removes the element");

      // LOW: a left-click while the menu is open just dismisses it (no select/deselect side-effect).
      addShape();
      var nSel = applied().elements.length;
      el("td-canvas-box").dispatchEvent(new MouseEvent("contextmenu",{clientX:40,clientY:40,bubbles:true}));
      ok(cdisp("td-ctx")!=="none", "#4 menu open before dismiss");
      el("td-canvas-box").dispatchEvent(new PointerEvent("pointerdown",{clientX:40,clientY:40,button:0,bubbles:true}));
      ok(cdisp("td-ctx")==="none", "#4 left-click dismisses the menu");
      ok(applied().elements.length===nSel, "#4 the dismiss click did not add/remove an element");

      // #3 click-select an element BENEATH the region box (position:fixed → real viewport coords).
      var surf=el("surface-theme-designer"); surf.style.display="block"; surf.classList.add("active");
      var box=el("td-canvas-box"); box.style.cssText="position:fixed;left:0;top:0;width:400px;height:226px;z-index:9;display:block";
      addShape(); // default centre ≈ (500,500) permille
      document.querySelector('#td-region button[data-region="body"]').click(); // select the large Body region
      ok(el("td-el-inspector").hidden, "#3 region selected — element inspector hidden");
      var br=box.getBoundingClientRect();
      // The forced position:fixed;width:400px MUST yield real viewport geometry (Chrome does
      // layout); assert it as a precondition so the hit-test below can never be silently
      // skipped by a vacuous fallback (adversarial review, audit #9).
      ok(br.width>10, "#3 canvas box has real layout geometry (width=" + Math.round(br.width) + ")");
      // The Body region box overlays the shape centre; a click there must re-hit-test to the shape.
      var cx=br.left+br.width*0.5, cy=br.top+br.height*0.5;
      el("td-sel").dispatchEvent(new PointerEvent("pointerdown",{clientX:cx,clientY:cy,button:0,bubbles:true,pointerId:1}));
      ok(!el("td-el-inspector").hidden, "#3 clicking an element UNDER the region box selects it");

      // User ask: clicking the Body or Reference/Title text ON THE CANVAS auto-selects that
      // region. Load a fresh built-in (T has no elements) so the click can't hit a leftover
      // element; the box keeps its real position:fixed geometry from #3.
      el("td-themes").querySelector('.td-theme-row:not(.td-theme-saved) .td-theme-name').click();
      await sleep(20);
      var toClient = function(xp, yp){ var b = box.getBoundingClientRect(); return { x: b.left + (xp/1000)*b.width, y: b.top + (yp/1000)*b.height }; };
      var pt = toClient(500, 200); // inside the title rect (y 150..260)
      box.dispatchEvent(new PointerEvent("pointerdown",{clientX:pt.x,clientY:pt.y,button:0,bubbles:true,pointerId:2}));
      ok(el("td-el-inspector").hidden, "canvas region-click stays in region mode (no element)");
      ok(document.querySelector('#td-region button[data-region="title"]').getAttribute("aria-pressed")==="true",
         "canvas: clicking the Reference/Title text selects that region");
      var pb = toClient(500, 500); // inside the body rect (y 280..840)
      box.dispatchEvent(new PointerEvent("pointerdown",{clientX:pb.x,clientY:pb.y,button:0,bubbles:true,pointerId:3}));
      ok(el("td-region-body").getAttribute("aria-pressed")==="true",
         "canvas: clicking the Body text selects the Body region");

      // Design 2.0: LAYERS drag-and-drop reorders z, and dragging an element past the text
      // REGION rows crosses the text boundary (front z>0 <-> behind z<0). Fresh Classic theme
      // (no elements) → add two front shapes → drag the top one below the region rows.
      el("td-themes").querySelector('.td-theme-row:not(.td-theme-saved) .td-theme-name').click();
      await sleep(20);
      addShape(); addShape();
      var dTop = applied().elements.length - 1; // the frontmost (highest z) shape
      ok(applied().elements[dTop].z >= 0, "D2 dnd: a freshly-added shape starts in front of the text (z>=0)");
      var lbox = el("td-layers");
      var dragRow2 = Array.prototype.filter.call(lbox.querySelectorAll(".td-layer"), function(r){ return r.dataset.idx===String(dTop); })[0];
      var regionRows2 = Array.prototype.filter.call(lbox.querySelectorAll(".td-layer"), function(r){ return r.dataset.region; });
      var lastRegion = regionRows2[regionRows2.length-1];
      var dr = dragRow2.getBoundingClientRect(), lr = lastRegion.getBoundingClientRect();
      // Precondition: the layers list has real vertical layout (rows at distinct Y) — else the
      // drag hit-test is meaningless and the assertion below could pass vacuously.
      ok(lr.top > dr.top + 4, "D2 dnd: the LAYERS list has real row geometry (regions below the shape)");
      var hdl = dragRow2.querySelector(".td-layer-handle");
      hdl.dispatchEvent(new PointerEvent("pointerdown",{clientX:dr.left+6,clientY:dr.top+6,button:0,bubbles:true,pointerId:9}));
      window.dispatchEvent(new PointerEvent("pointermove",{clientX:lr.left+6,clientY:lr.bottom+8,bubbles:true,pointerId:9}));
      window.dispatchEvent(new PointerEvent("pointerup",{clientX:lr.left+6,clientY:lr.bottom+8,bubbles:true,pointerId:9}));
      await sleep(10);
      ok(applied().elements[dTop].z < 0, "D2 dnd: dragging a layer below the region rows moves it BEHIND the text (z<0)");

      // C-004 shape PICKER: each geometry adds an element with the right variant + the
      // corner-radius control appears only for a rounded rectangle.
      document.querySelector('.td-addbar button[data-add="shape"]').click();
      ok(!el("td-shape-row").hidden, "C-004 Add Shape opens the shape picker");
      document.querySelector('#td-shape-row [data-shape="ellipse"]').click();
      ok(el("td-shape-row").hidden, "C-004 picker closes after choosing Ellipse");
      var te = applied(); var lastE = te.elements[te.elements.length-1];
      ok(lastE.kind==="shape" && lastE.variant==="ellipse", "C-004 Ellipse pick → variant=ellipse");
      ok(el("td-el-corner-row").hidden, "C-004 corner control hidden for a non-rounded shape");
      ok(el("td-el-head").textContent.indexOf("Ellipse")>=0, "C-004 inspector head names the geometry");
      // Rounded: variant + a default corner_permille + the corner control visible + editable.
      addShape("rounded_rect");
      var tr = applied(); var lastR = tr.elements[tr.elements.length-1];
      ok(lastR.variant==="rounded_rect" && lastR.corner_permille>0, "C-004 Rounded pick → variant + default corner_permille");
      ok(!el("td-el-corner-row").hidden, "C-004 corner-radius control shown for a rounded rect");
      el("td-el-corner").value = 20; el("td-el-corner").dispatchEvent(new Event("input"));
      var idxR = tr.elements.length-1;
      ok(applied().elements[idxR].corner_permille===200, "C-004 corner slider 20% → corner_permille=200");
      // Triangle pick.
      addShape("triangle");
      var tt = applied();
      ok(tt.elements[tt.elements.length-1].variant==="triangle", "C-004 Triangle pick → variant=triangle");
      // Picker Cancel adds nothing.
      var nBefore = applied().elements.length;
      document.querySelector('.td-addbar button[data-add="shape"]').click();
      el("td-shape-cancel").click();
      ok(el("td-shape-row").hidden && applied().elements.length===nBefore, "C-004 picker Cancel adds nothing");

      // #5 font weight + letter-spacing (86ajq3225): the enabled fields set the theme + persist.
      el("td-weight").value = "700"; el("td-weight").dispatchEvent(new Event("change"));
      el("td-letter").value = "0.1"; el("td-letter").dispatchEvent(new Event("change"));
      var tw = applied();
      ok(tw.weight === 700, "#5 weight select sets theme.weight=700");
      ok(tw.letter_spacing_permille === 100, "#5 letter-spacing 0.1em → permille=100");
      ok(!el("td-weight").disabled && !el("td-letter").disabled, "#5 weight + letter fields are ENABLED");
      // Regular + zero drop the fields (byte-stable default).
      el("td-weight").value = "400"; el("td-weight").dispatchEvent(new Event("change"));
      el("td-letter").value = "0"; el("td-letter").dispatchEvent(new Event("change"));
      var td = applied();
      ok(td.weight === undefined, "#5 Regular drops weight (byte-stable)");
      ok(td.letter_spacing_permille === undefined, "#5 zero letter-spacing dropped");

      // === Design 2.0: LAYERS panel + per-layer visibility + zoom + Duplicate ===
      var layersBox = el("td-layers");
      ok(!!layersBox, "D2 LAYERS panel present");
      var qLayers = function(){ return el("td-layers").querySelectorAll(".td-layer"); };
      var elRowFor = function(i){ return Array.prototype.filter.call(qLayers(), function(r){ return parseInt(r.dataset.idx,10)===i; })[0]; };
      var regionRowFor = function(k){ return Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.region===k; })[0]; };
      addShape(); // a fresh element to operate on
      var elCount = applied().elements.length;
      ok(qLayers().length === elCount + 2, "D2 LAYERS lists every element + the 2 regions (got " + qLayers().length + ")");
      var regionRows = Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.region; });
      ok(regionRows.length === 2, "D2 LAYERS includes both region rows (Title + Body)");
      ok(regionRows[0].querySelector(".td-layer-handle").getAttribute("aria-disabled")==="true",
         "D2 a region row is not reorderable (handle aria-disabled)");
      // The eye HIDES an element layer → a REAL, byte-stable `visible:false` in the Apply payload.
      var firstEl = Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.idx!==undefined; })[0];
      var idx = parseInt(firstEl.dataset.idx, 10);
      firstEl.querySelector(".td-layer-eye").click();
      ok(applied().elements[idx].visible === false, "D2 the eye HIDES a layer (visible:false in the Apply payload)");
      elRowFor(idx).querySelector(".td-layer-eye").click(); // show again
      ok(applied().elements[idx].visible === undefined, "D2 showing a layer OMITS `visible` (byte-stable JSON)");
      // Selecting a layer row selects that element; a region row selects the region.
      elRowFor(idx).click();
      ok(!el("td-el-inspector").hidden, "D2 clicking a layer row selects its element");
      regionRowFor("title").click();
      ok(el("td-el-inspector").hidden, "D2 clicking a region row selects the region");
      // The eye also hides a REGION (real region.visible flag).
      regionRowFor("title").querySelector(".td-layer-eye").click();
      ok(applied().title.visible === false, "D2 the eye hides a REGION (title.visible=false)");
      regionRowFor("title").querySelector(".td-layer-eye").click();
      ok(applied().title.visible === true, "D2 toggling a region eye shows it again");
      // Zoom: −/+ scale the preview box via a CSS var; the % readout tracks it (frontend-only).
      var z0 = parseFloat(el("td-canvas-box").style.getPropertyValue("--td-zoom") || "1");
      el("td-zoom-in").click();
      ok(parseFloat(el("td-canvas-box").style.getPropertyValue("--td-zoom")) > z0, "D2 zoom-in increases the preview scale");
      ok(el("td-zoom-v").textContent.indexOf("%")>=0, "D2 the zoom readout shows a percentage");
      el("td-zoom-out").click();
      // Duplicate: clones the current design into a new unsaved working theme (elements carry over).
      var beforeDup = applied().elements.length;
      el("td-duplicate").click();
      // Check the status SYNCHRONOUSLY (before any await): a pending Apply .then from the
      // applied() above would otherwise overwrite #td-status with "Applied…" during a sleep.
      ok(el("td-status").textContent.indexOf("Duplicated")>=0, "D2 Duplicate reports it into the status line");
      await sleep(20);
      ok(applied().elements.length === beforeDup, "D2 Duplicate clones the current design (same elements, new unsaved copy)");

      // D2 a11y (review fix): keyboard focus survives the LAYERS innerHTML rebuild.
      addShape();
      var aRow = Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.idx!==undefined; })[0];
      var aidx = parseInt(aRow.dataset.idx, 10);
      var eyeA = aRow.querySelector(".td-layer-eye"); eyeA.focus(); eyeA.click(); // hide → rebuild
      ok(document.activeElement && document.activeElement.classList.contains("td-layer-eye") &&
         document.activeElement.closest(".td-layer").dataset.idx === String(aidx),
         "D2 a11y: an eye toggle keeps focus on the same layer's eye after the rebuild");
      document.activeElement.click(); // show again (clean state)
      var rowB = elRowFor(aidx); rowB.focus();
      rowB.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowUp",altKey:true,bubbles:true})); // reorder → rebuild
      ok(document.activeElement && document.activeElement.classList.contains("td-layer") &&
         document.activeElement.dataset.idx === String(aidx),
         "D2 a11y: Alt+Arrow reorder keeps focus on the moved layer's row");

      // D2 reliability (review fix): a cancelled layer-drag tears down (no stuck reorder).
      var dragRow = elRowFor(aidx);
      var zBefore = applied().elements[aidx].z;
      dragRow.querySelector(".td-layer-handle").dispatchEvent(new PointerEvent("pointerdown",{clientX:0,clientY:0,button:0,bubbles:true,pointerId:7}));
      window.dispatchEvent(new PointerEvent("pointercancel",{pointerId:7,bubbles:true}));
      window.dispatchEvent(new PointerEvent("pointermove",{clientX:0,clientY:400,bubbles:true,pointerId:7})); // big move AFTER cancel
      ok(applied().elements[aidx].z === zBefore, "D2 a cancelled layer-drag stops reordering (pointercancel teardown)");

      // === Design 2.0: Templates strip is selectable (bug repro: "can't select templates") ===
      // "New from current" clears the selection so the builtin row is NOT current — a
      // selection CHANGE is then observable on a single builtin row (no saved-theme needed).
      el("td-new-2").click();
      await sleep(20);
      var biRow = el("td-themes").querySelector(".td-theme-row:not(.td-theme-saved)");
      ok(!!biRow, "D2 a builtin template row renders");
      ok(biRow.dataset.current === "false", "D2 precondition: the builtin is not current after New");
      // Clicking the THUMBNAIL (the dominant card target) must select the template.
      biRow.querySelector(".td-theme-thumb").click();
      await sleep(20);
      ok(el("td-themes").querySelector(".td-theme-row:not(.td-theme-saved)").dataset.current === "true",
         "D2 clicking a template THUMBNAIL selects it");
      // Deselect again; the NAME text must also select.
      el("td-new-2").click(); await sleep(20);
      el("td-themes").querySelector(".td-theme-row:not(.td-theme-saved) .td-theme-name").click();
      await sleep(20);
      ok(el("td-themes").querySelector(".td-theme-row:not(.td-theme-saved)").dataset.current === "true",
         "D2 clicking a template NAME selects it");

      // === Design 2.0: the LAYERS panel IS the z-order (reorder changes element z + list order) ===
      addShape(); // a fresh, frontmost element (z = maxZ+1)
      addShape(); // another frontmost element on top
      var topIdx = applied().elements.length - 1; // the topmost element
      var zTop = applied().elements[topIdx].z;
      // The topmost element's LAYERS row is ABOVE (earlier in DOM) the one it stacks over.
      var order1 = Array.prototype.map.call(qLayers(), function(r){ return r.dataset.idx; }).filter(function(x){ return x!==undefined; });
      ok(order1.indexOf(String(topIdx)) < order1.indexOf(String(topIdx-1)),
         "D2 LAYERS lists a higher-z element ABOVE a lower-z one (list = z-order)");
      // Reorder the topmost DOWN via the panel (Alt+ArrowDown) → its z drops below its neighbour.
      elRowFor(topIdx).focus();
      elRowFor(topIdx).dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowDown",altKey:true,bubbles:true}));
      await sleep(10);
      ok(applied().elements[topIdx].z < zTop, "D2 a LAYERS reorder changes the element's z-order (backward lowers z)");
      var order2 = Array.prototype.map.call(qLayers(), function(r){ return r.dataset.idx; }).filter(function(x){ return x!==undefined; });
      ok(order2.indexOf(String(topIdx)) > order2.indexOf(String(topIdx-1)),
         "D2 the LAYERS list re-sorts to the new z-order after a reorder");

      // === audit M1: the plan dedup key EXCLUDES view.timer (no per-second rebuild) ===
      // render() is a global function; drive it directly with crafted view deltas.
      var baseView = JSON.parse(JSON.stringify(V));
      render(baseView);                       // plan reflects baseView; lastRendered = narrowed key
      var row0 = document.querySelector("#plan .item");
      ok(!!row0, "M1 plan has a row to track");
      // (a) a view differing ONLY in timer must NOT rebuild the plan (same node identity).
      var vTimer = JSON.parse(JSON.stringify(baseView));
      vTimer.timer = { remaining_secs: 42, elapsed_secs: 8, running: true };
      render(vTimer);
      ok(document.querySelector("#plan .item") === row0,
         "M1 timer-only view delta does NOT rebuild the plan (node identity stable)");
      // (b) a genuine plan change (an added item) MUST still rebuild.
      var vItems = JSON.parse(JSON.stringify(baseView));
      vItems.items = baseView.items.concat([{id:2,kind:"song",title:"Added",is_live:false,is_staged:false}]);
      render(vItems);
      var rows2 = document.querySelectorAll("#plan .item");
      ok(rows2.length === 2 && rows2[0] !== row0,
         "M1 an items delta DOES rebuild the plan (2 fresh rows)");
      render(baseView); // restore so the trailing 1s poll stays consistent

      // === audit M4: the transcript DOM is client-capped even if the host over-sends ===
      var many = [];
      for (var mi = 0; mi < 200; mi++) many.push({ id: mi, text: "line " + mi, start_ms: mi * 1000 });
      syncTranscript({ transcript: many });
      var logEl = el("transcript-log");
      ok(logEl.children.length === 120,
         "M4 transcript DOM capped at 120 rows even when the host sends 200 (got " + logEl.children.length + ")");
      var segIds = Array.from(logEl.children).map(function (r) { return r.dataset.segId; });
      ok(segIds.indexOf("199") >= 0 && segIds.indexOf("0") < 0,
         "M4 keeps the NEWEST 120 (id 199 present, id 0 pruned)");

      // === right-column tabs: Service Timer | Detected Scriptures (Figma 430:124) ===
      var rtabTimer = el("rtab-timer"), rtabDet = el("rtab-detections");
      var rpTimer = el("rpanel-timer"), rpDet = el("rpanel-detections");
      ok(rtabTimer && rtabDet && rpTimer && rpDet, "tabs: right-column tabs + panels exist");
      ok(rtabTimer.getAttribute("aria-selected") === "true" && rpDet.hidden && !rpTimer.hidden,
         "tabs: Service Timer active on boot; the Detected panel is hidden");
      rtabDet.click();
      ok(rtabDet.getAttribute("aria-selected") === "true" && !rpDet.hidden &&
         rpTimer.hidden && rtabTimer.getAttribute("aria-selected") === "false",
         "tabs: clicking Detected Scriptures shows its panel and hides the timer");
      rtabDet.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
      ok(rtabTimer.getAttribute("aria-selected") === "true" && !rpTimer.hidden,
         "tabs: ArrowLeft moves selection back to Service Timer (real tablist)");
      // A new detection auto-surfaces the Detected tab (no focus steal) while on the timer tab.
      render(Object.assign({}, baseView, { detections: [
        { id: 991, reference: "John 3:16", text: "For God so loved the world", confidence: 95 },
      ] }));
      ok(rtabDet.getAttribute("aria-selected") === "true",
         "tabs: a new detection auto-surfaces the Detected Scriptures tab");
      var rcnt = el("detections-count");
      ok(rcnt && rcnt.hidden === false && rcnt.textContent.indexOf("1") >= 0,
         "tabs: the count badge on the tab shows the unactioned detection count");
      // A bare detection must NOT display anything: no Preview/Live change, no chapter opened.
      ok(!window.__calls.some(function(c){ return c.cmd === "get_chapter" && c.args && c.args.reference === "John 3:16"; }),
         "flow: a detection does NOT open its chapter or touch Preview/Live (nothing until Stage)");
      // Stage confirms it: approve_detection (Preview) + go_live (audience) + open the chapter.
      el("detections-list").querySelector(".det-stage").click();
      await sleep(15);
      ok(window.__calls.some(function(c){ return c.cmd === "approve_detection" && c.args && c.args.detectionId === 991; }),
         "flow: Stage → approve_detection (stages the verse in Preview)");
      ok(window.__calls.some(function(c){ return c.cmd === "go_live"; }),
         "flow: Stage → go_live (operator confirmed → pushed Live to the audience)");
      ok(window.__calls.some(function(c){ return c.cmd === "get_chapter" && c.args && c.args.reference === "John 3:16"; }),
         "flow: Stage → the full chapter opens in the Scriptures browser");
      rtabTimer.click(); render(baseView); // reset for the following checks

      // === display: recognised STT text reaches the operator through the FULL poll->render
      // path (not just a direct syncTranscript call). This is what the 1s poll does with the
      // host-authoritative view once the on-device STT source ingests segments. ===
      var sttView = Object.assign({}, baseView, { transcript: [
        { id: 9001, text: "For God so loved the world", start_ms: 5000 },
        { id: 9002, text: "that he gave his only Son", start_ms: 9000 },
      ] });
      render(sttView); // the SAME top-level render() the 1s poll invokes
      var sttLog = el("transcript-log");
      var sttEmpty = el("transcript-empty");
      ok(sttLog.children.length === 2 &&
         sttLog.textContent.indexOf("For God so loved the world") >= 0 &&
         sttLog.textContent.indexOf("that he gave his only Son") >= 0,
         "display: STT segments in view.transcript render as visible lines in #transcript-log");
      ok(sttEmpty.style.display === "none",
         "display: the empty-state overlay is hidden once transcript lines arrive");
      render(baseView); // restore so the trailing 1s poll stays consistent

      // === R4 detection: a confidence-bearing detection renders the match-% pill, colour-
      // coded green (>=90, e.g. an explicitly-spoken reference) vs amber "fuzzy" (a paraphrase). ===
      var detView = Object.assign({}, baseView, { detections: [
        { id: 501, reference: "John 3:16", text: "For God so loved the world", confidence: 95 },
        { id: 502, reference: "Psalm 23:1", text: "The Lord is my shepherd", confidence: 72 },
      ] });
      render(detView); // the SAME render() the 1s poll invokes
      var detList = el("detections-list");
      var pills = detList.querySelectorAll(".match-pill");
      ok(pills.length === 2 &&
         detList.textContent.indexOf("95% MATCH") >= 0 &&
         detList.textContent.indexOf("72% MATCH") >= 0,
         "R4: detections render a match-% pill from view.confidence (95% + 72%)");
      // #3 newest-first: the host queues oldest-first, so id 502 (last in the array) renders on top.
      var firstRef = detList.querySelector(".detection .ref");
      ok(firstRef && firstRef.textContent.indexOf("Psalm 23:1") >= 0,
         "#3 the newest detection renders at the top (host oldest-first list reversed for display)");
      ok(pills[0].className.indexOf("fuzzy") >= 0 && pills[1].className.indexOf("fuzzy") < 0,
         "R4: pill colour follows its card — newest 72% fuzzy (amber) on top, 95% solid (green) below");
      render(baseView); // restore so the trailing 1s poll stays consistent

      // === listen control: a real state machine — the button never sits silently disabled,
      // and "no transcript" is a diagnosable state, not a dead panel. ===
      var lBtn = el("transcript-listen");
      var lLabel = el("transcript-listen-label");
      var lStatus = el("transcript-status");
      ok(lLabel.textContent.indexOf("Start listening") >= 0 && !lBtn.disabled,
         "listen: idle shows 'Start listening', enabled");
      lBtn.click(); // start_listening stays pending (model load) — must show progress, not freeze
      ok(lBtn.disabled && lLabel.textContent.indexOf("Preparing") >= 0,
         "listen: clicking Start immediately shows 'Preparing…' (never a silent dead button)");
      window.__emit("stt://progress", { done: 620000000, total: 1600000000, pct: 38 });
      ok(lStatus.textContent.indexOf("38%") >= 0,
         "listen: first-run model-download progress renders (Downloading model… 38%)");
      window.__startCtl.resolve(null); // worker loaded the model + opened the mic
      await sleep(10);
      ok(!lBtn.disabled && lLabel.textContent.indexOf("Stop listening") >= 0,
         "listen: once ready the control flips to 'Stop listening' (enabled)");
      ok(lStatus.textContent.toLowerCase().indexOf("waiting for speech") >= 0,
         "listen: listening but no lines yet -> 'waiting for speech…' (makes empty transcript diagnosable)");
      // A live mic level surfaces in the waiting status so a dead/denied microphone (peak 0
      // while speaking) is visibly distinct from a working mic with recognition pending.
      window.__emit("stt://level", { pct: 0 });
      ok(lStatus.textContent.indexOf("mic 0%") >= 0,
         "listen: mic level 0 while waiting shows '(mic 0%)' — isolates a dead/denied microphone");
      window.__emit("stt://level", { pct: 42 });
      ok(lStatus.textContent.indexOf("mic 42%") >= 0,
         "listen: a live mic level shows '(mic 42%)' (audio is arriving; recognition is downstream)");
      // Sustained 0% (denied mic) turns into an actionable permission hint, not an endless wait.
      var lSub = el("transcript-empty-sub");
      for (var z = 0; z < 14; z++) window.__emit("stt://level", { pct: 0 });
      ok(lSub.textContent.indexOf("Privacy & Security") >= 0 && lSub.textContent.indexOf("Microphone") >= 0,
         "listen: a run of 0% surfaces the 'grant mic access' hint (actionable, not a dead 0%)");
      render(Object.assign({}, baseView, { transcript: [{ id: 77, text: "and it came to pass", start_ms: 1000 }] }));
      ok(lStatus.textContent.toLowerCase().indexOf("transcribing") >= 0,
         "listen: once a line is recognised, status shows 'transcribing on-device'");
      lBtn.click(); await sleep(5); // Stop -> idle
      lBtn.click();                 // Start again -> preparing/pending
      window.__startCtl.reject({ message: "This build does not include on-device speech-to-text." });
      await sleep(10);
      ok(!lBtn.disabled && lStatus.textContent.indexOf("does not include on-device") >= 0,
         "listen: a start failure surfaces the reason and re-enables the button (no silent no-op)");
      render(baseView); // restore the view for the trailing poll

      // (The Theme-Designer's MAX_ELEMENTS=64 cap is enforced + tested host-side in Rust —
      // engine/present tests — so it is not re-asserted here as a tautology.)

      // === per-screen PREVIEW (86ajq321k): the Screens page shows each Audience screen's own
      // themed output via render_screen; the three previews render + differ ===
      document.querySelector('.nav-item[data-surface="screens"]').click();
      await waitFor(function(){
        var cs = document.querySelectorAll('#screens-list canvas.screen-preview');
        return cs.length >= 3 && Array.from(cs).every(function(c){ return c.classList.contains("has-render"); });
      });
      var previews = document.querySelectorAll('#screens-list canvas.screen-preview');
      ok(previews.length === 3, "per-screen: 3 preview canvases render (main/lower-third/stream, got " + previews.length + ")");
      var byScreen = {};
      Array.from(previews).forEach(function(c){ byScreen[c.dataset.screen] = c; });
      ok(!!byScreen["main"] && !!byScreen["lower-third"] && !!byScreen["stream"],
         "per-screen: a preview canvas for each of main / lower-third / stream");
      var pixel = function(c){ return Array.from(c.getContext("2d").getImageData(0,0,1,1).data).join(","); };
      ok(pixel(byScreen["main"]) === "255,0,0,255", "per-screen: main preview shows its own themed frame (red)");
      ok(pixel(byScreen["main"]) !== pixel(byScreen["lower-third"]) &&
         pixel(byScreen["lower-third"]) !== pixel(byScreen["stream"]),
         "per-screen: the three screens render DIFFERENT designs at once");

      // === Screens page — dynamic registry: enable/disable + add/delete virtual ===
      var rowFor = function(id){ return document.querySelector('#screens-list .screen-row[data-screen="'+id+'"]'); };
      ok(!!rowFor("main") && !!rowFor("lower-third") && !!rowFor("stream") && !!rowFor("stage"),
         "registry: the four built-in screen rows render (main/lower-third/stream/stage)");
      ok(!!rowFor("main").querySelector('.screen-enable-toggle') && !rowFor("main").querySelector('.screen-delete'),
         "registry: a built-in row has an enable toggle but NO delete control");

      // Disabling a screen invokes set_screen_enabled(false) and dims the row.
      var beforeToggle = window.__calls.length;
      rowFor("lower-third").querySelector('.screen-enable-toggle').click();
      await waitFor(function(){ var r = rowFor("lower-third"); return r && r.classList.contains("screen-disabled"); });
      var disableCall = window.__calls.slice(beforeToggle).filter(function(c){ return c.cmd === "set_screen_enabled"; })[0];
      ok(disableCall && disableCall.args.screen === "lower-third" && disableCall.args.enabled === false,
         "registry: toggling a screen invokes set_screen_enabled(enabled=false)");
      ok(rowFor("lower-third").classList.contains("screen-disabled"),
         "registry: a disabled screen row is dimmed");

      // '+ Add screen' (role=stream) creates a virtual, DELETABLE row.
      document.getElementById("screen-add-role").value = "stream";
      document.getElementById("screen-add-btn").click();
      await waitFor(function(){ return !!rowFor("stream-2"); });
      ok(!!rowFor("stream-2"), "registry: '+ Add screen' creates a virtual stream-2 row");
      ok(!!rowFor("stream-2").querySelector('.screen-delete'),
         "registry: a virtual row HAS a delete control (unlike a built-in)");
      ok(window.__calls.some(function(c){ return c.cmd === "add_screen" && c.args.role === "stream"; }),
         "registry: add_screen invoked with role=stream");

      // Deleting the virtual screen invokes remove_screen and removes its row.
      rowFor("stream-2").querySelector('.screen-delete').click();
      await waitFor(function(){ return !rowFor("stream-2"); });
      ok(!rowFor("stream-2"), "registry: deleting a virtual screen removes its row");
      ok(window.__calls.some(function(c){ return c.cmd === "remove_screen" && c.args.screen === "stream-2"; }),
         "registry: remove_screen invoked for the virtual screen");

      // A REJECTED enable-toggle (RBAC-denied / older host) must revert to authoritative,
      // never leave the checkbox lying (review HIGH fix).
      window.__rejectSetEnabled = true;
      var streamCb = rowFor("stream").querySelector('.screen-enable-toggle');
      var wasChecked = streamCb.checked; // true (enabled)
      streamCb.click(); // attempt to disable — the stub rejects
      await new Promise(function(r){ setTimeout(r, 80); });
      var streamRow = rowFor("stream");
      ok(streamRow.querySelector('.screen-enable-toggle').checked === wasChecked &&
         !streamRow.classList.contains("screen-disabled"),
         "registry: a REJECTED enable-toggle reverts to authoritative (no permanent desync)");
      window.__rejectSetEnabled = false;

      // Keyboard focus survives the destructive rebuild (a11y fix): focus a toggle, activate
      // it, and focus is restored to the rebuilt equivalent control.
      var mainCb = rowFor("main").querySelector('.screen-enable-toggle');
      mainCb.focus();
      mainCb.click(); // disable main (succeeds) → full rebuild
      await waitFor(function(){ var r = rowFor("main"); return r && r.classList.contains("screen-disabled"); });
      var active = document.activeElement;
      ok(active && active.classList.contains("screen-enable-toggle") &&
         active.closest('.screen-row') && active.closest('.screen-row').dataset.screen === "main",
         "registry: keyboard focus is restored to the toggle after the rebuild (a11y)");
    } catch(e){ R.push("FAIL: exception "+e.message+" @ "+(e.stack||"").split("\n")[1]); }
    el("__r").textContent = "RESULTS\n"+R.join("\n")+"\nDONE("+R.length+")";
  }
  // Wait until app.js has BOOTED (a host call fired + the designer DOM exists), then run.
  // The designer built-ins now load lazily on first activation (audit L3), so the driver
  // opens the designer itself — we no longer gate readiness on `builtin_themes`.
  var tries=0;
  var iv=setInterval(function(){
    tries++;
    var booted = window.__calls.length > 0 && document.getElementById("td-bg");
    if (booted){ clearInterval(iv); setTimeout(run, 50); }
    else if (tries>60){ clearInterval(iv); el("__r").textContent="RESULTS\nFAIL: app never booted\nDONE(1)"; }
  }, 30);
</script>
"""

# Inject the stub into <head> (before app.js runs) and the driver before </body>.
# The <base> MUST precede the <link rel=stylesheet href="app.css"> (line ~7) — a <base>
# only affects relative URLs that come AFTER it, so injecting it at </head> left app.css
# resolving against the /tmp temp file (never loading). Inject it right after <head> so the
# real app.css (and app.js) load and CSS-dependent checks are meaningful.
html = html.replace("<head>", '<head><base href="file://' + DIST + '/">', 1)
html = html.replace("</head>", STUB + "</head>", 1)
html = html.replace("</body>", DRIVER + "</body>", 1)

with tempfile.NamedTemporaryFile(
    "w", suffix=".html", delete=False, dir=tempfile.gettempdir()
) as f:
    f.write(html)
    path = f.name

try:
    try:
        out = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--virtual-time-budget=6000", "--dump-dom", "file://" + path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90).stdout
    except subprocess.TimeoutExpired:
        # A hung Chrome is an INFRA failure (exit 2), distinct from a check FAIL (exit 1).
        print("FAIL: headless Chrome timed out (infra) — no RESULTS produced")
        sys.exit(2)
    m = re.search(r"RESULTS\n(.*?)\nDONE\((\d+)\)", out, re.S)
    if not m:
        print("NO RESULTS BLOCK — dom head:\n", out[:1500]); sys.exit(2)
    body = m.group(1)
    count = int(m.group(2))
    print(body)
    fails = [line for line in body.splitlines() if line.startswith("FAIL")]
    print("\n=== %d checks, %d FAIL ===" % (count, len(fails)))
    # Guard against the suite silently SHRINKING: a driver regression / early return that
    # runs FEWER checks would otherwise report 0 FAIL and pass. Bump EXPECTED_MIN_CHECKS
    # when you add checks; never lower it to hide a lost one.
    if count < EXPECTED_MIN_CHECKS:
        print(
            "FAIL: only %d checks ran; expected >= %d (the suite must not silently shrink)"
            % (count, EXPECTED_MIN_CHECKS)
        )
        sys.exit(4)
    sys.exit(1 if fails else 0)
finally:
    os.unlink(path)
