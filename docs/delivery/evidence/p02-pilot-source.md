# P02 native pilot credential source

Ticket: https://app.clickup.com/t/17tnw2bbhw1. Accountable role: Nova.
Source baseline: `3f651d143ad73de262cab1d74c6fb577b73adf5a`. Final review base: `cbc1e541f66f4f99fae0591733e2497a670b9fbd`.

After source checks, rebased onto main PR325. Verified that integration changed no Rust files, Cargo manifests/locks or Makefile; P02 source is unchanged by rebase. The feature/release guard and diff checks passed again after integration. PR325 adds Linux packaging controls/configuration and owns their separate runtime evidence; this does not turn P02 into installer or provider-account proof.

Implementation uses synthetic fixtures only. Actual provider scopes, expiry, model permission and revocation-owner proof (P01), scanner exception (P04), P03 active-session cutoff, packaging/runtime QA, signing and publishing remain separate release gates. No installer readiness claim or real credential use follows from these tests.

## Source contract

`pilot-credentials` is explicit and off by default in the operator. It reuses provider libraries and request routes, without enabling `dev-keys`, `openai-notes` or `cloud-stt`. All three existing developer features remain RELEASE UNSAFE and their environment guards remain unchanged. Ordinary builds do not use the pilot input, even if its build-path variable exists. Pilot builds never fall back to developer environment, including when the package configuration is absent, malformed or expired.

The build script accepts **only** the build-time `SELAHCUE_PILOT_CONFIG_PATH` path to a generated UTF-8 JSON file. It performs a bounded read, copies the file to native `OUT_DIR`, and embeds it through Rust `include_str!`. Runtime needs no file, dotenv or shell export. This is extraction-prone native embedding, with provider-side expiry as the authority; it is not secure against an installer recipient extracting the key or changing the client clock. Real inputs must remain outside source control, frontend assets, IPC, test reports and routine caches/artifact uploads. The build directory and native binary necessarily contain this payload and must fall under P04's scoped policy before any real use. No workflow or cache policy is changed here.

Schema 1 has required fields: `schema` (integer 1), `cohort` (nonempty ASCII identifier, max 128 bytes), `cutoff` (Unix UTC seconds, exactly `1809129599`), and `openai` / `deepgram` objects. Each provider requires `key`, `expires_at` (actual provider-returned Unix UTC seconds), and `model`. Extra fields, missing fields, wrong types, unsafe strings, oversized input or any expiry beyond the cohort cutoff are unavailable. OpenAI model must be an approved identifier supplied by issuance configuration; P01 verifies actual account/model permission. Deepgram is fixed to the current production route's `nova-3`. No provider endpoint is configurable through the pilot payload.

Cutoff is **2027-04-30T23:59:59Z**, not a duration from installation. Both sources become unavailable at the earliest provider or cohort expiry (`now < min(cutoff, openai.expires_at, deepgram.expires_at)`). New OpenAI generation/regeneration and Deepgram worker construction recheck time and reject at equality. Invalid system time before the Unix epoch is unavailable. A client clock rolled backwards cannot be made authoritative; external provider expiry remains mandatory. Already running requests/sockets, reconnect/session shutdown and operator expiry presentation are P03; this unit does not claim to terminate them.

`provider_source` is the shared operator selector: OpenAI descriptor plus both request paths, Deepgram readiness plus worker credential all consume it. Secret-bearing parsed types implement neither Debug/Display nor serialization. Errors discard parser details. Deepgram reuses its redacted Credential and Token authorization. OpenAI reuses the redacted Token and Responses constructor. Pilot readiness discloses a pilot source and does not direct the user to `.env`. Existing consent, license/entitlement and explicit completed-transcript Generate entry points are retained.

## Verification ledger

- RED: first release `test_pilot` run failed solely on missing `selahcue_cloud::pilot` API after correcting the test transport name. Mutation controls also caught allowing construction at expiry equality and removing the actual input size cap; source was restored and full cloud release regression rerun.
- GREEN: initial 3 release source tests passed (absent/malformed/schema, earlier expiry equality, safe fields/expiry extension). Expanded matrix adds fixed cutoff before/at/after, either provider earlier expiry, required/unknown fields and size bounds.
- `python3 scripts/check_launch_reachability.py`: passed; confirms existing three UNSAFE features still match actual Make release guards.
- Full cloud release suite (`--features openai --no-fail-fast --offline`): exit 0; 101 passed, 0 failed, 0 ignored across 20 binaries.
- Full Deepgram release suite (`--features deepgram --no-fail-fast --offline`): exit 0; 93 passed, 0 failed, 0 ignored across 13 binaries. Strict release clippy of both changed provider crates and all targets passed with warnings denied. Operator source matrix: absent, valid, malformed and expired generated configurations each passed 3 release tests with ordinary synthetic provider/model environment overrides present. After the final diagnostic-only correction, the full expired-pilot suite and valid positive-control build passed again. Pilot and developer-route operator strict release clippy passed with all targets and warnings denied.
- Full ordinary operator release suite: 455 passed, zero failed, one ignored child-process entry (exercised by its parent). Full pilot operator release suite: 476 passed, zero failed, two ignored entries (the child-process entry and explicit real ~1.6GB model load/hash test).
- Full `make ci`, cross-platform installer/runtime and real provider account checks: not executed here; root coordinates broader gates.
- Root owns ClickUp browser updates; no remote task mutation claimed.

## Reproduce the synthetic source matrix

The three `selahcue-operator/tests/fixtures/pilot-*.json` files contain explicitly synthetic credentials and are not deployable package configuration. Export synthetic ordinary `OPENAI_API_KEY`, `DEEPGRAM_API_KEY` and `SELAHCUE_OPENAI_MODEL` values to check that they are ignored. For each case, run:

```
cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --features pilot-credentials --release --test test_pilot_source --offline
```

Use `PILOT_TEST_EXPECT_READY=0` with `SELAHCUE_PILOT_CONFIG_PATH` unset for absent input. Set the build path to the absolute `pilot-valid.json` fixture and `PILOT_TEST_EXPECT_READY=1` for the valid case; malformed/expired fixtures require expectation `0`. The expectation variable is read only by the test harness. Production selection never consults it. No configuration file or ordinary provider environment is needed by the installed executable; the source is compiled native payload. `make stage-operator-binaries` supplies compile-only placeholders in a fresh worktree; those are not an output sidecar or installer acceptance.


## Remaining integration boundaries

P02 blocks new construction at the source deadline. P03 must enforce running-stream/transport deadlines and refuse late OpenAI results before persistence; dropping a blocking worker handle or relying on provider WebSocket key expiry does not establish active-session cancellation. Operator expiry/fallback presentation remains P03.

P04's read-only audit found that this native `include_str!` JSON does not yet carry a uniquely bounded payload designation. A future narrow exception requires a verified envelope/section and an all-occurrence matcher, with the ordinary scanner left intact. No real credential may be embedded using a broad exception. This ticket changes no scanner policy, cache policy or CI enablement. Any later packaging remains manual `workflow_dispatch` on exact `main` only.
