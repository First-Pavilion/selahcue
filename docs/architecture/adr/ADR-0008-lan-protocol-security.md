# ADR-0008: LAN protocol and transport security

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** High
- **Validating spike:** S6 — mDNS reliability on real church Wi-Fi (AP isolation, multicast filtering) + QR pairing/auth
- **Owner:** Software Architect
- **Closes open decision:** OD-18 (LAN transport final choice)
- **Grounded in:** `docs/product/prds/SelahCue-PRD.md` (FR-085..094, FR-097/098, FR-174, NFR-016), `docs/research/FEASIBILITY.md` §5/§6, `docs/security/reviews/threat-model-draft.md` §2 (T1–T8, T18–T20) and §3, `docs/architecture/ARCHITECTURE.md` §9

## Decision

The desktop host and mobile controllers communicate over a **WebSocket channel carried on TLS 1.3**, where the host presents a **self-signed certificate whose fingerprint is delivered in the QR pairing payload and pinned by the controller** (trust-on-first-use, no CA). Layered on top of that encrypted channel:

1. **Discovery:** mDNS/DNS-SD advertisement, with a **QR-only fallback** (host network locator carried in the QR) for networks where multicast is blocked (FR-085).
2. **Pairing:** single-use, short-TTL QR carrying host fingerprint + ephemeral secret, gated by **host-side confirmation** (FR-086).
3. **Session auth:** per-device tokens **bound to a device-held keypair** (proof-of-possession), independently revocable (FR-089).
4. **Message integrity:** every control message carries a **monotonic sequence/nonce + timestamp** (replay window ±30 s), authenticated under the session key (FR-091).
5. **Authorization:** **server-side, deny-by-default RBAC** evaluated on the authoritative host for every command; client-asserted role is never trusted (FR-090).
6. **Validation & isolation:** strict schema/type/size/range validation (FR-174) and per-device + global rate limiting with the render/output path isolated from control-plane load (FR-091, NFR-024).

**All** LAN traffic — control, previews, transcript/caption streams, and media — rides the encrypted channel; plaintext egress is rejected (FR-088, NFR-016).

This is deliberately a **layered** decision, not a single transport pick. TLS provides channel confidentiality, host authentication, and integrity; the application layer provides per-command replay resistance, device authentication, and authorization. TLS alone does not satisfy the threat model (T4 replay, T5 elevation are explicitly *not* addressed by transport encryption — threat model §2, §3.4).

## Context

The LAN control plane is the product's **primary attack surface** (PRD §16; threat model §1.2 TB1). The forces:

- **The LAN is untrusted by construction.** Church Wi-Fi is a shared, hostile-by-default segment; WPA2/WPA3 provides no isolation between clients on a shared/guest PSK, so a passive sniffer and rogue devices must be assumed present (threat model TB1, §3.1). Live output control (asset A1) is the highest real-time-impact asset — an injected "clear/blackout" mid-service is a Critical integrity/availability threat (T1/T2).
- **No public CA exists on a LAN host.** There is a genuine trust-on-first-use problem: the host cannot obtain a CA-signed cert for an ad-hoc local address, so channel security must be bootstrapped out-of-band (threat model §3.1).
- **Everything on the wire is sensitive.** Lyrics, scripture, transcripts, previews, and bearer tokens all traverse the LAN; the transport-scope requirement was broadened (PRD change MAJOR-11) so that FR-088/NFR-016 cover *all* controller traffic, not just commands — no plaintext preview or transcript egress.
- **The desktop is authoritative; mobile is assistive and optional.** Mobile holds no authoritative state; loss of every controller must never disable any desktop capability (FR-098, CON-1). This means the transport can fail closed without endangering the live service, and that authorization decisions belong on the host, never on the client.
- **Discovery must survive real church networks.** mDNS/DNS-SD is the zero-config LAN discovery standard (RFC 6763, UDP 5353) but is single-LAN-only and is frequently blocked by AP/guest isolation and multicast filtering — DOCUMENTED capability, church-network reliability INFERRED and unproven (FEASIBILITY §6, S6). A remote is useless if it cannot find the host.
- **Cross-platform reach.** The controller is a single-codebase mobile app (ADR-0009, Flutter) speaking to a Rust host; the transport must be implementable on both sides without exotic tooling.
- **Threat coverage is mandated, not optional.** The threat model's §3 recommendations (T1–T8, T18–T20) and the FEASIBILITY security flag — "do NOT ship an unauthenticated LAN control channel" (§6) — are hard constraints on any option.

## Options considered

