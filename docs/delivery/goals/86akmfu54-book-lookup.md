# Goal Contract — TASK-86akmfu54

## Identity
- Goal ID: TASK-86akmfu54
- Parent goal ID: NONE
- Title: Scripture book lookup preserves parsing without per-candidate allocation
- Role: mobile-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akmfu54
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective
Remove canonical-book normalization allocations from lookup while preserving all parser behavior and demonstrate at least a threefold release-mode miss improvement under the approved measurement protocol.

## Baseline
Verified main 8f7d610ef81efc4c7359e9b3cb6d9d44fb99c56e: lookup_book normalizes each canonical book name into a String before comparing. Input normalization remains separate. Current verification budgets are MAX_LIST_REFERENCES and MAX_EMBEDDED_REFERENCES; the historical MAX_VERIFIED_REFERENCES name no longer exists.

## Inputs and evidence sources
- Coordinator's full live ClickUp description/comments/dependency qualification in /private/tmp/selahcue-batch20-20261029/native-queued-payloads.md; no blockers or owner hold.
- Core scripture parser, book definitions, detection and verification tests; actual operator verification call sites.
- Runtime, mobile and goal skills; no applicable AGENTS.md found. Historical timings are context only and will not be used as fresh results.

## Scope
### In scope
- Allocation-free canonical name comparison, preserving normalization and aliases/public APIs.
- Meaningful allocation and semantic regression tests; actual release benchmark with saved baseline/candidate provenance.
- Clarify current verification budget documentation and explicitly record remaining async/byte-budget decision.
### Non-goals
- No detector redesign, canon/alias changes, new parser API, scan budget, worker migration, provider changes or dependency additions.
### Constraints
- Same black_box inputs/results, compiler, release build/profile and benchmark driver; seven rounds of 20,000 repetitions for both miss and hit. Coordinator must reserve each quiet measurement window before timing.
- Temporary benchmark remains out of shipped tests; no timing assertion in normal CI. Test allocator instrumentation stays in a dedicated integration test binary; no unsafe production code.
- Coordinator owns tracker, four independent reviews, hosted CI, publication, merge and QA. Isolated branch only; do not revert other agents.
### Assumptions and unknowns
- Parser changes affect native callers transitively; no device UI/permission/signing/persistence contract changes or physical-device acceptance required.
- Quiet means coordinator-quiesced agent workloads, not an unsupported claim that every operating-system process is idle.

## Dependencies and approvals
- User authorizes existing actionable tickets and the implementation/review/merge/QA cycle; coordinator assigns native core scope despite historical owner prose.
- Both released native caches are exclusive to this worker. Full make ci/Flutter and timed windows require coordinator scheduling.

## Completion predicate
All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Book search adds no allocation per candidate | Real public parser allocation regression, source proof and inline allocating mutation | baseline/mutant RED, candidate GREEN | /private/tmp/selahcue-batch20-20261029/86akmfu54-allocation.log | PASS |
| C-002 | yes | Canonical/alias/normalization/detection behavior and public API preserved | Complete core tests plus explicit canonical/alias controls | All pass, no API change | /private/tmp/selahcue-batch20-20261029/86akmfu54-core.log | PASS |
| C-003 | yes | Release quick brown miss at least 3x faster than baseline | Identical black_box benchmark binaries; approved quiet windows; best of 7 rounds of 20,000 | baseline best / candidate best >=3; all rounds/provenance saved | /private/tmp/selahcue-batch20-20261029/86akmfu54-benchmark.md | PASS |
| C-004 | yes | Verification docs state verdict/lookup limits do not bound full scanning time; async decision explicit | Actual call-site audit and revised current-constant docs | Correct scope, no silent budget/worker change | This goal and source docs | PASS |
| C-005 | yes | Complete required local gate passes | Serialized make ci, format and lint | exit0 with limitations explicit | /private/tmp/selahcue-batch20-20261029/86akmfu54-make-ci-recovered.log and final integration receipts | PASS |
| C-006 | yes | All four independent reviews pass frozen revision | Cody, Quinn, Vera and Shadow | Four passes after remediation | Coordinator reports | BLOCKED |
| C-007 | yes | Exact-head hosted CI, merge and linked task QA readback succeed | Coordinator delivery verification | Merge and QA persisted | Coordinator evidence | BLOCKED |

## Verification plan
- Focused verification: allocation RED/GREEN, all canonical/alias normalization, complete core suite.
- Broader regression verification: complete serialized make ci including transitive native callers.
- Independent verifier: coordinator's four reviewers.
- Required environment: pinned macOS Rust toolchain, identical release benchmark driver/compiler/settings; coordinator-reserved quiet windows.

## Iteration ledger
### Iteration 1
- Target criterion: C-001/C-002/C-003.
- Hypothesis: streaming normalized canonical bytes removes repeated heap work and short-circuits ordinary misses without changing lookup ordering or aliases.
- Change or investigation: confirmed live source gap; prepare failing allocation regression, semantic controls and baseline benchmark before production change.
- Verifier executed: pending.
- Result: pending.
- New evidence: canonical normalization allocation still present at fresh main.
- Decision: iterate.

