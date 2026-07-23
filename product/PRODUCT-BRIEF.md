research, define, audit, and decompose a production-ready cross-platform church presentation, scripture, transcription, and sermon-assistance application.

Continue working until:

1. The product research is complete.
2. The PRD has been independently audited.
3. The final PRD audit verdict is PASS.
4. Every approved requirement is represented by one or more implementation tickets or is explicitly deferred.
5. The ticket dependency graph is valid.
6. The PM artifact validator exits successfully.
7. The implementation-readiness report states that the project is ready for specialist agents.

Do not implement the application during this phase. Your responsibility is product discovery, requirements gathering, competitor research, PRD creation, PRD audit, ticket decomposition, release planning, and specialist-agent routing.

Stop as BLOCKED only when a material decision requires information that cannot be determined from the repository, available documentation, browser research, or a clearly documented reasonable assumption.

# Product vision

Define a cross-platform church presentation and ministry-assistance application that combines the strongest ideas from products such as PewBeam and ProPresenter while creating an original product, workflow, architecture, terminology, and interface.

The application should help churches manage:

* Presentation slides.
* Song lyrics.
* Bible scriptures.
* Multiple independent outputs.
* Stage and confidence displays.
* Lower thirds.
* Timers.
* Live transcription.
* Automatic scripture detection.
* AI-generated sermon notes.
* Text-to-speech.
* Mobile remote control.
* Livestream-specific content.
* Media playback.
* Service planning.

The product must be suitable for churches, conferences, concerts, worship events, livestream productions, and sermon recording.

It must prioritise:

* Reliability during live services.
* Low CPU and memory consumption.
* Cross-platform support.
* Fast live operation.
* Offline-first functionality.
* Operator control over AI-generated actions.
* Privacy of sermon recordings and transcripts.
* Recovery from crashes, network loss, display disconnection, or AI-provider failure.

# Target platforms

Research and define requirements for:

* Windows.
* macOS.
* Linux.
* Android mobile controller.
* iPhone and iPad mobile controller.

The mobile application should control the desktop application over the same local network without requiring cloud connectivity for normal presentation control.

# Primary users

Research and define workflows for at least:

* Church media operator.
* Scripture operator.
* Worship leader.
* Pastor or preacher.
* Stage manager.
* Livestream director.
* Sound engineer.
* Service coordinator.
* System administrator.
* Mobile remote user.
* Post-service media or sermon editor.

Document the responsibilities, permissions, needs, pain points, and primary workflows of each relevant role.

# Reference-product research

Use Chrome MCP or any relevant or browser installed agent to study relevant systems through public websites, official documentation, product demos, videos, trial accounts, or authorised accounts where available.

Study at least:

* PewBeam.
* ProPresenter.
* OpenLP.
* FreeShow.
* EasyWorship.
* Quelea.
* Church presentation or scripture-detection tools.
* Live transcription and captioning systems.
* Sermon transcription and sermon-note platforms.
* Text-to-speech platforms.
* Remote presentation-control applications.

Include adjacent systems where useful, such as:

* OBS Studio.
* vMix.
* Blackmagic ATEM Software Control.
* Bitfocus Companion.
* NDI tools.
* Stream Deck.
* Descript.
* Otter.
* Whisper-based transcription applications.
* Speech-to-text services.
* Speech-synthesis services.

Do not merely read landing pages.

Where access permits, study actual workflows such as:

* Creating a service plan.
* Creating slides.
* Importing song lyrics.
* Searching for scriptures.
* Presenting scriptures.
* Configuring stage displays.
* Configuring multiple outputs.
* Creating lower thirds.
* Running timers.
* Controlling presentations remotely.
* Displaying live captions.
* Exporting transcripts.
* Recovering after a problem.
* Handling disconnected outputs.
* Handling missing media.
* Managing templates.
* Assigning permissions.
* Configuring integrations.

For every finding, clearly classify it as:

* OBSERVED.
* DOCUMENTED.
* INFERRED.
* UNKNOWN.

