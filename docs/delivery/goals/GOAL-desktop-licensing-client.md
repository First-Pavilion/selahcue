# Goal Contract — GOAL-desktop-licensing-client

## Identity

- Goal ID: GOAL-desktop-licensing-client
- Parent goal ID: 86ajy5v6k (EPIC — Platform API / Licensing & Entitlements)
- Title: Desktop licensing client foundation — device activation over both shipped paths, device-token custody in the OS secret store, and a rotation-ready trusted-key set
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5mn11
- Created: 2026-08-25
- Updated: 2026-08-25
- Maximum iterations: 10
- Independent verification required: yes

## Objective

A fresh SelahCue desktop install can activate itself against the Platform API — by signing in, or with an enrollment key — and keeps its device token where only the OS secret store can hand it back, without any licensing state, failure or outage being able to blank, block or degrade live output.

## Baseline

Verified at `607a7b5` before work began:

- **The desktop consumed none of the platform.** No activation, entitlement or licence code in any of the 13 Rust crates; no `ed25519` in `implementation/desktop/Cargo.lock` (`grep -c ed25519` → 0).
- `selahcue-cloud` already owned the seams this work needed: `HttpTransport` (+ `ReqwestTransport`/`MockTransport`), `SecretStore` (+ `KeyringSecretStore`/`InMemorySecretStore`) and a self-redacting `Token`. Reused rather than duplicated.
- `selahcue-data` migrations contain no token, licence or credential column (`grep -i` → none), so "never in the app database" started true and had to be kept true.
- Server side already shipped: `POST /v1/activations` (enrollment key) and the `activateDeviceWithSession` GraphQL mutation (account session), plus the signed entitlement manifest.

## Inputs and evidence sources

- `docs/product/prds/SelahCue-Platform-PRD.md` — EPIC-PL-C, FR-513/517/518, CON-P1/P2/P7, NFR-501/502/504.
- DEC-004 (activation model), DEC-005/007 (both paths; sign-out invariant), DEC-011 pt 2 (trusted key **set**) and pt 3 (both paths retained).
- `implementation/api/selahcue_api/` read directly — `platform/views.py`, `platform/urls.py`, `graphql/account_schema.py`, `graphql/errors.py`, `graphql/views.py`, `apps/devices/services.py`, `apps/entitlements/signing.py`.
- `docs/design/ACCOUNT-SETUP-HANDOFF.md` (frames A4/A5/A6/A7/A9), `docs/design/ACCOUNT-AUTH-API-HANDOFF.md`.
- Review findings: Sana (security), Cody (code).

## Scope

### In scope

- A licensing client crate speaking the shipped `/v1` and account-GraphQL activation contracts.
- Sign-in as the primary path; enrollment key as the retained delegation path.
- Device-token custody in the OS secret store; sign-out keeps the device token.
- The trusted entitlement-signing key **set**, selected by `key_id`.

### Non-goals

- Manifest fetch, Ed25519 signature verification, entitlement caching — 86ak5mn1d.
- Opportunistic refresh and backoff — 86ak5mn1h.
- Enforcement behaviour of any kind — 86ak5mn1t.
- The account-setup screens — 86ajy7anx.

### Constraints

- CON-P1 / NFR-024: no licensing state, transition, API response or outage may blank, block or degrade live output.
- CON-P2 / NFR-015: core presentation runs with zero network for the whole entitlement window.
- CON-P7: the manifest signature covers the transmitted base64url payload string, not the decoded JSON.
- The device token is a credential: OS secret store only, never a file, never the database, never a log.

### Assumptions and unknowns

- **UNKNOWN → now VERIFIED FALSE:** that both activation paths share `POST /v1/activations`. They do not; the account path is a GraphQL mutation. Corrected against source.
- **BLOCKED:** the account-session path cannot authenticate against the deployed API — Django CSRF rejects `/graphql/account` and the injected transport carries only a bearer. Owner: API side, tracked as `86ak5t1gw`.
- **ASSUMED:** no production entitlement signing public key exists yet to bundle; the trust store ships empty and fails closed on verification only.

## Dependencies and approvals

