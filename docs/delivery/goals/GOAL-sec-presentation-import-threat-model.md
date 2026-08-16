# Goal Contract - GOAL-sec-presentation-import-threat-model

## Identity

- Goal ID: GOAL-sec-presentation-import-threat-model
- Parent goal ID: BUILD-selahcue
- Title: Pre-build threat model for the presentation import feature (.txt / .pptx / clipboard) is ready for gate review
- Role: security-reviewer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-15
- Updated: 2026-08-15 (closeout)
- Maximum iterations: 5
- Independent verification required: yes

## Objective

Produce a pre-build secure design review (threat model) for the owner-approved presentation-import feature — .txt file, .pptx file (text + speaker notes + embedded images, partial-import model), and clipboard paste — as `docs/security/THREAT-MODEL-presentation-import.md`, containing a concrete per-source attack-surface enumeration, product-realistic ranked risks, a testable constraint list for the implementer, hostile-case test construction guidance without committed malicious fixtures, explicit build blockers, and explicit residual risks for owner acceptance. No implementation code is written or modified.

## Baseline

Verified current state before substantive work:

- Nothing of the import feature exists in `implementation/`; there is no diff to review. This is design-time review only.
- `docs/security/THREAT-MODEL-presentation-import.md` does not exist. Existing security artefacts: `docs/security/reviews/threat-model-draft.md` (T11/T12 cover import/decoder classes at design level), `ADMIN-LICENSING-THREAT-MODEL.md`, `ADMIN-API-FOUNDATION-SECURITY-REVIEW.md`.
- Deck library is operator-local (`implementation/desktop/crates/selahcue-operator/src/deck_library.rs`), persisted BY NAME via `deck_repo` with "(n)" collision suffixing; DB writes are parameterized (rusqlite).
- Deck/slide bounds already exist in `selahcue-present`: `MAX_DECK_SLIDES=500`, `MAX_NOTES_LEN=4000`, `MAX_ELEMENTS=64`, `MAX_TEXT_ELEMENT_LEN=2000`.
- Still-image decode is the ADR-0018 bounded IN-PROCESS pure-Rust PNG-only path (`selahcue-engine/src/media.rs`: PNG signature allowlist, 64 MiB encoded cap, 40 MP / dimension caps enforced before allocation, Result-based, panic-contained, placeholder on failure). The ADR-0016 out-of-process sandbox is the deferred end-state, not shipped.
- The output window (`selahcue-output`, `selahcue-desktop`) is a separate process from the Tauri operator console; the operator webview renders untrusted strings via `textContent` in audited spots and uses `innerHTML` for structural rebuilds (`dist/app.js`).
- Workspace rules: parsers never panic on untrusted input (`clippy::unwrap_used = warn`), bounded memory with bounded-memory tests, never-blank live output (NFR-024), FR-138 safe import and FR-173 bomb defense are PRD requirements.
- ClickUp MCP tools are not available in this session; per precedent (GOAL-sec-admin-api-foundation) pending ClickUp update text is recorded in this contract.

## Inputs and evidence sources

- Task assignment from the coordinating agent (owner-approved feature scope: .txt / .pptx text+notes+images / clipboard; partial-import model).
- `CLAUDE.md`, `docs/architecture/ARCHITECTURE.md`, `docs/architecture/adr/ADR-0016-decode-isolation-sandbox.md`, `docs/architecture/adr/ADR-0018-in-process-still-image-decode.md`
- `docs/security/reviews/threat-model-draft.md` (T11, T12, T20)
- `implementation/desktop/crates/selahcue-operator/src/deck_library.rs`, `implementation/desktop/crates/selahcue-data/src/media_repo.rs`, `implementation/desktop/crates/selahcue-engine/src/media.rs`, `implementation/desktop/crates/selahcue-present/src/{deck.rs,theme.rs,compose.rs}`, `implementation/desktop/crates/selahcue-operator/dist/app.js`
- `.claude/team/` operating contract documents.

## Scope

### In scope

- Threat model document `docs/security/THREAT-MODEL-presentation-import.md`: per-source surface enumeration (confirm or dismiss each named class with reasoning), clipboard-specific risks, live-service isolation and failure-mode requirements, ranked risks with product-realistic severity, a numbered testable constraint list, hostile-case test construction guidance, build blockers, and residual risks for owner acceptance.
- Read-only inspection of existing code as evidence for integration constraints.

