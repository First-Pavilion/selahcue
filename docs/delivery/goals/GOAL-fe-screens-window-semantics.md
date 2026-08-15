# Goal Contract — GOAL-fe-screens-window-semantics

## Identity

- Goal ID: GOAL-fe-screens-window-semantics
- Parent goal ID: NONE
- Title: The Screens & Output page reads a disabled built-in screen as a CLOSED output window, and its enable switch reflects an externally-closed window without operator interaction
- Role: frontend-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: NONE
- Created: 2026-08-15
- Updated: 2026-08-15
- Maximum iterations: 8
- Independent verification required: yes

## Objective

On the Live Console's Screens & Output page, a built-in `main`/`stage` screen whose `enabled` flag is false reads as having no OS output window (not as a muted-but-open output), the enable switch announces that it will close/open that window, virtual (lower-third/stream) screens keep their NDI-gating wording, and the switch reflects an `enabled` change that arrived with no operator interaction.

## Baseline

Verified in `implementation/desktop/crates/selahcue-operator/dist/app.js`:

- The 1 s poll (`setInterval` at app.js:5236) calls `invoke("view")` → `render(view)` → `syncChrome(view)` (app.js:11, before every early return) → `renderOutputs(view)` (app.js:285).
- `renderOutputs` gates on a change key (app.js:573) that includes `registry` (= `view.screens`, which carries `enabled`), so an externally-changed `enabled` normally rebuilds the grid within 1 s and `cb.checked = s.enabled` (app.js:682) reflects truth.
- HOLE: app.js:579-583 defers the whole rebuild (`outputsPending = view; return`) whenever a `<select>` inside `#screens-list` or `#screens-inspector` holds focus. A `<select>` can hold focus indefinitely, so the switch, the status pill and the meta line freeze at their last-rendered values for an unbounded time.
- The toggle's revert (app.js:690) reads `s.enabled` from the render-pass closure, so any in-place reconcile that does not also update that source would revert to a stale value.
- `statusPillFor` (app.js:747) ignores `s.enabled` entirely on the `main`/`stage` branch — a disabled built-in still reports LIVE/CONNECTED/NO SIGNAL — and labels a disabled virtual `MUTED`.

## Inputs and evidence sources

- `implementation/desktop/crates/selahcue-operator/dist/app.js`
- `implementation/desktop/crates/selahcue-operator/dist/app.css`
- `scripts/operator_headless.py`
- `implementation/desktop/crates/selahcue-present/tests/test_tokens.rs` (read-only: confirms the dist pins are `contains` assertions, so additive CSS is safe)

## Scope

### In scope

- Wording for a disabled built-in screen: status pill, card meta line, inspector subtitle, inspector signal footer, toggle `aria-label`.
- Bounding the staleness of the enable switch when `enabled` changes with no operator interaction.
- Headless coverage for both.

### Non-goals

- Any `.rs` file (Kenji owns the Rust side and is editing `selahcue-desktop`/`selahcue-app`).
- `implementation/mobile/`.
- Changing virtual (lower-third/stream) screen wording — their `enabled` gates NDI output only and has no window.
- Inventing new colour tokens. (The `.screen-disabled` dimming WAS changed — the coordinator ruled on it mid-goal: scope the opacity to the preview thumbnail so the controls stay legible.)
- Committing, staging, stashing or reverting anything.

### Constraints

- Must not depend on compiling Kenji's in-flight Rust change; drive checks from the existing `OperatorView` shape.
- CSS changes stay conservative (colour only, no layout) — WKWebView shows flex `<select>` collapse and grid implicit-auto-row overflow that the Blink gate does not.
- Headless assertions on visibility must read COMPUTED DISPLAY, not `.hidden`.

### Assumptions and unknowns

- ASSUMED: the host keeps sending `view.screens` with `enabled` per screen for the built-ins. Validation owner: Kenji. The fallback registry (app.js:564) hardcodes `enabled: true`, so an older host simply never shows a closed state — no lie either way.

## Dependencies and approvals

