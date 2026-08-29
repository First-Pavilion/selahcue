//! The service-plan domain model (FR-001, FR-002).
//!
//! A [`ServicePlan`] is an ordered run sheet of [`PlanItem`]s. This module owns
//! the pure domain rules — creation, editing, reordering, duplication, and
//! planned-time roll-up — with stable per-item ids. Persistence and UI live in
//! other crates; this layer has no I/O.

/// The kinds of item a service plan can contain (FR-002).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ItemKind {
    SlideGroup,
    Song,
    Scripture,
    Media,
    Announcement,
    Timer,
    /// A non-triggerable divider used to group the run sheet.
    Section,
}

impl ItemKind {
    /// Stable string tag for persistence/serialization (not the display label).
    pub fn as_tag(&self) -> &'static str {
        match self {
            ItemKind::SlideGroup => "slide_group",
            ItemKind::Song => "song",
            ItemKind::Scripture => "scripture",
            ItemKind::Media => "media",
            ItemKind::Announcement => "announcement",
            ItemKind::Timer => "timer",
            ItemKind::Section => "section",
        }
    }

    /// Inverse of [`ItemKind::as_tag`]. Returns `None` for an unknown tag.
    pub fn from_tag(tag: &str) -> Option<ItemKind> {
        Some(match tag {
            "slide_group" => ItemKind::SlideGroup,
            "song" => ItemKind::Song,
            "scripture" => ItemKind::Scripture,
            "media" => ItemKind::Media,
            "announcement" => ItemKind::Announcement,
            "timer" => ItemKind::Timer,
            "section" => ItemKind::Section,
            _ => return None,
        })
    }
}

/// A stable identifier for an item within a plan (unique for the plan's lifetime,
/// never reused after removal).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct ItemId(pub u64);

/// One stanza of a song: the lines shown together on ONE slide (story S8-1).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Stanza {
    pub lines: Vec<String>,
}

/// The coordinator's CHOSEN verse-number treatment for a scripture slide (FR-029 · Design 2.0
/// inspector, "Verse numbers" — Superscript / Inline / Hidden). `None` on a link = the plan
/// default.
///
/// **Carried, not yet applied — and no renderer reads it.** This value round-trips through the
/// wire and through persistence so the inspector can hold the operator's choice, but nothing
/// composes a slide from it: `scripture_slide_in` still prefixes the verse number on a
/// multi-verse passage and omits it on a single one, whichever variant is stored. Setting it
/// changes what is saved and what the UI shows as selected. It does not change what the
/// audience sees.
///
/// **There is no ticket for the renderer half yet.** Saying so plainly rather than writing
/// "later": FR-029 is MVP in the PRD and its "verse numbers formatted per setting" clause is
/// unbuilt, so whoever picks this up should raise that ticket first rather than assume one
/// exists. The wire and persistence half is 86ajy0hw0, which is this change and is done.
///
/// The variant docs below describe the TYPOGRAPHIC INTENT each option will carry when a
/// renderer is written. They are a specification for that work, not a description of current
/// behaviour.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VerseNumbers {
    /// Intent: raised, smaller than the verse text (the default typographic convention).
    Superscript,
    /// Intent: full-size, on the same baseline as the verse text.
    Inline,
    /// Intent: not rendered at all.
    Hidden,
}

impl VerseNumbers {
    /// Stable string tag for persistence/serialization (not the display label).
    pub fn as_tag(&self) -> &'static str {
        match self {
            VerseNumbers::Superscript => "superscript",
            VerseNumbers::Inline => "inline",
            VerseNumbers::Hidden => "hidden",
        }
    }

    /// Inverse of [`VerseNumbers::as_tag`]. Returns `None` for an unknown tag.
    pub fn from_tag(tag: &str) -> Option<VerseNumbers> {
        Some(match tag {
            "superscript" => VerseNumbers::Superscript,
            "inline" => VerseNumbers::Inline,
            "hidden" => VerseNumbers::Hidden,
            _ => return None,
        })
    }
}

/// Whether a plan item's linked content resolves — **as far as the layer doing the asking
/// can tell**. The third state is the point of this type.
///
/// Decks and media are **operator-owned by design**: the host has no deck store and
/// `selahcue-app` does not depend on `selahcue-data`, so the host structurally cannot answer
/// "does deck 17 still exist?". A two-state answer would force it to say `false` — "not
/// missing" — for a link it never checked, and a UI reading that as "fine" is exactly the
/// absent-equals-fine failure this model exists to prevent. [`Unknown`] lets the host decline
/// to answer, so the operator's local resolution stays authoritative for decks and media
/// while the host stays authoritative for scripture (which it can always parse).
///
/// [`Unknown`]: LinkResolution::Unknown
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinkResolution {
    /// Checked, and the link resolves.
    Resolved,
    /// Checked, and the link does **not** resolve — the passage no longer parses, or the
    /// deck/media asset is gone.
    Missing,
    /// **Not** checked: the asking layer cannot see the library this link points into.
    /// Never conflate this with [`Resolved`](LinkResolution::Resolved).
    Unknown,
}

impl LinkResolution {
    /// Interpret an existence probe: `Some(true)`/`Some(false)` = checked, `None` = the
    /// probing layer cannot answer.
    pub fn from_probe(probe: Option<bool>) -> LinkResolution {
        match probe {
            Some(true) => LinkResolution::Resolved,
            Some(false) => LinkResolution::Missing,
            None => LinkResolution::Unknown,
        }
    }

    /// Stable string tag (not the display label).
    pub fn as_tag(&self) -> &'static str {
        match self {
            LinkResolution::Resolved => "resolved",
            LinkResolution::Missing => "missing",
            LinkResolution::Unknown => "unknown",
        }
    }
}

