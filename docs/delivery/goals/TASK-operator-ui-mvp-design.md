# Goal Contract — TASK-operator-ui-mvp-design

## Identity

- Goal ID: TASK-operator-ui-mvp-design
- Parent goal ID: EPIC-86ak7kgj3 (Operator UI — ProPresenter adopt/adapt/reject)
- Title: Implementation-ready UX specs for the five design tickets of the Operator UI MVP slice (UI-B1, UI-A1, UI-C1, UI-D1, UI-A2)
- Role: ui-ux-designer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak7kgjk (sequence #1; siblings 86ak7kgmk, 86ak7kgn1, 86ak7kgn9, 86ak7kgnm)
- Created: 2026-08-28
- Updated: 2026-08-28
- Maximum iterations: 8
- Independent verification required: yes (owner review — the UI/UX Designer's work is reviewed by the user, not the four-reviewer pipeline)

## Objective

Every one of the five MVP design tickets has a written, implementation-ready UX spec in `docs/design/`
covering layout/IA, the full state matrix, edge cases, interaction detail, keyboard map, accessibility
annotations and Design 2.0 token redlines — precise enough for a frontend engineer to build and for QA to
test without asking a follow-up question; plus a cross-surface interaction proposal for the owner-approved
double-click accelerator, written as a proposal for Priya to ratify into an FR rather than as settled spec.

## Baseline (Verified)

- `docs/product/prds/SelahCue-Operator-UI-PRD.md` v1.0 exists (Priya, 2026-08-28), §14 carries FR-201…223
  with per-FR "Designer detail" blocks. `docs/research/PROPRESENTER-UI-RESEARCH.md` carries the evidence
  register E01…E42.
- Diego has cut the epic into tickets. The five in this contract sit at `planning/todo`, priority high
  (UI-A2 normal), all children of `86ak7kgj3`, all recorded as "Blocked by the DEC-016 gate".
- **DEC-016 is PROPOSED, not approved.** Seven of nine open questions are unanswered. The owner directed
  work to start anyway. OQ-3 and OQ-8 are answered (see Dependencies).
- The shipped operator console is `implementation/desktop/crates/selahcue-operator/dist/`
  (`index.html` 1418 lines, `app.css` 6713, `app.js` 8575). Design 2.0 `--sc-*` tokens are present in
  `app.css:29-56`; the legacy `--bg/--panel/--line/--text/--accent/--preview-ink/--live-ink/--warn-ink`
  layer is still in place beneath them (DESIGN-2.0-HANDOFF §3.2 — migration is not complete).
- **The slide grid has no density control and no size slider today.** The console filmstrip
  (`#slide-strip`) renders fixed 168×94 canvases (`app.js:4913`); the Presentations Library grid
  (`#pm-grid-tiles`) renders fixed 320×180 canvases (`app.js:7501`). Neither reads a stored preference.
- **Verified, and material to this goal: a double-click-to-live accelerator already ships, in three
  places, by three different mechanisms** — see `docs/design/DOUBLE-CLICK-GO-LIVE-proposal.md` §2. It is
  not new work; it is undocumented shipped behaviour with divergent semantics.
- `Presenter::stage()` is `selahcue-present/src/present.rs:159`, `go_live()` `:186`,
  `present_authored()` `:229`. `required_permission()` maps `GoLive | FollowScripture |
  PresentAuthoredSlide → Permission::GoLive` (`selahcue-lan/src/rbac.rs:104-109`) — the no-escalation
  precedent from `86ajtwq2b` is already applied to the authored-slide path.

## Inputs and evidence sources

- PRD `docs/product/prds/SelahCue-Operator-UI-PRD.md` §8 (constraints), §14 (FR-201…215 + Designer detail),
  §22 (accessibility), §26 (risks), §28 (open questions), §30 (MVP slice).
- Research `docs/research/PROPRESENTER-UI-RESEARCH.md` §4 (owner screenshots), §7 (category), §10.1
  (what the reference leaves undocumented). Evidence rows E01, E02, E03, E09, E23, E41, E42.
- Design canon: `docs/design/DESIGN-2.0-HANDOFF.md` (§3.1 tokens, §4 component inventory, §6 a11y),
  `NAV-IA-spec.md` (§3 Screens page, §4 console outputs status), `THEME-MODEL-spec.md`, `UX-CANONICAL.md`.
- Shipped console: `implementation/desktop/crates/selahcue-operator/dist/{index.html,app.css,app.js}`.
- Engine seams: `selahcue-present/src/present.rs`, `selahcue-app/src/controller.rs`,
  `selahcue-lan/src/rbac.rs`.
- The five ClickUp tickets, read in full.

## Scope

### In scope

- Written UX specs, one per ticket, in `docs/design/`, following the `NAV-IA-spec.md` house style
  (decision-forward prose, state tables, explicit accessibility and token sections, a handoff section).
- The thumbnail **size tiers** UI-B1's slider steps through — specified here because UI-B2 (`86ak7kgkg`,
  engineering) depends on them, even though UI-B2 itself is not design work.
- A cross-surface **proposal** for the double-click accelerator, for Priya to ratify into an FR.
- ClickUp status moves and QA steps in list form on each ticket.

### Non-goals

- `86ak7kgkg` / UI-B2 / FR-207 — variable-size engine thumbnails and the bounded LRU. Engineering.
  This contract supplies only the tier table it consumes.
- Any change under `implementation/`. Docs only.
- Figma frames. **Deferred deliberately**, on the PRD's own instruction: RISK-205 reads "NFR-204 pins
  shipped ink; Uma designs from the live console + tokens, Figma updated after". The Design 2.0 frames are
  known to lag the shipped console on contrast (`figma-frames-draw-wcag-failures`), so drawing frames first
  would encode a regression. Recorded as a follow-up, not as done.
- Answering any open question. Defaults are labelled as assumptions awaiting the owner.

### Constraints

- **CON-U2** — staging never changes Live; only Go Live does. The density cluster is output-neutral.
- **CON-U1** — WebView is the console only; the compositor is native wgpu (ADR-0002/0003).
- **CON-U4** — one meaning per colour family: green staged/safe, red live/alarm, amber warning.
- **CON-U7** — do not regress shipped accessible ink (GO LIVE 8.70:1, BLACKOUT 7.19:1, primary 4.72:1).
  Only `--sc-text-muted` is genuinely open.
- **CON-U3** offline-first. **CON-U6** mobile enforces 4 roles today, not 7.
- A SelahCue "theme" is a slide-design template, never a light/dark colour mode.
- Colour is never the sole channel (WCAG 1.4.1).

### Assumptions and unknowns

| Ref | Open question | Assumption taken | Validation owner |
|---|---|---|---|
| OQ-1 | Default density + thumbnail tier | Grid, tier M (6 columns) — the PRD's stated consequence of silence | Owner |
| OQ-5 | Screen-dot semantics | Red = rendering live content; struck = disabled — the PRD's proposed mapping | Owner |
| OQ-7 | Hotkeys auto-only vs user-assignable | Auto-assigned only in v1 (Proclaim model) | Owner |
| — | `dblclick` dispatch when the two clicks land on different children | ASSUMED browser-dependent; the spec therefore requires an explicit item-identity comparison rather than relying on it | Implementer, at build |

## Dependencies and approvals

- **DEC-016 gate — PROPOSED, not approved.** Owner directed a start regardless. Every ticket still carries
  "Blocked by the DEC-016 gate"; nothing here closes that.
- **OQ-8 ANSWERED** — keep the staging invariant *and* add a double-click accelerator. Confirms the
  acceptance criteria as written; CON-U2 stands.
- **OQ-3 ANSWERED** — a content marketplace is wanted eventually. No effect on this queue.
- `86ajy0hw0` (Service Plan wire — per-item duration, plan summary, missing flag) is *in progress* and
  supplies the data FR-202 rolls up and FR-204 badges. Design does not wait on it; implementation follows it.
- `86ak4xxwm` (host signal seams) is *in progress* and is what FR-214 must read. The spec says so.
- `86ak507hh` (output-fault reporting never self-clears) is an open risk to the FR-204 "resolved" state.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | UI-B1 has a spec covering FR-205 and FR-206 with all six named states, all three edge cases, the keyboard map, and `aria-valuetext` | Read `docs/design/SLIDE-VIEW-DENSITY-spec.md` against the ticket's States / Edge cases / Accessibility sections | Every listed item present and specified | `docs/design/SLIDE-VIEW-DENSITY-spec.md` | PASS |
| C-002 | yes | The thumbnail size tiers UI-B2 consumes are specified as a table: tier name, request size, column count, CSS-scale range | Read the tier table | 3 quantised request tiers, ≥4 and ≤12 columns, explicit "quantise then CSS-scale" rule | `SLIDE-VIEW-DENSITY-spec.md` §5 | PASS |
| C-003 | yes | UI-A1 spec covers FR-201 + FR-202 including the five states and the two edge cases, with the live-chip stub rule | Read `docs/design/PLAN-SECTIONS-DURATIONS-spec.md` | All present | `PLAN-SECTIONS-DURATIONS-spec.md` | PASS |
| C-004 | yes | UI-C1 spec fixes a 6-colour section palette that reuses no broadcast status hue, and specifies auto-assignment with collision checking | Read `docs/design/SONG-GROUPS-HOTKEYS-spec.md` §3/§5; cross-check each hue against `--sc-live/--sc-preview/--sc-warn` | No group hue in the live/preview/warn families; assignment algorithm stated deterministically | `SONG-GROUPS-HOTKEYS-spec.md` | PASS |
| C-005 | yes | UI-D1 spec maps the five per-screen states to SelahCue semantics and states the divergence from the reference explicitly | Read `docs/design/SCREEN-STATUS-spec.md` §3 | Red = live; struck = disabled; divergence recorded with its reason | `SCREEN-STATUS-spec.md` | PASS |
| C-006 | yes | UI-A2 spec defines the badge roster from SelahCue's own detection model, not the screenshot, and handles the never-clearing-fault risk | Read `docs/design/ATTENTION-BADGES-spec.md` §3/§6 | Roster traced to master FR-007/FR-084; `86ak507hh` addressed | `ATTENTION-BADGES-spec.md` | PASS |
| C-007 | yes | The double-click accelerator proposal answers all four owner questions (surfaces, already-live, misclick window, opt-out) and is labelled a proposal, not spec | Read `docs/design/DOUBLE-CLICK-GO-LIVE-proposal.md` | Four numbered answers; status line says "proposal for Priya" | `DOUBLE-CLICK-GO-LIVE-proposal.md` | PASS |
| C-008 | yes | Every assumption taken against an unanswered OQ is visibly labelled as an assumption awaiting owner confirmation, in the spec itself | `grep -n "OQ-" docs/design/{SLIDE-VIEW-DENSITY,SONG-GROUPS-HOTKEYS,SCREEN-STATUS}-spec.md` | Each hit sits inside an "assumption, not a decision" framing | grep output | PASS |
| C-009 | yes | No file under `implementation/` is modified | `git status --porcelain implementation/` compared to the session-start snapshot | No new modifications attributable to this goal | git status | PASS |
| C-010 | yes | Each of the five tickets is moved to `in progress`, carries a comment naming its spec path, and carries QA steps in list form | Read the five ClickUp tickets | Status `in progress`; spec-location comment; QA steps list present | ClickUp | PASS |
| C-011 | no | Figma frames extending file `SYQn5hFY8YVQKm3c6rw0eJ` | — | — | Deferred per PRD RISK-205; recorded as a follow-up | NOT_APPLICABLE |

## Verification plan

- Focused verification: read each written spec back against its ticket's States / Edge cases / Acceptance
  criteria / Accessibility sections, item by item; confirm each Design 2.0 token named actually exists in
  `dist/app.css:29-56`.
- Broader regression verification: `git status --porcelain implementation/` unchanged; no existing
  `docs/` file edited (`docs/decisions/DECISION-LOG.md` in particular carries another session's WIP and is
  untouched).
- Independent verifier: the owner, at the DEC-016 gate. Priya for the double-click FR.
- Required environment: repository read access; ClickUp MCP.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-008 (all specs)
- Hypothesis: The tickets are detailed enough that the design work is genuine specification — resolving
  what the tickets deliberately leave to design — rather than re-derivation, and the shipped console is the
  correct source of truth for tokens and existing behaviour (PRD RISK-205).
- Change or investigation: read PRD §14 designer-detail blocks, all five tickets in full, Design 2.0
  handoff §1/§2/§3/§4/§6/§7, `NAV-IA-spec.md`, and the shipped `dist/` (markup, tokens, slide-strip and
  grid handlers) plus the Rust seams `present.rs`, `controller.rs`, `rbac.rs`.
- Verifier executed: source reading; `grep` over `dist/app.js` for `dblclick`, `goLive`, `stageSlide`.
- Result: specs written. **One hard constraint in the commissioning brief turned out to be unworkable as
  literally stated** — see Risks below and the proposal doc §4.
- New evidence: three shipped double-click paths with divergent semantics; `Presenter::present_authored`
  writes straight to Live without touching `staged`.
- Decision: gate-review

## Risks and rollback

- **Risk — the brief's hard constraint "must compose `Presenter::stage()` then `go_live()`" cannot be met
  for deck slides.** `go_live()` commits `self.staged`, which for a plan deck item is the item *title*, not
  deck pixels: the host has no deck store (decks are operator-owned — `86ajy02zq`). Routing a deck slide to
  Live is `PresentAuthoredSlide` → `Presenter::present_authored()` (`present.rs:229`), which calls
  `apply_live` directly and never touches `staged`. Mitigation: the proposal restates the invariant as a
  *property* — nothing reaches Live except through an explicit operator commit gesture, and Preview shows
  what is about to go and what did go — and specifies the deck-slide equivalent with the same `GoLive`
  permission and the same post-commit verification the scripture path already performs. Escalated to Priya
  and Aria rather than resolved by design.
- Risk — the specs are written against defaults for three unanswered OQs. If the owner answers differently,
  the affected sections change. Mitigation: each is isolated in a single labelled subsection so the edit is
  local; none is load-bearing for the surrounding layout.
- Rollback: all seven files are new and untracked. Deleting them restores the prior state exactly. Nothing
  is committed and no existing file is edited.

## Pause and escalation conditions

- If the owner answers OQ-1, OQ-5 or OQ-7 differently from the assumption taken, the corresponding spec
  subsection is revised before implementation starts — owner, via the DEC-016 gate.
- The `stage()`-then-`go_live()` composition finding is escalated to Priya (FR authorship) and Aria
  (architecture): it needs a decision about how the invariant is *stated*, not a design workaround.
- If `86ak507hh` (faults never self-clear) is not fixed, FR-204's "badges clear when resolved" acceptance
  criterion cannot pass for output faults — Kenji owns that.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-operator-ui-mvp-design.md --completion`
- Validator result: recorded at run time in the handoff comment.
- Independent verification result: pending — owner review at the DEC-016 gate.
- Terminal state: `GATE_REVIEW`
- Remaining failed or blocked criteria: none mandatory. C-011 (Figma) `NOT_APPLICABLE` per PRD RISK-205,
  carried as a follow-up.
- ClickUp final evidence comment: posted on each of the five tickets, naming the spec path and the QA steps.
