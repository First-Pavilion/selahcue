# SelahCue — Personas & Permission Matrix (RP-12)

**Product:** SelahCue — cross-platform church presentation & ministry-assistance app
(presentation slides, song lyrics, Bible scripture, multiple outputs, stage/confidence
displays, lower thirds, timers with "TIME UP", live transcription, automatic scripture
detection, AI sermon notes, text-to-speech, mobile remote control, media playback,
service planning).

**Contexts of use:** churches, conferences, concerts, worship events, livestream
productions, sermon recording.

> **Evidence limitation (per DISCOVERY-REVIEW C4/M4).** This is **un-validated domain
> modelling.** No user interviews, surveys, or field observation were conducted. The
> personas, their needs and pain points, the permission-matrix defaults, and the persona→role
> mappings are **INFERRED** from domain knowledge and the competitor research
> ([COMPETITOR-MATRIX.md](../research/COMPETITOR-MATRIX.md)), not evidenced against real
> operators. They are a strong starting hypothesis for the PRD, to be validated (and corrected)
> by real user feedback in later stages. Classification of every persona need/pain and matrix
> default: **INFERRED / Med.**

**Design principle referenced throughout:** the **desktop application is authoritative**.
Mobile devices, AI features, and third-party providers (transcription, TTS) are
*assistive and optional*. Core presentation (slides, scripture, lyrics, outputs,
blackout, timers) must remain fully operable from the desktop even when every network,
mobile, and AI dependency fails.

---

## 1. Personas (11 roles)

### 1.1 Church Media Operator (a.k.a. ProPresenter/EasyWorship operator, "the tech")
- **Goals:** Run the entire visual service smoothly with zero on-screen mistakes; keep
  slides, lyrics, and scripture in lockstep with what is happening live.
- **Responsibilities:** Build/finish the service playlist, drive the main output during
  service, manage slide advance, clear layers, blackout, media playback, correct
  mistakes instantly.
- **Primary JTBD:** "When the worship set moves to the next song, I want the right lyric
  slide up in under a second so the congregation never loses the words."
- **Needs:** Fast keyboard-driven control, reliable preview vs. program separation,
  instant blackout/clear, undo, a stage display they can trust, offline reliability.
- **Pain points:** Wrong slide on the big screen; laggy transitions; losing track of song
  order when the worship leader improvises; software crashing mid-service; fear of a
  black screen during offering or altar call.
- **Device:** **Desktop** (primary operator seat). Occasionally a second desktop/laptop
  for redundancy.

### 1.2 Scripture Operator
- **Goals:** Put the correct Bible passage on screen, in the correct translation, exactly
  when the preacher references it — often reactively and quickly.
- **Responsibilities:** Search scripture by reference or keyword, stage passages, advance
  verse-by-verse, switch translations, review and approve auto-detected scripture
  suggestions before they go live.
- **Primary JTBD:** "When the pastor says 'turn to Romans 8:28', I want that verse
  searched and on screen before the congregation finishes flipping pages."
- **Needs:** Lightning-fast reference search, translation switcher, verse-range staging,
  a **preview-before-live** step, an approval queue for auto-detected references so
  nothing wrong ever auto-displays.
- **Pain points:** Mishearing a reference; wrong translation; auto-detection displaying a
  false positive live; passages that span awkward verse ranges; keeping up with a fast
  or improvising preacher.
- **Device:** **Desktop** primary; **mobile** as a secondary reactive station (a roaming
  operator approving/pushing scripture from a tablet near the stage).

### 1.3 Worship Leader
- **Goals:** Lead worship without breaking flow; keep the band and media in sync with
  where the Spirit/the set is going, including spontaneous changes.
- **Responsibilities:** Define song set/order in planning; during service, signal or
  directly trigger the next song, repeat a chorus, vamp, or jump — sometimes from stage.
- **Primary JTBD:** "When I decide to repeat the bridge, I want to move the slides myself
  from my in-ear/tablet without shouting to the booth."
- **Needs:** A trusted stage/confidence view of current + next lyric; simple, large,
  glanceable mobile controls; ability to advance/repeat lyrics and send a quiet cue to
  the operator; minimal, distraction-free UI.
- **Pain points:** Media lagging behind spontaneous set changes; can't communicate with
  booth mid-song; confidence monitor showing the wrong line; fiddly controls under stage
  lighting.