/// Hard cap on a link's stored display label, in CHARACTERS (no-leak rule). A label is a
/// human-facing deck name echoed into the run sheet, so a real one is a few dozen characters;
/// this only stops a buggy/hostile `SetItemContent` (or a hand-edited database row) from
/// parking an unbounded string on each of up to [`MAX_PLAN_ITEMS`] items. Over-long labels are
/// TRUNCATED rather than rejected: the label is decoration, and refusing to link a deck because
/// its name is long would be a worse failure than shortening the name.
pub const MAX_LINK_LABEL_LEN: usize = 120;

// Pinned beside the constant as well as in the tests: small enough that the truncation test
// really truncates, large enough that a real deck name is never touched. Moving it past either
// bound fails the build rather than quietly making the guard vacuous.
const _: () = assert!(MAX_LINK_LABEL_LEN >= 16 && MAX_LINK_LABEL_LEN <= 4096);

/// A content reference linked to a plan item — the passage a Scripture item shows,
/// the deck a Presentation (slide-group) item shows, or the asset a Media item
/// shows (FR-002 · ADR-0020 follow-up). `None` on a [`PlanItem`] = today's
/// title-only / stanza behaviour (an *unlinked* item).
///
/// Held with **core-visible primitives only** (a canonical reference `String`,
/// and plain `u64` ids that map to `present::DeckId` / `core::media::MediaId` at
/// the boundary) so this pure domain layer neither serializes a non-serde
/// [`crate::scripture::Reference`] nor depends upward on the presentation crate.
/// The reference is re-parsed on use via [`crate::scripture::parse_one`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ItemContent {
    /// A linked scripture passage: the canonical reference (e.g. `"Romans 8:28-30"`),
    /// an optional bundled-translation code (`None` = the plan's default), an optional
    /// verses-per-slide override, and an optional verse-numbers mode (FR-026 · FR-029).
    ///
    /// `verse_numbers` is **carried, not yet applied**: it round-trips through the wire and
    /// persistence so the inspector can hold the coordinator's choice, but the host's slide
    /// composition does not read it yet — `scripture_slide_in` still prefixes the verse number
    /// on a multi-verse passage and omits it on a single one, whatever the mode says.
    Scripture {
        reference: String,
        translation: Option<String>,
        verses_per_slide: Option<u16>,
        verse_numbers: Option<VerseNumbers>,
    },
    /// A linked presentation deck by its library id (maps to `present::DeckId`).
    /// `slide_count` is the deck's slide count as known by the deck-owning operator at link time
    /// (the host has no deck store, so it cannot derive it) — `None` for a legacy link or before
    /// the operator syncs it. It lets a deck presentation report its true slide count / stage a
    /// specific within-item slide (the Live Console slide picker) rather than collapsing to one slide.
    ///
    /// `label` is the deck's **last known good** display name, capped at
    /// [`MAX_LINK_LABEL_LEN`]. The deck-owning operator supplies it on every link and relink,
    /// and an update that omits it leaves the stored name alone, so it stays accurate while the
    /// deck exists and is the last name the deck had once it does not. A deck renamed IN PLACE
    /// keeps the older name until the item is next linked — propagating a rename to every plan
    /// that references the deck is not yet implemented. Without it a deleted deck can only be described by
    /// its id — the design calls for "\u{201c}Sunday Service \u{2014} Aug 4\u{201d} was deleted from the library",
    /// and once the library row is gone no layer can turn the id back into that name.
    Deck {
        deck_id: u64,
        slide_count: Option<u32>,
        label: Option<String>,
    },
    /// A linked media asset by its library id (maps to `core::media::MediaId`).
    Media { media_id: u64 },
}

/// Neutralise any control character (especially TAB/CR/LF) in a codec text field by replacing it
/// with a space. Fields are TAB-delimited, so a stray TAB in a value would shift the field
/// boundaries on [`ItemContent::decode`] and silently corrupt the round-trip (e.g. a wire-supplied
/// reference `"Romans 8:28\tKJV"` hijacking the translation field). Scripture references never
/// legitimately contain control characters, so this makes the "no TAB in a field" invariant true
/// rather than merely assumed.
fn sanitize_field(s: &str) -> String {
    s.chars()
        .filter(|c| !is_invisible_formatting(*c))
        .map(|c| if c.is_control() { ' ' } else { c })
        .collect()
}

/// Zero-width and bidirectional-override characters, which `char::is_control` does NOT cover:
/// it tests the Cc category only, and every character below is Cf.
///
/// These render as nothing yet reorder or hide the text around them, so a deck name can be made
/// to *display* as something other than what it is — a right-to-left override rewrites how a
/// name reads, and zero-width joiners let two distinct labels look identical. A link label is
/// echoed to every paired device and rendered in the run sheet, so it is a display-spoofing
/// surface. Dropped rather than replaced with a space, because they are zero-width by
/// definition: substituting a space would change how legitimate text looks, whereas removing
/// them restores what it already appeared to be. Found by security review of PR #13.
fn is_invisible_formatting(c: char) -> bool {
    matches!(c,
        '\u{200B}'..='\u{200F}'   // zero-width space/non-joiner/joiner, LRM, RLM
        | '\u{202A}'..='\u{202E}' // LRE, RLE, PDF, LRO, RLO
        | '\u{2060}'..='\u{2064}' // word joiner, invisible operators
        | '\u{2066}'..='\u{2069}' // LRI, RLI, FSI, PDI
        | '\u{FEFF}'              // BOM / zero-width no-break space
    )
}

