//! How a presentation link survives a machine boundary (ClickUp 86ak196cr · `FINDING-LIB-07` ·
//! `RULE-LIB-XFER-01`).
//!
//! # The defect this exists to prevent
//!
//! A plan item links a presentation by [`ItemContent::Deck`]`{ deck_id }`, and that number is a
//! counter that starts at 1 **inside each machine's own library**. Machine A's deck 3 and
//! machine B's deck 3 are unrelated presentations. A plan that carried the bare number from A to B
//! and looked it up on B would not fail: it would show B's deck 3 on the audience output, with
//! nothing on the operator console to say anything was wrong.
//!
//! # The rule
//!
//! A deck link that leaves a machine carries a [`DeckUid`] — a random 128-bit identity minted once
//! per presentation and stored with it — and **never** the local number. On import the receiving
//! library is asked "which of my presentations has this uid?":
//!
//! - one does: the link is bound to **that** local deck ([`DeckLinkMatch::Matched`]);
//! - none does, or the uid is absent or malformed: the link is bound to
//!   [`UNRESOLVED_DECK_ID`], a number no library ever assigns, so the operator sees the existing
//!   missing-content state (FR-007 / FR-070) before the service ([`DeckLinkMatch::NotInLibrary`]).
//!
//! There is no third outcome and no fallback to the foreign number: [`import_deck_link`] cannot
//! return a `deck_id` that did not come out of the receiving library's own uid lookup (or the
//! sentinel). That is the whole guarantee, and it is why the function takes a lookup closure
//! instead of a list of ids.
//!
//! Pure and total — no I/O, no panics on hostile input (it runs on bundle contents a stranger
//! wrote). The library that owns the uids lives in `selahcue-operator`; this layer holds only the
//! rule and the types, so the rule is tested by `cargo test --workspace`.

use crate::plan::{sanitize_label, ItemContent, MAX_LINK_LABEL_LEN};

/// The local deck number of a link that resolves to **no** presentation.
///
/// `0` is the "unassigned" `DeckId` (`selahcue_present::DeckId(0)`): every library mints from 1 and
/// self-heals any deck loaded with `0`, so no stored deck ever answers to it and a lookup of it is
/// always the missing-content state.
pub const UNRESOLVED_DECK_ID: u64 = 0;

/// Number of hex digits in a [`DeckUid`] (128 bits).
pub const DECK_UID_HEX_LEN: usize = 32;

/// A presentation's globally distinguishable identity.
///
/// 128 random bits, written as exactly [`DECK_UID_HEX_LEN`] lowercase hexadecimal digits. There is
/// **one** spelling of each identity — upper-case or padded input is refused rather than folded —
/// so two strings are the same deck if and only if they are byte-equal, and no spelling trick can
/// make a hostile bundle's uid compare unequal to the real one in one place and equal in another.
///
/// The all-zero value is refused: it is what an uninitialised buffer looks like, and a library
/// that minted it would hand every such deck the same identity.
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct DeckUid(String);

impl DeckUid {
    /// The canonical form of `s`, or `None` if it is not exactly 32 lowercase hex digits or is all
    /// zero. The length is checked first, so a hostile megabyte-long "uid" costs one comparison.
    pub fn parse(s: &str) -> Option<DeckUid> {
        if s.len() != DECK_UID_HEX_LEN {
            return None;
        }
        if !s.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f')) {
            return None;
        }
        if s.bytes().all(|b| b == b'0') {
            return None;
        }
        Some(DeckUid(s.to_string()))
    }

    /// The uid for 128 random bits, or `None` for the all-zero buffer.
    pub fn from_bytes(bytes: [u8; 16]) -> Option<DeckUid> {
        const HEX: &[u8; 16] = b"0123456789abcdef";
        if bytes.iter().all(|b| *b == 0) {
            return None;
        }
        let mut out = String::with_capacity(DECK_UID_HEX_LEN);
        for b in bytes {
            out.push(char::from(HEX[usize::from(b >> 4)]));
            out.push(char::from(HEX[usize::from(b & 0x0f)]));
        }
        Some(DeckUid(out))
    }

    /// The canonical text form.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Display for DeckUid {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

