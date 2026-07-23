# SelahCue — Core UX Flows

> **Canonical rules:** keybindings, Go-Live/Undo behaviour, emergency-vs-modal rules, colour tokens, and seizure-safe defaults are governed by [UX-CANONICAL.md](UX-CANONICAL.md), which **supersedes** any conflicting inline statement here (Stage-5 review B1/M8/M9/M10).

Version: 1.0 (Stage 5) · Date: 2026-07-23 · Owner: UI/UX Designer · Status: For Stage 5 architecture+UX review

**Sources:** PRD `docs/product/prds/SelahCue-PRD.md`, personas `docs/business/PERSONAS.md`, workflows `docs/business/WORKFLOWS.md`, architecture `docs/architecture/ARCHITECTURE.md`. Every flow traces to FR/FLOW/workflow IDs. Wireframes are low-fi ASCII (layout intent, not pixels).

> **Status limitation.** These flows are **un-validated design intent** built on INFERRED personas/workflows (no user research yet). They are a testable hypothesis to be corrected by real operator feedback (usability test → METRIC-006, ≤10 min time-to-first-slide). Nothing here is built.

---

## 0. Design foundations (shared by every flow)

Flows below reference these once instead of repeating them. Read this section first.

### 0.1 The five live-operation principles

1. **Fast.** The most-used live actions (advance, go-live, clear, blackout) are one keypress or one large button — never buried in a menu, never a modal.
2. **Keyboard-first.** Every core live action is operable with no mouse (NFR-019, FR-014). Shortcuts are documented and remappable. The mouse is a convenience, not a requirement.
3. **Glanceable.** State an operator must read under pressure (what's LIVE, what's NEXT, is the timer running, is cloud active, is a device connected) is always visible, large, and colour-coded — readable in a dark booth at arm's length.
4. **Mistake-resistant.** Preview and Live are physically separated. Nothing reaches an audience output without an explicit "go live". AI never auto-acts. Destructive/config edits are guarded; emergency-safety actions are instant *and* reversible.
5. **Calm under pressure.** Failures never blank the screen or throw a blocking dialog over the live controls. A failure is a non-blocking banner; the operator keeps driving the service.

### 0.2 The invariants (never violated by any flow)

- **Preview ≠ Live.** Editing/staging never changes any audience output until "Go Live" is invoked (FR-012).
- **Emergency clear + blackout are always reachable** — global, offline, keyboard + always-visible on-screen, no confirmation, <200ms, reversible (FR-076/077, CON-2).
- **Desktop is authoritative.** Mobile/AI/providers send *requests*; the desktop validates and executes. Losing all of them never disables a desktop capability (CON-1, FR-098).
- **No AI auto-action without operator confirmation.** Detection/notes/transcription never change live output on their own (FR-083/115/119, WORKFLOWS §3).
- **Fail safe, not surprising.** On any component failure the current live output is *held*; the operator gets a non-blocking alert (WORKFLOWS §Governing-4).

### 0.3 Operator console anatomy (desktop — the home screen for most flows)

