//! The trusted entitlement-signing key **set** (FR-518, DEC-011 pt 2).
//!
//! Two properties are under test, and they pull in opposite directions on purpose:
//! the store must be *provably a set* — able to hold more than one key, so a rotation is
//! shippable to machines already in the field — and it must be *bounded*, so it cannot
//! grow without limit. A cap of 1 would satisfy the second and destroy the first, which
//! is why the lower bound is pinned at compile time in both the source and here.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::trust::{
    derive_key_id, TrustError, TrustedKeys, MAX_TRUSTED_KEYS, PUBLIC_KEY_BYTES,
};

// --- premise pins ---------------------------------------------------------------------
// Both bounds are asserted at COMPILE time so that changing the cap cannot silently turn
// the tests below vacuous. Without the lower pin, setting MAX_TRUSTED_KEYS = 1 would make
// `the_store_is_provably_a_set` fail in a confusing way at runtime instead of stopping the
// build at the line that states the requirement.
const _: () = assert!(
    MAX_TRUSTED_KEYS >= 2,
    "FR-518/DEC-011: the trust store must be a SET. A cap of 1 is a single-key client, \
     which makes any future rotation unshippable to offline machines."
);
// The over-cap test below fills the store one key at a time. If the cap ever became huge,
// that test would still pass but would stop being a cheap, obviously-correct check.
const _: () = assert!(
    MAX_TRUSTED_KEYS <= 64,
    "the over-cap test fills the store key by key; keep the cap small enough for that to \
     stay a cheap check"
);

/// A distinct, deterministic public key per index.
fn key(n: u8) -> [u8; PUBLIC_KEY_BYTES] {
    [n; PUBLIC_KEY_BYTES]
}

#[test]
fn key_id_derivation_matches_the_server_byte_for_byte() {
    // Cross-language pins. These values were computed by Python running the SERVER's own
    // derivation (`apps/entitlements/signing.py:72-79` — SHA-256 over the raw public key,
    // first 8 hex chars), not by this implementation. If the Rust and Python derivations
    // ever disagree, every manifest fails key selection with a correct signature, which is
    // the single most confusing failure this contract can produce.
    let sequential: [u8; PUBLIC_KEY_BYTES] = core::array::from_fn(|i| i as u8);
    assert_eq!(
        derive_key_id(&sequential),
        "630dcd29",
        "key_id for the 0x00..0x1f key must match the server's derive_key_id"
    );
    assert_eq!(derive_key_id(&key(0xAA)), "e0e77a50");
    assert_eq!(derive_key_id(&key(0x11)), "02d449a3");
}

#[test]
fn key_id_is_eight_lowercase_hex_characters() {
    let id = derive_key_id(&key(7));
    assert_eq!(id.len(), 8, "key_id must be 8 characters, got {id:?}");
    assert!(
        id.chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_uppercase()),
        "key_id must be lowercase hex, got {id:?}"
    );
}

#[test]
fn the_store_is_provably_a_set_and_a_second_key_needs_no_code_change() {
    // FR-518's acceptance criterion, stated directly: "the trust store is provably a set —
    // adding a second key requires no client code change". This test IS that proof; it
    // calls only `insert`, the same call the first key uses.
    let mut store = TrustedKeys::new();

    let outgoing = store.insert(key(1)).unwrap();
    let incoming = store.insert(key(2)).unwrap();

    assert_ne!(outgoing, incoming, "distinct keys must get distinct ids");
    assert_eq!(store.len(), 2, "both keys must be held at once");

    // Per-key assertions — a count alone would not prove that BOTH are individually
    // selectable, which is the property a rotation actually depends on.
    assert!(
        store.get(&outgoing).is_some(),
        "the outgoing key must stay selectable during the overlap window"
    );
    assert!(
        store.get(&incoming).is_some(),
        "the incoming key must be selectable before the server starts signing with it"
    );
    assert_eq!(store.get(&outgoing).unwrap().public_key(), &key(1));
    assert_eq!(store.get(&incoming).unwrap().public_key(), &key(2));
}

