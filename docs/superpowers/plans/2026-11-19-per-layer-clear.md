# Per-Layer Clear Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The operator can clear one part of the live slide (text, background, lower-third band or logo) while the other parts stay on the audience output, from the console, the keyboard (Backspace = text) and the phone.

**Architecture:** The compositor already draws a slide as separate categories behind a per-output `LayerMask` (`selahcue-present/src/compose.rs:503`). We add a *live-only* set of cleared layers to `Presenter`. Live (main and secondary screens) is composed with `screen mask AND NOT cleared`; Preview never is. Going live, presenting, identify and full clear reset the set. A new `clear_layer` LAN command carries it, and the operator state reports which layers are cleared.

**Tech Stack:** Rust (selahcue-present, selahcue-app, selahcue-lan, selahcue-desktop, selahcue-operator/Tauri), vanilla JS webview (`selahcue-operator/dist/app.js`), Flutter/Dart (`implementation/mobile/selahcue_controller`).

**Spec:** `docs/superpowers/specs/2026-11-19-public-beta-design.md`, W3 "Per-layer clear". ClickUp 86ajpy59e. PRD FR-078 (`docs/product/prds/SelahCue-PRD.md:219`).

## Global Constraints
- The layer tags are exactly `background`, `text`, `lower-third`, `logo`. They are the same strings `SetScreenLayerVisible` accepts (`selahcue-app/src/controller.rs:1816`). `timer` is rejected, because it is not on the audience compose path.
- Wire shape: `{"cmd":"clear_layer","layer":"text"}`. Change the Rust and Dart sides together (repo rule).
- The new `OperatorStateView` field is `#[serde(default, skip_serializing_if = "Vec::is_empty")]`, so the pinned `operator_state` fixture in `wire_fixtures_are_stable_for_cross_language_clients` stays byte-identical.
- RBAC: `ClearLayer` requires `Permission::ClearLive`, the same as `Clear`.
- Blackout, clear-all, double-Esc and every existing keybinding behave exactly as today. Backspace changes from clear-all to clear text.
- The cleared set is at most 4 flags. There is no queue or history, so there's nothing unbounded.
- Cleared layers are not persisted. Session restore starts with none cleared.
- Work in your own worktree and branch, cut from `origin/main` and named for 86ajpy59e. Make one PR. `make ci` must be green before review.

## Decisions taken in this plan (owner can override)
- **Going live with any new content resets the cleared set.** Clearing text on verse 1 and then going live on verse 2 shows verse 2's text. This matches how operators use "clear text".
- **On an authored deck slide, ClearLayer acts as a full Clear.** Authored slides are composed as their own elements, with no theme-layer categories (`present.rs` `set_main_layer_mask` comment). The controller routes it, so Backspace on a deck still clears.
- **Clearing every layer keeps the slide live with a background-free black frame.** It is not converted to a full Clear, so the LIVE ring and the next go-live behave as normal.
- **Phone gets one button, "Clear text".** The console gets the full picker.

## Review Focus
1. **Backspace while a text field has focus** (rename, search, notes) must edit the text and not clear the live layer. The existing app.js keydown guard has to keep covering Backspace. The test is in Task 5.
2. **A theme switch or a screen-mask change while text is cleared** must keep the text cleared. Any recompose path that uses `main_layer_mask` directly would bring it back. The test is in Task 1.
3. **Secondary and NDI screens** must drop the cleared layer too, not only main. The test is in Task 1.
4. **Blackout on, clear text, blackout off** must come back with the text still cleared. Blackout is orthogonal. The test is in Task 2.
5. **Old phone clients** that don't know `cleared_layers` must still parse state. The field is optional and skip-if-empty. The test is in Task 4.

---

### Task 1: Live-only cleared layers in the Presenter

**Files:**
- Modify: `implementation/desktop/crates/selahcue-present/src/compose.rs` (next to `LayerMask`, ~503)
- Modify: `implementation/desktop/crates/selahcue-present/src/present.rs` (struct at 27-74, every live compose site: `go_live` 186, `set_theme` ~258, `set_main_screen_theme` ~293, `set_main_layer_mask` 334, `compose_screen_live` 379, `set_live_theme` 421, `clear_live` 443, `present_authored` 229, `identify` 466)
- Test: `implementation/desktop/crates/selahcue-present/tests/test_present.rs`

