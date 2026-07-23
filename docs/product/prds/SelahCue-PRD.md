# SelahCue — Product Requirements Document (PRD)

Version: 1.0 (Stage 3 draft, pre-audit) · Date: 2026-07-23 · Owner: Product Manager · Status: For Stage 4 independent audit

**Sources:** discovery package `docs/research/*`, `docs/business/*`, `docs/security/reviews/threat-model-draft.md`, decisions `docs/decisions/DECISION-LOG.md`, product brief `product/PRODUCT-BRIEF.md`. Requirement IDs are stable; acceptance criteria are measurable/testable. Priorities: **MVP** · **R2** media/output expansion · **R3** transcription · **R4** scripture intelligence · **R5** sermon intelligence · **R6** integrations & hardening · **NON-GOAL**.

---

## 1. Product vision

SelahCue is a cross-platform (Windows, macOS, Linux) church presentation and ministry-assistance application with a companion mobile controller (Android, iOS/iPadOS), combining the strongest ideas of products such as PewBeam and ProPresenter into an original product. It helps churches, conferences, worship events, livestream productions, and sermon recordings drive presentation slides, song lyrics, Bible scripture, multiple independent outputs, stage/confidence displays, lower thirds, and timers — and layers **responsible, operator-in-the-loop AI** (live transcription, automatic scripture detection, AI sermon notes) on top of a complete production suite. It prioritises live-service reliability, low resource use, fast operation, offline-first behaviour, operator control over AI, privacy of sermon data, and recovery from crash/network/display/provider failure.

## 2. Problem statement

Churches choose between power (ProPresenter — deep, pro AV, but Mac-first, ~$399/seat, steep learning curve, no Linux), accessibility (OpenLP/FreeShow/Quelea — free, cross-platform, but utilitarian and light on pro AV routing/roles), and ease (EasyWorship — volunteer-friendly, subscription, no Linux). AI-native entrants (PewBeam) prove demand for live sermon-follow scripture but appear verse-projection-centric rather than complete production suites. No incumbent delivers genuine Win/macOS/Linux support, volunteer-first UX with opt-in pro depth, native role-based collaboration, first-class ecosystem interop (NDI/alpha, transparent browser-source, Companion/Stream Deck), and responsible operator-controlled AI, with offline-first reliability as an explicit guarantee. SelahCue targets that gap.

## 3. Personas and roles

Full personas: `docs/business/PERSONAS.md` (un-validated domain modelling — INFERRED). Eleven personas across desktop (authoring/operating) and mobile (roaming control): Church Media Operator, Scripture Operator, Worship Leader, Pastor/Preacher, Stage Manager, Livestream Director, Sound Engineer, Service Coordinator, System Administrator, Mobile Remote User, Post-Service Media/Sermon Editor. Seven scoped **mobile control roles** (Observer, Presenter, Worship Leader, Scripture Operator, Timer Operator, Production Operator, Administrator) — see §16 Permissions.

## 4. Jobs to be done (selected)

- **JTBD-1:** When the worship set advances, put the correct lyric slide on the main output in <1s so the congregation never loses the words.
- **JTBD-2:** When the pastor names a scripture, get that verse (correct translation) on screen before the congregation finishes turning pages.
- **JTBD-3:** When a segment runs long, send a discreet "wrap up" and a hard TIME UP countdown to the stage without touching audience outputs.
- **JTBD-4:** When roaming the room, advance slides and see previews from a phone with role-appropriate controls only.
- **JTBD-5:** After service, get an editable, corrected transcript and an AI sermon-note draft to publish by Monday.
- **JTBD-6:** When anything fails mid-service (display unplugged, network drops, AI provider errors), keep the current output on screen and stay in control from the desktop.

## 5. Goals

- **G-1:** Deliver a reliable live-presentation core that works fully offline and never blanks/clears output as a side effect of any failure.
- **G-2:** Run genuinely on Windows, macOS, and Linux with a companion mobile controller over the local network.
- **G-3:** Provide operator-in-the-loop AI (transcription, scripture detection, sermon notes) that assists without ever blocking core controls.
- **G-4:** Be volunteer-operable within minutes while offering opt-in pro depth (multi-output, key/fill, integrations).
- **G-5:** Protect sermon privacy: offline-first, opt-in cloud with visible disclosure, secure secret storage.

## 6. Non-goals

- **NG-1: Text-to-speech (TTS)** — removed from the roadmap by [DEC-001](../../decisions/DECISION-LOG.md); not MVP, not planned; revisit only on explicit future request.
- **NG-2: Voice cloning** — excluded unless separately approved with consent + safeguards.
- **NG-3:** Bundling copyrighted Bible translations, worship lyrics, fonts, codecs, or AI models without verified permission.
- **NG-4:** Copying proprietary product code, interfaces pixel-for-pixel, branding, or protected assets.
- **NG-5:** Cloud-hosted SaaS presentation control (SelahCue is desktop-authoritative; mobile control is LAN-based).
- **NG-6:** RTL / complex-script (Arabic/Hebrew) text rendering in MVP (scoped later — OD-22); MVP covers Latin + diacritics (incl. Yoruba/Hausa/Igbo/French/Spanish).

## 7. Success metrics

See §31 for METRIC-* definitions. Headline: zero unintended output blanks in live use (METRIC-001), slide-trigger latency (METRIC-002), 12h soak memory stability (METRIC-003), operator time-to-first-slide for a new user (METRIC-006).

## 8. Constraints

- **CON-1:** Desktop is the authoritative state owner; mobile/AI/providers are assistive and optional.
- **CON-2:** Core live functions (slides, local scripture, media, blackout/clear, timers) must work with zero network/cloud/mobile/AI.
- **CON-3:** MVP bundles only public-domain Bible translations; licensed translations are API-only/user-supplied (later).
- **CON-4:** Media playback uses OS-native/HW decoders for encumbered codecs (H.264/HEVC **and AAC** and other patented audio codecs); SelahCue-encoded media prefers VP9/AV1+Opus (codec-patent safe harbor, OD-08a); verified in the dependency audit (FR-073).
- **CON-5:** Cloud transmission is opt-in, per-provider, with visible disclosure; no sermon audio/transcript leaves the host without explicit user action.
- **CON-6:** Stage-gated build; requirements are testable and traceable.

## 9. Assumptions

- **AS-1:** MVP = presentation foundation on desktop tri-platform + a **feature-scoped** mobile controller (user-accepted at Stage 2 gate, OD-01/03). Note (Stage-3 review C-4): the controller is *feature*-thin (slide/timer control + previews), but it ships with **two full hardened subsystems** — the secure LAN transport/pairing/replay layer and server-side RBAC — so MVP mobile effort is non-trivial and is planned as its own foundation slice (Stage 7).
- **AS-2:** Target church hardware ranges from CPU-only PCs to modest GPU / Apple Silicon; performance targets are per-tier (§26).
- **AS-3:** Final technology stack is chosen in Stage 5 via ADRs; the Rust core + wgpu compositor + GStreamer + SQLite leaning is preliminary and spike-gated.
- **AS-4:** Users hold their own CCLI / translation licences; SelahCue provides compliance affordances, not the licences.
- **AS-5:** At-rest confidentiality (FR-154) defaults to app-managed SQLCipher; where OS full-disk encryption is relied upon instead, it is a documented deployment prerequisite the app verifies (§21).
- **AS-6:** The bounded MVP presumes a small dedicated engineering team over a multi-month schedule, with the presentation-core desktop sub-release preceding the mobile control-plane slice (RISK-001, AS-1). This is the capacity assumption the MVP boundary rests on; revise the boundary if capacity differs.

## 10. Competitor research (summary)

Full: `docs/research/COMPETITOR-MATRIX.md`, `docs/research/ADJACENT-TRANSCRIPTION-PRODUCTS.md`. Key: ProPresenter deepest but Mac-first/no-Linux/costly; FreeShow strongest free challenger (NDI/MIDI/importers, cross-platform); EasyWorship volunteer-friendly subscription; OpenLP/Quelea free/OSS incl. Linux; PewBeam AI-native but verse-centric. Ecosystem table-stakes: OBS (browser source/NDI/websocket), NDI, ATEM (key/fill), Bitfocus Companion/Stream Deck. Differentiators for SelahCue: cross-platform incl. Linux + real mobile, volunteer-first UX, native RBAC, first-class alpha-NDI/browser-source/Companion, responsible operator-in-the-loop AI inside a full production suite, migration importers, offline-first reliability.

## 11. User journeys

Requirement-style flow IDs; full narrative flows in `docs/business/WORKFLOWS.md` (design intent).

