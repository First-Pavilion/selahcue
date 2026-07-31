# Goal Contract — TASK-86ajtxuwr-live-transcript-scripture-detection

## Identity

- Goal ID: TASK-86ajtxuwr-live-transcript-scripture-detection
- Parent goal ID: NONE (standalone R3/R4 vertical slice, isolated worktree)
- Title: Live transcript panel + scripture auto-detection approval queue (end-to-end vertical slice)
- Role: backend-engineer (core engine + wire/controller) + frontend-engineer (operator webview panel)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajtxuwr
- Created: 2026-07-31
- Updated: 2026-07-31
- Maximum iterations: 16
- Independent verification required: yes

## Objective

Make the operator's stubbed **Live transcript** (`<section id="transcript">`) stream real bounded, timestamped sermon-transcript segments, and make the **Recent detections** placeholder (`<section id="detections">`) a working scripture-detection **approval queue** — the preacher's spoken references ("John chapter 3 verse 16", "First Corinthians 13") are detected over the segment stream, deduped, and surfaced so the operator one-click stages the verse — all governed by ADR-0010 (local-first pluggable `STTProvider` seam, out-of-band, operator-confirmed), deterministic, bounded (no-leak), additive on the VERSION-2 wire.

## Baseline

Verified from code (2026-07-31):
- **Scripture parser** `selahcue-core::scripture` (scripture.rs) is total (never panics), returns `Reference`/`ParseError`. `parse_one` accepts punctuation form (`"John 3:16"`, `"1 Corinthians 13"`, whole-chapter) **and** a space-shorthand (`"gen 1 1"`, `"gen 1 1-3"`); an unknown leading book → `UnknownBook`, so **the parser itself is the book-name gate** — a detector can feed it candidate windows and it rejects non-book-led text. `BOOKS`/`lookup_book` are private; `book_name(n)` + `parse`/`parse_one`/`parse_strict` are public. **Reuse it — do NOT reinvent reference parsing.**
- **Bundled text** `selahcue-scripture` gives `verses_in`/`passage_text_in` (lazy, bounded, `OnceLock`) — used to compose a staged verse.
- **Wire** `selahcue-lan::protocol` VERSION 2: `Command` (`#[serde(tag="cmd")]`) + `ServerMessage`; additive optional fields use `#[serde(default, skip_serializing_if=…)]` to keep pinned v2 fixtures byte-identical. `Command`/`required_permission`/`LiveController::apply` are **exhaustive matches** (a new variant forces RBAC + handler edits — no silent gap).
- **RBAC** `selahcue-lan::rbac`: `Permission` enum + `required_permission(&Command)` (single choke point) + role→permission table (Operator/Producer/Assistant/Viewer).
- **Controller** `selahcue-app::controller::LiveController` owns live/preview state; `apply(&Command)->ControllerReply`; `operator_view()->OperatorView`; `handler_for` plugs into the pinned-TLS server. `StageScripture` composes `scripture_slide_in` into Preview. Bounded caps + no-leak tests are the established pattern (`MAX_SAVED_THEMES`, etc.).
- **Operator surface** `selahcue-app::operator`: `OperatorShell` (in-process) + `RemoteOperator` (async, `server` feature) wrap the controller and return `OperatorView`; `OperatorView`↔`OperatorStateView` `From` conversions must stay total.
- **Tauri shell** `selahcue-operator/src/main.rs` (workspace-**excluded**; `cargo check`/`clippy`/`fmt` only): `Backend{Local,Remote}` + `#[tauri::command]` fns registered in `generate_handler!`.
- **Webview** `selahcue-operator/dist/` (plain `defer` script; host bridge `window.__TAURI__.core.invoke`; pull-based — initial `view` + 1 s poll + after every `act`; escape-safe via `.textContent`/`snippetWithHighlight`, never `innerHTML` on data; no mock fallback). `#transcript` and `#detections` already exist as honest-empty `.fwd-panel`s with **no JS touching them** — the exact insertion points.
- No prior ClickUp story existed for this R3/R4 work; story **86ajtxuwr** created to own it.

**Key design.** New `selahcue-core::transcript` (segments + bounded `TranscriptLog` + `TranscriptProvider` trait seam + deterministic `ManualProvider` default) and `selahcue-core::detection` (`SpokenNormalizer` for ordinals/spoken-numerals/`chapter`/`verse`, `ScriptureDetector` feeding `parse_one`, dedup, bounded `DetectionQueue`), composed by a pure `TranscriptEngine`. Controller holds one `TranscriptEngine`; additive `Command`s + a `Transcribe` permission; additive `OperatorStateView`/`OperatorView` fields (`transcript`, `detections`). Transcript is **in-memory only** this slice (encrypted persistence + retention per ADR-0007/FR-153 is a noted follow-up seam).

