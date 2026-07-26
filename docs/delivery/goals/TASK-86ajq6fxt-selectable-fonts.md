# Goal Contract — TASK-86ajq6fxt-selectable-fonts

## Identity

- Goal ID: TASK-86ajq6fxt-selectable-fonts
- Parent goal ID: STAGE8-core-presentation
- Title: Selectable system fonts in themes — opt-in, with the bundled Noto Sans as the deterministic default
- Role: backend-engineer (engine/theme/enumeration) + a thin frontend wire (Designer font picker)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq6fxt
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 16
- Independent verification required: yes

## Objective

Let a theme select a font from those installed on the machine running the output (no bundled fonts added), while keeping the bundled Noto Sans as the **deterministic default** so a theme with no font set renders byte-identically on every OS (NFR-014, unchanged). The Theme Designer's "Font" control becomes a real picker.

## Baseline

Verified from code:
- **Engine** (`selahcue-engine/src/raster.rs`) renders text via **cosmic-text** (rustybuzz + swash) over a **single BUNDLED font** (`FONT_BYTES = include_bytes!("../assets/fonts/NotoSans-Latin.ttf")`). System fonts are deliberately NOT loaded ("shaping is deterministic and identical across OSes → NFR-014"). A per-thread `TextCtx { fs, cache }` rebuilt every `RESET_EVERY=4096` renders (bounded). `draw_text` + `measure_line_width` shape with `Attrs::new()` (default = the bundled font).
- **Scene** (`scene.rs`): `Layer::Text { rect, text, px, color, align }` — no font field. `compose.rs` `autofit_layers` builds `Layer::Text`.
- **Theme** (`theme.rs`): a fixed-size `Copy` POD (`background: Rgba`, `title`/`body: RegionStyle`, `band`). The comment marks "the single bundled font family; multi-weight fonts are later slices."
- `arrayvec` (a `Copy` bounded string) is already a transitive dependency; `fontdb::load_system_fonts()` (fontdb 0.16.2, via cosmic-text) enumerates + loads installed fonts.
- The theme flows to the output via its serialized JSON (`SetCustomTheme`/`SaveTheme`, the saved-theme table, `session_state.custom_theme`) — a Theme font field rides in that JSON, so **no new wire command and no migration** are needed.

## Scope

### In scope

