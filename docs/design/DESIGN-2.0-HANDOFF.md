# SelahCue — "Design 2.0" UI Redesign · Implementation Handoff

Status: **design complete, ready for engineering translation** · Author: UI/UX pass (2026-08-01)
Figma file: `SYQn5hFY8YVQKm3c6rw0eJ` ([open](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue))
Companion docs: [DESIGN-TOKENS.md](DESIGN-TOKENS.md) (current implemented tokens) · [UX-CANONICAL.md](UX-CANONICAL.md) (semantics contract)

> **What this is.** A full redesign of the SelahCue operator/desktop/mobile UI in a warmer, higher-contrast
> visual language ("Design 2.0"), covering every core screen plus the complete state matrix engineers need
> (empty / loading / error / permission / destructive / recovery). It is **design + spec only** — no code was
> changed. Every frame maps back to a real code seam so specialist skills (`/frontend-engineer`,
> `/backend-engineer`, `/mobile-engineer`, `/accessibility` reviewer) can build it without guessing.
>
> **Scope discipline.** The redesign deliberately mirrors the *information architecture already built in
> `dist/`* (see the Operator Console section). Re-skinning the console is a **low-code CSS/token change**, not a
> rebuild. New surfaces (Presentation/Media, Settings, Mobile, Pre-service) are genuinely new and sized as such.

---

## 1. Node map (Figma → what it is → code seam)

All nodes live on page `0:1` of `SYQn5hFY8YVQKm3c6rw0eJ`. Link pattern:
`https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=<node>` (replace `:` with `-`).

| # | Screen / spec | Node | Primary code seam |
|---|---|---|---|
| 0 | **Design 2.0 palette board** (tokens) | `310:124` | `selahcue-present/src/tokens.rs` (canonical) + `dist/app.css` `:root` |
| 1 | **Operator Console** (flagship) | `312:124` | `dist/index.html` + `dist/app.css` + `dist/app.js` |
| 2 | **Theme Designer** | `317:124` | `dist/` theme-designer view + `preview_theme` host cmd + `selahcue-present` |
| 3 | **Screens & Outputs** manager | `327:124` | `dist/` screens view + presenter/output-manager (`selahcue-app`) |
| 4 | **Presentation & Media** (mini-deck) | `329:124` | NEW — presentation editor + media library (`selahcue-present` slide model) |
| 5 | **Detected Scriptures — state spec** (9 states) | `332:124` | `dist/` right-rail panel + detection pipeline (R4, `selahcue-scripture`) |
| 6 | **App Navigation & Global Controls** | `336:124` | `dist/` app-shell (menu, ⌘K palette, chords, emergency footer) |
| 7 | **Settings** (Providers & Privacy shown) | `338:124` | NEW — settings view + provider abstraction (transcription/AI/TTS) |
| 8 | **Mobile Remote** (4 screens) | `342:124` | `implementation/mobile/selahcue_controller` (Flutter) |
| 9 | **Pre-service Check** | `344:124` | NEW — readiness/pre-flight (`selahcue-app` + output/media/audio health) |
| 10 | **System & Recovery States** (6 vignettes) | `346:124` | cross-cutting — blackout/offline/recovery/crash-restore/missing-media |
| 11 | **SelahCue AI — Generate flow** (3 states) | `349:124` | Settings AI card → consent → generate → editor (`selahcue` AI-notes service) |
| 12 | **SelahCue AI — Limits & Failures** (4 states) | `351:124` | approaching-limit · quota-exhausted · service-unavailable · generation-failed |
| 13 | **Mobile RBAC — Capability Matrix** (7×14) | `354:124` | `selahcue-app` RBAC enforcement · PERSONAS §2 / PRD §16 |
| 14 | **Mobile RBAC — Role home screens** (6 roles) | `355:124` | Flutter — per-role control UI (Observer/Worship/Scripture/Timer/Production/Admin) |
| 15 | **Mobile RBAC — Enforcement states** (4) | `357:124` | Flutter — block · downgrade-live · reject-not-queue · revoke |
| 16 | **Desktop — Remote Control · Devices** (QR pair + role assignment) | `359:124` | **desktop app** · pairing + RBAC assignment (FR-086/089/147) |
| 17 | **Mobile — Navigation & Config** | `363:124` | Flutter — role-scoped bottom tabs + ⓘ session sheet (matches built app) |
| 18 | **Stage / Confidence Displays** — 3 themes + states (**individual frames**) | `373:133` · `373:159` · `374:128` · `374:151` · `374:166` · `375:128` | engine output · `StageTheme` |

