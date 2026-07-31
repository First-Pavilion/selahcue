# Audit — Memory leaks · slow-loading views · scripture→output latency

- **Goal contract:** [`docs/delivery/goals/TASK-audit-memory-perf-latency.md`](../delivery/goals/TASK-audit-memory-perf-latency.md) · **ClickUp:** BUILD CONTROL `86ajnx548` (⚠ MCP rate-limited — follow-ups queued below)
- **Role:** qa-engineer · **Date:** 2026-07-31 · **Revision:** `362c5a9` (audit ran on the working tree at this commit)
- **Owner request:** *"check for memory leaks, slow loading views, also test for the response time from clicking a scripture to it displaying on the output."*
- **Method:** read-only inventory + one measurement. A `Workflow` fan-out (ultracode) with three lenses — memory (Rust), memory (webview), view-load (webview) — each reading the code (`wf_f7726032-3d7`, 3 agents, 336k tokens); a deterministic timing test for latency. HIGH findings would have been adversarially verified (refute-by-default) before reporting — **none were raised**, so no verification round ran. The two highest-impact findings were additionally **re-verified by hand** (see labels).
- **Scope guard:** no product code changed — only the one committed timing test + this report. The uncommitted font batch (`86ajq3225`) was audited as-is, not modified.

## Verdict

**No HIGH severity finding. No unbounded, anonymously-reachable OOM path.** The strict no-leak rule (every collection/cache/ring/listener bounded + a bounded-memory test) is **largely satisfied** — the great majority of growing structures are hard-capped **and** pinned by a flood test. The audit surfaces **5 MEDIUM** and **4 LOW** gaps (missing caps or missing tests on structures that are otherwise reachable only by an authenticated/operator-gated path or bounded only by an external contract), plus one measured performance characteristic. The headline for "slow-loading views" is a **per-second plan-list rebuild** on the Live Console while a countdown runs (**Verified by hand**).

**Severity-ranked findings**

| # | Sev | Area | Finding | Reachability | Label |
|---|-----|------|---------|--------------|-------|
| M1 | MEDIUM | view-load | Live Console **plan list fully torn down + rebuilt every second** while a countdown runs — the plan dedup key is `JSON.stringify(view)`, which includes `view.timer` | Every service with a running timer (normal state) | **Verified** |
| M2 | MEDIUM | memory (rust) | `ServicePlan.items` Vec grows per `Command::AddItem` with **no `MAX_PLAN_ITEMS` cap and no flood test**; persisted + reloaded with no `LIMIT` | Authenticated Operator/Producer (`EditPlan`) | **Verified** |
| M3 | MEDIUM | memory (rust) | LAN `active` session `HashMap` has **no hard cap / no idle-TTL** — one permanent entry per distinct paired device, only removed on explicit `revoke`; no cap test | Operator-gated pairing (single-use code each) | **Verified** |
| M4 | MEDIUM | memory (webview) | `#transcript-log` DOM is append-only and **bounded only by the host tail** (`OPERATOR_TRANSCRIPT_TAIL=60`), with no client-side cap and no JS test | A host that ever returns an untailed `view.transcript` | Inferred |
| M5 | MEDIUM | view-load | Console preview/live RGBA base64 decoded **synchronously on the main thread** via the slow `Uint8Array.from(atob,cb)` per-byte path (~1.8M callbacks/output-change) | On real output change only (well-gated) | Inferred |
| L1 | LOW | memory (rust) | `TranscriptEngine.recent_refs` dedup ring is capped (`RECENT_DEDUP_WINDOW=16`) but has **no direct bounded-memory test** | n/a (already capped) | Inferred |
| L2 | LOW | memory (webview) | `#td-font` `<option>` list grows via `tdEnsureFontOption` with no explicit numeric cap (deduped + bounded source → safe) | n/a (bounded source) | Inferred |
| L3 | LOW | view-load | Theme Designer eagerly loads built-ins + the **entire system-font list** at startup even if never opened (2 host round-trips + 300–800 `<option>` nodes on macOS) | Every cold start | Inferred |
| L4 | LOW | view-load | Whole-`view` serialized **twice per second** (plan dedup key + console sig) | Every poll | Inferred |

No finding is release-blocking. All are follow-ups (§4).

---

## §1 Memory audit

### 1a. Confirmed bounded **and** tested (the no-leak rule holds) — no action

