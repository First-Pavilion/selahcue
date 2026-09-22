// Settings → Appearance surface (Design 2.0, Figma 581:124 — story 17tnw2axwer, closes SET-004).
//
// HONESTY: exactly one control on this page has a real backend behind it —
// "Default stage theme" — and it is wired to `set_stage_template`/`view.stage_template`, the SAME
// command and field the Presentation surface's own stage-theme picker already uses (app.js,
// `#stage-themes .stage-theme[data-template]`); the three template ids (worship/scripture/
// timer-only) are copied verbatim from there rather than re-invented. Everything else this frame
// draws — interface density, interface/stage text size, high-contrast, reduced-motion override,
// stage-clock format, brand accent, church-logo-in-header — has no backend command or persistence
// anywhere in this app (checked against every `#[tauri::command]` registered in
// `selahcue-operator/src/main.rs`'s `generate_handler!`, and there is no `localStorage` use
// anywhere in dist/ either). Each of those renders as a REAL, focusable, DISABLED control with an
// honest "not saved yet — coming soon" note, never a toggle that flips and silently forgets on
// reload. "Default slide theme" sits in between: `builtin_themes()` is real and populates the
// select with the actual built-in theme names, but there is no distinct "default theme for new
// decks" field to write to (only the CURRENTLY LIVE theme, which this Settings page must not
// change as a side effect of opening it) — so the select is populated with real data but left
// disabled, and the one live action on this page is the Theme Designer link-out.
(function () {
  "use strict";
  var root = document.getElementById("set-page-appearance");
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

  // A disabled, honestly-inert segmented control — same visual shape as a real one, but every
  // button carries `disabled` + `aria-disabled` so it reads to assistive tech as unavailable
  // rather than a live radiogroup nobody can actually operate a choice out of.
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

  // ---------- Default stage theme (REAL — set_stage_template / view.stage_template) ----------
  // Copied verbatim from app.js's own #stage-themes cards (Presentation surface) — same three
  // ids, same order, same copy — so choosing a default here means the same thing it means there.
  var STAGE_TEMPLATES = [
    { id: "worship", title: "Worship", desc: "Song + position + wall-clock, large NOW lyric with dim NEXT, and a service-timer bar." },
    { id: "scripture", title: "Scripture", desc: "Gold reference, large scripture, NEXT line, and a prominent time-left panel." },
    { id: "timer-only", title: "Timer-only", desc: "A big countdown and date — for pre-service and segment clocks." },
  ];

  function stageThemeCard(tpl, selected) {
    var card = el("button", "pp-radio-card" + (selected ? " sel" : ""));
    card.type = "button";
    card.id = "ap-stage-theme-" + tpl.id;
    card.setAttribute("role", "radio");
    card.setAttribute("aria-checked", selected ? "true" : "false");
    card.tabIndex = selected ? 0 : -1;
    var head = el("div", "pp-radio-head");
    var dot = el("span", "pp-radio-dot" + (selected ? " on" : ""));
    dot.setAttribute("aria-hidden", "true");
    head.appendChild(dot);
    var textcol = el("div", "pp-radio-textcol");
    textcol.appendChild(el("span", "pp-radio-title", tpl.title));
    textcol.appendChild(el("span", "pp-radio-desc", tpl.desc));
    head.appendChild(textcol);
    card.appendChild(head);
    card.addEventListener("click", function () {
      if (selected) return;
      invoke("set_stage_template", { template: tpl.id })
        .then(function (view) { renderStageThemes(view && view.stage_template); })
        .catch(function () { loadStageTheme(); }); // resync on rejection — no unconfirmed state
    });
    return card;
  }

  function renderStageThemes(current) {
    var host = document.getElementById("ap-stage-themes");
    if (!host) return;
    var active = current || "worship";
    host.textContent = "";
    STAGE_TEMPLATES.forEach(function (tpl) {
      host.appendChild(stageThemeCard(tpl, tpl.id === active));
    });
  }

  function loadStageTheme() {
    invoke("view").then(function (v) {
      renderStageThemes(v && v.stage_template);
    }).catch(function () {
      renderStageThemes("worship"); // offline-first default (matches app.js's own fallback)
    });
  }

  // ---------- Default slide theme (real data, no writable "default" field — see header) --------
  function loadSlideThemeNames() {
    var sel = document.getElementById("ap-slide-theme");
    if (!sel) return;
    sel.textContent = "";
    invoke("builtin_themes").then(function (list) {
      sel.textContent = "";
      (list || []).forEach(function (item) {
        var opt = document.createElement("option");
        opt.value = item.name || "";
        opt.textContent = item.name || "Theme";
        sel.appendChild(opt);
      });
      if (!sel.options.length) {
        var empty = document.createElement("option");
        empty.textContent = "—";
        sel.appendChild(empty);
      }
    }).catch(function () {
      sel.textContent = "";
      var empty = document.createElement("option");
      empty.textContent = "—";
      sel.appendChild(empty);
    });
  }

  window.settingsAppearanceActivate = function () {
    loadStageTheme();
    loadSlideThemeNames();
    renderInertSegmented("ap-density", ["Comfortable", "Compact"], 0);
    renderInertSegmented("ap-clockfmt", ["12-hour", "24-hour"], 0);
    var openTd = document.getElementById("ap-open-theme-designer");
    if (openTd && !openTd.dataset.wired) {
      openTd.dataset.wired = "1";
      openTd.addEventListener("click", function () {
        if (typeof showSurface === "function") showSurface("theme-designer");
      });
    }
  };
})();
