# Design 2.0 parity audit — Settings

**Role:** UI/UX Designer (Uma) · **Date:** 2026-09-20 · **Type:** read-only audit + gap spec (lighter
pass, per the Phase B brief: full audit of what's built, page-level `MISSING` for what isn't)
**Goal Contract:** `docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ`. Two relevant nodes:
- `338:124` "Settings — Design 2.0" — the pre-existing **flagship** page (Providers & Privacy), the only
  one of the ten sidebar items that predates the 8-page expansion.
- `618:124` "SelahCue · Settings — Design 2.0 (8 pages + all states)" — the **other eight** sidebar pages
  (General/Scripture/Outputs/Network/Appearance/Security/Storage/About), 51 frames (8 defaults + 43
  states), documented in `docs/design/SETTINGS-2.0-HANDOFF.md`.
**Companion doc:** `docs/design/SETTINGS-2.0-HANDOFF.md` (frame-by-frame design spec + its own
independent design-QA pass, referenced throughout rather than re-derived)
**Status:** point-in-time. Figma and `dist/` both move; re-run before acting on a row older than a week.

## What was audited

`#surface-settings` (`index.html:1098-1189`) and `settings.js` (1312 lines) against the **two built**
pages (Providers & Privacy, Network & Mobile) in full. The **seven unbuilt** pages are recorded as
page-level `MISSING` findings, per the Phase B brief's instruction not to manufacture component-level
drift against pages that don't exist yet in the app.

### A documentation-side discrepancy, noted but not fixed here

