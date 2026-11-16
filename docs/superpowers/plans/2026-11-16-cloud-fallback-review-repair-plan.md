# PR398 Cloud Fallback Review Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair all PR398 findings while preserving fixed fallback diagnostics, native response bounds and persistence/admission policy.

**Architecture:** Merge current main into the existing source ancestry; compose the shared transport changes and select existing behavioral fixtures in existing CI jobs. Observe the owning Chrome failure before correcting its exact-count pin; qualify the final source and obtain independent re-review.

**Tech Stack:** Existing Rust/Cargo, Python Chrome harness, GitHub Actions and shell receipt checks; repository-pinned tools only.

**Spec:** `docs/superpowers/specs/2026-11-16-cloud-fallback-review-repair.md`

## Global Constraints

- Start: `11eb869c8bd51bf2070cc74e071e7365341e1cc5`; target: `256035f16c996fde6cd7e56849920f451e4bf033`; preserve both ancestries.
- Own work only; preserve other agents' changes. No provider calls, real secrets or `.env` access.
- No new CI jobs, matrices, dependencies or timeout changes; no configuration-mirroring tests.
- Keep Chrome expected 2997 until actual owning hosted Chrome RED measures total and both named assertions; never guess 2999.
- Existing synthetic readiness fixture and clock only. Exact selections must execute assertions; zero tests or a ready-parent early return cannot pass qualification.
- Hosted full-current-source CI is source-merge evidence. Goal C-005 local `make ci` remains UNRUN during pageout/swapin pressure; macOS/native release and future Notes C qualification remain separate.

## Review Focus

- Cap-plus-one streaming GET/POST must stop before EOF; at-cap GET succeeds; invalid constructor limits refuse.
- Empty Linux roots plus missing/blank Direct key must preserve NotConfigured with zero builds in debug combined features.
- Hosted fallback at pilot cutoff must still save/stage correctly; unreadable draft and denied consent must build/write nothing.
- Pilot expiry/rejection during construction and lock waits must preserve accepted/pending drafts; all six child cases must execute.
- Real TLS refusal and hostile diagnostics must retain fixed plain-text notice; actual Chrome must reach both new assertions and measure the whole count.

---

### Task 1: Compose target and expose missing behavioral checks

**Files:**
- Modify conflict resolution: `implementation/desktop/crates/selahcue-cloud/src/transport.rs`.
- Preserve merged controls: `implementation/desktop/crates/selahcue-cloud/src/transport/tls_tests.rs`, `implementation/desktop/crates/selahcue-operator/src/account/commands.rs`.
- Modify selections only: `.github/workflows/ci.yml`.
- Read/test: `selahcue-cloud/tests/test_fallback.rs`, `test_transport.rs`, `test_tls_system_store_linux.rs`; operator `src/main.rs`, `src/pilot_mixed_tests.rs`, `tests/fixtures/pilot-valid.json`; `.github/scripts/test_native_test_receipts.py`.
- Preserve Chrome pin in `scripts/operator_headless.py`.

**Interfaces:**
- Consumes both pinned histories and existing behavioral fixtures.
- Produces a reviewed merge composition retaining `ReqwestTransport::new_with_response_limit(usize) -> Result<Self, TransportError>` and both `read_bounded(resp, self.max_response_bytes)` calls with `reqwest_transport_error(&e, HttpFailurePhase::Send)` send mapping.
- Produces commit SHA/run ID, named feature/cap/TLS receipts, and owning Chrome measured RED for Task 2. No inferred runtime PASS.

