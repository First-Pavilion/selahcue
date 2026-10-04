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
| C-002 | yes | The listed guards are tested: breaking any one of them (a whole guard, or one clause of it) makes the self-test fail. This is a statement about the 194 listed mutations, not about every conceivable one | `python3 scripts/translation_catalog_mutation_proof.py` | exit 0, `194/194 mutations caught`, none "CANNOT APPLY" | Iterations 3 to 6 below; ClickUp evidence comment | PASS |
| C-003 | yes | The converter is correct on real data: eBible's current USFM for the five bundled Bibles converts to the shipped assets, with only explained differences | `python3 scripts/build_translation_catalog.py --work-dir WORKDIR --verify-bundled` | exit 0; KJV, ASV, DBY `IDENTICAL` (93,287 rows); WEB 17 and WEBBE 20 rows `DIFFERS AS PINNED` | Iteration 2 below; ClickUp evidence comment | PASS |
| C-004 | yes | The four allowlist translations build, meet eBible's own published verse counts, and rebuild byte-identically | `python3 scripts/build_translation_catalog.py --work-dir WORKDIR --out-dir OUT1`, then again with `--offline --out-dir OUT2`, then `diff -r OUT1 OUT2` | exit 0 twice; BSB 31,086, HAU 31,087, IBO 31,103, YOR 31,087 verses; `diff -r` empty | Iteration 2 below; ClickUp evidence comment | PASS |
| C-005 | yes | The publish gate holds: with `--require-cleared` the three pending Biblica entries are refused and nothing is written; `--only BSB --require-cleared` builds the cleared translation alone | `python3 scripts/build_translation_catalog.py ... --offline --require-cleared`, then the same with `--only BSB` | first: exit 1, three `legal_review is still pending` lines, output directory not created; second: exit 0, folder holds exactly `bsb.tsv.gz` and `catalog.json` | Iterations 3 and 4 below | PASS |
| C-006 | yes | The self-test runs in `make ci` and in CI, and the repo's workflow checker accepts the edit | `grep -n build_translation_catalog Makefile .github/workflows/ci.yml`; `python3 .github/scripts/check_workflows.py` | one hit in each file; `workflow checks: ... OK` | Iteration 3 below | PASS |
| C-007 | yes | Nothing shipped changes: no Rust, UI, asset or wire change | `git diff --name-only origin/main...HEAD` | only the six paths listed under In scope | PR description; Iteration 3 below | PENDING |
| C-008 | yes | The branch is up to date and a Draft PR is open against `main` | `git rev-list --count HEAD..origin/main`; `gh pr view` | `0`; PR is Draft, base `main` | PR link on ClickUp | PENDING |
| C-009 | yes | Independent review passed: code (Cody), security (Shadow) and QA (Quinn) each reviewed at the head SHA and every blocking finding is fixed and re-checked | review round report page linked on the PR | each reviewer's verdict recorded, zero open blocking findings | report page URL | PENDING |
| C-010 | no | Performance review (Vera) | not applicable: an offline build script that runs in about one second on the self-test and about three seconds on the real four translations; it ships nothing to users | recorded as not applicable with that reason | this row | NOT_APPLICABLE |

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

### Iteration 4 (review round 1 at db66f0d4: Cody BLOCK, Quinn FAIL, Shadow APPROVE WITH CONDITIONS)

