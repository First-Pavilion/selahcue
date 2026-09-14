# ADR-0026 — The operator console's virtualized lists own an exact, monotone scroll metric, and never classify scroll-event provenance

- Status: Proposed (for review) — assessment deliverable for 86akcffvt / PR #34. **No code change is proposed in this ADR; implementation is a separate ticket and one spike.**
- Date: 2026-09-14
- Confidence: **High** on the root-cause diagnosis and on the two invariants below (both are structural properties of the code, readable without running it, and one of them is already pinned — wrongly — by a committed test). **Medium** on the claim that the target design removes the need for *all* script `scrollTop` writes on the common paths; the one remaining writer (upward scroll into unmeasured rows) needs a real-WebKit spike before the design is accepted.
- Owner: Software Architect, with Frontend Engineer (delivery), QA and Performance Engineer (the gates this replaces)
- Relates: ADR-0002 / ADR-0003 (the WebView is the operator console only; the compositor is native wgpu — nothing here renders audience output), FR-130 (Transcripts viewer), NFR-019 (keyboard operability), AC3 of 86akcffvt (bounded DOM)
- Applies to: `selahcue-operator/dist/transcripts.js` today; binding on any future virtualized list in this console (deck library, media library, long plan lists)

---

## Context

`transcripts.js`'s sliding-window virtualizer has produced a distinct, real, independently-reproduced defect in **every one of seven review rounds** on PR #34. The bugs, in order:

1. `role="log"` re-announcement (clear+rebuild instead of diff-and-patch).
2. Row-height estimation diverging from reality at realistic widths — blank frames, unreachable last segment.
3. The fix for (2) shifted the render band under a fixed `scrollTop` with no compensation — more blank frames on drags.
4. Home/End's own scroll write raced a cascaded native-scroll recompute; PageUp/PageDown/Space were never covered at all.
5. A wheel tick landing immediately before a keyboard jump corrupted the landing position (Blink's deferred wheel commit).
6. The guard built for (5) cannot distinguish a stale wheel commit from a **genuine scrollbar drag or arrow-key scroll** — both produce an identical DOM signature. Found independently by two reviewers, reproduced deterministically on both engines, negative-controlled against the pre-round-6 file.

(Round 1 also produced an unrelated, genuinely solid fix — `Database::open_existing_readonly` — which is **out of scope here and must not be touched**.)

Each round's remedy was competently built and mutation-verified for the case it targeted. The pattern is therefore not carelessness. It is the design.

---

## Root cause

### The component makes **absolute** `scrollTop` promises, and an absolute promise cannot compose with concurrent native scrolling

Every defect from round 4 onward traces to one property. The component writes an *absolute* value to `scrollTop` and then requires that value to survive:

- `jumpScrollTop(target, …)` sets an exact pixel target for Home/End/PageUp/PageDown/Space.
- `armJumpGuard` re-asserts that exact target for ~96 ms afterwards.
- `recomputeWindow`'s tail branch re-asserts `scrollHeight - clientHeight` exactly.
- `expectedScrollTop` records the exact value the module last intended.

An absolute write must **win** against everything else that might move the scroll position. To win, it must know what else is moving it. And that is the wall: **the DOM exposes no provenance for a scroll.** A `scroll` event carries no cause, no originator, no in-flight-delta accounting. So every version of this component has had to *infer* provenance from a proxy, and each proxy partitions the event space incompletely:

| Round | Proxy | Partitions on | First uncovered source |
|---|---|---|---|
| 5 | `expectedScrollTop` | scroll **value** equality | any foreign write landing on a different value — i.e. Quinn's deferred wheel commit |
| 6 | `wheelEventSeq` | whether a `wheel` **event type** fired | scrollbar drag, arrow keys, track click, touch/pen drag, middle-click autoscroll, find-in-page, `scrollIntoView` |
| 6 | `jumpGuardGen` | **recency** of this module's own jumps | nothing external at all |

Round 6's own PR comment argued the enumeration was complete ("*Why this is complete, not just two patched cases*"). It was disproved within hours, by the very next reviewer, on the largest uncovered class in the table. Round 4's "holistic audit" table made the same shape of claim and was invalidated by round 6 layering a timer on top of the paths that table had certified safe.

**A relative write has none of this problem.** `scrollTop += d` composes with an in-flight native delta by construction: if the engine later applies a pending wheel delta on top, the result is `read + d + wheelDelta`, which is the correct composition of both intents. Nothing needs to be classified, suppressed, or out-guessed. *(Inferred from the mechanism Quinn measured — "it applies its pending delta on top" — rather than directly re-measured here. This is the single claim the spike below must confirm.)*

### Why the absolute promises exist at all: a scroll metric that mutates retroactively

The component does not write `scrollTop` because it wants to. It writes it because its own scroll metric moves under the user.

Row heights are estimated from character count (`CHARS_PER_LINE = 88`, `ROW_VPAD = 14`), then corrected by **one global scalar**, `avgRatio = sumMeasured / sumEstimated`. Every position in the document is `offsets[i] * avgRatio`. So **every measurement of any row anywhere retroactively changes the pixel position of every other row, including every row above the viewport.** That is why `renderWindow` must compensate on essentially every render, and why the compensation magnitude scales with depth (Vera measured single corrections of 2,563 px and 3,479 px).

From there the chain is forced, not incidental:

```
global-ratio rescale
  → content moves under a fixed scrollTop on nearly every render
    → compensating script scrollTop writes on nearly every render
      → those writes cancel WebKit's native key-scroll animation   → intercept 5 keys (V-10, V-12, Home/End race)
      → those writes fire async scroll events                       → echo suppression (expectedScrollTop)
      → scripted absolute jumps can be clobbered by a deferred
        native commit                                               → the wheel guard (round 6)
        → the guard cannot attribute drift                          → round 7
```

Roughly **190 of the virtualizer's ~510 lines** — `jumpScrollTop`, `armJumpGuard`, `wheelEventSeq`, `jumpGuardGen`, the `keydown` interception, the echo-suppression branch, and the `suppressCompensation` plumbing threaded through `renderWindow` — exist solely to service the consequences of the global rescale. They are not an independent subsystem with its own residual bugs. They are scaffolding, and they can be deleted if and only if the metric stops moving.

### The evidence that this is non-convergent, not a shrinking tail

I checked the opposite case honestly. It does not hold.

- **Severity is not decreasing.** Round 5's bug needed a real wheel tick inside a 0–4 ms window, on Blink only, and neither the author nor the reporter could force it without a mutant. Round 7's bug is deterministic (100 % of trials), on **both** engines, on an everyday gesture (press End, then grab the scrollbar). The newest bug is strictly worse than the one it was introduced to fix.
- **The remedy for round N is the bug of round N+1**, four rounds running (3→4→5→6→7). That is a system fighting itself, not a residual being worked down.
- **Decisive:** the committed regression test for round 6 *pins the bug*. `scripts/operator_headless.py:3105-3112` performs `scrollTop = 400; dispatchEvent(new Event("scroll"))` — which is exactly, byte for byte, the DOM signature of a scrollbar drag — and asserts it **must** be reverted to the jump's target. Fixing round 7 requires **inverting a committed, mutation-verified assertion**. Per this repo's own bounded-memory discipline (CLAUDE.md: *"a control asserting something about the wrong expression"*), a suite that must be inverted is evidence the model is wrong, not that a case was missed. I verified this by reading the committed script; it is not a report I am relaying.
- **The narrow fix for round 7 does not close the class.** Arming the guard only when a wheel event fired shortly before the jump (Cody's suggestion, and a reasonable one) makes the guard arm *less often*. A wheel tick 20 ms before a jump, followed by a scrollbar drag inside the guard's 96 ms window, reproduces the identical false positive. Window shrunk; ambiguity intact.

---

## Decisions

### D1 — A virtualized list in this console owns an **exact, monotone** scroll metric

Replace the global `avgRatio` rescale with a **per-row height array plus an incremental prefix-sum structure** (a Fenwick/BIT over `segs.length`; ~30 lines, `O(log n)` point update and prefix query, `O(n)` build). A row's entry starts at its estimate and is overwritten **once**, with its real `offsetHeight`, the first time it is mounted and laid out.

Two invariants follow, and they are the whole decision:

- **I1 — Monotone.** A row's recorded height changes at most once (estimate → measured) and never again for the lifetime of an open transcript.
- **I2 — Local.** Changing row *i*'s height changes the document position of rows `> i` only. Rows `≤ i` never move.

`indexAtOffset` becomes an exact prefix-sum search rather than a scaled estimate lookup. `.tr-line`'s real height is `20n + 6` (`line-height: 20px`, `padding: 3px 0`), so measured heights are small quantized integers — an `Int32Array` of length `n` plus a Fenwick `Int32Array` of length `n+1`, bounded by the same `n` that `segs` and `offsets` are already bounded by. **No new unbounded structure**; the existing bound (Sana's F3 — the unpaginated `transcript_get` payload) is unchanged and remains the real ceiling.

### D2 — The component writes `scrollTop` **only** when a row *above the current top visible row* changes height, and then only **relatively**

Under I1 + I2, the common interactions produce **zero** script writes to `scrollTop`:

- **Open, wheel down, PageDown, End, drag-then-read-down** — new rows mount at or below the viewport. Their heights change; nothing above the viewport moves; the viewport does not move.
- **Wheel up / PageUp / Home through already-visited content** — heights are already measured and, by I1, will not change.

The one case that does move the viewport is scrolling **upward into rows never measured before** (e.g. drag to the middle, then read upward). That is handled by the standard local correction, in the same synchronous turn as the DOM mutation: sum `(measured − estimated)` over the rows mounted above the anchor and apply it as `scrollTop += delta`. It is **relative** (D-principle above), it is **bounded** by the mounted band (~35 rows, tens to low hundreds of pixels — not the depth-proportional thousands the global rescale produced), and it is **rare**.

### D3 — Delete the provenance-classification apparatus outright

`jumpScrollTop`, `armJumpGuard`, `wheelEventSeq`, `jumpGuardGen`, the five-key `keydown` interception, and the `suppressCompensation` parameter are removed. Home/End/PageUp/PageDown/Space return to their **native default action**.

This is not a cost, it is the point:

- **Round 7 cannot exist** — there is no guard to fight a drag.
- **Round 5 cannot exist** — the component makes no absolute position promise for a deferred wheel commit to corrupt.
- **V-10 / V-12 cannot exist** — no script write lands during WebKit's native key-scroll animation on the down/already-measured paths, so there is nothing to cancel; and native keys keep native modifier semantics (Shift+End extends a selection) for free rather than by a hand-maintained modifier allowlist.
- **The Home/End race cannot exist** — nothing writes `scrollTop` synchronously and then re-reads itself a frame later.
- `pageStepPx()` and its reverse-engineered `ScrollableArea::PageStep` formula are deleted. Reimplementing an engine's own scroll step in application JS was always a liability; it is now unnecessary.

`expectedScrollTop` is retained only if the D2 correction proves to need it, and only with a control that bites — round 4 already disclosed it is not independently mutation-provable today.

### D4 — Keep what is genuinely converged

Unchanged: `WINDOW_ROWS` bounded DOM (AC3), diff-and-patch row identity (the `role="log"` fix and its V-7 control), the two-spacer layout, `overflow-anchor: none`, the `EDGE_MARGIN_ROWS` hysteresis, the tail pin and its V-11 re-assertion, every test hook, and the whole Rust side.

Improvement that costs nothing and is safe under I1/I2: calibrate `CHARS_PER_LINE` **once at open**, from the real rendered column width, before the first render. It happens before any row is placed, so it changes nothing retroactively, and it collapses the 0.36–0.79 estimate error that rounds 2–3 were fighting to a small residue.

---

## Alternatives considered

**A. Keep patching; apply Cody's narrowed arming condition for round 7.** Cheapest by far (a few lines), and the estimation half of the component (calibration, hysteresis, anchor, tail pin) is genuinely well-tested. **Rejected** on the four points under "non-convergent" above — most decisively, that the fix requires inverting a committed mutation-verified assertion, and that the narrowed condition shrinks the window without removing the ambiguity.

**B. Stop classifying, make the render idempotent with respect to *why* `scrollTop` changed.** This is the right instinct and is precisely what D1–D3 implement. Stating it as "make the render side-effect-free" alone is not achievable for a variable-height virtualizer (every serious one writes `scrollTop` sometimes); the achievable version is "make the *metric* monotone so the render almost never *needs* to, and make the writes it does need *relative*." Adopted, in that form.

**C. `IntersectionObserver` / `ResizeObserver` on sentinel rows instead of offset arithmetic.** Genuinely removes the estimate-vs-reality gap that rounds 2–3 fought. **Rejected as the primary mechanism:** observers are asynchronous, so "what is visible" arrives a frame or more after the scroll that caused it — which reintroduces exactly the *ordering* ambiguity this ADR is trying to eliminate, in a new place. It also does not solve the scroll-extent problem: the scrollbar still needs a total height for unvisited rows, which is still an estimate. **Adopted in one narrow role:** a `ResizeObserver` on the log's *width* to invalidate the height cache on a column resize — which also closes Vera's V-9 (the ratio is never re-learned after a resize), currently open.

**D. `content-visibility: auto` + `contain-intrinsic-size` on every row; no virtualizer at all.** Very attractive: the browser owns an exact scroll metric, native scroll anchoring works, and the whole class of bug disappears. **Rejected on two grounds.** (i) It bounds *rendering* but not *nodes* — a 30,000-segment transcript is ~90,000 elements, which contradicts AC3 as written and this repo's standing bounded-memory rule. (ii) Support risk: fine on WebView2 (Windows), but macOS ships the system WKWebView and Linux WebKitGTK, where availability is version-dependent and the failure mode is a *silent* regression to unbounded layout cost rather than a loud error. Worth revisiting if AC3 is ever re-scoped to "bounded render cost" rather than "bounded nodes" — that is a product decision, not mine.

**E. Adopt a virtualization library (`@tanstack/virtual-core`, `virtua`).** These have already been through these seven rounds upstream, with a maintained bug stream. Real cost here: no bundler and no framework by deliberate convention (ADR-0003), so it means vendoring a UMD build into `dist/`; the repo has `cargo audit`/`cargo deny` for Rust but **no supply-chain gate for JS at all**, so a vendored dependency enters unwatched; and CSP/offline rules out a CDN. It also would not automatically solve the WebKit native-animation interaction, since these libraries write scroll offsets too. **Rejected for this component** — the core algorithm is ~30 lines of Fenwick tree and the D1/D2 invariants are the actual value, not the code volume. Worth reopening if the console grows three or four more virtualized surfaces.

---

## Consequences

**Good.** ~190 lines of race machinery deleted; the file gets smaller, not larger. Five whole bug classes become unreachable by construction rather than defended against. Native keyboard behaviour (including modifiers and selection) is restored for free. V-9 closes. The compensation that remains is bounded and rare instead of depth-proportional and constant.

**Costs and risks, stated plainly.**

- **The one residual risk** is D2's upward correction: it is still a script `scrollTop` write, and on WebKit it could still land during a native PageUp animation and cancel it (V-10's original mechanism). This is the single thing that must be settled before the design is accepted — see the spike below. If it bites, the fallback is to defer that correction to the next animation frame, accepting one frame of visual drift on an uncommon path, which is a far smaller concession than the current apparatus.
- **The scrollbar thumb still breathes** as unvisited rows are measured. This is honest and unavoidable for any variable-height virtualizer, and Vera already recorded it as accepted.
- **Test surgery is required, and some of it is an inversion, not an addition.** The 7 "TR wheel-race" checks and the `__trAvgRatio` calibration check are deleted (they test mechanisms that cease to exist). One of them must be **replaced by its inverse**: after a keyboard jump, a bare `scrollTop` write plus a `scroll` event must now **stick**. That inverted check is the regression test for round 7 and makes the diff self-documenting. Everything else stays — and note that V-13 (the "row under the reader does not move more than 2 px across a render" check) is already exactly the right *behavioural* shape and becomes the primary proof the redesign works.
- **Two new controls are required,** both mutation-verified against a sibling run per CLAUDE.md:
  - **I2 monotonicity control** — after measuring row *i*, assert the document offset of every row `≤ i` is unchanged. Mutation: reintroduce a global rescale ⇒ must go red. This is the control that structurally prevents rounds 3–7 from recurring.
  - **Upward-correction control** — drag to the middle, scroll up into unmeasured rows, assert the anchor row's on-screen position holds within 2 px. Mutation: remove the correction ⇒ must go red.
