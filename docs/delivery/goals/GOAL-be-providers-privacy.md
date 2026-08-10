# Goal Contract — GOAL-be-providers-privacy

## Identity

- Goal ID: GOAL-be-providers-privacy
- Parent goal ID: 86ajp08py (EPIC — R3 · Transcription (STT))
- Title: Backend for the Settings → Providers & Privacy screen — settings/consent persistence, on-device transcription default, and a SelahCue-hosted cloud client (note-generation + cloud transcription) built against a defined API contract and integration-tested with a local mock
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy034h
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Deliver the desktop-side backend for the Providers & Privacy settings screen (Design 2.0 reference frame `338:124`): persist all screen settings and cloud-consent state, keep the app offline-by-default with cloud strictly opt-in and Administrator-gated, expose provider readiness and settings read/write to the operator webview, and provide a fully-functional on-device transcription default plus a SelahCue-hosted cloud client (sermon-note generation + cloud transcription) implemented against a defined SelahCue cloud API contract and integration-tested against a local mock — such that pointing the client at the real service (when it exists) is a configuration change, not a code change.

## Baseline

Verified from a full backend investigation this session:

- **No settings/consent/config store exists.** No key-value settings table, no `settings_repo`, no consent/provider-selection persistence (grep of `selahcue-data/src` for `settings|preference|consent|provider_config` → zero hits). Persistence today is domain repos (`plan_repo`, `deck_repo`, `saved_theme_repo`, …); the reusable KV template is `saved_theme_repo.rs` (`save_all`/`load_all`, `(String,String)` replace-set) + append-only `migrations.rs` (currently schema **v18**, `PRAGMA user_version`).
- **`TranscriptProvider` seam exists** (`selahcue-core/src/transcript.rs:147`): `ManualProvider` (default) + `SttProvider` (`selahcue-stt`, on-device Whisper). Provider is swapped at **compile time** / hardware-selected — there is **no runtime, persisted, user-chosen provider selection**, and **no note-generation / AI-provider trait at all**.
- **Secret store is single-purpose.** `selahcue-desktop/src/keys.rs` wraps the `keyring` crate but is hard-wired to one credential (`service "SelahCue"`, user `"database-key"`). No generic named-secret API; the `Entry::new → get/set_password` + `zeroize` idiom (keys.rs:96-133) is the template to reuse for an account/session token.
- **No cloud/consent/privacy backend.** The only consent reference is a hard-coded UI placeholder (`operator/dist/preservice.js:171` `"AI consent — later"`). No cloud endpoint, account/auth, quota source, or privacy text anywhere.
- **Operator webview ↔ backend pattern is mature.** `#[tauri::command] async fn … -> Result<T,String>` reading `State<'_, AppState>`, registered in `generate_handler![…]`, invoked from `dist/app.js` via `window.__TAURI__.core.invoke("name",{camelCaseArgs})`. The **`#surface-settings` panel is already routed** (`index.html:930`, `app.js:1108`) but is a stub ("Application settings arrive later."). Operator-local commands return operator-local JSON (NOT the LAN-shared `OperatorView`) to keep the pinned cross-language wire fixtures untouched.
- **On-device STT support exists:** `selahcue_stt::{model_readiness, verify_model, WhisperModel::asset, HardwareProbe}` for readiness/integrity; `audio::default_input_info()` for mic presence.

## Inputs and evidence sources

- Figma reference frame `338:124` (Settings — Providers & Privacy), file `SYQn5hFY8YVQKm3c6rw0eJ`; screenshots in scratchpad.
- docs/product/prds/SelahCue-PRD.md — FR-101, FR-131, FR-132, FR-134, FR-135, FR-137, FR-153, FR-156, FR-158, FR-177; NFR-018; CON-5.
- docs/decisions/DECISION-LOG.md — DEC-001 (TTS removed → TTS section excluded).
- docs/design/SETTINGS-2.0-HANDOFF.md — cross-page reconciliations (keys live only here; consent/retention Administrator-gated).
- Backend investigation report (this session): keys.rs, transcript.rs, migrations.rs, saved_theme_repo.rs, operator/src/main.rs command pattern, selahcue-stt model API.
- ClickUp epic 86ajp08py; design story 86ajxucue.

## Scope

### In scope

