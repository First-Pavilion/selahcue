# Frame G recovery states — what shipped, and where it diverges from the frame

Companion to `docs/design/DESIGN-2.0-PARITY-AUDIT-console.md` (Frame G, node `346:124`) and
`docs/delivery/HOST-SIGNAL-WEBVIEW-CONTRACT.md`. Records the five recovery states as built, and
every place the implementation deliberately does **not** match the Figma frame.

The audit found Frame G specifies six states with five absent. G.1 (blackout) has since shipped —
`CON-101`/`CON-102` pass in `scripts/operator_headless.py`. This covers the remaining five.

## The rule every divergence obeys

> A reported problem renders as the fault. A reported-healthy value renders as healthy. An
> **absent** value renders as *unknown* — never as either of the other two.

Frame G was drawn before the host signals existed. Where it draws a value no seam produces, the
frame is asking for a fabrication — and a fabrication through a *truthful-looking* surface is
worse than the status quo, because it now looks sourced. In each case below the implementation
keeps the frame's layout, tint, geometry and intent, and changes only the claim.

## The five states, and what drives each

| State | Figma | Driven by | Notes |
|---|---|---|---|
| G.2 Control-link loss | `346:159` | `link_status` + view-poll outcome | Scoped to operator↔host |
| G.3 Output signal lost | `346:175` | `view.outputs[].signal` | Real telemetry; carries display identity |
| G.3 Held frame + recovery | `346:182`, `346:186` | `view.output_health` | Counters read as **edges** across polls |
| G.5 Session recovery | `347:147` | `view.session`, `view.storage` | A notice, not a dialog |
| G.6 Missing media | `347:165` | `deck_view` element `missing` | Operator-side; host already draws the placeholder |

## Divergence 1 — "Reconnecting… attempt 3" / "Auto-reconnecting… attempt 2 of ∞"

**Frame:** `346:165-167` a spinner and a retry counter; `346:183-185` an unbounded attempt count.

**Why not:** two separate reasons, both structural.

- For the control link, `build_backend()` runs exactly once (`selahcue-operator/src/main.rs`) and
  `AppState.backend` is an immutable field. **Nothing re-dials.** The 1 Hz poll retries a *call*
  on a dead socket, which is not reconnecting. The contract is explicit that `"reconnecting"` is
  true *exactly* when an automatic attempt is scheduled — a biconditional, not a best effort.
- `of ∞` contradicts the contract's own guarantee that retries are **bounded**, after which the
  state becomes `disconnected`.

**Shipped:** the link banner states `No automatic reconnect — restart the console to reconnect.`
The output strip states the guarantee that *is* real — FR-041's automatic reattach — and counts
nothing. No retry button is offered, because this shell has none to honour; that follows the
project's established honest-affordance pattern (a sentence, not a dead control).

## Divergence 2 — "HDMI-2 disconnected"

**Frame:** `346:182` names a specific connector.

**Why not:** `OutputHealthView` is `{held, fault, holds, recoveries}`. It carries **no display
identity**, and `fault` is a closed set — `gpu_device_lost`, `decoder_fault`, `ipc_stall`,
`disk_full` — none of which means a cable disconnect.

**Shipped:** the card names the output the host actually reports, from `outputs[].display` and
falling back to its role. Never an invented connector name.

## Divergence 3 — the red "SIGNAL LOST" framing applied to a held output

**Frame:** `346:176-181` renders the whole state in live-red as a failure.

**Why not:** the contract's wording rule — `held: true` means the audience **still sees content**.
This is the never-blank guarantee *working*, not a blank screen. "Output held (audience
unaffected)" is accurate; "output failed" is not.

**Shipped:** the two signals are separated rather than conflated, because they are different
things from different producers.

- `outputs[].signal === "no_signal"` — a display really went away. Red, `SIGNAL LOST`, as drawn.
- `output_health.held` — the live output is holding its last good frame. Its own line, worded as
  the guarantee working, and shown **only** while the host reports it.

An assigned output whose `signal` is **absent** paints nothing at all. That is the `else → NO
SIGNAL` fallthrough the contract calls the live instance of "absent treated as a fault".

## Divergence 4 — "Mobile remotes are paused"

**Frame:** `346:164`.

**Why not:** no seam reports LAN controller peers, their count, or a paused state for them. The
operator↔host link is the only network state the console can observe.

**Shipped:** the banner speaks only to the link it can see, and adds the reassurance that *is*
supported by the architecture — the host keeps presenting, because the product is
desktop-authoritative. Omitted rather than guessed.

## Divergence 5 — the crash-recovery choice dialog

**Frame:** `347:147` a modal with **Restore session** / **Start fresh**, and the body copy
"SelahCue closed unexpectedly during "Sunday Service"".

