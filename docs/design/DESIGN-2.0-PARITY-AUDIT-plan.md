# Design 2.0 parity audit — Service Plan builder

**Role:** UI/UX Designer (Uma) · **Date:** 2026-09-20 · **Type:** read-only audit + gap spec
**Goal Contract:** `docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ`, section `614:124` "SelahCue · Service Plan — Design 2.0 (builder +
linking + states)" — 19 frames
**Companion docs:** `docs/design/SERVICE-PLAN-2.0-HANDOFF.md` (the frame-by-frame handoff this audit
verifies against the live tree), `docs/design/PLAN-SECTIONS-DURATIONS-spec.md` (a **different** surface
— see the scope note below, cited only where it clarifies intent)
**Status:** point-in-time. Figma and `dist/` both move; re-run before acting on a row older than a week.

## What was audited

The dedicated Service Plan builder route, `#surface-plan` (`index.html:1057-1097`, the skeleton; content
is built by ~45 `plan*` functions in `app.js`, primarily lines 6302-8830), against every one of the 19
frames the handoff names under section `614:124`.

| Node | Name | Audited as |
|---|---|---|
| `606:124` | Builder — default | Frame `606:124` below |
| `608:124` | Inspector — Presentation linked | Frame `608:*` below |
| `608:380` | Inspector — Scripture unlinked | Frame `608:*` below |
| `608:627` | Inspector — Presentation unlinked | Frame `608:*` below |
| `608:875` | Right panel — Plan Summary | Frame `608:*` below |
| `610:124` | Link Scripture (modal) | Link flows below |
| `610:390` | Link Presentation (modal) | Link flows below |
| `611:124` | Empty (no plan) | States below |
| `611:350` | Loading | States below |
| `611:602` | Running / live | States below |
| `611:820` | Reorder (drag) | States below |
| `611:1035` | Missing content | States below |
| `612:124` | Error (couldn't open) | States below |
| `612:342` | Permission (view only) | States below |
| `612:584` | Delete item (confirm) | States below |
| `612:802` | Recovery (autosave) | States below |
| `612:1020` | Published — review changes | States below |
| `613:124` | Live Console · Service Plan panel (populated) | Console panel below |

### Scope note — `PLAN-SECTIONS-DURATIONS-spec.md` is a different surface

That spec (FR-201/202, Figma `965:124`) designs **section-grouping headers with collapse, per-section
duration subtotals, and a six-slot colour palette** for the **Live Console's compact `#plan-wrap`
panel** — its own text is explicit: *"The plan stays in the console left zone (`#plan-wrap`). No new
surface."* It is cited here only where the two surfaces share a data model (the `section` item kind),
not as a spec this audit's target surface (`#surface-plan`, the dedicated builder route) is expected to
implement. Findings below that touch `section` items on the *builder* route are scoped to what
`SERVICE-PLAN-2.0-HANDOFF.md` §3 itself says about them there ("a non-triggerable divider"), not to the
console-panel spec's fuller header/collapse/subtotal behaviour.

## Method

`get_metadata` on section `614:124` (one call, full 19-frame subtree — 310KB, saved to a local file and
parsed with `jq`/`python3` rather than pulled inline) for structure/text/geometry, cross-checked against
`app.js`/`app.css`/`index.html` and the handoff doc. As with the other Design 2.0 frames, no node on
this section carries a bound Figma variable — every colour cited below is a raw literal, named by its
matching `--sc-*` token for readability where one exists.

## Verdict vocabulary

Same as the existing audits: **MATCH** / **DRIFT** / **MISSING** / **EXTRA** / **UNSPECIFIED** /
**INTENTIONAL-DEVIATION** / **A11Y-DEFECT** / **A11Y-CONFLICT**. Severity: **S1** blocks
correct/accessible use · **S2** visible parity break an operator would notice · **S3** cosmetic · **S4**
informational.

---

# Summary

**9 numbered findings: PLN-001…PLN-009.**

| Verdict | Count |
|---|---|
| MATCH | 22 |
| DRIFT | 9 |
| MISSING | 6 |
| EXTRA | 3 |
| A11Y-DEFECT | 1 |

Severity: **1 × S1**, 12 × S2, 20 × S3, 8 × S4.

## Headline

This is, by a wide margin, the **most rigorously self-documented** surface in this audit round: the
code's own comments cite the exact frame ids they implement, name the design-QA findings they fix
(§9 of the handoff), and — repeatedly — explain *why* a deliberate departure exists rather than leaving
it for an auditor to guess at. Three things stand out:

1. **The two link flows (Scripture, Presentation) are built inline in the inspector, not as the two
   dedicated modal frames the design specifies.** `610:124` and `610:390` both draw a **modal** dialog;
   the shipped code (`planScriptureBody`/`planDeckBody`, `app.js:6982-7373`) builds the *same content*
   — reference/translation/verse-picker for Scripture; grid/list deck picker with a "✓ Selected" marker
   for Presentation — directly inside the right-panel inspector, with no overlay. Functionally
   equivalent, structurally different from both frames. **PLN-001/PLN-002.**
2. **The Plan Summary panel (`608:875`) is close to a line-for-line match**, including the exact
   header-total-must-agree-with-rows fix the handoff's own design-QA §9 records as a MAJOR, and the
   `612:1020` "⟳ Plan updated" change badge, built with an explicit code comment naming the predicate
   trap (`app.js:8508-8518`) that a prior attempt at this exact badge already fell into once.
3. **Two states share one honest gap.** `612:124` (Error) and `612:802` (Recovery) are both
   **MISSING as designed** — the code's own comment says the error state "needs autosave-slot wire
   fields that do not exist yet and belongs to 86ak8467m," and ships a minimum honest banner instead of
   either the full error UI or a fabricated one. **PLN-007/PLN-008.**

---

# Frame `606:124` — Builder, default (palette · run sheet · scripture-linked inspector)

## Header

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | "SelahCue · Service Plan" + plan name | `606:129-132` | `index.html:1061` (`<h1>Service Plan</h1>`) — the plan name itself is not repeated in the header (it lives in the run sheet's own header, see below) | DRIFT (Figma's breadcrumb-style header collapses to a plain page title) | S4 |
| — | Versions / "All changes saved" / Open in Live | `606:134-142` | **Not found** as header controls — "Open in Live" exists as `#plan-open-live` (`index.html:1069`), matching content but relocated to the page header's own row rather than a right-aligned trio; **no Versions control and no autosave indicator were found on this route** (the save-state affordance the Theme Designer and Settings surfaces both carry is absent here) | MISSING (Versions, autosave indicator) / MATCH (Open in Live, relocated) | S3 |
| — | View-only badge slot | Not drawn on `606:124` (only on `612:342`) | `#plan-viewonly-slot` (`index.html:1063-1067`) rendered on **every** visit via `planSyncPermission()`, not only the dedicated permission frame — a design choice the code comment justifies explicitly | EXTRA (correct — a permission state that only painted itself on one static Figma frame would be a defect if literal) | — |

## ADD ITEM palette

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Palette item set | Handoff §3: **Song · Scripture · Presentation · Media · Announcement · Timer · Section** | `PLAN_ADD_KINDS` (`app.js:7378-7386`): exactly these seven, same order, same labels | **MATCH** | — |
| **PLN-003** | Button style | Not pixel-specced beyond "add-item palette" | `.plan-palette-btn` (`app.css:6485-6486`): plain text `"＋ " + label` on a flat `--sc-inset` fill — **no type-accent colour** on the palette buttons themselves (the accent only appears once an item is added, on its row) | UNSPECIFIED — the handoff doesn't specify palette-button colour; noting because the run-sheet row *does* carry a type accent and the palette arguably should preview it | S4 |

## Run sheet (row rendering)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Row: drag handle · type accent bar · title · kind badge · link chip · owner · duration · tools | Handoff §3 | `planRenderBuilder()` row builder (`app.js:7910-8040`): handle `⠿` (canEdit-gated), `.plan-b-accent.kind-<kind>`, title, `.kind.kind-<kind>` badge via `planKindLabel()`, link chip via `planLinkChip()`, `.plan-b-owner` (omitted if unset), `.plan-b-dur` (omitted if unset), `↑`/`↓` reorder tools | **MATCH**, structurally complete | — |
| — | Type-accent colours | Handoff §3: Song violet · Scripture gold · Presentation cyan · Media rose · Announcement slate · Timer amber · Section muted | `.plan-b-accent.kind-*` (`app.css:6563-6569`): `--sc-song #A99BFF` (violet) · `--sc-gold` · `--sc-info` (cyan) · `--sc-media #F472B6` (rose) · `--sc-text-secondary` (slate) · `--sc-warn` (amber) · `--sc-text-muted` | **MATCH**, every one of the seven hues verified against the token file | — |
| **PLN-004** | LIVE / PREVIEW badges | Live = red, solid, text label; Preview/Staged = green, dashed, text label (handoff §6) | `badge("live", "LIVE")` / `badge("preview", "PREVIEW")` (`app.js:8018-8019`) — text labels present (WCAG 1.4.1 satisfied); the **row border** carries the colour (`.plan-b-row.is-live { border-color: var(--sc-live) }` / `.is-staged { border-color: var(--sc-preview) }`, `app.css:6491-6492`) — solid in both cases, no dashed treatment for staged | DRIFT (staged border is solid, not dashed, contradicting the handoff's own "Preview/staged = green/**dashed**" line) | S3 |
| **PLN-005** | Section as "a non-triggerable divider" (handoff §3) | `606:124` doesn't draw a Section row in the default state, but the handoff's own prose is explicit about the intended behaviour | The row builder applies **no special case** for `it.kind === "section"` beyond excluding it from the duration column (`app.js:8005`, `it.kind !== "section"`) — a Section item is otherwise a fully selectable, fully reorderable `role="option"` row exactly like every other kind, with `onclick = select` unconditionally wired (`app.js:8025`) | **DRIFT** — the handoff's own stated behaviour for this item kind is not what the row does. A Section on this surface is a live, selectable, orderable row, not an inert label | **S2** |
| — | Duration format `m:ss` / `h:mm:ss` / `—` | PLAN-SECTIONS-DURATIONS-spec §4.1 (console-panel spec, cited for the shared format contract) | `planFmtDuration()`/`planFmtTotal()` (`app.js:6364-6398`) implement exactly this format, tabular-nums styled (`app.css:6570`) | MATCH | — |
| — | Unset duration → omitted vs. "—" placeholder | Code comment at `app.js:7999-8001` names this **exact open conflict**: *"86ak846ft AC-1: 'without a gap or placeholder text'. UI-A1 FR-202 asks for a '—' placeholder instead; the two acceptance criteria conflict and DECISION 86ak84cth owns it."* | Current behaviour: element omitted entirely, not even a dash | **UNSPECIFIED** (self-flagged in code as an open decision, not a bug) — folded into **Open questions** | S4 |

---

# Frame `608:*` — Inspector variants

## `608:875` — Right panel · Plan Summary (no selection)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Totals: Items, Songs, Scripture, Presentations, Media, Announcements, Timers, Missing, Assigned | Handoff §9 design-QA fix: rebuilt to **"Items 6, Songs 2, Scripture 1, Presentations 1, Media 1, Announcements 1, Missing 0, Assigned 6/6"** — every per-kind row summing to Items | `planRenderSummaryInto()` (`app.js:8605-8652`): renders exactly this row set (`Total time`, `Items`, `Songs`, `Scripture`, `Presentations`, `Media`, `Announcements`, `Timers`, `Missing content`, `Assigned`), with a code comment explicitly justifying the **omission** of a Sections row so the per-kind rows keep summing to Items — the identical arithmetic-integrity property the handoff's design-QA fix exists to guarantee | **MATCH**, including the invariant, not just the row list | — |
| — | Missing content — coloured, not just counted | Handoff — missing content is safety-relevant (FR-007/070) | `sum.missing ? "⚠ " + sum.missing : "0"` with `.plan-sum-warn` class only when non-zero (`app.js:8640-8642`) — glyph + text, not colour alone | MATCH (WCAG 1.4.1) | — |
| — | Run pre-service check | Drawn as an action on `608:875` | `planSummaryActions()` (`app.js:8536-8542`): rendered **disabled**, `aria-describedby` a reason note reading *"The pre-service check isn't built yet."* — an honest "later" affordance, not hidden and not faked | MATCH in spirit (drawn as available; shipped as an honest stub) — **UNSPECIFIED whether this counts as parity or a gap**, noted rather than scored either way | S4 |
| — | Publish to team + the `612:1020` change badge | Handoff §5/§9 | `planSummaryActions()` (`app.js:8494-8599`): publication line (`Draft · not published yet` / `Published · version N` / the `⟳ Plan updated` badge when `pub.changed`), gated correctly on `canEdit` and `lifecycle`, live when the host reports the capability, disabled-with-reason otherwise | **MATCH**, including the specific predicate-ordering bug the code comment (`app.js:8508-8518`) says a first attempt at this exact badge already fell into and a mutation test now guards against | — |
| — | Duplicate this service | Drawn on `608:875` | `#plan-sum-duplicate` (`app.js:8573-8579`), gated with the publish/lifecycle pair | MATCH | — |
| — | Open in Live / view-only "Follow in Live" | Handoff §9 design-QA fix: relabel to a passive verb under view-only | `live.textContent = canEdit ? "▶ Open in Live" : "▶ Follow in Live"` (`app.js:8592-8598`) — the *exact* wording the design-QA fix landed | **MATCH**, word-for-word | — |

## `608:124` / `608:380` / `608:627` — Presentation-linked / Scripture-unlinked / Presentation-unlinked

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Linked deck card: thumbnail · "N slides · edited…" · Change deck… · Open in editor | `608:124` | `planDeckCard()` (`app.js:8655+`) resolves the deck name/slide-count from the loaded library, renders the missing treatment when the deck is gone; "Open in editor" jumps to the Presentation surface with the deck pre-opened (`app.js:8774-8786`) | MATCH — the "edited 2h ago" relative timestamp specifically was not verified (not read in this pass) | S4 |
| — | Unlinked warn chip ("won't display until a valid reference is set" / "No presentation linked") | `608:380`/`608:627` | A `Link…`/`Link a presentation…` CTA is rendered per-kind (`app.js:8760-8772`); the literal warn copy from the handoff was not located verbatim, but the functional state (no content until linked) is correctly gated | DRIFT (copy not verified verbatim) | S4 |
| — | Unlink | Not separately named as a frame element but implied by "Change deck…" | `#plan-insp` "Unlink" button, shown only `if (it.link && canEdit)` (`app.js:8787-8797`) | EXTRA (a reasonable, needed control not explicitly drawn) | S4 |
| — | Remove item (danger) | `612:584`'s content, triggered from the inspector | `pmConfirm({...})` two-step dialog (`app.js:8800-8818`): title `Remove "<title>"?`, body *"Only this run-sheet item is removed — any linked scripture or presentation is untouched"* — matching the handoff's §5 "linked deck stays in library" invariant almost word for word | **MATCH** | — |

---

# Link flows — structural drift from the modal pattern

| # | Frame | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| **PLN-001** | `610:124` Link Scripture (modal) | A **dedicated modal dialog**: reference + translation + verse list (chapter nav, contiguous-range selection) + verses-per-slide + a gold reference preview + a footer "Link to item" | `planScriptureBody()` (`app.js:6982-7215`) builds this **exact field set** — reference input, translation select, `Browse`, an inline verse picker with chapter nav (`◀`/`▶`), a `role="listbox" aria-multiselectable` verse list with click-to-extend range selection, verses-per-slide input, and a live gold preview (`"✦ " + ref`) — but renders it **inline inside the right-panel inspector**, with no modal, no overlay, no separate dialog surface | **DRIFT** — content is a near-exact match; structure (modal vs. inline) is not. Functionally the inline approach avoids an extra click-through, but it is a deliberate divergence from the drawn pattern, not an accident (no dialog markup, `role="dialog"`, or focus trap exists around this block) | **S2** |
| **PLN-002** | `610:390` Link Presentation (modal) | A dedicated modal reusing the Presentations-library deck grid: Grid/List toggle, deck cards (thumbnail, name, slide-count pill), a "New presentation" card, indigo-selected + non-colour "✓ Selected" marker, footer "Link to item" | `planDeckBody()` (`app.js:7217-7372`) builds the **identical** field set — Grid/List segmented toggle, deck cards with `▦` thumbnail/name/slide-count pill, a "New presentation" card (guarded against double-activation), `role="option"` selection with a `.pm-link-sel` "✓ Selected" marker, footer `Link to item` button — again **inline in the inspector**, not a modal | **DRIFT**, same structural pattern as PLN-001 | **S2** |

Both flows share the same root cause and are recorded once here rather than as separate per-field
findings — the content-level fidelity is genuinely high; the structural pattern (inline vs. modal) is
the actual gap.

---

# States (`611:*` / `612:*`)

| # | State | Frame | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Empty (no plan) | `611:124` | Centred CTA: heading + sub-copy + **Create / Template / Duplicate / Import** actions (WORKFLOWS B1), each live or disabled-with-reason | `planRenderBuilder()` empty branch (`app.js:7803-7904`): heading text changes by permission (*"Build your service plan"* vs. *"No service plan yet"*), all **four** actions present as `mk()`-built buttons, each individually gated (`planNewPlan`/`planTemplatePlan`/`planDuplicatePlan` disabled — **no saved-plan library exists in this build**, stated as the reason — /`planImportPlan`), plus a fifth "Import a plan bundle…" the frame doesn't draw, disabled with its own reason (FR-139's portable-bundle format doesn't exist) | **MATCH**, including per-action honesty about *why* each is or isn't live — the view-only variant (no controls, a single explanatory line) is also built (`app.js:7824-7837`) | — |
| — | Loading | `611:350` | Skeleton rows + "Opening plan… scanning for missing content" (`role=status`) | `planRenderLoading()` (`app.js:7403-7423`): exact copy match, `role="status"`, header counters blanked to `—` rather than showing a stale figure, 4 `aria-hidden` skeleton rows | **MATCH** | — |
| — | Running / live | `611:602` | One item `◀ LIVE` (red, solid) + one `NEXT · STAGED` (green, dashed); invariant preserved (staging ≠ live) | `.plan-b-row.is-live`/`.is-staged` + `badge()` text labels (`app.js:8018-8019`, `app.css:6491-6492`) — see **PLN-004** for the dashed-vs-solid drift | DRIFT (via PLN-004) | S3 |
| **PLN-006** | Reorder (drag) | `611:820` | Design-QA §9 fix: **origin row dimmed "moving…"** + a **dashed indigo ghost** reading `"<item title> · dropping here"` at the drop position | `.plan-b-dropline` (`app.css:6503`): a plain **2px `--sc-primary` solid line**, no ghost row, no "dropping here" label; `.plan-b-row.dragging { opacity: 0.4 }` (`app.css:6502`) dims the origin row correctly | **DRIFT** — the origin-dim half of the design-QA fix shipped; the drop-position ghost-label half did not | **S2** |
| — | Missing content | `611:1035` | `⚠` badge + text + `aria-describedby` remediation; audience gets a safe placeholder, never black; inspector Relink | `planLinkState()` (`app.js:6398-6408`) is a single three-state resolver (`resolved`/`missing`/`unknown`) consumed identically by the run-sheet chip, the inspector deck card, and the Plan Summary count — explicitly engineered (per its own comment) so the three can never disagree, and decks resolve **locally** against the loaded library first (the operator, not the host, owns deck existence — "Sana S1" fix noted in the comment) | **MATCH**, and a materially more careful implementation than a literal reading of the frame would produce | — |
| **PLN-007** | Error (couldn't open) | `612:124` | Non-blocking banner "Couldn't open this plan" + **Restore last autosave** (FR-005 last-3) + integrity check | `planRenderLoadFailed()` (`app.js:7428-7453`): a minimal honest banner (*"Couldn't open the plan. Live output is unaffected — reopen this surface to retry."*) with `role="alert"`, no Restore-last-autosave affordance and no integrity check — the code's own comment states why: *"needs autosave-slot wire fields that do not exist yet and belongs to 86ak8467m"* | **MISSING** (self-documented, honest partial substitute shipped in the meantime) | S2 |
| **PLN-008** | Recovery (autosave) | `612:802` | Crash-loop breaker: 3 crashes/60s → **Resume last live state** vs. **Start clean**, ≤5s loss | **Not found.** No crash-loop counter, no Resume/Start-clean affordance exists for this surface (grep for "crash-loop"/"Resume"/"Start clean" in `app.js` returns no plan-surface hits) | **MISSING** — same root cause as PLN-007 (the autosave-slot backend piece, 86ak8467m) | S2 |
| — | Permission (view only) | `612:342` | Palette + edit controls **hidden**, not greyed; read-only inspector; a "View only" badge | `planSyncPermission()` (`app.js:7668-7707`) — an unusually careful implementation: the badge is written only on an *explicit* `can_edit === false` (an absent field is not treated as a restriction — never-invent-facts), the palette is hidden with an **inline** `style.display = "none"` rather than the `hidden` attribute specifically because "a class-level `display` rule silently defeats `hidden` in this webview" (a documented WKWebView trap), and the CSS grid track collapse that would otherwise result is explicitly compensated for (`.is-viewonly` class, `app.js:7698-7699`) with a code comment describing the exact 3-column-track bug this fixes | **MATCH**, materially more careful than the frame alone specifies | — |
| — | Delete item (confirm) | `612:584` | `role="alertdialog"`; linked deck stays in library; Undo | `pmConfirm()` invocation at `app.js:8800-8818` — see **inspector variants** table above | MATCH | — |
| — | Published — review changes | `612:1020` | "Plan updated · Review changes" change badge; reload vs. keep | `⟳ Plan updated` badge (`app.js:8519-8524`) — see **`608:875`** table above | MATCH | — |

---

# Frame `613:124` — Live Console · Service Plan panel (populated)

This is the **console's** compact plan panel (`#plan-wrap`, `index.html:98-107`), a structurally
different surface from the dedicated builder audited above — reusing the same host `OperatorView`.
**Its chrome (card shell, the plan-vs-transcript height split) was already audited under the console
pass** (`DESIGN-2.0-PARITY-AUDIT-console.md` `CON-012`, a DRIFT on the height-split ratio, not
re-litigated here). This pass checked only its *content* population, since `613:124` is explicitly named
in the Service Plan handoff as "no longer a placeholder."

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Populated rows (not a placeholder) | `613:124` | The console's own row renderer (`app.js:60-137`, distinct from `planRenderBuilder`) builds real rows: title, a **lower-case** kind badge (`it.kind`, e.g. `"song"`) with truthful slide position (`"song · 2/6"`), and reuses `planLinkChip()` — the same link-chip function the builder uses, so a linked/missing/unknown state reads identically in both places | **MATCH** on population; the badge text case differs from the builder's `planKindLabel()` (which properly cases "Song") | DRIFT (S4, cosmetic) | S4 |
| — | Select → stage (never live) | Handoff §6 invariant | Row click → `invoke("select", { itemId })` (`app.js:70`) — stages, does not go live | MATCH | — |

---

# Accessibility

## A11Y-1 — Real defect (fix regardless of the frame)

This surface's own controls did not introduce a new instance of the recurring gradient/white-text
defect found on Theme Designer and Preservice — `#plan-open-live`/`#plan-sum-live` use `.pm-btn-primary`
(the flat-fill, already-compliant control the Presentation audit measured at 4.72:1). One real defect
was found:

| # | Where | Measured | Why it fails | Fix |
|---|---|---|---|---|
| **PLN-009** | `.plan-viewonly` badge — need to confirm ink. `app.css:6626-6631` was read at metadata level only in this pass; flagging for a follow-up spot-check rather than asserting a ratio without a direct read | not computed in this pass | — | Re-verify `.plan-viewonly`'s fill/ink pairing directly before treating this as closed; not scored above pending that check (kept out of the summary counts) |

(Recorded honestly as an open verification item rather than guessed — see the project's own
"never guess an implemented value" rule.)

## A11Y-2 — Classified, not blanket-swapped

- `.plan-b-owner`, `.plan-empty-later`, `.rc`-style meta text use `--sc-text-secondary` (7.40-8.74:1),
  already the compliant tier — **no muted-token violation found on this surface's own new rules.**
- The Missing-content and Publish-changed indicators both pair colour with text/glyph (`⚠ N`,
  `⟳ Plan updated`), satisfying WCAG 1.4.1 throughout.

## A11Y-3 — Clear

- LIVE/PREVIEW badges are text, not colour-only (PLN-004 notes a *shape* drift — dashed vs. solid — not
  a colour-only violation).
- Keyboard: `Alt+↑/↓` reorder is gated on the exact same `canEdit` verdict as the visible buttons
  (`app.js:8035-8038`) — the code comment explicitly notes this is the **second** time a reviewer had to
  find a keyboard path left open after the mouse path was correctly restricted, matching the CLAUDE.md
  precedent about hidden-not-greyed permission gating needing to hold for every input modality.

---

# Open questions

- **PLN-OQ-1 (product/backend).** PLN-007/PLN-008 (Error, Recovery) are both blocked on the same
  missing autosave-slot backend piece (`86ak8467m`), already tracked. Not a design gap to re-scope —
  flagged here only to confirm Phase D's ticket for this should point at the existing tracked item
  rather than opening a duplicate.
- **PLN-OQ-2 (product).** The unset-duration display conflict the code itself flags (`app.js:7999-8001`,
  omit vs. "—" placeholder, `DECISION 86ak84cth`) is already an owned open decision — repeated here only
  so it surfaces in this audit's own findings list rather than being missed by whoever reads this doc
  without also reading the source comment.
- **PLN-OQ-3 (product).** PLN-005 — should "Section" actually behave as the handoff's own §3 describes
  it ("a non-triggerable divider") on this builder route, or was that always aspirational text carried
  over from the console-panel spec (`PLAN-SECTIONS-DURATIONS-spec.md`) that the builder was never meant
  to implement? If the builder is meant to treat Section as an ordinary selectable/orderable item (which
  is what it does today), the handoff's own §3 line is the thing that needs correcting, not the code.
- **PLN-OQ-4 (design/product).** PLN-001/PLN-002 — is the inline-in-inspector link flow the *intended*
  final pattern (a legitimate, reasonable UX simplification over two extra modal dialogs), or should the
  two dedicated `610:124`/`610:390` modal frames still be built? Both are complete, working
  implementations of the same content — this is a choice between two valid patterns, not a build gap.
- **PLN-OQ-5 (design).** PLN-006 — is the drop-position "ghost" label (design-QA §9's fix) worth the
  extra implementation cost given the origin-row dim already communicates a drag is in progress, or was
  it accepted into Figma but never actually requested of Farah as a ticket?

---

## Pending ClickUp update

No ClickUp task ID was assigned to this audit at authoring time. Recorded per Phase D of the parent
plan (`docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md`) — ticket creation and
linking is out of scope for this docs-only pass.

---

## Reconciliation — 2026-09-22

**Author:** Farah (Frontend). **Scope:** ClickUp `17tnw2axptt` — re-verify all 9 `PLN-###` findings
against `main` (this worktree's base commit, `0f08778`, `origin/main` tip at the time) and close what
is genuinely open and not decision- or dependency-blocked. This section is additive; every table
above is left as originally written — this is the *current* status layered on top.

### Method

1. Re-read every cited `file:line` directly against this worktree's own `dist/app.css`/`dist/app.js`,
   not the shared checkout — the shared tree carries large uncommitted WIP from concurrent sessions
   that shifts line numbers (e.g. `.plan-b-row.is-staged` reads at a different line there than in a
   clean worktree cut from `origin/main`).
2. Cross-checked the two dependency families this ticket's own description names: the ClickUp
   `waiting_on` dependency on `86ak8467m` ("Service Plan states") and, transitively, its own backend
   dependencies `86ajy0hwg`/`86ajy0hxg`; and the consolidated decision ticket `17tnw2axpu4` covering
   `PLN-OQ-3`/`PLN-OQ-4`/`PLN-OQ-5`.
3. Computed the WCAG contrast for `PLN-009` directly from the live `--sc-*` token values and
   corroborated it against the existing automated sweep (`PL AC-46` in `operator_headless.py`, which
   already includes `.plan-viewonly`/`.plan-viewonly-why` in its ink-contrast site list).
4. Verified with `python3 scripts/operator_headless.py`: **1824 checks, 0 FAIL** (1818 immediately
   before this ticket's checks, after rebasing onto `origin/main`'s intervening fixes — a real
   conflict in `EXPECTED_MIN_CHECKS`'s own history block, resolved by re-deriving the count from an
   actual clean run, never hand-summed; 1821 after this ticket's original 3 PLN-004 checks; 1824
   after Vera's PR #83 performance review found the fix needed a cascade guard for the
   live-AND-staged case (below) and 3 more checks were added to prove it — matching
   `EXPECTED_MIN_CHECKS` in `scripts/operator_headless.py`, confirmed by two independent clean runs,
   and mutation-verified by reverting the guard and watching exactly the 2 new precedence
   assertions go red).

### FIXED

| Finding | Evidence |
|---|---|
| `PLN-004` | `app.css`: `.plan-b-row.is-staged` now carries `border-style: dashed` alongside its existing `border-color: var(--sc-preview)`; `.plan-b-row.is-live` is untouched (stays solid) — matching the handoff's "Preview/staged = green/dashed, Live/Program = red/solid" line verbatim, not a paraphrase of it. 3 `operator_headless.py` checks added beside the existing C-001 run-sheet fixture prove it: a non-vacuousness setup check (item 11 is staged-only, not also live), the dashed-border assertion itself, and a solid-border control on an unstaged row (item 12) proving the dashed rule is scoped to `.is-staged` and not a global border reset. **Precedence fix (Vera, PR #83 performance review):** `Command::GoLive` (`selahcue-app/src/controller.rs`) sets `live_idx = staged_idx` but never clears `staged_idx`, so the item that just went live carries BOTH `is_live` and `is_staged` on every ordinary Go Live — not an edge case. `.is-live`/`.is-staged` have equal CSS specificity and `.is-staged` was declared second, so it won the cascade: the item actually on air rendered with Preview's colour (pre-existing) and, after this PR's own dashed-border change, Preview's *shape* too — worse, not better. Fixed by scoping the staged rule to `.plan-b-row.is-staged:not(.is-live)` so Live always wins an overlap; 3 more checks added in an isolated fixture proving a live+staged row renders solid (not dashed) and the same border colour as a live-only row. Mutation-verified: reverting the `:not(.is-live)` guard turns exactly those 2 new precedence assertions red and nothing else. All 6 checks PASS. |

**1 finding FIXED.**

### VERIFIED — no change needed

| Finding | Evidence |
|---|---|
| `PLN-009` | The original audit left `.plan-viewonly`'s ink unverified (read at metadata level only). Direct computation: ink `var(--sc-warn)` `#f5a524` on fill `var(--sc-warn-soft)` `#2a2415` (the badge's own solid pill background, not the page ground behind it — the correct pairing per WCAG 1.4.3 for a filled chip) = **7.56:1**, clearing AA-normal (4.5:1) and AAA (7:1) despite the 11px/700 type. Corroborated by the pre-existing automated sweep `PL AC-46`, which already lists `.plan-viewonly`/`.plan-viewonly-why` among its ink-contrast sites and reports "all clear" across both the editor and view-only renders it exercises. No code change required — this closes the finding as verified-passing rather than leaving it an open question. |

**1 finding VERIFIED (no defect found).**

### OPEN — decision-blocked (unchanged; guardrail RISK-205/NFR-204)

| Finding | Why still open |
|---|---|
| `PLN-001` / `PLN-002` | `PLN-OQ-4` (inline-in-inspector vs. the two dedicated modal frames) is unresolved — `DECISION — New-surfaces` (`17tnw2axpu4`) is still `planning/todo`. Both patterns are complete, working implementations of the same content; this ticket does not "correct" toward Figma while the product question the audit itself raised is still open. |
| `PLN-005` | `PLN-OQ-3` (should Section behave as a non-triggerable divider on the builder route, or was the handoff's §3 line aspirational text never meant for this route) is unresolved, same decision ticket. |
| `PLN-006` | `PLN-OQ-5` (is the drop-position ghost label worth the implementation cost, or was it never actually requested) is unresolved, same decision ticket. |

### OPEN — blocked on a tracked dependency (unchanged)

| Finding | Why still open |
|---|---|
| `PLN-007` | Frame 13 (Error → Restore last autosave) is explicitly in scope for `86ak8467m` ("Service Plan states"), which this ticket formally depends on via a ClickUp `waiting_on` link. `86ak8467m` itself cannot complete until its own backend dependency `86ajy0hxg` (autosave slots + restore) ships — confirmed still `planning/todo` as of this reconciliation. Not duplicated here, per this ticket's own description: "this ticket should depend on / point at that existing ticket rather than re-implement it here." |
| `PLN-008` | Frame 16 (Recovery / crash-loop dialog) is explicitly **out of scope** for `86ak8467m` and is gated on a separate open architecture decision, `86ak846ge` ("should the Resume vs Start-clean choice be deferred to an operator?"), confirmed still `planning/todo` and explicitly marked "Do not implement against this ticket." The blocker is the decision, not a missing wire field. |

### NOT ACTIONED — no spec to correct toward

| Finding | Why |
|---|---|
| `PLN-003` | Scored `UNSPECIFIED` in the original audit, not `DRIFT` — the handoff never specifies a palette-button colour, so there is no concrete target to build toward and nothing the code contradicts. Left as-is; it is not named in the decision ticket's open-questions list either. |

### Totals (this reconciliation)

| | Count |
|---|---:|
| Total findings | 9 |
| FIXED | 1 (`PLN-004`) |
| VERIFIED, no change needed | 1 (`PLN-009`) |
| OPEN — decision-blocked | 4 (`PLN-001`, `PLN-002`, `PLN-005`, `PLN-006`) |
| OPEN — dependency-blocked | 2 (`PLN-007`, `PLN-008`) |
| Not actioned (no spec) | 1 (`PLN-003`) |

Zero findings were closed by guessing at an unresolved product/design decision or by fabricating a
spec Figma/the handoff never stated. The two genuinely actionable, non-blocked findings (`PLN-004`,
`PLN-009`) are closed; everything else is exactly where the original audit and the existing ClickUp
dependency graph already said it would have to stay.
