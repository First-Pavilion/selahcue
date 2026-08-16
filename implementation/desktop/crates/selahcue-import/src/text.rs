//! The shared text splitter: `.txt` files and pasted text, one path.
//!
//! Both sources call [`parse`]. The only differences between them are the [`ImportSource`] label
//! and the default deck name — there is no second splitter and no source-specific branch inside
//! this one, so pasted text and a text file can never drift into producing different decks.
//!
//! **What "blank line" means.** Each rule below has a plausible wrong answer, so each is pinned
//! by a test:
//!
//! - A line is blank if it is empty **after trimming whitespace** — a line of spaces separates
//!   slides, because that is what the person typing it meant.
//! - **N consecutive blank lines are ONE separator**, not N−1 empty slides.
//! - Leading and trailing blank runs are discarded; a trailing newline does not produce an empty
//!   final slide.
//! - An empty slide is never produced. Entirely blank input yields zero slides and is the one
//!   text case that is genuinely an error rather than a report.

use crate::error::ImportError;
use crate::hygiene;
use crate::limits::{MAX_IMPORT_SLIDES, MAX_LINE_LEN, MAX_SLIDE_LINES, MAX_TITLE_LEN};
use crate::model::{ImportSource, ImportedDocument, ImportedSlide};
use crate::report::{LimitKind, ReportBuilder, SkipKind, TruncatedField};

/// Whether a text slide's first line becomes its title.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum TextLayout {
    /// The first line is the slide's title and the rest is body — the shipped default for both
    /// text sources. Every comparable tool works this way, the slide model is shaped that way,
    /// and a title-less slide renders worse under a theme that reserves a title region.
    #[default]
    FirstLineIsTitle,
    /// Every line is body. Carried as a parameter so the product default is a one-line change
    /// rather than a redesign.
    AllBody,
}

/// Options for the text path.
#[derive(Debug, Clone, Copy, Default)]
pub struct TextOptions {
    pub layout: TextLayout,
}

/// Split already-decoded, already-newline-normalised text into slides.
///
/// The report is accumulated as it goes, so a truncation is attributed to the slide it happened
/// on rather than reconstructed afterwards.
pub fn parse(
    text: &str,
    source: ImportSource,
    opts: &TextOptions,
    mut report: ReportBuilder,
) -> Result<ImportedDocument, ImportError> {
    let normalised = crate::decode::normalise_newlines(text);
    let mut slides: Vec<ImportedSlide> = Vec::new();
    let mut current: Vec<&str> = Vec::new();
    let mut hit_slide_cap = false;
    // Blocks of the SOURCE, counted whether or not each becomes a slide — the report's one index
    // space (see `ImportedSlide::source_index`). Using the output position instead would hand a
    // block's number to the next block as soon as hygiene emptied it.
    let mut block_index = 0usize;

    // `chain` appends one synthetic blank line so the final group is flushed by the same code
    // path as every other group — no duplicated flush at the end to drift out of step.
    for line in normalised.lines().chain(std::iter::once("")) {
        if line.trim().is_empty() {
            // N consecutive blanks are ONE separator: an empty group flushes to nothing.
            if current.is_empty() {
                continue;
            }
            let index = block_index;
            block_index = block_index.saturating_add(1);
            if slides.len() >= MAX_IMPORT_SLIDES {
                hit_slide_cap = true;
                current.clear();
                continue;
            }
            if let Some(slide) = build_slide(index, &current, opts, &mut report) {
                slides.push(slide);
            }
            current.clear();
        } else {
            current.push(line);
        }
    }

    if hit_slide_cap {
        report.skip(None, SkipKind::LimitReached(LimitKind::Slides), "");
    }
    if slides.is_empty() {
        return Err(ImportError::NothingToImport);
    }
    Ok(ImportedDocument {
        source,
        slides,
        report,
    })
}

/// Turn one group of consecutive non-blank lines into a slide, clamping and reporting as it goes.
fn build_slide(
    index: usize,
    lines: &[&str],
    opts: &TextOptions,
    report: &mut ReportBuilder,
) -> Option<ImportedSlide> {
    let (title_src, body_src): (Option<&str>, &[&str]) = match opts.layout {
        TextLayout::FirstLineIsTitle => match lines.split_first() {
            Some((first, rest)) => (Some(*first), rest),
            None => (None, &[]),
        },
        TextLayout::AllBody => (None, lines),
    };

    let title = title_src.map(|t| {
        let cleaned = hygiene::clean_single_line(t, MAX_TITLE_LEN);
        report.record_hygiene(&cleaned);
        report.truncate(
            index,
            TruncatedField::Title,
            cleaned.text.chars().count(),
            cleaned.truncated,
        );
        cleaned.text
    });

    let mut body: Vec<String> = Vec::new();
    for line in body_src.iter().take(MAX_SLIDE_LINES) {
        let cleaned = hygiene::clean(line, MAX_LINE_LEN);
        report.record_hygiene(&cleaned);
        report.truncate(
            index,
            TruncatedField::BodyLine,
            cleaned.text.chars().count(),
            cleaned.truncated,
        );
        body.push(cleaned.text);
    }
    if body_src.len() > MAX_SLIDE_LINES {
        report.truncate(
            index,
            TruncatedField::BodyLines,
            MAX_SLIDE_LINES,
            body_src.len() - MAX_SLIDE_LINES,
        );
    }

    let slide = ImportedSlide {
        source_index: index,
        title: title.filter(|t| !t.is_empty()),
        body,
        notes: String::new(),
        pictures: Vec::new(),
    };
    // Hygiene can empty a group that was entirely control characters; an empty slide is never
    // produced, so it is dropped here rather than shipped blank.
    slide.has_content().then_some(slide)
}
