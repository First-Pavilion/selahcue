# Goal Contract — GOAL-fe-providers-privacy

## Identity

- Goal ID: GOAL-fe-providers-privacy
- Parent goal ID: GOAL-be-providers-privacy (backend; ClickUp 86ajy034h)
- Title: Build the Settings → Providers & Privacy screen in the Tauri operator webview and integrate it with the shipped backend commands (Figma frame 338:124), rendering REAL backend state with honest not-configured / null-quota affordances
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy05r9
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 10
- Independent verification required: yes

## Objective

Replace the `#surface-settings` stub ("Application settings arrive later.") in the operator webview with the full Providers & Privacy panel from Figma frame `338:124` — Offline-by-default banner, LIVE TRANSCRIPTION (On-device / Cloud radio cards), and SELAHCUE AI · SERMON NOTES (provider status, consent, quota, template + translation selects, 6 include toggles, Generate) — wired to the already-shipped operator Tauri commands, rendering real backend state and honest placeholders (no fabricated numbers), verified by the headless webview gate and green `make ci`.

## Baseline

Verified this session:

- `#surface-settings` (index.html:930) is a stub: `<h1>Settings</h1><p class="coming-soon">Application settings arrive later.</p>`. It is already routed (`APP_SURFACES` includes `settings`, `showSurface` handles it, nav item exists).
- The backend (GOAL-be-providers-privacy, task 86ajy034h, status "code review") ships 9 operator-local Tauri commands: `providers_view`, `set_transcription_mode{mode}`, `set_cloud_consent{kind,enabled}`, `set_notes_template{template}`, `set_preferred_translation{code}`, `set_include_flag{name,enabled}`, `set_account_token{token}`, `clear_account_token`, `generate_sermon_notes{transcript}`. All but the last return `ProvidersView`; `generate_sermon_notes` returns `{ok,degraded,provider,draft,quota}` or `{ok:false,error,message}` (error ∈ consent_required|not_configured|quota_exceeded|transport|malformed).
- `ProvidersView` (operator/src/main.rs:2038): `cloud_status` is `"not_configured"` and `quota` is `null` in the current (no `cloud-live`) build — the live SelahCue service does not exist. `cloud_connected` is false. `on_device` = `{ready,state,model,detail}`.
- Established modular surface pattern: separate JS files (`preservice.js`, `remote.js`) as IIFEs that own their surface body, grab `window.__TAURI__.core.invoke`, and expose a global `window.<name>Activate` that `showSurface` calls. Design tokens are CSS custom properties `--sc-*` in app.css; reusable primitives exist (`.scr-toggle` 42×24, `.scr-select`, `.scr-pill-*`, status pills).
- The headless gate `scripts/operator_headless.py` injects a `window.__TAURI__` stub + a driver into the real dist; `EXPECTED_MIN_CHECKS = 425`. It records `ok(cond,msg)` results and records every invoke in `window.__calls`.
- Product decisions: TTS excluded (DEC-001); BYOK / "Advanced · custom provider" excluded (hosted-only). Both appear in the frame data but must NOT be built.

## Inputs and evidence sources

- Figma frame `338:124` (Settings — Providers & Privacy), file `SYQn5hFY8YVQKm3c6rw0eJ` — screenshot + get_design_context pulled this session (scratchpad/pp-frame.png).
- docs/design/SETTINGS-2.0-HANDOFF.md §2 (tokens/primitives) + §3 (reconciliations); docs/design/DESIGN-2.0-HANDOFF.md.
- Backend goal contract docs/delivery/goals/GOAL-be-providers-privacy.md + operator/src/main.rs commands (exact JSON shapes).
- MEMORY: hidden-attr-vs-css-display; operator-webview-wkwebview-layout-traps; match-figma-full-shell; themes-are-design-templates.
- ClickUp: backend task 86ajy034h; design story 86ajxucue; epic 86ajp08py.

## Scope

### In scope

