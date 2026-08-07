//! The media library (Design 2.0 "Presentation & Media", Figma node 329:124): a bounded
//! registry of imported media assets — images, video, and audio — referenced by authored
//! slide decks (FR-003 reusable media refs). Pure and deterministic: the registry holds only
//! metadata (kind, size, dimensions/duration), never file bytes, and never touches the
//! filesystem itself — missing-file detection takes an **injected existence probe** so the
//! domain stays I/O-free and exhaustively testable (the data layer supplies the real probe).
//!
//! Bounded by [`MAX_MEDIA_ASSETS`] and [`MAX_MEDIA_PATH_LEN`] (no-leak). Rendering video/audio
//! on the audience output is a later capability (ADR-0020) — the registry lists those kinds
//! now (the design shows `.mp4`/`.wav` entries) so the library is complete ahead of playback.
//!
//! Like the rest of [`selahcue-core`](crate), this module is **dependency-free** (no serde):
//! the data layer maps a [`MediaAsset`] to structured `media_asset` columns (mirroring
//! `plan_repo`), and [`MediaKind`] carries a stable string tag ([`MediaKind::as_tag`] /
//! [`MediaKind::from_tag`]) for that column, exactly like `ItemKind`.

/// Upper bound on the number of assets in one library (no-leak): the registry, its
/// persistence, and any usage scan stay bounded regardless of how much the operator imports.
pub const MAX_MEDIA_ASSETS: usize = 1000;

/// Upper bound on a single asset's path length **in bytes** (no-leak): a host-local media path
/// is short; this caps the persisted/snapshotted registry so a pathological path cannot grow it
/// without limit. Kept equal to `selahcue_engine::scene::MediaRef::CAP` (1024 bytes) so a path
/// that fits the library also fits the `MediaRef` a slide holds — the two never disagree on
/// which paths are representable (see [`MediaLibrary::import`]).
pub const MAX_MEDIA_PATH_LEN: usize = 1024;

/// The class of a media asset. Carries a stable string tag for persistence.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum MediaKind {
    /// A still image (PNG/JPG…) — the only kind the engine renders today.
    Image,
    /// A video clip — listed now; audience-output playback is a later slice (ADR-0020).
    Video,
    /// An audio track — listed now; playback is a later slice (ADR-0020).
    Audio,
}

impl MediaKind {
    /// The stable string tag for the `media_asset.kind` column (mirrors `ItemKind::as_tag`).
    pub fn as_tag(self) -> &'static str {
        match self {
            MediaKind::Image => "image",
            MediaKind::Video => "video",
            MediaKind::Audio => "audio",
        }
    }

    /// Parse a [`MediaKind`] from its [`as_tag`](MediaKind::as_tag) string; unknown tags →
    /// `None` (the repo drops an unrecognised row rather than guessing).
    pub fn from_tag(tag: &str) -> Option<Self> {
        match tag {
            "image" => Some(MediaKind::Image),
            "video" => Some(MediaKind::Video),
            "audio" => Some(MediaKind::Audio),
            _ => None,
        }
    }
}

/// A stable per-library asset id, assigned on import and never reused within a library.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct MediaId(pub u64);

/// One imported media asset's **metadata** (never its bytes). `path` is a host-local
/// reference the render/decode layer resolves; a `path` that no longer exists is reported by
/// [`MediaLibrary::missing`], never crashes anything.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MediaAsset {
    /// Stable id within the owning library.
    pub id: MediaId,
    /// Host-local path/reference to the file (bounded by [`MAX_MEDIA_PATH_LEN`]).
    pub path: String,
    /// Image / video / audio.
    pub kind: MediaKind,
    /// File size in bytes (for the library's storage accounting).
    pub size_bytes: u64,
    /// Pixel width, when known (images/video); `None` persists as a NULL column.
    pub width: Option<u32>,
    /// Pixel height, when known (images/video); `None` persists as a NULL column.
    pub height: Option<u32>,
    /// Duration in milliseconds, when known (video/audio); `None` persists as a NULL column.
    pub duration_ms: Option<u32>,
    /// Import time as epoch milliseconds — **caller-supplied** (the core takes no clock), so
    /// the domain stays deterministic and testable.
    pub imported_at: u64,
}

impl MediaAsset {
    /// Whether this asset is within its content bounds (no-leak): the path is capped at
    /// [`MAX_MEDIA_PATH_LEN`] bytes.
    pub fn within_bounds(&self) -> bool {
        self.path.len() <= MAX_MEDIA_PATH_LEN
    }
}

/// A bounded registry of [`MediaAsset`]s with stable ids and storage accounting.
///
/// Import is **idempotent by path**: re-importing the same file returns the existing id
/// instead of adding a duplicate row, so the storage total and usage scan stay correct when
/// the operator drops the same asset onto more than one slide.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct MediaLibrary {
    assets: Vec<MediaAsset>,
    /// The next id to assign — monotonic, never reused (mirrors `ServicePlan::next_id`).
    next_id: u64,
}

