# Goal Contract - GOAL-devops-logto-coolify

## Identity

- Goal ID: GOAL-devops-logto-coolify
- Parent goal ID: GOAL-arch-customer-identity-oidc
- Title: Execution-ready runbook for self-hosting Logto on Coolify as the SelahCue customer IdP (plan/documentation only; no live provisioning)
- Role: devops-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy7aa3
- Created: 2026-08-10
- Updated: 2026-08-10
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Produce an execution-ready deployment runbook (`docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md`) that lets a human operator self-host and operate Logto on Coolify as the SelahCue customer identity IdP (DEC-006 / ADR-0022 §5), covering topology, the Coolify service definition (Logto + dedicated Postgres, ports, public issuer vs locked-down admin), TLS, env/secrets cross-referenced to `deployments.md`, encrypted+tested backup/restore, the H6 signing-key reconciliation, post-deploy Logto app registration (API resource, desktop native app, M2M management app), region/residency + retention hooks (FR-176/FR-177), upgrades/rollback + monitoring + SPOF/HA note, and a security-conditions checklist mapping the APPROVED-WITH-CONDITIONS findings H1–H7 + MEDIUMs (task 86ajy7aqw) to concrete deployment controls. Enumerate exactly the owner inputs required to execute. **Documentation + config only — no live provisioning, no DNS, no secrets, no application code.**

## Baseline

Verified current state before substantive work:

- **ClickUp task 86ajy7aa3** ([DevOps] Self-host Logto) is `planning/todo` under epic **86ajy5v6k**; it blocks the backend RP task 86ajy7add and the desktop PKCE-client task 86ajy7ak8 (dependency type 1, waiting_on). No comments yet. Verify step in the task: "OIDC discovery + JWKS reachable over TLS from the API host; a PKCE auth against the registered desktop client succeeds end-to-end in staging; restore drill documented. Independent review before QA."
- **ADR-0022** (`docs/architecture/adr/ADR-0022-customer-identity-oidc-logto.md`, Proposed) §5 flags the self-host/devops surface: Logto container + its Postgres, TLS-fronted; secrets via KMS/secret-manager not env files; backup/restore + version-pinned upgrades + staging tenant; data residency + retention are owner decisions.
- **Security review (task 86ajy7aqw)** verdict = **APPROVED-WITH-CONDITIONS** (comment 90130303357181). DevOps-routed conditions: **H6** (IdP-compromise blast radius — signing keys in KMS/HSM with rotation, TLS-validated JWKS, network-restricted least-privilege admin/management API, separate DB creds, key-use monitoring), **M3** (refresh rotation + reuse-detection revokes the whole family — Logto app config), **M5** (env-var secret hygiene — env injection from a secret manager is fine, plaintext env files are not), **M7** (privacy/NDPA-GDPR residency + retention spanning Logto + AccountUser), plus "confirm PKCE-only (reject plain/no-verifier) on the Logto app config." M4 (redaction denylist) already fixed pre-emptively on the backend.
- **deployments.md** (repo root) is the env-var key registry; §2 already lists the load-bearing Logto keys (`LOGTO_DB_URL` SECRET, `LOGTO_ENDPOINT`, `LOGTO_ADMIN_ENDPOINT`, `LOGTO_PORT`/`LOGTO_ADMIN_PORT`, `LOGTO_TRUST_PROXY_HEADER`) and §1c the RP keys (`SELAHCUE_OIDC_ISSUER`, `SELAHCUE_OIDC_AUDIENCE`, `LOGTO_MGMT_*`). The file documents key names only, never values, and asks new keys be added in the same turn.
- **Existing ops style reference:** `docs/ops/WINDOWS-INSTALLER.md` — concise, numbered, owner-facing, with a "First-run verification (owner)" section.
- No `docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md` exists yet. No server access, DNS, or secrets are available in this environment (hard boundary — plan only).

## Inputs and evidence sources

