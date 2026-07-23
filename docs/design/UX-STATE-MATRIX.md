# SelahCue — Interface-State Matrix (UX-STATE-MATRIX)

> **Canonical rules:** [UX-CANONICAL.md](UX-CANONICAL.md) governs keybindings, colours, and emergency behaviour and supersedes conflicting inline text. **Additional required states (Stage-5 review):** every live surface carries an **always-on emergency chrome** state (Blackout + Clear visible/operable, never occluded — M10); the mobile control surface has a **"contested"** state when two controllers issue conflicting commands (host serialises; last-writer-wins; the losing device sees "another operator just acted" — M12/OD-20); and a **Cloud-provider consent** surface (R3) has states: disclosure → explicit-confirm → admin-gated-enabled → CLOUD-active indicator → error/offline → revoke/purge (M11).

Version: 1.0 (Stage 5 design) · Date: 2026-07-23 · Owner: UI/UX Designer · Status: For design review + Stage 5 gate

**Purpose.** For every key operator surface, this document enumerates the interface states the UI must design for, and — per state — *what the user sees*, *what they can do*, *the transition triggers*, and *the accessibility contract*. It is the single reference that lets engineering build, and QA verify, every state without guessing (skill: "all acceptance criteria map to a visible interaction or system response").

**Sources / evidence status.**
- **Verified** against the PRD (`docs/product/prds/SelahCue-PRD.md`) — every state references its FR/NFR/FLOW/METRIC ID.
- **Inferred (design intent)** from Personas (`docs/business/PERSONAS.md`) and Workflows (`docs/business/WORKFLOWS.md`), which are themselves un-validated domain modelling (DISCOVERY-REVIEW C4/M4). Present-tense UI behaviour below is *design intent to be built and QA-verified*, not existing behaviour.
- **Grounded** in Architecture (`docs/architecture/ARCHITECTURE.md`): desktop-authoritative Rust core + wgpu output windows + Tauri operator shell; Flutter mobile controller over TLS-1.3 LAN.
- Nothing here redefines approved scope; open UX decisions are flagged in §17 and traced to OPEN-DECISIONS IDs.

---

## 1. The four invariants every state must honour

These are non-negotiable and appear as constraints inside the tables below.

1. **Preview vs Live separation (FR-012).** Editing/staging *never* changes live output. The **only** path from staged → on-air is an explicit **GO LIVE** action. No state — loading, error, degraded, recovery — may leak preview content to live.
2. **Emergency Clear / Blackout always reachable (FR-076/077).** The `CLEAR ▾` and `BLACKOUT` controls are present, focusable, and operable in **every** desktop state, with **zero network dependency**, in <200ms. No error, permission, offline, or loading state removes, disables, or obscures them on the authoritative desktop seat.
3. **Desktop stays authoritative (CON-1, FR-098).** Loss of mobile, AI, cloud, or network never disables any desktop capability. Mobile sends *requests*; the desktop validates and executes. Stale/unvalidatable requests are **rejected, not queued** (FR-097).
4. **No AI auto-action without operator confirmation (FR-115, WORKFLOWS principle 3).** Transcription, detection, and notes never change live output on their own. The default detection mode requires human approval; nothing auto-displays.

---

## 2. How to read this matrix

Every surface uses the same ten-state vocabulary so QA can diff surfaces uniformly. Where a state cannot occur for a surface, the row is kept and marked **N/A — <justification>** (skill: N/A must be justified, not skipped).

| State | Definition used throughout |
|---|---|
| **Default** | Resting/idle steady state after a successful load; nothing in-progress. The surface's baseline appearance. |
| **Loading** | Data fetch, model load, render, or index build in progress. |
| **Empty** | No content exists yet (zero items / no query / not started). A *designed* state, not a blank. |
| **Populated** | Content present and actively worked or driven live. |
| **Error** | An operation or subsystem failed. Always non-blocking to already-live output (invariant 2). |
| **Permission-denied** | The device/user role (RBAC, PERSONAS §2) forbids the surface or action. |
| **Offline / no-network** | No LAN and/or no internet. Core surfaces stay fully operable (NFR-015); only network-dependent extras degrade. |
| **Mobile-disconnected** | A paired controller dropped (desktop view) **or** the controller lost its host (mobile view). Desktop unaffected (invariant 3). |
| **Degraded (AI / perf)** | A subsystem runs below target: AI degraded, frame drops, HW-decode fallback, weak Wi-Fi. Core control preserved. |
| **Recovery** | Post-crash resume, display/audio reconnect, or reconnect re-sync restoring exact prior state. |

**Transition notation:** `← <trigger to enter>` / `→ <trigger to exit>`.

**State-styling tokens** (canonical: UX-CANONICAL.md §4): `LIVE` = solid **red** tally + text "LIVE" + solid border; `PREVIEW` = **green** + text "PREVIEW" + dashed border; `DEGRADED`/warning = **amber** chip + icon; `ERROR` = non-alarming banner with icon + heading (never color-only); `OFFLINE` = slate badge; `DISCONNECTED` = slate badge + text. Colour is **never** the only signal (WCAG 1.4.1; NFR-020).

---

## 3. Global operator console — layout & always-on chrome

The desktop shell (Tauri) that hosts most surfaces. The **top status bar** and **bottom emergency/action bar** persist across all surfaces and all states.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ SelahCue  ● LIVE   [Service: Sunday 10AM ▾]   ⏱ 24:13   ☁ CLOUD OFF   ⬤2 devices  ⌨ ⚙   │  ← status bar (always)
├───────────────┬────────────────────────────────────────┬───────────────────────────────────┤
│ SERVICE PLAN  │  EDITOR / WORKSPACE                      │  PREVIEW  (staged, amber, dashed) │
│ (run sheet)   │                                          │  ┌─────────────────────────────┐  │
│ ▸ Welcome     │    [ slide canvas / content editor ]     │  │  next content to go live    │  │
│ ▾ Worship     │                                          │  └─────────────────────────────┘  │
│   • Song A ◀L │                                          │       [  GO LIVE  → ]  (only path)│
│   • Song B  N │                                          ├───────────────────────────────────┤
│ ▸ Sermon      │                                          │  LIVE / PROGRAM  (red, solid)     │
│ ▸ Response    │                                          │  ┌─────────────────────────────┐  │
│               │                                          │  │ ● on MAIN + STAGE           │  │
│               │                                          │  └─────────────────────────────┘  │
├───────────────┴────────────────────────────────────────┴───────────────────────────────────┤
│  [ CLEAR ▾ ]  [ BLACKOUT ]        current ▸ Song A v2      next ▸ Song B      Scr | Tmr | Out │  ← emergency + action bar (always)
└──────────────────────────────────────────────────────────────────────────────────────────────┘
   ◀L = live marker   N = next marker
```

**Always-on chrome contract (applies in every state of every surface):**

| Element | Contract |
|---|---|
| `CLEAR ▾` / `BLACKOUT` (bottom-left) | Invariant 2. Always visible/focusable/operable; offline; <200ms; canonical shortcuts (UX-CANONICAL §1) `Esc Esc`→**clear**, `B`→**blackout**, with non-unbindable global fallbacks `Ctrl/Cmd+Shift+.`/`+B`. Confirm-on-blackout is a fast toggle, never a modal that blocks re-blackout. `aria-live="assertive"` announces "Blackout on / Live restored". |
| `● LIVE` tally (status bar) | Persistent on-air indicator; red + "LIVE" text; mirrors program state; screen-reader `role="status" aria-live="assertive"`. |
| `☁ CLOUD OFF/ACTIVE` | FR-133. Unmistakable indicator whenever any cloud provider is transmitting; text + icon; never color-only. Default "CLOUD OFF". |
| `⬤ N devices` | Paired-controller count + connection state; opens Pairing/Devices admin. |
| `current ▸ / next ▸` | FR-013. Reflects live state within ≤100ms; always present so the operator never loses place. |
| Preview panel border | Green + dashed + "PREVIEW" label — visually un-confusable with the red/solid Live panel (invariant 1; colorblind-safe via border-style + label). |

---

## 4. Surface: Service Plan (run sheet)

Desktop authoring/operating surface. Refs: FR-001…008, FR-024, FLOW-001, WORKFLOWS A1. Primary personas: Service Coordinator (build), Church Media Operator (drive).

```
 SERVICE PLAN                       [ + Item ▾ ] [ Reorder ] [ Publish ]
 ─────────────────────────────────────────────────────────────────────
 ▾ Worship set                                    planned 18:00 · @Ada
   • Song A — "Great Are You Lord"     3 slides   04:00  ◀ LIVE
   • Song B — "Way Maker"              5 slides   05:00    NEXT
   ⚠ • Video — bumper.mp4         MISSING MEDIA   00:30
 ▸ Sermon                                          25:00  @Pastor J
 ─────────────────────────────────────────────────────────────────────
 Planned length 1:12:00     ⟳ change badge: plan edited since publish