impl MediaLibrary {
    /// An empty library. The first imported asset gets id `1`.
    pub fn new() -> Self {
        MediaLibrary {
            assets: Vec::new(),
            next_id: 1,
        }
    }

    /// The assets in import order.
    pub fn assets(&self) -> &[MediaAsset] {
        &self.assets
    }

    /// The number of assets.
    pub fn len(&self) -> usize {
        self.assets.len()
    }

    /// Whether the library is empty.
    pub fn is_empty(&self) -> bool {
        self.assets.is_empty()
    }

    /// Register a media asset, returning its id. **Idempotent by path**: an existing asset
    /// with the same `path` is returned unchanged (its id), never duplicated. Returns `None`
    /// (rejects) when the library is full ([`MAX_MEDIA_ASSETS`]) or the `path` is empty or
    /// longer than [`MAX_MEDIA_PATH_LEN`] — the registry never grows past its bound.
    #[allow(clippy::too_many_arguments)]
    pub fn import(
        &mut self,
        path: impl Into<String>,
        kind: MediaKind,
        size_bytes: u64,
        width: Option<u32>,
        height: Option<u32>,
        duration_ms: Option<u32>,
        imported_at: u64,
    ) -> Option<MediaId> {
        // Normalize exactly like `MediaRef::new` (trim + reject NUL + byte cap) so a library
        // path and the `MediaRef` a slide holds key IDENTICALLY — otherwise a whitespace- or
        // over-long-path asset would be stored under a different key than the slide's reference
        // and `media_usage`/`get_by_path` would misclassify a live asset as unused.
        let path = path.into();
        let path = path.trim().to_string();
        if path.is_empty() || path.contains('\0') || path.len() > MAX_MEDIA_PATH_LEN {
            return None;
        }
        if let Some(existing) = self.assets.iter().find(|a| a.path == path) {
            return Some(existing.id);
        }
        if self.assets.len() >= MAX_MEDIA_ASSETS {
            return None;
        }
        let id = MediaId(self.next_id);
        self.next_id += 1;
        self.assets.push(MediaAsset {
            id,
            path,
            kind,
            size_bytes,
            width,
            height,
            duration_ms,
            imported_at,
        });
        Some(id)
    }

    /// The asset with `id`, if present.
    pub fn get(&self, id: MediaId) -> Option<&MediaAsset> {
        self.assets.iter().find(|a| a.id == id)
    }

    /// The asset whose `path` matches, if present.
    pub fn get_by_path(&self, path: &str) -> Option<&MediaAsset> {
        self.assets.iter().find(|a| a.path == path)
    }

    /// Remove the asset with `id`; returns `true` if one was removed. Ids are never reused,
    /// so a removed asset's id stays retired.
    pub fn remove(&mut self, id: MediaId) -> bool {
        let before = self.assets.len();
        self.assets.retain(|a| a.id != id);
        self.assets.len() != before
    }

    /// Total size of all assets in bytes (saturating) — the library's storage accounting
    /// ("1.2 GB of media").
    pub fn total_bytes(&self) -> u64 {
        self.assets
            .iter()
            .fold(0u64, |acc, a| acc.saturating_add(a.size_bytes))
    }

    /// The ids of assets whose file is **missing**, per an injected existence probe
    /// `exists(path) -> bool` (the data layer supplies the real filesystem check). Pure and
    /// deterministic — the same library + probe always yields the same list, in import order.
    pub fn missing<F: Fn(&str) -> bool>(&self, exists: F) -> Vec<MediaId> {
        self.assets
            .iter()
            .filter(|a| !exists(&a.path))
            .map(|a| a.id)
            .collect()
    }

    /// Whether every asset is within its content bounds and the count is within
    /// [`MAX_MEDIA_ASSETS`] (no-leak).
    pub fn within_bounds(&self) -> bool {
        self.assets.len() <= MAX_MEDIA_ASSETS && self.assets.iter().all(MediaAsset::within_bounds)
    }

    /// Rehydrate a library from persisted assets (the repo layer). `next_id` is derived as one
    /// past the largest id, so newly-imported assets never collide with a persisted id even
    /// though `next_id` itself is not stored.
    pub fn from_assets(assets: Vec<MediaAsset>) -> Self {
        // Saturating: `core` must never panic (a u64::MAX persisted id would overflow `+ 1` in a
        // debug build). At the cap of MAX_MEDIA_ASSETS this is unreachable in practice, but the
        // never-panic rule holds for any input, including a tampered persisted row.
        let next_id = assets
            .iter()
            .map(|a| a.id.0)
            .max()
            .map_or(1, |m| m.saturating_add(1));
        MediaLibrary { assets, next_id }
    }
}
