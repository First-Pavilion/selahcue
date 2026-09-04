# Goal Contract — TASK-perf-review-pr19-openai-notes

## Identity

- Goal ID: TASK-perf-review-pr19-openai-notes
- Parent goal ID: TASK-86akby7d8
- Title: PR #19 (feat/86akby7d8-openai-sermon-notes) is performance-reviewed at head f1c648c, findings posted on the PR, and a verdict reported to the requester
- Role: performance-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby7d8
- Created: 2026-09-04
- Updated: 2026-09-04
- Maximum iterations: 8
- Independent verification required: no (this IS the independent performance review in the four-reviewer gate)

## Objective

At head f1c648c594107a22a111539c9c3563768b130883 (base origin/main cb006fc): the
performance posture of the OpenAI sermon-note path is reviewed with evidence — the
blocking-call offload, the adequacy of the 30s transport timeout against the workload
FR-122 targets, the compute cost of the bounded input/parse paths at realistic and
adversarial sizes, the CI time added by the four new gate lines, and the NFR claim
(idle memory / cold start unaffected) — findings posted as a review on PR #19 in plain
English, and the blocking findings summarised back to the requester.

## Baseline

PR #19 adds a GPT-backed `CloudNoteProvider` behind off-by-default `openai` /
`openai-notes` features. Cody and Sana have reviewed; their blocking findings are
remediated. Live round trip measured by the implementer: 14.6–17.8s on a 1,431-word
transcript. `ReqwestTransport::new()` carries a pre-existing 30s total timeout that this
PR makes load-bearing for the first time. Memory bounds are reviewed; the compute and
elapsed-time story is not.

## Inputs and evidence sources

- Worktree /Users/m.oluwole/Documents/code/scph-86akby7d8 at f1c648c (never the shared main checkout for gates)
- `git diff cb006fc..f1c648c` — the full reviewed diff
- ClickUp 86akby7d8 (acceptance criteria; "within a reasonable time"), docs/research/PROVIDER-TRADEOFFS.md ("sermon-notes is not latency-critical")
- GitHub Actions runs on PR #19 vs recent main runs (CI-time delta, nfr job)
- Scratchpad measurement harness driving the crate's public API (consent gate intact)
- One or two deliberate live OpenAI runs at realistic sermon length (authorised by the requester, ~$0.05/run, reported)

## Scope

### In scope

- Offload correctness of the blocking reqwest call under `tauri::async_runtime::spawn_blocking` (both `cloud-live` and `openai-notes` variants)
- Timeout adequacy: 30s total vs a realistic 45–60 min sermon transcript; behaviour when it fires (degraded fallback, spend without result)
- Concurrency: whether repeated Generate presses can stack unbounded in-flight requests
- Compute bounds: `bounded_transcript` char scans, `parse_draft` on hostile max-size bodies, `clamp_chars`, `ClampLog::record`, the 4MB error-path parse in `error_code`
- CI cost of the four added gate lines (cloud openai clippy+test; operator openai-notes clippy+test), local timing plus actual CI run deltas
- NFR: verify the measured binary's relationship to the diff; read the PR's CI nfr job result

### Non-goals