**Interfaces:**
- Produces (in `compose.rs`, re-exported where `LayerMask` is):
  - `pub enum LiveLayer { Background, Text, LowerThird, Logo }` (Debug, Clone, Copy, PartialEq, Eq)
  - `impl LiveLayer { pub fn from_tag(tag: &str) -> Option<LiveLayer>; pub fn tag(self) -> &'static str }`, mapping `"background"|"text"|"lower-third"|"logo"`
  - `pub const LiveLayer::ALL: [LiveLayer; 4]`, in composite order: Background, LowerThird, Logo, Text
  - `impl LayerMask { pub fn without(self, cleared: LayerMask) -> LayerMask }`: a field-wise `self.x && !cleared.x`
  - `pub const LayerMask::NONE`: all fields false
- Produces (in `present.rs`, on `Presenter`):
  - private field `live_cleared: LayerMask`, initialised to `LayerMask::NONE`
  - `pub fn clear_live_layer(&mut self, layer: LiveLayer) -> bool`. It sets the flag and recomposes Live from `live_slide` with `main_layer_mask.without(live_cleared)`. It returns `false`, with no state change, when nothing title+body is live (`live_slide` is None, including when an authored slide is live). Like `set_theme`, it doesn't handle blackout itself: the caller re-applies it.
  - `pub fn cleared_live_layers(&self) -> Vec<LiveLayer>`, in `LiveLayer::ALL` order
  - private `fn live_mask(&self) -> LayerMask` returning `self.main_layer_mask.without(self.live_cleared)`. **Every Live compose site uses it**, and Preview sites keep `main_layer_mask`.
  - `compose_screen_live(screen_theme, mask)` composes with `mask.without(self.live_cleared)`
  - `go_live`, `present_authored`, `identify` and `clear_live` reset `live_cleared` to `NONE`

- [ ] **Step 1: Write the failing tests** in `test_present.rs`, using the existing helpers there (see `clear_blanks_live_but_not_preview`, line 229):
  - `clear_text_layer_keeps_background_on_live`: go live with a slide that has a solid background and body text. Call `clear_live_layer(LiveLayer::Text)`. The result is true. The live frame equals `compose_slide_masked(slide, theme, w, h, LayerMask { text: false, ..LayerMask::ALL })`, and it differs from the unmasked frame.
  - `clear_layer_leaves_preview_untouched`: the staged preview frame is byte-identical before and after `clear_live_layer(Text)`.
  - `go_live_resets_cleared_layers`: clear Text, stage another slide and `go_live()`. Then `cleared_live_layers()` is empty, and the live frame equals the full composition.
  - `cleared_layer_survives_theme_and_mask_changes`: clear Text, then call `set_theme(other)`, `set_live_theme(Some(t))` and `set_main_layer_mask(LayerMask { logo: false, ..ALL })`. After each, the live frame has text off (Review Focus 2).
  - `secondary_screen_drops_cleared_layer`: clear Text. `compose_screen_live(None, LayerMask::ALL)` equals the raster of the text-off composition (Review Focus 3).
  - `clear_layer_with_nothing_live_is_noop`: with nothing live, the call returns false and `cleared_live_layers()` is empty.
  - `clear_layer_on_authored_slide_is_noop`: after `present_authored`, the call returns false and the live frame is unchanged.
  - `live_layer_tags_round_trip`: `from_tag(l.tag()) == Some(l)` for all four, and `from_tag("timer") == None`.

- [ ] **Step 2: Run them and confirm they fail.** Run `cargo test -p selahcue-present --test test_present clear_ go_live_resets cleared_ secondary_screen live_layer` from `implementation/desktop`. Expected: a compile failure, because `LiveLayer` and `clear_live_layer` don't exist yet.

- [ ] **Step 3: Implement the Interfaces above.**

- [ ] **Step 4: Run the whole crate.** Run `cargo test -p selahcue-present`. Expected: all pass, including the 30 existing `test_present` tests and the 63 `test_compose` tests, unchanged.

