//! SelahCue render-engine test seam (ADR-0015).
//!
//! The engine is built with its test-harness contract as a first-class part of the
//! design, so the reliability guarantees (never-blank output NFR-024, bounded fault
//! recovery FR-160, seizure-safe flashing FR-175, slide latency NFR-004) are
//! verifiable from day one — before the GPU backend exists.
//!
//! - [`scene`] — the backend-independent scene model (`Frame`, `Layer`, `Rgba`).
//! - [`raster`] — a GPU-free deterministic rasterizer + pixel readback.
//! - [`media`] — bounded, deterministic, panic-contained still-image (PNG + JPEG) decode + a
//!   size-capped decode cache for `Layer::Image` (S8-6; ADR-0018, amended by ADR-0025).
//! - [`analysis`] — the FR-175 flash-rate analyzer and the NFR-004 latency proxy.
//! - [`fault`] — injectable faults for output-failure-isolation tests.
//! - [`engine`] — the render↔control IPC contract and the never-blank [`Engine`].
//!
//! The wgpu on-screen backend (a later batch) renders the *same* [`scene::Frame`];
//! cross-GPU parity is asserted perceptually (SSIM ≥ 0.99), not by byte-equality.

#![forbid(unsafe_code)]

pub mod analysis;
pub mod engine;
/// The bounded single-tag EXIF orientation reader ([`media`]'s step 11) — private: callers get
/// upright pixels from `decode_image`, never an orientation value to apply themselves.
mod exif;
pub mod fault;
/// The B5-J JPEG admission profile ([`media`]'s steps 4–5) — private: the only supported way in
/// is `media::decode_image`, so no caller can reach a decoder past the profile.
mod jpeg;
pub mod media;
pub mod raster;
pub mod scene;

pub use engine::{Engine, EngineCommand, EngineEvent, IPC_VERSION};
pub use fault::Fault;
#[allow(deprecated)]
pub use media::decode_png;
pub use media::{
    decode_image, probe_image, sniff, DecodeError, DecodeLimits, DecodedImage, ImageFormat,
    ImageInfo,
};
pub use raster::{render, Fit, FrameBuffer};
pub use scene::{
    Frame, GradientDirection, ImageFit, Layer, MediaRef, Rect, Rgba, ShapeKind, TextAlign,
    TextStyle,
};
