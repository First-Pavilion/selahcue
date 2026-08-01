# Goal Contract — TASK-design2-palette-tokens

## Identity

- Goal ID: TASK-design2-palette-tokens
- Parent goal ID: NONE (relates to the Design 2.0 redesign; see docs/design/DESIGN-2.0-HANDOFF.md)
- Title: Implement the SelahCue "Design 2.0" palette as design tokens (CSS variables + Rust/Dart constants), WCAG-audited and cross-surface pinned
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: PENDING (ClickUp MCP not exercised this run — queued update in handoff)
- Created: 2026-08-03
- Updated: 2026-08-03
- Maximum iterations: 8
- Independent verification required: yes (automated WCAG-AA audit + no-regression suite)

## Objective

Make the Design 2.0 palette (Figma node 310:124) available in the codebase as first-class design
tokens — CSS custom properties in the operator webview, canonical Rust constants, and Flutter
constants — cross-surface pinned and WCAG-AA audited, without regressing the existing canonical tokens.

## Baseline

- Canonical tokens live in `selahcue-present/src/tokens.rs` (PREVIEW/LIVE/WARN/NEUTRAL as `fill`+`ink`),
  mirrored in `dist/app.css` `:root` and `mobile/.../design_tokens.dart`, pinned by
  `selahcue-present/tests/test_tokens.rs` (content-pin + WCAG-AA audit).
- The existing status tokens are **white-on-deep-fill** (`#0f7b6c/#a3283a/#9a5b00`). Design 2.0 uses
  **bright ink on soft-tint** (a different pattern) — confirmed in DESIGN-2.0-HANDOFF.md §3. A hex swap
  would break the pin + the white-on-fill WCAG audit, so Design 2.0 is added as a new token layer.

## Inputs and evidence sources

- Figma palette board node `310:124` (file SYQn5hFY8YVQKm3c6rw0eJ)
- docs/design/DESIGN-2.0-HANDOFF.md §3 (token table + migration mapping + WCAG caveat)
- selahcue-present/src/tokens.rs, tests/test_tokens.rs; dist/app.css; design_tokens.dart

## Scope

### In scope

- Add the full Design 2.0 palette (neutrals, brand, gold, status inks + soft + border, text scale, info)
  as: canonical Rust constants (`tokens::design2`), CSS custom properties (`--sc-*` in dist/app.css),
  and Flutter constants (`DesignTokens.d2*`).
- A cross-surface pinning test + a WCAG-AA audit test for the Design 2.0 pairings.
- Document in docs/design/DESIGN-TOKENS.md.

### Non-goals

- Re-skinning components to *use* the new tokens (separate migration; components still use legacy vars).
- Removing or changing the existing canonical status tokens.
- Any wire/protocol/behaviour change.

### Constraints

- Must not regress existing tests (`cargo test -p selahcue-present`), fmt, or clippy (CI gates).
- Additive only; existing `--bg/--preview/...` and PREVIEW/LIVE/WARN stay intact.

### Assumptions and unknowns

- ASSUMED: the Design 2.0 hexes on node 310:124 equal those recorded in DESIGN-2.0-HANDOFF.md §3.1
  (authored + screenshot-verified this session). Validation owner: frontend-engineer (this task).
- KNOWN a11y caveat: `text-muted #6B7383` on base is ~3.98:1 (< AA-text 4.5, > AA-large 3.0) — audited
  at 3.0 and documented as tertiary/label-only, flagged to the owner.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Design 2.0 palette exists as canonical Rust constants | `cargo test -p selahcue-present design2` | compiles + palette test passes | tokens.rs (`mod design2`) | PASS |
| C-002 | yes | Palette present as CSS custom properties in dist/app.css | grep `--sc-base`,`--sc-primary`,`--sc-live-soft` | all present | app.css :root | PASS |
| C-003 | yes | Palette mirrored in Flutter design_tokens.dart | grep `d2Base`,`d2Primary` | present | design_tokens.dart | PASS |
| C-004 | yes | Cross-surface pin: CSS + Dart carry every Rust hex | `cargo test … design2_palette_is_pinned_across_surfaces` | PASS | `design2_palette_is_pinned_across_surfaces ... ok` | PASS |
| C-005 | yes | WCAG-AA audit of Design 2.0 text + status pairings | `cargo test … design2_palette_meets_wcag_aa` | PASS | `design2_palette_meets_wcag_aa ... ok` | PASS |
| C-006 | yes | No NEW regression from this change | compare vs HEAD | 0 new failures; my 2 tests pass | see note ↓ | PASS |
| C-007 | yes | fmt + clippy clean | `cargo fmt -p selahcue-present -- --check` + `cargo clippy -p selahcue-present --tests` | clean | `FMT CLEAN`; clippy `Finished` no warnings | PASS |
| C-008 | yes | Palette documented | review docs/design/DESIGN-TOKENS.md | Design 2.0 section present | "Design 2.0 palette" section | PASS |

