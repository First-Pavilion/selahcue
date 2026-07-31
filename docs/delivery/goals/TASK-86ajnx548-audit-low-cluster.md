# Goal Contract — TASK-86ajnx548-audit-low-cluster

## Identity

- Goal ID: TASK-86ajnx548-audit-low-cluster
- Parent goal ID: BUILD-selahcue (Stage 8 quality — audit LOW cluster)
- Title: Sweep the audit LOW cluster — recent_refs test (L1), lazy Theme Designer (L3), CI Chrome pin note (#11-doc)
- Role: backend-engineer (L1) + frontend-engineer (L3) + devops-engineer (#11-doc)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited — audit report §4 L1/L3/#11)
- Created: 2026-07-31
- Independent verification required: yes (adversarial review + the committed headless gate + a recent_refs flood test)
- Maximum iterations: 8

## Objective

Close the safe, self-contained LOW audit follow-ups:
- **L1** — the `TranscriptEngine.recent_refs` dedup ring is capped (`RECENT_DEDUP_WINDOW=16`) in code but has **no direct bounded-memory test**. Add a `recent_dedup_len()` accessor (matching the `active_count`/`pending_count` convention) + a flood test asserting it stays ≤ the cap under many distinct references.
- **L3** — the Theme Designer eagerly loads its built-ins + the full system-font list (300–800 `<option>` nodes + 2 host round-trips) at startup even if never opened. **Lazy-init on first activation** (a once-guard in `showSurface`), removing that work from cold start for operators who never open the designer. Update the committed headless gate to open the designer (its real user path) so it still exercises the load.
- **#11-doc** — document/pin a minimum `google-chrome-stable` expectation in the CI headless step so a Chrome change is diagnosable (the cheap half of follow-up #11; the poll-vs-sleep refactor stays deferred).

The larger LOWs stay tracked, not crammed: **#8** (M3 remote re-pair / idle-TTL — a feature), **#10** (WebKit-engine smoke — new infra), **#11 poll refactor** (risks flakiness for a refuted-to-LOW concern).

## Baseline

Verified: `recent_refs: VecDeque<String>` (detection.rs:365) capped in `remember` (395-399); no accessor. `TranscriptEngine` public accessors follow the crate's bounded-assert convention (`DetectionQueue::len`, session `active_count`/`pending_count`). Theme Designer: `tdLoadBuiltins()`+`tdLoadFonts()` at app.js:1675-1676 (module top-level, at boot); `showSurface(name)` (620) routes surfaces; the designer surface is `"theme-designer"` (APP_SURFACES:606); `syncSavedThemes`/`tdList` already no-op until the built-ins exist (709), and the plan's per-row theme picker uses the host `view.themes` (not the designer built-ins), so deferring the designer load affects only the designer surface. The committed headless gate (`scripts/operator_headless.py`) forces the designer surface active directly (L242/275) and its readiness gate waits for `builtin_themes` (L372) — both must move to the nav-open path under lazy-init.

## Scope

### In scope

- L1 (`selahcue-core/src/detection.rs` + `tests/test_detection.rs`): `pub fn recent_dedup_len(&self) -> usize`; a flood test ingesting > `RECENT_DEDUP_WINDOW` distinct references → `recent_dedup_len() == RECENT_DEDUP_WINDOW`.
- L3 (`selahcue-operator/dist/app.js`): a `let tdLoaded=false` once-guard + `ensureThemeDesignerLoaded()` called from `showSurface` when `name === "theme-designer"`; remove the eager boot calls. `scripts/operator_headless.py`: open the designer via the nav (triggering the lazy load) before the designer checks; relax the readiness gate off `builtin_themes`; a new check asserting the designer is NOT loaded at boot but IS after opening it.
- #11-doc (`.github/workflows/ci.yml`): a comment on the headless step noting the min Chrome expectation + that a Chrome bump is a known durability axis.

### Non-goals

- #8 (idle-TTL / stable remote device_id — feature); #10 (WebKit smoke — new infra); the #11 poll-vs-sleep refactor. All stay tracked.

### Constraints

- L1: pure test + a read-only accessor; no behaviour change. L3: the designer must still fully work when opened; the plan/console surfaces are unaffected; determinism/gating unchanged. The committed headless gate stays green (with the updated flow) + its floor updated. `node --check` + `make ci` (fmt/clippy/test) + CI green (verified by conclusion + the runner log).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | L1: `recent_dedup_len()` accessor + a flood test that ingests > cap distinct refs and asserts the ring stays == `RECENT_DEDUP_WINDOW` (fails without the cap) | `cargo test -p selahcue-core` | ring capped; test pins it | test_detection (`recent_dedup_ring_is_bounded_under_many_distinct_references`); core 76/0 | PASS |
| C-002 | yes | L3: the designer loads lazily on first activation (not at boot); the plan/console are unaffected; the headless gate opens the designer + asserts not-loaded-at-boot → loaded-after-open | operator `node --check` + committed headless gate | lazy; gate green with the new checks | app.js once-guard + harness; node --check OK; headless 66/0 (+2 L3) | PASS |
| C-003 | yes | Gate: #11-doc added; independent adversarial review, findings fixed; `make ci` + 3-OS CI green (verified by run conclusion + the runner log) | Workflow review + make ci + CI | all green; review clean | CODE-REVIEW doc; CI run | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Local: `cargo test -p selahcue-core` (the recent_refs flood test fails if the cap is removed); `python3 scripts/operator_headless.py` (the designer is not loaded at boot, is after opening it; the render/dedup/cap checks stay green); `node --check`; `make ci`. Independent: an adversarial Workflow review (L1 test bites; L3 lazy-init breaks nothing on plan/console + the designer still works; no gating drift). Broader: 3-OS CI (verified by conclusion + the operator-Linux log check count).
- Required environment: local + CI.

## Iteration ledger

- Iter 0 (C-001, L1): added `pub fn recent_dedup_len(&self) -> usize` (detection.rs, matching the `active_count`/`pending_count`/`DetectionQueue::len` convention) + a flood test `recent_dedup_ring_is_bounded_under_many_distinct_references` — ingests 200 distinct "Psalm N verse M" texts (>> the 16-window) and asserts `recent_dedup_len() == RECENT_DEDUP_WINDOW`. Evidence: `cargo test -p selahcue-core` — core **76/0**; fmt/clippy clean. Result: PASS.
- Iter 1 (C-002, L3): the Theme Designer built-ins + system-font list load LAZILY on first activation — a `let tdLoaded` once-guard + `ensureThemeDesignerLoaded()` called from `showSurface` when `name==="theme-designer"`; the eager boot `tdLoadBuiltins(); tdLoadFonts();` removed. Only the designer surface reads them (the plan picker uses the host `view.themes`; `syncSavedThemes`/`tdList` already no-op until the built-ins exist), so the console/plan are unaffected at boot. Updated the committed headless gate: it opens the designer via nav before the designer checks, its readiness gate is relaxed off `builtin_themes` to `__calls.length>0`, and +2 checks pin the behaviour (designer NOT loaded at boot → loaded after opening it). Evidence: `node --check` OK; headless **66/66** (+2 L3). Result: PASS.
- Iter 2 (C-003, #11-doc): `.github/workflows/ci.yml` — a comment on the headless step noting the min Chrome expectation (`--headless=new` needs Chrome ≥ 112; runner ships google-chrome-stable 120+) + that a Chrome bump fails closed and the poll-vs-sleep refactor (#11) is the deferred hardening. YAML validates. Independent review + CI: pending this push.

## Risks and rollback

- Risks: L3 deferring a load that another surface silently depends on (mitigated: verified only the designer surface reads the built-ins/fonts; `syncSavedThemes` already no-ops until they exist; the plan picker uses host `view.themes`). The headless gate hanging on the old `builtin_themes` readiness gate (mitigated: move it to the nav-open path + relax the gate). L1 accessor widening the API (mitigated: a tiny read-only len, matching `active_count`/`pending_count`). Rollback: git; L1 is test+accessor, L3 is operator-webview + harness, #11 is a CI comment.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajnx548-audit-low-cluster.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- ClickUp final evidence comment: (pending — MCP rate-limited; closes audit report §4 L1/L3 + #11-doc)