/// A presentation link as it travels between machines: the identity, never the local number.
///
/// `uid` is a raw string on purpose. On the import side it comes from a file a stranger wrote and
/// is validated in exactly one place ([`import_deck_link`]); on the export side `None` means the
/// exporting library could not name the deck (it had been deleted), which travels as "this
/// presentation is not identifiable" rather than as a guess.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PortableDeckLink {
    /// The deck's identity, or `None` when the exporter could not identify it.
    pub uid: Option<String>,
    /// The deck's slide count on the exporting machine. A hint only: it is dropped on import,
    /// because the receiving machine's copy of the deck may have a different number of slides.
    pub slide_count: Option<u32>,
    /// The deck's last known name on the exporting machine — what the operator is told is
    /// missing when the deck is not in the receiving library.
    pub label: Option<String>,
}

/// What the receiving library knows about the deck a uid names.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LocalDeck {
    /// The deck's number in the **receiving** library.
    pub id: u64,
    /// Its slide count there.
    pub slide_count: u32,
    /// Its name there.
    pub name: String,
}

/// How an imported deck link was bound.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeckLinkMatch {
    /// The receiving library holds the presentation with that uid; the link now points at it.
    Matched,
    /// It does not (or the link could not name one): the link is the missing-content state.
    NotInLibrary,
}

/// The portable form of a deck link, for export. `None` if `content` is not a deck link.
///
/// `uid_of` is the **exporting** library's answer to "what is the identity of local deck `id`?";
/// it returns `None` for a deck the library no longer holds, and the link then travels
/// unidentified (so it can only ever import as missing — never as someone else's deck).
pub fn export_deck_link(
    content: &ItemContent,
    uid_of: impl Fn(u64) -> Option<DeckUid>,
) -> Option<PortableDeckLink> {
    let ItemContent::Deck {
        deck_id,
        slide_count,
        label,
    } = content
    else {
        return None;
    };
    Some(PortableDeckLink {
        // The sentinel is "no presentation", so it never has an identity — asking the library
        // would only invite a lookup that a buggy `uid_of` could answer.
        uid: (*deck_id != UNRESOLVED_DECK_ID)
            .then(|| uid_of(*deck_id))
            .flatten()
            .map(|u| u.as_str().to_string()),
        slide_count: *slide_count,
        label: label.clone(),
    })
}

/// Bind an imported deck link to the **receiving** library, or to the missing-content state.
///
/// `find_by_uid` is the receiving library's own lookup: it returns the local deck that carries the
/// uid, or `None`. It is the only source of a returned `deck_id`; the exporter's local number is
/// not an input at all (see the module docs). A uid that is absent, malformed, or answered with
/// the [`UNRESOLVED_DECK_ID`] sentinel is treated as not found.
///
/// The returned link carries the **local** deck's name and slide count when matched, and the
/// imported (bounded, sanitised) name when not — that name is what "'Communion' is missing" is
/// built from.
pub fn import_deck_link(
    link: &PortableDeckLink,
    find_by_uid: impl Fn(&DeckUid) -> Option<LocalDeck>,
) -> (ItemContent, DeckLinkMatch) {
    let found = link
        .uid
        .as_deref()
        .and_then(DeckUid::parse)
        .and_then(|uid| find_by_uid(&uid))
        .filter(|local| local.id != UNRESOLVED_DECK_ID);
    match found {
        Some(local) => (
            ItemContent::Deck {
                deck_id: local.id,
                slide_count: Some(local.slide_count),
                label: clean_label(&local.name),
            },
            DeckLinkMatch::Matched,
        ),
        None => (
            ItemContent::Deck {
                deck_id: UNRESOLVED_DECK_ID,
                slide_count: None,
                label: link.label.as_deref().and_then(clean_label),
            },
            DeckLinkMatch::NotInLibrary,
        ),
    }
}

/// How many characters of an incoming label are even looked at: a few times the stored bound, so
/// cleaning (which can only shrink a label) still has room to fill it, and no more. Without this a
/// label the size of the whole file would be copied in full just to keep its first 120 characters.
const LABEL_SCAN_CHARS: usize = MAX_LINK_LABEL_LEN * 4;

/// A display label made safe to store: control and display-hostile characters removed, bounded to
/// [`MAX_LINK_LABEL_LEN`] characters, and `None` when nothing visible is left (a blank name is no
/// name, as for every other optional text on a plan item). Only the first [`LABEL_SCAN_CHARS`]
/// characters are examined, so the work and the transient memory are independent of the input's
/// length.
fn clean_label(raw: &str) -> Option<String> {
    let head: String = raw.chars().take(LABEL_SCAN_CHARS).collect();
    let cleaned = sanitize_label(&head);
    (!cleaned.trim().is_empty()).then_some(cleaned)
}
