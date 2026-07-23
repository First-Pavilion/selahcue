# SelahCue — Early Threat Model (DRAFT)

- **Scope reference:** RP-10 (early / pre-implementation security review)
- **Stage:** EARLY. This is a design-time STRIDE threat model, not a full security assessment. A Stage-13 review must revisit everything flagged in §7.
- **Date:** 2026-07-23
- **Reviewer role:** Security Reviewer
- **Product:** SelahCue — cross-platform church presentation app. Desktop (Win/macOS/Linux) is the authoritative *host*; mobile (Android/iOS/iPadOS) are *controllers* over the LOCAL network. Features: live audio capture, transcription, automatic scripture detection, AI sermon notes (optional cloud providers via user-supplied API keys), TTS.

### Evidence classification legend
Each factual claim is tagged: **OBSERVED** (verified in this codebase/environment), **DOCUMENTED** (vendor/standard doc, cited), **INFERRED** (reasoned from architecture, not directly verified), **UNKNOWN** (needs decision/investigation).

> Note: No SelahCue source code was present to inspect in this environment at review time (INFERRED — directory contained only this docs tree). All product-behaviour claims are therefore INFERRED from the RP-10 brief and MUST be re-validated against the real implementation at Stage-13.

---

## 1. Assets & Trust Boundaries

### 1.1 Assets (what we protect)

| # | Asset | Where it lives | Why it matters |
|---|-------|----------------|----------------|
| A1 | **Live output control** (what is projected: slides, scripture, lyrics, timers, blank/clear) | Desktop host | Integrity/availability critical — unauthorized control disrupts a live service; highest real-time impact. |
| A2 | **Sermon audio capture** | Desktop host (RAM/disk); optionally cloud transcription | Sensitive/personal content; may capture congregation audio. |
| A3 | **Transcripts** (live + stored) | Desktop host local storage; optionally cloud AI | Sensitive speech content; potential PII of speaker/congregation. |
| A4 | **AI sermon notes** | Desktop host; optionally cloud AI providers | Derived sensitive content. |
| A5 | **User-supplied AI/transcription/TTS API keys** | OS secret store per platform | Credential theft → financial loss (billable APIs) + impersonation. |
| A6 | **Per-device pairing tokens / auth secrets** | Desktop host store + mobile secure storage | Compromise → unauthorized control (A1). |
| A7 | **Role/permission configuration** | Desktop host | Integrity → privilege escalation. |
| A8 | **Media library / imported files** (images, video, presentations, fonts) | Desktop host filesystem | Path traversal / malicious media → RCE or host compromise. |
| A9 | **Local AI model files** (on-device transcription/scripture detection) | Desktop host filesystem | Integrity → poisoned/backdoored inference, RCE via malformed model. |
| A10 | **Software update artifacts** | Vendor distribution → host | Supply-chain: malicious update = full host compromise. |
| A11 | **Backups / exported service sets** | Local disk / user-chosen location | Confidentiality of A2–A5 at rest and in transit. |
| A12 | **Retention/consent/privacy settings** | Desktop host | Integrity → silent data exfiltration; governs privacy guarantees. |

### 1.2 Trust boundaries

```
                              (OPTIONAL, OPT-IN)
  [ Mobile controllers ]        [ Cloud AI / transcription / TTS ]
  Android/iOS/iPadOS                     ▲  user API keys
        │  LAN control API               │  HTTPS (public internet)
        │  (WiFi — UNTRUSTED shared)     │
        ▼                                │
  ══════════════ TB1: LAN ══════════ TB3: Internet ═══════════
        │                                │
        ▼                                │
  ┌─────────────────────────────────────┴───────────────────┐
  │  DESKTOP HOST (authoritative)   — TB2: process/OS bnd     │
  │  • Control API server  • Audio capture  • Transcription   │
  │  • Scripture detect    • AI notes orchestration  • TTS    │
  │  • Role/permission engine                                 │
  │      │                                                    │
  │      ▼  TB4: OS secret store boundary                     │
  │  [ Keychain / DPAPI / Secret Service ] ← API keys, tokens │
  │      │                                                    │
  │      ▼  TB5: filesystem boundary                          │
  │  [ Media library | AI models | transcripts | backups ]   │
  └───────────────────────────────────────────────────────────┘
        ▲  TB6: update/distribution boundary
        │  signed update feed + artifacts
  [ Vendor build/release infrastructure ]
```

