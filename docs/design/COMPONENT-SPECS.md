# SelahCue — Component & Interaction Specifications

> **Canonical rules:** [UX-CANONICAL.md](UX-CANONICAL.md) governs keybindings (Go Live = `Enter`, distinct from Next; Clear = `Esc Esc`; Blackout = `B`, with non-unbindable global fallbacks), the Undo-live model, always-on emergency chrome, and colour tokens (green=PREVIEW, red=LIVE, amber=WARN, always with a non-colour label). It supersedes any conflicting inline statement here (Stage-5 review B1/M8/M9/M10).

Version: 1.0 (Stage 5, UX) · Date: 2026-07-23 · Owner: UI/UX Designer · Status: For architecture + engineering review

**Scope.** Implementation-ready interaction specs for the live-operation building blocks of the SelahCue operator console (desktop, authoritative) and companion mobile controller. Sources: PRD `docs/product/prds/SelahCue-PRD.md`, personas `docs/business/PERSONAS.md`, workflows `docs/business/WORKFLOWS.md`, architecture `docs/architecture/ARCHITECTURE.md`. Requirement IDs (FR-/NFR-/FLOW-) are cited inline and are the normative acceptance surface.

**Design stance — live operation first.** Every screen is designed to be driven at speed, by keyboard, under pressure, in a dark booth or under stage lighting, by a volunteer who learned the tool this month. The three questions each spec answers: *Can I do it in one glance and one key? Can it hurt the congregation if I slip? Can I undo it before anyone notices?*

---

## 0. How to read this document

### 0.1 ASCII wireframe conventions

```
┌─┐ └─┘  panel / container border          [ Button ]   push button
▸ ▾      collapsed / expanded disclosure    [[ Button ]] primary / default button
◀        current live pointer               ( ) [x]      radio / checkbox
●        active / on            ○  inactive  ▓▓▓░░        meter / progress
⚠        attention / warning     ✕  close     |cursor|     focus ring (described in prose)
↑↓←→     arrow-key affordance                “LIVE”       state word (never colour-only)
```

Wireframes are **low-fi and indicative** — they fix layout hierarchy and control adjacency, not pixel metrics. Sizing/contrast tokens are in §2.

### 0.2 Annotation legend used in every component

Each component is specified under a fixed set of headings so engineering can implement without ambiguity:

- **Purpose** — the job it does and the persona/JTBD it serves.
- **Key states** — the finite states and transitions (the state machine).
- **Interaction — mouse/touch** and **Interaction — keyboard** — the two operable paths; both are mandatory for core live actions (NFR-019).
- **Inputs / outputs** — data in, events/commands out.
- **Error & edge handling** — failure, empty, contested, and boundary cases.
- **Accessibility** — accessible role + name, focus behaviour, contrast, minimum target size (NFR-019/020/021/026, FR-175).

### 0.3 The five invariants every component honours

1. **Preview ≠ Live.** Authoring/staging never changes any audience output until an explicit *Go Live* / *Display* (FR-012, WORKFLOWS A2).
2. **Emergency Clear & Blackout are always reachable and always local.** No modal, no network, no AI in their path; <200ms; reachable by dedicated key and on-screen control from any focus (FR-076/077, CON-2).
3. **Desktop stays authoritative.** Mobile and AI issue *requests*; the desktop validates and executes. UI never lets a mobile/AI surface appear to own live state (CON-1, PERSONAS §2.2).
4. **No AI auto-action.** Nothing an AI produces reaches an audience output without a human action in the same UI (FR-115/117, WORKFLOWS A6).
5. **Fail safe, never surprising.** No component's failure, empty, or error state may blank or clear an audience output as a side effect; failures surface as non-blocking indicators while the last-good frame holds (NFR-024, WORKFLOWS governing-principle 4).

---

## 1. Interaction-model summary

### 1.1 Two modes, one console

SelahCue is not modal in the trap-you-in-a-mode sense — authoring and operating coexist so an operator can fix Sunday's plan while it is live. "Mode" describes **which surface has intent**, signalled persistently, never hidden:

| Mode | What it governs | Persistent signal | Invariant |
|---|---|---|---|
| **Edit / Author** | Plan structure, slide/song/scripture content, templates, timer presets | Editor panel has the caret; **Preview** pane shows the staged result | Changes are local to Preview/library; **zero effect on Live** until Go Live (FR-012) |
| **Live / Operate** | What is on each audience output right now | Global **“● LIVE”** badge top bar; **Live** pane framed red; Current/Next reflect program | Every action here is audience-facing and logged (FR-150) |

The boundary between them is the **Preview↔Live control** (§5). Nothing crosses from Edit to Live except through it.

### 1.2 Confirmation model — four tiers

Confirmation is calibrated to *reversibility × audience exposure*. Over-confirming slows a live operator into mistakes; under-confirming lets a slip reach the congregation. The tiers:

| Tier | Applies to | Confirmation | Rationale |
|---|---|---|---|
| **T0 — Instant, silent** | Next/Prev slide, verse advance, preview navigation, select item | **None.** Single key, <150ms | Speed is safety here; every action is trivially reversible by advancing back (FR-024, NFR-004) |
| **T1 — Instant + reversible audience action** | Go Live, Clear (layer/all), Blackout, TIME UP dismiss | **None.** Executes immediately; protected by (a) dedicated distinct control, (b) loud persistent *active-state* indicator, (c) quick-undo | Emergency actions must never sit behind a dialog (invariant 2). Accident-resistance comes from feedback + undo, not friction |
| **T2 — Confirm (destructive authoring)** | Delete plan item / document / song / template, remove media, revoke device, discard unsaved recovery | **Inline confirm** (button morphs to “Confirm delete?” for 3s) or modal for multi-item | Irreversible or expensive to rebuild; not time-critical |
| **T3 — Arm-then-fire (audience-facing risk)** | Sending **TIME UP or any audible cue to an audience/house output**, enabling AI **auto-display**, pushing content to the **stream + room** at once | **Two-step:** explicit output selection **then** confirm; audience/house outputs **default-excluded** and shown with a warning | The mistake being prevented is "the congregation saw/heard the operator's private cue" or "a wrong verse auto-displayed" (FR-062/063/116) |

**Quick-undo (the T1 safety net).** Go Live, Clear, Blackout, and AI Display each leave the prior live state recoverable for a bounded window via a single **Undo live** affordance (`Cmd/Ctrl+Z` while presentation-focused; on-screen toast). AI *Display* undo is guaranteed for **≥5s** (FR-117). Undo of a live action re-pushes the prior program frame; it does **not** rewind authoring history (that is the separate editor undo, FR-016) — the two undo stacks are distinct and never cross (FR-016 note: "live triggering is not undone destructively").

### 1.3 Destructive & audience-facing rules (quick reference)

- **Blackout** is a toggle with a full-screen unmistakable active state; un-blackout restores exact prior content (FR-077). Never auto-engages.
- **Clear** removes chosen layer(s) only; other layers/outputs untouched; quick-undo restores (FR-076/078).
- **Any timer/alert to audience** requires T3 arm-then-fire; audience outputs are off by default (FR-062/063).
- **AI suggestions** never cross to Live without T0/T1 human action on the card (§12).
- **Delete** anything persistent → T2 confirm.
- **A failure is never a confirmation prompt that blocks live control** — errors are non-blocking banners (invariant 5).

### 1.4 Console shell (orientation)