```

| State | What the user sees | What they can do | Transitions (← enter / → exit) | Accessibility |
|---|---|---|---|---|
| **Default** | Ordered run-of-show; current item = `◀ LIVE`, next = `NEXT`; per-item duration + owner (FR-004); section headers collapsible. | Scroll, select an item → stages to Preview; expand/collapse sections; open in Editor; jump position. | ← plan opened/published (FR-006). → select item; go-live; open editor. | Roving-tabindex list; `role="tree"`/`treeitem`; each item name announces "item, type, duration, live/next". Live item `aria-current="true"`. |
| **Loading** | Skeleton rows; "Opening plan…"; missing-media scan spinner (FR-007). | Cancel/wait; already-live output untouched. | ← file open / DB read. → load ok = Populated; failure = Error. | Spinner `role="status" aria-live="polite"` "Loading plan"; focus parked on list container, not lost. |
| **Empty** | No plan or new blank plan: centered CTA "Create a service", "Choose a template", "Duplicate previous", "Import" (WORKFLOWS B1). | Create/choose template/duplicate/import. | ← first run / new service. → first item added = Populated. | CTA buttons in logical tab order; heading `<h2>` "No service plan yet"; each action a real `<button>`. |
| **Populated** | Full plan; durations sum to planned length; `⟳ change badge` if edited post-publish (A1); `⚠ MISSING MEDIA` badges (FR-007/F6); drag-handles in Reorder mode. | Reorder (drag or `Alt+↑/↓`), edit, duplicate/template/version (FR-005), relink missing media, stage any item, publish/hand-off (FR-006). | ← content present. → item goes live; edit → Editor. | Drag has keyboard equivalent (`Alt+↑/↓`) — NFR-019. Missing-media badge = icon + "Missing media" text + `aria-describedby` remediation hint. |
| **Error** | Non-blocking banner: "Couldn't open this plan — the file may be moved or corrupt." Offers "Restore last autosave version" (FR-005 last-3) + "Run integrity check" (FR-079). Any already-live output is **unaffected**. | Restore an autosave version, run integrity check, open a different plan. | ← corrupt/missing plan, version mismatch. → restore/repair = Populated. | Banner `role="alert"`; icon + heading + body; actions keyboard-first; does not steal focus from emergency bar. |
| **Permission-denied** | Read-only plan (badge "View only"); reorder/edit/publish controls hidden, not just greyed (persona pain: "seeing controls they can't use"). Operator can still follow along + stage where role allows. | Scroll, follow live position; stage if role permits (matrix). | ← user lacks planning permission / mobile role read-only. → role upgrade = Populated. | "View only" conveyed in text + `aria-disabled`; hidden actions removed from tab order. |
| **Offline / no-network** | Fully operable (plan is local, NFR-015). Only "Publish/share to team" (if network-backed) shows a queued/`OFFLINE` chip; media on network shares flagged. | Everything except network share; local reorder/edit/stage/go-live. | ← network down. → network back = queued shares flush. | `OFFLINE` chip = slate badge + "Offline" text; no functional loss announced. |
| **Mobile-disconnected** | Desktop plan control fully intact (invariant 3). A controller that was mirroring the plan drops → `⬤` device count decrements; no modal. | Continue unaffected; re-pair from Devices admin if wanted. | ← paired controller drops (F3). → reconnect (F3) re-syncs mobile. | Status-bar count update `aria-live="polite"`; never a focus-stealing alert for a non-authoritative loss. |
| **Degraded (perf)** | Large plan (≥50 items, FR-001) virtualises smoothly; if library index is rebuilding, an "Indexing…" chip appears; in-plan search may be briefly slower. | All actions; search results fill in as index completes. | ← large plan / index rebuild. → index done = Default. | Indexing chip `aria-live="polite"`; no blocking. |
| **Recovery** | Post-crash **Resume** banner: "Restore Sunday 10AM to its last live position?" With **crash-loop breaker** (FR-075) after N rapid crashes: choose "Resume last live state" vs "Start clean / skip last item"; the suspected offending item is flagged disabled. | Resume, start clean, or skip/disable the flagged item. | ← relaunch after abnormal exit (F5/F7). → choice made = Populated at restored position. | Recovery is a **choice**, not auto — `role="dialog"`, focus trapped, first focus on the safe default ("Resume"); ≤5s data-loss note (NFR-023). |

---

## 5. Surface: Slide / Content Editor

Desktop authoring. Refs: FR-009…017, FR-019…021, FR-049, FR-016 (undo), FR-173 (decode hardening), FR-074 (autosave). Persona: Media Operator / Coordinator.

```
 EDITOR — Song A · slide 2/3            [ Template ▾ ] [ Layers ] [ ↶ ↷ ]  ● Saved
 ┌───────────────────────────────────────────────┐  Layers
 │                                                 │  ▸ Text  "Great are you Lord"
 │        Great are You, Lord                      │  ▸ Background  motion.mp4
 │        It's Your breath in our lungs            │  ▸ Lower third (off)
 │                                                 │
 └───────────────────────────────────────────────┘  Safe area ⬚  Contrast ✓
   NOTE: editing here NEVER changes live (FR-012)