```
┌──────────────────────────────────────── SAFETY BAR (always visible, always live) ─────────────────────────────────────┐
│ SelahCue   Sun AM Service · 09:00      [ ⛶ BLACKOUT  (B) ]   [ ✕ CLEAR ALL  (Esc Esc) ]      ●CLOUD off   ⏱ 24:13   ⣿ │
├────────────────────────┬───────────────────────────────────────┬───────────────────────────────────────────────────┤
│ SERVICE PLAN (run sheet)│  PREVIEW — staged, NOT on air          │  LIVE — ● ON AIR                                   │
│ ─────────────────────── │  ┌──────────────────────────────────┐  │  ┌──────────────────────────────────────────────┐ │
│ ▸ 1 Welcome             │  │                                  │  │  │                                                │ │
│ ▾ 2 Great Is Thy Faith. │  │      [ staged slide render ]     │  │  │            [ MAIN output mirror ]              │ │
│     · Verse 1           │  │                                  │  │  │                                                │ │
│   ▶ · Chorus  (staged)  │  │                                  │  │  │                                                │ │
│     · Verse 2           │  └──────────────────────────────────┘  │  └──────────────────────────────────────────────┘ │
│ ▸ 3 Scripture: Rom 8    │  NEXT ▸ ┌────────┐  translation: WEB    │  STAGE ▸ current line · next line · clock · timer  │
│ ▸ 4 Sermon              │         └────────┘                      │  Outputs:  Main ●live   Stage ●live               │
│ ▸ 5 Response            │  ┌───────────── GO LIVE ▸ (Enter) ────┐ │                                                    │
│   ⚑ missing media: 0    │  └────────────────────────────────────┘ │                                                    │
├────────────────────────┴───────────────────────────────────────┴───────────────────────────────────────────────────┤
│ ⌨ Command Palette (⌘/Ctrl K)     ◀ Prev (←)   Next ▶ (Space)   Clear Layer (Esc)   Undo (⌘Z)     🔌 2 devices · ✓sync │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Three columns, left→right = **plan → preview → live** (matches reading order and the preview→live mental model). The **safety bar** (blackout + clear-all) spans the top and is present on every screen in the app, including editors and settings. The **transport bar** at the bottom holds the second-most-used actions.

### 0.4 Global keyboard map (all remappable — FR-014)

| Action | Default | Reversible? | Confirm? |
|---|---|---|---|
| Go Live (Preview → Live) | `Enter` | yes (re-stage) | no |
| Next (advance live) | `Space` / `→` | yes | no |
| Previous | `←` | yes | no |
| Select next/prev item or slide in Preview | `↓` / `↑` | n/a | no |
| **Blackout audience (toggle)** | `B` | yes (un-blackout restores) | **no** |
| **Clear all live layers** | `Esc Esc` (double-tap) | yes (undo restores) | **no** |
| Clear focused layer (text/bg/lower-third/media) | `Esc` | yes | no |
| Command palette | `⌘/Ctrl K` | — | — |
| Focus scripture search | `⌘/Ctrl L` | — | — |
| Repeat / jump song section | `R` / `J` then section | yes | no |
| Undo / redo (edit ops) | `⌘/Ctrl Z` / `⇧⌘Z` | — | no |
| Identify displays | `⌘/Ctrl I` | — | no |

Emergency actions (`B`, `Esc Esc`) are **single-action and never behind a modal** — mistake-resistance for them comes from *reversibility*, not from a confirmation step. Destructive *edits* (delete plan, revoke device, enable AI auto-display) are the ones that get guards (§0.6).

### 0.5 State & colour semantics (glanceable vocabulary)

| Meaning | Signal | Notes |
|---|---|---|
| **LIVE / on air** | red `●` + red left-border on the Live pane | the only place red "●" is used |
| **PREVIEW / staged** | amber `▶` marker + amber outline | "loaded but not on air" |
| **Healthy / OK** | green `✓` | outputs, devices, checks |
| **Attention / degraded** | amber `⚠` | non-blocking; keep working |
| **Lost / error** | red text *inside a card* — **never** a red/black full output | failure is isolated to the affected card |
| **Cloud active** | persistent blue `●CLOUD` badge in safety bar | unmistakable while any data leaves device (FR-133) |
| **AI suggestion** | violet card in a side queue, never on an output | human-gated (FR-115) |

Colour is never the *only* signal — every state also carries an icon/word (WCAG 1.4.1). Contrast meets WCAG 2.1 AA: ≥4.5:1 normal text, ≥3:1 large text/UI (NFR-020).

### 0.6 Confirmation-cost model (when to guard, when not to)

- **Instant, no confirm, reversible:** Go Live, Next/Prev, Blackout, Clear (any layer). These are the live-driving actions; friction here causes on-screen mistakes.
- **Guarded (inline confirm or 5s undo-window):** enabling AI auto-display, revoking a paired device, deleting/overwriting a plan, sending audio/TIME-UP to a house/audience output, purging a transcript.
- **Never automatic (always an explicit human action):** displaying a detected verse, sending TIME UP to an audience output, sending sermon audio/transcript to a cloud provider.

### 0.7 Accessibility baseline (applies to every screen)

- **Keyboard:** full operation of core live actions with no mouse; visible focus ring on every interactive element; logical tab order; no keyboard traps (NFR-019).
- **Screen reader (MVP scope):** core live controls (next/prev/clear/blackout/go-live, timer/TIME-UP, scripture-stage) expose accessible name + role + state (NFR-021).
- **Contrast & legibility:** WCAG AA contrast; stage/confidence text configurable to ≥48px-equivalent with a high-contrast theme for stage-lighting readability (NFR-020).
- **Motion & seizure safety:** audience/stream animation ≤3 flashes/sec; a global **Reduced Motion** setting disables non-essential animation on all outputs and in the console (FR-175, NFR — WCAG 2.3.1).
- **Mobile:** every touch target ≥44×44pt; accessible labels on all controls (NFR-026).

### 0.8 Reading key for the flows

Each flow lists: **Goal · Actor · Entry point · Preconditions · Trace · Key screens · Happy path (operator action → system response) · Branches · Safety/A11y notes**. `[MVP]`/`[R3]`/`[R4]`/`[R5]` mark release.

---

## Flow 1 — Build & open a service plan `[MVP]`

**Goal.** A coordinator assembles an ordered run-sheet ahead of time; the operator opens the identical plan on service day with every cue in order.
**Actor.** Service Coordinator (build) → Church Media Operator (open). Desktop.
**Entry point.** Home → **New Service** (or **Duplicate last week**); on service day, **Open Plan**.
**Preconditions.** SelahCue installed; library available; user has planning permission.
**Trace.** FLOW-001; FR-001…008, FR-139; WORKFLOWS A1/B1; JTBD-1; personas §1.8/§1.1.

### Key screen — plan builder

```
┌─ NEW SERVICE ────────────────────────────────────────────────────────────────┐
│ Name [ Sunday AM Service        ]  Date [2026-07-26] Time [09:00] Type [Sunday]│
│ Start from:  ( ) Blank   (•) Template: "Standard Sunday"   ( ) Duplicate…      │
├─ RUN SHEET ──────────────────────────────┬─ ADD ITEM ─────────────────────────┤
│  ⠿ 1 § Welcome                    5:00 🧑Ade│  [ Song ] [ Scripture ] [ Slides ] │
│  ⠿ 2 ♪ Great Is Thy Faithfulness  6:00 🧑Sam│  [ Media ] [ Announcement ]        │
│  ⠿ 3 ✝ Scripture: Romans 8:28-30  2:00 🧑Ada│  [ Timer ] [ Section header ]      │
│  ⠿ 4 ✎ Sermon                    30:00 🧑Pst│  ── drop into the run sheet ──     │
│  ⠿ 5 § Response / Altar call      8:00 🧑Ade│                                    │
│  ⚑ 1 item has missing media  → Review        │  Library search: [ great is… ]🔎  │
│  ── planned length: 51:00 ──                 │  · Great Is Thy Faithfulness (PD) │
├──────────────────────────────────────────────┴────────────────────────────────┤
│ [ Save (⌘S) ]  autosave ✓ 3s ago   Versions ▾   [ Publish to team ▸ ]          │
└────────────────────────────────────────────────────────────────────────────────┘
```
`⠿` = drag handle · `§` header · `♪` song · `✝` scripture · `✎` sermon · `🧑` responsible person.

### Happy path

| # | Operator action | System response |
|---|---|---|
| 1 | New Service → pick **Template** or **Duplicate last week**, set name/date/type | Creates a `draft` plan; template items pre-load or blank canvas appears |
| 2 | Add items by dragging from **Add Item** / library search into the run sheet | Each item type addable, editable, removable (FR-002); library search returns matches <300ms (FR-003) |
| 3 | Set per-item duration + responsible person | Item shows planned duration + owner; footer sums **planned service length** (FR-004) |
| 4 | Reorder via drag handles `⠿` | Order persists live; supports ≥50 mixed items; survives restart (FR-001) |
| 5 | (Auto) validation runs on every add/reorder | Any item whose media is missing/moved gets a `⚑ missing media` badge + Review prompt (FR-007 → **Flow 8**) |
| 6 | **Save** / autosave | Continuous autosave; last-3 versions restorable (FR-005); state `draft` |
| 7 | **Publish to team** | State `validated → published`; operator seat can open the identical ordered plan (FR-006) |
| 8 | *(service day)* Operator **Open Plan** | Plan opens in the console (§0.3) with every cue in order, no mismatch; missing-media re-checked on open (FR-007) |

### Branches

- **B1 · Duplicate & swap (WORKFLOWS B1):** start from last week's plan, swap songs/scriptures rather than build from scratch. "Duplicate" produces an independent copy (FR-005).
- **Edit after publish:** creates a new version; the operator's open plan shows a **change badge** ("Plan updated · Review changes") — non-destructive, operator chooses when to reload so a mid-service edit never silently reorders the live run sheet.
- **Save as template:** any plan → "Save as template" produces a reusable independent copy (FR-005).
- **Missing media at open →** routes into **Flow 8** (pre-service check) with a remediation prompt; never blocks opening.
- **Import a plan bundle (FR-139):** portable bundle re-imports with items + media refs intact; unresolved refs surface as missing-media badges.

### Safety / A11y

Publishing is guarded (explicit action, versioned) but building is not — autosave means no data-loss friction. Run-sheet reorder is fully keyboard-operable (`↑/↓` to move focus, `⌥↑/⌥↓` to move item). Responsible-person and duration are text, not colour-only.

---

## Flow 2 — Go live with a slide (preview → live) `[MVP]`

**Goal.** Put the correct slide on the main output in <1s, with a mandatory preview step, so the congregation never sees a wrong or half-built slide.
**Actor.** Church Media Operator. Desktop.
**Entry point.** Console home (§0.3), a plan open. Selecting any plan item or slide loads it into **Preview**.
**Preconditions.** A plan is open; Main + Stage outputs assigned (Flow 8 / display setup).
**Trace.** FLOW-001; FR-012 (preview↔live), FR-013 (current/next), FR-009/010, FR-024 (jump/repeat), FR-076 (clear); JTBD-1; NFR-004 (≤150ms trigger).

### Key screen — the preview→live handoff

```
 PREVIEW (staged, NOT on air)              GO LIVE (Enter)             LIVE (● ON AIR)
 ┌───────────────────────────┐                 ══▶                 ┌───────────────────────────┐
 │  Chorus                    │                                     │  Verse 1                   │
 │  "Great is thy            "│   the ONLY bridge from staged       │  "Morning by morning…"     │
 │   faithfulness…"           │   to on-air is this explicit step   │                            │
 └───────────────────────────┘                                     └───────────────────────────┘
   ▲ operator edits/stages here                                      ▲ audience sees this
   nothing here touches output                                       Main ● + Stage ● mirror