- **Domain (selahcue-core, pure):** `ProvidersSettings` (transcription provider selection, notes template, preferred translation, six include-in-notes flags), `ConsentState` (offline-by-default, per-provider cloud opt-in, Administrator-gated), `Quota` (used/limit/resets/remaining), a `NoteProvider` trait + `NoteRequest`/`NoteDraft`/`NoteOptions`, and pure consent-gating logic (`may_send_to_cloud` etc.). Deterministic, no I/O.
- **Persistence (selahcue-data):** one appended migration (v18→v19) + a `providers_repo` modeled on `saved_theme_repo` to save/load `ProvidersSettings` + `ConsentState`.
- **On-device transcription default:** wire the existing `selahcue-stt` path + readiness probe as the working default provider selection.
- **SelahCue cloud client (new crate `selahcue-cloud`):** a defined SelahCue cloud API contract (serde request/response types) for note-generation, cloud transcription, and quota; `SelahCueCloudClient` implementing `NoteProvider` over an injected `HttpTransport` seam; a deterministic in-process **mock transport** for tests; consent-gated so nothing is sent unless opt-in + explicit generate; graceful local fallback on transport error (FR-135). Real HTTP transport (reqwest) behind an off-by-default feature.
- **Account/session-token secret store:** a `SecretStore` trait with an in-memory test impl and a keyring-backed impl (reusing the keys.rs idiom) storing the SelahCue account/session token — never third-party keys; redacting `Debug`; `remove` purges; no token in logs.
- **Operator wiring:** `#[tauri::command]`s to read/write settings + consent, report provider readiness + quota, and run generation; registered in `generate_handler!` and callable from the webview; operator-local JSON replies (LAN wire fixtures untouched).
- **Tests:** persistence round-trip, consent-gating invariants, mock cloud integration (sent-only-completed-transcript / never-when-consent-off), graceful fallback, quota parsing, secret redaction, bounded-memory for any new buffer.

### Non-goals

- **TTS** — excluded (DEC-001). The reference frame's below-fold TTS section is flagged to design, not built.
- **BYOK / bring-your-own-key custom provider** — excluded per owner (hosted-only model). The frame's Advanced BYOK row is flagged to design, not built.
- **The live SelahCue hosted cloud service** (real endpoint, account/auth/entitlement, server-owned quota) — external infra owned elsewhere; tracked as a dependency. This goal delivers the client + mock, not the server.
- Frontend UI build — handed to /frontend-engineer as a linked follow-on (this backend exposes the commands it integrates against).
- Redesigning the reference frame or app shell; scripture-detection / R4 pipeline; retention *enforcement* jobs beyond persisting the setting.

### Constraints

- Offline-first: no audio/transcript/notes leave the host without an explicit per-provider opt-in (CON-5, FR-132, NFR-018); consent/retention are Administrator-gated (FR-137).
- Keep `selahcue-core` pure/deterministic (injected transport/clock; parser-style no-panic on untrusted input).
- Do not change the LAN wire protocol or its pinned cross-language fixtures (operator-local commands only).
- Memory bounded: no unbounded queues/caches/logs; new buffering gets a bounded-memory test.
- `cargo fmt --check` + `clippy -D warnings` must pass; CRLF-normalize newline-sensitive fixtures.
- Additive migration only (append v19; never edit an existing entry).

### Assumptions and unknowns

- ASSUMED: the SelahCue cloud API shape (note-generation request = completed transcript + options; response = structured note draft; a quota/entitlement endpoint) is defined by this goal as a stable contract for the real service to satisfy later. Owner: backend-engineer + product; recorded in `selahcue-cloud`.
- ASSUMED: the operator shell (not the encrypted desktop-output process) hosts these settings; it uses its own DB open path. Owner: backend-engineer.
- UNKNOWN: real SelahCue account/auth/entitlement model. Owner: product/infra. Client abstracts auth behind the token `SecretStore`; the live wiring is BLOCKED on that decision.

## Dependencies and approvals

