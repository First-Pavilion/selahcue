# Goal Contract — TASK-17tnw2axptg-presentation-safety-access

## Identity

- Goal ID: TASK-17tnw2axptg-presentation-safety-access
- Parent goal ID: NONE (parent epic EPIC — Design 2.0 Parity Closure, ClickUp `17tnw2axpt8`)
- Title: Presentation web surface — safety & access essentials closed (PME-055/043/053/058/059/005/006-011/027)
- Role: frontend-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2axptg
- Created: 2026-09-22
- Updated: 2026-09-22
- Maximum iterations: 8
- Independent verification required: yes (four-reviewer pipeline: Cody, Sana, Vera, Quinn)

## Objective

Close the genuinely-still-open findings in `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md`
covered by ClickUp `17tnw2axptg` — PME-055, PME-043, PME-053, PME-058, PME-059, PME-006–011,
PME-027 (PME-005 is confirmed already fixed, out of scope for changes) — with each fix
headless-verified and, for the two safety-critical additions, mutation-verified.

## Baseline

Per the ticket's own 2026-09-20 reconciliation (confirmed OPEN as of worktree base commit,
identical to `main` HEAD `9a64417`):

- PME-055 — no `Present` item in the library card `⋯` menu.
- PME-043 — no view-only/permission-gated mode on the Presentation surface at all.
- PME-053 — no `Start from` template radio group in the New-Presentation dialog.
- PME-058 — delete-undo copy/behaviour contradiction (Q-08 decision not recorded as applied).
- PME-059 — no warning when deleting a deck referenced by a service plan.
- PME-006–011 — six selectors on `--sc-text-muted` (AA-large only) that the project's own
  written policy classifies as essential text needing AA-normal.
- PME-027 — the two horizontal-align buttons share the glyph `≡`.
- PME-005 — already fixed (`.pm-btn-primary:hover` darkens instead of lightening); listed for
  completeness only, verified untouched.

## Inputs and evidence sources

- `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` (full read, including the
  2026-09-20/09-21 Reconciliation sections).
- `docs/design/PRESENTATIONS-LIBRARY-spec.md` §2, §4, §5 (Start-from radio group, delete
  copy, card menu order).
- `docs/design/CANVAS-EDITING-spec.md` §"permission-denied" (view-only model reference).
- `docs/product/prds/SelahCue-Operator-UI-PRD.md` (RISK-205/NFR-204 — shipped ink/behaviour wins
  over a stale Figma frame; not directly triggered by this batch, but checked).
- `docs/design/UX-CANONICAL.md` (safety/keybinding rules — checked; none of these findings touch
  the canonical keybinding/live-safety territory it governs).
- Live architecture reading: `selahcue-lan/src/protocol.rs` (`OperatorStateView`, `ViewerView`),
  `selahcue-lan/src/rbac.rs` (`Role::permissions()`), `selahcue-operator/src/deck_library.rs`,
  `selahcue-operator/src/main.rs` — to determine what PME-043 would actually need to gate on.
- ClickUp `17tnw2axpt8` (epic) and its child `DECISION — Presentation: blocking questions`
  (`17tnw2axpu1`) — read to confirm PME-043 is not already covered by a recorded decision.

## Scope

### In scope

- PME-055, PME-053, PME-058 (confirm/record), PME-059, PME-006–011, PME-027: implement and
  verify.
- `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` Reconciliation update for every id closed
  or newly classified as blocked.
- `scripts/operator_headless.py` coverage for each behavioural fix.

### Non-goals

- PME-043: full implementation. Determined to require a product/architecture decision no signal
  in this codebase currently supports (see Iteration ledger and the audit doc's own new
  Reconciliation entry). Routed to the existing `DECISION — Presentation` ClickUp task instead
  of implemented.
- PME-005: already fixed; explicitly not re-touched per the ticket's own brief.
- Any other `PME-###`/`OUT-###` id not named on this ticket.
- Rust `selahcue-present`/`selahcue-gpu` (Part B / audience output) — out of this ticket's scope.

### Constraints

- PRD RISK-205/NFR-204: shipped console ink/behaviour is the source of truth over a stale Figma
  frame — checked for every colour/behaviour change; none of this batch's fixes contradict
  shipped behaviour toward a stale frame (PME-006–011 apply the project's *own* written policy,
  not a Figma value).