### Iteration 2 — allocation/semantics and measured release result
- Target criterion: C-001 through C-004.
- Hypothesis: short-circuiting normalized bytes avoids canonical heap work while retaining exact full-name equality and alias ordering.
- Change or investigation: allocation regression first failed on unchanged lookup (late-book 51 vs early 4 allocations). Baseline canonical/alias controls and 25 parser integration tests passed. Replaced only canonical comparison with filtered lowercase byte iterators; aliases/input normalization retained. Dedicated allocation observer is test-only, delegates to System, has a real allocation positive control and compares equal-length early/late/miss parser inputs. No unsafe production code.
- Verifier executed: candidate allocation test, allocating mutation with semantic siblings, restored complete core debug/release suites, strict clippy, immutable release binaries under separately approved quiet windows.
- Result: allocation GREEN; allocating mutation 36 passed/1 expected allocation failure; restored core 280 passed in debug and 280 in release, zero ignored. Clippy passed. Fresh release miss best 2187.60415 to 251.78125 ns/call = 8.68851x; hit 1353.1146 to 288.82915 ns/call = 4.68483x. Seven rounds of 20,000, 2,000 warmup, black_box input/result and identical driver/compiler/profile. All candidate miss samples below 729.201 ns; variation retained. Both binaries compiled at same 8f7d610e target before main integration. Temporary benchmark test removed before complete core suites and publication.
- New evidence: allocation-red.log, allocation.log, mutation.log, core.log, core-release.log, clippy.log and full benchmark artifacts prefixed 86akmfu54 under /private/tmp/selahcue-batch20-20261029/. Benchmark report includes all samples, compiler/source/binary hashes, flags and CPU conditions. Initial virtual-workspace formatter had no targets; corrected to the core package.
- Decision: iterate for merged-main integration and reserved complete make ci. No historical metric, universal speedup or full scan-time bound claimed.

### Iteration 3 — recover and complete the full local gate
- Target criterion: C-005.
- Hypothesis: a durable wrapper can complete and retain the required full gate after the original session disappeared, without repeating the already-proven release benchmark.
- Change or investigation: the first log stops at API 45%, lacks an exit marker and has no surviving book make/pytest process; termination cause is unknown. Preserve that incomplete attempt. Merge main c72ae6f7 into 40f48c2f210999599384edc13338612fb83f2dbe, then run make ci through a detached wrapper with exact revision, environment, PID and timestamps.
- Verifier executed: CARGO_TARGET_DIR=/private/tmp/selahcue-review238-target CARGO_INCREMENTAL=0 make ci, with no audit skip flag.
- Result: exit0 and ALL GREEN banner, started 2026-10-29T12:24:07.854835+00:00 and finished 2026-10-29T13:22:54.066391+00:00. Marketing1217 passed0 skipped, API1592 passed28 skipped (PostgreSQL/Redis requirements named in log), Flutter380 passed and analyzer clean. Rust368 suite invocations:6549 passed test executions,0 failed,29 ignored executions (includes repeat feature runs and child/manual probes; not6549 unique tests). All three Cargo roots passed audit; workspace2/operator4 allowed warnings retained, STT root no warning. No failure-summary line in the complete log. Wrapper is no longer running.
- New evidence: 86akmfu54-make-ci-recovered.log/.json/.exit and make-ci-summary.json in the coordinator evidence directory. This full-gate receipt applies to40f48c2f, not an untested later integration revision. Original incomplete log remains separate. CI-only platforms, Postgres/Redis and other omissions remain those listed in Makefile ci header; this is not hosted CI.
- Decision: C-005 PASS; proceed to proportional fresh integration and final author handoff.

### Iteration 4 — current-main integration and author freeze
- Target criterion: preserve C-001 through C-005 on current target; hand off C-006/C-007.
- Hypothesis: main6ef0e0980a950a179b22c5ea6e960b96e654ddd9 adds only API observability and pipe-safe launcher/workflow changes, leaving measured parser/native/mobile sources unchanged, so focused affected-area regressions plus fresh core/static checks provide proportional integration evidence.
- Change or investigation: save and restore only this run's generated pubspec.lock Flutter SDK floor change (3.41 to3.44; no dependency changes), merge current main cleanly as3615e0c91595d9c54650a1079897d430decd61e5. Full diff from full-gate source has14 API/launcher/workflow/docs paths and no implementation/desktop, implementation/mobile or Makefile difference. Parser SHA256 remains63ae3c4d31b9bf215fec1170d43a393e7e8d3901a351912370d3b146316d33ff, matching the immutable measured candidate. Benchmark binaries/driver hashes were rechecked, not rerun under load.
- Verifier executed: complete core tests and strict core lint/format; new/native/throttling/guard/header/deployment-doc API regression set; pipe-safe launcher caller suite; workflow/minute self-tests and checks; target ancestry/behind0, structural goal and diff checks. Actual receipts and final immutable SHA are recorded in 86akmfu54-report.md and matching final logs under /private/tmp/selahcue-batch20-20261029/.
- Result: fresh core280 passed across14 targets,0 failed/ignored; strict lint/format PASS. Focused API244 passed1 existing real-Redis-header skip (CACHE_URL absent); this is not a current-head full API or Redis result. Launcher15 cases across5 test methods PASS with no surviving fixture helpers; workflow101-case self-test and5-workflow/17-job check PASS, minute self-test and5-workflow check PASS. Full make ci is not repeated on the later integration because Rust/Flutter/Makefile trees are byte-identical; no newer full-suite or newer benchmark claim is implied. No production source/test edit was made during recovery/finalization. Final docs/static verification follows this evidence-only update before commit.
- New evidence: generated-flutter-lock.diff and integration proof/receipt artifacts in the coordinator evidence directory. No dependency/lock change ships.
- Decision: author handoff only after the final checks pass; all four independent reviews, exact-head hosted CI, publication/merge and linked QA readback remain coordinator-owned.

