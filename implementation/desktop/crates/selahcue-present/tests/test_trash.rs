//! Bounded deck retention: undo-delete must restore the REAL deck, and the buffer that makes
//! that possible must not grow without limit.
//!
//! This is the case `CLAUDE.md`'s bounded-memory section is about — a retention buffer fed by an
//! operator action. Every test here asserts the **entity** (a named deck present or absent, or
//! the entry count) rather than a proxy like total bytes, because a byte figure can look
//! healthy while the wrong deck is the one that survived.

#![allow(clippy::unwrap_used)]

use selahcue_present::{DeckId, DeckTrash, SlideDeck, MAX_TRASH_BYTES, MAX_TRASH_ENTRIES};

/// The premises these tests rest on, re-pinned at the point of use. `CLAUDE.md` asks for the
/// compile-time assert beside the constant *and* inside the test: changing a cap must break the
/// build rather than quietly turn an eviction test into an assertion about a buffer that never
/// evicts, or an over-cap test into one that refuses everything.
const _: () = assert!(MAX_TRASH_ENTRIES >= 2);
const _: () = assert!(MAX_TRASH_BYTES >= 64 * 1024);
/// A maximal deck measures 2 010 940 bytes, so the budget must stay below that for the refusal
/// test to exercise anything at all.
const _: () = assert!(MAX_TRASH_BYTES < 2_010_940);

/// A deck with `slides` slides and a stable id, so tests can name the exact entity they expect.
fn deck(id: u64, name: &str, slides: usize) -> SlideDeck {
    let mut d = SlideDeck::new(name);
    d.set_id(DeckId(id));
    for _ in 0..slides {
        d.add_slide();
    }
    d
}

/// The byte budget must bind **independently of the entry cap**.
///
/// This test exists because removing the byte cap entirely SURVIVED the rest of this file: every
/// other deck here is a few hundred bytes, so the total never came near the budget and only the
/// entry cap was ever doing any work. Three ~600 KB decks exceed the budget while staying well
/// under `MAX_TRASH_ENTRIES`, so an eviction here can only have come from the byte budget.
#[test]
fn the_byte_budget_evicts_large_decks_before_the_entry_cap_is_reached() {
    const LARGE_DECKS: usize = 3;
    const _: () = assert!(LARGE_DECKS < MAX_TRASH_ENTRIES);

    // Each is 40% of the whole budget, so three cannot coexist but three ENTRIES are well under
    // the entry cap — an eviction here can only have come from the byte budget.
    let each = MAX_TRASH_BYTES * 2 / 5;
    const _: () = assert!(LARGE_DECKS >= 3);
    let mut trash = DeckTrash::new();
    for i in 1..=LARGE_DECKS as u64 {
        assert!(
            trash.push(deck(i, &format!("Big {i}"), 1), each),
            "premise: each large deck must be individually retainable"
        );
    }
    assert!(
        each * LARGE_DECKS > MAX_TRASH_BYTES,
        "premise: the three together must actually exceed the budget, or nothing forces an \
         eviction and this test proves nothing"
    );
    assert!(
        trash.len() < LARGE_DECKS,
        "the byte budget must have forced an eviction — the entry cap cannot have, since \
         {LARGE_DECKS} entries is under the cap of {MAX_TRASH_ENTRIES}"
    );
    assert!(trash.retained_bytes() <= MAX_TRASH_BYTES);
    assert_eq!(
        trash.peek(DeckId(1)),
        None,
        "the OLDEST large deck must be the one dropped"
    );
    assert!(
        trash.peek(DeckId(LARGE_DECKS as u64)).is_some(),
        "the newest must survive"
    );
}

#[test]
fn a_deleted_deck_is_retained_with_its_real_content() {
    let mut trash = DeckTrash::new();
    assert!(trash.push(deck(1, "Sermon", 5), 1_000));

    let kept = trash
        .peek(DeckId(1))
        .expect("the deleted deck must still be retrievable, or undo can only fake it");
    assert_eq!(kept.name, "Sermon");
    assert_eq!(
        kept.len(),
        5,
        "undo must restore the SLIDES too — an empty deck of the same name is a lie \
         about what was restored"
    );
}

#[test]
fn taking_a_deck_out_removes_it_from_retention() {
    let mut trash = DeckTrash::new();
    trash.push(deck(1, "Sermon", 2), 1_000);
    let restored = trash.take(DeckId(1)).expect("premise: it was retained");
    assert_eq!(restored.name, "Sermon");
    assert_eq!(
        trash.peek(DeckId(1)),
        None,
        "a restored deck must leave the trash, or a second undo would duplicate it"
    );
    assert_eq!(trash.len(), 0);
    assert_eq!(trash.retained_bytes(), 0, "its bytes must be released too");
}