```

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Selected slide on canvas; layer list; template controls; `● Saved` autosave indicator; safe-area + contrast guides. | Edit text/box/image layers, reorder, apply theme (FR-010), undo/redo (FR-016). None of it touches live. | ← item opened from plan. → stage to preview; close. | Canvas controls labelled; layer list `role="list"`, reorder via keyboard; contrast checker surfaces per-slide contrast ratio (helps meet NFR-020 on outputs). |
| **Loading** | "Rendering…"; thumbnail generation for large groups; theme-apply progress. | Wait; live output unaffected. | ← open large doc / apply theme. → done = Default. | `aria-busy="true"` on canvas region; focus retained. |
| **Empty** | New/blank slide: "Add text", "Add background", "Add element", "Apply a template". | Add first element or apply template. | ← new slide, nothing selected. → element added = Populated. | Empty canvas has accessible name "Empty slide — add content"; CTAs are buttons. |
| **Populated** | Layered content; drag-to-position with snapping; undo/redo stack (≥20, FR-016); copyright-metadata fields for songs (FR-021). | Full editing; toggle on-slide attribution footer (FR-021); duplicate; reorder sections (FR-019). | ← content present. → stage; go-live via Preview only. | Every layer keyboard-selectable; position adjust via arrow keys; undo announced ("Undid: move text"). |
| **Error** | An element that fails to decode (untrusted media/font, FR-173) shows a **safe placeholder** inline + "This image couldn't be loaded" — never a broken canvas. Save failure surfaces the FR-169 storage-guard warning "Low disk — changes may not save". | Replace/relink the element; free disk; retry save. | ← decode/parse fail; disk write fail. → fixed = Populated. | Inline error `role="alert"` scoped to the element, not the whole editor; heading + action. |
| **Permission-denied** | Read-only canvas ("View only"); edit tools hidden. | Inspect; stage if role allows. | ← no edit rights. → role upgrade = editable. | Tools removed from tab order; "View only" in text. |
| **Offline / no-network** | Fully operable — authoring is local (NFR-015). No network affordance here. | Everything. | ← network down. → n/a. | No change; no false "offline" alarms. |
| **Mobile-disconnected** | **N/A** — the Editor is a desktop authoring surface, not mirrored to or driven from mobile. A controller drop only decrements the status-bar count. | — | — | — |
| **Degraded (perf)** | Heavy media preview downscales; motion-background preview may pause with a "Preview paused for performance" chip; export/thumbnail throttled. | Continue editing; final output unaffected by editor preview throttle. | ← perf pressure / HW-decode fallback (ADR-0006). → headroom returns = Default. | Chip `aria-live="polite"`; reduced-motion users get the paused preview by default (FR-175). |
| **Recovery** | Autosave restores unsaved edits after crash (≤5s loss, NFR-023) with an "Unsaved edits recovered" note; undo history rebuilt where possible. | Keep or discard recovered edits. | ← relaunch after crash (F5). → choice = Populated. | Recovery note `role="status"`; non-destructive; live triggering is never "undone" (FR-016). |

---

## 6. Surface: Preview panel (staged)

The staging area — what *will* go live. Refs: FR-012/013, JTBD-1, WORKFLOWS A2. **Invariant 1 lives here.**

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Green/dashed **PREVIEW** frame; last staged content or empty; armed **GO LIVE** button (the only bridge to Live). | Stage content, adjust it, then **GO LIVE**. Edits never affect Live. | ← item staged. → GO LIVE = content moves to Live panel. | Panel labelled "Preview — staged content, not live"; GO LIVE is a distinct high-emphasis button with `aria-keyshortcuts` (canonical `Enter`, distinct from Next=`Space`; global `Ctrl+Enter`). |
| **Loading** | "Staging…" — scripture pagination (FR-029), media preload (FR-071), template render. | Wait or re-stage a different item. | ← stage action. → ready = Populated; GO LIVE disabled until ready. | `aria-busy`; GO LIVE `aria-disabled="true"` with reason "Preview still loading". |
| **Empty** | Placeholder "Nothing staged — pick an item to preview." | Stage from plan/scripture/editor. | ← cleared / fresh start. → stage = Populated. | Accessible name states empty + how to fill. |
| **Populated** | Fully rendered staged content; verse-by-verse or slide-by-slide navigation of the staged set; GO LIVE armed. | Navigate within staged set, edit, swap translation/template, **GO LIVE**. | ← content staged & ready. → GO LIVE. | Staged navigation keyboard-operable; announces "Staged: John 3:16 (WEB), slide 1 of 2". |
| **Error** | Staged item fails to render → safe placeholder + "This item can't be previewed"; **GO LIVE is disabled** to protect the audience (fail-safe). **Live is unaffected.** | Fix/replace/relink; stage a different item. | ← render/decode error. → resolved = Populated. | GO LIVE disabled with spoken reason; error `role="alert"` scoped to panel. |
| **Permission-denied** | Roles that can't stage/go-live (Observer) see Preview **view-only**; GO LIVE hidden. | Watch staged content only. | ← low role. → role upgrade = interactive. | GO LIVE removed from DOM/tab order for these roles. |
| **Offline / no-network** | Fully operable (local staging). | Everything. | ← network down. → n/a. | No change. |
| **Mobile-disconnected** | The preview *stream to a mobile* stops (mobile shows its own reconnecting state); the **desktop preview is unaffected**. | Continue on desktop. | ← controller drop. → reconnect re-streams preview. | Desktop panel silent on this; no alarm. |
| **Degraded (perf)** | If the WebView preview stream is bandwidth/GPU-limited (ADR-0003 S5 fallback), the *thumbnail* preview downscales — a "Preview at reduced resolution" chip appears. **Actual output fidelity is unaffected** (native wgpu path). | Trust the Live panel + outputs for true fidelity; continue. | ← preview-stream pressure. → headroom = Default. | Chip `aria-live="polite"`; clarifies it is preview-only, not output. |
| **Recovery** | After crash, Preview re-populates from last staged item (or empties safely); after a display reconnect, offers "Re-stage current live to preview" for quick re-push (F1 step 4). | Re-stage, GO LIVE. | ← crash resume / display reconnect. → staged = Populated. | Recovery affordance is explicit action, never auto-go-live (invariant 1 + 4). |

---

## 7. Surface: Live / Program panel

Mirror of what is on the physical outputs. Refs: FR-013, FR-036/037/041/059/070/160, NFR-004/024, JTBD-1/6. **This surface must never lie about what is on screen.**

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Red/solid **LIVE** frame; per-output tallies (MAIN, STAGE); `current ▸ / next ▸`; live thumbnails within ≤100ms of truth (FR-013). | Advance/back (`→`/`←`), clear layers, blackout, jump. | ← content live. → clear/blackout/advance. | Panel `role="region" aria-label="Live output"`; on-air state `aria-live="assertive"` announces "Live: Song A slide 2 on Main and Stage". |
| **Loading** | Brief transition indicator during GO LIVE / advance — must complete ≤150ms (NFR-004); the previous frame is held, never a flash of empty. | Wait (sub-perceptual); emergency controls still live. | ← go-live/advance. → rendered = Populated. | No focus change on transition; latency budget protects perceived instantness. |
| **Empty** | **Designed, explicit** state — not a bug. Shows `CLEARED` or `BLACKOUT` in words on the panel (never an ambiguous blank), so the operator always knows *why* the screen is dark. | Un-blackout (restores prior content, FR-077), or stage + GO LIVE new content. | ← Clear/Blackout invoked; service start. → new content live. | The panel **and** a status chip both say "Output cleared" / "Blackout active" — critical anti-ambiguity (persona fear of "black screen"). `aria-live="assertive"`. |
| **Populated** | Live content across outputs; per-output content may differ (main = lyrics over motion; stage = current/next/clock; FR-038 R2); missing-media shows a **placeholder, never black** (FR-070). | Advance/repeat/jump (FR-024), per-layer clear (FR-078), blackout, send to other outputs. | ← content live. → any live change. | Each output tally focusable; current/next announced on change. |
| **Error** | A single output's decoder/GPU fault → its **last-good frame is held** (NFR-024, FR-160); a banner names *only* that output ("Stage output: display error — holding last frame"); **other outputs keep running**; recovery happens out-of-band. | Continue on healthy outputs; re-init the affected output; content is never lost or rebuilt. | ← per-output decoder fault / display glitch (F1). → auto-recover ≤3s (FR-160) or manual re-select. | Banner scoped to the output, `role="alert"`, does **not** imply global failure; emergency bar unaffected. |
| **Permission-denied** | Roles without live-drive rights (Observer, most mobile) see Live **view-only**; advance/clear/blackout hidden per role (matrix). | Monitor live state. | ← low role. → role upgrade. | View-only stated in text; disallowed controls out of tab order. |
| **Offline / no-network** | Fully operable — core live is offline-first (NFR-015, invariant 3). No degradation of live control. | Full live control. | ← network down. → n/a. | No change; no false alarm on the most safety-critical panel. |
| **Mobile-disconnected** | Desktop retains **all** live authority (FR-098). Any in-flight mobile advance that can't be validated is **rejected, not replayed** (FR-097) — no ghost slide change. Status-bar device count updates. | Continue driving live from desktop. | ← controller drop (F3). → reconnect re-syncs mobile to *current* live truth before re-enabling it. | Non-authoritative loss → `aria-live="polite"` count change only; never a focus-stealing modal on the live panel. |
| **Degraded (perf)** | GPU/decoder falls back (software decode / 1080p30, ADR-0006) — **content stays on screen**; a per-output "Reduced performance" chip appears; reduced-motion/seizure caps still enforced (FR-175). | Continue; optionally lower output load. | ← perf pressure / zero-copy fallback. → headroom = Default. | Chip is informational (`polite`); never blocks live control; flashing capped ≤3/sec regardless (FR-175). |
| **Recovery** | On **display reconnect**, the exact prior live content auto-restores to that output (FR-041/F1) with a brief "Restored to Stage output" toast. On **crash resume**, live state is re-pushed to the correct displays (F5) and running timers re-anchored (FR-075). On **GPU device-loss**, affected outputs recover ≤3s holding last frame (FR-160). | Verify outputs (pre-service check, FR-008); resume driving. | ← reconnect / relaunch / GPU reset. → restored = Populated. | Restoration is automatic for outputs (no rebuild), announced `assertive`; crash-resume position offered as a choice, not silent. |

---

## 8. Surface: Output / Display config

Desktop admin surface. Refs: FR-036/037/040/041/046/151; FR-042/043/044/163 (R2); FR-160/161; ADR-0004/0006. Personas: System Administrator, Livestream Director.

```
 OUTPUTS                                            [ Identify displays ] [ + Output ]
 ─────────────────────────────────────────────────────────────────────────────────
 ● MAIN    → Display 2 (1920×1080)  fullscreen   ✓ healthy      [ Test pattern ]
 ● STAGE   → Display 3 (1920×1080)  fullscreen   ✓ healthy
 ○ STREAM  → (unassigned)                         — assign display —      (R2)
 ─────────────────────────────────────────────────────────────────────────────────
 Tip: only 2 displays detected — STREAM needs a 3rd output or a windowed output.