```

### Happy path

| # | Operator action | System response |
|---|---|---|
| 1 | `↓/↑` (or click) to select the next item/slide in the plan | Selected slide renders in **Preview** only; **Live is untouched** (FR-012). NEXT thumbnail updates |
| 2 | Glance at Preview to confirm the right slide/translation/formatting | Preview render is pixel-identical to what Live will show (FR-009) |
| 3 | Press **`Enter`** (Go Live) | Staged slide moves to Live; Main output updates on-screen in ≤150ms (goal ≤80ms, NFR-004); Live pane border pulses red once; Stage output shows current+next (FR-013/037) |
| 4 | Press **`Space`** to advance to the next slide | Next slide goes live; the following slide auto-stages into Preview; current/next update ≤100ms (FR-013) |
| 5 | (Worship improvises) Press **`R`** → pick **Chorus** to repeat, or **`J`** to jump | Section repeats/jumps live in ≤2 actions, reflected on output <1s (FR-024) |
| 6 | Clear when the item ends — `Esc` (this layer) | Text layer clears from Live <200ms; background/other layers preserved (FR-078) |

### Branches

- **Wrong slide staged:** operator simply selects a different slide and Go-Lives again — because staging never touched the output, there is nothing to "undo" on-air. This is the core mistake-resistance payoff of preview/live separation.
- **Wrong slide went live:** press `←` (Previous) or select the right slide + `Enter` — recovers in one action, <1s. `⌘Z` does **not** destructively "un-trigger" a live change (FR-016) — live navigation is forward/back, not undo.
- **Edit a slide while live:** open the inline editor from Preview; edits render in Preview, and only reach Live on the next Go Live (FR-012). A "live edit" toggle (advanced) can push edits to the current live slide, clearly labelled.
- **Blackout during offering/altar call:** `B` — see **Flow 5**.
- **Mobile advance:** a paired Presenter can drive step 4 — see **Flow 6**.

### Safety / A11y

Preview/live separation is the headline safety property (FR-012). Go Live, Next, Prev, Clear are all keyboard-first with screen-reader names/roles/state (NFR-021). Live pane uses red `●` + border + label (not colour alone). Slide-advance animation respects Reduced Motion (FR-175).

---

## Flow 3 — Present scripture from search `[MVP]`

**Goal.** Get the correct verse, correct translation, on screen before the congregation finishes turning pages — reactively and fast, fully offline.
**Actor.** Scripture Operator. Desktop primary (mobile secondary — Flow 6 / B2).
**Entry point.** `⌘/Ctrl L` focuses the scripture search from anywhere; or the plan's Scripture item.
**Preconditions.** Bundled PD translations installed (WEB/ASV/BSB/BBE/Darby/Webster; **no KJV**, FR-025).
**Trace.** FLOW-002; FR-025…031, FR-035; WORKFLOWS A2/B2; JTBD-2; personas §1.2.

### Key screen — scripture search & stage

```
┌─ SCRIPTURE ────────────────────────────────────────────── translation: [ WEB ▾ ] ┐
│ 🔎 [ rom 8:28-30                    ]   history: Ps 23 · Jn 3:16 · ★ favourites   │
│ ─────────────────────────────────────────────────────────────────────────────── │
│ Parsed:  Romans 8:28–30  ·  3 verses  ·  → 2 slides (2 verses/slide)             │
│ ┌─ PREVIEW (staged) ─────────────────────────┐  slides:  [1]•  [2]              │
│ │ 28 And we know that all things work together│  verses/slide: [ 2 ▾ ]           │
│ │    for good to those who love God…          │  verse #: [ show ▾ ]  ✝ template │
│ │ 29 For whom he foreknew, he also predestined│                                   │
│ └─────────────────────────────────────────────┘  compare ▸ (R2)                  │
│ [ Stage to Preview ]                 [ GO LIVE ▸ (Enter) ]                        │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Happy path

| # | Operator action | System response |
|---|---|---|
| 1 | `⌘L`, type a reference: `rom 8:28-30` (or a keyword phrase) | Reference parser resolves aliases/ranges/multi-selects (FR-027). Keyword search returns ranked matches <500ms (FR-028). Invalid refs rejected with guidance (FR-026) |
| 2 | Pick translation from the switcher (default WEB) | Text re-resolves from the **local** library — no network (FR-025). Attribution shown; PD marked (FR-035) |
| 3 | (Auto) passage paginates | Split into display-sized verse slides at the configured verses/slide with verse-number formatting (FR-029) |
| 4 | Review in **Preview**; adjust verse range / translation / verses-per-slide if needed | All re-render in Preview only; Live untouched (FR-012) |
| 5 | **`Enter`** (Go Live) | Correct verse text on Main output; Stage shows current + next line (FR-037) |
| 6 | `Space` to advance verse-by-verse as the preacher reads | Next verse slide goes live <1s; current/next update |
| 7 | `Esc` to clear the scripture layer when done | Scripture layer clears; content underneath (e.g. background) preserved (FR-078) |

### Branches

- **Mishearing / wrong verse staged:** re-type in search, re-stage — Live never showed it (preview gate). This is exactly the pain point in persona §1.2.
- **Favourites / history:** last-N references + ★favourites re-present in ≤2 actions (FR-031) — for recurring call-to-worship passages.
- **Awkward multi-passage:** `Jn 3:16; 1 Cor 13:4` parses to a combined verse set (FR-027).
- **Mobile push (B2):** a mobile Scripture Operator stages reactively near the stage; **same preview→live gate**, executed by the authoritative desktop (Flow 6, FR-095 at R4).
- **Side-by-side compare (R2):** two translations of the same passage in a comparison view (FR-030).
- **From an AI suggestion (R4):** the passage may arrive pre-staged from **Flow 10** — still requires the operator's Go Live.

### Safety / A11y

Offline-first (no network in the whole flow). Preview-before-live is mandatory (WORKFLOWS A2). Search field and translation switcher are keyboard-operable with SR labels. Verse text on stage is large-text/high-contrast configurable (NFR-020).

---

## Flow 4 — Run a countdown → TIME UP `[MVP]`

**Goal.** Run a hard countdown and show a prominent **TIME UP** on the stage/confidence display — **never on an audience output by accident** (JTBD-3).
**Actor.** Stage Manager / Timer Operator. Mobile (roaming) or desktop.
**Entry point.** Timers panel, or a Timer item in the plan; `⌘K` → "Start sermon timer".
**Preconditions.** A stage/confidence display is showing; a timer exists or can be created.
**Trace.** FLOW-003; FR-054…065 (esp. **FR-062** accidental-audience prevention, **FR-058** operator-only vs stage-visible, FR-059 TIME UP config, FR-060 overrun, FR-061 dismissal, FR-063 audio guard); WORKFLOWS A3/B3; personas §1.5.

### Key screen — timer with explicit output scoping (the safety control)

```
┌─ TIMER: Sermon ──────────────────────────────────────────────────────────────┐
│                                                                                │
│                     24 : 13                 ● running                          │
│        preset [25:00 ▾]   [ ⏸ Pause ] [ +1m ] [ -1m ] [ ↺ Reset ]              │
│                                                                                │
│  Warn at:  amber [ 2:00 ]   red/flash [ 0:30 ]                                 │
│  ───────────────────────────────────────────────────────────────────────────  │
│  SHOW ON:   [✓] Stage/Confidence     [✓] Operator                             │
│             [ ] Main audience  ⚠     [ ] Livestream  ⚠                         │
│             └─ audience outputs are OFF by default (FR-062) ──┘                │
│  ───────────────────────────────────────────────────────────────────────────  │
│  TIME UP state:  text [ "TIME UP" ]  colour [red]  bg [black]  [flash ▾ ≤3/s]  │
│  Alert sound at 0:  [✓] operator (local)   [ ] to output ⚠ (explicit + confirm)│
└────────────────────────────────────────────────────────────────────────────────┘
```

