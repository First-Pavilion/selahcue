# Public cloud release boundary — direct-provider

Status: DECIDED by the owner on 14 November 2026. Keep the direct-provider design in ADR-0028. Public API base URL: `https://api.selahcueapp.com`. The owner deploys manually through Coolify.

## Required result

Windows, macOS and Ubuntu installers include cloud transcription and AI sermon notes. Downloads are published to `https://selahcue-installers.sfo3.digitaloceanspaces.com`. Apple Developer ID signing and notarization are waived for this release; any ad-hoc signature must be described accurately.

Reusable Deepgram and OpenAI credentials remain on the server. Installers contain the public API address and receive account/device credentials and short-lived provider credentials at runtime. No provider key is embedded at build time.

## Selected data flow

1. The desktop signs in and activates its device against SelahCue. The API resolves the church and plan from authenticated server records.
2. The API checks entitlement and weekly allowance, reserves usage, and issues a short-lived provider credential. The client cannot choose another church's billing identity.
3. Audio goes directly from the desktop to Deepgram. Note input goes directly to OpenAI under option A, subject to the qualification decision in ADR-0028.
4. Server jobs reconcile provider-observed usage against the church's parent key/project. Client reports are diagnostic inputs and cannot establish billable identity.
5. Parent provider keys and any OpenAI administrative credential remain in server secret storage. The admin credential is for usage/provisioning administration, not model inference or installer configuration. The current experiment uses it only for usage reads.
6. Allowances retain the existing Free/Core/Pro values: transcription minutes 20/50/80; notes 1/5/10. Preserve the account-timezone Monday reset, upgrade/downgrade and carried-debt decisions in ADR-0027/0028.

The owner did not select the proposed audio/notes gateway. Notes option C remains only the already-approved conditional fallback if the Realtime spike fails; no result is invented to select it. Reusable OpenAI keys on a desktop remain rejected.

## Verified source gap

Main `40661b4fde38f1e670bc8fde522c17b30bdb93a7` has licensing/account API routes, catalogue migrations, Celery/Redis infrastructure, and an injectable Deepgram client. It lacks public STT grants, the selected notes service, provider credential provisioning/reconciliation and the weekly usage ledger. The operator does not yet integrate the complete native account/activation journey. Ordinary installer builds enable local STT; they are packaging baselines, not the requested cloud release.

The credential-bearing pilot is unsuitable for unrestricted public downloads. The selected design needs new server and desktop integration, its provider qualification, and a fresh build after those changes.

## Qualification and release gates

- Complete the observed Deepgram attribution and OpenAI Realtime experiments, retaining uncertainty and conflicting provider documentation. See the public-provider qualification evidence dated 14 November.
- Verify tenant boundaries, revoked devices, expired licences, concurrent reservations, retries, replay and over-limit refusal without secrets or content in logs.
- Bound provider abuse using actual provider behavior and approved project limits. Token expiry alone does not establish an inference-duration or spending cap.
- Verify a fresh install can sign in, transcribe synthetic speech and produce a valid note draft against the deployed API without shell configuration.
- Prepare a manual Coolify deployment runbook for the implemented services, secret variable names, migrations, HTTPS routing, health checks and rollback. Runtime verification follows the owner's deployment.
- Independently review the implementation and runtime evidence, inspect installed packages, and compare public downloaded bytes with the verified immutable artifacts before promoting website links.


## Normal note cost target — owner decision

The owner selected a target of at most USD 0.25 per AI note, including its one allowed retry. Qualify the selected direct Realtime candidate against this target at representative lengths. Keep normal generation cost, ledger token accounting and provider-enforced abuse exposure distinct; this decision does not approve unlimited sessions or a particular project rate limit.

## Controlled pilot delivery decision

The owner selected a controlled pilot with manually enabled cloud access for selected churches on 14 November 2026. The delivery deadline is 15 November 2026 at 16:36 UTC (17:36 Africa/Lagos), not a 24-hour pilot duration. All three platforms and both cloud features remain in scope. Provider mappings can be provisioned manually; automatic fleet provisioning and unrestricted self-service cloud access are deferred. Entitlement, tenant/device binding, bounded admission, provider reconciliation, credential custody and the USD 0.25 normal-note target still apply. Reviewed PRs with passing applicable checks may be merged without another approval request. The owner performs the final Coolify deployment using repository-root DEPLOYMENT.md.
