//! Scripture reference detection over the transcript stream (R4; ADR-0010).
//!
//! The preacher speaks references aloud — "John chapter 3 verse 16", "First
//! Corinthians 13", "Romans eight twenty-eight" — and this module surfaces them as
//! **candidates the operator confirms** (operator-confirmation default, FR-115;
//! precision over recall, FR-121). It is pure and deterministic (NFR-014): the same
//! transcript text always yields the same detections, with no clock or ordering
//! nondeterminism.
//!
//! **Reuse, not reinvention.** Reference parsing is delegated wholesale to
//! [`selahcue_core::scripture::parse_one`](crate::scripture::parse_one) — that parser
//! *is* the book-name authority (an unknown leading book is rejected), so this module
//! only has to turn spoken language into candidate strings the parser already
//! understands (its space-shorthand `"john 3 16"` and numbered-book aliases
//! `"first corinthians"` do the heavy lifting) and then feed it windows of the text.
//!
//! Everything here is **bounded** (no-leak): the detection queue and the
//! cross-segment dedup window are hard-capped rings.

use crate::scripture::parse_one;
use crate::transcript::TranscriptLog;
use std::collections::VecDeque;

/// Upper bound on queued (un-actioned) detections. Older un-actioned candidates are
/// evicted once the cap is reached, so a flood of spoken references cannot grow memory
/// without limit (no-leak; asserted by the bounded-memory tests).
pub const MAX_DETECTIONS: usize = 32;

/// How many recently-detected references are remembered to suppress duplicates across
/// segments (a preacher repeating "John 3:16" should surface once, not on every breath —
/// precision, FR-121). A small fixed ring.
pub const RECENT_DEDUP_WINDOW: usize = 16;

/// The most tokens a single reference may span (e.g. "first corinthians thirteen four" —
/// numbered book + chapter + verse). Bounds the per-segment scan cost.
const MAX_WINDOW: usize = 6;

/// A scripture reference detected in the transcript, awaiting operator action.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DetectedReference {
    /// Queue-assigned id (what the operator's approve/dismiss actions reference).
    pub id: u64,
    /// The canonical, **parseable** reference (e.g. `"Romans 8:28"`) — stages directly
    /// via the existing scripture path.
    pub reference: String,
    /// The transcript segment id this was detected in (provenance for the UI).
    pub source_segment: u64,
}

/// Detect every scripture reference in one piece of transcript text, in order, as
/// canonical parseable strings (duplicates within this call collapsed). A **pure
/// function** — deterministic and side-effect-free.
///
/// Strategy: normalise spoken language into parser-ready tokens (spelled-out numbers
/// folded to digits, "chapter"/"verse" filler dropped, "X through Y" ranges joined),
/// then slide a window and hand each candidate to [`parse_one`], taking the longest
/// match from each position. The parser rejects any window not led by a real book, so
/// non-references never survive. A precision floor (≥3 alphabetic characters in the
/// book portion) suppresses the parser's two-letter typing aliases (`is`, `so`, `am`)
/// firing on ordinary speech.
pub fn detect(text: &str) -> Vec<String> {
    let tokens = normalize_tokens(text);
    let mut found: Vec<String> = Vec::new();
    let mut i = 0;
    while i < tokens.len() {
        let mut matched: Option<(String, usize)> = None;
        let max_end = (i + MAX_WINDOW).min(tokens.len());
        // Longest window first, so "john 3 16" wins over "john 3".
        let mut end = max_end;
        while end >= i + 2 {
            let window = &tokens[i..end];
            let alpha: usize = window
                .iter()
                .map(|t| t.chars().filter(|c| c.is_ascii_alphabetic()).count())
                .sum();
            if alpha >= 3 {
                let candidate = window.join(" ");
                if let Ok(r) = parse_one(&candidate) {
                    matched = Some((r.to_string(), end));
                    break;
                }
            }
            end -= 1;
        }
        match matched {
            Some((reference, next)) => {
                if !found.contains(&reference) {
                    found.push(reference);
                }
                i = next; // skip the consumed tokens (no overlapping double-count)
            }
            None => i += 1,
        }
    }
    found
}

