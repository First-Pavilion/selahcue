# Goal Contract — TASK-86ajtwq28-console-decode-perf

## Identity

- Goal ID: TASK-86ajtwq28-console-decode-perf
- Parent goal ID: BUILD-selahcue (Stage 8 quality — audit follow-up M5)
- Title: Decode the console/designer RGBA thumbnails off the slow per-byte path
- Role: frontend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited — audit report §4 #5)
- Created: 2026-07-31
- Independent verification required: yes (adversarial review + a byte-exact pixel-readback check in the committed headless gate)
- Maximum iterations: 6

## Objective

Close audit follow-up **M5**: the operator webview decodes base64 RGBA frames with `Uint8Array.from(atob(rgba), (c) => c.charCodeAt(0))` — V8's slow path (a JS closure invoked per byte) — for ≤640×360×4 frames (~0.9 MB each) synchronously on the main thread. It is well-gated (resolution-capped, debounced 120 ms, signature-deduped, console-surface-gated), so it fires only on real output changes, not every poll — but the decode itself is the single heaviest synchronous op. Replace the per-byte callback with a **tight indexed loop** into a preallocated `Uint8Array`, at both decode sites (the console preview/live `drawConsoleFrame` and the Theme-Designer preview). Output must be **byte-identical** (same pixels), so it is a pure speed fix.

## Baseline

Verified from code (`dist/app.js`): `drawConsoleFrame` (L304-335) decodes at L313 via `Uint8Array.from(atob(frame.rgba), (c) => c.charCodeAt(0))` then `putImageData` (L325) after a length guard (L318). The Theme-Designer preview uses the identical slow form at L1034. Both are correct but use the per-byte-callback form (V8 slow path). The committed headless gate (`scripts/operator_headless.py`, audit #9) already asserts the console render fires + the canvas dimensions; it does NOT yet assert the decoded pixel values.

## Scope

### In scope

- A shared `b64ToBytes(b64)` helper: `atob` once, then a plain indexed `for` loop into a preallocated `Uint8Array` (JIT-friendly; no per-byte closure). Replace both decode sites (`drawConsoleFrame` L313 + the designer preview L1034) with it. The existing length guard + try/catch stay.
- A **pixel-readback** check in the committed headless harness: after the boot console render, read `getImageData` from the preview canvas and assert the decoded pixels match the stub's known RGBA bytes (red/green) — proving the new decode is byte-exact. Bump `EXPECTED_MIN_CHECKS` accordingly.

### Non-goals

- Moving the decode off-thread (`createImageBitmap`/OffscreenCanvas worker) — a larger change; the tight loop is the high-value, low-risk win this slice. Noted as a seam.
- Any host/wire/protocol change; any change to the render gating (cap/debounce/dedup/console-gate stay).

### Constraints

- **Byte-identical output:** the tight loop must produce the exact same bytes as the per-byte form for any valid base64 (verified by the pixel-readback check + the unchanged length guard). No functional/gating change. `node --check` + the committed headless gate (now with the pixel check) green; CI green (verified by conclusion + the runner log).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Both decode sites use the `b64ToBytes` tight-loop helper; the console render still draws + the decoded pixels are byte-exact (a readback check pins them) | operator `node --check` + committed headless gate | render draws; pixels match the stub bytes | app.js diff + harness pixel check | PASS |
| C-002 | yes | Gate: independent adversarial review (byte-identity / edge cases), findings fixed; the committed headless gate + 3-OS CI green (verified by run conclusion + the runner log) | Workflow review + `python3 scripts/operator_headless.py` + CI | byte-identical; review clean; CI green | CODE-REVIEW doc; CI run | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Local: `python3 scripts/operator_headless.py` with the new pixel-readback check → the preview canvas's decoded pixels equal the stub's red/green bytes (proves byte-exact); `node --check`. Independent: an adversarial Workflow review (byte-identity of the tight loop vs the per-byte form incl. edge cases — empty/odd-length/high-bit bytes; both sites covered; gating unchanged). Broader: 3-OS CI (the committed gate runs it on Linux), verified by conclusion + the runner log.
- Required environment: local (macOS Chrome) + CI (Linux).

## Iteration ledger

- Iter 0 (C-001): added a `b64ToBytes(b64)` helper (`atob` once → a plain indexed `for` loop into a preallocated `Uint8Array`, no per-byte closure) and replaced BOTH slow-decode sites — `drawConsoleFrame` (console preview/live) + `tdPreview` (Theme-Designer preview); grep confirms zero remaining `Uint8Array.from(atob` code sites. The length guard + try/catch are unchanged; output is byte-identical. Added a **pixel-readback** check to the committed headless gate: after the boot render it reads `getImageData` from the preview canvas and asserts the two stub pixels (red `255,0,0,255`, green `0,255,0,255`). Evidence: `node --check` OK; headless **64/64** (was 63; +1 M5) — the M5 check printed `preview pixels: 255,0,0,255,0,255,0,255` (byte-exact); `EXPECTED_MIN_CHECKS` bumped to 64. Result: PASS.

## Risks and rollback

- Risks: the tight loop producing different bytes than the per-byte form (mitigated: `charCodeAt(i)` on the `atob` string is identical to the callback form; the pixel-readback check pins byte-exactness; the length guard stays). A missed decode site (mitigated: grep confirms exactly the two `Uint8Array.from(atob` sites). Rollback: git; operator-webview-only, output-identical.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajtwq28-console-decode-perf.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- ClickUp final evidence comment: (pending — MCP rate-limited; closes audit report §4 #5)
