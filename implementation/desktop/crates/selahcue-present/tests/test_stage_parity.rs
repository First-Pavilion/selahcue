//! Design 2.0 parity for the stage / confidence monitor.
//!
//! Every assertion here is traceable to a row of
//! `docs/design/DESIGN-2.0-PARITY-AUDIT-stage.md` — the STG-### id is named in each test.
//! The audit's §6.4 table is the oracle for type size, and it is re-derived here from the
//! Figma **em** and the documented `h_frac = em / 0.72 / 563` relation rather than read out
//! of `stage.rs`, so a constant that drifts in the source cannot drift in step with the test.
//!
//! Sizes are checked at a real 1920×1080 stage output; 1920/1080 is within 0.1 % of the
//! 1000/563 reference aspect, so the design scales onto it essentially exactly.

#![allow(clippy::unwrap_used)]

use selahcue_engine::scene::{Frame, Layer, Rgba, ShapeKind};
use selahcue_present::stage::{
    StageTemplate, STAGE_TEXT_SCALE_DEFAULT, STAGE_TEXT_SCALE_MAX, STAGE_TEXT_SCALE_MIN,
};
use selahcue_present::{
    compose_stage, Slide, StageContext, StageDisplay, StageTheme, TimerView, WallClock,
};

const W: u32 = 1920;
const H: u32 = 1080;

/// The Design 2.0 figures this file checks the composer against, transcribed from the audit
/// (§3.1/§6.4) rather than imported — `stage.rs`'s own copies are what is under test, so a
/// shared constant would let source and oracle drift together.
mod design {
    /// Worship — the FIXED lyric rect Figma 373:133 draws (the two-line case).
    pub const Y_LYRIC: f64 = 131.5;
    pub const H_LYRIC: f64 = 212.0;
    /// Worship — where the design puts the NEXT row and the timer band.
    pub const Y_NEXT_ROW: f64 = 377.5;
    pub const Y_TIMER_BAND: f64 = 456.0;
}

/// The audit's reference frame and line-box ratio (§6.3/§6.4). Restated here so this file is
/// an independent oracle rather than a mirror of the implementation's constants.
const REF_H: f64 = 563.0;
const FONT_TO_LINE: f64 = 0.72;

// If the reference frame were the render size, `cell()` below would collapse to `em/0.72`
// and every size assertion would pass whatever the composer did with the frame height.
const _: () = assert!(REF_H != H as f64);

/// The line box the composer must pass for a Figma font size `em`, at height `h`.
fn cell(em: f64, h: u32, scale_permille: u16) -> u32 {
    ((em / FONT_TO_LINE / REF_H) * h as f64 * (scale_permille as f64 / 1000.0)).max(1.0) as u32
}

/// The rendered glyph size ("px-equivalent") for a line box.
fn em_of(cell_px: u32) -> f64 {
    cell_px as f64 * FONT_TO_LINE
}

fn slide(title: &str, body: &[&str]) -> Slide {
    Slide::new(title, body.iter().copied())
}

fn running() -> TimerView {
    TimerView {
        elapsed_secs: 100,
        remaining_secs: Some(765), // 12:45
        time_up: false,
        warn: false,
        progress: 0.5,
        overrun_secs: 0,
    }
}

/// 32 seconds past zero — the `OVER 0:32` both TIME-UP frames draw.
fn timed_up() -> TimerView {
    timed_up_by(32)
}

fn timed_up_by(overrun: u32) -> TimerView {
    TimerView {
        elapsed_secs: 900 + overrun,
        remaining_secs: Some(0),
        time_up: true,
        warn: false,
        progress: 0.0,
        overrun_secs: overrun,
    }
}

fn ctx(scale: u16) -> StageContext {
    StageContext {
        clock: Some(WallClock::new("Sunday · August 3, 2026", "10:42 AM")),
        song_position: Some((2, 4)),
        text_scale_permille: scale,
    }
}

fn compose(
    template: StageTemplate,
    up: bool,
    scale: u16,
    message: Option<&str>,
    w: u32,
    h: u32,
) -> Frame {
    let cur = slide("Amazing Grace", &["Amazing grace"]);
    let next = slide("Isaiah 61:6", &["I once was lost, but now am found"]);
    let t = if up { timed_up() } else { running() };
    compose_stage(
        Some(&cur),
        Some(&next),
        Some(&t),
        template,
        message,
        &ctx(scale),
        &StageTheme::dark(),
        w,
        h,
    )
}

/// Timer-only wants a segment title, not a song — the composer treats a slide WITH body
/// lines as a song, which the timer-only template does not use.
fn compose_timer_only(up: bool, scale: u16) -> Frame {
    let cur = slide("Sermon", &[]);
    let t = if up { timed_up() } else { running() };
    compose_stage(
        Some(&cur),
        None,
        Some(&t),
        StageTemplate::TimerOnly,
        None,
        &ctx(scale),
        &StageTheme::dark(),
        W,
        H,
    )
}

/// The `(line-box px, letter-spacing px)` of the chrome run whose text is exactly `needle`.
fn run(frame: &Frame, needle: &str) -> (u32, i32) {
    frame
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text {
                text, px, style, ..
            } if text == needle => Some((*px, style.map(|s| s.letter_spacing_px).unwrap_or(0))),
            _ => None,
        })
        .unwrap_or_else(|| {
            panic!(
                "no stage run reads {needle:?} — the layout changed, so the size assertion \
                 below never ran. Runs present: {:?}",
                texts(frame)
            )
        })
}

/// As [`run`], but matching on a PREFIX — for runs the composer may legitimately ellipsize
/// (the next lines), whose rendered text is a truncation of what was authored.
fn run_prefix(frame: &Frame, prefix: &str) -> (u32, i32) {
    frame
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text {
                text, px, style, ..
            } if text.starts_with(prefix) => {
                Some((*px, style.map(|s| s.letter_spacing_px).unwrap_or(0)))
            }
            _ => None,
        })
        .unwrap_or_else(|| {
            panic!(
                "no stage run starts with {prefix:?}. Runs present: {:?}",
                texts(frame)
            )
        })
}

fn texts(frame: &Frame) -> Vec<String> {
    frame
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Text { text, .. } => Some(text.clone()),
            _ => None,
        })
        .collect()
}

fn has_text(frame: &Frame, needle: &str) -> bool {
    texts(frame).iter().any(|t| t.contains(needle))
}

/// The largest line box among the auto-fit runs containing `needle` (the wrapped lyric /
/// verse / message body is split across layers).
fn autofit_cap(frame: &Frame, needle: &str) -> u32 {
    frame
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Text { text, px, .. } if text.contains(needle) => Some(*px),
            _ => None,
        })
        .max()
        .unwrap_or_else(|| panic!("no auto-fit run contains {needle:?}"))
}

fn shapes(frame: &Frame) -> Vec<(ShapeKind, u32, u32, u32, u32, Rgba, Rgba)> {
    frame
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Shape {
                rect,
                kind,
                fill,
                border,
                border_px,
                corner_px,
            } => Some((
                *kind, rect.w, rect.h, *border_px, *corner_px, *fill, *border,
            )),
            _ => None,
        })
        .collect()
}

// --- STG-019…STG-072: type sizes are the Design 2.0 sizes (audit §6.4) -------------------

