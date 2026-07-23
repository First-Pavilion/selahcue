# ADR-0009: Mobile controller framework

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** Medium
- **Validating spike:** S9 — mobile-framework background LAN-discovery reliability (iOS especially): Flutter vs React Native vs native background-Bonjour test
- **Owner:** Software Architect (decision) · Mobile (spike + iOS background-discovery risk)
- **Related:** ADR-0008 (LAN protocol & transport security — this app implements the client side), ADR-0012 (packaging & updates — mobile via App Store / Play, FR-176), ADR-0001 (desktop-authoritative Rust core)
- **Grounded in:** `docs/research/FEASIBILITY.md` §5 (mobile-controller options), §6 (discovery/pairing), §10 (spike S9); finding [MO1]. `docs/product/prds/SelahCue-PRD.md` EPIC-J (FR-085..094, FR-097/098), FR-176, NFR-009/010/014/017/026, CON-1, AS-1. `docs/architecture/ARCHITECTURE.md` §3, §5, §16 (iOS background-mDNS risk row), §17 (escalated Medium-confidence ADR).

## Context — the forces

The companion controller is a **single-codebase mobile app for Android and iOS/iPadOS** that speaks to the authoritative desktop host over the LAN (ARCHITECTURE §3/§5). What it actually has to be is narrow, and what it has to *do* underneath is not:

- **Functionally thin, per AS-1.** The controller is a *feature*-thin surface: discover/pair, see current+next previews and navigate the plan (FR-092), issue role-scoped slide/clear/blackout requests (FR-093), and drive timers/TIME UP (FR-094). In UI terms this is "lists, buttons, a socket, and a preview raster" — the very definition of a **standard app** in FEASIBILITY §5 ("A LAN remote is a *standard* app (lists, buttons, a socket)").
- **But it ships two hardened subsystems (AS-1).** Thin UI notwithstanding, the controller carries the **client half of the ADR-0008 secure transport** — mDNS/QR discovery (FR-085), QR pairing with host confirmation (FR-086), pinned-TLS 1.3 session establishment with **custom trust evaluation** of a self-signed host cert (FR-088), a **device keypair + token in the OS secret store** for proof-of-possession and revocation (FR-089), and replay-safe reconnection with no ghost actions (FR-097). RBAC itself is enforced server-side on the host (FR-090), so the app only *requests*; it never decides authorization.
- **The OS-sensitive pieces need native code regardless of framework.** Two of those subsystems touch platform primitives no cross-platform runtime fully abstracts: **mDNS/DNS-SD discovery** (Bonjour/NSD) and the **secure keystore** (iOS Keychain / Android Keystore, per NFR-017 and ADR-0008's "mobile Keystore/Keychain" placement). This is why the decision line reads "platform channels for mDNS + secure keystore": whichever cross-platform framework we pick, these are bridged to native, not written once in portable code.
- **Discovery must survive real church Wi-Fi.** mDNS is single-LAN-only and frequently blocked by AP/guest isolation and multicast filtering (FEASIBILITY §6, DOCUMENTED capability / INFERRED church-network reliability). ADR-0008 already carries a **QR-only discovery fallback** for that case (FR-085) — a decision-level mitigation the framework choice inherits.
- **iOS background discovery is an OS-level constraint, not a framework one.** On iOS, custom multicast/Bonjour browsing requires Apple's multicast-networking entitlement and the local-network privacy grant, and background execution is aggressively suspended — so reliable service discovery is effectively a **foreground** activity. *(INFERRED from platform behaviour; FEASIBILITY §10 flags this only as "background LAN discovery reliability (iOS especially)" and makes it the reason S9 exists.)* Crucially, **switching frameworks does not remove this ceiling** — it binds any Flutter, React Native, or even native app equally. ARCHITECTURE §16 records the mitigation as QR-only pairing + foreground-discovery, owned by Mobile.
- **Low, steady footprint over long services.** The app runs beside a service for hours; command latency must stay ≤200 ms on LAN (NFR-009) and memory must not creep over a long session (NFR-010 posture). FEASIBILITY §5 flags that React Native "memory grows more; needs iOS tuning [MO1]" while Flutter shows "fastest startup; steady memory [MO1]".
- **Must be publishable to both stores with completed privacy disclosures (FR-176).** The single codebase must produce store-compliant iOS and Android builds carrying Apple App Privacy + Google Play Data Safety disclosures (ADR-0012).
- **Bounded blast radius (CON-1, FR-098).** The desktop is authoritative; the controller holds **no** live state. A wrong framework choice can at worst make the *controller* worse — it can never blank output or disable a desktop capability (FR-098, NFR-024). This is why a **Medium**-confidence, spike-gated decision here is acceptable in a way it would not be for the render/output core.

The evidence base for the framework comparison itself is modest and I treat it as such: FEASIBILITY §5's performance multipliers come from a **single secondary blog [MO1]** and are classified **DOCUMENTED (Med) — "treat as directional."** Its headline conclusion is the load-bearing one: *"By mid-2026 both Flutter & RN closed historic perf gaps; equivalent for standard apps"* — i.e. for this app class, raw performance is **not** the deciding axis; developer velocity and a single codebase are.

## Options considered

### Option A — Flutter (single codebase; platform channels for mDNS + secure keystore) — **CHOSEN**

*How it fits:* one Dart/Flutter codebase for the entire UI (plan/preview/control), the WebSocket-over-TLS client (ADR-0008), and connection-state logic; **thin platform channels** bridge to native for the two OS-sensitive subsystems — mDNS/DNS-SD discovery and the Keychain/Keystore secret store.

**Pros (evidence-based):**
- **Best-fit for a "standard app" where velocity + one codebase dominate.** FEASIBILITY §5 concludes that for a LAN remote, "developer velocity + one codebase matter more than raw perf" once the perf gap has closed [MO1]. Flutter delivers that with a mature widget toolkit for the lists/buttons/preview surface (FR-092/093/094).
- **Steady memory and fast startup** [MO1] suit a controller that lives alongside a multi-hour service and must feel instant (NFR-009 ≤200 ms tap→act on LAN) without memory creep (NFR-010 posture). This is the concrete axis on which §5 separates it from React Native, whose "memory grows more; needs iOS tuning."
- **WebSocket-handling headroom.** FEASIBILITY §5 cites isolate-parallelised message parsing and a directional "~2.7× faster WS message handling vs RN, avoids JS-thread saturation" [MO1]. *(DOCUMENTED-secondary / directional — not a measured guarantee; carried into S9 rather than relied on.)* It is at worst neutral and at best a margin for the preview/transcript streams the same channel carries (ADR-0008).
- **Adequate native access via plugins** for mDNS and sockets (FEASIBILITY §5: "Good via plugins"), which is sufficient to build the ADR-0008 client, with the genuinely native bits isolated behind platform channels.
- **One store-publishable codebase** for both Apple and Google, easing the FR-176 privacy-disclosure and ADR-0012 packaging obligations versus maintaining two.

**Cons / risks (evidence-based):**
- **"Single codebase" is qualified.** The two highest-security subsystems — mDNS discovery and the secure keystore — are **native platform-channel code on each OS**, so Flutter does not eliminate per-platform native work; it isolates it. This is stated in the decision line, not hidden.
- **Custom-trust TLS pinning must work through Flutter's TLS stack.** ADR-0008 Option A's standing con — "pinning a self-signed cert requires custom trust evaluation on the mobile side; some platform TLS stacks make custom-trust awkward" — lands **here**. This is precisely the mobile-trust/pinning risk ADR-0008 defers to S9, and it is a real reason confidence is Medium.
- **The iOS background-discovery ceiling applies.** Flutter cannot lift the OS-level foreground restriction on multicast discovery (see Context). The product answer is the QR-only + foreground-discovery mitigation (ARCHITECTURE §16), not the framework.
- **The comparative evidence is thin and secondary** [MO1] — a single blog benchmark. The choice between Flutter and React Native is genuinely close on the evidence; S9 must confirm the plugin/platform-channel path to background discovery, custom-trust pinning, and keystore is adequate before this hardens.

### Option B — React Native — **REJECTED (secondary cross-platform alternative)**

*How it fits:* one JS/TS codebase; native modules bridge discovery, keystore, and TLS pinning.

**Pros (evidence-based):**
- Single codebase, same core benefit as Flutter.
- **Strongest native-module ecosystem.** FEASIBILITY §5: New Architecture "removed bridge jank; strong native-module ecosystem for BLE/NFC/network [MO1]" with "Excellent native-module access." Because our hardest pieces are native (mDNS, keystore, pinning), a richer native-module story is a genuine point in RN's favour — and the reason RN, not native, is the *secondary cross-platform* alternative.
- Perf "equivalent for standard apps" by mid-2026 [MO1].

**Cons (evidence-based):**
- **Memory growth + iOS tuning burden.** FEASIBILITY §5: "Memory grows more; needs iOS tuning [MO1]" — a direct mark against the steady-footprint posture (NFR-010) for a controller that runs the length of a service. Flutter's "steady memory" is the cleaner default.
- **JS-thread saturation risk under WS load** [MO1] (mitigated by New Architecture, but not eliminated) versus Flutter's isolate parallelism — directional, but it points the same way.
- No decisive win: its native-module edge is real but only matters *if* Flutter's platform-channel access to the same primitives proves insufficient — which is exactly the S9 question. Absent that, its footprint/tuning cost tips a close call to Flutter.

**Disposition:** kept as the **secondary cross-platform alternative**. If S9 shows the problem is *Flutter-plugin-specific* (a native primitive is reachable from an RN native module but awkward from a Flutter plugin) rather than OS-level, RN is the cheaper pivot than going native, because it keeps a single codebase. It is not the primary fallback (see Option C and the brief's directive).

### Option C — Native Swift + Kotlin (per-platform) — **FALLBACK**

*How it fits:* two separate native apps — Swift/SwiftUI on iOS, Kotlin on Android — each using first-class platform APIs directly.

**Pros (evidence-based):**
- **Best raw control of exactly the pieces that are hard here.** FEASIBILITY §5: "Best raw control (NWListener/NSD, Bonjour first-class). Lowest memory [MO1]" and "Best (Bonjour/NSD native)" LAN/mDNS access — plus the cleanest path to platform TLS custom-trust (the ADR-0008 pinning risk) and to Keychain/Keystore. Highest perf.
- Native code has the **most headroom** for the iOS background-discovery constraint (entitlements, background-task APIs) — though it is still OS-bounded, not exempt.

**Cons (evidence-based):**
- **Two codebases** — FEASIBILITY §5 marks native "❌ two codebases," directly contradicting the single-cross-platform-controller goal (ARCHITECTURE §3/§5).
- **Poor ROI for a feature-thin controller.** AS-1 makes the controller deliberately thin; doubling the build/test/maintenance surface of the UI + connection logic to gain native access to a handful of primitives is disproportionate — *unless* the cross-platform route to those primitives genuinely cannot meet the security/discovery bar.

**Why fallback, not primary:** it buys first-class native discovery/keystore/pinning at the cost of two codebases. We do **not** pay that up front for a thin controller; we hold it as the S9-gated fallback for the case where cross-platform plugin/platform-channel access to the OS primitives proves fundamentally inadequate on a platform (most plausibly iOS). This matches the brief's directive to record a native-per-platform fallback.

## Decision

Build the SelahCue mobile controller as a **single Flutter codebase**, with the two OS-sensitive subsystems — **mDNS/DNS-SD discovery** and the **secure keystore** (device keypair/token, NFR-017) — implemented behind **thin native platform channels** on each platform. The app is the **client of ADR-0008**: it performs mDNS/QR discovery (FR-085), QR pairing (FR-086), pinned-TLS 1.3 session establishment with custom trust of the self-signed host cert (FR-088), keypair-bound proof-of-possession (FR-089), and replay-safe reconnection (FR-097) — and it holds **no authoritative state** (CON-1, FR-098). Authorization is server-side on the host (FR-090); the app only issues role-scoped requests.

Confidence is **Medium**, gated on **spike S9**, with **native Swift + Kotlin per-platform (Option C) as the pre-designated fallback** and React Native as a secondary cross-platform alternative if the shortfall is Flutter-plugin-specific rather than OS-level. This is one of the two ADRs ARCHITECTURE §17 escalates as Medium-confidence and spike-gated.

## Consequences

### Positive
- **Fastest route to a single, store-publishable controller** for Android + iOS (FR-176, ADR-0012), aligning with FEASIBILITY §5's conclusion that velocity + one codebase dominate for this app class [MO1].
- **Steady memory + fast startup** [MO1] protect the NFR-009 latency feel and NFR-010 long-session footprint posture better than the React Native default.
- **Native complexity is contained**, not eliminated: mDNS and keystore live in small, auditable platform channels, keeping the security-critical surface (which must be reviewed/fuzzed per ADR-0008) small and explicit.
- **Bounded blast radius:** because the desktop is authoritative and the controller holds no live state, even a poor framework outcome cannot blank output or disable the desktop (FR-098, NFR-024) — the reason a Medium-confidence pick is tolerable here.

### Negative / accepted costs
- **We own per-platform native code anyway** — the mDNS and keystore platform channels (and the custom-trust TLS-pinning glue) must be written and hardened twice, so the "single codebase" benefit is real but partial.
- **The mobile custom-trust pinning risk from ADR-0008 lands on this framework** and is unproven until S9; a pinning defect is a direct security regression (ADR-0008 §Consequences), so this code is security-critical, not merely feature code.
- **The iOS background-discovery ceiling remains** and is not solved by the framework; the product depends on the QR-only + foreground-discovery mitigation (ARCHITECTURE §16) for that case.
- **The comparative evidence is a single secondary source** [MO1]; the Flutter-vs-RN margin is thin, so the decision is explicitly provisional pending S9.

### What this commits us to
- **Implementing the ADR-0008 client contract in Flutter** — pinned TLS 1.3, keypair-bound tokens, nonce/timestamp replay-safe reconnection, strict handling of server-rejected/stale actions (no ghost actions, FR-097) — with the app-layer auth kept **transport-agnostic** so ADR-0008's Noise fallback remains viable without a rewrite.
- **Secrets only in the OS secret store** (Keychain/Keystore) via the platform channel, never in Dart-side plaintext or logs (NFR-017; ADR-0008 §Consequences).
- **QR-only + foreground discovery** as the always-present path for multicast-blocked networks and iOS background limits (FR-085; ARCHITECTURE §16).
- **Store-compliance obligations:** Apple App Privacy + Google Play Data Safety disclosures and a shipped privacy policy for the mobile app (FR-176, ADR-0012).
- **Mobile accessibility baseline:** accessible labels + ≥44×44 pt touch targets on MVP controls (NFR-026) — supported by Flutter's accessibility APIs, to be verified.
- **Keeping the native-per-platform fallback (and the RN secondary) genuinely open** until S9 reports, i.e. not designing the client in a way that assumes Flutter-only capabilities beyond the platform-channel boundary.

## Fallback & validation

- **Confidence is Medium precisely because S9 has not run and the comparative evidence is thin/secondary [MO1].** No single component is doubtful in isolation; the open questions are (a) whether Flutter's plugin/platform-channel access to **background LAN discovery**, **custom-trust TLS pinning**, and the **secure keystore** is adequate on each OS — iOS most at risk — and (b) whether the directional perf/memory advantages hold in practice.
- **Validating spike: S9** (FEASIBILITY §10) — Flutter vs React Native vs native background-Bonjour test, measuring background/foreground discovery reliability on real church-network conditions, custom-trust pinned-TLS session establishment end-to-end (jointly with ADR-0008's S6), keystore integration, and command latency (NFR-009) + memory over a soak-length session (NFR-010).
- **Pre-designed fallback #1 (discovery / iOS background):** already in the decision — **QR-only pairing + foreground discovery** (FR-085; ARCHITECTURE §16). This removes the multicast/background dependency without changing the framework, so the iOS background risk does **not** by itself lower framework confidence.
- **Pre-designed fallback #2 (framework):** if S9 shows Flutter's platform-channel access to the OS primitives is fundamentally inadequate on a platform, **drop to native Swift + Kotlin per-platform (Option C)** for the first-class Bonjour/NSD, platform TLS-trust, and Keychain/Keystore access, accepting two codebases for the feature-thin controller. If instead the shortfall is Flutter-plugin-specific rather than OS-level, **React Native (Option B)** is the cheaper pivot that preserves a single codebase.
- Both fallbacks are engineered in advance, and the app-layer contract is kept transport- and framework-agnostic (dovetailing with ADR-0008's Noise fallback), so each failure mode has a ready, requirement-compliant answer.

## Requirement / PRD references

| Ref | Requirement | Relevance to this ADR |
|---|---|---|
| FR-085 | Discover hosts (mDNS + QR-only fallback when multicast blocked) | mDNS via platform channel; QR-only fallback is fallback #1 |
| FR-086 | QR pairing with host-side confirmation | Client scans/pairs; host confirms |
| FR-087 | Remember hosts + secure reconnection (no fresh QR) | Pinned fingerprint + device proof-of-possession (keystore) |
| FR-088 | Encrypted, authenticated LAN transport | Pinned TLS 1.3 client through Flutter's TLS stack (custom-trust risk → S9) |
| FR-089 | Per-device revocable keypair-bound tokens | Device keypair/token in Keychain/Keystore via platform channel (NFR-017) |
| FR-090 | Server-side RBAC (deny-by-default) | Enforced on host; the app only issues role-scoped requests |
| FR-091 | Replay protection + rate limiting | App honours nonce/timestamp window on reconnect |
| FR-092/093/094 | Mobile preview/nav, slide/clear/blackout, timer/TIME UP (role-scoped) | The thin UI surface this framework renders |
| FR-097 | Graceful reconnection, no ghost actions | Stale/queued actions discarded on reconnect |
| FR-098 | Loss of all mobile never disables desktop | No authoritative state on device → bounded blast radius (CON-1) |
| FR-176 | Privacy policy + app-store data disclosures | Single Flutter codebase → Apple/Google store builds + disclosures (ADR-0012) |
| NFR-009 | Mobile-command latency ≤200 ms on LAN | Startup/memory/WS-handling characteristics [MO1] |
| NFR-010 | Long-run memory stability | Flutter steady memory vs RN growth [MO1] |
| NFR-014 | Cross-platform parity | Single codebase → identical Android/iOS behaviour |
| NFR-017 | OS-secret-store-only secrets | Keystore platform channel; no Dart-side plaintext |
| NFR-026 | Mobile-controller accessibility | Accessible labels + ≥44×44 pt targets via Flutter a11y APIs |
| CON-1 / AS-1 | Desktop-authoritative; feature-thin controller w/ two hardened subsystems | Frames why velocity/one-codebase win and blast radius is bounded |

**Feasibility evidence:** FEASIBILITY §5 (mobile-controller trade-off table: Flutter / React Native / Native rows; "standard app" conclusion), §6 (mDNS single-LAN limits + QR fallback), §10 spike **S9**; finding **[MO1]** (`synergyboat.com` Flutter-vs-RN-vs-native benchmark, `videosdk.live` WS-on-RN — DOCUMENTED-secondary, directional). **Related ADRs:** ADR-0008 (LAN protocol & security — client contract, mobile-trust/pinning risk → S9), ADR-0012 (mobile packaging via app stores), ADR-0001 (desktop-authoritative core). **Architecture context:** ARCHITECTURE §3, §5, §16 (iOS background-mDNS risk → QR-only/foreground fallback, Mobile-owned), §17 (escalated Medium-confidence, spike-gated ADR).
