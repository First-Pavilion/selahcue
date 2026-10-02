# SelahCue — Transcripts (Design 2.0) Handoff

**Status:** REVISED (v2) 2026-09-30 (17tnw2b0ntc) — this v2 revision is **the one agreed design** for transcript review and sermon-note generation. It supersedes both the shipped-code layout bugs **and** the v1 revision of this doc/section — the owner reviewed v1's Figma frames (section `1050:2`) and correctly rejected them as low-fidelity snapshots traced from the broken shipped code, not a design. v2 is built at full fidelity, reusing real cloned components from the file's own polished reference frames (`349:124` SelahCue AI Generate flow, `338:124`/`348:124` Settings, `336:124`/`336:133` App Navigation) rather than hand-drawn boxes. It supersedes the side-by-side editor in `UX-FLOWS.md` Flow 11 and the pop-up generation flow + stale Settings copy in `DESIGN-2.0-HANDOFF.md:190-240` (see §11–§14). Pending owner sign-off on ClickUp task `17tnw2b0ntc`.
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` · **Canonical section:** `1127:2` **"Transcripts — Design 2.0 (v2 — full fidelity)"** (page `0:1`) — 14 frames, all built this revision. The old section `1050:2` is renamed `SUPERSEDED — do not build from` and left in place only for history; nothing under it is current.
**ClickUp task:** `17tnw2b0ntc` (design), parent `17tnw2b0nt5`, blocks build subtask `17tnw2b0ntd`.
**Goal Contract:** `docs/delivery/goals/TASK-transcripts-design2-spec.md` (original pass); this revision is scoped small enough to track directly on the ClickUp task per the Operating Contract's right-sizing rule.
**Grounding:** this doc is built **from the shipped implementation's intent**, not its broken layout — `implementation/desktop/crates/selahcue-operator/dist/transcripts.js` (1605 lines), `dist/index.html` `#surface-transcripts` (~lines 2231–2306), `dist/app.js` (surface routing, `trActivate`, `showSurface`, `navGo`), `dist/app.css` (`.tr-*`/`.pp-gen-*` rules, `app.css:7985+`) — cross-referenced against `docs/design/DETECTIONS-VIEW-spec.md` (mobile equivalent — state naming, not a template), `UX-CANONICAL.md` (binding keybinding/colour/safety rules), `UX-STATE-MATRIX.md`, `DESIGN-TOKENS.md` (`--sc-*`), and — for visual fidelity — the real, already-polished Figma frames `349:124`, `338:124`/`348:124`, `336:124`/`336:133`, cloned and adapted rather than redrawn. `UX-FLOWS.md` Flow 11 is no longer treated as live guidance for this surface — see §11. ClickUp `17tnw2az0g8` (D7, weekly generation allowances) is reflected in the Generate-flow copy — see §16.

Frame link pattern: `https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=<id-with-dash>` (e.g. `1127-2`).

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

**Chrome note:** like `SETTINGS-2.0-HANDOFF.md` §2, these frames clone the reference topbar (logo, surface label) from the shipped console chrome and do **not** redraw the global emergency footer (BLACKOUT / CLEAR ALL) — per `UX-CANONICAL.md` §3 that chrome is app-shell-global (`336:124`) and persists over every surface including Transcripts; it is never occluded by anything on this page. The app-menu dropdown **is** drawn, once, as its own dedicated frame (§4 row 4) because D2's selected-state change specifically concerns it.

### 3a. v2 fidelity note: real nodes cloned, not redrawn

The v1 pass (superseded, §0/status line) built every frame from primitive rectangles and text with colours approximated from the token table above. The owner correctly rejected this as "a low-fidelity snapshot traced from shipped code… not a design" and pointed at `349:124` ("SelahCue AI — Generate flow") as the bar to match. v2 closes that gap by **cloning real nodes from the file** wherever one exists, inspecting their exact `fills`/`strokes`/`cornerRadius`/`effects` first rather than re-guessing them:

- **Topbar** — every list/detail frame's topbar is `338:125.clone()` (Settings' real topbar: logo mark, wordmark, divider, page label, session-status chip), with only the label and session text edited.
- **Generate-flow cards** — the Consent (`1133:2`) and Generating (`1133:36`) frames are `349:136.clone()` / `349:173.clone()` respectively; the Notes-ready card embedded in every Detail frame is `349:204.clone()`. Copy is edited via `findAllWithCriteria({types:['TEXT']})` + exact-string match, never rebuilt.
- **App menu** (`1135:2`) — the entire panel is `336:133.clone()`; only the Transcript & Notes row's fill (elevated) and a new 3px accent-bar rectangle were added, plus its subtitle text edited.
- **Settings AI card** (`1135:78`) — the entire card is `348:124.clone()`; the Generate button and usage-meter frames were located by exact text match and removed, the privacy paragraph's text was edited in place, and a new link row was appended matching the card's own padding rhythm.
- **New-but-matching primitives** (over-limit notice, edit-mode form, still-recording card, list/log/detections cards) reuse the exact hex values, corner radii (16 for outer cards, 12 for list cards, 8–10 for inner rows/badges), and auto-layout padding rhythm read directly off the cloned nodes above — never re-approximated from memory.

This is why the result "looks like it belongs next to `349:124`": large parts of it *are* `349:124`, `338:124`/`348:124`, and `336:133`, with only the words changed.

## 4. Frames pushed to Figma

All under section `1127:2` **"Transcripts — Design 2.0 (v2 — full fidelity)"**, page `0:1`, placed beside (not inside) the superseded `1050:2`. Every frame below either clones a real node from `349:124`/`338:124`/`348:124`/`336:124`/`336:133` and edits only its copy, or is newly built using the exact same tokens, radii, and card chrome read directly off those nodes (see §3a). None are hand-drawn approximations.

**Row 1 — List view:**

| # | Frame | Node | What it shows |
|---|---|---|---|
| 1 | List — populated | `1128:2` | Real topbar (cloned `338:125`), 3 example transcripts with icon chips, meta, and notes-status badges |
| 2 | List — empty | `1128:46` | `#tr-empty` card: no transcripts recorded yet |
| 3 | List — error | `1128:67` | `#tr-error` card: load failed, with Retry |
| 4 | List — loading | `1128:88` | `aria-busy` note: list stays visually empty until the fetch resolves |

**Row 2 — Detail view (the scroll-model fix, §11):**

| # | Frame | Node | What it shows |
|---|---|---|---|
| 5 | Detail — 1280×720, default | `1132:2` | Flagship: sticky head, capped/internally-scrolling log, detections panel, the real Notes-ready card (cloned `349:204`) embedded as `.tr-gen` |
| 6 | Detail — scrolled (notes taller than window) | `1132:81` | Same content, frame extended to 900px tall with an illustrative 720px fold line + page-scrollbar affordance, showing every control (Regenerate/Edit at the bottom) is reachable by scrolling `.tr-detail`, not `.tr-log` |
| 7 | Detail — still recording | `1132:163` | Generate **disabled** (opacity-dimmed) + the info notice, matching D1 |
| 8 | Detail — narrow window (900px) | `1132:208` | Stacked single column, 16px padding, reduced log height, no horizontal scroll |

**Row 3 — Generate flow, hosted on the Transcripts page (reuses `349:124` directly, §16):**

| # | Frame | Node | What it shows |
|---|---|---|---|
| 9 | Consent — before send | `1133:2` | Cloned from `349:136`; copy corrected to name the complete saved transcript and the weekly allowance (D7) |
| 10 | Generating (in flight) | `1133:36` | Cloned from `349:173`, reused **verbatim** — no copy in this step referenced the monthly/Settings framing, so nothing needed correcting |
| 11 | Over-limit notice | `1133:64` | New card, same outer/inner chrome + amber `pp-gen-info` treatment as the consent card, naming the 400,000-character clamp |
| 12 | Edit mode | `1133:80` | New card, same chrome as the Ready card, with labelled input fields (title/summary/points) and Cancel/Save |

**Row 4 — Settings and navigation:**

| # | Frame | Node | What it shows |
|---|---|---|---|
| 13 | App menu — Transcript & Notes selected | `1135:2` | The **entire app-menu panel cloned from `336:133`** (already has no ⌘8 item in the source spec — D2 was already reflected there) with a selected-state accent bar added to the Transcript & Notes row and its subtitle corrected |
| 14 | Settings AI card — redrawn | `1135:78` | The **entire card cloned from `348:124`**, Generate button + usage meter removed, privacy copy corrected, link to Transcripts added |

