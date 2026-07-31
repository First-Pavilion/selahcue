# Code Review — Batch: audit LOW cluster (86ajnx548)

- **Scope:** close the safe, self-contained LOW audit follow-ups — **L1** (a bounded-memory test for the `recent_refs` dedup ring), **L3** (lazy-init the Theme Designer so its 300–800 `<option>` nodes + 2 host round-trips leave cold start), and **#11-doc** (a CI comment on the min Chrome expectation). Executed via `/goal` (`TASK-86ajnx548-audit-low-cluster.md`, validator PASS `--require-complete`). The larger LOWs stay tracked, not crammed: #8 (idle-TTL feature), #10 (WebKit smoke — new infra), #11 poll-refactor.
- **Method:** an adversarial Workflow review (L1-test-quality · L3-lazy-safety lenses → refute-by-default) `wf_bc870aca-45b`.
- **Outcome:** **all INFO, 0 findings requiring action.**

## What shipped

- **L1** (`selahcue-core`): `pub fn recent_dedup_len(&self) -> usize` (matching the `active_count`/`pending_count`/`DetectionQueue::len` bounded-assert convention) + `recent_dedup_ring_is_bounded_under_many_distinct_references` — ingests 200 distinct "Psalm N verse M" texts (≫ the 16 window) and asserts `recent_dedup_len() == RECENT_DEDUP_WINDOW`.
- **L3** (`selahcue-operator/dist/app.js`): the Theme Designer built-ins + system-font list load **lazily on first activation** — a `let tdLoaded` once-guard + `ensureThemeDesignerLoaded()` called from `showSurface` when `name === "theme-designer"`; the eager boot calls removed. The committed headless gate opens the designer via nav before its checks, relaxes its readiness gate off `builtin_themes`, and adds 2 checks pinning *not-loaded-at-boot → loaded-after-open*.
- **#11-doc** (`.github/workflows/ci.yml`): a comment noting `--headless=new` needs Chrome ≥ 112 (the runner ships google-chrome-stable 120+), that a Chrome bump fails closed, and that the poll-vs-sleep refactor is the deferred #11.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | L1-test | INFO | The flood test **pins the cap** — removing the `while len > RECENT_DEDUP_WINDOW pop_front` loop makes it fail (`left 200 right 16`); with the cap it passes at 16. | Not vacuous; no change. |
| 2 | L3-lazy | INFO | **No other surface reads the designer built-ins/fonts** — the Plan per-item picker + the Screens `themePickerFor` source options from the host `view.themes`/`view.saved_themes`; `syncSavedThemes` is guarded by `if (tdOrder.length) tdList()` so it no-ops (never throws) before the designer opens while keeping `tdSaved` current. | Console/Plan/Screens boot unaffected; no change. |
| 3 | L3-lazy | INFO | **Once-guard correct** — `tdLoaded` set synchronously before the async loads; re-activation returns early; fired only for `name === "theme-designer"`. | No double-load; no change. |
| 4 | L3-lazy | INFO | **No TDZ** — `showSurface` is never called during initial eval (initial surface set in `index.html`; `showSurface` wired only to nav clicks + the boot poll, all after `let tdLoaded`); `tdLoadBuiltins`/`tdLoadFonts` are hoisted `async function` decls called only at click-time. | Sound; no change. |
| 5 | L3-lazy | INFO | **`tdTheme` stays null harmlessly** — every pre-open reader is `if(!tdTheme) return`-guarded; the only unconditional consumers (`tdSync`/`tdPreview`) run inside `tdLoadBuiltins`, i.e. after the designer is opened. No boot path dereferences it. | No throw; no change. |

**0 defects.** Both the L1 test and the L3 lazy-init were verified sound by the independent review, corroborated by the empirical gates (workspace 471/0, headless 66/66 — which exercises the console boot render *and* the newly-lazy designer via the nav-open).

## Verification

- **Workspace:** `cargo test --workspace` **471/0** (+1 L1); `cargo test -p selahcue-core` 76/0; fmt/clippy clean; `ci.yml` YAML valid.
- **Operator gate:** `node --check` OK; committed headless **66/66** (+2 L3: designer not-loaded-at-boot → loaded-after-open); the L1 flood test + the L3 behaviour are now durable CI gates.
- **CI:** 3-OS matrix `30663004635` `completed → success` (verified by conclusion); the operator-Linux log printed both `L3 designer NOT loaded at boot` + `L3 designer loads on FIRST activation` and `=== 66 checks, 0 FAIL ===`.

## Follow-ups (tracked, not in this batch)

- **#8** — M3 remote re-pair replace / active-session idle-TTL (a feature: a stable client `device_id` on `PairRequest` or a last-seen timestamp + prune).
- **#10** — a WebKit/WKWebView-driven fidelity smoke (new infra; the current gate is Blink).
- **#11 poll-refactor** — replace the harness's fixed boot-render `sleep` with a poll for `render_console` (durability; the fail-closed concern is already refuted-to-LOW).