- **Engine (`raster.rs` + `scene.rs`):** `Layer::Text` gains an optional font family (a bounded `Copy` name; `None` = the bundled default). `draw_text` + `measure_line_width` take the font and render/measure with it: `None` → the existing bundled-only `TextCtx` (byte-identical, deterministic); `Some(family)` → a **lazily-loaded** system `FontSystem` (`load_system_fonts`, with the bundled font as the fallback so a missing/unknown family degrades to Noto Sans, never tofu/panic). Memory stays bounded (the periodic reset covers the system context too). The GPU backend compiles with the new field (parity unaffected — parity/pinned tests use the default font).
- **Theme model + compose (`theme.rs` + `compose.rs`):** `Theme.font: Option<FontName>` where `FontName` is a bounded `Copy` string (`arrayvec::ArrayString`) so `Theme` stays a fixed-size POD; empty/`None` = default; additive serde (`skip_serializing_if = Option::is_none`, so a default-font theme's JSON is byte-identical → pinned theme fixtures/tests unchanged). `compose` threads `theme.font` into every `Layer::Text`.
- **Enumeration + persistence:** a `system_fonts()` operator command (like `builtin_themes`/`preview_theme`) returns the installed family names (sorted, deduped, **bounded** to a sane cap). The font persists inside the theme JSON (saved library + custom theme) — **no new wire command, no migration**; assert `target_version` + pinned fixtures unchanged.
- **Frontend (Theme Designer):** the "Font" control (`#td-font`, today a disabled "Noto Sans (bundled)" placeholder) becomes a real `<select>` populated from `system_fonts()` (+ a "Noto Sans (default)" entry = clear); selecting sets `tdTheme.font`; the live preview (`preview_theme`) + Apply render it. WKWebView-safe; pinned console invariants intact.

### Non-goals (seams — note)

- Multi-weight / italic / letter-spacing selection (later slice, FR-173 remainder). Per-region fonts (this batch is per-theme, one family for the whole theme). Font-file import; embedding a font file into the theme (would break the bounded-POD invariant). CJK/complex-script coverage beyond what the chosen system font provides.

### Constraints

- **Determinism preserved:** the default (no-font) path is byte-identical to today — the parity (`test_parity`) + pinned-render tests stay green on all 3 OSes. A themed font renders per-machine (documented). **No new wire command and no migration** — `target_version` unchanged, pinned v2 fixtures byte-stable. Bounded memory (bounded font name; bounded enumeration; periodic cache reset). No-leak / determinism for the default. `Theme` stays `Copy`. fmt/clippy clean; 3-OS CI.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Engine: `Layer::Text` optional font; `draw_text`/`measure_line_width` render/measure the selected system font (lazy system `FontSystem`) or the bundled default; the DEFAULT (no-font) render is byte-identical to before; a missing/unknown family falls back to the bundled font (no tofu/panic); bounded memory | `cargo test -p selahcue-engine` | selected font renders; default unchanged; fallback safe | test_raster/test_engine | PASS |
| C-002 | yes | Theme + compose: `Theme.font: Option<FontName>` (bounded `Copy`; `Theme` still a fixed-size POD) threaded through `compose` to the Text layers; a themed font renders; additive serde (empty font → theme JSON byte-identical; pinned fixtures unchanged) | `cargo test -p selahcue-present` | per-theme font renders; serde additive | test_compose/test_slide/test_tokens | PASS |
| C-003 | yes | Enumeration + no wire/migration: `system_fonts()` lists installed families (sorted, deduped, bounded); the font persists in the theme JSON only — `target_version` unchanged, pinned wire fixtures byte-stable | `cargo test -p selahcue-lan -p selahcue-data` + operator build | enumeration bounded; no wire/migration drift | test_protocol/test_db + operator | PASS |
| C-004 | yes | Frontend: the Theme Designer Font control is a real picker from `system_fonts()`; selecting a font sets the theme font; the preview + Apply render it; a "default" entry clears it; pinned console invariants intact | structure test + headless render | font picker works; invariants intact | test_tokens + render | PASS |
| C-005 | yes | Full: make ci + operator build + fmt/clippy clean; determinism preserved (parity + pinned render tests green); independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed; parity holds | CODE-REVIEW-batch-selectable-fonts.md; CI run 30223399683 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-engine` (a selected font renders differently from the default; the default render is byte-identical to a captured baseline; a bogus family falls back to the bundled font; bounded over many renders), `-p selahcue-present` (Theme.font threads through compose; empty-font serde byte-identical; a themed compose differs), `-p selahcue-lan`/`-p selahcue-data` (no fixture/migration drift; `target_version` unchanged), a headless render of the Theme Designer with a font picker. Broader: make ci + 3-OS CI (parity must hold). Independent: adversarial Workflow review (determinism/fallback/no-leak · theme-serde/no-drift · frontend/invariant lenses).
- Required environment: local + CI (3-OS parity is the key determinism gate).

## Iteration ledger

- **Iter 1 — engine (C-001).** `scene.rs`: `Layer::Text.font: Option<FontName>` (additive serde) + a new `FontName` = a `Copy` bounded string (newtype over `arrayvec::ArrayString<64>`, transparent serde, `FontName::new` trims + rejects empty/>64B). `raster.rs`: a lazy `TextCtx.system_fs`; `build_bundled_fs` (the unchanged deterministic default) vs `build_system_fs` (bundled + `load_system_fonts`, bundled family set as the fallback for all default families); `draw_text` + `measure_line_width` take the font (None → bundled fs, byte-identical; Some → the lazy system fs); `tick` drops `system_fs` on reset (bounded); `system_font_families()` (sorted/deduped/bounded). Evidence: `test_raster` (4 new: missing→readable+deterministic fallback, a selected font differs, enumeration sorted/deduped/bounded, bounded over many renders) + the existing pinned/parity tests still green (default byte-identical). **PASS.**
- **Iter 2 — theme + compose (C-002).** `theme.rs`: `Theme.font: Option<FontName>` (additive `skip_serializing_if`; `Theme` stays a `Copy` POD). `compose.rs`: threaded `theme.font` through `autofit_layers` (measure + `Layer::Text`) + `layout_region` + `compose_slide` (title + body). `stage.rs`: passes `None` (the confidence monitor keeps the bundled font). Evidence: `test_compose` (2 new: additive+byte-stable serde; a themed font changes the composed slide). **PASS.**
- **Iter 3 — enumeration + no wire/migration (C-003).** `system_fonts()` Tauri command (returns `system_font_families`). Confirmed **no** change to `protocol.rs`/`migrations.rs`/`rbac.rs` — `target_version` unchanged, pinned v2 fixtures byte-stable (`test_protocol`/`test_db` green, 85 lan+data tests). The font rides in the theme JSON (`SetCustomTheme`/`SaveTheme`, saved_theme table, session custom_theme). **PASS.**
- **Iter 4 — frontend (C-004).** `index.html`: the Font control is now an enabled `<select>` (was a disabled "later" placeholder) with a "Noto Sans (default)" option. `app.js`: `tdLoadFonts()` populates it from `system_fonts()`; onchange sets `tdTheme.font` (or `delete tdTheme.font` for the default → byte-stable JSON); `tdSync` reflects it. Evidence: `test_tokens` pin (picker enabled + wired + not the disabled placeholder) + a headless check (options populated: Noto Sans (default)|Arial|Georgia|Helvetica Neue; selecting Georgia flows `"font":"Georgia"` to the preview; default clears the field). **PASS.**
- **Iter 5 — gate (C-005).** `cargo fmt --check` clean (main + operator workspaces); `clippy -D warnings` clean on every target this batch touches (removed a duplicate `#[allow(too_many_arguments)]`); engine/present/gpu tests green incl. **test_parity** (determinism preserved); app+lan+data 166/0; operator builds; `node --check` clean. `arrayvec` added as a direct dep (already transitive). Independent adversarial Workflow review (`wf_a5313bef-b7e`, 3 lenses → per-finding verify, 7 agents): **4 raised → 3 confirmed (1 MED + 2 LOW), all fixed; 1 refuted.** (MED) `#[serde(transparent)]` bypassed `FontName::new`, so `{"font":""}`/`{"font":" Arial "}` slipped through the wire → replaced with a **validating** manual (de)serialize + a test. (LOW) dead `set_*_family` calls + a false "Noto Sans fallback" claim → removed + corrected the honest "readable platform font" guarantee. (LOW) the picker blanked an un-installed saved-theme font → `tdEnsureFontOption` reflects it "(not installed here)". Re-verified: determinism gate 116/0 (parity holds), fmt/clippy clean, headless checks. See `docs/delivery/CODE-REVIEW-batch-selectable-fonts.md`. CI green pending this push.

## Risks and rollback

- Risks: breaking the deterministic default (mitigated: the no-font path uses the unchanged bundled-only `TextCtx`; a byte-identical guard test + the existing parity/pinned tests); a missing font rendering tofu or panicking (mitigated: the system `FontSystem` includes the bundled font as the fallback family; a bogus-family test); unbounded memory from a system `FontSystem` (mitigated: lazy load + the periodic reset covers it; a bounded-over-many-renders test); `Theme` accidentally becoming non-`Copy` (mitigated: a bounded `arrayvec::ArrayString`, not a `String` — a compile-time `Copy` assertion); wire/migration drift (mitigated: NONE — the font rides in the theme JSON; assert fixtures + `target_version` unchanged); a huge system-font list bloating the picker/IPC (mitigated: a sane cap + dedupe + sort). Rollback: git; additive across crates.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq6fxt-selectable-fonts.md --require-complete`
- Validator result: PASS (all 5 mandatory criteria PASS).
- Independent verification result: adversarial Workflow review `wf_a5313bef-b7e` (3 lenses → per-finding verify, 7 agents) — 4 raised → 3 confirmed (1 MED + 2 LOW), all fixed; 1 refuted. 3-OS CI run 30223399683 GREEN (11/11 jobs incl. the rust/parity determinism gate on all 3 OSes; Flutter path-skipped). Committed to main as `e44bc56` (cherry-picked — a parallel QA-programme process had switched the tree onto its branch; my commit was extracted to main and the parallel branch restored).
- Terminal state: VERIFIED_COMPLETE (story `86ajq6fxt` handed to QA; not self-marked Done).
- ClickUp final evidence comment: posted on 86ajq6fxt (comment 90130296744099); commit `e44bc56`.