Record evidence, URLs, dates, screenshots where supported, access limitations, plan limitations, and confidence.

Do not copy proprietary code, copyrighted assets, product branding, or interfaces pixel-for-pixel.

# Core presentation requirements

Research and define requirements for:

* Presentation library.
* Service plans or run sheets.
* Slide creation and editing.
* Song lyrics.
* Announcements.
* Sermon points.
* Images.
* Video.
* Audio.
* Motion backgrounds.
* Reusable templates.
* Reusable themes.
* Preview and live states.
* Current and next slide views.
* Keyboard shortcuts.
* Command palette.
* Undo and redo.
* Autosave.
* Crash recovery.
* Import and export.
* Missing-media detection.
* Pre-service checks.
* Emergency clear.
* Emergency blackout.
* Per-layer clearing.
* Operator multiview.
* Macros and automation.
* Scheduled cues.

The PRD should clearly distinguish between MVP requirements and later-release capabilities.

# Multiple-output requirements

The application must support independent outputs such as:

* Main projector.
* Secondary projector.
* Stage display.
* Confidence monitor.
* Livestream output.
* Lower-third output.
* Lobby display.
* Overflow display.
* Recording output.
* Transparent browser-source output.
* Operator multiview.
* Future NDI output.
* Future fill-and-key output.

Research and define how one live presentation should be represented differently on each output.

Example:

* The main projector displays four lyric lines over a motion background.
* The livestream output displays two lyric lines as a lower third.
* The stage monitor displays the current line, next line, clock, and service timer.
* The lobby output continues displaying announcements.
* A dedicated lower-third output has a transparent background.

Define independent output configuration for:

* Resolution.
* Frame rate.
* Orientation.
* Layout.
* Theme.
* Safe areas.
* Visible layers.
* Cropping.
* Scaling.
* Delay.
* Mirroring.
* Rotation.
* Fullscreen and windowed operation.
* Display identification.
* Display reconnection.
* Output health.
* Test patterns.

# Scripture requirements

Research and define a comprehensive scripture system supporting:

* Bible book, chapter, and verse navigation.
* Reference parsing.
* Spoken-reference parsing.
* Abbreviated references.
* Verse ranges.
* Multiple verse selections.
* Keyword search.
* Exact phrase search.
* Fuzzy quote search.
* Semantic scripture search.
* Multiple Bible translations.
* Translation comparison.
* Scripture history.
* Favourites.
* Custom templates.
* Automatic slide pagination.
* Configurable verses per slide.
* Verse-number formatting.
* Per-output scripture layouts.
* Unicode and multiple languages.
* Right-to-left language support where practical.
* Public-domain and properly licensed translations.
* Translation importing.
* Translation copyright and attribution metadata.

Do not assume that copyrighted Bible translations may be bundled without permission.

Document licensing requirements and restrictions.

# Live transcription requirements

The application must capture the pastor’s or speaker’s audio and generate a live transcript.

Research and define requirements for:

* Selecting microphones and audio interfaces.
* Monitoring input levels.
* Selecting an input channel.
* Supporting common church audio interfaces.
* Starting, pausing, resuming, and stopping transcription.
* Interim transcript text.
* Confirmed transcript segments.
* Timestamps.
* Multiple speakers where practical.
* Language selection.
* Accent and dialect considerations.
* Transcript correction.
* Transcript search.
* Bookmarks.
* Sermon markers.
* Session recovery.
* Automatic saving.
* Plain-text export.
* Markdown export.
* JSON export.
* SRT export.
* WebVTT export.
* PDF or document export where useful.

Define separate provider models for:

* Fully offline transcription.
* Cloud transcription.
* Hybrid transcription.
* User-configured transcription providers.

Research appropriate offline and cloud technologies.

Compare them based on:

* Accuracy.
* Latency.
* CPU usage.
* GPU usage.
* Memory usage.
* Internet dependency.
* Privacy.
* Supported languages.
* Streaming support.
* Cost.
* Cross-platform support.
* Integration complexity.
* Licensing.

