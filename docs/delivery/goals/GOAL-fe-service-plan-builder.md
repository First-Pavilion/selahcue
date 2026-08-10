# Goal Contract — GOAL-fe-service-plan-builder

## Identity

- Goal ID: GOAL-fe-service-plan-builder
- Parent goal ID: 86ajp072p (EPIC — Service Planning & Library)
- Title: Implement the Service Plan builder + link-Scripture/Presentation flows + a populated console plan panel in the operator webview, wired to the backend content-reference API, keeping make ci green
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxxuz9
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 20
- Independent verification required: yes

## Objective

In the operator webview (`implementation/desktop/crates/selahcue-operator/dist/` — `index.html` / `app.js` / `app.css`), turn the `plan` placeholder surface into a real Service Plan builder (Add-item palette · run sheet · item inspector), add the link-Scripture and link-Presentation modal flows, and render link status (linked / unlinked / missing) in the run sheet and the console Service Plan panel — all wired to the backend `set_item_content` command + `PlanItemView.link`, matching `docs/design/SERVICE-PLAN-2.0-HANDOFF.md` and preserving the live-cueing invariant, with `make ci` green.

## Baseline

- Backend content-reference API is implemented (task 86ajxxuye, code review): `set_item_content` command + additive `PlanItemView.link` (`{kind, reference?, translation?, verses_per_slide?, id?}`). Verified.
- The operator webview has a console Service Plan panel (`#plan-wrap`) rendering plan-item rows + quick-add; the dedicated `plan` surface is a placeholder. The Scriptures browser + Presentations library already exist in the webview (reusable for the pickers).
- CI frontend gates: operator `cargo check`, `scripts/operator_headless.py`, and `selahcue-present/tests/test_tokens.rs` string-needle wiring checks.

## Inputs and evidence sources

- ClickUp 86ajxxuz9 + SERVICE-PLAN-2.0-HANDOFF.md (Figma section 614:124).
- Operator webview `dist/{index.html,app.js,app.css}`; `test_tokens.rs`; `operator_headless.py`.
- Backend wire: `selahcue-lan/src/protocol.rs` (`SetItemContent`, `PlanItemView.link`, `ContentLinkView`).
- Scout report (this session) mapping surface routing, plan render, command send, CSS tokens, and test needles.

## Scope

### In scope

- Console Service Plan panel renders `item.link` (scripture ref / deck / missing) — the run surface is no longer a placeholder.
- The `plan` surface becomes a Service Plan builder: Add-item palette, run sheet (typed rows + link status + duration/owner), item inspector.
- Link-Scripture modal (reuse the Scriptures browser) and link-Presentation modal (reuse the Presentations library) → `set_item_content`.
- Inspector link states (unlinked / scripture-linked / presentation-linked / missing) + a way to set/clear a link.
- Accessibility (keyboard, roles/labels, focus) and the live-cueing invariant (select stages Preview; Go Live commits).

### Non-goals

- Backend changes (done in 86ajxxuye) — this is UI wiring only.
- Redesigning the Scriptures browser / Presentations library / deck editor (reused, not rebuilt).
- The mobile controller (separate).

### Constraints

- Reuse existing webview patterns (surface router, command-send, modal/overlay, Design-2.0 `--sc-*` tokens + component classes). No new framework.
- Keep `make ci` green: satisfy the `test_tokens.rs` wiring needles, the operator compile-check, and `operator_headless.py`.
- Preserve the live-cueing invariant and emergency chrome; never send a Go-Live from a plan edit.

### Assumptions and unknowns

- ASSUMED: the webview's existing modal/overlay + command-send patterns are reusable for the pickers (scout confirms).
- UNKNOWN: exact `plan`-surface container + render hook (scout resolves).

## Dependencies and approvals

