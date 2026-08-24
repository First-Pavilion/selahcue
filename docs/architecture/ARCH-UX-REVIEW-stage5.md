# Stage-5 Architecture + UX Review — Adjudication (SelahCue)

**Artifact under review:** Stage-5 architecture package (ARCHITECTURE.md, 14 ADRs, UX-FLOWS, UX-STATE-MATRIX, COMPONENT-SPECS) against the PRD, brief, and threat model.
**Role:** Lead reviewer, adjudicating five independent lens reviews.
**Date:** 2026-07-23

---

## Verdict: FAIL

Two blockers stand. Per the gate rule (FAIL if any blocker stands), the Stage-5 package does not pass as-is. Both blockers are day-one commitments — one is a safety-critical documentation contradiction, the other a bespoke-engine testability seam that must be built in from the first line of engine code — so neither can be deferred and cleared later without rework. The package is otherwise strong and internally honest; clearing the two blockers plus resolving the twelve consolidated majors (design decisions recorded, not necessarily fully built) converts this to PASS WITH CONDITIONS.

### Per-lens verdicts (as submitted)

| Lens | Verdict |
|---|---|
| Architecture conformance & coverage | PASS WITH CONDITIONS |
| Security architecture vs threat model | PASS WITH CONDITIONS |
| Accessibility | PASS WITH CONDITIONS |
| Testability | PASS WITH CONDITIONS (raised 1 blocker) |
| UX completeness & live-safety | PASS WITH CONDITIONS (raised 1 blocker) |

Both lenses that returned "PASS WITH CONDITIONS" while raising a blocker are internally reconciled here: a standing blocker overrides the lens's own conditional pass. Adjudicated package verdict is therefore FAIL until the two blockers are cleared.

---

## Consolidated blockers (must clear before Stage-6/7)

### B1 — Emergency-control keyboard bindings contradict across the three normative UX docs
*(UX lens blocker 1 + Accessibility lens major 1 — same defect, adjudicated at blocker severity)*

The default keybindings for the two most safety-critical, muscle-memory panic controls disagree across UX-FLOWS, UX-STATE-MATRIX, and COMPONENT-SPECS, and in one case invert:

- `Esc Esc` = **CLEAR ALL** in UX-FLOWS (lines 35/64/325/347/688) but = **BLACKOUT/restore** in UX-STATE-MATRIX (lines 77/410) — literally opposite outcomes (blackout is a reversible blank that restores prior content; clear-all removes content).
- Clear-all: `Esc Esc` (FLOWS) vs `.` (MATRIX) vs `Shift+C` / `Cmd+.` (COMPONENT-SPECS).
- Blackout: `B` (FLOWS/COMPONENT-SPECS) vs `Esc Esc` (MATRIX).
- The always-reachable mechanism even differs in kind: a double-`Esc` (matrix/flows) vs a `Cmd/Ctrl` modifier that survives text entry (component). In FLOWS, single `Esc` also clears the focused layer, colliding with the `Esc Esc` double-tap.

This is the single affordance the entire accessibility and live-safety story leans on. Three conflicting default schemes cannot all be implemented; an operator trained on one doc will fire the wrong emergency action under pressure, and QA cannot verify one behaviour.

**Exact change to clear:** Publish one canonical, doc-cited binding table for Go-Live / Next / Prev / Clear-layer / Clear-all / Blackout / Undo, used identically by all three UX docs and by QA. Recommended resolution: adopt the COMPONENT-SPECS §11 scheme (presentation-focus single keys plus always-global `Cmd/Ctrl+B` / `Cmd/Ctrl+.` fallbacks that fire while typing), delete the `Esc Esc`=blackout and `.`=clear variants, keep FR-014 remappability but define one unambiguous default, and apply the "emergency binding cannot be unbound to nothing" guard to the canonical keys. Ensure the always-global emergency backstop is included in the canonical set so it survives text entry.

### B2 — No test seam for the bespoke Rust+wgpu render/reliability engine
*(Testability lens blocker 1)*

The architecture makes the bespoke compositor the product's core value and explicitly accepts owning "a bug surface a framework would otherwise absorb," yet specifies no way to test that engine deterministically or in isolation. A repo-wide search finds zero mention of headless/offscreen rendering, frame readback, golden-image/snapshot rendering, a deterministic render mode, or fault-injection hooks. Consequences:

1. Rendering-correctness ACs (per-output layout FR-038, deterministic text shaping FR-017/ADR-0014, missing-media placeholder FR-070, TIME UP FR-059) can only be checked by eye on physical multi-monitor hardware — not repeatable, not CI-able. Cross-platform parity (NFR-014 / METRIC-010 "identical" / "100% test-matrix pass") has no automatable oracle.
2. The headline reliability invariant — "never blank output" (G-1, METRIC-001 = 0 unintended blanks, NFR-024, FR-160 hold-last-frame) — is declared "verified via fault-injection," but nothing can inject a GPU device-loss/TDR, decoder fault, IPC/control-plane stall, or storage-exhaustion write-failure, nor capture the composited output frame to prove the last-good frame was held.
3. The render↔control IPC boundary is described only as "a validated IPC boundary" with no drivable contract, so the engine cannot be exercised headlessly.

Determinism, offscreen readback, and fault hooks must be built into a bespoke compositor from the first line of engine code — the same "cheaper to build in than retrofit" logic ADR-0007 already applies to SQLCipher — so this is settled before engine implementation begins, not after.

**Exact change to clear:** Add an architectural commitment (a new ADR, or an ARCHITECTURE §12/§13 addition) specifying: (a) a headless/offscreen render path rendering any per-output scene to an offscreen wgpu surface with pixel readback for golden-image/snapshot tests within a defined perceptual tolerance (the parity oracle for NFR-014); (b) a deterministic render mode (fixed clock/seed, injectable monotonic timeline) so frame output is reproducible; (c) explicit fault-injection hooks to force wgpu device-lost, per-output decoder failure, IPC stall, and disk-full so NFR-024/FR-160/FR-169 are exercised repeatably; (d) a frame-capture path feeding a luminance-transition analyzer for FR-175 (≤3 flashes/sec). Make the render↔control IPC boundary a documented, versioned, drivable message contract so the engine is testable in isolation. This seam is also a hard dependency of major M6 (performance/safety measurement methodology).

---

## Majors (each with the exact design change needed)

Twelve majors after de-duplication across lenses. Each must have its design decision recorded before the dependent code is written; full build can follow the stated timing.