#[test]
fn an_untrusted_key_id_is_absent_rather_than_confused_with_another_key() {
    let mut store = TrustedKeys::new();
    let known = store.insert(key(3)).unwrap();

    // Positive control FIRST: prove selection works at all on this store, so that the
    // `None` below is a real refusal and not a dead lookup that would answer `None` for
    // everything.
    assert!(
        store.get(&known).is_some(),
        "selection is not working on this store, so the refusal below proves nothing"
    );

    assert!(
        store.get("deadbeef").is_none(),
        "an unknown key_id must be refused, not resolved to some other key"
    );
    assert!(!store.contains("deadbeef"));
}

#[test]
fn the_store_is_bounded_and_the_over_cap_key_is_absent_by_name() {
    let mut store = TrustedKeys::new();

    // Pin the premise inside the test too, so a cap change cannot make this vacuous.
    const _: () = assert!(MAX_TRUSTED_KEYS >= 2);

    // Fill to exactly the cap, remembering the LAST accepted key by name.
    let mut last_accepted = String::new();
    for n in 0..MAX_TRUSTED_KEYS {
        last_accepted = store
            .insert(key(n as u8))
            .expect("inserting up to the cap must succeed");
    }

    // --- positive control, asserted BEFORE the refusal ---------------------------------
    // Without this, "the over-cap key is absent" is indistinguishable from "insert is
    // broken and nothing is ever stored". Naming what would go unexercised is the point.
    assert_eq!(
        store.len(),
        MAX_TRUSTED_KEYS,
        "the store did not actually fill to its cap, so the over-cap refusal below \
         exercises nothing"
    );
    assert!(
        store.get(&last_accepted).is_some(),
        "the last within-cap key is not retrievable, so the benign path is broken and the \
         refusal below proves nothing"
    );

    // --- the hostile case --------------------------------------------------------------
    let over_cap_key = key(MAX_TRUSTED_KEYS as u8);
    let over_cap_id = derive_key_id(&over_cap_key);
    let refused = store.insert(over_cap_key);

    assert_eq!(
        refused,
        Err(TrustError::Full {
            cap: MAX_TRUSTED_KEYS
        }),
        "the (cap+1)-th distinct key must be refused"
    );

    // Assert the ENTITY, not a proxy: the exact entry count, and the refused key's absence
    // BY NAME. A byte-budget or a `len() <= cap` check would pass even if the store had
    // silently evicted a key it was still meant to trust.
    assert_eq!(
        store.len(),
        MAX_TRUSTED_KEYS,
        "a refused insert must not change the entry count"
    );
    assert!(
        store.get(&over_cap_id).is_none(),
        "the refused key must not be present under its own key_id"
    );
    // ...and nothing already trusted was evicted to make room.
    assert!(
        store.get(&last_accepted).is_some(),
        "a refused insert must not evict an already-trusted key"
    );
}

#[test]
fn re_adding_a_trusted_key_consumes_no_slot() {
    // A loader that runs twice — or a config listing the same key under two names — must
    // not be able to exhaust the cap. Without this, "bounded" would be true while the
    // store still filled up with duplicates of one key.
    let mut store = TrustedKeys::new();
    let first = store.insert(key(9)).unwrap();
    assert_eq!(store.len(), 1);

    let again = store.insert(key(9)).unwrap();
    assert_eq!(again, first, "the same key must derive the same id");
    assert_eq!(store.len(), 1, "re-adding a key must not consume a slot");

    // And it is still the same key, not a replaced one.
    assert_eq!(store.get(&first).unwrap().public_key(), &key(9));
}

