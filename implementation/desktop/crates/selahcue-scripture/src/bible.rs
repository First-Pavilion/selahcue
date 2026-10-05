//! [`Bible`]: one handle for a bundled or an installed translation.
//!
//! The five bundled translations are the closed [`Translation`] enum (their wire codes, the quote
//! matcher's index cells and the verse-run tables are all pinned to it), so a downloaded one cannot
//! be a sixth variant. This handle is what lets one set of lookups serve both without duplicating
//! each function: `Bible::from_code("KJV")` and `Bible::from_code("YOR")` answer the same methods.
//!
//! - A **bundled** handle delegates to the existing free functions ([`crate::verses_in`],
//!   [`crate::passage_exists_in`], ...), so it is those functions, including the table-backed ones
//!   that decode nothing. Its answers are identical by construction.
//! - An **installed** handle (feature `installed`) runs the same selection code over the registry's
//!   decoded index (`select_verses` and friends in the crate root, the very functions the bundled
//!   path uses), loading the index through the bounded cache when it is not resident.
//!
//! Existing code that holds a [`Translation`] keeps calling the free functions unchanged; a handle
//! is for code that must also accept a downloaded translation's code (the output host, the
//! operator's picker).
//!
//! An installed translation whose file is missing or damaged does not panic: every lookup answers
//! "nothing" (empty, `None`, `0`, `false`), exactly as for a reference outside the canon. **The
//! lookups do not say WHY.** [`Bible::is_available`] only says the file is in place (it does not
//! hash it), so a file damaged without changing its size is "available" and reads as an empty
//! translation. A picker that lists installed translations must call [`Bible::check`] (or
//! `Registry::verify`) before presenting one; it remembers its answer per file, so asking again
//! costs a `stat`, not a hash.

use selahcue_core::scripture::Reference;

use crate::{
    adjacent_in_index, chapter_of_index, join_verses, search_index, select_verses, Chapter,
    SearchHit, Translation, Verse,
};

#[cfg(feature = "installed")]
use crate::catalog::TranslationCode;
#[cfg(feature = "installed")]
use crate::registry::Registry;

/// A translation a lookup can be asked of: bundled, or installed by the user.
#[derive(Clone)]
pub struct Bible {
    repr: Repr,
}

#[derive(Clone)]
enum Repr {
    Bundled(Translation),
    #[cfg(feature = "installed")]
    Installed(InstalledBible),
}

#[cfg(feature = "installed")]
#[derive(Clone)]
struct InstalledBible {
    registry: Registry,
    code: TranslationCode,
    name: String,
}

impl std::fmt::Debug for Bible {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Bible({}, {})", self.code(), self.kind())
    }
}

impl PartialEq for Bible {
    /// Two handles are equal when they name the same translation: the same bundled variant, or the
    /// same code in the same registry.
    fn eq(&self, other: &Bible) -> bool {
        match (&self.repr, &other.repr) {
            (Repr::Bundled(a), Repr::Bundled(b)) => a == b,
            #[cfg(feature = "installed")]
            (Repr::Installed(a), Repr::Installed(b)) => {
                a.registry.same_registry(&b.registry) && a.code == b.code
            }
            #[cfg(feature = "installed")]
            _ => false,
        }
    }
}

impl Eq for Bible {}

impl From<Translation> for Bible {
    fn from(t: Translation) -> Bible {
        Bible::bundled(t)
    }
}

impl Bible {
    /// The handle for bundled translation `t`.
    pub fn bundled(t: Translation) -> Bible {
        Bible {
            repr: Repr::Bundled(t),
        }
    }

    #[cfg(feature = "installed")]
    pub(crate) fn installed(registry: Registry, code: TranslationCode, name: String) -> Bible {
        Bible {
            repr: Repr::Installed(InstalledBible {
                registry,
                code,
                name,
            }),
        }
    }

    /// Resolve a wire/UI code (case-insensitive): a bundled code first, then (with feature
    /// `installed`) a translation installed in the process-wide registry
    /// ([`Registry::global`]). `None` when the code is neither, or names a translation that is not
    /// installed. Never performs network I/O; for a code that is not bundled it DOES file I/O (the
    /// registry's receipt, re-read only when it changed, and a `stat` of the file), so it is not a
    /// free call on a path that runs per frame.
    pub fn from_code(code: &str) -> Option<Bible> {
        if let Some(t) = Translation::from_code(code) {
            return Some(Bible::bundled(t));
        }
        #[cfg(feature = "installed")]
        {
            Registry::global()?.bible(code)
        }
        #[cfg(not(feature = "installed"))]
        {
            None
        }
    }

    /// Short display/wire code (`"KJV"`, `"BSB"`, ...).
    pub fn code(&self) -> &str {
        match &self.repr {
            Repr::Bundled(t) => t.code(),
            #[cfg(feature = "installed")]
            Repr::Installed(i) => i.code.as_str(),
        }
    }

    /// Full name for attribution.
    pub fn name(&self) -> &str {
        match &self.repr {
            Repr::Bundled(t) => t.name(),
            #[cfg(feature = "installed")]
            Repr::Installed(i) => &i.name,
        }
    }

