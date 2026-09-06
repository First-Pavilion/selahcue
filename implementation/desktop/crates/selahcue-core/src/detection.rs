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

/// Confidence assigned to an **explicitly-detected** reference — one the parser matched
/// verbatim from the spoken words (e.g. "Romans eight twenty-eight"). It is a deliberate,
/// explicit citation, so it ranks high (renders green in the operator's match-% pill), but
/// stays below 100 to stay honest about STT mishearing a spoken number. A *fuzzy quote*
/// match instead carries its own coverage-derived score.
pub const NAMED_REFERENCE_CONFIDENCE: u8 = 95;

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
    /// Detector confidence as a whole percent (`0..=100`): [`NAMED_REFERENCE_CONFIDENCE`]
    /// for an explicitly-spoken reference, or the fuzzy quote matcher's coverage score for
    /// a paraphrase. Surfaces as the operator's "N% MATCH" pill.
    pub confidence: u8,
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
/// digits, including a **digit-by-digit reading** ("one zero three" / "one oh three" →
/// `103` — see [`take_digit_run`]); and join spoken ranges ("28 through 30" → `28-30`).
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

    // 3. Fold spelled-out cardinal numbers into digit tokens. A digit-by-digit run
    //    ("one zero three") is tried first — it is a disjoint reading from the cardinal
    //    grammar `take_number` implements (see `take_digit_run`'s doc for why the two
    //    never conflict) — before falling back to the existing cardinal folding.
    let mut folded: Vec<String> = Vec::new();
    let mut i = 0;
    while i < words.len() {
        if let Some((value, consumed)) = take_digit_run(&words[i..]) {
            folded.push(value.to_string());
            i += consumed;
        } else if let Some((value, consumed)) = take_number(&words[i..]) {
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

/// The longest a digit-by-digit run ("one zero three") may span. Bounds
/// [`take_digit_run`]'s scan and its resulting numeric string to a fixed size regardless
/// of how long a hostile transcript segment's word run is (no-leak). Six comfortably
/// covers any real chapter/verse number spoken digit-by-digit. `pub` so the
/// bounded-memory test can pin against it directly rather than a hardcoded copy.
pub const MAX_DIGIT_RUN: usize = 6;

// Pinned so the constant can never shrink below what the reported bug case needs
// ("one zero three" is 3 words) without this failing to compile — a silent regression
// here would reopen 86akd8903 without any test noticing.
const _: () = assert!(MAX_DIGIT_RUN >= 3);

/// Maps a single spoken digit word (`"zero"`/`"oh"` through `"nine"`) to its value, or
/// `None` for anything else — in particular the teen/tens/hundred words, which never
/// appear inside a digit-by-digit reading and so are deliberately excluded here (they
/// stay [`classify`]'s and [`take_number`]'s job).
fn digit_word(word: &str) -> Option<u8> {
    Some(match word {
        "zero" | "oh" => 0,
        "one" => 1,
        "two" => 2,
        "three" => 3,
        "four" => 4,
        "five" => 5,
        "six" => 6,
        "seven" => 7,
        "eight" => 8,
        "nine" => 9,
        _ => return None,
    })
}

/// Consume a maximal run of single-digit spoken words at the start of `tokens` — but
/// only when that run is at least two words long **and contains a "zero"/"oh" that is
/// itself immediately followed by another digit word** (i.e. the zero/oh is internal to
/// the run, never its last word).
///
/// That "internal" qualifier is the whole design, and it is stricter than it first looks
/// like it needs to be. No English cardinal number is ever spoken with an internal zero
/// ("one zero three" is never how anyone says a cardinal number), so a zero/oh inside a
/// run of single-digit words IS an unambiguous signal of digit-by-digit reading — but
/// only while more digits follow it. A *trailing* zero/oh, where the run ends right
/// there, is NOT unambiguous: a spoken chapter digit followed by "oh" is indistinguishable
/// from that same digit followed by the ordinary English interjection "oh" ("Psalm
/// eight! Oh, how majestic...", which is itself Psalm 8:1), a self-correction ("chapter
/// three, oh, I mean four"), or the idiom "zero tolerance"/"zero in". All three are
/// common in live preaching, far more so than a number genuinely ending in a spoken
/// zero, and folding them reintroduces exactly the silently-wrong-high-confidence
/// detection this function exists to eliminate, via a different trigger word (review
/// finding on 86akd8903 PR #27 — Sana, independently confirmed by Cody). So a trailing
/// zero/oh is excluded from the run entirely: the run ends BEFORE it, and if that leaves
/// fewer than 2 digits or no internal zero, this returns `None` and the token(s) fall
/// back to `take_number`/literal handling exactly as before this function existed.
///
/// Recorded trade-off, not an oversight: a chapter/verse number that genuinely ends in a
/// spoken zero ("one two zero" for 120) is not read digit-by-digit by this function — it
/// falls back to whatever handling a stray trailing "zero" already got (an unrecognised
/// literal token). "one twenty" is overwhelmingly the more natural spoken form anyway.
///
/// Without a zero, a bare run of single-digit words is left entirely alone here —
/// `take_number`'s existing cardinal-combination state machine already owns that case
/// (e.g. it stops "eight" at a following "twenty" on its own), and this function must
/// never compete with it, or "Romans eight twenty-eight" would fold into "828" instead
/// of staying "8" then "28".
///
/// Bounded to [`MAX_DIGIT_RUN`] words so a pathological run can never grow the resulting
/// string, or the u32 accumulator, without limit. A zero/oh sitting exactly at that cap
/// boundary is also treated as trailing (nothing this function is allowed to look at
/// follows it) and excluded, on the same conservative principle. Returns `(value, tokens
/// consumed)` or `None`.
fn take_digit_run(tokens: &[&str]) -> Option<(u16, usize)> {
    let limit = tokens.len().min(MAX_DIGIT_RUN);
    let mut digits: Vec<u8> = Vec::new();
    let mut saw_internal_zero = false;
    let mut i = 0;
    while i < limit {
        let Some(d) = digit_word(tokens[i]) else {
            break;
        };
        if d == 0 {
            let followed_by_digit = i + 1 < limit && digit_word(tokens[i + 1]).is_some();
            if !followed_by_digit {
                // Trailing zero/oh: stop the run BEFORE it rather than folding it in.
                break;
            }
            saw_internal_zero = true;
        }
        digits.push(d);
        i += 1;
    }
    if digits.len() < 2 || !saw_internal_zero {
        return None;
    }
    // Cap in u32 first so a full MAX_DIGIT_RUN of "nine"s cannot overflow before the
    // final clamp into u16 (the parser rejects out-of-range chapters/verses anyway).
    let value: u32 = digits.iter().fold(0u32, |acc, &d| {
        acc.saturating_mul(10).saturating_add(d as u32)
    });
    Some((value.min(u16::MAX as u32) as u16, digits.len()))
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
    pub fn enqueue(
        &mut self,
        reference: String,
        source_segment: u64,
        confidence: u8,
    ) -> Option<u64> {
        if self.items.iter().any(|d| d.reference == reference) {
            return None;
        }
        let id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1);
        self.items.push_back(DetectedReference {
            id,
            reference,
            source_segment,
            confidence,
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

    /// Ingest one transcript segment: append it to the (bounded) log, detect explicit
    /// references, and enqueue any that are neither still-pending nor within the recent-dedup
    /// window. Returns the ids of the newly enqueued detections (empty when nothing new).
    pub fn ingest(&mut self, text: &str, start_ms: u64, end_ms: u64) -> Vec<u64> {
        self.ingest_with_quotes(text, start_ms, end_ms, &[])
    }

    /// Like [`ingest`](Self::ingest), but also enqueues `quote_refs` — canonical references
    /// produced by an external **fuzzy quote/paraphrase matcher** the caller runs over the
    /// scripture corpus (the pure core cannot see the corpus, so the candidates are injected).
    /// Explicit references (from [`detect`]) are enqueued first, so an explicitly-spoken
    /// "John 3:16" takes precedence over a fuzzy quote match for the same verse via the
    /// recent-dedup + still-pending dedup below; a quote candidate that duplicates one is
    /// dropped. Both share the same `source_segment` and flow through the same bounded queue.
    /// Deterministic: `quote_refs` are enqueued in the caller-supplied order.
    pub fn ingest_with_quotes(
        &mut self,
        text: &str,
        start_ms: u64,
        end_ms: u64,
        quote_refs: &[(String, u8)],
    ) -> Vec<u64> {
        let segment_id = self.log.push(text, start_ms, end_ms);
        let mut new_ids = Vec::new();
        // Explicit references first (high confidence), so an explicitly-spoken "John 3:16"
        // wins the dedup over a fuzzy quote match for the same verse and keeps its score.
        for reference in detect(text) {
            self.try_enqueue(
                reference,
                segment_id,
                NAMED_REFERENCE_CONFIDENCE,
                &mut new_ids,
            );
        }
        for (reference, confidence) in quote_refs {
            self.try_enqueue(reference.clone(), segment_id, *confidence, &mut new_ids);
        }
        new_ids
    }

    /// Enqueue one candidate reference (with its detector confidence) unless it is within the
    /// recent-dedup window or already pending; on success, remember it and record the new id.
    fn try_enqueue(
        &mut self,
        reference: String,
        segment_id: u64,
        confidence: u8,
        new_ids: &mut Vec<u64>,
    ) {
        if self.recent_refs.iter().any(|r| r == &reference) {
            return;
        }
        if let Some(id) = self
            .queue
            .enqueue(reference.clone(), segment_id, confidence)
        {
            self.remember(reference);
            new_ids.push(id);
        }
    }

    fn remember(&mut self, reference: String) {
        self.recent_refs.push_back(reference);
        while self.recent_refs.len() > RECENT_DEDUP_WINDOW {
            self.recent_refs.pop_front();
        }
    }

    /// Current size of the cross-segment dedup ring — exposed so a bounded-memory test can
    /// assert it stays ≤ [`RECENT_DEDUP_WINDOW`] under a flood of distinct references (the
    /// same pattern as `DetectionQueue::len` and the session `active_count`/`pending_count`).
    pub fn recent_dedup_len(&self) -> usize {
        self.recent_refs.len()
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
