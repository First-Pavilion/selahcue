# SelahCue — Cross-Functional Decision Log

Durable record of material product/scope/architecture decisions, with traceability. Newest first.

---

## DEC-002 — RBAC: the Assistant role may navigate/clear the live output (kept as-is)

- **Date:** 2026-07-23
- **Stage:** Stage 7 gate (batch 7d)
- **Decided by:** User (product owner)
- **Type:** RBAC policy confirmation
- **Status:** DECIDED (revisit-later)

**Context.** The batch-7d independent review flagged that `Command::Clear` maps to the `Navigate` permission, which the **Assistant** role holds — so an Assistant can blank the live output, whereas `Blackout` is gated to Producer+. The reviewer verified this is deliberate and test-locked (not an accidental mis-mapping), but noted it sits in tension with the Assistant docstring ("cannot push to the live output") and raised it as a product policy question.

**Decision.** Keep the current policy: **Assistant retains `Navigate` (Next/Previous/SelectItem/Clear)**; `GoLive`, `Blackout`, and `Timer` remain Producer+. No code change.

**User rationale.** "Let's keep as is. We can revisit later if there's a need to."

**Affected items.** `selahcue-lan::rbac` (unchanged); the RBAC matrix in `crates/selahcue-lan/src/rbac.rs` and its tests remain authoritative.

**Reversibility.** Trivially reversible — move `Clear` (and/or the `Navigate` grant for Assistant) to a higher permission tier and update the `test_rbac` matrix. Revisit if operators report Assistants disrupting live output.

---

## DEC-001 — Text-to-Speech (TTS) removed from the product roadmap (de-scoped)

- **Date:** 2026-07-23
- **Stage:** Stage 2 gate (refine)
- **Decided by:** User (product owner)
- **Type:** Scope reduction (authorized at gate)
- **Status:** DECIDED

**Decision.** TTS is **not** a requirement for SelahCue's MVP or its planned roadmap. It is reclassified from "later release" to a **non-goal / on-hold** feature, revisited only if the user explicitly requests it in future.

**User rationale.** "Let's hold off on TTS. I don't see it as a major requirement in the long run."

**Supporting evidence (discovery).** Independent research already assessed TTS as the **lowest-value** of the four AI features (a presentation app's congregation reads the screen) and the **highest live-room risk** (audio feedback, mic bleed / self-re-transcription, accidental routing to the house system). See [../research/PROVIDER-TRADEOFFS.md](../research/PROVIDER-TRADEOFFS.md) §3, [../research/CAPABILITY-ASSESSMENT.md](../research/CAPABILITY-ASSESSMENT.md), and open decision OD-02. Discovery already recommended deferring it; the user's decision goes further and removes it from the roadmap.

**Affected items.**
- Product brief `product/PRODUCT-BRIEF.md` §"Text-to-speech requirements" → now a documented non-goal (brief remains the historical source; PRD will mark TTS as an explicit non-goal with this decision cited).
- Open decision **OD-02** → DECIDED (hold off).
- Risk **RISK-008** (TTS audio routing / feedback) → no longer active roadmap risk; retained as conditional (re-activates only if TTS is reconsidered).
- **Stage 11** ("Sermon intelligence and TTS") → becomes **"Sermon intelligence"** only; TTS deliverables dropped.
- Build Goal Contract `BUILD-selahcue.md` → TTS added to Non-goals; TTS-specific sub-clauses of completion predicates C-013/C-018/C-019/C-021 become NOT_APPLICABLE.
- Voice-selection/routing/pronunciation/audio-export TTS work → removed from scope.

**Impact.** Reduces scope and live-service risk; simplifies the audio path (no TTS output-routing/feedback-safety subsystem). No negative impact on core presentation, transcription, scripture detection, or sermon notes. Accessibility use cases that TTS might have served are noted for the PRD's accessibility section to address by other means (e.g. screen-reader compatibility, large-text/high-contrast) rather than built-in TTS.

**Reversibility.** Fully reversible before implementation; TTS research artifacts are retained. Re-scoping TTS back in would return to Stage 2/3 for that feature only.