/// Public form of [`sanitize_field`], for callers that must clean untrusted text BEFORE
/// validating it — the controller parses a scripture reference and stores what it parsed, so
/// sanitizing only on `encode` would let a bidi override ride on the wire and into the run
/// sheet while never reaching persistence. One implementation, so the two cannot drift.
///
/// Cleans ONLY -- it applies no length bound of any kind. A caller that also needs the value
/// bounded wants [`sanitize_label`]; one that calls this is responsible for its own limit.
/// Saying so explicitly because this doc block and `sanitize_label`'s were previously
/// transposed, leaving a public function documented as capping a length it never touched.
pub fn sanitize_text(s: &str) -> String {
    sanitize_field(s)
}

/// [`sanitize_field`] a display label AND bound it to [`MAX_LINK_LABEL_LEN`] characters.
/// Truncation is by CHARACTER, never by byte, so a multi-byte name can never be cut mid-scalar
/// (which would not round-trip). Applied on the way in and again on decode, so neither a hostile
/// wire value nor a hand-edited database row can park an unbounded string on a plan item.
fn sanitize_label(s: &str) -> String {
    sanitize_field(s).chars().take(MAX_LINK_LABEL_LEN).collect()
}

impl ItemContent {
    /// Serialize to a stable, reversible, single-line string for persistence
    /// (the data layer stores this opaque value in one column — keeping the codec
    /// pure and in the domain, with no serde in core). Fields are TAB-separated; text fields are
    /// [`sanitize_field`]-cleaned of control chars so the round-trip is always lossless.
    pub fn encode(&self) -> String {
        match self {
            ItemContent::Scripture {
                reference,
                translation,
                verses_per_slide,
                verse_numbers,
            } => format!(
                "scripture\t{}\t{}\t{}\t{}",
                sanitize_field(reference),
                translation
                    .as_deref()
                    .map(sanitize_field)
                    .unwrap_or_default(),
                verses_per_slide.map(|v| v.to_string()).unwrap_or_default(),
                verse_numbers.map(|n| n.as_tag()).unwrap_or_default(),
            ),
            ItemContent::Deck {
                deck_id,
                slide_count,
                label,
            } => format!(
                "deck\t{deck_id}\t{}\t{}",
                slide_count.map(|c| c.to_string()).unwrap_or_default(),
                label.as_deref().map(sanitize_label).unwrap_or_default(),
            ),
            ItemContent::Media { media_id } => format!("media\t{media_id}"),
        }
    }

    /// Inverse of [`ItemContent::encode`]. Total — any input returns `None` rather
    /// than panicking (it runs on persisted, possibly-corrupt data). An unparseable
    /// numeric id or an unknown tag yields `None` (the item loads unlinked).
    pub fn decode(s: &str) -> Option<ItemContent> {
        let mut parts = s.split('\t');
        match parts.next()? {
            "scripture" => {
                let reference = parts.next()?.to_string();
                let translation = parts.next().filter(|t| !t.is_empty()).map(str::to_string);
                let verses_per_slide = parts
                    .next()
                    .filter(|v| !v.is_empty())
                    .and_then(|v| v.parse().ok());
                // Back-compat: a pre-verse-numbers `scripture\t{ref}\t{tr}\t{vps}` (no fifth
                // field) decodes to `None`, and an unknown tag also decodes to `None` rather
                // than failing the whole link.
                let verse_numbers = parts
                    .next()
                    .filter(|n| !n.is_empty())
                    .and_then(VerseNumbers::from_tag);
                Some(ItemContent::Scripture {
                    reference,
                    translation,
                    verses_per_slide,
                    verse_numbers,
                })
            }
            "deck" => Some(ItemContent::Deck {
                deck_id: parts.next()?.parse().ok()?,
                // Back-compat: a legacy `deck\t{id}` (no third field) decodes to `None`.
                slide_count: parts
                    .next()
                    .filter(|c| !c.is_empty())
                    .and_then(|c| c.parse().ok()),
                // Back-compat: a pre-label `deck\t{id}\t{n}` (no fourth field) decodes to
                // `None`. Re-bounded here so a hand-edited row cannot smuggle in a huge label.
                label: parts.next().filter(|l| !l.is_empty()).map(sanitize_label),
            }),
            "media" => Some(ItemContent::Media {
                media_id: parts.next()?.parse().ok()?,
            }),
            _ => None,
        }
    }

    /// Whether this link resolves, from the point of view of the caller's libraries.
    ///
    /// `deck_exists` / `media_exists` return `Some(true)`/`Some(false)` when the caller CAN
    /// check, and **`None` when it cannot** — which is the host's situation for both, since
    /// decks and media are operator-owned and the host has no store for either. Scripture is
    /// always answerable here, because resolving it is a pure parse.
    pub fn resolve(
        &self,
        passage_exists: impl Fn(&str, Option<&str>) -> Option<bool>,
        deck_exists: impl Fn(u64) -> Option<bool>,
        media_exists: impl Fn(u64) -> Option<bool>,
    ) -> LinkResolution {
        match self {
            ItemContent::Scripture {
                reference,
                translation,
                ..
            } => {
                // A reference that does not even parse is missing without asking anyone.
                if crate::scripture::parse_one(reference).is_err() {
                    return LinkResolution::Missing;
                }
                // Parsing is SYNTAX only. `parse_one` accepts "Jude 2:1" (Jude has one chapter)
                // and "Romans 99:1" — well-formed references naming nothing. Whether a passage
                // yields any verse is a corpus question this pure layer cannot answer, so it is
                // probed exactly like a deck or a media asset. Treating "it parsed" as "it
                // resolves" reported an unpresentable passage as healthy — the absent-equals-fine
                // failure this type exists to prevent, on the one kind the host claims authority
                // over. The renderer already knows the state exists: `scripture_slide_in` falls
                // back to a bare title when the verse lookup comes back empty.
                LinkResolution::from_probe(passage_exists(reference, translation.as_deref()))
            }
            ItemContent::Deck { deck_id, .. } => LinkResolution::from_probe(deck_exists(*deck_id)),
            ItemContent::Media { media_id } => LinkResolution::from_probe(media_exists(*media_id)),
        }
    }
}

