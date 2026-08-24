//! Native (Rust-rendered) capture side of the **visual-parity harness**.
//!
//! The operator console is HTML and can be screenshotted by a browser. The stage /
//! confidence monitor and the audience output are NOT — they are composed by the CPU
//! rasterizer in `selahcue-engine` and never exist as a DOM. This test target is how
//! they become PNGs a human (and `scripts/vp_compare.py`) can look at, rendered at the
//! Figma frames' native sizes (stage frames are 1000x563; the audience output is the
//! real 1920x1080 canvas).
//!
//! Two modes, ONE code path — the harness renders exactly what this test asserts on:
//!
//! * default (no env): render every capture into a temp dir, assert it, delete it.
//!   This runs in `cargo test -p selahcue-present` and is a real gate, not a no-op.
//! * `SELAHCUE_VISUAL_OUT=<dir>`: additionally write the PNGs + `index.json` there
//!   for `scripts/vp_capture_native.py` to collect.
//!
//! WHY THE ASSERTIONS LOOK LIKE THIS (CLAUDE.md, "Bounded-memory tests"): a visual
//! harness whose capture step silently fails produces a blank frame, and a blank frame
//! is indistinguishable from "no diff yet" unless something asserts otherwise. So every
//! capture declares what it must LOOK like — `Expect::Ink` (drew content) or
//! `Expect::Uniform` (deliberately one colour, e.g. blackout) — and both directions are
//! asserted. `Expect::Uniform` is the positive control for the ink detector: if
//! `ink_fraction` were stubbed to return a constant, the blackout capture would fail.

#![allow(clippy::unwrap_used)]

use png::{BitDepth, ColorType, Encoder};
use selahcue_engine::raster::FrameBuffer;
use selahcue_present::stage::StageTemplate;
use selahcue_present::{Presenter, Slide, StageDisplay, StageTheme, Theme, TimerView, WallClock};
use std::fs;
use std::io::BufWriter;
use std::path::{Path, PathBuf};

/// The Figma stage/confidence frames (373:133 … 375:128) are all 1000x563.
const STAGE_W: u32 = 1000;
const STAGE_H: u32 = 563;
/// The audience output's real canvas. There is no 1:1 Figma frame for it (the
/// Design 2.0 board covers it only as vignettes inside `346:124`), so these
/// captures are for human review, not for an automated whole-frame diff.
const OUT_W: u32 = 1920;
const OUT_H: u32 = 1080;

/// Hard cap on how many images one native capture run may produce. The run writes a
/// FIXED set of filenames and overwrites them, so a repeat run must not grow the
/// directory — `native_captures_are_idempotent_and_bounded` runs the writer twice and
/// asserts the file count is unchanged, which is what actually bites if someone makes
/// the filenames run-unique (a timestamp, a counter) and turns the output directory
/// into an unbounded accumulator.
const MAX_NATIVE_CAPTURES: usize = 24;

/// Pin the premise at compile time: if the capture list ever grows past the cap, this
/// fails to COMPILE rather than silently turning the bound into a no-op.
const _: () = assert!(CAPTURES.len() <= MAX_NATIVE_CAPTURES);
/// …and pin that the cap still leaves headroom, so the bound is not simply "the number
/// of captures we happen to have", which would make the idempotence test vacuous.
const _: () = assert!(MAX_NATIVE_CAPTURES >= CAPTURES.len() + 4);

/// What a capture must look like once rendered.
#[derive(Clone, Copy, PartialEq, Debug)]
enum Expect {
    /// Content was drawn: at least this fraction of pixels differ from the modal colour.
    Ink(f64),
    /// Deliberately a single colour (blackout). The negative control for `Ink`.
    Uniform,
}

struct Capture {
    slug: &'static str,
    width: u32,
    height: u32,
    /// The Figma node this frame is meant to match, or `""` when there is no 1:1
    /// reference frame (the comparator reports those as "captured, not compared").
    node: &'static str,
    expect: Expect,
}

