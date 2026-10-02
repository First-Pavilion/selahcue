# Notification bell and panel — Design Spec

**Status:** implemented with this spec (Figma frames not built — drawn from this spec and the shipped `--sc-*` tokens) · **Owner:** Uma (design), Farah (implementer)
**Sources:** owner request, in his words — the system messages ("Host link lost", "Monitor #41057 DEGRADED") "should not take up space… design a dashboard-like notification panel where these messages go… I just click on a bell icon and the panel shows up. It's simple and straightforward." · `UX-CANONICAL.md` §3, §5 · `UX-STATE-MATRIX.md` invariant 2 · `HOST-SIGNAL-INVENTORY.md` · `FRAME-G-RECOVERY-STATES-divergences.md` · shipped `dist/index.html` / `app.css` / `app.js`.

## 1. What changes

The four Frame G cards (session notice, host link lost, output signal / held, recovered) sat in the console's flow above the GO LIVE row, so every active message pushed the whole console down. They now live in a **bell panel**. Nothing else changes: ids, producers, *when* a card shows and every word on it are as shipped.

## 2. Placement

- **Bell** `#notif-bell` in the top bar, between the clock and the connection pill. A `.tb-btn`-family button, 40×40, inline SVG (no emoji, no asset).
- **Panel** `#notif-panel`: `position: fixed`, non-modal (`role="dialog"`, `aria-modal="false"`), no scrim, no focus trap. It is **out of flow, so opening or closing it moves nothing** — measured by the gate on the header, the zones, the monitors, the GO LIVE row and the footer.
- Right-aligned to the header's 20px padding, top just under the header, at most `min(400px, 100vw − 24px)` wide, internal scroll for the card list. `app.js` measures on open, on resize and on a surface change (never assumes):
  - **bottom stops 12px above `#emergency`** — BLACKOUT and CLEAR ALL are never covered;
  - **left edge stays 8px right of Previous / GO LIVE / Next** while the console is showing (on the console this lands the panel on the right-hand column, ~384px); if the window is too narrow for that (the console's own columns collapse under ~1100px, far below the 1400×900 product minimum) the panel starts *under* those controls instead.
- **Top bar must still fit.** The bell adds 52px to a bar that had ~1px of slack at the 900px CSS floor (and none once the timer chip shows — it already overflowed there). Below 1100px the bar compacts: tighter padding and gaps, one-line control labels, the surface name gives way behind an ellipsis (the only part that shrinks), the connection pill's text is bounded at 110px, the clock is dropped at ≤1000px. The gate pins "no sideways scroll, no overlap" at 900, 1280 and 1440 in the widest state, including under a ~6% wider face (WebKit's wider default face is what the first CI run tripped on).
- `z-index: 70`: above the console, the app menu and the fullscreen output preview; below the command palette and dialogs. Opening the app menu closes it and vice versa.

## 3. Severity → bell, and the states

The badge is a **live computed read** of the cards visible right now (`rcvRegionSync()` runs after every producer) — never a latched event; a condition that clears clears it on the next poll. Fault cards (warn / live) are counted; info cards are a number-less dot.

| Card | Rank |
|---|---|
| Host link lost | warn (amber) |
| Output DEGRADED | warn |
| Output SIGNAL LOST, OUTPUT HELD (the live output cannot update) | live (red) |
| Session notice, Recovered | info (sky dot, no number) |

| State | Badge | `aria-label` | Panel |
|---|---|---|---|
| All clear | none; bell muted | `Notifications: all clear` | "All clear" + the true line (§6) |
| Info only | sky dot, no number | `Notifications: 1 notice` | the info card(s) |
| Warn | amber `N` (cap `9+`) | `Notifications: 2 active` | the cards |
| Critical | red `!N`, light ring | `Notifications: 1 active, 1 critical` | the cards |
| Many | worst severity wins; number counts faults only | `Notifications: 2 active, 1 critical, 1 notice` | the cards, list scrolls inside the panel |

Colour is never the only signal: the number is text, red adds a `!` and a ring, and the `aria-label` says it in words. No animation or transition anywhere in the block (seizure-safety default; `prefers-reduced-motion` has nothing left to honour).

## 4. Keyboard and focus

Click, Enter or Space on the bell toggles. Opening moves focus to the panel container (`tabindex="-1"`); Tab then walks the panel's real controls (close, then the session notice's dismiss) and carries on into the console. **Esc** closes it and returns focus to the bell; a click outside closes it (focus stays where the click put it). The panel adds **no new global shortcut**.

With focus *inside* the panel, Enter / Space / arrows do not fall through to GO LIVE / Next / Previous. Everything else is untouched: the emergency chords (Ctrl/Cmd+Shift+B, Ctrl/Cmd+Shift+.), plain `B` and Backspace work with the panel open.

**Esc and CLEAR ALL.** The console's double-Esc is CLEAR ALL (1000 ms window). While the panel is open the first Esc is consumed by it **and disarms any pending window**: Esc, Esc sends no clear (the second is a fresh first tap), and an Esc armed *before* the panel opened is cancelled too. A clean Esc, Esc with the panel closed still clears. Three Escs inside a second still clear, as ever: panel, tap, tap.

## 5. Screen readers

Cards inside a closed panel do not announce, so one always-present visually-hidden live region `#notif-live` speaks `Notification: <card title>` when a card **becomes** visible while the panel is closed — edge-detected against the previous poll, not on every 1 Hz poll; assertive for a new red card (including amber → red on a card already showing), polite otherwise; nothing when a card goes away or while the panel is open (the cards' own `status` / `alert` roles speak). Retained state: one rank per card id, no history.

## 6. Honest by construction, and what is not shown

The empty state says only what is true. "The host link and outputs are reporting normally" appears **only** when the link is up *and* every assigned output reports a healthy signal. A Local backend says "No host link to report — this console runs stand-alone"; absent telemetry says "Awaiting host telemetry" or "Output status is not being reported". An unknown is never "healthy" (`HOST-SIGNAL-INVENTORY.md`). "All clear" means *no active notification*, never *healthy*.

Deliberately **not** shown, because no signal backs them: mobile-remote status (no seam reports LAN controllers), reconnect progress or retry counts (nothing reconnects), detector or provider health (no field), disk-low verdicts (only raw `disk_free`), autosave events beyond `view.session` / `view.storage`, and any history of resolved items.

## 7. Known limits (pre-existing, not introduced here)

Below ~1100px wide the console's columns overlap (the GO LIVE centre already hits the Service Timer on the untouched baseline), and below ~640px tall the transcript panel overflows the emergency footer. Both are far outside the 1400×900 minimum; the gate therefore asserts "opening the panel changes nothing about what sits at those points" at 900px, and "the control itself" at 1440 and 1280.

## 8. Decisions left to the owner

1. **Toast for a new critical?** Should a NEW red card also raise a transient toast, so a sighted operator with the panel closed sees more than a badge change? (Not built: a toast is a second, time-limited surface over live chrome.)
2. **A shortcut for the bell?** None added, to keep the keymap contract (`selahcue_app::keymap` + its JS mirror) unchanged.
3. **Short history of resolved items?** Not kept: the badge is a live read and memory is bounded. A short, capped "resolved" list would need an owner call on its size and lifetime.
4. **Grade of the session notice?** "Started clean after repeated restarts" and "Your recent work may not be saved" are info-styled today, so they never take a number. Should either count as a warning?
