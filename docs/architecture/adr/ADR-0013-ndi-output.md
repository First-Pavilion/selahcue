# ADR-0013: NDI output inclusion

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** Medium — the licensing *terms* are OBSERVED/High from primary sources, but integration effort is INFERRED/Med and legal acceptance of the NDI 6.x EULA is an **external, still-open gate** (OD-06/08; §17). We do not overstate this to High.
- **Validating spike:** None mandated. NDI is an **R2** capability, so no spike blocks MVP. An optional thin integration spike is described in Fallback/validation; the make-or-break unknown here is legal acceptance, not technical feasibility.
- **Owner:** Software Architect (technical) · legal/compliance accepting authority outside the engineering roster owns the licence acceptance (§27; FR-140)
- **Related:** ADR-0002 (wgpu compositor / output frames), ADR-0004 (windowing & multi-output), ADR-0005 (media engine & codec safe harbor), ADR-0008 (LAN protocol — NDI publishes onto the LAN), ADR-0012 (packaging, signed updates, keep-runtime-current)

---

## Context

SelahCue must interoperate with the live-production ecosystem churches and conferences already run — OBS, vMix, ATEM, Bitfocus Companion/Stream Deck. The PRD and market analysis treat this as **table-stakes, not a nicety**: the competitive gap SelahCue targets includes "first-class ecosystem interop (NDI/alpha, transparent browser-source, Companion/Stream Deck)" (PRD §1), and the competitor matrix lists NDI among the "ecosystem table-stakes" that FreeShow — the strongest free challenger — already ships (PRD §5). Omitting NDI cedes a differentiator to an incumbent that is free.

The forces driving this decision:

1. **Explicit requirement.** FR-140 (R2) — "NDI output with required attribution + License-ID compliance"; acceptance: "NDI output publishes to the LAN; UI shows ndi.video attribution; runtime kept current" (LICENSING §2.6; carried Stage-2 condition C14). This ADR exists to accept, or reject, exactly that requirement's obligations.

2. **Adjacent output requirements it interlocks with.** FR-048 (R2) exposes a transparent output for external compositors as "a transparent HTML/URL **or** NDI-alpha feed keyable in OBS/vMix" — so NDI is one of two named ways to satisfy it. FR-141 (R2) is the browser-source (transparent HTML/URL) endpoint. FR-052 (R2) is a dedicated transparent lower-third output for key/fill or browser-source. NDI, browser-source, and transparent HTML are a **family** of R2 external-feed capabilities, not a single choice; this ADR decides the NDI member of that family.

3. **Architectural placement.** NDI is an **additional output sink**, not a new render path: the Output manager owns "the NDI sink (R2)" fed by the same wgpu-composited frames as the physical outputs (Architecture §4, §6). It publishes onto the LAN the LAN control server already secures (ADR-0008).

4. **Licensing obligations are hard constraints, evaluated by an external authority.** The NDI SDK is royalty-free but carries redistribution obligations (attribution near use, a License-ID for NDI 6, keep-the-runtime-current) and an explicit codec-liability shift onto the licensee. Per PRD §27, a legal/compliance reviewer **outside the engineering roster** is the accepting authority for FR-140. The NDI 6.x EULA is on the "legal-confirmation, gate-later" list (PRD §29; §17) and must be re-read for any 2025 commercial-use tightening before ship (LICENSING-REGISTER §2.6, item 8 — Med).

5. **Codec-patent posture (CON-4 / OD-08a).** SelahCue deliberately confines encumbered codecs to OS-native/HW decoders and bundles no encumbered software codec (ADR-0005). NDI's licence **explicitly states that AAC/H.264/H.265 licensing is the licensee's responsibility** — i.e. codec liability is ours. This intersects directly with the safe harbor and must be reconciled, not glossed over.

The evidence base is unusually strong for a licensing decision: the NDI terms are **OBSERVED/High** in the LICENSING-REGISTER §2.6 (read directly from the NDI License Agreement, Nov 2024, and docs.ndi.video) and **DOCUMENTED/High** in FEASIBILITY §4 [N1]. What is *not* settled is (a) integration effort (INFERRED/Med) and (b) whether the current 6.x EULA is accepted by legal.

## Options considered

### Option A — Bundle the NDI redistributable and ship NDI output in R2 (chosen)

**Pros**
- **Meets a documented table-stake and a named requirement.** Directly satisfies FR-140 and the NDI-alpha branch of FR-048; delivers the "first-class NDI/alpha" differentiator the product is positioned on (PRD §1, §5).
- **Royalty-free with an explicit redistribution grant.** "May bundle the NDI **redistributable** object code in your installer for free or commercial products" — OBSERVED/High (LICENSING-REGISTER §2.6). There is no per-seat NDI fee, so this does not compromise the pricing posture.
- **Feasible as an output sink.** FEASIBILITY §4 classes NDI output as "Feasible & royalty-free SDK" (DOCUMENTED/High for terms); it consumes the frames the compositor already produces (Architecture §6), so it adds a sink, not a second render pipeline.
- **Native NDI is what the ecosystem expects.** vMix/ATEM/Companion/NDI-Tools workflows route *NDI*, not browser sources; a network-discoverable AV transport across machines is precisely what browser-source and virtual-camera cannot provide.