```

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Output list (MAIN/STAGE/…); each shows assigned display, resolution, health; **Identify** button (FR-040). | Assign/reassign displays, toggle fullscreen/windowed (FR-046), identify, save venue profile (FR-151). | ← config opened. → assignment change. | List `role="table"`; each output row has accessible name "Main output, Display 2, 1080p, healthy"; Identify announces the on-screen number it drew. |
| **Loading** | "Detecting displays…" while enumerating monitors. | Wait; running outputs untouched during enumeration. | ← open / hardware change event. → enumerated = Populated/Empty. | `aria-busy`; focus retained. |
| **Empty** | No outputs configured, or **only one display present**: guidance "Add an output" + warning that a separate stage display needs a 2nd monitor (or a windowed output). | Add output; assign the sole display; use windowed output. | ← fresh install / single-monitor laptop. → output added = Populated. | Warning = icon + text; CTA buttons; single-display constraint stated plainly. |
| **Populated** | Outputs mapped and live-capable; per-output health (connected/resolution/dropped-frames R2, FR-042); windowed/fullscreen state. | Configure resolution/layout/fps (FR-163 R2), delay/rotate/crop (FR-044 R2), send test pattern (FR-043 R2). | ← outputs assigned. → edit config. | All transforms keyboard-settable; health status text + icon. |
| **Error** | Assignment failed / unsupported resolution / display vanished / **GPU device-loss** (FR-160): row shows "error — holding last frame", offers re-assign / retry; **other outputs and live content unaffected**. | Reassign, pick supported resolution, retry, run test pattern. | ← display fault (F1), unsupported mode, TDR. → fixed = Populated. | Row-scoped `role="alert"`; clarifies isolation ("Stage only"). |
| **Permission-denied** | Non-admins see **read-only** output status (health, assignments) but cannot change config (FR-151). | View health; identify (safe). | ← non-admin role. → admin. | Edit controls hidden; "View only (admin configures outputs)" text. |
| **Offline / no-network** | Fully operable — displays are local hardware (NFR-015). NDI/browser-source (R2) is LAN, not internet. | Everything local. | ← network down. → n/a. | No change. |
| **Mobile-disconnected** | The mobile **output-health view** (FR-096, R2) stops updating on the phone; desktop config unaffected. | Continue on desktop. | ← controller drop. → reconnect. | Desktop silent on this. |
| **Degraded (perf)** | Per-output "dropped frames >5% over 10s" flag (FR-042); zero-copy HW-decode fallback noted per output (ADR-0006) as "software decode / reduced fps". | Reduce load, lower fps/resolution, drop an output. | ← frame-drop condition / decode fallback. → recovered = healthy. | Health chip text ("12% frames dropped") not color-only; `aria-live="polite"`. |
| **Recovery** | Unplug/replug an output → **exact prior content auto-restores** to it (FR-041/F1); venue profile reload restores assignments. | Verify via pre-service check (FR-008). | ← reconnect / profile load. → restored = Populated. | Auto-restore toast `assertive`; no manual rebuild required. |

---

## 9. Surface: Scripture search

Desktop primary; mobile secondary for scoped roles. Refs: FR-025…031/035, FR-165 (R4 manual fuzzy/semantic), FLOW-002, WORKFLOWS A2. Personas: Scripture Operator.

```
 SCRIPTURE                                  Translation: [ WEB ▾ ]  (PD)
 ┌──────────────────────────────────────────────────────────────────┐
 │  🔎  Rom 8:28-30                                        [ Stage ] │
 └──────────────────────────────────────────────────────────────────┘
 Parsed → Romans 8:28–30 · 3 verses · 2 slides @ 2 verses/slide
 History:  Jn 3:16 · Ps 23 · 1 Cor 13:4        ★ Favourites: Rom 8:28
```

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Search field (focused), translation switcher with PD attribution (FR-035), History + Favourites (FR-031). | Type a reference or keyword; pick translation; open favourites. | ← surface opened. → search submitted. | Search field has `role="searchbox"` + label; translation switcher announces "WEB, public domain". History/favourites are lists. |
| **Loading** | "Searching…"; keyword search target <500ms (FR-028); translation module load. | Wait; type-ahead may refine. | ← query submit. → results = Populated; none = Empty. | `aria-busy`; results region `aria-live="polite"` announces count. |
| **Empty** | No query → History + Favourites shown. No results → "No matches — check the reference or spelling" with the parser's interpretation echoed (FR-026 invalid ref rejected *with guidance*). | Refine query, pick from history/favourites. | ← empty field / zero results. → valid results = Populated. | Guidance is text, not just a red field; suggested corrections keyboard-selectable. |
| **Populated** | Parsed reference (ranges/multi-selection, FR-027) or ranked keyword hits; pagination preview "N slides @ M verses/slide" (FR-029); verse-number format per setting. | Stage to Preview (never straight to live), adjust verse range/translation, favourite, paginate. | ← results returned. → Stage = Preview panel. | Each result focusable; staging announces "Staged Romans 8:28–30 (WEB)"; **stage → preview only** (invariant 1). |
| **Error** | Typed reference won't parse → inline "Couldn't read that reference" + examples ("try Rom 8:28-30, Ps 23, Jn 3:16; 1 Cor 13:4"). Translation module missing → "That translation isn't installed". | Correct the reference, pick another translation. | ← parse/module error. → valid = Populated. | Inline error `role="alert"` tied to the field via `aria-describedby`; examples are copy-able text. |
| **Permission-denied** | On mobile, roles without scripture rights don't see this surface at all (matrix: only Scripture Operator / Production / Admin). On desktop, always available. | — (role-gated on mobile). | ← low mobile role. → role upgrade. | Surface omitted from the mobile role's nav entirely (not a disabled tease). |
| **Offline / no-network** | **Fully operable** — bundled PD translations are local (CON-3, NFR-015). Only the R4 licensed-translation *API* path (FR-034) needs network. | Full search/stage on PD translations. | ← network down. → API translations queue/unavailable. | Offline PD translations behave identically; any API-only translation shows a slate "Needs network" chip. |
| **Mobile-disconnected** | A mobile scripture station drops; the desktop scripture surface is unaffected (invariant 3). | Continue on desktop. | ← controller drop. → reconnect. | Desktop silent. |
| **Degraded (AI / perf)** | Keyword index rebuilding → slower search ("Indexing… results may be incomplete"). R4 licensed-API failure → **graceful fallback to local PD translation** (FR-135-style) with a banner "Using local translation — API unavailable". Manual fuzzy/semantic search (FR-165) may return fewer candidates when the semantic index is degraded. | Search anyway (local), retry API later. | ← index rebuild / API error. → recovered = Populated. | Fallback banner `polite`; never blocks manual reference search (FR-119). |
| **Recovery** | Last search + history restored after restart; favourites persist. | Re-run last search in one action. | ← relaunch. → restored = Default. | History/favourites persistence announced only if focus lands there. |

---

## 10. Surface: Timer panel

Desktop + role-scoped mobile. Refs: FR-054…065, FR-094, NFR-022, FLOW-003, WORKFLOWS A3. Personas: Stage Manager, Timer Operator. **Safety-critical: never surprise the audience with a countdown.**

```
 TIMERS                                                   [ + Timer ▾ ]
 ─────────────────────────────────────────────────────────────────────
 ▸ Sermon countdown   24:13   ● running   → STAGE only   (not audience)
     thresholds:  amber 02:00 · red 00:30      [⏸] [＋1m] [－1m] [reset]
 ▸ Service clock      10:41    time-of-day     → operator only
 ─────────────────────────────────────────────────────────────────────
 TIME UP config:  text "TIME UP" · red bg · flash≤3/sec · STAGE only (default)
