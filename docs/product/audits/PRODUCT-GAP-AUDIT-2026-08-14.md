# SelahCue — Product Gap Audit (what is left to build)

Date: 2026-08-14 · Role: /product-manager · Type: current-state product audit (PM workflow §1 + §6)
Sources of truth: ClickUp list **SelahCue — Delivery** (`901327960792`), Build Control `86ajnx548`, PRD v1.1 (`docs/product/prds/SelahCue-PRD.md`), `docs/decisions/DECISION-LOG.md`, and the code in `implementation/`.

**Readiness verdict: `Not Ready` for MVP launch — and the PRD itself is `Ready with Conditions` (it no longer describes the product being built).**

No ClickUp items were created or changed by this audit. Ticket creation is gated on your approval (§9).

---

## 1. Method and evidence basis

| Evidence | How it was obtained |
|---|---|
| Delivery state | ClickUp `filter_tasks` over list `901327960792`, both pages — 132 open items, statuses tallied below |
| Requirement set | PRD §33 traceability — the normative MVP list is **85 FRs** |
| Implementation state | Direct code probes over 229 source files in `implementation/{desktop,api,mobile}` (symbol/keyword greps per requirement), plus `docs/delivery/BUILD_STATE.md` batch log |
| Scope decisions | DEC-001 … DEC-007 in the decision log |

Claims below are labelled **Verified** (repository or ClickUp evidence cited), **Inferred**, or **Unknown**. Where a probe found no implementing symbol anywhere in source, that is stated as "no implementing code found" rather than "not built" — the distinction matters for a few requirements that could be satisfied indirectly.

---

## 2. Delivery state at a glance (Verified)

> **Superseded same-day — see §11 addendum.** After this section was written the owner accepted the entire 56-item `qa` queue (all moved to `complete`, incl. EPIC — Foundation & Platform `86ajp06yv`) and the Platform API infra batch landed (`cc66e75..145fe17`). Live tally at verification: **82 open items / 61 real work items** (11 `code review`, 7 `in progress`, 2 `ready dev`, 62 `planning/todo` of which 21 are epic/milestone/control containers). The table below is preserved as the state at audit time.

132 open items in the delivery list:

| Status | Count | Meaning |
|---|---|---|
| `qa` | 56 | Built + independently reviewed, **awaiting owner acceptance** |
| `code review` | 10 | Built, in review |
| `in progress` | 7 | Active (incl. Build Control + 2 epics + 1 milestone) |
| `ready dev` | 2 | Specified, not started |
| `planning/todo` | 57 | Of these, **18 are epic/milestone containers** → ~**39 real open work items** |

Three milestones: **MVP Foundation demo** (`86ajp0bpn`, in progress — never closed), **MVP Launch-ready** (`86ajp0bt6`, todo), **R2–R6** (`86ajp0bvg`, todo).

**The single largest delivery risk is not unbuilt features — it is that 56 items sit in `qa` awaiting your acceptance.** Nothing has been formally accepted since the foundation demo. Until that queue drains, "what is built" is really "what is built and unverified by the owner".

Stale artefacts (Verified): `BUILD_STATE.md` ends at 2026-08-01 but 25+ commits have landed since (Platform API, auth, entitlement manifest, email templates). Build Control `86ajnx548`'s description still reads "Current position (2026-07-24) … batches 7a–7ae".

---

## 3. The biggest finding: the PRD no longer describes the product

**Verified.** PRD v1.1 (177 FR / 27 NFR) covers a **desktop presentation app + LAN mobile controller**. Since 2026-08-08 the build has added an entire second product — a commercial platform — under DEC-004/005/006/007, with **zero PRD requirements, zero acceptance criteria, and no traceability**:

| Shipped or in-flight surface | Evidence | PRD coverage |
|---|---|---|
| Platform API (Django + Strawberry) | `implementation/api` — accounts, devices, license_keys, entitlements, audit apps with models/services/migrations | **None** |
| Licensing & entitlements (device activation, license refresh, Ed25519-signed offline manifest) | `86ajy5v7h`, `86ajy5yze`, `86ajy5v6k`, `86ak0mt8f`; `apps/entitlements/signing.py` | **None** |
| Customer identity (email/password auth, verification, reset) | DEC-007; `apps/accounts/models.py` (208 lines); `86ak0qd9u` | **None** |
| Marketing website | `implementation/marketing` — 16 public views (Home, Pricing, Download, Docs, Blog, Careers…) | **None** |
| Admin console | `marketing/src/views/admin` — 9 views (Customers, Licenses, Subscriptions, Payouts, Users…) | Project **brief** only (`SelahCue-Admin-Console-Project-Brief.md`), no PRD |
| Affiliate programme | `marketing/src/views/affiliates` — 6 views + payouts | **None** — no brief, no decision record found |
| SelahCue-hosted AI cloud | `86ajy04hz` (todo), `selahcue-cloud` crate | PRD EPIC-N covers *provider framework*, not a SelahCue-operated service |

**Consequence:** a commercial launch depends on billing, pricing, entitlement enforcement, downloads and support — none of which has a requirement, an acceptance criterion, or a success metric. §7 lists the concrete holes.

**Recommendation:** author `docs/product/prds/SelahCue-Platform-PRD.md` (accounts · licensing · entitlement enforcement · billing · distribution · admin console · affiliate) before further platform build, and add a PRD v1.2 amendment noting the two-product split. This is the highest-value product action outstanding.

---

## 4. MVP requirement gaps (PRD §33 — 85 MVP FRs)

Roughly **60 of 85 MVP FRs are implemented** (mostly at `qa`). The following are the gaps. Everything not listed here was found implemented (Verified by code probe) — e.g. plans/library, slide + theme + canvas editing, scripture navigation/parsing/search/pagination, preview→live separation, main + stage outputs, display identify/assignment, autosave/crash-recovery/crash-loop-breaker/storage guard, emergency clear + blackout, pairing/pinned-TLS/RBAC/mobile control, decode hardening, control-message validation, seizure-safety analyzer, Argon2id secret vault.

### 4.1 Not built — no implementing code found (Verified)

