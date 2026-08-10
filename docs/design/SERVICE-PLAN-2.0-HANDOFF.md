# SelahCue — Service Plan builder (Design 2.0) Handoff

**Status:** design complete — builder + inspector, two link flows, all UX-STATE-MATRIX §4 states, and a populated Live Console plan panel.
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` · **Section:** `614:124` "SelahCue · Service Plan — Design 2.0".
**Anchors:** Live Console `312:124`, old builder `31:2` (visual reference), Presentations library `547:124` (deck-picker source), Presentation/Media editor `329:124`.
**ClickUp:** [STORY 86ajxxqtp](https://app.clickup.com/t/86ajxxqtp) under [EPIC — Service Planning & Library 86ajp072p](https://app.clickup.com/t/86ajp072p).
**Goal Contract:** `docs/delivery/goals/GOAL-design-service-plan.md`.
**Grounding:** SelahCue-PRD FR-001..008/012/013/019-021/026/029/070/071/074/075/138/139; UX-FLOWS §1-2; UX-STATE-MATRIX §4-6; NAV-IA-spec; PRESENTATIONS-LIBRARY-spec; ADR-0020; code `selahcue-core/src/plan.rs`, `selahcue-lan/src/protocol.rs`, `selahcue-app/src/controller.rs`, `selahcue-data/src/deck_repo.rs`, operator `dist/` (`#plan-wrap`).

Frame links: `https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=<id-with-dash>`.

---

## 1. What this delivers & why

The dedicated Service Plan surface (`plan` route) was a placeholder, and the Live Console's "Service Plan" panel had no authoring/linking surface behind it. This delivers the **Service Plan builder** (Design 2.0) — Add-item palette · run sheet · item inspector — and the net-new capability the request asks for: **linking Scriptures and Presentations to plan items**. The Live Console panel is shown **populated from the builder** so it is no longer a placeholder.

### ⚑ Key finding — linking is net-new modelling (flag for backend)

A `PlanItem` today stores only a title (`selahcue-core/src/plan.rs`: `PlanItem { id, kind, title, planned_secs, owner, stanzas, theme }`) — **no `scripture_ref`, `deck_id`, or `media_id`**. A "Scripture" item is a title-only slide; a "SlideGroup" item has no deck link; decks are presented via a separate `PresentAuthoredSlide` takeover path. So linking is **new modelling** (the ADR-0020 follow-up called out in PRESENTATIONS-LIBRARY-spec §2), not wiring of something that exists. This design makes link affordances + **unlinked / linked / missing** states first-class. Follow-up task: see §8 + ClickUp.

---

## 2. Frames (node IDs)

Section `614:124`.

