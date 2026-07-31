# Code Review — Batch: console/designer RGBA decode perf (audit M5, 86ajtwq28)

- **Scope:** close audit follow-up **M5** — both operator-webview base64→RGBA decodes used `Uint8Array.from(atob(s), (c) => c.charCodeAt(0))`, V8's slow path (a JS closure per byte) for the ~0.9 MB console thumbnails on the main thread. Replace with a shared `b64ToBytes` tight-loop helper at both sites (`drawConsoleFrame` + `tdPreview`). **Byte-identical output** — a pure speed fix. Executed via `/goal` (`TASK-86ajtwq28-console-decode-perf.md`, validator PASS `--require-complete`). Operator-webview only; no host/wire/gating change.
- **Method:** an adversarial Workflow review (byte-identity / both-sites / gating lens → refute-by-default) **plus** an empirical byte-exact proof via the committed headless gate.
- **Outcome:** **SOUND — 0 findings** (`wf_095ae627-3a7`). byte-identity holds; both sites replaced; guards + gating untouched.

## What shipped

```js
function b64ToBytes(b64) {
  const bin = atob(b64);
  const n = bin.length;
  const bytes = new Uint8Array(n);
  for (let i = 0; i < n; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}
```

- Applied at **both** decode sites: `drawConsoleFrame` (console preview/live thumbnails) and `tdPreview` (Theme-Designer preview). Grep confirms **zero** remaining `Uint8Array.from(atob` code sites.
- The length guard (`bytes.length === w*h*4`) and the `try/catch` around the decode are **unchanged** — `atob` still throws on malformed input and is caught.
- The render gating — resolution cap (≤640×360), 120 ms debounce, signature-dedup, console-surface-gate — is **untouched**; this is decode-only.

## Byte-identity argument

`atob` returns a Latin1 *binary string* whose code units are already `0..255`. So `bin.charCodeAt(i)` yields a value in `0..255`, and assigning it into a `Uint8Array` element is a no-op mask (`& 0xFF`). This is exactly what `Uint8Array.from(atob(s), c => c.charCodeAt(0))` does per element — the two forms are **byte-for-byte identical** for every input (empty string, high-bit bytes `0x80..0xFF`, all lengths). The change only removes the per-byte JS-closure call overhead (V8 fast path: a plain indexed typed-array store).

## Verification (empirical)

- **Byte-exact, proven by the committed CI gate:** a new pixel-readback check reads the preview canvas back after the boot render and asserts the two known stub pixels — it printed `preview pixels: 255,0,0,255,0,255,0,255` (red, then green), matching the stub's base64 exactly. So the tight decode produces the identical pixels the per-byte form did.
- **Operator gate:** `node --check dist/app.js` OK; committed headless **64/64** (+1 M5); the pixel check is now part of the durable CI-gated suite (`EXPECTED_MIN_CHECKS=64`).
- **CI:** 3-OS matrix `30655511386` `completed → success` (verified by conclusion); the operator-Linux log printed `M5 tight base64 decode is byte-exact (preview pixels: 255,0,0,255,0,255,0,255)` + `=== 64 checks, 0 FAIL ===`.

## Adversarial review

Byte-identity lens (refute-by-default) — **SOUND, 0 findings** (`wf_095ae627-3a7`). Verbatim: *"the shared `b64ToBytes` helper is byte-identical to `Uint8Array.from(atob(s), c=>c.charCodeAt(0))` for every input — `atob` yields a Latin1 string of single BMP code units 0..255 (no surrogates), so `charCodeAt` gives 0..255 with no mod-256 truncation, code-point iteration equals index iteration, lengths match, and the empty string maps to a length-0 array both ways; both call sites are replaced, the try/catch and length guard are preserved, gating/debounce/console-gate are untouched (decode-only), and no other `Uint8Array.from(atob` site remains."* No fix required. Byte-exactness is additionally pinned empirically by the committed headless pixel-readback check.

## Follow-ups

- Deferred seam: moving the decode off-thread (`createImageBitmap`/OffscreenCanvas worker) — a larger change; the tight loop is the high-value, low-risk win. The decode is already well-gated (fires only a few times a minute on real output changes, never on the poll).
- Remaining audit follow-ups after M5: only LOWs — L1 (`recent_refs` test), L3 (lazy Theme Designer), #8 (M3 re-pair/idle-TTL), #10 (WebKit fidelity smoke), #11 (Chrome-pin/poll durability).
