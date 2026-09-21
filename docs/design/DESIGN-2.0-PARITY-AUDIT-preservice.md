# Design 2.0 parity audit — Pre-service Check

**Role:** UI/UX Designer (Uma) · **Date:** 2026-09-20 · **Type:** read-only audit + gap spec
**Goal Contract:** `docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ`, frame `344:124` "Pre-service Check — Design 2.0" (1760×1000)
**Status:** point-in-time. Figma and `dist/` both move; re-run before acting on a row older than a week.

## What was audited

`#surface-preservice` (`index.html:1278-1321`) plus its render logic, all of `preservice.js` (386
lines — the surface's own file, read in full). Confirmed by grep against the three existing audits: no
`344:*` id appears in `DESIGN-2.0-PARITY-AUDIT-{console,presentation,stage}.md`.

## Method

`get_metadata` on `344:124` (one call, full subtree — the frame is a single populated mock, no separate
states board), cross-checked against `preservice.js` line by line. No bound Figma variables on this
frame; every colour below is a raw literal, named by its matching `--sc-*` token.

## Verdict vocabulary

**MATCH** / **DRIFT** / **MISSING** / **EXTRA** / **UNSPECIFIED** / **INTENTIONAL-DEVIATION** /
**A11Y-DEFECT** / **A11Y-CONFLICT**. Severity: **S1** blocks correct/accessible use · **S2** visible
parity break · **S3** cosmetic · **S4** informational.

---

# Summary

**10 numbered findings: PSC-001…PSC-010.**

| Verdict | Count |
|---|---|
| MATCH | 12 |
| DRIFT | 4 |
| MISSING | 4 |
| EXTRA | 1 |
| A11Y-DEFECT | 1 |

Severity: **1 × S1**, 6 × S2, 9 × S3, 6 × S4.

## Headline

Pre-service Check is a **single populated mock**, not a states board — Figma draws exactly one
confident, all-green-except-two-warnings scenario, with no empty/loading/error frames of its own. The
implementation reasonably has to invent the states the frame doesn't show (no host connected, a check
whose data isn't wired yet), and does so **honestly** — every check that cannot be verified today
degrades to a `pending` state with a truthful reason string, never a fabricated pass. Two clusters of
gaps:

1. **Three of the nine checks cannot detect the exact condition Figma's mock shows.** Livestream frame
   drops, motion-background caching, and AI consent are all drawn *populated* in Figma (a warn state and
   two green "ready" states respectively) but the host does not yet expose the telemetry any of the
   three needs — the code says so in each check's own comment. **PSC-002/PSC-003/PSC-008.**
2. **The `▶ Start service` primary button repeats the codebase's recurring gradient/white-text contrast
   defect** — the fifth sighting in this audit round. **PSC-005, A11Y-DEFECT, S1.**

---

# Frame `344:124`

## Header

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Brand row + "Pre-service Check" surface label | `344:126-132` | Global app header, same relocation pattern already accepted on every other surface (`index.html:64` region) | MATCH | S4 |
| **PSC-001** | "Sunday Service · 10:32 AM" | `344:133`: 154×15, right-aligned | **NOT FOUND** — no timestamp/service-name readout exists anywhere in `#surface-preservice` (`index.html:1284-1321`) or `preservice.js` | MISSING | S2 |

## Lead + section headers

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | "Pre-service check" H1 + sub-copy "Everything that must be right before the first slide goes live." | `344:137-138` | `index.html:1288-1289`, word-for-word | MATCH | — |
| — | Section overlines: DISPLAYS & OUTPUTS / MEDIA / AUDIO / STORAGE, NETWORK & PROVIDERS | `344:140/165/183/199` | `buildSections()` (`preservice.js:181-188`) — same four sections, same titles, same order, same check groupings (3/2/2/3 checks) | **MATCH**, exactly | — |

## Check rows

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Row: status icon (✓/!/✕/…) + title + detail + optional action button | `344:142-220`, e.g. `344:143-147` ("Audience — Main", ✓, "Connected · 1920×1080 · 60fps") | `renderCheckRow()` (`preservice.js:201-223`): `.ps-ico-<state>` glyph (`{ok:"✓",warn:"!",block:"✕",pending:"…"}`), title, detail, and an action button when `chk.action` is set — plus a full SR summary (`"<title> — <state word>. <detail>"`) the frame has no equivalent for | **MATCH** (+ EXTRA a11y summary) | — |
| — | Audience — Main | `344:145-147`: ✓ "Connected · 1920×1080 · 60fps" | `checkMainOutput()` (`preservice.js:71-84`): resolves `signal` to `ok`/`warn`/`block`/`pending` from real `OutputStatusView` data, builds the identical `"Connected · WxH · Nfps"` string | MATCH | — |
| — | Stage Display | `344:150-154`: ✓ "Connected · Current+Next+Timer" | `checkStageOutput()` (`preservice.js:85-94`): resolves `stage_template` to the same label set (`STAGE_LABEL`, `preservice.js:53-57`), including honestly reporting "not set up (optional)" when absent — a state Figma's confident mock doesn't draw | MATCH (+ EXTRA state) | — |
| **PSC-002** | Livestream Program | `344:159-163`: **!** "Frame drops detected — check encoder" + Details | `checkLivestream()` (`preservice.js:95-108`): can only report `pending` ("NDI output is off") or `ok` ("NDI output on · <name>") — **no frame-drop path exists**, the function's own comment states why: *"Live encoder frame-drop telemetry is not exposed yet (honest note)."* | **MISSING** — the exact scenario Figma's mock draws cannot be produced by this build at all | **S2** |
| — | Slide media present | `344:170-174`: **!** "1 file missing — Baptism.jpg" + Locate | `checkSlideMedia()` (`preservice.js:109-123`): resolves real `missing_count` from `deck_view`, builds `"<n> file(s) missing"` + a `Locate` action routing to the Presentation surface | MATCH | — |
| **PSC-003** | Motion backgrounds cached | `344:179-181`: ✓ "4 backgrounds · pre-decoded" | `checkMotionCache()` (`preservice.js:124-126`) is a one-line stub: `{ state: "pending", title: "Motion backgrounds cached", detail: PENDING_LATER }` — a hard-coded honest "not checked yet" regardless of any real state | **MISSING**, self-labelled (`PENDING_LATER = "Not checked yet — arriving in a later slice."`) | S2 |
| — | Input device | `344:189-190`: ✓ "Focusrite Scarlett 2i2 · channel 1" | `checkAudioDevice()` (`preservice.js:127-136`): reads a real `audio_input` device state, with honest degradation (`not_in_build` / `no_device` / `ok`) | MATCH — the specific Figma device name is illustrative content, not a spec value | — |
| **PSC-004** | Signal levels | `344:195-197`: ✓ "Healthy · −18 dB peak" (drawn as an at-rest passing check) | `checkAudioLevels()` (`preservice.js:137-144`) is **always** `pending`: *"Shown live while listening (start transcription to check)"* — the function's own comment explains why: live dB metering needs an active capture stream, so an at-rest "Healthy · −18 dB peak" would be a fabricated reading | **DRIFT** (a deliberate, well-reasoned honesty trade-off — Figma draws a value this build structurally cannot produce without lying) | S3 |
| — | Disk space | `344:204-206`: ✓ "42 GB free · autosave on" | `checkDisk()` (`preservice.js:145-154`): real `disk_free`, with `DISK_CRITICAL`/`DISK_LOW` thresholds mirroring "the host guard's spirit" per its own comment | MATCH | — |
| — | Local network & remotes | `344:211-213`: ✓ "Network up · 2 remotes paired" | `checkNetworkRemotes()` (`preservice.js:155-165`): matches the string format exactly, gated on `hostConnected` — see **PSC-007** below for why that gate matters | MATCH | — |
| **PSC-008** | Transcription & AI | `344:218-220`: ✓ "On-device ready · **AI consent granted**" | `checkTranscriptionAi()` (`preservice.js:166-178`): on-device STT readiness is real (`stt_ready`); the AI-consent half is a **hard-coded literal string** `" · AI consent — later"` appended in every branch — the function's own comment: *"the AI-consent half is still a deferred product decision, so it's noted honestly rather than claimed"* | **MISSING** (the consent-granted half of this check has no real signal at all) | S2 |

## Readiness sidebar

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | READINESS kicker | `345:124` | `.ps-kicker`, `index.html:1297` | MATCH | — |
| — | Verdict dial + card ("Safe to start", ✓, "11 checks passed · 2 warnings · 0 blocking") | `345:125-129` | `renderReadiness()` (`preservice.js:245-312`): `data-state` driven (`ok`/`warn`/`block`/`pending`) cascading through `.ps-verdict-card`/`.ps-dial`/`.ps-dial-glyph` (`app.css:6364-6376`), summary string built from live counts | MATCH | — |
| **PSC-006** | Verdict logic — Figma's mock shows "Safe to start" as green even with 2 warnings present | Implied by the mock (warnings ≠ blocking) | `renderReadiness()` (`preservice.js:259-271`): explicit three-tier order — no host connected → `pending`; any blocking → `block`; otherwise → `ok` **even with warnings**, matching the code comment *"Otherwise → 'Safe to start', even with advisory warnings (mirrors the design)"* | **MATCH**, and the code explicitly cites the design intent it is mirroring | — |
| — | Passed / Warnings / Blocking count pills | `345:130-147` | `.ps-count-row`/`.ps-count-pill`, `setPill()` (`preservice.js:192-196`) — zero-state pills go neutral grey rather than a coloured zero, matching the code comment's explicit design callout | MATCH | — |
| — | REVIEW BEFORE START cards, blocking-then-warning order | `345:148-159` | `renderReadiness()` (`preservice.js:281-297`): `flagged = blocking.concat(warnings)`, each card `⛔`/`⚠` + title + detail | MATCH | — |
| **PSC-005** | `▶ Start service` primary CTA | `345:160-161` | `.ps-start` (`app.css:6404-6407`): `background: linear-gradient(to right, var(--sc-primary-hover), var(--sc-primary))`, `color: #fff`, `font: 700 16px/1` | DRIFT in the frame (not clearly a gradient as drawn) / **A11Y-DEFECT in the implementation** — see **A11Y** below | **S2 (parity) / S1 (a11y)** |
| — | `↻ Re-run checks` | `345:162-163` | `.ps-rerun`, flat `--sc-elevated` fill | MATCH | — |
| — | "Last checked 30s ago · re-runs automatically each service" | `345:164` | `updateLastChecked()` (`preservice.js:313-320`) builds the identical string pattern, and the auto-refresh really does run every ~15s while the surface is visible (`tick()`, `preservice.js:365-371`) — not just copy that claims it | MATCH | — |

## States Figma does not draw, that the code adds

| # | Component | Verdict | Sev |
|---|---|---|---|
| **PSC-007** | "No output window connected" — every check gates on `hostConnected` (an explicit `true` from a real `host_connected` command); with no host, checks read `pending` rather than fabricating a pass, and the verdict reads *"No output window"* / *"Connect an output window to run the checks"* (`preservice.js:269, 277-279`). Correctly distinguishes a real desktop host from the stand-alone demo, which the code comment notes would otherwise report an indistinguishable empty `remote_snapshot` | EXTRA (a necessary, honestly-built state the single-mock frame has no equivalent for) | S4 |

---

# Accessibility

## A11Y-1 — Real defect (fix regardless of the frame)

| # | Where | Measured | Why it fails | Fix |
|---|---|---|---|---|
| **PSC-005** | `.ps-start` — `app.css:6404-6407`: `background: linear-gradient(to right, var(--sc-primary-hover), var(--sc-primary))`, `color: #fff`, `font-weight: 700`, `font-size: 16px` | white on `--sc-primary-hover #7E6EFF` (the gradient's start) = **3.78:1** | 16px bold needs ≥18.66px bold to count as large text — it does not, so the 4.5:1 bar applies. This is the **Start service** button: the single action that transitions an operator from pre-flight checks into the live console. It is the **fifth** sighting of the same defect this audit round (already fixed once at `.tb-golive`, `app.css:4505-4507`; found again at Theme Designer's `.td-save-cta`, Service Plan's `.pm-btn-primary:hover` per the Presentation audit's PME-005, and the Download modal's `.dl-btn-primary:hover`, see that audit). | Darken instead of lighten: `background: linear-gradient(to right, var(--sc-primary), #5a48d0)` (matching the shipped `.tb-golive` fix), or flatten to solid `--sc-primary` (4.72:1). |

## A11Y-2 — Classified, not blanket-swapped

`--sc-text-muted` appears on `.ps-sub`, `.ps-section-h`, `.ps-row-detail` (default state), `.ps-kicker`,
`.ps-review-empty`, `.ps-lastchecked` — all secondary/instructional copy, consistent with the project's
written policy and the classification already applied across the other audits in this round. No new
site promotes this surface past the pre-existing, project-wide condition.

One check worth naming: `.ps-detail-warn`/`.ps-detail-block` recolour the row detail text to
`--sc-warn`/`--sc-live` respectively when a check fails — both measured elsewhere in this codebase as
AA-large-only pairings on dark surfaces (per the Presentation audit's established figures for the same
tokens). At the row detail's 12px/500 weight, this is **not** large text, so this is worth a direct
follow-up measurement rather than being asserted here — flagged as **PSC-009** below rather than scored,
since this pass did not compute the exact ratio for `--sc-warn`/`--sc-live` against `--sc-surface` at
this specific weight/size pairing.

| # | Note |
|---|---|
| **PSC-009** | `.ps-detail-warn`/`.ps-detail-block` (`app.css:6354-6355`) recolour 12px/500 body text to `--sc-warn #F5A524` / `--sc-live #FF4D4D` on `--sc-surface`. Not measured directly in this pass — flag for a follow-up contrast check before treating as clear. |

## A11Y-3 — Clear

- Every status pairs a glyph **and** text (`✓`/`!`/`✕`/`…` plus a state word in the SR summary,
  `preservice.js:220`) — WCAG 1.4.1 satisfied throughout.
- The re-run announcement (`announce()`, `preservice.js:40-47`) explicitly clears then re-populates the
  live region so assistive tech registers a change even when the verdict text is unchanged between runs
  — a real, tested consideration, not an oversight.

---

# Open questions

- **PSC-OQ-1 (product).** PSC-002/PSC-003/PSC-008 are all blocked on host telemetry that doesn't exist
  yet (encoder frame-drop stats, motion-background cache status, AI consent state). Should these three
  checks be de-scoped from the Pre-service Check MVP until that telemetry lands, or should the frame's
  "populated and green" mock be treated as the target state to build toward? Not a design call.
- **PSC-OQ-2 (design, minor).** PSC-001 — is the "Sunday Service · 10:32 AM" service-name/time readout
  a real requirement, or mock dressing for the Figma screenshot? If real, it needs a data source (no
  `service_name`/scheduled-time field was found wired anywhere in this surface's code).
