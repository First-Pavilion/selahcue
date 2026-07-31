# Code Review — Batch: operator webview behavioural CI gate (audit #9, 86ajq0569)

- **Scope:** close the test-integrity gap the M2/M3/M4 review surfaced — the operator webview (`dist/app.js`) had **no committed JS test runner**, so its behavioural checks (console render, plan-dedup, transcript cap, Theme-Designer wiring) were verified only by a dev-time scratchpad harness and were never CI-gated. Port the proven harness (63 checks) into the repo and wire it into `make ci` + the CI `operator` job so those checks become a durable regression gate. Executed via `/goal` (`TASK-86ajq0569-operator-headless-ci.md`, validator PASS `--require-complete`). Test-only tooling (`scripts/` + `Makefile` + `ci.yml`); **no product change**.
- **Method:** an adversarial Workflow review (portability/false-pass · does-it-actually-gate lenses → refute-by-default) **plus** empirical proofs (a mutation bite + the CI-runner execution log + exit-path guards). Candid note: the review agents returned **placeholder stubs** on two runs (a model anomaly, not a real verdict), so the false-pass audit below was done by hand; the review was re-run with an explicit anti-stub instruction for an independent second opinion.
- **Outcome:** one real gap found by the self-audit (no minimum-check-count guard → a silently-shrinking suite could false-pass) — **fixed**. The gate is empirically proven to bite.

## What shipped

- **`scripts/operator_headless.py`** — the ported harness, made portable:
  - **repo-relative `DIST`** (from `__file__`) + a `SELAHCUE_OPERATOR_DIST` override (for a staged/mutated copy).
  - **`find_chrome()`** — `CHROME_BIN` → `shutil.which` (google-chrome/chromium) → the macOS app bundle; runs on macOS (dev) + `ubuntu-latest` (CI, google-chrome-stable pre-installed).
  - **`SELAHCUE_HEADLESS_REQUIRE=1`** — a missing Chrome is a hard failure (exit 3) so the CI gate can never silently no-op; without it, a missing Chrome exits 0 with a SKIP notice so `make ci` on a Chrome-less dev box still passes.
  - **`EXPECTED_MIN_CHECKS=63`** — exit 4 if the `DONE(n)` count drops below the floor (the suite must not silently shrink).
- **`Makefile`** — an `operator-headless` target + a call from `ci`.
- **`.github/workflows/ci.yml`** — a `Webview behavioural check (Linux, headless Chrome)` step in the `operator` job (`if: runner.os == 'Linux'`, `working-directory: ${{ github.workspace }}`, `SELAHCUE_HEADLESS_REQUIRE=1`).

## False-pass audit (the exit-code contract)

The harness must NEVER exit 0 unless the checks actually ran and all passed. Every failure path was traced:

| Scenario | Exit | Correct? |
|---|---|---|
| No RESULTS block (Chrome crashed / DOM never produced) | 2 | ✅ fail |
| Chrome process times out (90s) | non-zero (uncaught `TimeoutExpired`) | ✅ fail |
| RESULTS block with ≥1 `FAIL:` line | 1 | ✅ fail |
| `DONE(n)` count `< EXPECTED_MIN_CHECKS` (suite silently shrank) | 4 | ✅ fail (added this batch) |
| Missing Chrome + `SELAHCUE_HEADLESS_REQUIRE=1` | 3 | ✅ fail |
| RESULTS block, count ≥ floor, 0 FAIL | 0 | ✅ pass |

The **min-check-count guard was the one gap** — before it, a driver regression that ran fewer `ok()` calls would report `0 FAIL` and exit 0. Now the count is asserted against a floor.

## Verification (empirical)

- **Runs portably:** `python3 scripts/operator_headless.py` → **63 checks / 0 FAIL** (exit 0) on macOS; `make operator-headless` green; `find_chrome()` returns `None` correctly when no browser exists (→ require:3 / skip:0).
- **Gate bites (mutation):** a `dist/` copy with the M4 slice removed → **2 FAIL, exit 1**; the pristine dist → exit 0. A floor bumped to 64 → **exit 4**. So a real behavioural regression *and* a shrunk suite both fail.
- **Runs in CI (not just green):** CI `30652466817` `completed → success`; the **operator-Linux job log** shows the step ran with `SELAHCUE_HEADLESS_REQUIRE: 1` and printed the PASS lines + `=== 63 checks, 0 FAIL ===` — proving Chrome launched and the M1/M4 assertions executed on the runner.
- **YAML valid** (`yaml.safe_load`; operator job = 7 steps). fmt/clippy unaffected (Python/YAML/Makefile only).