- [ ] **Step 1: Record baseline and merge conflicts.** Inspect `git status --short`, `git rev-parse HEAD`, and live target before mutation; the actual assigned BASE includes the root-approved design/plan commit above original source `11eb869c`. If target moved, parent records the new composition requirement. Merge the pinned target with `git merge --no-commit --no-ff 256035f16c996fde6cd7e56849920f451e4bf033`. Record the actual GET/POST conflicts. Do not remove the cap or classifier to make either side compile.
- [ ] **Step 2: Resolve the two transport hunks.** Retain classifier build/send mappings, per-instance field/default/validation, separate body deadline and native account 65536-byte cap. Both verbs finish with `read_bounded(resp, self.max_response_bytes)`.
- [ ] **Step 3: Select missing tests in existing jobs.** Add the debug combined-feature command below to Linux `rust`; add the exact Hosted command to `operator`; add mixed-cutoff Hosted and explicit pilot children to `operator-native`. Preserve the five existing pilot phases and sole parser; add the new pilot parent to `before-bin` required names. New gate steps retain `!cancelled()`; Linux-only trust-store step also checks `runner.os == 'Linux'`.

Commands below run in the named CI job's existing working directory. They are planned commands, not evidence of execution.

`rust` (`implementation/desktop`):

```bash
cargo test -p selahcue-cloud --features http,openai --test test_tls_system_store_linux --no-fail-fast
```

`operator` (`implementation/desktop/crates/selahcue-operator`):

```bash
cargo test --features cloud-live --bin selahcue-operator --no-fail-fast regenerate_with_retention_tests::hosted_construction_fallback_respects_preflight_and_saves_or_stages -- --exact
```

`operator-native` uses `SELAHCUE_PILOT_CONFIG_PATH=${{ github.workspace }}/implementation/desktop/crates/selahcue-operator/tests/fixtures/pilot-valid.json`. Run the same Hosted name with `--release --features pilot-credentials,cloud-live` and env `SELAHCUE_PILOT_TEST_EPOCH=1809129599`, `PILOT_TEST_EXPECT_READY=0`, `PILOT_MIXED_EXPECT_EXPIRED=1`.

Ready pilot uses epoch `1809125999`, `PILOT_TEST_EXPECT_READY=1`, `PILOT_MIXED_EXPECT_EXPIRED=0`; unset `SELAHCUE_CLOUD_URL` for these Direct cases:

```bash
cargo test --release --features pilot-credentials,cloud-live --bin selahcue-operator --no-fail-fast regenerate_with_retention_tests::pilot_construction_fallback_preserves_terminal_policy -- --exact
```

Run that exact command separately for each row, setting `SELAHCUE_PILOT_CONSTRUCTION_TEST_CASE` and `SELAHCUE_PILOT_TEST_EPOCH`. The env field is the existing test's child entry interface, not an application configuration change:

| Child case | Epoch | Required observed behavior |
| --- | --- | --- |
| expired | 1809129599 | pilot_expired; zero builds/writes |
| terminal | 1809125999 | not_configured; no persistence |
| admitted | 1809125999 | one build; fallback staged; accepted draft retained; explicit promotion |
| build-rejected | 1809125999 | pilot_access_rejected; accepted/pending unchanged |
| build-expired | 1809129596 | actual admitted builder crosses cutoff, local fallback then pilot_expired; no write |
| late | 1809125999 | rejection after fallback; accepted/pending unchanged |

Each selection must retain its label, epoch, exact named `... ok` and `test result: ok. 1 passed` receipt. Use pipefail when teeing and explicit UTF-8 decoding for receipt parsing. Parent ready execution proves orchestration; explicit children make its otherwise captured stdout independently inspectable. Preserve existing mutex-wait test in the ready `pilot_` suite.

- [ ] **Step 4: Verify workflow compatibility with existing checks.** From root, run the existing checks on an admitted host or in hosted CI: `python3 .github/scripts/check_workflows.py`, `python3 .github/scripts/check_ci_minutes.py`, `python3 .github/scripts/test_native_test_receipts.py`, and actionlint from the owning workflow. Do not install dependencies locally under the resource hold. Verify no new job/matrix/timeout/dependency changes and no config-only tests were added. These checks do not establish behavioral test execution.
- [ ] **Step 5: Commit the reviewed merge composition and selections.** Stage only owned changes; preserve both parents. Verify `git merge-base --is-ancestor 11eb869c8bd51bf2070cc74e071e7365341e1cc5 HEAD` and `git merge-base --is-ancestor 256035f16c996fde6cd7e56849920f451e4bf033 HEAD`. Parent publishes through the authorized PR398 repair workflow without rewriting unrelated history.
- [ ] **Step 6: Capture actual hosted RED and feature evidence.** Require owning `Webview behavioural check (Linux, headless Chrome)` with `SELAHCUE_HEADLESS_REQUIRE=1`, executing `python3 scripts/operator_headless.py` from root. Archive run SHA/ID, exit condition, full observed count, zero assertion failures and both exact names:
  - `TR cloud fallback: the fixed certificate reason renders as immediate plain text`
  - `TR cloud fallback: an unclassified transport failure keeps the generic notice`
  A billing failure, missing Chrome, cancellation, earlier preflight failure or unseen assertion is not this RED. Resolve actual failures within scope before count correction; never fabricate a total.

