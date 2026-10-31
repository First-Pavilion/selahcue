# Goal Contract — 17tnw2bbhyu-mobile-app-identity

## Identity

- Goal ID: 17tnw2bbhyu-mobile-app-identity
- Parent goal ID: NONE
- Title: Ship consistent native SelahCue Controller branding and verify native build metadata
- Role: mobile-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhyu
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Align native user-visible app identity with existing Dart/store-listing branding and verify it in actual native build products where tools permit. This is a scoped continuation of M01, not a claim of full store readiness.

## Baseline

Verified on origin/main add4702e: Android launcher label is selahcue_controller; iOS display name is Selahcue Controller and short bundle name is selahcue_controller; Dart and store-listing app name are SelahCue Controller. Existing iOS privacy-manifest resource fix from PR316 remains present. Android release signing still uses debug configuration, a separate release blocker.

## Inputs and evidence sources

- Live M01 snapshot supplied by root; original cleanup86ajxxu0r complete and publishing86ajxz3nj separate.
- Native manifests, Gradle project, Dart MaterialApp title and docs/release/mobile/STORE-LISTING.md.
- Current official Google Play target SDK and Apple submission/CFBundleName references; URLs recorded in release evidence.

## Scope

### In scope

- Native launcher/display names and a suitable short iOS bundle name.
- Native source metadata verification, current SDK evidence, unsigned/native build smoke and release-checklist handoff.

### Non-goals

- No application/bundle-ID migration, release-version allocation, signing provisioning, new features, legal approval or store upload.
- Do not change approved icons/splash/responsive behavior or privacy declarations.

### Constraints

- New isolated codex/17tnw2bbhyu-mobile-app-identity branch; root owns ClickUp and merges.
- Serialize Flutter runs; do not alter shared backend/marketing/CI files.
- Missing signing/device evidence remains explicit; no debug-signed artifact is store-ready.

### Assumptions and unknowns

- Existing store listing's SelahCue Controller is the approved display name.
- Final signed archive, store identifiers/account ownership and physical device matrix require publishing owner evidence.

## Dependencies and approvals

- User-approved continuation through root. First privacy-manifest increment already merged.
- Store accounts/signing/legal/submission remain in86ajxz3nj; material independent blockers receive separate work.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Source native labels match approved branding without ID/version changes | parse Android XML and iOS plist; inspect diff | Android/iOS display SelahCue Controller, short bundle SelahCue | iteration ledger | PASS |
| C-002 | yes | Native products carry correct app identity and permissions | Android release manifest task and iOS unsigned release build; inspect products | metadata correct; unsigned/debug limitations explicitly recorded | release evidence | PASS |
| C-003 | yes | App regression gate passes | make mobile-test | analysis clean and mobile tests pass | release evidence | PASS |
| C-004 | yes | Policy/toolchain and remaining release gaps documented | compare primary sources, installed SDKs and artifact metadata | dated accurate evidence and blockers, no store-ready claim | release checklist | PASS |
| C-005 | yes | Independent review passes current revision | Cody/Shadow/Quinn/Vera via root | no blocking findings | PR review | PENDING |

## Verification plan

- Focused verification: source native identity before/after; plist/XML syntax; actual build metadata when available.
- Broader regression verification: serialized make mobile-test plus affected native build smoke.
- Independent verifier: root coordinates all four reviewers.
- Required environment: Flutter/Dart, Android SDK/JBR/Gradle and Xcode; no signing secrets required for unsigned smoke.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: replacing Flutter-template labels with existing approved branding fixes the actual native app identity while retaining package IDs and versions.
- Change or investigation: source/SDK inspection confirms mismatched native labels and available Xcode 26.6/iOS 26.5/AndroidAPI 36 tools.
- Verifier executed: source native metadata red/green comparison; make mobile-test; Android debug APK + aapt2 metadata; actual release merged-manifest task/parser; unsigned iOS release build + compiled plist/manifest parser; existing iOS graph verifier; plist lint; diff check.
- Result: original source comparison failed, corrected native names passed; analysis clean and 499 tests pass; Android debug APK/release manifest and unsigned iOS release app compile/metadata checks passed. Detailed evidence in docs/release/mobile/2026-10-31-app-identity-evidence.md.
- New evidence: Google Play requires API 36+ for new phone/tablet submissions; Apple requires Xcode 26+/iOS 26 SDK+; local Flutter default compile/target SDK is36.
- Decision: gate-review

## Risks and rollback

- Risks: native metadata/build smoke does not prove signing, store approval or physical-device behavior.
- Rollback or recovery: revert scoped branding commit; IDs/storage/permissions unaffected.

## Pause and escalation conditions

- Split signing provisioning or substantive newly discovered defects; do not expand this branding increment silently.
- Report exact environmental build blockers after bounded diagnostics.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2bbhyu-mobile-app-identity.md
- Validator result: structural validator passes; completion validator withheld while independent reviews remain pending.
- Independent verification result: pending
- Terminal state: GATE_REVIEW for scoped branding continuation only; broader M01 remains In Progress.
- Remaining failed or blocked criteria: C-005 independent reviews pending. Full M01 still requires production signing/AAB/archive, native 16 KB/runtime/device/privacy/store gates; debug/unsigned compile outputs are not deployment-ready.
- ClickUp final evidence comment: root-owned