```

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Timer list; each shows type, remaining/elapsed, target outputs, scope (operator-only vs stage-visible, FR-058), threshold colours (FR-057). | Create timers/presets (FR-057), start/pause/resume/reset/±time (FR-055), pick target outputs, set TIME UP state (FR-059). | ← surface opened. → start timer. | Each timer `role="timer" aria-live="off"` (avoid per-second spam); announce on state change (start/pause/threshold/TIME UP), not every tick. |
| **Loading** | **N/A** — timers are local and instantaneous (monotonic clock, FR-065). Preset load is sub-perceptual. | — | — | — |
| **Empty** | No timers → "Create a timer" + preset chips (sermon 25:00, offering 5:00, countdown-to-start). | Create from preset or custom. | ← no timers. → created = Populated. | Preset chips are buttons; each states its duration. |
| **Populated** | Running timers with live remaining; threshold styling (amber 2:00, red 0:30, A3); **TIME UP** state at zero (FR-059) with overrun into negative (FR-060); operator-only vs stage-visible clearly separated. | Start/pause/±time, send stage message (FR-162), trigger/extend/dismiss TIME UP (FR-061), reset. | ← running. → hits 0 = TIME UP; dismiss/extend. | Threshold changes announced ("Sermon: 2 minutes left"); TIME UP `aria-live="assertive"`. Colour + text always paired. |
| **Error** | A timer's **target output is lost** (display gone) → the timer **keeps running on the authoritative clock**; a chip warns "Not visible — Stage output disconnected". Timer accuracy is never affected. | Reassign target output; continue timing. | ← target display disconnect (F1). → output back = visible again. | Chip = "Not currently visible on Stage" text; timer value unaffected and still announced. |
| **Permission-denied** | Only Timer Operator / Production / Admin control timers + TIME UP (matrix); other roles view. Presenter/Worship-Leader have `⚠️` limited control per admin config. | View; limited control if `⚠️` granted. | ← low role. → role upgrade. | Disallowed controls out of tab order; view-only stated. |
| **Offline / no-network** | **Fully operable** — timers/TIME UP are local desktop functions (A3, NFR-015). The desktop is "timekeeper of record". | Full timer control. | ← network down. → n/a. | No change on this safety-critical surface. |
| **Mobile-disconnected** | A mobile Timer Operator drops; the **desktop remains the timekeeper of record** (A3, invariant 3); running timers continue untouched. | Continue on desktop; dismiss TIME UP from desktop. | ← controller drop (F3). → reconnect re-syncs timer state to mobile. | Status-bar count only; no alarm; running timer keeps announcing. |
| **Degraded (AI / perf)** | **N/A by design** — timer accuracy uses an authoritative **monotonic clock independent of render frame rate** (FR-065/NFR-022, ≤100ms/hr drift). Even under GPU/perf degradation, timing is exact; only the *rendered* display of it shares the output's perf state. | — | — | Timing integrity is a guarantee, not perf-dependent — worth stating for QA. |
| **Recovery** | Crash resume **re-anchors countdowns to wall-clock** and **resumes count-up with accumulated time** (FR-075/F5) — no drift, no restart from scratch. | Verify timers in pre-service check; resume. | ← relaunch (F5/F7). → restored = Populated. | Restored timer state announced; TIME UP audit logged (FR-064 R6). |

**TIME UP safety contract (all states):** displaying TIME UP or any timer to an **audience** output requires **explicit output selection**; the default target is Stage/confidence only and **excludes audience** (FR-062). An audible cue to any output requires explicit per-output selection + confirmation, default-excluding house outputs (FR-063). Flash rate is capped ≤3/sec (FR-175).

---

## 11. Surface: Mobile control surface

Flutter controller. Refs: FR-085…098, FR-164/168, NFR-009/026, WORKFLOWS A4/F3, PERSONAS §2. Persona: Mobile Remote User (role-scoped). **All targets ≥44×44pt (NFR-026).**

```
  ┌─────────────────────────────┐        Connection: ● Connected · Presenter
  │  ● Connected   Presenter     │        ┌──────────────────────────────────┐
  │  ─────────────────────────── │        │  current ▸ Song A · slide 2/3      │
  │  current ▸ Song A  slide 2   │        │  next    ▸ Song B                  │
  │  next    ▸ Song B            │        ├──────────────────────────────────┤
  │  ┌─────────┐   ┌─────────┐    │        │   [   ◀ PREV   ] [   NEXT ▶   ]    │  44×44pt+
  │  │  ◀ PREV │   │  NEXT ▶ │    │        │   [   CLEAR (own layers)     ]    │
  │  └─────────┘   └─────────┘    │        │   [   BLACKOUT   ]  (role ✅)     │
  │  [ BLACKOUT ]  (role-scoped) │        └──────────────────────────────────┘
  └─────────────────────────────┘        Only role-permitted controls are shown.