// Kept as a readable one-line-per-capture table; rustfmt would explode it to 48 lines.
#[rustfmt::skip]
const CAPTURES: &[Capture] = &[
    Capture { slug: "stage-worship-running", width: STAGE_W, height: STAGE_H, node: "373:133", expect: Expect::Ink(0.01) },
    Capture { slug: "stage-worship-timeup", width: STAGE_W, height: STAGE_H, node: "373:159", expect: Expect::Ink(0.01) },
    Capture { slug: "stage-scripture-running", width: STAGE_W, height: STAGE_H, node: "374:128", expect: Expect::Ink(0.01) },
    Capture { slug: "stage-timer-only-running", width: STAGE_W, height: STAGE_H, node: "374:151", expect: Expect::Ink(0.01) },
    Capture { slug: "stage-timer-only-timeup", width: STAGE_W, height: STAGE_H, node: "374:166", expect: Expect::Ink(0.01) },
    Capture { slug: "stage-message", width: STAGE_W, height: STAGE_H, node: "375:128", expect: Expect::Ink(0.01) },
    Capture { slug: "audience-scripture-live", width: OUT_W, height: OUT_H, node: "", expect: Expect::Ink(0.005) },
    Capture { slug: "audience-blackout", width: OUT_W, height: OUT_H, node: "", expect: Expect::Uniform },
];

// ---------------------------------------------------------------------------
// Scene builders — the live state each Figma frame depicts.
// ---------------------------------------------------------------------------

fn worship_now() -> Slide {
    // The copy the Figma frames themselves draw (373:133 / 373:159 / 375:128). Matching it
    // matters: the diff is a measure of LAYOUT and TYPOGRAPHY, and different words would
    // wrap differently and inflate every number with noise the design pass cannot act on.
    Slide::new(
        "Amazing grace, how sweet the sound",
        ["that saved a wretch like me"],
    )
}

fn worship_next() -> Slide {
    Slide::new("I once was lost, but now am found", Vec::<String>::new())
}

fn scripture_now() -> Slide {
    // Figma 374:128 — "ISAIAH 61:5 · KJV" over the verse text.
    Slide::new(
        "Isaiah 61:5",
        [
            "And strangers shall stand and feed your flocks,",
            "and the sons of the alien shall be your plowmen.",
        ],
    )
}

fn scripture_next() -> Slide {
    Slide::new(
        "Isaiah 61:6 · But ye shall be named the Priest",
        Vec::<String>::new(),
    )
}

/// 12:45 remaining — the value every running Figma stage frame shows.
fn running_timer() -> TimerView {
    TimerView {
        elapsed_secs: 735,
        remaining_secs: Some(765),
        time_up: false,
        warn: false,
        progress: 0.51,
        overrun_secs: 0,
    }
}

/// TIME UP, 32 seconds over — the `OVER 0:32` readout in 373:159 / 374:166.
fn timeup_timer() -> TimerView {
    TimerView {
        elapsed_secs: 32,
        remaining_secs: Some(0),
        time_up: true,
        warn: false,
        progress: 0.0,
        overrun_secs: 32,
    }
}

fn clock() -> WallClock {
    WallClock::new("Sunday · August 3, 2026", "10:42 AM")
}

fn stage(
    template: StageTemplate,
    message: Option<&str>,
    timer: &TimerView,
    now: Option<&Slide>,
    next: Option<&Slide>,
) -> FrameBuffer {
    let mut display = StageDisplay::new(STAGE_W, STAGE_H, StageTheme::dark());
    display.set_template(template);
    display.set_clock(Some(clock()));
    display.set_song_position(Some((2, 4)));
    if let Some(m) = message {
        display.set_message(m);
    }
    display.update(now, next, Some(timer));
    display.output().clone()
}

