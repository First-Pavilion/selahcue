// Settings → Providers & Privacy surface (Design 2.0, Figma 338:124 — story 86ajxucue, backend
// 86ajy034h). Renders the panel body (#pp-trans + #pp-ai) from the REAL backend state returned by
// the operator commands and wires every control to its command:
//   providers_view · set_transcription_mode · set_cloud_consent · set_notes_template ·
//   set_preferred_translation · set_include_flag · set_account_token / clear_account_token ·
//   generate_sermon_notes
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

    var warn = el("div", "pp-warn");
    warn.appendChild(el("span", "pp-warn-ico", "⚠"));
    warn.appendChild(el("span", "pp-warn-text", "Streams live microphone audio to the provider while active"));

    var cloudOn = mode === "cloud" && view.cloud_transcription_consent;
    var cloudFoot = el("p", "pp-radio-foot",
      "Requires network + explicit consent · currently " + (cloudOn ? "on" : "off"));

    var cloud = transcriptionCard({
      id: "pp-radio-cloud",
      selected: mode === "cloud",
      title: "Cloud transcription",
      badgeCls: "pp-badge-optin",
      badgeText: "☁ OPT-IN",
      desc: "Higher accuracy via a cloud speech service.",
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

    // --- Generate + result region ---
    var gen = el("button", "pp-generate", "✦   Generate Sermon Notes");
    gen.type = "button";
    gen.id = "pp-generate";
    gen.addEventListener("click", onGenerate);
    aiEl.appendChild(gen);

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
  function onGenerate() {
    if (generating) return;
    generating = true;
    var btn = document.getElementById("pp-generate");
    if (btn) { btn.setAttribute("aria-busy", "true"); btn.disabled = true; }
    // This settings screen doesn't own a transcript; use the operator's completed transcript when
    // the app exposes one, else an empty string. The backend enforces consent/config first, so
    // nothing is fabricated and nothing leaves the device in the current build.
    var transcript = (typeof window.scCompletedTranscript === "string") ? window.scCompletedTranscript : "";
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

  function showGenResult(res) {
    if (!res || res.ok !== true) {
      var err = res || {};
      return showGenError(err.error || "malformed", err.message || "Something went wrong.");
    }
    var r = genResultEl();
    if (!r) return;
    r.className = "pp-gen-result pp-gen-ok";
    r.setAttribute("role", "status"); // a completed draft is a polite status, not an alert
    var d = res.draft || {};
    var hd = el("div", "pp-gen-hdr");
    hd.setAttribute("role", "status");
    var provider = res.provider ? res.provider : "AI sermon notes";
    hd.appendChild(el("span", "pp-gen-badge", (res.degraded ? "Local draft" : provider)));
    hd.appendChild(el("span", "pp-gen-title", d.title || "Sermon notes"));
    // FR-123: a model draft is labelled as one. The backend sets `ai_generated` from the provider
    // that actually SERVED the draft, so a degraded offline scaffold is not mislabelled as AI.
    if (res.ai_generated) {
      hd.appendChild(el("span", "pp-gen-ai-label", res.ai_label || "AI-generated draft"));
    }
    r.appendChild(hd);
    // FR-128: the fabrication warning travels WITH the draft, never separately and never omitted.
    // The backend guarantees `disclosure` is non-null exactly when `ai_generated`, so this cannot
    // render a label without its warning.
    if (res.ai_generated && res.disclosure) {
      var disc = el("p", "pp-gen-disclosure", res.disclosure);
      disc.setAttribute("role", "note");
      r.appendChild(disc);
    }
    // FR-135: a degraded draft says so in words, not just via a badge. The operator asked for AI
    // notes and got an offline outline instead; showing the scaffold in silence would read as
    // though it WERE the notes they asked for — the same under-reporting the AI label prevents,
    // pointing the other way. `degraded_notice` is non-null exactly when `degraded`.
    if (res.degraded && res.degraded_notice) {
      var deg = el("p", "pp-gen-degraded", res.degraded_notice);
      deg.setAttribute("role", "note");
      r.appendChild(deg);
    }
    if (d.summary) r.appendChild(el("p", "pp-gen-summary", d.summary));
    (d.sections || []).forEach(function (s) {
      r.appendChild(el("p", "pp-gen-sec-h", s.heading || ""));
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
    }
    // A returned quota is authoritative — reflect it (and it will drive the meter on next render).
    if (res.quota && typeof res.quota.limit === "number") {
      view.quota = res.quota;
      var meterHost = document.querySelector(".pp-quota");
      if (meterHost && meterHost.parentNode) meterHost.parentNode.replaceChild(renderQuota(), meterHost);
    }
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
    // quota_exceeded / transport / malformed → surface the message.
    r.className = "pp-gen-result pp-gen-err";
    r.setAttribute("role", "alert");
    var label = code === "quota_exceeded" ? "Monthly limit reached" : "Couldn’t generate notes";
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
  window.settingsActivate = function () {
    invoke("providers_view")
      .then(function (v) { view = v || defaultView(); render(); })
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