| Structure | Cap | Test |
|---|---|---|
| Engine glyph/shape + system-font caches (`raster.rs`) | `RESET_EVERY=4096` full rebuild; `MAX_SYSTEM_FONTS=2048` | `text_caches_stay_bounded_over_many_renders`, `themed_font_rendering_is_bounded_over_many_renders`, `system_font_enumeration_is_sorted_deduped_and_bounded` |
| Image decode cache (`media.rs`) | `64` entries **and** `256 MiB`, clear-on-breach; decode bomb-capped | `the_image_decode_cache_stays_bounded_over_many_distinct_images` |
| Transcript log ring (`transcript.rs`) | `MAX_TRANSCRIPT_SEGMENTS=240` + `MAX_SEGMENT_TEXT_LEN=2000` (UTF-8 boundary) | `log_is_bounded_under_flood`, `segment_text_is_length_bounded` |
| Detection queue ring (`detection.rs`) | `MAX_DETECTIONS=32` + dedup vs pending | `queue_is_bounded_under_flood` |
| Saved-theme library + per-screen map (`controller.rs`) | `MAX_SAVED_THEMES=256`, `MAX_THEME_NAME_LEN=64`, `MAX_ELEMENTS=64`; `screen_themes` ⊂ 3-item allowlist | `saved_theme_library_is_bounded_and_load_drops_bad_entries`, `set_screen_theme_validates_maps_and_recomposes_main` |
| `pending_assignments` / desktop assignments | one-per-role `retain` before push | `output_assignments_are_bounded_and_latest_per_role_wins` |
| Pairing pending-offer map (`session.rs`) | TTL-pruned each ingress (`prune_expired`), operator-initiated | `expired_offers_are_reclaimed_by_prune` (500→0), `redeeming_consumes_the_offer…` |

Transient per-call allocations (flash-analysis per-tile signal Vecs, `channel_ssim` per-pixel Vecs, `Frame.layers`, GPU per-frame instance Vec) are local, dropped on return, and bounded by already-capped inputs (`MAX_ELEMENTS`, `MAX_WRAP_WORDS=1000`, `MAX_DIMENSION`) — informational only.

### 1b. Gaps (findings)

