# Goal Contract — 17tnw2ay5jm

## Identity

- Goal ID: TASK-17tnw2ay5jm
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Arm emergency actions while busy and show Scripture reconnect gating
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2ay5jm
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Blackout/Clear may arm locally while another command is busy, while confirmation/send remains busy-gated and syncing blocks both. Scripture verse rows, fallback actions and caption visibly reflect syncing, recover when current state arrives and retain existing permissions/busy protection.

## Baseline

Actual main e730b475de71a6f27751fdedaee659851159d020 after verified UHZ merge. EmergencyStrip._guarded returns null for syncing ORbusy before distinguishing arm/send; arm itself only changes local state/timer. ScriptureTab currently threads busy only into row/fallback actions and caption. SelahListRow does not automatically dim when callbacks are null, so visible disabled treatment requires scoped row presentation, not just relying on controller refusal. Existing tests cover confirm/timer pause/absolute intent, busy fallback/rows and staged/live semantics. Full frozen task has three criteria, zero comments/dependencies/links; live UI refresh unavailable while Mac locked/connector capped. Root authorizes unchanged frozen scope, start/status explicitly pending and no new scope inferred.

## Inputs and evidence sources

- Full mobile-qualification/17tnw2ay5jm.json, original qualifications.md, frozen selected20 and AGENT-RUNBOOK.md.
- Current mobile_widgets.dart EmergencyStrip, ScriptureTab and existing emergency_confirm_test.dart/scripture_tab_test.dart.
- Existing Plan/Timer disabled/reason/caption patterns and shared SelahButton0.4disabled opacity; controller auth/busy/syncing guards unchanged.
- Canonical runtime/mobile-engineer/Goal workflow and current repository guidance (no AGENTS files found).

## Scope

### In scope

- EmergencyStrip arm/send busy distinction and minimal existing timer lifecycle adjustment only if needed.
- Scripture syncing+busy disabled/reason presentation for rows/fallback/caption, reusing existing disabled opacity/reason/hint vocabulary.
- Focused real widget regressions and this Goal; meaningful hosted mutations/restoration evidence.

### Non-goals

- Un-blackout preemption while busy, atomic gestures, new emergency semantics or any protocol/auth/revocation/deadline/reconnect/timer policy.
- Scripture range selection/default translation/backend policy, shared primitive redesign, unrelated UI, Figma parity or physical device/native/radio/battery acceptance.

### Constraints

- Own managed checkout/branch; native creation returned actual path with100attachment registration error, use that checkout without duplication. Not alone, never revert/stage others.
- No local project runtime/import/build/test/install/pub/simulator/container/benchmark; tiny Git/source/stdlib/static checks only. Hosted real widget behavioral RED before production edits.
- Local arm sends nothing; busy send remains disabled, syncing blocks both arm/send, current armed absolute intent and leftover paused confirm window remain unchanged. Recovery stays one tap when not busy/syncing; no policy to preempt in-flight command.
- Scripture browsing/reading remains available; only audience-affecting row/fallback stage/live actions gate on busy/syncing. Preserve role gating and live/staged glyphs. Reuse existing0.4disabled opacity for visible rows/caption; no new visual system.
- Ordinary push/one draft/body-file/attempt attachment allowed; retain actual100cap response and parent association boundary. Separate exact-parent workflow-only hosted diagnostics, locked/no-pub dependency/source identity and restoration; no forcepush/protected edits/merge/ClickUp/status/review publication/subagents/next13XZ.

### Assumptions and unknowns

- Current task comments/dependencies are verified from frozen qualification, not newly read live. Root owns pending start/status and final fresh tracker handoff on unlock.
- Widget/source inspection does not prove runtime behavior; actual RED/GREEN/mutant/normal receipts pending. No UHZ completed export until root QA receipt.

## Dependencies and approvals