/// One ordered entry in a service plan.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlanItem {
    pub id: ItemId,
    pub kind: ItemKind,
    pub title: String,
    /// Planned duration in seconds, if the coordinator set one.
    pub planned_secs: Option<u32>,
    /// Responsible person/role, if assigned.
    pub owner: Option<String>,
    /// Stanza content (songs; slide-per-stanza). Empty = a title-only item,
    /// which is exactly the pre-8a behaviour for every existing item.
    pub stanzas: Vec<Stanza>,
    /// Optional per-item theme override — a built-in theme NAME (S8-3d). When set,
    /// the audience output renders THIS item on that template instead of the global
    /// theme; `None` = use the global theme (the pre-8-3d behaviour for every item).
    pub theme: Option<String>,
    /// Optional linked content — the scripture passage, deck, or media asset this
    /// item shows (ADR-0020 follow-up). `None` = an *unlinked* / title-only item,
    /// which is exactly the pre-content-reference behaviour for every existing item.
    pub content: Option<ItemContent>,
}

impl PlanItem {
    /// How many slides this item presents as (a title-only item is one slide). A deck-linked
    /// presentation reports the deck's slide count as synced by the operator (the host has no deck
    /// store); a legacy/unsynced deck link falls back to one slide until the operator syncs it.
    pub fn slide_count(&self) -> usize {
        match &self.content {
            Some(ItemContent::Deck {
                slide_count: Some(c),
                ..
            }) => (*c as usize).max(1),
            // A scripture link renders as a single passage slide (the presenter's `item_slide`
            // returns one scripture slide regardless of index), so it counts as one — even if the
            // item also carries stanzas. Otherwise the picker would advertise N slides that all
            // render the same passage, and LIVE/PREVIEW cursors would be meaningless for the item.
            Some(ItemContent::Scripture { .. }) => 1,
            _ => self.stanzas.len().max(1),
        }
    }
}

/// Parse the PD-hymn-friendly plain-text stanza format: stanzas are separated
/// by one or more blank lines; each non-blank run of lines is one stanza (one
/// slide). Whitespace-only lines count as blank; line ends may be \n or \r\n.
/// Pure and total — any input parses (possibly to zero stanzas).
pub fn stanzas_from_text(text: &str) -> Vec<Stanza> {
    let mut stanzas = Vec::new();
    let mut current: Vec<String> = Vec::new();
    for raw in text.lines() {
        let line = raw.trim_end_matches('\r');
        if line.trim().is_empty() {
            if !current.is_empty() {
                stanzas.push(Stanza {
                    lines: std::mem::take(&mut current),
                });
            }
        } else {
            current.push(line.trim().to_string());
        }
    }
    if !current.is_empty() {
        stanzas.push(Stanza { lines: current });
    }
    stanzas
}

/// Serialize stanzas back to the plain-text format (lossless round-trip with
/// [`stanzas_from_text`] for trimmed content): lines joined by newlines,
/// stanzas separated by one blank line.
pub fn stanzas_to_text(stanzas: &[Stanza]) -> String {
    stanzas
        .iter()
        .map(|s| s.lines.join("\n"))
        .collect::<Vec<_>>()
        .join("\n\n")
}

/// Hard cap on the number of items in a service plan (audit M1/M2 no-leak rule).
/// Far above any real run sheet (a large conference order is well under ~100 items),
/// so legitimate use never hits it — it only stops a buggy/hostile client loop of
/// remote `AddItem`s (or a corrupt/oversized persisted plan reloaded) from growing the
/// `items` Vec without bound. Enforced at the untrusted ingress (the controller's
/// `AddItem` handler) and on persistence load; the infallible domain `add_item`/
/// `insert_item` stay uncapped for trusted seeding/tests.
pub const MAX_PLAN_ITEMS: usize = 500;

/// An ordered run sheet.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ServicePlan {
    pub name: String,
    items: Vec<PlanItem>,
    next_id: u64,
}

/// A plan's planned-duration roll-up (FR-202) — the total, and how much of the plan it covers.
///
/// `secs` alone is not safe to display: a plan where only half the items carry a duration
/// produces a total that looks authoritative and is not. [`PlannedTotal::is_partial`] is what
/// lets the UI mark it, and it is computed in the same pass as the sum so the two cannot
/// disagree.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct PlannedTotal {
    /// Sum of every item's planned duration, saturating.
    pub secs: u32,
    /// How many items carried a duration and so contributed to `secs`.
    pub counted: usize,
    /// How many items could have carried a duration and did not. `secs` excludes them, so a
    /// non-zero value means the total is a FLOOR for the service, not its length.
    ///
    /// Inert [`ItemKind::Section`] dividers are excluded from this roll-up entirely — from
    /// `secs` and `counted` as well as from here. A divider is not a thing anyone schedules.
    pub unplanned: usize,
}

impl PlannedTotal {
    /// Whether `secs` omits at least one item that could have had a duration.
    pub fn is_partial(&self) -> bool {
        self.unplanned > 0
    }
}

/// Errors from plan mutations that reference a position or id.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PlanError {
    /// No item with the given id exists.
    NotFound(ItemId),
    /// A move referenced an out-of-bounds index.
    IndexOutOfBounds,
    /// The item's KIND cannot carry the value being set — today, only that an
    /// [`ItemKind::Section`] divider cannot be given an owner, a planned duration or a content
    /// link. A divider is an inert label that never fires, so it is not staffable, not
    /// schedulable and presents nothing.
    ///
    /// Refused rather than stored-and-ignored on purpose. Every summary metric excludes
    /// dividers, so a stored value would be invisible to the totals while still riding on the
    /// item view — producing one frame that reports `missing: 0` beside a row whose own link
    /// says `"missing"`. A contradiction inside a single frame is worse than a rejected edit.
    NotApplicable(ItemId),
}