- [ ] **Step 5: Commit.** Run `git commit -m "present: live-only per-layer clear (86ajpy59e)"`.

### Task 2: Controller command, RBAC and operator state

**Files:**
- Modify: `implementation/desktop/crates/selahcue-lan/src/protocol.rs` (`enum Command` 42-61; `OperatorStateView` 1146)
- Modify: `implementation/desktop/crates/selahcue-lan/src/rbac.rs` (`required_permission` 124)
- Modify: `implementation/desktop/crates/selahcue-app/src/controller.rs` (`apply_at` 2823, near `Command::Clear` 2978; `operator_view` ~2600)
- Modify: `implementation/desktop/crates/selahcue-app/src/operator.rs` (`OperatorView` 67; `OperatorShell` ~277; `RemoteOperator` ~1130)
- Test: `selahcue-lan/tests/test_protocol.rs`, `selahcue-lan/tests/test_rbac.rs`, `selahcue-app/tests/test_controller.rs`

**Interfaces:**
- Consumes: `LiveLayer::from_tag`, `Presenter::clear_live_layer`, `Presenter::cleared_live_layers`, `Presenter::authored_live_id` (Task 1).
- Produces:
  - `Command::ClearLayer { layer: String }` → `{"cmd":"clear_layer","layer":"text"}`
  - `OperatorStateView.cleared_layers: Vec<String>` with tags in `LiveLayer::ALL` order, skip-if-empty. Mirror it as `OperatorView.cleared_layers: Vec<String>`.
  - Controller behaviour:
    - An unknown tag (including `timer`) gets `Deny(BadRequest)`, and state is unchanged.
    - If an authored slide is live, it does exactly what `Command::Clear` does (one shared private fn, not a copy).
    - Otherwise it calls `presenter.clear_live_layer`, then re-applies `presenter.blackout(true)` if `self.blackout` is on, as the theme-switch paths do. It returns Ack whether or not anything was live, as Clear does.
    - `self.blackout` is never changed.
  - `OperatorShell::clear_layer(&self, layer: &str) -> OperatorView` and `RemoteOperator::clear_layer(&self, layer: &str) -> OperatorView`, both sending `Command::ClearLayer`.

- [ ] **Step 1: Write the failing tests**
  - `test_protocol.rs`, in `command_tag_encoding_is_stable`: `to_json(&Command::ClearLayer { layer: "text".into() })` equals `r#"{"cmd":"clear_layer","layer":"text"}"#`. Add a decode round-trip. Then a new test, `operator_state_cleared_layers_is_additive`: the default state serialises without `cleared_layers`, and a state with `vec!["text".into()]` contains `"cleared_layers":["text"]`. `wire_fixtures_are_stable_for_cross_language_clients` stays unedited and passes.
  - `test_rbac.rs`: `required_permission(&Command::ClearLayer{..}) == Permission::ClearLive`. Operator and Producer are authorised; Assistant and Viewer are not.
  - `test_controller.rs` (next to `clear_and_blackout_act_on_live`, line 107):
    - `clear_layer_text_keeps_item_live`: go live on an item, then send `ClearLayer{text}`. The reply is Ack, `live_index` is unchanged, and `operator_view().cleared_layers == ["text"]`.
    - `clear_layer_rejects_unknown_and_timer`: `"timer"` and `"bogus"` both get `Deny(BadRequest)`, and `cleared_layers` stays empty.
    - `clear_layer_on_authored_slide_clears_all`: present an authored slide, then send `ClearLayer{text}`. `live_authored_id` is None, as it would be after Clear.
    - `blackout_then_clear_layer_then_unblackout`: blackout on, `ClearLayer{text}`, blackout off. During blackout the live output is still black. After it, `blackout == false` and `cleared_layers == ["text"]` (Review Focus 4).
    - `clear_layer_within_200ms_budget`: mirror `blackout_and_clear_are_local_and_act_within_200ms` (line 49) for `ClearLayer`.

- [ ] **Step 2: Run them and confirm they fail.** Run `cargo test -p selahcue-lan --test test_protocol --test test_rbac` and `cargo test -p selahcue-app --test test_controller clear_layer blackout_then_clear_layer`. Expected: a compile failure, because there is no `ClearLayer` variant yet.