### M1 — Untrusted media/font decode runs in-process with no isolation boundary (reliability crash AND security RCE)
*(Architecture lens major + Security lens major 1 — merged; shared root cause)*

The highest-RCE-risk assets (imported media and fonts, A8, FR-173) are routed through GStreamer's large in-process C decode/demux surface, native/OS HW-decode C elements (ADR-0005), the explicitly-unsafe zero-copy wgpu-hal interop (ADR-0006), and HarfBuzz shaping (ADR-0014) — all inside the authoritative render process. The ADR-0001 two-process split is render-vs-UI, not decode-sandbox-vs-compositor. Two distinct failures share this root cause:

- **Reliability (NFR-024/FR-160):** the design treats decoder/GPU faults as recoverable in-process error returns ("hold last frame, recover out-of-band"), but a hard crash/segfault in a C decoder or the unsafe interop path takes down the render process and blanks **all** outputs at once — contradicting NFR-024 ("a media-decoder failure never blanks output") and FR-160 ("an isolated per-output decoder failure never affects other outputs").
- **Security (T12, High):** "hold last frame" contains a crash, not code execution. A successful media/font exploit is code running in the render process = full host compromise on the live-service machine. ADR-0005 never mentions T12, RCE, or security isolation, and conflates it with output-failure isolation. FR-173 only offers "sandbox where platform-feasible," and no ADR owns the decision.

**Exact change:** Add an explicit decode-isolation ADR before the media engine is built. Run media/font decode in out-of-process, low-privilege/sandboxed workers (OS sandbox / seccomp-BPF / AppContainer / `sandbox_init` where available), passing only decoded frames/glyph atlases across the boundary — restartable and fenced from the wgpu compositor. Retrofitting process isolation onto an in-process gstreamer-rs/HarfBuzz integration is expensive and changes the zero-copy interop design, so it is a day-one topology commitment (ADR-0001) and belongs in the S2 fault-injection matrix. Explicitly distinguish security isolation from fault isolation in ADR-0005/§7, and state which platforms get real sandboxing vs best-effort (validation-only) so residual T12 risk is visible. If full isolation is not committed, narrow the NFR-024 "structural isolation" claim to control/AI/UI faults and reclassify render-process-internal faults as best-effort bounded-recovery.

### M2 — No decided key-custody path on Linux without a Secret Service backend
*(Security lens major 2)*

SQLCipher-at-rest is adopted from MVP; its DB key plus the per-device token/keypair (A6) must live "only in the OS secret store" (NFR-017, MVP). On a headless/minimal-DE Linux host with no Secret Service backend — a real deployment class for a product whose headline is genuine tri-platform parity — no key-custody path is decided (OD-19 / threat-model §7.6 leave it open). ARCHITECTURE §11/§4 present secret storage and at-rest encryption as solved MVP properties and never surface the Linux hole. The "do NOT silently fall back to plaintext" guardrail lives only in the draft threat model, so an implementer could satisfy "it builds on Linux" by weakening NFR-017. Because device tokens are MVP secrets, this lands at MVP for Linux, earlier than the SQLCipher R3 timeline implies.

**Exact change:** Close OD-19 before Linux MVP ships: specify the no-keyring fallback (passphrase-derived key-encryption-key, or refuse-to-persist-and-require-re-entry) and the warn/block-on-unconfirmed behaviour, and record the "never silently fall back to plaintext" invariant in ARCHITECTURE §11 (not only the ADR/threat-model).

### M3 — No structured live-scene text channel for the MVP screen-reader baseline
*(Accessibility lens major 2)*

Two coupled gaps make the SR baseline names-only rather than operable. (1) Data path: ADR-0003 sends the WebView console only a downscaled composited raster of live/preview — opaque to a screen reader. COMPONENT-SPECS §6 requires Current/Next content and blackout/cleared state exposed "as text, not image-only," but the architecture does not guarantee a structured live-scene text channel (current line, next line, slide n/m, translation, blackout|cleared) feeding accessible names — asserted in UX, not committed in the preview/IPC contract. (2) Scope: NFR-021's MVP set is control names/roles only and defers full coverage to R2, so it never mandates announcing what is now live/next or that output is blacked out/cleared. A blind or low-vision-with-SR operator gets labelled buttons but no in-scope way to know current program state, so cannot safely drive a service.

**Exact change:** Make the structured live-scene text a first-class IPC payload (separate from the raster) that feeds aria-live regions, and add "screen reader announces current/next content and blackout/cleared state" to the S5 accessibility acceptance bar. Then either pull live-state read-back into the NFR-021 MVP baseline, or state plainly in §22 that MVP AT targets keyboard/low-vision operation and NOT fully non-visual live driving — so the specs stop implying more than MVP guarantees.

### M4 — Default flashing TIME UP under-specifies the red-flash / large-area seizure case
*(Accessibility lens major 3)*

FR-175 and the §32 launch criterion verify only "≤3 flashes per second." The default TIME UP is full-panel/large-area saturated red with a flash (Flow 4, COMPONENT §8, matrix §10). WCAG 2.3.1 has a distinct, stricter red-flash provision and a flash-area threshold (>25% of display within the central 10° field) beyond the 3/sec count — exactly the large-area saturated-red transition TIME UP produces. A TIME UP that passes the stated ≤3/sec check can still be a photosensitive-seizure hazard. The information-preserving static variant exists only when the user has enabled Reduced Motion; flashing red is the default.

**Exact change:** Constrain the default flashing TIME UP (and any large-area flash) to also satisfy the red-flash and flash-area sub-criteria — limit saturated-red flash area/relative-luminance transition, or make the solid high-contrast inverted TIME UP the default with flashing as explicit opt-in. Extend the FR-175/launch acceptance test beyond a bare frequency count to cover red-flash and flash-area thresholds (depends on the B2 frame-capture seam).

### M5 — LAN protocol / RBAC contract is deferred to Stage-13 but the MVP build needs it at Stage-7
*(Testability lens major 1; reinforced by Security lens minor 3)*

The LAN control plane is the product's primary attack surface and MVP-scoped, but the artifacts a contract test needs as its oracle are deferred to post-implementation Stage-13: the command→role RBAC matrix and multi-controller conflict resolution (§7.4), the concrete replay/nonce algorithm + reconnect sequence-state persistence (§7.5), and the message schema itself (ADR-0008 favours "a versioned JSON/CBOR schema + strict validator" but names no deliverable/owner). FR-174 mandates a fuzz AC on the parser and FR-090 requires "every command validated against granted role," yet authorization-matrix, replay-window, and schema/fuzz tests cannot be written to a spec that arrives after the code. The Flutter mobile client (ADR-0009) implements the same contract, so consumer-driven contract testing has no shared source of truth.

