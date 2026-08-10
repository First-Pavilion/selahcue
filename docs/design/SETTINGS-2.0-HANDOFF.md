# SelahCue — Settings (Design 2.0) Handoff

**Status:** design complete — 8 pages + every meaningful state, high-fidelity.
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` · **Section:** `593:124` "SelahCue · Settings — Design 2.0 (8 pages + all states)".
**Reference (pre-existing):** Settings — Providers & Privacy `338:124`.
**ClickUp:** [STORY — Settings (Design 2.0)](https://app.clickup.com/t/86ajxucue) under [EPIC — Accessibility & Design System](https://app.clickup.com/t/86ajp08bx).
**Goal Contract:** `docs/delivery/goals/GOAL-design-settings-2.0.md`.
**Grounding:** DESIGN-2.0-HANDOFF §5.7, SelahCue-PRD (FR/NFR), UX-CANONICAL, UX-STATE-MATRIX, NAV-IA-spec, THEME-MODEL-spec, DESIGN-TOKENS; implemented code in `implementation/desktop/crates/` (scripture `Translation::ALL`, `selahcue-data` SQLCipher/backup/integrity, `selahcue-desktop/src/keys.rs`, `selahcue-lan` cert fingerprint).

Frame link pattern: `https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=<id-with-dash>` (e.g. `577-126`).

---

## 1. Scope & method

The Settings surface has a **9-item sidebar**; only **Providers & Privacy** was designed. This delivers the other **8 pages** at the same Design-2.0 fidelity, each with **every meaningful non-default state as its own full-page frame** (owner decision, this session). Total **51 frames** (8 defaults + 43 states).

Each frame **clones the reference chrome from `338:124`** — identical top bar (logo, "All changes saved" auto-save indicator), left sidebar, deep-ink background — then sets the correct active nav item and rebuilds the content column. This guarantees pixel-consistency with the shipped reference page. Frames auto-fit their height so every control is visible for review.

---

## 2. Design system reused (no new patterns)

Tokens (Design 2.0 `--sc-*`, from DESIGN-TOKENS.md; extracted verbatim from `338:124`):

| Role | Value | Role | Value |
|---|---|---|---|
| page base | `#0b0d12` | text | `#f4f6fb` |
| surface (sidebar/cards) | `#14161d` | text-secondary | `#a7aebe` |
| selected card | `#171a2a` | text-muted (labels only) | `#6b7383` |
| elevated | `#1c1f28` | brand primary / hover | `#6e5cf0` / `#7e6eff` |
| inset (fields, icon boxes) | `#0f1116` | scripture gold | `#f2b84b` |
| border / strong | `#262a34` / `#363b47` | | |

Status (one meaning per family, **fixed, not user-recolourable** — UX-CANONICAL §4): live/on-air red `#ff4d4d` (soft `#2a1416`), preview/safe green `#35c08a` (soft `#10231c`), warn amber `#f5a524` (soft `#2a2415`), info blue `#38bdf8` (soft `#10222b`).

Type: **Inter** (Regular/Medium/Semi Bold/Bold). Title 20 · section label 12 uppercase tracked · card title 15 · body/help 12 · meta 11.

Component primitives reused (COMPONENT-SPECS §4): section label, card (13px radius, 15 pad), selected/radio card, badge pill (999), info/warn/danger banner, toggle 42×24, radio 20, select 38 + chevron, input, segmented, slider, meter, list row, row card, kbd chip, primary/ghost/danger button, type-to-confirm dialog (dimmed scrim overlay). No new pattern language was introduced.

**Chrome note:** the reference Settings frame does not re-draw the global emergency footer (BLACKOUT / CLEAR-ALL); per UX-CANONICAL §3 that footer + global chords (`Cmd/Ctrl+.`, `Cmd/Ctrl+B`) live in the app shell (`336:124`) and persist over every surface, including Settings, and must never be occluded by a settings modal. These frames match the reference and rely on the shell footer.

---

## 3. Cross-page reconciliations (single source of truth)

Resolved during an independent coverage critique before build:

- **Updates:** **About** owns the update *action* + states (Check / Download & install / checking / available / error). **General** keeps update *preferences* only (auto-check, auto-download, channel) and links to About. **Security** shows update *status* and links to About. One state machine, not three.
- **Stage look:** **Appearance** is the single home for default stage theme, high-contrast, stage large-text size, and stage-clock format. **Outputs** keeps output-specific region toggles (Now/Next/Clock/Timer/Stage-message/Theme-bg) + TIME UP safety, and **links to Appearance** for theme/text/contrast. **General** no longer carries stage clock.
- **Reduced motion — exactly two scopes:** operator-UI (General = source, Appearance = mirror; one value) and audience/stream output (Outputs = source). Defaults reconciled to "Follows system". Seizure caps are always-on regardless.
- **Revoke all devices:** canonical on **Network & Mobile** (type-to-confirm "revoke all"); **Security → Danger Zone** links to it (no duplicate token).
- **Audit log:** canonical table + export on **Security**; Network links to it.
- **Permission-denied copy:** standardized neutral line "Some settings are managed by your administrator." across all pages (no info leak, no silent shorter page).
- **Provider/API keys:** appear in exactly one place — the Providers & Privacy advanced row + OS secret store. No raw key field on any of these 8 pages (Network shows the public cert *fingerprint*, not a secret).

---

## 4. Per-page specs

Each page lists its default node, sections (→ requirement), and its state frames (→ node). Deferred controls (R2–R5) render as honest disabled "Coming in Rn" affordances, never omitted or faked.

