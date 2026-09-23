// Settings → Outputs & Displays surface (Design 2.0, Figma 579:124 — story 17tnw2axweu, closes
// SET-003).
//
// Real: DISPLAYS reads view().displays/view().outputs (never the Figma mock's fabricated
// "Display 1 — 1920×1080 · 60Hz · Built-in" text) and "Identify displays" calls the existing
// identify_outputs command. "Manage screens" is a real navigation to the Screens & Outputs
// surface, which already owns live per-screen assignment (handoff's own "don't duplicate" IA
// rule — this page holds defaults only).
//
// PER-OUTPUT CONFIG / OUTPUT HEALTH / TEST PATTERNS / NETWORK OUTPUTS are whole sections the
// FIGMA FRAME ITSELF marks "COMING SOON" — rendered that way here because the design says so, not
// as this batch's own judgement call. Everything else (venue profiles, audio device, stage/
// confidence region defaults, reduced motion) has no backend command anywhere in this app
// (checked against the full generate_handler! registry) and renders as a real, disabled control.
(function () {
  "use strict";
  var root = document.getElementById("set-page-outputs");
  if (!root) return;

  var INVOKE =
    (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) || null;
  function invoke(cmd, args) {
    if (!INVOKE) return Promise.reject(new Error("no host connection"));
    return INVOKE(cmd, args || {});
  }

  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  // ---------- DISPLAYS (real: view().displays cross-referenced with view().outputs) ----------
  function renderDisplays(view) {
    var host = document.getElementById("out-displays-list");
    if (!host) return;
    host.textContent = "";
    var displays = (view && view.displays) || [];
    var outputs = (view && view.outputs) || [];
    if (!displays.length) {
      host.appendChild(el("p", "set-inert-note", "No displays reported by the host yet."));
      return;
    }
    displays.forEach(function (d) {
      var assignedTo = outputs.filter(function (o) { return o.assigned && o.assigned_key === d.key; })
        .map(function (o) { return o.role; });
      var row = el("div", "set-row");
      var left = el("div");
      left.appendChild(el("p", "set-row-t", (d.name || d.key) + " — " + d.width + " × " + d.height));
      left.appendChild(el("p", "set-row-d", assignedTo.length ? "Assigned to: " + assignedTo.join(", ") : "Not assigned to a live output role."));
      row.appendChild(left);
      host.appendChild(row);
    });
  }

  function loadDisplays() {
    invoke("view").then(renderDisplays).catch(function () { renderDisplays(null); });
  }

  // ---------- inert segmented / stage-region list ----------
  function renderInertSegmented(hostId, options, selectedIndex) {
    var host = document.getElementById(hostId);
    if (!host) return;
    host.textContent = "";
    options.forEach(function (label, i) {
      var btn = el("button", "pp-segmented-btn" + (i === selectedIndex ? " sel" : ""), label);
      btn.type = "button";
      btn.disabled = true;
      btn.setAttribute("aria-disabled", "true");
      btn.setAttribute("role", "radio");
      btn.setAttribute("aria-checked", i === selectedIndex ? "true" : "false");
      host.appendChild(btn);
    });
  }

  var STAGE_REGIONS = [
    { t: "Current line (Now)", d: "The line currently live." },
    { t: "Next line (Next)", d: "Stage/confidence only — never shown to the audience." },
    { t: "Time-of-day clock", d: "Wall clock on stage displays." },
    { t: "Timer + TIME UP", d: "Stage/confidence only — audience never sees timers by default." },
    { t: "Stage message", d: "Operator-to-platform notes — never shown to the audience." },
    { t: "Theme background", d: "Show the stage theme background behind text." },
  ];

  function renderStageRegions() {
    var host = document.getElementById("out-stage-regions");
    if (!host) return;
    host.textContent = "";
    STAGE_REGIONS.forEach(function (r) {
      var row = el("div", "set-row");
      var left = el("div");
      left.appendChild(el("p", "set-row-t", r.t));
      left.appendChild(el("p", "set-row-d", r.d + " Not configurable yet — defaults to on, stage/confidence only."));
      row.appendChild(left);
      var toggle = el("label", "pp-toggle set-inert");
      var input = document.createElement("input");
      input.type = "checkbox";
      input.checked = true;
      input.disabled = true;
      input.setAttribute("aria-label", r.t + " (not configurable yet)");
      toggle.appendChild(input);
      toggle.appendChild(el("span", "pp-toggle-knob"));
      row.appendChild(toggle);
      host.appendChild(row);
    });
  }

  window.settingsOutputsActivate = function () {
    loadDisplays();
    renderStageRegions();
    renderInertSegmented("out-winmode", ["Fullscreen", "Windowed"], 0);
    var openScreens = document.getElementById("out-open-screens");
    if (openScreens && !openScreens.dataset.wired) {
      openScreens.dataset.wired = "1";
      openScreens.addEventListener("click", function () {
        if (typeof showSurface === "function") showSurface("screens");
      });
    }
    var identify = document.getElementById("out-identify");
    if (identify && !identify.dataset.wired) {
      identify.dataset.wired = "1";
      identify.addEventListener("click", function () {
        identify.disabled = true;
        invoke("identify_outputs").then(loadDisplays).catch(function () {}).then(function () {
          identify.disabled = false;
        });
      });
    }
  };
})();
