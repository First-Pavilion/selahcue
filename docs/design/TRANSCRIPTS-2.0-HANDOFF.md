# SelahCue — Transcripts (Design 2.0) Handoff

**Status:** REVISED 2026-09-30 (17tnw2b0ntc) — this revision is **the one agreed design** for transcript review and sermon-note generation. It supersedes the scrolling/layout gaps in the original pass below, the side-by-side editor in `UX-FLOWS.md` Flow 11, and the pop-up generation flow + Settings copy in `DESIGN-2.0-HANDOFF.md:190-240` (see §11–§14). Pending owner sign-off on ClickUp task `17tnw2b0ntc`.
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` · **Section:** `1050:2` "Transcripts — Design 2.0" (page `0:1`) — now 15 frames (7 original + 8 added in this revision).
**ClickUp task:** `17tnw2b0ntc` (design), parent `17tnw2b0nt5`, blocks build subtask `17tnw2b0ntd`.
**Goal Contract:** `docs/delivery/goals/TASK-transcripts-design2-spec.md` (original pass); this revision is scoped small enough to track directly on the ClickUp task per the Operating Contract's right-sizing rule.
**Grounding:** this doc is built **from the shipped implementation**, not the other way around — `implementation/desktop/crates/selahcue-operator/dist/transcripts.js` (1605 lines), `dist/index.html` `#surface-transcripts` (~lines 2231–2306), `dist/app.js` (surface routing, `trActivate`, `showSurface`, `navGo`), `dist/app.css` (`.tr-*`/`.pp-gen-*` rules, `app.css:7985+`); cross-referenced against `docs/design/DETECTIONS-VIEW-spec.md` (mobile equivalent — state naming, not a template), `UX-CANONICAL.md` (binding keybinding/colour/safety rules), `UX-STATE-MATRIX.md`, `DESIGN-TOKENS.md` (`--sc-*`). `UX-FLOWS.md` Flow 11 is no longer treated as live guidance for this surface — see §11.

Frame link pattern: `https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=<id-with-dash>` (e.g. `1050-3`).

---

## 1. Why this surface had no Figma design, and why it does now

Transcripts is the **only** major desktop surface with zero Figma coverage anywhere in the file's 79 top-level nodes (confirmed by a full enumeration during planning; every other surface — console, screens, theme designer, presentation, settings, plan, pre-service, remote — has at least one named frame). It was built directly against the PRD/ADR record (86akcffvt core slice, then 86akgqdxr added detections + saved-draft view/edit, then 86akgqdwc/86akgqdw0/86akgqdx8 iterated the sermon-notes generation flow this month) without a preceding design pass. This handoff is the first one, produced **from the live implementation forward into Figma** — the same "code is truth, Figma catches up" direction the project already uses for `965:124` (RISK-205, PRD) and for `338:124`'s Settings expansion — not a redesign. Nothing in this document asks for a UI change; it records what already ships and gives it the same design-spec treatment (states, tokens, copy, a11y) every other surface already has.

## 2. What the surface actually does (read from the code, not assumed)

One workspace with two views:

- **List view** (`#tr-list-view`) — every saved transcript, most recent first: label, start date/time, duration (`h:mm:ss` at/above an hour, `m:ss` below — matching the Service Plan's own duration convention), segment count. Selecting one opens the detail view.
- **Detail view** (`#tr-detail-view`) — a single vertical workspace, not the split transcript↔notes layout `UX-FLOWS.md` Flow 11 originally sketched (see §9): a back button + header (title, meta, a "Notes generated / Notes not yet generated" badge), the **transcript log** (bounded sliding-window virtualizer, ADR-0026 — a service can run to thousands of segments and the DOM only ever mounts ~150 real rows at once, with two spacer elements keeping the scrollbar proportional to the full length), a **Detected scripture** panel (every reference persisted against this transcript, with an approximate position resolved from its source segment's timestamp, or "Position unknown" when the backend has no segment link), and a **Generate Sermon Notes** panel that is also where an *existing* saved draft renders — one render path for both a fresh generation and a reopened one.

Two things this surface is emphatically **not**: it is not the live in-session transcript panel (that is the console's own `.tr-seg` in the left column, a read-only live view with no Generate control of any kind — **corrected from the previous revision of this doc**, which wrongly described the console as having "its own tail-limited Generate"; per D1/D2 below, Generate exists on exactly one screen, this one) and it does not offer live editing of the raw transcript text (`.tr-line-corrected` renders an *existing* correction read-only; writing a new one is out of scope here, per the file's own header comment).

**Owner decisions this revision reflects (2026-09-30, ClickUp `17tnw2b0ntc`):**

- **D1 — post-service only.** Notes are generated only after a service has ended. While recording, Generate is visibly unavailable with a short explanation. There is no "generate so far" option. See §5 (still-recording state) and §11.
- **D2 — navigation.** ⌘7 "Transcript & Notes" opens this Transcripts page and shows as selected while it's open. The separate "Transcripts" ⌘8 menu item is removed — ⌘7 now carries both jobs. See §14.
- **Settings.** The AI card in Settings › Providers & Privacy keeps consent and provider settings only, plus a link to this page. It no longer has Generate, preview or result controls. See §13.

## 3. Design system reused (no new patterns)

Tokens (Design 2.0 `--sc-*`, from `DESIGN-TOKENS.md`, extracted from the shipped `app.css`):

| Role | Value | Role | Value |
|---|---|---|---|
| page base | `#0b0d12` | text | `#f4f6fb` |
| surface (cards) | `#14161d` | text-secondary | `#a7aebe` |
| elevated | `#1c1f28` | text-muted (labels only) | `#6b7383` |
| inset (log/preview boxes) | `#0f1116` | brand primary / hover | `#6e5cf0` / `#7e6eff` |
| border / strong | `#262a34` / `#363b47` | scripture gold | `#f2b84b` |

Status (one meaning per family, UX-CANONICAL §4): preview/verified-safe green `#35c08a` (soft `#10231c` / border `#1c3a2e`) — used for the "Notes generated" badge and the AI-generated draft's accent, never for "on air"; warn amber `#f5a524` (soft `#2a2415`) — used for an unverified scripture suffix and the "this will replace…" overwrite notice; info blue `#38bdf8` (soft `#10222b`) — used for the still-recording "Generate becomes available once it ends" notice and the "not configured" state.

Type: **Inter** (Regular/Medium/Semi Bold/Bold), matching every other Design 2.0 frame. Title 22 (list) / 17 (detail header) · panel heading 13 bold · body/list-card-name 14 · meta/body-secondary 12 · timestamp 11 tabular.

Component primitives reused verbatim from the shipped CSS, not reinvented: `.tr-card` (10px radius list row), `.tr-empty`/`.tr-error` (centered state card + retry button), `.tr-notes-badge` (999px pill, on/off tint), `.pp-generate` (the same primary gradient CTA the Settings live-session Generate uses), `.pp-gen-preview`/`.pp-gen-result` (the shared preview-and-confirm consent pattern — FR-132/135 — reused byte-for-byte from `settings.js`, including the exact caveat vocabulary: `section_empty`, `scripture_verification_incomplete`), `.pp-gen-edit-form` (the same editable-draft form Settings' own persisted-draft surface uses, ported here with `tr-`-prefixed element ids to avoid a duplicate-`id` collision in the shared document). **No new component language was introduced for this surface.**

**Chrome note:** like `SETTINGS-2.0-HANDOFF.md` §2, these frames clone the reference topbar (logo, surface label) from the shipped console chrome and do **not** redraw the global emergency footer (BLACKOUT / CLEAR ALL) or the app-menu dropdown — per `UX-CANONICAL.md` §3 that chrome is app-shell-global (`336:124`) and persists over every surface including Transcripts; it is never occluded by anything on this page.

## 4. Frames pushed to Figma

All under section `1050:2` "Transcripts — Design 2.0", page `0:1`.

| # | Frame | Node | What it shows |
|---|---|---|---|
| 1 | List — default | `1050:3` | Populated list, 3 example transcripts (one still `In progress`) |
| 2 | List — empty | `1051:2` | `#tr-empty`: no transcripts recorded yet |
| 3 | List — error | `1051:18` | `#tr-error`: load failed, with Retry |
| 4 | Detail — default | `1052:2` | Flagship: log with one corrected line, 2 detections, an existing AI-generated draft in **view** mode (one verified + one unverified reference) |
| 5 | Detail — still recording | `1053:2` | Empty detections panel + Generate **disabled** with the info notice (service not yet ended) |
| 6 | Generate — review & consent | `1053:33` | The preview-and-confirm step: full-text disclosure, "will REPLACE" overwrite warning, Cancel/Confirm |
| 7 | Notes — edit mode | `1053:55` | The editable draft form: title, summary, one outline section with a point + sub-point |
| 8 | Detail — 1280×720, scroll model | `1118:4` | **New.** The canonical scrolling fix: sticky detail head, capped/internally-scrolling log, unbounded notes panel, whole view scrolls as one column. See §11. |
| 9 | Detail — narrow window (900px) | `1118:29` | **New.** Stacked single column at the narrow-window floor, reduced padding, no horizontal scroll. See §11. |
| 10 | Generate — generating (in flight) | `1118:45` | **New.** The transient `aria-busy` sub-state of the Confirm button, drawn as its own frame per the acceptance criteria. |
| 11 | Generate — over-limit notice | `1118:51` | **New.** The 400,000-character clamp notice, amber, naming what's kept (the start of the transcript). |
| 12 | List & Detail — loading | `1118:58` | **New.** `aria-busy` list (stays visually empty) + detail header's "Loading…" title. |
| 13 | Settings AI card — redrawn | `1120:2` | **New.** No Generate/preview/result; consent + provider settings kept; corrected privacy copy; link to Transcripts. See §13. |
| 14 | App menu — ⌘7 selected, no ⌘8 | `1120:27` | **New.** "Transcript & Notes" shown with `aria-current="page"`/selected styling; no separate Transcripts item. See §14. |
| 15 | Detail — draft view + Regenerate | `1052:2` (updated) | Frame 4, updated: added a **Regenerate** button beside Edit on the saved-draft panel (`1052:41`), needed for the "regenerate/confirm/discard" state in Scope. |

Two states are still deliberately **not** separate frames — they are covered by an existing frame's own annotations rather than duplicated pixel-for-pixel: the **notes-not-yet-generated-but-service-ended** state (`#tr-notes-empty`, same shell as frame 5 minus the disabled/info treatment — Generate is enabled) and the edit-form **save-in-flight** sub-state (`Save` disabled + `aria-busy`, a one-line variant of frame 7). Both are specified in prose in §5 below.

## 5. State matrix

| Region | default / happy | empty | loading | error | disabled / permission | recovery / other |
|---|---|---|---|---|---|---|
| List | populated `1050:3` | no transcripts `1051:2` | `aria-busy="true"` on `#tr-list`, no dedicated frame (list stays visually empty until the fetch resolves) | load failed `1051:18` | — | — |
| Detail header | populated `1052:2` | — | title reads "Loading…", meta blank (no dedicated frame) | `#tr-detail-error` — load failed, Retry (same shape as list error) | — | — |
| Transcript log | populated, bounded window `1052:2` | 0-segment transcript renders an empty `.tr-log` (edge case — not separately designed; treat as the log simply having no rows, no special copy) | — | folds into the detail-header error (the whole detail view fails to load together) | — | a corrected line overlays raw (struck through) + corrected (bold) — shown in `1052:2` |
| Detected scripture | populated `1052:2` | "No scripture references were detected during this service." `1053:2` | — | — | — | — |
| Generate / notes | existing draft, view mode `1052:2` (**Regenerate** + Edit, both always present on a saved draft) | not yet generated, service ended: `#tr-notes-empty` text + **enabled** Generate button (same shell as `1053:2`, without the info banner and with the CTA active) | Generate clicked, in flight: CTA reads unchanged label but `aria-busy`, disabled, spinner — now its own frame `1118:45` | `not_configured` (info, "isn't available in this build yet") · `consent_required` (alert, links to Settings → Providers & Privacy) · `quota_exceeded` ("Monthly limit reached") · `transcript_too_short` / `no_transcript` (guarded before any network call) · `transport`/`malformed` (generic "Couldn't generate notes") · **over the 400,000-character limit — now its own frame `1118:51`**, amber, names what's kept (the start of the transcript, per `selahcue-cloud/src/transcript_bounds.rs:26`) | still recording: Generate disabled + info notice `1053:2` | Confirm step (review & consent) `1053:33`; edit mode `1053:55`; save-in-flight (Save disabled + `aria-busy`, sub-state of `1053:55`); **Regenerate** (from the draft view, `1052:41`) re-enters the same review & consent step `1053:33` with the "will REPLACE" warning already worded for this — Regenerate and Generate share one confirm flow, never a second path |
| List/Detail — loading | — | — | list: `aria-busy="true"` on `#tr-list`, stays visually empty (no skeleton shimmer) — now its own frame `1118:58`; detail header: title reads "Loading…", meta blank, same frame | — | — | — |
| Window size | 1280×720 and wide: single column capped at the shared content max-width, centered — frame `1118:4` | — | — | — | — | narrowest supported width (900px): stacked, reduced padding, no horizontal scroll — frame `1118:29` |

## 6. Copy voice (as shipped — recorded, not invented)

- Empty list: "No transcripts yet" / "Transcripts appear here after you record a service with transcription on." — plain, no jargon, tells the operator exactly what to do next.
- Error states never say "error" or cite a code to the operator: "Couldn't load your transcripts." / "Couldn't load this transcript." with a single Retry action.
- The still-recording guard is explained, not just disabled: "This service is still being recorded. Generate becomes available once it ends." — honesty over a silently-greyed control (FR-169's "never silent" principle, applied here too).
- The consent/preview step discloses exactly what will happen before it happens: character count, "Nothing leaves this device until you press Confirm," and — the one piece of copy unique to this surface versus the Settings live-tail Generate — "This is the complete transcript stored for this service — every recorded segment, not a recent window," because unlike the live console's tail-limited preview, this one genuinely is the whole thing.
- An overwrite is disclosed **before** it happens, in capitals for emphasis but not alarm: "This will REPLACE the sermon notes already generated for this transcript."
- Scripture verification is never silently omitted: a verified reference gets a subtle "✓" (secondary ink, not a loud green flag — this is a quiet confirmation, not a status light); an unverified one reads "(unverified — not found in the bundled text)" in the warn ink; and when the verification budget was exhausted before every reference could be checked, a note says so explicitly rather than leaving some references unmarked with no explanation.
- The AI-generated label and fabrication disclosure are **always** present alongside a generated or reopened draft (`.pp-gen-ai-label`/`.pp-gen-disclosure`), matching FR-123/128 and the Flow 11 "trust guard" principle.

## 7. Accessibility (testable)

- **Bounded rendering is itself an accessibility feature, not just a performance one:** `#tr-detail-log` is `role="log"` with implicit `aria-live="polite"`; the virtualizer diffs-and-patches (only rows that actually entered/left the window are added/removed) specifically so a scroll-driven recompute never re-announces the entire mounted window to assistive tech (ADR-0026, Cody/Quinn review). Diverging from this in implementation — e.g. a naive clear-and-rebuild virtualizer — would be a regression, not a neutral refactor.
- **Keyboard scrolling is native, not intercepted.** `tabindex="0"` on both the log and the detections list makes them standard keyboard-scrollable regions (arrows / Page Up-Down / Home / End — NFR-019); no custom key handling exists or should be reintroduced (ADR-0026 D3 deleted a five-key interception apparatus for exactly this reason — it fought WebKit's native scroll animation).
- **Focus management on view transitions:** opening a transcript moves focus into the log (`logEl.focus()`); returning to the list moves focus to the card that opened it, or the Retry button if that card is no longer present after a refresh (WCAG 2.4.3 — never leaves focus on a now-hidden element).
- **A live-region summary announces what just loaded:** `#tr-detail-live` (`aria-live="polite"`) reports "Opened <label>, N segments, M detected reference(s)" — a screen-reader user gets the shape of what they just opened without reading the whole log.
- **Colour is never the only cue:** the notes badge, verified/unverified scripture marks, and every error/info panel pair a colour with a text label or icon+label, never colour alone (WCAG 1.4.1) — consistent with `UX-CANONICAL.md` §4's cross-surface rule.
- **A correction is additive, never a silent rewrite:** both the raw (struck-through, `--sc-text-secondary`, audited AA-normal per the CSS comment) and corrected (`--sc-text`, bold) text render together — this is a content-accessibility decision as much as a trust one: nothing is hidden from a reader who wants to see what was actually said.
- **Untrusted transcript text is never `innerHTML`'d** — the preview box and every rendered line use `textContent` (`el()`'s implementation), which also means no screen-reader-breaking markup injection is possible from spoken content.

## 8. Component inventory — reused vs. new

**Reused verbatim (already shipped, already a Design 2.0 pattern elsewhere):**
`.pp-generate` primary CTA · `.pp-gen-preview`/`.pp-gen-result`/`.pp-gen-err`/`.pp-gen-info` consent-and-result panel family (from the Settings live-session Generate) · `.pp-gen-edit-form`/`.pp-edit-*` editable-draft form (from Settings' persisted-draft surface) · badge-pill pattern (`.tr-notes-badge`, same 999px/uppercase shape as Settings' status pills) · card row pattern (`.tr-card`, same 10px-radius bordered row as other list surfaces) · empty/error state card (`.tr-empty`/`.tr-error`, same centered-icon-plus-copy shape used elsewhere) · retry button.

**New to this surface, but composed entirely from existing primitives — no new visual language:**
the dual-panel bounded-window virtualizer chrome (`.tr-log` + `.tr-panel`/`.tr-det-log`, ADR-0026) — visually just scrollable panels with row primitives already in the system, but behaviourally the one genuinely new pattern here (a second sliding-window renderer alongside the transcript log, deliberately simpler — fixed row height, no Fenwick tree) · the detection row (`.tr-det-row`: gold reference + secondary position + right-aligned confidence, a three-column echo of the Detected Scriptures panel's row shape already specified at `332:124`, not duplicated design language) · the correction overlay (`.tr-line-corrected`, raw-struck-through + corrected-bold stacked pair) — genuinely new, first designed here.

## 9. Where this diverges from the earlier `UX-FLOWS.md` Flow 11 vision — settled, not open

`UX-FLOWS.md` Flow 11 ("Generate & edit sermon notes") sketches a **side-by-side split view** — raw transcript in a left column, editable notes in a right column, with click-to-jump timestamp links. What shipped, and what this revision confirms as the one agreed design at every window size, is a **single vertical workspace** — log, then detections, then notes, stacked — with no timestamp-linked jump-to-source interaction from a note item back into the log (FR-124's "note items link to transcript timestamps" is not implemented on this surface).

**This is no longer an open divergence.** As of this revision (17tnw2b0ntc, 2026-09-30), Flow 11's side-by-side split is **superseded** for this surface — see §12 for the formal pointer. The single-column model is the design at 1280×720, at wide windows, and at the narrow-window floor alike (§11); there is no width at which a split-pane layout is the target.

- Per RISK-205 ("shipped code is truth, Figma catches up, not the reverse"), this handoff documents the **shipped single-column layout** as the permanent target, not a stopgap pending a future split-pane build.
- The one real open item inherited from Flow 11 is FR-124 (timestamp-linked note navigation) — explicitly a **non-goal** of this ticket (see parent `17tnw2b0nt5`'s non-goals, tracked separately as 86akgqdw0 / 17tnw2axprv). Nothing here blocks it from being designed later as an addition to the single-column layout; it does not revive the split-pane shape.

## 10. Where this diverges from `DESIGN-2.0-HANDOFF.md`'s Settings generation flow — settled, not open

`DESIGN-2.0-HANDOFF.md:190-240` (§5.7) describes a **pop-up/modal generation flow** launched from the Settings AI card (consent modal → generating progress → notes-ready preview, all as dialogs over Settings), plus a privacy line ("Only your completed transcript is sent for processing…") that in the shipped code was never true — the Settings card actually sent at most `window.scCompletedTranscript`, a 60-segment tail (`OPERATOR_TRANSCRIPT_TAIL`), not the complete stored transcript.

**As of this revision, both are superseded.** Settings has no generation flow at all — modal or otherwise. See §13 for the redrawn card and the corrected copy, and §12 for the formal superseded pointer into `DESIGN-2.0-HANDOFF.md` itself.

## 11. Scrolling, content column, and window-size rules (new — the core of this revision)

This is the part the original pass (§1–§10 above) never specified, and the reason the shipped surface cuts content off. Three rules, in order of how often they'll come up in review:

### 11.1 Which region scrolls

The bug in the shipped CSS (`app.css:7997` `#surface-transcripts { overflow: hidden }`, `.tr-log` at `flex: 1` being the *only* scrolling region, `.tr-panel`/`.tr-gen` at `flex: none` with no height cap) is that **one region was made to scroll by starving every other region of space**, rather than by any of them getting a bounded height on purpose. Once a saved draft or an edit form is tall, the log gets shrunk to zero and the rest is simply cut off — there is no scrollbar anywhere for it.

The fix is not "make the log scroll harder." It's to separate two different jobs that were living in the same region:

- **The transcript log's own bounded-window virtualizer (ADR-0026) is a performance mechanism, not a viewport-filling one.** It exists so a thousand-segment service doesn't mount a thousand DOM rows — it does **not** need to occupy 100% of the available vertical space to do that job. Give it a **capped height** instead: `min-height: 220px; max-height: min(48vh, 480px);` with its own internal `overflow-y: auto` (unchanged from today — ADR-0026's scroll-anchoring behaviour is untouched). It becomes a "window into a long transcript" that settles at a sensible size, not a panel that either eats everything or shrinks to nothing.
- **The detail view itself (`.tr-detail`) becomes the outer scroll container.** Change `#surface-transcripts.surface-pad.active` from `overflow: hidden` to allow its child `.tr-detail` to scroll: `.tr-detail { overflow-y: auto; }`. Everything below the capped log — the detections panel (already capped at 220px via `.tr-det-log`, unchanged) and the notes/generate panel (`.tr-gen`, kept `flex: none` with **no height cap** — a draft or edit form is allowed to be as tall as its content needs) — now sits in normal block flow under the log. However tall the notes panel gets, scrolling the *page* (not the log) reaches every part of it: title, points, Regenerate, Edit, Confirm, Discard.
- **The detail header (`.tr-detail-head`) becomes `position: sticky; top: 0;`** inside that same scroll container, so the back button and the service identity stay visible while reviewing a long draft. (This is an explicit addition beyond what the ticket strictly required — flagged as a design decision, not a guess: it costs nothing structurally since the header was already `flex: none`, and it matches how a reader expects "back" to stay reachable on a long page. If the owner would rather it scroll away with the rest, that's a one-line revert of `position: sticky`.)
- **The list view is unchanged** — `.tr-view { overflow-y: auto }` already does the right thing; the bug is isolated to the detail view.

Concretely, against the current rules at `app.css:7985+`:

```css
#surface-transcripts.surface-pad.active {
  padding: 0;
  overflow: hidden;         /* unchanged — the app shell itself still doesn't scroll */
  display: flex;
  flex-direction: column;
}
.tr-detail {
  overflow-y: auto;         /* NEW — .tr-detail is now the outer scroll container */
}
.tr-detail-head {
  flex: none;
  position: sticky;         /* NEW */
  top: 0;
  z-index: 1;
  background: var(--sc-surface);   /* must be opaque — content scrolls under it */
}
.tr-log {
  flex: none;                       /* CHANGED from flex: 1 */
  min-height: 220px;                /* NEW */
  max-height: min(48vh, 480px);     /* NEW — was unbounded-by-starvation before */
  overflow-y: auto;                 /* unchanged — still its own virtualizer viewport */
}
.tr-panel { flex: none; }           /* unchanged */
.tr-gen   { flex: none; }           /* unchanged — no cap, grows to content */
```

This is the exact mechanism shown in Figma frame `1118:4` (1280×720, notes taller than the visible viewport) — screenshot-verified: the log sits as a bounded box with its own scroll affordance, the notes panel below it is fully present in the DOM (not clipped), and a page-level scrollbar on the right is what reaches it.

### 11.2 One shared content column and its max-width

Today each section (`.tr-view`, `.tr-detail-head`, `.tr-log`, `.tr-panel`, `.tr-gen`) pads itself independently to 28px with no shared column and no `max-width` — so on a very wide window, lines of transcript text and notes stretch edge-to-edge and become hard to read.

**Decision: reuse the Settings precedent exactly.** `.pp-wrap`/`.set-page` in Settings (`app.css:7513`, `7528`) already cap their content at `max-width: 1180px`. Apply the same value here rather than inventing a new number: every one of `.tr-view`, `.tr-detail-head`, `.tr-log`, `.tr-panel`, `.tr-gen` gets

```css
max-width: 1180px;
margin-inline: auto;
width: 100%;
box-sizing: border-box;
```

on top of its existing padding. This creates one shared, centered content column across every stacked region (header, log, detections, notes) without restructuring the DOM into a new wrapper element — each region keeps its own left/right padding (28px ≥ 900px, 16px below — see §11.3) inside that shared max-width.

### 11.3 Narrow-window width and stacking behaviour

**Decision: reuse the Pre-service Check precedent exactly.** That screen's own narrow-window rule (`app.css:7124`, `@media (max-width: 900px)`) is the pattern the ticket names as the closest fit, and Settings' sidebar collapse and the Service Plan builder both also break at 900px — so 900px is already this app's established "narrow shell" floor, not a new number invented for this surface.

```css
@media (max-width: 900px) {
  .tr-view,
  .tr-detail-head,
  .tr-log,
  .tr-panel,
  .tr-gen {
    padding-left: 16px;   /* was 28px */
    padding-right: 16px;
  }
  .tr-log {
    max-height: 34vh;     /* was min(48vh, 480px) — leaves relatively more room
                              for the detections + notes panels below it on a
                              short, narrow window */
  }
}
```

**How the layout stacks below 900px:** it doesn't have to change shape, because it was never anything but a single column (§9 — Flow 11's side-by-side split is superseded at every width, not just this one). What changes at the narrow floor is purely padding and the log's height cap — there is **no horizontal scroll** at any width down to 900px, matching every other screen's own narrow-window rule. This is shown in Figma frame `1118:29`.

### 11.4 Verified at the three required sizes

- **1280×720** — frame `1118:4`. The default target size; the scroll model in §11.1 is shown here with a notes draft deliberately taller than the 720px viewport.
- **Wide window** — the same rules apply; because of the `max-width: 1180px` column (§11.2), a wide window doesn't stretch content, it just adds neutral page-background margin either side of the centered column. No separate frame needed — `1118:4`'s column-behaviour annotation covers it.
- **Narrowest supported width (900px)** — frame `1118:29`, per §11.3.

All three are screenshot-verified at a readable zoom (see the design session's evidence; screenshots attached to the ClickUp comment).

## 12. Superseded passages — formal pointers

Per Scope, the conflicting passages named in Context are marked superseded at their source rather than silently reconciled:

- **`docs/design/UX-FLOWS.md` Flow 11** ("Generate & edit sermon notes", the side-by-side transcript↔notes split view): superseded by §9 and §11 of this document. A superseded-notice has been added directly above Flow 11's heading in that file, pointing here.
- **`docs/design/DESIGN-2.0-HANDOFF.md:190-240`** (§5.7 Settings — the pop-up/modal generation flow, the usage-meter-gated Generate button, and the "Only your completed transcript is sent…" privacy line): superseded by §10 and §13 of this document. A superseded-notice has been added directly above that section in that file, pointing here.

## 13. Settings › Providers & Privacy — AI card, redrawn (no Generate)

Figma frame `1120:27`... *(see `1120:2`)*. Per the owner decision, the card keeps consent and provider settings only:

**Kept, unchanged in substance:**
- The consent toggle ("Enable cloud processing for sermon notes").
- **Default notes template** and **Preferred Bible translation** selects.
- **Include in notes** toggles (all 8).

**Removed entirely:**
- The **Generate Sermon Notes** button (`settings.js` button around line 439).
- The preview-and-confirm step (`openGenPreview`, `settings.js:605-667`).
- The result/edit panel (`confirmGenerate`, `settings.js:675-689`, and everything `run_note_generation` rendered back into this card).
- The usage/quota meter — it was scoped to this card's own Generate action; with no Generate here, a quota count with nothing to spend it on would be confusing, not reassuring. (If the owner wants generation-allowance visibility to persist somewhere, the natural home is the Transcripts page itself, next to its own Generate button — flagged as an **open question**, not decided here, since it's outside this ticket's scope.)

**Added:**
- A plain link row, styled as a link (not a button — it's navigation, not an action): **"Open Transcripts to generate sermon notes →"**, with a one-line sub-caption: "Notes are generated only on a stored, ended transcript — never from here."

**Corrected privacy copy.** The old line — "Only your completed transcript is sent for processing — never live audio, and never during the service. Nothing is sent until you press Generate." — was untrue in two ways: there was no way to "press Generate" on this card to trigger the send (once Generate is removed, that clause is simply dead), and even when the button existed, this card actually sent a 60-segment tail (`window.scCompletedTranscript`, `OPERATOR_TRANSCRIPT_TAIL = 60`), not the complete transcript. The new line states what the *system* does, truthfully, in a form that doesn't go stale the moment this card's own controls change:

> "Only a saved, ended service's complete transcript is sent — never live audio, never during the service, and never a recent-segments window. Subject to a 400,000-character limit."

This wording is anchored to the actual data path (`transcript_generate_notes`, stored text, `selahcue-cloud/src/transcript_bounds.rs:26`'s 400,000-character cap) rather than to this card's own UI, so it stays true regardless of which screen initiates generation.

## 14. App menu — ⌘7 opens Transcripts, no ⌘8 item

Figma frame `1120:27`. Per D2:

- The **"Transcript & Notes"** item (⌘7, currently `data-surface="console" data-focus="transcript"` at `index.html:61-64`) gets `data-surface="transcripts"` and drops `data-focus` entirely — it now opens this page directly, the same route the old ⌘8 item used.
- Subtitle copy changes from "Live transcript + sermon AI" to **"Review transcripts & generate notes"** — the old copy was written for a live-tail deep-link into the console; the new destination is the saved-transcript workspace, and the copy should say so.
- Shown with a **selected state** (left accent bar + elevated background, `aria-current="page"`) while the Transcripts surface is open — `showSurface()`'s existing logic (`app.js:1536-1539`, "mark only the primary entry for a surface as current") already does this correctly for any item whose `data-surface` matches with no `data-focus` set; removing `data-focus` from this item is what makes that logic pick it up, no new code path needed.
- The separate **"Transcripts"** item (⌘8, `index.html:72-78`) is **removed** entirely — its markup, not just its shortcut, since a hidden-but-present duplicate route would still be reachable via the command palette or direct DOM inspection.
- No two remaining items share a shortcut once ⌘8 is removed (verified against the menu's live-DOM-order chord derivation in `app.js`'s "Global ⌘/Ctrl+1–8" block — removing an item shifts nothing, since chords are derived from order, not from a fixed slot).

## 15. Implementation notes & open questions

- Farah implementing this surface's *next* increment should treat frames 1–4 (list default/empty/error, detail default) and the §11 scrolling/responsive rules as the near-term priority — together they cover the everyday path and the two reported bugs (layout cut-off, no window-size response). Frames 5–7 (still-recording, consent preview, edit mode) already exist in the live app in substance; §11's CSS changes apply around them, not to their content.
- **Open question (design, minor) — carried from the original pass:** the 0-segment transcript log and the mid-recomputed-window-resize cases have no distinct visual treatment beyond "the log has nothing/reflows" — flagged here rather than silently assumed complete.
- **Open question (design, new, default chosen) — sticky detail header:** §11.1 makes the detail header `position: sticky`. This wasn't explicitly requested in Scope; the default was chosen because it's low-cost and matches user expectation for a long scrolling page. If the owner disagrees, it's a one-line revert.
- **Open question (product, new) — generation-allowance visibility after removing the Settings quota meter:** see §13. Not decided here; flagged for the owner/PM to place (or explicitly decline) on the Transcripts page.
- FR-124 (timestamp-linked note navigation) remains out of scope for this ticket (non-goal, per parent `17tnw2b0nt5`) and is not reopened by this revision — see §9.
- No implementation file was modified to produce this handoff — verified by `git status --porcelain implementation/`.

---

**Verdict:** this revision is the one agreed design for transcript review and sermon-note generation — scrolling model, shared content column, narrow-window floor, and the Settings/menu redraws are all specified concretely enough to implement without guessing. Pending owner sign-off on ClickUp `17tnw2b0ntc`; the build subtask `17tnw2b0ntd` remains blocked until that sign-off lands.
