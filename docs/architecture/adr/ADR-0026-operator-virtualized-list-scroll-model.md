# ADR-0026 — The operator console's virtualized lists never write `scrollTop`

- Status: Proposed (for review) — **revision 3.** Revision 1 recommended a design that the S1 spike falsified and revision 2 replaced its central mechanism. Revision 3 re-opens **nothing**: D1–D4 stand unchanged, and it extends **D5 only**, to cover the second virtualizer 86akgqdxr adds to the same file. Revision 2 was the assessment deliverable for 86akcffvt / PR #34, and its decisions shipped there (`cc9a3a5`).
- Date: 2026-09-14 (rev 2) · 2026-09-20 (rev 3)
- Confidence: **High** for revision 2 — unlike revision 1, its central mechanism is measured rather than reasoned, on both engines, with negative controls, by two independent sessions; the residual unknowns named in "Before this is accepted" are about the *real component*, not the mechanism. **High** for revision 3 on a deliberately narrower basis: it introduces no new mechanism and no new class of `scrollTop` write, and the existing safety argument was re-checked against the second container's actual call graph rather than assumed to carry over (see "Revision 3").
- Owner: Software Architect, with Frontend Engineer (delivery), QA and Performance Engineer
- Relates: ADR-0002 / ADR-0003 (the WebView is the operator console only), FR-130, NFR-019, AC3 of 86akcffvt; 86akgqdxr (rev 3)
- Applies to: every virtualized list in `selahcue-operator/dist/transcripts.js` — **two** as of rev 3, the transcript log and the detections panel — and binding on any future virtualized list in this console

---

## Context

`transcripts.js`'s scroll virtualizer produced a distinct, real, independently-reproduced defect in **each of seven review rounds** on PR #34: `role="log"` re-announcement; height estimates diverging from reality; the render band shifting under a fixed `scrollTop`; Home/End racing its own cascaded recompute (with PageUp/PageDown/Space uncovered); a deferred wheel commit corrupting a keyboard jump's landing position; and finally a guard that cannot tell a stale wheel commit from a genuine scrollbar drag.

Revision 1 of this ADR diagnosed the pattern as: the component makes **absolute** `scrollTop` promises, which forces it to classify scroll provenance, which the DOM does not expose — so each round's proxy (`expectedScrollTop` by value, `wheelEventSeq` by event type, `jumpGuardGen` by recency) left the next event source uncovered. **That diagnosis stands and is unchanged.**

Revision 1's *remedy* was wrong. It proposed making the height metric monotone so that script `scrollTop` writes became rare and **relative**, and then handing the keyboard back to the browser. It rested on the premise that a relative write composes with native scrolling where an absolute one does not. The S1 spike falsified that premise.

---

## What the spike measured

**Round 1 (implementing session).** A script `scrollTop` write during WebKit's native multi-frame keyboard-scroll animation cancels it: Chromium 8/8 survived, **WebKit 8/8 cancelled**, and a positive control showed **relative and absolute writes behave identically**. Revision 1's premise was simply false — the engine's cancellation does not distinguish the two.

**Round 2 (this session, independent harness, own fixture, negative controls).** I reproduced that and then asked the two questions round 1 did not reach. Verdicts are "did the animation keep travelling after an injection at ~40 % of its settle time, compared with an uninjected control press at the same instant":

- **A no-op write cancels too.** `el.scrollTop = el.scrollTop` — writing back the value it already holds — cancels on WebKit **3/3** (control would still have travelled 177–246 px; actual travel after injection: **exactly 0**). It is the *write*, not the *change*. This kills every read-then-conditionally-write mitigation.
- **A pure DOM mutation does *not* cancel.** Growing the top spacer by 200 px — which shifts all content and changes `scrollHeight`, with **no `scrollTop` write at all** — survived **3/3 on WebKit** (travelled 212 / 310 / 256 px against controls of 205 / 172 / 238 px) and 3/3 on Chromium. Diff-and-patch row churn likewise survived 3/3 on both.
- **Wheel scrolling is not animated** on either engine (settle 33–43 ms, i.e. discrete), confirming the review chain's standing assumption that only *keyboard* scrolls animate.
- **Native scroll anchoring works on WebKit, exactly.** With anchoring enabled, growing a spacer above the viewport by 200 px made the engine move `scrollTop` by **exactly +200** on its own, and the row the reader was looking at drifted **0 px** — 3/3, both engines. **Negative control:** with `overflow-anchor: none` (what `.tr-log` ships today) the same mutation moved `scrollTop` by **0** and jumped the reader's row by **+200 px**, 3/3. So this is a real discriminator, not a vacuous pass.
- **Anchoring holds during the animation**, which is the case the design needs: injected mid-flight during a native PageUp with anchoring on, the animation survived on both engines (−634 px WebKit, −534 px Chromium after injection).

