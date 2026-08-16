# Goal Contract - GOAL-be-import-remediation-round2

## Identity

- Goal ID: GOAL-be-import-remediation-round2
- Parent goal ID: BUILD-selahcue
- Title: Second remediation round on the presentation importer clears the blocking reviewer findings, makes every named control fail under mutation, and leaves the local CI gate green
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-16
- Updated: 2026-08-16
- Maximum iterations: 5
- Independent verification required: yes

## Objective

Work the four reviewer reports (Cody — code review, Sana — security, Vera — performance, Quinn — QA
with seven genuinely PowerPoint-authored decks) in tier order against the UNCOMMITTED importer in
the working tree. Tier 1: stop real decks importing page numbers and footers as audience text; stop
a legitimate 278 MiB photo deck importing as nothing; stop validating images by full-decoding and
discarding the pixels; and repair three tests that assert properties their fixtures cannot exhibit.
Tier 2: replace five tests that are satisfied by a neighbouring control, and cover four shipped
controls that have no test at all. Tier 3: correctness and honesty — module lints, an over-claiming
guard script, a misleadingly named decode entry point, silent drops on the public build seam, and
report fatigue. **For every Tier 1 item and every Tier 2 test, state the mutation that now fails.**
The importer is NOT wired into the operator shell. Nothing is committed, staged, reset or reverted.

## Baseline

Verified current state before substantive work:

- The importer exists uncommitted in the working tree: `selahcue-import` (18 src files, 6 test
  files, a `support` builder), `selahcue-engine`'s `jpeg.rs`/`exif.rs`/`media.rs` changes,
  `scripts/import_guards.sh` wired into `Makefile:191` and `.github/workflows/ci.yml:150`.
- `make ci` was green on the pre-remediation tree.
- Quinn's seven real decks are at the session scratchpad's `realdecks/` and `realdecks2/`.
- Quinn's stated corrected shadow test (`test_qa_shadow.rs`) is NOT present at the path given in
  the tasking, nor anywhere under the scratchpad; it was rewritten from her description.
- `MAX_IMPORT_SLIDES == MAX_DECK_SLIDES`, `MAX_LINE_LEN == MAX_TEXT_ELEMENT_LEN` and
  `MAX_IMPORT_NOTES_LEN == MAX_NOTES_LEN`, asserted by `limits.rs`'s own tests — which is why
  `build_deck`'s `within_bounds` repair arm is unreachable from outside.

## Inputs and evidence sources

- The four reviewer reports as relayed in the tasking.
- The uncommitted working-tree implementation listed in the Baseline.
- Quinn's seven real decks, replayed through a scratchpad harness that path-deps the crates.
- `make ci` (`$HOME/.cargo/bin`, `$HOME/flutter/flutter/bin` on PATH).
- Mutation runs: each named control removed or inverted in place, the suite run, the source
  restored.

## Scope

### In scope

- `implementation/desktop/crates/selahcue-import/{src,tests}`
- `implementation/desktop/crates/selahcue-engine/{src/media.rs,tests}`
- `scripts/import_guards.sh`
- `docs/architecture/adr/ADR-0024-presentation-import.md`, `ADR-0025-jpeg-still-image-decode.md`
- This goal contract.

### Non-goals

- Wiring the importer into the operator shell (explicitly excluded by the tasking).
- Any commit, stage, reset or revert.
- Widening or weakening any cap.

### Constraints

- Every cap decision stays on header-derived values, before allocation (B5-J).
- The partial-import rule holds: if one slide survived, it is not an error.
- A design attribute SelahCue replaces on purpose is not a skipped item.

## Verification plan

