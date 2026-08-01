# Code Review — Batch: the TEXT element (Canvas Editing, 86ajq6j64)

- **Scope:** the **last missing `Element` kind** — a free text box on the slide canvas. The Canvas Editing epic shipped Shape + Image and a full kind-agnostic authoring layer (add/select/drag/resize/arrange/inspector/context-menu/keyboard), but `Element` had no `Text` variant and the Theme Designer's "Text" add button was disabled — a glaring hole (text is the most common slide element). Add `Element::Text` end-to-end: an engine variant that renders wrapped, auto-fit text in a per-mille rect (reusing the EXISTING title/body region text path), a raster fix so text honours the colour alpha (element opacity), a per-element content cap (no-leak), and the Theme Designer authoring. Executed via `/goal` (`TASK-86ajq6j64-text-element.md`, validator PASS `--require-complete`). Additive — no wire command, no migration.
- **Method:** an adversarial Workflow review `wf_027265e3-52b` — 3 lenses (engine-text-raster · model-serde-bounded · frontend-authoring) → **per-finding refute-by-default**, each finding checked by two perspective-diverse verifiers (correctness + reproduction). 7 agents. The riskiest change (the raster alpha-fold, which touches ALL text rendering) was scrutinised hardest.
- **Outcome:** 2 findings raised → **both confirmed (1 MEDIUM + 1 LOW), both fixed.** The **engine + serde/bounded lenses found nothing** — the raster alpha-fold is byte-identical for opaque text and the additive/bounded model is sound.

## What shipped

- **Engine (`selahcue-present`):** `Element::Text { rect, text, color, size_permille, line_height_permille, align_h, align_v, fit, opacity, z, font?, weight?, letter_spacing_permille? }` (additive tagged-enum variant; optional typography `skip_serializing_if`). Compose: an `element_layers` `Text` arm → per-mille rect + the whole-element opacity folded into the text-colour alpha (0 → no layers) → `autofit_layers(...)` — the **same** word-wrap/shrink-to-fit path the title/body regions use; z via the existing `compose_slide` sort. Bounded: `MAX_TEXT_ELEMENT_LEN = 2000` via `Theme::elements_bounded()` at all 3 theme-ingress sites.
- **Raster (`selahcue-engine`):** `draw_text` now folds the layer text-colour ALPHA into the glyph coverage — **byte-identical for opaque text** (`(c·255+127)/255 == c` exactly for every `c`), so every existing region render is unchanged; a translucent Text element dims uniformly. The GPU skips `Layer::Text`, so `test_parity` is untouched.
- **Operator (`dist/`):** the Theme Designer "Text" add button is enabled + a text inspector (content / colour / size / alignment); the kind-agnostic add/select/drag/resize/arrange/copy-paste/delete layer works unchanged.

## Findings and dispositions

| # | Lens | Sev | Finding | Verify | Fix |
|---|------|-----|---------|--------|-----|
| 1 | frontend | MEDIUM | The content textarea had **no client-side length bound**, so an operator could author a text box > `MAX_TEXT_ELEMENT_LEN` (2000). The host `set_custom_theme` then rejects it (`elements_bounded → false`, live output unchanged), but `act()` resolves Ok on a Deny in both backends and the Apply handler reports **"Applied to the audience output."** regardless — a **false success** (operator believes the long text is airing; the audience is on the old theme). The in-designer preview also renders it, reinforcing the illusion. | **2/2 REAL** | **Fixed at the root** — the textarea gets `maxlength="2000"` and the content handler slices to the cap (+ syncs the field + status), so the UI **can never author an over-cap element** → Apply never denies for this reason. Headless: "an over-cap paste is truncated to 2000 chars on the client". |
| 2 | frontend | LOW | When `save_theme` is denied for an over-long Text element, the operator sees the generic **"the name may be too long or the library is full"** — misdiagnosing the real cause (text over 2000 chars). | **2/2 REAL** | **Fixed by the same root fix** — the client cap means Save is never reached with an over-cap text element, so the message can no longer misfire for this cause. |

**No engine/raster/serde/determinism finding survived** (both those lenses returned empty). No HIGH.

### On the reviewer's structural note

The MEDIUM verifier also observed that the Apply handler reports success without verifying the reply (unlike the Save path, which checks the returned view) — a **pre-existing** gap for *any* denial cause, not specific to this batch. The UI's other custom-theme controls are all bounded, so text length was the one new UI-reachable denial; capping it at the source closes the reproducible hole. Making Apply verify acceptance generally (threading the accept/reject signal through `set_custom_theme` on both backends + the wire) is a legitimate but broader robustness follow-up, recorded below rather than folded into this element batch.

## Verification

- **Workspace:** `cargo test --workspace` **495/0** (+7: 6 engine/compose Text tests + the controller apply/recover/bounded test); the raster change kept every existing text + parity test green (byte-identical for opaque text); `--features server` green; fmt/clippy clean (workspace + operator).
- **Operator gates (run on the CI runner):** committed Chrome headless **90/90** (+9: button enabled, adds a text element, inspector shows + hides shape/image, head names Text, edits content, size%→permille, alignment, the over-cap client cap) + WebKit smoke **5/5**.
- **3-OS CI:** `<pending — verified by run conclusion>`.
- **Owner on-device QA (optional):** the definitive "add a text box, type into it, drag/resize it, send it behind the verse" is owner-run on the real Tauri GUI; the headless + Rust assertions are the strongest short of the GUI.

## Follow-ups

- Apply-handler honesty: verify the host actually accepted a `SetCustomTheme` before reporting success (a pre-existing gap; needs an accept/reject signal through both backends). Rich text (per-run styling), rotation, vertical text (unchanged seams). Line/star/polygon shapes; gradients; aspect-preserving image fit — the other Canvas Editing R-later seams.
