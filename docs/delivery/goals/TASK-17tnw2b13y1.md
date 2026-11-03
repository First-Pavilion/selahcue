# Goal Contract — TASK-17tnw2b13y1

## Identity

- Goal ID: TASK-17tnw2b13y1
- Parent goal ID: NONE
- Title: Preserve typed mobile scripture ranges through browsing and staging
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b13y1
- Created: 2026-11-03
- Updated: 2026-11-03
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Typing Psalms 119:2-10 retains the range and stages verse 2, through the existing host command. Existing verse-row selection remains available.

## Baseline

Verified source base 9801fc587adba59a30ddee066efb5d0da26fc425. Current successful chapter browsing overwrites the field with Book Chapter; chapter-success UI exposes individual verse gestures while Stage/Live buttons exist only on fetch failure. No ticket comments, parent or dependencies. Runtime widget reproduction confirmed the field became Psalms 119 instead of Psalms 119:2-10.

## Inputs and evidence sources

- ClickUp ticket; scripture_tab.dart; LiveController and LAN protocol; Rust controller and current desktop browser.

## Scope

### In scope

- Mobile scripture tab and focused interaction regression tests; this goal evidence.

### Non-goals

- Host/protocol changes, service-plan navigation, release/store packaging, account/network access.

### Constraints

- One isolated main-based branch/PR. Preserve user lockfile; no dependency changes.
- Keep capability and busy/syncing checks and accessibility labels.

### Assumptions and unknowns

- UNKNOWN: physical-device runtime; widget tests do not claim physical-device evidence.
- No new device services, permissions, storage, background work or analytics; those platform gates are inapplicable because this change only manages existing widget reference state and commands.

## Dependencies and approvals

- User authorized ticket implementation and public branch/PR; root owns merge and QA transitions.
- Root coordinates independent Cody, Vera, Shadow and Quinn reviews.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C1 | yes | Typed range retains identity and the explicit Stage action sends it intact so the host stages its first verse | Focused widget interaction tests and host contract inspection | Range retained; exact stage_scripture reference; host stages verse 2 | Iteration ledger and scripture_range_test.dart | PASS |
| C2 | yes | Chapter, single verse, failure, stale response and role behavior remain safe | Scoped widget suites | All tests pass | Iteration ledger | PASS |
| C3 | yes | Changed files format and analyze cleanly without lockfile changes | Dart format, Flutter analyze and git diff | Checks pass; only scoped files | Iteration ledger | PASS |
| C4 | yes | Current source receives all four independent reviews | Root review round | Cody/Vera/Shadow/Quinn pass and current CI | Root review report/PR | PENDING |

## Verification plan

- Focused verification: scripture_range_test.dart through actual widget and LiveController with fake ControllerSession RPC boundary.
- Broader regression verification: existing scripture tab/role/approval suites.
- Independent verifier: Cody, Vera, Shadow, Quinn through root.
- Required environment: local Flutter test runner; physical mobile checks unavailable unless separately evidenced.

## Iteration ledger

### Iteration 1

- Target criterion: C1
- Hypothesis: chapter normalization discards requested verse identity; retain loaded reference separately and expose safe reference staging.
- Change or investigation: inspected current host StageScripture, which narrows ranges to first verse; Next/Previous navigate plan items.
- Verifier executed: source inspection; widget reproduction pending.
- Result: host contract identified; no host mutation needed.
- New evidence: controller.rs StageScripture; test_controller.rs staging_a_range_shows_only_its_first_verse.
- Decision: iterate

## Risks and rollback

- Risks: async chapter response must not overwrite newer text or stage stale content.
- Rollback or recovery: revert ticket commit.

## Pause and escalation conditions

- Host/protocol scope change or acceptance ambiguity is routed to root.

### Iteration 2

- Target criterion: C1 and C2
- Hypothesis: retaining successful request identity independently of ChapterResult fixes staging without changing the wire contract; generation/revision guards prevent stale overwrite.
- Change or investigation: added explicit loaded-reference Stage action; preserved identity through translation reload and failed lookup, with chapter paging selecting its new chapter. Existing individual verse gestures unchanged.
- Verifier executed: Flutter widget suite at real ScriptureTab/LiveController with ControllerSession RPC fake; unchanged Rust host test `staging_a_range_shows_only_its_first_verse` with offline ticket-owned CARGO_TARGET_DIR.
- Result: RED expected `Psalms 119:2-10`, actual `Psalms 119`. First GREEN assertions passed but test-owned poll timer/semantics disposal needed correction; no production change for those harness failures. Rust: 1 passed, 149 filtered, no failures.
- New evidence: `/private/tmp/scripture-range-red.log`, `/private/tmp/scripture-range-host.log`; focused test file.
- Decision: iterate

### Navigation scope clarification

Verified host `StageScripture` narrows a range to its first verse and stores the single-verse readback. Host `Next`/`Previous` navigate plan items; they are not scripture stepping. Current desktop `dist/app.js` keeps the full chapter cursor and uses per-verse `follow_scripture` for Up/Down; it does not retain a range-scoped host cursor. Current mobile has individual verse gestures and no scripture Up/Down controls. The coordinating owner confirmed the ticket correction is range identity plus explicit staging, with no new host cursor or mobile navigation controls. No assertion of range-scoped navigation is made.

### Iteration 3

- Target criterion: C2 and C3
- Hypothesis: the loaded-reference action obeys existing busy/syncing guards and the selection survives reconnection.
- Change or investigation: added range-specific busy/Assistant and reconnect tests, newer edit/out-of-order reply tests, fallback and disposal coverage; corrected test-app polling-controller ownership and semantics handle cleanup.
- Verifier executed: `flutter test --no-pub test/views/scripture_range_test.dart test/views/scripture_tab_test.dart test/views/scripture_tab_role_test.dart test/views/scripture_approval_test.dart`; `dart format --output=none --set-exit-if-changed lib/views/tabs/scripture_tab.dart test/views/scripture_range_test.dart`; `flutter analyze --no-pub lib/views/tabs/scripture_tab.dart test/views/scripture_range_test.dart`; `git diff --check`.
- Result: 24 widget tests passed (12 focused range tests and 12 existing scripture/role/approval tests). Format has 0 changed files. Final analyzer: No issues found (25.5s); all tracked dependency lockfiles unchanged. No physical-device, store build or end-to-end LAN session claim.
- New evidence: `/private/tmp/scripture-range-green.log`, `/private/tmp/scripture-range-analyze.log`; committed regression suite. Fetched origin/main remains 9801fc587adba59a30ddee066efb5d0da26fc425; branch is 0 commits behind.
- Decision: handoff

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b13y1.md
- Validator result: structural validator PASS; completion remains gated by C4 independent reviews.
- Independent verification result: pending
- Terminal state: GATE_REVIEW — implementation ready for root-coordinated independent reviews, not VERIFIED_COMPLETE.
- Remaining failed or blocked criteria: C4 pending independent review and CI.
- ClickUp final evidence comment: pending