## Adversarial review

Two lenses (portability/false-pass · does-it-actually-gate) → refute-by-default verify. **The first two runs returned placeholder stubs** (a model anomaly, discarded); the re-run with an explicit anti-stub instruction (`wf_1d8e9056-4da`) produced real analysis. The portability lens **confirmed there is NO exit-0 false-pass path** (exit 0 requires either the legitimate no-Chrome skip or a matched RESULTS block with count ≥ floor and zero FAIL; everything else fails **closed** — no-RESULTS/crash → 2, count < floor → 4, any FAIL → 1, timeout → 2) and that the floor is tight (63 = the exact happy-path count). The ci-wiring lens **confirmed the gate is genuinely wired** (repo-root working-directory, `REQUIRE=1`, the `desktop` changes-filter triggers it, `make ci` aborts on non-zero).

| # | Lens | Sev (raised→verified) | Finding | Disposition |
|---|------|------|---------|-------------|
| 1 | portability | MEDIUM → **REFUTED** | "Gate rides on unpinned ubuntu Chrome + fixed boot `sleep(260)` — a Chrome bump / app.js boot growth could break it." | **Refuted** by verify: it fails **closed** (spurious RED, not a false green) — CI-noise/durability, not a false pass. Kept as a LOW hardening follow-up (**#11**: pin Chrome + poll for `render_console` vs a fixed sleep). |
| 2 | ci-wiring | MEDIUM | Blink-only coverage — Tauri ships WebKitGTK/WKWebView/WebView2, so engine-specific regressions aren't caught. | **Documented** as a known fidelity gap (harness docstring): the gate covers browser-portable DOM/JS logic (its stated scope); the real webview stays owner-run. Follow-up **#10** (WebKit smoke) queued. |
| 3 | both | LOW | A vacuous `ok(true, "bounded guard…")` padded the check floor (asserted nothing). | **Fixed** — dropped it; the MAX_ELEMENTS=64 cap is already host-side Rust-tested. Floor retightened to the real count. |
| 4 | ci-wiring | LOW | `make ci` runs the harness without `REQUIRE=1`, so a Chrome-less dev box prints "ALL GREEN" while the gate silently skipped. | **Fixed** — the skip now prints a LOUD multi-line `!! WEBVIEW BEHAVIOURAL GATE SKIPPED` banner so it can't be misread (graceful skip kept so a Chrome-less `make ci` still runs the Rust gates). |
| 5 | portability | LOW | The `#3 click-select` check silently degraded to `ok(true)` when layout width ≤ 10 (a vacuous fallback). | **Fixed** — replaced the fallback with a real precondition assertion (`box width > 10`) so the hit-test can never be silently skipped. |
| 6 | portability | INFO | Robustness: `TimeoutExpired` reported exit 1 (looks like a check-fail) not 2; `text=True` without encoding; hardcoded `/tmp`. All fail-closed. | **Fixed** — `except TimeoutExpired → exit 2`; `encoding="utf-8", errors="replace"`; `tempfile.gettempdir()`. |

**No HIGH; no false-pass path.** All actionable findings fixed except the two documented DEVOPS follow-ups (#10 engine fidelity, #11 Chrome-pin/poll durability), both LOW and both fail-closed.

## Coverage note + follow-ups

- **Linux-only** headless step (browser-portable DOM behaviour; Chrome path/availability varies on macOS/Windows runners) — an accepted, documented scope; the static `test_tokens.rs`/`test_keymap.rs` content pins still run on all three OSes.
- The harness covers the currently-written 63 checks; as the operator webview grows, add checks and bump `EXPECTED_MIN_CHECKS`.
- Remaining audit follow-ups unchanged: **M5** console RGBA decode (PERF); the LOW cluster (L1/L3, #8 M3 re-pair/idle-TTL).
