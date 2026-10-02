# Goal Contract — ARCH-17tnw2az0g6-direct-to-provider

## Identity

- Goal ID: ARCH-17tnw2az0g6-direct-to-provider
- Parent goal ID: NONE
- Title: Architecture revision for the owner's direct-to-provider directive (STT and sermon notes), folded into ADR-0027 / ADR-0028 on PR #111
- Role: software-architect
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2az0g6
- Created: 2026-09-27T01:01:36Z
- Updated: 2026-10-02T10:53:00Z
- Maximum iterations: 4
- Independent verification required: yes

Timestamps: `Created` is the commit time of the first commit that carries this file (`91d210d`). The original value, 2026-09-27T12:00:00Z, was later than the commits that contained it and so cannot have been true when written. `Updated` is the time of the 2026-10-02 edit.

## Objective

An ADR set on PR #111 that an independent reviewer (Sana, Vera) can check against the owner's directive and their review findings: the Platform API only authenticates, checks allowance and issues a provider credential; usage is attributed by something only the server controls; commit comes from server-to-server reconciliation; the OpenAI credential question is answered from provider documentation with its unknowns stated.

## Baseline

- ADR-0027 at `e8e782d` (Proposed, Draft PR #111). Vera's review (6 items, 2 High) and Sana's review (8 items, 3 blocking) posted on the PR and the epic.
- Iteration 1 produced ADR-0028 and ADR-0027 revision 2 (`91d210d`, `903dfa7`).
- The owner then decided ADR-0028 D4 (OpenAI option), D5 (retry grace) and D7 (overrun carry) on 2026-09-27. They are recorded as ADR-0028 revision 2 and ADR-0027 revision 3 at `38755430`. **D4: option A (Realtime text-only with a client secret), spiked first; option C if the spike fails; option B rejected.**
- A review of revision 3 at `38755430` (PR #111, 2026-10-02) found process gaps, content findings a to k, and the goal-contract problems corrected here. Its fixes are ADR-0027 revision 4 and ADR-0028 revision 3.
- `selahcue-cloud/src/openai.rs` calls `POST /v1/responses` with a developer key and a JSON schema; its module doc says a desktop-held key is not acceptable in a shipped product.
- No outbound provider call exists in `implementation/api` today.

## Inputs and evidence sources

- PR #111 reviews and inline comments; epic 17tnw2az0g6 comments; tickets 86akby3xu, 17tnw2az0gn, 86akby344, 86akby4e9, 86ajy04hz.
- Deepgram docs: token-based auth, keys create, requests list, usage breakdown, API key limits, discussions #673 and #1409.
- OpenAI docs: realtime client secrets create, usage API (completions), admin API projects / service accounts / rate limits, key permissions help article.
- Provider documentation was read on 2026-09-27 and **has not been re-read since** (ADR-0028 open item OI-6).

## Scope

### In scope

- ADR-0027 revisions (D5 settlement semantics, D6 replaced, review dispositions, staff-auth dependency; revision 4: D3 fallback refusals, throttles, retention, single source of truth for held allowance).
- New ADR-0028 for the provider access boundary (credential issue, attribution, reconciliation) for both providers; revision 3 adds the settle-point definition, provisioning gate, desktop custody (D8) and the open-items list.
- Epic comment naming ticket fallout.

### Non-goals

- Implementation code; ticket description edits (Priya / Diego own those); starting Kenji.
- Edits to the Platform PRD, ADR-0010 or `openai.rs`: they are listed as open items (ADR-0028 OI-7 to OI-9), not done.

### Constraints

- No claim about a provider capability without a documentation source or an explicit UNKNOWN.
- No invented ticket ids: an item without a ticket says so.

### Assumptions and unknowns

- UNKNOWN: whether OpenAI Realtime ephemeral usage is reported under the parent key/project in the Usage API; the other three spike criteria in ADR-0028 D4 — spike owner Nova (in progress; owner-approved 2026-09-27).
- UNKNOWN: Deepgram limit on durable keys per project, the log reporting lag, and whether a still-open stream appears in the request log — spike 86akby344.
- UNKNOWN: `NOTE_TOKEN_ENVELOPE`, the held-open transcript ceiling, the provisioning budget (ADR-0028 OI-3, OI-4, OI-5).

## Dependencies and approvals

- Owner decision on the OpenAI option (ADR-0028 D4): **DECIDED 2026-09-27** (A, spiked first; C if the spike fails; B rejected). Nothing is pending on the owner for D4 itself.
- OpenAI Realtime spike result (Nova): pending. It picks A or C and gates the notes build tickets.
- Security re-review (Sana) and performance re-review (Vera) of the revision: independent verifiers (C-008).
- Ticket ids for the open items that have none (staff authenticator, PRD amendments, ADR-0010 clause, `openai.rs` comment, `NOTE_TOKEN_ENVELOPE`, held-open ceiling, provisioning budget): owner to supply.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | ADR states whether removing the server-side OpenAI call resolves Vera's worker finding, including the residual mint-call cost | Read ADR-0028 D6 | Explicit yes-with-residual and a timeout/capacity rule | ADR-0028 D6 (author re-read at revision 3, 2026-10-02) | PASS |
| C-002 | yes | Attribution for both providers uses only server-chosen identity, fails closed on unattributable usage, and reconciles server-to-server read-only | Read ADR-0028 D2, D3, D5 | All three properties stated per provider | ADR-0028 D2, D3, D5 (author re-read at revision 3) | PASS |
| C-003 | yes | OpenAI ephemeral-credential research is stated with sources and the key-to-client risk is presented as an owner tradeoff | Read ADR-0028 D4 | Options with sources, unknowns and a recommendation | ADR-0028 D4; the owner has since decided it (OD-R1). Sources not re-read since 2026-09-27 (OI-6) | PASS |
| C-004 | yes | Deepgram error bound stated honestly | Read ADR-0028 D3 | Bound names parallel streams and stream length, and the shared concurrency pool | ADR-0028 D3 (author re-read at revision 3) | PASS |
| C-005 | yes | Ledger commit comes from reconciliation for both meters; replay rules defined | Read ADR-0027 D5 + ADR-0028 D5 | State machine and replay table present | ADR-0027 revision 4 D5; ADR-0028 revision 3 D5 (the replay rules are now a table) | PASS |
| C-006 | yes | Ticket fallout named on the epic | ClickUp epic comment read-back | Comment lists 17tnw2az0gn, 86akby3xu, 17tnw2az0gq, 86akby4e9, 86akby344 with required rework | Epic comment 1400430000022746, read back in iteration 1. Not re-read in iteration 3, and it predates revisions 3 and 4 | PASS |
| C-007 | yes | Revision pushed to the PR #111 branch, not behind origin/main | `git rev-list --count HEAD..origin/main`, and the PR's head SHA on GitHub | 0 and the new head SHA | 2026-10-02: 0 after merging `origin/main` (`feaee70`) into the branch (merge commit `3d99e40`), re-run immediately before the push. **Perishable:** true only at push time; it goes stale as main moves and must be re-run when the PR is merged | PASS |
| C-008 | yes | Independent security and performance re-review passed | Sana / Vera review on PR #111 | No open blocking finding | PR #111 | PENDING |

## Verification plan

- Focused verification: reread both ADRs against each review finding; read back the ClickUp comment.
- Independent verifier: Sana (C-002..C-005), Vera (C-001, C-005).
- Required environment: docs only.
- C-001 to C-006 are the author's own checks. Only C-008 is independent.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-007
- Hypothesis: per-org server-held credentials give server-controlled attribution for Deepgram; OpenAI lacks an ephemeral credential for the Responses API.
- Change or investigation: provider documentation research; ADR-0028 written; ADR-0027 revised.
- Verifier executed: see Final evaluation.
- Result: C-001..C-007 recorded as PASS (ADR-0028, ADR-0027 revision 2 at `91d210d`; epic comment 1400430000022746 read back). **C-007 was wrong as recorded:** its evidence column said "expect 0", an expectation and not a measurement, and the 2026-10-02 review measured the branch 136 commits behind `origin/main`. Corrected in iteration 3.
- New evidence: Deepgram grant tokens share the parent key's accessor; request logs carry `api_key_id` per request; temporary API keys capped at 250/day. OpenAI client secrets grant Realtime API access only.
- Decision: gate-review

### Iteration 2

- Target criterion: none (no criterion status changed); record the owner's decisions.
- Hypothesis: the owner's three answers close the pending owner decisions without reopening any criterion.
- Change or investigation: ADR-0028 revision 2 and ADR-0027 revision 3 at `38755430`: OD-R1 (notes option A, spiked first, C if it fails, B rejected), OD-R2 (one retry per notes session), OD-R3 (overrun carries into the next week only, capped at one week of debt).
- Verifier executed: none beyond re-reading the two ADRs.
- Result: the D4 owner decision, listed in iteration 1 as outstanding, is decided. The OpenAI spike result is the only thing still pending on the notes path.
- Decision: continue

### Iteration 3

- Target criterion: C-005, C-007, and the goal-contract findings of the 2026-10-02 review of `38755430`.
- Hypothesis: every content finding (a to k) can be answered in the ADR text, either by deciding it or by recording it as an explicit open item. None needs a code change.
- Change or investigation: merged `origin/main` (`feaee70`) into the branch, with no rebase and no force-push; ADR-0027 revision 4; ADR-0028 revision 3; this contract corrected (timestamps, baseline, owner decision, ledger, C-007 re-run). Code claims touched by the revisions were re-checked on `feaee70`: both `is_fallback` refusals, the staff header bridge, and the `openai.rs` module doc.
- Verifier executed: `python3 scripts/validate_goal_contract.py docs/delivery/goals/ARCH-17tnw2az0g6-direct-to-provider.md` (structural PASS); `git rev-list --count HEAD..origin/main` (0); criteria C-001 to C-005 re-read against the new text.
- Result: C-001..C-007 PASS as author checks; C-008 still PENDING. `--require-complete` fails only on C-008.
- New evidence: the throttle in revision 3 could not carry 5-minute transcript slices (12 an hour against a cap of 10); the `ISSUED` state made the retention rule unsafe as written; both are fixed in the ADR text.
- Decision: gate-review

## Risks and rollback

- Risks: the chosen OpenAI path (option A) depends on an unverified Realtime capability, and its fallback (option C) is owner-approved. Provider facts in the ADRs date from 2026-09-27 and are unverified since. Several figures are explicitly not set (ADR-0028 OI-3, OI-4, OI-5).
- Rollback or recovery: docs only; revert the commit.

## Pause and escalation conditions

- No notes build ticket starts until the OpenAI spike reports (ADR-0028 D4). This is no longer an owner decision: the owner has decided.
- The ADRs do not move to `Accepted` until the items in "Needed before Accepted" (ADR-0027) and "Open items before Accepted" (ADR-0028) are closed.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/ARCH-17tnw2az0g6-direct-to-provider.md`
- Validator result: structural PASS; with `--require-complete` it fails only on C-008 (pending)
- Independent verification result: pending (C-008)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-008 pending independent security and performance re-review; the OpenAI spike result; the ticket ids and figures listed under ADR-0028 "Open items before Accepted"
- ClickUp final evidence comment: epic 17tnw2az0g6
