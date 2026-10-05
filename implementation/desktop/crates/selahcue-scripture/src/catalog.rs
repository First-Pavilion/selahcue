//! The catalogue of downloadable translations (feature `installed`).
//!
//! `assets/catalog.json` is embedded in the binary and parsed, then validated, the first time it is
//! asked for. It is the allowlist the whole download path trusts: which codes exist, what file each
//! one is, what digest the file must have and how many verses it must hold. So the document is
//! treated as input and checked as input, even though it ships with the app: an unknown schema, a
//! duplicate code, a code that collides with a bundled translation, a file name that is not a
//! plain name, a digest that is not 64 lowercase hex characters, a text field of absurd length or
//! a base URL that is not https are all refused, each with its own error.
//!
//! The schema is A1's (`scripts/build_translation_catalog.py`, schema 1). A new translation is
//! data plus a release.
//!
//! **Nothing is published yet.** The shipped document has `base_url: null`, so
//! [`Catalogue::download_url`] reports [`NotPublished`] and no request can be made. The digests and
//! sizes in it come from a scratch build of A1's converter and say so in the document's `note`;
//! the publish job (A7) replaces them with the digests of the files it actually uploads.

use std::collections::HashSet;
use std::sync::OnceLock;

use serde_json::{Map, Value};

use crate::url_policy::UrlPolicy;
use crate::Translation;

/// The catalogue schema this code reads.
pub const SCHEMA: u32 = 1;
/// The longest catalogue document that is parsed at all (the shipped one is under 10 KiB).
pub const MAX_CATALOGUE_BYTES: usize = 1024 * 1024;
/// The most entries a catalogue may list. A bound, so a hostile or broken document cannot grow
/// the registry's per-code bookkeeping without limit.
pub const MAX_ENTRIES: usize = 256;
/// The largest asset (compressed) a catalogue entry may pin: 64 MiB, the same ceiling `build.rs`
/// puts on a bundled asset's decompressed size. Real assets are about 1.4 MB.
pub const MAX_ASSET_BYTES: u64 = 64 * 1024 * 1024;
/// The longest any one text field may be.
const MAX_TEXT_BYTES: usize = 8 * 1024;
/// The longest a base URL may be.
const MAX_URL_BYTES: usize = 512;
/// The longest a catalogue file name may be.
const MAX_FILE_NAME_BYTES: usize = 64;
/// The most verses an Old or New Testament may claim. Real counts are about 23,000 and 8,000.
const MAX_VERSES_PER_TESTAMENT: u64 = 100_000;

const EMBEDDED_JSON: &str = include_str!("../assets/catalog.json");

/// A validated translation code: `^[A-Z][A-Z0-9-]{1,15}$`, and never one of the five bundled codes
/// (those stay the closed [`Translation`] enum, so a downloaded translation can never shadow one).
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TranslationCode(String);

/// Why a string is not a usable translation code.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CodeError {
    /// Not 2 to 16 characters of `A-Z`, `0-9` and `-`, starting with a letter.
    BadShape,
    /// A bundled code (`KJV`, `WEB`, `ASV`, `WEBBE`, `DBY`).
    CollidesWithBundled,
}

impl TranslationCode {
    /// Validate `code` exactly as given (upper case only; fold a wire code's case before calling).
    pub fn parse(code: &str) -> Result<TranslationCode, CodeError> {
        let b = code.as_bytes();
        let shaped = (2..=16).contains(&b.len())
            && b[0].is_ascii_uppercase()
            && b.iter()
                .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || *c == b'-');
        if !shaped {
            return Err(CodeError::BadShape);
        }
        if Translation::from_code(code).is_some() {
            return Err(CodeError::CollidesWithBundled);
        }
        Ok(TranslationCode(code.to_string()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Display for TranslationCode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl AsRef<str> for TranslationCode {
    fn as_ref(&self) -> &str {
        &self.0
    }
}

/// Whether a translation has been through legal review. Only `Cleared` entries are offered for
/// download; a `Pending` one is listed (so a UI can say so) and refused by the download function.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LegalReview {
    Cleared,
    Pending,
}

/// The licence a translation is shared under.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct Licence {
    pub id: String,
    pub name: String,
    pub summary: String,
    pub url: Option<String>,
    pub attribution_required: bool,
    pub share_alike: bool,
}

/// Where the text came from, for the attribution screen.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct Source {
    pub ebible_id: String,
    pub url: String,
    pub title: String,
    pub copyright: String,
    pub ebible_update_date: String,
    /// SHA-256 of the USFM zip the asset was built from (lowercase hex).
    pub usfm_zip_sha256: String,
}

