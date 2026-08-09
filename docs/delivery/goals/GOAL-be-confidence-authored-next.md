# Goal Contract — GOAL-be-confidence-authored-next

## Identity

- Goal ID: GOAL-be-confidence-authored-next
- Parent goal ID: 86ajp07k1 (EPIC — Outputs & Displays)
- Title: The Stage/Confidence monitor's "next" line shows the NEXT authored deck slide during Presentation & Media playback (operator-emitted, host-projected), not the stale Preview slide
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajp0aa4 (STORY — Stage / confidence display output; follow-up of BUG 86ajy4czf)
- Created: 2026-08-09
- Updated: 2026-08-09
- Maximum iterations: 10
- Independent verification required: yes

## Objective

During authored **Presentation & Media** deck playback, make the host-rendered Stage/Confidence monitor's "next" line show the NEXT deck slide's text (projected via the shipped `AuthoredSlide::confidence_slide()`), instead of `presenter.staged()` (the stale/empty Preview slide). Do this WITHOUT the host owning the deck — the operator (which owns the deck + cursor) emits the next slide alongside the present; the host stores and projects it. Preserve the ratified Approach A ownership model, wire byte-stability, and all existing behaviour.

## Baseline

Verified this session (two investigations + direct reads):

- The confidence "next" is `LiveController::stage_next_slide()` (`controller.rs:1738`): song-stanza case via `live_idx`, else `presenter.staged().cloned()`. During authored playback `live_idx = None` (cleared at controller.rs:2087) and the host holds only ONE `AuthoredSlide` (`live_authored`) — no deck, no next.
- `Command::PresentAuthoredSlide { slide_json, theme_json }` (`protocol.rs:169`) is the sole operator→host authored-present command; desktop-operator→desktop-host only (mobile never emits it — no Dart fixture; Rust-pinned at `test_protocol.rs:270,364`).
- Ratified design `docs/design/LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md` (Approach A): host stays deck-blind, operator composites/owns decks; teaching the host to own decks is explicitly rejected. The confidence "next" is unspecified there, so this goal must honour that ownership model (operator emits, host projects).
- The operator already knows the next slide: `DeckWorkspace::present_payload` (`deck_workspace.rs:676`, cursor via `go_live_delta`/`effective_selected`) and `DeckLibrary::present_payload` (`deck_library.rs:326`, whole deck + slide id). Neither emits a next today.
- The shipped fix (`37f3bb8`) added `AuthoredSlide::confidence_slide()` — reused here to project the next slide's text.

## Inputs and evidence sources

- Scoping investigation (this session): controller.rs, present.rs, protocol.rs, operator.rs, operator/main.rs, deck_workspace.rs, deck_library.rs, test_protocol.rs.
- `docs/design/LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md` §Why/§5/§6; `docs/delivery/goals/GOAL-be-confidence-authored-content.md:52,109` (tracked follow-up).
- ClickUp: BUG 86ajy4czf (parent fix), STORY 86ajp0aa4, EPIC 86ajp07k1.

## Scope

### In scope

- **Wire (protocol.rs):** additive `next_slide_json: Option<String>` on `PresentAuthoredSlide` (`#[serde(default, skip_serializing_if = "Option::is_none")]`) — byte-stable (absent = None; existing fixture unchanged). Update Rust fixtures + add a with-next case.
- **Host (present.rs):** `Presenter.live_authored_next: Option<AuthoredSlide>`; cleared by `present_authored` (fresh present resets any stale next) and `go_live`; a `set_authored_next(next)` setter; `authored_next_confidence_slide() -> Option<Slide>` (projects via `confidence_slide()`). `present_authored`'s signature is UNCHANGED (avoids churning shipped tests) — the next is set via the setter after a successful present.
- **Host (controller.rs):** `present_authored_slide` gains an optional `next_slide_json`; a malformed/over-bounds next is best-effort dropped (never fails the present). `stage_next_slide()` returns `authored_next_confidence_slide()` when set, before the `staged()` fallback. Dispatch threads the new command field.
- **Operator control (operator.rs, app crate):** `OperatorShell`/`RemoteOperator` `present_authored_slide` carry the optional next.
- **Operator (Tauri crate):** `DeckWorkspace`/`DeckLibrary` emit the next slide's json from the cursor; `Backend::present_authored_slide` + the Tauri handlers thread it.
- **Tests:** protocol round-trip/byte-stability (with + without next); present (set/clear next, projection, go_live clears); controller (PresentAuthoredSlide with next → stage_next_slide shows it); operator present_payload next-slide (workspace + library, incl. end-of-deck → None).

### Non-goals

