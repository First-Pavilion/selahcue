# ADR-0011: Observability and diagnostics

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** High
- **Validating spike:** None required. No FEASIBILITY unknown gates this decision; the residual risk is execution risk on redaction completeness, discharged by test/fuzz obligations rather than a spike (see Fallback / validation).
- **Owner:** Software Architect
- **Related:** ADR-0001 (Rust core, split render/UI two-process topology), ADR-0002/0003 (native render process vs. Tauri UI process — the surfaces that must be correlated), ADR-0007 (SQLite/SQLCipher persistence, storage headroom), ADR-0008 (LAN security: append-only audit log, "no secrets/transcripts in logs" T9/T19), ADR-0010 (AI/provider consent, usage/cost surfacing), ADR-0012 (packaging & updates; crash-report path)

---

## Context

SelahCue is a long-running, two-process desktop application that must be **debuggable in the field** (church volunteers, no on-site engineer, services running 8–12 h) **without ever leaking sensitive data off the device**. Observability is a cross-cutting concern; this ADR fixes the instrumentation layer, the local sink, the diagnostics-export shape, and — most consequentially — the **default egress posture**. The forces:

1. **A field-diagnosable, two-process system.** The architecture is deliberately split (ADR-0001/0002/0003): a native Rust render/output process, isolated from a Tauri UI/control process and the LAN control server. A fault (decoder stall, GPU device-loss, reconnection, crash-loop) frequently manifests in one process but originates in another. Diagnosis therefore needs **structured, causally-correlatable** records across process and async-task boundaries — flat `printf` logs do not survive this. This is the primary technical force.

2. **Reliability evidence must be *producible*.** The PRD's reliability posture (PRD §Reliability; ARCHITECTURE §12) — continuous autosave (FR-074/NFR-023), crash recovery + crash-loop breaker (FR-075), storage-exhaustion guard (FR-169), output-failure isolation (NFR-024/FR-083), GPU/decoder recovery (FR-160) — is only *verifiable* if the system emits the spans/events that show what happened. FEASIBILITY §10 spike **S7** (12-h soak harness) and target **#13** (< 5 % memory growth over 12 h) cannot be measured, and a post-incident RCA cannot be written, without this instrumentation. Observability is the evidence layer under the whole reliability story.

3. **Privacy is a hard constraint, not a preference.** Sermon audio (asset A2), transcripts (A3), AI notes (A4), and user API keys (A5) are sensitive under NDPA 2023 + GDPR (PRD §21). The threat model is explicit: **T19** — "Secrets/transcripts leak via logs, crash reports, or clipboard" (Medium; mitigation: "Scrub logs/crash reports; **opt-in diagnostics only**; no sensitive data in analytics") — and **T9** — "Redact in telemetry … Never in plaintext config, logs, or crash dumps." CON-5 and the cloud-AI posture (FR-132: nothing leaves the host until a per-provider opt-in; FR-133: a live "cloud active" indicator) establish the product's baseline: **data does not leave the device without an explicit, disclosed act of consent.** Any telemetry channel is, functionally, cloud egress and inherits exactly those obligations (FR-176/177).

4. **Low, bounded resource use.** ARCHITECTURE §1(6) and FEASIBILITY §8 targets **#13** (soak stability) and **#14** (background CPU < 3 %, no needless wake) bound the cost of observability itself: instrumentation must be low-overhead, and the log sink must be **size-capped and rotating** so it cannot grow without bound on disk or undermine the memory/CPU envelope — logs must not become the leak they exist to catch.

5. **Logging must not fight the storage-exhaustion guard.** FR-169 reserves checkpoint headroom and warns before writes fail; FR-081 (R2) adds a low-disk warning + safe-mode. An unbounded or greedy log writer directly contradicts these. The log sink must **coordinate with** the storage guard, not compete with it.

6. **Offline-first.** Core diagnosis must work with zero network (CON-2, NFR-015). Whatever we choose cannot *require* a cloud backend to be useful — the default must be fully local.

