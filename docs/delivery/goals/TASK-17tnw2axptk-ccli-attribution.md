# Goal Contract — TASK-17tnw2axptk-ccli-attribution

## Identity

- Goal ID: TASK-17tnw2axptk-ccli-attribution
- Parent goal ID: NONE
- Title: Audience output can render CCLI/attribution for a song slide
- Role: frontend-engineer (Farah) — Rust compositor (audience-output rendering), not web frontend
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2axptk
- Created: 2026-09-21
- Updated: 2026-09-21
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`selahcue-present` can compose a themed CCLI/attribution line (the CCLI number and the song
author, formatted "CCLI #NNNNNNN · Author Name") into the audience output frame when a slide
carries song licensing metadata and its theme defines a footer region — closing OUT-006/OUT-015
from `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md`.

## Baseline

**Verified** (2026-09-21, this worktree at `origin/main` `5911c91`):
- `implementation/desktop/crates/selahcue-present/src/theme.rs` `Theme` has `background`,
  `title`, `body`, `band`, `font`, `weight`, `letter_spacing_permille`, `elements` — no
  footer/attribution region.
- `implementation/desktop/crates/selahcue-present/src/slide.rs` `Slide` is exactly
  `{ title: String, body: Vec<String> }` — no song metadata field.
- `grep -rniE "ccli|licens" implementation/desktop/crates/selahcue-present` matches nothing
  (the only `ccli`/`licens` hits repo-wide are `selahcue-licensing` — software entitlement
  licensing, an unrelated domain — and docs).
- `docs/product/prds/SelahCue-PRD.md:132` FR-021 (MVP): "Copyright-metadata fields (title,
  author, ©year, publisher, CCLI#) + optional on-slide footer ... Fields captured per song;
  footer toggle renders attribution on output."
- No `PlanItem`/import path currently populates song author/CCLI/publisher/year anywhere in
  the Rust workspace — **this is a model-missing gap, not an unwired one.**

## Inputs and evidence sources

- `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` — OUT-006, OUT-015, headline summary,
  "Suggested build order" § Rust Step 2.
- `docs/product/prds/SelahCue-PRD.md` FR-021.
- `implementation/desktop/crates/selahcue-present/src/theme.rs` (RegionStyle/Band/Element
  additive pattern to follow), `compose.rs`, `slide.rs`, `measure.rs`.
- Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, frame `208:130` ("Song — Center").

## Scope

### In scope

- `Theme.footer: Option<RegionStyle>` — additive, `skip_serializing_if`, same pattern as `band`.
- `Slide.song: Option<SongAttribution>` — additive, `skip_serializing_if`; `SongAttribution`
  carries `author`, `ccli_number`, `copyright_year`, `publisher` (FR-021's field set minus
  `title`, which `Slide.title` already carries), each bounded (no-leak).
- A formatted footer line (`"CCLI #<number> · <author>"`, degrading gracefully when a field
  is absent) and its render path in `compose.rs`, reusing the existing `layout_region`/
  `autofit_layers` path (no new text-shaping attribute, so `measure.rs`'s `Key`/`Hash` are
  untouched).
- Unit + composition tests: serde round-trip, additive byte-stability (built-in themes/slide
  JSON unchanged when the new fields are unset), footer renders when present, does not render
  when absent (theme has no footer, or slide has no/blank song metadata), bounds enforcement.
- Reconciliation update to `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` for
  OUT-006/OUT-015.

### Non-goals

- OUT-009 (per-content-role templates: Scripture — Full / Song — Center) — explicitly
  scoped-later (Step 3) by the audit; built-in themes keep `footer: None` so their JSON and
  the `builtin_themes_are_distinct_designs_and_names_round_trip` test stay unchanged.
- Wiring `PlanItem`/song import/operator UI to populate `SongAttribution` end-to-end — out of
  scope for this Rust-compositor ticket; the content-side field exists and composes correctly
  given a populated `Slide`, which is what OUT-006/OUT-015 ask for.
- GPU compositor / ADR-0015 parity oracle changes: footer renders via `Layer::Text`, the same
  category `title`/`body` already use, which the GPU compositor already documents skipping
  (OUT-012). No new `Layer` variant, so `selahcue-gpu` is untouched.
- Any Part A (web operator UI) change — a different half of this audit, not this ticket.

### Constraints

- Additive-only: existing `Theme`/`Slide` JSON must round-trip byte-identical when the new
  fields are unset (repo convention, explicit in the ticket).
- No new attribute may leak into `measure.rs`'s shaping memo key unless it changes shaped
  width (OUT-013 trap) — verified not to apply here (footer text uses the same
  font/weight/size inputs already in the key).
- Bounded memory: new string fields get explicit char-length caps + a `within_bounds`-style
  predicate, per repo convention (`Element::within_bounds`, `MediaAsset::within_bounds`).

### Assumptions and unknowns

