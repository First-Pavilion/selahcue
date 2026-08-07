# Presentation Browse → Present → Edit Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Invert the operator's Presentation surface from editor-first to browse/present-first — Library list → slide grid → double-click go-live → arrows advance live → Edit opens the existing editor — with authored deck slides mirrored to every audience output.

**Architecture:** Three layers of one feature. (1) Render engine (`selahcue-present`): an authored deck slide becomes the single live content for ALL outputs (primary + secondary/NDI), not just primary. (2) Host (`selahcue-operator` + `selahcue-app`): an atomic advance-and-present command and a host-truth live signal the grid rings from. (3) Webview (`dist/`): a three-mode Presentation surface (library|grid|editor) reusing the existing library + editor + `deck_*` command layer.

**Tech Stack:** Rust (workspace crates + the excluded `selahcue-operator` Tauri crate), wgpu/CPU rasterizer, plain HTML/JS/CSS webview, Python headless-Chrome behavioural gate.

**Spec:** `docs/superpowers/specs/2026-08-04-presentation-browse-present-flow-design.md` (approved 2026-08-04, verified against the codebase).

## Global Constraints

- **CI gate:** run `make ci` before every push — it runs `cargo fmt --check`, `clippy -D warnings`, all test suites, the operator `cargo check`, and the headless operator webview check. CI has a `cargo fmt --check` gate.
- **No `unwrap`/`expect` in non-test code** — workspace lint `clippy::unwrap_used = warn`; `-D warnings` makes it fail CI. Tests may `#![allow(clippy::unwrap_used)]`.
- **Bounded memory:** no unbounded queues/caches/logs; any new cache/buffer gets a bounded-memory test.
- **Never-blank (NFR-024):** no live/secondary composition path may yield a blank frame for valid content.
- **Cross-GPU parity:** the wgpu compositor must match the CPU rasterizer at **SSIM ≥ 0.99** (`selahcue-gpu`).
- **Live invariant:** staging never changes Live; only an explicit go-live does. Presenting a deck slide **takes over** the single live surface (last-writer-wins with plan/scripture content).
- **Design 2.0 tokens:** in `dist/app.css` use the `--sc-*` variables ONLY (`--sc-primary`, `--sc-live`, `--sc-live-soft`, `--sc-live-border`, `--sc-inset`, `--sc-surface`, `--sc-elevated`, `--sc-border`, `--sc-primary-hover`). Never the legacy aliases `--live` (wrong red `#a3283a`), `--panel`, `--line`, `--accent`.
- **Operator crate is excluded from the workspace.** Verify it with `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` and behaviourally with `python3 scripts/operator_headless.py`.
- **Commit message trailer** (every commit): end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Work on `main` (owner-directed; no feature branch).

## File Structure

**Phase 1 — Engine**
- Modify `implementation/desktop/crates/selahcue-present/src/present.rs` — add `live_authored` to `Presenter`; retain/mirror/recompose authored live; getter `authored_live_id`.
- Modify `implementation/desktop/crates/selahcue-present/tests/test_present.rs` — authored-live tracking, secondary mirroring, never-blank, theme-survival tests.
- Modify `implementation/desktop/crates/selahcue-gpu/tests/test_parity.rs` — an authored-representative parity scene.

**Phase 2 — Host**
- Modify `implementation/desktop/crates/selahcue-operator/src/deck_workspace.rs` — `go_live_delta`; `#[cfg(test)]` clamp test.
- Modify `implementation/desktop/crates/selahcue-operator/src/main.rs` — `deck_go_live_delta` + `output_connected` commands; register both; `Backend::is_remote`.
- Modify `implementation/desktop/crates/selahcue-app/src/operator.rs` — `OperatorView.live_authored_id`.
- Modify `implementation/desktop/crates/selahcue-app/src/controller.rs` — populate `live_authored_id` from the presenter.
- Modify `implementation/desktop/crates/selahcue-app/tests/test_controller.rs` — assert the live signal.

**Phase 3 — Webview**
- Modify `implementation/desktop/crates/selahcue-operator/dist/index.html` — grid DOM; remove `#pm-lib-back`; remove `#pm-present`.
- Modify `implementation/desktop/crates/selahcue-operator/dist/app.js` — mode state, grid render/interactions/states, entry-point relocations.
- Modify `implementation/desktop/crates/selahcue-operator/dist/app.css` — grid + ring geometry + transport styles.
- Modify `scripts/operator_headless.py` — stubs for new commands/fields; grid driver checks; bump `EXPECTED_MIN_CHECKS`.

---

## Phase 1 — Render engine: authored slides on all outputs

### Task 1: Retain the authored slide as live content

**Files:**
- Modify: `implementation/desktop/crates/selahcue-present/src/present.rs`
- Test: `implementation/desktop/crates/selahcue-present/tests/test_present.rs`

**Interfaces:**
- Produces: `Presenter::authored_live_id(&self) -> Option<u64>`; new private field `live_authored: Option<AuthoredSlide>`; `present_authored` now sets it, `go_live` clears it (mutual exclusion preserved).
- Consumes: existing `AuthoredSlide` (has `id: SlideId`, `SlideId(pub u64)`), `Presenter`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_present.rs`:

```rust
#[test]
fn authored_live_is_tracked_and_cleared_by_a_later_go_live() {
    let mut p = presenter();
    assert_eq!(p.authored_live_id(), None, "nothing authored is live initially");

    let mut slide = AuthoredSlide::new(SlideId(7));
    slide.background = Some(Background::Solid(Rgba::rgb(180, 40, 90)));
    assert!(p.present_authored(&slide, &Theme::dark()));
    assert_eq!(
        p.authored_live_id(),
        Some(7),
        "presenting an authored slide records it as the live authored content"
    );

    // A later plan go-live takes over → the authored-live signal clears (mutual exclusion).
    p.stage(Slide::title("Song 2"));
    assert!(p.go_live());
    assert_eq!(
        p.authored_live_id(),
        None,
        "a plan go-live clears the authored-live signal"
    );
}
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd implementation/desktop && cargo test -p selahcue-present --test test_present authored_live_is_tracked -- --nocapture`
Expected: FAIL — `no method named authored_live_id`.

- [ ] **Step 3: Add the field + init**

In `present.rs`, add to the `Presenter` struct (after `live_slide`):

```rust
    /// The authored deck slide currently on the Live surface (Design 2.0, node 329:124), if any.
    /// Mutually exclusive with `live_slide`: `present_authored` sets this and clears `live_slide`;
    /// a plan/scripture `go_live` clears this. Retained so secondary screens / NDI can MIRROR the
    /// authored slide (see `compose_screen_live`) instead of falling back to idle black.
    live_authored: Option<AuthoredSlide>,
```

In `Presenter::new(..)`, add `live_authored: None,` to the struct literal.

- [ ] **Step 4: Set it in `present_authored`, clear it in `go_live`, add the getter**

In `present_authored` (currently sets `live_slide = None; live_theme = None;` on success), change the success block to:

```rust
        self.live_slide = None;
        self.live_theme = None;
        self.live_authored = Some(slide.clone());
        true
```

In `go_live`, after `self.live_slide = Some(slide);` add:

```rust
        self.live_authored = None;
```

Add the getter in the `impl Presenter` block:

```rust
    /// The id of the authored deck slide currently on Live, if an authored slide is presented
    /// (rather than plan/scripture content). Host-truth for the operator grid's LIVE ring.
    pub fn authored_live_id(&self) -> Option<u64> {
        self.live_authored.as_ref().map(|s| s.id.0)
    }
