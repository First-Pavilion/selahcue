//! The operator-local **Presentations Library** (design 86ajvpngr · `PRESENTATIONS-LIBRARY-spec.md`).
//!
//! Owns the authoritative set of saved decks (each a [`SlideDeck`] with a stable [`DeckId`]) plus an
//! optional persistence handle. It surfaces the deck list for the Library UI and backs the
//! create/open/rename/duplicate/delete commands; the currently-*open* deck is edited by the separate
//! [`DeckWorkspace`](crate::deck_workspace::DeckWorkspace) and synced back here (autosave).
//!
//! **Persistence is best-effort** (recovery, not a hard dependency): if the SQLite DB can't open, the
//! library runs in memory — editing is never blocked — and reports `is_persistent() == false` so the
//! UI can surface an honest "changes won't be saved" state. It is keyed by a stable `DeckId` but
//! **persisted by NAME** (the `deck` table PK, `deck_repo`), so names are kept **unique** (a `(n)`
//! suffix on collision) — otherwise an upsert on a name owned by a *different* deck would clobber it.
//!
//! **Identity (86ak196cr · ADR-0031).** `DeckId` is only this library's own counter: another
//! machine's library hands out the same numbers to unrelated decks. Every saved deck therefore also
//! carries a random [`DeckUid`], minted here and kept by the library as the authority; a plan link
//! that crosses a machine boundary travels as that uid and is re-bound by
//! [`export_link`](DeckLibrary::export_link) / [`import_link`](DeckLibrary::import_link), never as a
//! number. A uid is an **unauthenticated claim**, not proof of sameness, which is why
//! [`try_adopt`](DeckLibrary::try_adopt) always mints a fresh one.

use crate::deck_workspace::deck_image_paths;
use selahcue_core::deck_ref::{
    export_deck_link, import_deck_link, DeckLinkMatch, DeckUid, LocalDeck, PortableDeckLink,
};
use selahcue_core::plan::ItemContent;
use selahcue_data::deck_repo::MAX_DECK_NUMBER;
use selahcue_data::{deck_repo, Database};
use selahcue_present::{
    render_authored_slide, DeckId, DeckTrash, FrameBuffer, SlideDeck, SlideId, Theme,
};

/// Lightweight row for the Library list (`deck_list`) — never carries the slide bytes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeckMeta {
    pub id: DeckId,
    pub name: String,
    pub slides: usize,
}

/// One hit from the global presentation search (`deck_search`): the matched deck (id + name) and —
/// for a SLIDE-CONTENT match — the matched slide's id/index + a short snippet of the matched line.
/// A NAME match carries no slide fields. Serializes to the JSON the search modal renders.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct SearchHit {
    pub deck_id: u64,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slide_id: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slide_index: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub snippet: Option<String>,
    /// `"name"` for a title match, `"content"` for a slide-text match.
    pub kind: &'static str,
}

/// A short, char-boundary-safe excerpt of `line`, capped to `max` chars (ellipsis when trimmed).
/// Slide text lines are short, so the first window is enough context for a search snippet.
fn search_snippet(line: &str, max: usize) -> String {
    if line.chars().count() > max {
        let head: String = line.chars().take(max).collect();
        format!("{head}…")
    } else {
        line.to_string()
    }
}

/// Lightweight per-slide row for the Live Console slide picker (`plan_deck_slides`,
/// `LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md` §6): the slide's stable id, a speaker-readable
/// label (its first on-screen text line, falling back to a notes line), and whether it carries
/// speaker notes. Never the slide bytes — the picker fetches pixels separately, on demand, via
/// [`DeckLibrary::render_slide`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SlideMeta {
    pub id: SlideId,
    pub label: Option<String>,
    pub has_notes: bool,
}

/// What [`DeckLibrary::adopt_with_policy`] does when the deck being adopted carries a name a saved
/// deck already holds (ADR-0024 decision 5; design §11.2 B).
///
/// The library deliberately has **no default**. Silent suffixing is tolerable when a human typed
/// the name and can see what happened; it is an operational hazard when the name was *derived* — a
/// presentation import names the deck after the file stem, nobody typed anything and nobody is
/// watching that field, so `Sunday Service (2)`, `(3)`, `(4)` accumulate with no way to tell which
/// one is this week's, and the wrong deck opens on a Sunday morning (design §11.1). Making the
/// choice a caller argument is what forces every derived-name path to state its intent.
// DELETE THIS ALLOW once `main.rs` wires the import commands. The operator is a *binary* crate, so
// `pub` exempts nothing from `dead_code`, and its clippy gate is `-D warnings`; `#[expect]` cannot be
// used because `--all-targets` compiles the bin both with and without `cfg(test)` and the tests below
// already exercise this API, so the lint fires in one build and not the other.
#[allow(dead_code)] // consumed by the import commands in main.rs (ADR-0024)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum NameCollisionPolicy {
    /// Keep the existing deck and adopt this one under a `(n)` suffix — today's [`uniquify`]
    /// behaviour, and what [`DeckLibrary::adopt`] has always done.
    KeepBoth,
    /// Update the existing deck **in place**, preserving its [`DeckId`] (see
    /// [`DeckLibrary::replace_deck`] for why the id must survive).
    Replace,
    /// Refuse: report the collision to the caller and change nothing.
    Fail,
}

/// Why [`DeckLibrary::adopt_with_policy`] / [`DeckLibrary::replace_deck`] refused. Refusals are
/// **total and side-effect-free** — on any `Err` the library, its ids and its persisted rows are
/// exactly as they were, so a caller can safely report the error and offer a different policy.
///
/// Hand-rolled with a manual `Display` + [`std::error::Error`], the house pattern (`ParseError` in
/// `selahcue-core::scripture`); the tree carries no `thiserror`/`anyhow`.
#[allow(dead_code)] // consumed by the import commands in main.rs (ADR-0024)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AdoptError {
    /// A saved deck already holds this name and the policy was [`NameCollisionPolicy::Fail`].
    NameTaken,
    /// The deck that would be overwritten is the one currently live or staged. Replacing the
    /// content of the deck on the audience output mid-service is exactly what the presenter's
    /// "staging never changes Live" invariant exists to prevent, so this is **refused outright** —
    /// never queued, never applied at the next transition (design §11.2 D).
    TargetIsLive,
    /// [`DeckLibrary::replace_deck`] was given a [`DeckId`] the library does not hold — the deck the
    /// caller meant to replace was deleted (or its id was never valid) between the moment the choice
    /// was offered and the moment it was committed. Refused rather than silently adopted as a new
    /// deck, because "replace *that* one" and "add a new one" are different user intents.
    UnknownTarget,
    /// The deck would have needed a new number and the database would not record one
    /// ([`NumberNotRecorded`]); nothing was added.
    NumberNotRecorded,
}

impl std::fmt::Display for AdoptError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            AdoptError::NameTaken => "a presentation with that name already exists",
            AdoptError::TargetIsLive => {
                "that presentation is on the audience output — it can't be replaced right now"
            }
            AdoptError::UnknownTarget => "that presentation is no longer in the library",
            AdoptError::NumberNotRecorded => {
                "the presentation database did not accept a new presentation number"
            }
        };
        f.write_str(s)
    }
}

impl std::error::Error for AdoptError {}

/// The decks (other than the open one) that still show a given stored picture — see
/// [`DeckLibrary::media_keepers`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct MediaKeepers {
    /// Saved decks in the Library list that show it.
    pub saved: usize,
    /// Recently deleted decks ("Undo delete" could restore them) that show it.
    pub trashed: usize,
}

impl MediaKeepers {
    /// Whether anything outside the open deck still needs the file to exist.
    pub fn any(self) -> bool {
        self.saved > 0 || self.trashed > 0
    }
}

/// A new deck number could not be recorded durably, so none was issued and nothing was created.
///
/// A number is written to the deck database BEFORE it is handed out (17tnw2b9arx): plans are stored
/// by the host in a different file, so a deck that exists only in memory (its row failed to write)
/// can still be linked from a plan that does save, and a number issued without a durable record
/// would be handed to a different deck after the next restart. When the database will not take the
/// record (disk full, locked past the busy timeout, a damaged mark, or the numbers are used up) the
/// honest answer is "no new presentation", not a number that may later point at the wrong one.
/// Only a library WITH a database can refuse: the in-memory fallback has nothing to record to and
/// already reports `is_persistent() == false`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NumberNotRecorded;

impl std::fmt::Display for NumberNotRecorded {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(
            "the presentation database did not accept a new presentation number, so nothing was created",
        )
    }
}

impl std::error::Error for NumberNotRecorded {}

/// A source of 128 random bits for a new deck identity, or `None` if the platform has none to give.
///
/// A plain `fn` pointer, not a boxed closure: the library lives in the shell's shared state and
/// must stay `Send`, and the one production source ([`os_entropy`]) captures nothing. Tests swap in
/// a counter, a stuck source and a failing one to prove the library never hands two decks the same
/// identity and degrades to "unidentified" rather than to a guess.
type Entropy = fn() -> Option<[u8; 16]>;

/// The operating system's random source.
fn os_entropy() -> Option<[u8; 16]> {
    let mut bytes = [0u8; 16];
    getrandom::fill(&mut bytes).ok()?;
    Some(bytes)
}

/// How many times minting a uid retries when the draw is refused (all-zero) or already held. With
/// a working source a retry is never needed (2^-128); the bound exists so a stuck source ends in
/// "no identity" instead of a loop.
const MINT_UID_ATTEMPTS: usize = 8;

/// What the identity backfill on load wrote -- observed by the tests, not used in production.
#[allow(dead_code)] // the fields are read by the tests only
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
struct BackfillStats {
    /// Rows written back (or attempted).
    attempted: usize,
    /// Of those, writes that failed (the backfill stops after the first).
    failed: usize,
}

/// The persisted deck library.
pub struct DeckLibrary {
    /// The persistence handle, or `None` when running in the in-memory fallback.
    db: Option<Database>,
    /// The saved decks — each with a unique, non-zero [`DeckId`] and a unique `name`.
    decks: Vec<SlideDeck>,
    /// Monotonic library-level deck-id counter: a LOWER BOUND for the next number to issue. Never
    /// reused, across restarts too (17tnw2b9arx): it is seeded at load from the larger of the
    /// highest surviving deck and the PERSISTED high-water mark (`deck_repo::high_water`), but it is
    /// only a hint. The authority is the database: every number is issued by
    /// `deck_repo::issue_number`, which records it durably BEFORE it is handed out, so a number whose
    /// deck was deleted (and whose undo-trash entry died with the process), or whose deck row failed
    /// to write, is still never handed out again, even if this counter is behind or the mark could
    /// not be read at load. Self-heals past loaded ids.
    next_id: u64,
    /// Recently deleted decks, retained so a delete can be undone with its REAL content.
    ///
    /// In-memory and bounded — this is an undo affordance for an accidental delete during a
    /// service, not an archive, and it deliberately does not survive a restart: retaining
    /// deleted decks on disk would quietly resurrect data an operator believed they had
    /// removed. (What DOES survive a restart is the deleted deck's NUMBER: the persisted
    /// high-water mark keeps it from ever being issued again, so a plan link that still holds it
    /// shows "Presentation missing" rather than some other deck; 17tnw2b9arx.)
    /// The bounded container itself lives in `selahcue-present`
    /// ([`DeckTrash`]) because this crate is excluded from the workspace and nothing here
    /// gets real tests.
    trash: DeckTrash,
    /// Where new deck identities come from (see [`Entropy`]).
    entropy: Entropy,
    /// Names (the row key and the deck's own) of decks that were read from the database but left
    /// OUT of the library because they needed a new number at load and none could be given (see
    /// `heal`). Their rows stay on disk untouched; the names stay reserved here so a new deck can
    /// never take one and upsert over the row. Bounded by the number of rows in the database.
    held_back: Vec<String>,
    /// How many decks `heal` left out of the library at load. Only the COUNT is kept and logged (never
    /// a name: no user content in logs); the console is not told (ADR-0031 limit 4).
    left_out: usize,
}