impl ServicePlan {
    /// Create an empty plan.
    pub fn new(name: impl Into<String>) -> Self {
        ServicePlan {
            name: name.into(),
            items: Vec::new(),
            next_id: 1,
        }
    }

    /// Append an item, returning its new id.
    pub fn add_item(&mut self, kind: ItemKind, title: impl Into<String>) -> ItemId {
        let id = ItemId(self.next_id);
        self.next_id += 1;
        self.items.push(PlanItem {
            id,
            kind,
            title: title.into(),
            planned_secs: None,
            owner: None,
            stanzas: Vec::new(),
            theme: None,
            content: None,
        });
        id
    }

    /// Insert an item at `index` (clamped to the end), returning its new id.
    pub fn insert_item(
        &mut self,
        index: usize,
        kind: ItemKind,
        title: impl Into<String>,
    ) -> ItemId {
        let id = ItemId(self.next_id);
        self.next_id += 1;
        let idx = index.min(self.items.len());
        self.items.insert(
            idx,
            PlanItem {
                id,
                kind,
                title: title.into(),
                planned_secs: None,
                owner: None,
                stanzas: Vec::new(),
                theme: None,
                content: None,
            },
        );
        id
    }

    /// Remove an item by id. Returns the removed item, or `NotFound`.
    pub fn remove(&mut self, id: ItemId) -> Result<PlanItem, PlanError> {
        match self.items.iter().position(|i| i.id == id) {
            Some(pos) => Ok(self.items.remove(pos)),
            None => Err(PlanError::NotFound(id)),
        }
    }

    /// Move the item at `from` to index `to` (both bounded by the current length).
    pub fn reorder(&mut self, from: usize, to: usize) -> Result<(), PlanError> {
        let len = self.items.len();
        if from >= len || to >= len {
            return Err(PlanError::IndexOutOfBounds);
        }
        if from == to {
            return Ok(());
        }
        let item = self.items.remove(from);
        self.items.insert(to, item);
        Ok(())
    }

    /// Mutable access to an item by id.
    pub fn get_mut(&mut self, id: ItemId) -> Option<&mut PlanItem> {
        self.items.iter_mut().find(|i| i.id == id)
    }

    /// Set (or clear, with `None`) an item's per-item theme override (S8-3d).
    /// Returns `NotFound` if no item has that id.
    pub fn set_item_theme(&mut self, id: ItemId, theme: Option<String>) -> Result<(), PlanError> {
        match self.get_mut(id) {
            Some(item) => {
                item.theme = theme.filter(|t| !t.is_empty());
                Ok(())
            }
            None => Err(PlanError::NotFound(id)),
        }
    }

    /// Set (or clear, with `None`) an item's linked content — the scripture passage,
    /// deck, or media asset it shows (ADR-0020 follow-up). A `Scripture` link whose
    /// `reference` is blank is treated as *unlinked* (`None`), so an item can't be
    /// left half-linked. Returns `NotFound` if no item has that id.
    pub fn set_item_content(
        &mut self,
        id: ItemId,
        content: Option<ItemContent>,
    ) -> Result<(), PlanError> {
        self.refuse_on_divider(id, content.is_some())?;
        let normalized = match content {
            // Clean the reference and translation on the way IN, not only on `encode`. The
            // controller validates the parse and stores what it validated, so sanitizing at the
            // persistence boundary alone let a bidi override ride the wire into the run sheet
            // while never reaching disk. A blank reference is not a link, so the item cannot be
            // left half-linked.
            Some(ItemContent::Scripture {
                reference,
                translation,
                verses_per_slide,
                verse_numbers,
            }) => {
                let reference = sanitize_field(&reference);
                if reference.trim().is_empty() {
                    None
                } else {
                    Some(ItemContent::Scripture {
                        reference,
                        translation: translation.map(|t| sanitize_field(&t)),
                        verses_per_slide,
                        verse_numbers,
                    })
                }
            }
            // Bound the display label on the way IN, so the in-memory plan — not just its
            // persisted form — can never hold an unbounded string.
            Some(ItemContent::Deck {
                deck_id,
                slide_count,
                label,
            }) => {
                // "Last known good" only survives if an update that says NOTHING about the name
                // leaves it alone. This is a full replace, so an absent label must mean "I have
                // nothing new to say", not "forget it" — otherwise any re-link (syncing a slide
                // count, say) destroys the very name a deleted deck needs to be described by.
                // A relink to a DIFFERENT deck drops it: it is no longer that deck's name.
                let carried = match label {
                    // Blank is ABSENT, as it is for `set_item_owner`, a scripture reference and
                    // `set_item_theme`. Keying on `Option` alone stored `Some("")` and
                    // `Some("   ")` as real names — and the invisible-character filter turns a
                    // hostile all-zero-width label into `Some("")` too, which then rendered as
                    // `⚠ "" is missing`.
                    Some(l) if !sanitize_label(&l).trim().is_empty() => Some(sanitize_label(&l)),
                    // Falls through to the carry-forward below, so a blank update is treated as
                    // "nothing new to say" rather than as an erase.
                    Some(_) | None => self.get(id).and_then(|it| match &it.content {
                        Some(ItemContent::Deck {
                            deck_id: prev_id,
                            label: prev_label,
                            ..
                        }) if *prev_id == deck_id => prev_label.clone(),
                        _ => None,
                    }),
                };
                Some(ItemContent::Deck {
                    deck_id,
                    slide_count,
                    label: carried,
                })
            }
            other => other,
        };
        match self.get_mut(id) {
            Some(item) => {
                item.content = normalized;
                Ok(())
            }
            None => Err(PlanError::NotFound(id)),
        }
    }