- Host owning the deck / a host-side `DeckSession` (rejected by Approach A).
- Mobile/Dart changes (mobile never emits `PresentAuthoredSlide`).
- The dedicated authored/notes confidence template (separate design follow-up).
- Auto-advance / deck transitions on the confidence monitor.

### Constraints

- Wire byte-stability: the pinned `present_authored_slide` fixture (`test_protocol.rs:280`) must stay byte-identical for the no-next case.
- `selahcue-present` pure/deterministic, `clippy::unwrap_used = warn` (no unwrap in new code); no unbounded growth (next is one bounded `AuthoredSlide`, same caps as the current).
- Concurrent WIP is in protocol.rs/controller.rs/operator.rs/operator-crate — stage ONLY my hunks at commit.

### Assumptions and unknowns

- ASSUMED: "next" = the slide immediately after the current live slide in deck order; at the last slide there is no next (None → confidence "next" falls back to `staged()`), matching the deck's no-wrap playback.

## Dependencies and approvals

- Owner chose "implement end-to-end now" (this session) over deferring to the presentation-playback effort.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `PresentAuthoredSlide` gains additive `next_slide_json`; no-next JSON is byte-identical; with-next round-trips | `cargo test -p selahcue-lan --test test_protocol present_authored` | passes; pinned no-next fixture unchanged | test_protocol.rs | PASS |
| C-002 | yes | Presenter stores/clears an authored "next" and projects it; `go_live` + a fresh `present_authored` reset it | `cargo test -p selahcue-present --test test_present` | passes | test_present.rs | PASS |
| C-003 | yes | With an authored slide + next live, `stage_next_slide()` returns the next slide's projection; a bad next is dropped, never failing the present | `cargo test -p selahcue-app --features server --test test_controller` | passes | test_controller.rs | PASS |
| C-004 | yes | The operator emits the next slide's json from the deck cursor (workspace + library); end-of-deck → None | `cargo test --manifest-path crates/selahcue-operator/Cargo.toml` | passes | deck_workspace/deck_library tests | PASS |
| C-005 | yes | Operator crate compiles + headless webview check passes | `cargo check --manifest-path crates/selahcue-operator/Cargo.toml` and `python3 scripts/operator_headless.py` | clean | CI logs | PASS |
| C-006 | yes | No regression across the workspace + app `server`; wire fixtures (Rust) consistent | `cargo test --workspace` and `cargo test -p selahcue-app --features server` and `-p selahcue-lan --features server` | all pass | gate output | PASS |
| C-007 | yes | Lint + format gates clean | `cargo fmt --check` and `cargo clippy --workspace --all-targets -- -D warnings` (+ app/lan `server`, operator) | no diff, no warnings | gate output | PASS |
| C-008 | yes | Independent review + owner QA | code-reviewer + owner QA on a real second display | review passes; owner confirms next-slide on confidence during deck playback | pending handoff | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-layer TDD (protocol → present → controller → operator), each test watched to fail first.
- Broader regression: `cargo test --workspace`, `-p selahcue-app --features server`, `-p selahcue-lan --features server`, operator `cargo test`/`cargo check`, `operator_headless.py`; `cargo fmt --check`; clippy `-D warnings`.
- Independent verifier: /code-reviewer; owner QA — during authored deck playback the confidence "next" shows the coming deck slide.
- Required environment: desktop Rust workspace; a second display for owner QA.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004.
- Hypothesis: the host can show a deck-aware next iff the operator emits it (Approach A); an additive wire field + a stored `live_authored_next` + `stage_next_slide` wiring suffices.
- Change or investigation: implement the additive field, presenter next-store + projection, controller wiring, operator emission; TDD each layer.
- Verifier executed: (per layer, pending)
- Result: (pending)
- New evidence: (pending)
- Decision: iterate

## Risks and rollback

- Risks: wire byte-stability regression (mitigated: skip-if-none + pinned-fixture assertion); operator-crate WIP conflict (mitigated: stage-only-mine); end-of-deck/"next" edge (defined: None → staged() fallback).
- Rollback or recovery: additive + localized; revert the hunks to restore prior behaviour (no data/migration impact; the field defaults to None everywhere).

## Pause and escalation conditions

- Any need to make the host deck-aware, change audience output, or alter the ratified Approach A ownership model → escalate (design decision owned elsewhere).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-confidence-authored-next.md`
- Validator result: PASS. Test evidence: lan test_protocol/test_rbac GREEN (byte-stable no-next fixture); present authored_next test GREEN; app test_controller confidence_next GREEN; operator present_payload (next + end-of-deck) GREEN; clippy -D (workspace + lan/app server + operator) clean; fmt clean; operator_headless 545/0.
- Independent verification result: PENDING (code-review + owner QA)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-008 (review + owner QA) PENDING
- ClickUp final evidence comment: PENDING
