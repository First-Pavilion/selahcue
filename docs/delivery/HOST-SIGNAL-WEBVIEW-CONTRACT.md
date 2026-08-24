# Host signal seams — webview consumer contract

For the operator webview (`selahcue-operator/dist/`). Names, shapes, meanings and traps for the
health seams landed under ClickUp `86ak4xxwm`. Source of truth is the code; this is the contract
it guarantees.

Background: `docs/design/HOST-SIGNAL-INVENTORY.md`. Owner's acceptance bar: **a dead scripture
detector and a silent room must not render identically.**

---

## Read this first — absent means UNKNOWN, never a fault

Every seam here is **tri-state**. There are always three cases, and conflating any two of them
recreates the bug this work exists to remove:

| Case | Looks like | Render as |
|---|---|---|
| The host reports a problem | field present, value says so | the fault / degraded state |
| The host reports it is fine | field present, value says so | healthy |
| **The host does not report at all** | `null` (Tauri) or key absent (wire) | **unknown** — "awaiting host telemetry" |

The third case is **not** a fault. It means an older host, a peer with no compositor, or a
subsystem this build does not have. `statusPillFor` currently ends `else → "NO SIGNAL"`, which
turns exactly this case into a hard failure — while the footer ~350 lines away handles the same
data honestly under a comment reading *"never fabricated"*. That fallthrough is the bug; do not
carry its shape into the new fields.

A reported-healthy value and an absent value must **never** produce the same UI. If they do, an
operator cannot tell a working subsystem from one nobody is asking about.

Two encodings of absent, same meaning:

- **Tauri path** (`invoke("view")` → `OperatorView`): absent is JSON `null`. The key is present.
- **Wire path** (`OperatorStateView`, remote console): absent is the **key missing entirely**
  (`skip_serializing_if`). Use `?? null`-style access, never `"key" in obj`.

---

## Tier 1a — detector liveness

**Shipped.** Two Tauri commands, registered in both build configurations.

### `invoke("detection_health")` → object, never throws

```jsonc
{
  "state": "unsupported" | "idle" | "listening" | "unavailable",
  "provider": string | null,   // e.g. "whisper-small"; null when nothing is listening
  "error":    string | null,   // the retained terminal failure; null unless state is "unavailable"
  "can_retry": boolean
}
```

All four keys are always present. `provider` and `error` are `null`, never omitted.

### What each state means to an operator

| `state` | Meaning | Operator can do |
|---|---|---|
| `"unsupported"` | This build has no on-device detector compiled in at all. | **Nothing.** Do not offer a retry. |
| `"idle"` | A detector exists but is not running. | Start listening (the existing control). |
| `"listening"` | The microphone is live and transcribing. | Stop listening. |
| `"unavailable"` | The detector **failed**. `error` says why. | **Retry** — this is where the affordance belongs. |

`"unsupported"` is a build-configuration state, not a normal condition: the shipped Windows
installer builds `--features stt`, and `make` auto-enables it when cmake is present. Render it
correctly but **unobtrusively** — it should not be a prominent scare in an app where it will
essentially never appear.

### The acceptance bar, in fields

This is the distinction the whole programme is measured against:

- **Silent room** → `state: "listening"`, `error: null`, and no transcript arriving.
- **Dead detector** → `state: "unavailable"`, `error` non-null.

**Silence is evidence of neither.** Do not infer detector health from the absence of transcript
text — that is precisely what made the two indistinguishable. Only `state` answers it.

### `invoke("retry_detection")` → same object, or rejects with a string

Restarts the detector. **Only call it when `can_retry` is true.**

`can_retry` is derived from the state's own permission rule (`DetectorState::retry_request()`),
so it can never disagree with what `retry_detection` will do. In `"unsupported"` the retry path
is not merely disabled, it is **unreachable**: the permission token `RetryRequest` has a private
field and cannot be constructed there, verified as a compile error
(`error[E0603]: tuple struct constructor RetryRequest is private`).

