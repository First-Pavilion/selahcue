// Settings → General surface (Design 2.0, Figma 577:126 — story 17tnw2axwet, closes SET-001
// from docs/design/DESIGN-2.0-PARITY-AUDIT-settings.md).
//
// HONESTY: checked every #[tauri::command] registered in selahcue-operator/src/main.rs's
// generate_handler! list — none of this page's designed controls (organisation identity,
// startup-surface preference, language/region, keyboard-shortcut remapping, an explicit
// reduce-motion override, update preferences, pre-service-check subsystem config) have a backend
// command or any client-side persistence (no localStorage use anywhere in dist/) to write to.
// Each renders as a real, focusable, DISABLED control with an honest "not saved yet" note —
// never a fake save, never a remap interaction with nothing behind it.
//
// What IS real on this page:
//   - "On launch, open to" names Live Console because that really is what index.html ships
//     (`#surface-console` carries the `active` class at rest, index.html:93) — not a guess.
//   - The keyboard-shortcuts table is read LIVE from the app's own `#shortcuts` overlay DOM
//     (the dialog `⌘K`/F10/etc. already opens), never a hand-typed second copy of that list —
//     a second copy is exactly how a real shortcut and this page's description of it drift apart.
//     The "Open the full shortcuts overlay" button reveals that same dialog for real.
//   - "Manage updates" and "Open Pre-service Check" are real navigations to pages that already
//     exist (About & Licensing, the Pre-service Check surface).
(function () {
  "use strict";
  var root = document.getElementById("set-page-general");
  if (!root) return;

  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  // ---------- Startup (STARTUP section) ----------
  // "Live Console" is marked selected because that is what this build actually does on launch
  // (index.html:93's #surface-console carries `active` at rest) — the other two are real,
  // reachable destinations, just not yet a SAVED preference.
  var STARTUP_OPTIONS = [
    { id: "console", title: "Live Console", desc: "Go straight to live cueing.", real: true },
    { id: "plan", title: "Last service plan", desc: "Reopen the plan you had loaded last." },
    { id: "preservice", title: "Pre-service Check", desc: "Run the readiness checklist before the console." },
  ];

  function startupRow(opt) {
    var row = el("div", "pp-radio-card set-inert" + (opt.real ? " sel" : ""));
    row.setAttribute("role", "radio");
    row.setAttribute("aria-checked", opt.real ? "true" : "false");
    row.setAttribute("aria-disabled", "true");
    var head = el("div", "pp-radio-head");
    var dot = el("span", "pp-radio-dot" + (opt.real ? " on" : ""));
    dot.setAttribute("aria-hidden", "true");
    head.appendChild(dot);
    var textcol = el("div", "pp-radio-textcol");
    textcol.appendChild(el("span", "pp-radio-title", opt.title));
    textcol.appendChild(el("span", "pp-radio-desc", opt.desc));
    head.appendChild(textcol);
    row.appendChild(head);
    return row;
  }

  function renderStartup() {
    var host = document.getElementById("gn-startup-list");
    if (!host) return;
    host.textContent = "";
    STARTUP_OPTIONS.forEach(function (opt) { host.appendChild(startupRow(opt)); });
  }

  // ---------- Keyboard shortcuts (read live from the app's own #shortcuts overlay) ----------
  function renderShortcuts() {
    var host = document.getElementById("gn-shortcuts-list");
    var overlay = document.getElementById("shortcuts");
    if (!host) return;
    host.textContent = "";
    var rows = overlay ? overlay.querySelectorAll(".sc-row") : [];
    if (!rows.length) {
      host.appendChild(el("p", "set-inert-note", "Couldn't read the shortcuts list."));
      return;
    }
    rows.forEach(function (r) {
      var dt = r.querySelector("dt"), dd = r.querySelector("dd");
      if (!dt || !dd) return;
      var row = el("div", "set-row");
      var left = el("div");
      left.appendChild(el("p", "set-row-t", dd.textContent.trim()));
      left.appendChild(el("p", "set-row-d", "Read-only in this build — remapping isn't available yet."));
      row.appendChild(left);
      // dt holds one or more <kbd> chips (e.g. "Esc" "Esc") — reproduce each verbatim, never
      // collapse a two-key chord into one string.
      var chips = el("span", "set-row-v");
      Array.prototype.forEach.call(dt.querySelectorAll("kbd"), function (k, i) {
        if (i > 0) chips.appendChild(document.createTextNode(" "));
        chips.appendChild(el("kbd", null, k.textContent));
      });
      if (!chips.childNodes.length) chips.textContent = dt.textContent.trim();
      row.appendChild(chips);
      host.appendChild(row);
    });
  }

  // ---------- Pre-service check subsystems ----------
  // The real Pre-service Check surface's own four sections, verbatim from preservice.js's
  // buildSections() (its literal title strings, "in the Figma order" per that function's own
  // comment) — not a claim about a per-subsystem enable/disable switch, since no such switch
  // exists anywhere in this app. A prior version of this list invented a "Pairing" item that
  // isn't a real distinct check and omitted "Displays & Outputs" — arguably the most
  // safety-critical section — entirely (Cody + Quinn's independent review findings on PR #70,
  // ClickUp 17tnw2axwgt). Purely informational; the "not saved yet" framing lives once, in the
  // section's own lead paragraph above this list.
  var PRESERVICE_SUBSYSTEMS = [
    "Displays & Outputs — main, stage, and livestream program outputs.",
    "Media — slide media presence and motion-background caching.",
    "Audio — input device and signal levels.",
    "Storage, Network & Providers — disk space, LAN/remotes, and transcription & AI readiness.",
  ];

  function renderPreserviceList() {
    var host = document.getElementById("gn-preservice-list");
    if (!host) return;
    host.textContent = "";
    PRESERVICE_SUBSYSTEMS.forEach(function (label) {
      var parts = label.split(" — ");
      var row = el("div", "set-row");
      var left = el("div");
      left.appendChild(el("p", "set-row-t", parts[0]));
      if (parts[1]) left.appendChild(el("p", "set-row-d", parts[1]));
      row.appendChild(left);
      host.appendChild(row);
    });
  }

  window.settingsGeneralActivate = function () {
    renderStartup();
    renderShortcuts();
    renderPreserviceList();
    // "Open the full shortcuts overlay" is wired generically by app.js's own
    // `document.querySelectorAll("[data-open]")` handler (data-open="shortcuts" on the button in
    // index.html) — it calls the REAL openShortcuts(), which moves focus into the dialog and
    // enables its Tab-trap, exactly like every other way to open this same dialog. A prior version
    // of this file set `overlay.hidden = false` directly, which opened the dialog visually but
    // left keyboard focus behind it, outside the aria-modal="true" region (Cody's review of
    // PR #70). No JS needed here now — removing the bespoke handler is the fix.
    var manageUpdates = document.getElementById("gn-manage-updates");
    if (manageUpdates && !manageUpdates.dataset.wired) {
      manageUpdates.dataset.wired = "1";
      manageUpdates.addEventListener("click", function () {
        if (typeof setSettingsPage === "function") setSettingsPage("about");
      });
    }
    var openPreservice = document.getElementById("gn-open-preservice");
    if (openPreservice && !openPreservice.dataset.wired) {
      openPreservice.dataset.wired = "1";
      openPreservice.addEventListener("click", function () {
        if (typeof showSurface === "function") showSurface("preservice");
      });
    }
  };
})();
