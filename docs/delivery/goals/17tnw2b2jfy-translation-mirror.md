# Goal Contract — 17tnw2b2jfy-translation-mirror

## Identity

- Goal ID: 17tnw2b2jfy-translation-mirror
- Parent goal ID: 17tnw2b2jfv-user-downloaded-translations
- Title: A committed, tested pipeline turns a curated eBible.org allowlist into byte-reproducible, normalised Bible assets plus a SHA-256-pinned catalogue, refusing anything it cannot prove clean or licensed
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2jfy
- Created: 2026-10-04
- Updated: 2026-10-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Ship `scripts/build_translation_catalog.py` and its allowlist (A1 of story 17tnw2b2jfv). Given eBible.org USFM it
produces one `CODE.tsv.gz` asset per translation in the same row format as the bundled Bibles and a `catalog.json` that pins each asset by
SHA-256, applying the same normalisation the bundled Bibles satisfy (17tnw2b2g7q). It must refuse, with a clear message
and with nothing written, any translation it cannot prove clean (headings fused into verses, unknown markup, wrong
chapter or verse counts) or licensed (licence not permitted, eBible no longer marks it redistributable, copyright text
drifted, legal review pending on a publish run). Out of scope: publishing the files, embedding the catalogue in the app
(A2), any Rust change.

## Baseline

**Verified** on `origin/main` at `0b116558` (2026-10-04):

- `scripts/strip_bible_headings.py` exists (one-shot, not in `make ci`). There is no USFM-to-TSV converter and no allowlist.
- Five bundled Bibles ship as `selahcue-scripture/assets/{kjv,web,asv,webbe,dby}.tsv.gz`, converted from eBible VPL.
- `selahcue-scripture` has a `download` feature with one catalogue entry (YLT) whose URL is `OWNER-SUPPLIED.invalid`.
- eBible's catalogue (`translations.csv`, 1,551 rows) has no NIV or NLT row; `engamp` is flagged not Redistributable and not downloadable.
- eBible USFM census over twelve zips (five bundled translations plus BSB, MSB, YLT, OEB-US, Yoruba, Igbo, Hausa): no verse bridges and no lettered verses anywhere; OEB-US has 44 of 66 books; MSB and YLT have no title markup.

## Inputs and evidence sources

