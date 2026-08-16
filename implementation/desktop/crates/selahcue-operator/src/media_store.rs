//! The **app-owned media store** — where imported image bytes actually live on disk, and the
//! staging-then-atomic-commit protocol that puts them there (ADR-0024 decision 4;
//! `IMPORT-presentation-design.md` §8.2–8.6; threat model blockers **B1** and **B4**).
//!
//! Until now SelahCue had no media store at all: [`MediaLibrary`] recorded *metadata* about files
//! sitting wherever the operator picked them, `media_repo` had no production caller, and the
//! registry was therefore rebuilt empty at every launch. That is survivable while every media path
//! is a file the user already owns and can find again; it is not survivable for imported images,
//! which exist nowhere else — without a store they vanish the moment the app closes. This module
//! introduces both halves: the on-disk root at `<app_data>/media/`, and the [`save`]/[`load`] pair
//! that finally wires `media_repo` so the registry survives a restart.
//!
//! Three properties are load-bearing and each is a merge gate:
//!
//! 1. **No filesystem path is ever derived from archive content (B1).** There is deliberately no
//!    parameter anywhere in this module through which a name from a `.pptx` — an entry name, a
//!    relationship target, an `<a:blip>` attribute — could reach a path. Staged files are named by
//!    slot index; committed files are named `import-<n>.<ext>` where `<ext>` comes from a
//!    [`MediaFormat`] *enum* the caller obtained by sniffing magic bytes, never from a string.
//!    Zip-slip, absolute paths, Windows device names and case-folding collisions are therefore
//!    absent by construction rather than filtered — but each still gets a test, because a structural
//!    rule is only as good as its enforcement.
//! 2. **Nothing is visible until commit (B4).** Staged bytes live under
//!    `<app_data>/media/.staging/<import-id>/` and are seen by nothing else. Abort, cancellation,
//!    timeout or a dropped [`ImportStaging`] removes that directory and leaves the media root
//!    byte-identical; a directory left behind by a crash is removed by [`sweep_stale_staging`] at
//!    the next launch.
//! 3. **A failure is scoped to the file it happened to.** One slot failing to commit is reported as
//!    that slot's failure and the rest still land — the caller turns it into a report line and the
//!    import continues. Disk-full mid-import degrades to a text-only deck plus an honest report,
//!    never to a failed import or, worse, a deck referencing media that is not there (§8.4).
//!
//! Like `DeckLibrary`, **persistence here is best-effort**: a database error is swallowed, because
//! losing the registry must never block editing. Losing the *files* is a different matter, which is
//! why file errors are typed and surfaced per slot rather than swallowed.

// DELETE THIS ALLOW once every item below has a caller. The operator is a *binary* crate, so `pub`
// exempts nothing from `dead_code`, and its clippy gate is `-D warnings`; this module lands complete
// and is consumed piecemeal (the import commands take most of it; `is_app_owned` is unreachable until
// `DeckWorkspace::remove_media` learns to ask it). `#[expect]` cannot be used instead: `--all-targets`
// compiles the bin both with and without `cfg(test)`, and the tests below already exercise this API,
// so the lint fires in one build and not the other.
#![allow(dead_code)] // wired into main.rs / remove_media as the import lands (ADR-0024)

use selahcue_core::media::{MediaAsset, MediaLibrary, MAX_MEDIA_ASSETS, MAX_MEDIA_PATH_LEN};
use selahcue_data::{media_repo, Database};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

/// The media root's directory name under the app data dir. A constant rather than a literal because
/// [`is_app_owned`] and [`sweep_stale_staging`] must agree with the writer about where "app-owned"
/// begins — a divergence would either strand files or, worse, let a delete escape the root.
pub const MEDIA_DIR: &str = "media";

/// The staging area's directory name *inside* the media root. Dot-prefixed so a user browsing their
/// media folder does not see half-imported files, and nested inside the root so a staged file and
/// its committed destination are always on the same filesystem — which is what makes the commit a
/// rename rather than a copy, and therefore atomic per file.
pub const STAGING_DIR: &str = ".staging";

/// `<app_data>/media` — the app-owned media root. Every file this module creates lives directly
/// inside it (or, before commit, inside its staging area).
pub fn media_root(app_data: &Path) -> PathBuf {
    app_data.join(MEDIA_DIR)
}

/// `<app_data>/media/.staging` — the parent of every per-import staging directory. Owned entirely by
/// this module: nothing else may write here, which is what lets [`sweep_stale_staging`] remove its
/// whole contents without inspecting them.
pub fn staging_root(app_data: &Path) -> PathBuf {
    media_root(app_data).join(STAGING_DIR)
}

/// The image format a committed file is named after — **the decode seam's own type**, re-exported
/// through `selahcue-present`.
///
/// This used to be a second enum declared here, with its own `Png`/`Jpeg` variants and its own copy
/// of `extension()`. Two enums with identical variants and no conversion between them agree only by
/// the order someone happened to write them in: nothing catches a third format being added to one
/// and not the other, or the variants being reordered, and the symptom would be an image saved
/// under the wrong extension — a file the operator's own tools then refuse to open, with no error
/// anywhere to explain it. There is one seam that decides what an image is, so there is one type
/// that says so.
///
/// It matters that this is an **enum and not a string**. The extension is the one part of a
/// committed filename that varies with the file's content, so it is the one place archive content
/// could plausibly leak into a path. A closed enum the caller can only obtain by sniffing magic
/// bytes has no representable value carrying `../`, a drive letter, a NUL or a 4 KiB name — so B1
/// holds by typing rather than by validation, and a new format is a compile-error-guided change.
pub use selahcue_present::ImageFormat as MediaFormat;

