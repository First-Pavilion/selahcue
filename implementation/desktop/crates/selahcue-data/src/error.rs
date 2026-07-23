//! Persistence error type.

use std::fmt;

/// Errors from the data layer.
#[derive(Debug)]
pub enum DataError {
    /// An underlying SQLite error.
    Sqlite(rusqlite::Error),
    /// The requested row does not exist.
    NotFound,
    /// Stored data could not be interpreted (e.g. an unknown enum tag) — a
    /// corruption or schema-mismatch signal, not user error.
    Corrupt(String),
    /// `PRAGMA integrity_check` returned something other than `ok`.
    IntegrityFailed(String),
    /// The database was created by a newer build than this one understands;
    /// opening (and writing) it would risk data loss, so it is refused.
    SchemaTooNew { found: i64, supported: i64 },
}

impl fmt::Display for DataError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DataError::Sqlite(e) => write!(f, "sqlite error: {e}"),
            DataError::NotFound => f.write_str("row not found"),
            DataError::Corrupt(s) => write!(f, "corrupt data: {s}"),
            DataError::IntegrityFailed(s) => write!(f, "integrity check failed: {s}"),
            DataError::SchemaTooNew { found, supported } => write!(
                f,
                "database schema v{found} is newer than this build supports (v{supported})"
            ),
        }
    }
}

impl std::error::Error for DataError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            DataError::Sqlite(e) => Some(e),
            _ => None,
        }
    }
}

impl From<rusqlite::Error> for DataError {
    fn from(e: rusqlite::Error) -> Self {
        DataError::Sqlite(e)
    }
}

/// Result alias for the data layer.
pub type Result<T> = std::result::Result<T, DataError>;