```
┌ SelahCue ── Sunday · 2nd Service ─────────────────[ ● LIVE ]─[ Cloud OFF ]─[ ⌘K ]─┐
│  File   Edit   View   Live   Outputs   Timers   Tools   Help                       │
├──────────────┬──────────────────────────────────┬────────────────────────────────┤
│ SERVICE PLAN │  EDITOR  ·  PREVIEW (staged)      │  LIVE CONTROL                  │
│ (run sheet)  │                                    │ ┌─PREVIEW──────┬─LIVE────────┐ │
│              │                                    │ │  (green)      │  (red)      │ │
│ ▾ Worship    │   ┌───────────────────────────┐    │ │  [staged]     │  [program]  │ │
│   • Song A ◀ │   │                           │    │ └──────────────┴─────────────┘ │
│   • Song B   │   │    slide canvas / editor  │    │        [[  GO LIVE →  ]]        │
│ ▸ Announce   │   │                           │    │  CURRENT ▶ v.12  NEXT ▷ v.13   │
│ ▸ Sermon     │   └───────────────────────────┘    │  [ CLEAR ▾ ]   [ BLACKOUT ]    │
│ ▸ Response   │   Verses/slide · Template · …      │  Timer  24:31 ▓▓▓▓░  [TIME UP] │
├──────────────┴──────────────────────────────────┴────────────────────────────────┤
│ ● Main 1080p  ● Stage 1080p  ○ Stream(off) │ ⏱ Sermon 24:31 │ ⚠ 1 missing media   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

Three columns — **Plan** (what's next), **Editor/Preview** (what I'm staging), **Live Control** (what's on screen now) — are always visible during service; the emergency row (Clear/Blackout) and the status bar (output health) never scroll off. Panels are resizable and collapsible **except** the Live Control column and status bar, which are pinned (invariant 2).

---

## 2. Design foundations (tokens referenced by every component)

### 2.1 Semantic colour + state tokens (dark booth default; light/high-contrast variants required, NFR-020)

State is **never conveyed by colour alone** (WCAG 1.4.1) — every colour token is paired with a word and/or icon.

| Token | Meaning | Pairing (always present) | Contrast rule |
|---|---|---|---|
| `--live` red | On an audience output / program | “LIVE” label + red frame | ≥3:1 vs adjacent (UI, NFR-020) |
| `--preview` green | Staged, not live | “PREVIEW / STAGED” label + green frame | ≥3:1 |
| `--warn` amber | Timer threshold, caution | icon + text | ≥3:1 (large), ≥4.5:1 (body) |
| `--danger` red | Destructive confirm | “Confirm delete?” text | ≥4.5:1 text |
| `--ok` neutral-green | Connected / healthy | “Connected” text + ● | ≥3:1 |
| `--cloud` violet | Cloud provider transmitting | “CLOUD ACTIVE” + icon | ≥4.5:1 (FR-133) |
| surfaces | booth-dark base `#12141A`-class; text `#EDEFF4`-class | — | body text ≥4.5:1, all AA (NFR-020) |

### 2.2 Typography & sizing

- **Operator console:** body ≥14px, control labels ≥13px, min interactive hit area **≥32×32px** (desktop pointer) / focus target never smaller than the glyph.
- **Stage / confidence & audience text:** operator-configurable, **≥48px-equivalent** floor, high-contrast theme selectable (NFR-020, FR-037). Current-line/next-line and countdown are the largest glyphs on the stage output.
- **Mobile controller:** every interactive target **≥44×44pt** with ≥8pt spacing (NFR-026); primary live buttons span the full width.

### 2.3 Motion & seizure safety (FR-175, WCAG 2.3.1)

- Any flashing/animated output (TIME UP flash, threshold pulse, "cloud active" indicator, reconnecting spinner) is **bounded to ≤3 flashes per second**.
- A global **Reduced-motion** setting (mirrors OS preference) replaces flashes with **static** high-contrast state changes and disables non-essential transitions on audience/livestream outputs. Reduced-motion must not remove *information* — a flashing TIME UP becomes a solid inverted TIME UP.

### 2.4 Focus & keyboard baseline

- A **visible focus ring** (≥2px, ≥3:1 against both the focused element and its background) is mandatory and never suppressed (NFR-019).
- Logical tab order follows visual order: Plan → Editor → Live Control → status. `F6`/`Shift+F6` jumps between the three primary regions (panes are ARIA landmarks/regions).
- **Roving tabindex** inside lists/grids (plan, multiview, palette results): one tab stop for the group, arrow keys move within.
- Core live controls expose accessible name + role to platform screen readers in MVP (NFR-021).

---

## 3. Component — Service-plan list (drag-reorder)

**Purpose.** The run-of-show: the ordered spine of the service the Coordinator authors (WORKFLOWS A1) and the Operator drives (JTBD-1). Holds ≥50 mixed items, survives restart, reorders by drag (FR-001/002). It is the operator's map of "what's now / what's next."

**Wireframe.**
```
┌ SERVICE PLAN ─ Sunday 2nd Service ── v4 (published) ── [ + Add ▾ ] ─┐
│  Planned 68:00  ·  Elapsed 41:12                                    │
│ ────────────────────────────────────────────────────────────────── │
│ ▾ ▤ Worship set                              18:00   Worship Ld  ⋮  │
│ ⣿  ♪ Song — “Great Are You Lord”     LIVE ◀  05:00   —          ⋮  │  ← live row: red edge + “LIVE”
│ ⣿  ♪ Song — “Way Maker”              NEXT ▷  05:00   —          ⋮  │  ← next row: green edge + “NEXT”
│ ⣿  ✝ Scripture — Rom 8:28–30 (WEB)           02:00   Scr. Op    ⋮  │
│ ▾ ▤ Announcements                            04:00   Host       ⋮  │
│ ⣿  �national image — Missions.png     ⚠ missing 01:00   —          ⋮  │  ← ⚠ missing-media badge
│ ▸ ▤ Sermon                                   30:00   Pastor     ⋮  │
│ ────────────────────────────────────────────────────────────────── │
│  Drop indicator ▔▔▔▔  (during drag)                                 │
└────────────────────────────────────────────────────────────────────┘
   ⣿ = drag handle   ⋮ = row menu   ▤ = section header   ▾/▸ = expand/collapse
```

**Key states.**
- Item states: `idle`, `selected` (keyboard/pointer focus), `live` (currently on program — red left edge + "LIVE" word), `next` (green edge + "NEXT"), `staged` (this item is in Preview but not live), `missing-media` (⚠ badge, FR-007), `dragging`, `drop-target`.
- List states: `empty` (first-run guidance), `loading`, `published` vs `draft` (change badge when edited after publish, WORKFLOWS A1), `has-unresolved-media` (header ⚠ count).
- Plan states: `draft → validated → published` (FR-006, WORKFLOWS A1).

**Interaction — mouse.**
- Click a row = select + stage it into Preview (does **not** go live — invariant 1). Double-click a content item = open in editor.
- Drag the ⣿ handle (or long-press the row body) to reorder; a horizontal drop-indicator shows the insertion point; sections accept nested items; dropping onto a collapsed section inserts at its end. Reorder persists immediately + autosaves (FR-001/074).
- `⋮` row menu: Stage to preview · Go live · Duplicate · Edit · Set timing/owner · Remove (T2 confirm) · Move to section.
- `+ Add ▾`: slide group · song · scripture · media · announcement · timer · section header (FR-002).

**Interaction — keyboard.** (list is a `listbox`/`tree` with roving tabindex)
- `↑/↓` move selection; `←/→` collapse/expand sections; `Home/End` first/last.
- `Enter` = stage selected into Preview; `Cmd/Ctrl+Enter` = **Go Live** with selected (still a deliberate live action).
- `Alt+↑ / Alt+↓` = **reorder** the selected item (keyboard drag equivalent — mandatory, drag must not be mouse-only, NFR-019); moves persist + announce "moved to position N of M".
- `Cmd/Ctrl+D` duplicate · `Delete` remove (→ T2 inline confirm) · `F2` rename · `Cmd/Ctrl+↑/↓` jump between sections.
- Typeahead: typing letters jumps to the next matching item title.