- Live SelahCue hosted cloud service — owner: product/infra — status: DOES NOT EXIST (tracked dependency; client built against contract + mock).
- ClickUp MCP — status: connected (task 86ajy034h).
- Figma MCP — status: connected (reference frame read).
- Independent review (code-reviewer / security-reviewer) of consent-gating + secret handling — status: pending (required; not self-certified).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Core domain types + consent-gating invariants exist and are unit-tested (default = on-device, cloud OFF, offline-by-default true; `may_send_to_cloud` is false unless per-provider opt-in AND explicit generate) | `cargo test -p selahcue-core --test test_providers` | Exits 0; all tests pass incl. a test asserting no-send-without-opt-in and no-live-audio | selahcue-core/tests/test_providers.rs + output | PASS |
| C-002 | yes | Settings + consent persistence via one appended migration (v18→v19) + `providers_repo`, with a save/load round-trip test | `cargo test -p selahcue-data --test test_providers_repo` | Exits 0; round-trip preserves every field; `target_version()` bumped to 19 | selahcue-data/tests/test_providers_repo.rs + migrations.rs diff | PASS |
| C-003 | yes | `NoteProvider` + SelahCue cloud client over an injected transport, integration-tested against a deterministic mock: with opt-in + generate the mock receives only the completed transcript (never live audio) and returns a draft; with consent off no request is issued (ConsentRequired) | `cargo test -p selahcue-cloud` | Exits 0; both the sends-completed-transcript-only and never-sends-when-consent-off tests pass | selahcue-cloud/tests + output | PASS |
| C-004 | yes | Graceful local fallback (FR-135): a failing/unreachable cloud transport yields a degraded status and a local fallback path without panic or blocking | `cargo test -p selahcue-cloud --test test_fallback` | Exits 0; fallback test asserts no panic, degraded status surfaced, local path used | selahcue-cloud/tests/test_fallback.rs + output | PASS |
| C-005 | yes | SelahCue account/session token stored via a `SecretStore` (in-memory + keyring impls): get/set/remove round-trips, `Debug` is redacting, `remove` purges, and no token is logged | `cargo test -p selahcue-cloud --test test_secret_store` and `rg -n "token" implementation/desktop/crates/selahcue-cloud/src implementation/desktop/crates/selahcue-operator/src` | Test exits 0; grep shows no token value in any log/format string (redaction only) | test_secret_store.rs + grep output | PASS |
| C-006 | yes | Monthly quota (used/limit/resets/remaining) is modeled and surfaced from the provider/mock with a correct remaining calculation | `cargo test -p selahcue-cloud --test test_quota` (or core quota unit test) | Exits 0; remaining = limit − used; parse from mock response verified | quota test + output | PASS |
| C-007 | yes | Operator commands to read/write settings+consent, report provider readiness+quota, and generate exist, are registered in `generate_handler!`, and the operator crate compiles + headless webview check passes | `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` and `python3 scripts/operator_headless.py` | Both exit 0; new commands present in the handler list | operator/src/main.rs diff + command output | PASS |
| C-008 | yes | Full local CI gate is green after the change (fmt --check, clippy -D warnings, all suites incl. feature-gated, operator check, headless, flutter) | `make ci` | Exits 0 | make ci output captured to scratchpad | PASS |
| C-009 | yes | LAN cross-language wire fixtures are unchanged (settings kept operator-local) and any new buffering has a bounded-memory test | `cargo test -p selahcue-lan --features server` and review of new buffers | Exits 0; `wire_fixtures_are_stable_for_cross_language_clients` passes unchanged; bounded-memory test present if a buffer was added | selahcue-lan test output + test file | PASS |
| C-010 | yes | Independent review (code-reviewer + security-reviewer) confirms consent-gating, secret handling, and no data egress without opt-in, with no unresolved critical/high finding | code-reviewer + security-reviewer subagent review of the diff | Report returns no unresolved critical/high finding (or they are fixed and re-verified) | review report in ClickUp comment / handoff | PASS |
| C-011 | yes | ClickUp task 86ajy034h carries goal ID, engine, iteration limit, start + final evidence, and terminal state | Inspect task 86ajy034h comments | Start comment + final evidence comment present with links | ClickUp task 86ajy034h | PASS |
| C-012 | no | Frontend integrated: the Providers & Privacy panel renders against the backend commands (dispatched to /frontend-engineer) | /frontend-engineer handoff + headless render | Panel renders and round-trips a setting; or a linked follow-up task exists | frontend handoff / follow-up task | PENDING |
| C-013 | no | Goal Contract structural validator passes | `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-providers-privacy.md` | Exits 0 | validator output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-criterion `cargo test`/`cargo check` targets above, run and inspected (not just exit code — assert the specific behaviours, especially C-001/C-003/C-005 privacy invariants).
- Broader regression verification: `make ci` (C-008) as the full gate; explicit LAN wire-fixture stability (C-009).
- Independent verifier: code-reviewer + security-reviewer subagents review the consent-gating and secret handling (C-010); the implementing role does not self-certify C-010.
- Required environment: desktop Rust workspace + operator toolchain + Flutter (for `make ci`); Figma/ClickUp MCP for evidence.

