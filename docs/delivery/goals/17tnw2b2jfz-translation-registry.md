# Goal Contract - 17tnw2b2jfz-translation-registry

## Identity

- Goal ID: 17tnw2b2jfz-translation-registry
- Parent goal ID: 17tnw2b2jfv-user-downloaded-translations
- Title: The scripture crate can install, validate, store and serve downloaded Bible translations under a bounded memory cap, without touching the five bundled Bibles
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2jfz
- Created: 2026-10-05
- Updated: 2026-10-05
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Ship the runtime registry for downloaded translations (A2 of story 17tnw2b2jfv) in `implementation/desktop/crates/selahcue-scripture`: an embedded, validated catalogue; install-time validation of a downloaded asset; storage in the app data directory with an atomic receipt; a bounded LRU cache of decoded indexes; a `Bible` handle that serves bundled and installed translations through one set of lookup methods; a Cargo feature split (`installed` has no network crate, `download` adds the HTTP fetch); and a download function that cannot be called without a terms acceptance. The placeholder `Translation::Ylt` is removed. Out of scope: any UI (A3, A4), output-host wiring (A5), publishing (A7), licensed text (B0).

## Baseline

**Verified** on `origin/main` at `0b116558` (2026-10-05):

- `Translation` is a closed enum of six variants (five bundled, plus the placeholder `Ylt`). Each decoded index lives in a `OnceLock` forever. `Ylt` loads from the OS cache directory under feature `download`; its catalogue URL is `https://OWNER-SUPPLIED.invalid/...`, so it has never been fetchable.
- Feature `download` is the only feature. The crate has no JSON dependency. `selahcue-operator` enables `download`; `selahcue-app` and `selahcue-desktop` enable nothing.
- Consumers of the removed pieces: `selahcue-operator/src/main.rs` (`list_translations`, `download_translation`), `selahcue-app` tests (three `is_downloadable` filters, one `Some("YLT")` sample), `quote_match.rs` (cell array sized to six), eight scripture test files, `scripts/operator_headless.py` (a mock that names YLT; it does not call Rust).
- PR 181 (A1, Draft) builds the mirror assets and `catalog.json` schema 1. Nothing is published, so there is no real base URL.

## Inputs and evidence sources

- ClickUp 17tnw2b2jfz (this task), story 17tnw2b2jfv and its owner-decision comments of 2026-10-04; A1 = 17tnw2b2jfy (PR 181), A7 = 17tnw2b2jqd (publish job; URL layout), A3 (operator commands; the terms acceptance record lives there)
- The approved plan `/Users/m.oluwole/.claude/plans/i-believe-we-can-toasty-dream.md` (sections A2 and Verification)
- `implementation/desktop/CLAUDE.md` (bounded-memory test method), ADR-0017, `docs/research/LICENSING-REGISTER.md`
- A1's converter (`scripts/build_translation_catalog.py` on `origin/feat/17tnw2b2jfy-translation-mirror-pipeline`, read only) for the row grammar and the text rules the validator repeats

## Scope

### In scope

Footprint:

- `implementation/desktop/crates/selahcue-scripture/` (Cargo.toml, src, tests, `assets/catalog.json`)
- `implementation/desktop/crates/selahcue-app/tests/` (remove the `is_downloadable` filters and the YLT sample only)
- `implementation/desktop/crates/selahcue-operator/src/main.rs` and its `Cargo.lock` (compile fix only: no YLT, no `catalog()`; the download command reports "not published yet" until A3 adds the terms step)
- `scripts/import_guards.sh`, `Makefile`, `.github/workflows/ci.yml`, `.github/workflows/rust-canary.yml` (run the new feature; guard that `installed` has no network crate)
- `implementation/desktop/Cargo.lock` and `implementation/desktop/crates/selahcue-operator/Cargo.lock` (one line each: the scripture crate gains `serde_json`, which is already in both locks)
- `implementation/desktop/CLAUDE.md` (one paragraph on the registry and the two features)
- this contract