Sub-nodes worth bookmarking: Console body `312:150`, center `320:200`, right `320:201`; Theme canvas `317:141` / inspector `317:142`; Screens inspector `327:348`; Presentation canvas `329:178` / media `329:179`; Settings content `338:176`; Pre-service sidebar `344:221`.

---

## 2. Design language — "Design 2.0"

The prior UI was a flat navy field with blue/amber accents. Design 2.0 keeps SelahCue's **broadcast semantics**
(the part `test_tokens.rs` and UX-CANONICAL §4 pin) but changes the *neutrals and brand* for depth and focus:

- **Warm-ink neutral stack** — a 4-step dark ramp (`base → surface → elevated → inset`) instead of one flat
  panel colour, so cards read as layered, not painted-on.
- **Indigo→violet brand** (`#6E5CF0 → #7E6EFF`) — more saturated and modern than the old `#5b6bd6`; used for
  the primary action, selection, and focus.
- **Gold worship accent** (`#F2B84B`) — reserved for **Scripture** (references, verse numbers). This is the
  "Selah" signal; it never means status.
- **Broadcast semantics kept, brightened as ink-on-dark** — live-red, preview/staged-green, warning-amber.
  Crucially they now appear as **bright ink on a soft same-hue tint** (`liveS/previewS/warnS`) rather than
  white-on-saturated-fill. This reads better on dark and is calmer, **but changes the WCAG audit** (see §3).

One meaning per colour family everywhere (unchanged from UX-CANONICAL): green = staged/safe (never "on air"),
red = live/alarm/TIME UP, amber = warning/threshold. LIVE/PREVIEW always also carry a **text label** (WCAG 1.4.1
— never colour alone).

**Logo.** The SelahCue mark is an open book with a rising flame. Assets in the file: `369:126` (primary/violet),
`369:127` (white), `369:125` (black). Usage in the app chrome: the **violet mark, no background tile**, placed
directly on the dark surface next to the "SelahCue" wordmark (top bars, app menu, mobile app bar, Config identity).
White variant → for use on a solid violet/brand fill; black variant → on light surfaces. The workspace/church
avatar slot (App menu "Grace Chapel") is left as a placeholder for the **church's own** logo, not the SelahCue mark.

---

## 3. Design tokens & migration

### 3.1 Design 2.0 token table

| Role | Token | Hex | Notes |
|---|---|---|---|
| Neutral | `base` | `#0B0D12` | app background |
| Neutral | `surface` | `#14161D` | panels/cards |
| Neutral | `elevated` | `#1C1F28` | rows, inner cards, controls |
| Neutral | `inset` | `#0F1116` | wells, inputs, monitor mattes |
| Neutral | `border` | `#262A34` | hairlines (`border-strong #363B47` for emphasis) |
| Text | `text` | `#F4F6FB` | primary |
| Text | `text-secondary` | `#A7AEBE` | secondary |
| Text | `text-muted` | `#6B7383` | tertiary/hints |
| Brand | `primary` | `#6E5CF0` | primary action / selection |
| Brand | `primary-hover` | `#7E6EFF` | hover / gradient top |
| Accent | `gold` | `#F2B84B` | scripture only (`gold-soft #2A2415` tint) |
| Status | `live` | `#FF4D4D` | on-air/alarm (`live-soft #2A1416` tint, `live-border #5A2327`) |
| Status | `preview` | `#35C08A` | staged/safe (`preview-soft #10231C` tint, `preview-border #1C3A2E`) |
| Status | `warn` | `#F5A524` | warning (`warn-soft #2A2415` tint, `warn-border #4A3A15`) |
| Status | `info` | `#38BDF8` | neutral-informational (stage role, opt-in badges) |

