# Design 2.0 parity audit — Offline download modal

**Role:** UI/UX Designer (Uma) · **Date:** 2026-09-20 · **Type:** read-only audit + gap spec (short
focused pass, per the Phase B brief — this is global chrome with an existing handoff doc and two
incidental A11Y findings already on record; this closes the gap to "actually audited")
**Goal Contract:** `docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ`, frame `396:124` "SPEC — Offline Download Modal (Design 2.0)"
(2768×716 — a states-and-notes spec sheet, 7 state cards + 4 implementation-note blocks)
**Companion doc:** `docs/design/DOWNLOAD-MODAL-handoff.md` (the design spec this audit verifies against
the live tree)
**Prior incidental coverage:** `DESIGN-2.0-PARITY-AUDIT-console.md`'s accessibility appendix already
flagged `.dl-modal-sub` and `.dl-modal-progmeta` as small-text contrast violations. Both are confirmed
again here, now as part of a full pass rather than an incidental note.
**Status:** point-in-time. Figma and `dist/` both move; re-run before acting on a row older than a week.

## What was audited

`#dl-modal-back`/`#dl-modal` (`index.html:1494-1528`, global chrome — not inside any `surface-*`
section) plus the self-contained IIFE that drives it in `app.js` (~4460-4655) and the `.dl-modal-*`/
`.dl-btn-*`/`.dl-pill` rules in `app.css:5760-5884`.

## Method

`get_metadata` on `396:124` (one call, full subtree — all 7 state cards + the 4 note blocks) cross-
checked against the code line by line. No bound Figma variables on this frame.

## Verdict vocabulary

**MATCH** / **DRIFT** / **MISSING** / **EXTRA** / **UNSPECIFIED** / **INTENTIONAL-DEVIATION** /
**A11Y-DEFECT** / **A11Y-CONFLICT**. Severity: **S1** blocks correct/accessible use · **S2** visible
parity break · **S3** cosmetic · **S4** informational.

---

# Summary

**8 numbered findings: DLM-001…DLM-008**, plus 7 unnumbered MATCH state-cards confirmed clean (listed
in the state table below) — the highest match rate of any surface in this round.

| Verdict | Count |
|---|---|
| MATCH (unnumbered) | 7 states + 4 implementation-note blocks |
| DRIFT | 4 |
| MISSING | 1 |
| A11Y-DEFECT | 3 |

Severity: **1 × S1** (DLM-001), 2 × S2 (DLM-002/003), 2 × S3 (DLM-004/006), 3 × S4 (DLM-005/007/008).

## Headline

This is the **most completely matched** surface in this audit round at the state-machine level: all
seven Figma states (Downloading / Verifying / Ready / Couldn't-connect / Couldn't-verify / Offline /
Reuse-for-a-Bible) exist in the code with matching titles, button sets, and — almost verbatim — the
exact copy the handoff specifies. The gaps are narrow and specific:

1. **The hover state on the primary button repeats this audit round's recurring gradient/white-text
   defect one more time** — the **sixth** sighting (after `.tb-golive`'s original fix, Theme Designer,
   Preservice, and the Presentation audit's `.pm-btn-primary:hover`). **DLM-001, A11Y-DEFECT, S1.**
2. **The two contrast findings the console audit already flagged incidentally are confirmed as real**,
   and this pass adds the fix each needs. **DLM-002/DLM-003.**
3. **A handful of small geometric drifts** (card radius 14 vs. 16, button radius 8 vs. 10) — cosmetic,
   not behavioural.

---

# Frame `396:124` — state-by-state

| # | State | Figma node | Figma key content | Implemented | Verdict | Sev |
|---|---|---|---|---|---|---|
| — | 1 · Downloading | `398:124` | Determinate bar; `{done} MB of {total} · {pct}%`; `~{eta} left`; "Runs once…" note; Hide (ghost) · Cancel (bordered) | `renderDownloading()` (`app.js:4516-4529`): identical fields — `fmtBytes(lastDone) + " of " + fmtBytes(lastTotal)`, `lastPct + "%"`, note text matching the handoff's copy verbatim, `Hide`/`Cancel` shown, `Start listening` hidden | **MATCH** — the one field Figma draws that the code doesn't is `~{eta} left` (a time estimate); **DLM-004** below | DRIFT (ETA only) | S3 |
| — | 2 · Verifying | `400:124` | Indeterminate bar; "Checking integrity…"; explains the checksum guard; **Cancel only**, no Hide, Esc disabled | `renderVerifying()` (`app.js:4530-4541`): `progwrap.classList.add("is-indeterminate")`, `btn(btnHide, false)`, note text matching the handoff's *"guards against a corrupted or tampered file"* copy almost verbatim (code says "file", handoff says "model" — see **DLM-005**); the keydown handler explicitly refuses Esc during `verifying` (`app.js:4632-4633`) | **MATCH**, including the safety-critical "can't abort a verify" behaviour | DRIFT (word choice only) | S4 |
| — | 3 · Ready | `400:146` | Green ✓; "Installed · {size} · verified"; successCopy; `Start listening` primary; **auto-continues (~1.5s or on the button)** | `renderReady()` (`app.js:4542-4555`): `ico.className = "is-ready"`, `progfill.className = "is-ready"` at 100%, `btn(btnPrimary, true, "Start listening")`, and — matching the handoff's flow note exactly — `readyTimer = setTimeout(() => { if (state === "ready") closeModal(); }, 1500)` | **MATCH**, including the exact 1.5s auto-dismiss timing named in the handoff | — | — |
| — | 4 · Couldn't connect | `400:168` | Gold `!`; "Download interrupted / Paused at {pct}%"; progress kept; Cancel (ghost) · Retry (primary) | `renderFailed("connect")` (`app.js:4568-4579`): `ico.className = "is-warn"`, title/sub match, `progfill.className = "is-warn"` at `lastPct`% (progress kept, not reset), buttons `Cancel`/`Retry` | **MATCH** | — | — |
| — | 5 · Couldn't verify | `400:190` | Red `!`; "Discarded for your safety"; checksum mismatch → deleted, nothing installed; Cancel (ghost) · Retry (primary) | `renderFailed("verify")` (`app.js:4557-4562`): `ico.className = "is-integrity"`, title/sub match verbatim, `progwrap.hidden = true` (matching Figma's own hidden progress row on this state), body copy matches the handoff's copy verbatim | **MATCH** | — | — |
| — | 6 · Offline | `400:212` | Grey `⚠`; "Connection needed one time"; works offline afterward; Not now (ghost) · Try again (primary) | `renderFailed("offline")` (`app.js:4563-4567`): `ico.className = "is-warn"` — **not** a distinct grey/neutral class; buttons correctly relabel to `Not now`/`Try again` via the `reason === "offline"` branch (`app.js:4577-4578`) | DRIFT — see **DLM-006** (icon tone) | S3 |
| — | 7 · Reuse — Bible | `400:234` | Same layout, "Downloading King James Version", a Bible-specific size/progress example | `translationAsset()` (`app.js:4467-4480`) + `onBiblePhase()` (`app.js:4648`): builds a parameterised asset descriptor (`title`, `sub: "Bible translation · offline text"`, per-translation `note`/`readyNote`/`offlineNote`) driven by the real `bible://phase` event, proving the "one component, seven states, two asset kinds" pattern the handoff specifies | **MATCH**, and confirms the handoff's own parameterisation requirement (`type OfflineDownload`) is genuinely implemented, not just the model asset hard-coded | — | — |

---

# Placement, scrim, and flow (implementation-note blocks)