/// The composer rendered its chrome at roughly 60–75 % of the designed type size; this is
/// the whole §6.4 substitution, one row per role. Closes STG-019/020/021/024/025/028/030/
/// 037/040/041/042/044/045/049/051/054/055/056/057/060/064.
#[test]
fn type_sizes_match_the_design_2_0_reference() {
    let s = STAGE_TEXT_SCALE_DEFAULT;

    // Worship, running (Figma 373:133).
    let ws = compose(StageTemplate::Worship, false, s, None, W, H);
    for (role, needle, em) in [
        ("song title (STG-019)", "Amazing Grace", 22.0),
        ("stanza position (STG-020)", "Verse 2 of 4", 20.0),
        ("header clock (STG-021)", "10:42 AM", 30.0),
        ("SERVICE TIMER (STG-028)", "SERVICE TIMER", 20.0),
        ("timer readout (STG-030)", "12:45", 52.0),
    ] {
        let (px, _) = run(&ws, needle);
        assert_eq!(
            px,
            cell(em, H, s),
            "worship {role}: line box {px} px, design {em} px em wants {} px",
            cell(em, H, s)
        );
    }
    // The lyric band (STG-022) and the NEXT row (STG-024/025) are deliberately NOT in this
    // table: owner direction made the live band fill its region and the NEXT row a ratio of
    // whatever the band resolved to, so they have no fixed size to pin. Their contracts are
    // `the_live_band_grows_to_fill_its_region`,
    // `the_next_line_never_outgrows_the_live_line` and
    // `the_next_row_keeps_the_designs_ratio_to_the_live_line`.

    // Worship, TIME UP (Figma 373:159).
    let wsu = compose(StageTemplate::Worship, true, s, None, W, H);
    assert_eq!(
        run(&wsu, "TIME UP").0,
        cell(46.0, H, s),
        "worship TIME UP word (STG-037)"
    );
    assert_eq!(
        run(&wsu, "OVER 0:32").0,
        cell(22.0, H, s),
        "worship overrun pill label (STG-038)"
    );

    // Scripture (Figma 374:128).
    let sc = compose(StageTemplate::Scripture, false, s, None, W, H);
    for (role, needle, em) in [
        ("screen label (STG-040)", "STAGE · SCRIPTURE", 20.0),
        ("header clock (STG-041)", "10:42 AM", 28.0),
        ("reference (STG-042)", "AMAZING GRACE", 30.0),
        ("status pill label (STG-049)", "ON TIME", 13.0),
        ("TIME LEFT (STG-051)", "TIME LEFT", 15.0),
        ("big readout (374:145)", "12:45", 96.0),
    ] {
        let (px, _) = run(&sc, needle);
        assert_eq!(
            px,
            cell(em, H, s),
            "scripture {role}: line box {px} px, design {em} px em wants {} px",
            cell(em, H, s)
        );
    }

    // Timer-only (Figma 374:151 / 374:166).
    let to = compose_timer_only(false, s);
    for (role, needle, em) in [
        ("header label (STG-054)", "SERVICE TIMER", 20.0),
        ("header clock (STG-055)", "10:42 AM", 28.0),
        ("segment label (STG-056)", "SERMON", 26.0),
        ("giant readout (STG-057)", "12:45", 190.0),
    ] {
        let (px, _) = run(&to, needle);
        assert_eq!(
            px,
            cell(em, H, s),
            "timer-only {role}: line box {px} px, design {em} px em wants {} px",
            cell(em, H, s)
        );
    }
    assert_eq!(
        run(&to, "Sunday · August 3, 2026 · 10:42 AM").0,
        cell(30.0, H, s),
        "timer-only footer (STG-060)"
    );

    let tou = compose_timer_only(true, s);
    assert_eq!(
        run(&tou, "TIME UP").0,
        cell(130.0, H, s),
        "timer-only TIME UP word (STG-064)"
    );
    assert_eq!(
        run(&tou, "OVER BY 0:32").0,
        cell(28.0, H, s),
        "timer-only overrun pill label (STG-065)"
    );
    assert_eq!(
        run(&tou, "Sunday · August 3, 2026").0,
        cell(22.0, H, s),
        "timer-only TIME-UP date (STG-066)"
    );

    // Production message overlay (Figma 375:128). `SLOW DOWN` is one of the four preset
    // payloads (Figma 563:169-175) and sits well inside the card's body box, so the cap is
    // reached exactly; `long_message_shrinks_inside_the_card` covers the shrink path.
    let msg = compose(StageTemplate::Worship, false, s, Some("SLOW DOWN"), W, H);
    assert_eq!(
        run(&msg, "MESSAGE FROM PRODUCTION").0,
        cell(18.0, H, s),
        "message chip label (STG-071)"
    );
    assert_eq!(
        autofit_cap(&msg, "SLOW DOWN"),
        cell(56.0, H, s),
        "message body cap (STG-072)"
    );
}

/// The design's type is a fraction of the frame HEIGHT, so the same role must scale between
/// output resolutions. Without this, `type_sizes_match_the_design_2_0_reference` could be
/// satisfied by nine hard-coded pixel constants that happen to be right at 1080.
#[test]
fn type_sizes_scale_with_the_output_height() {
    let s = STAGE_TEXT_SCALE_DEFAULT;
    let big = compose(StageTemplate::Worship, false, s, None, 1920, 1080);
    let small = compose(StageTemplate::Worship, false, s, None, 1280, 720);
    let (b, _) = run(&big, "12:45");
    let (m, _) = run(&small, "12:45");
    assert_eq!(b, cell(52.0, 1080, s));
    assert_eq!(m, cell(52.0, 720, s));
    assert!(
        m < b,
        "the readout is {m} px at 720p and {b} px at 1080p — type is not tracking the frame"
    );
}

/// The message body auto-fits: a note that does not fit the card at the design size shrinks
/// rather than clipping, and never grows past the design cap. Measured on the LONGEST preset
/// payload the console can send (`WRAP UP · 2 MIN LEFT`, Figma 563:169), which our shaper
/// measures a hair wider than the design's own 612px body box — so it lands one pixel under
/// the cap. That is the auto-fit doing its job, not a size regression.
#[test]
fn a_long_message_shrinks_inside_the_card_and_never_exceeds_the_design_cap() {
    let s = STAGE_TEXT_SCALE_DEFAULT;
    let cap = cell(56.0, H, s);
    let longest = compose(
        StageTemplate::Worship,
        false,
        s,
        Some("WRAP UP · 2 MIN LEFT"),
        W,
        H,
    );
    let got = autofit_cap(&longest, "WRAP UP");
    assert!(
        got <= cap,
        "the message body rendered at {got} px, past the design cap of {cap} px"
    );
    assert!(
        got >= cap - 2,
        "the longest preset shrank to {got} px against a {cap} px cap — the card's body box \
         is no longer big enough for the design size"
    );
    // A note far past the card shrinks a long way, and still shows every word (no clipping).
    let overlong = "zulu ".repeat(14);
    let big = compose(
        StageTemplate::Worship,
        false,
        s,
        Some(overlong.trim()),
        W,
        H,
    );
    let shrunk = autofit_cap(&big, "zulu");
    assert!(
        shrunk < cap,
        "a 70-character note rendered at the full design size ({shrunk} px) — it cannot have \
         fitted the card"
    );
}

// --- Owner defect: the live band must FILL its region, and NEXT must stay subordinate ------

/// Content whose lyric lines are individually addressable, plus a distinctive NEXT line.
fn worship_with(lines: usize) -> Frame {
    let body: Vec<String> = (0..lines).map(|i| format!("alpha{i:02} beta")).collect();
    let cur = Slide::new("Amazing Grace", body);
    let next = Slide::new("Next Item", ["coming zulu line"]);
    compose_stage(
        Some(&cur),
        Some(&next),
        Some(&running()),
        StageTemplate::Worship,
        None,
        &ctx(STAGE_TEXT_SCALE_DEFAULT),
        &StageTheme::dark(),
        W,
        H,
    )
}

/// The resolved line box of the live lyric band.
fn lyric_cell(frame: &Frame) -> u32 {
    autofit_cap(frame, "alpha")
}

/// The resolved line box of the NEXT line.
fn next_cell(frame: &Frame) -> u32 {
    run(frame, "coming zulu line").0
}

/// The design's FIXED lyric rect (Figma 373:133's 212 units) — the two-line case, kept here
/// as the baseline the elastic band is measured against.
fn fixed_band_h() -> u32 {
    ((212.0 / REF_H) * H as f64) as u32
}

/// The ELASTIC lyric band: from the bottom of the header chrome to the top of the reserved
/// NEXT row, less a safe gap at each end. Re-derived from the audit's chrome constants rather
/// than read out of `stage.rs`.
fn elastic_band() -> (i32, i32) {
    let v = |u: f64| ((u / REF_H) * H as f64) as i32;
    let cell_of = |em: f64| ((em / FONT_TO_LINE / REF_H) * H as f64) as i32;
    let gap = v(12.0);
    let top = (v(28.0) + v(41.0)).max(v(30.5) + cell_of(30.0)) + gap;
    let band_y = H as i32 - v(107.0);
    let bottom = band_y - gap - cell_of(30.0) - gap;
    (top, bottom)
}

/// The height a block of `n` lines occupies at `cell` — `compose`'s own arithmetic:
/// `(n-1)` advances plus one cell, where an advance is the cell scaled by the leading.
fn block_h(n: u32, cell: u32, lh: f64) -> u32 {
    let advance = ((cell as f64) * lh).round().max(cell as f64) as u32;
    (n - 1) * advance + cell
}