impl DeckLibrary {
    /// Build the library from an optional DB: load every persisted deck, deserialize, and
    /// **self-heal** to unique non-zero ids + unique names + unique identities. A missing/failed
    /// DB → an empty in-memory library (never an error — persistence is best-effort).
    pub fn load(db: Option<Database>) -> Self {
        Self::load_inner(db, os_entropy)
    }

    fn load_inner(db: Option<Database>, entropy: Entropy) -> Self {
        Self::load_reporting(db, entropy).0
    }

    /// [`load_inner`](Self::load_inner), also reporting what the identity backfill wrote (tests
    /// read it; production ignores it).
    fn load_reporting(db: Option<Database>, entropy: Entropy) -> (Self, BackfillStats) {
        let mut decks: Vec<SlideDeck> = Vec::new();
        // The key of the ROW each deck was read from, parallel to `decks`. The row key is the only
        // thing that says which row a write would land on; the name inside the JSON can disagree
        // with it (a restored, hand-edited or older-build database), and writing by that name would
        // overwrite a DIFFERENT presentation's row.
        let mut row_keys: Vec<String> = Vec::new();
        if let Some(db) = &db {
            if let Ok(rows) = deck_repo::load_all(db) {
                for (row_key, json) in rows {
                    if let Ok(deck) = serde_json::from_str::<SlideDeck>(&json) {
                        decks.push(deck);
                        row_keys.push(row_key);
                    }
                    // A single corrupt blob is skipped, never fatal (FR-070-style tolerance).
                }
            }
        }
        // The highest deck number ever recorded as issued on this database (17tnw2b9arx). A store
        // from a build that predates the mark has no row: that reads as 0 and is raised below. A
        // mark that cannot be READ is retried once; if it still cannot, this load must not pretend it
        // is 0 and say nothing. It is harmless to the numbering (the counter is only a lower bound;
        // `deck_repo::issue_number` checks the stored value on every new number and REFUSES while it
        // is unreadable) but the operator-facing consequence, "new presentations are refused", is
        // logged here so it can be traced.
        let issued: Option<u64> = match &db {
            Some(db) => {
                let mark = read_mark(db);
                if mark.is_none() {
                    eprintln!(
                        "SelahCue: the presentation number record could not be read; creating \
                         new presentations will be refused until it can be."
                    );
                }
                mark
            }
            // No database: nothing to read, and the fallback library numbers from its counter alone.
            None => Some(0),
        };
        let mut lib = DeckLibrary {
            db,
            decks,
            next_id: 1,
            trash: DeckTrash::new(),
            entropy,
            held_back: Vec::new(),
            left_out: 0,
        };
        let stats = lib.heal(&mut row_keys, issued);
        if lib.left_out > 0 {
            // The COUNT only: no names, no user content in a log. The console is not told (ADR-0031
            // limit 4), so this line is the only signal that presentations are missing from the list.
            eprintln!(
                "SelahCue: {} presentation(s) were left out of the library because no number could \
                 be issued for them (the database would not record one, or the numbers are used \
                 up); their rows are untouched and they return once that is repaired.",
                lib.left_out
            );
        }
        lib.record_high_water(stats.failed > 0);
        (lib, stats)
    }

    /// Whether edits are actually being persisted (false = in-memory fallback).
    pub fn is_persistent(&self) -> bool {
        self.db.is_some()
    }

    /// Ensure every deck has a unique non-zero id and a unique, non-empty name; set `next_id` past
    /// the highest id. Mirrors the slide `mint_id` self-heal — a stale/tampered/duplicated blob can
    /// never leave two decks sharing an id (which would make `deck_open`/`delete` target the wrong
    /// one) or a name (which would make a `save_one` upsert clobber a sibling).
    ///
    /// `row_keys[i]` is the key of the row `decks[i]` was read from (see
    /// [`load_reporting`](Self::load_reporting)); it is kept parallel to `decks` when a deck is left
    /// out. `issued` is the persisted high-water mark, or `None` if it could not be read: the counter
    /// starts past it as well as past every surviving deck, so a number whose deck was deleted is never
    /// issued again. Returns what the identity backfill wrote.
    ///
    /// **A deck that needs a number** (zero, duplicate or out of range) gets one RECORDED by the
    /// database when it will. The first refusal stops the calls (as the backfill below does, so a locked
    /// database costs one busy timeout, not one per deck) and the remaining decks get a SESSION-ONLY
    /// number from the counter, inside [`MAX_DECK_NUMBER`] and only if the mark was readable: that
    /// number is not recorded, so another process or the next launch may issue it again. A deck that
    /// cannot be given even that (the numbers are used up, or the mark could not be read so a retired
    /// number might be handed out) is **left out of the library**: its row stays on disk, untouched,
    /// and its name stays reserved ([`held_back`](Self::held_back)). It comes back once the cause is
    /// repaired (ADR-0031, "Known limits" item 4).
    fn heal(&mut self, row_keys: &mut Vec<String>, issued: Option<u64>) -> BackfillStats {
        use std::collections::HashSet;
        let mut stats = BackfillStats::default();
        self.next_id = self
            .highest_deck_number()
            .max(issued.unwrap_or(0))
            .saturating_add(1)
            .max(1);
        // Pass 1 — ids: reserve every distinct non-zero id in order; anything zero or duplicate gets
        // a freshly minted id (always > all existing, so it can't collide with a reserved one).
        let mut seen_ids: HashSet<u64> = HashSet::new();
        let mut need_id: Vec<usize> = Vec::new();
        for (i, d) in self.decks.iter().enumerate() {
            let id = d.id().0;
            // A number above the ceiling is not trusted (the webview's JSON numbers would alias it
            // with its neighbours): it is renumbered like a zero or duplicate one, and never raises
            // the mark.
            if id == 0 || id > MAX_DECK_NUMBER || !seen_ids.insert(id) {
                need_id.push(i);
            }
        }
        let mut recording = true;
        let mut left_out: Vec<usize> = Vec::new();
        for i in need_id {
            let recorded = if recording {
                match self.issue_id() {
                    Ok(id) => Some(id),
                    Err(NumberNotRecorded) => {
                        recording = false; // stop asking a database that just said no
                        None
                    }
                }
            } else {
                None
            };
            let id = recorded.or_else(|| {
                if issued.is_some() {
                    self.mint_unrecorded()
                } else {
                    None
                }
            });
            match id {
                Some(id) => self.decks[i].set_id(id),
                None => left_out.push(i),
            }
        }
        self.left_out = left_out.len();
        // Highest index first, so earlier indices stay valid while the vectors shrink.
        for &i in left_out.iter().rev() {
            let deck = self.decks.remove(i);
            let key = row_keys.remove(i);
            if deck.name != key {
                self.held_back.push(deck.name);
            }
            self.held_back.push(key);
        }
        // Pass 2 — names: reserve every distinct non-empty name in order; anything empty or duplicate
        // is uniquified against the reserved set.
        let mut seen_names: HashSet<String> = self.held_back.iter().cloned().collect();
        let mut need_name: Vec<usize> = Vec::new();
        for (i, d) in self.decks.iter().enumerate() {
            if !d.name.trim().is_empty() && seen_names.insert(d.name.clone()) {
                continue; // unique as-is
            }
            need_name.push(i);
        }
        for i in need_name {
            let base = if self.decks[i].name.trim().is_empty() {
                "Untitled presentation".to_string()
            } else {
                self.decks[i].name.clone()
            };
            let unique = uniquify(&base, &seen_names);
            seen_names.insert(unique.clone());
            self.decks[i].name = unique;
        }
        // Pass 3 — identities (86ak196cr): every deck keeps a valid uid that no other deck holds;
        // a deck with none (stored before identities existed, or with a damaged value) or with a
        // copy of another deck's gets a fresh one. `set_uid(fresh)` below assigns the minted value
        // OR `None` if minting fails, so a copy never keeps the original's identity -- two decks
        // sharing an identity is the one outcome this pass exists to make impossible.
        let mut held: HashSet<DeckUid> = HashSet::new();
        let mut need_uid: Vec<usize> = Vec::new();
        for (i, d) in self.decks.iter().enumerate() {
            match d.uid() {
                Some(u) if held.insert(u.clone()) => {}
                _ => need_uid.push(i),
            }
        }
        // The backfill is written once and then given up on at the first failed write: a locked or
        // read-only database would otherwise make every remaining deck wait out the busy timeout.
        // Nothing is lost -- the decks are identified in memory, and the next launch retries.
        let mut writing = true;
        for i in need_uid {
            let fresh = self.mint_uid();
            self.decks[i].set_uid(fresh);
            // Persist, so the identity is the same on the next launch. Without this a legacy deck
            // would be given a different one every run and a bundle exported yesterday could not
            // name it today.
            //
            // ONLY when the row the deck was read from is the row a write would land on: `save_one`
            // upserts by the deck's own (in-memory) name, so for a deck whose JSON name differs
            // from its row key -- or whose name pass 2 just changed -- the write would overwrite
            // some OTHER presentation's row, or create a second row for this one. That deck keeps
            // its identity in memory and gets a new one each launch until the row is repaired.
            let lands_on_own_row = row_keys.get(i).is_some_and(|k| *k == self.decks[i].name);
            if writing && self.decks[i].uid().is_some() && lands_on_own_row {
                stats.attempted += 1;
                if !self.persist_one_checked(&self.decks[i]) {
                    stats.failed += 1;
                    writing = false;
                }
            }
        }
        stats
    }

    /// The highest deck number any saved deck holds that is a valid number (non-zero, within
    /// [`MAX_DECK_NUMBER`]); `0` when there is none.
    fn highest_deck_number(&self) -> u64 {
        self.decks
            .iter()
            .map(|d| d.id().0)
            .filter(|id| *id <= MAX_DECK_NUMBER)
            .max()
            .unwrap_or(0)
    }

    /// Make the persisted high-water mark cover the highest number a deck here holds: what lets a
    /// store written before the mark existed start recording from its first load, and what covers
    /// ids the self-heal above just minted. Only ever RAISES it (`deck_repo` takes `MAX` and the
    /// table refuses a lowering UPDATE), so a mark that is ahead of every surviving deck -- the
    /// whole point of it -- is left exactly as it is. Best-effort like every write here: on a
    /// failure the next load retries (new numbers do not depend on it: `issue_number` reconciles).
    ///
    /// Skipped when the identity backfill gave up on a failed write (`backfill_failed`): the database
    /// is locked or read-only, and a second write would wait out the busy timeout again. Also skipped
    /// when the mark cannot be read -- a write to a mark that cannot be read is a guess.
    fn record_high_water(&self, backfill_failed: bool) {
        let Some(db) = &self.db else {
            return;
        };
        if backfill_failed {
            return;
        }
        let highest = self.highest_deck_number();
        if highest == 0 {
            return;
        }
        if let Some(mark) = read_mark(db) {
            if mark < highest {
                let _ = deck_repo::raise_high_water(db, highest);
            }
        }
    }

