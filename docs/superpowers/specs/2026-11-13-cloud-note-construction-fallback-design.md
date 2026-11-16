# Cloud fallback architecture ruling

Ticket: [17tnw2b9b8u](https://app.clickup.com/t/17tnw2b9b8u). Source inspected: `218e14140e8df0e1089dbbc3ce09096f26e08310`. Scope: architectural decision and implementation instructions only; no source, Git state or tracker changes.

## Decision

Use a **fallible provider factory inside the shared generator**, plus credential-aware fallible transport constructors. Do not use the draft lazy HttpTransport adapter.

The order is: shared consent/request admission → shared clamp → one-time credential/model selection → existing transport/pilot admission → HTTP construction → cloud request → the single transport-only local fallback → existing post-generation and persistence policy guards. Hosted uses already selected base/token; Direct uses the developer or pilot constructor appropriate to the build. The existing shared borrowed-provider entry point stays compatible and uses the same internal orchestration.

`provider_source::notes_transport()` already returns `NoteError`, including terminal `NotConfigured`. That result travels unchanged through the new factory API. Only the real HTTP constructor's `TransportError` maps to `NoteError::Transport`. Thus an unavailable pilot or missing developer key cannot become a local draft merely because construction is deferred. Dynamic pilot rechecks remain necessary even after credential selection; they are not duplicate secret/environment reads.

## Why this option

| Option | Result and cost |
| --- | --- |
| Lazy HttpTransport around current notes_transport | Rejected: the trait can return only TransportError, so it erases terminal NoteError or needs sidechannel/reconstruction logic. |
| Specialized deferred provider wrapping a fallible factory | Viable, but adds state/interior mutability or a new provider wrapper only to move the same NoteError-bearing boundary; more machinery than a one-shot generator callback. |
| Fallible generator factory + one-time credential selection | Chosen: explicit FnOnce lifecycle and error enum, no mutable error state; two constructor additions preserve existing APIs and avoid duplicate secrets or fallback logic. |
| Typed replacement of both public error shapes | Deferred: stronger provenance but changes many producers/fixtures and the core error surface. Exact canonical strings plus closed rendering satisfy this bounded notice requirement without that churn. |

The implementation touches cloud lib/openai/pilot/transport/deadline_transport, operator provider_source/main and outcome fixtures/tests. The explicit signatures and file map are in `cloud-fallback-plan-draft.md`. No new crate or core error variant is required. Existing rustls dependency is sufficient for typed TLS classification.

## Safe cause policy

Keep `TransportError(pub String)` and `NoteError::Transport(String)`. Classify typed reqwest/rustls chains before formatting. At most eight nodes; inspect io::Error's inner error as well as ordinary source links. Recognize InvalidCertificate and the locked typed General no-roots literal; everything else maps to generic setup/unavailable. Both ordinary and deadline build/send sites emit fixed canonical messages. The generator allowlists whole canonical strings into a closed reason enum; the operator displays fixed copy only. Arbitrary strings are neither interpolated nor substring-parsed. This preserves bounded notices even for fabricated hostile errors. It does not assert cryptographic provenance for the category string, which is unnecessary because category choice grants no authority and reveals no input text.

The accepted cost is less verbose raw build/send diagnostics for other transport consumers. Avoid retaining an additional diagnostic payload merely to preserve URL/certificate detail. The requested user-visible distinction is trusted-root setup versus rejected certificate versus generic unavailability; per-certificate names, dates and operating-system strings are deliberately excluded. Unknown constructor failures use a generic client-setup reason, not a misleading assertion of TLS failure.

## Requirement trace and evidence boundary

| Approved acceptance criterion | Design / verifier |
| --- | --- |
| Build failure uses existing local fallback | Factory returns NoteError into the same match as request errors; counting tests plus real Linux builder fixture. |
| Configuration/consent before construction | Shared gate and credential-aware constructors; zero-builder-count tests for denied consent, missing/blank key, release/pilot refusal. |
| Short safe TLS cause in plain-text notice | Typed bounded classifier, canonical allowlist, fixed <=160-byte added reason, existing textContent rendering; real TLS refusal and separate operator UI assertions. |
| Empty SSL_CERT_FILE on Linux gives local draft | Child-process Linux fixture with empty file AND directory plus configured synthetic credentials; run inside existing Linux runtime. |
| Missing key wins even on machine with broken roots | Child fixture under same Linux environment plus zero-build count. |
| Certificate refusal shown using existing TLS server | Real untrusted certificate produces fixed category and no HTTP bytes, with trusted control; operator fixture proves notice composition and text rendering. |

Verified in this design pass: current source signatures/control flow, pilot terminal transport admission, current tuple errors, existing rustls dependency and exact cached platform-verifier no-roots literal. The ticket export supplies the approved acceptance criteria. No runtime checks or compilation ran during this architecture assignment because root's other ticket CI was running. The new signatures and classifications require compilation and the named fixtures during implementation. Mac tests, Linux cross compilation and mocks do not establish native Linux trust-root behavior.

## Preserved boundaries and ownership

Root/implementer owns execution Goal Contract, source edits, current-base reconciliation, CI, independent code/security/QA/performance gates and tracker handoff. Architecture does not self-approve security or claim those gates. Preserve all pilot pre/post/save guards, accepted/pending behavior and Hosted exemption. Immediate notice is transient; reopening historical drafts is not part of the approved scope. There is no schema migration, new deployment dependency, network retry, capacity change or persistence recovery procedure. PR revert is sufficient rollback.

Architecture handoff status: **GATE_REVIEW** to the parent execution/review workflow. The parent reports plan approval already authorized; this is not a request for another user permission round. Implementation and independent review remain outstanding.