**Exact change:** Before Stage-7, produce a versioned, machine-checkable schema artifact (JSON-Schema/CBOR/protobuf IDL) for every control message, a concrete command→role allowlist matrix, and the replay/nonce algorithm — the single source of truth driving host authorization tests, the FR-174 fuzz corpus, and shared host/mobile contract tests. Pull the device-auth handshake + key-establishment + proof-of-possession binding + reconnect nonce-persistence design (Security minor 3) forward into an early spike alongside S6/S9, keeping it transport-agnostic so the Noise fallback does not force a PoP redesign. Stage-13 then hardens an existing testable contract rather than first defining it.

### M6 — Performance and safety launch-gate metrics have no defined measurement method
*(Testability lens major 2)*

Several launch-gate metrics name targets but no method, so they are non-automatable as written. NFR-004/METRIC-002 "input→on-screen ≤150ms (goal ≤80ms)": "on-screen" is the physical display; true input-to-photons latency needs external instrumentation or a defined GPU-present-timestamp proxy — neither specified. FR-013 "current/next reflect live ≤100ms" and ADR-0003 WebView preview latency (S5) have no defined capture point. FR-175 "≤3 flashes/sec" (§32 launch gate) needs output-frame capture + luminance-transition analysis — no method defined. The "(RP-09 §8) benchmark harness" is referenced but never specified.

**Exact change:** Specify the perf/safety measurement methodology in the harness spec: the acceptable latency proxy (e.g. input-event timestamp vs wgpu present-complete callback) and its relationship to the ≤150ms/≤80ms bar; the preview-latency capture point for FR-013; and the frame-capture + flash-rate analysis method for FR-175. Depends on the B2 engine frame-capture seam.

### M7 — No ongoing GPU-hardware regression environment for the unsafe zero-copy interop paths
*(Testability lens major 3)*

ADR-0006 commits to four backend-specific unsafe wgpu-hal paths (VA-API/DMABuf, NVDEC/CUDA, Metal/IOSurface, D3D11 shared-handle) at Medium-Low confidence ("make-or-break") and to re-validating interop on each wgpu upgrade. These paths — and GPU device-loss recovery (FR-160) — only run on real GPUs with real drivers; typical headless/virtualized CI cannot exercise them. The only validation named is one-time spikes S1/S2; there is no GPU-equipped test lab or self-hosted-runner matrix for ongoing regression of the project's highest-risk code, and the anticipated per-OS mixed primary/fallback posture multiplies the matrix.

**Exact change:** Specify a GPU-hardware test lab / self-hosted-runner matrix ({Intel VA-API, AMD, NVIDIA, Apple Silicon, Windows D3D}) covering each interop backend as a first-class, ongoing CI target (not just spikes), including a deterministic way to trigger and assert recovery from device-loss (FR-160). Pin the wgpu version and gate upgrades on re-running the interop matrix.

### M8 — Live-action key semantics (Space, ⌘Z) are defined inconsistently
*(UX lens major 1)*

(1) Space: UX-FLOWS §0.4 and COMPONENT-SPECS §11.2 say Space = Next/advance, but COMPONENT-SPECS §5 wireframe and STATE-MATRIX §6 say Space = Go Live when the Preview panel is focused — so the operator's most-used key either advances the live slide or pushes staged content to air depending on focus, risking wrong/premature content on the audience output. (2) ⌘Z: COMPONENT-SPECS §1.2/§11.2 define "Undo live" re-pushing the prior program frame for Go-Live/Clear/Blackout, while UX-FLOWS Flow 2 says ⌘Z does NOT un-trigger a live change and live recovery is forward/back only. Operators will form opposite recovery expectations under pressure.

**Exact change:** Bind Go Live to a distinct key (e.g. Enter / Cmd+Enter) never overloaded with Next on any pane; decide whether a bounded-window "Undo live" exists for Go-Live/Clear/Blackout (beyond the FR-117 5s AI-Display undo) or whether live is strictly forward/back. Reflect the single decision in all three docs.

### M9 — Preview vs Live colour vocabulary disagrees, and amber double-books as "warning"
*(UX lens major 2)*

The core cue separating staged from on-air conflicts: COMPONENT-SPECS §2.1/§5 use GREEN for PREVIEW, while UX-FLOWS §0.5 and UX-STATE-MATRIX §2 use AMBER. Worse, in FLOWS/MATRIX amber simultaneously denotes attention/degraded/warning, so a staged pane shares its colour with the fault state — under booth pressure a staged pane could read as a fault. Colour is never the sole signal (border + label always present), which caps the risk, but the primary distinction must use one token.

**Exact change:** Standardise one token set (recommend COMPONENT-SPECS: green=PREVIEW/staged, red=LIVE, amber=WARN/degraded) so "staged" and "something's wrong" are never the same colour; update the FLOWS/MATRIX colour legends to match.

### M10 — Emergency reachability is unreconciled with focus-trapping modals
*(UX lens major 3)*

Invariant 2 asserts Clear/Blackout are operable from any focus in every state, and COMPONENT-SPECS §11.1 says the global emergency bindings fire even while typing — but STATE-MATRIX §15.2 and §4/§5 Recovery rows say modals (recovery, destructive T2 confirm) trap focus. A focus-trapping modal intercepts key events and can overlay the pinned Live-Control column; a T2 confirm or blocking dialog appearing mid-service could swallow the global blackout/clear keypress. The interaction is never reconciled, leaving the always-reachable guarantee unproven where it matters most.

**Exact change:** Specify that emergency Clear/Blackout pierce any application modal (dedicated OS-level or capture-phase handler outside the focus trap), OR that no blocking/focus-trapping modal may appear over live controls while any output is live (inline confirms only during a live service). Add this as a testable row to the always-on-chrome contract.

### M11 — Cloud-provider consent/enable surface has no flow and no state-matrix coverage
*(UX lens major 4)*

The moment sensitive congregation audio/transcript first leaves the device is the consent opt-in, yet no flow and no state-matrix surface enumerates it. It is referenced only in passing ("Cloud provider (B5 → Flow-N settings)") but Flow-N does not exist, and the disclosure screen's states (default/confirming/error/revoke/offline) and the transition that first lights ●CLOUD are unspecified. This is a hard privacy requirement (FR-132/133/177, threat T10) with no interface-state coverage.

