# Goal Contract — 17tnw2bbjcd-android-upload-signing

## Identity

- Goal ID: 17tnw2bbjcd-android-upload-signing
- Parent goal ID: NONE
- Title: Ship consistent native SelahCue Controller branding and verify native build metadata
- Role: mobile-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbjcd
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Replace Android debug release signing with explicit upload signing from environment secrets; fail closed for release while retaining debug development.

## Baseline

Verified origin/main 6f03aee7: release uses signingConfigs debug.

## Inputs and evidence sources

- Root-provided approved atomic ClickUp scope and Gradle source.
- Flutter Android release and Android signing official documentation.

## Scope

### In scope

- Android Gradle signing config, executable checks and signing handoff docs.

### Non-goals

- No owner credentials, account provisioning, store upload, identity changes, CI or dependency upgrades.

### Constraints

- Isolated ticket branch; root coordinates four reviewers and merge.

### Assumptions and unknowns

- Approved owner upload key is unavailable. Fixture keys prove wiring only.

## Dependencies and approvals

- User-approved delivery via root; publishing/account provision remains86ajxz3nj.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Missing/malformed signing cannot produce release | actual Gradle bundleRelease negative runs | nonzero, safe diagnostics | signing evidence | PASS |
| C-002 | yes | Debug remains usable without signing secrets | assembleDebug | debug APK builds | signing evidence | PASS |
| C-003 | yes | Explicit fixture upload key signs release AAB | bundleRelease and jarsigner fingerprint | expected fixture certificate, valid signature | signing evidence | PASS |
| C-004 | yes | Secrets remain outside source and logs | executable sentinel and diff checks | no secret values tracked or printed | signing evidence | PASS |
| C-005 | yes | Four independent reviews and current CI pass | root reviewer coordination | no blockers | PR | PENDING |

## Verification plan

- Focused verification: executable actual Gradle missing/partial/invalid/fixture and debug checks.
- Broader regression verification: no Dart changes; existing mobile CI remains required.
- Independent verifier: Cody, Shadow, Quinn and Vera via root.
- Required environment: Flutter, Android SDK, JBR; local disposable fixture only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: dedicated release signing plus a release-task dependency rejects missing credentials without blocking debug configuration.
- Change or investigation: establish actual Gradle negative baseline, then implement minimal config and execute matrix.
- Verifier executed: actual Flutter/Gradle missing, partial, malformed, wrong-password, debug and fixture cases; jarsigner/keytool certificate comparison; diff/syntax checks.
- Result: baseline missing-config test correctly failed because release succeeded; fixed negative cases and debug/fixture builds passed.
- New evidence: fixture signer matches generated key SHA256; no production credentials consumed. See docs/release/mobile/ANDROID-UPLOAD-SIGNING.md.
- Decision: gate-review

## Risks and rollback

- Risks: owner credential/store acceptance unverified; fixture is not approved signing identity.
- Rollback or recovery: revert ticket commit; do not restore debug release signing for distribution.

## Pause and escalation conditions

- External credentials/account or shared CI changes belong to publishing owner.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2bbjcd-android-upload-signing.md
- Validator result: structural check passes; completion withheld pending independent reviews.
- Independent verification result: pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-005 four independent reviews and current CI pending; owner key/account/store provisioning remain external publishing work
- ClickUp final evidence comment: root-owned
