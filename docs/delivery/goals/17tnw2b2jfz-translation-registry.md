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
- `implementation/desktop/Cargo.lock` (the scripture crate gains `serde_json`, which is already in the lock)
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
- **Unknown**: gzip bytes can differ across zlib builds, so the pinned digest must come from the artefact actually published (A7).

## Dependencies and approvals

- A1 (PR 181) defines the catalogue schema; this change reads schema 1 and does not depend on A1's merge.
- A7 sets the final URL template and the real digests; the template is a single function so A7 can change it.
- The brief says to stop and report if a new dependency is needed. `serde_json` is the one deviation and is reported, not hidden.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Installing and reading N+1 translations never keeps more than N decoded indexes resident (N defaults to 3), the least recently used one is the one evicted, and removing the cap makes the test fail | `cargo test -p selahcue-scripture --features installed --test test_registry_bounded` and the mutation list in the ledger | exit 0; each listed mutation turns it red | Iteration ledger | PENDING |
| C-002 | yes | A re-downloaded translation is served from the new file without a restart | `--test test_installed` (re-install case) | exit 0 | Iteration ledger | PENDING |
| C-003 | yes | A decompression bomb, a wrong-hash file, a truncated file, a substituted file, an oversized file, a malformed row, a book outside 1 to 66, a wrong verse count, markup residue and out-of-order rows are each rejected and leave no installed file, no receipt entry and no staging file; a catalogue `file_name` with a path component is refused | `--test test_validate`, `--test test_installed`, `--test test_catalog` | exit 0 | Iteration ledger | PENDING |
| C-004 | yes | An interrupted install (`.part` left behind) is cleaned up and never listed as installed; a planted symlink is never followed and a file this call did not create is never removed | `--test test_installed` | exit 0 | Iteration ledger | PENDING |
| C-005 | yes | A build with only `installed` has no HTTP client or TLS crate in its dependency tree, and `make ci` guards it | `cargo tree -p selahcue-scripture --no-default-features --features installed -e normal`; `sh scripts/import_guards.sh` | no `ureq`, `rustls`, `hyper`, `reqwest`; guard prints OK | Iteration ledger | PENDING |
| C-006 | yes | The embedded catalogue parses and is validated (unknown schema, duplicate code, code colliding with a bundled one, bad file name, bad digest all refused); an entry with no base URL reports "not published yet" and makes no request; a `legal_review: pending` entry is not offered and the download function refuses it | `--test test_catalog`, `--test test_download` | exit 0 | Iteration ledger | PENDING |
| C-007 | yes | The download function refuses a non-HTTPS start URL and a redirect to a non-HTTPS URL (loopback http only through an explicit test constructor), reports progress, honours cancel, and needs a `TermsAcceptance` argument | `cargo test -p selahcue-scripture --features download --test test_download` | exit 0 | Iteration ledger | PENDING |
| C-008 | yes | Bundled behaviour is unchanged: the five wire codes, `quote_match`, the cross-language LAN fixtures, every existing scripture test (YLT-specific ones removed) and the app and operator consumers | `cargo test -p selahcue-scripture` (3 feature sets), `cargo test -p selahcue-app --features server`, `cargo test -p selahcue-lan --features server`, `cargo check --manifest-path .../selahcue-operator/Cargo.toml` | all exit 0 | Iteration ledger | PENDING |
| C-009 | yes | The handle serves an installed code through the same lookups as a bundled one (verses, text, search, chapter, adjacent chapter, exists, bounds) with the same answers on the same data | `--test test_bible` | exit 0 | Iteration ledger | PENDING |
| C-010 | yes | Gates: fmt, clippy (default, `download`, `installed`), import guards, `cargo deny`, `cargo audit`, and `make ci` once at the end | commands in the verification plan | all exit 0, real output recorded | Iteration ledger | PENDING |
| C-011 | yes | Source files are ASCII-only except where they were not before | `LC_ALL=C grep -nP '[^\x00-\x7F]'` over touched files, compared with `origin/main` | no new non-ASCII bytes | Iteration ledger | PENDING |
| C-012 | yes | The branch is up to date and a Draft PR is open against `main` | `git rev-list --count HEAD..origin/main`; `gh pr view` | `0`; PR is Draft, base `main` | PR link on ClickUp | PENDING |
| C-013 | yes | Independent review passed: code (Cody), security (Shadow), QA (Quinn) and performance (Vera, for the memory cap) each reviewed at the head SHA and every blocking finding is fixed and re-checked | review round report page linked on the PR | each verdict recorded, zero open blocking findings | report page URL | PENDING |

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
- Verifier executed: none yet
- Result: design recorded in the PR description
- New evidence: ureq 3 checks `https_only` on every redirect hop; the real A1 BSB asset is on disk for a one-off positive control
- Decision: iterate

## Risks and rollback

- Risks: the `Translation` enum shrinks from six to five variants, so any out-of-tree code naming `Ylt` stops compiling (none found in the repo); `is_downloadable` is removed (its only users were updated); the receipt-and-file replace is two renames, not one (a crash between them fails closed: the load checks the file digest against the receipt)
- Rollback or recovery: revert the single PR; installed files in a user's data directory are inert without the registry code

## Pause and escalation conditions

- The LAN wire protocol, a bundled translation's behaviour or a shipped crate API would have to change beyond what the brief allows: stop and report
- Three materially different failed attempts at one criterion: report BLOCKED with the smallest unblocker

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2jfz-translation-registry.md`; `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <file> --completion`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: all, at the time of writing
- ClickUp final evidence comment: pending