### Non-goals

- No implementation, no changes under `implementation/`, no git staging/commit/reset.
- No dependency (crate) selection — security-critical dependency PROPERTIES are stated as constraints; component boundaries and crate choice belong to the architect (Aria).
- No exploit execution, fuzzing runs, or malicious-fixture creation in this goal.
- No risk acceptance on behalf of the owner.

### Constraints

- Write only under `docs/`.
- Severity must reflect a single-operator offline desktop deployment, not a multi-tenant server model.
- Proportionate control count: ranked, with an explicit load-bearing blocker subset.
- Label material claims Verified / Inferred / Assumed / Unknown.

### Assumptions and unknowns

- ASSUMED: import runs in the operator (Tauri) process, not the output process, because the deck library is operator-local. Owner: Architect (Aria) — the threat model states isolation requirements either way.
- ASSUMED: the partial-import model (import what is representable, report drops) is settled product scope. Owner: Product.
- UNKNOWN: which zip/XML crates Aria selects — constraints are written as testable properties independent of crate choice.

## Dependencies and approvals

- Owner-approved feature scope: satisfied (stated in the assignment).
- Aria's parallel architecture: not a dependency for this document; constraints are inputs to it.
- ClickUp write path: unavailable in this session; pending update text recorded below.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Goal Contract validates before substantive work | `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-threat-model.md` | Exit 0 | Validator output in session (PASS, 6 criteria) | PASS |
| C-002 | yes | Threat model exists at the requested path and enumerates the attack surface per source, explicitly confirming or dismissing every class named in the assignment (zip-slip, bombs, quines, entity expansion, XXE/external fetch, malformed OOXML, image decoders, name/metadata injection, symlink/hardlink, absolute paths, member counts, slide/element exhaustion, clipboard classes) | Document review against the assignment's checklist | Every named class appears with confirm/dismiss reasoning grounded in this codebase | `docs/security/THREAT-MODEL-presentation-import.md` | PASS |
| C-003 | yes | Live-service isolation requirements and failure modes are specified concretely (process/thread placement, atomic commit, cancellation/timeout, panic containment, output-path independence) | Document review | A dedicated section states required isolation and the exact required failure mode while live | `docs/security/THREAT-MODEL-presentation-import.md` | PASS |
| C-004 | yes | Constraint list is concrete and testable (numbered, with limits and enforcement points), ranked, with an explicit blocker subset and residual risks for owner acceptance | Document review | Each constraint names a limit/behaviour and how it is verified; blockers are separated from required and recommended items | `docs/security/THREAT-MODEL-presentation-import.md` | PASS |
| C-005 | yes | Hostile-case testing guidance shows how to construct adversarial inputs programmatically with no malicious fixtures committed | Document review | Concrete in-test construction techniques for each hostile class | `docs/security/THREAT-MODEL-presentation-import.md` | PASS |
| C-006 | yes | Contract validates at completion and no `implementation/` file is touched | Validator + `git status --porcelain -- implementation/` compared to session start | Exit 0; no new implementation changes attributable to this goal | Validator + git status output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: document review against the assignment's explicit class checklist; goal contract validator before and after.
- Broader regression verification: `git status --porcelain -- implementation/` unchanged relative to session start (pre-existing dirty files only).
- Independent verifier: the coordinating agent / architect (Aria) consume the constraint list; the eventual implementation review (post-build security review) independently verifies each constraint against code — this document is design-time input, not a completion claim for the feature.
- Required environment: local repository, read-only for `implementation/`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: A structurally valid contract can be authored from the assignment plus verified repo evidence.
- Change or investigation: Read skill + team contracts, CLAUDE.md, ARCHITECTURE.md, threat-model-draft.md, ADR-0016/0018, deck_library.rs, media_repo.rs, engine media.rs, present bounds, app.js rendering discipline; authored this contract.
- Verifier executed: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-threat-model.md`
- Result: C-001 PASS — `GOAL CONTRACT VALIDATION: PASS` (6 criteria, 6 mandatory).
- New evidence: validator output in session; baseline facts verified in code (deck bounds, decode limits, process split, textContent discipline).
- Decision: iterate

### Iteration 2

- Target criterion: C-002, C-003, C-004, C-005
- Hypothesis: A per-source surface enumeration grounded in the verified integration points (deck bounds, ADR-0018 decode seam, operator/output process split, name-PK persistence, webview sink discipline) yields a concrete, proportionate constraint set with a defensible blocker subset.
- Change or investigation: Authored `docs/security/THREAT-MODEL-presentation-import.md`: trust-boundary diagram; per-source enumeration confirming/dismissing every assigned class (T1.x txt, T2.1-T2.20 pptx archive/XML/media/metadata, T3.x clipboard); ranked risks R1-R8 with offline-desktop severity; live-isolation requirements §6; constraint list §7 (blockers B1-B5, required C1-C14, recommended R1-R3); fixture-free hostile-case test construction §8; residual risks RR1-RR6 §9; verdict §10. Corrected the brief's premise: the existing image decode is ADR-0018 bounded IN-PROCESS decode, not the ADR-0016 sandbox.
- Verifier executed: grep coverage check for every class named in the assignment (zip-slip, traversal, ratio/absolute bombs, quines, billion laughs/entity expansion, XXE/external fetch + offline-first, malformed OOXML panic/allocation, image decoder, filename/metadata injection, symlink/hardlink, absolute paths, member counts, slide/element exhaustion, clipboard flavors, bidi/control/homoglyph) — all present with confirm/dismiss verdicts; document review against C-003/C-004/C-005 wording.
- Result: C-002 PASS, C-003 PASS (§6 states placement, atomicity, cancel/timeout, typed-failure-only, budget composition), C-004 PASS (§7 numbered with limits + enforcement points + per-constraint tests; B/C/R ranking; §9 residual table with owner column), C-005 PASS (§8 gives in-test construction for every hostile class, incl. hand-crafted zip records, lying-header patching, generated bombs, DOCTYPE payloads, dependency-graph network assertion, catch_unwind battery, headless webview inertness check).
- New evidence: `docs/security/THREAT-MODEL-presentation-import.md` (354 lines); cross-reference renumbering applied and verified stale-free.
- Decision: iterate

### Iteration 3

- Target criterion: C-006
- Hypothesis: Final validators pass and no implementation file was touched by this goal.
- Change or investigation: Re-ran the contract validator with `--require-complete`; ran `git status --porcelain` — only three new untracked docs exist (this contract, the threat model, and Aria's concurrent `GOAL-arch-presentation-import.md`); `implementation/` is clean (the owner committed the pre-existing WIP mid-session, consistent with repo history).
- Verifier executed: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-threat-model.md --require-complete`; `git status --porcelain -- implementation/`
- Result: C-006 PASS.
- New evidence: validator + git output in session.
- Decision: gate-review