7. **A clean boundary with the audit log.** ADR-0008 owns an **append-only security audit log** (FR-150/T7: device, role, command, timestamp, result). That is a distinct artifact from operational/diagnostic logs and must not be conflated: the audit log is a tamper-evident security record (never redacted away, but also never carrying content/secrets), whereas diagnostic logs are operational and are aggressively redacted. This ADR covers the diagnostic/operational plane and defers the audit plane to ADR-0008.

**Evidence-base honesty.** FEASIBILITY did not run an observability spike — it evaluated rendering, media, interop, mobile, and LAN unknowns, not logging. So this decision does **not** rest on a FEASIBILITY measurement; it rests on (a) the two-process topology from ADR-0001, (b) the hard privacy constraints in the threat model and PRD, (c) the resource bounds in FEASIBILITY §8, and (d) the well-established maturity of the Rust `tracing` ecosystem as general engineering knowledge. That combination is why confidence is High while the "validating spike" is deliberately empty — there is no open unknown to resolve, only implementation discipline to enforce.

## Options considered

### Option A — `tracing` structured spans/events → local rotating files; redacted diagnostics bundle; telemetry opt-in only (CHOSEN)

Instrument the Rust core with the `tracing` facade (spans + structured, keyed events), fan out to a **local, size-capped, rotating file** subscriber; expose an on-demand **redacted diagnostics bundle** export (FR-082); and treat any off-device telemetry as **opt-in only**, disclosed, and default-off.

