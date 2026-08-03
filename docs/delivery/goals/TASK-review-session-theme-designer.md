# Goal Contract — TASK-review-session-theme-designer

## Identity

- Goal ID: TASK-review-session-theme-designer
- Parent goal ID: TASK-design2-theme-designer
- Title: Independent code review of this session's Theme Designer 2.0 + streamline changes
- Role: code-reviewer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: PENDING (relates to impl story 86ajuptvy; ClickUp rate-limited this session)
- Created: 2026-08-03
- Updated: 2026-08-03
- Maximum iterations: 6
- Independent verification required: yes (adversarial multi-lens review workflow + reproduce)

## Objective

Independently review the CUMULATIVE code changes authored this session, catching real defects a
prior incremental review may have missed across the whole delta, and confirming the model
visibility slice coexists correctly with the concurrent (owner) `LayerMask` edits in compose.rs.

## Baseline

Verified before review: node --check OK; token 14/14; headless 180/0; `test_present` 21/21;
`test_compose`/`test_controller` pass. `make ci` currently blocked by out-of-scope concurrent WIP
(the `LayerMask`/screen-config feature spanning present.rs/compose.rs/lan/data). Three prior
adversarial reviews this session (Theme Designer 2.0, inspector, streamline) found 14 issues, all
fixed — this pass is the consolidated independent review of the cumulative delta.

## Scope

**In scope (this session's deliverables):**
- Model: `theme.rs` (additive `Element.visible` + accessor + serde helpers); `compose.rs` (the
  visibility gate `theme.elements.iter().filter(|e| e.visible())` + the `visible: _` match arms).
- Tests: `test_compose.rs` (visibility tests + `visible:true` sites), `test_controller.rs`
  (`visible:true`), `test_tokens.rs` (pin add/remove), `operator_headless.py` (D2 checks),
  `test_present.rs` (incidental `LayerMask::ALL` migration).
- Webview (`dist/`): `index.html` `#surface-theme-designer`, `app.css` Design-2.0 block,
  `app.js` (LAYERS panel + DnD, per-layer visibility, zoom, `tdFitCanvas`, collapsible templates,
  segmented Background, SIZE/LINE number fields, region canvas click-select, Region-picker +
  numeric-LAYOUT removal, Save-theme-expands-collapsed fix).

**Out of scope (concurrent owner WIP — do NOT review as this session's work):** the `LayerMask` /
per-screen layer-visibility feature itself (present.rs `compose_screen_live` mask param,
`compose_slide_masked`, selahcue-lan / selahcue-data changes) — flag ONLY where it breaks/interacts
with the in-scope visibility slice.

**Verified baseline:** node --check OK; token 14/14; headless 180/0; `test_present` 21/21;
`test_compose`/`test_controller` pass. `make ci` currently blocked by the out-of-scope concurrent WIP.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Full in-scope delta reviewed across correctness/maintainability/perf/tests/a11y | review workflow | all in-scope files examined | PENDING | PENDING |
| C-002 | yes | Findings are evidence-backed, deduped, severity-ranked, adversarially verified | verify pass | confirmed set (or empty) | PENDING | PENDING |
| C-003 | yes | Every confirmed Blocker/High is resolved or explicitly owned; fixes re-reviewed | fix + re-verify | none unresolved | PENDING | PENDING |
| C-004 | yes | In-scope suites stay green after any fixes | headless + token + cargo | green | PENDING | PENDING |
| C-005 | yes | Verdict states reviewed vs unreviewed scope + QA readiness | this doc + handoff | stated | PENDING | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- 3-lens adversarial review workflow (correctness/integration · a11y-ux · QA/test-quality) over
  the in-scope delta; refute each finding; fix confirmed Blocker/High; re-run headless + token +
  the affected cargo suites.

## Iteration ledger

(Appended per iteration.)

## Risks and rollback

- Risk: reviewing concurrent WIP as this session's work → scoped out explicitly above.
  Rollback: findings are advisory; fixes are small + test-gated.

## Final evaluation

- Validator: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-review-session-theme-designer.md`
- Terminal state: PENDING
- ClickUp final evidence: PENDING (rate-limited).