**Why not:** three independent reasons.

1. **The choice is already made.** The host restores the persisted session unconditionally at
   launch, before the console renders anything. By the time this UI could appear, the restored
   content is already on air.
2. **No command can undo it.** There is no `start_fresh` / `discard_session` in the Tauri handler
   list, and no session-recovery variant in the LAN `Command` enum. Both buttons would be inert.
3. **"Closed unexpectedly" is unbackable.** `SessionHealthView.restored` is documented as
   "crash **or** restart", and a clean exit also saves a session — so an ordinary quit-and-relaunch
   sets it. The frame's copy would assert a crash after most normal launches.

Separately, `UX-CANONICAL.md` — which is authoritative where it conflicts with the state matrix —
prohibits blocking modals over the live-control chrome during a service, and requires the
emergency controls to stay visible and operable at all times.

**Shipped:** a dismissible, non-blocking **notice** inside the console card, below the monitors
and above the GO LIVE row, so it can never obscure the emergency footer. Three cases:

- `restored` → "Session restored", with no claim about *why*.
- `crash_loop` → "Started clean after repeated restarts", with the real launch count **and** the
  fact that the previous session is *preserved, not deleted* — omitting that reads as data loss.
- `autosave_error` / `checkpoints_paused` → a chip carrying the host's own reason, and wording
  that scopes it to saving: live output is unaffected.

## Divergence 6 — the missing-media composited preview

**Frame:** `347:166-169` a preview with a dashed placeholder hole and the lyric still rendered.

**Why not:** nothing needs synthesizing. A missing image already composes to a real placeholder in
the rasterizer, which is FR-070's guarantee ("never an unintended black screen") honoured at the
only layer that can honour it. The console's job is to say *which* asset is missing and what the
audience is therefore seeing.

**Shipped:** the inspector already named the file; it now also states what the audience sees, and
warns that repairing the deck does **not** repair what is already on air — every `deck_*` repair
routes through `with_deck` and never presents, which is correct under FR-012 and precisely why the
operator must re-push.

## The connection pill

Built last, on a new read-only `link_status` command. It removes three fabrications:

| Was | Now |
|---|---|
| permanent green "Connected" in the stand-alone build | neutral **Local** — no host, and none wanted |
| "Reconnecting…" while nothing retried | **Host unreachable**, with no implication of activity |
| no way to say "not known yet" | neutral **Checking…** |

`link_status` is read-only by design: it reports the observed outcome of real traffic and does not
add a retry loop. `LinkState::Reconnecting` is therefore unreachable, which keeps the contract's
biconditional intact rather than quietly weakening it. When a re-dial loop lands, the command
grows a `reconnecting` arm and the guarantee still holds.

The pill and the link banner are refreshed from **both** the success and failure paths of the
poll. `render()` runs only when the view call succeeds — exactly the case where the link is fine —
so anything hung off it would freeze displaying "Connected" at the moment it became false.

## Reading the counters as edges

`holds` / `recoveries` are monotonic counters, absent at zero, and there is no health event
channel. A hold that begins **and** ends between two 1 Hz polls reads `held: false` in both
samples, so the recovery is invisible to any level-based reading. Only the delta against the
previous poll sees it.

Implemented as: baseline on first observation (a non-zero counter is a level, not an event);
announce only a positive delta; re-baseline unconditionally, which also covers a counter going
*down* — that means a new host or session, never a recovery. When `output_health` goes unknown the
baseline is dropped, so the next known sample cannot read as one enormous delta.

Retained state for the whole feature is four scalars and one string. No queues, no history, no
timer handles — the transient confirmation is cleared by a later poll comparing timestamps.

## Verification

`scripts/operator_headless.py` — **829 checks, 0 FAIL** (`EXPECTED_MIN_CHECKS` raised 771 → 829).

Every state ships with a negative control, because "the banner appeared" proves nothing unless
"it stays away when it should" also holds.

Mutation log — each control broken, confirmed RED with siblings running, then restored:

| Mutation | Result |
|---|---|
| Announce on every poll (edge → level) | 7 FAIL |
| Announce on any change, including a decrease | 1 FAIL |
| Absent `signal` treated as a fault | 5 FAIL |
| `local` rendered as connected | 1 FAIL |
| `[hidden]` CSS guard removed | 5 FAIL |
| Unknown health does not drop the baseline | 2 FAIL |
| Held-frame line always shown | 1 FAIL |

One finding came out of this rather than going in: the first decrease mutation survived. The
explicit decrease branch and the positive-delta test each produced the behaviour independently, so
neither could be pinned — removing either left the other, and the suite would have gone green on a
real regression. The redundant branch was removed, after which the mutation goes RED.
