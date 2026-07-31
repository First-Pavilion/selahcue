# Goal Contract — TASK-86ajtwq2b-scripture-live-follow

## Identity

- Goal ID: TASK-86ajtwq2b-scripture-live-follow
- Parent goal ID: EPIC-86ajp07ce-presentation-slides
- Title: Scripture live-follow — scrolling verses updates Preview AND Live, only when a scripture is already live
- Role: backend-engineer (controller + wire + RBAC) + frontend-engineer (scriptures browser)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajtwq2b (⚠ ClickUp MCP rate-limited at batch start — updates queued below, to post on recovery)
- Created: 2026-07-31
- Independent verification required: yes
- Maximum iterations: 12

## Objective

Owner refine #8 — "scrolling down on scriptures should populate both preview and live, not just preview," with the owner's decision: **live follows ONLY when a scripture is already live** (preserving preview⟂live isolation otherwise). Today, navigating verses in the scriptures browser stages the verse to **Preview only** (`stage_scripture`); the operator must Go-Live each verse. This adds a **follow** path: while a scripture is live, moving through verses advances **both Preview and Live** (the preacher's passage follows the audience), without disturbing blackout or any non-scripture live content.

## Baseline

Verified from code:
- **Controller** (`selahcue-app/controller.rs`): `apply(StageScripture{reference,translation})` composes the verse and stages it to **Preview** (`presenter.stage`, `staged_scripture=Some(ref)`, `staged_idx=None`) — Live untouched. `apply(GoLive)` commits staged→Live (`presenter.go_live()` → `live_scripture=staged_scripture.clone()`, and separately reveals from blackout). `live_scripture: Option<String>` tracks whether Live currently shows a scripture. `presenter.go_live()` (present.rs:111) pushes the staged slide to the Live engine (SetScene) and returns `false` if nothing is staged; it does NOT itself toggle blackout (the `GoLive` handler sets `self.blackout=false` explicitly to reveal).
- **Wire** (`selahcue-lan/protocol.rs`, VERSION 2): `Command` is `#[serde(tag="cmd", snake_case)]`; `StageScripture{reference, translation:Option<String>}` (skip-if-none). **RBAC** (`rbac.rs`): `StageScripture|ScriptureSearch|GetChapter => SearchScripture` (Assistant+); `GoLive => GoLive` (Producer+).
- **Operator** (`selahcue-operator/dist/app.js`): `setCursor(i, true)` (arrow-key / click verse navigation) debounces `invoke("stage_scripture", {reference, translation})` (120 ms); `ondblclick` = instant-live (stage + go_live). The host has an async `stage_scripture` command → `Backend::stage_scripture` → `OperatorShell`/`RemoteOperator::stage_scripture`.

**Key design:** a **new command** `Command::FollowScripture{reference, translation}` (not a `follow` flag on `StageScripture`) — because updating Live is a `GoLive`-class action, and RBAC is per-command; a flag would let a `SearchScripture`-only role (Assistant) escalate to Live. `FollowScripture => GoLive`. The controller: stage the verse to Preview (as `StageScripture`), then **iff a scripture was already live** (`live_scripture.is_some()`) commit it to Live (`presenter.go_live()` + update `live_scripture`/`live_idx`/`live_slide`/`live_free_text`) **without touching blackout** (following updates content, not the blackout state). The operator's verse-navigation (`setCursor` debounced) sends `follow_scripture`; the search box + double-click paths are unchanged. Additive (VERSION 2), no migration.

## Scope

### In scope

- **Protocol (`selahcue-lan`):** additive `Command::FollowScripture{reference, translation:Option<String>}` (snake_case, skip-if-none). VERSION unchanged.
- **RBAC (`rbac.rs`):** `FollowScripture => GoLive` (it can change Live).
- **Controller (`selahcue-app/controller.rs`):** `apply(FollowScripture)` — a read/stage of Preview + a conditional Live commit ONLY when `live_scripture.is_some()`; preserves blackout + any non-scripture live content; bad translation → `Deny(BadRequest)`. When nothing is live (or Live is not a scripture), behaves exactly like `StageScripture` (Preview only).
- **Operator (`selahcue-operator`):** `OperatorShell` + `RemoteOperator::follow_scripture`; a `Backend::follow_scripture`; an async `follow_scripture` `#[tauri::command]` (registered); `setCursor`'s debounced stage → `follow_scripture` (verse navigation follows Live when live). Search box + double-click unchanged.
- **Tests:** controller (follow while a scripture is live → both Preview + Live advance to the new verse; follow while NOTHING live → Preview only, Live untouched; follow while a NON-scripture plan item is live → Preview only, Live untouched; blackout preserved across a follow; bad translation denied), rbac (`FollowScripture => GoLive`: Producer+ yes, Assistant/Viewer no), protocol (round-trip + additive), a remote loopback round-trip if apt, operator headless (verse-nav sends `follow_scripture`).

### Non-goals (seams)