### Happy path

| # | Operator action | System response |
|---|---|---|
| 1 | Create/select a **countdown** (e.g. 25:00); pick target display(s) | Timer created; **Show-on** defaults to Stage + Operator, **audience/livestream OFF** (FR-062). Uses monotonic clock, ≤100ms/hr drift (FR-065/NFR-022) |
| 2 | **Start** | Stage/confidence shows the running clock (FR-037). Controls act <200ms on every output showing it (FR-055) |
| 3 | (Auto) thresholds hit | Amber at 2:00, red/flashing at 0:30 on the stage display only (FR-057); flash bounded ≤3/sec (FR-175) |
| 4 | (Auto) reaches `00:00` | Configured **TIME UP** state renders on the **selected outputs only** (FR-059). Operator hears a local alert (FR-063). Overrun continues into negative "+1:12 over" (FR-060) |
| 5 | Operator chooses: **+time / extend**, **send stage message**, or **dismiss** | Extend adds time and resumes; stage message (Flow-specific, FR-162) shows "wrap up"; **Dismiss** clears TIME UP from all outputs (FR-061). Every expiry can be logged (FR-064, R6) |

### Branches

- **Attempt to enable an audience output for the timer/TIME-UP:** ticking **Main audience** or **Livestream** triggers an inline guard — "This will show the timer to the congregation/stream. Continue?" — the one place TIME-UP gets a confirmation, because it's the irreversible-surprise risk the persona fears (FR-062, §0.6).
- **Audio cue to an output (FR-063):** default is operator-local only; routing an audible cue to any output requires explicit per-output selection **+ confirm**, and default-excludes audience/house outputs (mirrors FR-062).
- **Count-up / open-ended (B3):** elapsed timer, or manual **TIME UP** trigger sent by the Stage Manager with no countdown.
- **Operator-only timer (FR-058):** a timer visible to the operator but on no stage/audience output — for silent pacing.
- **Mobile dismissal:** Timer Operator dismisses TIME UP / adjusts from mobile (FR-094/FR-061) — Flow 6.
- **Audio-feedback guard (FR-172, R3):** if an alert sound routes to a shared/house output while transcription runs, ingestion is suppressed so the app doesn't transcribe its own beep.

### Safety / A11y

The **Show-on** scoping block is the primary safety mechanism — audience outputs are opt-in with a guard (FR-062). TIME UP flash respects the ≤3/sec seizure limit and Reduced Motion (a non-flashing high-contrast TIME UP is the reduced-motion variant, FR-175). Timer text is large/high-contrast for stage-lighting legibility (NFR-020). All controls keyboard + mobile ≥44×44pt.

---

## Flow 5 — Emergency clear / blackout `[MVP]`

**Goal.** In one instant action, remove content or blank the audience output — with zero network dependency — and get it back just as fast. The operator's panic button (JTBD-6, "fear of a black screen during offering").
**Actor.** Church Media Operator (any live seat); Production Operator / Admin on mobile.
**Entry point.** **Always available** — global keyboard, always-visible safety-bar buttons (§0.3), command palette, and mobile.
**Preconditions.** None. Works offline, mid-crash-recovery, during any failure.
**Trace.** FR-076 (clear per/all-layer), FR-077 (blackout), FR-078 (per-layer), CON-2; WORKFLOWS §Governing; personas §1.1 pain points.

### Key screen — the always-present safety rail (+ per-layer clear)

```
 SAFETY BAR (top of every screen)
 ┌───────────────────────────────────────────────────────────────────────────┐
 │  [ ⛶ BLACKOUT  (B) ]          [ ✕ CLEAR ALL  (Esc Esc) ]        ●CLOUD off  │
 └───────────────────────────────────────────────────────────────────────────┘
        │                                  │
        ▼ toggles audience to black        ▼ removes all live layers
     (un-blackout restores exact prior)  (undo restores)

 Per-layer clear (⌘K → "Clear…", or right-click the Live pane):
   [ Clear Text ]  [ Clear Background ]  [ Clear Lower-third ]  [ Clear Media ]
      Esc              (each independent — FR-078; others untouched)
```

### Happy path — blackout

| # | Operator action | System response |
|---|---|---|
| 1 | Press **`B`** (or tap **BLACKOUT**) | Audience output(s) go black <200ms, **offline, no confirmation** (FR-077). Safety-bar button switches to a lit "UN-BLACKOUT" state; Stage/confidence keeps showing content so the platform team isn't blind |
| 2 | Press **`B`** again | Un-blackout restores the **exact prior content** that was live before (FR-077) |

### Happy path — clear

| # | Operator action | System response |
|---|---|---|
| 1 | Press **`Esc Esc`** (or tap **CLEAR ALL**) | All live layers removed from output <200ms, offline (FR-076) |
| 2 | *or* Press **`Esc`** / pick one layer | Only the focused/selected layer clears; others untouched (FR-078) |
| 3 | `⌘Z` / re-stage | Prior live content restored |

### Branches

- **During a failure:** blackout/clear remain functional while a display/audio/mobile/provider/AI failure banner is showing — they are on the isolated control path (NFR-024). This is the "calm under pressure" guarantee.
- **From mobile:** Presenter/Production/Admin roles (per matrix) can blackout; `⚠`/scoped roles per PERSONAS §2. Open decision OD-12 (blackout for lower roles as a panic button) is flagged.
- **Blackout vs Clear distinction (surfaced in UI tooltip):** *Blackout* = temporary blank, remembers what to bring back; *Clear* = removes the content itself. Two buttons, never merged, so intent is unambiguous under pressure.

### Safety / A11y

These actions are deliberately **un-guarded** because they *are* the safety mechanism and are reversible (§0.6) — a confirmation modal here would be the hazard. Both are keyboard-first with SR names/roles/state (NFR-021), always in the tab order, and mirrored on mobile ≥44×44pt. Blackout/un-blackout is an instant state change, not an animation (Reduced-Motion-safe by default).

---

## Flow 6 — Pair a mobile controller (QR) & advance a slide `[MVP]`

**Goal.** A roaming user pairs a phone/tablet in seconds and advances slides with role-appropriate controls only — the desktop stays the authority and validates every request.
**Actor.** Mobile Remote User + System Administrator/desktop (approves).
**Entry point.** Desktop: **Settings → Pairing → Show QR**. Mobile: **SelahCue app → Scan to connect**.
**Preconditions.** Desktop running; pairing enabled; device on same LAN (or QR-only fallback if multicast blocked).
**Trace.** FLOW-004; FR-085 (discover), FR-086 (QR + host confirm), FR-087 (remember host), FR-088 (TLS), FR-089 (revocable), FR-090 (server RBAC), FR-091 (replay/rate-limit), FR-092/093 (preview + advance), FR-097/098 (reconnect, desktop unaffected); WORKFLOWS A4/B4/F3; threat T1/T18; personas §1.10.

### Key screens

