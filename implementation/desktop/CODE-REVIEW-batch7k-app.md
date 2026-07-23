# Code Review — batch 7k: LAN control → presenter (LiveController)

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context workflow. No self-approval.
**Date:** 2026-07-24
**Scope:** `selahcue-app` (`LiveController::apply`, `handler_for`) and the
`selahcue-lan` `Reply::Deny` addition.

## Verdict: PASS (3 confirmed findings fixed; 1 routed to the product owner)

8 agents ran (4 review lenses + 4 verify). **4 findings raised → 4 confirmed** (0
dismissed — a sharp review). Three are controller defects, now fixed and re-verified
(`cargo test -p selahcue-app --features server` → 10 unit + 2 E2E; workspace 155/155;
clippy clean). One is an **RBAC policy** question that belongs to the product owner.

## Confirmed & fixed

### M1/M2 — a staged scripture could never go Live (dead-end command)
`StageScripture` staged a scripture in Preview but set `staged_idx = None`, and `GoLive`
gated on `staged_idx` being `Some` — so `GoLive` after `StageScripture` returned
`Denied(BadRequest)` and the verse was stuck in Preview with no path to the audience.
**Fix:** `GoLive` now commits whatever the presenter has staged (`presenter.go_live()`),
setting `live_idx = staged_idx` (`None` for a non-plan scripture, which `GetState`
already reports as `live_item = None`). Still denies when nothing is staged.
**Regression test:** `staged_scripture_can_go_live`.

### L1 — staging a scripture reset plan navigation
`staged_idx = None` overloaded two concepts (plan-item-in-preview and the navigation
position), so `Next` after a scripture snapped back to item 0.
**Fix:** a dedicated `plan_cursor` tracks the navigation position and persists across
scripture staging; `Next`/`Previous` resume from it. `staged_idx` still honestly reports
`None` for a scripture. **Regression test:** `staging_a_scripture_preserves_plan_navigation`.

## Confirmed → routed to the owner → RESOLVED (tightened per user refine)

### H1 — an Assistant could wipe the Live output via `Clear`
`Command::Clear` mapped to the `Navigate` permission, which the **Assistant** role holds, so
an Assistant could wipe the live audience output to idle **and** lift an operator-set
blackout — a role that per its own description "cannot push to the live output." Wired to
`clear_live()`, the consequence was concrete over the LAN control path.

**Disposition:** this was the RBAC policy the user had kept in DEC-002; the review supplied
a concrete need to revisit, so it was routed to the owner at the Stage-7 gate. The user
chose **"refine: tighten it."**

**Resolution (2026-07-24):** `Command::Clear` now requires a dedicated
**`Permission::ClearLive`** held only by **Operator** and **Producer**. Assistant keeps
`Navigate` (Next/Previous/SelectItem — which stage *Preview*, not Live) plus SearchScripture
and Monitor, but can no longer wipe the live output. DEC-002 updated to REVISED.
Verified: unit `test_rbac` asserts Assistant/Viewer `Clear` denials and the Producer+ grant;
the app E2E asserts an Assistant `Clear` is **denied over the wire**
(`rbac_and_application_denials_over_the_wire`). lan 34+39, app 10+2 E2E, workspace 155,
clippy clean. A focused adversarial re-verification of the change found **0 defects**.

## Notes

- RBAC is enforced by the server's `authorize()` before the handler runs (verified — no
  command reaches the controller/presenter unauthorized). The controller does not, and
  need not, re-check.
- `handler_for` locks a `std::sync::Mutex<LiveController>` with no `.await` held, so the
  brief critical section cannot deadlock the async task; on poison it degrades to an
  `Error` reply.

## Independence statement

Reviewed by fresh-context agents that did not author the code, over the listed files, using
the crate's own test/lint tooling. Findings were adversarially verified; the 3 code defects
were fixed and re-verified, and the RBAC-policy finding is routed to the owner (DEC-002).