- Delegating-agent task (2026-08-10): author the Logto-on-Coolify runbook, plan-only; validated goal contract; ClickUp evidence on 86ajy5v6k/86ajy7aa3; move task only to a valid next status (not Done).
- `docs/architecture/adr/ADR-0022-customer-identity-oidc-logto.md` (esp. §1 desktop client, §2 RP/resource server, §3 revocation, §5 self-hosting/devops, §6 security posture)
- ClickUp 86ajy7aa3 (task scope), 86ajy7aqw (security verdict + H1–H7 + M1–M8 routing), epic 86ajy5v6k
- `deployments.md` (env-var registry), `docs/decisions/DECISION-LOG.md` (DEC-004/005/006)
- `docs/product/prds/SelahCue-PRD.md` FR-176/FR-177 (privacy policy/disclosures; DPA + cross-border transfer)
- `docs/ops/WINDOWS-INSTALLER.md` (style), Logto official self-hosting documentation (external, version-sensitive facts labelled)

## Scope

### In scope

- One runbook doc `docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md` covering the 10 required areas (topology; Coolify service def; TLS; env/secrets; backups + restore drill; H6 signing-key reconciliation; Logto app registration → deployments.md values; region/residency + retention hooks; upgrades/rollback + monitoring + SPOF/HA; security-conditions checklist H1–H7 + MEDIUMs).
- Names-only additions to `deployments.md` for any additional Logto/hosting env keys identified, marked SECRET vs public.
- Explicit enumeration of owner inputs required to execute (server/instance + spec, domain/DNS, region decision, list of secret values to supply).
- Goal Contract + ClickUp start/final evidence on 86ajy7aa3.

### Non-goals

- Any live provisioning: no Coolify deployment, no DNS records, no TLS issuance, no Logto tenant/app creation, no secret generation/injection, no restore executed against real data.
- Any application/runtime code, migrations, or backend/desktop OIDC implementation (owned by 86ajy7add / 86ajy7ag8 / 86ajy7ak8).
- Owner/legal decisions: hosting region, retention/deletion SLA, dedicated-vs-shared topology choice, HA timeline (surface, do not decide).
- Security approval or closing any H1–H7 finding (owned by security-reviewer task 86ajy7aqw at code-level re-test).
- Marking the task Done — the task is not executed.

### Constraints

- Hard boundary: RUNBOOK/PLAN ONLY. No server/DNS/secrets available in this environment.
- Honour ADR-0022 posture: system-browser PKCE public desktop client (no secret), JWKS-primary RP validation, OS-keychain token storage, no secrets in logs (ADR-0008/ADR-0011).
- Secrets via Coolify's encrypted store / a secret manager — never plaintext env files in prod (M5). deployments.md stays names-only, no values.
- Every DevOps-routed security condition (H6, M3, M5, M7, PKCE-only) maps to a concrete control; the H1–H5/H7 items owned by backend/desktop are shown as such, not claimed satisfied here.
- Label version-sensitive Logto facts Verified / Inferred / Assumed / Unknown; tell the operator to confirm against their pinned Logto version.

### Assumptions and unknowns

- ASSUMED: the deployment target is a Coolify-managed host (the task names Coolify explicitly). Owner: DevOps/owner confirms the host + spec.
- ASSUMED: Logto OSS stores OIDC signing keys + cookie keys in its Postgres (`logto_configs`), with no native HSM/KMS; rotation is via the Logto CLI. Owner: verify against the pinned Logto version before executing H6 controls.
- UNKNOWN: production hosting region + identity-data retention/deletion SLA (FR-176/FR-177 / NDPA-GDPR). Owner: product/legal + DevOps.
- UNKNOWN: dedicated-VM vs segmented-shared topology choice. Owner: owner picks from the documented trade-offs.
- UNKNOWN: the exact Logto Management API resource indicator + default signing algorithm for the pinned version. Owner: operator confirms from discovery/JWKS at deploy time; RP pins the alg (H1).

## Dependencies and approvals