- Build the `#surface-settings` body as the Providers & Privacy panel (HTML in index.html), styled with reused `--sc-*` tokens (new `pp-*` classes in app.css), wired in a new `settings.js` IIFE module (loaded after app.js) exposing `window.settingsActivate`, called from `showSurface("settings")`.
- Three sections top-to-bottom: (1) Offline-by-default green lock banner; (2) LIVE TRANSCRIPTION two radio cards (On-device PRIVATE + model detail from backend; Cloud OPT-IN + amber live-audio warning + consent footer); (3) SELAHCUE AI · SERMON NOTES (provider card + INCLUDED badge + honest status pills, green consent banner + consent control, quota meter, template + translation selects, 6 include toggles in 2 columns, Generate button, footnote).
- Wire every control to the correct command with correct args; render real state from `providers_view()`; refresh the view after each mutation.
- Honest states: Available/Cloud connected pills only when `cloud_connected`; `quota==null` → honest placeholder (never "12/40"); `cloud_status=="not_configured"` → honest "coming soon"; `generate_sermon_notes` errors surfaced (consent_required → prompt opt-in; not_configured → coming soon; quota/transport/malformed → message).
- Extend `scripts/operator_headless.py`: stub the 9 commands, add driver checks (render, per-control invoke+args, consent-gated Generate, honest not-configured/quota, no fabricated numbers, computed-display + layout robustness), bump `EXPECTED_MIN_CHECKS`.

### Non-goals

- The 8 other Settings pages / the 9-item settings sidebar (separate story 86ajxucue — design only; not in frontend scope). This task builds the one designed+backed page reached via the app nav's Settings item.
- The "Advanced · Bring your own key / custom provider" row and the "Text-to-Speech" section — excluded by product (BYOK hosted-only; TTS DEC-001). Not built.
- Any backend change (selahcue-core/-data/-cloud or the operator commands); the LAN wire protocol / pinned cross-language fixtures.

### Constraints

- Honesty is the point of this screen: render only real backend state; never fabricate quota/status/pills.
- Reuse existing token classes/primitives; match Figma faithfully (copy, colour, spacing, radii, 42×24 toggles).
- Avoid the WKWebView traps: assert computed `display` (not just the `hidden` attribute); no flex `<select>` collapse; no grid implicit-row overflow.
- Bounded memory: no unbounded caches/logs in the module.
- CI has a `cargo fmt --check` gate; do not touch backend Rust; CRLF-safe.

### Assumptions and unknowns

