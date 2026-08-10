# SelahCue — Account Setup (Desktop · Design 2.0) Handoff

**Status:** design complete — first-run activation flow + in-Settings Account page + every meaningful state, high-fidelity.
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` · **Section:** `651:124` "SelahCue · Account Setup — Design 2.0 (activation + licensing + states)".
**Reference chrome (pre-existing, not mutated):** Settings — Providers & Privacy `338:124` (sidebar `338:137`).
**ClickUp:** [STORY — Account setup (Desktop, Design 2.0)](https://app.clickup.com/t/86ajy600r) under [EPIC — Accessibility & Design System](https://app.clickup.com/t/86ajp08bx); linked to [EPIC — Platform API / Licensing](https://app.clickup.com/t/86ajy5v6k) and the [device-activation slice](https://app.clickup.com/t/86ajy5v7h).
**Goal Contract:** `docs/delivery/goals/GOAL-design-account-setup.md`.
**Authoritative grounding:** **DEC-004** (`docs/decisions/DECISION-LOG.md`); PRD NFR-015 / CON-2 / NFR-024 (offline + never-blank), FR-137 (admin-gated), FR-176/FR-177 (privacy/DPA), FR-132 (cloud opt-in); Platform API device-activation slice (`implementation/api/selahcue_api/apps/devices` — `models.py`, `services.py`) + `GOAL-be-api-device-activation`; Design-2.0 tokens + Settings shell (`docs/design/SETTINGS-2.0-HANDOFF.md` §2).

Frame link pattern: `https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=<id-with-dash>` (e.g. `652-124`).

---

## 1. What this is (product frame)

The Account setup experience is how a church **activates a desktop install against its SelahCue account** and sees its **licensing/entitlement status**. Per **DEC-004** the licensing model is a hybrid: an **account-identity spine + account-bound device *instances* + activation-cached offline entitlement**. A church holds a SelahCue org account; the plan sets a **device/instance limit**; each install activates **once online**, is counted as an **instance**, and caches a signed, time-boxed entitlement so it runs **fully offline within a grace window**. The **enrollment key is an *optional* org bootstrap token**, not the primary unit — so "sign in to your account" and "enter an enrollment key" are **co-equal activation paths**.

**Hard invariant carried through every frame:** account/licensing state must **never** block or imply blocking of live presentation (NFR-015 offline, CON-2 offline-core, NFR-024 never-blank). Offline and every error frame explicitly reassure that the app keeps working; none reads as "app broken/blocked".

---

## 2. Method & placement

Two entry points, two chrome treatments:

- **First-run activation (A0–A7)** — a **focused full-screen** frame (top bar with wordmark + a persistent "Works offline" pill, deep-ink base, one centred card). A fresh install has no account yet, so activation is a distinct entry shown before the operator console when there is no cached entitlement. The "Works offline" pill in the bar is a standing honesty cue.
- **In-Settings Account page (A8–A10)** — clones the **Settings shell chrome from `338:124`** (top bar, left sidebar, deep-ink base) pixel-for-pixel, adds an **Account** item to the sidebar, and rebuilds the content column. This is where the account/device/entitlement relationship lives after activation; **Providers & Privacy links here**.

**Sidebar change (additive):** a new **Account** nav item is inserted at **position 2 (after General, before Providers & Privacy)** with the standard selected-row treatment (brand@14% fill, brand@40% stroke, brand icon, Bold white label). No existing frame is mutated.

**Section placement:** the 11 frames live in a tight **4×3 grid** inside section `651:124` (7700 × 3560), positioned directly **below the Settings-2.0 section** (`618:124`) at canvas ≈ (60220, 18400) so it sits with the rest of the Design-2.0 work. Grid order: row 1 A0–A3, row 2 A4–A7, row 3 A8–A10 (140px horizontal / 160px vertical gaps; no overlaps).

---

## 3. Design system reused (no new patterns)

Tokens (Design 2.0 `--sc-*`, from SETTINGS-2.0-HANDOFF §2 / DESIGN-TOKENS):

| Role | Value | Role | Value |
|---|---|---|---|
| page base | `#0b0d12` | text | `#f4f6fb` |
| surface (cards/sidebar) | `#14161d` | text-secondary | `#a7aebe` |
| elevated (dialog) | `#1c1f28` | text-muted (labels/meta only) | `#6b7383` |
| inset (fields, chips, meter track was elevated) | `#0f1116` | brand / hover | `#6e5cf0` / `#7e6eff` |
| border / strong | `#262a34` / `#363b47` | scripture gold (unused here) | `#f2b84b` |

