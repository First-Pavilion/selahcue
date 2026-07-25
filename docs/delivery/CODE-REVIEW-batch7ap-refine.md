# Design Review — Batch 7ap refine (Operator UX: transcript + detections; queue → service plan)

- **Scope:** story `86ajpx7c0`, owner refine — a **better Operator UX** that includes a **Live transcript** + **Recent detections** (auto-detected scriptures with confidence · Add-to-plan · Preview), like Pewbeam, but as a clean, uncramped SelahCue design. Then a second owner refinement: **remove the Queue** (redundant with the Service Plan + Preview) and **restore the Service Plan**. Executed via the `/goal` engine (`TASK-86ajpx7c0-operator-ux-refine.md`, validator `--require-complete` PASS, 5/5).
- **Deliverable:** Figma frame **`161:124` "Operator Console — plan · transcript · detections (target)"** — a 4-zone layout on the "SelahCue Color" variables. The shipped-MVP frame `150:124` and the concept `4:2` are preserved.
- **Forward-looking:** the transcript (R3) + detection (R4) panels depend on post-MVP epics — this is the **target** Operator design (design leads implementation).

## The design (4 clean zones, uncramped)

| Zone | Contents |
|---|---|
| **Service Plan** (left) | the ordered service (PREVIEW/LIVE outline rows) + add-row — the running order |
| **Listen** (centre-left) | **Live transcript** (interim=grey / final=bright · "listening…" cue · legend · Pause · REC) + **Recent detections** (● 96% HIGH green / 74% MED / 61% LOW amber · verse text · **＋ Add to plan** / **▸ Preview**) |
| **Program** (centre) | Preview·Staged / Live·On-air 16:9 monitors + ◀ GO LIVE ▶ + a **Coming next** strip (from the plan) |
| **Reference** (right) | scripture browser (translation · search · ‹ chapter › · verse list) + Service timer + Outputs (Assign · Identify) |
| **Footer** | ■ BLACKOUT · ✕ CLEAR ALL · "always reachable" · hints |

## Why no Queue (owner question, answered)

The owner asked why a Queue is needed when there's a Preview. It isn't: in SelahCue's model the **Service Plan** is the ordered list of what's coming and **Preview** is the single on-deck item reviewed before GO LIVE. A detection goes to **Preview** (stage it) or into the **Plan** (running order) — a separate queue duplicates both. The Queue was a Pewbeam-ism that doesn't fit the preview→live safety model; it was **removed** and the Service Plan restored.

## Independent design review + dispositions

Reviewer verdict on the first version: **"faithfully delivers the intended better Operator UX"** — on-brand (no Pewbeam orange), uncramped, confidence mapping correct (high=green / medium=amber, not reversed). Findings (2 med + 5 low) dispositioned:

| Sev | Finding | Disposition |
|---|---|---|
| med | Transcript interim/final ambiguous, no "still-listening" cue | added a green "listening…" cue + a "Bright = final · grey = still resolving" legend |
| med | "Present" action semantics + inconsistent live-verb terminology | renamed the detection action to **Preview** (stages to preview → GO LIVE); unified helper strings on "Go Live" |
| low | No low-confidence tier; colour-only confidence | added **HIGH / MED / LOW** text labels (right-aligned, no overlap) |
| low | Duplicate BLACKOUT (header + footer) | removed the header copy — the footer is the single emergency surface |
| low | Amber Pause (pause isn't a warning) | neutralized to muted; REC given a label |
| low | Preview/Live not exactly 16:9; Outputs status colour-only | monitors are 16:9 surfaces; added an "active" text status to Outputs |

## Verification

- get_screenshot of `161:124` (and the intermediate versions) — 4 uncramped zones, all panels present, no queue, Service Plan restored, tokens bound (preview green / live red / warn amber).
- Goal Contract `--require-complete` PASS.

## Layout v2 — owner reorg (OBS studio mode), final frame `165:124`

The owner then directed a smoother arrangement, delivered as frame **`165:124` "Operator Console — OBS studio (target)"** (1760 wide):

1. **Live transcript + Recent detections moved to the RIGHT** column (with the Service timer in the bottom-right corner).
2. **PROGRAM is OBS studio-mode**: Preview | Live arranged **horizontally** (side by side), with the **GO LIVE** transition ("Preview → Program") spanning below.
3. **Scriptures sit directly below PROGRAM** (centre column), with the **Outputs** strip beneath.
4. **Service timer in the bottom-right corner.**

Final zones: **LEFT** Service Plan · **CENTER** OBS Preview|Live + GO LIVE → Scriptures → Outputs · **RIGHT** Live transcript → Recent detections → Service timer · always-on emergency footer. All fills remain bound to the "SelahCue Color" variables; the transcript/detections review fixes (listening cue, HIGH/MED/LOW labels, Preview verb, neutral Pause, no duplicate BLACKOUT) carry over. This is the current target frame; `161:124` and the earlier versions were superseded within this refine.

## Handoff

- Node `165:124` is the **target** Operator console; `150:124` is the current shipped MVP; `4:2` the old concept.
- No repository code changed. The transcript/detection panels are a design target for the R3 (Transcription) + R4 (Scripture Intelligence) epics — recommend linking this frame from those epics when they're planned.