The PRD must require that cloud transcription is opt-in and visibly indicates when audio is being sent outside the device.

# Automatic scripture detection

The application should analyse the pastor’s live speech and detect scriptures in two main ways.

## Explicit references

Examples:

* “John chapter three verse sixteen.”
* “John 3:16.”
* “Let us read from Romans chapter eight.”
* “Psalm twenty-three from verse one to six.”

## Quoted or paraphrased scriptures

Examples:

* The pastor quotes a verse without mentioning the reference.
* The pastor quotes part of a verse.
* The pastor paraphrases a familiar passage.
* The pastor combines lines from multiple verses.

Research and define a staged scripture-detection pipeline that may include:

1. Deterministic reference parsing.
2. Normalised exact-text matching.
3. Fuzzy-text matching.
4. Semantic retrieval.
5. Context-aware ranking.
6. Confidence scoring.
7. Duplicate suppression.
8. Cooldown logic.
9. Operator approval.
10. Live display.
11. Detection history.
12. Correction and feedback.

The deterministic reference parser must take priority over semantic guesses.

Define three operating modes:

* Suggest only.
* Operator confirmation required.
* Automatic display above a configurable confidence threshold.

The default mode should require operator confirmation.

Each scripture suggestion should display:

* Detected reference or quotation.
* Suggested Bible passage.
* Translation.
* Confidence level.
* Alternative matches.
* Reason for the match.
* Approve action.
* Reject action.
* Edit action.
* Display action.
* Ignore-duplicate action.
* Quick undo.
* Auto-clear configuration.

Research how well this can realistically work and document limitations, latency, false positives, false negatives, accent considerations, noisy-room considerations, and operator responsibilities.

Do not describe the feature as perfectly accurate.

# AI-generated sermon notes

The application should use the sermon transcript to generate structured sermon notes.

Research and define requirements for generating:

* Sermon title suggestions.
* Main scripture.
* Supporting scriptures.
* Introduction.
* Main sermon points.
* Sub-points.
* Illustrations or examples mentioned.
* Important quotations from the sermon.
* Prayer points.
* Calls to action.
* Announcements mentioned.
* Key lessons.
* Summary.
* Chapter markers.
* Speaker timestamps.
* Referenced people, books, or topics.
* Closing prayer or conclusion.
* Social-media excerpts.
* YouTube chapter suggestions.
* Podcast show notes.
* Short sermon description.
* Full sermon outline.

The notes must be editable before export or publication.

The system should preserve links between generated notes and the source transcript timestamps where possible.

Define export formats such as:

* Plain text.
* Markdown.
* PDF.
* DOCX.
* JSON.
* Copy to clipboard.
* Future publishing integrations.

Research and define an AI-provider abstraction supporting:

* Local models where practical.
* Cloud AI providers.
* User-supplied API keys.
* Configurable providers.
* Provider fallback.
* Usage visibility.
* Estimated cost.
* Data-retention disclosure.
* Consent.
* Secure API-key storage.

No transcript should be sent to an external AI provider without explicit user action and disclosure.

Generated notes must be labelled as AI-generated and should not silently overwrite the original transcript.

# Text-to-speech requirements

Add a text-to-speech system that can read generated or selected content aloud.

Research and define possible TTS use cases such as:

* Reading Bible passages.
* Reading announcements.
* Reading sermon notes.
* Reading service instructions.
* Accessibility support.
* Rehearsal support.
* Creating voiceovers for church content.
* Producing audio versions of sermon summaries.
* Providing pronunciation assistance.
* Previewing written content before presentation.

Define requirements for:

* Selecting text.
* Selecting a voice.
* Selecting language.
* Voice preview.
* Speech speed.
* Pitch where supported.
* Volume.
* Pausing and resuming.
* Stopping playback.
* Queueing speech.
* Exporting synthesised audio.
* Local TTS providers.
* Cloud TTS providers.
* Voice availability by platform.
* Usage costs.
* Offline support.
* Pronunciation dictionary.
* Bible-book and biblical-name pronunciation.
* Output-device selection.
* Preventing TTS audio from accidentally playing through the main sound system.
* Routing TTS to preview, operator headphones, livestream, or selected outputs.
* Displaying a clear status when TTS is active.