**Cons (all grounded in LICENSING-REGISTER §2.6 [OBSERVED/High] and FEASIBILITY §4 [N1])**
- **Standing redistribution obligations:** attribution/link to ndi.video **near every place NDI is used/selected in the UI**, on the website, and in docs; a **License-ID** for NDI 6; and a **reasonable effort to keep the redistributed runtime up to date** (a security *and* a licence obligation — ADR-0012).
- **Not open source.** Only the NDI **header files** are MIT; the SDK **binaries are under the NDI licence** (FEASIBILITY §4 [N1]). This adds a proprietary, non-OSS binary to the SBOM and third-party-notices file (NFR-027; LICENSING-REGISTER §2.6 note 5).
- **Codec liability is ours.** NDI explicitly places AAC/H.264/H.265 licensing responsibility on the licensee (OBSERVED/High). If NDI|HX (which uses H.264/HEVC) is enabled we inherit those codec obligations directly — a live tension with CON-4/OD-08a.
- **External legal gate not yet closed.** The 6.x EULA must be re-read and accepted by the compliance authority before ship (§17, §27; OD-06/08; LICENSING-REGISTER §2.6 item 8).
- **Integration effort is INFERRED/Med**, not measured — no OBSERVED evidence in this repo (FEASIBILITY §4, §10 classification summary: 0 OBSERVED).

### Option B — Omit NDI entirely

**Pros**
- Zero NDI licensing surface: no attribution obligation, no License-ID, no keep-current duty, no proprietary binary, no codec-liability shift; smaller SBOM and simpler packaging/signing (ADR-0012).

**Cons**
- **Fails a table-stake the product is explicitly positioned to beat.** FreeShow (free) ships NDI; ProPresenter ships NDI. Omitting it concedes the "first-class NDI/alpha" differentiator (PRD §1, §5) to cheaper/free incumbents.
- **Leaves FR-140 unmet** and weakens FR-048 (removes the NDI-alpha branch, leaving only the transparent-HTML branch).
- Cross-machine AV routing (the core NDI value) has no clean substitute in SelahCue's stack.
- **Verdict:** rejected — it trades away a positioning pillar to avoid an obligation that the evidence shows is manageable and royalty-free.

### Option C — Browser-source / transparent-HTML output only (no NDI)

**Pros**
- Satisfies FR-141 and the transparent-HTML branch of FR-048 via an OBS/vMix **browser source**, which FEASIBILITY §4 confirms is feasible "via NDI, **or** by exposing an output as a virtual camera / an HTTP/WebRTC surface" (INFERRED/Med).
- No NDI SDK, no NDI licence, no proprietary NDI binary; avoids the codec-liability shift.

**Cons**
- **A browser source is not NDI.** It covers on-machine OBS/vMix HTML ingestion but not the network-discoverable, multi-machine AV transport that ATEM/vMix/Companion/NDI-Tools workflows expect — the specific capability NDI provides.
- **Still leaves FR-140 unmet** (FR-140 names NDI specifically); it only reframes FR-048/FR-141 around the HTML path.
- **Verdict:** kept — not as a rejection of NDI, but as the **documented fallback** if the legal gate closes against NDI (see Fallback/validation). Browser-source/transparent-HTML is complementary to NDI (both are R2), so we ship the HTML path regardless; Option C is what "NDI-less R2" looks like if legal declines.

## Decision

**Accept the NDI SDK and ship NDI output in R2**, on the following terms:

- Bundle the **NDI redistributable object code** (permitted royalty-free for commercial products per the NDI License Agreement) as an **additional output sink** in the Output manager (Architecture §4, §6), fed by the wgpu-composited output frames (ADR-0002) and publishing onto the LAN (ADR-0008).
- Discharge the redistribution obligations as product invariants: (1) **attribution** — a link to ndi.video shown near every NDI use/selection in the UI, on the website, and in docs; (2) **License-ID** — obtain and embed the NDI 6 License-ID; (3) **keep-current** — track upstream NDI runtime releases and update on a defined cadence via the signed update feed (ADR-0012).
- **Gate the ship on the external legal/compliance authority accepting the current NDI 6.x EULA** (§27; OD-06/08). NDI ships in R2 only after that acceptance is recorded; because NDI is R2, this gate does not block MVP.
- **Reconcile codec liability with CON-4.** Standard NDI (SpeedHQ) carries the licensee's general codec responsibility; **NDI|HX (H.264/HEVC) inherits the encumbered-codec obligations directly.** Default to standard NDI; if HX is ever enabled, route it through the same OS-native/HW-decode safe-harbor posture as ADR-0005 and record it in the licence register — never bundle an encumbered software codec to serve NDI.
- **Record NDI in the SBOM/third-party-notices and the licence register** (NFR-027; LICENSING-REGISTER §2.6; RP-10/RP-11 registers).

**Invariants (not spike-gated):** attribution-near-use; License-ID embedded; runtime kept current; NDI binary listed in SBOM/notices; no encumbered software codec bundled for NDI; NDI sink isolated so its failure never blanks a physical output (NFR-024).

