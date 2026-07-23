//! Fault-injection kinds for output-failure-isolation testing (ADR-0015;
//! NFR-024, FR-160).

use serde::{Deserialize, Serialize};

/// A fault the harness can inject to prove the "no component failure blanks or
/// clears the live output" guarantee: after injection the affected output must
/// hold its last good frame, other outputs must be unaffected, and recovery must
/// be bounded.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Fault {
    /// GPU device lost/reset mid-render.
    GpuDeviceLost,
    /// A media decoder failed to produce a frame.
    DecoderFault,
    /// The UI↔engine IPC channel stalled.
    IpcStall,
    /// The autosave/persistence path hit a full disk.
    DiskFull,
}

impl Fault {
    /// Every fault kind — for exhaustive fault-matrix tests.
    pub const ALL: [Fault; 4] = [
        Fault::GpuDeviceLost,
        Fault::DecoderFault,
        Fault::IpcStall,
        Fault::DiskFull,
    ];
}
