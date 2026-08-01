# Goal Contract — TASK-86ajq0569-webview-testinfra

## Identity

- Goal ID: TASK-86ajq0569-webview-testinfra
- Parent goal ID: BUILD-selahcue (Stage 8 quality — audit follow-ups #10 + #11)
- Title: Webview test-infra hardening — WebKit-engine fidelity smoke (#10) + poll the boot render instead of a fixed sleep (#11)
- Role: devops-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited — audit report §4 #10/#11)
- Created: 2026-08-01
- Independent verification required: yes (adversarial review + both harnesses run in CI)
- Maximum iterations: 10

## Objective

Close the last two audit follow-ups on the operator-webview test harness:
- **#11 (durability):** the committed Chrome harness waits for the boot render with a **fixed `sleep(260)`**, so app.js boot-timing growth (or a Chrome change) could spuriously RED the gate. Replace the fixed sleeps with a **poll** for the actual signal (e.g. the `render_console` call / a DOM condition) up to a bounded timeout — so the gate waits exactly as long as needed and only fails on a genuine regression.
- **#10 (engine fidelity):** the committed gate drives **Blink** (headless Chrome), not the WebKit engine Tauri ships on (WebKitGTK/WKWebView). Add a **WebKit-engine smoke** (Playwright's WebKit — the same JavaScriptCore/WebCore core, headless + cross-platform, testable on macOS dev + Linux CI) that loads the real `dist/` and asserts the app **boots on WebKit without a JS error** and the console-render path runs — catching an engine-specific JS/API break the Blink gate can't. Minimal boot smoke (not a full re-port); wired into CI with a `REQUIRE`/skip pattern like the Chrome gate.

## Baseline

Verified: `scripts/operator_headless.py` (audit #9) runs the real `dist/` under headless Chrome (`--headless=new --dump-dom`), with `EXPECTED_MIN_CHECKS`, a `REQUIRE`/loud-skip Chrome gate, and a fixed `await sleep(260)` before the boot-render checks (+ smaller fixed sleeps at ~147/191). The CI `operator` job (Linux) runs it with `SELAHCUE_HEADLESS_REQUIRE=1`. Playwright's WebKit runs headlessly on macOS + Linux (JavaScriptCore/WebCore — Tauri's engines are WebKitGTK/WKWebView, same core). The operator CI job already installs `libwebkit2gtk-4.1-dev`, but Playwright bundles its own WebKit (self-contained, no GTK-version coupling).

## Scope

### In scope

- **#11:** a `wait_for(pred, timeout)` poll in the harness driver replacing the fixed boot-render `sleep` — poll until `render_console` has fired (and the panels are ready) up to a bounded timeout (fail if it never fires). Keep the harness deterministic (bounded timeout + the existing `--virtual-time-budget`); the check count is unchanged.
- **#10:** `scripts/operator_webkit_smoke.py` — a Playwright-WebKit boot smoke: inject the `__TAURI__` stub, load the real `dist/index.html`, assert (a) no uncaught JS error/`pageerror`, (b) the boot render path ran (`render_console` invoked), (c) the console panels reached `has-render`. A `SELAHCUE_WEBKIT_REQUIRE=1` gate (missing Playwright/WebKit → hard fail in CI; else a loud skip). Wire into the CI `operator` job (Linux): install Playwright + WebKit, run the smoke required.
- Both: a mutation/self-check that each gate BITES; documented as engine-portable-JS gates.

### Non-goals

- Re-porting all 66 Chrome checks to WebKit (the boot smoke is the fidelity signal); WKWebView-on-macOS or WebView2-on-Windows drivers (Playwright-WebKit is the cross-platform proxy). No product change.

### Constraints

- Deterministic + non-flaky (bounded timeouts; both gates fail closed). Testable locally (macOS) before CI. The Chrome gate stays green (66 checks). CI green (verified by conclusion + both runner logs). `fmt`/`clippy` unaffected (Python/YAML only).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | #11: the Chrome harness polls for the boot render (bounded timeout) instead of a fixed sleep; still 66/0 locally; fails if the render never fires | `python3 scripts/operator_headless.py` (+ a no-render mutation) | 66/0; polls; fails-closed on no render | harness (`waitFor`); 66/0; mutation (no has-render) → times out → 2 FAIL exit 1 (no hang) | PASS |
| C-002 | yes | #10: `operator_webkit_smoke.py` loads the real dist/ under Playwright-WebKit and asserts boot (no JS error) + render path ran; passes locally; a mutation (inject a JS error) makes it FAIL; missing WebKit + REQUIRE=1 fails, else skips | `python3 scripts/operator_webkit_smoke.py` (+ mutation + skip check) | boot smoke passes; bites on a JS error; require/skip correct | smoke 5/5 on real WebKit; JS-error mutation → 5 FAIL exit 1 (WebKit-specific error); ImportError → require:3/skip:0 | PASS |
| C-003 | yes | Both wired into the CI operator job (Linux, REQUIRE=1); 3-OS CI green (verified by conclusion + both runner logs show the gates ran) | push + `gh run view --json conclusion` + logs | both gates run on Linux; overall success | CI run | PENDING |
| C-004 | yes | Gate: independent adversarial review (does each gate actually bite / no false-pass / determinism), findings fixed | Workflow review | review clean/fixed | CODE-REVIEW doc | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Local (macOS): the Chrome harness still 66/0 after the poll refactor + fails if the render is stubbed off; the WebKit smoke passes on Playwright-WebKit + FAILS when a JS error is injected + skips/requires correctly. Broader: 3-OS CI (both gates run on the Linux operator job), verified by conclusion + the runner logs. Independent: an adversarial Workflow review (poll bounded + fails-closed; WebKit smoke actually loads+asserts on WebKit, no false-pass; both deterministic).
- Required environment: local (macOS + Playwright-WebKit) + CI (Linux, Playwright-WebKit + Chrome).

## Iteration ledger

- Iter 0 (C-001, #11): added a bounded `waitFor(pred, tries)` poll + a `hasRender(id)` helper to the Chrome harness driver; replaced the fixed boot-render `sleep(260)` with `waitFor(() => hasRender("preview-panel") && hasRender("live-panel"))` and the available:false re-render `sleep(180)` with a poll for the fallback. The gate now waits exactly as long as the boot render needs (deterministic, bounded to 150×20ms virtual). Evidence: harness **66/0**; a mutation (a dist copy where `has-render` is never toggled) → the poll times out (no hang) and the two #7 has-render checks **FAIL** → exit 1. Result: PASS.
- Iter 1 (C-002, #10): `scripts/operator_webkit_smoke.py` — a Playwright-WebKit boot smoke: inject the `__TAURI__` stub, load the real `dist/index.html`, assert no `pageerror`, the boot poll ran (`view`), the render path ran (`render_console`), the panel reached `has-render`, and the preview canvas is drawn 2×1 (base64 decode + putImageData work on WebKit). `SELAHCUE_WEBKIT_REQUIRE=1` → hard fail if Playwright/WebKit is missing; else a loud skip. Evidence: **5/5 on the real WebKit engine** (Playwright WebKit = JavaScriptCore/WebCore); a JS-error mutation → 5 FAIL exit 1 with the WebKit-specific message (`undefined is not an object` — Safari phrasing, not Chrome's); `py_compile` clean. Result: PASS.
- Iter 2 (C-003 wiring): `.github/workflows/ci.yml` — after the Chrome step, an `Install Playwright WebKit (Linux)` step (`pip install --user playwright` + `playwright install --with-deps webkit`) + a `Webview WebKit-engine smoke (Linux)` step (`SELAHCUE_WEBKIT_REQUIRE=1`). YAML validates; operator job now 9 steps. CI: pending this push (verified by conclusion + both runner logs).

## Risks and rollback

- Risks: a flaky poll (mitigated: bounded timeout + `--virtual-time-budget`; poll on the concrete `render_console` signal). Playwright/WebKit adds a CI dependency (mitigated: install step + a REQUIRE/skip so a setup failure is diagnosable, not a silent no-op; self-contained WebKit, no GTK coupling). A WebKit smoke that silently passes without loading (mitigated: a JS-error mutation proves it bites + a boot-render assertion). Rollback: git; test-only tooling (scripts/ + ci.yml), no product change.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq0569-webview-testinfra.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- ClickUp final evidence comment: (pending — MCP rate-limited; closes audit report §4 #10 + #11)