**M2 — `ServicePlan.items` has no cap and no flood test.** `add_item` ([`plan.rs:151`](../../implementation/desktop/crates/selahcue-core/src/plan.rs#L151)) / `insert_item` (`plan.rs:176`) push/insert unconditionally — **no `MAX_PLAN_ITEMS`** anywhere in the file (Verified: grep). Reachable remotely via `Command::AddItem` (`controller.rs`), which only checks kind/non-empty-title; RBAC gates it behind `EditPlan` (Operator/Producer), so it needs an authenticated peer, but an authenticated Producer or a buggy client loop can grow the plan without bound. The bloat is persisted and reloaded with **no `LIMIT`** (`plan_repo` load). *Fix:* a `MAX_PLAN_ITEMS` const enforced in `add_item`/`insert_item` (reject past the cap) + a `BadRequest` in the controller + a cap on the repo load; add `plan_is_bounded_under_flood`.

**M3 — LAN `active` session map has no hard cap / no idle-TTL.** `active: HashMap<DeviceId, Session>` ([`session.rs:80`](../../implementation/desktop/crates/selahcue-lan/src/session.rs#L80)) grows one entry per successful `redeem` (`session.rs:137`); an entry lives forever until an explicit `revoke` — **no `MAX_ACTIVE_SESSIONS`, no idle eviction** (Verified: grep). Growth is operator-gated (each pairing needs an operator-offered single-use code) and re-pairing the same `DeviceId` replaces (no growth), so it is not attacker-driven — but a long-lived host that pairs many transient devices without revoking accumulates sessions unbounded. Tests prove `revoke`→baseline and 100 devices→100 active, but never pin an upper bound. *Fix:* a `MAX_ACTIVE_SESSIONS` cap in `redeem` (reject or evict oldest/LRU when full) and/or an idle-TTL evicted alongside `prune_expired`; add `active_sessions_are_hard_capped`.

**M4 — Transcript DOM bounded only by the host contract.** `syncTranscript()` ([`app.js:2291`](../../implementation/desktop/crates/selahcue-operator/dist/app.js#L2291)) is the only DOM builder that does not clear its container — it is deliberately append-only (an `aria-live role=log` region) and prunes by removing rows whose segment id is no longer in `view.transcript`. So the live node count equals `view.transcript.length`, which is bounded **only because the Rust host tails it** (`OPERATOR_TRANSCRIPT_TAIL=60` from a 240-capped log; host test at `test_controller.rs`). The frontend imposes no independent cap and there is no JS-level test. A remote/older/newer host that returned an untailed transcript would grow the DOM 1:1 with the sermon. *Fix:* a defensive client slice (`view.transcript.slice(-120)`) before the prune loop + a small DOM test.

**L1 — `recent_refs` dedup ring capped but untested.** `recent_refs: VecDeque<String>` (`detection.rs:365`) is hard-capped at `RECENT_DEDUP_WINDOW=16` in `remember`, but the field is private with no accessor, so no test directly pins its size (the engine flood test asserts only `transcript()`/`detections()` lengths). *Fix:* a test-only `recent_dedup_len()` + a flood assertion, or document the transitive coverage. Low risk — the cap is enforced in code.

**L2 — `#td-font` option list.** `tdEnsureFontOption` (`app.js:692`) appends an `<option>` for any not-yet-present font; deduped and sourced only from installed fonts + the host-capped (`MAX_SAVED_THEMES=256`) theme library, so it is bounded and cannot grow per-poll — no runtime cap strictly required. Noted for completeness.

**Webview listener/timer hygiene — clean (informational).** 22 `addEventListener` / 0 `removeEventListener`, all init-once on permanent nodes (window/document/form/Theme-Designer singletons); none inside any render/poll/sync path. Per-row/per-option handlers use property assignment (`.onclick`) on freshly-created elements after `innerHTML=""`, so old handlers are GC'd — no `removeEventListener` needed. Two `setInterval` (1s poll + clock) are single, permanent, non-accumulating; every debounce `setTimeout` `clearTimeout`s its prior handle. **No listener or timer leak.**

---

## §2 View-load audit (operator surfaces)

| Surface | On-load / on-activation cost | Verdict |
|---|---|---|
| **Scriptures** | ONE `get_chapter` per chapter (no 1189-chapter tree, no per-verse N+1); rows ≤176 built on load; search debounced 250ms + generation-guarded, hits sliced to 6 | **Good (credit)** |
| **Screens** | `renderOutputs` change-keyed (early-return unless content key changed), defers rebuild while a picker holds focus; small DOM (main+stage + 2 virtual rows); single-`view` data, no N+1 | **Good (credit)** |
| **Theme Designer** | Eagerly loads built-ins + full system-font list at startup even if never opened (**L3**) | Minor |
| **Live Console** | Plan list rebuilt every second during a countdown (**M1**); console RGBA decoded synchronously (**M5**); double per-poll serialize (**L4**) | Findings below |

**M1 — plan list rebuilt every second (Verified by hand).** The plan dedup key is `const key = JSON.stringify(view)` ([`app.js:25`](../../implementation/desktop/crates/selahcue-operator/dist/app.js#L25)) and the render early-returns only on `key === lastRendered` (`app.js:37`). `view` includes `view.timer`, which the host advances every second during a countdown — so the key differs every poll, the early-return is skipped, `plan.innerHTML=""` (`app.js:43`) tears down the list, and `view.items.forEach` rebuilds every row **including a per-row `<select>` of every built-in + saved theme**. For a 40-item plan with ~30 saved themes that is ~1,700+ DOM nodes and ~160 event closures recreated **per second**, none of which the timer affects. The console-render sig was carefully written to **exclude** `view.timer` ([`app.js:262-269`](../../implementation/desktop/crates/selahcue-operator/dist/app.js#L262), Verified) — that exclusion was applied to the canvas path but **not** the plan path. Cost scales with plan size × theme count; crosses into HIGH (hundreds of ms/sec) for very large plans. This is the primary "laggy view" cause. *Fix (1 line):* scope the plan key to plan-affecting fields (`plan_name, items, themes, saved_themes, live_index, staged_index`), dropping `view.timer` — mirroring the console sig. Then the plan rebuilds only on genuine plan changes.

**M5 — console RGBA synchronous per-byte decode.** `drawConsoleFrame` decodes each frame with `Uint8Array.from(atob(frame.rgba), c=>c.charCodeAt(0))` ([`app.js:301`](../../implementation/desktop/crates/selahcue-operator/dist/app.js#L301)) — V8's slow per-byte-callback path — then `putImageData`, for two ≤640×360×4 frames (~1.8M callbacks) on the main thread. **Well-mitigated:** resolution-capped, debounced 120ms, signature-deduped, timer-excluded, and gated on the console surface being active — so it fires only a few times a minute on real output changes, never on the 1s tick, and first paint (text labels) is not blocked. Hence MEDIUM, not HIGH. *Fix:* a tight `atob→preallocated Uint8Array` loop, or `createImageBitmap`/`OffscreenCanvas` off-thread; add a perf test pinning the ≤640×360 cap + single-decode-per-change so the gating cannot silently regress.

**L3 — Theme Designer eager startup load.** `tdLoadBuiltins()` + `tdLoadFonts()` run at initial script execution (`app.js:1651-1652`) though the default surface is the Live Console; `tdLoadFonts` invokes `system_fonts` and appends one `<option>` per family (300–800 on macOS). Off the first-paint critical path (async), so LOW. *Fix:* lazy-init on first activation of the designer (once-guard) + build options via a single `DocumentFragment`.

**L4 — double per-poll serialization.** Each poll runs `JSON.stringify(view)` (plan key) **and** `JSON.stringify([view.items,…])` (console sig). Intended dedup, negligible (<1ms) for realistic data; noted because the plan key's breadth is what enables M1. Narrowing the plan key (M1 fix) also shrinks this.

---

## §3 Scripture → output latency (C-003)

**Test:** `scripture_stage_to_live_latency_is_measured` ([`test_controller.rs`](../../implementation/desktop/crates/selahcue-app/tests/test_controller.rs)) — a `LiveController` at the **real audience resolution (1920×1080)** (the shared test helper is 320×180, which would under-report), warms up, then times the median over 25 runs of `apply(StageScripture) + apply(GoLive)` with the live frame materialized (`live_output().bytes()`), prints the actual, and asserts a **profile-scaled** sanity ceiling.

**Measured — local dev machine (warm caches):**

```
[AUDIT] scripture stage→live compose+render @1920×1080: median=118.7ms p90=125.3ms max=126.4ms (n=25)
```

**Measured — CI (GitHub ubuntu shared runner, unoptimized debug build):**

```
[AUDIT] scripture stage→live compose+render @1920×1080: median=246.7ms p90=262.7ms max=571.6ms (n=25)
```

CI is ~2× the local median with a much heavier tail (max 571ms) — the classic unoptimized-debug-on-oversubscribed-runner effect. The assertion is therefore **profile-scaled** (matching the `test_present` slide-trigger convention): a generous **2000ms** tripwire on debug builds (catches a catastrophic regression everywhere) and the real **300ms** release NFR (≈2× the single-slide 150ms trigger budget, since this path does two 1080p renders). The *reported* latency is the printed median, not the ceiling. (The first cut used a flat 150ms ceiling — correct locally, but it measured the CI runner rather than the product and reddened CI; the profile-scaled ceiling fixes that without weakening the release bound.)

**Where the budget goes** (attributed by a throwaway present-level probe, not committed): a single `compose_slide + raster::render` at 1080p is **≈59ms — compose ≈8.6ms (~15%), raster ≈50.5ms (~85%)**. The raster dominates: it fills + composites ~2.07M pixels (background + themed text regions) as a pure integer function. The controller's `StageScripture + GoLive` figure (~118ms) is **≈ two full compose+renders** — the verse is composed+rastered once into the **preview** output on stage, then again into the **live** output on go-live — plus the (sub-millisecond) `parse_one` + `verses_in` reference lookup.

**The webview→wire→host hops (local multi-monitor, no network — the owner's setup):** the operator is a Tauri webview driving separate output windows; a scripture action is a Tauri `invoke` (loopback IPC, sub-ms to low-single-digit ms) → the host command → the compose+render above → the output window. There is **no LAN round-trip** in the single-machine case, so the ~118ms host-side compose+render is the dominant term; the IPC/wire hops are small relative to it. The console **preview thumbnail** the operator sees is a separate, debounced, ≤640×360 path (§2 M5) and is not on the audience-output critical path.

**Interpretation:** ~118ms locally (≈247ms on a slow CI debug build) from action to audience pixels is **acceptable for a one-shot slide transition** (not a per-frame budget) and is dominated by the CPU raster at 1080p. It is the floor for how instantaneous "click a verse → on screen" can feel; if the owner ever wants it snappier, the lever is the raster (e.g. the GPU compositor path for full-fill/background, or reusing the preview frame as the live frame when identical) — a larger change tracked as a seam, **not** a leak or a blocker.

---

## §4 Follow-up tickets (⚠ ClickUp MCP rate-limited — queued; post on recovery)

Create under the existing epics, each linked to BUILD CONTROL `86ajnx548` and this report:

1. **BUG/CHORE — cap `ServicePlan.items` (M2).** `MAX_PLAN_ITEMS` const + enforce in `add_item`/`insert_item` + controller `BadRequest` + repo-load cap + `plan_is_bounded_under_flood`. Owner `/backend-engineer`. Epic: core/session-plan. Sev MEDIUM.
2. **CHORE — bound LAN `active` session map (M3).** `MAX_ACTIVE_SESSIONS` (reject/evict) and/or idle-TTL in `prune_expired` + `active_sessions_are_hard_capped`. Owner `/backend-engineer`. Epic: LAN/pairing. Sev MEDIUM.
3. **CHORE — defensive client cap on the transcript DOM (M4).** `view.transcript.slice(-120)` in `syncTranscript` + a DOM test. Owner `/frontend-engineer`. Epic: operator console. Sev MEDIUM.
4. **PERF — narrow the plan-render dedup key (M1).** Drop `view.timer` (+ transcript/detections) from the plan key so the Live Console stops rebuilding the plan every second during a countdown. 1-line change mirroring the console sig; the highest-value fix for perceived responsiveness. Owner `/frontend-engineer`. Epic: operator console. Sev MEDIUM.
5. **PERF — console RGBA decode off the slow path (M5).** Tight `atob→Uint8Array` loop or `createImageBitmap`/OffscreenCanvas + a perf test pinning the cap/gate. Owner `/frontend-engineer`. Epic: operator console. Sev MEDIUM.
6. **CHORE (LOW, batchable) —** `recent_refs` size test (L1); lazy-init the Theme Designer + `DocumentFragment` font-option build (L3); optional `MAX_PENDING_OFFERS` hardening; optional explicit-size assertions in the glyph/image flood tests.
8. **CHORE (LOW) — let a remote re-pair replace its old session (or add an active-session idle-TTL).** The M3 cap bounds `active` at 256, but the registry-level "re-pair replaces, no growth" branch is unreachable via the remote WS server, which mints a fresh random `device_id` per pairing (`server.rs:318`; `PairRequest` carries no client id) — so a remote device re-pairing after credential loss takes a NEW slot rather than replacing its old one, and `active` (in-memory, reset on restart) is reclaimed only by `revoke`. Very low probability (256 host-approved pairings in one process lifetime with zero revokes) and fail-closed, so LOW; the clean fix is a stable client-supplied `device_id` on `PairRequest` OR an idle-TTL that self-reclaims dead sessions. Owner `/backend-engineer`. Epic: LAN/pairing. Sev LOW.
9. **DEVOPS — real operator JS/jsdom test infra wired into CI.** The operator webview (`dist/app.js`) has **no JS test runner in the repo or CI** — all `dist/` verification is either static content assertions (`test_tokens.rs`, `test_keymap.rs`, CI-gated) or a **dev-time** headless harness (Chrome + a `__TAURI__` stub, in the session scratchpad, NOT committed). So behavioural webview checks (`syncTranscript` DOM cap, plan-dedup, console render, designer wiring) are verified at dev time but not gated in CI. Add a committed jsdom/headless harness + a `package.json` + a CI operator-JS job so those behavioural checks become durable regression gates. Owner `/devops-engineer`. Epic: CI/tooling. Sev MEDIUM (integrity/coverage — surfaced by the M2/M3/M4 review). *Interim:* the M4 cap now has a committed content guard (`test_tokens::operator_transcript_log_is_client_capped`).

## §5 Completion predicate

| ID | Criterion | Result | Evidence |
|---|---|---|---|
| C-001 | Memory: every growing structure inventoried + classified; gaps flagged with file:line + a cap/test | **PASS** | §1 (7 bounded+tested, M2/M3/M4/L1/L2 gaps) |
| C-002 | View-load: each surface characterised; heavy paths flagged | **PASS** | §2 (Scriptures/Screens credited; M1/M5/L3/L4 flagged) |
| C-003 | Latency: a deterministic timing test measures the path; median + hop budget reported | **PASS** | §3 (median 118.7ms @1080p; raster ≈85%; hops reasoned) |
| C-004 | Report severity-ranked with evidence; every HIGH verified (0 unverified HIGH); tickets queued; timing test fmt/clippy clean | **PASS** | this report; 0 HIGH raised; §4 queued; timing test in `cargo fmt/clippy` clean workspace |

**Terminal state:** `VERIFIED_COMPLETE` — read-only audit + one timing test; no release-blocking defect; 5 MEDIUM + 4 LOW follow-ups queued.
