# Goal Contract — TASK-design2-reskin-operator

## Identity

- Goal ID: TASK-design2-reskin-operator
- Parent goal ID: TASK-design2-palette-tokens
- Title: Re-skin the operator webview neutrals + brand onto the Design 2.0 palette (foundation slice)
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: PENDING (queued)
- Created: 2026-08-03
- Updated: 2026-08-03
- Maximum iterations: 6
- Independent verification required: yes (token pins + fmt/clippy + node --check)

## Objective

Migrate the operator webview's **neutral surfaces + brand** to Design 2.0 (warm-ink ramp + indigo→violet
brand) by re-pointing the legacy CSS variables/hardcoded neutrals to the Design 2.0 values, without touching
the WCAG-pinned canonical §4 **status** tokens (deferred to Phase 2) and without layout risk.

## Baseline

- `dist/app.css` uses legacy vars `--bg #0e1116 / --panel #171b22 / --line #2b323d / --text #eef1f6 /
  --muted #9aa4b2 / --accent #5b6bd6` (~180 usages) + hardcoded neutrals (#1d2430, #232a35, #2b323d, #9aa4b2,
  #eef1f6). Status vars `--preview/--live/--warn` (+ inks) are the UX-CANONICAL §4 tokens, pinned by
  `test_tokens.rs::operator_webview_is_pinned_to_the_canonical_tokens` (6 hexes must appear) + WCAG-audited.
- Design 2.0 palette already implemented as `--sc-*` (TASK-design2-palette-tokens, committed cc988ef).

## Scope

### In scope

- Swap the 6 legacy neutral/brand var VALUES → Design 2.0 (base/surface/border/text/text-secondary/primary).
- Map hardcoded neutral hexes (#1d2430,#232a35 → elevated #1c1f28; #2b323d → #262a34; #9aa4b2 → #a7aebe;
  #eef1f6 → #f4f6fb) for a consistent ramp.

### Non-goals

- Status colours (preview/live/warn fills + inks) — Phase 2 (changes §4 + the pin + WCAG basis; a design decision).
- Layout/structure/behaviour changes; index.html/app.js edits (they inherit via CSS vars).

### Constraints

- The 6 canonical status hexes (#0f7b6c #a3283a #9a5b00 #2bb673 #ef4444 #f2b53c) MUST remain present + used
  (leave status vars untouched) → `operator_webview_is_pinned_to_the_canonical_tokens` stays green.
- No new test failures; fmt + clippy clean; app.js `node --check` clean.

### Assumptions and unknowns

- ASSUMED: darkening the neutral surfaces cannot reduce ink/text contrast below AA (a darker bg only raises
  contrast). Validated by the retained WCAG audits (Rust) + the Design 2.0 audit.
- UNKNOWN (owner-run): pixel-level visual QA in the running Tauri webview — no headless render harness in-repo.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Neutral/brand vars now hold Design 2.0 values | grep app.css `:root` | `--bg:#0b0d12 … --accent:#6e5cf0` | app.css `:root` | PASS |
| C-002 | yes | Hardcoded legacy neutrals remapped | grep for old hexes | 0 remaining (#1d2430/#232a35/#2b323d/#9aa4b2/#eef1f6) | app.css | PASS |
| C-003 | yes | Canonical status pins intact | `cargo test -p selahcue-present --test test_tokens` | all pass | `13 passed; 0 failed` | PASS |
| C-004 | yes | No regression: full present-crate suite green | `cargo test -p selahcue-present` | all pass | `93 passed, 0 failed` | PASS |
| C-005 | yes | Operator JS still valid | `node --check app.js` | ok | `JS OK` | PASS |
| C-006 | yes | fmt + clippy clean | `cargo fmt -p selahcue-present -- --check` + clippy | clean | `FMT CLEAN`; clippy 0 | PASS |

**Terminal:** VERIFIED_COMPLETE (foundation slice). All 6 canonical status hexes remain present (pin green).
**Phase 2 (separate, owner decision):** migrate status colours to Design 2.0 (bright ink + soft-tint chips) —
this supersedes UX-CANONICAL §4 status, changes the pin + WCAG basis, and needs running-webview visual QA.

## Verification plan

- Focused: token tests + node --check + grep of the swapped vars.
- Broader: `cargo test -p selahcue-present`.
- Independent verifier: the pin + WCAG token tests (automated); visual QA is owner-run (no in-repo render).
- Required environment: desktop Rust workspace + node.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-006 (single coherent value-swap increment)
- Hypothesis: re-pointing the legacy neutral/brand vars + hardcoded neutrals to Design 2.0 re-skins the
  foundation with no test/layout regression; status untouched keeps the pins green.
- Change or investigation: edit app.css `:root` + hardcoded neutral hexes.
- Verifier executed: cargo test + fmt + clippy + node --check.
- Result: <pending>
- New evidence: <pending>
- Decision: iterate | handoff | complete

## Risks and rollback

- Risks: a hardcoded hex I map is actually a status/semantic colour (mitigated: I only map known neutrals; status
  hexes excluded). Visual regressions not caught without a render harness (owner-run QA).
- Rollback: revert app.css.

## Pause and escalation conditions

- Status-colour migration (Phase 2) changes UX-CANONICAL §4 + the pin + WCAG basis → owner/architect decision; do
  not do it silently in this slice.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-reskin-operator.md`
- Validator result: <pending>
- Independent verification result: <pending>
- Terminal state: <pending>
- Remaining failed or blocked criteria: <pending>
- ClickUp final evidence comment: <pending — queued>