| ID | Journey | Priority | Acceptance criteria (measurable) | Trace |
|---|---|---|---|---|
| FLOW-001 | Build a service plan and present a static slide on the main output | MVP | Coordinator builds plan with ≥3 item types; operator opens it and triggers a slide live in ≤2 taps; slide renders on main output <1s | JTBD-1; RP-01 |
| FLOW-002 | Search a scripture and display it with a chosen template | MVP | Operator searches by reference, selects translation+template, stages then goes live; correct verse text on output; verse-per-slide pagination applied | JTBD-2; RP-01 |
| FLOW-003 | Run a stage countdown and show TIME UP at zero | MVP | Countdown to 0 triggers configured TIME UP state on selected outputs only; overrun continues in negative; manual + auto dismissal work | JTBD-3; brief §Timer |
| FLOW-004 | Pair a mobile controller and advance a slide | MVP | QR pairing completes; paired device (Presenter role) advances the live slide with desktop acting <200ms on LAN | JTBD-4; RP-12 |
| FLOW-005 | Capture microphone audio and show an interim transcript | R3 | Operator selects input device; live interim transcript appears with provisional styling; confirmed segments persist with timestamps | JTBD-5; RP-03 |
| FLOW-006 | Detect an explicit spoken reference and present it for approval | R4 | Spoken "John three sixteen" surfaces a suggestion with reference+translation+confidence; operator approves → displays; nothing auto-displays by default | JTBD-2; RP-04 |
| FLOW-007 | Generate editable sermon notes from a completed transcript | R5 | From a stored transcript, notes generate with summary/points/timestamps; notes are editable and labelled AI-generated; source transcript unchanged | JTBD-5; RP-05 |
| FLOW-008 | Recover the exact live state after an app crash | MVP | After forced kill, on relaunch the prior live output, service position, and timers restore from the last checkpoint (≤5s data loss) | JTBD-6; RP-reliability |
| FLOW-009 | Continue presenting when a display is unplugged and replugged | MVP | Output disconnect does not blank other outputs; on reconnect the exact prior live content auto-restores to that output | JTBD-6; threat/personas |
| FLOW-010 | Lose all mobile connectivity mid-service | MVP | Desktop retains full control; stale mobile commands after reconnect are rejected, not replayed; no ghost actions | CON-1/2; threat T4 |

## 12. Feature inventory

Presentation library; service plans; slides; song lyrics; announcements; sermon points; images/video/audio/motion backgrounds; templates & themes; preview/live; current/next; keyboard shortcuts; command palette; undo/redo; autosave; crash recovery; import/export; missing-media detection; pre-service checks; emergency clear/blackout; per-layer clearing; operator multiview; macros (R6); scheduled cues (R6); scripture system; multiple independent outputs; stage/confidence displays; lower thirds; timers + TIME UP; media playback; mobile control + pairing; live transcription (R3); automatic scripture detection (R4); AI sermon notes (R5); production integrations (R6). **TTS: removed (NG-1).**

## 13. Functional requirements

Format: `ID | Requirement | Priority | Acceptance criteria (measurable) | Trace`. Every requirement is independently testable. Acceptance-criteria conventions in §29.

### EPIC-A — Service planning & library (MVP)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-001 | Create/edit/delete a service plan (run sheet) of ordered items | MVP | Plan persists ≥50 items of mixed types; reorder via drag; survives restart | RP-01; FLOW-001 |
| FR-002 | Item types in a plan: slide group, song, scripture, media, announcement, timer, section header | MVP | Each type addable, editable, removable; renders correct live behaviour when triggered | RP-01 |
| FR-003 | Presentation library of reusable documents (slides/songs/scripture sets/media refs) | MVP | Library search returns matches <300ms for ≤5k items; items reusable across plans | RP-01 |
| FR-004 | Per-item planned timing and responsible-person annotation | MVP | Item shows planned duration + owner; sum shown as planned service length | RP-12 |
| FR-005 | Duplicate, template, and version a service plan | MVP | "Save as template" and "duplicate" produce independent copies; last-3 autosave versions restorable | RP-01 |
| FR-006 | Publish/hand-off a plan to the live operator view | MVP | Coordinator marks plan ready; operator opens identical ordered plan; no data mismatch | RP-12; FLOW-001 |
| FR-007 | Missing-media detection at plan open and pre-service check | MVP | Opening a plan flags every item whose media file is missing/moved with a remediation prompt | brief §pre-service |
| FR-008 | Pre-service checklist (outputs, media, audio input, storage, pairing) | MVP | One screen reports each subsystem OK/attention with actionable detail | RP-reliability |

### EPIC-B — Slides & content editing (MVP)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-009 | Create/edit slides with text, background, and layered elements | MVP | Text/box/image layers add/edit/reorder; changes render identically on preview and live | RP-01 |
| FR-010 | Reusable templates and themes (fonts, colours, safe areas, positions) | MVP | Applying a theme restyles a slide group without losing content; theme editable centrally | RP-01 |
| FR-011 | Announcements and sermon-point slide types | MVP | Both types creatable from templates; display on selected outputs | brief §core |
| FR-012 | Preview (staged) vs Live (program) separation | MVP | Editing/staging never changes live output until "go live" is invoked | RP-01; JTBD-1 |
| FR-013 | Current-slide and next-slide operator views | MVP | Operator sees current + next thumbnails reflecting live state within ≤100ms (about one frame) | RP-12 |
| FR-014 | Keyboard shortcuts for core live actions (next/prev/clear/blackout/go-live) | MVP | All core actions have documented, remappable shortcuts; work without mouse | RP-12; a11y |
| FR-015 | Command palette for quick action/item search | MVP | Palette opens via shortcut; fuzzy-search actions & plan items; execute selected | RP-01 |
| FR-016 | Undo/redo for editing operations | MVP | ≥20-step undo/redo for edit actions; live triggering is not "undone" destructively | RP-01 |
| FR-017 | Unicode + multi-language text (Latin + diacritics incl. Yoruba/Hausa/Igbo/French/Spanish) | MVP | Diacritic glyphs shape/render correctly on output; font fallback covers the character set | OD-22; brief §scripture |
| FR-018 | RTL / complex-script text rendering | R6 | Arabic/Hebrew shape with correct bidi/joining on output (scoped later per NG-6) | OD-22 |

