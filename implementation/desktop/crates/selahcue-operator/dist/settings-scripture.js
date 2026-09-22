// Settings → Scripture & Translations surface (Design 2.0, Figma 578:124 — story 17tnw2axwet,
// closes SET-002 from docs/design/DESIGN-2.0-PARITY-AUDIT-settings.md).
//
// The best-backed of the seven new pages. Real, already-shipped commands this file uses:
//   list_translations           — the real installed/downloadable set (never the Figma mock's
//                                  static "World English Bible, ASV, KJV, WEBBE, Darby" text).
//   set_preferred_translation   — the SAME command settings.js's Providers & Privacy panel
//                                  already calls for its translation select; this page's per-row
//                                  "Default" radio AND its summary select both write through it
//                                  and re-render from its response, so the two controls can never
//                                  independently drift (handoff §9's own requirement: "keep the
//                                  dropdown a reflection of the radio").
//
// HONESTY: everything else this page's Figma frame draws — per-row "show in picker" + drag-to-
// reorder, verses-per-slide / verse-number style / reference-header formatting, history length +
// favourites, rebuild-keyword-index, side-by-side comparison (Figma's own SOON badge), custom
// layouts (Figma's own SOON badge), and "Add a translation"'s import/API-key flow — has no
// backend mutation to call (checked against every #[tauri::command] registered in
// selahcue-operator/src/main.rs). Each renders as a real, disabled control with an honest note,
// never a drag handle that silently reorders nothing or a "Rebuild" button with no index behind
// it.
(function () {
  "use strict";
  var root = document.getElementById("set-page-scripture");
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

  // Latest known installed-translations list + the currently preferred code — replaced wholesale
  // on every load/mutation, never appended (same discipline as settings.js's `view`).
  var installed = [];
  var preferred = "";

  function badge(cls, text) {
    return el("span", "pp-badge " + cls, text);
  }

  function translationRow(t) {
    var selected = t.code === preferred;
    var row = el("button", "pp-radio-card" + (selected ? " sel" : ""));
    row.type = "button";
    row.id = "sc-translation-" + t.code;
    row.setAttribute("role", "radio");
    row.setAttribute("aria-checked", selected ? "true" : "false");
    row.tabIndex = selected ? 0 : -1;

    var head = el("div", "pp-radio-head");
    var dot = el("span", "pp-radio-dot" + (selected ? " on" : ""));
    dot.setAttribute("aria-hidden", "true");
    head.appendChild(dot);
    var textcol = el("div", "pp-radio-textcol");
    var titlerow = el("div", "pp-radio-titlerow");
    titlerow.appendChild(el("span", "pp-radio-title", t.name || t.code));
    // downloadable:false in this catalog means "shipped in the binary" — every one of them is a
    // real public-domain text per selahcue_scripture::Translation::ALL; a downloadable (licensed)
    // entry gets no such claim.
    if (!t.downloadable) titlerow.appendChild(badge("pp-badge-private", "PUBLIC DOMAIN"));
    if (selected) titlerow.appendChild(badge("pp-badge-included", "DEFAULT"));
    textcol.appendChild(titlerow);
    head.appendChild(textcol);
    row.appendChild(head);

    var actions = el("div", "pp-radio-actions");
    // "Show in picker" has no backend field to reflect or write — a real, disabled toggle rather
    // than an interactive-looking one that would silently do nothing on click.
    var showToggle = el("label", "pp-toggle set-inert");
    var showInput = document.createElement("input");
    showInput.type = "checkbox";
    showInput.checked = true;
    showInput.disabled = true;
    showInput.setAttribute("aria-label", (t.name || t.code) + " shows in picker (not configurable yet)");
    showToggle.appendChild(showInput);
    showToggle.appendChild(el("span", "pp-toggle-knob"));
    actions.appendChild(showToggle);
    row.appendChild(actions);

    row.addEventListener("click", function (e) {
      // The row itself sets the default; the inert toggle inside it must never bubble into that.
      if (e.target === showInput || showToggle.contains(e.target)) return;
      if (selected) return;
      invoke("set_preferred_translation", { code: t.code }).then(function (view) {
        applyPreferred(view && view.preferred_translation);
      }).catch(function () { loadTranslations(); }); // resync — no unconfirmed state
    });
    return row;
  }

  function renderTranslations() {
    var host = document.getElementById("sc-translations-list");
    if (!host) return;
    var focusId = document.activeElement && host.contains(document.activeElement) && document.activeElement.id;
    host.textContent = "";
    if (!installed.length) {
      host.appendChild(el("p", "set-inert-note", "No scripture translations are installed in this build."));
    } else {
      installed.forEach(function (t) { host.appendChild(translationRow(t)); });
    }
    if (focusId) {
      var again = document.getElementById(focusId);
      if (again && typeof again.focus === "function") again.focus();
    }
    renderDefaultSelect();
  }

  // Keeps the summary select a REFLECTION of the radio list (handoff §9), not an independent
  // second source of truth — both are rebuilt from the same `installed`/`preferred` state.
  function renderDefaultSelect() {
    var sel = document.getElementById("sc-default-select");
    if (!sel) return;
    sel.textContent = "";
    if (!installed.length) {
      var empty = document.createElement("option");
      empty.textContent = "—";
      sel.appendChild(empty);
      sel.disabled = true;
      return;
    }
    sel.disabled = false;
    installed.forEach(function (t) {
      var opt = document.createElement("option");
      opt.value = t.code;
      opt.textContent = t.name || t.code;
      if (t.code === preferred) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function applyPreferred(code) {
    if (code) preferred = code;
    renderTranslations();
  }

  function loadTranslations() {
    invoke("list_translations").then(function (res) {
      installed = (res && res.translations) || [];
      // list_translations doesn't itself say which is preferred — read that from the same
      // providers_view() Providers & Privacy already uses, so this page can never show a
      // "default" that disagrees with the one actually in effect.
      return invoke("providers_view");
    }).then(function (view) {
      preferred = (view && view.preferred_translation) || (installed[0] && installed[0].code) || "";
      renderTranslations();
    }).catch(function () {
      installed = [];
      preferred = "";
      renderTranslations();
    });
  }

  function onSelectChange() {
    var sel = document.getElementById("sc-default-select");
    if (!sel || !sel.value || sel.value === preferred) return;
    invoke("set_preferred_translation", { code: sel.value }).then(function (view) {
      applyPreferred(view && view.preferred_translation);
    }).catch(function () { loadTranslations(); });
  }

  // ---------- inert segmented control (verse-number style) ----------
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

  // Roving-tabindex arrow-key navigation (APG radiogroup pattern) — ported from settings.js's
  // onRadioKeydown/Appearance's onStageThemeKeydown (a keyboard-only operator must be able to
  // reach every card, not just the selected one; see settings-appearance.js's header comment for
  // the QA finding, ClickUp 17tnw2axwfm, that made this a standing requirement for every new
  // radiogroup in this batch, not just the one it was originally found on).
  function onTranslationsKeydown(e) {
    var host = document.getElementById("sc-translations-list");
    if (!host) return;
    var cards = Array.prototype.slice.call(host.querySelectorAll(".pp-radio-card"));
    var i = cards.indexOf(document.activeElement);
    if (i < 0) return;
    if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      var next = (e.key === "ArrowRight" || e.key === "ArrowDown")
        ? (i + 1) % cards.length : (i - 1 + cards.length) % cards.length;
      cards[next].focus();
      cards[next].click();
    } else if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      cards[i].click();
    }
  }

  window.settingsScriptureActivate = function () {
    loadTranslations();
    renderInertSegmented("sc-versenum", ["Superscript", "Inline", "Hidden"], 0);
    var transHost = document.getElementById("sc-translations-list");
    if (transHost && !transHost.dataset.wired) {
      transHost.dataset.wired = "1";
      transHost.addEventListener("keydown", onTranslationsKeydown);
    }
    var sel = document.getElementById("sc-default-select");
    if (sel && !sel.dataset.wired) {
      sel.dataset.wired = "1";
      sel.addEventListener("change", onSelectChange);
    }
    var openTd = document.getElementById("sc-open-theme-designer");
    if (openTd && !openTd.dataset.wired) {
      openTd.dataset.wired = "1";
      openTd.addEventListener("click", function () {
        if (typeof showSurface === "function") showSurface("theme-designer");
      });
    }
  };
})();
