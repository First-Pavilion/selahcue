# SelahCue — Consolidated QA Walk-through (owner, ~15 minutes)

Date prepared: 2026-07-24 · Covers every ClickUp item in **QA** after batches 7v–7af.
Do it in order — each step builds on the previous. Tick the box on the ClickUp item as you go.

## Setup (2 min)

```bash
cd ~/Documents/code/scph
git pull
make output       # terminal 1 — the audience + stage windows
make operator     # terminal 2 — the console
```

## 1 · Keyboard focus, WITHOUT clicking first — `86ajphu2h` (high)

With the operator window frontmost and **no prior click**: press `Space`.
- ✅ The next plan item stages (PREVIEW panel updates).
- Then `Enter` (Go Live), `B` (blackout on/off), `Esc Esc` (clear all).
- Type in the scripture box — letters must NOT trigger actions; `Cmd+Shift+B` while typing MUST still blackout.

## 2 · Plan rows — `86ajphtyh`

Look at the Service Plan panel:
- ✅ Single-line titles with ellipsis (no wrapping), kind in small text below, edit tools (✏ ↑ ↓ ✕) appear on hover, badges right-aligned.
- Tab into a row from the keyboard — the tools appear on focus too.

## 3 · Console layout — `86ajpgz4t` + `86ajpkfg7`

- ✅ Scriptures panel center; Preview/Live as compact 16:9 thumbnails on the right with GO LIVE between them; Service Timer + Outputs below.

## 4 · Scripture chapter browser — `86ajpkfcd` + KJV default

Type **"Psalm 23"** → Enter:
- ✅ The whole chapter opens as a numbered list (chip says **KJV**).
- Press ↓ ↓ — the highlight moves and the PREVIEW thumbnail follows each verse.
- Press ⏎ Enter — the highlighted verse's **text** appears on the audience window.
- `‹ ›` page chapters (try `‹` from Psalm 23 → Psalm 22).

## 5 · Five translations — `86ajpqfyj` (Track 1)

With a chapter open, switch the picker: KJV → WEB → ASV → WEBBE → DBY.
- ✅ The verse text re-renders in each translation; the highlighted verse number is preserved.

## 6 · Search with highlights — `86ajpv0ub`

Clear the box, type **"predestin"** (no Enter — wait ~½s):
- ✅ Hits appear showing reference + KJV chip + the verse text with **predestin** highlighted.
- ↓ to select a hit, Enter — its chapter opens with the verse staged.
- Type nonsense ("zzzz") + Enter — ✅ a visible "No matches" note, never a silent nothing.

## 7 · Double-click to live — `86ajpwcxc` (new)

In the verse list, **double-click** any verse:
- ✅ It goes straight to the audience output (<1s); the status line shows "… → LIVE".
- A single click still only stages.

## 8 · Timer controls — `86ajphu98`

- Type `7` in the minutes box → Enter — a 7:00 countdown starts (stage window shows it).
- Press **+1:00** — ✅ the readout jumps by a minute mid-run. **−1:00** works too.
- Hold −1:00 down to near zero — ✅ TIME UP appears (solid red, stage only).

## 9 · Scripture on the phone — `86ajpew05`

Open the mobile app (paired): type "John 3:16" in its scripture field → Stage → Go Live from the phone.
- ✅ The verse text (KJV) lands on the audience output; the phone's status strip shows LIVE John 3:16.

## 10 · Display assignment + identify — `86ajpew0c` (needs a 2nd display)

Connect a second display, relaunch `make output`:
- In the console's OUTPUTS panel, assign **Main** to the external display — ✅ the audience window goes fullscreen there.
- Assign **Stage** to the built-in. Press **Identify displays** — ✅ a "1" and a "2" appear for 5s, then the content returns untouched.
- Quit + relaunch — ✅ both windows open on their assigned displays.

## 11 · Plan editing persistence — `86ajpew01`

Rename a plan item (✏), add an item, quit the output app, relaunch:
- ✅ The edits survived.

## 12 · Crash recovery + the loop breaker — `86ajp09td`

- Go live on an item, start a timer, then `kill -9` the output process. Relaunch — ✅ identical state, "Session restored".
- Now `kill -9` it **3× within a minute** (relaunch each time quickly). On the 3rd relaunch:
  - ✅ The console prints **CRASH LOOP DETECTED … starting CLEAN** and shows the demo plan.
  - Relaunch once more (calmly) — ✅ your real session comes back untouched.
- *(Note on the story: two acceptance deltas await your call — the GUI Resume dialog and per-item disable.)*

## 13 · Design system spot-checks — `86ajp0b3d`

- PREVIEW indicators are **green**, LIVE **red**, warnings **amber** everywhere (console, stage timer, phone).
- The emergency footer (BLACKOUT / CLEAR ALL) is visible in every state — including while renaming an item.

---
**When done:** mark each verified item Complete in ClickUp (or comment what failed and I'll fix it in the next batch). Items 10's multi-display walk closes the last demo-review caveat on step 4.
