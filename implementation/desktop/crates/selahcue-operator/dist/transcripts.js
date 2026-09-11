// Transcripts surface (86akcffvt / FR-130 core slice): every saved transcript (label · date ·
// duration · segment count), most recent first; selecting one opens a read-only, fully scrollable
// view of its complete stored text, plus whether sermon notes have already been generated from it
// (status only). Editing/corrections, the detected-scripture list, and generating notes from a
// selected transcript are all explicitly deferred — see the ticket's non-goals.
//
// DATA: `transcript_list` / `transcript_get`, read-only Tauri commands wired to 86ajtxzrn's
// `transcript_repo`. Nav + ⌘8 live in app.js; this module owns the surface body and is loaded
// after app.js (same convention as preservice.js/settings.js).
//
// BOUNDED RENDERING (86akcffvt AC3): a transcript can run to thousands of segments (a multi-hour
// service), far past the live console's 240-segment ring cap. The full segment array is fetched
// once (fine — it's data, not DOM), but only a bounded, contiguous WINDOW of it is ever turned
// into real `.tr-line` DOM rows at any one time; two spacer elements keep the scrollbar
// proportional to the transcript's FULL length so every segment is still reachable by scrolling,
// never truncated to a tail or a sample. See `renderWindow`/`recomputeWindow` below.
(function () {
  "use strict";
  var root = document.getElementById("surface-transcripts");
  if (!root) return;

  // Tauri IPC (absent when opened outside the shell — every call then rejects, read by the error
  // states below; same guarded shape as preservice.js/settings.js).
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

  var listView = document.getElementById("tr-list-view");
  var detailView = document.getElementById("tr-detail-view");
  var listEl = document.getElementById("tr-list");
  var emptyEl = document.getElementById("tr-empty");
  var errorEl = document.getElementById("tr-error");
  var retryBtn = document.getElementById("tr-retry");
  var backBtn = document.getElementById("tr-detail-back");
  var detailTitle = document.getElementById("tr-detail-title");
  var detailMeta = document.getElementById("tr-detail-meta");
  var notesBadge = document.getElementById("tr-detail-notes");
  var detailErrorEl = document.getElementById("tr-detail-error");
  var detailRetryBtn = document.getElementById("tr-detail-retry");
  var logEl = document.getElementById("tr-detail-log");
  var topSpacer = document.getElementById("tr-log-top-spacer");
  var rowsHost = document.getElementById("tr-log-rows");
  var bottomSpacer = document.getElementById("tr-log-bottom-spacer");
  var liveEl = document.getElementById("tr-detail-live");

  var loading = false;
  var transcripts = [];
  var openId = null;

  // ---------- formatting (no locale APIs — deterministic across engines, per this console's own
  // WKWebView-vs-Blink history: a fixed table beats trusting ICU to render the same everywhere) ----------
  var MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function two(n) { return String(n).padStart(2, "0"); }
  function fmtDate(ms) {
    if (typeof ms !== "number" || !isFinite(ms)) return "—";
    var d = new Date(ms);
    var h = d.getHours();
    var suffix = h >= 12 ? "PM" : "AM";
    var h12 = h % 12; if (h12 === 0) h12 = 12;
    return MONTH[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear() + " · " + h12 + ":" + two(d.getMinutes()) + " " + suffix;
  }
  // h:mm:ss at/above an hour, m:ss below — same convention as the Service Plan's duration display
  // (fmtClock/planFmtTotal in app.js), so a transcript's length reads consistently with the rest
  // of the console.
  function fmtDuration(startMs, endMs) {
    if (typeof startMs !== "number" || typeof endMs !== "number") return "In progress";
    var secs = Math.max(0, Math.round((endMs - startMs) / 1000));
    var h = Math.floor(secs / 3600);
    var m = Math.floor((secs % 3600) / 60);
    var s = secs % 60;
    return h > 0 ? (h + ":" + two(m) + ":" + two(s)) : (m + ":" + two(s));
  }
  function fmtTimestamp(ms) {
    var secs = Math.max(0, Math.round((ms || 0) / 1000));
    var h = Math.floor(secs / 3600);
    var m = Math.floor((secs % 3600) / 60);
    var s = secs % 60;
    return (h > 0 ? h + ":" : "") + two(m) + ":" + two(s);
  }
  function fmtSegCount(n) { return n + (n === 1 ? " segment" : " segments"); }

  // ---------- LIST ----------
  function showList() {
    detailView.hidden = true;
    listView.hidden = false;
    openId = null;
  }
  function trCard(t) {
    var card = el("div", "tr-card");
    card.setAttribute("role", "listitem");
    card.dataset.id = String(t.id);
    var btn = el("button", "tr-card-open");
    btn.type = "button";
    var dur = fmtDuration(t.started_at_ms, t.ended_at_ms);
    var label = t.label || "Untitled transcript";
    btn.setAttribute(
      "aria-label",
      "Open " + label + ", " + fmtDate(t.started_at_ms) + ", " + dur + ", " + fmtSegCount(t.segment_count)
    );
    var col = el("div", "tr-card-col");
    col.appendChild(el("span", "tr-card-name", label));
    col.appendChild(el("span", "tr-card-meta", fmtDate(t.started_at_ms) + " · " + dur + " · " + fmtSegCount(t.segment_count)));
    btn.appendChild(col);
    btn.addEventListener("click", function () { openTranscript(t.id); });
    card.appendChild(btn);
    return card;
  }
  function renderList() {
    listEl.innerHTML = "";
    emptyEl.hidden = transcripts.length !== 0;
    if (transcripts.length === 0) return;
    transcripts.forEach(function (t) { listEl.appendChild(trCard(t)); });
  }
  function loadList() {
    if (loading) return Promise.resolve();
    loading = true;
    listEl.setAttribute("aria-busy", "true");
    errorEl.hidden = true;
    return invoke("transcript_list")
      .then(function (rows) {
        transcripts = Array.isArray(rows) ? rows : [];
        renderList();
        loading = false;
        listEl.setAttribute("aria-busy", "false");
      })
      .catch(function (e) {
        console.error("[SelahCue] transcript_list failed", e);
        transcripts = [];
        listEl.innerHTML = "";
        emptyEl.hidden = true;
        errorEl.hidden = false;
        loading = false;
        listEl.setAttribute("aria-busy", "false");
      });
  }
  if (retryBtn) retryBtn.addEventListener("click", loadList);

  // ---------- DETAIL: bounded sliding-window renderer ----------
  // Character-count height ESTIMATE, not a measured one — deliberately: a measured/remeasured
  // virtualizer needs ResizeObserver + timing that is hard to make deterministic across engines,
  // and this console has a documented history of engine-specific layout surprises (WKWebView flex
  // <select> collapse, grid implicit auto-row overflow). An estimate only has to keep the
  // scrollbar roughly proportional and pick the right window — it never has to be pixel-exact.
  var CHARS_PER_LINE = 88;
  var LINE_HEIGHT_PX = 20;
  var ROW_VPAD = 14;
  // Hard cap on real `.tr-line` rows mounted in the DOM at once, regardless of transcript length —
  // the entity this ticket's bounded-memory test asserts directly (never a byte/proxy measure).
  // Comfortably above a typical viewport's visible rows (a few dozen) so scrolling never outruns
  // the window, and far below what even a short multi-hour service accumulates.
  var WINDOW_ROWS = 150;

  var segs = [];       // the full, unbounded segment array for the open transcript (data, not DOM)
  var offsets = [0];   // offsets[i] = estimated px height of everything BEFORE segment i
  var totalHeight = 0;
  var winStart = 0, winEnd = 0;
  var rafPending = false;

  function estRowHeight(text) {
    var len = (text || "").length || 1;
    var lines = Math.max(1, Math.ceil(len / CHARS_PER_LINE));
    return lines * LINE_HEIGHT_PX + ROW_VPAD;
  }
  function buildOffsets() {
    offsets = new Array(segs.length + 1);
    offsets[0] = 0;
    for (var i = 0; i < segs.length; i++) offsets[i + 1] = offsets[i] + estRowHeight(segs[i].text);
    totalHeight = offsets[segs.length];
  }
  // The index of the segment whose estimated [offset, offset+height) range contains `y` — a
  // standard upper-bound binary search over the strictly increasing `offsets` prefix sums.
  function indexAtOffset(y) {
    var lo = 0, hi = segs.length - 1;
    if (hi < 0) return 0;
    while (lo < hi) {
      var mid = (lo + hi) >> 1;
      if (offsets[mid + 1] <= y) lo = mid + 1; else hi = mid;
    }
    return lo;
  }
  function segRow(s) {
    var row = el("div", "tr-line");
    row.dataset.segId = String(s.id);
    row.appendChild(el("span", "tr-line-t", fmtTimestamp(s.start_ms)));
    row.appendChild(el("span", "tr-line-txt", s.text));
    return row;
  }
  // Mount [start, end) as REAL rows; everything outside that range is represented only by the two
  // spacer heights. The DOM therefore never holds more than WINDOW_ROWS real segment rows no
  // matter how long the transcript is.
  function renderWindow(start, end) {
    start = Math.max(0, Math.min(start, segs.length));
    end = Math.max(start, Math.min(end, segs.length));
    winStart = start; winEnd = end;
    rowsHost.innerHTML = "";
    for (var i = start; i < end; i++) rowsHost.appendChild(segRow(segs[i]));
    topSpacer.style.height = offsets[start] + "px";
    bottomSpacer.style.height = Math.max(0, totalHeight - offsets[end]) + "px";
  }
  function recomputeWindow() {
    rafPending = false;
    if (!segs.length) return;
    var idx = indexAtOffset(logEl.scrollTop);
    var half = Math.floor(WINDOW_ROWS / 2);
    var start = Math.max(0, idx - half);
    var end = Math.min(segs.length, start + WINDOW_ROWS);
    start = Math.max(0, end - WINDOW_ROWS); // re-clamp start if end got clamped near the tail
    if (start !== winStart || end !== winEnd) renderWindow(start, end);
  }
  function onScroll() {
    if (rafPending) return;
    rafPending = true;
    window.requestAnimationFrame(recomputeWindow);
  }
  logEl.addEventListener("scroll", onScroll);

  // Test hooks (CLAUDE.md bounded-memory discipline): a per-key Option-returning accessor, never a
  // global counter — a caller must name the segment it expects, so one assertion's hit can never
  // mask another's miss.
  window.__trRowFor = function (segId) {
    return rowsHost.querySelector('.tr-line[data-seg-id="' + segId + '"]') || null;
  };
  window.__trRenderedRowCount = function () { return rowsHost.children.length; };
  window.__trScrollToFraction = function (f) {
    var max = Math.max(0, logEl.scrollHeight - logEl.clientHeight);
    logEl.scrollTop = Math.max(0, Math.min(1, f)) * max;
    recomputeWindow();
  };

  // ---------- DETAIL: header + load ----------
  function showDetail() {
    listView.hidden = true;
    detailView.hidden = false;
  }
  function renderDetailHeader(t) {
    detailTitle.textContent = t.label || "Untitled transcript";
    detailMeta.textContent = fmtDate(t.started_at_ms) + " · " + fmtDuration(t.started_at_ms, t.ended_at_ms) + " · " + fmtSegCount(t.segments.length);
    notesBadge.textContent = t.notes_generated ? "Notes generated" : "Notes not yet generated";
    notesBadge.className = "tr-notes-badge" + (t.notes_generated ? " tr-notes-on" : "");
  }
  function openTranscript(id) {
    openId = id;
    showDetail();
    detailErrorEl.hidden = true;
    detailTitle.textContent = "Loading…";
    detailMeta.textContent = "";
    notesBadge.textContent = "";
    segs = []; offsets = [0]; totalHeight = 0; winStart = 0; winEnd = 0;
    rowsHost.innerHTML = ""; topSpacer.style.height = "0px"; bottomSpacer.style.height = "0px";
    invoke("transcript_get", { id: id })
      .then(function (t) {
        if (openId !== id) return; // a later selection superseded this one
        segs = Array.isArray(t.segments) ? t.segments : [];
        buildOffsets();
        renderDetailHeader(t);
        renderWindow(0, Math.min(segs.length, WINDOW_ROWS));
        logEl.scrollTop = 0;
        logEl.focus();
        liveEl.textContent = "Opened " + (t.label || "transcript") + ", " + fmtSegCount(segs.length) + ".";
      })
      .catch(function (e) {
        console.error("[SelahCue] transcript_get failed", e);
        if (openId !== id) return;
        detailTitle.textContent = "Transcript";
        detailErrorEl.hidden = false;
      });
  }
  if (detailRetryBtn) detailRetryBtn.addEventListener("click", function () {
    if (openId != null) openTranscript(openId);
  });
  if (backBtn) backBtn.addEventListener("click", function () {
    showList();
    // Focus a stable element after the view-swap (WCAG 2.4.3) — the card that opened this
    // transcript may no longer be first in a refreshed list, so fall back to the retry button
    // (always present) rather than leaving focus on a now-hidden element.
    var focusTarget = listEl.querySelector(".tr-card-open") || retryBtn;
    if (focusTarget) focusTarget.focus();
  });

  // Exposed for app.js's showSurface() activation hook — reloads the list every time the surface
  // is opened (a fresh read from the shared store, never a stale cache from a prior visit).
  window.trActivate = function () {
    showList();
    loadList();
  };
})();