- Depends on backend 86ajxxuye (content-reference API) — implemented.
- Independent review/QA — owner: code-reviewer/qa. Status: pending.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The console Service Plan panel renders link status from `item.link` (scripture ref / deck / missing), not a placeholder | operator_headless.py / DOM inspection + review | a linked item shows its scripture ref or deck; missing shows a ⚠ affordance | headless: "SP C-001" checks (scripture chip, deck-name resolves, ⚠ missing, boot-load, failed-load → generic) all PASS; screenshot | PASS |
| C-002 | yes | The `plan` surface is a real Service Plan builder (palette + run sheet + inspector), replacing the placeholder | headless / review of dist | the plan route renders the three regions | headless "SP C-002" (7-kind palette + run sheet + inspector + empty CTA) PASS; screenshot `plan-builder.png` | PASS |
| C-003 | yes | A link-Scripture flow sets a scripture link via `set_item_content` (reference + translation) | code review of the command send + a wiring assertion | selecting a passage sends `{cmd:"set_item_content",...link:{kind:"scripture",...}}` | headless "SP C-003" asserts the exact payload; app.js `planScriptureBody`→`commit` | PASS |
| C-004 | yes | A link-Presentation flow sets a deck link via `set_item_content` (deck id from the library) | code review + wiring assertion | choosing a deck sends `{cmd:"set_item_content",...link:{kind:"deck",id}}` | headless "SP C-004" (select-then-confirm: no premature commit, `Link to item` sends `{kind:deck,id}`, deleted-deck preselect guarded) PASS | PASS |
| C-005 | yes | The inspector shows link state (unlinked / linked / missing) + set/clear | review / headless | each link state is visibly distinct + actionable | headless "SP C-005" (linked chip + Change…/Unlink/Remove; unlinked warning + Link…; role=option/aria-selected) PASS; screenshot | PASS |
| C-006 | yes | Live-cueing invariant preserved + key states (empty/loading/permission) handled per handoff | review + headless | plan edits never send Go-Live; states render | headless "SP C-006": zero live-control commands across the whole builder session incl. Open-in-Live (nav-only) + rejected-link stays open; adversarial invariant lens confirmed | PASS |
| C-007 | yes | Accessibility: keyboard operable, roles/labels, focus for the modals | review / headless a11y checks | modals focus-trap; controls labelled | headless "SP C-007 a11y": Tab-trap wraps last→first (non-tautological), scripture modal focuses the input, reorder buttons labelled, aria-modal/role=alert; adversarial a11y lens (2 rounds) confirmed | PASS |
| C-008 | yes | `make ci` is green (operator check + headless webview + test_tokens + all suites) | `make ci` | exit 0 | final run exit 0: fmt+clippy(0 warn) + workspace/feature tests + operator check + **headless 426 checks/0 FAIL** (REQUIRE=1) + flutter 95 tests; banner "== local CI gate: ALL GREEN ==" | PASS |
| C-009 | yes | ClickUp 86ajxxuz9 carries goal ID, engine, iteration evidence, terminal state | inspect task comments | start + evidence comments present | ClickUp 86ajxxuz9 evidence comment; follow-up 86ajy02zq linked | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `operator_headless.py`; targeted DOM/behaviour inspection; the `test_tokens.rs` wiring needles for the new surfaces.
- Broader regression: full `make ci`.
- Independent verifier: code-reviewer/qa for UX + accessibility + wiring; not self-certified (C-008).
- Required environment: operator webview + headless Chrome; workspace.

## Iteration ledger

### Iteration 1

- Target criterion: setup (C-009)
- Hypothesis: a scout map of the webview (routing, plan render, command send, CSS, test needles) is a prerequisite to surgical edits.
- Change or investigation: dispatched a scout; authored this contract.
- Verifier executed: python3 scripts/validate_goal_contract.py
- Result: contract valid
- New evidence: task 86ajxxuz9
- Decision: iterate

### Iteration 2 — Increment A: console panel + link modal + Tauri bridge

- Target criteria: C-001, C-003, C-004
- Change: console `render()` now renders `item.link` via `planLinkChip` (scripture ref / deck / ⚠ missing); `openLinkModal` (scripture + deck pickers) → `set_item_content`; added the full Tauri bridge (`OperatorShell.set_item_content` + remote client + `main.rs` command/handler/`Backend`).
- Verifier executed: `cargo build -p selahcue-app --features server`; operator `cargo check`; `operator_headless.py`; `test_tokens`.
- Result: compiles clean; headless PASS; test_tokens 18 PASS.
- Decision: iterate.

