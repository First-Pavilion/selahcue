//! Bytes to text, for the `.txt` half of the shared text path.
//!
//! Clipboard text arrives already a `String`; a file arrives as bytes, and church lyric files
//! are frequently not UTF-8. Windows-1252 exports and Notepad's UTF-16 are the normal case here,
//! not the edge case — which is exactly why the substitutions must be **counted and reported**.
//! Replacing bytes with U+FFFD silently would violate the partial-import rule at the encoding
//! layer, which is the layer where people forget to apply it.

/// The decoded text plus how many replacement characters were substituted.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodedText {
    pub text: String,
    /// U+FFFD substitutions introduced by a lossy decode.
    pub replacements: usize,
}

/// Decode `bytes` to text.
///
/// 1. Strip a UTF-8 BOM.
/// 2. Valid UTF-8 is used as-is.
/// 3. A UTF-16 BOM (either endianness) is transcoded — Notepad still produces UTF-16, so this is
///    not exotic.
/// 4. Anything else is decoded as lossy UTF-8, and the substitutions are counted.
///
/// NULs are stripped in every branch, before the text can reach SQLite or the UI.
pub fn to_text(bytes: &[u8]) -> DecodedText {
    // UTF-16 first: its BOM is unambiguous, and a UTF-16 file is usually not valid UTF-8 anyway.
    if let Some(rest) = bytes.strip_prefix(&[0xFF, 0xFE]) {
        return utf16(rest, u16::from_le_bytes);
    }
    if let Some(rest) = bytes.strip_prefix(&[0xFE, 0xFF]) {
        return utf16(rest, u16::from_be_bytes);
    }
    let bytes = bytes.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(bytes);
    match std::str::from_utf8(bytes) {
        Ok(s) => DecodedText {
            text: strip_nuls(s),
            replacements: 0,
        },
        Err(_) => {
            let lossy = String::from_utf8_lossy(bytes);
            let replacements = lossy
                .chars()
                .filter(|c| *c == char::REPLACEMENT_CHARACTER)
                .count();
            DecodedText {
                text: strip_nuls(&lossy),
                replacements,
            }
        }
    }
}

/// Transcode a UTF-16 payload, counting unpaired surrogates as replacements.
fn utf16(rest: &[u8], read: fn([u8; 2]) -> u16) -> DecodedText {
    let units: Vec<u16> = rest.chunks_exact(2).map(|c| read([c[0], c[1]])).collect();
    let mut text = String::with_capacity(units.len());
    let mut replacements = 0usize;
    for r in char::decode_utf16(units) {
        match r {
            Ok(c) if c != '\0' => text.push(c),
            Ok(_) => {}
            Err(_) => {
                replacements += 1;
                text.push(char::REPLACEMENT_CHARACTER);
            }
        }
    }
    // A trailing odd byte is a truncated code unit: count it rather than drop it silently.
    if rest.len() % 2 == 1 {
        replacements += 1;
        text.push(char::REPLACEMENT_CHARACTER);
    }
    DecodedText { text, replacements }
}

fn strip_nuls(s: &str) -> String {
    if s.contains('\0') {
        s.chars().filter(|c| *c != '\0').collect()
    } else {
        s.to_string()
    }
}

/// Normalise line endings to `\n` — CRLF and lone CR alike — **once**, before anything splits on
/// them.
///
/// Without this a CRLF file still splits correctly on blank lines, but every line keeps a
/// trailing `\r` that becomes a rendered glyph on the audience screen. This repository already
/// has a CRLF trap on record; this is the same one, at the import boundary.
pub fn normalise_newlines(text: &str) -> String {
    if !text.contains('\r') {
        return text.to_string();
    }
    let mut out = String::with_capacity(text.len());
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\r' {
            if chars.peek() == Some(&'\n') {
                chars.next();
            }
            out.push('\n');
        } else {
            out.push(c);
        }
    }
    out
}