- Modifying the code under review
- Re-reviewing security or general correctness (Sana's and Cody's lanes)
- Merging, approving, or marking the PR ready
- Weakening the consent gate or fabricating a quota for measurement purposes
- `make ci` in the shared checkout (another session's Flutter tests are running)

### Constraints

- Test suite must never touch the network; live measurement only via a deliberate scratchpad harness through the public consent-gated API, cost reported
- No shared CARGO_TARGET_DIR with the main checkout
- Exit codes captured directly, never piped away

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The full PR diff cb006fc..f1c648c is read and every performance-relevant path identified (offload, timeout, compute bounds, concurrency, CI gates, NFR surface) | reviewer (Vera) code read | Paths enumerated with file references in the review | Diff read end-to-end; paths enumerated in review 1 and ledger I1 | PASS |
| C-002 | yes | Feature-gated suites compile and pass in the worktree, with wall-clock times captured (cloud openai clippy+test; operator openai-notes clippy+test) | cargo exit codes captured directly + `time` | EXIT=0 for each, times recorded | cloud gates EXIT=0 isolated (7s/11s/15s); operator gates EXIT=0 in PR worktree (2s/4s warm) + 3-OS CI green at 8492c90; ledger I2 | PASS |
| C-003 | yes | Compute cost of the bounded paths measured at realistic and adversarial sizes (`bounded_transcript` at/over 400k chars, `parse_draft` on a max-hostile body, error-path parse) | scratchpad harness output | Numbers recorded; verdict problem / no problem | microbench numbers in ledger I3 and review 1 section 3; verdict no compute problem | PASS |
| C-004 | yes | Timeout adequacy of the 30s transport cap assessed against a realistic 45-60 min sermon, with at least one deliberate live measurement (cost reported) or an explicit reasoned verdict if measurement fails | scratchpad harness through the public consent-gated API | Elapsed time vs 30s recorded; behaviour on expiry named | three live runs 18.0s/24.6s/16.6s (~$0.22) + stall probes; drip shape found UNBOUNDED (8m29s@30s cap; text() control cut at 30.0s; 9845bba probe in review 2) -> PERF-2 blocking finding raised | PASS |
| C-005 | yes | CI time delta of the four added gate lines quantified from PR #19 CI runs vs a main baseline run, and the nfr job result on this PR read | gh run/job timings | Delta stated in minutes per job; nfr PASS/FAIL read | step timings from run 33866074098 (~5 runner-min/run, no critical-path change); nfr green in run 33867543714 at f1c648c; ledger I5 | PASS |
| C-006 | yes | Findings posted as a review on PR #19 in plain English per team writing standards | gh pr review visible on PR | Review URL | review 1: pullrequestreview-5112486486 (COMMENTED); review 2 (PERF-2, blocking): pullrequestreview-5112573984 (COMMENTED; GitHub refuses REQUEST_CHANGES on the owner's own PR) | PASS |
| C-007 | yes | Verdict and blocking findings (or "none") reported back to the requester | Final response text | Stated | final response summarises PERF-2 blocking + verdict | PASS |

## Iteration ledger

- I1 (diff read, C-001): full diff cb006fc..f1c648c read. Perf-relevant paths: `run_openai_note_generation` + `cloud-live` `_ =>` arm (both wrap client construction AND the blocking call in `tauri::async_runtime::spawn_blocking` — offload correct, and the blocking reqwest client is never built on an async worker); `settings.js` `generating` single-flight guard (pre-existing) prevents stacked Generates; `bounded_transcript`/`clamp_chars`/`parse_draft`/`error_code` compute paths; 4 added gate lines in Makefile + ci.yml (operator job ×3 OS); `make nfr` measures `selahcue-output`, which contains none of the feature code (diff to its dep graph = additive types in selahcue-core). PASS.
- I2 (gates, C-002): first run in the SHARED PR worktree hit a non-reproducible failure in `a_section_the_operator_switched_off_...` (scriptures non-empty with extraction off) — pure deterministic test, CI-green at same code, passed 31/31 on re-run and in my isolated worktree; consistent with compiling a peer's transient mutation probe (Quinn is reviewing the same worktree; Kenji warned of collisions mid-run). Isolated worktree (scratchpad/vera-pr19-wt @ f1c648c): cloud clippy openai EXIT=0 (7s), cloud test openai EXIT=0 31/31 (11s), cloud clippy openai,http EXIT=0 (15s). Operator gates fail in the fresh worktree only for a missing gitignored Tauri sidecar (env artifact, not a PR defect); they passed in the PR worktree (EXIT=0, 2s+4s warm) and on all three CI OSes at 8492c90 (operator code unchanged in f1c648c). PASS.
- I3 (compute, C-003): release-mode microbench (scratchpad/vera-pr19-bench, vera_offline_bench): bounded_transcript 3.5µs @ 40k chars, 27µs @ cap 400k, 749µs @ 4M, 5.2ms @ 40M (hostile 100x). build_body 75µs realistic / 406µs at cap / 1.06ms hostile. parse_draft 17µs realistic; 4.2ms worst hostile under-cap (433KB, 100×100 points + 9×4000 items); over-cap reject 82ns (O(1) as documented). Error path: map_error_status on 1.5MB hostile JSON 429 body 12.2ms (linear; ≤4MB transport cap bounds it), 4MB non-JSON 125ns. Verdict: no compute problem at realistic or adversarial sizes. PASS.
- I4 (timeout, C-004): three deliberate live runs through the public consent-gated API (generate_sermon_notes, ConsentState.cloud_notes=true, shipped ReqwestTransport 30s), cost ≈$0.22 total: 6,533 words (~50 min) → 18.0s OK; 12,049 words (~92 min) → 24.6s OK; 23,547 words (~181 min) → 16.6s OK. With Kenji's 1,431-word runs (17.8s terra / 14.6s luna): elapsed is flat in input length (prefill cheap at 31k tokens), driven by output size + provider variance. Observed max 24.6s = 82% of the 30s cap; median ~18s = 60%. Stall probes (loopback): accept-then-silent 30.0s Err, headers-then-stall 30.0s Err (the manual read_capped path IS bounded), slow-drip pending at ledger time. Behaviour on expiry: NoteError::Transport → honest degraded local draft + notice; tokens still billed; retry re-bills. Verdict: adequate for the median workload with thin headroom at the long tail; finding PERF-1 (non-blocking) recommends raising this call's total timeout and adding a short connect timeout. PASS.
- I5 (CI cost, C-005): from green run 33866074098 (head 8492c90) step timings: rust job cloud-openai test step 2s ubuntu / 5s windows (clippy line inside existing step, seconds); operator job Clippy(openai-notes) 45s ubuntu / 37s windows, Test(openai-notes) 84s ubuntu / 111s windows. ≈5 runner-minutes per run across the matrix; workflow wall time unchanged (rust windows 11m29s remains the critical path; operator jobs finish ≤5m10s). Local warm `make ci` addition ≈13s. Run 33867543714 at the review head f1c648c: SUCCESS, including launch-smoke (which runs `make nfr` under xvfb) — the NFR budgets passed at the exact head. PASS.

- I6 (reopened, C-004, resolved): the slow-drip stall shape (headers, then one byte per 5s) was left running past my first review post and NEVER hit the 30s deadline — killed by hand at 8m29s. The shipped read path (`read_bounded` → `read_capped` over the blocking `Response`'s `Read` impl) evades the client's "total" timeout when bytes keep arriving; the zero-byte stalls (the only shapes the PR's own probes and its 9845bba doc-comment measured) are cut exactly at the deadline. This voids the "no blocking findings" verdict posted earlier — finding PERF-2 (blocking) raised in a follow-up review. Verified at 9845bba: zero-byte shapes cut at exactly 60.0s (constants live); the drip was still alive 172s past the 60s deadline when the 300s observation window killed it. Control: the identical drip against reqwest's own text() with the identical 30s client config errors at exactly 30.0s — the hole is introduced by this PR's read path. PERF-2 posted as review 5112573984; ClickUp corrected (comment 90130316142424); direct SendMessage to kenji failed (session unreachable), relayed via final response to the requester.

- I7 (re-review round, PERF-2 closure): PR head moved to 82a1bb2 (remote-verified: 9 ahead / 0 behind origin/main@3f3072e; earlier heads 41e52d0/f56fe72 superseded by squash+force-push-with-lease). Remediation verified by measurement in a fresh isolated worktree: read_capped now takes Option<Instant> deadline checked before every read and after every chunk; overflow fixed with saturating_add. Probes through the shipped transport: body drip cut at 63.9s (was: alive 172s past deadline), header drip cut at 62.4s by reqwest (head-phase running-total claim verified). Mutation A (deadline checks gutted) = test binary HANGS at 40s wall cap — the drip test cannot pass by hanging; Mutation B (+1 restored) = RED overflow panic; both restored, worktree clean. Cloud gates EXIT=0 (openai 34/34, transport 9/9, openai,http clippy, default suite). Model override SELAHCUE_OPENAI_MODEL assessed: bounded 64 chars, unknown model → 404 → NotConfigured (honest), one resolver feeds panel and provider; no perf finding, no live spend. Complement sweep: upload phase covered by verified head-phase bound; cap×deadline cross-product tested both directions; serde depth limit covers nesting; observation only — dev_env.rs unbounded read_to_string on .env (local dev file). Re-review posted: pullrequestreview-5113112722; ClickUp updated. CI matrix on 82a1bb2 (33873838920) in progress at post time — caveat stated in the review; verdict rests on my own measurements.

## Terminal state

- VERIFIED_COMPLETE — PERF-2 raised, remediated by the engineer, and independently verified closed at 82a1bb2. Performance gate cleared, with the explicit caveat that the 3-OS CI matrix on 82a1bb2 must finish green before merge.
