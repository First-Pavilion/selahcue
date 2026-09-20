# Goal Contract — TASK-86akgqdwc-podcast-notes-short-description

## Identity

- Goal ID: TASK-86akgqdwc-podcast-notes-short-description
- Parent goal ID: NONE
- Title: Two new generatable sermon-note artifacts — podcast show notes and a short description (FR-126)
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akgqdwc
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 8
- Independent verification required: yes

## Objective

An operator can enable "Podcast show notes" and/or "Short description" in
Providers & Privacy, generate notes, and see both rendered as their own
sections — each independently toggleable, each absent (no message) when its
toggle is off, each reported as requested-but-empty (via the existing
`DraftCaveat::SectionRequestedEmpty`, never a second mechanism) when the
provider returns nothing for it.

## Baseline

Verified against `feat/86akby820-scripture-verification` @ `7bd0fba` (PR #47,
not yet merged to `origin/main`; PR #46/`fix/86akc0tua-requested-but-empty-sections`
also still open) — this ticket branches from PR #47's tip per its own branch-base
instruction, since both Wave-1 PRs are open at start:

- `selahcue-core/src/providers.rs`: `IncludeInNotes` has six toggles
  (`prayer_points`, `scripture_extraction`, `social_excerpts`, `chapter_markers`,
  `notable_quotations`, `short_summary`); no `podcast_show_notes` or
  `short_description` field anywhere (`grep -rniE "podcast|show[ _-]notes"` and
  `grep -rniE "short[ _-]description"` under `implementation/desktop/` both empty).
  `DraftCaveat::SectionRequestedEmpty` and `ScriptureVerdict` already exist (Wave 1).
- `selahcue-cloud/src/openai.rs`: `FLAT_SECTIONS` is the one table that drives the
  schema, the parse loop, and the requested-but-empty caveat together for 5 of the
  6 toggles (`quotes`, `prayer_points`, `chapter_markers`, `social_excerpts`, plus
  two ungated fields); adding a table row is the entire mechanism for a new
  gated flat section, including its caveat — confirmed by reading
  `draft_schema`, `parse_draft`'s flat-section loop, and the ticket's own claim
  that no second caveat mechanism should be built.
- `selahcue-cloud/src/local.rs`: pushes an empty placeholder heading for
  `prayer_points`/`notable_quotations`/`social_excerpts` only (not all six
  toggles) — an existing, pre-ticket inconsistency, not something this ticket
  must fully reconcile.
- `selahcue-cloud/src/contract.rs`: `IncludeDto` mirrors `IncludeInNotes` field-
  for-field (`to_core`/`from_core`); NOT in the ticket's stated file footprint,
  but its struct-literal construction of `IncludeInNotes` means it cannot
  compile once `IncludeInNotes` gains two fields — in scope by necessity.
- `selahcue-data/tests/test_providers_repo.rs`: one `IncludeInNotes { .. }`
  literal (round-trip test) — same compile necessity.
- `selahcue-operator/src/main.rs`: `IncludeView` (6 fields), `providers_view_from`,
  `set_include_flag` (6 match arms) all enumerate the six toggles by name;
  `providers_view_tests::the_frontend_contract_field_names_are_pinned` pins the
  six `include` keys explicitly. `draft_json` and the persisted-draft-reload path
  (`sermon_note_draft_json`) are generic over `d.sections`/`d.caveats` — no
  change needed there.
- `selahcue-operator/dist/settings.js`: `defaultView().include` and the two
  `pp-inc-col` blocks (`renderProviders`, 3 `includeRow` calls each) enumerate
  the six toggles by name.
- `scripts/operator_headless.py`: a mock `providers_view.include` fixture
  (~line 526) and an explicit assertion the include panel renders "6 switches in
  two columns of three" (~line 5858-5882) — will break on toggle count once two
  more toggles exist; in scope by necessity for the headless gate to pass.
- No existing ticket or open PR mentions either artifact.

## Inputs and evidence sources