- Target criterion: C-009 (independent review), and through it C-001 to C-005.
- Hypothesis: the three reviews share a small number of root causes, and fixing those plus the gaps in the test evidence clears them.
- Change or investigation: reproduced every blocking finding myself before changing code, then fixed the causes. Findings and what was done:
  - **Inline markup (Cody F1, Quinn B1, Hausa data).** `clean()` stripped every mid-line marker and kept its content, so `\fm ,\fm*` doubled a comma in four Hausa verses and an unknown marker would have put its content in a verse. The claim "refuses unknown markers" was true for line-start markers only. Now `\fm` is a note, any inline marker outside a known list is refused with its verse, and a note whose closer belongs to a later note (which would delete every verse between) is refused.
  - **Space before punctuation (Quinn B2, Cody N1).** Removing a footnote left the space that sat before it: 26 BSB, 4 Igbo and 5 Hausa verses read "egg ?". My first fix missed four verses where the punctuation sits behind an inline marker (`\wj* \f..\f* \wj ?`); the look-ahead now skips markers. Result: 0 verses in all four. Row-level diff against the previous build: every changed row is the deletion of one stray space or comma (BSB 27, Igbo 4, Hausa 15, Yoruba 0). **[Corrected in iteration 5: this was false for 6 of the 15 Hausa rows, where the deleted space was correct.]** The BSB, Hausa and Igbo digests changed as Quinn predicted; nothing was pinned or published.
  - **Quadratic regexes (Shadow C1, and one more found while checking it).** `\w` followed by spaces (10,000 spaces took 1 s, 40,000 took 16 s) and the DOTALL footnote regex (140 KB of unclosed openers took 5 s). Now linear: 2,000,000 unclosed openers refuse in 12 ms. **I then introduced a third quadratic in the fix** (`text[pos:].lstrip()` copies the rest of the text per note; 100,000 notes took 2.4 s). Found by timing the real entry points, fixed with index scans; 100,000 notes now take 0.1 s and doubling the input doubles the time (x1.9, x2.0, x2.0).
  - **Zip size cap (Shadow C2).** The cap read the size the zip declares about itself; a member declared as 1,000 bytes cost 201 MiB to read. Now reads are bounded to cap+1: 25 MiB for the same file. Also: a member-count cap, corrupt or non-UTF-8 members and macOS sidecars are clean refusals instead of tracebacks.
  - **Licence gate weaker than claimed (Cody M2/M3, Quinn 4.7/4.8).** It matched a substring ("public domain" is inside "not public domain") and trusted a cached catalogue. Now: eBible's Copyright column must EQUAL the entry's pin; the licence page inside each zip (`copr.htm`) must still contain the pinned phrases and none of "all rights reserved", "non-commercial", "no derivatives", "not public domain"; `--require-cleared` always refetches the catalogue; the catalogue's own SHA-256 is recorded. The real texts pass: BSB says Public Domain, the three Biblica texts say CC BY-SA 4.0.
  - **Publish footguns (Cody M5, Quinn 4.3/4.4).** `--only BSB --require-cleared` was refused because of unrelated pending entries; it now builds BSB alone. `--out-dir` must be absent or empty, so a stale folder cannot carry legal-pending files beside a new catalogue.
  - **Test evidence (Quinn 4.1, Cody M4).** Both reviewers wrote mutations of their own against guards I had not listed: Quinn 20 of 24 survived, Cody 13 of 25. Added tests and mutation entries for the CLI flags, the catalogue's legal fields, the three heading-fusion clauses, the total zip cap, the licence checks, the fetch timeout and others (47 to 104 mutations, all caught). One of my new entries survived on first run because every test of one clause also tripped a second check; rewritten to isolate it. **I did not run Quinn's or Cody's own mutation scripts** (they sit in their scratch folders and target line text that this round changed), so "all their survivors are now caught" is not claimed. Both are asked to re-run their own sets at the new head.
  - **Docs (Cody M1, Quinn 5).** The docstring said an empty verse "aborts the run" (it is omitted and counted) and that `--verify-bundled` fetches (it does not). Corrected. The "about 20 seconds" figure was wrong (about 3). A vacuous self-test assertion (WEBBE = WEB + NBSP, true by construction) replaced with the measured pins.
- Verifier executed, at this iteration's head: `--self-test` (also on Python 3.14); the mutation proof (104/104); `--verify-bundled` (KJV, ASV, Darby byte-identical; WEB 17 and WEBBE 20 as pinned, unchanged by every fix); real build of the four translations, rebuilt with `diff -r` empty; `--require-cleared` with and without `--only`; the hostile-input timings above; both goal-contract validators; `check_workflows.py`.
- Result: all pass. Not yet re-reviewed: that is the next step.
- New evidence: eBible's data has no unclosed notes and no unknown inline markers in any of the twelve zips, so none of the new refusals fire on real input (the five bundled English Bibles still convert with the same 0, 17 and 20 differing rows).
- **Deliberately not done**, with reasons: (1) splitting the 1,400-line script and its self-test into modules (Cody S1): the repo's `--self-test` pattern keeps them together and the split is a refactor with no behaviour change, better as its own ticket if wanted; (2) the mutation proof still records only "the self-test failed", not why (Quinn 4.2); (3) the ticket description still lists MSB, YLT and OEB-US for v1: **the scope change needs the product owner's acceptance** and I have recorded it on the ticket as a comment, not as an edit.
- Decision: iterate (re-review at the new head).