Investigate whether TTS should be part of the MVP or a later release based on user value, risk, platform differences, and implementation complexity.

Do not include voice cloning unless it is explicitly approved as a separate future feature with appropriate consent and safeguards.

# Timer requirements

Research and define:

* Countdown timers.
* Count-up timers.
* Time-of-day clocks.
* Service-duration timers.
* Speaker timers.
* Segment timers.
* Scheduled start timers.
* Elapsed timers.
* Multiple simultaneous timers.
* Warning thresholds.
* Pause.
* Resume.
* Reset.
* Add time.
* Subtract time.
* Timer presets.
* Per-output visibility.
* Mobile control.
* Stage-display presentation.
* Operator-only timer controls.
* Timer completion actions.

When a countdown reaches zero, the application must support a configurable “TIME UP” state.

Define “TIME UP” requirements including:

* Large “TIME UP” text.
* Customisable wording.
* Per-output layout.
* Stage-display-only mode.
* Audience-output mode.
* Livestream-output mode.
* Flashing or static display.
* Configurable background.
* Configurable colour.
* Optional animation.
* Optional sound for the operator.
* Optional sound for selected outputs.
* Continue into negative overrun time.
* Display how far the speaker has exceeded the allocated time.
* Manual dismissal.
* Automatic dismissal.
* Extend-time control.
* Reset control.
* Mobile dismissal.
* Macro or automation trigger.
* Audit log of when time expired.
* Preventing accidental display on audience outputs.

Timer accuracy must use an authoritative monotonic clock and must not depend on visual refresh intervals.

# Lower-thirds requirements

Research and define support for:

* Speaker name and title.
* Sermon title.
* Scripture reference.
* Song lyrics.
* Announcements.
* Social-media handles.
* Church branding.
* Custom text.
* Logos.
* Images.
* Entry and exit animations.
* Templates.
* Display duration.
* Manual hold.
* Queueing.
* Transparent background.
* Dedicated lower-third output.
* Browser-source output.
* Livestream layout.
* Future NDI with alpha.

# Mobile-control requirements

The mobile application should support:

* Discovering desktop hosts.
* QR-code pairing.
* Remembering authorised hosts.
* Secure reconnection.
* Current slide preview.
* Next slide preview.
* Service-plan navigation.
* Triggering slides.
* Clearing layers.
* Blackout.
* Timer control.
* “TIME UP” display control.
* Lower-third control.
* Scripture search.
* Scripture display.
* Scripture-suggestion approval.
* Transcript viewing.
* Sermon-note status.
* TTS controls.
* Stage-message sending.
* Output-health monitoring.
* Macro triggering.
* Role-based permissions.

Research and define roles such as:

* Observer.
* Presenter.
* Worship leader.
* Scripture operator.
* Timer operator.
* Production operator.
* Administrator.

The desktop application must remain the authoritative state owner.

Loss of mobile connectivity must not stop or damage the desktop presentation.

# Reliability requirements

The application will be used during live church services and must remain dependable during long sessions.

Research and define requirements for:

* Continuous autosave.
* Crash recovery.
* Automatic backups.
* Database integrity.
* Media-file integrity.
* Missing-file detection.
* Audio-device disconnection.
* Display disconnection.
* Mobile disconnection.
* Transcription-provider failure.
* AI-provider failure.
* TTS-provider failure.
* Network failure.
* GPU or decoder failure.
* Storage-space warnings.
* Safe mode.
* Diagnostic reports.
* Structured logs.
* Log rotation.
* Recovery after forced shutdown.
* Eight-hour and twelve-hour service operation.
* Bounded memory usage.
* Cancellable background tasks.
* Bounded queues.
* Bounded caches.
* No transcription or AI failure blocking slide control.
* Emergency blackout and clear without network access.