    /// Set (or clear, with `None`) an item's responsible owner/role (FR-004). A blank string is
    /// treated as unassigned (`None`). Returns `NotFound` if no item has that id.
    pub fn set_item_owner(&mut self, id: ItemId, owner: Option<String>) -> Result<(), PlanError> {
        self.refuse_on_divider(id, owner.is_some())?;
        match self.get_mut(id) {
            Some(item) => {
                item.owner = owner.filter(|o| !o.trim().is_empty());
                Ok(())
            }
            None => Err(PlanError::NotFound(id)),
        }
    }

    /// Set (or clear, with `None`) an item's planned duration in seconds (FR-004).
    /// Returns `NotFound` if no item has that id.
    pub fn set_item_planned_secs(
        &mut self,
        id: ItemId,
        secs: Option<u32>,
    ) -> Result<(), PlanError> {
        self.refuse_on_divider(id, secs.is_some())?;
        match self.get_mut(id) {
            Some(item) => {
                item.planned_secs = secs;
                Ok(())
            }
            None => Err(PlanError::NotFound(id)),
        }
    }

    /// Item ids whose linked content **cannot be resolved** — the missing-content
    /// check run at plan open and pre-service (FR-007). Existence is injected (this
    /// layer has no I/O and no deck/media library): `deck_exists(id)` /
    /// `media_exists(id)` probe the presenting layer's libraries. A `Scripture` link
    /// is unresolved when its reference does not parse; an *unlinked* item (`None`)
    /// is never flagged. Pure and total.
    pub fn unresolved_content(
        &self,
        passage_exists: impl Fn(&str, Option<&str>) -> bool,
        deck_exists: impl Fn(u64) -> bool,
        media_exists: impl Fn(u64) -> bool,
    ) -> Vec<ItemId> {
        // One resolution rule, shared with [`ItemContent::resolve`]: a caller that CAN answer
        // both probes (this signature's `bool`) never sees `Unknown`, so "not resolved" and
        // "missing" coincide here — which is exactly what this method has always meant.
        self.items
            .iter()
            .filter(|it| {
                it.content.as_ref().is_some_and(|c| {
                    c.resolve(
                        |r, t| Some(passage_exists(r, t)),
                        |id| Some(deck_exists(id)),
                        |id| Some(media_exists(id)),
                    ) == LinkResolution::Missing
                })
            })
            .map(|it| it.id)
            .collect()
    }

    /// Refuse to put schedulable data on an inert divider. Clearing (`setting_a_value ==
    /// false`) is always allowed, so a legacy item can be cleaned up rather than being stuck.
    ///
    /// # What this covers, and what it does not
    ///
    /// It guards the three fields the SUMMARY reads — `owner`, `planned_secs` and `content` —
    /// because the invariant it exists to protect is that a summary can never contradict the
    /// rows beside it (`missing: 0` next to a row whose link says `"missing"`, `assigned: 0`
    /// next to a row showing an owner). [`ServicePlan::from_parts`] sweeps the same three on the
    /// load path, since rehydration is the one route that bypasses the setters.
    ///
    /// It does **not** cover `stanzas`. A divider can carry stanza content, on both paths:
    /// over the wire via `AddItem { kind: "section", content: Some(..) }`, which writes through
    /// `get_mut` rather than a setter, and across a save/reload, because the `from_parts` sweep
    /// clears the other three and not this one. Going live on such an item presents its body
    /// text.
    ///
    /// That is deliberately left open rather than overlooked. `stanzas` feeds **no** summary
    /// metric, so it cannot break the invariant above; and a divider was already presentable
    /// before any of this — nothing in staging or Go Live inspects `ItemKind`, and `item_slide`
    /// renders a title slide for any item. So the question "may a section present body text?"
    /// is a product decision about whether a divider is inert *by type*, not a defect in this
    /// guard. **It is not ticketed yet** — whoever acts on it should raise one. Stated that way
    /// deliberately: an id written before the ticket exists is a guess, and a wrong id in a
    /// source comment outlives the pull request that introduced it and reads as authoritative.
    ///
    /// Note also that `get_mut` and `PlanItem`'s public fields bypass this guard for the other
    /// three fields just as readily; the coverage is uniform, not lopsided. Sealing that means
    /// routing the two `selahcue-app` writes (`controller.rs` `AddItem` and `RenameItem`)
    /// through setters first — `get_mut` cannot simply be narrowed to `pub(crate)`, because
    /// those callers live in a different crate and it would not compile.
    ///
    /// Worth knowing when that is scoped: `stanzas` and `title` are bounded only by the 64 KiB
    /// LAN frame cap and [`MAX_PLAN_ITEMS`], so a hostile authenticated Operator has roughly a
    /// 31 MiB worst case, against the 120 characters a link label is held to.
    fn refuse_on_divider(&self, id: ItemId, setting_a_value: bool) -> Result<(), PlanError> {
        match self.get(id) {
            Some(item) if setting_a_value && item.kind == ItemKind::Section => {
                Err(PlanError::NotApplicable(id))
            }
            // A missing id is reported by the caller's own `NotFound` path, so it passes here.
            _ => Ok(()),
        }
    }

    /// Read access to an item by id.
    pub fn get(&self, id: ItemId) -> Option<&PlanItem> {
        self.items.iter().find(|i| i.id == id)
    }

    /// The items in order.
    pub fn items(&self) -> &[PlanItem] {
        &self.items
    }

    /// Number of items.
    pub fn len(&self) -> usize {
        self.items.len()
    }

    /// Whether the plan has no items.
    pub fn is_empty(&self) -> bool {
        self.items.is_empty()
    }

