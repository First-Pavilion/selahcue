# SelahCue — Cross-Functional Decision Log

Durable record of material product/scope/architecture decisions, with traceability. Newest first.

---

## DEC-006 — Customer identity: self-hosted open-source IdP (Logto) via OIDC

- **Date:** 2026-08-10
- **Stage:** Customer-identity workstream (resolves the DEC-005 open IdP-technology sub-decision)
- **Decided by:** User (product owner)
- **Type:** Architecture (identity)
- **Status:** DECIDED (technology direction) — implementation approach to be detailed in an ADR

**Decision.** Customer sign-in / identity uses a **self-hostable open-source IdP** — **Logto** as the leading candidate (or a comparable OSS self-hostable IdP, e.g. Zitadel/Keycloak/Authentik/Ory) — integrated via **OIDC**. SelahCue self-hosts the IdP rather than adopting a paid managed provider or building auth from scratch.

**User rationale.** "Use free alternatives… like Logto or something we can even host ourselves." Keeps church identities self-hosted (consistent with the privacy-first, offline-first, no-vendor-lock-in posture and DEC-004's self-hosted model), avoids per-user managed-IdP cost, and avoids owning/hardening bespoke auth code.

**Implications (to be detailed in an ADR + decomposed into tasks).**
- **Desktop** is a native OIDC client → Authorization Code + **PKCE** flow for account sign-in; the org **enrollment key** remains the secondary/offline-friendly activation path (DEC-004).
- **Platform API** becomes an OIDC relying party / resource server: validate Logto-issued tokens, map the IdP subject → a SelahCue **CustomerOrg**/account; account-based device activation runs **alongside** the existing enrollment-key `/v1/activations`.
- **Devops:** self-host + operate Logto (deployment, backup, upgrades, data-residency); auth is one-time online (activation), so offline-first still holds (offline entitlement = license window, DEC-005).
- Session/token/refresh model, MFA/password-reset (provided by the IdP), and account↔org mapping to be specified in the ADR.

**Still open (for the ADR/architecture).** Final IdP product choice (Logto vs alternatives) after a short evaluation; token-validation model (JWKS/introspection); account↔CustomerOrg mapping + multi-user-per-org roles; self-hosting topology + data residency; migration/coexistence with the enrollment-key path.

**Reversibility.** OIDC is a standard interface, so the specific IdP product is swappable; the enrollment-key activation path already shipped remains valid regardless.

---

## DEC-005 — Account setup: build real customer sign-in / IdP now; offline entitlement = full license window (no separate grace)

- **Date:** 2026-08-09
- **Stage:** Account-setup / Platform API (post-DEC-004 licensing build)
- **Decided by:** User (product owner)
- **Type:** Product + architecture scope (builds on DEC-004)
- **Status:** DECIDED

**Decision.** For the Desktop **Account setup** flow:

1. **Build real customer sign-in / IdP now** (not deferred). Account sign-in is the primary, shipped activation path; the org **enrollment key stays the secondary/OPTIONAL** bootstrap (per DEC-004). This adds a customer-identity workstream: customer accounts, authentication, sessions, and account-based device activation on the Platform API + a real sign-in on the desktop. (The design already leads with "Sign in to your SelahCue account" as primary; enrollment key is OPTIONAL.)
2. **Offline entitlement = the full license validity window; no separate offline-grace timer/nudge.** The cached entitlement (device token) is valid until the license itself expires — the token-lifetime==license-window behaviour already built in the device-activation slice. Simplest model; never blocks presentation (NFR-024).

**User rationale.** Chose "build real IdP now" over enrollment-key-first-defer, and "match full license window" over a 30-day/7-day grace, in the account-setup PM decision round.

**Affected items.**
- Reverses the enrollment-key-first *recommendation* — real sign-in/IdP is now in-scope (previously an open item in the Platform API README + account-setup handoff open-question #1).
- Offline-grace open question (account-setup handoff #2) → RESOLVED: no separate grace; = license window.
- New workstream (to be created): **customer identity / account authentication** (Platform API account surfaces + desktop sign-in) under the Platform API epic 86ajy5v6k — this is a substantial addition.
- Desktop account-setup implementation now integrates a real sign-in path, not a "coming soon" affordance.

**Still open (sub-decisions).** The **IdP technology** (build on Django auth for customer accounts vs adopt a managed IdP — Auth0/Clerk/Cognito/etc.), session/token model, password-reset/MFA, and pricing tiers (OD-04) — route to software-architect + product before building the customer-identity workstream.

**Reversibility.** Reversible before the customer-identity workstream is built; the enrollment-key activation path already shipped remains valid as the secondary path regardless.

---

## DEC-004 — Licensing model: account-identity spine + activation-cached offline entitlement (hybrid)

- **Date:** 2026-08-09
- **Stage:** Platform API / licensing design (post-MVP monetisation track)
- **Decided by:** User (product owner)
- **Type:** Product / monetisation model (resolves a facet of OD-04 and the Platform API "Customer identity model" open decision)
- **Status:** DECIDED

**Decision.** SelahCue licensing uses an **account-identity spine with account-bound device *instances***, hardened for offline-first:

1. **Account is the identity spine.** A church/org holds a SelahCue account; the plan defines a **device/instance limit**. Cloud features (AI sermon notes, cloud transcription, quota, billing, entitlements) are authenticated and metered against the account — consistent with [DEC-…/Providers & Privacy] "users go through SelahCue, no user keys".
2. **Each install activates once (online) → the server registers a counted device instance and returns a signed, time-boxed entitlement policy cached on the device.** The app then runs **fully offline within an offline-grace window**, re-validating opportunistically when online. This preserves the offline-first guarantee (NFR-015, CON-2) and the never-blank-live-output invariant (NFR-024): a lapsed network or expired session must never block presentation at service time.
3. **The app license key is demoted to an *optional org enrollment/bootstrap token*** (offline/bulk/reseller enrollment), **not** the primary licensed unit. The canonical unit is the account-bound device instance; `AppLicenseKey.device_limit` is reinterpreted as the plan's **instance limit**.

**User rationale.** Chose the hybrid explicitly over pure key-only and pure sign-in-only. Account identity is needed for the cloud AI/quota/billing surfaces (already chosen for Providers & Privacy), but pure sign-in would break offline/air-gapped/low-connectivity church booths; the cached signed entitlement + offline grace reconciles the two.

**Supporting evidence.** Offline-first + never-blank guarantees (PRD NFR-015, CON-2, NFR-024); volunteer-first, cross-platform incl. Linux, Global-South positioning (PRD §competitive, OD-04); the Platform API scaffold already models `activation → device token → entitlement manifest → license:refresh` and flags "policy envelope cryptographic suite" + "offline grace" as open owner decisions (`implementation/api/README.md`).

**Affected items.**
- OD-04 (pricing/positioning) → licensing *model* facet now DECIDED (hybrid); tier/price points still open.
- Platform API "Customer identity model" open decision → resolved to account-spine + device-instance.
- Device-activation slice (`POST /v1/activations`) → built as **account-instance registration issuing a device token** (+ a basic entitlement now; the *signed* offline policy-envelope crypto + real account sign-in/IdP remain open owner decisions, built as follow-ups).
- `AppLicenseKey` reframed as an enrollment/bootstrap token; `device_limit` → instance limit.

**Still open (owner/next):** account sign-in / customer IdP; policy-envelope cryptographic suite + key rotation; offline-grace duration; plan tiers + price points (OD-04 pricing facet).

**Reversibility.** The activation mechanism (device token + cached entitlement) is model-agnostic; if the model changed, the enrollment path (key vs account session) and the instance-limit source would change, not the device-token/entitlement machinery.

---

## DEC-003 — Slides & Media engine: build the authored-deck + media library, defer live video/audio render

- **Date:** 2026-08-03
- **Stage:** Stage 8 (Presentation & Slides epic 86ajp07ce)
- **Decided by:** User (product owner), scoping the /backend-engineer build of the Design-2.0 "Presentation & Media" surface (Figma node 329:124)
- **Type:** Scope boundary (architecture)
- **Status:** DECIDED

**Decision.** The Slides/presentations engine is built as **two subsystems this pass** — the authored slide-deck engine (domain model where slides own layered elements + compose + Preview→Live playback + persistence) and the **media library** engine (a bounded registry of image/video/audio assets with import, missing-file and used/unused detection, and storage accounting) — with a **new forward-only SQLite `deck` + `media_asset` schema**. **Live video/audio playback on the audience output is explicitly deferred** to its own story + ADR: the media library *lists* video/audio assets now, but they cannot yet go live.

**User rationale.** Selected "Deck engine + media library" scope with "new deck/document repo" persistence when the engine was scoped; live video-on-output was surfaced as the largest, highest-risk slice and held back.

**Supporting evidence.** Video-on-wgpu is a heavy new subsystem (decode pipeline + frame-clock sync + preserving the NFR-024 never-blank guarantee with a *live* decoder that can stall), out of proportion to a slide-engine slice and interacting with ADR-0016 decode isolation. Per ADR-0002/0003 it renders in the native compositor, never the WebView. See **ADR-0020** for the full realisation + non-goals.

**Affected items.** New: `selahcue-present::deck` (`SlideDeck`/`AuthoredSlide`/`DeckSession`/`crossfade`/`media_usage`), `compose_authored_slide`; `selahcue-core::media` (`MediaLibrary`/`MediaAsset`/`MediaKind`); `selahcue-data` migrations v16 (`deck`) + v17 (`media_asset`) with `deck_repo`/`media_repo`. Deferred (own follow-ups): live video/audio render; the S8-4 in-webview editor + undo/redo; new LAN wire commands to drive decks; FR-029 auto-pagination.

**Reversibility.** Additive throughout (new modules + additive `CREATE TABLE` migrations); no wire or existing-schema change. Video render can be added later without reworking the model (assets already carry kind/duration/dimensions).

---

## DEC-002 — RBAC: `Clear` (wipe live output) tightened to Producer+ (revised)

- **Date:** 2026-07-23 (original) · **Revised:** 2026-07-24
- **Stage:** Stage 7 gate (batch 7d original; batch 7k revision)
- **Decided by:** User (product owner)
- **Type:** RBAC policy
- **Status:** REVISED — `Clear` is now Producer+ (superseding the 7d "keep as-is")

**Revision (2026-07-24, batch 7k).** When the LAN control was wired to the presenter (7k), `Clear` gained teeth: the batch-7k independent review confirmed a **HIGH** consequence — an **Assistant** (a role that "cannot push to the live output") could `Clear` the live audience output *and* lift an operator-set blackout over the wire. Presented at the 7k gate, the user chose to **tighten it** ("refine: tighten it").

**Decision (revised).** `Command::Clear` now requires a dedicated **`Permission::ClearLive`**, held only by **Operator** and **Producer**. Assistant retains `Navigate` (Next/Previous/SelectItem — which stage *Preview* and do not change Live) plus SearchScripture and Monitor, but **cannot wipe the live output**. `GoLive`, `Blackout`, `Timer` remain Producer+ as before.

**User rationale.** Original (7d): "keep as is; revisit later if there's a need." Revision (7k): "tighten it" — an emergency wipe of the congregation screen must not be available to the lowest control role, especially once it can also lift a blackout.

**Affected items.** `selahcue-lan::rbac` — added `Permission::ClearLive`; `required_permission(Clear)` now maps to it; granted to Operator + Producer. `test_rbac.rs` updated (Clear removed from the navigate set; Assistant/Viewer `Clear` denials asserted; `Clear` added to the Producer+ matrix). The `LiveController` is unchanged — RBAC is enforced by the server before the handler.

**Reversibility.** Trivially reversible by re-mapping `Clear` to `Navigate`.

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