- **Device:** **Mobile** (on-stage tablet/phone remote) primary; relies on **desktop**
  operator as backstop.

### 1.4 Pastor / Preacher
- **Goals:** Preach without technology getting in the way; have scripture, notes, and
  timing support appear reliably; get usable notes/recording afterward.
- **Responsibilities:** Provide sermon references/outline ahead of time (ideally); preach;
  respond to timer cues; benefit from confidence display and (post-service) AI sermon
  notes.
- **Primary JTBD:** "When I glance at the confidence monitor, I want to see my current
  point, the next scripture, and how much time I have left."
- **Needs:** Clean confidence/stage display (next point, current scripture, clock/timer),
  discreet **TIME UP** signalling, accurate transcript/sermon notes afterward, no
  requirement to touch tech mid-sermon.
- **Pain points:** Being surprised by time; scripture appearing wrong or late; distracting
  countdowns; inaccurate AI notes that misquote them; feeling monitored.
- **Device:** **Confidence/stage display** (view-only). Optionally a **mobile** view of
  their own notes/timer. Rarely operates controls.

### 1.5 Stage Manager
- **Goals:** Keep the service/production on schedule and cue people on/off stage safely.
- **Responsibilities:** Own the run-of-show timing; run countdowns to service start and
  between segments; send stage messages ("wrap up", "go to mic 2"); trigger/monitor the
  **TIME UP** signal; coordinate transitions.
- **Primary JTBD:** "When a segment runs 3 minutes long, I want to send a discreet
  'wrap up' to the stage and start a hard TIME UP countdown."
- **Needs:** Timer creation/control (count up/down, presets), stage-message sending,
  clear TIME UP escalation, visibility of the current run-of-show item, mobility.
- **Pain points:** Talent ignoring cues; unclear whether a message reached the stage
  display; countdowns drifting; no way to intervene from the floor.
- **Device:** **Mobile** (roaming) primary; **desktop** for run-of-show setup.

### 1.6 Livestream Director
- **Goals:** Deliver a clean broadcast: lower thirds, scripture, and graphics keyed
  correctly to the online audience without on-air errors.
- **Responsibilities:** Manage the dedicated stream/broadcast output (often separate from
  auditorium output); control lower thirds (name/title, scripture, song credits);
  coordinate with the switcher/encoder; monitor output health.
- **Primary JTBD:** "When the pastor is introduced, I want to key a lower third with their
  name to the stream output only — not the in-room screens."
- **Needs:** Independent multi-output routing, lower-third control, per-output preview,
  **output-health monitoring** (is the stream output alive, resolution, dropped frames),
  fast clear.
- **Pain points:** A layer meant for the room bleeding onto the stream; lower third stuck
  on air; output silently disconnected; audio/video desync; no health visibility.
- **Device:** **Desktop** primary (broadcast booth); **mobile** for health monitoring.

### 1.7 Sound Engineer
- **Goals:** Clean audio for room and broadcast; and, for SelahCue specifically, feed a
  reliable audio source into live transcription.
- **Responsibilities:** Select/route the mic/audio-device source SelahCue captures for
  transcription; monitor audio device connection.
- **Primary JTBD:** "When I bring up the pulpit mic, I want SelahCue transcribing from that
  same feed so captions and scripture detection track the preacher."
- **Needs:** Explicit audio-input-device selection, level/signal indication, graceful
  handling when a device disconnects.
- **Pain points:** SelahCue grabbing the wrong input; USB/interface disconnects killing
  transcription; latency.
- **Device:** **Desktop** (at/near the audio console) primary.

### 1.8 Service Coordinator (Producer / Planner)
- **Goals:** Plan the whole service ahead of time so operators can execute without guessing.
- **Responsibilities:** Build the service plan / run-of-show (segments, songs, scriptures,
  media, timings, responsible people); assign roles; publish the plan to the team; make
  last-minute edits.
- **Primary JTBD:** "When I finish the plan on Thursday, I want the media operator to open
  Sunday's service and have every song, scripture, and media cue already in order."
- **Needs:** Service-plan authoring, templates, drag-and-drop ordering, per-item timing,
  role/assignment, versioning, easy handoff to the operator's live view.
- **Pain points:** Plans changing at the last minute; media missing on service day;
  mismatch between the plan and what's loaded; no clear ownership of items.
- **Device:** **Desktop** primary; **mobile** for review/last-minute edits.