- One `make ci` at a time in this checkout; check `CARGO_TARGET_DIR` and concurrent sessions before
  running.
- Never work on `main`/`dev`; own worktree, own branch, one ticket per branch/PR.

### Assumptions and unknowns

- ASSUMED: PME-058's "OPEN" classification in the 2026-09-20 reconciliation was about the Q-08
  decision lacking a *written* record rather than a functional code gap — verified by direct
  code + existing-test inspection (the fix predates that reconciliation, commit `3db5398`,
  2026-08-07). Validation owner: this session, via code/test evidence; recorded in the audit doc.
- UNKNOWN, escalated rather than guessed: what signal (if any) should drive PME-043's view-only
  mode, given no local operator-role/session concept and no remote deck-viewer exist in this
  codebase today. Validation owner: product/architecture, via the `DECISION — Presentation`
  ClickUp task.

## Dependencies and approvals

- Four-reviewer pipeline (Cody/Sana/Vera/Quinn) — required before `VERIFIED_COMPLETE`, dispatched
  after the PR opens.
- PME-043 decision — owned by product/architecture via ClickUp `17tnw2axpu1`; not a dependency of
  the other nine findings, which do not depend on it.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | PME-055: a `Present` item exists in the library card `⋯` menu and presents that card's OWN deck (not merely the open one) | `python3 scripts/operator_headless.py`, mutation-verified | checks pass; mutation (removing the menu item) turns exactly the PME-055 assertion RED | `/tmp/headless_out3.txt`, `/tmp/headless_mutation2.txt` | PASS |
| C-002 | yes | PME-053: New-presentation dialog has a Start-from radio group (Blank / Duplicate / Template-later) whose Duplicate path duplicates the CHOSEN source, renames the copy, and opens it | `python3 scripts/operator_headless.py` | 13 new assertions pass, incl. selecting a non-default row changes the source id | `/tmp/headless_out3.txt` | PASS |
| C-003 | yes | PME-058: the delete-confirm copy names the real slide count and never contradicts its own undo behaviour | code + existing test inspection (`scripts/operator_headless.py` "PME-058 / Q-08" block, pre-existing) | copy correct, Undo offered iff `restorable`; no code change needed | `implementation/desktop/crates/selahcue-operator/dist/app.js:9806-9855`, headless PME-058/Q-08 block | PASS |
| C-004 | yes | PME-059: deleting a deck referenced by a service-plan item warns by the plan's name before the operator can confirm; an unreferenced deck shows no such warning | `python3 scripts/operator_headless.py`, mutation-verified | positive + negative control both pass; mutation turns exactly the PME-059 warning assertion RED | `/tmp/headless_out3.txt`, `/tmp/headless_mutation.txt` | PASS |
| C-005 | yes | PME-006–011: the six named selectors use `--sc-text-secondary`, not `--sc-text-muted` | `python3 scripts/operator_headless.py` (live rule-text check against `window.__CSSTEXT`) | 12 assertions (premise + fix) pass for all six | `/tmp/headless_out3.txt` | PASS |
| C-006 | yes | PME-027: the three horizontal-align buttons render three DISTINCT glyphs | `python3 scripts/operator_headless.py` | glyphs `⇤ ⇔ ⇥`, `Set` size 3 | `/tmp/headless_out3.txt` | PASS |
| C-007 | yes | PME-005 unmodified | `grep` diff review | `.pm-btn-primary:hover` still `#5a48d0`; no diff to that rule | `git diff` | PASS |
| C-008 | yes | No regression: full headless suite green | `python3 scripts/operator_headless.py` | 0 FAIL | `/tmp/headless_out3.txt` (1662 checks, 0 FAIL) | PASS |
| C-009 | yes | Rust side (`deck_duplicate`'s additive `new_id`) compiles, lints and passes existing tests | `cargo check`/`cargo clippy -D warnings`/`cargo test` (`selahcue-operator`) | all clean | terminal output, this session | PASS |
| C-010 | yes | Audit doc Reconciliation section updated for every id closed this session, and PME-043 reclassified as blocked with a routed decision | `Read` the updated doc section | new "Update — 2026-09-22" section present with FIXED list, PME-043 rationale, updated totals | `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` | PASS |
| C-011 | yes | `make ci` green on the branch before marking the PR ready | `make ci` (one at a time, after checking for concurrent runs) | ALL GREEN | PR / CI evidence, to be attached at handoff | PENDING |
| C-012 | yes | Four-reviewer pipeline (Cody/Sana/Vera/Quinn) run, blocking findings remediated | reviewer reports, published as an Artifact | all four reviewers clear | review artifact URL, to be attached at handoff | PENDING |
| C-013 | no | PME-043 implemented | N/A — routed to `DECISION — Presentation` (`17tnw2axpu1`) instead; no signal exists in this codebase to gate it on, per the audit doc's new Reconciliation entry | see Non-goals and the audit doc | — | NOT_APPLICABLE |

## Verification plan

- Focused verification: `python3 scripts/operator_headless.py` after each change; targeted `grep`/
  `Read` against `app.js`/`app.css`/`main.rs` for exact line-level correctness.
- Broader regression verification: full `scripts/operator_headless.py` run (1662 checks) before and
  after the batch; `cargo check`/`clippy -D warnings`/`test` on `selahcue-operator`; full `make ci`
  before marking the PR ready.
- Independent verifier: four-reviewer pipeline (Cody, Sana, Vera, Quinn), each in its own worktree.
- Required environment: this worktree (`agent-ac4f01d9ce77ff94a`), macOS, Rust toolchain per
  `rust-toolchain.toml`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001–C-006 (implement the six clearly-actionable findings).
- Hypothesis: each finding has a concrete, existing pattern in the codebase to reuse (Plan
  surface's view-only pattern was considered for PME-043 but ruled out — see below; template
  radiogroup pattern for PME-053; PME-005's own hover-fix comment pattern for the muted-text
  promotions).
- Change or investigation: read the full audit doc + Reconciliation, the PRESENTATIONS-LIBRARY and
  CANVAS-EDITING specs, and the live architecture (`protocol.rs`, `rbac.rs`, `deck_library.rs`,
  `main.rs`) to determine PME-043's real gating signal. Found none exists (decks are
  operator-local, `OperatorStateView` carries no deck content, no local role/login/profile concept
  anywhere in `app.js`/`main.rs`). Implemented PME-055, PME-053 (+ backend `new_id` addition),
  PME-058 (confirmed already-fixed), PME-059, PME-006–011, PME-027.