## Iteration ledger

### Iteration 1

- Target criterion: setup (C-011, C-013)
- Hypothesis: a validated contract + registered ClickUp task are prerequisites to any implementation iteration.
- Change or investigation: full backend investigation; created task 86ajy034h under epic 86ajp08py; authored this contract.
- Verifier executed: python3 scripts/validate_goal_contract.py (PASS: 13 criteria, 11 mandatory)
- Result: PASS — contract validated; ClickUp start comment posted
- New evidence: task 86ajy034h; backend investigation report; reference-frame screenshots
- Decision: iterate

### Iteration 2 — core domain + egress gate (C-001)

- Target criterion: C-001
- Hypothesis: the privacy invariants belong in a pure, dependency-free core module with a single egress choke point, unit-testable without I/O.
- Change: added `selahcue-core/src/providers.rs` (`ProvidersConfig`/`ProvidersSettings`/`ConsentState`/`Quota`/`NoteProvider` + `may_stream_cloud_audio` + `build_note_request`, tolerant `from_kv`); tests in `tests/test_providers.rs`.
- Verifier executed: `cargo test -p selahcue-core --test test_providers`; `cargo clippy -p selahcue-core --all-targets`; `cargo fmt --check`.
- Result: PASS — 11 tests; clippy/fmt clean.
- New evidence: no-send-without-opt-in, no-live-audio-field, garbage-never-enables-cloud all asserted.
- Decision: iterate

### Iteration 3 — persistence (C-002)

- Target criterion: C-002
- Hypothesis: reuse the `saved_theme_repo` (key,value) replace-set pattern + an append-only migration keeps the data layer a dumb store and the core the source of defaults.
- Change: appended migration v18→v19 (`providers_setting`); added `selahcue-data/src/providers_repo.rs` (`save`/`load`); bumped `schema_version_is_pinned` to 19 and updated the 5 old-DB replay tests to drop the new table; tests in `tests/test_providers_repo.rs`.
- Verifier executed: `cargo test -p selahcue-data --test test_providers_repo --test test_db`.
- Result: PASS — 13 tests (3 repo + 10 db); empty store → safe defaults; consent-revocation clears the row.
- Decision: iterate

### Iteration 4 — SelahCue cloud client + mock + fallback + secret store + quota (C-003..C-006)

- Target criteria: C-003, C-004, C-005, C-006
- Hypothesis: an injected `HttpTransport` seam + a deterministic mock makes the client fully testable offline; the live service is a config change, not a code change.
- Change: new workspace crate `selahcue-cloud` — versioned API `contract`, `SelahCueCloudClient` (`NoteProvider`/`CloudNoteProvider`) over `HttpTransport`, `MockTransport`, `LocalNoteProvider` fallback, `SecretStore`/`Token` (redacting), `generate_sermon_notes` orchestrator (Transport→fallback; QuotaExceeded/NotConfigured propagate). reqwest/keyring behind off-by-default features.
- Verifier executed: `cargo test -p selahcue-cloud`; `cargo clippy -p selahcue-cloud --all-targets --all-features`; token-leak grep.
- Result: PASS — 12 tests; feature-gated build clean; no token value logged.
- Decision: iterate

### Iteration 5 — operator wiring (C-007)