    /// The bundled [`Translation`] this is, or `None` for an installed one.
    pub fn bundled_translation(&self) -> Option<Translation> {
        match &self.repr {
            Repr::Bundled(t) => Some(*t),
            #[cfg(feature = "installed")]
            Repr::Installed(_) => None,
        }
    }

    fn kind(&self) -> &'static str {
        match &self.repr {
            Repr::Bundled(_) => "bundled",
            #[cfg(feature = "installed")]
            Repr::Installed(_) => "installed",
        }
    }

    /// Whether lookups can be answered right now. Bundled: always. Installed: the translation has a
    /// receipt entry and its file is in place (a regular file of the recorded size). That is a cheap
    /// check with no hashing and no decode, so a file damaged in place WITHOUT changing its size
    /// still counts as available and its lookups come back empty: use [`Bible::check`] to find
    /// out. Never loads an index, so it cannot evict one.
    pub fn is_available(&self) -> bool {
        match &self.repr {
            Repr::Bundled(_) => true,
            #[cfg(feature = "installed")]
            Repr::Installed(i) => i.registry.installed_entry(&i.code).is_some(),
        }
    }

    /// Whether the translation would actually load: for an installed one, the file's digest and
    /// size are the receipt's and it passes the same validation a load applies. Bundled: always
    /// `Ok`. Unlike every lookup, this says WHY a translation reads as empty
    /// ([`crate::registry::LoadError::Mismatch`] for a damaged file, `Missing`, `Invalid`...).
    /// Decodes nothing and evicts nothing. The answer for a given file is remembered until its
    /// length, modification time or inode changes.
    #[cfg(feature = "installed")]
    pub fn check(&self) -> Result<(), crate::registry::LoadError> {
        match &self.repr {
            Repr::Bundled(_) => Ok(()),
            Repr::Installed(i) => i.registry.verify(&i.code),
        }
    }

    /// Run `f` over this translation's verse index, or over an empty one when an installed
    /// translation cannot be read (see [`Bible::check`] for why).
    fn with_index<R>(&self, f: impl FnOnce(&[Verse]) -> R) -> R {
        match &self.repr {
            Repr::Bundled(t) => f(crate::index_of(*t)),
            #[cfg(feature = "installed")]
            Repr::Installed(i) => match i.registry.index(&i.code) {
                Ok(index) => f(index.as_slice()),
                Err(_) => f(&[]),
            },
        }
    }

    /// All verses of `reference`, in canonical order. See [`crate::verses_in`]. Owned, because an
    /// installed translation's index can be evicted while the caller still holds the answer.
    pub fn verses(&self, reference: &Reference) -> Vec<Verse> {
        self.with_index(|all| select_verses(all, reference).into_iter().cloned().collect())
    }

    /// The verse text of `reference` as one string. See [`crate::passage_text_in`].
    pub fn passage_text(&self, reference: &Reference) -> Option<String> {
        self.with_index(|all| join_verses(&select_verses(all, reference)))
    }

    /// Keyword search, bounded by `limit`. See [`crate::search_in`].
    pub fn search(&self, query: &str, limit: usize) -> Vec<SearchHit> {
        self.with_index(|all| search_index(all, query, limit))
    }

    /// The whole chapter containing `reference`. See [`crate::chapter_in`].
    pub fn chapter(&self, reference: &Reference) -> Option<Chapter> {
        self.with_index(|all| chapter_of_index(all, reference))
    }

    /// The previous or next chapter. See [`crate::adjacent_chapter_in`].
    pub fn adjacent_chapter(&self, reference: &Reference, forward: bool) -> Option<String> {
        self.with_index(|all| adjacent_in_index(all, reference, forward))
    }

    /// Whether `reference` presents at least one verse. Bundled: the table-backed
    /// [`crate::passage_exists_in`], which decodes nothing. Installed: answered from its decoded
    /// index (loading it through the bounded cache if it is not resident).
    pub fn passage_exists(&self, reference: &Reference) -> bool {
        match &self.repr {
            Repr::Bundled(t) => crate::passage_exists_in(*t, reference),
            #[cfg(feature = "installed")]
            Repr::Installed(_) => self.with_index(|all| !select_verses(all, reference).is_empty()),
        }
    }

    /// The first and last verse numbers of the chapter `reference` names. Bundled: the table-backed
    /// [`crate::chapter_verse_bounds_in`]. Installed: from its decoded index.
    pub fn chapter_verse_bounds(&self, reference: &Reference) -> Option<(u16, u16)> {
        match &self.repr {
            Repr::Bundled(t) => crate::chapter_verse_bounds_in(*t, reference),
            #[cfg(feature = "installed")]
            Repr::Installed(_) => self.with_index(|all| crate::bounds_in_index(all, reference)),
        }
    }

    /// How many verses the translation has (0 for an installed one that cannot be read).
    pub fn verse_count(&self) -> usize {
        self.with_index(<[Verse]>::len)
    }
}
