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
        reg.redeem(
            "aaaaaa",
            dev("a"),
            SessionToken::new("t"),
            t0 + Duration::from_secs(20)
        ),
        Err(PairingError::UnknownCode)
    );
    assert!(reg
        .redeem(
            "bbbbbb",
            dev("b"),
            SessionToken::new("t"),
            t0 + Duration::from_secs(20)
        )
        .is_ok());
}

#[test]
fn empty_token_never_authenticates() {
    // Even if an empty token were somehow stored, presenting "" must not authenticate.
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("555555", Role::Operator, now, Duration::from_secs(60));
    reg.redeem("555555", dev("d"), SessionToken::new(""), now)
        .unwrap();
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
    reg.redeem("aaa", dev("A"), SessionToken::new("tokA"), now)
        .unwrap();
    reg.redeem("bbb", dev("B"), SessionToken::new("tokB"), now)
        .unwrap();
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
    reg.redeem("ccc", dev("d"), SessionToken::new("s3cr3t-value"), now)
        .unwrap();
    assert_eq!(reg.authenticate(&dev("d"), "s3cr3t"), None); // prefix
    assert_eq!(reg.authenticate(&dev("d"), "s3cr3t-value-extra"), None); // longer
    assert_eq!(reg.authenticate(&dev("d"), "s3cr3t-valuE"), None); // one char differs
    assert_eq!(
        reg.authenticate(&dev("d"), "s3cr3t-value"),
        Some(Role::Producer)
    );
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
        reg.redeem(
            &code,
            dev(&format!("d{i}")),
            SessionToken::new(format!("t{i}")),
            now,
        )
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
        reg.redeem(&code, d.clone(), SessionToken::new(format!("t{i}")), now)
            .unwrap();
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
    assert!(
        !shown.contains("super-secret-value"),
        "token leaked via Debug: {shown}"
    );
}

#[test]
fn withdrawing_an_offer_kills_the_code_immediately() {
    // Cancelling pairing mode must make the code un-redeemable at once — not leave
    // it alive until TTL (e.g. the operator cancels because the QR was photographed).
    let mut reg = SessionRegistry::new();
    let now = Instant::now();
    reg.offer_pairing("CODE1234", Role::Producer, now, Duration::from_secs(120));
    assert!(reg.code_valid("CODE1234", now));
    assert!(reg.withdraw("CODE1234"));
    assert!(!reg.code_valid("CODE1234", now), "withdrawn code is dead");
    assert!(
        reg.redeem(
            "CODE1234",
            DeviceId("d".into()),
            SessionToken::new("t"),
            now
        )
        .is_err(),
        "withdrawn code cannot be redeemed"
    );
    assert!(!reg.withdraw("CODE1234"), "second withdraw is a no-op");
    assert_eq!(reg.pending_count(), 0);
}

#[test]
fn active_sessions_are_hard_capped() {
    // Audit M3: the active-session map must not grow without bound. Pairing MAX_ACTIVE_SESSIONS
    // distinct devices fills it; a further NEW device is refused with TooManySessions (its
    // single-use code is still consumed, so pending never grows); re-pairing an already-active
    // device still works (replaces, no growth); freeing a slot (revoke) + a fresh code lets a
    // new device in.
    use selahcue_lan::session::MAX_ACTIVE_SESSIONS;
    let now = Instant::now();
    let ttl = Duration::from_secs(300);
    let mut reg = SessionRegistry::new();
    for i in 0..MAX_ACTIVE_SESSIONS {
        let code = format!("code-{i}");
        reg.offer_pairing(&code, Role::Producer, now, ttl);
        reg.redeem(
            &code,
            dev(&format!("dev-{i}")),
            SessionToken::new(format!("tok-{i}")),
            now,
        )
        .expect("under the cap");
    }
    assert_eq!(reg.active_count(), MAX_ACTIVE_SESSIONS);
    assert_eq!(reg.pending_count(), 0, "every offer consumed");

    // A NEW device is refused, the map stays capped, and the single-use code is still consumed.
    reg.offer_pairing("overflow", Role::Producer, now, ttl);
    assert_eq!(
        reg.redeem(
            "overflow",
            dev("dev-new"),
            SessionToken::new("tok-new"),
            now
        ),
        Err(PairingError::TooManySessions)
    );
    assert_eq!(reg.active_count(), MAX_ACTIVE_SESSIONS, "still capped");
    assert!(
        !reg.code_valid("overflow", now),
        "the single-use code is consumed even on a cap rejection (pending never grows)"
    );

    // Re-pairing an ALREADY-active device is allowed at the cap (replaces, no growth).
    reg.offer_pairing("repair", Role::Producer, now, ttl);
    assert!(reg
        .redeem("repair", dev("dev-0"), SessionToken::new("tok-0b"), now)
        .is_ok());
    assert_eq!(
        reg.active_count(),
        MAX_ACTIVE_SESSIONS,
        "re-pair does not grow"
    );

    // Freeing a slot (revoke) + a fresh code lets a new device in.
    assert!(reg.revoke(&dev("dev-1")));
    reg.offer_pairing("after-revoke", Role::Producer, now, ttl);
    assert!(reg
        .redeem(
            "after-revoke",
            dev("dev-new2"),
            SessionToken::new("tok-new2"),
            now
        )
        .is_ok());
    assert_eq!(reg.active_count(), MAX_ACTIVE_SESSIONS);
}

