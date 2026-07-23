# SelahCue — Workflows (RP-12)

Normal, alternate, and failure-recovery workflows for SelahCue.

> **Evidence & status limitation (per DISCOVERY-REVIEW C4/M4, m7).** These workflows are
> **un-validated design intent**, not observed behaviour and not delivered guarantees. No user
> interviews or field observation informed them; they are INFERRED from domain knowledge and
> competitor research. Present-tense descriptions of SelahCue behaviour (e.g. "SelahCue restores
> the exact prior live state") are **design intent (must/should)** for the PRD and architecture to
> realise and QA to verify — **not** claims that the behaviour already exists. Nothing here is built.

## Governing principles (apply to every workflow below)

1. **The desktop application is authoritative.** It owns the live output state (what is on
   each screen), the service plan, and the source of truth for every layer. Mobile devices
   send *requests*; the desktop decides and executes.
2. **Core presentation must survive AI, mobile, and provider failure.** Slides, lyrics,
   scripture (from the local library), media playback, blackout/clear, outputs, and timers
   must remain fully operable from the desktop with **no network, no mobile, and every AI
   or third-party provider offline.**
3. **AI is assistive and human-gated.** Transcription, scripture auto-detection, sermon
   notes, and TTS never change live output on their own. A person (usually a scripture or
   production operator) approves anything that goes to screen.
4. **Fail safe, not surprising.** On any component failure, the current live output is
   *held* (never auto-cleared or blacked out as a side effect), and the operator is
   notified with a clear, non-blocking indicator.
5. **State is durable.** Live state is checkpointed continuously so an app crash can be
   recovered to the last known good service position.

---

# A. Normal Flows

## A1. Create a service plan
**Actor:** Service Coordinator (desktop). **Precondition:** SelahCue installed, library
available, user has planning permission.

1. Create a new service; choose a template or blank plan; set date/time and event type.
2. Add segments to the run-of-show (welcome, worship set, announcements, sermon, response).
3. For each segment add items: songs (with lyric arrangements), scripture references,
   media, presentation decks, timers, lower-third graphics.
4. Set per-item timing/durations and assign a responsible role/person to each segment.
5. Reorder items via drag-and-drop; validate that all referenced media and songs resolve
   (see **F6 Missing media** if any are unresolved).
6. Save; the plan is versioned. Publish/share to the team.

**Key states:** `draft → validated → published`.
**Expectation:** Publishing produces a plan the Media Operator can open on service day with
every cue in order. Edits after publish create a new version; operators see a change badge.

## A2. Present scripture from search
**Actor:** Scripture Operator (desktop primary). **Precondition:** local Bible/translation
library installed.

1. Enter a reference (e.g. `Rom 8:28`) or keyword in the scripture search.
2. Results resolve from the **local** library; select the passage and translation.
3. Passage stages into **preview** (not live), split into display-sized verse slides.
4. Review; adjust verse range/translation if needed.
5. Send to **live/program**; advance verse-by-verse as the preacher reads.
6. Clear the scripture layer when finished (content underneath is preserved).

**Key states:** `searched → staged(preview) → live → cleared`.
**Expectation:** Search and display work entirely offline. Preview-before-live is
mandatory; nothing displays without an explicit send.

## A3. Run a stage countdown → "TIME UP"
**Actor:** Stage Manager / Timer Operator (mobile or desktop). **Precondition:** a timer
exists or can be created; a stage/confidence display is showing.

1. Create/select a countdown timer (e.g. 25:00 for the sermon) and choose the target
   display(s).
2. Start the countdown; the stage/confidence display shows the running clock.
3. As time runs low, thresholds trigger visual cues (e.g. amber at 2:00, red/flashing at
   0:30) on the stage display.
4. At `00:00` the timer reaches zero and the **TIME UP** state is displayed prominently on
   the stage/confidence display.
5. Operator may extend/add time, send a stage message ("wrap up"), or clear TIME UP.

**Key states:** `armed → running → warning → TIME UP → cleared/extended`.
**Expectation:** Timer and TIME UP are **local desktop functions** — they run even with no
network/mobile. Mobile control is a convenience; the desktop remains the timekeeper of
record.

## A4. Pair a mobile controller & advance a slide
**Actor:** Mobile Remote User + System Administrator/desktop. **Precondition:** desktop
running; pairing enabled; device on same network (or approved transport).

1. On desktop, open pairing; display a PIN/QR and the role to be granted.
2. On mobile, scan QR / enter PIN; request pairing with the offered (or requested) role.
3. Desktop validates and **approves** the pairing, binding the device to a scoped role
   (see PERSONAS.md §2). Connection status shows "Connected" on both ends.
4. Mobile sees only its role-appropriate controls and live previews.
5. User taps **Next**; mobile sends an `advance` request to the desktop.
6. Desktop validates the request against the device's role, executes the advance on the
   authoritative output, and echoes the new state back to the mobile preview.

**Key states:** `unpaired → pairing-pending → paired(role) → active`.
**Expectation:** The mobile never drives output directly; it requests, the desktop
executes and confirms. Unpair/role-change is immediate (see **F3**).

## A5. Capture mic audio → live transcript
**Actor:** Sound Engineer (audio source) + operator. **Precondition:** an audio input
device is selected; a transcription provider is configured (online) **or** local engine.

1. Sound Engineer selects the audio **input device** SelahCue captures (e.g. pulpit mic
   feed); signal level is shown.
2. Operator starts transcription; audio is streamed to the transcription provider/engine.
3. Interim (partial) transcript text appears; it is finalised into stable segments with
   timestamps.
4. Transcript scrolls in a panel; it is **buffered/persisted locally** as it arrives.
5. Stop transcription; the transcript is saved to the service record.

**Key states:** `idle → capturing → transcribing(interim→final) → stopped/saved`.
**Expectation:** Transcription is **assistive** — it never touches live output. If it
fails, presentation is unaffected (see **F2**, **F4**).

## A6. Detect a spoken scripture reference → operator approval → display
**Actor:** SelahCue auto-detection + Scripture Operator (approver). **Precondition:** live
transcript running; scripture detection enabled; local Bible library available.

1. The detector monitors the finalised transcript for scripture references.
2. On a candidate (e.g. hears "Romans chapter 8 verse 28"), it resolves the reference
   against the local library and creates a **suggestion** in an approval queue — **it does
   not display anything.**
3. The Scripture Operator sees the suggestion (reference, translation, confidence) and
   previews the resolved passage.
4. Operator **approves** (→ passage stages to preview or directly to live per config) or
   **dismisses** the suggestion.
5. If approved to preview, operator sends to live and advances as in **A2**.

**Key states:** `detected → suggested(queued) → previewed → approved→live | dismissed`.
**Expectation:** **Human-in-the-loop is mandatory.** A false positive is a dismissed queue
item, never a wrong verse on screen. Detection failure degrades to manual search (**A2**).

## A7. Generate editable sermon notes from a transcript
**Actor:** Post-Service Media/Sermon Editor + AI. **Precondition:** a saved transcript
exists; AI notes provider configured.

1. Editor selects a completed service transcript and requests sermon-note generation.
2. SelahCue sends the transcript to the AI notes provider and generates a **draft**
   (outline, key points, scripture list with timestamps, summary).
3. The draft opens in an **editable** editor — never read-only.
4. Editor corrects/reorganises, fixes any misattributions or hallucinations, and cross-
   checks scripture references.
5. Editor saves/exports (and may re-run generation on a corrected transcript).

**Key states:** `transcript-ready → generating → draft(editable) → edited → exported`.
**Expectation:** AI output is always a *draft* the human owns. Generation failure leaves
the raw transcript intact and available for manual notes (see **F4**).

## A8. TTS read a passage to a selected output
**Actor:** Production/Scripture Operator + Sound Engineer (output routing). **Precondition:**
TTS provider/engine configured; an audio **output** device selected.

1. Operator selects a passage/text and chooses **TTS**.
2. Operator selects the target audio **output** (must not be the live house mix unless
   intended); Sound Engineer confirms routing.
3. Operator triggers synthesis; audio plays to the selected output.
4. Operator can pause/stop; visual state shows TTS is speaking and to which output.

**Key states:** `text-selected → output-selected → synthesizing → playing → stopped`.
**Expectation:** TTS routing is explicit to avoid speaking to the live congregation by
accident. TTS failure is non-fatal (see **F4**); it never blocks presentation.

---

# B. Alternate Flows

- **B1 (alt of A1):** Import/duplicate a previous service as a starting plan; swap songs
  and scriptures rather than building from scratch.
- **B2 (alt of A2):** Scripture pushed reactively from a **mobile** Scripture Operator near
  the stage instead of the booth desktop — same preview-then-live gate, executed by desktop.
- **B3 (alt of A3):** Count-**up** timer (elapsed) instead of countdown; or an open-ended
  timer with a manual TIME UP trigger sent by the Stage Manager.
- **B4 (alt of A4):** Pairing without QR (manual PIN entry) or re-pairing a previously
  known device (fast-reconnect with remembered role, still admin-revocable).
- **B5 (alt of A5):** Use a **local/offline** transcription engine instead of a cloud
  provider when no internet is available or privacy requires it.
- **B6 (alt of A6):** Detection auto-stages to **preview only** (never live) as a stricter
  org policy; operator must always send to live manually.
- **B7 (alt of A7):** Generate notes from an **imported/edited** transcript (e.g. the
  editor cleaned it first) or regenerate a section only.
- **B8 (alt of A8):** TTS to a **file/asset** for later use (accessibility export) rather
  than live audio output.
- **B9 (worship spontaneity):** Worship Leader triggers a chorus repeat/jump from stage
  mobile; the Media Operator sees the change reflected and can override from desktop.

---

# C. Failure-Recovery Flows

> In every failure below: **current live output is held**, the desktop stays authoritative,
> core presentation continues, and the operator gets a clear non-blocking alert. No failure
> of a mobile device, AI feature, or provider may black out or clear the screen as a side
> effect.

## F1. Display disconnection mid-service
**Trigger:** an output display (projector/screen/stream feed) disconnects (cable, resolution
change, GPU glitch).
1. SelahCue detects the output is gone; the operator gets a distinct alert naming the lost
   output; **other outputs are unaffected.**
2. The last-rendered frame/state for that output is **retained in the desktop's model** so
   nothing is lost.
3. On reconnection (auto-detected), SelahCue **restores the exact prior live state** to that
   output — same slide/verse/layer — without operator rebuild.
4. If it does not auto-recover, operator re-selects the display and re-pushes current state
   with one action.
**Recovery expectation:** No content loss; reconnect restores live state; other screens and
the service never stopped.

## F2. Audio-device disconnection during transcription
**Trigger:** the transcription input device (USB mic/interface) disconnects.
1. Transcription **pauses**, not crashes; the transcript captured so far is preserved.
2. Operator/Sound Engineer is alerted that the input was lost, with the device name.
3. On device return (or selection of a new input), transcription **resumes**; the transcript
   continues appending (a gap marker notes the interruption).
4. Scripture auto-detection resumes with transcription; presentation was never affected.
**Recovery expectation:** Presentation untouched; transcript preserved with a clear gap; no
data loss on the captured-so-far portion.

## F3. Mobile connectivity loss
**Trigger:** a paired mobile device loses network/goes to sleep.
1. Desktop marks the device **disconnected**; the desktop retains full authority and every
   capability (nothing the mobile "held" is lost).
2. **In-flight requests that cannot be validated are rejected, not blindly queued** — the
   desktop does not replay a stale slide-advance seconds later.
3. Mobile shows a clear "Reconnecting…" state and its controls are disabled while offline.
4. On reconnect, the desktop re-validates the device's role and **syncs current live state**
   to the mobile preview before re-enabling controls.
**Recovery expectation:** The service is never dependent on the mobile; reconnection is clean
and re-syncs to truth; no ghost/stale actions fire.

## F4. AI / transcription / TTS provider failure
**Trigger:** a third-party provider errors, times out, or auth/quota fails (transcription,
scripture-detection resolve, sermon notes, or TTS).
1. The affected **assistive** feature degrades gracefully and shows an "unavailable" state;
   **core presentation and local scripture search are unaffected.**
2. Scripture detection stops surfacing suggestions → operators fall back to **manual search
   (A2)**. TTS failure → the passage can still be displayed/read manually. Sermon-note
   generation failure → the **raw transcript remains** for manual notes or later retry.
3. SelahCue retries with backoff and, where configured, **fails over to a local engine**
   (e.g. offline transcription) or an alternate provider.
4. No provider failure ever blocks a slide, verse, or media cue.
**Recovery expectation:** Assistive features degrade to manual; presentation is fully intact;
retry/fallback available; nothing wrong auto-displays because the human gate still applies.

## F5. App crash & recovery
**Trigger:** the SelahCue desktop process crashes mid-service.
1. Live output state, the loaded plan, current position, timers, and buffered transcript are
   **continuously checkpointed** to durable local storage.
2. On relaunch, SelahCue detects the prior session ended abnormally and offers **"Resume
   service"**, restoring the loaded plan and the **last known live position** (current
   slide/verse/layer, active timers).
