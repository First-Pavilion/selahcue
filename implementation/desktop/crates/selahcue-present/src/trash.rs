//! Bounded retention for deleted decks — the seam that makes "undo delete" honest.
//!
//! Deleting a presentation used to be final: the deck was dropped from the library and its row
//! removed from the store in the same step, so nothing above could offer an undo. A client-side
//! undo could only recreate an **empty deck with the same name**, which is a lie about what was
//! restored — the slides, elements, theme and notes were already gone.
//!
//! ## Why this is here and not in the operator crate
//!
//! Decks are operator-owned by design and the host deliberately has no deck store; that is not
//! being changed. But the risky part of an undo is the **retention buffer**, and
//! `selahcue-operator` is excluded from the workspace, so a buffer living there would be tested
//! by nothing. The bounded container therefore lives in this crate, where it gets real tests;
//! `DeckLibrary` holds one and owns the persistence.
//!
//! ## Bounded on two axes, deliberately
//!
//! A byte budget alone admits unboundedly many tiny decks, which unbounds lookup cost; an entry
//! cap alone admits a handful of enormous ones. Both are enforced, and a deck too large to
//! retain at all is **refused outright** rather than evicting the entire buffer to make room for
//! something that still would not fit.

use crate::deck::{DeckId, SlideDeck};
use std::collections::VecDeque;

/// How many deleted decks are retained. Small on purpose: this is an undo affordance for an
/// accidental delete, not an archive.
pub const MAX_TRASH_ENTRIES: usize = 8;

/// Total retained deck bytes.
///
/// Sized so it can actually BIND. A *maximal* deck measures **2 010 940 bytes** serialized
/// (500 slides each carrying the full 4 000-character notes allowance) — measured, not
/// estimated. A budget at or above that could never be exceeded by any legal deck, which would
/// make the refusal path unreachable and its test vacuous: a guard no workload can trip is a
/// guard no test can verify. At 1.5 MB the byte budget genuinely binds, and since it caps the
/// TOTAL, retained memory here can never exceed it regardless of entry count.
pub const MAX_TRASH_BYTES: usize = 1_536 * 1024;

/// The largest a legal deck can serialize to, measured (`MAX_DECK_SLIDES` slides × the full
/// `MAX_NOTES_LEN` notes allowance). Used only to keep the budget honest, below.
const MAX_LEGAL_DECK_BYTES: usize = 2_010_940;

/// The cap must leave room for eviction to be observable — with fewer than two entries a test
/// cannot tell "evicted the oldest" from "never stored anything". Pinned here so lowering the
/// cap breaks the build rather than silently making the eviction tests vacuous.
const _: () = assert!(MAX_TRASH_ENTRIES >= 2);

/// The byte budget must comfortably hold a realistic deck, or the buffer would refuse everything
/// and the "refused" tests would pass against a mechanism that never retains anything at all.
const _: () = assert!(MAX_TRASH_BYTES >= 64 * 1024);

/// ...and it must stay BELOW the largest legal deck, or no deck could ever be refused, the
/// refusal branch would be dead code, and the test that exercises it would silently prove
/// nothing. Raising the budget past this must break the build and force a rethink, not quietly
/// retire a guard.
const _: () = assert!(MAX_TRASH_BYTES < MAX_LEGAL_DECK_BYTES);

/// One retained deck plus its measured size.
///
/// The size is measured **once, on insert** (deletes are rare and operator-driven) and stored, so
/// eviction never re-serializes and the running total cannot drift from what was actually added.
#[derive(Debug, Clone)]
struct TrashEntry {
    deck: SlideDeck,
    bytes: usize,
}

/// A bounded FIFO of recently deleted decks.
#[derive(Debug, Clone, Default)]
pub struct DeckTrash {
    entries: VecDeque<TrashEntry>,
    bytes: usize,
}

impl DeckTrash {
    pub fn new() -> Self {
        DeckTrash {
            entries: VecDeque::new(),
            bytes: 0,
        }
    }

    /// Retain a deleted deck, evicting the oldest entries until both caps hold.
    ///
    /// `bytes` is the deck's **serialized** size, measured by the caller. This crate deliberately
    /// does not serialize it here: `selahcue-present` is a normal dependency of
    /// `selahcue-import`, whose dependency graph is guarded as a security property because it
    /// parses hostile documents (`scripts/import_guards.sh`). Pulling a JSON serializer in here
    /// to measure a deck would have propagated one into that crate. The deck-owning library
    /// already serializes decks to persist them, so it measures the representation it is about
    /// to write anyway. A caller that cannot serialize a deck must pass `usize::MAX`, which
    /// refuses retention — safe, where counting it as zero would let unbounded content in under
    /// a byte budget of zero.
    ///
    /// Returns `false` when the deck is too large to retain **at all**, in which case nothing is
    /// stored and nothing already retained is evicted — a single oversized deck must not empty
    /// the buffer to make room for something that still would not fit. A caller that gets
    /// `false` must not offer an undo, because there is nothing to restore.
    pub fn push(&mut self, deck: SlideDeck, bytes: usize) -> bool {
        if bytes > MAX_TRASH_BYTES {
            return false;
        }
        // A re-deleted id must not appear twice; the newer copy wins.
        self.remove_id(deck.id());
        self.entries.push_back(TrashEntry { deck, bytes });
        self.bytes = self.bytes.saturating_add(bytes);
        while self.entries.len() > MAX_TRASH_ENTRIES || self.bytes > MAX_TRASH_BYTES {
            match self.entries.pop_front() {
                Some(old) => self.bytes = self.bytes.saturating_sub(old.bytes),
                None => break,
            }
        }
        true
    }

    /// The retained deck with `id`, if it is still retained.
    ///
    /// Deliberately a **per-id** accessor rather than a count: a global "how many are retained"
    /// lets one deck's presence mask another's absence, so a test asking "is MY deck still
    /// there?" could pass on someone else's entry.
    pub fn peek(&self, id: DeckId) -> Option<&SlideDeck> {
        self.entries
            .iter()
            .find(|e| e.deck.id() == id)
            .map(|e| &e.deck)
    }

    /// Remove and return the retained deck with `id` (the restore path).
    pub fn take(&mut self, id: DeckId) -> Option<SlideDeck> {
        let i = self.entries.iter().position(|e| e.deck.id() == id)?;
        let entry = self.entries.remove(i)?;
        self.bytes = self.bytes.saturating_sub(entry.bytes);
        Some(entry.deck)
    }

    fn remove_id(&mut self, id: DeckId) {
        if let Some(i) = self.entries.iter().position(|e| e.deck.id() == id) {
            if let Some(old) = self.entries.remove(i) {
                self.bytes = self.bytes.saturating_sub(old.bytes);
            }
        }
    }

    /// How many decks are retained.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Total retained bytes, as measured on insert.
    pub fn retained_bytes(&self) -> usize {
        self.bytes
    }

    /// The retained deck ids, oldest first — for an undo affordance that lists what it can
    /// actually restore rather than guessing.
    pub fn ids(&self) -> Vec<DeckId> {
        self.entries.iter().map(|e| e.deck.id()).collect()
    }
}