/// Two DIFFERENT 32-byte keys that derive the SAME `key_id` (`12bf2ed8`).
///
/// Found by brute force in about a second, which is the whole point: `key_id` is the first
/// 8 hex characters of SHA-256, so only 32 bits, and a colliding pair is cheap to find
/// deliberately and possible to hit by accident. Both values are pinned here so the test
/// is deterministic and needs no search at runtime.
fn colliding_pair() -> ([u8; PUBLIC_KEY_BYTES], [u8; PUBLIC_KEY_BYTES]) {
    let mut a = [0u8; PUBLIC_KEY_BYTES];
    a[0..4].copy_from_slice(&5264u32.to_le_bytes());
    let mut b = [0u8; PUBLIC_KEY_BYTES];
    b[0..4].copy_from_slice(&57654u32.to_le_bytes());
    (a, b)
}

#[test]
fn the_colliding_pair_really_does_collide() {
    // Premise check for the test below. Without it, a change to `derive_key_id` would stop
    // these two keys colliding and `a_key_id_collision_is_refused_not_silently_dropped`
    // would pass while exercising nothing at all.
    let (a, b) = colliding_pair();
    assert_ne!(a, b, "the two keys must be different key material");
    assert_eq!(
        derive_key_id(&a),
        derive_key_id(&b),
        "these keys no longer collide; the collision test below is now vacuous and needs \
         a fresh pair"
    );
    assert_eq!(derive_key_id(&a), "12bf2ed8");
}

#[test]
fn a_key_id_collision_is_refused_not_silently_dropped() {
    // Treating "id already present" as idempotent success without comparing key material
    // would keep the first key, discard the second, and return Ok. Verification then uses
    // the stored full 32-byte key, so it is fail-closed rather than a forgery vector — but
    // it is a SILENT rotation denial-of-service on the mechanism DEC-011's accepted
    // no-KMS risk depends on, surfacing in the field only as unexplained verification
    // failures.
    let (first, second) = colliding_pair();
    let mut store = TrustedKeys::new();

    let id = store.insert(first).unwrap();

    // Positive control before the refusal: the first key really is stored and selectable,
    // so the error below is about the collision and not about a store that rejects
    // everything.
    assert_eq!(store.len(), 1);
    assert_eq!(
        store.get(&id).unwrap().public_key(),
        &first,
        "the first key must be retrievable, or the refusal below proves nothing"
    );

    let refused = store.insert(second);
    assert_eq!(
        refused,
        Err(TrustError::Collision { key_id: id.clone() }),
        "a different key deriving an existing id must be refused, not swallowed"
    );

    // The store is unchanged: still one entry, still the ORIGINAL key material.
    assert_eq!(
        store.len(),
        1,
        "a refused collision must not change the count"
    );
    assert_eq!(
        store.get(&id).unwrap().public_key(),
        &first,
        "the stored key must still be the first one, not silently replaced"
    );
}

#[test]
fn key_ids_are_reported_deterministically() {
    // Deterministic ordering keeps diagnostics and any future logging stable.
    let mut a = TrustedKeys::new();
    let mut b = TrustedKeys::new();
    for n in [5u8, 1, 9, 3] {
        a.insert(key(n)).unwrap();
    }
    for n in [3u8, 9, 1, 5] {
        b.insert(key(n)).unwrap();
    }
    assert_eq!(
        a.key_ids(),
        b.key_ids(),
        "insertion order must not change the reported set"
    );
}

#[test]
fn the_bundled_store_is_empty_and_says_so_honestly() {
    // No production entitlement public key has been issued for bundling yet (DEC-011 pt 1
    // keeps the private key as a server env-var seed). An empty store fails closed on
    // VERIFICATION — every key_id is unknown, so every manifest is refused, which FR-518
    // says must keep the previous valid cache and never degrade the running app. It must
    // never fail closed on PRESENTATION, which is why nothing in this crate consults it to
    // decide whether the app may run.
    let bundled = TrustedKeys::bundled();
    assert!(bundled.is_empty());
    assert_eq!(bundled.len(), 0);
    assert!(
        bundled.get("630dcd29").is_none(),
        "an empty bundled store trusts nothing"
    );
    assert_eq!(TrustedKeys::capacity(), MAX_TRUSTED_KEYS);
}