### Iteration 3 — Increment B: the `plan` builder surface

- Target criteria: C-002, C-005, C-006
- Change: `#surface-plan` placeholder → real builder (7-kind palette · run sheet · inspector) via `planActivate`/`planRenderBuilder`/`planRenderInspector`; link states + invariant note.
- Verifier executed: `operator_headless.py`; screenshot of the `plan` route with a mock plan.
- Result: builder renders all link states; PASS.
- Decision: iterate.

### Iteration 4 — behavioural coverage + make ci

- Target criteria: C-007, C-008
- Change: added 18 plan-builder DOM-assertion checks to the CI headless driver (the builder had zero coverage — the driver never navigated to `plan`); raised `EXPECTED_MIN_CHECKS`.
- Verifier executed: full `make ci`.
- Result: ALL GREEN — headless 404 checks/0 FAIL; flutter 95 tests.
- Decision: iterate (run independent verification before completion).

### Iteration 5 — independent adversarial review + fixes

- Target criteria: C-006, C-007 (independent verification, not self-certified)
- Change/investigation: a 6-dimension adversarial review (wiring · a11y · invariant · WKWebView · regression · fidelity), each finding independently verified. 13 confirmed (1 refuted). Fixed 12: link-modal Tab focus-trap (a11y + invariant), dead "Open in Live" button wired nav-only, focus-restore after run-sheet rebuild, role=option/aria-selected, labelled reorder, console deck chips resolve at boot, keep-modal-open-until-resolved + inline `role=alert` error, empty-state CTA, deck select-then-confirm, reworded subtitle. Deferred #2 (remote deck-library resolution) → backend follow-up **86ajy02zq**.
- Verifier executed: `operator_headless.py` (added targeted checks per fix); full `make ci`.
- Result: ALL GREEN — 416 checks/0 FAIL.
- Decision: iterate (re-verify the fixes).

### Iteration 6 — adversarial re-verification of the fixes + closure

- Target criteria: C-006, C-007
- Change/investigation: a 5-lens re-verification of the 12 fixes (did they resolve + introduce no regression). 7 real issues surfaced (5 confirmed + 2 from a connection-dropped verify agent, recovered from the journal): focus lost to `<body>` after a link commit; scripture modal focused Cancel not the input; stale focus intent after a rejected reorder; `planLoadDecks` conflated load-failure with empty (false ⚠ missing); tautological Tab-trap check; `Change…` on a deleted deck enabled a phantom commit; empty-CTA had no coverage. All 7 fixed + covered.
- Verifier executed: `operator_headless.py`; full `make ci`.
- Result: ALL GREEN — **426 checks/0 FAIL**; flutter 95 tests.
- Decision: complete → VERIFIED_COMPLETE; hand off to code review.

## Risks and rollback

- Risks: (1) large plain-JS surgery on a big file — regression risk; mitigate incrementally + headless after each step. (2) test_tokens string needles — add/keep required strings. (3) scope: full builder is large; deliver incrementally + follow-ups for any deferral.
- Rollback: dist edits are additive to the surface; revert per-hunk; git history preserved.

## Pause and escalation conditions

- Escalate design ambiguity to /ui-ux-designer (owns the handoff).
- BLOCKED if the backend API is insufficient for a link flow (create a linked backend follow-up).
- If the full builder cannot land in this pass, deliver a ci-green increment + follow-up tasks and return GATE_REVIEW.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-fe-service-plan-builder.md --require-complete
- Validator result: PASS (all mandatory criteria PASS)
- Independent verification result: PASS — two rounds of adversarial multi-agent review (6-dimension find→verify, then 5-lens re-verify of the fixes). 20 real findings surfaced across both rounds and all frontend-scoped ones fixed; every fix carries a targeted headless regression check. One correctness issue was correctly out of frontend scope (remote deck-library resolution) and deferred to backend follow-up **86ajy02zq** (linked). Not self-certified: C-008 is the objective `make ci` gate.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none (0 FAIL / 0 BLOCKED). One deferred out-of-scope item tracked as 86ajy02zq.
- ClickUp final evidence comment: posted on 86ajxxuz9; task moved to code review.
