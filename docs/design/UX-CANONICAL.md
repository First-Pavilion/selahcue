# SelahCue — Canonical UX Rules (single source of truth)

Version: 1.0 (Stage-5 review remediation) · Date: 2026-07-23 · Owner: UI/UX Designer + Software Architect

**This document is authoritative.** Where `UX-FLOWS.md`, `UX-STATE-MATRIX.md`, or `COMPONENT-SPECS.md` describe a keybinding, a live-safety behaviour, or a colour differently, **this file wins**. Implementation and QA test against this file. It resolves Stage-5 review blocker **B1** and majors **M8, M9, M10**.

## 1. Canonical keybindings

Two tiers: **presentation-focus** keys (active when the live/preview surface has focus) and **always-global emergency fallbacks** (OS-level global hotkeys that fire even when SelahCue is not focused or a dialog is open). Emergency keys are **non-unbindable** (they may be *remapped* but never removed).

| Action | Presentation-focus key | Always-global fallback | Non-unbindable | Notes |
|---|---|---|---|---|
| Next slide / item | `Space` or `→` | — | no | Advance only |
| Previous slide / item | `←` | — | no | |
| **Go Live** (send Preview → Program) | `Enter` | — | no | **Distinct key; never overloaded with Next** (M8) |
| **Clear all live layers** | `Esc` `Esc` (double-tap) | `Ctrl/Cmd+Shift+.` | **yes** | Clears all live output layers to empty |
| **Blackout** (toggle audience to black) | `B` | `Ctrl/Cmd+Shift+B` | **yes** | Toggles; un-blackout restores prior content |
| Clear current layer only | `Backspace` | — | no | |
| Command palette | `Ctrl/Cmd+K` | — | no | |
| Undo (edit only) | `Ctrl/Cmd+Z` | — | no | See §2 |

**Canonical meaning (resolves B1):** `Esc Esc` = **Clear all layers**. `B` = **Blackout**. These two are never swapped or reused for another action in any surface. The double-tap-Escape and the global `Ctrl/Cmd+Shift+.`/`+B` chords are reserved system-wide.

## 2. Undo and live actions (M8)

- **Undo (`Ctrl/Cmd+Z`) applies to authoring/edit operations only** (FR-016) — creating/editing/reordering content. It never "un-does" a live trigger.
- **Live changes are reverted by explicit forward actions**, not Undo: "Recall previous" re-stages the prior live item; Clear/Blackout remove output. This prevents an ambiguous "Undo just changed what's on the audience screen."
- Going live is itself a deliberate, single-key (`Enter`) confirmation of the staged preview.

## 3. Emergency reachability vs. modals (M10)

- The **Clear** and **Blackout** canonical keys (presentation-focus **and** global fallbacks) are honoured **even when a modal/dialog has focus** — emergency keys **pierce any modal**.
- **During a live service, blocking modals over the live-control chrome are prohibited.** Dialogs are non-blocking or instantly dismissible, and the **emergency controls remain visible and operable at all times** ("always-on chrome" — an on-screen Blackout and Clear affordance is never occluded).
- This "always-on emergency chrome" is a testable UI invariant (present + operable in every live state).

## 4. Canonical colour tokens (M9)

One meaning per colour across every surface (desktop and mobile). Staged and warning are **never** the same colour.

| Token | Meaning | Colour | Contrast requirement |
|---|---|---|---|
| `--preview` | Preview / staged (not on air) | **Green** `#0f7b6c` | WCAG-AA vs its background |
| `--live` | Live / Program (on air) | **Red** `#a3283a` | WCAG-AA; plus a non-colour cue (label "LIVE" + border) |
| `--warn` | Warning / threshold (e.g. timer nearing zero) | **Amber** `#9a5b00` | WCAG-AA |
| `--neutral` | Idle / inactive | Grey | — |

- **Non-colour redundancy is required** (WCAG 1.4.1): LIVE and PREVIEW always carry a text label and border, never colour alone — so colour-blind operators are never left guessing what is on air.

## 5. Seizure-safety default (M4, cross-ref FR-175/FR-059)

- The **default "TIME UP" state is solid inverted** (static high-contrast), **not** flashing.
- If an operator enables flashing, the engine **enforces WCAG 2.3.1**: ≤3 general flashes/sec **and** ≤3 red flashes/sec **and** the flashing area stays within the small-safe-area limit; the ADR-0015 flash-rate analyzer verifies all three, not just the frequency count.

## 6. Application to the other UX docs

`UX-FLOWS.md`, `UX-STATE-MATRIX.md`, and `COMPONENT-SPECS.md` each carry a header pointer to this file. Any inline keybinding, colour, or emergency-behaviour statement that conflicts with §1–§5 is **superseded** by this document; the inline text will be reconciled to match during Stage-7 UI implementation.
