// Settings → Providers & Privacy surface (Design 2.0, Figma 338:124 — story 86ajxucue, backend
// 86ajy034h). Renders the panel body (#pp-trans + #pp-ai) from the REAL backend state returned by
// the operator commands and wires every control to its command:
//   providers_view · set_transcription_mode · set_cloud_consent · set_notes_template ·
//   set_preferred_translation · set_include_flag · set_account_token / clear_account_token
//
// 17tnw2b0ntd (D1/D2, TRANSCRIPTS-2.0-HANDOFF.md §13): this card no longer generates, previews,
// stores, or edits a sermon-note draft at all — every bit of that apparatus (Generate button,
// review-before-send preview, result/edit panel, regenerate-with-retention banner, quota meter)
// was removed from here and lives ONLY on the Transcripts page now (`transcripts.js`'s
// `#tr-generate`/`#tr-gen-preview`/`#tr-gen-result`, driven by `transcript_generate_notes`). This
// card keeps consent + provider settings only, plus a plain link to Transcripts. The removed
// live-tail `generate_sermon_notes` Tauri command (and the `window.scCompletedTranscript` bridge
// it depended on) are gone from the codebase entirely — see `src/main.rs` and `dist/app.js`.
//
// HONESTY (this screen is about trust): only real state is rendered, and under-reporting breaks
// that contract exactly as much as over-reporting does.
//
// `cloud_status` is one of FOUR states and the panel renders a different, true thing for each:
//   "not_configured"  — no provider path is compiled in and no hosted service is configured.
//                       Honest "coming soon". This is the stock build.
//   "key_missing"     — a direct-provider path IS compiled in but no developer key is present.
//                       NOT "coming soon" and NOT an error: the feature exists, the key does not,
//                       and saying which is the difference between actionable and useless.
//   "direct_provider" — a third-party provider (OpenAI) is configured on this machine via a
//                       developer key. Notes really are generated. The panel says so, names the
//                       provider (FR-132), and says the key is a developer key — because it is.
//   "hosted"          — the SelahCue hosted service is configured. Phase 2.
//
// `notes_available` (RENAMED from `cloud_connected`) means "note generation can run right now" —
// true for the last two states only. The old name meant "the hosted service is reachable", which
// stayed false while GPT generated real drafts, so this panel rendered "coming soon" over a working
// feature. A field called `cloud_connected` reading true for a local developer key would have been
// the same lie with better manners, so it was renamed rather than redefined.
//
// `notes_provider` is null EXACTLY when `notes_available` is false. Never render an availability
// claim without reading the provider out of it — the two are tied on the backend and asserted in
// both directions, and that tie is what stops this screen advertising a feature it cannot name.
//
// Consent is still gated end to end on the backend (`consent_required` when cloud-notes consent
// is off, `not_configured` when nothing can serve the request) — this card is where that consent
// is granted, even though the Generate action it gates now lives elsewhere. Nav + activation live
// in app.js (showSurface → settingsActivate); this module owns the surface body and loads after
// app.js.
//
// Excluded by product decision (present in the frame, NOT built here): Text-to-Speech (DEC-001) and
// the "Advanced · Bring your own key / custom provider" row (hosted-only model).
(function () {
  "use strict";
  var root = document.getElementById("surface-settings");
  if (!root) return;
  var transEl = document.getElementById("pp-trans");
  var aiEl = document.getElementById("pp-ai");
  if (!transEl || !aiEl) return;

  // Tauri IPC (absent when the dist is opened outside the shell — the panel then renders the
  // offline-first defaults so it is never blank, and mutations are no-ops).
  var INVOKE =
    (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) || null;
  function invoke(cmd, args) {
    if (!INVOKE) return Promise.reject(new Error("no host connection"));
    return INVOKE(cmd, args || {});
  }

  // ---------- helpers ----------
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }
  // The offline-first defaults the CORE would supply — used only when there is no host connection,
  // so the panel is never blank. These are honest defaults (cloud OFF, not configured), NOT
  // fabricated live values.
  function defaultView() {
    return {
      transcription_mode: "on_device",
      on_device: { ready: false, state: "unknown", model: "", detail: "" },
      cloud_transcription_consent: false,
      cloud_notes_consent: false,
      offline_by_default: true,
      any_cloud_enabled: false,
      notes_template: "",
      notes_templates: [],
      preferred_translation: "",
      translations: [],
      include: {
        prayer_points: false, scripture_extraction: false, social_excerpts: false,
        chapter_markers: false, notable_quotations: false, short_summary: false,
        podcast_show_notes: false, short_description: false,
      },
      cloud_status: "not_configured",
      notes_available: false,
      notes_provider: null,
      account_token_set: false,
      quota: null,
      // Honest offline-first default (86akby7th): no build claims Cloud transcription is ready
      // until the backend actually confirms it, mirroring notes_available/notes_provider above.
      transcription_available: false,
      transcription_provider: null,
    };
  }

  // Latest known view (source of truth for re-render). Never accumulates — replaced, never appended.
  var view = defaultView();
  // The last Generate result region content is transient and lives inside #pp-ai (cleared on every
  // re-render), so nothing here grows without bound.

  // Apply a fresh ProvidersView returned by a mutation and re-render, preserving keyboard focus on
  // the acting control (re-render replaces the DOM subtree).
  function apply(next) {
    if (next && typeof next === "object" && "transcription_mode" in next) view = next;
    var focusId = document.activeElement && document.activeElement.id;
    render();
    if (focusId) {
      var again = document.getElementById(focusId);
      if (again && typeof again.focus === "function") again.focus();
    }
  }

  // Run a mutation command: optimistic focus is restored by apply(); a host rejection re-reads the
  // authoritative view so the UI never shows a state the backend didn't confirm (no silent lie).
  function mutate(cmd, args) {
    return invoke(cmd, args).then(apply).catch(function () {
      resync();
    });
  }

  // Re-read the authoritative view and re-render — the "no silent lie" recovery: the card can only
  // ever show a state the backend confirmed.
  function resync() {
    invoke("providers_view").then(apply).catch(function () {});
  }

  // ---------- badges / pills ----------
  function badge(cls, text) {
    return el("span", "pp-badge " + cls, text);
  }
  function pill(cls, text) {
    var p = el("span", "pp-pill " + cls);
    p.appendChild(el("span", "pp-pill-dot"));
    p.appendChild(el("span", null, text));
    return p;
  }

  // ---------- a 42×24 switch (checkbox styled as a toggle) ----------
  function toggle(id, checked, ariaLabel, onChange) {
    var wrap = el("label", "pp-toggle");
    var input = document.createElement("input");
    input.type = "checkbox";
    input.id = id;
    input.checked = !!checked;
    input.setAttribute("role", "switch");
    input.setAttribute("aria-checked", checked ? "true" : "false");
    if (ariaLabel) input.setAttribute("aria-label", ariaLabel);
    input.addEventListener("change", function () { onChange(input.checked); });
    wrap.appendChild(input);
    wrap.appendChild(el("span", "pp-toggle-knob"));
    return wrap;
  }

  // ==================================================================================
  // 2 · LIVE TRANSCRIPTION — two radio cards. Selecting Cloud is the opt-in gesture
  //     (grants transcription consent, then switches the mode); selecting On-device
  //     switches back AND revokes cloud-transcription consent so the "audio never
  //     leaves this machine" guarantee actually holds. Each click issues explicit,
  //     testable commands; the last returned view wins.
  // ==================================================================================
  function transcriptionCard(opts) {
    // opts: {id, selected, title, badgeCls, badgeText, desc, footNode, warnNode, onSelect}
    var card = el("button", "pp-radio-card" + (opts.selected ? " sel" : ""));
    card.type = "button";
    card.id = opts.id;
    card.setAttribute("role", "radio");
    card.setAttribute("aria-checked", opts.selected ? "true" : "false");
    card.tabIndex = opts.selected ? 0 : -1; // roving tabindex (APG radiogroup)

    var head = el("div", "pp-radio-head");
    var dot = el("span", "pp-radio-dot" + (opts.selected ? " on" : ""));
    dot.setAttribute("aria-hidden", "true");
    head.appendChild(dot);

    var textcol = el("div", "pp-radio-textcol");
    var titlerow = el("div", "pp-radio-titlerow");
    titlerow.appendChild(el("span", "pp-radio-title", opts.title));
    titlerow.appendChild(badge(opts.badgeCls, opts.badgeText));
    textcol.appendChild(titlerow);
    textcol.appendChild(el("span", "pp-radio-desc", opts.desc));
    head.appendChild(textcol);
    card.appendChild(head);

    if (opts.warnNode) card.appendChild(opts.warnNode);
    if (opts.footNode) card.appendChild(opts.footNode);

    card.addEventListener("click", function () { if (!opts.selected) opts.onSelect(); });
    return card;
  }

  function renderTranscription() {
    transEl.textContent = "";
    var mode = view.transcription_mode;
    var od = view.on_device || {};

    // On-device model / readiness line — driven from the backend probe (never the frame's literal
    // "small.en · 380 MB"). Honest per state.
    var detail = "Runs locally · audio never leaves this device.";
    if (od.state === "ready" && (od.model || od.detail)) {
      detail = "Model: " + (od.model || "on-device") + (od.detail ? " · " + od.detail : "") + " · works offline";
    } else if (od.detail) {
      detail = od.detail;
    } else if (od.state === "not_in_build") {
      detail = "On-device transcription is not enabled in this build.";
    }
    var onDeviceFoot = el("p", "pp-radio-detail", detail);

    var onDevice = transcriptionCard({
      id: "pp-radio-ondevice",
      selected: mode === "on_device",
      title: "On-device",
      badgeCls: "pp-badge-private",
      badgeText: "🔒 PRIVATE",
      desc: "Whisper runs locally — audio never leaves this machine.",
      footNode: onDeviceFoot,
      onSelect: function () {
        // Switch to on-device AND revoke cloud-transcription consent (audio stays local).
        // On-device is the privacy-SAFE direction, so we still switch even if the revoke call
        // fails (mode=on_device makes may_stream_cloud_audio false regardless); mutate() resyncs
        // if the switch itself is rejected, so the card never shows an unconfirmed state.
        invoke("set_cloud_consent", { kind: "transcription", enabled: false })
          .then(function () { return mutate("set_transcription_mode", { mode: "on_device" }); })
          .catch(function () { mutate("set_transcription_mode", { mode: "on_device" }); });
      },
    });

    // Honest readiness (86akby7th, mirroring on_device above): name the real provider once the
    // backend confirms one is actually configured (FR-120/FR-132) — never an unnamed "the
    // provider" once a real Deepgram socket is what would open, and never a claim of
    // availability the backend has not confirmed.
    var tp = view.transcription_provider;
    var ta = !!view.transcription_available;
    var cloudProviderName = tp && tp.name ? tp.name : "a cloud speech service";

    var warn = el("div", "pp-warn");
    warn.appendChild(el("span", "pp-warn-ico", "⚠"));
    warn.appendChild(el("span", "pp-warn-text", "Streams live microphone audio to " + cloudProviderName + " while active"));

    var cloudOn = mode === "cloud" && view.cloud_transcription_consent;
    var cloudFootText = "Requires network + explicit consent · currently " + (cloudOn ? "on" : "off");
    if (!ta) {
      // Not "coming soon" and not an error — the same honesty rule the notes panel already
      // follows for key_missing/not_configured: say the feature is not usable right now rather
      // than hiding the card or implying it works. Selecting it still switches the mode (so the
      // Settings intent is recorded), but `listening.rs` falls back to on-device and says so on
      // the console the moment "Start listening" is pressed — this card cannot know that live
      // detail without a running session, so it states its OWN honest scope: not ready to start.
      cloudFootText += " · not available right now on this machine";
    }
    var cloudFoot = el("p", "pp-radio-foot", cloudFootText);

    var cloud = transcriptionCard({
      id: "pp-radio-cloud",
      selected: mode === "cloud",
      title: "Cloud transcription",
      badgeCls: "pp-badge-optin",
      badgeText: "☁ OPT-IN",
      desc: tp && tp.name
        ? "Higher accuracy via " + tp.name + "."
        : "Higher accuracy via a cloud speech service.",
      warnNode: warn,
      footNode: cloudFoot,
      onSelect: function () {
        // Opt in (grant consent) THEN switch mode — the only path that ungates cloud audio.
        // If the host REJECTS the consent grant, do NOT switch to cloud: resync to the last
        // backend-confirmed state so the card never shows a cloud posture the backend didn't
        // authorise (trust — a failed consent step must not be papered over).
        invoke("set_cloud_consent", { kind: "transcription", enabled: true })
          .then(function () { return mutate("set_transcription_mode", { mode: "cloud" }); })
          .catch(resync);
      },
    });

    transEl.appendChild(onDevice);
    transEl.appendChild(cloud);
  }

  function onRadioKeydown(e) {
    var cards = Array.prototype.slice.call(transEl.querySelectorAll(".pp-radio-card"));
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

  // ==================================================================================
  // 3 · SELAHCUE AI · SERMON NOTES
  // ==================================================================================
  function renderAi() {
    aiEl.textContent = "";

    // --- provider header: identity + honest status pills ---
    var head = el("div", "pp-ai-head");
    var id = el("div", "pp-ai-id");
    var logo = el("span", "pp-ai-logo", "✦");
    logo.setAttribute("aria-hidden", "true");
    id.appendChild(logo);
    var idcol = el("div", "pp-ai-idcol");
    var titlerow = el("div", "pp-ai-titlerow");
    // The provider is NAMED (FR-132), from the backend's own descriptor. Hardcoding "SelahCue AI"
    // stopped being true the moment OpenAI generated the notes, and so did "no accounts, keys or
    // billing to manage" — a developer key is an account, a key and a bill.
    var np = view.notes_provider || null;
    var status = view.cloud_status || "not_configured";
    titlerow.appendChild(el("span", "pp-ai-title", np && np.name ? np.name : "AI sermon notes"));
    if (np && np.developer_key) {
      titlerow.appendChild(badge("pp-badge-dev", "DEVELOPER KEY"));
    } else if (status === "hosted") {
      titlerow.appendChild(badge("pp-badge-included", "INCLUDED"));
    }
    idcol.appendChild(titlerow);
    idcol.appendChild(el("span", "pp-ai-sub", providerSubtitle(status, np)));
    id.appendChild(idcol);
    head.appendChild(id);

    var statusEl = el("div", "pp-ai-status");
    if (view.notes_available && np) {
      // ONLY when the backend confirms notes can actually be generated AND says by whom.
      statusEl.appendChild(pill("pp-pill-ok", "Available"));
      if (np.developer_key) {
        var dev = pill("pp-pill-info", np.name + (np.model ? " · " + np.model : ""));
        dev.title = "Notes are generated by " + np.name +
          " using a developer key on this machine. This is not the shipping configuration.";
        statusEl.appendChild(dev);
      } else {
        statusEl.appendChild(pill("pp-pill-info", "Cloud connected"));
      }
    } else if (status === "key_missing") {
      // The feature is built in; the key is not there. Distinct from "coming soon", because the
      // reader can do something about this one.
      var nokey = pill("pp-pill-muted", "No key configured");
      nokey.title = "Sermon-note generation is built into this app, but no developer API key was " +
        "found. Add OPENAI_API_KEY to the .env file at the repository root.";
      statusEl.appendChild(nokey);
    } else {
      // Honest: no note provider is wired up in this build at all.
      var soon = pill("pp-pill-muted", "Coming soon");
      soon.title = "Sermon-note generation isn’t available in this build yet.";
      statusEl.appendChild(soon);
    }
    head.appendChild(statusEl);
    aiEl.appendChild(head);

    // --- consent banner (green) + actionable cloud-notes consent toggle ---
    //
    // Copy corrected per TRANSCRIPTS-2.0-HANDOFF.md §13 (17tnw2b0ntd): the old line named
    // "your completed transcript" and "press Generate" — both untrue once Generate itself moved
    // off this card. The wording is anchored to the actual data path (`transcript_generate_notes`,
    // `selahcue-cloud/src/transcript_bounds.rs`'s clamp) rather than to this card's own controls.
    var consent = el("div", "pp-consent");
    consent.appendChild(el("span", "pp-consent-ico", "🔒"));
    // Wording agreed with the owner from Shadow's privacy review (17tnw2b0ntd): it states what the
    // code actually enforces (an ENDED transcript, text only, reviewed and confirmed first) and does
    // NOT claim "never live audio" — cloud transcription, a separate setting just above, streams audio.
    consent.appendChild(el("span", "pp-consent-text",
      "Sermon notes are made from text only: the complete saved transcript of a recording that has " +
      "ended, up to 400,000 characters. Nothing is sent while that transcript is still recording, " +
      "and nothing is sent until you review the exact text and confirm. Cloud transcription " +
      "(above) is a separate setting and does stream microphone audio while it is on."));
    consent.appendChild(toggle(
      "pp-consent-notes", view.cloud_notes_consent,
      "Enable cloud processing for sermon notes",
      function (on) { mutate("set_cloud_consent", { kind: "notes", enabled: on }); }
    ));
    aiEl.appendChild(consent);

    // --- template + translation selects (grid; each select is width:100% so it can't collapse) ---
    var fields = el("div", "pp-fields");
    fields.appendChild(selectField(
      "pp-template", "Default notes template",
      view.notes_templates, "value", "label", view.notes_template, false,
      function (val) { mutate("set_notes_template", { template: val }); }
    ));
    fields.appendChild(selectField(
      "pp-translation", "Preferred Bible translation",
      view.translations, "code", "name", view.preferred_translation, true,
      function (val) { mutate("set_preferred_translation", { code: val }); }
    ));
    aiEl.appendChild(fields);

    // --- INCLUDE IN NOTES — 8 switches in two explicit columns (matches the frame's order;
    //     86akgqdwc added "Podcast show notes" and "Short description", one per column so
    //     the 3/3 split becomes 4/4 rather than lopsided) ---
    aiEl.appendChild(el("p", "pp-seclabel pp-seclabel-inline", "INCLUDE IN NOTES"));
    var inc = view.include || {};
    var cols = el("div", "pp-inc-cols");
    var left = el("div", "pp-inc-col");
    var right = el("div", "pp-inc-col");
    left.appendChild(includeRow("prayer_points", "Prayer points", inc.prayer_points));
    left.appendChild(includeRow("scripture_extraction", "Scripture extraction", inc.scripture_extraction));
    left.appendChild(includeRow("social_excerpts", "Social excerpts", inc.social_excerpts));
    left.appendChild(includeRow("podcast_show_notes", "Podcast show notes", inc.podcast_show_notes));
    right.appendChild(includeRow("chapter_markers", "Chapter markers", inc.chapter_markers));
    right.appendChild(includeRow("notable_quotations", "Notable quotations", inc.notable_quotations));
    right.appendChild(includeRow("short_summary", "Short summary", inc.short_summary));
    right.appendChild(includeRow("short_description", "Short description", inc.short_description));
    cols.appendChild(left);
    cols.appendChild(right);
    aiEl.appendChild(cols);

    // --- link to the Transcripts page (Figma 1135:78; TRANSCRIPTS-2.0-HANDOFF.md §13) ---
    //
    // Per D1 (17tnw2b0ntd), Generate is removed from this card entirely — notes are generated
    // only from a saved, ended transcript on the Transcripts page, never a live in-progress one.
    // This is navigation, not an action, so it is styled and marked up as a link, not a button.
    // No preview/result/quota apparatus lives here any more; see transcripts.js for the single
    // remaining Generate flow (full-transcript, post-service only).
    var linkRow = el("div", "pp-ai-link-row");
    var link = el("a", "pp-ai-link", "Open Transcripts to generate sermon notes →");
    link.href = "#";
    link.id = "pp-open-transcripts";
    link.addEventListener("click", function (e) {
      e.preventDefault();
      // `showSurface`/`navGo` are private closures inside app.js's IIFE, not exposed on
      // `window` — this link reuses the real "Transcript & Notes" app-menu item's own click
      // handler (same route ⌘7 now takes, D2) rather than inventing a second navigation path
      // that could silently drift from it.
      var navItem = document.querySelector('.nav-item[data-surface="transcripts"]');
      if (navItem) navItem.click();
    });
    linkRow.appendChild(link);
    linkRow.appendChild(el("p", "pp-ai-link-sub",
      "Notes are generated only on a stored, ended transcript — never from here."));
    aiEl.appendChild(linkRow);
  }

  // The one-line honest description of who generates the notes, per status. Kept beside the four
  // states so adding a state without adding its copy is a visible omission rather than a silent
  // fall-through to a sentence that is no longer true.
  function providerSubtitle(status, np) {
    if (status === "direct_provider" && np) {
      return "Sermon notes are generated by " + np.name +
        (np.model ? " (" + np.model + ")" : "") +
        " using a developer key stored on this machine. This is a development setup, not the " +
        "shipping configuration.";
    }
    if (status === "hosted" && np) {
      return "Sermon notes are generated by " + np.name + " — no accounts, keys or billing to manage.";
    }
    if (status === "key_missing") {
      return "Sermon-note generation is built in, but no developer API key was found on this " +
        "machine, so nothing can be generated yet.";
    }
    return "Sermon-note generation isn’t available in this build yet.";
  }

  // A labelled <select> inside a chevron wrapper. Rendered in a grid cell at width:100% so it can
  // never collapse to a sliver the way a flex-child <select> does in WKWebView.
  function selectField(id, label, options, valueKey, labelKey, selected, gold, onChange) {
    var field = el("div", "pp-field");
    var lab = el("label", "pp-field-label", label);
    lab.setAttribute("for", id);
    field.appendChild(lab);
    var wrap = el("div", "pp-select-wrap");
    var sel = document.createElement("select");
    sel.id = id;
    sel.className = "pp-select" + (gold ? " pp-select-gold" : "");
    if (!options || !options.length) {
      var opt0 = document.createElement("option");
      opt0.value = "";
      opt0.textContent = "—";
      sel.appendChild(opt0);
      sel.disabled = true;
    } else {
      options.forEach(function (o) {
        var opt = document.createElement("option");
        opt.value = o[valueKey];
        opt.textContent = o[labelKey];
        if (o[valueKey] === selected) opt.selected = true;
        sel.appendChild(opt);
      });
    }
    sel.addEventListener("change", function () { onChange(sel.value); });
    wrap.appendChild(sel);
    field.appendChild(wrap);
    return field;
  }

  function includeRow(name, label, checked) {
    var row = el("div", "pp-inc-row");
    row.appendChild(el("span", "pp-inc-label", label));
    row.appendChild(toggle("pp-inc-" + name, checked, label,
      function (on) { mutate("set_include_flag", { name: name, enabled: on }); }));
    return row;
  }

  // ---------- render + activation ----------
  function render() {
    renderTranscription();
    renderAi();
  }

  // Called by app.js showSurface("settings"). Loads the authoritative view, then renders. Without a
  // host it renders the offline-first defaults so the panel is never blank.
  //
  // 17tnw2b0ntd: this card no longer holds any sermon-note draft state at all (that whole
  // apparatus — Generate, preview, result, edit, regenerate — moved to transcripts.js, D1). A
  // draft is never fetched or redrawn here; render() is now just the consent/provider settings.
  window.settingsActivate = function () {
    invoke("providers_view")
      .then(function (v) {
        view = v || defaultView();
        render();
      })
      .catch(function () { view = defaultView(); render(); });
  };

  // APG radiogroup keyboard (attached ONCE — Arrow keys move + select; Space/Enter selects). The
  // group container (#pp-trans) persists across re-renders, so a single delegated listener suffices
  // and never accumulates.
  transEl.addEventListener("keydown", onRadioKeydown);

  // First paint with defaults so the DOM exists even before the first activation (keeps the surface
  // non-empty if styled/inspected pre-activation).
  render();
})();