`SETTINGS-2.0-HANDOFF.md:4` names the 8-page section **`593:124`**. `get_metadata` against
**`618:124`** (the node id given in this audit's own brief) returns exactly the content the handoff
describes (General `577:126`, Scripture `578:124`, Outputs `579:124`, Network `580:124`, Appearance
`581:124`, Security `582:124`, Storage `583:124`, About `584:124`, plus all 43 state frames) — so
`618:124` is confirmed as the live node. Whether `593:124` was the section's id at authoring time and it
was later renumbered (Figma section ids can change when a section is duplicated or rebuilt, unlike frame
ids, which are more stable), or whether it was a typo in the handoff, was not determined — recorded as
**Open question SET-OQ-1**.

## Method

`get_metadata` on `618:124` (full 8-page + all-states subtree — 1.16MB, exceeded the inline tool
response limit and was parsed from the saved file with `python3`/`jq`) and on `338:124` (the flagship,
returned inline). Cross-checked against `index.html:1098-1189`, `settings.js`, and the sidebar-routing
logic in `app.js:1320-1374`.

## Verdict vocabulary

**MATCH** / **DRIFT** / **MISSING** (including page-level MISSING, called out separately below) /
**EXTRA** / **UNSPECIFIED** / **INTENTIONAL-DEVIATION** / **A11Y-DEFECT** / **A11Y-CONFLICT**.
Severity: **S1** blocks correct/accessible use · **S2** visible parity break · **S3** cosmetic ·
**S4** informational.

---

# Summary

**9 numbered findings: SET-001…SET-009**, of which **7 are page-level MISSING findings** (one per
unbuilt sidebar page) and **2** are component-level findings against the two built pages, plus **7**
unnumbered MATCH confirmations across those same two pages (listed in the tables below for evidence,
consistent with the other audits' convention of numbering gaps and decisions but not every plain match).

| Verdict | Count |
|---|---|
| MATCH (unnumbered) | 7 |
| INTENTIONAL-DEVIATION | 1 |
| MISSING (page-level) | 7 |
| MISSING (component-level) | 1 |
| A11Y-DEFECT | 0 |

Severity: **0 × S1**, 9 × S2 (7 unbuilt pages + SET-008 recorded as a decision + SET-009), 0 × S3,
0 × S4 beyond the BYOK/Advanced-row note folded into SET-008.

## Headline

1. **Nine sidebar items, three tiers of readiness.** Two pages are genuinely built and wired to real
   host state (Providers & Privacy, Network & Mobile); one (Pre-service Check) is not a Settings page at
   all but a link-out to the standalone surface already audited separately
   (`DESIGN-2.0-PARITY-AUDIT-preservice.md`); the remaining **seven** — General, Scripture &
   Translations, Outputs & Displays, Appearance, Security, Storage & Backups, About & Licensing — render
   a single shared "coming soon" placeholder. All seven are fully designed (51 Figma frames between
   them, an independent design-QA pass already run against all of them per the handoff's §9) and none
   are built. This is squarely "not yet built," not "built wrong" — recorded as seven page-level
   `MISSING` findings, **SET-001…SET-007**, rather than manufactured component drift.
2. **The two built pages are a close match to their reference frame(s).** Providers & Privacy
   (`338:124`) and Network & Mobile (`580:124`) both implement their designed sections with real,
   host-backed data — no fabricated figures, consistent with the project's stated policy.
3. **One deliberate, documented scope cut on the built flagship.** `338:124` draws a TEXT-TO-SPEECH
   section that the shipped Providers & Privacy page omits entirely — matching the code's own comment,
   *"TTS (DEC-001) and the BYOK/Advanced row (hosted-only) are excluded"* — a real product decision
   (DEC-001), not an oversight. **SET-008, INTENTIONAL-DEVIATION.**

---

# Page-level coverage

| Sidebar item | `data-setpage` | Figma page | Built? | Finding |
|---|---|---|---|---|
| General | `general` | `577:126` | No — shared placeholder | **SET-001** MISSING |
| Pre-service Check | `preservice` | n/a (link-out to `#surface-preservice`, `app.js:1364-1367`) | Yes, but as a **navigation**, not a Settings sub-page — out of scope here, covered by `DESIGN-2.0-PARITY-AUDIT-preservice.md` | — |
| Providers & Privacy | `providers` | `338:124` | **Yes** | see below |
| Scripture & Translations | `scripture` | `578:124` | No — shared placeholder | **SET-002** MISSING |
| Outputs & Displays | `outputs` | `579:124` | No — shared placeholder | **SET-003** MISSING |
| Network & Mobile | `network` | `580:124` | **Yes** | see below |
| Appearance | `appearance` | `581:124` | No — shared placeholder | **SET-004** MISSING |
| Security | `security` | `582:124` | No — shared placeholder | **SET-005** MISSING |
| Storage & Backups | `storage` | `583:124` | No — shared placeholder | **SET-006** MISSING |
| About & Licensing | `about` | `584:124` | No — shared placeholder | **SET-007** MISSING |

Confirmed by direct read of the routing logic (`app.js:1334-1359`, `setSettingsPage()`): `built = {
providers: "set-page-providers", network: "set-page-network" }` — **exactly** two entries. Every other
`data-setpage` value falls through to `#set-placeholder`, which renders a shared, honest message: *"This
settings page is designed (Figma 338:124) and coming soon. Providers & Privacy and Network & Mobile are
available now."* (`index.html:1180-1186`). This is the one literal "coming soon" string in the file at
this audit's time of reading — a lower count than the Phase B brief's planning-time estimate of three,
re-verified directly rather than assumed (the `coming-soon` **CSS class** is reused generically elsewhere
for unrelated honest "later" affordances on other surfaces, which is what the earlier grep likely
counted).

Each placeholder page carries the correct page title (`#set-ph-title`, set from the clicked nav button's
own label) so an operator who clicks "Security" sees "Security" named in the placeholder, not a generic
message — a small but real honesty detail worth recording as **MATCH**, not folded silently into the
page-level MISSING findings above.

---

# Providers & Privacy (`338:124`) — built page, full pass

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Header: title + "Choose where transcription, AI notes and speech run…" | `340:125-126` | `.pp-title`/`.pp-sub`, `index.html:1126-1127`, word-for-word | MATCH | — |
| — | "Offline by default" banner | `340:127-131` | `.pp-banner.pp-banner-ok`, `index.html:1131-1137`, word-for-word | MATCH | — |
| — | LIVE TRANSCRIPTION — two radio cards (On-device 🔒PRIVATE, Cloud ☁OPT-IN) | `340:132-158` | `renderTranscription()` (`settings.js:215-300`): `transcriptionCard()` builds both cards from real `providers_view()` state — model name, latency, size, offline capability for on-device; a `⚠` warning row for cloud ("Streams live microphone audio to the provider while active") | MATCH | — |
| — | SELAHCUE AI · SERMON NOTES — usage counter, quota bar, template/translation selects, include-in-notes toggles, Generate button, consent copy | `348:124-211` | `renderAi()`/`renderQuota()`/`includeRow()`/`onGenerate()` (`settings.js:321-593`) — all host-driven, no fabricated quota figures per the code's own trust-boundary discipline (matching the pattern already verified on the Service Plan surface's summary panel) | MATCH | — |
| **SET-008** | TEXT-TO-SPEECH section (Voice select, Output routing select, PA-safety warning) | `340:182-198` | **NOT FOUND** anywhere in `#surface-settings` or `settings.js` | **INTENTIONAL-DEVIATION** — DEC-001 excludes TTS from this build entirely; this is a scoped product decision, not a gap. Recorded so the omission has evidence behind it rather than reading as an unexplained hole | S2 (recorded as a decision) |
| — | ADVANCED — "Bring your own key / custom provider" row | `348:201-211` | **NOT FOUND** | **INTENTIONAL-DEVIATION** — the code comment at `index.html:1098-1103` states this directly: *"TTS (DEC-001) and the BYOK/Advanced row (hosted-only) are excluded."* Hosted-only is a real, documented product posture | S4 |

## Network & Mobile (`580:124`) — built page, full pass

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Header + "Offline by default"-style banner ("Controllers connect over your local network") | Handoff §4.4 | `index.html:1156-1166`, close paraphrase of the intended banner copy | MATCH | — |
| — | DEVICES link-card → Remote Control · Devices | Handoff §8: *"Network/roles/pairing → Remote Control · Devices `359:124`"* | `.set-linkcard` (`index.html:1167-1176`): "Remote Control · Devices" title, description, `Manage devices ▶` button routing to `showSurface("remote")` (`app.js:1372-1373`) | **MATCH** — correctly a link-out, not a duplicate of the pairing UI (matches the handoff's explicit "don't duplicate" rule) | — |
| **SET-009** | LAN defaults (server on/off, mDNS visibility, rate-limit controls) — implied by `580:124`'s own content per the handoff §4.4 (FR-085 LAN server/mDNS; FR-091 rate limits) | Not drawn on the built page at all — the shipped Network & Mobile page is **only** the banner + the Devices link-card | Confirmed absent by direct read of `index.html:1153-1177` | **MISSING** — the handoff's own scope for this page (LAN server defaults, not just a link-out) is narrower in the shipped build than in the design | S2 |

---

# Accessibility

## A11Y-1 — Clear

No gradient-styled primary action was found on either built Settings page — `#pp-generate`/
`.pp-generate` and `#set-open-remote`/`.pm-btn-primary` reuse the same flat-fill primary button already
measured compliant (4.72:1) on the Presentation surface. **This is the second surface this round (after
Remote Control) with no instance of the recurring gradient/white-text defect** — worth naming given how
often it recurred elsewhere.

## A11Y-2 — Classified, not blanket-swapped

The handoff's own §7 already states the project's muted-token policy applies here identically to every
other surface (`text-muted` for tertiary labels only). This audit's read of the two built pages found no
new violation of that policy beyond the pre-existing, project-wide condition already tracked (Q-02 in
the Presentation audit).

## A11Y-3 — Not verifiable for the seven unbuilt pages

The handoff's own §7 and §9 (independent design-QA, 8 reviewers) already give the unbuilt pages a
documented accessibility pass **at the design level** — contrast-audited tokens, colour-never-alone
status pairing, admin-gating via removal from tab order rather than greying, ≥44px targets. None of that
can be re-verified against a live DOM that doesn't exist yet. Recorded as a dependency for whoever builds
these pages, not as a finding against the current code.

---

# Open questions

- **SET-OQ-1 (documentation hygiene).** `SETTINGS-2.0-HANDOFF.md:4` names the 8-page section `593:124`;
  this audit's brief and a direct `get_metadata` both confirm the live node is `618:124`. Whoever next
  edits that handoff should correct the section id (or confirm which of the two is stale) rather than
  leaving two audits pointing at different numbers for the same content.
- **SET-OQ-2 (product/delivery, the one this brief specifically anticipated).** Which of the seven
  unbuilt pages should be prioritised first? The handoff's own §9 design-QA already certifies all 51
  frames as implementation-ready with **no outstanding critical or major issues** — so this is purely a
  sequencing decision, not a design-readiness gate. Not Uma's or Farah's call.
- **SET-OQ-3 (product).** SET-009 — was Network & Mobile's LAN-defaults scope (server on/off, mDNS
  visibility, rate limits) deliberately deferred behind the Devices link-out for this build, or is it a
  genuine gap against the page's own designed scope? The handoff's frame-level detail for `580:124`
  itself was not independently re-derived in this pass (out of scope per the "lighter pass" instruction)
  — flagging rather than asserting.
- **SET-OQ-4 (product).** SET-008/TTS — DEC-001 is cited as the reason TTS is absent; confirm this
  decision is still current before anyone reads its absence as a bug to fix.
