# SelahCue — Implementation Readiness

Date: 2026-07-23 · Owner: Delivery Manager · Stage 6

## Status: READY

The PRD (audit PASS), architecture (+16 ADRs, independent review passed), and UX (specs + Figma) are approved; ClickUp epics and the first-release stories exist with owners, requirement traceability, acceptance criteria, and required tests; the dependency graph is acyclic with a defined critical path; and the first implementation release is a coherent, demonstrable vertical-slice set. **Production implementation may begin at Stage 7 upon user approval of this gate.**

## MVP boundary (from PRD §30)

The reliable **presentation foundation** on Windows/macOS/Linux + a secure, feature-scoped mobile controller. Phased later releases R2–R6. TTS is a non-goal (DEC-001). MVP capacity assumption: small dedicated team over a multi-month schedule (AS-6), presentation-core desktop sub-release before the mobile control-plane slice.

## First implementation batch (Stage 7 — foundation)

A single coherent vertical-slice set that lights up the core live loop and every reliability guarantee:

1. Walking skeleton (Rust core + native output window + Tauri shell) — `86ajp09c2` · **ready**
2. Persistence (SQLite WAL + SQLCipher + migrations) — `86ajp09he` · **ready**
3. Testable render seam (headless/deterministic/fault-injection/IPC) — `86ajp09m9` · **ready**
4. CI + test infra (per-OS + GPU matrix) — `86ajp09nk` · **ready**
5. Design system + canonical keybindings + emergency chrome — `86ajp0b3d` · **ready**
6. Autosave + crash recovery + crash-loop breaker + storage guard — `86ajp09td`
7. Service plan model + CRUD + library — `86ajp0a4z`
8. Basic presentation: static slide → main output (preview→live) — `86ajp0a6q`
9. Stage / confidence display output — `86ajp0aa4`
10. Timer foundation + TIME UP (monotonic, seizure-safe) — `86ajp0ac9`
11. Static scripture display (PD translations + parse + search) — `86ajp0afa`
12. Emergency clear / blackout + per-layer — `86ajp0awx`
13. Missing-media detection + pre-service check — `86ajp0az9`
14. Basic mobile pairing (QR + pinned TLS + RBAC) + slide advance — `86ajp0b0t`

**Foundation demo (Stage 7 gate):** launch on 3 OSes → build a plan → static slide on main output → stage display → countdown to TIME UP (stage-only) → search & display a PD scripture → emergency blackout/clear offline → pair mobile by QR + advance a slide → force-kill + recover exact live state. (Milestone `86ajp0bpn`.)

## Dependency graph (acyclic — machine-checkable)

Epic-level and foundation-story-level edges (`A -> B` = A blocks B / B depends on A). Nodes are epic short-names and story numbers.

```dependency-graph
Foundation -> ServicePlanning
Foundation -> Outputs
Foundation -> Reliability
Foundation -> Admin
Foundation -> Accessibility
Foundation -> Media
Accessibility -> Presentation
Outputs -> Presentation
Outputs -> Timers
Outputs -> Media
Outputs -> Reliability
Presentation -> Scripture
Presentation -> Mobile
Timers -> Mobile
Scripture -> Mobile
Admin -> Mobile
S1-walking -> S2-persistence
S1-walking -> S3-renderseam
S1-walking -> S14-designsystem
S3-renderseam -> S4-ci
S3-renderseam -> S7-presentation
S3-renderseam -> S8-stage
S3-renderseam -> S9-timer
S2-persistence -> S5-autosave
S2-persistence -> S6-serviceplan
S2-persistence -> S10-scripture
S14-designsystem -> S7-presentation
S14-designsystem -> S11-emergency
S6-serviceplan -> S7-presentation
S6-serviceplan -> S12-missingmedia
S7-presentation -> S8-stage
S7-presentation -> S10-scripture
S7-presentation -> S11-emergency
S7-presentation -> S13-mobile
S9-timer -> S8-stage
S10-scripture -> S13-mobile
Admin -> S13-mobile
```

## Critical path

Walking skeleton → Testable render seam → Basic presentation → Stage display / Emergency → **Foundation demo**. In parallel: Persistence → Service plan → Basic presentation; Design system → Presentation/Emergency; Admin (secret store/RBAC) → Mobile pairing. The **LAN protocol spec (ADR-0008/M5)** is a pre-implementation deliverable for the Mobile story.

## Risks carried into implementation

| Risk | Mitigation |
|---|---|
| Zero-copy HW-decode→GPU (spike S2) | Fallback glvideomixer / 1080p30 (ADR-0006; RISK-013/014) — validated in Media |
| Multi-monitor fullscreen (spike S4) | Borderless-per-monitor fallback — validated in Outputs |
| Scope breadth (RISK-001) | MVP bounded; foundation first; core-MVP decomposed at Stage 8/9 |
| Real-room AI accuracy | Deferred to R3/R4; operator-in-the-loop defaults; eval-set spike S11 |

## Gate

Stage 6 completion: PRD audit PASS · every requirement mapped (REQUIREMENTS-TRACEABILITY.md) · epics + first-release stories in ClickUp with owners/AC/tests · dependency graph valid (this file) · first release coherent · **READY** · validators pass. Next: Stage 7 (implementation foundation) — requires user approval at this gate.