/// A staged image's handle: its index within this import, and nothing else.
///
/// The pure importer never learns a path — it stages bytes, gets a slot back, and puts the slot in
/// the element it is building; the shell resolves slots to real paths only *after* the commit
/// succeeds. That indirection is what keeps `selahcue-import` free of filesystem knowledge, and it
/// is also why an import that is abandoned mid-parse has nothing to undo.
///
/// # The contract this shares with `selahcue_import::MediaSlot`, and why it is written down
///
/// There are two slot types across this seam — the importer's and this one — and **they are the
/// same numbering**: slot *n* is the *n*-th image staged, counting from zero, in the order
/// `MediaSink::stage` was called. Nothing in the type system says so, and if the two ever disagree
/// the symptom is not an error but the wrong photograph on the wrong slide, which no test of
/// either side alone would catch.
///
/// So the contract is stated here and pinned by
/// [`slots_are_consecutive_from_zero_and_resolve_to_their_own_bytes`], which is the test that would
/// fail if this side's numbering ever drifted — including across a failed slot in the middle, the
/// case where an index-based mapping silently shifts by one.
///
/// A typed conversion between the two is the right end state and it belongs with the wiring: it
/// requires this crate to depend on `selahcue-import`, which is a dependency-graph change to the
/// shipped operator binary and therefore part of the import feature's own security review, not a
/// change to smuggle in ahead of it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct MediaSlot(pub usize);

/// Why a media-store operation failed.
///
/// Hand-rolled with a manual `Display` + [`std::error::Error`] — the house pattern (`ParseError` in
/// `selahcue-core::scripture`); the tree carries no `thiserror`/`anyhow`.
///
/// [`MediaStoreError::Io`] deliberately carries only [`std::io::ErrorKind`] and never the underlying
/// [`std::io::Error`] or a path. That makes the enum `Copy`/`Eq` (so a report can hold and compare
/// it), and — more importantly — makes it **impossible to leak a filesystem path into a log or a
/// user-facing string**, which ADR-0011 and FR-082 redaction require of anything touching imported
/// user content (design §15).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum MediaStoreError {
    /// The filesystem refused the operation; the kind is kept, the path is not.
    Io(std::io::ErrorKind),
    /// This import already holds [`MAX_MEDIA_ASSETS`] staged images, so a further one could never be
    /// registered even if it committed. Scoped to the image, never to the import (§8.6).
    Full,
    /// [`MAX_MEDIA_ASSETS`] candidate names in a row were already claimed. Unreachable while the
    /// media root is within its own cap; kept as a hard bound so the naming loop is provably finite
    /// rather than finite-in-practice.
    NameSpaceExhausted,
    /// The committed path would exceed [`MAX_MEDIA_PATH_LEN`], which is also
    /// `selahcue_engine::scene::MediaRef::CAP`. Caught here, before the file is claimed, because a
    /// path the store can write but a slide cannot reference is a silently unusable asset.
    PathTooLong,
    /// The app data directory is not valid UTF-8, so the path cannot be stored in a
    /// [`MediaAsset`]/`MediaRef`, both of which are `String`-typed. Refused rather than lossily
    /// converted — a mangled path would point at a file that does not exist.
    PathNotUtf8,
}

impl std::fmt::Display for MediaStoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            MediaStoreError::Io(std::io::ErrorKind::NotFound) => "the media folder is missing",
            MediaStoreError::Io(std::io::ErrorKind::PermissionDenied) => {
                "SelahCue isn't allowed to write to the media folder"
            }
            MediaStoreError::Io(_) => "the image couldn't be written to the media folder",
            MediaStoreError::Full => "the media library is full",
            MediaStoreError::NameSpaceExhausted => "the media folder has no free file name left",
            MediaStoreError::PathTooLong => "the media folder's path is too long to store an image",
            MediaStoreError::PathNotUtf8 => "the media folder's path can't be stored",
        };
        f.write_str(s)
    }
}

impl std::error::Error for MediaStoreError {}

/// One committed image: the slot it was staged under and where it finally landed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Committed {
    /// The slot the pure importer holds.
    pub slot: MediaSlot,
    /// The final path, as a `String` because that is what both [`MediaLibrary::import`] and the
    /// `MediaRef` a slide holds take — and because validating UTF-8 once, here, is better than
    /// having each caller guess at a lossy conversion.
    pub path: String,
    /// The file's size, for the library's storage accounting.
    pub size_bytes: u64,
    /// The sniffed format the extension came from.
    pub format: MediaFormat,
}

/// One slot that could not be committed. The import continues; the caller turns this into a report
/// entry ("1 image couldn't be saved") rather than failing the whole deck (§8.4).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommitFailure {
    /// The slot that failed — so the report can say *which* picture is missing.
    pub slot: MediaSlot,
    /// Why, with no path in it.
    pub error: MediaStoreError,
}

/// The outcome of a commit: what landed and what did not. Never an `Err` as a whole — a commit that
/// saves nine images out of ten is a *partial* success, and collapsing it to a failure would throw
/// away nine files the user's deck references.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CommitResult {
    /// Committed slots, in staging order.
    pub committed: Vec<Committed>,
    /// Slots that failed, in staging order.
    pub failed: Vec<CommitFailure>,
}

impl CommitResult {
    /// The final path for `slot`, if it committed — the slot resolver the deck builder is handed
    /// after the media commit (design §8.4, §6).
    pub fn resolve(&self, slot: MediaSlot) -> Option<&str> {
        self.committed
            .iter()
            .find(|c| c.slot == slot)
            .map(|c| c.path.as_str())
    }
}

/// A staged file's retained metadata. Note what is **absent**: the bytes, and the path. The bytes
/// are written straight through to disk and never held; the path is recomputed from the staging
/// directory plus the slot, so the store's footprint is a fixed number of machine words per staged
/// image regardless of how large the images are (the no-leak rule).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct StagedEntry {
    slot: MediaSlot,
    format: MediaFormat,
    size_bytes: u64,
}

/// Process-local counter making each import's staging directory distinct even within one run.
static IMPORT_SEQ: AtomicU64 = AtomicU64::new(0);

/// One import's staging area: bytes written somewhere nothing else looks, until [`commit`] moves
/// them into the media root in one pass.
///
/// **Dropping this without committing removes the staging directory.** That is the atomicity
/// guarantee (B4) expressed as a type rather than as discipline: an early `return`, a `?`, a
/// cancellation, a timeout, or a panic unwinding through the import all leave the media root exactly
/// as it was, because none of them can skip the destructor. There is no code path that has to
/// *remember* to clean up.
pub struct ImportStaging {
    /// `<app_data>/media` — where committed files land.
    root: PathBuf,
    /// `<app_data>/media/.staging/<import-id>` — this import's private area.
    dir: PathBuf,
    /// Fixed-size metadata for each staged file, in slot order. Never the bytes.
    staged: Vec<StagedEntry>,
    /// How many images this import may still stage before the media LIBRARY — not merely this
    /// import — would be full. See [`ImportStaging::begin`].
    headroom: usize,
}