- Target criterion: C-007
- Hypothesis: add operator-local Tauri commands (own JSON replies) + persist via `providers_repo`, keeping the LAN wire untouched; leave `dist` unchanged so the headless gate stays green (UI is the frontend-engineer's task).
- Change: added `selahcue-cloud` dep + `cloud-live` feature; `AppState` gains `providers`/`providers_db`/`secrets`; 9 commands (`providers_view`, `set_transcription_mode`, `set_cloud_consent`, `set_notes_template`, `set_preferred_translation`, `set_include_flag`, `set_account_token`, `clear_account_token`, `generate_sermon_notes`) registered in `generate_handler!`.
- Verifier executed: `cargo check --manifest-path .../selahcue-operator/Cargo.toml`; `cargo clippy` (operator); `python3 scripts/operator_headless.py`.
- Result: PASS — compiles clean; headless 427 checks / 0 FAIL.
- Decision: iterate

### Iteration 6 — full gate + wire stability (C-008, C-009) + independent review (C-010)

- Target criteria: C-008, C-009, C-010
- Change: ran `cargo test -p selahcue-lan --features server --test test_protocol` (C-009); ran `make ci` (C-008 — first run failed on `cargo fmt --check` for an unformatted `providers_repo.rs`; fixed with `cargo fmt` and re-ran); launched two independent reviewers (security + correctness) for C-010.
- Verifier executed: LAN wire fixtures test; `make ci`; reviewer subagents.
- Result: C-009 PASS (23 LAN tests; `wire_fixtures_are_stable_for_cross_language_clients` unchanged). C-008 re-run + C-010 in progress.
- New evidence: correctness review returned no live bug; one test-quality gap (M1: assert 0 requests through the orchestrator) to fix.
- Decision: iterate (apply review fixes, then re-verify)

### Iteration 7 — review fixes + final gate (C-008, C-010)

- Target criteria: C-010 findings, then re-confirm C-008.
- Change: (1) [MEDIUM] consent-gated `fetch_quota(&ConsentState)` — refuses + 0 requests without cloud-notes consent; (2) [M1] `consent_off_generates_nothing_and_issues_zero_requests` proves 0 requests through the full orchestrator; (3) [LOW] `MockTransport` recovers a poisoned lock (no panic); (4) [LOW] `LocalNoteProvider` bounded collect; (5) [LOW] empty account token purges the keychain entry.
- Verifier executed: `cargo test -p selahcue-cloud` (14 tests); `cargo clippy -p selahcue-cloud --all-targets --all-features`; `make ci`.
- Result: PASS — 14 cloud tests; clippy clean; `make ci` == "local CI gate: ALL GREEN", exit 0.
- New evidence: `scratchpad/make_ci_final.log`; C-010 evidence comment on task 86ajy034h.
- Decision: complete (backend). Frontend (C-012) dispatched to /frontend-engineer as a follow-on.

## Risks and rollback

- Risks: (1) scope is large + multi-crate → mitigate by building/verifying crate-by-crate (core → data → cloud → operator) so each criterion is independently real. (2) Cloud client without a live service → mitigate with the injected-transport seam + deterministic mock; live service tracked as a dependency. (3) Accidental data egress / secret leakage → mitigated as first-class privacy tests (C-001/C-003/C-005) + independent security review (C-010). (4) `make ci` breakage from fmt/clippy or wire fixtures → run gates incrementally; keep settings operator-local.
- Rollback or recovery: all changes are additive (new crate, appended migration, new commands); the migration is forward-only but the new table is isolated; revert is a clean crate/module removal. No existing frames or wire fixtures mutated.

## Pause and escalation conditions

- BLOCKED to product/infra if a criterion requires the live SelahCue service (real endpoint/auth/quota) — the client+mock path must not be faked as live end-to-end.
- Escalate to product if implementing any control would contradict a recorded decision (e.g. TTS/DEC-001 or BYOK) — flag, do not build.
- Stop after three materially different failed attempts on a criterion without new evidence; report the smallest unblocker.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-providers-privacy.md --require-complete
- Validator result: PASS (all 11 mandatory criteria PASS)
- Independent verification result: two independent reviewers (security + correctness) — no critical/high; one MEDIUM (un-gated `fetch_quota` egress) + minor findings fixed and re-verified; all 6 privacy invariants confirmed.
- Terminal state: VERIFIED_COMPLETE (backend). Non-mandatory C-012 (frontend UI) dispatched to /frontend-engineer; C-013 validator PASS.
- Remaining failed or blocked criteria: none mandatory. C-012 (frontend integration) PENDING — owned by /frontend-engineer.
- ClickUp final evidence comment: posted to task 86ajy034h; task moved to code review.