# Performance and resource requirements

The product should not consume excessive CPU or memory.

Research and recommend measurable targets for:

* Startup time.
* Idle memory.
* Presentation memory.
* AI-model memory.
* Media-cache memory.
* Slide-trigger latency.
* 1080p60 rendering.
* Multiple simultaneous outputs.
* Transcription latency.
* Scripture-detection latency.
* Mobile-command latency.
* TTS-generation latency.
* Long-running memory stability.
* Background CPU usage.
* GPU usage.
* Model lazy loading.
* Media preloading.
* Hidden-media decoding.
* Cache eviction.

Evaluate appropriate technologies for achieving this, including whether Rust, Tauri, native rendering, wgpu, GStreamer, SQLite, and local AI runtimes are suitable.

Do not choose the technology stack solely because it was suggested in the initial brief. Research and document the trade-offs before recommending the final architecture.

# Security and privacy requirements

Research and define:

* Local-network API security.
* Mobile pairing.
* Device authentication.
* Role-based permissions.
* Revocation.
* Rate limiting.
* Command validation.
* Replay protection.
* Secure secret storage.
* API-key management.
* Transcript privacy.
* Audio privacy.
* Sermon-note privacy.
* Cloud-provider disclosure.
* Data-retention settings.
* Transcript deletion.
* Recording deletion.
* Audit logs.
* File-import security.
* Path-traversal protection.
* Dependency security.
* Tauri permissions.
* Content security policy.
* Local AI-model security.
* Update security.
* Backup encryption where appropriate.

# Licensing and compliance

Research and document licensing or compliance considerations for:

* Bible translations.
* Fonts.
* Icons.
* Media codecs.
* Speech-recognition models.
* Text-to-speech voices.
* AI providers.
* NDI.
* Imported song lyrics.
* User recordings.
* Sermon transcripts.
* Cloud storage.
* Data protection.
* App-store distribution.
* Open-source dependencies.

Do not assume that scripture translations, song lyrics, voices, AI models, or codecs may be redistributed freely.

# Required PRD outputs

Produce the complete product-manager artifact structure.

The PRD must include:

* Product vision.
* Problem statement.
* Personas and roles.
* Jobs to be done.
* Goals.
* Non-goals.
* Success metrics.
* Constraints.
* Assumptions.
* Competitor research.
* User journeys.
* Feature inventory.
* Functional requirements.
* Non-functional requirements.
* Permissions.
* Data lifecycle.
* AI and provider architecture requirements.
* Offline behaviour.
* Security.
* Privacy.
* Accessibility.
* Reliability.
* Performance.
* Licensing.
* Risks.
* Dependencies.
* Open questions.
* MVP.
* Later releases.
* Acceptance criteria.
* Launch criteria.
* Traceability.

Assign stable requirement IDs such as:

* FR-001.
* NFR-001.
* FLOW-001.
* RISK-001.
* METRIC-001.

# PRD audit requirements

After drafting the PRD, create a fresh-context audit sub-agent.

The auditor must attempt to find:

* Missing workflows.
* Missing failure states.
* Ambiguous requirements.
* Untestable acceptance criteria.
* Hidden assumptions.
* Infeasible AI expectations.
* Missing operator controls.
* Privacy problems.
* Licensing problems.
* Security gaps.
* Accessibility gaps.
* Performance risks.
* Resource-consumption risks.
* Offline limitations.
* Incorrect scripture-detection assumptions.
* TTS-routing risks.
* Audio-feedback risks.
* Missing crash-recovery behaviour.
* Scope that is too large for one release.
* Requirements that cannot be assigned to a specialist skill.

The audit verdict must be exactly one of:

* FAIL.
* PASS WITH CONDITIONS.
* PASS.

Do not create implementation tickets until the verdict is PASS.

Resolve every blocker and major audit finding, update the PRD, and re-run the audit.

# Ticket decomposition

