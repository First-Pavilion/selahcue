// Settings › Network & Mobile — SET-009 addendum (story 17tnw2axweu). The page itself was already
// built (Providers & Privacy tier); this file wires the NEW sections this batch adds: LAN CONTROL
// SERVER / DISCOVERY / SECURITY & TRANSPORT / PAIRED DEVICES / ROLES & GRANTS / RATE LIMITS /
// AUDIT / PREVIEW STREAMING (Figma 580:124). Checked against the full generate_handler! registry
// in selahcue-operator/src/main.rs: none of it has a backend command (no LAN-server toggle, no
// mDNS toggle, no cert-regenerate, no revoke-all, no control-audit, no rate-limit config) — this
// answers SET-OQ-3 with evidence: a genuine backend gap, not a deliberate deferral behind the
// Devices link-out. Every control here is a real, disabled element with an honest note.
//
// What IS real: the paired-devices SUMMARY count, from remote_snapshot() (the same command
// Remote Control · Devices itself calls) — never the Figma mock's fabricated "3 paired total ·
// 2 connected · 1 offline". The online/idle/offline split mirrors remote.js's own statusFor()
// thresholds verbatim (idle_secs < 30 online, < 300 idle, else offline) rather than inventing a
// second definition of what "connected" means.
(function () {
  "use strict";
  var root = document.getElementById("set-page-network");
  if (!root) return;

  var INVOKE =
    (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) || null;
  function invoke(cmd, args) {
    if (!INVOKE) return Promise.reject(new Error("no host connection"));
    return INVOKE(cmd, args || {});
  }

  // Same thresholds as remote.js's statusFor() — kept as a literal copy (that function isn't
  // exposed outside remote.js's own closure) rather than a re-invented definition.
  function statusFor(secs) {
    secs = secs || 0;
    if (secs < 30) return "online";
    if (secs < 300) return "idle";
    return "offline";
  }

  function loadPairedSummary() {
    var el = document.getElementById("net-paired-summary");
    if (!el) return;
    invoke("remote_snapshot").then(function (res) {
      var devices = (res && res.devices) || [];
      var pending = (res && res.pending) || [];
      var online = devices.filter(function (d) { return statusFor(d.idle_secs) === "online"; }).length;
      var offline = devices.length - online;
      var text = devices.length + " paired total · " + online + " online · " + offline + " idle/offline";
      if (pending.length) text += " · " + pending.length + " pending request" + (pending.length === 1 ? "" : "s");
      el.textContent = text;
    }).catch(function () {
      el.textContent = "Couldn't load paired devices.";
    });
  }

  window.settingsNetworkActivate = function () {
    loadPairedSummary();
    var openRoles = document.getElementById("net-open-roles");
    if (openRoles && !openRoles.dataset.wired) {
      openRoles.dataset.wired = "1";
      openRoles.addEventListener("click", function () {
        if (typeof showSurface === "function") showSurface("remote");
      });
    }
  };
})();
