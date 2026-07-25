# Goal Contract — TASK-86ajpzha7-text-shaping

## Identity

- Goal ID: TASK-86ajpzha7-text-shaping
- Parent goal ID: STAGE8-core-presentation
- Title: Output text is shaped with a real font stack (cosmic-text/rustybuzz) so Unicode + diacritics (Yoruba/Hausa/Igbo/French/Spanish) render correctly on every output, deterministically across all three OSes
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajpzha7
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Replace the ASCII-only `font8x8` bitmap glyph path in `selahcue-engine::raster::draw_text` with real font shaping + rasterization per ADR-0014 (cosmic-text + rustybuzz over a bundled OFL font), so FR-017's acceptance holds: "diacritic glyphs shape/render correctly on output; font fallback covers the character set."

## Baseline

Verified: the single output-text seam is `selahcue-engine/src/raster.rs::draw_text`, which renders `Layer::Text{rect,text,px,color}` with `font8x8::legacy::BASIC_LEGACY`, **skipping every non-ASCII char** (`code < 128`) — so "María" drops the í and Yoruba/Igbo marks vanish. The GPU compositor (`selahcue-gpu`) renders Fill layers only and **CPU-rasterizes text via this same path, then blits** (its own comments), so fixing `draw_text` fixes all output text; the GPU SSIM parity oracle covers Fill, not text. `compose.rs::layout_lines` produces one `Layer::Text` per line — that layout stays; only per-line rasterization changes. A subset OFL font is bundled at `crates/selahcue-engine/assets/fonts/NotoSans-Latin.ttf` (127 KB, Regular instance, verified to cover í/ẹ/ọ/ṣ/ị/ṅ + combining marks) with `OFL.txt`.

## Inputs and evidence sources

- Story 86ajpzha7 (S8-2) + epic 86ajp07ce (FR-017/023/024); ADR-0014 (cosmic-text/rustybuzz decision), ADR-0002 (compositor); FR-173 (memory-safe font decode); NFR-014 (cross-OS parity); the bundled font; raster.rs / compose.rs / test_raster.rs / test_parity.rs.

## Scope

### In scope

- Add `cosmic-text` to `selahcue-engine`; a process-wide font system loading ONLY the bundled font (system fonts disabled for determinism/parity).
- Rewrite `draw_text` to shape the line with cosmic-text (rustybuzz) and rasterize each glyph (swash) to alpha coverage, blended into the FrameBuffer at the layer rect/colour, clipped as today, sized to ≈`px`.
- Preserve the existing behaviour surface: title + up-to-6-body-line slides still fit (the compose caps are unchanged); blackout/fill unaffected; bounded work (no unbounded glyph caches — a fixed-capacity or per-render cache).
- Tests: non-ASCII now renders (a diacritic string produces glyph coverage where font8x8 produced none); determinism (same input → identical FrameBuffer bytes); the compose/stage/parity suites stay green.

### Non-goals

- GPU-native glyph atlas (glyphon path — a later batch; text stays CPU-rasterized + blitted as today); RTL/complex-script (R6/FR-018); the operator-webview text (that's the OS web stack, ADR-0003); theme/imported fonts (FR-173 path — later).

### Constraints

- Deterministic + identical on all 3 OSes (one bundled shaper+font, no system fonts) — NFR-014; memory-safe pure-Rust parser (rustybuzz/ttf-parser) — FR-173; no unbounded growth; the OFL font + license bundled and picked up by the license/SBOM scan; slide-trigger latency budget still met.

### Assumptions and unknowns

- ASSUMED: cosmic-text's swash rasterization of the bundled static font is byte-deterministic across OSes for a fixed input. VALIDATION: a determinism test + CI on 3 OSes.
- UNKNOWN(S10 residual): exact mark-stacking fidelity for every combining sequence — verified for the precomposed FR-017 set; recorded honestly.

## Dependencies and approvals

- None blocking (8b is on the critical path after 8a).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | draw_text shapes+rasterizes via cosmic-text over the bundled OFL font (system fonts disabled); ASCII text still renders legibly | `cargo test -p selahcue-engine` | raster tests pass incl. ASCII | raster.rs | PENDING |
| C-002 | yes | Non-ASCII diacritics render: "María" shows the í, and a Yoruba/Igbo string (ẹ/ọ/ṣ/ị) produces non-empty glyph coverage where font8x8 produced NONE | diacritic raster test | coverage present for non-ASCII | test_raster.rs | PENDING |
| C-003 | yes | Deterministic: the same (text, px, colour, rect) renders byte-identical FrameBuffers (single bundled shaper → cross-OS parity) | determinism test + 3-OS CI | identical bytes; CI green on 3 OSes | test_raster.rs; CI | PENDING |
| C-004 | yes | No regression: compose/stage/present/parity suites green; bounded work (no unbounded font/glyph cache); slide-trigger budget intact | full workspace tests | all green | test_compose/stage/parity | PENDING |
| C-005 | yes | The OFL font + license are bundled and the dependency-audit + supply-chain (license/SBOM) CI jobs pass with the new deps (cosmic-text tree) + the font licence | CI audit + supply-chain jobs | green | CI | PENDING |
| C-006 | yes | Full verification: fmt/clippy clean, CI green on 3 OSes; independent adversarial review, confirmed findings fixed | make-ci + Workflow review | all green; review record | CODE-REVIEW-batch8b.md | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: raster tests (ASCII legibility, diacritic coverage, determinism). Broader: full workspace + fmt/clippy; the 3-OS CI matrix (proves cross-OS byte parity + the audit/supply-chain jobs with the new deps + font licence). Independent: adversarial Workflow review (determinism/parity lens · memory-safety/bounds lens · correctness-of-shaping lens · dependency/licence lens).
- Required environment: local + 3-OS CI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001/C-002
- Hypothesis: a lazily-initialized cosmic-text FontSystem loaded with only the bundled font, plus a SwashCache, shaping each `Layer::Text` line and blending swash alpha into the FrameBuffer, renders ASCII + diacritics correctly and deterministically.
- Change or investigation: add the dep + font loader; rewrite draw_text; add tests.
- Verifier executed: (pending)
- Result: (pending)
- New evidence: (pending)
- Decision: iterate

## Risks and rollback

- Risks: cosmic-text rasterization non-determinism across OSes (mitigated: pure-Rust swash + a single static bundled font + a CI 3-OS byte check); dependency-tree size hitting the audit/licence jobs; latency of shaping (mitigated: bounded cache, ≈per-line shaping). Rollback: git; the change is contained to selahcue-engine + a bundled asset.

## Pause and escalation conditions

- If cosmic-text rasterization proves non-deterministic across OSes, fall back to asserting a perceptual (coverage/centroid) invariant instead of byte-equality, and record the divergence honestly (do not claim byte parity it doesn't have).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajpzha7-text-shaping.md`
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: IN_PROGRESS → GATE_REVIEW
- Remaining failed or blocked criteria: all PENDING
- ClickUp final evidence comment: PENDING