    /// Whether `uid` already identifies a deck here -- saved, or sitting in the undo-delete trash,
    /// because restoring that deck would otherwise put two decks under one identity.
    fn uid_held(&self, uid: &DeckUid) -> bool {
        self.decks.iter().any(|d| d.uid() == Some(uid))
            || self
                .trashed_decks()
                .into_iter()
                .any(|d| d.uid() == Some(uid))
    }

    /// Mint a deck identity no deck here holds, or `None` if the source has none to give or keeps
    /// offering ones that are refused or held ([`MINT_UID_ATTEMPTS`]). `None` leaves the deck
    /// working and unidentified: it exports as "not identifiable" and so can only ever import as
    /// missing elsewhere, and the next load tries again. It never falls back to a derived or
    /// reused value.
    fn mint_uid(&self) -> Option<DeckUid> {
        for _ in 0..MINT_UID_ATTEMPTS {
            let bytes = (self.entropy)()?;
            if let Some(uid) = DeckUid::from_bytes(bytes) {
                if !self.uid_held(&uid) {
                    return Some(uid);
                }
            }
        }
        None
    }

    /// Give `deck` an identity fit to be added: the one it arrives with when that is valid and free
    /// (so the same presentation keeps its identity as it travels), otherwise a fresh one.
    fn keep_free_uid_or_mint(&self, deck: &mut SlideDeck) {
        let keep = deck.uid().is_some_and(|u| !self.uid_held(u));
        if !keep {
            deck.set_uid(self.mint_uid());
        }
    }

    // --- cross-machine identity (86ak196cr · FINDING-LIB-07 · ADR-0031) ---------------------------

    /// The globally unique identity of the saved deck `id`, or `None` if there is no such deck or it
    /// could not be given one (see [`mint_uid`](Self::mint_uid)). A deck in the undo-delete trash
    /// is not in the library and has no answer here.
    #[allow(dead_code)] // consumed by the plan-bundle export (FR-139, 86ak0qn15)
    pub fn uid_of(&self, id: DeckId) -> Option<DeckUid> {
        self.decks.iter().find(|d| d.id() == id)?.uid().cloned()
    }

    /// The saved deck that carries `uid`, as the facts an imported link is rebuilt from, or `None`.
    /// Only SAVED decks answer: a deleted deck is missing, even if "Undo delete" could bring it
    /// back, because a plan must not claim a presentation the library does not currently hold.
    #[allow(dead_code)] // consumed by the plan-bundle import (FR-139, 86ak0qn15)
    pub fn find_by_uid(&self, uid: &DeckUid) -> Option<LocalDeck> {
        let d = self.decks.iter().find(|d| d.uid() == Some(uid))?;
        Some(LocalDeck {
            id: d.id().0,
            slide_count: u32::try_from(d.len()).unwrap_or(u32::MAX),
            name: d.name.clone(),
        })
    }

    /// A deck link as it may leave this machine: this library's identity for the deck, never its
    /// local number ([`export_deck_link`]). `None` for anything but a deck link.
    #[allow(dead_code)] // consumed by the plan-bundle export (FR-139, 86ak0qn15)
    pub fn export_link(&self, content: &ItemContent) -> Option<PortableDeckLink> {
        export_deck_link(content, |id| self.uid_of(DeckId(id)))
    }

    /// Bind a deck link that arrived from another machine to THIS library: the saved deck with the
    /// same identity, or the missing-content state ([`import_deck_link`]). Never a deck chosen by
    /// the sender's local number. Reads the library only -- it adds, removes and renumbers nothing.
    #[allow(dead_code)] // consumed by the plan-bundle import (FR-139, 86ak0qn15)
    pub fn import_link(&self, link: &PortableDeckLink) -> (ItemContent, DeckLinkMatch) {
        import_deck_link(link, |uid| self.find_by_uid(uid))
    }

    /// The lowest number the counter may hand out next: past `next_id` AND past every valid number
    /// a deck here holds (so a deck adopted with a non-zero number, or a stale `next_id`, can never
    /// make an issue return a live number, which would make `get`/`delete`/`store` target the wrong
    /// deck). Saturating, never panics.
    fn candidate_id(&self) -> u64 {
        self.next_id
            .max(self.highest_deck_number().saturating_add(1))
            .max(1)
    }

    /// Issue a fresh library deck number (monotonic, never reused -- across restarts too, and even
    /// when the deck that gets it fails to write: 17tnw2b9arx). The number is recorded in the deck
    /// database BEFORE it is returned (`deck_repo::issue_number`: one atomic statement that also keeps
    /// two processes on one file from being issued the same number). If the database will not record
    /// it (or the numbers are used up) no number is issued, `next_id` does not move and the caller
    /// must not create anything. A library with no database (the in-memory fallback) has nothing to
    /// record to and issues from the counter alone, bounded by [`MAX_DECK_NUMBER`].
    fn issue_id(&mut self) -> Result<DeckId, NumberNotRecorded> {
        let at_least = self.candidate_id();
        if at_least > MAX_DECK_NUMBER {
            return Err(NumberNotRecorded);
        }
        let issued = match &self.db {
            Some(db) => deck_repo::issue_number(db, at_least).map_err(|_| NumberNotRecorded)?,
            None => at_least,
        };
        self.next_id = issued.saturating_add(1);
        Ok(DeckId(issued))
    }

    /// The counter's next number WITHOUT recording it anywhere: for the load-time repair of a deck whose
    /// number was zero, duplicated or out of range, when the database would not record one (see
    /// [`heal`](Self::heal) and [`issue_id`](Self::issue_id)). `None` once the counter is past
    /// [`MAX_DECK_NUMBER`]: a number above it is never minted, because the webview's JSON numbers would
    /// round it onto its neighbours.
    fn mint_unrecorded(&mut self) -> Option<DeckId> {
        let id = self.candidate_id();
        if id > MAX_DECK_NUMBER {
            return None;
        }
        self.next_id = id.saturating_add(1);
        Some(DeckId(id))
    }

    /// The Library list — decks ordered by name (matches `deck_repo::load_all`'s deterministic order
    /// and the design's default sort). Bounded by the library size (user data, not a leak).
    pub fn list(&self) -> Vec<DeckMeta> {
        let mut metas: Vec<DeckMeta> = self
            .decks
            .iter()
            .map(|d| DeckMeta {
                id: d.id(),
                name: d.name.clone(),
                slides: d.len(),
            })
            .collect();
        metas.sort_by_key(|m| m.name.to_lowercase());
        metas
    }

    /// Whether the library has no decks (the empty-state).
    pub fn is_empty(&self) -> bool {
        self.decks.is_empty()
    }

    /// A clone of the deck with `id` (for opening it into the editor), or `None`.
    pub fn get(&self, id: DeckId) -> Option<SlideDeck> {
        self.decks.iter().find(|d| d.id() == id).cloned()
    }

    fn index_of(&self, id: DeckId) -> Option<usize> {
        self.decks.iter().position(|d| d.id() == id)
    }

    /// The index of the deck holding EXACTLY `name`. Exact, not case- or whitespace-folded, because
    /// [`uniquify`] is exact: any looser comparison here would let a policy decide a name collides
    /// while the uniquify path decides it does not, and the two must never disagree.
    #[allow(dead_code)] // reached via adopt_with_policy, wired in main.rs (ADR-0024)
    fn index_of_name(&self, name: &str) -> Option<usize> {
        self.decks.iter().position(|d| d.name == name)
    }

    /// Create a new **blank** deck (one empty slide, per the design's "Blank deck") with a unique id
    /// and a unique name, persist it, and return it (the caller opens it in the editor).
    ///
    /// `Err(NumberNotRecorded)` when the database would not record the deck's number: nothing was
    /// created (see [`NumberNotRecorded`]). Production callers use this; the test-only `create` is
    /// the same call for tests that have a healthy database and want a deck back.
    pub fn try_create(&mut self, name: &str) -> Result<SlideDeck, NumberNotRecorded> {
        let base = if name.trim().is_empty() {
            "Untitled presentation"
        } else {
            name.trim()
        };
        let unique = uniquify(base, &self.name_set());
        let mut deck = SlideDeck::new(unique);
        let id = self.issue_id()?;
        deck.set_id(id);
        deck.set_uid(self.mint_uid());
        deck.add_slide(); // "One empty slide, ready to edit"
        self.persist_one(&deck);
        self.decks.push(deck.clone());
        Ok(deck)
    }

    /// [`try_create`](Self::try_create) for tests, where the database is healthy: panics on a refusal.
    /// Compiled in tests only, so a production caller must handle the refusal.
    #[cfg(test)]
    #[allow(clippy::unwrap_used)]
    pub fn create(&mut self, name: &str) -> SlideDeck {
        self.try_create(name).unwrap()
    }

    /// Adopt an EXISTING deck (e.g. the startup demo deck) into the library: give it a FRESH number
    /// (whatever number it arrives with is ignored), a unique name, persist it, and return it (the
    /// caller opens it).
    ///
    /// This is [`adopt_with_policy`](Self::adopt_with_policy) under
    /// [`NameCollisionPolicy::KeepBoth`] with no live deck, minus the `Result` that policy can never
    /// produce — `KeepBoth` has no refusal path, so `adopt` stays total and every existing caller is
    /// untouched. Both entry points run the *same* private [`adopt_keep_both`](Self::adopt_keep_both)
    /// body rather than one calling the other through a `Result` it would have to unwrap, so the two
    /// cannot drift apart and no `unwrap`/`expect` enters a non-test path.
    ///
    /// **The adopted deck always gets a FRESH identity**, whatever uid it arrives carrying. A uid
    /// is an unauthenticated claim: a deck from outside can name any uid, including one that
    /// belongs to a presentation at another church, and honouring it would let that deck answer
    /// the plan links meant for the real one. `adopt_trusted_identity` (compiled in tests only,
    /// until an ingress records its trust decision) is the one path that keeps it.
    ///
    /// `Err(NumberNotRecorded)` when the deck needed a new number and the database would not record
    /// one: nothing was added.
    pub fn try_adopt(&mut self, deck: SlideDeck) -> Result<SlideDeck, NumberNotRecorded> {
        self.adopt_keep_both(deck, false)
    }

    /// [`try_adopt`](Self::try_adopt) for tests with a healthy database; compiled in tests only.
    #[cfg(test)]
    #[allow(clippy::unwrap_used)]
    pub fn adopt(&mut self, deck: SlideDeck) -> SlideDeck {
        self.try_adopt(deck).unwrap()
    }