### Iteration 5 (review round 2 at 2a439335: Cody BLOCK, Quinn FAIL, Shadow APPROVE WITH CONDITIONS)

- Target criterion: C-009 (independent review) again.
- **A claim I made in iteration 4 was false, and the fix I described introduced the defect.** I wrote that every changed row was "the deletion of one stray space or comma". Cody and Quinn independently showed that 6 of the 15 changed Hausa rows were the deletion of a space that was CORRECT: Hausa starts words with the apostrophe U+2019 (`'yan`, `'yar`), and my new spacing rule treated it as closing punctuation, so "Abiya 'yar Zakariya" became "Abiya'yar Zakariya" (GEN 49:8, GEN 49:26, 2SA 17:25, 2KI 18:2, 1CH 3:5, 2CH 1:16). My check had verified the KIND of change, not that each deleted space was stray. The unit test only covered an apostrophe followed by a space.
- Change or investigation, all findings reproduced first:
  - **Apostrophe (Quinn N1, Cody 3.1).** A quote closes a phrase only when no letter or digit follows it. All six verses are back to their earlier text (checked row by row). Hausa now changes in 9 rows (not 15), BSB 27, Igbo 4, Yoruba 0. To replace the check that was too weak I wrote a detector that flags any deleted single space that joined two words or put a word-initial apostrophe against the word before it: 6 hits on the previous build, **0 on this one**, in all four translations.
  - **Licence-page tag regex (Cody 3.3, Shadow N1).** `<[^>]+>` is quadratic on a page of `<` (80,000 took 1.9 s, 160,000 took 6 s; a 1 MiB page extrapolates to minutes). Shadow's note that a `[^>]*` variant is also quadratic is why the fix is `<[^<>]*>`, which stops at the next `<`. At the full 1 MiB cap: 0.13 s. Both ways of treating a tag (as a space, as nothing) are now checked, so a phrase a tag splits ("Non-<b>commercial</b>") is still seen.
  - **`\qc` in Psalm 119 (Cody 3.2, Quinn N2).** "Label-shaped" included any 1-3 Latin words, so a verse's own "Amen." was silently dropped. A label now needs a Hebrew letter AND must sit where a section starts (after verse 8k).
  - **Publish run builds from fresh files (Cody M2 residue).** `--require-cleared` now refetches the zips of the selected translations as well as the catalogue, so the licence page the gate reads and the bytes published come from the same fresh download.
  - **Shadow's lower findings.** F1: the code and id patterns accepted a trailing newline ("KJV\n" passed every gate, including the bundled-collision check); now `fullmatch`. F4: `.part` and `.tmp` files are created exclusively, a planted symlink is removed or refused and never followed, and only a file the call created is ever removed on failure. F5: a corrupt or hostile catalogue is a refusal. **[Corrected in iteration 6: a row cut short still crashed; a catalogue WITHOUT a BOM is valid and builds, as it should.]** F7: a redirect from HTTPS to anything but HTTPS is refused. N2: the member-count cap also applies on the licence-page path. Also: an unreadable `--out-dir` is a refusal (Quinn N6); the forbidden-phrase list gained "noderivs" and "by-nc" (Quinn N4).
  - **Source hygiene, found by me while fixing these.** The tool I edit files with turned some typed `\uXXXX` escapes into real characters, so the converter's source contained U+202A (a bidirectional control character), U+FEFF (a BOM) and no-break spaces. That is the "Trojan Source" class of problem and GitHub would flag the file. Both Python files are now ASCII-only (visible escapes), and the self-test enforces it, including on the allowlist (no invisible characters).
  - **Test evidence.** The wall-clock bounds Cody called flaky are now ratio checks (four times the input may take about four times as long, never sixteen). **[Corrected in iteration 6: the first version of this check could still flake (it failed once in 144 runs on Python 3.12); see iteration 6.]** Added: the BOM on the real catalogue (Quinn showed removing `utf-8-sig` kept every test green while a real run crashed), sorted catalogue keys, a loose `.usfm` suffix, every note kind, three notes in a row, each closing mark, tab spacing, the English-only checks not running on other languages, and the `--refresh`, `--verify-bundled`, `--require-cleared`, `--offline`, `--only`, `--base-url` and `--allowlist` wiring through `main()`. 104 to 154 mutations, all caught. One of my new mutants survived on first run (nothing tested that the default opener carries the redirect rule) and one entry was stale; both fixed.
