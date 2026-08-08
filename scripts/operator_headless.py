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
EXPECTED_MIN_CHECKS = 367


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
  // Remote Control device-management mock (86ajxer8n): mirrors the host session registry so the
  // surface's optimistic updates reconcile against consistent snapshots (roles are non-Operator —
  // the host caps remote devices at Producer).
  window.__remote = {
    devices: [
      { device_id: "dev-aa01", name: "Booth iPad", platform: "iPadOS", role: "producer", idle_secs: 3, pinned: false },
      { device_id: "dev-bb02", name: "Guest tablet", platform: "iPadOS", role: "viewer", idle_secs: 210, pinned: false },
    ],
    pending: [
      { device_id: "dev-cc03", name: "Anna's iPhone", platform: "iOS", fingerprint: "A1 B2 C3 D4", waiting_secs: 8 },
    ],
  };
  // A REAL OperatorView so the boot render path (act->render->syncChrome->renderConsole) runs
  // exactly as in the app — the prior null stub masked the #7 render never firing on launch.
  var V = { plan_name:"Svc", items:[{id:1,kind:"scripture",title:"Genesis 1:13",is_live:true,is_staged:true}],
    live_index:0, staged_index:0, blackout:false, live_authored_id:null, timer:null, staged_scripture:"Genesis 1:13",
    live_scripture:"Genesis 1:13", live_free_text:null,
    outputs:[{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080}],
    displays:[{key:"d1", name:"Main", width:1920, height:1080}], translations:["KJV"],
    theme:"classic", themes:["classic"], saved_themes:[], screen_themes:[],
    screens:[
      {screen:"main", role:"main", enabled:true, deletable:false, theme:null},
      {screen:"stage", role:"stage", enabled:true, deletable:false, theme:null}
    ] };
  var T = {
    background:{r:8,g:10,b:20,a:255},
    title:{x_permille:60,y_permille:150,w_permille:880,h_permille:110,align_h:"center",align_v:"middle",size_permille:48,line_height_permille:1200,color:{r:242,g:181,b:60,a:255},fit:"shrink_to_fit",visible:true},
    body:{x_permille:60,y_permille:280,w_permille:880,h_permille:560,align_h:"center",align_v:"middle",size_permille:78,line_height_permille:1150,color:{r:255,g:255,b:255,a:255},fit:"shrink_to_fit",visible:true}
  };
  // A DeckView (Presentation & Media, node 329:124) — the separate operator-local shape the
  // deck_* commands return (NOT the OperatorView). The stubs below mutate it so the surface's
  // add/select/edit/undo/media behaviours are exercised end to end.
  var D = {
    name:"Sermon: Grace That Feeds", count:2,
    slides:[
      {id:1, n:1, lines:["Grace That Feeds"], kind:"text"},
      {id:2, n:2, lines:["Isaiah 61:5"], kind:"text"}
    ],
    selected:2, live:null,
    slide:{ id:2, elements:[{index:0,kind:"text",label:"Isaiah 61:5",x:80,y:240,w:700,h:90,z:0,visible:true,
        text:"Isaiah 61:5",size_permille:90,line_height_permille:1100,weight:400,align_h:"left",align_v:"top",
        color:{r:240,g:240,b:245,a:255},fit:"shrink_to_fit",opacity:255}],
      selected_element:null, notes:"read slowly", transition:"fade", auto_advance_secs:null, has_background:false },
    media:{ assets:[
        {id:1,name:"harvest.jpg",path:"demo://harvest field.jpg",kind:"image",size_label:"2.4 MB",width:1920,height:1080,duration_label:null,missing:false,unused:false,uses:2},
        {id:2,name:"sunrise.jpg",path:"demo://sunrise.jpg",kind:"image",size_label:"3.1 MB",missing:false,unused:true,uses:0},
        {id:3,name:"testimony.mp4",path:"demo://testimony.mp4",kind:"video",size_label:"48 MB",duration_label:"2:14",missing:false,unused:true,uses:0},
        {id:4,name:"baptism.jpg",path:"demo://baptism.jpg",kind:"image",size_label:"2 MB",missing:true,unused:false,uses:1},
        {id:5,name:"ambient pad.wav",path:"demo://ambient pad.wav",kind:"audio",duration_label:"3:20",missing:false,unused:true,uses:0}
      ], total_label:"1.2 GB", missing_count:1, unused_count:3 },
    can_undo:false, can_redo:false
  };
  var dClone = function(){ return JSON.parse(JSON.stringify(D)); };
  var dEdit = function(){ D.can_undo = true; D.can_redo = false; return dClone(); };
  window.__TAURI__ = { core: { invoke: function(cmd, args){
    window.__calls.push({cmd:cmd, args:args});
    if (cmd === "builtin_themes") return Promise.resolve([{name:"Classic", theme:JSON.parse(JSON.stringify(T))}]);
    if (cmd === "system_fonts") return Promise.resolve(["Arial","Georgia","Helvetica Neue"]);
    if (cmd === "view") return Promise.resolve(JSON.parse(JSON.stringify(V)));
    if (cmd === "preview_theme") return Promise.resolve({rgba: btoa("\x00\x00\x00\xff"), w:1, h:1});
    if (cmd === "pick_image") return Promise.resolve("/tmp/picked.png");
    if (cmd === "remote_snapshot")
      return Promise.resolve({devices: window.__remote.devices.slice(), pending: window.__remote.pending.slice()});
    if (cmd === "remote_approve") {
      var RA = window.__remote, ri = RA.pending.findIndex(function(p){return p.device_id === args.deviceId;});
      if (ri >= 0) { var rp = RA.pending.splice(ri,1)[0];
        RA.devices.push({device_id:rp.device_id, name:rp.name, platform:rp.platform, role:(args.role==="operator"?"producer":args.role), idle_secs:0, pinned:false}); }
      return Promise.resolve({devices: RA.devices.slice(), pending: RA.pending.slice()});
    }
    if (cmd === "remote_deny") {
      window.__remote.pending = window.__remote.pending.filter(function(p){return p.device_id !== args.deviceId;});
      return Promise.resolve({devices: window.__remote.devices.slice(), pending: window.__remote.pending.slice()});
    }
    if (cmd === "remote_revoke") {
      window.__remote.devices = window.__remote.devices.filter(function(d){return d.device_id !== args.deviceId;});
      return Promise.resolve({devices: window.__remote.devices.slice(), pending: window.__remote.pending.slice()});
    }
    if (cmd === "remote_set_role") {
      if (args.role !== "operator") window.__remote.devices.forEach(function(d){ if (d.device_id === args.deviceId) d.role = args.role; });
      return Promise.resolve({devices: window.__remote.devices.slice(), pending: window.__remote.pending.slice()});
    }
    if (cmd === "remote_new_code")
      return Promise.resolve({code:"AB12CD34", fingerprint:"A1 B2 C3 D4", expires_in_secs:120});
    if (cmd === "host_connected") return Promise.resolve(!window.__psNoHost); // a real output window (unless the test says otherwise)
    if (cmd === "stt_ready") return Promise.resolve(window.__psStt || {ready:true, state:"ready", model:"Small", detail:"On-device model ready"});
    if (cmd === "disk_free")
      return Promise.resolve({available_bytes: (window.__psDiskLow ? 0.5 : 42) * 1073741824, total_bytes: 500 * 1073741824}); // 42 GB free (or <1 GB critical when flagged)
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
      // Mint the bare role name first, then role-2, role-3… — mirroring the host registry.
      var ids = V.screens.map(function(s){ return s.screen; });
      var id = args.role, n = 2;
      while (ids.indexOf(id) >= 0) { id = args.role + "-" + n; n++; }
      V.screens.push({screen: id, role: args.role, enabled:true, deletable:true, theme:null});
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
    // --- Presentation & Media (deck_* commands + render_deck_slide) ---
    // One-shot rejection hook: lets the driver exercise the error banner (role=alert) + Retry.
    if (window.__pmRejectOnce && cmd.indexOf("deck_") === 0) { window.__pmRejectOnce = false; return Promise.reject("simulated host rejection"); }
    // One-shot DEFER hook: hold the next deck command pending so the driver can observe the
    // in-flight aria-busy loading state, then resolve it. Mirrors a slow host round-trip.
    if (window.__pmDeferOnce && cmd.indexOf("deck_") === 0) {
      window.__pmDeferOnce = false;
      return new Promise(function(res){ window.__pmDeferred = function(){ res(dEdit()); }; });
    }
    if (cmd === "deck_view") return Promise.resolve(dClone());
    // --- Presentations Library (deck_list/new/open/rename/duplicate/delete) ---
    var LIB = window.__LIB || (window.__LIB = {
      decks: [
        {id:1, name:"Sunday Service — Aug 4", slides:24},
        {id:2, name:"Sermon: Grace That Feeds", slides:2},  // the open deck (matches D)
        {id:3, name:"Youth Night — Identity", slides:12}
      ],
      open: 2, persistent: true, nextId: 4
    });
    var libView = function(){ return { decks: LIB.decks.map(function(d){return {id:d.id,name:d.name,slides:d.slides};}), open: LIB.open, persistent: LIB.persistent }; };
    var libUnique = function(base){ var n=base, k=2; var names=LIB.decks.map(function(d){return d.name;}); while(names.indexOf(n)>=0){ n=base+" ("+k+")"; k++; } return n; };
    if (cmd === "deck_list") return Promise.resolve(libView());
    if (cmd === "deck_new") {
      var nid=LIB.nextId++; var nm=libUnique((args.name&&args.name.trim())||"Untitled presentation");
      LIB.decks.push({id:nid, name:nm, slides:1}); LIB.open=nid;
      D.name=nm; D.count=1; return Promise.resolve(dClone()); // DeckView (opens the editor)
    }
    if (cmd === "deck_open") {
      var od=LIB.decks.filter(function(x){return x.id===args.id;})[0];
      if (od){ LIB.open=od.id; D.name=od.name; D.count=od.slides; } return Promise.resolve(dClone());
    }
    if (cmd === "deck_rename") {
      var rd=LIB.decks.filter(function(x){return x.id===args.id;})[0];
      if (rd){ rd.name=libUnique((args.name&&args.name.trim())||"Untitled presentation"); if(LIB.open===rd.id) D.name=rd.name; } return Promise.resolve(libView());
    }
    if (cmd === "deck_duplicate") {
      var sd=LIB.decks.filter(function(x){return x.id===args.id;})[0];
      if (sd){ LIB.decks.push({id:LIB.nextId++, name:libUnique(sd.name+" copy"), slides:sd.slides}); } return Promise.resolve(libView());
    }
    if (cmd === "deck_delete") {
      var wasOpen=(LIB.open===args.id);
      LIB.decks=LIB.decks.filter(function(x){return x.id!==args.id;});
      if (wasOpen){ if(LIB.decks.length){ LIB.open=LIB.decks[0].id; D.name=LIB.decks[0].name; D.count=LIB.decks[0].slides; } else { LIB.decks.push({id:LIB.nextId++, name:"Untitled presentation", slides:1}); LIB.open=LIB.decks[0].id; D.name="Untitled presentation"; D.count=1; } }
      return Promise.resolve(libView());
    }
    if (cmd === "render_deck_slide")
      return Promise.resolve({available:true, frame:{w:2, h:1, rgba: btoa("\x33\x2b\x5a\xff\x1a\x1d\x27\xff")}});
    if (cmd === "deck_add_slide") {
      var nid = D.slides.length + 1;
      D.slides.push({id:nid, n:nid, lines:["Empty slide"], kind:"text"});
      D.count = D.slides.length; D.selected = nid;
      D.slide = {id:nid, elements:[], selected_element:null, notes:"", transition:"cut", auto_advance_secs:null, has_background:false};
      return Promise.resolve(dEdit());
    }
    if (cmd === "deck_select_slide") {
      D.selected = args.id;
      D.slide = {id:args.id, elements:[], selected_element:null, notes:"", transition:"cut", auto_advance_secs:null, has_background:false};
      return Promise.resolve(dClone());
    }
    if (cmd === "deck_add_element") {
      var ne = {index:D.slide.elements.length, kind:args.kind, x:200,y:430,w:600,h:160,z:0,visible:true, opacity:255};
      if (args.kind === "text") { ne.label="Text"; ne.text="Text"; ne.size_permille=90; ne.line_height_permille=1100; ne.weight=400; ne.align_h="left"; ne.align_v="top"; ne.color={r:240,g:240,b:245,a:255}; ne.fit="shrink_to_fit"; }
      else { ne.label="Shape"; ne.fill={r:124,g:92,b:255,a:255}; ne.border={r:0,g:0,b:0,a:0}; ne.border_permille=0; ne.corner_permille=16; ne.variant="rect"; }
      D.slide.elements.push(ne);
      D.slide.selected_element = D.slide.elements.length - 1;
      return Promise.resolve(dEdit());
    }
    if (cmd === "deck_add_image_element") {
      D.slide.elements.push({index:D.slide.elements.length, kind:"image", label:"img", name:"harvest.jpg", source:"demo://harvest field.jpg", missing:false, x:200,y:250,w:600,h:460,z:0,visible:true, opacity:255, fit:"stretch"});
      D.slide.selected_element = D.slide.elements.length - 1;
      return Promise.resolve(dEdit());
    }
    if (cmd === "deck_update_element") {
      var eu = D.slide.elements[args.index]; if (eu) { for (var k in args.patch) eu[k] = args.patch[k]; } return Promise.resolve(dEdit());
    }
    if (cmd === "deck_replace_element_image") {
      var er = D.slide.elements[args.index], ar = D.media.assets.filter(function(a){return a.id===args.mediaId;})[0];
      if (er && ar) { er.source = ar.path; er.name = ar.name; er.missing = false; } return Promise.resolve(dEdit());
    }
    if (cmd === "deck_select_element") { D.slide.selected_element = args.index; return Promise.resolve(dClone()); }
    if (cmd === "deck_move_element") {
      var e = D.slide.elements[args.index]; if (e) { e.x=args.x; e.y=args.y; e.w=args.w; e.h=args.h; }
      D.slide.selected_element = args.index; return Promise.resolve(dEdit());
    }
    if (cmd === "deck_set_element_z") { var e2=D.slide.elements[args.index]; if(e2) e2.z=args.z; return Promise.resolve(dEdit()); }
    if (cmd === "deck_reorder_elements") { var n=D.slide.elements.length; args.order.forEach(function(i,k){ if(D.slide.elements[i]) D.slide.elements[i].z = n-1-k; }); return Promise.resolve(dEdit()); }
    if (cmd === "deck_set_element_text") { var et=D.slide.elements[args.index]; if(et && et.kind==="text"){ et.text=args.text; et.label=(args.text||"").split("\\n")[0]; } return Promise.resolve(dEdit()); }
    if (cmd === "deck_toggle_element_visible") { var e3=D.slide.elements[args.index]; if(e3) e3.visible=!e3.visible; return Promise.resolve(dEdit()); }
    if (cmd === "deck_remove_element") { D.slide.elements.splice(args.index,1); D.slide.selected_element=null; return Promise.resolve(dEdit()); }
    if (cmd === "deck_set_notes") { D.slide.notes = args.notes; return Promise.resolve(dEdit()); }
    if (cmd === "deck_set_transition") { D.slide.transition = args.transition; return Promise.resolve(dEdit()); }
    if (cmd === "deck_set_auto_advance") { D.slide.auto_advance_secs = args.secs; return Promise.resolve(dEdit()); }
    if (cmd === "deck_undo") { D.can_undo = false; D.can_redo = true; return Promise.resolve(dClone()); }
    if (cmd === "deck_redo") { D.can_redo = false; D.can_undo = true; return Promise.resolve(dClone()); }
    if (cmd === "deck_go_live") { D.live = D.selected; V.live_authored_id = D.selected; return Promise.resolve(dClone()); }
    if (cmd === "deck_go_live_delta") {
      var gids = D.slides.map(function(s){ return s.id; });
      var gcur = (V.live_authored_id != null) ? gids.indexOf(V.live_authored_id) : gids.indexOf(D.selected);
      if (gcur < 0) gcur = 0;
      var gnx = Math.max(0, Math.min(gids.length - 1, gcur + args.delta));
      D.selected = gids[gnx]; D.live = gids[gnx]; V.live_authored_id = gids[gnx];
      return Promise.resolve(dClone());
    }
    if (cmd === "output_connected") return Promise.resolve(window.__outputConnected !== false);
    if (cmd === "deck_remove_slide") {
      D.slides = D.slides.filter(function(s){ return s.id !== args.id; });
      D.count = D.slides.length;
      D.slides.forEach(function(s, i){ s.n = i + 1; });
      return Promise.resolve(dEdit());
    }
    if (cmd === "deck_duplicate_slide" || cmd === "deck_reorder_slide")
      return Promise.resolve(dEdit());
    if (cmd === "deck_import_image") {
      D.media.assets.push({id:99,name:"picked.png",kind:"image",size_label:"1.0 MB",missing:false,unused:true});
      D.media.unused_count += 1; return Promise.resolve(dClone());
    }
    if (cmd === "deck_remove_media") return Promise.resolve(dClone());
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

      // (The numeric X/Y/W/H fields were removed — position is edited on the canvas: keyboard.)
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

      // Region regression: selecting a region (via the LAYERS row — the Region picker was
      // removed) hides the element inspector and shows the region-layout controls.
      el("td-layers").querySelector('.td-layer[data-region="title"]').click();
      ok(el("td-el-inspector").hidden, "selecting a region hides the element inspector");
      ok(el("td-region-align").style.display!=="none", "region layout controls visible in region mode");

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
      el("td-layers").querySelector('.td-layer[data-region="body"]').click(); // select the large Body region (LAYERS row)
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
      // The Region picker was removed — the active region is named in the inspector header.
      ok(el("td-insp-title").textContent.indexOf("Reference")>=0,
         "canvas: clicking the Reference/Title text selects that region (header names it)");
      var pb = toClient(500, 500); // inside the body rect (y 280..840)
      box.dispatchEvent(new PointerEvent("pointerdown",{clientX:pb.x,clientY:pb.y,button:0,bubbles:true,pointerId:3}));
      ok(el("td-insp-title").textContent==="Body",
         "canvas: clicking the Body text selects the Body region (header names it)");

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
      // Review fix: the selected layer row exposes aria-current (not colour-only) to AT.
      ok(el("td-layers").querySelector(".td-layer.sel") &&
         el("td-layers").querySelector(".td-layer.sel").getAttribute("aria-current")==="true",
         "D2 a11y: the selected layer row exposes aria-current to assistive tech");
      // Review fix: Enter on a layer's EYE must NOT steal row selection (keyboard/pointer parity)
      // — row.onkeydown bails for keydowns originating on the child eye button.
      var elRowsK = Array.prototype.filter.call(qLayers(), function(r){ return r.dataset.idx!==undefined; });
      if (elRowsK.length >= 2) {
        var aK = parseInt(elRowsK[0].dataset.idx,10), bK = parseInt(elRowsK[1].dataset.idx,10);
        elRowFor(aK).click(); // select layer A
        elRowFor(bK).querySelector(".td-layer-eye").dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",bubbles:true}));
        ok(el("td-layers").querySelector('.td-layer[data-idx="'+aK+'"]').classList.contains("sel"),
           "D2 a11y: Enter on a layer's eye does not steal selection from another row");
      }

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

      // === Design 2.0: collapsible Templates row (gives the canvas more room) ===
      var tmpl = document.querySelector(".td-templates");
      var tgl = el("td-templates-toggle");
      ok(!!(tmpl && tgl), "D2 templates collapse toggle present");
      ok(!tmpl.classList.contains("collapsed") && tgl.getAttribute("aria-expanded")==="true", "D2 templates start expanded");
      tgl.click();
      ok(tmpl.classList.contains("collapsed") && tgl.getAttribute("aria-expanded")==="false", "D2 toggle collapses the templates row (#td-panel hidden via CSS)");
      tgl.click();
      ok(!tmpl.classList.contains("collapsed") && tgl.getAttribute("aria-expanded")==="true", "D2 toggling again expands the templates row");
      // Review fix (HIGH): "Save theme" while Templates are collapsed must EXPAND the strip so
      // the save form (inside the collapsible #td-panel) is visible — not a silent no-op.
      tgl.click(); // collapse
      ok(tmpl.classList.contains("collapsed"), "D2 precondition: templates collapsed before Save");
      el("td-save").click(); // the topbar "Save theme" CTA
      ok(!tmpl.classList.contains("collapsed") && tgl.getAttribute("aria-expanded")==="true", "D2 Save-theme expands the collapsed Templates strip (no silent no-op)");
      ok(!el("td-save-row").hidden, "D2 Save-theme reveals the save-name form");
      el("td-save-cancel").click();
      // The Region picker + numeric X/Y/W/H + Lock were removed from the inspector.
      ok(!el("td-region") && !el("td-x") && !el("td-lock"), "D2 inspector trimmed: Region picker + X/Y/W/H + Lock removed");

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

      // === Timer | Stage sub-tab: stage theme picker + production-message composer (stage-only) ===
      rtabTimer.click(); // back to the Service Timer tab
      var segTimer = el("seg-timer"), segStage = el("seg-stage");
      var stabTimer = el("stab-timer"), stabStage = el("stab-stage");
      ok(segTimer && segStage && stabTimer && stabStage, "stage: the Timer|Stage sub-tabs + panels exist");
      ok(!stabTimer.hidden && stabStage.hidden, "stage: the Timer sub-panel shows first");
      segStage.click();
      ok(!stabStage.hidden && stabTimer.hidden && segStage.getAttribute("aria-selected") === "true",
         "stage: clicking Stage reveals the theme/message panel");
      // Theme picker -> set_stage_template.
      var scriptureCard = document.querySelector('#stage-themes .stage-theme[data-template="scripture"]');
      scriptureCard.click();
      ok(window.__calls.some(function(c){ return c.cmd === "set_stage_template" && c.args.template === "scripture"; }),
         "stage: a theme card invokes set_stage_template(scripture)");
      // Preset chip -> set_stage_message with its text.
      var preset = document.querySelector('#stage-presets .stage-preset');
      preset.click();
      ok(window.__calls.some(function(c){ return c.cmd === "set_stage_message" && c.args.text === preset.dataset.msg; }),
         "stage: a preset chip invokes set_stage_message with its text");
      // Custom field + Send -> set_stage_message(custom).
      el("stage-msg-input").value = "HOLD FOR PRAYER";
      el("stage-msg-send").click();
      ok(window.__calls.some(function(c){ return c.cmd === "set_stage_message" && c.args.text === "HOLD FOR PRAYER"; }),
         "stage: the custom field + Send invokes set_stage_message(custom)");
      // Clear -> set_stage_message("").
      el("stage-msg-clear").click();
      ok(window.__calls.some(function(c){ return c.cmd === "set_stage_message" && c.args.text === ""; }),
         "stage: Clear invokes set_stage_message with an empty string");
      // syncStage reflects the host's authoritative template + live message.
      render(Object.assign({}, baseView, { stage_template: "timer-only", stage_message: "WRAP UP NOW" }));
      var toCard = document.querySelector('#stage-themes .stage-theme[data-template="timer-only"]');
      ok(toCard.classList.contains("active") && toCard.getAttribute("aria-checked") === "true",
         "stage: syncStage marks the host's active template (timer-only)");
      var msgActive = el("stage-msg-active");
      ok(msgActive && !msgActive.hidden && msgActive.textContent.indexOf("WRAP UP NOW") >= 0,
         "stage: syncStage shows the live production message");
      // Restore the detection the following flow test depends on (do NOT clear it).
      render(Object.assign({}, baseView, { detections: [
        { id: 991, reference: "John 3:16", text: "For God so loved the world", confidence: 95 },
      ] }));
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
      // #1 real-time streaming: the in-progress interim renders as a live partial line and
      // clears when the utterance finalises (no partial_transcript).
      render(Object.assign({}, baseView, { partial_transcript: "and it came to" }));
      var partialEl = el("transcript-partial");
      ok(partialEl && !partialEl.hidden && partialEl.textContent.indexOf("and it came to") >= 0,
         "stream: a streaming interim renders as the live partial line");
      render(baseView);
      ok(partialEl.hidden, "stream: the partial line clears when the interim finalises");
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
      ok(getComputedStyle(el("transcript-meter")).display === "none",
         "listen: the mic-level meter is hidden when idle (computed display, not just [hidden])");
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
      // A live mic level drives the VISUAL meter (shown only while listening) so a dead/denied
      // microphone (peak 0 while speaking) is visibly distinct from a working mic with recognition
      // pending. role=meter + a numeric % (not colour-only).
      var lMeter = el("transcript-meter");
      var lMeterFill = el("transcript-meter-fill");
      var lMeterVal = el("transcript-meter-val");
      ok(lMeter && getComputedStyle(lMeter).display !== "none" && lMeter.getAttribute("role") === "meter",
         "listen: the mic-level meter (role=meter) is shown while listening");
      window.__emit("stt://level", { pct: 0 });
      ok(lMeter.getAttribute("aria-valuenow") === "0" && lMeterVal.textContent === "0%" && lMeterFill.style.width === "0%",
         "listen: mic level 0 sets the meter to 0% (isolates a dead/denied microphone)");
      window.__emit("stt://level", { pct: 42 });
      ok(lMeter.getAttribute("aria-valuenow") === "42" && lMeterVal.textContent === "42%" && lMeterFill.style.width === "42%",
         "listen: a live mic level fills the meter to 42% (audio arriving; recognition downstream)");
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

      // === per-screen PREVIEW (86ajq321k): only Audience + Stage are built in now, so ADD the
      // two secondary Audience feeds on demand; then all three previews render + differ ===
      document.querySelector('.nav-item[data-surface="screens"]').click();
      var rowFor = function(id){ return document.querySelector('#screens-list .screen-row[data-screen="'+id+'"]'); };
      var addFeed = function(role){
        document.getElementById("screen-add-role").value = role;
        document.getElementById("screen-add-btn").click();
      };
      addFeed("lower-third");
      await waitFor(function(){ return !!rowFor("lower-third"); });
      addFeed("stream");
      await waitFor(function(){ return !!rowFor("stream"); });
      await waitFor(function(){
        var cs = document.querySelectorAll('#screens-list canvas.screen-preview');
        return cs.length >= 3 && Array.from(cs).every(function(c){ return c.classList.contains("has-render"); });
      });
      var previews = document.querySelectorAll('#screens-list canvas.screen-preview');
      ok(previews.length === 3, "per-screen: 3 preview canvases render (main + added lower-third/stream, got " + previews.length + ")");
      var byScreen = {};
      Array.from(previews).forEach(function(c){ byScreen[c.dataset.screen] = c; });
      ok(!!byScreen["main"] && !!byScreen["lower-third"] && !!byScreen["stream"],
         "per-screen: a preview canvas for each of main / lower-third / stream");
      var pixel = function(c){ return Array.from(c.getContext("2d").getImageData(0,0,1,1).data).join(","); };
      ok(pixel(byScreen["main"]) === "255,0,0,255", "per-screen: main preview shows its own themed frame (red)");
      ok(pixel(byScreen["main"]) !== pixel(byScreen["lower-third"]) &&
         pixel(byScreen["lower-third"]) !== pixel(byScreen["stream"]),
         "per-screen: the three screens render DIFFERENT designs at once");

      // === Screens page — dynamic registry: only Audience + Stage are built in; the added
      // feeds are deletable virtuals ===
      ok(!!rowFor("main") && !!rowFor("stage"),
         "registry: the two built-in outputs render (Audience main + Stage)");
      ok(!rowFor("main").querySelector('.screen-delete') && !rowFor("stage").querySelector('.screen-delete'),
         "registry: a built-in output has an enable toggle but NO delete control");
      ok(!!rowFor("lower-third").querySelector('.screen-delete') && !!rowFor("stream").querySelector('.screen-delete'),
         "registry: an ADDED virtual feed HAS a delete control (unlike a built-in)");
      ok(window.__calls.some(function(c){ return c.cmd === "add_screen" && c.args.role === "stream"; }),
         "registry: '+ Add virtual output' invoked add_screen with role=stream");

      // Disabling a screen invokes set_screen_enabled(false) and dims the row.
      var beforeToggle = window.__calls.length;
      rowFor("lower-third").querySelector('.screen-enable-toggle').click();
      await waitFor(function(){ var r = rowFor("lower-third"); return r && r.classList.contains("screen-disabled"); });
      var disableCall = window.__calls.slice(beforeToggle).filter(function(c){ return c.cmd === "set_screen_enabled"; })[0];
      ok(disableCall && disableCall.args.screen === "lower-third" && disableCall.args.enabled === false,
         "registry: toggling a screen invokes set_screen_enabled(enabled=false)");
      ok(rowFor("lower-third").classList.contains("screen-disabled"),
         "registry: a disabled screen row is dimmed");

      // A SECOND stream feed mints stream-2 (the bare `stream` id is taken); delete it.
      addFeed("stream");
      await waitFor(function(){ return !!rowFor("stream-2"); });
      ok(!!rowFor("stream-2") && !!rowFor("stream-2").querySelector('.screen-delete'),
         "registry: a second stream feed mints stream-2 with a delete control");
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

      // === Output cap: '+ Add virtual output' disables at the 8-output maximum (MAX_SCREENS) ===
      var addBtnCap = document.getElementById("screen-add-btn");
      var addRoleCap = document.getElementById("screen-add-role");
      var rowCount = function(){ return document.querySelectorAll('#screens-list .screen-row').length; };
      // Fill to the cap with virtual stream feeds (the registry currently holds 4 outputs).
      var capGuard = 0;
      while (rowCount() < 8 && !addBtnCap.disabled && capGuard++ < 12) {
        addFeed("stream");
        await new Promise(function(r){ setTimeout(r, 40); });
      }
      ok(rowCount() === 8, "cap: the registry fills to the 8-output maximum (got " + rowCount() + ")");
      ok(addBtnCap.disabled && addRoleCap.disabled,
         "cap: '+ Add virtual output' + role picker are DISABLED at the 8-output maximum");
      ok(/aximum of 8/.test(addBtnCap.getAttribute("aria-label") || ""),
         "cap: the disabled add affordance announces the 8-output maximum (a11y)");
      // Deleting a virtual output drops below the cap and re-enables the affordance.
      var lastV = Array.from(document.querySelectorAll('#screens-list .screen-row'))
        .map(function(r){ return r.dataset.screen; })
        .filter(function(id){ return /^stream-/.test(id); }).pop();
      rowFor(lastV).querySelector('.screen-delete').click();
      await waitFor(function(){ return !addBtnCap.disabled; });
      ok(!addBtnCap.disabled && !addRoleCap.disabled,
         "cap: deleting an output re-enables '+ Add virtual output' below the cap");

      // === Design 2.0 INSPECTOR: the per-output config controls drive the new backend
      // commands (orientation / scaling / mirror / delay / frame-rate / safe-area / layers). ===
      var insp = document.getElementById("screens-inspector");
      ok(!!insp && /DISPLAY/.test(insp.textContent) && /APPEARANCE/.test(insp.textContent)
         && /VISIBLE LAYERS/.test(insp.textContent) && /TIMING/.test(insp.textContent)
         && /DEVICE/.test(insp.textContent),
         "inspector: the selected output shows DISPLAY / APPEARANCE / VISIBLE LAYERS / TIMING / DEVICE");
      // The connected pill reflects the assigned physical outputs (honest count).
      ok(/connected/.test((document.getElementById("screens-conn")||{}).textContent||""),
         "inspector: the topbar shows an honest '<n> connected' pill");
      var setSel = function(aria, val){
        var s = insp.querySelector('select[aria-label="'+aria+'"]');
        s.value = String(val); s.dispatchEvent(new Event("change"));
      };
      var togInsp = function(aria){ insp.querySelector('input[aria-label="'+aria+'"]').click(); };
      var lastCall = function(cmd){
        var m = window.__calls.filter(function(c){ return c.cmd === cmd; }); return m[m.length-1];
      };
      setSel("Target frame rate for main", 30);
      ok((lastCall("set_output_frame_rate")||{}).args && lastCall("set_output_frame_rate").args.fps === 30
         && lastCall("set_output_frame_rate").args.screen === "main",
         "inspector: Frame rate → set_output_frame_rate(fps=30)");
      setSel("Orientation for main", 1);
      ok((lastCall("set_output_orientation")||{}).args && lastCall("set_output_orientation").args.quarterTurns === 1,
         "inspector: Orientation → set_output_orientation(quarterTurns=1)");
      setSel("Scaling and fit for main", "fit");
      ok((lastCall("set_output_scale_fit")||{}).args && lastCall("set_output_scale_fit").args.fit === "fit",
         "inspector: Scaling/fit → set_output_scale_fit(fit=fit)");
      setSel("Output delay for main", 40);
      ok((lastCall("set_output_delay")||{}).args && lastCall("set_output_delay").args.ms === 40,
         "inspector: Output delay → set_output_delay(ms=40)");
      togInsp("Mirror main horizontally");
      ok((lastCall("set_output_mirror")||{}).args && lastCall("set_output_mirror").args.on === true,
         "inspector: Mirror → set_output_mirror(on=true)");
      togInsp("Show safe-area guides on the operator preview for main");
      ok((lastCall("set_output_safe_area")||{}).args && lastCall("set_output_safe_area").args.on === true,
         "inspector: Safe-area guides → set_output_safe_area(on=true)");
      togInsp("Lower third layer on main");
      ok((lastCall("set_screen_layer_visible")||{}).args
         && lastCall("set_screen_layer_visible").args.layer === "lower-third"
         && lastCall("set_screen_layer_visible").args.visible === false,
         "inspector: a VISIBLE LAYERS toggle → set_screen_layer_visible(layer, visible=false)");

      // === NDI OUTPUT: an audience feed can be set up as an NDI source (name + broadcast). ===
      var streamCard = rowFor("stream");
      Array.from(streamCard.querySelectorAll("button")).filter(function(b){ return b.textContent === "Configure"; })[0].click();
      await waitFor(function(){ return /NDI OUTPUT/.test(document.getElementById("screens-inspector").textContent); });
      var insp2 = document.getElementById("screens-inspector");
      ok(/NDI OUTPUT/.test(insp2.textContent), "inspector: an audience feed shows an NDI OUTPUT section");
      var ndiName = insp2.querySelector('input[aria-label="NDI source name for stream"]');
      ok(!!ndiName, "inspector: NDI section has a source-name input");
      ndiName.value = "Test NDI"; ndiName.dispatchEvent(new Event("change"));
      insp2.querySelector('input[aria-label="Broadcast stream as an NDI source"]').click();
      ok(window.__calls.some(function(c){
           return c.cmd === "set_ndi_output" && c.args.screen === "stream"
             && c.args.name === "Test NDI" && c.args.enabled === true;
         }),
         "inspector: NDI name + broadcast toggle → set_ndi_output(screen=stream, name, enabled=true)");

      // === Presentation & Media surface (Design 2.0, node 329:124) ===
      var pmNav = document.querySelector('.nav-item[data-surface="presentation"]');
      ok(!!pmNav && pmNav.getAttribute("aria-disabled") !== "true", "PM: the Presentation nav item is ACTIVATED (not a disabled 'later' affordance)");
      ok(pmNav && pmNav.dataset.nodigit, "PM: the Presentation item is data-nodigit (keeps the ⌘1–6 map intact)");
      pmNav.click();
      ok(el("surface-presentation").classList.contains("active"), "PM: clicking the nav item activates #surface-presentation");
      // --- Track B: browse/present/edit flow (story 86ajxeq17) ---
      // Nav lands on the LIBRARY (not the editor); grid + editor are hidden.
      ok(!el("pm-library").hidden && getComputedStyle(el("pm-library")).display !== "none", "PM/B: presentation nav lands on the Library (visible)");
      ok(el("pm-grid").hidden, "PM/B: the slide grid is hidden until a presentation is opened");
      ok(getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display === "none", "PM/B: the editor body is hidden on the Library");
      // Deck-open FAILURE stays on the Library (never a blank grid).
      await waitFor(function(){ return el("pm-lib-grid").querySelector(".pm-lib-open"); });
      window.__pmRejectOnce = true;
      el("pm-lib-grid").querySelector(".pm-lib-open").click();
      await waitFor(function(){ return !el("pm-error").hidden; });
      ok(el("pm-grid").hidden && !el("pm-library").hidden, "PM/B3: a failed deck_open stays on the Library (no blank grid)");
      ok(!el("pm-error").hidden, "PM/B3: a failed deck_open surfaces an error");
      if (el("pm-error-dismiss")) el("pm-error-dismiss").click();
      // Open a presentation card → the slide GRID.
      el("pm-lib-grid").querySelector(".pm-lib-open").click();
      await waitFor(function(){ return !el("pm-grid").hidden && el("pm-grid-tiles").querySelectorAll(".pm-tile").length > 0; });
      ok(!el("pm-grid").hidden, "PM/B: opening a presentation shows the slide GRID");
      ok(el("pm-library").hidden, "PM/B: the Library is hidden in grid mode");
      var pmTiles = el("pm-grid-tiles").querySelectorAll(".pm-tile");
      ok(pmTiles.length === 2, "PM/B: the grid renders one tile per slide (" + pmTiles.length + ")");
      // The 'no slides yet' empty-state must be TRULY hidden when the deck HAS slides. The box
      // carries an author `display: grid`, which defeats the UA `[hidden]{display:none}` in
      // WKWebView unless a `.pm-grid-empty[hidden]{display:none}` guard wins — assert the
      // COMPUTED display, not just the attribute (a stale empty-state otherwise overlays a
      // populated deck; cf. the .td-ctx/.pm-transport guards).
      ok(el("pm-grid-empty").hidden && getComputedStyle(el("pm-grid-empty")).display === "none",
         "PM/B: the 'no slides yet' empty-state is truly hidden when the deck HAS slides (computed display, not just [hidden])");
      ok(getComputedStyle(el("pm-grid-tiles")).display !== "none",
         "PM/B: the slide-tiles grid is visible when the deck HAS slides");
      ok(window.__calls.some(function(c){ return c.cmd === "render_deck_slide"; }), "PM/B: grid thumbnails compose via render_deck_slide");
      // Single-click SELECTS (safe — no go-live).
      var glBeforeSel = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
      pmTiles[0].dispatchEvent(new MouseEvent("click", {bubbles:true}));
      ok(pmTiles[0].classList.contains("sel"), "PM/B: single-click selects a slide (safe cursor ring)");
      ok(!pmTiles[0].classList.contains("live"), "PM/B: single-click does NOT go live");
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length === glBeforeSel, "PM/B: single-click fires no deck_go_live");
      // Double-click PRESENTS live → the red LIVE ring on that tile. (Slide 2 keeps the host
      // selection at 2 so the editor checks below still read 'Slide 2 / 2'.)
      pmTiles[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return el("pm-grid-tiles").querySelector(".pm-tile.live"); });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_go_live"; }), "PM/B: double-click presents the slide live (deck_go_live)");
      ok(el("pm-grid-tiles").querySelector(".pm-tile.live"), "PM/B: the live slide shows the red LIVE ring");
      // --- Slice 2: transport + arrows advance live (deck_go_live_delta) + host-truth ring ---
      await waitFor(function(){ return !el("pm-transport").hidden; });
      ok(!el("pm-transport").hidden, "PM/B2: the transport bar shows once a slide is live");
      ok(el("pm-next").getAttribute("aria-disabled") === "true", "PM/B2: Next is disabled at the last live slide");
      ok(el("pm-prev").getAttribute("aria-disabled") !== "true", "PM/B2: Previous is enabled when not at the first slide");
      // ◀ Previous advances live via deck_go_live_delta(-1) → host-truth ring moves to slide 1.
      el("pm-prev").click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_go_live_delta" && c.args.delta === -1; }); });
      ok(true, "PM/B2: Previous advances live via deck_go_live_delta(-1)");
      await waitFor(function(){ var t = el("pm-grid-tiles").querySelectorAll(".pm-tile")[0]; return t && t.classList.contains("live"); });
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[0].classList.contains("live"), "PM/B2: host-truth LIVE ring moved to slide 1 (view().live_authored_id)");
      ok(el("pm-next").getAttribute("aria-disabled") !== "true", "PM/B2: Next re-enables after leaving the last slide");
      // A keyboard arrow while LIVE advances live (deck_go_live_delta(+1)) → back to slide 2.
      var deltaBefore = window.__calls.filter(function(c){ return c.cmd === "deck_go_live_delta"; }).length;
      el("pm-grid-tiles").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", bubbles:true}));
      await waitFor(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_go_live_delta"; }).length > deltaBefore; });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_go_live_delta" && c.args.delta === 1; }), "PM/B2: a keyboard arrow while live advances live (deck_go_live_delta(+1))");
      await waitFor(function(){ var t = el("pm-grid-tiles").querySelectorAll(".pm-tile")[1]; return t && t.classList.contains("live"); });
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("live"), "PM/B2: arrows advance the LIVE ring (now slide 2)");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].tabIndex === 0, "PM/B2: focus/cursor follows live (the live tile is the roving-focus target)");
      // --- Slice 3: §8 states (preview-only, blackout, go-live failure) ---
      // Preview-only honesty: no audience output → a "Preview only" badge, never a false LIVE.
      window.__outputConnected = false;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return !el("pm-grid-badge").hidden; });
      ok(!el("pm-grid-badge").hidden && el("pm-grid-badge").textContent.indexOf("Preview only") >= 0, "PM/B3: no audience output → 'Preview only' badge (honest, not a false LIVE)");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("preview") && !el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("live"), "PM/B3: preview-only shows a distinct PREVIEW ring, NOT a true red LIVE ring");
      ok(el("pm-tp-live").textContent.indexOf("PREVIEW") >= 0, "PM/B3: the transport reads PREVIEW (not LIVE) with no audience output");
      window.__outputConnected = true;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return el("pm-grid-badge").hidden; });
      ok(el("pm-grid-badge").hidden, "PM/B3: the badge clears once the audience output is connected");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("live"), "PM/B3: reconnecting restores the true red LIVE ring");
      // Blackout is shown IN WORDS on the transport (never an ambiguous blank).
      V.blackout = true;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return el("pm-tp-live").textContent.indexOf("BLACKED OUT") >= 0; });
      ok(el("pm-tp-live").textContent.indexOf("BLACKED OUT") >= 0, "PM/B3: blackout is shown in words on the transport");
      V.blackout = false;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return el("pm-tp-live").textContent.indexOf("● LIVE") >= 0; });
      ok(el("pm-tp-live").textContent.indexOf("● LIVE") >= 0, "PM/B3: the transport returns to '● LIVE' when blackout clears");
      // Go-live FAILURE: a rejected present surfaces the error banner; the LIVE ring stays put.
      window.__pmRejectOnce = true;
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[0].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await waitFor(function(){ return !el("pm-error").hidden; });
      ok(!el("pm-error").hidden, "PM/B3: a rejected present surfaces the error banner (role=alert)");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].classList.contains("live"), "PM/B3: the LIVE ring stays on the prior slide after a failed present (no false ring)");
      if (el("pm-error-dismiss")) el("pm-error-dismiss").click(); // restore for later checks
      // --- Slice 5: a11y (role=listbox, roving tabindex, aria-live, LIVE text label) ---
      ok(el("pm-grid-tiles").getAttribute("role") === "listbox", "PM/B5: the grid is a role=listbox");
      el("pm-grid-tiles").querySelectorAll(".pm-tile")[0].dispatchEvent(new MouseEvent("click", {bubbles:true}));
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile")[0].tabIndex === 0 && el("pm-grid-tiles").querySelectorAll(".pm-tile")[1].tabIndex === -1, "PM/B5: roving tabindex (selected tile 0, others -1)");
      ok(/live/i.test(el("pm-grid-live-region").textContent), "PM/B5: live changes are announced via aria-live");
      var liveLbl = el("pm-grid-tiles").querySelector(".pm-tile.live .pm-tile-live");
      ok(liveLbl && /LIVE/.test(liveLbl.textContent), "PM/B5: the LIVE state carries a text label (WCAG 1.4.1, not colour-only)");
      // Edit ▸ → the authoring editor (so the existing editor checks below run).
      el("pm-grid-edit").click();
      ok(getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display !== "none", "PM/B: Edit ▸ opens the editor");
      ok(el("pm-grid").hidden, "PM/B: the grid is hidden in editor mode");
      // The surface loads its DeckView + composites the slide canvas (native preview, has-render).
      await waitFor(function(){ return el("pm-canvas").classList.contains("has-render"); });
      ok(el("pm-canvas").classList.contains("has-render"), "PM: the slide canvas shows a native composited preview (render_deck_slide → blitFrame)");
      ok(window.__calls.some(function(c){ return c.cmd === "render_deck_slide"; }), "PM: render_deck_slide drives the preview (compositor stays native, not HTML)");
      ok(document.querySelectorAll("#pm-slide-list .pm-slide").length === 2, "PM: the SLIDES list renders one row per deck slide");
      ok(/Slide 2 \/ 2/.test(el("pm-slide-pos").textContent), "PM: the canvas shows 'Slide N / M · 1920×1080'");
      // Preview→Live isolation (FR-012): editing NEVER changes Live; only Present does.
      var liveBefore = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_add_element"; }); });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_add_element" && c.args.kind === "text"; }), "PM: the Text tool adds a text element to the slide");
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length === liveBefore, "PM: editing the slide never goes Live (FR-012 — Live untouched by edits)");

      // === Inspector: selecting/adding an element AUTO-OPENS the right-panel Inspector (design 509:124) ===
      await waitFor(function(){ return !el("pm-inspector-body").hidden; });
      ok(!el("pm-inspector-body").hidden && el("pm-tab-inspector").getAttribute("aria-selected") === "true",
         "PM: adding/selecting an element AUTO-OPENS the Inspector tab");
      ok(!el("pm-inspector-body").contains(document.activeElement),
         "PM: the auto-open does NOT move focus into the Inspector (no focus-steal off the canvas, review #9)");
      ok(el("pm-tab-inspector").getAttribute("aria-disabled") !== "true", "PM: the Inspector tab is enabled when an element is selected");
      ok(/Text element/.test(el("pm-inspector-body").textContent), "PM: the Inspector binds to the selected element (Text element header)");
      // A Text inspector control drives deck_update_element.
      var sizeIn = Array.from(el("pm-inspector-body").querySelectorAll("input[type=number]"))[0];
      sizeIn.value = "120"; sizeIn.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.size_permille === 120; }), "PM: an Inspector control drives deck_update_element (size)");
      var colorIn = el("pm-inspector-body").querySelector("input[type=color]");
      colorIn.value = "#ff8800"; colorIn.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.color && c.args.patch.color.r === 255; }), "PM: the Colour control patches deck_update_element with an {r,g,b,a}");
      var alignBtn = Array.from(el("pm-inspector-body").querySelectorAll("button[aria-label^='Align ']"))[1];
      alignBtn.focus(); alignBtn.click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.align_h === "center"; }), "PM: an Align button patches align_h");
      await sleep(20);
      ok(document.activeElement && document.activeElement.dataset && document.activeElement.dataset.ik === "align-center",
         "PM: focus is RESTORED to the button after its edit re-renders the inspector (WCAG 2.4.3, review #2)");
      // The Layers panel (replacing the old Arrange buttons) lists the slide's elements; Alt+↑ on a
      // layer row raises it in the z-order.
      var layerRow = el("pm-inspector-body").querySelector("#pm-layers .td-layer");
      layerRow.focus(); layerRow.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowUp", altKey:true, bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_element_z"; }), "PM: a Layers-panel Alt+↑ raises the element (deck_set_element_z)");
      // Manual tab switch: Media ⟷ Inspector. Assert the COMPUTED display, not just the `.hidden`
      // property — a class `display:flex` can outrank the UA `[hidden]{display:none}` and leave BOTH
      // panels visible while `.hidden` still reads true (the contextual switch must actually hide one).
      var disp = function(id){ return getComputedStyle(el(id)).display; };
      el("pm-tab-media").click();
      ok(!el("pm-media-body").hidden && el("pm-inspector-body").hidden, "PM: the Media tab switches the right panel back to the library");
      ok(disp("pm-media-body") !== "none" && disp("pm-inspector-body") === "none", "PM: on Media, ONLY the media library is rendered (inspector display:none)");
      el("pm-tab-inspector").click();
      ok(!el("pm-inspector-body").hidden, "PM: the Inspector tab switches back to the inspector");
      ok(disp("pm-inspector-body") !== "none" && disp("pm-media-body") === "none", "PM: on Inspector, the media library is NOT rendered (media display:none)");
      // Image inspector + Replace flow.
      document.querySelector('#surface-presentation .pm-tool[data-add="image"]').click();
      await waitFor(function(){ return /Image element/.test(el("pm-inspector-body").textContent); });
      ok(/Image element/.test(el("pm-inspector-body").textContent), "PM: adding an image element opens the Image inspector (source + Replace)");
      var repBtn = Array.from(el("pm-inspector-body").querySelectorAll("button")).filter(function(b){ return /Replace|Relink/.test(b.textContent); })[0];
      repBtn.click();
      ok(!el("pm-replace-hint").hidden && !el("pm-media-body").hidden, "PM: Replace… arms the flow + switches to the media library with a hint");
      var imgCell = document.querySelector('#pm-media-grid .pm-asset:not(.missing) .pm-asset-thumb');
      imgCell.click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_replace_element_image" && c.args.mediaId === 1 && typeof c.args.index === "number"; }), "PM: picking a media image fires deck_replace_element_image({mediaId, index}) — camelCase→snake arg crossing");
      // Deselect → the panel returns to Media.
      await waitFor(function(){ return !el("pm-inspector-body").hidden; }); // replace re-opened the inspector
      document.querySelector('#surface-presentation .pm-mtab[data-filter="all"]').click(); // reset the media filter after the Replace flow
      // Add a slide.
      var slidesBefore = document.querySelectorAll("#pm-slide-list .pm-slide").length;
      el("pm-add-slide").click();
      await waitFor(function(){ return document.querySelectorAll("#pm-slide-list .pm-slide").length > slidesBefore; });
      ok(document.querySelectorAll("#pm-slide-list .pm-slide").length === slidesBefore + 1, "PM: '+ Add slide' adds a slide via deck_add_slide");
      // Deselect (a fresh slide with no selected element) returns the panel to Media (review #8).
      await waitFor(function(){ return !el("pm-media-body").hidden; });
      ok(!el("pm-media-body").hidden && el("pm-inspector-body").hidden, "PM: a slide with no selected element returns the right panel to Media (deselect)");
      // Select the first slide.
      document.querySelector('#pm-slide-list .pm-slide .pm-slide-card').click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_select_slide"; }); });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_select_slide"; }), "PM: clicking a slide row selects it (deck_select_slide)");
      // Per-slide props: transition + auto-advance + notes.
      el("pm-transition").value = "cut"; el("pm-transition").dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_transition" && c.args.transition === "cut"; }), "PM: the Transition control drives deck_set_transition");
      el("pm-autoadv").value = "8"; el("pm-autoadv").dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_auto_advance" && c.args.secs === 8; }), "PM: Auto-advance drives deck_set_auto_advance(secs)");
      el("pm-notes").value = "pause here"; el("pm-notes").dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_notes" && c.args.notes === "pause here"; }), "PM: the speaker-notes field drives deck_set_notes");
      // Media library: grid + missing/unused footer + filter.
      ok(document.querySelectorAll("#pm-media-grid .pm-asset").length >= 3, "PM: the media library renders image/video asset cells");
      ok(document.querySelector("#pm-media-grid .pm-asset.missing"), "PM: a missing asset shows the missing state");
      ok(document.querySelectorAll("#pm-media-audio .pm-audio-row").length === 1, "PM: audio assets render in the AUDIO list");
      ok(/1 missing/.test(el("pm-media-stats").textContent) && /3 unused/.test(el("pm-media-stats").textContent), "PM: the footer reports 'N missing · M unused' (from media_usage + missing detection)");
      ok(el("pm-media-stats").classList.contains("warn"), "PM: the missing count is styled as a warning");
      document.querySelector('#surface-presentation .pm-mtab[data-filter="image"]').click();
      ok(!Array.from(document.querySelectorAll("#pm-media-grid .pm-asset .pm-asset-meta")).some(function(m){ return /VIDEO/.test(m.textContent); }), "PM: the Images filter hides video assets");
      document.querySelector('#surface-presentation .pm-mtab[data-filter="all"]').click();
      // Undo/redo (buttons + the DeckView's can_undo/redo drive enablement; ≥20 steps supported host-side).
      ok(el("pm-undo") && !el("pm-undo").disabled, "PM: after edits, Undo is enabled (can_undo)");
      el("pm-undo").click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_undo"; }); });
      ok(window.__calls.some(function(c){ return c.cmd === "deck_undo"; }), "PM: Undo drives deck_undo");
      // Present is now GRID-owned (double-click / Enter / transport) — the editor's ▶ Present button
      // was relocated (story 86ajxeq17). Grid go-live is covered by the PM/B checks above.
      // Canvas keyboard: add an element (which selects it), then nudge / toggle / raise / remove it.
      document.querySelector('#surface-presentation .pm-tool[data-add="shape"]').click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_add_element" && c.args.kind === "shape"; }); });
      await sleep(20);
      el("pm-canvas").focus();
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"Tab", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_select_element"; }), "PM: Tab on the canvas selects/cycles an element (keyboard selection, WCAG 2.1.1)");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_move_element"; }), "PM: an arrow key nudges the selected element (deck_move_element)");
      // Resize: the selection box has drag handles; Alt+arrows resize by keyboard; a handle drag
      // resizes by pointer. The stub shape is 600×160 ‰ — a grow must report a larger w/h.
      ok(document.querySelectorAll('#pm-sel .pm-h').length === 8, "PM: the selection box has 8 resize handles");
      ok(!!document.querySelector('#pm-sel .pm-h[data-h="se"]') && !!document.querySelector('#pm-sel .pm-h[data-h="w"]'), "PM: handles cover corners + edges (data-h)");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", altKey:true, bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_move_element" && c.args.w > 600 && c.args.h === 160; }),
         "PM: Alt+arrow RESIZES the element (width grows, height + origin unchanged — not a move)");
      // Pointer resize: the canvas collapses to 0×0 in headless (no definite layout), so stub its
      // getBoundingClientRect to a known 320×180 box → the SE-handle drag maps to a deterministic
      // per-mille delta (grab 800,590 → move 920,710 ⇒ w 600→720, h 160→280). This exercises the
      // REAL resize path (pointToPermille + the pointermove resize math), not the layout.
      var seH = document.querySelector('#pm-sel .pm-h[data-h="se"]');
      var cnv = el("pm-canvas");
      var origGBCR = cnv.getBoundingClientRect.bind(cnv);
      cnv.getBoundingClientRect = function(){ return {left:0, top:0, width:320, height:180, right:320, bottom:180, x:0, y:0}; };
      var mvBefore = window.__calls.filter(function(c){ return c.cmd === "deck_move_element"; }).length;
      seH.dispatchEvent(new PointerEvent("pointerdown", {clientX: 256, clientY: 106, pointerId: 7, bubbles: true}));
      cnv.dispatchEvent(new PointerEvent("pointermove", {clientX: 294, clientY: 128, pointerId: 7, bubbles: true}));
      cnv.dispatchEvent(new PointerEvent("pointerup", {clientX: 294, clientY: 128, pointerId: 7, bubbles: true}));
      cnv.getBoundingClientRect = origGBCR;
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_move_element"; }).slice(mvBefore).some(function(c){ return c.args.w > 600 && c.args.h > 160; }),
         "PM: dragging the SE handle resizes the element (deck_move_element grows both w and h)");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"h", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_toggle_element_visible"; }), "PM: 'H' toggles the selected element's visibility");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"]", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_element_z"; }), "PM: ']' raises the selected element's z-order");
      el("pm-canvas").dispatchEvent(new KeyboardEvent("keydown", {key:"Delete", bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_remove_element"; }), "PM: Delete removes the selected element");

      // === Inline text editing (double-click) + Layers panel (replaces Arrange) ===
      // A fresh slide with a single text element → deterministic canvas hit-test + layer list.
      el("pm-add-slide").click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_add_slide"; }); });
      await sleep(20);
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return /Text element/.test(el("pm-inspector-body").textContent); });
      // -- Inline editor: double-click the (visible) text element on the canvas (stub the 0×0
      //    headless canvas rect so the hit-test maps to the element). --
      var cnv2 = el("pm-canvas");
      var origG2 = cnv2.getBoundingClientRect.bind(cnv2);
      cnv2.getBoundingClientRect = function(){ return {left:0, top:0, width:320, height:180, right:320, bottom:180, x:0, y:0}; };
      cnv2.dispatchEvent(new MouseEvent("dblclick", {clientX:160, clientY:92, bubbles:true}));
      ok(!!el("pm-text-edit") && el("pm-text-edit").tagName === "TEXTAREA", "PM: double-clicking a text element opens an inline textarea editor");
      el("pm-text-edit").value = "Edited on canvas";
      el("pm-text-edit").dispatchEvent(new KeyboardEvent("keydown", {key:"Enter", metaKey:true, bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_set_element_text" && c.args.text === "Edited on canvas"; }), "PM: Cmd+Enter commits the edit via deck_set_element_text");
      ok(!el("pm-text-edit"), "PM: committing closes the inline editor");
      await sleep(20);
      cnv2.dispatchEvent(new MouseEvent("dblclick", {clientX:160, clientY:92, bubbles:true}));
      var setN = window.__calls.filter(function(c){ return c.cmd === "deck_set_element_text"; }).length;
      el("pm-text-edit").value = "discarded";
      el("pm-text-edit").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      ok(!el("pm-text-edit") && window.__calls.filter(function(c){ return c.cmd === "deck_set_element_text"; }).length === setN, "PM: Escape cancels the inline edit (editor closes, no commit)");
      cnv2.getBoundingClientRect = origG2;
      await sleep(20);
      // -- Layers panel (mirrors the Theme Designer): lists elements, eye toggles, handle drag reorders. --
      ok(!!el("pm-inspector-body").querySelector("#pm-layers"), "PM: the inspector has a LAYERS panel (replacing Arrange)");
      ok(el("pm-inspector-body").querySelectorAll("#pm-layers .td-layer").length >= 1, "PM: the Layers panel lists the slide's elements front→back");
      var lEye = el("pm-inspector-body").querySelector("#pm-layers .td-layer .td-layer-eye");
      var visN = window.__calls.filter(function(c){ return c.cmd === "deck_toggle_element_visible"; }).length;
      lEye.click();
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_toggle_element_visible"; }).length === visN + 1, "PM: a Layers-row eye toggles element visibility");
      await sleep(20);
      var lh = el("pm-inspector-body").querySelector("#pm-layers .td-layer .td-layer-handle");
      lh.dispatchEvent(new PointerEvent("pointerdown", {clientX:5, clientY:5, button:0, pointerId:9, bubbles:true}));
      window.dispatchEvent(new PointerEvent("pointerup", {clientX:5, clientY:40, pointerId:9, bubbles:true}));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_reorder_elements" && Array.isArray(c.args.order); }), "PM: dragging a layer handle reorders via deck_reorder_elements(order)");
      // Command palette: Presentation actions are offered while the surface is active.
      window.__cmdPalette.open();
      await sleep(20);
      document.getElementById("cmd-input").value = "Add slide";
      document.getElementById("cmd-input").dispatchEvent(new Event("input"));
      ok(Array.from(document.querySelectorAll("#cmd-list li")).some(function(li){ return /Add slide/.test(li.textContent); }), "PM: the command palette offers 'Add slide' while Presentation is active");
      window.__cmdPalette.closeAll();
      // ⌘⇧P jumps to the Presentation surface from elsewhere.
      document.querySelector('.nav-item[data-surface="console"]').click();
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"P", metaKey:true, shiftKey:true, bubbles:true}));
      ok(el("surface-presentation").classList.contains("active"), "PM: ⌘⇧P jumps to the Presentation surface");
      // The Present-ed slide shows a non-colour-only LIVE badge + names 'live' in its aria-label (review #4).
      await waitFor(function(){ return !!document.querySelector("#pm-slide-list .pm-slide.live .pm-slide-live-badge"); });
      var liveCard = document.querySelector("#pm-slide-list .pm-slide.live .pm-slide-card");
      ok(!!document.querySelector("#pm-slide-list .pm-slide.live .pm-slide-live-badge"), "PM: the live slide shows a non-colour-only LIVE badge");
      ok(liveCard && /live/i.test(liveCard.getAttribute("aria-label") || ""), "PM: the live slide names 'live' in its aria-label (not colour-only)");
      // The active media filter reflects aria-pressed (a real toggle-button group, not a fake tablist).
      ok(document.querySelector('#surface-presentation .pm-mtab[aria-pressed="true"]'), "PM: the media filter marks the active button with aria-pressed");

      // === Remaining states: font picker · image Fit · destructive confirms · system states ===

      // --- C-006 Font-family picker (Text inspector, from system_fonts) ---
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return /Text element/.test(el("pm-inspector-body").textContent); });
      await waitFor(function(){ var s = el("pm-inspector-body").querySelector('select[data-ik="font"]'); return s && s.options.length >= 4; });
      var fontSel = el("pm-inspector-body").querySelector('select[data-ik="font"]');
      ok(!!fontSel, "PM: the Text inspector has a Font-family picker (C-006)");
      ok(Array.from(fontSel.options).some(function(o){ return o.value === ""; }) && Array.from(fontSel.options).some(function(o){ return o.value === "Georgia"; }),
         "PM: the Font picker is populated from system_fonts (System default + families)");
      fontSel.value = "Georgia"; fontSel.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.font === "Georgia"; }),
         "PM: choosing a font patches deck_update_element {font}");
      await sleep(20);
      fontSel = el("pm-inspector-body").querySelector('select[data-ik="font"]'); // re-query after the re-render
      fontSel.value = ""; fontSel.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.font === null; }),
         "PM: 'System default' clears the font to null (bundled default)");

      // --- C-008 Image Fit control (Stretch / Fit / Fill) ---
      document.querySelector('#surface-presentation .pm-tool[data-add="image"]').click();
      await waitFor(function(){ return /Image element/.test(el("pm-inspector-body").textContent); });
      var fitSel = el("pm-inspector-body").querySelector('select[data-ik="imgfit"]');
      ok(!!fitSel && fitSel.options.length === 3, "PM: the Image inspector Fit control offers Stretch/Fit/Fill (C-008, not a disabled placeholder)");
      ok(fitSel && !fitSel.disabled, "PM: the Fit control is live (wired to the render), not a later-seam stub");
      fitSel.value = "fit"; fitSel.dispatchEvent(new Event("change"));
      ok(window.__calls.some(function(c){ return c.cmd === "deck_update_element" && c.args.patch && c.args.patch.fit === "fit"; }),
         "PM: the Fit control patches deck_update_element {fit} (letterbox)");

      // --- C-003 Delete-element Undo toast (role=status) ---
      await sleep(20);
      el("pm-inspector-body").querySelector('button[data-ik="del"]').click();
      await waitFor(function(){ return !el("pm-toast").hidden; });
      ok(!el("pm-toast").hidden && el("pm-toast").getAttribute("role") === "status", "PM: deleting an element shows a role=status toast (C-003)");
      ok(/deleted/i.test(el("pm-toast").textContent), "PM: the toast reads 'Element deleted'");
      var undoBtn = el("pm-toast").querySelector(".pm-toast-action");
      ok(!!undoBtn && /Undo/.test(undoBtn.textContent), "PM: the toast offers an Undo action");
      // Before/after delta (deck_undo was already fired earlier by the Undo button, so a bare
      // `.some()` would be tautological — assert the toast Undo STRICTLY increases the count).
      var undoN = window.__calls.filter(function(c){ return c.cmd === "deck_undo"; }).length;
      undoBtn.click();
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_undo"; }).length === undoN + 1, "PM: the toast Undo drives a fresh deck_undo (⌘Z-backed)");

      // --- C-001 Delete-slide confirm (role=alertdialog, Cancel-focused, Esc cancels) ---
      await waitFor(function(){ return document.querySelectorAll("#pm-slide-list .pm-slide").length >= 2; });
      var slideDel = document.querySelector("#pm-slide-list .pm-slide .pm-slide-del:not([disabled])");
      ok(!!slideDel, "PM: each slide has a delete affordance, enabled while >1 slide (C-001)");
      slideDel.click();
      await waitFor(function(){ return !!document.querySelector('.pm-confirm[role="alertdialog"]'); });
      var dlg = document.querySelector('.pm-confirm[role="alertdialog"]');
      ok(!!dlg, "PM: delete-slide opens a role=alertdialog confirm");
      ok(dlg.getAttribute("aria-modal") === "true" && dlg.hasAttribute("aria-labelledby"), "PM: the confirm is aria-modal + labelled (C-009)");
      ok(document.activeElement && document.activeElement.textContent === "Cancel", "PM: the confirm focuses Cancel (safe default for a destructive action)");
      var rmSlideBefore = window.__calls.filter(function(c){ return c.cmd === "deck_remove_slide"; }).length;
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      ok(!document.querySelector('.pm-confirm[role="alertdialog"]'), "PM: Esc cancels the confirm (C-009 modal semantics)");
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_remove_slide"; }).length === rmSlideBefore, "PM: cancelling does not remove the slide");
      document.querySelector("#pm-slide-list .pm-slide .pm-slide-del:not([disabled])").click();
      await waitFor(function(){ return !!document.querySelector('.pm-confirm[role="alertdialog"]'); });
      Array.from(document.querySelectorAll('.pm-confirm .pm-btn-danger')).filter(function(b){ return /Delete slide/.test(b.textContent); })[0].click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_remove_slide"; }), "PM: confirming delete-slide drives deck_remove_slide");

      // --- C-002 Remove-media confirm with the in-use warning ---
      el("pm-tab-media").click();
      await waitFor(function(){ return !el("pm-media-body").hidden; });
      var inUseCell = Array.from(document.querySelectorAll("#pm-media-grid .pm-asset")).filter(function(cell){
        var d = cell.querySelector(".pm-asset-del"); return d && /used on 2/i.test(d.getAttribute("aria-label") || ""); })[0];
      ok(!!inUseCell, "PM: an in-use asset cell has a remove affordance labelling its usage (C-002)");
      inUseCell.querySelector(".pm-asset-del").click();
      await waitFor(function(){ return !!document.querySelector('.pm-confirm[role="alertdialog"]'); });
      ok(!!document.querySelector(".pm-confirm-warn") && /2 slide/i.test(document.querySelector(".pm-confirm-warn").textContent),
         "PM: removing an in-use asset warns 'Used on 2 slides'");
      document.querySelector('.pm-confirm .pm-btn-danger').click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_remove_media" && c.args.id === 1; }), "PM: confirming remove-media drives deck_remove_media(id)");

      // --- C-004 System states: loading (aria-busy) + error banner (role=alert) + Retry ---
      // The busy state must actually ENGAGE while a command is in flight, then clear — not merely
      // exist as an attribute. Defer the next deck command, assert aria-busy="true" + the .busy
      // shimmer during it, resolve, assert it clears to "false".
      await waitFor(function(){ return el("pm-canvas-box").getAttribute("aria-busy") === "false"; }); // let prior commands settle
      ok(el("pm-canvas-box").getAttribute("aria-busy") === "false", "PM: the canvas is not busy at rest");
      window.__pmDeferOnce = true;
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return el("pm-canvas-box").getAttribute("aria-busy") === "true"; });
      ok(el("pm-canvas-box").getAttribute("aria-busy") === "true" && el("pm-canvas-box").classList.contains("busy"),
         "PM: a command in flight sets aria-busy=true + the .busy shimmer (C-004 loading)");
      if (window.__pmDeferred) window.__pmDeferred();
      await waitFor(function(){ return el("pm-canvas-box").getAttribute("aria-busy") === "false"; });
      ok(el("pm-canvas-box").getAttribute("aria-busy") === "false" && !el("pm-canvas-box").classList.contains("busy"),
         "PM: the busy state clears when the command resolves");
      window.__pmRejectOnce = true;
      document.querySelector('#surface-presentation .pm-tool[data-add="text"]').click();
      await waitFor(function(){ return !el("pm-error").hidden; });
      ok(!el("pm-error").hidden && el("pm-error").getAttribute("role") === "alert", "PM: a rejected deck command shows a role=alert error banner");
      ok(/couldn't/i.test(el("pm-error-msg").textContent), "PM: the banner explains what failed (not colour-only)");
      el("pm-error-retry").click(); // the one-shot reject flag is cleared → the retry succeeds
      await waitFor(function(){ return el("pm-error").hidden; });
      ok(el("pm-error").hidden, "PM: Retry re-runs the action and clears the banner on success");

      // ‹ Done returns from the editor to the slide grid (the Edit ▸ / ‹ Done round-trip, C-005).
      ok(!!el("pm-done"), "PM/B4: the editor has a '‹ Done' control");
      el("pm-done").click();
      await waitFor(function(){ return !el("pm-grid").hidden; });
      ok(!el("pm-grid").hidden && getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display === "none", "PM/B4: ‹ Done returns from the editor to the grid");

      // === Presentations Library (deck_list / new / open / rename / duplicate / delete) ===
      ok(!!el("pm-deckswitch"), "PM/Lib: the topbar has a deck-switcher breadcrumb");
      el("pm-deckswitch").click();
      await waitFor(function(){ return !el("pm-library").hidden; });
      ok(!el("pm-library").hidden, "PM/Lib: the deck-switcher opens the Presentations Library");
      ok(getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display === "none",
         "PM/Lib: the editor is hidden while the Library is open");
      await waitFor(function(){ return el("pm-lib-grid").querySelectorAll(".pm-lib-card").length >= 3; });
      ok(el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 3, "PM/Lib: deck_list renders one card per presentation");
      ok(!!el("pm-lib-grid").querySelector(".pm-lib-new-tile"), "PM/Lib: a '＋ New presentation' tile leads the grid");
      ok(/3 presentations/.test(el("pm-lib-count").textContent), "PM/Lib: the count reflects the library");
      ok(!!el("pm-lib-grid").querySelector(".pm-lib-card.open .pm-lib-openflag"), "PM/Lib: the open deck's card carries a non-colour-only OPEN flag");
      // search filters the grid.
      el("pm-lib-q").value = "youth"; el("pm-lib-q").dispatchEvent(new Event("input"));
      ok(el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 1, "PM/Lib: search filters the grid");
      // a query with no matches shows a 'no results' message (no cards, no New tile).
      el("pm-lib-q").value = "zzznotacard"; el("pm-lib-q").dispatchEvent(new Event("input"));
      ok(el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 0 && /No presentations match/.test(el("pm-lib-grid").textContent), "PM/Lib: a no-match search shows a no-results message");
      el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input"));
      // ⋯ menu → Duplicate.
      el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots").click();
      await waitFor(function(){ return !!el("pm-lib-menu"); });
      ok(!!el("pm-lib-menu") && el("pm-lib-menu").getAttribute("role") === "menu", "PM/Lib: the ⋯ menu opens (role=menu, keyboard-navigable)");
      var dupN = window.__calls.filter(function(c){ return c.cmd === "deck_duplicate"; }).length;
      Array.from(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /Duplicate/.test(b.textContent); })[0].click();
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_duplicate"; }).length === dupN + 1, "PM/Lib: ⋯ Duplicate drives deck_duplicate");
      await waitFor(function(){ return el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 4; });
      ok(el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 4, "PM/Lib: the duplicate appears in the library");
      // ⋯ Rename → name dialog → deck_rename.
      el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots").click();
      await waitFor(function(){ return !!el("pm-lib-menu"); });
      Array.from(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /Rename/.test(b.textContent); })[0].click();
      await waitFor(function(){ return !!el("pm-prompt-input"); });
      ok(!!el("pm-prompt-input") && document.querySelector('.pm-confirm[role="dialog"]'), "PM/Lib: Rename opens a role=dialog name prompt");
      el("pm-prompt-input").value = "Renamed Deck";
      Array.from(document.querySelectorAll(".pm-confirm .pm-btn-primary")).slice(-1)[0].click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_rename" && c.args.name === "Renamed Deck"; }), "PM/Lib: the Rename dialog drives deck_rename(name)");
      // ⋯ Delete the OPEN deck → alertdialog confirm → deck_delete(that id) → editor switches.
      var delCard = el("pm-lib-grid").querySelector(".pm-lib-card.open") || el("pm-lib-grid").querySelector(".pm-lib-card");
      var wantDelId = Number(delCard.dataset.id);
      var nameBeforeDelete = el("pm-plan-name").textContent;
      delCard.querySelector(".pm-lib-dots").click();
      await waitFor(function(){ return !!el("pm-lib-menu"); });
      Array.from(el("pm-lib-menu").querySelectorAll("button")).filter(function(b){ return /Delete/.test(b.textContent); })[0].click();
      await waitFor(function(){ return !!document.querySelector('.pm-confirm[role="alertdialog"]'); });
      ok(!!document.querySelector('.pm-confirm[role="alertdialog"]'), "PM/Lib: Delete opens a role=alertdialog confirm");
      document.querySelector(".pm-confirm .pm-btn-danger").click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_delete" && c.args.id === wantDelId; }), "PM/Lib: confirming delete drives deck_delete(that card's id)");
      await waitFor(function(){ return el("pm-plan-name").textContent !== nameBeforeDelete; });
      ok(el("pm-plan-name").textContent !== nameBeforeDelete, "PM/Lib: deleting the OPEN deck switches the editor to a surviving deck");
      // ＋ New Presentation → dialog → deck_new → opens the editor.
      el("pm-lib-new").click();
      await waitFor(function(){ return !!el("pm-prompt-input"); });
      el("pm-prompt-input").value = "Fresh Deck";
      Array.from(document.querySelectorAll(".pm-confirm .pm-btn-primary")).slice(-1)[0].click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_new" && c.args.name === "Fresh Deck"; }), "PM/Lib: New Presentation drives deck_new(name)");
      await waitFor(function(){ return el("pm-library").hidden; });
      ok(el("pm-library").hidden && getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display !== "none", "PM/Lib: creating a deck returns to the editor");
      ok(/Fresh Deck/.test(el("pm-plan-name").textContent), "PM/Lib: the deck-switcher shows the new deck's name");
      // Open a deck from the Library → editor (the CARD'S id crosses + the editor opens on it).
      el("pm-deckswitch").click();
      await waitFor(function(){ return !el("pm-library").hidden; });
      var openCard = el("pm-lib-grid").querySelector(".pm-lib-card");
      var wantOpenId = Number(openCard.dataset.id);
      var wantOpenName = openCard.querySelector(".pm-lib-name").textContent;
      openCard.querySelector(".pm-lib-open").click();
      ok(window.__calls.some(function(c){ return c.cmd === "deck_open" && c.args.id === wantOpenId; }), "PM/Lib: clicking a card drives deck_open(that card's id)");
      await waitFor(function(){ return el("pm-library").hidden; });
      ok(el("pm-library").hidden, "PM/Lib: opening a deck returns to the editor");
      ok(el("pm-plan-name").textContent === wantOpenName, "PM/Lib: the editor opens on the chosen deck (name matches)");
      // Not-persistent banner.
      el("pm-deckswitch").click();
      await waitFor(function(){ return !el("pm-library").hidden; });
      window.__LIB.persistent = false;
      el("pm-lib-retry").click();
      await waitFor(function(){ return !el("pm-lib-nopersist").hidden; });
      ok(!el("pm-lib-nopersist").hidden, "PM/Lib: a non-persistent library shows the 'not saved' banner");
      window.__LIB.persistent = true; el("pm-lib-retry").click();
      // Error state: a rejected deck_list shows an error + Retry recovers.
      await waitFor(function(){ return el("pm-lib-nopersist").hidden; });
      window.__pmRejectOnce = true;
      el("pm-lib-retry").click();
      await waitFor(function(){ return !el("pm-lib-error").hidden; });
      ok(!el("pm-lib-error").hidden && el("pm-lib-error").getAttribute("role") === "alert", "PM/Lib: a failed deck_list shows a role=alert error state");
      el("pm-lib-retry").click();
      await waitFor(function(){ return el("pm-lib-error").hidden; });
      ok(el("pm-lib-error").hidden, "PM/Lib: Retry recovers the library");
      // Empty state: an empty library shows 'No presentations yet' with a CTA that opens New.
      window.__LIB.decks = []; window.__LIB.open = 0;
      el("pm-lib-retry").click();
      await waitFor(function(){ return !el("pm-lib-empty").hidden; });
      ok(!el("pm-lib-empty").hidden && el("pm-lib-grid").querySelectorAll(".pm-lib-card").length === 0, "PM/Lib: an empty library shows the 'No presentations yet' state");
      el("pm-lib-empty-new").click();
      await waitFor(function(){ return !!el("pm-prompt-input"); });
      ok(!!el("pm-prompt-input"), "PM/Lib: the empty-state CTA opens the New dialog");
      el("pm-prompt-input").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      await waitFor(function(){ return !el("pm-prompt-input"); });
      // ⌘N opens the New presentation dialog (a shipped shortcut the ⋯ menu advertises).
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"n", metaKey:true, bubbles:true}));
      await waitFor(function(){ return !!el("pm-prompt-input"); });
      ok(!!el("pm-prompt-input"), "PM/Lib: ⌘N opens the New presentation dialog");
      el("pm-prompt-input").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      await waitFor(function(){ return !el("pm-prompt-input"); });
      // (The '‹ Back to editor' affordance was removed — the Library is the landing; opening a card
      //  goes to the grid, story 86ajxeq17.)

      // The ⌘1-6 surface map is UNCHANGED by activating Presentation: ⌘2 still → Theme Designer.
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"2", metaKey:true, bubbles:true}));
      ok(el("surface-theme-designer").classList.contains("active") && !el("surface-presentation").classList.contains("active"),
         "PM: ⌘2 still routes to Theme Designer (data-nodigit keeps the ⌘1–6 map intact)");

      // === Pre-service Check surface (Design 2.0, Figma 344:124): readiness checklist ===
      document.querySelector('.nav-item[data-surface="preservice"]').click();
      ok(el("surface-preservice").classList.contains("active"), "Pre-service: nav opens the surface");
      await waitFor(function(){ return document.querySelectorAll("#ps-sections .ps-row").length >= 10 && el("ps-passed").textContent !== "0"; });
      ok(document.querySelectorAll("#ps-sections .ps-row").length === 10,
         "Pre-service: all 10 checks render across the four sections");
      ok(document.querySelectorAll("#ps-sections .ps-section").length === 4,
         "Pre-service: four grouped sections (Displays / Media / Audio / Storage)");
      ok(el("ps-passed").textContent === "4" && el("ps-warnings").textContent === "1" && el("ps-blocking").textContent === "0",
         "Pre-service: readiness counts derive from live host data (4 passed · 1 warning · 0 blocking)");
      var psStt = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Transcription & AI/.test(r.textContent); });
      ok(psStt && psStt.querySelector(".ps-ico-ok") && /On-device STT ready/.test(psStt.textContent),
         "Pre-service: on-device STT ready reflects the real stt_ready probe");
      // STT model missing → the check becomes an attention warning (not a fabricated pass).
      window.__psStt = {ready:false, state:"not_downloaded", model:"Small", detail:"On-device model not downloaded yet"};
      el("ps-rerun").click();
      await waitFor(function(){ var r=Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Transcription & AI/.test(x.textContent);}); return r && r.querySelector(".ps-ico-warn"); });
      ok(true, "Pre-service: stt_ready 'not downloaded' → attention warning (honest, not a pass)");
      window.__psStt = null;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-passed").textContent === "4"; });
      ok(el("ps-verdict").textContent === "Safe to start" && el("ps-verdict-card").getAttribute("data-state") === "ok",
         "Pre-service: 0 blocking → Safe to start (green verdict)");
      ok(document.querySelectorAll("#ps-review .ps-review-card").length === 1,
         "Pre-service: the one warning surfaces as a Review-before-start card");
      var psMediaRow = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Slide media present/.test(r.textContent); });
      ok(psMediaRow && psMediaRow.querySelector(".ps-ico-warn") && psMediaRow.querySelector(".ps-row-action"),
         "Pre-service: missing-media check is a warning with a Locate fix action");
      ok(document.querySelectorAll("#ps-sections .ps-ico-pending").length >= 4,
         "Pre-service: subsystems the host doesn't expose yet show an honest 'not checked' state (never faked)");
      ok(!el("ps-start").disabled, "Pre-service: Start service enabled when nothing is blocking");
      // A BLOCKING check (disk critically low) flips the verdict to Not-safe and disables Start.
      window.__psDiskLow = true;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-blocking").textContent !== "0"; });
      ok(el("ps-blocking").textContent === "1" && el("ps-verdict").textContent === "Not safe to start"
         && el("ps-verdict-card").getAttribute("data-state") === "block" && el("ps-start").disabled,
         "Pre-service: a blocking check → Not safe to start, red verdict, Start disabled");
      ok(/Disk space/.test((document.querySelector("#ps-review .ps-review-block") || {}).textContent || ""),
         "Pre-service: the blocking check leads the Review-before-start list");
      window.__psDiskLow = false;
      // NO output window connected → never a green 'Safe to start'; Start is gated.
      window.__psNoHost = true;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-verdict").textContent === "No output window"; });
      ok(el("ps-start").disabled && el("ps-verdict-card").getAttribute("data-state") === "pending",
         "Pre-service: no output window → not ready, Start disabled (never a false 'Safe to start')");
      var psNet = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Local network & remotes/.test(r.textContent); });
      ok(psNet && psNet.querySelector(".ps-ico-pending"),
         "Pre-service: network reads 'not checked' with no host (no fabricated green)");
      window.__psNoHost = false;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-verdict").textContent === "Safe to start"; });
      el("ps-start").click();
      ok(el("surface-console").classList.contains("active"), "Pre-service: Start service goes to the Live Console");
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"K", metaKey:true, shiftKey:true, bubbles:true}));
      ok(el("surface-preservice").classList.contains("active"),
         "Pre-service: ⌘⇧K jumps to the surface (data-nodigit keeps the ⌘1–6 map intact)");

      // === Remote Control surface (Design 2.0, Figma 359:124): pair/approve/role/revoke ===
      document.querySelector('.nav-item[data-surface="remote"]').click();
      ok(el("surface-remote").classList.contains("active"), "Remote: nav opens the Remote Control surface");
      var rcN0 = +el("rc-count-n").textContent;
      ok(document.querySelectorAll("#rc-rows .rc-row").length === rcN0 && rcN0 >= 1,
         "Remote: the paired-devices table renders and the count chip matches");
      var rcPend = document.querySelector("#rc-pending .rc-pending-card");
      ok(!!rcPend, "Remote: a pending pair request is shown with a role picker");
      rcPend.querySelector(".rc-approve").click();
      ok(document.querySelectorAll("#rc-pending .rc-pending-card").length === 0 &&
         +el("rc-count-n").textContent === rcN0 + 1,
         "Remote: Approve moves the request into paired devices (" + rcN0 + "→" + el("rc-count-n").textContent + ")");
      var rcRevs = document.querySelectorAll("#rc-rows .rc-revoke");
      var rcRb = rcRevs[rcRevs.length - 1];
      var rcRows0 = document.querySelectorAll("#rc-rows .rc-row").length;
      rcRb.click();
      ok(rcRb.classList.contains("armed"), "Remote: first Revoke click arms a two-step confirm (destructive)");
      rcRb.click();
      ok(document.querySelectorAll("#rc-rows .rc-row").length === rcRows0 - 1,
         "Remote: second Revoke click removes the device");
      document.querySelector('.nav-item[data-surface="console"]').click();
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"R", metaKey:true, shiftKey:true, bubbles:true}));
      ok(el("surface-remote").classList.contains("active"),
         "Remote: ⌘⇧R jumps to Remote Control (data-nodigit keeps the ⌘1–6 map intact)");
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
