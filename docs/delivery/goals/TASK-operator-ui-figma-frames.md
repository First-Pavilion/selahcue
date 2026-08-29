# Goal Contract — TASK-operator-ui-figma-frames

## Identity

- Goal ID: TASK-operator-ui-figma-frames
- Parent goal ID: TASK-propresenter-ui-prd
- Title: The five MVP operator-UI specs have Figma frames in the Design 2.0 file, drawn from the specs and the shipped tokens, with node links recorded in the specs and on the ClickUp tickets.
- Role: ui-ux-designer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak7kgjk (UI-B1, ★) and the four sibling tickets
- Created: 2026-08-28
- Updated: 2026-08-28
- Maximum iterations: 8
- Independent verification required: yes (owner review — the designer's work is reviewed by the user, not the four-reviewer pipeline)

## Objective

RISK-205's "Figma updated after" phase is discharged: each of the five MVP operator-UI
specs has a set of Figma frames covering its real state matrix, in a clearly-named new
section of the existing Design 2.0 file, drawn from the specs and the shipped token
values rather than copied from lagging Design 2.0 frames.

## Baseline

Verified 2026-08-28:

- Five specs exist under `docs/design/` and all five carry a "Figma: none yet" line.
- File `SYQn5hFY8YVQKm3c6rw0eJ` has 5 pages; Page 1 holds all product design work.
  Recent epics are single top-level `SECTION` nodes named `SelahCue · <topic> — Design 2.0 (…)`.
  Rightmost existing content ends near x=78960.
- The only variable collection is `SelahCue Color` (19 vars) and it carries the **legacy**
  palette (`accent/live` `#ef4444`, `text/muted` `#9aa4b2`), not the Design 2.0 `--sc-*`
  values that ship in `dist/app.css:29-56`. Binding it would draw the wrong ink.
- Frames use Inter (Regular / Medium / Semi Bold / Bold).

## Inputs and evidence sources

- `docs/design/SLIDE-VIEW-DENSITY-spec.md` (UI-B1), `PLAN-SECTIONS-DURATIONS-spec.md` (UI-A1),
  `SONG-GROUPS-HOTKEYS-spec.md` (UI-C1), `SCREEN-STATUS-spec.md` (UI-D1),
  `ATTENTION-BADGES-spec.md` (UI-A2), `DOUBLE-CLICK-GO-LIVE-proposal.md`
- `implementation/desktop/crates/selahcue-operator/dist/app.css:29-56` — the shipped `--sc-*` values
- `docs/design/DESIGN-2.0-HANDOFF.md`

## Scope

### In scope

- One new top-level section on Page 1 of the existing file.
- Frames per spec covering the state matrices the specs define.
- Design-2.0 `sc/*` colour variables added to the existing collection at their **shipped**
  values, and bound rather than hardcoded.
- Updating the `Figma:` line in all five specs with real node links.
- A ClickUp comment per ticket with the frame links. Tickets stay `in progress`.
- **Added mid-run at the owner's request:** an in-context frame per spec placing the new component
  inside the real shipped console shell, built from `implementation/desktop/crates/selahcue-operator/dist/`,
  with before/after where the change alters something that already ships, and any fit problem drawn
  as it actually falls rather than designed around (C-010).

### Non-goals

- Any change under `implementation/`.
- Restructuring existing pages, or editing any existing frame or component.
- Closing OQ-1, OQ-5 or OQ-7, or resolving the PREVIEW/LIVE vs STAGED/ON AIR vocabulary.
- Fixing the lagging Design 2.0 component library (recorded as a divergence instead).

### Constraints

- **Do not copy existing Design 2.0 frames.** They lag the shipped console on contrast
  (RISK-205). Draw from the specs and shipped tokens.
- LIVE chip renders at the corrected value (live ink on `--sc-live-soft` + `--sc-live-border`,
  ≥5.3:1) — never white on `--sc-live` (3.27:1).
- `--sc-text-muted` (3.79:1) is not used except the one site UI-D1 §3 justifies.
- Every colour-carried state also carries text or shape.
- PREVIEW / LIVE vocabulary, flagged as awaiting Priya's ruling.
- Auto-layout with `layoutSizingVertical = 'HUG'` for content-hugging cards; never `resize(w, 10)`.
- Shared checkout: touch only the five spec files and this contract.

### Assumptions and unknowns

- ASSUMED (OQ-1, owner): Grid at step 7 — 6 columns, tier M — is the default. Annotated on frame.
- ASSUMED (OQ-5, owner): the richer per-screen dot mapping (live / idle / fault / disabled). Annotated on frame.
- ASSUMED (OQ-7, owner): hotkeys are auto-assigned only in v1. Annotated on frame.
- ASSUMED (Priya): chips read PREVIEW / LIVE. Annotated on frame.

## Dependencies and approvals

- DEC-016 is PROPOSED — nothing moves out of `in progress`. Owner: Priya.
- Vocabulary ruling — owner: Priya, outstanding.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A new top-level section exists on Page 1 named for this epic, and no pre-existing node was modified | script read-back of Page 1 children; overlap check across section children | New SECTION `965:124`, 35 children, zero overlaps; the pre-existing top-level list is unchanged | node `965:124` | PASS |
| C-002 | yes | UI-B1 has frames for Grid, Text, List, slider step 1 and step 9, an image-only slide in Text mode, the three tiers at true pixel size, and staged + live markers visible in every mode | `get_screenshot` at readable zoom on each frame | Nine frames render legibly; markers present in Grid at 12/6/4 columns, in Text and in List | `971:124`, `973:124`, `973:312`, `974:124`, `974:229`, `975:124`, `976:124`, `976:166`, `975:271` | PASS |
| C-003 | yes | UI-A1, UI-A2, UI-C1 and UI-D1 each have frames covering their spec's state matrix incl. empty, warning, multiple-issue and collapsed states | `get_screenshot` per frame | Every state named in each spec appears | `983:127`, `983:318`, `984:127`, `984:237`, `985:127`, `985:196`, `986:127`, `986:225` | PASS |
| C-004 | yes | The LIVE chip is drawn as live ink on `--sc-live-soft` with a `--sc-live-border`, nowhere as white on `--sc-live` except where deliberately labelled as the shipped bug | script read-back of every node containing the text `LIVE` | 27 sites. 24 are the corrected treatment. 3 are white-on-`--sc-live` and all three are named `… WAS / SHIPPED: #fff on --sc-live = 3.27:1, FAILS AA …`, in the legend before/after card and the baseline console frame | read-back output, this session — the 3 exceptions are deliberate, named, and are the bug the spec fixes | PASS |
| C-005 | yes | `--sc-text-muted` appears only at the single site UI-D1 §3 justifies, plus wherever the in-context frames faithfully reproduce shipped console chrome | script read-back of bound variables across the section | The disabled-screen glyph (6 vector strokes across the 3 in-context frames + D1 frames) is the justified new site. The rest are shipped chrome reproduced in the console shell: inactive `.ctab` labels and `.scrip-note`. No new component adds a site | read-back output; the full audit is recorded on an on-frame card in the section | PASS |
| C-006 | yes | OQ-1, OQ-5 and OQ-7 each carry a visible on-frame annotation marking the rendering as an assumption awaiting owner confirmation, and none is described as decided | `get_screenshot` of the legend and of frames `971:124`, `981:124`, `984:237` | Three ASSUMED callouts in the legend plus one on each owning frame, all worded as assumptions with the cost of a late change | screenshots | PASS |
| C-007 | yes | All five spec files have their `Figma:` line replaced with real node links in the documented URL form | `grep -c 'node-id=' docs/design/*-spec.md` | 4 link-bearing lines in each of the five specs | grep output | PASS |
| C-008 | yes | Each of the five ClickUp tickets carries a comment with its frame links and its findings, and each ticket is still `in progress` | ClickUp comment create + `clickup_get_task` read-back | Five comments posted; `86ak7kgjk` and `86ak7kgnm` re-read as `in progress`; no status was written by this session | comment ids 90130312755229 / 755602 / 755980 / 756351 / 756700 | PASS |
| C-009 | yes | No file under `implementation/` and no file authored by a peer session was modified | `git status --porcelain -- implementation/` | 0 lines. `docs/decisions/DECISION-LOG.md` was already modified at session start and was not touched | git output | PASS |
| C-010 | yes | Each spec has an in-context frame placing its component inside the real shipped console shell at real scale, with before/after where it changes something that already ships, and any fit problem drawn as it actually falls rather than designed around | `get_screenshot` at 1760px on each in-context frame | Four frames built from `dist/index.html` + `dist/app.css` (header 64, grid 380/936/380 at gap 16 padding 16, 168px filmstrip cards, 56px pinned footer). Two fit problems drawn honestly and annotated: a 24-slide deck clipping at row 4 in the Slides panel, and the top bar overflowing at ≈1100px | `977:124`, `978:139`, `979:124`, `981:124` + four FINDING cards | PASS |

## Iteration ledger

| # | Criterion | Hypothesis | Action | Result |
|---|---|---|---|---|
| 1 | C-001 | The file's convention is one top-level SECTION per epic, placed right of existing content | Created section `965:124` at x=80000; existing content ends near x=78960 | PASS |
| 2 | C-004 / C-005 | Binding the file's only colour collection would draw the WRONG ink — it holds the legacy palette (`accent/live` `#ef4444`, `text/muted` `#9aa4b2`), not Design 2.0 | Added 41 `sc/*` variables to the existing collection at the shipped `dist/app.css:29-56` values, plus the six structure-palette trios marked PROPOSED in their descriptions; bound them throughout instead of hardcoding hex | PASS |
| 3 | — | `figma.createAutoLayout()` frames default to a white fill | First legend render came back with white boxes over three annotation blocks; cleared 16 default fills and adopted a transparent-by-default `AL()` helper for every later script | Fixed |
| 4 | — | Emoji glyphs (⏱, ⚠) render in Inter | They do not — the clock came back as a blank box. Replaced both with imported SVG vectors whose strokes/fills bind to `sc/warn` and `sc/info` | Fixed |
| 5 | C-002 | UI-B1 needs nine frames to cover its matrix | Built 01–09, including the three tiers at true pixel size as the UI-B2 contract | PASS |
| 6 | C-002 | Drawing tier S to spec would look fine | It does not: at 77 × 44 the 20px group footer strip takes half the card and the PREVIEW chip nearly its full width. Rendered as written so the collision is visible, with a proposed remedy on-frame rather than silently applied | PASS (finding raised) |
| 7 | C-010 | An in-context frame can be approximated | It cannot and must not be. Read `dist/index.html` and `dist/app.css` for real header height, grid template, card sizes, footer height and token usage, then built the shell once and cloned it for each variant | PASS |
| 8 | C-010 | UI-B1's Grid mode fits the real Slides panel | It does not at the assumed default: 316px of panel height, 90px rows, three rows fit, 24 slides need four. Drawn clipped and annotated, with step 5 offered as evidence for the other OQ-1 answer | PASS (finding raised) |
| 9 | C-010 | UI-D1's collapse rule is sufficient at narrow widths | It is not: at ≈1100px the bar needs ~1180px even with the group collapsed, and Blackout clips. Drawn as it falls, with three options and a recommendation for Priya | PASS (finding raised) |
| 10 | C-003 | The other four specs need two frames each | Built A1 (2), C1 (2), D1 (2), A2 (2) plus band labels | PASS |
| 11 | C-007 / C-008 | Spec `Figma:` lines and ticket comments close the loop | Updated five specs; posted five ClickUp comments; verified two tickets still read `in progress` | PASS |

## Terminal state

`GATE_REVIEW` — the verifiable work is complete and the frames are the artefact the owner asked to see. Four things are now waiting on someone else and none of them is mine to settle:

1. **Priya — vocabulary.** PREVIEW / LIVE (drawn) vs STAGED / ON AIR (the tickets). One relabelling pass either way.
2. **Owner — OQ-1, OQ-5, OQ-7.** All three rendered as annotated assumptions. None closed.
3. **Priya / owner — the top bar does not fit at ≈1100px** even with the UI-D1 group collapsed. Three options annotated on frame `981:124`.
4. **Owner — UI-B1 at the assumed default does not fit a 24-slide deck in the real panel.** Evidence on frame `978:139`; step 5 would fit, which bears on OQ-1.

Two documentation conflicts are also recorded and are not fixed here: `NAV-IA-spec.md` §4 ("green = healthy") now contradicts FR-214, and the Design 2.0 component library still carries the 3.27:1 LIVE chip these frames correct.
