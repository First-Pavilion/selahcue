// Settings → Security surface (Design 2.0, Figma 582:124 — story 17tnw2axweu, closes SET-005).
//
// AT-REST ENCRYPTION now reads the REAL `security_status` command (86akgrz3b, Shadow's security
// review of PR #125) instead of a hardcoded claim. That command peeks the actual on-disk header
// of the shared transcript store — the same plaintext-vs-encrypted discriminator
// `open_transcript_db_at`/`selahcue-desktop::SessionStore::open_store` use — so this page can no
// longer disagree with reality in either direction. Before this fix it hardcoded "NOT YET ON",
// which became FALSE the moment `encryption`/`read-encrypted-transcripts` shipped default-on
// (86akgrz3b), and — worse — was indistinguishable from the one case that genuinely still needs a
// red flag: a keychain/passphrase hiccup at a store's creation silently leaves it plaintext
// forever (`SessionStore::open_store`'s `(None, None)` arm; in-place migration is a documented
// pending tool, not shipped by this ticket — see 86akgrz3b's PR description and ClickUp comments
// for the product-owner decision this still needs on existing installs).
//
// Four states `security_status` can report, and what this page shows for each:
//   "encrypted"     — the store on disk is genuinely SQLCipher-encrypted. Positive badge.
//   "not_encrypted" — the store on disk is genuinely plaintext SQLite. This is the silent-
//                     downgrade case: shown as a clear warning, not softened.
//   "no_store_yet"  — no service has been recorded yet (or the path isn't resolvable). The next
//                     service creates the store, encrypted, if a key is available then.
//   "unavailable"   — this build was not compiled with `read-encrypted-transcripts`; encryption
//                     genuinely is not available here.
//
// Still real, unchanged from before: "Signed updates" (no update mechanism exists anywhere in
// this app yet — see settings-about.js) and the Audit Log (no control-audit command or data
// source anywhere — never the Figma mock's fabricated "Sarah's iPad" / "FOH Mac" rows) stay
// honestly marked not-yet-built.
//
// What IS real: the two link-outs (Providers & Privacy for cloud/consent, Network & Mobile for
// device revocation) navigate to pages that actually own that content.
(function () {
  "use strict";
  var root = document.getElementById("set-page-security");
  if (!root) return;

  var INVOKE =
    (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) || null;
  function invoke(cmd, args) {
    if (!INVOKE) return Promise.reject(new Error("no host connection"));
    return INVOKE(cmd, args || {});
  }

  var COPY = {
    encrypted: {
      badge: "ON",
      badgeClass: "pp-badge-ok",
      desc: "Service plans, library, transcripts, and captured audio are encrypted at rest (SQLCipher).",
      note: "At-rest encryption (SQLCipher, ADR-0007) is on for this host's database.",
    },
    not_encrypted: {
      badge: "NOT ENCRYPTED",
      badgeClass: "pp-badge-danger",
      desc: "This host's database exists but is NOT encrypted — likely an OS secret store issue at the time it was created. Restart SelahCue to retry; if this persists, check the platform keychain/credential manager.",
      note: "At-rest encryption is enabled in this build but could not be applied when this database was created. Existing data is not encrypted; a fresh database created once the key source is working will be.",
    },
    no_store_yet: {
      badge: "READY",
      badgeClass: "pp-badge-neutral",
      desc: "No service has been recorded on this host yet. The next one creates an encrypted database automatically.",
      note: "At-rest encryption (SQLCipher, ADR-0007) is on for this host — nothing has been recorded here yet.",
    },
    unavailable: {
      badge: "NOT IN THIS BUILD",
      badgeClass: "pp-badge-neutral",
      desc: "This build was not compiled with at-rest encryption support.",
      note: "At-rest encryption (SQLCipher, ADR-0007) is not compiled into this build.",
    },
  };
  // Never trust an unrecognised state string as if it were good news.
  var FALLBACK = {
    badge: "UNKNOWN",
    badgeClass: "pp-badge-neutral",
    desc: "Couldn't determine this host's encryption status.",
    note: "Couldn't determine this host's encryption status.",
  };

  function applyStatus(state) {
    var c = (Object.prototype.hasOwnProperty.call(COPY, state) && COPY[state]) || FALLBACK;
    var badge = document.getElementById("sec-atrest-badge");
    if (badge) {
      badge.textContent = c.badge;
      badge.className = "pp-badge " + c.badgeClass;
    }
    var desc = document.getElementById("sec-atrest-desc");
    if (desc) desc.textContent = c.desc;
    var note = document.getElementById("sec-atrest-note");
    if (note) note.textContent = c.note;
  }

  function loadSecurityStatus() {
    invoke("security_status")
      .then(function (res) {
        applyStatus(res && res.state);
      })
      .catch(function () {
        applyStatus(null); // falls through to FALLBACK — an honest "couldn't determine", never a
                            // guessed "encrypted"/"not encrypted".
      });
  }

  window.settingsSecurityActivate = function () {
    loadSecurityStatus();
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