**Inputs / outputs.**
- In: plan model (ordered `plan_item`s, ARCHITECTURE §8), media-resolution status, live/next pointers from the presentation service, published/version metadata.
- Out: `reorder(itemId, toIndex)`, `stage(itemId)`, `goLive(itemId)`, `edit(itemId)`, CRUD events, `select(itemId)`. All mutations autosave (FR-074) and reorder/live events append to the audit log where they change output (FR-150).

**Error & edge handling.**
- **Missing media** (FR-007/070, WORKFLOWS F6): ⚠ badge on the row + count in header; the row is still selectable and triggerable — triggering a missing item shows a **safe placeholder, never a black screen**, and offers "Relink / Skip / Substitute" inline. Never blocks the list.
- **Edited-after-publish:** a "changed since publish" badge on affected rows; operator's live view shows the badge but is never force-refreshed mid-service.
- **Drag cancelled** (`Esc` mid-drag, or drop outside): snaps back, no mutation.
- **Empty plan:** friendly first-run panel with "Add first item / Start from template / Duplicate last service" (WORKFLOWS B1).
- **Long lists (≥50):** virtualised; the live and next rows are **always kept in view** (auto-scroll on live-pointer change) so the operator never loses "what's now".

**Accessibility.**
- Role `tree` (sections) / `listbox` (flat); each row `treeitem`/`option` with accessible name = "{type} — {title}, {duration}, {owner}{, LIVE|NEXT|missing media}". Live/next/missing conveyed in the name **and** by icon+word, not colour alone.
- Reorder operable by keyboard (`Alt+↑/↓`) with live-region announcements of new position; drag has an accessible alternative (invariant: no mouse-only path, NFR-019).
- Focus ring ≥3:1; row hit area ≥32px tall; `⋮`/handle targets ≥24×24 with ≥32px focus target.
- `aria-live="polite"` region announces live/next pointer changes and missing-media flags.

---

## 4. Component — Content / slide editor

**Purpose.** Author slides, song sections, announcements, sermon points, and scripture templates with layered text/box/image elements; what renders in the editor renders identically on preview and live (FR-009/010/011/017/019). Serves the Coordinator (authoring) and the Operator (last-minute fixes).

**Wireframe.**
```
┌ EDITOR — Song “Way Maker” · Chorus 1 ─────────────── [ Undo ↶ ][ Redo ↷ ] ┐
│ SECTIONS      │  CANVAS (16:9, safe-area guides)          │  INSPECTOR      │
│ • Verse 1     │  ┌──────────────────────────────────┐     │  Layer: Text    │
│ • Chorus 1 ◀  │  │  ·············· safe ············ │     │  Font  [ Inter ]│
│ • Verse 2     │  │   Way maker, miracle worker      │     │  Size  [  64  ] │
│ • Bridge      │  │   Promise keeper, light in the   │     │  Align [≡][≣][≡]│
│ [+ section]   │  │   darkness                       │     │  Color �e AAF   │
│               │  │  ·······························  │     │  ── Layers ──   │
│ Verses/slide  │  └──────────────────────────────────┘     │  ▤ Text     ●   │
│   [ 2 ]  ▾    │  ◀ slide 1 / 2 ▶       Theme [ Default ▾ ] │  ▤ Background ● │
│               │                                            │  ▤ Logo      ○ │
└───────────────┴────────────────────────────────────────────┴─────────────────┘
```

**Key states.**
- Editor: `empty/new`, `editing`, `dirty` (unsaved — autosaved continuously, FR-074), `saved`, `applying-template`.
- Element/layer: `selected`, `editing-text` (caret active — **captures single-key live shortcuts**, see §11), `locked`, `hidden` (visibility toggle per layer).
- Content-type variants: slide group, song section (verse/chorus/bridge/tag, FR-019), announcement, sermon point, scripture template (FR-011/029).

**Interaction — mouse.**
- Click element to select; drag to move; handles to resize; double-click text to edit inline. Layer list toggles visibility (●/○) and lock; reorder layers by drag (FR-009). Template dropdown restyles the whole group **without losing content** (FR-010).
- Verses/slide control repaginates scripture/lyrics live in the canvas (FR-029).

**Interaction — keyboard.**
- Standard text editing when a text layer's caret is active. `Esc` exits text editing (returns single-key live shortcuts to global scope).
- `Tab/Shift+Tab` cycle elements; arrow keys nudge selected element (Shift = ×10); `Cmd/Ctrl+]`/`[` reorder layer; `Cmd/Ctrl+;` toggle layer visibility.
- **Undo/redo** `Cmd/Ctrl+Z` / `Cmd/Ctrl+Shift+Z`, ≥20 steps (FR-016) — editor stack only, never touches live (§1.2).
- `Cmd/Ctrl+S` explicit save-point (autosave is continuous regardless).

**Inputs / outputs.**
- In: `document`/`song`+`section`/`scripture_set` model, `template`/`theme`, font-fallback set (must shape Latin+diacritics incl. Yoruba/Hausa/Igbo/French/Spanish, FR-017).
- Out: content mutations (autosaved, FR-074), `stageToPreview()` (never live from editor directly), template application, pagination settings.

**Error & edge handling.**
- **Missing font glyph:** font-fallback covers the character set; if a glyph still can't shape, show a visible in-canvas warning at the glyph, never silent tofu (FR-017).
- **Missing image layer:** placeholder tile in canvas, flagged (mirrors FR-070).
- **Template application that would clip content:** warn + show overflow indicator, do not silently truncate; content is preserved (FR-010).
- **Editing an item that is currently live:** edits stay in the editor/preview; a persistent "This item is LIVE — changes apply to Preview, press Go Live to push" banner (invariant 1). Never live-mutates on keystroke.

**Accessibility.**
- Canvas is an editable region with a labelled toolbar (`toolbar` role) and inspector (`group`s with field labels). Every control has a text label; colour pickers expose hex value as text.
- Full keyboard authoring (element select/move/resize/reorder via keys) — no mouse-only editing path.
- Contrast: editor chrome AA (NFR-020); safe-area and selection guides ≥3:1. A **live preview of on-output contrast** warns when authored text/background falls below AA for the *audience* (helps the operator not ship an illegible slide).
- Reduced-motion respected in canvas transition previews (FR-175).

---

## 5. Component — Preview↔Live control (Go Live · Clear · Blackout)

**Purpose.** The single legal crossing from staged to audience-facing, plus the two emergency exits. This is the most safety-critical component: it embodies invariants 1 and 2. Serves every operating persona; it is the heart of JTBD-1/6.

**Wireframe.**
```
┌ LIVE CONTROL ───────────────────────────────────────────────────┐
│ ┌ PREVIEW (staged) ──────────┐   ┌ LIVE (program) ─────────────┐ │
│ │  green frame · “PREVIEW”    │   │  red frame · “● LIVE”        │ │
│ │  ┌───────────────────────┐  │   │  ┌───────────────────────┐   │ │
│ │  │  Rom 8:28 (WEB)        │  │   │  │  Rom 8:28 (WEB) v.1/3  │   │ │
│ │  └───────────────────────┘  │   │  └───────────────────────┘   │ │
│ └────────────────────────────┘   └─────────────────────────────┘ │
│                 [[  GO LIVE  → ]]   (Enter — not Space)            │
│  ── emergency (always active) ──────────────────────────────────  │
│  [ CLEAR ▾ ]  layer: Text|BG|Lower-3rd|Media|ALL    [  BLACKOUT ] │
│                                          ↑ toggle · full-screen ● │
│  Undo live ↶ (5s)                        Outputs: ●Main ●Stage    │
└───────────────────────────────────────────────────────────────────┘
```