- **TB1 — LAN / shared WiFi (UNTRUSTED):** Church WiFi is a shared, hostile-by-default segment. Assume rogue phones/laptops, guests, and a passive sniffer are present. Highest-risk boundary for A1/A6.
- **TB2 — Desktop process/OS:** Local malware, other local users. The host runs a network-listening service — treat it like any exposed server.
- **TB3 — Internet to cloud providers:** Only crossed when the user opts in. Carries A2/A3/A4 + A5 to third parties outside our control.
- **TB4 — OS secret store:** Boundary between app process and OS-protected credential vault (A5/A6).
- **TB5 — Filesystem:** Untrusted imported files (A8) and model files (A9) cross into parsing/execution contexts.
- **TB6 — Update/distribution:** Vendor → host; classic supply-chain boundary (A10).

---

## 2. STRIDE Threat Table

Severity scale: **Critical / High / Medium / Low** (likelihood × impact for a live-service context). All threats **INFERRED** from architecture unless noted.

| ID | STRIDE | Threat | Asset(s) | Sev | Recommended control (MVP unless noted) |
|----|--------|--------|----------|-----|----------------------------------------|
| T1 | **S**poofing | Rogue device on WiFi impersonates an authorized controller / a fake "host" tricks a controller into pairing | A1,A6 | **Critical** | Mutual auth on every session: host identity pinned during QR pairing (host pubkey/cert fingerprint in QR); per-device tokens bound to device keypair. Reject unpaired devices by default. (§3) |
| T2 | **T**ampering | MITM on LAN alters control commands or injects commands (e.g. clear/blank output mid-service) | A1 | **Critical** | Authenticated, integrity-protected transport (TLS 1.3 with pinned host cert, or authenticated app-layer AEAD). Sign/MAC every command with per-session key. (§3) DOCUMENTED: HTTPS alone insufficient without integrity + replay prevention per request. |
| T3 | **I**nfo disclosure | Passive sniffing of LAN traffic reveals lyrics/scripture/notes, control tokens, or transcript streams | A3,A6 | **High** | Encrypt all LAN control + streaming traffic (TLS 1.3). Never send bearer tokens in cleartext or URLs. |
| T4 | **S**poofing/**E**levation | Replay of a previously captured valid command (e.g. re-send "advance slide" / "reveal") | A1 | **High** | Per-command monotonic nonce + timestamp within a short window; server rejects duplicates and stale messages. Bind nonce to session key. (§3) |
| T5 | **E**levation | Lower role (Observer) issues higher-privileged commands (goes live, edits scripture) | A1,A7 | **High** | Server-side RBAC enforced on the host for EVERY command (never trust client-asserted role). Deny-by-default; command→role allowlist. (§3) |
| T6 | **D**oS | Flood of control/connection requests freezes host or the live output | A1 | **High** | Per-device + global rate limiting, connection caps, bounded queues, input size limits. Watchdog keeps output rendering independent of control-API load. |
| T7 | **R**epudiation | No record of who changed the live output / who sent a command | A1,A7 | **Medium** | Append-only local audit log: device id, role, command, timestamp, result. Needed for post-service incident review. |
| T8 | **T**ampering | Stolen/never-revoked device retains control after phone is lost or volunteer leaves | A6,A1 | **High** | Per-device revocable tokens + admin "devices" screen (view/rename/revoke). Token expiry + re-pair. Revocation effective immediately on host. (§3) |
| T9 | **I**nfo disclosure | API keys (A5) readable from disk/config/plaintext file or process memory dump | A5 | **Critical** | Store ONLY in OS secret store (Keychain/DPAPI/Secret Service; mobile Keystore/Keychain). Never in plaintext config, logs, or crash dumps. Redact in telemetry. (§4) |
| T10 | **I**nfo disclosure / privacy | Transcript/audio sent to cloud AI without explicit user consent (silent exfiltration of sermon + congregation speech) | A2,A3,A4 | **Critical** | Cloud is OPT-IN, per-provider, with visible, unambiguous disclosure before first send. No transcript/audio leaves host without explicit user action. Persisted consent state; visible "cloud active" indicator. (§5) |
| T11 | **T**ampering | Path traversal / zip-slip via media or service-pack import writes outside intended dir | A8 | **High** | Canonicalize + validate all import paths; reject `..`/absolute/symlink escapes; extract to sandboxed dir; enforce type allowlist. |
| T12 | **E**levation (RCE) | Malicious media (crafted image/video/font) exploits a decoder/parser | A8 | **High** | Use memory-safe/maintained decoders; sandbox media decode where feasible; validate headers; keep media libs patched (§6). Defer deep fuzzing to Stage-13. |
| T13 | **T**ampering | Poisoned/swapped local AI model file → manipulated inference or RCE on load | A9 | **Medium** | Verify model integrity (hash/signature) before load; pin known-good hashes; load from app-controlled dir with restricted perms. |
| T14 | **T**ampering (supply chain) | Malicious or downgraded software update installed | A10 | **Critical** | Code-signed releases + signed update feed with signature verification before apply; secure transport; anti-rollback (min-version). Signing keys offline/HSM. (§6) DOCUMENTED: Sparkle CVE-2025-0509 shows signed-update-replacement bypasses are real. |
| T15 | **I**nfo disclosure | Unencrypted backups expose transcripts/notes/keys | A11,A5 | **High** | Encrypt backups at rest (authenticated encryption); exclude raw secrets or wrap them; warn on export to untrusted locations. (§6) |
| T16 | **T**ampering | Vulnerable third-party dependency (transitive) introduces exploit | all | **Medium** | SBOM + automated dependency/CVE scanning in CI; pin + review; patch cadence. (§6) |
| T17 | **R**epudiation / privacy | User cannot delete recordings/transcripts; data retained indefinitely | A2,A3,A4,A12 | **Medium** | Configurable retention + reliable delete (recording, transcript, notes), including derived copies. Default to conservative retention. (§5) |
| T18 | **S**poofing | QR pairing code intercepted/shoulder-surfed/reused to pair an attacker device | A6 | **High** | Short-lived, single-use pairing codes; channel-binding (code carries host fingerprint + ephemeral secret); require host-side confirmation; expire on use/timeout. (§3) |
| T19 | **I**nfo disclosure | Secrets/transcripts leak via logs, crash reports, or clipboard | A3,A5 | **Medium** | Scrub logs/crash reports; opt-in diagnostics only; no sensitive data in analytics. |
| T20 | **D**oS / integrity | Malformed control message crashes host parser mid-service | A1 | **Medium** | Strict schema validation, size/type limits, fuzz-tested parser, fail-safe (keep last good output rendered). |

---

## 3. LAN Control-Protocol Security Recommendations

Threat model of the LAN control API (addresses T1–T8, T18–T20).

### 3.1 Transport security on the LAN
- **Encrypt all control + streaming traffic.** Even though "no cloud is required," LAN is untrusted (TB1). Use **TLS 1.3** for the control channel. DOCUMENTED: TLS 1.3 as baseline; cleartext disabled ([OWASP MASTG best-practices](https://mas.owasp.org/MASTG/best-practices/)).
- **The trust-on-first-use problem:** the host has no public CA. Two acceptable patterns:
  1. **Host self-signed cert + pinning:** host generates a long-lived keypair/cert on first run; its fingerprint is delivered to the controller *in the QR pairing code* and pinned on the mobile client. Subsequent TLS connections verify against the pinned fingerprint. This defeats LAN MITM without a CA. (Certificate pinning "rejects connections using unexpected certificates even if CA-signed" — DOCUMENTED, [Secure Vale](https://securevale.blog/articles/certificate-pinning-in-mobile-apps/).)
  2. **Authenticated app-layer encryption** (e.g. Noise-protocol-style handshake using the pairing-established static keys) if a raw TLS stack is impractical on some platforms.
- **Do NOT rely on WiFi WPA2/WPA3 for confidentiality** — everyone on church WiFi shares the segment; guest/shared PSK offers no isolation between clients. (INFERRED.)

### 3.2 Pairing (QR-code)
- QR pairing payload SHOULD carry: host identity (stable pubkey/cert **fingerprint** — enables pinning + defeats fake-host spoofing T1/T18), an **ephemeral single-use pairing secret**, host network locator, and a short **expiry**.
- **Single-use + short TTL** (e.g. code invalid after first successful pair or after ~60–120s). Rotate on display. (Aligns with changing-QR device-pairing patents/prior art — DOCUMENTED that QR pairing exchanges a current authentication parameter.)
- **Host-side confirmation** of a new device before it becomes active ("Allow 'Sarah's iPad'?"). Prevents silent pairing.
- **Validate the QR payload against a strict allowlist format** (QR is untrusted input — DOCUMENTED, OWASP treats QR codes as attacker-controllable input, [MASTG](https://mas.owasp.org/MASTG/best-practices/)).

### 3.3 Auth tokens & remembered hosts
- **Per-device tokens** derived from the pairing exchange; each device gets its own credential (revocable independently — DOCUMENTED pattern: "device-specific tokens that can be revoked," OWASP mobile best practices).
- Bind the token to a **device-held keypair** (private key in mobile Keystore/Keychain) so a stolen token alone is insufficient; connection requires proof-of-possession.
- **Secure reconnection:** remembered host = stored (host fingerprint + device token/keypair). Reconnect performs mutual verification (pinned host fingerprint ↔ device proof-of-possession) with no fresh QR needed, but re-authenticates every session (no implicit trust of network position).
- **Token expiry + rotation**; force re-pair after long inactivity or on host security-config reset.

### 3.4 Roles, command validation, replay, rate-limit
- **RBAC enforced server-side on the host** for the seven roles (Observer / Presenter / Worship leader / Scripture operator / Timer operator / Production operator / Administrator). Deny-by-default; maintain an explicit **command → allowed-roles** matrix. Never trust a client-asserted role (T5).
- **Revocation** takes effect immediately on the host; revoked device is dropped mid-session.
- **Command validation:** strict schema, type/size/range checks, reject unknown fields (T20).
- **Replay protection (T4):** every command carries a **monotonic sequence/nonce + timestamp**, authenticated under the session key (MAC/AEAD). Host rejects duplicates, out-of-window timestamps, and out-of-order sequence. Maintain a per-session seen-nonce window.
- **Rate limiting (T6):** per-device and global command/connection rate caps; connection count caps; bounded input; keep the rendering/output path isolated so control-plane pressure cannot blank the screen.
- **Audit log (T7):** append-only local log of device, role, command, timestamp, outcome.

---

## 4. Secret-Storage Recommendations (per platform)

Applies to A5 (user AI/transcription/TTS keys) and A6 (device tokens/keypairs). **Never store secrets in plaintext config, source, logs, or crash dumps** (T9, T19).

| Platform | Backend | Notes |
|----------|---------|-------|
| **macOS (host)** | **Keychain Services** (Security.framework) | DOCUMENTED. Use per-item access control; avoid dumping to Keychain-accessible-when-unlocked broader than needed. |
| **Windows (host)** | **DPAPI** (user-scoped) and/or **Credential Manager** | DOCUMENTED — DPAPI protects keys; Credential Manager is the standard vault. |
| **Linux (host)** | **Secret Service API** (libsecret / GNOME Keyring / KWallet) | DOCUMENTED. Availability varies by desktop environment — **UNKNOWN** which environments church PCs run; need a documented fallback (see below) and to warn if no keyring present. |
| **Android (controller)** | **Android Keystore** (hardware-backed where available) | DOCUMENTED (OWASP: use Keystore). Store device keypair; use StrongBox/TEE if present. |
| **iOS/iPadOS (controller)** | **Keychain** (Secure Enclave for keys where possible) | DOCUMENTED (OWASP: use Keychain). |

Cross-platform implementation options (DOCUMENTED): framework-native helpers such as Electron `safeStorage` (Keychain/DPAPI/Linux secret store) or a native keychain library (Windows Credential Manager / macOS Keychain / Linux Secret Service). — [Electron safeStorage](https://www.electronjs.org/docs/latest/api/safe-storage), [cross-keychain](https://github.com/magarcia/cross-keychain).

Additional requirements:
- **Linux fallback (UNKNOWN → decide):** if no Secret Service is available, do NOT silently fall back to plaintext. Options: OS-derived encryption with a user passphrase, or refuse to persist and require re-entry. Must be an explicit, documented decision at Stage-13.
- **API keys are user-supplied and per-user** — treat as the user's property; provide clear "remove key" that actually purges from the store.
- **Never transmit API keys over the LAN** to controllers; keys live only on the host that talks to the cloud.

---

## 5. Privacy & Consent Requirements

Sermon audio (A2), transcripts (A3), and AI notes (A4) are sensitive and may include third-party (congregation) speech. These are **hard requirements**, not options (addresses T10, T17, T19).

### 5.1 Cloud opt-in & disclosure
- **Cloud processing is OFF by default.** On-device transcription/scripture detection is the default path where feasible.
- **No transcript, audio, or note content is transmitted to any external AI/transcription/TTS provider without an explicit, per-provider, user opt-in action.** (Restates RP-10 privacy mandate.)
- **Visible disclosure before first send:** name the provider, what is sent (audio? text?), that it leaves the local network, and that the user's own API key/account governs it. Persist the consent decision; allow revocation.
- **Live "cloud active" indicator** whenever data is being sent off-device, so operators always know the current posture.
- **Third-party provider terms are outside our control (TB3):** disclose that provider data-handling/retention applies once opted in. **UNKNOWN:** each provider's retention/training-use policy — surface links, don't assert guarantees.

### 5.2 Retention & deletion
- **Configurable retention** for recordings, transcripts, and notes; default to a conservative retention (e.g. do not retain raw audio longer than needed) — exact default **UNKNOWN → product decision**.
- **Reliable deletion:** deleting a recording/transcript/note must remove all copies including derived artifacts and (best-effort) backups; document what deletion does and does not reach (cloud provider copies are outside our control — disclose).
- **Data minimization:** don't persist audio if only the transcript is needed; don't log content.
- **Congregation-privacy notice:** provide guidance/setting acknowledging that capturing service audio may record attendees; recommend churches disclose recording. (Governance item — flag to product/legal.)

### 5.3 Consent-config integrity
- Consent/retention settings (A12) are security-relevant: protect from unauthorized (non-Administrator) change; changes should be audited (T7).

---

## 6. File-Import / Media / Update / Dependency / Backup Notes

- **File import & path traversal (T11):** canonicalize paths; reject `..`, absolute paths, and symlink escapes; for archives/service packs guard against **zip-slip**; extract into a dedicated sandboxed directory; enforce a media-type allowlist; validate declared vs actual type.
- **Unsafe media handling (T12):** prefer memory-safe/maintained decoders; sandbox or isolate decode of untrusted media where feasible; header/size validation before full decode; keep decoders patched. Deep fuzzing of the media pipeline → **Stage-13**.
- **Local AI-model integrity (T13):** verify model files by pinned hash/signature before loading; load only from an app-controlled directory with restricted permissions; reject unexpected/oversized model files.
- **Software update security (T14):** DOCUMENTED best practice — **code-sign all releases** and **sign the update feed + artifacts**, verify signatures before applying, serve over TLS, and enforce **anti-rollback** (minimum-version). Keep signing keys off the distribution host / offline or in an HSM (Sparkle guidance: keys must not be reachable from the web server — [Sparkle docs](https://sparkle-project.org/documentation/)). **Heed CVE-2025-0509** (Sparkle < 2.6.4: signed-update *replacement* bypass) — pin update-framework versions and verify the full artifact, not just feed metadata ([advisory](https://advisories.gitlab.com/pkg/swift/github.com/sparkle-project/sparkle/CVE-2025-0509)). Windows/Linux updaters need equivalent signature verification (WinSparkle/libappupdater-class or platform packaging signatures).
- **Dependency security (T16):** generate an **SBOM**; run automated dependency + CVE scanning in CI; pin versions; review transitive additions; define a patch cadence and a process for security advisories.
- **Backup encryption (T15):** encrypt backups/exports with authenticated encryption; never embed raw API keys in backups (wrap or exclude); warn when exporting to user-chosen/untrusted locations; document the key-management model for backup encryption.

---

## 7. Items Deferred to the Full (Stage-13) Security Review

1. **Actual code review** — this early model saw no implementation (INFERRED throughout). Re-validate every claim against real code.
2. **LAN transport decision** — final choice between TLS-1.3-with-pinning vs. Noise-style app-layer crypto; concrete handshake, key rotation, and cipher suites.
3. **Pairing protocol spec** — exact QR payload format, TTL, single-use enforcement, channel-binding, host-confirmation UX; formal analysis of the pairing handshake.
4. **RBAC matrix** — the definitive command→role authorization table for all seven roles, plus multi-controller conflict resolution (who wins when two operators send conflicting live commands).
5. **Replay/nonce window** — concrete algorithm, clock-skew tolerance, and sequence-state persistence across reconnects.
6. **Linux secret-storage fallback** — decision + implementation when no Secret Service is present.
7. **Media pipeline fuzzing** — decoder attack surface, sandboxing feasibility per platform, format allowlist.
8. **Local AI model provenance** — signing/verification scheme and update path for models.
9. **Update framework hardening** — per-platform updater selection, signature verification depth, key custody/HSM, anti-rollback; regression test against CVE-2025-0509-class bypasses.
10. **Dependency/SBOM baseline** — first full scan; license + CVE posture.
11. **Cloud-provider data-handling review** — per-provider retention/training-use terms; disclosure accuracy; DPA/legal review for congregation audio (privacy/legal, possibly jurisdiction-specific — e.g. two-party consent recording laws).
12. **Deletion completeness** — verify delete reaches all derived + backup copies; define behaviour for cloud-side copies.
13. **Threat modeling of discovery/mDNS** — host advertisement on LAN (spoofing/enumeration) if service discovery is used.
14. **Denial-of-service resilience testing** — the rendering/output isolation guarantee under control-plane load.

---

## Sources (accessed 2026-07-23)
- OWASP Mobile Application Security — Best Practices: https://mas.owasp.org/MASTG/best-practices/
- OWASP Mobile Application Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Mobile_Application_Security_Cheat_Sheet.html
- Certificate pinning overview — Secure Vale: https://securevale.blog/articles/certificate-pinning-in-mobile-apps/
- Android — Security with network protocols: https://developer.android.com/privacy-and-security/security-ssl
- Electron safeStorage API: https://www.electronjs.org/docs/latest/api/safe-storage
- cross-keychain (Keychain/DPAPI/Secret Service): https://github.com/magarcia/cross-keychain
- Sparkle update framework documentation: https://sparkle-project.org/documentation/
- Sparkle EdDSA (Ed25519) signing: https://github.com/sparkle-project/Sparkle
- Sparkle CVE-2025-0509 (signed-update replacement bypass): https://advisories.gitlab.com/pkg/swift/github.com/sparkle-project/sparkle/CVE-2025-0509
