//! The render↔control IPC contract and the never-blank render engine (ADR-0015).
//!
//! [`EngineCommand`]/[`EngineEvent`] are the single, versioned, serde-serializable
//! seam that both the real control plane and the test harness drive. [`Engine`]
//! applies commands and **guarantees a non-blank live output** (NFR-024): an
//! injected fault holds the last good frame, and only a successful render replaces
//! the output. It is backend-agnostic — here it uses the GPU-free
//! [`raster`](crate::raster); the wgpu backend renders the same scenes later.

use crate::fault::Fault;
use crate::raster::{self, FrameBuffer};
use crate::scene::Frame;
use serde::{Deserialize, Serialize};

/// Version of the render↔control IPC command/event contract. Bumped on any
/// breaking change to the message shapes.
pub const IPC_VERSION: u16 = 1;

/// A command from the control plane (or test harness) to the engine.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "cmd", rename_all = "snake_case")]
pub enum EngineCommand {
    /// Replace the live scene and render it.
    SetScene { frame: Frame },
    /// Toggle emergency blackout (a deliberate, safe black output).
    Blackout { on: bool },
    /// Clear to the safe background (black, no layers).
    Clear,
    /// Inject a fault — the live output must **hold** its last good frame, not blank.
    InjectFault { fault: Fault },
    /// Capture the current output (pixel readback).
    Capture,
}

/// An event from the engine back to the control plane / harness.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "snake_case")]
pub enum EngineEvent {
    /// A new frame was rendered and presented; `seq` increments per presented frame.
    FrameRendered { seq: u64 },
    /// A fault was isolated — the output is holding its last good frame.
    OutputHeld { fault: Fault },
    /// A good frame was presented after a fault (recovered).
    Recovered { seq: u64 },
    /// The current output was captured.
    Captured { seq: u64 },
    /// A command was rejected (e.g. an out-of-range frame resolution). The live
    /// output is held unchanged — a bad command never blanks it (NFR-024).
    Rejected { reason: String },
}

/// A single render output (one display). Never blanks: a fault holds the last good
/// frame; only a successful render replaces it.
pub struct Engine {
    scene: Frame,
    output: FrameBuffer,
    seq: u64,
    faulted: bool,
}

impl Engine {
    /// A new engine whose initial output is a safe black frame of `width×height`.
    /// Dimensions are clamped into the renderable range so construction can never
    /// panic or over-allocate.
    pub fn new(width: u32, height: u32) -> Self {
        let width = width.clamp(1, raster::MAX_DIMENSION);
        let height = height.clamp(1, raster::MAX_DIMENSION);
        let scene = Frame::new(width, height);
        let output = raster::render(&scene);
        Engine {
            scene,
            output,
            seq: 0,
            faulted: false,
        }
    }

    /// The live output — always a valid, non-blank frame.
    pub fn output(&self) -> &FrameBuffer {
        &self.output
    }

    /// Number of frames presented so far.
    pub fn seq(&self) -> u64 {
        self.seq
    }

    /// Whether the output is currently held because of a fault.
    pub fn is_faulted(&self) -> bool {
        self.faulted
    }

    fn present(&mut self, scene: Frame) -> EngineEvent {
        self.scene = scene;
        self.output = raster::render(&self.scene);
        self.seq += 1;
        if self.faulted {
            self.faulted = false;
            EngineEvent::Recovered { seq: self.seq }
        } else {
            EngineEvent::FrameRendered { seq: self.seq }
        }
    }

    /// Apply one command and return the resulting event.
    pub fn apply(&mut self, command: EngineCommand) -> EngineEvent {
        match command {
            EngineCommand::SetScene { frame } => {
                // Reject an out-of-range resolution instead of rendering it — the
                // live output holds its last good frame rather than crashing.
                if raster::is_renderable(frame.width, frame.height) {
                    self.present(frame)
                } else {
                    EngineEvent::Rejected {
                        reason: format!(
                            "frame {}x{} exceeds the renderable range (max {})",
                            frame.width,
                            frame.height,
                            raster::MAX_DIMENSION
                        ),
                    }
                }
            }
            EngineCommand::Blackout { on } => {
                let mut scene = self.scene.clone();
                scene.blackout = on;
                self.present(scene)
            }
            EngineCommand::Clear => {
                let scene = Frame::new(self.scene.width, self.scene.height);
                self.present(scene)
            }
            EngineCommand::InjectFault { fault } => {
                // Output-failure isolation: mark faulted and HOLD the last good
                // frame — `self.output` is deliberately left untouched.
                self.faulted = true;
                EngineEvent::OutputHeld { fault }
            }
            EngineCommand::Capture => EngineEvent::Captured { seq: self.seq },
        }
    }
}