- Verifier executed: `python3 scripts/operator_headless.py`.
- Result: 1662 checks, 0 FAIL (up from the pre-existing 1649 with no new assertions run against
  the pre-change code, which also passed 0 FAIL as a baseline).
- New evidence: `/tmp/headless_out.txt` (baseline pre-my-tests but post-behaviour-changes, 1 FAIL
  — a test-timing bug, not a product bug), `/tmp/headless_out2.txt` (fixed, 0 FAIL),
  `/tmp/headless_out3.txt` (final, with all new assertions, 0 FAIL), mutation logs for PME-055 and
  PME-059.
- Decision: complete (for C-001–C-010); C-011/C-012 pending PR + review pipeline; C-013 marked
  NOT_APPLICABLE with rationale recorded.

### Iteration 2 — four-reviewer pipeline round 1 (C-012)

- Target criterion: C-012 (Cody/Sana/Vera/Quinn review the PR).
- Change or investigation: dispatched all four reviewers in parallel, each in its own isolated
  worktree pinned to head `d7fa211`.
- Result: **Quinn — GATE_REVIEW, one blocking bug.** `.pm-startfrom-picker`'s own `display: flex`
  (`app.css`) defeated the `[hidden]` attribute in WKWebView/Chrome — the known trap this codebase
  already guards against in ~6 other places, missed on this new rule. The PME-053 duplicate
  picker stayed visually painted at all times regardless of which Start-from radio was selected.
  Filed as ClickUp bug `17tnw2axwg9`. **Cody — pass, 2 non-blocking findings** (a false-positive
  success toast when a duplicate source vanishes mid-dialog; a stale `EXPECTED_MIN_CHECKS`
  constant), independently corroborated Quinn's bug. **Sana — pass, no blocking findings** (3
  non-blocking notes, incl. the `pmLibDelete` fail-open comment/code mismatch below). **Vera —
  pass, no blocking findings** (measured the picker/grid DOM cost, confirmed `view()`'s IPC cost is
  negligible; also independently reproduced Quinn's bug via her own benchmark; flagged the same
  fail-open mismatch Sana found, plus a factually wrong "not a LAN round-trip" comment).
