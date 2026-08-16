# Goal Contract - GOAL-sec-presentation-import-condition-reverify

## Identity

- Goal ID: GOAL-sec-presentation-import-condition-reverify
- Parent goal ID: GOAL-sec-presentation-import-postbuild-review
- Title: Independently re-verify the v1.2 merge conditions of the presentation-import threat model against the remediated working tree and issue a v1.3 verdict on whether the condition is discharged
- Role: security-reviewer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-16
- Updated: 2026-08-16
- Maximum iterations: 5
- Independent verification required: yes

## Objective

Adjudicate, against code and by independent mutation-level evidence, whether v1.2's merge condition 2 (replace the hollow B3 lying-header test with a referenced-bomb test that actually exercises the streaming actual-byte counter) is genuinely discharged - explicitly deciding the coordinator-raised question of whether `a_lying_header_does_not_get_past_the_streaming_counter` passing while `account()`'s cap returns are neutered means the condition is only apparently satisfied - and re-verify each remediation item that landed since v1.2 (streamed central directory, `PptxBuilder::replacing` panic-on-no-match, new `tests/test_zip.rs`, F2 allowlist guard, F3 `ooxml.rs` lints, F4 `build.rs` always-on backstop, `read_stored` compressed-size extent, `quick-xml` pin), then update `docs/security/THREAT-MODEL-presentation-import.md` in place with a v1.3 revision preserving the audit trail, a clear merge verdict, the restated DEFERRED shell constraints, and the RR1 standing-condition status. Review only: no file under `implementation/` modified, nothing staged, committed or reverted.

## Baseline

Verified current state before substantive work:

- HEAD `f9d132a`; the importer remains UNCOMMITTED in the working tree; `git status --porcelain -- implementation/` snapshot hash `8790468` recorded in session.
- Threat model v1.2 (`docs/security/THREAT-MODEL-presentation-import.md`, 679 lines) verdict: MERGE WITH CONDITIONS - condition 1 shell-slice review before wiring (still future), condition 2 fix F1 (the hollow lying-header test), recommended F3/F4.
- Remediation has landed (all Verified by read): `zip.rs` streams the central directory one 46-byte record at a time through `ByteSource` (fixes the Cody-found ~1015 MiB peak from `vec![0u8; cd_size]`); `tests/support/mod.rs` `replacing()` substitutes at generation time and panics on no-match; new `tests/test_zip.rs` (334 lines) covers ArchiveTooLarge / RatioExceeded / EntryTooLarge (stored path) / MAX_IMPORT_IMAGES / MAX_ZIP_NAME_LEN / stored-entry extent; the lying-header test now references its bomb via `replacing()` but the bomb is `deflate_zeros` (~1000:1), which the ratio guard refuses at ~1 MiB - before either byte counter is in range.
- Parent-agent report (to be independently replicated, not trusted): neutering `account()`'s EntryTooLarge/ArchiveTooLarge returns produced 2 failures in test_zip.rs while the lying-header test still passed via the `zip.rs` ratio guard.
- ClickUp MCP tools are unavailable in this session; per repo precedent the pending ClickUp update is recorded in this contract.

## Inputs and evidence sources

- `docs/security/THREAT-MODEL-presentation-import.md` v1.2 (the condition under adjudication)
- `docs/delivery/goals/GOAL-sec-presentation-import-postbuild-review.md` (parent goal, v1.2 evidence)
- The uncommitted working-tree implementation (`selahcue-import`, `selahcue-engine`, operator media store, `scripts/import_guards.sh`)
- Read-only command evidence: `cargo test`, `sh scripts/import_guards.sh`, `cargo tree`, greps
- A mutation replica of the crate in the session scratchpad (never the working tree)

## Scope

### In scope

- Read-only code review of the remediated files; execution of the crate's own tests; independent replication of the account()-neutering mutation in a scratchpad copy of the workspace.
- A reasoned adjudication: condition discharged / not discharged, with the gate-integrity question answered explicitly.
- Re-examination of why the v1.2 constraint-by-constraint pass missed the central-directory allocation, and an explicit statement of which controls in the model are verifiable only by measurement rather than inspection.
- In-place v1.3 update of the threat model (revision note, verdicts, DEFERRED restatement, RR1 status).
- This goal contract.

### Non-goals

- No modification of any file under `implementation/`; no fixes; no staging/commit/revert.
- No re-adjudication of constraints v1.2 already verified and that no landed change touches.
- No risk acceptance on behalf of the owner; no shell-slice review (the shell is still unwired).
- No new report/summary document - the threat model is updated in place.

### Constraints

