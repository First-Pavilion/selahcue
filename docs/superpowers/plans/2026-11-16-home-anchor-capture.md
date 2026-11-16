# Home Anchor Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded test-local evidence around the existing Pricing-to-Home anchor assertion without changing its action, timing, production behavior or result.

**Architecture:** One browser-evaluable observer forwards the existing browser calls and collects fixed-size scalar evidence. A stdlib-only Python adapter preserves the original action and assertion, emits bounded receipts and contains diagnostic failures. One implementation worker owns this single PR-sized unit; an independent reviewer checks it before one normal hosted capture.

**Tech Stack:** Existing Node >=22.18 with node:test/assert/vm, Python stdlib unittest/json/hashlib/importlib.metadata, existing Playwright Home harness; no packages or runtime services added.

**Spec:** `docs/superpowers/specs/2026-11-16-home-anchor-capture-design.md`.

## Global Constraints

- Preserve the original Pricing navigation, Pricing font-ready wait, visible desktop `How it works` first-link click, reused page and effective compensated viewport.
- Preserve `wait_for_url("**/#how-it-works")`, the following 1200 ms wait, and the original 95 ±2 px assertion and message; add no readiness wait, retry, polling, sleep, motion override, viewport reset or alternate navigation.
- Preserve all production sources, dependencies, font policy, motion policy, existing assertions, gate commands and exit-status semantics. The sole workflow exception is the controller-owned additional stdlib fixture invocation in the existing lint job during native Task4; no existing jobs, conditions, timeouts or commands change.
- No local browser, app, service, build, install, native command, network request or CI launch during design or fixture verification. Only existing Node >=22.18 and Python stdlib fixture controls are admitted under the local runtime hold.
- Use a test-local observer only; no persistent storage, screenshot, trace, video, page text, request data, full URL, stack trace or arbitrary error/string serialization.
- Every intercepted call forwards the saved original synchronously exactly once with unchanged `this` and argument identities; preserve the original return value or thrown object.
- No added rect/computed-style reads after arming and before the original target-top sample; no geometry reads in method wrappers or mutation callbacks. Passive scroll callbacks may read scrollY. Initial effective viewport reads occur before the click. Final extra geometry reads occur after the target-top sample.
- Emit schema version 1, one start receipt and at most one terminal receipt per engine/action; each ASCII JSON line is at most 24 KiB including newline. Missing terminal evidence remains incomplete.
- Retain at most 16 target-lookup records, 16 scroll-command records and 16 route observations. Observe at most 256 scroll callbacks and 128 mutation callbacks; count one overflow callback, mark the corresponding limit and disconnect that listener/observer. Counters saturate at 1,000,000 and expose saturation.
- Use one final normal hosted candidate capture after independent review; archive its exact source/run evidence and do not automatically repeat inconclusive or passing capture.

## Review Focus

- Browser options objects with accessor properties or Proxy traps: original method behavior survives, projection remains unknown and emits no arbitrary value (Task 1 Node control).
- A competing wrapper, installation failure or a replaced document: cleanup never overwrites another owner, and evidence remains incomplete (Task 1 Node and Python controls).
- Native calls after retention caps and scroll/mutation storms: original calls keep forwarding while observation stays bounded and truncation is explicit (Task 1 Node controls).
- Click, URL wait, measurement or output failure: no action retry, no swallowed original failure and no extra acceptance check (Task 1 Python controls).
- Route changes without hash events and a passing instrumented action: observed chronology is labelled honestly, with no inferred commit time, layout shift or historical root cause (Task 1 Node controls and Task 2 evidence review).

---

### Task 1: Implement the test-local observer and original-action adapter as one PR-sized unit

**Files / exclusive worker ownership:**

- Create `implementation/marketing/tests/home_anchor_capture.js`.
- Create `implementation/marketing/tests/homeAnchorCapture.test.ts`.
- Create `implementation/marketing/tests/home_anchor_capture.py`.
- Create `implementation/marketing/tests/test_home_anchor_capture.py`.
- Modify only import and routed action block in `implementation/marketing/tests/home_page_headless.py` (source baseline lines 492–499).
- Create `docs/superpowers/specs/2026-11-16-home-anchor-capture-design.md` and `docs/superpowers/plans/2026-11-16-home-anchor-capture.md` from the supplied documents.

**Interfaces:**

- Browser file evaluates to `installHomeAnchorCapture({actionId: string}) -> ArmSnapshot`; the ID is 32 lowercase hex characters.
- Installed `window.__scHomeAnchorCapture` exposes `actionId`, `finish(measureTargetTop: () => number|null) -> {top: number|null, capture: CaptureSummary}`, and idempotent `dispose() -> CleanupSummary`.
- Python `run_pricing_anchor_check(page, run, *, engine: str, target_top_js: str, provenance: dict, sink) -> None` executes the unchanged action and assertion; it does not import Playwright.
- Python `build_home_anchor_provenance(*, engine: str, browser_version: str, environ, harness_path: Path, helper_path: Path) -> dict` obtains only the spec's validated context/version/hash fields; metadata absence is null and never prevents the action.
- Python `emit_home_anchor_receipt(receipt: dict, sink) -> bool` projects the fixed schema and emits one complete ASCII JSON line <=24 KiB, or a minimal incomplete envelope; return false on sink failure without throwing.
- The original assertion message is exactly `the navbar's How it works, clicked on /pricing, lands on the section clear of the bar`.
- `TARGET_TOP_JS` stays unchanged; the adapter embeds that trusted checked-in expression as the one callback run at the existing assertion sampling point. Arbitrary receipt strings are never embedded as source.