```

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default (paired, connected)** | `● Connected` + role badge; current/next preview (FR-092); **only** the controls the granted role allows (matrix) — no teasing of forbidden controls (persona pain). | Role-scoped: advance/back, clear own layers, blackout (if role), timer/scripture per role. | ← paired + connected. → tap sends request; desktop executes ≤200ms (NFR-009). | Every control ≥44×44pt; labelled for VoiceOver/TalkBack (NFR-026); connection state `aria-live="polite"`; blackout/advance results announced. |
| **Loading** | "Connecting…" / "Syncing live state…" spinner after (re)connect, before controls enable. | Wait; controls disabled until synced to truth. | ← pairing complete / reconnect. → synced = Default. | Spinner labelled; controls `aria-disabled` with reason "Syncing"; no accidental taps register. |
| **Empty (unpaired)** | Pairing screen: "Scan the QR on the desktop" / "Enter PIN" / discovered hosts list (mDNS, FR-085); requested role shown. | Scan QR (FR-086), enter PIN (B4), pick a host. | ← app open, no known host. → pairing approved = Default. | Camera-scan has a manual-PIN fallback (accessibility + multicast-blocked); host list rows ≥44pt. |
| **Populated (actively controlling)** | Live current/next mirroring desktop; role controls active; latency subtle indicator. | Drive slides/timers/scripture/stage-messages per role (FR-093/094/095/096/162/164). | ← connected + role active. → any control action. | Action feedback within 200ms or an explicit "Sent…/Done" so the user knows it landed (persona pain: "unclear whether it reached the desktop"). |
| **Error** | Pairing rejected / cert-pin mismatch ("This host's identity changed — pairing refused", FR-086/T18) / a command **rejected** by the desktop (schema/replay/rate-limit, FR-091/174) shown as "Action not accepted" — **never a silent ghost action**. | Re-pair, retry, or defer to desktop. | ← pairing/cert/command rejection. → resolved = Default. | Error is explicit text + icon; rejected action clearly *did not* happen; no queued replay. |
| **Permission-denied** | Role downgrade → the now-forbidden controls **disappear** immediately (not greyed); admin **revoke** drops the device with "Access ended by administrator" (FR-089). | Only what the (new) role allows; nothing if unpaired. | ← role change / revoke (immediate, invariant 3). → re-grant. | Removed controls leave the tab order; revoke message `role="alert"`; large dismiss target. |
| **Offline / no-network** | Can't reach host → full-bleed **"Reconnecting…"**; **all controls disabled** (F3); the mobile holds no authority and shows it plainly. | Wait for reconnect; nothing controls the service from here while offline. | ← Wi-Fi lost / host unreachable. → link restored = Loading→Default. | Reconnecting banner high-contrast; disabled controls announced as unavailable; no offline "queue" that could fire later. |
| **Mobile-disconnected** | (Same surface, host-side view is invariant 3.) On the phone: "Reconnecting…", controls disabled; **stale actions are discarded** on reconnect, not replayed (FR-097). | Wait; re-sync happens automatically. | ← link drop (F3). → reconnect = re-validate role + re-sync live truth → Default. | On reconnect, the preview updates to *current* truth before controls re-enable — user never acts on a stale screen. |
| **Degraded (AI / perf)** | Weak Wi-Fi → preview stream downscales / drops to periodic snapshots; a "Slow connection" chip; **control still works** (control messages are tiny vs preview). | Keep controlling; expect coarser preview. | ← bandwidth pressure. → good link = Default. | Chip `polite`; control latency indicator; reduced-motion honoured on any transitions. |
| **Recovery** | After a drop, reconnect re-validates the device's role and **re-syncs current live state to the preview before re-enabling controls** (F3, FR-097) — clean, no ghost actions. | Resume control once re-enabled. | ← reconnect. → synced = Default. | The "controls re-enabled" moment is announced; first focus goes to a safe, non-destructive control. |

**Mobile emergency note (invariant 2):** Blackout on mobile is **role-scoped** (Presenter ✅; Worship Leader/Scripture ⚠️; others ❌ — matrix; OD-12 open). The **guaranteed** emergency path is always the authoritative desktop; mobile blackout is a convenience, never the safety backstop.

---

## 12. Surface: [R3] Transcript view

R3. Refs: FR-099…110, FR-166/167/170/172, FR-131…135, FR-104, WORKFLOWS A5/F2/F4. Personas: Sound Engineer (source), Operator, Post-Service Editor. **Assistive — never touches live output.**

```
 TRANSCRIPT   input:[ Pulpit Mic ▾ ] ▮▮▮▮▯ level   ☁ CLOUD OFF (local)  [▶ Start]
 ─────────────────────────────────────────────────────────────────────────────
 10:41:02  "…and so Paul writes to the church in Rome, that we know…"   (confirmed)
 10:41:09  that all things work together for good…                      · interim ·
 ─────────────────────────────────────────────────────────────────────────────
 model: base.en (auto-selected)   ⌂ offline   VAD gating ON
```

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Input-device selector + live **level meter** (FR-099); Start/Pause/Stop (FR-100); model + offline/cloud indicator (FR-133); empty transcript body ready. | Pick input, start transcription, choose language/locale (FR-167). | ← R3 surface opened. → Start = Loading→Populated. | Level meter has a text/`aria-valuenow` equivalent (not color-only); controls labelled; cloud indicator spoken. |
| **Loading** | "Loading model…" (hardware probe auto-selects a model, FR-101); "Starting capture…". | Wait; slide control **unaffected** meanwhile (invariant 3). | ← Start pressed / first run probe. → ready = Populated; can't sustain = Degraded. | `aria-busy`; a warning is announced if the probe says real-time can't be sustained. |
| **Empty** | Not started, or started but **VAD-gated silence/music produces no text** (FR-102, ≤1% non-speech committed) — an intentional quiet, not a hang. | Start, speak/route audio, adjust input. | ← not started / silence. → speech detected = Populated. | Empty body labelled "No speech yet"; VAD state visible so silence isn't read as failure. |
| **Populated** | Scrolling transcript: **interim** in provisional style + **confirmed** timestamped segments (FR-103); search/bookmarks/markers (FR-107); non-destructive correction layer (FR-106). | Search, bookmark, correct (over an immutable raw stream), export (FR-110), set custom vocabulary (FR-108). | ← speech transcribing. → Pause/Stop = saved. | Interim vs confirmed distinguished by **style + text tag** ("interim"), not color alone; corrections announced; auto-scroll pausable (reduced-motion/AT). |
| **Error** | **Capture device disconnects** (FR-170/F2): transcription **pauses, does not crash**; captured segments preserved; a **gap marker** is inserted on reconnect/new-input. Model-load failure → clear "Couldn't load model" + smaller-model option. **Slide control never affected.** | Select a new input, resume (gap marker noted), pick a smaller model. | ← device unplug / model fail. → new input = resume; gap-marked. | Pause + gap are explicit text; `role="status"`; the immutable raw stream is safe (FR-106). |
| **Permission-denied** | Full live-transcript **control** is Administrator-only (matrix); all other roles get **view-only** (👁) transcript. Mobile view is R2 (FR-164). | View transcript; Admin controls capture. | ← non-admin. → admin. | View-only stated; control affordances hidden for non-admins. |
| **Offline / no-network** | **Fully operable** — offline transcription is the **default** (Whisper family, FR-101). Cloud is opt-in only. | Full local transcription. | ← network down. → n/a for local. | Offline is the normal, un-alarming case; `⌂ offline` badge is neutral, not an error. |
| **Mobile-disconnected** | Mobile live-transcript viewers (FR-164, R2) stop updating; desktop capture unaffected. | Continue on desktop. | ← controller drop. → reconnect. | Desktop silent. |
| **Degraded (AI / perf)** | Insufficient hardware → status "**degraded / paused**", offers a smaller model (FR-104); **slide control unaffected**. Cloud provider error/quota → **graceful fallback to local** (FR-135) with a "Switched to local engine" note. **Audio-feedback guard**: while app audio plays to a shared/house output, ingestion is **suppressed** and detection **gated** (FR-172) with an on-screen "Paused: app audio on house output". | Accept degraded quality, switch model, or pause; re-route mic (FR-172 guidance). | ← weak HW / cloud fail / feedback risk. → resolved = Populated. | Degraded status is text + icon; latency indicator; the feedback-guard pause is clearly explained, not silent. |
| **Recovery** | A transcription session **survives app restart with no committed-segment loss** (FR-105); the interruption shows a gap marker (F2). | Resume the session; export the recovered transcript. | ← relaunch (F5). → restored = Populated. | Recovered segments + gap marker announced; raw stream intact (FR-106). |

**Cloud-transmission contract (all states):** no audio/transcript leaves the host until a per-provider opt-in (FR-132); while any cloud provider transmits, the **`☁ CLOUD ACTIVE`** indicator is unmistakable (FR-133) and mirrored in the status bar.

---

## 13. Surface: [R4] Scripture-suggestion queue

R4. Refs: FR-111…121, FR-095/165, WORKFLOWS A6/B6/F4, FLOW-006. Persona: Scripture Operator (approver). **Invariant 4 lives here — nothing auto-displays.**

```
 DETECTION  mode: ● Operator-confirmation (default)          Listening… ▮
 ─────────────────────────────────────────────────────────────────────────
 ┌───────────────────────────────────────────────────────────────────────┐
 │  Romans 8:28   (WEB)                              confidence  ██████░ 86%│
 │  "And we know that all things work together for good to those who love…"│
 │  reason: explicit spoken reference  ·  alt: Rom 8:28-30                  │
 │  [ Approve → Preview ] [ Display ] [ Edit ] [ Reject ] [ Ignore ]  ↶undo │
 └───────────────────────────────────────────────────────────────────────┘