- Write only under `docs/` (and the session scratchpad for the mutation replica).
- Mutation experiments run only on a scratchpad copy; the working tree is never mutated.
- Findings labelled Verified / Inferred / Assumed / Unknown; parent-agent claims are replicated, not cited as evidence.
- Severity calibrated to a single-operator offline desktop deployment.

### Assumptions and unknowns

- ASSUMED: the working tree state reviewed is the state that would merge; any post-review change to the reviewed files invalidates the verdict for them.
- UNKNOWN until measured: whether `test_memory.rs` now bounds the hostile-central-directory scenario that produced the 1015 MiB peak.

## Dependencies and approvals

- Owner acceptance of RR1-RR6: recorded (v1.1/v1.2); the ADR-0016 worker milestone remains the standing condition - its ClickUp ticket status is re-checked, not re-decided.
- ClickUp write path: unavailable; pending update recorded below.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Goal Contract validates before substantive work | `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-condition-reverify.md` | Exit 0 | Validator output in session | PASS |
| C-002 | yes | The account()-neutering mutation is independently replicated in a scratchpad copy: which tests fail and which pass is recorded from actual runs, and the lying-header test's behaviour under the mutation is confirmed or refuted | Mutated scratchpad build + `cargo test -p selahcue-import` there; unmutated in-tree run as control | Recorded pass/fail lists from both runs | Session command output; summarised in threat model v1.3 | PASS |
| C-003 | yes | Condition 2 of v1.2 is adjudicated discharged or not, with the gate-integrity question (ratio-guard masking) answered explicitly and any residual finding named and ranked | Reasoned adjudication in the threat model against the C-002 evidence | An unambiguous discharged/not-discharged statement with evidence | `docs/security/THREAT-MODEL-presentation-import.md` v1.3 | PASS |
| C-004 | yes | Every landed remediation item is re-verified against code: streamed central directory (incl. bounded-memory evidence), replacing() panic, test_zip.rs coverage claims, F2 allowlist delivers B2, F3 ooxml lints present and honoured, F4 build.rs backstop always-on, read_stored compressed-size extent opens no new path, quick-xml pin | Code inspection + test/guard execution | Per-item verdicts with file/line evidence | `docs/security/THREAT-MODEL-presentation-import.md` v1.3 | PASS |
| C-005 | yes | The threat model carries a v1.3 revision note preserving the audit trail, a clear merge verdict, the restated DEFERRED shell constraints (B4 placement, C13 timeout/lock, C3 clipboard flavor, C11 textContent, C1/C2 admission caps), the methodology re-examination (why the CD allocation was missed; which controls are measurement-only), and the RR1 standing-condition status | Document review | All named elements present and unambiguous | `docs/security/THREAT-MODEL-presentation-import.md` | PASS |
| C-006 | yes | No file under `implementation/` is modified by this goal and the contract validates at completion | `git status --porcelain -- implementation/` hash vs session start; validator | Identical hash `8790468`; exit 0 | git + validator output in session | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: full read of `zip.rs`, `tests/test_zip.rs`, `tests/support/mod.rs`, the lying-header test, `ooxml.rs` lint header, `build.rs` backstop, `import_guards.sh`, `Cargo.toml`/`Cargo.lock` pins; in-tree `cargo test -p selahcue-import`; `sh scripts/import_guards.sh`; scratchpad mutation replica per C-002; `test_memory.rs` hostile-directory scenario run.
- Broader regression verification: `git status --porcelain -- implementation/` hash unchanged at completion.
- Independent verifier: this review is itself the independent check for the v1.2 condition; its verdict is handed to the authorised human gate via the parent agent and Build Control.
- Required environment: local repository, cargo toolchain, session scratchpad.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: A valid contract can be authored from the v1.2 model, the tasking, and the already-read remediated code.
- Change or investigation: Read skill + team protocol docs, threat model v1.2 in full, parent goal contract, `zip.rs`, `limits.rs`, `test_zip.rs`, `tests/support/mod.rs`, the lying-header test; recorded HEAD and implementation/ status hash; authored this contract.
- Verifier executed: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-condition-reverify.md`
- Result: C-001 PASS (validator green, 6 criteria).
- New evidence: validator output in session.
- Decision: iterate

### Iteration 2

- Target criterion: C-002
- Hypothesis: The parent agent's mutation report replicates faithfully in a scratchpad copy of the workspace, and a complementary ratio-guard mutation plus a both-guards mutation pin down exactly which tests protect which control.
- Change or investigation: rsync'd `implementation/desktop` (minus `target/`) into the session scratchpad; ran the unmutated in-tree suite as control (`cargo test -p selahcue-import`: 81/81 green, exit 0, full untruncated log); mutation A - neutered `account()`'s EntryTooLarge/ArchiveTooLarge returns in the replica only; mutation B - restored pristine zip.rs, neutered only the zip.rs:363 ratio guard; mutation C - neutered both.
- Verifier executed: `cargo test -p selahcue-import --tests` in the replica per mutation.
- Result: C-002 PASS. Mutation A: test_zip.rs 2 FAIL (`a_stored_member_past_the_per_entry_cap...` degrades to `[ImageFormatUnsupported]` vs `[ImageTooLarge]` at test_zip.rs:209; `the_whole_archive_budget_aborts...` import SUCCEEDS with 17 slides, every bomb fully inflated) while `a_lying_header_does_not_get_past_the_streaming_counter` PASSES (ratio guard refuses the ~1000:1 zeros bomb) - replicating the parent's report exactly. Mutation B: test_zip 1 FAIL (`a_high_ratio_member_is_refused...`), lying-header PASSES (byte counter stops the bomb at the 16 MiB cap). Mutation C: lying-header FAILS (`[ImageFormatUnsupported]` - the bomb inflated in full).
- New evidence: mutant run logs in scratchpad (`mutant1.log`, `mutant2.log`, task outputs); matrix recorded in threat model SS12.1.
- Decision: iterate

### Iteration 3

- Target criterion: C-003, C-004, C-005, C-006
- Hypothesis: With the mutation matrix in hand, the condition can be adjudicated precisely (battery discharges it; the renamed lying-header test alone would not), the remaining remediation items re-verified, and the model updated to v1.3.
- Change or investigation: Full read of `zip.rs` (streamed `read_central_directory`, `read_stored` compressed-size extent, `account`, ratio guard), `tests/test_zip.rs`, `tests/support/mod.rs` (`replacing()` panic path, `HostileDirectory`, `deflate_lowish_ratio`), the lying-header test, `limits.rs`, `ooxml.rs` lint header + `has_doctype`, `build.rs` repair-and-report, `test_memory.rs` hostile scenarios 5-7 and budgets, `import_guards.sh`, Cargo.toml/lock pins; ran `sh scripts/import_guards.sh` (OK) and simulated allowlist fail-closed by injecting `ureq` + an unlisted name into the real `cargo tree` output (both caught); `cargo clippy -p selahcue-import --all-targets` clean (F3 honoured); confirmed the shell is still unwired (no caller of `read_pptx`/`import_text`; `deck_import_image` pre-exists at HEAD and does not touch selahcue-import); confirmed no ADR-0016 worker ticket exists in the delivery record. Authored SS12 in the threat model in place (revision note 1.3, condition-2 adjudication + F6, per-item table, methodology SS12.3, DEFERRED restatement, RR1 status, verdict).
- Verifier executed: document review against the tasking's deliverable list; `git status --porcelain -- implementation/ | shasum` = `8790468...` (identical to session start); validator with completion flag.
- Result: C-003 PASS (condition adjudicated DISCHARGED with the apparent-vs-genuine question answered; F6 LOW raised), C-004 PASS (all eight items re-verified with evidence), C-005 PASS (SS12 present with every mandated element), C-006 PASS (hash identical; validator green).
- New evidence: threat model at 868 lines with SS12; session command outputs.
- Decision: gate-review

## Risks and rollback

- Risks: the mutation replica must faithfully mirror the working tree or its pass/fail lists mislead; mitigated by copying the tree verbatim and mutating only the two return statements. Concurrent commits can race the review; mitigated by recording HEAD and the status hash and scoping the verdict to them.
- Rollback or recovery: docs-only output; the threat model revision can itself be revised.

## Pause and escalation conditions

- Pause if verification would require modifying `implementation/` or the mutation replica cannot be made faithful.
- Escalate to the owner: any adjudication that the condition is NOT discharged (merge gate holds), and the standing RR1 milestone condition.
- Escalate to Aria/Kenji via the parent agent: any new code-change finding.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-condition-reverify.md --require-complete`
- Validator result: PASS
- Independent verification result: This review IS the independent confirmation v1.2's conditioned verdict required; its verdict (condition 2 discharged; change set merges; condition 1 stands; RR1 milestone ticket still missing) is handed to the parent agent and the authorised human gate.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none for this goal. Feature-level: condition 1 (shell-slice security review before wiring) stands; F6/F2-residual recommended non-gating; RR1's ADR-0016 milestone ticket must be created when ClickUp is writable.
- ClickUp final evidence comment: PENDING (ClickUp MCP unavailable this session; post to Build Control `86ajnx548` when available - see the handoff text in the session output).
