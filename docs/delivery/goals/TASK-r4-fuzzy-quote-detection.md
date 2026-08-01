# Goal Contract — TASK-r4-fuzzy-quote-detection

## Identity

- Goal ID: TASK-r4-fuzzy-quote-detection
- Parent goal ID: EPIC 86ajp08rm (R4 · Scripture Intelligence)
- Title: Fuzzy quote/paraphrase detection — spoken quotation of a verse → most-likely verse, wired to STT
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajp08rm (R4 epic — no dedicated story; owner elected to track under this Goal Contract)
- Created: 2026-08-01
- Updated: 2026-08-01
- Maximum iterations: 12
- Independent verification required: yes

## Objective

When a scripture is spoken as a (near-verbatim) quotation or close paraphrase without its
reference being named, the detection engine surfaces the most-likely verse as an
operator-confirmed suggestion in the existing approval queue — alongside the existing exact
reference detector — by adding the **fuzzy** rung of the R4 detection ladder
(parse → exact → **fuzzy** → semantic). The STT output is wired into the detection engine so
any `TranscriptProvider` (the on-device `SttProvider` or a fake) flows text through it.

## Baseline

- Exact/explicit reference detection exists: `selahcue_core::detection::detect(text)` (reuses
  `scripture::parse_one`) + `TranscriptEngine::ingest` → bounded `DetectionQueue`
  (`DetectedReference { id, reference, source_segment }`). Precision-biased; ordinary speech
  does not fire.
- Corpus + search live in `selahcue-scripture` (sorted `Vec<Verse>` per translation via
  `OnceLock`; `search` is a linear substring AND-match with **no scoring/ranking**;
  `display_reference` builds a parseable `"John 3:16"`). `index_of(t)` is the internal index.
- Dependency arrow: `selahcue-core` (zero deps) ← `selahcue-scripture` ← `selahcue-app`. Core
  **cannot** see the corpus; the matcher must live in `selahcue-scripture`, invoked from
  `selahcue-app` (`LiveController::ingest_transcript` → `TranscriptEngine`).
- No fuzzy/semantic/embedding infrastructure exists. Approve stages to Preview only (FR-115).
- Working tree note: concurrent operator-console work has uncommitted edits to `controller.rs`
  / operator / lan (NOT `detection.rs` / `scripture`). This work stages surgically.

## Inputs and evidence sources

- ClickUp R4 epic 86ajp08rm; ADR-0019, ADR-0010; `docs/research/CAPABILITY-ASSESSMENT.md` (fuzzy = string/lexical similarity; paraphrase unreliable → suggestion-only), `PROVIDER-TRADEOFFS.md` (parse→exact→fuzzy→embeddings ladder).
- `selahcue-core/src/detection.rs`, `selahcue-scripture/src/lib.rs`, `selahcue-app/src/controller.rs`.

## Scope

### In scope

- `selahcue-scripture`: `match_quote(text) -> Vec<String>` — an offline, deterministic,
  precision-gated IDF-weighted token-overlap matcher with a lazily-built (`OnceLock`), bounded
  inverted index over the default (KJV) corpus; returns the most-likely verse(s) as canonical
  references above thresholds, else empty.
- `selahcue-core`: additive `TranscriptEngine::ingest_with_quotes(text, start, end, quote_refs)`
  — enqueues exact detections AND externally-matched quote candidates through the same
  recent-dedup + bounded queue; `ingest` delegates to it with `&[]` (behaviour unchanged).
- `selahcue-app`: run `match_quote` in `ingest_transcript` and pass its results to
  `ingest_with_quotes`; add a tested `pump_transcript(controller, provider)` that drains any
  `TranscriptProvider` into `ingest_transcript` (the STT↔detection wiring).
- Tests (deterministic, bounded, precision) + one independent review.

### Non-goals

- Confidence score in the detection model / wire / operator UI (deferred scope option).
- Semantic/embeddings paraphrase (barred from auto-display; no infra; separate spike).
- Auto-display (always operator-confirmed, FR-115). Multi-translation matching (KJV default).
- Real desktop hookup of the whisper `SttEngine` on a worker thread (thin host follow-up;
  the seam is proven with a fake/manual provider).

### Constraints

- Offline, deterministic (no clock/RNG; canonical tie-break), bounded memory (index built once;
  candidate scoring bounded). Precision over recall (FR-121): ordinary speech must not fire.
- No wire/view change; VERSION-stable. No new dependencies. No change to the exact detector's behaviour.

### Assumptions and unknowns

