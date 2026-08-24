//! Launch-stability and storage guards (FR-169, NFR-023/024; story 86ajp09td).
//!
//! **Crash-loop breaker:** if the app dies repeatedly right after launch (a
//! corrupt store, a driver crash on restore, …), recovery itself becomes the
//! failure. Each launch is journaled; reaching [`STABLE_AFTER`] of uptime (or a
//! clean exit) clears the journal. Three unstable launches inside
//! [`CRASH_WINDOW`] trip the breaker: the app starts CLEAN — the persisted
//! session is *skipped, never deleted*, so a later healthy launch can resume it
//! deliberately.
//!
//! **Storage guard:** checkpoint writes need headroom. Below [`DISK_LOW`] the
//! operator is warned (writes continue — session rows are tiny); below
//! [`DISK_CRITICAL`] checkpoint writes stop (never risk corrupting the store on
//! a full disk) and the degradation is reported loudly — never silently.
//!
//! All decision logic is pure (`assess`, `disk_status_from`) and unit-tested;
//! the file I/O wrapper is deliberately thin. Wall-clock (`SystemTime`) is used
//! for the journal because crash gaps span process lifetimes.

use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// Unstable launches within this window trip the breaker (FR-169: 3 in 60s).
pub const CRASH_WINDOW: Duration = Duration::from_secs(60);
/// How many rapid unstable launches trip the breaker.
pub const CRASH_LIMIT: usize = 3;
/// Uptime after which a launch counts as stable (the journal clears).
pub const STABLE_AFTER: Duration = Duration::from_secs(10);
/// Warn below this much free space at the data dir.
pub const DISK_LOW: u64 = 100 * 1024 * 1024;
/// Stop checkpoint writes below this floor (never corrupt a full disk).
pub const DISK_CRITICAL: u64 = 10 * 1024 * 1024;

/// The launch verdict the shell acts on.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LaunchVerdict {
    /// Restore the session normally.
    Normal,
    /// The breaker tripped: start clean (session preserved on disk).
    CrashLoop {
        /// Unstable launches inside the window, including this one.
        rapid_launches: usize,
    },
}

/// Pure breaker decision: `previous` = start times (unix secs) of launches that
/// never reached stability; `now` = this launch. Counting includes this launch.
pub fn assess(previous: &[u64], now: u64) -> LaunchVerdict {
    let window = CRASH_WINDOW.as_secs();
    let rapid = previous
        .iter()
        .filter(|&&t| t <= now && now - t <= window)
        .count()
        + 1; // this launch
    if rapid >= CRASH_LIMIT {
        LaunchVerdict::CrashLoop {
            rapid_launches: rapid,
        }
    } else {
        LaunchVerdict::Normal
    }
}

/// Free-space status of the checkpoint volume.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DiskStatus {
    /// Healthy headroom. Carries the figure too, so the operator view can show how much is
    /// left rather than only that it is "fine" — a bare verdict makes a slow slide toward the
    /// warning threshold invisible until it crosses.
    Ok { available: u64 },
    /// Low headroom — warn, keep writing (session rows are tiny).
    Low { available: u64 },
    /// Below the floor — stop checkpoint writes, report loudly.
    Critical { available: u64 },
}

/// Pure threshold mapping (testable without a filesystem).
pub fn disk_status_from(available: u64) -> DiskStatus {
    if available < DISK_CRITICAL {
        DiskStatus::Critical { available }
    } else if available < DISK_LOW {
        DiskStatus::Low { available }
    } else {
        DiskStatus::Ok { available }
    }
}

/// Free space at `path`, if the platform can report it.
pub fn disk_status(path: &Path) -> Option<DiskStatus> {
    fs4::available_space(path).ok().map(disk_status_from)
}

/// The on-disk launch journal (one unix-seconds start time per line for
/// launches that never reached stability).
pub struct LaunchGuard {
    journal: PathBuf,
}

impl LaunchGuard {
    pub fn new(data_dir: &Path) -> Self {
        LaunchGuard {
            journal: data_dir.join("launches.txt"),
        }
    }

    fn read(&self) -> Vec<u64> {
        std::fs::read_to_string(&self.journal)
            .unwrap_or_default()
            .lines()
            .filter_map(|l| l.trim().parse().ok())
            .collect()
    }

    /// Record this launch and return the verdict. The journal only ever holds
    /// the entries inside the window plus this launch — bounded by design.
    pub fn record_launch(&self) -> LaunchVerdict {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let previous = self.read();
        let verdict = assess(&previous, now);
        let window = CRASH_WINDOW.as_secs();
        let mut keep: Vec<u64> = previous
            .into_iter()
            .filter(|&t| t <= now && now - t <= window)
            .collect();
        keep.push(now);
        let body = keep
            .iter()
            .map(u64::to_string)
            .collect::<Vec<_>>()
            .join("\n");
        if let Err(e) = std::fs::write(&self.journal, body) {
            eprintln!("SelahCue: could not write the launch journal ({e}).");
        }
        verdict
    }

    /// This launch reached stability (10s uptime or a clean exit): forgive all
    /// journaled launches.
    pub fn mark_stable(&self) {
        let _ = std::fs::remove_file(&self.journal);
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn three_rapid_launches_trip_the_breaker() {
        // Two prior unstable launches inside 60s + this one = the FR-169 limit.
        assert_eq!(assess(&[], 1000), LaunchVerdict::Normal);
        assert_eq!(assess(&[990], 1000), LaunchVerdict::Normal);
        assert_eq!(
            assess(&[950, 990], 1000),
            LaunchVerdict::CrashLoop { rapid_launches: 3 }
        );
        // Old crashes outside the window are forgiven.
        assert_eq!(assess(&[900, 935], 1000), LaunchVerdict::Normal);
        assert_eq!(assess(&[900, 990], 1000), LaunchVerdict::Normal);
        // Clock skew (future timestamps) never counts toward the limit.
        assert_eq!(assess(&[2000, 3000], 1000), LaunchVerdict::Normal);
    }

    #[test]
    fn disk_thresholds_map_to_statuses() {
        assert_eq!(
            disk_status_from(u64::MAX),
            DiskStatus::Ok {
                available: u64::MAX
            }
        );
        assert_eq!(
            disk_status_from(DISK_LOW),
            DiskStatus::Ok {
                available: DISK_LOW
            }
        );
        assert_eq!(
            disk_status_from(DISK_LOW - 1),
            DiskStatus::Low {
                available: DISK_LOW - 1
            }
        );
        assert_eq!(disk_status_from(0), DiskStatus::Critical { available: 0 });
    }

    #[test]
    fn journal_round_trips_and_stays_bounded() {
        let dir = std::env::temp_dir().join(format!("selahcue-guard-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let guard = LaunchGuard::new(&dir);
        guard.mark_stable(); // clean slate

        assert_eq!(guard.record_launch(), LaunchVerdict::Normal);
        assert_eq!(guard.record_launch(), LaunchVerdict::Normal);
        assert!(matches!(
            guard.record_launch(),
            LaunchVerdict::CrashLoop { rapid_launches: 3 }
        ));
        // The journal never grows past the window's worth of entries + 1.
        assert!(guard.read().len() <= CRASH_LIMIT + 1);

        // Stability forgives everything.
        guard.mark_stable();
        assert_eq!(guard.record_launch(), LaunchVerdict::Normal);
        std::fs::remove_dir_all(&dir).ok();
    }
}