Radii: cards `14–16`, controls/rows `8–12`, pills `999`. Spacing rhythm: `8 / 11–16 / 20–24`.
Type (Inter): display `52–68`, H1 `22–24`, H2 `15–17`, body `12–14`, label/overline `10–12` (letter-spacing `+1`).

### 3.2 Migration from the currently-implemented tokens

The current tokens are canonical in **`selahcue-present/src/tokens.rs`** and *pinned by tests on four surfaces*
(Rust, operator webview `dist/index.html` / `app.css`, Flutter `design_tokens.dart`, `StageTheme::dark()`).
**Adopting Design 2.0 is therefore a coordinated token change, not a CSS tweak.** Mapping of the existing
`dist/app.css` `:root` vars:

| Current CSS var | Current | → Design 2.0 | New var(s) to add |
|---|---|---|---|
| `--bg` | `#0e1116` | `#0B0D12` | `--elevated #1C1F28`, `--inset #0F1116` |
| `--panel` | `#171b22` | `#14161D` | — |
| `--line` | `#2b323d` | `#262A34` | `--line-strong #363B47` |
| `--text` | `#eef1f6` | `#F4F6FB` | `--text-2 #A7AEBE`, `--text-3 #6B7383` |
| `--muted` | `#9aa4b2` | `#A7AEBE` | — |
| `--accent` | `#5b6bd6` | `#6E5CF0` | `--accent-hover #7E6EFF`, `--gold #F2B84B` |
| `--preview-ink` | `#2bb673` | `#35C08A` | `--preview-soft #10231C` |
| `--live-ink` | `#ef4444` | `#FF4D4D` | `--live-soft #2A1416` |
| `--warn-ink` | `#f2b53c` | `#F5A524` | `--warn-soft #2A2415`, `--info #38BDF8` |

> ⚠ **The fill/ink split changes.** Today `--preview/--live/--warn` are deep hexes audited as **white-on-fill
> ≥4.5:1** (chip backgrounds carrying white text). Design 2.0 mostly uses **bright ink on a soft tint** instead.
> Any engineer adopting these tokens **must re-run and update the WCAG audit** in
> `selahcue-present/tests/test_tokens.rs` for every new fg/bg pairing, and update the three mirror surfaces so
> the pinning tests pass. Do not hex-swap blind. Recommend a `/backend-engineer` (tokens) +
> `/accessibility` pair, one story, all four surfaces in lockstep.

---

## 4. Component inventory

Reusable primitives observed across the design (build once, reuse):

| Component | Variants | Spec |
|---|---|---|
| **Button** | primary (violet gradient), secondary (elevated + border), ghost, danger (live-soft), success (preview) | radius 8–14, padding y 8–18 by prominence; keyboard chord chip optional |
| **Status chip** | live / preview / warn / info / neutral; with/without leading dot | pill, `*-soft` bg + `*-border` + ink text, 10–11px bold |
| **Kind badge** | SONG (violet), SCRIPTURE (gold), SECTION (muted), ANNOUNCEMENT (info) | inset bg + border, 10px bold, letter-spacing |
| **Card / panel** | surface, radius 14–16, 1px border; header = overline + count pill | — |
| **List row** | default / live-tint / staged-tint / selected (violet border) | elevated bg, radius 11–12 |
| **Input / select** | text field, select (▾), search (⌕ leading), masked+keychain | inset bg + border, radius 8–10 |
| **Toggle** | on (violet) / off (elevated) | 42×24, 18px knob |
| **Radio** | selected (violet + white dot) / unselected | 20px |
| **Monitor** | preview (green 2px frame) / live (red 2px frame) / black (blackout) | 16:9, status chip + resolution label, mock render inside |
| **Segmented control** | 2–4 options, active = violet | inset track, 3px inset, radius 7–9 |
| **Kbd chip** | key hint | inset bg + border, 11px; on filled buttons → white text |
| **Emergency footer** | normal / blackout-active | pinned bottom, BLACKOUT + CLEAR ALL always present |

---

## 5. Screen specs & code mapping