| Region / state | Node | Notes |
|---|---|---|
| **Builder — default** (palette · run sheet · scripture-linked inspector) | `606:124` | hero |
| Inspector — Presentation linked | `608:124` | deck card + Change deck / Open in editor |
| Inspector — Scripture unlinked | `608:380` | reference empty + Search + warn |
| Inspector — Presentation unlinked | `608:627` | "Link a presentation" CTA + warn |
| Right panel — Plan Summary (no selection) | `608:875` | totals, counts, Run pre-service check, Publish, Open in Live |
| **Link Scripture (modal)** | `610:124` | reference + translation + verse list + verses/slide |
| **Link Presentation (modal)** | `610:390` | deck grid picker (reuses library cards) |
| State — Empty (no plan) | `611:124` | Create / Template / Duplicate / Import |
| State — Loading | `611:350` | skeleton + missing-content scan |
| State — Running / live | `611:602` | LIVE (red) + NEXT·STAGED (green) |
| State — Reorder (drag) | `611:820` | lifted row + drop line; Alt+↑/↓ |
| State — Missing content | `611:1035` | ⚠ items + inspector relink |
| State — Error (couldn't open) | `612:124` | Restore last autosave + integrity check |
| State — Permission (view only) | `612:342` | palette + edit controls hidden; read-only inspector |
| State — Delete item (confirm) | `612:584` | dialog; linked deck stays in library; undo |
| State — Recovery (autosave) | `612:802` | crash-loop breaker: Resume vs Start clean |
| State — Published — review changes | `612:1020` | change-badge; reload vs keep |
| **Live Console — Service Plan panel (populated)** | `613:124` | linked scripture + presentation, LIVE/STAGED cueing |

---

## 3. Item types (run sheet)

Reuses `ItemKind` (`plan.rs`) + the UX-FLOWS §1 palette. Type badges (a type scale distinct from status colours): **Song** violet · **Scripture** gold `#f2b84b` · **Presentation** (slide-group) cyan · **Media** rose · **Announcement** slate · **Timer** amber · **Section** muted (a non-triggerable divider). Each run-sheet row: drag handle `⠿` + type accent bar + title + type badge + subtitle (link status/detail) + owner/role + planned duration. Sources: FR-002 (plan_item + types), FR-004 (per-item timing + owner), FR-011 (announcement/sermon-point), FR-019-021 (song sections/copyright). "Sermon" is not a distinct kind — model it as Section/Presentation/Announcement.

---

## 4. Linking flows (the net-new work)

Pattern (owner decision): **right-column Item Inspector + modal pickers**.

### 4.1 Link a Scripture (`610:124`)
A **Scripture** plan item stores a reference. Inspector (`606:124`) shows: Title · **Reference** (parse-validated, ✓ VALID / invalid-with-guidance per FR-026) · **Translation ▾** (bundled code WEB/KJV/… ; omitted ⇒ default) · **Verses / slide** (FR-029) · **Verse numbers** (superscript/inline/hidden) · a verse **Preview** slide (gold reference) · **Search scriptures…**. The modal reuses the console Scriptures browser: reference/keywords search + translation ▾ + chapter nav + verse list with the selected range highlighted (green), footer verses-per-slide + **Link to item**. Ref search = `ScriptureSearch` (FR-028, <500ms). Unlinked state (`608:380`) shows an empty reference + a warn chip "won't display until a valid reference is set".

### 4.2 Link a Presentation (`610:390`)
A **Presentation** (slide-group) plan item points at a `DeckId` (= one authored deck = one `document`; ADR-0020). Inspector (`608:124`) shows the **linked deck card** (thumbnail, "24 slides · edited 2h ago") + **Change deck…** / **Open in editor**. The modal reuses the Presentations library (`547:124`) deck grid — search + Grid/List + a **New presentation** card + deck cards with slide-count pills; the selected deck gets an indigo border; footer **Link to item**. Linking marks the deck "In a plan" on its library card (PRESENTATIONS-LIBRARY §3/§5). Unlinked state (`608:627`) shows a dashed "No presentation linked" CTA + warn. Deleting a linked deck ⇒ the plan item shows **missing** (FR-007; §5 below).

---

## 5. States (UX-STATE-MATRIX §4 → frame)

| State | Frame | Treatment |
|---|---|---|
| Populated / running (default) | 606:124 | run-of-show, per-item duration+owner, planned sum, section dividers, item inspector |
| Empty (no plan) | 611:124 | centered CTA — Create · Template · Duplicate · Import (WORKFLOWS B1) |
| Loading | 611:350 | skeleton rows + "Opening plan… scanning for missing content" (`role=status`) |
| Item-selected / staged + Live | 611:602 | selecting stages to **Preview** (green); one item **◀ LIVE** (red) + **NEXT·STAGED** — invariant preserved |
| Reorder / drag | 611:820 | drag handle `⠿`, lifted row + drop line; keyboard **Alt+↑/↓**; order persists (FR-001) |
| Validation — missing content | 611:1035 | `⚠` badge (icon+text, `aria-describedby`) + Review; audience gets safe placeholder never black (FR-007/070); inspector Relink |
| Error | 612:124 | non-blocking banner "Couldn't open this plan"; **Restore last autosave** (FR-005 last-3) + integrity check (FR-079); live output unaffected |
| Permission (view only) | 612:342 | edit/add/reorder/publish **hidden, not greyed**; read-only inspector; follow live where role allows |
| Destructive (delete item) | 612:584 | confirm; **linked deck stays in library**; Undo (PRESENTATIONS-LIBRARY §5) |
| Recovery / autosave | 612:802 | crash-loop breaker (3 crashes/60s) → Resume last live state (default) vs Start clean; ≤5s loss (FR-074/075) |
| Published → change badge | 612:1020 | "Plan updated · Review changes"; reload vs keep; never silently reorders the live run sheet (FR-006) |

N/A justifications: *offline* — the plan is local (NFR-015), fully operable; only "Publish to team" queues (a chip on that button), not a distinct frame. *Mobile-disconnected* — desktop control intact; device-count decrement is shell chrome, not a plan state.

---

## 6. Live-cueing invariant (annotated on every relevant frame)

**Selecting/staging a plan item loads it into Preview only; it never changes Live. The only path staged→air is an explicit Go Live (`Enter`; global fallback `Ctrl/Cmd+Enter`)** (FR-012; UX-CANONICAL §15; controller.rs). Preview/staged = green/dashed, Live/Program = red/solid, each carrying a **text label** (not colour-only). The inspector and console panel both carry a lock note stating this. Deck-linked items must flow through this normal Preview→Go Live path (reconciling the current `PresentAuthoredSlide` takeover).

---

## 7. Accessibility

- **Keyboard:** every row/control focusable; reorder via **Alt+↑/↓** (NFR-019); **Go Live = Enter** (never overloaded with Next); modals are focus-trapped `role=dialog`; permission-hidden controls leave tab order.
- **Structure:** run sheet as `role=tree`/`treeitem`; live item `aria-current=true`; loading `role=status aria-live=polite`; error `role=alert`; destructive/recovery `role=alertdialog`/`dialog` (Cancel/Resume focused).
- **Colour independence:** LIVE/STAGED/MISSING all carry text labels; the missing state pairs `⚠` + text + `aria-describedby` remediation (WCAG 1.4.1).
- **Contrast:** Design-2.0 tokens audited AA; `text-muted #6b7383` used only for tertiary labels. Touch/hit targets sized comfortably (≥44px rows).
- Reduced motion: reorder/skeleton animations respect the global reduced-motion setting.

## 8. Implementation notes, handoff & follow-ups

- **Two surfaces:** the **builder** (`plan` route, coordinator authoring) publishes → the **Live Console panel** (operator run surface, `#plan-wrap`) opens the published plan (FR-006). Keep them distinct; the console panel is compact (running order + quick-add + transport), the builder is the full editor.
- **Reuse, don't rebuild:** link-Scripture reuses the console Scriptures browser; link-Presentation reuses the Presentations library `547:124`; a linked deck opens in the editor `329:124`.
- **Design-system:** all controls map to Design-2.0 primitives (badge, card, banner, toggle, select, segmented, button, dialog/modal, list row). No new pattern language. Type badges are a documented type scale separate from the fixed status colours.

**Recommended next roles (per owner):**
1. **/backend-engineer** — add the `PlanItem` content-reference (scripture ref {book/chapter/verses, translation, verses-per-slide}; `deck_id`; `media_id`) to `plan.rs`; extend `AddItem`/`PlanItemView`/`OperatorStateView` in `protocol.rs` (update the Dart fixtures + `test_protocol.rs` together); resolve linked refs/decks in `controller.rs` (`slide_for_item`/`scripture_slide_in`); missing-content detection (FR-007). This is the ADR-0020 follow-up.
2. **/frontend-engineer** — implement the builder + link modals + the populated console `#plan-wrap` panel in the operator webview (`dist/`), per this handoff; wire select→Preview and Go Live; drag-reorder + Alt+↑/↓.

**Open questions:** (1) content-reference model shape (backend/architect). (2) whether the builder lives under a "Presentations" landing or a standalone "Plan / Library" route (NAV-IA). (3) plan-level auto-advance is unspecified — deck-level auto-advance only (ADR-0020); confirm.

---

## 9. Independent design-QA

An independent multi-agent design-QA pass (5 reviewers) inspected all 18 rendered frames via screenshots. **0 critical, 4 major, 20 total** (the Settings-session dialog-collapse fix held — all modals/dialogs rendered correctly).

### Fixed
- **MAJOR — demo data didn't reconcile.** Header read "8 items · 1:12:00" while 6 rows render (sum 53:12); summary counts didn't add up. Reconciled everywhere to **6 items · 0:53:12**, and rebuilt the Plan Summary (Items 6, Songs 2, Scripture 1, Presentations 1, Media 1, **Announcements 1**, Missing 0, Assigned 6/6). Empty state → "0 items · 0:00"; loading → header counters skeletoned ("—"). Console → "6 items".
- **MAJOR — reorder ambiguous** (`611:820`): the drop line was disconnected from the grabbed row. Now the origin row is dimmed ("moving…") and a **dashed indigo ghost of "Sermon: The Waiting · dropping here"** sits at the drop position.
- **MAJOR — empty state** (`611:124`) still showed populated counters → zeroed.
- **MAJOR — view-only** (`612:342`): the enabled "Open in Live" write action contradicted view-only → relabelled to a passive **"Following live"** (ghost).
- **Invariant copy corrected:** the builder inspector note wrongly used the console's "Selecting stages to Preview · Go Live (⏎)" vocabulary. Standardised to builder-accurate copy: *"Editing the plan here never changes Live. Open in Live loads it into the console — cueing (Preview → Go Live) happens there."* The console panel keeps the Preview/Go-Live cueing note (that surface's action). Error state (`612:124`) saved-indicator → **"Recovery mode"** (amber) instead of a contradictory green "All changes saved".
- **Link modals:** full verse text (no ellipsis) in the scripture picker; a non-colour **"✓ Selected"** footer on the chosen deck; a Preview/never-Live reassurance added to the presentation-modal subtitle; the behind-scrim inspector context switched to the Presentation item.
- **Console:** "ANN" → "ANNOUNCE"; dropped the internal "no longer a placeholder" phrase from the caption; nudged dim position readouts (1/24, 0:00) to the AA `text-secondary` tier.

### Accepted / documented (minor)
- Type-accent bars reuse hue families that also appear on type badges (e.g. SCRIPTURE gold bar + gold badge). This is the **type scale by design** (bar = quick type cue, badge = label); selection/focus is a separate **indigo** border, so there is no functional collision.

**Verdict:** no outstanding critical/major; coverage complete and implementation-ready.
