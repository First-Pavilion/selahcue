# Goal Contract — TASK-operator-live-transcript-display

## Identity

- Goal ID: TASK-operator-live-transcript-display
- Parent goal ID: NONE
- Title: The operator sees on-device STT text live in the Live Transcript panel, and the panel truthfully reflects that transcription is running
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajtxuwr (Live transcript + scripture auto-detection — R3/R4 slice; status QA)
- Created: 2026-08-02
- Updated: 2026-08-02
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Ensure the recognised text from the on-device STT engine is displayed to the operator in the Operator Console's Live Transcript section, the panel copy honestly reflects that transcription is live, AND the scripture-detection (R4) queue surfaces each detected verse with a genuine confidence/match-% — an explicitly-spoken reference at high confidence, a fuzzy paraphrase at its coverage score — so the operator sees the most-likely verse and how sure the engine is before staging (operator-confirmed, FR-115).

## Baseline

- **Verified:** The display path is already wired. The 1 s poll (`app.js:3464`) calls the top-level `render(view)` (`app.js:7`) → `syncTranscript(view)` (`app.js:3131`), which renders `view.transcript` into `#transcript-log` via `textContent` (untrusted-safe), append-only by segment id, client-capped at 120 rows. The headless harness already asserts `syncTranscript` populates `#transcript-log`.
- **Verified:** The STT worker (`listening.rs`) ingests recognised segments through `Backend::ingest_transcript` (local shell or the pinned-TLS wire to a host), so `view.transcript` is populated on both the standalone and `make launch` paths; the poll surfaces it within ≤1 s.
- **Verified defect:** The listening panel's dynamic copy still says on-device transcription "plugs in here — no lines appear until it lands" (`app.js:3267`) and the code comments say "there is no host listen command yet" / "until it lands no lines are fabricated" — all stale now that STT ships. `test_tokens.rs` pins the string `"transcription (R3)"` as the honest-seam disclosure.

## Inputs and evidence sources

- `dist/app.js` (`render`, `syncTranscript`, `wireTranscriptListen`), `dist/index.html` (`#transcript` section), `src/listening.rs`, `src/main.rs` (`ingest_transcript`, `start_listening`).
- `crates/selahcue-present/tests/test_tokens.rs` (pinned needles), `scripts/operator_headless.py` (webview behavioural gate).

## Scope

### In scope

- Rewrite the Live Transcript panel's listening copy/status (and the stale index.html/app.js comments) to reflect that on-device transcription is running and lines appear as recognised.
- Update the pinned needle that encoded the pre-STT seam disclosure to a truthful, stable pin.
- Add a headless regression check that a transcript-bearing view renders visible text into `#transcript-log` and hides `#transcript-empty`.
- Thread a genuine confidence through the detection engine: expose the fuzzy quote matcher's coverage score (`match_quote_scored`), give explicitly-detected references a high fixed confidence, carry it on `DetectedReference`, and map it to `DetectionView.confidence` so the operator's queue shows a real match-% pill.
- Add a headless check that a detection carrying confidence renders the match-% pill (green ≥90 / amber fuzzy).

### Non-goals

- The backend STT/whisper recognition itself (separate, spike-gated; needs cmake/model — not exercised here).
- Automatic staging / auto-go-live from a detection — staging stays operator-confirmed (FR-115). A push/event transport (the 1 s poll already surfaces text/detections within ≤1 s).
- Changing the wire shape: `DetectionView.confidence` is already an additive `Option<u8>`; only its population changes.

### Constraints

- Untrusted transcript text stays `textContent`, never innerHTML. The `aria-live` log stays append-only (no full re-announce). The 120-row client cap and all other pinned ids/needles/a11y invariants stay intact. `make ci` clean.

### Assumptions and unknowns

- ASSUMED: within-repo verification (headless harness + pins) plus the already-verified poll/ingest wiring is sufficient evidence of display; live whisper QA is owner-run (no cmake here). VALIDATION: owner runs `make launch OP_FEATURES=stt` and speaks a line.

## Dependencies and approvals

