# Host signal inventory — what the operator webview can honestly render

Status: **verified against committed code, 2026-08-23.** Every row was checked by reading the
source, not inferred from docs. Written while building the Design 2.0 "missing states", when it
emerged that most designed recovery states have no backing data.

> **Why this exists.** The owner's acceptance bar for the detection/recovery states is: *"a dead
> scripture detector and a silent room must not render identically."* Meeting it honestly requires
> knowing which signals exist. Several designed states imply data no channel carries — rendering
> them would mean **inventing** system health, which is the precise failure the bar names.

## The three channels

1. `invoke("view")` → `OperatorView` (`selahcue-app/src/operator.rs:62-114`), polled every 1000 ms.
2. Ad-hoc per-surface Tauri commands (`deck_view`, `remote_snapshot`, `disk_free`, `host_connected`, …).
3. Four Tauri events: `stt://progress`, `stt://level`, `stt://phase`, `bible://phase`.
   **There is no system/health/recovery event channel of any kind.**

The wire equivalent is `OperatorStateView` (`selahcue-lan/src/protocol.rs:606-694`). It carries **no**
health, recovery, session, disk, crash, fault or connection field.

## Buildable honestly TODAY

| Signal | Anchor |
|---|---|
| Output signal health — healthy / degraded / no_signal / closed / **unknown** | `protocol.rs:913-917`; `desktop/main.rs:821-833` |
| `fps`, `dropped_frames` (measured) | `protocol.rs:900-911` |
| Media asset missing — per-asset, per-element, count (open deck only) | `deck_workspace.rs:800, 817, 1043` |
| Deck-link missing on a plan item (client-side join against `deck_list`) | `app.js:5612-5624, 5636-5658` |
| Blackout (one bool, **live output only** — preview is genuinely unaffected) | `operator.rs:69`; `present.rs:406-410` |
| Console empty plan — `view.items.length === 0` | `app.js:57-61` — **pure UI gap, never written** |
| Detection: *not listening* vs *listening, nothing yet* | `sttState` + `partial_transcript` |

## NOT buildable — no backing signal, would be fabrication

| Signal | Why |
|---|---|
| Retry attempt count / reconnect progress | **Nothing reconnects** — see defect 1 |
| Successful reconnect event | No edge signal anywhere; `signal` is a level, not a transition |
| Display **disconnected** as a distinct event | Only `signal=="no_signal"`, re-sampled on Moved/Resized |
| Output **holding last frame** (NFR-024) | `EngineEvent::OutputHeld`/`Recovered`/`is_faulted` — **zero consumers** outside `selahcue-engine`; `present.rs` discards every returned event |
| Auto-reconnect attempt number | Deliberately absent — `desktop/main.rs:266-271`: retry is *"the operator's gesture, never a loop"* |
| Autosave / crash recovery / unclean shutdown / dirty | Real and substantial **host-side** (`guard.rs`, `session_repo.rs`) — reported by `eprintln!`/`println!` only. No path to the webview. |
| Disk low/critical verdict | `DiskStatus` exists (`guard.rs:65-75`); operator has only raw `disk_free` |
| Media **relink** a moved file | Label only. No `relink_media` command; "Relink…" swaps a *different* library asset |
| Per-plan-item **media** link missing | `ContentLinkView` has no `missing` field; `plan.rs:419-442` `unresolved_content` is **never called** |
| Detector liveness / provider unavailable | No detector/provider/liveness field in `protocol.rs`. `is_listening()` (`listening.rs:195`) has **zero callers** |
| Detection cooldown | `cooldown` appears **0 times** in the workspace |
| Detection alternatives | Matcher computes candidates then discards all but one — `quote_match.rs:320-334` |
| Detection history / on-air record | `approve()` **removes** the detection — `detection.rs:326-330` |

## Live defects found by this survey

**1. "Reconnecting…" is a fabrication.** `build_backend()` (`operator/src/main.rs:2241`) is called
**exactly once**, at Tauri setup (`:2702`). `ControlClient::request` writes to a dead socket and
returns `Err` forever. There is no reconnect loop, no backoff, no re-dial. The pill's only input is
whether `invoke("view")` threw. **Nothing is retrying**, so the label states something untrue.

**2. An unknown is rendered as a fault.** `statusPillFor` (`app.js:858-863`) ends
`else { variant = "warning"; label = "NO SIGNAL"; }` — so absent telemetry (`signal === None`, e.g.
`Backend::Local`, or a host that hasn't reported yet) displays as a hard fault. The footer ~350
lines later handles the identical case honestly: `"Signal — · awaiting host telemetry"`, under the
comment *"Honest signal-health footer (telemetry — never fabricated)"*. Same file, same data, two
treatments.

**3. In `Backend::Local` the pill reads a green "Connected" permanently**, because `view()` can
never fail there (`main.rs:75-78`). The real signal exists (`host_connected` `main.rs:884-886`,
`output_connected` `:1888-1890`) and is **not wired to the pill**.

**4. A comment claims a missingness signal that isn't one.** `app.js:6836-6840` says
`// missing media / no frame → honest "can't preview" tile`. But `render_deck_slide`
(`operator/src/main.rs:1750-1770`) returns `"available": true` in **both** arms, and a slide with
missing media still renders — the compositor draws the FR-070 placeholder. `pmThumbFail` fires only
when there is no slide/frame at all, never because media is missing.

## The seam that unblocks the most

`TranscriptProvider::label()` (`core/src/transcript.rs:150`) exists as the FR-120 honest-disclosure
hook and is not surfaced. A **liveness/error field on `OperatorStateView`** plus a `retry_detection`
command would unblock the detection-unavailable (blocker) and listening states properly. That is the
smallest change with the largest honest-UI payoff.