So: gate the control on `can_retry`. Offering a retry button in `"unsupported"` would be a button
that cannot possibly work — a new fabrication, of the same kind as the ones being removed.

---

## Tier 1b — output health (NFR-024 never-blank)

**Shipped.** Rides the existing polled view; no new command.

- Tauri: `view.output_health` from `invoke("view")` — object or `null`.
- Wire: `OperatorStateView.output_health` — object or key absent.

```jsonc
{
  "held":  boolean,   // always present
  "fault": "gpu_device_lost" | "decoder_fault" | "ipc_stall" | "disk_full",  // absent when not held
  "holds":      number,   // absent when 0
  "recoveries": number    // absent when 0
}
```

`held: true` means the live output is **holding its last good frame**. The audience still sees
content — this is the guarantee *working*, not a blank screen. Word it that way; "output held
(audience unaffected)" is accurate, "output failed" is not.

`fault` is present **only** while `held` is true, so a recovered output can never be shown beside
the reason it used to be held. Do not cache the last `fault` across a recovery.

### `holds` / `recoveries` are edges, not counts

This is the part that is not obvious from the names, and the whole reason they exist.

The console polls at 1 Hz and there is **no health event channel**. A hold that begins and ends
between two polls is invisible to `held` — both samples read `false`. So a recovery could never
be shown.

**Remember the previous `recoveries` value and compare.** An increment means a recovery happened,
whenever it happened. Same for `holds`.

```js
if (health && prev && health.recoveries > prev.recoveries) {
  // a recovery occurred since the last poll — show the transient "recovered" affordance
}
```

Both are monotonic and use saturating addition, so they never decrease. Treat a *decrease* as a
new host/session, not as a recovery. Remember: they are **absent when zero**, so read them as
`health.holds ?? 0`.

---

## Tier 2 — control-link state

> **Producer not yet shipped.** `LinkState`/`LinkStatus` exist and are tested in
> `selahcue-lan::link`, but **no Tauri command exposes them yet**. That command is mine
> (`selahcue-operator/src/main.rs`); the render is yours. Code against this shape; it will not
> change. Until it lands, `invoke("host_connected")` → `boolean` already distinguishes a real
> host from the stand-alone demo, which is enough to fix the permanent green "Connected" today.

```jsonc
{
  "state": "local" | "connected" | "reconnecting" | "disconnected",
  "epoch": number,
  "attempts": number,
  "last_error": string | null
}
```

| `state` | Meaning | UI |
|---|---|---|
| `"local"` | Stand-alone demo backend — **there is no host and none is wanted**. | Say so plainly. **Never** a green "Connected". |
| `"connected"` | A live link to the host. | Healthy. |
| `"reconnecting"` | The link dropped and an attempt **is scheduled**. | "Reconnecting…" is honest here, and **only** here. |
| `"disconnected"` | Down, automatic attempts exhausted. | Down + **offer the manual retry**. Do not imply anything is happening. |

### Guarantees you can rely on

1. **`"reconnecting"` is true exactly when an automatic attempt is scheduled.** This is a
   biconditional asserted over every state, not a best effort. If the state says reconnecting,
   something really is retrying; if something is retrying, the state says so. This is the direct
   fix for the old "Reconnecting…" label, which was shown while nothing retried at all.
2. **`"local"` never becomes `"connected"`.** No sequence of events moves it — the demo backend's
   view call cannot fail, so treating it as connected reported the absence of a failure path, not
   the presence of a host.
3. **Retries are bounded**, then the state becomes `"disconnected"`. It will not sit in
   `"reconnecting"` forever.
4. **`epoch` is monotonic** and advances on every reconnect. A reply formed under an older epoch
   describes a world the host has since replaced — discard it rather than applying it. Same idea
   as the mobile controller's `_epoch`.

The manual retry belongs on **`"disconnected"`** only.

### Not to be confused with output-window retry

`selahcue-desktop`'s screen-window logic deliberately does not loop — a failed window open is
retried only when the operator toggles that screen off and on: *"the operator's gesture, never a
loop."* That decision stands. It is about creating an OS window for an audience screen; this is a
network socket. Different problems, different right answers. Do not unify the two in the UI.