### EPIC-C — Songs & lyrics (MVP)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-019 | Create/edit songs as ordered lyric sections (verse/chorus/bridge/tag) | MVP | Sections labelled, reorderable; each renders as one or more slides | RP-01 |
| FR-020 | User-supplied lyrics + public-domain hymn bundle only (no bundled copyrighted lyrics) | MVP | App ships PD hymns; user can type/import lyrics; no copyrighted lyrics in the binary | CON-3; LICENSING |
| FR-021 | Copyright-metadata fields (title, author, ©year, publisher, CCLI#) + optional on-slide footer | MVP | Fields captured per song; footer toggle renders attribution on output | LICENSING §3 |
| FR-022 | Streaming-licence reminder when lyrics are sent to a livestream output | R2 | Sending copyrighted lyrics to a stream output surfaces a CCLI streaming-licence reminder | LICENSING §3 |
| FR-023 | Import songs from common formats (OpenSong/OpenLP/ProPresenter/EasyWorship where feasible) | R6 | At least two external formats import with lyrics + section structure preserved | RP-01 differentiation |
| FR-024 | Quick lyric navigation (jump/repeat section) during live | MVP | Operator repeats/jumps a section live in ≤2 actions; reflected on output <1s | JTBD-1 |

### EPIC-D — Scripture system (MVP + later)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-025 | Bundled public-domain translations (WEB, ASV, BSB, BBE, Darby, Webster) | MVP | ≥4 PD translations available offline; no copyrighted translation bundled; **KJV excluded from the bundle** (OD-24 resolved — UK Crown-copyright exposure avoided; WEB/ASV/BSB cover the need) | LICENSING §1; OD-24 |
| FR-026 | Book/chapter/verse navigation | MVP | Navigate to any valid reference; invalid references rejected with guidance | brief §scripture |
| FR-027 | Reference parsing (typed): abbreviations, ranges, multi-selections | MVP | "Rom 8:28-30", "Ps 23", "Jn 3:16; 1 Cor 13:4" parse to correct verse sets | RP-04 (parser) |
| FR-028 | Keyword and exact-phrase search across a translation | MVP | Keyword search returns ranked verse matches <500ms for a bundled translation | brief §scripture |
| FR-029 | Configurable verses-per-slide auto-pagination + verse-number formatting | MVP | Passage paginates by configured verses/slide; verse numbers formatted per setting | brief §scripture |
| FR-030 | Multiple translations + side-by-side comparison | R2 | Two translations display the same passage in a comparison view | brief §scripture |
| FR-031 | Scripture history and favourites | MVP | Last-N presented references listed; favourites persist and re-present in ≤2 actions | brief §scripture |
| FR-032 | Custom scripture templates and per-output scripture layouts | R2 | Different output configs show different verse layouts for the same live passage | brief §multi-output |
| FR-033 | Translation import (user-supplied licensed module) | R4 | User imports a licensed module; text displays with required attribution; not redistributed | LICENSING §1; OD-06 |
| FR-034 | Licensed-translation API integration (API.Bible commercial / ESV) | R4 | Licensed verses fetched via API with attribution + caching within licence limits | OD-06; LICENSING |
| FR-035 | Copyright/attribution metadata display for translations | MVP | Each translation shows required attribution; PD marked as such | LICENSING §1 |

### EPIC-E — Outputs, displays & multiview (MVP + R2)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-036 | Main audience output (fullscreen, per-monitor) | MVP | Main output renders live content fullscreen on a chosen display at native resolution | brief §multi-output |
| FR-037 | Stage/confidence display (current line, next line, clock, timers, messages) | MVP | Stage output shows current+next content, time-of-day, active timer, and stage messages | RP-12; JTBD-3 |
| FR-038 | Independent per-output configuration (resolution, layout, theme, visible layers, safe area) | R2 | Two outputs simultaneously show different layouts/layers of the same live state | brief §multi-output |
| FR-039 | Additional independent outputs (secondary, lobby, overflow, recording) | R2 | ≥3 independent outputs run concurrently with per-output content within perf targets | brief §multi-output |
| FR-040 | Display identification and assignment | MVP | "Identify" shows a number on each physical display; outputs assignable to displays | brief §multi-output |
| FR-041 | Display reconnection restores exact prior live content | MVP | Unplug/replug an output → no other output blanks; content auto-restores on reconnect | FLOW-009 |
| FR-042 | Output health monitoring (connected, resolution, frame health) | R2 | Per-output status shows connected/resolution and flags a dropped-frame condition when >5% of frames drop over a 10s window | RP-12 (livestream) |
| FR-043 | Test patterns per output | R2 | A test pattern can be sent to any output for projector calibration | brief §multi-output |
| FR-044 | Per-output delay, mirroring, rotation, cropping, scaling | R2 | Each transform configurable per output and visibly applied | brief §multi-output |
| FR-045 | Operator multiview (all outputs + preview/next at a glance) | R2 | One screen shows live thumbnails of every output plus preview/next | brief §core |
| FR-046 | Windowed and fullscreen output operation | MVP | Any output runs fullscreen or windowed without restart | brief §multi-output |
| FR-047 | Livestream-specific output layout | R2 | A stream output can show a reduced layout (e.g. 2 lyric lines as lower third) distinct from main | brief §multi-output |
| FR-048 | Transparent/browser-source output for external compositors (OBS/vMix) | R2 | An output exposes a transparent HTML/URL or NDI-alpha feed keyable in OBS/vMix | RP-02; LICENSING NDI |

### EPIC-F — Lower thirds (MVP + R2)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-049 | Lower-third content types (speaker name/title, sermon title, scripture ref, custom text, logo/image) | MVP | Each type creatable from a template and displayable on a selected output | brief §lower-thirds |
| FR-050 | Lower-third templates with entry/exit animation + display duration | R2 | Template defines animation + auto-hide duration; manual hold overrides auto-hide | brief §lower-thirds |
| FR-051 | Lower-third queueing | R2 | Multiple lower thirds queue and play in order without overlap errors | brief §lower-thirds |
| FR-052 | Dedicated transparent lower-third output (alpha) | R2 | A dedicated output renders lower thirds over transparency for key/fill or browser-source | brief §lower-thirds; FR-048 |
| FR-053 | Livestream lower-third layout distinct from room outputs | R2 | Lower third can target the stream output only, never the audience output | RP-12 (livestream) |

### EPIC-G — Timers & TIME UP (MVP)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-054 | Countdown, count-up, time-of-day, elapsed, and segment timers | MVP | Each timer type creatable and accurate to ±100ms against a monotonic clock over 1h | brief §timer; METRIC-004 |
| FR-055 | Timer controls: start/pause/resume/reset/add/subtract time | MVP | Each control takes effect <200ms and is reflected on all outputs showing the timer | brief §timer |
| FR-056 | Multiple simultaneous timers with per-output visibility | MVP | ≥3 timers run at once; each independently shown/hidden per output | brief §timer |
| FR-057 | Warning thresholds and timer presets | MVP | Configurable warning threshold changes timer appearance; presets reusable | brief §timer |
| FR-058 | Operator-only vs stage-visible timer scoping | MVP | A timer can be operator-only (not on audience) or shown on stage/audience per config | brief §timer |
| FR-059 | Configurable "TIME UP" state at zero (text, colour, background, flash/static, per-output) | MVP | At 0 the configured TIME UP state renders on selected outputs only; wording customisable | brief §timer; FLOW-003 |
| FR-060 | TIME UP overrun into negative time with elapsed-over display | MVP | After 0, timer continues showing how far over the speaker is | brief §timer |
| FR-061 | TIME UP dismissal (manual, auto), extend-time, reset, and mobile dismissal | MVP | Each dismissal path clears TIME UP from all outputs; extend adds time and resumes | brief §timer; FR-094 |
| FR-062 | Prevent accidental TIME UP/timer display on audience outputs | MVP | Displaying TIME UP requires explicit output selection; default excludes audience unless chosen | brief §timer; safety |
| FR-063 | Operator alert sound and optional selected-output sound at TIME UP | R2 | Operator hears a local alert at 0; an audible cue to any output requires explicit per-output selection + confirmation and default-excludes audience/house outputs (mirrors FR-062) | brief §timer |
| FR-064 | Timer completion actions / macro trigger + audit log of expiry | R6 | TIME UP can trigger a macro; every expiry is logged with timestamp | brief §timer; FR-144; FR-150 |
| FR-065 | Timer accuracy uses an authoritative monotonic clock (not refresh-driven) | MVP | Timer drift ≤100ms/hour independent of render frame rate | METRIC-004 |

### EPIC-H — Media playback (MVP + R2)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-066 | Image display with scaling/positioning | MVP | PNG, JPEG, WebP, static GIF, and BMP display on output with configured scaling | brief §core |
| FR-067 | Video playback via OS-native/HW decoders | MVP | H.264/HEVC/AAC play via platform decoder (no bundled encumbered encoder/decoder, OD-08a); play/pause/seek work | CON-4; OD-08a |
| FR-068 | Audio playback with output-device selection | MVP | Audio plays to a chosen device; never forced onto the transcription-capture path | RP-12 (sound) |
| FR-069 | Motion backgrounds (looping video) behind text | R2 | A looping background composits under text at target frame rate (perf §26) | brief §core |
| FR-070 | Missing-media placeholder (never a black audience screen) | MVP | A missing media item shows a safe placeholder on output, never an unintended black screen | RP-reliability; FLOW pre-service |
| FR-071 | Media preloading and bounded, evictable media cache | R2 | Next media preloads; cache respects a configured ceiling and evicts LRU | METRIC-003; perf |
| FR-072 | SelahCue-encoded/exported media uses royalty-free codecs (VP9/AV1 + Opus) | R2 | Any media SelahCue encodes/exports is VP9/AV1+Opus (codec safe harbor) | CON-4; LICENSING §2.1 |
| FR-073 | Hardware-decode path constrained to platform elements (no gst-libav for encumbered codecs) | MVP | Build uses platform/HW-decode only for H.264/HEVC; verified in dependency audit (promoted to MVP alongside FR-067, per Stage-3 review C-6) | OD-08a; C8 |

### EPIC-I — Live operation, autosave & recovery (MVP)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-074 | Continuous autosave of plan + live state | MVP | Edits and live-state changes checkpoint automatically; ≤5s of work lost on hard kill | FLOW-008; METRIC-005 |
| FR-075 | Crash recovery + crash-loop breaker | MVP | After forced shutdown, relaunch restores live content, plan position, and running timers (countdowns re-anchored to wall-clock, count-up resumes accumulated). **Crash-loop breaker:** after N rapid crashes the app does not silently auto-resume — it offers "Resume last live state" vs "Start clean / skip last item" and disables the suspected offending item | FLOW-008; MAJOR-02 |
| FR-076 | Emergency clear (per-layer and all-layer) without network | MVP | Clear removes chosen layer(s) from live output <200ms with no network dependency | CON-2; JTBD-6 |
| FR-077 | Emergency blackout (instant) without network | MVP | Blackout blanks audience output(s) <200ms offline; un-blackout restores prior content | CON-2 |
| FR-078 | Per-layer clearing (text/background/lower-third/media independently) | MVP | Each layer clears independently without affecting others | brief §core |
| FR-079 | Database integrity check + safe backup (WAL-aware) | MVP | Integrity check runnable; backups are crash-safe (checkpoint or backup API), never corrupt | RP-08 §7 |
| FR-080 | Automatic backups on a schedule | R2 | Periodic backups created and retained per policy; restore verified | RP-reliability |
| FR-081 | Storage-space warning and safe-mode | R2 | Low-disk warns before capture/record; safe-mode boots with minimal subsystems on repeated crash | RP-reliability |
| FR-082 | Structured logs with rotation + diagnostic report export | R2 | Logs rotate under a size cap; a redacted diagnostic bundle exports on demand | threat T19; observability |
| FR-083 | No AI/transcription/provider failure blocks slide/scripture/timer control | MVP | Cross-cutting architectural invariant; MVP failure-isolation is carried by NFR-024. With AI/providers failing or disabled, all core live controls remain fully operable — meaningful acceptance begins at R3 when AI subsystems land, verified by fault-injection | G-3; CON-2; FLOW-010 |
| FR-084 | Bounded queues/caches and cancellable background tasks | MVP | Background work (indexing, media scan) is cancellable and memory-bounded; no unbounded growth | METRIC-003; perf |

### EPIC-J — Mobile control & pairing (MVP + later)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-085 | Discover desktop hosts on the LAN | MVP | Mobile app lists reachable hosts via mDNS; QR-only fallback works when multicast is blocked | RP-08 §6; C14 |
| FR-086 | QR-code pairing with host-side confirmation | MVP | Scanning a host QR (fingerprint + single-use short-TTL secret) prompts host approval; pairing completes only on approval | threat T1/T18 |
| FR-087 | Remember authorised hosts + secure reconnection (no fresh QR) | MVP | Paired device reconnects via pinned host fingerprint + device proof-of-possession; re-auth each session | threat T8 §3.3 |
| FR-088 | Encrypted, authenticated LAN transport | MVP | All LAN traffic to/from controllers — control, previews, transcript/caption, and media — is TLS 1.3 with a pinned host cert; plaintext rejected; no plaintext preview/transcript egress | threat T2/T3 |
| FR-089 | Per-device revocable tokens bound to a device keypair | MVP | Admin can revoke a device; revocation drops it mid-session immediately | threat T8 |
| FR-090 | Server-side role enforcement for all seven roles (deny-by-default) | MVP | Every command validated against the device's granted role on the host; client-asserted role never trusted | threat T5; §16 |
| FR-091 | Command replay protection + rate limiting | MVP | Duplicate/stale/out-of-window commands rejected (replay window: ±30s clock-skew tolerance + monotonic sequence); per-device+global rate caps enforced; output path isolated | threat T4/T6 |
| FR-092 | Current + next slide preview and service-plan navigation on mobile | MVP | Paired device (role-permitting) sees live current/next and can navigate the plan | RP-12; FLOW-004 |
| FR-093 | Mobile slide/clear/blackout control (role-scoped) | MVP | Role-permitted device advances slides / clears / blacks out; desktop acts <200ms on LAN | METRIC-007; FLOW-004 |
| FR-094 | Mobile timer + TIME UP control (role-scoped) | MVP | Timer Operator role starts/stops/adjusts timers and dismisses TIME UP from mobile | FR-061; §16 |
| FR-095 | Mobile scripture search/display + suggestion approval (role-scoped) | R4 | Scripture Operator role searches, displays, and approves detected suggestions from mobile | RP-12; FLOW-006 |
| FR-096 | Mobile stage-message sending + output-health view (role-scoped) | R2 | Permitted roles send stage messages and view per-output health from mobile | RP-12 |
| FR-097 | Clear connection status + graceful reconnection with no ghost actions | MVP | Connection state always visible; on reconnect, queued stale actions are discarded, live state re-synced | FLOW-010; threat T4 |
| FR-098 | Loss of all mobile devices never disables any desktop capability | MVP | With every mobile disconnected, desktop retains full control | CON-1; FLOW-010 |

### EPIC-K — Live transcription (R3)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-099 | Select audio input device/interface and monitor input level | R3 | Operator picks an input; a live level meter reflects signal; selection persists | RP-12 (sound) |
| FR-100 | Start/pause/resume/stop transcription | R3 | Each control takes effect and is reflected in transcript state within 1s | brief §transcription |
| FR-101 | Offline transcription default (Whisper family) with hardware-based model auto-select | R3 | On first run a hardware probe selects a model that sustains real-time; a warning shows if it cannot | RP-03; C13 |
| FR-102 | Mandatory VAD gating to suppress silence/music hallucination | R3 | On the FR-171 non-speech evaluation set, ≤1% of non-speech seconds produce **committed** transcript text (the surface detection/notes consume; verbatim display is OFF by default per FR-166) — provisional cap, ratified after Stage-10 | RP-03/04; capability |
| FR-103 | Interim (provisional) vs confirmed transcript segments with timestamps | R3 | Interim text shown in a distinct provisional style; confirmed segments carry timestamps and persist | RP-03; FLOW-005 |
| FR-104 | Transcription degrades gracefully on insufficient hardware (pause/smaller model/"degraded" status) | R3 | When real-time cannot be sustained, status shows "degraded/paused"; slide control unaffected | C13; capability §4 |
| FR-105 | Transcript persistence, autosave, and session recovery | R3 | A transcription session survives app restart with no committed-segment loss | brief §transcription |
| FR-106 | Transcript correction editing (non-destructive over an immutable raw stream) | R3 | Corrections edit a display layer without altering the stored raw token stream | RP-adjacent C1; C6 |
| FR-107 | Transcript search, bookmarks, and sermon markers | R3 | Operator searches the transcript and sets/jumps bookmarks and markers | brief §transcription |
| FR-108 | Per-church custom vocabulary / keyword boosting | R3 | A glossary biases recognition; on the FR-171 evaluation set, added terms reduce their per-term word-error rate by ≥20% relative in an A/B test vs no glossary | RP-adjacent C1; MAJOR-06 |
| FR-109 | Editable, non-authoritative speaker labels (best-effort diarization) | R3 | Speaker labels are editable and clearly marked non-authoritative | capability §2.8; m5 |
| FR-110 | Transcript export (TXT, Markdown, JSON token-level, SRT, WebVTT, PDF) | R3 | Each format exports and re-imports/opens correctly with timestamps where applicable | brief §transcription; C1 |

### EPIC-L — Automatic scripture detection (R4)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-111 | Staged detection pipeline: deterministic reference parse → exact → fuzzy → semantic → confidence | R4 | Pipeline runs on the live transcript; deterministic parser results outrank semantic guesses | RP-04 |
| FR-112 | Deterministic spoken-reference parsing (spoken numbers, book aliases) | R4 | "John three sixteen", "first Corinthians thirteen", "Psalm twenty-three one to six" parse correctly on clean audio | RP-04 |
| FR-113 | Quote/paraphrase matching (fuzzy + semantic) surfaced as suggestions only | R4 | Verbatim quotes match; paraphrase surfaces candidates; semantic-only never auto-displays | RP-04; capability |
| FR-114 | Confidence scoring + duplicate suppression + cooldown | R4 | Each suggestion carries a confidence; repeats within a cooldown window (default 60s, configurable) and the on-screen passage are suppressed | RP-04 |
| FR-115 | Three operating modes: suggest-only, operator-confirmation (default), auto-display (high-confidence explicit only) | R4 | Default mode requires confirmation; auto-display available only for explicit refs above a threshold | RP-04; capability §2.7 |
| FR-116 | Auto-display corroboration gate + strong-discouragement warning | R4 | Enabling auto-display shows the wrong-verse risk; a corroboration check is required before unattended display; semantic-only barred | C7; capability §2.7 |
| FR-117 | Suggestion card: reference, passage, translation, confidence, alternatives, reason, approve/reject/edit/display/ignore/undo | R4 | Every suggestion exposes all listed actions; quick-undo reverts a display within 5s | brief §detection |
| FR-118 | Detection history and correction/feedback | R4 | A history log records detections + operator decisions; corrections are recordable | brief §detection |
| FR-119 | Detection never blocks or overrides manual scripture control | R4 | Manual search/display remains available and authoritative regardless of detector state | CON-2; capability |
| FR-120 | Documented accuracy limits surfaced to operator (no perfect-accuracy claim) | R4 | Product UI/docs state detection is reliable for explicit refs, fallible for quotes, unreliable for paraphrase | brief §detection; capability |
| FR-121 | Accent/noise handling posture: precision-over-recall defaults | R4 | Default thresholds favour precision; false-positive rate ≤5% on the FR-171 explicit-reference evaluation set (provisional ceiling, ratified after Stage-10) | RP-04; METRIC-009 |

### EPIC-M — Sermon intelligence (R5)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-122 | Generate structured sermon notes from a stored transcript | R5 | Notes produce title(s), main/supporting scripture, intro, points/sub-points, illustrations, quotes, prayer points, calls-to-action, key lessons, summary | brief §sermon-notes; FLOW-007 |
| FR-123 | Notes are editable, labelled AI-generated, and never overwrite the source transcript | R5 | Editing notes leaves the raw transcript unchanged; AI-generated label present | C6; brief |
| FR-124 | Timestamp-linked notes + chapter/YouTube-chapter markers | R5 | Note items link back to transcript timestamps; chapter markers exportable | brief §sermon-notes |
| FR-125 | Auto-extracted scripture references verified against the local Bible index, flagged unverified until matched | R5 | Any reference in generated notes is checked against the index; unmatched refs marked "unverified" | C6; capability §2.9 |
| FR-126 | Summaries, social-media excerpts, podcast show notes, short description, full outline | R5 | Each artifact generates and is independently editable/exportable | brief §sermon-notes |
| FR-127 | Note export (TXT, Markdown, PDF, DOCX, JSON, clipboard) | R5 | Each export format produces a well-formed file/clipboard payload | brief §sermon-notes |
| FR-128 | Fabrication-risk disclosure in the notes UI | R5 | UI states notes may fabricate/misattribute and require human review before publish | C6; capability §2.9 |
| FR-129 | Regenerate/re-run notes with different provider/settings | R5 | Operator re-runs generation; prior version retained until replaced | brief §sermon-notes |
| FR-130 | Post-service editor access to transcript + notes + detected-scripture list | R5 | Editor persona opens saved transcript, notes, and detections in an editable workspace | RP-12 (editor) |

### EPIC-N — AI provider framework (R3+)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-131 | Provider abstraction for STT and note-generation (local default + pluggable cloud) | R3 | Switching provider requires no core-flow change; local default always present | RP-03/05 §4 |
| FR-132 | Cloud providers OFF by default; opt-in per provider with visible disclosure | R3 | No audio/transcript/notes leave the host until a per-provider opt-in is accepted; the disclosure names the provider, what data is sent, and that data leaves the local network/jurisdiction (see FR-177) | CON-5; threat T10 |
| FR-133 | Live "cloud active" indicator whenever data is sent off-device | R3 | An unmistakable indicator shows while any cloud provider is transmitting | threat T10 §5 |
| FR-134 | User-supplied API keys stored only in the OS secret store | R3 | Keys never in plaintext config/logs; stored in Keychain/DPAPI/Secret Service; "remove key" purges | threat T9 §4 |
| FR-135 | Graceful fallback to local provider on cloud error/network loss (never interrupts live output) | R3 | Bounded retry-with-backoff before dropping to local; a defined failover order for multi-provider configs; falls back without blanking output; transcription may degrade | RP §4; CON-2 |
| FR-136 | Usage visibility + estimated cost + data-retention disclosure per provider | R3 | Operator sees usage/cost estimate and the provider's retention disclosure link before/while using it | brief §AI |
| FR-137 | Consent + retention state persisted and Administrator-gated | R3 | Consent/retention settings persist, are auditable, and only Administrator can change them | threat §5.3; §16 |

### EPIC-O — Import/export & production integrations (MVP + R6)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-138 | Safe file import (path canonicalisation, zip-slip protection, type allowlist) | MVP | Imports reject `..`/absolute/symlink escapes and disallowed types; extract to a sandboxed dir | threat T11 |
| FR-139 | Export/import a service plan / document set | MVP | A plan exports to a portable bundle and re-imports with items + media refs intact | brief §core |
| FR-140 | NDI output with required attribution + License-ID compliance | R2 | NDI output publishes to the LAN; UI shows ndi.video attribution; runtime kept current | LICENSING §2.6; C14 |
| FR-141 | Browser-source (transparent HTML/URL) output endpoint | R2 | An OBS/vMix browser source renders SelahCue lower-third/stage content with transparency | RP-02; FR-048 |
| FR-142 | Bitfocus Companion module / Stream Deck plugin | R6 | An official Companion module triggers slides/timers/scenes; buttons act <300ms | RP-02 differentiation |
| FR-143 | MIDI/OSC control surface support | R6 | SelahCue responds to configurable MIDI/OSC triggers for core live actions | brief §integrations |
| FR-144 | Macros and automation | R6 | A macro chains ≥3 actions and is triggerable from UI/mobile/timer within permissions | brief §core; FR-064 |
| FR-145 | Scheduled cues | R6 | A cue fires a plan action at a scheduled time or offset | brief §core |
| FR-146 | Data export honours licensing (no redistribution of licensed translations/lyrics) | R4 | Exports of licensed content are blocked or watermarked per licence; PD content exports freely | LICENSING |

### EPIC-P — Administration, users & security features (MVP)

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-147 | User/role management (create, assign role, revoke) | MVP | Admin creates users, assigns one of seven roles, and revokes access effective immediately | §16; RP-12 |
| FR-148 | Pairing management screen (view/rename/revoke devices) | MVP | Admin sees every paired device and can rename/revoke each | threat T8 |
| FR-149 | Time-boxed / event-scoped mobile grants | R2 | A grant can auto-expire at a set time/end-of-service | OD-15 |
| FR-150 | Append-only audit log (who changed live output / sent command / changed consent) | MVP | Every live-control and consent change logs device, role, action, timestamp, result; log is append-only | threat T7 |
| FR-151 | Output/display configuration management | MVP | Admin configures outputs/displays and persists profiles per venue | brief §multi-output |
| FR-152 | Provider & key configuration (secure) | R3 | Admin configures providers and keys via the secret store; keys never shown in plaintext after entry | FR-134 |
| FR-153 | Configurable data retention + reliable deletion of recordings/transcripts/notes | R3 | Retention policy configurable with a conservative provisional default (raw audio purged after 7 days unless explicitly kept; transcripts/notes retained), revisable post-measurement (OD-09); delete removes all copies incl. derived artifacts; cloud-copy limits disclosed | threat T17 §5.2 |
| FR-154 | At-rest confidentiality for the primary datastore + captured audio | R3 | App-managed encryption (SQLCipher) is the default acceptance path; if relying on OS full-disk encryption instead, the app verifies FDE is enabled and warns/blocks sensitive capture when FDE is unconfirmed (assumption recorded §9/§21) | C9; OD-21 |
| FR-155 | Signed application updates with signature verification + anti-rollback | MVP | Updates apply only if signature verifies; downgrade below min-version rejected; heeds Sparkle CVE-2025-0509 class | threat T14 |
| FR-156 | Local AI-model integrity verification before load | R3 | Model files verified by pinned hash/signature before load; mismatch refuses to load | threat T13 |
| FR-157 | Backup encryption + untrusted-location warning | R2 | Backups use authenticated encryption; exporting to a user-chosen location warns about sensitivity | threat T15 |
| FR-158 | Congregation-recording consent affordance | R3 | A setting/notice supports disclosing that service audio may be recorded | LICENSING §4; privacy |
| FR-159 | Linux secret-storage fallback never silently plaintext | R3 | With no Secret Service present, the app uses passphrase-derived encryption or refuses to persist — never plaintext | threat §4; OD-19 |

### EPIC-Q — Coverage requirements (Stage-3 review discharge)

Added to close Stage-3 pre-audit review gaps ([PRD-REVIEW-stage3.md](../audits/PRD-REVIEW-stage3.md)).

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-160 | GPU/renderer device-loss & media-decoder failure recovery | MVP | An isolated per-output decoder failure recovers (software-decode fallback) without affecting other outputs. A whole-device GPU loss (TDR/driver reset) — which drops all shared-GPU outputs at once — causes no content loss or operator rebuild and recovers affected outputs within a bounded time (≤3s target), holding the last presented frame where possible; no full app restart | C-1; MAJOR-04; NFR-024 |
| FR-161 | Audio-output-device disconnection/reconnection handling | MVP | Audio-device loss is detected and surfaced; on reconnect, playback resumes to the selected device; audio is never forced onto an unintended device | C-2; FR-068; NFR-024 |
| FR-162 | Desktop stage-message authoring & sending | MVP | Operator composes and sends a stage message to the stage/confidence output; it displays and clears on command | C-10; RP-12 |
| FR-163 | Per-output frame-rate configuration | R2 | Each output's target frame rate is configurable and applied | C-10; brief §multi-output |
| FR-164 | Mobile lower-third, live-transcript view, and sermon-note-status controls (role-scoped) | R2 | Permitted roles control lower thirds, view the live transcript, and see sermon-note status from mobile | C-10; RP-12 |
| FR-165 | Manual fuzzy/semantic scripture search (operator-initiated) | R4 | Operator runs a fuzzy/semantic search over the local Bible index and stages a result manually | C-10; RP-04 |
| FR-166 | Verbatim ASR on-screen caption display (OFF by default) | R3 | Verbatim transcript captioning to an output is an advanced opt-in, OFF by default; interim text uses provisional styling | C-10; capability §1.6 |
| FR-167 | Transcription language & accent/locale selection | R3 | Operator selects transcription language/locale; selection persists and is applied to the recognizer | C-10; RP-03 |
| FR-168 | Mobile macro triggering (role-scoped) | R6 | Production Operator/Administrator trigger permitted macros from mobile | RP-12; §16; FR-144 |

### EPIC-R — Audit-discharge requirements (Stage-4 audit)

Added to close the 17 majors from the Stage-4 audit ([PRD-AUDIT-stage4.md](../audits/PRD-AUDIT-stage4.md)).

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| FR-169 | Storage-exhaustion detection & graceful degradation | MVP | Pre-write low-disk detection warns the operator before autosave/checkpoint/backup writes can fail; a reserved checkpoint headroom protects crash recovery; on a write failure the app degrades gracefully and always surfaces it (never silent) | MAJOR-01; NFR-024 |
| FR-170 | Transcription capture-device disconnect handling | R3 | On audio-input-device loss, transcription pauses (does not crash), captured segments are preserved, a visible gap marker is inserted on reconnect/new-input selection, transcription resumes, and slide control is unaffected | MAJOR-03; WORKFLOWS F2 |
| FR-171 | AI evaluation-set definition (benchmark corpora) | R3 | A defined evaluation-set artefact specifies the composition, source, size, and scoring protocol of the non-speech and explicit-reference test sets; FR-102/FR-108/FR-121/METRIC-009 reference it by name; delivered before Stage-10 measurement (spike S11) | MAJOR-05/06 |
| FR-172 | Audio-feedback / self-re-transcription guard | R3 | While app-emitted media/alert audio (FR-063/068/069) is routed to a shared/house output, transcription ingestion is suppressed/paused and scripture-detection firing is gated; the operator is warned and mic-source guidance is documented | MAJOR-08; capability §1.2/1.3 |
| FR-173 | Untrusted-media/font decode hardening | MVP | Imported media/fonts decode via memory-safe or actively-maintained decoders with header/type/size validation before full decode; decode is isolated/sandboxed where platform-feasible; a documented patch cadence applies (deep fuzzing → Stage-13) | MAJOR-09; threat T12 |
| FR-174 | Control-message schema/input validation | MVP | Every LAN control message passes strict schema/type/size/range validation; unknown/oversized fields are rejected; malformed input fails safe (reject + keep last-good output rendered); a fuzz/fault-injection AC covers the parser | MAJOR-10; threat T20 |
| FR-175 | Seizure-safety / reduced-motion | MVP | Any flashing/animated output is bounded to ≤3 flashes per second (WCAG 2.3.1) and a reduced-motion option disables non-essential animation on audience/livestream outputs | MAJOR-12; WCAG 2.3.1 |
| FR-176 | Privacy policy & app-store data disclosures | MVP | A privacy policy is shipped/linked in-product and in each store listing; Apple App Privacy and Google Play Data Safety disclosures are completed for the MVP mobile app | MAJOR-14; LICENSING §5 |
| FR-177 | DPA & cross-border transfer handling (cloud) | R3 | Enabling any cloud provider requires a DPA + cross-border-transfer disclosure; the FR-132 disclosure names the provider, what data is sent, and that data leaves the local network/jurisdiction | MAJOR-14; LICENSING §4 |

## 14. Non-functional requirements

Performance targets are **proposals to be ratified in Stage 5** against a benchmark harness (RP-09 §8); multi-output targets are **spike-gated** (S1/S2, OD-23).

**Reference hardware tiers** (per Stage-3 review C-8): **Tier A (minimum)** = quad-core CPU-only, 8 GB RAM, integrated GPU — must run all MVP single-output presentation NFRs (NFR-001…004, 010, 022–024) and small-model transcription. **Tier B (recommended)** = 6-core+, 16 GB RAM, discrete GPU or Apple Silicon — target for multi-output (NFR-005/006) and larger transcription models (NFR-007/012). Each NFR states or inherits its tier; MVP NFRs bind Tier A unless noted.

| ID | Requirement | Priority | Acceptance criteria | Trace |
|---|---|---|---|---|
| NFR-001 | Startup time | MVP | Cold start ≤3s; warm ≤1s on reference hardware | RP-09 #1 |
| NFR-002 | Idle memory | MVP | ≤300MB resident when idle | RP-09 #2 |
| NFR-003 | Presentation-active memory (1 output) | MVP | ≤1.5GB during active presentation | RP-09 #3 |
| NFR-004 | Slide-trigger latency | MVP | Input→on-screen ≤150ms (goal ≤80ms) | METRIC-002; RP-09 #6 |
| NFR-005 | 1080p60 render (1 output) | R2 | Sustained 60fps, <5% dropped frames on Tier-B hardware (spike-gated: S1/S2) | RP-09 #7 |
| NFR-006 | Multiple independent outputs | R2 | 2–3 independent 1080p60 outputs ≥55fps each (spike-gated S1/S2) | RP-09 #8; OD-23 |
| NFR-007 | Transcription latency | R3 | ≤2s behind live speech (goal ≤1s) on the selected model/hardware (spike-gated: S8) | RP-09 #9 |
| NFR-008 | Scripture-detection latency | R4 | ≤1.5s incremental after transcript segment (INFERRED-Low; spike-gated S8; provisional pending Stage-5/10 measurement) | RP-09 #10 |
| NFR-009 | Mobile-command latency | MVP | Tap→desktop acts ≤200ms on same LAN | METRIC-007; RP-09 #11 |
| NFR-010 | Long-run (8–12h) memory stability | MVP | <5% memory growth over 12h; no unbounded leak | METRIC-003; RP-09 #13 |
| NFR-011 | Background CPU/GPU when idle | R2 | CPU <3% over a 5-min idle sample; GPU stays in low-power state (no periodic wake) when no presentation is active | RP-09 #14 |
| NFR-012 | Transcription model resident memory | R3 | ≤2GB for the selected model (model-dependent; spike-gated: S8) | RP-09 #4 |
| NFR-013 | Media-cache memory | R2 | Bounded ≤1GB, LRU-evictable | RP-09 #5; FR-071 |
| NFR-014 | Cross-platform parity | MVP | Core presentation behaviour identical on Windows, macOS, Linux (test matrix passes on all three) | G-2; CON-1 |
| NFR-015 | Offline operation | MVP | All core live functions operate with the network disabled | CON-2; G-1 |
| NFR-016 | LAN transport security | MVP | All LAN traffic to/from controllers — control, previews, transcript/caption streams, and media — uses TLS 1.3 with a pinned host cert (or authenticated app-layer crypto); no plaintext egress of any control/preview/transcript/media data | threat §3.1; T3 |
| NFR-017 | Secret storage | MVP | All secrets/tokens only in OS secret store; none in plaintext/logs | threat §4 |
| NFR-018 | Cloud data-egress control | R3 | No sermon audio/transcript/notes leave the host without explicit per-provider opt-in | CON-5; threat T10 |
| NFR-019 | Keyboard accessibility | MVP | Every core live action operable by keyboard alone | a11y; FR-014 |
| NFR-020 | Display legibility/accessibility | MVP | Operator UI meets WCAG 2.1 AA **contrast** (≥4.5:1 normal text, ≥3:1 large text/UI); stage/confidence text supports configurable large size (≥48px-equivalent) + high-contrast themes for stage-lighting readability. (AA claim scoped to contrast; photosensitivity/flash safety is FR-175) | a11y; RP-12 |
| NFR-021 | Screen-reader support (desktop) | MVP | MVP: core live desktop controls (next/prev/clear/blackout/go-live, timer/TIME-UP, scripture-stage) expose accessible names/roles to platform screen readers; full screen-reader coverage of all UI is R2 | a11y; MAJOR-13 |
| NFR-022 | Timer accuracy | MVP | ≤100ms/hour drift, independent of render frame rate (monotonic clock) | FR-065; METRIC-004 |
| NFR-023 | Autosave work-loss bound | MVP | ≤5s of work lost on forced shutdown | FR-074; METRIC-005 |
| NFR-024 | Output-failure isolation | MVP | No AI / media-decoder / audio-device / network / display / mobile / storage-exhaustion failure blanks or clears live output as a side effect; an isolated per-output decoder failure never affects other outputs; a whole-device GPU loss (TDR/driver reset) causes no content loss or operator rebuild and recovers affected outputs within a bounded time, holding the last presented frame where possible. Verified via fault-injection incl. storage exhaustion and GPU device-loss | CON-2; G-1; METRIC-001; FR-160/161/169 |
| NFR-025 | Localisation readiness | R2 | UI strings externalised for translation; no hard-coded user-facing strings in core flows | brief §core |
| NFR-026 | Mobile-controller accessibility | MVP | MVP mobile controls expose accessible labels and meet minimum touch-target size (≥44×44pt); full AT coverage is R2 | a11y; MAJOR-13 |
| NFR-027 | Dependency security / supply chain | MVP | CI generates an SBOM and runs automated dependency/CVE + license (GPL/AGPL-exclusion) scanning on every build; a defined patch cadence applies | m10; threat T16 |

## 15. Feature-to-release note

MVP delivers presentation foundation + core mobile control + reliability. R2–R6 layer media/output expansion, transcription, scripture intelligence, sermon intelligence, and integrations. Full mapping in §32 Traceability.

## 16. Permissions

Seven scoped mobile-control roles enforced **server-side on the authoritative desktop** (deny-by-default; client-asserted role never trusted — FR-090). Full matrix (7 roles × **14 capabilities** — the TTS-control capability was removed per DEC-001) in `docs/business/PERSONAS.md` §2. Highlights: Observer view-only; Presenter advances current content; Worship Leader = lyric advance/repeat + stage messages; Scripture Operator is the human gate that approves detected scripture; Timer Operator owns timers/TIME UP; Production Operator near-full minus admin; Administrator alone manages pairing/roles/consent and full live-transcript control. All `⚠️` cells are Administrator-configurable defaults. Enforcement invariant: role downgrade/unpair takes effect immediately; unvalidatable actions are rejected, not queued (FR-097). Open permission decisions (Blackout for lower roles, per-output permissions, event-scoped grants, macro granularity) tracked in OPEN-DECISIONS OD-12…OD-17.

## 17. Data lifecycle

Entities: service plans, library documents, songs, scripture sets, media references, transcripts (raw immutable stream + editable correction layer), detected-scripture history, AI sermon notes, audit log, device pairings, provider consent/retention settings, backups. **Creation:** locally on the desktop host. **Storage:** SQLite (WAL) for structured data; media as path-referenced files; secrets in OS secret store; primary store + captured audio encrypted at rest (FR-154). **Processing:** on-device by default; cloud only on opt-in (FR-132). **Retention:** configurable; conservative default (transcripts/notes retained, raw audio purged after need — OD-09) (FR-153). **Deletion:** reliable delete removes all copies incl. derived artifacts; cloud-copy limits disclosed (FR-153). **Export:** honours licensing (FR-146). **Backup:** crash-safe + encrypted (FR-079/FR-157).

## 18. AI and provider architecture requirements

Provider abstraction per capability (STT, note-generation) with a local default always present and pluggable cloud adapters (FR-131). Offline-first; cloud OFF by default, opt-in + visible disclosure + "cloud active" indicator (FR-132/133); user-supplied keys in OS secret store (FR-134); graceful local fallback on cloud/network failure never interrupting live output (FR-135); usage/cost/retention visibility (FR-136); Administrator-gated consent/retention (FR-137). AI never blocks core presentation (FR-083; NFR-024). Realistic-capability posture (no perfect-accuracy claims), operator-in-the-loop defaults, and disclosed failure modes (FR-120/128; capability assessment). TTS is a non-goal (NG-1).

## 19. Offline behaviour

Core live presentation (slides, local scripture from bundled PD translations, media, blackout/clear, timers, stage/confidence outputs) is fully operable with no network, cloud, or mobile connectivity (NFR-015; CON-2). Mobile control operates over the LAN without internet. Transcription/detection run offline by default (FR-101). Cloud features degrade gracefully to local on connectivity loss (FR-135). Emergency clear/blackout work with no network (FR-076/077).

## 20. Security

LAN control plane is the primary attack surface. Controls: TLS 1.3 + QR-pinned host fingerprint (NFR-016), single-use short-TTL QR pairing + host confirmation (FR-086), per-device revocable keypair-bound tokens (FR-089), server-side RBAC (FR-090), per-command nonce+timestamp replay protection + rate limiting with output isolation (FR-091), OS-secret-store-only secrets (NFR-017), signed updates + anti-rollback (FR-155), local-model integrity (FR-156), safe file import/path-traversal protection (FR-138), backup encryption (FR-157), append-only audit log (FR-150). Full early threat model: `docs/security/reviews/threat-model-draft.md`; a Stage-13 review revisits all deferred items.

## 21. Privacy

Sermon audio/transcripts/notes are sensitive (NDPA 2023 + GDPR). Cloud OFF by default, opt-in per provider with visible disclosure (NFR-018; FR-132), live cloud indicator (FR-133), configurable retention + reliable deletion (FR-153), congregation-recording consent affordance (FR-158), at-rest encryption (FR-154), no secrets/transcripts in logs (FR-082). No transcript/audio leaves the host without explicit user action.

## 22. Accessibility

Full keyboard operation of core live actions (NFR-019; FR-014); WCAG 2.1 AA **contrast** (≥4.5:1 normal, ≥3:1 large/UI) with configurable large-text (≥48px-equiv) and high-contrast stage/confidence legibility (NFR-020); **seizure-safety / reduced-motion** — flashing/animated output bounded to ≤3/sec (WCAG 2.3.1, FR-175); localisation-ready UI (NFR-025). **MVP assistive-technology baseline (per Stage-4 audit MAJOR-13):** MVP ships accessible names/roles on **core live desktop controls** (NFR-021) and accessible labels + ≥44×44pt touch targets on the **mobile controller** (NFR-026); full screen-reader coverage of all UI is R2. This makes the DEC-001 TTS-removal rationale consistent — the compensating accessibility path (keyboard + contrast + AT-labelled core controls) is present in MVP, not deferred. TTS remains a non-goal (NG-1).

## 23. Reliability

8–12h continuous operation (NFR-010); continuous autosave (FR-074; NFR-023); crash/forced-shutdown recovery restoring exact live state (FR-075); output-failure isolation — no failure blanks/clears output (NFR-024; FR-083); display/audio/mobile/network/provider disconnection handled gracefully (FR-041/068/097/135); database integrity + crash-safe backups (FR-079); missing-media placeholder (FR-070); storage warnings + safe mode (FR-081); bounded queues/caches + cancellable tasks (FR-084); structured logs + diagnostics (FR-082).

## 24. Performance

Measurable targets in §14 (NFR-001…013, NFR-022). Model lazy-loading (FR-101), media preloading + bounded evictable cache (FR-071/NFR-013), monotonic-clock timing (FR-065/NFR-022). Multi-output + 1080p60 targets are spike-gated (S1/S2, OD-23) and ratified in Stage 5 before becoming committed. Low CPU/memory is a first-class goal (NFR-001…003, 010, 011).

## 25. Licensing

Bundle public-domain Bibles only; licensed translations API-only/user-supplied (FR-025/033/034; CON-3). No bundled copyrighted lyrics; copyright-metadata + CCLI affordances (FR-020/021/022). OS-native codecs; VP9/AV1+Opus for encoded media; no bundled encumbered encoder; platform/HW-decode-only GStreamer elements (FR-067/072/073; CON-4; OD-08a). NDI attribution + License-ID + current runtime (FR-140). Fonts OFL/Apache, icons MIT/ISC; Whisper MIT on-device. NDPA/GDPR for sermon data (§21). SBOM + no GPL/AGPL in the proprietary build (dependency policy). Legal-confirmation items (ESV/API.Bible commercial, cloud-AI terms, NDI 6 EULA, codec path, unfoldingWord share-alike) gate only their specific later features. Full register: `docs/research/LICENSING-REGISTER.md`.

## 26. Risks

Full register + scoring: `docs/delivery/RISK-REGISTER.md`.

| ID | Risk | Mitigation (in PRD) |
|---|---|---|
| RISK-001 | Scope breadth vs one release (two-product MVP surface: cross-platform GPU-compositing suite + hardened LAN control plane) | MVP bounded (§30); phased R2–R6; **intra-MVP sequencing** — ship a presentation-core desktop sub-release *before* the mobile control-plane slice (AS-1/AS-6, Stage 7); capacity assumption recorded (AS-6); validator + audit check MVP coherence |
| RISK-002 | Bible-translation licensing | PD-only bundle (FR-025); licensed = API/user-supplied (FR-033/034); CON-3 |
| RISK-003 | Scripture-detection accuracy | Operator-confirmation default (FR-115), precision-over-recall (FR-121), disclosed limits (FR-120) |
| RISK-004 | Offline transcription performance | Hardware model auto-select (FR-101), graceful degradation (FR-104), spike S8 |
| RISK-005 | Live-service reliability | Output-failure isolation (NFR-024), recovery (FR-075), offline core (NFR-015) |
| RISK-008 | (Retired — TTS de-scoped, DEC-001) | n/a |
| RISK-010 | Sermon-data privacy | Opt-in cloud (FR-132), at-rest encryption (FR-154), retention/delete (FR-153) |
| RISK-011 | Version control (resolved: git initialised) | n/a |
| RISK-012 | Tauri-WebView-as-compositor tension | Architecture leans Rust core + wgpu + native output; Stage-5 ADR + spikes S1/S2 (OD-23) |
| RISK-013 | Multi-output 1080p60 feasibility | NFR-006 spike-gated; fallback architecture required before committing (OD-23) |
| RISK-014 | MVP dual-output (main + stage/confidence) independent fullscreen + hot-plug robustness depends on unproven spike S4 | Run spike S4 (FEASIBILITY §10) before committing FR-040/041; borderless-per-monitor + manual placement fallback; MVP dual-output is best-effort until S4 passes |

## 27. Dependencies

- **External:** OS-native media decoders (per platform); NDI SDK (attribution/License-ID); Whisper (MIT) + local LLM runtime; public-domain Bible data (eBible.org/open.bible, USFM/USX); code-signing certificates per OS; (later) licensed-translation APIs, cloud AI/STT providers; ClickUp MCP (delivery).
- **Internal:** Stage 5 ADRs (stack, UI shell, windowing, media engine, LAN protocol, NDI, at-rest encryption) and feasibility spikes S1–S10 gate committing NFR-005/006 and the render/media architecture; PM artifact validator (this stage).
- **Legal (gate later features only):** ESV/API.Bible commercial terms, cloud-AI data terms, NDI 6.x EULA, codec-patent path, unfoldingWord share-alike (OD-06/08).
- **Compliance accepting authority:** a legal/compliance reviewer **outside the engineering roster** is the accepting authority for licensing/privacy requirements (FR-021/022/034/140/146/153/158/176/177); recorded per-requirement in ClickUp ownership at Stage 6.

## 28. Open questions

Tracked in `docs/research/OPEN-DECISIONS.md` (OD-01…OD-24). Still open at PRD time: pricing/positioning (OD-04); licensed-translation commercial strategy + legal confirmations (OD-06/08); permission questions (Blackout for lower roles OD-12, per-output permissions OD-14, macro granularity OD-17); retention defaults (OD-09); LAN transport final choice (OD-18); Linux secret fallback (OD-19); multi-controller conflict resolution (OD-20). Deferred Stage-2 review conditions carried as requirements: C2→FR-017/018+S10, C8→FR-073, C9→FR-154, C10→NFR-006/OD-23, C14→FR-085/140. Stage-2 minor-condition backlog (C11/C12) discharged into requirements: reliability/decoder/GPU/audio recovery→FR-160/161, storage-warning/safe-mode/logs→FR-081/082, diarization candour→FR-109, accessibility→NFR-019/020/021/026; the remaining C12 items (citation spot-checks, secondary-figure calibration) are discovery-doc hygiene tracked in `docs/research/CONDITION-DISPOSITIONS.md`, not PRD requirements.

## 29. Acceptance criteria (conventions)

Every FR/NFR row's **Acceptance criteria** column is its normative, testable pass condition — measurable (a number, a state transition, or an observable behaviour), verified by QA from Stage 8 onward and mapped to tests in Stage 6 tickets. Criteria avoid subjective terms ("looks good"); performance numbers are the §14 targets (Stage-5-ratified). A requirement is "met" only when its acceptance criteria pass with evidence and independent verification.

## 30. MVP

**MVP = Presentation foundation (desktop Win/macOS/Linux + thin mobile controller).** Scope: service plans & library (EPIC-A), slides & editing incl. Latin/diacritic Unicode (EPIC-B), songs/lyrics user-supplied + PD hymns (EPIC-C), scripture search/display with bundled PD translations (EPIC-D MVP rows), main + stage/confidence outputs with display identification/reconnection (EPIC-E MVP rows), lower-third content types (FR-049), timers + TIME UP (EPIC-G MVP rows), media playback via OS/platform-only HW decoders (FR-067 + FR-073, promoted per C-6) + missing-media placeholder (EPIC-H MVP rows), autosave/crash-recovery/emergency clear/blackout/per-layer + GPU/decoder/audio-device recovery (EPIC-I MVP rows + FR-160/161/162), mobile pairing + slide/timer control with full LAN security + RBAC (EPIC-J MVP rows), safe import/export (FR-138/139), user/role/pairing management + audit + signed updates (EPIC-P MVP rows). Also in MVP (Stage-4 audit discharge): storage-exhaustion handling + crash-loop breaker (FR-169, FR-075), untrusted-media/font decode hardening + control-message validation (FR-173, FR-174), seizure-safety/reduced-motion (FR-175), privacy policy + app-store data disclosures (FR-176), MVP assistive-tech minimums (NFR-021/026), and dependency/SBOM scanning (NFR-027). Reliability, offline, keyboard accessibility, and core Tier-A performance NFRs apply. **Render/media bound (C-5, MAJOR-16):** MVP drives **two concurrent independent outputs** (main audience + stage/confidence), not a single output — dependent on robust independent multi-monitor windowing (spike S4, RISK-014; borderless-per-monitor fallback). MVP video has a testable floor on Tier-A (single-output 1080p30 or 720p60, ≤5% dropped frames) under the NFR-003 memory bound and the METRIC-003 12h soak; the *guaranteed* 1080p60/<5%-dropped bar (NFR-005) and 3+ independent outputs (NFR-006) are R2 and spike-gated. **MVP is realistically bounded** (RISK-001): no transcription/detection/sermon-notes, no multi-output expansion, no integrations, **no TTS** (NG-1).

## 31. Later releases

- **R2 — Media & output expansion:** independent multi-output, per-output config, output health/test patterns, motion backgrounds, transparent lower thirds, NDI, browser-source, livestream layouts, backups/logs/diagnostics, event-scoped grants, screen-reader/localisation.
- **R3 — Transcription:** audio input, offline transcription, interim/confirmed segments, correction, export, provider framework, at-rest encryption, retention/consent.
- **R4 — Scripture intelligence:** staged detection, operator approval, modes, history, licensed-translation import/API.
- **R5 — Sermon intelligence:** AI notes, timestamps, chapters, summaries, excerpts, exports (with reference-verification + fabrication disclosure).
- **R6 — Integrations & hardening:** Companion/Stream Deck, MIDI/OSC, macros, scheduled cues, RTL/complex-script, song importers.

### Success metrics — METRIC definitions

| ID | Metric | Target |
|---|---|---|
| METRIC-001 | Unintended output blanks in live use | 0 across recovery/soak test suite |
| METRIC-002 | Slide-trigger latency (p95) | ≤150ms (goal ≤80ms) |
| METRIC-003 | 12h soak memory growth | <5%, no unbounded leak |
| METRIC-004 | Timer drift | ≤100ms/hour |
| METRIC-005 | Autosave work-loss on hard kill | ≤5s |
| METRIC-006 | New-operator time-to-first-slide | ≤10 minutes (usability test) |
| METRIC-007 | Mobile command latency (p95) | ≤200ms on LAN |
| METRIC-008 | Crash-recovery success | 100% of forced-shutdown tests restore live state |
| METRIC-009 | Scripture-detection false-positive rate (explicit refs) | ≤5% on the explicit-reference test set (provisional; ratified after Stage-10 measurement) |
| METRIC-010 | Cross-platform core test-matrix pass | 100% on Windows/macOS/Linux |

## 32. Launch criteria (MVP)

MVP is launch-ready when: all MVP-priority FR/NFR acceptance criteria pass with evidence; METRIC-001/002/003/004/005/006/007/008/010 meet targets (incl. the 12h soak METRIC-003 and time-to-first-slide METRIC-006); independent code/QA/security reviews pass; no unresolved critical/high security finding; packaging validated on Windows/macOS/Linux; crash-recovery + crash-loop-breaker + storage-exhaustion + display/audio/mobile/network-loss recovery tests pass; seizure-safety (≤3 flashes/sec) verified; a published privacy policy + completed App Store/Play data disclosures ship with the MVP mobile app (FR-176); documentation + runbooks complete; PRD audit PASS and Goal Contract validator exits 0.

## 33. Traceability

Every FR maps to exactly one release below; NFRs and METRICs apply cross-cutting. Requirement→ticket mapping is created in Stage 6 (ClickUp). Requirement→test mapping is created with tickets and verified in Stage 8+.

**MVP:** FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-012, FR-013, FR-014, FR-015, FR-016, FR-017, FR-019, FR-020, FR-021, FR-024, FR-025, FR-026, FR-027, FR-028, FR-029, FR-031, FR-035, FR-036, FR-037, FR-040, FR-041, FR-046, FR-049, FR-054, FR-055, FR-056, FR-057, FR-058, FR-059, FR-060, FR-061, FR-062, FR-065, FR-066, FR-067, FR-068, FR-070, FR-074, FR-075, FR-076, FR-077, FR-078, FR-079, FR-083, FR-084, FR-085, FR-086, FR-087, FR-088, FR-089, FR-090, FR-091, FR-092, FR-093, FR-094, FR-097, FR-098, FR-138, FR-139, FR-147, FR-148, FR-150, FR-151, FR-155, FR-073, FR-160, FR-161, FR-162, FR-169, FR-173, FR-174, FR-175, FR-176

**R2 (media & output expansion):** FR-022, FR-030, FR-032, FR-038, FR-039, FR-042, FR-043, FR-044, FR-045, FR-047, FR-048, FR-050, FR-051, FR-052, FR-053, FR-063, FR-069, FR-071, FR-072, FR-080, FR-081, FR-082, FR-096, FR-140, FR-141, FR-149, FR-157, FR-163, FR-164

**R3 (transcription):** FR-099, FR-100, FR-101, FR-102, FR-103, FR-104, FR-105, FR-106, FR-107, FR-108, FR-109, FR-110, FR-131, FR-132, FR-133, FR-134, FR-135, FR-136, FR-137, FR-152, FR-153, FR-154, FR-156, FR-158, FR-159, FR-166, FR-167, FR-170, FR-171, FR-172, FR-177

**R4 (scripture intelligence):** FR-033, FR-034, FR-095, FR-111, FR-112, FR-113, FR-114, FR-115, FR-116, FR-117, FR-118, FR-119, FR-120, FR-121, FR-146, FR-165

**R5 (sermon intelligence):** FR-122, FR-123, FR-124, FR-125, FR-126, FR-127, FR-128, FR-129, FR-130

**R6 (integrations & hardening):** FR-018, FR-023, FR-064, FR-142, FR-143, FR-144, FR-145, FR-168

**NFRs (cross-cutting):** NFR-001…NFR-027 apply across releases per their listed priority. **METRICs:** METRIC-001…METRIC-010. **FLOWs:** FLOW-001…FLOW-010. **RISKs:** RISK-001…RISK-014.

## 34. Stage-3 pre-audit review discharge

An independent fresh-context 4-lens pre-audit review ([PRD-REVIEW-stage3.md](../audits/PRD-REVIEW-stage3.md)) returned **PASS WITH CONDITIONS** (0 blockers, 10 majors, 12 minors). All conditions were discharged in this PRD before the Stage-4 formal audit:

- **C-1** GPU/renderer + decoder recovery → FR-160; NFR-024 extended.
- **C-2** audio-device loss/reconnect → FR-161; NFR-024 extended.
- **C-3** concrete AI thresholds → FR-102 (≤1% non-speech), FR-121/METRIC-009 (≤5% FP, provisional).
- **C-4** thin-controller reconciliation → AS-1 note (two hardened subsystems).
- **C-5** MVP render/media bound → §30 render/media clause.
- **C-6** platform-only decode to MVP → FR-073 promoted to MVP.
- **C-7** spike-gate parity → NFR-005/007/008/012 annotated (NFR-008 added per Stage-4 MAJOR-17).
- **C-8** reference-hardware tiers → §14 Tier-A/B definition.
- **C-9** measurable accessibility → NFR-020 (WCAG AA), NFR-021/026, §22 MVP screen-reader decision.
- **C-10** coverage gaps → FR-162…FR-167 (stage-message authoring, per-output fps, mobile lower-third/transcript/note-status, manual fuzzy/semantic search, verbatim-caption default-OFF, language/accent selection).
- **C-11** citation typos fixed (FR-061→FR-094, FR-064→FR-144/FR-150); §28 backlog mapping added.

FR count after Stage-3 discharge: 168 (159 + EPIC-Q 9); NFR 26.

## 35. Stage-4 formal-audit discharge

The formal Stage-4 independent audit ([PRD-AUDIT-stage4.md](../audits/PRD-AUDIT-stage4.md)) returned **PASS WITH CONDITIONS** (0 blockers, 17 majors, 16 minors). All 17 majors were discharged in this revision (material minors folded in):

- **MAJOR-01** storage exhaustion → FR-169 (MVP) + NFR-024.
- **MAJOR-02** crash-loop breaker → FR-075 (MVP).
- **MAJOR-03** transcription capture-device disconnect → FR-170 (R3).
- **MAJOR-04** GPU device-loss reframed (bounded recovery; per-output vs whole-device) → FR-160, NFR-024.
- **MAJOR-05** undefined AI benchmark corpora → FR-171 (eval-set definition); FR-102/108/121/METRIC-009 reference it.
- **MAJOR-06** FR-108 untestable → metric + ≥20% relative threshold + A/B on FR-171 set.
- **MAJOR-07** TTS de-scope in companion docs → PERSONAS §2 (14 caps), §16 count 14, WORKFLOWS A8/B8/F4 de-scoped.
- **MAJOR-08** audio-feedback / self-re-transcription → FR-172 (R3).
- **MAJOR-09** malicious-media decode hardening → FR-173 (MVP).
- **MAJOR-10** control-message schema validation → FR-174 (MVP).
- **MAJOR-11** transport scope → FR-088, NFR-016 broadened to all LAN traffic.
- **MAJOR-12** seizure-safety / reduced-motion → FR-175 (MVP); NFR-020 framing corrected.
- **MAJOR-13** MVP AT minimums → NFR-021/026 pulled to MVP; §22 reconciles DEC-001.
- **MAJOR-14** compliance deliverables → FR-176 (MVP), FR-177 (R3), FR-132, §32 launch.
- **MAJOR-15** RISK-001 sequencing + capacity → RISK-001, AS-6.
- **MAJOR-16** MVP dual-output correction → §30, RISK-014.
- **MAJOR-17** NFR-008 spike-gate → NFR-008, §34 C-7.

Minors folded in: FR-013/025/042/063/066/067/091/102/114/135/153/154 refinements, NFR-011/027, CON-4 (AAC), §27 legal accepting-authority, §32 metrics, KJV dropped (OD-24 resolved). **FR count now 177 (168 + EPIC-R 9); NFR 27.**

---

*End of PRD v1.1 (Stage 4 audit-discharged). Re-audit run to confirm exactly PASS before Stage 5.*




