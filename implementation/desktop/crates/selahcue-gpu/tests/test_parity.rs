//! Cross-backend parity (ADR-0015): the wgpu compositor must render the same scene
//! as the CPU rasterizer to SSIM ≥ 0.99. Skips gracefully where no GPU is present.

#![allow(clippy::unwrap_used)]

use selahcue_engine::analysis::ssim;
use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};
use selahcue_gpu::Compositor;

fn scenes() -> Vec<Frame> {
    let mut solid = Frame::new(320, 180).with_background(Rgba::rgb(20, 40, 120));

    let mut rects = Frame::new(320, 180).with_background(Rgba::rgb(8, 10, 20));
    rects.push(Layer::Fill {
        rect: Rect::new(20, 20, 120, 40),
        color: Rgba::WHITE,
    });
    rects.push(Layer::Fill {
        rect: Rect::new(60, 80, 200, 60),
        color: Rgba::rgb(31, 176, 122),
    });

    let mut overlap = Frame::new(256, 256).with_background(Rgba::rgb(40, 40, 40));
    overlap.push(Layer::Fill {
        rect: Rect::new(30, 30, 150, 150),
        color: Rgba::rgb(224, 32, 32),
    });
    overlap.push(Layer::Fill {
        rect: Rect::new(90, 90, 150, 150),
        color: Rgba::rgb(32, 32, 224),
    });

    let mut blackout = Frame::new(128, 72).with_background(Rgba::WHITE);
    blackout.push(Layer::Fill {
        rect: Rect::new(0, 0, 128, 72),
        color: Rgba::WHITE,
    });
    blackout.blackout = true;

    // A solid slide-like frame is where the parity oracle matters most.
    solid.push(Layer::Fill {
        rect: Rect::new(16, 16, 288, 24),
        color: Rgba::WHITE,
    });

    // Translucent overlay — forces the GPU alpha-blend path and the CPU src-over
    // blend to actually mix (a blend/premultiplication/sRGB regression would break).
    let mut translucent = Frame::new(320, 180).with_background(Rgba::rgb(20, 40, 120));
    translucent.push(Layer::Fill {
        rect: Rect::new(40, 40, 200, 90),
        color: Rgba::new(224, 32, 32, 128),
    });

    // A width that is NOT a multiple of 64 (300×4 = 1200 → padded to 1280), so the
    // 256-byte readback row-padding strip is exercised for real.
    let mut padded = Frame::new(300, 130).with_background(Rgba::rgb(10, 60, 90));
    padded.push(Layer::Fill {
        rect: Rect::new(20, 20, 120, 40),
        color: Rgba::WHITE,
    });
    padded.push(Layer::Fill {
        rect: Rect::new(60, 70, 180, 40),
        color: Rgba::rgb(31, 176, 122),
    });

    vec![solid, rects, overlap, blackout, translucent, padded]
}

#[test]
fn wgpu_matches_cpu_rasterizer_to_ssim_0_99() {
    let Some(compositor) = Compositor::new() else {
        eprintln!("no GPU adapter — skipping wgpu parity (compile-only in this environment)");
        return;
    };

    for frame in scenes() {
        let cpu = render(&frame);
        let gpu_pixels = compositor.render_to_pixels(&frame);
        let gpu = FrameBuffer::from_rgba(frame.width, frame.height, gpu_pixels).unwrap();
        let score = ssim(&cpu, &gpu);
        assert!(
            score >= 0.99,
            "wgpu↔CPU SSIM {score:.4} < 0.99 for a {}×{} frame",
            frame.width,
            frame.height
        );
    }
}