---

## Undo delete (`deck_restore`) — operator-side, not a host signal

**Shipped.** Listed here because the webview consumes it, but note it is **operator-side**: decks
are operator-owned by design and the host has no deck store. This is not part of the wire work.

`deck_list` / `deck_delete` / `deck_restore` all return the `LibraryView`, which now carries:

```jsonc
{
  "decks": [ { "id": 1, "name": "Sermon", "slides": 12 } ],
  "open": 1,
  "persistent": true,
  "restorable": [3, 7]          // deck ids an undo could actually put back, oldest first
}
```

`invoke("deck_restore", { id })` → the `LibraryView` plus:

```jsonc
{ "restored_name": "Sermon (2)" }
```

### Rules

- **Offer undo only for ids in `restorable`.** Retention is bounded (8 entries / 1.5 MB total),
  so an old delete ages out, and an unusually large presentation may never have been retained at
  all. Do not assume "the last delete" is always restorable — that assumption is how you get an
  Undo button that fails.
- **`restored_name` may differ from the name that was deleted.** If the name was taken while the
  deck sat in the trash it is uniquified. Tell the operator what their presentation is now
  called; silently restoring under a different name is its own small lie.
- **A refusal is a rejected promise**, with an operator-facing reason. Nothing is mutated when it
  refuses.
- Undo restores the deck's **real** content — slides, elements, theme, notes, transitions. Before
  this existed, the most a client-side undo could do was recreate an empty deck of the same name.

### ⚠️ The delete-confirm copy must change with it

The existing test asserting *"the delete copy and the delete behaviour agree"* — that the confirm
says "can't be undone" **and** that no Undo is offered — **will now fail, correctly.** The
capability exists, so the copy is the thing that is now wrong. Update the copy and the assertion
in the same change, keeping the biconditional shape so the two still cannot disagree.

## How to get this wrong

A subtly wrong reading reproduces the fabrication through a *truthful* source — worse than the
status quo, because it now looks sourced.

1. **Treating absent as a fault.** The single most likely mistake, and the existing
   `else → "NO SIGNAL"` fallthrough is already an instance of it. Absent is unknown.
2. **Treating absent as healthy.** The mirror error. A subsystem nobody is reporting on is not
   confirmed fine. Both wrong readings collapse three states into two.
3. **Inferring detector health from transcript silence.** A quiet room produces no transcript;
   so does a dead detector. Read `state`.
4. **Offering retry where `can_retry` is false.** Especially `"unsupported"`, where the backend
   physically cannot honour it.
5. **Reading `holds`/`recoveries` as levels.** They are counters. `recoveries > 0` does not mean
   "recovering now" — it means recoveries have happened. Compare against the previous poll.
6. **Forgetting the zero-skip.** `holds`/`recoveries` are omitted when 0; `x.holds > 0` on
   `undefined` is silently false, which is right by luck, but `x.holds.toFixed()` throws. Use
   `?? 0`.
7. **Showing a stale `fault` after recovery.** `fault` is absent once `held` is false. Do not
   keep the last value.
8. **Saying "Reconnecting…" for `"disconnected"`.** That is the original lie, restored.
9. **Rendering `"local"` as connected.** That is fabrication 3, restored.
10. **Using `"key" in obj` on the wire path.** Absent keys are omitted there, present-with-`null`
    on the Tauri path. Test both if a surface consumes both.

---

## Status

| Seam | Producer | Consumer |
|---|---|---|
| Tier 1a detector liveness | **shipped** — `detection_health`, `retry_detection` | open |
| Tier 1b output health | **shipped** — `view.output_health` | open |
| Tier 2 link state | **`LinkStatus` built + tested; Tauri command not yet shipped** | blocked on producer |
| Tier 2 storage/session health | **shipped** — `view.storage`, `view.session` | open |
| Undo delete (operator-side) | **shipped** — `deck_restore`, `restorable` | open |