```

- [ ] **Step 5: Mirror the clear anywhere `live_slide` is force-cleared**

Search: `cd implementation/desktop && grep -n "live_slide = None" crates/selahcue-present/src/present.rs`
For each hit OTHER than the `present_authored` line you just edited (e.g. a `clear`/reset path), add `self.live_authored = None;` immediately after so a cleared Live never leaves a stale authored-live signal. (If the only hit is inside `present_authored`, no extra edit is needed.)

- [ ] **Step 6: Run the test to confirm it passes**

Run: `cargo test -p selahcue-present --test test_present authored_live_is_tracked -- --nocapture`
Expected: PASS. Then `cargo test -p selahcue-present` (the existing `present_authored_puts_the_slide_on_live_and_takes_over` must still pass).

- [ ] **Step 7: Commit**

```bash
git add implementation/desktop/crates/selahcue-present/src/present.rs implementation/desktop/crates/selahcue-present/tests/test_present.rs
git commit -m "feat(present): retain authored slide as live content (mutual-exclusion + signal)"
```

---

### Task 2: Mirror the authored live slide to secondary screens

**Files:**
- Modify: `implementation/desktop/crates/selahcue-present/src/present.rs` (`compose_screen_live`)
- Test: `implementation/desktop/crates/selahcue-present/tests/test_present.rs`

**Interfaces:**
- Consumes: `Presenter::live_authored` (Task 1), `compose_authored_slide` (already imported at the top of `present.rs`).
- Produces: `compose_screen_live` returns the authored composition (not black) whenever an authored slide is live.

- [ ] **Step 1: Write the failing test**

```rust
#[test]
fn secondary_screens_mirror_a_presented_authored_slide() {
    let mut p = Presenter::new(320, 180, Theme::classic());
    let mut slide = AuthoredSlide::new(SlideId(3));
    let bg = Rgba::rgb(180, 40, 90);
    slide.background = Some(Background::Solid(bg));
    assert!(p.present_authored(&slide, &Theme::dark()));

    // A secondary screen mirrors the SAME authored slide — not idle black.
    let secondary = p.compose_screen_live(Some(&Theme::lower_third()), LayerMask::ALL);
    assert!(
        !is_black(&secondary),
        "a secondary screen mirrors the presented authored slide (not idle black)"
    );
    assert_eq!(
        secondary.pixel(160, 90).unwrap(),
        bg,
        "the secondary screen shows the authored slide's own background"
    );
    // compose_screen_live(None) still equals the physical main output.
    assert_eq!(
        p.compose_screen_live(None, LayerMask::ALL).bytes(),
        p.live_output().bytes(),
        "compose_screen_live(None) mirrors the physical main output for an authored slide too"
    );
}

#[test]
fn an_authored_slide_with_no_elements_mirrors_a_nonblank_background() {
    let mut p = Presenter::new(320, 180, Theme::classic());
    let mut slide = AuthoredSlide::new(SlideId(4));
    slide.background = Some(Background::Solid(Rgba::rgb(10, 90, 200)));
    assert!(p.present_authored(&slide, &Theme::dark()));
    // Never-blank (NFR-024): zero elements still mirrors the background, never black.
    assert!(!is_black(&p.compose_screen_live(Some(&Theme::classic()), LayerMask::ALL)));
}
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cargo test -p selahcue-present --test test_present secondary_screens_mirror -- --nocapture`
Expected: FAIL — the secondary is black (`compose_screen_live` still keys off `live_slide`, which is now `None`).

- [ ] **Step 3: Add the authored branch to `compose_screen_live`**

In `present.rs`, at the top of `compose_screen_live` (before the `let Some(slide) = self.live_slide.as_ref() else { ... }` line), insert:

```rust
        // An authored deck slide takes over Live and mirrors to EVERY screen (Design 2.0). Its own
        // background overrides the theme; `screen_theme`/global is only the fallback. Layer masks do
        // not apply — an authored slide's elements ARE the content, not theme-layer categories.
        if let Some(slide) = self.live_authored.as_ref() {
            let theme = screen_theme.or(self.live_theme.as_ref()).unwrap_or(&self.theme);
            return raster::render(&compose_authored_slide(slide, theme, self.width, self.height));
        }
```

Update the doc comment on `compose_screen_live` to note it mirrors an authored live slide (mask ignored for authored content).

- [ ] **Step 4: Run to confirm pass**

Run: `cargo test -p selahcue-present --test test_present secondary_screens_mirror an_authored_slide_with_no_elements -- --nocapture`
Expected: PASS. Then run the whole file: `cargo test -p selahcue-present` (the existing `a_blank_live_composes_a_safe_black_secondary_screen` and `secondary_screens_render_the_same_live_content...` must still pass — nothing authored is live in those).

- [ ] **Step 5: Commit**

```bash
git add implementation/desktop/crates/selahcue-present/src/present.rs implementation/desktop/crates/selahcue-present/tests/test_present.rs
git commit -m "feat(present): mirror the presented authored slide to secondary screens / NDI"
```

---

### Task 3: Keep authored live through theme/layer switches + GPU parity

**Files:**
- Modify: `implementation/desktop/crates/selahcue-present/src/present.rs` (`set_theme`, `set_main_screen_theme`, `set_main_layer_mask`)
- Modify: `implementation/desktop/crates/selahcue-gpu/tests/test_parity.rs`
- Test: `implementation/desktop/crates/selahcue-present/tests/test_present.rs`

**Interfaces:**
- Consumes: `Presenter::live_authored`, `compose_authored_slide`, `EngineCommand::SetScene`.

- [ ] **Step 1: Write the failing test (present)**

```rust
#[test]
fn a_theme_switch_keeps_a_live_authored_slide_on_air() {
    let mut p = Presenter::new(320, 180, Theme::classic());
    let mut slide = AuthoredSlide::new(SlideId(9));
    let bg = Rgba::rgb(200, 30, 60);
    slide.background = Some(Background::Solid(bg));
    assert!(p.present_authored(&slide, &Theme::dark()));

    // A global theme switch must NOT lose the authored slide (its own bg wins; it stays on air).
    p.set_theme(Theme::high_contrast());
    assert_eq!(p.authored_live_id(), Some(9), "authored slide survives a global theme switch");
    assert_eq!(
        p.live_output().pixel(160, 90).unwrap(),
        bg,
        "the authored slide's own background is still on the main output after a theme switch"
    );
    // And a per-screen theme change likewise keeps it.
    p.set_main_screen_theme(Some(Theme::lower_third()));
    assert_eq!(p.live_output().pixel(160, 90).unwrap(), bg);
}
```

- [ ] **Step 2: Run to confirm it fails**

Run: `cargo test -p selahcue-present --test test_present a_theme_switch_keeps_a_live_authored -- --nocapture`
Expected: FAIL — after `set_theme`, the main live surface is recomposed only from `live_slide` (now `None`), so the authored pixels are lost / overwritten.

- [ ] **Step 3: Recompose authored live in the three setters**

In `present.rs`, in EACH of `set_theme`, `set_main_screen_theme`, and `set_main_layer_mask`, after the existing `if let Some(slide) = self.live_slide.clone() { ... }` block, add:

```rust
        if let Some(slide) = self.live_authored.clone() {
            // Authored slide: its own background wins; the effective theme is only the fallback.
            // Layer masks don't apply to authored content, so recompose without a mask.
            let theme = self.effective(self.live_theme.as_ref()).clone();
            let frame = compose_authored_slide(&slide, &theme, self.width, self.height);
            self.live.apply(EngineCommand::SetScene { frame });
        }