/// A short stanza used to leave most of its band empty, because the design size was a ceiling
/// the fit could only fall below; a long one shrank to nothing inside a band that occupied
/// only 37.7 % of the frame. The band is now elastic — it claims the space the chrome does
/// not need — and the text fills it in both directions.
#[test]
fn the_live_band_grows_to_fill_its_region() {
    let (top, bottom) = elastic_band();
    let band = (bottom - top) as u32;
    let fixed = fixed_band_h();
    let design_ceiling = cell(56.0, H, STAGE_TEXT_SCALE_DEFAULT);

    // Premises, so neither claim below can go quietly vacuous. The design's own rect must
    // leave real space between the live band and the chrome under it, or "elastic" and
    // "fixed" would be the same band. Pinned at COMPILE time against the audit's figures, so
    // editing one of them here breaks the build rather than turning the test green-and-empty.
    // (`assertions_on_constants` is exactly what this is; the lint is the point, not a smell.)
    #[allow(clippy::assertions_on_constants)]
    const _: () = assert!(
        design::Y_LYRIC + design::H_LYRIC < design::Y_NEXT_ROW,
        "the fixed lyric rect ends above the NEXT row"
    );
    #[allow(clippy::assertions_on_constants)]
    const _: () = assert!(
        design::Y_NEXT_ROW < design::Y_TIMER_BAND,
        "the NEXT row sits above the timer band"
    );
    assert!(
        band > fixed,
        "the elastic band is {band} px against the fixed {fixed} px — it did not expand"
    );
    assert!(
        block_h(2, design_ceiling, 1.21) < band,
        "two lines at the design size already fill the band — growth is undetectable here"
    );

    // 1. A SHORT stanza grows past the old design ceiling and fills the band.
    let two = worship_with(2);
    let c2 = lyric_cell(&two);
    assert!(
        c2 > design_ceiling,
        "a two-line stanza resolved to {c2} px, still under the old {design_ceiling} px \
         ceiling — the band is not growing to fill"
    );
    let filled = block_h(2, c2, 1.21);
    assert!(
        filled > band * 9 / 10 && filled <= band,
        "a two-line stanza fills {filled} px of a {band} px band"
    );

    // 2. The owner's case: an EIGHT-line stanza is materially larger than the fixed band
    //    would have allowed. The fixed-band result is computed from the same arithmetic, so
    //    this is a real comparison rather than a remembered number.
    let eight = worship_with(8);
    let c8 = lyric_cell(&eight);
    let c8_fixed = (1..=fixed)
        .rev()
        .find(|c| block_h(8, *c, 1.21) <= fixed)
        .expect("some cell fits eight lines in the fixed band");
    assert!(
        c8 >= c8_fixed * 13 / 10,
        "eight lines resolved to {c8} px; the fixed band gave {c8_fixed} px — the elastic \
         band bought less than the 30 % the geometry says it should"
    );
    assert!(
        block_h(8, c8, 1.21) <= band,
        "eight lines overflow the elastic band"
    );

    // 3. Positive control — growth did not replace shrinking, and WIDTH still binds. An
    //    unbreakable token cannot wrap, so the fit must shrink it below what the band's
    //    HEIGHT alone would allow; without a width bound this would resolve to the full band.
    let long_word = "A".repeat(40);
    let cur = Slide::new("Amazing Grace", [long_word.clone()]);
    let f = compose_stage(
        Some(&cur),
        None,
        Some(&running()),
        StageTemplate::Worship,
        None,
        &ctx(STAGE_TEXT_SCALE_DEFAULT),
        &StageTheme::dark(),
        W,
        H,
    );
    let one_line_height_bound = band;
    let cw = autofit_cap(&f, &long_word);
    assert!(
        cw < one_line_height_bound,
        "a 40-character unbreakable token resolved to {cw} px in a {band} px band — the fit \
         is not bounded by the region WIDTH, only its height"
    );

    // 4. …and every line of a long stanza is still visible (never truncated).
    let many = worship_with(16);
    let c16 = lyric_cell(&many);
    assert!(
        c16 < c2,
        "16 lines resolved to {c16} px against 2 lines' {c2} px"
    );
    for i in 0..16 {
        assert!(
            has_text(&many, &format!("alpha{i:02}")),
            "line {i} of 16 is missing — growing broke the never-truncate guarantee"
        );
    }
    assert!(block_h(16, c16, 1.21) <= band, "16 lines overflow the band");
}

/// Growth must never collide with the chrome the band grows between.
#[test]
fn a_grown_band_still_clears_the_clock_the_next_row_and_the_timer_band() {
    let (top, bottom) = elastic_band();
    let v = |u: f64| ((u / REF_H) * H as f64) as i32;
    let clock_bottom = v(30.5) + cell(30.0, H, STAGE_TEXT_SCALE_DEFAULT) as i32;
    let band_y = H as i32 - v(107.0);

    // Two lines is the largest the band ever grows to; check the extreme, not the average.
    let two = worship_with(2);
    let c = lyric_cell(&two) as i32;

    // Where the block actually lands: the region is VAlign::Middle, so it is centred.
    let used = block_h(2, c as u32, 1.21) as i32;
    let block_top = top + ((bottom - top) - used) / 2;
    assert!(
        block_top >= clock_bottom,
        "the grown lyric starts at {block_top} px, above the wall clock's {clock_bottom} px"
    );
    assert!(
        block_top + used <= bottom,
        "the grown lyric ends past the band bottom"
    );
    // The NEXT row and the timer band both sit below the band bottom, by construction.
    let next_top = band_y - v(12.0) - cell(30.0, H, STAGE_TEXT_SCALE_DEFAULT) as i32;
    assert!(bottom < next_top, "the band bottom overlaps the NEXT row");
    assert!(
        next_top + next_cell(&two) as i32 <= band_y,
        "the NEXT row overlaps the timer band"
    );
}

/// The **audience** output is owner-locked to its current fit behaviour. All of the growth
/// above is confidence-monitor only: it is expressed at the stage call sites (which hand
/// `autofit_layers` the region height as the ceiling) and adds no `Fit` variant, so every
/// audience caller is untouched. A short audience slide must therefore still sit at its
/// theme's design size rather than growing to fill.
#[test]
fn the_audience_output_still_shrinks_only() {
    use selahcue_present::{compose_slide, Theme};
    let theme = Theme::classic();
    let short = Slide::new("Isaiah 61:5", ["Short."]);
    let f = compose_slide(&short, &theme, W, H);
    let body_px = f
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Text { text, px, .. } if text.contains("Short") => Some(*px),
            _ => None,
        })
        .max()
        .expect("the audience slide renders its body");
    let design_cell = (theme.body.size_permille as u32 * H) / 1000;
    assert_eq!(
        body_px, design_cell,
        "a short audience slide resolved to {body_px} px instead of its theme's design size \
         {design_cell} px — the stage's grow behaviour has leaked into the audience path"
    );
}

/// The reported defect: with a fixed NEXT size against a shrinking lyric, a stanza of six
/// lines or more rendered the COMING line larger than the line being sung. NEXT is now a
/// ratio of the resolved lyric, so the hierarchy holds at every content length.
#[test]
fn the_next_line_never_outgrows_the_live_line() {
    // The old crossover, from the fixed 30px NEXT against `(212/n)/1.21` em: n = 6 was the
    // first inversion and n = 9 was the screenshot. Both are checked explicitly, and the
    // whole range around them is swept so a future constant cannot re-invert it quietly.
    for n in 1..=16u32 {
        let f = worship_with(n as usize);
        let (lyric, next) = (lyric_cell(&f), next_cell(&f));
        assert!(
            next < lyric,
            "{n}-line stanza: the NEXT line is {next} px against a {lyric} px lyric — the \
             coming line is bigger than the line being sung"
        );
    }
    // The two the owner actually hit, named so the failure message says which.
    for n in [6usize, 9] {
        let f = worship_with(n);
        let (lyric, next) = (lyric_cell(&f), next_cell(&f));
        assert!(
            (next as f64) < (lyric as f64) * 0.75,
            "{n} lines: NEXT {next} px is not clearly subordinate to the lyric's {lyric} px"
        );
    }
}

/// Subordinate does not mean arbitrary: the row keeps the design's own proportions
/// (Figma 373-148/373-147: a 30px NEXT line and a 16px chip against a 56px lyric), so at the
/// design's content length the rendered row is the design's row.
#[test]
fn the_next_row_keeps_the_designs_ratio_to_the_live_line() {
    let f = worship_with(4);
    let lyric = lyric_cell(&f);
    let next = next_cell(&f);
    let chip = run(&f, "NEXT").0;
    assert_eq!(
        next,
        ((lyric as f64) * 30.0 / 56.0) as u32,
        "the NEXT line is not the design's 30/56 of the resolved lyric ({lyric} px)"
    );
    assert_eq!(
        chip,
        ((next as f64) * 16.0 / 30.0) as u32,
        "the NEXT chip is not the design's 16/30 of the NEXT line ({next} px)"
    );
    // …and the row stays out of the timer band whatever the lyric does.
    let band_top = ((456.0 / REF_H) * H as f64) as u32;
    let row_top = ((377.5 / REF_H) * H as f64) as u32;
    let two = worship_with(2);
    assert!(
        row_top + next_cell(&two) <= band_top,
        "with a grown lyric the NEXT row runs into the timer band"
    );
    // Coupling only ever pulls NEXT DOWN. When the live band grows, NEXT stops at the size
    // the design gives it — inflating it would ellipsize the scripture row away and overflow
    // the worship one.
    assert_eq!(
        next_cell(&two),
        cell(30.0, H, STAGE_TEXT_SCALE_DEFAULT),
        "a grown lyric pushed the NEXT line past its design size"
    );
    assert!(
        lyric_cell(&two) > lyric_cell(&f),
        "the two-line lyric is not larger than the four-line one — the premise of the \
         ceiling check above does not hold"
    );
}