3. Outputs are re-initialised and the restored live state is re-pushed to the correct
   displays.
4. Paired mobiles reconnect (**F3**) and re-sync; buffered transcript is recovered up to the
   last checkpoint.
**Recovery expectation:** Fast resume to the last good position with minimal manual rebuild;
no need to reconstruct the service from memory; transcript recovered to last checkpoint.

## F6. Missing media
**Trigger:** a plan item references media that is absent/unresolved (moved file, missing
download) — detected at plan validation (A1.5) or at trigger time.
1. **At planning:** unresolved items are flagged with a clear "missing media" badge; the
   coordinator relinks or replaces before publish.
2. **At service time:** if a missing item is triggered, SelahCue **does not black out** —
   it holds the prior content (or shows a safe placeholder) and alerts the operator.
3. Operator skips the item, substitutes another, or relinks on the spot; the run continues.
**Recovery expectation:** Missing media never causes a black screen mid-service; it is caught
in planning and, if it slips through, degrades to a held frame/placeholder, not a failure.

## F7. Forced shutdown (power loss / OS kill)
**Trigger:** abrupt power loss or forced OS termination of the machine.
1. Because live state is continuously checkpointed (**F5**), the most recent good state
   survives on disk.
2. On power-up and relaunch, the **"Resume service"** path (F5) restores the plan and last
   live position.