Status (one meaning per family, fixed): live/danger red `#ff4d4d` (soft `#2a1416`), safe/positive green `#35c08a` (soft `#10231c`), warn amber `#f5a524` (soft `#2a2415`), info blue `#38bdf8` (soft `#10222b`).

Type: **Inter** — title 20–24 Bold, section label 12 Bold uppercase tracked, card title 15 Semi Bold, body/help 12–14 Regular, meta 11–12.

Primitives reused (all from COMPONENT-SPECS / the reference page): card (13–16px radius), input 46-tall + focus/error stroke, primary/ghost/danger button, badge pill (999), info/green/amber/red/neutral banner, meter (track + fill), selected/unselected sidebar row, list/link row (▸), type-to-confirm dialog on a dimmed scrim, status-icon chip. **No new pattern language was introduced.**

---

## 4. Per-frame specs

> Every value shown (device name, plan, dates, instance count, key/token) is **sample data**; nothing is a live secret. The **device token** (the show-once credential) is **never rendered** — it leaves the system exactly once, at activation, and does not appear on any frame. Enrollment-key fields show a **masked placeholder** by default; the one exception is the inline error state A4, which deliberately **echoes the user's own typed key** (a rejected, fictitious value) so they can spot the typo — this is standard error-echo UX, not a secret, and is the only place a full-looking key string appears.

### 4.1 A0 — First-run activation · chooser — `652:124` (default first-run entry)
Focused card: brand mark, title **"Activate SelahCue"**, subtitle, then the two **co-equal** paths — primary button **"Sign in to your SelahCue account"** (recommended hint below) and ghost button **"Enter an organisation enrollment key"** carrying an **OPTIONAL** badge (DEC-004 demotion of the key). Info banner **"SelahCue works offline — you can skip this and activate anytime from Settings › Account. Live presentation is never blocked by activation."** Text button **"Skip — set up later"**. → A1 / A2 / (skip → operator console).

### 4.2 A1 — Sign in — `654:124`
Back link · **"Sign in to SelahCue"** · Email field (placeholder `name@yourchurch.org`) · Password field with **Forgot?** link · primary **Continue** · **"Use an enrollment key instead"** (cross-link to A2) · info banner **"You can activate later — SelahCue works offline. Signing in is not required to run live presentation."** Maps to the account-sign-in path (**Assumed / open**: customer IdP is a tracked owner decision — see §9).

### 4.3 A2 — Enrollment key — `654:157`
Back link · **"Enter your enrollment key"** · **Organisation enrollment key** field (mono placeholder `SC-XXXX-XXXX-XXXX-XXXX-XXXX`, shown focused) · **Device name** field (sample `Sanctuary Booth PC` → `display_name`) · meta **"This device: Windows 11 · SelahCue 1.0.0 — detected automatically"** (→ `platform`, `app_version`, `device_fingerprint`) · primary **Activate this device** · **"Sign in with your account instead"** · info banner **"A connection is needed once — after activation, SelahCue caches your entitlement and runs fully offline."** → A3.
Backend: `POST /v1/activations` with `presented_key` + `device_fingerprint` + `platform` + `app_version` + `display_name` + idempotency key.

### 4.4 A3 — Activating (loading) — `655:124`
Determinate-looking spinner (ring + brand arc) + progress bar · **"Activating this device…"** · subtitle "Contacting SelahCue and registering this install on your plan." · **green** banner **"You can keep working — SelahCue is ready to present. Activation runs in the background and never blocks live output."** Announce via `aria-busy` / an `aria-live=polite` status region (see §7).