**Exact change:** Add a Cloud-provider consent flow and a state-matrix surface covering: pre-first-send disclosure (provider name, data sent, leaves-network/jurisdiction, DPA), explicit-confirm, Administrator-gating, revoke/purge-key, error/offline states, and the exact transition that toggles ●CLOUD ACTIVE. R3 timing (not MVP-blocking), but must exist before that surface is built.

### M12 — Multi-controller conflict resolution (OD-20) is undefined, but MVP ships multi-device pairing
*(UX lens major 5 + Architecture lens minor + Security lens minor 4 — merged; highest severity wins)*

Two paired controllers (or mobile + desktop) issuing simultaneous advance/clear/blackout has no defined arbitration; the audience-visible outcome (double-advance, race, last-writer-wins) is undefined. Desktop-authoritative serialization makes last-command-wins the implicit behaviour, but the host command-ordering/serialization model is unspecified, so MVP concurrent-control determinism is undefined. This is an integrity/availability gap on the highest-impact asset (A1 live output) under authorized-but-uncoordinated use — and MVP ships multi-device pairing (FR-085–094 with 2+ devices in the wireframes), so it is reachable in MVP, not a future concern.

**Exact change:** Resolve OD-20 before the mobile control path is implemented. State the MVP host command-serialization model (single authoritative command queue, total ordering, deterministic last-writer-wins) and define arbitration (e.g. single-active-driver lock per capability, or last-writer-wins with mandatory audit + visible attribution). Add the "contested" state to the Live/Program and Mobile Populated state-matrix rows, and note the chosen model in ARCHITECTURE §9. The richer conflict-arbitration UX may stay deferred, but MVP concurrent control must be deterministic and testable.

---

## Minors

| # | Lens | Issue | Fix |
|---|---|---|---|
| m1 | Architecture | ARCHITECTURE §15 asserts "all 79 MVP FRs covered"; PRD §33 lists 84 (79 predates the EPIC-R audit-discharge additions FR-169/173/174/175/176). Matrix rows already map all 84; only the count is stale. | Correct to 84; add explicit FR list per matrix row so the count self-checks against §33. |
| m2 | Architecture | Completion criterion S5-001 requires "21 required domains" but no artifact enumerates the canonical 21 (objective prose lists 20; brief is a different, longer set). Closure is by reviewer judgement. | Enumerate the canonical 21 and map each to an owning component/ADR (a one-column addendum to §15). |
| m3 | Architecture | §4 component PRD-ref column is not a complete inverse of the §15 matrix: FR-068/147/148/151/161/162 appear in matrix/ADRs but against no §4 component. FR-161 (MVP audio-device reconnect) is detailed by NO ADR — carried only by the §12 principle. | Add FR-068/147/148/151/161/162 to the relevant §4 rows; give FR-161 an explicit owning-component note in ADR-0005 or §12. |
| m4 | Architecture | FR-013's ≤100ms bar rests on a Medium-confidence, unproven S5 spike (downscaled raster into WebView, capped by macOS 60fps WebView limit); failure forces an egui/iced re-platform of the operator console. | Flag FR-013 ≤100ms as spike-gated on S5 in the gate report (as NFR-005/006 are); confirm the S5 bar measures against ≤100ms; cost the egui/iced fallback editor/accessibility scope before it is needed. |
| m5 | Security | ADR-0013 frames NDI as "an additive sink, not a new network surface"; inaccurate — NDI publishes plaintext, mDNS-discoverable video outside the ADR-0008 TLS channel (TB1). Per-output content can differ; future transcript/caption overlays (A3) would egress cleartext. NDI is absent from the threat model. | Correct the ADR-0013 framing; add NDI to the Stage-13 threat model; bar sensitive stage/confidence/transcript overlays from NDI by default; document that NDI content leaves the TLS/consent boundary. |
| m6 | Security | ADR-0011 calls the ADR-0008 audit log "tamper-evident," but neither ADR-0008 nor §11 specifies any mechanism — it is only "append-only local log" in SQLite/SQLCipher. Append-only is app discipline, not integrity against the TB2 local attacker; the ADRs also disagree in wording. | Specify a concrete mechanism (hash-chained entries and/or periodic signed checkpoints) so the T7 mitigation and the "tamper-evident" claim are true, or downgrade to "append-only within the app" and record residual local-tamper risk. Align ADR-0008/ADR-0011 wording. |
| m7 | Security | Device-auth handshake / session-key + PoP binding, key derivation/rotation, reconnect nonce-state persistence, and the transport-agnostic form (pinned-TLS + Noise fallback) are entirely deferred to Stage-13 — yet ADR-0008 is rated High confidence and itself calls this "security-critical code that must be reviewed and fuzzed." | Pull the handshake/key-establishment/PoP-binding/nonce-persistence design forward into an early spike alongside S6/S9; keep the High-confidence rating caveated; ensure app-layer auth is transport-agnostic. *(Reinforces M5.)* |
| m8 | Accessibility | Multiple regions are `aria-live="assertive"` concurrently (● LIVE tally, Live/Program panel, Blackout, TIME UP); assertive regions interrupt each other, so rapid Next flooding makes the SR baseline practically unusable. Design is inconsistent (Current view uses polite; timer announces on state-change). | Define one live-region priority model: single assertive channel for on-air/blackout transitions only; current/next/health/connection polite; debounce/coalesce per-advance announcements; apply the timer's "announce on state change" rule across surfaces. |
| m9 | Accessibility | WCAG-AA contrast is asserted, not demonstrated: state chips (amber/violet/red) and ≥48px stage high-contrast themes have no computed ratios; tokens deferred. NFR-020 also narrows the AA claim to contrast only (excludes resize-text 1.4.4, reflow 1.4.10); the dense console makes no OS text-scaling/zoom commitment. | Ratify the full token palette against 4.5:1 (body) / 3:1 (large/UI) with evidence before hi-fi, focusing on amber/violet/red chips and stage themes; decide explicitly whether OS text-scaling/zoom is in MVP scope. |
| m10 | Accessibility | Single-key live shortcuts (B, C, Space, →) are active only in "presentation focus" and disambiguated by a persistent visual indicator a non-visual operator cannot perceive (open question U-5). | Convey the focus-mode boundary non-visually (verify SR field-focus enter/leave is sufficient); make the reconciled always-global emergency binding (B1) the guaranteed backstop; include keyboard-only and SR operators in the METRIC-006 usability test validating U-5. |
| m11 | Testability | FR-075 crash-loop breaker triggers "after N rapid crashes" but leaves both N and the "rapid" window undefined, so the AC is non-deterministic (the sibling timer-restoration ambiguity was fixed; this was not). | Fix a concrete N and time-window (e.g. "3 crashes within 5 minutes") in FR-075 so the breaker and its "Resume vs Start clean" UX are deterministically testable. |
| m12 | Testability | ADR-0004 commits to a per-OS windowing test matrix incl. monitor hot-plug/DPI-change but does not say how unplug/replug is simulated per OS (Windows IDD, X/Wayland virtual outputs exist; macOS has no easy virtual-display API without kexts). FR-041/FLOW-009 hot-plug tests risk being manual. | Name the per-OS virtual-display/hot-plug simulation approach (or an explicit manual-with-evidence fallback where infeasible, e.g. macOS) so FR-041 reconnection-isolation has a defined verification path. |
| m13 | Testability | The 12h soak (S7, <5% memory growth) cannot run per-commit, so leak regressions are caught late; no faster CI proxy is named. | Add a short accelerated soak / allocation-regression proxy runnable per-PR against the bounded-queue/cache invariants (NFR-010, FR-084); reserve the full 12h S7 run for pre-gate verification. |
| m14 | UX | The Shortcuts-remap screen, Reduced-Motion toggle (FR-175), and Retention settings have no state-matrix surface; the live-safety guard "emergency actions cannot be unbound to nothing" lives only in prose (COMPONENT §11.3), not as a testable state — yet remapping is where an operator could break emergency reachability. | Add a Settings/Shortcuts surface to the state matrix; make the "emergency binding must remain non-empty" guard a testable acceptance state. *(Ties to B1.)* |
| m15 | UX | Flow 4 is [MVP] but its happy path and timer wireframe state "Operator hears a local alert (FR-063)"; per the PRD FR-063 is R2 and MVP TIME UP is visual-only. An MVP flow's happy path depends on an R2 capability. | Mark the audible-alert step [R2] within the MVP flow, or correct the trace so MVP TIME UP is documented visual-only. |
| m16 | UX | The Sermon-notes editor has a full flow (Flow 11, R5) but no state-matrix surface (matrix stops at R4). Separately, stage messages (FR-162, "Send wrap up") carry no explicit T3 guard against reaching an audience output, unlike TIME UP. | Add an R5 notes-editor surface when that release is planned; confirm stage-message output selection defaults to stage/confidence and cannot silently target an audience output (or document why no guard is needed). |

