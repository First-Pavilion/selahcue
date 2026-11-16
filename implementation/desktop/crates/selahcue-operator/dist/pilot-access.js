// Safe pilot status shared by Providers & Privacy and Transcripts. Credentials never enter JS.
(function () {
  "use strict";
  var states = ["available", "unavailable", "rejected", "expired"];
  function normalize(raw, now) {
    if (raw == null) return null; // ordinary build, including older host fixtures
    var expiry = raw.effective_expiry_unix_seconds;
    var validExpiry = Number.isSafeInteger(expiry) && expiry > 0 && expiry <= 253402300799;
    var valid = typeof raw === "object" && states.indexOf(raw.state) >= 0 &&
      states.indexOf(raw.notes_state) >= 0 && states.indexOf(raw.transcription_state) >= 0 &&
      (validExpiry || expiry === null);
    var validSource = typeof raw.notes_uses_pilot === "boolean";
    // Missing/malformed source metadata cannot confer a hosted exemption.
    var usesPilot = !validSource || raw.notes_uses_pilot;
    var notes = valid && validSource ? raw.notes_state : "unavailable";
    var transcription = valid ? raw.transcription_state : "unavailable";
    var validClock = Number.isFinite(now) && now >= 0;
    if (!validClock || !validExpiry) {
      if (usesPilot && notes === "available") notes = "unavailable";
      if (transcription === "available") transcription = "unavailable";
    }
    if (valid && validExpiry && validClock && now >= expiry) {
      if (usesPilot) notes = "expired";
      transcription = "expired";
    }
    var state = states[Math.max(usesPilot ? states.indexOf(notes) : 0, states.indexOf(transcription))];
    return {state: state, notes_state: notes, transcription_state: transcription,
      notes_uses_pilot: usesPilot,
      effective_expiry_unix_seconds: valid && validExpiry ? expiry : null,
      replacement_required: (usesPilot && notes !== "available") || transcription !== "available"};
  }
  function laneState(status, lane) {
    return status && (lane === "transcription" ? status.transcription_state : status.notes_state);
  }
  function message(status, lane) {
    if (!status || (lane !== "transcription" && status.notes_uses_pilot === false)) return "";
    var name = lane === "transcription" ? "cloud transcription" : "notes";
    var state = laneState(status, lane);
    if (state === "available") {
      return "Pilot " + name + " access is available until " +
        new Date(status.effective_expiry_unix_seconds * 1000).toISOString().replace("T", " ").replace(".000Z", " UTC") + ".";
    }
    var reason = state === "expired" ? "expired" : state === "rejected" ? "was rejected" : "is unavailable";
    return "Pilot access for " + name + " " + reason + ". Install a current pilot build or contact the pilot coordinator. " +
      "Live presentation and available on-device transcription are unaffected.";
  }
  function errorMessage(code) {
    if (code === "pilot_expired") return message({notes_state: "expired"}, "notes");
    if (code === "pilot_access_rejected") return message({notes_state: "rejected"}, "notes");
    if (code === "pilot_unavailable") return message({notes_state: "unavailable"}, "notes");
    return null;
  }

  var raw = null, version = 0, generation = 0, timer = null, pending = false, again = false;
  var watchers = [], suspended = false, attached = false, observedExpiry = null;
  function current() {
    var value = normalize(raw, Math.floor(Date.now() / 1000));
    if (value && value.state === "expired" && value.effective_expiry_unix_seconds !== null) {
      observedExpiry = Math.max(observedExpiry || 0, value.effective_expiry_unix_seconds);
    }
    // A backwards wall-clock adjustment cannot revive access already observed expired
    // in this process. Native/provider enforcement still owns the security boundary.
    if (value && observedExpiry !== null && value.effective_expiry_unix_seconds !== null &&
        value.effective_expiry_unix_seconds <= observedExpiry) {
      value.state = value.transcription_state = "expired";
      if (value.notes_uses_pilot) value.notes_state = "expired";
      value.replacement_required = true;
    }
    return value;
  }
  function visible(w) { return !suspended && !document.hidden && w.visible(); }
  function active() { return watchers.some(visible); }
  function clearTimer() { if (timer !== null) clearTimeout(timer); timer = null; }
  function notify() {
    var value = current(), json = JSON.stringify(value);
    watchers.forEach(function (w) {
      if (!visible(w)) { w.last = undefined; return; }
      if (w.last !== json) { w.last = json; w.changed(value); }
    });
  }
  function schedule() {
    clearTimer();
    if (!active() || raw === null) return;
    var status = current(), wait = 2000;
    var remaining = status.effective_expiry_unix_seconds * 1000 - Date.now();
    if (remaining > 0) wait = Math.min(wait, remaining);
    timer = setTimeout(function () { timer = null; notify(); refresh(); schedule(); }, Math.max(1, wait));
  }
  function accept(value, expectedVersion) {
    if (expectedVersion !== version) return false;
    // Only safe fields survive normalization; provider response text is never retained.
    raw = normalize(value, Math.floor(Date.now() / 1000));
    version++;
    notify(); schedule();
    return true;
  }
  function refresh() {
    if (!active()) return;
    notify(); // clock boundary applies before IPC resolves
    if (pending) { again = true; return; }
    var invoke = window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke;
    if (!invoke) return;
    pending = true;
    var expectedVersion = version, expectedGeneration = generation;
    var request;
    try { request = invoke("pilot_access_status", {}); } catch (_) { request = Promise.reject(); }
    Promise.resolve(request).then(function (value) {
      if (active() && generation === expectedGeneration) accept(value, expectedVersion);
    }).catch(function () {
      // Keep the last safe state. A failed read cannot renew availability or turn an
      // ordinary build into a pilot; local expiry still applies through notify().
      notify();
    }).then(function () {
      pending = false;
      if (again && active()) { again = false; refresh(); }
      else { again = false; schedule(); }
    });
  }
  function visibilityChanged() {
    if (!active()) { generation++; again = false; clearTimer(); notify(); return; }
    notify(); refresh(); schedule();
  }
  function onFocus() { if (active()) { notify(); refresh(); } }
  function onHide() { suspended = true; visibilityChanged(); }
  function onShow() { suspended = false; visibilityChanged(); }
  function attach() {
    if (attached) return;
    attached = true;
    document.addEventListener("visibilitychange", visibilityChanged);
    window.addEventListener("focus", onFocus);
    window.addEventListener("pagehide", onHide);
    window.addEventListener("pageshow", onShow);
  }
  function detach() {
    if (!attached) return;
    attached = false;
    document.removeEventListener("visibilitychange", visibilityChanged);
    window.removeEventListener("focus", onFocus);
    window.removeEventListener("pagehide", onHide);
    window.removeEventListener("pageshow", onShow);
  }
  function watch(isVisible, changed) {
    var watcher = {visible: isVisible, changed: changed, last: undefined};
    watchers.push(watcher); attach(); visibilityChanged();
    return function () {
      watchers = watchers.filter(function (w) { return w !== watcher; });
      if (!watchers.length) detach();
      visibilityChanged();
    };
  }
  window.scPilotAccess = {normalize: normalize, laneState: laneState, message: message,
    errorMessage: errorMessage, current: current, revision: function () { return version; },
    accept: accept, refresh: refresh, watch: watch, visibilityChanged: visibilityChanged};
})();