**C-006 note (honest):** my change is additive (tokens.rs + `--sc-*` CSS + Dart + 2 new tests) and
introduces **no** new failures — both new tests pass, fmt+clippy clean. However the full
`selahcue-present` suite is **not** green: **3 operator-webview *content pins* fail on
`transcript-form` (×1) and `set_item_theme` (×2)** — needles that live in `index.html`/`app.js`,
which I did NOT edit. These stem from **uncommitted, in-progress operator changes in the working
tree** (a transcript-UI refactor: HEAD's `transcript-form` → working-tree `transcript-status`/
`transcript-rec`, +6/+3 lines; plus the earlier per-item-theme dropdown removal). Verified pre-
existing/unrelated: `git show HEAD:…/app.js | grep set_item_theme` = 0; the failing needles are
none of the palette tokens. **Owner action:** update those two operator-pin tests to match the
transcript/theme refactor before commit/CI — a separate task (not the palette).

## Verification plan

- Focused: the two new tests (pin + WCAG audit) + grep of each surface.
- Broader regression: `cargo test -p selahcue-present` (existing pin/audit stay green).
- Independent verifier: the automated WCAG-AA audit test (deterministic contrast math) is the objective
  independent check; a11y caveat on text-muted is surfaced to the owner.
- Required environment: desktop Rust workspace (`implementation/desktop`).

## Risks and rollback

- Risks: hex drift between surfaces (mitigated by the pin test); a11y caveat on text-muted (documented).
- Rollback: additive only — revert the added consts/vars/tests to restore baseline.

## Pause and escalation conditions

- If the WCAG audit fails for an essential pairing → surface to owner (design decision), do not weaken the threshold silently.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-008 (single coherent additive increment)
- Hypothesis: adding the Design 2.0 palette as canonical Rust consts + CSS `--sc-*` + Dart `d2*`, cross-pinned + WCAG-audited, satisfies all criteria without regressing the existing pinned tokens.
- Change or investigation: implement palette across the three surfaces + two new tests + docs.
- Verifier executed: `cargo test -p selahcue-present …`, `cargo fmt -p selahcue-present -- --check`, `cargo clippy -p selahcue-present --tests`.
- Result: palette implemented across 3 surfaces; `design2_palette_is_pinned_across_surfaces` + `design2_palette_meets_wcag_aa` PASS; fmt CLEAN; clippy no warnings. 3 unrelated operator content-pin failures (transcript-form/set_item_theme) surfaced from the working tree's in-progress operator refactor.
- New evidence: test output (both palette tests ok); `git show HEAD` diffs proving the 3 failures are unrelated + pre-existing.
- Decision: complete (palette) + flag (unrelated operator pins → owner follow-up).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-palette-tokens.md`
- Validator result: PASS (structure)
- Independent verification result: automated WCAG-AA audit (`design2_palette_meets_wcag_aa`) PASS — deterministic contrast math is the objective independent check; text-muted a11y caveat documented.
- Terminal state: **VERIFIED_COMPLETE** for the palette (C-001…C-005, C-007, C-008 PASS; C-006 = no new regression). Overall `selahcue-present` suite is NOT green due to 3 unrelated, pre-existing operator-webview content-pin failures (transcript/theme refactor in the working tree) — flagged for the owner; must be fixed before commit/CI.
- Remaining failed or blocked criteria: none in scope. Out-of-scope blocker: 3 operator-pin tests (transcript-form ×1, set_item_theme ×2) — separate follow-up.
- ClickUp final evidence comment: PENDING (ClickUp not exercised this run) — queued: (1) this task's evidence; (2) follow-up "update operator webview pins for the transcript/theme refactor (transcript-form → transcript-status/rec; drop set_item_theme)".