---

## Conditions to clear the gate

To move from FAIL to PASS WITH CONDITIONS, before Stage-6/7 engine and mobile implementation begins:

1. **[B1]** Publish one canonical emergency/live keybinding table (presentation-focus keys + always-global fallbacks) used identically by UX-FLOWS, UX-STATE-MATRIX, COMPONENT-SPECS, and QA; apply the non-unbindable guard to the canonical emergency keys.
2. **[B2]** Add an ADR / ARCHITECTURE §12–13 commitment to a headless offscreen render path with pixel readback, a deterministic render mode, fault-injection hooks (device-loss, decoder fault, IPC stall, disk-full), a frame-capture + flash-rate analyzer, and a documented drivable render↔control IPC contract — before the first line of engine code.
3. **[M1]** Add a decode-isolation ADR (out-of-process sandboxed media/font decode) or explicitly narrow the NFR-024 "structural isolation" claim; separate security isolation from fault isolation; state per-platform sandboxing posture. Include decoder/interop crash in the S2 fault-injection matrix.
4. **[M2]** Close OD-19: decide the Linux no-keyring key-custody fallback and record the "never silently fall back to plaintext" invariant in ARCHITECTURE §11 — this is MVP for Linux.
5. **[M3]** Commit a structured live-scene text IPC payload feeding aria-live, and either pull live-state read-back into NFR-021 MVP or state in §22 that MVP AT excludes fully non-visual live driving.
6. **[M4]** Constrain the default flashing TIME UP to satisfy the red-flash and flash-area sub-criteria (or make solid-inverted the default); extend the FR-175 acceptance test beyond ≤3/sec.
7. **[M5]** Produce, before Stage-7, the versioned LAN message schema + command→role matrix + replay/nonce algorithm as the single source of truth for authorization, fuzz, and host/mobile contract tests; pull the device-auth handshake/PoP design (M7) into an early spike.
8. **[M6]** Define the latency/preview/flash measurement methodology in the harness spec (depends on B2).
9. **[M7]** Specify a GPU-hardware CI matrix per interop backend as an ongoing target with a deterministic device-loss recovery assertion; pin wgpu and gate upgrades on re-running it.
10. **[M8]** Bind Go Live to a distinct key never overloaded with Next; settle the Undo-live model; propagate to all three docs.
11. **[M9]** Standardise the preview/live/warn colour tokens (green/red/amber) across all UX docs.
12. **[M10]** Reconcile emergency reachability with focus-trapping modals (pierce, or ban blocking modals over live controls during a service); add a testable row.
13. **[M11]** Add the Cloud-provider consent flow + state-matrix surface before that surface is built (R3 timing).
14. **[M12]** Resolve OD-20: state the MVP host command-serialization model and arbitration; add a "contested" state — before the mobile control path is implemented.
15. **Minors m1–m16** tracked and dispositioned; m1 (count 79→84), m11 (FR-075 N/window), m15 (FR-063 MVP/R2 trace) are cheap correctness fixes that should be closed alongside the majors.

---

## Strengths (carried forward from the lens reviews)