**Key states.**
- **Go Live:** `preview-differs-from-live` (button armed/enabled), `preview==live` (button quiet/disabled — nothing to push), `transitioning` (<150ms).
- **Clear:** menu of layers (Text · Background · Lower-third · Media · **All**) each with a cleared/present state; `clear-all` distinct from per-layer (FR-076/078).
- **Blackout:** `off` ↔ `on` **toggle**; when on, the whole Live pane and a global top-bar chip show an unmistakable "BLACKOUT — audience blank" state (FR-077).
- Cross-cutting: **Undo-live available** (post Go Live / Clear / Blackout, ~5s window).

**Interaction — mouse.**
- **Go Live** button (T1): click pushes Preview → Live instantly (<150ms), animates the frame from green→red, updates Current/Next. No confirm.
- **Clear** split-button (T1): main click = clear the last-cleared/most-relevant layer or ALL per setting; caret opens the per-layer menu. Clearing removes only chosen layer(s); other layers and other outputs untouched (FR-078).
- **Blackout** (T1): click toggles; a second click un-blacks and restores exact prior content (FR-077). Distinct heavy styling, isolated from Go Live to prevent mis-click.
- **Undo live**: click within window restores prior program frame.

**Interaction — keyboard.** (see §11 for the full scheme + focus rules)
- **Go Live:** `Enter` (presentation focus) — the operator's dominant action, a **distinct key from Next (`Space`)** per UX-CANONICAL §1 (never overloaded with Next).
- **Clear layer:** `C`; **Clear all:** `Shift+C`; **Blackout:** `B` (presentation focus). **Always-global fallbacks** that fire even while typing: `Cmd/Ctrl+.` (clear all), `Cmd/Ctrl+B` (blackout) — guaranteeing invariant 2 regardless of focus.
- **Undo live:** `Cmd/Ctrl+Z` (presentation focus).

**Inputs / outputs.**
- In: current Preview scene, current Live scene, per-output layer composition, blackout state.
- Out: `goLive(scene)`, `clear(layer|all, outputScope)`, `blackout(on|off)`, `undoLive()`. All are local, network-independent (CON-2), execute in <200ms, and append to the audit log (FR-150). Blackout/clear default to audience+all-live outputs unless a scope is chosen.

**Error & edge handling.**
- **Nothing staged / Preview==Live:** Go Live is disabled with a quiet "Preview matches Live" label (not an error).
- **Output disconnected at Go Live** (WORKFLOWS F1): push succeeds to remaining outputs; the lost output is flagged in status; on reconnect the exact frame auto-restores (FR-041). Go Live never blocks on a dead output.
- **Blackout during a failure:** blackout is a deliberate operator state; a *failure* must never engage it (invariant 5). If the app crashes while blacked out, recovery restores the blackout state truthfully (FR-075).
- **Rapid repeated Go Live:** debounced to the latest scene; each push is idempotent to current Preview.

**Accessibility.**
- Go Live: `button`, name "Go live — push preview to program". Clear: `button` with `aria-haspopup=menu`, name "Clear layer"; menu items named per layer. Blackout: `button` `aria-pressed` reflecting on/off, name "Blackout audience output, currently {on|off}".
- These are **core live controls with mandatory screen-reader names/roles in MVP** (NFR-021). State changes announced via `aria-live="assertive"` ("Live: Romans 8:28", "Blackout on", "Cleared text layer").
- Frames use colour **and** the words PREVIEW/LIVE/BLACKOUT (never colour alone). Blackout on/off has a text + icon state, ≥4.5:1.
- Targets: emergency buttons are oversized (≥44×44 even on desktop) and spatially separated so Blackout is not adjacent to Go Live. Focus never trapped; these controls are reachable from any pane via their global shortcuts.

---

## 6. Component — Current / Next views

**Purpose.** The operator's glanceable "what's on screen now / what fires next," reflecting **live** state within ≤100ms (FR-013), and the model the stage/confidence display mirrors for the pastor/worship leader (FR-037, JTBD confidence). Answers "am I where I think I am?" without reading the whole plan.

**Wireframe.**
```
┌ CURRENT ▶ (LIVE) ──────────────┐   ┌ NEXT ▷ (staged/plan) ─────────┐
│  Song · “Way Maker”            │   │  Song · “Way Maker”            │
│  Chorus 1 · slide 1/2          │   │  Chorus 1 · slide 2/2          │
│  ┌──────────────────────────┐  │   │  ┌──────────────────────────┐  │
│  │ Way maker, miracle worker│  │   │  │ Promise keeper, light in │  │
│  │ Promise keeper …         │  │   │  │ the darkness …           │  │
│  └──────────────────────────┘  │   │  └──────────────────────────┘  │
│  red edge · “LIVE”             │   │  advance ▶ = this becomes live │
└────────────────────────────────┘   └────────────────────────────────┘

STAGE/CONFIDENCE OUTPUT (mirror, ≥48px):
┌───────────────────────────────────────────────────────────┐
│  10:42 AM        ⏱ SERMON  24:31        [ wrap up ]         │
│  NOW:  Way maker, miracle worker                            │
│  NEXT: Promise keeper, light in the darkness                │
└───────────────────────────────────────────────────────────┘
```

**Key states.** `current` reflects program (source of truth = live scene); `next` reflects the next advance target (next slide/verse/plan item). States: `slide content`, `blackout` (Current shows "BLACKOUT — audience blank" so the operator always knows), `cleared layer`, `end-of-item` (Next shows the next plan item), `no-next` (end of plan).

**Interaction — mouse.** Current is **display-only** (it is the truth, not a control) — clicking it does nothing destructive; it may offer a "reveal in plan" affordance. Next is clickable to advance (equivalent to Next). Thumbnails scale with panel size.

**Interaction — keyboard.** These views are read-outs; advancing is done via the global Next/Prev keys (§11). `Cmd/Ctrl+L` focuses/reads the Current view for screen-reader users.

**Inputs / outputs.**
- In: live scene + next-advance target from the presentation service, blackout/clear state, timer + stage-message state (for the confidence mirror).
- Out: `advance()` (from Next click) — otherwise read-only.

**Error & edge handling.**
- **Current must always show the truth**, including uncomfortable truths: if audience is blacked out or a layer cleared, Current says so explicitly — it must never show stale "what I think is up" content (this is how operators catch a mistake). Reflects within ≤100ms (FR-013).
- **Stage display disconnected** (WORKFLOWS F1): operator Current/Next in the console are unaffected; the lost stage output is flagged; content auto-restores on reconnect (FR-041).
- **No next:** Next shows "End of plan" rather than blank.

**Accessibility.**
- Current: `region` name "Current live output"; Next: `region` "Next". Text content exposed to screen readers (not image-only) so an operator using AT can hear "Live: Way maker, chorus 1 slide 1 of 2."
- Stage/confidence text ≥48px-equivalent, high-contrast theme, configurable size (NFR-020, FR-037) for readability under stage lighting.
- `aria-live="polite"` announces Current changes; blackout/clear announced. Contrast AA; "LIVE" word + red edge (not colour alone).

---

## 7. Component — Scripture search + stager

**Purpose.** Put the right verse, right translation, on screen fast — reactively, keeping up with an improvising preacher (JTBD-2, Scripture Operator, WORKFLOWS A2). Reference + keyword search over bundled PD translations, offline, with a mandatory preview-before-live gate (FR-025–031/035).

