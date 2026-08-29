# SelahCue — Operator UI PRD: ProPresenter adopt / adapt / reject

Version: 1.0 (draft, pre-gate) · Date: 2026-08-28 · Owner: Product Manager (Priya) · Status: **For owner gate review — no ClickUp tickets exist yet (Diego cuts them after approval)**

**Sources:** owner-supplied ProPresenter screenshots (two, described in the commissioning brief — treated as primary evidence of the owner's reference UI), `docs/research/PROPRESENTER-UI-RESEARCH.md` (Rowan's cited evidence report, produced alongside this PRD), prior repo research (`docs/research/COMPETITOR-MATRIX.md` §2.2, `docs/research/LIBRARY-ORGANISATION-RESEARCH.md` §2.1), the master PRD (`SelahCue-PRD.md`, FR-001…177), design canon (`docs/design/DESIGN-2.0-HANDOFF.md`, `NAV-IA-spec.md`, `THEME-MODEL-spec.md`, `UX-CANONICAL.md`), architecture (`docs/architecture/ARCHITECTURE.md`, ADR-0002/0003/0008/0013/0015), and the shipped operator console (`implementation/desktop/crates/selahcue-operator/dist/`).

**Requirement ID range:** this PRD owns **FR-2xx / NFR-2xx / FLOW-2xx / RISK-2xx / METRIC-2xx** (the master PRD owns 0xx/1xx; the Platform PRD owns 5xx). IDs are stable; do not renumber.