- [ ] **Step 3: Implement the Interfaces above.** Also add any exhaustive `match` arms the compiler demands, for example `handler_for` (controller.rs:4331).

- [ ] **Step 4: Run the touched crates.** Run `cargo test -p selahcue-lan --no-fail-fast` and `cargo test -p selahcue-app --features server --no-fail-fast`. Expected: all pass.

- [ ] **Step 5: Commit.** Run `git commit -m "lan/app: clear_layer command and cleared_layers state (86ajpy59e)"`.

### Task 3: Desktop keymap and Tauri command

**Files:**
- Modify: `implementation/desktop/crates/selahcue-app/src/keymap.rs` (module doc 15-19; `ClearLayer` doc 60)
- Modify: `implementation/desktop/crates/selahcue-desktop/src/main.rs:3924-3928`
- Modify: `implementation/desktop/crates/selahcue-operator/src/main.rs` (beside `async fn clear` 1865; register in the `invoke_handler` list)
- Test: `selahcue-app/tests/test_keymap.rs`

**Interfaces:**
- Consumes: `Command::ClearLayer`, `OperatorShell::clear_layer`, `RemoteOperator::clear_layer` (Task 2).
- Produces:
  - Tauri command `async fn clear_layer(layer: String, state: ...) -> Result<OperatorView, String>`, dispatching through `Backend::{Remote, Local}` exactly as `clear` does
  - `selahcue-desktop`: `CanonicalAction::ClearLayer` drives `Command::ClearLayer { layer: "text".into() }`

- [ ] **Step 1: Write the failing test.** In `test_keymap.rs:39` the existing Backspace → `ClearLayer` mapping is kept. Add `clear_layer_targets_text`: assert the exported constant `keymap::CLEAR_LAYER_DEFAULT_TAG == "text"`. Add that constant in `keymap.rs` and use it in `selahcue-desktop/src/main.rs`.
- [ ] **Step 2: Run** `cargo test -p selahcue-app --test test_keymap`. Expected: FAIL (the constant is missing).
- [ ] **Step 3: Implement it.** Update the keymap docs: Backspace now clears the text layer, and the clear-all aliasing note for 86ajpy59e is removed.
- [ ] **Step 4: Run** `make check` and `cargo test -p selahcue-app --test test_keymap`. Expected: PASS. The operator crate compiles; run `make stage-operator-binaries` first in a fresh worktree.
- [ ] **Step 5: Commit.** Run `git commit -m "desktop: Backspace clears the text layer (86ajpy59e)"`.

### Task 4: Phone controller (Dart)

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/models/protocol.dart` (beside `cmdClear` 44; `OperatorStateView` 217-282)
- Modify: `implementation/mobile/selahcue_controller/lib/models/rbac.dart` (CommandAction map 189-192)
- Modify: `implementation/mobile/selahcue_controller/lib/views/widgets/mobile_widgets.dart` (beside the Clear button, ~630)
- Test: `test/models/protocol_test.dart`, the RBAC test beside it, and the widget test for the live controls

**Interfaces:**
- Consumes: the wire shapes from Task 2.
- Produces:
  - `Map<String, dynamic> cmdClearLayer(String layer)` returning `{'cmd': 'clear_layer', 'layer': layer}`
  - `OperatorStateView.clearedLayers: List<String>`, defaulting to `const []` when the key is absent
  - `'clear_layer'` mapped to `Capability.clearLive`
  - a "Clear text" button, shown when the role has `clearLive`, sending `cmdClearLayer('text')`, and shown as pressed when `clearedLayers.contains('text')`

- [ ] **Step 1: Write the failing tests**
  - `protocol_test.dart`, in `'command shapes are internally tagged'`: `cmdClearLayer('text')` equals `{'cmd':'clear_layer','layer':'text'}`, byte-for-byte matching the Rust string from Task 2.
  - `'operator state without cleared_layers parses to empty'` (Review Focus 5): the pinned operator_state JSON parses with `clearedLayers` empty.
  - `'operator state with cleared_layers parses'`: `["text"]` parses to `['text']`.
  - RBAC: `clear_layer` is allowed for operator and producer, denied for assistant and viewer.
  - Widget: tapping "Clear text" sends `cmdClearLayer('text')`, and a viewer doesn't see the button.
- [ ] **Step 2: Run** `flutter test test/models/protocol_test.dart` from `implementation/mobile/selahcue_controller`. Expected: FAIL (`cmdClearLayer` is not defined). Prepend `/opt/homebrew/bin` and the Documents Flutter SDK to PATH if `flutter` isn't found.
- [ ] **Step 3: Implement the Interfaces above.**
- [ ] **Step 4: Run** `make mobile-test`. Expected: all pass.
- [ ] **Step 5: Commit.** Run `git commit -m "mobile: clear text layer control (86ajpy59e)"`.

### Task 5: Operator console (webview)

**Files:**
- Modify: `implementation/desktop/crates/selahcue-operator/dist/app.js` (`clearAll` 3519; Backspace binding 4460-4465; `#clear-all` wiring 3551)
- Modify: `implementation/desktop/crates/selahcue-operator/dist/index.html` (beside the `#clear-all` button)
- Test: `scripts/operator_headless.py` (`make operator-headless`)

