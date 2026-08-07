//! Per-output NDI video delivery — the host sink that broadcasts a composed audience feed as
//! an NDI source (Screens page "NDI OUTPUT"). FEATURE-GATED behind `ndi`: the default build
//! links NO native NDI runtime (mirrors the `selahcue-stt` whisper/cpal precedent), so
//! `make ci` stays native-free. The NDI *setup* (name/enable, persisted + surfaced) works in
//! every build; only the actual transmission needs `--features ndi` + the NDI SDK/runtime.
//!
//! Design: a tiny object-safe [`VideoSink`] seam. [`NdiOutput::new`] returns `None` when NDI is
//! unavailable (feature off, or the runtime failed to init), so the host creates no sender and
//! never composes a frame for it — zero cost in the default build. When the `ndi` feature is
//! on, it wraps a real `grafton-ndi` sender (Apache-2.0; NDI SDK 6). SelahCue's RGBA8
//! `FrameBuffer` maps straight to NDIlib RGBA — no pixel conversion.

use selahcue_engine::raster::FrameBuffer;

/// Whether THIS build can actually transmit NDI on the network — i.e. the `ndi` feature is
/// compiled in and a native NDI runtime is linked. The default build is `false`: the NDI
/// *setup* (name/enable) still persists and surfaces, but no source is broadcast, so the host
/// (and, via it, the operator) can tell the difference between "configured" and "on air"
/// instead of silently pretending to broadcast. Build to transmit: `--features ndi`.
pub const TRANSMIT_AVAILABLE: bool = cfg!(feature = "ndi");

/// Receives composed RGBA frames for one output and delivers them (e.g. as an NDI source).
/// Object-safe so the host holds a `Box<dyn VideoSink>` per enabled output.
pub trait VideoSink {
    /// Deliver one composed frame. `rgba` is row-major RGBA8 (`w * h * 4` bytes).
    fn send_frame(&mut self, w: u32, h: u32, rgba: &[u8]);
}

/// One managed NDI output: the source name it broadcasts + its live sink. Dropping it closes
/// the underlying NDI source (RAII), which is how the host keeps the sender set bounded as
/// screens are disabled / deleted / renamed.
pub struct NdiOutput {
    name: String,
    sink: Box<dyn VideoSink>,
}

impl NdiOutput {
    /// The NDI source name this output broadcasts.
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Create an NDI output broadcasting `name` at `w×h` / `fps`, or `None` when NDI delivery
    /// is unavailable (the `ndi` feature is off, or the runtime/init failed). On `None` the host
    /// creates no sender and composes no frames for the screen.
    pub fn new(name: &str, w: u32, h: u32, fps: u16) -> Option<Self> {
        make_sink(name, w, h, fps).map(|sink| NdiOutput {
            name: name.to_string(),
            sink,
        })
    }

    /// Broadcast one composed frame.
    pub fn send(&mut self, fb: &FrameBuffer) {
        self.sink.send_frame(fb.width(), fb.height(), fb.bytes());
    }
}

#[cfg(feature = "ndi")]
fn make_sink(name: &str, w: u32, h: u32, fps: u16) -> Option<Box<dyn VideoSink>> {
    ndi_backend::NdiSink::new(name, w, h, fps).map(|s| Box::new(s) as Box<dyn VideoSink>)
}

#[cfg(not(feature = "ndi"))]
fn make_sink(_name: &str, _w: u32, _h: u32, _fps: u16) -> Option<Box<dyn VideoSink>> {
    // The `ndi` feature is off: no NDI runtime is linked, so there is no sink and the host
    // creates no sender (the config still persists + surfaces). Build with `--features ndi`
    // against the NDI SDK to broadcast for real.
    None
}

/// The real NDI backend (grafton-ndi 1.x → NDI SDK 6). Compiled ONLY under `--features ndi`,
/// so the default build never references the native runtime. Written against grafton-ndi's
/// documented 1.0 send API; a developer building the feature verifies it against the installed
/// SDK (same contract as the feature-gated STT whisper backend).
#[cfg(feature = "ndi")]
mod ndi_backend {
    use super::VideoSink;
    use grafton_ndi::{PixelFormat, Sender, SenderOptions, VideoFrame, NDI};

    /// A live NDI video source. SelahCue's RGBA8 frames go out as NDIlib RGBA (no conversion).
    /// The source closes when this is dropped (RAII).
    pub struct NdiSink {
        // Field order matters for drop order: the frame + sender drop before the NDI runtime.
        frame: VideoFrame,
        sender: Sender,
        _ndi: NDI,
        // Broadcast frame rate (numerator over 1), kept so a mid-stream resolution change can
        // rebuild the frame without silently dropping back to a default rate.
        fps: i32,
    }

    impl NdiSink {
        pub fn new(name: &str, w: u32, h: u32, fps: u16) -> Option<Self> {
            let ndi = NDI::new().ok()?;
            // `SenderOptions::builder(..).build()` returns the options by value (NOT a `Result`),
            // so it must not be `?`-unwrapped — doing so was a compile error that kept the whole
            // `ndi` feature from ever building, which is why an "enabled" NDI output never
            // appeared on the network.
            let opts = SenderOptions::builder(name).clock_video(true).build();
            let sender = Sender::new(&ndi, &opts).ok()?;
            let fps = fps.max(1) as i32;
            let frame = VideoFrame::builder()
                .resolution(w as i32, h as i32)
                .frame_rate(fps, 1)
                .pixel_format(PixelFormat::RGBA)
                .build()
                .ok()?;
            Some(NdiSink {
                frame,
                sender,
                _ndi: ndi,
                fps,
            })
        }
    }

    impl VideoSink for NdiSink {
        fn send_frame(&mut self, w: u32, h: u32, rgba: &[u8]) {
            // A resolution drift (rare) rebuilds the frame; a build failure keeps the old size
            // and simply skips this frame rather than panicking (never-blank discipline).
            if self.frame.width() != w as i32 || self.frame.height() != h as i32 {
                match VideoFrame::builder()
                    .resolution(w as i32, h as i32)
                    .frame_rate(self.fps, 1)
                    .pixel_format(PixelFormat::RGBA)
                    .build()
                {
                    Ok(f) => self.frame = f,
                    Err(_) => return,
                }
            }
            let dst = self.frame.data_mut();
            let n = dst.len().min(rgba.len());
            dst[..n].copy_from_slice(&rgba[..n]);
            self.sender.send_video(&self.frame);
        }
    }
}