### Task 2: Correct measured count and qualify final source

**Files:**
- Modify: only the authoritative final expected-count assignment/comment in `scripts/operator_headless.py`, using Task 1 evidence.
- Evidence update: existing Goal Contract ledger and parent release-evidence report; preserve C-005 local UNRUN.
- Conditional fixes: only observed in-scope failures, with behavioral regression checks and fresh review.

**Interfaces:**
- Consumes Task 1 measured Chrome receipt and composed commit.
- Produces final exact-source CI receipts, four independent review verdicts and a merge-ready source/tree handoff; no native release claim.

- [ ] **Step 1: Apply the smallest measured correction.** Set authoritative `EXPECTED_MIN_CHECKS` to the exact Task 1 observed total; cite the run in evidence/comment. Retain exact equality, both assertions and required Chrome. Do not lower a count or bypass checks to obtain GREEN.
- [ ] **Step 2: Rerun the same owning Chrome gate.** Require exit 0, the same measured count, both named PASS outcomes and zero failures. Any changed total requires investigation and fresh measurement.
- [ ] **Step 3: Qualify transport, features and persistence on final source.** Preserve existing full cloud default/http/openai debug/release and operator suites. In `implementation/desktop`, the key actual controls are:

```bash
cargo test -p selahcue-cloud --test test_fallback --no-fail-fast
cargo test -p selahcue-cloud --features http --no-fail-fast
cargo test -p selahcue-cloud --features http,openai --test test_tls_system_store_linux --no-fail-fast
cargo test -p selahcue-cloud --features openai --no-fail-fast
cargo test -p selahcue-cloud --features openai --release --no-fail-fast
```

Require named `per_instance_response_limit_refuses_out_of_range_values`, `a_smaller_cap_stops_get_and_post_while_the_chunked_response_is_still_open`, trusted/untrusted/name/expiry TLS controls, stall/drip deadline controls and Step 1's exact operator selections. Loopback uses the existing `NO_PROXY=127.0.0.1,localhost` policy. No live TLS/provider probe is authorized. Dependency integration tests are not satisfied by compiling an operator feature.

- [ ] **Step 4: Commit and run full current-source hosted CI.** Parent records the final SHA and archives the automatic PR398 run created by the authorized push when it selects every required gate. Only if that event omits a required area does parent use the existing all-area dispatch on the actual remote PR398 branch, with the authorized Windows tier. Do not duplicate a complete current-source run. Verify the run head is the candidate; all required source gates must execute successfully, including audits. Existing Windows qualification remains whatever the authorized tier actually runs; no macOS result is implied. Re-run affected checks after a source-changing fix, and refresh the final composition evidence.
- [ ] **Step 5: Re-review and deliver through parent.** Cody, Shadow, Quinn and Vera review the final source and actual evidence. Return every requested change to the implementer and re-review the resulting SHA. Parent verifies live target, merge tree/ancestry, performs the authorized merge only when source gates pass, then rereads exact ClickUp QA state. Keep native/local qualification and historical failures explicit; never mark original C-005 fully PASS from hosted evidence.

Self-review: every consolidated finding maps to Task 1/2; signatures/epochs/test names were checked against source and pinned target. No implementation, runtime testing, commits or publication occurred while authoring this plan.
