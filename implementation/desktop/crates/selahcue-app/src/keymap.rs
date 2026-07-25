//! The canonical keybinding map (UX-CANONICAL §1; FR-014, NFR-019) as a pure,
//! contract-tested state machine, shared by every desktop surface (the output
//! window and the operator shell implement the same map — the webview mirrors it
//! in JS, pinned by the keybinding contract test).
//!
//! | Action                 | Key                       |
//! |------------------------|---------------------------|
//! | Next slide / item      | `Space` or `→`            |
//! | Previous slide / item  | `←`                       |
//! | Go Live                | `Enter` (never overloaded with Next) |
//! | Clear all live layers  | `Esc` `Esc` (double-tap)  |
//! | Blackout (toggle)      | `B`                       |
//! | Clear current layer    | `Backspace`               |
//!
//! `Backspace` clears the current (topmost) **live** layer. The live output is
//! single-layer until per-layer clearing (story 86ajpy59e, split from 86ajp0awx
//! and blocked on the R2 multi-layer output model), so today it performs the
//! same clear as `Esc Esc`; the two actions stay distinct in the map so the
//! bindings do not change when layers arrive.
//!
//! **Emergency actions are non-unbindable:** Clear-all (`Esc Esc`) and Blackout
//! (`B`) are always present in the map — there is no configuration surface that
//! can remove them (asserted by the contract tests). The always-global OS-level
//! fallback chords (`Ctrl/Cmd+Shift+.` / `Ctrl/Cmd+Shift+B`) are the app-shell
//! acquisition story's scope; in-app, the chords are honoured even while a text
//! field or dialog has focus (the operator shell routes them around inputs).
//!
//! Memory: the only state is the timestamp of a pending first `Esc` — bounded.

use std::time::{Duration, Instant};

/// A pressed key, surface-agnostic (winit and the webview both translate into this).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeyPress {
    /// A printable character key (case-insensitive matching).
    Char(char),
    Enter,
    Space,
    Escape,
    Backspace,
    ArrowLeft,
    ArrowRight,
}

/// A canonical action the surface must perform. Surfaces translate these into
/// controller commands (`BlackoutToggle` needs the current blackout state, which
/// only the caller has).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CanonicalAction {
    Next,
    Previous,
    GoLive,
    /// Clear ALL live layers (double-`Esc` completed).
    ClearAll,
    /// Toggle the audience blackout.
    BlackoutToggle,
    /// Clear the current (topmost) live layer only (see the module doc: equal
    /// to a full clear while the live output is single-layer — real per-layer
    /// semantics land with story 86ajpy59e).
    ClearLayer,
}

/// How long the second `Esc` of the double-tap may lag the first.
pub const DOUBLE_ESC_WINDOW: Duration = Duration::from_millis(1000);

/// The canonical keymap state machine. One instance per input surface.
#[derive(Debug, Default)]
pub struct Keymap {
    pending_escape: Option<Instant>,
}

impl Keymap {
    pub fn new() -> Self {
        Self::default()
    }

    /// Feed a key press; returns the canonical action it completes, if any.
    /// A first `Esc` returns `None` (armed); a second within
    /// [`DOUBLE_ESC_WINDOW`] returns `ClearAll`.
    pub fn press(&mut self, key: KeyPress, now: Instant) -> Option<CanonicalAction> {
        // Any non-Escape key disarms a pending double-tap (deliberate: Esc-then-B
        // is a blackout, not a half-clear).
        if !matches!(key, KeyPress::Escape) {
            self.pending_escape = None;
        }
        match key {
            KeyPress::Space | KeyPress::ArrowRight => Some(CanonicalAction::Next),
            KeyPress::ArrowLeft => Some(CanonicalAction::Previous),
            KeyPress::Enter => Some(CanonicalAction::GoLive),
            KeyPress::Backspace => Some(CanonicalAction::ClearLayer),
            KeyPress::Char(c) if c.eq_ignore_ascii_case(&'b') => {
                Some(CanonicalAction::BlackoutToggle)
            }
            KeyPress::Escape => match self.pending_escape.take() {
                Some(t0) if now.duration_since(t0) <= DOUBLE_ESC_WINDOW => {
                    Some(CanonicalAction::ClearAll)
                }
                _ => {
                    self.pending_escape = Some(now);
                    None
                }
            },
            KeyPress::Char(_) => None,
        }
    }

    /// Disarm a pending double-`Esc`. Surfaces MUST call this when they handle a
    /// key outside the keymap (e.g. the host-local pairing keys `P`/`Y`/`N`) —
    /// otherwise `Esc`, host-key, `Esc` would complete an accidental Clear-all.
    pub fn disarm(&mut self) {
        self.pending_escape = None;
    }

    /// A first `Esc` has been pressed and the clear-all double-tap is armed
    /// (surfaces may show a "press Esc again to clear" hint).
    pub fn escape_armed(&self) -> bool {
        self.pending_escape.is_some()
    }
}