/// Normalise transcript text into parser-ready tokens: lowercase; strip punctuation
/// (keeping `:` so a typed `"8:28"` still parses); drop "chapter"/"verse" filler; fold
/// spelled-out numbers ("twenty eight" → `28`, "one hundred nineteen" → `119`) to
/// digits; and join spoken ranges ("28 through 30" → `28-30`).
fn normalize_tokens(text: &str) -> Vec<String> {
    // 1. Lowercase; keep ASCII alphanumerics and ':' (a chapter:verse separator),
    //    everything else becomes a break.
    let cleaned: String = text
        .chars()
        .map(|c| {
            let c = c.to_ascii_lowercase();
            if c.is_ascii_alphanumeric() || c == ':' {
                c
            } else {
                ' '
            }
        })
        .collect();
    let raw: Vec<&str> = cleaned.split_whitespace().collect();

    // 2. Drop filler connectors (their numbers survive on their own).
    let words: Vec<&str> = raw
        .into_iter()
        .filter(|w| !matches!(*w, "chapter" | "chapters" | "verse" | "verses"))
        .collect();

    // 3. Fold spelled-out cardinal numbers into digit tokens.
    let mut folded: Vec<String> = Vec::new();
    let mut i = 0;
    while i < words.len() {
        if let Some((value, consumed)) = take_number(&words[i..]) {
            folded.push(value.to_string());
            i += consumed;
        } else {
            folded.push(words[i].to_string());
            i += 1;
        }
    }

    // 4. Join spoken ranges: <digits> <range-word> <digits> → "a-b".
    let mut out: Vec<String> = Vec::new();
    let mut j = 0;
    while j < folded.len() {
        if j + 2 < folded.len()
            && is_all_digits(&folded[j])
            && matches!(folded[j + 1].as_str(), "to" | "through" | "thru")
            && is_all_digits(&folded[j + 2])
        {
            out.push(format!("{}-{}", folded[j], folded[j + 2]));
            j += 3;
        } else {
            out.push(folded[j].clone());
            j += 1;
        }
    }
    out
}

fn is_all_digits(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c.is_ascii_digit())
}

/// A spoken-number word class.
#[derive(Clone, Copy)]
enum NumWord {
    /// 1..=9
    Ones(u16),
    /// 10..=19
    Teen(u16),
    /// 20,30,…,90
    Tens(u16),
    Hundred,
}

fn classify(word: &str) -> Option<NumWord> {
    Some(match word {
        "one" => NumWord::Ones(1),
        "two" => NumWord::Ones(2),
        "three" => NumWord::Ones(3),
        "four" => NumWord::Ones(4),
        "five" => NumWord::Ones(5),
        "six" => NumWord::Ones(6),
        "seven" => NumWord::Ones(7),
        "eight" => NumWord::Ones(8),
        "nine" => NumWord::Ones(9),
        "ten" => NumWord::Teen(10),
        "eleven" => NumWord::Teen(11),
        "twelve" => NumWord::Teen(12),
        "thirteen" => NumWord::Teen(13),
        "fourteen" => NumWord::Teen(14),
        "fifteen" => NumWord::Teen(15),
        "sixteen" => NumWord::Teen(16),
        "seventeen" => NumWord::Teen(17),
        "eighteen" => NumWord::Teen(18),
        "nineteen" => NumWord::Teen(19),
        "twenty" => NumWord::Tens(20),
        "thirty" => NumWord::Tens(30),
        "forty" => NumWord::Tens(40),
        "fifty" => NumWord::Tens(50),
        "sixty" => NumWord::Tens(60),
        "seventy" => NumWord::Tens(70),
        "eighty" => NumWord::Tens(80),
        "ninety" => NumWord::Tens(90),
        "hundred" => NumWord::Hundred,
        _ => return None,
    })
}

/// State of the spoken-number accumulator, encoding which magnitudes may still follow
/// so two adjacent numbers ("eight twenty eight" = 8 then 28) are not merged.
#[derive(Clone, Copy, PartialEq)]
enum NumState {
    Start,
    AfterOnes,
    AfterTens,
    AfterHundred,
    AfterHundredTens,
    Done,
}

/// Consume a maximal valid number starting at `tokens[0]`, returning `(value, tokens
/// consumed)` or `None` if it is not a number. A leading all-digit token is taken
/// verbatim; otherwise spelled-out words are combined by English magnitude rules
/// (a rising magnitude ends the number, so run-on speech splits correctly).
fn take_number(tokens: &[&str]) -> Option<(u16, usize)> {
    let first = *tokens.first()?;
    if is_all_digits(first) {
        // Cap at u16 so an absurd spoken/typed number can never overflow; the parser
        // rejects out-of-range chapters/verses anyway.
        let value: u16 = first.parse().unwrap_or(u16::MAX);
        return Some((value, 1));
    }
    let mut value: u16 = 0;
    let mut consumed = 0;
    let mut state = NumState::Start;
    for &tok in tokens {
        let Some(class) = classify(tok) else { break };
        let next = match (state, class) {
            (NumState::Start, NumWord::Ones(n)) => {
                value = n;
                NumState::AfterOnes
            }
            (NumState::Start, NumWord::Teen(n)) => {
                value = n;
                NumState::Done
            }
            (NumState::Start, NumWord::Tens(n)) => {
                value = n;
                NumState::AfterTens
            }
            (NumState::Start, NumWord::Hundred) => {
                value = 100;
                NumState::AfterHundred
            }
            (NumState::AfterOnes, NumWord::Hundred) => {
                value = value.saturating_mul(100);
                NumState::AfterHundred
            }
            (NumState::AfterTens, NumWord::Ones(n)) => {
                value = value.saturating_add(n);
                NumState::Done
            }
            (NumState::AfterHundred, NumWord::Tens(n)) => {
                value = value.saturating_add(n);
                NumState::AfterHundredTens
            }
            (NumState::AfterHundred, NumWord::Teen(n)) => {
                value = value.saturating_add(n);
                NumState::Done
            }
            (NumState::AfterHundred, NumWord::Ones(n)) => {
                value = value.saturating_add(n);
                NumState::Done
            }
            (NumState::AfterHundredTens, NumWord::Ones(n)) => {
                value = value.saturating_add(n);
                NumState::Done
            }
            // Any other transition (e.g. Ones then Tens) ends this number.
            _ => break,
        };
        state = next;
        consumed += 1;
        if state == NumState::Done {
            break;
        }
    }
    (consumed > 0).then_some((value, consumed))
}

