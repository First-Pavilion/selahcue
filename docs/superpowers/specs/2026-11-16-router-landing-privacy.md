# Auth landing privacy before router history

This is the bounded correction for PR #417, requested by the user's review/fix/re-review/merge instruction. It is a controller construction ruling for an already requested fix, not a claim of a separate user design approval.

## Problem and accepted scope

Vue Router 5.5.0 records scroll state under a full-path key in `sessionStorage['vue-router:scroll']` on page departure. SelahCue currently captures and removes verification/reset query tokens only when the lazy view mounts. A same-tab document navigation before that mount can therefore leave a token in scroll storage. Cody and Shadow independently confirmed this Medium finding from the exact dependency and application source; actual browser reproduction is the first execution gate.

The fix must sanitize the initial supported email-link URL synchronously before the only `createWebHistory()` invocation, then transfer the token once to the matching mounted view through private memory. Keep the existing router, lazy routes, page layouts, synchronous `takeLandingToken(): string` consumer contract, server validation and API calls. This correction does not introduce a general client-side navigation credential framework.

Source inputs: target `28314d31f172ad05e757b14ee8a0a69016f9ddd7`, Router PR head `9c5496e9cbc420db42edef3a386390f172536c16`, local integration base `45ba636155eed0382bc1136679c9fc38c35872fe`, tree `b6dbbaa54083d613fc2606f2a6c20d523402456f`. Construction evidence: `designs/router-landing-preflight-20261116.md` and the complete PR #417 Cody/Shadow reviews in the adjacent release-evidence directory.

## URL and history contract

- Recognize `/verify` and `/reset`, case-insensitively and with the single trailing slash accepted by the current classic router. Preserve the actual pathname spelling. Exclude auth subpaths and other destinations.
- Parse only the query needed for this handoff. Match the classic parser's first value semantics, including decoded names, plus-to-space conversion, first-equals splitting, a bare key, explicit empty value, repeats and JavaScript trim. A failed percent decode silently retains the whole plus-normalized segment. Do not use forgiving partial `URLSearchParams` decoding as a substitute. Do not introduce length, prefix or character-set rejection; the server remains the token validator.
- Recognize the presence of a `token` field separately from whether its first value is usable. If present, remove the entire query and hash, matching today's valid-token scrub while closing the empty-first duplicate case. If absent, preserve the current URL and query/hash, including existing missing-token test scenarios.
- Replace the current entry synchronously before history construction, never by a push. Do not put the capture into history state. Preserve unrelated history metadata. For existing classic router URL fields (`back`, `current`, `forward`), sanitize any relative same-site supported auth landing containing a token with the same full-query/hash removal; preserve other values. A null state can remain null for the router to initialize normally. This handles a reload of an existing router entry without turning the fix into arbitrary history-state inspection.
- A failed URL replacement clears the capture and aborts bootstrap before `createWebHistory()` with a fixed credential-free error. It must not continue with an unsafe address. The tradeoff is a refused bootstrap in an exceptional browser environment rather than exposing a token to history bookkeeping; normal browsers keep the existing flow.

## Handoff and lifetime contract

Keep the pending capture private to a small auth module; never use session/local storage, a browser global, a route/query field, DOM content, logs or an event payload for transport. A dedicated pure helper is allowed to keep the existing hook small and to test lifecycle behavior directly.

The first synchronous router guard may bind the capture only to the expected sanitized initial destination, originating at `START_LOCATION`. Bind the actual normalized destination identity, not merely the route name/path. `takeLandingToken` checks `router.currentRoute.value`, because injected `useRoute()` is a facade. Clear before returning the captured string. A later navigation attempt, even to the same destination, cannot claim the initial capture. The current application's router installer remains its only initial navigation initiator; changing that assumption later requires revisiting this binding.

Discard a pending capture on another navigation, failed/cancelled navigation, lazy-load/router error, and non-cancelling document `pagehide`. Remove the temporary pagehide listener after transfer or discard; BFCache return must not restore it. A successful `afterEach` must retain the pending token until the view mounts. Error cleanup must not log raw route, URL or error data. Existing view-owned abort cleanup remains responsible for requests after transfer. Retain the current late query fallback for an intentional later SPA navigation, so this fix does not silently remove existing functionality; it must never recover an abandoned initial capture.

No changes to `main.ts`, `App.vue`, auth views, nginx, workflow selection or package versions beyond the existing Router bump are planned. An implementation need outside this boundary must be reported to the controller before editing.

## Verification

Use the existing `tests/public_routes_headless.py --engine both` production-build gate. Add fresh contexts for pending auth landings so acquisition receipts, manifest counts and existing scenario accounting stay intact. Hold the intended built lazy view chunk, observe that request and the real loading status, and prove no verify/reset API operation or view mount occurred. An interception miss is a failing test, never a pass.

Perform a real same-tab document navigation to a simple inert same-origin fixture, before another router can alter storage. Prove a different document and preserved harmless session marker. Collect observations before departure but assert the retained-storage regression first, so the expected RED demonstrates the storage leak rather than merely an earlier address-bar mismatch. Check initial cleaned address/history and subsequent sessionStorage keys/values (including the scroll entry), localStorage, readable cookies, DOM attributes/content and diagnostics for a synthetic token. Report only fixed labels/booleans, never raw captured storage or diagnostic content. Cover both route names and the accepted case/slash variants across Chromium and WebKit with finite waits and per-case cleanup.

The existing plain-Chrome auth gate remains unchanged at its measured 2,816 checks. Add focused pure tests for token query semantics, unrelated URL/history preservation, replacement refusal, take-once route identity, wrong/repeated navigation and each discard path. Test actual helper behavior, not source spelling. Preserve current source tripwires and existing tests. Browser evidence is the observed feature RED; individual newly added unit assertions must not be falsely reported as having run against old code.

Host runtime work remains held for active paging. No local browser, test runner, project import, install, service or compiler until the controller records fresh stable resource admission. Hosted CI is authorized. A failed setup, import error, audit failure or unrelated timeout is not the desired assertion RED. Do not weaken normal gates, disable scroll restoration, change timeouts, or add retries to obtain green.

After real RED, implement the minimal correction, obtain current-composition GREEN and the complete routed marketing gate, then independent spec/code, security and QA review and the required final whole-branch review. Preserve historical failed runs and distinguish this token correction from the separate intermittent WebKit timeout investigation.
