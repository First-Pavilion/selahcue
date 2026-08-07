# Goal Contract — TASK-present-deck-to-output

## Identity

- Goal ID: TASK-present-deck-to-output
- Parent goal ID: EPIC-86ajp072p (Service Planning & Library)
- Title: Route the deck editor's "▶ Present" to the native audience output (present an authored slide)
- Role: frontend-engineer (cross-crate: present · lan · app · operator webview)
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajvw08d (bug — created at handoff)
- Origin: user bug report — "clicking 'present' on a presentation does not show it on the output"
- Created: 2026-08-04
- Updated: 2026-08-04
- Maximum iterations: 10
- Independent verification required: yes (`make ci` + full-stack tests incl. remote E2E)

## Objective

Make the deck editor's **▶ Present** show the selected authored slide on the **native audience
output window** (`selahcue-desktop`, wgpu). Before this, `deck_go_live` only set an editor-local
`live` annotation — the documented "decks are not in the LiveController yet" deferral — so
presenting never reached the physical output.

## Baseline (Verified)

- The audience output renders **only** `presenter().live_output()` — a composed title+body `Slide`
  from the scripture/plan/free-text path (`selahcue-desktop` `RedrawRequested`, `main.rs:1804`).
- The deck editor composes real audience pixels via `render_authored_slide` → `FrameBuffer` (the
  SAME compositor), but the whole `AuthoredSlide` machinery lived only inside the excluded operator
  process — never referenced by `selahcue-app`/`-lan`/`-desktop`.
- `deck_go_live` (operator `main.rs:1132`) → `DeckWorkspace::go_live` set only `self.live`.
- The wgpu renderer blits ANY `FrameBuffer`, so **no renderer change is needed** — only a transport
  seam. Chosen approach: **Option C** — a new opaque-JSON wire command + a `Presenter` live slot,
  mirroring the proven `SetCustomTheme` pattern (user-approved scope: "selected slide → output").

## Scope

### In scope
- `selahcue-present`: `Presenter::present_authored(&AuthoredSlide, &Theme)` — composes via
  `compose_authored_slide` and takes over the live surface (clears `live_slide`, like `identify`).
- `selahcue-lan`: `Command::PresentAuthoredSlide { slide_json, theme_json }` (opaque JSON) + rbac
  mapping to the `GoLive` permission (changes what the audience sees; no escalation).
- `selahcue-app`: controller `apply` arm + `present_authored_slide` helper (deserialize + bound-check
  + present, clearing plan/scripture/free-text live cursors); `OperatorShell` + `RemoteOperator`
  `present_authored_slide` wrappers.
- `selahcue-operator`: `DeckWorkspace::present_payload()` (selected slide + theme JSON) + a `Backend`
  dispatch method; `deck_go_live` rewritten to annotate locally AND route to the output; a webview
  success toast ("Now presenting on the audience output").

### Non-goals (documented follow-ups)
- Full on-air deck playback (Next/Prev/auto-advance/transitions) — Option D (a `DeckSession` in the
  LiveController). Secondary-screen / NDI mirroring of a presented authored slide (`compose_screen_live`
  returns idle black while an authored slide is live, matching the `identify` precedent). Persisting a
  presented authored slide across a controller restart (snapshot/restore).

### Constraints
- No renderer change; single audience output (present takes over, plan/scripture Go-Live replaces it;
  Blackout/Clear stay orthogonal). No-leak: `AuthoredSlide::within_bounds()` + `Theme::elements_bounded()`
  reject a hostile/hand-edited payload. Cross-language wire fixtures stay byte-stable (additive command).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `Presenter::present_authored` puts the composed authored slide on Live + takes over (clears `live_slide`); a later plan Go-Live replaces it | `cargo test -p selahcue-present` | pass | `test_present::present_authored_puts_the_slide_on_live_and_takes_over` | PASS |
| C-002 | yes | Wire command round-trips byte-stably + is additive (v2 fixtures hold); rbac maps it to `GoLive` (Operator/Producer only) | `cargo test -p selahcue-lan` | pass | `test_protocol::present_authored_slide_round_trips_and_is_additive` + `every_command_round_trips`; `test_rbac::present_authored_slide_is_go_live_privilege` + `operator_can_do_every_command` | PASS |
| C-003 | yes | Controller `apply(PresentAuthoredSlide)` composes the slide on Live + clears plan cursors; malformed/over-bounds JSON is rejected (Live unchanged) | `cargo test -p selahcue-app` | pass | `test_controller::present_authored_slide_puts_a_deck_slide_on_live_and_takes_over` | PASS |
| C-004 | yes | Full remote loop: `RemoteOperator::present_authored_slide` drives the HOST's live output over pinned-TLS; no plan item is live | `cargo test -p selahcue-app --features server` | pass | `test_operator_remote::remote_present_authored_slide_drives_the_host_live_output` | PASS |
| C-005 | yes | Operator `deck_go_live` annotates locally AND routes the payload; `present_payload` = selected slide+theme, `None` when empty | `cargo test --manifest-path .../selahcue-operator` | pass | `deck_workspace::tests::present_payload_is_the_selected_slide_and_theme_or_none_when_empty` | PASS |
| C-006 | yes | Webview: ▶ Present drives `deck_go_live` and confirms with a toast on success | `operator_headless.py` | pass | `PM: 'Present' confirms it reached the audience output with a toast`; headless 310/0 (`EXPECTED_MIN_CHECKS` 310) | PASS |
| C-007 | yes | Full CI gate green (fmt, clippy -D, all suites incl. cross-language fixtures + operator headless + flutter) | `make ci` | ALL GREEN | `make ci` == **local CI gate: ALL GREEN** (exit 0) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-crate `cargo test` (present/lan/app default + `--features server`/operator), `node --check`,
  `operator_headless.py`. Broader: `make ci`.
- Independent: the seam + options were mapped by an independent explorer before implementation; the remote
  E2E test exercises the exact loopback path the owner's real setup uses.

## Iteration ledger

- Iter 1: investigated (systematic-debugging) — confirmed `deck_go_live` only annotated locally; an
  explorer mapped the full content→output pipeline and the Option A–D seams. User chose Option C.
- Iter 2: implemented bottom-up (present → lan → app → operator → webview), each layer tested before the
  next; `make ci` GREEN.

## Risks and rollback

- Risk: presenting takes over the single live output. Mitigation: mirrors `identify`; plan/scripture
  Go-Live and Clear/Blackout all replace/clear it cleanly (tested). Rollback: additive command —
  reverting the arm restores the prior "annotation-only" behaviour.
- Risk: cross-language wire drift. Mitigation: additive variant; existing v2 fixtures pinned byte-stable
  (verified in `present_authored_slide_round_trips_and_is_additive` + the Dart fixture suite in `make ci`).

## Pause and escalation conditions

- Stop at `make ci` green + owner visual gate (present a deck via `make launch` and confirm the output).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-present-deck-to-output.md --require-complete`
- Validator result: PASS
- Independent verification result: PASS — full-stack tests incl. the remote E2E loop over pinned-TLS;
  `make ci` GREEN.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to 86ajvw08d; BUILD CONTROL 86ajnx548 updated.