- [ ] **Step 1: Reconcile ownership and install the spec.** Read destination HEAD/status and applicable AGENTS files; compare the five owned paths against baseline `1d39a31e0ac1f2850dd9c004c98487c12e9d1b34`. Use the existing `/Users/m.oluwole/.codex/worktrees/selahcue-account-overview-20261116/scph` only after the controller confirms no competing writer for these paths. Do not reset another worker's changes. Copy the design and plan to their declared repository paths. No workflow changes.

- [ ] **Step 2: Establish callable behavior-preserving seams.** In the new Python adapter, move only click, URL wait, 1200 ms wait and unchanged original measurement/assertion into the declared function; leave Pricing goto/font wait at the existing call site. Introduce the browser install/finish/dispose interface with pass-through functions and no diagnostic recording. Add initial fixture controls proving that these seams call native methods once and preserve original action order. The repository need not run a browser for this refactor; inspect the exact diff and execute only fixtures below.

- [ ] **Step 3: Write meaningful failing observer controls against those callable seams.** Execute the exact JS file with Node vm stand-ins, not a test-only replica. Add named tests with these assertions:

  - `records_target_lookup_and_scroll_without_touching_arguments`: one target getter and one options scroll produce one corresponding receipt each; receiver/object identity and original return values match; another ID's `toString` is never invoked.
  - `preserves_throw_identity_and_contains_projection_failure`: saved native methods throw a sentinel object; the caller receives that same object once, including when the observer's clock/projection throws.
  - `does_not_invoke_options_getters`: native stub avoids getter access; observer invokes zero getters; accessor fields become unknown. A Proxy's throwing descriptor trap cannot replace a native return or thrown sentinel.
  - `observes_missing_then_present_without_layout_reads`: target getter first returns null, one mutation callback later sees a target via saved getter, no observer probe is counted as an external lookup, and rect/computed-style spies have zero calls until finish.
  - `records_observed_route_without_hash_event`: change the fixture location and invoke an observed method; the route observation changes to `home_anchor` without a hashchange event; no field claims a commit timestamp.
  - `bounds_retention_and_keeps_forwarding`: invoke 17 target lookups, 17 scroll calls and 17 route changes, then continue native calls; arrays stay <=16, dropped counts/reasons appear, all originals still run once. Deliver 257 scroll/129 mutation callbacks to verify caps/disconnects. Exercise saturation directly through a fixture sequence or bounded counter seam, not a million real DOM events.
  - `measurement_runs_first_once_and_cleanup_preserves_owners`: finish's first geometry operation is the supplied callback, original top is returned unchanged, listeners disconnect, inherited/own descriptors restore exactly, double dispose is harmless, replacements are left intact, and partial install rolls back.

- [ ] **Step 4: Record behavioral RED.** From the destination's `implementation/marketing`, run `node --test tests/homeAnchorCapture.test.ts`. Expected RED: assertions for recorded lookup/command/presence/caps fail against callable pass-through behavior; no missing-file/import/syntax failure qualifies. Save command/output in the controller's review evidence folder, not in application source.

- [ ] **Step 5: Implement bounded browser capture.** Implement the declared browser interface using the exact caps, method ownership/forwarding, enums, post-native safe argument projection, observed-route timing and passive event/MutationObserver behavior in the spec. Disable and restore owned wrappers before invoking the original measurement callback once. Perform only the final supplemental geometry afterward; contain its failures. Keep all arbitrary strings/nodes/event objects out of retained records. Do not wrap history, requestAnimationFrame or production code.

- [ ] **Step 6: Verify browser helper GREEN.** Run `node --test tests/homeAnchorCapture.test.ts`. Expected: all observer behavior tests pass using only vm fixtures; report explicitly that this is not browser reproduction evidence.

- [ ] **Step 7: Write failing adapter/projection controls.** In stdlib unittest, use a fake page/run and controlled sink; no app imports beyond the new stdlib adapter. Add tests that assert: exact `click -> wait_for_url('**/#how-it-works') -> wait_for_timeout(1200) -> one sample -> near(top,95,2,original_message)` sequence; no other page evaluation between click and sample; one start and one terminal record on pass/fail; validated 40/64/32-hex provenance; arbitrary URLs/credentials/nonfinite numbers never emitted; serialized output <=24 KiB with `export_limit`; installation failure executes the action once with original sample; click/URL exception identity survives cleanup; original measurement error is never retried; missing controller yields incomplete evidence and one original measurement; broken sink preserves original pass/fail/exception behavior. Initial pass-through adapter fails receipt/completeness assertions.