### 4.1 General — `577:126` (nav 0)
**FRs:** FR-014 (remappable shortcuts, NFR-019), FR-175 (reduced motion), FR-155 (signed/anti-rollback updates), FR-008 (pre-service check), FR-037 (stage clock via Appearance), NFR-025 (localisation readiness), FR-162/FR-055/FR-016 (shortcut targets).
**Sections:** Organisation identity (name, logo) · Startup (radio) · Language & region (language + date/time; "more languages R2") · Keyboard shortcuts (remap table; emergency chords remap-only, cannot be unbound — FR-014/UX-CANONICAL §1) · Accessibility (reduce motion, operator-UI scope) · Software updates (preferences + link to About) · Pre-service check (subsystem toggles + block-on-blocking).
**States:** language-restart `585:127` · permission (org identity + updates hidden) `585:430` · save-failure (auto-save can't write, FR-169 — never silent) `585:731`.

### 4.2 Scripture & Translations — `578:124` (nav 2)
**FRs:** FR-025 (translations/default), FR-035 (attribution), FR-029 (pagination), FR-031 (history/favourites), FR-028 (keyword search), FR-030 (compare R2), FR-032 (custom layouts R2), FR-033/034 (import/API R4), FR-146 (export licensing R4).
**Sections:** Installed translations (5 bundled PD rows: KJV·WEB·ASV·WEBBE·DBY, enable/default/reorder, Public-Domain badge) · Default translation · Pagination & formatting · History & favourites · Search (rebuild index) · Side-by-side (R2) · Custom layouts (R2) · Add a translation (R4, advanced; keys route to Providers & Privacy) · Export licensing.
**States:** empty (no added translations) `586:127` · add-translation expanded `586:364` · permission (import hidden) `586:617` · error (translation not installed) `586:855`.
**⚑ Product flag** — see §6. On-frame amber design-team callout beside `578:124`; NOT rendered in app UI.

### 4.3 Outputs & Displays — `579:124` (nav 3)
**FRs:** FR-151 (venue profiles), FR-040/046 (displays/identify/window), FR-068/161 (audio output device + disconnect — added per critique), FR-037 (region toggles), FR-059/062/175 (TIME UP safety, flash cap), FR-038/163/044/042/043/140/141/048/052 (R2 per-output, health, test patterns, network outputs), FR-175 (audience/stream reduced motion).
**IA:** links out to **Screens & Outputs `327:124`** for live per-screen assignment; holds defaults/profiles/advanced only.
**States:** detecting (loading, matrix §8) `587:127` · empty (no displays) `587:422` · mismatch (display disconnected, amber) `587:717` · identify-active (aria-pressed) `587:1025` · error (holding last frame, isolated) `587:1333` · permission (view only) `587:1629`.

### 4.4 Network & Mobile — `580:124` (nav 4) — Administrator-only
**FRs:** FR-085 (LAN server/mDNS), ADR-0008/FR-088 (TLS pinned cert fingerprint), FR-148/089 (paired devices/revoke), FR-147/090/149 (roles/grants; R2 time-boxed), FR-091 (rate limits), FR-150 (audit), ADR-0003 (preview stream).
**IA:** links out to **Remote Control · Devices `359:124`** for QR pairing / role assignment / per-device revoke.
**States:** empty (no devices) `588:127` · permission (removed from non-admin sidebar; neutral panel if deep-linked) `588:308` · error (cert/fingerprint mismatch) `588:486` · degraded (mDNS unreliable → QR) `588:665` · regenerate-certificate confirm (type "regenerate") `588:844` · revoke-all confirm (type "revoke all") `588:1033`.

### 4.5 Appearance — `581:124` (nav 5)
**FRs:** NFR-020 (high-contrast/large stage text), FR-175 (reduced motion mirror), FR-010 (default slide theme → Theme Designer `317:124`), FR-037 (stage clock).
**Note:** "theme" = slide/stage template, **not** a light/dark colour mode (THEME-MODEL-spec) — no colour-mode switch offered. Broadcast-semantic colours are fixed (on-frame guardrail).
**Sections:** Operator UI (density, text size) · Contrast & legibility (live stage-preview mini-monitor + high-contrast + stage text size) · Motion · Default slide theme · Default stage theme (radio cards) · Stage clock · Brand accent (R2, excludes semantic colours).
**States:** high-contrast + large text (preview flips) `589:127` · reduced-motion applied `589:337` · reduced-motion OS-forced (locked) `589:534` · permission (brand accent hidden) `589:728`.

### 4.6 Security — `582:124` (nav 6)
**FRs:** FR-154/159 (at-rest encryption, key source), NFR-017 (secret store), FR-150 (audit table + export), FR-155 (signed-update status), FR-156 (model integrity R3), FR-158 (recording consent R3), FR-153 (retention/deletion R3), FR-137/132 (cloud consent link), FR-176 (privacy policy). Code: `open_encrypted` (SQLCipher), `keys.rs` (Keychain/DPAPI/Secret Service + Argon2id).
**States:** passphrase-vault (no keychain path) `590:127` · permission (consent/retention/danger hidden) `590:368` · error-keychain (loud warning, no plaintext) `590:591` · purge-secrets confirm (type "purge") `590:814` · delete-recordings confirm (type "delete") `590:1047` · change-passphrase form dialog `590:1280` · audit empty `590:1519` · destructive result / recovery `590:1741`.
**Copy:** destructive dialogs say "back up your recovery-key file" (no internal filename / crypto jargon in the primary line).

### 4.7 Storage & Backups — `583:124` (nav 7)
**FRs:** FR-079 (backup/integrity), FR-157 (encrypted backups R2), FR-080 (auto backups R2), FR-169/081 (low-disk warning/safe-mode), FR-071/NFR-013 (media cache R2), FR-074/075/NFR-023 (autosave/crash-loop), FR-082/ADR-0011 (redacted diagnostics R2), FR-138/139 (import/export + path safety). Code: `backup_to`, `backup_to_encrypted`, `integrity_check`, `checkpoint_truncate`.
**States:** low-disk warning `591:127` · backup-in-progress (loading) `591:373` · operation-failed `591:620` · export-location warning `591:858` · restore confirm (type "restore") `591:1102` · never-backed-up (empty) `591:1350` · permission (restore/relocate/schedule hidden) `591:1598`.

### 4.8 About & Licensing — `584:124` (nav 8)
**FRs:** FR-155/ADR-0012 (updates action home), NFR-027 (SBOM/licenses), FR-035 (scripture attributions), FR-140 (NDI attribution R2, conditional), CON-4/FR-072/073 (codec notice), FR-021/022 (song copyright/CCLI R2, conditional), FR-176/177 (privacy/DPA), FR-082 (diagnostics R2).
**States:** checking (loading) `592:127` · update-available `592:371` · update-error (offline-safe) `592:622` · conditional-rows-shown (NDI/cloud/CCLI active) `592:872` · permission (install/export admin-only) `592:1130`.

---

## 5. State matrix (kind → frame)

| Page | default | empty | loading | error | permission | destructive-confirm | recovery/other |
|---|---|---|---|---|---|---|---|
| General | 577:126 | — | — | save-fail 585:731 | 585:430 | — | restart 585:127 |
| Scripture | 578:124 | 586:127 | rebuild = N/A¹ | 586:855 | 586:617 | — | add-expanded 586:364 |
| Outputs | 579:124 | 587:422 | detecting 587:127 | 587:1333 | 587:1629 | — | mismatch 587:717 · identify 587:1025 |
| Network | 580:124 | 588:127 | — | 588:486 | 588:308 | regen 588:844 · revoke 588:1033 | degraded 588:665 |
| Appearance | 581:124 | N/A² | N/A² | N/A² | 589:728 | — | high-contrast 589:127 · reduced-motion 589:337 · OS-forced 589:534 |
| Security | 582:124 | audit 590:1519 | — | keychain 590:591 | 590:368 | purge 590:814 · delete 590:1047 | vault 590:127 · change-passphrase 590:1280 · result 590:1741 |
| Storage | 583:124 | never-backed-up 591:1350 | backup 591:373 | 591:620 | 591:1598 | restore 591:1102 | low-disk 591:127 · export-warn 591:858 |
| About | 584:124 | — | checking 592:127 | 592:622 | 592:1130 | — | update-available 592:371 · conditional 592:872 |

¹ Rebuild-keyword-index runs in the background with an aria-live progress announcement; no full-page loading frame is warranted. ² Appearance is a preferences-only page with a live preview; empty/loading/error are N/A — a preview GPU-loss is covered by the never-blank guarantee (NFR-024) upstream, not a settings state.

---

## 6. ⚑ Product flag — Scripture translation bundle (needs a decision)

**Conflict:** PRD **FR-025 / OD-24** says *exclude KJV* (UK Crown copyright) and bundle **WEB (default), ASV, BSB, BBE, Darby, Webster**. The **shipped code** (`selahcue-scripture` `Translation::ALL`) makes **KJV the default** and bundles **KJV, WEB, ASV, WEBBE, DBY**, citing an owner decision dated 2026-07-24.

**Design decision (this session):** the Scripture page reflects the **shipped code** (KJV default + WEB/ASV/WEBBE/DBY). The conflict is surfaced as a **design-team annotation beside frame `578:124`** — it is deliberately **not** rendered as an in-app banner (an earlier draft did; that would ship internal process copy to operators). **Product must reconcile the bundle before release** (drop KJV per FR-025, or record an owner override to FR-025). The translation list + default here are data-driven and update automatically once resolved.

---

## 7. Accessibility (testable)

- **Contrast:** all body/label/status text uses tokens audited AA on `base`/`surface` (DESIGN-TOKENS §"Accessibility note"). `text-muted #6b7383` is used **only** for tertiary labels/meta, never small essential body text (it clears AA-large, not AA-normal).
- **Colour is never the only cue:** every status carries a text label (PRIVATE/OPT-IN/ON/VERIFIED/EMERGENCY, "disconnected", "Blocked"); the mismatch state pairs an amber dot with the word "disconnected" (WCAG 1.4.1).
- **Keyboard/focus:** every control is a standard focusable primitive; reading/focus order follows top-to-bottom, left-column-then-right within two-column rows; the keyboard-shortcuts table is itself the remap surface (FR-014). Emergency chords are shown remap-only (cannot be unbound).
- **Targets:** rows, toggles (42×24 + 46-tall row hit area), buttons, and selects are sized for comfortable pointer + touch (≥44px effective row height).
- **Reduced motion:** honoured as two explicit scopes (operator-UI + audience/stream); OS-forced state shows the toggle locked with an explanatory note (`589:534`). Seizure caps (flash ≤3/sec, solid-inverted TIME UP default) are always-on and stated on Outputs.
- **Screen reader:** destructive dialogs are modal type-to-confirm; permission-denied removes controls from tab order rather than greying (no phantom focus stops); loading states are described in text ("Detecting displays…", "Backing up… 62%") for an aria-live/aria-busy channel.

---

## 8. Implementation notes & open questions

- Build the sidebar + top bar as the persistent Settings shell; render one content column per route. Auto-save (no Apply button) with the top-bar "All changes saved" indicator; surface save failures (General save-failure state) — never silent (FR-169).
- **Admin-gating** (FR-137/147/151): hide forbidden controls (remove from tab order), never grey-tease. Non-admin Network & Mobile is removed from the sidebar entirely.
- **Link-outs** (don't duplicate): Outputs → Screens & Outputs `327:124`; Network/roles/pairing → Remote Control · Devices `359:124`; Appearance slide theme → Theme Designer `317:124`; Scripture/Security/About keys & cloud consent → Providers & Privacy.
- **Open questions:** (1) Scripture bundle (§6) — product. (2) Audio-output device home: placed on Outputs per FR-068/161; confirm it shouldn't be its own page. (3) Confirm the audit log is a single append-only source shared by Network's link and Security's table (FR-150).

---

## 9. Independent design-QA

An independent multi-agent design-QA pass (8 reviewers, one per page) inspected all 51 rendered frames via screenshots against visual correctness, state coverage, copy, accessibility, and design-system consistency. It surfaced **6 critical, 6 major, 23 minor** findings.

### Fixed (all critical + all major + most minor)

- **CRITICAL ×6 — collapsed dialogs.** All six type-to-confirm/form dialogs (Network regenerate `588:844` + revoke `588:1033`; Security purge `590:814` + delete `590:1047` + change-passphrase `590:1280`; Storage restore `591:1102`) had rendered as a thin sliver — the dialog auto-layout height was frozen at 10px by a `resize(w,10)` call instead of hugging content. Fixed (`layoutSizingVertical = HUG`); all six now render as full centered cards on the dimmed scrim. Re-verified by screenshot (change-passphrase, restore).
- **MAJOR ×6:** General save-failure — top-bar badge now reads "Couldn't save — disk full" (red) instead of a contradictory "All changes saved" `585:731`. General language-restart — the Display language field now shows the pending "Español (España)" to match the restart banner `585:127`. Outputs view-only — banner reworded to promise only what's shown; window-mode + Flash controls now render LOCKED (not interactive) `587:1629`. Outputs mismatch — window-mode row restored alongside Reselect `587:717`. Security keychain-error — the contradictory green "encrypted / in your OS secure store" banner removed and the At-rest badge flipped ON → UNAVAILABLE `590:591`. Storage/General "R2/R3" roadmap codes removed from operator-facing UI (see below).
- **Jargon sweep (283 text nodes):** internal roadmap codes (`R2`/`R3`/`R4`) → "SOON"/"COMING SOON"; requirement/spec IDs in operator copy (`(NFR-025)`, `(WCAG 2.3.1 · UX-CANONICAL §4)`, `(FR-150)`, `per ADR-0008`, `(matrix §8)`) stripped from the app UI. The Rn→release mapping lives here in the handoff for the design team; the off-frame KJV design-note callout (which intentionally cites FR-025/OD-24) was preserved.
- **Consistency minors:** restored dropped standard rows/banners in About checking/error/permission/conditional-rows and Security passphrase-vault; added a consistent "Reduced motion is on" banner to the OS-forced Appearance state; recoloured the Outputs identify-active banner to the indigo action treatment; named the translation in the Scripture error ("ESV isn't installed"); added a "toggle shows in picker · ◉ sets default · drag to reorder" clarifier to the Scripture translation list; reworded the Network view-only card and empty-state icon; de-duplicated the About "Retry" row label.

### Accepted / documented (minor, deliberate)

- Permission-denied banners are **neutral** (not amber-tinted) on every page by design — an admin-managed state is not a warning; cross-page consistency was chosen over per-page scannability.
- Scripture keeps both the per-row "Default" radio and the summary "Default translation" dropdown (a common, tied pattern); implementation should keep the dropdown a reflection of the radio.
- `text-muted #6b7383` on `#14161d` for tertiary licence metadata clears AA-large, not AA-normal (DESIGN-TOKENS gate) — it is used only for non-essential labels; essential copy uses `text-secondary #a7aebe`.
- The top-bar "All changes saved" indicator is global chrome; on read-only About it never implies edits.
- The Storage export-location warning is shown in-state on the frame; at implementation, surface it adjacent to the Export action / in the export flow.

**Verdict:** no outstanding critical or major issues; coverage is complete and implementation-ready. The accepted minors above are polish notes, not blockers.
