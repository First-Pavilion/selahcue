# Goal Contract — ARCH-17tnw2az0g6-direct-to-provider

## Identity

- Goal ID: ARCH-17tnw2az0g6-direct-to-provider
- Parent goal ID: NONE
- Title: Architecture revision for the owner's direct-to-provider directive (STT and sermon notes), folded into ADR-0027 / ADR-0028 on PR #111
- Role: software-architect
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2az0g6
- Created: 2026-09-27T12:00:00Z
- Updated: 2026-09-27T12:00:00Z
- Maximum iterations: 4
- Independent verification required: yes

## Objective

An ADR set on PR #111 that an independent reviewer (Sana, Vera) can check against the owner's directive and their review findings: the Platform API only authenticates, checks allowance and issues a provider credential; usage is attributed by something only the server controls; commit comes from server-to-server reconciliation; the OpenAI credential question is answered from provider documentation with its unknowns stated.

## Baseline

- ADR-0027 at `e8e782d` (Proposed, Draft PR #111). Vera's review (6 items, 2 High) and Sana's review (8 items, 3 blocking) posted on the PR and the epic.
- `selahcue-cloud/src/openai.rs` calls `POST /v1/responses` with a developer key and a JSON schema; its module doc calls a client-held key unacceptable for shipping.
- No outbound provider call exists in `implementation/api` today.

## Inputs and evidence sources

- PR #111 reviews and inline comments; epic 17tnw2az0g6 comments; tickets 86akby3xu, 17tnw2az0gn, 86akby344, 86akby4e9, 86ajy04hz.
- Deepgram docs: token-based auth, keys create, requests list, usage breakdown, API key limits, discussions #673 and #1409.
- OpenAI docs: realtime client secrets create, usage API (completions), admin API projects / service accounts / rate limits, key permissions help article.

## Scope

### In scope

- ADR-0027 revision (D5 settlement semantics, D6 replaced, review dispositions, staff-auth dependency).
- New ADR-0028 for the provider access boundary (credential issue, attribution, reconciliation) for both providers.
- Epic comment naming ticket fallout.

### Non-goals

- Implementation code; ticket description edits (Priya / Diego own those); starting Kenji.

### Constraints

- No claim about a provider capability without a documentation source or an explicit UNKNOWN.

### Assumptions and unknowns

- UNKNOWN: whether OpenAI Realtime ephemeral usage is reported under the parent key/project in the Usage API — spike owner Nova/Kenji.
- UNKNOWN: Deepgram limit on durable keys per project and the log reporting lag — spike 86akby344.

## Dependencies and approvals

- Owner decision on the OpenAI option (ADR-0028 D4) — owner.
- Security re-review (Sana) and performance re-review (Vera) of the revision — independent verifiers.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | ADR states whether removing the server-side OpenAI call resolves Vera's worker finding, including the residual mint-call cost | Read ADR-0028 D6 | Explicit yes-with-residual and a timeout/capacity rule | ADR-0028 | PENDING |
| C-002 | yes | Attribution for both providers uses only server-chosen identity, fails closed on unattributable usage, and reconciles server-to-server read-only | Read ADR-0028 D2, D3, D5 | All three properties stated per provider | ADR-0028 | PENDING |
| C-003 | yes | OpenAI ephemeral-credential research is stated with sources and the key-to-client risk is presented as an owner tradeoff | Read ADR-0028 D4 | Options with sources, unknowns and a recommendation | ADR-0028 | PENDING |
| C-004 | yes | Deepgram error bound stated honestly | Read ADR-0028 D3 | Bound names parallel streams and stream length, and the shared concurrency pool | ADR-0028 | PENDING |
| C-005 | yes | Ledger commit comes from reconciliation for both meters; replay rules defined | Read ADR-0027 D5 + ADR-0028 D5 | State machine and replay table present | ADR-0027/0028 | PENDING |
| C-006 | yes | Ticket fallout named on the epic | ClickUp epic comment read-back | Comment lists 17tnw2az0gn, 86akby3xu, 17tnw2az0gq, 86akby4e9, 86akby344 with required rework | Epic comment | PENDING |
| C-007 | yes | Revision pushed to the PR #111 branch, not behind origin/main | `git rev-list --count HEAD..origin/main` and `gh pr view 111` | 0 and new head SHA | PR #111 | PENDING |
| C-008 | yes | Independent security and performance re-review passed | Sana / Vera review on PR #111 | No open blocking finding | PR #111 | PENDING |

## Verification plan

- Focused verification: reread both ADRs against each review finding; read back the ClickUp comment.
- Independent verifier: Sana (C-002..C-005), Vera (C-001, C-005).
- Required environment: docs only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-007
- Hypothesis: per-org server-held credentials give server-controlled attribution for Deepgram; OpenAI lacks an ephemeral credential for the Responses API.
- Change or investigation: provider documentation research; ADR-0028 written; ADR-0027 revised.
- Verifier executed: see Final evaluation.
- Result: recorded at hand-off.
- New evidence: Deepgram grant tokens share the parent key's accessor; request logs carry `api_key_id` per request; temporary API keys capped at 250/day. OpenAI client secrets grant Realtime API access only.
- Decision: gate-review

## Risks and rollback

- Risks: the recommended OpenAI path depends on an unverified Realtime capability.
- Rollback or recovery: docs only; revert the commit.

## Pause and escalation conditions

- Owner decision on ADR-0028 D4 before any notes build ticket starts.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/ARCH-17tnw2az0g6-direct-to-provider.md`
- Validator result: recorded at hand-off
- Independent verification result: pending (C-008)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-008 pending independent review; owner decision on ADR-0028 D4
- ClickUp final evidence comment: epic 17tnw2az0g6