- **Coverage is genuinely complete:** every one of the 84 PRD MVP FRs maps to an owning component in the §15 matrix (verified line-by-line); every brief feature-domain is addressed; TTS is correctly and consistently excluded as a non-goal (NG-1/DEC-001).
- **The ADRs are rigorous and intellectually honest:** each records real options with trade-offs, tags evidence (candidly noting FEASIBILITY has 0 OBSERVED findings), pre-commits concrete fallbacks, and gates risky sub-decisions on named spikes (S1–S11) rather than asserting confidence it lacks.
- **The load-bearing brief correction** — WebView is the operator console, NOT the compositor — is argued from documented WebView GPU limits and cleanly separated across ADR-0002/0003, standing independent of spike outcomes.
- **AI-never-blocks-core (FR-083) is enforced by construction:** an always-present resident local provider + out-of-band isolation + bounded one-way channels mean no provider state can block core controls; the render loop structurally never awaits AI (ADR-0010). The capability-interface is a clean, mockable seam for provider-failure tests.
- **Desktop-authoritative and offline-first are structural:** single-writer data layer as sole DB owner (ADR-0007), host-side deny-by-default RBAC with client role never trusted, mobile holding no authoritative state, LAN security bootstrapped entirely from an out-of-band QR with no CA/cloud dependency (ADR-0008/0009).
- **Security is defense-in-depth and faithfully mapped to the threat model:** correct CA-less TOFU pinning defeats LAN MITM (T1/T2/T18); pairing is single-use, short-TTL, host-confirmation-gated; privacy-by-default is structural (local-first AI default, cloud opt-in/per-provider/Administrator-gated with persisted+audited consent and a live indicator); supply-chain/update posture is specific and current (full-artifact signature verification, anti-rollback, offline signing keys, CVE-2025-0509 remediation, NFR-027 SBOM/CVE gate).
- **Fail-closed control plane composes with output-failure isolation:** rejecting an unauthenticated/replayed/over-rate/malformed message can never blank the live output; loss of all controllers leaves the desktop fully capable.
- **Testable seams already present:** the two-process split makes output-failure isolation structural; persistence fault-injection is concretely specified (kill-mid-write + PRAGMA integrity_check); FR-171 is a model of testable AI acceptance (named eval-set artifact, S11 delivery, provisional-until-measured thresholds); observability (tracing spans + cross-process correlation IDs) is the measurement substrate; the deterministic scripture-reference parser is separately unit-testable; timer accuracy is a clean accuracy-test seam.
- **Accessibility is a first-class, QA-diffable deliverable:** the UX-STATE-MATRIX gives an explicit Accessibility column for all ten states across every surface; colour-is-never-the-only-signal is applied consistently; reduced-motion/flash-safety are designed in and information-preserving; mobile meets ≥44×44pt with accidental-tap protection; ADR-0003 makes the keyboard/SR bar an explicit S5 gate with a Rust-native fallback trigger.
- **UX live-safety is strong where it is reconciled:** a fixed 10-state vocabulary across 12 surfaces with justified N/A entries; excellent timer/TIME-UP audience safety (audience outputs default-excluded, T3 arm-then-fire, monotonic clock); an explicit "CLEARED"/"BLACKOUT ACTIVE" empty state that never lies about output; fail-safe GO LIVE disabling; connection-status handling that rejects-not-replays stale actions on reconnect; airtight AI human-gating (violet side queue, polite semantics, corroboration-gated auto-display).

---

## Independence statement

This adjudication was performed with fresh context. I did not author the ARCHITECTURE document, any of the 14 ADRs, the PRD, the threat model, or the three UX specification documents under review, and I hold no stake in their conclusions. My role was limited to adjudicating the five independent lens reviews against the stated gate rule, verifying internal consistency between them, de-duplicating overlapping findings across lenses (merging the emergency-keybinding defect raised by both the UX and Accessibility lenses into a single blocker; merging the media/font decode-isolation defect raised by both the Architecture and Security lenses into one major; and merging the multi-controller conflict-resolution defect raised by the Architecture, Security, and UX lenses into one major at the highest asserted severity), and rendering a consolidated verdict. Findings, severities, and recommendations originate from the lens reviews; the adjudication assigns the package-level verdict and the conditions to clear the gate.

---

# Re-review outcome (Stage-5 RE-REVIEW adjudication)

**Date:** 2026-07-23
**Role:** Lead reviewer, adjudicating three independent verifier groups covering B1, B2, and M1–M12.
**Inputs:** Verifier reports for groups `stage5-rereview-B1-B2-M6-M7`, `M1/M2/M5/M12`, and `M3/M4/M8/M9/M10/M11`.

## Verdict: PASS WITH CONDITIONS

**Gate rule applied:** PASS only if BOTH blockers (B1, B2) and ALL 12 majors are `discharged` with no new blocker/major regression; FAIL if any blocker is not discharged or a new blocker is raised; otherwise PASS WITH CONDITIONS.

Both blockers are discharged and no new blocker was raised — so the package does **not** FAIL. However, two of the twelve majors (M2, M11) landed at `partial`, and the verifiers raised **three new major regressions**. Full PASS is therefore not met. The adjudicated outcome is **PASS WITH CONDITIONS**: the two day-one blockers are cleared at the authority/architecture level (safe to begin Stage-6/7 engine and mobile design), contingent on closing the two partial majors and the three new majors before the dependent implementation is written.

Independent spot-check (fresh reads of the source docs, not relying on the verifier prose): every load-bearing claim behind the two partials and the three new majors was reproduced against the files — UX-CANONICAL.md §1 lines 16–17/22 (Esc Esc = Clear all, B = Blackout) vs UX-STATE-MATRIX.md lines 79/412 (still Esc Esc → blackout, . → clear); PRD FR-159 R3 scoping (line 335) and PRD §33 (line 476) still listing OD-19/OD-20 "still open" vs ARCHITECTURE §11 (line 105) and OPEN-DECISIONS OD-19/OD-20 (lines 49–50) marked DECIDED/MVP; UX-FLOWS flows ending at Flow 11 (line 630) with a dangling "Flow-N settings" cloud reference (line 568); and ADR-0015 lines 19/26 defining the parity oracle as "byte-reproducible frames … across OSes/GPUs" with no perceptual tolerance. All confirmed.

## Per-item discharge table

