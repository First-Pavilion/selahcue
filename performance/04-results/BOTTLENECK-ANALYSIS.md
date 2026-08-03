# Bottleneck Analysis

Source: an exhaustive independent static hot-path / unbounded-collection scan of the whole workspace,
corroborated by the executed test evidence. **No true memory leak was found** — no uncapped collection on
any hot or long-running path. The findings are CPU/allocation-churn and lock-contention risks, ranked by
product impact. None is Critical or High; none can blank live output.

The ranking weights *product impact under real service use*, not micro-cost. Render-path lock findings
(#4/#6) rank near the efficiency findings because "never-blank" makes any render-path delay a correctness
concern, even though both are currently sub-frame and bounded.

---

## Finding 1 — STT interim re-transcribes the whole growing utterance every ~0.8 s — MEDIUM

- **Evidence:** `selahcue-stt/src/engine.rs` `emit_interim()` calls `recognizer.transcribe(&self.utterance, …)`
  over the **entire** accumulated buffer; driven at `interim_interval_frames` cadence, set to `40` (~0.8 s)
  in `selahcue-operator/src/listening.rs`.
- **Cost:** the buffer grows to `max_utterance_samples` = 10 s. Whisper transcription is ~O(audio length),
  so per utterance the interims re-transcribe 0.8 s, 1.6 s, … 10 s ≈ **6–7× the real audio duration** in
  transcription work (interims dominate; the final close adds one more full pass).
- **Bounded, not a leak:** the 10 s force-close caps any single pass and the whole buffer. It cannot grow
  without limit — this is a CPU/real-time-factor risk, not a memory risk.
- **Why it matters:** on a weaker CPU the RTF could rise enough that interims lag the speech they exist to
  surface. It runs on a **dedicated worker thread, out-of-band from render**, so it can never stall the
  audience output — the risk is CPU headroom, not a blank screen.
- **Cheaper option:** transcribe only the newly-appended tail, or a fixed trailing window, instead of the
  whole buffer. The code already flags this (`listening.rs` comment: "a sliding-window pass is a perf
  follow-up").
- **Coverage:** memory is gated (`bounded_memory.rs`); RTF/CPU cost is not (a bounded-memory test can't
  cover it). A micro-benchmark on RTF is the follow-up's acceptance gate.
- **Owner:** ai. Severity **MEDIUM**. Non-blocking.

## Finding 2 — Fuzzy quote matcher re-tokenizes every candidate verse on every final segment — MEDIUM

- **Evidence:** `selahcue-scripture/src/quote_match.rs` — inside the per-candidate scoring loop,
  `let v_tokens: BTreeSet<String> = tokenize(&v.text).into_iter().collect();` allocates a fresh `Vec` +
  `BTreeSet` **per candidate, per call**. `QuoteIndex` precomputes `df`/`postings`/`verse_mass` but **not**
  per-verse token sets, so this repeats on every query. Driven per final segment in
  `selahcue-app/src/controller.rs` (`match_quote_scored(&window)` over a 3-segment rolling window).
- **Cost:** bounded by `MAX_CANDIDATES = 5000` + discriminative-token / shared-mass thresholds. Typical
  spoken quotes yield tens of candidates; a pathological input could hit the 5000 cap → up to 5000 verse
  re-tokenizations per final segment. Not a leak, not on the render path (final-segment cadence, seconds
  apart), but real allocation churn on a spike.
- **Cheaper option:** memoise the per-verse token `BTreeSet` (or a sorted token slice) in `QuoteIndex` at
  build time — the build already tokenizes each verse once and discards the result.
- **Coverage:** correctness/bounds gated (`test_quote_match::the_indexes_are_bounded_and_idempotent`,
  `test_detection::engine_ingest_with_quotes_is_bounded_under_a_flood_of_candidates`); per-call cost is not.
- **Owner:** ai. Severity **MEDIUM**. Non-blocking.

## Finding 3 — Native render loop re-uploads the full ~8 MB framebuffer + rebuilds bind group every frame — LOW-MEDIUM

- **Evidence:** `selahcue-desktop/src/main.rs` `Renderer::render` — `queue.write_texture(… frame.bytes() …)`
  uploads the whole 1920×1080×4 ≈ 8.3 MB buffer, and `create_bind_group(…)` + a texture view are recreated
  **every** frame. `new_events` unconditionally `request_redraw()`s both windows every ~16 ms, so this runs
  at ~60 Hz per window even when the slide is static.
- **Cost:** ~500 MB/s upload per window × 2 windows continuously, plus per-frame GPU-object churn, for
  content that changes only on operator action. Bounded, no leak, but wasteful bandwidth/power for a
  projector app that idles on a static slide most of the time. The **compose** path is already correctly
  cached (recompose only on state change; `live_output()` returns a cached buffer) — only the GPU upload is
  redundant.
- **Cheaper option:** a frame-content generation/dirty flag; skip `write_texture` + redraw when unchanged
  (still upload on resize/first-frame).
- **Owner:** backend/graphics. Severity **LOW-MEDIUM**. Non-blocking. Most relevant to the idle-power /
  idle-RSS NFR still to be measured (M18).

## Finding 4 — RemoteOperator serialises all commands *and* console-thumbnail polls behind one mutex across the network round-trip — LOW-MEDIUM

- **Evidence:** `selahcue-operator/src/main.rs` — `Backend::Remote(Box<tokio::sync::Mutex<RemoteOperator>>)`;
  every command does `m.lock().await.<op>().await`, holding the lock across the wire request/response. The
  read-only `render_console` / `render_screen` thumbnail polls take the **same** lock.
- **Cost:** head-of-line blocking. Only one wire request in flight is inherent to a single control channel
  (fine), but sharing the lock with frequent thumbnail/state polls means a laggy poll serialises against a
  live `go_live`/`blackout`. It is a `tokio::sync::Mutex`, so no OS thread blocks — a stalled host still
  delays the next control command.
- **Cheaper option:** split read-only thumbnail/state fetches onto a separate connection/lock, or make them
  best-effort/cancellable.
- **Owner:** frontend/backend. Severity **LOW-MEDIUM**. Non-blocking. Affects the remote (mobile-driven)
  path only; the local operator path uses a synchronous std mutex with no await inside the critical section.

## Finding 5 — `operator_view()` fully rebuilds and deep-clones the view-model on every poll and command — LOW

- **Evidence:** `selahcue-app/src/controller.rs` `operator_view()` clones plan item titles, the 60-segment
  transcript tail, all saved-theme JSON blobs (≤ `MAX_SAVED_THEMES = 256`), the screen registry/themes, and
  does a `parse_one` + `passage_text` verse lookup **per pending detection** (≤ `MAX_DETECTIONS = 32`). Runs
  on every 1 Hz operator poll and after every command.
- **Cost:** everything bounded → no leak, no stall, but a non-trivial allocation+lookup burst per poll. Fine
  at 1 Hz; would matter only if poll frequency rose.
- **Cheaper option:** memoise the verse lookups / dirty-track the view if poll cadence ever increases.
- **Owner:** backend. Severity **LOW**. Non-blocking.

## Finding 6 — Controller mutex held across the wgpu present in the redraw path — LOW

- **Evidence:** `selahcue-desktop/src/main.rs` — `self.controller.lock()` then `r.render(main_out)` runs
  `get_current_texture` + submit + `present()` **while holding the controller lock**. With `PresentMode::Fifo`,
  the swapchain acquire can block up to a vsync (~16 ms), during which the control-server thread cannot apply
  a remote command.
- **Cost:** mild render-thread ↔ control-thread contention; a remote command can wait up to ~one frame.
  Bounded and small.
- **Cheaper option:** read `live_output()` into a local frame and drop the lock before presenting.
- **Owner:** backend. Severity **LOW**. Non-blocking.

---

## Minor notes (not ranked)

- **`ManualProvider.pending`** (`selahcue-core/src/transcript.rs`) is an unbounded `VecDeque` grown by
  `submit`/`submit_segment`, drained only on `poll()`. It is the deterministic **test/host-injection**
  provider — its only non-doc reference outside the type is under `#[cfg(test)]` in `pump.rs`; the
  production STT path is `SttEngine → SegmentSink → SttProvider::poll → controller.ingest_transcript(...)`
  and never wires it to a live source. A one-line bound is worth adding only if it ever backs a live ingest.
- **`SessionRegistry.pending`** (LAN) has no hard **count** cap the way `active` does (256). It relies on
  expiry-prune plus operator-only reachability: `pending` is grown only by the operator's P-keypress pairing
  offer (plus a one-time host seed), and the prune runs immediately before each offer, so it is TTL-bounded
  and not reachable by an untrusted/remote peer. Safe today, but **asymmetric** with `active`; adding a
  count cap would make the bound a local invariant rather than a reachability argument. Filed as PERF-8.
- **`ServicePlan::add_item`** is itself uncapped, but every production caller enforces `MAX_PLAN_ITEMS = 500`
  (`Command::AddItem`, the local operator shell, and the restore path); `insert_item` has no production
  caller. Verified during independent review — not a leak, noted for completeness.

---

## Verified well-bounded (checked, not a risk)

Called out explicitly so the review is honest rather than padded — these were specifically inspected and are
correctly capped:

- **STT engine** — `frame_buf`/`frame_scratch`/`utterance` reuse capacity (`clear()`, not realloc); `VecDeque`
  front-pop is O(1); utterance force-closed at 10 s. `PcmRing` capped by `MAX_PCM_SAMPLES`; `SegmentSink` by
  `MAX_PENDING_SEGMENTS = 256`; worker→drain channel a **bounded** `mpsc(256)` with `try_send` that drops
  under backpressure and never blocks.
- **Core transcript/detection** — `TranscriptLog` ring 240 segs + 2000 B/seg (UTF-8-safe truncate);
  `DetectionQueue` ring 32; `recent_refs` ring 16; controller `recent_texts` ring 3.
- **Rasterizer text caches** — thread-local `SwashCache`/`FontSystem` fully rebuilt every 4096 renders;
  system-font enumeration capped; image decode cache bounded (test).
- **Compose auto-fit** — `wrap_at` memoises per-word widths (O(words), not O(words²)), capped at 1000 words;
  ShrinkToFit is a binary search over the cell (O(log h)), not linear.
- **Config/registry maps** — `saved_themes` (256 + name-length + element bounds on every ingress incl. load);
  `screen_registry` (16); defensive drops on the load path.
- **LAN** — WebSocket frame/message capped at 64 KiB; session registry self-prunes (expired/idle) with a hard
  active-session cap; `RemoteOperator` holds no buffers of its own.
- **Locks** — `OperatorShell` std mutex `with()` closure never awaits; the STT `WORKER` static mutex is held
  only to swap an `Option`, and `stop()` takes the worker out **before** joining (no lock-across-join).
- **GPU compositor** — allocates per-call textures/buffers, but that is the **offscreen parity/readback path
  only**; it does not drive the on-screen surface (the desktop CPU-composites and blits), so its per-call
  allocation is test-time, not the 60 Hz loop.