- ASSUMED: selecting the Cloud transcription radio is the opt-in gesture → it calls `set_cloud_consent{kind:"transcription",enabled:true}` then `set_transcription_mode{mode:"cloud"}`; selecting On-device calls `set_transcription_mode{mode:"on_device"}` and revokes transcription consent. Owner: frontend-engineer (defensible; each click issues clear, testable commands). Recorded as a design reconciliation.
- ASSUMED: the green "consent" banner needs an actionable consent control for cloud notes → a toggle mapping to `set_cloud_consent{kind:"notes"}`; Generate remains consent-gated. Owner: frontend-engineer.
- ASSUMED: the model-detail line and readiness are driven from `on_device.{model,detail,state}` (not the frame's literal "small.en · 380 MB").

## Dependencies and approvals

- Backend task 86ajy034h (commands) — status: code review; DONE enough (commands shipped + tested). Dependency satisfied.
- Live SelahCue hosted cloud service — DOES NOT EXIST (tracked); the panel shows honest not-configured/null-quota affordances.
- Independent review (code-reviewer subagent) of the consent/honesty wiring — required (not self-certified).
- ClickUp MCP — connected (task 86ajy05r9).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The `#surface-settings` panel renders all three sections (offline banner, LIVE TRANSCRIPTION, SELAHCUE AI · SERMON NOTES) from a real `providers_view()` call on activation, with the frame's copy; the stub line is gone | `python3 scripts/operator_headless.py` (settings driver block) | Checks assert the offline banner, both transcription cards, and the AI card exist with correct copy after `settingsActivate`; providers_view was invoked | operator_headless.py settings checks + output | PASS |
| C-002 | yes | Transcription radio cards reflect `transcription_mode` and invoke the right commands: On-device → `set_transcription_mode{mode:"on_device"}`; Cloud → `set_cloud_consent{kind:"transcription",enabled:true}` + `set_transcription_mode{mode:"cloud"}`; PRIVATE/OPT-IN badges + amber live-audio warning present; model detail from `on_device` | headless driver checks | Correct commands+args recorded in `__calls`; badges + warning asserted; model line reads from backend `on_device` | headless output | PASS |
| C-003 | yes | Template + translation selects list backend options, show the selected value, and invoke `set_notes_template{template}` / `set_preferred_translation{code}` with the chosen value | headless driver checks | Selecting an option records the correct command+arg; selects are real focusable `<select>`s that do not collapse (computed width > 0) | headless output | PASS |
| C-004 | yes | The 6 INCLUDE-IN-NOTES toggles render in 2 columns, reflect `include.*`, and each invokes `set_include_flag{name,enabled}` with the correct snake_case name | headless driver checks | Each of the 6 names fires with the toggled enabled value; 2-column layout asserted | headless output | PASS |
| C-005 | yes | Consent + Generate flow: the cloud-notes consent control invokes `set_cloud_consent{kind:"notes"}`; Generate invokes `generate_sermon_notes`; `consent_required` prompts opt-in; `not_configured` shows an honest "coming soon"; a success payload renders the draft | headless driver checks | consent toggle command asserted; generate path asserted for consent_required, not_configured, and ok payloads; role=alert/status surfaced | headless output | PASS |
| C-006 | yes | Honest states only: Available/Cloud-connected pills render ONLY when `cloud_connected`; `quota==null` renders an honest placeholder (NOT a fabricated "12/40"); `cloud_status=="not_configured"` surfaced | headless driver checks | With the default (not_configured, null quota) fixture: no "12 / 40" text, no green/blue connected pills; a "coming soon"/"not configured" affordance present. With a cloud_connected+quota fixture the pills+meter render | headless output | PASS |
| C-007 | yes | Excluded sections are absent: no "Bring your own key"/BYOK/Advanced row and no Text-to-Speech section in the rendered panel | headless driver checks + `rg` on index.html | No BYOK/TTS text nodes rendered under `#surface-settings` | headless output + grep | PASS |
| C-008 | yes | WKWebView robustness: panel visibility uses computed display (asserted, not just `.hidden`); no flex `<select>` collapse; content does not overflow past the surface | headless driver checks | Computed display of the active panel asserted; select computed width > 0; no horizontal overflow of the settings body | headless output | PASS |
| C-009 | yes | The headless gate passes with the raised floor | `python3 scripts/operator_headless.py` | Exits 0; `=== N checks, 0 FAIL ===` with N ≥ the bumped `EXPECTED_MIN_CHECKS` (> 425) | headless output captured to scratchpad | PASS |
| C-010 | yes | The operator crate still compiles (no Rust touched, but dist is embedded) | `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` | Exits 0 | cargo output | PASS |
| C-011 | yes | Full local CI gate is green | `make ci` | Exits 0; "ALL GREEN" | make ci log in scratchpad | PASS |
| C-012 | yes | Independent review (code-reviewer subagent) confirms honesty wiring (no fabricated state, consent correctly gated, correct command args) with no unresolved critical/high finding | code-reviewer subagent review of the diff | No unresolved critical/high (or fixed + re-verified) | review report in handoff / ClickUp | PASS |
| C-013 | yes | ClickUp task 86ajy05r9 carries goal ID, engine, iteration limit, start + final evidence, terminal state; linked to 86ajy034h + 86ajxucue | Inspect task 86ajy05r9 | Start + final comments present with links; dependency/link set | ClickUp task 86ajy05r9 | PASS |
| C-014 | no | Goal Contract structural validator passes | `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-fe-providers-privacy.md` | Exits 0 | validator output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the settings driver block in `scripts/operator_headless.py` — inspect the actual asserted behaviours (commands+args, honest states, layout), not just the exit code.
- Broader regression verification: `make ci` (C-011) full gate; operator `cargo check` (C-010); the whole headless suite must not shrink (C-009 floor).
- Independent verifier: code-reviewer subagent reviews the honesty/consent wiring (C-012); the implementing role does not self-certify it.
- Required environment: desktop Rust workspace + operator toolchain + headless Chrome + Flutter (for `make ci`); Figma/ClickUp MCP for evidence.

## Iteration ledger

### Iteration 1

- Target criterion: setup (C-013, C-014)
- Hypothesis: a validated contract + a registered/linked ClickUp task are prerequisites to any implementation iteration.
- Change or investigation: full FE/design/backend investigation; pulled Figma 338:124; authored this contract; created ClickUp task 86ajy05r9 linked to 86ajy034h + 86ajxucue.
- Verifier executed: python3 scripts/validate_goal_contract.py → PASS (14 criteria, 13 mandatory); ClickUp start comment posted.
- Result: PASS (C-014); C-013 start-half done.
- New evidence: scratchpad/pp-frame.png; contract file; ClickUp task 86ajy05r9 start comment.
- Decision: iterate

### Iteration 2 — build the panel (C-001..C-008)

- Target criteria: C-001..C-008
- Hypothesis: a `settings.js` IIFE mirroring `preservice.js`/`remote.js`, rendering `#pp-trans` + `#pp-ai` from a real `providers_view()` with honest null-quota / not-configured affordances, wires every control 1:1 to its command.
- Change: `index.html` `#surface-settings` body (header + offline banner + two dynamic regions); new `settings.js` (renders both regions, wires all 9 commands, consent-gated Generate with consent_required/not_configured/ok handling, honest quota/pill states, APG radiogroup, 42×24 switches); `pp-*` classes in `app.css` reusing `--sc-*` tokens (grid layouts + width:100% selects to dodge WKWebView flex-collapse); `showSurface("settings")→settingsActivate` hook in `app.js`.
- Verifier executed: (deferred to C-009 headless run in iteration 3).
- Result: implemented; pending headless proof.
- Decision: iterate

### Iteration 3 — headless proof + full gate (C-009..C-011)

- Target criteria: C-009, C-010, C-011 (and behavioural proof of C-001..C-008)
- Hypothesis: extending `operator_headless.py` with a `P` ProvidersView fixture + the 9 command stubs + a 47-check settings driver block proves render + per-control invoke + consent gating + honest states behaviourally; the operator crate still compiles and `make ci` stays green.
- Change: added the `P` fixture (default = on-device/cloud-off/not_configured/null-quota, mirrors the real backend), `window.__pp` exposure, the 9 command handlers, and the settings driver block; bumped `EXPECTED_MIN_CHECKS` 425 → 474.
- Verifier executed: `python3 scripts/operator_headless.py` → **474 checks, 0 FAIL, exit 0** (47 new PP checks all PASS, incl. computed-display, no-fabricated-12/40, consent-gated Generate, cloud_connected pills only when connected); `cargo check` operator + `make ci` (running).
- Result: C-009 PASS; C-001..C-008 PASS (behavioural); C-010/C-011 pending the running gate.
- New evidence: scratchpad/headless.log; scratchpad/make_ci.log.
- Decision: iterate (await gate) then independent review (C-012)

### Iteration 4 — full gate green + independent review + fixes (C-010, C-011, C-012, C-013)

- Target criteria: C-010, C-011, C-012, C-013
- Note: this iteration was completed by the coordinating backend-engineer after the FE worker agent hit a stream-watchdog stall; its work was intact and verified/finished from here.
- Change/verification: `make ci` → "local CI gate: ALL GREEN", exit 0 (covers operator `cargo check` C-010 + full gate C-011). Independent code review (fresh subagent, not the implementer) of the FE diff — verdict: no Blocker/High, honesty invariant holds. Fixed its findings: **M1** (selecting Cloud no longer forces the cloud posture if the consent grant is rejected — resyncs instead), **M2** (added a `__ppRejectOnce` hook + a driver test proving a rejected mutation reverts the optimistic switch to the backend value — no silent lie), **L1** (clear stale ARIA role so a success after an error is role=status not a lingering alert), **L2** (guard quota sub-fields against "undefined"), **L3** (assert all 6 include-flag args + every generate error branch: quota_exceeded/transport/malformed/degraded). L4 (3 hardcoded colour literals) + L5 (Home/End keys) accepted as cosmetic/a11y polish (operator UI does not theme-switch).
- Verifier executed: `python3 scripts/operator_headless.py` → **486 checks, 0 FAIL**; `make ci` → ALL GREEN, exit 0; `python3 scripts/validate_goal_contract.py … --require-complete`.
- Result: PASS — C-010, C-011, C-012, C-013 all PASS.
- New evidence: scratchpad/make_ci_fe2.log; review report in the ClickUp handoff on 86ajy05r9.
- Decision: complete

## Risks and rollback

- Risks: (1) dishonest state leaking through (fabricated quota/pills) — mitigated by making C-006 a first-class test and an independent review C-012. (2) WKWebView-only layout breakage invisible in Blink — mitigated by robust layout + computed-display asserts (C-008) and the known-trap memories. (3) suite silently shrinking — mitigated by the `EXPECTED_MIN_CHECKS` floor. (4) accidental backend/wire change — mitigated by touching only dist + the headless script.
- Rollback or recovery: all changes are additive to the operator webview (dist HTML/CSS/JS + the headless script). Revert is a clean removal of the `#surface-settings` body, `settings.js`, the `pp-*` CSS, and the settings driver block; no backend/wire/migration touched.

## Pause and escalation conditions

- BLOCKED to product if any control would contradict a recorded decision (TTS/DEC-001, BYOK) — flag, do not build.
- BLOCKED to backend if a required behaviour needs a command/shape the backend does not expose.
- Stop after three materially different failed attempts on a criterion without new evidence; report the smallest unblocker.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-fe-providers-privacy.md --require-complete
- Validator result: PASS (all 13 mandatory criteria PASS)
- Independent verification result: fresh independent code review (not the implementer) — no Blocker/High; honesty invariant confirmed (no fabricated quota/pills; `mutate` resyncs on rejection). 2 MEDIUM + minors fixed and re-verified.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to task 86ajy05r9; task moved to code review.
- ClickUp final evidence comment: pending