| Item | Original severity | Re-review status | Basis |
|---|---|---|---|
| **B1** — Emergency keybindings contradict across UX docs | Blocker | **Discharged** | UX-CANONICAL.md is now the single authoritative source; §1 table fixes `Esc Esc`=Clear-all and `B`=Blackout with non-unbindable global fallbacks (`Ctrl/Cmd+Shift+.` / `+B`); line 22 states the canonical meaning "resolves B1"; all three UX docs carry a superseding header pointer; single-Esc collision removed. Authority-level inversion resolved. *(Residual literal contradictions → new major NM-3.)* |
| **B2** — No test seam for the bespoke Rust+wgpu engine | Blocker | **Discharged** | ADR-0015 (Accepted, High) commits the full seam as day-one design: headless/offscreen render + CPU readback sharing on-screen code; deterministic render mode (fixed clock/seed); fault-injection hooks (GPU device-loss, decoder fault, IPC stall, disk-full); frame-capture + flash/luminance analyzer + latency proxy; versioned drivable render↔control IPC contract. Mirrored in ARCHITECTURE §12. *(Parity-oracle tolerance gap → new major NM-1.)* |
| **M1** — Untrusted decode in-process (reliability + RCE) | Major | **Discharged** | ADR-0016 (Accepted, High) mandates out-of-process sandboxed decode with concrete per-platform sandboxes; separates fault isolation from security isolation; exercised by the ADR-0015 fault hook + spike S2. *(Two doc-consistency minors: PRD NFR-024 unchanged; ADR-0005 not cross-referenced.)* |
| **M2** — No decided Linux key-custody path w/o Secret Service | Major | **Partial → NOT discharged** | Decision recorded in ARCHITECTURE §11 and OPEN-DECISIONS OD-19 (Argon2id vault, never plaintext, "holds for MVP on Linux"), but **contradicted at the requirement layer**: PRD FR-159 is scoped **R3** (line 335, and in the R3 FR list line 521) and PRD §33 (line 476) still lists OD-19 as "still open at PRD time." MVP secrets (device tokens/keypairs, FR-089 under NFR-017) need custody at MVP on headless Linux, so the binding requirement must be MVP. Decided but not propagated to the normative PRD. |
| **M3** — No structured live-scene text channel for SR baseline | Major | **Discharged** | ARCHITECTURE §13 commits a structured live-scene text payload → aria-live region; PRD NFR-021 upgraded so MVP requires live-state announcement. *(Minor: NFR-021 cites "ADR-0015 §13" — payload lives in ARCHITECTURE §13.)* |
| **M4** — Default flashing TIME UP under-specifies red-flash/area | Major | **Discharged** | **Re-discharged 2026-08-23 under option (a)** — the default TIME UP carries a ≤0.5 Hz word pulse, measured through the ADR-0015 analyzer across all three stage templates: worst **0.500 red flashes/sec** (limit 3.0, a 6× margin), pulsing area **4.18 %** at 1080p on the whole-screen Timer-only case (WCAG small-safe limit 25 %). Positive control: a 6 Hz strobe through the same harness reports 6.000/6.000, passes=false. Evidence: `selahcue-present/tests/test_stage_flash.rs`. Prior grounds were option (b), PRD FR-059 default = solid-inverted static; FR-175 bounds ≤3 general + ≤3 red flashes/sec + small-safe area (WCAG 2.3.1) via the ADR-0015 analyzer; UX-CANONICAL §5 matches. *(Minor: PRD §32 summary still reads "≤3 flashes/sec".)* |
| **M5** — LAN protocol/RBAC contract deferred past when Stage-7 needs it | Major | **Discharged** | ARCHITECTURE §9 adds a "Protocol-spec deliverable (M5)": versioned schema + command→role matrix (7×14 in PERSONAS §2) + replay/nonce algorithm produced before Stage-7 as the single oracle for contract/RBAC/fuzz tests. *(Minor: reconnect-nonce spike not named as a distinct forward spike.)* |
| **M6** — Perf/safety launch-gate metrics have no measurement method | Major | **Discharged** | ADR-0015 item 4 + Consequences define the normative measures: latency proxy for NFR-004/METRIC-002, preview-capture point for FR-013, flash-rate analyzer for FR-175. *(Minor: proxy stops at pixel readback, omits present+scan-out tail → NM-caveat, minor.)* |
| **M7** — No ongoing GPU-hardware regression environment | Major | **Discharged** | ADR-0015 Consequences + ARCHITECTURE §12 commit a per-backend GPU CI matrix (VA-API/NVDEC/Metal/D3D11) running deterministic parity + device-loss-recovery assertions; wgpu pinned, upgrades gated. Framed as ongoing CI, not one-time spikes. |
| **M8** — Live-action key semantics (Space, ⌘Z) inconsistent | Major | **Discharged** | UX-CANONICAL §1 binds Go Live = Enter ("never overloaded with Next"); Next = Space/→; §2 settles Undo-live (authoring only, never un-does a live trigger). *(Residual inline: UX-STATE-MATRIX §6/§15.1 still list Space/Ctrl+Enter as Go-Live → new major NM-3.)* |
| **M9** — Preview/Live colour vocabulary disagrees; amber double-books | Major | **Discharged** | UX-CANONICAL §4 defines one token set (green=preview, red=live, amber=warn, grey=neutral) with non-colour redundancy (WCAG 1.4.1). *(Residual inline: UX-STATE-MATRIX §2/§3 still amber=PREVIEW → new major NM-3.)* |
| **M10** — Emergency reachability unreconciled with modals | Major | **Discharged** | UX-CANONICAL §3: emergency keys pierce any modal; blocking modals over live chrome prohibited; always-on emergency chrome is a testable UI invariant; mirrored in UX-STATE-MATRIX header + §3 contract row. *(Residual inline: §3 row still annotates Esc Esc→blackout → new major NM-3.)* |
| **M11** — Cloud consent surface has no flow / no state-matrix coverage | Major | **Partial → NOT discharged** | Intent recorded (UX-STATE-MATRIX header enumerates the consent states; PRD FR-132/133/177 cover disclosure). But the **two artifacts the review demanded are not produced**: no consent FLOW exists (UX-FLOWS ends at Flow 11; line 568 still dangles a non-existent "Flow-N"), and no dedicated per-surface state-matrix table with the ●CLOUD-ACTIVE transition. A header sentence + dangling pointer is a promise, not the deliverable. R3 timing (non-MVP-blocking) but required before the surface is built. |
| **M12** — Multi-controller arbitration undefined; MVP ships pairing | Major | **Discharged** | ARCHITECTURE §9 + OD-20 (DECIDED): host totally orders commands, deterministic last-writer-wins, losing device gets a "contested" response; contested state declared in UX-STATE-MATRIX header + COMPONENT-SPECS §36. *(Minor: UX-STATE-MATRIX §17 still lists OD-20 as an "open UX decision," and the contested state is header-declared rather than integrated as a testable cell; PRD §33 also still lists OD-20 open.)* |

**Tally:** 12 of 14 items discharged (B1, B2, M1, M3, M4, M5, M6, M7, M8, M9, M10, M12). **Not discharged (partial):** M2, M11.

## New findings raised in re-review

### New majors (regressions / newly-surfaced gaps — 3)

