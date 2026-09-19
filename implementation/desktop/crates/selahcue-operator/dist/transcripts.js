// Transcripts surface (86akcffvt / FR-130 core slice): every saved transcript (label · date ·
// duration · segment count), most recent first; selecting one opens a read-only, fully scrollable
// view of its complete stored text, plus whether sermon notes have already been generated from it
// (real status, not a placeholder — see `notes_generated` below). From this same detail view the
// operator can also Generate sermon notes from the transcript's COMPLETE stored text (86akcffy0;
// see the "Generate Sermon Notes" section near the end of this file) — the shipped counterpart to
// the tail-limited Generate the Settings panel's live console offers. Editing/corrections and the
// detected-scripture list remain deferred — see 86akgqdxr.
//
// DATA: `transcript_list` / `transcript_get`, read-only Tauri commands wired to 86ajtxzrn's
// `transcript_repo`; `transcript_generate_notes` / `note_generation_limits` (86akcffy0) for
// generation. Nav + ⌘8 live in app.js; this module owns the surface body and is loaded after
// app.js (same convention as preservice.js/settings.js).
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

  // ---------- DETAIL: bounded sliding-window renderer (ADR-0026 rev 2) ----------
  // D1: exact, monotone per-row heights via a Fenwick/BIT prefix-sum tree, replacing the old
  // global `avgRatio` scalar. D2: this component never writes `scrollTop`; native
  // `overflow-anchor` does all compensation (see `app.css`'s `.tr-log`/`.tr-log-spacer` rules).
  // D3: the five-key keyboard interception apparatus is deleted outright — Home/End/PageUp/
  // PageDown/Space/arrows all run their native default action. D5: the "never writes scrollTop"
  // invariant is statically enforced (`scripts/operator_headless.py`'s `check_d5_no_scrolltop_writes`),
  // not inferred from behaviour — every write site below is marked `D5-exempt`.
  var CHARS_PER_LINE = 88; // pre-measurement seed; calibrateCharsPerLine() below corrects it once
  var lastCalibratedWidth = 0; // set by calibrateCharsPerLine(); drives the ResizeObserver below
  var LINE_HEIGHT_PX = 20;
  var ROW_VPAD = 14;
  var WINDOW_ROWS = 150;
  var EDGE_MARGIN_ROWS = 40;
  var END_PIN_EPSILON_PX = 2;

  var segs = [];        // the full, unbounded segment array for the open transcript (data, not DOM)
  var winStart = 0, winEnd = 0;
  var rafPending = false;
  var renderCount = 0;  // how many times the mounted window actually moved (test hook, V-2)

  // ---------- D1: exact, monotone height metric ----------
  // Fenwick/BIT (Binary Indexed Tree) over `heights`, replacing the single global `avgRatio`
  // scalar. `heights[i]` starts at the char-count ESTIMATE and is overwritten EXACTLY ONCE, with
  // the row's real `offsetHeight`, the first time it is laid out.
  //   I1 — Monotone: a row's recorded height changes at most once and never again for the life
  //        of an open transcript.
  //   I2 — Local: changing row i's height changes the position (prefix sum) of rows > i only;
  //        rows <= i never move.
  // This is what keeps the corrections native scroll anchoring has to make small and local
  // (tens of px, one row's line-count error) instead of global and depth-proportional (Vera
  // measured single `avgRatio` corrections of 2,563px and 3,479px).
  var heights = new Int32Array(0);
  var fenwick = new Int32Array(1); // 1-indexed BIT over `heights`; fenwick[0] unused
  var fenN = 0;
  var measuredIds = Object.create(null); // segId -> true once folded into `heights` (never re-added)

  function fenAdd(i, delta) {
    if (!delta) return;
    for (var idx = i + 1; idx <= fenN; idx += idx & -idx) fenwick[idx] += delta;
  }
  // Exact cumulative px height of everything BEFORE row i (i may equal fenN, the grand total).
  function fenPrefix(i) {
    var sum = 0;
    for (var idx = i; idx > 0; idx -= idx & -idx) sum += fenwick[idx];
    return sum;
  }
  // The index of the row whose EXACT [offset, offset+height) range contains `y` — Fenwick-tree
  // order-statistics binary lift, O(log n), replacing the old scaled binary search over the
  // `offsets` prefix-sum array.
  function fenFindByPrefix(y) {
    if (fenN === 0) return 0;
    var pos = 0, remaining = Math.max(0, y);
    var bit = 1;
    while (bit * 2 <= fenN) bit *= 2;
    for (; bit > 0; bit = bit >> 1) {
      var next = pos + bit;
      if (next <= fenN && fenwick[next] <= remaining) {
        pos = next;
        remaining -= fenwick[next];
      }
    }
    return Math.min(pos, fenN - 1);
  }
  function estRowHeight(text) {
    var len = (text || "").length || 1;
    var lines = Math.max(1, Math.ceil(len / CHARS_PER_LINE));
    return lines * LINE_HEIGHT_PX + ROW_VPAD;
  }
  // D4's "free improvement" (ADR-0026): calibrate CHARS_PER_LINE ONCE per transcript, from the
  // REAL rendered column width, before the first row is placed — safe under I1/I2, since it runs
  // before any row exists and only sets the STARTING baseline every future estimate is computed
  // from; it changes nothing retroactively. Without this, the hardcoded 88-chars/line guess can
  // be off by 2x or more at a real operator window width (this file's own measured history: real
  // rows ran 0.36-0.79x the estimate at 1520px) — which matters specifically for a FRESH jump
  // into never-before-measured territory (a scrollbar drag, or `__trScrollToFraction`): with no
  // overlap to anchor to (ADR-0026's own named residual risk), the landing position is only as
  // good as this baseline, so a 2x-wrong estimate can land the mounted window far enough from the
  // real target position to produce a fully blank frame. Falls back to the hardcoded default if
  // the log has no usable layout yet (defensive; `openTranscript` always shows the detail view,
  // giving it real layout, before this runs).
  function calibrateCharsPerLine() {
    if (!logEl.clientWidth) return;
    var SAMPLE = "The quick brown fox jumps over the lazy dog, said the preacher, 0123456789.";
    var probe = el("span", "tr-line-txt", SAMPLE);
    probe.style.position = "absolute";
    probe.style.visibility = "hidden";
    probe.style.whiteSpace = "pre";
    probe.style.left = "-9999px";
    var tsProbe = el("span", "tr-line-t", "00:00:00"); // widest realistic timestamp, h:mm:ss
    tsProbe.style.position = "absolute";
    tsProbe.style.visibility = "hidden";
    tsProbe.style.whiteSpace = "pre";
    tsProbe.style.left = "-9999px";
    document.body.appendChild(probe);
    document.body.appendChild(tsProbe);
    var textWidthPx = probe.getBoundingClientRect().width;
    var tsWidthPx = tsProbe.getBoundingClientRect().width;
    document.body.removeChild(probe);
    document.body.removeChild(tsProbe);
    if (!textWidthPx) return;
    var avgCharPx = textWidthPx / SAMPLE.length;
    // Mirror `.tr-line`'s real layout (`display:flex; gap:10px`, `.tr-log`'s `padding: 6px 28px
    // 28px`) rather than using the log's raw clientWidth — the text column is narrower than the
    // log by the timestamp column and the inter-column gap.
    var LOG_HPAD_PX = 56, ROW_GAP_PX = 10;
    var availPx = Math.max(100, logEl.clientWidth - LOG_HPAD_PX - tsWidthPx - ROW_GAP_PX);
    CHARS_PER_LINE = Math.max(10, Math.floor(availPx / avgCharPx));
    lastCalibratedWidth = logEl.clientWidth;
  }
  // (Re)builds the Fenwick tree from scratch — called once per transcript open, when the full
  // estimate baseline is known and nothing has been measured yet.
  function buildHeights() {
    calibrateCharsPerLine();
    fenN = segs.length;
    heights = new Int32Array(fenN);
    fenwick = new Int32Array(fenN + 1);
    for (var i = 0; i < fenN; i++) {
      heights[i] = estRowHeight(segs[i].text);
      fenAdd(i, heights[i]);
    }
    measuredIds = Object.create(null);
  }
  // D4's ResizeObserver role (ADR-0026: "a width ResizeObserver to invalidate the height cache on
  // a column resize, which also closes Vera's V-9"). This is the one asynchronous-observer role
  // the ADR adopts — everywhere else D1/D2 stay purely synchronous — because there is no
  // synchronous signal for "the flex layout finished recalculating the log's column width" the
  // way there is for "a row just got measured". A measured height (D1's `heights[i]`, folded via
  // I1) is only "real" for the column width it was measured under; a resize invalidates EVERY
  // row's height back to a fresh, re-calibrated estimate rather than trying to selectively
  // preserve some of them, matching the ADR's own word "invalidate". The currently-mounted window
  // is then force-remounted so its rows are freshly measured under the new width immediately,
  // instead of waiting for the next scroll to notice.
  function invalidateHeightsForWidth() {
    if (!segs.length || logEl.clientWidth === lastCalibratedWidth) return;
    var savedStart = winStart, savedEnd = winEnd;
    buildHeights();
    winStart = 0; winEnd = 0;
    // 86akmdkdg: disconnect BEFORE clearing, matching renderWindow's no-overlap branch and
    // openTranscript below — otherwise a row mid-async-measurement (observed via startMeasuring's
    // deferred/inScrollFrame path) leaves measureObserver holding a reference to a node this line
    // is about to detach. The very next line's renderWindow(savedStart, savedEnd) call happens to
    // disconnect again on its own (winStart/winEnd are already zeroed above, so it always takes the
    // no-overlap branch) — but that is AFTER this clear, not before it, so the detach-before-
    // disconnect ordering bug (and the leak window it opens) is real regardless.
    moDisconnect();
    rowsHost.innerHTML = "";
    renderWindow(savedStart, savedEnd);
  }
  var resizeObserver = typeof ResizeObserver !== "undefined"
    ? new ResizeObserver(function () { invalidateHeightsForWidth(); })
    : null;
  if (resizeObserver) resizeObserver.observe(logEl);

  function offsetAt(i) { return fenPrefix(i); }
  function totalHeight() { return fenPrefix(fenN); }
  function indexAtOffset(y) { return fenFindByPrefix(y); }
  // Fold ONE row's REAL rendered height into the Fenwick tree, EXACTLY ONCE (I1), and refresh the
  // spacers so the correction is visible. `idx` is read off the node itself (`row._idx`, stashed
  // by `segRow` at creation) rather than passed in, so this can run from either call site below.
  function foldOneMeasurement(node, real) {
    var segId = node.dataset.segId;
    if (measuredIds[segId]) return;
    if (!real) return; // not laid out yet (hidden/detached) — the observer fires again once it is
    measuredIds[segId] = true;
    var idx = node._idx;
    var delta = real - heights[idx];
    if (delta !== 0) {
      heights[idx] = real;
      fenAdd(idx, delta);
      topSpacer.style.height = offsetAt(winStart) + "px";
      bottomSpacer.style.height = Math.max(0, totalHeight() - offsetAt(winEnd)) + "px";
    }
  }
  // 86akmd00b: measurement used to read `node.offsetHeight` SYNCHRONOUSLY inside `renderWindow`,
  // itself called from `recomputeWindow` inside `onScroll`'s `requestAnimationFrame` callback —
  // i.e. on every frame of a native keyboard-scroll animation. `.offsetHeight` forces a
  // synchronous layout; ADR-0026's own spike already established that a `scrollTop` WRITE mid-
  // animation cancels WebKit's in-flight native scroll (D2's whole reason for existing). A forced
  // synchronous layout READ, landing mid-animation on WebKit's compositor the same way, is the
  // leading candidate for the V-10 PageDown/PageUp/Space/End shortfalls found investigating
  // 86akhf8e6 (confirmed NOT explained by anchoring: instrumented real animated PageDown presses
  // against this file under Chromium and the scroll delta was identical whether a spacer moved
  // that press or not) — ADR-0026 D2 eliminated the WRITE side of this hazard but never addressed
  // a forced-layout READ recurring on every scroll frame. A `ResizeObserver` reports AFTER the
  // browser's own layout pass, asynchronously, off the scroll/rAF path entirely — the same
  // non-forcing pattern D4 already uses for column-width invalidation just below — so measurement
  // no longer performs its own synchronous layout during a scroll event. Unverified against real
  // WebKit (unavailable in the environment that made this change); see the ticket.
  var measureObserver = typeof ResizeObserver !== "undefined"
    ? new ResizeObserver(function (entries) {
        for (var i = 0; i < entries.length; i++) {
          var node = entries[i].target;
          var box = entries[i].borderBoxSize && entries[i].borderBoxSize[0];
          var real = box ? box.blockSize : node.offsetHeight;
          foldOneMeasurement(node, real);
          if (measuredIds[node.dataset.segId]) moUnobserve(node);
        }
      })
    : null;
  // 86akmdkdg: `measureObserver` has no query API of its own, so this counter is the only way to
  // see "how many now-detached nodes are still referenced by the observer" from outside — the
  // exact shape of the leak this ticket fixes (a resize firing mid-async-measurement used to clear
  // rowsHost without disconnecting first). Every observe/unobserve/disconnect call on
  // `measureObserver` MUST go through these three wrappers so the count never drifts from reality.
  // Membership is tracked with a WeakSet, not a Set (security review, Sana): a `Set` of DOM nodes
  // holds STRONG references, which would make this instrumentation the only thing in the file
  // capable of keeping a detached row alive forever if some future row-removal path ever forgot to
  // route through these wrappers — reintroducing, inside the leak-detector itself, the exact bug
  // class this ticket exists to fix. A `WeakSet` never keeps a node alive on its own. Its trade-off
  // is no `.size`/iteration/`.clear()`, so a plain counter still carries the actual count — kept
  // accurate (QA review, Quinn) by only touching it when the WeakSet confirms real membership, not
  // unconditionally on every observe/unobserve/disconnect call: `startMeasuring` only ever routes a
  // node through `moObserve` while `inScrollFrame` (every other mount — initial open, a test-hook
  // jump, invalidateHeightsForWidth's own rebuild — measures synchronously and never registers with
  // `measureObserver` at all), yet `moUnobserve` is still called on those never-observed nodes too
  // (renderWindow's stale-row eviction doesn't know which rows were ever observed); an unconditional
  // decrement there would silently under-report a real leak elsewhere in the same session.
  var measureObservedSet = new WeakSet();
  var measureObservedCount = 0;
  function moObserve(node) {
    if (!measureObserver) return;
    measureObserver.observe(node);
    if (!measureObservedSet.has(node)) { measureObservedSet.add(node); measureObservedCount++; }
  }
  function moUnobserve(node) {
    if (!measureObserver) return;
    measureObserver.unobserve(node);
    if (measureObservedSet.has(node)) { measureObservedSet.delete(node); measureObservedCount--; }
  }
  function moDisconnect() {
    if (!measureObserver) return;
    measureObserver.disconnect();
    measureObservedSet = new WeakSet(); // WeakSet has no .clear() — replace it instead
    measureObservedCount = 0;
  }
  function segRow(s, idx) {
    var row = el("div", "tr-line");
    row.dataset.segId = String(s.id);
    row._idx = idx;
    row.appendChild(el("span", "tr-line-t", fmtTimestamp(s.start_ms)));
    row.appendChild(el("span", "tr-line-txt", s.text));
    return row;
  }
  // Mount [start, end) as REAL rows; everything outside that range is represented only by the two
  // spacer heights. The DOM therefore never holds more than WINDOW_ROWS real segment rows no
  // matter how long the transcript is.
  //
  // DIFF-AND-PATCH, not clear+rebuild (code/QA review, Cody/Quinn High): `#tr-detail-log` is
  // role="log", whose implicit `aria-live` is "polite" — a full rebuild on every scroll-driven
  // recompute would make assistive tech re-announce the ENTIRE mounted window on every step.
  // `[start, end)` is a CONTIGUOUS range, so the diff is simple: rows in the overlap of the old
  // and new windows are left untouched (same DOM node, no unmount/remount, no re-announcement);
  // only rows that actually left or entered the window are removed/added.
  //
  // D2 (ADR-0026 rev 2): this function NEVER writes `scrollTop`. The only things it moves are the
  // two spacers' `height` — a plain DOM mutation, not a scroll write — and native scroll
  // anchoring (enabled on `.tr-log`, excluded on the spacers via `overflow-anchor: none` there)
  // is what keeps the row the reader is looking at stationary across that mutation. Spike
  // evidence: a script `scrollTop` write cancels an in-flight WebKit keyboard-scroll animation
  // (any value, including a no-op); a DOM mutation that shifts content does not, on either engine,
  // and native anchoring holds through the animation too.
  // Start measuring a newly-mounted row. Deferred (via the observer, async, off the scroll/rAF
  // path) ONLY while `inScrollFrame` — i.e. only for a recompute reached through `onScroll`'s own
  // `requestAnimationFrame` callback, the one path a real in-flight native scroll animation can
  // actually be racing. Every other caller (initial mount, the `__trScrollBy`/
  // `__trScrollToFraction` test hooks, `invalidateHeightsForWidth`'s force-remount) calls
  // `renderWindow` directly — no animation is in flight to protect, and several of those callers
  // (e.g. the I2/anchoring-is-live checks in `operator_headless.py`, which call `__trScrollBy` in
  // a tight loop with no yield between calls) rely on measurement completing SYNCHRONOUSLY, the
  // same as before this change. Deferring unconditionally regressed those checks (confirmed:
  // `operator_headless.py` FAILED `TR I2 (setup)`/`TR anchoring-is-live` intermittently once
  // deferred everywhere) without buying anything, since there is nothing to protect them from.
  function startMeasuring(node) {
    if (measureObserver && inScrollFrame) moObserve(node);
    else foldOneMeasurement(node, node.offsetHeight);
  }
  function renderWindow(start, end) {
    start = Math.max(0, Math.min(start, segs.length));
    end = Math.max(start, Math.min(end, segs.length));
    renderCount++;

    var newRows = []; // nodes mounted THIS call — measurement started on each, once, below
    var overlapStart = Math.max(start, winStart);
    var overlapEnd = Math.min(end, winEnd);
    var hasOverlap = overlapStart < overlapEnd && rowsHost.children.length > 0;

    if (!hasOverlap) {
      // Every currently-mounted row is being discarded — stop observing all of them in one call
      // rather than walking the (about to be destroyed) child list individually.
      moDisconnect();
      rowsHost.innerHTML = "";
      for (var i = start; i < end; i++) {
        var node = segRow(segs[i], i);
        rowsHost.appendChild(node);
        newRows.push(node);
      }
    } else {
      for (var r = winStart; r < overlapStart; r++) {
        var stale = rowsHost.firstChild;
        if (stale) { moUnobserve(stale); rowsHost.removeChild(stale); }
      }
      for (var r2 = winEnd; r2 > overlapEnd; r2--) {
        var staleEnd = rowsHost.lastChild;
        if (staleEnd) { moUnobserve(staleEnd); rowsHost.removeChild(staleEnd); }
      }
      for (var p = overlapStart - 1; p >= start; p--) {
        var pNode = segRow(segs[p], p);
        rowsHost.insertBefore(pNode, rowsHost.firstChild);
        newRows.push(pNode);
      }
      for (var a = overlapEnd; a < end; a++) {
        var aNode = segRow(segs[a], a);
        rowsHost.appendChild(aNode);
        newRows.push(aNode);
      }
    }

    winStart = start; winEnd = end;
    for (var m = 0; m < newRows.length; m++) startMeasuring(newRows[m]);
    topSpacer.style.height = offsetAt(start) + "px";
    bottomSpacer.style.height = Math.max(0, totalHeight() - offsetAt(end)) + "px";
    // No scrollTop write here — none. See D2 above.
  }
  function recomputeWindow() {
    rafPending = false;
    if (!segs.length) return;
    var scrollTop = logEl.scrollTop;
    var maxScroll = Math.max(0, logEl.scrollHeight - logEl.clientHeight);
    // Pin the tail: at the TRUE bottom of the real scrollable area, always mount all the way to
    // the real last segment, regardless of any transient estimate-vs-real gap in rows not yet
    // measured. Unlike the pre-M1 file, this performs NO `scrollTop` re-assertion (D2) — with an
    // exact metric for every already-measured row and native anchoring covering the rest, the
    // browser's own clamp keeps `scrollTop` correct on its own.
    if (scrollTop >= maxScroll - END_PIN_EPSILON_PX) {
      if (winEnd !== segs.length) {
        var pinnedEnd = segs.length;
        renderWindow(Math.max(0, pinnedEnd - WINDOW_ROWS), pinnedEnd);
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
  // D2/D3: no echo-suppression bookkeeping. This file never writes `scrollTop` reactively, so a
  // `scroll` event is always genuine (user input or native anchoring/animation) and simply
  // schedules a recompute, rAF-coalesced same as before.
  // True only while a recompute reached through THIS function's own rAF callback is running — see
  // `startMeasuring`'s comment above for why that is the one path measurement defers on (86akmd00b).
  var inScrollFrame = false;
  function onScroll() {
    if (rafPending) return;
    rafPending = true;
    window.requestAnimationFrame(function () {
      inScrollFrame = true;
      try {
        recomputeWindow();
      } finally {
        inScrollFrame = false;
      }
    });
  }
  logEl.addEventListener("scroll", onScroll);
  // D3 (the part D2 requires to be honestly testable): NO keydown interception. Home, End,
  // PageUp, PageDown, Space, Shift+Space, and the arrow keys all run their native default action.
  // Under D2 nothing ever writes `scrollTop` from script, so nothing can cancel WebKit's native
  // keyboard-scroll animation (the spike's C1) — the five-key interception this file's pre-M1
  // version needed (`jumpScrollTop`/`armJumpGuard`/`wheelEventSeq`/`jumpGuardGen`/`pageStepPx`)
  // no longer has anything to protect against and is deleted outright, not merely unused.

  // Test hooks (CLAUDE.md bounded-memory discipline): a per-key Option-returning accessor, never a
  // global counter. `__trAvgRatio` is deleted — there is no more ratio (D1).
  window.__trRowFor = function (segId) {
    return rowsHost.querySelector('.tr-line[data-seg-id="' + segId + '"]') || null;
  };
  window.__trRenderedRowCount = function () { return rowsHost.children.length; };
  window.__trRenderCount = function () { return renderCount; };
  window.__trWindowBounds = function () { return { start: winStart, end: winEnd }; };
  // The exact cumulative Fenwick-tree offset of row i — direct access to the D1 metric itself,
  // not a rendered pixel reading (which conflates the data structure with layout/anchoring).
  // This is what the I2 monotonicity control below reads: "measuring row i never moves the
  // offset of any row <= i" is a property of THIS function's return value, not of anything on
  // screen.
  window.__trOffsetAt = function (i) { return offsetAt(i); };
  // How many distinct rows have been folded into the exact metric so far (D1) — the direct
  // successor to the deleted `__trAvgRatio`: "did real measurement actually happen" without
  // exposing a ratio that no longer exists.
  window.__trMeasuredCount = function () { return Object.keys(measuredIds).length; };
  // 86akmdkdg: `measureObserver` exposes no query API, so this is the only way from outside to see
  // "how many nodes is the observer still holding a reference to" — the direct measure of the
  // leak this ticket fixes (a resize firing mid-async-measurement used to detach a row without
  // ever disconnecting the observer watching it).
  window.__trMeasureObservedCount = function () { return measureObservedCount; };
  // Force-fires the resize-triggered force-remount path independent of an actual layout-width
  // change reaching the real ResizeObserver on `logEl` — makes "invalidate mid an in-flight async
  // measurement" a deterministic test setup instead of racing real browser resize-notification
  // timing.
  window.__trInvalidateHeightsForWidth = function () {
    lastCalibratedWidth = -1; // force the width-unchanged early-return below to fall through
    invalidateHeightsForWidth();
  };
  // A row is genuinely VISIBLE (not just mounted somewhere in the 150-row window) iff its real
  // bounding rect actually overlaps the log container's — the direct measure of "blank frame".
  window.__trVisibleSegIds = function () {
    var host = logEl.getBoundingClientRect();
    var ids = [];
    for (var i = 0; i < rowsHost.children.length; i++) {
      var r = rowsHost.children[i].getBoundingClientRect();
      if (r.bottom > host.top && r.top < host.bottom) ids.push(rowsHost.children[i].dataset.segId);
    }
    return ids;
  };
  // D5 exemption (b): these two hooks exist to SIMULATE user input (a scrollbar drag / a wheel
  // tick), not to compensate anything — the ADR names them explicitly as the one class of
  // permitted scrollTop write besides openTranscript's initial `= 0`.
  window.__trScrollToFraction = function (f) {
    var max = Math.max(0, logEl.scrollHeight - logEl.clientHeight);
    logEl.scrollTop = Math.max(0, Math.min(1, f)) * max; // D5-exempt: simulates a scrollbar drag (test hook)
    recomputeWindow();
  };
  window.__trScrollBy = function (deltaPx) {
    var max = Math.max(0, logEl.scrollHeight - logEl.clientHeight);
    logEl.scrollTop = Math.max(0, Math.min(max, logEl.scrollTop + deltaPx)); // D5-exempt: simulates a wheel tick (test hook)
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
    // Generate is only for a FINISHED service (86akcffy0, Sana security review — High): a
    // still-recording transcript is not the immutable record this flow's preview/consent/
    // persist steps all assume — its writer can append segments the preview never showed, and
    // the "complete transcript... every recorded segment" disclosure copy would be lying about
    // one still growing. `transcript_list` has no ended-only filter, so an in-progress service
    // can be the very FIRST, most-clickable card — this is not a rare edge case to shrug off.
    generateAllowed = t.ended_at_ms != null;
    generateHasExistingDraft = !!t.notes_generated;
    if (generateBtn) generateBtn.disabled = !generateAllowed;
    if (!generateAllowed) {
      var r = genResultEl();
      if (r) {
        r.className = "pp-gen-result pp-gen-info";
        r.setAttribute("role", "status");
        r.appendChild(el("span", "pp-gen-info-ico", "◔"));
        r.appendChild(el("span", null,
          "This service is still being recorded. Generate becomes available once it ends."));
      }
    }
  }
  function openTranscript(id) {
    openId = id;
    showDetail();
    detailErrorEl.hidden = true;
    detailTitle.textContent = "Loading…";
    detailMeta.textContent = "";
    notesBadge.textContent = "";
    // A different transcript's Generate state has no bearing on this one (86akcffy0) — a stale
    // result/preview from whatever was open before must not linger into the newly opened one.
    resetGenerateUi();
    segs = []; heights = new Int32Array(0); fenN = 0; fenwick = new Int32Array(1);
    winStart = 0; winEnd = 0;
    // Fresh metric per transcript (D1): a Fenwick tree built from one transcript's real row
    // heights has no bearing on another's (different text, but more importantly a stale
    // `measuredIds` set would make measurement silently skip every row of a new transcript,
    // freezing its heights at whatever the PREVIOUS transcript last measured).
    measuredIds = Object.create(null);
    renderCount = 0;
    moDisconnect(); // stop watching the previous transcript's rows
    rowsHost.innerHTML = ""; topSpacer.style.height = "0px"; bottomSpacer.style.height = "0px";
    invoke("transcript_get", { id: id })
      .then(function (t) {
        if (openId !== id) return; // a later selection superseded this one
        segs = Array.isArray(t.segments) ? t.segments : [];
        buildHeights();
        renderDetailHeader(t);
        renderWindow(0, Math.min(segs.length, WINDOW_ROWS));
        logEl.scrollTop = 0; // D5-exempt: initial position, before any scroll/animation can exist
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

  // ---------- Generate Sermon Notes from this stored transcript (86akcffy0; FR-122/130) --------
  // Reuses the SAME preview-and-confirm consent pattern (FR-132/135) as the Settings panel's
  // live-tail Generate (settings.js's onGenerate/openGenPreview/confirmGenerate) — same
  // `.pp-generate`/`.pp-gen-preview`/`.pp-gen-result` CSS classes, same Cancel/Confirm shape,
  // same consent-gated backend (`run_note_generation`, untouched) — but built from `segs`, the
  // transcript's COMPLETE stored segments `openTranscript` already fetched in full (never a
  // bounded tail), and sent by id (`transcript_generate_notes`) rather than as a client-supplied
  // string: the command re-reads the store itself, so "what the preview showed" and "what was
  // sent" can never drift from a stale client-side copy the way a LIVE, still-advancing
  // transcript could (PP F-5 L-1's concern doesn't apply here — a stored transcript is static).
  var generateBtn = document.getElementById("tr-generate");
  var genPreviewBox = document.getElementById("tr-gen-preview");
  var genResultBox = document.getElementById("tr-gen-result");
  var generating = false;
  // Set by renderDetailHeader from the transcript's OWN `ended_at_ms`/`notes_generated` fields
  // every time a transcript is opened (86akcffy0, Sana security review) — `onGenerate` re-checks
  // `generateAllowed` itself (defense in depth) rather than trusting only the disabled button.
  var generateAllowed = false;
  var generateHasExistingDraft = false;

  // Same floor as settings.js's MIN_TRANSCRIPT_CHARS (Vera, PERF-3): an empty/near-empty
  // transcript is refused before any network call, never billed as a fully fabricated draft. A
  // stored, completed transcript should essentially never be this short, but the guard costs
  // nothing and keeps both Generate entry points behaving identically at the edges.
  var MIN_TRANSCRIPT_CHARS = 20;

  // Unicode-scalar-aware length/prefix helpers (Sana security review F5 + Vera performance
  // review PERF-1, 86akcffy0). Plain JS `str.length`/`str.slice` count/cut UTF-16 CODE UNITS, not
  // characters — an astral character (rare in spoken-transcript text, but possible) is 2 UTF-16
  // units and would inflate a `.length`-based count above what the backend's `chars().count()`
  // (Unicode SCALAR values) reports, and `.slice` could split a surrogate pair in half. Neither
  // function below materializes the whole string into an array first: `unicodeLength` is a single
  // counting pass, `firstUnicodeChars` stops as soon as it has `n` characters, so previewing a
  // multi-megabyte transcript never costs more work than the `limit` it is bounded to.
  function unicodeLength(s) {
    var n = 0;
    for (var i = 0; i < s.length; ) {
      var code = s.codePointAt(i);
      i += (code > 0xFFFF) ? 2 : 1;
      n++;
    }
    return n;
  }
  function firstUnicodeChars(s, n) {
    var end = 0, count = 0;
    while (count < n && end < s.length) {
      var code = s.codePointAt(end);
      end += (code > 0xFFFF) ? 2 : 1;
      count++;
    }
    return s.slice(0, end);
  }

  // Mirrors `selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS` — fetched from the host
  // (`note_generation_limits`, 86akcffy0) so the number has exactly ONE owner. This constant is
  // only the fallback for the (practically unreachable — transcript_list/transcript_get would
  // already have failed too) case where that one call fails on an otherwise-working host.
  var NOTE_TRANSCRIPT_CHAR_LIMIT_FALLBACK = 400000;
  var noteCharLimit = null;
  function loadNoteCharLimit() {
    if (typeof noteCharLimit === "number") return Promise.resolve(noteCharLimit);
    return invoke("note_generation_limits")
      .then(function (v) {
        noteCharLimit = (v && typeof v.max_transcript_chars === "number")
          ? v.max_transcript_chars : NOTE_TRANSCRIPT_CHAR_LIMIT_FALLBACK;
        return noteCharLimit;
      })
      .catch(function () { return NOTE_TRANSCRIPT_CHAR_LIMIT_FALLBACK; });
  }

  // Joins EVERY currently-loaded segment's text with "\n" — matching `app.js`'s `syncTranscript`
  // bridge (`segs.map(s => s.text).join("\n")`) byte for byte, the same wire shape the backend's
  // `transcript_full_text` builds from the stored rows. `segs` here is never tailed (86akcffvt
  // AC2/AC3: the full array is fetched once; only its DOM rendering is windowed).
  function fullTranscriptText() {
    return segs.map(function (s) { return (s && typeof s.text === "string") ? s.text : ""; }).join("\n");
  }

  function genResultEl() {
    var r = genResultBox;
    if (r) { r.hidden = false; r.textContent = ""; r.removeAttribute("role"); }
    return r;
  }

  function showGenError(code, message) {
    var r = genResultEl();
    if (!r) return;
    if (code === "not_configured") {
      r.className = "pp-gen-result pp-gen-info";
      r.setAttribute("role", "status");
      r.appendChild(el("span", "pp-gen-info-ico", "☁"));
      r.appendChild(el("span", null, "Sermon-note generation isn’t available in this build yet."));
      return;
    }
    if (code === "consent_required") {
      r.className = "pp-gen-result pp-gen-err";
      r.setAttribute("role", "alert");
      r.appendChild(el("span", null,
        "Turn on cloud processing in Settings → Providers & Privacy to generate sermon notes."));
      return;
    }
    // quota_exceeded / transport / malformed / no_transcript / transcript_too_short → surface the
    // message. The latter two never reach here from a network response — onGenerate refuses
    // before any call is made — so their label says exactly that: nothing was sent.
    r.className = "pp-gen-result pp-gen-err";
    r.setAttribute("role", "alert");
    var label = code === "quota_exceeded" ? "Monthly limit reached"
      : code === "no_transcript" ? "No transcript to generate from"
      : code === "transcript_too_short" ? "Transcript too short"
      : "Couldn’t generate notes";
    r.appendChild(el("span", "pp-gen-err-t", label + " — "));
    r.appendChild(el("span", null, message || ""));
  }

  // Read-only rendering (86akcffy0 non-goal: no edit surface for a from-history draft — that
  // stays the Settings panel's persisted-draft flow, `update_sermon_note_draft`, unchanged).
  function renderDraftReadOnly(res) {
    var r = genResultEl();
    if (!r) return;
    r.className = "pp-gen-result pp-gen-ok";
    r.setAttribute("role", "status");
    var d = res.draft || {};
    var hd = el("div", "pp-gen-hdr");
    hd.appendChild(el("span", "pp-gen-badge", res.degraded ? "Local draft" : (res.provider || "AI sermon notes")));
    hd.appendChild(el("span", "pp-gen-title", d.title || "Sermon notes"));
    // FR-123: a model draft is labelled as one.
    if (res.ai_generated) hd.appendChild(el("span", "pp-gen-ai-label", res.ai_label || "AI-generated draft"));
    r.appendChild(hd);
    // FR-128: the fabrication warning travels WITH the draft, never omitted.
    if (res.ai_generated && res.disclosure) {
      var disc = el("p", "pp-gen-disclosure", res.disclosure);
      disc.setAttribute("role", "note");
      r.appendChild(disc);
    }
    // FR-135: a degraded draft says so in words, not just via a badge.
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
      // FR-122 points/sub-points render as a NESTED list inside their parent point.
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
  }

  function showGenResult(res) {
    if (!res || res.ok !== true) {
      var err = res || {};
      showGenError(err.error || "malformed", err.message || "Something went wrong.");
      return;
    }
    renderDraftReadOnly(res);
    // The backend just persisted this draft against `openId` (`sermon_note_repo` — 86akcffy0);
    // reflect that immediately rather than waiting for a future reopen of this same transcript.
    if (openId != null) {
      notesBadge.textContent = "Notes generated";
      notesBadge.className = "tr-notes-badge tr-notes-on";
    }
  }

  function closeGenPreview(refocusButton) {
    if (genPreviewBox) { genPreviewBox.hidden = true; genPreviewBox.textContent = ""; }
    if (generateBtn) {
      generateBtn.hidden = false;
      if (refocusButton) generateBtn.focus();
    }
  }

  // Resets ALL Generate-related UI/state — called whenever a different transcript is opened
  // (86akcffy0) so nothing from a previous selection leaks into the newly opened one. Leaves
  // `generateAllowed`/`generateHasExistingDraft` at a neutral "not yet known" false/false —
  // `renderDetailHeader` sets their real values once the newly opened transcript's data arrives.
  function resetGenerateUi() {
    generating = false;
    generateAllowed = false;
    generateHasExistingDraft = false;
    if (genPreviewBox) { genPreviewBox.hidden = true; genPreviewBox.textContent = ""; }
    if (genResultBox) { genResultBox.hidden = true; genResultBox.textContent = ""; genResultBox.className = "pp-gen-result"; }
    if (generateBtn) { generateBtn.hidden = false; generateBtn.disabled = false; generateBtn.removeAttribute("aria-busy"); }
  }

  // The actual send — reachable ONLY from openGenPreview's Confirm button. Sends `id`, never the
  // transcript text itself: `transcript_generate_notes` re-reads the store, which is both the
  // authoritative source and avoids shipping a (potentially 400k-character) string over IPC
  // twice for no benefit.
  function confirmGenerate(id) {
    closeGenPreview(false);
    generating = true;
    if (generateBtn) { generateBtn.setAttribute("aria-busy", "true"); generateBtn.disabled = true; }
    invoke("transcript_generate_notes", { id: id })
      .then(function (res) {
        // A LATER selection superseded this one while the call was in flight (86akcffy0, Sana
        // F3) — without this guard, transcript A's result/badge would render under transcript
        // B's now-open heading. `openTranscript`'s own `if (openId !== id) return` a few lines up
        // is the exact precedent this mirrors.
        if (openId !== id) return;
        showGenResult(res);
      })
      .catch(function (e) {
        if (openId !== id) return;
        showGenError("transport", String(e && e.message ? e.message : e));
      })
      .then(function () {
        generating = false;
        // Only restore THIS transcript's button state — if a different one is open now,
        // `openTranscript`/`renderDetailHeader` already set its own correct state, and this
        // stale completion must not clobber it (e.g. re-enabling a button `renderDetailHeader`
        // deliberately disabled because the NOW-open transcript is still recording).
        if (openId === id && generateBtn) {
          generateBtn.removeAttribute("aria-busy");
          generateBtn.disabled = !generateAllowed;
        }
      });
  }

  // Renders the text about to be sent, plus who it's going to, and waits for an explicit Confirm
  // click — nothing is sent until then. `limit` is the live `note_generation_limits` value (or
  // its fallback).
  //
  // When `transcript` exceeds it: an ADDITIONAL paragraph discloses the truncation plainly
  // (86akcffy0 AC2: a documented, VISIBLE strategy, never a silent cut) — truncate-to-head, the
  // same behaviour the backend's `clamp_transcript_in_place` already applies at send time — AND
  // the preview text box itself shows only the first `limit` characters, the same ones that will
  // actually be sent. Before this it showed the FULL, unclamped transcript while only a prefix
  // would be sent — its own "this exact text will be sent" claim was false in the clamped case,
  // and rendering a multi-megabyte string into one DOM node forced real layout cost with no
  // bound (Vera performance review PERF-1, measured ~0.10ms/KB — 320ms at 3MB — that this
  // surface's own bounded-window design, see this file's header comment, exists to prevent).
  // Clamping the RENDERED text to `limit` fixes both at once: the preview is now always exactly
  // what gets sent, and its cost is capped regardless of how large the stored transcript grows.
  function openGenPreview(transcript, limit) {
    var box = genPreviewBox;
    if (!box) return;
    box.textContent = "";

    var id = openId;
    var providerName = "the configured provider";

    var heading = el("h3", "pp-gen-preview-title", "Review before sending");
    heading.id = "tr-gen-preview-title";
    heading.tabIndex = -1;
    box.appendChild(heading);

    var totalChars = unicodeLength(transcript);
    var willClamp = typeof limit === "number" && totalChars > limit;
    var sentText = willClamp ? firstUnicodeChars(transcript, limit) : transcript;

    box.appendChild(el("p", "pp-gen-preview-desc",
      willClamp
        ? ("This transcript is " + totalChars.toLocaleString() + " characters. The first " +
           limit.toLocaleString() + " (shown below) will be sent to " + providerName +
           ". Nothing leaves this device until you press Confirm.")
        : ("This exact text (" + totalChars.toLocaleString() + " characters) will be sent to " +
           providerName + ". Nothing leaves this device until you press Confirm.")));

    // Honest for THIS flow (86akcffy0): the operator explicitly selected this transcript from
    // the Transcripts list, and this is its COMPLETE stored text — every recorded segment, not
    // the console's recent-window tail the Settings panel's own preview (rightly, for THAT flow)
    // discloses. Keep the class name (`.pp-gen-preview-scope`) shared with that other flow — same
    // role (the disclosure sentence), different, equally honest wording.
    box.appendChild(el("p", "pp-gen-preview-desc pp-gen-preview-scope",
      "This is the complete transcript stored for this service — every recorded segment, not a " +
      "recent window."));

    // FR-129-adjacent honesty (86akcffy0, Sana security review F2): `notes_generated` is now
    // real and visible on this same screen — Confirm here silently REPLACES whatever draft
    // already exists (possibly hand-edited via the Settings panel), so say so before it happens
    // rather than after.
    if (generateHasExistingDraft) {
      box.appendChild(el("p", "pp-gen-preview-desc pp-gen-preview-overwrite",
        "This will REPLACE the sermon notes already generated for this transcript."));
    }

    if (willClamp) {
      var dropped = totalChars - limit;
      box.appendChild(el("p", "pp-gen-preview-desc pp-gen-preview-clamp",
        "This transcript is longer than the " + limit.toLocaleString() + "-character limit for " +
        "one request. The first " + limit.toLocaleString() + " characters will be sent; the " +
        "final " + dropped.toLocaleString() + " characters will be left out, and the notes may " +
        "not reflect the end of the service."));
    }

    // Untrusted transcript text → el() sets it via textContent, never innerHTML. Bounded to
    // `limit` characters when clamped — see the function doc comment above (PERF-1).
    var text = el("div", "pp-gen-preview-text", sentText);
    text.tabIndex = 0;
    box.appendChild(text);

    var actions = el("div", "pp-gen-preview-actions");
    var cancel = el("button", "pp-gen-preview-cancel", "Cancel");
    cancel.type = "button";
    cancel.id = "tr-gen-preview-cancel";
    cancel.addEventListener("click", function () { closeGenPreview(true); });
    actions.appendChild(cancel);

    var confirm = el("button", "pp-gen-preview-confirm", "Confirm — send to " + providerName);
    confirm.type = "button";
    confirm.id = "tr-gen-preview-confirm";
    confirm.addEventListener("click", function () { confirmGenerate(id); });
    actions.appendChild(confirm);
    box.appendChild(actions);

    box.setAttribute("role", "group");
    box.setAttribute("aria-labelledby", "tr-gen-preview-title");
    box.hidden = false;
    if (generateBtn) generateBtn.hidden = true;
    heading.focus();
  }

  function onGenerate() {
    if (generating) return;
    if (genPreviewBox && !genPreviewBox.hidden) return; // already reviewing
    if (openId == null) return;
    // Defense in depth (86akcffy0, Sana security review F1): `generateBtn.disabled` already
    // stops a normal click while the transcript is still recording, but this function is the
    // one place that actually decides whether to open the review step, so it re-checks rather
    // than trusting only the button's own attribute.
    if (!generateAllowed) return;
    var transcript = fullTranscriptText();
    var trimmed = transcript.trim();
    if (trimmed.length === 0) {
      showGenError("no_transcript", "This transcript has no text, so nothing was sent.");
      return;
    }
    if (trimmed.length < MIN_TRANSCRIPT_CHARS) {
      showGenError("transcript_too_short",
        "This transcript is too short to generate sermon notes from, so nothing was sent.");
      return;
    }
    // Capture the transcript id THIS call refers to, in case a fast double-click races
    // `loadNoteCharLimit`'s async round trip and the operator switches transcripts before it
    // resolves (Vera performance review PERF-2) — never open a preview for a transcript that
    // is no longer the one open.
    var forId = openId;
    loadNoteCharLimit().then(function (limit) {
      if (openId !== forId || generating || (genPreviewBox && !genPreviewBox.hidden)) return;
      openGenPreview(transcript, limit);
    });
  }
  if (generateBtn) generateBtn.addEventListener("click", onGenerate);

  // Exposed for app.js's showSurface() activation hook — reloads the list every time the surface
  // is opened (a fresh read from the shared store, never a stale cache from a prior visit).
  window.trActivate = function () {
    showList();
    loadList();
  };
})();
