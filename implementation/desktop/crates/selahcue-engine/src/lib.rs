//! SelahCue render-engine test seam (ADR-0015).
//!
//! The engine is built with its test-harness contract as a first-class part of the
//! design, so the reliability guarantees (never-blank output NFR-024, bounded fault
//! recovery FR-160, seizure-safe flashing FR-175, slide latency NFR-004) are
//! verifiable from day one — before the GPU backend exists.
//!
//! - [`scene`] — the backend-independent scene model (`Frame`, `Layer`, `Rgba`).
//! - [`raster`] — a GPU-free deterministic rasterizer + pixel readback.
//! - [`media`] — bounded, deterministic, panic-contained still-image (PNG) decode + a
//!   size-capped decode cache for `Layer::Image` (S8-6; ADR-0018).
//! - [`analysis`] — the FR-175 flash-rate analyzer and the NFR-004 latency proxy.
//! - [`fault`] — injectable faults for output-failure-isolation tests.
//! - [`engine`] — the render↔control IPC contract and the never-blank [`Engine`].
//!
//! The wgpu on-screen backend (a later batch) renders the *same* [`scene::Frame`];
//! cross-GPU parity is asserted perceptually (SSIM ≥ 0.99), not by byte-equality.

#![forbid(unsafe_code)]

pub mod analysis;
pub mod engine;
pub mod fault;
pub mod media;
pub mod raster;
pub mod scene;

pub use engine::{Engine, EngineCommand, EngineEvent, IPC_VERSION};
pub use fault::Fault;
pub use media::{decode_png, DecodeError, DecodeLimits, DecodedImage};
pub use raster::{render, FrameBuffer};
pub use scene::{
    Frame, GradientDirection, Layer, MediaRef, Rect, Rgba, ShapeKind, TextAlign, TextStyle,
};