### Option A — WebSocket over TLS 1.3 with QR-pinned self-signed cert (CHOSEN)

WebSocket for the bidirectional control + streaming channel, wrapped in TLS 1.3, with the host's self-signed cert fingerprint pinned via the QR pairing payload; app-layer keypair-bound tokens, nonce+timestamp replay protection, and server-side RBAC on top.

**Pros**
- WebSocket is the pragmatic default for command + live-state + streaming: "simplest, bidirectional, works everywhere" (FEASIBILITY §6 transport row, INFERRED-Med). Bidirectional framing suits both the request/response command flow and the push-based preview/transcript streams on one connection.
- TLS 1.3 is the DOCUMENTED baseline for transport security (threat model §3.1, OWASP MASTG); it directly answers T2 (tampering/MITM) and T3 (passive sniffing) for the channel.
- **Cert pinning defeats LAN MITM without a CA** (threat model §3.1 pattern 1, DOCUMENTED — Secure Vale): the QR delivers the host fingerprint out-of-band, so a fake host or a MITM presenting a different cert is rejected even if "CA-signed." This closes the trust-on-first-use gap that plain TLS would leave open (T1/T18 host-spoofing).
- Mature, well-audited TLS 1.3 implementations exist for the Rust host (rustls) and for the Flutter/mobile clients, so we are *not* rolling our own channel crypto — the highest-leverage way to avoid crypto-implementation error.
- The same encrypted channel carries previews, transcripts, and media, satisfying the broadened FR-088/NFR-016 with no second transport.
- Cleanly composes with the app-layer controls the threat model requires anyway (§3.3/§3.4): keypair-bound tokens (T8), nonce+timestamp replay window (T4), server-side RBAC (T5), rate limiting (T6).

**Cons / costs**
- **Certificate lifecycle is on us.** Self-signed + pinned means we own key generation on first run, rotation, and forced re-pair on host security-config reset (threat model §3.3). A pinning-validation bug re-opens the MITM window — pinning correctness is now security-critical code and must be spike/fuzz-covered.
- **TLS is necessary but not sufficient.** It gives channel security but not per-command replay resistance or authorization; those must be built at the app layer regardless (this is why the decision is layered, not "just TLS"). Presenting TLS as the whole answer would be a documented mistake (threat model T4/T5).
- **Platform TLS-trust customization varies.** Pinning a self-signed cert requires custom trust evaluation on the mobile side; some platform TLS stacks make custom-trust awkward. This risk is carried into the mobile spike (S9) and is the trigger for the Option C fallback below.

### Option B — gRPC

Schema-first RPC over HTTP/2 + TLS, with generated stubs and first-class streaming.

**Pros**
- Typed, schema-first contracts (protobuf) give a head start on FR-174 message validation and reduce hand-rolled parsing; strong bidirectional streaming for previews/transcripts.
- Mature, widely deployed, good tooling.

**Cons**
- **Heavier** for what a LAN church remote needs — FEASIBILITY §6 explicitly frames gRPC as "typed, streaming, **heavier**" versus WebSocket as the pragmatic default. The HTTP/2 + codegen + mobile-runtime weight is disproportionate to a control app whose payloads are small commands and downscaled preview frames.
- **Solves none of the hard problems for free.** The trust-on-first-use / self-signed-pinning story is identical to Option A (still no CA on the LAN); replay protection, keypair-bound device auth, and RBAC still have to be built at the app layer. Protobuf validates wire *shape* but not size/range/business constraints, so the FR-174 validator is still required.
- Adds build and dependency complexity on the Flutter controller (gRPC-dart / codegen pipeline) against a single, simple host — cost without a commensurate security or capability gain.
- Net: it buys typing we can obtain more cheaply (a versioned JSON/CBOR schema + strict validator) while importing weight that conflicts with the low-footprint posture (NFR-001..003).

### Option C — Noise-protocol app-layer crypto over plain WebSocket

An authenticated app-layer handshake (Noise IK/XX-style) using the pairing-established static keys, running over an unencrypted WebSocket/TCP; no platform TLS involvement.

**Pros**
- **Explicitly sanctioned by the threat model** as an acceptable transport-security pattern (§3.1 pattern 2) "if a raw TLS stack is impractical on some platforms."
- Binds the secure channel directly to the **device keypair we already require** for proof-of-possession (T8, §3.3), giving a very clean identity story and channel-binding.
- Modern, formally analyzable handshake; sidesteps platform TLS-trust-store quirks entirely (relevant to the Option A mobile-trust risk).