After the PRD audit passes, create dependency-aware epics and implementation tickets.

Route tickets to specialist skills such as:

* architecture.
* ui.
* frontend.
* backend.
* mobile.
* data.
* qa.
* security.
* devops.
* accessibility.
* documentation.

Future specialist skills may include:

* rust-core.
* renderer.
* media-engine.
* transcription-ai.
* scripture-intelligence.
* tts.
* output-management.
* integrations.

Every ticket must include:

* Unique ticket ID.
* Epic.
* Primary owner skill.
* Collaborating skills.
* Requirement IDs.
* Dependencies.
* Product outcome.
* Context.
* Scope.
* Non-goals.
* Behaviour and business rules.
* UX states.
* API contracts.
* Data implications.
* AI-provider implications.
* Security and privacy.
* Performance and reliability.
* Accessibility.
* Observability.
* Acceptance criteria.
* Required tests.
* Completion evidence.
* Documentation requirements.

Prefer vertical slices that create demonstrable user value.

Examples of potential vertical slices include:

* Create a service plan and display a static slide on the main output.
* Search for a scripture and display it using a selected template.
* Run a stage countdown and show “TIME UP” at zero.
* Pair a mobile controller and advance a slide.
* Capture microphone audio and display an interim transcript.
* Detect an explicit spoken scripture reference and present it for operator approval.
* Generate editable sermon notes from a completed transcript.
* Read a selected scripture through TTS to an operator-selected audio output.

Do not create broad tickets such as:

* Build the backend.
* Build the frontend.
* Implement AI.
* Add mobile support.
* Add tests.

# Release planning

Create realistic release slices.

At minimum, evaluate a release sequence similar to:

## Phase 1: Presentation foundation

* Service plans.
* Static slides.
* Song lyrics.
* Scripture search.
* Main output.
* Stage output.
* Timers.
* “TIME UP” state.
* Lower thirds.
* Autosave.
* Crash recovery.
* Basic mobile control.

## Phase 2: Media and output expansion

* Images.
* Video.
* Audio.
* Motion backgrounds.
* Multiple custom outputs.
* Livestream layouts.
* Transparent lower thirds.
* Output diagnostics.

## Phase 3: Transcription

* Audio input.
* Live transcript.
* Transcript editing.
* Transcript persistence.
* Transcript export.
* Provider configuration.

## Phase 4: Scripture intelligence

* Spoken-reference parsing.
* Quote matching.
* Semantic matching.
* Confidence ranking.
* Operator approval.
* Automatic mode.
* Scripture-detection history.

## Phase 5: Sermon intelligence and TTS

* AI-generated sermon notes.
* Timestamp-linked notes.
* Summaries.
* Chapters.
* Social excerpts.
* Text-to-speech.
* Voice and output routing.
* Audio export.

## Phase 6: Production integrations and hardening

* MIDI.
* OSC.
* Stream Deck.
* Companion.
* Browser source.
* NDI where licensing permits.
* Advanced macros.
* Security review.
* Accessibility review.
* Long-running soak tests.
* Cross-platform packaging.

Change this sequence when research supports a better plan.

# Final completion conditions

Do not declare this PM task complete until:

* Research evidence has been recorded.
* User workflows are documented.
* AI transcript requirements are documented.
* Scripture-detection requirements are documented.
* Sermon-note requirements are documented.
* TTS requirements are documented.
* “TIME UP” timer behaviour is documented.
* MVP and later releases are clearly separated.
* Every requirement has testable acceptance criteria.
* The PRD audit verdict is PASS.
* All blocker and major audit findings are resolved.
* Every approved requirement maps to a ticket or explicit deferral.
* Every ticket has a specialist owner.
* Ticket dependencies contain no cycles.
* The first release is coherent and realistically implementable.
* The product-manager artifact validator exits successfully.
* IMPLEMENTATION-READINESS.md states READY.

Begin by inspecting the repository, checking available MCP tools and existing product documentation, and creating the research plan.
