# Operator Console — Right Panel: Timer / Detected Scriptures tabs (Design 2.0)

**For:** frontend-engineer (operator webview, `crates/selahcue-operator/dist/`)
**Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ` → frame **`SPEC — Right Panel Tabs: Timer / Detected Scriptures (Design 2.0)`** (node `430:124`) — Detected tab `431:124`, Timer tab `434:124`, notes `435:124`.
**Console being changed:** frame `312:124`, right column `320:201` (Timer `323:124` + Detected Scriptures `323:151`, currently stacked).

## Problem

The right column stacks Service Timer (~437px) over Detected Scriptures (~397px), so only ~2 detection cards fit and scriptures scroll out of view as they arrive.

## Change

Make the right column **one panel with a 2-tab header** — **Service Timer** · **Detected Scriptures** (with an unactioned-count badge). Each tab owns the full column height (~848px), so **≥3 detection cards** are visible at once. No new host data; both tabs reuse the existing DOM/JS hooks (`#timer*`, `#detections*`) — only the container becomes tabbed.

## Tabs

- Header row, 2 tabs. Active = white label + 2px primary (`#6e5cf0`) underline; inactive = muted (`#6b7383`). 1px bottom border under the whole header (`#262a34`).
- **Detected Scriptures** tab carries a count pill (unactioned detections) in soft-primary.
- Default tab: Service Timer. **Optional nicety:** auto-switch to Detected Scriptures when a *new* detection arrives and the operator isn't mid-timer-edit; always reflect the count badge.

## Detected Scriptures tab

- A scrollable list; **≥3 cards visible**, list scrolls beyond (keep the existing client cap).
- **Newest detection on top** (reverse of today's oldest-first) — see repo change #3.
- Card: `Reference · Translation`, match-% pill (**green ≥90**, **amber/gold** `#f2b84b` when fuzzy), snippet (`textContent`, untrusted), source + "spoken Ns ago", then **Stage** (primary) / **Approve** / **Dismiss**.
- Staging stays operator-confirmed (FR-115); nothing auto-goes-live.

## Service Timer tab

- The existing timer, unchanged, moved behind the tab: big readout, RUNNING pill, SET A CUSTOM TIME, presets (5:00/10:00, −1:00/+1:00), Pause/Reset/Stop, "shown on the stage output only".

## Accessibility

- Real tablist: `role="tablist"` / `tab` / `tabpanel`, `aria-selected`, roving `tabindex`, ←/→ to switch, `aria-controls` linking tab→panel.
- Count badge announced ("Detected Scriptures, 3 new"). New-detection announcements stay polite (no focus steal while approving). Match-% is text, not colour-only. All text ≥ AA on `#14161d`.

## Tokens

surface `#14161d` · card `#1c1f28` · border `#262a34` · primary `#6e5cf0` (active tab + Stage) · ok `#35c08a` (≥90 / RUNNING) · gold `#f2b84b` (fuzzy match) · text `#f4f6fb` / `#6b7383`. Inter.