#[test]
fn prune_idle_reclaims_idle_sessions_and_keeps_touched_ones() {
    // Audit #8: a session unused past the idle-TTL self-reclaims; a re-authenticated (touched)
    // one survives. Clock-injected (no wall-clock).
    use selahcue_lan::session::SESSION_IDLE_TTL;
    let t0 = Instant::now();
    let ttl = Duration::from_secs(300);
    let mut reg = SessionRegistry::new();
    for id in ["dev-a", "dev-b"] {
        reg.offer_pairing(id, Role::Producer, t0, Duration::from_secs(60));
        reg.redeem(id, dev(id), SessionToken::new(id), t0).unwrap();
    }
    assert_eq!(reg.active_count(), 2);
    // dev-b re-authenticates at t0+200s → its idle clock resets.
    assert!(reg.touch(&dev("dev-b"), t0 + Duration::from_secs(200)));
    assert!(
        !reg.touch(&dev("ghost"), t0),
        "touch on an unknown device is a no-op"
    );
    // At t0+301s: dev-a idle 301s (> ttl) → reclaimed; dev-b idle 101s (<= ttl) → kept.
    let now = t0 + ttl + Duration::from_secs(1);
    assert_eq!(
        reg.prune_idle(now, ttl),
        1,
        "exactly the idle session is reclaimed"
    );
    assert_eq!(reg.active_count(), 1);
    assert!(
        reg.authenticate(&dev("dev-b"), "dev-b").is_some(),
        "the touched session survives"
    );
    assert!(
        reg.authenticate(&dev("dev-a"), "dev-a").is_none(),
        "the idle session was reclaimed"
    );
    // The shipped TTL is generous (longer than a service) so an active device is never pruned mid-use.
    assert!(SESSION_IDLE_TTL >= Duration::from_secs(3600));
}

#[test]
fn idle_ttl_frees_cap_slots_but_recently_active_sessions_still_reject() {
    // Audit #8 + M3: a full registry of RECENTLY-ACTIVE sessions still rejects a new device
    // (fail-closed); once they all go idle, prune_idle frees the whole registry and a new
    // device pairs — so the cap bounds recently-active, not lifetime, pairings.
    use selahcue_lan::session::MAX_ACTIVE_SESSIONS;
    let t0 = Instant::now();
    let ttl = Duration::from_secs(300);
    let mut reg = SessionRegistry::new();
    for i in 0..MAX_ACTIVE_SESSIONS {
        let code = format!("c{i}");
        reg.offer_pairing(&code, Role::Producer, t0, Duration::from_secs(60));
        reg.redeem(
            &code,
            dev(&format!("d{i}")),
            SessionToken::new(format!("t{i}")),
            t0,
        )
        .unwrap();
    }
    assert_eq!(reg.active_count(), MAX_ACTIVE_SESSIONS);

    // All recently active → prune reclaims nothing → a new device is still refused.
    let fresh = t0 + Duration::from_secs(10);
    for i in 0..MAX_ACTIVE_SESSIONS {
        reg.touch(&dev(&format!("d{i}")), fresh);
    }
    assert_eq!(reg.prune_idle(fresh, ttl), 0, "nothing idle yet");
    reg.offer_pairing("overflow", Role::Producer, fresh, Duration::from_secs(60));
    assert_eq!(
        reg.redeem("overflow", dev("new"), SessionToken::new("tok-new"), fresh),
        Err(PairingError::TooManySessions),
        "a full registry of recently-active sessions still rejects (fail-closed)"
    );

    // Let them all go idle → prune frees the whole registry → a new device pairs.
    let later = t0 + ttl + Duration::from_secs(20); // last_seen == fresh (t0+10); idle 310s > ttl
    assert_eq!(reg.prune_idle(later, ttl), MAX_ACTIVE_SESSIONS);
    assert_eq!(reg.active_count(), 0);
    reg.offer_pairing("after-idle", Role::Producer, later, Duration::from_secs(60));
    assert!(
        reg.redeem(
            "after-idle",
            dev("fresh-dev"),
            SessionToken::new("tok-fresh"),
            later
        )
        .is_ok(),
        "after idle sessions self-reclaim, a new device pairs"
    );
    assert_eq!(reg.active_count(), 1);
}