**Wireframe.**
```
┌ SCRIPTURE ───────────────────────────────────────────────────────┐
│ [ Rom 8:28-30                         ]  Trans [ WEB ▾ ]  [Search] │
│  parsed → Romans 8:28–30 · WEB · 3 verses · 2 slides ✓            │
│ ── results (keyword mode) ──────────────────────────────────────  │
│  ▸ Rom 8:28  “And we know that all things work together…”         │
│  ▸ Rom 8:29  “For whom he foreknew…”                              │
│ ── stager (preview) ────────────────────────────────────────────  │
│  Slide 1/2:  v.28 “And we know that all things work together for  │
│              good to those who love God…”         [ Verses/slide 2▾]│
│  History: Jn 3:16 · Ps 23 · 1 Cor 13:4    ★ Favourites            │
│                          [ Stage → Preview ]   [[ Display Live ]]  │
└───────────────────────────────────────────────────────────────────┘
```

**Key states.**
- Search: `idle`, `parsing` (typed reference → live parse feedback), `parsed-valid` (✓ + resolved range), `parse-error` (invalid reference guidance, FR-026), `keyword-searching`, `results`, `no-results`.
- Stager: `empty`, `staged(preview)` (paginated verse slides), `live` (advancing verse-by-verse), `cleared` (WORKFLOWS A2 `searched → staged → live → cleared`).

**Interaction — mouse.**
- Type a reference (`Rom 8:28-30`, `Ps 23`, `Jn 3:16; 1 Cor 13:4`) — parsed live with a human-readable echo of what will show (FR-027). Or switch to keyword and search (<500ms, FR-028). Pick translation from switcher (FR-035).
- Select a result / range → it stages into **Preview**, auto-paginated by verses/slide (FR-029). Adjust verses/slide, translation, or range in the stager — all still in Preview.
- **Stage → Preview** (safe default) vs **Display Live** (one-step to program for the fast case) — both are explicit human actions honouring the preview gate (FR-012, WORKFLOWS A2). History + favourites re-present in ≤2 actions (FR-031).

**Interaction — keyboard.**
- `/` or `Cmd/Ctrl+G` focuses the reference field from anywhere.
- Type reference; `Enter` = stage to Preview; `Cmd/Ctrl+Enter` = Display Live. `Tab` moves to translation switcher; `↑/↓` through results; `Alt+←/→` cycle translation.
- While live: global Next/Prev advance verse-by-verse; `C` clears scripture layer.
- `Cmd/Ctrl+H` history, `Cmd/Ctrl+B`… (reserved for blackout — history uses a different chord to avoid collision; history = `Cmd/Ctrl+Y`).

**Inputs / outputs.**
- In: bundled PD translations (WEB/ASV/BSB/BBE/Darby/Webster — **KJV excluded**, FR-025), reference parser, keyword index, history/favourites, per-output scripture template.
- Out: `stage(passage, translation, template)`, `displayLive(...)`, `paginate(versesPerSlide)`, `addFavourite()`. Display-live appends to audit log (FR-150). All operate offline (NFR-015).

**Error & edge handling.**
- **Invalid reference:** rejected inline with guidance ("No chapter 51 in Psalms — did you mean…?"), never a silent empty stage (FR-026).
- **Awkward multi-verse ranges** (a Scripture Operator pain point): pagination preview shows exactly how the range splits across slides before Display; operator can re-split.
- **Wrong-translation risk:** the staged slide and Current view always show the translation name; switching translation re-stages (never silently swaps a live verse without the operator seeing it).
- **Keeping up with a fast preacher:** Display Live is one keystroke from a parsed reference; history makes re-showing instant. Detection (R4, §12) later assists but never auto-displays.
- **Attribution:** each translation renders required attribution/PD mark (FR-035).

**Accessibility.**
- Reference field: `textbox` name "Scripture reference or keyword"; parse feedback in an `aria-live` region ("Parsed: Romans 8 verse 28 to 30, World English Bible, 2 slides"). Results `listbox`.
- Stage/Display buttons: distinct accessible names ("Stage to preview" vs "Display live"). Display-live announced assertively.
- Full keyboard path from search → stage → live → clear (no mouse-only). Contrast AA; results legible; verse text preview honours the audience-contrast warning (§4).

---

## 8. Component — Timer + TIME UP control

**Purpose.** Run the room to time and deliver a discreet, unmistakable TIME UP to the stage — without ever touching the audience output by accident (JTBD-3, Stage Manager, WORKFLOWS A3, FR-054–065). Monotonic-clock accurate (±100ms/hr, NFR-022).

**Wireframe.**
```
┌ TIMERS ──────────────────────────────────────────────────────────┐
│  ● Sermon  24:31 ▓▓▓▓▓▓▓░░  ↓  amber@2:00 red@0:30                │
│     [▮▮ Pause][↻ Reset][ −1:00 ][ +1:00 ]   show on: [Stage ✓][Op]│
│  ○ Pre-service  00:00 (armed)                                     │
│  ── TIME UP ─────────────────────────────────────────────────────│
│  State: “TIME UP” · red · flash≤3/s · targets: [Stage ✓][Op ✓]   │
│         [Audience ☐ ⚠ arm to enable]                              │
│  At 0 → shows on targets only.  Overrun: −01:12 (over)            │
│  [ Extend +2:00 ]  [ Dismiss TIME UP ]  [ Send “wrap up” ▸ ]      │
│  + New timer ▾  (countdown · count-up · time-of-day · elapsed · seg)│
└───────────────────────────────────────────────────────────────────┘
```

**Key states.** (WORKFLOWS A3: `armed → running → warning → TIME UP → cleared/extended`)
- Timer: `armed`, `running`, `paused`, `warning` (crossed amber/red threshold — appearance changes, FR-057), `expired/TIME UP`, `overrun` (negative, "over", FR-060), `dismissed`, `reset`.
- Visibility scope per timer: `operator-only` vs `stage-visible` vs (armed) `audience` (FR-058/062).
- Multiple simultaneous timers, each independently shown/hidden per output (FR-056).

**Interaction — mouse.**
- Create timer (type picker), set duration, thresholds, presets (FR-054/057). Controls: Start/Pause/Resume/Reset/±time each take effect <200ms on all outputs showing it (FR-055).
- **Per-output visibility** checkboxes; **audience** target is a **T3 arm-then-fire**: unchecked by default, shows ⚠, requires explicit arm to ever appear on the congregation screen (FR-062).
- TIME UP config: text/colour/background/flash-or-static, per-output (FR-059); flash bounded ≤3/s and reduced-motion → static (FR-175). At 0 it renders on selected targets only.
- Dismiss (manual), Extend (+time, resumes), Reset (FR-061). Send stage message ("wrap up") to stage/confidence (FR-162, distinct from TIME UP).

**Interaction — keyboard.**
- `T` focuses timers. Selected timer: `Space` start/pause, `R` reset, `+`/`-` add/subtract a step. `Shift+T` triggers/dismisses TIME UP for the selected timer.
- Sending TIME UP/alert to **audience** cannot be done by a single accidental key — it requires the arm-then-confirm interaction (T3).

**Inputs / outputs.**
- In: monotonic clock (authoritative, not refresh-driven, FR-065/NFR-022), timer models, per-output visibility, TIME UP config.
- Out: `start/pause/resume/reset/adjust(timerId)`, `armAudience(timerId)`, `fireTimeUp/dismiss/extend`, `sendStageMessage(text)`. Expiry is logged (FR-064 R6 audit; MVP surfaces it). Mobile Timer Operator issues the same as role-scoped requests (FR-094).

