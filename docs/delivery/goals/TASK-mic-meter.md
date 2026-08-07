# Goal Contract — TASK-mic-meter

## Identity

- Goal ID: TASK-mic-meter
- Parent goal ID: EPIC (Transcription & scripture intelligence) — STT engine 86ajtxzre
- Title: Show the live microphone-level meter in the Live Console STT section
- Role: frontend-engineer (operator webview)
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajxepha
- Origin: owner request — "show the mic meter on the STT section on the Live Console"
- Created: 2026-08-07
- Updated: 2026-08-07
- Maximum iterations: 8
- Independent verification required: yes (headless + `make ci`)

## Objective

Add a visual microphone-level meter to the Live Transcript (STT) section on the Live Console so the
operator can see input level while listening, driven by the already-emitted `stt://level` event.

## Baseline (Verified)

- The STT source thread emits `stt://level` → `MicLevel { pct: 0..=100 }` (`listening.rs`), ~20/s.
- `wireTranscriptListen` (app.js) already receives it into `micPct`, but only uses it as **status
  text** ("(mic X%)") and a 0%-run "no audio" hint — there is **no visual meter**.
- The STT section is `#transcript` (index.html): head + `#transcript-log` + `#transcript-empty` +
  a `.listen-row` (Start/Stop) + `#transcript-status`. Console uses `--sc-*` tokens.

## Scope

### In scope
- `index.html`: a `#transcript-meter` element in `#transcript` — `role="meter"`
  (`aria-valuemin/max/now`, `aria-label`), a mic glyph, a track + fill, and a numeric `%` readout.
- `app.css`: `.mic-meter*` styles using `--sc-*` (track `--sc-inset`, fill `--sc-primary`); a smooth
  fill transition disabled under `prefers-reduced-motion`.
- `app.js`: an `applyMeter()` that updates fill width + `aria-valuenow` + the numeric % + visibility;
  the `stt://level` handler updates it every tick while listening; the meter shows only while
  listening; the redundant "(mic X%)" status text is removed (the meter carries it, avoiding
  aria-live spam).

### Non-goals (documented follow-ups)
- Peak-hold / clipping (amber) indicator; per-channel meters; a meter for remote (wire) hosts beyond
  the level the host already emits.

### Constraints
- Not colour-only (numeric % always shown); AA; `role="meter"` value updates are not an aria-live
  region (no announcement spam). Existing listen-control behaviour + its headless checks stay green.
  `make ci` green.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A `role="meter"` mic meter exists in `#transcript` with an aria-label, a fill, and a numeric % | headless | present | `#transcript-meter[role=meter]` + `#transcript-meter-fill` + `#transcript-meter-val`; headless "mic-level meter … shown while listening" | PASS |
| C-002 | yes | The meter is hidden when idle and shown while listening | headless | toggles | headless: idle computed `display==="none"`; after Start computed `display!=="none"` | PASS |
| C-003 | yes | An `stt://level` event updates the fill width, `aria-valuenow`, and the numeric % | headless | updates | headless: `stt://level {pct:42}` → `aria-valuenow="42"` + width `42%` + text `42%`; `{pct:0}` → `0%` | PASS |
| C-004 | yes | Not colour-only + reduced-motion honored + AA tokens | headless + code | a11y | numeric % always shown; `.mic-meter-fill` transition removed under `prefers-reduced-motion`; `--accent`/`--sc-inset` fill/track; `.mic-meter[hidden]{display:none}` (gotcha) | PASS |
| C-005 | yes | Existing listen-control checks still pass; token pin covers the meter | headless + `cargo test` | green | headless **312/0** (prior listen checks intact; the removed "(mic X%)" text replaced by meter checks); `test_tokens::operator_webview_is_pinned_to_the_canonical_tokens` PASS (pins `id="transcript-meter"` + `role="meter"`) | PASS |
| C-006 | yes | Full CI gate green | `make ci` | ALL GREEN | `make ci` == **local CI gate: ALL GREEN** (exit 0) — re-run after the concurrent present-flow work settled (it had transiently blocked the shared-tree gate; the mic-meter change is Rust-free and never affected it) | PASS |
| C-007 | yes | Independent review/QA (owner visual gate) | review | none unresolved | self-review (small, additive, isolated — no keyboard trap; not colour-only; reduced-motion honored); owner visual gate handed to QA (`make launch`) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `node --check`; `operator_headless.py` (meter presence, toggle, level→fill/aria/%);
  `test_tokens`. Broader: `make ci`.

## Iteration ledger

- Iter 1 (2026-08-07): implemented the meter — `#transcript-meter` (role=meter) in index.html;
  `.mic-meter*` CSS (tokens, reduced-motion, explicit `[hidden]{display:none}`); `applyMeter()` +
  `stt://level` → fill/aria/% in app.js; removed the redundant "(mic X%)" status text (avoids
  aria-live spam). Headless **312/0** (+2 net: idle-hidden + meter-shown + two level checks replace
  the two old mic-text checks); token pin extended with `#transcript-meter` + `role="meter"`.
- Blocked on the workspace `make ci` by a CONCURRENT session's in-progress present-flow edits
  (`present.rs` `live_authored`, `test_present.rs`) — not the mic-meter change. Verified in isolation
  instead (headless + token pin, both green). Did NOT modify the concurrent files.

## Risks and rollback

- Risk: frequent level events spam aria-live. Mitigation: the meter's `role="meter"` value is not a
  live region; the aria-live status text no longer carries the %. Rollback: additive element.

## Pause and escalation conditions

- Stop at `make ci` green + owner visual gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-mic-meter.md --require-complete`
- Validator result: PASS
- Independent verification result: PASS — headless 312/0 (4 meter checks) + token pin green +
  `make ci` ALL GREEN (re-run after the concurrent present-flow work settled).
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to 86ajxepha; moved to QA for the owner visual gate.