**Version house rule (from the research, §5):** Renewed Vision abandoned `7.x` numbering — the current release is **ProPresenter 21.4.2 (2026-07-01)**; `7.16.3` was the last of the 7 line (research E41 — https://www.renewedvision.com/propresenter/download, accessed 2026-08-28). This PRD writes "ProPresenter (v21.x)" or "7.x-era" and never bare "ProPresenter 7"; any version-labelled behaviour is re-verified before it becomes an acceptance criterion. Citations of the form **E01…E42** refer to the evidence register in `docs/research/PROPRESENTER-UI-RESEARCH.md` §2/§5.3, each row carrying URL + access date (2026-08-28).

**Audience:** written so a designer (Uma) can act on each requirement directly — every adopt/adapt item carries the user problem, the interaction pattern, IA/layout implication, states and edge cases, RBAC implication, offline behaviour, accessibility notes, and testable acceptance criteria. Each `FR-2xx` heading in §14 is an intended ticket boundary.

---

## 1. Product vision (of this slice)

SelahCue's operator console already ships a live-first, volunteer-operable 3-zone surface. ProPresenter is the category's power benchmark and the owner's explicit visual reference. This PRD closes the gap **selectively**: adopt the ProPresenter interaction patterns that make dense live operation faster and calmer, adapt the ones that conflict with SelahCue's architecture or volunteer-first posture, and **explicitly reject** the rest with reasons — so the console gains ProPresenter's fluency without inheriting its learning curve, its Mac-first idioms, or any pattern that violates SelahCue's invariants (staging never changes Live; the WebView never renders audience output; offline-first; no failure blanks output; themes are slide-design templates, never colour modes).

## 2. Problem statement

Operators coming from ProPresenter — the market leader — expect specific fluencies the SelahCue console does not yet provide: a service plan with coloured section groups and duration roll-ups; a slide grid whose **view density and thumbnail size the operator controls** (the owner's own annotation singles this out); colour-coded song sections with one-key jumps; at-a-glance per-screen on-air awareness; and per-presentation context (auto-advance, loop, total duration) visible where the slides are. Today SelahCue's plan is a flat list, the slide grid is fixed-density, song sections have no colour or hotkey affordance, and media transport is absent (video render itself is deferred by DEC-003). Meanwhile, several ProPresenter behaviours would be actively harmful to import — live-propagating edits, a mode-switched main surface, per-slide style painting — and this PRD names them as rejections so they are never built by accident.

## 3. Personas and users

Same persona set as the master PRD §3 (`docs/business/PERSONAS.md`). Primarily affected here: **Church Media Operator** (drives the console live), **Worship Leader** (song section jumps, arrangements), **Service Coordinator** (plan structure, durations), **Scripture Operator** (unchanged surfaces), **Stage Manager** (messages/timers — minor), **Mobile Remote User** (read-only mirror implications only). The design target remains the **volunteer** operator (G-4): every adopted pattern must be discoverable without training, with pro depth opt-in.

## 4. Jobs to be done

- **JTBD-U1:** When scanning a long service plan, see at a glance which section (PreShow / Worship / Sermon) I'm in and how long each runs, so I can pace the service.
- **JTBD-U2:** When a song is on screen, jump straight to the chorus (or repeat a verse) in one keypress, so the congregation never waits on me scrolling.
- **JTBD-U3:** When working a dense grid of slides, set the thumbnail size and view mode that fits *my* screen and eyesight, so I can find the right slide fast. *(Owner-annotated priority.)*
- **JTBD-U4:** When mid-service, know instantly which screens are live/enabled — and mute a stream or lower-third feed without leaving the console.
- **JTBD-U5:** When an item has a problem (missing media, no assigned output), see the warning on the item itself before it goes live.
- **JTBD-U6:** When preparing lyrics, edit the whole song as text and have slides regenerate, instead of editing slide boxes one by one.

## 5. Goals

- **G-U1:** Reduce operator time-to-locate (plan item or slide) in a realistic 30-item plan — measured, not asserted (METRIC-201).
- **G-U2:** Ship the owner-flagged slide-grid density controls as the first slice.
- **G-U3:** Every adopted pattern is fully offline, keyboard-operable, and safe under the staging invariant.
- **G-U4:** Give Diego unambiguous ticket boundaries (one FR-2xx heading = one shippable slice) and give Uma per-item states and acceptance criteria.

## 6. Non-goals

- **NG-U1:** Pixel-for-pixel copying of ProPresenter's interface, branding, or iconography (master PRD NG-4). We adopt *patterns*, not pixels.
- **NG-U2:** Rendering audience output in the operator WebView, in any adopted pattern (ADR-0002/0003). All slide thumbnails and previews remain engine-rendered textures/thumbnails streamed to the console.
- **NG-U3:** Any pattern where an edit propagates to the live audience output without Go Live (staging invariant, FR-012).
- **NG-U4:** A ProContent-style bundled/cloud media store (licensing + offline-first conflict; see rejection table and Open Question OQ-3).
- **NG-U5:** A light/dark "theme mode" of any kind — a SelahCue theme remains a slide-design template (`THEME-MODEL-spec.md`).
- **NG-U6:** Text-to-speech (TTS) remains removed (DEC-001); nothing in this PRD touches it.
- **NG-U7:** Multi-screen edge blend, mirror/grouped screen types, and per-layer "Looks" routing stay out of scope (already deferred R2+ with seams noted in `NAV-IA-spec.md` §3).
- **NG-U8:** Planning Center Online (or other planning-service) integration — R6 integrations territory, not this PRD.

## 7. Success metrics

| ID | Metric | Target |
|---|---|---|
| METRIC-201 | Time-to-locate a named slide in a 30-item / 200-slide plan (usability test, volunteer operator) | ≥30% faster than the pre-change console baseline |
| METRIC-202 | Song-section jump: keypress → staged section | ≤150ms (inherits NFR-004 budget) |
| METRIC-203 | View-mode/thumbnail-size preference survives restart | 100% of restarts, offline |
| METRIC-204 | Unintended live-output changes caused by any new UI control | 0 across the QA suite (inherits METRIC-001) |
| METRIC-205 | Memory growth attributable to thumbnail/stacked views over a 12h soak | within the existing METRIC-003 <5% envelope |

## 8. Constraints

- **CON-U1:** WebView = console only; compositor = native wgpu (ADR-0002/0003). Thumbnails come from the engine's read-only preview path (`GetConsoleThumbnails` / `GetScreenFrame` precedent — additive commands, no live-path work).
- **CON-U2:** Staging never changes Live; only Go Live does (FR-012). Every new control is either read-only, staging-scoped, or an explicit live action with the existing confirmation semantics.
- **CON-U3:** Offline-first: every adopted pattern functions with zero network (NFR-015).
- **CON-U4:** One meaning per colour family (UX-CANONICAL): green = staged/safe, red = live/alarm, amber = warning. ProPresenter's screen-toggle colour semantics are **not** importable as-is (its red = "screen off" collides with SelahCue red = "on air") — see FR-214.
- **CON-U5:** Bounded memory: any new thumbnail cache, virtualised list, or preview stream carries an entry-count *and* byte bound plus a bounded-memory test that bites (repo CLAUDE.md bar).
- **CON-U6:** Mobile enforces **4 roles today** (7 designed; expansion tracked `86ajxuf81`/`86ajxufbg`). Nothing here may silently assume 7.
- **CON-U7:** Do not regress the shipped accessible ink: GO LIVE (8.70:1), BLACKOUT (7.19:1), primary (4.72:1) are already WCAG-clear; only `--sc-text-muted` small-type sites are genuinely open (`figma-frames-draw-wcag-failures` finding).

## 9. Assumptions

- **AS-U1:** The owner's screenshot descriptions accurately reflect the reference UI (validated at the gate by the owner).
- **AS-U2:** ProPresenter behaviours differ materially across 6 → 7.x → the current 17–21 majors (research §5); every version-sensitive claim is version-flagged in the research report, and no SelahCue requirement depends on a Pro6-only behaviour. Where a behaviour is documented only for Pro6 (group hotkeys, E42) or only observed in the owner's screenshots (the stacked Show view), the dependent requirement says so.
- **AS-U3:** DEC-003 (live video/audio render deferred) stands; FR-216 (media transport) therefore ships as design + dead-man's UI wiring gated on the media engine, not as a playing scrubber.
- **AS-U4:** The existing keymap (`selahcue_app::keymap`, chords pierce dialogs, double-Esc) is the collision authority for all new shortcuts (FR-211).

## 10. Competitor and category context (summary)

Full evidence: `docs/research/PROPRESENTER-UI-RESEARCH.md` (Rowan, 2026-08-28) §7 + `COMPETITOR-MATRIX.md` + `LIBRARY-ORGANISATION-RESEARCH.md`. The comparator set is Proclaim, EasyWorship, OpenLP, FreeShow, VideoPsalm, Quelea, and — because the brief's "Presenter One" could not be identified as a real product (all plausible domains NXDOMAIN; research §7.1) — **Presenter by WorshipTools as a labelled substitute** (see OQ-9).

- **Category convention (6–7 of 7 — not ProPresenter differentiation):** the library-vs-run-sheet split (7/7), drag reorder (7/7), a one-key go-dark (7/7), clear-text-keep-background (6/7), a stage/confidence display (6/7), labelled song sections (6/7). SelahCue already ships all of these.
- **Genuinely contested (3–4 of 7 — real design decisions):** explicit preview→Go-Live staging (3/7 — OpenLP, Quelea, EasyWorship; **ProPresenter is click-to-live: a Grid View click "will send it to the screen instantly", E02**); thumbnail grid as the primary surface (4/7); an explicit density/thumbnail-size control (4/7, two arranged exactly as ProPresenter's); section hotkeys (4/7 — Proclaim auto-generates them from section labels); first-class arrangements (3/7).
- **Minority patterns:** per-layer clearing (3/7, **ProPresenter's the most developed and its best-loved control** — research §6 T9, §7.5); per-output colour-coded state dots (FreeShow + the owner's screenshot); Proclaim's time-driven service sections; VideoPsalm's operator "freeze".
- **ProPresenter-specific:** the mode-switched toolbar, Looks/Props/Macros as a show-control layer, ProContent in-app store, Reflow, Custom Clear Groups, the House of Worship chrome toggle.

Two research findings frame every call in §13: ProPresenter is effectively **two UIs in one window** — an easy runtime surface and a hard configuration/authoring surface that volunteer curricula simply omit (research §6 T1/§6.4); and its recurring failure modes are **vocabulary and configuration** (Looks, Screen Configuration, undefined Theme-vs-Template), not the live-driving patterns this PRD adopts. SelahCue fills the named gaps and no more.

## 11. User journeys

| ID | Journey | Priority | Acceptance criteria (measurable) | Trace |
|---|---|---|---|---|
| FLOW-201 | Volunteer locates and stages a slide in a long plan using section groups + density controls | MVP | In a 30-item/200-slide test plan, an untrained operator finds a named slide ≥30% faster than baseline; no live change until Go Live | JTBD-U1/U3; METRIC-201 |
| FLOW-202 | Worship leader jumps to the chorus during live | MVP | Press the group hotkey → chorus first slide staged ≤150ms; Go Live commits; audience output never changes on the keypress itself | JTBD-U2; METRIC-202 |
| FLOW-203 | Operator mutes the stream feed mid-service from the console | R2 | Stream screen disabled in ≤2 interactions from the console; main + stage outputs unaffected; state visible in top bar | JTBD-U4; FR-214/215 |
| FLOW-204 | Operator adjusts thumbnail size and view mode; preference survives restart | MVP | Slider + view cluster change layout <100ms; restart restores both, offline | JTBD-U3; METRIC-203 |
| FLOW-205 | Operator sees a missing-media badge on a plan row and fixes it before service | MVP | Badge appears at plan open (FR-007 data); clicking it opens the remediation prompt; badge clears when resolved | JTBD-U5 |
| FLOW-206 | Coordinator restructures lyrics in the text editor; slides regenerate; live is untouched | R2 | Editing text re-paginates slides in preview only; content is never lost (theme model §1); Go Live required to show changes | JTBD-U6 |

## 12. Feature inventory (this PRD)

Plan section groups + duration roll-ups + pinned filter + attention badges (+ placeholder rows later); slide-grid view-density cluster + thumbnail-size slider (owner-flagged); engine-rendered WYSIWYG thumbnails at variable size; stacked plan-ordered "show" view; per-presentation header bar (duration/auto-advance/loop); song group colours + hotkey chips + arrangements; Reflow-style lyric text editor; per-screen on-air indicators + console quick-mute; **per-layer clear cluster** (stacked in composite order, lit-when-active); media transport (design, gated on DEC-003); background-media provenance chip; stage-message tokens; pre-service countdown item; persistent overlay ("prop") layer; operator chrome profile ("Focus mode", later). Rejections in §13.

---

## 13. Adopt / Adapt / Reject — the full table

Verdicts: **ADOPT** (pattern imported, SelahCue-styled) · **ADAPT** (imported with a stated change) · **REJECT** (not built, reason given) · **SHIPS** (SelahCue already has it — listed to stop duplicate tickets). Every notable ProPresenter UI capability from the research report and the owner's screenshots appears once.

| # | ProPresenter capability | Verdict | SelahCue disposition (one-line rationale) | FR |
|---|---|---|---|---|
| 1 | Library vs Playlist split (reusable library referenced by ordered service lists) | SHIPS | Presentations Library + Service Plan already separate; a 7/7 category convention (research §7.3), not a ProPresenter idea; flat-library + strong search beats trees | — |
| 2 | Playlist **section headers** (coloured group dividers: PreShow/Music/…) | ADOPT | Plan section-header item type (FR-002) exists in the model but not the console UI; direct gap | FR-201 |
| 3 | Per-item planned duration + per-section/service roll-up | ADOPT | Master FR-004 requires it; console never surfaced it | FR-202 |
| 4 | Pinned Filter box at the bottom of the playlist | ADAPT | Adopt a plan-scoped filter, but pinned to the plan header (SelahCue's search idiom), not the footer | FR-203 |
| 5 | Warning/status badges on items & thumbnails (missing media, timer, clock) | ADOPT | FR-007 missing-media data exists; surface it where the operator looks | FR-204 |
| 6 | Slide-grid **view-density cluster** (grid / text-only / list) | ADOPT | **Owner-annotated emphasis**; fixed-density grid is a real volunteer pain | FR-205 |
| 7 | **Thumbnail-size slider** | ADOPT | Owner-annotated emphasis; pairs with #6, own control | FR-206 |
| 8 | WYSIWYG engine-rendered slide thumbnails | SHIPS/ADAPT | Console thumbnails exist (read-only engine path); extend to variable sizes without a live-path cost | FR-207 |
| 9 | Stacked "Show" view (all presentations of the playlist in one scroll, per-presentation header bars) | ADAPT | High value, high memory risk — ship virtualised + bounded, R2, never the only view | FR-208 |
| 10 | Per-presentation header controls (total duration, auto-advance badge, loop) | ADAPT | Adopt as read-only badges first; editing stays in the deck editor | FR-209 |
| 11 | Song **group colour-coding** (name on first slide, colour continuation) | ADOPT | Sections exist (FR-019); colour + first-slide labelling is pure UI gap | FR-210 |
| 12 | Group **hotkey chips** (A/C/B letter jumps) | ADOPT | Realises FR-024 quick navigation as a one-keypress *staging* action; a 4/7 contested pattern — Proclaim auto-generates keys from section labels (research §7.4); ProPresenter's version is Pro6-documented only (E42, survival inferred from the owner's screenshot) | FR-211 |
| 13 | **Arrangements** (reorder groups per service without editing the song) | ADAPT | Strong worship feature; per-plan-item group order, later release | FR-212 |
| 14 | **Reflow** bulk lyric/text editor | ADAPT | Adopt as a lyrics-first text pane that regenerates slides via the theme engine (content⟂theme), not a slide-box editor | FR-213 |
| 15 | Toolbar per-screen live-state indicators (Audience/Stage dots) | ADAPT | Adopt the at-a-glance idea; **reject ProPresenter's colour semantics** (its red=off collides with SelahCue red=live) and its **partiality** — ProPresenter's toolbar toggles reflect only system screens, NDI/SDI are always-on and untoggleable (E01), so at-a-glance state is incomplete by design; SelahCue's status covers every registered screen incl. virtual | FR-214 |
| 16 | One-click screen enable/disable from the top chrome | ADAPT | Console quick-mute for secondary feeds only (stream/lower-third); main+stage keep the Screens-page + confirmation path | FR-215 |
| 17 | Media transport (play/pause, ±15s, elapsed/remaining timecode, scrubber) | ADAPT | Design now, wire when DEC-003's media engine lands; transport controls are staging/live-item-scoped | FR-216 |
| 18 | "Blank" slide showing background media filename + duration | ADAPT | Keep SelahCue's layered theme model; show a background **provenance chip** on slide 1 instead of a fake slide | FR-217 |
| 19 | Stage message templates with live tokens (timer/clock in message) | ADAPT | Presets ship; add token substitution | FR-220 |
| 20 | Pre-service countdown item rendering live over a background | ADAPT | Compose existing Timer + theme background into a plan-item type | FR-221 |
| 21 | Props (persistent overlay layer — logo bug/watermark) | ADAPT | Later: one persistent per-screen overlay layer; per-layer clear already exists (FR-078) | FR-219 |
| 22 | Timers panel / bins in the right rail | SHIPS | Timer panel with presets, custom HH:MM:SS, stage scoping already shipped | — |
| 23 | Bible module (reference search, translation picker, live verse display) | SHIPS | Scripture browser + translation + chapter nav + detections already shipped and deeper (AI detection) | — |
| 24 | Global search across libraries (Quick Search) | SHIPS | ⌘/Ctrl+S global presentation search + ⌘K palette already shipped, per the library research recommendation | — |
| 25 | Mode-switched main toolbar (Show / Edit / Reflow modes repurposing the main area) | REJECT | Conflicts with the committed app-menu + surface IA (NAV-IA §1); mode state on the live surface is a mis-trigger risk for volunteers | — |
| 26 | **Click-to-live slide firing** (a Grid View click "will send it to the screen instantly" — E02) and live-propagating edits | REJECT | Violates the staging invariant (FR-012). The category is genuinely split 3/7 (research §7.4): SelahCue sides with OpenLP/Quelea/EasyWorship and **against the owner's reference product** — a load-bearing tension raised explicitly as **OQ-8**, not decided silently | — |
| 27 | Per-slide style copy/paste ("style painter") | REJECT | Conflicts with content⟂theme (THEME-MODEL §1); restyling flows through themes/templates so content is never style-forked | — |
| 28 | ProContent in-app cloud media store | REJECT | Licensing/commercial scope + offline-first conflict; raise as OQ-3, not a UI ticket | — |
| 29 | Looks (per-layer routing per screen) | REJECT (stands) | Already deliberately deferred with a seam (NAV-IA §3); per-screen themes deliver the 80% | — |
| 30 | Mirror / grouped / edge-blend screen types | REJECT (stands) | Pro-AV depth beyond SelahCue's target user; already rejected for MVP in NAV-IA §3 | — |
| 31 | Far-right vertical panel-switcher strip (7+ panels) | REJECT | Panel proliferation vs volunteer-first 3-zone console; right-rail tabs already cover timer/stage/detections | — |
| 32 | Audio bin (audio playlist, shuffle, import drop target) | REJECT (deferred) | Real need but gated on DEC-003 audio; defer wholesale rather than ship a dead bin — revisit with the media engine (OQ-4) | — |
| 33 | Planning Center Online sync | REJECT (stands) | R6 integrations scope (master FR-023/-142 family), not an operator-UI concern | — |
| 34 | Macros / show-control buttons | REJECT (stands) | Master PRD already schedules macros R6 (FR-144); no UI pulled forward | — |
| 35 | Multi-Tracks / click-track integrations | REJECT | Audio-production scope outside SelahCue's product boundary | — |
| 36 | Copy of ProPresenter visual styling (icons, chrome, exact layouts) | REJECT | NG-4 + Design 2.0 is the visual canon | — |
| 37 | **Per-layer clear buttons stacked in on-screen composite order, lit only when their layer is active** | ADOPT | The single best-loved control in the reference product (research §6 T9) and a 3/7 minority pattern where ProPresenter leads the category (§7.5); the control's spatial order *is* the operator's mental model; SelahCue's per-layer clearing (master FR-078) has the engine seam but no console cluster | FR-222 |
| 38 | House of Worship chrome toggle (remove whole feature families from toolbar + menus — E25) | ADAPT | The vendor's own answer to its clutter problem, but it keys on *segment*; SelahCue adapts the idea as an operator-profile chrome simplification keyed on *task depth* (the research shows volunteer curricula omit the hard concepts entirely, §6.4) | FR-223 |
| 39 | Playlist **Templates** with Headers + **Placeholders** (empty slots filled later — E09) | ADAPT | Plan save-as-template/duplicate is master FR-005 (partial today); Headers land via FR-201; Placeholder rows join FR-201's later scope so a weekly service skeleton is reproducible | FR-201 (+ master FR-005) |
| 40 | Announcement layer (an independent content stream with its own destination + green state — E22) | REJECT (deferred) | SelahCue's screen roles + per-screen themes already route different content per screen; a concurrent second content stream (lobby loops) is real but separate scope — revisit with a lobby-loop feature, not as console chrome | — |
| 41 | Bible module's three-way destination (Save as Presentation / Copy to Current / Save to Playlist — E18) | ADAPT | A good pattern at the moment of scripture creation; folds into the existing scripture history/favourites ticket (master FR-031, `86ak0qn2u`) rather than a new FR | — (master FR-031) |
| 42 | Custom Clear Groups (operator-defined layer subsets with icon + colour, 7.7+ — E05) | REJECT (deferred) | Power-user depth on top of #37; ship the fixed per-layer cluster first, revisit only on demand evidence | — |

**Headline counts: 8 ADOPT · 15 ADAPT · 14 REJECT · 5 SHIPS (already built, no ticket).**

**How to read the evidence behind this table.** Three grades, per the research report's own labelling: **(a) cited** — vendor-documented behaviour with an E-number URL (most rows); **(b) screenshot-derived** — present in the owner's screenshots but documented nowhere Rowan could reach: the stacked Show view itself (row 9), the per-presentation header icon roster (row 10), the countdown thumbnail's status badges (row 5's thumbnail placement), and the preview rail's audio meter (research §10.1); **(c) inferred** — group hotkeys surviving past Pro6 (row 12, E42 + screenshot). Screenshot-derived and inferred items are adopted on their SelahCue merits (each maps to an existing master-PRD requirement), not on the strength of ProPresenter documentation — and Uma designs them from SelahCue's model, not from an attempt to clone an undocumented reference.

---

## 14. Functional requirements

Format: `ID | Requirement | Priority | Acceptance criteria | Trace`. Priorities: **MVP** = first UI slice (must), **R2** = second slice (should), **LATER** = could/roadmap. Each FR heading below is one intended ticket. The detailed designer sections follow each table row group.

### EPIC-UI-A — Service plan structure (console left zone)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-201 | Plan section groups: coloured, collapsible section headers grouping plan items | MVP | Section headers render as full-width coloured dividers with name + item count + summed duration; collapse/expand persists per plan; items reorder within and across sections by drag; a plan with no sections renders exactly as today | JTBD-U1; FLOW-201; master FR-002 |
| FR-202 | Duration roll-ups: per-item planned duration, per-section subtotal, whole-plan total | MVP | Item rows show planned duration when set (master FR-004); each section header shows its subtotal; plan header shows the total; unset durations render as "—" and are excluded from sums, with the sum marked "partial" | JTBD-U1; master FR-004 |
| FR-203 | Plan filter: a text filter scoped to the open plan | R2 | Typing filters plan rows (name + kind) <100ms for a 100-item plan; filtered-out rows hide, section headers with no visible children collapse to a count; Esc clears; filter never changes selection or live state | FLOW-201 |
| FR-204 | Attention badges on plan rows and slide thumbnails (missing media, unassigned output, over-long text) | MVP | A plan item whose media is missing (master FR-007 detection) shows a warning badge with an accessible name; the badge opens the remediation prompt; badges clear when resolved; badge state also appears on the item's slide thumbnails | JTBD-U5; FLOW-205 |

**Designer detail — FR-201/202 (plan sections + durations).**
*User problem:* a flat plan list forces re-reading every row to find "where are we"; coordinators cannot pace the service. *Evidence:* ProPresenter playlists carry exactly three element types — **Headers** (section titles), **Placeholders**, and Presentations — saveable as a Playlist Template so a service structure repeats weekly (E09 — https://support.renewedvision.com/hc/en-us/articles/40377194830995, accessed 2026-08-28); the owner's Screenshot A shows Headers in use as the blue "Music" divider. Headers are **inert labels** — Proclaim's time-driven auto-advancing sections are the alternative model, and SelahCue deliberately follows the inert-label side (research §7.5): a section never fires anything. *Pattern:* coloured section dividers inline in the plan list, restyled to Design 2.0 kind-badge language; a gear affordance on the header → rename / recolour / delete-section (items survive, moving to the parent level). *Later scope (with master FR-005 plan templates):* Placeholder rows — a named empty slot ("Sermon deck — add Saturday") that carries the FR-204 attention badge until filled. *IA:* the plan stays in the console left zone; sections are plan data (`plan_item` kind `section` already exists in the model) — no new surface. *States:* empty section (header + "no items" hint); collapsed (chevron + counts); drag-over (insertion line inside or between sections); section with partial durations ("12:30 · partial"); recovery (collapse state restored after crash per FR-074 autosave). *Edge cases:* deleting a section never deletes items; the live item's section cannot visually hide the ON-AIR row — collapsing a section containing the live item keeps a live-chip stub visible. *RBAC:* desktop-only editing; the mobile plan view (Observer+) renders sections read-only — 4-role model unchanged. *Offline:* pure local data. *Accessibility:* headers are real `role="heading"`/group semantics; colour is never the only cue (name + count text); AA contrast on divider ink using existing tokens; keyboard: arrow navigation enters/skips collapsed groups, `←/→` collapse/expand. *No regression:* plan-row live/staged chips keep their shipped ink.

**Designer detail — FR-203 (plan filter).** *Pattern:* a search field in the plan panel header (not ProPresenter's footer pin — SelahCue's search affordances live in headers; also keeps it clear of the emergency footer). *States:* idle (placeholder "Filter plan"), active (count "6 of 32 items"), no-match ("nothing matches — clear"), cleared. *Edge:* the live item always stays visible with its section stub even when filtered out — never let the filter hide what is on air. *A11y:* `role="searchbox"`, results count in an `aria-live` region; `Esc` clears then returns focus per the existing keymap (no collision: verify against `selahcue_app::keymap`).

**Designer detail — FR-204 (attention badges).** *Pattern:* small leading badges (⚠ amber for missing media / unassigned output; ⏱ info for timers/auto-advance) on plan rows and slide thumbnails; click → the existing remediation UI (pre-service check for media). *States:* warning, resolved (badge disappears), multiple issues (one badge + count, details on open). *Edge:* badge computation is background/cancellable (master FR-084) — a slow media scan never delays plan rendering. *A11y:* icon + text tooltip + accessible name ("Missing media: filename"); amber pairs with a shape, never colour alone.

### EPIC-UI-B — Slide grid, view density & stacked view (owner-flagged)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-205 | View-density cluster on the slide grid: Grid / Text-only / List modes | MVP | A segmented control on the slides panel switches modes <100ms without re-fetching thumbnails; Text-only renders slide text lines (no thumbnails); List renders one row per slide (number, group, first line, badges); the staged and live slides stay visibly marked in every mode | JTBD-U3; FLOW-204; owner annotation |
| FR-206 | Thumbnail-size slider with persisted per-operator preference | MVP | A slider (min 4 / max 12 columns-equivalent) rescales the grid live; the value and view mode persist locally and restore on restart offline; keyboard `-`/`+` equivalents exist on the focused control | JTBD-U3; METRIC-203; owner annotation |
| FR-207 | Variable-size engine thumbnails without live-path cost | MVP | Thumbnails re-render at the new size via the read-only preview path; resizing during live playback causes zero dropped frames on the audience output (fault-injection verified); thumbnail cache is entry- and byte-bounded with an LRU test that bites | CON-U1/U5; NFR-203 |
| FR-208 | Stacked plan view: all plan presentations in one virtualised scroll, in plan order | R2 | A "Plan view" toggle shows every presentation stacked with its header bar; scrolling a 50-item plan stays smooth (no unbounded DOM/memory — bounded test); the current deck view remains available and default; selection/staging behaviour identical in both views | JTBD-U1; RISK-201 |
| FR-209 | Per-presentation header bar: total duration, auto-advance badge, loop indicator (read-only) | R2 | Each presentation's header in stacked view shows summed duration, an auto-advance chip when configured (existing transition/auto-advance data), and a loop chip; controls navigate to the deck editor rather than editing inline | JTBD-U1; FLOW-201 |

**Designer detail — FR-205/206 (the owner-annotated cluster).** *User problem:* one fixed grid density serves nobody — a 13" laptop volunteer wants big legible thumbnails; a power operator on a 27" display wants 10 columns. The owner drew an arrow at exactly this cluster: treat it as the first slice shipped. *Evidence (research §4.3):* the reference cluster — three view buttons + a three-dot per-view options menu + a size slider, bottom-right of the Slide View Area — is documented as strictly **output-neutral** (E02 — https://support.renewedvision.com/hc/en-us/articles/360041344174, accessed 2026-08-28); the idiom repeats in at least four places in ProPresenter incl. its mobile Remote (E23); a named reviewer ties the text-forward view to operator legibility in a dark booth (ChurchTechToday, 2020-01-22); and the vendor invested again **five months ago** — v21.3 (2026-03-18) added View-menu switching with per-view custom key bindings (E41). The category ships a density control in 4/7 comparators (research §7.4) — a strong pattern, not a requirement. *Naming:* ProPresenter's own two current articles disagree on the view names ("Grid, Table, Easy" vs "Grid, Easy, Outline" — E02 vs E01); SelahCue deliberately names its own modes **Grid / Text / List** rather than importing unstable vendor vocabulary. *Four decisions ProPresenter leaves undocumented, which SelahCue defines rather than copies (research §10.1):* **scope** — the preference is per-operator per-surface (Slides tab vs Library), not per-presentation; **persistence** — settings table, restored on boot (NFR-201); **slider** — stepped across the quantised thumbnail tiers of FR-207, not continuous; **group-rows** — a "one row per group" toggle lives in the options menu and applies to Grid and List alike. *Pattern:* bottom-right of the slides panel, a compact cluster — `[⊞ grid] [≡ text] [☰ list] · [⋯ options] · [size ————○—]` — mirroring the shipped segmented-control component (Design 2.0 §4). *IA:* lives in the slides panel footer of both the Slides tab and the Presentations Library grid; one shared component, one preference store (`localStorage`-class local persistence is not enough if the console webview resets — persist via the existing settings table, per-host). *States:* grid (default), text-only (lyrics scanning — the use-case worship leaders love), list (dense audit view with badges), group-rows on/off, slider at min/max (clamped with a tick), restored-on-boot. *Could (not required):* a hold-key peek of Text view from Grid, ProPresenter's `~` Easy View gesture (E02) — only if it costs nothing against the keymap. *Edge cases:* text-only mode for an image-only slide shows the slide number + "image slide" hint, never an empty row; extremely long lines ellipsize with full text on hover/focus; the staged (green frame) and live (red frame) markers must survive every mode — in list mode they become row chips with labels. *RBAC:* none (desktop operator surface). *Offline:* fully local. *A11y:* the cluster is a labelled `radiogroup` + slider with `aria-valuetext` ("6 columns"); frames-as-state always pair with text chips (STAGED / ON AIR) per WCAG 1.4.1; existing GO LIVE/BLACKOUT ink untouched. *Acceptance criteria are the FR rows above plus:* switching mode never changes selection, staging, or live state (METRIC-204).

**Designer detail — FR-207 (thumbnails).** The engine already serves clamped read-only thumbnails (`GetConsoleThumbnails` / `GetScreenFrame`, ≤480×270). Variable size stays within a fixed set of quantised sizes (e.g. 3 tiers) so the cache stays bounded: `tiers × visible slides` entries max, LRU-evicted, with a per-key hit accessor and a compile-pinned cap per the repo's bounded-memory test bar. Never request per-pixel-perfect sizes per slider tick — quantise, then CSS-scale between tiers.

**Designer detail — FR-208/209 (stacked view).** *User problem:* "one deck at a time" hides service context; the owner's reference shows the whole service's slides stacked in playlist order. *Evidence honesty (research §3.3, §10.1):* the stacked multi-presentation scroll is **screenshot-derived — no vendor article documents it**; the per-presentation header's icon roster (auto-advance badge, loop, split/columns) is likewise undocumented. Uma therefore designs both from SelahCue's own plan/deck model, treating the screenshot as intent, not spec. *Adaptation:* SelahCue ships it as an *optional* view (toggle in the plan header), virtualised — only presentations near the viewport hold rendered thumbnails; far items render as header bars + placeholder rows. *States:* loading placeholders, section dividers inline (FR-201 headers appear in the stack, exactly the ProPresenter blue-bar pattern), live presentation pinned-highlight, collapsed presentation (header only), empty plan. *Edge:* staging via click in the stack behaves identically to the deck view; auto-scroll-to-live is a button, never automatic while the operator is scrolling (respect scroll intent). *RBAC/offline:* as above. *A11y:* virtualisation must keep a coherent accessibility tree (announce "Presentation 3 of 11, Good Grace, 20 slides"); keyboard paging Home/End/PgUp/PgDn per presentation.

### EPIC-UI-C — Songs: groups, hotkeys, arrangements, Reflow-style editing

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-210 | Song section group colour-coding on slides (label on first slide, colour continuation on the rest) | MVP | Each section (Verse/Chorus/Bridge/Tag/…) has a colour from a fixed accessible palette; the first slide of a group shows the group name + colour; continuation slides show the colour bar only; colours are consistent across grid/text/list/stacked views and the mobile read-only plan view | JTBD-U2; master FR-019 |
| FR-211 | Group hotkeys: single-key jump-to-section that stages (never goes live) | MVP | Pressing a group's key stages that group's first slide ≤150ms; chips show the key on the first slide of each group; keys are auto-assigned (V1→A convention configurable later), collision-checked against the canonical keymap; the action never changes live output (Go Live commits) | JTBD-U2; FLOW-202; master FR-024 |
| FR-212 | Arrangements: per-plan-item section order (e.g. V1 C V2 C C) without editing the song | LATER | A plan item referencing a song can carry its own ordered group sequence; the library song is unchanged; the slide views render the arranged order; deleting an arrangement reverts to song order | JTBD-U2; master FR-019 |
| FR-213 | Lyrics-first text editor: edit the whole song as text; slides regenerate via the theme engine | R2 | A text pane shows the song as labelled sections; editing re-paginates slides in preview with zero content loss (content⟂theme); markers define section splits; changes never touch live until Go Live; undo ≥20 steps (master FR-016) | JTBD-U6; FLOW-206 |

**Designer detail — FR-210/211 (groups + hotkeys).** *Evidence:* group tokens are colour-matched to the group from 7.3 (E03 — https://support.renewedvision.com/hc/en-us/articles/360041809973, accessed 2026-08-28); labelled sections are a 6/7 category convention while section *hotkeys* are contested 4/7, with **Proclaim's auto-generated model the closest analogue** — keys derived from section labels (C for chorus, B for bridge) and displayed on the slide (research §7.4). ProPresenter's own hotkey mechanism is documented only in a Pro6-era article (E42) and its survival is inferred from the owner's screenshot chips — SelahCue builds the feature on master FR-024's merits, not on that inference. *Pattern:* the reference's strongest worship idiom, restyled: a coloured footer band on each slide card (group name only on the first slide) + a small key chip on the group's first slide. *Colour system decision for Uma:* a fixed 6-colour section palette drawn from Design 2.0 (not user-assignable in v1) — verse/chorus/bridge/tag/pre-chorus/other — every pairing AA against card backgrounds, and colour never alone (the group name text + chip letter carry the meaning). **Do not reuse the broadcast status colours** (live-red / preview-green / warn-amber) for groups — that would break the one-meaning-per-colour canon; use distinct hues (e.g. blue/violet/purple family + neutrals). *Hotkey states:* idle chip; pressed (stages + chip flash); conflict (a key already taken by the canonical keymap is never assigned — next free letter); hotkeys inactive while a text input/search is focused (existing keymap rule). *Edge:* two groups with the same name ("Chorus" ×2) get distinct keys; a song with >26 groups falls back to no chips beyond the limit (badge "no key"). *RBAC:* mobile Worship-Leader-capable roles inherit the same *jump* as a staged request when the 4-role model's equivalent (Producer path today) permits — flag: do **not** design against the 7-role matrix (CON-U6). *A11y:* chips carry `aria-keyshortcuts`; the jump announces "Staged: Chorus 1" via the existing aria-live scene payload.

**Designer detail — FR-213 (lyrics-first editor).** *Adaptation vs Reflow:* Reflow edits slide text in place; SelahCue's version edits the **song source text** and lets the theme engine re-paginate (verses-per-slide config, ShrinkToFit per THEME-MODEL §4) — this keeps content⟂theme and makes overflow structurally impossible to lose. *IA:* a pane in the deck/song editor surface (not the live console). *States:* editing (dirty marker + autosave), re-paginating (brief), overflow-warning (region badge, never truncation), conflict (song edited elsewhere — last-writer-wins with a visible notice, consistent with host arbitration). *A11y:* a real `textarea`/content-editable with full AT support; section labels as headings.

### EPIC-UI-D — Outputs: on-air awareness & quick mute

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-214 | Top-bar per-screen status: one dot + label per enabled screen, SelahCue colour semantics | MVP | The console top bar lists each enabled screen (Main, Stage, Stream, L3) with a state dot: **red = rendering live content, neutral/dim = enabled-idle, amber = fault/mismatch, struck = disabled**; every dot has a text label; clicking routes to the Screens page; state updates ≤1s after a screen change | JTBD-U4; NAV-IA §4; CON-U4 |
| FR-215 | Console quick-mute for secondary feeds (stream / lower-third) | R2 | From the top-bar status a permitted operator disables/enables a *secondary* screen in ≤2 interactions with an inline confirm; Main and Stage cannot be disabled from this control (Screens page only); the action is audit-logged (master FR-150) and reflected on the Screens page and mobile mirror ≤1s | JTBD-U4; FLOW-203; DEC-002 |

**Designer detail — FR-214/215.** *Evidence:* ProPresenter's toolbar Audience/Stage buttons toggle **system screens only — NDI/SDI screens are always on and cannot be toggled** (E01 — https://support.renewedvision.com/hc/en-us/articles/360041345954, accessed 2026-08-28), so its at-a-glance state is partial by design; Screen Configuration is the research's #1 volunteer failure point, cited 2019→2025 (research §6 T2). FreeShow is the comparator precedent for full per-output colour-coded status dots (research §7.5). SelahCue's status covers **every registered screen including virtual feeds** — a deliberate improvement, not a copy. *The semantics trap (this is the reason this is ADAPT, not ADOPT):* in the owner's screenshot, ProPresenter shows Audience as a **red hollow ring meaning OFF** and Stage as **green meaning ON**. Importing that reads catastrophically in SelahCue, where red already means *on air* and green means *staged/safe*. Uma must design to UX-CANONICAL: red dot = this screen is showing live content; disabled = struck-through/dimmed with an "off" label; amber = the existing mismatch state (NAV-IA §4). *States per screen:* live, enabled-idle (blackout counts as idle-black + BLACKOUT chip), disabled, fault/mismatch, identify-active. *Quick-mute guard rails:* secondary feeds only; inline confirm ("Mute Stream? The stream sees black — audience unaffected"); blackout remains the emergency path for main. *RBAC:* desktop console is the authoritative operator; the mobile mirror shows status read-only for all roles, and any future mobile mute follows the 4-role model's ConfigureOutputs equivalent — do not assume 7 roles. *Offline:* pure local. *A11y:* dots pair with labels; `aria-pressed` on the mute; state changes announced politely; contrast per tokens (no new ink).

### EPIC-UI-E — Media surfaces (gated on DEC-003)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-216 | Media transport UI: play/pause, ±15s skip, elapsed/remaining timecode, scrubber — designed now, functional when the media engine lands | R2 | The design ships states for: no-media, loading, playing, paused, scrub-preview, near-end warning; wiring activates against the DEC-003 media engine when built; until then media plan items show duration metadata only (no dead controls rendered) | JTBD-U1; AS-U3; DEC-003 |
| FR-217 | Background-media provenance chip on slide 1 of a themed deck (filename + duration badge) | R2 | A deck whose theme uses an image/video background shows a compact chip on its first slide (asset name + duration when video); the chip opens the theme's background editor; a missing background asset raises the FR-204 badge | JTBD-U5; THEME-MODEL §2 |
| FR-219 | Persistent overlay layer ("prop"): one per-screen watermark/logo overlay that survives slide changes | LATER | An overlay can be shown/hidden per audience-class screen; it persists across slide changes and clears via the existing per-layer clear (master FR-078); it never appears on the stage display; opacity/position come from a theme template | master FR-049/078 |
| FR-220 | Stage-message tokens: dynamic values in stage message presets | R2 | Presets support `{timer}`, `{clock}`, `{overrun}` tokens rendered live on the stage output; token rendering follows the stage theme; a preset with an unresolvable token shows a preview warning before send | master FR-162 |
| FR-221 | Pre-service countdown plan item: a countdown composed over a theme background | R2 | A countdown item targets selected audience screens, renders the timer over the theme background via the engine, auto-advances (optional) at zero to the next item, and never flashes (FR-175 bounds); the console thumbnail shows a static badge, not a live-rendering thumbnail | master FR-054/059; FLOW-001 |

**Designer detail — FR-216 (transport).** *Sequencing honesty:* DEC-003 defers live video/audio render; the console must not grow dead controls. The ticket is **design + component build behind the media-engine capability flag**: when the engine reports no playback capability, media items render metadata rows (name, duration, badges) with no transport. When capability arrives, the transport appears in the right rail (the shipped rail already reserves the monitor + panel slot; do not add a new zone). *Scrubber rule:* scrubbing a **staged** item previews freely; scrubbing the **live** item is a live action and follows live-action affordances (distinct ink + confirm-free but clearly framed in live-red context). *A11y:* transport buttons ≥ existing hit sizes, `aria-valuetext` timecodes ("30 seconds elapsed, 29 remaining").

**Designer detail — FR-221 (countdown item).** *Evidence:* in the reference product an **audience**-screen countdown is not a first-class object — it is composed from three objects, a Timer + a Theme text box + a Message with a binding token (E15 — https://support.renewedvision.com/hc/en-us/articles/360050786794, accessed 2026-08-28) — while a **stage** countdown is a prebuilt object with progressive Color Triggers (E14). SelahCue makes the audience countdown a **first-class plan item** precisely to avoid that three-object composition; threshold colour changes map onto the existing timer warning thresholds (master FR-057), never onto flashing. *Adaptation:* ProPresenter renders a live countdown inside the slide thumbnail (screenshot A shows it, plus warning/clock badges — the badges themselves are screenshot-derived, undocumented). SelahCue explicitly does **not** live-render thumbnails in the console (CPU discipline, NFR-011); the thumbnail carries a static clock badge + the configured duration, and the *monitors* (preview/live) show the real render. States: scheduled, running, zero (TIME UP semantics per master FR-059 — solid, ≤0.5Hz pulse), overrun, dismissed.

### EPIC-UI-F — Live control: per-layer clear cluster & chrome simplification

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-222 | Per-layer clear cluster: one clear button per output layer, stacked in on-screen composite order, lit only when its layer is active | R2 | The console shows a vertical clear cluster beside the Live monitor with one button per layer (text, media/background, lower-third, overlay) in the same top-to-bottom order the engine composites them; a button is enabled/lit **only** while its layer has live content; pressing it clears exactly that layer <200ms offline (master FR-076/078); CLEAR ALL and BLACKOUT stay in the emergency footer unchanged; every clear is audit-logged | research §6 T9; master FR-078; DEC-002 |
| FR-223 | Operator chrome profile: a "Focus" setting that hides authoring/config surfaces from the console chrome for a service | LATER | A per-host setting collapses non-runtime chrome (Theme Designer, Screens management, detections tuning) behind the app menu with a visible "Focus mode" chip; live driving, emergency controls, and all keyboard chords are unaffected; turning it off restores everything; nothing is permission-gated by it (it is a view preference, not RBAC) | research §6 T1/T5/§6.4; E25 |

**Designer detail — FR-222 (per-layer clear cluster).** *User problem:* clearing *just the text* while a background keeps playing (or dropping a lower-third while lyrics stay) currently has no one-press console affordance; the emergency footer offers only the blunt CLEAR ALL / BLACKOUT. *Evidence:* the per-layer clear cluster is the **best-loved control** in the reference product (research §6 T9 — Churchfront, https://churchfront.com/2025/12/09/propresenter-crash-course-for-churches/, accessed 2026-08-28), and its documented virtue is spatial: the buttons stack in the same order the layers composite on screen, so the control's arrangement *is* the output's mental model (E01/E05). Only 3/7 category products have per-layer clearing at all — this is one of the few places the reference leads its category. *Pattern for Uma:* a compact vertical strip adjacent to the Live monitor; each button = layer glyph + label; **lit/enabled only when that layer is live** (ChurchTechToday corroborates the lit-when-active behaviour as a loved detail); order pinned to the engine's composite order — never alphabetical, never configurable in v1 (Custom Clear Groups are explicitly deferred, table #42). *States:* inactive (dimmed, disabled), active (lit, enabled), pressed (clears + brief confirmation flash), all-inactive (whole cluster quiet — blackout state shows BLACKOUT chip instead). *Edge cases:* clearing the last visible layer is not blackout — the output shows the theme background per the engine's layer model; a clear during blackout queues nothing (rejected, consistent with existing blackout semantics). *RBAC:* desktop console operator is authoritative; the mobile mirror follows DEC-002 (`Clear` is Producer+ on the 4-role model). *Offline:* fully offline (master FR-076). *Dependency:* the per-layer clearing engine follow-up (`86ajpy59e`) must land first; this ticket is the console surface for it. *A11y:* each button has an accessible name naming the layer and its state ("Clear lower-third — active"); state change announced; ≥ existing hit sizes; layer colours never the only cue.

**Designer detail — FR-223 (chrome profile).** *User problem:* the research's strongest sentiment finding is a two-tier curve — running a prepared service is easy, configuration is hard — and the industry's answer is to *not teach* volunteers the hard surfaces at all (a real volunteer curriculum omits Looks, Screen Config, Themes, Props and Macros entirely — research §6.4). *Evidence:* ProPresenter ships a segment-keyed version of this (the House of Worship toggle strips Bible/SongSelect/PCO chrome — E25); SelahCue adapts it as **task-depth-keyed**, which the evidence actually points at. *Pattern:* one toggle in Settings (and the app menu) — not per-role, not per-user-account; a visible chip so an operator knows why a surface is "missing"; every hidden surface stays one app-menu click away (hidden, never locked). *Non-goal:* this is not RBAC and must never be presented as a security boundary. LATER: ships only after the MVP slice proves itself; raised now so Diego can park it as a backlog ticket rather than lose it.

---

## 15. Non-functional requirements

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| NFR-201 | View preferences persist per host, offline, and restore fast | MVP | Density mode + slider tier restore on boot <100ms with network disabled; stored via the settings table (not volatile webview storage alone) | METRIC-203 |
| NFR-202 | Bounded memory for every new cache/virtualised view | MVP | Thumbnail tiers and stacked-view row pools carry entry-count + byte caps, compile-pinned premises, per-key hit accessors, positive controls, and mutation-verified tests per the repo bounded-memory bar; 12h soak stays in the METRIC-003 envelope | CON-U5; METRIC-205 |
| NFR-203 | Zero live-path cost from console UI work | MVP | Thumbnail re-render, density switching, stacked-view scroll, and badge computation cause no audience-output frame drops under the ADR-0015 fault-injection/perf harness | NFR-024; CON-U1 |
| NFR-204 | Keyboard + AA accessibility on all new controls, no ink regression | MVP | Every new control keyboard-operable (NFR-019); all new fg/bg pairs AA (≥4.5:1 / ≥3:1 large) via the token audit tests; shipped GO LIVE/BLACKOUT/primary contrast values unchanged; colour never the only cue | CON-U7; NFR-020 |
| NFR-205 | Hotkey and interaction latency inside existing budgets | MVP | Group-hotkey staging ≤150ms (NFR-004 budget); density/mode switch <100ms; per-screen status update ≤1s | METRIC-202 |
| NFR-206 | Cross-platform parity of every adopted pattern | MVP | New console behaviour passes the existing WebKit + Chrome headless gates and the 3-OS CI matrix (WKWebView layout traps checked per the known select/grid pitfalls) | NFR-014 |

## 16. Permissions

The operator console is the authoritative **desktop** surface: none of these features add mobile capabilities. RBAC implications are limited to: (a) FR-215 quick-mute maps to the existing `ConfigureOutputs` permission and is audit-logged (master FR-150); (b) FR-222 per-layer clears follow DEC-002 — `Clear` is Producer+ on the current 4-role model wherever mirrored to mobile; (c) mobile mirrors (plan sections FR-201, group colours FR-210, screen status FR-214) are **read-only views** available to all paired roles under the **current 4-role model** — nothing here presumes the 7-role expansion (tracked `86ajxuf81`); (d) group-hotkey jumps from mobile, if later exposed, ride the existing content-advance permission, not a new one; (e) FR-223's Focus mode is a view preference and must never be presented or implemented as a permission boundary. Server-side deny-by-default enforcement (master FR-090) is unchanged. Note the research corroborates native RBAC as a SelahCue differentiator: no role or permission model is documented on either ProPresenter remote surface (research §3.13 — still an inference, labelled as such).

## 17. Data lifecycle

New persisted data, all local SQLite (additive migrations, forward-only): plan section metadata (name, colour, collapsed) on the existing `plan_item` section kind; per-plan-item arrangement order (FR-212); operator view preferences (density mode, thumbnail tier) in the settings table; stage-message token presets. Nothing here leaves the host; exports of plans include sections/arrangements (master FR-139 bundle format extends additively). Thumbnails are derived, cache-only data — never persisted, always regenerable.

## 18. AI and detection surfaces

No new AI behaviour. The Detected Scriptures panel, transcript, and detection pipeline are untouched; the invariant that **AI assists but never gates core controls** (master FR-083) is preserved — every adopted pattern here is operable with AI subsystems absent or failed. Group hotkeys, density controls, and screen status have no AI dependency. (Heading retained for validator parity; see master PRD §18 for the provider architecture.)

## 19. Offline behaviour

Every FR in this PRD is fully functional with zero network (NFR-015): plan sections, density preferences, hotkeys, badges, screen status, countdown items are local. The only network-adjacent item, FR-216's transport, is gated on the local media engine — not on connectivity. ProContent-style cloud browsing is rejected (NG-U4) partly for exactly this reason.

## 20. Security

No new attack surface: no new wire commands beyond additive read-only/preview and the FR-215 mute (which reuses the existing `SetScreenEnabled` command + RBAC + audit). No new input parsing beyond the plan filter (local, length-bounded input). Token substitution in FR-220 is a fixed allowlist (`{timer}`, `{clock}`, `{overrun}`) — no template language, no injection surface. All new persisted fields ride the existing SQLCipher-capable store.

## 21. Privacy

No new data classes, no telemetry, no cloud egress. Operator view preferences are local configuration. Nothing in this PRD touches transcripts, audio, or sermon data.

## 22. Accessibility

Summarised per-FR above; binding rules: WCAG 2.1 AA contrast on every new pairing via the token audit tests (NFR-204); colour never the only cue (group colours pair with names/letters; status dots pair with labels); full keyboard paths incl. group hotkeys, density cluster, quick-mute; `aria-live` announcements for staging changes ride the existing structured live-scene payload (NFR-021); reduced-motion honoured (no new animation is essential); the countdown item obeys the FR-175 flash bounds. **Regression guard:** the shipped accessible ink on GO LIVE (8.70:1), BLACKOUT (7.19:1) and primary (4.72:1) is pinned — building "pixel-perfect to Figma" is explicitly *not* the bar where Figma is behind the shipped console.

## 23. Reliability

All new UI is read-only or staging-scoped except FR-215 (guarded, audited) — METRIC-204 requires zero unintended live changes. Thumbnail and stacked-view work is isolated from the render path (NFR-203) and fault-injection-verified via the ADR-0015 seam. Badge scans are cancellable background work (master FR-084). Crash recovery restores collapse state, view preferences, and arrangements with the plan (master FR-074/075).

## 24. Performance

Budgets in §15: ≤150ms hotkey staging, <100ms density switch, ≤1s status propagation, bounded caches, 12h-soak clean. The stacked view (FR-208) is the only structurally risky item and is R2-gated behind its virtualisation design; it must be measured against a 50-item / 500-slide synthetic plan before ship (RISK-201).

## 25. Licensing

Nothing here bundles third-party content. The ProContent rejection (table #28) is partly a licensing decision: an in-app content store implies redistribution licensing SelahCue has not acquired (master PRD §25, CON-3-adjacent) — raised as OQ-3 for the owner rather than decided. Adopting *patterns* while rejecting ProPresenter's visual identity keeps NG-4 (no pixel-copying) intact. No new fonts, codecs, or SDKs.

## 26. Risks

| ID | Risk | Mitigation |
|---|---|---|
| RISK-201 | Stacked view (FR-208) unbounded memory / jank on large plans | R2 gate; virtualisation design + bounded-memory tests + synthetic-plan benchmark before ship |
| RISK-202 | Colour-semantics confusion importing ProPresenter idioms (red=off vs red=live) | FR-214 explicitly re-maps to UX-CANONICAL; design review checklist item; QA scenario |
| RISK-203 | Scope creep toward cloning ProPresenter (NG-U1/NG-4) | The rejection table is normative; new "ProPresenter has X" asks route through PRD change, not tickets |
| RISK-204 | Hotkey collisions with the canonical keymap (chords pierce dialogs) | FR-211 auto-assignment is collision-checked against `selahcue_app::keymap`; keymap tests extended |
| RISK-205 | Design 2.0 Figma frames lag the shipped console (known contrast finding) | NFR-204 pins shipped ink; Uma designs from the live console + tokens, Figma updated after |
| RISK-206 | Version-stale or undocumented reference claims mislead a design (the product is at v21.x while repo docs say "7"; several screenshot elements are documented nowhere) | The version house rule (header) + the evidence-grade note in §13; no FR depends on a Pro6-only or undocumented behaviour — each maps to a master-PRD requirement on its own merits (AS-U2) |

## 27. Dependencies

- **Rowan's research report** `docs/research/PROPRESENTER-UI-RESEARCH.md` — evidence base for the table in §13.
- **DEC-003** (media engine deferred) gates FR-216's functional wiring; **FR-217/221** depend on the shipped theme background + timer engines (present).
- **Existing seams:** read-only thumbnail commands (`GetConsoleThumbnails`/`GetScreenFrame`), screen registry (`SetScreenEnabled` + RBAC), plan `section` item kind, keymap module, settings table, per-screen themes.
- **FR-222** depends on the per-layer clearing engine follow-up (`86ajpy59e`, master FR-078) landing first.
- **Owner gate approval** of this PRD → Diego (delivery) cuts ClickUp tickets in the SelahCue list → Uma (design) picks up per-FR.
- Mobile 4→7 role expansion (`86ajxuf81`) is *not* a dependency — everything here is 4-role-safe (CON-U6).

## 28. Open questions (owner decisions — raised, not decided)

- **OQ-1 — Default view density:** should Grid remain the default for new operators, and at which thumbnail tier? (FR-205/206 ship with grid + middle tier unless directed.)
- **OQ-2 — Arrangements priority:** FR-212 is scoped LATER; the owner may want it pulled into R2 alongside FR-213 (they share the song-model work). Worship-heavy churches feel this gap most.
- **OQ-3 — Content marketplace:** ProContent is rejected as a UI ticket, but does SelahCue ever want a curated (licensed) media pack store as a commercial feature? Platform-PRD territory if yes.
- **OQ-4 — Audio bin:** rejected-deferred pending DEC-003; when the media engine lands, does an audio playlist bin enter R2 scope or stay out?
- **OQ-5 — Screen-status live semantics:** confirm the FR-214 mapping (red dot = screen rendering live content; struck = disabled). An alternative reading (dot = enabled/disabled only) is simpler but loses on-air awareness.
- **OQ-6 — Stacked view default:** if FR-208 tests well, should it become the default plan-driving view (ProPresenter's default) or stay opt-in? Ship opt-in first regardless.
- **OQ-7 — Group hotkey letters:** auto-assigned only (v1) vs user-assignable per song. V1 ships auto-assigned (Proclaim's model, research §7.4); confirm.
- **OQ-8 — Staging invariant vs the reference's click-to-live model:** ProPresenter fires a slide the instant it is clicked (E02); SelahCue's core invariant stages first and commits on Go Live, siding with the 3/7 category minority **against the owner's reference product** (research §7.6). My recommendation: **keep the invariant** — it is architectural (FR-012, `selahcue-present`), it is the safety story, and the speed cost is mitigated by ⏎ Go Live; if the owner wants more speed, a *double-click = stage + Go Live* accelerator can be designed without breaking the invariant. This is flagged rather than silently decided because the owner's reference behaves the other way.
- **OQ-9 — "Presenter One" identity:** the brief's seventh comparator could not be identified as a real product (research §7.1); Presenter by WorshipTools was substituted, labelled as such. Confirm the intended product; if it is something else, the comparator baseline gets one follow-up pass.

## 29. Acceptance criteria (conventions)

As master PRD §29: every FR/NFR row's Acceptance criteria column is the normative, testable pass condition; subjective wording is banned; UI latencies are measured on Tier-A reference hardware; "no live change" claims are verified through the ADR-0015 seam (fault injection + pixel readback), not visual inspection. A requirement is met only when its criteria pass with evidence and independent verification (the four-reviewer pipeline for implementation tickets).

## 30. MVP (first slice of this PRD)

**Slice 1 (must):** FR-205, FR-206, FR-207 (the owner-annotated density cluster + slider + variable thumbnails) · FR-201, FR-202 (plan sections + durations) · FR-204 (attention badges) · FR-210, FR-211 (group colours + hotkeys) · FR-214 (screen status re-semanticised) — with NFR-201…206 binding. Rationale: highest owner signal (annotation), pure-console work on existing seams, zero architectural risk, every item offline + 4-role-safe. Note "MVP" here means *first slice of this UI uplift*, sequenced after the product-gap-audit blockers — it does not amend the master PRD's product-MVP boundary.

## 31. Later releases

- **R2 (should):** FR-203 (plan filter), FR-208/209 (stacked view + headers), FR-213 (lyrics-first editor), FR-215 (quick-mute), FR-216 (transport, engine-gated), FR-217 (provenance chip), FR-220 (message tokens), FR-221 (countdown item), FR-222 (per-layer clear cluster — first among the R2 items if `86ajpy59e` lands early; it is the strongest sentiment-backed item in the research).
- **LATER (could):** FR-212 (arrangements — see OQ-2), FR-219 (persistent overlay/prop layer), FR-223 (chrome profile / Focus mode).
- Revisit-on-decision: OQ-3 (content packs), OQ-4 (audio bin).

## 32. Launch criteria (this PRD's slices)

A slice ships when: its FR acceptance criteria pass with evidence on all three OSes (NFR-206); METRIC-204 records zero unintended live changes across the slice's QA suite; bounded-memory tests exist and are mutation-verified for every new cache (NFR-202); the token/contrast audit passes with shipped ink unchanged (NFR-204); the Chrome + WebKit headless gates and `make ci` are green; and the four-reviewer pipeline has cleared each implementation ticket.

## 33. Traceability

Every FR in this PRD maps to exactly one slice:

**MVP (slice 1):** FR-201, FR-202, FR-204, FR-205, FR-206, FR-207, FR-210, FR-211, FR-214
**R2 (slice 2):** FR-203, FR-208, FR-209, FR-213, FR-215, FR-216, FR-217, FR-220, FR-221, FR-222
**LATER:** FR-212, FR-219, FR-223

**NFRs (cross-cutting, bind from slice 1):** NFR-201, NFR-202, NFR-203, NFR-204, NFR-205, NFR-206.
**FLOWs:** FLOW-201…206. **RISKs:** RISK-201…206. **METRICs:** METRIC-201…205.
Master-PRD traces are inline per row (FR-0xx/1xx references). Requirement→ticket mapping is created by Diego post-gate; requirement→test mapping lands with the tickets.

---

*End of Operator UI PRD v1.0 (draft). Gate: owner approval required before any ClickUp ticket is created.*