/// One downloadable translation. Read-only: the only way to get one is [`Catalogue::parse`], so
/// every entry in hand has passed the checks above.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct CatalogEntry {
    pub code: TranslationCode,
    pub name: String,
    pub language: String,
    pub language_name: String,
    /// A plain file name ending `.tsv.gz`: part of the download URL and of the name on disk.
    pub file_name: String,
    /// Size of the compressed asset. The download is capped at exactly this.
    pub size_bytes: u64,
    /// Lowercase-hex SHA-256 of the compressed asset.
    pub sha256: String,
    /// Old Testament verses (books 1 to 39) the asset must hold.
    pub verses_ot: u32,
    /// New Testament verses (books 40 to 66) the asset must hold.
    pub verses_nt: u32,
    pub omitted_verses: u32,
    pub licence: Licence,
    pub attribution: Option<String>,
    pub trademark_note: Option<String>,
    pub modifications: Option<String>,
    pub legal_review: LegalReview,
    pub source: Source,
}

impl CatalogEntry {
    /// `verses_ot + verses_nt`.
    pub fn verse_count(&self) -> u32 {
        self.verses_ot + self.verses_nt
    }
}

/// A validated catalogue document.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Catalogue {
    schema: u32,
    base_url: Option<String>,
    note: Option<String>,
    translations: Vec<CatalogEntry>,
}

/// The catalogue has no base URL: nothing is published, so nothing can be requested.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NotPublished;

impl std::fmt::Display for NotPublished {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("not published yet")
    }
}

impl std::error::Error for NotPublished {}

/// Why a catalogue document was refused. One variant per reason, so a test can name the one it
/// expects and cannot be satisfied by a generic failure. `field` is a path such as
/// `translations[2].sha256`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CatalogError {
    TooLarge {
        limit: usize,
    },
    BadJson(String),
    UnsupportedSchema {
        found: u64,
    },
    Missing {
        field: String,
    },
    WrongType {
        field: String,
        expected: &'static str,
    },
    TooLong {
        field: String,
    },
    BadCode {
        code: String,
        reason: CodeError,
    },
    DuplicateCode {
        code: String,
    },
    BadFileName {
        code: String,
        file_name: String,
    },
    DuplicateFileName {
        file_name: String,
    },
    BadDigest {
        field: String,
    },
    BadSize {
        code: String,
        size_bytes: u64,
    },
    BadCount {
        code: String,
    },
    BadLegalReview {
        code: String,
        value: String,
    },
    BadBaseUrl {
        base_url: String,
        reason: String,
    },
    BadUrl {
        field: String,
    },
    TooManyEntries {
        limit: usize,
    },
}

