# Cloud Note Construction Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eligible, consented cloud HTTP initialization failures produce the existing local sermon-note draft with a short safe reason; consent, configuration and pilot policy remain terminal.

**Architecture:** Add a fallible provider factory to the shared generator, with one common admission/clamp/fallback implementation. Credential-aware constructors select credentials once before invoking the transport factory. Typed HTTP errors become fixed canonical messages, then a closed fallback category and fixed transient notice copy.

**Tech Stack:** Existing Rust, reqwest, rustls, SQLite fixtures and operator headless tests; no new dependencies.

**Spec:** `docs/delivery/goals/17tnw2b9b8u-cloud-note-construction-fallback.md`, `docs/superpowers/specs/2026-11-13-cloud-note-construction-fallback-design.md`, and [approved ticket17tnw2b9b8u](https://app.clickup.com/t/17tnw2b9b8u). Architecture inspected218e1414; execution starts at merged40661b4fde38f1e670bc8fde522c17b30bdb93a7, whose only additional source change bounds note timestamp reads and does not alter this factory boundary.

## Global Constraints

- Never initialize HTTP without both explicit Generate/consent and eligible configured credentials. Consent is checked first by shared generation; terminal configuration refusal is checked next by the provider factory.
- Preserve HTTPS-only endpoints, OS trust, ring, redirects refused, deadlines and feature boundaries. No additional credential/env reads to preflight a provider that will read them again.
- Preserve Hosted priority, captured base/token, and exemption from direct pilot policy. Do not consult pilot/developer credentials for Hosted.
- Preserve all existing pilot pre/post-generation and pre-save/stage guards, including lock waits. Concurrent expiry/rejection can invalidate fallback before persistence.
- `ConsentRequired`, `NotConfigured`, `QuotaExceeded` and `Malformed` remain terminal whether returned by a factory or request. Only `NoteError::Transport` reaches fallback.
- One common request clamp and fallback match; no lazy `HttpTransport` adapter, error sidechannel, fake provider or fallback duplication.
- Added reason copy is fixed plain text, at most 160 bytes; never display an original error, URL, path, bearer, provider body, certificate subject/SAN, transcript, Debug output or parsed substring.
- Immediate notice only. Keep accepted/pending behavior, local draft provenance and current JSON fields. No stored-note schema, history-reload, UI wire or source-sharing redesign.
- One ticket/PR. Root runs full local `make ci`, independent Cody/Shadow/Quinn/Vera review and re-review, then the already authorized delivery flow. Do not add Windows CI work.

## Review Focus

1. Missing/blank key, disabled consent or release refusal with an otherwise failing HTTP factory: terminal result and zero factory calls.
2. Factory `NotConfigured` versus factory `Transport`: same error enum, opposite outcomes; no conversion erases that distinction.
3. Pilot expires/rejects after credentials are selected or during construction/request: policy guards still win before save/stage; Hosted remains unaffected.
4. Unknown diagnostics containing TLS words, secrets or markup: generic notice; exact canonical categories produce only fixed copy.
5. Existing accepted draft plus construction fallback: pending replacement, accepted artifact untouched; first-generation fallback saves normally.

### Task 1: Implement and prove the single construction-fallback path

**Files and interfaces:**

Paths below are relative to `implementation/desktop/crates/` unless otherwise stated.

| File | Responsibility |
| --- | --- |
| `selahcue-cloud/src/lib.rs` | Factory API, single internal orchestration, outcome reason and shared success construction. |
| `selahcue-cloud/src/openai.rs` | One-time developer credential/model selection before fallible transport construction. |
| `selahcue-cloud/src/pilot.rs` | Validated pilot credential/model selection before fallible transport construction. |
| `selahcue-cloud/src/transport.rs` | Closed reason type/canonical literals and bounded typed reqwest classifier; use for blocking build/send failures. |
| `selahcue-cloud/src/deadline_transport.rs` | Reuse classifier for async HTTP build/send failures; leave deadline/rejection/body policy intact. |
| `selahcue-operator/src/provider_source.rs` | Feature-specific fallible provider factory; preserve terminal transport-admission errors and canonical transport causes. |
| `selahcue-operator/src/main.rs` | Hosted/Direct call new generator; fixed degraded notice composition; command/persistence tests. |
| `selahcue-operator/src/sermon_note_caveats.rs` | Update existing `GenerationOutcome` fixture literal. |
| `selahcue-cloud/tests/test_fallback.rs` | Factory/request error parity, consent ordering, clamp and outcome invariants. |
| `selahcue-cloud/tests/test_tls_system_store_linux.rs` | Native Linux empty-root generation test in child process. |
| `selahcue-cloud/src/transport/tls_tests.rs` | Typed actual refusal, trusted positive control and safety assertions. |
| Existing OpenAI/pilot/operator tests; root `scripts/operator_headless.py` | Credential ordering, pilot guards, accepted/pending behavior, immediate plain-text notice. |

No new adapter module or core error variant is needed. Keep `TransportError(pub String)` and `NoteError::Transport(String)` unchanged.

### Shared generator

Retain `generate_sermon_notes(config, transcript, generate_pressed, &cloud, &local)` unchanged. Add:

```rust
pub fn generate_sermon_notes_with_factory<C, L, F>(
    config: &ProvidersConfig,
    transcript: &str,
    generate_pressed: bool,
    make_cloud: F,
    local: &L,
) -> Result<GenerationOutcome, NoteError>
where
    C: CloudNoteProvider,
    L: NoteProvider,
    F: FnOnce() -> Result<C, NoteError>;
```

Both APIs delegate to one private `generate_sermon_notes_with_attempt<L, F>` with the same first three arguments, `attempt: F`, and `local: &L`, where `F: FnOnce(&NoteRequest) -> Result<GenerationOutcome, NoteError>`. That helper alone builds the request, clamps it, invokes the attempt once, and matches success / `Transport` / other terminal errors. A private `cloud_outcome<C: CloudNoteProvider>(&C, &NoteRequest) -> Result<GenerationOutcome, NoteError>` owns successful cloud metadata. Existing borrowed API supplies `|req| cloud_outcome(cloud, req)`; factory API supplies `|req| make_cloud().and_then(|cloud| cloud_outcome(&cloud, req))`. There is no borrowed-provider blanket trait implementation or double consent/clamp.

Add `pub degraded_reason: Option<DegradedNoteReason>` to `GenerationOutcome`; set `None` on cloud success and `Some(from_transport_message(message))` only in the existing local fallback branch. Keep local draft label, quota=None and local provider generativity/disclosure semantics exactly as they are. Update both operator fixture literals explicitly.

### One-time credential selection

On `impl<T: HttpTransport> OpenAiNoteProvider<T>`, add:

```rust
pub fn from_env_with_transport<F>(build: F) -> Result<Self, NoteError>
where F: FnOnce() -> Result<T, NoteError>;
```

It checks release/debug permission before environment access, reads the key once, rejects missing/blank key as `NotConfigured`, selects the model once, then calls `build()?` and `new`. Retain `from_env(transport) -> Option<Self>` by delegating to `from_env_with_transport(|| Ok(transport)).ok()`. No extra readiness/key check in the caller. Model/key selection stays native and is never formatted or serialized. This constructor provides configuration ordering, not consent; shared generation provides consent.

On `PilotConfig`, add:

```rust
pub fn openai_with_transport<T, F>(
    &self, build: F, now: u64,
) -> Result<OpenAiNoteProvider<T>, NoteError>
where T: HttpTransport, F: FnOnce() -> Result<T, NoteError>;
```

Check `available(now)` before invoking the factory, select/clone the already validated key/model once, then build. Retain `openai(transport, now) -> Option<_>` as `self.openai_with_transport(|| Ok(transport), now).ok()`. No developer environment access in this path.

In operator `provider_source`, add the feature-gated:

```rust
pub fn openai_with_transport<T, F>(build: F)
    -> Result<selahcue_cloud::OpenAiNoteProvider<T>, NoteError>
where T: HttpTransport, F: FnOnce() -> Result<T, NoteError>;
```

Pilot arm checks `notes_fault()`, obtains existing `pilot()` and `now()` or returns `NotConfigured`, and calls the new pilot method. Developer arm calls the new `from_env_with_transport`. Keep existing `openai(transport) -> Option<_>` as a compatible wrapper if it has remaining callers. Leave `notes_transport() -> Result<NotesTransport, NoteError>` intact. Its pilot checks run again at actual transport admission; these are necessary clock/rejection checks, not secret re-resolution. Change only `pilot_notes_transport_with`'s build-error mapping from the generic discarded cause to `NoteError::Transport(e.to_string())`, so typed canonical TLS information survives. Its `NotConfigured` exits remain unchanged.

In `run_note_generation`, Direct supplies `|| provider_source::openai_with_transport(provider_source::notes_transport)` to shared factory generation. Hosted supplies a closure that builds ReqwestTransport, maps its error to `NoteError::Transport`, and constructs the cloud client using the captured eligible base/token. Hosted must not re-read the secret store. Offline keeps consent then `NotConfigured`. Remove the Direct duplicate `cfg.build_note_request` branch made unnecessary by the shared factory entry point. Preserve outer command consent, authoritative draft read, route capture and policy guards.

### Safe reason contract

Define and re-export `DegradedNoteReason` from `transport.rs` (always compiled): `TransportUnavailable`, `ClientSetupFailed`, `NoTrustedCertificates`, `CertificateRejected`. Derive Copy/Clone/Debug/PartialEq/Eq; no serialization needed. Define `canonical_message(self) -> &'static str`, `from_transport_message(&str) -> Self`, and `notice_reason(self) -> Option<&'static str>` with this exact closed mapping:

| Variant | Canonical TransportError inner string | Added notice reason |
| --- | --- | --- |
| TransportUnavailable | `cloud transport unavailable` | None; keep existing generic unavailable notice |
| ClientSetupFailed | `cloud HTTP client setup failed` | `The cloud connection could not be initialized.` |
| NoTrustedCertificates | `cloud TLS trust store empty` | `No trusted certificates could be loaded from this computer.` |
| CertificateRejected | `cloud TLS certificate rejected` | `The cloud service's TLS certificate was rejected.` |

`from_transport_message` matches complete exact canonical strings, with every other string mapped to TransportUnavailable. It never renders or extracts source text. These strings are compatibility carriers, not security credentials: a synthetic error can imitate a category, but can only select fixed harmless copy and cannot change admission or error class.

Under `http`, define `pub(crate) enum HttpFailurePhase { Build, Send }` and `pub(crate) fn reqwest_transport_error(error: &reqwest::Error, phase: HttpFailurePhase) -> TransportError`. It uses a private bounded classifier accepting `&(dyn std::error::Error + 'static)` so tests can supply typed chains. Inspect at most eight nodes including the root. At each node, inspect typed `rustls::Error`; then use `std::io::Error::get_ref()` if present, otherwise `source()`, to avoid skipping the wrapped rustls error. Never call Display/Debug on the chain.

- `rustls::Error::InvalidCertificate(_)` => CertificateRejected, discard all certificate metadata.
- `rustls::Error::General(s)` with exact equality to locked platform-verifier literal `No CA certificates were loaded from the system` => NoTrustedCertificates.
- Otherwise => ClientSetupFailed for Build, TransportUnavailable for Send. Do not label every constructor error TLS-specific.

Replace blocking build/send use of `describe_build_error`/`describe_send_error` with this classifier; remove the now-unused raw cause formatter and update assertions that expected raw certificate/URL text. Reuse the same classifier in DeadlineTransport build and `request.send()` failure mapping. Keep response-body, deadline, rejection and runtime-build handling unchanged and generic. This intentionally reduces raw diagnostics for all consumers of these two transport methods; it avoids an additional secret-bearing channel and makes reasons consistent. Provider status mapping remains untouched.

Operator composes its existing notice plus `notice_reason()` using fixed literals only. Render through existing textContent path; no new frontend field. Unknown errors keep the current generic copy. Do not reuse `disclosure` for failure reasons.

## Implementation steps

- [x] **Step 1: Write shared-generator tests.** Add `factory_transport_failure_degrades`, `factory_terminal_errors_propagate`, `denied_consent_never_calls_factory`, `generate_not_pressed_never_calls_factory`, and `factory_and_borrowed_paths_share_request_bound`. Assert one factory call when admitted, zero provider request on failed construction, one local call only on Transport, same capped transcript for request/fallback, exact terminal variant preserved, quota/provenance/disclosure unchanged and reason Some only on fallback. Exercise every terminal NoteError variant from both factory and request.
- [ ] **Step 2: Observe red and implement shared interfaces.** Run `cargo test -p selahcue-cloud --test test_fallback` in `implementation/desktop`; retain the failing baseline, then implement the shared interfaces and rerun to green. Update all GenerationOutcome literals found by a repository search.
- [ ] **Step 3: Pin and implement credential ordering.** Add tests for absent/blank developer key, release/profile refusal, valid key with build failure, unavailable/expired pilot, and injected `notes_transport` returning NotConfigured after initial admission. Assert factory counts; environment cases run in isolated child processes, never mutating shared test-runner credentials. New fallible and old constructor results must agree. Add the credential constructors and wire both routes only after these tests demonstrate the early-return problem.
- [ ] **Step 4: Pin and implement reason propagation.** Test typed InvalidCertificate, exact typed no-roots General, unknown General and arbitrary TLS-looking strings; test io wrapping and eight-node cutoff. Then add fixed messages/classifier and both transport mappings. Actual existing loopback TLS fixture must produce CertificateRejected through shared generation with no HTTP request bytes; a trusted positive control must succeed. Test forged URLs/userinfo/query, bearer, transcript, certificate metadata, control characters and markup against absence from canonical error and immediate notice. Exact harmless canonical matches are permitted; substrings must remain generic.
- [ ] **Step 5: Verify real Linux construction fallback.** Extend existing `test_tls_system_store_linux` child harness: empty temporary SSL_CERT_FILE and separate empty SSL_CERT_DIR, isolated proxy configuration, consent plus configured synthetic provider, actual ReqwestTransport::new invoked through shared factory => local draft and NoTrustedCertificates. Existing trusted-root positive and unknown-root negative controls remain. Add missing/blank-key cases under `http,openai` with the same broken trust environment and zero-construction spy. Native operator integration fixtures separately prove command/persistence behavior; a direct cloud test does not alone prove IPC/save. Run in existing Linux Docker only after resource admission; macOS execution/skips and cross compilation are not Linux evidence.
- [ ] **Step 6: Verify command and policy behavior.** Extend file-backed completed-transcript command fixtures to use the production factory wiring with an injectable HTTP builder (not a closure returning a fabricated GenerationOutcome). Assert first fallback saves; accepted draft fallback stages pending; consent/draft-read failure stops construction. Exercise pilot failure before build, during failed build, post-generation and save lock wait; terminal pilot response wins and neither save nor stage occurs. Existing captured Hosted + expired pilot remains successful/unaffected. Keep actual deadline request/rejection regression tests.
- [ ] **Step 7: Verify immediate UI copy.** Extend operator headless fixture with fixed certificate notice, assert rendered textContent and generic unknown-reason fallback. Test added strings <=160 bytes and no injected markup/credentials. This proves UI wiring separately from the real TLS refusal fixture; do not label a synthetic browser response a live TLS end-to-end test.
- [ ] **Step 8: Run final focused matrix and deliver.** Sequentially run cloud default, `--features http` and `--features http,openai`; operator manifest with `--features openai-notes`, `cloud-live`, then `pilot-credentials,cloud-live` using existing synthetic pilot fixture/clock. Use the repository's existing headless invocation. Run the native Linux trust fixture explicitly with `cargo test -p selahcue-cloud --features http,openai --test test_tls_system_store_linux` inside Linux. Capture feature/platform/results and blocked/skipped work distinctly. Root then runs full `make ci`, reviews/re-reviews and delivery; architecture documents alone claim none of these checks passed.

## Deployment, rollback and evidence

No migrations, new services, retries, caches, background work, request count or quota changes. The factory is synchronous and called once inside the existing blocking worker; the transient reason is not stored. No secret data receives a new owner/lifetime beyond the existing provider. Deadline checks continue to govern request time and persistence admission. Rollback is the ticket PR revert, with no data conversion. Resource/latency risk is limited to O(8) error inspection and no added network calls. Root attaches test/review evidence to the existing ClickUp ticket; no new ticket or product-priority change is needed.

## Execution evidence

The factory, provider, transport, native command/persistence, Linux system-store and browser fixtures are implemented. Steps 2–8 stay open for runtime verification. The reconstructed baseline `cargo test -p selahcue-cloud --test test_fallback` exited 101 in 2.38 seconds on the expected missing factory and reason imports. This baseline run restored the original cloud library after initial implementation edits, then restored the working library. It did not execute test assertions. Formatting, diff whitespace, and Python/embedded JavaScript parsing passed; native test, browser execution, CI, independent reviews, and delivery gates remain pending under the host paging pause.
