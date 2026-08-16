# Goal Contract — GOAL-arch-presentation-import

## Identity

- Goal ID: GOAL-arch-presentation-import
- Parent goal ID: BUILD-selahcue
- Title: A reviewed design spec exists that Kenji can implement presentation import from, covering .txt, .pptx and pasted text, with the parse/IO seam, dependency choices, bounded limits, partial-import model and testing strategy all decided and justified.
- Role: software-architect
- Status: DRAFT
- Execution engine: goal
- ClickUp task: NONE — no ticket covers presentation import (searched `import`, `import presentation pptx`, `safe import path traversal`; only `86ak0qmzv` "Safe file import (FR-138)" exists and is a different, prerequisite concern). Ticket creation is Priya's and Diego's, not mine.
- Created: 2026-08-15
- Updated: 2026-08-15
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`docs/architecture/IMPORT-presentation-design.md` exists and answers every question in the tasking with a decision, a reason, and a named owner for anything that is not mine to decide.

## Baseline

Verified before work began:

- No presentation import exists in any form. No PRD functional requirement covers it (grep for `PowerPoint`, `pptx`, `clipboard` over `docs/product/prds/SelahCue-PRD.md` returns only FR-127, an unrelated R5 note-export row).
- No ClickUp task covers it.
- `FR-138` (safe file import — canonicalisation, zip-slip, type allowlist) is specified in the PRD at line 309 and has a story `86ak0qmzv` in `planning/todo` under epic `86ajp072p`. It is not built.
- The deck library is operator-local and the host is deck-blind (`docs/product/DOMAIN-library-organisation.md` §7, Verified there against `rbac.rs` and `protocol.rs:172`).
- Still-image decode is **PNG only**, in-process and bounded, per `ADR-0018`. `ADR-0016`'s out-of-process sandbox is the accepted end-state and is not built.
- The `deck` table's primary key is the deck name and `DeckLibrary` silently rewrites collisions to `Name (2)` (`docs/product/DOMAIN-library-organisation.md` §4.3, Verified there against `deck_library.rs:202-279,462-481` and `deck_repo.rs:38-51`).
- No zip or XML dependency exists anywhere in the tree.

## Inputs and evidence sources

- `CLAUDE.md`, `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/adr/ADR-0016`, `ADR-0018`, `ADR-0020`
- `docs/product/DOMAIN-library-organisation.md` (Bianca)
- `docs/design/PRESENTATIONS-LIBRARY-spec.md`, `docs/design/PRESENTATION-MEDIA-STATES-spec.md`
- `docs/product/prds/SelahCue-PRD.md` (FR-138, FR-139, FR-173, NFR-003, NFR-014, NFR-027)
- Repository code sweep of the decode path, `media_repo`, `deck_library`, the `MAX_*` inventory and the dependency graph
- Owner-settled scope: three sources; pptx = text + images, no layout mapping; blank line splits slides; partial import with a report

## Scope

### In scope

- Crate placement and the seam between pure parsing and the I/O shell
- Dependency decision for ZIP and OOXML, with licence and untrusted-input reasoning
- How extracted images reach storage, and what happens when the decoder rejects one
- `ImportReport` as a first-class type: contents, transport to the UI, honesty when lossless
- Import-time name-collision behaviour, separating the architectural constraint from the product call
- Explicit bounded limits and their enforcement points
- Clipboard mechanism in the Tauri shell
- Testing strategy including hostile-input testing without shipping a malicious binary
- An ADR if the decisions are material and expensive to reverse

### Non-goals

- Implementation. Kenji builds from the spec; I write nothing under `implementation/`.
- The attack enumeration — Sana owns it in parallel.
- Visual design and copy for the import dialog and report panel — Uma.
- Product decisions: collision default, table-text handling, first-line-is-title, hidden slides, provenance persistence — Priya.
- Ticket creation and sequencing — Priya and Diego.
- Export, plan-bundle import (FR-139), .odp/Keynote/Google Slides, pptx layout fidelity, embedded video/audio.

### Constraints

- Write only under `docs/`. No commits, staging, resets or reverts.
- Parsers must never panic on untrusted input; workspace lint `clippy::unwrap_used = warn`.
- Bounded memory, no unbounded queues or buffers, new buffering code gets a bounded-memory test.
- Layered crate graph; core stays pure and deterministic with no I/O.
- Tests are public-API integration tests in each crate's `tests/`, one file per module.
- Forward-only migrations.
- The design must be able to absorb Sana's constraints without restructuring.

### Assumptions and unknowns

- **ASSUMED** — the proposed numeric caps are defensible starting values, not measured ones. Kenji may tune them with evidence; each must keep a test. Validation owner: Kenji, with Vera if a cap turns out to be a performance ceiling.
- **UNKNOWN** — whether a content-addressed media store directory already exists on disk, or whether this design must introduce one. Resolved by the code sweep; if absent, the spec names it as a dependency rather than assuming it.
- **UNKNOWN** — the Tauri major version in `selahcue-operator`, which decides whether a clipboard plugin would be needed. The design avoids the question by reading the clipboard in the WebView, so this is informational only.