### Iteration 4

- Target criterion: C-002, C-004 (scoped revision on coordinator direction — owner decision changed the feature)
- Hypothesis: The owner's decision to add JPEG decode to `selahcue-engine` within this work can be absorbed as an in-place revision of B5 (plus dependent sections) without weakening any criterion or redoing the model.
- Change or investigation: Applied **Revision 1.1** to `docs/security/THREAT-MODEL-presentation-import.md` in place with a revision-history block preserving the 1.0 audit trail. Content: (1) B5 revised — supported formats become PNG + B5-J-conforming JPEG; new **B5-J admission profile**: SOF0/SOF1/SOF2 only; dimension caps enforced at SOF parse before any pixel/coefficient allocation; `height==0`/DNL and second-SOF rejected; amplification bounded by the pixel cap (40 MP baseline/extended, 24 MP progressive) not a ratio; decode-time working set budgeted including progressive coefficient planes (~W×H×components×2 bytes, worst case ~240 MiB inside the §6.6 budget); 8-bit grayscale/YCbCr only with {1×1,1×2,2×1,2×2} sampling; metadata length-skipped never parsed (no EXIF orientation, no ICC, no thumbnails); PNG-equivalent failure semantics. Refusal list on risk grounds: arithmetic coding, lossless/hierarchical, 12/16-bit, CMYK/YCCK, DNL, non-standard sampling, multi-SOF. (2) JPEG decoder **crate constraint** added as the one security-critical dependency gate: pure-Rust (no libjpeg-family FFI), unsafe/SIMD disabled or absent (also protects NFR-014 byte-parity), caller-side pre-allocation limit enforcement (or importer-side SOF pre-parse), RustSec-reviewed/pinned/SBOM-covered. (3) §8.4 hostile-JPEG byte-patch battery (fixture-free) incl. cross-platform byte-identity determinism assertion. (4) R6 likelihood raised to Low-Medium; RR1 revised to conditional, time-bounded acceptance: ADR-0016 worker moves from "re-prioritise" to scheduled-with-committed-milestone, and if no crate meets the constraint, JPEG-in-process is NOT accepted (feature ships PNG-only until the worker). (5) RR2 wording, R3 recommendation, §1/§3.3 annotations, verdict note.
- Verifier executed: document review of the revised sections against the coordinator's four questions; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-threat-model.md --require-complete`; `git status --porcelain -- implementation/` (clean).
- Result: C-002 and C-004 remain PASS with the revised content; no criterion weakened; all four coordinator questions answered in-document. C-006 re-verified (docs-only change).
- New evidence: Revision 1.1 in `docs/security/THREAT-MODEL-presentation-import.md` (now 446 lines, revision history at top).
- Decision: gate-review