### 1.9 System Administrator
- **Goals:** Keep SelahCue installed, licensed, secure, and configured across machines and
  the whole team; manage who can do what.
- **Responsibilities:** Install/update software; configure outputs/displays; manage users,
  roles, and permissions; manage mobile pairing/PINs; configure AI/transcription
  providers and keys; backups; bibles/translations licensing.
- **Primary JTBD:** "When a new volunteer joins, I want to grant them a scoped mobile role
  and revoke it after the event."
- **Needs:** User/role management, pairing management, provider configuration, output
  configuration, audit/logging, backup & restore, safe defaults.
- **Pain points:** Volunteers with too much access; lost pairing PINs; provider keys
  leaking or expiring; config drift between machines; no audit trail.
- **Device:** **Desktop** primary; **mobile** for pairing approvals.

### 1.10 Mobile Remote User
- **Goals:** Assist the service from a phone/tablet away from the booth, within a *scoped*
  set of controls granted to them.
- **Responsibilities:** Whatever their assigned mobile role allows — from view-only
  monitoring (Observer) up to full remote control (Administrator). Common: advancing
  slides, controlling timers, pushing scripture, sending stage messages.
- **Primary JTBD:** "When I'm roaming the room, I want to advance slides and see previews
  on my phone without being tied to the desktop."
- **Needs:** Simple pairing (PIN/QR), reliable connection with clear connection status,
  role-appropriate controls only, graceful reconnection, large touch targets.
- **Pain points:** Connection dropping silently; seeing controls they can't actually use;
  accidental taps triggering live changes; unclear whether an action reached the desktop.
- **Device:** **Mobile** (definitionally).

### 1.11 Post-Service Media / Sermon Editor
- **Goals:** Turn the captured service into shareable assets: edited sermon notes, clean
  transcript, recorded media, clips.
- **Responsibilities:** Access post-service transcript, AI-generated sermon notes, detected
  scripture list, and media; edit/correct them; export/publish.
- **Primary JTBD:** "When the service ends, I want an editable draft of the sermon notes and
  a corrected transcript I can publish by Monday."
- **Needs:** Access to saved transcript + AI notes, an editor (not read-only), scripture
  list with timestamps, export formats, ability to re-run/regenerate AI, correction of AI
  errors.
- **Pain points:** AI notes inaccurate or hallucinated; transcript unpunctuated; no
  timestamps; content lost if the app crashed; can't edit generated output.
- **Device:** **Desktop** primary (editing); **mobile** for quick review/approval.

---

## 2. Permission Matrix — 7 Mobile Control Roles × Capabilities

These roles are the **scoped remote-control roles** assigned to a paired mobile device
(and enforced by the authoritative desktop). They are distinct from the 11 personas above:
a person's persona informs which mobile role they should be granted.

> **TTS removed (DEC-001, Stage-4 MAJOR-07):** TTS is a non-goal. The former "TTS control"
> capability has been struck from the matrix below (now **7 roles × 14 capabilities**) and
> TTS output-routing pruned from the Sound Engineer/Production Operator personas.

**Legend:** ✅ = full capability · 👁 = view/read-only · ⚠️ = limited / with-approval /
suggest-only · ❌ = not permitted

| Capability                         | Observer | Presenter | Worship Leader | Scripture Operator | Timer Operator | Production Operator | Administrator |
|------------------------------------|:--------:|:---------:|:--------------:|:------------------:|:--------------:|:-------------------:|:-------------:|
| View previews (preview/program)    |    👁     |     ✅     |       ✅        |         ✅          |       👁        |          ✅          |       ✅       |
| Trigger slides (advance/back)      |    ❌     |     ✅     |     ✅ (lyrics) |     ✅ (scripture)  |       ❌        |          ✅          |       ✅       |
| Clear layers                       |    ❌     |     ⚠️ own |       ⚠️ own    |        ⚠️ own       |       ❌        |          ✅          |       ✅       |
| Blackout (kill output)             |    ❌     |     ✅     |       ⚠️        |         ⚠️          |       ❌        |          ✅          |       ✅       |
| Timer control (start/stop/adjust)  |    ❌     |     ⚠️     |       ⚠️        |         ❌          |       ✅        |          ✅          |       ✅       |
| **TIME UP** control                |    ❌     |     ❌     |       ⚠️        |         ❌          |       ✅        |          ✅          |       ✅       |
| Lower-third control                |    ❌     |     ⚠️     |       ❌        |         ⚠️          |       ❌        |          ✅          |       ✅       |
| Scripture search / display         |    ❌     |     ⚠️     |       ❌        |         ✅          |       ❌        |          ✅          |       ✅       |
| Approve scripture suggestions      |    ❌     |     ❌     |       ❌        |         ✅          |       ❌        |          ✅          |       ✅       |
| View transcript (live)             |    👁     |     👁     |       👁        |         👁          |       👁        |          👁          |       ✅       |
| Send stage messages                |    ❌     |     ⚠️     |       ✅        |         ❌          |       ✅        |          ✅          |       ✅       |
| Output-health monitoring           |    👁     |     👁     |       👁        |         👁          |       👁        |          ✅          |       ✅       |
| Macro triggering                   |    ❌     |     ⚠️     |       ⚠️        |         ❌          |       ❌        |          ✅          |       ✅       |
| Admin / pairing management         |    ❌     |     ❌     |       ❌        |         ❌          |       ❌        |          ❌          |       ✅       |

