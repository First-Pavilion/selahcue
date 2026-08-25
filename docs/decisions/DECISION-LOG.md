# SelahCue — Cross-Functional Decision Log

Durable record of material product/scope/architecture decisions, with traceability. Newest first.

---

## DEC-012 — EXPIRED error code: split by surface — explicit on licence/entitlement, collapsed on auth tokens (D6)

- **Date:** 2026-08-25
- **Stage:** Platform licensing decision round (Platform PRD v1.2 amendment; decision ticket D6 [86ak120fz](https://app.clickup.com/t/86ak120fz))
- **Decided by:** User (product owner)
- **Type:** Product + security posture (API error-surface design)
- **Status:** DECIDED

**Decision.** The "distinct EXPIRED error code?" question is split by surface rather than answered once:

1. **Licence/entitlement state → expose `EXPIRED` explicitly** (Platform PRD FR-523): a distinct coded error on the authenticated licence/entitlement surfaces (refresh, manifest issuance, activation).
2. **Auth tokens (`verify_email`, `confirm_password_reset`) → keep the collapse** (FR-529): unknown / consumed / expired / wrong-purpose token failures stay indistinguishable.
3. **Two fixes that leak nothing**, decided alongside: **(a)** `confirm_password_reset` must validate the token **before** the new password — a live defect verified in the tree (`apps/accounts/services.py:968` calls `_validate_password()` before the token lookup at 973–987, both raising the same `_validation_error()`, so a valid link plus a weak password is indistinguishable from a dead link and the user loops forever); reorder plus a regression test pinning the order (FR-551). **(b)** The `/verify` and `/reset` landing pages always offer "request a new link", whatever the error, since the API deliberately cannot say why a token failed (FR-552; `resendVerificationEmail` already ships, 86ak120ac).

**User rationale.** No enumeration oracle exists on the licence surfaces — a church told "your licence expired" learns nothing about anyone else's account, and collapsing it into VALIDATION_FAILED only generates support load. On auth tokens the anti-enumeration stance of the independent security review stands. The two fixes remove the user-visible dead end (a verification email in spam past its 24h TTL; a reset link clicked after its 1h TTL) without telling an attacker anything: reordering converts "your link is broken" into "your password is too short", and the unconditional resend affordance is the entire remedy when a link expired.

**Affected items.** Platform PRD v1.2: FR-523 and FR-529 finalised, FR-551/552 added, CON-P6's sanctioned exception recorded. Delivery: a defect ticket for (a) — a user-visible loop, not a nice-to-have.

**Reversibility.** Additive error code on authenticated surfaces only; the public-surface collapse is untouched, so the anti-enumeration posture cannot regress by this decision.

---

## DEC-011 — Entitlement signing keys: no KMS at MVP (accepted risk, named revisit trigger); client trusts a key SET + `key_id` from the first build; both activation paths retained (D5)

- **Date:** 2026-08-25
- **Stage:** Platform licensing decision round (Platform PRD v1.2 amendment; decision ticket D5 [86ak10gb9](https://app.clickup.com/t/86ak10gb9))
- **Decided by:** User (product owner)
- **Type:** Security architecture (entitlement signing custody + rotation), deliberately split by cost and reversibility
- **Status:** DECIDED

**Decision.** Three parts:

1. **Custody: NO KMS at MVP.** The Ed25519 entitlement signing key stays in the hosting platform's encrypted secret store, with a single documented holder. **Accepted risk, recorded explicitly:** whoever obtains the private key can mint unlimited entitlements at any tier, valid for any duration, entirely offline — no server call to rate-limit, no login to detect, no audit row, no way to know it happened; rotation is the only remedy. **Revisit trigger: first revenue, or the first N paying orgs — whichever comes first.** A deferral with a named end, not a permanent position. It enters the launch security review (86ak11w10) as an accepted-risk item rather than being discovered there as a finding.
2. **Rotation: the client trusts a KEY SET from the first shipped build — not deferrable.** The public key is compiled into every installed desktop copy; a single-key client means any future key change rejects every new entitlement everywhere at once, unfixable by shipping an update because the machines that matter are deliberately offline. Required in the first build that verifies an entitlement: the client holds a **set** of trusted public keys; the manifest carries a **`key_id`**; the rotation procedure is documented (add new key to the client set → ship → wait for adoption → start signing with the new key → retire the old after the overlap window). Cost: an array instead of a constant, plus one field — and it is what makes part 1 a safe deferral.
3. **Activation: account login is the primary path; the enrolment key is retained as delegation. No code change** — this is already DEC-004's model and both paths ship. Removing the key path was considered and rejected: it deletes tested code, and it costs the volunteer-installer case (a volunteer setting up sound-booth machines would otherwise need the admin's account password on each one).

**Scope bar (recorded with the decision).** Signing raises the attack cost from "edit a JSON file" to "patch and re-sign a binary". It does not defeat an attacker who controls the machine, and no custody scheme would — build to that bar and no further.

**Affected items.** Platform PRD v1.2: FR-518 (trust-set shape + `key_id`) and FR-538 (custody, accepted risk, revisit trigger, rotation procedure, runbook) finalised; RISK-502 mitigation updated. Launch security review 86ak11w10 gains the accepted-risk item.

**Reversibility.** Part 2 is the reversibility mechanism itself: once the key set + `key_id` ship, custody can be upgraded (or a leaked key rotated out) at any time without touching an installed copy. Part 1 is explicitly temporary with a named trigger.

---

## DEC-010 — SUSPENDED is a soft, reversible licence state; REVOKED remains the terminal, token-killing act (D3)

- **Date:** 2026-08-25
- **Stage:** Platform licensing decision round (Platform PRD v1.2 amendment; decision ticket D3 [86ak10g8q](https://app.clickup.com/t/86ak10g8q))
- **Decided by:** User (product owner)
- **Type:** Product policy (licence lifecycle severity)
- **Status:** DECIDED

**Decision.** `SUSPENDED` is softer than `REVOKED`, and reversible. Suspended: running devices keep working (existing device tokens stay valid), new activations are refused, cloud/AI features stop, and reinstatement returns the licence to its **prior status**. Revoked: tokens killed by the hourly cascade, terminal. Today the two are operationally identical — both sit outside `ACTIVATABLE_KEY_STATUSES` (`apps/devices/services.py:40`), so the cascade (`apps/devices/tasks.py`) kills device tokens for both, making SUSPENDED a status with no distinct meaning.

**User rationale.** A commercial problem degrades commercial surfaces, not the show. A suspension is a lever for a billing situation that is expected to resolve; killing a church's presentation tokens over a failed card is disproportionate and hits during a service. Revocation is the deliberate, terminal act and keeps its teeth.

**Implementation notes (recorded with the decision).**
- `SUSPENDED → prior status` requires the **prior status to be recorded at suspension time** — a schema implication, not just a service one — or reinstatement cannot know where to return.
- The revocation cascade must be **scoped so SUSPENDED is not a token-killing state** — the actual code change, landing with cascade correctness (86ak1099u); reachability of SUSPENDED is the state-machine ticket's job (86ak5mn00).
- A suspended licence's already-cached offline entitlement keeps working until its own expiry, consistent with the PRD's RISK-501 — intended behaviour, not a hole.

**Affected items.** Platform PRD v1.2: FR-504, FR-510, FR-522 finalised (plus FLOW-506, the SUSPENDED state-machine row, and the FR-520 enforcement ladder); FR-535's deferral narrows to D2 only.

**Reversibility.** The severity split is policy over an existing state machine; tightening SUSPENDED later (e.g. a tiered abuse-suspension) is additive and does not invalidate the recorded-prior-status schema.

---

## DEC-009 — Renewal grace: 7-day grace period, then fallback to the Free tier at the next session start (D4 — AMENDS DEC-005)

- **Date:** 2026-08-25
- **Stage:** Platform licensing decision round (Platform PRD v1.2 amendment; decision ticket D4 [86ak10ga1](https://app.clickup.com/t/86ak10ga1))
- **Decided by:** User (product owner)
- **Type:** Product policy (renewal/lapse behaviour) — **amendment to DEC-005**, not a free-standing decision
- **Status:** DECIDED
- **Amends:** DEC-005 point 2 (offline entitlement = full licence window, **no separate grace**). That rule is reopened and amended; DEC-005 point 1 and everything else stand.

**Decision.** A lapsed subscription gets a **7-day grace period, after which it falls back to the FREE TIER** — not a shutdown. A lapsed licence never stops the app: for 7 days after `expires_at` the entitlement keeps the full tier grants with renewal notices; after day 7 it degrades to Free (watermark, 1 device, 2 outputs, no NDI, 30 min STT).

**Two rules are the substance of the decision, both normative:**

1. **The Free-tier fallback takes effect at the NEXT SESSION START; a session already running finishes on the entitlement it began with** (PRD FR-549). Falling to Free is a downgrade that changes four things a congregation can see — the watermark appears, NDI feeds stop, outputs drop to 2, the device allowance drops to 1 — and if day 7 elapses at 10:40 on a Sunday, all four would land mid-service. FR-548 already forbade exactly this for the watermark ("never applied, removed or altered mid-session as an enforcement reaction"); the identical rule now extends to the **whole** downgrade. Grace expiry is a state change the operator console reflects immediately and the output path honours only at a session boundary. Without this rule, a 7-day grace merely delays a mid-service degradation by a week.
2. **A downgrade must not deactivate or revoke surplus devices** (PRD FR-550). When a 3-seat Pro org drops to Free's 1 device, all device records and tokens stay intact; the limit is enforced at **session start** — the first device to start a session gets it, the others are told why and offered the upgrade path. Re-subscribing restores the org exactly as it was, with no re-activation and no burnt instance slots. The rejected alternative — deactivating surplus devices on downgrade — destroys state on a billing event and forces every device through re-activation on renewal.

**Affected items.** Platform PRD v1.2: FR-521 finalised; FLOW-505 (the hard case) resolved; FR-549/550 added to carry the two rules; FR-516, the EXPIRED state-machine row, AS-P5, §18 and §24 updated. DEC-005's status annotated with this amendment.

**Reversibility.** The grace length (7 days) is policy data; the two rules are invariants of the never-blank posture (NFR-024/NG-P2) and should survive any future change to the grace length or fallback tier.

---

## DEC-008 — D1 partial closure: tier structure and entitlement limits (Free/Pro/Platinum), seat unit, STT quota period and scope; pricing and affiliate terms stay open

- **Date:** 2026-08-25
- **Stage:** Platform licensing decision round (Platform PRD v1.1 amendment, same day as the PRD's first issue; decision ticket D1 [86ak10gph](https://app.clickup.com/t/86ak10gph))
- **Decided by:** User (product owner)
- **Type:** Product / commercial model — **partial closure of D1**; the remainder stays open
- **Status:** PARTIALLY DECIDED

**Decision.** The plan/tier structure and entitlement limits:

| | Free | Pro | Platinum |
|---|---|---|---|
| Seats | 1 device | 3 seats, each with its own licence | 7 seats, each with its own licence |
| Screens/outputs | 2 | 5 | 10 |
| NDI outputs | none | 5 | 10 |
| STT | 30 minutes | 5 hours | 10 hours |
| Watermark | on all output | none | none |

Owner, verbatim: "the names can change in the nearest future, the hrs for STT can also change as this is dependent on the AI subscription we start using" — hence the PRD makes the catalogue data-driven (FR-544) and keeps tier names out of the manifest's semantics (FR-545). **Same-day follow-up decisions:** a **seat** is a device instance/activation under the org's **single** licence key — "each with its own license" means its own activation/device token, not its own `AppLicenseKey` (AS-P8; DEC-004 unchanged, matches the shipped code, no migration); the **STT quota period** is per calendar month, resetting on the billing anniversary (AS-P6); the **STT quota scope** is pooled per org across all seats (AS-P7).

**Affected items.** Platform PRD v1.1 (2026-08-25 amendment): FR-515/516/533/546 released; EPIC-PL-I (FR-544–548: data-driven catalogue, value-carrying manifest, org-pooled monthly STT metering, exhaustion degrade, Free watermark) added; OQ-P1 reframed as a defect finding (sum-of-key-limits capacity contradicts the one-key-per-org seat model).

**Still open in D1.** Pricing/price points; affiliate terms (the portal stays NOT-V1, 86ak11w7g); AS-P9 (what a screen/output counts); final STT hour values (tied to the AI-subscription choice); tier naming. These continue to gate FR-506, FR-509 (automation facet), FR-534, catalogue pricing content, and METRIC-505's baseline.

**Reversibility.** The volatile values (names, STT hours) are data by design (FR-544/545), so revising them is a data change, not a release; the seat-unit and quota-scope decisions match the shipped code and require no migration to hold.

---

## DEC-007 — Customer identity: traditional email/password auth (SelahCue-owned), superseding self-hosted Logto/OIDC

- **Date:** 2026-08-11
- **Stage:** Customer-identity workstream (Platform API account surface + desktop sign-in) — revises the DEC-006 technology direction
- **Decided by:** User (product owner)
- **Type:** Architecture (identity)
- **Status:** DECIDED
- **Supersedes:** DEC-006 (self-hosted Logto/OIDC). ADR-0022 (customer-identity via OIDC/Logto) → **Superseded**.

**Decision.** Customer sign-in / identity is built as **traditional email + password authentication owned by SelahCue**, on the existing Django 5.2 + Strawberry Platform API — **not** a self-hosted IdP and **not** OIDC. Concretely: a new `CustomerUser` login principal (email + Django-hashed password + email-verified state) FK'd to the existing tenant `CustomerOrg`; an **opaque, server-side, hashed session token** modelled on the shipped `DeviceToken` (no JWT/JWKS); and email/password mutations on the account GraphQL surface. **Email verification is IN SCOPE now; 2FA is explicitly DEFERRED** (forward-compatible seam left, no second factor built). The org **enrollment key remains the secondary/OPTIONAL activation path** and account sign-in becomes the **primary** activation path (DEC-004/DEC-005 unchanged).

**User rationale.** "Too much hassle for Logto — let's just use the authentication mode you recommended; we would handle email verification, 2FA later." Self-hosting/operating an IdP (container + its own Postgres + backups + upgrades + data residency) was judged not worth the operational cost for the current stage; building on Django's already-present password hashing and the repo's existing hashed-credential conventions is simpler to ship and operate while preserving the privacy-first, offline-first posture.

**Implications.**
- **Platform API** gains a greenfield identity layer reusing existing seams: `make_password`/`check_password` for passwords (as `AppLicenseKey.secret_hash` / `DeviceToken.token_hash` already do), HMAC-SHA256(SECRET_KEY) fingerprints for deterministic lookup, the `transaction.atomic` + `UniqueConstraint` + IntegrityError-savepoint idempotency pattern, `SafeAPIError`/`ErrorCode` with **no user-enumeration oracle**, and `record_audit_event` on every mutation. Login mints `ActorContext(kind=ActorKind.CUSTOMER, actor_id=<CustomerUser id>, org_id=<CustomerOrg id>)`, making the already-present `require_customer_org()` choke point live and **retiring `SELAHCUE_TRUST_ACTOR_HEADERS` for customers in prod**.
- **Session model** = opaque hashed token (device-token pattern) delivered as an HttpOnly/Secure/SameSite=Strict cookie (satisfying the already-declared `customer_session_with_csrf` route contract) and/or a keychain-stored `account_token` on desktop; instantly revocable (logout, password change, seat removal). Password change revokes all sessions.
- **Account-based device activation** (DEC-005) adds a session-authenticated path that resolves the caller's org → its active `AppLicenseKey` → the **unchanged** `activate_device` instance-limit + show-once `DeviceToken` logic, running **alongside** the untouched enrollment-key `POST /v1/activations`.
- **Devops** DROPS the entire Logto/OIDC operational surface: no IdP container/Postgres/backups/upgrades/KMS, no JWKS/introspection, no PKCE native client, no RP-initiated logout. All `SELAHCUE_OIDC_*` / `LOGTO_*` env keys (marked PLANNED, never WIRED) are removed from `deployments.md`; new keys are `SESSION_TTL`, credential-token TTLs, and an `EMAIL_*` delivery backend (injectable seam; no SMTP creds yet).
- **Never-blank / offline-first UNCHANGED:** offline entitlement = full license window (DEC-005); account session expiry/logout never revokes the device token or blanks live output (NFR-024).

**Still open (routed to product).** Exact `SESSION_TTL` value; self-serve web signup vs invite-only org provisioning (and where the first Admin is created); email-verify/reset token TTLs; email delivery provider; whether `seat_limit` is enforced per-user; multi-org-per-person (v1 = one email → one org via FK).

**Product answers (2026-08-11).** (1) **Self-serve signup** — `registerCustomerUser` creates a **new `CustomerOrg`** (status/plan TRIAL, `created_by_actor_id='self_signup'`) and its **first Admin** in one atomic op; the desktop A0/A1 design (which assumed the org exists) gains a companion sign-*up* path (FE follow-up). (2) **`SESSION_TTL` = 30 days** (refresh rotates; never shortens the offline device-entitlement window). Defaulted (not blocking, revisable): email-verify token TTL **24h**, password-reset token TTL **1h**, email delivery = injectable no-op/console seam (no SMTP creds yet), `seat_limit` enforcement **dormant**, email uniqueness **global** (one email → one org).

**Reversibility.** SelahCue owns the auth crypto and UI now (the trade-off the owner accepted). The opaque-token session and `CustomerUser` schema are additive/forward-only; a future move to an IdP or to 2FA is a new workstream and does not invalidate the shipped enrollment-key or device-activation paths.

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
- **Status:** DECIDED — **point 2 amended by DEC-009 (2026-08-25):** a 7-day renewal grace now follows the licence window, after which the subscription falls back to the Free tier at the next session start

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
