# Goal Contract — TASK-86ajq0569-operator-headless-ci

## Identity

- Goal ID: TASK-86ajq0569-operator-headless-ci
- Parent goal ID: BUILD-selahcue (Stage 8 quality — audit follow-up #9)
- Title: Commit the operator-webview behavioural test harness + wire it into `make ci` and CI (close the test-integrity gap)
- Role: devops-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited — audit report §4 #9)
- Created: 2026-07-31
- Independent verification required: yes (adversarial review + CI shows the harness actually running + a mutation check)
- Maximum iterations: 8

## Objective

Close audit follow-up **#9** (surfaced by the M2/M3/M4 review): the operator webview (`dist/app.js`) has **no committed JS test runner** — all behavioural checks (`syncTranscript` cap, plan-dedup, console render, designer wiring) were verified only by a **dev-time** headless harness living in the session scratchpad, so they were never CI-gated. Commit a **portable** headless harness into the repo, wire it into `make ci` (graceful skip if Chrome absent) and the CI **operator** job (Linux, required), so those behavioural checks become durable regression gates. Reuse the proven scratchpad harness (63 checks incl. the M1 plan-dedup + M4 transcript-cap assertions) — port, don't rewrite.

## Baseline

Verified: the scratchpad harness (`td_headless.py`) injects a `window.__TAURI__` stub + a driver into a copy of the real `dist/index.html`, runs headless Chrome (`--headless=new --dump-dom --no-sandbox --virtual-time-budget`), and parses a `RESULTS…DONE(n)` block for PASS/FAIL (63/63 today). Its `DIST`/`CHROME` are hardcoded macOS absolute paths. `make ci` (Makefile:78-93) runs fmt/clippy/test/check + flutter — no operator JS step. The CI `operator` job (ci.yml, ubuntu/macos/windows) runs fmt/check/clippy only. In-repo, `scripts/` holds the other CI helpers (`measure_nfr.sh`, validators); GitHub's `ubuntu-latest` ships `google-chrome-stable`. `test_tokens.rs`/`test_keymap.rs` already statically pin `dist/` content (CI-gated), but no committed test exercises the JS behaviour.

## Scope

### In scope

- Commit `scripts/operator_headless.py`: the ported harness with (1) **repo-relative** `DIST` (resolved from the script location), (2) **Chrome auto-detection** (`CHROME_BIN` env → `shutil.which` over google-chrome/chromium names → the macOS app path), (3) a `SELAHCUE_HEADLESS_REQUIRE=1` env that makes a MISSING Chrome a hard FAILURE (for CI) while a missing Chrome without it exits 0 with a SKIP notice (so `make ci` on a Chrome-less dev box doesn't break). Same 63 behavioural checks.
- `Makefile`: an `operator-headless` target (`python3 scripts/operator_headless.py`) + call it from `ci` (graceful-skip locally).
- `.github/workflows/ci.yml`: a step in the `operator` job (Linux only) running the harness with `SELAHCUE_HEADLESS_REQUIRE=1`, so a missing Chrome or any FAIL reddens CI.

### Non-goals

- A full jsdom/Node rewrite or layout/canvas-heavy assertions beyond what the Chrome harness already covers (the harness runs REAL Chrome, so layout/CSS/canvas checks work as-is).
- Running the headless step on macOS/Windows CI runners (Chrome path/availability varies; the Linux gate is sufficient for browser-portable DOM behaviour — documented).
- New product behaviour; the harness is test-only tooling.

### Constraints

- Deterministic + non-flaky (bounded `--virtual-time-budget` + a 90s process timeout; the harness already polls for readiness). The committed harness must reproduce the scratchpad's 63/0 locally. No change to `dist/` product files. Portable (macOS dev + Linux CI). fmt/clippy unaffected (Python + YAML + Makefile only).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The committed `scripts/operator_headless.py` runs the behavioural checks portably (repo-relative dist, Chrome auto-detect) and reproduces 63/0 locally; missing Chrome + REQUIRE=1 fails, without it skips (exit 0) | `python3 scripts/operator_headless.py` (+ a REQUIRE/skip check) | 63 checks / 0 FAIL locally; require-fail + skip both correct | harness run | PENDING |
| C-002 | yes | `make ci` invokes the harness (graceful skip if Chrome absent); the `ci` target still passes end-to-end | `make operator-headless` + review `ci` target | wired; local ci gate green | Makefile diff | PENDING |
| C-003 | yes | The CI `operator` job runs the harness on Linux with REQUIRE=1; 3-OS CI green (verified by run CONCLUSION) with the operator-Linux log showing the harness ran (`N checks, 0 FAIL`) | push + `gh run view --json conclusion` + job log | operator-Linux runs the harness; overall success | CI run | PENDING |
| C-004 | yes | A mutation check proves the gate BITES: temporarily breaking a pinned behaviour (locally) makes the harness FAIL non-zero; independent adversarial review, findings fixed | local mutation + Workflow review | harness fails on a regression; review clean | mutation note; review | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Local: run the harness (63/0); simulate a missing Chrome (`CHROME_BIN=/nonexistent` with/without `SELAHCUE_HEADLESS_REQUIRE`) → require-fail vs skip-0; a mutation (temporarily revert the M4 slice in a scratch copy or point at a broken dist) → the harness FAILs (C-004 bite proof). `make operator-headless`. Broader: push → the CI operator-Linux job runs it; verify the 3-OS CI by run conclusion + the operator-Linux log line `N checks, 0 FAIL`. Independent: adversarial Workflow review (harness-portability/determinism · CI-wiring-correctness/does-it-actually-gate lenses).
- Required environment: local (macOS Chrome) + CI (Linux google-chrome-stable).

## Iteration ledger

- Iter 0 (C-001): ported the scratchpad harness to `scripts/operator_headless.py` — repo-relative `DIST` (from `__file__`) with a `SELAHCUE_OPERATOR_DIST` override, `find_chrome()` (CHROME_BIN → `shutil.which` google-chrome/chromium → macOS app path), and a `SELAHCUE_HEADLESS_REQUIRE=1` gate (missing Chrome → exit 3; else SKIP exit 0). Reproduces **63 checks / 0 FAIL** locally; the find_chrome None-path returns None correctly (→ require:3 / skip:0). Result: PASS.
- Iter 1 (C-002): `Makefile` — new `operator-headless` target + a call from `ci` (`python3 scripts/operator_headless.py`, graceful-skip locally). `make operator-headless` → 63/0. Result: PASS.
- Iter 2 (C-004 mutation bite): copied `dist/` to a temp dir, removed the M4 slice, ran with `SELAHCUE_OPERATOR_DIST=<copy>` → the harness reported **2 FAIL and exited 1**; the pristine dist exits 0. Proves the gate BITES on a real behavioural regression. (Independent adversarial review: pending.)
- Iter 3 (C-003 wiring): `.github/workflows/ci.yml` — a `Webview behavioural check (Linux, headless Chrome)` step in the `operator` job (`if: runner.os == 'Linux'`, `working-directory: ${{ github.workspace }}`, `SELAHCUE_HEADLESS_REQUIRE=1`). YAML validates; operator job now has 7 steps. CI run: pending this push (verified by conclusion + the operator-Linux log `N checks, 0 FAIL`).

## Risks and rollback

- Risks: flaky headless run in CI (mitigated: bounded virtual-time + a generous process timeout + the readiness poll; the harness is deterministic DOM logic, not timing-sensitive rendering). Chrome absent on the CI runner (mitigated: `ubuntu-latest` ships google-chrome-stable; REQUIRE=1 turns a missing Chrome into a hard fail so the gate can't silently no-op). A silent no-op gate (mitigated: the C-004 mutation check proves it bites; CI log asserts `0 FAIL` over a real check count). Rollback: git; test-only tooling (scripts/ + Makefile + ci.yml), no product change.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq0569-operator-headless-ci.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- ClickUp final evidence comment: (pending — MCP rate-limited; closes audit report §4 #9)