### 2.1 Notes on the matrix
- **Observer** is a safe, view-only badge for guests, trainees, or a pastor watching
  previews — it can trigger nothing live.
- **Presenter** is the general "advance the current thing" role; `⚠️` entries mean it may
  act only on the currently active presentation/its own layers, and may *suggest* rather
  than commit for lower thirds and macros, subject to admin configuration.
- **Worship Leader** is deliberately narrow: lyric advance/repeat + stage messaging, so a
  leader can drive their set from stage without touching broadcast or scripture layers.
- **Scripture Operator (mobile)** mirrors the desktop scripture operator: it is the role
  that may **approve auto-detected scripture suggestions** — a deliberately restricted,
  human-in-the-loop gate so no detection auto-displays.
- **Timer Operator** owns countdowns and the **TIME UP** escalation but cannot touch
  content — matching the Stage Manager persona roaming the floor.
- **Production Operator** is a near-full remote (lower thirds, macros, output health)
  for a trusted second operator — everything except administration.
- **Administrator** is the only role that can manage pairing, provisioning, and roles, and
  is the only role with full live transcript control. Grant sparingly.
- **All `⚠️` cells are configurable by the System Administrator** per-organisation; the
  table shows the recommended default.

### 2.2 Enforcement invariant
Mobile roles are **capability requests to the authoritative desktop**. The desktop
validates every incoming action against the paired device's granted role at execution
time; a role downgrade or unpair takes effect immediately, and any action the desktop
cannot validate (stale role, lost pairing) is **rejected, not queued blindly**. Losing
all mobile devices never disables any desktop capability.

---

## 3. Persona → Recommended Mobile Role (quick mapping)

| Persona                         | Typical mobile role(s)                    |
|---------------------------------|-------------------------------------------|
| Church Media Operator           | Production Operator (if roaming)          |
| Scripture Operator              | Scripture Operator                        |
| Worship Leader                  | Worship Leader                            |
| Pastor / Preacher               | Observer (own notes/timer view)           |
| Stage Manager                   | Timer Operator                            |
| Livestream Director             | Production Operator                       |
| Sound Engineer                  | Observer / Production Operator            |
| Service Coordinator             | Presenter or Observer                     |
| System Administrator            | Administrator                             |
| Mobile Remote User              | Any granted role (scoped per event)       |
| Post-Service Media/Sermon Editor| Observer (review only)                    |

---

## 4. Open questions (roles / permissions) — for the user
1. Should **Blackout** ever be available to lower roles (Presenter/Worship Leader) as an
   emergency "panic" button, or stay restricted to Production/Admin only?
2. Is there ever a need for a mobile role to **display scripture without desktop approval**
   (e.g. a trusted second scripture operator), or is human-in-the-loop approval always
   mandatory?
3. Should permissions be **per-output** (e.g. control stream lower thirds but not room
   output), which the Livestream Director persona implies but the current flat matrix does
   not model?
4. Do we need a **time-boxed / event-scoped** grant (auto-revoke when the service ends) for
   volunteer Mobile Remote Users?
5. Should the **Pastor** get a dedicated read-only "confidence" mobile profile distinct
   from Observer (own notes + timer, no previews of others)?
6. Is **macro triggering** granular (per-macro allow-list) or all-or-nothing per role?
