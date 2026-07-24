# Code Review — Batch 7ae (PD translation bundles: ASV, WEBBE, Darby)

- **Scope reviewed:** three additional public-domain translation bundles + the Translation-engine extension (Track 1 of story `86ajpqfyj`; acceptance: ≥3 more PD translations selectable in the chapter browser).
- **Method:** independent adversarial review via the Workflow tool (run `wf_aa9ffec5-e06`, 6 agents; 2 lenses: bundled-data integrity + licensing · integration) → per-finding adversarial verification, including a live fetch of ebible.org's copyright pages. No self-approval.
- **Raised → confirmed → unique:** **4 confirmed → 4 unique (A–D)** · 0 refuted.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | med | **BBE's public-domain status is US-only** (UCC non-notice; Cambridge UP; translator d. 1968 → plausibly in copyright until 2038 in life+70 jurisdictions incl. the UK, EU, and Nigeria) — the crate and the licensing register claimed unqualified PD while bundling the full text into every binary | **BBE dropped from the bundle**, replaced by the **WEB British Edition** (PD by dedication, worldwide-safe, 31,098 verses); the crate docs and `LICENSING-REGISTER.md` now record the exclusion + the owner decision needed for any US-only distribution |
| B | med | BBE carried `***` defective-text placeholders (7 verses; 1 Samuel 13:1 was *only* `***` — literal asterisks on the congregation display) | moot with BBE dropped; the conversion pipeline now strips the marker class everywhere |
| C | low | Darby's Psalm 119 had 19 dangling `*` footnote-apparatus markers ("Thy \*word have I hid…") | DBY regenerated with asterisks stripped; a **full-corpus residue scan test** now asserts no `[ ] ¶ *` characters across every verse of every bundled translation (~155k verses scanned) |
| D | med | A 7ae console against an older host confidently offered translations the host would silently deny (the picker was seeded shell-locally) | the host **advertises its translation list on the wire** (`OperatorStateView.translations`, skip-if-empty — fixtures byte-identical); the picker adopts the host's list, set-compared (not length-compared), with the selection falling back when no longer offered |

## Verification after remediation

- `cargo test --workspace --features selahcue-lan/server`: **260 passed** (incl. the new full-corpus residue scan and per-translation counts/wording: KJV 31,102 · WEB 31,098 · ASV 31,086 · WEBBE 31,098 · DBY 31,099). Clippy clean; operator crate clean; JS syntax-checked; Flutter **20**.
- All five bundles audited: canon shape, famous-verse wording per translation, no markup residue; lazy per-translation decode keeps memory bounded (untouched translations cost only compressed bytes; the no-leak test loops all five).

## Residual notes

- YLT has no usable ebible export (404) — stays on `86ajpqfyj` with the licensed set (NIV/NLT/…, licensing spike) and the BBE owner decision.
- Binary grows ~3.8MB compressed (5 assets ≈ 6.4MB total); cold-start unaffected (assets decode lazily).
