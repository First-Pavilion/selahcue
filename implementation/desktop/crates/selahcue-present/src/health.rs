//! Output health — the **observable** form of the never-blank guarantee (NFR-024).
//!
//! `selahcue-engine` has always isolated faults correctly: [`EngineEvent::OutputHeld`]
//! holds the last good frame and [`EngineEvent::Recovered`] reports the next good one.
//! Until now nothing outside the engine's own tests ever read those events —
//! [`Presenter`](crate::present::Presenter) discarded every one — so the guarantee was
//! real but *unobservable*, and a held output rendered identically to a healthy one.
//! This module is the record that makes it visible.
//!
//! ## Why counters, and never a log
//!
//! The obvious shape is a list of past faults. That is an unbounded queue, which
//! `CLAUDE.md` forbids outright: a service that faults in a loop would grow it without
//! limit. [`OutputHealth`] is therefore **fixed-width counters only**. Its size is a
//! compile-time constant (asserted below), so boundedness is a property of the *type*
//! rather than of a cap some later edit could raise — there is no cap to raise.
//!
//! ## Why a counter, specifically
//!
//! The operator console polls state at 1 Hz; it has no event channel for system health
//! (see `docs/design/HOST-SIGNAL-INVENTORY.md`, which records that there is "no edge
//! signal anywhere"). A *level* (`held: bool`) sampled at 1 Hz cannot show a hold that
//! began and ended between two polls, so recovery would stay invisible. A **monotonic
//! counter turns that level into an edge**: a reader that remembers the previous
//! `recoveries` sees the increment regardless of when it happened. That is why NFR-024
//! recovery becomes observable here without adding any new plumbing.

use selahcue_engine::engine::EngineEvent;
use selahcue_engine::fault::Fault;

/// The live output's fault/recovery record.
///
/// `held` is **not stored** — [`Presenter::output_health`](crate::present::Presenter::output_health)
/// re-derives it from [`Engine::is_faulted`](selahcue_engine::engine::Engine::is_faulted) on every
/// read, so it is the engine's own truth and cannot drift out of sync with it. Only the counters
/// and the current fault kind, which the engine does not retain, are recorded here.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct OutputHealth {
    /// The live output is holding its last good frame right now (NFR-024 in effect).
    pub held: bool,
    /// The fault that caused the current hold. `None` when the output is not held —
    /// cleared on recovery so a stale reason can never be shown beside a healthy output.
    pub fault: Option<Fault>,
    /// Times the live output has been held this session (monotonic).
    pub holds: u64,
    /// Times it has recovered this session (monotonic). Compare against a remembered
    /// value to detect a recovery that happened between two polls.
    pub recoveries: u64,
}

/// `OutputHealth` must stay a small, fixed-size value type. This bites the moment
/// someone adds a `Vec`/`VecDeque`/`String` fault log to it — the very unbounded-growth
/// mistake the module doc rules out — because any heap collection adds at least a
/// pointer + length and pushes the size past this bound at COMPILE time, before a test
/// ever runs. Four `u64`-ish fields plus discriminants fit well inside 32 bytes.
const _: () = assert!(std::mem::size_of::<OutputHealth>() <= 32);

impl OutputHealth {
    /// Fold one engine event into the record. Every other event kind is deliberately
    /// ignored: `FrameRendered` is the healthy steady state, `Captured` is a readback,
    /// and `Rejected` means the command never reached the output at all (the caller
    /// already treats it as "Live unchanged"), so none of them is a health transition.
    pub(crate) fn record(&mut self, event: &EngineEvent) {
        match event {
            EngineEvent::OutputHeld { fault } => {
                self.fault = Some(*fault);
                self.holds = self.holds.saturating_add(1);
            }
            EngineEvent::Recovered { .. } => {
                self.fault = None;
                self.recoveries = self.recoveries.saturating_add(1);
            }
            _ => {}
        }
    }
}

/// The stable, lowercase wire tag for a fault kind.
///
/// Kept here rather than derived from `serde` so the operator-facing string is pinned by
/// this crate's tests and cannot change silently if the engine's serde attributes are
/// ever reworked. Matches `Fault`'s `rename_all = "snake_case"` representation.
pub fn fault_tag(fault: Fault) -> &'static str {
    match fault {
        Fault::GpuDeviceLost => "gpu_device_lost",
        Fault::DecoderFault => "decoder_fault",
        Fault::IpcStall => "ipc_stall",
        Fault::DiskFull => "disk_full",
    }
}
