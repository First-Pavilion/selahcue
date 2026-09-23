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

**Counts above are as originally audited on 2026-09-20 and are left unchanged for the point-in-time
record.** A tenth finding, **`SET-010`** (an A11Y-DEFECT this pass's own A11Y-1 section wrongly cleared),
was found and fixed on 2026-09-21 — see the A11Y-1 correction and the Reconciliation section at the
end of this doc for current state.

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
| **SET-010** | SELAHCUE AI · SERMON NOTES — usage counter, quota bar, template/translation selects, include-in-notes toggles, Generate button, consent copy | `348:124-211` | `renderAi()`/`renderQuota()`/`includeRow()`/`onGenerate()` (`settings.js:321-593`) — all host-driven, no fabricated quota figures per the code's own trust-boundary discipline (matching the pattern already verified on the Service Plan surface's summary panel) | Content/behaviour MATCH. **A11Y-DEFECT, now FIXED** — `.pp-generate` REST + `.pp-generate`/`.pp-optin-btn`/`.pp-gen-preview-confirm` `:hover` carried the CON-007/PME-005 white-on-`--sc-primary-hover` defect (3.78:1); darkened to the established `var(--sc-primary)`→`#5a48d0` pattern. See Reconciliation | was major, now — |
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

## A11Y-1 — Corrected 2026-09-21 (was wrongly "Clear"; see `SET-010` and Reconciliation below)

This section originally claimed no gradient-styled primary action was found on either built Settings
page. That claim was wrong: `#pp-generate`/`.pp-generate` (the SELAHCUE AI · SERMON NOTES "Generate"
CTA, Figma `348:124`) is a `linear-gradient(90deg, var(--sc-primary-hover), var(--sc-primary))` with a
16px bold white label — the same recurring defect as `CON-007`/`CON-067`/`PME-005`, not a flat-fill
button. `#set-open-remote`/`.pm-btn-primary` genuinely is the compliant flat button this section
described; the miss was treating `#pp-generate` as reusing it when it does not share a class or a fill.
See `SET-010` below. `#set-open-remote`/`.pm-btn-primary` itself remains a correct MATCH (4.72:1,
unaffected by this correction).

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

---

## Reconciliation — 2026-09-21

**Scope:** `SET-010` — the sermon-prep Generate panel's contrast defect, found while auditing
`app.css`'s "Generate button + result region" (`.pp-*`, ~line 6854) for the same class of defect
already fixed on Theme Designer / Pre-service / Download modal (ClickUp `17tnw2axpt9`).

### Method

`#pp-generate`'s Figma frame (`348:124`, Providers & Privacy → SELAHCUE AI · SERMON NOTES) was
re-screenshotted directly (`get_screenshot`, node `348:124`) and shows a bright-violet "Generate
Sermon Notes" button with a bold white label — the same design-level pairing already established
(CON-007/CON-067/CON-150) as a Figma-spec defect the shipped code is expected to deliberately
deviate from, not match. `git blame` traces the shipped `.pp-generate` gradient to `ce11f483`
(2026-08-10) and `.pp-gen-preview-confirm` to `70828e94` (2026-09-04) — both well before this
doc's original A11Y-1 pass (`2c8d4c11`, 2026-09-20), so the miss was not a later regression; the
original pass simply read the rule incorrectly. `#tr-generate` in the Transcripts workspace
(`index.html:1270`) reuses the identical `.pp-generate` class byte-for-byte
(`TRANSCRIPTS-2.0-HANDOFF.md` §"Component primitives") — Transcripts itself has no Figma coverage
(same doc, §1) and is not re-audited here, but the fix carries over automatically since it is the
same CSS rule, not a separate implementation.

### FIXED

- **`.pp-generate`** (`app.css`, "Generate button + result region"): REST gradient reversed
  `(--sc-primary-hover, --sc-primary)` → `(--sc-primary, #5a48d0)`; `:hover` changed from
  `filter: brightness(1.06)` to a flat `background: #5a48d0` — deliberately NOT the brightness-filter
  approach, which is the exact unfixed gap still open on `.tb-golive`/`.timer-start` (console audit
  §8.1, tracked separately). REST 3.78:1 → 4.72:1; HOVER 3.78:1 → 6.42:1.
- **`.pp-optin-btn:hover`** (the inline "Opt in & generate" CTA in the `consent_required` state):
  flat `var(--sc-primary-hover)` → flat `#5a48d0`, mirroring `.pm-btn-primary:hover` exactly.
  3.78:1 → 6.42:1.
- **`.pp-gen-preview-confirm:hover`** (the review-before-send Confirm button, F-5): same fix.
  3.78:1 → 6.42:1.

**Total FIXED: 1 finding (`SET-010`), 3 selectors**, all using the identical established
`var(--sc-primary)`/`#5a48d0` values already shipped elsewhere — not a new colour decision.