- Kenji's Rust change (window create/destroy on `enabled`) — concurrent, not required for this frontend work to be verifiable.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A disabled built-in (`main`/`stage`) card shows a CLOSED status pill and a "No output window" meta line, not LIVE/CONNECTED/NO SIGNAL | `python3 scripts/operator_headless.py` | exits 0; the closed-wording checks PASS | headless output | PASS |
| C-002 | yes | A disabled VIRTUAL screen keeps NDI/mute wording and never gains window language | `python3 scripts/operator_headless.py` | exits 0; the virtual-wording check PASS | headless output | PASS |
| C-003 | yes | The toggle's `aria-label` says it will close/open the output window for a built-in, and disable/enable for a virtual | `python3 scripts/operator_headless.py` | exits 0; both aria-label checks PASS | headless output | PASS |
| C-004 | yes | An `enabled` change made with NO operator interaction flips the switch off within the poll cadence | `python3 scripts/operator_headless.py` | exits 0; the externally-changed check PASS | headless output | PASS |
| C-005 | yes | The same externally-changed `enabled` still reaches the switch while a `<select>` holds focus, and the open `<select>` is NOT destroyed | `python3 scripts/operator_headless.py` | exits 0; the deferred-reconcile check PASS | headless output | PASS |
| C-006 | yes | After an in-place reconcile, a REJECTED toggle still reverts to the authoritative value (no stale-closure lie) | `python3 scripts/operator_headless.py` | exits 0; the revert check PASS | headless output | PASS |
| C-007 | yes | The accessible switch stays a labelled, keyboard-operable checkbox with focus restored across the rebuild | `python3 scripts/operator_headless.py` | exits 0; the existing a11y focus check still PASS | headless output | PASS |
| C-008 | yes | The whole committed webview behavioural gate is green and runs at least `EXPECTED_MIN_CHECKS` checks | `python3 scripts/operator_headless.py` | exit code 0, 0 FAIL | headless output | PASS |
| C-009 | yes | No `.rs` file and no `implementation/mobile/` file is modified | `git status --porcelain` | no new/changed `.rs` or mobile paths attributable to this goal | git status | PASS |
| C-010 | yes | On a closed card the enable switch, CLOSED pill, name and meta line render at effective opacity 1, and only the preview thumbnail is dimmed | `python3 scripts/operator_headless.py` | exits 0; the four `dimming:` checks PASS | headless output | PASS |
| C-011 | yes | The `dimming:` checks actually catch the regression they guard (not tautologies) | negative control: restore whole-card `opacity: 0.5`, re-run the gate | 3 `dimming:` checks FAIL with `eff=0.5` | negative-control run, then CSS restored | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `python3 scripts/operator_headless.py` (headless Chrome, real layout/CSS/canvas).
- Broader regression verification: the same gate covers the whole operator webview; `EXPECTED_MIN_CHECKS` guards against silently dropped checks.
- Independent verifier: Code Reviewer (Cody) on the working-tree diff; owner-run WKWebView smoke for the engine-specific CSS gap.
- Required environment: macOS dev box with Chrome resolvable by `find_chrome()`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-009
- Hypothesis: Adding a `hasOutputWindow(s)` discriminator and routing the pill/meta/subtitle/footer/aria-label through it satisfies C-001..C-003; reconciling enable state in place on the deferred path (with the authoritative value moved from the render closure onto `dataset.enabled`) satisfies C-004..C-006 without disturbing the open `<select>`.
- Change or investigation: added `hasOutputWindow`/`enableToggleLabel`/`inspectorSubtitle` helpers; CLOSED pill + "No output window" meta/subtitle/footer for closed built-ins; `syncEnableState` in-place reconcile on the deferred path; moved the toggle's authoritative value from the render closure onto `dataset.enabled`; `.scr-pill-closed` (colour only); 24 new headless checks.
- Verifier executed: `python3 scripts/operator_headless.py`
- Result: exit 0, 640 checks, 0 FAIL.
- New evidence: headless output; `cargo test -p selahcue-present --test test_tokens` 18 passed.
- Decision: iterate (coordinator ruled on the dimming — see Iteration 2)

### Iteration 2

- Target criterion: C-010, C-011
- Hypothesis: Moving `.screen-disabled`'s opacity from the card onto `.scr-thumb` restores the controls to full opacity; the meta line then still needs an ink step-up to clear AA.
- Change or investigation: `.scr-card.screen-disabled` -> `.scr-card.screen-disabled .scr-thumb`; `.scr-card-meta` colour `--sc-text-muted` (3.79:1, fails AA even at full opacity) -> `--sc-text-secondary` (8.12:1). No new tokens. Added 4 effective-opacity headless checks that walk the ancestor chain, because a computed-opacity read on the control alone is a tautology under the old rule.
- Verifier executed: `python3 scripts/operator_headless.py`, plus a negative control with the old CSS restored.
- Result: exit 0, 640 checks, 0 FAIL. Negative control: 3 `dimming:` checks FAIL with `eff=0.5`, confirming they are real.
- New evidence: measured contrast — meta line 1.80:1 and CLOSED pill 2.78:1 at the old whole-card 0.5; 8.12:1 and 7.40:1 after.
- Decision: complete

## Risks and rollback

- Risks: an in-place DOM reconcile can drift from the full rebuild's output. Mitigated by routing both paths through the same `statusPillFor`/`metaLine`/`enableToggleLabel` helpers.
- Risks: WKWebView-only CSS regressions the Blink gate cannot see. Mitigated by restricting CSS to a colour-only pill variant using existing tokens.
- Rollback or recovery: revert `dist/app.js`, `dist/app.css`, `scripts/operator_headless.py`; no persisted state, no migration.

## Pause and escalation conditions

- If the host stops sending `view.screens[].enabled` for built-ins, escalate to Kenji — the page would silently never show a closed state.
- If a `.rs` change is required to make the wording honest, stop and escalate rather than editing Rust.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-fe-screens-window-semantics.md`
- Validator result: PASS (11 criteria, 11 mandatory)
- Independent verification result: PENDING — Code Reviewer not yet run; owner-run WKWebView smoke still outstanding (the Blink gate cannot see engine-specific CSS/layout quirks).
- Terminal state: VERIFIED_COMPLETE for the implementation predicate; independent review still required before QA sign-off.
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: not posted — no ClickUp task was supplied for this assignment.