- Root selected/assigned this existing task after verified UHZ merge; no owner decision in captured scope. Root owns allfour reviews/consolidation/mergeQA.
- Preserve other implementers' work and UHZ/F1Y source behavior; no new unit before root dispatch.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Busy Blackout/Clear first tap arms locally and confirmation cannot send until busy clears | Real LiveController gated command plus widget taps/semantics/command maps | Both arm immediately with zero emergency sends; confirming tap while busy no-op; armed intent remains and confirms once after recovery | Hosted focused widget RED/GREEN/raw | PENDING |
| C-002 | yes | Syncing blocks emergency arm/send without changing recovery or timer safety | Real stale-session/replacement-read gates, existing confirm/remaining-window/role controls | No arm/send on syncing; one-tap unblackout only when ready; paused leftover window/absolute command preserved | Focused/full widget suite | PENDING |
| C-003 | yes | Scripture visually reflects syncing and returns to usable state after synchronization | Loaded chapter/replacement read gate, rendered opacity/caption/semantics/callbacks, fallback controls | Rows/caption dim and explain syncing; no stage/live; existing busy gates/permissions unchanged; current-state recovery re-enables actual action | Hosted widget raw assertions | PENDING |
| C-004 | yes | New tests detect each behavior and meaningful guard/style regressions | Actual unchanged-production hosted RED plus scoped arm/send/syncing/style/caption mutations with siblings | Intended failures before fix, each mutant fails named assertions; positive controls and exact restored source pass | Immutable RED/mutant/restore hashes/runs | PENDING |
| C-005 | yes | Normal full affected Flutter/analyze and scope pass | Hosted exact candidate normal analyze/fulltest; full target diffcheck/prefix/components | Analysis/all tests pass, only scoped two views/two test files/Goal, no workflow/dependency change; skips explicit | Normal run/head/tree/raw/source manifest | PENDING |
| C-006 | yes | Independent review and authorized delivery close | Root four final reports, actual merge/tree and exactQA readback | Cody/Quinn/Vera/Shadow Pass; merge andQA verified | Root receipts/completed export | PENDING |

## Verification plan

- Tests first use real LiveController/ChangeNotifier rebuilds, injected transport command/read gates, actual widget taps, semantics and captured command maps; no new product seam unless actual evidence requires it.
- New behaviorRED for both busy local arm directions and scripture syncing callbacks/opacity/caption/fallback. Existing busy/syncing/remaining-window/one-tap/role controls remain or updated only where this task deliberately changes arm semantics.
- Meaningful mutations independently restore old busy-arm guard, permit busy send, remove syncing gate/visual/caption treatment; full selected sibling tests retain positive controls. Exact candidate Git/source/dependency identities before/after, no product diagnostic workflow.
- Hosted normal full Flutter analysis/tests required; Android/platform skips remain unexecuted. Root allfour current-source review and delivery mandatory.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-005
- Hypothesis: actual widget gates and visible presentation assertions reproduce the two existing UX defects without changing product source.
- Change or investigation: read full frozen task/comments/criteria and current view/test patterns; fetch actualmaine730 and create own managed checkout (100registrationcap explicitly retained). Prepare bounded Goal before any test/source edits. Tracker start pending root, no false receipt.
- Verifier executed: structural Goal validation, source inspection only; hosted behavior and normal gates pending.
- Result: preparation only; all completion criteria pending.
- New evidence: null row callbacks do not themselves dim SelahListRow; test must observe actual disabled presentation as well as the controller backstop.
- Decision: add tests-only widget regressions/positive controls, freeze one draft and obtain actual behavioral RED before minimal view change. No local project runtime.

## Risks and rollback

- Risks: arm accidentally sends while busy, confirmed intent flips after poll, pausing grants fresh window, syncing looks usable, or visual gating prevents safe browsing/permissions.
- Rollback or recovery: revert only this unit's two views/tests/Goal; no protocol or persistence change.

## Pause and escalation conditions

- Compiler/setup/test oracle errors are not expectedRED; inspect actual runtime before product edits.
- No silent iteration extension beyond8, next ticket, tracker/merge action or unexecuted platform acceptance claim. Yield immutable hosted waits.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2ay5jm-emergency-scripture-sync.md
- Validator result: structural PASS before and after tests-only regressions; hosted behavioral RED pending
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-006
- ClickUp final evidence comment: root owns publication; initial start/status pending unlock