**Pros**
- **Structured spans model the async, multi-process reality** (force 1). `tracing` records causal span trees with typed fields, which is what correlating a render-process decoder fault to a UI-process action or a control-plane message actually requires — flat log lines cannot express this. A shared correlation/trace id can be threaded across the render, UI, and LAN-server processes.
- **Native fit to the Rust core (ADR-0001).** `tracing` is the de-facto standard structured-diagnostics layer in the Rust ecosystem, integrates directly with `tokio`/async spans, and is mature and battle-tested — the choice imports no novel risk.
- **Fully local by default** (forces 3, 6): the file subscriber needs no network, satisfying offline-first and the privacy baseline out of the box. It is the observability substrate S7's soak harness and any RCA consume (force 2).
- **Level/target filtering + low overhead** lets us keep the hot render path near-silent in production and raise verbosity only when diagnosing, protecting the CPU/soak budget (force 4, FEASIBILITY #13/#14).
- **The diagnostics bundle is a first-class, redacted artifact** (FR-082): structured fields make **allowlist** redaction tractable — we serialise a known set of safe fields rather than trying to scrub free-text after the fact.

**Cons / accepted costs**
- **Redaction correctness is now security-critical code.** A structured event with a mis-typed or content-bearing field is a T19 leak. This is the real risk of the whole ADR and is addressed by an allowlist (deny-by-default) redaction model plus tests/fuzzing — not by hoping developers remember to scrub (see Fallback / validation).
- **Instrumentation discipline is ongoing:** spans/fields must be added as code is written and reviewed to keep content and secrets out of them (T9/T19). This is a standing review checklist item, not a one-time task.
- **Log rotation must be coordinated with FR-169/FR-081**, not implemented naively, or it undermines the storage-exhaustion guard (force 5).

### Option B — Default-on cloud telemetry / hosted crash reporting (REJECTED as the default, on privacy grounds)

Ship an OpenTelemetry/hosted-analytics or Sentry-style crash-reporting pipeline that transmits events, metrics, and crash dumps to a vendor backend by default (opt-out).

**Pros**
- Centralised, aggregate visibility into field behaviour and crashes without asking the user to export anything; fast fleet-wide RCA; mature vendor tooling.

**Cons — disqualifying as a default**
- **Directly violates the product's privacy baseline.** Default egress of diagnostics is exactly the T19 finding ("opt-in diagnostics only") and contradicts CON-5 and the FR-132/133 posture that *nothing* leaves the host without an explicit, disclosed opt-in. Default-on telemetry is functionally cloud egress and would inherit FR-176/177 (privacy policy, DPA, cross-border transfer) obligations while defeating the very trust position that differentiates SelahCue.
- **Crash dumps are a documented leak vector** (T9/T19: "Never in plaintext … crash dumps"). A raw crash report can carry secrets from process memory (API keys, A5) and transcript/sermon content (A3) — precisely what must not egress. An opt-out model guarantees that some churches leak before they notice.
- **Fails offline-first** (CON-2/NFR-015): a telemetry-dependent diagnostics story is useless on the air-gapped networks SelahCue targets.
- **Verdict:** rejected **as a default**. The *capability* is not banned — it is demoted to an **opt-in, disclosed, redacted export** that reuses the same redaction pipeline as Option A's bundle, gated exactly like a cloud AI provider (consent + "active" disclosure). The transport of any such opt-in telemetry rides the same privacy obligations as cloud AI.

### Option C — Minimal flat logging (`log` facade + a file writer), no structured spans (REJECTED)

The lightest possible option: a `log`-style leveled facade writing formatted lines to a file.

**Pros:** trivial to adopt; near-zero conceptual overhead; smallest dependency.

**Cons**
- **Cannot express the causal, cross-process structure** the two-process topology demands (force 1). Correlating a render-process fault to its control-plane trigger across async tasks becomes manual log-grepping — inadequate for field RCA and for S7 soak analysis.
- **Free-text lines make allowlist redaction and machine-readable diagnostics bundles hard** — redaction regresses to fragile post-hoc scrubbing, raising T19 risk rather than lowering it.
- **Verdict:** rejected as the primary layer. (`tracing` can still emit a human-readable formatted layer for `tail`-style local viewing, so the ergonomic benefit of flat logs is retained *inside* Option A without giving up structure.)

### Option D — OpenTelemetry (OTel) as the primary, always-on instrumentation layer (considered; folded in as an opt-in bridge)

Adopt OTel SDK + collector as the instrumentation standard from the start.

**Pros:** vendor-neutral standard; rich metrics/traces; a clean path if fleet observability is ever wanted; `tracing` has a first-class `tracing-opentelemetry` bridge, so this is not mutually exclusive with Option A.

**Cons**
- An always-on OTel collector adds weight and an **egress-shaped surface** that conflicts with the low-footprint (#14) and privacy-default posture if enabled by default.
- The neutral-standard benefit only pays off with a backend to export to — which reintroduces Option B's default-egress problem unless it stays opt-in.
- **Verdict:** not the default. We adopt `tracing` as the instrumentation layer and keep the **OTel bridge available for the opt-in telemetry path**, so a church that *chooses* fleet observability can have it without imposing egress on everyone else. This preserves future optionality at zero default-privacy cost.

## Decision

Adopt **`tracing`-based structured instrumentation** across the Rust core (render process, UI/control process, LAN server, AI orchestration), emitting **spans + typed, keyed events** with a correlation id threaded across the two-process boundary. The default subscriber writes to **local, size-capped, rotating log files** with production-safe level/target filtering. Provide an on-demand **redacted diagnostics bundle** export (FR-082) built by **allowlist (deny-by-default) serialisation** of known-safe fields — carrying **no secrets, no API keys, no transcripts, and no sermon content** (T9/T19). **All off-device telemetry is opt-in only, default-off, disclosed, and redacted through the same pipeline**, gated exactly like a cloud AI provider (consent + an "active" disclosure analogous to FR-133); the OTel bridge is reserved for that opt-in path.

**Invariants (not spike-gated; enforced by design + review + CI):**
- **No secrets/transcripts/sermon content in any log, bundle, crash dump, or telemetry event** — allowlist redaction, verified by test/fuzz (T9/T19).
- **Default egress = none.** Diagnostics stay on the device until the user exports a bundle or explicitly opts into telemetry (T19, CON-5, FR-132 posture).
- **The log sink is bounded** (size-capped rotation) and **coordinates with the FR-169 storage-exhaustion guard / FR-081 safe-mode**, reserving headroom rather than competing for it.
- **The diagnostic plane is separate from the ADR-0008 audit plane;** neither carries content/secrets, but they have different retention, tamper-evidence, and redaction rules.

**Release phasing (honest scoping).** The `tracing` instrumentation and local rotating logs are **cross-cutting and built in from MVP** — they are how we debug MVP, run the S7 soak, and produce recovery evidence for the MVP reliability ACs. The **user-facing FR-082 diagnostics-bundle export UI + rotation-under-cap polish is scheduled R2** per the PRD priority; the redaction pipeline it depends on is designed from MVP so the R2 surface is a UI over an already-safe substrate. Provider **usage/cost/retention surfacing (FR-136, R3)** and **per-output health (dropped-frames; mobile health view FR-096, R2)** are on-device operational readouts built on the same instrumentation — they are *local diagnostics*, explicitly **not** external telemetry.

## Consequences

### Positive
- **The whole reliability story becomes evidenced, not asserted.** Autosave/recovery/crash-loop/output-isolation/soak (FR-074/075/169/160, NFR-010/024) can be demonstrated from structured spans; S7 and target #13 are measurable; field RCA is possible for volunteers-plus-remote-support.
- **Privacy-by-default is preserved and consistent.** The same principle that gates cloud AI (FR-132/133) governs telemetry, so there is one coherent egress-consent model, not two. Nothing sensitive leaves the device by accident.
- **Cross-process causality is first-class**, matching the ADR-0001/0002/0003 split — the observability model fits the architecture instead of fighting it.
- **Diagnostics are shareable safely:** a redacted bundle can be handed to support without exposing sermon content or keys, satisfying FR-082 and closing T19 by construction.
- **Future fleet-observability is not foreclosed** (OTel bridge on the opt-in path) without imposing egress on anyone.

### Negative / accepted costs
- **Redaction is security-critical and must be actively verified.** A single content-bearing field is a T19 privacy incident. This is a permanent test/fuzz/review obligation, not a build-once feature.
- **Standing instrumentation discipline:** every new span/field is a potential leak and a review checkpoint; keeping the hot path low-overhead (#14) requires deliberate level/target hygiene.
- **Bounded logging can drop detail under pressure.** Size-capped rotation means the oldest diagnostic detail is discarded, and coordinating with FR-169 may throttle logging exactly when a disk-exhaustion incident is most interesting — an accepted trade to protect checkpoint headroom.
- **No fleet-wide default visibility.** Because telemetry is opt-in, most field issues arrive as user-exported bundles, which is slower than push telemetry — the deliberate price of the privacy posture.

### What this commits us to
- An **allowlist redaction pipeline** shared by the diagnostics bundle, any crash-report path (ADR-0012), and any opt-in telemetry — with automated tests and fuzzing that assert no secret/transcript/content field can escape (T9/T19).
- A **bounded, rotating local log sink** that is a cooperating client of the FR-169 storage guard and FR-081 safe-mode, never an unbounded writer.
- **Cross-process correlation ids** wired through the render, UI, and LAN-server processes so spans join up.
- A **telemetry-consent + "telemetry active" disclosure** modeled on FR-132/133, plus FR-176/177 handling if/when any opt-in telemetry transports off-device.
- Keeping the **diagnostic plane and the ADR-0008 audit plane distinct** in storage, retention, and redaction rules.
- Never routing secrets to logs/dumps (NFR-017/T9) — device keypairs/tokens and API keys stay in the OS secret store and are never serialised into any diagnostic artifact.

## Fallback / validation

- **Confidence is High and no validating spike is required — deliberately.** Unlike the render/interop/mobile/LAN decisions, observability has no open FEASIBILITY unknown: `tracing` + local rotating files + redacted bundles are mature, well-understood engineering, and the privacy-first default is *dictated* by hard constraints (T19, T9, CON-5, FR-132) rather than chosen on a technical bet. There is no cross-OS make-or-break unknown here (contrast ADR-0006/S2).
- **What must nonetheless be *verified* (execution risk, not design risk):** redaction completeness. Because "no secrets/transcripts/content in logs" is a Medium-severity threat-model requirement (T19) whose failure is a privacy incident, the redaction path is treated as security-critical: **allowlist serialisation, unit tests asserting known-sensitive fields are absent, and fuzzing of the bundle/crash-report exporters.** This is the "validation" this decision carries — discharged by tests in Stage 6/8 and the security review (Stage 13), not by a discovery spike.
- **Fallback if a leak is found** (redaction defect, or a field that must exist but risks content): fail **closed** — omit the field from the exportable artifact by default and require explicit, per-field opt-in to include it, keeping the deny-by-default posture. A redaction regression is a release-blocking security finding, consistent with ADR-0008's "high-blast-radius component" treatment of the pinning/validator code.
- **Cross-check against S7:** the 12-h soak harness (FEASIBILITY §10 S7 / target #13) doubles as a real-world exercise of the log sink under sustained load — it will surface unbounded-growth or overhead regressions in the observability layer itself, so the reliability spike incidentally validates the sink's resource behaviour (force 4).

## Requirement / PRD references

| Ref | Requirement | How this ADR satisfies it |
|---|---|---|
| **FR-082** | Structured logs with rotation + diagnostic report export (R2) | `tracing` structured events → size-capped rotating files; on-demand **redacted** diagnostics bundle via allowlist serialisation |
| FR-081 | Storage-space warning + safe-mode (R2) | Log sink coordinates with the storage guard; bounded rotation reserves headroom |
| FR-169 | Storage-exhaustion detection + graceful degradation (MVP) | Logging is a cooperating client, never an unbounded writer; reserves checkpoint headroom |
| FR-075 / FR-074 / NFR-023 | Crash recovery + crash-loop breaker; continuous autosave | Structured spans make recovery paths diagnosable and the ACs evidenced |
| FR-160 | GPU/renderer + decoder recovery | Out-of-band recovery events instrumented for RCA without blanking output |
| FR-083 / NFR-024 | AI/provider failure never blocks core; output-failure isolation | Observability runs off the render/output hot path; a logging fault cannot blank output |
| FR-132 / FR-133 | Cloud OFF by default; live "cloud active" indicator (R3) | Same consent + "active" disclosure model applied to any opt-in telemetry egress |
| FR-136 | Provider usage/cost/retention visibility (R3) | On-device operational readout built on the same instrumentation (local, not external telemetry) |
| FR-096 | Mobile per-output health view (R2) | Per-output health (connected/resolution/dropped-frames) surfaced as local diagnostics |
| FR-150 | Append-only audit log | Kept **distinct** from diagnostic logs (owned by ADR-0008); neither carries content/secrets |
| FR-176 / FR-177 | Privacy policy + data disclosures; DPA + cross-border transfer | Trigger only if a user opts into off-device telemetry; default posture avoids them entirely |
| NFR-016 | LAN transport security | Diagnostics never create a plaintext side channel; transcript/preview/media stay on the encrypted channel |
| NFR-017 | OS-secret-store-only secrets | Keys/tokens never serialised into logs, bundles, or crash dumps |
| NFR-010 | 8–12 h soak stability | Bounded, low-overhead sink; validated incidentally by S7 |
| NFR-027 | Dependency/SBOM + license scanning | `tracing`/subscriber deps pass the CI SBOM/license gate (no GPL/AGPL in the proprietary build) |
| CON-2 / NFR-015 | Offline-first | Default diagnostics are fully local; no cloud backend required to be useful |
| CON-5 | Cloud/privacy default posture | Telemetry opt-in only; nothing leaves the device by default |

- **Threat model (`docs/security/reviews/threat-model-draft.md`):** **T19** (secrets/transcripts leak via logs/crash reports — "opt-in diagnostics only; scrub logs/crash reports"), **T9** (redact in telemetry; never in plaintext logs/crash dumps), T10/T17 (sermon-data confidentiality), T7 (audit log — ADR-0008 boundary).
- **Feasibility (`docs/research/FEASIBILITY.md`):** §8 targets **#13** (12-h soak < 5 % memory growth) and **#14** (background CPU < 3 %) bound the sink's cost; §10 **S7** (soak harness) both consumes and exercises this layer. Note: FEASIBILITY ran no dedicated observability spike — this decision rests on the two-process topology, the privacy constraints, the resource bounds, and `tracing`'s ecosystem maturity, as stated in Context.
- **Architecture (`ARCHITECTURE.md`):** §13 (Observability), §12 (Reliability & crash recovery), §1 principles 3/4/6 (output isolation, AI out-of-band, bounded resource use).
- **Related ADRs:** ADR-0001 (two-process topology being observed), ADR-0008 (audit log + "no secrets/transcripts in logs" T19), ADR-0010 (provider consent model reused for telemetry), ADR-0012 (crash-report path shares the redaction pipeline).