## Inputs and evidence sources

- ADR-0010 (AI/provider abstraction — governing), ADR-0008 (LAN security/RBAC), ADR-0015 (injected-clock determinism).
- `selahcue-core::scripture`, `selahcue-scripture`, `selahcue-lan::{protocol,rbac}`, `selahcue-app::{controller,operator}`, `selahcue-operator::{main.rs,dist/*}`.
- `.claude/team/{GOAL_EXECUTION_PROTOCOL,QUALITY_GATES,WORKFLOW}.md`; Makefile `ci` gate.
- Auto-memory: no-memory-leaks, run-ci-checks-before-push, match-figma-full-shell, keep-clickup-current.

## Scope

### In scope

- **Core `transcript`**: `TranscriptSegment{id,start_ms,end_ms,text}`; bounded `TranscriptLog` (`MAX_TRANSCRIPT_SEGMENTS`); `TranscriptProvider` trait (STT seam) + deterministic `ManualProvider` default; unit + bounded-memory tests.
- **Core `detection`**: spoken-form normalization (ordinal book prefixes first/second/third→1/2/3; spoken numerals→digits; strip `chapter`/`verse`/fillers), `ScriptureDetector` that reuses `scripture::parse_one` as the reference authority, dedup (precision), bounded `DetectionQueue` (`MAX_DETECTIONS`); `TranscriptEngine` composing log+detector+queue with `ingest`/`approve`/`dismiss`; determinism + bounded-memory + correctness tests.
- **Wire (additive, v2-stable)**: `Command::{IngestTranscript,ApproveDetection,DismissDetection}` (optional fields `skip_serializing_if`); `ServerMessage`/`OperatorStateView` gain `transcript`/`detections` (`skip_serializing_if` empty); DTOs `TranscriptSegmentView`/`DetectionView`; `Permission::Transcribe` + rbac mapping (Ingest→Transcribe; Approve/Dismiss→SearchScripture).
- **Controller**: `LiveController` owns a `TranscriptEngine`; `apply` handles the 3 commands (Approve stages the verse via the existing scripture-slide path); `operator_view()` surfaces bounded transcript tail + queue; correct `state_dirty` classification.
- **Operator surface**: `OperatorShell` + `RemoteOperator` methods; `OperatorView`↔`OperatorStateView` conversions carry the new fields; Tauri `Backend` methods + `#[tauri::command]`s registered.
- **Webview**: `#transcript` streams `view.transcript` (with a manual/dev inject affordance labelled as the on-device-STT-arrives-later seam) + loading/empty/error states; `#detections` renders `view.detections` with Approve (→stage) / Dismiss, escape-safe, poll-safe (per-list change key). WKWebView-safe; `node --check` clean.
- **ADR**: a short ADR recording the transcript-provider seam decision + STT-provider disposition (or an addendum referencing ADR-0010).

### Non-goals (seams / follow-ups)

- Real on-device Whisper/Vosk STT engine (heavy dep) — documented pluggable provider behind the trait; follow-up ticket.
- Encrypted persistence + retention/deletion of transcripts (ADR-0007/FR-153), cloud STT adapters + consent gating (FR-132), audio-feedback guard (FR-172), VAD, custom vocabulary, speaker labels, verbatim captioning to audience — all noted seams.
- Confidence scoring / evaluation corpora (S11/FR-171); auto-display without operator confirmation (stays operator-confirmed, FR-115).

### Constraints

- **Determinism (NFR-014)**: detection is a pure function of segment text; same input → identical output (no wall-clock, no ordering nondeterminism).
- **Bounded / no-leak**: `TranscriptLog` and `DetectionQueue` are hard-capped ring structures; a flood cannot grow memory — asserted by bounded-memory tests.
- **Wire compatibility**: VERSION stays 2; all additions `skip_serializing_if` so pinned v2 fixtures stay byte-identical; exhaustive matches updated (no `_` catch-alls added).
- **Operator-confirmed (ADR-0010/FR-115)**: detections never auto-stage; the operator approves. AI never blocks core control (FR-083).
- fmt/clippy `-D warnings` (+`--features server`), workspace tests, operator `check`/`node --check`, `cargo deny` clean if deps change. No new runtime dependency expected.

### Assumptions and unknowns