- ClickUp 17tnw2b2jfy (this task), story 17tnw2b2jfv, epic 86ajp07gt; related 17tnw2b2g7q, 17tnw2b2hkm
- `docs/research/LICENSING-REGISTER.md` (YLT and the Berean family are public domain via CC0; CC BY-SA is an open legal item)
- `implementation/desktop/crates/selahcue-scripture/tests/test_scripture_data.rs` (the corpus rules the bundled Bibles satisfy; ported as the converter's post-checks)
- eBible `translations.csv` and `*_usfm.zip` files, fetched 2026-10-04 (twelve zips, digests in the build output)

## Scope

### In scope

Footprint (new files unless noted):

- `scripts/build_translation_catalog.py`, `scripts/translation_allowlist.json`, `scripts/translation_catalog_mutation_proof.py`
- `Makefile` (one self-test line in `ci`) and `.github/workflows/ci.yml` (one step beside the reachability step)
- this contract

### Non-goals

- Publishing assets to the bucket (owner / DevOps); embedding `catalog.json` in the app and the CI check that it matches the published digests (A2)
- YLT, MSB, OEB-US, NET, FBV, LSV, EMTV, Nigerian Pidgin, Amplified (excluded with reasons recorded in the allowlist)
- Fixing the bundled WEB/WEBBE speaker labels the positive control found (follow-up 17tnw2b2jj2)
- Any Rust, UI, wire-protocol or bundled-asset change

### Constraints

- One ticket, one branch, one Draft PR off `origin/main`; never merged by this role; no `Co-Authored-By` trailer
- Python imports at module top; no new third-party dependency (standard library only, plus `strip_bible_headings`)
- Untrusted input is bounded: network downloads capped, zip members capped, nothing extracted to disk
- The converter refuses rather than guesses; every refusal is a message that names the verse and the reason

### Assumptions and unknowns

- **Assumed**: eBible's `Redistributable` and `Copyright` columns are authoritative for what may be mirrored. Legal sign-off on the CC BY-SA texts is A6 (17tnw2b2jg3); until then those entries are `legal_review: pending` and `--require-cleared` refuses them.
- **Unknown**: gzip bytes can differ across zlib builds, so the pinned digest must come from the artefact actually published, not a rebuild elsewhere. Recorded in the script docstring.

## Dependencies and approvals

- A6 (legal) gates publishing the three Biblica texts, not building them. Owner supplies the bucket. Neither blocks this change.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The self-test passes with no network and covers the converter, every licence gate, the download cap, atomic writes, determinism and the positive-control logic | `python3 scripts/build_translation_catalog.py --self-test` | exit 0, prints `build_translation_catalog self-test: ok` | ClickUp 17tnw2b2jfy evidence comment; CI step "Translation mirror converter self-test" | PASS |
| C-002 | yes | Every guard is tested: breaking any one makes the self-test fail | `python3 scripts/translation_catalog_mutation_proof.py` | exit 0, `47/47 mutations caught`, none "CANNOT APPLY" | Iteration 3 below; ClickUp evidence comment | PASS |
| C-003 | yes | The converter is correct on real data: eBible's current USFM for the five bundled Bibles converts to the shipped assets, with only explained differences | `python3 scripts/build_translation_catalog.py --work-dir WORKDIR --verify-bundled` | exit 0; KJV, ASV, DBY `IDENTICAL` (93,287 rows); WEB 17 and WEBBE 20 rows `DIFFERS AS PINNED` | Iteration 2 below; ClickUp evidence comment | PASS |
| C-004 | yes | The four allowlist translations build, meet eBible's own published verse counts, and rebuild byte-identically | `python3 scripts/build_translation_catalog.py --work-dir WORKDIR --out-dir OUT1`, then again with `--offline --out-dir OUT2`, then `diff -r OUT1 OUT2` | exit 0 twice; BSB 31,086, HAU 31,087, IBO 31,103, YOR 31,087 verses; `diff -r` empty | Iteration 2 below; ClickUp evidence comment | PASS |
| C-005 | yes | The publish gate holds: with `--require-cleared` the three pending Biblica entries are refused and nothing is written | `python3 scripts/build_translation_catalog.py ... --offline --require-cleared` | exit 1, three `legal_review is still pending` lines, output directory not created | Iteration 3 below | PASS |
| C-006 | yes | The self-test runs in `make ci` and in CI, and the repo's workflow checker accepts the edit | `grep -n build_translation_catalog Makefile .github/workflows/ci.yml`; `python3 .github/scripts/check_workflows.py` | one hit in each file; `workflow checks: ... OK` | Iteration 3 below | PASS |
| C-007 | yes | Nothing shipped changes: no Rust, UI, asset or wire change | `git diff --name-only origin/main...HEAD` | only the six paths listed under In scope | PR description; Iteration 3 below | PENDING |
| C-008 | yes | The branch is up to date and a Draft PR is open against `main` | `git rev-list --count HEAD..origin/main`; `gh pr view` | `0`; PR is Draft, base `main` | PR link on ClickUp | PENDING |
| C-009 | yes | Independent review passed: code (Cody), security (Shadow) and QA (Quinn) each reviewed at the head SHA and every blocking finding is fixed and re-checked | review round report page linked on the PR | each reviewer's verdict recorded, zero open blocking findings | report page URL | PENDING |
| C-010 | no | Performance review (Vera) | not applicable: an offline build script that runs in about one second on the self-test and about 20 seconds on the real four translations; it ships nothing to users | recorded as not applicable with that reason | this row | NOT_APPLICABLE |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-006 above, all run from the worktree at the head SHA
- Broader regression verification: `make ci` is the full gate; this change touches only Python and CI wiring, so the relevant parts are the Makefile line (run directly) and `check_workflows.py`. The Rust and Flutter gates are unaffected by construction (no file under `implementation/` changes) and are not claimed.
- Independent verifier: Cody, Shadow and Quinn, each in their own worktree pinned to the head SHA
- Required environment: Python 3.9 or later, network for C-003 and C-004 only (twelve eBible downloads, about 29 MB)

## Iteration ledger

### Iteration 0 (process disclosure)

- This contract was written after the converter prototype and its first real-data runs, not before them, which the operating contract forbids. The ledger below records what was done and what each run found; no result has been backdated.

### Iteration 1

- Target criterion: C-003 (the converter is correct on real data)
- Hypothesis: converting eBible USFM directly, with headings never emitted, reproduces the bundled assets.
- Change or investigation: wrote the converter; ran `--verify-bundled`.
- Verifier executed: `--verify-bundled` against the five real USFM zips.
- Result: FAIL. KJV and DBY differed in 9 rows; WEB, WEBBE and ASV aborted.
- New evidence: three real defects in the converter, each found only because the control existed. (1) USFM's single space after an opening marker is a delimiter, but `strip_bible_headings.clean_usfm` keeps it, so `(\add is\add* it` became `( is it`; a dedicated cleaner fixes it. (2) WEB, WEBBE and ASV contain verses with a number and no text (Acts 8:37, Luke 17:36 ...); the shipped assets omit them, so the converter omits them and counts them (WEB: 31,103 `\v` lines, 31,098 rows). (3) ASV marks Psalm 119's letters with `\qc`; classifying them by a list of letter names missed ASV's own spelling "HHETH" and fused it into 119:56, so the rule became structural (a `\qc` line with no verse in Psalm 119).
- Decision: iterate.

### Iteration 2

- Target criterion: C-003 and C-004
- Hypothesis: after the three fixes the only remaining differences are explained.
- Change or investigation: word-level diff of the 37 remaining WEB/WEBBE rows; real build of the six candidate translations.
- Verifier executed: `--verify-bundled`; the real build; a second offline build and `diff -r`.
- Result: C-003 PASS (KJV, ASV, DBY byte-identical; WEB 17 and WEBBE 20 differ only as pinned). The real build REFUSED MSB and YLT: psalm titles are fused into verse 1 with no markup (BSB, by contrast, marks them), so there is no oracle for where a title ends. It also refused BSB until its Habakkuk 3:19 note was named. BSB, Hausa, Igbo and Yoruba then built and met eBible's published verse counts exactly; the second build was byte-identical.
- New evidence: of WEB's 17 differing rows, 12 are eBible revising WEB since the import, 4 are Song of Solomon speaker labels ("Friends", "Beloved", "Lover") that the VPL import fused into verse text (a defect in the shipped assets; follow-up 17tnw2b2jj2), and 1 is a space after an em dash. WEBBE adds 3 no-break-space rows because its asset lost the NBSP that WEB's kept. OEB-US has only 44 of 66 books. BSB cannot serve as an oracle for MSB (the Old Testaments differ in over a hundred verses). YLT, MSB and OEB-US were therefore dropped from v1 and recorded, with reasons, in the allowlist's `excluded` list; YLT ticket 17tnw2b2hkm was corrected.
- Decision: iterate (write the self-test and prove it).

### Iteration 3

- Target criterion: C-001, C-002, C-005, C-006
- Hypothesis: a self-test over synthetic USFM covers every guard, and a mutation battery proves it.
- Change or investigation: wrote the self-test (fixtures, gates, fetch cap, atomic write, CLI, positive-control logic); wrote the mutation proof; wired both into `make ci` and CI.
- Verifier executed: `--self-test`; `translation_catalog_mutation_proof.py`; `--require-cleared` run; `check_workflows.py`.
- Result: first battery 44/47 caught. The three survivors were missing tests, not missing guards: a book that is short or long (only the chapter-count check sees it), Psalm 119 missing a verse, and the catalogue's `omitted_verses`. Tests added; second battery 47/47. Three of my own test cases were wrong (a start-label on a letter boundary is correctly stripped; `[ ]` are stripped not refused; a fixture lacked the Habakkuk note) and were corrected, not the code. `--require-cleared` refuses YOR, IBO and HAU and creates nothing. `check_workflows.py`: 4 workflows, 15 jobs OK.
- New evidence: self-test runs in about 0.9 s.
- Decision: handoff to review once the PR is open.

## Risks and rollback

- Risks: (1) the converter is stricter than the data in a future eBible re-release and refuses it (intended: stop and look); (2) the CC BY-SA entries may need relabelling after legal review (A6; they cannot be published until then); (3) a NIV/NLT/Amplified expectation: this change adds none, and says why in the allowlist and ticket.
- Rollback: revert the commit. Nothing ships to users and no asset or Rust file changes.

## Pause and escalation conditions

- A reviewer finds the converter emits text that is not verse text: stop, add the case to the self-test first, then fix.
- Legal (Nathan, A6) decides the Biblica texts cannot be mirrored: remove their allowlist entries; no other change.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2jfy-translation-mirror.md --require-complete`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: C-007, C-008, C-009
- ClickUp final evidence comment: pending