fn render(slug: &str) -> FrameBuffer {
    let (now, next) = (worship_now(), worship_next());
    match slug {
        "stage-worship-running" => stage(
            StageTemplate::Worship,
            None,
            &running_timer(),
            Some(&now),
            Some(&next),
        ),
        "stage-worship-timeup" => stage(
            StageTemplate::Worship,
            None,
            &timeup_timer(),
            Some(&now),
            Some(&next),
        ),
        "stage-scripture-running" => {
            let (s, sn) = (scripture_now(), scripture_next());
            stage(
                StageTemplate::Scripture,
                None,
                &running_timer(),
                Some(&s),
                Some(&sn),
            )
        }
        "stage-timer-only-running" => {
            stage(StageTemplate::TimerOnly, None, &running_timer(), None, None)
        }
        "stage-timer-only-timeup" => {
            stage(StageTemplate::TimerOnly, None, &timeup_timer(), None, None)
        }
        "stage-message" => stage(
            StageTemplate::Worship,
            Some("WRAP UP · 2 MIN LEFT"),
            &running_timer(),
            Some(&now),
            Some(&next),
        ),
        "audience-scripture-live" => {
            let mut p = Presenter::new(OUT_W, OUT_H, Theme::classic());
            p.stage(scripture_now());
            assert!(
                p.go_live(),
                "audience capture: go_live() refused the staged slide"
            );
            p.live_output().clone()
        }
        "audience-blackout" => {
            let mut p = Presenter::new(OUT_W, OUT_H, Theme::classic());
            p.stage(scripture_now());
            assert!(
                p.go_live(),
                "audience capture: go_live() refused the staged slide"
            );
            p.blackout(true);
            p.live_output().clone()
        }
        other => panic!("visual-parity: no renderer for capture slug {other:?}"),
    }
}

// ---------------------------------------------------------------------------
// Image inspection + PNG writing
// ---------------------------------------------------------------------------

/// Fraction of pixels whose colour differs from the frame's MODAL colour.
///
/// Bounded by construction: colours are quantised to 5 bits per channel into a
/// fixed 32768-entry histogram, so the working set does not scale with the number of
/// distinct colours in the frame (a full-colour map would).
fn ink_fraction(fb: &FrameBuffer) -> f64 {
    const BUCKETS: usize = 32 * 32 * 32;
    let mut hist = vec![0u32; BUCKETS];
    let bucket = |p: &[u8]| {
        ((p[0] as usize >> 3) << 10) | ((p[1] as usize >> 3) << 5) | (p[2] as usize >> 3)
    };
    for px in fb.bytes().chunks_exact(4) {
        hist[bucket(px)] += 1;
    }
    let total: u64 = fb.bytes().len() as u64 / 4;
    if total == 0 {
        return 0.0;
    }
    let modal = hist.iter().copied().max().unwrap_or(0) as u64;
    (total - modal) as f64 / total as f64
}

/// True when the frame is a single colour at 5-bit precision — the blank-capture
/// signature, and the shape a deliberate blackout must have.
fn is_uniform(fb: &FrameBuffer) -> bool {
    ink_fraction(fb) == 0.0
}

fn write_png(fb: &FrameBuffer, path: &Path) {
    let file = fs::File::create(path).unwrap_or_else(|e| panic!("create {}: {e}", path.display()));
    let mut enc = Encoder::new(BufWriter::new(file), fb.width(), fb.height());
    enc.set_color(ColorType::Rgba);
    enc.set_depth(BitDepth::Eight);
    let mut writer = enc.write_header().expect("png header");
    writer.write_image_data(fb.bytes()).expect("png data");
}

/// Render every capture into `dir`, writing `index.json` alongside. Returns the
/// per-capture (slug, ink fraction) so the caller can assert on it.
fn render_all_into(dir: &Path) -> Vec<(&'static str, f64)> {
    fs::create_dir_all(dir).expect("create capture dir");
    let mut measured = Vec::new();
    let mut index = String::from(
        "{\n  \"engine\": \"selahcue-engine CPU rasterizer (Rust)\",\n  \"captures\": [\n",
    );
    for (i, cap) in CAPTURES.iter().enumerate() {
        let fb = render(cap.slug);
        assert_eq!(
            (fb.width(), fb.height()),
            (cap.width, cap.height),
            "capture {} rendered {}x{}, expected {}x{} — the harness would compare the WRONG SIZE",
            cap.slug,
            fb.width(),
            fb.height(),
            cap.width,
            cap.height
        );
        write_png(&fb, &dir.join(format!("{}.png", cap.slug)));
        measured.push((cap.slug, ink_fraction(&fb)));
        index.push_str(&format!(
            "    {{\"slug\": \"{}\", \"file\": \"{}.png\", \"width\": {}, \"height\": {}, \"node\": \"{}\", \"ink\": {:.6}}}{}\n",
            cap.slug,
            cap.slug,
            cap.width,
            cap.height,
            cap.node,
            ink_fraction(&fb),
            if i + 1 == CAPTURES.len() { "" } else { "," }
        ));
    }
    index.push_str("  ]\n}\n");
    fs::write(dir.join("index.json"), index).expect("write index.json");
    measured
}