/// Entry-count bound, asserted by NAMED KEY rather than by length alone: a count of
/// `MAX_TRASH_ENTRIES` proves nothing about *which* deck survived, and the whole risk is
/// evicting the wrong one.
#[test]
fn the_entry_count_is_bounded_and_the_oldest_is_the_one_evicted() {
    let mut trash = DeckTrash::new();
    for i in 0..(MAX_TRASH_ENTRIES as u64 + 3) {
        assert!(trash.push(deck(i + 1, &format!("Deck {i}"), 1), 1_000));
    }

    assert_eq!(
        trash.len(),
        MAX_TRASH_ENTRIES,
        "retention must be capped by ENTRY COUNT, not only by bytes — a byte budget alone \
         admits unboundedly many tiny decks and unbounds lookup cost"
    );
    assert_eq!(
        trash.peek(DeckId(1)),
        None,
        "the OLDEST deck must be the one evicted"
    );
    let newest = DeckId(MAX_TRASH_ENTRIES as u64 + 3);
    assert!(
        trash.peek(newest).is_some(),
        "the NEWEST deck must survive eviction — asserting the count alone would pass even \
         if eviction dropped the wrong end"
    );
}

/// Byte bound. The positive control matters as much as the bound: without it, "refused" is
/// indistinguishable from a buffer that retains nothing at all.
#[test]
fn an_oversized_deck_is_refused_and_leaves_retention_intact() {
    let mut trash = DeckTrash::new();
    trash.push(deck(1, "Keeper", 3), 1_000);
    let bytes_before = trash.retained_bytes();
    assert!(
        trash.peek(DeckId(1)).is_some(),
        "positive control: a benign deck IS retained, so a later refusal is a real decision \
         and not a dead mechanism"
    );

    // A deck whose serialized form exceeds the whole budget.
    // Refusal must be inert: one byte past the budget changes nothing at all.
    assert!(
        !trash.push(deck(3, "One byte over", 1), MAX_TRASH_BYTES + 1),
        "one byte past the budget must be refused"
    );
    assert_eq!(
        trash.peek(DeckId(3)),
        None,
        "and must not be partially retained"
    );
    assert!(
        trash.peek(DeckId(1)).is_some(),
        "refusing an oversized deck must NOT evict what was already retained — clearing the \
         buffer to make room for something that still would not fit loses real work"
    );
    assert_eq!(trash.retained_bytes(), bytes_before);

    // The other half of the boundary, on a fresh buffer: a deck of EXACTLY the budget is legal.
    // It needs its own buffer because retaining it legitimately evicts everything else — which
    // is correct behaviour, not the refusal this test is about.
    let mut exact = DeckTrash::new();
    assert!(
        exact.push(deck(4, "Exactly at cap", 1), MAX_TRASH_BYTES),
        "a deck of exactly the budget must be retainable — an off-by-one here would refuse \
         the largest legal case"
    );
    assert!(
        exact.peek(DeckId(4)).is_some(),
        "and it must really be there, not merely reported as accepted"
    );
}

/// Both caps hold together under sustained churn — the shape a real session produces.
#[test]
fn retention_stays_within_both_caps_under_sustained_deletes() {
    let mut trash = DeckTrash::new();
    for i in 0..500u64 {
        trash.push(deck(i + 1, &format!("Deck {i}"), 3), 1_000);
        assert!(
            trash.len() <= MAX_TRASH_ENTRIES,
            "entry cap breached at iteration {i}"
        );
        assert!(
            trash.retained_bytes() <= MAX_TRASH_BYTES,
            "byte cap breached at iteration {i}"
        );
    }
    assert_eq!(trash.len(), MAX_TRASH_ENTRIES);
    assert_eq!(
        trash.peek(DeckId(500)).map(|d| d.name.clone()),
        Some("Deck 499".to_string()),
        "the most recent delete must always be the one undo can reach"
    );
}

/// Deleting the same id twice must not retain it twice — otherwise the buffer holds duplicate
/// copies of one deck, wasting the budget and making `take` ambiguous.
#[test]
fn re_deleting_the_same_id_keeps_one_copy_and_it_is_the_newer_one() {
    let mut trash = DeckTrash::new();
    trash.push(deck(7, "First", 1), 1_000);
    let after_first = trash.retained_bytes();
    trash.push(deck(7, "Second", 1), 1_000);

    assert_eq!(trash.len(), 1, "one id, one retained copy");
    assert_eq!(
        trash.peek(DeckId(7)).map(|d| d.name.clone()),
        Some("Second".to_string()),
        "the newer copy must win"
    );
    assert!(
        trash.retained_bytes() <= after_first + 8,
        "the superseded copy's bytes must be released, not double-counted: {} vs {}",
        trash.retained_bytes(),
        after_first
    );
    assert_eq!(trash.take(DeckId(7)).map(|d| d.name), Some("Second".into()));
    assert_eq!(trash.take(DeckId(7)), None, "only one copy existed");
}

#[test]
fn ids_lists_exactly_what_undo_can_restore() {
    let mut trash = DeckTrash::new();
    trash.push(deck(1, "A", 1), 1_000);
    trash.push(deck(2, "B", 1), 1_000);
    assert_eq!(trash.ids(), vec![DeckId(1), DeckId(2)], "oldest first");
    trash.take(DeckId(1));
    assert_eq!(
        trash.ids(),
        vec![DeckId(2)],
        "an affordance built on this must never offer to restore a deck that has gone"
    );
}