impl ImportStaging {
    /// Open a staging area for one import, creating the media root and the staging directory.
    ///
    /// The `<import-id>` is **generated here and cannot be supplied by the caller**. It could have
    /// been a parameter — the design writes it as `<import-id>` — but a caller-supplied id is one
    /// more string that could, through some future refactor, end up being the source file's name.
    /// Minting it internally from the process id, the wall clock and a process-local counter costs
    /// nothing and closes that door permanently: there is no input to this module from which a
    /// directory name can be built.
    ///
    /// # `library_len`, and the orphans it exists to prevent
    ///
    /// The caller passes the media library's CURRENT size, and it is not a hint — it is what makes
    /// the staging cap mean anything.
    ///
    /// The refusal that matters is `MediaLibrary::import` returning `None` at
    /// [`MAX_MEDIA_ASSETS`], and that counts the library, not one import. Capping on this import's
    /// own count alone means a library holding 900 assets happily stages a 200-image import, all
    /// 200 files are renamed into the media root, and the last 100 get no registry row at all.
    /// Those files then sit in an app-owned directory with nothing pointing at them: invisible in
    /// the media panel, absent from every usage report, and unremovable through any surface the
    /// user has. Silent, permanent disk growth they cannot explain or undo.
    ///
    /// Refusing the 101st image up front instead costs the same image and reports it as
    /// [`MediaStoreError::Full`] — a line in the import report the user can act on (§8.6).
    pub fn begin(app_data: &Path, library_len: usize) -> Result<Self, MediaStoreError> {
        let root = media_root(app_data);
        // Wall clock only for uniqueness, never for ordering — a clock before the epoch degrades to
        // 0 and the counter still separates concurrent imports.
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let seq = IMPORT_SEQ.fetch_add(1, Ordering::Relaxed);
        let id = format!("{}-{nanos:x}-{seq:x}", std::process::id());
        let dir = root.join(STAGING_DIR).join(id);
        fs::create_dir_all(&dir).map_err(|e| MediaStoreError::Io(e.kind()))?;
        Ok(ImportStaging {
            root,
            dir,
            staged: Vec::new(),
            headroom: MAX_MEDIA_ASSETS.saturating_sub(library_len),
        })
    }

    /// How many further images this import may stage before the media library would be full.
    pub fn headroom(&self) -> usize {
        self.headroom.saturating_sub(self.staged.len())
    }

    /// How many images are staged so far.
    pub fn staged_count(&self) -> usize {
        self.staged.len()
    }

    /// Stage one image's **original encoded bytes** under a generated name, returning its slot.
    ///
    /// The encoded bytes are staged, not the decoded pixels: the store should hold the file the
    /// user's deck actually contained, and a decoded frame is up to 64 MiB of data we would only
    /// have to re-encode. `bytes` is borrowed and written straight through — the store never takes
    /// ownership of an image buffer, which is what keeps peak memory at one image rather than an
    /// arena of all of them (§12.1).
    ///
    /// Refuses with [`MediaStoreError::Full`] once the media library's own
    /// [`MAX_MEDIA_ASSETS`] would be reached — counting what the library **already holds**, not
    /// just this import — because an image that could never be registered should not be written
    /// into the media root at all. Per §8.6 that refusal is scoped to the *image*: the caller
    /// reports it and carries on with the import.
    pub fn stage(
        &mut self,
        bytes: &[u8],
        format: MediaFormat,
    ) -> Result<MediaSlot, MediaStoreError> {
        if self.staged.len() >= self.headroom {
            return Err(MediaStoreError::Full);
        }
        let slot = MediaSlot(self.staged.len());
        let path = self.staged_path(slot, format);
        // `create_new` even here, where the name is ours and provably unused: it costs nothing and
        // means a staging directory that somehow already held a file can never be written through.
        let write = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)
            .and_then(|mut f| f.write_all(bytes));
        if let Err(e) = write {
            // A part-written file is not left for the commit to pick up; the whole directory would
            // go on drop anyway, but a half image must never be reachable through a slot.
            let _ = fs::remove_file(&path);
            return Err(MediaStoreError::Io(e.kind()));
        }
        self.staged.push(StagedEntry {
            slot,
            format,
            size_bytes: bytes.len() as u64,
        });
        Ok(slot)
    }

    /// Move every staged file into the media root, in slot order, and report where each landed.
    ///
    /// `start_index` is where the `import-<n>` probe begins — the caller passes the media library's
    /// current length, so a fresh library starts at `import-0`. It is a **hint, not a guarantee**:
    /// correctness comes from `create_new`, which fails atomically if the name is taken, so the
    /// first success is provably an unclaimed name whatever `start_index` was. A wrong hint costs
    /// extra probe attempts and nothing else.
    ///
    /// Consumes the staging area: the directory (and anything still in it, such as a file whose
    /// rename failed) is removed on the way out, so a partial commit leaves no debris.
    pub fn commit(self, start_index: usize) -> CommitResult {
        let mut result = CommitResult::default();
        let mut next = start_index;
        for entry in &self.staged {
            match self.commit_one(entry, &mut next) {
                Ok(c) => result.committed.push(c),
                // Scoped to the slot: a disk-full or permission failure on one picture must not cost
                // the user the other nineteen, or the deck (§8.4).
                Err(error) => result.failed.push(CommitFailure {
                    slot: entry.slot,
                    error,
                }),
            }
        }
        result
    }

    /// Discard everything staged: the directory and its contents go, the media root is untouched.
    /// Identical to simply dropping the value — it exists so a cancel path can say what it means.
    pub fn abort(self) {}

    /// `<staging>/NNNN.<ext>` — named by slot index, never by anything that came out of an archive.
    /// Zero-padded so a directory listing during a support call sorts in import order.
    fn staged_path(&self, slot: MediaSlot, format: MediaFormat) -> PathBuf {
        self.dir
            .join(format!("{:04}.{}", slot.0, format.extension()))
    }

    /// Claim the first free `import-<n>.<ext>` and move the staged file onto it.
    ///
    /// The claim is `create_new` (§8.3): it is the naming primitive precisely because it fails
    /// atomically on an existing name, which is what makes a plain counter safe without a content
    /// hash (a new dependency) or a persisted sequence (a schema change). Note the reservation is
    /// released immediately before the rename — `fs::rename` replaces an existing destination on
    /// both Unix and Windows, but Windows will not replace a file that is still open, and holding
    /// the handle across the rename would fail there and nowhere else.
    fn commit_one(
        &self,
        entry: &StagedEntry,
        next: &mut usize,
    ) -> Result<Committed, MediaStoreError> {
        let ext = entry.format.extension();
        for _ in 0..MAX_MEDIA_ASSETS {
            let n = *next;
            *next = next.saturating_add(1);
            let dest = self.root.join(format!("import-{n}.{ext}"));
            // The path has to fit a `MediaRef` or the slide could never reference the file we are
            // about to write. Checked before the name is claimed, so a refusal claims nothing.
            let Some(dest_str) = dest.to_str() else {
                return Err(MediaStoreError::PathNotUtf8);
            };
            if dest_str.len() > MAX_MEDIA_PATH_LEN {
                return Err(MediaStoreError::PathTooLong);
            }
            let dest_str = dest_str.to_string();
            match OpenOptions::new().write(true).create_new(true).open(&dest) {
                Ok(handle) => {
                    drop(handle);
                    if let Err(e) = fs::rename(self.staged_path(entry.slot, entry.format), &dest) {
                        // Never leave the 0-byte reservation behind masquerading as an image.
                        let _ = fs::remove_file(&dest);
                        return Err(MediaStoreError::Io(e.kind()));
                    }
                    return Ok(Committed {
                        slot: entry.slot,
                        path: dest_str,
                        size_bytes: entry.size_bytes,
                        format: entry.format,
                    });
                }
                // Someone already owns this name — a previous session, or a previous slot in this
                // very commit. Try the next one; never overwrite.
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(e) => return Err(MediaStoreError::Io(e.kind())),
            }
        }
        Err(MediaStoreError::NameSpaceExhausted)
    }
}

