# Code Review — Batch 7ab (scripture chapter browser + KJV default + console rebalance)

- **Scope reviewed:** the Pewbeam-style chapter browser (verse list, arrow-key cursor with auto-stage, chapter paging), the KJV bundle + multi-translation engine (KJV default — owner decision 2026-07-24), the optional `translation` wire fields, and the console rebalance (Preview/Live as 16:9 thumbnails in the right column).
- **Method:** independent multi-lens adversarial review via the Workflow tool (run `wf_c5226f85-e91`, 13 agents): 3 finder lenses (browser interaction incl. the literal acceptance walk · KJV data + translation plumbing incl. an audit of the decompressed asset · restructure regression) → per-finding adversarial verification. No self-approval.
- **Raised → confirmed → unique:** **9 confirmed → 6 unique (A–F)** · 1 refuted (a stale-response guard concern — the generation guard already covers it). The data lens verified the KJV asset verbatim (31,102 verses, canon shape, brackets/pilcrows stripped, famous verses exact).

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | **Enter on a keyword query was a silent dead-end** that also destroyed the pending debounced search (type-then-Enter within 250ms: no hits, no chapter, no message, search cancelled) | Enter now: hits → open; else try as a chapter; else an **immediate** translation-aware search renders hits; a `role="status"` line surfaces "No matches"/chapter errors — never silent, never search-destroying |
| B | med | **Verse ranges collapsed to a single verse** — every UI path funneled through the chapter loader, which staged only the range start ("John 3:16-18" → v16 alone on air; a regression, the backend renders full ranges) | a typed range stages the **whole passage** and lands the cursor on its first verse without re-staging a single verse |
| C | med | **Translation switch kept the cursor INDEX** — KJV/WEB numbering diverges in six chapters (verified in the assets: WEB omits Luke 17:36, Acts 8:37/15:34/24:7; Romans 14/16 differ), so flipping the picker could silently stage a different verse | the switch carries the verse **NUMBER**; a verse absent from the new translation lands nearby **without staging** plus an explicit status ("Acts 8:37 is not present in WEB") |
| D | med | **Keyword search ignored the picker** — it always searched the KJV default (all 3 lenses found this) | `ScriptureSearch` gains optional `translation` (skip-if-none; fixtures byte-identical), threaded controller → shell → webview |
| E | low | The global `e.repeat` guard (correct for emergency keys) made **held arrows inert** in the verse list | arrows exempt from the repeat guard; staging trails the cursor by 120ms so a held arrow traverses without a wire burst |
| F | low | The bounded-memory test covered only the KJV index after the second bundle landed | the no-leak test now loops both translations' indexes |

## Verification after remediation

- `cargo test --workspace --features selahcue-lan/server`: **253 passed** (this batch: 2 reworked translation tests + chapter/paging coverage). Clippy `-D warnings` clean; operator crate clean; `node --check` on the webview script; Flutter **19**.
- Acceptance walk (as staged): type "Genesis 1" → Enter opens the chapter (KJV) → ↓ ↓ stages Genesis 1:3 → Enter (canonical Go Live) commits it to the audience output — preview→live safety intact.
- Wire compat: both new optional fields skip-if-none; all pinned fixtures byte-identical; Dart shapes unchanged.

## Residual notes

- The chosen translation is **not persisted**: crash recovery recomposes scripture in the default (KJV) — documented in `scripture_slide_in`; revisit with venue profiles.
- More PD bundles + licensed translations (NIV/NLT/…): story `86ajpqfyj` (licensing spike required for the commercial set).
- Visual QA of the rebalanced console on the user's machine pending.