fn scratch_dir(tag: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("selahcue-vp-{tag}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    dir
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

/// Every native capture renders at its Figma frame's size and actually DREW something —
/// asserted BEFORE anything downstream compares it, because a blank frame is the exact
/// failure a similarity score cannot distinguish from "not diffed yet".
///
/// `Expect::Uniform` (blackout) is the positive control: it asserts the ink detector
/// still reports zero when the frame genuinely is one colour, so a stubbed or
/// always-true `ink_fraction` fails here rather than blessing every other capture.
#[test]
fn every_native_capture_renders_at_figma_size_with_the_expected_ink() {
    let dir = scratch_dir("render");
    let measured = render_all_into(&dir);
    assert_eq!(
        measured.len(),
        CAPTURES.len(),
        "a capture went missing from the run"
    );
    for (cap, (slug, ink)) in CAPTURES.iter().zip(&measured) {
        assert_eq!(&cap.slug, slug, "capture order drifted from CAPTURES");
        match cap.expect {
            Expect::Ink(min) => assert!(
                *ink >= min,
                "capture {slug}: ink fraction {ink:.4} < {min} — the frame is (near-)blank, so \
                 NOTHING downstream compared real content; a similarity score on this image \
                 would be meaningless"
            ),
            Expect::Uniform => assert!(
                *ink == 0.0,
                "capture {slug}: expected a single-colour frame (blackout) but ink fraction is \
                 {ink:.4} — either blackout regressed or the ink detector is measuring nothing"
            ),
        }
    }
    let _ = fs::remove_dir_all(&dir);
}

/// The blank detector must distinguish a drawn frame from a flat one in BOTH directions.
/// Without this, `is_uniform` could be hardwired to `false` and every capture above would
/// still pass.
#[test]
fn the_blank_frame_detector_separates_drawn_frames_from_flat_ones() {
    let flat = FrameBuffer::filled(64, 64, selahcue_engine::scene::Rgba::BLACK);
    assert!(is_uniform(&flat), "a filled frame must read as uniform");
    let drawn = render("stage-worship-running");
    assert!(
        !is_uniform(&drawn),
        "a composed stage frame must NOT read as uniform — if it does, composition produced \
         nothing and every parity number computed from it is a fiction"
    );
}

/// Re-running the capture writer must OVERWRITE, never accumulate: the output directory
/// is a fixed set of filenames. This is the bounded-growth guard for the native side —
/// it bites if someone makes the filenames run-unique (timestamp/counter), which would
/// turn a directory a human runs on every design pass into an unbounded image dump.
#[test]
fn native_captures_are_idempotent_and_bounded() {
    let dir = scratch_dir("idempotent");
    render_all_into(&dir);
    let after_first = fs::read_dir(&dir).unwrap().count();
    render_all_into(&dir);
    let after_second = fs::read_dir(&dir).unwrap().count();
    assert_eq!(
        after_first, after_second,
        "a second capture run changed the file count ({after_first} -> {after_second}); the \
         capture directory accumulates instead of overwriting"
    );
    assert_eq!(
        after_first,
        CAPTURES.len() + 1,
        "expected exactly one PNG per capture plus index.json"
    );
    assert!(
        CAPTURES.len() <= MAX_NATIVE_CAPTURES,
        "capture list outgrew MAX_NATIVE_CAPTURES"
    );
    let _ = fs::remove_dir_all(&dir);
}

/// The harness entry point: with `SELAHCUE_VISUAL_OUT` set, write the captures where
/// `scripts/vp_capture_native.py` can collect them. Unset (the normal `cargo test` case)
/// this is a no-op — the assertions above already exercised the same `render_all_into`.
#[test]
fn export_captures_when_the_harness_asks_for_them() {
    let Ok(out) = std::env::var("SELAHCUE_VISUAL_OUT") else {
        return;
    };
    let dir = PathBuf::from(out);
    let measured = render_all_into(&dir);
    for (cap, (slug, ink)) in CAPTURES.iter().zip(&measured) {
        if let Expect::Ink(min) = cap.expect {
            assert!(
                *ink >= min,
                "exported capture {slug} is (near-)blank: ink {ink:.4} < {min}"
            );
        }
    }
    println!(
        "visual-parity: wrote {} native captures to {}",
        measured.len(),
        dir.display()
    );
}