Two states are still deliberately **not** separate frames — covered by an existing frame's own content rather than duplicated pixel-for-pixel: the **notes-not-yet-generated-but-service-ended** state (same shell as frame 7 minus the disabled/info treatment — Generate is enabled) and the edit-form **save-in-flight** sub-state (`Save` disabled + `aria-busy`, a one-line variant of frame 12). Both are specified in prose in §5 below.

**What happened to the old section (`1050:2`) and the v1 frames (`1118:*`, `1120:*`):** renamed, not deleted — `1050:2` is now titled `SUPERSEDED — do not build from — Transcripts (Design 2.0, low-fidelity code trace) — see "Transcripts — Design 2.0 (v2 — full fidelity)" section`, and every v1-only frame (`1118:4`, `1118:29`, `1118:45`, `1118:51`, `1118:58`, `1120:2`, `1120:27`) is prefixed `SUPERSEDED (low-fi) —`. Nothing was deleted so the review history stays intact, but there is exactly one current design now, not two competing ones.

## 5. State matrix

| Region | default / happy | empty | loading | error | disabled / permission | recovery / other |
|---|---|---|---|---|---|---|
| List | populated `1128:2` | no transcripts `1128:46` | `aria-busy="true"` on `#tr-list`, list stays visually empty until the fetch resolves — `1128:88` | load failed `1128:67` | — | — |
| Detail header | populated `1132:2` | — | title reads "Loading…", meta blank (same shell as `1128:88`'s note, no separate frame needed — it's a text swap) | `#tr-detail-error` — load failed, Retry (same shape as list error) | — | — |
| Transcript log | populated, bounded internally-scrolling window `1132:2` | 0-segment transcript renders an empty `.tr-log` (edge case — not separately designed; treat as the log simply having no rows, no special copy) | — | folds into the detail-header error (the whole detail view fails to load together) | — | a corrected line overlays raw (struck through) + corrected (bold) — same treatment as `1132:2`'s log rows |
| Detected scripture | populated `1132:2` | "No scripture references were detected during this service." `1132:163` | — | — | — | — |
| Generate / notes | existing draft, view mode — the real Notes-ready card (cloned `349:204`) embedded in `1132:2`/`1132:81`/`1132:208` (**Regenerate** + Edit draft, both always present on a saved draft) | not yet generated, service ended: `#tr-notes-empty` text + **enabled** Generate button (same shell as `1132:163`, without the info banner and with the CTA active) | Generate clicked, in flight — cloned `349:173` verbatim, its own frame `1133:36` | `not_configured` (info, "isn't available in this build yet") · `consent_required` (alert, links to Settings → Providers & Privacy) · `quota_exceeded` ("No generations left this week") · `transcript_too_short` / `no_transcript` (guarded before any network call) · `transport`/`malformed` (generic "Couldn't generate notes") · **over the 400,000-character limit — its own frame `1133:64`**, amber, names what's kept (the start of the transcript, per `selahcue-cloud/src/transcript_bounds.rs:26`) | still recording: Generate disabled + info notice `1132:163` | Consent step (review & send) `1133:2`; edit mode `1133:80`; save-in-flight (Save disabled + `aria-busy`, sub-state of `1133:80`); **Regenerate** (from the draft view) re-enters the same consent step `1133:2` with the "will REPLACE" warning already worded for this — Regenerate and Generate share one confirm flow, never a second path |
| List/Detail — loading | — | — | list: `1128:88`; detail header: title reads "Loading…", meta blank | — | — | — |
| Window size | 1280×720 and wide: single column capped at the shared content max-width, centered — frame `1132:2`, scrolled variant `1132:81` | — | — | — | — | narrowest supported width (900px): stacked, reduced padding, no horizontal scroll — frame `1132:208` |

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

This is the exact mechanism shown in Figma frame `1132:81` (1280×900, the frame is drawn taller than the real 720px viewport specifically to show the notes panel fully present and reachable) — screenshot-verified: the log sits as a bounded box with its own internal scroll, an illustrative fold line marks where the real 720px viewport ends, the notes panel below it is fully present in the DOM (not clipped), and a page-level scrollbar on the right is what reaches it, not the log's own scrollbar.

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

**How the layout stacks below 900px:** it doesn't have to change shape, because it was never anything but a single column (§9 — Flow 11's side-by-side split is superseded at every width, not just this one). What changes at the narrow floor is purely padding and the log's height cap — there is **no horizontal scroll** at any width down to 900px, matching every other screen's own narrow-window rule. This is shown in Figma frame `1132:208`.

### 11.4 Verified at the three required sizes