```
 DESKTOP — pairing                          MOBILE — scan → role-scoped controller
 ┌─ PAIRING ───────────────────────┐        ┌──────────────────────────┐
 │  Grant role: [ Presenter  ▾ ]   │        │  ●  Connected            │
 │  ┌──────────┐                    │        │  Sunday AM · Presenter   │
 │  │ ▓▒░ QR ░▒│  fingerprint:       │        │ ┌──────────────────────┐ │
 │  │ ░▒▓ code │  4F:A2:…:9C         │        │ │  LIVE  (current)     │ │
 │  └──────────┘  expires in 0:48    │        │ │  "Great is thy…"     │ │
 │  ── waiting for device ──          │        │ └──────────────────────┘ │
 │                                    │        │  NEXT ▸ "Morning by…"    │
 │  ⏵ "Studio iPad" requests pairing  │        │ ┌────────┐  ┌──────────┐ │
 │     as Presenter                   │        │ │ ◀ PREV │  │  NEXT ▶  │ │  ≥44×44pt
 │     [ Approve ]   [ Deny ]         │        │ └────────┘  └──────────┘ │
 └─────────────────────────────────┘        │  [ Clear ]     [ ⛶ Black ]│
                                             └──────────────────────────┘
```

### Happy path

| # | Actor · action | System response |
|---|---|---|
| 1 | Admin (desktop): open Pairing, pick the role to grant (e.g. **Presenter**), Show QR | Desktop advertises via mDNS (FR-085) and renders a single-use, short-TTL QR carrying host **fingerprint + ephemeral secret** (FR-086) |
| 2 | User (mobile): open app → **Scan to connect**; app lists discovered hosts or scans QR | Mobile pins the host cert fingerprint from the QR (defeats LAN MITM, FR-088); requests pairing with the offered role |
| 3 | Admin (desktop): a **request card** appears → **Approve** | Pairing completes only on host approval (FR-086/T1). Device bound to a keypair-issued, revocable token scoped to the role (FR-089/090). Both ends show **Connected** |
| 4 | User (mobile): sees **only** role-appropriate controls + live current/next preview | Client-asserted role is never trusted; the desktop shows exactly the matrix capabilities for Presenter (PERSONAS §2). Preview streamed over TLS (FR-088/092) |
| 5 | User taps **NEXT ▶** | Mobile sends an `advance` request (nonce+timestamp). Desktop validates role + replay window ±30s + rate limit (FR-090/091), executes on the authoritative output, echoes new state back; **desktop acts ≤200ms on LAN** (FR-093/NFR-009) |

### Branches

- **QR-only fallback (FR-085/C14):** when multicast/mDNS is blocked, discovery falls back to QR scan only — same security.
- **Fast reconnect (B4/FR-087):** a previously paired device reconnects via pinned fingerprint + device proof-of-possession, no fresh QR, re-auth each session; still admin-revocable.
- **Mobile connectivity loss (F3/FR-097):** mobile shows **"Reconnecting…"** and disables its controls; desktop marks it disconnected but **retains full authority** (FR-098). In-flight/stale requests that can't be validated are **rejected, not replayed** — no ghost slide-advance seconds later. On reconnect the desktop re-validates role and re-syncs current live state before re-enabling controls.
- **Revoke / downgrade (FR-089):** Admin revokes a device on the Pairing-management screen (FR-148) → dropped mid-session immediately; a downgrade takes effect on the next command.
- **Manual PIN (B4):** pairing without QR via a short PIN.
- **Role mismatch:** a request outside the granted role is denied server-side and surfaced on mobile as "Not permitted for your role" (FR-090) — the mobile never shows controls it can't use (persona §1.10 pain point).

### Safety / A11y

The **host-side Approve** step is the anti-spoof gate (T1/T18) — pairing is never automatic. Connection status is always visible on both ends (persona pain: "unclear whether an action reached the desktop"). All mobile targets ≥44×44pt with accessible labels (NFR-026); high-contrast; the LIVE/Blackout controls mirror desktop semantics so muscle memory transfers.

---

## Flow 7 — Crash recovery + crash-loop breaker `[MVP]`

**Goal.** After a crash or forced kill, restore the exact live state fast (≤5s data loss) — and if the app is crash-looping, **do not silently re-crash**; give the operator a safe choice.
**Actor.** Church Media Operator. Desktop.
**Entry point.** App relaunch after an abnormal exit (auto or manual).
**Preconditions.** Continuous autosave has been checkpointing live state + plan position + timers (FR-074).
**Trace.** FLOW-008; FR-074 (autosave ≤5s), FR-075 (recovery + **crash-loop breaker**), FR-169 (storage-exhaustion guard), NFR-023; WORKFLOWS F5/F7; MAJOR-02; personas §1.1 ("software crashing mid-service").

### Key screen A — normal resume (≤ N crashes)

```
┌─ WELCOME BACK ─────────────────────────────────────────────────────────────┐
│  SelahCue closed unexpectedly during "Sunday AM Service".                    │
│                                                                              │
│  Restore your live state from the last checkpoint (3s before the crash)?     │
│    • Live: Song "Great Is Thy Faithfulness" — Chorus                         │
│    • Plan position: item 2 of 5                                              │
│    • Timers: Sermon countdown re-anchored to wall-clock → 22:41 remaining    │
│                                                                              │
│     [ ▶ Resume service ]            [ Start clean ]                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Key screen B — crash-loop breaker (after N rapid crashes — FR-075)

```
┌─ ⚠ REPEATED CRASHES DETECTED ──────────────────────────────────────────────┐
│  SelahCue has crashed 3 times in quick succession. It will NOT auto-resume   │
│  so it doesn't crash again on the same content.                              │
│                                                                              │
│  Suspected cause:  plan item 4 "Sermon bumper.mp4" (crashed on load)         │
│                                                                              │
│   ( ) Resume last live state        (may re-trigger the crash)              │
│   (•) Start clean / skip last item  ← recommended                           │
│        └─ item 4 will be DISABLED and flagged for review                     │
│                                                                              │
│           [ Continue ]        [ Advanced: safe mode ▾ ]                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Happy path

| # | Operator action | System response |
|---|---|---|
| 1 | (Background, always) service runs | Live state + plan position + running timers checkpoint continuously; ≤5s work-loss bound (FR-074/NFR-023). Storage-exhaustion guard reserves checkpoint headroom (FR-169) |
| 2 | App crashes / is force-killed → operator relaunches | On launch, SelahCue detects the prior session ended abnormally |
| 3 | **Screen A** appears → **Resume service** | Restores loaded plan + last known live position (current slide/verse/layer); **countdowns re-anchored to wall-clock, count-ups resume accumulated** (FR-075). Outputs re-initialise and the restored live state is re-pushed to the correct displays (WORKFLOWS F5.3) |
| 4 | (Auto) paired mobiles reconnect | They re-sync via F3; buffered transcript (R3) recovered to last checkpoint |

### Branches

- **Crash-loop (FR-075 / MAJOR-02):** after **N rapid crashes**, SelahCue shows **Screen B** instead of auto-resuming. It names the **suspected offending item**, defaults to **Start clean / skip last item**, and **disables** that item so a resume can't re-trigger the crash. "Resume last live state" is still offered but clearly marked as risky.
- **Safe mode (FR-081, R2):** "Advanced" boots with minimal subsystems (no media engine / no AI) so the operator can at least drive text slides while diagnosing.
- **Forced shutdown / power loss (F7):** identical resume path from the on-disk checkpoint; if a redundant second operator machine exists it can act authoritative in the interim, then hand back (WORKFLOWS F7.3).
- **Storage exhaustion (FR-169):** if disk is low *before* the crash, the operator has already seen a non-blocking "Low disk — recovery headroom protected" warning; a write failure is always surfaced, never silent.
- **Start clean:** operator declines resume; app opens the plan at position 0 with nothing live (no output change until they Go Live).