- ClickUp evidence to task 86ajtxuwr. No blocking dependency.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A transcript-bearing view renders its text into `#transcript-log` and hides `#transcript-empty` | `python3 scripts/operator_headless.py` (new check) | new transcript-render check passes; 0 FAIL | 139-check run: PASS display: STT segments render + empty-state hidden | PASS |
| C-002 | yes | Panel copy no longer claims STT is unwired (the stale "plugs in" / "until it lands" / "no host listen command yet" phrases removed) | grep for each stale phrase across dist/app.js + dist/index.html | zero matches | grep: zero matches for the stale phrases across dist/ | PASS |
| C-003 | yes | Panel copy affirmatively states on-device transcription is live | `grep -n "On-device transcription" dist/app.js` | present in the listening state copy | app.js:3268 carries "On-device transcription is running…" | PASS |
| C-004 | yes | Pinned token/needle suite green after the copy + needle update | `cargo test -p selahcue-present --test test_tokens` | all pass | test_tokens: 14 passed | PASS |
| C-005 | yes | app.js parses | `node --check dist/app.js` | OK | node --check dist/app.js: OK | PASS |
| C-006 | yes | Full CI gate green | `make ci` | ALL GREEN | ci4.log: "== local CI gate: ALL GREEN ==" (fmt+clippy -D warnings+all suites+flutter) | PASS |
| C-007 | yes | The fuzzy quote matcher exposes a confidence score; a known quote (John 3:16) scores, ordinary speech does not | `cargo test -p selahcue-scripture --test test_quote_match` | new scored-match tests pass | test_quote_match: 12 passed (scored_quote_* new) | PASS |
| C-008 | yes | `DetectedReference` carries a confidence: an explicitly-detected reference is high; a fuzzy quote gets its coverage score; dedup keeps the named (higher) one | `cargo test -p selahcue-core --test test_detection` | new confidence tests pass | test_detection: 26 passed (named-confidence + quote-score new) | PASS |
| C-009 | yes | The controller maps detection confidence into `DetectionView.confidence` (no longer hard-coded None); wire fixtures stay byte-stable | `cargo test -p selahcue-app --test test_controller` + `cargo test -p selahcue-lan --test test_protocol` | detection view carries Some(confidence); `wire_fixtures_are_stable…` green | test_controller 88 + test_protocol 18 passed; wire_fixtures stable | PASS |
| C-010 | yes | The operator queue renders the match-% pill from a confidence-bearing detection | `python3 scripts/operator_headless.py` (new check) | match-% pill check passes; 0 FAIL | headless 141 checks, 0 FAIL (R4 match-% pill 95/72) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `node --check dist/app.js`; `python3 scripts/operator_headless.py`; `cargo test -p selahcue-present --test test_tokens`.
- Broader: `make ci`.
- Independent: owner visual QA in the live Tauri webview with `OP_FEATURES=stt` (speak a line, confirm it appears); headless harness is the in-repo proxy.
- Environment: desktop Rust workspace + node + headless Chrome.

## Iteration ledger

### Iteration 1 — transcript display + honest copy (C-001…C-006)

- Target criterion: C-001…C-006
- Hypothesis: the display already works; making the copy truthful + adding a render regression test closes the operator-visible gap without touching the (correct) render/ingest wiring.
- Change or investigation: confirmed the poll→render→syncTranscript path renders `view.transcript`; rewrote the listening copy/status + stale index.html/app.js comments; retargeted the pinned needle (`transcription (R3)` → `On-device transcription`); added a headless check that a transcript view renders visible text and hides the empty overlay.
- Verifier executed: `node --check` (OK); grep (no stale phrases); `test_tokens` (14); headless (display checks pass).
- Result: PASS.
- Decision: continue → Iteration 2 (build out R4, per the mid-task request).

### Iteration 2 — detection (R4) confidence build-out (C-007…C-010)

- Target criterion: C-007…C-010 (+ re-run C-004/C-006)
- Hypothesis: the detection UI already renders a match-% pill when `confidence` is present; the engine just never populated it. Exposing the quote matcher's coverage score + a high fixed score for explicit references, threaded to `DetectionView.confidence`, lights the pill honestly without any wire-shape change.
- Change or investigation: `match_quote_scored` (scripture); `DetectedReference.confidence` + `NAMED_REFERENCE_CONFIDENCE=95` + scored `ingest_with_quotes` (core, named-first precedence); controller maps it to `DetectionView.confidence` (was `None`); TDD tests in scripture/core/app; headless match-% pill check (green 95 / amber 72).
- Verifier executed: scripture (12), core (26), app (88), lan (18, incl. `wire_fixtures_are_stable`), headless (141 checks, 0 FAIL), full `make ci` ALL GREEN.
- Result: PASS — all 10 criteria PASS.
- Decision: complete → VERIFIED_COMPLETE.

## Risks and rollback

- Risk: changing a pinned needle breaks the cross-file pin test — mitigated by retargeting it to a stable substring of the new copy and running the suite.
- Rollback: the change is copy + one test needle + one harness check; revert the three files.