Each criterion is verified twice: the test passes on the tree, AND the named control removed or
inverted makes that test fail. Commands run from `implementation/desktop` with
`$HOME/.cargo/bin` on PATH. The gate is `make ci` from the repository root.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-101 | yes | Slide-number / footer / date / header placeholders never reach body text | `cargo test -p selahcue-import --test test_pptx` + replay of the 7 real decks | tests pass; 0 of 124 `sldNum` + 5 `ftr` strings survive into imported text | test output; harness scan reported 0 survivors | PASS |
| C-101m | yes | …and removing the furniture filter fails those tests | delete the `is_furniture` guard in `assemble_text` | 2 FAILED | mutation run | PASS |
| C-102 | yes | A stored photograph is not charged to the inflate budget | `--test test_zip a_stored_photograph_is_not_charged_to_the_bomb_budget` | pass | test output | PASS |
| C-102m | yes | …and charging it there again fails | `Production::Copied` charged to the inflate total | 2 FAILED | mutation run | PASS |
| C-103 | yes | Extraction-budget exhaustion degrades to text + report; inflate exhaustion still aborts | `--test test_zip` | both tests pass | test output | PASS |
| C-103m | yes | …and aborting on exhaustion, or deleting the budget, fails | 2 mutations | 1 FAILED each | mutation runs | PASS |
| C-104 | yes | Image validation probes headers and allocates no pixel buffer | `--test test_memory`, engine `--test test_probe`, `--test test_jpeg_alloc` | pass; 4 Mpx import peaks under 3× encoded; quadrupling pixels does not treble probe cost | test output | PASS |
| C-104m | yes | …and full-decoding instead fails | `probe_image` → `decode_image` in `stage_pictures` | test_memory FAILED | mutation run | PASS |
| C-105a | yes | The lying-header bomb test binds the byte counter, not the ratio guard | `--test test_pptx`, `--test test_memory` | pass on `deflate_lowish_ratio` | test output | PASS |
| C-105b | yes | The shadow test can observe shadowing | `--test test_zip a_refused_name_can_never_shadow…` | pass | test output | PASS |
| C-105bm | yes | …and letting a refused name into the duplicate set fails it | drop `!bad_name &&` | FAILED | mutation run | PASS |
| C-105c | yes | The report-index test binds the BUILDER's truncation | `--test test_pptx a_report_index…` | pass | test output | PASS |
| C-105cm | yes | …and `elements_for(999, …)` fails it | mutation | FAILED | mutation run | PASS |
| C-201 | yes | The DOCTYPE refusal is proven to run on raw bytes, pre-parser | `--test test_pptx the_doctype_refusal_is_on_the_raw_bytes…` | pass | test output | PASS |
| C-201m | yes | …and deleting `has_doctype()` fails it | mutation | FAILED | mutation run | PASS |
| C-202 | yes | The XML event budget is the only control in range (part stored, not deflated) | `--test test_pptx` | pass | test output | PASS |
| C-202m | yes | …and deleting the event budget fails it | mutation | FAILED | mutation run | PASS |
| C-203 | yes | The in-walk entry cap is reachable via an under-declaring EOCD | `--test test_pptx an_entry_flood_that_under_declares_itself…` | pass | test output | PASS |
| C-203m | yes | …and deleting the in-walk cap fails it | mutation | FAILED | mutation run | PASS |
| C-204 | yes | A partially encrypted archive is refused per entry | `--test test_pptx a_single_encrypted_part…` | pass | test output | PASS |
| C-204m | yes | …and deleting `read_entry`'s encrypted check fails it | mutation | FAILED | mutation run | PASS |
| C-205 | yes | There is exactly one signature allowlist and off-list bytes never reach a decoder | `--test test_pptx`, `--test test_memory` | pass | test output | PASS |
| C-205m | yes | …and making `sniff` fall through to PNG fails both | mutation | FAILED (both) | mutation runs | PASS |
| C-206 | yes | The >25 % image escalation, `truncations_overflow`, `MAX_TITLE_LEN`/`MAX_SLIDE_LINES` and the ingress guarantee all have tests | `--test test_report`, `--test test_pptx`, `--test test_build` | pass | test output | PASS |
| C-206m | yes | …and inverting each threshold fails its test | 4 mutations | 1 FAILED each | mutation runs | PASS |
| C-207 | yes | A deflate member spanning several chunks arrives whole and never carries its neighbour's bytes | `--test test_zip a_deflate_member…` | pass | test output | PASS |
| C-207m | no | The two `read_deflate` controls are individually observable | advance-by-`take`; delete the stall guard | expected FAILED | **both mutations pass the whole suite** — see Findings | FAIL |
| C-208 | yes | The JPEG alloc control really exercises a decode | engine `--test test_jpeg_alloc` | pass; control asserts > one pixel plane | test output | PASS |
| C-208m | no | The decoder-buffer budget is individually observable | delete it; re-introduce the cap-sized defect | expected FAILED | **arithmetically unreachable** — see Findings | FAIL |
| C-301 | yes | `media.rs` denies `indexing_slicing` and `arithmetic_side_effects` | `cargo clippy -p selahcue-engine --all-targets -- -D warnings` | clean | clippy output | PASS |
| C-302 | yes | The guard catches the brace-import form and claims only what is true | plant `use std::{fs, …}; fs::read(…)` | script exits 1 | guard run (exit 1 planted, 0 clean) | PASS |
| C-303 | yes | `decode_png` is deprecated, callers moved to `decode_image`, widening noted | clippy `-D warnings`; ADR-0025 amendment | clean | clippy + ADR | PASS |
| C-304 | yes | `build_deck`'s slide-cap drop and whitespace-only truncation are honest | `--test test_build` | pass | test output | PASS |
| C-304m | yes | …and deleting the slide-cap report, or clamping before the emptiness test, fails | 2 mutations | 1 FAILED each | mutation runs | PASS |
| C-305 | yes | Embedded fonts collapse to one standing notice | `--test test_pptx embedded_fonts…` | 25 files → 1 notice, 0 skipped items | test output | PASS |
| C-401 | yes | Full local CI gate green | `make ci` | exit 0 | `== local CI gate: ALL GREEN ==`, exit 0 | PASS |