### 5.1 Operator Console — `312:124` → `dist/`
The flagship. **IA is 1:1 with the built app**, so this is a re-skin:
- **Left column**: Service Plan (item rows w/ kind badge + live/staged chip + "+ Add" row) **and** Live Transcript
  (REC chip, interim vs confirmed lines, "type or dictate a line" input + Send). → existing `#plan` + transcript panel.
- **Center**: Preview│Live monitors (real composited engine output — see refine #7 story `86ajtwq28`) → transport
  (◀ Previous / **GO LIVE** ⏎ / Next ▶) → **Scriptures browser** (translation ▾, search, chapter nav, verse list w/ staged) → footer hint.
- **Right column**: Service Timer (live countdown; **manual HH:MM:SS entry** — "SET A CUSTOM TIME" 00h:05m:00s + Start, for arbitrary-length countdowns; 5:00/10:00 presets; ±1:00; Pause/Reset/Stop; "stage output only") **and** Detected Scriptures (see §5.5). The **mobile timer carries the same HH:MM:SS entry** (`355:124` Timer Op + base `342:124`) — replaces the minutes-only field so hours can be set.
- **Chrome**: top bar (app menu, transport, ⏱ timer / clock / Connected) + pinned emergency footer.

### 5.2 Theme Designer — `317:124` → `dist/` theme view + `preview_theme`
Left = WYSIWYG canvas (element toolbar T/▢/🖼, centered 16:9 slide with **selection handles**, template gallery
strip). Right inspector = Background (Solid/Gradient/Image seg + gradient stops + angle), Typography (family,
weight, size/line/spacing, colour, L/C/R), Layers list (drag handle + eye + z-order). Renders via the same
engine `render()` the audience sees. Theme carries `Element` (Shape/Image/Text) + `Background` (Solid/Gradient/Image).

### 5.3 Screens & Outputs — `327:124`
Grid of **role-accurate output cards** each with a live mini-preview: Audience-Main, Stage (NOW/NEXT + timer),
Confidence (mirror), Lower-Third (transparent checkerboard + L3 bar), Lobby, Livestream (2-line + frame-drop
warning). Per-output inspector: Display (monitor/resolution/fps/orientation), Appearance (theme/fit/safe-area),
**Visible layers toggles**, Timing (delay/mirror), Device (Identify / Test pattern / Fullscreen / health readout).
Realises the PRD independent-outputs model (one live presentation, different per output).

### 5.4 Presentation & Media — `329:124` (NEW build)
Mini-PowerPoint: slide navigator (numbered thumbnails + Add slide), slide-edit canvas (toolbar Text/Shape/Image/
Video/Background, selection handles, speaker-notes + transition/auto-advance bar), Media Library (All/Images/
Video/Audio tabs, asset grid with durations + a **missing-media** card, audio rows, storage footer). Maps to PRD
FR-002 (slide group as plan-item), FR-009 (free-form layered slides), FR-066/067/068 (image/video/audio).

### 5.5 Detected Scriptures — `332:124` — **complete state matrix (9)**
Panel width 360; lives in the console right rail. States:
1. **Empty** — idle + mode chip. 2. **Listening** — waveform + "Analysing speech…". 3. **High confidence** —
verse + reason + confidence bar + Stage/Approve/Dismiss. 4. **Low + alternatives** — amber, alt matches, Edit.
5. **Auto-display** (mode ≥90%) — live badge + "auto-clears in 0:08 · hold to keep". 6. **On-air** — staged→live,
Clear output/Next verse. 7. **Duplicate/cooldown** — suppressed + "Show anyway / Mute". 8. **History** — Live/History
tabs, audit rows (staged/auto/dismissed) + re-stage. 9. **Provider offline** — "Detection unavailable · manual
still works" + Retry. Modes: Suggest only / **Operator confirms (default)** / Auto ≥ threshold.

### 5.6 App Navigation & Global Controls — `336:124`
Persistent shell present on every surface: **app menu** (workspace header + routed items w/ ⌘1–7, ⌘, shortcuts),
**⌘K command palette** (fuzzy; Actions / Navigate / Scriptures groups), **global chords** reference (Space, ⏎, ←→,
↑↓, B, Esc Esc, ⌘K, F, ⌘Z), **emergency footer** normal + blackout-active. Mirrors the implemented keymap
(`selahcue_app::keymap`, double-Esc 1000ms, chords pierce dialogs).

### 5.7 Settings — `338:124` (NEW build) — Providers & Privacy shown
Left nav (General / Providers & Privacy / Scripture / Outputs / Network & Mobile / Appearance / Security / Storage
/ About). Content realises the PRD provider abstraction + privacy: **offline-by-default banner**; Transcription
(On-device 🔒 "audio never leaves" vs Cloud ☁ opt-in with "streams live audio" warning); TTS (voice + **output
routing guard** "never routes to the main PA by default").

**SelahCue AI — sermon notes (platform-managed, no keys).** Per owner decision (2026-08-01), non-technical
operators must never see providers, tokens, keys, or external billing in the normal path. The AI Sermon Notes
section is a single **SelahCue AI** card:
- Header: "SelahCue AI" + **INCLUDED** badge + live status chips (**Service: Available**, **Cloud: connected**).
- **Privacy statement** (always visible): "Only your completed transcript is sent for processing — never live
  audio, and never during the service. Nothing is sent until you press Generate."
- **Usage allowance**: "12 / 40 sermon-note generations this month" + progress bar + "28 remaining · resets <date>".
- **Default notes template** (select) + **Preferred Bible translation** (select).
- **Include in notes** toggles: Prayer points, Chapter markers, Scripture extraction, Notable quotations, Short
  summary, Social excerpts.
- **Generate Sermon Notes** primary action + consent sub-line ("you'll see exactly what's sent and confirm first").
- **Advanced (collapsed) — "Bring your own key / custom provider"**: an *optional / enterprise* disclosure row,
  chevron-collapsed and de-emphasised. This is the ONLY place API keys / custom providers appear.

**Generate flow — `349:124`** (interaction states, shown before/around generation):
1. **Consent (before send)** — "Generate sermon notes?" modal: ✓ completed transcript is sent · ✗ raw audio never
   sent · ☁ processed by SelahCue's cloud AI, not stored after · "uses 1 of your 28 remaining" · "don't ask again
   for this service" · Cancel / **Generate**. Shown every generation unless muted for the service.
2. **Generating** — progress with steps (transcript sent → extracting → drafting) + reassurance "your audio never
   left this device" + Cancel.
3. **Notes ready** — **AI-GENERATED DRAFT** badge, preview (title, main scripture, points, extras), amber "review
   & edit before publishing — your transcript is unchanged", Regenerate / Open in editor; usage increments.

**Limit & failure states — `351:124`** (the unhappy paths; every one reassures the operator that the service,
transcript and manual notes are unaffected):
1. **Approaching limit** — inline amber usage (e.g. 38/40) + "only 2 generations left this month · resets <date>";
   Generate still works.
2. **Quota exhausted** — pressing Generate at 40/40 opens a blocked (not dead-end) modal: reset date + "transcript
   is saved, write notes manually or export" + options (remind-me-on-reset, use-my-own-key→Advanced) + Got it.
3. **Service unavailable** — AI provider unreachable modal: "doesn't affect your service" + "Service: Unavailable ·
   retrying automatically" + "no generation was used" + Write manually / Try again.
4. **Generation failed** — mid-draft error modal: "transcript is safe and unchanged · this didn't count against
   your allowance" + Cancel / Retry.

Backend implication: SelahCue operates the notes provider (platform key held server-side, never on the client);
the client needs a **usage/allowance meter** (with approaching-limit + exhausted states), a **transcript-only**
send contract (no audio), and graceful **service-unavailable / failed** handling that never charges the
allowance. BYO-key stays a hidden advanced/enterprise path.

### 5.8 Mobile Remote — `342:124` + RBAC set `354/355/357:124` (Flutter)
**Base surfaces — `342:124`:** Pairing/discovery (LAN hosts + PAIRED chip + Connect + QR), Live control (role chip,
ON-AIR verse preview, UP NEXT, Prev/Next, **GO LIVE**, Blackout/Clear), Scripture (search + translation + verse
list w/ per-verse stage → operator confirms), Timer (countdown, ±1:00, Pause/Reset/Stop, **Send "TIME UP" to
stage**). Desktop stays the authoritative state owner; losing the phone never stops the presentation.

**RBAC is the spine of the mobile app** — 7 scoped roles × 14 capabilities, **enforced server-side on the
authoritative desktop, deny-by-default, client-asserted role never trusted** (FR-090). Full matrix + the four
value classes (✅ full · 👁 view-only · ⚠️ limited/with-approval · ❌ none) rendered at **`354:124`**; canonical
source is `docs/business/PERSONAS.md §2` / PRD §16. The `⚠️` cells are **Administrator-configurable per-org**.

**Role-adaptive home screens — `355:124`:** the app renders *only the permitted controls* for the paired role,
with an honest lock-note for what's out of scope. Six designed:
- **Observer** — view-only (previews + transcript view); a "controls disabled" banner; triggers nothing.
- **Worship Leader** — lyric Prev/Next-line + Repeat-section + quiet cues to booth (Repeat/Vamp/Move-on); no
  scripture/blackout/broadcast.
- **Scripture Operator** — the human gate: an **approve-detected-suggestion** card (Approve→Live / Reject) + search
  + verse-stage + translation switch.
- **Timer Operator** — countdown + presets + ±1:00 + Pause/Reset/Stop + **Send TIME UP to stage** + stage messages;
  no content control.
- **Production Operator** — near-full remote: tabbed (Live / Lower-thirds / Macros / Health), monitors, transport,
  Blackout/Clear; everything but admin.
- **Administrator** — on mobile this is a **full control surface** (all control capabilities + **editable full live
  transcript**, no lock-outs). Pairing and role *management* are **not** on mobile — they live on the desktop (see
  Remote Control below). (Presenter ≈ the base Live-control surface.)

**Enforcement states — `357:124`** (deny-by-default made real, all experienced *on the mobile client*):
1. **Permission blocked** — tapping a control the role lacks opens a sheet ("that's not in your role" + which roles
   can + Request access) — never a silent dead-end.
2. **Role changed — live** — a downgrade banner appears and live controls are removed **immediately** (FR-090);
   view access remains.
3. **Action rejected** — a stale/unvalidatable command is **rejected, not queued** (FR-097), with a reconnecting toast.
4. **Access revoked** — admin unpair → full-screen "access removed · the live service is unaffected · scan QR to
   pair again".

**Navigation model — `363:124` (matches the built app — one nav system):**
- **Bottom tab bar = primary navigation:** `Live · Plan · Scripture · Timer` (exactly the shipped pattern). This is
  the *only* content navigation — there is **no hamburger menu**.
- **Tabs are role-scoped:** a role only sees tabs it can use; view-only capabilities show a 👁 tab; capabilities it
  lacks are hidden. Production/Admin-only tools (lower-thirds, macros, output-health, Admin's editable transcript)
  live under a **"More"** tab. The board renders the tab-bar variant for all 6 roles.
- **ⓘ (top-right) = session overflow → the Config/About sheet** (matches the built app's About). Leads with the
  identity header (**S · SelahCue · Controller · <Role>**) + **CONNECTION** (Status / Host / **Role, read-only** /
  Fingerprint) + **Disconnect this device** — exactly the shipped layout. Extended below: preferences (keep-awake,
  haptics, reduced-motion) + About (version, licenses, help). It is a **sheet from the ⓘ**, not a menu.
  ⚠️ **Naming to reconcile:** the shipped app labels the role **"Producer"**; the RBAC matrix (PERSONAS §2) calls
  it **"Production Operator."** The design uses "Production Operator" for consistency with the 7-role matrix —
  pick one canonical label and align the app + docs.
- **Emergency (Blackout / Clear-All)** stays pinned above the tab bar on every tab.

**Pairing + role assignment is a DESKTOP responsibility — `359:124`** (not mobile). The desktop **Remote Control ·
Devices** page holds: the **QR code** to pair (single-use, TLS-pinned host fingerprint, expiry + regenerate),
**pending-request approval** (verify fingerprint → assign a role → Approve/Deny), and the **paired-devices table**
(per-device role dropdown, last-seen, online/idle status, **Revoke**). Roles are enforced server-side here; a role
change or revoke takes effect on the device immediately and is written to the audit log (FR-086/089/147/150). The
mobile only ever *scans* a QR and *receives* a role — it never assigns one.

**A11y (NFR-026):** mobile ships accessible labels + **≥44×44pt touch targets** (all primary controls sized for it).

### 5.9 Pre-service Check — `344:124` (NEW build)
Grouped checks (Displays & Outputs, Media, Audio, Storage/Network/Providers) with ✓/⚠/✕ status + quick-fix
actions. Readiness sidebar: "Safe to start" ring, Passed/Warnings/**Blocking** breakdown, review-before-start
warnings, **Start service** (gated on 0 blocking), Re-run checks.

### 5.10 System & Recovery States — `346:124` — 6 vignettes
Blackout active (black monitors + red footer + Restore), Network lost (mobile paused, "presentation unaffected"),
Output lost → auto-recovery (holds last frame, retries, reconnected toast), Empty plan, **Crash recovery** dialog
("session recovered · autosaved 10:47" + Restore/Start fresh), Missing-media fallback (dashed placeholder +
"audience never sees an error"). These encode the PRD reliability promises.

---

### 5.11 Stage / Confidence Display — themes (engine output render, individual frames)
**Stage and confidence are one display type** with a selectable **theme** per screen (drawn by `StageTheme`,
high-contrast, glanceable). Each design is a standalone frame:
- **Worship theme** (`373:133`) — top bar (song + position + wall-clock), large **NOW** lyric + dim **NEXT**,
  bottom **Service Timer** bar (green).
- **Scripture theme** (`374:128`) — gold reference + large scripture + **NEXT** + a prominent **TIME-LEFT** panel.
- **Timer-only theme** (`374:151`) — just a big countdown + date; for pre-service / segment clocks.
- **TIME-UP behavior differs by theme:**
  - **Content themes** (Worship, Scripture) flip **only the clock/timer region** to "TIME UP · OVER m:ss" — the
    lyric/scripture **stays on screen** (`373:159` = worship inline TIME UP).
  - **Timer-only theme** goes **full-screen** "TIME UP" (`374:166`).
  - All TIME-UP states are **solid, never flashing** (WCAG 2.3.1, ≤3 Hz).
- **Stage message** (`375:128`) — a stage-manager/production cue banner (e.g. "WRAP UP · 2 MIN LEFT") over dimmed
  content; available on any content theme.
- **Per-output region toggles** (configured in Screens & Outputs `327:124`): Now / Next / Clock / Timer+TIME-UP /
  Stage message / Theme background. **The audience output never shows** the timer, next-line, or stage messages —
  guards operator/production info from leaking on-screen. Text sized for platform legibility (NFR-020).

## 6. Accessibility annotations

- **Contrast**: re-audit required (§3.2). Target AA (≥4.5:1 text, ≥3:1 large/UI). Bright inks on `*-soft` tints
  and on `base/surface` must be measured; the amber warn ink on warn-soft is the tightest pair — verify.
- **Never colour alone (1.4.1)**: LIVE/PREVIEW/ON-AIR/STAGED always carry a text label + often a shape (dot/frame).
  Status icons (✓ ⚠ ✕) accompany status colour on every check row and detection card.
- **Keyboard**: every action has a chord (see `336:124`); focus order follows visual order; ⌘K reachable
  everywhere; Esc Esc clears; B blackout. Emergency controls remain operable while a row/input is focused.
- **Focus visible**: use `primary` 2px ring on focus (selection uses the same violet — keep focus ring distinct
  from selection fill, e.g. ring + offset).
- **Reduced motion**: honour `prefers-reduced-motion` (transcript shimmer, waveform, spinners → static). TIME UP is
  solid-inverted, no flashing (ADR-0015).
- **Touch targets (mobile)**: primary controls ≥ 44pt (GO LIVE, transport, timer, Send TIME UP are sized for it).
- **Screen reader**: blackout button `aria-pressed` + "ON" label (existing); detection actions need labelled
  buttons; monitor regions need alt text describing current/next content.

---

## 7. Content / copy guidance

- **Reassurance under failure** is the voice: "presentation unaffected", "audience never sees an error",
  "works with no network", "session recovered · your edits are safe". Keep it.
- **Privacy is explicit**: "audio never leaves this machine", "streams live audio to the provider while active",
  "sent only when you press Generate", cost + retention stated inline. Do not soften.
- **Destructive/emergency** copy names the consequence: "Audience sees nothing · press B to restore".
- Scripture references use gold; verse numbers are gold; translation shown as `· KJV`.

---

## 8. Routing to specialist skills (suggested stories)

| Work | Owner skill | Depends on |
|---|---|---|
| Design 2.0 token migration (4 pinned surfaces + WCAG re-audit) | `/backend-engineer` (tokens) + `/accessibility` | this handoff |
| Operator Console re-skin (console IA already matches) | `/frontend-engineer` | token migration |
| Presentation & Media (mini-deck editor + media library) | `/frontend-engineer` + `/backend-engineer` (slide model, media decode) | FR-002/009/066 |
| Settings — Providers & Privacy (transcription/TTS) | `/frontend-engineer` + `/backend-engineer` (provider abstraction) | R3/R5 provider work |
| SelahCue AI notes — platform-managed service (server-side key, usage meter, transcript-only send, consent flow) | `/backend-engineer` + `/frontend-engineer` | R5 sermon-notes |
| BYO-key / custom provider (advanced/enterprise, hidden) | `/backend-engineer` | after platform-managed ships |
| Detected Scriptures panel + states | `/frontend-engineer` | R4 detection (`selahcue-scripture`) |
| App shell (menu, ⌘K palette, chords, footer) | `/frontend-engineer` | keymap (done) |
| Mobile remote — base surfaces + 6 role homes + enforcement states | `/mobile-engineer` (client) | pairing |
| Mobile RBAC — server-side role enforcement (deny-by-default, immediate downgrade, reject-not-queue) | `/backend-engineer` (`selahcue-app`) | FR-090/097; §16 matrix |
| Pre-service check | `/frontend-engineer` + `/backend-engineer` (health probes) | output/media/audio health |
| Stage & Confidence outputs (StageTheme render + region toggles + TIME-UP overrun) | `/backend-engineer` (engine render) + `/frontend-engineer` (Screens config) | Timers epic; output-management |

Register these in ClickUp under the existing epics (Accessibility & Design System `86ajp08bx`, Presentation &
Slides `86ajp07ce`, plus Console/Canvas). **Planning only — do not implement from this doc without a Goal Contract.**

---

## 9. Open questions / decisions for the owner

1. **Token adoption**: confirm we migrate the canonical tokens to Design 2.0 (coordinated 4-surface + WCAG story),
   vs applying the new neutrals/brand only to the webview first. Recommend the coordinated migration.
2. **Detected Scriptures populated vs empty**: live app currently ships the empty state; the spec now covers all 9.
   Confirm the auto-display threshold default (design assumes ≥90%, mode default = Operator confirms).
3. **Presentation/Media**: this is net-new build scope (paused earlier). Confirm it re-enters the queue and at what
   release (design assumes it slots against FR-002/009/066).
4. **Mobile RBAC** *(designed against the documented matrix — PERSONAS §2 / PRD §16, at `354/355/357:124`)*. The
   7 roles and their 14 capabilities are now drawn; residual **open permission decisions** are values in the `⚠️`
   cells, tracked in OPEN-DECISIONS: Blackout for lower roles (OD-12), per-output permissions (OD-14), macro
   granularity (OD-17). The design shows the recommended defaults and marks all `⚠️` cells as Admin-configurable —
   confirm the ship-one defaults and whether per-output scoping lands in MVP or R2.
5. **SelahCue AI allowance** *(direction decided 2026-08-01: platform-managed, no user keys in the normal path;
   all limit/failure states now designed at `351:124`)*. Remaining product inputs are values, not UX: the actual
   monthly quota (design shows 40/month), the reset cadence, and the exhaustion policy the design assumes
   (**hard block until reset, with manual-notes + BYO-key fallbacks offered — no silent upsell**). Confirm the
   numbers and whether a paid top-up path exists (would add one "add generations" affordance to the exhausted modal).