    /// Total planned duration in seconds across items that have one (saturating,
    /// so a pathological plan can never overflow/panic).
    ///
    /// Prefer [`ServicePlan::planned_total`] wherever the caller DISPLAYS this number: on its
    /// own it cannot say whether it covers the whole plan.
    pub fn planned_total_secs(&self) -> u32 {
        self.planned_total().secs
    }

    /// The planned-duration roll-up: the total **and whether it covers every item** (FR-202 ·
    /// PLAN-SECTIONS-DURATIONS-spec §4.2).
    ///
    /// Both come out of ONE pass deliberately. A completeness flag derived separately from the
    /// sum it describes drifts the moment either side changes, and the drift is silent — a
    /// total that reads as the whole service when it is really a floor.
    ///
    /// # This total is load-bearing for the operator console, in a way nothing here enforces
    ///
    /// The operator console does not trust this number on sight. `planSummaryIsSound` in
    /// `selahcue-operator/dist/app.js` RECOMPUTES it from the rows it was sent and rejects the
    /// whole summary when the two disagree. Its recomputation sums `planned_secs` over **every**
    /// item, sections included; this one **excludes** sections (the settled rule that a divider
    /// is not part of the run sheet).
    ///
    /// The two therefore agree for exactly one reason: **a section can never hold a duration.**
    /// [`ServicePlan::set_item_planned_secs`] refuses to set one and [`ServicePlan::from_parts`]
    /// strips any an older build stored. Relax either and the sums diverge.
    ///
    /// What makes that worth a comment is the failure mode. Nothing breaks loudly: the console
    /// simply stops trusting a correct summary and silently falls back to computing its own,
    /// so the Plan Summary panel keeps rendering plausible numbers that are no longer the
    /// host's. No panic, no error, no failing test. `a_section_with_a_duration_would_break_the_
    /// operators_summary_validation_seam` in `tests/test_plan.rs` is the tripwire; the mirror
    /// of this note sits beside the check in `app.js`. The two must move together.
    pub fn planned_total(&self) -> PlannedTotal {
        let mut t = PlannedTotal::default();
        for item in &self.items {
            // A Section is a DIVIDER, not an item, so it is excluded from the roll-up
            // entirely — it contributes no duration and creates no gap. The design draws this
            // directly: node 608:875 shows "6 items" and "Total time 0:53:12" over a run sheet
            // of six rows and three dividers, and the total is not marked partial. Counting a
            // divider as a missing duration would mark every sectioned plan partial, and a
            // warning that is always on is one coordinators learn to ignore.
            if item.kind == ItemKind::Section {
                continue;
            }
            match item.planned_secs {
                Some(secs) => {
                    t.secs = t.secs.saturating_add(secs);
                    t.counted = t.counted.saturating_add(1);
                }
                None => t.unplanned = t.unplanned.saturating_add(1),
            }
        }
        t
    }

    /// The next id the plan will assign — needed to persist and faithfully
    /// rehydrate the no-reuse invariant.
    pub fn next_id(&self) -> u64 {
        self.next_id
    }

    /// Rehydrate a plan from persisted parts (used by the persistence layer).
    /// `next_id` must exceed every item id to preserve the no-reuse invariant;
    /// it is clamped up to `max(item id) + 1` if a smaller value is passed.
    pub fn from_parts(name: impl Into<String>, items: Vec<PlanItem>, next_id: u64) -> Self {
        let min_next = items.iter().map(|i| i.id.0).max().map_or(1, |m| m + 1);
        // Sweep anything a pre-guard build (or a hand-edited row) stored on a divider. The
        // setters refuse it now, but rehydration is the one path that bypasses them, and the
        // invariant has to hold for data as well as for edits — otherwise the summary silently
        // disagrees with a row it is looking straight at.
        let items: Vec<PlanItem> = items
            .into_iter()
            .map(|mut it| {
                if it.kind == ItemKind::Section {
                    // The same three fields `refuse_on_divider` guards on the command path, and
                    // for the same reason: these are what the summary reads. `stanzas` is
                    // deliberately NOT swept here — see that method's doc. Keep the two lists
                    // identical: a sweep that covers fewer fields than the setters refuse would
                    // let a save/reload reintroduce exactly what an edit is not allowed to set.
                    it.owner = None;
                    it.planned_secs = None;
                    it.content = None;
                }
                it
            })
            .collect();
        ServicePlan {
            name: name.into(),
            items,
            next_id: next_id.max(min_next),
        }
    }

    /// A deep, independent copy with a new name (FR-005). Ids are preserved but
    /// the copy has its own id counter, so future additions never collide.
    pub fn duplicate(&self, new_name: impl Into<String>) -> ServicePlan {
        ServicePlan {
            name: new_name.into(),
            items: self.items.clone(),
            next_id: self.next_id,
        }
    }
}

/// Longest permitted service-plan NAME, in characters.
///
/// `ServicePlan.name` was previously unbounded because every writer was trusted seeding or a
/// rename of an item (not the plan). The publish/hand-off commands (FR-006) create and rename
/// whole plans from the untrusted wire, so the name needs the same bound every other
/// wire-reachable string has. Matched to [`MAX_LINK_LABEL_LEN`]: both are one-line display
/// labels shown in the same run-sheet header, and a plan title far shorter than this is already
/// unreadable in the UI.
pub const MAX_PLAN_NAME_LEN: usize = 120;