impl std::fmt::Display for CatalogError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CatalogError::TooLarge { limit } => {
                write!(f, "the catalogue is larger than {limit} bytes")
            }
            CatalogError::BadJson(e) => write!(f, "the catalogue is not valid JSON: {e}"),
            CatalogError::UnsupportedSchema { found } => {
                write!(
                    f,
                    "catalogue schema {found} is not supported (expected {SCHEMA})"
                )
            }
            CatalogError::Missing { field } => write!(f, "catalogue field '{field}' is missing"),
            CatalogError::WrongType { field, expected } => {
                write!(f, "catalogue field '{field}' must be {expected}")
            }
            CatalogError::TooLong { field } => write!(f, "catalogue field '{field}' is too long"),
            CatalogError::BadCode { code, reason } => {
                write!(f, "catalogue code '{code}' is not usable: {reason:?}")
            }
            CatalogError::DuplicateCode { code } => {
                write!(f, "catalogue lists code '{code}' more than once")
            }
            CatalogError::BadFileName { code, file_name } => {
                write!(
                    f,
                    "catalogue file name '{file_name}' for {code} is not a plain name"
                )
            }
            CatalogError::DuplicateFileName { file_name } => {
                write!(f, "catalogue lists file name '{file_name}' more than once")
            }
            CatalogError::BadDigest { field } => {
                write!(
                    f,
                    "catalogue field '{field}' is not 64 lowercase hex characters"
                )
            }
            CatalogError::BadSize { code, size_bytes } => write!(
                f,
                "catalogue size {size_bytes} for {code} is outside 1..={MAX_ASSET_BYTES}"
            ),
            CatalogError::BadCount { code } => {
                write!(f, "catalogue verse counts for {code} are not usable")
            }
            CatalogError::BadLegalReview { code, value } => write!(
                f,
                "catalogue legal_review '{value}' for {code} is neither 'cleared' nor 'pending'"
            ),
            CatalogError::BadBaseUrl { base_url, reason } => {
                write!(f, "catalogue base_url '{base_url}' is refused: {reason}")
            }
            CatalogError::BadUrl { field } => {
                write!(f, "catalogue field '{field}' is not an https URL")
            }
            CatalogError::TooManyEntries { limit } => {
                write!(f, "the catalogue lists more than {limit} translations")
            }
        }
    }
}

impl std::error::Error for CatalogError {}

/// Windows refuses these as file names (with or without an extension).
fn is_reserved_device_name(stem: &str) -> bool {
    let s = stem.to_ascii_uppercase();
    matches!(s.as_str(), "CON" | "PRN" | "AUX" | "NUL")
        || ((s.starts_with("COM") || s.starts_with("LPT"))
            && s.len() == 4
            && s.as_bytes()[3].is_ascii_digit()
            && s.as_bytes()[3] != b'0')
}

/// `Ok(())` when `name` is a plain file name safe to join onto a directory on any supported OS:
/// 1 to 64 characters of `A-Za-z0-9._-`, starting with a letter or digit, with no `..`, and not a
/// Windows device name. Everything else (a path separator, a drive prefix, a leading dot,
/// whitespace, a control character) is refused with a reason.
pub fn validate_plain_name(name: &str) -> Result<(), &'static str> {
    if name.is_empty() || name.len() > MAX_FILE_NAME_BYTES {
        return Err("empty or longer than 64 characters");
    }
    if !name
        .bytes()
        .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-'))
    {
        return Err("only letters, digits, '.', '_' and '-' are allowed");
    }
    if !name.as_bytes()[0].is_ascii_alphanumeric() {
        return Err("must start with a letter or digit");
    }
    if name.contains("..") {
        return Err("must not contain '..'");
    }
    let stem = name.split('.').next().unwrap_or(name);
    if is_reserved_device_name(stem) {
        return Err("is a reserved device name on Windows");
    }
    Ok(())
}

/// [`validate_plain_name`] and, in addition, the name of a translation asset: it must end
/// `.tsv.gz` and have something before that.
pub fn validate_file_name(name: &str) -> Result<(), &'static str> {
    const SUFFIX: &str = ".tsv.gz";
    validate_plain_name(name)?;
    if !name.ends_with(SUFFIX) || name.len() == SUFFIX.len() {
        return Err("must end with '.tsv.gz' and have a name before it");
    }
    Ok(())
}

/// Whether `s` is exactly 64 lowercase hexadecimal characters.
pub fn is_sha256_hex(s: &str) -> bool {
    s.len() == 64 && s.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
}

/// The URL of `entry`'s asset under `base_url`. **The one place the URL layout is decided**: A7's
/// publish job may key objects by digest (`translations/CODE/SHA256.tsv.gz`), and when it does this
/// function changes and nothing else does.
pub fn asset_url(base_url: &str, entry: &CatalogEntry) -> String {
    let separator = if base_url.ends_with('/') { "" } else { "/" };
    format!("{base_url}{separator}{}", entry.file_name)
}