3. If a redundant/second operator machine exists, it can take over as authoritative in the
   interim (operational failover), then hand back.
4. Team is guided to re-verify outputs and timers before resuming live.
**Recovery expectation:** Bounded loss (only since the last checkpoint), a one-action resume,
and an optional redundant-desktop failover path so the service can continue.

---

# D. Cross-cutting recovery expectations (summary)

| Failure                         | Presentation continues? | Data preserved                        | Recovery path                          |
|---------------------------------|:-----------------------:|---------------------------------------|----------------------------------------|
| F1 Display disconnect           | ✅ (other outputs)       | Live state per output                 | Auto-restore on reconnect              |
| F2 Audio device disconnect      | ✅                       | Transcript so far (+ gap marker)      | Resume on device return                |
| F3 Mobile connectivity loss     | ✅                       | N/A (desktop authoritative)           | Re-validate + state re-sync            |
| F4 AI/provider failure          | ✅                       | Transcript / manual fallback intact   | Degrade to manual; retry/local failover|
| F5 App crash                    | ▶ after resume           | Plan + live position + transcript     | "Resume service" from checkpoint       |
| F6 Missing media                | ✅ (held/placeholder)    | Rest of plan intact                   | Relink/skip/substitute                 |
| F7 Forced shutdown              | ▶ after relaunch/failover| Checkpointed state on disk            | Resume + optional redundant desktop    |

**Bottom line:** SelahCue's presentation core is a self-sufficient, offline-capable,
crash-recoverable desktop application. Mobile control, transcription, scripture detection,
sermon notes, and TTS are layered assistance that can each fail independently without ever
stopping the service, clearing the screen, or displaying unapproved content.
