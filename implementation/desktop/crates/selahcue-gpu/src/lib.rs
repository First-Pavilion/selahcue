//! SelahCue wgpu compositor (ADR-0002).
//!
//! Renders the [`selahcue_engine`] scene model on the GPU. The offscreen
//! [`Compositor::render_to_pixels`] path renders to a texture and reads pixels back,
//! so it can be compared against the CPU rasterizer for cross-backend parity
//! (ADR-0015; `selahcue_engine::analysis::ssim`). The same pipeline drives an
//! on-screen surface in the desktop shell (a subsequent, display-only batch).

#![forbid(unsafe_code)]

mod compositor;

pub use compositor::Compositor;

/// Whether a usable GPU adapter is available in this environment (so callers can
/// skip the offscreen path where there is no GPU).
pub fn adapter_available() -> bool {
    let instance = wgpu::Instance::default();
    pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).is_some()
}

/// A short description of the first adapter, if any (for diagnostics).
pub fn adapter_info() -> Option<String> {
    let instance = wgpu::Instance::default();
    let adapter =
        pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default()))?;
    let info = adapter.get_info();
    Some(format!("{:?} {} ({:?})", info.backend, info.name, info.device_type))
}
