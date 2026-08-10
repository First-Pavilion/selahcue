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
    /// an optional bundled-translation code (`None` = the plan's default), and an
    /// optional verses-per-slide override (FR-026 · FR-029).
    Scripture {
        reference: String,
        translation: Option<String>,
        verses_per_slide: Option<u16>,
    },
    /// A linked presentation deck by its library id (maps to `present::DeckId`).
    /// `slide_count` is the deck's slide count as known by the deck-owning operator at link time
    /// (the host has no deck store, so it cannot derive it) — `None` for a legacy link or before
    /// the operator syncs it. It lets a deck presentation report its true slide count / stage a
    /// specific within-item slide (the Live Console slide picker) rather than collapsing to one slide.
    Deck {
        deck_id: u64,
        slide_count: Option<u32>,
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
        .map(|c| if c.is_control() { ' ' } else { c })
        .collect()
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
            } => format!(
                "scripture\t{}\t{}\t{}",
                sanitize_field(reference),
                translation
                    .as_deref()
                    .map(sanitize_field)
                    .unwrap_or_default(),
                verses_per_slide.map(|v| v.to_string()).unwrap_or_default(),
            ),
            ItemContent::Deck {
                deck_id,
                slide_count,
            } => format!(
                "deck\t{deck_id}\t{}",
                slide_count.map(|c| c.to_string()).unwrap_or_default()
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
                Some(ItemContent::Scripture {
                    reference,
                    translation,
                    verses_per_slide,
                })
            }
            "deck" => Some(ItemContent::Deck {
                deck_id: parts.next()?.parse().ok()?,
                // Back-compat: a legacy `deck\t{id}` (no third field) decodes to `None`.
                slide_count: parts
                    .next()
                    .filter(|c| !c.is_empty())
                    .and_then(|c| c.parse().ok()),
            }),
            "media" => Some(ItemContent::Media {
                media_id: parts.next()?.parse().ok()?,
            }),
            _ => None,
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

/// Errors from plan mutations that reference a position or id.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PlanError {
    /// No item with the given id exists.
    NotFound(ItemId),
    /// A move referenced an out-of-bounds index.
    IndexOutOfBounds,
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
        let normalized = match content {
            Some(ItemContent::Scripture { reference, .. }) if reference.trim().is_empty() => None,
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
        deck_exists: impl Fn(u64) -> bool,
        media_exists: impl Fn(u64) -> bool,
    ) -> Vec<ItemId> {
        self.items
            .iter()
            .filter(|it| match &it.content {
                Some(ItemContent::Scripture { reference, .. }) => {
                    crate::scripture::parse_one(reference).is_err()
                }
                Some(ItemContent::Deck { deck_id, .. }) => !deck_exists(*deck_id),
                Some(ItemContent::Media { media_id }) => !media_exists(*media_id),
                None => false,
            })
            .map(|it| it.id)
            .collect()
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
    pub fn planned_total_secs(&self) -> u32 {
        self.items
            .iter()
            .filter_map(|i| i.planned_secs)
            .fold(0u32, u32::saturating_add)
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

// Tests live in `tests/test_plan.rs` (public-API integration tests).