- Owner/DevOps: provide server/instance + spec, domain/DNS, region decision, and supply secret values — required to execute the runbook. Status: PENDING (blocks execution, not this doc).
- Security Reviewer (86ajy7aqw): owns H1–H7 sign-off at code-level re-test before release; this runbook maps the infra-relevant conditions to controls but does not self-approve. Status: OPEN.
- Backend (86ajy7add/86ajy7ag8) + Desktop (86ajy7ak8): consume the issuer/JWKS/discovery URLs, client_id, audience, and M2M secret this runbook tells the operator to produce. Status: waiting_on this task.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`. Execution-time criteria that require server/DNS/secrets are marked `NOT_APPLICABLE` for this plan-only slice, with the justification recorded, and are handed to the owner-gated execution follow-up.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Runbook exists at the required path, follows the WINDOWS-INSTALLER.md ops style, and is grounded in ADR-0022 §5 + DEC-006 + the 86ajy7aqw verdict | Doc review + `rg` for section headings | `docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md` present with numbered operator sections; cites ADR-0022, DEC-006, task 86ajy7aa3/86ajy7aqw | `docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md` | PASS |
| C-002 | yes | Topology: dedicated IdP instance/VM (recommended per H6) vs segmented shared-server fallback, each with trade-offs and an owner-pick | Doc review | Both options documented with isolation/cost trade-offs; H6 blast-radius rationale for the dedicated recommendation; owner-pick flagged | Runbook "Topology" section | PASS |
| C-003 | yes | Coolify service definition for Logto + a dedicated Postgres: compose/resource config, ports, public issuer endpoint vs admin endpoint locked down (internal / IP-allowlist, never public) | Doc review | Compose/config snippet + port table; admin endpoint explicitly not public; Postgres separate from the Platform API DB on an internal network | Runbook "Coolify service definition" section | PASS |
| C-004 | yes | TLS via Coolify Let's Encrypt on a stable issuer host, with the issuer URL matching `SELAHCUE_OIDC_ISSUER` | Doc review | LE/reverse-proxy steps; `SELAHCUE_OIDC_ISSUER = <LOGTO_ENDPOINT>/oidc`; `TRUST_PROXY_HEADER` set behind the proxy | Runbook "TLS" section | PASS |
| C-005 | yes | Env/secrets: exact Logto env keys cross-referenced to deployments.md; secrets via Coolify encrypted store / secret manager (no plaintext env files); SECRET vs public marked (M5) | Doc review + cross-check to deployments.md | Env table for DB_URL/ENDPOINT/ADMIN_ENDPOINT/ports/TRUST_PROXY_HEADER etc., each mapped to a deployments.md key and SECRET/public label; no-plaintext-env rule stated | Runbook "Environment & secrets" section + deployments.md | PASS |
| C-006 | yes | Backups: encrypted, offsite, tested restore of Logto's Postgres, including a written restore drill | Doc review | Scheduled encrypted pg backup to offsite storage + step-by-step restore drill + verification (JWKS/sign-in) + the signing-key-in-DB restore caveat | Runbook "Backup & restore" section | PASS |
| C-007 | yes | Signing-key H6 reconciliation: DB-stored keys, mitigation (DB encryption + strict access + rotation procedure), residual risk recorded for owner acceptance | Doc review | States Logto OSS keeps keys in DB (no native HSM); documents encrypt-at-rest + least-privilege + CLI rotation steps; records the accepted-by-design residual risk (DEC-006) | Runbook "Signing keys (H6)" section | PASS |
| C-008 | yes | Post-deploy Logto app registration: API resource (audience), desktop native app (public, PKCE, redirect URIs), M2M management app — noting which produces which deployments.md value | Doc review | Console steps for each app; explicit mapping API resource → SELAHCUE_OIDC_AUDIENCE, native app id → SELAHCUE_OIDC_CLIENT_ID + redirect URIs, M2M → LOGTO_MGMT_APP_ID/APP_SECRET/ENDPOINT; PKCE-only + refresh-rotation/reuse-detection config (M3) | Runbook "Logto app registration" section | PASS |
| C-009 | yes | Region/residency + retention/deletion hooks (FR-176/FR-177, M7) flagged as owner/legal decisions spanning both Logto + AccountUser | Doc review | Residency (NDPA/GDPR/cross-border) + retention/right-to-erasure across Logto user + AccountUser flagged as owner/legal decisions, not decided here | Runbook "Region, residency & retention" section | PASS |
| C-010 | yes | Upgrades + rollback (staging first), health checks/monitoring, single-server SPOF note + HA-later | Doc review | Version-pinned upgrade tested in staging + DB-snapshot-before-upgrade rollback (forward-only alteration caveat); health/monitoring/alerts (IdP gates new sign-ins only); SPOF + HA-later path | Runbook "Upgrades, monitoring, HA" sections | PASS |
| C-011 | yes | Security-conditions checklist mapping H1–H7 + the MEDIUMs to concrete controls, marking which are satisfied by this runbook vs which belong to backend/desktop tasks | Doc review + cross-check to 86ajy7aqw | A table covering H1–H7 and M1–M8 with control + owner (runbook / 86ajy7add / 86ajy7ag8 / 86ajy7ak8 / owner); H6/M3/M5/M7 shown as runbook-satisfied controls | Runbook "Security-conditions checklist" section | PASS |
| C-012 | yes | deployments.md updated: any additional Logto/hosting env keys appended, names-only, SECRET vs public marked, consistent with existing style | `git diff` of deployments.md | New keys appended to the Logto/hosting section with SECRET/public labels and no values; existing keys unchanged | `deployments.md` diff | PASS |
| C-013 | yes | Owner inputs required to execute are enumerated: server/instance + spec, domain/DNS, region decision, and the list of secret values to supply | Doc review | A single "Owner inputs required to execute" section listing all four categories with the exact secrets to supply | Runbook "Owner inputs required to execute" section | PASS |
| C-014 | yes | No application/runtime code, no live provisioning, no duplicate Markdown tickets created | `git status --short` review | Only docs changed (runbook + this contract) plus the names-only deployments.md edit; no code, no ticket markdown | `git status --short` | PASS |
| C-015 | yes | Goal contract validates structurally; ClickUp start + final evidence posted on 86ajy7aa3; task moved to a valid next status (not Done) | `validate_goal_contract.py` + ClickUp read-back | Validator exits 0; start comment (engine + predicate) and final comment (predicate table + terminal state) on 86ajy7aa3; status advanced to `code review` | Validator output + ClickUp comments on 86ajy7aa3 | PASS |
| C-101 | no | OIDC discovery + JWKS reachable over TLS from the API host | curl the discovery/JWKS URL from the API host | 200 + valid JSON over a valid cert | Owner execution log | NOT_APPLICABLE |
| C-102 | no | A PKCE auth against the registered desktop client succeeds end-to-end in staging | Manual staging PKCE run | Auth Code + PKCE round-trip returns tokens; RP validates | Owner execution log | NOT_APPLICABLE |
| C-103 | no | Restore drill executed against a real backup with sign-in verified | Run the documented restore drill in staging | Restored Logto serves JWKS + admin sign-in | Owner execution log | NOT_APPLICABLE |

C-101/C-102/C-103 are `NOT_APPLICABLE` for this slice: no server, DNS, or secrets are available (the delegating agent's explicit hard boundary). They are the owner-gated execution verifiers and are carried forward on task 86ajy7aa3 for the execution step; this contract delivers the runbook that makes them runnable.

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-devops-logto-coolify.md`; `rg` for the runbook's required section headings + the H1–H7/M1–M8 rows; cross-check the env table against deployments.md.
- Broader regression verification: `git status --short` confirms only docs changed and no code/migrations/tickets; `deployments.md` diff is names-only.
- Independent verifier: independent review before QA (task requirement) + the security-reviewer re-test on 86ajy7aqw own H1–H7 sign-off; this pass ends at `GATE_REVIEW`.
- Required environment: local repository, ClickUp read/create tools, shell validators. No production/staging access (plan only).

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-015
- Hypothesis: ADR-0022 §5, the 86ajy7aqw security conditions, deployments.md, DEC-004/005/006, FR-176/177, and Logto's self-hosting model are sufficient to author an execution-ready Coolify runbook and append the needed env keys without any live provisioning or code.
- Change or investigation: Read the team contracts + validator, ADR-0022, both ClickUp tasks (scope + full security verdict), deployments.md, the decision log, FR-176/177, and the WINDOWS-INSTALLER style reference. Authored the runbook covering all 10 areas, appended Logto/hosting env keys to deployments.md (names-only), and enumerated owner inputs.
- Verifier executed: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-devops-logto-coolify.md` (PASS, 15 mandatory); `grep -nE '^## '` over the runbook → 14 numbered sections (0–13) + "First-run verification (owner)"; `grep` confirmed H1–H7, M1–M8, L1–L4 rows present; `git status --short` → only `docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md`, `docs/delivery/goals/GOAL-devops-logto-coolify.md`, `deployments.md`; `grep` confirmed the appended `LOGTO_POSTGRES_PASSWORD` + `LOGTO_BACKUP_*` keys in deployments.md.
- Result: C-001..C-015 PASS. C-101/C-102/C-103 remain NOT_APPLICABLE (owner-gated execution verifiers — no server/DNS/secrets in this environment).
- New evidence: `docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md`; deployments.md §2/§2a additions; ClickUp start comment 90130303363155 on 86ajy7aa3.
- Decision: gate-review

## Risks and rollback

- Risk: version-sensitive Logto facts (management-API resource indicator, default signing alg, key-storage internals, CLI syntax) drift across releases. Mitigation: label them Inferred/verify and instruct the operator to confirm against the pinned version at deploy time.
- Risk: the runbook could imply security conditions H1–H5/H7 are satisfied by hosting alone. Mitigation: the checklist marks each condition's true owner (runbook vs backend/desktop) and does not claim code-level items as done.
- Risk: H6 residual (IdP compromise = token forgery for any org) is inherent to self-hosting. Mitigation: document the layered controls + record the accepted-by-design residual (DEC-006) for explicit owner acceptance; recommend the dedicated-VM topology to shrink blast radius.
- Rollback or recovery: docs + names-only deployments.md edit; fully revertible, no runtime impact. The shipped enrollment-key activation path is untouched and remains the offline fallback.

## Pause and escalation conditions

- Pause before ANY live provisioning, DNS change, TLS issuance, secret generation/injection, Logto tenant/app creation, or restore against real data — all owner-gated.
- Escalate the topology choice (dedicated vs shared) and the residency/retention SLA to the owner/legal.
- Escalate H1–H7 sign-off to the security-reviewer (86ajy7aqw) at code-level re-test; do not self-approve.
- If ClickUp write access fails, record the pending comment text in this contract and return BLOCKED with the exact connection requirement rather than claiming ClickUp was updated.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-devops-logto-coolify.md`
- Validator result: PASS (structural; 18 criteria, 15 mandatory all PASS).
- Independent verification result: Pending independent review before QA (task requirement) + security-reviewer H1–H7 code-level re-test on 86ajy7aqw; this pass does not approve execution.
- Terminal state: GATE_REVIEW — the runbook (verifiable work) is complete and review-ready; live provisioning + the execution verifiers (C-101 discovery/JWKS over TLS, C-102 staging PKCE E2E, C-103 executed restore drill) are owner-gated and carried forward on task 86ajy7aa3.
- Remaining failed or blocked criteria: none FAIL/BLOCKED; C-101/C-102/C-103 remain NOT_APPLICABLE for this plan-only slice (owner-gated execution).
- ClickUp final evidence comment: recorded on task 86ajy7aa3; task moved to `code review` for independent review of the runbook (not Done — not executed).
