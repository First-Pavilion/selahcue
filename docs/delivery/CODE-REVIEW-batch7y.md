# Code Review — Batch 7y (bundled scripture verse text, end to end)

- **Scope reviewed:** new `selahcue-scripture` crate (WEB translation asset, 31,098 verses, lookup + keyword search); controller verse-text composition (`scripture_slide`, wrap + truncation); `ScriptureSearch` keyword fallback; protocol scripture fields; operator/Tauri/webview scripture UI; Flutter command + display; wire E2E.
- **Method:** independent multi-lens adversarial review via the Workflow tool (run `wf_516d2959-967`, 15 agents): 4 finder lenses (bundled-data integrity + licensing · wire compatibility · controller correctness · client runtime) → per-finding adversarial verification, including decompressing and auditing the actual asset and mutation-testing the wire contract. No self-approval.
- **Raised → confirmed → unique:** **10 confirmed → 7 unique (A–G)** · 1 refuted (asset provenance — recorded in the crate docs). The data lens verified the asset verbatim against WEB (canon counts, famous verses, no mojibake) and the licensing claims (public domain).

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | Scripture slides built 8 body lines + a 9th "…" — but the compositor physically renders **title + 6 body lines**; tail lines and the ellipsis were silently clipped (verified empirically at 4 resolutions) | cap = 6 body lines including "…" (5 verse lines + marker when truncated); the capacity itself is now pinned by `compose_slide_renders_title_plus_six_body_lines` in selahcue-present |
| B | med | `live_scripture` conflated real scripture with the 7v removed-item free slide: recovery **recomposed verse text for a removed item whose title parses** ("Romans 8:28" plan item → different surface than pre-crash), and remote panels mislabeled removed items as "scripture" | new `live_free_text` field end to end (schema **v4**, snapshot, wire view with skip-if-none, webview "slide" kind); free slides restore **verbatim**, byte-identical (regression-tested); scripture keeps recomposing correctly |
| C | high | Webview Enter/Stage could commit a **stale first hit from the previous query** (hits invalidated only after the 250ms debounce + RTT), and a pending debounce repopulated the list after staging | hits dropped immediately on input; generation counter discards superseded async results; stage/click clear the timer |
| D | low | No cross-language fixture pinned the serialized `operator_state` **with** the new fields — a serde rename would ship silently (proven by mutation) | serialize-side fixture pinned in Rust; the **exact same JSON string** parsed in the Dart test |
| E | low | The 500ms search perf test timed the one-time index decode (flaky on slow debug CI runners) | index warmed before the timed section |
| F | low | Flutter parsed the scripture fields but **never displayed them** — blind Go Live from the phone | PREVIEW/LIVE status strip (canonical badges) above the controls |
| G | low | (fold-in of B's wire half) removed items rendered with a "scripture" badge remotely | `live_free_text` renders as kind "slide" |

## Verification after remediation

- `cargo test --workspace --features selahcue-lan/server`: **244 passed** (13 new this batch: 6 scripture-data incl. perf + bounded-memory, 2 controller verse-text/recovery regressions + 2 review regressions, compositor capacity pin, wire E2E, session v4 round-trip). Clippy `-D warnings` clean; operator crate clean.
- `flutter analyze` clean; `flutter test`: **18 passed** (command shape + pinned fixture parse + token audits).
- Wire E2E: `wire_scripture_search_stage_golive_shows_verse_text` — keyword search over the real TLS link → stage → Go Live → the host's live slide body contains the WEB text of Romans 8:28.
- Migration v3 → **v4** is append-only; the user's real store upgrades in place on next launch.

## Residual notes

- One translation bundled (WEB); ASV/BSB/BBE remain the story's stretch target — additional assets extend the crate.
- Passage pagination beyond the 6-line cap, verse text on the stage output, and mobile search-as-you-type are follow-on slices.
- Asset provenance: ebible.org `engwebp_vpl` export, converted to canonical-book TSV (5 non-verse source lines skipped — audited as headers, not verses).