- **Deliberately not done**, with reasons: (1) a note on its own line before punctuation, and a no-break space before a note, still leave a space (Quinn N3: no real zip has either); (2) a note directly after a verse number followed by punctuation is refused with a misleading message (Quinn N5, Cody 3.7: refused loudly, not in real data); (3) the download timeout is per socket operation, not total (Shadow F6: bounded by the 64 MiB size cap; this is an owner-run build, not a service); (4) `old.keys() | new.keys()` in the positive control and the Habakkuk `endswith` vs `in` check (Cody: equivalent mutants); (5) splitting the 1,500-line script (Cody S1); (6) the mutation proof records "the self-test failed", not why (Quinn 4.2); (7) Cody's independent oracle, a row-by-row comparison against eBible's VPL export, is not in the repo: it found the Hausa comma rows and would be worth adding as its own ticket.
- Verifier executed at this iteration's head: `--self-test` on Python 3.9 and 3.14; the mutation proof (154/154); `--verify-bundled` (KJV, ASV, Darby byte-identical; WEB 17 and WEBBE 20 as pinned, unchanged); real build of the four translations twice, `diff -r` empty; the fused-word detector (0); `--require-cleared` with and without `--only BSB`; hostile-input timings.
- Result: all pass. Not yet re-reviewed.
- Decision: iterate (re-review at the new head).

### Iteration 6 (review round 3 at d7283707: Shadow APPROVE, Cody APPROVE WITH CONDITIONS, Quinn PASS WITH CONDITIONS)

