//! Safe JSON diagnostics shared by the protocol core and optional TLS transport.

/// What a failed JSON decode (or encode) is allowed to tell a person or a log: a category in
/// words of our own, and the line and column **when serde has them**. **Never serde's message.**
///
/// serde quotes the offending VALUE in its message: `invalid type: string "SECRET sermon words",
/// expected a sequence` for a wrongly-typed field, ``unknown variant `SECRET`, expected one of
/// ...`` for an unknown enum tag. The frame can be the operator's state (it carries the live
/// transcript), a pairing grant (it carries a device token) or whatever a version-skewed, buggy
/// or hostile peer put in the wrong place. `TransportError::Json` used to wrap the whole
/// `serde_json::Error`, so both `Display` and the derived `Debug` printed that text, and every
/// caller that logged the error or returned it to the UI carried it along (FR-082,
/// 17tnw2b9aec).
///
/// This type holds a [`JsonFailureKind`] and two numbers, so there is no text for a derived
/// `Debug` to leak and no `source()` to walk. It is the same approach as the cloud client's
/// error mapping (`selahcue-cloud`, 86akbzxjg: category and position only), not a redaction pass
/// over text: a filter can only remove what someone thought to describe.
///
/// **The position is not always there.** serde reports line 0 and column 0 when it has no
/// position, which is the case for a data error inside an internally tagged enum (serde buffers
/// the content before it knows the variant). Every wire message here (`ServerMessage`,
/// `AuthResponse`, `PairResponse`, `Hello`, `Command`) is such an enum, so most shape errors have
/// none. `Display` says `(no position)` for those rather than `at line 0 column 0`, as serde
/// itself omits the suffix; the numbers stay readable through [`JsonFailure::line`] and
/// [`JsonFailure::column`]. Where there is a position it says roughly how far into the frame the
/// failure was, never what was there.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct JsonFailure {
    kind: JsonFailureKind,
    line: usize,
    column: usize,
}

/// What kind of JSON failure it was, as `serde_json` classifies it.
///
/// `#[non_exhaustive]`: a new category in a future serde_json must not break a caller that
/// matches on this. Nothing in the workspace matches it exhaustively outside this crate.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum JsonFailureKind {
    /// The text is not valid JSON.
    Syntax,
    /// Valid JSON that does not have the shape the protocol defines (a missing field, a field of
    /// the wrong type, an unknown variant). The category serde quotes values in.
    Data,
    /// The text ended before the value did.
    Eof,
    /// Reading the text failed. **Unreachable from parsing a string** (`protocol::from_json` and
    /// every frame the transport receives): `serde_json` produces it only when it reads a stream.
    /// Kept so the mapping from `serde_json`'s categories is total.
    Io,
}

impl JsonFailure {
    /// The category of the failure.
    pub fn kind(&self) -> JsonFailureKind {
        self.kind
    }

    /// The 1-based line the failure was detected on (0 when serde has no position: see the type
    /// documentation).
    pub fn line(&self) -> usize {
        self.line
    }

    /// The 1-based column the failure was detected at (0 when serde has no position: see the type
    /// documentation).
    pub fn column(&self) -> usize {
        self.column
    }
}

impl From<&serde_json::Error> for JsonFailure {
    fn from(e: &serde_json::Error) -> Self {
        use serde_json::error::Category;
        JsonFailure {
            kind: match e.classify() {
                Category::Syntax => JsonFailureKind::Syntax,
                Category::Data => JsonFailureKind::Data,
                Category::Eof => JsonFailureKind::Eof,
                Category::Io => JsonFailureKind::Io,
            },
            line: e.line(),
            column: e.column(),
        }
    }
}

impl std::fmt::Display for JsonFailure {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let what = match self.kind {
            JsonFailureKind::Syntax => "the message was not valid JSON",
            JsonFailureKind::Data => "the message did not have the shape the protocol defines",
            JsonFailureKind::Eof => "the message ended early",
            JsonFailureKind::Io => "the message could not be read",
        };
        if self.line == 0 {
            // serde has no position (see the type documentation); do not invent one.
            write!(f, "{what} (no position)")
        } else {
            write!(f, "{what} at line {} column {}", self.line, self.column)
        }
    }
}

impl From<serde_json::Error> for JsonFailure {
    /// Keep only the safe category/position and drop the raw error, including its message/source.
    fn from(error: serde_json::Error) -> Self {
        Self::from(&error)
    }
}

impl std::error::Error for JsonFailure {}
