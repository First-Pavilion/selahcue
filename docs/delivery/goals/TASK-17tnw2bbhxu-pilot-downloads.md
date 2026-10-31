# Goal Contract — TASK-17tnw2bbhxu-pilot-downloads

## Identity

- Goal ID: TASK-17tnw2bbhxu-pilot-downloads
- Parent goal ID: NONE
- Title: Registration-first pilot downloads on the marketing site
- Role: frontend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhxu
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Implement the approved P14 frontend unit: visitors reach a distinct pilot journey from shared download CTAs, select Windows/Ubuntu/macOS architecture, see truthful configured release/expiry states and navigate to an explicitly configured n8n-hosted registration form. Never issue a client-authorized download.

## Baseline

Main cbc8949145bd15bb47f08442358e081f27a72599. Existing Vue Download page matches Figma487:124 layout with honest unavailable licensed installer/store controls. No pilot frontend or implemented public grant route. Home has stale on-device transcript wording for this cloud-provider pilot.

## Inputs and evidence sources

- Parent-approved P14 scope/current ClickUp comments; design file SYQn5hFY8YVQKm3c6rw0eJ node487:124 design context and screenshot.
- docs/design/MARKETING-SITE-HANDOFF.md (illustrative claims superseded by approved current scope).
- docs/architecture/api/PILOT-REGISTRATION-v1.md; Kenji coordination.

## Scope

### In scope

- Add a pilot panel within Download, reuse existing PageHero/UiButton/tokens and maintain licensed controls.
- Validate nonsecret deploy configuration, registration-only external navigation and honest unavailable/loading/retry/expired states.
- OS/architecture selection, accessible responsive flow and truthful cloud AI consent/internet/expiry wording.
- Shared Home/nav/footer download CTAs lead to the pilot section.

### Non-goals

- API/n8n implementation, receipt issuance, bucket access, packaging CI, mobile, legal-policy approval and deployment.

### Constraints

- New isolated ticket worktree/branch; no API/CI/mobile writes; root owns ClickUp browser and merge.
- Missing registration/manifest/policy configuration fails closed; no endpoint or signed receipt fabricated.

### Assumptions and unknowns

- Owner confirmed six-month pilot expiry2027-04-30T23:59:59Z. Live P11/P12/P13/P15 configuration, actual artifact manifests, collection notice/data owner/retention remain dependencies; fixture readiness does not imply deployed availability.

## Dependencies and approvals

- User authorized implementation; root owns review coordination and integration.
- Kenji supplies registration handoff; hosted n8n handles personal/church data and server-authorized grant only after persistence.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Only valid unexpired configured OS/architecture entries expose registration navigation; no direct installer href or client success bypass | pilot unit tests | all adversarial and valid cases pass | tests/pilotDownloads.test.ts:15cases; final npm log /private/tmp/farah-p14-tests.log | PASS |
| C-002 | yes | Actual rendered pilot flow supports loading/error/retry/unavailable, keyboard selection and mobile without overflow | dedicated Playwright runtime scenarios/screenshots | expected states and navigation pass | /private/tmp/farah-p14-runtime.log + /private/tmp/farah-p14-shots/ (Chromium and WebKit required) | PASS |
| C-003 | yes | Existing marketing unit/build/lint checks pass and unchanged licensed controls remain honest | npm test, npm run build, npm run lint | exits0 | /private/tmp/farah-p14-tests.log:1246/0; /private/tmp/farah-p14-build.log; /private/tmp/farah-p14-lint.log | PASS |
| C-004 | yes | All four independent scoped reviews pass | Cody/Shadow/Quinn/Vera via root | no unresolved blockers | pending | PENDING |

## Verification plan

- Test-first validation boundary using real config fixtures; meaningful dangerous URLs, timestamps, shape and unavailable variants.
- Actual built Vue page driven in desktop/mobile Chromium and WebKit where available, with fixture config served only in the test harness.
- Unit/build/lint gates. Save screenshots of the requested Download/pilot flow only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-003
- Hypothesis: a separately configured registration-only panel can be shipped safely ahead of live grants by failing closed.
- Change or investigation: inspect existing patterns/designs and coordinate backend handoff; tests first, then config boundary/view and shared CTA wiring.
- Verifier executed: node --test tests/pilotDownloads.test.ts; npm test; npm run build; npm run lint; python3 tests/pilot_downloads_headless.py --shots /private/tmp/farah-p14-shots (from implementation/marketing).
- Result: baseline1230/0; final1246/0 (including15pilot boundary cases), production build/typecheck and lint pass. Required actual Chromium and WebKit fixture journeys pass; screenshots inspected. Logs are under /private/tmp/farah-p14-{tests,build,lint,runtime}.log.
- New evidence: existing licensed buttons remain disabled. Kenji confirmed complete production n8n URL plus non-PII registration_id UUIDv4 and exact platform enum. Session storage preserves same-attempt identity; storage failure/corruption blocks navigation. Explicit new-registration action alone resets an existing identity; UUID is not an authorization receipt.
- Test-first controls: new module/export absence failed before implementation; anchor offset regression failed with top0 before adding Download to the existing anchored-route set; JSONP media type passed incorrectly before the final rejection fix (exactly1intended failing test). Relevant RED logs: /private/tmp/farah-p14-{red,identity-red,anchor-red,media-red}.log.
- Runtime evidence: actual built Vue served locally; deterministic pending load, unavailable target, all3OS/architecture selections, keyboard focus/Enter navigation to intercepted form, stable ID across reload/return, deliberate reset,503retry, unapproved policy, expired package/live clock expiry and unavailable session storage. Widths320/375/768/1440 have no horizontal overflow. HomeCTA reaches pilot with heading below sticky navigation. Both required engines passed; no live form/Sheets/provider/download exercised.
- Screenshot inspection found the new hash route needed the established sticky-header offset; corrected through router/scroll.ts and regression-tested. Native select styling was normalized with existing tokens. Existing static assets/components are reused, with no new Figma-derived raster/SVG substitution.
- Scoped copy ledgers now reflect approved pilot cloud consent/internet/expiry copy and Ubuntu; legacy standard Download bans still cover standard content. The independently tested pilot panel has a distinct copy/behavior scope rather than treating old cloud/architecture bans as current pilot requirements.
- Live-service limitation: committed public config is schema_version1/enabledfalse. No actual form/notice/artifact/grant URL is fabricated. README specifies schema, deploy prerequisites, trust boundaries and separate platformQA. Root independently reported n8n2.45.7 production hidden-field fixture proof; this is not full end-to-end registration/grant proof.
- Integration: rebased the unpublished ticket branch onto origin/main add4702e3474fb9c6c793beccbd2d38b59993db0 without conflicts. Upstream changed only an unrelated Operator test and goal document; the tested marketing source/build inputs remain unchanged.
- Decision: hand off the completed frontend unit for four independent reviews; live collection/release enablement remains dependency-gated.

## Risks and rollback

- Risks: client state cannot authorize artifact access; trusted n8n/P12 must enforce persistence and grants. No personal data or receipt is stored here.
- Rollback or recovery: revert P14 branch increment or leave public config disabled.

## Pause and escalation conditions

- Live contract/policy gaps are reported; no fake deploy configuration or launch claim.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhxu-pilot-downloads.md
- Validator result: structural validation passed; completion validation withheld pending C-004.
- Independent verification result: pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-004 independent reviews; live-service/artifact/policy integration remains external readiness work and is not claimed complete.
- ClickUp final evidence comment: root to post
