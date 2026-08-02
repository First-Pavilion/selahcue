# Operator Console — Design 2.0 rewrite (spec)

Status: approved direction (owner Q&A 2026-08-01) · Design source: Figma
`SYQn5hFY8YVQKm3c6rw0eJ` node `312:124` ("SelahCue · Operator Console (Design 2.0)") ·
Token source: `docs/design/DESIGN-TOKENS.md` §"Design 2.0" (`--sc-*`, pinned by
`selahcue-present/tests/test_tokens.rs`). Supersedes the foundation slice
`TASK-design2-reskin-operator` (value-only var swap, commit 445a97e).

## 1. Objective

Rewrite the operator webview (`selahcue-operator/dist/index.html` + `app.css`, with
targeted `app.js` and Rust plumbing) to the full Design 2.0 Operator Console: a rich
topbar transport, rounded Design-2.0 cards, colour-coded plan badges, gradient
Preview|Live monitors, a re-styled service timer with **Pause** + an **HH:MM:SS**
custom-time control, detected-scripture cards with **match-%**, and a deep-red
emergency footer — while preserving every behavioural invariant and pinned test.

## 2. Hard invariants (must stay green)

`test_tokens.rs` concatenates `index.html`+`app.css`+`app.js` and pins ~90 needles.
The rewrite preserves ALL of them:

- **Element-ID/class contract**: `app.js` (2,669 lines, 180 `getElementById`) drives
  behaviour off exact ids/classes. Every id it reads and every structural hook it
  queries (`zone-left`/`zone-center`/`zone-right`, `obs-row`, `#preview-panel .surface`,
  `#live-panel .surface`, `.nav-item`, `.listen-ico`, all `td-*`, `#screens-list …`) is
  kept. IDs are the API between markup and logic.
- **Canonical §4 status tokens** stay defined in `:root` (`--preview/--live/--warn` +
  inks = the six pinned hexes `#0f7b6c #a3283a #9a5b00 #2bb673 #ef4444 #f2b53c`) and the
  Rust WCAG audit is untouched. Badges *adopt* the Design-2.0 chip pattern (`--sc-*`
  soft-tint bg + bright ink), which is separately WCAG-audited (`design2_palette_meets_wcag_aa`).
  Nothing canonical is removed — only the *visible* skin changes.
- **Structural invariants**: `#emergency` footer stays a sibling **after** `</main>`;
  the console stays `id="surface-console" class="surface-page active"`; the app-menu
  router (roles, `data-surface`, `accesskey`) is intact; `"CLEAR ALL"` survives as the
  clear button's `aria-label` (visible text becomes "Clear Output"); `"PREVIEW · STAGED"`,
  `"LIVE · ON AIR"`, `"BLACKOUT — OUTPUT DARK"`, `aspect-ratio: 16 / 9`, `"KJV"`,
  `transcription (R3)`, `detection (R4)`, `MAX_TRANSCRIPT_ROWS = 120`/`slice(-MAX_TRANSCRIPT_ROWS)`
  all remain.
- **Accessibility**: `aria-pressed` state on toggles, non-colour redundancy on
  LIVE/STAGED (label + border, never colour alone), `prefers-reduced-motion` honoured,
  AA contrast (Design-2.0 palette is audited; `text-muted` stays label-only per §6).
- The Theme Designer / Screens / saved-theme-library / per-screen-theme / font-picker
  surfaces and their pinned ids are **out of scope** and left byte-stable except where
  they inherit the shared token/button restyle.

## 3. Layout → surface mapping

Root: column flex — **topbar → body(3-col) → emergency footer**.

- **Topbar** (`<header>`): logo pill (icon + "SelahCue ▾" = the existing app-menu
  button), a divider, "Live Console" label (the surface name), a right cluster of
  transport mirrors (`◀ Previous`, `Next ▶`, gradient `● GO LIVE`, `Blackout`) reusing
  the existing `previous/next/go_live/blackout` handlers, a timer chip (⏱ + `#clock`-adjacent
  readout), the clock, and a **● Connected** status pill (host/remote-connection derived).
- **Left column** (`zone-left`, 380px): **Service Plan** card — header + "N items"
  count pill; plan-item rows re-skinned to rounded D2 cards with colour-coded kind
  badges (SONG=`--sc-primary-hover`, SCRIPTURE=`--sc-gold`, ANNOUNCEMENT=`--sc-info`,
  SECTION=`--sc-text-secondary`) and inline LIVE (`--sc-live` chip) / STAGED
  (`--sc-preview` chip); add-row (kind select + title + gradient `+ Add`). **Live
  Transcript** card — REC pill, streamed lines (recent bright / older dim), red
  `■ Stop listening`.
