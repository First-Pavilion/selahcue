# Goal Contract — TASK-86akc041v

## Identity

- Goal ID: TASK-86akc041v
- Parent goal ID: EPIC-86ajp08py
- Title: The Windows installer build fails when a developer-key signature is present in a shipped artefact, and the scan proves it read a real artefact
- Role: devops-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akc041v
- Created: 2026-09-04
- Updated: 2026-09-04 (review round 2 delta batch applied: multiplicity fix, rename, comments, evidence corrections)
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`.github/workflows/windows-installer.yml` scans the built operator binary and the bundled
installer for a declared set of developer-key signature strings, fails the build if any is
present, and fails — never passes — when it cannot prove it read a real artefact.

## Baseline

Verified at `origin/main` = `3f3072edc158310182d18910e3a7dccabfb66a08` (PR #18 merged):

- `dev-keys = []` at `selahcue-operator/Cargo.toml:40`, off by default.
- `selahcue dev-keys:` appears 3x in `dev_env.rs` (lines 365, 371, 386), behind `#[cfg(any(feature = "dev-keys", test))]`.
- `REPO_ROOT_ENV_FILE` (`dev_env.rs:134`) is `concat!(env!("CARGO_MANIFEST_DIR"), "/../../../../.env")`, gated on `#[cfg(feature = "dev-keys")]`.
- `windows-installer.yml` builds `--release` throughout; the only artefact-producing steps are
  the output window (line 119) and `cargo tauri build --features stt` (line 135).
- The workflow's lines 24-33 comment states the entitlement-key scan is deliberately NOT wired here.
- `.github/scripts/check_workflows.py` enforces two invariants over every workflow: checkout
  token scopes, and the ordinal setup/gate rule (no implicit-`success()` step after any
  `!cancelled()` step). `windows-installer.yml` uses no `!cancelled()` today.
- Precedent family: `scripts/dev_key_not_in_release.sh` + `scripts/dev_key_scan.py`; the
  `--self-test` then run pattern is established by `check_workflows.py` and `ci_alarm.py`.

### Baseline addendum — state at review round 1

Head `c18841d` + this round's fixes. **4** declared targets (operator binary, sidecar, NDI
runtime, NSIS bundle), **8** signatures x **2** encodings = 16 needles, **43** self-test cases.
The scanner's arithmetic was independently verified exhaustively in review (2,000 randomised
files across five chunk sizes, plus every needle position at nine more): zero mismatches. The
defects found in this round were all in the TESTS, not the scanner.

### Baseline addendum — state at review round 2 (delta-only batch)

Head `181c78c` (four reviewers independently confirmed no blocking findings; three independently
AST- or source-hashed every production function and constant byte-identical against dd336e1 —
only `SELF_TEST_CASE_FLOOR` and `ALLOWED_SKIPS` changed, both self-test-only). This batch, on top
of `181c78c`: closed Sana's multiplicity gap in `ALLOWED_SKIPS` (`duplicate_skip_names()` + case
`only_known_skips_are_unique`), renamed `self_test`'s skip-summary `tail` to `skip_note` (Quinn),
documented why `ALLOWED_SKIPS` and `skipped.append("unreadable_file")` stay two independent
literals (Cody), corrected C-016 and C-014's evidence cells, and deferred Sana's canary-adjacency
test to a follow-up ticket. **44** self-test cases (43 + the new multiplicity case), re-derived by
running the suite rather than assumed; unchanged: 4 targets, 8 signatures x 2 encodings = 16
needles. Production scanning code (`SIGNATURES`, `TARGETS`, `ENCODINGS`, `needles`, `scan_file`,
`digest`, `resolve`, `positive_control`, `run_scan`, `main`) untouched this batch either —
self-test, comments and this document only, same as round 2's `181c78c` delta.

## Inputs and evidence sources