### Safety / A11y

The crash-loop breaker is the anti-footgun: the app refuses to silently repeat the crash and defaults to the safe option (§0.6). Re-pushing to outputs never blanks a working output as a side effect (NFR-024). Both dialogs are fully keyboard-operable with a clear default focus on the recommended button; text (not colour) states the recommendation.

---

## Flow 8 — Missing-media pre-service check `[MVP]`

**Goal.** Catch every unresolved media file (and every unhealthy subsystem) *before* the service, so nothing black-screens mid-service. And if something slips through, degrade to a placeholder — never a black audience screen.
**Actor.** Service Coordinator (planning) → Church Media Operator (service day).
**Entry point.** Automatically at **plan open**; manually via **Pre-service check** button.
**Preconditions.** A plan is open.
**Trace.** FR-007 (missing-media detection), FR-008 (pre-service checklist), FR-070 (placeholder never black); WORKFLOWS A1.5/F6; personas §1.8 pain ("media missing on service day").

### Key screen — pre-service checklist (one glanceable screen, FR-008)

```
┌─ PRE-SERVICE CHECK ───────────────────────────────── Sunday AM · 08:41 ──────┐
│  ✓ Outputs        Main ● 1920×1080  ·  Stage ● 1280×720            OK         │
│  ⚠ Media          1 of 12 items unresolved                        Attention   │
│       └ item 4 "Sermon bumper.mp4"  → moved/missing                            │
│          [ Relink… ]  [ Replace… ]  [ Skip item ]                             │
│  ✓ Audio input    "USB Pulpit Mic" · signal ▁▃▅▂                  OK  (R3)    │
│  ✓ Storage        212 GB free                                      OK         │
│  ✓ Pairing        2 devices paired · both reachable               OK         │
│  ─────────────────────────────────────────────────────────────────────────── │
│  1 item needs attention.        [ Re-run check ]     [ Start service ▸ ]      │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Happy path

| # | Operator action | System response |
|---|---|---|
| 1 | Open the plan (or click **Pre-service check**) | One screen reports each subsystem OK / Attention with actionable detail (FR-008): outputs, media, audio input, storage, pairing |
| 2 | (Auto) media validation runs | Every item whose file is missing/moved is flagged with a remediation prompt (FR-007) |
| 3 | For a flagged item → **Relink…** (point at the moved file) or **Replace…** | The item resolves; badge clears; planned length recomputes |
| 4 | **Re-run check** | All subsystems re-validate; green when clear |
| 5 | **Start service** | Console opens with confidence that cues resolve |

### Branches

- **At planning (A1.5):** the coordinator sees the same missing-media badges in the builder (Flow 1) and relinks/replaces before publish — catching it days early.
- **Slipped through to service time (F6/FR-070):** if a missing item is *triggered* live, SelahCue **does not black out** — it holds the prior content or shows a **safe placeholder** and alerts the operator. The operator skips, substitutes, or relinks on the spot; the run continues.
- **Output not connected:** the Outputs row shows Attention with **Identify displays** (FR-040) to sort out which physical screen is which.
- **Audio input missing (R3):** the Audio row flags it; not a blocker for MVP presentation (transcription is R3).
- **Storage low (FR-169):** Storage row warns before capture/autosave can fail.

### Safety / A11y

This flow is the *preventive* half of the never-black-screen guarantee; FR-070 placeholder is the *runtime* safety net. "Start service" is never blocked by an Attention item — the operator stays in control and decides (calm-under-pressure). Each row states status in words + icon (not colour alone), fully keyboard-navigable.

---

## Flow 9 — Start transcription & select input `[R3]`

**Goal.** Capture the right mic feed and produce a live, timestamped transcript that assists (captions/detection/notes) **without ever touching live output**.
**Actor.** Sound Engineer (selects the source) + operator (starts). Desktop.
**Entry point.** **Transcription** panel; or the pre-service Audio row (Flow 8).
**Preconditions.** An audio input device available; a local engine (default) or a consent-gated cloud provider configured.
**Trace.** FLOW-005; FR-099 (input select + level), FR-100 (start/pause/resume/stop), FR-101 (offline default + HW auto-select), FR-102 (VAD gating), FR-103 (interim vs confirmed), FR-104 (degrade gracefully), FR-166 (verbatim caption OFF by default), FR-167 (language/locale), FR-170 (capture-device disconnect); WORKFLOWS A5/B5/F2; personas §1.7.

### Key screen — transcription panel

```
┌─ TRANSCRIPTION ─────────────────────────────── engine: [ Local (Whisper) ▾ ] ┐
│  Input: [ USB Pulpit Mic         ▾ ]   level ▁▃▅▇▅▃▂   language [ English ▾ ] │
│  Model: small (auto-selected for this hardware ✓ real-time)                    │
│  ●CLOUD off — audio stays on this device                                      │
│  ────────────────────────────────────────────────────────────────────────── │
│  [ ▶ Start ]  [ ⏸ Pause ]  [ ⏹ Stop ]        on-screen captions: [ OFF ] ⚠    │
│  ────────────────────────────────────────────────────────────────────────── │
│  09:14:02  …and we know that all things work together for good,   ✓confirmed  │
│  09:14:09  to those who love God, who are called according…       ✓confirmed  │
│  09:14:15  ‹for his purpose. Now Paul goes on to say›              …interim    │  ← provisional style
└────────────────────────────────────────────────────────────────────────────────┘
```

### Happy path

| # | Actor · action | System response |
|---|---|---|
| 1 | Sound Engineer: pick the **input device** (e.g. USB Pulpit Mic) | A live **level meter** reflects the signal; selection persists (FR-099) |
| 2 | (First run) hardware probe | Auto-selects a model that sustains real-time; warns if it cannot (FR-101/104) |
| 3 | Operator: select language/locale | Applied to the recognizer; persists (FR-167) |
| 4 | Operator: **Start** | Transcription begins on-device by default (FR-101); **●CLOUD off** confirms nothing leaves the host. Effect visible within 1s (FR-100) |
| 5 | (Auto) speech recognised | **Interim** text shows in a distinct provisional style; **confirmed** segments carry timestamps and persist (FR-103). VAD gates silence/music so non-speech doesn't hallucinate committed text (FR-102) |
| 6 | Operator: **Pause / Resume / Stop** | Each reflected in transcript state within 1s (FR-100); on Stop, transcript saved to the service record and survives restart (FR-105) |

### Branches

- **On-screen captions (FR-166):** verbatim ASR captioning to an output is an **advanced opt-in, OFF by default**; the toggle carries a `⚠` because ASR errors would be audience-visible. Interim caption text always uses provisional styling.
- **Insufficient hardware (FR-104):** status shows **"degraded / paused"** or drops to a smaller model — **slide control is never affected** (the whole panel can fail and presentation continues).
- **Capture-device disconnect (F2 / FR-170):** transcription **pauses (does not crash)**; captured segments preserved; the operator/engineer is alerted with the device name. On reconnect or new-input selection, a **visible gap marker** is inserted and transcription resumes. Presentation untouched throughout.
- **Cloud provider (B5 → Flow-N settings):** using a cloud STT requires a per-provider opt-in; while active, the **●CLOUD** badge is lit (FR-132/133). Graceful fallback to local on error (FR-135).
- **Audio-feedback guard (FR-172):** if app audio plays to a shared/house output, ingestion is suppressed so the app doesn't transcribe itself.

### Safety / A11y

Transcription is strictly **assistive** — it never writes to a live output on its own (WORKFLOWS A5). The ●CLOUD indicator and the default-OFF captions are the privacy/mistake guards. Provisional vs confirmed uses styling **plus** a word/icon, not colour alone. Panel is keyboard-operable; the level meter has a text/numeric equivalent for SR users.

---

## Flow 10 — Approve a detected scripture suggestion `[R4]`

**Goal.** When the preacher speaks a reference, surface a **suggestion** the operator can approve — **nothing auto-displays by default** (JTBD-2, the human-in-the-loop gate).
**Actor.** SelahCue auto-detection + Scripture Operator (approver). Desktop or mobile.
**Entry point.** A live transcript running (Flow 9) with scripture detection enabled; suggestions appear in a side **Suggestion queue**.
**Preconditions.** Live transcript; detection enabled; local Bible index available.
**Trace.** FLOW-006; FR-111 (staged pipeline), FR-112 (spoken-ref parse), FR-113 (fuzzy/semantic = suggestions only), FR-114 (confidence + dedup + cooldown), **FR-115** (operator-confirmation default), **FR-116** (auto-display corroboration gate + warning), FR-117 (card actions + 5s undo), FR-119 (never blocks manual), FR-120/121 (disclosed limits, precision-over-recall); WORKFLOWS A6/B6; personas §1.2.

### Key screen — suggestion queue + card (violet, never on an output)

```
┌─ SCRIPTURE SUGGESTIONS ───────────── mode: [ Operator confirmation (default) ▾ ] ┐
│                                                                                   │
│  ┌─ suggestion ─────────────────────────────────────────────  92% confidence ─┐ │
│  │  Romans 8:28   ·   WEB                                     (explicit ref)   │ │
│  │  "And we know that all things work together for good…"                      │ │
│  │  heard: “…turn with me to Romans chapter eight verse twenty-eight…”         │ │
│  │  alternatives: Rom 8:28 (BSB) · Rom 8:28–30                                 │ │
│  │  ───────────────────────────────────────────────────────────────────────── │ │
│  │  [ ✓ Approve → Preview ]  [ ⇥ Edit ]  [ ▶ Display ]  [ ✕ Reject ]  [ Ignore ]│ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│  ┌─ suggestion ───────────────────────────────────  61% · quote (fuzzy) ⚠ ────┐ │
│  │  John 3:16?  paraphrase match — review carefully                            │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│  ⓘ Detection is reliable for explicit refs, fallible for quotes, unreliable for  │
│     paraphrase. It never displays on its own.                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### Happy path (default = operator confirmation)