- **ASSUMED**: the footer render format is `"CCLI #<number> · <author>"` (matching the Figma
  mock's literal string), degrading to whichever of the two is present, and rendering nothing
  when both are absent/blank. `copyright_year`/`publisher` are captured (FR-021 compliance)
  but not part of the Figma-drawn footer string — a future format change is a follow-up, not
  blocked by this ticket. Owner: Farah, low risk (additive, doesn't foreclose a richer format).
- **ASSUMED**: footer rendering is gated by the existing `LayerMask.text` flag (same as
  title/body), not a new mask category — no Part A (operator UI) change ships in this ticket,
  so a new mask flag would be unreachable from the UI anyway.

## Dependencies and approvals

- None blocking. Independent review (Cody/Vera/Sana/Quinn) required before `VERIFIED_COMPLETE`
  per the team operating contract.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `Theme` gains an optional `footer` field (an optional RegionStyle), additive | `cargo test -p selahcue-present` (serde round-trip + byte-stability tests) | compiles; built-in theme JSON unchanged (no `footer` key) when unset | `no_builtin_theme_or_plain_slide_emits_a_footer_or_song_key`, `theme_footer_and_slide_song_serde_round_trip` — both PASS | PASS |
| C-002 | yes | `Slide` gains an optional `song` field (an optional SongAttribution), additive, bounded | `cargo test -p selahcue-present` | compiles; existing `Slide` JSON unchanged when unset; over-bound input rejected by `within_bounds` | `song_attribution_within_bounds_rejects_an_over_length_field_and_accepts_a_boundary_one` — PASS | PASS |
| C-003 | yes | A themed footer renders the CCLI number and author line when both theme.footer and slide.song are set | `cargo test -p selahcue-present --test test_compose` | new test asserts ink present in the footer region | `footer_renders_when_theme_has_a_footer_region_and_slide_has_song_metadata` — PASS | PASS |
| C-004 | yes | No footer renders when `theme.footer` is `None` or `slide.song` is `None`/blank | same test file | new test asserts no ink in the (unconfigured) footer area / no layer emitted | `footer_does_not_render_when_the_theme_has_no_footer_region`, `footer_does_not_render_when_the_slide_has_no_song_metadata`, `footer_does_not_render_for_blank_song_attribution`, `builtin_themes_still_render_byte_identically_with_no_footer` — all PASS | PASS |
| C-005 | yes | `measure.rs` Key/Hash unchanged (OUT-013 trap avoided) | `git diff` review | `measure.rs` not modified, or diff shows no new shaping attribute | `git show --stat HEAD` — `measure.rs` absent from the changed-files list | PASS |
| C-006 | yes | Full local gate green | `make ci` (single run, worktree-scoped `CARGO_TARGET_DIR`) | exits 0 | Full run, single invocation, no concurrent session detected beforehand (`ps aux` clean). Final line: `== local Rust/Flutter gate: ALL GREEN ==`, `[exited with code 0]` | PASS |
| C-007 | yes | Reconciliation entry added for OUT-006/OUT-015 | manual diff review | `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` Reconciliation section updated | "Update — 2026-09-21" subsection added under "Reconciliation — 2026-09-20", including the Figma-drift finding (see Risks) | PASS |
| C-008 | yes | PR opened against `main`, draft until CI green | `gh pr view` | PR exists, later marked ready | https://github.com/First-Pavilion/selahcue/pull/59 — opened Draft, all remote GitHub Actions checks passed (`rust`/`operator shell`/`operator shell — release & native-toolchain features` × macos/ubuntu/windows, `launch-smoke` × macos/ubuntu, `dependency audit`, `supply chain`, `workflows`; `api`/`marketing`/`flutter controller` correctly path-filter-skipped, nothing touched), marked ready for review | PASS |
| C-009 | yes | Independent review (Cody/Vera/Sana/Quinn) blocking findings resolved | review pipeline | all four review steps finished | All four PASS, no blocking findings, independently confirmed via `gh api repos/First-Pavilion/selahcue/issues/59/comments` (not just the relayed summaries): Cody https://github.com/First-Pavilion/selahcue/pull/59#issuecomment-5760827047, Vera https://github.com/First-Pavilion/selahcue/pull/59#issuecomment-5760848895, Sana https://github.com/First-Pavilion/selahcue/pull/59#issuecomment-5760854234, Quinn https://github.com/First-Pavilion/selahcue/pull/59#issuecomment-5760816352. Two non-blocking follow-ups filed and linked: 17tnw2axr3y (visible=false coverage), 17tnw2axr55 (pre-existing RenameItem length cap). Consolidated report: https://claude.ai/artifact/DnzJr7vUUG6WyYjzvV2yq4. Also verified: a later CI run hit a transient, unrelated `selahcue-data` Windows flake (not this diff); targeted re-run passed clean, all checks green with nothing pending as of this evaluation | PASS |

## Verification plan

- Focused verification: `cargo test -p selahcue-present` while iterating.
- Broader regression verification: `make ci` once, from this worktree, with
  `CARGO_TARGET_DIR` confirmed local (not shared), and after checking for a concurrent
  `make ci`/Flutter run in other sessions.
- Independent verifier: Cody (code), Vera (performance — expected N/A/light for this change),
  Sana (security — bounds/no-leak), Quinn (QA).
- Required environment: macOS, this worktree, no GPU dependency (footer path doesn't touch
  `selahcue-gpu`).

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-005 (model + compose + tests)
- Hypothesis: adding `Theme.footer`/`Slide.song` additively and rendering via the existing
  `layout_region` path closes OUT-006/OUT-015 without touching `measure.rs` or `selahcue-gpu`.
- Change or investigation: implemented `Theme.footer`, `SongAttribution`, `Slide.song`,
  `compose_slide_masked`'s footer render, 17 new tests.
- Verifier executed: `cargo test -p selahcue-present` (all suites), `cargo clippy -p
  selahcue-present --all-targets -- -D warnings`, `cargo fmt -p selahcue-present -- --check`,
  `cargo check --workspace`, `cargo check -p selahcue-app --all-targets`, `cargo check
  --manifest-path .../selahcue-operator/Cargo.toml`.
- Result: all green on first implementation pass — no fix-up iteration needed. 17/17 new tests
  PASS; 0 clippy warnings; fmt clean after one auto-format pass; whole workspace + operator
  compile clean.
- New evidence: independently verified against live Figma (file `SYQn5hFY8YVQKm3c6rw0eJ`) that
  the `208:*` node subtree (the audit's sole citation for `OUT-006`) has been deleted from the
  file since 2026-08-23 — does not change the hypothesis (the fix stayed geometry-agnostic) but
  recorded as a finding; follow-up task spawned (`task_235bab3e`).
- Decision: iterate (C-006/C-007 next)

### Iteration 2

- Target criterion: C-006, C-007 (full gate + reconciliation doc)
- Hypothesis: the change is workspace-safe (no downstream crate breaks) and the full local gate
  passes without needing further code changes.
- Change or investigation: ran `make ci` (checked `ps aux` for a concurrent run first — none
  found; `CARGO_TARGET_DIR` confirmed unset/local). Wrote the Reconciliation "Update —
  2026-09-21" entry in `docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md`.
- Verifier executed: `make ci` (single run, ~9 minutes, Rust workspace + feature-gated crates +
  operator + Flutter + toolchain/launch-reachability checks).
- Result: `== local Rust/Flutter gate: ALL GREEN ==`, exit code 0. No fix-up needed.
- New evidence: none beyond the green run itself.
- Decision: handoff (C-008/C-009 — PR + independent review — are the remaining, role-boundary
  steps: opening/pushing a PR and requesting Cody/Vera/Sana/Quinn review)

## Risks and rollback

- Risks: a hidden pinned-JSON fixture elsewhere in the workspace could break on the new
  optional fields — mitigated by grepping for Theme/Slide JSON fixtures before implementing
  (done: none found beyond in-crate round-trip tests, which construct `Theme`/`Slide` values
  in Rust rather than comparing to a literal JSON string).
- Rollback: revert the branch; no persisted data migration involved (additive fields only).

## Pause and escalation conditions

- If `make ci` cannot run because a concurrent run is active in another session, wait/serialize
  rather than diagnosing a false red.
- If the CARGO_TARGET_DIR is found pointed at a shared location, override it locally before
  running any cargo command.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2axptk-ccli-attribution.md --completion`
- Validator result: OK (completion) — 9/9 mandatory criteria PASS.
- Independent verification result: 9/9 mandatory criteria PASS. C-009 (Cody/Vera/Sana/Quinn)
  independently confirmed genuine and passing by querying the GitHub API directly rather than
  trusting relayed summaries — see C-009's evidence for the four comment URLs. Along the way, a
  relayed claim that a reviewer had left an uncommitted mutation in this worktree was checked and
  found false (`git status`/`git diff HEAD` showed the worktree already clean); the actual source
  was Cody's own temporary, self-reverted mutation test in his review process, not a leftover
  here. Also found and resolved for real: a later CI run's `rust (windows-latest)` failure, a
  transient WAL-checkpoint timing flake in `selahcue-data` (untouched by this diff) — confirmed
  transient by re-running the job, which passed clean.
- Terminal state: **VERIFIED_COMPLETE** — every mandatory criterion PASS, evidence recorded,
  independent review passed with no blocking findings, validator green (both structural and
  `--completion` modes). PR #59 is fully green (local `make ci` + remote GitHub Actions, all
  jobs) and left open, marked ready for review, for the repo owner to merge — this role does not
  merge its own PR.
- Remaining failed or blocked criteria: (recorded at completion)
- ClickUp final evidence comment: (recorded at completion)