| # | Note | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Centred dialog, max-width 360, scrim 72% over the console, **emergency footer stays above the scrim** | `403:125-131` | `.dl-modal-back:not([hidden])` (`app.css:5761-5770`): `inset: 0 0 56px 0` (leaves exactly the footer's height clear), `background: rgba(11, 13, 18, 0.72)`; `.dl-modal { width: min(360px, 92vw) }` (`app.css:5774`) | **MATCH**, including the specific 56px inset that keeps BLACKOUT/Clear reachable — the "a dialog must never trap live output" rule this codebase applies consistently | — | — |
| — | Narrow width → 92vw; body scrolls, buttons pinned | `403:127-131` | `.dl-modal-progwrap { overflow-y: auto }` (`app.css:5802`), `.dl-modal-actions { flex: none }` (`app.css:5846`) with the comment *"stay pinned; the body above scrolls"* | MATCH | — | — |
| — | Hide = background pill; Cancel = abort + delete partial; Retry = resume progress; integrity failure restarts clean | `403:134-138` | `hideToBackground()` (`app.js:4511-4515`) shows `#dl-pill`; `btnSecondary` click invokes `cancel_download` + `stop_listening` then closes (`app.js:4619-4624`); `btnPrimary` click on a failed state calls `asset.retry()`, which re-invokes the download command fresh | MATCH — "resume from kept progress" vs. "restart clean" is a backend behaviour (`fetch_model`'s own resume/redownload logic) not independently re-verified from the webview layer in this pass | MATCH (UI contract only) | S4 |
| — | Accessibility notes: `role=dialog` `aria-modal`, focus trap, Esc=Cancel except Verifying, progress `role=progressbar` + `aria-live=polite` in ~10% steps, reduced-motion static bar, all text ≥AA, hit targets ≥40px | `403:141-147` | `role="dialog" aria-modal="true"` (`index.html:1499`); focus trap via `Tab`/`Shift+Tab` cycling (`app.js:4636-4641`); Esc suppressed only during `verifying` (`app.js:4632-4633`); `announce()` gated by `Math.floor(lastPct / 10)` step changes (`app.js:4527-4528`) — **exactly** the "~10% steps, not every tick" requirement; `.dl-btn { min-height: 40px }` (`app.css:5849`) | **MATCH** on every mechanical claim — see **A11Y** below for the one claim ("all text ≥ AA") that does **not** hold | DRIFT (the AA claim) | see A11Y |

---

# Geometry drift (cosmetic)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| **DLM-004** | ETA readout `~{eta} left` | `398:139`: shown alongside the byte progress on the Downloading state | `progbytes`/`progpct` are populated; **no `~N left` time estimate was found** anywhere in the download-modal IIFE | MISSING | S3 |
| **DLM-005** | Verifying body copy: *"This guards against a corrupted or tampered **model**."* | `400:140` | `app.js:4537`: *"This guards against a corrupted or tampered **file**."* — generalised for the Bible-translation reuse case (state 7), where "model" would be wrong | **DRIFT**, and arguably the correct choice given the component is genuinely shared between two asset kinds — the handoff's own copy was written before the generalisation | S4 |
| **DLM-006** | Offline state icon: grey `⚠`, visually distinct from the gold `!` on states 4/7 | `400:217-218` | `renderFailed("offline")` uses `ico.className = "is-warn"` (`app.js:4565`) — the **same** gold class as the "couldn't connect" state, not a separate neutral/grey tone | DRIFT — a real but minor loss of visual distinction between "your connection failed" and "you have no connection at all," two states an operator would reasonably want to tell apart at a glance | S3 |
| **DLM-007** | Card radius 16 | `396:124` note block, §PARAMETERISATION | `.dl-modal { border-radius: 14px }` (`app.css:5778`) | DRIFT | S4 |
| **DLM-008** | Button radius 10 | same | `.dl-btn { border-radius: 8px }` (`app.css:5851`) | DRIFT | S4 |

---

# Accessibility

## A11Y-1 — Real defects (fix regardless of the frame)

| # | Where | Measured | Why it fails | Fix |
|---|---|---|---|---|
| **DLM-001** | `.dl-btn-primary:hover` — `app.css:5859`: `background: var(--sc-primary-hover)`, inheriting `color: #fff` and `font-weight: 600` from `.dl-btn` (`app.css:5852-5858`) | white on `--sc-primary-hover #7E6EFF` = **3.78:1** | Not large text at this button's size, so 4.5:1 applies. This is the **sixth** sighting of the exact recurring defect this audit round found on Theme Designer's `.td-save-cta`, Preservice's `.ps-start`, and the Presentation audit's `.pm-btn-primary:hover` (already fixed once at `.tb-golive`, `app.css:4505-4507`) — this button is `Start listening` / `Retry` / `Try again`, i.e. the primary action on **every** failure and success state of this dialog. | Darken on hover instead of lightening: `background: #5a48d0` (matching the shipped `.tb-golive` fix, ≥6:1), not `--sc-primary-hover`. |
| **DLM-002** (pre-existing, promoted from incidental to confirmed) | `.dl-modal-sub` — `app.css:5800`: `font-size: 12.5px`, `color: var(--sc-text-muted)` | `--sc-text-muted #6B7383` on `--sc-surface` = **3.79:1** (the console audit's own already-measured figure for this pairing) | This is the **subtitle line directly under the modal's title** on every state — e.g. "Whisper · English · on-device" — informational but immediately adjacent to the title, at a size (12.5px) and weight that reads as primary supporting copy, not a tertiary label. The console audit flagged this incidentally; this pass confirms it belongs in **A11Y-1** (a real defect) rather than the classified/compliant tier, because it sits in the header of a modal an operator must read to know what is downloading — closer to "essential" than "supplementary" under the project's own written policy. | Promote to `--sc-text-secondary` (7.40:1+), matching the `PME-006…011` promotion pattern. |
| **DLM-003** (pre-existing, promoted from incidental to confirmed) | `.dl-modal-progmeta` — `app.css:5831-5838`: `font-size: 12px`, `color: var(--sc-text-muted)` | same **3.79:1** | The byte-progress readout ("620 MB of 1.6 GB") and the percentage — decision-relevant during an active download (an operator gauging whether to wait), the same "informational, not incidental" tier the Presentation audit's PME-012 already discusses for a materially identical case (slide-count metadata) | Same fix — promote to `--sc-text-secondary`, or fold into the second-tier compliant muted-token decision already open as **Q-02** in the Presentation audit rather than a one-off exception here. |

## A11Y-2 — Clear

- Every failure/success state pairs an icon **and** a text title/subtitle — no colour-only signal.
- The reduced-motion path is real, not just documented: `@media (prefers-reduced-motion: reduce)`
  (`app.css:5827-5829`) disables the shimmer animation and holds a static bar — matching the handoff's
  *"show a static 'Working…'"* requirement in spirit (the code shows a static bar rather than literal
  "Working…" text, a minor wording gap not scored as a defect since the state is still legible and
  distinct).
- Progress announcements are correctly throttled to ~10% steps (verified functionally, not just
  documented — see the table above), avoiding the aria-live spam a naive per-tick announcement would
  produce.

## Reconciliation — 2026-09-21

**Author:** Farah (Frontend Engineer). **Scope:** `DLM-001` only, fixed under ClickUp task
`17tnw2axpt9` ("shared gradient-hover contrast fix", TD-012 / PSC-005 / DLM-001 — the same
defect found once here and twice more on the Theme Designer and Pre-service surfaces). This
section is additive; the table above is left as originally written.

### FIXED

| Finding | Evidence |
|---|---|
| `DLM-001` | `.dl-btn-primary:hover` (`app.css:5866-5870`): changed from `background: var(--sc-primary-hover)` (**3.78:1**) to a flat `background: #5a48d0; border-color: #5a48d0` (**6.42:1**), matching `.pm-btn-primary:hover` (`app.css:5106`) exactly — rest was already accessible at 4.72:1 (solid `var(--sc-primary)`, unlike TD-012/PSC-005 this button never used a gradient), so only the hover rule needed a fix. Verified by 6 new assertions in `scripts/operator_headless.py` (the `DLM-001` block), mutation-tested. Commit `d8ecf4b`. |

---

# Open questions

- **DLM-OQ-1 (design, minor).** DLM-004 — is the `~{eta} left` time estimate a real requirement, or
  illustrative mock content? If real, it needs a rate calculation the current byte-only progress payload
  doesn't obviously carry.
- **DLM-OQ-2 (design, minor).** DLM-006 — should the Offline state get its own neutral/grey icon tone
  distinct from the gold "couldn't connect" tone, to help an operator tell "no internet at all" apart
  from "had a connection, lost it"?
- **DLM-OQ-3 (product/a11y).** DLM-002/DLM-003 — this is the same Q-02 (second-tier compliant muted
  token) decision already open from the Presentation audit, now with two more call sites. Every audit in
  this round that touches informational-but-adjacent-to-essential text keeps finding more instances of
  the same unresolved token question. Worth treating as one cross-surface ticket rather than N separate
  promotions, once Phase D groups the findings.