/// The same coupling on the scripture column — a long verse shrinks there too, and its NEXT
/// line was the same fixed constant.
#[test]
fn the_scripture_next_line_stays_subordinate_to_the_verse() {
    for n in [1usize, 4, 8, 14] {
        let body: Vec<String> = (0..n).map(|i| format!("alpha{i:02} beta")).collect();
        let cur = Slide::new("Isaiah 61:5", body);
        let next = Slide::new("Isaiah 61:6", ["coming zulu line"]);
        let f = compose_stage(
            Some(&cur),
            Some(&next),
            Some(&running()),
            StageTemplate::Scripture,
            None,
            &ctx(STAGE_TEXT_SCALE_DEFAULT),
            &StageTheme::dark(),
            W,
            H,
        );
        let verse = autofit_cap(&f, "alpha");
        let nxt = f
            .layers
            .iter()
            .find_map(|l| match l {
                // The scripture NEXT line is ellipsized to keep the countdown panel clear,
                // so match its stable prefix rather than the whole authored string.
                Layer::Text { text, px, .. } if text.starts_with("Isaiah 61:6") => Some(*px),
                _ => None,
            })
            .expect("the scripture NEXT line renders");
        assert!(
            nxt < verse,
            "{n}-line verse: NEXT {nxt} px against a {verse} px verse"
        );
    }
}

/// The coupling CEILING — `subordinate_cell`'s `.min(design_cell)` — guarded where it is
/// actually load-bearing.
///
/// It is not load-bearing on Worship: there the reserved row height happens to equal the
/// design cell, so `row_h` clamps to the same value and removing the ceiling changes nothing.
/// Scripture's row is taller, so the ceiling is the only thing holding its NEXT line at the
/// design size — and without it the line inflates until `ellipsize` cuts it down to `...`,
/// which is the truncation bug the ceiling exists to prevent.
#[test]
fn the_next_coupling_ceiling_holds_where_it_is_load_bearing() {
    let s = STAGE_TEXT_SCALE_DEFAULT;
    // A ONE-line verse: maximum growth of the live band, so the uncapped ratio is at its
    // largest and the ceiling is doing the most work.
    let cur = Slide::new("Isaiah 61:5", ["alpha00 beta"]);
    let next = Slide::new("Isaiah 61:6", ["coming zulu line"]);
    let f = compose_stage(
        Some(&cur),
        Some(&next),
        Some(&running()),
        StageTemplate::Scripture,
        None,
        &ctx(s),
        &StageTheme::dark(),
        W,
        H,
    );
    let verse = autofit_cap(&f, "alpha");
    let design_next = cell(26.0, H, s);

    // Premise: the uncapped ratio must actually EXCEED the design cell here, or the ceiling
    // is being asserted in a case where it never applies and the test proves nothing.
    let uncapped = ((verse as f64) * 26.0 / 48.0) as u32;
    assert!(
        uncapped > design_next,
        "with a {verse} px verse the uncapped ratio gives {uncapped} px, already within the \
         {design_next} px design size — this case does not exercise the ceiling"
    );

    let nxt = f
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text { text, px, .. } if text.starts_with("Isaiah 61:6") => Some(*px),
            _ => None,
        })
        .unwrap_or_else(|| {
            panic!(
                "the scripture NEXT line carries none of its reference — an inflated line \
                 was ellipsized away. Runs present: {:?}",
                texts(&f)
            )
        });
    assert_eq!(
        nxt, design_next,
        "the scripture NEXT line is {nxt} px against a {design_next} px design size — the \
         coupling ceiling let a grown verse push it up"
    );
}

// --- Worship NEXT-line overflow -----------------------------------------------------------

/// Compose the worship template with `next_line` as the coming line, and return the rendered
/// `(text, right edge)` of the run that carries it. The token `zulu` appears nowhere else on
/// the frame, so this cannot accidentally match chrome or the lyric.
fn worship_next_frame(next_line: &str) -> Frame {
    let cur = Slide::new("Amazing Grace", ["Amazing grace"]);
    let next = Slide::new("Next Item", [next_line]);
    compose_stage(
        Some(&cur),
        Some(&next),
        Some(&running()),
        StageTemplate::Worship,
        None,
        &ctx(STAGE_TEXT_SCALE_DEFAULT),
        &StageTheme::dark(),
        W,
        H,
    )
}

fn worship_next_run(next_line: &str) -> (String, i32) {
    let f = worship_next_frame(next_line);
    f.layers
        .iter()
        .find_map(|l| match l {
            Layer::Text { text, rect, .. } if text.contains("zulu") => {
                Some((text.clone(), rect.x + rect.w as i32))
            }
            _ => None,
        })
        .unwrap_or_else(|| {
            panic!(
                "no worship NEXT run carries the authored text — it was truncated away \
                 entirely. Runs present: {:?}",
                texts(&f)
            )
        })
}

/// The worship NEXT line ran off the right edge of the frame and was cut mid-word with no
/// indication anything was missing: the row is centred by `w.saturating_sub(group_w)`, which
/// saturates to 0 once the group is wider than the frame, so the line's rect reached
/// `right = 4854` on a 1920-wide output. Scripture already ellipsized; worship did not.
///
/// Both directions are asserted. A fix that ellipsized *everything* would satisfy "does it
/// ellipsize" while quietly truncating lines that fit perfectly well.
#[test]
fn a_long_worship_next_line_is_ellipsized_and_a_short_one_is_left_alone() {
    // Short: well inside the row. Must render VERBATIM.
    let short = "zulu alpha";
    let sf = worship_next_frame(short);
    assert!(
        texts(&sf).iter().any(|t| t == short),
        "a short next line was altered — it must render verbatim, never gain an ellipsis. \
         Runs present: {:?}",
        texts(&sf)
    );
    let (shown, right) = worship_next_run(short);
    assert!(
        !shown.ends_with("..."),
        "a short next line gained an ellipsis"
    );
    assert!(right <= W as i32, "even the short line overflows the frame");

    // Long: far past the row. Must be cut WITH the ellipsis, and must stay in the frame.
    let long = "zulu ".repeat(40);
    let long = long.trim();
    let (shown, right) = worship_next_run(long);
    assert!(
        shown.ends_with("..."),
        "a next line long enough to overflow was not ellipsized: {shown:?}"
    );
    assert!(
        shown.len() < long.len(),
        "the ellipsized line is not shorter than what was authored"
    );
    assert!(
        right <= W as i32,
        "the ellipsized next line still reaches {right} px on a {W} px frame — it is cut at \
         the frame edge, which is the defect this closes"
    );

    // The invariant across the whole boundary, so neither direction is a lucky sample:
    // the run never leaves the frame, and it carries an ellipsis EXACTLY when it was cut.
    let mut saw_verbatim = false;
    let mut saw_ellipsis = false;
    for words in 1..=40usize {
        let authored = vec!["zulu"; words].join(" ");
        let (shown, right) = worship_next_run(&authored);
        assert!(
            right <= W as i32,
            "{words}-word next line reaches {right} px on a {W} px frame"
        );
        assert_eq!(
            shown.ends_with("..."),
            shown != authored,
            "{words}-word next line: the ellipsis and the truncation disagree ({shown:?})"
        );
        saw_verbatim |= shown == authored;
        saw_ellipsis |= shown != authored;
    }
    // Premise: the sweep must actually cross the boundary, or it proves only one direction.
    assert!(
        saw_verbatim && saw_ellipsis,
        "the 1..=40-word sweep never crossed the boundary (verbatim seen: {saw_verbatim}, \
         ellipsized seen: {saw_ellipsis})"
    );
}

// --- STG-011: letter-spacing --------------------------------------------------------------