**Error & edge handling.**
- **Accidental audience display** (the core safety case): impossible without T3 arm; audience target defaults off and is visually warned (FR-062). Audible TIME UP cue to an output is R2 and also arm+confirm, audience-excluded (FR-063).
- **Crash mid-countdown** (WORKFLOWS F5): countdowns re-anchor to wall-clock on resume, count-ups resume accumulated (FR-075) — the timer of record is the desktop (WORKFLOWS A3).
- **Overrun:** past 0 continues negative with "over" so the speaker sees how far past (FR-060); TIME UP persists until dismissed/extended.
- **Reduced-motion / seizure safety:** flashing TIME UP degrades to a solid inverted state, ≤3/s enforced (FR-175).

**Accessibility.**
- Each timer: `group` named "{name} timer, {remaining}, {running|paused|over}"; controls are labelled `button`s. Time value in an `aria-live` region at threshold crossings and at 0 ("Sermon timer: time up" / "one minute over").
- TIME UP audience arm is a clearly labelled two-step control with `aria-pressed`/confirm; screen reader announces the armed/fired state.
- Timer/TIME UP display text ≥48px-equiv on stage, high-contrast (NFR-020). Contrast of threshold colours paired with text ("2:00 — caution") not colour alone. Operator alert respects an accessible non-audio-only cue.

---

## 9. Component — Output multiview

**Purpose.** See every output plus Preview/Next at a glance — catch "a room layer bled onto the stream" or "the stream output died" before the audience does (Livestream Director, FR-045/042, R2). MVP shows Main + Stage; R2 adds 3+ independent outputs and health.

**Wireframe.**
```
┌ MULTIVIEW ───────────────────────────────────────────────────────┐
│ ┌ MAIN 1080p ●──────────┐ ┌ STAGE 1080p ●────────┐ ┌ STREAM ○ ──┐ │
│ │ Way maker, miracle…    │ │ NOW: Way maker        │ │  (off)      │ │
│ │  [LIVE]                │ │ NEXT: Promise keeper  │ │  no signal  │ │
│ │  ● 60fps  0% drop      │ │ ⏱24:31                │ │             │ │
│ └────────────────────────┘ └───────────────────────┘ └────────────┘ │
│ ┌ PREVIEW (staged) ──────┐ ┌ NEXT ▷ ───────────────┐               │
│ │ Rom 8:28 (WEB)         │ │ Chorus 1 · slide 2/2  │  [Identify]    │
│ │  [PREVIEW]             │ │                        │  [Test pattern]│
│ └────────────────────────┘ └───────────────────────┘               │
└───────────────────────────────────────────────────────────────────┘
```

**Key states.** Per tile: `live-healthy`, `preview`, `disconnected` (⚠ named, WORKFLOWS F1), `no-signal/off`, `degraded` (dropped frames >5% over 10s, FR-042), `test-pattern`, `identifying` (number overlay, FR-040). Global: MVP (2 tiles) vs R2 (3+ tiles).

**Interaction — mouse.** Click a tile to select that output for scoped actions (e.g. clear this output, assign display). **Identify** flashes a number on each physical display for assignment (FR-040). **Test pattern** to any output for calibration (FR-043, R2). Tiles are read-outs of truth; no tile click blanks an audience output without going through Clear/Blackout.

**Interaction — keyboard.** Multiview is a grid with roving tabindex; `↑↓←→` move between tiles; `Enter` selects an output for scoped ops; `I` triggers Identify.

**Inputs / outputs.** In: per-output rendered thumbnails (downscaled texture stream, ARCHITECTURE risk S5), health telemetry (connected/resolution/frame-drop, FR-042 R2). Out: `selectOutput()`, `identify()`, `sendTestPattern()`, scoped clear.

**Error & edge handling.** A disconnected output tile shows ⚠ + name + "content held, will restore on reconnect" — **other tiles are unaffected** (invariant 5, FR-041). Degraded (dropped-frame) tile flags without implying the audience output failed. Multiview itself failing must never affect what's on the outputs (it is a monitor, not the render path).

**Accessibility.** Each tile `group` named "{output name}, {resolution}, {LIVE|preview|disconnected|degraded}, {fps/drop}"; status in text + icon (not colour alone). Grid keyboard-navigable. Thumbnails carry text alternatives of their content. Contrast AA; health colours paired with words.

---

## 10. Component — Command palette

**Purpose.** One keystroke to any action or plan item by fuzzy search — the volunteer's escape hatch and the pro's accelerator (FR-015). Reduces "where is that button" to typing.

**Wireframe.**
```
        ┌ ⌘K ─────────────────────────────────────────────┐
        │ 🔎 black|                                        │
        │ ────────────────────────────────────────────────│
        │  ⚡ Blackout audience output            B         │  ← action + shortcut
        │  ⚡ Clear all layers                    ⇧C        │
        │  ♪  Song — “Black Fast” (plan item)               │
        │  ✝  Scripture — display Rom 8:28                  │
        │  ⏱ Start Sermon timer                            │
        │ ────────────────────────────────────────────────│
        │  ↑↓ navigate · ↵ run · esc close                 │
        └──────────────────────────────────────────────────┘
```

**Key states.** `closed`, `open-empty` (recent/suggested actions), `filtering`, `results`, `no-match`, `confirm-inline` (a destructive result asks to confirm in-palette — T2). Results interleave **actions** and **plan items** (FR-015), ranked by fuzzy score + recency.

**Interaction — mouse/keyboard.** `Cmd/Ctrl+K` opens (from anywhere, even mid-edit); type to fuzzy-filter; `↑/↓` select; `Enter` run; `Esc` close. Mouse click on a result runs it. Destructive results surface with a warning icon and require a second `Enter`/confirm (T2); **audience-facing results still obey their tier** — e.g. "TIME UP to audience" from the palette still routes through the arm step (T3), never fires blind.

**Inputs / outputs.** In: action registry (with current enablement + bound shortcut), plan-item index, recent-command history. Out: dispatch the chosen `action` / `stage(item)`. Live-affecting dispatches obey confirmation tiers and audit logging (FR-150).

**Error & edge handling.** No match → "No actions or items match" + a hint. Disabled actions appear greyed with the reason ("Go live — nothing staged"). The palette must **not** become a way to bypass safety: emergency/audience actions keep their tier behaviour; the palette is a locator, not an override. Opening the palette never steals focus from a running live action already in flight.

**Accessibility.** Combobox pattern: input `combobox` `aria-expanded`, results `listbox` with `aria-activedescendant`; the bound shortcut is part of each result's accessible name. Announced result count. Full keyboard by definition. Contrast AA; the highlighted match is indicated by more than colour (weight/underline). Reduced-motion: no open/close animation beyond a fade.

---

## 11. Component — Keyboard-shortcut scheme

**Purpose.** Make the whole live path keyboard-drivable (NFR-019, FR-014) with bindings that are fast, memorable, remappable, and — critically — that **never trap the operator** (single-key live actions when appropriate; always-global emergency fallbacks that survive text entry).

### 11.1 Focus rule (the linchpin)

Single-key shortcuts (`Space`, `B`, `C`, `→`…) are **live only when no text field has the caret** ("presentation focus"). When a text editor/field is focused, those keys type literally; `Esc` returns presentation focus. A **persistent focus indicator** in the top bar shows which mode is active ("⌨ Presentation" vs "✎ Editing"), so the operator always knows whether `Space` advances a slide or types a space.

**Emergency actions are exempt** — Blackout and Clear-all have **always-global modifier bindings** (`Cmd/Ctrl+B`, `Cmd/Ctrl+.`) that fire *even while typing*, so invariant 2 holds from any focus.

