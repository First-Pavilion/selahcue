# Code Review — Batch: webview test-infra (#10 WebKit smoke + #11 poll, 86ajq0569)

- **Scope:** the last two audit follow-ups on the operator-webview harness — **#11** replace the Chrome harness's fixed boot-render `sleep(260)` with a bounded poll (durability), and **#10** add a WebKit-engine boot smoke (fidelity) since the committed gate drives Blink, not the WebKit engine Tauri ships on. Executed via `/goal` (`TASK-86ajq0569-webview-testinfra.md`, validator PASS `--require-complete`). Test-only tooling (`scripts/` + `ci.yml`); no product change.
- **Method:** an adversarial Workflow review (bite-falsepass · ci-wiring lenses → refute-by-default) `wf_9095cf04-439` (the first run stubbed; re-run with an anti-stub instruction) **plus** empirical proofs (mutation bites + the CI runner logs).
- **Outcome:** **bite-falsepass INFO×2 (both gates sound, no false-pass); ci-wiring 1 MEDIUM + 2 LOW — all CI-durability, all fixed.**

## What shipped

- **#11** (`operator_headless.py`): a bounded `waitFor(pred, tries=150)` poll (20ms/try of virtual time) + `hasRender(id)` replace the fixed boot-render `sleep(260)` and the available:false `sleep(180)`. The gate waits exactly as long as the boot render needs; the check count is unchanged (66). Mutation-proven: a dist copy where `has-render` is never applied → the poll times out (no hang) → the two #7 checks FAIL, exit 1.
- **#10** (`operator_webkit_smoke.py`, new): a Playwright-WebKit boot smoke — inject the `__TAURI__` stub, load the real `dist/index.html`, assert no `pageerror`, the boot poll ran (`view`), the render path ran (`render_console`), the panel reached `has-render`, and the canvas drew 2×1 (base64 decode + putImageData on WebKit). `SELAHCUE_WEBKIT_REQUIRE=1` → hard fail if the engine is missing, else a loud skip. Mutation-proven: a JS error at boot → 5 FAIL, exit 1, reporting WebKit's own `undefined is not an object`.
- **CI** (`ci.yml`): the operator job (Linux) installs Playwright + WebKit and runs the smoke `REQUIRE=1`.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | ci-wiring | MEDIUM | `pip install --user playwright` could refuse on a PEP-668 externally-managed runner image (Ubuntu 24.04+) — fails LOUD (job red at install), never a silent green. | **Fixed** — `--break-system-packages` on the install, so it works whether or not the image is marked. |
| 2 | ci-wiring | LOW | playwright unpinned → the WebKit engine is a moving target (spurious RED on a future breaking release). | **Fixed** — pinned `playwright==1.60.0` (bump deliberately). |
| 3 | ci-wiring | LOW | The operator job had no `timeout-minutes` (sibling launch-smoke caps at 20), so a wedged install/apt step could run toward GitHub's 6h default. | **Fixed** — `timeout-minutes: 25` on the operator job. |
| 4 | bite-falsepass | INFO | The skip guard caught a missing Playwright *package* (ImportError) but not a missing WebKit *browser binary* — `p.webkit.launch()` would raise uncaught (correct RED in CI, but a raw crash on a dev box without REQUIRE). | **Fixed** — extracted `skip_or_fail()` and wrapped the launch, so a missing engine is a hard fail under REQUIRE, else a loud dev skip. |
| 5 | bite-falsepass | INFO | The WebKit smoke uses an 8s wall-clock `wait_for_function` timeout (vs the Chrome harness's virtual time) — a small flake surface on a heavily-loaded runner. Fail-RED, never false-pass. | **Accept** — 8s is generous; the reviewer says raise (not lower) it if flakes ever appear. |
| 6 | bite-falsepass / ci-wiring | INFO | Confirmed: both gates are hard-bounded + fail-closed (no false-pass path); the WebKit smoke genuinely runs + gates on the Linux runner (working-directory, REQUIRE, changes-filter all correct; no silent-green path). | No change. |

**No HIGH; no false-pass.** All actionable findings fixed; one INFO accepted as-is.

## Verification (empirical)

- **Both gates run in CI (proven):** CI `30686139914` `completed → success`; the operator-Linux logs show `=== 66 checks, 0 FAIL ===` (Chrome, with the #11 poll) **and** `=== WebKit smoke: 5 checks, 0 FAIL ===` (real WebKit — Playwright installed + `--with-deps webkit` + the smoke passed). This is the definitive validation that Playwright+WebKit works on the runner.
- **Both gates bite (mutation):** #11 → a broken boot render times out → 2 FAIL exit 1 (no hang); #10 → a JS error → 5 FAIL exit 1 with the WebKit-specific message.
- **Local:** Chrome harness 66/0; WebKit smoke 5/5 on real WebKit (AppleWebKit UA); `py_compile` clean; YAML valid.
- **CI (hardened):** re-run — pending this push (verified by conclusion + both runner logs).

## Follow-ups

- The whole audit is now closed through this batch. Optional future: a WKWebView-on-macOS / WebView2-on-Windows smoke (Playwright-WebKit is the cross-platform proxy today); bump the pinned `playwright` deliberately.
