# P03 pilot expiry evidence — 17tnw2bbhwt

Implementation scope: one shared native/UI unit on `codex/17tnw2bbhwt-pilot-expiry`. Accountable Farah; native/AI transport owner Nova. This is synthetic source/runtime evidence. Independent Cody, Shadow, Quinn and Vera verdicts and current hosted CI remain pending at this snapshot. Root owns ClickUp and merge.

## Behavior and boundaries

The fixed cohort ceiling remains **2027-04-30T23:59:59Z** (`1809129599`), shortened by the earliest actual provider metadata. Admission captures the smaller wall/monotonic remaining budget. Clones/retries cannot renew it; expiry/invalid-clock retirement is shared and sticky within the process. New process admission uses the same absolute configured expiry. This is not tamper-proof trusted time across a user-controlled system clock or a protected hardware clock claim.

The native status is ordinary `null`, or exactly six safe fields: `state`, `notes_state`, `transcription_state`, `notes_uses_pilot`, `effective_expiry_unix_seconds`, `replacement_required`. States are available/expired/rejected/unavailable. Rejection latches its provider lane; a shared expiry retires applicable pilot lanes. A captured configured hosted route keeps its normal deadline/errors and is explicitly inapplicable to pilot notes restrictions. Status and request selection use the same helper. Missing/malformed UI applicability fails notes closed. No raw response, credential or parser diagnostic crosses this contract.

OpenAI uses an actual deadline-bound async HTTP head/body exchange inside its blocking adapter. The admitted budget covers both head and body; 20ms clock checks cancel the owned future and private runtime. Response cap remains 4MiB, no redirects, production HTTPS. 401/403 are observed without awaiting or exposing their body. A resolver may finish separately after runtime shutdown; it has no credential/request continuation. Deepgram wraps the actual connect/retry/backoff/pump future, closes without courtesy audio flush at expiry, discards unsent cloud audio and joins the worker. Local fallback receives the same capture source; completed transcript queue is retained. No model is downloaded or claimed available.

Generated notes are checked after provider completion, after awaited existing-draft load and after mutation mutex/readiness waits. Generated-only guards run inside local controller admission and after remote backend mutex acquisition, then recheck after socket readiness before `start_send`. Aria/root explicitly permit a save/stage **admitted before expiry** to finish/commit later. No new host/wire deadline is introduced and an already admitted shared LAN exchange is not cancelled. Manual edit/update behavior retains its existing route.

Consent/licence checks remain in place; credentials do not confer consent. Ordinary release still has no developer environment privilege; dev loaders and RELEASE_UNSAFE classifications remain unchanged. Production never consults the test epoch variable. Tests scan the actual non-test executable for that hook's name.

## Native verification

All commands use synthetic fixture credentials and mocks/loopback only. Retained idle P02 build caches are reused without cleaning; dependency lockfiles only add the existing Tokio package as a direct cloud dependency, no package upgrades.

- Affected release regression command: `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-core -p selahcue-cloud -p selahcue-stt-cloud -p selahcue-lan -p selahcue-app --features http,openai,deepgram,server --release --no-fail-fast --offline`. Log `/private/tmp/p03-native-regressions.log`: 93 successful target summaries/1106 passing tests, plus one failing source redaction guard target. The guard found new match-arm placement outside its expected parser wrapper. Each arm now explicitly goes through the parser, scanner additionally recognizes guarded commands, and hostile reply coverage includes both new methods. Focused correction: `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-app --features server --test test_no_debug_dump_in_errors --test test_operator_reply_redaction --release --offline`: **6 + 4 pass**, `/private/tmp/p03-redaction.log`. Historical failed run is not counted as a fully green suite.
- Core deadline: **3 pass**, exact equality, monotonic rollback, forward wall jump, invalid clock, shared sticky retirement and fresh absolute admission.
- Real HTTP: **3 pass**, stalled head/partial body socket EOF within the declared deadline +500ms allowance (120ms admission); forward jump cancels in-flight I/O; pre-expired admission opens no socket; rejection drops raw body.
- Real Deepgram worker: **6 pass**, stalled handshake, active stream/no courtesy flush/no reconnect, retry-backoff cutoff, pre-expired zero sockets, rejection redaction, sustained audio with unread-peer backpressure. Last case sends real audio, observes bounded ring drops and real worker join; 500ms admission, server intentionally unread until700ms, close/join asserted within1000ms total. No detached worker is treated as success.
- Real LAN readiness: **1 pass**, held Sink prevents actual `start_send` after expiry; positive control sends once. Existing client timeout/poison and redaction tests also run in the affected suite.
- Earlier integrated operator release run `/private/tmp/p03-operator-tests.log`: **483 pass,2 ignored** in bin plus eight integration assertions (491 total pass). Ignored tests are a child-process helper exercised by its parent and an existing real-model fixture requiring a1.6GB model. This predates final test-clock/lint wiring; final focused CI results below supersede affected pilot paths.
- New actual operator controls preserve accepted draft, stage count and byte-identical visible scripture output after a late result or expiry during draft load; reject mutation after a real remote backend mutex wait; preserve capture for same-source local fallback before any further audio push; and keep captured configured hosted routes usable after pilot expiry.

