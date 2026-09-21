# SelahCue — Transcripts (Design 2.0) Handoff

**Status:** design complete — first Figma coverage for this surface (previously undesigned), 7 frames covering the primary states.
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` · **Section:** `1050:2` "Transcripts — Design 2.0" (page `0:1`).
**ClickUp task:** NONE — pending ClickUp update (see `docs/delivery/goals/TASK-transcripts-design2-spec.md`).
**Goal Contract:** `docs/delivery/goals/TASK-transcripts-design2-spec.md`.
**Grounding:** this doc is built **from the shipped implementation**, not the other way around — `implementation/desktop/crates/selahcue-operator/dist/transcripts.js` (1605 lines), `dist/index.html` `#surface-transcripts` (~lines 1191–1276), `dist/app.js` (surface routing, `trActivate`), `dist/app.css` (`.tr-*`/`.pp-gen-*` rules); cross-referenced against `docs/design/DETECTIONS-VIEW-spec.md` (mobile equivalent — state naming, not a template), `UX-CANONICAL.md` (binding keybinding/colour/safety rules), `UX-FLOWS.md` Flow 11 (the original "Generate & edit sermon notes" vision — see §9 for where the shipped surface diverges), `UX-STATE-MATRIX.md`, `DESIGN-TOKENS.md` (`--sc-*`).

Frame link pattern: `https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=<id-with-dash>` (e.g. `1050-3`).

---

## 1. Why this surface had no Figma design, and why it does now

Transcripts is the **only** major desktop surface with zero Figma coverage anywhere in the file's 79 top-level nodes (confirmed by a full enumeration during planning; every other surface — console, screens, theme designer, presentation, settings, plan, pre-service, remote — has at least one named frame). It was built directly against the PRD/ADR record (86akcffvt core slice, then 86akgqdxr added detections + saved-draft view/edit, then 86akgqdwc/86akgqdw0/86akgqdx8 iterated the sermon-notes generation flow this month) without a preceding design pass. This handoff is the first one, produced **from the live implementation forward into Figma** — the same "code is truth, Figma catches up" direction the project already uses for `965:124` (RISK-205, PRD) and for `338:124`'s Settings expansion — not a redesign. Nothing in this document asks for a UI change; it records what already ships and gives it the same design-spec treatment (states, tokens, copy, a11y) every other surface already has.

## 2. What the surface actually does (read from the code, not assumed)

One workspace with two views:

- **List view** (`#tr-list-view`) — every saved transcript, most recent first: label, start date/time, duration (`h:mm:ss` at/above an hour, `m:ss` below — matching the Service Plan's own duration convention), segment count. Selecting one opens the detail view.
- **Detail view** (`#tr-detail-view`) — a single vertical workspace, not the split transcript↔notes layout `UX-FLOWS.md` Flow 11 originally sketched (see §9): a back button + header (title, meta, a "Notes generated / Notes not yet generated" badge), the **transcript log** (bounded sliding-window virtualizer, ADR-0026 — a service can run to thousands of segments and the DOM only ever mounts ~150 real rows at once, with two spacer elements keeping the scrollbar proportional to the full length), a **Detected scripture** panel (every reference persisted against this transcript, with an approximate position resolved from its source segment's timestamp, or "Position unknown" when the backend has no segment link), and a **Generate Sermon Notes** panel that is also where an *existing* saved draft renders — one render path for both a fresh generation and a reopened one.

Two things this surface is emphatically **not**: it is not the live in-session transcript panel (that is the console's own `.tr-seg`/`.pp-generate` in the left column, a different context with its own tail-limited Generate) and it does not offer live editing of the raw transcript text (`.tr-line-corrected` renders an *existing* correction read-only; writing a new one is out of scope here, per the file's own header comment).

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

Two states are deliberately **not** separate frames — they are covered by frame 4/5's own annotations rather than duplicated pixel-for-pixel: the **notes-not-yet-generated-but-service-ended** state (`#tr-notes-empty`, same shell as frame 5 minus the disabled/info treatment — Generate is enabled) and the **generating** loading state (frame 6's Confirm button with `aria-busy`, spinner, disabled — a transient sub-state of frame 6, not a distinct screen). Both are specified in prose in §5 below; a future implementer builds them from the same primitives already on the pushed frames.

## 5. State matrix

| Region | default / happy | empty | loading | error | disabled / permission | recovery / other |
|---|---|---|---|---|---|---|
| List | populated `1050:3` | no transcripts `1051:2` | `aria-busy="true"` on `#tr-list`, no dedicated frame (list stays visually empty until the fetch resolves) | load failed `1051:18` | — | — |
| Detail header | populated `1052:2` | — | title reads "Loading…", meta blank (no dedicated frame) | `#tr-detail-error` — load failed, Retry (same shape as list error) | — | — |
| Transcript log | populated, bounded window `1052:2` | 0-segment transcript renders an empty `.tr-log` (edge case — not separately designed; treat as the log simply having no rows, no special copy) | — | folds into the detail-header error (the whole detail view fails to load together) | — | a corrected line overlays raw (struck through) + corrected (bold) — shown in `1052:2` |
| Detected scripture | populated `1052:2` | "No scripture references were detected during this service." `1053:2` | — | — | — | — |
| Generate / notes | existing draft, view mode `1052:2` | not yet generated, service ended: `#tr-notes-empty` text + **enabled** Generate button (same shell as `1053:2`, without the info banner and with the CTA active) | Generate clicked, in flight: CTA reads unchanged label but `aria-busy`, disabled, spinner (sub-state of `1053:33`'s Confirm) | `not_configured` (info, "isn't available in this build yet") · `consent_required` (alert, links to Settings → Providers & Privacy) · `quota_exceeded` ("Monthly limit reached") · `transcript_too_short` / `no_transcript` (guarded before any network call) · `transport`/`malformed` (generic "Couldn't generate notes") — none pushed as a separate frame; each is a one-line swap of `1052:2`'s result panel content into `.pp-gen-err`/`.pp-gen-info` styling, already on the token table | still recording: Generate disabled + info notice `1053:2` | Confirm step (review & consent) `1053:33`; edit mode `1053:55`; save-in-flight (Save disabled + `aria-busy`, sub-state of `1053:55`) |

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

## 9. Where this diverges from the earlier `UX-FLOWS.md` Flow 11 vision — and why that's fine

`UX-FLOWS.md` Flow 11 ("Generate & edit sermon notes") sketches a **side-by-side split view** — raw transcript in a left column, editable notes in a right column, with click-to-jump timestamp links. What shipped is a **single vertical workspace** — log, then detections, then notes, stacked — with no timestamp-linked jump-to-source interaction from a note item back into the log (FR-124's "note items link to transcript timestamps" is not implemented on this surface as of this handoff). This is recorded here as an honest gap, not silently reconciled either direction:

- Per RISK-205 ("shipped code is truth, Figma catches up, not the reverse"), this handoff documents the **shipped single-column layout**, not Flow 11's split-pane sketch — the same principle that already governs every other Design 2.0 frame in this file.
- The gap (no timestamp-linked navigation from notes back to source) is a real, open product/build question, not a design decision made here. Flagged in `TASK-transcripts-design2-spec.md` §Open questions and left for the owner to prioritize against FR-124.

## 10. Implementation notes & open questions

- Farah implementing this surface's *next* increment should treat frames 1–4 (list default/empty/error, detail default) as the near-term priority — they cover the everyday path. Frames 5–7 (still-recording, consent preview, edit mode) already exist in the live app; the frames here exist so the *design* record catches up, not because any of them need rebuilding.
- **Open question (product):** should FR-124 (timestamp-linked note navigation) be scheduled for this surface, given it already ships on the mobile equivalent's adjacent territory? See §9.
- **Open question (design, minor):** the 0-segment transcript log and the mid-recomputed-window-resize cases have no distinct visual treatment beyond "the log has nothing/reflows" — flagged here rather than silently assumed complete.
- No implementation file was modified to produce this handoff — verified by `git status --porcelain implementation/` (§Verification in the goal contract).

---

**Verdict:** first design coverage for a surface that previously had none. Built from and verified against the live implementation, not drafted independently of it — consistent with this project's established "code is truth, Figma catches up" pattern (PRD RISK-205).
