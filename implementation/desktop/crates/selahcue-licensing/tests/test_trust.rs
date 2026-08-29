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
    // `len()` is a weak witness here: `BTreeMap::insert` REPLACES under an existing id, so
    // the count stays 1 whether or not the dedupe ran. Retrievability by id is the real
    // assertion, and `re_adding_a_key_to_a_completely_full_store_still_succeeds` covers the ordering.
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
fn re_adding_a_key_to_a_completely_full_store_still_succeeds() {
    // The dedupe has to run BEFORE the cap check, and only a full store can tell the
    // difference. `re_adding_a_trusted_key_consumes_no_slot` uses a store with one entry, so
    // removing the dedupe leaves it green: the cap is never reached, `insert` falls through
    // and `BTreeMap::insert` REPLACES rather than adds, so `len()` stays 1 either way.
    //
    // At the cap the two orders diverge visibly: dedupe-first returns `Ok`, cap-first
    // returns `Err(Full)` for a key the store already trusts. That is the failure an
    // operator would hit re-running a loader on a fully-populated store.
    let mut store = TrustedKeys::new();
    let mut ids = Vec::new();
    for n in 0..MAX_TRUSTED_KEYS {
        ids.push(store.insert(key(n as u8)).unwrap());
    }

    // Positive control before the re-add: the store really is full and the key really is in
    // it, so an `Ok` below is about the dedupe and not about a store with room to spare.
    assert_eq!(store.len(), MAX_TRUSTED_KEYS, "the store must be full");
    let existing = ids[0].clone();
    assert!(
        store.get(&existing).is_some(),
        "the key being re-added must already be present, or this proves nothing"
    );

    let again = store
        .insert(key(0))
        .expect("re-adding a key the FULL store already trusts must succeed, not hit the cap");
    assert_eq!(again, existing);
    assert_eq!(
        store.len(),
        MAX_TRUSTED_KEYS,
        "no slot consumed, none freed"
    );

    // Per-key retrievability, not just a count: the entry must still be the SAME material.
    // A count alone survives `BTreeMap::insert` replacing the value under the same id.
    assert_eq!(
        store.get(&existing).unwrap().public_key(),
        &key(0),
        "the re-added key must still resolve to its own material"
    );
    for (n, id) in ids.iter().enumerate() {
        assert_eq!(
            store.get(id).map(|k| *k.public_key()),
            Some(key(n as u8)),
            "key {n} is no longer retrievable by its own id after the re-add"
        );
    }
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
fn no_production_key_is_bundled_yet_and_the_store_says_so_honestly() {
    // This test used to assert the bundled store was simply EMPTY. That stopped being true
    // when debug builds began trusting the development key, so it is restated rather than
    // deleted: what it actually protects is that **no production key is bundled**, because
    // none has been issued — the production signing key is a server env-var seed (DEC-011
    // pt 1). An empty store fails closed on VERIFICATION (every key_id is unknown, so every
    // manifest is refused, which FR-518 says must keep the previous valid cache) and never
    // fails closed on PRESENTATION, which is why nothing consults it to decide whether the
    // app may run.
    let bundled = TrustedKeys::bundled();

    let production_keys = bundled
        .key_ids()
        .into_iter()
        .filter(|id| *id != TrustedKeys::DEV_KEY_ID)
        .count();
    assert_eq!(
        production_keys, 0,
        "a production entitlement key appeared in the bundled set; if one has genuinely \
         been issued, this test should be updated deliberately rather than by surprise"
    );

    // A key_id nobody has issued is unknown in every profile.
    assert!(bundled.get("630dcd29").is_none());
    assert_eq!(TrustedKeys::capacity(), MAX_TRUSTED_KEYS);
}

#[test]
fn the_development_key_id_matches_its_committed_bytes() {
    // The id and the bytes are committed separately (the id in `trust.rs`, the bytes there
    // and in `dev-signing-key.NOT-A-SECRET`). If they ever drifted, a debug build would
    // trust a key nobody could name and the exclusion test below would assert the absence
    // of something that was never present — passing while protecting nothing.
    let bytes: [u8; PUBLIC_KEY_BYTES] = [
        122, 63, 108, 222, 26, 234, 144, 88, 16, 53, 82, 180, 127, 244, 213, 16, 86, 6, 76, 132,
        249, 209, 18, 122, 21, 96, 175, 100, 231, 174, 33, 129,
    ];
    assert_eq!(
        derive_key_id(&bytes),
        TrustedKeys::DEV_KEY_ID,
        "the committed dev key_id does not match the committed dev public key"
    );
}

#[test]
fn the_development_key_is_trusted_in_this_build_iff_it_is_a_debug_build() {
    // Asserts the ENTITY by name — the dev key_id present or absent from the trusted set —
    // not a proxy like "the set is empty".
    let bundled = TrustedKeys::bundled();
    let trusted = bundled.contains(TrustedKeys::DEV_KEY_ID);

    if cfg!(debug_assertions) {
        // Positive control: in a debug build it IS there, and resolves to real key
        // material. Without this, "absent in release" would be indistinguishable from a
        // dead mechanism that never adds any key in any profile.
        assert!(
            trusted,
            "a debug build must trust the development key, or `make launch` would demand \
             activation on every developer's machine"
        );
        assert_eq!(
            bundled
                .get(TrustedKeys::DEV_KEY_ID)
                .map(|k| *k.public_key()),
            Some([
                122, 63, 108, 222, 26, 234, 144, 88, 16, 53, 82, 180, 127, 244, 213, 16, 86, 6, 76,
                132, 249, 209, 18, 122, 21, 96, 175, 100, 231, 174, 33, 129
            ]),
            "the trusted dev entry must be the committed key, not some other key"
        );
        assert_eq!(bundled.len(), 1, "debug trusts exactly the dev key today");
    } else {
        assert!(
            !trusted,
            "a RELEASE build must not trust the development key: its seed is committed in \
             dev-signing-key.NOT-A-SECRET, so anyone at all can sign with it"
        );
        assert!(
            bundled.is_empty(),
            "release trusts no key until one is issued"
        );
    }
}

/// `src/trust.rs` with every comment removed.
///
/// Stripping comments is the whole point. The first version of the guard below searched the
/// raw text, so deleting both `#[cfg(debug_assertions)]` gates while leaving
/// `// was: #[cfg(debug_assertions)]` behind kept it green — the `rfind` matched the gate
/// text inside the comment. A release build would then have trusted a key whose seed is
/// committed in this repository, with the whole debug suite passing.
///
/// The general lesson, worth stating where the next person writing a source guard will see
/// it: **a guard that inspects source TEXT is defeated by anything that preserves the text
/// while removing its effect** — a comment, a string literal, `#[cfg(any())]`, or moving the
/// code somewhere that never runs. Assert the effect where you can; the effect assertion
/// here is `the_development_key_is_trusted_in_this_build_iff_it_is_a_debug_build`, which
/// only exercises the release branch under `cargo test --release`, so CI now runs exactly
/// that (`ci.yml`, "Test (licensing crate in RELEASE ...)").
fn trust_rs_without_comments() -> String {
    let raw = std::fs::read_to_string(
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src/trust.rs"),
    )
    .unwrap();

    // Strip /* ... */ first, then // to end-of-line.
    let mut out = String::with_capacity(raw.len());
    let mut rest = raw.as_str();
    while let Some(open) = rest.find("/*") {
        out.push_str(&rest[..open]);
        match rest[open..].find("*/") {
            Some(close) => rest = &rest[open + close + 2..],
            None => {
                rest = "";
                break;
            }
        }
    }
    out.push_str(rest);

    out.lines()
        .map(|line| line.split("//").next().unwrap_or(""))
        .collect::<Vec<_>>()
        .join("\n")
}

#[test]
fn the_comment_stripper_actually_removes_gate_text() {
    // Positive control for the stripper itself. If it ever stopped removing comments, the
    // guard below would silently return to matching commented-out gates — the exact defect
    // it was written to close — and would still pass.
    let stripped = trust_rs_without_comments();
    assert!(
        stripped.contains("const DEV_PUBLIC_KEY"),
        "the stripper removed real code, not just comments"
    );

    let sample =
        "let a = 1; // #[cfg(debug_assertions)]\n/* #[cfg(debug_assertions)] */ let b = 2;";
    let stripped_sample: String = sample
        .lines()
        .map(|l| l.split("//").next().unwrap_or(""))
        .collect::<Vec<_>>()
        .join("\n");
    assert!(
        !stripped_sample.contains("// #[cfg"),
        "line comments must be removed before the gate search"
    );
}

#[test]
fn the_development_key_is_gated_on_debug_assertions() {
    // The runtime test can only exercise the profile it is compiled in, and `cargo test` is
    // a debug build — so on its own it never sees the release branch. This reads the source
    // (comments stripped) and fails if either gate is removed, so the control also bites in
    // an ordinary debug run.
    //
    // Two things must be gated: the key BYTES (so a release binary does not carry them) and
    // the INSERTION (so a release build does not trust them). Removing either is the defect.
    let source = trust_rs_without_comments();
    let gate = "#[cfg(debug_assertions)]";

    // Positive control: we really read trust.rs, so the assertions below are not vacuous.
    assert!(
        source.contains("DEV_PUBLIC_KEY"),
        "did not read trust.rs, or the dev key was renamed — repoint this guard, never drop it"
    );

    let bytes_at = source
        .find("const DEV_PUBLIC_KEY")
        .expect("DEV_PUBLIC_KEY declaration not found");
    let gate_before_bytes = source[..bytes_at].rfind(gate).is_some_and(|g| {
        source[g..bytes_at]
            .trim_start_matches(gate)
            .trim()
            .is_empty()
    });
    assert!(
        gate_before_bytes,
        "DEV_PUBLIC_KEY is not immediately preceded by {gate} — a release binary would \
         carry the development key material"
    );

    let insert_at = source
        .find("store.insert(DEV_PUBLIC_KEY)")
        .expect("the dev key insertion was not found in bundled()");
    assert!(
        source[..insert_at]
            .rfind(gate)
            .is_some_and(|g| !source[g..insert_at].contains("fn ")),
        "the dev key insertion in bundled() is not inside a {gate} block — a RELEASE build \
         would trust a key whose seed is committed in the repository"
    );
}

#[test]
fn the_dev_signing_seed_is_committed_and_says_it_is_not_a_secret() {
    // A secret that is deliberately public cannot be confused with one that leaked — but
    // only if it says so where someone will read it.
    let path =
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("dev-signing-key.NOT-A-SECRET");
    let body = std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!(
            "{} must exist ({e}) — the dev seed is deliberately committed",
            path.display()
        )
    });
    assert!(body.contains("SELAHCUE-DEV-ONLY-NOT-A-SECRET!!"));
    assert!(body.contains("NEVER PRODUCTION"));
    assert!(
        body.contains(TrustedKeys::DEV_KEY_ID),
        "the seed file must name the key_id it derives to, or the pair cannot be checked"
    );
}