- [ ] **Step 8: Record adapter behavioral RED.** Run `python3 -m unittest discover -s tests -p test_home_anchor_capture.py -v` from `implementation/marketing`. Expected RED: missing bounded receipts/cleanup/completeness behavior, not import errors. Save the output with the Node RED evidence.

- [ ] **Step 9: Implement adapter and bounded projection.** Read browser helper text once; generate action ID and provenance before arming. Emit start; install; preserve original action order; evaluate finish with the original callback; call the original `near`; emit at most one terminal in `finally`. Disambiguate original measurement failure from supplemental capture failure so neither sampling nor action can retry. Catch diagnostic failures only; re-raise original action exceptions. Project all receipts to fixed enums/finite scalars/length limits; oversize output becomes the incomplete envelope specified in the design.

- [ ] **Step 10: Run focused GREEN and inspect the integration diff.** Run the same two focused commands from steps 6 and 8. Expected both exit 0 without browser/service/build/network work. Inspect `git diff --check` and the owned-path diff: no changes to the cold cases, `TARGET_TOP_JS`, Pricing goto/font wait, effective viewport, motion, production files, workflow, package files, existing check count or original assertion message. Do not broaden into npm build/test:home or native checks under the hold.

- [ ] **Step 11: Commit the PR-sized change with evidence.** Stage only owned paths after controller coordination and commit `test(marketing): capture bounded Home anchor diagnostics`. Report exact base/head, focused RED/GREEN evidence, unchanged gate boundaries and the remaining real-browser unknowns. Never claim the intermittent failure fixed.

### Task 2: Independent review, remediation and one hosted evidence capture

**Files / ownership:** Independent reviewer reads the exact Task 1 patch and controls; implementation worker alone edits Task 1 files for remediation. Controller owns external review receipts and normal CI archival under `release-evidence/open-pr-review`; no application writes in this task; the native Task4 worker owns the sole additional workflow fixture invocation below.

**Interfaces:** Consumes Task 1 exact base/head, source diff, spec and focused test receipts. Produces a current-head review decision and one archived hosted-capture interpretation, with original gate results and capture completeness separately reported.

- [ ] **Step 1: Independently review the current source head.** Use a fresh reviewer under the user's SDD authorization. Check once-only forwarding/throw identity, callback order, options accessors/Proxy limitation, privacy projection, fixed retention/output caps, missing receipts and cleanup, preserved assertion and no hidden waits. Inspect the Python fake-page controls and exact generated browser evaluation to rule out double sampling on errors.

- [ ] **Step 2: Remediate any findings and re-review.** The original implementing worker owns changes; rerun only affected fixture controls plus both focused suites at final head. Obtain an independent review again on that final head. Do not carry approval from the previous commit forward.

- [ ] **Step 3: Select controls and capture exactly one normal hosted candidate under controller admission.** Native Task4 must add `python3 implementation/marketing/tests/test_home_anchor_capture.py` to the existing workflow lint job; the existing Node test glob already selects `homeAnchorCapture.test.ts`. The parent reviews that additive selection with the combined workflow patch. No new job, changed original condition/timeout/command or suppressed failure is permitted. After accepted review, controller includes this patch in the already authorized normal CI candidate. Preserve the existing Home job/command/engine invocations and all gates. No new workflow, retry matrix, diagnostic-only browser run, local runtime release or CI launch by the design worker. Existing Chromium is the within-run observation control; WebKit uses the normal pinned Linux install. Coordinate with native-fault instrumentation so this is one final instrumented candidate, not two competing capture runs.

- [ ] **Step 4: Archive and interpret the observed outcome.** Verify actual hosted checkout/merge parents, source/tree identity, helper/harness hashes, run/job and browser install metadata. Match start/terminal IDs and schema; report original Home pass/fail separately from observer completeness. On lookup miss with later presence, successful lookup without dispatch, or a bounded command/movement pattern, state the narrow observation and remaining caller/geometry/interruption uncertainty. On pass or missing evidence retain historical unknown cause. Do not automatically rerun.

- [ ] **Step 5: Complete the authorized delivery decision.** Controller applies the existing review/merge gates to the actual final source; a diagnostic pass does not waive an unrelated failure. Record merge or remaining gate blocker with exact evidence. Any later production fix requires evidence-grounded scope and its own meaningful controls; it is not silently part of this capture PR.

## Self-review and execution handoff

Spec coverage is mapped to Task 1 controls and Task 2 runtime evidence: bounds/privacy/provenance, original semantics, cleanup/error paths and interpretation limits all have owners. This is one PR-sized implementation task plus review/capture, not a platform or general logging project. Fixture execution is admitted under the local hold; browser/native execution remains hosted under controller admission. User already selected SDD and authorized reversible diagnostic work, so hand off to that workflow without a new approval question.

Controller execution supplement: the parent has already published both accepted documents. In Task1 Step1, read them and reconcile the then-current assigned BASE; do not recopy stale external drafts. The implementation worker owns only the five named application-test files unless a later concrete review requires a documented amendment. Start only after explicit one-writer handoff. NativeTask4 owns the additional Python fixture invocation and the combined final capture.
