# Native fault capture implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development as requested by the user: a fresh implementation worker per task and fresh review at each task boundary, under the parent session's existing authorization and single-writer sequencing. No core/debugger operations are in scope. Parent controls hosted verification admission; local native/heavy hold persists.

**Goal:** Capture enough bounded metadata on one normal CI candidate to distinguish genuine GPU readback/None and corroborated native signal threads, preserving original gates.

**Architecture:** Extend the existing journal collector and offline controls with two fixed profiles and a conservative kernel join. Add a test-only observer around existing parity calls; production compositor stays unchanged.

**Tech stack:** Existing Python stdlib collector, Rust stdlib test helper, existing Actions Linux jobs and installed system journal.

**Spec:** [2026-11-16-native-fault-capture-design.md](../specs/2026-11-16-native-fault-capture-design.md). Detailed tradeoffs: [architecture report](/Users/m.oluwole/.codex/visualizations/2026/11/14/01a1d9e8-f42c-7583-89ee-386ea3167ba8/release-evidence/open-pr-review/native-fault-next-capture-design.md).

## Global constraints

- No production compositor, version/backend/OS, assertion/coverage, scheduling, job/matrix/runner/cache/timeout or original gate-exit changes.
- Exact workspace command remains `cargo test --workspace --no-fail-fast`; no serialization, nocapture, retry or new noGPU escape.
- Metadata 256 KiB + 64 KiB, one probe byte each; index ≤3 records ×64 TIDs ×12 sanitized frames before correlation; export ≤3 records ×3 stacks ×12 frames; JSON ≤24 KiB; 8-second metadata + 2-second fixed-file identity ceilings. Any unexamined possible candidate makes attribution unknown.
- GPU ≤48 records/case including overflow marker, ≤256 bytes each; fixed enums and numeric data only. No pixel/private data or arbitrary errors.
- No core/debugger machinery, installs or local native/heavy execution. Parent may admit necessary tests-only hosted RED/GREEN checkpoints before final capture wiring; exactly one FINAL instrumented normal capture follows Task 4 and review. No blind reruns or automatic retries.
- Fresh SDD implementation worker per task; only one worker writes shared files at a time, after the busy application writer yields them. Fresh review at each task boundary; preserve everyone else's changes.

## Review focus

- Filtered native #0 must not become #1/first-retained fault evidence — Task 1 fixture.
- Kernel TID reuse, unsupported complete grammar, duplicate/global pairs or unexamined possible candidates must not create ownership — Task 2 grammar/completeness controls.
- Native signal/early successful return must not hide GPU evidence in libtest buffers — Task 3 direct-writer/abrupt-child control.
- Permission failure or descendant-held pipe must not hang/emit private output — Tasks 1–2 subprocess controls.
- Stale cached binary/installed library must not masquerade as crash-mapped identity — Task 2 ELF/path/build-ID controls.

## Task 1: Preserve bounded journal identity

**Files:** modify `implementation/marketing/scripts/webkit_crash_journal.py`; extend `implementation/marketing/tests/test_webkit_crash_journal.py`.

**Interface:** keep `collect(result, data, cut, since, until)` callable and existing WebKit CLI/replay path while evolving output to schema version 2; `stack` indexes all ≤64 TIDs/original #0s and ≤12 sanitized frames per indexed thread before any three-stack export selection. Keep `candidate_scan_complete`, `export_truncated`, reasons and private PC fields distinct. Private PC fields must never reach `export`.

- [ ] Add tests using existing `collect`/replay invocation: two TIDs, disallowed #0 then valid #4, module build ID, explicit core truncation. Assert original ordinal/TID and safe identity rather than indexing a nonexistent implementation symbol. Run selected controls and record behavioral RED (lost evidence).
- [ ] Extend existing parser to index ≤64 headers and original #0s before bounded three-stack export selection, preserve ordinals, parse supported build IDs and separate core truncation/candidate completeness/export omissions. Detect fourth eligible record/65th distinct header without raising caps. Keep finite module/symbol validation; add fixed GPU role/profile.
- [ ] Extend existing caps/hostile-string/replay tests for schema v2, 24 KiB export and exact omission priority. Add boundary tests for duplicate TID/ordinal/conflicting IDs, unknown modules, whitespace/control bytes and malformed nested JSON.
- [ ] Run `python3 implementation/marketing/tests/test_webkit_crash_journal.py` only when parent admits fixture execution. Require original controls plus new behavioral tests passing, with no real journal/core reads. Record actual commands/results; do not claim live capability.