    /// [`try_adopt`](Self::try_adopt), but a valid incoming uid that no deck here holds is KEPT, so the
    /// same presentation keeps its identity as it travels between libraries.
    ///
    /// **No ingress calls this today.** The only decks that reach the library carry no uid (the
    /// presentation importer builds them fresh, the demo deck is built locally), and no feature
    /// carries a deck between machines yet. Whoever adds one must make and record a trust decision
    /// first -- who may assert "this is presentation U" -- because the first deck to claim a uid
    /// wins it (ADR-0031, "A uid is a claim"). Until then every caller uses [`try_adopt`](Self::try_adopt).
    ///
    /// **Compiled in tests only** (`#[cfg(test)]`), on purpose: with no ingress, a production
    /// caller would be a silent trust decision made by whoever typed the call. Gated this way it
    /// fails to compile, so adding one forces the decision through review; lift the gate in the
    /// change that records it.
    #[cfg(test)]
    #[allow(clippy::unwrap_used)]
    pub fn adopt_trusted_identity(&mut self, deck: SlideDeck) -> SlideDeck {
        self.adopt_keep_both(deck, true).unwrap()
    }

    /// The one implementation of "add this deck beside whatever is already here": a FRESH number, a
    /// `(n)`-suffixed name if its own is taken, persist, return. Shared verbatim by
    /// [`try_adopt`](Self::try_adopt), its trusted twin and the `KeepBoth` arm of
    /// [`adopt_with_policy`](Self::adopt_with_policy) (which never trusts: `keep_free_uid` false).
    ///
    /// **The deck's own number is always ignored.** A deck number is this library's private handle and
    /// never crosses a machine (ADR-0031 decision 3), so a foreign one has no value, and keeping it is a
    /// hazard: it could be a number issued here before and retired (the hole the high-water mark
    /// closes, 17tnw2b9arx), or the largest legal number, which would move the mark to the ceiling and
    /// refuse every later create for good. `Err` (nothing added) when the database will not record the
    /// fresh number.
    fn adopt_keep_both(
        &mut self,
        mut deck: SlideDeck,
        keep_free_uid: bool,
    ) -> Result<SlideDeck, NumberNotRecorded> {
        let id = self.issue_id()?;
        deck.set_id(id);
        if keep_free_uid {
            self.keep_free_uid_or_mint(&mut deck);
        } else {
            deck.set_uid(self.mint_uid());
        }
        let base = adopt_base_name(&deck);
        let unique = uniquify(&base, &self.name_set());
        deck.name = unique;
        self.persist_one(&deck);
        self.decks.push(deck.clone());
        Ok(deck)
    }

    /// Adopt `deck`, stating explicitly what to do if its name is already taken (ADR-0024 decision 5).
    ///
    /// `live_deck` is the [`DeckId`] currently live or staged on the audience output, or `None`. It
    /// is passed **in** rather than read out of a presenter the library holds: `DeckLibrary` owns
    /// saved decks and nothing else, and giving it a handle on presenter state would make every
    /// library operation depend on the live pipeline it must never disturb. An `Option<DeckId>`
    /// argument keeps the refusal rule (`Replace` is refused against the live deck, design §11.2 D)
    /// enforceable *inside* the library — where it cannot be forgotten by a caller — while leaving
    /// the library itself presenter-free and unit-testable with no live output at all. The caller
    /// re-supplies it at commit time, because live state can change while a long import parses
    /// (`IMPORT-product-decisions.md` §1).
    ///
    /// **When the name is free, every policy behaves identically** — the deck is adopted under the
    /// name it carries. A policy is a collision *rule*, not a mode.
    ///
    /// **Identity.** A deck this adds always gets a FRESH uid, whatever uid it arrives carrying
    /// (see [`try_adopt`](Self::try_adopt)); `Replace` keeps the target deck's own uid instead.
    ///
    /// On any `Err` nothing was mutated: no deck added, no id minted, no row written.
    #[allow(dead_code)] // consumed by the import commands in main.rs (ADR-0024)
    pub fn adopt_with_policy(
        &mut self,
        deck: SlideDeck,
        policy: NameCollisionPolicy,
        live_deck: Option<DeckId>,
    ) -> Result<SlideDeck, AdoptError> {
        // Resolve the collision on the SAME normalised name `adopt` would have used, so a policy
        // can never disagree with the uniquify path about whether a collision exists.
        let base = adopt_base_name(&deck);
        let Some(i) = self.index_of_name(&base) else {
            // No collision: policy-independent by construction — `uniquify` returns `base` verbatim
            // when it is free, so this is the same adopt for all three.
            return self
                .adopt_keep_both(deck, false)
                .map_err(|NumberNotRecorded| AdoptError::NumberNotRecorded);
        };
        match policy {
            NameCollisionPolicy::KeepBoth => self
                .adopt_keep_both(deck, false)
                .map_err(|NumberNotRecorded| AdoptError::NumberNotRecorded),
            NameCollisionPolicy::Fail => Err(AdoptError::NameTaken),
            // Resolve the collision to the id the NAME holder actually has, then replace by id. The
            // name is how the collision was found; the id is what the replacement is keyed on.
            NameCollisionPolicy::Replace => {
                let target = self.decks[i].id();
                self.replace_deck(target, deck, live_deck)
            }
        }
    }

    /// Overwrite the deck with id `target` with `deck`'s slides, **keeping the target's own
    /// [`DeckId`] and name**, and persist through the ordinary content-upsert path.
    ///
    /// Preserving the id is the whole point, not an implementation detail. The `deck` table's
    /// primary key is the *name*, so the obvious implementations — delete-then-insert, or an upsert
    /// keyed on the name — write the row belonging to a **different** `DeckId` while the in-memory
    /// library still holds the old one. Every `PlanItem` that links the old id
    /// (`ItemContent::Deck { deck_id }`) then resolves to nothing or, worse, to an unrelated deck:
    /// the service plan does not fail loudly, it silently shows the wrong presentation to the
    /// congregation (`FINDING-LIB-07`, ClickUp `86ak196cr`). Because plan links never depended on the
    /// name, keeping the id makes them survive a replace for free — and because the stored name is
    /// kept too, the persisted row is *updated*, never orphaned and re-created.
    ///
    /// Refused, with nothing mutated, when `target` is unknown ([`AdoptError::UnknownTarget`]) or is
    /// the live/staged deck ([`AdoptError::TargetIsLive`]).
    #[allow(dead_code)] // consumed by the import commands in main.rs (ADR-0024)
    pub fn replace_deck(
        &mut self,
        target: DeckId,
        deck: SlideDeck,
        live_deck: Option<DeckId>,
    ) -> Result<SlideDeck, AdoptError> {
        // Both refusals are checked BEFORE any mutation, so an `Err` is always a no-op.
        let Some(i) = self.index_of(target) else {
            return Err(AdoptError::UnknownTarget);
        };
        if live_deck == Some(target) {
            return Err(AdoptError::TargetIsLive);
        }
        let mut updated = deck;
        updated.set_id(target); // the id plan items link — never re-minted
        updated.set_uid(self.decks[i].uid().cloned()); // ...and the identity bundles link
        updated.name = self.decks[i].name.clone(); // the row key — so this upserts, not orphans
        self.decks[i] = updated.clone();
        self.persist_one(&updated);
        Ok(updated)
    }

    /// The saved decks other than `except` — what the media panel counts, alongside the deck the
    /// editor holds live, to decide whether a picture is really unused. `except` is the open deck:
    /// its stored copy here can lag the editor by an edit, and the live one is the truth.
    pub fn saved_decks_except(&self, except: DeckId) -> Vec<&SlideDeck> {
        self.decks.iter().filter(|d| d.id() != except).collect()
    }

    /// The decks "Undo delete" could still bring back (the bounded in-memory trash). Gone from the
    /// Library list, but restoring one resurrects its slides — pictures included.
    pub fn trashed_decks(&self) -> Vec<&SlideDeck> {
        self.trash
            .ids()
            .into_iter()
            .filter_map(|id| self.trash.peek(id))
            .collect()
    }

    /// Which decks **other than the open one** still show the picture at `path`: the saved decks
    /// ([`DeckLibrary::saved_decks_except`]) and the restorable trashed ones. This is the question
    /// Remove must ask before deleting a stored image: the open deck's own slides are the ones the
    /// operator is looking at and was just warned about; the others are out of sight, and a file
    /// deleted from under them leaves them with a missing picture and no undo.
    pub fn media_keepers(&self, path: &str, open: DeckId) -> MediaKeepers {
        let showing = |decks: Vec<&SlideDeck>| {
            decks
                .into_iter()
                .filter(|d| deck_image_paths(d).contains(path))
                .count()
        };
        MediaKeepers {
            saved: showing(self.saved_decks_except(open)),
            trashed: showing(self.trashed_decks()),
        }
    }

    /// Sync the open deck's edited content back into the library and persist it (per-edit autosave).
    /// No-op if `deck` is not a library deck (e.g. an id-less transient). Names are NOT changed here
    /// (that is [`rename`](Self::rename)); if the caller renamed the open deck out of band, the name
    /// is re-uniquified defensively.
    pub fn store(&mut self, deck: &SlideDeck) {
        let Some(i) = self.index_of(deck.id()) else {
            return;
        };
        let old_name = self.decks[i].name.clone();
        let mut updated = deck.clone();
        // The library is the authority on a saved deck's identity: whatever the editor's copy
        // carries (nothing, for a deck it built itself), the identity stays this one.
        updated.set_uid(self.decks[i].uid().cloned());
        // Guard the name-PK invariant even if the caller mutated name directly.
        if updated.name != old_name {
            let unique = uniquify_excluding(&updated.name, &self.name_set(), &old_name);
            updated.name = unique;
        }
        let new_name = updated.name.clone();
        self.decks[i] = updated.clone();
        if new_name != old_name {
            self.persist_rename(&old_name, &updated); // atomic drop-old + upsert-new
        } else {
            self.persist_one(&updated);
        }
    }

    /// Rename the deck with `id` to a unique form of `new_name`; persist. Returns the applied name,
    /// or `None` if `id` is unknown.
    pub fn rename(&mut self, id: DeckId, new_name: &str) -> Option<String> {
        let i = self.index_of(id)?;
        let old_name = self.decks[i].name.clone();
        let base = if new_name.trim().is_empty() {
            "Untitled presentation"
        } else {
            new_name.trim()
        };
        let unique = uniquify_excluding(base, &self.name_set(), &old_name);
        if unique == old_name {
            return Some(old_name); // no change
        }
        self.decks[i].name = unique.clone();
        let deck = self.decks[i].clone();
        self.persist_rename(&old_name, &deck); // atomic drop-old + upsert-new (no lost row on crash)
        Some(unique)
    }

    /// Duplicate the deck with `id` into an independent copy ("<name> copy", unique) with a fresh id;
    /// persist. Returns the new deck (not opened), or `None` if `id` is unknown OR the database would
    /// not record a number for the copy (see [`NumberNotRecorded`]; a caller that must tell the two
    /// apart asks [`get`](Self::get) first).
    pub fn duplicate(&mut self, id: DeckId) -> Option<SlideDeck> {
        let src = self.decks.iter().find(|d| d.id() == id)?.clone();
        let mut copy = src.clone();
        let new_id = self.issue_id().ok()?;
        copy.set_id(new_id);
        copy.set_uid(self.mint_uid()); // a copy is a different presentation, not the same one twice
        let copy_name = uniquify(&format!("{} copy", src.name), &self.name_set());
        copy.name = copy_name;
        self.persist_one(&copy);
        self.decks.push(copy.clone());
        Some(copy)
    }