- `86ak5t1gw` (CSRF on `/graphql/account`) — API owner, OPEN. Blocks the primary path end to end; does not block this ticket's scope.
- A5/A6 sub-code on the enrollment-key path — product/API decision, OPEN, deliberately not invented client-side.
- `86ak5rjh7` (Otto) — `make ci` cannot run on a fresh clone without the Tauri sidecar placeholders.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A fresh install activates via sign-in and receives a device token | `cargo test -p selahcue-licensing --test test_client` | `a_fresh_install_activates_by_signing_in_and_receives_a_device_token` passes | test output | PASS |
| C-002 | yes | The enrollment-key path activates the same machine | same | `the_enrollment_key_path_activates_the_same_machine` passes | test output | PASS |
| C-003 | yes | The device token is reachable only through the OS secret store; no plaintext copy on disk or in the database | `cargo test -p selahcue-licensing --test test_custody` | redaction sweep + no-filesystem-primitive sweep + DB-schema sweep all pass | test output | PASS |
| C-004 | yes | Signing out leaves the device token intact | same | `sign_out_leaves_the_device_token_intact` passes; mutation-verified RED | test output; battery log | PASS |
| C-005 | yes | Replaying an activation returns the original result and consumes no second slot | `cargo test -p selahcue-licensing --test test_client` | replay → `KeepExisting`; re-mint → overwrite | test output | PASS |
| C-006 | yes | No licensing code is reachable from the render, go-live or live-control path | `cargo test -p selahcue-licensing --test test_never_blank` | `licensing_is_absent_from_the_entire_render_and_live_control_closure` passes over the **transitive** closure | test output | PASS |
| C-007 | yes | Activation failure never blocks starting or presenting | same | every failure and status variant permits presentation; a failed activation destroys no existing token | test output | PASS |
| C-008 | yes | The trust store is provably a **set** selected by `key_id`, bounded, and refuses collisions | `cargo test -p selahcue-licensing --test test_trust` | set proof, compile-time floor, cap, collision refusal all pass | test output | PASS |
| C-009 | yes | `NOT_FOUND` is classified per path (A6 on session, A4 on key) | `cargo test -p selahcue-licensing --test test_client` | both `not_found_on_the_*` tests pass | test output | PASS |
| C-010 | yes | The full local CI gate is green | `make ci` | exit 0; 147 cargo test-result lines; 0 failures | `MAKECI_REAL_EXIT=0` | PASS |
| C-011 | yes | Every named guard is mutation-verified: broken → RED, restored → GREEN | mutation batteries with landing proof, clean-baseline re-verification and `--no-fail-fast` | every mutation caught by the guard it names | battery summaries | PASS |
| C-012 | yes | Independent review findings remediated | Sana + Cody review | all in-scope findings closed; out-of-scope ticketed | ClickUp comments | PASS |
| C-013 | no | Live integration against the API under Docker Compose | `docker compose up` + client run | activation succeeds end to end | — | BLOCKED |

`C-013` is non-mandatory and BLOCKED: the compose file bind-mounts `implementation/api`, which peer sessions are actively editing, so a run would exercise their mid-edit state rather than the shipped contract; it also requires an `api/.env` absent from the repo. It is additionally blocked behind `86ak5t1gw`. The wire contract is instead pinned byte-for-byte to server source, including `key_id` fixtures computed by Python running the server's own `derive_key_id`.

## Verification plan

- Focused verification: `cargo test -p selahcue-licensing --no-fail-fast` (78 tests).
- Broader regression verification: `make ci` — fmt ×2, clippy ×5 with `-D warnings`, `cargo test --workspace`, `scripts/import_guards.sh`, four feature-gated suites, operator check + test, headless operator webview, `flutter analyze` + tests.
- Mutation verification: two batteries in a ticket-scoped path with per-mutation landing proof, a verified-clean baseline between mutations, and `--no-fail-fast`.
- Independent verifier: Cody (code), Sana (security), Vera (performance), Quinn (QA).
- Required environment: macOS, Rust stable, Flutter; no network required.

## Iteration ledger

### Iteration 1 — build

- Target criterion: C-001…C-008
- Change: new `selahcue-licensing` crate reusing `selahcue-cloud`'s transport/secret seams.
- Result: green; six mutations caught. Commit `c2e3deb`.
- Decision: handoff to review.

### Iteration 2 — security remediation (Sana)

- Target criterion: C-003, C-008
- Hypothesis: the redaction fix covered requests only, and the trust store swallowed `key_id` collisions.
- Change: token fields typed `Token` (structural redaction); per-entry positive controls; a source-level guard requiring any secret-named field to be `Token`-typed; collision refused.
- Result: green; 11/11 mutations caught. Commit `46ea4f2`.
- New evidence: two harness defects found and fixed — an inert mutation that scored "survived", and mtime-preserving restores that reused a mutated test binary across mutations.
- Decision: handoff to review.

### Iteration 3 — code remediation (Cody)

- Target criterion: C-006, C-009, C-003
- Hypothesis: `NOT_FOUND` was path-ambiguous; the never-blank guard saw only direct dependencies; the test-support transport printed request bodies.
- Change: path-aware classification with `NoActiveLicense`; transitive-closure guard; `RecordedRequest`/`ScriptedTransport` `Debug` redacted; `UnexpectedStatus` for non-5xx non-contract responses; `is_known_remint`; dead `truncate` removed; workspace-membership check moved into `scripts/import_guards.sh` where it can actually fail.
- Result: green; 10/10 mutations caught plus the membership guard verified by its own verifier.
- New evidence: a third harness defect — the failure-name regex was blind to uppercase, producing a false "survived".
- Decision: handoff to review.

## Risks and rollback

- Risks: the primary path is unreachable until `86ak5t1gw` is resolved; the bundled trust store is empty until a production key is issued; A5/A6 remain merged on the enrollment-key path pending a server sub-code.
- Rollback or recovery: the crate is additive and nothing on the render or live-control path depends on it, so reverting the two commits removes it with no effect on presentation.

## Pause and escalation conditions

- The A5/A6 sub-code is a product/API decision — owner, not this role.
- `86ak5t1gw` is an API-side decision — do not work around it in the client.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-desktop-licensing-client.md`
- Validator result: see ClickUp evidence comment.
- Independent verification result: Sana PASS with required remediations (closed); Cody not-ready-for-PR (closed); Vera and Quinn pending.
- Terminal state: GATE_REVIEW — implementation and review remediation complete; Vera and Quinn outstanding before any PR.
- Remaining failed or blocked criteria: `C-013` (BLOCKED, non-mandatory).
- ClickUp final evidence comment: https://app.clickup.com/t/86ak5mn11