## Task 2: Correlate existing kernel metadata and identify installed file

**Files:** same collector/tests; no new generalized package.

**Interfaces:** fixed profile chooses exact coredump executable/module allowlists. Add `correlate_kernel(records, kernel_bytes, candidate_scan_complete) -> records_with_attribution_and_completeness` and `installed_identity(profile, eligible_records) -> safe_identity` as private functions. Correlate across the whole invocation before export selection. Keep original no-attribution behavior until RED assertions are established; runnable seams/fixtures must exist before testing new behavior, not import errors. `--kernel-jsonl` is offline-only companion replay; no replay-to-host fallback.

- [ ] Add the spec's complete literal P1–P5/N1–N6 grammar fixtures; assert all supported producer endings, exact private parsed TID/IP/module and rejection of unsupported/incomplete/trailing/path/bad-number input. Implement only the five pinned variants, with no general permissive parser or exported task/address/error/CPU data. Unknown relevant forms set `kernel_unsupported_format` plus incomplete inspection.
- [ ] Add complete-population join fixtures: matching fourth and 64th-listed TID become first exported fault stack; wrong PC/TID/time/boot remain unknown; missing/filtered original #0, hidden fourth eligible record, 65th header, raw/kernel byte caps and malformed relevant input yield `join_incomplete` and null. Two fully inspected disjoint pairs anywhere in invocation yield global `kernel_ambiguous`; duplicated kernel entries cannot be silently deduplicated into uniqueness. Export-only truncation after one fully inspected pair preserves attribution. Record behavioral RED, then implement bounded parse/index → global correlation → export selection, without increasing caps.
- [ ] Reuse isolated bounded subprocess supervision for the second projected kernel query; pin 64 KiB+one byte, two-second query deadline and eight-second total metadata cap. Test denied/missing/malformed/oversized/timed-out kernel output and pipe-holding descendants; existing valid coredump data survives kernel unavailability.
- [ ] Add tiny synthetic ELF/hash tests for fixed-file identity before implementing it: valid GNU note/hash, no notes, wrong class/architecture, oversized note/file, invalid offsets, duplicate conflicting ID, symlink escape and inode/size/mtime mutation. Byte identity never sets crash identity without matching journal ID.
- [ ] Implement fixed-profile identity child using existing supervisor, two seconds including cleanup, streamed 256 MiB file maximum, one-MiB chunks, 128 headers/one-MiB notes. GPU selects unique eligible crash executable only; no directory search. WebKit selects exact resolved WPE library. No raw temporary files/tool output, file execution or download.
- [ ] Run admitted offline collector controls and inspect exact safe outputs. Requirement: ≤24 KiB, no absolute PC/path/sentinel/raw line and no indefinite process. Parent reviews attribution and safety before workflow integration.

## Task 3: Observe existing GPU test operations

**Files:** add `implementation/desktop/crates/selahcue-gpu/tests/support/parity_diagnostics.rs` and `tests/test_parity_diagnostics.rs`; modify only `tests/test_parity.rs`. Production `src/compositor.rs` remains unchanged.

**Interfaces:** test-local fixed `Case`/`Stage` enums; `Observer` holds enabled flag, case, sequence/count and writer; `observe_construct<T>(observer, generation, operation: impl FnOnce() -> Option<T>) -> Option<T>` and `observe_readback(observer, generation, scene, operation: impl FnOnce() -> Vec<u8>) -> Vec<u8>` preserve supplied operation results/panics. Writer accepts one bounded byte slice and returns I/O result; failures are diagnostic-only. Remaining stage calls surround existing loss/drop/assertion boundaries without moving them.

