// Settings → Storage & Backups surface (Design 2.0, Figma 583:124 — story 17tnw2axweu, closes
// SET-006).
//
// Real:
//   - STORAGE USAGE reads the real disk_free command (available_bytes/total_bytes) — an existing
//     command that was registered but never called from anywhere in dist/ until this page. Never
//     the Figma mock's fabricated "38.2 GB free of 256 GB".
//   - Autosave and Crash-loop protection restate behaviour this app ALREADY ships and already
//     tests (scripts/operator_headless.py's "G.5" session-recovery checks: an autosave failure
//     shows the host's real reason, and the crash-loop breaker reports a real restart count) —
//     not re-derived here, just honestly restated as informational (not a toggle, matching the
//     design's own "Always on" framing).
//
// backup_to / backup_to_encrypted / integrity_check / checkpoint_truncate already exist as Rust
// functions in selahcue-data (confirmed by reading the crate) but are NOT wired as Tauri commands
// anywhere in main.rs's generate_handler! registry — flagged as a backend follow-up (the domain
// logic already exists; it needs thin command wrappers), not silently added by this ticket. Back
// up now / Run integrity check / Restore all render as real, disabled controls — never a fake
// destructive action with nothing behind it.
(function () {
  "use strict";
  var root = document.getElementById("set-page-storage");
  if (!root) return;

  var INVOKE =
    (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) || null;
  function invoke(cmd, args) {
    if (!INVOKE) return Promise.reject(new Error("no host connection"));
    return INVOKE(cmd, args || {});
  }

  function fmtGb(bytes) {
    return (bytes / 1073741824).toFixed(1) + " GB";
  }

  function loadDiskUsage() {
    var el = document.getElementById("st-disk-usage");
    if (!el) return;
    invoke("disk_free").then(function (res) {
      if (!res || typeof res.available_bytes !== "number" || typeof res.total_bytes !== "number") {
        el.textContent = "Not available.";
        return;
      }
      if (res.total_bytes === 0) { el.textContent = "Not available on this platform."; return; }
      el.textContent = fmtGb(res.available_bytes) + " free of " + fmtGb(res.total_bytes);
    }).catch(function () {
      el.textContent = "Couldn't read disk usage.";
    });
  }

  window.settingsStorageActivate = function () {
    loadDiskUsage();
    var openPlan = document.getElementById("st-open-plan");
    if (openPlan && !openPlan.dataset.wired) {
      openPlan.dataset.wired = "1";
      openPlan.addEventListener("click", function () {
        if (typeof showSurface === "function") showSurface("plan");
      });
    }
  };
})();