/// Every stage line hard-coded `letter_spacing_px: 0`; Design 2.0 tracks nine runs. The
/// values are in Figma px at the 563-tall reference, so they scale with the frame.
#[test]
fn tracked_runs_carry_the_designed_letter_spacing() {
    let s = STAGE_TEXT_SCALE_DEFAULT;
    let track = |figma_px: f64| -> i32 { ((figma_px / REF_H) * H as f64).round() as i32 };
    // The premise: at this frame height the design's smallest tracking value must still
    // round to something non-zero, or "tracked" and "untracked" are indistinguishable.
    assert!(
        track(1.0) > 0,
        "1px of tracking rounds to 0 at {H}px tall — this test cannot tell the two apart"
    );

    let ws = compose(StageTemplate::Worship, false, s, None, W, H);
    assert_eq!(run(&ws, "NEXT").1, track(1.0), "worship NEXT label +1");
    assert_eq!(
        run(&ws, "SERVICE TIMER").1,
        track(1.0),
        "worship SERVICE TIMER +1"
    );

    let sc = compose(StageTemplate::Scripture, false, s, None, W, H);
    assert_eq!(
        run(&sc, "STAGE · SCRIPTURE").1,
        track(2.0),
        "STAGE · SCRIPTURE +2"
    );
    assert_eq!(
        run(&sc, "AMAZING GRACE").1,
        track(1.0),
        "scripture reference +1"
    );
    assert_eq!(run(&sc, "TIME LEFT").1, track(1.0), "TIME LEFT +1");
    assert_eq!(run(&sc, "12:45").1, track(-2.0), "scripture readout −2");

    let to = compose_timer_only(false, s);
    assert_eq!(
        run(&to, "SERVICE TIMER").1,
        track(2.0),
        "timer-only header +2"
    );
    assert_eq!(run(&to, "SERMON").1, track(4.0), "timer-only segment +4");
    assert_eq!(
        run(&to, "12:45").1,
        track(-4.0),
        "timer-only giant readout −4"
    );

    let tou = compose_timer_only(true, s);
    assert_eq!(run(&tou, "TIME UP").1, track(2.0), "timer-up TIME UP +2");
    assert_eq!(run(&tou, "SERMON").1, track(1.5), "timer-up header +1.5");

    let msg = compose(
        StageTemplate::Worship,
        false,
        s,
        Some("WRAP UP · 2 MIN LEFT"),
        W,
        H,
    );
    assert_eq!(
        run(&msg, "MESSAGE FROM PRODUCTION").1,
        track(1.5),
        "message chip +1.5"
    );

    // Negative control: the runs the design does NOT track must stay at 0, or "tracking is
    // applied" would be indistinguishable from "tracking is applied everywhere".
    assert_eq!(
        run(&ws, "Amazing Grace").1,
        0,
        "the song title is untracked"
    );
    assert_eq!(run(&ws, "10:42 AM").1, 0, "the wall clock is untracked");
    assert_eq!(run(&ws, "12:45").1, 0, "the worship readout is untracked");
}

// --- STG-012: font weight ------------------------------------------------------------------

/// The `weight` (`TextStyle::weight`) of the chrome run whose text is exactly `needle`.
fn weight_of(frame: &Frame, needle: &str) -> u16 {
    frame
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text { text, style, .. } if text == needle => {
                style.map(|s| s.weight).or(Some(400))
            }
            _ => None,
        })
        .unwrap_or_else(|| {
            panic!(
                "no stage run reads {needle:?}. Runs present: {:?}",
                texts(frame)
            )
        })
}

/// As [`weight_of`], matching on a prefix (a run the composer may ellipsize or compose from
/// several joined fields — the NEXT lines, the timer-only footer).
fn weight_of_prefix(frame: &Frame, prefix: &str) -> u16 {
    frame
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text { text, style, .. } if text.starts_with(prefix) => {
                style.map(|s| s.weight).or(Some(400))
            }
            _ => None,
        })
        .unwrap_or_else(|| {
            panic!(
                "no stage run starts with {prefix:?}. Runs present: {:?}",
                texts(frame)
            )
        })
}

/// The composer hard-coded every chrome run at weight 700 (Bold), where Design 2.0 draws
/// three weights: Bold for labels/readouts, Semi Bold (600) for the wall clock, Medium (500)
/// for the stanza position, both NEXT lines and the timer-only footer. Closes STG-012 — but
/// only as far as this crate can safely go: `Family::Name("Inter")` has a bundled face at
/// exactly 400 and 700 (`selahcue-engine`'s `INTER_BYTES`/`INTER_BOLD_BYTES`), and requesting
/// any other weight from that family does not fall back to the nearest bundled face — it
/// falls OUT of the family onto whatever the host has installed. See
/// `only_the_two_bundled_inter_weights_are_requested_by_the_stage_composer` below for the
/// measurement that found this and now guards it. So Semi Bold and Medium both render as
/// **Regular (400)** here, not their nominal Figma weights — the achievable, SAFE slice of
/// the design's hierarchy with the font this crate actually ships, not "500 and 600 done".
#[test]
fn chrome_runs_carry_the_designed_font_weight() {
    let s = STAGE_TEXT_SCALE_DEFAULT;

    // Worship: the wall clock, stanza position and NEXT line are all Regular (400) — the
    // safe stand-in for Semi Bold/Medium (see the test doc comment); the song title and the
    // timer caption stay Bold (700).
    let ws = compose(StageTemplate::Worship, false, s, None, W, H);
    assert_eq!(
        weight_of(&ws, "10:42 AM"),
        400,
        "worship wall clock: Regular"
    );
    assert_eq!(
        weight_of(&ws, "Verse 2 of 4"),
        400,
        "worship stanza position: Regular"
    );
    assert_eq!(
        weight_of_prefix(&ws, "I once was lost"),
        400,
        "worship NEXT line: Regular"
    );
    assert_eq!(
        weight_of(&ws, "Amazing Grace"),
        700,
        "song title stays Bold"
    );
    assert_eq!(
        weight_of(&ws, "SERVICE TIMER"),
        700,
        "SERVICE TIMER caption stays Bold"
    );

    // Scripture: same wall-clock/next-line roles, plus a Bold control (the reference).
    let sc = compose(StageTemplate::Scripture, false, s, None, W, H);
    assert_eq!(
        weight_of(&sc, "10:42 AM"),
        400,
        "scripture wall clock: Regular"
    );
    assert_eq!(
        weight_of_prefix(&sc, "Isaiah 61:6"),
        400,
        "scripture NEXT line: Regular"
    );
    assert_eq!(
        weight_of(&sc, "AMAZING GRACE"),
        700,
        "scripture reference stays Bold"
    );

    // Timer-only: its header clock is a SEPARATE code path from `header_clock` (STG-055) and
    // must carry the same Regular weight; its footer (date + time, joined) is Regular too.
    let tou = compose_timer_only(false, s);
    assert_eq!(
        weight_of(&tou, "10:42 AM"),
        400,
        "timer-only header clock: Regular"
    );
    assert_eq!(
        weight_of_prefix(&tou, "Sunday"),
        400,
        "timer-only footer: Regular"
    );
    assert_eq!(
        weight_of(&tou, "SERVICE TIMER"),
        700,
        "timer-only header label stays Bold"
    );
}

/// The REAL regression guard for the finding above — composes every template/state/scale/
/// message combination through the actual `compose_stage` API and asserts every `Layer::Text`
/// the composer emits carries one of the two weights genuinely safe to request from the
/// bundled `Inter` family (see the `design` module's font-weight doc comment). This is a
/// property of THIS CRATE'S CODE (which `u16` constant each `line()` call site passes), not of
/// the host's installed fonts, so — unlike
/// [`unbundled_inter_weights_still_escape_to_host_faces`] below — it is safe to run
/// unconditionally in CI on every OS.
///
/// An earlier cut of this batch had a test with this same NAME that instead measured
/// `measure_line_width` in isolation — it could tell "500/600 are unsafe in general" but could
/// not tell "the composer still only ever asks for 400/700", so a stray `line(..., 600)` call
/// anywhere in `stage.rs` would have sailed through it. Caught in review (Vera, mutation-proved
/// by setting the scripture `"TIME LEFT"` caption — a run no other test names — to 600 and
/// showing the whole suite stayed green). This version composes real frames and enumerates
/// every text run's weight, so that specific mutation (or any call site passing a literal
/// weight outside `{400, 700}`) fails here directly.
#[test]
fn the_stage_composer_emits_only_bundled_inter_weights() {
    use std::collections::BTreeSet;

    let mut seen: BTreeSet<u16> = BTreeSet::new();
    let mut frames_checked = 0usize;
    for template in [
        StageTemplate::Worship,
        StageTemplate::Scripture,
        StageTemplate::TimerOnly,
    ] {
        for up in [false, true] {
            for scale in [
                STAGE_TEXT_SCALE_MIN,
                STAGE_TEXT_SCALE_DEFAULT,
                STAGE_TEXT_SCALE_MAX,
            ] {
                for msg in [None, Some("WRAP UP · 2 MIN LEFT")] {
                    let frame = if template == StageTemplate::TimerOnly {
                        // The timer-only composer has its own helper (a non-song slide) and
                        // takes no `message` — the overlay is template-agnostic, already
                        // covered by the worship/scripture branches.
                        compose_timer_only(up, scale)
                    } else {
                        compose(template, up, scale, msg, W, H)
                    };
                    for layer in &frame.layers {
                        if let Layer::Text { style, .. } = layer {
                            seen.insert(style.map(|s| s.weight).unwrap_or(400));
                        }
                    }
                    frames_checked += 1;
                }
            }
        }
    }

    // Vacuity guard: a bug that made the composer draw NO text at all (e.g. every branch
    // returning early) would leave `seen` empty and the assertion below would pass for the
    // wrong reason — nothing was checked, not "everything checked was fine".
    assert!(
        frames_checked >= 30,
        "only checked {frames_checked} frames — the sweep above is smaller than intended"
    );
    assert!(
        !seen.is_empty(),
        "no stage frame across {frames_checked} compositions drew any text at all — the \
         weight assertion below would be vacuous"
    );

    assert_eq!(
        seen.into_iter().collect::<Vec<_>>(),
        vec![400, 700],
        "the stage composer emitted a text weight outside the two bundled Inter faces \
         (400/700) — anything else silently escapes onto a host-installed font (see \
         `design::WEIGHT_BOLD`/`WEIGHT_REGULAR`'s doc comment)"
    );
}