**Review-round regression, found by Sana (security-reviewer) and fixed in the same PR:**
moving `.pp-generate:hover` off `filter: brightness(1.06)` onto a flat `background` broke
`.pp-generate[disabled]`/`.pp-generate[aria-busy="true"]`'s neutralisation of hover — `:hover`
and `[disabled]` are equal specificity, and the old `filter: none` only ever cancelled a
filter-based hover, so a disabled or in-flight (`aria-busy`) Generate button visibly flipped to
the active fill on hover. This is the exact `PSC-005` trap already documented against
`.ps-start:disabled` (`scripts/operator_headless.py`) — Cody's independent review did not catch
it; Sana's did, by reading the disabled rule's own text rather than only the hover rule. Fixed
identically to `.ps-start:disabled`: the disabled rule now re-declares the REST gradient
explicitly instead of relying on `filter: none` alone.

**A second review-round regression, found by Cody (code-reviewer) on re-review and fixed by
Farah (frontend-engineer):** the identical `PSC-005` trap existed, unfixed, on
`.pp-gen-preview-confirm` — that class is shared by the transient "Confirm — send to provider"
button (never disabled) and the edit-draft form's "Save" button (`pp-gen-save`/`tr-gen-save` in
`settings.js`/`transcripts.js`, which genuinely sets `disabled`+`aria-busy="true"` while saving),
and there was no `.pp-gen-preview-confirm[disabled]`/`[aria-busy="true"]` rule at all — so the
`:hover` fill this same fix added had nothing to lose to on a disabled/saving Save button. Fixed
by re-declaring the REST-state flat `background: var(--sc-primary)` explicitly (flat, not a
gradient, so the fix mirrors `.ps-start:disabled`'s flat shape rather than `.pp-generate[disabled]`'s
two-stop case), with the same `opacity`/`cursor` as `.pp-generate[disabled]` for consistency
within the same CSS block.

### Verification

- `python3 scripts/operator_headless.py`: **1538 checks, 0 FAIL** (18 new `PP-GEN` assertions —
  `.pp-generate` at every gradient stop plus its parsed `:hover` rule text mirroring the
  `CON-046`/`PME-005` pattern; `.pp-optin-btn`/`.pp-gen-preview-confirm` mirroring `PME-005`
  directly — each with a `--sc-primary-hover`-still-fails control). `EXPECTED_MIN_CHECKS` bumped
  1520 → 1538, against the base commit this fix was originally built on.
- Mutation-verified against that base: reverting all three selectors to their original values
  reproduces exactly the 7 originally-expected `PP-GEN` FAILs (the 8th assertion, the
  hover-background regex match, also goes unreachable under the `filter:` mutation, as designed)
  with every other check staying green; restoring returns to 1538/0 FAIL.
- **Rebased onto `main` twice** as unrelated work landed in parallel: first onto ClickUp
  `17tnw2axpt9`/PR #58 (`TD-012`/`PSC-005`/`DLM-001`, `EXPECTED_MIN_CHECKS` 1544 → 1562 at that
  point), then again onto the stacked Settings-pages PRs #68/#70/#71 (ClickUp `17tnw2axptw`,
  which independently closed `SET-001`–`SET-007`/`SET-009` — see the second Reconciliation below
  — and carried `EXPECTED_MIN_CHECKS` to 1768). None of these overlap this fix's 3 selectors.
  Post-rebase count: `EXPECTED_MIN_CHECKS` 1768 → 1786, 1786 checks, 0 FAIL.
- **Sana's disabled-state regression fix** added 5 more assertions (the same `PSC-005` two-check
  pattern: the disabled rule declares its own background, and that background is exactly the
  REST fill) — mutation-verified (reverting the disabled rule's explicit background turns exactly
  1 assertion RED, a second dependent one goes unreachable, restoring returns clean). Count at
  that point: `EXPECTED_MIN_CHECKS` 1786 → 1791, 1791 checks, 0 FAIL.
- **Cody's second-regression fix** (`.pp-gen-preview-confirm[disabled]`) added 5 more assertions,
  same two-check pattern, same mutation-verification shape. Count at that point: 1791 → 1796.
- **Rebased onto `main` a third time**, picking up a peer session's independent fix for
  `.tb-golive`/`.timer-start`'s `filter: brightness(1.06)` hover-regression gap (previously noted
  below as "not done here" — now fixed on `main`, so that note no longer applies). Conflict again
  in `scripts/operator_headless.py` (the same recurring `EXPECTED_MIN_CHECKS` hotspot), resolved
  the same way. Final, empirically re-run count: **`EXPECTED_MIN_CHECKS` 1788 → 1816, 1816
  checks, 0 FAIL.**
- `cargo test -p selahcue-present --test test_tokens`: 19/19 passed (re-run after every change above).
- `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml`: clean
  (re-run after every change above).
- **Cody (code-reviewer) and Sana (security-reviewer) reviewed PR #60 twice each.** First round:
  Cody found no blockers; Sana found the `.pp-generate[disabled]` regression above. Second round
  (after both fixes): Cody found the `.pp-gen-preview-confirm[disabled]` regression above and
  signed off once it was fixed; Sana independently re-verified the first fix live in both
  Chromium and WebKit (the engine Tauri ships on macOS) and gave a clean security pass. Both
  rounds' findings are fixed and re-verified; no open blockers from either reviewer.

