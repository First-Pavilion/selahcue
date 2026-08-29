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
import json
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
# (Re-tightened with the window-semantics checks: the floor had drifted 19 below the real
# count, so up to 19 checks could have been dropped silently. Verified stable across runs.)
# (Raised with the Design 2.0 parity batch 1 block — CON-046 / CON-142 / PME-001 / PME-005 /
# PME-014 / PME-015 — which adds 67 checks: 640 -> 707. Set to the REAL observed count, not a
# round number, so that dropping even one of the new checks trips exit 4.)
# (Raised for the Service Plan parity batch — 86ak846ft: run-sheet owner/duration, the Plan Summary
# panel, the loading state, and the QA/security remediation. Set to the REAL observed count so
# dropping even one trips exit 4. Sana S4: this floor had been left at 829 while the driver ran
# more, which would have let every new check disappear without failing.)
EXPECTED_MIN_CHECKS = 947


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

# The real app.css text, handed to the driver as a string. Chrome refuses
# `document.styleSheets[i].cssRules` for a file:// stylesheet (SecurityError), so a rule that
# only exists in a pseudo-class state (`.pm-btn-primary:hover`) is unreachable from the DOM.
# The driver regexes the rule out of this text and then resolves its VALUE through the live CSS
# engine (an inline `background-color: var(--token)` on a probe element), so `var()` is followed
# rather than string-matched and a token rename cannot fake a pass.
CSS_SRC = (
    "<script>window.__CSSTEXT = "
    + json.dumps(open(os.path.join(DIST, "app.css")).read())
    + ";</script>"
)

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
    // Health seams. Real Tauri ALWAYS sends these three keys (OperatorView carries no
    // skip_serializing_if on them), so absent is `null` with the key present — never a
    // missing key. The nested counters DO skip at zero, which is why `output_health` here is
    // {held:false} with no holds/recoveries: that is the exact byte shape
    // test_health_view.rs:177 pins for a healthy controller.
    output_health:{held:false}, storage:null, session:null,
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
  // Providers & Privacy (Settings, node 338:124) — the operator-local ProvidersView the
  // providers_* commands return. Mirrors the REAL backend default in a build without `cloud-live`:
  // on-device is the private default, cloud is OFF, cloud_status is "not_configured", cloud_connected
  // is false, and quota is null (the live SelahCue service does not exist yet). The driver mutates P
  // through the commands and flips the cloud_connected/quota fixtures to exercise the honest states.
  var P = {
    transcription_mode:"on_device",
    on_device:{ready:true, state:"ready", model:"Small", detail:"ggml-small.en.bin"},
    cloud_transcription_consent:false, cloud_notes_consent:false,
    offline_by_default:true, any_cloud_enabled:false,
    notes_template:"full_outline",
    notes_templates:[{value:"full_outline",label:"Full outline + scriptures"},{value:"summary",label:"Short summary"},{value:"bullets",label:"Bullet points"}],
    preferred_translation:"KJV",
    translations:[{code:"KJV",name:"King James Version"},{code:"WEB",name:"World English Bible"},{code:"ASV",name:"American Standard Version"}],
    include:{prayer_points:true, scripture_extraction:true, social_excerpts:false, chapter_markers:true, notable_quotations:true, short_summary:true},
    cloud_status:"not_configured", cloud_connected:false, account_token_set:false, quota:null
  };
  var ppView = function(){
    P.any_cloud_enabled = !!(P.cloud_transcription_consent || P.cloud_notes_consent);
    P.cloud_status = P.cloud_connected ? "available" : "not_configured";
    return JSON.parse(JSON.stringify(P));
  };
  window.__pp = P; // exposed so the driver can flip cloud_connected / quota to exercise honest states
  window.__TAURI__ = { core: { invoke: function(cmd, args){
    window.__calls.push({cmd:cmd, args:args});
    if (cmd === "builtin_themes") return Promise.resolve([{name:"Classic", theme:JSON.parse(JSON.stringify(T))}]);
    if (cmd === "system_fonts") return Promise.resolve(["Arial","Georgia","Helvetica Neue"]);
    if (cmd === "view") return Promise.resolve(JSON.parse(JSON.stringify(V)));
    // Service Plan builder (86ajxxuz9): plan mutations + content-link + scripture search.
    // Each returns a fresh OperatorView (byte-cloned) so the builder re-render never aliases V;
    // set_item_content is a PLAN edit (never a live-control command — the invariant check relies
    // on this staying out of the go_live/next/select/blackout/clear/start_timer set).
    if (cmd === "set_item_content") {
      // One-shot rejection hook: lets the driver exercise the "host rejected the link" path
      // (modal stays open + role=alert), mirroring a reference the host can't parse.
      if (window.__sicRejectOnce) { window.__sicRejectOnce = false; return Promise.reject("simulated host rejection"); }
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "add_item" || cmd === "move_item" || cmd === "rename_item" || cmd === "remove_item" || cmd === "plan_undo" || cmd === "plan_redo")
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    // Blackout mirrors the host: it MUTATES the state and returns the new view. It used to fall
    // through to `Promise.resolve(null)`, so the engaged blackout state could never be exercised
    // end to end — the driver could only fake it by poking V directly.
    if (cmd === "blackout") { V.blackout = !!(args && args.on); return Promise.resolve(JSON.parse(JSON.stringify(V))); }
    if (cmd === "scripture_search")
      return Promise.resolve([{reference:"Romans 8:28", text:"And we know that all things work together for good"}]);
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
  // Tier 2 control-link state. Defaults to a healthy remote link; __link overrides it.
  // Returning `null` here would exercise the "older shell" path instead, which the driver
  // covers separately by deleting the override.
  if (cmd === "link_status") return Promise.resolve(window.__link || {state:"connected", epoch:1, attempts:0, last_error:null});
    if (cmd === "stt_ready") return Promise.resolve(window.__psStt || {ready:true, state:"ready", model:"Small", detail:"On-device model ready"});
    if (cmd === "audio_input") return Promise.resolve(window.__psAudio || {available:true, state:"ok", name:"Focusrite Scarlett 2i2", channels:2, detail:"Focusrite Scarlett 2i2 · 2 ch"});
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
    // --- Live Console slide picker (LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec §6): the read-only
    // deck-slide bridge + within-item staging the Slides filmstrip drives. deckId 7 = a 3-slide
    // presentation; deckId 999 = a removed deck (available:false → the "presentation missing" state). ---
    if (cmd === "plan_deck_slides") {
      if (args.deckId === 999) return Promise.resolve({available:false});
      if (args.deckId === 8) { var big=[]; for (var i=0;i<80;i++) big.push({slide_id:200+i, label:"S"+(i+1), has_notes:false}); return Promise.resolve({available:true, slides:big}); } // large deck: bounded-memory test
      return Promise.resolve({available:true, slides:[
        {slide_id:101, label:"Grace That Feeds", has_notes:false},
        {slide_id:102, label:"Isaiah 61:5", has_notes:true},
        {slide_id:103, label:"Closing", has_notes:false}
      ]});
    }
    if (cmd === "render_plan_deck_slide")
      return Promise.resolve({available:true, frame:{w:2, h:1, rgba:btoa("\xff\x00\x00\xff\x00\xff\x00\xff")}});
    if (cmd === "select_slide") { // mirror the host: clamp to the item's slide_count + set the STAGED cursor (never Live)
      if (V.items[1]) {
        var _cnt = V.items[1].slide_count || 1;
        var _k = Math.max(0, Math.min(_cnt - 1, args.slideIndex));
        V.items[1].staged_slide_index = _k;
        if (V.live_index !== 1) V.items[1].slide_index = _k; // slide_index is LIVE-first when also live
      }
      V.staged_index = 1; V.staged_scripture = null;
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
    if (cmd === "present_plan_deck_slide") { // route the authored deck slide to Live (mirror present_authored_slide)
      V.live_authored_id = args.slideId; // the on-air authored slide id drives the filmstrip LIVE marker
      V.live_index = null;               // present_authored takes over the live surface (clears the plan live item)
      return Promise.resolve(JSON.parse(JSON.stringify(V)));
    }
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
      open: 2, persistent: true, nextId: 4,
      // Mirrors the host's bounded in-memory trash (8 entries). Without it the driver could never
      // reach the restorable/non-restorable branches at all — a fixture that never reaches the
      // condition the test names is the way these checks rot into decoration.
      trash: []
    });
    var libView = function(){ return { decks: LIB.decks.map(function(d){return {id:d.id,name:d.name,slides:d.slides};}), open: LIB.open, persistent: LIB.persistent,
      // What an undo could ACTUALLY put back (LibraryView.restorable). Bounded, so it shrinks.
      restorable: LIB.trash.map(function(t){ return t.id; }) }; };
    var libUnique = function(base){ var n=base, k=2; var names=LIB.decks.map(function(d){return d.name;}); while(names.indexOf(n)>=0){ n=base+" ("+k+")"; k++; } return n; };
    if (cmd === "deck_list") {
      // Test hook (mirrors __pmRejectOnce): force a MALFORMED null answer, so a host that does
      // not implement deck_list can be told apart from one reporting an empty library.
      if (window.__deckListNullOnce) { window.__deckListNullOnce = false; return Promise.resolve(null); }
      return Promise.resolve(libView());
    }
    if (cmd === "deck_search") {
      var gq = String((args && args.query) || "").trim().toLowerCase();
      if (!gq) return Promise.resolve({hits: []});
      var ghits = [];
      LIB.decks.forEach(function(d){
        if (d.name.toLowerCase().indexOf(gq) >= 0) ghits.push({deck_id: d.id, name: d.name, kind: "name"});
      });
      // Synthetic slide-content hit so the modal's content-row (slide # + snippet) is exercised.
      if (gq.indexOf("grace") >= 0 && LIB.decks.length) {
        var gd = LIB.decks[LIB.decks.length - 1];
        ghits.push({deck_id: gd.id, name: gd.name, kind: "content", slide_id: 7, slide_index: 3, snippet: "Amazing grace, how sweet the sound"});
      }
      return Promise.resolve({hits: ghits});
    }
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
      var doomed=LIB.decks.filter(function(x){return x.id===args.id;})[0];
      // The host retains the deck in a bounded trash — EXCEPT when it is too large to keep, which
      // is why `restorable` exists rather than "the last delete is always undoable".
      // window.__deckNoRetain names an id the fixture wants to be unretainable.
      if (doomed && window.__deckNoRetain !== args.id) {
        LIB.trash.push({id:doomed.id, deck:{id:doomed.id, name:doomed.name, slides:doomed.slides}});
        while (LIB.trash.length > 8) LIB.trash.shift();
      }
      LIB.decks=LIB.decks.filter(function(x){return x.id!==args.id;});
      if (wasOpen){ if(LIB.decks.length){ LIB.open=LIB.decks[0].id; D.name=LIB.decks[0].name; D.count=LIB.decks[0].slides; } else { LIB.decks.push({id:LIB.nextId++, name:"Untitled presentation", slides:1}); LIB.open=LIB.decks[0].id; D.name="Untitled presentation"; D.count=1; } }
      return Promise.resolve(libView());
    }
    // Detector liveness (HOST-SIGNAL-WEBVIEW-CONTRACT Tier 1a). All four keys always present.
    // __detHealthFail simulates a host with no such command — the UNKNOWN case, which is the one
    // the old `else -> NO SIGNAL` shape got wrong.
    if (cmd === "detection_health") {
      if (window.__detHealthFail) return Promise.reject("no such command");
      return Promise.resolve(window.__detHealth || {state:"idle", provider:null, error:null, can_retry:false});
    }
    if (cmd === "retry_detection") {
      if (window.__detRetryRefuse) return Promise.reject(window.__detRetryRefuse);
      window.__detHealth = {state:"listening", provider:"whisper-small", error:null, can_retry:false};
      return Promise.resolve(window.__detHealth);
    }
    if (cmd === "deck_restore") {
      var ti=-1; for (var k=0;k<LIB.trash.length;k++) if (LIB.trash[k].id===args.id) ti=k;
      // Refusal is a REJECTED PROMISE with an operator-facing reason — never a silent no-op.
      if (ti<0) return Promise.reject("That presentation can no longer be restored.");
      var back=LIB.trash.splice(ti,1)[0].deck;
      // The name can differ: if it was taken while the deck sat in the trash it is uniquified.
      back.name=libUnique(back.name);
      LIB.decks.push(back);
      var rv=libView(); rv.restored_name=back.name;
      return Promise.resolve(rv);
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
    // --- Providers & Privacy (Settings 338:124) ---
    if (cmd === "providers_view") return Promise.resolve(ppView()); // the resync read is NEVER rejected
    // One-shot rejection hook for the PP MUTATION commands only (not providers_view): lets the driver
    // exercise the "host rejected a setting" path — the optimistic control must revert to the
    // backend-confirmed value (mutate() resyncs), never showing a state the backend didn't confirm.
    var __ppSet = (cmd==="set_transcription_mode"||cmd==="set_cloud_consent"||cmd==="set_notes_template"||
                   cmd==="set_preferred_translation"||cmd==="set_include_flag"||
                   cmd==="set_account_token"||cmd==="clear_account_token");
    if (__ppSet && window.__ppRejectOnce) { window.__ppRejectOnce = false; return Promise.reject("simulated host rejection"); }
    if (cmd === "set_transcription_mode") { P.transcription_mode = args.mode; return Promise.resolve(ppView()); }
    if (cmd === "set_cloud_consent") {
      if (args.kind === "transcription") P.cloud_transcription_consent = !!args.enabled;
      else if (args.kind === "notes") P.cloud_notes_consent = !!args.enabled;
      return Promise.resolve(ppView());
    }
    if (cmd === "set_notes_template") { P.notes_template = args.template; return Promise.resolve(ppView()); }
    if (cmd === "set_preferred_translation") {
      // Mirror the backend: only an installed code is accepted (unknown → keep current).
      if (P.translations.some(function(t){ return t.code === args.code; })) P.preferred_translation = args.code;
      return Promise.resolve(ppView());
    }
    if (cmd === "set_include_flag") { if (args.name in P.include) P.include[args.name] = !!args.enabled; return Promise.resolve(ppView()); }
    if (cmd === "set_account_token") { P.account_token_set = !!(args.token && args.token.length); return Promise.resolve(ppView()); }
    if (cmd === "clear_account_token") { P.account_token_set = false; return Promise.resolve(ppView()); }
    if (cmd === "generate_sermon_notes") {
      // Consent-gated end to end (mirrors the backend): no notes consent → consent_required; else the
      // driver picks the outcome via window.__ppGen ("ok" | "not_configured" | "quota_exceeded").
      if (!P.cloud_notes_consent)
        return Promise.resolve({ok:false, error:"consent_required", message:"cloud notes consent is off"});
      var g = window.__ppGen || "not_configured";
      if (g === "ok") return Promise.resolve({
        ok:true, degraded:false, provider:"SelahCue AI",
        draft:{title:"Grace That Feeds", summary:"A sermon on provision and grace.",
          sections:[{heading:"Prayer points", items:["Thank God for provision","Pray for the hungry"]}],
          scriptures:["Isaiah 61:5","John 6:35"]},
        quota:{used:13, limit:40, remaining:27, resets_label:"Sep 1"}
      });
      if (g === "degraded") return Promise.resolve({
        ok:true, degraded:true, provider:"SelahCue AI",
        draft:{title:"Offline outline", summary:null,
          sections:[{heading:"Outline", items:["point one"]}], scriptures:[]},
        quota:null
      });
      if (g === "quota_exceeded") return Promise.resolve({ok:false, error:"quota_exceeded", message:"monthly limit reached"});
      if (g === "transport") return Promise.reject("network down"); // invoke rejects → onGenerate .catch → transport
      if (g === "malformed") return Promise.resolve({ok:false, error:"malformed", message:"bad response"});
      return Promise.resolve({ok:false, error:"not_configured", message:"the SelahCue cloud service is not configured"});
    }
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

      // === Live Console slide picker (LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec §1/§2/§4) ===
      // Default (a scripture is staged): Slides tab disabled + its panel hidden (computed display —
      // a class rule must not defeat [hidden] in WKWebView).
      ok(el("ctab-slides").getAttribute("aria-disabled")==="true", "SP: Slides tab disabled when no presentation is staged");
      ok(getComputedStyle(el("cpanel-slides")).display === "none", "SP: Slides panel hidden by COMPUTED display by default (WKWebView-safe)");
      ok(el("ctab-scriptures").getAttribute("aria-selected")==="true", "SP: Scriptures is the default active content tab");

      // Stage a presentation (a slide_group item linked to deck 7) in the real view; the 1s poll and
      // a direct sync agree because V is mutated. The filmstrip auto-surfaces + lists the deck's slides.
      V.items = [V.items[0], {id:2, kind:"slide_group", title:"Sermon Slides", is_live:false, is_staged:true, slide_count:3, slide_index:0, staged_slide_index:0, link:{kind:"deck", id:7, slide_count:3}}];
      V.staged_index = 1; V.staged_scripture = null;
      window.__syncSlides(JSON.parse(JSON.stringify(V)));
      await waitFor(function(){ return el("slide-strip").querySelectorAll(".slide-card").length === 3; });
      ok(!el("ctab-slides").hasAttribute("aria-disabled"), "SP: Slides tab enabled when a presentation is staged");
      ok(el("ctab-slides").getAttribute("aria-selected")==="true", "SP: auto-switched to the Slides tab on staging a presentation");
      ok(getComputedStyle(el("cpanel-slides")).display !== "none", "SP: Slides panel visible by COMPUTED display when active");
      ok(getComputedStyle(el("scriptures")).display === "none", "SP: Scriptures panel hidden when Slides is active ([hidden] wins over its flex display)");
      ok(el("slide-strip").querySelectorAll('[role="option"]').length === 3, "SP: the filmstrip lists all 3 slides as role=option cards");
      ok(el("slides-count").textContent === "3" && !el("slides-count").hidden, "SP: the Slides tab count badge reflects slide_count");
      ok((el("slide-strip").querySelector(".slide-card").getAttribute("aria-label")||"").indexOf("Grace That Feeds")>=0, "SP: a slide's aria-label carries its label text");
      ok(el("slide-strip").querySelectorAll(".slide-card")[0].classList.contains("staged"), "SP: the staged slide (0) is ringed PREVIEW");
      var __t0 = el("slide-strip").querySelectorAll(".slide-card")[0].querySelector(".slide-card-tag");
      ok(__t0 && __t0.textContent === "PREVIEW", "SP: PREVIEW is a text tag (never colour-only)");
      await waitFor(function(){ return window.__calls.some(function(c){return c.cmd==="render_plan_deck_slide" && c.args.deckId===7;}); });
      ok(window.__calls.some(function(c){return c.cmd==="render_plan_deck_slide" && c.args.deckId===7;}), "SP: thumbnails render lazily via render_plan_deck_slide");

      // Clicking a slide stages it to Preview (select_slide) — NEVER Live (FR-012).
      var __cb = window.__calls.length;
      el("slide-strip").querySelectorAll(".slide-card")[2].click();
      await waitFor(function(){ return window.__calls.some(function(c){return c.cmd==="select_slide" && c.args.slideIndex===2;}); });
      ok(window.__calls.some(function(c){return c.cmd==="select_slide" && c.args.itemId===2 && c.args.slideIndex===2;}), "SP: clicking slide 3 invokes select_slide{itemId:2, slideIndex:2}");
      ok(!window.__calls.slice(__cb).some(function(c){return c.cmd==="go_live";}), "SP: a slide click stages Preview only — never go_live (FR-012)");
      // B1 fix: the PREVIEW ring actually MOVES to the picked slide (it was stuck on slide 1 while the
      // host clamped every deck stage to 0). Proven end-to-end via staged_slide_index.
      await waitFor(function(){ return el("slide-strip").querySelectorAll(".slide-card")[2].classList.contains("staged"); });
      ok(el("slide-strip").querySelectorAll(".slide-card")[2].classList.contains("staged"), "SP: staging slide 3 moves the PREVIEW ring to slide 3 (B1 fixed — no longer stuck on slide 1)");
      ok(!el("slide-strip").querySelectorAll(".slide-card")[0].classList.contains("staged"), "SP: slide 1 is no longer the staged slide");

      // Enter routes the ACTUAL deck slide to Live via the authored-slide present path (NOT the
      // plan-item go_live, which would show only the item title). The presented slide is then marked
      // LIVE by live_authored_id.
      var __lb = window.__calls.length;
      el("slide-strip").dispatchEvent(new KeyboardEvent("keydown", {key:"Enter", bubbles:true}));
      await waitFor(function(){ return window.__calls.slice(__lb).some(function(c){return c.cmd==="present_plan_deck_slide";}); });
      ok(window.__calls.slice(__lb).some(function(c){return c.cmd==="present_plan_deck_slide" && c.args.deckId===7;}), "SP: Enter routes the REAL deck slide to Live (present_plan_deck_slide, not the plan title)");
      ok(!window.__calls.slice(__lb).some(function(c){return c.cmd==="go_live";}), "SP: go-live for a deck does NOT use the plan-item go_live (which shows the title)");
      await waitFor(function(){ return el("slide-strip").querySelector(".slide-card.live") != null; });
      ok(el("slide-strip").querySelector(".slide-card.live") != null, "SP: the presented slide is marked LIVE (via live_authored_id)");
      // The global GO LIVE button also routes the staged deck slide (not the plan title).
      var __gb = window.__calls.length;
      el("golive").click();
      await waitFor(function(){ return window.__calls.slice(__gb).some(function(c){return c.cmd==="present_plan_deck_slide";}); });
      ok(window.__calls.slice(__gb).some(function(c){return c.cmd==="present_plan_deck_slide";}), "SP: the GO LIVE button routes the staged deck slide (present_plan_deck_slide)");
      ok(window.__consoleDeckPreview && window.__consoleDeckPreview.deckId===7, "SP: the staged deck slide is published for GO LIVE + the Preview panel render");

      // Arrow keys move + stage the neighbouring slide (Preview only).
      var __ab = window.__calls.length;
      el("slide-strip").dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowLeft", bubbles:true}));
      await waitFor(function(){ return window.__calls.slice(__ab).some(function(c){return c.cmd==="select_slide";}); });
      ok(window.__calls.slice(__ab).some(function(c){return c.cmd==="select_slide";}), "SP: ArrowLeft moves + stages the previous slide (Preview)");

      // A removed linked deck → the honest 'presentation missing' state (no crash, FR-007).
      V.items[1].link.id = 999;
      window.__syncSlides(JSON.parse(JSON.stringify(V)));
      await waitFor(function(){ return !el("slides-empty").hidden; });
      ok(!el("slides-empty").hidden && el("slides-empty-msg").textContent.toLowerCase().indexOf("missing")>=0, "SP: a removed linked deck shows the honest 'presentation missing' state");

      // Bounded memory (spec §2 / no-leak): a large deck must not retain O(N) thumbnails. Stage an
      // 80-slide presentation, walk every card, and assert the thumbnail LRU stays capped.
      V.items = [V.items[0], {id:3, kind:"slide_group", title:"Big Deck", is_live:false, is_staged:true, slide_count:80, slide_index:0, staged_slide_index:0, link:{kind:"deck", id:8, slide_count:80}}];
      V.staged_index = 1; V.staged_scripture = null;
      window.__syncSlides(JSON.parse(JSON.stringify(V)));
      await waitFor(function(){ return el("slide-strip").querySelectorAll(".slide-card").length === 80; });
      ok(el("slide-strip").querySelectorAll(".slide-card").length === 80, "SP: a large (80-slide) deck lists every card");
      await window.__slidesDebug.renderAll(); // simulate a full scroll-through: render each card once
      ok(window.__slidesDebug.thumbCacheSize() <= 60, "SP: the thumbnail cache stays bounded (LRU cap) after rendering 80 slides — no O(N) growth (spec §2, no-leak)");

      // De-stage the presentation (a scripture staged) → Slides disabled + back to Scriptures. Restore V.
      V.items = [{id:1, kind:"scripture", title:"Genesis 1:13", is_live:true, is_staged:true}];
      V.staged_index = 0; V.staged_scripture = "Genesis 1:13";
      window.__syncSlides(JSON.parse(JSON.stringify(V)));
      ok(el("ctab-slides").getAttribute("aria-disabled")==="true", "SP: Slides tab disabled again when a scripture is staged");
      ok(el("ctab-scriptures").getAttribute("aria-selected")==="true", "SP: returns to Scriptures when the presentation is de-staged");

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

      // The Delete KEY removes the selected element in ONE press (global capture handler), distinct
      // from the button's two-click arm. Add a throwaway shape and delete it with a single Delete.
      addShape();
      var nKbdDel = applied().elements.length;
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"Delete", bubbles:true}));
      ok(applied().elements.length===nKbdDel-1, "TD: a single Delete keypress removes the selected element");

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

      // === Undo/redo (⌘Z / ⌘⇧Z): the Theme Designer's client-side snapshot history (tdHistory).
      // The document is the serialisable tdTheme object; ⌘Z/⌘⇧Z walk a bounded snapshot stack.
      // Typography reverts are read from the td-size field (tdSync updates it SYNCHRONOUSLY on
      // undo, before the debounced canvas re-render); structural reverts are read from applied()
      // (the last preview_theme JSON) after letting the 120ms debounce publish.
      el("surface-theme-designer").classList.add("active"); // ⌘Z acts only while the designer is up
      var undoZ = function(shift){ document.dispatchEvent(new KeyboardEvent("keydown",{key:"z",metaKey:true,shiftKey:!!shift,bubbles:true})); };
      var loadFreshTheme = function(){ el("td-themes").querySelector('.td-theme-row:not(.td-theme-saved) .td-theme-name').click(); };
      // (1) A typography edit undoes and redoes.
      loadFreshTheme(); await sleep(20);
      var szBase = el("td-size").value;
      var szEdit = (szBase === "7.5") ? "8.5" : "7.5";
      el("td-size").value = szEdit; el("td-size").dispatchEvent(new Event("input"));
      ok(el("td-size").value === szEdit && szEdit !== szBase, "undo(1): SIZE edited away from the loaded baseline");
      undoZ(false);
      ok(el("td-size").value === szBase, "undo(1): ⌘Z reverts the SIZE edit to the loaded value");
      undoZ(true);
      ok(el("td-size").value === szEdit, "undo(1): ⌘⇧Z re-applies the reverted SIZE edit");
      // (2) A new edit after an undo clears the redo branch (⌘⇧Z then does nothing).
      undoZ(false);
      ok(el("td-size").value === szBase, "undo(2): ⌘Z back to baseline (a redo is now available)");
      var szNew = (szBase === "9.5") ? "5.5" : "9.5";
      el("td-size").value = szNew; el("td-size").dispatchEvent(new Event("input")); // a NEW edit
      undoZ(true); // the pending redo was invalidated by the new edit
      ok(el("td-size").value === szNew, "undo(2): a new edit clears the redo branch (⌘⇧Z is a no-op)");
      // (3) Adding an element is undoable via ⌘Z (element count, debounce-published).
      loadFreshTheme(); await sleep(160);
      var nStart = (applied().elements || []).length;
      addShape(); await sleep(160);
      ok((applied().elements || []).length === nStart + 1, "undo(3): a shape was added (+1 element)");
      undoZ(false); await sleep(160);
      ok((applied().elements || []).length === nStart, "undo(3): ⌘Z removes the added shape (count back to start)");
      undoZ(true); await sleep(160);
      ok((applied().elements || []).length === nStart + 1, "undo(3): ⌘⇧Z re-adds the shape (+1 again)");
      // (4) A pointer gesture spanning multiple inputs collapses to ONE undo step (coalescing).
      loadFreshTheme(); await sleep(20);
      var szPreVal = el("td-size").value;
      var surfTD = el("surface-theme-designer");
      surfTD.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true})); // open a coalescing gesture
      el("td-size").value = "6.0"; el("td-size").dispatchEvent(new Event("input"));
      el("td-size").value = "6.5"; el("td-size").dispatchEvent(new Event("input"));
      window.dispatchEvent(new PointerEvent("pointerup",{bubbles:true})); // seal → the whole drag is one step
      ok(el("td-size").value === "6.5", "undo(4): a two-input pointer gesture set SIZE to 6.5");
      undoZ(false);
      ok(el("td-size").value === szPreVal, "undo(4): ONE ⌘Z reverts the WHOLE gesture (coalesced, not just the last input)");
      // (5) Undoing past the start is a safe no-op — the editor stays usable afterward.
      undoZ(false); undoZ(false); undoZ(false); undoZ(false);
      el("td-size").value = "8.0"; el("td-size").dispatchEvent(new Event("input"));
      ok(el("td-size").value === "8.0", "undo(5): undoing past the start does not corrupt — editing still works");

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
      // ←/→ switch the Timer|Stage sub-tabs via the keyboard (APG tablist parity with the other tabs).
      segStage.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowLeft", bubbles:true}));
      ok(!stabTimer.hidden && stabStage.hidden && segTimer.getAttribute("aria-selected") === "true",
         "stage: ← switches the Timer|Stage sub-tabs via the keyboard");
      segTimer.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowRight", bubbles:true}));
      ok(!stabStage.hidden && segStage.getAttribute("aria-selected") === "true",
         "stage: → returns to the Stage sub-tab (keyboard tablist)");
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
      // Restore the detection the following flow test depends on (do NOT clear it), now with the
      // provenance fields — translation + the transcript segment it was heard in.
      render(Object.assign({}, baseView, {
        detections: [
          { id: 991, reference: "John 3:16", text: "For God so loved the world", confidence: 95,
            translation: "KJV", source_segment: 42 },
        ],
        transcript: [{ id: 42, text: "turn to John three sixteen", start_ms: 3000, end_ms: 5000 }],
      }));
      // A bare detection must NOT display anything: no Preview/Live change, no chapter opened.
      ok(!window.__calls.some(function(c){ return c.cmd === "get_chapter" && c.args && c.args.reference === "John 3:16"; }),
         "flow: a detection does NOT open its chapter or touch Preview/Live (nothing until Stage/Approve)");
      // The card renders the translation label + the source-phrase / "spoken Ns ago" provenance line.
      var det0 = el("detections-list").querySelector(".detection");
      var tr0 = det0 && det0.querySelector(".det-translation");
      ok(tr0 && tr0.textContent === "KJV", "card: the detection shows its translation label (KJV)");
      var meta0 = det0 && det0.querySelector(".det-meta");
      ok(meta0 && /spoken .+ ago/.test(meta0.textContent) && meta0.textContent.indexOf("John three sixteen") >= 0,
         "card: the detection shows its source phrase + 'spoken Ns ago' provenance");
      // Stage = accept into PREVIEW ONLY (nothing auto-goes-live — FR-115) + open the chapter.
      var goLiveBeforeStage = window.__calls.filter(function(c){ return c.cmd === "go_live"; }).length;
      det0.querySelector(".det-stage").click();
      await sleep(15);
      ok(window.__calls.some(function(c){ return c.cmd === "approve_detection" && c.args && c.args.detectionId === 991; }),
         "flow: Stage → approve_detection (stages the verse in Preview)");
      ok(window.__calls.filter(function(c){ return c.cmd === "go_live"; }).length === goLiveBeforeStage,
         "flow: Stage does NOT go live on its own (nothing auto-goes-live — FR-115)");
      ok(window.__calls.some(function(c){ return c.cmd === "get_chapter" && c.args && c.args.reference === "John 3:16"; }),
         "flow: Stage → the full chapter opens in the Scriptures browser");
      // Approve = accept AND push Live to the audience in one action (the fast path).
      render(Object.assign({}, baseView, { detections: [
        { id: 991, reference: "John 3:16", text: "For God so loved the world", confidence: 95 },
      ] }));
      var goLiveBeforeApprove = window.__calls.filter(function(c){ return c.cmd === "go_live"; }).length;
      el("detections-list").querySelector(".det-approve").click();
      await sleep(15);
      ok(window.__calls.filter(function(c){ return c.cmd === "go_live"; }).length > goLiveBeforeApprove,
         "flow: Approve → go_live (operator confirmed → pushed Live to the audience)");
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

      // === WINDOW SEMANTICS: for the two BUILT-IN screens (main/stage) the `enabled` flag means
      // THE OS OUTPUT WINDOW EXISTS — toggling off destroys the window, toggling on re-creates
      // it, and the window's own close button performs the identical action. The page must
      // therefore read "closed", never "muted"/"live". A VIRTUAL feed (lower-third/stream) has
      // NO window: its flag still gates NDI only, so window language must never leak onto it. ===
      var pillOf = function(id){ var p = rowFor(id).querySelector(".scr-pill"); return p ? p.textContent : ""; };
      var metaOf = function(id){ var m = rowFor(id).querySelector(".scr-card-meta"); return m ? m.textContent : ""; };
      var ariaOf = function(id){ return rowFor(id).querySelector(".screen-enable-toggle").getAttribute("aria-label") || ""; };
      // `main` is disabled by the focus check above, so it is the closed built-in here.
      ok(/CLOSED/.test(pillOf("main")),
         "window: a disabled BUILT-IN screen reads CLOSED (pill=" + pillOf("main") + ")");
      ok(!/MUTED/.test(pillOf("main")) && !/LIVE/.test(pillOf("main")) && !/CONNECTED/.test(pillOf("main")),
         "window: a closed built-in never claims LIVE/CONNECTED/MUTED (pill=" + pillOf("main") + ")");
      ok(/No output window/.test(metaOf("main")),
         "window: a closed built-in's meta line reports NO output window (meta=" + metaOf("main") + ")");
      // KNOWN TRAP in this webview: a class `display` rule defeats the `hidden` attribute, so a
      // node can be in the DOM and still unpainted. Assert COMPUTED DISPLAY + a real box, not
      // mere presence — otherwise "the pill says CLOSED" could pass while nobody can see it.
      var closedPill = rowFor("main").querySelector(".scr-pill");
      ok(getComputedStyle(closedPill).display !== "none" && closedPill.getClientRects().length > 0,
         "window: the CLOSED pill is actually PAINTED (computed display=" + getComputedStyle(closedPill).display + ")");
      ok(/^Open the .+ output window$/.test(ariaOf("main")),
         "window: a closed built-in's switch announces it will OPEN the output window (aria=" + ariaOf("main") + ")");
      ok(/^Close the .+ output window$/.test(ariaOf("stage")),
         "window: an open built-in's switch announces it will CLOSE the output window (aria=" + ariaOf("stage") + ")");
      // The switch stays a real, labelled, keyboard-operable checkbox (accessible switch intact).
      var mainSwitch = rowFor("main").querySelector(".screen-enable-toggle");
      ok(mainSwitch.tagName === "INPUT" && mainSwitch.type === "checkbox" && !mainSwitch.disabled
         && mainSwitch.checked === false,
         "window: the enable control is still a labelled, operable checkbox reflecting the closed state");
      // DIMMING IS SCOPED TO THE PREVIEW THUMBNAIL. A closed card is the only route back to an
      // open output window, so its controls must stay fully legible; at the old whole-card
      // opacity 0.5 the meta line measured 1.80:1 and the CLOSED pill 2.78:1, both under AA.
      // Assert EFFECTIVE opacity — the product of every ancestor's own opacity up to the list.
      // Reading computed opacity on the control ALONE would be a tautology: the old rule put
      // 0.5 on the CARD, so a control's own computed value was "1" before and after the fix.
      var listEl = document.getElementById("screens-list");
      var effOpacity = function(node){
        var v = 1;
        for (var n = node; n && n !== listEl; n = n.parentElement) {
          var o = parseFloat(getComputedStyle(n).opacity);
          if (!isNaN(o)) v *= o;
        }
        return v;
      };
      var closedCard = rowFor("main");
      // NB: measure the VISIBLE switch (.scr-toggle wrapper + .scr-toggle-knob). The <input>
      // itself is deliberately opacity:0 — it is the invisible hit target, and the knob draws
      // the switch — so asserting on the input would always read 0 and mean nothing.
      var knobEff = effOpacity(closedCard.querySelector(".scr-toggle-knob"));
      var pillEff = effOpacity(closedCard.querySelector(".scr-pill"));
      var thumbEff = effOpacity(closedCard.querySelector(".scr-thumb"));
      ok(knobEff === 1 && effOpacity(closedCard.querySelector(".scr-card-enable")) === 1,
         "dimming: the enable switch on a CLOSED card renders at FULL opacity (eff=" + knobEff + ")");
      ok(pillEff === 1,
         "dimming: the CLOSED pill renders at FULL opacity (eff=" + pillEff + ")");
      ok(effOpacity(closedCard.querySelector(".scr-card-name")) === 1
         && effOpacity(closedCard.querySelector(".scr-card-meta")) === 1,
         "dimming: the card name and meta line on a CLOSED card render at FULL opacity");
      ok(thumbEff === 0.5,
         "dimming: the PREVIEW THUMBNAIL is the ONLY dimmed part of a closed card (eff=" + thumbEff + ")");
      // A VIRTUAL feed: NDI-gating wording only, no window language anywhere.
      ok(/MUTED/.test(pillOf("lower-third")) && !/CLOSED/.test(pillOf("lower-third")),
         "window: a disabled VIRTUAL feed stays MUTED — it has no window to close (pill=" + pillOf("lower-third") + ")");
      ok(/COMPOSED/.test(pillOf("stream")),
         "window: an enabled virtual feed still reads COMPOSED (pill=" + pillOf("stream") + ")");
      ok(!/window/i.test(ariaOf("lower-third")) && !/window/i.test(ariaOf("stream")),
         "window: a virtual feed's switch never mentions an output window (aria=" + ariaOf("lower-third") + ")");
      ok(!/window/i.test(metaOf("lower-third")),
         "window: a virtual feed's meta line never mentions an output window (meta=" + metaOf("lower-third") + ")");

      // === CLOSE-BUTTON PATH: closing the output window with its own OS close button changes
      // `enabled` on the HOST with no operator interaction in this webview. Mutate the host view
      // directly (NO click anywhere) and let the app's own 1 s poll deliver it. ===
      var stageCb = function(){ return rowFor("stage").querySelector(".screen-enable-toggle"); };
      ok(stageCb().checked === true, "close-button: the stage switch starts ON (window open)");
      var enabledCalls = function(){
        return window.__calls.filter(function(c){ return c.cmd === "set_screen_enabled"; }).length;
      };
      var callsBeforeClose = enabledCalls();
      V.screens.forEach(function(s){ if (s.screen === "stage") s.enabled = false; });
      await waitFor(function(){ return stageCb() && stageCb().checked === false; }, 120); // 2.4s > the 1s poll
      ok(stageCb().checked === false,
         "close-button: an externally-closed window flips the switch OFF with NO operator interaction");
      ok(/CLOSED/.test(pillOf("stage")),
         "close-button: the externally-closed screen's pill becomes CLOSED (pill=" + pillOf("stage") + ")");
      ok(enabledCalls() === callsBeforeClose,
         "close-button: the page REFLECTED the close without echoing a set_screen_enabled back at the host");

      // === DEFERRED REBUILD: a focused <select> defers the grid rebuild so an open picker is
      // never yanked away. That deferral must NOT also freeze the enable switch — a <select> can
      // hold focus indefinitely, and `enabled` now changes with no operator input. Driven on
      // `main` in the OPEN direction (it is still closed from the checks above), which also
      // keeps this block to ONE poll of virtual time.
      var mainCb = function(){ return rowFor("main").querySelector(".screen-enable-toggle"); };
      ok(mainCb().checked === false, "deferred: main starts CLOSED before the deferral test");
      var inspSel = document.getElementById("screens-inspector").querySelector("select");
      inspSel.focus();
      var selOptionCount = inspSel.options.length;
      ok(!!inspSel && document.activeElement === inspSel,
         "deferred: an inspector <select> holds focus (the grid rebuild is now deferred)");
      V.screens.forEach(function(s){ if (s.screen === "main") s.enabled = true; });
      await waitFor(function(){ return mainCb() && mainCb().checked === true; }, 120);
      ok(mainCb().checked === true,
         "deferred: an externally-reopened window STILL flips the switch ON while a <select> holds focus");
      ok(!/CLOSED/.test(pillOf("main")),
         "deferred: the status pill reconciles in place too (pill=" + pillOf("main") + ")");
      ok(!rowFor("main").classList.contains("screen-disabled"),
         "deferred: the reopened card is un-dimmed by the in-place reconcile");
      ok(!/No output window/.test(metaOf("main")),
         "deferred: the meta line reconciles in place too (meta=" + metaOf("main") + ")");
      ok(document.activeElement === inspSel && inspSel.isConnected && inspSel.options.length === selOptionCount,
         "deferred: the open <select> is NOT destroyed by the reconcile (still focused, options intact)");
      // The revert must read the RECONCILED authoritative value, not this card's stale
      // render-pass closure: the card was reconciled IN PLACE (never rebuilt) and its closure
      // still holds enabled=false, so a closure read would snap the switch back OFF and deny a
      // window that is open. Read `checked` back SYNCHRONOUSLY — the onchange revert runs during
      // the click, before any deferred rebuild.
      window.__rejectSetEnabled = true;
      mainCb().click(); // attempt to close the reopened window — the stub rejects it
      var revertedTo = mainCb().checked;
      ok(revertedTo === true,
         "deferred: a REJECTED toggle reverts to the RECONCILED value, not the stale closure (got " + revertedTo + ")");
      window.__rejectSetEnabled = false;
      // Release the picker: the deferral lasts exactly as long as the <select> holds focus, and
      // a programmatic .click() does NOT move focus — so without this blur every later
      // renderOutputs would keep deferring and no new card would ever appear.
      inspSel.blur();
      await waitFor(function(){ return document.querySelectorAll('#screens-list .screen-row').length === 4
                                    && document.activeElement !== inspSel; });
      ok(mainCb().checked === true && !rowFor("main").classList.contains("screen-disabled"),
         "deferred: the full rebuild resumes once the <select> releases focus");

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
      ok(pmNav && !pmNav.dataset.nodigit && pmNav.querySelector(".nav-key").textContent === "⌘2", "PM: the Presentation item carries ⌘2 (menu-order digit)");
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

      // --- Command palette sections (Design 2.0): ACTIONS / NAVIGATE / SCRIPTURES, with the whole
      //     top-level app menu mirrored under NAVIGATE carrying its ⌘ badges. ---
      window.__cmdPalette.open();
      el("cmd-input").value = ""; el("cmd-input").dispatchEvent(new Event("input"));
      var pGroups = Array.from(document.querySelectorAll("#cmd-list .cmd-group")).map(function(g){ return g.textContent; });
      ok(pGroups.indexOf("ACTIONS") >= 0 && pGroups.indexOf("NAVIGATE") >= 0, "Palette: renders ACTIONS + NAVIGATE section headers");
      ok(document.querySelector("#cmd-list .cmd-item").textContent.indexOf("Go Live") >= 0, "Palette: Go Live is the first ACTIONS item");
      var pItems = Array.from(document.querySelectorAll("#cmd-list .cmd-item")).map(function(li){ return li.textContent; });
      ok(pItems.some(function(t){ return /Go to Presentation/.test(t) && /⌘2/.test(t); }), "Palette: NAVIGATE mirrors 'Go to Presentation' with its ⌘2 badge");
      ok(["Live Console","Presentation","Theme Designer","Screens & Outputs","Service Plan","Transcript & Notes","Settings"].every(function(n){ return pItems.some(function(t){ return t.indexOf("Go to "+n) >= 0; }); }), "Palette: NAVIGATE lists all seven top-level app menu items");
      el("cmd-input").value = "grace"; el("cmd-input").dispatchEvent(new Event("input"));
      ok(Array.from(document.querySelectorAll("#cmd-list .cmd-group")).some(function(g){ return g.textContent === "SCRIPTURES"; }) &&
         Array.from(document.querySelectorAll("#cmd-list .cmd-item")).some(function(li){ return /Search "grace" in Bible/.test(li.textContent); }),
         "Palette: a typed query adds a SCRIPTURES 'Search … in Bible' entry");
      window.__cmdPalette.closeAll();

      // --- Global presentation search (⌘/Ctrl+S) — a dedicated modal over `deck_search` that
      //     searches deck names + slide text and opens the chosen presentation in the editor. ---
      var gsLibSave = window.__LIB; // restore after so the later PM/Lib tests keep their fixture
      window.__LIB = { decks: [{id:71, name:"Grace Sunday", slides:5}, {id:72, name:"Hymns Vol. 2", slides:8}], open:71, persistent:true, nextId:90 };
      var gs = el("gsearch");
      var gsEv = new KeyboardEvent("keydown", {key:"s", metaKey:true, bubbles:true, cancelable:true});
      document.dispatchEvent(gsEv);
      ok(!gs.hidden, "gsearch: ⌘S opens the presentation-search modal");
      ok(gsEv.defaultPrevented, "gsearch: ⌘S prevents the browser save-page default");
      ok(gs.getAttribute("role")==="dialog" && gs.getAttribute("aria-modal")==="true", "gsearch: the modal is a real dialog (aria-modal)");
      var gi = el("gsearch-input");
      ok(document.activeElement === gi, "gsearch: focus lands in the search input on open");
      gi.value = "grace"; gi.dispatchEvent(new Event("input"));
      await sleep(180); // debounce (120ms) + the deck_search promise
      var gRows = document.querySelectorAll("#gsearch-list .gsearch-item");
      ok(gRows.length >= 2, "gsearch: typing a query renders result rows from deck_search");
      ok(Array.from(gRows).some(function(li){ return /Grace Sunday/.test(li.textContent); }), "gsearch: a NAME match renders");
      ok(Array.from(gRows).some(function(li){ var s=li.querySelector(".gsearch-sub"); return s && /slide 4/.test(s.textContent) && /amazing grace/i.test(s.textContent); }),
         "gsearch: a slide-CONTENT match shows the slide number + snippet");
      ok(el("gsearch-list").getAttribute("role") === "listbox" && !!document.querySelector("#gsearch-list .gsearch-item[role='option']"),
         "gsearch: results are a listbox of role=option rows (a11y)");
      // ↓ then Enter opens the selected presentation in the editor (deck_open + surface switch).
      var gOpenBefore = window.__calls.filter(function(c){ return c.cmd === "deck_open"; }).length;
      gi.dispatchEvent(new KeyboardEvent("keydown", {key:"ArrowDown", bubbles:true}));
      gi.dispatchEvent(new KeyboardEvent("keydown", {key:"Enter", bubbles:true}));
      await sleep(15);
      ok(window.__calls.filter(function(c){ return c.cmd === "deck_open"; }).length > gOpenBefore, "gsearch: Enter opens the selected presentation (deck_open)");
      ok(el("surface-presentation").classList.contains("active"), "gsearch: opening a result switches to the Presentation surface");
      ok(gs.hidden, "gsearch: selecting a result closes the modal");
      // ⌘S is suppressed while another modal (the palette) is open — one modal at a time.
      window.__cmdPalette.open();
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"s", metaKey:true, bubbles:true, cancelable:true}));
      ok(gs.hidden, "gsearch: ⌘S does NOT open the search while the command palette is open");
      window.__cmdPalette.closeAll();
      // Esc closes the search modal.
      window.__gsearch.open();
      ok(!gs.hidden, "gsearch: opens again via the API");
      el("gsearch-input").dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true}));
      ok(gs.hidden, "gsearch: Esc closes the modal");
      window.__LIB = gsLibSave; // restore the library fixture for the later PM/Lib tests

      // ⌘2 jumps to the Presentation surface from elsewhere (menu-order digit).
      document.querySelector('.nav-item[data-surface="console"]').click();
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"2", metaKey:true, bubbles:true}));
      ok(el("surface-presentation").classList.contains("active"), "PM: ⌘2 jumps to the Presentation surface");
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

      // The ⌘1–7 surface map follows menu order: ⌘2 → Presentation, ⌘3 → Theme Designer.
      document.dispatchEvent(new KeyboardEvent("keydown", {key:"3", metaKey:true, bubbles:true}));
      ok(el("surface-theme-designer").classList.contains("active") && !el("surface-presentation").classList.contains("active"),
         "PM: ⌘3 routes to Theme Designer (menu-order ⌘1–7 map)");

      // === Pre-service Check (moved into the Settings sidebar, Design 2.0) ===
      document.querySelector('.nav-item[data-surface="settings"]').click();
      document.querySelector('.set-nav[data-setpage="preservice"]').click();
      ok(el("surface-preservice").classList.contains("active"), "Pre-service: the Settings sidebar entry opens the surface");
      await waitFor(function(){ return document.querySelectorAll("#ps-sections .ps-row").length >= 10 && el("ps-passed").textContent !== "0"; });
      ok(document.querySelectorAll("#ps-sections .ps-row").length === 10,
         "Pre-service: all 10 checks render across the four sections");
      ok(document.querySelectorAll("#ps-sections .ps-section").length === 4,
         "Pre-service: four grouped sections (Displays / Media / Audio / Storage)");
      ok(el("ps-passed").textContent === "5" && el("ps-warnings").textContent === "1" && el("ps-blocking").textContent === "0",
         "Pre-service: readiness counts derive from live host data (5 passed · 1 warning · 0 blocking)");
      var psStt = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Transcription & AI/.test(r.textContent); });
      ok(psStt && psStt.querySelector(".ps-ico-ok") && /On-device STT ready/.test(psStt.textContent),
         "Pre-service: on-device STT ready reflects the real stt_ready probe");
      var psAudio = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row"))
        .find(function(r){ return /Input device/.test(r.textContent); });
      ok(psAudio && psAudio.querySelector(".ps-ico-ok") && /Focusrite/.test(psAudio.textContent),
         "Pre-service: Input device reflects the real audio_input probe (device name)");
      // STT model missing → the check becomes an attention warning (not a fabricated pass).
      window.__psStt = {ready:false, state:"not_downloaded", model:"Small", detail:"On-device model not downloaded yet"};
      el("ps-rerun").click();
      await waitFor(function(){ var r=Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Transcription & AI/.test(x.textContent);}); return r && r.querySelector(".ps-ico-warn"); });
      ok(true, "Pre-service: stt_ready 'not downloaded' → attention warning (honest, not a pass)");
      window.__psStt = null;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-passed").textContent === "5"; });
      // No input device → the Input device check becomes an attention warning (not a fabricated pass).
      window.__psAudio = {available:false, state:"no_device", name:"", channels:null, detail:"No microphone / input device detected"};
      el("ps-rerun").click();
      await waitFor(function(){ var r=Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Input device/.test(x.textContent);}); return r && r.querySelector(".ps-ico-warn"); });
      ok(true, "Pre-service: audio_input 'no device' → attention warning (honest, not a pass)");
      // Default (no-STT) build → 'not_in_build' → honest PENDING, never a fabricated pass.
      window.__psAudio = {available:false, state:"not_in_build", name:"", channels:null, detail:"Audio input check is not enabled in this build"};
      el("ps-rerun").click();
      await waitFor(function(){ var r=Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Input device/.test(x.textContent);}); return r && r.querySelector(".ps-ico-pending"); });
      var psAudioNib = Array.prototype.slice.call(document.querySelectorAll("#ps-sections .ps-row")).find(function(x){return /Input device/.test(x.textContent);});
      ok(psAudioNib && psAudioNib.querySelector(".ps-ico-pending") && el("ps-passed").textContent === "4",
         "Pre-service: audio_input 'not_in_build' → honest pending, not counted as passed (default build)");
      window.__psAudio = null;
      el("ps-rerun").click();
      await waitFor(function(){ return el("ps-passed").textContent === "5"; });
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
         "Pre-service: ⌘⇧K jumps to the surface (now reached from the Settings sidebar)");

      // === Remote Control (Figma 359:124) — now reached from Settings › Network & Mobile (it left the
      // top-nav, Figma 336:124), not a top-level nav item: pair/approve/role/revoke ===
      ok(!document.querySelector('.nav-item[data-surface="remote"]'),
         "Nav: Remote Control is no longer a top-level nav item (moved under Settings, Figma 336:124)");
      document.querySelector('.nav-item[data-surface="settings"]').click();
      setSettingsPage("network");
      ok(document.getElementById("set-page-network") && !document.getElementById("set-page-network").hidden,
         "Settings: the Network & Mobile page renders");
      document.getElementById("set-open-remote").click();
      ok(el("surface-remote").classList.contains("active"),
         "Settings › Network & Mobile → 'Manage devices' opens the Remote Control surface");
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
      ok(el("surface-settings").classList.contains("active") && !document.getElementById("set-page-network").hidden,
         "Remote: ⌘⇧R now opens Settings › Network & Mobile (Remote left the top-nav; ⌘1–7 map intact)");

      // === Service Plan builder (86ajxxuz9, Figma 614:124) — the `plan` surface is a real
      // builder (palette · run sheet · inspector) with link status + link/unlink flows, and a
      // plan edit NEVER changes Live. The CI driver never navigated here before, so the builder
      // + link states had zero behavioural coverage; these checks close that gap. ==============
      var isLiveCtrl = function(c){ return ["go_live","next","select","blackout","clear","start_timer"].indexOf(c.cmd) >= 0; };
      var ctrlBefore = window.__calls.filter(isLiveCtrl).length;
      // #6/#7 fix: the console resolves deck-link chips at BOOT (planDecks loaded WITHOUT ever
      // visiting the plan surface). No plan nav has happened yet, so a non-null resolution here
      // proves the boot-time load; the boot fixture's deck id 2 is "Sermon: Grace That Feeds".
      ok(typeof planDeckName === "function" && planDeckName(2) === "Sermon: Grace That Feeds",
         "SP C-001: the console resolves deck-link names at boot (planDecks loaded before any plan visit)");
      // This block owns its deck fixture: an earlier library test empties __LIB.decks (the
      // 'No presentations yet' state), so restore a known list BEFORE planActivate loads it —
      // deck-link chips resolve names from deck_list, and the picker lists these decks.
      window.__LIB = window.__LIB || {};
      window.__LIB.decks = [{id:2, name:"Sermon: Grace That Feeds", slides:2}, {id:5, name:"Youth Night — Identity", slides:12}];
      window.__LIB.open = 2; window.__LIB.persistent = true; window.__LIB.nextId = 6;
      document.querySelector('.nav-item[data-surface="plan"]').click(); // showSurface("plan") → planActivate
      ok(el("surface-plan").classList.contains("active"), "SP: the plan nav opens the Service Plan builder surface");
      await sleep(60); // let planActivate resolve invoke("view") + invoke("deck_list") (deck names for chips)
      // C-002: the three builder regions replace the placeholder.
      var palette = el("plan-palette-btns");
      ok(palette && palette.querySelectorAll(".plan-palette-btn").length === 7,
         "SP C-002: the Add-item palette lists all 7 item kinds (got " + (palette ? palette.querySelectorAll(".plan-palette-btn").length : "none") + ")");
      ok(!!el("plan-b-list") && !!el("plan-b-insp"), "SP C-002: the run sheet + item inspector regions exist");
      // Palette wiring: clicking a kind sends add_item{kind,title}.
      palette.querySelector('.plan-palette-btn').click();
      await sleep(20);
      ok(window.__calls.some(function(c){return c.cmd==="add_item";}), "SP: a palette button sends add_item to the host");
      // ⌘Z / ⌘⇧Z on the plan surface drive the backend-authoritative run-sheet undo/redo.
      var __pu = window.__calls.length;
      document.dispatchEvent(new KeyboardEvent("keydown",{key:"z",metaKey:true,bubbles:true}));
      await sleep(10);
      ok(window.__calls.slice(__pu).some(function(c){return c.cmd==="plan_undo";}), "SP: ⌘Z on the plan surface invokes plan_undo (backend history)");
      document.dispatchEvent(new KeyboardEvent("keydown",{key:"z",metaKey:true,shiftKey:true,bubbles:true}));
      await sleep(10);
      ok(window.__calls.slice(__pu).some(function(c){return c.cmd==="plan_redo";}), "SP: ⌘⇧Z on the plan surface invokes plan_redo");

      // === Offline download modal (Figma 396-124): ONE dialog, 7 states, driven by stt://phase.
      var dlBack = el("dl-modal-back");
      ok(dlBack.hidden, "DL: the download modal is hidden until a phase arrives");
      // (1) Downloading — progress bar + 'X of Y' bytes + Hide/Cancel, no primary.
      window.__dlModal.onPhase({phase:"downloading", done:650000000, total:1600000000, pct:41});
      ok(!dlBack.hidden && getComputedStyle(dlBack).display!=="none", "DL(1): a downloading phase opens the modal (computed display, not just attr)");
      ok(el("dl-modal-progfill").getAttribute("aria-valuenow")==="41", "DL(1): the progressbar reflects the percent");
      ok(el("dl-modal-progbytes").textContent.indexOf("of")>=0 && el("dl-modal-progbytes").textContent.indexOf("GB")>=0, "DL(1): bytes render as 'X of Y GB'");
      ok(!el("dl-modal-hide").hidden && !el("dl-modal-secondary").hidden && el("dl-modal-primary").hidden, "DL(1): Downloading offers Hide + Cancel, no primary");
      // (2) Verifying — indeterminate bar, Cancel only, Esc-cancel still allowed but no Hide.
      window.__dlModal.onPhase({phase:"verifying"});
      ok(el("dl-modal-progwrap").classList.contains("is-indeterminate"), "DL(2): Verifying shows an indeterminate bar");
      ok(el("dl-modal-progfill").getAttribute("aria-valuenow")===null, "DL(2): the bar is indeterminate (no aria-valuenow)");
      ok(el("dl-modal-hide").hidden && !el("dl-modal-secondary").hidden, "DL(2): Verifying hides Hide, keeps Cancel");
      // (3) Ready — success (green) icon + Start listening primary.
      window.__dlModal.onPhase({phase:"ready"});
      ok(el("dl-modal-ico").classList.contains("is-ready"), "DL(3): Ready shows the success (green) icon");
      ok(!el("dl-modal-primary").hidden && el("dl-modal-primary").textContent.indexOf("Start")>=0, "DL(3): Ready offers the primary Start listening");
      ok(window.__dlModal.state()==="ready", "DL(3): the controller is in the ready state");
      // (4) Couldn't connect — warn, Retry + Cancel.
      window.__dlModal.onPhase({phase:"downloading", done:200000000, total:1600000000, pct:12});
      window.__dlModal.onPhase({phase:"failed", reason:"connect", message:"reset", resumable:false, bytes_kept:0});
      ok(el("dl-modal-ico").classList.contains("is-warn") && el("dl-modal-title").textContent.indexOf("interrupted")>=0, "DL(4): a connect failure shows 'Download interrupted' (warn)");
      ok(!el("dl-modal-primary").hidden && el("dl-modal-primary").textContent==="Retry", "DL(4): couldn't-connect offers Retry");
      // (5) Couldn't verify — integrity (red) icon, progress hidden, discarded.
      window.__dlModal.onPhase({phase:"downloading", done:1, total:1600000000, pct:99});
      window.__dlModal.onPhase({phase:"failed", reason:"verify", message:"sha mismatch", resumable:false, bytes_kept:0});
      ok(el("dl-modal-ico").classList.contains("is-integrity"), "DL(5): a verify failure shows the integrity (red) icon");
      ok(el("dl-modal-title").textContent.indexOf("verified")>=0 && el("dl-modal-progwrap").hidden, "DL(5): couldn't-verify names the failure + hides the progress bar");
      // (6) Offline — Try again + Not now.
      window.__dlModal.onPhase({phase:"downloading", done:1, total:1600000000, pct:3});
      window.__dlModal.onPhase({phase:"failed", reason:"offline", message:"dns", resumable:false, bytes_kept:0});
      ok(el("dl-modal-title").textContent.toLowerCase().indexOf("offline")>=0, "DL(6): an offline failure shows 'You're offline'");
      ok(el("dl-modal-primary").textContent==="Try again" && el("dl-modal-secondary").textContent==="Not now", "DL(6): offline offers Try again + Not now");
      // Cancel aborts the in-flight download (cancel_download) and closes.
      var __cd = window.__calls.length;
      el("dl-modal-secondary").click();
      ok(window.__calls.slice(__cd).some(function(c){return c.cmd==="cancel_download";}), "DL: Cancel/Not-now invokes cancel_download (abort)");
      ok(dlBack.hidden, "DL: Cancel closes the modal");
      // A 'cancelled' failure echo (from the abort) closes silently — never an error state.
      window.__dlModal.onPhase({phase:"downloading", done:1, total:100, pct:1});
      window.__dlModal.onPhase({phase:"failed", reason:"other", message:"cancelled", resumable:false, bytes_kept:0});
      ok(dlBack.hidden, "DL: a 'cancelled' echo closes the modal silently (no error state)");
      // A lone `ready` with nothing active (warm cache hit) must NOT pop the modal.
      window.__dlModal.onPhase({phase:"ready"});
      ok(dlBack.hidden, "DL: a lone ready (warm cache hit) does not open the modal");
      // Hide backgrounds the download to a pill; progress keeps updating it; the pill re-opens it.
      window.__dlModal.onPhase({phase:"downloading", done:1, total:1600000000, pct:20});
      el("dl-modal-hide").click();
      ok(dlBack.hidden && !el("dl-pill").hidden, "DL: Hide backgrounds the modal to a pill");
      window.__dlModal.onPhase({phase:"downloading", done:1, total:1600000000, pct:55});
      ok(el("dl-pill").textContent.indexOf("55")>=0, "DL: progress keeps updating the background pill");
      el("dl-pill").click();
      ok(!dlBack.hidden && el("dl-pill").hidden, "DL: clicking the pill re-opens the modal");
      window.__dlModal.close();
      ok(dlBack.hidden, "DL: closing tidies up for later checks");
      // State 7 — the SAME dialog reused for a Bible translation (bible://phase carries name + id).
      window.__dlModal.onBiblePhase({phase:"downloading", name:"Young's Literal Translation", id:"ylt", done:5000000, total:12000000, pct:42});
      ok(!dlBack.hidden && el("dl-modal-title").textContent.indexOf("Young")>=0, "DL(7): a bible://phase opens the SAME modal, titled with the translation");
      ok(el("dl-modal-sub").textContent.toLowerCase().indexOf("translation")>=0, "DL(7): the subtitle names it a Bible translation (assetKind reuse)");
      window.__dlModal.onBiblePhase({phase:"ready", name:"Young's Literal Translation", id:"ylt"});
      ok(el("dl-modal-title").textContent.indexOf("ready")>=0 && el("dl-modal-ico").classList.contains("is-ready"), "DL(7): a translation reaches Ready in the same dialog");
      window.__dlModal.close();
      ok(dlBack.hidden, "DL(7): the reused dialog closes cleanly");
      // C-001 / C-005 read side: render a crafted plan covering every link state (scripture-linked,
      // deck-linked, deck-MISSING, unlinked) and assert the run-sheet chips. planRenderBuilder is a
      // global (top-level fn), driven directly the same way the M1 checks drive render().
      var planView = { plan_name:"Sunday", items:[
        {id:11, kind:"scripture",   title:"Opening Word",  is_live:false, is_staged:true,  link:{kind:"scripture", reference:"John 3:16", translation:"KJV"}},
        {id:12, kind:"slide_group", title:"Sermon Deck",   is_live:false, is_staged:false, link:{kind:"deck", id:2}},   // resolves to a name
        {id:13, kind:"slide_group", title:"Old Deck",      is_live:false, is_staged:false, link:{kind:"deck", id:99}},  // id gone → missing
        {id:14, kind:"scripture",   title:"Closing Prayer",is_live:false, is_staged:false}                              // unlinked
      ] };
      planRenderBuilder(planView);
      var bRows = document.querySelectorAll("#plan-b-list .plan-b-row");
      ok(bRows.length === 4, "SP C-001: the run sheet renders a typed row per plan item (got " + bRows.length + ")");
      var sChip = document.querySelector("#plan-b-list .link-scripture");
      ok(sChip && /John 3:16/.test(sChip.textContent) && /KJV/.test(sChip.textContent),
         "SP C-001: a scripture-linked item shows its reference + translation chip");
      var dChips = document.querySelectorAll("#plan-b-list .link-deck");
      ok(Array.prototype.some.call(dChips, function(c){return /Grace That Feeds/.test(c.textContent);}),
         "SP C-001: a deck-linked item resolves the deck name from the lazily-loaded deck list");
      var mChip = document.querySelector("#plan-b-list .link-missing");
      ok(mChip && /missing/i.test(mChip.textContent), "SP C-001: a deck whose id is gone shows a ⚠ missing chip");
      // C-005 inspector: a linked scripture item → chip + Change…/Unlink/Remove.
      document.querySelectorAll("#plan-b-list .plan-b-row")[0].click();
      var insp = el("plan-b-insp");
      ok(insp.querySelector(".link-scripture") && /John 3:16/.test(insp.textContent),
         "SP C-005: selecting a linked item shows its link in the inspector");
      ok(Array.prototype.some.call(insp.querySelectorAll(".pm-btn-primary"), function(b){return /Change/.test(b.textContent);}),
         "SP C-005: a linked item's inspector offers Change…");
      ok(Array.prototype.some.call(insp.querySelectorAll("button"), function(b){return b.textContent==="Unlink";}),
         "SP C-005: a linked item's inspector offers Unlink");
      ok(!!insp.querySelector(".pm-btn-danger"), "SP C-005: the inspector offers Remove item");
      ok(/never changes Live/.test(insp.textContent), "SP C-006: the inspector states editing here never changes Live");
      // #4 selection is exposed to AT via role=option + aria-selected (not border-colour alone);
      // #3 keyboard focus survives the list-rebuild (lands on the selected row, not <body>);
      // #5 the reorder buttons carry an accessible name.
      var selRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"]');
      ok(selRow && selRow.getAttribute("role") === "option" && selRow.getAttribute("aria-selected") === "true",
         "SP C-005 a11y: the selected run-sheet row is role=option aria-selected=true");
      ok(document.querySelector('#plan-b-list .plan-b-row[data-item-id="12"]').getAttribute("aria-selected") === "false",
         "SP C-005 a11y: an unselected row exposes aria-selected=false");
      ok(document.activeElement === selRow,
         "SP C-005 a11y: selecting a row keeps keyboard focus on it (survives the list rebuild)");
      var upBtn = document.querySelector('#plan-b-list .plan-b-up');
      ok(upBtn && /move/i.test(upBtn.getAttribute("aria-label") || ""),
         "SP C-007 a11y: the ↑/↓ reorder buttons have an accessible name");
      // C-005 unlinked state: distinct warning + a Link… affordance.
      document.querySelectorAll("#plan-b-list .plan-b-row")[3].click();
      var insp2 = el("plan-b-insp");
      ok(!!insp2.querySelector(".plan-insp-unlinked"), "SP C-005: an unlinked scripture item shows the 'no reference yet' warning");
      ok(/Link a scripture/.test(insp2.textContent), "SP C-005: an unlinked item offers Link a scripture…");
      // C-003 link-Scripture flow: the modal → set_item_content{kind:scripture,reference,translation}.
      var sicBefore = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      openLinkModal({id:14, kind:"scripture", title:"Closing Prayer"});
      var lm = document.querySelector(".pm-confirm.pm-link");
      ok(!!lm && lm.getAttribute("aria-modal")==="true", "SP C-007: the link modal is a labelled aria-modal dialog");
      // #2 the scripture modal opens with the reference input focused (not Cancel) — a keyboard
      // operator types the reference immediately.
      ok(document.activeElement === lm.querySelector('input[aria-label="Scripture reference"]'),
         "SP C-007 a11y: the scripture link modal opens with the reference input focused (not Cancel)");
      // #1 focus trap: Tab is contained within the dialog (the background console — which holds
      // live-control buttons — is NOT inert, so an escaping Tab could reach Go Live). A synthetic
      // Tab does NOT move focus natively, so asserting "focus stayed inside" would be tautological
      // (it passes even with the trap removed). Instead assert the trap ACTIVELY wraps focus from
      // the last control back to the first — that only happens if the Tab handler fired.
      var lmFoc = Array.prototype.filter.call(lm.querySelectorAll("button, input, select"), function(n){ return !n.disabled; });
      var lmFirst = lmFoc[0], lmLast = lmFoc[lmFoc.length - 1];
      lmLast.focus();
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
      ok(document.activeElement === lmFirst && lmFirst !== lmLast && lm.contains(document.activeElement),
         "SP C-007 a11y: Tab from the last control WRAPS to the first (the trap actively contains focus, not a no-op)");
      var refIn = lm.querySelector('input[aria-label="Scripture reference"]');
      refIn.value = "Romans 8:28";
      Array.prototype.filter.call(lm.querySelectorAll(".pm-btn-primary"), function(b){return b.textContent==="Link";})[0].click();
      await sleep(20);
      var sic = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      ok(sic.length > sicBefore && sic[sic.length-1].args.link && sic[sic.length-1].args.link.kind==="scripture" &&
         /Romans 8:28/.test(sic[sic.length-1].args.link.reference),
         "SP C-003: the link-Scripture flow sends set_item_content{link:{kind:scripture,reference}}");
      // === Frame 610:124 — scripture verse picker (chapter nav + verse list + verses/slide) =====
      openLinkModal({ id: 14, kind: "scripture", title: "Opening Word" });
      await sleep(20);
      var lmV = document.querySelector(".pm-confirm.pm-link");
      lmV.querySelector('input[aria-label="Scripture reference"]').value = "Isaiah 61:1";
      Array.prototype.filter.call(lmV.querySelectorAll("button"), function(b){return b.textContent==="Browse";})[0].click();
      await sleep(30); // get_chapter
      var vpick = lmV.querySelector(".pm-verse-picker");
      ok(vpick && !vpick.hidden, "SP2 C-003: Browse opens the verse picker (get_chapter)");
      ok(!!lmV.querySelector('.pm-verse-navbtn[aria-label="Next chapter"]') && !!lmV.querySelector('.pm-verse-navbtn[aria-label="Previous chapter"]'),
         "SP2 C-003: the picker has chapter next/prev nav");
      var vrows = lmV.querySelectorAll(".pm-verse");
      ok(vrows.length >= 1, "SP2 C-003: the verse list renders");
      ok(!!lmV.querySelector('.pm-verse-list[aria-multiselectable="true"]'),
         "SP2 C-006 a11y: the verse list is aria-multiselectable (a contiguous range is selectable)");
      vrows[0].click();
      ok(lmV.querySelector(".pm-verse.sel") && lmV.querySelector('.pm-verse[aria-selected="true"]'),
         "SP2 C-003: clicking a verse highlights the selected range (aria-selected)");
      ok(/Isaiah 61/.test(lmV.querySelector(".pm-verse-preview").textContent),
         "SP2 C-003: the gold reference preview reflects the selection");
      var vpsIn = lmV.querySelector('input[aria-label="Verses per slide"]');
      ok(!!vpsIn, "SP2 C-003: a verses-per-slide control is present");
      vpsIn.value = "2"; vpsIn.dispatchEvent(new Event("input", { bubbles: true }));
      var sicV = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      Array.prototype.filter.call(lmV.querySelectorAll(".pm-btn-primary"), function(b){return b.textContent==="Link";})[0].click();
      await sleep(20);
      var sicV2 = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      ok(sicV2.length > sicV && sicV2[sicV2.length-1].args.link.kind === "scripture" && sicV2[sicV2.length-1].args.link.verses_per_slide === 2,
         "SP2 C-003: Link commits scripture with the selected reference + verses_per_slide");
      // SP2 fix: editing the reference AFTER browsing invalidates the stale chapter — the freshly
      // typed reference wins on Link (was silently committing the browsed one).
      openLinkModal({ id: 14, kind: "scripture", title: "Opening Word" });
      await sleep(20);
      var lmS = document.querySelector(".pm-confirm.pm-link");
      var sIn = lmS.querySelector('input[aria-label="Scripture reference"]');
      sIn.value = "Isaiah 61:1";
      Array.prototype.filter.call(lmS.querySelectorAll("button"), function(b){return b.textContent==="Browse";})[0].click();
      await sleep(30);
      ok(!lmS.querySelector(".pm-verse-picker").hidden, "SP2 C-003: precondition — a chapter is browsed");
      sIn.value = "John 3:16";
      sIn.dispatchEvent(new Event("input", { bubbles: true }));
      ok(lmS.querySelector(".pm-verse-picker").hidden,
         "SP2 C-003: editing the reference invalidates the browsed chapter (picker hides)");
      var sicS = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      Array.prototype.filter.call(lmS.querySelectorAll(".pm-btn-primary"), function(b){return b.textContent==="Link";})[0].click();
      await sleep(20);
      var sicS2 = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      ok(sicS2.length > sicS && /John 3:16/.test(sicS2[sicS2.length-1].args.link.reference),
         "SP2 C-003: Link commits the freshly-typed reference, not the stale browsed one");
      // #8 host-rejection path: a rejected link keeps the modal OPEN and shows a role=alert error
      // (no silent close on a no-op). The one-shot __sicRejectOnce hook fails the next command.
      openLinkModal({id:14, kind:"scripture", title:"Closing Prayer"});
      var lmE = document.querySelector(".pm-confirm.pm-link");
      lmE.querySelector('input[aria-label="Scripture reference"]').value = "Nope 9:9";
      window.__sicRejectOnce = true;
      Array.prototype.filter.call(lmE.querySelectorAll(".pm-btn-primary"), function(b){return b.textContent==="Link";})[0].click();
      await sleep(30);
      ok(document.querySelector(".pm-confirm.pm-link") === lmE,
         "SP C-006: a host-rejected link keeps the modal open (no optimistic close on a silent no-op)");
      var alertEl = lmE.querySelector(".pm-link-err");
      ok(alertEl && !alertEl.hidden && alertEl.getAttribute("role") === "alert",
         "SP C-007: a rejected link surfaces an inline role=alert error");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); // close before the next modal
      await sleep(10);
      // C-004 link-Presentation flow: SELECT-then-confirm (handoff §4.2). Clicking a deck selects it
      // (aria-selected + "✓ Selected", NO commit); the footer "Link to item" → set_item_content{deck}.
      openLinkModal({id:12, kind:"slide_group", title:"Sermon Deck"});
      await sleep(40); // planDeckBody awaits the deck list
      var lm2 = document.querySelector(".pm-confirm.pm-link");
      var deckHit = lm2.querySelector(".pm-link-hit");
      ok(!!deckHit, "SP C-004: the link-Presentation modal lists the available decks");
      // Frame 610:390 — grid picker: grid layout + slide-count pills + New card + Grid/List toggle.
      ok(!!lm2.querySelector(".pm-deck-grid") && !!lm2.querySelector(".pm-deck-card .pm-deck-pill"),
         "SP2 C-004: the picker is a grid with per-deck slide-count pills");
      ok(!!lm2.querySelector(".pm-deck-new"), "SP2 C-004: a New-presentation card is offered");
      ok(!lm2.querySelector(".pm-deck-grid .pm-deck-new"),
         "SP2 C-006 a11y: the New card is outside the deck role=listbox (options only)");
      var listSeg = Array.prototype.filter.call(lm2.querySelectorAll(".pm-deck-seg-btn"), function(b){return b.dataset.view==="list";})[0];
      ok(!!listSeg, "SP2 C-004: a Grid/List toggle is present");
      listSeg.click();
      ok(lm2.querySelector(".pm-deck-grid").classList.contains("as-list"),
         "SP2 C-004: switching to List re-lays the picker");
      var linkFoot = lm2.querySelector(".pm-link-foot .pm-btn-primary");
      ok(!!linkFoot && linkFoot.disabled, "SP C-004: 'Link to item' is disabled until a deck is selected");
      var sicBeforeDeck = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      deckHit.click(); // SELECT (must not commit)
      ok(window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length === sicBeforeDeck,
         "SP C-004: selecting a deck does NOT commit (no premature set_item_content)");
      ok(deckHit.getAttribute("aria-selected") === "true" && deckHit.querySelector(".pm-link-sel") &&
         !deckHit.querySelector(".pm-link-sel").hidden && !linkFoot.disabled,
         "SP C-004: a selected deck shows '✓ Selected' + enables 'Link to item'");
      linkFoot.click(); // CONFIRM
      await sleep(20);
      var sic2 = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      ok(sic2.length > sicBeforeDeck && sic2[sic2.length-1].args.link && sic2[sic2.length-1].args.link.kind==="deck" &&
         typeof sic2[sic2.length-1].args.link.id === "number",
         "SP C-004: 'Link to item' sends set_item_content{link:{kind:deck,id}} (select-then-confirm)");
      // SP2 New-presentation card: creates a deck (deck_new) and links it immediately.
      openLinkModal({ id: 12, kind: "slide_group", title: "Sermon Deck" });
      await sleep(40);
      var lmN = document.querySelector(".pm-confirm.pm-link");
      var sicN = window.__calls.filter(function(c){return c.cmd==="set_item_content";}).length;
      lmN.querySelector(".pm-deck-new").click();
      await sleep(50); // deck_new → planLoadDecks → commit
      var sicN2 = window.__calls.filter(function(c){return c.cmd==="set_item_content";});
      ok(window.__calls.some(function(c){return c.cmd==="deck_new";}) && sicN2.length > sicN &&
         sicN2[sicN2.length-1].args.link && sicN2[sicN2.length-1].args.link.kind === "deck",
         "SP2 C-004: the New-presentation card creates + links a deck");
      // SP2 fix: double-activating the New card creates exactly ONE deck (re-entrancy/disabled guard).
      openLinkModal({ id: 12, kind: "slide_group", title: "Sermon Deck" });
      await sleep(40);
      var lmNN = document.querySelector(".pm-confirm.pm-link");
      var dnBefore = window.__calls.filter(function(c){return c.cmd==="deck_new";}).length;
      var nc = lmNN.querySelector(".pm-deck-new");
      nc.click(); nc.click(); // double-activate
      await sleep(50);
      ok(window.__calls.filter(function(c){return c.cmd==="deck_new";}).length === dnBefore + 1,
         "SP2 C-004: the New card guards double-activation (exactly one deck_new)");
      // F12b Change… on an item whose linked deck was DELETED: preselect nothing so "Link to item"
      // stays disabled (no phantom-id re-commit), not enabled with nothing visibly selected.
      openLinkModal({ id: 20, kind: "slide_group", title: "Ghost Deck", link: { kind: "deck", id: 999999 } });
      await sleep(40);
      var lm3 = document.querySelector(".pm-confirm.pm-link");
      ok(!lm3.querySelector('.pm-link-hit[aria-selected="true"]'),
         "SP C-004: Change… on a deleted deck preselects nothing (no phantom selection)");
      ok(lm3.querySelector(".pm-link-foot .pm-btn-primary").disabled,
         "SP C-004: 'Link to item' stays disabled when the preselected deck is missing");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); // close before the next check
      await sleep(10);
      // F11 empty state: an empty plan renders the centered CTA (not a bare line); "Add first item"
      // focuses the palette; the inspector is cleared.
      planRenderBuilder({ plan_name: "Empty", items: [] });
      var emptyEl = document.querySelector("#plan-b-list .plan-empty");
      ok(!!emptyEl && !!document.getElementById("plan-empty-add"),
         "SP C-002: an empty plan renders the centered CTA with an 'Add first item' action");
      ok(/coming soon/i.test(emptyEl.textContent),
         "SP C-002: the empty state shows honest 'coming soon' affordances (Template/Duplicate/Import)");
      document.getElementById("plan-empty-add").click();
      ok(document.activeElement === document.querySelector("#plan-palette-btns .plan-palette-btn"),
         "SP C-002 a11y: 'Add first item' focuses the Add-item palette");
      ok(/Select an item/i.test(el("plan-b-insp").textContent), "SP C-002: an empty plan clears the item inspector");
      // F5: a FAILED deck-list load leaves deck chips GENERIC (planDecks stays null), never a false
      // "⚠ missing". Reuse the one-shot deck_ rejection hook, reload, and assert the chip is generic.
      window.__pmRejectOnce = true;
      await planLoadDecks();
      ok(!/missing/i.test(planLinkChip({ kind: "deck", id: 987654 }).textContent),
         "SP C-001: a failed deck-list load renders a generic chip, not a false '⚠ missing'");
      await planLoadDecks(); // restore the resolved deck list
      planRenderBuilder(planView); // restore a populated run sheet
      // === Frame 608:124 — presentation-linked inspector: deck card + Open in editor ============
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="12"]').click(); // the deck-linked item
      var dinsp = el("plan-b-insp");
      var deckCard = dinsp.querySelector(".plan-deck-card");
      ok(deckCard && /Grace That Feeds/.test(deckCard.textContent) && /slide/.test(deckCard.textContent),
         "SP2 C-005: a presentation-linked item shows a deck card (name + slide count)");
      var openEd = Array.prototype.filter.call(dinsp.querySelectorAll("button"), function(b){return b.textContent==="Open in editor";})[0];
      ok(!!openEd, "SP2 C-005: the deck inspector offers Open in editor");
      openEd.click();
      await sleep(30);
      ok(el("surface-presentation").classList.contains("active"),
         "SP2 C-005: Open in editor navigates to the Presentation surface with the deck");
      document.querySelector('.nav-item[data-surface="plan"]').click(); // back to the builder
      await sleep(40);
      planRenderBuilder(planView); // restore a populated run sheet after the plan-surface re-activation
      // === Frame 611:820 — run-sheet reorder (keyboard Alt+↑/↓ + pointer drag) ==================
      // C-001 keyboard: Alt+↓ on a row reorders it down via move_item{to:i+1}.
      var r0 = document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"]');
      r0.focus();
      var mvBefore = window.__calls.filter(function(c){return c.cmd==="move_item";}).length;
      r0.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", altKey: true, bubbles: true }));
      await sleep(20);
      var mv = window.__calls.filter(function(c){return c.cmd==="move_item";});
      ok(mv.length > mvBefore && mv[mv.length-1].args.itemId === 11 && mv[mv.length-1].args.to === 1,
         "SP2 C-001: Alt+↓ reorders the row via move_item{to:i+1}");
      planRenderBuilder(planView); // restore
      // C-006 a11y: the drag handle is aria-hidden (Alt+↑/↓ is the keyboard-accessible reorder path).
      var handle = document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"] .plan-b-handle');
      ok(handle && handle.getAttribute("aria-hidden") === "true",
         "SP2 C-006: the drag handle is aria-hidden (Alt+↑/↓ is the accessible reorder path)");
      // C-002 pointer drag: pointerdown on the handle → move past threshold → drop line renders +
      // origin row lifts → pointerup reorders via move_item.
      var pr = document.querySelectorAll('#plan-b-list .plan-b-row');
      var startRect = pr[0].getBoundingClientRect(), thirdRect = pr[2].getBoundingClientRect();
      handle.dispatchEvent(new PointerEvent("pointerdown", { button: 0, clientY: startRect.top + 5, bubbles: true, pointerId: 9 }));
      window.dispatchEvent(new PointerEvent("pointermove", { clientY: thirdRect.top + thirdRect.height * 0.6, bubbles: true, pointerId: 9 }));
      ok(!!document.querySelector("#plan-b-list .plan-b-dropline"), "SP2 C-002: dragging shows the drop line");
      ok(document.querySelector('#plan-b-list .plan-b-row[data-item-id="11"]').classList.contains("dragging"),
         "SP2 C-002: the dragged origin row is marked (lifted)");
      var mvBefore2 = window.__calls.filter(function(c){return c.cmd==="move_item";}).length;
      window.dispatchEvent(new PointerEvent("pointerup", { clientY: thirdRect.top + thirdRect.height * 0.6, bubbles: true, pointerId: 9 }));
      await sleep(20);
      ok(window.__calls.filter(function(c){return c.cmd==="move_item";}).length > mvBefore2, "SP2 C-002: dropping reorders via move_item");
      ok(!document.querySelector("#plan-b-list .plan-b-dropline"), "SP2 C-002: the drop line is torn down after drop");
      // C-002 a cancelled drag never reorders + tears down.
      planRenderBuilder(planView);
      var pr2 = document.querySelectorAll('#plan-b-list .plan-b-row');
      var h2 = pr2[1].querySelector(".plan-b-handle");
      h2.dispatchEvent(new PointerEvent("pointerdown", { button: 0, clientY: pr2[1].getBoundingClientRect().top + 5, bubbles: true, pointerId: 10 }));
      window.dispatchEvent(new PointerEvent("pointermove", { clientY: pr2[3].getBoundingClientRect().top + 5, bubbles: true, pointerId: 10 }));
      var mvBefore3 = window.__calls.filter(function(c){return c.cmd==="move_item";}).length;
      window.dispatchEvent(new PointerEvent("pointercancel", { pointerId: 10, bubbles: true }));
      window.dispatchEvent(new PointerEvent("pointerup", { clientY: pr2[3].getBoundingClientRect().top + 5, bubbles: true, pointerId: 10 }));
      await sleep(10);
      ok(window.__calls.filter(function(c){return c.cmd==="move_item";}).length === mvBefore3, "SP2 C-002: a cancelled drag does not reorder");
      ok(!document.querySelector("#plan-b-list .plan-b-dropline"), "SP2 C-002: pointercancel tears down the drop line");
      // === 86ak846ft — run-sheet owner/duration + Plan Summary + loading ======================
      // A plan whose per-item owner + duration are known, so the RENDERED rows and the RENDERED
      // summary can be checked against each other rather than against a hand-copied constant.
      var sumView = { plan_name:"Sunday", items:[
        {id:21, kind:"song",         title:"Opening Song",    is_live:false, is_staged:false, owner:"Worship",      planned_secs:300},
        {id:22, kind:"announcement", title:"Welcome",         is_live:false, is_staged:false, owner:"Host",         planned_secs:120},
        {id:23, kind:"scripture",    title:"Romans 8:28-30",  is_live:false, is_staged:false, owner:"Scripture op", planned_secs:120,
         link:{kind:"scripture", reference:"Romans 8:28-30", translation:"WEB"}},
        {id:24, kind:"slide_group",  title:"Sermon",          is_live:false, is_staged:false, owner:"Pastor",       planned_secs:2100, link:{kind:"deck", id:2}},
        {id:25, kind:"media",        title:"Testimony Video", is_live:false, is_staged:false, owner:"Media",        planned_secs:192},
        {id:26, kind:"song",         title:"Closing Song",    is_live:false, is_staged:false,                       planned_secs:360}
      ] };
      planSelectedId = null; // nothing selected -> the right panel is the Plan Summary
      planRenderBuilder(sumView);
      // --- owner + planned duration on every row (handoff §3, FR-004) -------------------------
      var oRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]');
      ok(!!oRow.querySelector(".plan-b-owner") && /Worship/.test(oRow.querySelector(".plan-b-owner").textContent),
         "SP3 AC-1: a run-sheet row renders its owner");
      ok(!!oRow.querySelector(".plan-b-dur") && /5:00/.test(oRow.querySelector(".plan-b-dur").textContent),
         "SP3 AC-1: a run-sheet row renders its planned duration as m:ss");
      ok(/Owner:/.test(oRow.querySelector(".plan-b-owner").textContent),
         "SP3 AC-1 a11y: the owner carries a visually-hidden prefix, so a bare 'Worship' is not ambiguous to AT");
      // Positive control: the element is OMITTED when unassigned, never padded with a placeholder
      // dash that would read as data. Without this, "renders the owner" could pass on a stub.
      var noOwner = document.querySelector('#plan-b-list .plan-b-row[data-item-id="26"]');
      ok(!noOwner.querySelector(".plan-b-owner"), "SP3 AC-1 (control): an unassigned item renders NO owner element");
      ok(!!noOwner.querySelector(".plan-b-dur"), "SP3 AC-1 (control): that same row still renders its duration — the owner omission is per-field, not a dead branch");
      ok(oRow.querySelector(".plan-b-dur").getAttribute("aria-label") === "Planned 5 minutes",
         "SP3 AC-1 a11y (UI-A1 §211): the duration carries a SPOKEN label — a screen reader reading \"five colon zero zero\" is not useful");
      // --- AC-3: the summary must AGREE with the run sheet ------------------------------------
      // Design-QA §9 rejected these frames once for exactly this: "8 items · 1:12:00" displayed
      // over 6 rows summing 53:12. So compare the two RENDERED surfaces against each other. A
      // second, independent computation of the totals is precisely how they drift apart, and only
      // a cross-check between them catches it — asserting the summary against a literal would not.
      function sumRowValue(label) {
        var rows = document.querySelectorAll("#plan-b-insp .plan-sum-row");
        for (var i = 0; i < rows.length; i++) {
          if (rows[i].querySelector(".plan-sum-label").textContent === label)
            return rows[i].querySelector(".plan-sum-value").textContent.trim();
        }
        return null;
      }
      function clockToSecs(t) {
        // Tolerates surrounding text: the total renders "0:05:00 · partial", and a naive split
        // would make the last field NaN and silently zero the comparison.
        var m = String(t).match(/(\d+):(\d{2})(?::(\d{2}))?/);
        if (!m) return NaN;
        return m[3] !== undefined
          ? Number(m[1])*3600 + Number(m[2])*60 + Number(m[3])
          : Number(m[1])*60 + Number(m[2]);
      }
      var renderedRows = document.querySelectorAll("#plan-b-list .plan-b-row");
      function rowDurationSum() {
        var t = 0;
        Array.prototype.forEach.call(document.querySelectorAll("#plan-b-list .plan-b-dur"), function(d) {
          var txt = d.textContent.trim();
          if (txt === "\u2014") return; // an unset duration renders "—" and is excluded from the sum
          t += clockToSecs(txt);
        });
        return t;
      }
      var rowSum = rowDurationSum();
      ok(sumRowValue("Items") === String(renderedRows.length),
         "SP3 AC-3: Plan Summary 'Items' equals the rows the run sheet actually rendered (" + sumRowValue("Items") + " vs " + renderedRows.length + ")");
      ok(clockToSecs(sumRowValue("Total time")) === rowSum,
         "SP3 AC-3: Plan Summary total equals the sum of the durations shown on those rows (" + sumRowValue("Total time") + " vs " + rowSum + "s)");
      ok(sumRowValue("Total time") === "0:53:12",
         "SP3 AC-3: the total is formatted h:mm:ss, so a 53-minute plan cannot read as 53 minutes 12 seconds of m:ss");
      // Derived, not literal — same reasoning as the per-kind counts: a hardcoded "5 / 6" stops
      // describing the fixture the moment the fixture changes, and keeps passing anyway.
      var expAssigned = sumView.items.filter(function(i){ return !!i.owner; }).length;
      ok(sumRowValue("Assigned") === expAssigned + " / " + sumView.items.length,
         "SP3 AC-3: 'Assigned' counts the items that actually carry an owner (shown " + sumRowValue("Assigned") +
         ", fixture " + expAssigned + " / " + sumView.items.length + ")");
      // AC-3 states a SUMMATION invariant, so assert the sum — derived from the fixture, never
      // hardcoded. The literals this replaces held for ANY fixture, and because sumView contains
      // no timer and no section they never exercised the summation at all: the bug (two kinds
      // uncounted) and the check that should have caught it shared a blind spot. Deriving the
      // expectation also means an eighth ItemKind cannot slip past unnoticed.
      // No `section` entry: the panel has no Sections row, because every summary metric describes
      // the TRIGGERABLE run sheet and `items` excludes dividers (frame 608:875 — "6 items",
      // "Assigned 6 / 6", six rows over three dividers).
      var KIND_ROWS = { song:"Songs", scripture:"Scripture", slide_group:"Presentations", media:"Media",
                        announcement:"Announcements", timer:"Timers" };
      function assertKindCounts(view, label) {
        var expected = {}, unmapped = [];
        Object.keys(KIND_ROWS).forEach(function(k){ expected[k] = 0; });
        var triggerable = view.items.filter(function(it){ return it.kind !== "section"; });
        triggerable.forEach(function(it){
          if (KIND_ROWS[it.kind] === undefined) unmapped.push(it.kind);
          else expected[it.kind] += 1;
        });
        ok(unmapped.length === 0,
           "SP3 AC-3 (" + label + "): every item kind present has a summary row — an unrepresented kind is invisible in the counts (unmapped: " + (unmapped.join(",") || "none") + ")");
        var shownTotal = 0, wrong = [];
        Object.keys(KIND_ROWS).forEach(function(k){
          var shown = Number(sumRowValue(KIND_ROWS[k]));
          shownTotal += shown;
          if (shown !== expected[k]) wrong.push(KIND_ROWS[k] + " shows " + shown + ", fixture has " + expected[k]);
        });
        ok(wrong.length === 0,
           "SP3 AC-3 (" + label + "): each per-kind count matches the fixture (" + (wrong.join("; ") || "all match") + ")");
        ok(shownTotal === triggerable.length && String(shownTotal) === sumRowValue("Items"),
           "SP3 AC-3 (" + label + "): the per-kind counts SUM to Items, counting triggerable rows only (" + shownTotal +
           " vs Items=" + sumRowValue("Items") + ", fixture=" + triggerable.length + " of " + view.items.length + " rows)");
        ok(!sumRowValue("Sections"),
           "SP3 AC-3 (" + label + "): the panel has NO Sections row — one would make the per-kind rows stop summing to Items");
      }
      assertKindCounts(sumView, "sumView");
      // A fixture carrying ALL seven ItemKind variants, so the summation is exercised across every
      // row the panel draws rather than only the five the demo plan happens to contain.
      var allKindsView = { plan_name:"All", items:[
        {id:101, kind:"song",         title:"a", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:102, kind:"scripture",    title:"b", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:103, kind:"slide_group",  title:"c", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:104, kind:"media",        title:"d", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:105, kind:"announcement", title:"e", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:106, kind:"timer",        title:"f", is_live:false, is_staged:false, planned_secs:60, owner:"o"},
        {id:107, kind:"section",      title:"g", is_live:false, is_staged:false, planned_secs:60, owner:"o"}
      ] };
      planSelectedId = null;
      planRenderBuilder(allKindsView);
      assertKindCounts(allKindsView, "all seven kinds");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- Q2: the run-sheet header carries the planned total (frame 608:925) ------------------
      // Section 9 records this total as the fix for the MAJOR these frames were rejected for, so a
      // header that omits it reintroduces the defect. It must agree with the rows AND the summary:
      // two headline numbers that can drift apart is precisely what was rejected.
      planSelectedId = null;
      planRenderBuilder(sumView);
      // Q12: assert the RENDERED STRING, not its parse. clockToSecs reads "53:12" and "0:53:12"
      // identically, so comparing parsed seconds let a regression from planFmtTotal to fmtClock
      // pass every assertion here while the header and the summary visibly disagreed.
      function fmtHMS(secs) {
        var h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), q = secs % 60;
        return h + ":" + String(m).padStart(2, "0") + ":" + String(q).padStart(2, "0");
      }
      ok(sumRowValue("Total time") === fmtHMS(rowDurationSum()),
         "SP3 AC-22 (Quinn Q2): the Plan Summary total is the h:mm:ss STRING for the rendered rows' durations (got \"" +
         sumRowValue("Total time") + "\", expected \"" + fmtHMS(rowDurationSum()) + "\")");
      ok(el("plan-b-total").textContent === "planned " + fmtHMS(rowDurationSum()),
         "SP3 AC-22 (Quinn Q2): the run-sheet header renders exactly \"planned \" + that same string (got \"" +
         el("plan-b-total").textContent + "\")");
      ok(el("plan-b-total").textContent === "planned " + sumRowValue("Total time"),
         "SP3 AC-22 (Quinn Q2): header and summary are the same STRING — m:ss vs h:mm:ss drift between them cannot hide behind a matching parse");
      // The header must count the SAME thing the panel does. It read "9 items" beside a summary
      // saying "Items 6" — two headline numbers describing one run sheet and disagreeing.
      var secView = { plan_name:"Sec", items:[
        {id:601, kind:"section",      title:"GATHERING", is_live:false, is_staged:false},
        {id:602, kind:"song",         title:"Open",  is_live:false, is_staged:false, owner:"W", planned_secs:300},
        {id:603, kind:"section",      title:"WORD",  is_live:false, is_staged:false},
        {id:604, kind:"announcement", title:"Notes", is_live:false, is_staged:false, owner:"H", planned_secs:120}
      ] };
      planSelectedId = null;
      planRenderBuilder(secView);
      ok(el("plan-b-count").textContent === "2 items" && sumRowValue("Items") === "2",
         "SP3 AC-26: the run-sheet header counts triggerable rows, agreeing with the panel (header=\"" +
         el("plan-b-count").textContent + "\" panel=\"" + sumRowValue("Items") + "\")");
      ok(document.querySelectorAll("#plan-b-list .plan-b-row").length === 4,
         "SP3 AC-26 (control): all four rows including the dividers really are rendered — the count excludes them, the run sheet does not hide them");
      ok(sumRowValue("Assigned") === "2 / 2",
         "SP3 AC-26: Assigned excludes dividers too — a divider is not a staffable item, so a fully-staffed sectioned plan reads 2 / 2 and never 2 / 4");
      ok(!document.querySelector('#plan-b-list .plan-b-row[data-item-id="601"] .plan-b-dur'),
         "SP3 AC-26: an inert divider carries no duration on its row — its duration is excluded from the total, so a figure there would not be in the header");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- AC-4: the empty plan's counters, verbatim -------------------------------------------
      // AC-4 had no test at all, which is how the missing header total hid: with no total in the
      // header, the string AC-4 quotes could not be produced on any input.
      planSelectedId = null;
      planRenderBuilder({ plan_name:"E", items: [] });
      ok(el("plan-b-count").textContent === "0 items · 0:00",
         "SP3 AC-23 (AC-4): an empty plan's header counters read exactly \"0 items · 0:00\" (got \"" + el("plan-b-count").textContent + "\")");
      ok(sumRowValue("Items") === "0" && clockToSecs(sumRowValue("Total time")) === 0 && sumRowValue("Assigned") === "0 / 0",
         "SP3 AC-23 (AC-4): and the summary is zeroed too — not the previous plan's figures left standing");
      ok(!document.querySelector("#plan-b-list .plan-b-row") && !!document.querySelector("#plan-b-list .plan-empty"),
         "SP3 AC-23 (control): the empty state really rendered — the zeros describe an empty run sheet, not a failed render");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- host summary + `partial` (PR #13 contract, consumed not computed) -------------------
      // These drive the RENDERER with a synthetic host summary, so the consumption path is proven
      // against the agreed shape before the wire carries it — and so the swap cannot land wrong.
      // A host summary is only trusted when it DESCRIBES the items being rendered, so each of these
      // pairs a summary with items it actually adds up over. (The first draft of this block used
      // arbitrary figures and the new validator rejected every one of them — which is the guard
      // working.)
      function withSummary(items, sum) {
        planSelectedId = null;
        planRenderBuilder({ plan_name:"HS", items: items, summary: sum });
        return sumRowValue("Total time");
      }
      function hostSum(extra) {
        var o = { planned_total_secs:0, items:0, songs:0, scripture:0, presentations:0, media:0,
                  announcements:0, timers:0, sections:0, assigned:0, missing:0, unknown:0 };
        Object.keys(extra).forEach(function(k){ o[k] = extra[k]; });
        return o;
      }
      var SONG = function(id, secs) {
        var it = { id:id, kind:"song", title:"s"+id, is_live:false, is_staged:false };
        if (secs !== null) it.planned_secs = secs;
        return it;
      };
      ok(withSummary([SONG(301, 750), SONG(302, null)],
                     hostSum({ planned_total_secs:750, items:2, songs:2, partial:true, planned_items:1 })) === "0:12:30 · partial",
         "SP3 AC-24: a partial total with something planned reads as a real but incomplete sum plus the marker (got \"" + sumRowValue("Total time") + "\")");
      ok(withSummary([SONG(303, null), SONG(304, null)],
                     hostSum({ planned_total_secs:0, items:2, songs:2, partial:true, planned_items:0 })) === "— · partial",
         "SP3 AC-24: with planned_items 0 the figure is meaningless and reads \"— · partial\" — zero is a legitimate duration meaning instant (spec §4.1), so a 0 total does NOT imply nothing is set");
      ok(withSummary([SONG(305, 750)], hostSum({ planned_total_secs:750, items:1, songs:1, partial:false, planned_items:1 })) === "0:12:30",
         "SP3 AC-24 (control): a complete total carries no marker — 'partial' is not stuck on");
      ok(!/partial/i.test(document.querySelector("#plan-b-insp .plan-sum-total .plan-sum-value").getAttribute("aria-label")),
         "SP3 AC-24 (control): and the spoken form does not say partial either when it is complete");
      withSummary([SONG(306, null)], hostSum({ planned_total_secs:0, items:1, songs:1, partial:true, planned_items:0 }));
      ok(/partial/i.test(document.querySelector("#plan-b-insp .plan-sum-total .plan-sum-value").getAttribute("aria-label")) &&
         !!document.querySelector("#plan-b-insp .plan-sum-total.is-partial"),
         "SP3 AC-24 a11y: 'partial' is spoken and marked, and the word is in the TEXT so it is not colour-only");
      // The "inert sections never set partial" rule (spec §4.2) is the HOST's to enforce, and this
      // client cannot diverge from it because it never computes the flag. A plan that is nothing
      // but dividers, reported partial:false, must render no marker — the client must not
      // second-guess it into one.
      ok(withSummary([{id:201, kind:"section", title:"Gathering", is_live:false, is_staged:false},
                      {id:202, kind:"section", title:"The Word",  is_live:false, is_staged:false}],
                     hostSum({ planned_total_secs:0, items:0, sections:2, partial:false, planned_items:0 })) === "0:00:00" &&
         !document.querySelector("#plan-b-insp .plan-sum-total.is-partial"),
         "SP3 AC-24: a plan of inert section dividers is NOT marked partial — a warning that is always on is one coordinators learn to ignore");
      // --- Q13: the pass-through crosses a trust boundary and must validate ---------------------
      // None of these needs an attacker: a host one release ahead or behind produces them. Each
      // must fall back to the local computation, which is derived from the rendered items.
      var q13Items = [SONG(311, 300), SONG(312, 300)]; // local total 600 -> "0:10:00"
      // Every malformed fixture carries songs:7, which the local computation (two songs) can never
      // produce. Asserting the LOCAL value is what distinguishes a fallback from a host object that
      // happens to agree — without it, two of these could not tell the two apart and the checks
      // they were meant to pin survived mutation.
      function malformed(sum, label) {
        planSelectedId = null;
        planRenderBuilder({ plan_name:"M", items:q13Items, summary:sum });
        ok(sumRowValue("Total time") === "0:10:00" && sumRowValue("Items") === "2" &&
           sumRowValue("Songs") === "2" && sumRowValue("Assigned") === "0 / 2",
           "SP3 AC-25 (Q13): " + label + " falls back to the local computation (got total \"" +
           sumRowValue("Total time") + "\", Items \"" + sumRowValue("Items") + "\", Songs \"" +
           sumRowValue("Songs") + "\", Assigned \"" + sumRowValue("Assigned") + "\")");
      }
      malformed({}, "an empty summary object");
      malformed(hostSum({ planned_total_secs:1e308, items:2, songs:7 }), "a non-finite-scale total (1e308 rendered 2.77e+304:58:56)");
      malformed(hostSum({ planned_total_secs:-1200, items:2, songs:7 }), "a negative total (rendered -1:-20:00)");
      malformed(hostSum({ planned_total_secs:600, items:2, songs:7 }), "per-kind counts that do not add up to items");
      malformed(hostSum({ planned_total_secs:99999, items:2, songs:7 }), "a total disagreeing with the rows beneath it (the §9 MAJOR)");
      // Each of the remaining fixtures is otherwise WELL-FORMED, so exactly one check rejects it.
      // Overlapping checks would mask a mutation of the one the case is meant to pin — which is
      // how three of these survived the first round.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:"1" }), "a count that is a string rather than a number");
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:1, partial:"yes" }), "a non-boolean partial");
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, partial:true }), "partial:true with no planned_items to disambiguate it");
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, assigned:9 }), "more assigned items than items");
      // Backend's own incoherence, mirrored: a duration set ON a section reached planned_items
      // while the section was absent from items, so planned_items could exceed items and this
      // panel would have rendered "7 of 6". A subset cannot exceed its whole.
      malformed(hostSum({ planned_total_secs:600, items:2, songs:2, partial:true, planned_items:9 }), "planned_items exceeding items (\"7 of 6\")");
      // Isolates PLAN_MAX_TOTAL_SECS: eight items at the per-item cap sum to 691200s, so the total
      // AGREES with the rows and every other check passes — only the week-long bound rejects it.
      // A corrupt plan claiming eight days of runtime is the real shape of this.
      var hugeItems = [];
      for (var hz = 0; hz < 8; hz++) hugeItems.push(SONG(400 + hz, 86400));
      planSelectedId = null;
      planRenderBuilder({ plan_name:"HUGE", items:hugeItems,
                          summary: hostSum({ planned_total_secs:691200, items:8, songs:8, assigned:5 }) });
      ok(sumRowValue("Assigned") === "0 / 8",
         "SP3 AC-25 (Q13): a total beyond the week-long bound is rejected even though it agrees with the rows and every other field is sound — only the bound can catch this one (Assigned=" +
         sumRowValue("Assigned") + ")");
      // Control: a WELL-FORMED summary is still used. Without this the guard could pass by
      // rejecting everything, which would silently disable PR #13 the day it merges.
      planSelectedId = null;
      planRenderBuilder({ plan_name:"OK", items:q13Items,
                          summary: hostSum({ planned_total_secs:600, items:2, songs:2, assigned:0, partial:true, planned_items:2 }) });
      ok(sumRowValue("Total time") === "0:10:00 · partial",
         "SP3 AC-25 (control): a sound host summary IS used — the guard rejects malformed input, not every input");
      // ...and it is genuinely the HOST's object, not the local fallback coincidentally agreeing:
      // the local computation cannot produce a partial marker at all.
      ok(!!document.querySelector("#plan-b-insp .plan-sum-total.is-partial"),
         "SP3 AC-25 (control): and the marker proves the host object was used — the local fallback carries no partial flag");
      // Sections-not-items is UNSETTLED (frame 608:875 counts 6 items over 3 dividers), so the
      // guard must accept both readings rather than hard-code a decision nobody has made.
      planSelectedId = null;
      planRenderBuilder({ plan_name:"SX", items:[SONG(321, 600), {id:322, kind:"section", title:"D", is_live:false, is_staged:false}],
                          summary: hostSum({ planned_total_secs:600, items:1, songs:1, sections:1 }) });
      ok(sumRowValue("Items") === "1",
         "SP3 AC-25: a host summary excluding inert sections from `items` is accepted — that is the settled rule, and the per-kind rows sum to it");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- missing-content count: three-state link status -------------------------------------
      // Local deck resolution stays authoritative (the host has no deck store and cannot resolve a
      // deck_id), and an "unknown" status must never be counted as either missing or resolved-by-
      // fiat. Deck 2 resolves locally; deck 99 does not.
      var missView = { plan_name:"S", items:[
        {id:31, kind:"slide_group", title:"Gone",       is_live:false, is_staged:false, link:{kind:"deck", id:99}},
        {id:32, kind:"slide_group", title:"Present",    is_live:false, is_staged:false, link:{kind:"deck", id:2}},
        {id:33, kind:"media",       title:"Host: gone", is_live:false, is_staged:false, link:{kind:"media", id:7, status:"missing"}},
        {id:34, kind:"media",       title:"Unknown",    is_live:false, is_staged:false, link:{kind:"media", id:8, status:"unknown"}}
      ] };
      planSelectedId = null;
      planRenderBuilder(missView);
      ok(sumRowValue("Missing content") === "⚠ 2",
         "SP3 AC-4: Missing content counts the locally-unresolvable deck AND the host-flagged media (got " + sumRowValue("Missing content") + ")");
      ok(document.querySelectorAll("#plan-b-insp .plan-sum-warn").length === 1,
         "SP3 AC-4: a non-zero missing count is marked, and the ⚠ is in the TEXT so it is not colour-only");
      // Control for the "unknown" branch specifically. Item 34 is a NON-deck link carrying
      // status:"unknown" — it reaches the `status === "unknown"` return, which a deck link never
      // does (decks short-circuit into local resolution first). "Could not check" must not be
      // counted as broken; if it were, the count above would read 3.
      ok(planLinkState(missView.items[3].link) === "unknown",
         "SP3 AC-4 (control): a non-deck link with status 'unknown' resolves to unknown, not missing and not resolved-by-fiat");
      // Control for the OTHER unknown branch: a deck_list that never loaded. planDecks === null
      // must read unknown, so one transient deck_list failure cannot flag every deck-linked item
      // in the plan as broken. This is the branch a loaded fixture otherwise never exercises.
      var decksSaved = planDecks;
      planDecks = null;
      planRenderBuilder(missView);
      ok(planLinkState(missView.items[0].link) === "unknown" && sumRowValue("Missing content") === "⚠ 1",
         "SP3 AC-4 (control): with the deck list unloaded, deck links read unknown — only the host-flagged media counts missing (got " + sumRowValue("Missing content") + ")");
      planDecks = decksSaved;
      planRenderBuilder(missView);
      ok(sumRowValue("Missing content") === "⚠ 2",
         "SP3 AC-4 (control): restoring the deck list restores the real count — the unknown path is a state, not a latch");
      // Regression, found by rendering the real dist in WebKit: a host that answers deck_list with
      // null must read as UNKNOWN, not as a loaded-and-empty library. `(r && r.decks) || []` made
      // a null response mean "the library is empty", so every deck-linked item was flagged
      // "⚠ presentation missing" and counted here — the false alarm the catch branch exists to
      // prevent, reached through the success path instead.
      window.__deckListNullOnce = true;
      await planLoadDecks();
      ok(planDecks === null, "SP3 AC-4 (regression): a null deck_list response reads UNKNOWN, not an empty library");
      planRenderBuilder(missView);
      ok(sumRowValue("Missing content") === "⚠ 1",
         "SP3 AC-4 (regression): with the deck library unreadable, deck links are NOT counted missing — only the host-flagged media is (got " + sumRowValue("Missing content") + ")");
      await planLoadDecks();
      ok(Array.isArray(planDecks) && planDecks.length > 0,
         "SP3 AC-4 (control): a well-formed deck_list still loads the library — the guard rejects malformed responses, not every response");
      planRenderBuilder(missView);
      planRenderBuilder(sumView);
      ok(sumRowValue("Missing content") === "0" && !document.querySelector("#plan-b-insp .plan-sum-warn"),
         "SP3 AC-4 (control): a plan with nothing missing reads 0 and is NOT marked — the marker is not stuck on");
      // --- the panel swaps with selection, and the heading says which panel this is ------------
      ok(el("plan-insp-h").textContent === "PLAN SUMMARY", "SP3 AC-2: with nothing selected the right panel is headed PLAN SUMMARY");
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]').click();
      ok(el("plan-insp-h").textContent === "ITEM" && !document.querySelector("#plan-b-insp .plan-sum-card"),
         "SP3 AC-2: selecting an item swaps the summary for the item inspector, and the heading follows");
      planSelectedId = null;
      planRenderBuilder(sumView);
      ok(!!document.querySelector("#plan-b-insp .plan-sum-card"), "SP3 AC-2: clearing the selection brings the summary back");
      // --- the two write actions are present, honest, and slotted for 86ak8467m ---------------
      ok(!!el("plan-sum-publish") && el("plan-sum-publish").disabled,
         "SP3 AC-5: 'Publish to team' is PRESENT and disabled — not hidden (an operator must be able to find it) and not wired to a no-op");
      ok(!!el("plan-sum-precheck") && el("plan-sum-precheck").disabled, "SP3 AC-5: 'Run pre-service check' is present and disabled");
      ok(el("plan-sum-publish").getAttribute("aria-describedby") === "plan-sum-later" && !!el("plan-sum-later"),
         "SP3 AC-5 a11y: the disabled actions point at a stated reason, so AT hears why they are unavailable");
      ok(!!el("plan-sum-live") && !el("plan-sum-live").disabled,
         "SP3 AC-5 (control): 'Open in Live' in the SAME panel is enabled — 'disabled' means not-yet-built, not a dead panel");
      // Open in Live is a pure surface switch: it must never send a live-control command.
      // Assert what is FORBIDDEN, not a raw call count: a 1 Hz `view` poll runs throughout the
      // gate, so counting every call makes this pass or fail on timing rather than on behaviour.
      var liveCallsBefore = window.__calls.length;
      el("plan-sum-live").click();
      await sleep(20);
      var during = window.__calls.slice(liveCallsBefore).map(function(c){ return c.cmd; });
      // Name what is FORBIDDEN rather than allowlisting reads: the console polls view /
      // detection_health / link_status continuously, so a new poll must not break this, while any
      // command that commits to Live or edits the plan must.
      var FORBIDDEN = ["go_live","deck_go_live","deck_go_live_delta","blackout","clear","next","previous",
                       "select","select_slide","stage_scripture","present_plan_deck_slide",
                       "add_item","move_item","remove_item","rename_item","set_item_content","plan_undo","plan_redo"];
      var offended = during.filter(function(c){ return FORBIDDEN.indexOf(c) >= 0; });
      ok(offended.length === 0,
         "SP3 AC-6 invariant: 'Open in Live' only switches surface — it commits nothing to Live and edits no plan item (saw: " + (offended.join(",") || "none") + ")");
      // --- unset durations: OMITTED, per 86ak846ft AC-1 ("without a gap or placeholder text") ---
      // UI-A1 FR-202 asks for a "—" placeholder instead. The two acceptance criteria genuinely
      // conflict and DECISION 86ak84cth owns it; this pins the CURRENT contract so a silent switch
      // to either behaviour fails here rather than surprising whichever spec wins.
      var partialView = { plan_name:"P", items:[
        {id:41, kind:"song",        title:"Has one",  is_live:false, is_staged:false, owner:"W", planned_secs:300},
        {id:42, kind:"song",        title:"Has none", is_live:false, is_staged:false, owner:"W"},
        {id:43, kind:"announcement",title:"Zero",     is_live:false, is_staged:false, owner:"H", planned_secs:0}
      ] };
      planSelectedId = null;
      planRenderBuilder(partialView);
      ok(!document.querySelector('#plan-b-list .plan-b-row[data-item-id="42"] .plan-b-dur'),
         "SP3 AC-8: an item with no planned duration renders NO duration element (86ak846ft AC-1; the UI-A1 em-dash is DECISION 86ak84cth)");
      // An explicit 0 is SET, not unset — guards the predicate against a truthiness bug.
      var zeroRow = document.querySelector('#plan-b-list .plan-b-row[data-item-id="43"] .plan-b-dur');
      ok(!!zeroRow && zeroRow.textContent.trim() === "0:00",
         "SP3 AC-8 (control): planned_secs 0 is a SET duration and renders 0:00 — the omission is 'absent', not 'falsy'");
      ok(clockToSecs(sumRowValue("Total time")) === rowDurationSum(),
         "SP3 AC-8: the total still equals the sum of the durations that ARE set");
      // KNOWN GAP pinned deliberately: the total excludes unplanned items with no marker. `partial`
      // must be computed in ONE place, the same place as the sum (PLAN-SECTIONS-DURATIONS §128),
      // and that place is the host's PlanSummaryView — which does not carry it yet (raised on PR
      // #13). Computing it here would make THIS surface look right while the mobile client and the
      // Live Console panel stayed wrong. This asserts the gap is not silently "fixed" locally.
      ok(!/partial/i.test(sumRowValue("Total time")),
         "SP3 AC-8 (pinned gap): the total carries no locally-computed 'partial' — that flag belongs on the wire beside the sum, not in this one client");
      // Hostile numerics must not corrupt the total (Sana S3): out of range is treated as UNSET.
      planRenderBuilder({ plan_name:"X", items:[
        {id:44, kind:"song", title:"Neg",  is_live:false, is_staged:false, planned_secs:-1200},
        {id:45, kind:"song", title:"Huge", is_live:false, is_staged:false, planned_secs:1e308},
        {id:46, kind:"song", title:"Real", is_live:false, is_staged:false, planned_secs:600}
      ] });
      ok(sumRowValue("Total time") === "0:10:00",
         "SP3 AC-8 (Sana S3): a negative or non-finite planned_secs is treated as UNSET, so it cannot render -1:-15:00 or Infinity:NaN:NaN (got " + sumRowValue("Total time") + ")");
      ok(document.querySelectorAll("#plan-b-list .plan-b-dur").length === 1,
         "SP3 AC-8 (Sana S3 control): only the one in-range duration renders — the guard rejects bad values, not every value");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- unknown is counted separately from missing, and never merged into it ----------------
      // The host structurally cannot resolve decks or media, so it returns "unknown" for both.
      // Collapsing that into "resolved" is the failure the three-state field exists to prevent.
      var unkView = { plan_name:"U", items:[
        {id:51, kind:"media",       title:"Unresolvable media", is_live:false, is_staged:false, link:{kind:"media", id:9, status:"unknown"}},
        {id:52, kind:"slide_group", title:"Gone deck",          is_live:false, is_staged:false, link:{kind:"deck", id:99}}
      ] };
      planRenderBuilder(unkView);
      ok(planSummaryOf(unkView).unknown === 1 && planSummaryOf(unkView).missing === 1,
         "SP3 AC-9: unknown and missing are counted SEPARATELY — 'the host could not check' is not 'it is fine'");
      ok(sumRowValue("Missing content") === "⚠ 1",
         "SP3 AC-9 (control): the unknown item is NOT folded into the missing count");
      // The summary object mirrors OperatorStateView.summary field-for-field, so adopting the
      // host's summary is a swap of planSummaryOf's body and nothing else.
      var shape = planSummaryOf(sumView);
      var WIRE = ["items","songs","scripture","presentations","media","announcements","timers","sections","assigned","missing","unknown","planned_total_secs"];
      var absent = WIRE.filter(function(k){ return !(k in shape); });
      ok(absent.length === 0,
         "SP3 AC-10: the local summary carries every OperatorStateView.summary field, so the backend swap is one function (missing: " + (absent.join(",") || "none") + ")");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- QA-review remediation (Quinn, PR #12): these guard fixes whose probes were transient ---
      showSurface("plan");
      await sleep(40);
      // P1: the per-kind rows must ALWAYS sum to Items, including kinds the demo frame has none of.
      var kindsView = { plan_name:"K", items:[
        {id:61, kind:"song",    title:"S", is_live:false, is_staged:false, planned_secs:60},
        {id:62, kind:"timer",   title:"T", is_live:false, is_staged:false, planned_secs:60},
        {id:63, kind:"section", title:"Sec", is_live:false, is_staged:false, planned_secs:60},
        {id:64, kind:"media",   title:"M", is_live:false, is_staged:false, planned_secs:60}
      ] };
      planSelectedId = null;
      planRenderBuilder(kindsView);
      var kindSum = ["Songs","Scripture","Presentations","Media","Announcements","Timers"]
        .reduce(function(a,k){ return a + Number(sumRowValue(k)); }, 0);
      ok(String(kindSum) === sumRowValue("Items"),
         "SP3 AC-11 (Quinn P1): the per-kind rows sum to Items for every kind, so a reader's arithmetic adds up (kinds=" + kindSum + " vs Items=" + sumRowValue("Items") + ")");
      ok(document.querySelectorAll("#plan-b-list .plan-b-row").length === 4,
         "SP3 AC-11 (control): the run sheet really did render all four kinds");
      // P5c: a long owner must not crush the title to nothing (WKWebView trap #1, owner side).
      var longView = { plan_name:"L", items:[{id:71, kind:"song", title:"A reasonably long item title here",
        is_live:false, is_staged:false, owner:"Wednesday Evening Worship Team Coordinator", planned_secs:300}] };
      planRenderBuilder(longView);
      var lRow = document.querySelector('#plan-b-list .plan-b-row');
      var lTitle = lRow.querySelector(".plan-b-title");
      // The bug was titleW=0 — total collapse. The floor on .plan-b-main stops that. In a SQUEEZED
      // column the title is still short, because the ↑↓ tools (66px) and the type badge (33px) are
      // fixed and the owner has already yielded to ~7px; that is geometry, not a starvation bug.
      // What must hold is that the title never disappears and the owner yields FIRST.
      ok(lTitle.getBoundingClientRect().width > 20,
         "SP3 AC-12 (Quinn P5c): a very long owner never crushes the title out of existence (titleW=" + Math.round(lTitle.getBoundingClientRect().width) + ")");
      ok(lRow.querySelector(".plan-b-owner").getBoundingClientRect().width < lTitle.getBoundingClientRect().width,
         "SP3 AC-12: under pressure the OWNER yields before the title — priority is title > duration > owner");
      ok(lRow.scrollWidth <= lRow.clientWidth + 2,
         "SP3 AC-12 (Quinn P5): a very long owner does not overflow its row (scrollW=" + lRow.scrollWidth + " clientW=" + lRow.clientWidth + ")");
      ok(lRow.querySelector(".plan-b-dur").getBoundingClientRect().width > 20,
         "SP3 AC-12 (control): the duration is never the thing that gets truncated — a clipped time is worse than a clipped name");
      // P9: a 65-minute row must not read "65:00".
      planRenderBuilder({ plan_name:"H", items:[{id:81, kind:"song", title:"Long", is_live:false, is_staged:false, planned_secs:3900}] });
      var hDur = document.querySelector("#plan-b-list .plan-b-dur").textContent.trim();
      ok(hDur === "1:05:00",
         "SP3 AC-13 (Quinn P9): a 65-minute row reads h:mm:ss like the total, not '65:00' (got " + hDur + ")");
      ok(document.querySelector("#plan-b-list .plan-b-dur").getAttribute("aria-label") === "Planned 1 hour 5 minutes",
         "SP3 AC-13: and its spoken form is unambiguous");
      // P8: the per-type accent bar (handoff §3), decorative — the badge carries the type as text.
      planSelectedId = null;
      planRenderBuilder(sumView);
      var acc = document.querySelector('#plan-b-list .plan-b-row[data-item-id="23"] .plan-b-accent');
      ok(!!acc && acc.classList.contains("kind-scripture"),
         "SP3 AC-14 (Quinn P8): run-sheet rows carry a per-type accent bar");
      ok(acc.getAttribute("aria-hidden") === "true",
         "SP3 AC-14 a11y: the accent bar is decorative — the type badge carries the same information as TEXT, so colour is never the only cue");
      ok(document.querySelectorAll("#plan-b-list .plan-b-accent").length === document.querySelectorAll("#plan-b-list .plan-b-row").length,
         "SP3 AC-14 (control): every row gets one, not just the typed ones");
      // P7: the landmark must follow the heading rather than claim "Item inspector" throughout.
      var aside = document.getElementById("plan-insp-panel");
      ok(aside.getAttribute("aria-labelledby") === "plan-insp-h" && !aside.getAttribute("aria-label"),
         "SP3 AC-15 (Quinn P7): the right panel is labelled BY its heading, so it never announces the wrong panel");
      ok(el("plan-insp-h").textContent === "PLAN SUMMARY",
         "SP3 AC-15 (control): and that heading currently reads PLAN SUMMARY");
      // P6: swapping the panel must not strand focus on <body>.
      el("plan-sum-live").focus();
      ok(document.activeElement === el("plan-sum-live"), "SP3 AC-16 (setup): focus is inside the Plan Summary panel");
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]').click();
      ok(document.activeElement !== document.body,
         "SP3 AC-16 (Quinn P6): swapping the summary for the inspector does not strand focus on <body> (activeElement=" + document.activeElement.tagName + ")");
      // Control: a swap with focus OUTSIDE the panel must NOT steal it — otherwise the fix would
      // yank focus away from the run sheet on every background re-render.
      planSelectedId = null;
      planRenderBuilder(sumView);
      var outside = document.querySelector('#plan-b-list .plan-b-row[data-item-id="22"]');
      outside.focus();
      planRenderBuilder(sumView);
      // Asserts what planKeepPanelFocus OWNS: it must not PULL focus into the panel when focus was
      // outside it. (Where focus lands after a run-sheet rebuild is separate, pre-existing
      // behaviour — planFocusAfterRender is deliberately null on a background re-render.)
      ok(!el("plan-b-insp").contains(document.activeElement),
         "SP3 AC-16 (control): a rebuild with focus OUTSIDE the panel does not steal focus into it (activeElement=" + document.activeElement.tagName + ")");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- Sana S1: local deck truth outranks a host-stamped status ---------------------------
      // The host has no deck store, so its verdict on a deck is never ground truth. A deck the
      // operator can SEE is not missing because the host said so.
      ok(planLinkState({kind:"deck", id:2, status:"missing"}) === "resolved",
         "SP3 AC-17 (Sana S1): a deck present in the local library resolves even when the host stamped status:missing");
      ok(planLinkState({kind:"deck", id:99, status:"missing"}) === "missing",
         "SP3 AC-17 (control): a deck absent locally is still missing — local truth decides BOTH ways, it does not merely ignore the host");
      var savedDecks = planDecks;
      planDecks = null;
      ok(planLinkState({kind:"deck", id:2, status:"missing"}) === "missing" && planLinkState({kind:"deck", id:2}) === "unknown",
         "SP3 AC-17: with no local library there is no ground truth, so the host's status is the fallback and silence reads unknown");
      planDecks = savedDecks;
      // --- Sana S2: one verdict per link, shared by the chip and the summary -------------------
      var s2View = { plan_name:"S2", items:[
        {id:91, kind:"media", title:"Host says gone", is_live:false, is_staged:false, link:{kind:"media", id:3, status:"missing"}},
        {id:92, kind:"media", title:"Fine",           is_live:false, is_staged:false, link:{kind:"media", id:4}}
      ] };
      planSelectedId = null;
      planRenderBuilder(s2View);
      // THE assertion behind planLinkState's stated purpose: what is DRAWN missing and what is
      // COUNTED missing must be the same set. Previously the chip ignored `status` while the
      // summary honoured it, so the panel read "⚠ 1" with no visibly-missing row.
      ok(document.querySelectorAll("#plan-b-list .link-missing").length === Number(String(sumRowValue("Missing content")).replace(/\D/g, "")),
         "SP3 AC-18 (Sana S2): the rows DRAWN missing equal the summary's missing count — one verdict, not two (drawn=" +
         document.querySelectorAll("#plan-b-list .link-missing").length + " counted=" + sumRowValue("Missing content") + ")");
      ok(/media missing/i.test(document.querySelector('#plan-b-list .plan-b-row[data-item-id="91"] .link-chip').textContent),
         "SP3 AC-18: a host-flagged missing medium is drawn missing, not as a healthy chip");
      ok(!document.querySelector('#plan-b-list .plan-b-row[data-item-id="92"] .link-chip').classList.contains("link-missing"),
         "SP3 AC-18 (control): a medium with no status is NOT drawn missing — the treatment is not stuck on");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- Cody BLOCKER 1: the way back to the Plan Summary must exist as a GESTURE -----------
      // AC-2 above proved nothing about reachability: it restores the summary by assigning
      // planSelectedId = null, which no operator can do. Selecting a row was a one-way door, and
      // it took Publish / Run pre-service check (the 86ak8467m seam) with it.
      planSelectedId = null;
      planRenderBuilder(sumView);
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]').click();
      ok(el("plan-insp-h").textContent === "ITEM", "SP3 AC-19 (setup): clicking a row opens the item inspector");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(40);
      ok(el("plan-insp-h").textContent === "PLAN SUMMARY" && !!el("plan-sum-publish"),
         "SP3 AC-19 (Cody BLOCKER 1): Escape returns to the Plan Summary, so Publish is reachable again after a row has been selected");
      document.querySelector('#plan-b-list .plan-b-row[data-item-id="21"]').click();
      ok(el("plan-insp-h").textContent === "ITEM", "SP3 AC-19 (setup): re-selected, for the pointer path");
      el("plan-b-list").click(); // the empty area below the rows — target is the list itself
      await sleep(40);
      ok(el("plan-insp-h").textContent === "PLAN SUMMARY",
         "SP3 AC-19 (Cody BLOCKER 1): clicking the empty run-sheet area also deselects");
      // Control: Escape with nothing selected must not fire a pointless refetch.
      var cardBefore = document.querySelector("#plan-b-insp .plan-sum-card");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await sleep(20);
      ok(document.querySelector("#plan-b-insp .plan-sum-card") === cardBefore,
         "SP3 AC-19 (control): Escape with nothing selected does not rebuild the panel — it is a genuine no-op, not a rebuild on every keypress");
      // --- Cody HIGH 4: the summary must not report a plan that is loading or failed to open ---
      planSelectedId = null;
      planRenderBuilder(sumView);
      ok(!!document.querySelector("#plan-b-insp .plan-sum-card"), "SP3 AC-20 (setup): the summary is showing real figures");
      planRenderLoading();
      ok(!document.querySelector("#plan-b-insp .plan-sum-card") && !!document.querySelector("#plan-b-insp .plan-sum-blank"),
         "SP3 AC-20 (Cody HIGH 4): loading clears the summary — it must not report the previous plan's figures beside a skeleton run sheet");
      planRenderLoading();
      planRenderLoadFailed(new Error("x"));
      ok(!document.querySelector("#plan-b-insp .plan-sum-card") && /unavailable/i.test(el("plan-b-insp").textContent),
         "SP3 AC-20 (Cody HIGH 4): after a failed open the panel says figures are unavailable, not 'Items 6 · 0:53:12' next to 'Couldn't open the plan'");
      // --- focus retention, exercised properly --------------------------------------------------
      // AC-16 could not reach planKeepPanelFocus: clicking a row focuses the ROW, so focus was
      // never inside the panel at rebuild time. This drives the actual path — a background
      // re-render under a focused panel control.
      planSelectedId = null;
      planRenderBuilder(sumView);
      el("plan-sum-live").focus();
      planRenderBuilder(sumView);
      ok(el("plan-insp-panel").contains(document.activeElement),
         "SP3 AC-16b: a rebuild under a focused panel control keeps focus in the panel rather than dropping it to <body> (activeElement=" + document.activeElement.tagName + ")");
      planSelectedId = null;
      planRenderBuilder(sumView);
      // --- the Plan Summary must stay REACHABLE as it grows (WKWebView trap #2 family) ---------
      // Adding the Timers/Sections rows pushed the panel's last element below the emergency
      // footer. That is fine only because #surface-plan scrolls; if a future row made the panel
      // taller than the scroll container allows, the bottom of the summary would be permanently
      // obscured. Note the weaker check this replaces: the grid's own scrollHeight === clientHeight
      // stayed equal the whole time the content was overflowing, so it proved nothing.
      planSelectedId = null;
      planRenderBuilder(sumView);
      var surf = el("surface-plan");
      var hint = document.querySelector("#plan-b-insp .plan-sum-hint");
      ok(!!hint, "SP3 AC-21 (setup): the summary's last element exists");
      // Self-referential to the SCROLL CONTAINER, not to the footer: the footer sits in different
      // places under the gate's layout than in the real window, so a footer-relative assertion
      // would measure the harness rather than the product.
      // FORCE the overflow. At the gate's viewport the panel happens to fit, so the assertion
      // would be trivially true and guard nothing (it survived an overflow-y:hidden mutation until
      // this was added). Squeezing the surface reproduces the real-window condition, where the
      // panel's last element sits below the fold.
      var savedH = surf.style.height;
      surf.style.height = "200px";
      ok(hint.getBoundingClientRect().bottom > Math.round(surf.getBoundingClientRect().top + surf.clientHeight),
         "SP3 AC-21 (premise): with the surface squeezed the summary really does overflow — otherwise the reachability check below proves nothing");
      // The container must be USER-scrollable, not merely script-scrollable: overflow-y:hidden
      // still honours a programmatic scrollTop, so scrolling in a test and finding the element
      // proves nothing about whether an operator could ever reach it.
      var ovf = getComputedStyle(surf).overflowY;
      ok(ovf === "auto" || ovf === "scroll",
         "SP3 AC-21: the plan surface is user-scrollable (overflow-y=" + ovf + "), so overflowing panel content is reachable by a person and not just by script");
      surf.scrollTop = surf.scrollHeight;
      var surfBottom = Math.round(surf.getBoundingClientRect().top + surf.clientHeight);
      ok(Math.round(hint.getBoundingClientRect().bottom) <= surfBottom + 1,
         "SP3 AC-21: the bottom of the Plan Summary can be scrolled into the surface's visible area — a taller panel must never become unreachable (hint=" +
         Math.round(hint.getBoundingClientRect().bottom) + " surfaceBottom=" + surfBottom + ")");
      surf.scrollTop = 0;
      surf.style.height = savedH;
      // --- loading (frame 611:350) ------------------------------------------------------------
      planRenderLoading();
      ok(document.querySelectorAll("#plan-b-list .plan-skel-row").length > 0, "SP3 AC-7: opening the plan paints skeleton rows");
      var lmsg = document.querySelector("#plan-b-list .plan-loading-msg");
      ok(!!lmsg && lmsg.getAttribute("role") === "status" && /scanning for missing content/i.test(lmsg.textContent),
         "SP3 AC-7 a11y: the wait is announced via role=status and names the missing-content scan, not just drawn");
      ok(document.querySelector("#plan-b-list .plan-skel-row").getAttribute("aria-hidden") === "true",
         "SP3 AC-7 a11y: the skeleton rows are aria-hidden — texture, not four empty rows announced to AT");
      ok(el("plan-b-count").textContent === "—",
         "SP3 AC-7: the count reads — while loading, rather than showing a stale count as if it were current");
      // Positive control: the skeleton is REPLACED by real content. Without this, "paints a
      // skeleton" would pass just as well on a loading state that never resolves.
      planSelectedId = null;
      planRenderBuilder(sumView);
      ok(!document.querySelector("#plan-b-list .plan-skel-row") && document.querySelectorAll("#plan-b-list .plan-b-row").length === 6,
         "SP3 AC-7 (control): the first real render clears the skeleton — the loading state is not stuck");
      ok(el("plan-b-count").textContent === "6 items", "SP3 AC-7 (control): and the real count replaces the — placeholder");
      // A failed open must not leave the skeleton up forever: an endless loading state is a lie
      // about work still being in flight.
      planRenderLoading();
      planRenderLoadFailed(new Error("boom"));
      var lfail = document.querySelector("#plan-b-list .plan-load-failed");
      ok(!!lfail && lfail.getAttribute("role") === "alert" && !document.querySelector("#plan-b-list .plan-skel-row"),
         "SP3 AC-7: a failed open replaces the skeleton with a role=alert message instead of spinning forever");
      ok(/Live output is unaffected/.test(lfail.textContent),
         "SP3 AC-7: the failure says the audience is unaffected (NFR-024) rather than implying live output is at risk");
      // Control: a LATE failure must not wipe a run sheet that already painted.
      planRenderBuilder(sumView);
      planRenderLoadFailed(new Error("late"));
      ok(document.querySelectorAll("#plan-b-list .plan-b-row").length === 6 && !document.querySelector("#plan-b-list .plan-load-failed"),
         "SP3 AC-7 (control): a late rejection does not clobber a run sheet that already rendered");
      showSurface("plan");
      await sleep(40);
      planRenderBuilder(planView); // restore before the nav check
      // #9/#10 "Open in Live ▶" is a real, NAV-ONLY control (it was a dead button) — it switches to
      // the Live Console and sends no live-control command.
      el("plan-open-live").click();
      ok(el("surface-console").classList.contains("active") && !el("surface-plan").classList.contains("active"),
         "SP C-006: 'Open in Live' navigates to the Live Console (nav-only, not a go-live)");
      // C-006 invariant: the whole builder session (incl. Open-in-Live) sent NOT ONE live-control command.
      ok(window.__calls.filter(isLiveCtrl).length === ctrlBefore,
         "SP C-006: no plan-builder interaction sent a live-control command (staging/linking never changes Live)");

      // === Settings → Providers & Privacy (Figma 338:124, backend 86ajy034h) — the panel renders
      // REAL providers_view() state and each control invokes the right command. HONESTY is the whole
      // point of this screen: in this build cloud_status="not_configured", quota=null,
      // cloud_connected=false → honest "coming soon" + placeholder quota, NEVER a fabricated "12/40".
      // ==================================================================================
      var ppCall = function(cmd){ return window.__calls.filter(function(c){return c.cmd===cmd;}); };
      var ppLast = function(cmd){ var a=ppCall(cmd); return a.length?a[a.length-1]:null; };
      document.querySelector('.nav-item[data-surface="settings"]').click(); // showSurface → settingsActivate
      ok(el("surface-settings").classList.contains("active"), "PP: the Settings nav opens the Providers & Privacy surface");
      // hidden-attr-vs-css-display trap: assert the COMPUTED display, not just the .active class.
      ok(getComputedStyle(el("surface-settings")).display === "block",
         "PP C-008: the active Settings surface is computed display:block (not defeated by a display rule)");
      await sleep(60); // let settingsActivate resolve invoke("providers_view") + render
      ok(ppCall("providers_view").length > 0, "PP C-001: activation reads real state via providers_view()");
      ok(!/Application settings arrive later/.test(el("surface-settings").textContent),
         "PP C-001: the old stub copy is gone");

      // (1) Offline-by-default banner
      var ppBanner = document.querySelector("#surface-settings .pp-banner-ok");
      ok(!!ppBanner && /Offline by default/.test(ppBanner.textContent), "PP C-001: the Offline-by-default banner renders");
      ok(/never leave this device/.test(ppBanner.textContent), "PP C-001: the offline banner carries the honest 'never leave this device' copy");

      // (2) LIVE TRANSCRIPTION radio cards
      var odCard = el("pp-radio-ondevice"), clCard = el("pp-radio-cloud");
      ok(!!odCard && !!clCard, "PP C-002: both transcription radio cards render (On-device + Cloud)");
      ok(odCard.getAttribute("role")==="radio" && clCard.getAttribute("role")==="radio" &&
         document.querySelector('#pp-trans[role="radiogroup"]'),
         "PP C-002 a11y: the two cards form a radiogroup of role=radio");
      ok(odCard.getAttribute("aria-checked")==="true" && clCard.getAttribute("aria-checked")==="false",
         "PP C-002: On-device is the selected (private) default; Cloud is unselected");
      ok(/PRIVATE/.test(odCard.textContent) && !!odCard.querySelector(".pp-badge-private"),
         "PP C-002: the On-device card shows the PRIVATE badge");
      var odDetail = odCard.querySelector(".pp-radio-detail");
      ok(!!odDetail && /Small/.test(odDetail.textContent) && /works offline/.test(odDetail.textContent),
         "PP C-002: the On-device model line is driven from the backend on_device probe (model 'Small')");
      ok(/OPT-IN/.test(clCard.textContent) && !!clCard.querySelector(".pp-badge-optin"),
         "PP C-002: the Cloud card shows the OPT-IN badge");
      var clWarn = clCard.querySelector(".pp-warn");
      ok(!!clWarn && /Streams live microphone audio/.test(clWarn.textContent),
         "PP C-002: the Cloud card shows the amber live-audio warning");
      ok(/currently off/.test(clCard.textContent), "PP C-002: the Cloud footer honestly reads 'currently off' when consent is off");

      // Selecting Cloud is the opt-in gesture: grants transcription consent THEN switches mode.
      var scBefore = ppCall("set_cloud_consent").length, tmBefore = ppCall("set_transcription_mode").length;
      el("pp-radio-cloud").click();
      await sleep(70);
      var scT = ppCall("set_cloud_consent").filter(function(c){return c.args.kind==="transcription" && c.args.enabled===true;});
      ok(scT.length > 0, "PP C-002: selecting Cloud grants transcription consent (set_cloud_consent{transcription,true})");
      ok(ppLast("set_transcription_mode") && ppLast("set_transcription_mode").args.mode==="cloud",
         "PP C-002: selecting Cloud switches the mode (set_transcription_mode{cloud})");
      ok(el("pp-radio-cloud").getAttribute("aria-checked")==="true" && /currently on/.test(el("pp-radio-cloud").textContent),
         "PP C-002: after opt-in the Cloud card is selected and the footer reads 'currently on'");
      // Selecting On-device switches back AND revokes cloud-transcription consent (audio stays local).
      el("pp-radio-ondevice").click();
      await sleep(70);
      ok(ppLast("set_transcription_mode").args.mode==="on_device",
         "PP C-002: selecting On-device switches the mode back (set_transcription_mode{on_device})");
      ok(ppCall("set_cloud_consent").some(function(c){return c.args.kind==="transcription" && c.args.enabled===false;}),
         "PP C-002: selecting On-device revokes cloud-transcription consent (audio never leaves the device)");
      ok(el("pp-radio-ondevice").getAttribute("aria-checked")==="true", "PP C-002: On-device is selected again");

      // (3) SelahCue AI — honest status FIRST (no fabricated pills/quota before any live connection).
      var aiStatus = document.querySelector(".pp-ai-status");
      ok(!!aiStatus && !/Cloud connected/.test(aiStatus.textContent) && !/Available/.test(aiStatus.textContent),
         "PP C-006: with cloud_connected=false the Available / Cloud-connected pills are NOT shown");
      ok(!!aiStatus.querySelector(".pp-pill-muted") && /Coming soon/.test(aiStatus.textContent),
         "PP C-006: an honest 'Coming soon' pill is shown instead");
      ok(!/12\s*\/\s*40/.test(el("surface-settings").textContent),
         "PP C-006: NO fabricated '12 / 40' quota anywhere on the panel");
      var ppQuota = document.querySelector(".pp-quota");
      ok(!!ppQuota && ppQuota.classList.contains("pp-quota-empty") && /Not available yet/.test(ppQuota.textContent),
         "PP C-006: the quota shows an honest placeholder (null quota → 'Not available yet'), not numbers");
      ok(!!document.querySelector(".pp-badge-included") && /INCLUDED/.test(document.querySelector(".pp-ai-head").textContent),
         "PP C-001: the SelahCue AI provider card renders with the INCLUDED badge");

      // (3) selects — options + selected value from the backend; each change invokes its command.
      var tSel = el("pp-template");
      ok(!!tSel && tSel.tagName==="SELECT" && tSel.options.length===3 && tSel.value==="full_outline",
         "PP C-003: the notes-template select lists the backend options with the current value selected");
      ok(tSel.getBoundingClientRect().width > 40,
         "PP C-003: the template <select> does not collapse to a sliver (WKWebView flex-collapse trap)");
      tSel.value = "summary"; tSel.dispatchEvent(new Event("change"));
      await sleep(50);
      ok(ppLast("set_notes_template") && ppLast("set_notes_template").args.template==="summary",
         "PP C-003: changing the template invokes set_notes_template{template}");
      var xSel = el("pp-translation");
      ok(!!xSel && xSel.tagName==="SELECT" && xSel.value==="KJV" && xSel.classList.contains("pp-select-gold"),
         "PP C-003: the translation select shows the current (gold) value from the backend");
      xSel.value = "WEB"; xSel.dispatchEvent(new Event("change"));
      await sleep(50);
      ok(ppLast("set_preferred_translation") && ppLast("set_preferred_translation").args.code==="WEB",
         "PP C-003: changing the translation invokes set_preferred_translation{code}");

      // (3) INCLUDE IN NOTES — 6 switches in two columns; each invokes set_include_flag{name,enabled}.
      var incCols = document.querySelectorAll("#surface-settings .pp-inc-col");
      ok(incCols.length===2 && incCols[0].querySelectorAll(".pp-inc-row").length===3 && incCols[1].querySelectorAll(".pp-inc-row").length===3,
         "PP C-004: the 6 include-in-notes toggles render in two columns of three");
      var soc = el("pp-inc-social_excerpts");
      ok(!!soc && soc.getAttribute("role")==="switch" && soc.checked===false,
         "PP C-004: 'Social excerpts' is a switch reflecting the backend (off)");
      soc.click(); // check it
      await sleep(50);
      var incSoc = ppLast("set_include_flag");
      ok(incSoc && incSoc.args.name==="social_excerpts" && incSoc.args.enabled===true,
         "PP C-004: toggling a switch invokes set_include_flag{name:social_excerpts,enabled:true}");
      el("pp-inc-prayer_points").click(); // was on → turn off
      await sleep(50);
      ok(ppLast("set_include_flag").args.name==="prayer_points" && ppLast("set_include_flag").args.enabled===false,
         "PP C-004: toggling another switch off invokes set_include_flag{name:prayer_points,enabled:false}");
      // Every one of the remaining flags fires with the correct snake_case name + toggled value
      // (a wrong name string would be a silent no-op the 2-flag check above would miss).
      ["scripture_extraction","chapter_markers","notable_quotations","short_summary"].forEach(function(nm){
        var sw = el("pp-inc-"+nm), before = sw.checked;
        sw.click(); // checkbox change fires synchronously → the invoke is recorded immediately
        var last = ppLast("set_include_flag");
        ok(last && last.args.name===nm && last.args.enabled===(!before),
           "PP C-004: toggling '"+nm+"' invokes set_include_flag{name:"+nm+", enabled:"+(!before)+"}");
      });
      await sleep(40);
      // (M2 — no-lie on host rejection) a REJECTED mutation must revert the optimistic switch to the
      // backend-confirmed value (mutate() resyncs via providers_view), never leaving a lying toggle.
      var rjBackend = window.__pp.include.short_summary; // authoritative value the backend keeps
      ok(el("pp-inc-short_summary").checked === rjBackend, "PP C-004: (pre) the switch matches the backend value");
      window.__ppRejectOnce = true;
      el("pp-inc-short_summary").click(); // optimistic flip → host rejects → resync
      await sleep(90);
      ok(window.__pp.include.short_summary === rjBackend,
         "PP C-004: a rejected set_include_flag leaves the BACKEND value unchanged");
      ok(el("pp-inc-short_summary").checked === rjBackend,
         "PP C-004 (M2): after a host rejection the switch REVERTS to the backend value (no silent lie)");

      // (3) Generate — consent-gated end to end.
      ok(el("pp-consent-notes") && el("pp-consent-notes").getAttribute("role")==="switch" && el("pp-consent-notes").checked===false,
         "PP C-005: the cloud-notes consent switch reflects the backend (off) before opt-in");
      // Generate with consent OFF → the backend returns consent_required → prompt to opt in.
      window.__ppGen = "not_configured";
      el("pp-generate").click();
      await sleep(70);
      var genRes = el("pp-gen-result");
      ok(!!genRes && !genRes.hidden && genRes.getAttribute("role")==="alert" && /Turn on cloud processing/.test(genRes.textContent),
         "PP C-005: Generate with consent off surfaces a consent_required prompt (role=alert)");
      ok(!!el("pp-optin-retry"), "PP C-005: the consent_required prompt offers a one-click 'Opt in & generate'");
      // Opt in & generate → grants notes consent then retries; the service is not configured → honest 'coming soon'.
      el("pp-optin-retry").click();
      await sleep(90);
      ok(ppCall("set_cloud_consent").some(function(c){return c.args.kind==="notes" && c.args.enabled===true;}),
         "PP C-005: 'Opt in & generate' grants cloud-notes consent (set_cloud_consent{notes,true})");
      var genRes2 = el("pp-gen-result");
      ok(!!genRes2 && genRes2.getAttribute("role")==="status" && /coming soon/i.test(genRes2.textContent),
         "PP C-005: with consent on but the service not configured, Generate shows an honest 'coming soon'");
      ok(el("pp-consent-notes").checked===true, "PP C-005: the consent switch now reflects the granted consent");
      // Now simulate a configured service returning a draft.
      window.__ppGen = "ok";
      el("pp-generate").click();
      await sleep(80);
      var genOk = el("pp-gen-result");
      ok(!!genOk && genOk.classList.contains("pp-gen-ok") && /Grace That Feeds/.test(genOk.textContent),
         "PP C-005: a successful generation renders the returned draft (title + sections)");
      ok(genOk.querySelectorAll(".pp-gen-list li").length > 0 && /Isaiah 61:5/.test(genOk.textContent),
         "PP C-005: the draft renders section items + scriptures");
      ok(/\/\s*40/.test(document.querySelector(".pp-quota").textContent) && /27 remaining/.test(document.querySelector(".pp-quota").textContent),
         "PP C-006: a server-returned quota drives the meter (real numbers only, after a live response)");

      // (C-005 — the terminal generate outcomes each surface honestly; consent is on from the opt-in above.)
      window.__ppGen = "quota_exceeded"; el("pp-generate").click(); await sleep(70);
      var gQ = el("pp-gen-result");
      ok(gQ.getAttribute("role")==="alert" && /Monthly limit reached/.test(gQ.textContent),
         "PP C-005: quota_exceeded surfaces 'Monthly limit reached' (role=alert)");
      window.__ppGen = "transport"; el("pp-generate").click(); await sleep(70);
      var gT = el("pp-gen-result");
      ok(gT.getAttribute("role")==="alert" && /Couldn’t generate notes/.test(gT.textContent),
         "PP C-005: a transport failure (rejected invoke) surfaces 'Couldn’t generate notes' (role=alert)");
      window.__ppGen = "malformed"; el("pp-generate").click(); await sleep(70);
      var gM = el("pp-gen-result");
      ok(gM.getAttribute("role")==="alert" && /Couldn’t generate notes/.test(gM.textContent),
         "PP C-005: a malformed response surfaces 'Couldn’t generate notes' (role=alert)");
      // A degraded (local fallback) success renders the draft with a 'Local draft' badge — and,
      // following the errors above, the result region is role=status, NOT a lingering alert (L1).
      window.__ppGen = "degraded"; el("pp-generate").click(); await sleep(80);
      var gD = el("pp-gen-result");
      ok(gD.classList.contains("pp-gen-ok") && /Local draft/.test(gD.textContent),
         "PP C-005: a degraded generation renders the draft with a 'Local draft' badge (FR-135)");
      ok(gD.getAttribute("role")==="status",
         "PP C-005 (L1): a success after an error is announced as role=status, not a lingering alert");
      window.__ppGen = "ok"; // restore for any later reads

      // (C-006 positive) flip the backend to a connected+quota state and re-activate: the pills + meter appear.
      window.__pp.cloud_connected = true;
      window.__pp.quota = {used:13, limit:40, remaining:27, resets_label:"Sep 1"};
      document.querySelector('.nav-item[data-surface="settings"]').click();
      await sleep(60);
      var aiStatus2 = document.querySelector(".pp-ai-status");
      ok(/Available/.test(aiStatus2.textContent) && /Cloud connected/.test(aiStatus2.textContent) && !/Coming soon/.test(aiStatus2.textContent),
         "PP C-006: when cloud_connected=true the Available + Cloud-connected pills render (and 'Coming soon' is gone)");
      var q2 = document.querySelector(".pp-quota");
      ok(!q2.classList.contains("pp-quota-empty") && /13/.test(q2.textContent) && /\/\s*40/.test(q2.textContent),
         "PP C-006: a real quota renders the used/limit meter");
      window.__pp.cloud_connected = false; window.__pp.quota = null; // restore honest default

      // (C-007) excluded sections are absent.
      ok(!/Bring your own key/i.test(el("surface-settings").textContent) && !/Text-to-Speech/i.test(el("surface-settings").textContent) && !/BYOK/i.test(el("surface-settings").textContent),
         "PP C-007: the excluded BYOK/Advanced row and Text-to-Speech section are NOT built");

      // (C-008) layout robustness: the panel does not overflow horizontally past its surface.
      var ss = el("surface-settings");
      ok(ss.scrollWidth <= ss.clientWidth + 2, "PP C-008: the Settings body does not overflow horizontally (no sideways scroll)");

      // ==================================================================================
      // W — Design 2.0 parity, batch 1. CON-046 / CON-142 / PME-001 / PME-005 / PME-014-015.
      //
      // Every contrast number below is measured COMPOSITED from the REAL computed styles and
      // at EVERY stop of every gradient. Both properties matter and both were real defects:
      // CON-046's chip is `rgba(255,255,255,.18)` sitting invisibly between the ink and the
      // fill, so a token-on-token check reports "white on green" and misses it entirely; and
      // GO LIVE's fill is a two-stop gradient, so a single-stop check passes on the bright end
      // while the text is still failing on the dark end. Each group carries a control that must
      // measure as FAILING, so a green result proves the measurement works.
      // ==================================================================================
      function _sl(v){ v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); }
      function _lum(c){ return 0.2126*_sl(c[0])+0.7152*_sl(c[1])+0.0722*_sl(c[2]); }
      function _cr(a,b){ var la=_lum(a), lb=_lum(b), hi=Math.max(la,lb), lo=Math.min(la,lb); return (hi+0.05)/(lo+0.05); }
      function _rgba(s){ var m=String(s).match(/[-\d.]+/g)||["0","0","0"]; return [+m[0],+m[1],+m[2], m.length>3?+m[3]:1]; }
      function _over(f,b){ var a=(f[3]==null?1:f[3]); return [a*f[0]+(1-a)*b[0], a*f[1]+(1-a)*b[1], a*f[2]+(1-a)*b[2]]; }
      // ink over chip over backdrop — the layer order the browser actually paints.
      function _stack(ink, chip, bg){ var base=_over(chip,bg); return _cr(_over(ink,base), base); }
      function _f(r){ return r.toFixed(2); }
      // Resolve ANY colour declaration (hex, rgb(), or var(--token)) through the live CSS engine.
      function _resolve(decl){
        var pr=document.createElement("span");
        pr.style.cssText="position:absolute;left:-9999px;top:-9999px;background-color:"+decl;
        document.body.appendChild(pr);
        var c=getComputedStyle(pr).backgroundColor; pr.remove(); return _rgba(c);
      }
      // Every colour stop of an element's gradient, or its flat fill when it has no gradient.
      function _stops(node){
        var cs=getComputedStyle(node), m=(cs.backgroundImage||"none").match(/rgba?\([^)]*\)/g);
        return (m && m.length) ? m.map(_rgba) : [_rgba(cs.backgroundColor)];
      }
      function _same(a,b){ return a[0]===b[0] && a[1]===b[1] && a[2]===b[2]; }
      // Shorter wait budget than the default 150×20ms. This block sits at the very END of the
      // driver, so every FAILING predicate here spends virtual time that the RESULTS write still
      // needs: at the default budget a handful of real regressions could push the run past
      // --virtual-time-budget and the gate would report "NO RESULTS BLOCK" (an infra error) instead
      // of the named FAIL that tells you what broke. 60×20ms is ample for these local predicates.
      var wWait = function(pred){ return waitFor(pred, 60); };

      // --- CON-046: the keyboard-hint chips on the three token-filled buttons ---------------
      var wGl = el("golive"), wGlKey = wGl.querySelector(".key"), wGlLbl = wGl.querySelector(".gl-label");
      var wGlStops = _stops(wGl);
      ok(wGlStops.length === 2 && !_same(wGlStops[0], wGlStops[1]),
         "CON-046 (premise): GO LIVE really is a TWO-stop gradient (" + wGlStops.length + " stops, distinct), so 'measured at both stops' is not vacuous");
      // Control: the pairing that actually shipped must still measure as FAILING through this
      // exact helper. Without it, a green result below could just mean the helper returns 21.
      var wOld = wGlStops.map(function(s){ return _stack([255,255,255,1],[255,255,255,0.18],s); });
      ok(Math.max.apply(null, wOld) < 3.0,
         "CON-046 (control): the ORIGINAL white-on-rgba(255,255,255,.18) chip still measures below AA-LARGE through this helper (" + wOld.map(_f).join(" / ") + ":1) — the measurement is not rubber-stamping");
      var wGlChip = _rgba(getComputedStyle(wGlKey).backgroundColor), wGlInk = _rgba(getComputedStyle(wGlKey).color);
      wGlStops.forEach(function(s, i){
        var r = _stack(wGlInk, wGlChip, s);
        ok(r >= 4.5, "CON-046: the GO LIVE '⏎ Enter' chip clears AA-NORMAL on gradient stop " + (i+1) + " (" + _f(r) + ":1)");
      });
      ok(getComputedStyle(wGlKey).color === getComputedStyle(wGlLbl).color,
         "CON-046: the key hint carries the SAME dark ink as the GO LIVE label — one ink on one fill, not two answers to the same question");
      ok(parseFloat(getComputedStyle(wGlKey).fontSize) < 18.66,
         "CON-046 (premise): the chip is SMALL text (" + getComputedStyle(wGlKey).fontSize + "), so 4.5:1 is the right bar — a font-size bump must not silently relax this");

      // Every OTHER key chip on the page, measured on its own button's real fill. The generic
      // `button .key` fallthrough is where this defect class hides: the specific rule you are
      // reading does not mention the state at all, so a rule-by-rule review never sees it.
      // #blackout RESTING was exactly that — muted ink on the resting red gradient, 3.20 / 3.75:1.
      var wEveryKey = Array.prototype.slice.call(document.querySelectorAll("button .key"));
      ok(wEveryKey.length >= 5,
         "CON-046 (premise): every `.key` chip on the page is enumerated (" + wEveryKey.length + " found) — a chip added later is measured, not missed");
      wEveryKey.forEach(function(k){
        var host = k.closest("button"), kc = getComputedStyle(k);
        var worst = Math.min.apply(null, _stops(host).map(function(st){
          return _stack(_rgba(kc.color), _rgba(kc.backgroundColor), st);
        }));
        ok(worst >= 4.5, "CON-046: key chip '" + k.textContent.trim().slice(0,6) + "' on #" + (host.id||host.className) +
           " (RESTING) clears AA-NORMAL on every stop of its own fill (" + _f(worst) + ":1)");
      });
      // The resting BLACKOUT specifically, including its :hover brightness(1.06) — the state the
      // operator looks at most on a safety-critical control.
      var wBoRest = el("blackout"), wBoRestKey = wBoRest.querySelector(".key");
      var wBoRestCs = getComputedStyle(wBoRestKey);
      var wBoRestStops = _stops(wBoRest);
      ok(wBoRestStops.length === 2 && !_same(wBoRestStops[0], wBoRestStops[1]),
         "CON-046 (premise): resting BLACKOUT is a TWO-stop gradient, so both stops must be measured");
      var wBoRestWorst = Math.min.apply(null, wBoRestStops.map(function(st){
        return _stack(_rgba(wBoRestCs.color), _rgba(wBoRestCs.backgroundColor), st); }));
      ok(wBoRestWorst >= 4.5,
         "CON-046: the RESTING BLACKOUT key hint clears AA-NORMAL on both stops of the resting red gradient (" + _f(wBoRestWorst) + ":1)");
      // Control: the muted ink it used to fall through to must still measure as FAILING here.
      var wBoRestOld = Math.max.apply(null, wBoRestStops.map(function(st){
        return _stack(_resolve("var(--sc-text-secondary)"), [107,115,131,0.16], st); }));
      ok(wBoRestOld < 4.5,
         "CON-046 (control): the generic `button .key` muted ink still measures BELOW AA-normal on this fill (" + _f(wBoRestOld) + ":1) — the fix is the ink override, not a measurement artefact");
      ok(getComputedStyle(wBoRestKey).color === getComputedStyle(wBoRest).color,
         "CON-046: the resting BLACKOUT chip takes the button's OWN ink, so resting and engaged read the same (no chip jump on engage)");

      // BLACKOUT engaged: `.on` and [aria-pressed=true] are set together by the render loop, and
      // the review block resolves that state to the darkened canonical red. Measured rather than
      // assumed; a shared fix would have been wrong here.
      var wBo = el("blackout"), wBoKey = wBo.querySelector(".key");
      var wBoWasOn = wBo.classList.contains("on"), wBoPressed = wBo.getAttribute("aria-pressed");
      wBo.classList.add("on"); wBo.setAttribute("aria-pressed", "true");
      var wBoStops = _stops(wBo);
      var wBoChip = _rgba(getComputedStyle(wBoKey).backgroundColor), wBoInk = _rgba(getComputedStyle(wBoKey).color);
      var wBoWorst = Math.min.apply(null, wBoStops.map(function(s){ return _stack(wBoInk, wBoChip, s); }));
      ok(wBoWorst >= 4.5, "CON-046: the BLACKOUT-engaged key hint clears AA-NORMAL on its real engaged fill (" + _f(wBoWorst) + ":1)");
      var wBoLabel = Math.min.apply(null, wBoStops.map(function(s){ return _cr(_rgba(getComputedStyle(wBo).color), s); }));
      ok(wBoLabel >= 4.5,
         "CON-046 (premise): BLACKOUT engaged still uses the darkened canonical red (label " + _f(wBoLabel) + ":1) — that is WHY its white chip passes where GO LIVE's did not");
      if (!wBoWasOn) wBo.classList.remove("on");
      if (wBoPressed == null) wBo.removeAttribute("aria-pressed"); else wBo.setAttribute("aria-pressed", wBoPressed);

      // Clear Output armed sits on --sc-live, an INK used as a fill — the light chip measured 2.74:1.
      var wCa = el("clear-all"), wCaKey = wCa.querySelector(".key"), wCaWasArmed = wCa.classList.contains("armed");
      wCa.classList.add("armed");
      var wCaStops = _stops(wCa);
      var wCaChip = _rgba(getComputedStyle(wCaKey).backgroundColor), wCaInk = _rgba(getComputedStyle(wCaKey).color);
      var wCaWorst = Math.min.apply(null, wCaStops.map(function(s){ return _stack(wCaInk, wCaChip, s); }));
      ok(wCaWorst >= 4.5, "CON-046: the ARMED Clear-Output key hint clears AA-NORMAL on its fill (" + _f(wCaWorst) + ":1)");
      ok(getComputedStyle(wGlKey).backgroundColor !== getComputedStyle(wBoKey).backgroundColor,
         "CON-046: the chips are treated PER FILL, not re-merged into one shared declaration (the merge is what hid this defect)");
      // The armed LABEL, and the non-text contrast of the armed STATE itself. Fixing the label by
      // swapping the FILL would have cost the state its visibility — WCAG 1.4.11 covers states, and
      // the armed hint is a one-second transient whose only signal is that colour flip.
      var wCaArmedFill = _rgba(getComputedStyle(wCa).backgroundColor);
      var wCaLabel = _cr(_rgba(getComputedStyle(wCa).color), wCaArmedFill);
      ok(wCaLabel >= 4.5, "CON-046: the ARMED Clear-Output LABEL clears AA-NORMAL on its fill (" + _f(wCaLabel) + ":1, was white-on---sc-live at 3.27:1)");
      wCa.classList.remove("armed");
      var wCaRestFill = _rgba(getComputedStyle(wCa).backgroundColor);
      if (wCaWasArmed) wCa.classList.add("armed");
      var wCaState = _cr(wCaArmedFill, wCaRestFill);
      ok(wCaState >= 3.0,
         "CON-046: ARMED still stands out from RESTING at the 3:1 non-text bar (" + _f(wCaState) + ":1) — the label fix did not cost the state its visibility");
      ok(_cr(wCaArmedFill, _resolve("var(--panel)")) >= 3.0,
         "CON-046: the ARMED fill still clears 3:1 against the page behind it (" + _f(_cr(wCaArmedFill, _resolve("var(--panel)"))) + ":1)");

      // --- CON-142: three unrelated `.seg` declarations, equal specificity, last-wins ---------
      ok(document.querySelectorAll(".seg").length === 0,
         "CON-142: no element carries the bare `seg` class any more — the three families cannot collide again through markup");
      var wSub = document.querySelector(".subtab-seg"), wSubCs = getComputedStyle(wSub);
      ok(wSubCs.columnGap === "3px",
         "CON-142: the Timer|Stage control keeps its OWN 3px gap (the transcript rule was leaking 8px into it) — got " + wSubCs.columnGap);
      ok(wSubCs.alignItems !== "baseline",
         "CON-142: the Timer|Stage control no longer inherits the transcript line's align-items:baseline — got " + wSubCs.alignItems);
      ok(wSubCs.paddingTop === "3px" && wSubCs.borderTopLeftRadius === "9px",
         "CON-142: the Timer|Stage control keeps its own inset chrome (padding " + wSubCs.paddingTop + ", radius " + wSubCs.borderTopLeftRadius + ")");
      var wSubBtn = wSub.querySelector(".subtab-seg-btn"), wSubBtnCs = getComputedStyle(wSubBtn);
      ok(wSubBtnCs.fontSize === "13px",
         "CON-142: a sub-tab button keeps its own 13px label — `.seg button` (0,0,1,1) used to OUTRANK `.seg-btn` (0,0,1,0) and force 12px; got " + wSubBtnCs.fontSize);
      ok(wSubBtnCs.paddingLeft === "0px",
         "CON-142: a sub-tab button keeps its own `padding: 6px 0` — the same specificity bug forced 6px 8px; got " + wSubBtnCs.paddingLeft);
      var wTp = el("transcript-partial"), wTpWasHidden = wTp.hidden; wTp.hidden = false;
      var wTpCs = getComputedStyle(wTp);
      ok(wTpCs.paddingTop === "0px" && wTpCs.borderTopWidth === "0px" && wTpCs.marginBottom === "0px" && wTpCs.borderTopLeftRadius === "0px",
         "CON-142: a transcript line no longer inherits the segmented control's inset chrome (padding " + wTpCs.paddingTop + ", border " + wTpCs.borderTopWidth + ", margin-bottom " + wTpCs.marginBottom + ", radius " + wTpCs.borderTopLeftRadius + ")");
      ok(wTpCs.columnGap === "8px" && wTpCs.alignItems === "baseline",
         "CON-142: the transcript line keeps its own 8px baseline-aligned geometry (gap " + wTpCs.columnGap + ", align " + wTpCs.alignItems + ")");
      wTp.hidden = wTpWasHidden;
      // Positive control: the rename must have MOVED the Theme-Designer rules, not deleted them.
      // Without this, "the collision is gone" is indistinguishable from "the CSS is gone".
      var wTd = el("td-bg-type"), wTdCs = getComputedStyle(wTd), wTdBtn = wTd.querySelector("button");
      ok(wTdCs.display === "flex",
         "CON-142 (positive control): the Theme-Designer option group still gets its .td-seg layout — got display " + wTdCs.display);
      ok(!!wTdBtn && getComputedStyle(wTdBtn).flexGrow === "1",
         "CON-142 (positive control): `.td-seg button` still styles the designer's segment buttons (the rename moved the rules, it did not drop them)");

      // --- PME-005: .pm-btn-primary:hover ---------------------------------------------------
      var wHoverRule = /\.pm-btn-primary:hover\s*\{([^}]*)\}/.exec(window.__CSSTEXT || "");
      ok(!!wHoverRule, "PME-005 (premise): the .pm-btn-primary:hover rule is present in the shipped app.css");
      var wHb = wHoverRule ? /background(?:-color)?\s*:\s*([^;]+)/.exec(wHoverRule[1]) : null;
      ok(!!wHb, "PME-005 (premise): the hover rule declares a background, so there is a value to measure");
      if (wHb) {
        var wHoverBg = _resolve(wHb[1].trim());
        var wRestBg = _rgba(getComputedStyle(document.querySelector(".pm-btn-primary")).backgroundColor);
        var wHoverR = _cr([255,255,255,1], wHoverBg), wRestR = _cr([255,255,255,1], wRestBg);
        ok(wHoverR >= 4.5, "PME-005: the HOVERED primary keeps its white label at AA-NORMAL (" + _f(wHoverR) + ":1) — hover is a real UI state and WCAG applies to it");
        ok(_lum(wHoverBg) < _lum(wRestBg),
           "PME-005: hover DARKENS the fill instead of lightening it (rest " + _f(wRestR) + ":1 → hover " + _f(wHoverR) + ":1), matching the fix already shipped for .tb-golive");
        var wOldHover = _resolve("var(--sc-primary-hover)");
        ok(_cr([255,255,255,1], wOldHover) < 4.5,
           "PME-005 (control): --sc-primary-hover itself still measures BELOW AA-normal for white (" + _f(_cr([255,255,255,1], wOldHover)) + ":1) — the TOKEN VALUE is untouched; only this rule stopped using it");
      }

      // --- PME-014 / PME-015: the two missing topbar primary actions ------------------------
      document.querySelector('.nav-item[data-surface="presentation"]').click();
      ok(await wWait(function(){ return el("surface-presentation").classList.contains("active") && !el("pm-library").hidden; }),
         "PME-014/015 (setup): the Presentation surface opens on the Library");
      var wPres = el("pm-present"), wAtp = el("pm-addtoplan");
      ok(!!wPres && wPres.tagName === "BUTTON", "PME-014: a real '▶ Present' control exists in the Presentation topbar (it was reachable ONLY from the ⌘K palette)");
      ok(!!wAtp && wAtp.tagName === "BUTTON", "PME-015: an 'Add to plan' control exists in the Presentation topbar");
      ok(getComputedStyle(wPres).display === "none" && getComputedStyle(wAtp).display === "none",
         "PME-014/015: both topbar actions are hidden by COMPUTED display while browsing the Library (not merely the [hidden] attribute, which a class `display` rule would defeat)");
      ok(wPres.getClientRects().length === 0 && wAtp.getClientRects().length === 0,
         "PME-014/015: the hidden actions are genuinely unpainted, so they leave the tab order too (WCAG 2.4.3)");
      ok(await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-open"); }), "PME-014 (setup): the library lists at least one presentation to open");
      el("pm-lib-grid").querySelector(".pm-lib-open").click();
      ok(await wWait(function(){ return !el("pm-grid").hidden; }), "PME-014 (setup): opening a presentation shows the slide grid");
      ok(getComputedStyle(wPres).display !== "none" && wPres.getClientRects().length > 0,
         "PME-014: '▶ Present' is really PAINTED once a presentation is open (computed display " + getComputedStyle(wPres).display + ")");
      ok(getComputedStyle(wAtp).display !== "none" && wAtp.getClientRects().length > 0,
         "PME-015: 'Add to plan' is really painted once a presentation is open");
      ok(getComputedStyle(wPres).backgroundImage === "none",
         "PME-003: '▶ Present' uses the FLAT primary fill, never the frame's gradient (white on the frame's light stop is 3.78:1)");
      var wGlN = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
      wPres.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length > wGlN; }),
         "PME-014: '▶ Present' presents from GRID mode (deck_go_live) — the same split the ⌘K palette already made");
      el("pm-grid-edit").click();
      ok(await wWait(function(){ return getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display !== "none"; }),
         "PME-014 (setup): Edit ▸ opens the authoring editor");
      ok(getComputedStyle(wPres).display !== "none", "PME-014: '▶ Present' stays available in the EDITOR, not just the grid");
      var wGlN2 = window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length;
      wPres.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_go_live"; }).length > wGlN2; }),
         "PME-014: '▶ Present' presents the selected slide from EDITOR mode (deck_go_live)");

      // --- PME-001: the LIVE badge on the presented slide's rail card ------------------------
      // Measured on the REAL badge the editor just rendered, not on a synthetic probe.
      ok(await wWait(function(){ return !!document.querySelector(".pm-slide-live-badge"); }),
         "PME-001 (positive control): a presented slide really renders the non-colour LIVE badge — the ratio below is measured on a live element");
      var wBadge = document.querySelector(".pm-slide-live-badge");
      if (wBadge) {
        var wBc = getComputedStyle(wBadge), wBFill = _rgba(wBc.backgroundColor), wBInk = _rgba(wBc.color);
        var wBR = _cr(wBInk, wBFill);
        ok(wBR >= 4.5, "PME-001: the LIVE badge clears AA-NORMAL at " + wBc.fontSize + "/" + wBc.fontWeight + " (" + _f(wBR) + ":1) — an accessibility affordance that was itself failing accessibility");
        ok(parseFloat(wBc.fontSize) < 18.66,
           "PME-001 (premise): the badge really is SMALL text (" + wBc.fontSize + "), so AA-normal applies — a size change must not silently relax this check");
        ok(!_same(wBFill, _resolve("var(--sc-live)")),
           "PME-001: the badge no longer uses --sc-live (an INK) as a fill; it uses the canonical white-text red fill, the same resolution #blackout already took");
        ok(_cr([255,255,255,1], _resolve("var(--sc-live)")) < 4.5,
           "PME-001 (control): white on --sc-live still measures BELOW AA-normal (" + _f(_cr([255,255,255,1], _resolve("var(--sc-live)"))) + ":1) — the token value is untouched; the badge stopped using it as a fill");
      }

      // --- PME-015 behaviour: a REAL plan item with a REAL deck link -------------------------
      var wOpenId = window.__LIB.open;
      var wOpenDeck = window.__LIB.decks.filter(function(d){ return d.id === wOpenId; })[0];
      var wAiN = window.__calls.filter(function(c){ return c.cmd === "add_item"; }).length;
      var wSicN = window.__calls.filter(function(c){ return c.cmd === "set_item_content"; }).length;
      wAtp.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "set_item_content"; }).length > wSicN; }),
         "PME-015: 'Add to plan' commits through the host (set_item_content), not a local stub");
      var wAdd = window.__calls.filter(function(c){ return c.cmd === "add_item"; }).pop();
      ok(window.__calls.filter(function(c){ return c.cmd === "add_item"; }).length === wAiN + 1 && wAdd.args.kind === "slide_group",
         "PME-015: it appends exactly ONE Presentation item to the plan (add_item{kind:slide_group})");
      ok(wAdd.args.title === wOpenDeck.name,
         "PME-015: the new plan item is titled with the OPEN deck's name (\"" + wAdd.args.title + "\")");
      var wLink = window.__calls.filter(function(c){ return c.cmd === "set_item_content"; }).pop();
      ok(wLink.args.link && wLink.args.link.kind === "deck" && wLink.args.link.id === wOpenId,
         "PME-015: the item carries a REAL deck reference (link{kind:deck,id:" + (wLink.args.link && wLink.args.link.id) + "}), not an unlinked title");
      ok(wLink.args.link.slide_count === wOpenDeck.slides,
         "PME-015: the link carries the deck's slide count (" + wLink.args.link.slide_count + ") to the host, which owns no deck store — so the plan row reports a real count");
      ok(!el("pm-toast").hidden && /plan/i.test(el("pm-toast").textContent),
         "PME-015: a role=status toast confirms the plan edit");
      var wUndo = el("pm-toast").querySelector(".pm-toast-action");
      ok(!!wUndo && /Undo/i.test(wUndo.textContent), "PME-015: the toast offers Undo — the plan edit is reversible");
      var wRiN = window.__calls.filter(function(c){ return c.cmd === "remove_item"; }).length;
      wUndo.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "remove_item"; }).length > wRiN; }),
         "PME-015: Undo really removes the item it just added (remove_item)");
      // Rollback: a rejected LINK must not leave behind a plan row that claims a deck it has not got.
      if (!el("pm-error").hidden && el("pm-error-dismiss")) el("pm-error-dismiss").click();
      window.__sicRejectOnce = true;
      var wRiN2 = window.__calls.filter(function(c){ return c.cmd === "remove_item"; }).length;
      wAtp.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "remove_item"; }).length > wRiN2; }),
         "PME-015: a REJECTED deck link rolls the plan item back (no orphan row promising a deck it does not hold)");
      ok(await wWait(function(){ return !el("pm-error").hidden; }) && el("pm-error").getAttribute("role") === "alert",
         "PME-015: a rejected deck link surfaces the role=alert error banner — the failure is reported, not swallowed");
      if (el("pm-error-dismiss")) el("pm-error-dismiss").click();

      // --- CON-128 / CON-139: detector liveness -------------------------------------------
      // THE ACCEPTANCE BAR, as a test: a dead detector and a silent room must not render
      // identically. Every fixture below asserts it actually REACHED the state it names before
      // asserting what that state renders — silence looks the same from outside, so a fixture
      // that never arrives would let all of this pass while proving nothing.
      document.querySelector('.nav-item[data-surface="console"]').click();
      ok(await wWait(function(){ return el("surface-console").classList.contains("active"); }),
         "CON-128/139 (setup): the console surface is active");
      el("rtab-detections").click();
      ok(await wWait(function(){ return !el("rpanel-detections").hidden; }),
         "CON-128/139 (setup): the Detected Scriptures panel is open");
      var wHealth = function(h){ window.__detHealth = h; window.__detHealthFail = false; return window.__detHealthRefresh(); };
      var wHBox = el("det-health"), wHTitle = el("det-health-title"), wHBody = el("det-health-body"),
          wHRetry = el("det-health-retry"), wEmptyMsg = el("det-empty-msg"), wEmptySub = el("det-empty-sub");
      ok(!!wHBox && !!wEmptyMsg, "CON-128/139: the detector-health element and a state-driven empty state exist");

      // (1) LISTENING, nothing heard yet — a silent room.
      await wHealth({state:"listening", provider:"whisper-small", error:null, can_retry:false});
      ok(wHBox.hidden, "CON-128 (premise): a healthy listening detector shows NO fault card — the fixture reached 'listening'");
      var wSilent = (wEmptyMsg.textContent + " " + wEmptySub.textContent).replace(/\s+/g, " ").trim();
      ok(/listening/i.test(wSilent), "CON-128: a silent room says it is LISTENING (\"" + wSilent.slice(0, 58) + "\")");
      ok(/whisper-small/.test(wSilent), "CON-128: it names the engine producing the transcript (FR-120 honest disclosure), rather than an unattributed claim");

      // (2) IDLE — not listening at all. Must NOT read like (1).
      await wHealth({state:"idle", provider:null, error:null, can_retry:false});
      var wIdle = (wEmptyMsg.textContent + " " + wEmptySub.textContent).replace(/\s+/g, " ").trim();
      ok(wHBox.hidden, "CON-128 (premise): idle is not a fault either — the fixture reached 'idle'");
      ok(/not running/i.test(wIdle) && wIdle !== wSilent,
         "CON-128: 'not listening' and 'listening, nothing yet' render DIFFERENTLY — they used to be the same sentence");

      // (3) UNAVAILABLE — a dead detector. THE other half of the bar.
      await wHealth({state:"unavailable", provider:null, error:"The speech model failed to load.", can_retry:true});
      ok(!wHBox.hidden && getComputedStyle(wHBox).display !== "none" && wHBox.getClientRects().length > 0,
         "CON-139 (premise): a dead detector renders a PAINTED fault card — the fixture reached 'unavailable'");
      ok(/Detection unavailable/i.test(wHTitle.textContent), "CON-139: it says the detection is unavailable, in words");
      ok(/speech model failed to load/i.test(wHBody.textContent),
         "CON-139: it shows the HOST'S retained reason, not a generic apology (\"" + wHBody.textContent.slice(0, 50) + "\")");
      var wDead = (wHTitle.textContent + " " + wHBody.textContent + " " + wEmptyMsg.textContent).replace(/\s+/g, " ").trim();
      ok(wDead !== wSilent,
         "ACCEPTANCE BAR: a DEAD detector and a SILENT room do not render identically — this is the property the whole batch is measured against");
      var wCardBg = _rgba(getComputedStyle(wHBox).backgroundColor);
      ok(_cr(_rgba(getComputedStyle(wHTitle).color), wCardBg) >= 4.5,
         "CON-139: the fault heading clears AA-NORMAL on the card (" + _f(_cr(_rgba(getComputedStyle(wHTitle).color), wCardBg)) + ":1)");
      ok(_cr(_rgba(getComputedStyle(wHBody).color), wCardBg) >= 4.5,
         "CON-139: the fault body clears AA-NORMAL on the card (" + _f(_cr(_rgba(getComputedStyle(wHBody).color), wCardBg)) + ":1)");
      ok(!wHRetry.hidden, "CON-139: retry is offered when the host says can_retry");
      var wRetryEdge = Math.max(_cr(_rgba(getComputedStyle(wHRetry).backgroundColor), wCardBg),
                                _cr(_rgba(getComputedStyle(wHRetry).borderTopColor), wCardBg));
      ok(wRetryEdge >= 3.0,
         "CON-139: the retry control is distinguishable from the card it sits on (" + _f(wRetryEdge) + ":1, 3:1 non-text bar) — the frame's own treatment measures 1.07:1");

      // (4) can_retry FALSE — the affordance must not exist.
      await wHealth({state:"unavailable", provider:null, error:"Microphone is in use by another application.", can_retry:false});
      ok(!wHBox.hidden && wHRetry.hidden,
         "CON-139: when the host says can_retry is FALSE the retry control is not rendered at all");

      // (5) UNSUPPORTED — a build fact, not a scare.
      await wHealth({state:"unsupported", provider:null, error:null, can_retry:false});
      ok(!wHBox.hidden && wHBox.classList.contains("det-health-quiet"),
         "CON-139 (premise): 'unsupported' renders in the QUIET treatment, not the amber fault card — the fixture reached 'unsupported'");
      ok(wHRetry.hidden, "CON-139: no retry is offered in 'unsupported' — the host cannot even construct the permission to honour it");

      // (6) UNKNOWN — the case the NO SIGNAL fallthrough gets wrong.
      window.__detHealthFail = true;
      await window.__detHealthRefresh();
      ok(!wHBox.hidden && wHBox.classList.contains("det-health-quiet"),
         "CON-139 (premise): an unreported detector renders quietly — the fixture reached UNKNOWN");
      ok(/unknown/i.test(wHTitle.textContent) && !/unavailable/i.test(wHTitle.textContent),
         "TRI-STATE: absent telemetry renders as UNKNOWN, never as a fault (\"" + wHTitle.textContent + "\")");
      ok(wHTitle.textContent !== "" && !wHBox.classList.contains("det-health-fault"),
         "TRI-STATE: ...and it is not silently treated as healthy either — both wrong readings collapse three states into two");
      window.__detHealthFail = false;

      // (7) retry calls the host, and a refusal survives the 1 Hz re-render.
      await wHealth({state:"unavailable", provider:null, error:"Audio device disappeared.", can_retry:true});
      window.__detRetryRefuse = "Retry does not apply while detection is 'idle'.";
      var wRtN = window.__calls.filter(function(c){ return c.cmd === "retry_detection"; }).length;
      wHRetry.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "retry_detection"; }).length > wRtN; }),
         "CON-139: the retry control calls retry_detection on the host");
      ok(await wWait(function(){ return /does not apply/i.test(wHBody.textContent); }),
         "CON-139: a refused retry shows the HOST'S reason");
      await window.__detHealthRefresh();
      ok(/does not apply/i.test(wHBody.textContent),
         "CON-139: the refusal SURVIVES the next poll's re-render — written straight to the DOM it would vanish within a second of appearing");
      window.__detRetryRefuse = null;
      wHRetry.click();
      ok(await wWait(function(){ return wHBox.hidden; }),
         "CON-139: a successful retry recovers, and the stale refusal is not left showing beside the recovered state");
      window.__detHealth = null;

      // --- PME-058 / Q-08: the delete confirm must state the SLIDE COUNT, and must not promise
      // reversibility the host cannot deliver. The interesting case is NOT the one where the count
      // is known — it is the ABSENT one. A naive "it says 2 slides" check passes happily while an
      // unknown count renders as a confidently wrong "its 0 slides".
      var wOpenDel = async function(){
        el("pm-deckswitch").click();
        if (!(await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots"); }))) return null;
        el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots").click();
        if (!(await wWait(function(){ return !!el("pm-lib-menu"); }))) return null;
        var items = Array.prototype.slice.call(el("pm-lib-menu").querySelectorAll("button"));
        var del = items.filter(function(b){ return /^Delete/.test(b.textContent); })[0];
        if (!del) return null;
        del.click();
        if (!(await wWait(function(){ return !!document.querySelector(".pm-confirm-body"); }))) return null;
        return document.querySelector(".pm-confirm-body").textContent.replace(/\s+/g, " ").trim();
      };
      var wCloseDel = function(){
        var back = document.querySelector(".pm-confirm-back");
        if (!back) return;
        var cancel = Array.prototype.slice.call(back.querySelectorAll("button")).filter(function(b){ return /Cancel/i.test(b.textContent); })[0];
        if (cancel) cancel.click(); else back.remove();
      };
      // The deck the driver will ACTUALLY act on: the first RENDERED card, read by its data-id.
      // Deriving it from LIB order instead was a real fixture bug — the grid sorts by NAME, so the
      // fixture named one deck while the UI deleted another, and a check about "the deck that was
      // not retained" was quietly reporting on a different deck. A fixture that does not reach the
      // condition its check names is worth less than no check.
      var wFirstDeck = function(){
        var card = el("pm-lib-grid") && el("pm-lib-grid").querySelector(".pm-lib-card");
        if (!card) return null;
        var id = Number(card.dataset.id);
        return window.__LIB.decks.filter(function(d){ return d.id === id; })[0] || null;
      };
      el("pm-deckswitch").click();
      await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card"); });
      if (el("pm-lib-q")) { el("pm-lib-q").value = ""; el("pm-lib-q").dispatchEvent(new Event("input", {bubbles:true})); }
      var wD = wFirstDeck();
      if (wD) {
        wD.slides = 7;
        var wBody7 = await wOpenDel();
        ok(!!wBody7 && /its 7 slides/.test(wBody7),
           "PME-058: the delete confirm names the SLIDE COUNT (\"" + String(wBody7).slice(0, 70) + "\")");
        wCloseDel();
        wD.slides = 1;
        var wBody1 = await wOpenDel();
        ok(!!wBody1 && /its 1 slide\b/.test(wBody1) && !/1 slides/.test(wBody1),
           "PME-058: a one-slide presentation reads \"its 1 slide\", not \"1 slides\"");
        wCloseDel();
        // THE CASE THAT MATTERS: the host did not report a count.
        delete wD.slides;
        var wBodyU = await wOpenDel();
        ok(!!wBodyU && /its slides/.test(wBodyU),
           "PME-058: an UNKNOWN slide count falls back to \"its slides\" (\"" + String(wBodyU).slice(0, 70) + "\")");
        ok(!!wBodyU && !/\b0 slides?\b/.test(wBodyU) && !/undefined/.test(wBodyU) && !/NaN/.test(wBodyU),
           "PME-058: an unknown count is never rendered as a confident \"0 slides\"/undefined/NaN — vague beats fabricated");
        // Q-08 honesty invariant: the PROMISE and the BEHAVIOUR must agree. The host has no restore
        // path today (no deck_export/deck_import/deck_restore; DeckLibrary::delete is a hard drop),
        // so the copy must say so. When the seam lands and an Undo appears, this check goes RED and
        // forces the sentence to be corrected with it — in either direction the product cannot lie.
        // Q-08, flipped. deck_restore + a bounded trash shipped, so "can't be undone" is now FALSE.
        ok(!/can.t be undone/i.test(wBodyU || ""),
           "Q-08: the confirm no longer claims the delete is irreversible — deck_restore exists");
        ok(!/you can undo/i.test(wBodyU || ""),
           "Q-08: ...and it does not promise undo either: whether THIS deck is retained depends on its size against the trash budget, which is not knowable at confirm time. The promise is made where it can be verified");
        wCloseDel();
        wD.slides = 3;
        var wDoDelete = async function(){
          el("pm-deckswitch").click();
          if (!(await wWait(function(){ return !!el("pm-lib-grid").querySelector(".pm-lib-card .pm-lib-dots"); }))) return false;
          if (!(await wOpenDel())) return false;
          var back = document.querySelector(".pm-confirm-back");
          var go = back ? Array.prototype.slice.call(back.querySelectorAll("button")).filter(function(b){ return /^Delete$/.test(b.textContent.trim()); })[0] : null;
          if (!go) return false;
          go.click();
          return await wWait(function(){ return !el("pm-toast").hidden; });
        };
        // THE PROPERTY, capability-aware: Undo is offered IF AND ONLY IF the host reports this deck
        // as restorable. The previous version compared the copy against the webview's OWN behaviour,
        // which stayed self-consistent — and therefore GREEN — when the host gained a capability the
        // UI was not using. This version fails in that case.
        var wTarget = wFirstDeck(), wTargetId = wTarget && wTarget.id, wTargetName = wTarget && wTarget.name;
        window.__deckNoRetain = null;
        ok(await wDoDelete(), "Q-08 (setup): a restorable delete completes");
        var wRestorableNow = (window.__LIB.trash || []).some(function(t){ return t.id === wTargetId; });
        var wUndoShown = !!el("pm-toast").querySelector(".pm-toast-action");
        ok(wRestorableNow && wUndoShown,
           "Q-08: a RESTORABLE delete offers Undo (host restorable=" + wRestorableNow + ", Undo offered=" + wUndoShown + ")");
        // The restored name must be the host's, not the remembered one. Make the old name be taken
        // first, so restore genuinely uniquifies — a fixture that never reaches the rename would
        // let a "shows the right name" check pass while showing the wrong one.
        await invoke("deck_new", { name: wTargetName });
        var wRestN = window.__calls.filter(function(c){ return c.cmd === "deck_restore"; }).length;
        el("pm-toast").querySelector(".pm-toast-action").click();
        ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "deck_restore"; }).length > wRestN; }),
           "Q-08: Undo calls deck_restore on the host — the client cannot rebuild the slides itself");
        await wWait(function(){ return /Restored/.test(el("pm-toast").textContent); });
        var wToastTxt = el("pm-toast").textContent;
        var wBackName = (window.__LIB.decks.filter(function(d){ return d.id === wTargetId; })[0] || {}).name;
        ok(/\(2\)/.test(wBackName || ""),
           "Q-08 (premise): the fixture really reached the RENAME path — the deck came back as \"" + wBackName + "\", not its original name");
        ok(wToastTxt.indexOf(wBackName) >= 0,
           "Q-08: the confirmation quotes the name the deck came back UNDER (\"" + wBackName + "\"), not the one that was deleted");
        // THE CASE THAT MATTERS: a delete the host did NOT retain must offer no Undo at all.
        var wBig = wFirstDeck();
        if (wBig) {
          window.__deckNoRetain = wBig.id;
          ok(await wDoDelete(), "Q-08 (setup): a non-retained delete completes");
          var wRetained = (window.__LIB.trash || []).some(function(t){ return t.id === wBig.id; });
          var wUndoShown2 = !!el("pm-toast").querySelector(".pm-toast-action");
          ok(!wRetained && !wUndoShown2,
             "Q-08: a delete the host could NOT retain offers no Undo (restorable=" + wRetained + ", Undo offered=" + wUndoShown2 + ") — an affordance that would fail is a new fabrication, not a courtesy");
          window.__deckNoRetain = null;
        }
        // A refusal is a rejected promise with the host's OWN reason: the affordance was valid when
        // shown, but the trash aged out before the operator reached for it.
        var wT2 = wFirstDeck();
        if (wT2) {
          ok(await wDoDelete(), "Q-08 (setup): a third delete completes so Undo is on screen");
          var wAct = el("pm-toast").querySelector(".pm-toast-action");
          if (wAct) {
            window.__LIB.trash.length = 0; // it ages out between offer and click
            if (el("pm-error-dismiss") && !el("pm-error").hidden) el("pm-error-dismiss").click();
            wAct.click();
            ok(await wWait(function(){ return !el("pm-error").hidden; }),
               "Q-08: a refused restore surfaces an error rather than failing silently");
            ok(/no longer be restored/i.test(el("pm-error-msg").textContent),
               "Q-08: it shows the HOST'S own reason (\"" + el("pm-error-msg").textContent.slice(0, 60) + "\"), not a generic \"couldn't do that, retry\" for something retrying cannot fix");
            if (el("pm-error-dismiss")) el("pm-error-dismiss").click();
          }
        }
      }

      // --- \u00a710 case 6 / CON-099, CON-101, CON-102: the engaged BLACKOUT state ------------
      // The bug is that the most destructive state in the product explains nothing: the operator
      // sees "BLACKOUT ON" and no statement of what the audience sees or how to get back. So the
      // checks that matter are the ones about the ABSENT case (nothing shown when not blacked out)
      // and about the explanation being genuinely PAINTED, not merely un-hidden — a class display
      // rule defeats [hidden] in this webview, which is how an "it appears" check goes vacuous.
      var wBoBtn = el("blackout"), wExp = el("blackout-explain"), wRes = el("restore-output");
      ok(!!wExp && !!wRes, "CON-101/102: the blackout explanation and a Restore control exist at all");
      // (a) NOT blacked out — both must be genuinely gone, and the label must not claim the state.
      ok(getComputedStyle(wExp).display === "none" && wExp.getClientRects().length === 0,
         "CON-101 (control): with output live the explanation is NOT painted — otherwise 'it appears on blackout' proves nothing");
      ok(getComputedStyle(wRes).display === "none" && wRes.getClientRects().length === 0,
         "CON-102 (control): with output live the Restore control is unpainted and out of the tab order");
      ok(el("blackout-label").textContent.trim() === "BLACKOUT",
         "CON-099: with output live the button reads BLACKOUT (the action), not the state");
      // (b) engage it through the REAL command path, not by poking the view.
      wBoBtn.click();
      ok(await wWait(function(){ return !wExp.hidden; }), "CON-101 (setup): engaging blackout via the real command renders the engaged state");
      ok(getComputedStyle(wExp).display !== "none" && wExp.getClientRects().length > 0,
         "CON-101: the explanation is actually PAINTED during a blackout (computed display " + getComputedStyle(wExp).display + ")");
      // Normalise whitespace first: the sentence wraps in the markup, so textContent carries a
      // newline + indent and a literal-phrase regex silently misses. Assert the words, not the layout.
      var wExpTxt = wExp.textContent.replace(/\s+/g, " ").trim();
      ok(/audience sees nothing/i.test(wExpTxt) && /restore/i.test(wExpTxt),
         "CON-101: it says what the AUDIENCE sees and how to get back — the two things the state never stated (\"" + wExpTxt.slice(0, 72) + "\")");
      ok(wExp.getAttribute("role") === "status",
         "CON-101: the explanation is announced to assistive tech (role=status), not a silent visual-only cue");
      ok(el("blackout-label").textContent.trim() === "BLACKED OUT",
         "CON-099: engaged, the button states the STATE in words (non-colour, WCAG 1.4.1)");
      ok(document.querySelector("#emergency .note").hidden,
         "CON-101: the general footer note yields its slot, so the bar carries one sentence not two");
      // Contrast of the explanation, measured composited against the footer's REAL ground.
      var wFoot = _rgba(getComputedStyle(el("emergency")).backgroundColor);
      var wExpR = _stack(_rgba(getComputedStyle(wExp).color), _rgba(getComputedStyle(wExp).backgroundColor), wFoot);
      ok(wExpR >= 4.5, "CON-101: the explanation clears AA-NORMAL on the real footer ground (" + _f(wExpR) + ":1)");
      var wResCs = getComputedStyle(wRes);
      var wResR = _cr(_rgba(wResCs.color), _rgba(wResCs.backgroundColor));
      ok(wResR >= 4.5, "CON-102: the Restore label clears AA-NORMAL on its fill (" + _f(wResR) + ":1)");
      ok(_cr(_rgba(wResCs.backgroundColor), wFoot) >= 3.0,
         "CON-102: the Restore control is distinguishable from the footer behind it (" + _f(_cr(_rgba(wResCs.backgroundColor), wFoot)) + ":1, 3:1 non-text bar)");
      ok(_cr(_rgba(wResCs.backgroundColor), _rgba(getComputedStyle(wBoBtn).backgroundColor)) >= 3.0,
         "CON-102: Restore is distinguishable from the BLACKOUT button beside it — the way back must not read as another way in");
      // (c) Restore is ONE-WAY. A toggle here would re-black the output on a double-press, so
      // assert the ARGUMENT, twice — a single click passing proves nothing about a toggle.
      var wBn = window.__calls.filter(function(c){ return c.cmd === "blackout"; }).length;
      wRes.click();
      ok(await wWait(function(){ return window.__calls.filter(function(c){ return c.cmd === "blackout"; }).length > wBn; }),
         "CON-102 (setup): Restore issues the blackout command");
      var wLast = window.__calls.filter(function(c){ return c.cmd === "blackout"; }).pop();
      ok(wLast.args && wLast.args.on === false, "CON-102: Restore sends blackout{on:false} — it restores, never toggles");
      ok(await wWait(function(){ return wExp.hidden; }), "CON-102: restoring clears the engaged state");
      ok(document.activeElement === wBoBtn,
         "CON-102: focus lands on the BLACKOUT button after Restore disappears, not on <body> (WCAG 2.4.3)");
      // Press it again while output is already live: it must STILL mean restore, never re-black.
      wRes.hidden = false; // reachable only in the engaged state, but prove the handler is one-way
      wRes.click();
      ok(await wWait(function(){ var l = window.__calls.filter(function(c){ return c.cmd === "blackout"; }).pop(); return l && l.args.on === false; }),
         "CON-102: a second activation still sends on:false — the control is not a disguised toggle");
      ok(!el("blackout-explain") || el("blackout-explain").hidden,
         "CON-102: the audience is NOT re-blacked by pressing Restore twice");

      // --- §10 case 5: the emergency-ready chip is the canonical frame's PILL --------------
      // Asserting the declared radius alone would pass on an element nobody paints, and "999px"
      // is a string, not a shape. Measure it against the element's REAL rendered height instead:
      // a pill is radius >= half the height, whatever the number says.
      var wRdy = document.querySelector(".emergency-ready");
      ok(!!wRdy && wRdy.getClientRects().length > 0,
         "\u00a710 case 5 (positive control): the Offline-ready chip is actually painted, so its shape can be measured");
      if (wRdy) {
        var wRdyH = wRdy.getBoundingClientRect().height;
        var wRdyR = parseFloat(getComputedStyle(wRdy).borderTopLeftRadius);
        ok(wRdyH > 0 && wRdyR >= wRdyH / 2,
           "\u00a710 case 5: the Offline-ready chip is a PILL — radius " + wRdyR.toFixed(1) + "px >= half its " + wRdyH.toFixed(1) + "px height (canonical frame 312:151; was 10px)");
      }

      // ===================================================================================
      // SYSTEM & RECOVERY STATES (Design 2.0 Frame G, node 346:124) + the honest pill.
      //
      // What these checks defend, in one line: ABSENT TELEMETRY IS UNKNOWN, NEVER A FAULT AND
      // NEVER HEALTHY. Every state below therefore ships with a negative control, because
      // "the banner appeared" proves nothing unless "it stays away when it should" also holds.
      //
      // The edge checks are the load-bearing ones. The console polls at 1 Hz with NO health
      // event channel, so a hold that begins AND ends between two polls reads `held:false` in
      // both samples. Reading the counters as LEVELS would miss it entirely; only a delta
      // against the previous poll sees it. Those checks drive two real polls to prove it.
      // ===================================================================================
      var gPoll = function(pred){ return waitFor(pred, 120); };   // past the 1s poll, virtual
      // Count completed view polls. `gPoll(function(){ return true; })` does NOT wait — waitFor
      // returns immediately on an already-true predicate — so anything that must observe a real
      // poll (every edge check does, by definition) waits on THIS instead.
      var gViews = function(){
        var n = 0;
        for (var i = 0; i < window.__calls.length; i++) if (window.__calls[i].cmd === "view") n++;
        return n;
      };
      var gTicks = function(n){ var t = gViews(); return waitFor(function(){ return gViews() >= t + n; }, 200); };
      var gTx = function(id){ var e = el(id); return e ? e.textContent.replace(/\s+/g," ").trim() : ""; };
      // Painted = COMPUTED display + a real client rect. Never `.hidden` and never DOM
      // presence: a class `display` rule defeats the [hidden] attribute in this webview.
      var gOn = function(id){
        var e = el(id);
        return !!e && getComputedStyle(e).display !== "none" && e.getClientRects().length > 0;
      };

      document.querySelector('.nav-item[data-surface="console"]').click();
      await gPoll(function(){ return el("surface-console").classList.contains("active"); });

      // ---- resting state -------------------------------------------------------------
      ok(!!el("recovery"), "Frame G: the recovery region exists in the console");
      ok(!gOn("recovery"),
         "Frame G (control): with a healthy host NOTHING is painted — the region stays out of the way, so every 'it appeared' below means something");

      // ---- G.5 session recovery ------------------------------------------------------
      V.session = {restored:true};
      await gPoll(function(){ return gOn("rcv-session"); });
      ok(gOn("rcv-session"), "G.5: session.restored paints the recovery notice (computed display)");
      var gS = gTx("rcv-session-title") + " " + gTx("rcv-session-text");
      ok(/restored/i.test(gS), "G.5: it says the session was restored (\"" + gS.slice(0,60) + "\")");
      ok(!/unexpectedly|crashed/i.test(gS),
         "G.5: it does NOT claim a crash — `restored` means crash OR restart, and a clean exit also saves a session, so 'closed unexpectedly' would be false after an ordinary relaunch");
      ok(!/Start fresh|Restore session/i.test(gTx("rcv-session")),
         "G.5: no Restore/Start-fresh buttons — the host already restored before this rendered and NO command exists to undo it, so the frame's choice dialog would be two buttons that cannot act");

      // The crash-loop case is the one where "started clean" would read as data loss.
      V.session = {crash_loop:true, rapid_launches:4};
      await gPoll(function(){ return /clean/i.test(gTx("rcv-session-title")); });
      var gL = gTx("rcv-session-title") + " " + gTx("rcv-session-text");
      ok(/clean/i.test(gL) && /4/.test(gL), "G.5: the crash-loop breaker is reported with its real launch count (\"" + gL.slice(0,64) + "\")");
      ok(/preserved/i.test(gL),
         "G.5: it says the previous session is PRESERVED — the breaker skips it, never deletes it, and omitting that reads as data loss");

      // Storage: checkpoints paused is about SAVING, and must not imply the audience is affected.
      V.session = {restored:true}; V.storage = {status:"critical", checkpoints_paused:true};
      await gPoll(function(){ return gOn("rcv-session-chip"); });
      ok(gOn("rcv-session-chip") && /checkpoint/i.test(gTx("rcv-session-chip")),
         "G.5: checkpoints_paused surfaces as a chip (\"" + gTx("rcv-session-chip").slice(0,52) + "\")");
      // The host's OWN reason, not a generic failure.
      V.session = {restored:true, autosave_error:"disk quota exceeded"};
      await gPoll(function(){ return /quota/i.test(gTx("rcv-session-chip")); });
      ok(/disk quota exceeded/.test(gTx("rcv-session-chip")),
         "G.5: an autosave failure shows the HOST'S reason, not a generic 'something went wrong'");

      el("rcv-session-x").click();
      ok(!gOn("rcv-session"), "G.5: the notice is dismissible — an informational banner must not hold console space for a whole service");
      ok(!gOn("recovery"), "G.5: dismissing the only live state hides the whole region too");

      V.session = null; V.storage = null;
      await gPoll(function(){ return !gOn("rcv-session"); });
      ok(!gOn("rcv-session"),
         "G.5 (control): session:null paints NOTHING — a host that does not report session health is UNKNOWN, not a host with a healthy session and not one with a fault");

      // ---- G.2 control-link loss + the pill ------------------------------------------
      ok(!gOn("rcv-link"), "G.2 (control): a healthy link paints no banner");
      ok(gTx("conn-label") === "Connected", "pill (control): a real connected link reads Connected");

      window.__link = {state:"disconnected", epoch:1, attempts:0, last_error:"connection closed"};
      await gPoll(function(){ return gOn("rcv-link"); });
      ok(gOn("rcv-link"), "G.2: a dropped link paints the banner");
      var gK = gTx("rcv-link");
      ok(!/reconnecting/i.test(gK),
         "G.2: it does NOT say 'Reconnecting' — build_backend() runs once and nothing re-dials, so claiming a retry is the exact fabrication this seam removes");
      ok(/host keeps presenting|unaffected/i.test(gK),
         "G.2: it states the thing the operator needs under pressure — the host keeps presenting (\"" + gK.slice(0,64) + "\")");
      ok(!/mobile remote/i.test(gK),
         "G.2: it does NOT claim 'Mobile remotes are paused' — no seam reports LAN controller peers, so the frame's line would be a fabrication through a truthful-looking surface");
      ok(gTx("conn-label") === "Host unreachable",
         "pill: a dropped link reads 'Host unreachable', not 'Connected' and not 'Reconnecting…' (\"" + gTx("conn-label") + "\")");
      ok(el("conn-pill").classList.contains("down") && !el("conn-pill").classList.contains("reconnecting"),
         "pill: the dropped state is red, and is NOT the amber reconnecting state");

      // `local` is the fabrication that mattered most: green for the ABSENCE of a failure path.
      window.__link = {state:"local", epoch:0, attempts:0, last_error:null};
      await gPoll(function(){ return gTx("conn-label") === "Local"; });
      ok(gTx("conn-label") === "Local",
         "pill: the stand-alone backend says 'Local' — it has no host and wants none");
      ok(!el("conn-pill").classList.contains("down"),
         "pill: 'local' is NEUTRAL, not an error — no link is wanted, so it is not a failure");
      var gPc = getComputedStyle(el("conn-pill")).color;
      var gGreen = getComputedStyle(document.documentElement).getPropertyValue("--sc-preview").trim();
      ok(_cr(_rgba(gPc), _rgba(getComputedStyle(el("conn-pill")).backgroundColor)) >= 4.5,
         "pill: the Local label clears AA-NORMAL on its own ground (" + _f(_cr(_rgba(gPc), _rgba(getComputedStyle(el("conn-pill")).backgroundColor))) + ":1)");
      ok(!gOn("rcv-link"),
         "G.2 (control): 'local' paints NO banner — a console with no host link is healthy, not disconnected");

      window.__link = {state:"connected", epoch:1, attempts:0, last_error:null};
      await gPoll(function(){ return gTx("conn-label") === "Connected"; });
      ok(gTx("conn-label") === "Connected" && !gOn("rcv-link"),
         "pill (positive control): the pill and banner both recover when the link does — so 'it went red' above was the state changing, not a dead mechanism");

      // ---- G.3 output signal lost + the never-blank hold ------------------------------
      ok(!gOn("rcv-output"),
         "G.3 (control): an assigned output with NO `signal` reported paints nothing — absent telemetry is UNKNOWN, which is exactly the `else -> NO SIGNAL` bug this replaces");

      V.outputs = [{role:"stage", assigned:true, assigned_key:"d2", display:"Stage Display", width:1920, height:1080, signal:"no_signal"},
                   {role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080, signal:"healthy"}];
      await gPoll(function(){ return gOn("rcv-output"); });
      ok(gOn("rcv-output"), "G.3: a reported no_signal on an ASSIGNED output paints the card");
      ok(gTx("rcv-output-pill-label") === "SIGNAL LOST", "G.3: the pill reads SIGNAL LOST");
      var gO = gTx("rcv-output-text");
      ok(/Stage Display/.test(gO),
         "G.3: it names the output the HOST reported, not the frame's invented 'HDMI-2' (\"" + gO.slice(0,56) + "\")");
      ok(!/HDMI/i.test(gO), "G.3: no invented connector name — no seam carries a display identity for a lost output");
      ok(/Other outputs are unaffected/i.test(gO),
         "G.3: isolation is asserted FROM DATA — the sibling output really does report healthy");
      ok(!/attempt|∞/i.test(gTx("rcv-output")),
         "G.3: no 'attempt 2 of ∞' — retries are bounded by contract and unbounded counters contradict it");
      ok(gOn("rcv-output-reattach") && /automatically/i.test(gTx("rcv-output-reattach")),
         "G.3: it states FR-041's real guarantee — content reattaches automatically on reconnect");
      ok(!gOn("rcv-output-held"),
         "G.3 (control): with held:false the held-frame line is NOT painted, so its appearance below means the host really reported a hold");

      // The isolation claim must disappear when it stops being true.
      V.outputs = [{role:"stage", assigned:true, assigned_key:"d2", display:"Stage Display", width:1920, height:1080, signal:"no_signal"}];
      await gPoll(function(){ return !/Other outputs/i.test(gTx("rcv-output-text")); });
      ok(!/Other outputs are unaffected/i.test(gTx("rcv-output-text")),
         "G.3: with no healthy sibling the isolation sentence is DROPPED — it is asserted from data, never printed as boilerplate");

      V.output_health = {held:true, fault:"gpu_device_lost", holds:1};
      await gPoll(function(){ return gOn("rcv-output-held"); });
      var gH = gTx("rcv-output-held");
      ok(gOn("rcv-output-held"), "G.3: held:true paints the never-blank explanation");
      ok(/still sees content|holding its last good frame/i.test(gH),
         "G.3: it is worded as the GUARANTEE WORKING — 'output held (audience unaffected)' is accurate, 'output failed' is not (\"" + gH.slice(0,56) + "\")");
      ok(!/failed|failure/i.test(gH), "G.3: it never calls the never-blank guarantee a failure");

      // Everything healthy again -> the region must retract on its own. Placed HERE, before any
      // recovery is announced, so it does not have to wait out the confirmation's 8s window.
      V.output_health = {held:false}; V.session = null; V.storage = null;
      V.outputs = [{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080, signal:"healthy"}];
      await gPoll(function(){ return !gOn("recovery"); });
      ok(!gOn("recovery"),
         "Frame G: with every seam healthy again the whole region retracts (positive control for the region itself — it is not simply stuck open)");

      // ---- G.3 recovery: EDGES ACROSS POLLS, NOT LEVELS ------------------------------
      // These assert the EDGE (an announcement fired), not the card's visibility. The
      // confirmation is a transient whose 8s window deliberately outlives the moment it
      // fired, so "is it on screen?" cannot tell a NEW edge from the previous one still
      // showing — and a test that cannot tell those apart would pass on a broken edge.
      var gAnn = function(){ return window.__rcvAnnounced(); };

      V.outputs = [{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080, signal:"healthy"}];
      // Go UNKNOWN first so the next sample is genuinely a FIRST observation. (Without this the
      // baseline from the checks above is still live, and 1 -> 3 is a real delta of 3.)
      V.output_health = null;
      await gTicks(2);
      var gA0 = gAnn();
      V.output_health = {held:false, holds:3, recoveries:3};
      await gTicks(2);
      ok(gAnn() === gA0,
         "G.3 EDGE (control): a FIRST observation carrying recoveries:3 announces NOTHING — a non-zero counter is a level, not an event; baselining it is the whole point (announcements " + gA0 + " -> " + gAnn() + ")");

      var gA1 = gAnn();
      V.output_health = {held:false, holds:4, recoveries:4};
      await gPoll(function(){ return gAnn() > gA1; });
      ok(gAnn() === gA1 + 1,
         "G.3 EDGE: recoveries incrementing between two polls announces EXACTLY ONE recovery — THE case `held` cannot see, because a hold that begins and ends between polls reads false in both samples");
      ok(gOn("rcv-recovered") && /recovered/i.test(gTx("rcv-recovered-text")),
         "G.3 EDGE: the confirmation is actually painted (\"" + gTx("rcv-recovered-text").slice(0,52) + "\")");

      // Re-polling the SAME counters is not a new event.
      var gA2 = gAnn();
      await gTicks(2);
      ok(gAnn() === gA2,
         "G.3 EDGE (control): polling again with UNCHANGED counters announces nothing — otherwise every poll would re-announce the same recovery forever");

      // A counter going DOWN is a new host/session, not a recovery.
      var gA3 = gAnn();
      V.output_health = {held:false, holds:1, recoveries:1};
      await gTicks(2);
      ok(gAnn() === gA3,
         "G.3 EDGE: counters DECREASING announces nothing — both are monotonic and saturating, so a decrease means a new host/session, never a recovery (announcements " + gA3 + " -> " + gAnn() + ")");

      // ...and the re-baseline must be the NEW low value, not the old high one: climbing back
      // to 2 is one recovery, not a replay of the gap.
      var gA4 = gAnn();
      V.output_health = {held:false, holds:2, recoveries:2};
      await gPoll(function(){ return gAnn() > gA4; });
      ok(gAnn() === gA4 + 1 && /recovered — /i.test(gTx("rcv-recovered-text")),
         "G.3 EDGE: after a decrease the baseline is the NEW value — climbing 1 -> 2 announces ONE recovery, not a replay (\"" + gTx("rcv-recovered-text").slice(0,44) + "\")");

      // Unknown health must drop the baseline, or the next known sample fakes a huge delta.
      var gA5 = gAnn();
      V.output_health = null;
      await gTicks(2);
      V.output_health = {held:false, holds:9, recoveries:9};
      await gTicks(2);
      ok(gAnn() === gA5,
         "G.3 EDGE: after output_health goes UNKNOWN the baseline is DROPPED, so the next known sample re-baselines instead of reading as a 7-recovery delta (announcements " + gA5 + " -> " + gAnn() + ")");

      V.output_health = {held:false}; V.session = null; V.storage = null;
      V.outputs = [{role:"main", assigned:true, assigned_key:"d1", display:"Main", width:1920, height:1080, signal:"healthy"}];

      // ---- G.6 missing-media fallback (347:165) --------------------------------------
      // The inspector already NAMED a missing file. What it never said is the only thing that
      // matters mid-service: what the AUDIENCE is seeing. FR-070 guarantees a safe placeholder
      // and never a black screen, and the rasterizer already honours it — so the console does
      // not synthesize a fallback, it explains the one that exists.
      //
      // Driven entirely through the app's OWN commands (add image -> go missing -> refresh) so
      // the fixture and the editor can never disagree about which deck is open. The negative
      // control is therefore the SAME element before it goes missing, which is stronger than a
      // different element that happens to be fine.
      document.querySelector('.nav-item[data-surface="presentation"]').click();
      await waitFor(function(){ return el("surface-presentation").classList.contains("active"); }, 200);
      // Navigating to the surface lands on the LIBRARY, not the editor, and the grid renders
      // asynchronously — so a one-shot "is the grid hidden?" test can run before it exists and
      // silently skip the Edit click, leaving every later check measuring a display:none subtree.
      var gBody = function(){ return getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display; };
      await waitFor(function(){ return gBody() !== "none" || (el("pm-grid-edit") && !el("pm-grid").hidden); }, 200);
      if (gBody() === "none" && el("pm-grid-edit")) el("pm-grid-edit").click();
      await waitFor(function(){ return gBody() !== "none"; }, 200);
      ok(gBody() !== "none", "G.6 (setup): the deck editor is open, so the inspector checks measure a painted subtree");
      if (el("pm-tab-inspector")) el("pm-tab-inspector").click();
      document.querySelector('#surface-presentation .pm-tool[data-add="image"]').click();
      await waitFor(function(){ return window.__calls.some(function(c){ return c.cmd === "deck_add_image_element"; }); }, 200);
      await waitFor(function(){ return /image/i.test(el("pm-inspector-body").textContent); }, 200);
      ok(/image/i.test(el("pm-inspector-body").textContent),
         "G.6 (setup): an image element is selected in the inspector, so the missing state has something real to attach to");
      ok(!document.querySelector(".pm-insp-miss"),
         "G.6 (control): a PRESENT asset paints no missing-media explanation — the same element, before it goes missing");

      // Take it missing at the host, exactly as a deleted file would, then let the app refresh
      // through its own round-trip (the eye toggle returns a fresh DeckView; toggled twice so
      // visibility ends where it started and only `missing` differs).
      var gIx = D.slide.elements.length - 1;
      D.slide.elements[gIx].missing = true;
      D.slide.elements[gIx].name = "Harvest field.jpg";
      var gEye = document.querySelector("#pm-layers .td-layer.sel .td-layer-eye") || document.querySelector("#pm-layers .td-layer-eye");
      ok(!!gEye, "G.6 (setup): the layer row exposes a visibility control to drive a real host refresh");
      if (gEye) {
        gEye.click();
        await waitFor(function(){ return !!document.querySelector(".pm-insp-miss"); }, 200);
        var gEye2 = document.querySelector("#pm-layers .td-layer.sel .td-layer-eye") || document.querySelector("#pm-layers .td-layer-eye");
        if (gEye2) gEye2.click();
        await waitFor(function(){ return !!document.querySelector(".pm-insp-miss"); }, 200);
        // Re-assert the Inspector tab: the rect check below is meaningless if an ANCESTOR is
        // display:none, and an element's own computed display stays "block" in that case — so
        // without this the check could pass on an invisible panel or fail on a correct one.
        if (el("pm-tab-inspector")) el("pm-tab-inspector").click();
        await waitFor(function(){
          var m = document.querySelector(".pm-insp-miss");
          return !!m && m.getClientRects().length > 0;
        }, 200);
        var gMiss = document.querySelector(".pm-insp-miss");
        var gDbg = "surface=" + el("surface-presentation").classList.contains("active")
          + " pmBody=" + getComputedStyle(document.querySelector("#surface-presentation .pm-body")).display
          + " inspHidden=" + (el("pm-inspector-body") ? el("pm-inspector-body").hidden : "n/a")
          + " inspDisp=" + (el("pm-inspector-body") ? getComputedStyle(el("pm-inspector-body")).display : "n/a")
          + " missDisp=" + (gMiss ? getComputedStyle(gMiss).display : "n/a")
          + " rects=" + (gMiss ? gMiss.getClientRects().length : "n/a");
        ok(!!gMiss && getComputedStyle(gMiss).display !== "none" && gMiss.getClientRects().length > 0,
           "G.6: a missing image paints the fallback explanation (computed display + a real rect) [" + gDbg + "]");
        var gMt = gMiss ? gMiss.textContent.replace(/\s+/g, " ").trim() : "";
        ok(/audience/i.test(gMt) && /background/i.test(gMt),
           "G.6: it says what the AUDIENCE sees — the slide composes without the asset (\"" + gMt.slice(0, 58) + "\")");
        ok(/never an error/i.test(gMt),
           "G.6: it states FR-070's guarantee explicitly rather than leaving the operator to fear a black screen");
        ok(/re-push/i.test(gMt) && /on air/i.test(gMt),
           "G.6: it warns that repairing the DECK does not repair what is already ON AIR — deck repairs route through with_deck and never present (FR-012)");
        ok(gMiss && gMiss.getAttribute("role") === "status",
           "G.6: the explanation is announced to assistive tech, not a silent visual-only cue");
        var gMc = _cr(_rgba(getComputedStyle(gMiss).color), _rgba(getComputedStyle(gMiss).backgroundColor));
        ok(gMc >= 4.5,
           "G.6: the explanation clears AA-NORMAL on its own warn ground (" + _f(gMc) + ":1) — essential copy, so --sc-text-secondary not the AA-large-only --sc-text-muted");
        ok(/Relink/i.test(el("pm-inspector-body").textContent),
           "G.6: the repair affordance is offered and reads 'Relink…' for a missing asset, not the generic 'Replace…'");
      }

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
    else if (tries>300){ clearInterval(iv); el("__r").textContent="RESULTS\nFAIL: app never booted\nDONE(1)"; }
  }, 30);