/// A hard-capped queue of un-actioned scripture detections (the operator's approval
/// queue). Enqueue dedups against still-pending references; over-cap evicts the oldest.
#[derive(Debug, Clone, Default)]
pub struct DetectionQueue {
    items: VecDeque<DetectedReference>,
    next_id: u64,
}

impl DetectionQueue {
    pub fn new() -> Self {
        DetectionQueue {
            items: VecDeque::new(),
            next_id: 0,
        }
    }

    /// Enqueue a detected reference from `source_segment`. Returns the new id, or `None`
    /// if an identical reference is already pending (dedup). Evicts the oldest pending
    /// candidate when at capacity.
    pub fn enqueue(&mut self, reference: String, source_segment: u64) -> Option<u64> {
        if self.items.iter().any(|d| d.reference == reference) {
            return None;
        }
        let id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1);
        self.items.push_back(DetectedReference {
            id,
            reference,
            source_segment,
        });
        while self.items.len() > MAX_DETECTIONS {
            self.items.pop_front();
        }
        Some(id)
    }

    /// Remove and return the detection with `id` (the operator approved it).
    pub fn approve(&mut self, id: u64) -> Option<DetectedReference> {
        let pos = self.items.iter().position(|d| d.id == id)?;
        self.items.remove(pos)
    }

    /// Remove the detection with `id` without acting on it (dismissed). Returns whether
    /// one was removed.
    pub fn dismiss(&mut self, id: u64) -> bool {
        let before = self.items.len();
        self.items.retain(|d| d.id != id);
        self.items.len() != before
    }

    /// The pending detections, oldest first.
    pub fn pending(&self) -> impl Iterator<Item = &DetectedReference> {
        self.items.iter()
    }

    pub fn len(&self) -> usize {
        self.items.len()
    }

    pub fn is_empty(&self) -> bool {
        self.items.is_empty()
    }

    pub fn clear(&mut self) {
        self.items.clear();
    }
}

/// The transcript + detection engine: composes the bounded [`TranscriptLog`] with the
/// pure [`detect`] pass and the bounded [`DetectionQueue`], plus a small cross-segment
/// dedup ring. Pure and deterministic — the host feeds it segments (from any
/// [`TranscriptProvider`](crate::transcript::TranscriptProvider)) out-of-band and reads
/// back the bounded transcript + queue for the operator view.
#[derive(Debug, Clone, Default)]
pub struct TranscriptEngine {
    log: TranscriptLog,
    queue: DetectionQueue,
    recent_refs: VecDeque<String>,
}

impl TranscriptEngine {
    pub fn new() -> Self {
        TranscriptEngine {
            log: TranscriptLog::new(),
            queue: DetectionQueue::new(),
            recent_refs: VecDeque::new(),
        }
    }

    /// Ingest one transcript segment: append it to the (bounded) log, detect references,
    /// and enqueue any that are neither still-pending nor within the recent-dedup window.
    /// Returns the ids of the newly enqueued detections (empty when nothing new).
    pub fn ingest(&mut self, text: &str, start_ms: u64, end_ms: u64) -> Vec<u64> {
        let segment_id = self.log.push(text, start_ms, end_ms);
        let mut new_ids = Vec::new();
        for reference in detect(text) {
            if self.recent_refs.iter().any(|r| r == &reference) {
                continue;
            }
            if let Some(id) = self.queue.enqueue(reference.clone(), segment_id) {
                self.remember(reference);
                new_ids.push(id);
            }
        }
        new_ids
    }

    fn remember(&mut self, reference: String) {
        self.recent_refs.push_back(reference);
        while self.recent_refs.len() > RECENT_DEDUP_WINDOW {
            self.recent_refs.pop_front();
        }
    }

    /// Approve a queued detection (the operator staged it): removes and returns it.
    pub fn approve(&mut self, id: u64) -> Option<DetectedReference> {
        self.queue.approve(id)
    }

    /// Dismiss a queued detection without acting on it. Returns whether one was removed.
    pub fn dismiss(&mut self, id: u64) -> bool {
        self.queue.dismiss(id)
    }

    /// The bounded transcript log (for the operator view).
    pub fn transcript(&self) -> &TranscriptLog {
        &self.log
    }

    /// The bounded detection queue (for the operator view).
    pub fn detections(&self) -> &DetectionQueue {
        &self.queue
    }

    /// Reset transcript + detections (e.g. a new service). Bounded either way.
    pub fn clear(&mut self) {
        self.log.clear();
        self.queue.clear();
        self.recent_refs.clear();
    }
}

// Tests live in `tests/test_detection.rs` (public-API integration tests).
