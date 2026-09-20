// Settings → Providers & Privacy surface (Design 2.0, Figma 338:124 — story 86ajxucue, backend
// 86ajy034h). Renders the panel body (#pp-trans + #pp-ai) from the REAL backend state returned by
// the operator commands and wires every control to its command:
//   providers_view · set_transcription_mode · set_cloud_consent · set_notes_template ·
//   set_preferred_translation · set_include_flag · set_account_token / clear_account_token ·
//   generate_sermon_notes · load_sermon_note_draft · update_sermon_note_draft
//
// PERSISTENCE (86akgqdv0; FR-123 "editable" half): a successful generate is saved by the backend
// against its source transcript (best-effort — see `generate_sermon_notes`'s Rust doc comment),
// which returns a `transcript_id`. `load_sermon_note_draft` restores that saved draft on panel
// activation, so it survives a restart. `update_sermon_note_draft` persists an edit; the AI-
// generated label and FR-128 disclosure are re-read from the backend's response after a save, not
// assumed unchanged client-side, so an edit can never visually drift from what is actually stored.
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
// `quota` is still null and there is still NO metering, so the placeholder stays — NEVER a
// fabricated "12 / 40". A generation counter or session tally would be exactly the invented meter
// this file refuses to draw.
//
// Generate is consent-gated end to end: the backend returns `consent_required` when cloud-notes
// consent is off (we prompt to opt in) and `not_configured` when nothing can serve the request.
// A returned draft carries `ai_generated` + `disclosure`; both are rendered together and neither is
// rendered alone (FR-123/128). Nav + activation live in app.js (showSurface → settingsActivate);
// this module owns the surface body and loads after app.js.
//
// The transcript Generate sends is `window.scCompletedTranscript`, a bridge app.js sets on every
// poll from its own host-authoritative `view.transcript` (finalised segments only, never the
// in-progress partial line) — this screen has no transcript store of its own. Below the floor in
// `MIN_TRANSCRIPT_CHARS`, Generate refuses before any network call (Vera, PERF-3) instead of
// billing for a draft fabricated from nothing.
//
// Generate does not send on click. It opens a review step (openGenPreview) that renders the EXACT
// string about to be sent and waits for an explicit Confirm; Cancel sends nothing. That's what
// makes the footnote under the button true rather than aspirational (F-5 — Sana/Quinn, both
// blocking): the promise is "you'll see exactly what's sent and confirm before anything is
// generated", so the preview is built from the same string, not a re-derived one, and nothing
// reaches `invoke("generate_sermon_notes", …)` outside confirmGenerate().
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
    var consent = el("div", "pp-consent");
    consent.appendChild(el("span", "pp-consent-ico", "🔒"));
    consent.appendChild(el("span", "pp-consent-text",
      "Only your completed transcript is sent for processing — never live audio, and never during the service. Nothing is sent until you press Generate."));
    consent.appendChild(toggle(
      "pp-consent-notes", view.cloud_notes_consent,
      "Enable cloud processing for sermon notes",
      function (on) { mutate("set_cloud_consent", { kind: "notes", enabled: on }); }
    ));
    aiEl.appendChild(consent);

    // --- quota meter — real numbers only; honest placeholder when the server hasn't reported one ---
    aiEl.appendChild(renderQuota());

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

    // --- INCLUDE IN NOTES — 6 switches in two explicit columns (matches the frame's order) ---
    aiEl.appendChild(el("p", "pp-seclabel pp-seclabel-inline", "INCLUDE IN NOTES"));
    var inc = view.include || {};
    var cols = el("div", "pp-inc-cols");
    var left = el("div", "pp-inc-col");
    var right = el("div", "pp-inc-col");
    left.appendChild(includeRow("prayer_points", "Prayer points", inc.prayer_points));
    left.appendChild(includeRow("scripture_extraction", "Scripture extraction", inc.scripture_extraction));
    left.appendChild(includeRow("social_excerpts", "Social excerpts", inc.social_excerpts));
    right.appendChild(includeRow("chapter_markers", "Chapter markers", inc.chapter_markers));
    right.appendChild(includeRow("notable_quotations", "Notable quotations", inc.notable_quotations));
    right.appendChild(includeRow("short_summary", "Short summary", inc.short_summary));
    cols.appendChild(left);
    cols.appendChild(right);
    aiEl.appendChild(cols);

    // --- Generate + review-before-send + result region ---
    var gen = el("button", "pp-generate", "✦   Generate Sermon Notes");
    gen.type = "button";
    gen.id = "pp-generate";
    gen.addEventListener("click", onGenerate);
    aiEl.appendChild(gen);

    // The preview/confirm step (F-5, Sana/Quinn): built rather than left as a promise the copy
    // below makes and the code doesn't keep. Populated by openGenPreview() with the EXACT string
    // about to be sent — never re-derived at Confirm time — so what the operator reads here is
    // guaranteed byte-identical to what leaves the device.
    var preview = el("div", "pp-gen-preview");
    preview.id = "pp-gen-preview";
    preview.hidden = true;
    aiEl.appendChild(preview);

    var result = el("div", "pp-gen-result");
    result.id = "pp-gen-result";
    result.hidden = true;
    aiEl.appendChild(result);

    // --- footnote ---
    var foot = el("div", "pp-footnote");
    foot.appendChild(el("span", "pp-footnote-ico", "🔒"));
    foot.appendChild(el("span", null, "You’ll see exactly what’s sent and confirm before anything is generated."));
    aiEl.appendChild(foot);
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

  function renderQuota() {
    var box = el("div", "pp-quota");
    if (view.quota && typeof view.quota.limit === "number") {
      var q = view.quota;
      var left = el("div", "pp-quota-left");
      var num = el("div", "pp-quota-num");
      // Guard the sub-fields: a quota with `limit` but a missing `used`/`remaining` must never
      // print the literal "undefined".
      var used = (typeof q.used === "number") ? q.used : 0;
      num.appendChild(el("span", "pp-quota-used", String(used)));
      num.appendChild(el("span", "pp-quota-limit", "/ " + q.limit));
      left.appendChild(num);
      left.appendChild(el("span", "pp-quota-cap", "sermon-note generations this month"));
      box.appendChild(left);

      var right = el("div", "pp-quota-right");
      var meter = el("div", "pp-meter");
      var pct = q.limit > 0 ? Math.max(0, Math.min(100, (used / q.limit) * 100)) : 0;
      var fill = el("div", "pp-meter-fill");
      fill.style.width = pct + "%";
      meter.appendChild(fill);
      right.appendChild(meter);
      var resets = q.resets_label ? " · resets " + q.resets_label : "";
      var remaining = (typeof q.remaining === "number") ? q.remaining : Math.max(0, q.limit - used);
      right.appendChild(el("span", "pp-quota-reset", remaining + " remaining" + resets));
      box.appendChild(right);
    } else {
      // No server-reported quota → say so honestly. NO fabricated "12 / 40".
      box.classList.add("pp-quota-empty");
      var lz = el("div", "pp-quota-left");
      var numz = el("div", "pp-quota-num");
      numz.appendChild(el("span", "pp-quota-used pp-quota-dim", "—"));
      lz.appendChild(numz);
      lz.appendChild(el("span", "pp-quota-cap", "Usage metering isn’t available yet — no generations are counted."));
      box.appendChild(lz);
      var rz = el("div", "pp-quota-right");
      var meterz = el("div", "pp-meter");
      meterz.appendChild(el("div", "pp-meter-fill pp-meter-empty")); // 0% — honest empty track
      rz.appendChild(meterz);
      rz.appendChild(el("span", "pp-quota-reset", "Not available yet"));
      box.appendChild(rz);
    }
    return box;
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

  // ---------- Generate flow (consent-gated end to end by the backend) ----------
  var generating = false;

  // The floor below which a "transcript" is empty or near-empty noise rather than something
  // worth a model call (Vera, PERF-3): an empty transcript was being sent and billed as a fully
  // fabricated draft, on the same click a mis-wire (defect 1) used to make silently. This is NOT
  // a calibrated "enough content to summarise" threshold — no such number exists anywhere in the
  // product spec — it only catches the empty/blank-click case and near-empty noise, refused here,
  // before any network call is made.
  var MIN_TRANSCRIPT_CHARS = 20;

  // This settings screen doesn't own a transcript; it reads the operator's completed transcript
  // from the bridge app.js sets on every poll (syncTranscript → window.scCompletedTranscript),
  // or an empty string when the app doesn't expose one (e.g. dist opened standalone).
  function onGenerate() {
    if (generating) return;
    var previewEl = document.getElementById("pp-gen-preview");
    if (previewEl && !previewEl.hidden) return; // already reviewing — Cancel/Confirm decide next
    var transcript = (typeof window.scCompletedTranscript === "string") ? window.scCompletedTranscript : "";
    var trimmed = transcript.trim();
    if (trimmed.length === 0) {
      showGenError("no_transcript", "Nothing has been transcribed yet, so nothing was sent.");
      return;
    }
    if (trimmed.length < MIN_TRANSCRIPT_CHARS) {
      showGenError("transcript_too_short", "The transcript is too short to generate sermon notes from, so nothing was sent.");
      return;
    }
    openGenPreview(transcript);
  }

  // Renders the exact text about to be sent, plus who it's going to, and waits for an explicit
  // Confirm click. Nothing is sent until that click — this is what makes the footnote below the
  // button ("You'll see exactly what's sent and confirm before anything is generated.") true
  // instead of aspirational.
  function openGenPreview(transcript) {
    var box = document.getElementById("pp-gen-preview");
    var btn = document.getElementById("pp-generate");
    if (!box) return;
    box.textContent = "";

    var np = view.notes_provider || null;
    var providerName = np && np.name ? np.name : "the configured provider";

    var heading = el("h3", "pp-gen-preview-title", "Review before sending");
    heading.id = "pp-gen-preview-title";
    heading.tabIndex = -1;
    box.appendChild(heading);

    box.appendChild(el("p", "pp-gen-preview-desc",
      "This exact text (" + transcript.length + " characters) will be sent to " + providerName +
      ". Nothing leaves this device until you press Confirm."));

    // L-2 (Quinn, Cody, Vera — independently): the description above is true but incomplete.
    // `transcript` is window.scCompletedTranscript, which is the operator's bounded RECENT tail
    // (app.js's syncTranscript(), not a full-service store — FR-130 is that store and isn't built
    // yet), so after a long sermon this preview is honestly small while still reading as complete.
    // Say so here, where the operator is actually looking, not only in a code comment or the PR
    // body — a later engineer would find those; the operator reviewing THIS draft would not.
    box.appendChild(el("p", "pp-gen-preview-desc pp-gen-preview-scope",
      "This is drawn from the most recently transcribed speech, not the whole service — for a " +
      "long sermon, that may be just the last few minutes."));

    // Untrusted transcript text → el() sets it via textContent, never innerHTML.
    var text = el("div", "pp-gen-preview-text", transcript);
    text.tabIndex = 0;
    box.appendChild(text);

    var actions = el("div", "pp-gen-preview-actions");
    var cancel = el("button", "pp-gen-preview-cancel", "Cancel");
    cancel.type = "button";
    cancel.id = "pp-gen-preview-cancel";
    cancel.addEventListener("click", function () { closeGenPreview(true); });
    actions.appendChild(cancel);

    var confirm = el("button", "pp-gen-preview-confirm", "Confirm — send to " + providerName);
    confirm.type = "button";
    confirm.id = "pp-gen-preview-confirm";
    confirm.addEventListener("click", function () { confirmGenerate(transcript); });
    actions.appendChild(confirm);
    box.appendChild(actions);

    box.setAttribute("role", "group");
    box.setAttribute("aria-labelledby", "pp-gen-preview-title");
    box.hidden = false;
    if (btn) btn.hidden = true;
    heading.focus();
  }

  function closeGenPreview(refocusButton) {
    var box = document.getElementById("pp-gen-preview");
    var btn = document.getElementById("pp-generate");
    if (box) { box.hidden = true; box.textContent = ""; }
    if (btn) {
      btn.hidden = false;
      if (refocusButton) btn.focus();
    }
  }

  // The actual send — reachable ONLY from openGenPreview's Confirm button, and always with the
  // SAME string the operator just read there (never re-read from window.scCompletedTranscript,
  // which a live 1s poll could have advanced while the preview was open — "what you saw" and
  // "what was sent" must be the same string, not just the same source).
  function confirmGenerate(transcript) {
    closeGenPreview(false);
    generating = true;
    var btn = document.getElementById("pp-generate");
    if (btn) { btn.setAttribute("aria-busy", "true"); btn.disabled = true; }
    invoke("generate_sermon_notes", { transcript: transcript })
      .then(showGenResult)
      .catch(function (e) { showGenError("transport", String(e && e.message ? e.message : e)); })
      .then(function () {
        generating = false;
        var b = document.getElementById("pp-generate");
        if (b) { b.removeAttribute("aria-busy"); b.disabled = false; }
      });
  }

  function genResultEl() {
    var r = document.getElementById("pp-gen-result");
    // Clear the previous role too: a prior error left role="alert" here; a following success must
    // not announce its draft as an alert (each caller sets the correct role for its own content).
    if (r) { r.hidden = false; r.textContent = ""; r.removeAttribute("role"); }
    return r;
  }

  // ---------- persisted draft state + editing (86akgqdv0; FR-123 "editable" half) ----------
  //
  // `currentDraft` is the single source of truth for what #pp-gen-result shows — set by a
  // successful generate (showGenResult), a draft restored on panel activation
  // (loadPersistedDraft), or a saved edit (saveDraftEdit). It never accumulates: each setter
  // REPLACES it wholesale, the same discipline `view` above already follows.
  //
  // `transcriptId` is null exactly when local persistence was unavailable/failed for this draft
  // (the backend's save-on-generate is best-effort) — editing is hidden in that case because
  // there is nothing to key a save off; the draft itself still renders, unchanged from before
  // 86akgqdv0.
  var currentDraft = null;
  var editingDraft = false;

  // Test-only hook (86akgqdv0, Quinn's QA review of PR #33): resets in-page draft state so a
  // headless check can simulate "the operator just restarted the app" — a real restart clears
  // this module's closure state entirely, which a single continuous headless page session
  // otherwise never naturally does. Mirrors `window.__resetDeckPreviewKey` in app.js (the same
  // pattern already used elsewhere in this codebase for a driver-only reset hook). Calling
  // `window.settingsActivate()` after this exercises `loadPersistedDraft()`'s real fetch-and-
  // render path exactly as a genuine restart would, closing the gap the review flagged: this
  // path used to be provable only by a DB-level test, a wire-contract test, and a manual code
  // trace — never a machine-checked render.
  window.__resetSermonNoteDraftForTest = function () {
    currentDraft = null;
    editingDraft = false;
  };

  function showGenResult(res) {
    if (!res || res.ok !== true) {
      var err = res || {};
      return showGenError(err.error || "malformed", err.message || "Something went wrong.");
    }
    currentDraft = {
      transcriptId: (typeof res.transcript_id === "number") ? res.transcript_id : null,
      draft: res.draft || {},
      aiGenerated: !!res.ai_generated,
      aiLabel: res.ai_label || "AI-generated draft",
      disclosure: res.disclosure || null,
      provider: res.provider || "AI sermon notes",
      degraded: !!res.degraded,
      degradedNotice: res.degraded_notice || null,
    };
    editingDraft = false;
    renderCurrentDraft();
    // A returned quota is authoritative — reflect it (and it will drive the meter on next render).
    if (res.quota && typeof res.quota.limit === "number") {
      view.quota = res.quota;
      var meterHost = document.querySelector(".pp-quota");
      if (meterHost && meterHost.parentNode) meterHost.parentNode.replaceChild(renderQuota(), meterHost);
    }
  }

  // Restores a previously persisted draft (a prior session's generate, possibly since edited) so
  // it reappears after a restart, without requiring another Generate click. Silent no-op when
  // there is nothing to restore or no host connection — an absent draft is the common case, not
  // an error, and this must never overwrite a draft already on screen from THIS session's own
  // generate (e.g. a slow load racing a fast Generate click).
  function loadPersistedDraft() {
    invoke("load_sermon_note_draft").then(function (res) {
      if (!res || res.ok !== true || currentDraft) return;
      currentDraft = {
        transcriptId: (typeof res.transcript_id === "number") ? res.transcript_id : null,
        draft: res.draft || {},
        aiGenerated: !!res.ai_generated,
        aiLabel: res.ai_label || "AI-generated draft",
        disclosure: res.disclosure || null,
        provider: res.provider || "AI sermon notes",
        degraded: false,
        degradedNotice: null,
      };
      editingDraft = false;
      renderCurrentDraft();
    }).catch(function () {});
  }

  // Renders `currentDraft` (view or edit mode) into #pp-gen-result. The ONLY place either mode is
  // drawn, so view <-> edit is always a full re-render from the same state, never a partial DOM
  // patch that could drift from it.
  function renderCurrentDraft() {
    var r = genResultEl();
    if (!r || !currentDraft) return;
    r.className = "pp-gen-result pp-gen-ok";
    r.setAttribute("role", "status"); // a completed/restored draft is a polite status, not an alert
    if (editingDraft) renderDraftEditForm(r); else renderDraftView(r);
  }

  function renderDraftHeader(host) {
    var hd = el("div", "pp-gen-hdr");
    hd.setAttribute("role", "status");
    hd.appendChild(el("span", "pp-gen-badge", (currentDraft.degraded ? "Local draft" : currentDraft.provider)));
    hd.appendChild(el("span", "pp-gen-title", (currentDraft.draft && currentDraft.draft.title) || "Sermon notes"));
    // FR-123: a model draft is labelled as one — in EITHER mode, view or edit. Editing must never
    // silently remove this label; it is drawn from `currentDraft`, not from anything the edit form
    // itself could omit.
    if (currentDraft.aiGenerated) {
      hd.appendChild(el("span", "pp-gen-ai-label", currentDraft.aiLabel));
    }
    host.appendChild(hd);
    // FR-128: the fabrication warning travels WITH the draft, in either mode, never separately and
    // never omitted. The backend guarantees `disclosure` is non-null exactly when `ai_generated`.
    if (currentDraft.aiGenerated && currentDraft.disclosure) {
      var disc = el("p", "pp-gen-disclosure", currentDraft.disclosure);
      disc.setAttribute("role", "note");
      host.appendChild(disc);
    }
    // FR-135: a degraded draft says so in words, not just via a badge.
    if (currentDraft.degraded && currentDraft.degradedNotice) {
      var deg = el("p", "pp-gen-degraded", currentDraft.degradedNotice);
      deg.setAttribute("role", "note");
      host.appendChild(deg);
    }
  }

  // 86akc0tua: the operator explicitly requested this (an enabled toggle, or one of the
  // handful FR-122 always includes) and the draft came back with nothing for it. Copy is
  // agentless by design — it does not say "you asked" or "you switched this on", because
  // several sections (the outline included) are never toggled by anybody; and it does not
  // say the model failed or the sermon lacked the content, because neither is a claim this
  // screen can support (same prompt, same transcript produced 0 chapter markers on one run
  // and 7 on the next). Wording agreed with Uma (ui-ux-designer); copy verbatim, including
  // the em dash (—) and curly apostrophe (’) — do not let an editor ASCII-normalise
  // them.
  var EMPTY_REQUESTED_LINE = "Included in the request — nothing came back.";
  var EMPTY_REQUESTED_EXPLAINER = "The response doesn’t say why a requested section " +
    "comes back empty — the sermon may not have covered it, or this run may simply not " +
    "have returned it. Generating again may give a different result.";

  function hasCaveat(d, heading) {
    return !!(d.caveats && d.caveats.indexOf(heading) !== -1);
  }

  function renderDraftView(r) {
    var d = currentDraft.draft || {};
    // Both empty-requested strings are suppressed entirely for a degraded (offline
    // fallback) draft: `local.rs` deliberately pushes its own empty placeholder sections,
    // and DEGRADED_FALLBACK_NOTICE (rendered above, in renderDraftHeader) already explains
    // the emptiness — a second, contradictory-sounding message must not stack under it.
    // The backend already guarantees `caveats` is empty in this case; this is defence in
    // depth, reaffirming the ticket's own acceptance criterion rather than relying only on
    // that guarantee.
    var showEmptyState = !currentDraft.degraded;
    renderDraftHeader(r);
    if (d.summary) {
      r.appendChild(el("p", "pp-gen-summary", d.summary));
    } else if (showEmptyState && hasCaveat(d, "Summary")) {
      r.appendChild(el("p", "pp-gen-sec-h", "Summary"));
      r.appendChild(el("p", "pp-gen-empty", EMPTY_REQUESTED_LINE));
    }
    (d.sections || []).forEach(function (s) {
      r.appendChild(el("p", "pp-gen-sec-h", s.heading || ""));
      if (showEmptyState && s.empty_requested) {
        // Replaces the (would-be-empty) list for this section, in its own natural
        // position — empty sections are never collected at the bottom.
        r.appendChild(el("p", "pp-gen-empty", EMPTY_REQUESTED_LINE));
        return;
      }
      var ul = el("ul", "pp-gen-list");
      (s.items || []).forEach(function (it) { ul.appendChild(el("li", null, it)); });
      // FR-122 points/sub-points. Sub-points render as a NESTED list inside their parent point, so
      // the subordination the backend sent survives to the screen instead of being flattened into
      // one indistinguishable list.
      (s.points || []).forEach(function (pt) {
        var li = el("li", "pp-gen-point", pt && pt.text ? pt.text : "");
        var subs = (pt && pt.sub_points) || [];
        if (subs.length) {
          var sul = el("ul", "pp-gen-sublist");
          subs.forEach(function (sp) { sul.appendChild(el("li", null, sp)); });
          li.appendChild(sul);
        }
        ul.appendChild(li);
      });
      r.appendChild(ul);
    });
    if (d.scriptures && d.scriptures.length) {
      var sc = el("p", "pp-gen-scriptures");
      sc.appendChild(el("span", "pp-gen-sec-h", "Scriptures: "));
      sc.appendChild(el("span", "pp-gen-scr-list", d.scriptures.join(" · ")));
      r.appendChild(sc);
    } else if (showEmptyState && hasCaveat(d, "Scripture references")) {
      var scEmpty = el("p", "pp-gen-scriptures");
      scEmpty.appendChild(el("span", "pp-gen-sec-h", "Scriptures: "));
      scEmpty.appendChild(el("span", "pp-gen-empty", EMPTY_REQUESTED_LINE));
      r.appendChild(scEmpty);
    }
    // Once per draft, after everything else — never at the top, where the AI-disclosure and
    // degraded-notice pair (renderDraftHeader) must be read first.
    if (showEmptyState && d.caveats && d.caveats.length) {
      var explainer = el("p", "pp-gen-empty-explainer", EMPTY_REQUESTED_EXPLAINER);
      explainer.setAttribute("role", "note");
      r.appendChild(explainer);
    }
    // Editing needs a transcript id to save against — null only when local persistence itself was
    // unavailable/failed for this draft (see the `currentDraft` doc comment above).
    if (currentDraft.transcriptId != null) {
      var actions = el("div", "pp-gen-actions");
      var editBtn = el("button", "pp-gen-edit-btn", "Edit");
      editBtn.type = "button";
      editBtn.id = "pp-gen-edit";
      editBtn.addEventListener("click", function () { editingDraft = true; renderCurrentDraft(); });
      actions.appendChild(editBtn);
      r.appendChild(actions);
    }
  }

  function editField(labelText, inputEl, extraCls) {
    var wrap = el("label", "pp-gen-field" + (extraCls ? " " + extraCls : ""));
    wrap.appendChild(el("span", "pp-gen-field-label", labelText));
    wrap.appendChild(inputEl);
    return wrap;
  }

  // Editable text for existing title/summary/heading/item/point/sub-point wording. Deliberately
  // does NOT add UI to insert or remove a section/item/point — FR-123 asks for "editable", not a
  // structural outline builder; adding/removing entries is a reasonable later affordance, not
  // silently faked here.
  function renderDraftEditForm(r) {
    var d = currentDraft.draft || {};
    renderDraftHeader(r);

    var form = el("div", "pp-gen-edit-form");
    form.setAttribute("role", "group");
    form.setAttribute("aria-label", "Edit sermon notes draft");

    var titleInput = document.createElement("input");
    titleInput.type = "text";
    titleInput.id = "pp-edit-title";
    titleInput.value = d.title || "";
    form.appendChild(editField("Title", titleInput));

    var summaryInput = document.createElement("textarea");
    summaryInput.id = "pp-edit-summary";
    summaryInput.rows = 3;
    summaryInput.value = d.summary || "";
    form.appendChild(editField("Summary", summaryInput));

    var sectionsHost = el("div", "pp-gen-edit-sections");
    (d.sections || []).forEach(function (s, si) {
      var box = el("div", "pp-gen-edit-section");
      var headingInput = document.createElement("input");
      headingInput.type = "text";
      headingInput.className = "pp-edit-section-heading";
      headingInput.setAttribute("data-si", si);
      headingInput.value = s.heading || "";
      box.appendChild(editField("Heading", headingInput));

      var isOutline = (s.points || []).length > 0;
      if (isOutline) {
        (s.points || []).forEach(function (pt, pi) {
          var ptWrap = el("div", "pp-gen-edit-point");
          var ptInput = document.createElement("input");
          ptInput.type = "text";
          ptInput.className = "pp-edit-point-text";
          ptInput.setAttribute("data-si", si);
          ptInput.setAttribute("data-pi", pi);
          ptInput.value = (pt && pt.text) || "";
          ptWrap.appendChild(editField("Point", ptInput));
          (pt && pt.sub_points || []).forEach(function (sp, spi) {
            var spInput = document.createElement("input");
            spInput.type = "text";
            spInput.className = "pp-edit-subpoint-text";
            spInput.setAttribute("data-si", si);
            spInput.setAttribute("data-pi", pi);
            spInput.setAttribute("data-spi", spi);
            spInput.value = sp || "";
            ptWrap.appendChild(editField("Sub-point", spInput, "pp-gen-field-sub"));
          });
          box.appendChild(ptWrap);
        });
      } else {
        (s.items || []).forEach(function (it, ii) {
          var itInput = document.createElement("input");
          itInput.type = "text";
          itInput.className = "pp-edit-item-text";
          itInput.setAttribute("data-si", si);
          itInput.setAttribute("data-ii", ii);
          itInput.value = it || "";
          box.appendChild(editField("Item", itInput));
        });
      }
      sectionsHost.appendChild(box);
    });
    form.appendChild(sectionsHost);

    var actions = el("div", "pp-gen-preview-actions");
    var cancel = el("button", "pp-gen-preview-cancel", "Cancel");
    cancel.type = "button";
    cancel.id = "pp-gen-edit-cancel";
    cancel.addEventListener("click", function () { editingDraft = false; renderCurrentDraft(); });
    actions.appendChild(cancel);

    var save = el("button", "pp-gen-preview-confirm", "Save");
    save.type = "button";
    save.id = "pp-gen-save";
    save.addEventListener("click", function () { saveDraftEdit(form); });
    actions.appendChild(save);
    form.appendChild(actions);

    r.appendChild(form);
    titleInput.focus();
  }

  // A section round-tripped through the form is still empty — no non-blank item, no
  // point with non-blank text or a non-blank sub-point. Judged on content only, never
  // the heading, matching openai.rs's own emptiness test on the server side.
  function isStillEmpty(s) {
    var hasItem = (s.items || []).some(function (it) { return it && it.trim(); });
    if (hasItem) return false;
    return !(s.points || []).some(function (pt) {
      if (pt.text && pt.text.trim()) return true;
      return (pt.sub_points || []).some(function (sp) { return sp && sp.trim(); });
    });
  }

  // Reads the edit form's current input values back into the sections/points/items shape the
  // backend expects, preserving the flat-items-XOR-outline-points shape of each section (FR-122)
  // — never re-derived from scratch, always keyed off the SAME section/point/item positions
  // `renderDraftEditForm` drew the inputs at, so a value read back can never land on the wrong row.
  //
  // 86akc0tua remediation (Cody's second finding on PR #46 — the first, `generate`'s own
  // persistence call site, is fixed server-side by `sections_to_persist`; this is the OTHER
  // reachable route into the same persisted storage, and the backend has NO caveat data at
  // THIS call site to filter on: `NoteSectionInput` carries no `empty_requested` field, and
  // `update_sermon_note_draft` never sees a `NoteDraft` with caveats, only raw submitted
  // sections). A section that was `empty_requested` on the live view and is STILL empty after
  // reading the form (the operator did not fill it in) is dropped here, client-side, before
  // the payload is built — saving ANY edit elsewhere in the draft would otherwise silently
  // write that section's confusing "bare heading, no explanation" state straight into
  // storage. A section the operator DID fill in is kept: this is not a blanket "drop empty
  // sections" filter, only "don't re-persist the exact caveated-empty state unchanged."
  function readSectionsFromForm(form, sections) {
    return (sections || [])
      .map(function (s, si) {
        var headingEl = form.querySelector('.pp-edit-section-heading[data-si="' + si + '"]');
        var heading = headingEl ? headingEl.value : (s.heading || "");
        var isOutline = (s.points || []).length > 0;
        if (isOutline) {
          var points = (s.points || []).map(function (pt, pi) {
            var textEl = form.querySelector('.pp-edit-point-text[data-si="' + si + '"][data-pi="' + pi + '"]');
            var subPoints = (pt && pt.sub_points || []).map(function (sp, spi) {
              var sel = '.pp-edit-subpoint-text[data-si="' + si + '"][data-pi="' + pi + '"][data-spi="' + spi + '"]';
              var spEl = form.querySelector(sel);
              return spEl ? spEl.value : sp;
            });
            return { text: textEl ? textEl.value : (pt && pt.text) || "", sub_points: subPoints };
          });
          return { heading: heading, items: [], points: points, __empty_requested: !!s.empty_requested };
        }
        var items = (s.items || []).map(function (it, ii) {
          var itEl = form.querySelector('.pp-edit-item-text[data-si="' + si + '"][data-ii="' + ii + '"]');
          return itEl ? itEl.value : it;
        });
        return { heading: heading, items: items, points: [], __empty_requested: !!s.empty_requested };
      })
      .filter(function (s) { return !(s.__empty_requested && isStillEmpty(s)); })
      .map(function (s) { return { heading: s.heading, items: s.items, points: s.points }; });
  }

  function saveDraftEdit(form) {
    if (!currentDraft || currentDraft.transcriptId == null) return;
    var d = currentDraft.draft || {};
    var titleEl = document.getElementById("pp-edit-title");
    var summaryEl = document.getElementById("pp-edit-summary");
    var title = titleEl ? titleEl.value : (d.title || "");
    var summaryVal = summaryEl ? summaryEl.value : "";
    var sections = readSectionsFromForm(form, d.sections);
    var scriptures = d.scriptures || []; // scripture list editing is not in this ticket's scope

    var saveBtn = document.getElementById("pp-gen-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.setAttribute("aria-busy", "true"); }
    invoke("update_sermon_note_draft", {
      transcriptId: currentDraft.transcriptId,
      title: title,
      summary: summaryVal.trim() ? summaryVal : null,
      sections: sections,
      scriptures: scriptures,
    }).then(function (res) {
      if (!res || res.ok !== true) {
        var err = res || {};
        showGenError(err.error || "malformed", err.message || "The edit could not be saved.");
        return;
      }
      // Re-read the label/disclosure/provider back FROM the backend response, rather than assume
      // they survived unchanged client-side — the guarantee that editing can't drop them belongs
      // to the backend (`sermon_note_repo::update` cannot touch those columns), and this renders
      // exactly what it reports, not what the client hopes is still true.
      currentDraft = {
        transcriptId: currentDraft.transcriptId,
        draft: res.draft || {},
        aiGenerated: !!res.ai_generated,
        aiLabel: res.ai_label || currentDraft.aiLabel,
        disclosure: res.disclosure || null,
        provider: res.provider || currentDraft.provider,
        degraded: currentDraft.degraded,
        degradedNotice: currentDraft.degradedNotice,
      };
      editingDraft = false;
      renderCurrentDraft();
    }).catch(function (e) {
      showGenError("transport", String(e && e.message ? e.message : e));
    }).then(function () {
      var b = document.getElementById("pp-gen-save");
      if (b) { b.disabled = false; b.removeAttribute("aria-busy"); }
    });
  }

  function showGenError(code, message) {
    var r = genResultEl();
    if (!r) return;
    if (code === "not_configured") {
      // Two different truths arrive under one error code, and the panel tells them apart using the
      // status it already holds. "We haven't built it" and "you haven't supplied a key" call for
      // different things from the reader, and collapsing them wastes their time.
      r.className = "pp-gen-result pp-gen-info";
      r.setAttribute("role", "status");
      r.appendChild(el("span", "pp-gen-info-ico", "☁"));
      if (view.cloud_status === "key_missing") {
        r.appendChild(el("span", null,
          "No developer API key was found, so nothing was generated. Add OPENAI_API_KEY to the " +
          ".env file at the repository root and restart."));
      } else {
        r.appendChild(el("span", null,
          "Sermon-note generation isn’t available in this build yet."));
      }
      return;
    }
    if (code === "consent_required") {
      // Prompt to opt in, with a one-click "opt in & generate" recovery.
      r.className = "pp-gen-result pp-gen-err";
      r.setAttribute("role", "alert");
      r.appendChild(el("span", null,
        "Turn on cloud processing above to generate sermon notes."));
      var optin = el("button", "pp-optin-btn", "Opt in & generate");
      optin.type = "button";
      optin.id = "pp-optin-retry";
      optin.addEventListener("click", function () {
        invoke("set_cloud_consent", { kind: "notes", enabled: true })
          .then(apply)
          .then(onGenerate)
          .catch(function () {});
      });
      r.appendChild(optin);
      return;
    }
    // quota_exceeded / transport / malformed / no_transcript / transcript_too_short → surface the
    // message. The latter two (PERF-3) never reach here from a network response — onGenerate
    // refuses before any call is made — so their label says exactly that: nothing was sent.
    r.className = "pp-gen-result pp-gen-err";
    r.setAttribute("role", "alert");
    var label = code === "quota_exceeded" ? "Monthly limit reached"
      : code === "no_transcript" ? "No transcript yet"
      : code === "transcript_too_short" ? "Transcript too short"
      : "Couldn’t generate notes";
    r.appendChild(el("span", "pp-gen-err-t", label + " — "));
    r.appendChild(el("span", null, message || ""));
  }

  // ---------- render + activation ----------
  function render() {
    renderTranscription();
    renderAi();
  }

  // Called by app.js showSurface("settings"). Loads the authoritative view, then renders. Without a
  // host it renders the offline-first defaults so the panel is never blank.
  //
  // 86akgqdv0: render() rebuilds #pp-gen-result FRESH (empty) on every activation — including a
  // return visit to Settings within the same session, not only a cold app start — so the sermon-
  // note draft state has to be redrawn into it every time, not fetched-once. If this session
  // already holds `currentDraft` (an earlier generate/edit/load), just redraw it; otherwise fetch
  // the persisted draft from the backend. This is what makes "generate a draft, restart the app,
  // reopen the same transcript: the draft is still there" true from this panel, without requiring
  // another Generate click.
  window.settingsActivate = function () {
    invoke("providers_view")
      .then(function (v) {
        view = v || defaultView();
        render();
        if (currentDraft) renderCurrentDraft(); else loadPersistedDraft();
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