</script>
"""

# Inject the stub into <head> (before app.js runs) and the driver before </body>.
# The <base> MUST precede the <link rel=stylesheet href="app.css"> (line ~7) — a <base>
# only affects relative URLs that come AFTER it, so injecting it at </head> left app.css
# resolving against the /tmp temp file (never loading). Inject it right after <head> so the
# real app.css (and app.js) load and CSS-dependent checks are meaningful.
html = html.replace("<head>", '<head><base href="file://' + DIST + '/">', 1)
html = html.replace("</head>", STUB + CSS_SRC + "</head>", 1)
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
             # Budget is VIRTUAL time, fast-forwarded — it costs little wall clock, but every
             # driver step that waits on the app's own 1 s view poll spends a full second of it.
             # Raised from 9000 with the window-semantics checks, which wait on two real polls, and
             # again to 20000 with the Design 2.0 parity block: that block navigates surfaces and
             # waits on host round-trips at the very end of the run, so a run in which several of
             # its checks legitimately FAIL (each spending its wait budget) must still have time
             # left to WRITE the results. Without the headroom a real regression surfaces as
             # "NO RESULTS BLOCK" (exit 2, infra) instead of a named FAIL.
             # Raised again to 60000 for the Frame G recovery block, which is wait-heavy by
             # nature: every edge check must observe TWO successive 1 Hz polls (that is the
             # whole point of holds/recoveries being counters), so it spends ~1s of virtual
             # time per assertion pair and cannot be made cheaper without testing something
             # weaker than the real poll path.
             "--virtual-time-budget=60000", "--dump-dom", "file://" + path],
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
