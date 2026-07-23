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
}

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
        });
        id
    }

    /// Insert an item at `index` (clamped to the end), returning its new id.
    pub fn insert_item(&mut self, index: usize, kind: ItemKind, title: impl Into<String>) -> ItemId {
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
