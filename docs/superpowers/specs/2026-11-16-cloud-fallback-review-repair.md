# PR398 cloud fallback review repair design

Status: Accepted by the root coordinator for the already-authorized repair workflow after full design/plan/report review. This is a technical ruling, not new user product approval. Runtime results remain UNRUN.

Work item: [17tnw2b9b8u](https://app.clickup.com/t/17tnw2b9b8u). PR: [398](https://github.com/First-Pavilion/selahcue/pull/398). Existing contract: `docs/delivery/goals/17tnw2b9b8u-cloud-note-construction-fallback.md`. This is repair evidence for that ticket, not a new backlog.

## Intent and baseline

Preserve the already-approved construction-failure fallback for synchronous Hosted and Direct notes while fixing every consolidated review finding. The repair starts at `11eb869c8bd51bf2070cc74e071e7365341e1cc5` and integrates target `256035f16c996fde6cd7e56849920f451e4bf033`, preserving both ancestries. Worktree: `/private/tmp/selahcue-cloud-fallback-fix-20261116`, branch `codex/cloud-fallback-review-repair-20261116`.

Verified by source inspection: the source adds fixed transport error classification, while target adds `ReqwestTransport::new_with_response_limit` and a per-instance bounded read. Both GET and POST overlap. Source Chrome still pins 2997 despite two added counted assertions. Existing CI selects cloud `http` and `openai` separately and never explicitly selects the Hosted save/stage fixture. The ready-pilot parent returns early without `PILOT_TEST_EXPECT_READY=1`.

## Approaches and decision

1. Take either transport side wholesale: rejected; it loses either fixed classification or the native-account response cap/API.
2. Add new CI jobs or rewrite fallback architecture: rejected; it broadens a repair and duplicates established verification infrastructure.
3. Merge both histories, compose the two transport hunks, select existing behavioral tests in existing jobs, then measure and repair Chrome's exact-count pin: chosen by parent technical direction. This keeps deployment, errors, storage and provider policy unchanged.

## Required behavior and invariants

- GET and POST use the source's `reqwest_transport_error(&e, HttpFailurePhase::Send)` classifier and target's `read_bounded(resp, self.max_response_bytes)`; build errors retain fixed classification too.
- Keep `new_with_response_limit(max_bytes: usize) -> Result<Self, TransportError>`, its validation `1..=MAX_TRANSPORT_RESPONSE_BYTES`, field initialization, default 4 MiB ceiling and native account's 64 KiB cap. Keep the separate body-read deadline.
- Consent and configuration refusal precede construction; terminal `NoteError` variants remain terminal. One admitted factory invocation and one shared Transport-only fallback remain the contract.
- HTTPS verification, OS trust, redirect refusal, pilot deadlines/sticky rejection and the eight-node fixed diagnostic classifier remain intact. Added notice copy stays at most 160 bytes and uses plain-text rendering; no raw diagnostic or credential disclosure.
- Authoritative draft-read failure or denied consent yields zero construction/writes. First fallback saves; regeneration stages without replacing an accepted edit; promotion remains explicit. Pilot admission rechecks after work and backend-lock waits protect both accepted and pending data. Hosted remains independent of pilot cutoff.

## Verification architecture

Exactly two implementation tasks: (1) current-target composition and missing CI selections, retaining Chrome 2997, then capture the owning hosted Chrome RED; (2) update the pin only from that observed total, rerun qualification/full hosted CI and independent review.

Existing behavioral tests are the tests-first checkpoints. Do not add configuration-mirroring tests. Do not assume the observed Chrome count is 2999. Both new named assertions, the reported total and zero assertion failures must be visible before an exact-count-only failure supports the pin update.

Required selections:

- Existing Linux `rust` job: debug `cargo test -p selahcue-cloud --features http,openai --test test_tls_system_store_linux --no-fail-fast`. Pin `the_system_store_decides_who_is_trusted_and_an_empty_one_fails_closed`; its children cover empty/trusted roots and missing/blank developer keys. Release refusal alone cannot establish missing-key precedence.
- Existing `operator` job: debug `cloud-live` exact Hosted construction fixture.
- Existing `operator-native` job: `pilot-credentials,cloud-live` release exact Hosted construction fixture at cutoff, plus ready-pilot parent and all six explicit child cases. Use committed `tests/fixtures/pilot-valid.json`; ready epoch `1809125999`, cutoff `1809129599`.
- Preserve cloud default/http/openai debug/release, developer `openai-notes`, ready/cutoff pilot source checks, TLS acceptance/refusal, cap validation and real GET/POST overage, deadline/drip and remote mutex-refusal coverage.

### Workflow and preflight interactions

`.github/scripts/test_native_test_receipts.py` extracts the existing `Focused pilot expiry (release, synthetic only)` step, requires one inline Python parser, exactly five `run_pilot_tests` calls and seven total receipt cases. Keep that shape. Add `pilot_construction_fallback_preserves_terminal_policy` to `before-bin` required names, but put extra Hosted/explicit-child runs in separate steps within the existing jobs. Each exact selection must have a nonzero named outcome; child case labels/epochs and their individual `1 passed` receipts must survive in logs. No new jobs, matrices, dependencies or timeout changes.

Keep setup before gates and each new gate under existing `!cancelled()` policy. Preserve explicit UTF-8 receipt decoding and pipeline failure propagation. Reuse existing runner toolchains, Tauri placeholders, certificates and native dependencies. Local workflow checks need existing PyYAML; do not install tools under a resource hold merely to pass preflight. An unrelated earlier failure or cancelled run is not the required Chrome RED.

## Evidence and acceptance boundary

Parent ruling: full current-source hosted CI is source-merge verification while measured local pageouts/swapins persist. Original Goal C-005 local `make ci` remains **UNRUN**; hosted success does not change it to PASS. macOS/native release qualification remains separate. Keep historical billing failures as unexecuted attempts and report any hosted failures/skips honestly. Future Notes C qualification is out of scope.

| Review requirement | Proof required | Owner/task |
| --- | --- | --- |
| Both transport controls survive | Both ancestry checks, composed source, actual constructor-cap and GET/POST chunked tests, TLS controls | Implementer / 1 |
| Missing feature assertions run | Exact Linux combined-feature fixture; standalone Hosted; mixed cutoff Hosted; six pilot child receipts | Implementer / 1, qualification / 2 |
| Chrome count reflects actual suite | Owning hosted Chrome RED with both names and count; pin-only correction; same full suite GREEN | Implementer / 1 then 2 |
| Current behavior remains safe | Full required hosted checks on final source; Cody, Shadow, Quinn, Vera re-review the same revision | Parent / 2 |
| Delivery is auditable | Source/target/tree receipts, merge ancestry, exact ClickUp QA readback | Parent after gates |

No schema, storage ownership, API/wire payload, credentials, retry, dependency or deployment-topology change is planned. No provider calls, real secrets or `.env` access. Rollback is a reviewed revert; no data conversion/recovery task is introduced. If runtime failures require product-policy changes or unrelated repairs, report them to parent before widening this design.