- Auto-advancing Live on a TIMER or from the transcript (that is #8-adjacent transcript follow); multi-verse ranges as one slide; a per-role operator UI that sends `stage_scripture` for `SearchScripture`-only devices (the local/loopback operator is `Operator` role — full access; a lower-role remote fallback is a seam).

### Constraints

- **Preview⟂Live preserved unless already live:** `FollowScripture` changes Live ONLY when a scripture was already live — never promotes non-live or non-scripture content. Blackout + non-scripture live content untouched. Additive wire (VERSION 2, no migration, pinned fixtures byte-stable). RBAC `GoLive` (no escalation). Deterministic. fmt/clippy/deny clean; operator gate; 3-OS CI.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Protocol + RBAC: `Command::FollowScripture` serde round-trip, ADDITIVE (VERSION 2, existing fixtures byte-stable); `FollowScripture => GoLive` (Producer+ allowed, Assistant/Viewer denied) | `cargo test -p selahcue-lan` | round-trips; additive; GoLive-gated | test_protocol/test_rbac | PASS |
| C-002 | yes | Controller: `FollowScripture` while a scripture is live advances BOTH Preview + Live to the new verse; while nothing/non-scripture is live it stages Preview ONLY (Live byte-identical); blackout preserved; bad translation denied | `cargo test -p selahcue-app` | follows only when already live; isolation held | test_controller | PASS |
| C-003 | yes | Operator: `follow_scripture` command wired end-to-end (Local + Remote); the scriptures-browser verse navigation sends `follow_scripture`; operator + workspace compile; clippy clean | `cargo build`/`test` + `node --check` | compiles; verse-nav follows | build/headless | PASS |
| C-004 | yes | Gate: `make ci` (fmt/clippy/test + `--features server`) + operator build/fmt/clippy/deny clean; determinism + pinned fixtures green; independent Workflow review, findings fixed; 3-OS CI green | make-ci + operator + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-scripture-follow.md; CI run | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-lan` (FollowScripture round-trip + additive + `FollowScripture => GoLive` in the RBAC matrix), `-p selahcue-app` (the follow/no-follow/blackout/isolation matrix in `test_controller` + a loopback remote round-trip in `test_operator_remote` if apt). Broader: `make ci` + `--features server` + operator gate + 3-OS CI. Operator headless: verse navigation invokes `follow_scripture`. Independent: adversarial Workflow review (controller-isolation/no-escalation · wire-additive/RBAC-no-leak · frontend-verse-nav lenses).
- Required environment: local + CI.

## Iteration ledger

- Iter 1 (C-001): additive `Command::FollowScripture{reference, translation}` (protocol.rs, snake_case, skip-if-none); `FollowScripture => GoLive` (rbac.rs). Evidence: `test_protocol::follow_scripture_round_trips_and_is_additive` (tag `follow_scripture`, VERSION 2, `go_live` byte-identical); `test_rbac::follow_scripture_is_go_live_privilege_not_search` (Operator/Producer allowed, Assistant/Viewer DENIED — no escalation); existing fixtures unchanged. Result: PASS.
- Iter 2 (C-002): `LiveController::apply(FollowScripture)` — stage the verse to Preview; iff `live_scripture.is_some() && presenter.go_live()`, commit to Live + re-assert blackout when `self.blackout`; bad translation → `Deny(BadRequest)`. Evidence: `test_controller` — `advances_both_preview_and_live_when_a_scripture_is_live`, `stages_preview_only_when_nothing_is_live` (Live not promoted, output idle), `never_disturbs_non_scripture_live_content` (a live plan item's output is byte-identical), `preserves_blackout` (live content follows but stays dark), `rejects_an_unknown_translation`. Result: PASS.
- Iter 3 (C-003): `OperatorShell`/`RemoteOperator::follow_scripture` + `Backend::follow_scripture` + the async `follow_scripture` command (registered); `dist/app.js` `setCursor`'s debounced stage → `follow_scripture` (verse navigation). Evidence: workspace + operator build; `node --check`; **`test_operator_remote`** — `remote_follow_scripture_advances_live_only_when_already_live` (a full LOOPBACK round-trip: preview-only then Live-follows) + `remote_assistant_cannot_follow_scripture_to_live` (RBAC denied over the wire, host Live untouched). Result: PASS.
- Iter 4 (C-004): Gates — `cargo fmt --check` + `clippy --workspace --all-targets` + `--features server` clean; `cargo test --workspace` (53 groups, 0 fail) + `--features server` green; operator fmt/clippy/build + `deny bans·licenses·sources` OK; headless 53/53. Independent review `wf_b1b56a81-932` (3 lenses → refute-by-default) = **2 raised, 0 confirmed, 2 refuted**. Finding #1 (search/chapter-load verse landings also follow) was refuted (the "already live" invariant holds) but **acted on as a UX refinement**: `setCursor(i, stage, follow)` — verse navigation (arrow/click) → `follow_scripture`; a chapter LOAD (search/hit/prev-next/translation) → `stage_scripture` (Preview-only), so searching a new passage never jumps the audience. Finding #2 (Assistant can't preview) refuted (no shipping path pairs Assistant). node --check + headless 53/53 after the refinement. 3-OS CI: pending push.

## Risks and rollback

- Risks: an RBAC escalation (a lower role changing Live via follow) — mitigated: a SEPARATE command mapped to `GoLive`, not a flag on a `SearchScripture` command; an rbac test asserts Assistant/Viewer denied. Following promoting non-scripture or non-live content — mitigated: the Live commit is gated on `live_scripture.is_some()`; a controller test asserts Live is byte-identical when nothing/non-scripture is live. Blackout surprise — mitigated: follow does not touch blackout; a test asserts blackout preserved. Wire/fixture drift — mitigated: additive variant, VERSION 2, `skip_serializing_if`; existing fixtures byte-stable. Rollback: git; additive across protocol/rbac/controller/operator.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajtwq2b-scripture-live-follow.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- ClickUp final evidence comment: (pending — MCP rate-limited; queued)

## Pending ClickUp updates (MCP rate-limited — post on recovery)

- Move `86ajtwq2b` → in-progress with the goal-contract start comment (this contract path, engine=goal, max 12 iters).
- At handoff: evidence comment + move → qa (list-form QA steps); update BUILD CONTROL `86ajnx548`.