**Cons**
- **We would be operating our own secure channel.** Even with a good Noise library, handshake integration, key rotation, and session-state management are bespoke security-critical code — higher implementation-error risk than a vetted TLS 1.3 stack.
- The threat model frames Noise as the **fallback** ("if a raw TLS stack is impractical"), not the default. On our actual stack that precondition does not hold: rustls on the host and platform/Flutter TLS on the client are readily available, so the motivating constraint is absent.
- Handshake spec, key rotation, and cipher choices are still open Stage-13 items (threat model §7.2) — choosing Noise now would pull unresolved crypto-design work onto the critical path with no offsetting benefit today.

**Disposition:** kept as the **designated fallback** for Option A, because NFR-016 explicitly permits "authenticated app-layer crypto" as an alternative to pinned TLS. If S9/S6 surface a platform where custom-trust pinned TLS is impractical, we switch that path to Noise without changing any of the app-layer auth/replay/RBAC layers.

### Option D — Plain WebSocket, unencrypted/unauthenticated (REJECTED)

**Rejected outright.** It violates the encrypted-transport requirements (FR-088, NFR-016), the threat model's Critical/High findings (T2 MITM, T3 sniffing, T1 spoofing), and the FEASIBILITY security flag: "do NOT ship an unauthenticated LAN control channel" (§6). On an untrusted shared segment (TB1) it would allow trivial injection of live-output commands during a service. Not viable at any confidence.

## Consequences

### Positive
- **The primary attack surface is defended in depth.** Confidentiality + host authentication + integrity (pinned TLS 1.3) *and* per-command replay resistance, device-bound authentication, deny-by-default authorization, input validation, and rate limiting — mapping directly onto threat-model T1–T8, T18–T20.
- **No CA dependency and no cloud dependency** for LAN security: security bootstraps entirely from the out-of-band QR, preserving the offline-first principle (NFR-015, CON-2).
- **One encrypted channel for everything**, so previews/transcripts/media inherit the same protection with no plaintext side channel (FR-088, NFR-016).
- **Fail-closed without service impact:** because the host is authoritative and mobile is optional, rejecting an unauthenticated/replayed/over-rate message never risks the live output; loss of all controllers leaves the desktop fully capable (FR-098, NFR-024).
- **Clean revocation & audit:** keypair-bound per-device tokens give immediate mid-session revocation (FR-089/T8), and every live-control command is recorded in the append-only audit log (FR-150/T7).

### Negative / accepted costs
- We **own the certificate and key lifecycle** (generation, pinning storage, rotation, forced re-pair on security reset) and the **replay-window state** (per-session seen-nonce window, monotonic sequence, ±30 s clock-skew tolerance, and its persistence across reconnects — an explicit Stage-13 item, threat model §7.5). This is security-critical code that must be reviewed and fuzzed, not merely feature-tested.
- **Pinning correctness and the schema validator become high-blast-radius components.** FR-174 mandates a fuzz/fault-injection AC on the parser; the pinning path needs equivalent scrutiny. A defect in either is a direct security regression.
- **Custom-trust on mobile** carries platform variability that is not fully retired until the mobile spike (S9) and could force the Option C fallback on a given platform.
- **mDNS is not guaranteed** on real church networks (S6); we accept the operational cost of maintaining a second discovery path (QR-only) to remove that dependency.