- **1280×720** — frame `1132:2`. The default target size.
- **Notes taller than the window** — frame `1132:81`, per §11.1: the scroll model shown with a notes draft deliberately taller than the 720px viewport.
- **Wide window** — the same rules apply; because of the `max-width: 1180px` column (§11.2), a wide window doesn't stretch content, it just adds neutral page-background margin either side of the centered column. No separate frame needed — `1132:2`'s column behaviour covers it.
- **Narrowest supported width (900px)** — frame `1132:208`, per §11.3.

All three are screenshot-verified at a readable zoom (see the design session's evidence; screenshots attached to the ClickUp comment).

## 12. Superseded / re-aligned passages — formal pointers

Per Scope, the conflicting passages named in Context are marked superseded or re-aligned at their source rather than silently reconciled:

- **`docs/design/UX-FLOWS.md` Flow 11** ("Generate & edit sermon notes", the side-by-side transcript↔notes split view): superseded by §9 and §11 of this document. A superseded-notice has been added directly above Flow 11's heading in that file, pointing here. This one is a genuine supersession — Flow 11's split-pane layout is not used anywhere.
- **`docs/design/DESIGN-2.0-HANDOFF.md:190-240`** (§5.7 Settings): **re-aligned, not struck**, per the owner's correction. The Settings-hosted Generate button, usage meter, and the untrue privacy line are still removed from the Settings card (§13) — that part is superseded. But the **`349:124` consent → generating → notes-ready visual flow itself is not superseded** — it is the correct, polished reference, and v2 reuses it directly (cloned, not redrawn) as the Transcripts page's own `.tr-gen` generation flow (§4 row 3, §16). `DESIGN-2.0-HANDOFF.md` §5.7 now says explicitly that the `349:124` flow lives on the Transcripts page, not in a Settings pop-up, rather than marking it struck through.

## 13. Settings › Providers & Privacy — AI card, redrawn (no Generate)

Figma frame `1135:78` — the **entire real card cloned from `348:124`**, not redrawn. Per the owner decision, the card keeps consent and provider settings only:

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

> "Sermon notes are made from text only: the complete saved transcript of a recording that has ended, up to 400,000 characters. Nothing is sent while that transcript is still recording, and nothing is sent until you review the exact text and confirm. Cloud transcription (above) is a separate setting and does stream microphone audio while it is on."

**Superseded wording (owner decision, from the privacy review of PR #129):** the earlier draft of this line — "…never live audio, never during the service, and never a recent-segments window…" — overclaimed. Stopping listening ends a transcript, so a transcript from the first half of a still-running service can legitimately be sent, and "never live audio" sat next to a card offering cloud transcription, which does stream audio. The sentence above says only what the code enforces.

This wording is anchored to the actual data path (`transcript_generate_notes`, stored text, `selahcue-cloud/src/transcript_bounds.rs:26`'s 400,000-character cap) rather than to this card's own UI, so it stays true regardless of which screen initiates generation.

## 14. App menu — ⌘7 opens Transcripts, no ⌘8 item

Figma frame `1135:2` — the **entire app-menu panel cloned from `336:133`**, not redrawn; the source spec already has no ⌘8 item (D2 was already reflected there before this ticket), so this frame's job is to show the *selected* state for Transcript & Notes, not to remove anything. Per D2:

- The **"Transcript & Notes"** item (⌘7, currently `data-surface="console" data-focus="transcript"` at `index.html:61-64`) gets `data-surface="transcripts"` and drops `data-focus` entirely — it now opens this page directly, the same route the old ⌘8 item used.
- Subtitle copy changes from "Live transcript + sermon AI" to **"Review transcripts & generate notes"** — the old copy was written for a live-tail deep-link into the console; the new destination is the saved-transcript workspace, and the copy should say so.
- Shown with a **selected state** (left accent bar + elevated background, `aria-current="page"`) while the Transcripts surface is open — `showSurface()`'s existing logic (`app.js:1536-1539`, "mark only the primary entry for a surface as current") already does this correctly for any item whose `data-surface` matches with no `data-focus` set; removing `data-focus` from this item is what makes that logic pick it up, no new code path needed.
- The separate **"Transcripts"** item (⌘8, `index.html:72-78`) is **removed** entirely — its markup, not just its shortcut, since a hidden-but-present duplicate route would still be reachable via the command palette or direct DOM inspection.
- No two remaining items share a shortcut once ⌘8 is removed (verified against the menu's live-DOM-order chord derivation in `app.js`'s "Global ⌘/Ctrl+1–8" block — removing an item shifts nothing, since chords are derived from order, not from a fixed slot).

## 16. The generation flow hosted on the Transcripts page (reuses `349:124` directly)

Per the owner's direction, the `349:124` "SelahCue AI — Generate flow" (consent → generating → notes ready) is the correct, already-polished reference for this interaction — it is **not** superseded, and v2 hosts it directly on the Transcripts page rather than reinventing it:

- **Consent — before send** (`1133:2`, cloned `349:136`). Copy corrected in two places: the disclosure line now reads *"The complete saved transcript of this ended service is sent"* (was *"Your completed transcript is sent"* — the new wording makes explicit it's the complete, saved, ended-service transcript, matching the truthful-privacy requirement elsewhere in this doc), and the subtitle now reads *"…this service's complete stored transcript (subject to a 400,000-character limit)"*.
- **Generating** (`1133:36`, cloned `349:173`) — reused **verbatim**. Its copy ("Transcript sent securely", "Your audio never left this device") was already accurate and provider-agnostic; nothing referenced Settings or a monthly cadence, so nothing needed correcting.
- **Notes ready** (embedded in every Detail frame, cloned `349:204`) — copy corrected for D7 (see below) and for the on-page editor: the usage line now reads *"2 of 10 generations used this week"* (was *"13 of 40 generations used this month"*), and the secondary button now reads **"Edit draft"** (was *"Open in editor"* — on this single-page surface, editing happens inline in the same `.tr-gen` panel, not a separate editor route, so the label says so).
- **Edit mode** (`1133:80`) and **over-limit notice** (`1133:64`) are new cards built to match the same outer/inner card chrome, corner radii, and button styles read directly off the cloned cards above (§3a) — there was no existing polished reference for either state to clone from.

### D7 — weekly generation allowances (ClickUp `17tnw2az0g8`)

Per the linked ClickUp decision, generation allowances are weekly, not monthly. Every allowance-count string in this design says **"this week"**, not "this month": the consent step's *"Uses 1 of your 10 remaining generations this week"* and the ready card's *"2 of 10 generations used this week"*. This also **resolves §15's earlier open question 2** (where generation-allowance visibility should live now that the Settings quota meter is removed) — the answer is: **on the Transcripts page itself**, inside the Generate flow cards it already hosts, which is exactly where `349:124`'s own usage line lived before this design moved the whole flow here. This is recorded as a **proposal**, not a unilateral decision — it follows directly from D7 plus the reused `349:124` layout, but the owner should confirm it's the intended placement in the sign-off comment.

## 17. Implementation notes & open questions

- Farah implementing this surface's *next* increment should treat frames 1–5 (list states, detail default) and the §11 scrolling/responsive rules as the near-term priority — together they cover the everyday path and the two reported bugs (layout cut-off, no window-size response).
- **Open question (design, minor) — carried from the original pass:** the 0-segment transcript log and the mid-recomputed-window-resize cases have no distinct visual treatment beyond "the log has nothing/reflows" — flagged here rather than silently assumed complete.
- **Open question (design, default chosen) — sticky detail header:** §11.1 makes the detail header `position: sticky`. This wasn't explicitly requested in Scope; the default was chosen because it's low-cost and matches user expectation for a long scrolling page. If the owner disagrees, it's a one-line revert.
- **Open question (product, proposal made) — generation-allowance visibility:** §16 proposes the Transcripts page's own Generate flow cards as the home for weekly-allowance visibility (resolving the prior open question). Flagged for explicit owner confirmation, not assumed.
- FR-124 (timestamp-linked note navigation) remains out of scope for this ticket (non-goal, per parent `17tnw2b0nt5`) and is not reopened by this revision — see §9.
- No implementation file was modified to produce this handoff — verified by `git status --porcelain implementation/`.

---

**Verdict:** this v2 revision is the one agreed design for transcript review and sermon-note generation, built at the same fidelity as `349:124`/`338:124`/`336:124` by cloning their real nodes rather than approximating them — scrolling model, shared content column, narrow-window floor, the reused Generate flow with weekly-allowance wording, and the Settings/menu redraws are all specified concretely enough to implement without guessing. Pending owner sign-off on ClickUp `17tnw2b0ntc`; the build subtask `17tnw2b0ntd` remains blocked until that sign-off lands.
