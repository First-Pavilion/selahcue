# SelahCue — Initial Risk Register (Stage 1)

Date: 2026-07-23 · Owner: Delivery Manager · Status: Living document

Scoring: Likelihood (L) × Impact (I) on 1–5. Rating = L×I. Review each stage gate.

| ID | Risk | Category | L | I | Rating | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| RISK-001 | Scope breadth (presentation + multi-output + transcription + scripture AI + sermon notes + TTS + mobile + 5 platforms) is far too large for a single release | Scope | 5 | 5 | 25 | Enforce MVP boundary in PRD (Stage 3); phase per brief §Release planning; Stage 4 audit checks for oversized scope; first release bounded to presentation foundation | Product Manager | Open |
| RISK-002 | Bible-translation licensing — bundling copyrighted translations (NIV/ESV/etc.) is prohibited without permission | Licensing | 4 | 5 | 20 | RP-07 licensing register; MVP ships public-domain translations (KJV/WEB) + user-supplied/API path for licensed ones; attribution metadata model | Product + Security | Open |
| RISK-003 | Automatic scripture detection (quoted/paraphrased) accuracy — false positives/negatives, accents, noisy rooms; risk of overpromising | Feasibility/AI | 4 | 4 | 16 | RP-04 realistic assessment; default to operator-confirmation mode; deterministic parser prioritised; document limitations; never claim perfect accuracy | AI Engineer | Open |
| RISK-004 | Offline transcription feasibility & performance — local Whisper-class models vs low CPU/memory target may conflict | Feasibility/Perf | 4 | 4 | 16 | RP-03/RP-09 benchmarks; tiered model sizes; cloud/hybrid opt-in; lazy model loading; measured targets in PRD | AI + Architect | Open |
| RISK-005 | Reliability during 8–12h live services — AI/provider/display/audio/network failures must never block core presentation | Reliability | 4 | 5 | 20 | Architecture isolates AI/providers from presentation core; offline-first core; fault-injection tests (Stage 12); autosave/crash recovery; emergency clear/blackout without network | Architect + QA | Open |
| RISK-006 | "PM artifact validator" referenced by brief/skill does not exist in the repo | Tooling/Process | 3 | 3 | 9 | Define + implement a real PM artifact validator during Stage 3 (validates PRD structure, requirement IDs, acceptance criteria, MVP separation, traceability) before it gates Stage 3/6; surfaced now, not hidden | Delivery + Product | Open |
| RISK-007 | Chrome MCP requested by brief for reference-product study is not confirmed available; deep proprietary workflows may be inaccessible | Research | 3 | 3 | 9 | Use WebSearch/WebFetch + public docs/videos/trials; mark inaccessible internals UNKNOWN; do not infer proprietary internals | Product Researcher | Open |
| RISK-008 | TTS audio routing — accidental playback through main sound system, or audio feedback into transcription mic | Safety/UX | 3 | 4 | 12 | **RETIRED** — TTS removed from roadmap by [DEC-001](DECISION-LOG.md is docs/decisions/DECISION-LOG.md) (2026-07-23). Risk no longer active; re-activates only if TTS is reconsidered. | AI + QA | Retired |
| RISK-009 | Cross-platform packaging, multi-display output, and code-signing across Win/macOS/Linux + two mobile OSes | Delivery/DevOps | 4 | 3 | 12 | Tech-stack choice weighs packaging (Stage 5 ADR); CI per platform (Stage 7); bound platform scope if needed at a gate | DevOps + Architect | Open |
| RISK-010 | Privacy of sermon recordings/transcripts + cloud provider disclosure/consent + secure API-key storage | Privacy/Security | 4 | 4 | 16 | Cloud opt-in + visible disclosure; no transcript leaves device without explicit action; platform secret storage; data-retention/deletion controls; Stage 4 + security reviews | Security Reviewer | Open |
| RISK-011 | Not under version control — no git repo, so work is not yet tracked/rollback-safe | Delivery | 3 | 3 | 9 | git init (Stage 2) → pushed to github.com/First-Pavilion/selahcue with 3-OS CI (2026-07-24) | Delivery | **Closed** |
| RISK-015 | Dependabot #1: `glib 0.18.5` unsoundness advisory (GHSA-wrw7-89jp-8q8g, RUSTSEC informational) — transitive via Tauri v2's Linux GTK3 stack in the operator crate; patched only in glib 0.20, which Tauri v2 cannot use yet (`^0.18` pin). Linux-only code, no direct usage in our crates, no attacker-controlled GVariant path → residual risk low. Ecosystem-wide for Tauri v2 apps. | Security | 2 | 2 | 4 | **Accepted + tracked** (owner: user, 2026-07-24). Revisit trigger: Tauri migrating off gtk-rs 0.18 (watch tauri releases), or the advisory being upgraded from unsound→exploitable. cargo-audit intentionally stays green (informational class); Dependabot keeps it visible. | Security | Accepted |

## Notes

- RISK-001 and RISK-005 are the two highest-leverage risks and directly shape the PRD MVP boundary and the architecture's reliability posture.
- New risks discovered in later stages are appended here and mirrored as ClickUp risk items on the Build Control task.