- **Verification bar** is the one this PR has used throughout: real reproduction of each of the seven rounds' bugs against the new file, `make ci`, mutation-verified controls run with siblings (never `--exact`), and **both Blink and real WebKit** — the WebKit gate is not optional here, since three of the seven bugs were visible only there.

**Explicitly out of scope.** The round-1 read-only DB constructor (`Database::open_existing_readonly`) and its tests; PR #33's LAN routing; the five open 86ajtxzrn product/legal questions; Vera's V-3 (`transcript_repo::list`'s `COUNT(*)` scaling) and V-14, which remain their own follow-ups.

---

## Before this is accepted: one spike

**S1 — Does a relative `scrollTop += d` compose with an in-flight native scroll, and does it cancel WebKit's native key-scroll animation?** Two measurements, real trusted input, both engines: (a) Blink — dispatch a real wheel tick, then `scrollTop += d` inside the 0–4 ms window Quinn measured, and confirm the final position is the composition of both rather than either alone. (b) WebKit — hold PageUp through a never-measured region so the upward correction fires mid-animation, and measure whether the animation survives. Half a day. Both results are load-bearing: (a) is the premise of the "relative writes compose" principle, and (b) decides whether D2's correction is synchronous or deferred by a frame.

## Delivery note (owner's call, not the architect's)

PR #34 also carries a **security** fix — the read-only transcript-store open — that four reviewers have cleared and that is currently unshipped behind a scroll bug. Landing that Rust work on its own and taking the virtualizer as its own ticket is worth considering. It cuts against the one-ticket-one-branch-one-MR rule in the operating contract, so it is a delivery decision for the owner, flagged here rather than taken.