### 11.2 Default bindings (all remappable, FR-014)

| Action | Presentation-focus key | Always-global | Tier | Trace |
|---|---|---|---|---|
| Next slide/verse | `→` `Space` `PageDn` | — | T0 | FR-014/024 |
| Previous | `←` `PageUp` | — | T0 | FR-014 |
| Go Live (push preview) | `Enter` | `Cmd/Ctrl+Return` | T1 | FR-012 |
| Clear layer | `C` | — | T1 | FR-076/078 |
| **Clear all** | `Shift+C` | `Cmd/Ctrl+.` | T1 | FR-076 |
| **Blackout toggle** | `B` | `Cmd/Ctrl+B` | T1 | FR-077 |
| Undo live | `Cmd/Ctrl+Z` | `Cmd/Ctrl+Z` | T1 | FR-117/§1.2 |
| Editor undo/redo | `Cmd/Ctrl+Z` / `⇧` | — (editor focus) | — | FR-016 |
| Command palette | `Cmd/Ctrl+K` | `Cmd/Ctrl+K` | — | FR-015 |
| Scripture search | `/` | `Cmd/Ctrl+G` | — | FR-027 |
| Focus Plan / Editor / Live | `F6` / `Shift+F6` | same | — | NFR-019 |
| Timer start/pause (selected) | `Space`* | — | T0/T1 | FR-055 |
| TIME UP fire/dismiss | `Shift+T` | — | T2/T3 | FR-059/061 |
| Repeat/jump lyric section | `1`–`9` (section) | — | T0 | FR-024 |

\* Timer `Space` applies only when a timer is selected and presentation focus is on the timer group — otherwise `Space` = Next. Conflicts like this are resolved by **focused-region scoping**, surfaced in the shortcut editor.

### 11.3 Remap UX & conflicts

- A **Shortcuts** settings screen lists every action, its binding, scope (global/region), and tier; rebind by focusing a row and pressing the new combo. Conflicts are detected and shown inline ("`B` already bound to Blackout in Presentation scope"). Emergency actions may be rebound but **cannot be unbound to nothing** (a guard preserves invariant 2 — clearing them prompts "Blackout must have at least one binding").
- Bindings persist per user/profile and export/import with settings.
- A printable/`?`-overlay cheat-sheet shows the current scheme.

**Accessibility.** The shortcut editor is fully keyboard-operable and screen-reader labelled; each binding's accessible name includes action + keys + scope. The `?` overlay is a reachable dialog. No action is mouse-only anywhere in the product (NFR-019). Focus-mode indicator is text ("Presentation"/"Editing"), not colour alone.

---

## 12. Component — Mobile control surface (role-scoped)

**Purpose.** Assist from the floor/stage within a scoped role, over the LAN, with unmistakable connection status and no accidental live changes (JTBD-4, Mobile Remote User, FR-092/093/097; PERSONAS §2). The desktop is always the authority — mobile **requests**, desktop executes (CON-1, WORKFLOWS A4/F3).

**Wireframe (Presenter role, connected).**
```
┌ SelahCue Remote ─────────────── ● Connected · Presenter ─┐
│  NOW (live)                                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Way maker, miracle worker                          │ │
│  │  Chorus 1 · slide 1/2            [LIVE]             │ │
│  └────────────────────────────────────────────────────┘ │
│  NEXT ▷  Promise keeper, light in the darkness           │
│                                                          │
│  ┌───────────────┐        ┌───────────────┐              │
│  │  ◀  PREV      │        │   NEXT  ▶     │  ≥44×44pt    │
│  └───────────────┘        └───────────────┘              │
│  ┌───────────────┐        ┌───────────────┐              │
│  │  CLEAR (own)  │        │   BLACKOUT    │  (role-scoped)│
│  └───────────────┘        └───────────────┘              │
│  ── plan ──  ▸ Worship  ▸ Sermon  …                      │
└──────────────────────────────────────────────────────────┘
```

**Role-scoped variants** (buttons present only if the granted role permits — PERSONAS §2 matrix; capability requests validated server-side, FR-090):
- **Observer:** previews + live transcript view only; **no** live-triggering controls rendered at all (not just disabled) — so a guest never sees a button they can't use (persona pain point).
- **Presenter:** Prev/Next, Clear (own layers ⚠), Blackout ✅.
- **Worship Leader:** lyric Prev/Next + repeat/jump section, Send stage message; **no** scripture/broadcast controls.
- **Scripture Operator:** scripture search/display + **approve detected suggestions** (the human gate, §12/R4, FR-095).
- **Timer Operator:** timer start/stop/adjust + TIME UP; **no** content controls.
- **Production Operator:** near-full (lower thirds, macros, output health) minus admin.
- **Administrator:** all + pairing management + full transcript.

**Key states.**
- Connection (always visible, top): `Unpaired`, `Pairing-pending`, `● Connected`, `◐ Reconnecting…`, `✕ Disconnected`, `⛔ Revoked` (WORKFLOWS A4/F3).
- Controls: `enabled`, `disabled-while-offline` (greyed with reason), `not-permitted` (absent).

**Interaction — touch.**
- Pair via QR scan / PIN with host-side approval (FR-086, WORKFLOWS A4). Large full-width primary buttons (Prev/Next). Emergency Blackout (if permitted) is large and colour+word labelled. Send stage message = short compose sheet.
- **On disconnect, controls disable immediately** and show "Reconnecting… your taps won't be sent" — preventing the "did my tap land?" pain point; on reconnect, live state re-syncs before controls re-enable and **queued stale taps are discarded, not replayed** (FR-097, WORKFLOWS F3, no ghost actions).

**Inputs / outputs.**
- In: role grant, live current/next preview + transcript (role-permitting), connection state.
- Out: role-scoped **requests** over TLS 1.3 (advance/clear/blackout/timer/scripture-approve/stage-message), each carrying nonce+timestamp (replay-protected, FR-091). Desktop validates against granted role at execution and echoes new state (WORKFLOWS A4.6). Client-asserted role is never trusted (FR-090).