/// Whether `name` is acceptable as a service-plan name arriving from the untrusted wire:
/// non-empty after trimming, within [`MAX_PLAN_NAME_LEN`] characters, and free of BOTH control
/// characters and [`is_invisible_formatting`] characters.
///
/// # Both categories, because one is not enough
///
/// `char::is_control` tests the Cc category ONLY. Every character this file already classifies
/// as display-spoofing — zero-width spaces and joiners, bidi overrides and isolates, the BOM —
/// is Cf, so a rule built on `is_control` alone lets all of them through. That gap was real
/// here: a right-to-left override made a plan name display as something other than what it is,
/// and a "title" consisting solely of U+200B passed the non-blank check while rendering as
/// empty. Both reach every paired device through the run sheet. Found by security review of
/// PR #14, and the same class the PR #13 review found on link labels.
///
/// This consumes `is_invisible_formatting` rather than restating the character ranges, so the
/// list has ONE definition. A second copy is the thing that drifts the next time a character is
/// added to it.
///
/// # Refused here, dropped in the codec — deliberately different
///
/// [`sanitize_field`] REMOVES these characters, because the codec must be total: it processes
/// values that are already stored and has nobody to report a failure to. This is untrusted
/// INGRESS creating a new document, so it can do the more honest thing and refuse — the same
/// choice the NDI source name makes. A name quietly rewritten between the request and the run
/// sheet is a name the coordinator cannot search for later.
///
/// Counted in CHARACTERS, not bytes — a bound in bytes would refuse a legitimate name in a
/// non-Latin script at a third of the length a Latin one is allowed. Non-Latin names are
/// otherwise untouched by this rule and there is a test saying so, because a spoofing guard that
/// quietly excluded most of the world's scripts would be a worse bug than the one it fixes.
///
/// # Known cost: multi-person emoji are refused
///
/// U+200D (zero-width joiner) is what binds an emoji sequence together, so a plan named
/// "Sunday 👨‍👩‍👧" is refused. That is a real usability cost and it is accepted deliberately:
/// permitting U+200D is exactly the homograph hole this closes, and the alternative — silently
/// dropping it, as the codec does — would mangle the sequence into three separate people
/// without saying so. Single emoji carry no joiner and are unaffected.
pub fn plan_name_valid(name: &str) -> bool {
    let trimmed = name.trim();
    !trimmed.is_empty()
        && trimmed.chars().count() <= MAX_PLAN_NAME_LEN
        && !trimmed
            .chars()
            .any(|c| c.is_control() || is_invisible_formatting(c))
}

/// A named starter template — a run-sheet skeleton a coordinator begins a service from
/// (FR-005 "save as template"; the `Template` action on the empty-plan frame `611:124`).
///
/// # These entries are PROVISIONAL
///
/// No document in this repository says what a template contains. `UX-STATE-MATRIX.md:108`,
/// `SERVICE-PLAN-2.0-HANDOFF.md:74` and `COMPONENT-SPECS.md:192` each name the *action* three
/// different ways and none of them describes a template's content, where templates are stored,
/// or which ones ship. The two below are modelled on this repository's own `demo_plan()` —
/// the only service shape the product has ever committed to — so the mechanism can ship and be
/// tested. **The set and its contents are a product decision, not an engineering one**; they
/// live in this one table so changing them is a data edit rather than a code change.
///
/// The host REPORTS this list on the operator view (`plan_templates`) rather than the client
/// hardcoding it, for the same reason `themes` and `translations` are reported: a client that
/// transcribes the host's list drifts from it silently the first time either side changes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PlanTemplate {
    /// Stable id used on the wire (`TemplatePlan { template }`). Never displayed.
    pub id: &'static str,
    /// Default display name, used when the caller supplies no name of its own.
    pub name: &'static str,
    /// The ordered skeleton. Titles are placeholders the coordinator renames.
    pub items: &'static [(ItemKind, &'static str)],
}

impl PlanTemplate {
    /// Build a fresh, independent plan from this template under `name`.
    ///
    /// Uses the infallible domain `add_item`, which is correct here precisely because a
    /// template is *trusted, in-process seed data* — not wire input. The item count is fixed by
    /// the table above and asserted against [`MAX_PLAN_ITEMS`] at compile time below, so no
    /// template can ever seed a plan past the cap that the untrusted ingress enforces.
    pub fn build(&self, name: impl Into<String>) -> ServicePlan {
        let mut plan = ServicePlan::new(name);
        for (kind, title) in self.items {
            plan.add_item(*kind, *title);
        }
        plan
    }
}

/// The starter templates this build offers, in the order a picker should show them.
pub const PLAN_TEMPLATES: &[PlanTemplate] = &[
    PlanTemplate {
        id: "sunday-morning",
        name: "Sunday Morning",
        items: &[
            (ItemKind::Announcement, "Welcome"),
            (ItemKind::Song, "Opening Song"),
            (ItemKind::Scripture, "Scripture Reading"),
            (ItemKind::Section, "Sermon"),
            (ItemKind::Song, "Closing Song"),
        ],
    },
    PlanTemplate {
        id: "midweek",
        name: "Midweek Gathering",
        items: &[
            (ItemKind::Announcement, "Welcome"),
            (ItemKind::Song, "Worship"),
            (ItemKind::Section, "Teaching"),
            (ItemKind::Section, "Prayer"),
        ],
    },
];

/// No template may seed a plan that already breaches the cap the untrusted ingress enforces.
///
/// Pinned at COMPILE time rather than in a test: a template added to the table above is a data
/// edit, and the person making it should be stopped by the compiler rather than by a test they
/// may not think to run. Checks the LARGEST template, so adding a big one fails the build.
const _: () = {
    let mut i = 0;
    while i < PLAN_TEMPLATES.len() {
        assert!(
            PLAN_TEMPLATES[i].items.len() <= MAX_PLAN_ITEMS,
            "a starter template must not exceed MAX_PLAN_ITEMS"
        );
        i += 1;
    }
};

/// The template with this id, or `None` for an unknown one.
pub fn plan_template(id: &str) -> Option<&'static PlanTemplate> {
    PLAN_TEMPLATES.iter().find(|t| t.id == id)
}

// Tests live in `tests/test_plan.rs` (public-API integration tests).