- [ ] Extract behavior-preserving pass-through seams first (operation executes once, returns exact object/bytes and propagates panic). Add observer tests for None, bytes and panics; record RED for absent enter/return events, never absent symbols or failed compilation.
- [ ] Implement fixed enum/numeric direct-stderr records; test disabled mode, writer failure, exact event/byte bounds, overflow-marker reservation, native-TID missing/malformed input and per-case interleaving. No global operation lock, buffer, extra GPU construction or catch-panic in production test path.
- [ ] Add a controlled-child direct-write then abrupt-exit test that verifies enter record survival independently of libtest capture. Fake closures do not prove actual GPU work; keep that evidence boundary explicit.
- [ ] Place markers around existing constructor/render/loss/drop calls and after the original assertions. Compare all original scenes, assertion expressions, second-constructor expect and destructor timing. Do not add a backend-selection or adapter-enumeration probe.
- [ ] Run Rust observer controls in parent-admitted tests-only hosted RED/GREEN checkpoints as needed under the local native/heavy hold; final diagnostic wiring stays absent until Task 4. These validate observer behavior, not a completed diagnostic capture. The final normal hosted workspace command supplies real GPU coverage. Record assertion-completed versus libtest verdict separately.

## Task 4: Wire one normal capture and review

**Files:** `.github/workflows/ci.yml`; existing `implementation/marketing/scripts/webkit_crash_journal.py` and `implementation/marketing/tests/test_webkit_crash_journal.py` only for the approved finite rejection-stage amendment; evidence docs as needed. Native Tasks1–3 and the separately reviewed Home observer must be complete before final wiring/capture.

**Additional interface:** optional top-level `kernel_rejection_stage` follows the binding spec's approved finite stage addition. Preserve public `parse_kernel_message` compatibility, one strict parse path, existing omission reasons and null/incomplete joins.

- [ ] Before final wiring, add `test_kernel_rejection_stage_classifies_existing_branches`, `test_kernel_rejection_stage_aggregates_without_event_details` and `test_kernel_rejection_stage_absent_without_unsupported_text` through existing callable collection. Cover all six finite rejection stages, homogeneous/mixed aggregation, hostile sentinel privacy, supported P1–P5, unavailable and nontext projection. Observe actual missing-field assertion RED; missing imports/functions never qualify.
- [ ] Implement the one-parser finite result and constant-space aggregation. Preserve N1–N6 refusal, global ambiguity/incompleteness, private PCs and all original query/byte/population/deadline/output limits. Extend existing exact-cap/hostile-output controls for the field, keep matched frame zero and safe deadline fallback. No new grammar or raw evidence.
- [ ] Run focused new stdlib controls to GREEN, then the complete collector fixture file once under the prior bounded offline-only admission. Report actual results, no live journal/core/debugger/GPU/browser/local app execution.
- [ ] Add the already approved `python3 implementation/marketing/tests/test_home_anchor_capture.py` invocation in the existing workflow lint job. The existing Node glob selects its paired fixture. This additive selection preserves every original job, condition, timeout and command.

- [ ] Add workspace step ID, best-effort timestamp output and exact Linux-only diagnostic flag. Its final command/exit remains unchanged. Select post-step GPU collector only when the original Linux gate ran success/failure; diagnostic step alone is `continue-on-error`.
- [ ] Keep WebKit sweep and existing post-step collector selection; supply fixed profile/source identity and upgrade controls in the existing lint job. No jobs/matrices/runners/versions/timeouts/coverage change.
- [ ] Review workflow diff with actionlint and existing repository permission/structural controls when admitted. Use a controlled command/status fixture to prove collector failure does not alter original 0/101/2 gate outcomes; do not test only YAML string presence.
- [ ] Obtain parent-coordinated independent review of code, privacy, QA behavior and performance/bounds on exact candidate; remediate/re-review changes. Do not create another ticket or start native runtime while the local hold persists.
- [ ] After Task 4 integration and review, parent admits exactly one FINAL instrumented normal candidate CI run, captures original gate outcomes, observer receipts, source/binary identity and attribution/unknown reasons, and archives once. Earlier necessary tests-only hosted RED/GREEN checkpoints are not this capture. No blind rerun or automatic repeat on pass, noGPU, unavailable or inconclusive output.

## Handoff condition

Implementation readiness requires the settled metadata-only design, observer and parser RED/GREEN evidence, exact-source independent reviews and unchanged-gate verification. A successful diagnostic is not a GPU/browser pass or root-cause finding. Missing kernel events, incomplete candidate populations, stripped symbols, filtered driver modules or unavailable file identity remain bounded unknowns. Root has excluded stored-core/debugger fallback; no approval decision remains on it. Fresh SDD worker and review per task, then one final instrumented normal capture after Task 4.
