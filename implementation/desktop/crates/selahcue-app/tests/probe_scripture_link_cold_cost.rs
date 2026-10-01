//! Cold-cost probe for resolving a plan's scripture links on the operator view-build path
//! (86ak84fbd). A MEASUREMENT, not a gate: it prints, it asserts nothing about time, and it is
//! `#[ignore]`d so `cargo test` never pays for it. The deterministic gate is
//! `test_scripture_link_resolution_is_lazy.rs`; this file produces the before/after numbers
//! quoted in the ticket and the PR.
//!
//! The cost it measures is **first-touch**: the bundled corpus is decoded lazily into
//! process-wide `OnceLock`s, so only the FIRST view build in a process pays, and a second
//! `#[test]` in the same process would measure a warm cache. That is why this file holds exactly
//! one test and why the numbers come from several fresh processes.
//!
//! Knobs (environment, so one binary yields every variant):
//! - `PROBE_ACTION=blackout` (default) times the first `OperatorShell::blackout(true)` — the
//!   emergency control the ticket measured; `PROBE_ACTION=view` times the first `view()`.
//! - `PROBE_LINKED=1` (default) links each of five items to John 3:16 in a different bundled
//!   translation; `PROBE_LINKED=0` is the CONTROL — the same five items with no link — which is
//!   what the first action costs for reasons unrelated to scripture (first render, allocator
//!   warm-up). The scripture cost is the difference.
//!
//! Run (release profile — never compare numbers across profiles; debug gzip/SHA is ~19x slower;
//! and wall-clock on a busy machine is noisy, so take several processes and read min + median):
//!
//! ```text
//! cargo test -p selahcue-app --release --test probe_scripture_link_cold_cost --no-run
//! for i in 1 2 3 4 5 6 7 8 9 10 11; do
//!   PROBE_ACTION=blackout PROBE_LINKED=1 \
//!     target/release/deps/probe_scripture_link_cold_cost-<hash> --ignored --nocapture | grep PROBE
//! done
//! ```

#![allow(clippy::unwrap_used)]

use selahcue_app::{LiveController, OperatorShell};
use selahcue_core::plan::{ItemContent, ItemKind, ServicePlan};
use selahcue_present::Theme;
use std::sync::{Arc, Mutex};
use std::time::Instant;

/// Resident set size of this process in KiB, via `ps` (macOS + Linux). `None` if unavailable.
fn rss_kib() -> Option<u64> {
    let out = std::process::Command::new("ps")
        .args(["-o", "rss=", "-p", &std::process::id().to_string()])
        .output()
        .ok()?;
    String::from_utf8(out.stdout).ok()?.trim().parse().ok()
}

fn mib(kib: Option<u64>) -> f64 {
    kib.map_or(f64::NAN, |k| k as f64 / 1024.0)
}

#[test]
#[ignore = "measurement probe — run with --release --ignored --nocapture, one fresh process per sample"]
fn probe_first_operator_action_on_a_plan_naming_every_bundled_translation() {
    let linked = std::env::var("PROBE_LINKED").map_or(true, |v| v != "0");
    let action = std::env::var("PROBE_ACTION").unwrap_or_else(|_| "blackout".into());

    let mut plan = ServicePlan::new("Sunday");
    for code in ["KJV", "WEB", "ASV", "WEBBE", "DBY"] {
        let id = plan.add_item(ItemKind::Scripture, format!("John 3:16 ({code})"));
        if linked {
            plan.set_item_content(
                id,
                Some(ItemContent::Scripture {
                    reference: "John 3:16".into(),
                    translation: Some(code.into()),
                    verses_per_slide: None,
                    verse_numbers: None,
                }),
            )
            .unwrap();
        }
    }
    let shell = OperatorShell::new(Arc::new(Mutex::new(LiveController::new(
        plan,
        320,
        180,
        Theme::dark(),
    ))));

    let rss_before = rss_kib();
    let t = Instant::now();
    let first = match action.as_str() {
        "view" => shell.view(),
        _ => shell.blackout(true),
    };
    let first_ms = t.elapsed().as_secs_f64() * 1e3;
    let rss_after = rss_kib();
    assert_eq!(first.items.len(), 5, "premise: the whole plan is in view");

    let t = Instant::now();
    let warm = shell.blackout(false);
    let warm_us = t.elapsed().as_secs_f64() * 1e6;
    assert_eq!(warm.items.len(), 5);

    const N: u32 = 200;
    let t = Instant::now();
    for _ in 0..N {
        std::hint::black_box(shell.view());
    }
    let steady_us = t.elapsed().as_secs_f64() * 1e6 / f64::from(N);

    println!(
        "PROBE action={action} linked={} first_ms={first_ms:.2} second_action_us={warm_us:.1} \
         steady_view_us={steady_us:.1} rss_before_mib={:.1} rss_after_first_mib={:.1} \
         rss_delta_mib={:.1}",
        u8::from(linked),
        mib(rss_before),
        mib(rss_after),
        mib(rss_after) - mib(rss_before),
    );
}