**Interfaces:**
- Consumes: the Tauri command `clear_layer` and `OperatorView.cleared_layers` (Tasks 2-3).
- Produces:
  - `const clearLayer = (layer) => act(() => invoke("clear_layer", { layer }))`
  - **Backspace** calls `clearLayer("text")`, under the same editable-target guard the current binding uses
  - a `CLEAR ▾` picker beside Clear All, following `docs/design/UX-STATE-MATRIX.md:177,411` and `COMPONENT-SPECS.md:285`. It has four entries in composite order (Background, Lower third, Logo, Text). Each entry shows a cleared state from `cleared_layers`.
  - Clear All and double-Esc are unchanged

- [ ] **Step 1: Write the failing headless checks** in `scripts/operator_headless.py`, using the existing stub-backend pattern there:
  - Backspace with focus on the body records an `invoke("clear_layer", {layer:"text"})` call, not `clear`.
  - Backspace inside a focused text input records no clear command at all (Review Focus 1).
  - Each `CLEAR ▾` entry invokes `clear_layer` with its tag.
  - When the stub view returns `cleared_layers:["text"]`, the Text entry renders as cleared. Assert the computed style, not just a class (the `hidden` vs `display` trap).
- [ ] **Step 2: Run** `make operator-headless`. Expected: the new checks FAIL.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run** `make operator-headless`. Expected: all pass. Then do the WebKit layout check of the picker, following the repo's Playwright WebKit probe approach. The flex `<select>` collapse trap applies, so use buttons, not a `<select>`.
- [ ] **Step 5: Commit.** Run `git commit -m "operator: CLEAR layer picker and Backspace clears text (86ajpy59e)"`.

### Task 6: Gate, docs and handoff

**Files:**
- Modify: `docs/product/prds/SelahCue-PRD.md` (FR-078 row, 219): add a note that FR-078 is delivered for text/background/lower-third/logo, and that media clearing waits on video (DEC-003)
- Modify: `docs/design/UX-FLOWS.md` (~322-350), where the Backspace/Esc wording describes the new behaviour

- [ ] **Step 1:** In the worktree, run `make marketing-install` and `make api-install` once, then run `make ci`. Expected: ALL GREEN. Don't pipe it; read the exit code.
- [ ] **Step 2: Manual check in the real app** (`make launch`):
  1. Go live on a song with a background, then press Backspace. The lyrics disappear and the background stays.
  2. Go live on the next slide. The lyrics are back.
  3. Use the phone's "Clear text". The console picker shows Text as cleared.
  4. Blackout on and off. Text is still cleared.
- [ ] **Step 3:** Update the docs and commit. Run `git commit -m "docs: FR-078 delivered scope (86ajpy59e)"`.
- [ ] **Step 4:** Rebase on `origin/main`, push, and open a Draft PR. Put "86ajpy59e" and the manual-check results in the body. Move the ticket to review. This change touches the live render path, so it gets the full four-reviewer gate, and it is included in the W8 12-hour soak.