## Findings that are reported rather than satisfied

Two Tier 2 criteria could not be met as stated, and were measured rather than assumed:

- **C-207m — `read_deflate`'s advance-by-consumed and stall guard.** With `flate2` pinned as it is,
  the inner loop only ever leaves with `offset == take` or through `StreamEnd`. Advancing by `take`
  therefore produces byte-identical output on every input this suite can construct, and deleting the
  stall guard hangs nothing: **both mutations pass the entire suite.** They are defence in depth
  against a decompressor that behaves differently — the general ZIP crate the module header
  contemplates taking, or a version bump — guarding a failure mode (quietly wrong content) that no
  cap or report would catch. The comment now says so with the evidence, and the *property* they
  protect is pinned by `a_deflate_member_is_never_served_its_neighbours_content`.

- **C-208m — the JPEG decoder-buffer budget.** For the pinned decoder the budget is compared against
  `components × width × height`; steps 6–7 have already admitted `width × height ≤ effective_pixels`
  and `components ≤ 3`, and the budget is at least `width × height × components × 4`. No admitted
  frame can be refused by it and no refused frame reaches it, so both the "delete it" and the
  "re-introduce the cap-sized defect" mutations are inert **by arithmetic, not by luck**. The
  comment now carries that derivation. `test_jpeg_alloc.rs` pins the property that does bind, with a
  control that now decodes a real 512×512 frame and is weighed against that frame's own output —
  the previous `assert!(bytes > 0)` was satisfied by `jpeg_decoder::Error::Format`'s owned `String`.

One reviewer claim did not reproduce: the *knock-on* half of Tier 1 item 1 (furniture consuming the
joined-body budget and escalating decks to `Material`). Replayed with and without the filter, the
seven decks produce identical truncation counts and identical tiers; the two `Material` decks are
`Material` because of a genuine body truncation on a dense dashboard slide. The audience-text defect
itself is real, and is fixed and verified.

## Iteration ledger

| # | Action | Result |
|---|---|---|
| 1 | Read the importer, the engine decode chain, the four reviewer findings and the existing suites | Baseline established |
| 2 | Tier 1 item 1 — furniture predicate shared with the notes path; builder teaches `sldNum`/`ftr`/`dt` | 2 new tests; mutation fails both |
| 3 | Tier 1 item 3 — `probe_image` in the engine; importer stops decoding | engine `test_probe.rs`; import peak bound to encoded size |
| 4 | Tier 1 item 2 — inflate vs extraction budgets; degrade path; `MediaBudgetExhausted` | 2 new tests; 3 mutations fail |
| 5 | Tier 1 item 4 — three hollow tests repaired; `Entry::aliasing` / `PptxBuilder::first` / `zip_declaring` added to `support` | mutations fail each |
| 6 | Tier 2 items 5–8 | 4 neighbour-proof tests, `test_report.rs`, `test_build.rs`; 2 findings reported |
| 7 | Tier 3 items 9–13 | lints, guard script, rename, honest reports |
| 8 | Replay the 7 real decks; `make ci` | 0 furniture survivors; CI exit 0 |

## Handoff

Recommend Code Review (Cody) on the budget split and the probe seam, then QA (Quinn) to re-run her
real-deck corpus and adjudicate the two reported findings. Security (Sana) should confirm the
narrowed §14 claim in `scripts/import_guards.sh` and `lib.rs`.