- ASSUMED: thresholds tuned so near-verbatim quotes hit and ordinary speech does not — validated by C-002/C-004; exact values provisional (spike-gated S11).
- UNKNOWN: real-world precision/recall on live ASR output — spike-gated (S11), owner: QA/AI-eng.

## Dependencies and approvals

- Design approved by owner (o.majiyagbe) in session, 2026-08-01. Ticketing: Goal-Contract-only (owner decision).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `match_quote` returns the correct verse for a near-verbatim quote (e.g. John 3:16 from "for God so loved the world…") | `cargo test -p selahcue-scripture --test test_quote_match quote` | test passes | test output | PENDING |
| C-002 | yes | `match_quote` returns nothing for ordinary (non-scripture) speech — precision over recall (FR-121) | `cargo test -p selahcue-scripture --test test_quote_match precision` | test passes | test output | PENDING |
| C-003 | yes | `match_quote` is deterministic (same input → same output; canonical tie-break) | `cargo test -p selahcue-scripture --test test_quote_match determin` | test passes | test output | PENDING |
| C-004 | yes | A near-verbatim quote with a minor word omitted/changed still matches (fuzzy tolerance) | `cargo test -p selahcue-scripture --test test_quote_match fuzzy` | test passes | test output | PENDING |
| C-005 | yes | The matcher index is built once and bounded (idempotent init; no unbounded growth) | `cargo test -p selahcue-scripture --test test_quote_match bounded` | test passes | test output | PENDING |
| C-006 | yes | `TranscriptEngine::ingest_with_quotes` enqueues quote candidates alongside exact detections, deduped + bounded; a quote duplicating an exact/recent ref does not double-enqueue | `cargo test -p selahcue-core --test test_detection quote` | test passes | test output | PENDING |
| C-007 | yes | Existing exact-detection behaviour is unchanged (`ingest` == `ingest_with_quotes(…&[])`) — regression | `cargo test -p selahcue-core --test test_detection` | all existing tests pass | test output | PENDING |
| C-008 | yes | App `ingest_transcript` runs BOTH exact + quote: injecting a spoken quote surfaces the verse in the detection queue | `cargo test -p selahcue-app --test test_quote_detection ingest` | test passes | test output | PENDING |
| C-009 | yes | `pump_transcript` drives a `TranscriptProvider` (ManualProvider) end-to-end into the detection queue (STT↔detection wiring) | `cargo test -p selahcue-app --test test_quote_detection pump` | test passes | test output | PENDING |
| C-010 | yes | No wire/view change and no new dependencies: the detection wire model is untouched; no crate gains a dependency | review: my staged diff touches no `selahcue-lan` file and no `[dependencies]` line | confirmed | staged diff | PENDING |
| C-011 | yes | fmt + clippy clean on the changed crates | `cargo fmt -p selahcue-core -p selahcue-scripture -p selahcue-app -- --check && cargo clippy -p selahcue-core -p selahcue-scripture -p selahcue-app -- -D warnings` | no diffs, no warnings | command output | PENDING |
| C-012 | yes | Independent review passes with evidence; findings addressed | code-reviewer subagent | no unresolved high/critical findings | review report | PENDING |

## Verification plan

- Focused: per-criterion `cargo test` filters on the three crates.
- Broader regression: existing `test_detection` + `test_scripture` suites stay green; the exact detector is unchanged.
- Independent verifier: code-reviewer subagent.
- Required environment: Rust stable; no native toolchain/model needed (matcher is pure Rust over the bundled corpus).

## Iteration ledger

### Iteration 1

- Target criteria: C-001..C-011.
- Hypothesis: an IDF-weighted token-overlap matcher over the KJV index, precision-gated, recovers near-verbatim quotes while ordinary speech stays silent; wired additively into the detection engine + STT pump with no wire/UI change.
- Change or investigation: (pending)
- Verifier executed: (pending)
- Result: (pending)
- Decision: iterate

## Risks and rollback

- Risks: threshold too low → false positives (mitigated by C-002 precision test + operator-confirmation, never auto-live); index memory (mitigated by C-005 bounded/idempotent init); controller.rs concurrent edits (mitigated by surgical staging).
- Rollback or recovery: all additive — revert the scripture module + the one `ingest_transcript` hunk + the additive core method; the exact detector and wire are untouched, so reverting fully restores prior behaviour.

## Pause and escalation conditions

- If precision cannot be met without also losing near-verbatim recall at any single threshold → pause, record the trade-off, and escalate the threshold/algorithm to AI-eng (do not ship a false-positive-prone default).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-r4-fuzzy-quote-detection.md`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- Remaining failed or blocked criteria: (pending)
- ClickUp final evidence comment: (pending)