### Not done here

Nothing outstanding. The `.tb-golive`/`.timer-start` `filter: brightness(1.06)` hover-regression
gap noted in earlier drafts of this section was fixed independently by a peer session while this
PR was in review (see the third rebase above) — this fix's own `.pp-generate:hover` change was
deliberately built to avoid repeating that same gap, and both are now fixed on `main`.

## Reconciliation — 2026-09-22 (Farah, implementation ticket 17tnw2axptw)

All seven page-level `MISSING` findings and the SET-009 component-level gap are closed. Delivered as
three stacked PRs (branch build order documented on ClickUp 17tnw2axptw's start comment and on the
decision task 17tnw2axpu3, which was still unanswered at implementation time — build order was the
implementer's own judgement call per the ticket's explicit fallback instruction, simplest/lowest-risk
tier first):

| Finding | Page | Figma | PR | Status |
|---|---|---|---|---|
| SET-001 | General | `577:126` | #70 (stacked on #68) | Closed |
| SET-002 | Scripture & Translations | `578:124` | #70 | Closed |
| SET-003 | Outputs & Displays | `579:124` | #71 (stacked on #70) | Closed |
| SET-004 | Appearance | `581:124` | #68 | Closed |
| SET-005 | Security | `582:124` | #71 | Closed |
| SET-006 | Storage & Backups | `583:124` | #71 | Closed |
| SET-007 | About & Licensing | `584:124` | #68 | Closed |
| SET-009 | Network & Mobile LAN-defaults addendum | `580:124` | #71 | Closed |

**SET-OQ-3 answered with evidence, not assumption.** SET-009 asked whether Network & Mobile's
LAN-defaults scope (server on/off, mDNS, rate limits) was a deliberate deferral behind the Devices
link-out or a genuine gap. Checked directly against every `#[tauri::command]` registered in
`selahcue-operator/src/main.rs`'s `generate_handler!` list: no LAN-server, mDNS, cert-regenerate,
revoke-all, or control-audit command exists anywhere in this app. **Genuine backend gap, not a
deliberate deferral.** The addendum (PR #71) builds the full designed section set as real, disabled
controls with honest copy, plus one genuinely real piece: the paired-device summary count from
`remote_snapshot()` (the same command Remote Control · Devices itself uses).

**A second, unanticipated finding surfaced while building Security (SET-005), not flagged by this
audit's original pass**: the Figma mock for the Security page (`582:124`) draws at-rest encryption as
**ON** with a verified badge. The shipped build does **not** encrypt at rest — verified directly against
`selahcue-operator/Cargo.toml` (no `encryption` feature on the `selahcue-data` path dependency) and
`main.rs` (calls `Database::open`, never `open_encrypted`). `ADR-0007` already names FR-154/at-rest
encryption an explicit **R3 acceptance row** — a documented future milestone, not an oversight — so this
is not a new product decision, only a correction of what the Security page should honestly say about
today's build. The shipped Security page reads "NOT YET ON" rather than repeating the mock's claim.
Recorded here since it's exactly the kind of design-vs-shipped discrepancy this audit series exists to
catch, and this specific one wasn't caught by the original `338:124`/`580:124`-only pass (the other five
sidebar pages hadn't been built yet at that time, so `582:124` was never diffed against real backend
behaviour until now).

**Scope discipline applied throughout**: every one of the ~150 individual controls across all seven
pages was checked against the real command registry before being wired for real or rendered as an
honest, disabled control with an inline note — never a fabricated value (the Figma mocks' example data:
device names, disk-usage numbers, audit-log rows, translation lists) and never a live-looking control
with nothing behind it. Sections the Figma frames themselves mark "COMING SOON" (Outputs' PER-OUTPUT
CONFIG/OUTPUT HEALTH/TEST PATTERNS/NETWORK OUTPUTS; several Security/Scripture/Appearance rows) render
that way because the design says so, not as this batch's own judgement.

**Not touched, per the ticket's own explicit instruction**: SET-008 (Providers & Privacy's TTS
omission, DEC-001) — SET-OQ-4 remains open, owner's call.

**Backend follow-up work this build surfaced** (flagged as candidate tickets, not created here — that's
outside a frontend ticket's scope):
- `backup_to`/`backup_to_encrypted`/`integrity_check`/`checkpoint_truncate` already exist as Rust
  functions in `selahcue-data` but have no Tauri command wrapper (Storage & Backups' Backup Now/Restore/
  integrity check are all honestly inert pending this).
- LAN server on/off, mDNS visibility, and rate-limit configuration have no backend at all (SET-009).
- At-rest encryption (SQLCipher) is architecturally designed (ADR-0007) but not wired into the operator
  build (`selahcue-operator/Cargo.toml` needs the `encryption` feature, and `main.rs` needs to call
  `open_encrypted` with a key sourced from the OS secret store).
- No generic settings/preferences persistence exists for operator-UI-only values (density, text size,
  reduce-motion override, startup surface choice, language/region) — General and Appearance's remaining
  inert controls all need this before they can become real.