### Non-goals

- Operator UI, consent record, the real `download_translation` flow (A3, A4); output-host wiring and glyph coverage (A5); the publish job and bucket URL (A7); legal copy (A6)
- Quote detection for downloaded translations (stays KJV-only, unchanged)
- Changing the LAN wire protocol, the five bundled assets, or any bundled-translation behaviour
- Adding any Cargo feature to `selahcue-operator` or `selahcue-desktop`

### Constraints

- One ticket, one branch, one Draft PR off `origin/main`; never merged by this role; no `Co-Authored-By` trailer
- Memory must stay bounded: no unbounded cache; the bounded-memory test must fail when the cap is removed
- Source files ASCII-only (an earlier ticket lost days to an invisible bidirectional character and a BOM)
- Every claim in the PR description is re-checked against the code before it is written

### Assumptions and unknowns

- **Assumed**: `serde_json` (already used by several workspace crates and present in the lock) may be added to this crate. The brief expected no new dependency; no new crate enters the lock, but this is a manifest change and is called out for the owner.
- **Assumed**: the placeholder catalogue digests come from the latest A1 scratch build (`r4a`, 2026-10-04 22:47). They are not published artefacts and are labelled as such inside the file.
- **Unknown**: the translations bucket base URL (owner). The shipped catalogue has `base_url: null`, so nothing can be requested.
- **Unknown**: gzip bytes can differ across zlib builds, so the pinned digest must come from the artefact actually published (A7). A1's converter also writes literal UTF-8 (Yoruba with its accents) where `catalog.json` holds `\u` escapes, so A7 must re-escape to keep the non-ASCII scan quiet.
- **Assumed**: one writer process. The write lock, the in-flight list and the caches are per process; the operator is the only installer and the host only reads. If that changes, the answer is an advisory lock file (deferred), not this module.

## Dependencies and approvals

