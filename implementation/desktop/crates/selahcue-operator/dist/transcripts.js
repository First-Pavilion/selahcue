// Transcripts surface (86akcffvt core slice + 86akgqdxr; FR-130): every saved transcript (label ·
// date · duration · segment count), most recent first; selecting one opens ONE workspace with its
// complete stored text (scrollable, bounded-window rendered), any existing correction overlaid
// read-only on its raw segment (`.tr-line-corrected`, 86akgqdxr — writing a NEW correction is a
// linked follow-up, not this file's scope), every scripture reference detected during that
// service (`#tr-detections`, 86akgqdxr — see that section below), and the saved sermon-note
// draft's ACTUAL content if one exists, view + edit (`#tr-gen-result`, 86akgqdxr) — not merely
// whether one was generated. Generating a NEW draft from this stored transcript (86akcffy0; see
// the "Generate Sermon Notes" section near the end of this file) is the shipped counterpart to the
// tail-limited Generate the Settings panel's live console offers.
//
// DATA: `transcript_list` / `transcript_get`, read-only Tauri commands wired to 86ajtxzrn's
// `transcript_repo`; `transcript_generate_notes` / `note_generation_limits` (86akcffy0) for
// generation; `update_sermon_note_draft` (86akgqdv0) for editing a saved draft — already generic
// over `transcriptId`, reused here unchanged, no backend change needed. Nav + ⌘8 live in app.js;
// this module owns the surface body and is loaded after app.js (same convention as
// preservice.js/settings.js).
//
// BOUNDED RENDERING (86akcffvt AC3 + 86akgqdxr AC5): a transcript can run to thousands of segments
// (a multi-hour service) and detect far more scripture references than the live console's own
// in-session queue (`MAX_DETECTIONS = 32`) ever holds at once. The full segment/detection arrays
// are fetched once each (fine — it's data, not DOM), but only a bounded, contiguous WINDOW of
// either is ever turned into real DOM rows at any one time; spacer elements keep each list's
// scrollbar proportional to its FULL length so every row is still reachable by scrolling, never
// truncated to a tail or a sample. See `renderWindow`/`recomputeWindow` (transcript log) and
// `renderDetWindow`/`recomputeDetWindow` (detections — deliberately simpler: fixed row height, no
// Fenwick tree, since a detection row never wraps to a variable height).
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

  // Detected scripture (86akgqdxr) — see the "Detected scripture" section below.
  var detEmptyEl = document.getElementById("tr-detections-empty");
  var detLogEl = document.getElementById("tr-det-log");
  var detTopSpacer = document.getElementById("tr-det-top-spacer");
  var detRowsHost = document.getElementById("tr-det-rows");
  var detBottomSpacer = document.getElementById("tr-det-bottom-spacer");

  // Saved sermon-note draft (86akgqdxr) — see the "Sermon notes" section below.
  var notesEmptyEl = document.getElementById("tr-notes-empty");

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
  // not inferred from behaviour — every write site below is marked `D5-exempt(init)` or
  // `D5-exempt(test-hook)` (ADR-0026 rev 3 — the file holds a second virtualizer as of 86akgqdxr,
  // the detections panel below, with its own matching pair of marked sites).
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
    // 86akgqdxr: the "editable correction layer" 86ajtxzrn's schema reserved, made REACHABLE
    // from this screen — read-only in this ticket (see the linked follow-up for actual editing).
    // `s.correctedText` is merged onto the segment in `openTranscript`, from `t.corrections`; the
    // RAW segment text (`s.text`) is never mutated or hidden — both render, so a correction is
    // visibly an overlay on the immutable stream, never a silent rewrite of it.
    if (s.correctedText != null) {
      row.classList.add("tr-line-corrected");
      row.appendChild(el("span", "tr-line-txt tr-line-txt-raw", s.text));
      var corrected = el("span", "tr-line-txt tr-line-corrected-txt", s.correctedText);
      corrected.setAttribute("aria-label", "Corrected: " + s.correctedText);
      row.appendChild(corrected);
    } else {
      row.appendChild(el("span", "tr-line-txt", s.text));
    }
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
    logEl.scrollTop = Math.max(0, Math.min(1, f)) * max; // D5-exempt(test-hook): simulates a scrollbar drag
    recomputeWindow();
  };
  window.__trScrollBy = function (deltaPx) {
    var max = Math.max(0, logEl.scrollHeight - logEl.clientHeight);
    logEl.scrollTop = Math.max(0, Math.min(max, logEl.scrollTop + deltaPx)); // D5-exempt(test-hook): simulates a wheel tick
    recomputeWindow();
  };

  // ---------- Detected scripture (86akgqdxr; FR-130) — bounded, fixed-row-height window ---------
  // A transcript with a long/oratorical service can persist far more detections than the LIVE
  // console's `MAX_DETECTIONS = 32` queue ever holds at once — the point of this window is the
  // same bounded-DOM discipline as the transcript log above, deliberately SIMPLER: a detection
  // row is always exactly one line (reference · position · confidence), never variable-height
  // wrapped body text, so a fixed-row-height sliding window needs no Fenwick tree/measurement —
  // `Math.floor(scrollTop / DET_ROW_HEIGHT)` is exact, not an estimate. `DET_ROW_HEIGHT` must
  // match `.tr-det-row`'s CSS height (`app.css`) exactly, or the spacer math and the real
  // scrollbar drift apart.
  var DET_ROW_HEIGHT = 32;
  var DET_WINDOW_ROWS = 40;
  var dets = [];
  var detWinStart = 0;
  var detWinEnd = 0;

  // "Approximate transcript position" (the ticket's own wording): resolves a detection's
  // `source_segment` id against the FULL `segs` array `openTranscript` already fetched (never a
  // second query) into that segment's start timestamp, formatted the same way the log's own
  // timestamps would be. `source_segment === 0` is `transcript_repo::load`'s documented "no known
  // segment" sentinel (see `DetectedReferenceView`'s Rust-side doc comment) — shown honestly as
  // "Position unknown" rather than guessed at.
  function detPositionLabel(d) {
    if (!d || !d.source_segment) return "Position unknown";
    for (var i = 0; i < segs.length; i++) {
      if (segs[i] && segs[i].id === d.source_segment) return fmtTimestamp(segs[i].start_ms);
    }
    return "Position unknown";
  }

  function detRow(d) {
    var row = el("div", "tr-det-row");
    row.setAttribute("role", "listitem");
    row.setAttribute("data-det-id", d.id);
    row.appendChild(el("span", "tr-det-ref", d.reference || ""));
    row.appendChild(el("span", "tr-det-pos", detPositionLabel(d)));
    var conf = el("span", "tr-det-conf", (typeof d.confidence === "number" ? d.confidence : 0) + "% match");
    conf.setAttribute("aria-label", (typeof d.confidence === "number" ? d.confidence : 0) + " percent match confidence");
    row.appendChild(conf);
    return row;
  }

  // Mounts ONLY rows [start, end) as real DOM nodes; two spacers keep the scrollbar proportional
  // to the FULL detection count so every one stays reachable by scrolling, never truncated to a
  // sample — the same "renders completely, not just visibly" guarantee the transcript log makes.
  function renderDetWindow(start, end) {
    start = Math.max(0, Math.min(start, dets.length));
    end = Math.max(start, Math.min(end, dets.length));
    detWinStart = start;
    detWinEnd = end;
    detRowsHost.innerHTML = "";
    for (var i = start; i < end; i++) detRowsHost.appendChild(detRow(dets[i]));
    detTopSpacer.style.height = (start * DET_ROW_HEIGHT) + "px";
    detBottomSpacer.style.height = ((dets.length - end) * DET_ROW_HEIGHT) + "px";
  }

  function recomputeDetWindow() {
    var scrollTop = detLogEl.scrollTop;
    var idx = Math.floor(scrollTop / DET_ROW_HEIGHT);
    var half = Math.floor(DET_WINDOW_ROWS / 2);
    var start = Math.max(0, idx - half);
    var end = Math.min(dets.length, start + DET_WINDOW_ROWS);
    start = Math.max(0, end - DET_WINDOW_ROWS);
    if (start !== detWinStart || end !== detWinEnd) renderDetWindow(start, end);
  }

  // Same D2/D3 discipline as the transcript log above: never write `scrollTop` reactively — a
  // `scroll` event here is always genuine input, rAF-coalesced.
  var detRafPending = false;
  function onDetScroll() {
    if (detRafPending) return;
    detRafPending = true;
    window.requestAnimationFrame(function () {
      detRafPending = false;
      recomputeDetWindow();
    });
  }
  detLogEl.addEventListener("scroll", onDetScroll);

  // Test hooks (CLAUDE.md bounded-memory discipline: per-key accessor, never only a global count).
  window.__trDetRowFor = function (detId) {
    return detRowsHost.querySelector('.tr-det-row[data-det-id="' + detId + '"]') || null;
  };
  window.__trDetRenderedRowCount = function () { return detRowsHost.children.length; };
  window.__trDetWindowBounds = function () { return { start: detWinStart, end: detWinEnd }; };
  window.__trDetScrollToFraction = function (f) {
    var max = Math.max(0, detLogEl.scrollHeight - detLogEl.clientHeight);
    detLogEl.scrollTop = Math.max(0, Math.min(1, f)) * max; // D5-exempt(test-hook): simulates a scrollbar drag
    recomputeDetWindow();
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

  // Populates the detected-scripture list from `transcript_get`'s OWN response (86akgqdxr) — the
  // `detection` rows 86ajtxzrn already persisted, forwarded now instead of dropped. A clear empty
  // state when there are none, never a blank area (AC3); bounded rendering when there are many.
  function renderDetections(t) {
    dets = Array.isArray(t.detections) ? t.detections : [];
    detWinStart = 0;
    detWinEnd = 0;
    if (dets.length === 0) {
      detEmptyEl.hidden = false;
      detLogEl.hidden = true;
      detRowsHost.innerHTML = "";
      detTopSpacer.style.height = "0px";
      detBottomSpacer.style.height = "0px";
      return;
    }
    detEmptyEl.hidden = true;
    detLogEl.hidden = false;
    renderDetWindow(0, Math.min(dets.length, DET_WINDOW_ROWS));
    detLogEl.scrollTop = 0; // D5-exempt(init): before any scroll/animation can exist on this container
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
        // 86akgqdxr: merge any existing correction onto its segment BEFORE heights are measured
        // (a corrected line can render taller/shorter than the raw one) — read-only display, see
        // segRow's own doc comment for why the raw text is never touched.
        var corrById = {};
        (Array.isArray(t.corrections) ? t.corrections : []).forEach(function (c) {
          corrById[c.segment_id] = c.corrected_text;
        });
        segs.forEach(function (s) {
          if (Object.prototype.hasOwnProperty.call(corrById, s.id)) s.correctedText = corrById[s.id];
        });
        buildHeights();
        renderDetailHeader(t);
        // 86akgqdxr: detections + the saved draft's real content, alongside the transcript — one
        // workspace, not three separate places to piece together.
        renderDetections(t);
        renderNotesFromDetail(t);
        renderWindow(0, Math.min(segs.length, WINDOW_ROWS));
        logEl.scrollTop = 0; // D5-exempt(init): before any scroll/animation can exist on this container
        logEl.focus();
        liveEl.textContent = "Opened " + (t.label || "transcript") + ", " + fmtSegCount(segs.length) +
          ", " + (Array.isArray(t.detections) ? t.detections.length : 0) + " detected reference(s).";
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
  // Test-only hook (Vera performance review PERF-2 re-check): a real app never needs this — the
  // cache is a correct, permanent-for-the-session optimization — but a headless check that wants
  // to exercise the UNCACHED, concurrent-in-flight-calls race needs a way back to that state
  // without restarting the whole page, the same shape as `window.__resetSermonNoteDraftForTest`
  // in settings.js.
  window.__resetNoteCharLimitForTest = function () { noteCharLimit = null; };

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

  // ---------- Saved sermon-note draft: view + edit (86akgqdxr) ------------------------------
  // Ported from settings.js's persisted-draft surface (86akgqdv0/86akc0tua/86akby820), ADAPTED
  // to whichever HISTORICAL transcript is open here rather than "the active session" — the
  // underlying save call (`update_sermon_note_draft`) was already generic over `transcriptId`,
  // confirmed by reading its full call chain (Backend -> LAN Command::UpdateSermonNoteDraft ->
  // LiveController::apply, which does not special-case "the active transcript"). This removes
  // 86akcffy0's own documented restriction ("no edit surface for a from-history draft — that
  // stays the Settings panel's persisted-draft flow") — this ticket IS that restriction's
  // successor. Element IDs are prefixed `tr-` (never `pp-`) because both panels' markup coexists
  // in the same document (one hidden via its `surface-*` ancestor) — a duplicate `id` would make
  // `document.getElementById` silently resolve to the WRONG panel's node. CSS classes
  // (`.pp-gen-edit-form`, `.pp-edit-section-heading`, ...) are reused verbatim: every read of
  // them here is scoped to a specific `form`/`r` subtree, never `document.querySelector`, so a
  // duplicate class is safe (this codebase's own convention — see 86akcffy0 reusing
  // `.pp-generate`/`.pp-gen-preview*`/`.pp-gen-result*` the same way).
  //
  // `currentDraft` is the single source of truth for what `#tr-gen-result` shows — set by
  // `renderNotesFromDetail` (an existing saved draft, on open), `showGenResult` (a fresh
  // generate), or `saveDraftEdit` (an edit just saved). It never accumulates: each setter
  // REPLACES it wholesale.
  var currentDraft = null;
  var editingDraft = false;

  var EMPTY_REQUESTED_LINE = "Included in the request — nothing came back.";
  var EMPTY_REQUESTED_EXPLAINER = "The response doesn’t say why a requested section " +
    "comes back empty — the sermon may not have covered it, or this run may simply not " +
    "have returned it. Generating again may give a different result.";
  var SCRIPTURE_UNVERIFIED_SUFFIX = " (unverified — not found in the bundled text)";
  var SCRIPTURE_VERIFIED_SUFFIX = " ✓";

  // `d.caveats`/`d.scripture_verdicts` (86akc0tua + 86akby820) — same wire vocabulary
  // `sermon_note_draft_json` produces for both the live-session panel and this one; reused
  // unchanged rather than inventing a second vocabulary (the ticket's own instruction).
  function hasEmptySectionCaveat(d, heading) {
    return !!(d.caveats || []).some(function (c) {
      return c.kind === "section_empty" && c.heading === heading;
    });
  }
  function anySectionEmptyCaveat(d) {
    return !!(d.caveats || []).some(function (c) { return c.kind === "section_empty"; });
  }
  function scriptureVerifiedOrNull(d, reference) {
    var needle = (reference || "").trim();
    var v = (d.scripture_verdicts || []).filter(function (x) {
      return (x.reference || "").trim() === needle;
    })[0];
    return v ? v.verified : null;
  }

  function renderDraftHeader(host) {
    var hd = el("div", "pp-gen-hdr");
    hd.setAttribute("role", "status");
    hd.appendChild(el("span", "pp-gen-badge", (currentDraft.degraded ? "Local draft" : currentDraft.provider)));
    hd.appendChild(el("span", "pp-gen-title", (currentDraft.draft && currentDraft.draft.title) || "Sermon notes"));
    if (currentDraft.aiGenerated) {
      hd.appendChild(el("span", "pp-gen-ai-label", currentDraft.aiLabel));
    }
    host.appendChild(hd);
    if (currentDraft.aiGenerated && currentDraft.disclosure) {
      var disc = el("p", "pp-gen-disclosure", currentDraft.disclosure);
      disc.setAttribute("role", "note");
      host.appendChild(disc);
    }
    if (currentDraft.degraded && currentDraft.degradedNotice) {
      var deg = el("p", "pp-gen-degraded", currentDraft.degradedNotice);
      deg.setAttribute("role", "note");
      host.appendChild(deg);
    }
  }

  function renderDraftView(r) {
    var d = currentDraft.draft || {};
    var showEmptyState = !currentDraft.degraded;
    renderDraftHeader(r);
    if (d.summary) {
      r.appendChild(el("p", "pp-gen-summary", d.summary));
    } else if (showEmptyState && hasEmptySectionCaveat(d, "Summary")) {
      r.appendChild(el("p", "pp-gen-sec-h", "Summary"));
      r.appendChild(el("p", "pp-gen-empty", EMPTY_REQUESTED_LINE));
    }
    (d.sections || []).forEach(function (s) {
      r.appendChild(el("p", "pp-gen-sec-h", s.heading || ""));
      if (showEmptyState && s.empty_requested) {
        r.appendChild(el("p", "pp-gen-empty", EMPTY_REQUESTED_LINE));
        return;
      }
      var ul = el("ul", "pp-gen-list");
      (s.items || []).forEach(function (it) { ul.appendChild(el("li", null, it)); });
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
      d.scriptures.forEach(function (ref, i) {
        if (i > 0) sc.appendChild(document.createTextNode(" · "));
        var verified = scriptureVerifiedOrNull(d, ref);
        var span = el("span", "pp-gen-scr-item", ref);
        sc.appendChild(span);
        if (verified === true) {
          var vMark = el("span", "pp-gen-scr-verified", SCRIPTURE_VERIFIED_SUFFIX);
          vMark.setAttribute("role", "img");
          vMark.setAttribute("aria-label", "verified against the bundled Bible text");
          sc.appendChild(vMark);
        } else if (verified === false) {
          sc.appendChild(el("span", "pp-gen-scr-unverified", SCRIPTURE_UNVERIFIED_SUFFIX));
        }
      });
      r.appendChild(sc);
    } else if (showEmptyState && hasEmptySectionCaveat(d, "Scripture references")) {
      var scEmpty = el("p", "pp-gen-scriptures");
      scEmpty.appendChild(el("span", "pp-gen-sec-h", "Scriptures: "));
      scEmpty.appendChild(el("span", "pp-gen-empty", EMPTY_REQUESTED_LINE));
      r.appendChild(scEmpty);
    }
    var embeddedUnverified = (d.scripture_verdicts || []).filter(function (v) {
      return !v.verified && (d.scriptures || []).indexOf(v.reference) === -1;
    });
    if (embeddedUnverified.length) {
      var elsewhere = el("p", "pp-gen-scriptures");
      elsewhere.appendChild(el("span", "pp-gen-sec-h", "Also referenced in this draft: "));
      embeddedUnverified.forEach(function (v, i) {
        if (i > 0) elsewhere.appendChild(document.createTextNode(" · "));
        elsewhere.appendChild(el("span", "pp-gen-scr-item", v.reference));
        elsewhere.appendChild(el("span", "pp-gen-scr-unverified", SCRIPTURE_UNVERIFIED_SUFFIX));
      });
      r.appendChild(elsewhere);
    }
    if (currentDraft.scriptureVerificationNote) {
      var scNote = el("p", "pp-gen-scripture-note", currentDraft.scriptureVerificationNote);
      scNote.setAttribute("role", "note");
      r.appendChild(scNote);
    }
    if (showEmptyState && anySectionEmptyCaveat(d)) {
      var explainer = el("p", "pp-gen-empty-explainer", EMPTY_REQUESTED_EXPLAINER);
      explainer.setAttribute("role", "note");
      r.appendChild(explainer);
    }
    // Editing needs a transcript id to save against — always set here (this panel only ever
    // shows a draft for the currently OPEN transcript, `openId`).
    if (currentDraft.transcriptId != null) {
      var actions = el("div", "pp-gen-actions");
      var editBtn = el("button", "pp-gen-edit-btn", "Edit");
      editBtn.type = "button";
      editBtn.id = "tr-gen-edit";
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

  // Editable text for existing title/summary/heading/item/point/sub-point wording — mirrors
  // settings.js's own scope decision: FR-130 asks for "editable", not a structural outline
  // builder, so adding/removing a section/item/point stays a later affordance, not faked here.
  function renderDraftEditForm(r) {
    var d = currentDraft.draft || {};
    renderDraftHeader(r);

    var form = el("div", "pp-gen-edit-form");
    form.setAttribute("role", "group");
    form.setAttribute("aria-label", "Edit sermon notes draft");

    var titleInput = document.createElement("input");
    titleInput.type = "text";
    titleInput.id = "tr-edit-title";
    titleInput.value = d.title || "";
    form.appendChild(editField("Title", titleInput));

    var summaryInput = document.createElement("textarea");
    summaryInput.id = "tr-edit-summary";
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
    cancel.id = "tr-gen-edit-cancel";
    cancel.addEventListener("click", function () { editingDraft = false; renderCurrentDraft(); });
    actions.appendChild(cancel);

    var save = el("button", "pp-gen-preview-confirm", "Save");
    save.type = "button";
    save.id = "tr-gen-save";
    save.addEventListener("click", function () { saveDraftEdit(form); });
    actions.appendChild(save);
    form.appendChild(actions);

    r.appendChild(form);
    titleInput.focus();
  }

  // A section round-tripped through the form is still empty — no non-blank item, no
  // point with non-blank text or a non-blank sub-point. Judged on content only, never
  // the heading, matching openai.rs's own emptiness test on the server side and
  // settings.js's own `isStillEmpty` (86akc0tua, bfedaf2) this mirrors.
  function isStillEmpty(s) {
    var hasItem = (s.items || []).some(function (it) { return it && it.trim(); });
    if (hasItem) return false;
    return !(s.points || []).some(function (pt) {
      if (pt.text && pt.text.trim()) return true;
      return (pt.sub_points || []).some(function (sp) { return sp && sp.trim(); });
    });
  }

  // Reads the edit form's current values back into the sections/points/items shape the backend
  // expects — keyed off the SAME positions `renderDraftEditForm` drew the inputs at (scoped to
  // `form`, never `document`, so this is safe even though `.pp-edit-*` classes also exist in
  // settings.js's own edit form elsewhere in the document).
  //
  // 86akc0tua remediation (bfedaf2, Cody's second finding on PR #46 — the first, `generate`'s own
  // persistence call site, is fixed server-side by `sections_to_persist`; this edit-save route has
  // no caveat data at THIS call site to filter on server-side: `NoteSectionInput` carries no
  // `empty_requested` field). This ticket's own edit surface reaches the SAME
  // `update_sermon_note_draft` call as settings.js's, so it needs the identical client-side
  // filter: a section that was `empty_requested` on the loaded draft and is STILL empty after
  // reading the form (the operator did not fill it in) is dropped here before the payload is
  // built — otherwise saving any OTHER edit in this draft would silently persist that section's
  // confusing "bare heading, no explanation" state. A section the operator DID fill in is kept:
  // not a blanket "drop empty sections" filter, only "don't re-persist the exact caveated-empty
  // state unchanged."
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
    var titleEl = document.getElementById("tr-edit-title");
    var summaryEl = document.getElementById("tr-edit-summary");
    var title = titleEl ? titleEl.value : (d.title || "");
    var summaryVal = summaryEl ? summaryEl.value : "";
    var sections = readSectionsFromForm(form, d.sections);
    var scriptures = d.scriptures || []; // scripture list editing is not in this ticket's scope

    var saveBtn = document.getElementById("tr-gen-save");
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
      // Re-read the label/disclosure/provider FROM the backend response — the guarantee that
      // editing cannot drop them belongs to the backend (`sermon_note_repo::update` cannot touch
      // those columns), so this renders exactly what it reports, not what the client assumes.
      currentDraft = {
        transcriptId: currentDraft.transcriptId,
        draft: res.draft || {},
        aiGenerated: !!res.ai_generated,
        aiLabel: res.ai_label || currentDraft.aiLabel,
        disclosure: res.disclosure || null,
        provider: res.provider || currentDraft.provider,
        degraded: currentDraft.degraded,
        degradedNotice: currentDraft.degradedNotice,
        scriptureVerificationNote: res.scripture_verification_note || null,
      };
      editingDraft = false;
      renderCurrentDraft();
    }).catch(function (e) {
      showGenError("transport", String(e && e.message ? e.message : e));
    }).then(function () {
      var b = document.getElementById("tr-gen-save");
      if (b) { b.disabled = false; b.removeAttribute("aria-busy"); }
    });
  }

  // Renders `currentDraft` (view or edit mode) into `#tr-gen-result` — the ONLY place either mode
  // is drawn, so view <-> edit is always a full re-render from the same state.
  function renderCurrentDraft() {
    var r = genResultEl();
    if (!r || !currentDraft) return;
    r.className = "pp-gen-result pp-gen-ok";
    r.setAttribute("role", "status");
    if (editingDraft) renderDraftEditForm(r); else renderDraftView(r);
  }

  // Populates `currentDraft` from `transcript_get`'s OWN response (86akgqdxr) — the saved
  // draft's real content, shown the moment the transcript is opened, not only after a fresh
  // Generate. `#tr-notes-empty` covers the "nothing generated yet" case explicitly.
  function renderNotesFromDetail(t) {
    if (t && t.draft) {
      currentDraft = {
        transcriptId: t.id,
        draft: t.draft,
        aiGenerated: !!t.ai_generated,
        aiLabel: t.ai_label || "AI-generated draft",
        disclosure: t.disclosure || null,
        provider: t.notes_provider || "AI sermon notes",
        degraded: false,
        degradedNotice: null,
        scriptureVerificationNote: t.scripture_verification_note || null,
      };
      editingDraft = false;
      notesEmptyEl.hidden = true;
      renderCurrentDraft();
    } else {
      currentDraft = null;
      editingDraft = false;
      notesEmptyEl.hidden = false;
    }
  }

  function showGenResult(res) {
    if (!res || res.ok !== true) {
      var err = res || {};
      showGenError(err.error || "malformed", err.message || "Something went wrong.");
      return;
    }
    currentDraft = {
      transcriptId: (typeof res.transcript_id === "number") ? res.transcript_id : openId,
      draft: res.draft || {},
      aiGenerated: !!res.ai_generated,
      aiLabel: res.ai_label || "AI-generated draft",
      disclosure: res.disclosure || null,
      provider: res.provider || "AI sermon notes",
      degraded: !!res.degraded,
      degradedNotice: res.degraded_notice || null,
      scriptureVerificationNote: res.scripture_verification_note || null,
    };
    editingDraft = false;
    notesEmptyEl.hidden = true;
    renderCurrentDraft();
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
    // 86akgqdxr: a previous transcript's saved-draft state/empty-state must not leak into the
    // newly opened one either — `renderNotesFromDetail`/`renderDetections` set the real values
    // once the new transcript's data arrives, same discipline as `generateAllowed` above.
    currentDraft = null;
    editingDraft = false;
    if (notesEmptyEl) notesEmptyEl.hidden = true;
    dets = [];
    detWinStart = 0; detWinEnd = 0;
    if (detRowsHost) detRowsHost.innerHTML = "";
    if (detTopSpacer) detTopSpacer.style.height = "0px";
    if (detBottomSpacer) detBottomSpacer.style.height = "0px";
    if (detLogEl) detLogEl.hidden = true;
    if (detEmptyEl) detEmptyEl.hidden = true;
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
  // Test-visible invocation counter (Vera performance review PERF-2 re-check): `box.textContent
  // = ""` below makes two back-to-back calls produce an IDENTICAL final DOM (each clears the
  // other's work before rebuilding), so a check counting `.pp-gen-preview-text` nodes cannot
  // tell "rendered once" from "rendered twice, second one overwrote the first" — this counter
  // is the only way to observe the difference, which is exactly what PERF-2 is about (redundant
  // work, not wrong output).
  window.__trOpenGenPreviewCallCount = 0;
  function openGenPreview(transcript, limit) {
    window.__trOpenGenPreviewCallCount++;
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
