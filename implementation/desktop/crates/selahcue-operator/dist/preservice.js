// Pre-service Check surface (Design 2.0, Figma 344:124 — story 86ajp0az9, FR-007/008/070). A
// readiness checklist over Displays & Outputs / Media / Audio / Storage-Network-Providers, plus a
// Readiness sidebar (verdict dial · passed/warnings/blocking · review cards · Start / Re-run).
//
// DATA: derived from LIVE host data over the existing Tauri commands — `view` (OutputStatusView:
// display/resolution/fps/dropped_frames/signal + screens' NDI config), `remote_snapshot` (paired
// device count), `deck_view` (open-deck missing-media count), and `disk_free` (volume free bytes).
// Checks whose data the host does NOT yet expose (audio device/levels, on-device STT-ready, AI
// consent, motion-background cache, live-encoder telemetry) render an HONEST "not checked yet"
// state — never a fabricated value (per the project's never-invent-facts rule). Nav + ⌘⇧K live in
// app.js; this module owns the surface body and is loaded after app.js.
(function () {
  "use strict";
  var root = document.getElementById("surface-preservice");
  if (!root) return;

  // Tauri IPC (absent when opened outside the shell — every check then reads "not checked").
  var INVOKE =
    (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) || null;
  function invoke(cmd, args) {
    if (!INVOKE) return Promise.reject(new Error("no host connection"));
    return INVOKE(cmd, args || {});
  }

  // Last-fetched host data + run bookkeeping. `hostConnected` = the operator is driving a REAL
  // output window (not the stand-alone demo) — the gate that stops the surface reporting readiness
  // (or "network up") when there is no audience output at all.
  var data = { view: null, remote: null, deck: null, disk: null, hostConnected: false, lastCheckedAt: 0 };
  var ticker = null;
  var tickCount = 0;
  var running = false;

  // ---------- helpers ----------
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }
  function announce(msg) {
    var live = document.getElementById("ps-live");
    if (!live) return;
    // Clear then re-populate so assistive tech registers a change even when the message text is
    // identical to the previous run (e.g. re-running with an unchanged verdict).
    live.textContent = "";
    window.setTimeout(function () { live.textContent = msg; }, 30);
  }
  function gbLabel(bytes) {
    if (!bytes || bytes <= 0) return null;
    var gb = bytes / 1073741824;
    return (gb >= 100 ? Math.round(gb) : Math.round(gb * 10) / 10) + " GB";
  }
  var STAGE_LABEL = {
    worship: "Current + Next + Timer",
    scripture: "Scripture + reference",
    "timer-only": "Timer only",
  };
  // Disk thresholds (bytes): mirror the host guard's spirit (Critical < 1 GB, Low < 5 GB).
  var DISK_CRITICAL = 1073741824;
  var DISK_LOW = 5 * 1073741824;
  var PENDING_LATER = "Not checked yet — arriving in a later slice.";

  function outputByRole(role) {
    var outs = (data.view && data.view.outputs) || [];
    for (var i = 0; i < outs.length; i++) if (outs[i].role === role) return outs[i];
    return null;
  }

  // A check → { state:'ok'|'warn'|'block'|'pending', title, detail, action?:{label, surface} }.
  // Deriving each honestly from real host data; unavailable data yields 'pending', never a guess.
  function checkMainOutput() {
    var o = outputByRole("main");
    var c = { title: "Audience — Main" };
    if (!o) { c.state = "pending"; c.detail = "No output window connected"; return c; }
    var res = o.width && o.height ? o.width + "×" + o.height : "—";
    var fps = o.fps != null ? " · " + o.fps + "fps" : "";
    if (o.signal === "no_signal") { c.state = "block"; c.detail = "No signal — no display attached"; c.action = { label: "Details", surface: "screens" }; return c; }
    if (o.signal === "degraded") { c.state = "warn"; c.detail = "Frame drops detected · " + res + fps; c.action = { label: "Details", surface: "screens" }; return c; }
    if (o.signal === "healthy") { c.state = "ok"; c.detail = "Connected · " + res + fps; return c; }
    // Unmeasured signal: honest — assigned but health unknown (older/non-desktop host).
    if (o.display || o.assigned) { c.state = "ok"; c.detail = (o.display ? "Connected" : "Assigned") + " · " + res; return c; }
    c.state = "block"; c.detail = "No display assigned"; c.action = { label: "Details", surface: "screens" };
    return c;
  }
  function checkStageOutput() {
    var o = outputByRole("stage");
    var c = { title: "Stage Display" };
    var layers = data.view ? STAGE_LABEL[data.view.stage_template] || "Current + Next + Timer" : null;
    if (!o) { c.state = "pending"; c.detail = "No output window connected"; return c; }
    if (o.signal === "no_signal" || (!o.display && !o.assigned)) { c.state = "pending"; c.detail = "Stage display not set up (optional)"; return c; }
    if (o.signal === "degraded") { c.state = "warn"; c.detail = "Frame drops on the stage output"; c.action = { label: "Details", surface: "screens" }; return c; }
    c.state = "ok"; c.detail = "Connected · " + (layers || "stage output");
    return c;
  }
  function checkLivestream() {
    var screens = (data.view && data.view.screens) || [];
    var ndi = null;
    for (var i = 0; i < screens.length; i++) {
      var cfg = screens[i].config || {};
      if (cfg.ndi_enabled) { ndi = screens[i]; break; }
    }
    var c = { title: "Livestream Program" };
    if (!data.view) { c.state = "pending"; c.detail = "No output window connected"; return c; }
    if (!ndi) { c.state = "pending"; c.detail = "NDI output is off — enable it in Screens to stream"; c.action = { label: "Screens", surface: "screens" }; return c; }
    // NDI is configured/on. Live encoder frame-drop telemetry is not exposed yet (honest note).
    c.state = "ok"; c.detail = "NDI output on · " + ((ndi.config && ndi.config.ndi_name) || "SelahCue Program");
    return c;
  }
  function checkSlideMedia() {
    var media = data.deck && data.deck.media;
    var c = { title: "Slide media present" };
    if (!media) { c.state = "pending"; c.detail = "No deck open — open a presentation to check its media"; return c; }
    var total = (media.assets && media.assets.length) || 0;
    var missing = media.missing_count || 0;
    if (missing > 0) {
      c.state = "warn";
      c.detail = missing + (missing === 1 ? " file missing" : " files missing") + " — those slides will be blank";
      c.action = { label: "Locate", surface: "presentation" };
      return c;
    }
    c.state = "ok"; c.detail = total > 0 ? "All present · " + total + (total === 1 ? " file" : " files") : "No linked media";
    return c;
  }
  function checkMotionCache() {
    return { state: "pending", title: "Motion backgrounds cached", detail: PENDING_LATER };
  }
  function checkAudioDevice() {
    return { state: "pending", title: "Input device", detail: "Audio-device check — " + PENDING_LATER.toLowerCase() };
  }
  function checkAudioLevels() {
    return { state: "pending", title: "Signal levels", detail: "Signal-level metering — " + PENDING_LATER.toLowerCase() };
  }
  function checkDisk() {
    var c = { title: "Disk space" };
    var free = data.disk && data.disk.available_bytes;
    if (!data.disk || !free) { c.state = "pending"; c.detail = "Couldn't read free space on this machine"; return c; }
    var label = gbLabel(free);
    if (free < DISK_CRITICAL) { c.state = "block"; c.detail = "Almost full · " + label + " free — free up space before starting"; return c; }
    if (free < DISK_LOW) { c.state = "warn"; c.detail = "Low · " + label + " free"; return c; }
    c.state = "ok"; c.detail = label + " free · autosave on";
    return c;
  }
  function checkNetworkRemotes() {
    var c = { title: "Local network & remotes" };
    // Only claim "Network up" when a REAL output window is connected: the demo/Local backend
    // resolves remote_snapshot with an empty list that is indistinguishable from a real host with
    // zero remotes, so gating on hostConnected avoids fabricating a green pass (never-invent-facts).
    if (!data.hostConnected || !data.remote) { c.state = "pending"; c.detail = "No output window connected — remotes not checked"; c.action = { label: "Remote", surface: "remote" }; return c; }
    var n = (data.remote.devices && data.remote.devices.length) || 0;
    c.state = "ok";
    c.detail = "Network up · " + (n === 0 ? "no remotes paired" : n + (n === 1 ? " remote paired" : " remotes paired"));
    return c;
  }
  function checkTranscriptionAi() {
    return { state: "pending", title: "Transcription & AI", detail: "On-device STT & AI consent — " + PENDING_LATER.toLowerCase() };
  }

  // Section model → grouped checks, in the Figma order.
  function buildSections() {
    return [
      { title: "DISPLAYS & OUTPUTS", checks: [checkMainOutput(), checkStageOutput(), checkLivestream()] },
      { title: "MEDIA", checks: [checkSlideMedia(), checkMotionCache()] },
      { title: "AUDIO", checks: [checkAudioDevice(), checkAudioLevels()] },
      { title: "STORAGE, NETWORK & PROVIDERS", checks: [checkDisk(), checkNetworkRemotes(), checkTranscriptionAi()] },
    ];
  }

  // ---------- rendering ----------
  var GLYPH = { ok: "✓", warn: "!", block: "✕", pending: "…" };
  function setPill(node, n, kind) {
    if (!node) return;
    node.textContent = String(n);
    node.className = "ps-count-pill " + (n > 0 ? "ps-pill-" + kind : "ps-pill-zero");
  }
  function navTo(surface) {
    var nav = document.querySelector('.nav-item[data-surface="' + surface + '"]');
    if (nav) nav.click();
  }
  function renderCheckRow(chk) {
    var row = el("div", "ps-row");
    row.setAttribute("role", "listitem");
    var icon = el("div", "ps-ico ps-ico-" + chk.state);
    icon.appendChild(el("span", "ps-ico-glyph", GLYPH[chk.state] || "…"));
    icon.setAttribute("aria-hidden", "true");
    row.appendChild(icon);
    var body = el("div", "ps-row-body");
    body.appendChild(el("div", "ps-row-title", chk.title));
    body.appendChild(el("div", "ps-row-detail ps-detail-" + chk.state, chk.detail));
    row.appendChild(body);
    if (chk.action) {
      var btn = el("button", "ps-row-action", chk.action.label);
      btn.type = "button";
      btn.setAttribute("aria-label", chk.action.label + " — " + chk.title);
      btn.addEventListener("click", function () { navTo(chk.action.surface); });
      row.appendChild(btn);
    }
    // A concise SR summary of the row's status (the icon glyph is decorative).
    var stateWord = { ok: "OK", warn: "attention", block: "blocking", pending: "not checked" }[chk.state];
    row.setAttribute("aria-label", chk.title + " — " + stateWord + ". " + chk.detail);
    return row;
  }
  function renderSections(sections) {
    var host = document.getElementById("ps-sections");
    host.innerHTML = "";
    sections.forEach(function (sec) {
      var wrap = el("div", "ps-section");
      // A real <h2> (styled by .ps-section-h) so the visual section structure is also programmatic.
      wrap.appendChild(el("h2", "ps-section-h", sec.title));
      var card = el("div", "ps-card");
      card.setAttribute("role", "list");
      sec.checks.forEach(function (chk, i) {
        if (i > 0) {
          var div = el("div", "ps-divider");
          div.setAttribute("role", "presentation"); // a visual separator, not a list item
          card.appendChild(div);
        }
        card.appendChild(renderCheckRow(chk));
      });
      wrap.appendChild(card);
      host.appendChild(wrap);
    });
  }
  function renderReadiness(sections) {
    var all = [];
    sections.forEach(function (s) { s.checks.forEach(function (c) { all.push(c); }); });
    var passed = all.filter(function (c) { return c.state === "ok"; }).length;
    var warnings = all.filter(function (c) { return c.state === "warn"; }).length;
    var blocking = all.filter(function (c) { return c.state === "block"; }).length;
    var pending = all.filter(function (c) { return c.state === "pending"; }).length;

    // Count pills: colored when non-zero, neutral at zero (mirrors the design — 0 blocking reads
    // neutral, not alarming).
    setPill(document.getElementById("ps-passed"), passed, "ok");
    setPill(document.getElementById("ps-warnings"), warnings, "warn");
    setPill(document.getElementById("ps-blocking"), blocking, "block");

    // Verdict. Safety gate, in order:
    //  - No output window connected → NOT ready (the whole point is to verify the audience output;
    //    a green "Safe to start" with nothing connected would be dangerous). Start is disabled.
    //  - Any blocking check → "Not safe to start". Start disabled.
    //  - Otherwise → "Safe to start", even with advisory warnings (mirrors the design). Start enabled.
    var card = document.getElementById("ps-verdict-card");
    var verdict = document.getElementById("ps-verdict");
    var summary = document.getElementById("ps-summary");
    var dialGlyph = document.querySelector("#ps-dial .ps-dial-glyph");
    var vstate, vtext, vglyph, ready;
    if (!data.hostConnected) { vstate = "pending"; vtext = "No output window"; vglyph = "…"; ready = false; }
    else if (blocking > 0) { vstate = "block"; vtext = "Not safe to start"; vglyph = "✕"; ready = false; }
    else { vstate = "ok"; vtext = "Safe to start"; vglyph = "✓"; ready = true; }
    card.setAttribute("data-state", vstate);
    document.getElementById("ps-dial").setAttribute("data-state", vstate);
    verdict.textContent = vtext;
    if (dialGlyph) dialGlyph.textContent = vglyph;
    var parts = [passed + " checks passed", warnings + (warnings === 1 ? " warning" : " warnings"), blocking + " blocking"];
    summary.textContent = !data.hostConnected
      ? "Connect an output window to run the checks"
      : parts.join(" · ") + (pending ? " · " + pending + " not checked" : "");

    // Review cards: blocking first, then warnings.
    var review = document.getElementById("ps-review");
    review.innerHTML = "";
    var flagged = all.filter(function (c) { return c.state === "block"; }).concat(all.filter(function (c) { return c.state === "warn"; }));
    if (!flagged.length) {
      review.appendChild(el("p", "ps-review-empty", data.hostConnected ? "Nothing to review — all clear." : "Nothing to review yet."));
    } else {
      flagged.forEach(function (c) {
        var cardEl = el("div", "ps-review-card ps-review-" + c.state);
        cardEl.appendChild(el("span", "ps-review-mark", c.state === "block" ? "⛔" : "⚠"));
        var b = el("div", "ps-review-body");
        b.appendChild(el("div", "ps-review-title", c.title));
        b.appendChild(el("div", "ps-review-detail", c.detail));
        cardEl.appendChild(b);
        review.appendChild(cardEl);
      });
    }

    // Start service: offered only when READY (a real output window is connected AND nothing is
    // blocking). It navigates to the Live Console (the go-live workspace) — there is no separate
    // "start" host action; this is the honest entry point.
    var start = document.getElementById("ps-start");
    start.disabled = !ready;
    start.setAttribute("aria-disabled", ready ? "false" : "true");
    start.title = !data.hostConnected
      ? "Connect an output window first"
      : ready
        ? "Go to the Live Console"
        : "Resolve the blocking check before starting";

    updateLastChecked();
  }
  function updateLastChecked() {
    var lc = document.getElementById("ps-lastchecked");
    if (!lc) return;
    if (!data.lastCheckedAt) { lc.textContent = "Not checked yet"; return; }
    var secs = Math.max(0, Math.round((Date.now() - data.lastCheckedAt) / 1000));
    var rel = secs < 5 ? "just now" : secs < 60 ? secs + "s ago" : Math.floor(secs / 60) + " min ago";
    lc.textContent = "Last checked " + rel + " · re-runs automatically each service";
  }

  function render() {
    var sections = buildSections();
    renderSections(sections);
    renderReadiness(sections);
  }

  // ---------- run the checks (fetch host data, then render) ----------
  function runChecks() {
    if (running) return Promise.resolve();
    running = true;
    // Best-effort in parallel; each check degrades to "not checked" on its own rejection, so one
    // missing command never blanks the whole surface.
    return Promise.allSettled([
      invoke("view"),
      invoke("remote_snapshot"),
      invoke("deck_view"),
      invoke("disk_free"),
      invoke("host_connected"),
    ]).then(function (r) {
      data.view = r[0].status === "fulfilled" ? r[0].value : null;
      data.remote = r[1].status === "fulfilled" ? r[1].value : null;
      data.deck = r[2].status === "fulfilled" ? r[2].value : null;
      data.disk = r[3].status === "fulfilled" ? r[3].value : null;
      // host_connected returns a bool; treat only an explicit `true` as connected (an older host
      // without the command, or the demo, reads as not connected — the honest default).
      data.hostConnected = r[4].status === "fulfilled" && r[4].value === true;
      data.lastCheckedAt = Date.now();
      running = false;
      render();
    }).catch(function () {
      running = false;
      render();
    });
  }

  // ---------- init + bounded auto-refresh ----------
  // A single guarded 5s ticker: always refresh the relative "last checked" label; re-run the full
  // checks every ~15s, but ONLY while the surface is visible (no background work / no unbounded
  // growth). Re-run is the design's "re-runs automatically each service".
  function tick() {
    if (!root.classList.contains("active")) return;
    tickCount++;
    updateLastChecked();
    if (tickCount % 3 === 0) runChecks();
  }
  if (!ticker) ticker = setInterval(tick, 5000);

  var rerun = document.getElementById("ps-rerun");
  if (rerun) rerun.addEventListener("click", function () {
    runChecks().then(function () { announce("Pre-service checks re-run. " + document.getElementById("ps-verdict").textContent + "."); });
  });
  var start = document.getElementById("ps-start");
  if (start) start.addEventListener("click", function () { if (!start.disabled) navTo("console"); });

  // Render an initial neutral state so the surface is never blank before the first run.
  render();

  // Exposed for app.js's showSurface() activation hook (runs the checks on first open).
  window.psActivate = function () { tickCount = 0; runChecks(); };
})();