### 4.5 A4 — Error: invalid / unknown key (inline) — `655:144`
A2 with the key field in the **error** state (red 1.5px stroke) and an **inline** error under it: **"✕ We don't recognise that key. Check for typos, or ask your administrator for a new one."** Primary relabelled **Try again**; the account cross-link and an info banner ("SelahCue works offline — an invalid key never blocks live presentation…") remain. Maps to activation `NOT_FOUND` (unknown key **or** hash mismatch — the copy never reveals which, matching the backend's deliberate NOT_FOUND-for-both).

### 4.6 A5 — Error: instance limit reached — `656:124`
Amber status-icon · **"All device slots are in use"** · body "Your plan allows 5 devices, and all 5 are active…" · meta row **"Grace Chapel · Pro plan · 5 of 5 devices used"** · primary **Manage devices** + ghost **Try again** · muted note ("Ask your administrator to remove one or upgrade the plan") · **info** banner **"Nothing running is affected — this only blocks activating a new device. SelahCue keeps presenting offline on devices already activated."** Maps to activation `POLICY_DENIED` (active devices ≥ `AppLicenseKey.device_limit`).

### 4.7 A6 — Error: license expired / not yet active — `656:151`
Amber status-icon · **"Your SelahCue plan has expired"** · body "This account's plan ended on 31 Jul 2026…" · meta row **"Grace Chapel · Pro plan · expired 31 Jul 2026"** · primary **Renew plan** + ghost **Contact administrator** · muted note covering the **not-yet-started** variant ("If your plan begins in the future, it activates automatically on its start date") · **info** banner **"Live presentation keeps working — already-activated devices keep presenting offline within their grace window. An expired plan never blanks or blocks live output."** Maps to activation `POLICY_DENIED` (validity window: `starts_at <= now < expires_at` fails) — both the expired and not-yet-started sub-cases.

### 4.8 A7 — Offline: can't reach SelahCue — `657:124`
Neutral status-icon · **"Can't reach SelahCue right now"** · body "We couldn't connect to activate this device… there's no rush." · prominent **green** banner **"You're ready to present — SelahCue works fully offline. Slides, local scripture, media, blackout/clear and timers all work now — activation isn't required to run your service."** · primary **Try again** + ghost **Continue offline** · muted "You can activate later from Settings › Account whenever you're back online." This is the flagship never-blank frame (client-side network/unreachable case).

### 4.9 A8 — Activated / this device (Settings) — `659:124` (in-Settings default)
Settings shell, **Account** nav active. Header **"Account"** + subtitle stating live presentation always works offline. Green status banner **"Activated · Cloud connected"**. Sections:
- **THIS DEVICE** — device chip + **"Sanctuary Booth PC"** + "Windows 11 · SelahCue 1.0.0 · activated 2 Aug 2026" · **ACTIVE** badge (green) · **Deactivate this device** (danger-ghost). (→ `Device.display_name`, `platform`, `app_version`, `DeviceStatus.ACTIVE`.)
- **PLAN & LICENSE** — org **"Grace Chapel"** / **"Pro plan"** · **Device instances 3 of 5 used** with a meter (→ active `Device` count vs `device_limit`) · **License valid through 31 Jul 2027** (→ `expires_at`) · **WORKS OFFLINE 27 DAYS** green badge (offline-grace status) · **"Last checked 6 Aug 2026 · re-validates automatically when online."**
- **CLOUD & CONNECTED FEATURES** — **Cloud connected** (green dot) + "Cloud AI notes, cloud transcription and plan sync are available." · link rows **Manage devices** (→ SelahCue account portal) and **Providers & Privacy** (→ `338:124`).
- **Footer** info banner **"SelahCue always works offline — if this device loses its connection or the plan lapses, live presentation keeps working within your offline-grace window. Account status never blanks or blocks live output."**

### 4.10 A9 — Deactivate / sign out (type-to-confirm) — `665:124`
A8 with a dimmed scrim + centred **type-to-confirm** dialog: **"Deactivate this device?"** · body (frees a slot, signs out, cloud features stop) · **green** reassurance banner ("Your slides, local scripture, media and timers keep working offline — live presentation is not affected") · field **"Type `deactivate` to confirm"** (focused) · **Cancel** (ghost) + **Deactivate device** (danger, enabled only once the word matches). Frees a `Device` instance on the plan.

### 4.11 A10 — Administrator-managed (non-admin, read-only) — `666:124`
A8 with the **neutral** banner **"Some account settings are managed by your administrator — you can view this device's status and plan, but only an Administrator can activate, deactivate or manage devices."** The **Deactivate this device** button and the **Manage devices** link are **removed from the layout (and tab order)** — not greyed-teased. Status/plan/validity remain visible read-only. Consistent with FR-137 (Administrator-gated account changes).

---

## 5. State matrix (state → frame)

| Context | State | Frame |
|---|---|---|
| First-run | default / chooser | A0 `652:124` |
| First-run | sign-in (account path) | A1 `654:124` |
| First-run | enrollment-key (bootstrap path) | A2 `654:157` |
| First-run | loading (activating) | A3 `655:124` |
| First-run | error — invalid/unknown key (inline, `NOT_FOUND`) | A4 `655:144` |
| First-run | error — instance limit (`POLICY_DENIED`) | A5 `656:124` |
| First-run | error — expired / not-yet-active (`POLICY_DENIED`) | A6 `656:151` |
| First-run | offline / unreachable | A7 `657:124` |
| In-Settings | activated / this device (happy) | A8 `659:124` |
| In-Settings | destructive-confirm (deactivate) | A9 `665:124` |
| In-Settings | permission (admin-managed, read-only) | A10 `666:124` |

Recurrence note: the offline (A7) and expired (A6) conditions can also surface **inside** the Settings Account page as a banner delta on A8 (same copy, same never-blank guarantee) once the plan lapses or a re-validation fails; the dedicated frames above are the canonical rendering of each state.

---

## 6. Traceability (control → source)

| Frame / control | DEC / FR / NFR / contract |
|---|---|
| Two co-equal paths; enrollment key = OPTIONAL bootstrap token (A0/A1/A2) | **DEC-004** (account-spine + optional enrollment token) |
| Activation request fields — key, device fingerprint, platform, app_version, display_name, idempotency (A2) | Platform API `apps/devices/services.py::activate_device`; `GOAL-be-api-device-activation` |
| Instance "N of M" + meter; device_limit as plan instance limit (A8) | **DEC-004**; `AppLicenseKey.device_limit`; `Device` active-count check |
| License validity "valid through …" (A8/A6) | `AppLicenseKey.expires_at` / validity window `starts_at <= now < expires_at` |
| Offline-grace "works offline for N days" (A8) + cached entitlement (A2/A3) | **DEC-004** (activation-cached, time-boxed entitlement); `DeviceToken.expires_at`; offline-grace duration **open** |
| Masked-only token/key; never render a secret (all frames) | `DeviceToken` (masked triple only); show-once contract |
| Invalid key → inline NOT_FOUND, no exists-vs-mismatch leak (A4) | `_resolve_license_key` (NOT_FOUND for both) |
| Instance limit reached → POLICY_DENIED + manage-devices path (A5) | `activate_device` instance-limit `POLICY_DENIED` |
| Expired / not-yet-active → POLICY_DENIED + renew/contact (A6) | `_assert_key_activatable` validity window `POLICY_DENIED` |
| Offline "keeps working"; every error/offline never-blank copy (A5/A6/A7/A8 footer) | **NFR-015**, **CON-2**, **NFR-024** |
| Cloud-connected status + Providers & Privacy link (A8) | FR-132 (cloud opt-in); Providers & Privacy `338:124` |
| Admin-only activate/deactivate/manage; neutral managed line (A10) | **FR-137** (Administrator-gated); SETTINGS-2.0 §3 neutral copy |
| "Works offline" bar pill; skip/continue-offline affordances | NFR-015 / CON-2 |
| Sign-in path (email/password) | **Assumed / open** — customer IdP is a tracked owner decision (README, DEC-004 "still open") |
| Deactivate frees a slot; type-to-confirm | DEC-004 (instance model); COMPONENT-SPECS type-to-confirm |
| Privacy/DPA (referenced via Providers & Privacy, not duplicated here) | FR-176 / FR-177 |

No control lacks a source; the only **Assumed** items are the sign-in/IdP path and the offline-grace *duration* value (both flagged §9).

---

## 7. Accessibility (testable)

- **Contrast:** body/label/status text uses tokens audited AA on `base`/`surface`/`inset`/`elevated`; `text-muted #6b7383` is used **only** for tertiary meta (e.g. "Last checked…", recommended hint), never for essential body copy (essential copy uses `text-secondary #a7aebe` or `text`). White on the brand primary button and white on the red danger button both clear AA.
- **Colour never the only cue:** every status pairs colour with a text label/word — ACTIVE, "Activated · Cloud connected", "expired 31 Jul 2026", "All device slots are in use", "Can't reach SelahCue", "managed by your administrator", inline "✕" + error text. The instance meter is backed by the literal "3 of 5 used".
- **Keyboard / focus order:** first-run cards flow top→bottom (back → title → fields → primary → alt-path link → banner → skip); the enrollment-key field renders focused (brand stroke) to show the focus treatment; the type-to-confirm dialog (A9) is a **modal** — focus is trapped, initial focus on the confirm field, `Esc` = Cancel, and the danger button is enabled only when the typed word matches. Targets are ≥44px effective height (inputs 46, buttons ~46, sidebar rows 46, link rows ~46).
- **Screen-reader semantics:** A3 loading is an `aria-busy`/`aria-live=polite` status ("Activating this device…"); inline errors (A4) use `aria-describedby` on the field + an assertive announcement; the dialog (A9) is `role=dialog aria-modal=true` labelled by its title; the admin-gated frame (A10) **removes** forbidden controls from the DOM/tab order rather than greying (no phantom focus stops).
- **Reduced motion:** the A3 spinner/progress must respect reduced-motion (swap the animated arc for a static "Activating…" state); no other frame relies on motion. Seizure caps are inherited app-wide.
- **Never-blank as an a11y guarantee:** because live output must never be blocked, no account modal or activation screen may occlude the app's global emergency footer (BLACKOUT / CLEAR-ALL) or intercept its global chords — the first-run activation screen is shown pre-console; once in the console/Settings, account UI never captures the emergency chords.

---

## 8. Copy deck (canonical strings)

- **Bar pill:** "Works offline"
- **A0:** "Activate SelahCue" / "Connect this computer to your church's SelahCue account to unlock cloud features and manage your plan across devices." / "Sign in to your SelahCue account" / "Recommended — uses your church account for cloud AI, plan and billing." / "Enter an organisation enrollment key" + "OPTIONAL" / offline banner (§4.1) / "Skip — set up later"
- **A2 offline banner:** "A connection is needed once — after activation, SelahCue caches your entitlement and runs fully offline. Live presentation is never blocked."
- **A4 inline error:** "We don't recognise that key. Check for typos, or ask your administrator for a new one."
- **A5:** "All device slots are in use" / "Your plan allows 5 devices, and all 5 are active. Remove a device you no longer use, then activate this one." / "Nothing running is affected — this only blocks activating a new device. SelahCue keeps presenting offline on devices already activated."
- **A6:** "Your SelahCue plan has expired" / "This account's plan ended on 31 Jul 2026. Renew it to activate new devices and keep cloud features." / not-yet-started: "If your plan begins in the future, it activates automatically on its start date." / "Live presentation keeps working — already-activated devices keep presenting offline within their grace window."
- **A7:** "Can't reach SelahCue right now" / "You're ready to present — SelahCue works fully offline…" / "Continue offline"
- **A8:** "Activated · Cloud connected" / "Device instances — 3 of 5 used" / "License valid through — 31 Jul 2027" / "WORKS OFFLINE 27 DAYS" / "Last checked 6 Aug 2026 · re-validates automatically when online" / footer never-blank line (§4.9)
- **A9:** "Deactivate this device?" / "Type deactivate to confirm" / "Cancel" / "Deactivate device"
- **A10 neutral:** "Some account settings are managed by your administrator — you can view this device's status and plan, but only an Administrator can activate, deactivate or manage devices."

---

## 9. Open questions / decisions for product

1. **Account sign-in / customer IdP (A1).** The shipped activation path is enrollment-key-authed; real account sign-in (email/password/SSO) is a tracked **open owner decision** (README, DEC-004 "still open"). A1 is designed and ready but should ship only once the IdP is chosen; until then the chooser can lead with the enrollment-key path. Owner: product.
2. **Offline-grace duration (A8 "works offline for N days").** Rendered as a data-driven token; the actual grace-window length + the signed policy-envelope crypto are open owner decisions. Owner: product/security.
3. **Sidebar placement of Account.** Placed at position 2 (after General). Confirm this vs grouping it with About & Licensing. Owner: design/product.
4. **"Manage devices" destination.** Designed as a link out to the SelahCue account portal (a full device-management console is a separate story, not in this scope). Confirm whether an in-app device list is wanted for R-next. Owner: product.
5. **Plan tiers / naming ("Pro plan").** Sample only; pricing/tier facet of OD-04 is still open.

---

## 10. Independent design-QA

An independent reviewer (separate agent, read-only) inspected all 11 rendered frames via screenshots against the state matrix, DEC-004, the Platform API activation contract (`apps/devices`), and the never-blank invariant.

**Verdict: PASS — no Critical, no Major findings.** All 8 criteria passed: never-blank reassurance present on A4/A5/A6/A7/A9 + the A8 footer; co-equal paths with the OPTIONAL enrollment key (DEC-004); no device token rendered anywhere; faithful error mapping (A4 NOT_FOUND with no exists-vs-mismatch leak, A5 instance-limit POLICY_DENIED with a manage-devices path, A6 expired/not-yet-active POLICY_DENIED); A8 complete and A10 removing (not greying) admin-only actions; no clipped/collapsed/overlapping elements; colour never the sole cue; node IDs match the handoff.

**Minor findings + disposition:**
1. Handoff §4 "only masked keys shown" contradicted A4's typed-key echo → **fixed** (wording reconciled above to carve out the user-typed error-echo case).
2. A7 offline icon rendered as an amber emoji bolt, fighting the calm copy → **fixed** (swapped to a neutral `◇` dingbat in `text-secondary`).
3. A0 leads with the (not-yet-shipped) sign-in path while the enrollment-key path is the shipped one → **accepted / already flagged** (§9.1): the chooser can lead with the enrollment-key path until the IdP decision lands; the OPTIONAL labelling is correct to DEC-004.
4. §10 was an unfilled placeholder → **fixed** (this section).

No blockers remain.
