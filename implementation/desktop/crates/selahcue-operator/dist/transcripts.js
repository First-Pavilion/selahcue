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
  // Character-count height ESTIMATE as the STARTING POINT only — not the whole story. A fixed
  // 88-chars/line guess cannot know the real column width the log renders at (performance review,
  // Vera V-1): measured at the operator's own default window (1520x984) real rows ran 0.36-0.79x
  // the estimate, which left the median scroll frame showing only 44% of the viewport as text, up
  // to 131/240 frames fully BLANK with long utterances, and the last segment unreachable after
  // scrolling to the end (0/8 attempts — the window re-centred back up on the very next scroll
  // event). The estimate alone is kept only as the pre-measurement seed and as the per-row
  // DENOMINATOR the calibration ratio below is computed against; every position calculation is
  // scaled by that ratio once real rows have been measured.
  var CHARS_PER_LINE = 88;
  var LINE_HEIGHT_PX = 20;
  var ROW_VPAD = 14;
  // Hard cap on real `.tr-line` rows mounted in the DOM at once, regardless of transcript length —
  // the entity this ticket's bounded-memory test asserts directly (never a byte/proxy measure).
  // Comfortably above a typical viewport's visible rows (a few dozen) so scrolling never outruns
  // the window, and far below what even a short multi-hour service accumulates.
  var WINDOW_ROWS = 150;
  // Hysteresis margin (Vera V-1/V-2 verified fix direction (c)): only recompute the mounted
  // window once the real scroll position has drifted this many ROWS from a mounted edge, instead
  // of on every single row of movement. Collapses re-render count from "nearly every scroll
  // frame" (measured: 175/240 wheel frames, 146/150 arrow-key frames) to only the frames that
  // would otherwise run past what's mounted (11/240 in Vera's verified prototype).
  var EDGE_MARGIN_ROWS = 40;
  // Sub-pixel rounding slack at the true bottom of the scrollable area.
  var END_PIN_EPSILON_PX = 2;

  var segs = [];       // the full, unbounded segment array for the open transcript (data, not DOM)
  var offsets = [0];   // offsets[i] = ESTIMATED px height of everything BEFORE segment i (unscaled)
  var winStart = 0, winEnd = 0;
  var rafPending = false;
  var renderCount = 0; // how many times the mounted window actually moved (test hook, V-2)

  // Measured-height writeback + calibration (Vera V-1 fix direction (a)+(b)): once a row is
  // mounted, its real `offsetHeight` is folded into a running measured-vs-estimated ratio, and
  // every position calculation (spacer heights, the offset->index search) scales the character
  // estimate by that ratio. A single running scalar — rather than rewriting the whole `offsets`
  // prefix-sum array per measurement — keeps lookups O(1)/O(log n) while correcting the
  // systematic bias (Vera's own verified prototype: this leaves ~5-6% residual "breathing" since
  // the real ratio varies 0.36-0.79 row to row within one transcript, which is the accepted,
  // measured trade-off of a cheap global correction vs. an exact per-row remeasurement scheme).
  var measuredIds = Object.create(null); // segId -> true once folded into the ratio (never re-added)
  var sumMeasuredPx = 0, sumEstimatedPx = 0;
  var avgRatio = 1;

  function estRowHeight(text) {
    var len = (text || "").length || 1;
    var lines = Math.max(1, Math.ceil(len / CHARS_PER_LINE));
    return lines * LINE_HEIGHT_PX + ROW_VPAD;
  }
  function buildOffsets() {
    offsets = new Array(segs.length + 1);
    offsets[0] = 0;
    for (var i = 0; i < segs.length; i++) offsets[i + 1] = offsets[i] + estRowHeight(segs[i].text);
  }
  function scaledOffset(i) { return offsets[i] * avgRatio; }
  // The index of the segment whose CALIBRATED [offset, offset+height) range contains `y` — a
  // standard upper-bound binary search over the strictly increasing `offsets` prefix sums, scaled
  // uniformly by `avgRatio` at lookup time.
  function indexAtOffset(y) {
    var lo = 0, hi = segs.length - 1;
    if (hi < 0) return 0;
    while (lo < hi) {
      var mid = (lo + hi) >> 1;
      if (scaledOffset(mid + 1) <= y) lo = mid + 1; else hi = mid;
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
  // Scroll-anchor compensation (performance review, Vera V-6, verified fix "P2"): a calibration
  // update moves EVERYTHING below `start` (topSpacer = offsets[start] * avgRatio), and dropping a
  // row off the mounted window's edge loses its real measured height in favour of the estimate —
  // but `scrollTop` itself never moves, and `.tr-log { overflow-anchor: none }` (needed so the
  // browser's OWN scroll anchoring stops fighting the diff-and-patch rewrite above) removes the
  // browser's own compensation for this too. Left uncorrected this produced fully blank
  // viewports and multi-hundred-pixel visual jumps on a transcript whose segment lengths change
  // regime partway through (measured: up to 2,563px on a 30,000-segment fixture). Find the
  // topmost row, among those that will still be mounted after this render (the overlap of the
  // old and new window), whose box currently touches or is below the top of the visible log —
  // i.e. the row the user is actually looking at right now that survives the diff — and return
  // its live on-screen top. Called BEFORE any DOM write in `renderWindow`.
  function findTopVisibleSurvivor(overlapStart, overlapEnd) {
    var hostTop = logEl.getBoundingClientRect().top;
    var idx = winStart;
    var node = rowsHost.firstChild;
    while (node) {
      if (idx >= overlapStart && idx < overlapEnd) {
        var r = node.getBoundingClientRect();
        if (r.bottom > hostTop) return { node: node, top: r.top };
      }
      idx++;
      node = node.nextSibling;
    }
    return null;
  }
  // Read the just-mounted nodes' REAL rendered heights (one forced layout after all the DOM
  // writes in this render, never interleaved with them) and roll them into the running
  // measured/estimated ratio. `newRows` is [{node, est}] — the estimate captured at creation
  // time, since by the time this runs the node may have scrolled out of `winStart..winEnd` again
  // (a fast scroll can mount and unmount a row within one render).
  function foldMeasurements(newRows) {
    var changed = false;
    for (var k = 0; k < newRows.length; k++) {
      var segId = newRows[k].node.dataset.segId;
      if (measuredIds[segId]) continue;
      var real = newRows[k].node.offsetHeight;
      if (!real) continue; // not laid out yet (hidden/detached) — try again next render
      measuredIds[segId] = true;
      sumMeasuredPx += real;
      sumEstimatedPx += newRows[k].est;
      changed = true;
    }
    if (changed && sumEstimatedPx > 0) avgRatio = sumMeasuredPx / sumEstimatedPx;
  }
  // Mount [start, end) as REAL rows; everything outside that range is represented only by the two
  // spacer heights. The DOM therefore never holds more than WINDOW_ROWS real segment rows no
  // matter how long the transcript is.
  //
  // DIFF-AND-PATCH, not clear+rebuild (code/QA review, Cody/Quinn High): `#tr-detail-log` is
  // role="log", whose implicit `aria-live` is "polite" — `innerHTML = ""` + a full rebuild on
  // every scroll-driven recompute would make assistive tech re-announce the ENTIRE mounted window
  // on every step, the exact anti-pattern `app.js`'s `syncTranscript` already documents fixing
  // for the live console. `[start, end)` is a CONTIGUOUS range, so the diff is simple: rows in
  // the overlap of the old and new windows are left untouched (same DOM node, no
  // unmount/remount, no re-announcement); only rows that actually left or entered the window are
  // removed/added. This also collapses the per-render DOM-node churn from up to WINDOW_ROWS
  // (~450 elements incl. children) to just the delta, which is V-2's fix.
  function renderWindow(start, end, pinned) {
    start = Math.max(0, Math.min(start, segs.length));
    end = Math.max(start, Math.min(end, segs.length));
    renderCount++;

    var newRows = []; // [{node, est}] mounted THIS call — measured together, once, below
    var overlapStart = Math.max(start, winStart);
    var overlapEnd = Math.min(end, winEnd);
    var hasOverlap = overlapStart < overlapEnd && rowsHost.children.length > 0;

    // Capture the scroll-anchor BEFORE any DOM write below (V-6 fix) — with no overlap (a
    // scrollbar drag/big jump has nothing in common with what's mounted to anchor to) there is
    // no survivor to track, and the compensation below falls back to the ratio-only term. `pinned`
    // (the tail-pin caller, below) is exempt entirely: that path already deliberately holds
    // `scrollTop` at the real end regardless of estimate error, `bottomSpacer` is always 0 there
    // (nothing follows the true last segment), and the browser auto-clamps `scrollTop` to the new
    // `scrollHeight` on its own — compensating on top of that would pull the view back OFF the
    // true end the pin exists to guarantee (confirmed by running the committed end-reachability
    // checks: applying either term here regressed "TR realistic: ... actually VISIBLE at
    // scroll-to-end" before this guard was added).
    var anchor = !pinned && hasOverlap ? findTopVisibleSurvivor(overlapStart, overlapEnd) : null;
    var ratioBefore = avgRatio;

    if (!hasOverlap) {
      // No overlap with what's currently mounted (first render, or a big jump) — nothing to
      // diff against.
      rowsHost.innerHTML = "";
      for (var i = start; i < end; i++) {
        var node = segRow(segs[i]);
        rowsHost.appendChild(node);
        newRows.push({ node: node, est: estRowHeight(segs[i].text) });
      }
    } else {
      for (var r = winStart; r < overlapStart; r++) {
        var stale = rowsHost.firstChild;
        if (stale) rowsHost.removeChild(stale);
      }
      for (var r2 = winEnd; r2 > overlapEnd; r2--) {
        var staleEnd = rowsHost.lastChild;
        if (staleEnd) rowsHost.removeChild(staleEnd);
      }
      for (var p = overlapStart - 1; p >= start; p--) {
        var pNode = segRow(segs[p]);
        rowsHost.insertBefore(pNode, rowsHost.firstChild);
        newRows.push({ node: pNode, est: estRowHeight(segs[p].text) });
      }
      for (var a = overlapEnd; a < end; a++) {
        var aNode = segRow(segs[a]);
        rowsHost.appendChild(aNode);
        newRows.push({ node: aNode, est: estRowHeight(segs[a].text) });
      }
    }

    winStart = start; winEnd = end;
    foldMeasurements(newRows);
    topSpacer.style.height = scaledOffset(start) + "px";
    bottomSpacer.style.height = Math.max(0, scaledOffset(segs.length) - scaledOffset(end)) + "px";

    // Compensate (V-6 fix): move scrollTop by exactly the on-screen displacement the spacer/DOM
    // changes above just caused, so whatever the user was looking at does not jump. The anchor
    // term (same DOM node, real re-measured position) captures BOTH halves of the shift — the
    // ratio change AND the local estimate-vs-real error from rows dropping off the mounted
    // edge — because it reads the actual rendered position rather than recomputing from offsets.
    // With no anchor (no overlap to survive the diff), fall back to compensating for the ratio
    // change alone against this render's own top offset.
    if (anchor) {
      logEl.scrollTop += anchor.node.getBoundingClientRect().top - anchor.top;
    } else if (!pinned && avgRatio !== ratioBefore) {
      logEl.scrollTop += offsets[start] * (avgRatio - ratioBefore);
    }
  }
  function recomputeWindow() {
    rafPending = false;
    if (!segs.length) return;
    var scrollTop = logEl.scrollTop;
    var maxScroll = Math.max(0, logEl.scrollHeight - logEl.clientHeight);
    // Pin the tail (Vera V-1): at the TRUE bottom of the real scrollable area, always mount all
    // the way to the real last segment, regardless of what the (still imperfect) height estimate
    // maps `scrollTop` to. This is what makes the last segment reachable independent of
    // calibration accuracy — mapping the true end through an estimate is exactly what left it
    // unreachable before (0/8 attempts; the window re-centred back up on the next scroll event).
    if (scrollTop >= maxScroll - END_PIN_EPSILON_PX) {
      if (winEnd !== segs.length) {
        var pinnedEnd = segs.length;
        renderWindow(Math.max(0, pinnedEnd - WINDOW_ROWS), pinnedEnd, true);
      }
      return;
    }
    var idx = indexAtOffset(scrollTop);
    var half = Math.floor(WINDOW_ROWS / 2);
    var start = Math.max(0, idx - half);
    var end = Math.min(segs.length, start + WINDOW_ROWS);
    start = Math.max(0, end - WINDOW_ROWS); // re-clamp start if end got clamped near the tail
    // Hysteresis: recompute only once `idx` has drifted within EDGE_MARGIN_ROWS of (or past) a
    // mounted edge — this is also what catches a big jump (e.g. a scrollbar drag), since being
    // fully outside the mounted window trivially satisfies one side of this check too.
    var nearMountedEdge = idx <= winStart + EDGE_MARGIN_ROWS || idx >= winEnd - EDGE_MARGIN_ROWS;
    if (nearMountedEdge && (start !== winStart || end !== winEnd)) renderWindow(start, end);
  }
  function onScroll() {
    if (rafPending) return;
    rafPending = true;
    window.requestAnimationFrame(recomputeWindow);
  }
  logEl.addEventListener("scroll", onScroll);
  // Home/End: jump straight there ourselves, rather than let the browser's own default action
  // drive it (V-6 fix follow-up, found while verifying the fix against the real WebKit gate
  // below, not part of the original finding). WebKit runs a genuine multi-frame animation for a
  // native Home/End keyboard scroll (confirmed by tracing scrollTop across ~13 intermediate
  // frames over ~300ms — `docs/delivery` evidence for this ticket has the full trace), and ANY
  // script write to `scrollTop` — including this render's own anchor/ratio compensation above,
  // required for the wheel/drag fix — cancels that animation outright, the same way any other
  // programmatic scroll would. Left alone, the very first hysteresis-crossing render fired mid
  // -animation stops it a few hundred rows short of the true end, regressing the already-shipped,
  // four-reviewer-verified "End reaches the last segment" guarantee (NFR-019) purely as a side
  // effect of fixing V-6. A real mouse wheel or scrollbar drag never hits this: both re-assert
  // their own position on the very next native input event regardless of what we write, so they
  // do not depend on an uninterrupted engine-driven animation the way Home/End's default action
  // does. Handling the two jump keys ourselves — the same instant jump `__trScrollToFraction`
  // already performs for the committed Blink gate — sidesteps the race entirely instead of
  // trying to out-guess when a native animation might be in flight.
  logEl.addEventListener("keydown", function (ev) {
    if (ev.key !== "Home" && ev.key !== "End") return;
    ev.preventDefault();
    logEl.scrollTop = ev.key === "End" ? Math.max(0, logEl.scrollHeight - logEl.clientHeight) : 0;
    recomputeWindow();
  });

  // Test hooks (CLAUDE.md bounded-memory discipline): a per-key Option-returning accessor, never a
  // global counter — a caller must name the segment it expects, so one assertion's hit can never
  // mask another's miss. `__trRenderCount`/`__trAvgRatio`/`__trWindowBounds` are informational
  // process state (like `__trRenderedRowCount` already was), not per-key hit counters — added for
  // the realistic-width/content-size control (performance review, Vera V-1/V-2) so a headless
  // test can assert the calibration actually ran and the hysteresis actually reduced re-renders,
  // not just that the end state looks right.
  window.__trRowFor = function (segId) {
    return rowsHost.querySelector('.tr-line[data-seg-id="' + segId + '"]') || null;
  };
  window.__trRenderedRowCount = function () { return rowsHost.children.length; };
  window.__trRenderCount = function () { return renderCount; };
  window.__trAvgRatio = function () { return avgRatio; };
  window.__trWindowBounds = function () { return { start: winStart, end: winEnd }; };
  // A row is genuinely VISIBLE (not just mounted somewhere in the 150-row window) iff its real
  // bounding rect actually overlaps the log container's — the direct measure of Vera's "blank
  // frame" finding (a frame where rows are mounted but none intersect the viewport).
  window.__trVisibleSegIds = function () {
    var host = logEl.getBoundingClientRect();
    var ids = [];
    for (var i = 0; i < rowsHost.children.length; i++) {
      var r = rowsHost.children[i].getBoundingClientRect();
      if (r.bottom > host.top && r.top < host.bottom) ids.push(rowsHost.children[i].dataset.segId);
    }
    return ids;
  };
  window.__trScrollToFraction = function (f) {
    var max = Math.max(0, logEl.scrollHeight - logEl.clientHeight);
    logEl.scrollTop = Math.max(0, Math.min(1, f)) * max;
    recomputeWindow();
  };
  // A REAL small pixel delta (matching an actual wheel tick, e.g. Vera's measured "60px wheel
  // steps"), unlike `__trScrollToFraction` above which can jump across the WHOLE transcript in
  // one call — the hysteresis fix (V-2) only has anything to demonstrate against genuinely small,
  // incremental scroll steps; a handful of huge fraction jumps legitimately needs a render each
  // time regardless of hysteresis.
  window.__trScrollBy = function (deltaPx) {
    var max = Math.max(0, logEl.scrollHeight - logEl.clientHeight);
    logEl.scrollTop = Math.max(0, Math.min(max, logEl.scrollTop + deltaPx));
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
    segs = []; offsets = [0]; winStart = 0; winEnd = 0;
    // Fresh calibration per transcript (Vera V-1 fix): a ratio learned from one transcript's
    // real row heights has no bearing on another's (different text, but more importantly a
    // stale measuredIds set would make foldMeasurements silently skip every row of a new
    // transcript, freezing avgRatio at whatever the PREVIOUS transcript last measured).
    measuredIds = Object.create(null);
    sumMeasuredPx = 0; sumEstimatedPx = 0; avgRatio = 1;
    renderCount = 0;
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