Scripts and raw data: `aria_fixture.html`, `aria_spike.py`, `aria_spike2.py`, `aria_spike_results.json`, `aria_spike2_results.json` in this session's scratchpad. Nothing was committed and the tracked tree was not modified.

*(Caveat carried from the whole review chain: this is Playwright's WebKit, not WKWebView or WebKitGTK. It is the best available proxy and the one every prior round used.)*

---

## The real constraint

> **C1 — On WebKit, any script write to `element.scrollTop`, of any value including the one it already holds, cancels an in-flight native scroll animation. A DOM mutation that moves content does not.**
>
> **C2 — WebKit animates all keyboard scrolling** (Home, End, PageUp, PageDown, Space, and per round 4's own tracing, the arrow keys). Wheel and drag are not animated.

C1 + C2 mean a virtualizer that writes `scrollTop` in reaction to scroll events is incompatible with native keyboard scrolling on WebKit, full stop. Revision 1 tried to find a middle position — *rare* relative writes plus native keys — and C1 says no such position exists.

But C1's second half is the way out, and it is the finding revision 1 missed: **the constraint is on `scrollTop` writes specifically, not on virtualization.** A virtualizer that mutates the DOM and never writes `scrollTop` coexists with native keyboard scrolling perfectly.

## The root cause, restated

The component **disabled the platform's own correct solution to its central problem, and then reimplemented it in JavaScript** — and the JavaScript reimplementation is the thing that cannot be made correct, because it has to write `scrollTop`.

`app.css` sets `.tr-log { overflow-anchor: none }`, with this stated reason: *"every mutation here is the virtualizer's OWN scroll-position math already accounting for the shift, so anchoring fights it: a 60px wheel step was observed turning into 700-4000px jumps."*

That is accurate — and it is the wrong conclusion drawn from a true observation. Native scroll anchoring and the JS compensation do exactly the same job, so of course they fight. They are mutually exclusive, and **the one that was kept is the one that cannot work.** The engine's version needs no provenance classification, writes nothing from script, costs nothing per frame, and — as measured above — is exact to the pixel and survives the animation. `findTopVisibleSurvivor`, the ratio fallback, `expectedScrollTop`, `jumpScrollTop`, `armJumpGuard`, `wheelEventSeq` and `jumpGuardGen` are, collectively, a hand-rolled reimplementation of `overflow-anchor: auto`.

---

## Decisions

### D1 — Exact, monotone height metric (unchanged from revision 1)

Per-row height array plus an incremental prefix sum (Fenwick/BIT, ~30 lines, `O(log n)` update and query) replacing the single global `avgRatio`. A row's entry starts at its estimate and is overwritten **once**, with its real `offsetHeight`, the first time it is laid out.

- **I1 — Monotone.** A row's recorded height changes at most once and never again for the life of an open transcript.
- **I2 — Local.** Changing row *i* changes the position of rows `> i` only; rows `<= i` never move.

`indexAtOffset` becomes an exact prefix-sum search. Bounded by the same `n` as `segs`/`offsets` (`Int32Array`s) — no new unbounded structure.

D1 survives the spike because it was never about animations: it keeps the corrections anchoring has to make **small and local** (tens of pixels from one row's line count) instead of **global and depth-proportional** (Vera measured single shifts of 2,563 px and 3,479 px under the global ratio). It is also what keeps the scrollbar honest and stops `scrollHeight` breathing 34 % as the ratio wanders.

### D2 — The component never writes `scrollTop`; compensation is the engine's job (replaces revision 1's D2)

- **Delete `overflow-anchor: none` from `.tr-log`.** Native scroll anchoring does the compensation, inside the engine, with no script write.
- **Add `overflow-anchor: none` to the two spacers** (`#tr-log-top-spacer`, `#tr-log-bottom-spacer`). This is what the property is actually for at element level: excluding a node from *anchor candidacy*. The spacers are large empty boxes whose height we mutate — exactly the wrong thing for the engine to pick as its anchor. The rows remain candidates.
- **Delete every compensating write**: `findTopVisibleSurvivor`, the anchor term, the ratio fallback, `suppressCompensation`, and the tail pin's `logEl.scrollTop = scrollHeight - clientHeight` re-assertion (V-11). With an exact metric the tail is exact, and Vera's V-8 already found the pin non-load-bearing.

### D3 — Delete the whole provenance-classification and keyboard-interception apparatus (strengthened)

`jumpScrollTop`, `armJumpGuard`, `wheelEventSeq`, `jumpGuardGen`, `expectedScrollTop`, the five-key `keydown` handler, `pageStepPx()` and its reverse-engineered `ScrollableArea::PageStep` formula all go. Home/End/PageUp/PageDown/Space/arrows return to their native default action, which C1 now permits because nothing writes `scrollTop`.

Five bug classes become **unreachable by construction**, not defended against: round 7 (no guard exists), round 5 (no scripted position for a deferred commit to corrupt), V-10 and V-12 (no interception, so native page-step and native modifier/selection semantics are the browser's again), and the round-4 Home/End race (nothing writes then re-reads itself a frame later).

### D4 — Keep what converged

Bounded DOM (`WINDOW_ROWS`, AC3), diff-and-patch row identity and its V-7 control, the two-spacer layout, the `EDGE_MARGIN_ROWS` hysteresis, every test hook, and the entire Rust side.

One free improvement, safe under I1/I2: calibrate `CHARS_PER_LINE` **once at open** from the real rendered column width, before the first render, instead of the hardcoded 88. It happens before any row is placed, so it changes nothing retroactively, and it collapses the 0.36–0.79 estimate error that rounds 2–3 fought.

### D5 — The invariant is statically enforced, not behaviourally inferred

> `transcripts.js` contains **no assignment to `.scrollTop`**, except sites in these two classes, each of which must carry a marker comment naming **its own class**:
>
> - **`D5-exempt(init)`** — a virtualizer's single initial-position reset, which runs before any scroll or animation can exist on that container.
> - **`D5-exempt(test-hook)`** — a write inside a `window.__tr*` hook whose only purpose is to *simulate* user input for the headless driver.
>
> There is no third class. Any write reachable from a `scroll`, `wheel`, `keydown` or animation-frame handler falls in neither and is forbidden outright — that is precisely the write C1 says cannot be made correct.

This is a **grep-checkable** rule, and it is the most valuable thing in this ADR. Every previous round's control had to infer correctness from observed behaviour under conditions nobody could reliably reproduce — which is why round 6 shipped a mutation-verified check that pinned a bug. D5 needs no reproduction at all: a one-line committed assertion over the file's text, with the exemptions named explicitly, cannot be satisfied vacuously and cannot drift. It converts the entire class from "did we get the heuristic right" into a static check a reviewer can confirm by reading.

**The counts are per class, not one total (rev 3).** `scripts/operator_headless.py` asserts the number of marked sites in each class separately:

- **`init` — 2**: the transcript log's, in `openTranscript`'s success handler; the detections panel's, in `renderDetections`.
- **`test-hook` — 3**: `__trScrollToFraction`, `__trScrollBy`, `__trDetScrollToFraction`.

One total was sufficient while the file held one virtualizer. With two it is not, and simply raising `3` to `5` would have quietly weakened the check: a flat budget is **fungible**, so a later edit could delete an `init` reset and spend the freed slot on a reactive write marked `D5-exempt`, leaving the total at five and the check green — reintroducing the exact copy-paste hole the count exists to close.

This is **measured, not argued.** A seven-case mutation battery was run against the real `scripts/operator_headless.py` over isolated copies of `dist/` (positive control green, six mutations red, 7/7). Its M3 case deletes the detections panel's `init` reset and adds a reactive `detLogEl.scrollTop` write inside `onDetScroll` — the precise defect class this ADR exists to prevent — leaving five marked sites. The naive flat-count-of-5 check **passes M3**; the per-class check fails it on both classes. The other cases cover an unmarked reactive write, one silenced with a copied class marker, a bare classless `D5-exempt`, an unknown class, and a *deleted* exemption (so the numbers are guarded downward as well as upward).

Per-class counts also scale: a third virtualizer raises `init` by one and `test-hook` by however many hooks it needs, each recorded here in its own revision. As before, **a new exemption cannot be added by marking it; only a revision of this ADR can grow either number.**

---

## Alternatives considered

**Revision 1's design (monotone metric + rare *relative* writes + native keys).** Falsified by the spike: relative and absolute writes cancel identically on WebKit, and even a no-op write cancels. Recorded here rather than deleted, because the falsification is the reason the current design exists.

**Keep the interception, fix round 7 narrowly** (Cody's suggestion: arm the guard only when a wheel fired shortly before the jump). Cheapest by far, and now *better motivated* than revision 1 credited — under C1, interception is the only way to reconcile "we must sometimes write `scrollTop`" with "WebKit animates keys", so round 4's decision to intercept was correct given its premises. **Still rejected:** it shrinks the false-positive window without removing the ambiguity (a wheel tick 20 ms before a jump plus a drag inside the guard window reproduces it identically); it requires *inverting* a committed, mutation-verified check (`operator_headless.py:3105-3112` asserts that a bare `scrollTop` write plus a `scroll` event — exactly a drag's DOM signature — **must** be reverted); and D2 removes the premise that made interception necessary in the first place.

**Defer corrections to `scrollend`** (the coordinator's option (b): detect an animation in flight and suppress). `onscrollend` is available on both engines and on the element, so this is buildable. **Rejected as unnecessary** — it is a way to *schedule* a script write safely, and D2 removes the write entirely. Worth remembering if some future surface genuinely cannot avoid writing.

**`IntersectionObserver` / `ResizeObserver` on sentinel rows.** Asynchronous, so "what is visible" arrives a frame late, reintroducing ordering ambiguity in a new place; and it does not solve scroll extent for unvisited rows. **Adopted in one narrow role only:** a width `ResizeObserver` to invalidate the height cache on a column resize, which also closes Vera's V-9.

**`content-visibility: auto`, no virtualizer.** Supported on both engines per my feature probe. Rejected on bounded-DOM grounds: it bounds *rendering*, not *nodes* (~90,000 elements at 30k segments, contradicting AC3 and the repo's bounded-memory rule), and on older macOS/WebKitGTK the failure mode is a *silent* fallback to unbounded layout cost. Revisitable only if AC3 is re-scoped to "bounded render cost" — a product decision, not the architect's.

**Adopt a virtualization library (`@tanstack/virtual-core`, `virtua`).** No bundler or framework by deliberate convention (ADR-0003), so it means vendoring a UMD build; the repo has `cargo audit`/`cargo deny` for Rust but **no JS supply-chain gate at all**; and these libraries write scroll offsets, so under C1 they would carry the same WebKit defect. **Rejected, and the spike strengthens the rejection:** the value here is D2/D5, which no library provides.

**Accept it as a tracked limitation and ship round 7 as a known bug.** A legitimate answer and I weighed it seriously, since it is what the delivery pressure argues for. **Rejected because the limitation is not small:** the defect is deterministic (100 % of trials), on both engines, on an ordinary gesture (press End, then reach for the scrollbar), in the feature this ticket ships — and a known-bad guard that fights the user is worse than no guard at all, since removing `armJumpGuard` alone would leave only the rarer, Blink-only round-5 defect. If the redesign is declined, **the correct fallback is to revert round 6 entirely and track round 5**, not to ship round 7.

---

## Consequences

**Good.** The file gets substantially smaller — roughly 190 of the virtualizer's ~510 lines delete, and the replacement (Fenwick) is ~30. Five bug classes become unreachable rather than defended. Native keyboard behaviour, including modifiers, selection and the real page step, returns to the browser. The correctness argument becomes a static check (D5) instead of a timing-dependent reproduction. V-9 closes. Per-frame cost drops (no `getBoundingClientRect` survivor walk, no forced layout for compensation).

**Costs and risks, stated plainly.**

- **Scroll anchoring is now load-bearing.** If it is suppressed — the spec suppresses anchoring when the scroller is at `scrollTop: 0`, and on certain computed-style changes to the anchor node or its ancestors — content can jump. Near the top of a transcript `topSpacer` is ~0, so there is little to correct and the exposure is small, but this needs a control.
- **A big jump with no surviving anchor node** (a drag across the whole transcript) has nothing for the engine to anchor to. That is correct behaviour — the user asked to go somewhere else — and it is strictly better than today's ratio-fallback write, but the landing position is estimate-accurate, not exact. Same honest "the scrollbar thumb re-seats after a first visit into unmeasured territory" trade Vera already recorded as accepted.
- **The scrollbar still breathes** as unvisited rows are measured. Unavoidable for any variable-height virtualizer; D1 bounds it to one line per row instead of a global ratio swing.
- **Test surgery, some of it inversion.** Delete the 7 "TR wheel-race" checks (they test a mechanism that ceases to exist, and one of them pins a bug) and the `__trAvgRatio` calibration check. **Replace one with its inverse:** after a keyboard jump, a bare `scrollTop` write plus a `scroll` event must now **stick** — that is the regression test for round 7. V-13 ("the row under the reader does not move more than 2 px across a render") is already exactly the right *behavioural* shape and becomes the primary proof the redesign works; keep it unchanged.
- **Three new controls**, each mutation-verified with siblings running (never `--exact`):
  - **D5 static check** — no `.scrollTop` assignment outside the two named exemptions. Mutation: add one ⇒ red.
  - **Anchoring-is-live control** — grow the top spacer above the viewport, assert the reader's row drifts <= 2 px *and* `scrollTop` moved by the growth. Mutation: restore `overflow-anchor: none` on `.tr-log` ⇒ red. (This is the check that would have caught the original mistake.)
  - **I2 monotonicity control** — after measuring row *i*, the document offset of every row `<= i` is unchanged. Mutation: reintroduce a global rescale ⇒ red.
- **Verification bar**, unchanged: real reproduction of each of the seven rounds' bugs against the new file, `make ci`, mutation-verified controls, and **both Blink and real WebKit** — three of the seven bugs were visible only on WebKit.

**Explicitly out of scope.** The round-1 read-only DB constructor and its tests; PR #33's LAN routing; the five open 86ajtxzrn product/legal questions; V-3 and V-14, which remain their own follow-ups.

---

## Before this is accepted

The mechanism is proven at the **engine** level, by two independent sessions with negative controls. It is not yet proven on the **real component**, and that gap cannot be closed by another isolated probe — a fair test needs D1 in place, because with the global ratio still present anchoring would be asked to correct thousands of pixels per render, which is precisely Chromium's original complaint and would fail for reasons unrelated to the target design.

So the first implementation milestone is a **go/no-go**, not a deliverable:

**M1 — build D1 + D2 on a copy of `dist/`, then measure, before writing any tests.** Go/no-go on three numbers, both engines: (i) 240 real 60 px wheel ticks produce zero blank frames and no hop > 8 px of the intended step — this is the direct re-test of the "60px step became 700-4000px jumps" observation that caused anchoring to be disabled; (ii) real trusted PageUp held through never-measured territory travels a full native page every press; (iii) Vera's fresh-open drag suite across the `phased` and `tailheavy` profiles shows zero blank frames. If (i) fails, native anchoring cannot carry this component and the design returns here rather than accreting a workaround.

Estimated effort for the whole change after M1 clears: 1–2 focused days including the test surgery, dominated by the suite work rather than the ~30 lines of Fenwick.

## Delivery note (owner's call, not the architect's)

PR #34 also carries a **security** fix — the read-only transcript-store open — that four reviewers have cleared and that is currently unshipped behind a scroll bug, now for an eighth round. Landing that Rust work on its own and taking the virtualizer as its own ticket is worth considering. It cuts against the one-ticket-one-branch-one-MR rule in the operating contract, so it is a delivery decision, flagged rather than taken.

---

## Revision 3 — the detections panel is the second virtualizer (86akgqdxr)

86akgqdxr surfaces a transcript's detected-scripture list beside its log, in one workspace. That list grows with the service and is unbounded in principle, so it gets a bounded-DOM renderer of its own: a second, independent virtualizer over its own scroll container, `#tr-det-log`.

**What this revision decides: nothing new.** D1–D4 are untouched. The detections panel introduces no new *class* of `scrollTop` write — only a second instance of each class D5 already permits. D5's invariant text and its static check are extended to name those two sites, and the exemption budget is restructured per class (above). That is the whole change.

**Why the same safety argument holds — checked, not assumed.**

- **The initial reset.** `renderDetections(t)` has exactly one caller: `openTranscript`'s `transcript_get` success handler. It sets `detLogEl.scrollTop = 0` only after re-rendering the window from index 0, one statement before the transcript log's own identical reset in the same handler. It is **not** reachable from `onDetScroll`, from `recomputeDetWindow`, or from any animation frame. `#tr-det-log` is a persistent node reused across transcripts, which is the same reason the log needs its own reset: without it, a new transcript opens at the previous one's scroll offset.
- **It stands on firmer ground than the log's, not weaker.** `openTranscript` calls `resetGenerateUi()` *before* issuing the fetch, and that sets `detLogEl.hidden = true`; `renderDetections` un-hides it immediately before the reset. The container therefore has no layout box at all across the transition. An element with no box cannot carry an in-flight native scroll animation for a write to cancel — which is the precise hazard C1 names. The transcript log has no equivalent hide/show and rests on the timing argument alone.
- **We do not lean on that, though.** Whether destroying and recreating a scroll box *also* zeroes `scrollTop` on WebKitGTK, WKWebView and WebView2 is unmeasured here, and this ADR's standing rule is that unmeasured engine behaviour is not evidence. The reset stays an explicit write; the hide/show is recorded as a *second, independent* reason it is safe, never as a reason to drop it.
- **The test hook.** `__trDetScrollToFraction` is the shape of `__trScrollToFraction` applied to the other container. It exists because a headless driver cannot dispatch a *trusted* scrollbar drag; without it the detections panel's bounded-rendering claim — the counterpart to AC3 — would have no control at all. There is no alternative to weigh: the hook is the only way to test the thing.
- **There is no compensation problem to solve here.** D2's machinery — native scroll anchoring, `overflow-anchor: none` on the spacers — exists because the log's rows are *measured* after layout, so its metric shifts under the reader. Detection rows are fixed-height single lines (`DET_ROW_HEIGHT`), so `Math.floor(scrollTop / DET_ROW_HEIGHT)` is exact from the first frame and nothing is ever remeasured. The second virtualizer has nothing to compensate, which is why it correctly carries no Fenwick tree and no anchoring argument — **and why it must never acquire a reactive write to justify one.** If a future change makes detection rows variable-height, that is a D1/D2 question and returns here.

**Alternative considered and rejected: recreate the node instead of resetting `scrollTop`.** Replacing `#tr-det-log` with a fresh element on each open would hold the exemption count at three without an ADR revision. **Rejected:** it buys the number, not the property. It trades a write this ADR has proved safe for DOM churn whose own failure mode — a `scroll` listener silently lost on re-creation, stranding the virtualizer on its first window — is behavioural rather than grep-checkable, and would be invisible to D5 precisely because D5 only sees `scrollTop`. It would also leave two virtualizers in one file using two different mechanisms for the same job, which costs every future reader more than one extra row in a table costs. The count is an instrument; the invariant is the thing, and optimising the instrument at the invariant's expense is the wrong trade.

**Consequences.** The exemption budget becomes per class (2 `init`, 3 `test-hook`), a *tightening* relative to a flat bump to five. Every `D5-exempt` marker in `transcripts.js` must now name its class, and a bare `D5-exempt` no longer satisfies the check — deliberately, so the migration cannot be half-done silently. `scripts/operator_headless.py` carries the check and runs before Chrome is resolved, so it still gates a Chrome-less box.

**Unchanged.** Every revision-2 decision and consequence, and the verification bar. This revision re-opens no engine question and makes no new engine claim.