/// Evidence, not a CI gate — **`#[ignore]`d on purpose**. `Family::Name("Inter")` is bundled at
/// exactly weight 400 and 700; measured directly against the SAME public API `draw_text` uses
/// (`selahcue_engine::raster::measure_line_width`, swept 400/500/600/700 at fixed text+px on
/// the machine this was authored on), 500 and 600 each measured a DIFFERENT width from 400,
/// from 700, and from each other — i.e. each escaped the family onto its own distinct,
/// host-installed face (confirmed independently from source too — cosmic-text 0.12.1's
/// `Attrs::matches` filters by style/stretch only, ignoring family; family is applied later at
/// an exact-weight-diff filter, and when nothing matches that filter the family constraint is
/// dropped entirely and shaping falls through to whatever host face is left).
///
/// This is exactly why it is `#[ignore]`d rather than run by default: the specific widths (and
/// therefore which assertions fire) are a property of what's installed on the machine running
/// the test, not of this crate's code — the "safe" pair `{400, 700}` is asserted with zero host
/// dependency by [`the_stage_composer_emits_only_bundled_inter_weights`] above instead. This
/// crate has shipped exactly this class of "green on the author's OS, red on a sparser CI
/// runner" test before (`test_measure.rs`'s `installed_serif`, ticket 86ak643rc) and the
/// standing guidance since is not to gate CI on a host font assumption. Re-run by hand
/// (`cargo test -p selahcue-present -- --ignored unbundled_inter_weights`) when deciding
/// whether it is safe to bundle a real Inter Medium/Semi Bold face and retire the `WEIGHT_BOLD`
/// / `WEIGHT_REGULAR` two-value compromise — a widening of these gaps on that machine is the
/// signal that 500/600 (or whatever the new faces' real weights are) have become safe.
#[test]
#[ignore = "asserts a property of the HOST's installed fonts, not of this crate's code — see \
            doc comment; run manually, not as a CI gate (86ak643rc precedent)"]
fn unbundled_inter_weights_still_escape_to_host_faces() {
    use selahcue_engine::raster::measure_line_width;

    let font = selahcue_engine::scene::FontName::new("Inter").unwrap();
    let text = "SERVICE TIMER 10:42 AM Verse 2 of 4";
    let px = 100;

    let w400 = measure_line_width(text, px, Some(&font), 400);
    let w500 = measure_line_width(text, px, Some(&font), 500);
    let w600 = measure_line_width(text, px, Some(&font), 600);
    let w700 = measure_line_width(text, px, Some(&font), 700);

    // Premise: the two bundled faces really do measure differently from each other, or this
    // test would be unable to tell "escaped the family" from "landed on the bundled face".
    assert_ne!(
        w400, w700,
        "the bundled Regular and Bold Inter faces measure identically on this host"
    );

    assert_ne!(
        w500, w400,
        "on THIS host, weight 500 now measures the same as bundled Inter Regular (400) — if \
         a real Inter Medium face was bundled, `design::WEIGHT_REGULAR` could be replaced \
         with a proper Medium constant for the stanza/NEXT/footer roles"
    );
    assert_ne!(
        w600, w700,
        "on THIS host, weight 600 now measures the same as bundled Inter Bold (700) — if a \
         real Inter Semi Bold face was bundled, `design::WEIGHT_REGULAR` could be replaced \
         with a proper Semi Bold constant for the wall-clock roles"
    );
}

/// The `measure` memo's key is `{text, cell, font, weight}` — no tracking. `autofit_layers`
/// budgets the wrap for tracking on top of that memoised width, so a tracked auto-fit region
/// is safe *today*; Design 2.0 tracks none of the three regions anyway. This pins the second
/// fact, which is the one that costs nothing to keep true.
#[test]
fn no_auto_fit_region_carries_tracking() {
    let s = STAGE_TEXT_SCALE_DEFAULT;
    for (name, frame, needle) in [
        (
            "worship lyric",
            compose(StageTemplate::Worship, false, s, None, W, H),
            "grace",
        ),
        (
            "scripture verse",
            compose(StageTemplate::Scripture, false, s, None, W, H),
            "grace",
        ),
        (
            "message body",
            compose(
                StageTemplate::Worship,
                false,
                s,
                Some("WRAP UP · 2 MIN LEFT"),
                W,
                H,
            ),
            "WRAP UP",
        ),
    ] {
        let tracked: Vec<i32> = frame
            .layers
            .iter()
            .filter_map(|l| match l {
                Layer::Text { text, style, .. } if text.contains(needle) => {
                    Some(style.map(|s| s.letter_spacing_px).unwrap_or(0))
                }
                _ => None,
            })
            .collect();
        assert!(!tracked.is_empty(), "{name}: the region rendered nothing");
        assert!(
            tracked.iter().all(|&t| t == 0),
            "{name} carries tracking {tracked:?} — an auto-fit region must not, unless the \
             measure memo key is extended first"
        );
    }
}

// --- STG-008/009/010: shapes -------------------------------------------------------------

/// The dots are circles and the pills are pills — the composer drew squares with no radius
/// and no border anywhere. Closes STG-008, STG-009, STG-010, STG-018, STG-027, STG-048.
#[test]
fn status_dots_are_circles_and_pills_are_rounded() {
    let ws = compose(
        StageTemplate::Worship,
        false,
        STAGE_TEXT_SCALE_DEFAULT,
        None,
        W,
        H,
    );
    let sh = shapes(&ws);
    assert!(!sh.is_empty(), "the worship template drew no shapes at all");

    // Every dot: an ellipse inscribed in a SQUARE (a circle), not an ellipse.
    let circles: Vec<_> = sh
        .iter()
        .filter(|(k, ..)| *k == ShapeKind::Ellipse)
        .collect();
    assert_eq!(
        circles.len(),
        2,
        "worship draws exactly two dots (song + timer state); found {}",
        circles.len()
    );
    for (_, w, h, ..) in &circles {
        assert_eq!(w, h, "a status dot is {w}×{h} — not a circle");
    }

    // The song pill is fully rounded and carries the hairline border.
    let theme = StageTheme::dark();
    let pills: Vec<_> = sh
        .iter()
        .filter(|(k, w, h, b, c, ..)| {
            *k == ShapeKind::RoundedRect && *c == h / 2 && *b > 0 && w > h
        })
        .collect();
    assert!(
        pills
            .iter()
            .any(|(.., fill, border)| *fill == theme.track && *border == theme.border),
        "no fully-rounded, hairline-bordered song pill (STG-017/STG-008/STG-009)"
    );

    // The timer band is a bordered surface (square corners, per the design).
    assert!(
        sh.iter()
            .any(|(k, w, _, b, c, fill, border)| *k == ShapeKind::RoundedRect
                && *w == W
                && *c == 0
                && *b > 0
                && *fill == theme.panel
                && *border == theme.border),
        "the worship timer band has no hairline border (STG-026/STG-008)"
    );

    // Scripture's status pill takes the Design 2.0 chip pattern: soft tint + own border.
    let sc = compose(
        StageTemplate::Scripture,
        false,
        STAGE_TEXT_SCALE_DEFAULT,
        None,
        W,
        H,
    );
    assert!(
        shapes(&sc)
            .iter()
            .any(|(k, w, h, b, c, fill, border)| *k == ShapeKind::RoundedRect
                && *c == h / 2
                && w > h
                && *b > 0
                && *fill == theme.ok_soft
                && *border == theme.ok_border),
        "the ON TIME pill is not the preview-soft chip the design draws (STG-047)"
    );

    // The `▲` on the timer-only overrun pill is a shape, not a glyph the font lacks.
    let tou = compose_timer_only(true, STAGE_TEXT_SCALE_DEFAULT);
    assert!(
        shapes(&tou).iter().any(|(k, ..)| *k == ShapeKind::Triangle),
        "the timer-only overrun pill has no ▲ marker (STG-065)"
    );
    assert!(
        !has_text(&tou, "▲"),
        "the ▲ is being drawn as a glyph — the bundled Latin face has no such glyph"
    );
}