```

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Mode indicator (suggest-only / **operator-confirmation = default** / auto-display, FR-115); "Listening…" when detection is active; empty queue. | Change mode (auto-display is corroboration-gated + warned, FR-116); review incoming cards. | ← detection enabled on a live transcript. → suggestion arrives = Populated. | Mode stated in text; "Listening" `aria-live="polite"`; changing to auto-display triggers a spoken risk warning (FR-116). |
| **Loading** | Detection running / resolving a candidate against the **local Bible index**. | Wait; manual scripture search (A2) always available in parallel (FR-119). | ← candidate detected. → resolved = card in Populated. | `aria-busy` on the queue; manual search never blocked. |
| **Empty** | **Designed resting state** — "No suggestions" / "Listening…". **Nothing is on screen** because nothing auto-displays (invariant 4). | Fall back to manual search anytime (FR-165). | ← no detections. → detection = Populated. | Empty state reassures ("Detection is running; nothing displays without your approval"). |
| **Populated** | Suggestion **cards**: reference, passage, translation, **confidence**, alternatives, reason, actions — approve/reject/edit/**display**/ignore/**undo** (FR-117); duplicate-suppression + cooldown applied (FR-114). | **Approve → Preview** (default) or **Display** per config (A6/B6); edit reference; reject/ignore; quick-**undo** a display within 5s (FR-117). | ← suggestion(s) queued. → approve = stages to Preview/Live; reject = dismissed. | Each card is a focusable group; actions are labelled buttons; confidence is text + bar (not color-only); approve/display are deliberately distinct to avoid mis-tap. |
| **Error** | Detector/index-resolve failure → the feature **degrades to manual search** (A2/F4); a false positive is a **dismissed card, never a wrong verse on screen**. | Use manual search; report/correct (FR-118). | ← detector error (F4). → manual path. | Error `role="status"`; reassures that live is untouched. |
| **Permission-denied** | Only Scripture Operator / Production / Admin can **approve** (matrix); other roles can't act on the queue. Auto-display is barred for semantic-only regardless of role (FR-116). | View only (if permitted) / nothing. | ← low role. → role upgrade. | Approve buttons absent for non-approvers, not merely disabled. |
| **Offline / no-network** | Operates on the **local** transcript + **local** Bible index — offline-capable (cloud STT optional). | Full approve/reject offline. | ← network down. → n/a for local path. | No change; local resolution is the norm. |
| **Mobile-disconnected** | A mobile approval station (FR-095) drops; the **desktop queue is unaffected** and remains the human gate. | Approve from desktop. | ← controller drop. → reconnect. | Desktop silent. |
| **Degraded (AI / perf)** | **Precision-over-recall** defaults (FR-121, ≤5% FP on the FR-171 set): fewer, higher-confidence cards; low-confidence/paraphrase items are visibly marked and **never auto-display** (FR-113/116); documented accuracy-limits copy is present (FR-120). | Approve conservatively; rely on manual search for paraphrase. | ← noisy audio / low confidence. → clearer audio = more cards. | Confidence + "explicit / quote / paraphrase" basis shown in text; limits disclosure readable by AT. |
| **Recovery** | Detection **history persists** with operator decisions (FR-118); a mistaken display is reversible via **quick-undo within 5s** (FR-117). | Review history; undo a recent display. | ← relaunch / recent display. → history restored / undo. | Undo is a prominent, labelled control with a visible countdown (text, not just animation). |

---

## 14. Surface: Pairing / Devices admin

Desktop, Administrator-only. Refs: FR-085…090, FR-147/148/149/150/155, WORKFLOWS A4/B4/F3, PERSONAS §2. Persona: System Administrator.

```
 DEVICES & PAIRING                                        [ Pair a device ]
 ─────────────────────────────────────────────────────────────────────────
 Pair:  ┌──────────┐   scan on the controller, then approve here
        │  ▚▚ QR ▚▚ │   fingerprint 3F:A9:… · expires in 0:48 (single-use)
        └──────────┘
 ─────────────────────────────────────────────────────────────────────────
 Paired devices
  • Ada's iPad     Scripture Operator   ● connected   last seen now   [Revoke][Rename]
  • Booth phone    Presenter            ○ disconnected 3m ago         [Revoke][Rename]