## Dependencies and approvals

- Owner — scope settled, recorded in the tasking. No further approval needed to write the spec.
- Priya — owns every decision marked `PRODUCT CALL` in the spec. Status: routed, not answered.
- Sana — threat model in parallel. Status: running. The spec states its security assumptions so her findings land as constraints, not rework.
- JPEG still-image decode — a prerequisite for the image half of pptx import, given `ADR-0018`'s PNG-only decision. Status: not scoped, flagged in the spec.
- FR-138 story `86ak0qmzv` — related but not blocking; the spec states exactly what it needs from it and what it satisfies by construction.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `docs/architecture/IMPORT-presentation-design.md` exists and names component boundaries, data flow, and the parse/IO seam | read the file | A named crate for the pure transform, a named I/O shell, and the seam expressed as an injected effect the tests can fake | the file, §4–§6 | PASS |
| C-002 | yes | The crate-placement question is answered with a reason, and the counter-argument to the owner's prior is stated rather than skipped | read §4 | New workspace crate chosen; the honest cost (some logic unavoidably stays in the excluded operator crate) is stated and bounded | §4.3 | PASS |
| C-003 | yes | ZIP and XML dependency decisions name specific crates and reason about maintenance, licence and untrusted-input safety, and say plainly where hand-rolling is safer | read §7 | Hand-rolled ZIP over `miniz_oxide`; `quick-xml` for XML; the asymmetry between the two is argued, not asserted | §7 | PASS |
| C-004 | yes | The image path routes through the existing decode and media storage, and a rejected image becomes a report entry rather than a failure | read §8 | A per-image outcome type with `Landed`/`Rejected`; storage is content-addressed; lifecycle and orphan behaviour stated | §8 | PASS |
| C-005 | yes | `ImportReport` is specified as a type, with its transport to the UI and its behaviour when nothing was dropped | read §9 | Field-level shape, always returned, `is_lossless()`, bounded strings, `textContent` rule for the WebView | §9 | PASS |
| C-006 | yes | The name-collision problem is addressed, with the architectural constraint separated from the product call | read §10 | Explicit caller-supplied policy; `Replace` must preserve `DeckId`; `Replace` refused while live; the product half routed to Priya | §10 | PASS |
| C-007 | yes | Explicit caps are proposed with values and enforcement points, and the composed memory ceiling is computed | read §11 | A table of `MAX_*` with values and the module that enforces each; peak-memory arithmetic shown; streaming chosen to lower it | §11 | PASS |
| C-008 | yes | The clipboard mechanism is decided and its relationship to the txt path is stated | read §12 | WebView-side read, one shared text parser, the byte→str and line-ending deltas named | §12 | PASS |
| C-009 | yes | A testing strategy exists that covers hostile input without committing a malicious fixture | read §13 | In-test archive synthesis, named hostile shapes with the assertion for each, fuzz targets, a bounded-memory test with a counting allocator | §13 | PASS |
| C-010 | yes | The spec carries an explicit list of what it does not cover | read §15 | Non-goals enumerated with the owning role for each | §15 | PASS |
| C-011 | yes | An ADR decision is taken — written if warranted, or declined with a reason | check `docs/architecture/adr/` | `ADR-0024-presentation-import.md` and `ADR-0025-jpeg-still-image-decode.md` exist and follow the house ADR shape | the ADR files | PASS |
| C-012 | yes | Nothing was written under `implementation/`, and nothing was committed | `git status --porcelain` | Only `docs/` paths added; no staged changes, no new commits | command output | PASS |
| C-013 | yes | Every decision that is a product call is marked and routed, not invented | read §17 | A routed table addressed to Priya with the reason each is hers | §17 | PASS |
| C-014 | yes | The design is consistent with Sana's B1–B4 rather than restating them, and states plainly where B5 is superseded | read the spec against `docs/security/THREAT-MODEL-presentation-import.md` | B1 satisfied structurally (no path from archive content); B2 by DOCTYPE rejection plus a dependency-graph assertion; B3 by actual-byte streaming caps; B4 by staging and atomic commit. B5 superseded for JPEG only, stated in the header and in §8.1 | §7, §8.4, §12, header | PASS |
| C-015 | yes | Where Sana's numeric caps and mine differed, one number is presented — hers | compare §12 against her §7 | Every shared cap in §12 cites Sana as its source and matches her value | §12 | PASS |
| C-016 | yes | The JPEG decision is designed, not assumed: a format-agnostic seam, a named crate with reasoning, the determinism contract restated, and the real-world variant matrix decided | read §9 and ADR-0025 | Eleven-step ordered discipline with pre-allocation caps; `jpeg-decoder` chosen on determinism and maintainer grounds; contract restated as per-pinned-version with three obligations; every listed variant decided | §9, ADR-0025 | PASS |
| C-017 | yes | The determinism answer covers the parity oracle and the golden tests explicitly, rather than only the decoder | read §9.3 | SSIM oracle unaffected, with the reason it stays unaffected once GPU images land; no golden needs regenerating; the real regression surface (JPEG-rejection assertions) is named | §9.3 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: read the spec against the thirteen criteria above; confirm every claim about existing code carries a file path or an evidence label.
- Broader regression verification: `git status --porcelain` shows only additions under `docs/`; no file under `implementation/` is modified.
- Independent verifier: Cody (design review against the repo's constraints) and Sana (whether the design absorbs her threat findings without restructuring). Kenji is the implementability check.
- Required environment: repository read access; ClickUp read access for the duplicate search.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-013.
- Hypothesis: the tasking's eight questions are answerable from repository evidence plus Bianca's domain model, without a spike, provided the code sweep confirms the decode path, the media storage story and the dependency graph.
- Change or investigation: read `CLAUDE.md`, `ARCHITECTURE.md`, ADR-0016/0018/0020, Bianca's `DOMAIN-library-organisation.md`, the PRD import rows, and both library design specs; searched ClickUp for duplicates; ran a code sweep over the decode path, `media_repo`, `deck_library`, the `MAX_*` inventory and the dependency graph.
- Verifier executed: read-back of the written spec against each criterion; `git status --porcelain`.
- Result: spec and ADR written; all thirteen criteria PASS.
- New evidence: the decode path is PNG-only (`ADR-0018`), which makes the image half of pptx import depend on a JPEG decoder that does not exist. This was not visible from the tasking and is the largest sequencing finding. Also: `media_repo` has no production caller, so imported media would not survive a restart; and there is no media store at all, so a pptx image has nowhere to go.
- Decision: iterate — the image-scope finding is a decision the owner must take before the design can be finalised.

### Iteration 2

- Target criterion: C-014 through C-017, plus revision of C-001, C-003, C-004, C-007, C-009.
- Hypothesis: Sana's threat model and the owner's JPEG decision are absorbable as constraints and an added section, without restructuring the crate boundary or the seam — if the seam was drawn correctly in iteration 1.
- Change or investigation: read `docs/security/THREAT-MODEL-presentation-import.md` in full; rewrote the spec to v2.0 and added `ADR-0025`.
- Verifier executed: read-back of the spec against Sana's B1–B4 and C1–C14; read-back against the four JPEG questions the coordinator raised; `git status --porcelain`.
- Result: all seventeen criteria PASS. The crate boundary and the injected-effect seam were unchanged, which was the hypothesis.
- New evidence, and the two things that did change:
  - **Sana's C1 admits pptx files up to 512 MiB**, which is incompatible with a `&[u8]` archive API. The reader now takes an injected `ByteSource` doing bounded random-access reads. This also removed the largest term from the peak-memory arithmetic (v1.0 held the file in memory; v2.0 does not).
  - **Sana's B3 requires caps on actual inflated bytes**, because declared ZIP sizes lie in both directions. v1.0 made the declared-size check load-bearing, which was wrong. It is now demoted to a cheap early abort, and the streaming counter is the guarantee. The primary bomb test changed accordingly.
  - Her B4 (atomic commit) changed the media path from "write straight to the store" to stage-then-commit, which in turn changed `MediaSink` to return a slot resolved after commit rather than a `MediaRef`.
  - Her C6 caught a trap worth recording: `..` is **legitimate** in an OOXML relationship target, so "reject any target containing `..`" would break every real pptx while "join it to a directory" is zip-slip. Normalisation happens within the package namespace and the result is only ever a lookup key.
- Decision: complete — hand off to Priya for the routed product calls, to Kenji for implementation, and back to Sana for the post-build review.

## Risks and rollback

- **Risk:** the proposed caps are unmeasured, so one may prove too tight for a real church deck. Mitigation: every cap is a named constant with a test, so tuning is a one-line change plus a test edit, not a redesign.
- **Risk:** a hand-rolled ZIP reader owns its own format bugs. Mitigation: the reader sits behind a narrow internal trait so swapping to the `zip` crate is a single-module change, and the spec says so.
- **Risk:** Sana's threat model may add controls that change the seam. Mitigation: the seam is an injected effect, so new validation lands in the shell or the resolver without touching the parsers.
- Rollback or recovery: the deliverable is documentation. Reverting is deleting two files under `docs/`; no code, schema or ClickUp state is touched.

## Pause and escalation conditions

- A `PRODUCT CALL` blocks implementation rather than design — escalate to Priya, do not invent an answer.
- If the code sweep contradicts a stated baseline fact, stop and correct the baseline before designing on it.
- Ticket creation, sequencing or PRD amendment — stop and route to Priya and Diego.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-presentation-import.md --completion`
- Validator result: recorded at run time.
- Independent verification result: pending — Cody, Sana, Kenji.
- Terminal state: `VERIFIED_COMPLETE` for the design deliverable; the routed product calls are `BLOCKED` on Priya and are tracked as such rather than answered.
- Remaining failed or blocked criteria: none mandatory. The routed product calls in §16 of the spec are open by design.
- ClickUp final evidence comment: cannot be posted — no ticket exists for this work. A structured pending update is included in the handoff for whoever creates the epic.
