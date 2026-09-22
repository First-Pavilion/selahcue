// Settings → About & Licensing surface (Design 2.0, Figma 584:124 — story 17tnw2axwer, closes
// SET-007 from docs/design/DESIGN-2.0-PARITY-AUDIT-settings.md).
//
// HONESTY (same discipline as settings.js's header comment, restated for this page because it
// covers more genuinely-unbuilt ground than Providers & Privacy did): this page's Figma frame
// draws several fields this build has no live source for at all — an update-check mechanism, a
// generated SBOM/license manifest, a song/CCLI editor, and external support/policy URLs. None of
// those get a fabricated number or a dead link to a guessed URL. Each one renders as a real,
// labelled, DISABLED row with honest copy (the same "Coming in Rn" disabled-affordance pattern
// already used elsewhere in this spec for roadmap-deferred controls, extended here to cover
// backend-pending ones too) — never a button that looks live and silently does nothing.
//
// What IS real on this page:
//   - Version: read from Tauri's own `app.getVersion()` global (feature-detected; this is Tauri's
//     built-in API, not a new command this ticket invented) — falls back to "—" honestly if the
//     global isn't exposed rather than printing a made-up number.
//   - Platform: read from `navigator` — genuinely reflects the host OS the webview is running on.
//   - Scripture attributions: `list_translations` (an existing, already-shipped command) — the
//     real bundled/downloadable set, never the Figma mock's hardcoded "WEB, ASV, KJV, WEBBE,
//     Darby" text.
//   - The Data Processing Agreement row's SOON/shown state reflects `providers_view()`'s real
//     `any_cloud_enabled` flag (the same field Providers & Privacy itself is driven by).
//   - Offline-by-default / codec / NDI-availability banners restate facts already true and
//     already stated elsewhere in this app (Providers & Privacy's own banner, the `set_ndi_output`
//     command's existence) — not new claims invented for this page.
(function () {
  "use strict";
  var root = document.getElementById("set-page-about");
  if (!root) return;

  var INVOKE =
    (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) || null;
  function invoke(cmd, args) {
    if (!INVOKE) return Promise.reject(new Error("no host connection"));
    return INVOKE(cmd, args || {});
  }

  function setVersion() {
    var elv = document.getElementById("ab-version");
    if (!elv) return;
    // Tauri's own app-info API, exposed via the global bridge (withGlobalTauri) this app already
    // relies on for `core.invoke`. Feature-detected end to end: an older/narrower capability grant
    // or a dist opened outside the shell both fall through to the honest "—", never a guess.
    var app = window.__TAURI__ && window.__TAURI__.app;
    if (app && typeof app.getVersion === "function") {
      app.getVersion().then(function (v) {
        if (v) elv.textContent = v;
      }).catch(function () { /* leave the honest "—" */ });
    }
  }

  function setPlatform() {
    var elp = document.getElementById("ab-platform");
    if (!elp) return;
    var ua = (navigator.userAgent || "");
    var plat = (navigator.platform || "").trim();
    var os = "Unknown platform";
    if (/Mac/i.test(ua)) os = /Mac.*arm/i.test(ua) ? "macOS · Apple Silicon (arm64)" : "macOS";
    else if (/Win/i.test(ua)) os = "Windows";
    else if (/Linux/i.test(ua)) os = "Linux";
    elp.textContent = plat ? os + " (" + plat + ")" : os;
  }

  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  // Real bundled/downloadable translation set (never the Figma mock's static text) — same
  // `list_translations` command the Scripture-adjacent surfaces already call.
  function loadScriptureAttributions() {
    var host = document.getElementById("ab-scripture-list");
    if (!host) return;
    host.textContent = "";
    invoke("list_translations").then(function (res) {
      var items = (res && res.translations) || [];
      host.textContent = "";
      if (!items.length) {
        host.appendChild(el("p", "set-inert-note", "No scripture translations are installed in this build."));
        return;
      }
      items.forEach(function (t) {
        var row = el("div", "pp-inc-row");
        row.setAttribute("role", "listitem");
        row.appendChild(el("span", "pp-inc-label", t.name || t.code || "Translation"));
        var licence = t.downloadable
          ? "Licence shown once installed"
          : "Public Domain — no attribution required";
        row.appendChild(el("span", "set-row-v", licence));
        host.appendChild(row);
      });
    }).catch(function () {
      host.textContent = "";
      host.appendChild(el("p", "set-inert-note", "Couldn't load the installed translations."));
    });
  }

  // The DPA row's SOON/shown framing follows the SAME any_cloud_enabled signal Providers &
  // Privacy itself renders from — never a second, independently-drifting copy of that flag.
  function loadCloudDpaState() {
    var note = document.getElementById("ab-dpa-note");
    var badge = document.getElementById("ab-dpa-badge");
    if (!note || !badge) return;
    invoke("providers_view").then(function (view) {
      if (view && view.any_cloud_enabled) {
        note.textContent = "A cloud provider is enabled — a Data Processing Agreement and cross-border-transfer disclosure apply.";
        badge.textContent = "CLOUD ENABLED";
        badge.classList.remove("pp-badge-soon");
        badge.classList.add("pp-badge-neutral");
      } else {
        note.textContent = "A DPA and cross-border-transfer disclosure apply when a cloud provider is enabled. None is enabled right now.";
        badge.textContent = "NOT SHOWN";
        badge.classList.remove("pp-badge-soon");
        badge.classList.add("pp-badge-neutral");
      }
    }).catch(function () { /* leave the honest default copy already in the markup */ });
  }

  window.settingsAboutActivate = function () {
    setVersion();
    setPlatform();
    loadScriptureAttributions();
    loadCloudDpaState();
  };

  // Test-only hook (mirrors window.__resetSermonNoteDraftForTest in settings.js): lets a headless
  // check simulate a fresh activation without a real app restart.
  window.__resetSettingsAboutForTest = function () {
    var v = document.getElementById("ab-version");
    if (v) v.textContent = "—";
    var p = document.getElementById("ab-platform");
    if (p) p.textContent = "—";
    var list = document.getElementById("ab-scripture-list");
    if (list) list.textContent = "";
  };
})();