| FR | Requirement | Ticket | Note |
|---|---|---|---|
| FR-006 | Publish / hand-off plan to the live operator view | `86ajy0hwg` todo | Coordinator→operator handoff never built |
| FR-021 | Song copyright metadata (CCLI#) + on-slide footer | `86ajpzhb8` todo | **Licence-compliance affordance** — no `ccli` symbol anywhere |
| FR-031 | Scripture history and favourites | none | No **open** ticket in the backlog — untracked |
| FR-056 | Multiple simultaneous timers + per-output visibility | `86ajpzhbh` todo | Controller holds a single `timer: Option<Timer>` |
| FR-058 | Operator-only vs stage-visible timer scoping | `86ajpzhbh` todo | Currently hard-wired to stage-only |
| FR-059 | Configurable TIME UP (text/colour/background/flash/per-output) | `86ajpzhbh` todo | Rendering is fixed |
| FR-067 | Video playback via OS/HW decoders | `86ajpzhbg` todo | **Deferred by DEC-003** — still an MVP FR in the PRD |
| FR-068 | Audio playback + output-device selection | `86ajpzhbg` todo | Same; only STT *capture* audio exists |
| FR-073 | HW-decode path constrained to platform elements | — | Unverifiable until FR-067 lands |
| FR-078 | Per-layer clearing (text/background/lower-third/media) | `86ajpy59e` todo | Split out of `86ajp0awx`; all-layer clear works |
| FR-138 | Safe file import (zip-slip, path canonicalisation, allowlist) | none | **Security-relevant; no open ticket** |
| FR-139 | Export/import a service plan bundle | none | No open ticket |
| FR-147 | User/role management (create, assign, revoke) | epic `86ajp088c` only | Device RBAC exists; no local user administration |
| FR-150 | Append-only audit log | epic `86ajp088c` only | No `audit_log` symbol in desktop — API has an audit app, desktop does not |
| FR-155 | Signed application updates + anti-rollback | none | **Launch-blocking; no open ticket** — no updater code at all |
| FR-161 | Audio-output-device disconnect/reconnect handling | — | Blocked on FR-068 |

### 4.2 Partial — built but short of the PRD acceptance criteria (Verified)

| FR | What exists | What the acceptance criteria still require |
|---|---|---|
| FR-005 | `plan_repo::duplicate` | "Save as template"; last-3 autosave versions restorable (`86ajy0hxg` todo) |
| FR-014 | Canonical fixed keymap (`keymap.rs`) | Shortcuts must be **remappable** and documented |
| FR-016 | Undo inside the deck workspace | ≥20-step undo/redo across editing operations (`86ajpzhan` todo) |
| FR-020 | User-supplied lyrics | **PD hymn bundle ships with the app** — no hymn assets found |
| FR-025 | 5 bundled translations: WEB, WEBBE, ASV, Darby, **KJV** | PRD names WEB/ASV/BSB/BBE/Darby/Webster and **excludes KJV** (OD-24). BSB/BBE/Webster absent; KJV shipped as default → **open conflict `86ajxvvek`** |
| FR-035 | Translation metadata present | Required attribution surfaced per translation — not evidenced |
| FR-041 | Output status republished on Moved/Resized | Unplug/replug **restores exact prior live content**; no other output blanks — needs a physical-display test |
| FR-049 | Lower-third *screen role* + band render | Lower-third **content types** (speaker name/title, sermon title, scripture ref, logo/image) creatable from templates |
| FR-054 | count-down + count-up in core | time-of-day, elapsed, segment timer types |
| FR-055 | start/pause/reset/add/subtract | Resume semantics + "reflected on all outputs showing the timer" (blocked by FR-056) |
| FR-057 | 5:00/10:00 presets in console | **Configurable** warning threshold + reusable presets |
| FR-061 | Stop/adjust | Explicit TIME UP dismissal paths (manual/auto/mobile) + extend-and-resume |
| FR-090 | 4 roles (Operator/Producer/Assistant/Viewer) | **Seven** roles (`86ajxuf81` + `86ajxufbg`, both todo) |
| FR-091 | Single-use pairing replay guard; connection cap | **Per-device + global command rate limiting**; monotonic sequence/±30s replay window on commands. API-side throttling also open (`86ajy62xz`) |
| FR-176 | Mobile privacy/terms drafts + iOS PrivacyInfo | Legal sign-off, published policy, completed App Store + Play disclosures (`86ajxz3nj` todo) |

### 4.3 MVP-boundary decisions the PRD has not absorbed

- **DEC-003 defers live video/audio render**, but FR-067/068/073 (and dependent FR-161, FR-069) remain MVP in the PRD. Either the PRD's MVP boundary moves to R2 with a recorded rationale, or these are launch-blocking. **This is a product decision you own.**
- **KJV** ships as the default translation against FR-025/OD-24 (UK Crown copyright). Ticket `86ajxvvek` is open at `high`. Legal exposure until resolved.

---

## 5. Later-release (R2–R6) state

Not required for MVP, but relevant to "what is left": R2–R6 epics remain undecomposed by design (Stage-6 deferral). Notably, work has already landed **ahead of** the MVP in some of these areas — on-device STT (R3), live transcript + scripture detection (R4 slice), NDI sink scaffolding (R2) — all sitting in `qa`. NDI/SDI/stream **physical delivery**, motion backgrounds, per-output config, sermon intelligence (R5) and all integrations (R6) are untouched.

---

## 6. Verification and quality debt (Verified)

| Item | State |
|---|---|
| **56 items in `qa`** | Awaiting owner acceptance; blocks any honest "done" claim |
| Foundation-demo milestone `86ajp0bpn` | Still open/in progress since 2026-07-25 |
| Comprehensive test programme `86ajq67q2` | `planning/todo` — E2E, cross-device, reliability, performance, security verification **not started** |
| METRIC-003 (12h soak), METRIC-006 (time-to-first-slide usability) | No evidence of execution — **Unknown** |
| Independent security review of the Platform API | Two pre-commit review tickets open (`86ajyq86g`, `86ajyq89c`); no full review of the auth/licensing surface found |
| Known open defects | `86ajxwcft` (mobile reconnect race can go-live a **stale item**, high), `86ajxwcnc` (remote-control hardening backlog) |

---

## 7. Launch-blocking gaps beyond the feature set

1. **Packaging/distribution.** Windows installer `86ak0ndqg` in `qa`; macOS DMG (signed + notarized) `86ak0ndzc` todo; **no Linux packaging ticket exists** — yet PRD §32 requires packaging validated on all three. Also **no `downloads` backend** (`apps/downloads` is an empty scaffold) while the marketing site has a Download page.
2. **No entitlement enforcement in the product.** Verified: the Platform API issues device tokens, license refresh and a signed offline manifest, but **no desktop code references activation/entitlement/licence at all**. The account-setup design is done (`86ajy600r`, design story); the desktop implementation (`86ajy7anx`) is `planning/todo`. Today the app cannot be licensed, activated, or restricted.
3. **No billing.** `apps/billing`, `apps/catalogue` are empty scaffolds; the marketing Pricing page has no backend. No pricing decision, plan catalogue, payment provider, tax/VAT, refund or dunning requirement exists anywhere.
4. **Marketing/admin/affiliate front ends are unwired.** Verified: no `fetch`/GraphQL call anywhere in `implementation/marketing/src`. They are presentation-only shells.
5. **Signed auto-update (FR-155) does not exist** — required by PRD §32 and a security requirement (threat T14).
6. **Mobile store publication** `86ajxz3nj` todo — signing, accounts, legal sign-off.
7. **User-facing documentation/runbooks** required by §32 — only `docs/ops/DEPLOYMENT.md` found. **Unknown/likely missing.**

---

## 8. Decisions you own (blocking, in priority order)

| # | Decision | Ticket | Why it blocks |
|---|---|---|---|
| 1 | **KJV in the bundle** vs PRD FR-025/OD-24 | `86ajxvvek` | Copyright exposure; also decides whether BSB/BBE/Webster get bundled |
| 2 | **Is video/audio playback in MVP?** (DEC-003 vs FR-067/068/073) | `86ajpzhbg` | Moves the MVP boundary and the launch date |
| 3 | **Commercial model** — pricing, plans, payment provider, affiliate payouts | none | Nothing in billing/catalogue can start without it |
| 4 | **Licensed translations** route + budget | `86ajpzb09` | NIV/NLT/NKJV etc. cannot be bundled; needs counsel |
| 5 | **SelahCue-hosted AI cloud** — build, buy, or defer | `86ajy04hz` | Providers & Privacy is shipped against a service that does not exist |
| 6 | **7-role RBAC** now or ship on 4 | `86ajxuf81` | FR-090 is MVP; mobile + backend both wait on it |

---

## 9. Recommended sequencing (proposal — not yet ticketed)

**Track 0 — unblock the truth (days).** Drain the `qa` queue (or batch-accept with a QA walkthrough), close or re-score the foundation-demo milestone, refresh Build Control + `BUILD_STATE.md`. Everything else is guesswork until this is done.

**Track 1 — make it sellable (the real critical path).** Desktop activation/entitlement client (`86ajy7anx`) → licence enforcement + offline manifest verification → pricing/billing PRD + implementation → downloads backend + macOS DMG + Linux packaging → signed updates (FR-155) → wire the marketing/admin front ends.

**Track 2 — close MVP feature debt.** Timer epic remainders (FR-056/057/058/059/061) · per-layer clearing (FR-078) · plan publish + templates/versions (FR-005/006) · lower-third content types (FR-049) · scripture history/favourites (FR-031) · import/export + safe import (FR-138/139) · CCLI (FR-021) · PD hymns (FR-020) · user/role admin + audit log (FR-147/150) · 7 roles (FR-090) · command rate limiting (FR-091) · remappable keys + global undo (FR-014/016).

**Track 3 — prove it.** Execute the comprehensive test programme (`86ajq67q2`), the 12h soak, time-to-first-slide usability, and an independent security review of the auth/licensing surface.

### Tickets created from this audit (owner-approved 2026-08-14)

| Ticket | Scope | Parent epic | Priority |
|---|---|---|---|
| [86ak0qmza](https://app.clickup.com/t/86ak0qmza) | FR-155 signed application updates + anti-rollback | Admin, Roles & Security | high |
| [86ak0qmzv](https://app.clickup.com/t/86ak0qmzv) | FR-138 safe file import (path canonicalisation, zip-slip, allowlist) | Service Planning & Library | high |
| [86ak0qn15](https://app.clickup.com/t/86ak0qn15) | FR-139 export/import a service plan bundle | Service Planning & Library | normal |
| [86ak0qn2u](https://app.clickup.com/t/86ak0qn2u) | FR-031 scripture history and favourites | Scripture (Public Domain) | normal |
| [86ak0qn4j](https://app.clickup.com/t/86ak0qn4j) | Linux packaging + install validation | Foundation & Platform | high |
| [86ak0qn63](https://app.clickup.com/t/86ak0qn63) | Platform PRD — accounts/licensing/billing/distribution/admin/affiliate | Platform API / Licensing | high |

Still outstanding, **not** ticketed (needs your decisions first): a PRD v1.2 amendment covering the DEC-003 MVP-boundary change (video/audio) and the FR-025/KJV resolution.

---

## 10. Verdict

**`Not Ready`.** The presentation product is materially complete and unusually well-verified at the batch level; the *product* is not launch-ready because (a) 56 built items have never been accepted, (b) the entire commercial surface — licensing enforcement, billing, distribution, updates — is either absent or unwired, (c) ~16 MVP FRs have no implementing code and 15 more are partial, and (d) the PRD does not describe half of what is now being built.

**Gate:** this audit does not approve itself. Per the PM contract, ClickUp work is created only after your explicit approval of §9.

---

## 11. Addendum — same-day verification pass (2026-08-14, post-acceptance)

A second `/product-manager` pass re-verified this audit against the live ClickUp list, the tree after commits `cc66e75..145fe17`, and a full `docs/design/` inventory. Corrections and new findings:

### 11.1 Delivery state (supersedes §2 and part of §6)

- **The 56-item `qa` acceptance backlog is drained** — the owner accepted all 56 on 2026-08-14. It is no longer the critical path. Live state (Verified via `filter_tasks` on `901327960792`): **82 open / 61 real work items** — 11 `code review`, 7 `in progress` (incl. Build Control, EPIC Canvas Editing `86ajq6j01`, milestone `86ajp0bpn`), 2 `ready dev`, 62 `planning/todo` (21 containers).
- Build Control `86ajnx548` description says "76 open items"; the live count is 82 (the six audit gap tickets post-date that sentence). Minor description drift only.

### 11.2 Platform API infra shipped after this audit (Verified, commits `cc66e75..145fe17`, all `implementation/api` + docs)

Docker Compose (api/Postgres/Redis/celery-worker/celery-beat/mailhog), a Celery app, **fixed-window rate limiting on `/v1`** (the API half of the FR-091 partial — `86ajy62xz` now `code review`), transactional email delivered through the worker (all three TRANSACTIONAL-EMAIL-spec templates), and hourly beat jobs for the licence-revocation cascade + expiry sweeps. Desktop/mobile claims in §4 are unaffected (no non-API code changed).

### 11.3 NEW launch-blocking gap: the verification/reset emails link to routes that do not exist

**Verified.** `implementation/api/selahcue_api/apps/accounts/tasks.py:55` builds `{FRONTEND_BASE_URL}/verify?token=…` and `:64` builds `{FRONTEND_BASE_URL}/reset?token=…` (`FRONTEND_BASE_URL` defaults to `http://localhost:2000`, `settings.py:277`). **No surface serves `/verify` or `/reset`**: `implementation/web/` is a lone README, the marketing SPA router has no such routes, and the API serves none. Design coverage is likewise absent — `TRANSACTIONAL-EMAIL-spec.md` §"Open, owned elsewhere" explicitly disowns both routes, and `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §12 confirms no create-account-then-verify flow exists. **No ClickUp ticket covers this** (workspace search returns none). Until these pages exist, DEC-007 signup/verification/reset cannot complete end-to-end.

### 11.4 Design-coverage refinement of §3

§3 correctly reports zero *PRD* coverage for the platform surfaces, but design coverage is better than §3 implied: the marketing site (incl. Sign-in `505:124`, Account dashboard `506:124`), the account-portal gap-fill (create account, forgot-password request, entitlements, destructive dialogs), and the admin console + affiliate portal (proposal-grade, **not approved for implementation**) are all designed in Figma `SYQn5hFY8YVQKm3c6rw0eJ`. What has **no design anywhere**: `/verify` + `/reset` token-landing pages and expired-link states; desktop **sign-up** frame (DEC-007 follow-up); "Manage devices"; any checkout/plan-change/payment/dunning/tax flow; marketing/portal mobile+tablet frames (GAP-07); Linux packaging artifact spec.

### 11.5 Micro-corrections from the deep code sweep (Verified)

- API rate limiting is a **per-view decorator**, not middleware: `apps/throttling/decorators.py:16`, applied at `platform/views.py:49/126/163` (activation 10/60s; refresh + manifest 60/60s), fixed-window over Redis db 1.
- `apps/entitlements` has **no models and zero migrations** — a stateless service layer (`services.py` 101 + `signing.py` 119, real Ed25519) over `devices`/`license_keys`.
- `selahcue-cloud` (desktop) is a **real HTTP client but for the notes/quota API only** (`contract.rs:23-26`: `POST /v1/notes:generate`, `GET /v1/quota`) — it does not touch licensing endpoints. `lib.rs:3`: "The live SelahCue cloud service does not exist yet."
- The **stage theme + message engine is fully wired end-to-end** (`selahcue-present/src/stage.rs` → `operator.rs:531/538` + remote `:1245/:1256` → Tauri `main.rs:1199/1206` → webview `dist/index.html:308/332`), and `stage_template`/`stage_message` ride the LAN protocol — so mobile story `86ajxx4wf`'s stated blocker ("needs backend stage-message command") appears already resolved; only the RBAC/permission mapping for mobile roles needs confirming.
- `implementation/api/selahcue_api/settings.py:275-276` itself documents the §11.3 gap: "those routes do not exist yet — they land with slice 4 (86ajy7anx). Emails link to a 404 until then." Note `86ajy7anx` is the **desktop** account-setup task; the web landing pages are in nobody's in-scope list.
- FR-020's "PD hymn bundle" is confirmed absent as content: no hymn assets anywhere; `plan.rs:215`'s stanza format is a parser, not a corpus.

### 11.6 PRD staleness, quantified (refines the §0 "Ready with Conditions" verdict)

The 85-FR MVP list remains a **usable definition of done for the presentation product**: 78 of 85 MVP FRs are uncontested. The stale/contested set is exactly: **FR-067/068/073/161 (+R2 FR-069)** — MVP on paper, deferred by DEC-003, owner decision `86ajpzhbg` pending; **FR-025** — shipped bundle (KJV default + WEBBE/Darby, no BSB/BBE/Webster) contradicts the FR text (decision `86ajxvvek`); **FR-090** — seven roles specified, four shipped (decision `86ajxuf81`). What the PRD cannot define is V1 for the **commercial platform** — that is the Platform PRD's job (`86ak0qn63`), which §3 already identifies as the top product action.