```

(`live_slide` and `live_authored` are mutually exclusive, so at most one branch fires.)

- [ ] **Step 4: Run to confirm pass**

Run: `cargo test -p selahcue-present --test test_present a_theme_switch_keeps_a_live_authored -- --nocapture` → PASS.
Then `cargo test -p selahcue-present` — full suite green.

- [ ] **Step 5: Add the authored-representative GPU parity scene**

In `selahcue-gpu/tests/test_parity.rs`, inside `scenes()`, before the final `vec![...]`, add:

```rust
    // An authored-slide-like frame (Design 2.0 deck slide): a solid background with z-ordered
    // element FILLS — the exact Frame shape `compose_authored_slide` produces — so the authored
    // present path is under the SSIM parity oracle just like plan/scripture content.
    let mut authored = Frame::new(320, 180).with_background(Rgba::rgb(180, 40, 90));
    authored.push(Layer::Fill {
        rect: Rect::new(40, 30, 240, 40),
        color: Rgba::rgb(240, 240, 245),
    });
    authored.push(Layer::Fill {
        rect: Rect::new(40, 90, 180, 60),
        color: Rgba::new(124, 92, 255, 200),
    });
```

and add `authored` to the returned `vec![...]`.

- [ ] **Step 6: Run the parity + engine suites**

Run: `cargo test -p selahcue-gpu` (SSIM ≥ 0.99; skips gracefully with no GPU — that is fine locally) and `cargo test -p selahcue-present`.
Expected: PASS (or a printed GPU-absent SKIP for the parity test).

- [ ] **Step 7: Commit**

```bash
git add implementation/desktop/crates/selahcue-present/src/present.rs implementation/desktop/crates/selahcue-present/tests/test_present.rs implementation/desktop/crates/selahcue-gpu/tests/test_parity.rs
git commit -m "feat(present): recompose authored live on theme/layer switch + GPU parity scene"
```

---

## Phase 2 — Host: atomic advance-and-present + host-truth live signal

### Task 4: `DeckWorkspace::go_live_delta` (clamped pointer math)

**Files:**
- Modify: `implementation/desktop/crates/selahcue-operator/src/deck_workspace.rs`

**Interfaces:**
- Produces: `DeckWorkspace::go_live_delta(&mut self, delta: i32) -> bool` — advances the live pointer by `delta`, clamped to `[0, len-1]`, sets `selected` + `live`, returns whether a slide is now live.
- Consumes: `self.deck.index_of(SlideId) -> Option<usize>`, `self.deck.get_index(usize) -> Option<&AuthoredSlide>`, `self.deck.len()`, `self.effective_selected()`.

- [ ] **Step 1: Write the failing unit test**

At the bottom of `deck_workspace.rs`, add (or extend an existing) `#[cfg(test)]` module:

```rust
#[cfg(test)]
mod go_live_delta_tests {
    use super::*;

    fn ws_with(n: usize) -> DeckWorkspace {
        let mut ws = DeckWorkspace::new();
        for _ in 0..n {
            ws.add_slide();
        }
        ws
    }

    #[test]
    fn go_live_delta_steps_and_clamps_at_both_ends() {
        let mut ws = ws_with(3);
        // Start live on the first slide.
        let first = ws.view()["slides"][0]["id"].as_u64().unwrap();
        ws.select_slide(first);
        ws.go_live();
        assert_eq!(ws.view()["live"].as_u64(), Some(first));

        // +1 → slide 2, +1 → slide 3, +1 → clamped at slide 3.
        assert!(ws.go_live_delta(1));
        assert!(ws.go_live_delta(1));
        let last = ws.view()["slides"][2]["id"].as_u64().unwrap();
        assert_eq!(ws.view()["live"].as_u64(), Some(last));
        assert!(ws.go_live_delta(1));
        assert_eq!(ws.view()["live"].as_u64(), Some(last), "clamped at the last slide");

        // Back to the first, clamped at 0.
        assert!(ws.go_live_delta(-1));
        assert!(ws.go_live_delta(-1));
        assert!(ws.go_live_delta(-1));
        assert_eq!(ws.view()["live"].as_u64(), Some(first), "clamped at the first slide");
    }

    #[test]
    fn go_live_delta_on_an_empty_deck_is_a_noop() {
        let mut ws = DeckWorkspace::new();
        assert!(!ws.go_live_delta(1));
    }
}
```

