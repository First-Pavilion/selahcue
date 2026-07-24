# Code Review — batch 7m: operator shell (view-model + shell + Tauri app)

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context Workflow (`w4d8xq56o`, 7 agents). No self-approval.
**Date:** 2026-07-24
**Scope:** `selahcue-app` (`OperatorView`/`ItemView`/`OperatorShell` in `operator.rs`,
`LiveController::operator_view`, `tests/test_operator.rs`) and the excluded Tauri app
`selahcue-operator` (`main.rs`, `dist/index.html`, `tauri.conf.json`, `capabilities/`).

## Verdict: PASS (1 confirmed → fixed; 2 dismissed)

**3 findings raised → 1 confirmed → 1 fixed.** Notably, **all three findings named the
same docstring line** — the operator-surface *logic* (view-model correctness, shell
concurrency, Tauri command/arg wiring, the frontend JS, the Tauri security config) drew
**zero findings**. Verified: workspace `cargo test` **171/171** (incl. 8 new operator
tests); `selahcue-operator` `cargo check` + clippy clean; `selahcue-app` clippy clean.

## Confirmed & fixed

### (integration-honesty, low) — `OperatorShell` docstring overclaimed the operator↔output-window link
The `OperatorShell` doc read: *"Cloning shares the same underlying controller … so the
output window and the operator shell drive one live state."* The load-bearing clause
(Arc-sharing) is true and tested (`shell_clones_share_one_controller`), but the trailing
clause asserted — in unqualified present tense, naming "the output window" as a current
peer — an integration that **is not wired**: the Tauri shell (`selahcue-operator`) drives
its own in-process demo `LiveController`, and the audience output window
(`selahcue-desktop`) holds a **separate** controller; no code shares one controller
between them. That contradicts `selahcue-desktop/main.rs` ("The Tauri operator shell is a
subsequent batch") and the batch's own disclosure that the connection is the next slice.
**Fix:** reworded to a capability statement — cloning yields another handle to the same
controller, so *once an output window is given a clone* it and the shell *would* drive one
live state, with an explicit note that this batch's Tauri shell drives its own controller
and wiring it to the on-screen output window is a later slice.

## Dismissed (2)

Both were the **same docstring** raised by the view-model and shell-concurrency lenses;
each verifier ruled `real=false`, reading the sentence as Clone-semantics prose (subject
"Cloning", a capability of the `#[derive(Clone)]` type in the UI-agnostic core) rather
than an assertion that an output window is attached today. The honesty lens's verifier
took the stricter reading and confirmed it as a low-severity imprecision — so the line was
fixed regardless, resolving all three at once.

## What passed clean (no findings)
- **View-model:** `operator_view()` sets `is_live`/`is_staged` from `live_idx`/`staged_idx`
  correctly; a staged scripture yields `staged_index = None` with no item flagged (honest);
  serialized field names (`plan_name`, `items[].{id,kind,title,is_live,is_staged}`,
  `live_index`, `staged_index`, `blackout`) match what `dist/index.html` reads.
- **Shell concurrency:** `with()` recovers a poisoned lock via `into_inner()` (never
  panics the UI); `act()` applies-then-snapshots under **one** lock (atomic); `Clone`
  shares the `Arc` (tested). Single non-nested lock — no deadlock/re-entrancy.
- **Tauri wiring:** commands match `generate_handler!`; `blackout(on: bool)` /
  `select(item_id: u64)` map correctly from `invoke('blackout', { on })` /
  `invoke('select', { itemId })` under Tauri 2's camel↔snake convention; the frontend
  re-renders from each command's returned `OperatorView`; `withGlobalTauri` + `csp: null`
  + `core:default` capability are appropriate for a local desktop app.

## Honest scope
The Tauri GUI cannot be runtime-tested headless; it is **compile-verified** (`cargo check`
+ clippy), and the operator **logic** is verified by the `selahcue-app` unit tests. The
operator shell drives its own controller and is **not yet connected** to the batch-7l
output window — that integration is the next slice (disclosed at the gate, and now
correctly qualified in the docstring).

## Independence statement
Reviewed by fresh-context agents that did not author the code, over the listed files.
Each finding was adversarially verified by a separate agent defaulting to `real=false`;
the one surviving (an honesty imprecision) was fixed and re-verified (171/171, clippy clean).
