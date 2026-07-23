//! Device pairing and session-authentication tests. Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_lan::rbac::Role;
use selahcue_lan::session::{DeviceId, PairingError, SessionRegistry, SessionToken};
use std::time::{Duration, Instant};

fn dev(id: &str) -> DeviceId {
    DeviceId(id.into())
}

#[test]
fn pair_then_authenticate_happy_path() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("428913", Role::Producer, now, Duration::from_secs(120));

    let role = reg
        .redeem("428913", dev("ipad-01"), SessionToken::new("tok-abc"), now)
        .unwrap();
    assert_eq!(role, Role::Producer);
    assert_eq!(reg.active_count(), 1);

    // The token authenticates; the granted role comes back.
    assert_eq!(
        reg.authenticate(&dev("ipad-01"), "tok-abc"),
        Some(Role::Producer)
    );
}

#[test]
fn wrong_token_does_not_authenticate() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("111111", Role::Assistant, now, Duration::from_secs(60));
    reg.redeem("111111", dev("phone"), SessionToken::new("real"), now)
        .unwrap();

    assert_eq!(reg.authenticate(&dev("phone"), "wrong"), None);
    // Unknown device also fails.
    assert_eq!(reg.authenticate(&dev("ghost"), "real"), None);
}

#[test]
fn pairing_code_is_single_use() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("222222", Role::Viewer, now, Duration::from_secs(60));
    reg.redeem("222222", dev("a"), SessionToken::new("t1"), now)
        .unwrap();
    // The same code cannot be redeemed again (no replay).
    let second = reg.redeem("222222", dev("b"), SessionToken::new("t2"), now);
    assert_eq!(second, Err(PairingError::UnknownCode));
    assert_eq!(reg.active_count(), 1);
}

#[test]
fn expired_code_is_rejected_and_consumed() {
    let mut reg = SessionRegistry::new();
    let t0 = Instant::now();
    reg.offer_pairing("333333", Role::Producer, t0, Duration::from_secs(30));
    let later = t0 + Duration::from_secs(31);
    let res = reg.redeem("333333", dev("late"), SessionToken::new("t"), later);
    assert_eq!(res, Err(PairingError::ExpiredCode));
    // Consumed even on expiry — a second attempt now reports UnknownCode.
    assert_eq!(
        reg.redeem("333333", dev("late"), SessionToken::new("t"), later),
        Err(PairingError::UnknownCode)
    );
    assert_eq!(reg.active_count(), 0);
}

#[test]
fn unknown_code_is_rejected() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    assert_eq!(
        reg.redeem("000000", dev("x"), SessionToken::new("t"), now),
        Err(PairingError::UnknownCode)
    );
}

#[test]
fn revoke_ends_the_session() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("444444", Role::Operator, now, Duration::from_secs(60));
    reg.redeem("444444", dev("mac"), SessionToken::new("k"), now)
        .unwrap();
    assert_eq!(reg.authenticate(&dev("mac"), "k"), Some(Role::Operator));

    assert!(reg.revoke(&dev("mac")));
    assert_eq!(reg.authenticate(&dev("mac"), "k"), None);
    assert!(!reg.revoke(&dev("mac"))); // already gone
}

#[test]
fn prune_expired_drops_only_stale_offers() {
    let mut reg = SessionRegistry::new();
    let t0 = Instant::now();
    reg.offer_pairing("aaaaaa", Role::Viewer, t0, Duration::from_secs(10));
    reg.offer_pairing("bbbbbb", Role::Viewer, t0, Duration::from_secs(300));
    reg.prune_expired(t0 + Duration::from_secs(20));
    // The short-lived offer is gone; the long-lived one still redeems.
    assert_eq!(
        reg.redeem("aaaaaa", dev("a"), SessionToken::new("t"), t0 + Duration::from_secs(20)),
        Err(PairingError::UnknownCode)
    );
    assert!(reg
        .redeem("bbbbbb", dev("b"), SessionToken::new("t"), t0 + Duration::from_secs(20))
        .is_ok());
}

#[test]
fn empty_token_never_authenticates() {
    // Even if an empty token were somehow stored, presenting "" must not authenticate.
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("555555", Role::Operator, now, Duration::from_secs(60));
    reg.redeem("555555", dev("d"), SessionToken::new(""), now).unwrap();
    assert_eq!(reg.authenticate(&dev("d"), ""), None);
    // A real non-empty token still authenticates normally elsewhere (sanity).
    assert_eq!(reg.authenticate(&dev("d"), "anything"), None);
}

#[test]
fn empty_code_cannot_be_offered_or_redeemed() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("", Role::Operator, now, Duration::from_secs(60)); // no-op
    assert_eq!(
        reg.redeem("", dev("x"), SessionToken::new("t"), now),
        Err(PairingError::UnknownCode)
    );
    assert_eq!(reg.active_count(), 0);
}