```

| State | What the user sees | What they can do | Transitions (← / →) | Accessibility |
|---|---|---|---|---|
| **Default** | Paired-device list with role, connection state, last-seen; "Pair a device" entry (FR-148). | Rename/revoke devices (immediate, FR-089); start a pairing; set time-boxed grants (FR-149, R2). | ← admin opens surface. → start pairing. | Device list `role="table"`; each row named "Ada's iPad, Scripture Operator, connected"; Revoke has a confirm (destructive) with clear consequence text. |
| **Loading** | "Generating pairing code…"; QR + host **fingerprint** + single-use short-TTL countdown (FR-086); mDNS advertising. | Wait for the controller to scan; approve when prompted. | ← Pair pressed. → controller scans = approval prompt. | TTL countdown is text (not just a shrinking ring); QR has an alt text / manual-PIN equivalent. |
| **Empty** | No devices paired → "No devices yet — pair one to control the service from a phone or tablet" + prominent Pair CTA. | Pair the first device. | ← fresh install. → first pairing = Populated. | Heading + CTA; explains the LAN/role model briefly. |
| **Populated** | Devices listed with live status; **append-only audit** of grants/changes (FR-150); role per device. | Approve/deny pairing (host-side confirm, FR-086), assign role, revoke, rename, view audit. | ← devices exist. → revoke/re-role. | Approve/Deny during pairing are large, unambiguous; audit entries readable by AT. |
| **Error** | Pairing failed — wrong PIN, **cert/fingerprint mismatch** ("identity doesn't match — refused", T18), expired TTL (FR-086), or replay/rate-limit trip (FR-091): clear cause + "Try again". | Regenerate code, retry, investigate. | ← pairing failure. → new code = Loading. | Error names the specific cause (security-relevant); `role="alert"`; never auto-approves on error. |
| **Permission-denied** | **Administrator-only** surface (matrix, FR-147). Non-admins never see it (removed from nav), not merely disabled. | — | ← non-admin. → admin only. | Surface absent for non-admins — no information leak about paired devices. |
| **Offline / no-network** | **LAN pairing works without internet** (LAN-based, NG-5). If **mDNS multicast is blocked**, the **QR-only** discovery path is used (FR-085/C14). | Pair over LAN / QR fallback. | ← no internet / multicast blocked. → QR path. | The QR fallback is presented as normal, not an error; instructions clear. |
| **Mobile-disconnected** | A device drops → row shows `○ disconnected` + last-seen; **admin can still revoke** a disconnected device; desktop unaffected (invariant 3). | Revoke, rename, wait for reconnect. | ← device drop (F3). → fast-reconnect via pinned fingerprint (FR-087/B4). | Status change `aria-live="polite"`; revoke of an offline device still effective on reconnect. |
| **Degraded** | Multicast/mDNS unreliable → surface nudges to the **QR-only** path (FR-085); high pairing-failure rate hints at network conditions. | Use QR pairing; check network. | ← flaky discovery. → QR path stable. | Guidance text, not a blocking error. |
| **Recovery** | Known devices **fast-reconnect** via pinned host fingerprint + device proof-of-possession (FR-087, no fresh QR) but remain **revocable**; a **revoke drops the device mid-session immediately** (FR-089). | Confirm reconnected roles; revoke if needed. | ← device returns / admin revokes. → reconnected / dropped. | Reconnection status announced; revoke effect is immediate and confirmed. |

---

## 15. Cross-cutting accessibility specification

Per skill: "accessibility is testable." These apply to **every** surface and satisfy NFR-019/020/021/026 and FR-014/175.

### 15.1 Keyboard model (desktop) — NFR-019, FR-014
Every core live action is operable by keyboard alone, remappable, and documented.

| Action | Default shortcut | Notes |
|---|---|---|
| Next / Previous | `→` / `←` (or `Space` / `Shift+Space`) | Advance live content; ≤150ms (NFR-004). |
| Go Live | `Ctrl/Cmd+Enter` | The **only** preview→live bridge (invariant 1). |
| Clear (layer picker) | `.` | Per-layer via the `CLEAR ▾` menu (FR-078). |
| **Blackout / restore** | `B` (global `Ctrl/Cmd+Shift+B`) | Always reachable; offline; <200ms (invariant 2). Toggles audience to black. (Clear-all = `Esc Esc`, per UX-CANONICAL §1.) |
| Command palette | `Ctrl/Cmd+K` | Fuzzy action + plan-item search (FR-015). |
| Stage message | `Ctrl/Cmd+M` | Compose/send to stage/confidence (FR-162). |
| Timer start/stop | `T` / `Shift+T` | Focused timer (FR-055). |
| Undo / Redo | `Ctrl/Cmd+Z` / `Shift+Ctrl/Cmd+Z` | Editing only; live triggers not destructively undone (FR-016). |

### 15.2 Focus order & screen-reader semantics — NFR-021
- **Focus order** follows visual hierarchy: status bar → Service Plan → Editor/Workspace → Preview → Live → **emergency/action bar always last-and-reachable** via a global shortcut regardless of current focus.
- Lists (plan, devices, outputs, suggestions, history) use **roving tabindex**; `Home`/`End` jump; `Alt+↑/↓` reorders where drag exists.
- **Live regions:** program/on-air changes and blackout use `aria-live="assertive"`; status/health/connection changes use `aria-live="polite"`; timers announce on **state change** (start/pause/threshold/TIME UP), not every tick, to avoid AT flooding.
- MVP AT baseline (NFR-021): accessible names/roles on **core live controls** — next/prev/clear/blackout/go-live, timer + TIME UP, scripture-stage. Full-UI screen-reader coverage is R2.
- Modals (recovery, destructive confirm) trap focus, restore focus on close, and default-focus the **safe** option.

### 15.3 Contrast & legibility — NFR-020
- Operator UI: WCAG 2.1 AA — **≥4.5:1** normal text, **≥3:1** large text/UI components.
- Stage/confidence output: configurable **large text (≥48px-equivalent)** + high-contrast themes for stage-lighting readability; the Editor's per-slide contrast checker (§5) helps authors meet this on audience output.
- **Colour is never the only signal** (WCAG 1.4.1): LIVE/PREVIEW/DEGRADED/ERROR/OFFLINE all carry a text label + icon + shape/border cue in addition to colour (colorblind-safe; see §2 tokens).

### 15.4 Reduced motion & seizure safety — FR-175
- Any flashing/animated **audience/livestream** output is bounded to **≤3 flashes/second** (WCAG 2.3.1) — including TIME UP flash and transitions.
- A **reduced-motion** option disables non-essential animation on audience/stream outputs and in the operator UI; motion-background previews pause by default under OS reduced-motion.
- Countdowns/undo timers expose a **text** value, not motion-only, so reduced-motion users get the same information.

### 15.5 Mobile touch & AT — NFR-026
- All interactive targets **≥44×44pt** with adequate spacing to prevent mis-taps (persona pain: "accidental taps triggering live changes").
- Every control exposes an accessible label to VoiceOver/TalkBack; connection state and command results are announced.
- Destructive/live-affecting mobile controls (blackout, clear) have deliberate spacing/confirmation to resist accidental activation.

---

## 16. Cross-cutting recovery map (ties states to WORKFLOWS F1–F7)

| Failure (WORKFLOWS) | Surfaces primarily showing it | State used | Guarantee |
|---|---|---|---|
| **F1** Display disconnect | Live/Program, Output config, Timer | Error → Recovery | Other outputs unaffected; exact content auto-restores on reconnect (FR-041). |
| **F2** Audio-device disconnect | Transcript | Error → Recovery | Transcription pauses (not crash); segments preserved; gap marker; presentation untouched (FR-170). |
| **F3** Mobile connectivity loss | Mobile surface (all panels' Mobile-disconnected row) | Offline/Mobile-disconnected → Recovery | Desktop authoritative; stale actions rejected; clean re-sync (FR-097/098). |
| **F4** AI/provider failure | Transcript, Suggestion queue, Scripture (R4 API) | Degraded/Error | Assistive degrades to manual; local fallback; nothing wrong auto-displays (FR-135, invariant 4). |
| **F5** App crash | Service Plan, Editor, Live, Timer | Recovery | Resume to last live position; ≤5s loss; crash-loop breaker choice (FR-074/075). |
| **F6** Missing media | Service Plan (badge), Live (placeholder) | Populated w/ warning / Error | Never a black audience screen — placeholder/held frame (FR-070). |
| **F7** Forced shutdown | All (via checkpoint) | Recovery | Bounded loss; one-action resume; optional redundant-desktop failover. |

---

## 17. Open UX decisions (flagged, not decided here)

Owned by Product/Admin policy, not design alone (skill boundary). Traced to OPEN-DECISIONS.

1. **Blackout on lower mobile roles** (Presenter/Worship Leader as a panic button?) — affects the Mobile *Permission-denied*/emergency rows. **OD-12**, PERSONAS §4 Q1. *Design default shown: Presenter ✅, others ⚠️/❌.*
2. **Per-output permissions** (e.g. control stream lower-thirds but not room output) — the flat matrix doesn't model this; affects Output config + Mobile permission states. **OD-14**, PERSONAS §4 Q3.
3. **Event-scoped / auto-expiring grants** — affects Pairing admin *Populated* (FR-149). **OD-15**, PERSONAS §4 Q4.
4. **Macro-trigger granularity** (per-macro allow-list vs all-or-nothing) — affects Mobile role controls (FR-168). **OD-17**, PERSONAS §4 Q6.
5. **Pastor dedicated confidence profile** distinct from Observer — affects a future mobile view variant. PERSONAS §4 Q5.
6. **Multi-controller conflict resolution** (two controllers advancing at once) — affects Live/Program + Mobile *Populated*. **OD-20**.

---

## 18. Traceability (surface → requirements)

| Surface | Primary FRs | Key NFRs | Flows |
|---|---|---|---|
| Service Plan | FR-001…008, 024 | NFR-015/019/023 | FLOW-001, A1, F5/F7 |
| Slide/Content Editor | FR-009…017, 019…021, 049, 173 | NFR-019/020/023 | A1 |
| Preview panel | FR-012/013, 029, 071 | NFR-004 | A2, FLOW-002 |
| Live/Program panel | FR-013, 036/037/041/059/070/076/077/078, 160 | NFR-004/024 | FLOW-001/009, F1/F5 |
| Output/Display config | FR-036/037/040/041/046/151, 042…044/163, 160/161 | NFR-014/024 | F1 |
| Scripture search | FR-025…031/035, 165 | NFR-015 | FLOW-002, A2 |
| Timer panel | FR-054…065, 094, 162 | NFR-022 | FLOW-003, A3 |
| Mobile control surface | FR-085…098, 164/168 | NFR-009/026 | FLOW-004/010, A4, F3 |
| [R3] Transcript view | FR-099…110, 166/167/170/172, 131…135 | NFR-007/012/018 | A5, F2/F4 |
| [R4] Suggestion queue | FR-111…121, 095/165 | NFR-008 | FLOW-006, A6/B6, F4 |
| Pairing/Devices admin | FR-085…090, 147/148/149/150/155 | NFR-016/017 | A4/B4, F3 |
| Cross-cutting a11y | FR-014/175 | NFR-019/020/021/026 | — |

---

*End of UX-STATE-MATRIX v1.0. Design intent for Stage-5 review; every state maps to a testable interaction or system response for QA. Handoff note: this matrix feeds the wireframe/hi-fi and design-system work; open items in §17 must be resolved with Product before those states are finalised.*