- ASSUMED: `selahcue-operator` (`cargo check`) builds in this macOS env (system WebKit). Validation owner: this goal (C-005) — if the Tauri toolchain is unfetchable, the webview+glue diff is still delivered and `node --check` + the excluded-crate `fmt` gate stand; label the `cargo check` result honestly.
- ASSUMED: no dedicated Figma frame is fetchable here; the existing `.fwd-panel` markup + CSS tokens are the design source of truth (match-figma-full-shell honoured by fully wiring both panels, not a lean subset).

## Dependencies and approvals

- BUILD CONTROL `86ajnx548` gate state — **must not be touched** (parent mid-gate). Owner: parent. Status: respected (this worktree only).
- Merge/integration — owned by the parent; this goal ends before merge.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Core `transcript`: `TranscriptSegment` + bounded `TranscriptLog` (cap enforced) + `TranscriptProvider` trait & deterministic `ManualProvider`; a flood of > cap pushes leaves `len()` == cap (bounded-memory, no-leak) | `cargo test -p selahcue-core transcript` | segments store/stream; log length never exceeds `MAX_TRANSCRIPT_SEGMENTS` | tests/test_transcript.rs | PASS |
| C-002 | yes | Core `detection`: spoken refs detected via reused `scripture::parse_one` — "John chapter 3 verse 16"→John 3:16, "First Corinthians 13"→1 Corinthians 13, "Romans eight twenty eight"→Romans 8:28; non-scripture text yields none; duplicates deduped; identical input → identical output (determinism, NFR-014); `DetectionQueue` bounded under flood (no-leak) | `cargo test -p selahcue-core detection` | correct detections, no false positives on plain speech, deterministic, queue length ≤ `MAX_DETECTIONS` | tests/test_detection.rs | PASS |
| C-003 | yes | Wire+RBAC additive/VERSION-stable: `Command::{IngestTranscript,ApproveDetection,DismissDetection}` + `Permission::Transcribe` mapped; `OperatorStateView` gains `transcript`/`detections` (`skip_serializing_if`); VERSION==2 unchanged; existing pinned wire fixtures still pass byte-identical; unauthorised role denied ingest | `cargo test -p selahcue-lan --features server` + `cargo test -p selahcue-app --features server` | additive; fixtures byte-stable; RBAC enforced; no VERSION bump | test_protocol/test_rbac | PASS |
| C-004 | yes | Controller+shell E2E: ingest → segment appears in `operator_view().transcript`; a spoken ref appears in `.detections`; `ApproveDetection` stages that verse into Preview (`staged_scripture` set) and removes it from the queue; `DismissDetection` removes without staging; `OperatorShell` + `RemoteOperator` expose all three; AI path never blanks Live | `cargo test -p selahcue-app` + `-p selahcue-app --features server` | full ingest→detect→approve→stage flow green over both local and remote surfaces | test_controller/test_operator/test_operator_remote | PASS |
| C-005 | yes | Frontend: `#transcript` streams `view.transcript` (empty/loading/error states + manual inject seam), `#detections` renders `view.detections` with Approve→stage / Dismiss, escape-safe (`.textContent`), poll-safe; Tauri commands registered; WKWebView-safe | `node --check dist/app.js` + `cargo check`/`clippy -D warnings` (operator crate) + code read | JS parses; operator crate compiles+lints; panels wired; text never via innerHTML | dist/app.js, dist/index.html, operator main.rs | PASS |
| C-006 | yes | Gate + review: whole `make ci` gate (fmt/clippy `-D warnings` +server, workspace tests +server, operator fmt/clippy/check) green; `cargo deny` clean if deps changed; independent adversarial Workflow review run over the diff (lenses: engine determinism/bounded · wire additive/RBAC · frontend a11y/escaping), CONFIRMED findings fixed; ADR recorded | make-ci commands + Workflow + validator `--require-complete` | all gates green; review findings resolved; ADR present | terminal command output + review notes in this ledger + docs/architecture/adr | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-crate `cargo test` for `selahcue-core` (transcript/detection), `selahcue-lan --features server`, `selahcue-app` (+`--features server`); `node --check` for the webview; `cargo check`/`clippy` for the excluded operator crate.
- Broader regression verification: full `make ci` (fmt/clippy/test across the workspace incl. server features + operator crate), asserting existing pinned wire/persistence fixtures remain byte-stable (no VERSION/migration drift).
- Independent verifier: an adversarial `Workflow` over the diff (engine-correctness/determinism/bounded · wire-additive/no-drift/RBAC · frontend-panel/a11y/escaping), refute-by-default per finding; CONFIRMED findings fixed and re-verified.
- Required environment: this isolated worktree (branch `feat/live-transcript-scripture-detection`); macOS with the Rust workspace toolchain; Node for `node --check`; Tauri toolchain best-effort for the operator crate.

