// Settings → Security surface (Design 2.0, Figma 582:124 — story 17tnw2axweu, closes SET-005).
//
// CORRECTION vs. the Figma mock — read this before "restoring" the mock's copy: the mock draws
// at-rest encryption as ON with a verified badge. It is NOT on in this build. Verified directly:
// selahcue-operator/Cargo.toml declares `selahcue-data = { path = "../selahcue-data" }` with no
// `features = ["encryption"]`, and main.rs opens the database with the plain
// `selahcue_data::Database::open(...)`, never `open_encrypted`. ADR-0007 names FR-154/at-rest
// encryption an explicit **R3 acceptance row** — a documented future milestone, not an oversight
// — so this page says "not yet on" rather than repeating a claim this build doesn't back up. Same
// correction applied to "Signed updates" (no update mechanism exists anywhere in this app yet —
// see settings-about.js) and the Audit Log (no control-audit command or data source anywhere —
// never the mock's fabricated "Sarah's iPad" / "FOH Mac" rows).
//
// What IS real: the two link-outs (Providers & Privacy for cloud/consent, Network & Mobile for
// device revocation) navigate to pages that actually own that content.
(function () {
  "use strict";
  var root = document.getElementById("set-page-security");
  if (!root) return;

  window.settingsSecurityActivate = function () {
    var wire = function (id, fn) {
      var b = document.getElementById(id);
      if (b && !b.dataset.wired) { b.dataset.wired = "1"; b.addEventListener("click", fn); }
    };
    wire("sec-open-providers", function () {
      if (typeof setSettingsPage === "function") setSettingsPage("providers");
    });
    wire("sec-open-about", function () {
      if (typeof setSettingsPage === "function") setSettingsPage("about");
    });
    wire("sec-open-network-revoke", function () {
      if (typeof setSettingsPage === "function") setSettingsPage("network");
    });
  };
})();
