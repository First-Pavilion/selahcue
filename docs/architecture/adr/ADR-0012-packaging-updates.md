# ADR-0012: Packaging and update strategy

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** High
- **Validating spike:** None required for *this* decision. The residual work is per-platform updater **hardening detail**, deliberately deferred to the Stage-13 security review (threat model §7 item 9), not a make-or-break unknown — see §Fallback & validation.
- **Owner:** Software Architect
- **Closes open decision:** none tracked (no OD is open on packaging; this ADR records the §14 architecture stance and discharges FR-155)
- **Grounded in:** `docs/product/prds/SelahCue-PRD.md` (FR-155, FR-176, FR-156, FR-173, NFR-027, NFR-014, NFR-015, NFR-024, CON-2, CON-4), `docs/research/FEASIBILITY.md` §1 (packaging/signing columns; footprint [T2][S1]) + §10 (classification summary — code-signing DOCUMENTED, 0 OBSERVED), `docs/security/reviews/threat-model-draft.md` §1.2 (TB6/A10), §2 (T14, T16), §6 (update security) and §7 (item 9), `docs/architecture/ARCHITECTURE.md` §14, §11

## Decision

A **two-channel, security-first distribution model**:

**Desktop (Windows, macOS, Linux):**

1. **Per-OS signed installers** for first install and for offline/manual distribution: Windows (MSI/NSIS, **Authenticode**-signed), macOS (**notarised** DMG/pkg), Linux (AppImage + deb/rpm + Flatpak). CI builds and signs per platform (Stage 7; ARCHITECTURE §14).
2. **In-app auto-update from a signed feed** with three non-negotiable properties, each a direct control from the threat model (T14, Critical):
   - **Full-artifact signature verification before apply** — the *downloaded binary/package itself* is signature-verified, **not merely the feed metadata**. This is the specific lesson of **Sparkle CVE-2025-0509** (a signed-update *replacement* bypass): trusting feed metadata while failing to re-verify the swapped artifact is exactly the defect we must not reproduce (threat model §6).
   - **Anti-rollback (minimum-version)** — a downgrade below the enforced min-version is rejected, defeating forced-downgrade-to-vulnerable attacks (T14).
   - **Signing keys held off the distribution host** (offline / HSM), so a compromise of the update server cannot mint a valid update (threat model §6; Sparkle key-custody guidance).
   - The updater framework version is **pinned and regression-tested against CVE-2025-0509-class bypasses**; where a platform-native mechanism is used instead (MSIX, pkg, signed deb/rpm repo, Flatpak), it must provide **equivalent** signature verification (threat model §6).

**Mobile controller (Android, iOS/iPadOS):**

3. **App Store / Google Play** distribution, which supplies platform signing, delivery, and update, and is the surface on which the **FR-176** privacy policy + **Apple App Privacy** + **Google Play Data Safety** disclosures are published.

The invariant across both channels: **nothing is installed or updated unless a signature verifies**, and the update mechanism is **subordinate to live-service reliability** — it never blanks, interrupts, or gates the live output or offline operation (NFR-024, NFR-015, CON-2).

This is deliberately a **composite** decision, not a single mechanism pick. The three options in scope (signed-feed auto-update / store-only / manual) are weighed principally for the *desktop* channel; mobile store distribution is treated as a platform-mandated sub-decision (justified below).

## Context

Software update artifacts are asset **A10** and the update/distribution boundary **TB6** is a "classic supply-chain boundary" (threat model §1.2). A malicious or downgraded update is a **Critical** threat (T14): a compromised update is *full host compromise* on the very machine that drives a live service. The forces:

- **Signed updates + anti-rollback are a hard MVP requirement, not a preference.** FR-155 (MVP) mandates: "Updates apply only if signature verifies; downgrade below min-version rejected; heeds Sparkle CVE-2025-0509 class." This ADR must *implement* that, not re-open it.
- **The CVE is specific and instructive.** CVE-2025-0509 (Sparkle < 2.6.4) is a *signed-update replacement* bypass — the update was "signed" yet a different artifact was applied. The threat model's §6 remediation is explicit: **verify the full artifact, not just feed metadata**, and **pin updater-framework versions**. A generic "we sign updates" posture is insufficient; the failure mode is in the *verification depth* and the *updater implementation*.
- **Cross-platform parity is a differentiator, and Linux has no universal store.** Genuine Win/macOS/**Linux** support is SelahCue's headline differentiator (PRD §2, §10, G-2, NFR-014). Any distribution model that is strong on two OSes but weak on Linux undercuts the product's reason to exist. FEASIBILITY §1 records that per-OS packaging is bundler-supported but "**still need OS certs**" on every platform (Tauri/cargo rows [T2]) — packaging is uniform-ish; *signing* is per-OS ceremony.
- **Patch cadence is itself a security control.** The app carries untrusted-input attack surface that will need fast fixes: media/font decoders (FR-173/T12, "keep decoders patched"), platform HW-decode codec elements (CON-4/FR-073), and third-party dependencies flagged by the CI SBOM + CVE scan (NFR-027/T16). The distribution channel must let us push a Critical fix to the whole fleet **quickly**, without a gatekeeper's review queue.
- **Offline-first is inviolable.** All core live functions must run with the network disabled (NFR-015, CON-2). An updater that gates startup, blocks live use when the feed is unreachable, or cannot be turned off would violate this. Updates are opt-outable and always non-fatal on failure.
- **Live output must never be a casualty of an update.** Output-failure isolation (NFR-024) means an update must never apply mid-service or interrupt the render/output path; update checks belong out-of-band and application belongs to a maintenance window (tie-in: pre-service checklist FR-008).
- **Mobile is a consumer-installed controller.** The Flutter controller (ADR-0009) is installed by volunteers on their own phones; the practical, policy-compliant, trust-bearing distribution surface for that is the platform stores, which is also where the mandatory FR-176 data-safety disclosures live.
- **Evidence caveat (honest).** FEASIBILITY contains **0 OBSERVED findings** (§10) — packaging/signing evidence is DOCUMENTED (mature signing tooling: electron-builder [S1]; Tauri bundler / cargo per-OS packaging + OS certs [T2]) and no packaging spike was run. Unlike the performance spikes, this is acceptable: code-signing, notarisation, and signed-feed updaters are well-trodden, vendor-supported, widely deployed ground — the confidence rests on reusing vetted platform mechanisms, not on an unproven end-to-end combination.

## Options considered

The three candidate desktop mechanisms, each judged against T14 (supply-chain integrity), NFR-014 (tri-platform parity), the patch-cadence force, and NFR-015/NFR-024 (offline + output isolation).

### Option A — Per-OS signed installers + signed-feed auto-update (full-artifact verification + anti-rollback); mobile via stores (CHOSEN)

Signed installers for first install/offline distribution, plus an in-app updater that pulls a signed feed, **re-verifies the full downloaded artifact's signature before applying**, enforces a min-version floor, and draws its signing keys from offline/HSM custody. Mobile via App Store/Play.

**Pros**
- **Directly implements FR-155 and the T14 Critical control set** — code-signed releases + signed feed + verify-before-apply + anti-rollback + keys offline (threat model §2/§6). It is the option the requirement and threat model were written for.
- **Answers the CVE-2025-0509 class head-on.** Verifying the *full artifact* (not feed metadata) and pinning + regression-testing the updater framework is precisely the §6 remediation. No other option lets us own that verification depth.
- **Uniform channel across all three desktop OSes** — one signed-feed model on Windows, macOS, and Linux, preserving tri-platform parity (NFR-014, G-2) on the platform (Linux) where store-only coverage is weakest.
- **We control cadence.** A Critical decoder (FR-173/T12), codec (CON-4/FR-073), or dependency-CVE (NFR-027/T16) fix ships to the whole fleet on our timeline, with no store-review latency — cadence *is* a security control here.
- **No store gatekeeper, sandbox, or entitlement constraints** on the desktop app's core needs: multi-monitor borderless-fullscreen output control (ADR-0004), native GStreamer/HW-decode elements + zero-copy interop (ADR-0005/0006), a LAN-listening WebSocket server + mDNS (ADR-0008), and NDI output (ADR-0013). These are exactly the capabilities that OS-store sandboxes constrain (see Option B).
- Composes cleanly with the existing CI posture — Stage-7 per-platform build+sign, plus the NFR-027 SBOM + CVE/license gate on every signed build.

**Cons / accepted costs**
- **We own signing-key custody and update infrastructure** — key generation, **offline/HSM** custody, feed hosting, and rotation. Threat model §6 requires keys off the distribution host; a key compromise is a Critical (A10) supply-chain event. This is security-critical *operational* surface, established at Stage 7, not merely code.
- **We own updater correctness.** CVE-2025-0509 is a bug *in an updater*. Adopting Sparkle/WinSparkle-class frameworks means pinning versions and regression-testing against replacement bypasses (Stage-13 item 9); rolling our own updater would be strictly worse (more bespoke security-critical code). Either way the updater is a high-blast-radius component.
- **Per-platform updater fragmentation** — macOS (Sparkle-class / notarised pkg), Windows (WinSparkle / MSIX / custom), Linux (AppImage self-update / signed deb-rpm repo / Flatpak). Each needs *equivalent* signature verification (threat model §6). Real per-OS engineering and test cost.
- **Anti-rollback constrains legitimate recovery.** A min-version floor that protects against forced downgrade (T14) can also block a needed downgrade away from a bad release. Mitigated by (a) our fast forward-fix cadence — an Option A advantage — and (b) bumping min-version *only* when a security fix mandates it, never routinely.

### Option B — Store-only distribution (Microsoft Store / Mac App Store / Snap/Flathub; App Store/Play for mobile) — REJECTED as sole desktop channel; ADOPTED for mobile

Rely on platform stores to sign, deliver, and update the app on every OS.

**Pros**
- **Lowest key-custody and infrastructure burden** — Apple/Google/Microsoft own the supply-chain boundary (TB6), signing, and delivery; auto-update is handled. This materially shrinks the operational attack surface we run ourselves.
- **Trusted, familiar install UX** for non-technical volunteers; automatic background updates.
- **For mobile this is effectively mandatory and correct** — a consumer-installed controller (ADR-0009) belongs on App Store/Play; store review + the FR-176 privacy policy / Apple App Privacy / Google Play Data Safety disclosures are the required surface. Sideloading/enterprise distribution to a volunteer audience gives worse trust and no disclosure surface.

**Cons (as the sole *desktop* channel)**
- **No universal Linux store.** Snap/Flathub cover part of the ecosystem, not all distros/policies; many church Linux hosts install from downloaded packages. Store-only would open a coverage gap on the exact platform that is SelahCue's differentiator (NFR-014, G-2) — disqualifying as the *sole* channel.
- **Sandbox / entitlement conflicts with core function.** Mac App Store sandboxing (and, to a lesser degree, Microsoft Store/Snap confinement) is a poor fit for a device-driving AV + LAN-server app: exclusive/borderless multi-monitor fullscreen (ADR-0004), native codec/HW-decode elements (ADR-0005/0006), a listening WebSocket server + mDNS advertisement (ADR-0008), and NDI (ADR-0013) all press against store sandbox and entitlement policies. This is a real technical mismatch, not a paperwork one.
- **Store review gates the patch cadence** — the opposite of what a supply-chain-critical, decoder-hardening (FR-173) product wants; a Critical fix could sit in a review queue.
- Revenue share, account/policy dependence, and loss of direct control over the update timeline.

**Disposition:** rejected as the sole desktop channel (Linux gap + sandbox/entitlement conflicts); **adopted for mobile**, where it is effectively mandatory and appropriate. OS app stores may later be offered as an *additional, optional* desktop channel for users who prefer them — but only where the sandbox can be satisfied, and never as the parity-bearing primary path.

### Option C — Manual download + manual install, no auto-update — REJECTED (retained as a fallback path)

Signed installers on the website; the operator downloads and applies updates by hand; no feed, no in-app updater.

**Pros**
- **Simplest to build** — no updater, no feed, no update infrastructure; lowest engineering cost.
- **Smallest auto-update attack surface** — with no updater in the product, there is no CVE-2025-0509-class bug *in our updater* to exploit, and no background network reach (maximally aligned with NFR-015/CON-2 at the extreme).

**Cons**
- **It leaves live-service machines unpatched.** Church volunteers will not reliably track and hand-apply updates; a Critical dependency CVE (NFR-027/T16) or a media-decode vulnerability (FR-173/T12) would linger on production hosts. The security *benefit* of "no updater" is outweighed by the security *cost* of an unpatched fleet — the wrong trade for a supply-chain-critical, always-on app.
- **It does not escape the signing obligation.** FR-155 still requires signature verification on install and anti-rollback semantics even for manually downloaded installers — so we keep the signing ceremony and lose only the safe delivery mechanism.
- **Poor UX**, and it undermines the reliability/hardening posture the rest of the PRD is built on.

**Disposition:** rejected as the primary strategy. Manual signed-installer download is **retained as a deliberate fallback distribution path** — for air-gapped/offline venues, for users who disable auto-update (which must remain possible under NFR-015), and as the per-platform fallback if a chosen updater framework proves unsafe or unmaintained (see §Fallback & validation).

## Consequences

### Positive
- **The Critical supply-chain threat (T14) is controlled to the threat model's own specification** — signed releases + signed feed + **full-artifact** verify-before-apply + anti-rollback + offline/HSM keys, with the CVE-2025-0509 replacement-bypass class specifically designed out.
- **Tri-platform parity on the security property** — one uniform signed-update contract across Windows/macOS/Linux (NFR-014, G-2), with Linux a first-class citizen rather than a store-coverage gap.
- **Fast, self-controlled patch cadence** delivers decoder (FR-173), codec (CON-4/FR-073), and dependency-CVE (NFR-027) fixes to the whole fleet without a review-queue delay — cadence functioning as a live security control.
- **Offline-first is preserved** — auto-update is opt-outable and non-fatal; a live service never depends on the update feed being reachable (NFR-015, CON-2).
- **Mobile disclosures land where they belong** — App Store/Play carry the FR-176 privacy policy + Apple App Privacy + Google Play Data Safety disclosures, and the stores own mobile signing/delivery.

### Negative / accepted costs
- **We run a signing-key-custody and update-hosting operation** (offline/HSM keys, feed, rotation) — a Critical (A10) operational surface with its own compromise blast radius, standing up at Stage 7.
- **The updater is a high-blast-radius component** whose correctness (verification depth, atomic apply, version pinning) must be reviewed and regression-tested against CVE-2025-0509-class bypasses (Stage-13 item 9), not merely feature-tested.
- **Per-platform updater fragmentation** — three delivery mechanisms to build and keep at *equivalent* verification strength (threat model §6).
- **Anti-rollback narrows legitimate downgrade** — mitigated by conservative min-version bumps and fast forward-fix, but a real constraint on recovery flexibility.
- **A parallel mobile release track** (store review cycles, data-safety maintenance) sits on a different cadence than the self-hosted desktop channel.

### What this commits us to
- **CI builds and signs every artifact per platform** (Stage 7; ARCHITECTURE §14), with the **NFR-027 SBOM + CVE/license scan gating each signed build**.
- **Signing keys off the distribution host** (offline/HSM), with a documented key-custody and rotation process owned outside the update server (threat model §6).
- **Full-artifact signature verification before apply**, **min-version anti-rollback**, **atomic apply** (no half-written binary), and **pinned, regression-tested updater frameworks** on all three desktop OSes.
- **Update subordinate to the live service** — no mid-service application; update checks are out-of-band; an unreachable feed or a failed update never blanks or interrupts live output (NFR-024) and never blocks offline operation (NFR-015).
- **Auto-update is disable-able**, and a **manual signed-installer path** stays supported as the offline/fallback channel.
- **Mobile ships through App Store/Play** with the FR-176 disclosures completed and maintained.
- **The same signing/verification discipline is extended to local AI model files** (FR-156/T13, R3) — hash/signature-pinned, verified before load; the *model update path* is an explicit Stage-13 item (threat model §7 item 8), not solved here.

## Fallback & validation

This decision is **High confidence with no validating spike**, and the honesty about *why* matters:

- The confidence rests on **reusing vetted, widely deployed platform mechanisms** — Authenticode, macOS notarisation, and Sparkle/WinSparkle-class signed-feed updaters — rather than a bespoke or unproven end-to-end combination. Code-signing is DOCUMENTED capable (FEASIBILITY §1 [S1][T2], §10 classification summary), and the *controls* are lifted directly from the threat model's §2/§6 recommendations for T14. There is no performance or feasibility unknown of the kind that gates ADR-0002/0006.
- What is **not** yet fixed is per-platform *hardening detail*, and this ADR does not pretend otherwise. Deferred to the **Stage-13** full security review (threat model §7 **item 9 — "Update framework hardening"**): per-platform updater selection, **signature-verification depth**, **key custody/HSM**, anti-rollback mechanism, and a **regression test against CVE-2025-0509-class bypasses**. These are hardening choices with known-good answers, not open feasibility questions — which is why they lower the *implementation* detail owed at Stage 13 without lowering the *architectural* confidence here.

Because there is no spike, the honest risk statement and its **pre-designed fallbacks** are:

1. **Updater-framework risk (per platform).** If a chosen framework (e.g., Sparkle-class) proves unsafe or unmaintained on a given OS, **fall back to that platform's native packaging signature verification** — MSIX / signed pkg / signed deb-rpm repo / Flatpak — which the threat model §6 accepts as *equivalent*. The security property (signed + full-artifact-verified + anti-rollback) is preserved; only the delivery mechanism flexes on that one platform.
2. **Auto-update entirely, per platform.** If in-app auto-update cannot meet the verification bar on some platform, **fall back to the Option C manual signed-installer path** for that platform (with an in-app "update available" prompt). Parity on *safety* is kept; cadence degrades to manual on that platform only.
3. **Key-custody dependency.** Offline/HSM signing-key custody is an **organisational/operational** dependency established at Stage 7; if HSM provisioning slips, the interim fallback is an air-gapped signing host with documented handling — never keys on the distribution server (threat model §6).
4. **Store-channel feasibility (not on the critical path).** Because the desktop primary is self-hosted, Mac App Store / Microsoft Store sandbox feasibility does **not** gate this ADR. If an OS store channel is added later, it needs its own entitlement/sandbox spike against the ADR-0004/0005/0006/0008/0013 capability set before it is offered.

In every branch the invariant holds — **no install or update without a verified signature, and anti-rollback enforced** — and only the delivery mechanism varies per platform. That is why "High" is warranted: the decision's failure modes each have a ready, requirement-compliant answer, and the unresolved parts are hardening specifics owed to Stage-13, not existential unknowns.

## Requirement / PRD references

| Ref | Requirement | How this ADR satisfies it | Threat |
|---|---|---|---|
| FR-155 | Signed updates + signature verification + anti-rollback (MVP) | Signed per-OS installers + signed feed; **full-artifact** signature verified before apply; min-version anti-rollback; heeds CVE-2025-0509 | T14 |
| FR-176 | Privacy policy + app-store data disclosures (MVP) | Mobile via App Store/Play with privacy policy + Apple App Privacy + Google Play Data Safety | — |
| FR-156 | Local AI-model integrity before load (R3) | Same signing/verification discipline extended to model files; model *update path* deferred to Stage-13 item 8 | T13 |
| FR-173 | Untrusted media/font decode hardening — patch cadence (MVP) | Self-controlled fast update cadence delivers decoder patches to all three OSes | T12 |
| CON-4 / FR-073 | Platform/HW-decode-only codec path | Codec-element security fixes shipped through the same controlled channel | T12 |
| NFR-027 | Dependency security / SBOM + CVE + license scan in CI (MVP) | SBOM + CVE/license scan gates each signed build; cadence delivers dependency patches | T16 |
| NFR-014 / G-2 | Cross-platform parity; genuine Win/macOS/Linux | One uniform signed-update channel across all three desktop OSes (Linux first-class) | — |
| NFR-015 / CON-2 | Offline operation | Auto-update opt-outable; never gates startup/live use; unreachable feed is non-fatal | — |
| NFR-024 | Output-failure isolation | Updates never applied mid-service; never blank or interrupt live output | — |

**Assets / boundaries:** A10 (software update artifacts), TB6 (update/distribution boundary), A9 (local AI models — FR-156 extension), A11/A5 (backups/keys — kept out of update artifacts).

**Related ADRs:** ADR-0008 (LAN protocol/security — sibling supply-chain/security posture; T14 cross-referenced there), ADR-0009 (Flutter controller — the store-distributed mobile artifact carrying FR-176 disclosures), ADR-0005 / ADR-0006 (media/codec + HW-decode path patched via this channel — CON-4/FR-073), ADR-0013 (NDI — a capability that store sandboxes would constrain, reinforcing the self-hosted desktop choice), ADR-0011 (observability — redacted diagnostics carry no keys/secrets), ADR-0001 (Rust core / cargo per-OS packaging). Full architecture context: `ARCHITECTURE.md` §14 (Packaging & updates), §11 (Security).