- A1 (PR 181) defines the catalogue schema; this change reads schema 1 and does not depend on A1's merge.
- A7 sets the final URL template and the real digests; the template is a single function so A7 can change it.
- The brief says to stop and report if a new dependency is needed. `serde_json` is the one deviation and is reported, not hidden.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Installing and reading N+1 translations never keeps more than N decoded indexes alive (N defaults to 3), counted by the indexes themselves (a drop guard each owns, created in the only constructor) and not by a counter the cache keeps; the least recently used one is the one evicted; a file that fails its digest or its validation never evicts a good index; decodes in flight never exceed the free slots; a resident read, a handle lookup and `installed()` complete while another translation's decode is held mid-flight (the gate is inside the decode, `LoadStage::InsideDecode`); and removing the cap makes the test fail | `cargo test -p selahcue-scripture --features installed --test test_registry_bounded` (17 tests) and the mutations in the ledger | exit 0; mutations M1 to M10, R2 M10b, and round 2 Q1 to Q4, Q9, Q11, Q12, Q14, V1, V2, P1, B10a to B10d, F2a, F2b each turn it red | Iterations 3, 4, 6 and 7 | PASS |
| C-002 | yes | A re-downloaded translation is served from the new file without a restart, and the replaced index is never alive beside the new one | `--test test_registry` (`a_reinstalled_translation_is_served_from_the_new_file_without_a_restart`, `installing_over_an_older_file_that_is_resident_frees_it_at_once`, `a_read_that_races_a_reinstall_retries_against_the_new_receipt`), `--test test_registry_bounded` (`a_file_replaced_by_another_process_is_swapped_in_without_both_copies_alive`) | exit 0; mutations M6, R2 M10b, Q5/Q8, Q9, V1, B14a turn it red | Iterations 3, 4 and 6 | PASS |
| C-003 | yes | A decompression bomb (16 MiB inflate cap), a wrong-hash file, a truncated file, a substituted file, an oversized file, a malformed row, a book outside 1 to 66, a wrong verse count, more rows than the verse counts allow (at install from the catalogue entry, at load from the receipt), a second gzip member or any byte after the first, markup residue, an invisible or direction-changing character (U+0080 to U+009F, U+2028, U+2029, U+202A to U+202E, U+2066 to U+2069, U+200B, U+2060, U+FEFF; U+200C and U+200D allowed) and out-of-order rows are each rejected and leave no installed file, no receipt entry and no staging file; a catalogue `file_name` with a path component is refused; the five bundled assets pass the same rules (a committed test), and A1's four real assets (BSB 31,086, HAU 31,087, IBO 31,103, YOR 31,087 verses) were verified by hand against A1's scratch build `r4a`, the files whose digests the embedded catalogue carries, with a throwaway test: not repeatable from the repo (the coordinator names A1's build at `940e262d`; I did not rebuild at that commit) | `--test test_validate` (27), `--test test_registry` (44), `--test test_catalog` (21), `--test test_bible` (`every_bundled_asset_satisfies_the_installed_asset_rules`) | exit 0; mutations V1 to V16, C4, C14, C15, A1a to A1c, A7e, B12a, B12b, B13a to B13h turn it red | Iterations 3, 4 and 6 | PASS |
| C-004 | yes | An interrupted install (`.part` left behind) is cleaned up and never listed as installed; a planted symlink is never followed and a file this call did not create is never removed; an unreadable `installed.json` is refused by install, download and remove (before a byte is fetched) and never makes them forget the other installs, and `repair_receipt` rebuilds an unreadable or missing one only from files that match a catalogue pin and does nothing to a readable one (a later catalogue that drops or re-pins a translation does not make it forget the installed files); the receipt is re-read when its inode, its modification time or its length changes; the write lock is not held across the network (`remove` and another install complete while one install is stalled), a queued install gives up when cancelled, and cleanup skips the staging file of an install in flight | `--test test_registry` | exit 0; mutations V4, V5, V6, V7, V8, R1, R2, R3, H3, A4a to A4d, A5a to A5d, F1, F1b, G2a to G2c turn it red | Iterations 3, 4, 6 and 7 | PASS |
| C-005 | yes | A build with only `installed` has no HTTP client or TLS crate in its dependency tree, and `make ci` guards it | `cargo tree -p selahcue-scripture --no-default-features --features installed -e normal`; `sh scripts/import_guards.sh` | no `ureq`, `rustls`, `hyper`, `reqwest` (0 matches); guard prints OK; with `dep:ureq` added to `installed` the guard exits 1 | Iteration 5 | PASS |
| C-006 | yes | The embedded catalogue parses and is validated (unknown schema, duplicate code, code colliding with a bundled one, bad file name, bad digest all refused); an entry with no base URL reports "not published yet" and makes no request; a `legal_review: pending` entry is not offered and the download function refuses it | `--test test_catalog`, `--test test_download` | exit 0; mutations C1 to C15, D1 turn it red | Iterations 3 and 4 | PASS |
| C-007 | yes | `download_and_install` is the ONLY download function (the legacy `fetch_translation`, `fetch_translation_with`, `TranslationAsset`, `TranslationFetchError`, `default_cache_dir` with its `SELAHCUE_SCRIPTURE_CACHE` variable, and `sha256_file` were removed in iteration 6). It refuses a non-HTTPS start URL and a redirect to a non-HTTPS URL (loopback http only through an explicit test constructor that does not exist in release builds), reports progress, honours cancel (including a read or a request that fails after Cancel was pressed, reported as cancelled and not as a network error), needs a `TermsAcceptance` argument, refuses an unreadable install record before any request, and no error text carries a URL's query string, fragment or credentials | `cargo test -p selahcue-scripture --features download --test test_download` (25), `--test test_url_policy` (11), `--test test_catalog` (21) | exit 0; mutations D2, D4a, D5, D6, V9, V9b, E D12, A4c, A7a to A7d, A7f, A8c turn it red | Iterations 3, 4 and 6 | PASS |
| C-008 | yes | Bundled behaviour is unchanged: the five wire codes, `quote_match`, the cross-language LAN fixtures, every existing scripture test (YLT-specific ones removed) and the app and operator consumers | `cargo test -p selahcue-scripture` (3 feature sets), `cargo test -p selahcue-app --features server`, `cargo test -p selahcue-lan --features server`, `cargo check` of the operator, `make ci` | all exit 0 (scripture 48 / 181 / 208 passed; app 321; lan 129 passed incl. `wire_fixtures_are_stable_for_cross_language_clients`; `make ci` ALL GREEN at the iteration 7 head: 4,716 Rust tests passed, 0 failed, plus Flutter 380 and the marketing and Python gates) | Iterations 5, 6 and 7 | PASS |
| C-009 | yes | The handle serves an installed code through the same lookups as a bundled one (verses, text, search, chapter, adjacent chapter, exists, bounds) with the same answers on the same data, including a translation with omitted verses and one without the Old Testament; a damaged installed translation can be told apart from an empty one (`Bible::check`) | `--test test_bible` (9), `--test test_bible_is_lazy`, `--test test_bible_global` | exit 0 (the bundled KJV installed as `KJX` is compared with `KJV` over 71 books x 154 chapters x 5 selections; the bundled ASV installed as `ASX` is compared with `ASV` over every chapter with an omitted verse); mutations B1 to B4, A3, A8d, B14b turn it red | Iterations 3, 4 and 6 | PASS |
| C-010 | yes | Gates: fmt, clippy (default, `download`, `installed`), import guards, `cargo deny`, `cargo audit`, and `make ci` once at the end | commands in the verification plan | all exit 0, real output recorded in the PR description (re-run at the iteration 7 head: fmt, clippy x3 and the library in `--release` x3, scripture tests x3, app, lan, operator check, import guards, `cargo deny check licenses sources bans` x2, `cargo audit` x2, `check_workflows.py`, one `make ci`) | Iterations 5, 6 and 7 | PASS |
| C-011 | yes | Source files are ASCII-only except where they were not before | `LC_ALL=C grep -nP '[^\x00-\x7F]'` over touched files, compared with `origin/main` | no new non-ASCII bytes and no invisible or bidirectional character in any touched file | Iteration 5 | PASS |
| C-012 | yes | The branch is up to date and a Draft PR is open against `main` | `git rev-list --count HEAD..origin/main`; `gh pr view` | `0`; PR is Draft, base `main` | PR 188 (https://github.com/First-Pavilion/selahcue/pull/188), Draft, base `main`, mergeable; behind count 0 at head dfe9c9c6 (the last code commit of iteration 7; the docs commit that records it follows); linked on ClickUp | PASS |
| C-013 | yes | Independent review passed: code (Cody), security (Shadow), QA (Quinn) and performance (Vera, for the memory cap) each reviewed at the head SHA and every blocking finding is fixed and re-checked | review round report page linked on the PR | each verdict recorded, zero open blocking findings | round 1 (head dd23a637): Cody, Shadow and Vera approve with conditions, Quinn passes with conditions, nothing blocking; fixed in iteration 6. Round 2 (head 368a131d): Cody approve with conditions, Vera approve, Shadow approve, Quinn pass with conditions, nothing blocking; the remaining conditions are fixed in iteration 7 and need the orchestrator's last look at the new head | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-009 from the worktree at the head SHA, each test file run with its siblings (never `--exact`), every gate captured to a file and its exit code checked (a piped gate hides its exit code)
- Broader regression verification: the commands in C-008 and C-010; `make ci` once at the end with `/opt/homebrew/bin` and the Flutter SDK on PATH
- Independent verifier: Cody, Shadow, Quinn and Vera, dispatched by the orchestrator, each in its own worktree pinned to the head SHA
- Required environment: macOS arm64, Rust 1.98.0 (pinned), own `CARGO_TARGET_DIR` inside the worktree

## Iteration ledger

### Iteration 1

- Target criterion: baseline and design
- Hypothesis: a handle type over shared slice helpers lets one set of lookup code serve both kinds, so nothing is duplicated and the five-variant enum keeps its shape
- Change or investigation: read the crate, every consumer, A1's converter and the real A1 build; chose an instance-based `Registry` (so tests cannot interfere through shared state) with a process-wide default for the host
- Verifier executed: baseline `cargo test -p selahcue-scripture --features download`: 59 tests, exit 0
- Result: design recorded in the PR description
- New evidence: ureq 3 checks `https_only` on every redirect hop; the real A1 BSB, Yoruba, Igbo and Hausa assets are on disk for a one-off positive control
- Decision: iterate

### Iteration 2

- Target criterion: C-001 to C-009 (implementation, tests first)
- Hypothesis: modules url_policy, catalog, validate, registry, bible and download can each be driven by a failing public-API test file first
- Change or investigation: one test file per module (`test_url_policy`, `test_catalog`, `test_validate`, `test_registry`, `test_registry_bounded`, `test_bible`, `test_bible_global`, `test_bible_is_lazy`, `test_data_dir`, `test_download`), each seen to fail to compile before its module existed; `Ylt`, `is_downloadable` and the YLT placeholder catalogue removed; consumers updated
- Verifier executed: the three feature sets, fmt, clippy -D warnings
- Result: all green on the first complete run, which is why iteration 3 exists
- New evidence: removing the evict-before-decode ordering was found by review of my own code, not by a test (see iteration 3, M8/M9)
- Decision: iterate

### Iteration 3

- Target criterion: every control claimed in C-001 to C-009 must fail when it is removed
- Hypothesis: a green first run proves nothing about the tests
- Change or investigation: a mutation runner (95 single-guard mutant runs over registry, validate, catalog, download, url_policy, bible), each run against the whole suite with `--features download`, the file restored from git after each
- Verifier executed: the runner. Round one: 75 mutants, 69 caught, 5 survived, 1 invalid pattern. Round two (the survivors re-targeted plus 15 new guards): 18 caught, 2 survived
- Result: every survivor but one was a real test gap. Round one: the install-time prune (the next read pruned anyway), the receipt size cap (the test used a whitespace-only receipt, which the parser refused first), the licence and source URL checks (no test), and the low-level policy check (nothing asserted that a refused URL creates no directory). The fifth, a start-URL check in `download_and_install`, was redundant with the per-hop check in `open_stream`, so it was removed rather than tested. Round two: an `Interrupted` read retry and the cleanup of an orphan file when the first receipt cannot be written (both untested)
- New evidence: evict-before-decode (peak is the cap, not cap + 1) and "a bad file does not evict a good index" were added after M8 and M9 were written; `peak_decoded` is the seam that proves the first (a counter the cache kept itself; iteration 6 replaced it with `peak_live_indexes`, counted by the indexes' own drop guard, after Quinn's Q14 and Vera's late-eviction mutants passed against it)
- Decision: iterate

### Iteration 4

- Target criterion: the survivors of iteration 3
- Hypothesis: each survivor is killed by one new assertion
- Change or investigation: padded valid receipt, resident-then-install, licence/source URL cases, `a..b.tsv.gz`, an interrupted read, a directory planted where the receipt goes, unrelated `.part`/`.tmp` files that cleanup must not touch, an assertion that a refused low-level URL creates no directory; cleanup narrowed to this module's own staging names; the two test-only constructors made `#[cfg(debug_assertions)]` so a release binary cannot build a loopback policy (a release test build fails with an explanation)
- Verifier executed: the survivors re-run: all caught. Import guard mutated twice (a `dep:ureq` added to `installed`; `zmij` removed from the allowlist): both exit 1
- Result: no known survivor remains. 95 mutant runs in total (87 caught first time, 7 survived, 1 stale pattern); six survivors were test gaps, now tested, and one (the second start-URL check) was a redundant check, removed rather than tested
- New evidence: the real A1 BSB, Yoruba, Igbo and Hausa assets (1.3 to 1.5 MB each) install through the real embedded catalogue and read back (BSB 31,086 verses, YOR 31,087, IBO 31,103, HAU 31,087; John 3:16 in BSB; Yoruba diacritics intact); install about 130 to 190 ms and first read about 115 to 150 ms in a debug build; maximum resident set 13.7 MB at a cap of 1, 24.5 MB at 3, 29.0 MB at 4 (debug build, macOS)
- Decision: iterate

### Iteration 5

- Target criterion: C-005, C-008, C-010, C-011
- Hypothesis: nothing outside the crate changed behaviour
- Change or investigation: gates run from the worktree at the head SHA with their output captured to files and exit codes read (nothing piped into `tail`)
- Verifier executed: `cargo fmt --check` (0); clippy `-D warnings` default, `installed`, `download` (0, 0, 0) and the library in `--release` (0); `cargo test -p selahcue-scripture` default 48, `installed` 142, `download` 171 passed; `cargo test -p selahcue-app --features server` (0); `cargo test -p selahcue-lan --features server` 129 passed; `cargo check` of the operator (0, no warnings); `sh scripts/import_guards.sh` (0); `cargo deny check licenses sources bans` (0); `cargo audit` in the desktop workspace and in the operator (0; each prints allowed warnings for crates this change did not add); `python3 .github/scripts/check_workflows.py` (0); `make ci` (0, ALL GREEN); the non-ASCII comparison against `origin/main`
- Result: C-001 to C-011 PASS
- New evidence: `cargo tree -p selahcue-scripture --no-default-features --features installed -e normal` lists 22 crates, none a network crate; `selahcue-app` and `selahcue-desktop` trees contain no `ureq`
- Decision: handoff to the orchestrator for the review pipeline (C-012 needs the PR; C-013 is the four reviewers)

### Iteration 6

- Target criterion: the review round on PR 188 (Cody, Shadow, Vera: approve with conditions; Quinn: pass with conditions), items A1 to A9 (must fix) and B10 to B14 (should fix); the C list stays deferred
- Hypothesis: every finding is a defect with a test that can fail, and the new tests must be shown to bite
- Change or investigation: row counts recorded in the receipt and checked at load and install; a drop guard in the only index constructor (`peak_live_indexes`, `live_indexes`); a streaming validation before any slot is made; a slot reserved under the state lock, the decode outside it, a per-code latch; the receipt re-read only when its length, mtime or inode changes and a damaged-file memory; stage-hash-validate outside the write lock with a cancellable wait; an unreadable receipt refused by install, download and remove, plus `repair_receipt`; `Bible::check`; one gzip member; 16 MiB inflate cap; stricter character refusal; URL redaction; the legacy download path removed; the relative data-directory override refused; docs and the PR text corrected. New files `receipt.rs` and `staging.rs` split out of `registry.rs`
- Verifier executed: a second mutation runner (66 mutants over registry, validate, catalog, download, url_policy, bible, receipt, staging and lib), each against the whole suite with `--features download`; then the survivors and hangs fixed and re-run; the gates of C-010
- Result: 66 mutants: 62 caught by a failing test, 3 caught only because the run hung, 1 survived. The survivor was `repair_receipt` adopting any file with a catalogue name (its decoy had the wrong size, which the size check refused first); the three hangs were a test that held the write lock outside its thread scope. Both test weaknesses fixed; the four re-run and caught by a failing test. Quinn's Q14 and the late-eviction mutants are red. The bounds mutant `(first, count)` is caught only by the new ASV gap sweep
- New evidence: a same-size damaged file is "available" but empty (now `Bible::check` says why); `ureq` inflates a `Content-Encoding: gzip` response, so the cap and digest run on the decoded stream (pinned by a test with a wrapped asset and a wrapped bomb); the real A1 assets still install under the stricter rules, with the same resident-set figures as before (13.7, 24.5 and 29.0 MB at caps 1, 3 and 4, debug build) and a live peak equal to the cap. Known gap: a mutant that keeps each file's compressed bytes beside its index (Vera's second) would pass, because the tests count indexes and not bytes
- Decision: handoff for re-review; C-013 stays PENDING

### Iteration 7

- Target criterion: the conditions of the confirmation review at head 368a131d (Cody approve with conditions, Vera approve, Shadow approve, Quinn pass with conditions; nothing blocking), kept to a small diff
- Hypothesis: each condition is one small change plus a test that fails without it
- Change or investigation: `repair_receipt` returns a readable receipt unchanged and writes nothing (it rebuilds only a missing or unreadable one); `LoadStage::InsideDecode` fires from inside the decode so a test can hold a decode mid-flight and show a resident read, a handle lookup and `installed()` are not blocked; tests for the inode, modification-time and length halves of the receipt stamp; the vanished-file lookup test under a deadline; `replace_file` sets a distinct modification time; the `Phase::Installing` callback documented as running under the write lock; `hold_writes_for_tests` and `set_load_hook_for_tests` compiled only with debug assertions (the two test files that use them say why they do not build with `--release`); contract C-003 reworded; the PR's stale mentions mapped to ClickUp tickets A3 17tnw2b2jg0, A4 17tnw2b2jg1, A5 17tnw2b2jg2, A6 17tnw2b2jg3, A7 17tnw2b2jqd
- Verifier executed: a third mutation run of the new tests only (8 mutants: F1, F1b, F2a, F2b, G2a, G2b, G2c, G3), then the gates of C-010
- Result: 8 of 8 caught by a failing test. F2a is Quinn's E5 (the state lock taken just after the old gate): the old test passed it, the new one fails. G3 (a per-code latch not released on a failed load) now fails the vanished-file test in 20 seconds where it hung; other existing tests that repeat a failing load still hang under that mutant, so the run was killed at its time limit
- New evidence: the library builds in release with the two seams gated (clippy -D warnings, no features, `installed` and `download`); no CI job runs scripture tests in release
- Decision: handoff; C-013 stays PENDING

## Risks and rollback

- Risks: the `Translation` enum shrinks from six to five variants, so any out-of-tree code naming `Ylt` stops compiling (none found in the repo); `is_downloadable` is removed (its only users were updated); the receipt-and-file replace is two renames, not one (a crash between them fails closed: the load checks the file digest against the receipt, and a test builds exactly that state); the receipt gained `verses_ot` and `verses_nt`, so a receipt without them is unreadable (nothing has shipped, so none exists)
- Rollback or recovery: revert the single PR; installed files in a user's data directory are inert without the registry code

## Pause and escalation conditions

- The LAN wire protocol, a bundled translation's behaviour or a shipped crate API would have to change beyond what the brief allows: stop and report
- Three materially different failed attempts at one criterion: report BLOCKED with the smallest unblocker

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2jfz-translation-registry.md`; `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <file>` (structural). The `--completion` form is not claimed: C-013 is open
- Validator result: structural PASS with both validators
- Independent verification result: round 1 done (Cody, Shadow, Vera approve with conditions; Quinn passes with conditions; nothing blocking); the conditions are fixed in iteration 6. Round 2 confirmed at 368a131d (Cody approve with conditions, Vera approve, Shadow approve, Quinn pass with conditions; nothing blocking); its remaining conditions are fixed in iteration 7 and the last look is the orchestrator's. GitHub Actions has not run on this branch (account billing block), so every result above is local evidence from one machine
- Terminal state: not VERIFIED_COMPLETE. The implementation criteria C-001 to C-012 are PASS; the ticket is in code review until C-013 clears
- Remaining failed or blocked criteria: C-013 (independent review)
- ClickUp final evidence comment: posted on 17tnw2b2jfz with the PR