## Automatic pilot gate

One step is added to existing `operator-native`, with no job/matrix/timeout/installer/secrets change. It uses committed `tests/fixtures/pilot-valid.json` and test-only synthetic epoch `1809125999` (before), `1809129599` (equality), `1809129600` (after). No fixture rebuild is needed between epochs. `SELAHCUE_PILOT_TEST_EPOCH` is consulted only under `cfg(test)`; all normal production time reads remain native UTC/monotonic. Test AppState secret-store construction uses in-memory storage only under `cfg(test)`; production keyring defaults and explicit library secret-store tests are unchanged.

Exact step commands (operator crate cwd, `--features pilot-credentials,cloud-live` on each):

```sh
cargo clippy --release --features pilot-credentials,cloud-live --all-targets -- -D warnings
cargo test --release --features pilot-credentials,cloud-live --bin selahcue-operator --no-fail-fast pilot_
cargo test --release --features pilot-credentials,cloud-live --test test_pilot_source --test test_pilot_note_rejection --test test_pilot_stt_rejection --no-fail-fast
# equality epoch, READY=0, MIXED_EXPECT_EXPIRED=1
cargo test --release --features pilot-credentials,cloud-live --bin selahcue-operator --no-fail-fast pilot_mixed_tests
cargo test --release --features pilot-credentials,cloud-live --test test_pilot_source --no-fail-fast
# after epoch
cargo test --release --features pilot-credentials,cloud-live --test test_pilot_source --no-fail-fast
```

Each phase asserts a nonzero passing count and exact required control names in Cargo output, so a feature/filter typo cannot silently pass. Existing CI already reaches core/LAN/app, cloud HTTP and Deepgram library tests; no duplicate suite is added. Workflow inventory **6 workflows/19 jobs**, minute rules and actionlint pass. Workspace and operator rustfmt checks and `git diff --check` pass. Final local exact-step result: **PASS**, `/private/tmp/p03-exact-ci.log`: required-name/nonzero counts **5 before-bin +9 before-source/rejection +1 mixed-hosted at equality +5 source at equality +5 source after =25 passing test executions**. Equality/after use the same committed fixture and source executable; after-cutoff phase reports a1.24s cached finish. A disjoint main rebase during the run refreshed source mtimes and caused one intermediate rebuild; source bytes did not change. Operator strict release clippy and affected-library strict release clippy both pass.

## UI/runtime provenance

Farah UI commit `7533f9e5499e628aeeff5e56931f94666d30528b`: **20 focused Node tests pass**, full supported headless harness **2906 checks/0 failures**. Exact logs/provenance: `/private/tmp/farah-p03-ui/ui-evidence.md`, `fixture-provenance.json`, `node-final-verified.log`, `operator-headless-seven-field.log` (historical filename; actual schema has six fields). The initial environment SIGABRT and later three busy-Generate failures were corrected; final successful run is the evidence. A copied `>=`→`>` boundary mutation makes the real headless runner's Node gate fail before Chrome.

Root CUA used the actual UI module bytes with explicitly mocked native IPC: available UTC cutoff→automatic expired recovery/both pilot lanes disabled on the same page, rejected lane with healthy other lane, saved draft/Edit and offline/emergency controls retained, missing local model truthful. Screenshots under `/private/tmp/selahcue-continuation-20261031/`: `p03-ui-rejected.png`, `p03-ui-available-before.png`, `p03-ui-expired-after.png` and text capture. Fixture reload creates a new synthetic fixture admission; it is **not native restart proof**. Native restart policy is covered by absolute-admission tests. DOM/CUA fixtures do not prove a packaged installer, real provider/account policy, physical display or field-location behavior. Actual native socket/mutex/store/frame evidence is separate and identified above.

## Remaining gates

P03 still requires four independent reviews at the frozen whole-unit head, current CI, root acceptance of the combined runtime evidence and root merge. P01 actual provider account/scope/expiry/revoke-owner proof and P04 uniquely bounded scanner payload designation/all-occurrence policy remain mandatory before real credential embedding/packaging. No real keys, .env, provider calls, installer, publication or deployment are part of this evidence.

## Revision attribution

Initial native/source checkpoint `95ddd90eb71a1a9045d1601f1043c367639094a4` is based on main `4e2ce4374713956a498978fdf6383c74c2c548cb`. Main delta from a2ed7f96 is API/deployments/docs/mobile only; audited zero desktop/Cargo/UI/shared-workflow changes. Rebased UI commit `fe01ac8e87e5a4bbca86198a419b3fb4e0b72e6d` retains the exact original7533f9e UI bytes. Whole `implementation/desktop` tree fingerprint: `80243a513cc91021f09e33023b30f813b308462f`. Subsequent evidence-only updates do not alter that source fingerprint.

Root authorized a separate short-expiry native macOS smoke build from these exact frozen bytes, without cloud-live/dev-keys, real providers or production test-clock hooks. Build-only Tauri identifier/window-title overrides and synthetic provider expiries keep the cohort ceiling unchanged. Root's launcher sandbox deny probes pass; native launch/CUA is still pending. C004 is not satisfied by mock IPC alone. No installer/package is produced.