### Iteration 5 — latest native outage main integration
- Target criterion: preserve C-001 through C-005 against the latest target before review freeze.
- Hypothesis: main d5476edde13649e8b1c4fbfc92647d07e2f9e3eb adds only native API outage handling and documentation; its combined affected API regressions can verify integration while unchanged native/mobile components retain their prior full/focused evidence.
- Change or investigation: final behind check detected the newly merged main before patch export. Merge it cleanly as 0fdfa6bba8d2086f6416c09e06f44a84ea056f81. The seven newly integrated API/docs paths do not change desktop, mobile, Makefile, launcher or workflow sources. No production/test changes authored here; current parser and complete desktop/mobile tree equality to the full40f48c2f gate are recorded in final-freeze.json.
- Verifier executed: combined native-login-outage, native-auth-observability, native account, throttling, guards, header and deployment-doc tests on SQLite/local cache.
- Result:261 passed,1 existing real-Redis-header skip (CACHE_URL absent),65.80s. Receipt:86akmfu54-final-outage-integration.log/.exit in the coordinator evidence directory. Earlier244-case receipt remains separately tied to its then-current source. Fresh core280/lint/format and launcher/workflow evidence remains applicable by unchanged component/source proof. No full make ci, native broad suite or benchmark rerun is implied.
- New evidence: after this evidence-only update, repeat documentation and structural/diff/ancestry checks before the final clean evidence commit; final receipts and exact immutable review SHA are in86akmfu54-report.md. No tracked edits after those verifiers apart from committing the checked bytes.
- Decision: author freeze and release cache/Flutter reservations when own processes have finished. C-006/C-007 remain coordinator-owned.

### Verification runtime and byte-budget decision
The historical MAX_VERIFIED_REFERENCES name is superseded by the current MAX_LIST_REFERENCES and MAX_EMBEDDED_REFERENCES. Both document verdict/lookup counts, not full scanning time or bytes. The detector materializes each body's candidates before applying the embedded verdict budget; long ordinary text and repeated references still require work. This patch improves each lookup, not the asymptotic scan or its input budget.

Decision: no new worker migration or byte budget in this pure-core optimization. Persisted Settings draft loading already runs its codec inside a blocking job after PR254 / ticket17tnw2axpq3. That verified change remains intact. Actual remaining production callers audited at main8f7d610e:

| Call chain | Current execution | Disposition |
|---|---|---|
| load_sermon_note_draft → sermon_note_view_ok_json → codec → verify_scriptures | Tauri spawn_blocking | Already addressed separately; preserve |
| transcript_get → build_transcript_detail_view → codec | Inline in async command | Remains known CPU work; no scheduling change in this ticket |
| persist_generated_draft → previous accepted-draft codec | Inline in async staging flow | Preserve persistence and retention behavior; separate scheduling scope |
| transcript_generate_notes → apply_scripture_verification | Inline after awaiting provider generation | Provider offload does not offload this later verification; remains explicit |
| update_sermon_note_draft → codec | Inline after saving edit | Preserve edit response semantics; separate scheduling scope |
| confirm_sermon_note_regeneration / discard_sermon_note_regeneration → shared success builder → codec | Inline in async commands | Preserve accepted-draft lifecycle; separate scheduling scope |

Changing those command lifecycles belongs to a separately scoped native scheduling change. A new byte budget would change which references are checked and would require an explicit incomplete-verification response/caveat contract; silently truncating here would violate the preserved semantics. The approved ticket permits documenting this decision. No claim is made that every verifier call is off the async runtime or time-bounded, and no shadow ticket is created.

## Risks and rollback
- Risks: normalization equivalence and prefix equality must be exact; noisy measurements could overstate improvement.
- Rollback or recovery: revert isolated ticket; no schema/dependency/persistence change.

## Pause and escalation conditions
- Never time without a reserved quiet window. Stop for changed scope, unjudgeable integration overlap, new gate failure, or three materially distinct failed approaches without evidence.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86akmfu54-book-lookup.md
- Validator result: structural PASS; final docs/static receipt after the evidence-only update is in the author report
- Independent verification result: coordinator pending
- Terminal state: BLOCKED pending coordinator independent review and delivery
- Remaining failed or blocked criteria: C-006 and C-007; final author receipts recorded separately
- ClickUp final evidence comment: coordinator-owned