#[test]
fn a_device_cannot_use_another_devices_token() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("aaa", Role::Operator, now, Duration::from_secs(60));
    reg.offer_pairing("bbb", Role::Viewer, now, Duration::from_secs(60));
    reg.redeem("aaa", dev("A"), SessionToken::new("tokA"), now).unwrap();
    reg.redeem("bbb", dev("B"), SessionToken::new("tokB"), now).unwrap();
    // B presenting A's valid token must fail — no cross-device confusion.
    assert_eq!(reg.authenticate(&dev("B"), "tokA"), None);
    assert_eq!(reg.authenticate(&dev("A"), "tokB"), None);
    // Each device still authenticates with its own token.
    assert_eq!(reg.authenticate(&dev("A"), "tokA"), Some(Role::Operator));
    assert_eq!(reg.authenticate(&dev("B"), "tokB"), Some(Role::Viewer));
}

#[test]
fn prefix_and_length_mismatched_tokens_are_rejected() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("ccc", Role::Producer, now, Duration::from_secs(60));
    reg.redeem("ccc", dev("d"), SessionToken::new("s3cr3t-value"), now).unwrap();
    assert_eq!(reg.authenticate(&dev("d"), "s3cr3t"), None); // prefix
    assert_eq!(reg.authenticate(&dev("d"), "s3cr3t-value-extra"), None); // longer
    assert_eq!(reg.authenticate(&dev("d"), "s3cr3t-valuE"), None); // one char differs
    assert_eq!(reg.authenticate(&dev("d"), "s3cr3t-value"), Some(Role::Producer));
}

#[test]
fn expiry_is_inclusive_at_the_exact_boundary() {
    let mut reg = SessionRegistry::new();
    let t0 = Instant::now();
    let ttl = Duration::from_secs(30);
    reg.offer_pairing("ddd", Role::Producer, t0, ttl);
    // Exactly at expires_at: `now >= expires_at` → expired.
    assert_eq!(
        reg.redeem("ddd", dev("late"), SessionToken::new("t"), t0 + ttl),
        Err(PairingError::ExpiredCode)
    );
    // Just before the boundary still redeems.
    reg.offer_pairing("eee", Role::Producer, t0, ttl);
    assert!(reg
        .redeem(
            "eee",
            dev("intime"),
            SessionToken::new("t"),
            t0 + ttl - Duration::from_nanos(1)
        )
        .is_ok());
}

// --- bounded-memory / no-unbounded-growth guards (no-memory-leaks requirement) ---

#[test]
fn redeeming_consumes_the_offer_so_pending_does_not_grow() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    // Pair 100 devices; each redeem must consume its offer.
    for i in 0..100u32 {
        let code = format!("code-{i}");
        reg.offer_pairing(code.clone(), Role::Viewer, now, Duration::from_secs(300));
        reg.redeem(&code, dev(&format!("d{i}")), SessionToken::new(format!("t{i}")), now)
            .unwrap();
    }
    // Every offer was consumed — pending is empty, active is exactly the 100 devices.
    assert_eq!(reg.pending_count(), 0, "pending offers leaked");
    assert_eq!(reg.active_count(), 100);
}

#[test]
fn expired_offers_are_reclaimed_by_prune() {
    let mut reg = SessionRegistry::new();
    let t0 = Instant::now();
    for i in 0..500u32 {
        reg.offer_pairing(format!("c{i}"), Role::Viewer, t0, Duration::from_secs(10));
    }
    assert_eq!(reg.pending_count(), 500);
    // After they all expire, pruning returns pending to zero — no unbounded growth.
    reg.prune_expired(t0 + Duration::from_secs(11));
    assert_eq!(reg.pending_count(), 0, "expired offers were not reclaimed");
}

#[test]
fn repeated_failed_redeems_do_not_accumulate_state() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    // Thousands of wrong-code attempts must not grow either map.
    for i in 0..2000u32 {
        let _ = reg.redeem(&format!("nope-{i}"), dev("x"), SessionToken::new("t"), now);
    }
    assert_eq!(reg.pending_count(), 0);
    assert_eq!(reg.active_count(), 0);
}

#[test]
fn revoking_returns_active_sessions_to_baseline() {
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    let devices: Vec<_> = (0..50u32).map(|i| dev(&format!("dev{i}"))).collect();
    for (i, d) in devices.iter().enumerate() {
        let code = format!("k{i}");
        reg.offer_pairing(code.clone(), Role::Producer, now, Duration::from_secs(300));
        reg.redeem(&code, d.clone(), SessionToken::new(format!("t{i}")), now).unwrap();
    }
    assert_eq!(reg.active_count(), 50);
    for d in &devices {
        assert!(reg.revoke(d));
    }
    // All sessions released — back to an empty registry.
    assert_eq!(reg.active_count(), 0, "revoked sessions leaked");
    assert_eq!(reg.pending_count(), 0);
}

#[test]
fn token_debug_is_redacted() {
    // A leaked token in logs/panics would be a credential disclosure.
    let t = SessionToken::new("super-secret-value");
    let shown = format!("{t:?}");
    assert!(!shown.contains("super-secret-value"), "token leaked via Debug: {shown}");
}