- **Center column** (`zone-center`): `obs-row` = gradient Preview (green border/pill)
  | Live (red border/pill) 16:9 monitors with "1920 × 1080"; gradient GO-LIVE row with
  kbd chips; Scriptures browser (KJV pill + search, chapter nav, verse rows with gold
  verse-nums + STAGED pill); footer hint line.
- **Right column** (`zone-right`, 380px): **Service Timer** — RUNNING/PAUSED pill, 54px
  readout in an inset, `#timer-big` subtext, **SET A CUSTOM TIME** HH:MM:SS spinner +
  gradient Start, quick-set (5:00/10:00), ±1:00, **Pause**/Reset/Stop. **Detected
  Scriptures** — "N new" count, **Mode: Operator confirms** control, detection cards
  (gold ref, match-% pill coloured by confidence, snippet, meta, Stage/Approve/Dismiss).
- **Emergency footer** (`#emergency`, after `</main>`): deep-red bar — gradient
  `■ BLACKOUT`, `Clear Output` (aria-label "CLEAR ALL"), centre note, **● Offline-ready** pill.

## 4. New behaviour — three tiers

**Tier 1 — frontend only (no backend):**
- HH:MM:SS custom-time spinner → composes H·3600 + M·60 + S → existing `start_timer(seconds)`.
- Count pills ("N items", "N new") derived from `view.plan` / `view.detections`.
- RUNNING/PAUSED and Connected/Offline-ready pills derived from existing state
  (timer snapshot + connection/local mode).

**Tier 2 — backend vertical slice (Timer Pause/Resume):**
- `Command::PauseTimer` + `Command::ResumeTimer` (protocol.rs) → RBAC `Timer` role →
  controller match arms using core `Timer::pause`/resume (time already banks across
  segments) → `TimerSnapshot { … paused: bool }` → `operator.rs` local+remote wrappers →
  `#[tauri::command] pause_timer`/`resume_timer` registered in `main.rs` → JS toggle.
- Tests updated: protocol round-trip + RBAC + controller + operator for the new
  variants and the `paused` field.

**Tier 3 — detection match-% (additive wire field):**
- `DetectionView { … confidence: Option<u8> }` (integer percent, `#[serde(default,
  skip_serializing_if = "Option::is_none")]`) — additive so existing serde round-trips
  stay green. Rendered as a match-% pill (green ≥90 / amber otherwise) **only when
  present**; stays absent until the R4 detection engine surfaces real confidence
  (honest-empty — never fabricated).

## 5. Decisions locked (owner Q&A)

1. Scope = re-skin **and** wire new behaviour (not skin-only).
2. New controls wired fully now (Pause, HH:MM:SS, Mode) — no fakes.
3. Adopt Design-2.0 chips for visible status; keep canonical §4 vars defined.
4. Detection **Mode**: "Operator confirms" is the live mode; auto-stage/auto-approve
   render as honest disabled "later" options — **FR-115 preserved** (detections never
   auto-display).
5. Detection **match-%**: add the additive `confidence` wire field; render when present.

## 6. Verification

- `node --check app.js` (WKWebView-safe, no build step for the webview).
- `cargo test -p selahcue-present --test test_tokens` (all operator pins + Design-2.0
  palette + WCAG audit) and `cargo test -p selahcue-present`.
- `cargo test -p selahcue-lan` (protocol round-trip + RBAC incl. new timer variants +
  DetectionView.confidence) and `-p selahcue-core` (timer) and `-p selahcue-app`
  (controller/operator).
- `make ci` (fmt --check + clippy + test) — the CI gate.
- `python3 scripts/operator_headless.py` / `operator_webkit_smoke.py` where runnable.
- Visual QA of the running Tauri webview is owner-run (no in-repo render harness).

## 7. Non-goals / risks

- Non-goals: Theme Designer / Screens / Plan-Library / Settings surface redesign (they
  inherit the shared token+button restyle only); OS-global emergency hotkeys; real R4
  auto-detection; native file pickers.
- Risks: (a) breaking a pinned needle or a JS ID hook — mitigated by the preserved-ID
  contract + running the full pin suite; (b) the timer protocol change rippling through
  RBAC/round-trip tests — mitigated by tracing every construction site first (understand
  phase) and updating tests in the same slice; (c) WKWebView quirks (`[hidden]` vs author
  `display`, no `window.prompt`, physical-key chords) — follow the existing patterns.