    /// Delete the deck with `id`; persist. Returns `true` if a deck was removed.
    ///
    /// The deck is retained in a bounded in-memory trash first, so [`restore`](Self::restore)
    /// can put back its real slides, elements, theme and notes. Before this existed the deck was
    /// dropped and its row deleted in the same step, so the only undo a client could offer was
    /// recreating an EMPTY deck of the same name — a lie about what had been restored.
    ///
    /// Use [`can_restore`](Self::can_restore) to decide whether to offer an undo at all: an
    /// unusually large deck may be refused by the bounded trash, and offering an undo that
    /// cannot work would be its own fabrication.
    pub fn delete(&mut self, id: DeckId) -> bool {
        let Some(i) = self.index_of(id) else {
            return false;
        };
        let deck = self.decks.remove(i);
        self.delete_persisted(&deck);
        // Measure HERE, not inside the trash. `selahcue-present` is a normal dependency of
        // `selahcue-import`, whose dependency graph is guarded because it parses hostile
        // documents (`scripts/import_guards.sh`), so a JSON serializer must not be pulled into
        // it just to size a deck. This crate already serializes decks to persist them, so it is
        // measuring the representation it just wrote. `usize::MAX` on a serialization failure
        // refuses retention, which is the safe direction: counting it as zero would admit
        // unbounded content under a byte budget of zero.
        let bytes = deck_bytes(&deck);
        self.trash.push(deck, bytes);
        true
    }

    /// Whether [`restore`](Self::restore) could actually put this deck back.
    pub fn can_restore(&self, id: DeckId) -> bool {
        self.trash.peek(id).is_some()
    }

    /// The deck ids an undo could restore, oldest first.
    pub fn restorable(&self) -> Vec<DeckId> {
        self.trash.ids()
    }

    /// Undo a delete: put the retained deck back into the library and re-persist it.
    ///
    /// Returns the restored deck's name, which may differ from the original: if the name was
    /// taken while the deck sat in the trash, it is uniquified exactly as [`try_create`](Self::try_create)
    /// does. Restoring under a duplicate name would either collide with the live deck or
    /// silently overwrite its persisted row, so the rename is reported rather than hidden — the
    /// caller should tell the operator what the deck is now called.
    ///
    /// The deck keeps its original id: `next_id` is monotonic and never reused (within a session
    /// by the counter, across restarts by the persisted high-water mark), so the id cannot have
    /// been handed to anything else in the meantime.
    pub fn restore(&mut self, id: DeckId) -> Option<String> {
        let mut deck = self.trash.take(id)?;
        deck.name = uniquify(&deck.name, &self.name_set());
        self.persist_one(&deck);
        let name = deck.name.clone();
        self.decks.push(deck);
        Some(name)
    }

    // --- Live Console slide picker: read-only bridge (LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec §6) --

    /// List a saved deck's slides for the Live Console picker — id + a speaker-readable label + a
    /// notes flag, in deck order. `None` when the deck id is unknown (the picker renders its
    /// "presentation missing" state, FR-007). Reads the library only; never loads or mutates the
    /// open editor [`DeckWorkspace`](crate::deck_workspace::DeckWorkspace). Pure and bounded by the
    /// deck's own slide/element caps (no-leak).
    pub fn slide_list(&self, id: DeckId) -> Option<Vec<SlideMeta>> {
        let deck = self.get(id)?;
        Some(
            deck.slides()
                .iter()
                .map(|s| SlideMeta {
                    id: s.id,
                    label: s.confidence_slide().body.into_iter().next(),
                    has_notes: !s.notes.is_empty(),
                })
                .collect(),
        )
    }

    /// Global presentation search (`deck_search`): case-insensitive substring match on deck NAME and
    /// each slide's on-screen text, returning at most `limit` hits — NAME matches (whole deck) before
    /// per-slide CONTENT matches (one hit per matching slide). Decks are visited name-sorted (same
    /// deterministic order as [`list`](Self::list)). Bounded by `limit` and each deck's own slide/
    /// element caps; `confidence_slide()` is a cheap text extraction (no pixel render), so scanning
    /// the whole library is safe. An empty/whitespace query returns no hits. Reads the library only —
    /// never touches the open editor workspace.
    pub fn search(&self, query: &str, limit: usize) -> Vec<SearchHit> {
        let q = query.trim().to_lowercase();
        if q.is_empty() || limit == 0 {
            return Vec::new();
        }
        let mut order: Vec<&SlideDeck> = self.decks.iter().collect();
        order.sort_by_key(|d| d.name.to_lowercase());
        let mut hits: Vec<SearchHit> = Vec::new();
        for deck in order {
            if hits.len() >= limit {
                break;
            }
            // NAME match — the whole presentation.
            if deck.name.to_lowercase().contains(&q) {
                hits.push(SearchHit {
                    deck_id: deck.id().0,
                    name: deck.name.clone(),
                    slide_id: None,
                    slide_index: None,
                    snippet: None,
                    kind: "name",
                });
            }
            // CONTENT match — the first matching text line of each slide (one hit per slide).
            for (i, slide) in deck.slides().iter().enumerate() {
                if hits.len() >= limit {
                    break;
                }
                let matched = slide
                    .confidence_slide()
                    .body
                    .into_iter()
                    .find(|line| line.to_lowercase().contains(&q));
                if let Some(line) = matched {
                    hits.push(SearchHit {
                        deck_id: deck.id().0,
                        name: deck.name.clone(),
                        slide_id: Some(slide.id.0),
                        slide_index: Some(i),
                        snippet: Some(search_snippet(&line, 80)),
                        kind: "content",
                    });
                }
            }
        }
        hits.truncate(limit);
        hits
    }

    /// Render ONE slide of a saved deck to a bounded RGBA framebuffer for the picker/preview — the
    /// SAME native compositor and preview theme ([`Theme::dark`]) as the editor canvas, so a
    /// filmstrip thumbnail matches the editor. `None` when the deck OR slide id is unknown.
    /// Dimensions are clamped (≤960×540, mirroring the editor's own preview) so a hostile/oversized
    /// request can never allocate without bound (no-leak). Reads the library only — the open editor
    /// workspace is never loaded or mutated. Routing these pixels to the physical audience output is
    /// a separate seam (Dep 2, ADR ~0022); this is Preview/thumbnail composition only.
    pub fn render_slide(
        &self,
        deck_id: DeckId,
        slide_id: SlideId,
        max_w: u32,
        max_h: u32,
    ) -> Option<FrameBuffer> {
        let deck = self.get(deck_id)?;
        let slide = deck.get(slide_id)?;
        let w = max_w.clamp(1, 960);
        let h = max_h.clamp(1, 540);
        Some(render_authored_slide(slide, &Theme::dark(), w, h))
    }

    /// The `(slide_json, theme_json)` for ONE slide of a SAVED deck — the payload the console sends
    /// via `present_authored_slide` to route a plan-linked presentation slide to the LIVE audience
    /// output (the SAME authored-slide present path the deck editor's `deck_go_live` uses, but for a
    /// plan-linked saved deck rather than the open workspace). `None` when the deck OR slide id is
    /// unknown or serialization fails. Theme = [`Theme::dark`] (the console preview theme), so the
    /// audience output matches the filmstrip thumbnail. Reads the library only.
    pub fn present_payload(
        &self,
        deck_id: DeckId,
        slide_id: SlideId,
    ) -> Option<(String, String, Option<String>)> {
        let deck = self.get(deck_id)?;
        let idx = deck.index_of(slide_id)?;
        let slide = deck.get_index(idx)?;
        let slide_json = serde_json::to_string(slide).ok()?;
        let theme_json = serde_json::to_string(&Theme::dark()).ok()?;
        // The COMING deck slide feeds the host Stage/Confidence monitor's "next" (Approach A). `None`
        // at the end of the deck (no wrap).
        let next_json = deck
            .get_index(idx + 1)
            .and_then(|next| serde_json::to_string(next).ok());
        Some((slide_json, theme_json, next_json))
    }

    // --- persistence (best-effort; a DB error is swallowed, never blocks editing) ---

    fn persist_one(&self, deck: &SlideDeck) {
        let _ = self.persist_one_checked(deck);
    }

    /// [`persist_one`](Self::persist_one), reporting whether a write that was attempted failed.
    /// `true` when it succeeded or there was nothing to write to (the in-memory fallback).
    fn persist_one_checked(&self, deck: &SlideDeck) -> bool {
        let Some(db) = &self.db else {
            return true;
        };
        match serde_json::to_string(deck) {
            // Numbered: the row and the high-water mark (>= this deck's number) commit together.
            Ok(json) => deck_repo::save_one_numbered(db, &deck.name, &json, deck.id().0).is_ok(),
            Err(_) => false,
        }
    }

    /// Remove the deck's row and record its number as retired in the same transaction, so the number
    /// is never reissued even when nothing else wrote the mark (17tnw2b9arx).
    fn delete_persisted(&self, deck: &SlideDeck) {
        if let Some(db) = &self.db {
            let _ = deck_repo::delete_one_numbered(db, &deck.name, deck.id().0);
        }
    }

    /// Atomically move a deck's on-disk row from `old_name` to `deck.name` (one transaction) — a
    /// crash mid-rename can never lose the row. Best-effort (a DB error is swallowed).
    fn persist_rename(&self, old_name: &str, deck: &SlideDeck) {
        if let Some(db) = &self.db {
            if let Ok(json) = serde_json::to_string(deck) {
                let _ =
                    deck_repo::rename_one_numbered(db, old_name, &deck.name, &json, deck.id().0);
            }
        }
    }

    /// Every name a new deck must avoid: the saved decks' and those left out at load (their rows are
    /// still on disk and a new deck with the same name would overwrite them).
    fn name_set(&self) -> std::collections::HashSet<String> {
        self.decks
            .iter()
            .map(|d| d.name.clone())
            .chain(self.held_back.iter().cloned())
            .collect()
    }
}

/// The name an adopted deck is filed under before uniqueness is applied: its own name, trimmed,
/// falling back to `"Untitled presentation"` when it carries none. Factored out so collision
/// detection and the `(n)` suffixing operate on the *same* string — if one trimmed and the other did
/// not, `"Sermon "` would be judged collision-free and then filed as `"Sermon (2)"`, which is
/// exactly the silent fork the policy argument exists to prevent. (A caller with a better fallback —
/// import uses `"Imported presentation"` — supplies it in the deck's own name; the library's
/// fallback is unchanged so no existing behaviour moves.)
fn adopt_base_name(deck: &SlideDeck) -> String {
    let trimmed = deck.name.trim();
    if trimmed.is_empty() {
        "Untitled presentation".to_string()
    } else {
        trimmed.to_string()
    }
}

/// The deck-number high-water mark, retried once: `None` only if it cannot be read twice running (a
/// damaged value or a database that is not answering). An absent row is `Some(0)`, not `None`.
fn read_mark(db: &Database) -> Option<u64> {
    (0..2).find_map(|_| deck_repo::high_water(db).ok())
}

/// A deck's serialized size — the same representation [`DeckLibrary::persist_one`] writes, so the
/// retention byte budget reflects real stored cost rather than a field-count guess.
///
/// `usize::MAX` when the deck cannot be serialized: that refuses retention, which is the safe
/// direction. Reporting zero would let arbitrarily large content in under any byte budget.
///
/// **That arm is currently unreachable, and no test covers it.** `serde_json` fails on
/// non-finite floats and non-string map keys, and the deck/theme types contain neither — they
/// have no float fields at all, which `serialization_of_a_populated_deck_cannot_fail` pins. It
/// is kept as the safe default for the day someone adds one, not as a branch believed tested.
fn deck_bytes(deck: &SlideDeck) -> usize {
    serde_json::to_string(deck)
        .map(|s| s.len())
        .unwrap_or(usize::MAX)
}