(If `DeckWorkspace::new()` / `add_slide()` differ in name, use the crate's real constructor — grep `impl DeckWorkspace` — the command layer calls `ws.add_slide()` via `deck_add_slide`, so `add_slide` exists.)

- [ ] **Step 2: Run to confirm it fails**

Run: `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml go_live_delta`
Expected: FAIL — `no method named go_live_delta`.

- [ ] **Step 3: Implement `go_live_delta`**

In `deck_workspace.rs`, next to `go_live` (~line 643):

```rust
    /// Advance the LIVE slide pointer by `delta` (−1 previous / +1 next), clamped to the deck ends,
    /// then select AND mark it live. Steps from the current live slide (or the selected slide when
    /// nothing is live). Returns whether a slide is now live (`false` only on an empty deck).
    /// Navigation of what is on air — the grid transport (◀ ▶ / arrow keys while presenting).
    pub fn go_live_delta(&mut self, delta: i32) -> bool {
        let Some(base) = self.live.or_else(|| self.effective_selected()) else {
            return false;
        };
        let Some(idx) = self.deck.index_of(base) else {
            return false;
        };
        let last = self.deck.len().saturating_sub(1) as i64;
        let next = (idx as i64 + delta as i64).clamp(0, last) as usize;
        let Some(slide) = self.deck.get_index(next) else {
            return false;
        };
        let sid = slide.id;
        self.selected = Some(sid);
        self.selected_element = None;
        self.live = Some(sid);
        true
    }
```

- [ ] **Step 4: Run to confirm pass**

Run: `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml go_live_delta`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/src/deck_workspace.rs
git commit -m "feat(operator): DeckWorkspace::go_live_delta — clamped advance-and-present pointer"
```

---

### Task 5: `deck_go_live_delta` Tauri command

**Files:**
- Modify: `implementation/desktop/crates/selahcue-operator/src/main.rs`

**Interfaces:**
- Produces: Tauri command `deck_go_live_delta(delta: i32)` (JS: `invoke("deck_go_live_delta", { delta })`), returning the `DeckView` JSON; routes the composed slide to the audience output via `backend.present_authored_slide`.
- Consumes: `DeckWorkspace::go_live_delta` (Task 4); the existing `present_payload` / `backend.present_authored_slide` route.

- [ ] **Step 1: Add the command**

In `main.rs`, next to `deck_go_live` (~line 1149), add:

```rust
/// Advance the LIVE deck slide by `delta` (−1 previous / +1 next), clamped to the deck ends, and
/// present it to the audience output — atomically, under a single deck-lock acquisition (no
/// select-then-present race). Drives the presentation grid's ◀ ▶ transport and live-mode arrows.
#[tauri::command]
async fn deck_go_live_delta(
    delta: i32,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let (view, payload) = {
        let mut ws = state.deck.lock().map_err(|e| format!("deck lock: {e}"))?;
        ws.go_live_delta(delta);
        if let Ok(mut lib) = state.library.lock() {
            lib.store(ws.open_deck());
        }
        (ws.view(), ws.present_payload())
    };
    if let Some((slide_json, theme_json)) = payload {
        state
            .backend
            .present_authored_slide(slide_json, theme_json)
            .await?;
    }
    Ok(view)
}
```

- [ ] **Step 2: Register it in the invoke handler**

In `main.rs`, in the `tauri::generate_handler![ ... ]` list (~line 1640) add `deck_go_live_delta,` immediately after `deck_go_live,`.

- [ ] **Step 3: Compile-check the operator crate**

Run: `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml`
Expected: PASS (no errors/warnings).

- [ ] **Step 4: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/src/main.rs
git commit -m "feat(operator): deck_go_live_delta command — atomic advance+present"
```

---

### Task 6: Host-truth live signal + output-connected

**Files:**
- Modify: `implementation/desktop/crates/selahcue-app/src/operator.rs`
- Modify: `implementation/desktop/crates/selahcue-app/src/controller.rs`
- Modify: `implementation/desktop/crates/selahcue-app/tests/test_controller.rs`
- Modify: `implementation/desktop/crates/selahcue-operator/src/main.rs`

**Interfaces:**
- Produces: `OperatorView.live_authored_id: Option<u64>` (host truth for the grid LIVE ring); Tauri command `output_connected() -> bool` (JS: `invoke("output_connected")`); `Backend::is_remote(&self) -> bool`.
- Consumes: `Presenter::authored_live_id` (Task 1); existing `OperatorView.blackout`.

- [ ] **Step 1: Write the failing controller test**

In `test_controller.rs`, add (adapt the controller constructor + command-apply helper to the file's existing style — grep the file for how other tests build a `LiveController` and apply a `Command`):

```rust
#[test]
fn operator_view_reports_the_live_authored_slide_id() {
    let mut c = test_controller(); // the file's existing helper
    assert_eq!(c.operator_view().live_authored_id, None);

    let slide = selahcue_present::deck::AuthoredSlide::new(selahcue_present::deck::SlideId(11));
    let slide_json = serde_json::to_string(&slide).unwrap();
    let theme_json = serde_json::to_string(&selahcue_present::theme::Theme::dark()).unwrap();
    c.apply(Command::PresentAuthoredSlide { slide_json, theme_json });

    assert_eq!(
        c.operator_view().live_authored_id,
        Some(11),
        "presenting an authored slide surfaces its id as host-truth for the grid ring"
    );
}
```

- [ ] **Step 2: Run to confirm it fails**

Run: `cargo test -p selahcue-app --test test_controller operator_view_reports_the_live_authored`
Expected: FAIL — `no field live_authored_id on OperatorView`.

- [ ] **Step 3: Add the field to `OperatorView`**

In `operator.rs`, add to the `OperatorView` struct (near `live_scripture`/`live_free_text`):

```rust
    /// The id of the authored deck slide currently on Live (Design 2.0), if an authored slide is
    /// presented rather than plan/scripture content. Host-truth for the presentation grid's LIVE
    /// ring — the deck editor's local `live` annotation can go stale when the console drives plan
    /// content, so the grid rings THIS instead.
    pub live_authored_id: Option<u64>,
```

- [ ] **Step 4: Populate it in `operator_view()`**

In `controller.rs`, in the `OperatorView { ... }` literal returned by `operator_view()` (~line 1697), add:

```rust
            live_authored_id: self.presenter.authored_live_id(),
```

- [ ] **Step 5: Run to confirm the controller test passes**

Run: `cargo test -p selahcue-app --test test_controller operator_view_reports_the_live_authored`
Expected: PASS. Then `cargo test -p selahcue-app` (fixture builders that construct `OperatorView` literals elsewhere may need the new field — add `live_authored_id: None,` to any that fail to compile).

- [ ] **Step 6: Add `Backend::is_remote` + the `output_connected` command**

In `main.rs`, on the `Backend` enum's `impl` block, add:

```rust
    /// Whether a REAL audience output window is connected (a Remote backend), as opposed to the
    /// stand-alone/demo local backend where a present succeeds silently with no physical output.
    pub fn is_remote(&self) -> bool {
        matches!(self, Backend::Remote(_))
    }
```

(Confirm the remote variant name by reading the `enum Backend` definition ~line 46; use whatever it is.)

Add the command:

```rust
/// Whether a real audience output window is connected. The presentation grid uses this to be
/// HONEST: with no output it shows "Preview only — no audience output" instead of a true LIVE ring.
#[tauri::command]
async fn output_connected(state: State<'_, AppState>) -> Result<bool, String> {
    Ok(state.backend.is_remote())
}
```

Register `output_connected,` in the `generate_handler!` list.

- [ ] **Step 7: Compile-check + commit**

Run: `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` and `cargo test -p selahcue-app`.
Expected: PASS.

```bash
git add implementation/desktop/crates/selahcue-app/src/operator.rs implementation/desktop/crates/selahcue-app/src/controller.rs implementation/desktop/crates/selahcue-app/tests/test_controller.rs implementation/desktop/crates/selahcue-operator/src/main.rs
git commit -m "feat(host): expose live_authored_id + output_connected for the presentation grid"
```

---

## Phase 3 — Webview: browse → present → edit

> Verification for webview tasks uses the committed headless gate `scripts/operator_headless.py` (real layout/CSS/canvas under headless Chrome). Each webview task adds driver checks (`ok(cond, "msg")`) and STUB updates, and bumps `EXPECTED_MIN_CHECKS` by the number of checks added. Run: `python3 scripts/operator_headless.py`. Also run `cargo check --manifest-path .../selahcue-operator/Cargo.toml` when touching Rust, and do the MANUAL step (`make operator`) noted per task.

### Task 7: Three-mode state; land on Library; open a card → grid

**Files:**
- Modify: `dist/app.js` (mode state, `pmActivate`, `pmLibOpen`), `dist/index.html` (remove `#pm-lib-back`), `scripts/operator_headless.py`

**Interfaces:**
- Produces: `let pmMode` + `function pmSetMode(mode)` where `mode ∈ {"library","grid","editor"}`; `pmActivate` lands on `"library"`; `pmLibOpen` lands on `"grid"`.

- [ ] **Step 1: Add a failing headless check**

In `operator_headless.py`'s DRIVER (append a Presentation-flow block after an existing surface block), add:

```javascript
      // === Presentation flow: nav lands on the LIBRARY, not the editor ===
      document.querySelector('.nav-item[data-surface="presentation"]').click();
      await sleep(40);
      ok(!el("pm-library").hidden, "presentation nav lands on the Library (not the editor)");
      ok(getComputedStyle(el("pm-library")).display !== "none", "Library is actually visible (computed display)");
      ok(!document.getElementById("pm-lib-back"), "the 'Back to editor' link is removed");
```

Bump `EXPECTED_MIN_CHECKS` by `3`.

- [ ] **Step 2: Run to confirm it fails**

Run: `python3 scripts/operator_headless.py`
Expected: FAIL (Library hidden — `pmActivate` currently opens the editor; `pm-lib-back` still present).

- [ ] **Step 3: Add the mode state + setter**

In `app.js`, near the other `pm*` state (~line 4093), add:

```javascript
      let pmMode = "library"; // "library" | "grid" | "editor"
      function pmSetMode(mode) {
        pmMode = mode;
        const lib = pmEl("pm-library"), grid = pmEl("pm-grid"), body = pmLibBody();
        if (lib) lib.hidden = mode !== "library";
        if (grid) grid.hidden = mode !== "grid";
        if (body) body.style.display = mode === "editor" ? "" : "none";
      }
```

(`pm-grid` is created in Task 8; guarding with `if (grid)` keeps this task self-contained.)

- [ ] **Step 4: Land on Library; open a card → grid**

Change `pmActivate` (~4295) to:

```javascript
      function pmActivate() {
        pmSetMode("library");
        pmLibLoad();
        pmLoadFonts();
      }
```

Change the tail of `pmLibOpen` (~4458) so, on success, it enters grid mode instead of the editor:

```javascript
      async function pmLibOpen(id) {
        try {
          const dv = await invoke("deck_open", { id });
          pmDv = dv;
          pmSetMode("grid");
          pmRenderGrid(dv); // defined in Task 8
        } catch (e) {
          console.error(e);
          pmShowError("open the presentation");
        }
      }
```

- [ ] **Step 5: Remove the Back-to-editor link**

In `index.html`, delete the `#pm-lib-back` button (line ~686). In `app.js`, delete its wiring (`pmEl("pm-lib-back").onclick = pmHideLibrary;`, ~line 5165).

- [ ] **Step 6: Run to confirm pass (with a temporary grid stub)**

`pmRenderGrid` doesn't exist yet; add a one-line stub at the end of the pm section so this task runs green in isolation: `function pmRenderGrid(dv) {}` (replaced in Task 8).
Run: `python3 scripts/operator_headless.py` → the three new checks PASS.

- [ ] **Step 7: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/dist/app.js implementation/desktop/crates/selahcue-operator/dist/index.html scripts/operator_headless.py
git commit -m "feat(operator): presentation surface lands on the Library; open a card enters grid mode"
```

---

### Task 8: Grid DOM, styles, and lazy bounded-cache thumbnails

**Files:**
- Modify: `dist/index.html` (grid DOM), `dist/app.css` (grid styles), `dist/app.js` (`pmRenderGrid`, thumbnail cache), `scripts/operator_headless.py`

**Interfaces:**
- Produces: `#pm-grid` section (top bar `‹ Presentations` / deck name / `Edit ▸`; `#pm-grid-tiles`; transport `#pm-transport`); `function pmRenderGrid(dv)`; `function pmThumb(slideId, imgEl)` (lazy render via `render_deck_slide`); a bounded `pmThumbCache` (Map, capped).

- [ ] **Step 1: Add the grid DOM**

In `index.html`, inside `#surface-presentation`, after the `#pm-library` block and before `.pm-body`, add:

```html
      <!-- SLIDE GRID (Design 2.0 browse/present mode). Thumbnails are natively composited via
           render_deck_slide; double-click presents live; the transport advances live. -->
      <section id="pm-grid" class="pm-grid" hidden aria-label="Slides">
        <div class="pm-grid-top">
          <button id="pm-grid-back" class="pm-lib-back" type="button">‹ Presentations</button>
          <span class="pm-grid-title"><span id="pm-grid-name">Presentation</span>
            <span id="pm-grid-count" class="pm-plan-count">· — slides</span></span>
          <span class="pm-grid-spacer"></span>
          <span id="pm-grid-badge" class="pm-grid-badge" hidden></span>
          <button id="pm-grid-edit" class="pm-btn-primary" type="button">Edit ▸</button>
        </div>
        <div id="pm-grid-tiles" class="pm-grid-tiles" role="grid" aria-label="Slides"
          aria-describedby="pm-grid-hint"></div>
        <p id="pm-grid-hint" class="pm-grid-hint">Double-click a slide to present it live.</p>
        <div id="pm-grid-empty" class="pm-lib-empty" hidden>
          <div class="pm-lib-empty-title">This presentation has no slides yet</div>
          <button id="pm-grid-empty-edit" class="pm-btn-primary" type="button">Edit ▸ to add slides</button>
        </div>
        <div id="pm-transport" class="pm-transport" role="group" aria-label="Live transport" hidden>
          <button id="pm-prev" class="pm-tp-btn" type="button" aria-label="Previous slide">◀ Previous</button>
          <span id="pm-tp-live" class="pm-tp-live" aria-live="polite">● LIVE — slide — / —</span>
          <button id="pm-next" class="pm-tp-btn" type="button" aria-label="Next slide">Next ▶</button>
        </div>
      </section>
```

- [ ] **Step 2: Add grid styles (with the ring geometry)**

In `app.css`, add (uses `--sc-*` only):

```css
.pm-grid { display: flex; flex-direction: column; gap: 14px; padding: 16px; height: 100%; }
.pm-grid-top { display: flex; align-items: center; gap: 12px; }
.pm-grid-spacer { flex: 1; }
.pm-grid-tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px; overflow-y: auto; align-content: start; }
.pm-tile { position: relative; aspect-ratio: 16/9; background: var(--sc-inset); border-radius: 14px;
  overflow: hidden; cursor: pointer; border: 2px solid transparent; }
.pm-tile img, .pm-tile canvas { width: 100%; height: 100%; display: block; }
.pm-tile .pm-tile-n { position: absolute; left: 8px; top: 6px; font: 600 11px/1 Inter, sans-serif;
  color: var(--sc-text-2); }
/* Selection cursor — INSET ring (safe; never on air). */
.pm-tile.sel { box-shadow: inset 0 0 0 2px var(--sc-primary); }
/* Keyboard focus — OUTSET offset ring, distinct GEOMETRY from selection even at the same hue. */
.pm-tile:focus-visible { outline: 2px solid var(--sc-primary-hover); outline-offset: 2px; }
/* LIVE — red border + glow + the "● LIVE" text label (driven by host truth). */
.pm-tile.live { border-color: var(--sc-live-border); box-shadow: 0 0 0 2px var(--sc-live),
  0 0 14px var(--sc-live-soft); }
.pm-tile .pm-tile-live { position: absolute; right: 8px; top: 6px; padding: 2px 6px; border-radius: 999px;
  background: var(--sc-live-soft); border: 1px solid var(--sc-live-border); color: var(--sc-live);
  font: 700 10px/1 Inter, sans-serif; }
.pm-tile-fail { display: grid; place-items: center; color: var(--sc-text-3); font-size: 12px; }
.pm-transport { display: flex; align-items: center; justify-content: center; gap: 16px;
  padding: 10px; background: var(--sc-elevated); border: 1px solid var(--sc-border); border-radius: 12px; }
.pm-tp-live { color: var(--sc-live); font: 700 13px/1 Inter, sans-serif; }
.pm-tp-btn[aria-disabled="true"] { opacity: .4; pointer-events: none; }
.pm-grid-badge { padding: 3px 8px; border-radius: 999px; background: var(--sc-warn-soft);
  border: 1px solid var(--sc-warn-border); color: var(--sc-warn); font: 600 11px/1 Inter, sans-serif; }
```

(If `--sc-text-2`/`--sc-text-3`/`--sc-warn*` names differ, grep `:root` in `app.css` for the exact tokens; the migration table in the spec lists them.)

- [ ] **Step 3: Add a failing headless check**

STUB: extend the `render_deck_slide` stub already present (line ~230) — it already returns a 2×1 frame, good. In the DRIVER, after opening a deck (add to the Task-7 block):

```javascript
      el("pm-lib-grid").querySelector(".pm-lib-open").click(); // open the first presentation card
      await sleep(40);
      ok(!el("pm-grid").hidden, "opening a presentation shows the slide GRID");
      ok(el("pm-grid-tiles").querySelectorAll(".pm-tile").length >= 1, "the grid renders one tile per slide");
      ok(window.__calls.some(function(c){return c.cmd==="render_deck_slide";}), "thumbnails compose via render_deck_slide");
```

Bump `EXPECTED_MIN_CHECKS` by `3`.

- [ ] **Step 4: Run to confirm it fails**

Run: `python3 scripts/operator_headless.py`
Expected: FAIL — no `.pm-tile` (grid not rendered; `pmRenderGrid` is the stub).

- [ ] **Step 5: Implement `pmRenderGrid` + bounded thumbnail cache**

Replace the Task-7 stub with:

```javascript
      const PM_THUMB_CACHE_MAX = 60; // bounded — never grows without limit (repo rule)
      const pmThumbCache = new Map(); // slideId -> dataURL
      function pmThumbCachePut(id, url) {
        pmThumbCache.set(id, url);
        while (pmThumbCache.size > PM_THUMB_CACHE_MAX) {
          pmThumbCache.delete(pmThumbCache.keys().next().value); // evict oldest (insertion order)
        }
      }
      async function pmThumb(id, canvas) {
        if (pmThumbCache.has(id)) { blitDataUrl(canvas, pmThumbCache.get(id)); return; }
        try {
          const r = await invoke("render_deck_slide", { id, maxW: 320, maxH: 180 });
          if (r && r.frame) { const url = blitFrame(canvas, r.frame); if (url) pmThumbCachePut(id, url); }
        } catch (e) { canvas.parentElement.classList.add("pm-tile-fail"); canvas.parentElement.textContent = "⚠ Can't preview"; }
      }
      function pmRenderGrid(dv) {
        pmEl("pm-grid-name").textContent = dv.name || "Presentation";
        pmEl("pm-grid-count").textContent = "· " + (dv.count || 0) + " slides";
        const tiles = pmEl("pm-grid-tiles"); tiles.innerHTML = "";
        const empty = !dv.slides || dv.slides.length === 0;
        pmEl("pm-grid-empty").hidden = !empty;
        tiles.hidden = empty;
        const io = new IntersectionObserver((entries) => {
          entries.forEach((en) => {
            if (en.isIntersecting) { const t = en.target; io.unobserve(t); pmThumb(Number(t.dataset.id), t.querySelector("canvas")); }
          });
        });
        (dv.slides || []).forEach((s, i) => {
          const tile = document.createElement("div");
          tile.className = "pm-tile"; tile.dataset.id = String(s.id);
          tile.setAttribute("role", "gridcell"); tile.tabIndex = i === 0 ? 0 : -1;
          tile.setAttribute("aria-label", "Slide " + (i + 1) + (s.lines && s.lines[0] ? ": " + s.lines[0] : ""));
          const cv = document.createElement("canvas"); cv.width = 320; cv.height = 180; tile.appendChild(cv);
          const n = document.createElement("span"); n.className = "pm-tile-n"; n.textContent = String(i + 1); tile.appendChild(n);
          tiles.appendChild(tile); io.observe(tile);
        });
        pmGridWire(tiles);   // interactions — Task 9
        pmGridSyncLive();    // host-truth ring + transport — Task 9
      }
```

Add small helpers if not present: `blitDataUrl(canvas, url)` (draw a cached data URL) and make `blitFrame` return `canvas.toDataURL()` after drawing (check `blitFrame` at ~line 314 — if it returns nothing, add `return canvas.toDataURL();` at its end). Add temporary no-op `function pmGridWire(){}` and `function pmGridSyncLive(){}` (implemented in Task 9) so this task is green in isolation.

Wire the back/edit buttons:

```javascript
      pmEl("pm-grid-back").onclick = () => { pmSetMode("library"); pmLibLoad(); };
      pmEl("pm-grid-edit").onclick = () => { pmSetMode("editor"); renderPresentation(pmDv); };
      pmEl("pm-grid-empty-edit").onclick = () => { pmSetMode("editor"); renderPresentation(pmDv); };
```

- [ ] **Step 6: Run to confirm pass**

Run: `python3 scripts/operator_headless.py` → the three new checks PASS.

- [ ] **Step 7: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/dist/ scripts/operator_headless.py
git commit -m "feat(operator): slide grid — lazy bounded-cache thumbnails, top bar, transport shell"
```

---

### Task 9: Grid interactions — select, go-live, transport, arrows, host-truth ring

**Files:**
- Modify: `dist/app.js` (`pmGridWire`, `pmGridSyncLive`, key handling), `scripts/operator_headless.py`

**Interfaces:**
- Consumes: `deck_go_live`, `deck_go_live_delta` (Task 5), `deck_select_slide`, host `view().live_authored_id` (Task 6), `output_connected` (Task 6 — used in Task 10).
- Produces: `pmGridWire(tiles)`, `pmGridSyncLive()`, `pmGridLiveId` (host-truth live slide id), `pmGridCursor` (selected id).

- [ ] **Step 1: Add failing headless checks**

STUBs: add to the `invoke` switch in `operator_headless.py`:

```javascript
    if (cmd === "deck_go_live_delta") {
      var ids = D.slides.map(function(s){return s.id;});
      var cur = (V.live_authored_id!=null) ? ids.indexOf(V.live_authored_id) : ids.indexOf(D.selected);
      var nx = Math.max(0, Math.min(ids.length-1, (cur<0?0:cur) + args.delta));
      D.selected = ids[nx]; D.live = ids[nx]; V.live_authored_id = ids[nx];
      return Promise.resolve(dClone());
    }
    if (cmd === "output_connected") return Promise.resolve(window.__outputConnected !== false);
```

Also add `live_authored_id:null` to the `V` OperatorView literal, and make the `deck_go_live` stub set it: in the existing `deck_go_live` stub change to `D.live = D.selected; V.live_authored_id = D.selected; return Promise.resolve(dClone());`.

DRIVER (after the grid renders):

```javascript
      var tile1 = el("pm-grid-tiles").querySelector('.pm-tile');
      tile1.dispatchEvent(new MouseEvent("click", {bubbles:true}));
      ok(tile1.classList.contains("sel"), "single-click selects a slide (safe cursor ring)");
      ok(!tile1.classList.contains("live"), "single-click does NOT go live");
      tile1.dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await sleep(30);
      ok(window.__calls.some(function(c){return c.cmd==="deck_go_live";}), "double-click presents the slide live");
      ok(el("pm-grid-tiles").querySelector('.pm-tile.live'), "the live slide shows the red LIVE ring");
      ok(!el("pm-transport").hidden, "the transport bar shows once a slide is live");
      el("pm-next").click(); await sleep(30);
      ok(window.__calls.some(function(c){return c.cmd==="deck_go_live_delta" && c.args.delta===1;}), "Next ▶ advances live via deck_go_live_delta(+1)");
```

Bump `EXPECTED_MIN_CHECKS` by `6`.

- [ ] **Step 2: Run to confirm it fails**

Run: `python3 scripts/operator_headless.py` → FAIL (no selection/live behaviour; `pmGridWire` is a no-op).

- [ ] **Step 3: Implement interactions**

Replace the no-op stubs:

```javascript
      let pmGridCursor = null; // selected slide id (safe)
      let pmGridLiveId = null; // HOST-truth live authored slide id

      function pmGridTiles() { return Array.from(pmEl("pm-grid-tiles").querySelectorAll(".pm-tile")); }
      function pmGridSelect(id, focus) {
        pmGridCursor = id;
        pmGridTiles().forEach((t) => {
          const on = Number(t.dataset.id) === id;
          t.classList.toggle("sel", on);
          t.tabIndex = on ? 0 : -1;
          if (on && focus) t.focus();
        });
      }
      async function pmGridGoLive(id) {
        if (id != null && id !== pmGridCursor) { await pAct(() => invoke("deck_select_slide", { id }), "select the slide"); }
        // Success is decided by host truth on the next sync — do NOT paint the ring optimistically.
        await pmPresentGuarded(() => invoke("deck_go_live"));
      }
      async function pmGridDelta(delta) { await pmPresentGuarded(() => invoke("deck_go_live_delta", { delta })); }

      function pmGridWire(tiles) {
        tiles.querySelectorAll(".pm-tile").forEach((t) => {
          const id = Number(t.dataset.id);
          t.onclick = () => pmGridSelect(id, false);
          t.ondblclick = () => pmGridGoLive(id);
        });
        tiles.onkeydown = (e) => {
          const ids = pmGridTiles().map((t) => Number(t.dataset.id));
          const i = ids.indexOf(pmGridCursor == null ? ids[0] : pmGridCursor);
          if (e.key === "Enter") { e.preventDefault(); pmGridGoLive(pmGridCursor); return; }
          const live = pmGridLiveId != null;
          if (["ArrowRight", "ArrowDown", " "].includes(e.key)) {
            e.preventDefault();
            if (live) pmGridDelta(1); else pmGridSelect(ids[Math.min(ids.length - 1, i + 1)], true);
          } else if (["ArrowLeft", "ArrowUp"].includes(e.key)) {
            e.preventDefault();
            if (live) pmGridDelta(-1); else pmGridSelect(ids[Math.max(0, i - 1)], true);
          }
        };
      }
```

Add the host-truth sync (rings from `view().live_authored_id`, not `dv.live`):

```javascript
      async function pmGridSyncLive() {
        let liveId = null;
        try { const v = await invoke("view"); liveId = (v && v.live_authored_id != null) ? v.live_authored_id : null; }
        catch (e) { /* keep last-known; the conn pill already reflects a dropped host */ }
        pmGridLiveId = liveId;
        const tiles = pmGridTiles();
        tiles.forEach((t) => {
          const on = Number(t.dataset.id) === liveId;
          t.classList.toggle("live", on);
          let lbl = t.querySelector(".pm-tile-live");
          if (on && !lbl) { lbl = document.createElement("span"); lbl.className = "pm-tile-live"; lbl.textContent = "● LIVE"; t.appendChild(lbl); }
          if (!on && lbl) lbl.remove();
        });
        const tp = pmEl("pm-transport"); tp.hidden = liveId == null;
        if (liveId != null) {
          const ids = tiles.map((t) => Number(t.dataset.id)); const idx = ids.indexOf(liveId);
          pmEl("pm-tp-live").textContent = "● LIVE — slide " + (idx + 1) + " / " + ids.length;
          pmEl("pm-prev").setAttribute("aria-disabled", idx <= 0 ? "true" : "false");
          pmEl("pm-next").setAttribute("aria-disabled", idx >= ids.length - 1 ? "true" : "false");
          pmAnnounce("Now live: slide " + (idx + 1) + " of " + ids.length);
        }
      }
```

Add `pmPresentGuarded` (used by go-live and transport; drives the Task-10 failure/preview states) and `pmAnnounce` (writes to `#pm-live-region`):

```javascript
      async function pmAnnounce(msg) { const r = pmEl("pm-live-region"); if (r) r.textContent = msg; }
      async function pmPresentGuarded(fn) {
        try {
          pmDv = await fn();
          await pmGridSyncLive(); // ring reflects HOST truth (set only if the audience truly changed)
        } catch (e) { pmGridSyncLive(); pmShowError("present the slide"); } // no ring on failure
      }
```

Wire the transport buttons in `pmRenderGrid` (Task 8 step 5 area): `pmEl("pm-prev").onclick = () => pmGridDelta(-1); pmEl("pm-next").onclick = () => pmGridDelta(1);`

- [ ] **Step 4: Run to confirm pass**

Run: `python3 scripts/operator_headless.py` → the six checks PASS.

- [ ] **Step 5: Manual check**

Run `make operator` (or `make launch` with an output window): open a presentation, single-click (blue ring, audience unchanged), double-click (red LIVE ring, audience shows the slide), press → / click Next (live advances), press ← (live steps back). Confirm keyboard arrows advance live only once something is live.

- [ ] **Step 6: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/dist/app.js scripts/operator_headless.py
git commit -m "feat(operator): grid interactions — select, double-click go-live, arrows/transport advance live, host-truth ring"
```

---

### Task 10: Grid states — failure, preview-only, blackout, deck-open, reconnect, ends

**Files:**
- Modify: `dist/app.js` (state handling in the sync/guard paths), `scripts/operator_headless.py`

**Interfaces:**
- Consumes: `output_connected`, `view().blackout`, `view().live_authored_id`; the one-shot `__pmRejectOnce` stub hook (already in the harness) for the failure path.

- [ ] **Step 1: Add failing headless checks**

DRIVER:

```javascript
      // Go-live FAILURE: no ring, an alert, prior state kept.
      window.__pmRejectOnce = true;
      var tileF = el("pm-grid-tiles").querySelectorAll('.pm-tile')[0];
      tileF.dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await sleep(40);
      ok(!el("pm-error").hidden, "a go-live failure shows the error banner (role=alert)");

      // NO audience output → honest 'Preview only' badge instead of a true live claim.
      window.__outputConnected = false;
      el("pm-grid-tiles").querySelectorAll('.pm-tile')[0].dispatchEvent(new MouseEvent("dblclick", {bubbles:true}));
      await sleep(40);
      ok(!el("pm-grid-badge").hidden && el("pm-grid-badge").textContent.indexOf("Preview only")>=0,
         "no audience output → 'Preview only' badge (honest, not a false LIVE)");
      window.__outputConnected = true;

      // BLACKOUT active → the transport says the audience is blacked out.
      V.blackout = true;
      await el("pm-grid-tiles").querySelectorAll('.pm-tile')[0] && (function(){})();
      // trigger a sync via Next
      el("pm-next").click(); await sleep(40);
      ok(el("pm-tp-live").textContent.toUpperCase().indexOf("BLACKOUT")>=0, "blackout is shown in words on the transport");
      V.blackout = false;
```

Bump `EXPECTED_MIN_CHECKS` by `3`.

- [ ] **Step 2: Run to confirm it fails**

Run: `python3 scripts/operator_headless.py` → FAIL (no preview-only badge; no blackout wording).

- [ ] **Step 3: Implement the states**

Extend `pmGridGoLive`/`pmGridDelta` to check output connectivity before claiming live, and `pmGridSyncLive` to surface blackout:

```javascript
      async function pmOutputConnected() { try { return await invoke("output_connected"); } catch (e) { return true; } }
```

In `pmPresentGuarded`, after a successful `fn()` and `pmGridSyncLive()`, set the preview-only badge from connectivity:

```javascript
        const connected = await pmOutputConnected();
        const badge = pmEl("pm-grid-badge");
        badge.hidden = connected;
        if (!connected) { badge.textContent = "Preview only — no audience output"; }
```

In `pmGridSyncLive`, fold blackout into the transport text (read from the same `view()`):

```javascript
        // (inside pmGridSyncLive, reuse the `v` from invoke("view"))
        if (liveId != null && v && v.blackout) {
          pmEl("pm-tp-live").textContent = "BLACKED OUT — slide " + (idx + 1) + " / " + ids.length + " pending";
        }
```

(Refactor so `v` is available where the transport text is set.)

Deck-open failure is already handled by Task 7's `pmLibOpen` catch (stays on Library, shows the error banner) — add a confirming check:

```javascript
      window.__pmRejectOnce = true; // reject the next deck_ command (deck_open)
      el("pm-grid-back").click(); await sleep(20); // back to library
      el("pm-lib-grid").querySelectorAll(".pm-lib-open")[0].click();
      await sleep(40);
      ok(!el("pm-library").hidden, "a failed deck_open keeps you on the Library (never a blank grid)");
      ok(!el("pm-error").hidden, "a failed deck_open surfaces an error");
```

Bump `EXPECTED_MIN_CHECKS` by a further `2` (total `+5` this task).

Reconnecting: disable ◀/▶ when the host poll is failing — in the existing `setConn(false)` path (~app.js:4058), add `pmEl("pm-prev") && pmEl("pm-prev").setAttribute("aria-disabled","true"); pmEl("pm-next") && pmEl("pm-next").setAttribute("aria-disabled","true");` and re-enable via `pmGridSyncLive()` on the next good poll.

- [ ] **Step 4: Run to confirm pass**

Run: `python3 scripts/operator_headless.py` → all new checks PASS.

- [ ] **Step 5: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/dist/app.js scripts/operator_headless.py
git commit -m "feat(operator): grid states — go-live failure, preview-only, blackout, deck-open error, reconnect"
```

---

### Task 11: Relocate the old present entry points

**Files:**
- Modify: `dist/index.html` (remove `#pm-present`), `dist/app.js` (palette re-scope, remove `#pm-present` wiring), `scripts/operator_headless.py`

**Interfaces:**
- Consumes: `pmMode` (Task 7).

- [ ] **Step 1: Add failing checks**

DRIVER:

```javascript
      ok(!document.getElementById("pm-present"), "the editor '▶ Present' button is removed (the grid owns presenting)");
      // The palette "Present slide" must not fire in Library mode.
      document.querySelector('.nav-item[data-surface="presentation"]').click(); await sleep(20); // Library
      var beforeGL = window.__calls.filter(function(c){return c.cmd==="deck_go_live";}).length;
      // open palette + run "Present slide" if offered (should be gated out in library mode)
      // (driver opens the palette via its existing helper; assert no deck_go_live fired)
      ok(window.__calls.filter(function(c){return c.cmd==="deck_go_live";}).length===beforeGL,
         "the palette 'Present slide' does not present while in Library mode");
```

Bump `EXPECTED_MIN_CHECKS` by `2`.

- [ ] **Step 2: Run to confirm it fails**

Run: `python3 scripts/operator_headless.py` → FAIL (`#pm-present` still present).

- [ ] **Step 3: Remove `#pm-present` + re-scope the palette**

In `index.html`, delete the `#pm-present` button (line ~671). In `app.js`, delete `pmEl("pm-present").onclick = pmPresent;` (~5155). Keep `pmPresent` (still used by the palette, now guarded).

Change the palette "Present slide" entry (~app.js:3925) to only present in grid/editor mode and to route to the grid's live model when in grid mode:

```javascript
          if (pmMode === "grid") { cmds.push({ label: "Present slide", ico: "▶", sub: "grid", run: () => pmGridGoLive(pmGridCursor) }); }
          else if (pmMode === "editor") { cmds.push({ label: "Present slide", ico: "▶", run: () => pmPresent() }); }
```

(Leave "Add slide"/"Undo/Redo" gated to `pmMode === "editor"`.)

- [ ] **Step 4: Run to confirm pass + full CI**

Run: `python3 scripts/operator_headless.py` → PASS.
Run: `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml`.

- [ ] **Step 5: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/dist/ scripts/operator_headless.py
git commit -m "feat(operator): relocate presenting to the grid; re-scope the command palette by mode"
```

---

### Task 12: Accessibility polish + token audit

**Files:**
- Modify: `dist/app.js` (aria-live wiring, ensure `#pm-live-region` exists for the grid), `dist/index.html` (ensure `#pm-live-region` reachable in grid), `dist/app.css` (token audit), `scripts/operator_headless.py`

- [ ] **Step 1: Add failing checks**

DRIVER:

```javascript
      // Focus ring geometry is distinct from selection (outset outline vs inset shadow).
      var t0 = el("pm-grid-tiles").querySelector('.pm-tile'); t0.focus();
      ok(document.activeElement === t0 && t0.getAttribute("tabindex")==="0", "grid tile is focusable (roving tabindex)");
      // aria-live announcement fired on go-live.
      ok(el("pm-live-region") && el("pm-live-region").textContent.indexOf("live")>=0, "live changes announce via aria-live");
```

Bump `EXPECTED_MIN_CHECKS` by `2`.

- [ ] **Step 2: Run to confirm it fails, then implement**

Ensure `#pm-live-region` (already in the editor DOM at ~index.html:752) is present/visible for the grid — if it lives only inside `.pm-body`, move it to a surface-level element so grid announcements reach it. Confirm `pmAnnounce` (Task 9) targets it. Verify the CSS ring rules from Task 8 (inset selection, outset focus, red live) are present.

- [ ] **Step 3: Token audit**

Run: `cd implementation/desktop/crates/selahcue-operator/dist && grep -nE "var\(--(live|panel|line|accent)\)" app.css` — confirm NONE of your new `.pm-grid*`/`.pm-tile*`/`.pm-transport` rules use a legacy alias (they must use `--sc-*`). Fix any hits.

- [ ] **Step 4: Run to confirm pass**

Run: `python3 scripts/operator_headless.py` → PASS.

- [ ] **Step 5: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/dist/ scripts/operator_headless.py
git commit -m "feat(operator): grid a11y — roving focus, distinct ring geometry, aria-live; token audit"
```

---

### Task 13: Full local CI gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full gate**

Run: `make ci`
Expected: PASS — `cargo fmt --check`, `clippy -D warnings`, all suites (incl. `-p selahcue-present`, `-p selahcue-gpu`, `-p selahcue-app`), operator `cargo check`, and `python3 scripts/operator_headless.py` (with its bumped `EXPECTED_MIN_CHECKS`).

- [ ] **Step 2: If clippy flags the new Rust, fix and re-run**

Common: an `unwrap` outside tests (use `?`/`let-else`), or an unused import. Re-run `make ci` until green.

- [ ] **Step 3: Final manual smoke**

Run `make launch`: Presentation nav → Library → open a deck → grid → double-click a slide (audience shows it) → arrows advance live across all outputs (including a secondary/stage output shows the authored slide, not black) → Edit ▸ → edit → ‹ Done → grid. Confirm Blackout (footer) shows the blackout wording on the transport.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore(presentation): satisfy the full CI gate for the browse/present flow"
```

---

## Self-Review

**1. Spec coverage.** Library-landing + open→grid (Task 7); grid + thumbnails (Task 8); select/go-live/arrows-advance-live/transport + host-truth ring (Task 9, §6); one-live-output (§7 — Tasks 1–6); secondary/NDI mirroring (§7.4 — Tasks 2–3); state matrix §8 — empty-deck (Task 8), loading/render-fail (Task 8), go-live-failed/preview-only/blackout/deck-open/reconnect/first-last (Tasks 9–10); a11y three-ring geometry + aria-live + roving focus (§9 — Tasks 8, 12); `--sc-*` tokens (§10 — Tasks 8, 12); relocation seams (§11 — Task 11); Edit ▸/‹ Done autosave (Task 8). Covered.

**2. Placeholder scan.** Every Rust step has real code + a runnable command; webview steps give real DOM/JS/CSS + real `ok(...)` driver checks. Two instruction-only steps (Task 1 Step 5 grep-and-mirror; Task 6 Step 6 confirm the `Backend::Remote` variant name) are deliberate lookups against real code, not code placeholders.

**3. Type consistency.** `authored_live_id` (present.rs → controller.rs → OperatorView → JS `view().live_authored_id`) is spelled identically throughout. `go_live_delta(i32)` (deck_workspace) ↔ `deck_go_live_delta({delta})` (command/JS). `pmSetMode`/`pmMode`/`pmRenderGrid`/`pmGridSyncLive`/`pmPresentGuarded`/`pmGridGoLive`/`pmGridDelta` are defined before use and referenced consistently.

**Delivery note (not a code task):** before/at implementation, create or link a ClickUp story under epic `86ajp07ce` (per the ui-ux-designer ClickUp contract) and a linked follow-up for any deferred slice; keep the Build Control task updated. Not done here without owner go-ahead.