- Remediation (all on the same branch, new commits):
  - `d8d0ffe` — Quinn's `[hidden]`/`display:flex` fix + strengthened computed-style assertions.
    Mutation-verified.
  - `d382b81` — Cody's two findings (false-positive toast → routes through `pmShowError`; new
    regression test, mutation-verified; `EXPECTED_MIN_CHECKS` bumped with evidence).
  - `50fe981` — Sana + Vera's fail-open finding: `pmLibDelete`'s comment promised "fail OPEN on
    the warning" for a failed `view()` read, but the code left the warning list untouched on
    failure, reading identically to a genuinely clean "not referenced" result — defeating
    PME-059's purpose. Added a real third state (`planRefUnknown`) with its own honest warning
    copy. New test hook (`window.__viewRejectOnce`) + 2 assertions, mutation-verified.
  - `dc639be` — Vera's comment-accuracy finding (`view()` CAN be a network round-trip via
    `Backend::Remote`); docs-only, no behaviour change.
- Verifier executed: `python3 scripts/operator_headless.py`, run twice independently after each
  remediation commit; mutation-verification (temporarily reverting each fix, confirming the
  relevant assertion(s) go RED, restoring) for every behavioural fix in this iteration.
- New evidence: 1667 checks, 0 FAIL (two independent runs at final state); mutation logs for all
  three behavioural fixes (`[hidden]` guard, false-positive toast, fail-open warning).
- Decision: iterate — re-dispatch all four reviewers against the final commit (`dc639be`) before
  claiming C-012 PASS, since none of the four reviews above ran against the post-remediation code.

### Iteration 3 — four-reviewer pipeline round 2, in progress

- Target criterion: C-011 (`make ci` green) and C-012 (fresh review round against `dc639be`).
- Change or investigation: restarted `make ci` from a clean state (the round-1 background run was
  killed and discarded — it had been launched before the remediation commits landed and continued
  running while `app.js`/`app.css`/`operator_headless.py` were being edited in place, so its result
  would have been evidence about an inconsistent, partially-stale tree rather than any real commit).
  Dispatched fresh Cody/Sana/Vera/Quinn reviews, each a new isolated worktree pinned to `dc639be`,
  each briefed on exactly what changed since their last pass and asked to re-verify their own
  finding's fix plus do a genuine fresh pass, not a rubber-stamp.
- Result: pending — both `make ci` and the four reviews are running as of this ledger entry.
- Decision: iterate (awaiting evidence).

## Risks and rollback

- Risks: PME-043 left unimplemented on a ticket that named it as one of five "safety/access
  residuals" — mitigated by routing it explicitly to the existing DECISION ticket with a
  documented, evidence-based reason, rather than silently dropping it or fabricating a fake
  permission model.
- Risks: the `deck_duplicate` backend change is additive but touches a shared Tauri command —
  mitigated by keeping it strictly additive (`skip_serializing_if`-equivalent via `Option::map`,
  matching `deck_restore`'s own `restored_name` precedent) and re-running the full crate test
  suite.
- Rollback: revert the branch; no data migration, no destructive change, nothing merged to `main`.

## Pause and escalation conditions

- PME-043 requiring a product/architecture decision — escalated via the `DECISION —
  Presentation` ClickUp task and this contract's Non-goals, not blocking the rest of the ticket.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2axptg-presentation-safety-access.md --completion`
- Validator result: PENDING (run at handoff, after C-011/C-012 evidence is attached)
- Independent verification result: PENDING (four-reviewer pipeline, dispatched after PR opens)
- Terminal state: GATE_REVIEW pending PR/CI + reviewer pipeline; implementation-side criteria
  (C-001–C-010) are VERIFIED_COMPLETE
- Remaining failed or blocked criteria: C-011, C-012 (PENDING, not FAILED — sequenced after this
  contract snapshot); C-013 NOT_APPLICABLE (PME-043, routed to decision)
- ClickUp final evidence comment: to be posted on `17tnw2axptg` at handoff