### What this commits us to
- A **layered security contract** that later ADRs and implementation must not weaken: encrypted transport + host-fingerprint pinning + keypair-bound tokens + nonce/timestamp replay window + server-side RBAC + schema validation + rate limiting, with the output path isolated from control-plane load.
- **RBAC lives on the authoritative host** for all seven roles, deny-by-default; the definitive command→role matrix and multi-controller conflict resolution are owed to Stage-13 (threat model §7.4). Client-asserted role is never trusted.
- **Reconnection semantics:** remembered host = (pinned fingerprint + device token/keypair); every session re-authenticates (no implicit trust of network position, FR-087), and on reconnect stale/queued actions are discarded, not replayed — the nonce/timestamp window is the mechanism that enforces FR-097's "no ghost actions."
- **Secrets placement:** device keypairs/tokens live only in the OS secret store (Keychain/DPAPI/Secret Service; mobile Keystore/Keychain), never in plaintext or logs (NFR-017/T9), and API keys are never transmitted to controllers (threat model §4).
- Keeping the **Noise app-layer fallback viable** (NFR-016's permitted alternative), which constrains the app-layer auth to be transport-agnostic so it can sit on either pinned-TLS or Noise.

## Fallback & validation

The **cryptographic design is High confidence** — it is squarely grounded in the threat model's §3 recommendations and DOCUMENTED sources, and it reuses vetted TLS 1.3 implementations rather than bespoke channel crypto. The residual uncertainty is **not** in the crypto but in **discovery reliability on real church Wi-Fi**, which is the make-or-break unknown for the remote as a whole.

- **Validating spike S6** — LAN discovery + pairing test on isolated/guest networks (AP isolation, multicast filtering). It must confirm that mDNS advertisement/resolution works on representative church networks and that QR pairing + pinned-TLS session establishment succeeds end-to-end.
- **Pre-designed fallback #1 (discovery):** if S6 shows mDNS is unreliable or blocked, the **QR-only path** already carries the host network locator, so pairing and connection proceed with zero dependence on multicast (FR-085). This fallback is *in the decision*, which is why discovery risk does not lower overall confidence.
- **Pre-designed fallback #2 (transport crypto):** if the mobile spike (S9) or S6 surfaces a platform where custom-trust pinned TLS is impractical, switch that path to **Noise-protocol authenticated app-layer crypto over plain WebSocket** (Option C), which NFR-016 explicitly permits — without disturbing the keypair-bound tokens, replay window, or RBAC layered above it.

Both fallbacks are engineered in advance rather than left open, so the "High" confidence reflects a decision whose failure modes each have a ready, requirement-compliant answer. Items deliberately deferred to the **Stage-13** full security review (per threat model §7): concrete TLS-vs-Noise handshake/cipher/key-rotation spec (§7.2), the exact QR payload/TTL/channel-binding format (§7.3), the definitive RBAC matrix + conflict resolution (§7.4), the concrete replay/nonce algorithm and reconnect state persistence (§7.5), the Linux secret-store fallback (§7.6), and mDNS discovery-layer threat modeling — host advertisement spoofing/enumeration (§7.13).

## Requirement / PRD references

| Ref | Requirement | How this ADR satisfies it | Threat |
|---|---|---|---|
| FR-085 | Discover hosts on the LAN; QR-only fallback when multicast blocked | mDNS advertise + QR-only fallback carrying host locator | — |
| FR-086 | QR pairing with host-side confirmation | Single-use, short-TTL QR (fingerprint + ephemeral secret) + host approval | T1/T18 |
| FR-087 | Remember hosts + secure reconnection (no fresh QR) | Pinned fingerprint + device proof-of-possession; re-auth each session | T8 |
| FR-088 | Encrypted, authenticated LAN transport (incl. previews/transcript/media) | TLS 1.3 + pinned host cert over WS; plaintext rejected | T2/T3 |
| FR-089 | Per-device revocable tokens bound to a device keypair | Keypair-bound tokens; immediate mid-session revocation | T8 |
| FR-090 | Server-side RBAC for all seven roles (deny-by-default) | Host-side authorization per command; client role never trusted | T5 |
| FR-091 | Replay protection + rate limiting | Monotonic nonce+timestamp (±30 s); per-device+global caps; output isolation | T4/T6 |
| FR-092/093/094 | Mobile preview/nav, slide/clear/blackout, timer control (role-scoped) | Role-scoped commands over the authenticated channel | T5 |
| FR-097 | Graceful reconnection, no ghost actions | Nonce/timestamp window discards stale/queued actions on reconnect | T4 |
| FR-098 | Loss of all mobile never disables desktop | Authoritative host; fail-closed control plane; output-path isolation | — |
| FR-150 | Append-only audit log of live-control/commands | Every command logged: device, role, action, timestamp, result | T7 |
| FR-174 | Control-message schema/input validation | Strict schema/type/size/range validation; fail-safe on malformed input | T20 |
| NFR-016 | LAN transport security (TLS 1.3 pinned, or authenticated app-layer crypto) | Pinned TLS 1.3 default; Noise app-layer crypto as permitted fallback | §3.1/T3 |
| NFR-017 | OS-secret-store-only secrets | Device keypairs/tokens in OS secret store, never plaintext | T9 |
| NFR-024 | Output-failure isolation | Control-plane pressure/failures cannot blank live output | T6 |
| CON-1 / NFR-015 | Desktop-authoritative; offline-first | Security bootstraps from QR; no CA/cloud dependency | — |

Related ADRs: ADR-0009 (Flutter controller — implements the client side; mobile-trust/pinning validated by spike S9), ADR-0012 (signed updates + anti-rollback, T14), ADR-0011 (audit/observability with redacted diagnostics — no secrets/transcripts in logs, T19). Full architecture context: `ARCHITECTURE.md` §9, §11.