| # | Operator action | System response |
|---|---|---|
| 1 | (Background) detector monitors the confirmed transcript | Staged pipeline: deterministic parse → exact → fuzzy → semantic → confidence; deterministic results **outrank** semantic guesses (FR-111). It resolves against the **local** index and creates a **queued suggestion — it does not display anything** (WORKFLOWS A6.2) |
| 2 | Operator sees a **suggestion card** with reference, passage, translation, **confidence**, alternatives, and the **reason/heard-text** (FR-117) | Duplicates within the cooldown (default 60s) and the on-screen passage are suppressed (FR-114) |
| 3 | Operator **Approve → Preview** (or **Edit** the range/translation first) | Passage stages into **Preview**, not live (respects the preview gate). Or **Display** stages straight to the configured target |
| 4 | Operator sends to Live + advances (as **Flow 3**) | Correct verse on output; a **quick-undo reverts a display within 5s** (FR-117) |
| 5 | Operator **Reject / Ignore** a false positive | It becomes a dismissed queue item — **never a wrong verse on screen** (WORKFLOWS A6). Decision recorded in detection history (FR-118) |

### Branches

- **Preview-only org policy (B6):** detection auto-stages to **Preview only, never live**; the operator must always send to live manually.
- **Auto-display mode (FR-115/116) — discouraged:** enabling it shows an explicit **wrong-verse risk warning**; it is available **only for explicit refs above a threshold**, requires a **corroboration gate** before unattended display, and **semantic-only matches are barred**. This is the most-guarded toggle in the app (§0.6).
- **Quote / paraphrase:** verbatim quotes match; paraphrase surfaces low-confidence candidates marked `⚠` "review carefully" — surfaced as **suggestions only** (FR-113), precision-over-recall defaults keep false positives ≤5% on the eval set (FR-121/METRIC-009).
- **Detection fails / provider down (F4):** suggestions stop; operator falls back to **manual search (Flow 3)** — detection **never blocks manual control** (FR-119).
- **Mobile approval (FR-095):** a mobile Scripture Operator approves from a tablet near the stage — same gate, executed by the desktop (Flow 6).

### Safety / A11y

The entire flow embodies "no AI auto-action without operator confirmation." Suggestions live in a violet side queue and **never render to an output** until approved. The always-visible capability disclosure (ⓘ) prevents over-trust (FR-120). Confidence is shown as a number + label, not colour alone. Cards are keyboard-navigable (`↑/↓` between suggestions, `Enter`=approve, `Del`=reject) with SR-announced confidence and reason.

---

## Flow 11 — Generate & edit sermon notes `[R5]`

**Goal.** Turn a stored transcript into an editable sermon-note draft the human owns — clearly labelled AI-generated, with fabrication disclosed and references verified — to publish by Monday (JTBD-5).
**Actor.** Post-Service Media / Sermon Editor + AI. Desktop primary.
**Entry point.** **Post-service workspace → select a saved transcript → Generate notes**.
**Preconditions.** A saved transcript exists (Flow 9); a note-generation provider configured (local default).
**Trace.** FLOW-007; FR-122 (structured notes), FR-123 (editable, labelled, source untouched), FR-124 (timestamp links + chapters), FR-125 (reference verification / unverified flag), FR-126 (summaries/excerpts), FR-127 (exports), FR-128 (fabrication disclosure), FR-129 (regenerate keeps prior), FR-130 (editor access); WORKFLOWS A7/B7; personas §1.11.

### Key screen — notes editor (transcript ↔ editable draft)

