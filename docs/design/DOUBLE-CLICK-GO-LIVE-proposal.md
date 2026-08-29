# Double-click to go live — interaction design **proposal**

**Status: PROPOSAL. Not a spec, and not an approved requirement.**
**For:** Priya (Product) to ratify into an FR · **From:** Uma (UI/UX) · **Date:** 2026-08-28
**Raised by:** OQ-8, answered by the owner — *keep the staging invariant **and** add a double-click accelerator*.
**Lands on:** the slide grid specified in `SLIDE-VIEW-DENSITY-spec.md` (UI-B1, [`86ak7kgjk`](https://app.clickup.com/t/86ak7kgjk)), and on three other surfaces.
**Blocks nothing.** UI-B1 ships without it. This document exists because the accelerator has no FR, and because designing it turned up something that needs a product and an architecture decision rather than a design one.

---

## 1. Why this document is longer than "double-click goes live"

Two things came out of reading the shipped console that change the shape of the question the owner asked.

1. **The accelerator already ships.** Not as a plan, not as a stub — as working behaviour, in **three** places, built **three different ways**, with three different safety properties and no documentation. The owner approved a feature that is already partly live and inconsistent. §2.
2. **The hard constraint placed on this proposal — "it must compose `Presenter::stage()` then `go_live()`, never a direct-to-live path" — cannot be met for deck slides**, and the reason is architectural, not sloppiness. §4.

Neither is a reason to stop. Both are reasons the FR should be written deliberately rather than assumed.

---

## 2. What ships today (Verified — read from the working tree, 2026-08-28)

| # | Surface | Handler | Mechanism | Verifies the commit? | Guarded against a racing stage? |
|---|---|---|---|---|---|
| **V1** | Scripture verse list | `app.js:3583` | `stage_scripture` → **check `staged_scripture === ref`** → `go_live` → **check `live_scripture === ref`** | **Yes, both sides** | **Yes** — `dblclickBusy` blocks the 120ms debounced stage (`app.js:3527`, `:3543`) |
| **V2** | Console Slides tab, slide card | `app.js:4917` → `stageSlide(i, true)` (`app.js:4776`) | `present_plan_deck_slide` → `Command::PresentAuthoredSlide` → `Presenter::present_authored()` (`present.rs:229`) — **writes straight to Live via `apply_live`, never touches `staged`** | **No** | **No** |
| **V3** | Presentations Library slide grid | `app.js:7504` → `pmGridGoLive()` (`app.js:7418`) | `deck_select_slide` (a *selection*, not a stage) → `deck_go_live` → re-read host truth | Partly — re-syncs the LIVE ring from `view().live_authored_id` afterwards | **No** |

V1 was built to an explicit owner request (`86ajpwcxc`) and its comments record the review that hardened it: *"a denied stage must never commit whatever was in Preview before"*. It is the exemplar. V2 and V3 predate that thinking and were never brought up to it.

Discoverability is also uneven: only V3 tells the operator the gesture exists — the static hint *"Double-click a slide to present it live."* (`index.html:936`). V1 and V2 are undocumented in the UI.

**The practical consequence.** An operator who learns the gesture on one surface gets different failure behaviour on the next. On V1 a failed commit says so. On V2 a failed commit says nothing, because nothing checks.

---

## 3. The four questions, answered

### 3.1 Which surfaces?

**Rule: the gesture belongs to atomic, visible, single-frame units — never to containers.**

| Surface | Verdict | Reasoning |
|---|---|---|
| **Slide grid** — console Slides tab **and** Presentations Library | **Yes** | The unit is one frame, it is visible, the operator is looking straight at what they are committing. This is the case the owner asked for. |
| **Scripture verse list** | **Yes — already ships (V1), keep it** | Same property: an atomic, visible unit. |
| **Plan rows** | **No** | A plan row is a *container* — a deck, a song, an announcement. Double-click on a row means "open this" in every list UI an operator has ever used, and that is also the more common intent here: you still have to choose a slide. The accident cost is the whole wrong item on the audience screen mid-service; the speed gain is nil. **Propose: plan-row double-click opens/expands the item.** |
| **Library cards** (presentations, not slides) | **No** | Same: a card is a container. Double-click opens the deck. |
| **Search results** | **No** | Results are references to containers, and the operator's certainty about *which* result they hit is lowest here of anywhere. |

### 3.2 Already-live slide — re-fire or no-op?

**Re-fire, unconditionally — with one hard exception.**

Do not special-case it. An operator double-clicking the slide that is already live is usually asking "did that land?", and a silent no-op leaves them less certain than before. A re-fire of identical content produces an identical frame, so the audience sees nothing; and after a **Clear**, the same slide genuinely does need re-firing, which a no-op would break. The feedback differs even though the action does not: announce **"Already live"** rather than "Sent live", so the operator learns that nothing moved.

**The exception — never commit while the output is blacked out.** `Command::PresentAuthoredSlide` sets `blackout = false` in the controller (`controller.rs:2306`), and `GoLive` does the same. So under today's behaviour a double-click during a blackout *brings the audience back*. For a deliberate `⏎` that is arguably right. For a pointer gesture whose whole purpose is speed, it is a trap: the operator double-clicks to check something and the congregation sees the screen light up.

**Propose:** while blackout is active the accelerator **stages only** and shows *"Staged — output is blacked out. Press B to restore."* `⏎` keeps its current behaviour. This asymmetry between the two paths is deliberate and is one of the things Priya should confirm (§7).

### 3.3 The misclick window

Three rules, each independently testable.

1. **The commit target is the item identity captured on the *first* click of the pair.** If the second click resolves to a different item, the gesture is abandoned: selection and staging move to the second item, nothing commits.
2. **Do not rely on the browser's `dblclick` dispatch to enforce that.** Where the two clicks land on different children, which element receives `dblclick` is *assumed* to be a common ancestor — that is a platform detail and it is not verified here. Bind the handler **per item**; if a delegated handler is ever used instead, compare the two ids explicitly. The rule must hold because the code enforces it, not because a browser happens to.
3. **Never commit content that Preview does not currently show.** Stage, read back, and only commit if the read-back is the item you meant — then read back again and only claim "live" if the output confirms it. V1 already does exactly this (`app.js:3596-3607`); generalise it. And generalise V1's `dblclickBusy` guard so a debounced or in-flight stage from a neighbouring interaction cannot land between the two halves.

### 3.4 Opt-out

**Yes — and it is an accessibility feature, not only a preference.** Double-click is a motor-control demand; some operators cannot produce one reliably, and some will produce one accidentally.

- **Setting:** Settings → Console → **"Double-click sends a slide live"**, per host, stored in the settings table.
- **Default: On.** It already ships on. Defaulting off would silently remove behaviour operators depend on today.
- **Off** leaves `⏎` Go Live and the GO LIVE button, which are and remain the primary paths.
- **Surface it where the nervous volunteer will actually see it** — a line in the pre-service check, not only buried in Settings. The owner's framing was right: a nervous volunteer and a fast producer want opposite defaults, so the answer is not a cleverer default, it is a setting they each meet early.
- *Optional third value, if the owner wants it:* **Confirm** — double-click stages and arms GO LIVE for 3 s; a second double-click or `⏎` commits. It genuinely serves the nervous volunteer better than Off. It is more to build and more to explain, so it is offered rather than proposed.

---

## 4. The constraint that does not hold literally — and what to put in its place

The brief on this proposal said: *it must compose the existing `Presenter::stage()` then `go_live()` — never a direct-to-live path that bypasses staging.*

**For scripture, that is exactly right and V1 already does it.**

**For deck slides, it is not achievable as stated**, for a structural reason:

- `Presenter::go_live()` (`present.rs:186`) commits `self.staged`. For a plan deck item, what the host has staged is the plan item's **title**, not deck pixels — *"the host has no deck pixels"* (`app.js:4778-4781`). Decks are operator-owned; the host has no deck store (`86ajy02zq`).
- Routing an actual deck slide to Live therefore goes through `Command::PresentAuthoredSlide` → `Presenter::present_authored()` (`present.rs:229`), which calls `apply_live` directly and never populates `staged`.
- So `go_live()` on a deck slide would put the item *title* on the audience screen. Composing `stage()` then `go_live()` for a deck slide is not merely awkward; it produces the wrong output.

**Proposed restatement — the invariant as a property, not as a call sequence.** This is what the FR should assert, and what QA should test:

> **P1.** Nothing reaches the Live output except through an explicit operator commit gesture — `⏎`, the GO LIVE button, or the double-click accelerator.
> **P2.** Before any commit, Preview shows the exact content that is about to be committed, and the commit is issued against the identity the console has read back from Preview.
> **P3.** After any commit, the console verifies from host truth what actually reached the output, and reports honestly if it differs. "Live" is never claimed, only confirmed.
> **P4.** Every commit path authorises identically — `Permission::GoLive` — with no escalation and no alternate route.
> **P5.** Selecting, staging, browsing, resizing and re-viewing change Live never.

`stage()` → `go_live()` is one *implementation* of P1–P3 and remains correct for scripture and for plan items. `select_slide` → verify → `PresentAuthoredSlide` → verify is the deck-slide implementation of the same properties. Both satisfy the invariant; only one satisfies the literal wording.

**This needs Priya (how the requirement is written) and Aria (whether the two-door model is the intended long-term shape).** It is not a design workaround and I have not treated it as one.

---

## 5. Proposed unified behaviour

One shared handler, used by all four permitted targets (console slide card, library slide tile, scripture verse; plus whatever future atomic unit qualifies).

```
on double-click of item X:
  if setting "double-click sends live" is off        → treat as a single click (select + stage). stop.
  if X.id != id captured on the first click of pair  → abandon. select + stage X only. stop.
  if operator lacks Permission::GoLive               → select + stage X. announce "Staged — you do not have
                                                        permission to send content live." stop.
  cancel any armed/debounced stage; take the commit lock

  stage X                                             (select_slide / stage_scripture)
  read back                                           → if Preview is not X: announce
                                                        "Could not stage <X> — nothing was sent live." release. stop.

  if blackout is active                               → announce "Staged — output is blacked out.
                                                        Press B to restore." release. stop.

  commit X                                            (PresentAuthoredSlide for a deck slide; go_live otherwise)
  read back host truth                                → if Live is X and X was already live: "Already live."
                                                        if Live is X:                        "<X> → LIVE"
                                                        otherwise:                           "Go Live did not commit <X>."
  release the commit lock                             (in a finally — a thrown error must never strand it)
```

**Feedback.** Every branch above ends in a message. The gesture is fast and silent by nature; if it fails silently the operator will double-click again, and the second attempt is the one that goes wrong. Messages go to the existing per-panel `role="status"` region — the same place V1 already writes.

**Timing.** The pair must complete inside the OS double-click interval; do not invent a custom threshold, and do not lengthen it — a long window is what makes two deliberate single clicks read as one accelerator.

---

## 6. Permissions and accessibility

**Permissions — no change, and deliberately no new command.** `required_permission()` already maps `GoLive | FollowScripture | PresentAuthoredSlide → Permission::GoLive` (`rbac.rs:104-109`), with the no-escalation reasoning from `86ajtwq2b` written into the comment. The accelerator introduces no new command and therefore no new permission surface. A role without `GoLive` gets a stage and an explanation — never a silent no-op, which reads as a broken app rather than as a denied action. Mobile is 4 roles today; nothing here assumes 7.

**Accessibility — additive, never exclusive.**

- `⏎` Go Live remains the keyboard path and the primary route. The accelerator is pointer-only, so if it were ever the *only* way to reach something, that thing would be unreachable for keyboard and AT users. Nothing may be reachable only this way.
- The opt-out (§3.4) is the accommodation for operators who cannot reliably produce or reliably avoid a double-click.
- Discoverability must be evened out: today only the library grid carries the hint. Whatever form it takes, the affordance should be stated once per surface, in text, and be reachable by a screen reader — not left as folklore.
- Every outcome is announced politely through the existing status region. No outcome is conveyed by motion or colour alone.

---

## 7. What Priya needs to decide

1. **Ratify an FR** for the accelerator — it has none, and three shipped implementations are currently unattributed to any requirement. Suggested placement: EPIC-UI-B, as **FR-224**, MVP.
2. **Confirm the surface list** (§3.1) — in particular that **plan rows and library cards are excluded**, and that double-click there means *open*.
3. **Confirm the blackout exception** (§3.2) — the accelerator refuses to commit while blacked out, while `⏎` keeps today's un-blackout behaviour. This is a deliberate asymmetry between two commit paths and it should be a decision, not a side effect.
4. **Confirm the opt-out default is On**, and whether the third **Confirm** value is wanted.
5. **Route §4 to Aria** — the restatement of the invariant as properties P1–P5, and the two-door Live model (`go_live` for host content, `PresentAuthoredSlide` for operator-owned deck pixels) that makes the literal wording unachievable.
6. **Decide whether bringing V2 and V3 up to V1's safety properties is remediation or new work.** V2 in particular commits without verifying either side, which is the specific failure V1's review was written to prevent. My recommendation: a separate engineering ticket, sized honestly, not folded into UI-B1 — UI-B1 is design-only and this is a behavioural fix to shipped code.

---

## 8. Acceptance criteria, drafted for the FR

Offered so Priya has something concrete to edit rather than to write from scratch. Not binding until ratified.

- Double-clicking a slide in the console Slides tab or the Presentations Library grid, or a verse in the scripture list, puts **that** unit on the audience output, and the console confirms from host truth that it arrived.
- Double-clicking a plan row or a library card **opens** it and never changes the audience output.
- A double-click whose two halves land on different items commits **nothing**.
- A double-click whose stage does not read back as the intended item commits **nothing**, and says so.
- While blackout is active, a double-click stages and does not commit; the audience stays black.
- With the setting off, a double-click behaves as a single click.
- An operator lacking `Permission::GoLive` gets a stage and a stated reason; the audience output is unchanged.
- The accelerator adds no new wire command and no new permission (verified against `rbac.rs`).
- Every path is reachable without a pointer: `⏎` Go Live continues to commit the staged unit.
- Verified through the ADR-0015 fault-injection / pixel-readback seam, not by visual inspection.
