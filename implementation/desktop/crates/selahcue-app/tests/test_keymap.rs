//! Keybinding contract (story 86ajp0b3d): the canonical map matches
//! UX-CANONICAL §1 exactly, and the emergency bindings can never be absent.

use selahcue_app::keymap::{CanonicalAction, KeyPress, Keymap, DOUBLE_ESC_WINDOW};
use std::time::{Duration, Instant};

fn press(km: &mut Keymap, key: KeyPress) -> Option<CanonicalAction> {
    km.press(key, Instant::now())
}

#[test]
fn the_canonical_map_matches_ux_canonical() {
    let mut km = Keymap::new();
    // Next = Space or →; Previous = ←; Go Live = Enter (distinct from Next, M8).
    assert_eq!(press(&mut km, KeyPress::Space), Some(CanonicalAction::Next));
    assert_eq!(
        press(&mut km, KeyPress::ArrowRight),
        Some(CanonicalAction::Next)
    );
    assert_eq!(
        press(&mut km, KeyPress::ArrowLeft),
        Some(CanonicalAction::Previous)
    );
    assert_eq!(
        press(&mut km, KeyPress::Enter),
        Some(CanonicalAction::GoLive)
    );
    // Blackout = B (either case); clear current layer = Backspace.
    assert_eq!(
        press(&mut km, KeyPress::Char('b')),
        Some(CanonicalAction::BlackoutToggle)
    );
    assert_eq!(
        press(&mut km, KeyPress::Char('B')),
        Some(CanonicalAction::BlackoutToggle)
    );
    assert_eq!(
        press(&mut km, KeyPress::Backspace),
        Some(CanonicalAction::ClearLayer)
    );
    // Enter is never Next: staging and going live are distinct keys.
    assert_ne!(press(&mut km, KeyPress::Enter), Some(CanonicalAction::Next));
}

#[test]
fn clear_all_requires_a_double_escape() {
    let mut km = Keymap::new();
    let t0 = Instant::now();
    // A single Esc does nothing except arm the double-tap.
    assert_eq!(km.press(KeyPress::Escape, t0), None);
    assert!(km.escape_armed());
    // The second Esc inside the window clears all layers.
    assert_eq!(
        km.press(KeyPress::Escape, t0 + Duration::from_millis(300)),
        Some(CanonicalAction::ClearAll)
    );
    assert!(!km.escape_armed(), "consumed after firing");
}

#[test]
fn a_slow_second_escape_does_not_clear() {
    let mut km = Keymap::new();
    let t0 = Instant::now();
    assert_eq!(km.press(KeyPress::Escape, t0), None);
    // Past the window the second press re-arms instead of firing.
    let late = t0 + DOUBLE_ESC_WINDOW + Duration::from_millis(1);
    assert_eq!(km.press(KeyPress::Escape, late), None);
    assert!(km.escape_armed(), "late Esc re-arms the double-tap");
    // ...and the third press (fast) then fires.
    assert_eq!(
        km.press(KeyPress::Escape, late + Duration::from_millis(100)),
        Some(CanonicalAction::ClearAll)
    );
}

#[test]
fn an_intervening_key_disarms_the_double_tap() {
    let mut km = Keymap::new();
    let t0 = Instant::now();
    assert_eq!(km.press(KeyPress::Escape, t0), None);
    // Esc then B is a Blackout — never a half-armed clear.
    assert_eq!(
        km.press(KeyPress::Char('b'), t0 + Duration::from_millis(100)),
        Some(CanonicalAction::BlackoutToggle)
    );
    assert!(!km.escape_armed());
    assert_eq!(
        km.press(KeyPress::Escape, t0 + Duration::from_millis(200)),
        None,
        "the Esc after B is a fresh first tap"
    );
}

#[test]
fn emergency_bindings_are_non_unbindable() {
    // The map has no removal/configuration API at all: pressing the emergency
    // keys ALWAYS resolves. (Rebinding, when it arrives, may remap but the
    // actions must stay reachable — this contract is the regression tripwire.)
    let mut km = Keymap::new();
    let t0 = Instant::now();
    assert_eq!(
        km.press(KeyPress::Char('b'), t0),
        Some(CanonicalAction::BlackoutToggle)
    );
    km.press(KeyPress::Escape, t0);
    assert_eq!(
        km.press(KeyPress::Escape, t0 + Duration::from_millis(10)),
        Some(CanonicalAction::ClearAll)
    );
}

#[test]
fn keymap_state_is_bounded() {
    // No-leak rule: arbitrary key traffic never grows state — the only field is
    // the pending-escape timestamp.
    let mut km = Keymap::new();
    let t0 = Instant::now();
    for i in 0..10_000 {
        let key = match i % 5 {
            0 => KeyPress::Space,
            1 => KeyPress::Escape,
            2 => KeyPress::Char('x'),
            3 => KeyPress::Enter,
            _ => KeyPress::ArrowLeft,
        };
        km.press(key, t0 + Duration::from_millis(i));
    }
    assert_eq!(
        std::mem::size_of::<Keymap>(),
        std::mem::size_of::<Option<Instant>>()
    );
}

#[test]
fn host_handled_keys_disarm_via_the_disarm_api() {
    // Surfaces that handle keys OUTSIDE the keymap (the host pairing keys
    // P/Y/N) must call disarm() — Esc, host-key, Esc is never a Clear-all.
    let mut km = Keymap::new();
    let t0 = Instant::now();
    assert_eq!(km.press(KeyPress::Escape, t0), None);
    assert!(km.escape_armed());
    km.disarm(); // what main.rs does on P/Y/N
    assert!(!km.escape_armed());
    assert_eq!(
        km.press(KeyPress::Escape, t0 + Duration::from_millis(100)),
        None,
        "the Esc after a host key is a fresh first tap"
    );
}
