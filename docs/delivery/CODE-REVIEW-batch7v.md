# Code Review — Batch 7v (plan authoring + persistence wiring + library)

- **Scope reviewed:** plan-edit wire commands (`AddItem`/`RemoveItem`/`MoveItem`/`RenameItem`) + RBAC `Permission::EditPlan`; `LiveController` edit arms with index fixup + dirty tracking; `plan_repo::update/search/duplicate`; desktop persistence wiring (`save_plan`, autosave coupling, clean-exit); operator-shell editing UI (Tauri webview); library search perf at 5k plans.
- **Method:** independent multi-lens adversarial review via the Workflow tool (run `wcdpt578m`): finder lenses (correctness / persistence-consistency / RBAC-security / UI-runtime / data-integrity) → per-finding adversarial verification. No self-approval.
- **Raised → confirmed → unique:** **14 → 14 → 9** (A–I; several findings were the same defect seen through different lenses).

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | Rename/delete used `prompt()`/`confirm()` — **unimplemented in wry/WKWebView on macOS**, so both features were silently dead in the shell | UI rewritten: inline rename editor (✏ → input, Enter/Escape/blur), two-click delete confirm ("sure?", 3s timeout); verified against vendored wry 0.55.1 source |
| B | med | Plan write and session snapshot were throttled independently — a crash inside the ≤1s window could persist a new plan with **stale indices** (restores the wrong live item) | `autosave()`: a plan write now carries an **immediate joint session write** (throttle bypassed), both with retry re-arm |
| C | low | Clean-exit path saved the session but dropped a plan edit acked in the final instants | exit path now consumes `plan_dirty` → `save_plan` before the final session save |
| D | low | `plan_repo::search` passed the query into `LIKE` unescaped — `%`/`_` acted as wildcards (`"100%"` matched everything); doc claimed full case-insensitivity | escape `\` `%` `_` + `ESCAPE '\'`; doc corrected to ASCII-case-insensitive; literal-wildcard regression test |
| E | med | `save_plan` swallowed write failures — a failed plan persist was lost forever (session path already retried) | `save_plan` returns `bool`; failure re-arms via new `LiveController::mark_plan_dirty()` |
| F | med | Connect banner printed the **raw Operator token** to stdout (host session is Operator-role since 7q; stdout may be captured/logged) | banner now says the token is in the endpoint file (0600) |
| G | low | Removing the LIVE item keeps its slide on screen (correct) but recovery restored a **blank** — the slide was no longer any plan index and nothing tracked it | RemoveItem arm records the removed item's text as a free live slide (`live_scripture`); field doc widened; crash-recovery regression test |
| H | low | First-run seed inserted plan rows but wrote no session row until the first autosave — an early death orphaned demo-plan rows (unbounded growth across crash loops) | `App::new` writes the initial session snapshot synchronously after `ensure_plan` |
| I | med | 1s poll re-rendered the plan list mid-interaction — clobbering an open editor / eating in-flight clicks | render guards: `editing`/`confirmDelete` block re-render; `lastRendered` JSON skip; `act()` invalidates the cache |

## Verification after remediation

- `cargo test --workspace --features selahcue-lan/server`: **220 passed, 0 failed** (218 pre-review + 2 new regression tests: `removing_the_live_item_survives_crash_recovery`, `library_search_treats_like_wildcards_as_literals`).
- `cargo clippy --workspace --all-targets -D warnings`: clean. `cargo fmt --check`: clean (workspace + operator crate).
- Operator crate (workspace-excluded) `cargo check`: clean.
- Perf guard still green: `library_search_is_fast_at_5k_plans` (<300ms, 5k rows).

## Residual notes

- Rollback-under-fault for `plan_repo::update` remains untested by fault injection (transactional in implementation; tracked in the demo-review step 2 notes).
- Operator-shell editing is desktop-webview only; the mobile client gains editing in a later batch (Producer role deliberately cannot edit — RBAC-tested over the wire).