impl Drop for ImportStaging {
    /// Removing the staging directory in the destructor is what makes "nothing is visible until
    /// commit" true for *every* exit path, including the ones nobody wrote — a `?` in the middle of
    /// a parse, the 30 s timeout firing, a cancellation, or a panic unwinding through the import.
    /// Best-effort by necessity (a destructor cannot report), and harmless if it fails: a leftover
    /// directory is exactly what [`sweep_stale_staging`] is for.
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.dir);
    }
}

/// Remove every staging directory left under `<app_data>/media/.staging`, returning how many entries
/// were removed. **Call this once at launch, before any import starts.**
///
/// [`ImportStaging`]'s destructor covers every failure this process can survive; it cannot cover the
/// ones it does not — a power cut, an OS kill, a hard crash. Blocker B4 requires the next-launch
/// sweep explicitly, and the design notes it is easy to forget, so it is a first-class function
/// rather than a line inside setup. Safe to run unconditionally: this module owns the staging root
/// outright, so anything found there is by definition abandoned. Symlinks are unlinked, never
/// followed — `file_type` here does not traverse, so a link left in the staging area removes the
/// link and not whatever it points at. Bounded: one directory entry is held at a time.
pub fn sweep_stale_staging(app_data: &Path) -> usize {
    let root = staging_root(app_data);
    let Ok(entries) = fs::read_dir(&root) else {
        return 0; // nothing staged has ever happened here, or the dir is unreadable — either way
    };
    let mut removed = 0usize;
    for entry in entries.flatten() {
        let path = entry.path();
        let is_dir = entry.file_type().map(|t| t.is_dir()).unwrap_or(false);
        let gone = if is_dir {
            fs::remove_dir_all(&path).is_ok()
        } else {
            fs::remove_file(&path).is_ok()
        };
        if gone {
            removed = removed.saturating_add(1);
        }
    }
    removed
}

/// Whether `path` is a file this app put in its own media root — the question
/// `DeckWorkspace::remove_media` must ask before it deletes anything.
///
/// Removing a media asset should delete the file when SelahCue created it (an imported image exists
/// nowhere else, so leaving it behind is silent disk growth the user cannot explain), and must
/// **never** delete it when the asset merely points at a file the user chose from their own
/// Pictures folder. Deleting somebody's photograph out of their own folder because they took it off
/// a slide is a serious defect, and the two cases are indistinguishable without this predicate —
/// which is why it is implemented and tested here even though `remove_media` does not call it yet.
///
/// The check is **lexical**, not a canonicalised confinement check: it compares path components and
/// refuses outright on any `..`, because resolving `..` without touching the filesystem is unsound
/// and touching the filesystem cannot work for a file that has already been deleted. FR-138's
/// canonicalisation of user-chosen paths is a separate story (`86ak0qmzv`) and this predicate does
/// not pretend to discharge it. It also compares case-sensitively, so on a case-insensitive volume a
/// user path differing only in case reads as *not* app-owned — which fails safe, in the direction of
/// leaving a file alone.
pub fn is_app_owned(path: &Path, app_data: &Path) -> bool {
    let root = media_root(app_data);
    if path.components().any(|c| c == Component::ParentDir)
        || root.components().any(|c| c == Component::ParentDir)
    {
        return false;
    }
    match path.strip_prefix(&root) {
        // Strictly inside: the root itself is a directory, not an asset.
        Ok(rest) => rest.components().next().is_some(),
        Err(_) => false,
    }
}

// --- persistence (best-effort; a DB error is swallowed, exactly as in `DeckLibrary`) -------------

/// Persist the whole media registry, replacing the stored set (`media_repo::save_all` is
/// transactional, so a removal in memory becomes a removal on disk and a crash mid-write never
/// leaves half a set).
///
/// Best-effort by design: `db` is `None` when the operator is running its in-memory fallback, and a
/// database error is swallowed. The registry is recovery, not a dependency — an operator whose disk
/// is read-only must still be able to build a service, and `DeckLibrary::is_persistent` already
/// gives the UI an honest "changes won't be saved" state to surface for both.
pub fn save(db: Option<&Database>, library: &MediaLibrary) {
    let Some(db) = db else {
        return;
    };
    let _ = media_repo::save_all(db, library.assets());
}