- ClickUp task 86akgqdwc (description, no comments at start) — authoritative
  scope and acceptance criteria.
- `implementation/desktop/crates/selahcue-core/src/providers.rs` +
  `tests/test_providers.rs`.
- `implementation/desktop/crates/selahcue-cloud/src/{openai,local,contract}.rs` +
  `tests/test_openai.rs`.
- `implementation/desktop/crates/selahcue-data/tests/test_providers_repo.rs`.
- `implementation/desktop/crates/selahcue-operator/src/main.rs` + `dist/settings.js`.
- `scripts/operator_headless.py`.
- 86akc0tua (`DraftCaveat::SectionRequestedEmpty`) and 86akby820 (`ScriptureVerdict`)
  as the established caveat vocabulary to reuse, never duplicate.

## Scope

### In scope

- `IncludeInNotes`: add `podcast_show_notes: bool`, `short_description: bool`,
  both defaulting `false` (matches `social_excerpts`'s off-by-default precedent
  for a secondary/marketing artifact), with persisted keys
  `include.podcast_show_notes` / `include.short_description`, wired through
  `Default`, `to_kv`, `from_kv` exactly like the existing six.
- `openai.rs`: two new `FLAT_SECTIONS` rows — `podcast_show_notes` →
  "Podcast show notes", `short_description` → "Short description" — gated on
  the two new flags. This is the entire mechanism: `draft_schema` asks for the
  field only when enabled, `parse_draft`'s existing loop drops it when off,
  pushes it (possibly empty) when on, and raises
  `DraftCaveat::SectionRequestedEmpty` for it when on-but-empty — identical
  code path to the five existing gated flat sections, zero new branches.
  Prompt guidance added to `instruction()` describing each artifact's expected
  shape (podcast show notes: ready-to-publish copy — a short blurb, key
  discussion points, scripture referenced; short description: one-to-two
  sentences for a listing caption) so the two are recognisably distinct from
  `short_summary`/`social_excerpts` in content, on top of being structurally
  distinct fields/headings by construction.
- `local.rs`: two more empty placeholder headings, matching the existing
  three-of-six precedent.
- `contract.rs`: `IncludeDto` gains the two fields (compile necessity; the v1
  hosted contract is not yet live, so this is a additive, non-breaking change
  to an unshipped wire shape).
- `main.rs`: `IncludeView` gains the two fields; `providers_view_from` and
  `set_include_flag` gain the two wiring points; the pinned frontend-contract
  test's expected `include` key list grows to 8.
- `settings.js`: `defaultView().include` gains the two flags (both `false`);
  two new `includeRow(...)` calls, one added to each column to keep 4/4 (was
  3/3), following the identical `includeRow(name, label, checked)` +
  `mutate("set_include_flag", ...)` pattern.
- `scripts/operator_headless.py`: mock fixture and the column/row-count +
  toggle-wiring assertions updated to 8 toggles in two columns of four, with
  the two new toggles exercised the same way the existing ones are (switch
  reflects backend value, click invokes `set_include_flag{name,enabled}`).
- Fixture-based Rust tests (never live OpenAI): `all_on()`/`full_draft_json()`
  fixtures in `test_openai.rs` extended; the existing table-driven
  requested-but-empty test extended to cover the two new fields; an explicit
  toggle-off test (no section, no caveat) for both; a persistence round-trip
  test extension in `test_providers.rs` and `test_providers_repo.rs`.

### Non-goals

- Editable/exportable artifacts (FR-123/FR-127 — separate tickets).
- Prompt/model tuning for the four pre-existing artifacts (86akbzxyc).
- A model picker or any other unrelated Providers & Privacy surface change.
- Reconciling `local.rs`'s pre-existing three-of-six placeholder inconsistency
  for the OTHER four toggles — only the two new ones are added, matching
  precedent, not fixing what precedent already left inconsistent.
- Persisting the hosted v1 `contract.rs` wire change to any live consumer —
  no hosted client exists yet; this is a mechanical field-parity update only.

### Constraints

