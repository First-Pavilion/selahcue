# API CI capacity: binding narrow amendment

Accepted by the coordinator on 2026-11-17 after reading the actual terminal evidence and the independent builder's terminal-evidence addendum. Change only the existing `api` job's outer ceiling from **30 to 35 minutes** and its adjacent rationale comment. Keep the operator at 30 minutes and every other job, runner, matrix, dependency, condition, command, order, environment, artifact, failure rule and test selection unchanged. This supersedes the active API-only 30-minute references in the repair specification, plan and minimal qualification amendment. It does not change application performance requirements or authorize another automatic increase.

## Measured reason

Normal CI run `43970076858`, attempt 1, tested source `e461f4460c320edf01f24a395892a0189dbb2bb6` through hosted merge `28d1ceaa3539459f685f056cfa2b69d9f8f257c6`, tree `69606e27de7c3dbd0d891c48520dee5234e6e65a`. The API job `133665705892` began at 22:37:33 UTC and completed at 23:07:40 UTC. GitHub's official annotation says the job exceeded its maximum execution time of 30m0s. The attempt was not superseded or manually cancelled.

The unchanged normal suite completed with **3,745 passing tests, one intentional opt-in skip and 57 passing subtests**, accounting for all 3,746 collected identities, with zero unexecuted. All **493 original acceptance identities** and all **10 G1 joint cases** passed. Pytest reported 1,659.25 seconds; the Tests step occupied approximately 1,662 seconds after 141 seconds of setup and qualification. The full summary was emitted at 23:07:35.5880397 UTC, 0.7628627 seconds before cancellation. The final mandatory G1 JUnit validator and upload were skipped. A raw JUnit-generation message and passing case names are not retained, validated G1 evidence: the API gate remains failed.

The seven-control baseline and all four expected assertion-failing mutants passed their separate qualification contract, including four restorations, five distinct PostgreSQL 16.16 scratch databases and unchanged canonical API bytes. Those results do not substitute for successful normal API/G1 finalization or the later canonical run.

## Decision and unchanged requirements

Five additional minutes, about 17% of the measured whole-job scale, is proportionate headroom for final validation/upload and ordinary runner variation. It is not a measured minimum or a reliability guarantee. The earlier proposed 45-minute ceiling was never accepted or implemented; complete terminal timing now supports 35. The maximum additional allowance is five Linux job-minutes per eligible API attempt, including ten across the required overlay and post-overlay attempts, and persists for future shared API executions. Actual execution cost depends on elapsed runtime.

Keep the **180-second baseline, 60-second mutant, 450-second supervisor and 5-second cleanup reserve**; exact seven baseline identities, four recipes/assertions, source-copy checks, PostgreSQL provenance and restoration requirements; original 493 manifest; full normal pytest command and final G1 controls. Preserve all SQL, lock, child and application deadlines, including ordinary refresh's three-query/no-row-lock requirement and cascade application/soft/hard bounds 225/235/240 seconds, one-second lock, at-most-five-second statement and 60-second delivery expiry. Freeze API snapshot `01413d07e6377c017d5f2d2cbff4244ec4460017` and API tree `0410de586e948265ca1d20d69281ba950c5490d1`; no API, fixture or qualifier source change is authorized by this amendment.

Use the actual official job-cap failure as runtime RED. No unit test that merely repeats a YAML literal is required for this configuration correction. Validate exact workflow byte equivalence modulo the one accepted field/comment, parsed job equivalence, unchanged command parity and existing workflow/minutes policies. Obtain independent source/spec review before the next normal checkpoint. Local resource hold remains active; do not run application, database, browser, native or full API-gate selftests locally.

The corrected exact composition must pass full normal API and final mandatory G1 validation and retained evidence, with all 493 identities passing in the same run, attempt and hosted merge. Only then remove the temporary qualification overlay and repeat complete normal API, 493 and G1 verification on the resulting canonical source. A new assertion, resource failure or timeout requires investigation of its actual evidence. No gate waiver, further cap increase or test redesign is preauthorized.

## Evidence custody

The coordinator fully read terminal triage and timeout/G1 evidence, rehashed 36 raw/metadata files across 12 archive receipts plus three causal receipts, and verified hosted source/merge/tree. Custody is recorded in `ci-43970076858-root-reverification.json`; the archive manifest SHA-256 is `983a91b041df5f38b924b7842c916062e2a7ea7b2d52e992ca56a1f7f7da1af3`. Official cancellation annotations SHA-256: `a72ba4bf56c4afb24629585e0af653d89e7127ad3362067e131e70bf8feef295`; API raw log: `211012d90fbc5eb590b5f53b4c84b5787a189b594559e7d336c382ad0b5af081`.

Evidence files and the independently read `pr233-api-capacity-amendment-builder-20261116.md` are retained in the session's `release-evidence/open-pr-review` directory. This design decision changes no workflow by itself and claims no subsequent GREEN.
