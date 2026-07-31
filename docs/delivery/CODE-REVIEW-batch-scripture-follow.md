# Code Review — Batch: scripture live-follow (86ajtwq2b)

- **Outcome:** **2 raised → 0 confirmed → 2 refuted.** Both were real observations below the defect bar; **finding #1 pointed at a genuine UX nuance I acted on** (below).

- **Scope:** owner refine **#8** — "scrolling down on scriptures should populate both preview and live, not just preview," with the owner's decision: **Live follows ONLY when a scripture is already live** (preview⟂live isolation preserved otherwise). Navigating verses in the scriptures browser now advances **both Preview and Live** while a scripture is on air (the preacher's passage follows the audience), without disturbing blackout or any non-scripture live content. Executed via `/goal` (`TASK-86ajtwq2b-scripture-live-follow.md`, validator PASS 4/4). `selahcue-lan` + `selahcue-app` + `selahcue-operator`; **additive wire (VERSION 2 unchanged)**, RBAC `GoLive`.
- **Method:** an adversarial Workflow review (`wf_b1b56a81-932`, **3 lenses** → per-finding refute-by-default verify, ultracode). Lenses: **controller isolation / no-wrong-live-change / blackout** · **wire additive / RBAC no-escalation** · **frontend verse-nav**.

## What shipped

- **Protocol (`selahcue-lan`):** additive `Command::FollowScripture { reference, translation: Option<String> }` (snake_case `follow_scripture`, `skip_serializing_if` translation). VERSION 2 unchanged.
- **RBAC (`rbac.rs`):** `FollowScripture => GoLive`. A **separate command mapped to `GoLive`** — not a `follow` flag on the `SearchScripture`-level `StageScripture` — because RBAC is per-command; a flag would let an Assistant escalate to Live via the follow path.
- **Host (`selahcue-app/controller.rs`):** `apply(FollowScripture)` stages the verse to Preview (identical to `StageScripture`), then **iff a scripture was already live** (`live_scripture.is_some() && presenter.go_live()`) commits it to Live (`live_scripture`/`live_idx=None`/`live_slide`/`live_free_text`) and **re-asserts blackout** when `self.blackout` (because `go_live()`'s SetScene-on-Live reveals — the same pattern the theme/screen recompose handlers use). Bad translation → `Deny(BadRequest)`. When nothing / a non-scripture item is live, it is Preview-only.
- **Operator (`selahcue-operator`):** `OperatorShell` + `RemoteOperator::follow_scripture`; `Backend::follow_scripture`; an async `follow_scripture` `#[tauri::command]` (registered); `dist/app.js` `setCursor(i, stage, follow)` — verse **navigation** within the open chapter (arrow-scroll, verse click) uses `follow_scripture`; a chapter **load** (search box, hit click, chapter prev/next, translation change) stays `stage_scripture` (Preview-only). The double-click "instant live" path is unchanged (its own `stage_scripture` + `go_live`, guarded by `dblclickBusy`).

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | frontend | (raised) | `setCursor` is the shared primitive, so **search / chapter-load** verse landings also follow Live (not just arrow-scroll) — searching a NEW passage while a scripture is live would jump the audience. | **Refuted (invariant holds — the "already live" gate permits it) — but acted on as a UX refinement.** Following on a *new-passage search / chapter jump* is prepping, not scrolling, and shouldn't move the audience. **Fix:** `setCursor(i, stage, follow)` — verse **navigation** within the open chapter (arrow-scroll at app.js `setCursor(±1,true,true)`, verse click `setCursor(i,true,true)`) uses `follow_scripture`; a chapter **load** (search / hit / prev-next / translation change, via `loadChapter`'s `setCursor(idx,true)`) stays `stage_scripture` (Preview-only). So scrolling the reading follows the audience, but deliberately opening a new passage never jumps it. |
| 2 | frontend | (raised) | An Assistant-role remote operator can no longer preview scripture by scroll (follow is `GoLive`-gated). | **Refuted — no shipping path assigns Assistant.** Production pairing grants **Producer** (mobile/QR path, `main.rs`) or **Operator** (loopback host-local, `main.rs`) — both hold `GoLive`, so `follow_scripture` is authorized for every real role; the verse previews (and follows Live only when a scripture is live). `Assistant` appears only in tests/demo. Even hypothetically, the double-click path still uses `stage_scripture` (`SearchScripture`, which Assistant holds). Not a regression for any supported config; a per-role verse-nav fallback is a documented seam. |

**0 confirmed defects.** The controller-isolation lens confirmed Live changes only when a scripture was already live (the `live_scripture.is_some()` gate + byte-identical non-scripture Live + blackout re-assert); the wire/RBAC lens confirmed additive + `GoLive`-gated (no escalation, proven over the wire).

## Verification

- **Rust (matching CI):** `cargo fmt --check` clean · `clippy --workspace --all-targets -D warnings` + `-p selahcue-lan/-p selahcue-app --features server` clean · **`cargo test --workspace` green (53 groups, 0 fail)** + `--features server` green — incl.:
  - `test_protocol::follow_scripture_round_trips_and_is_additive` (tag stable, VERSION 2, `go_live` byte-identical) + `test_rbac::follow_scripture_is_go_live_privilege_not_search` (Operator/Producer allowed, **Assistant/Viewer denied** — no escalation).
  - `test_controller`: **follow advances both Preview+Live only when a scripture is live**; Preview-only when nothing is live (Live idle); **a live plan item's output is byte-identical** across a follow (non-scripture Live untouched); **blackout preserved** (live content follows but stays dark); bad translation denied.
  - `test_operator_remote`: **`remote_follow_scripture_advances_live_only_when_already_live`** — a full **loopback** round-trip (preview-only, then Live follows) — plus **`remote_assistant_cannot_follow_scripture_to_live`** (RBAC denied over the wire; host Live untouched).
- **Operator gate:** `cargo fmt --check` / `clippy` / `cargo build` clean · **`cargo deny check bans licenses sources` = OK** (no dependency change). Headless **53/53** (no regression), `node --check` clean.
- **Invariants:** Live changes ONLY when a scripture was already live (never promotes non-live/non-scripture content); blackout preserved; RBAC `GoLive` (no escalation, proven over the wire); additive wire (VERSION 2, no migration, pinned fixtures byte-stable); deterministic.
- **CI:** the 3-OS Rust matrix (+ `--features server`) + operator-shell + audit/SBOM/deny — pending this push.

## Follow-ups / seams

- A lower-role remote client of THIS webview would get `follow_scripture` denied on verse scroll (losing preview-on-scroll) — a non-issue for the operator shell (always `Operator`/`Producer` role); a per-role fallback to `stage_scripture` is a seam if a lower-role uses the webview. Transcript-driven live-follow (advancing Live from the sermon transcript) is separate. **Open refine items:** #4 real display names (`86ajtxnn1`), #5 fonts (`86ajq3225`); on-device STT (`86ajtxzre`), transcript persistence (`86ajtxzrn`), deferred line shape.
