# Code Review — batch 7u: autosave + crash recovery

**Method:** Independent multi-lens adversarial review (3 lenses × find → adversarially
verify, 13 agents, workflow run `wf_9fb846eb-bb6` — resumed across a session restart
with cached agents). One verifier **empirically reproduced** its finding with a
compiled test. No self-approval.
**Date:** 2026-07-24
**Scope:** migration v2/v3 + `session_repo` (`selahcue-data`), `Timer::with_elapsed`
(`selahcue-core`), `ControllerSnapshot`/`snapshot`/`restore` + dirty tracking
(`selahcue-app`), `Presenter::clear_preview` (`selahcue-present`), and the desktop
`SessionStore` + autosave loop.

## Verdict: PASS after remediation (10 raised → 9 confirmed → 6 unique defects → all fixed)

## Unique defects → fixes

1. **(medium, empirically reproduced) Phantom staged item after restore.** `go_live`
   never clears the presenter's staged slot, so restoring `{live: Some, staged: None}`
   left the live slide sitting in Preview: the confidence monitor showed a "next" that
   was never staged, and a later GoLive re-committed it while setting
   `live_idx = None` — an operator-visible state desync. **Fix:** new
   `Presenter::clear_preview()`; `restore()` explicitly empties Preview when nothing
   was staged. Regression: `restore_with_nothing_staged_leaves_preview_truly_empty`
   (asserts the staged slot, the blank preview readback, and that GoLive stays DENIED).
2. **(low→fixed properly) A scripture on the LIVE output recovered as a blank
   audience surface** — the snapshot model couldn't represent a non-plan live slide.
   **Fix:** migration **v3** adds `live_scripture`/`staged_scripture`; the controller
   now tracks both references through the command paths; `restore()` re-stages and
   re-commits them. Regressions: `a_live_scripture_survives_crash_recovery`
   (byte-identical audience output) + `a_staged_scripture_survives_crash_recovery`.
   This also upgrades the previously disclosed "preview scripture best-effort"
   limitation into faithful recovery.
3. **(medium ×2 lenses) A failed autosave consumed the dirty flag** — the change was
   never retried. **Fix:** `save_session` returns success; a failed write re-arms
   `mark_state_dirty` so the next frame retries.
4. **(low ×3 lenses) A corrupt session snapshot was silently discarded** (then
   overwritten by the next autosave, destroying evidence). **Fix:** the load now
   matches on the error and reports "persisted session unreadable (…); starting
   fresh" — mirroring the adjacent diagnostics.
5. **(medium) Silent storage degradation** when no data dir could be determined or
   created. **Fix:** every `data_dir()` failure path reports itself before the
   in-memory fallback.
6. **(low) Empty/relative `XDG_DATA_HOME`** produced a CWD-relative data dir.
   **Fix:** non-absolute values are treated as unset per the XDG spec.

Dismissed (1): "FK/SET-NULL never asserted" — the mechanisms were verified correct;
the *coverage* gap was real and closed anyway (`deleting_the_plan_nulls_the_session_reference`).

## Verified outcome
- Workspace **212** tests (controller 21; data 7 incl. the new FK/scripture coverage);
  fmt + clippy clean.
- **Live kill-recovery** (release binary): `live_item Some(2), blackout: true` →
  `kill -9` → relaunch → identical state, "Session restored" printed.
- **Real-store migration**: the user's Mac's v2 database upgraded to
  `user_version 3` in place, restored across builds, **1 plan row** (no orphan
  accumulation) — and en route the persistence survived real user interaction
  (keystrokes on a lingering window + a clean-exit save + a deep TIME-UP-overrun
  timer restored correctly).

## Honest remainders (story `86ajp09td` stays open for)
Crash-loop breaker; storage guard (disk-full policy). A crash loses at most ~1 s of
state changes and ~5 s of timer progress (autosave cadence) — disclosed.

## Independence statement
Reviewed by fresh-context agents that did not author the code; findings adversarially
verified (one by compiled reproduction). All six unique defects fixed with regression
tests and re-verified (212/212; live + migration evidence above).