## Risks and rollback

- Risks: constraints could be over-scoped for an offline desktop product (usability cost) or under-scoped for the internet-download deck story. Mitigation: explicit ranking, blocker subset, and residual-risk section for the owner.
- Risks: parallel architecture (Aria) may place the importer differently than assumed. Mitigation: isolation requirements are stated as properties, not component picks.
- Rollback or recovery: docs-only; the document can be revised without runtime impact.

## Pause and escalation conditions

- Pause if the review would require executing untrusted files, adding fixtures, or touching `implementation/`.
- Escalate to Product/Owner: partial-import UX decisions, residual-risk acceptance, ADR-0016 re-prioritisation.
- Escalate to Architect: importer process placement and dependency selection.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-presentation-import-threat-model.md --require-complete`
- Validator result: PASS.
- Independent verification result: This design-time review is itself the independent security input to the build; the constraints B1-B5/C1-C14 will be independently re-verified against code at the post-build security review (which is the required independent check for the feature). Residual-risk acceptance (RR1-RR6) is reserved to the product owner.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: none for this design-review goal. The feature itself is Not Assessed (nothing built).
- ClickUp final evidence comment: PENDING (ClickUp MCP unavailable this session; do not create a shadow backlog — post this to Build Control `86ajnx548` when the connection is available). Pending text: `Security pre-build review complete: GOAL-sec-presentation-import-threat-model reached GATE_REVIEW. Deliverable: docs/security/THREAT-MODEL-presentation-import.md — design-time threat model for presentation import (.txt/.pptx text+notes+images/clipboard, partial-import model). Five build blockers (B1 no paths from archive content; B2 no DTD/no network; B3 streaming inflate caps on actual bytes; B4 live isolation + atomic commit + contained failure; B5 images only via the existing bounded decode seam), 14 required controls with limits and per-control tests, fixture-free hostile-case test construction, 6 residual risks for owner acceptance (incl. ADR-0016 re-prioritisation). Corrected premise: image decode today is ADR-0018 bounded in-process, not sandboxed. No implementation changes. Verdict: Pass as design constraint set; feature release verdict Not Assessed. REVISION 1.1 (same day, coordinator-directed, owner decision): JPEG decode joins the bounded seam — B5 revised in place with a B5-J admission profile (SOF0/1/2 only, caps at SOF parse pre-allocation, DNL/arithmetic/lossless/12-16-bit/CMYK/non-standard-sampling refused, progressive capped at 24 MP with coefficient-plane budgeting), a security-critical JPEG crate constraint (pure-Rust, unsafe/SIMD disabled, pre-allocation limits, RustSec-reviewed), a fixture-free hostile-JPEG test battery, and RR1 revised to conditional time-bounded acceptance: ADR-0016 worker must be scheduled with a committed milestone, and if no crate meets the constraint JPEG waits for the worker (feature ships PNG-only meanwhile).`