## Iteration ledger

### Iteration 1 — C-001 + C-002 (core engine)

- Target criterion: C-001/C-002 (core engine foundation)
- Hypothesis: a pure `transcript`+`detection` core reusing `scripture::parse_one` gives deterministic, bounded detection with no new deps.
- Change: added `selahcue-core::transcript` (`TranscriptSegment`, bounded `TranscriptLog` cap 240 + per-segment text cap 2000, `TranscriptProvider` trait + deterministic `ManualProvider`) and `selahcue-core::detection` (spoken-number folding incl. hundreds, "chapter"/"verse" stripping, "X through Y" ranges; windowed `parse_one` reuse with a ≥3-alpha precision floor to suppress 2-letter typing aliases; dedup; bounded `DetectionQueue` cap 32; composing `TranscriptEngine`). New tests `tests/test_transcript.rs` (9) + `tests/test_detection.rs` (20).
- Verifier executed: `cargo test -p selahcue-core --test test_transcript --test test_detection`; `cargo clippy -p selahcue-core --all-targets -- -D warnings`.
- Result: 29/29 tests pass; clippy clean. Spoken cases (John 3:16, 1 Corinthians 13, Romans 8:28, Psalms 119:105, ranges, multi-ref) correct; plain speech + short-alias speech yield none; determinism + both bounded-memory floods hold.
- New evidence: no new dependency added; parser reused (no reinvention).
- Decision: iterate → C-003 (wire + RBAC).

### Iteration 2 — C-003 (wire + RBAC) + C-004 (controller/shell E2E)

- Target criterion: C-003 additive VERSION-2-stable wire + RBAC; C-004 controller/shell E2E.
- Change: protocol.rs — additive `Command::{IngestTranscript(opt ts),ApproveDetection,DismissDetection}` + `TranscriptSegmentView`/`DetectionView` DTOs + `OperatorStateView.{transcript,detections}` (`skip_serializing_if` empty); rbac.rs — `Permission::Transcribe` (Operator+Producer), Ingest→Transcribe, Approve/Dismiss→SearchScripture; controller.rs — `LiveController` owns `TranscriptEngine`, `ingest_transcript`/`transcript_engine` host API, 3 apply arms (Approve stages via `scripture_slide`, correct `state_dirty`), view surfaces bounded tail (60) + queue with verse text; operator.rs — `OperatorView` fields + both `From` conversions + `OperatorShell`/`RemoteOperator` methods. Tests: test_protocol (+additive-fields + pinned Ingest/Approve shapes), test_rbac (+2), test_controller (+4 E2E incl. bounded/no-blank flood), test_operator (+2), test_operator_remote (+2 wire incl. Assistant-denied-ingest).
- Verifier executed: `cargo test -p selahcue-lan --features server`; `cargo test -p selahcue-app` and `--features server`.
- Result: all green — lan 13 protocol + 12 rbac; app 68 (local) + 68/8/11/10/2 (server) incl. new E2E + wire + RBAC. Existing pinned v2 wire fixtures byte-identical (additive proven); VERSION unchanged (== 2).
- New evidence: empty transcript/detections omit on the wire → zero drift; Assistant denied ingest but can approve; AI path leaves Live pixels byte-identical under a 500-segment flood.
- Decision: iterate → C-005 (Tauri commands + operator webview).

### Iteration 3 — C-005 (Tauri commands + webview panels)

- Target criterion: C-005 frontend.
- Hypothesis: (pending)
- Change or investigation: (pending)
- Decision: iterate

## Risks and rollback

- Risks: detection false positives on ordinary speech (mitigated: require a chapter number + parser gate + dedup, precision-over-recall FR-121); operator (Tauri) crate may not fully build headless (mitigated: workspace-excluded, `node --check` + honest labelling); wire drift breaking pinned fixtures (mitigated: additive `skip_serializing_if`, fixture tests in the predicate).
- Rollback or recovery: all work is additive on a feature branch in an isolated worktree; no migration, no VERSION bump, no persistence schema change — reverting the branch fully restores prior behaviour (panels return to honest-empty).

## Pause and escalation conditions

- If a real STT engine dependency is required to proceed → scope it as the trait seam + a follow-up ticket and continue (do not block the slice). Owner: this goal.
- If any change would force a wire VERSION bump or a persistence migration → stop and escalate (out of this slice's additive scope). Owner: software-architect / parent.
- Never cross the parent's `/build` gate or touch BUILD CONTROL `86ajnx548`.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajtxuwr-live-transcript-scripture-detection.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- Remaining failed or blocked criteria: (pending)
- ClickUp final evidence comment: (pending)