/// A JSON object being read, remembering its path for error messages.
struct Obj<'a> {
    path: String,
    map: &'a Map<String, Value>,
}

impl<'a> Obj<'a> {
    fn field(&self, key: &str) -> String {
        if self.path.is_empty() {
            key.to_string()
        } else {
            format!("{}.{key}", self.path)
        }
    }

    /// The value at `key`, or `None` when it is absent or JSON null.
    fn get(&self, key: &str) -> Option<&'a Value> {
        self.map.get(key).filter(|v| !v.is_null())
    }

    fn require(&self, key: &str) -> Result<&'a Value, CatalogError> {
        self.get(key).ok_or_else(|| CatalogError::Missing {
            field: self.field(key),
        })
    }

    fn text(&self, key: &str) -> Result<String, CatalogError> {
        let v = self.require(key)?;
        self.text_value(key, v)
    }

    fn opt_text(&self, key: &str) -> Result<Option<String>, CatalogError> {
        match self.get(key) {
            None => Ok(None),
            Some(v) => self.text_value(key, v).map(Some),
        }
    }

    fn text_value(&self, key: &str, v: &Value) -> Result<String, CatalogError> {
        let s = v.as_str().ok_or_else(|| CatalogError::WrongType {
            field: self.field(key),
            expected: "a string",
        })?;
        if s.len() > MAX_TEXT_BYTES {
            return Err(CatalogError::TooLong {
                field: self.field(key),
            });
        }
        Ok(s.to_string())
    }

    fn unsigned(&self, key: &str) -> Result<u64, CatalogError> {
        self.require(key)?
            .as_u64()
            .ok_or_else(|| CatalogError::WrongType {
                field: self.field(key),
                expected: "a non-negative whole number",
            })
    }

    fn boolean(&self, key: &str) -> Result<bool, CatalogError> {
        self.require(key)?
            .as_bool()
            .ok_or_else(|| CatalogError::WrongType {
                field: self.field(key),
                expected: "true or false",
            })
    }

    fn object(&self, key: &str) -> Result<Obj<'a>, CatalogError> {
        let map = self
            .require(key)?
            .as_object()
            .ok_or_else(|| CatalogError::WrongType {
                field: self.field(key),
                expected: "an object",
            })?;
        Ok(Obj {
            path: self.field(key),
            map,
        })
    }

    fn digest(&self, key: &str) -> Result<String, CatalogError> {
        let s = self.text(key)?;
        if is_sha256_hex(&s) {
            Ok(s)
        } else {
            Err(CatalogError::BadDigest {
                field: self.field(key),
            })
        }
    }

    /// A display URL (licence page, source page): https only, or absent.
    fn opt_https_url(&self, key: &str) -> Result<Option<String>, CatalogError> {
        let Some(url) = self.opt_text(key)? else {
            return Ok(None);
        };
        UrlPolicy::https_only()
            .check(&url)
            .map_err(|_| CatalogError::BadUrl {
                field: self.field(key),
            })?;
        Ok(Some(url))
    }
}

