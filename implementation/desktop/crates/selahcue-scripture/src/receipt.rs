//! The install receipt, `installed.json` (feature `installed`).
//!
//! One JSON file in the registry directory records what is installed: for each translation its
//! code, file name, SHA-256, size, verse counts, the time it was installed as the caller's clock
//! gave it, and the catalogue schema. It is the single source of truth for "installed": a file
//! without an entry is not installed, and an entry whose file is missing or is a symlink is not
//! listed. Everything read from it is validated again (a plain file name, a 64-lowercase-hex digest,
//! bounded sizes and counts), because the file sits in a directory a user or another program can
//! write to. The registry writes it atomically (a temp file renamed into place); this module only
//! reads, parses and renders.

use std::fs::{self, File};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

use serde_json::{json, Value};

use crate::catalog::{
    is_sha256_hex, validate_file_name, TranslationCode, MAX_ASSET_BYTES, MAX_ENTRIES,
    MAX_VERSES_PER_TESTAMENT,
};

/// The receipt file name inside the registry directory.
pub const RECEIPT_FILE: &str = "installed.json";

const RECEIPT_SCHEMA: u64 = 1;
/// The largest receipt that is read at all. Real ones are a few hundred bytes per translation.
const MAX_RECEIPT_BYTES: u64 = 256 * 1024;

/// One installed translation, as the receipt records it.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct InstalledTranslation {
    pub code: TranslationCode,
    /// The plain file name inside the registry directory.
    pub file_name: String,
    /// Lowercase-hex SHA-256 of the file, as verified at install and re-checked at every load.
    pub sha256: String,
    pub size_bytes: u64,
    /// Old Testament verses the file held when it was installed. Loading refuses a file with more
    /// rows than the two counts allow, and one with other counts.
    pub verses_ot: u32,
    /// New Testament verses the file held when it was installed.
    pub verses_nt: u32,
    /// The `installed_at` the caller passed (its clock; this crate never reads one).
    pub installed_at: u64,
    /// The catalogue schema in force when it was installed.
    pub catalogue_schema: u32,
}

/// Why the receipt could not be read or written.
#[derive(Debug)]
pub enum ReceiptError {
    /// `installed.json` is not a trustworthy receipt (not JSON, a symlink, too large, a bad field).
    /// Installing and removing refuse to run over it, so no other translation is forgotten;
    /// [`crate::registry::Registry::repair_receipt`] rebuilds it from the files on disk.
    Corrupt(String),
    Io(std::io::Error),
}

impl std::fmt::Display for ReceiptError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ReceiptError::Corrupt(why) => write!(f, "the install record is damaged: {why}"),
            ReceiptError::Io(e) => write!(f, "the install record could not be read: {e}"),
        }
    }
}

impl std::error::Error for ReceiptError {}

/// What a file looked like when it was last examined: its length, its modification time and (on
/// Unix) its inode. A rename replaces the inode, so an atomic rewrite of the receipt is seen even
/// when the length and the clock tick are unchanged.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct Stamp {
    len: u64,
    modified: Option<SystemTime>,
    inode: Option<u64>,
}

impl Stamp {
    pub(crate) fn of(meta: &fs::Metadata) -> Stamp {
        #[cfg(unix)]
        let inode = {
            use std::os::unix::fs::MetadataExt;
            Some(meta.ino())
        };
        #[cfg(not(unix))]
        let inode = None;
        Stamp {
            len: meta.len(),
            modified: meta.modified().ok(),
            inode,
        }
    }
}

pub(crate) fn receipt_path(dir: &Path) -> PathBuf {
    dir.join(RECEIPT_FILE)
}

/// Read and validate the receipt. A missing file is an empty list; anything else wrong with it is
/// [`ReceiptError`]. Never follows a symlink, never reads more than [`MAX_RECEIPT_BYTES`].
pub(crate) fn read_receipts(dir: &Path) -> Result<Vec<InstalledTranslation>, ReceiptError> {
    let path = receipt_path(dir);
    let meta = match fs::symlink_metadata(&path) {
        Ok(m) => m,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(ReceiptError::Io(e)),
    };
    if !meta.file_type().is_file() {
        return Err(ReceiptError::Corrupt(
            "installed.json is not a regular file".to_string(),
        ));
    }
    let mut bytes = Vec::new();
    File::open(&path)
        .and_then(|f| f.take(MAX_RECEIPT_BYTES + 1).read_to_end(&mut bytes))
        .map_err(ReceiptError::Io)?;
    if bytes.len() as u64 > MAX_RECEIPT_BYTES {
        return Err(ReceiptError::Corrupt(format!(
            "installed.json is larger than {MAX_RECEIPT_BYTES} bytes"
        )));
    }
    parse_receipts(&bytes)
}