- Reuse `DraftCaveat::SectionRequestedEmpty` — do not build a second
  requested-but-empty mechanism (ticket's own explicit instruction).
- `settings.js` change and backend change land in the same commit/MR.
- Fixture-based tests only; never live OpenAI.
- No `dev` branch in this repo; branch from PR #47's tip (not yet merged),
  target `main`; rebase onto `origin/main` (and PR #47/#46 once merged) before
  marking the PR ready.

### Assumptions and unknowns

- **ASSUMED**: Uma (ui-ux-designer) is not looped in for new copy. The ticket
  says to loop her in only if the two new toggles' copy "genuinely needs
  design input beyond the existing toggle-row pattern" — the labels
  ("Podcast show notes", "Short description") are self-describing plain nouns
  in the exact shape of the existing six ("Social excerpts", "Chapter
  markers", ...), rendered through the identical `includeRow` component with
  no new visual treatment. Validation owner: Cody/Quinn review; escalate to
  Uma if either flags the copy as needing design judgement.
- **ASSUMED**: "podcast show notes" and "short description" are each modelled
  as a `NoteSection` (flat list of strings) via `FLAT_SECTIONS`, not a new
  scalar `NoteDraft` field. The ticket explicitly allows "a `NoteSection` (or
  equivalent)" and this reuses 100% of the existing caveat/schema/parse
  machinery with zero new code paths, which is the more literal reading of
  "coordinate rather than duplicate that logic." Validation owner: Cody review.
- **ASSUMED**: `contract.rs` (hosted v1 wire contract) is in scope by compile
  necessity though absent from the ticket's stated file footprint. Recorded in
  the ClickUp start comment.

## Dependencies and approvals

- PR #46 (86akc0tua) and PR #47 (86akby820) — both open at start; this branch
  is cut from PR #47's tip per the ticket's own instruction, and will rebase
  onto `origin/main` once either/both land.
- No blocking ClickUp dependency owned by another role.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `IncludeInNotes` carries both new toggles, each with its own persisted key + default, round-tripping through `to_kv`/`from_kv` | `cargo test -p selahcue-core --test test_providers` | PASS | test output, 13 passed | PASS |
| C-002 | yes | Both toggles on → draft includes a podcast-show-notes section and a short-description section, each in the schema | `cargo test -p selahcue-cloud --features openai --test test_openai` | PASS | test output, 48 passed | PASS |
| C-003 | yes | A toggle off → its section does not appear, no caveat | table-driven off test in `test_openai.rs` | PASS | test output | PASS |
| C-004 | yes | Both sections are structurally/label-distinct from `short_summary`/`social_excerpts` | FR-122-style headings assertion in `test_openai.rs` | PASS, distinct headings present | test output | PASS |
| C-005 | yes | A toggle enabled that returns empty is reported requested-but-empty, reusing `DraftCaveat::SectionRequestedEmpty` (no new caveat type) | table-driven empty test in `test_openai.rs`, extended | PASS | test output | PASS |
| C-006 | yes | A degraded (`local.rs`) result still carries zero caveats for the new toggles | existing degraded test still passes unmodified in premise | PASS | test output | PASS |
| C-007 | yes | `settings.js` change and backend change are one commit/MR | `git show --stat` at commit time | both files present | commit `77125ff` carries both | PASS |
| C-008 | yes | Persistence repo round-trip covers the two new fields | `cargo test -p selahcue-data --test test_providers_repo` | PASS | test output, 3 passed | PASS |
| C-009 | yes | Headless operator webview check reflects 8 toggles, both new ones wired | `python3 scripts/operator_headless.py` | PASS, 0 FAIL | 1325 checks, 0 FAIL; mutation-verified (984 checks, 2 FAIL) | PASS |
| C-010 | yes | `make ci` passes in full | `make ci` | exit 0, ALL GREEN | `MAKE_CI_EXIT:0`, `ALL GREEN`, 0 FAIL/error[/FAILED across 7085 lines (`/tmp/make_ci_86akgqdwc_v4.log`, post-rebase onto settled `origin/main`) | PASS |
| C-011 | yes | Four-reviewer gate passed (Cody/Vera/Sana/Quinn) | dispatched reviews, blocking findings remediated | no blocking findings outstanding | review artifact | PENDING |

## Verification plan

- Focused: `cargo test -p selahcue-core`, `-p selahcue-cloud --features openai`,
  `-p selahcue-data`, `-p selahcue-operator` (via `cargo check`/inline tests).
- Broader regression: full `make ci` (fmt, clippy, all workspace tests,
  headless operator check, Flutter gate).
- Independent verifier: Cody, Vera, Sana, Quinn, each in an isolated worktree.
- Required environment: macOS dev machine, no network required for tests
  (fixture-based only).

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-009 (core Rust behaviour + JS/headless surface)
- Hypothesis: extending `IncludeInNotes` and adding two `FLAT_SECTIONS` rows
  reuses the existing schema/parse/caveat machinery with zero new branches,
  satisfying the table-driven acceptance criteria the same way the five
  existing gated flat sections already pass them.
- Change or investigation: TDD — extended every `IncludeInNotes` struct
  literal and fixture across the workspace first (compile-red until the
  fields existed), then implemented `providers.rs`, `openai.rs`
  (`FLAT_SECTIONS` + prompt guidance), `local.rs`, `contract.rs` (compile
  necessity — its `IncludeDto` mirrors `IncludeInNotes` field-for-field),
  `main.rs` (`IncludeView`/`providers_view_from`/`set_include_flag`/pinned
  contract test), `settings.js` (`defaultView`/`includeRow` x2), and
  `scripts/operator_headless.py` (mock fixture + toggle-count/wiring
  assertions, mutation-verified).
- Verifier executed: `cargo test -p selahcue-core --test test_providers`;
  `cargo test -p selahcue-cloud --features openai --test test_openai`;
  `cargo test -p selahcue-data --test test_providers_repo`; `cargo test
  --manifest-path crates/selahcue-operator/Cargo.toml --features
  dev-keys,openai-notes`; `cargo fmt --check`; `cargo clippy -- -D warnings`
  on every touched crate; `python3 scripts/operator_headless.py` (plus a
  deliberate mutation — dropping one new `includeRow` call — to confirm the
  new assertions are not vacuous, then reverted).
- Result: 13/48/3/145 tests pass respectively; fmt/clippy clean; headless
  1325 checks, 0 FAIL (984 checks, 2 FAIL under the mutation, confirming the
  new assertions bite); `EXPECTED_MIN_CHECKS` raised 1323 → 1325 with the
  real observed count.
- New evidence: committed `77125ff`, pushed, Draft PR #48 opened against
  `main` (stacked on PR #47's tip per the branch-base instruction).
- Decision: iterate → C-010 (`make ci`)

### Iteration 2

- Target criterion: C-010 (`make ci` full gate)
- Hypothesis: with all focused crate tests, fmt, clippy and the headless
  check already green, `make ci` passes cleanly.
- Change or investigation: ran `make ci` in the background, exit code
  captured directly into the log (`{ make ci > log 2>&1; echo
  "MAKE_CI_EXIT:$?" >> log; }`) per the documented piping-swallows-exit-code
  trap.
- Verifier executed: `grep -n "MAKE_CI_EXIT" log`; inspected the log around
  the failure.
- Result: `MAKE_CI_EXIT:2`. Failure is `ld: write() failed, errno=28 (No
  space left on device)` during the very FIRST `cargo test --release -p
  selahcue-licensing` step in `make ci` — before reaching any crate this
  ticket touches. Confirmed as whole-machine disk exhaustion, not a defect:
  a subsequent plain `df -h /` failed with the harness's own tool-output
  write hitting `ENOSPC`, reproduced three times.
- New evidence: none possible locally right now — even read-only shell
  commands cannot run. Per this repo's shared-checkout discipline (never
  `cargo clean`/clear target-dir locks to escape a transient failure) and the
  operating contract's stop conditions, disk cleanup on a machine shared with
  several other active agent worktrees carrying uncommitted WIP is not a
  unilateral fix — it is a destructive, irreversible action needing an
  explicit owner decision.
- Decision: BLOCKED on C-010 only. Reported on the ClickUp task and to the
  requesting session. All other completion criteria (C-001..C-009, C-007)
  remain PASS from iteration 1; will re-run `make ci` and resume toward
  VERIFIED_COMPLETE as soon as disk space is confirmed available.

### Iteration 3

- Target criterion: C-007, C-010 (branch-base rebase discipline + `make ci`)
- Hypothesis: once PR #46/#47 are settled, rebasing this branch onto their
  final position (inheriting their conflict resolution rather than
  re-deriving it) leaves only this ticket's own, genuinely-independent
  `EXPECTED_MIN_CHECKS` delta to resolve.
- Change or investigation: disk crisis resolved externally (coordinator
  confirmed, verified locally via `df -h /`: 92-104Gi available). First
  retry of `make ci` hit an unrelated issue — `Permission denied` executing
  `target/release/build/libc-*/build-script-build` in this worktree's OWN
  (not shared) target dir, an execute-bit casualty of the ENOSPC period.
  Confirmed scope with a read-only scan of `~/.cargo/registry` (no truncated
  `.crate` files, no permission-mangled `src/`, no stray `.cargo-lock` —
  shared registry cache was clean), then fixed with a scoped `cargo clean -p
  libc` (debug + release) in this worktree only. Second retry made real
  progress (no failures logged) before being killed by machine-wide
  CPU/RAM contention (multiple concurrent `make ci` runs across the shared
  machine — confirmed via `ps aux`, corroborated by the coordinator).
  Queued behind other active runs rather than racing back in (twice, per
  the coordinator's explicit sequencing).
  Once PR #46 (86akc0tua) then PR #47 (86akby820) merged to `main` in turn,
  rebased in two steps: first `git rebase --onto
  origin/feat/86akby820-scripture-verification 7bd0fba HEAD` (replaying only
  this ticket's own 2 commits, NOT the old, now-superseded copies of #46/#47's
  commits this branch used to carry stacked underneath them — a plain
  `git rebase` at that point would have replayed stale commit hashes against
  their rewritten equivalents already in the target tip, a spurious conflict
  class this ticket does not own) — one genuine conflict, in
  `scripts/operator_headless.py`'s `EXPECTED_MIN_CHECKS`, between the
  settled 1381 baseline (86akmdkdg+86akcffy0+86akc0tua+86akby820, confirmed
  real by that chain's own commits) and this ticket's pre-crisis 1325 (still
  based on the old, pre-crisis baseline of 1323). Resolved as 1381 + 2 =
  1383 (this ticket's own 2-check addition, confirmed independent of all
  four prior tickets' additions — own fixture-adjacent toggle block, no
  shared DRIVER section, no edit to any assertion they added), then
  re-derived (not trusted) by actually running the file. Then, once #47
  itself merged to `main`, a second, plain `git rebase origin/main`
  completed with ZERO conflicts (the earlier step had already resolved
  everything upstream now contained).
- Verifier executed: `cargo test -p selahcue-core --test test_providers`;
  `cargo test -p selahcue-cloud --features openai --test test_openai`;
  `cargo test --manifest-path crates/selahcue-operator/Cargo.toml --features
  dev-keys,openai-notes`; `cargo fmt --check`; `cargo clippy -- -D warnings`
  on every touched crate; `python3 scripts/operator_headless.py`;
  `git push --force-with-lease`; `gh pr view 48`; `make ci` (exit code
  captured directly in the log, not through a piped wrapper).
- Result: 12/46/161 tests pass respectively (161, up from 145 pre-rebase —
  gained tests from the three newly-merged PRs); fmt/clippy clean; headless
  check **1383 checks, 0 FAIL**, exactly matching the re-derived arithmetic;
  `gh pr view 48` → `mergeable: MERGEABLE`; `make ci` →
  `MAKE_CI_EXIT:0`, `ALL GREEN`, zero FAIL/error[/FAILED across 7085 log
  lines; post-CI recheck → `mergeStateStatus: CLEAN`.
- New evidence: force-pushed rebased branch (`2ce4049`); PR #48 confirmed
  CLEAN/MERGEABLE against the now-settled `main`.
- Decision: complete → proceed to the four-reviewer gate (C-011).

### Iteration 4

- Target criterion: C-011 (four-reviewer gate)
- Hypothesis: dispatching Cody/Vera/Sana/Quinn in parallel, each in an isolated
  worktree pinned to `ebab44a`, surfaces any remaining defects before the PR
  is marked ready.
- Change or investigation: dispatched all four. Sana's review (relayed by the
  coordinator) returned overall APPROVE with two MINOR findings, both
  content-trust issues in the two new artifacts rather than the egress
  gate/consent/keys/bounding (her framing): **F1** — the podcast prompt asks
  for scripture regardless of `scripture_extraction`, so a reference can
  reach the one artifact meant for external publication with zero
  verification. **F2** — `verify_scriptures`'s embedded-reference scan
  silently drops candidates past `MAX_EMBEDDED_REFERENCES` (64) with no
  signal at all; the two new sections sit last in `FLAT_SECTIONS` scan order
  and are structurally most exposed. Decided to fix both now (coordinator's
  lean, and squarely the harm FR-125 exists to prevent) rather than defer:
  F1 — gated the podcast prompt's scripture clause on `scripture_extraction`
  too (openai.rs, ~1 line + 2 new tests asserting the actual outgoing
  request body). F2 — changed `verify_scriptures`'s return type to
  `(Vec<ScriptureVerdict>, bool)` (the bool: embedded scan truncated by the
  cap), added `DraftCaveat::ScriptureVerificationIncomplete`, wired both
  production call sites, updated ~26 call sites across `main.rs`'s own test
  module and `selahcue-core`'s `test_scripture_verify.rs` (mechanical,
  compile-checked, no behaviour change to 86akby820's own already-reviewed
  assertions), added 2 new pure-function tests reproducing the exact
  starvation mechanism plus a positive control, added Rust-level `draft_json`
  wire-shape + `sections_to_persist` exhaustiveness tests, added
  `settings.js` rendering + 3 new headless checks (mutation-verified: 1383 →
  1387, dropping the render branch caused exactly 1 targeted FAIL). Deferred
  (not this ticket's call to make unilaterally): reordering `FLAT_SECTIONS`
  or raising the cap — the fix chosen (report truncation honestly) helps
  every section, not just the two new ones, without touching the cap itself.
  Along the way, `make ci` caught a real gap in my own process: `cargo fmt`
  scoped to `implementation/desktop` never touches `selahcue-operator`
  (workspace-excluded) — fixed with a scoped `cargo fmt` in that crate's own
  directory.
- Verifier executed: `cargo test -p selahcue-core` (all files), `cargo test
  -p selahcue-cloud --features openai`, `cargo test --manifest-path
  crates/selahcue-operator/Cargo.toml --features dev-keys,openai-notes`,
  `cargo fmt --check` (workspace AND operator crate separately), `cargo
  clippy -- -D warnings` on every touched crate, `python3
  scripts/operator_headless.py` (plus a mutation-verify), `make ci` (real
  exit code captured directly in the log).
- Result: selahcue-core all 10 test files green (including 19/19 in
  `test_scripture_verify.rs`, up from 17); selahcue-cloud 48/48 in
  `test_openai.rs`; selahcue-operator 163/163 (up from 161); headless 1387
  checks, 0 FAIL (984→1387 across the whole session's iterations); `make ci`
  → `MAKE_CI_EXIT:0`, `ALL GREEN`, zero FAIL/error[/FAILED across 6820 log
  lines; `git status` clean (no side-effect diffs this run); `gh pr view 48`
  → `mergeStateStatus: CLEAN`, `mergeable: MERGEABLE`.
- New evidence: committed `bbf5da7` (the F1/F2 fix) then `3a51182` (the fmt
  fix), both pushed. Sana's worktree advanced to `3a51182` for her re-check.
- Decision: iterate → request Sana's re-check of F1/F2 specifically; await
  Cody/Vera/Quinn's initial verdicts (in progress, dispatched in parallel).

### Iteration 5

- Target criterion: C-011 (four-reviewer gate) — Sana's re-check
- Hypothesis: Sana's own repro tooling (not just the new tests) confirms
  both F1 and F2 are genuinely closed.
- Change or investigation: Sana re-ran her own probes against commit
  `a4a7c3f` (her worktree fast-forwarded in place). Verdict (relayed by the
  coordinator, she has no direct messaging tool): **APPROVE, F1 and F2 both
  CLOSED** — F1's clause confirmed correctly gated in both directions with a
  positive control ruling out "just deleted the sentence"; F2's truncation
  flag confirmed correct at all four cases she checked (starves-and-reports,
  not-vacuous, boundary-exact, correctly-quiet); no regressions across her
  original probes (consent gate, persistence, hostile-response bounding)
  plus 19 core + 48 cloud tests passing; headless 1383→1387. One new NIT:
  the degraded-suppression comment in `settings.js` claimed "the backend
  never sets this caveat on that path anyway" — false, she proved
  `verify_scriptures` DOES run on a degraded draft too (see
  `generate_sermon_notes`'s own doc comment), and `local.rs`'s "Outline"
  section carries real transcript text that could embed a real reference.
  Fixed the comment to rest on the actual reason (one explanation at a time
  on the degraded UI, not "this cannot happen"). Comment-only; re-verified
  headless still 1387/0 FAIL. Also surfaced, explicitly NOT a finding
  against this PR: the pre-existing default `template_guidance` (untouched
  by this ticket, present at merge base `a163db4`) has the identical F1
  shape for the FOUR pre-existing artifacts — filed by the coordinator as
  its own follow-up ticket rather than folded in here.
- Verifier executed: `python3 scripts/operator_headless.py` (post comment
  fix); `gh pr checks 48` / `gh pr checks 48 --watch` (real GitHub Actions
  CI, distinct from local `make ci`).
- Result: headless 1387 checks, 0 FAIL (unchanged, confirming the comment
  fix is behaviourally inert). GitHub Actions CI on `5cae53d` triggered,
  in progress at time of writing (Sana's own process note: `gh pr view 48`
  showed `mergeStateStatus: UNSTABLE` because CI was pending, not failing —
  correctly distinguished from a real failure before claiming done).
- New evidence: pushed `a4a7c3f` (goal-contract iteration 4 record — no code
  change) then `5cae53d` (the comment fix).
- Decision: iterate → wait for GitHub Actions CI to report fully green on
  `5cae53d` before treating C-010/C-011 as settled; Cody/Vera/Quinn's
  initial verdicts still outstanding.

## Risks and rollback

- Risks: `scripts/operator_headless.py` is a large (~6500-line) end-to-end
  fixture file; its column/row-count assertion and mock fixture are the parts
  most likely to need careful, non-mechanical editing. Shared-checkout `make
  ci` contention (documented Flutter ephemeral-dir collision) — check for
  other active sessions before running it.
- Rollback: single feature branch, not merged until reviewed; revertible by
  not merging the PR.

## Pause and escalation conditions

- Either Wave-1 PR (#46/#47) is force-pushed or rebased in a way that changes
  the shape of `DraftCaveat`/`ScriptureVerdict` materially — stop and re-verify
  the baseline before continuing.
- Cody or Quinn flags the two new toggles' copy as needing design judgement —
  loop in Uma rather than guessing.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path> --completion`
- Validator result: (recorded after execution)
- Independent verification result: (recorded after execution)
- Terminal state: (recorded after execution)
- Remaining failed or blocked criteria: (recorded after execution)
- ClickUp final evidence comment: (recorded after execution)