fn parse_entry(o: &Obj<'_>) -> Result<CatalogEntry, CatalogError> {
    let code_text = o.text("code")?;
    let code = TranslationCode::parse(&code_text).map_err(|reason| CatalogError::BadCode {
        code: code_text.clone(),
        reason,
    })?;

    let file_name = o.text("file_name")?;
    if validate_file_name(&file_name).is_err() {
        return Err(CatalogError::BadFileName {
            code: code_text,
            file_name,
        });
    }

    let size_bytes = o.unsigned("size_bytes")?;
    if size_bytes == 0 || size_bytes > MAX_ASSET_BYTES {
        return Err(CatalogError::BadSize {
            code: code.to_string(),
            size_bytes,
        });
    }

    let verses = o.object("verses")?;
    let (ot, nt) = (verses.unsigned("ot")?, verses.unsigned("nt")?);
    if ot > MAX_VERSES_PER_TESTAMENT || nt > MAX_VERSES_PER_TESTAMENT || ot + nt == 0 {
        return Err(CatalogError::BadCount {
            code: code.to_string(),
        });
    }

    let review = o.text("legal_review")?;
    let legal_review = match review.as_str() {
        "cleared" => LegalReview::Cleared,
        "pending" => LegalReview::Pending,
        _ => {
            return Err(CatalogError::BadLegalReview {
                code: code.to_string(),
                value: review,
            })
        }
    };

    let omitted_verses = match o.get("omitted_verses") {
        None => 0,
        Some(_) => {
            u32::try_from(o.unsigned("omitted_verses")?).map_err(|_| CatalogError::BadCount {
                code: code.to_string(),
            })?
        }
    };

    let lic = o.object("licence")?;
    let licence = Licence {
        id: lic.text("id")?,
        name: lic.text("name")?,
        summary: lic.text("summary")?,
        url: lic.opt_https_url("url")?,
        attribution_required: lic.boolean("attribution_required")?,
        share_alike: lic.boolean("share_alike")?,
    };

    let src = o.object("source")?;
    let source = Source {
        ebible_id: src.text("ebible_id")?,
        url: src.text("url")?,
        title: src.text("title")?,
        copyright: src.text("copyright")?,
        ebible_update_date: src.text("ebible_update_date")?,
        usfm_zip_sha256: src.digest("usfm_zip_sha256")?,
    };
    UrlPolicy::https_only()
        .check(&source.url)
        .map_err(|_| CatalogError::BadUrl {
            field: src.field("url"),
        })?;

    Ok(CatalogEntry {
        name: o.text("name")?,
        language: o.text("language")?,
        language_name: o.text("language_name")?,
        file_name,
        size_bytes,
        sha256: o.digest("sha256")?,
        // `ot` and `nt` are at most 100,000 (checked above), so they fit a `u32`.
        verses_ot: ot as u32,
        verses_nt: nt as u32,
        omitted_verses,
        licence,
        attribution: o.opt_text("attribution")?,
        trademark_note: o.opt_text("trademark_note")?,
        modifications: o.opt_text("modifications")?,
        legal_review,
        source,
        code,
    })
}

impl Catalogue {
    /// Parse and validate `json` under the product URL policy (https only).
    pub fn parse(json: &str) -> Result<Catalogue, CatalogError> {
        Catalogue::parse_with(json, UrlPolicy::https_only())
    }

    /// Parse and validate `json` under `policy`. Only tests pass anything but
    /// [`UrlPolicy::https_only`] (a catalogue whose base URL is a loopback server).
    pub fn parse_with(json: &str, policy: UrlPolicy) -> Result<Catalogue, CatalogError> {
        if json.len() > MAX_CATALOGUE_BYTES {
            return Err(CatalogError::TooLarge {
                limit: MAX_CATALOGUE_BYTES,
            });
        }
        let doc: Value =
            serde_json::from_str(json).map_err(|e| CatalogError::BadJson(e.to_string()))?;
        let map = doc.as_object().ok_or(CatalogError::WrongType {
            field: "(document)".to_string(),
            expected: "an object",
        })?;
        let root = Obj {
            path: String::new(),
            map,
        };

        let schema = root.unsigned("schema")?;
        if schema != u64::from(SCHEMA) {
            return Err(CatalogError::UnsupportedSchema { found: schema });
        }

        let base_url = match root.opt_text("base_url")? {
            None => None,
            Some(url) => Some(validate_base_url(url, policy)?),
        };
        let note = root.opt_text("note")?;

        let entries =
            root.require("translations")?
                .as_array()
                .ok_or_else(|| CatalogError::WrongType {
                    field: "translations".to_string(),
                    expected: "an array",
                })?;
        if entries.len() > MAX_ENTRIES {
            return Err(CatalogError::TooManyEntries { limit: MAX_ENTRIES });
        }

        let mut translations = Vec::with_capacity(entries.len());
        let mut codes = HashSet::new();
        let mut files = HashSet::new();
        for (i, value) in entries.iter().enumerate() {
            let map = value.as_object().ok_or_else(|| CatalogError::WrongType {
                field: format!("translations[{i}]"),
                expected: "an object",
            })?;
            let entry = parse_entry(&Obj {
                path: format!("translations[{i}]"),
                map,
            })?;
            if !codes.insert(entry.code.as_str().to_string()) {
                return Err(CatalogError::DuplicateCode {
                    code: entry.code.to_string(),
                });
            }
            // Two names that differ only in case are one file on a case-insensitive disk.
            if !files.insert(entry.file_name.to_ascii_lowercase()) {
                return Err(CatalogError::DuplicateFileName {
                    file_name: entry.file_name,
                });
            }
            translations.push(entry);
        }

        Ok(Catalogue {
            schema: SCHEMA,
            base_url,
            note,
            translations,
        })
    }