// --- STG-038 / STG-065: the overrun readout ----------------------------------------------

/// The speaker could not tell five seconds over from five minutes over: both TIME-UP frames
/// carry an overrun readout and the implementation showed only the words "TIME UP".
#[test]
fn time_up_shows_how_far_over_the_timer_has_run() {
    let s = STAGE_TEXT_SCALE_DEFAULT;
    let cur = slide("Amazing Grace", &["Amazing grace"]);
    let compose_with = |template, overrun| {
        compose_stage(
            Some(&cur),
            None,
            Some(&timed_up_by(overrun)),
            template,
            None,
            &ctx(s),
            &StageTheme::dark(),
            W,
            H,
        )
    };

    // Five seconds over and five minutes over must not render the same screen — the exact
    // failure the audit names.
    for (name, template, prefix) in [
        ("worship", StageTemplate::Worship, "OVER"),
        ("scripture", StageTemplate::Scripture, "OVER"),
        ("timer-only", StageTemplate::TimerOnly, "OVER BY"),
    ] {
        let five_secs = compose_with(template, 5);
        let five_mins = compose_with(template, 300);
        assert!(
            has_text(&five_secs, &format!("{prefix} 0:05")),
            "{name}: 5 seconds over does not read `{prefix} 0:05` — runs: {:?}",
            texts(&five_secs)
        );
        assert!(
            has_text(&five_mins, &format!("{prefix} 5:00")),
            "{name}: 5 minutes over does not read `{prefix} 5:00` — runs: {:?}",
            texts(&five_mins)
        );
        assert_ne!(
            texts(&five_secs),
            texts(&five_mins),
            "{name}: 0:05 over and 5:00 over render identically"
        );
        // …and it is an overrun readout, not a relabelled countdown: it appears only at
        // TIME UP. A readout that showed `OVER 0:00` while running would be worse than none.
        let ok = compose_stage(
            Some(&cur),
            None,
            Some(&running()),
            template,
            None,
            &ctx(s),
            &StageTheme::dark(),
            W,
            H,
        );
        assert!(
            !has_text(&ok, prefix),
            "{name}: the overrun readout is showing while the timer is still running"
        );
    }
}

/// The overrun rides on the `TimerView` the monitor is handed every tick, so a caller that
/// updates the timer cannot fail to update the overrun with it. `TimerView::from_timer`
/// fills it from the core `Timer`, which is what makes the readout advance in the app.
#[test]
fn the_overrun_travels_on_the_timer_snapshot_the_monitor_is_handed() {
    use selahcue_core::timer::Timer;
    use std::time::{Duration, Instant};

    let start = Instant::now();
    let mut timer = Timer::count_down(Duration::from_secs(10));
    timer.start(start);
    let total = Some(Duration::from_secs(10));

    let before = TimerView::from_timer(&timer, start + Duration::from_secs(4), total, 30);
    assert!(!before.time_up);
    assert_eq!(before.overrun_secs, 0, "a running countdown is not over");

    for over in [1u64, 5, 90] {
        let v = TimerView::from_timer(&timer, start + Duration::from_secs(10 + over), total, 30);
        assert!(v.time_up);
        assert_eq!(
            v.overrun_secs, over as u32,
            "from_timer did not carry the {over}s overrun off the core Timer"
        );
    }

    // …and it reaches the rendered monitor through the ordinary update call.
    let mut sd = StageDisplay::new(W, H, StageTheme::dark());
    sd.set_template(StageTemplate::TimerOnly);
    let cur = slide("Sermon", &[]);
    sd.update(Some(&cur), None, Some(&timed_up_by(5)));
    let at_5 = sd.output().clone();
    sd.update(Some(&cur), None, Some(&timed_up_by(300)));
    assert_ne!(&at_5, sd.output(), "0:05 over and 5:00 over render alike");
}

// --- STG-062: the TIME-UP vignette --------------------------------------------------------

/// Design 2.0 replaces the legacy solid-inverted TIME UP (white on flat `#C7212B`) with an
/// elliptical vignette in red ink. The engine has no radial-gradient layer, so this is
/// approximated with concentric ellipses — which must still ramp, and must stay bounded.
#[test]
fn timer_only_time_up_paints_a_bounded_radial_vignette() {
    let theme = StageTheme::dark();
    let tou = compose_timer_only(true, STAGE_TEXT_SCALE_DEFAULT);
    // The timer-only template draws no status dots, so every ellipse on this frame is a
    // vignette band. Taking them all is what lets the innermost band — the core stop — be
    // checked; a width filter would quietly drop it.
    let bands: Vec<_> = shapes(&tou)
        .into_iter()
        .filter(|(k, ..)| *k == ShapeKind::Ellipse)
        .collect();
    assert!(
        bands.len() >= 3,
        "the vignette collapsed to {} band(s) — it is a flat fill wearing a ramp's name",
        bands.len()
    );
    // Bounded: the approximation must not grow a layer per pixel row.
    assert!(
        bands.len() <= 32,
        "{} vignette bands — the approximation is unbounded in layer count",
        bands.len()
    );
    // It ramps: the innermost band is the dark-red core, the outermost the stage edge.
    let widest = bands.iter().map(|(_, w, ..)| *w).max().unwrap();
    let narrowest = bands.iter().map(|(_, w, ..)| *w).min().unwrap();
    assert!(narrowest < widest, "every band is the same size");
    let core = bands.iter().find(|(_, w, ..)| *w == narrowest).unwrap().5;
    let edge = bands.iter().find(|(_, w, ..)| *w == widest).unwrap().5;
    assert!(
        core.r > edge.r,
        "the vignette centre {core:?} is not redder than its rim {edge:?}"
    );
    assert_eq!(
        core, theme.alert_vignette_core,
        "the innermost band is not the design's core stop"
    );

    // The ink on it is the alert red — Design 2.0 is red-on-dark, the inverse of the legacy
    // solid-inverted treatment (white on `#C7212B`), so a white TIME UP word here would mean
    // the polarity was never switched.
    let word_ink = tou
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text { text, color, .. } if text == "TIME UP" => Some(*color),
            _ => None,
        })
        .expect("the timer-only TIME UP word renders");
    assert!(
        word_ink.r > word_ink.g && word_ink.r > word_ink.b,
        "the TIME UP word is {word_ink:?} — not a red ink, so the vignette polarity is wrong"
    );
    assert_ne!(
        word_ink,
        Rgba::WHITE,
        "TIME UP is still the legacy white-on-red"
    );
    let running_frame = compose_timer_only(false, STAGE_TEXT_SCALE_DEFAULT);
    assert!(
        shapes(&running_frame)
            .iter()
            .all(|(k, ..)| *k != ShapeKind::Ellipse),
        "the vignette is painted while the timer is still running"
    );
}

// --- STG-077: configurable stage text size (NFR-020) --------------------------------------

/// NFR-020 asks for a configurable large stage size. Every size was a hard-coded fraction of
/// the frame with no scale input; this is the seam.
#[test]
fn the_stage_text_scale_multiplies_every_type_size() {
    let needle = "SERVICE TIMER";
    let base = run(
        &compose(
            StageTemplate::Worship,
            false,
            STAGE_TEXT_SCALE_DEFAULT,
            None,
            W,
            H,
        ),
        needle,
    )
    .0;
    let big = run(
        &compose(
            StageTemplate::Worship,
            false,
            STAGE_TEXT_SCALE_MAX,
            None,
            W,
            H,
        ),
        needle,
    )
    .0;
    let small = run(
        &compose(
            StageTemplate::Worship,
            false,
            STAGE_TEXT_SCALE_MIN,
            None,
            W,
            H,
        ),
        needle,
    )
    .0;
    assert_eq!(base, cell(20.0, H, STAGE_TEXT_SCALE_DEFAULT));
    assert_eq!(big, cell(20.0, H, STAGE_TEXT_SCALE_MAX));
    assert_eq!(small, cell(20.0, H, STAGE_TEXT_SCALE_MIN));
    assert!(
        small < base && base < big,
        "the scale does not move the type: {small} / {base} / {big}"
    );
    // Tracking scales with the type it belongs to, or a 175 % run reads visibly tighter.
    let t_base = run(
        &compose(
            StageTemplate::Worship,
            false,
            STAGE_TEXT_SCALE_DEFAULT,
            None,
            W,
            H,
        ),
        needle,
    )
    .1;
    let t_big = run(
        &compose(
            StageTemplate::Worship,
            false,
            STAGE_TEXT_SCALE_MAX,
            None,
            W,
            H,
        ),
        needle,
    )
    .1;
    assert!(
        t_big > t_base,
        "tracking stayed at {t_base} px while the type grew — the run tightens as it scales"
    );
}