```
┌─ SERMON NOTES  ·  "Sunday AM Service"  ─────────────  🏷 AI-GENERATED · review ┐
│  ⓘ AI notes may fabricate or misattribute. Review before publishing. (FR-128)  │
├───────────────────────── TRANSCRIPT (raw, read-only) ─┬─ NOTES (editable) ─────┤
│ 09:14  …all things work together for good…            │ Title: The Good Purpose │
│ 09:15  …to those who love God, called according…      │ ─────────────────────── │
│ 09:22  …Joseph's story shows us…                      │ Main scripture:         │
│ 09:31  …three things about God's purpose…             │  • Romans 8:28 ✓verified │
│        ▲ click a note item to jump to its timestamp    │  • “Jer 29:11” ⚠unverified│
│                                                        │ Points:                 │
│                                                        │  1. God works in all…   │
│                                                        │     ↳ 09:31             │
│                                                        │  2. …                   │
│  raw transcript is NEVER modified by generation (FR-123)                        │
├────────────────────────────────────────────────────────────────────────────────┤
│  [ ↻ Regenerate ▾ ]  version 2 (v1 kept)   [ Export ▾: MD·PDF·DOCX·TXT·JSON ]   │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Happy path

| # | Operator action | System response |
|---|---|---|
| 1 | Open the post-service workspace; select a completed transcript; **Generate notes** | Editor persona can open transcript + notes + detected-scripture list (FR-130). Generation runs (local default; ●CLOUD only if opted in) |
| 2 | (Auto) draft produced | Structured notes: title(s), main/supporting scripture, intro, points/sub-points, illustrations, quotes, prayer points, calls-to-action, key lessons, summary (FR-122). Note items **link to transcript timestamps** (FR-124). Draft opens **editable, never read-only**, with a persistent **🏷 AI-GENERATED** label + fabrication disclosure (FR-123/128) |
| 3 | (Auto) references verified | Every reference in the notes is checked against the **local Bible index**; unmatched refs flagged **`⚠unverified`** until matched (FR-125) |
| 4 | Editor corrects/reorganises; fixes misattributions/hallucinations; cross-checks refs | Edits touch only the notes layer; the **raw transcript is unchanged** (FR-123). Click any note item to jump to its source timestamp (FR-124) |
| 5 | Editor generates derived artifacts | Summary, social excerpts, podcast show notes, short description, full outline — each independently editable/exportable (FR-126) |
| 6 | **Export** | TXT / Markdown / PDF / DOCX / JSON / clipboard, each well-formed (FR-127) |

### Branches

- **Regenerate (FR-129):** re-run with a different provider/settings; the **prior version is retained until replaced** ("v1 kept").
- **From an edited transcript (B7):** editor cleans the transcript first (via the R3 correction layer, non-destructive over the immutable raw stream) then generates; or regenerates one section only.
- **Generation fails (F4):** the **raw transcript remains intact** for manual notes or later retry; no data lost.
- **Unverified reference:** stays flagged `⚠unverified` and is **never silently trusted** — the editor confirms or corrects before publish (FR-125), reinforcing the fabrication-risk posture (FR-128).
- **Chapters/markers (FR-124):** chapter / YouTube-chapter markers export for video description.

### Safety / A11y

The immutable-transcript rule (FR-123) and the always-present AI-GENERATED label + fabrication disclosure (FR-128) are the trust guards — the human owns the output. `⚠unverified` uses word + icon, not colour alone. The split transcript↔notes view is keyboard-navigable; timestamp jumps are operable via keyboard; exports are labelled with format + accessible names.

---

## Appendix A — Keyboard cheat-sheet (printable booth card)

```
 LIVE DRIVING                         SAFETY (always available, reversible)
 ─────────────                        ────────────────────────────────────
 Enter    Go Live (Preview→Live)      B          Blackout audience (toggle)
 Space/→  Next                        Esc Esc    Clear ALL live layers
 ←        Previous                    Esc        Clear focused layer
 ↑ / ↓    Select item/slide (Preview) ⌘/Ctrl Z   Undo edit (not live trigger)

 FIND & GO                            SONGS / SCRIPTURE
 ─────────                            ─────────────────
 ⌘/Ctrl K  Command palette            R   Repeat section     ⌘/Ctrl L  Scripture search
 ⌘/Ctrl I  Identify displays          J   Jump to section
```
All bindings are remappable (FR-014). Emergency actions are single-key and never behind a modal.

## Appendix B — State legend (glanceable)

`●`LIVE(red) · `▶`staged/preview(amber) · `✓`OK(green) · `⚠`attention/degraded(amber) · `●CLOUD`data-leaving-device(blue) · violet-card = AI suggestion (never on an output). Colour is always paired with an icon/word (WCAG 1.4.1).

## Appendix C — Flow → requirement trace

| Flow | FLOW | Primary FRs | Workflow | Persona |
|---|---|---|---|---|
| 1 Build & open plan | FLOW-001 | FR-001…008, 139 | A1/B1 | §1.8 → §1.1 |
| 2 Go live with a slide | FLOW-001 | FR-012/013/009/024/076 | A(core) | §1.1 |
| 3 Scripture from search | FLOW-002 | FR-025…031/035 | A2/B2 | §1.2 |
| 4 Countdown → TIME UP | FLOW-003 | FR-054…065 (esp. 062) | A3/B3 | §1.5 |
| 5 Emergency clear/blackout | — | FR-076/077/078 | Governing | §1.1 |
| 6 Pair mobile & advance | FLOW-004 | FR-085…094/097/098 | A4/B4/F3 | §1.10 |
| 7 Crash recovery + loop breaker | FLOW-008 | FR-074/075/169 | F5/F7 | §1.1 |
| 8 Missing-media pre-service | — | FR-007/008/070 | A1.5/F6 | §1.8 |
| 9 Start transcription | FLOW-005 | FR-099…104/166/167/170 | A5/B5/F2 | §1.7 |
| 10 Approve detected scripture | FLOW-006 | FR-111…121 | A6/B6 | §1.2 |
| 11 Generate & edit sermon notes | FLOW-007 | FR-122…130 | A7/B7 | §1.11 |

## Appendix D — Cross-cutting UX invariants checklist (every flow honours these)

- [ ] Preview ≠ Live — nothing reaches an audience output without an explicit Go Live (FR-012).
- [ ] Blackout + Clear-all always visible, offline, <200ms, reversible, no modal (FR-076/077).
- [ ] Desktop authoritative — mobile/AI/providers request; losing them disables nothing (CON-1/FR-098).
- [ ] No AI auto-action — detection/notes/transcription never change live output on their own (FR-083/115).
- [ ] Fail safe — failures are non-blocking banners; live output is held, never blanked as a side effect (NFR-024).
- [ ] Keyboard-first + SR names/roles/state on core live controls (NFR-019/021).
- [ ] WCAG-AA contrast; stage text ≥48px-equiv high-contrast; colour never the only signal (NFR-020).
- [ ] Motion ≤3 flashes/sec + global Reduced Motion (FR-175).
- [ ] Mobile targets ≥44×44pt with accessible labels (NFR-026).

---

## Flow 12 — Enable a cloud AI provider (consent) [R3] (Stage-5 review M11)

**Goal:** an Administrator opts a church into a cloud transcription/notes provider, with full disclosure and consent, before any sermon data leaves the host.
**Entry:** Settings → AI Providers → "Enable cloud provider" (Administrator only — FR-137).

1. **Disclosure state.** A panel names the provider, **exactly what is sent** (audio? transcript? notes?), that **data leaves the local network/jurisdiction**, the provider's data-retention/​training-use link, and that a DPA applies (FR-132/136/177). Nothing is sent yet.
2. **Explicit confirm.** The Administrator must actively check "I understand and consent" and enter/paste the provider API key (stored only in the OS secret store — FR-134). A non-Administrator cannot reach this step (server-side gate).
3. **Enabled + indicator.** On confirm, the provider is enabled and a persistent **"CLOUD ACTIVE"** indicator appears wherever data is being transmitted (FR-133) — desktop status bar and mobile banner.
4. **In-use / error / offline states.** While active: usage + estimated cost surface (FR-136). On provider error or network loss: **auto-fallback to local**, live output unaffected, a non-alarming "cloud unavailable — using on-device" notice (FR-135).
5. **Revoke / purge.** "Disable & remove key" purges the key from the secret store, drops the CLOUD-ACTIVE indicator immediately, and offers to delete any data already sent per the provider's terms (disclosing what the app cannot reach) (FR-153).

**States (also in UX-STATE-MATRIX):** disclosure → explicit-confirm → admin-gated-enabled → cloud-active → error/offline (local fallback) → revoke/purge. **Safety:** default is OFF; no audio/transcript/notes leave the host without step 2; the indicator makes the current posture unmistakable.

---

*End of UX-FLOWS v1.0 (Stage 5). Un-validated design intent — to be corrected by usability testing (METRIC-006).*
