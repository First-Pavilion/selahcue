# Code Review — Batch 7al refine (scripture verse list + drawer removal)

- **Scope:** story `86ajpx7bd`, owner refine (3 asks): **(1)** remove the About/connection nav **drawer** (a second nav surface competing with the bottom tabs) → relocate to a top-bar action opening a modal sheet; **(2)** a real **chapter verse list** on mobile — single-tap → Preview, double-tap → Live, like the desktop browser; **(3)** keep the **Figma design and the implementation in sync**.
- **New wire surface:** mobile has no local scripture bundle, so #2 needed a wire path — a **read-only `Command::GetChapter` + `ServerMessage::Chapter` + `VerseView`** (Rust), gated on `SearchScripture` (Producer holds it), handled via the existing `selahcue_scripture::chapter_in`/`adjacent_chapter_in`; mirrored in Dart (`cmdGetChapter`, `ChapterResult`, `LiveController.fetchChapter`). **No VERSION bump** (additive at v2; an old host rejects the unknown `cmd` → `error` → the client degrades to reference-only staging). Translation threaded through `stage_scripture` so a verse stages in the browsed text.
- **Method:** independent adversarial review via the Workflow tool (run `wf_eff76b11-dca`, 11 agents; 3 lenses — wire-compat, scripture-fetch, flutter-ui — each finding verified by an independent refuter). No self-approval.
- **Raised → confirmed → unique:** **8 confirmed → 5 unique (A–E) fixed + 1 accepted tradeoff (F)** · 0 refuted. The **wire-compat lens found nothing** — the cross-language protocol path is clean (fixtures pinned both sides, RBAC/dirty-guard correct, graceful degrade verified).

## Findings and dispositions

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | med | **Live verse mis-coloured green.** `_VerseRow` tested `staged` before `live`, but after go-live the host reports `staged_scripture == live_scripture` (GoLive copies staged into live and never clears staged), so the verse actually on the audience rendered with the **green preview** box and announced ", staged" | test **`live` before `staged`** for border, fill, and the a11y label — matching `plan_tab`'s proven ordering (LIVE wins the overlap). Regression-tested (`scripture_tab_test.dart`) |
| B | med | **Silent failed lookup.** `_body` returned the current chapter whenever `_chapter != null` (before consulting `_fetchFailed`), and `_load` never reset `_chapter` on failure — so a failed reload kept the stale chapter with no feedback, the field/list/picker desynced, and tapping staged a stale verse | on a failed load with a chapter already shown: keep it, **SnackBar** the miss, and **re-sync the field** to the visible chapter. Translation only commits on success (picker reverts with the chapter) |
| C | low | **Transient blip → false "old host" fallback.** `fetchChapter` returned null on `SessionException` (after reconnect) with no retry, so a first-fetch socket blip showed the reference-only fallback on a fully capable host | **retry once across the reconnect** in `fetchChapter` |
| D | low | **Initial preload never fired.** The `addPostFrameCallback` `_initialLoad` ran before the first `operator_state` reply (view null) and, kept alive in the IndexedStack, never re-ran | listen on the controller until the view arrives, then preload once (`_maybeInitialLoad`), removing the listener after |
| E | low | **Stale reference field after ‹ › nav.** Chapter paging swapped `_chapter` but never updated `_ctrl.text`, so the field disagreed with the heading and re-submitting jumped back | `_load` now syncs the field to the loaded `book chapter` (nav, search, and initial load) |
| F | low | **~300ms single-tap delay** — inherent to combining `onTap`+`onDoubleTap` on one recognizer | **accepted** — the cost of the requested single-tap-preview / double-tap-live design, identical to the already-shipped `plan_tab`. Documented, no code change |

## Verification after remediation

- Rust: **266** workspace tests (+3 GetChapter controller tests; protocol round-trip + cross-language fixtures extended), `cargo clippy` clean.
- Flutter: `analyze` clean; **36** tests (+ chapter cmd/response fixtures, translations list, `fetchChapter` chapter + degrade, and the **verse-coloring regression widget test**).
- Cross-language wire fixtures pinned on both sides (`test_protocol.rs` ↔ `protocol_test.dart`).

## Figma sync (ask #3)

- The Figma Scripture frame (`123:18`) already specified the verse-list UX (translation picker · `‹ Romans 8 (KJV) ›` nav · numbered verses · "tap to stage, double-tap live") — the implementation was built to it, so #2 and #3 converged. The drawer was never in Figma, so removing it also restored parity.
- Added the **About/info affordance** to the shared `MobileTopBar` component (node `140:112`, bound to the `text/primary` variable) and set the Title to FILL so the trailing group right-aligns. Both design and app now read: **plan name · ● LIVE · clock · ⓘ About**.

## Residual notes (recorded on `86ajpx7bd`)

- On-device QA of the verse list (browse, chapter nav, single/double-tap, translation switch, staged-green/live-red) and the About sheet — QA steps posted on the ticket.
- The ~300ms single-tap latency (F) is an accepted tradeoff of the double-tap-to-live gesture.
