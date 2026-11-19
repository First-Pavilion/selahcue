# Auth Handoff Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Complete existing ticket86ak120kw by aligning onboarding handoff contracts with current auth behavior.
**Architecture:** Documentation-only corrections backed by the existing accounts services, marketing views, policy helper, token settings and DEC-017. No runtime component changes.
**Tech Stack:** Markdown; read-only Git and standard-library validation.
**Spec:** docs/superpowers/specs/2026-11-19-auth-handoff-contract.md.

## Global Constraints

Basea53d2ca5b97d72d4f353a9a9748f1e3ccc1eaf54; branchcodex/86ak120kw-auth-handoff-contract-20261119. One existing ticket/PR, one implementation writer. Preserve all other worktrees and historical outputs. No CI or application/native/browser execution; no installs, secrets, external staff messages, runtime policy changes or unrequested broad cleanup. Source-backed sign-in nonempty rule prevails over the stale ticket minimum. New/reset default10–200 length-only, reset1hour, verification24hours.

## Review Focus

- Existing/new signup and known/unknown reset requests must share accepted wording without implying account creation or delivery.
- Rate-limit/validation/server failures must remain failures, not be labeled accepted or sent.
- Existing short credentials may still be submitted at sign-in; creation rules and an optional strength meter cannot block them.
- Valid-token password errors remain correctable and do not consume the link; dead-token causes remain indistinguishable.
- Historical rejected examples, verification TTL and unrelated numeric values must not be changed by a broad textual replacement.

## Task1: Correct and verify the complete documentation ticket

**Files:** modify `docs/design/MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §§3–5, the directly related signup, verification-resend and reset-password guidance in `docs/design/AUTH-LANDING-PAGES-HANDOFF.md`, the signup and reset-request Notes cells in `docs/design/ACCOUNT-AUTH-API-HANDOFF.md`, and the two landing-page state cells and adjacent handoff text in `docs/design/TRANSACTIONAL-EMAIL-spec.md`. Include this plan and its spec. Report further live contradictions before expanding file ownership. No executable changes.

**Interfaces:** consumes the existing `register_customer_user`, `request_password_reset`, `login`, `_validate_password`, `_consume_reset_token`, marketing auth views/passwordPolicy and shipped account email templates. Produces consistent implementation guidance for those unchanged interfaces.

- [ ] Read the spec, current ticket/comments and `onboarding-code-map.md` in shared backlog-20261119 evidence. As backend engineer, independently inspect the relevant source and existing test assertions; don't assume the old ticket or companion handoff is authoritative over current code.
- [ ] Record the four original contradictions plus companion reset error-order discrepancy. Run and retain a bounded search over `docs/design/` and shipped email templates for eight-character/composition rules, email-existence responses and15-minute reset copy. Classify matches rather than mechanically replacing unrelated or historical content.
- [ ] Correct primary §§3c,4b/4c/4d,5b/5c and narrow precedence/context text as needed. Use one conditional accepted state, sign-in nonempty,10–200 length-only creation/reset policy and1-hour reset lifetime.
- [ ] Reconcile companion acceptance, reset critical note and superseded-corrections list. Use conditional A13 and V5 copy, document the shipped resend mutation in §10.3 and mark the original gap inventory as historical. Correct the two API Notes cells. Preserve the collapsed token-failure contract and explicitly handle `PASSWORD_INVALID` behind a live token. Keep device and transport guidance outside this correction.
- [ ] Align the transactional-email landing-page guidance with V3 and R4. Keep V4 and R5 deferred and preserve the issued-link lifetimes.
- [ ] Repeat the scoped search, map every remaining relevant match to its disposition, verify cited files/anchors and changed-path scope, then run `git diff --check`. No new application tests: source/test inspection and content validation are the evidence for this documentation-only change.
- [ ] Self-review and commit only owned docs plus plan/spec. Report source anchors, exact validation commands/output, all changed files and limitations in the SDD workspace. No push or external tracker mutations by the worker.

## Review and merge

Code/spec and security task review, remediation and scoped re-review for requested changes, then most-capable whole-branch final review. Performance and runtime QA are not routed for documentation-only edits; assess source accuracy and all acceptance criteria instead. Verify exact live target, final source and merge tree before moving the full ticket to configured QA with readback. User authorization covers merge after passed reviews, with CI excluded.