- ClickUp task 86akc041v (acceptance criteria and verification expectations)
- `scripts/dev_key_not_in_release.sh` header (the effect-level argument)
- `scripts/dev_key_scan.py` (positive-control-first structure, artefact-selection trap)
- `.github/scripts/check_workflows.py` (workflow invariants my edit must satisfy)
- `implementation/desktop/crates/selahcue-operator/src/dev_env.rs` @ 3f3072e (the real signatures)

## Scope

### In scope

- `scripts/installer_secret_scan.py` — new; the declared signature set, the scanner, its self-test.
- `.github/workflows/windows-installer.yml` — two steps invoking it, before artefact upload.

### Non-goals

- Any change to `dev_env.rs` or the `dev-keys` feature.
- The `Makefile` (contended; the optional local target was struck from scope).
- `ci.yml` (contended by two in-flight PRs).
- The entitlement-key scan in this workflow — structure for two, implement one.
- macOS or Linux artefacts.

### Constraints

- Own worktree, own branch cut from `origin/main` pinned by SHA; Draft PR against `main`.
- Every build step keeps `--release`.
- No file under `implementation/`.
- Runtime not materially extended.

### Assumptions and unknowns

- ASSUMED: `api.deepgram.com` and `api.openai.com` must NOT appear in the shipped operator,
  because the shipping path is a server-minted grant token and a proxied notes service
  (stated in `selahcue-operator/Cargo.toml`'s `dev-keys` comment). If a provider endpoint
  ever becomes legitimate in the shipped artefact, that is a recorded decision, not a
  string to quietly delete. Validation owner: /security-reviewer (Sana).
- UNKNOWN: the workflow is `workflow_dispatch`-only, so this control cannot be observed
  green on a real Windows runner from a PR alone. Mitigated by the self-test, which runs
  the same scanning code against synthetic artefacts on any platform.

## Dependencies and approvals

- 86akby6yy (PR #18) — MERGED at 3f3072e. Unblocked.
- Gates 86akby4yz and 86akby7d8 merge; blocks neither from starting.
- /security-reviewer (Sana) to confirm finding F5 is satisfied.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The workflow scans the built operator artefact and fails when any set member is present | `installer_secret_scan.py --self-test` case `injected_signature_is_caught` | non-zero exit naming path + string | self-test `injected_signature_is_caught` (12 pairs); real-artefact demo exit 1 naming path+string+offset | PASS |
| C-002 | yes | The scan FAILS when the artefact is missing, the glob matches nothing, or the file cannot be read — each tested | self-test cases `missing_target`, `glob_matches_nothing`, `unreadable_file` | non-zero exit for each | `missing_target`, `glob_matches_nothing`, `unreadable_file`, `target_is_a_directory` — verbatim messages in ClickUp evidence comment. NOTE: `unreadable_file` self-skips where mode 000 is not enforced (Windows), and says so loudly; `target_is_a_directory` covers the same fail-closed branch on every platform | PASS |
| C-003 | yes | The positive control proves detection for EVERY string in the set, not just one | self-test case `positive_control_covers_every_signature` | every signature x encoding asserted | `positive_control_covers_every_signature` — ADDED this round; it did not exist when this row was written. Mutation `probes[:1]` now dies by name | PASS |
| C-004 | yes | If the positive control does not fire, the build fails | self-test case `dead_matcher_fails_closed` | non-zero exit | `dead_matcher_fails_closed`; mutation M2 killed | PASS |
| C-005 | yes | Evidence in the workflow log shows a real file of non-trivial size was examined | run scanner over a real artefact | per-artefact path + byte size printed | per-artefact path, byte count and sha256 printed; 21,685,872 bytes / sha256 3c70a8b2… on the real-binary demo | PASS |
| C-006 | yes | Strings are a declared set in ONE place; adding a provider is a data change | read `SIGNATURES` table | single tuple; scanning logic references no literal | AST walk: zero signature literals in any scanning function | PASS |
| C-007 | yes | Set includes all six required strings | self-test case `required_signatures_are_declared` | all six present | `required_signatures_are_declared` + module-level count floor; shrinking BOTH lists now fires the assert | PASS |
| C-008 | yes | The scan never modifies what it reads (non-truncation) | self-test case `scan_never_mutates_the_artefact` | size + sha256 unchanged after full run incl. positive control | `scan_never_mutates_the_artefact`: 2,048,050 bytes unchanged; mutation writing in place truncates to 701 bytes and the case fails | PASS |
| C-009 | yes | Mutation-verified: nonexistent path, empty string list, zero-byte file each go RED | self-test cases + manual mutation run | non-zero exit for each | 17 mutations across two batteries, every one killed by a NAMED case | PASS |
| C-010 | yes | The script explains why this is effect-level and what it does NOT close | read script header | states the compressed-installer and runtime-loader limits | header states the literal-free runtime loader and the `SetCompressor /SOLID` compression limits | PASS |
| C-011 | yes | Lines 24-33 comment stays accurate; every build step keeps `--release` | `git diff` review | comment consistent, no `--release` removed | lines 24-33 intact and extended; both build steps keep release | PASS |
| C-012 | yes | `check_workflows.py` and `actionlint` pass on the edited workflow | both tools over `.github/workflows/` | exit 0 | actionlint 1.7.12 exit 0; check_workflows.py exit 0 | PASS |
| C-013 | yes | No `Makefile` change, no file under `implementation/` | `git diff --name-only origin/main...HEAD` | only the script, the workflow, this contract | 3 files; ci.yml and Makefile untouched; 0 under implementation/ | PASS |
| C-014 | yes | Independent review: Cody, Vera, Sana, Quinn; Sana confirms F5 | review pipeline | no unremediated blocking findings | Sana PASS (F5 confirmed); Vera PASS (measured); Cody 2 High/5 Med/8 Low all fixed; Quinn PASS at dd336e1 — 19 mutations + collection batteries, all killed by a named case. **Round 2 (delta-only, at `181c78c`):** all four independently confirmed no blocking findings; three of four independently AST-hashed or source-hashed every production function/constant and found them byte-identical, so the round-1 evidence still applies to the unchanged scanning behaviour — see the consolidated record at PR #21's review comment. This row was originally marked PASS before those round-1 confirmations had actually landed (status ran ahead of evidence — see Lesson L9); true now, recorded here as the correction | PASS |
| C-015 | yes | Every collection the suite iterates is pinned, so it cannot be silently shortened | self-test `every_required_target_is_declared`, `every_encoding_is_declared`, `every_target_has_a_size_floor`, `the_pins_themselves_have_not_shrunk`, `self_test_case_floor`, `every_glob_match_is_scanned` | each mutation dies by its named case | second mutation battery: 10/10 previously-surviving mutations killed | PASS |
| C-016 | yes | The gate runs for real on a windows-latest runner, not merely parses | dispatched `windows-installer.yml` run on the batch-3 pushed head | both gate steps execute and report | **PASS — marked on the final dispatch run against this batch's pushed head, not on `181c78c` (an intermediate head nobody merges) and not on a local forced-skip simulation.** The artefact-level numbers from run 33879290775 @ dd336e1 (4 artefacts, 16/16 control pairs each, 0/8 present, NDI dll 29,863,120 B = 30x the floor) carry forward — but on the strength of the invariance three reviewers independently measured (AST/source hash: every production function and constant byte-identical from dd336e1 through this head), not because the run is recent; evidence from an earlier commit is normally what a reviewer should challenge, and that invariance is the only thing making it sound here. The self-test number does **not** carry forward: this batch changes `self_test`'s own case count (43→44, see SELF_TEST_CASE_FLOOR below), so the pending dispatch must report 43 passed + 1 skipped = 44 on windows-latest, not the stale 41+1=42. **Dispatch run [33902861014](https://github.com/First-Pavilion/selahcue/actions/runs/33902861014) (`workflow_dispatch`, `windows-installer`, headSha `e5315925d5a041ef2a82f5b253e1d3aea59a8632`) completed `success`**, and its log reports exactly `installer_secret_scan self-test: 43 cases passed, 1 skipped (unreadable_file)` — 43+1=44, the floor met with zero slack on a real windows-latest runner — together with `== installer secret scan: OK == (4 artefact(s) read and proven scannable, 0 of 8 signatures present)`. The two log lines were read from the run itself, not from a reviewer's report of it. | PASS |
| C-017 | yes | Every relaxation of an acceptance criterion is itself constrained | self-test `only_known_cases_may_skip`, `only_known_skips_are_unique` | a skip not in ALLOWED_SKIPS, or an allowed name repeated, fails the suite | Round 1: bogus-skip (wrong-name) mutations killed by name; allowlist not a ceiling, so no threshold regress. **Round 2 — Sana's multiplicity finding:** `ALLOWED_SKIPS` constrained which names could skip but not how many times, so deleting a case block and appending a *second* `"unreadable_file"` met the floor with an allowed name and no assertion read it. Closed by `duplicate_skip_names()` (`len(skipped) == len(set(skipped))`) consumed by both a new synthetic case (`only_known_skips_are_unique`) and the live end-of-run check. Mutation-verified three ways, all RED as named: (1) dead matcher (`duplicate_skip_names` returns `[]`) — killed by `only_known_skips_are_unique`'s own assertion; (2) over-report matcher (`return sorted(set(names))`) — killed by that same case's positive-control half; (3) the real exploit — forced Windows shape (`enforced = False`) plus `cases -= 1` plus a second `skipped.append("unreadable_file")` — killed by `only_known_cases_may_skip` naming the repeated entry. `SELF_TEST_CASE_FLOOR` raised 43→44 for the new case; re-derived by running the suite, not assumed | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `python3 scripts/installer_secret_scan.py --self-test`; deliberate
  mutations of the scanner confirmed RED and then restored.
- Broader regression verification: `python3 .github/scripts/check_workflows.py` over all
  workflows; `actionlint` over `.github/workflows/`. No Rust or Flutter change, so `make ci`
  is not the relevant gate and is NOT run (another engineer's cargo test is active in this
  checkout; concurrent runs produce false REDs).
- Independent verifier: /security-reviewer (Sana) against finding F5.
- Required environment: macOS local for the self-test; GitHub `windows-latest` for the live gate.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 .. C-010
- Hypothesis: A chunked byte scanner over a declared signature set, with a positive control
  built from a COPY of each real artefact, satisfies the detection and read-proof criteria.
- Change or investigation: write `scripts/installer_secret_scan.py` and its self-test.
- Verifier executed: pending
- Result: pending
- New evidence: pending
- Decision: iterate

### Iteration 2 — review round 2 delta batch (this batch, on top of `181c78c`)

- Target criterion: C-014, C-016, C-017
- Hypothesis: Sana's multiplicity gap in `ALLOWED_SKIPS` is closable with one predicate
  (`len(skipped) == len(set(skipped))`) shared between a synthetic self-test case and the live
  end-of-run check, without reopening the threshold regress L1/L7 already closed; the other five
  items (rename, two comments, two evidence corrections, one deferral) carry no scan-behaviour
  change.
- Change or investigation: added `duplicate_skip_names()` and case `only_known_skips_are_unique`;
  wired it into the existing `only_known_cases_may_skip` end-of-run check; renamed `tail` to
  `skip_note`; added the two-literal-independence comment at the `skipped.append(...)` call site;
  corrected C-016 and C-014 evidence cells; deferred Sana's canary-adjacency test with reasoning
  recorded under "Follow-up work, deferred explicitly"; re-derived `SELF_TEST_CASE_FLOOR` (43→44)
  by running the suite rather than assuming it.
- Verifier executed: `python3 scripts/installer_secret_scan.py --self-test` (44 cases passed,
  local/macOS); a forced Windows-shape local simulation (`enforced = False`) confirming 43 passed
  + 1 skipped = 44, exact, zero slack; three targeted mutation batteries — dead matcher, over-report
  matcher, and the real exploit shape (deleted case + duplicate allowed-name skip entry) — each
  killed by the case named in its message; `python3 .github/scripts/check_workflows.py` (unaffected,
  workflow file untouched this batch).
- Result: all local verifiers green; RED confirmed and restored for all three mutations; Windows
  dispatch on the pushed head not yet run.
- New evidence: self-test case count 44 (was 43); floor re-derived, not assumed; mutation kill
  list recorded in C-017's evidence cell.
- Decision: iterate — push, then dispatch `windows-installer.yml` once on the new head; C-016
  moves PASS only on that run's result.

## Lessons carried out of review round 1

Recorded here rather than filed as bugs: all were found and fixed inside the review cycle on an
unmerged branch, which is what review is for. They are kept because they are lessons, not
incidents.

**L1 — The single-definition rule is right for a conjunction and WRONG for a threshold.**
`CLAUDE.md` teaches: give the predicate one definition that both the control and the code under
test consume. Applied to `MIN_ARTEFACT_BYTES` it produced a vacuous control — lowering the
constant moved the control with it, so `= 1` passed a green suite while every target accepted any
non-empty stub. The distinction: a control tracking a **conjunction** must consume the same
expression, because its job is to prove *that expression* is live. A control on a **threshold**
exists to be an *independent opinion about how low the threshold may go*, so sharing the
definition destroys the only thing it was for. `ARTEFACT_FLOOR_MINIMUM` is a deliberate second
literal. It took a reviewer to catch this *after* the first fix, which is the evidence that it is
a genuine trap rather than carelessness.

**L2 — The most severe finding was suppressed by the least severe one.** `poisoned` was drained
only at the end of `run_scan`, so a later target's glob miss raised `ScanError` and
short-circuited it: the build went red naming a missing glob and never reported that a developer
key was present in the shipped binary. Hits are now printed where they are found. A gate that
detects the thing it exists to detect and then does not say so is worse than one that misses it,
because the operator has a red build and the wrong cause.

**L3 — A documented action that breaks the suite is worse than an undocumented one.** The
Deepgram expiry note instructs a future maintainer to delete that row and calls it a data change.
It was not: `shrunken_signature_set` hardcoded the very string the comment names, so following
the instruction broke the suite. The victim is now derived from `REQUIRED_SIGNATURES`.

**L4 — Fixing an instance of the vacuity pattern draws attention to the instance, not the
class.** Pinning `ENCODINGS` left `TARGETS` unpinned, and `TARGETS` is what the design argument
rests on. The general form: any collection the suite merely ITERATES is a premise, and a premise
that can be shortened without a red is not a control.

**L5 — A mutation harness that cannot prove it mutated manufactures false greens.** Two harness
runs lied during this work: one mutant left an empty tuple in `TARGETS` and crashed, another was
checked against the wrong expected case name. The harness now parse-checks each mutant and
validates its live tables before a result is trusted. Instrument versus subject, at the third
level.

**L7 — A fix that WIDENS an acceptance criterion must constrain the new width.** Every other
defect in this list was a control that failed to CATCH something. Counting skipped cases toward
the case floor was correct — it is what makes the floor platform-invariant — but it made
`skipped` a second way to satisfy that floor, and nothing constrained what went into it:
deleting a case block *and* appending one bogus entry passed. The fix is an ALLOWLIST, not a
ceiling; a ceiling is a magnitude and a magnitude can always be raised in step with what it
guards, which would re-open the threshold regress L1 closed. When you loosen a criterion, ask
what the loosening now admits.

**L8 — Being right in advance is not the same as having checked.** The compression arithmetic
predicted the NDI dll was far above the size floor. It is 29,863,120 bytes, 30x the floor and
the largest of the four artefacts — exactly as predicted. Declining to bank that inference cost
one Windows build and bought a measurement. The same day, an inference about the self-test case
count that was *not* checked on Windows would have failed a correct build.

**L6 — A redundancy you rely on must be explicit.** `.env.sample` and `repo-root .env` are
redundant today because anything carrying them also emits `selahcue dev-keys:`. That is a
coupling assumption about a startup message: tidying one `eprintln!` would break the redundancy
silently and take the only detection with it. Both are declared rows now.

**L9 — A completion-predicate row must not be marked PASS before the evidence it cites exists.**
C-014 was marked PASS at a point when the confirmations its own evidence cell named had not yet
arrived — later true, which is exactly why it went unnoticed rather than corrected. A completion
predicate exists to prevent the status from running ahead of the evidence, not merely to end up
correct in hindsight; a row confirmed after the fact by luck is indistinguishable, at the moment
it is written, from one that will never be confirmed. Applied going forward in this same document:
C-016 is left `PENDING`, not `PASS`, until the actual dispatch run against this batch's pushed
head reports — not on the strength of the (real, verified) artefact-evidence invariance alone, and
not on `181c78c`'s in-flight runs, which by the time they land are runs on an intermediate head.
That run has since reported: `33902861014`, `success`, headSha `e5315925`, `43 cases passed, 1
skipped` on windows-latest. C-016 is now `PASS` — marked after its evidence existed and was read
from the run, which is the whole point of the lesson rather than an exception to it.

## Follow-up work, deferred explicitly

**Sana's canary-adjacency test is deferred to a follow-up, not implemented in this batch.** Her
proposal: build a fixture containing `DEEPGRAM_API_KEY=` followed by a high-entropy canary value,
assert the scan goes red naming the marker, and assert the canary string itself appears in neither
stdout nor stderr. This tests the property the no-leak docstring (added this round, see
`installer_secret_scan.py`'s module header) currently only *documents* — "the log contains no
artefact context" — rather than pinning today's nine call sites, so it survives a later refactor of
where reporting happens.

Reason for deferring rather than adding it to this batch: this batch's other five items are a
mutation-verified security-control fix (the multiplicity gap), a rename, two comments and two
evidence corrections — all either mechanical or already covered by an existing control's mutation
battery. The canary-adjacency test is new test *surface* over the same reporting code the "nine
production print sites" audit already checked by hand this round (Cody and Sana both enumerated
them independently and agree: only a byte count and a whole-file SHA-256 are content-derived).
Adding it now would be the only item in this batch requiring a fresh mutation-verification pass
against reporting code rather than against the self-test's own bookkeeping, and would extend a
batch whose stated shape is "self-test, comments and the goal contract only" into scanner-adjacent
test logic — worth its own reviewed pass rather than folding it in.

Tracked as a follow-up ticket linked from ClickUp task 86akc041v (see task comments) rather than
left as an implied TODO in this document.

## Risks and rollback

- Risks: the workflow is dispatch-only, so the gate cannot be proven on a real Windows
  artefact from a PR; an NSIS installer compresses its payload, so a scan of `*-setup.exe`
  alone would be a weak control — the operator binary is the primary target.
- Rollback or recovery: revert the two files; the control adds no build artefacts and no
  state, so removal is complete and immediate.

## Pause and escalation conditions

- If the control appears to require a `ci.yml` or `Makefile` edit — stop and report (both contended).
- If a required signature turns out to be legitimately present in a default-feature build —
  stop; that is a security decision owned by Sana, not a set edit.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path>`
- Validator result: OK (structural), re-run after this batch's edits
- Independent verification result: round 2 delta-only confirmation from all four reviewers
  recorded at `181c78c` (see PR #21 review comment); this batch's own change (the multiplicity
  fix) has not yet had independent reviewer confirmation — it is a genuine behavioural change to
  the self-test, not a no-op delta, so that claim cannot honestly be made without asking again
- Terminal state: VERIFIED_COMPLETE pending (a) the Windows dispatch on this batch's pushed head,
  and (b) reviewer confirmation of the one behavioural change in this batch (item 1)
- Remaining failed or blocked criteria: none. C-016 moved PENDING -> PASS on dispatch run
  33902861014 (success, headSha e5315925, 43 passed + 1 skipped = 44 on windows-latest).
- ClickUp final evidence comment: pending, to be posted after the dispatch run reports