pub(crate) fn parse_receipts(bytes: &[u8]) -> Result<Vec<InstalledTranslation>, ReceiptError> {
    let bad = |why: &str| ReceiptError::Corrupt(why.to_string());
    let doc: Value = serde_json::from_slice(bytes)
        .map_err(|e| ReceiptError::Corrupt(format!("not valid JSON: {e}")))?;
    let root = doc.as_object().ok_or_else(|| bad("not a JSON object"))?;
    if root.get("schema").and_then(Value::as_u64) != Some(RECEIPT_SCHEMA) {
        return Err(bad("unsupported receipt schema"));
    }
    let list = root
        .get("translations")
        .and_then(Value::as_array)
        .ok_or_else(|| bad("'translations' is not an array"))?;
    if list.len() > MAX_ENTRIES {
        return Err(bad("too many entries"));
    }

    let mut out: Vec<InstalledTranslation> = Vec::with_capacity(list.len());
    for item in list {
        let o = item
            .as_object()
            .ok_or_else(|| bad("an entry is not an object"))?;
        let text = |key: &str| {
            o.get(key)
                .and_then(Value::as_str)
                .ok_or_else(|| ReceiptError::Corrupt(format!("'{key}' is missing or not text")))
        };
        let number = |key: &str| {
            o.get(key)
                .and_then(Value::as_u64)
                .ok_or_else(|| ReceiptError::Corrupt(format!("'{key}' is missing or not a number")))
        };
        let code = TranslationCode::parse(text("code")?)
            .map_err(|e| ReceiptError::Corrupt(format!("code is not usable: {e:?}")))?;
        let file_name = text("file_name")?;
        validate_file_name(file_name).map_err(|why| {
            ReceiptError::Corrupt(format!(
                "file_name '{file_name}' is not a plain name: {why}"
            ))
        })?;
        let sha256 = text("sha256")?;
        if !is_sha256_hex(sha256) {
            return Err(bad("sha256 is not 64 lowercase hex characters"));
        }
        let size_bytes = number("size_bytes")?;
        if size_bytes == 0 || size_bytes > MAX_ASSET_BYTES {
            return Err(bad("size_bytes is outside the allowed range"));
        }
        let (ot, nt) = (number("verses_ot")?, number("verses_nt")?);
        if ot > MAX_VERSES_PER_TESTAMENT || nt > MAX_VERSES_PER_TESTAMENT || ot + nt == 0 {
            return Err(bad("verse counts are outside the allowed range"));
        }
        let catalogue_schema = u32::try_from(number("catalogue_schema")?)
            .map_err(|_| bad("catalogue_schema is too large"))?;
        if out.iter().any(|r| r.code == code) {
            return Err(bad("a code is listed twice"));
        }
        out.push(InstalledTranslation {
            code,
            file_name: file_name.to_string(),
            sha256: sha256.to_string(),
            size_bytes,
            // Both are at most 100,000 (checked above), so they fit a `u32`.
            verses_ot: ot as u32,
            verses_nt: nt as u32,
            installed_at: number("installed_at")?,
            catalogue_schema,
        });
    }
    Ok(out)
}

pub(crate) fn render_receipts(list: &[InstalledTranslation]) -> Vec<u8> {
    let translations: Vec<Value> = list
        .iter()
        .map(|r| {
            json!({
                "code": r.code.as_str(),
                "file_name": r.file_name,
                "sha256": r.sha256,
                "size_bytes": r.size_bytes,
                "verses_ot": r.verses_ot,
                "verses_nt": r.verses_nt,
                "installed_at": r.installed_at,
                "catalogue_schema": r.catalogue_schema,
            })
        })
        .collect();
    let doc = json!({ "schema": RECEIPT_SCHEMA, "translations": translations });
    let mut bytes = serde_json::to_vec_pretty(&doc).unwrap_or_default();
    bytes.push(b'\n');
    bytes
}

/// Whether the receipt's file is really there: a regular file (never a symlink) of the recorded
/// size. A cheap check; the digest is checked when the text is read.
pub(crate) fn file_in_place(dir: &Path, rec: &InstalledTranslation) -> bool {
    fs::symlink_metadata(dir.join(&rec.file_name))
        .is_ok_and(|m| m.file_type().is_file() && m.len() == rec.size_bytes)
}
