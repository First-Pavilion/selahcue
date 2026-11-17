# Public Free Deployment Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the manual deployment instructions for the approved public self-service Free release.

**Architecture:** Document the existing Compose, account and publication paths against an immutable reviewed source. Clearly retain missing cloud wiring and qualification as outstanding work; do not change executable configuration.

**Tech Stack:** Markdown, Compose reference, Django/Celery deployment and installer publisher contracts.

**Spec:** `docs/superpowers/specs/2026-11-17-public-free-deployment-guide.md`

## Global Constraints

- Full self-service Free; paid subscriptions later. API `api.selahcueapp.com`, website `selahcueapp.com`, installer Space `https://selahcue-installers.sfo3.digitaloceanspaces.com`.
- Manual owner deployment. No application, workflow, image, environment value, flag or deployment mutation; never read or reproduce real secrets.
- Public cloud delivery remains unqualified; notes startup refuses with `PCFG_NOTES_RUNTIME_UNAVAILABLE`. No invented enablement flags or ready runtime claims.
- Matching API signing seed and final package public trust are required; public key ID `e506b735`. Do not generate or rotate a key in this task.
- macOS disclosure: **ad-hoc signed application, unsigned DMG, no Apple Developer ID signature or notarization**.
- No heavy local execution, application imports, secret reads or production actions. Validate documentation against source and preserve all non-comment environment bytes.

## Review Focus

- Existing packaged trust versus a newly generated unrelated seed: instructions must prevent a mismatched production signer.
- Coolify Domains duplication, proxy hop counts and GraphQL routing: the primary layout must reflect Compose.
- Missing provider-role injection and unavailable notes runtime: an operator must not infer that adding a secret makes cloud delivery deployable.
- A successful signup without mail delivery or native activation: acceptance must exercise the real complete journey.
- Correct files uploaded but unpublished website manifest: publication must include verified manifest promotion and all four download links.

### Task 1: Reconcile the deployment instructions

**Files:**
- Modify: `DEPLOYMENT.md`.
- Modify narrowly: `docs/ops/DEPLOYMENT.md` and `implementation/deploy/README.md`.
- Modify comments only: `implementation/deploy/production.env.example`.

**Interfaces:**
- Consumes: the spec above and the coordinator's source audit pinned to main `9dd2105a356e39f6a369d7b2fb4dd1a19b3870bb`.
- Produces: an accurate manual operator runbook and consistent linked references; executable behavior is unchanged.

- [ ] Read the spec and source audit. Inspect the cited source only where needed to write concrete instructions, especially environment fields, exact publisher arguments and signing constraints. Record existing contradictions before editing.
- [ ] Rewrite the root guide around prerequisites, required environment inputs, source checkout/image identity, manual Coolify setup, migration/mail/account acceptance, current cloud boundary, package/publication acceptance, and backup/rollback. Resolve the five review-focus conditions explicitly.
- [ ] Correct corresponding routing/rate-limit/HSTS/signing/NDI wording in the two linked guides, and replace the unsafe standalone seed-generation instruction in template comments with matching-trust provisioning guidance. Preserve every non-comment template line byte-for-byte.
- [ ] Verify changed relative file links resolve, Markdown fences balance, referenced environment variables and commands exist in source, and the template's non-comment bytes equal the base. Run `git diff --check`; retain exact commands/results. Review the full diff for accidental ready claims or secrets. No prose-mirroring tests or app suite execution for this documentation-only task.
- [ ] Commit the four owned files and write the full report, including validation, changed paths, source limitations and self-review. Coordinator performs independent task review, whole-branch review, applicable hosted CI and merge verification.
