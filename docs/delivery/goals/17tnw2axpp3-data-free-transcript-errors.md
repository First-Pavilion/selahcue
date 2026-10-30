# Goal Contract — TASK-17tnw2axpp3

## Identity

- Goal ID: TASK-17tnw2axpp3
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Transcripts failure alerts are meaningful and data-free
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2axpp3
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Real generation/edit/regeneration failures and refusals show meaningful operation feedback without echoing transcript, partial-transcript or detection payloads through DOM, announcements or diagnostics, while preserving accepted data and existing successful-edit/reopen/retry/pending/focus behavior.

## Baseline

Fresh actual main dd5cc038efe04681e42746edb8d243996badc947. Original Rust reply-mismatch root was already fixed through operator_reply::expect_* and variant-only diagnostics; do not redo or count it as new work. Explicit latest S4 scope adds Transcripts UI generation/edit failures: transcripts.js1644/1725/1751/1905 echo raw rejected IPC text; structured regeneration refusals1718/1744 also consume raw messages. Existing showGenError/showGenErrorInner holds the operation/error-code presentation boundary. Current full driver measured2464, no local runtime executed.

## Inputs and evidence sources

- Complete original task/latest S4 and two comments in wave3-20261030/frontend-qualification/17tnw2axpp3-live.json; no dependencies; linked completed redaction boundary evidence and current source inspected.
- Frozen parent selected20.json/md, source-evidence.json, qualifiers and root explicit author ownership.
- Repository root/desktop guidance, frontend skill, Goal operating contract and test-first methodology.

## Scope

### In scope

- transcripts.js and necessary reuse/export of existing shared safe-code/literal error boundary, only after declaring new module footprint to root.
- Focused real IPC browser tests in serialized operator_headless DRIVER, Goal and exact measured count update after actual execution.
- Meaningful negative/positive/mutation/restoration proof, normal applicable CI and four independent reviews.

### Non-goals

- Already-fixed Rust operator_reply, Mika LAN/JSON code, Kenji backend/cloud/serializer error policies, request correlation, new policy enums or ad-hoc text scrubbers.
- Accepted draft/regeneration protocol changes, wider UI redesign or unrelated native incident remediation. Preexisting failed-save form clearing belongs to excluded bawx7; latest S4 privacy scope does not require new failed-input retention. Root clarified before any tests/production edits that preservation means no regression, not implementing that separate R6/native-gated unit.

### Constraints

- One new managed isolated worktree/feature branch/PR; not alone, never stage/revert others. Shared DRIVER fully serialized by root.
- No local project runtime/import/install/build/browserbench/containers under resource pressure; only source/Git/stdlib preparation/structural checks locally; actual runtime hosted.
- Actual unchanged-production behavioral RED before production correction, meaningful controls on real failure paths, all sibling assertions retained and no retry wrappers/ignored failures/guessed counts.
- Own bounded workflow-only hosted diagnostics/ordinary push/draft/body-file/immediate attach authorized. Root owns ClickUp, four reviews, merge and QA; no subagents/force push/protected edits.

### Assumptions and unknowns

- VERIFIED: newest ticket explicitly authorizes UI alert-boundary residual; original Rust formatting fixed, selected as one genuine existing unit.
- UNKNOWN: exact existing safe-message abstraction footprint and runtime RED/positive/final CI until inspected/executed. Any needed different-module helper footprint must be declared first.

## Dependencies and approvals

- Parent WAVE3-SELAHCUE-20 C-001 frozen selected20 approved, only this unit started. Root records In Progress/start after validated canonical Goal.
- No tracker blocker; source prerequisite boundary exists. No API, provider or owner policy decision to invent.

## Completion predicate

All mandatory rows must PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Failed generation/update/confirm/discard and structured refusals never echo hostile content in visible feedback, announcements or diagnostics | Real rejected/refused IPC browser paths with transcript/partial/detection sentinels | Data-free meaningful operation message and no secret in observed output | Hosted actual RED/GREEN raw logs | PENDING |
| C-002 | yes | Existing edit/reopen/retry, accepted data, pending and focus/selection behavior does not regress | Full real UI positive and negative lifecycle controls | Accepted data unchanged on failure, existing success/reopen/retry works, pending controls remain safe; no new retention feature claimed | Hosted browser assertions | PENDING |
| C-003 | yes | Existing safe boundary reused and controls catch raw-rendering regression | Isolated real raw-error mutants/full restoration and sibling suite | Named privacy assertions fail on raw echo; restored identical source/dist passes | Exact current parent/blob/manifest and raw receipt | PENDING |
| C-004 | yes | Normal applicable CI passes at exact measured count | Full normal affected operator/Rust/native/WebKit jobs | Every applicable configured gate succeeds; skipped/unexecuted domains disclosed | Official run metadata/raw | PENDING |
| C-005 | yes | All four independent final-source reviews pass | Root-owned Cody/Quinn/Vera/Shadow | No unresolved blocking finding after valid author remediation | Consolidated source-fresh review | PENDING |

## Verification plan

- Focused verification: real Tauri-stub rejected IPC and structured refusal through shipping UI, distinguish test transport fixtures from copied error oracle; inspect all relevant DOM/live/error channels.
- Broader regression verification: complete operator headless siblings, sensitive raw-rendering mutations/restored16-file manifest, normal affected-area CI.
- Independent verifier: root coordinates four separate reviewers and exact merge/QA evidence.
- Required environment: hosted Chrome and normal pinned Linux toolchains/WebKit. No real OS/native acceptance inferred from browser gates.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-002.
- Hypothesis: hostile rejected IPC strings/structured refusal messages reach current Transcripts alerts; same actual UI paths can expose this while preserving operation semantics in controls.
- Change or investigation: inspect existing shared safe-message pattern, prepare tests-only meaningful hostile-payload controls in fresh isolated main, production unchanged.
- Verifier executed: Goal structural/stdlib preparation checks; hosted actual RED follows frozen tests-only checkpoint.
- Result: Pending actual execution; no production correction before observed behavioral RED.
- New evidence: own wave3/transcript-errors receipts/raw/source proof to be saved at checkpoints.
- Decision: iterate

## Risks and rollback

- Risks: dropping useful operation feedback while removing raw text, accidentally clearing edit input, trusting arbitrary structured messages, copied safety oracle or incomplete failure-path coverage. Real positive/negative/mutation controls address these boundaries.
- Rollback or recovery: revert this one scoped PR; no data/schema or protocol mutation.

## Pause and escalation conditions

- Stop before production until actual behavioral RED; declare different-module footprint before edits; escalate new policy or unrelated Rust/API/native scope.
- Respect max8 iterations and three materially different failed attempts without useful evidence; no hidden limit extension or assertion weakening.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2axpp3-data-free-transcript-errors.md
- Validator result: Initial structural validation PASS. Root's privacy-only scope clarification recorded before tests; separate preexisting bawx7 retention bug excluded. Tests use unchanged existing IPC seam; production/STUB/CSS_SRC unchanged in tests-only checkpoint.
- Independent verification result: Pending four root-owned roles.
- Terminal state: ACTIVE, tests-first preparation.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns status/evidence and verified QA readback.