    /// The catalogue embedded in this build (`assets/catalog.json`), parsed and validated on first
    /// use. If the embedded document were ever invalid (a build defect that a test catches), this
    /// is an EMPTY catalogue rather than a panic, and [`Catalogue::embedded_status`] says why.
    pub fn embedded() -> &'static Catalogue {
        static EMPTY: Catalogue = Catalogue {
            schema: SCHEMA,
            base_url: None,
            note: None,
            translations: Vec::new(),
        };
        embedded_parsed().as_ref().unwrap_or(&EMPTY)
    }

    /// `Ok(())` when the embedded catalogue is valid; otherwise the reason it is not.
    pub fn embedded_status() -> Result<(), &'static CatalogError> {
        embedded_parsed().as_ref().map(|_| ())
    }

    pub fn schema(&self) -> u32 {
        self.schema
    }

    /// Where assets are published, or `None` before anything is.
    pub fn base_url(&self) -> Option<&str> {
        self.base_url.as_deref()
    }

    /// Whether a base URL is set. When it is not, no download can start.
    pub fn is_published(&self) -> bool {
        self.base_url.is_some()
    }

    /// A free-text note about the document (the shipped one labels its digests as placeholders).
    pub fn note(&self) -> Option<&str> {
        self.note.as_deref()
    }

    /// Every entry, including ones still pending legal review, in document order.
    pub fn translations(&self) -> &[CatalogEntry] {
        &self.translations
    }

    /// The entry for `code` (case-insensitive), if the catalogue lists it.
    pub fn find(&self, code: &str) -> Option<&CatalogEntry> {
        let code = code.to_ascii_uppercase();
        self.translations.iter().find(|e| e.code.as_str() == code)
    }

    /// The entries a UI may offer for download: those that have cleared legal review. A pending
    /// entry is deliberately absent; [`Catalogue::translations`] still lists it.
    pub fn offered(&self) -> impl Iterator<Item = &CatalogEntry> {
        self.translations
            .iter()
            .filter(|e| e.legal_review == LegalReview::Cleared)
    }

    /// The URL to fetch `entry` from, or [`NotPublished`] when the catalogue has no base URL.
    pub fn download_url(&self, entry: &CatalogEntry) -> Result<String, NotPublished> {
        self.base_url
            .as_deref()
            .map(|base| asset_url(base, entry))
            .ok_or(NotPublished)
    }
}

fn validate_base_url(url: String, policy: UrlPolicy) -> Result<String, CatalogError> {
    let refuse = |reason: &str| CatalogError::BadBaseUrl {
        base_url: url.clone(),
        reason: reason.to_string(),
    };
    if url.len() > MAX_URL_BYTES {
        return Err(refuse("longer than 512 characters"));
    }
    if url.contains('?') || url.contains('#') {
        return Err(refuse("must not carry a query or a fragment"));
    }
    policy.check(&url).map_err(|e| refuse(&e.to_string()))?;
    Ok(url)
}

fn embedded_parsed() -> &'static Result<Catalogue, CatalogError> {
    static PARSED: OnceLock<Result<Catalogue, CatalogError>> = OnceLock::new();
    PARSED.get_or_init(|| Catalogue::parse(EMBEDDED_JSON))
}
