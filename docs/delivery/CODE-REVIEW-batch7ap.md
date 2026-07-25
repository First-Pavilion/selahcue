# Design Review — Batch 7ap (Figma operator-console refresh)

- **Scope:** story `86ajpx7c0` remaining half — bring the Figma operator-console frame current with the SHIPPED desktop console (`crates/selahcue-operator/dist/index.html`). The mobile-screen half shipped in 7ak/7al. Executed via the `/goal` engine (`TASK-86ajpx7c0-console-refresh.md`, validator `--require-complete` PASS, 5/5).
- **What was built:** a new Figma frame **`150:124` "Operator Console — shipped (86ajpx7c0)"** reproducing the shipped 3-column console, fills bound to the "SelahCue Color" variables. The original concept frame `4:2` is preserved for history.
- **Method:** independent design-consistency review — a reviewer agent compared the built frame (`get_screenshot`/`get_metadata`) against the shipped `index.html` (source of truth). No self-approval.

## The refresh (concept → shipped)

The old `4:2` was the pre-shipping concept: Preview/Live 2-up in the center, a **LIVE-TRANSCRIPT** band and a scripture **auto-detection/confidence/approve** band (both R3/R4, not in the MVP), a "Cloud OFF" chip. The shipped console is a simpler 3-column MVP layout:

| Column | Shipped panels (now in the frame) |
|---|---|
| Header | plan name · ● LIVE chip · clock |
| Left | Service plan (list with PREVIEW/LIVE outline rows) + add-row (kind · title · Add) |
| **Center** | **Scriptures** — translation picker · search · ‹ chapter › nav · numbered verse list with the cursor verse highlighted (green), amber verse numbers |
| Right | PREVIEW·STAGED 16:9 → ◀ GO LIVE ▶ → ●LIVE·ON AIR 16:9 → Service timer → Outputs → Identify |
| Footer | ■ BLACKOUT · ✕ CLEAR ALL · "always reachable" · key hints |

The **R3/R4 concept bands were deliberately dropped** (transcript, auto-detection) — they are not in the shipped MVP.

## Review findings and dispositions

Verdict: **structurally faithful — all panels present in the correct columns, post-MVP bands correctly absent, no high-severity issues.** 3 medium divergences fixed:

| # | Sev | Divergence | Fix |
|---|-----|------------|-----|
| A | med | BLACKOUT rendered light in its resting state — the shipped off-state is a **dark** panel button (only red when active) | re-styled BLACKOUT to a dark `bg/base` button with light text + border |
| B | med | Timer controls crammed into one row — shipped lays them across **3 rows** | rebuilt: presets · minutes+Start · −1:00/+1:00/Stop + "shown on the stage output only" note |
| C | med | Outputs showed labels the app never emits ("Main projector"/"Livestream") and no assignment picker | rebuilt with the shipped role labels (**Main output** / **Stage display**) + per-row **Assign** picker + full-width **Identify displays** |

LOW items (enriched plan-row subtitles, preview/live big-line = title nuance, header sub "· Producer") accepted as reference-design latitude — the shipped **code** is the authoritative source for exact content/interaction states; this frame captures the IA + panels + controls + canonical colours faithfully.

## Verification

- `get_screenshot` of `150:124` (before + after the fixes) vs the shipped console — 3-column IA, scriptures centered, 16:9 preview/live, timer, outputs, emergency footer all match.
- Every panel/chip fill bound to a "SelahCue Color" variable (no forked hex); preview=green, live=red, verse numbers amber.

## Handoff

- Node `150:124` is the current console design; `4:2` is the superseded concept (owner may archive).
- No repository code changed (Figma is the artifact). Story `86ajpx7c0` — both halves (mobile + console) now done → QA (owner reviews the Figma).