- **NM-1 (Testability, relates to B2) — Parity oracle acceptance criterion is infeasible-as-written.** ADR-0015 item 2 defines the cross-platform parity oracle as producing "byte-reproducible frames … used for golden-image parity tests across OSes/GPUs" (ADR-0015 lines 19/26). Byte-identical rendering across different GPU vendors/drivers is generally infeasible (rasterization, filtering, floating-point differences), and B2's exact-change explicitly asked for readback "within a defined perceptual tolerance (the parity oracle for NFR-014)." No perceptual tolerance is defined, so NFR-014/METRIC-010 ("identical" / "100% test-matrix pass") is anchored to a gate that is either unachievable on real hardware or silently relaxed to per-backend goldens (in which case cross-platform parity is not actually pixel-compared). **Fix:** define the perceptual comparison metric and pass/fail tolerance for the parity gate; reserve byte-equality for same-backend determinism only.

- **NM-2 (Security/PRD propagation, is the cause of M2 partial) — MVP Linux secret-custody requirement is deferred to R3 in the PRD.** PRD FR-159 is scoped R3 (line 335, R3 FR list line 521) and PRD §33 (line 476) still lists OD-19 "still open at PRD time," contradicting ARCHITECTURE §11 (line 105) and OPEN-DECISIONS OD-19 (line 49) which state the Argon2id-vault/never-plaintext invariant "holds for MVP on Linux." Because MVP secrets (device tokens/keypairs FR-089 under MVP NFR-017) require custody at MVP on headless/no-Secret-Service Linux, deferring the encoding requirement to R3 reintroduces the exact hole M2 flagged. **Fix:** retag FR-159 MVP (Linux) and update PRD §33 to reflect OD-19 (and OD-20) as resolved.

- **NM-3 (UX/live-safety, relates to B1/M8/M9/M10) — Inverted/contradictory bindings physically persist in the QA-referenced normative UX docs.** The remediation created an authoritative UX-CANONICAL.md that "wins by reference" but left the old conflicting text in place, so UX-STATE-MATRIX.md still directly contradicts the authority on safety-critical items: lines 79 and 412 still say `Esc Esc` → blackout / `.` → clear (the exact panic-key inversion that made B1 a blocker); §6 still lists Space as a Go-Live key in Preview focus (M8 hazard); §2/§3 still show amber = PREVIEW double-booked with amber = warn (M9). B1's explicit requirement — "one canonical binding table used **identically** by all three UX docs and by QA" — is met at the authority level but not literally. Leaving inverted emergency-blackout semantics in a live-safety spec is a residual hazard. **Fix:** reconcile (or at minimum strike) the contradictory binding/colour cells in UX-STATE-MATRIX and COMPONENT-SPECS **before Stage-7**, not deferred to Stage-7 edits; route to the B1 re-reviewer.

*(No new blocker was raised. NM-3 does not re-open B1 to blocker status: the authority mechanism — canonical file wins, QA tests against it — resolves the safety inversion at the decision level; but given B1's weight the literal reconciliation is pulled forward as a hard condition.)*

### New minors (7, tracked — do not affect the verdict)

1. **(B2/M6)** Latency proxy terminates at CPU pixel readback and omits GPU present + display scan-out (~16–33ms at 60Hz); state the assumed present/scan-out allowance or an external-instrumentation cross-check so the proxy's relation to the physical ≤150/≤80ms bar is explicit.
2. **(B1)** The "delete the Esc Esc=blackout / .=clear variants" step is deferred to Stage-7; pull it before implementation given B1's safety weight. *(Overlaps NM-3; kept as the minor edit-hygiene item.)*
3. **(M1)** ADR-0016 claims NFR-024 wording is updated in PRD, but PRD NFR-024 (line 400) still reads as output-blanking (fault) isolation only, with no security/RCE-containment clause. Amend PRD NFR-024 or drop the ADR claim.
4. **(M1)** ADR-0005 was not updated to reference ADR-0016; it still frames decode as in-process "out-of-band" recovery. Add an ADR-0016 cross-reference/superseding note.
5. **(M3)** PRD NFR-021 cites "ADR-0015 §13"; the payload/aria-live commitment lives in ARCHITECTURE §13 (ADR-0015 has no §13). Correct the cross-reference.
6. **(M4)** PRD §32 launch-criteria summary (line 511) still reads "≤3 flashes/sec verified"; update to the extended general+red+area FR-175 check.
7. **(M12)** UX-STATE-MATRIX §17 still lists OD-20 as an "open UX decision," contradicting its own header and OD-20's DECIDED status; and the contested state is header-declared rather than integrated as a testable per-surface state cell. Reconcile §17 and add the contested row to the Live/Program and Mobile-Populated tables.

## Conditions to close (before the dependent Stage-6/7 work)

1. **[M2 / NM-2]** Retag PRD FR-159 to **MVP (Linux)** and update PRD §33 so OD-19 (and OD-20) read as resolved — bind the never-plaintext fallback at MVP, matching ARCHITECTURE §11 / OD-19.
2. **[M11]** Author the Cloud-provider consent **flow** (resolve the dangling "Flow-N" in UX-FLOWS) **and** a dedicated state-matrix **surface table** (per-state see/do/transition/accessibility + the ●CLOUD-ACTIVE transition) before that R3 surface is built.
3. **[NM-1]** Define the perceptual comparison metric and pass/fail tolerance for the cross-backend parity gate in ADR-0015; restrict "byte-reproducible" to same-backend determinism.
4. **[NM-3]** Reconcile the inline safety-critical text in UX-STATE-MATRIX (lines 79/412 Esc Esc→blackout, §6 Space=Go-Live, §2/§3 amber=PREVIEW) and COMPONENT-SPECS with UX-CANONICAL before Stage-7; route to the B1 re-reviewer.
5. **[Minors 1–7 above]** Tracked; the cheap correctness fixes (NFR-021 cross-ref, PRD §32/NFR-024 wording, ADR-0005 cross-ref, UX-STATE-MATRIX §17) should close alongside the conditions.

## Re-review independence statement

This re-review adjudication was performed with fresh context. I did not author the ARCHITECTURE document, any of the 16 ADRs (including the new ADR-0015 and ADR-0016), the PRD, the threat model, the OPEN-DECISIONS register, or the four UX specification documents (UX-CANONICAL, UX-FLOWS, UX-STATE-MATRIX, COMPONENT-SPECS), and I hold no stake in their conclusions. My role was limited to adjudicating the three independent verifier groups against the stated gate rule, independently spot-checking each load-bearing claim behind the two partial majors (M2, M11) and the three new majors directly against the source files rather than accepting the verifier prose, and rendering the consolidated re-review verdict. The per-item statuses, new findings, and severities originate from the verifier groups and were confirmed on independent reading; the adjudication assigns the package-level re-review verdict and the conditions to close.