- Target criterion: C-009 (independent review), and C-006 (CI).
- **Verdicts.** The apostrophe regression is fixed and confirmed independently by all three (Quinn's own oracle, which never calls the code under test, finds 0 suspect deleted spaces in all nine translations and flags exactly the six verses on the 2a439335 converter). Shadow: no remaining finding that changes the security posture. What was left were conditions and low findings, all addressed here; none changes a single byte of any built asset (the four real translations rebuild identically to the build reviewed in round 3).
- **Statements of mine that were not true as written, corrected:**
  - "The wall-clock bounds are now ratio checks, not limits that could flake." Quinn saw the assertion fail once in 144 runs on Python 3.12 (18 ms then 246 ms, 14x). The ratio test with a 20 ms floor and one run per size was still a timing test. Now each size runs three times and the fastest counts, and the floor is 0.1 s. Result: 0 failures in 120 runs on Python 3.12 with six running at once. That is evidence, not proof: a timing test can in principle still flake on a machine that stalls. The three quadratic mutants are still caught.
  - "A corrupt or hostile catalogue is a refusal": a row cut short (fewer values than the header) still crashed (`AttributeError` on `None`). Now refused, as is a header missing a column the gate reads, a translationId that appears twice, and an allowlist whose structure would crash the gate (a code, licence or legal_review that is not a string, a Habakkuk note that is a number, a translation that is not an object, a licence without its fields, and so on; the last three of these were still crashing when Cody and Quinn re-tested, and are fixed in the next commit). A real-data check first: the real 1,551-row catalogue has every column and no duplicate id.
  - `--help` said `--refresh` re-downloads "every zip" and `--require-cleared` only "refuse any pending entry". Both now say what the code does.
  - I had verified Python 3.9 and 3.14 only; the interpreter on the ubuntu CI runner is newer, and 3.12 is where the flake appeared. Self-test now run on 3.9, 3.12 and 3.14.
- **Other findings fixed.** A quote followed by an inline marker and then a letter (`'\wj yar\wj*`) was still treated as closing and fused the word (Quinn D2; 0 real verses). One upper-case Latin word on a Psalm 119 `\qc` line with no Hebrew letter ("HHETH.") is now refused instead of silently kept (Cody N-4). A plain-`http` URL is refused before anything is requested (Shadow I1). Tests added for the gaps Cody listed (digit or letter after a quote, a note at the end of a line, `\qc` word limit and chapter scope, the licence page in a folder in any case, the `__MACOSX/` clause alone, the unclosed-note timing). Mutations 154 to 194, all caught (Cody's and Quinn's confirmation passes added: one error needle per catalogue case, each catalogue column required on its own, each licence field required on its own, every non-https scheme, a chain of markers after a quote, the label look-alike's length bounds, and a larger size for the weakest timing case).
- **CI: `rust (ubuntu-latest)` FAILED at `d7283707` and at `512aa6e5` (twice), and the cause is known: the runner ran out of disk.** The job's check-run annotation reads `System.IO.IOException: No space left on device` on the runner's own diagnostic log, on three different runners (`GitHub Actions 1000009975`, `1000010004`, `1000010011`), same runner agent 2.337.0, in the same Rust test steps (LAN server E2E, scripture download, then the job ends). The job's step logs are not recoverable (GitHub returns "BlobNotFound"), so the annotation is the evidence. **My earlier description of this as "the runner dying, not a test failing" was wrong and is withdrawn.** It is reproducible, not a one-off. What I checked: the diff since the last green head touches no Rust; the Rust cache is present and warm (918 MB, restored by the failing runs), so it is not a cold build; this PR's converter self-test uses 0.66 MB of temporary disk at its peak, so it cannot be what fills a runner; `db66f0d4` and `2a439335` passed the same job; main's last CI run (19:43) passed. **The decisive experiment:** I re-ran the Ubuntu job of `2a439335`, the commit that PASSED at 20:46 with none of this round's changes. It now FAILS too, so the cause is the runner environment today and not anything in this PR's diff. Not caused by this PR, shown by the experiment above. It needs DevOps (Otto): the Ubuntu runners' free disk, and whether main will fail the same way on its next push. I am not claiming the PR is clear of this until the job is green on this PR's head.
- **Not done, deliberately** (unchanged unless noted): a note on its own line before punctuation and a no-break space before a note (Quinn N3: no real zip has either); `\v 1 \f..\f*,` gives a misleading message (N5); per-socket, not total, download timeout (Shadow F6); splitting the 1,600-line script (Cody S1); the mutation proof records "the self-test failed", not why; `write_all`'s final rename loop is not all-or-nothing if one rename fails midway (Cody N-5: each file is staged first, so a failure there leaves complete files but a partly renamed folder); the survivors Quinn lists as low importance (zip-member BOM: 0 of 806 real members have one; an ASCII-only line strip; the number of the caps); a duplicate-looking quote class for languages neither reviewer reads.
- **Scope change ACCEPTED by the product owner (Oluwole Majiyagbe, 2026-10-04, in the session chat, after the reviewers noted it had no recorded acceptance):** v1 is BSB, Yoruba, Igbo and Hausa. The ticket text listed MSB, YLT and OEB-US; the real data ruled them out (YLT and MSB have no title markup in eBible's USFM, OEB-US has 44 of 66 books). The ticket description was updated to match and a comment records the acceptance.
- Verifier executed at this iteration's head: `--self-test` on Python 3.9, 3.12 and 3.14; the mutation proof (194/194); `--verify-bundled` (KJV, ASV, Darby byte-identical; WEB 17 and WEBBE 20 as pinned, unchanged); the four real translations built twice with `diff -r` empty and identical to the round-3 build; the ASCII-only scan; both goal-contract validators; `check_workflows.py`.
- Result: all pass locally. CI and the final review confirmations are pending.
- Decision: iterate (confirm with the reviewers, watch CI at the new head).

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
