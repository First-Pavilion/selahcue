//! String hygiene at the producer, not at each sink.
//!
//! Every string that leaves this crate — slide text, notes, the deck name, and **every report
//! detail including archive entry names** — passes through [`clean`]. Sanitising here means
//! every consumer is safe by default: the report renderer, the structured log and the database
//! all receive already-clean strings.
//!
//! That placement is deliberate. The security review records the drop-report renderer as *"the
//! sink people forget"*, and it is the one that echoes attacker-chosen archive entry names. In a
//! Tauri app a webview injection is not a defaced page — it is legitimate IPC control of the
//! whole console, live output included. Doing the work at the producer is what makes forgetting
//! harmless.
//!
//! What is stripped, and why each:
//!
//! - **C0 controls except `\n` and `\t`, and C1 controls** — ANSI escape sequences that would
//!   reformat a terminal log, and stray control bytes that reach SQLite and the UI.
//! - **NUL** — before it can reach SQLite or a `MediaRef`.
//! - **Bidi overrides `U+202A..U+202E` and isolates `U+2066..U+2069`** — these can visually
//!   reverse or splice text, and this is presentation software: what is imported gets projected
//!   to a congregation.
//!
//! What is **preserved**, and this is the easy mistake: **ZWJ (`U+200D`) and ZWNJ (`U+200C`)**.
//! They are load-bearing for Arabic, Persian and Indic scripts and for emoji sequences;
//! blanket-stripping the zero-width block would silently corrupt legitimate text.
//!
//! Homoglyph spoofing is not machine-detectable in general and is accepted residual — the
//! operator previewing a slide before Go Live is the real control there.

/// The outcome of cleaning one string: the cleaned text and how many characters were removed, so
//  the hygiene is never itself a silent loss.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Cleaned {
    /// The sanitised text, capped to the requested character budget.
    pub text: String,
    /// Characters removed by sanitising (not by the length cap — see [`truncated`](Self::truncated)).
    pub stripped: usize,
    /// Characters dropped by the length cap.
    pub truncated: usize,
}

impl Cleaned {
    /// Whether anything at all was removed.
    pub fn is_clean(&self) -> bool {
        self.stripped == 0 && self.truncated == 0
    }
}

/// Whether `c` is removed by [`clean`].
fn is_stripped(c: char) -> bool {
    match c {
        '\n' | '\t' => false,
        // C0 controls (including NUL and every ANSI escape introducer) and DEL.
        '\u{0}'..='\u{1F}' | '\u{7F}' => true,
        // C1 controls.
        '\u{80}'..='\u{9F}' => true,
        // Bidi embedding/override controls and isolates. NOT the zero-width joiners.
        '\u{202A}'..='\u{202E}' | '\u{2066}'..='\u{2069}' => true,
        _ => false,
    }
}

/// Sanitise `text` and cap it at `max_chars` **characters** (not bytes — the deck and slide
/// bounds count chars, and truncating by bytes would both fail those predicates on non-ASCII
/// text and risk splitting a character).
pub fn clean(text: &str, max_chars: usize) -> Cleaned {
    let mut out = String::with_capacity(text.len().min(max_chars.saturating_mul(4)));
    let mut stripped = 0usize;
    let mut kept = 0usize;
    let mut truncated = 0usize;
    for c in text.chars() {
        if is_stripped(c) {
            stripped += 1;
            continue;
        }
        if kept >= max_chars {
            truncated += 1;
            continue;
        }
        out.push(c);
        kept += 1;
    }
    Cleaned {
        text: out,
        stripped,
        truncated,
    }
}

/// Sanitise and flatten to a **single line**: every newline and tab becomes a space, runs of
/// whitespace collapse, and the result is trimmed. This is the deck-name and report-detail form
/// — a name carrying a newline would break every list rendering that assumes one line per row.
pub fn clean_single_line(text: &str, max_chars: usize) -> Cleaned {
    let mut flattened = String::with_capacity(text.len());
    let mut last_was_space = true; // leading whitespace is dropped
    let mut stripped = 0usize;
    for c in text.chars() {
        if is_stripped(c) && c != '\n' && c != '\t' {
            stripped += 1;
            continue;
        }
        if c.is_whitespace() {
            if !last_was_space {
                flattened.push(' ');
                last_was_space = true;
            }
            continue;
        }
        flattened.push(c);
        last_was_space = false;
    }
    while flattened.ends_with(' ') {
        flattened.pop();
    }
    let mut cleaned = clean(&flattened, max_chars);
    cleaned.stripped += stripped;
    cleaned
}
