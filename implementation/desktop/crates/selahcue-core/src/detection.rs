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
/// (keeping `:` so a typed `"8:28"` still parses); fold spelled-out numbers ("twenty
/// eight" → `28`, "one hundred nineteen" → `119`) to digits, including a
/// **digit-by-digit reading** ("one zero three" / "one oh three" → `103` — see
/// [`take_digit_run`]); drop "chapter"/"verse" filler (their numbers already survived
/// the fold on their own); and join spoken ranges ("28 through 30" → `28-30`).
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

    // 2. Fold spelled-out numbers into digit tokens — over these RAW tokens, i.e.
    //    BEFORE "chapter"/"verse" filler is dropped below. That ordering matters: it
    //    makes "chapter"/"verse" a natural stop for a digit-by-digit run the same way
    //    they already are for `take_number`'s cardinal grammar (`classify` doesn't
    //    recognise either word, so `take_number` already halts there) — no separate
    //    "boundary word" concept is needed in `take_digit_run` itself. Folding after
    //    stripping them (the first cut of this fix) erased that boundary and let a
    //    chapter read digit-by-digit fuse with a following digit-by-digit verse across
    //    the removed "verse" (review finding, Quinn, 86akd8jzg):
    //    `"one zero three verse four"` folded into one wrong `1034` instead of separate
    //    `103` and `4`. A digit-by-digit run is tried first at each position — it is a
    //    disjoint reading from the cardinal grammar `take_number` implements (see
    //    `take_digit_run`'s doc for why the two never conflict) — before falling back
    //    to the existing cardinal folding.
    let mut folded: Vec<String> = Vec::new();
    let mut i = 0;
    while i < raw.len() {
        if let Some((value, consumed)) = take_digit_run(&raw[i..]) {
            folded.push(value.to_string());
            i += consumed;
        } else if let Some((value, consumed)) = take_number(&raw[i..]) {
            folded.push(value.to_string());
            i += consumed;
        } else {
            folded.push(raw[i].to_string());
            i += 1;
        }
    }

    // 3. Drop filler connectors now that any numbers straddling them have already been
    //    folded on their own (step 2's ordering is what makes this safe).
    let words: Vec<String> = folded
        .into_iter()
        .filter(|w| !matches!(w.as_str(), "chapter" | "chapters" | "verse" | "verses"))
        .collect();

    // 4. Join spoken ranges: <digits> <range-word> <digits> → "a-b".
    let mut out: Vec<String> = Vec::new();
    let mut j = 0;
    while j < words.len() {
        if j + 2 < words.len()
            && is_all_digits(&words[j])
            && matches!(words[j + 1].as_str(), "to" | "through" | "thru")
            && is_all_digits(&words[j + 2])
        {
            out.push(format!("{}-{}", words[j], words[j + 2]));
            j += 3;
        } else {
            out.push(words[j].clone());
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

/// Does a number start at the beginning of `rest`? Used only by `take_digit_run`'s
/// boundary-then-number lookahead, to decide whether "chapter"/"verse" is genuinely
/// introducing another number rather than ordinary continuing speech.
///
/// `take_number(rest).is_some()` alone is not enough: `classify()` has no entry for
/// "zero"/"oh", so a number that itself starts with a spoken zero ("verse zero four",
/// "verse oh five") makes `take_number` report nothing, even though it plainly is one
/// (review finding, Cody). The fallback below covers exactly that gap -- rest begins
/// with a zero/oh immediately followed by another digit word -- without recursing into
/// `take_digit_run` itself: recursion would let a hostile "zero verse zero verse..."
/// flood chain lookahead calls and go quadratic, which is exactly the risk this
/// non-recursive, two-token check avoids while still being O(1) per call (measured
/// linear across five input-size doublings; see PR review evidence).
fn starts_a_number(rest: &[&str]) -> bool {
    take_number(rest).is_some()
        || (rest.first().is_some_and(|&w| digit_word(w) == Some(0))
            && rest.get(1).is_some_and(|&w| digit_word(w).is_some()))
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
/// string, or the u32 accumulator, without limit. Rule 3 (the boundary-then-number
/// lookahead below) is itself bounded by the same `limit` as the rest of the scan, so it
/// can never reach a zero past the documented cap (review finding, Quinn: an earlier
/// draft let it peek past the cap). Rule 4 (end-of-input, also below) is deliberately
/// NOT bounded by `limit` the same way -- "is there truly nothing left in the input" is
/// a question about the whole `tokens` slice, not about what this call may consume --
/// so a zero sitting exactly at the cap boundary CAN still be rescued by Rule 4 if it is
/// also the last token in the input: `detect("psalm one one one one one zero")` ->
/// `"Psalms 65535"`, the clamp below saturating on a run this length. Degenerate,
/// bounded, and harmless (no realistic spoken chapter/verse has this shape) -- stated
/// plainly because this comment previously claimed a cap-boundary zero was always
/// trailing and excluded, which stopped being true the moment Rule 4 was added, and this
/// same sentence region had already been corrected twice before for saying one thing
/// while the code did another (review finding, Sana).
/// Returns `(value, tokens consumed)` or `None`.
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

            // Rule: a chapter ending in a spoken zero, immediately before a
            // "chapter"/"verse" marker that itself introduces another number
            // ("...one zero verse four..."), is internal -- literal "zero" only (see
            // below), bounded by `limit` so this can never reach past
            // MAX_DIGIT_RUN's documented cap (review finding, Quinn/Cody).
            // `starts_a_number` -- not a raw `take_number` call -- covers the number
            // after the marker itself starting with a spoken zero ("verse zero four"),
            // which plain `take_number` cannot see (`classify` has no "zero"/"oh" entry)
            // and would otherwise wrongly report "no number here", withdrawing this
            // rescue (review finding, Cody, Finding 2).
            let followed_by_boundary_then_number = i + 1 < limit
                && tokens[i] == "zero"
                && tokens
                    .get(i + 1)
                    .is_some_and(|&w| matches!(w, "chapter" | "chapters" | "verse" | "verses"))
                && tokens.get(i + 2..).is_some_and(starts_a_number);

            // Rule: a verse ending in a spoken zero, with NOTHING else left in the
            // input, is internal -- literal "zero" only, never "oh". A verse is
            // ordinarily the last number in a citation, so there is no following
            // marker+number for the rule above to find; the discriminator here is
            // instead "does anything at all follow" (review finding, Cody, Finding 1:
            // rule 3 alone can rescue a chapter's trailing zero but structurally never a
            // verse's, since nothing ever follows the last number in an utterance for it
            // to be "before"). An interjection needs either a reaction target before it
            // or trailing words after it ("oh, how majestic", "zero tolerance for...");
            // a "zero" that simply ends the segment, with nothing following to be
            // idiomatic about, is read as completing the number.
            //
            // "oh" stays excluded here for the same reason it is excluded from the rule
            // above -- but it is worth spelling out why that is probably still right
            // even with nothing following, rather than leaving a future reader to
            // mistake the asymmetry with `followed_by_digit` (which accepts "oh" freely)
            // for an oversight and "fix" it into a regression: "oh" alone can be a
            // complete, standalone exclamation ("Psalm eight... oh!") in a way "zero"
            // essentially never is -- nobody ends a sentence on a bare "zero" as a
            // reaction. Pinned: `detect("psalm one oh")` stays `["Psalms 1"]` (review
            // finding, Cody; regression-tested, Quinn -- mutating this check from the
            // literal `"zero"` to "any digit_word mapping to 0" passes all 60
            // pre-existing tests silently and turns `"psalm eight oh"` into the wrong
            // `"Psalms 80"`, so the literal-word restriction here is load-bearing even
            // though nothing else in this file's tests exercised it before).
            //
            // ACCEPTED RISK, KNOWINGLY TAKEN (not an oversight -- read this before
            // touching this line): "nothing follows" means nothing follows in THIS
            // TRANSCRIPT SEGMENT, and a segment boundary is not the same thing as an
            // utterance boundary. Cloud STT sends two independent signals -- `is_final`
            // ("this text will not be revised") and `speech_final` ("the speaker paused
            // here") -- and Deepgram can settle a chunk of text mid-utterance, before
            // `speech_final` fires (see `selahcue-stt-cloud/src/protocol.rs`). This
            // detector is only ever handed `is_final` segments (`speech_final` is parsed
            // there but dropped before it reaches here); the on-device engine has an
            // analogous exposure via `max_utterance_samples` force-closing unbroken
            // speech with no VAD-detected pause. So if a provider settles a segment
            // right after "zero" -- e.g. "John three zero" cut from "John three zero
            // tolerance for sin" -- this rule cannot tell that apart from a verse
            // genuinely ending in ten: no rule reading a single segment's text can, since
            // the disambiguating fact (did more speech actually follow) is not present
            // in what this function receives.
            //
            // Accepted rather than withheld: every digit-by-digit verse ending in zero
            // is confidently WRONG today with no split required at all, which is the
            // certainty this rule trades against a possibility. Operator confirmation
            // (FR-115) remains the gate before anything goes live either way. A
            // "must be preceded by a chapter/verse marker" companion condition was
            // considered and rejected -- it only closes the chapter-position slice of
            // this exposure; Cody's actual cases are all verse-position (immediately
            // preceded by "verse"), exactly where this risk concentrates, so that
            // condition would leave the case this rule exists for exactly as exposed.
            // Concretely: `"john three verse two zero"`, as if cut mid-"zero tolerance"
            // right after the marker, satisfies "preceded by verse" and would still be
            // rescued to `"John 3:20"` under that condition, when the uncut utterance,
            // `"john three verse two zero tolerance for sin"`, correctly gives
            // `"John 3:2"` (review addition, Sana).
            //
            // The real fix is threading `speech_final` (or the on-device equivalent)
            // through to here and gating THIS rule alone on it -- tracked as 86akdpw83,
            // linked to 86akd8903. NOT a claim that the other rules above are safe from
            // the same class of split, though an earlier draft of this comment wrongly
            // said so: `detect("psalm one zero verse")` -- a split right after "verse",
            // rule 3's own decision point -- gives `"Psalms 1"`, a wrong chapter at 95%
            // confidence via the pre-existing sliding-window fallback, not an incomplete
            // one (review finding, Sana). That the exposure is broader than this comment
            // used to claim argues FOR 86akdpw83, not against it: threading a real
            // utterance-boundary signal through is worth more than "gate Rule 4 alone"
            // implied, even though Rule 4 is the rule this PR adds and so the one it
            // takes direct responsibility for here.
            let is_final_zero_in_input = tokens[i] == "zero" && tokens.get(i + 1).is_none();

            if !followed_by_digit && !followed_by_boundary_then_number && !is_final_zero_in_input {
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
    // final clamp into u16 below. That clamp exists purely to avoid an overflow panic on
    // the cast -- it is NOT a correctness backstop: `parse_chapter_verse` in
    // scripture.rs does not range-check chapter/verse numbers against real book lengths
    // (e.g. `detect("psalm 151")` -> `"Psalms 151"` and `detect("john 99999")` ->
    // `"John 65535"`, on this commit and on unmodified `main` alike), so a saturated
    // value here can still surface as a plausible-looking wrong detection, exactly like
    // any other out-of-range input this parser already accepts. `saw_internal_zero`
    // above is the actual correctness control (review finding, Sana: an earlier version
    // of this comment cited the parser's leniency as a mitigating control, which it is
    // not).
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