## Consequences

**Positive**
- Satisfies FR-140 and the NDI-alpha branch of FR-048; delivers the ecosystem interop the product is positioned on (PRD §1, §5), at **no royalty cost**.
- NDI reuses the existing composited frames and the secured LAN — an additive sink, not a new pipeline or a new network surface.
- Terms are OBSERVED/High from primary sources, so the compliance path is concrete and auditable rather than speculative.

**Negative / costs**
- Adds a **proprietary, non-OSS binary** (only headers are MIT) to the packaged product, SBOM, and notices file — an ongoing supply-chain and update obligation (ADR-0012, NFR-027).
- **Standing obligations forever after ship:** attribution placement, License-ID management, and a keep-current duty that couples our release cadence to NDI's.
- **Codec liability sits with us** by the NDI licence's explicit terms — a real, if bounded, exposure that must be managed against CON-4/OD-08a, especially for NDI|HX.
- **The decision is contingent** on an external legal acceptance that is not yet closed (§17); confidence is therefore Medium, not High.

**Commitments**
- Surface ndi.video attribution near every NDI use in the UI, on the website, and in docs (FR-140 acceptance).
- Obtain, embed, and manage the NDI 6 License-ID; keep the redistributed runtime current via the signed, anti-rollback update feed (ADR-0012).
- Isolate the NDI sink on the output-failure-isolation boundary: an NDI encode/publish fault holds/degrades that sink only and never blanks or clears a physical output (NFR-024, FR-160).
- Enter the legal acceptance and codec-liability assessment into the licence register (RP-10/RP-11; LICENSING-REGISTER §2.6) and obtain the outside-roster compliance sign-off before R2 ship (§27).

## Fallback / validation

- **No technical spike is mandated.** NDI output as a sink is DOCUMENTED-feasible (FEASIBILITY §4 [N1]); the residual technical unknown is integration effort (INFERRED/Med), and NDI's R2 timing means it never sits on the MVP critical path. An **optional thin integration spike** — publish one composited output as an NDI source, confirm discovery/keying in OBS and vMix, and verify the attribution placement satisfies the licence — would convert the INFERRED/Med effort estimate to OBSERVED before R2 build; it is a nice-to-have, not a gate.
- **The make-or-break unknown is legal, not technical.** Confidence is Medium because the NDI 6.x EULA acceptance (§17, §27; OD-06/08) is still open and the codec-liability clause must be reconciled with CON-4.
- **Fallback if the legal gate closes against NDI** (EULA declined, License-ID terms unacceptable, or codec liability judged unacceptable): fall back to **Option C** — ship the transparent-HTML/browser-source output (FR-141, and the HTML branch of FR-048) plus, if needed, a virtual-camera / HTTP/WebRTC surface (FEASIBILITY §4), and **scope FR-140 (NDI) out of R2** pending resolution. This still serves OBS/vMix ingestion via the HTML path, so external-compositor interop degrades but does not disappear. Because both NDI and browser-source are R2, this fallback does not touch MVP.

## Requirement / PRD references

- **Functional:** FR-140 (NDI output + attribution + License-ID + keep-current, R2 — the subject of this ADR), FR-048 (transparent/browser-source or NDI-alpha feed for OBS/vMix, R2), FR-141 (browser-source transparent HTML/URL endpoint, R2), FR-052 (dedicated transparent lower-third output, R2), FR-160 (output-failure recovery), FR-073 (platform/HW-decode-only — bears on NDI|HX codec path).
- **Constraints / policy:** CON-4 & OD-08a (codec-patent safe harbor — the NDI codec-liability clause intersects here), NG-3 (no bundling codecs/assets without verified permission), PRD §25 Licensing (NDI attribution + License-ID + current runtime), PRD §27 (external legal/compliance accepting authority for FR-140), PRD §29 & §17 (NDI 6.x EULA as a gate-later legal confirmation, OD-06/08), Stage-2 condition C14 (→ FR-085/140).
- **Non-functional:** NFR-024 (output-failure isolation — NDI sink must not blank physical outputs), NFR-027 (SBOM + CVE/licence scanning; NDI listed in third-party notices).
- **Feasibility (FEASIBILITY.md):** §4 "NDI output" row [N1] (DOCUMENTED/High terms; integration INFERRED/Med) and the compliance flag feeding RP-10/RP-11; §4 "Browser-source" row (NDI vs virtual-camera/HTTP/WebRTC); §9 "What Stage 5 must decide" item 7 (NDI inclusion & licensing acceptance); §10 classification summary (0 OBSERVED — integration effort unproven here).
- **Licensing register:** LICENSING-REGISTER §2.6 (NDI SDK — royalty-free redistributable; attribution near use; keep runtime current; **AAC/H.264/H.265 licensing is the licensee's responsibility** — all OBSERVED/High; item 8: re-read the current 6.x EULA before ship — Legal/Med).
- **Architecture (ARCHITECTURE.md):** §2 ADR index (ADR-0013), §4 Output manager (NDI sink, R2), §6 Rendering & output (NDI as additional output sink), §17 escalated open decisions (NDI licensing gate).