/// Return `base` if unused, else `base (2)`, `base (3)`, … — the first form not in `taken`. Total
/// and collision-free: it searches until a free suffix is found, guaranteed within `|taken|+1`
/// iterations (there are only `|taken|` names to dodge), so it can never return a taken name.
fn uniquify(base: &str, taken: &std::collections::HashSet<String>) -> String {
    if !taken.contains(base) {
        return base.to_string();
    }
    let mut n = 2u64;
    loop {
        let cand = format!("{base} ({n})");
        if !taken.contains(&cand) {
            return cand;
        }
        n += 1;
    }
}

/// Like [`uniquify`] but treats `keep` as free (renaming a deck to a suffix of its own base).
fn uniquify_excluding(base: &str, taken: &std::collections::HashSet<String>, keep: &str) -> String {
    let mut set = taken.clone();
    set.remove(keep);
    uniquify(base, &set)
}

// Cross-machine identity tests (86ak196cr / FINDING-LIB-07) live beside the library, in their own
// file, because they are about the boundary between two libraries rather than about one.
#[cfg(test)]
mod identity_tests;

// Deck-number reuse across restarts (17tnw2b9arx): its own file for the same reason, and because
// every test in it needs a real database file and a simulated restart.
#[cfg(test)]
mod deck_number_tests;

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used)]
    use super::*;

    #[test]
    fn in_memory_library_is_not_persistent_and_starts_empty() {
        let lib = DeckLibrary::load(None);
        assert!(!lib.is_persistent());
        assert!(lib.is_empty());
        assert!(lib.list().is_empty());
    }

    #[test]
    fn create_mints_unique_ids_and_names_with_one_slide() {
        let mut lib = DeckLibrary::load(None);
        let a = lib.create("Sermon");
        let b = lib.create("Sermon"); // same display name → uniquified
        let c = lib.create("   "); // blank → "Untitled presentation"
        assert_ne!(a.id(), b.id(), "distinct ids");
        assert_ne!(a.id().0, 0, "assigned a non-zero id");
        assert_eq!(a.name, "Sermon");
        assert_eq!(b.name, "Sermon (2)", "duplicate name uniquified");
        assert_eq!(c.name, "Untitled presentation");
        assert_eq!(a.len(), 1, "a blank deck has one editable slide");
        assert_eq!(lib.list().len(), 3);
    }

    /// An image element showing `path`.
    fn image_el(path: &str) -> selahcue_present::Element {
        selahcue_present::Element::Image {
            x_permille: 0,
            y_permille: 0,
            w_permille: 1000,
            h_permille: 1000,
            source: selahcue_present::MediaRef::new(path).unwrap(),
            opacity: 255,
            z: 0,
            visible: true,
            fit: selahcue_present::ImageFit::default(),
        }
    }

    /// A saved deck whose first slide shows `path`.
    fn deck_showing(lib: &mut DeckLibrary, name: &str, path: &str) -> DeckId {
        let mut deck = lib.create(name);
        let sid = deck.slides()[0].id;
        deck.get_mut(sid).unwrap().elements.push(image_el(path));
        lib.store(&deck);
        deck.id()
    }

    /// A saved deck that shows `path` ONLY as its first slide's image background — no image element
    /// anywhere — so nothing but the background branch of "this slide shows that file" can see it.
    fn deck_with_background_only(lib: &mut DeckLibrary, name: &str, path: &str) -> DeckId {
        let mut deck = lib.create(name);
        let sid = deck.slides()[0].id;
        deck.get_mut(sid).unwrap().background = Some(selahcue_present::Background::Image(
            selahcue_present::ImageBackground {
                source: selahcue_present::MediaRef::new(path).unwrap(),
            },
        ));
        lib.store(&deck);
        deck.id()
    }

    #[test]
    fn a_deck_that_shows_a_picture_only_as_its_background_still_keeps_it() {
        let mut lib = DeckLibrary::load(None);
        let open = deck_showing(&mut lib, "Sunday", "/m/elsewhere.png");
        let easter = deck_with_background_only(&mut lib, "Easter", "/m/banner.png");
        // Premise: no image ELEMENT shows it, so only the background branch can find it.
        let easter_deck = lib.get(easter).unwrap();
        assert!(
            easter_deck.slides().iter().all(|s| !s
                .elements
                .iter()
                .any(|e| matches!(e, selahcue_present::Element::Image { .. }))),
            "premise: the deck has no image element"
        );

        assert_eq!(
            lib.media_keepers("/m/banner.png", open),
            MediaKeepers {
                saved: 1,
                trashed: 0
            },
            "a picture used as a slide BACKGROUND is a use: deleting its file blanks that slide"
        );
        // Positive control: the deck's other path is not kept by it.
        assert_eq!(
            lib.media_keepers("/m/other.png", open),
            MediaKeepers::default()
        );
        // And the same through the undo-trash.
        assert!(lib.delete(easter));
        assert_eq!(
            lib.media_keepers("/m/banner.png", open),
            MediaKeepers {
                saved: 0,
                trashed: 1
            }
        );
    }

    #[test]
    fn media_keepers_counts_other_saved_decks_and_restorable_deleted_ones_never_the_open_deck() {
        let mut lib = DeckLibrary::load(None);
        let open = deck_showing(&mut lib, "Sunday", "/m/banner.png");
        let easter = deck_showing(&mut lib, "Easter", "/m/banner.png");
        let _other = deck_showing(&mut lib, "Youth", "/m/other.png");

        // The open deck's stored copy shows the banner too, and is NOT counted: the editor holds
        // the live deck, and a stale stored copy must not keep a file alive (or shrink "unused").
        assert_eq!(
            lib.media_keepers("/m/banner.png", open),
            MediaKeepers {
                saved: 1,
                trashed: 0
            },
            "Easter is the one other deck showing it"
        );
        assert_eq!(
            lib.saved_decks_except(open).len(),
            2,
            "every saved deck except the open one"
        );
        // Positive control: nothing shows this path, so nothing keeps it.
        let none = lib.media_keepers("/m/nobody.png", open);
        assert_eq!(none, MediaKeepers::default());
        assert!(!none.any());

        // Deleting Easter takes it out of the Library list but "Undo delete" can bring it back
        // with its pictures, so it still counts — as a trashed keeper, not a saved one.
        assert!(lib.delete(easter));
        let kept = lib.media_keepers("/m/banner.png", open);
        assert_eq!(
            kept,
            MediaKeepers {
                saved: 0,
                trashed: 1
            }
        );
        assert!(kept.any(), "a restorable deck is enough to keep the file");

        // Restoring puts it back among the saved decks.
        assert!(lib.restore(easter).is_some());
        assert_eq!(
            lib.media_keepers("/m/banner.png", open),
            MediaKeepers {
                saved: 1,
                trashed: 0
            }
        );
    }

    #[test]
    fn slide_list_lists_slides_with_labels_and_notes_flag() {
        let mut lib = DeckLibrary::load(None);
        let mut deck = lib.create("Sermon"); // starts with one editable slide
        let s2 = deck.add_slide().unwrap();
        deck.get_mut(s2).unwrap().notes = "Closing prayer".into();
        lib.store(&deck); // sync the edit back into the library

        let metas = lib
            .slide_list(deck.id())
            .expect("a known deck lists its slides");
        assert_eq!(metas.len(), 2, "both slides listed, in deck order");
        assert_eq!(metas[1].id, s2);
        assert!(metas[1].has_notes, "the slide with notes is flagged");
        assert_eq!(
            metas[1].label.as_deref(),
            Some("Closing prayer"),
            "label falls back to a notes line when there is no on-screen text"
        );
        assert!(!metas[0].has_notes, "the default slide carries no notes");
    }

    /// A visible slide text box carrying `s` (mirrors the editor's `text_element` seed) so a test
    /// can author searchable on-screen content.
    fn text_el(s: &str) -> selahcue_present::Element {
        use selahcue_present::{Element, Fit, Rgba, TextAlign, VAlign};
        Element::Text {
            x_permille: 100,
            y_permille: 100,
            w_permille: 800,
            h_permille: 200,
            text: s.to_string(),
            color: Rgba::rgb(240, 240, 245),
            size_permille: 90,
            line_height_permille: 1100,
            align_h: TextAlign::Left,
            align_v: VAlign::Top,
            fit: Fit::ShrinkToFit,
            opacity: 255,
            z: 0,
            font: None,
            weight: 400,
            letter_spacing_permille: 0,
            visible: true,
        }
    }

    #[test]
    fn search_matches_names_and_slide_content_and_is_bounded() {
        let mut lib = DeckLibrary::load(None);
        // A deck whose NAME matches "grace".
        lib.create("Grace Fellowship");
        // A deck whose name does NOT match, but a slide's on-screen TEXT contains "amazing grace".
        let mut hymns = lib.create("Hymnbook"); // one blank slide
        let sid = hymns.slides()[0].id;
        hymns
            .get_mut(sid)
            .unwrap()
            .elements
            .push(text_el("Amazing Grace, how sweet the sound"));
        lib.store(&hymns); // sync the authored text back into the library

        // NAME query → a name hit (whole deck, no slide fields).
        let by_name = lib.search("grace", 50);
        assert!(
            by_name
                .iter()
                .any(|h| h.name == "Grace Fellowship" && h.kind == "name" && h.slide_id.is_none()),
            "a deck whose NAME matches is a name hit"
        );

        // CONTENT query → a content hit via slide text, with the matched slide id/index + a snippet.
        let by_content = lib.search("amazing grace", 50);
        let hit = by_content
            .iter()
            .find(|h| h.kind == "content")
            .expect("a slide-content hit");
        assert_eq!(hit.name, "Hymnbook");
        assert!(hit.slide_id.is_some() && hit.slide_index == Some(0));
        assert!(hit
            .snippet
            .as_deref()
            .unwrap()
            .to_lowercase()
            .contains("amazing grace"));

        // No match / empty query → no hits (empty query never scans).
        assert!(lib.search("zzz-not-found", 50).is_empty());
        assert!(lib.search("   ", 50).is_empty());

        // The result cap is honoured (both decks match "e"; cap to 1).
        assert!(
            lib.search("e", 1).len() <= 1,
            "search is bounded by the limit"
        );
    }

    #[test]
    fn slide_list_is_none_for_an_unknown_deck() {
        let lib = DeckLibrary::load(None);
        assert!(
            lib.slide_list(DeckId(999_999)).is_none(),
            "unknown deck → None"
        );
    }

    #[test]
    fn render_library_slide_is_bounded_and_matches_the_editor_theme() {
        let mut lib = DeckLibrary::load(None);
        let deck = lib.create("Sermon");
        let sid = deck.slides()[0].id;

        let fb = lib
            .render_slide(deck.id(), sid, 320, 180)
            .expect("a known deck+slide renders");
        assert!(
            fb.width() > 0 && fb.height() > 0,
            "never a blank/zero frame (NFR-024)"
        );
        assert!(
            fb.width() <= 320 && fb.height() <= 180,
            "honours the request"
        );

        // An oversized request is clamped — no unbounded allocation (no-leak).
        let big = lib
            .render_slide(deck.id(), sid, 5000, 5000)
            .expect("renders, clamped");
        assert!(
            big.width() <= 960 && big.height() <= 540,
            "dimensions clamped to the preview bound"
        );
    }

    #[test]
    fn render_library_slide_is_none_for_unknown_deck_or_slide() {
        let mut lib = DeckLibrary::load(None);
        let deck = lib.create("Sermon");
        let sid = deck.slides()[0].id;
        assert!(
            lib.render_slide(DeckId(999_999), sid, 320, 180).is_none(),
            "unknown deck → None"
        );
        assert!(
            lib.render_slide(deck.id(), SlideId(888_888), 320, 180)
                .is_none(),
            "unknown slide → None"
        );
    }

    #[test]
    fn present_payload_serialises_a_saved_deck_slide_or_none_for_unknown() {
        let mut lib = DeckLibrary::load(None);
        let deck = lib.create("Sermon");
        let sid = deck.slides()[0].id;
        let (slide_json, theme_json, next_json) = lib
            .present_payload(deck.id(), sid)
            .expect("a known deck+slide yields a present payload");
        assert!(
            slide_json.contains("\"id\""),
            "the slide serialises to JSON"
        );
        assert!(!theme_json.is_empty(), "the theme serialises");
        assert!(
            next_json.is_none(),
            "a single-slide deck has no coming slide (end of deck)"
        );
        assert!(
            lib.present_payload(DeckId(999_999), sid).is_none(),
            "unknown deck → None"
        );
        assert!(
            lib.present_payload(deck.id(), SlideId(888_888)).is_none(),
            "unknown slide → None"
        );
    }

    #[test]
    fn present_payload_supplies_the_coming_slide_before_the_last() {
        // Before the last slide, the payload carries the NEXT deck slide (Approach A) so the host
        // confidence/stage monitor's "next" is deck-aware.
        let mut lib = DeckLibrary::load(None);
        let mut deck = lib.create("Deck");
        deck.add_slide(); // 2 slides now
        lib.store(&deck);
        let first = deck.slides()[0].id;
        let (_, _, next_json) = lib
            .present_payload(deck.id(), first)
            .expect("a known deck+slide yields a present payload");
        let next_json = next_json.expect("a non-last slide has a coming slide");
        let next: selahcue_present::AuthoredSlide =
            serde_json::from_str(&next_json).expect("next_json is a valid AuthoredSlide");
        assert_eq!(
            next.id,
            deck.slides()[1].id,
            "the coming slide is the NEXT slide in deck order"
        );
    }

    #[test]
    fn store_autosaves_the_open_deck_content() {
        let mut lib = DeckLibrary::load(None);
        let mut deck = lib.create("Deck");
        deck.add_slide(); // now 2 slides
        lib.store(&deck);
        assert_eq!(lib.get(deck.id()).unwrap().len(), 2, "the edit synced back");
    }

    #[test]
    fn rename_is_unique_and_duplicate_makes_an_independent_copy() {
        let mut lib = DeckLibrary::load(None);
        let a = lib.create("Grace");
        let _b = lib.create("Grace copy"); // occupy the natural duplicate name
        let dup = lib.duplicate(a.id()).unwrap();
        assert_ne!(dup.id(), a.id());
        assert_eq!(dup.name, "Grace copy (2)", "copy name avoids the taken one");
        // Rename to an existing name → uniquified; renaming to its own name is a no-op.
        let applied = lib.rename(dup.id(), "Grace").unwrap();
        assert_eq!(applied, "Grace (2)");
        assert_eq!(
            lib.rename(a.id(), "Grace").unwrap(),
            "Grace",
            "self-rename no-op"
        );
    }

    /// The premise that makes `deck_bytes`' error arm unreachable.
    ///
    /// A mutation replacing `unwrap_or(usize::MAX)` with `unwrap_or(0)` SURVIVES the battery,
    /// because nothing can make a deck fail to serialize: `serde_json` errors on non-finite
    /// floats and non-string map keys, and these types have no float fields at all. Rather than
    /// leave that as an unexamined belief, this pins it — a fully populated deck serializes
    /// cleanly. If a float field is ever added and a NaN reaches here, the fallback is the safe
    /// direction, but this test is the record that the arm is unreached rather than verified.
    #[test]
    fn serialization_of_a_populated_deck_cannot_fail() {
        let mut lib = DeckLibrary::load(None);
        let id = lib.create("Sermon").id();
        let mut deck = lib.get(id).unwrap();
        for _ in 0..20 {
            let Some(sid) = deck.add_slide() else { break };
            if let Some(slide) = deck.get_mut(sid) {
                slide.notes = "notes with unicode: \u{2603} \u{1f600}".repeat(20);
            }
        }
        assert!(
            serde_json::to_string(&deck).is_ok(),
            "deck serialization must be infallible — this is what makes deck_bytes' error \
             arm unreachable, and the reason no test exercises it"
        );
        assert!(
            deck_bytes(&deck) < usize::MAX,
            "so the fallback is never taken"
        );
    }

    /// Positive control for the measurement that moved out of `selahcue-present`.
    ///
    /// The trash now takes a size from its caller, so nothing in that crate proves the number is
    /// real. If this measurement silently returned zero, every deck would look free and the byte
    /// budget would stop binding; if it returned `usize::MAX`, every delete would refuse
    /// retention and undo would quietly vanish. Both failures are invisible to the trash's own
    /// tests, which supply sizes directly — so they are checked here, at the only site that
    /// measures.
    #[test]
    fn a_real_decks_measured_size_flows_through_the_delete_path() {
        let mut lib = DeckLibrary::load(None);
        let id = lib.create("Sermon").id();
        let deck = lib.get(id).unwrap();

        let measured = deck_bytes(&deck);
        assert_eq!(
            measured,
            serde_json::to_string(&deck).unwrap().len(),
            "the size must be the SERIALIZED length the library persists, not a guess"
        );
        assert!(
            measured > 0 && measured < selahcue_present::MAX_TRASH_BYTES,
            "premise: a normal deck is measurable and comfortably retainable ({measured} bytes)"
        );

        assert!(lib.delete(id));
        assert!(
            lib.can_restore(id),
            "a normally-sized deck must actually be retained — otherwise the measurement is \
             refusing everything and undo is dead while every other test still passes"
        );
    }

    /// Undo must restore the deck's REAL content. This is the whole reason the seam exists:
    /// a client-side undo could only recreate an empty deck of the same name.
    #[test]
    fn restore_puts_back_the_real_slides_not_an_empty_deck() {
        let mut lib = DeckLibrary::load(None);
        let deck = lib.create("Sermon");
        let id = deck.id();
        // `create` gives one slide; add more so "restored the content" is falsifiable.
        let mut edited = lib.get(id).unwrap();
        for _ in 0..4 {
            edited.add_slide();
        }
        lib.replace_deck(id, edited, None).unwrap();
        let slides_before = lib.get(id).unwrap().len();
        assert!(slides_before >= 5, "premise: the deck has real content");

        assert!(lib.delete(id));
        assert!(lib.get(id).is_none(), "premise: it was deleted");
        assert!(
            lib.can_restore(id),
            "a just-deleted deck must be restorable"
        );

        assert_eq!(lib.restore(id).as_deref(), Some("Sermon"));
        let back = lib.get(id).expect("the deck must be back in the library");
        assert_eq!(
            back.len(),
            slides_before,
            "undo must restore the SLIDES — an empty deck of the same name is a lie about \
             what was restored"
        );
        assert_eq!(
            back.id(),
            id,
            "the id must survive, since it is never reused"
        );
    }

    /// If the name was taken while the deck sat in the trash, restoring must uniquify rather
    /// than collide with the live deck or overwrite its persisted row — and must REPORT the new
    /// name, because the operator's presentation is now called something else.
    #[test]
    fn restoring_into_a_taken_name_uniquifies_and_reports_it() {
        let mut lib = DeckLibrary::load(None);
        let id = lib.create("Sermon").id();
        assert!(lib.delete(id));
        // Something else claims the name while the original is in the trash.
        lib.create("Sermon");

        let restored = lib.restore(id).expect("still restorable");
        assert_ne!(
            restored, "Sermon",
            "restoring must not collide with the deck that took the name"
        );
        assert!(restored.starts_with("Sermon"), "got {restored}");
        assert_eq!(lib.get(id).unwrap().name, restored);
        // Both decks coexist, each with its own id.
        assert_eq!(lib.list().len(), 2);
    }

    #[test]
    fn a_deck_that_was_never_deleted_is_not_restorable() {
        let mut lib = DeckLibrary::load(None);
        let id = lib.create("Sermon").id();
        assert!(!lib.can_restore(id));
        assert_eq!(lib.restore(id), None, "there is nothing to put back");
        assert!(lib.get(id).is_some(), "and the live deck is untouched");
    }

    #[test]
    fn restoring_twice_does_not_duplicate_the_deck() {
        let mut lib = DeckLibrary::load(None);
        let id = lib.create("Sermon").id();
        lib.delete(id);
        assert!(lib.restore(id).is_some());
        assert_eq!(
            lib.restore(id),
            None,
            "a restored deck has left the trash; a second undo must not clone it"
        );
        assert_eq!(lib.list().len(), 1);
    }

    /// The trash is bounded, so an old delete becomes unrestorable. `can_restore` must track
    /// that, or the UI offers an undo that fails.
    #[test]
    fn an_evicted_delete_is_honestly_reported_as_unrestorable() {
        let mut lib = DeckLibrary::load(None);
        let first = lib.create("First").id();
        lib.delete(first);
        assert!(lib.can_restore(first), "premise: retained at first");

        for i in 0..selahcue_present::MAX_TRASH_ENTRIES {
            let id = lib.create(&format!("Filler {i}")).id();
            lib.delete(id);
        }

        assert!(
            !lib.can_restore(first),
            "the oldest delete must age out of a bounded trash"
        );
        assert_eq!(lib.restore(first), None);
        assert!(
            !lib.restorable().contains(&first),
            "and it must not be listed as restorable — an affordance built on this list would \
             otherwise offer an undo that cannot work"
        );
    }

    #[test]
    fn delete_removes_only_the_target() {
        let mut lib = DeckLibrary::load(None);
        let a = lib.create("A");
        let b = lib.create("B");
        assert!(lib.delete(a.id()));
        assert!(!lib.delete(a.id()), "second delete is a no-op");
        assert_eq!(lib.list().len(), 1);
        assert_eq!(lib.get(b.id()).unwrap().name, "B");
    }

    #[test]
    fn self_heals_missing_and_duplicate_ids_and_names_on_load() {
        // A tampered/legacy blob set: two decks with id 0, two sharing id 7, duplicate names.
        let db = selahcue_data::Database::open_in_memory().unwrap();
        deck_repo::save_one(&db, "Dup", r#"{"name":"Dup","slides":[],"next_id":1}"#).unwrap();
        // A second row can't share the PK name, so give it a distinct name but a colliding id.
        deck_repo::save_one(
            &db,
            "Seven A",
            r#"{"name":"Seven A","id":7,"slides":[],"next_id":1}"#,
        )
        .unwrap();
        deck_repo::save_one(
            &db,
            "Seven B",
            r#"{"name":"Seven B","id":7,"slides":[],"next_id":1}"#,
        )
        .unwrap();
        let lib = DeckLibrary::load(Some(db));
        let metas = lib.list();
        assert_eq!(metas.len(), 3);
        let ids: std::collections::HashSet<u64> = metas.iter().map(|m| m.id.0).collect();
        assert_eq!(ids.len(), 3, "all ids unique after heal");
        assert!(!ids.contains(&0), "no unassigned id remains");
        let names: std::collections::HashSet<&str> =
            metas.iter().map(|m| m.name.as_str()).collect();
        assert_eq!(names.len(), 3, "all names unique after heal");
    }

    #[test]
    fn adopt_keeping_a_nonzero_id_never_lets_a_later_mint_collide() {
        // Review regression: adopt keeps a deck's own non-zero id; the next mint must not return it.
        // `mint_id` self-heals past every existing id (mirrors SlideDeck::mint_id).
        let mut lib = DeckLibrary::load(None); // next_id starts at 1
        let mut d = SlideDeck::new("Kept");
        d.set_id(DeckId(1)); // non-zero, and equal to next_id
        let adopted = lib.adopt(d);
        assert_eq!(adopted.id(), DeckId(1), "adopt kept its own id");
        let created = lib.create("Fresh");
        assert_ne!(
            created.id(),
            adopted.id(),
            "the next mint jumps past the kept id — no collision"
        );
    }

    #[test]
    fn library_survives_a_reopen_of_the_same_db_file() {
        let dir = std::env::temp_dir().join(format!("selahcue-lib-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("lib.sqlite");
        let (grace_id, sermon_id);
        {
            let mut lib = DeckLibrary::load(Some(selahcue_data::Database::open(&path).unwrap()));
            let mut g = lib.create("Grace");
            g.add_slide();
            g.add_slide(); // 3 slides
            lib.store(&g);
            let s = lib.create("Sermon");
            grace_id = g.id();
            sermon_id = s.id();
        }
        {
            let lib = DeckLibrary::load(Some(selahcue_data::Database::open(&path).unwrap()));
            assert_eq!(lib.list().len(), 2, "both decks survived the reopen");
            assert_eq!(
                lib.get(grace_id).unwrap().len(),
                3,
                "Grace's 3 slides persisted"
            );
            assert!(lib.get(sermon_id).is_some(), "the stable id round-tripped");
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    // --- adopt_with_policy (ADR-0024 decision 5) ------------------------------------------------

    /// A deck named `name` carrying `slides` slides — stands in for a parsed import.
    fn incoming(name: &str, slides: usize) -> SlideDeck {
        let mut d = SlideDeck::new(name);
        for _ in 0..slides {
            d.add_slide();
        }
        d
    }

    #[test]
    fn replace_updates_in_place_preserving_the_deck_id_that_plan_items_link() {
        // FINDING-LIB-07 / 86ak196cr: the id is what `ItemContent::Deck { deck_id }` holds. If a
        // replace re-mints it, every plan link silently resolves to nothing or to another deck.
        let mut lib = DeckLibrary::load(None);
        let original = lib.create("Sunday Service"); // 1 slide
        let id_before = original.id();
        assert_eq!(original.len(), 1);

        let replaced = lib
            .adopt_with_policy(
                incoming("Sunday Service", 7),
                NameCollisionPolicy::Replace,
                None,
            )
            .expect("replacing a non-live deck is allowed");

        assert_eq!(
            replaced.id(),
            id_before,
            "the DeckId is byte-identical — plan links survive"
        );
        assert_eq!(replaced.name, "Sunday Service", "no (n) suffix was minted");
        assert_eq!(lib.list().len(), 1, "replaced in place, not added beside");
        let stored = lib
            .get(id_before)
            .expect("the deck is still reachable by its ORIGINAL id");
        assert_eq!(stored.len(), 7, "the slides were swapped for the new ones");
        assert_eq!(stored.id(), id_before);
    }

    #[test]
    fn replace_against_the_live_deck_is_refused_and_mutates_nothing() {
        // "staging never changes Live" — refused outright, never queued (design §11.2 D).
        let mut lib = DeckLibrary::load(None);
        let live = lib.create("Sunday Service");
        let other = lib.create("Midweek");
        let before: Vec<DeckMeta> = lib.list();
        let live_content = lib.get(live.id()).expect("live deck present");
        let other_content = lib.get(other.id()).expect("other deck present");

        let err = lib
            .adopt_with_policy(
                incoming("Sunday Service", 42),
                NameCollisionPolicy::Replace,
                Some(live.id()),
            )
            .expect_err("replacing the deck on the audience output is refused");
        assert_eq!(err, AdoptError::TargetIsLive);

        assert_eq!(lib.list(), before, "deck list, ids and names are unchanged");
        assert_eq!(
            lib.get(live.id()).as_ref(),
            Some(&live_content),
            "the live deck's content is untouched"
        );
        assert_eq!(
            lib.get(other.id()).as_ref(),
            Some(&other_content),
            "no collateral change"
        );
    }

    #[test]
    fn replace_targets_the_name_holder_and_cannot_corrupt_a_different_deck() {
        // The imported deck carries ANOTHER library deck's id. Replace resolves the target by NAME
        // and keys the write on that target's id, so the id it happened to carry is irrelevant.
        let mut lib = DeckLibrary::load(None);
        let sermon = lib.create("Sermon");
        let mut notes = lib.create("Notes");
        notes.add_slide();
        notes.add_slide(); // 3 slides
        lib.store(&notes);

        let mut hostile = incoming("Sermon", 5);
        hostile.set_id(notes.id()); // claims to BE the other deck

        let replaced = lib
            .adopt_with_policy(hostile, NameCollisionPolicy::Replace, None)
            .expect("replace proceeds");

        assert_eq!(
            replaced.id(),
            sermon.id(),
            "resolved by name — not by the id the incoming deck claimed"
        );
        assert_eq!(lib.get(sermon.id()).map(|d| d.len()), Some(5));
        let survivor = lib.get(notes.id()).expect("the other deck still exists");
        assert_eq!(survivor.name, "Notes", "its name is intact");
        assert_eq!(survivor.len(), 3, "its slides are intact");
        assert_eq!(lib.list().len(), 2, "nothing added, nothing lost");
    }

    #[test]
    fn replace_deck_with_an_unknown_target_is_refused_and_mutates_nothing() {
        // The deck the caller meant to replace was deleted while the import parsed.
        let mut lib = DeckLibrary::load(None);
        let keep = lib.create("Sermon");
        let before = lib.list();
        let err = lib
            .replace_deck(DeckId(999_999), incoming("Sermon", 3), None)
            .expect_err("an unknown target is refused, not adopted as a new deck");
        assert_eq!(err, AdoptError::UnknownTarget);
        assert_eq!(lib.list(), before);
        assert_eq!(lib.get(keep.id()).map(|d| d.len()), Some(1));
    }

    #[test]
    fn keep_both_suffixes_and_fail_errors_on_a_taken_name() {
        let mut lib = DeckLibrary::load(None);
        lib.create("Sunday Service");

        let kept = lib
            .adopt_with_policy(
                incoming("Sunday Service", 4),
                NameCollisionPolicy::KeepBoth,
                None,
            )
            .expect("KeepBoth never refuses");
        assert_eq!(kept.name, "Sunday Service (2)", "today's uniquify path");
        assert_eq!(lib.list().len(), 2);

        let err = lib
            .adopt_with_policy(
                incoming("Sunday Service", 4),
                NameCollisionPolicy::Fail,
                None,
            )
            .expect_err("Fail refuses a taken name");
        assert_eq!(err, AdoptError::NameTaken);
        assert_eq!(lib.list().len(), 2, "the refusal added nothing");
    }

    #[test]
    fn a_free_name_is_adopted_identically_under_every_policy() {
        // A policy is a collision RULE, not a mode: with no collision all three agree exactly.
        let outcome = |policy: NameCollisionPolicy| {
            let mut lib = DeckLibrary::load(None);
            lib.create("Occupied");
            let adopted = lib
                .adopt_with_policy(incoming("Fresh", 3), policy, None)
                .expect("a free name never refuses");
            (
                adopted.id(),
                adopted.name.clone(),
                adopted.len(),
                lib.list(),
            )
        };
        let keep_both = outcome(NameCollisionPolicy::KeepBoth);
        assert_eq!(keep_both.1, "Fresh", "adopted under the name it carried");
        assert_eq!(keep_both, outcome(NameCollisionPolicy::Replace));
        assert_eq!(keep_both, outcome(NameCollisionPolicy::Fail));
    }

    #[test]
    fn adopt_is_exactly_adopt_with_policy_keep_both() {
        // The no-regression gate for every pre-existing `adopt` caller: same ids, same names, same
        // list, on both a free and a taken name.
        let via_adopt = {
            let mut lib = DeckLibrary::load(None);
            lib.create("Sermon");
            let a = lib.adopt(incoming("Sermon", 2)); // taken
            let b = lib.adopt(incoming("Fresh", 1)); // free
            let c = lib.adopt(incoming("   ", 1)); // blank → fallback name
            (a.id(), a.name, b.id(), b.name, c.id(), c.name, lib.list())
        };
        let via_policy = {
            let mut lib = DeckLibrary::load(None);
            lib.create("Sermon");
            let p = NameCollisionPolicy::KeepBoth;
            let a = lib
                .adopt_with_policy(incoming("Sermon", 2), p, None)
                .expect("KeepBoth never refuses");
            let b = lib
                .adopt_with_policy(incoming("Fresh", 1), p, None)
                .expect("KeepBoth never refuses");
            let c = lib
                .adopt_with_policy(incoming("   ", 1), p, None)
                .expect("KeepBoth never refuses");
            (a.id(), a.name, b.id(), b.name, c.id(), c.name, lib.list())
        };
        assert_eq!(via_adopt, via_policy);
    }

    #[test]
    fn replace_upserts_the_same_persisted_row_and_survives_a_reopen() {
        // The persistence half of FINDING-LIB-07: the deck table is keyed by NAME, so a replace must
        // update that row rather than orphan it and write a second one.
        let dir = std::env::temp_dir().join(format!(
            "selahcue-lib-replace-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("lib.sqlite");
        let id_before;
        {
            let mut lib = DeckLibrary::load(Some(selahcue_data::Database::open(&path).unwrap()));
            let original = lib.create("Sunday Service");
            id_before = original.id();
            lib.adopt_with_policy(
                incoming("Sunday Service", 9),
                NameCollisionPolicy::Replace,
                None,
            )
            .expect("replace proceeds");
        }
        {
            let lib = DeckLibrary::load(Some(selahcue_data::Database::open(&path).unwrap()));
            assert_eq!(
                lib.list().len(),
                1,
                "one row, not two — the row was updated"
            );
            let stored = lib
                .get(id_before)
                .expect("the ORIGINAL DeckId round-tripped through persistence");
            assert_eq!(stored.len(), 9, "the replacement content persisted");
            assert_eq!(stored.name, "Sunday Service");
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn adopt_assigns_an_id_to_an_existing_deck() {
        let mut lib = DeckLibrary::load(None);
        let mut demo = SlideDeck::new("Sermon: Grace That Feeds");
        demo.add_slide();
        assert_eq!(demo.id().0, 0, "precondition: unassigned");
        let adopted = lib.adopt(demo);
        assert_ne!(adopted.id().0, 0, "adopt assigned a stable id");
        assert_eq!(lib.list().len(), 1);
        assert_eq!(lib.get(adopted.id()).unwrap().len(), 1, "kept its slide");
    }
}
