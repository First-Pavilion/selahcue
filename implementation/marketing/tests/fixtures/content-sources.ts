/**
 * Citations for every article: which repository file backs which claim.
 *
 * TEST-ONLY DATA, deliberately outside `src/`. These used to ride along in each article
 * object, which shipped 150-odd internal repo paths and one-line audit notes to every
 * visitor's browser for no reader benefit. `tests/content.test.ts` is the only consumer: it
 * requires an entry for every article (and no entry for a non-article), at least one source
 * each, and that every cited path is a git-tracked regular file.
 *
 * Keys: `blog/<slug>`, `docs/<category>/<slug>`, `support/<category>/<slug>`.
 * Paths are relative to the repository root. `supports` says which claim(s) the file backs.
 */
export interface Source {
  readonly path: string
  readonly supports: string
}

const OP = 'implementation/desktop/crates/selahcue-operator/dist'
const CR = 'implementation/desktop/crates'
const MOB = 'implementation/mobile/selahcue_controller/lib'

export const SOURCES: Readonly<Record<string, readonly Source[]>> = {
  'blog/why-offline-first-matters-for-sunday-morning': [
    { path: 'docs/architecture/ARCHITECTURE.md', supports: 'Principles: desktop-authoritative, offline-first core (slides, scripture, timers, blackout work with no network), mobile holds no authoritative state, output-failure isolation.' },
    { path: 'docs/product/prds/SelahCue-PRD.md', supports: 'Core live functions must work with zero network (line 54, NFR-015).' },
    { path: `${CR}/selahcue-scripture/src/lib.rs`, supports: 'Five bundled translations compiled in; "Everything works offline".' },
    { path: `${OP}/index.html`, supports: 'Console copy: nothing exposed to the internet; autosave saves within 5 s; update checking unavailable; "holding its last good frame".' },
    { path: `${OP}/app.js`, supports: 'Session restored notice; on-device model downloads once on first Start listening; OUTPUT HELD message.' },
    { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'Autosave throttled to at most once per second; running countdown re-saved every 5 s.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Restore on launch re-presents live/staged items, blackout and countdown; commands are RBAC-checked on the host.' },
    { path: `${CR}/selahcue-engine/src/engine.rs`, supports: 'Engine holds the last good frame on a fault (never-blank guarantee).' },
    { path: `${CR}/selahcue-operator/src/transcription_route.rs`, supports: 'Release builds fall back to on-device transcription when cloud is selected.' },
  ],
  'blog/what-your-stage-team-sees-on-the-stage-display': [
    { path: `${CR}/selahcue-present/src/stage.rs`, supports: 'Stage content: current/NEXT, TIME UP tint per template, OVER m:ss, Message from production overlay, templates.' },
    { path: `${OP}/index.html`, supports: 'Stage theme choices, message presets and 120-character custom message, "Shown on the stage output only", disabled text-size and layer controls.' },
    { path: `${OP}/settings-outputs.js`, supports: 'Stage defaults toggles are always-on and disabled: "Not configurable yet".' },
    { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'Wall clock rendered on the stage output.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Timer is shown on stage only; audience never receives it.' },
  ],
  'blog/which-bible-translations-ship-with-selahcue': [
    { path: `${CR}/selahcue-scripture/src/lib.rs`, supports: 'Bundled translations KJV (default), WEB, ASV, WEBBE, DBY compiled in; public-domain wording; works offline.' },
    { path: `${CR}/selahcue-core/src/scripture.rs`, supports: '66-book canon.' },
    { path: `${OP}/settings-about.js`, supports: 'About page lists bundled translations as "Public Domain — no attribution required".' },
    { path: `${OP}/index.html`, supports: '"Not available in this build yet" for licensed modules/APIs; "Licensed translations (a future release)".' },
    { path: `${OP}/app.js`, supports: 'Translation picker shows codes; console opens on KJV.' },
  ],
  'blog/controlling-selahcue-from-a-phone-how-pairing-works': [
    { path: `${CR}/selahcue-lan/src/rbac.rs`, supports: 'Producer / Assistant / Viewer permissions; plan edits, stage messages and device management not available to phones.' },
    { path: `${CR}/selahcue-lan/src/server.rs`, supports: 'Pairing code valid 120 s and single use; operator approval and role; revoke; per-connection tasks.' },
    { path: `${CR}/selahcue-lan/src/pinning.rs`, supports: 'Phone trusts only the certificate whose SHA-256 matches the invite.' },
    { path: `${OP}/remote.js`, supports: 'Pending request card with role dropdown, Approve and Deny; paired devices list with Revoke.' },
    { path: `${OP}/index.html`, supports: 'Pair a device panel; multicast-blocked guidance (scan the QR); nothing exposed to the internet.' },
    { path: `${MOB}/views/pairing_view.dart`, supports: 'Phone pairing screen: scan QR, waiting for host approval.' },
    { path: 'docs/release/mobile/RELEASE-CHECKLIST.md', supports: 'Mobile app not yet released to stores (checklist unchecked).' },
  ],
  'blog/ndi-output-in-selahcue-what-works-today': [
    { path: `${OP}/app.js`, supports: 'NDI Output inspector: Source name, Broadcast as NDI, runtime-unavailable message, duplicate-name refusal, frame-rate choices, receivable by OBS / vMix / another SelahCue.' },
    { path: `${CR}/selahcue-desktop/src/video_sink.rs`, supports: 'NDI sink; 1920x1080 RGBA frames.' },
    { path: `${CR}/selahcue-desktop/Cargo.toml`, supports: '`ndi` Cargo feature is off by default.' },
    { path: '.github/workflows/windows-installer.yml', supports: 'Windows installer built with --features ndi and bundles the NDI runtime.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Blackout returns black frames for all outputs including NDI; duplicate NDI source names refused.' },
    { path: `${CR}/selahcue-engine/src/raster.rs`, supports: 'Output is opaque; no alpha.' },
    { path: `${CR}/selahcue-present/src/theme.rs`, supports: 'Lower-third uses opaque backdrop; true NDI alpha-keying is a later slice.' },
  ],
  'docs/getting-started/preview-live-and-go-live': [
    { path: `${CR}/selahcue-present/src/present.rs`, supports: 'Staging never changes Live; only go_live does; blackout retains content; clear empties live and leaves preview.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Next/Previous stage only; go live with nothing staged is a no-op; going live releases blackout; clear releases blackout.' },
    { path: `${OP}/app.js`, supports: 'Key bindings (Space/→ next, ← previous, Enter go live, B blackout, Esc Esc and Backspace clear), Live Console only, ignored in fields; double-click behaviours.' },
    { path: `${OP}/index.html`, supports: 'Panel labels PREVIEW · STAGED / LIVE · ON AIR, GO LIVE with Enter hint, BLACKOUT B, Clear Output Esc Esc, Restore output; keyboard remapping unavailable.' },
  ],
  'docs/getting-started/offline-and-autosave': [
    { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'Autosave throttled to once per second; countdown re-saved every 5 s; restore-point cadence 60 s; data folder locations per OS; unencrypted-store behaviour not claimed.' },
    { path: `${CR}/selahcue-data/src/autosave_repo.rs`, supports: 'Restore-point ring of 3.' },
    { path: `${CR}/selahcue-desktop/src/guard.rs`, supports: 'Crash-loop breaker: 3 launches within 60 s; stable after 10 s or clean exit; old session preserved.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Restore on launch re-presents live/staged items, blackout and countdown.' },
    { path: `${OP}/app.js`, supports: 'Session restored and Started clean after repeated restarts notices; first-run model download on Start listening.' },
    { path: `${OP}/index.html`, supports: 'Autosave copy (at most 5 seconds lost); Back up now / Run check / Restore / Export diagnostics disabled.' },
    { path: `${CR}/selahcue-scripture/src/lib.rs`, supports: 'Bundled translations work offline.' },
    { path: `${CR}/selahcue-operator/src/main.rs`, supports: 'Operator keeps a second store (deck library and settings) in its app-data folder.' },
  ],
  'docs/display-outputs/assign-displays-to-outputs': [
    { path: `${OP}/app.js`, supports: 'Output kinds and names; Monitor dropdown in the Display section; "No displays found" / "No physical output"; disabled Test pattern and Go fullscreen.' },
    { path: `${OP}/index.html`, supports: 'Screens & Outputs navigation; Add virtual output; Identify; disabled settings entries (venue profiles, output health, test patterns).' },
    { path: `${OP}/settings-outputs.js`, supports: 'Settings > Outputs & Displays lists displays with Identify and links to Screens & Outputs; assignment is not done there.' },
    { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'Only main and stage get OS windows; assigned display = borderless fullscreen, unassigned = plain window; closing last window quits; Identify bars.' },
    { path: `${CR}/selahcue-present/src/stage.rs`, supports: 'Identify draws N vertical bars (1 on main, 2 on stage) for ~5 s.' },
    { path: `${CR}/selahcue-lan/src/rbac.rs`, supports: 'Assigning outputs is an operator-only permission.' },
  ],
  'docs/display-outputs/stage-display': [
    { path: `${OP}/index.html`, supports: 'Service Timer tab > Stage sub-tab; Stage theme choices; message presets, 120-char custom message, Send to stage / Clear; "Shown on the stage output only"; disabled text size.' },
    { path: `${OP}/settings-appearance.js`, supports: 'Settings > Appearance default stage theme with the same three choices.' },
    { path: `${OP}/settings-outputs.js`, supports: 'Stage defaults are fixed on and disabled ("Not configurable yet").' },
    { path: `${CR}/selahcue-present/src/stage.rs`, supports: 'Current/NEXT lines, templates (Worship, Scripture, Timer-only), TIME UP/OVER, Message from production overlay.' },
    { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'Date and time of day drawn on the stage output.' },
  ],
  'docs/display-outputs/ndi-output': [
    { path: `${OP}/app.js`, supports: 'NDI Output inspector (Source name, Broadcast as NDI, status line, NDI pill, frame rates, duplicate-name refusal, runtime-unavailable message, receivable by OBS / vMix / another SelahCue).' },
    { path: `${CR}/selahcue-desktop/src/video_sink.rs`, supports: '1920x1080 RGBA frames; NDI sink.' },
    { path: `${CR}/selahcue-desktop/Cargo.toml`, supports: '`ndi` feature off by default.' },
    { path: '.github/workflows/windows-installer.yml', supports: 'Windows installer built with --features ndi and the NDI runtime.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Blackout blacks out all outputs including NDI; duplicate source names refused.' },
    { path: `${CR}/selahcue-engine/src/raster.rs`, supports: 'Output is opaque.' },
    { path: `${CR}/selahcue-present/src/theme.rs`, supports: 'Lower third is opaque; alpha keying is a later slice.' },
    { path: 'docs/delivery/BUILD_STATE.md', supports: 'macOS DMG specified but not built; no Linux packaging.' },
  ],
  'docs/scripture-bibles/find-and-stage-a-verse': [
    { path: `${CR}/selahcue-core/tests/test_scripture.rs`, supports: 'Accepted reference forms (abbreviations, periods, numbered books, space shorthand); bare book name rejected.' },
    { path: `${CR}/selahcue-scripture/src/lib.rs`, supports: 'Keyword search: all words, case-insensitive, limit 8, canonical order.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Scripture slide composition (range on one slide, verse numbers, title), follow-live behaviour, one hit per reference.' },
    { path: `${OP}/app.js`, supports: 'Search box behaviour, Enter opens chapter, whole-chapter stages verse 1, verse not present message, arrow/click/double-click behaviour.' },
    { path: `${OP}/index.html`, supports: 'Scriptures tab labels, placeholder "Reference or keywords", footnote on arrows/Enter/double-click, disabled history and favourites.' },
  ],
  'docs/scripture-bibles/included-translations': [
    { path: `${CR}/selahcue-scripture/src/lib.rs`, supports: 'Bundled KJV (default), WEB, ASV, WEBBE, DBY; YLT downloadable but unavailable.' },
    { path: `${CR}/selahcue-scripture/src/download.rs`, supports: 'YLT download pin is a placeholder (not downloadable).' },
    { path: `${CR}/selahcue-core/src/scripture.rs`, supports: '66-book canon.' },
    { path: `${OP}/settings-about.js`, supports: 'Bundled translations shown as Public Domain.' },
    { path: `${OP}/settings-scripture.js`, supports: 'Installed translations and default-translation controls.' },
    { path: `${OP}/index.html`, supports: '"Not available in this build yet" for licensed modules and services.' },
    { path: `${OP}/app.js`, supports: 'Console opens on KJV; picker lists codes.' },
  ],
  'docs/timers-plans/build-a-service-plan': [
    { path: `${OP}/app.js`, supports: 'Add item buttons, rename, reorder (drag, arrows, Alt+arrows), remove with confirm, link scripture/presentation, Duplicate this service, Publish to team, Open in Live, Create/Template/Import flows, import example, one plan at a time.' },
    { path: `${OP}/index.html`, supports: 'Service Plan surface and its three columns.' },
    { path: `${CR}/selahcue-core/src/plan.rs`, supports: 'Templates Sunday Morning and Midweek Gathering; 500-item and 120-character limits.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Next/Previous do not skip Section items; Timer item kind is a label.' },
  ],
  'docs/timers-plans/service-timer': [
    { path: `${OP}/index.html`, supports: 'Service Timer tab, Set a custom time (HOURS/MIN/SEC), 5:00 and 10:00 presets, Pause/Resume/Reset/Stop, "Shown on the stage output only".' },
    { path: `${OP}/app.js`, supports: 'Timer controls and enabled states, status pill RUNNING/PAUSED/TIME UP, amber at 30 s, top-bar chip, command palette Start service timer = 5:00.' },
    { path: `${CR}/selahcue-core/src/timer.rs`, supports: 'Countdown keeps running past zero; subtracting below elapsed forces TIME UP; adding clears it.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'StartTimer replaces the timer; timer shown on stage output only; recovery restores at last save.' },
    { path: `${CR}/selahcue-present/src/stage.rs`, supports: 'Stage draws OVER m:ss and TIME UP state.' },
  ],
  'docs/mobile-control/pair-a-phone': [
    { path: `${OP}/index.html`, supports: 'Pair a device panel, host fingerprint, Single-use expiry, New code, Paired devices table, multicast-blocked guidance.' },
    { path: `${OP}/remote.js`, supports: 'Pending request card with Role dropdown (default Producer), Approve/Deny; device status thresholds; two-step Revoke; QR minted on page load, not auto-renewed.' },
    { path: `${OP}/app.js`, supports: 'Shortcut to Network settings (Ctrl/Cmd+Shift+R).' },
    { path: `${CR}/selahcue-lan/src/server.rs`, supports: 'Code valid 120 s, consumed on connect; operator wait up to 120 s.' },
    { path: `${MOB}/views/pairing_view.dart`, supports: 'Phone screens: Connect to a host, Scan the pairing QR, discovered hosts, device name, waiting for host.' },
    { path: 'docs/release/mobile/RELEASE-CHECKLIST.md', supports: 'Controller app not yet released to stores.' },
  ],
  'docs/mobile-control/phone-roles': [
    { path: `${CR}/selahcue-lan/src/rbac.rs`, supports: 'Permission matrix for Producer / Assistant / Viewer; stage messages and device management operator-only.' },
    { path: `${CR}/selahcue-lan/src/server.rs`, supports: 'Host refuses the Operator role for remote devices; role change applied on next request.' },
    { path: `${MOB}/models/tab_scope.dart`, supports: 'Phone tabs Live, Plan, Scripture, Timer and role scoping.' },
    { path: `${MOB}/views/widgets/mobile_widgets.dart`, supports: 'Emergency strip: second tap within 3 s to confirm blackout/clear; reconnecting banner.' },
    { path: `${MOB}/views/tabs/plan_tab.dart`, supports: 'Tap stages, double-tap goes live.' },
    { path: `${MOB}/views/tabs/live_tab.dart`, supports: 'Read-only transcript, last six lines.' },
    { path: `${MOB}/models/session.dart`, supports: 'Role fixed from handshake until reconnect.' },
  ],
  'docs/troubleshooting/status-messages': [
    { path: `${OP}/app.js`, supports: 'Session restored, Started clean after repeated restarts, Last autosave failed, Couldn’t open the plan / Restore last autosave / Restore requested, NO SIGNAL / SIGNAL LOST, OUTPUT HELD, No displays found, NDI runtime unavailable, duplicate NDI name, one plan at a time.' },
    { path: `${OP}/index.html`, supports: 'Reattach promise in the Signal-lost banner; Output is black copy and Restore output; autosave failure copy.' },
    { path: `${CR}/selahcue-desktop/src/guard.rs`, supports: 'Crash-loop breaker thresholds behind the Started clean notice; low-disk warning and checkpoint stop.' },
    { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'no_signal telemetry when the window’s monitor is gone; output fault path.' },
  ],
  'support/getting-started/nothing-on-the-audience-screen': [
    { path: `${OP}/index.html`, supports: 'Panel labels, Output idle, Output is black copy, Restore output, Clear Output Esc Esc, GO LIVE Enter.' },
    { path: `${OP}/app.js`, supports: 'Keys limited to Live Console and ignored in fields; Signal lost banner and NO SIGNAL pill.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Going live releases blackout; clear empties live; Go Live with nothing staged is a no-op.' },
    { path: `${CR}/selahcue-present/src/present.rs`, supports: 'Staging never changes Live.' },
  ],
  'support/display-outputs/no-display-to-choose': [
    { path: `${OP}/app.js`, supports: 'Monitor dropdown for main and stage only; "No displays found" / "No physical output".' },
    { path: `${OP}/settings-outputs.js`, supports: 'Settings > Outputs & Displays lists displays and assignments.' },
    { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'Display list built at startup; identical displays keyed by position.' },
  ],
  'support/display-outputs/ndi-toggle-greyed-out': [
    { path: `${OP}/app.js`, supports: 'NDI runtime unavailable message and disabled toggle; duplicate-name refusal; NDI offered for audience-class outputs only.' },
    { path: `${OP}/index.html`, supports: 'Settings > Outputs & Displays shows Network outputs as COMING SOON.' },
    { path: `${CR}/selahcue-desktop/Cargo.toml`, supports: '`ndi` feature is off by default.' },
    { path: '.github/workflows/windows-installer.yml', supports: 'Windows installer built with NDI.' },
  ],
  'support/scripture-bibles/verse-will-not-open': [
    { path: `${CR}/selahcue-core/tests/test_scripture.rs`, supports: 'Bare book name rejected; accepted reference forms.' },
    { path: `${CR}/selahcue-scripture/src/lib.rs`, supports: 'Keyword search semantics (all words, Bible order).' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'One hit per reference when several are given.' },
    { path: `${OP}/app.js`, supports: 'Verse not present message; arrow keys move verses only with a chapter open; Space and arrows step the plan.' },
  ],
  'support/scripture-bibles/niv-esv-nlt-not-available': [
    { path: `${OP}/index.html`, supports: '"Not available in this build yet" for licensed modules/APIs.' },
    { path: `${CR}/selahcue-scripture/src/lib.rs`, supports: 'Five bundled translations; YLT unavailable until fetched.' },
    { path: `${CR}/selahcue-scripture/src/download.rs`, supports: 'YLT download source is a placeholder.' },
    { path: `${OP}/settings-about.js`, supports: 'Bundled translations listed as Public Domain.' },
  ],
  'support/timers-clocks/timer-not-on-audience-screen': [
    { path: `${OP}/index.html`, supports: '"Shown on the stage output only"; TIME UP safety "Locked · stage only"; Timer-only stage theme.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Timer rendered on the stage output only.' },
    { path: `${OP}/app.js`, supports: 'Top-bar timer chip mirrors the readout.' },
  ],
  'support/mobile-control/phone-wont-pair': [
    { path: `${CR}/selahcue-lan/src/server.rs`, supports: 'Code valid 120 s, consumed on connect; "pairing rejected: forbidden" / "unauthenticated"; host waits up to 120 s.' },
    { path: `${OP}/remote.js`, supports: 'Pending requests polled only while the Remote Control page is open; New code; QR not auto-renewed.' },
    { path: `${OP}/index.html`, supports: 'Multicast-blocked guidance (scan the QR); Pair a device panel.' },
    { path: `${MOB}/views/pairing_view.dart`, supports: 'Waiting for the host to allow this device; discovered hosts list; same-Wi-Fi guidance.' },
    { path: `${MOB}/controllers/pairing_controller.dart`, supports: '"That is not a valid SelahCue pairing invite."' },
    { path: `${MOB}/models/session.dart`, supports: 'Formatting of pairing rejection messages.' },
    { path: 'docs/architecture/adr/ADR-0008-lan-protocol-security.md', supports: 'Client-isolation networks listed as an unvalidated risk (no result recorded).' },
  ],
  'support/mobile-control/phone-cannot-go-live': [
    { path: `${CR}/selahcue-lan/src/rbac.rs`, supports: 'Per-role permissions.' },
    { path: `${OP}/remote.js`, supports: 'Role dropdown in the Paired devices table.' },
    { path: `${MOB}/models/session.dart`, supports: 'Role fixed from the handshake until reconnect.' },
    { path: `${MOB}/views/tabs/scripture_tab.dart`, supports: 'Scripture tab shows double-tap-to-send-live regardless of go-live permission.' },
  ],
  'support/mobile-control/remove-a-paired-phone': [
    { path: `${OP}/remote.js`, supports: 'Two-step Revoke ("Confirm?" for ~4 s); paired-devices list.' },
    { path: `${OP}/index.html`, supports: 'Revoke all / Regenerate disabled ("not available in this build yet").' },
    { path: `${CR}/selahcue-lan/src/server.rs`, supports: 'Revocation applies on the next request of an open connection.' },
    { path: `${MOB}/views/controller_view.dart`, supports: '"Access removed" screen with Scan QR to pair again.' },
    { path: `${MOB}/controllers/live_controller.dart`, supports: 'Disconnect this device clears credentials on the phone only and sends no revoke to the host.' },
  ],
  'support/troubleshooting/after-a-restart-or-crash': [
    { path: `${OP}/app.js`, supports: 'Session restored and Started clean notices; Couldn’t open the plan / Restore last autosave / Restore requested.' },
    { path: `${OP}/index.html`, supports: 'Storage copy about resuming vs starting clean; disabled Back up now / Restore / Export diagnostics.' },
    { path: `${CR}/selahcue-desktop/src/guard.rs`, supports: 'Crash-loop breaker: 3 launches in 60 s; old session preserved.' },
    { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Restore on launch of live/staged items, blackout and countdown; no sender for Resume/StartClean.' },
    { path: `${CR}/selahcue-lan/src/protocol.rs`, supports: 'Restore refused if plan content changed since capture.' },
  ],
  'support/troubleshooting/transcription-will-not-start': [
    { path: `${OP}/app.js`, supports: 'Download on Start listening, offline and verification messages, no-audio microphone message, model-size copy.' },
    { path: `${OP}/preservice.js`, supports: 'Pre-service Check: On-device STT model not downloaded.' },
    { path: `${CR}/selahcue-stt/src/model.rs`, supports: 'Model choice and sizes by build: large-v3-turbo ~1.6 GB, small ~488 MB, base ~148 MB.' },
    { path: `${CR}/selahcue-stt/src/model_fetch.rs`, supports: 'Download is not resumable; cache location.' },
    { path: `${CR}/selahcue-operator/src/main.rs`, supports: '"This build does not include on-device speech-to-text".' },
    { path: `${CR}/selahcue-operator/src/transcription_route.rs`, supports: 'Release builds fall back to on-device when cloud is selected.' },
    { path: 'docs/ops/WINDOWS-INSTALLER.md', supports: 'Model downloads on first use and needs internet once; Windows installer is CPU-only.' },
  ],
}