/// An out-of-range scale is clamped, never obeyed: a stage monitor must not be renderable
/// at zero-height text, and the composer must not divide by a zero cell.
#[test]
fn an_out_of_range_text_scale_is_clamped_not_obeyed() {
    let mut sd = StageDisplay::new(W, H, StageTheme::dark());
    assert_eq!(sd.text_scale(), STAGE_TEXT_SCALE_DEFAULT);
    sd.set_text_scale(0);
    assert_eq!(
        sd.text_scale(),
        STAGE_TEXT_SCALE_MIN,
        "0 was not clamped up"
    );
    sd.set_text_scale(u16::MAX);
    assert_eq!(
        sd.text_scale(),
        STAGE_TEXT_SCALE_MAX,
        "u16::MAX was not clamped down"
    );
    // Even a caller writing straight into the public field cannot get past the clamp.
    let hostile = StageContext {
        text_scale_permille: 0,
        ..StageContext::default()
    };
    assert_eq!(hostile.clamped_text_scale(), STAGE_TEXT_SCALE_MIN);
    let frame = compose_stage(
        Some(&slide("Amazing Grace", &["Amazing grace"])),
        None,
        Some(&running()),
        StageTemplate::Worship,
        None,
        &hostile,
        &StageTheme::dark(),
        W,
        H,
    );
    assert_eq!(
        run(&frame, "SERVICE TIMER").0,
        cell(20.0, H, STAGE_TEXT_SCALE_MIN),
        "a 0 scale written straight into the public field did not render at the minimum"
    );
    // Positive control: the benign case is still scaled, so "clamped" is not the same as
    // "the scale is ignored".
    let benign = StageContext {
        text_scale_permille: STAGE_TEXT_SCALE_MAX,
        ..StageContext::default()
    };
    let scaled = compose_stage(
        Some(&slide("Amazing Grace", &["Amazing grace"])),
        None,
        Some(&running()),
        StageTemplate::Worship,
        None,
        &benign,
        &StageTheme::dark(),
        W,
        H,
    );
    assert_eq!(
        run(&scaled, "SERVICE TIMER").0,
        cell(20.0, H, STAGE_TEXT_SCALE_MAX)
    );
}

/// NFR-020's bar is a **≥48px-equivalent** stage size. This records exactly which roles
/// clear it at the maximum scale on a 1920×1080 stage output — and which one does not, so
/// the gap is a documented number rather than a discovery in the field.
#[test]
fn the_maximum_text_scale_lifts_every_word_carrying_role_past_48px_equivalent() {
    const BAR: f64 = 48.0;
    let s = STAGE_TEXT_SCALE_MAX;
    let ws = compose(StageTemplate::Worship, false, s, None, W, H);
    let sc = compose(StageTemplate::Scripture, false, s, None, W, H);
    let to = compose_timer_only(false, s);

    let mut below: Vec<(&str, f64)> = Vec::new();
    for (role, frame, needle) in [
        ("worship song title", &ws, "Amazing Grace"),
        ("worship stanza", &ws, "Verse 2 of 4"),
        ("worship clock", &ws, "10:42 AM"),
        ("worship NEXT chip", &ws, "NEXT"),
        // (both coupled to the resolved lyric size — included so a coupling that
        // collapsed them to nothing still shows up here; the next line is matched on a
        // prefix because at this scale it is legitimately ellipsized)
        ("worship timer caption", &ws, "SERVICE TIMER"),
        ("worship readout", &ws, "12:45"),
        ("scripture screen label", &sc, "STAGE · SCRIPTURE"),
        ("scripture reference", &sc, "AMAZING GRACE"),
        ("scripture NEXT chip", &sc, "NEXT"),
        ("scripture status pill", &sc, "ON TIME"),
        ("scripture TIME LEFT", &sc, "TIME LEFT"),
        ("scripture readout", &sc, "12:45"),
        ("timer-only header", &to, "SERVICE TIMER"),
        ("timer-only segment", &to, "SERMON"),
        ("timer-only readout", &to, "12:45"),
    ] {
        let em = em_of(run(frame, needle).0);
        if em < BAR {
            below.push((role, em));
        }
    }
    // The worship next line, which the ellipsis may have shortened at this scale.
    let em = em_of(run_prefix(&ws, "I once was los").0);
    if em < BAR {
        below.push(("worship next line", em));
    }
    // The status pill is a 4-to-7-character state badge beside a 170px-equivalent readout;
    // it is the single role the fixed chrome positions cannot lift past the bar. Pinned as
    // an exact set so a regression that pushes another role under is a failure, not a shrug.
    let names: Vec<&str> = below.iter().map(|(n, _)| *n).collect();
    assert_eq!(
        names,
        vec!["scripture status pill"],
        "roles below {BAR}px-equivalent at the maximum scale changed: {below:?}"
    );
}

// --- STG-078: the high-contrast theme -----------------------------------------------------

/// A second stage palette exists and actually composes — `StageTheme` had exactly one
/// constructor, so NFR-020's high-contrast clause had no code path at all.
#[test]
fn the_high_contrast_theme_composes_a_distinct_stage() {
    let cur = slide("Amazing Grace", &["Amazing grace"]);
    let make = |theme: &StageTheme| {
        compose_stage(
            Some(&cur),
            None,
            Some(&running()),
            StageTemplate::Worship,
            None,
            &ctx(STAGE_TEXT_SCALE_DEFAULT),
            theme,
            W,
            H,
        )
    };
    let dark = make(&StageTheme::dark());
    let hc = make(&StageTheme::high_contrast());
    assert_eq!(
        texts(&dark),
        texts(&hc),
        "the two palettes must lay the SAME stage out — only the colours differ"
    );
    assert_ne!(
        dark.background, hc.background,
        "the high-contrast theme renders on the same field as the dark one"
    );
    assert_eq!(hc.background, Rgba::BLACK);
    // Layout is identical, so the layer COUNT must match too — a palette must not be able
    // to add or drop chrome.
    assert_eq!(dark.layers.len(), hc.layers.len());
}

// --- Regression guards --------------------------------------------------------------------

/// STG-071 is deliberately NOT "corrected" toward Figma: the frame draws gold-on-white
/// (2.04:1, fails AA at every size) and the implementation inverts it to a dark label on the
/// gold token (11.19:1). This batch touched that chip's size, tracking and shape, so it pins
/// the polarity that must survive.
#[test]
fn the_production_message_chip_keeps_its_accessible_polarity() {
    let theme = StageTheme::dark();
    let msg = compose(
        StageTemplate::Worship,
        false,
        STAGE_TEXT_SCALE_DEFAULT,
        Some("WRAP UP · 2 MIN LEFT"),
        W,
        H,
    );
    let chip_ink = msg
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text { text, color, .. } if text == "MESSAGE FROM PRODUCTION" => Some(*color),
            _ => None,
        })
        .expect("the production-message chip renders");
    assert_eq!(
        chip_ink, theme.background,
        "the chip label is no longer the dark ink — gold on white measures 2.04:1"
    );
    assert!(
        shapes(&msg)
            .iter()
            .any(|(.., fill, _)| *fill == theme.accent),
        "the chip is no longer filled with the gold token"
    );
    // The point of the inversion is the contrast it buys: gold-on-white is 2.04:1.
    let ratio = selahcue_present::tokens::contrast_ratio(chip_ink, theme.accent);
    assert!(
        ratio >= 4.5,
        "the message chip measures {ratio:.2}:1 — the frame's gold-on-white is 2.04:1 and \
         this inversion exists to avoid it"
    );
}

/// Every template still composes without panicking at a pathological size and at the extreme
/// scales — the composer must never take the output down.
#[test]
fn the_composer_never_panics_at_any_scale_or_size() {
    for template in [
        StageTemplate::Worship,
        StageTemplate::Scripture,
        StageTemplate::TimerOnly,
    ] {
        for scale in [0, STAGE_TEXT_SCALE_MIN, STAGE_TEXT_SCALE_MAX, u16::MAX] {
            for (w, h) in [(1u32, 1u32), (160, 90), (200, 100), (3840, 2160)] {
                for up in [false, true] {
                    let _ = compose(template, up, scale, Some("WRAP UP"), w, h);
                }
            }
        }
    }
}