/// Rehydrate the media registry at launch — the missing half that made every imported image
/// disappear on restart.
///
/// Bounds are **re-checked on the way in**: an asset whose stored path exceeds
/// [`MAX_MEDIA_PATH_LEN`] is dropped and the set is truncated to [`MAX_MEDIA_ASSETS`], so a row
/// written by a different build, or an edited database file, cannot hand the running app a registry
/// that fails its own `within_bounds` predicate. That an unbounded ingress is a real defect even for
/// local SQLite reads is settled precedent here (`CODE-REVIEW-batch-element-model.md:18`).
///
/// Any failure — no database, an unreadable table — yields an empty library rather than an error,
/// mirroring `DeckLibrary::load`.
pub fn load(db: Option<&Database>) -> MediaLibrary {
    let Some(db) = db else {
        return MediaLibrary::new();
    };
    let Ok(mut assets) = media_repo::load_all(db) else {
        return MediaLibrary::new();
    };
    assets.retain(MediaAsset::within_bounds);
    assets.truncate(MAX_MEDIA_ASSETS);
    MediaLibrary::from_assets(assets)
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used)]
    use super::*;
    use selahcue_core::media::{MediaId, MediaKind};

    /// A private temp directory standing in for `<app_data>`, unique per test and per run so the
    /// suite is safe under `cargo test`'s thread parallelism.
    fn temp_app_data(tag: &str) -> PathBuf {
        static N: AtomicU64 = AtomicU64::new(0);
        let dir = std::env::temp_dir().join(format!(
            "selahcue-media-store-{}-{tag}-{}",
            std::process::id(),
            N.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    /// Every path under `root`, relative and sorted — one half of a "byte-identical" snapshot.
    fn walk(root: &Path) -> Vec<String> {
        fn go(dir: &Path, base: &Path, out: &mut Vec<String>) {
            let Ok(rd) = fs::read_dir(dir) else { return };
            let mut entries: Vec<PathBuf> = rd.flatten().map(|e| e.path()).collect();
            entries.sort();
            for p in entries {
                if let Ok(rel) = p.strip_prefix(base) {
                    out.push(rel.to_string_lossy().into_owned());
                }
                if p.is_dir() {
                    go(&p, base, out);
                }
            }
        }
        let mut out = Vec::new();
        go(root, root, &mut out);
        out.sort();
        out
    }

    /// Path plus contents for every file under `root` — the other half of "byte-identical".
    fn snapshot(root: &Path) -> Vec<(String, Vec<u8>)> {
        walk(root)
            .into_iter()
            .map(|rel| {
                let bytes = fs::read(root.join(&rel)).unwrap_or_default();
                (rel, bytes)
            })
            .collect()
    }

    /// Names of the files sitting directly in the media root (i.e. what the user would see).
    fn root_files(app_data: &Path) -> Vec<String> {
        let mut names: Vec<String> = fs::read_dir(media_root(app_data))
            .map(|rd| {
                rd.flatten()
                    .filter(|e| e.file_type().map(|t| t.is_file()).unwrap_or(false))
                    .map(|e| e.file_name().to_string_lossy().into_owned())
                    .collect()
            })
            .unwrap_or_default();
        names.sort();
        names
    }

    #[test]
    fn staged_files_are_invisible_until_commit_then_land_under_generated_names() {
        let app = temp_app_data("visibility");
        let mut staging = ImportStaging::begin(&app, 0).unwrap();
        let a = staging
            .stage(b"first-image-bytes", MediaFormat::Png)
            .unwrap();
        let b = staging.stage(b"second-image", MediaFormat::Jpeg).unwrap();
        assert_eq!((a, b), (MediaSlot(0), MediaSlot(1)), "slots are indices");
        assert_eq!(
            root_files(&app),
            Vec::<String>::new(),
            "nothing is visible in the media root before commit (B4)"
        );

        let staging_dir = staging.dir.clone();
        let result = staging.commit(0);

        assert!(result.failed.is_empty(), "all slots committed");
        assert_eq!(
            root_files(&app),
            vec!["import-0.png".to_string(), "import-1.jpg".to_string()],
            "committed under store-generated `import-<n>.<ext>` names"
        );
        assert_eq!(
            fs::read(result.resolve(a).expect("slot 0 committed")).unwrap(),
            b"first-image-bytes".to_vec(),
            "the original encoded bytes are what landed"
        );
        assert_eq!(
            fs::read(result.resolve(b).expect("slot 1 committed")).unwrap(),
            b"second-image".to_vec()
        );
        assert_eq!(
            result.committed[1].size_bytes,
            b"second-image".len() as u64,
            "size accounting survives the move"
        );
        assert!(
            !staging_dir.exists(),
            "the staging directory is gone after commit"
        );
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn abort_before_commit_leaves_the_media_root_byte_identical() {
        let app = temp_app_data("abort");
        // An import that DID commit, so the "before" state is non-empty and a mistake would show.
        let mut first = ImportStaging::begin(&app, 0).unwrap();
        first.stage(b"kept-image", MediaFormat::Png).unwrap();
        first.commit(0);
        let before = snapshot(&media_root(&app));
        assert!(!before.is_empty(), "precondition: the root holds a file");

        let mut aborted = ImportStaging::begin(&app, 0).unwrap();
        aborted.stage(b"doomed-a", MediaFormat::Png).unwrap();
        aborted.stage(b"doomed-b", MediaFormat::Jpeg).unwrap();
        aborted.stage(b"doomed-c", MediaFormat::Png).unwrap();
        let staging_dir = aborted.dir.clone();
        assert!(staging_dir.exists(), "precondition: staged on disk");
        aborted.abort();

        assert!(!staging_dir.exists(), "the staging directory was removed");
        assert_eq!(
            snapshot(&media_root(&app)),
            before,
            "the media root is byte-identical to before the aborted import (B4)"
        );
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn a_dropped_staging_area_cleans_up_without_an_explicit_abort() {
        // The atomicity guarantee has to hold on paths nobody wrote — an early return, a timeout,
        // an unwinding panic. Those all run the destructor and nothing else.
        let app = temp_app_data("drop");
        let mut committed = ImportStaging::begin(&app, 0).unwrap();
        committed.stage(b"kept-image", MediaFormat::Png).unwrap();
        committed.commit(0);
        // Compare the COMMITTED media only: the `.staging` parent directory is created on the first
        // `begin` and legitimately outlives any one import (the per-import child is what must go).
        let committed_only = |app: &Path| -> Vec<(String, Vec<u8>)> {
            snapshot(&media_root(app))
                .into_iter()
                .filter(|(rel, _)| !rel.starts_with(STAGING_DIR))
                .collect()
        };
        let before = committed_only(&app);
        assert!(!before.is_empty(), "precondition: the root holds a file");

        let staging_dir = {
            let mut staging = ImportStaging::begin(&app, 0).unwrap();
            staging.stage(b"never-committed", MediaFormat::Png).unwrap();
            staging.dir.clone()
        };

        assert!(!staging_dir.exists(), "dropping cleans up");
        assert_eq!(
            walk(&staging_root(&app)),
            Vec::<String>::new(),
            "no staged bytes survive the drop"
        );
        assert_eq!(committed_only(&app), before, "committed media is untouched");
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn hostile_archive_names_cannot_influence_any_created_path() {
        // B1. The store takes no name of any kind — bytes and a format enum, nothing else — so these
        // strings have no parameter to arrive through. They are pushed in as the only thing an
        // archive controls that does reach the store (the file's own content), and the assertions
        // are the ones B1's test demands: generated names only, and nothing created outside the
        // media root. `app` here plays the app-data parent, so the walk sees any escape.
        let app = temp_app_data("hostile");
        let sibling = app.join("untouched-sibling");
        fs::create_dir_all(&sibling).unwrap();
        fs::write(sibling.join("keep.txt"), b"user data").unwrap();
        let before = snapshot(&app);

        let hostile: [&[u8]; 8] = [
            b"../../evil",
            b"/etc/passwd",
            b"C:\\Windows\\evil",
            b"..\\..\\evil",
            b"CON",
            b"nul",
            b"with\0nul",
            b"....//....//evil",
        ];
        let mut staging = ImportStaging::begin(&app, 0).unwrap();
        for (i, bytes) in hostile.iter().enumerate() {
            let format = if i % 2 == 0 {
                MediaFormat::Png
            } else {
                MediaFormat::Jpeg
            };
            staging.stage(bytes, format).unwrap();
        }
        let result = staging.commit(0);
        assert_eq!(result.committed.len(), hostile.len());
        assert!(result.failed.is_empty());

        let root = media_root(&app);
        for c in &result.committed {
            let path = Path::new(&c.path);
            assert_eq!(
                path.parent(),
                Some(root.as_path()),
                "every file is a DIRECT child of the media root: {}",
                c.path
            );
            let name = path
                .file_name()
                .and_then(|n| n.to_str())
                .expect("a generated, UTF-8 name");
            let (stem, ext) = name.split_once('.').expect("import-<n>.<ext>");
            let n = stem
                .strip_prefix("import-")
                .expect("the generated `import-` prefix");
            assert!(
                !n.is_empty() && n.bytes().all(|b| b.is_ascii_digit()),
                "the only variable part is a decimal counter, got {name}"
            );
            assert!(
                ext == "png" || ext == "jpg",
                "the extension comes from the sniffed format enum, got {name}"
            );
        }

        // Nothing was created outside the media root: the whole app-data tree differs only by the
        // media root's own contents.
        let after = snapshot(&app);
        let escaped: Vec<&(String, Vec<u8>)> = after
            .iter()
            .filter(|(rel, _)| !rel.starts_with(MEDIA_DIR))
            .collect();
        let before_outside: Vec<&(String, Vec<u8>)> = before
            .iter()
            .filter(|(rel, _)| !rel.starts_with(MEDIA_DIR))
            .collect();
        assert_eq!(
            escaped, before_outside,
            "nothing outside the media root was created, changed or removed"
        );
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn a_claimed_name_is_never_overwritten_the_commit_takes_the_next_free_one() {
        // `create_new` is the whole safety argument for using a plain counter instead of a hash.
        let app = temp_app_data("claimed");
        let root = media_root(&app);
        fs::create_dir_all(&root).unwrap();
        fs::write(root.join("import-0.png"), b"a previous session's file").unwrap();

        let mut staging = ImportStaging::begin(&app, 0).unwrap();
        staging.stage(b"new-import", MediaFormat::Png).unwrap();
        let result = staging.commit(0); // deliberately the WRONG hint: import-0 is taken

        assert_eq!(result.failed.len(), 0);
        assert_eq!(
            result.committed[0].path,
            root.join("import-1.png").to_string_lossy(),
            "the taken name was skipped, not overwritten"
        );
        assert_eq!(
            fs::read(root.join("import-0.png")).unwrap(),
            b"a previous session's file".to_vec(),
            "the previous session's file is untouched"
        );
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn one_failed_slot_is_reported_without_costing_the_others() {
        // Partial media, whole deck (§8.4): a per-file failure is a report line, not an import
        // failure. The failure is induced by removing a staged file before the commit reaches it.
        let app = temp_app_data("partial");
        let mut staging = ImportStaging::begin(&app, 0).unwrap();
        let ok_a = staging.stage(b"good-a", MediaFormat::Png).unwrap();
        let doomed = staging.stage(b"vanishing", MediaFormat::Png).unwrap();
        let ok_b = staging.stage(b"good-b", MediaFormat::Jpeg).unwrap();
        fs::remove_file(staging.staged_path(doomed, MediaFormat::Png)).unwrap();

        let result = staging.commit(0);

        assert_eq!(result.committed.len(), 2, "the healthy slots still landed");
        assert_eq!(result.failed.len(), 1);
        assert_eq!(result.failed[0].slot, doomed);
        assert!(result.resolve(ok_a).is_some() && result.resolve(ok_b).is_some());
        assert!(
            result.resolve(doomed).is_none(),
            "the failed slot resolves to nothing, so the builder drops that picture"
        );
        assert_eq!(
            root_files(&app).len(),
            2,
            "no empty reservation file was left behind for the failed slot"
        );
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn slots_are_consecutive_from_zero_and_resolve_to_their_own_bytes() {
        // The seam's unwritten contract: slot `n` is the n-th image staged, counting from zero, in
        // the order `stage` was called — and that is what the pure importer's own `MediaSlot`
        // means too. The two types are separate, so nothing checks the agreement; if it ever
        // breaks, the failure is not an error but the wrong photograph on the wrong slide.
        //
        // The middle slot is made to fail on purpose. That is the case where an index-based
        // mapping silently shifts by one, and it is the only way this drifts in practice: every
        // slot after the gap would resolve to its neighbour's file, and nothing would say so.
        let app = temp_app_data("slots");
        let mut staging = ImportStaging::begin(&app, 0).unwrap();
        let payloads: Vec<Vec<u8>> = (0..6)
            .map(|i| format!("distinct-image-{i}").into_bytes())
            .collect();
        let slots: Vec<MediaSlot> = payloads
            .iter()
            .map(|p| staging.stage(p, MediaFormat::Png).unwrap())
            .collect();
        assert_eq!(
            slots,
            (0..6).map(MediaSlot).collect::<Vec<_>>(),
            "slots are consecutive indices from zero, in staging order"
        );

        // Sabotage slot 3 so the commit has a hole in the middle.
        fs::remove_file(staging.staged_path(MediaSlot(3), MediaFormat::Png)).unwrap();
        let result = staging.commit(0);
        assert_eq!(result.failed.len(), 1);
        assert_eq!(result.failed[0].slot, MediaSlot(3));

        for (i, payload) in payloads.iter().enumerate() {
            let slot = MediaSlot(i);
            if i == 3 {
                assert!(
                    result.resolve(slot).is_none(),
                    "the failed slot resolves to nothing"
                );
                continue;
            }
            let path = result.resolve(slot).expect("a committed slot resolves");
            assert_eq!(
                fs::read(path).unwrap(),
                *payload,
                "slot {i} must resolve to the bytes staged under slot {i} — not its neighbour's"
            );
        }
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn sweep_removes_stale_staging_and_leaves_committed_media_untouched() {
        // B4's crash path: the destructor cannot run if the process was killed.
        let app = temp_app_data("sweep");
        let mut committed = ImportStaging::begin(&app, 0).unwrap();
        committed.stage(b"survivor", MediaFormat::Png).unwrap();
        committed.commit(0);
        let media_before = snapshot(&media_root(&app))
            .into_iter()
            .filter(|(rel, _)| !rel.starts_with(STAGING_DIR))
            .collect::<Vec<_>>();

        // Two directories and a loose file, as a killed process would have left them.
        let stale_a = staging_root(&app).join("crashed-1");
        let stale_b = staging_root(&app).join("crashed-2");
        fs::create_dir_all(&stale_a).unwrap();
        fs::create_dir_all(&stale_b).unwrap();
        fs::write(stale_a.join("0000.png"), b"orphan").unwrap();
        fs::write(staging_root(&app).join("loose"), b"orphan").unwrap();

        assert_eq!(sweep_stale_staging(&app), 3, "both dirs and the loose file");
        assert_eq!(
            walk(&staging_root(&app)),
            Vec::<String>::new(),
            "the staging area is empty"
        );
        assert_eq!(
            snapshot(&media_root(&app))
                .into_iter()
                .filter(|(rel, _)| !rel.starts_with(STAGING_DIR))
                .collect::<Vec<_>>(),
            media_before,
            "committed media is byte-identical after the sweep"
        );
        assert_eq!(
            sweep_stale_staging(&app),
            0,
            "sweeping a clean store removes nothing"
        );
        assert_eq!(
            sweep_stale_staging(Path::new("/definitely/not/a/real/app/data/dir")),
            0,
            "an unreadable or absent staging root is not an error"
        );
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn is_app_owned_separates_store_files_from_the_users_own_pictures() {
        let app = temp_app_data("owned");
        let root = media_root(&app);
        assert!(
            is_app_owned(&root.join("import-3.jpg"), &app),
            "a committed file is app-owned — removing the asset may delete it"
        );
        assert!(
            is_app_owned(&root.join(STAGING_DIR).join("x").join("0000.png"), &app),
            "staged files are inside the root too"
        );
        assert!(
            !is_app_owned(Path::new("/Users/someone/Pictures/wedding.jpg"), &app),
            "a user's own photo is NOT app-owned — deleting it would be a serious defect"
        );
        assert!(
            !is_app_owned(&root, &app),
            "the root itself is a directory, not an asset"
        );
        assert!(
            !is_app_owned(&app.join("selahcue.db3"), &app),
            "a sibling of the media root is not inside it"
        );
        assert!(
            !is_app_owned(&root.join("..").join("escape.png"), &app),
            "a `..` component is refused rather than lexically resolved"
        );
        assert!(
            !is_app_owned(Path::new("relative.png"), &app),
            "a bare relative path is not provably inside the root"
        );
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn the_media_registry_round_trips_through_the_repo_with_its_ids() {
        // The prerequisite this module exists to unblock: without it, an imported image's metadata
        // is gone at the next launch even though the file is still on disk.
        let db = Database::open_in_memory().unwrap();
        let mut lib = MediaLibrary::new();
        let a = lib
            .import(
                "/app/media/import-0.png",
                MediaKind::Image,
                1234,
                Some(800),
                Some(600),
                None,
                42,
            )
            .unwrap();
        let b = lib
            .import(
                "/app/media/import-1.jpg",
                MediaKind::Image,
                99,
                None,
                None,
                None,
                43,
            )
            .unwrap();

        save(Some(&db), &lib);
        let reloaded = load(Some(&db));

        assert_eq!(
            reloaded, lib,
            "the whole registry round-trips, ids included"
        );
        assert_eq!(reloaded.get(a).map(|x| x.width), Some(Some(800)));
        assert_eq!(reloaded.get(b).map(|x| x.size_bytes), Some(99));
        // A newly imported asset must not reuse a persisted id.
        let mut reloaded = reloaded;
        let c = reloaded
            .import(
                "/app/media/import-2.png",
                MediaKind::Image,
                7,
                None,
                None,
                None,
                44,
            )
            .unwrap();
        assert!(c > b && c > a, "next_id resumes past the persisted maximum");

        // Best-effort: no database is an empty library and a silent save, never an error.
        assert_eq!(load(None), MediaLibrary::new());
        save(None, &lib);
    }

    #[test]
    fn a_stored_asset_that_breaks_its_bounds_is_dropped_on_load() {
        // Bounds are re-checked on the way in — a row from another build cannot hand the running app
        // a registry that fails its own `within_bounds` predicate.
        let db = Database::open_in_memory().unwrap();
        let over_long = "x".repeat(MAX_MEDIA_PATH_LEN + 1);
        media_repo::save_all(
            &db,
            &[
                MediaAsset {
                    id: MediaId(1),
                    path: "/app/media/import-0.png".into(),
                    kind: MediaKind::Image,
                    size_bytes: 10,
                    width: None,
                    height: None,
                    duration_ms: None,
                    imported_at: 0,
                },
                MediaAsset {
                    id: MediaId(2),
                    path: over_long,
                    kind: MediaKind::Image,
                    size_bytes: 10,
                    width: None,
                    height: None,
                    duration_ms: None,
                    imported_at: 0,
                },
            ],
        )
        .unwrap();

        let lib = load(Some(&db));
        assert_eq!(
            lib.len(),
            1,
            "the out-of-bounds row was dropped, not loaded"
        );
        assert!(lib.within_bounds());
        assert!(lib.get(MediaId(1)).is_some());
    }

    #[test]
    fn staging_retains_no_image_bytes_and_refuses_past_the_asset_cap() {
        // No-leak. The store's footprint must be a function of the NUMBER of images, never of their
        // size — the bytes go straight to disk and are never held.
        let app = temp_app_data("bounded");
        let footprint = |s: &ImportStaging| s.staged.len() * std::mem::size_of::<StagedEntry>();

        let tiny = {
            let mut s = ImportStaging::begin(&app, 0).unwrap();
            for _ in 0..8 {
                s.stage(&[0u8; 1024], MediaFormat::Png).unwrap();
            }
            footprint(&s)
        };
        let huge = {
            let mut s = ImportStaging::begin(&app, 0).unwrap();
            for _ in 0..8 {
                s.stage(&vec![0u8; 512 * 1024], MediaFormat::Png).unwrap();
            }
            footprint(&s)
        };
        assert_eq!(
            tiny, huge,
            "512x the payload, identical retained footprint — no bytes are held"
        );
        assert!(
            std::mem::size_of::<StagedEntry>() <= 32,
            "a staged entry is a few machine words, not a buffer or a path"
        );

        // And the count itself is capped, so the footprint has an absolute ceiling.
        let mut s = ImportStaging::begin(&app, 0).unwrap();
        for _ in 0..MAX_MEDIA_ASSETS {
            s.stage(b"", MediaFormat::Png).unwrap();
        }
        assert_eq!(s.staged_count(), MAX_MEDIA_ASSETS);
        assert_eq!(
            s.stage(b"one too many", MediaFormat::Png),
            Err(MediaStoreError::Full),
            "refused at the cap — scoped to the image, never to the import (§8.6)"
        );
        assert_eq!(
            s.staged_count(),
            MAX_MEDIA_ASSETS,
            "the refusal added nothing"
        );
        drop(s);
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn a_nearly_full_library_refuses_early_rather_than_committing_invisible_orphans() {
        // The refusal that matters is `MediaLibrary::import` returning `None` at the asset cap, and
        // that counts THE LIBRARY. Capping on this import's own count alone means a library at 900
        // accepts a 200-image import, all 200 files are renamed into the media root, and the last
        // 100 get no registry row: files in an app-owned directory that appear in no media panel,
        // no usage report and no delete path. Silent, permanent disk growth the user cannot
        // explain or undo.
        //
        // This is deliberately asserted on the FILES on disk, not only on the return values — the
        // defect's whole signature is a file existing that nothing knows about.
        let app = temp_app_data("headroom");
        let existing = MAX_MEDIA_ASSETS - 100;
        let mut staging = ImportStaging::begin(&app, existing).unwrap();
        assert_eq!(staging.headroom(), 100, "the library's own space, not ours");

        let mut accepted = 0usize;
        let mut refused = 0usize;
        for _ in 0..200 {
            match staging.stage(b"an imported image", MediaFormat::Png) {
                Ok(_) => accepted += 1,
                Err(MediaStoreError::Full) => refused += 1,
                Err(e) => panic!("unexpected {e:?}"),
            }
        }
        assert_eq!((accepted, refused), (100, 100));

        let result = staging.commit(existing);
        assert_eq!(result.committed.len(), 100);
        assert!(result.failed.is_empty());
        assert_eq!(
            root_files(&app).len(),
            100,
            "exactly the registrable images reached the media root — a file that could never get \
             a registry row was never written into it"
        );

        // And the survivors really do all fit the library, which is the property the cap is for.
        let mut lib = MediaLibrary::new();
        // Distinct paths: `import` keys on the path and returns the existing id for a repeat, so a
        // constant path would build a library of one and prove nothing.
        for i in 0..existing {
            lib.import(
                format!("/prior-{i}.png"),
                MediaKind::Image,
                1,
                None,
                None,
                None,
                0,
            )
            .expect("the pre-existing library");
        }
        assert_eq!(lib.len(), existing);
        for c in &result.committed {
            assert!(
                lib.import(&c.path, MediaKind::Image, c.size_bytes, None, None, None, 0)
                    .is_some(),
                "every committed file must be registrable — otherwise it is an orphan"
            );
        }
        fs::remove_dir_all(&app).ok();
    }

    #[test]
    fn errors_read_as_plain_english_and_carry_no_path() {
        // ADR-0011 / FR-082 redaction: an error may say what went wrong, never where.
        let e = MediaStoreError::Io(std::io::ErrorKind::PermissionDenied);
        assert_eq!(
            e.to_string(),
            "SelahCue isn't allowed to write to the media folder"
        );
        assert_eq!(
            MediaStoreError::Full.to_string(),
            "the media library is full"
        );
        let _: &dyn std::error::Error = &e; // the house error contract
    }
}