**Error & edge handling.**
- **Silent drop** (the #1 mobile pain point): connection status is a persistent, high-contrast chip; loss is announced visually + haptic, controls disabled — never a live change fired into the void (FR-097).
- **Role downgrade / unpair mid-session:** takes effect immediately; disallowed controls disappear/disable at once (PERSONAS §2.2).
- **Losing all mobiles never disables any desktop capability** (FR-098) — the mobile UI states this ("Desktop keeps full control") so a nervous volunteer isn't afraid to disconnect.
- **Accidental tap protection:** destructive/audience actions (Blackout) get a brief press-and-hold or confirm on mobile (touch is slip-prone) even where the desktop equivalent is one-tap.

**Accessibility (mobile, NFR-026).**
- Every control ≥**44×44pt** with ≥8pt spacing; labels exposed to VoiceOver/TalkBack. Connection state is a labelled live region ("Connected as Presenter" / "Disconnected, controls unavailable").
- Contrast AA on-device; state by icon+word+shape, not colour alone. Reduced-motion honoured (reconnect spinner → static). Primary actions reachable one-handed (bottom-weighted layout).

---

## 13. Component — [R4] AI scripture-suggestion card (approve / reject / edit / display / ignore / undo)

**Purpose.** Surface an auto-detected scripture reference for a **human decision** — never auto-display (FR-115/117, WORKFLOWS A6, invariant 4). It accelerates JTBD-2 while keeping the Scripture Operator as the mandatory gate. (Release R4; specced here so the interaction contract is fixed early.)

**Wireframe.**
```
┌ SUGGESTION ─ scripture detected ─────────────── confidence 0.86 ▓▓▓▓░ ┐
│  ✝  Romans 8:28   ·   WEB   ·   explicit reference                    │
│  “And we know that all things work together for good to those who      │
│   love God, to those who are called according to his purpose.”         │
│  Heard: “…turn with me to Romans chapter eight verse twenty-eight…”    │
│  Why: deterministic reference parse (spoken numerals) · high certainty │
│  Alternatives:  ○ Rom 8:28–30   ○ ESV (not installed)                  │
│ ─────────────────────────────────────────────────────────────────────│
│  [[ Approve → Preview ]] [ Display Live ]  [ Edit ]  [ Reject ] [ Ignore ]│
│                                              (never auto-displays)       │
└───────────────────────────────────────────────────────────────────────┘
   after Display:  ┌ Displayed Rom 8:28 · Undo (5s) ↶ ┐   (quick-undo toast)
```

**Key states.** `queued` (in the approval queue, WORKFLOWS A6 `suggested`), `focused/expanded`, `previewing` (Approve → staged to Preview), `displayed` (operator sent to Live), `undo-window` (≥5s after Display, FR-117), `dismissed-reject` (negative feedback recorded), `dismissed-ignore` (silent), `superseded` (cooldown/duplicate-suppressed, FR-114). Confidence and a plain-language **reason** are always shown; low-confidence/semantic-only suggestions are visually distinct and can **never** be routed to auto-display (FR-113/116).

**Interaction — mouse/keyboard.** Actions (all human, none automatic):
- **Approve → Preview** (safe default, `A`): stages the passage into the scripture stager/Preview; operator then Displays via §5/§7. Matches operator-confirmation default (FR-115, WORKFLOWS B6).
- **Display Live** (`D`): pushes to program in one step (for trusted explicit refs); still a deliberate keypress, still logged. Followed by the **Undo (5s)** toast.
- **Edit** (`E`): opens reference/translation/range/template in the stager to correct a mis-hear before approving.
- **Reject** (`R`): dismiss **and** record a false-positive signal for detection history/feedback (FR-118).
- **Ignore** (`I`): dismiss silently (not now / duplicate) — no feedback signal, no learning penalty.
- **Undo** (`Cmd/Ctrl+Z` within window): revert the live output to the prior state, guaranteed ≥5s (FR-117).
- Alternatives (different range/translation) are selectable before Approve/Display.

The card lives in an **approval queue** panel; multiple suggestions stack newest-on-top; keyboard focus moves card-to-card with `↑/↓`. Detection **never blocks manual scripture control** — the operator can ignore the whole queue and search manually at any time (FR-119).

**Inputs / outputs.** In: detection event (reference, resolved passage verified against local index, translation, confidence, reason, alternatives, source transcript span) — FR-111/114/125. Out: `approveToPreview()`, `displayLive()`, `edit()`, `reject(feedback)`, `ignore()`, `undoLive()`. Display/undo append to audit + detection history (FR-118/150).

**Error & edge handling.**
- **Never auto-displays** — there is no "auto" action on the card; auto-display mode (FR-115/116) is a separate, discouraged, corroboration-gated, warned setting and even then only for high-confidence explicit refs, never semantic-only (invariant 4).
- **False positive** = a Reject/Ignore in the queue, **never a wrong verse on screen** (WORKFLOWS A6 expectation).
- **Unverified reference:** if a detected reference can't be matched in the local index it is flagged "unverified" and cannot be one-tap Displayed until resolved (parallels FR-125).
- **Duplicate/cooldown:** repeats within the cooldown window and the currently-on-screen passage are suppressed (FR-114) so the queue doesn't spam during a re-read.
- **Provider/detector failure:** the card simply stops appearing; manual search is unaffected (WORKFLOWS F4, FR-119) — no error blocks live control.
- **Accuracy honesty:** the card and its help state that detection is reliable for explicit refs, fallible for quotes, unreliable for paraphrase (FR-120) — no perfect-accuracy implication.

**Accessibility.** Card is a `group`/`article` with accessible name "Scripture suggestion: Romans 8:28, World English Bible, confidence 86 percent, explicit reference." Confidence shown as number **and** meter (not colour/length alone). Each action is a labelled `button` with its shortcut in the name. New suggestions announced `polite` (not assertive — must not interrupt a live operator); the operator opts into reading the queue. Undo toast is a labelled, keyboard-reachable control persisting the full window. Contrast AA; reduced-motion (no attention-grabbing flash on arrival — a suggestion must never behave like an alarm, FR-175 + invariant 4).

---

## 14. Cross-component consistency checklist (for engineering & QA)

| Concern | Rule applied everywhere |
|---|---|
| Preview vs Live | Only §5 Go Live / §7 Display / §13 Display cross to program; editors/stagers never do (FR-012) |
| Emergency reach | Clear + Blackout reachable by dedicated on-screen control **and** always-global key from any focus, no modal, <200ms, offline (FR-076/077, CON-2) |
| Desktop authority | Every mobile/AI surface issues *requests*; UI never implies mobile/AI owns live state (CON-1) |
| No AI auto-action | No AI output reaches an output without a human action on §13 (FR-115/117) |
| Fail-safe | No empty/error/failure state blanks an audience output; failures = non-blocking banners; last-good frame holds (NFR-024) |
| Colour never alone | Every state has a word/icon + colour (WCAG 1.4.1) |
| Contrast | Operator UI AA (≥4.5:1 text, ≥3:1 UI/large); stage/confidence ≥48px + high-contrast (NFR-020) |
| Keyboard | Every action has a keyboard path; drag/edit/live all keyboard-operable (NFR-019); core live controls SR-named (NFR-021) |
| Motion | Flashing ≤3/s; reduced-motion swaps flash→static without losing information (FR-175) |
| Mobile targets | ≥44×44pt, ≥8pt spacing, SR labels, persistent connection state (NFR-026) |
| Confirmation tiers | T0 silent / T1 instant+undo / T2 confirm-destructive / T3 arm-then-fire for audience (§1.2) |
| Audit | Every live-output/consent-changing action logs device/role/action/time/result (FR-150) |

---

## 15. Open UX decisions (carry into usability testing)

- **U-1.** Should **Blackout** be available to lower mobile roles as a panic button, or Production/Admin only? (mirrors PERSONAS OQ-1 / OD-12) — affects §12 role variants.
- **U-2.** Is **Display Live** (one-step) on §7/§13 too fast for volunteer scripture operators — should orgs be able to force Approve→Preview only? (PERSONAS OQ-2, WORKFLOWS B6) — a per-org "preview-gate always" setting.
- **U-3.** Per-**output** permissions/scoping for mobile (control stream lower-thirds but not room) — flat matrix today (PERSONAS OQ-3 / OD-14).
- **U-4.** Dedicated **Pastor confidence** mobile profile distinct from Observer (own notes + timer, no other previews)? (PERSONAS OQ-5).
- **U-5.** Confirm the **focus-mode** model (§11.1) tests well with volunteers — is a persistent Presentation/Editing indicator enough to prevent "I typed into the congregation" errors, or do we need a stronger visual boundary?
- **U-6.** Time-to-first-slide target ≤10 min for new operators (METRIC-006) — validate the console shell (§1.4) + palette (§10) get a volunteer there.

---

*End of Component & Interaction Specs v1.0. Traceable to PRD v1.1 (Stage-4 audit-discharged), PERSONAS RP-12, WORKFLOWS, ARCHITECTURE v1.0. Wireframes are low-fi intent; visual design tokens ratified separately. For independent UX review alongside `docs/architecture/ARCH-UX-REVIEW-stage5.md`.*
