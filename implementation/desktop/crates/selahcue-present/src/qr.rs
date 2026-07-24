//! QR rendering for the pairing invite (FR-086): encode the `selahcue://pair?...`
//! URI as a scannable code composed into an engine [`Frame`] (shown on the
//! stage/confidence output while pairing mode is active) or as module data for a
//! terminal fallback.

use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};

/// Quiet-zone width in modules on every side (the QR spec requires 4).
const QUIET_MODULES: u32 = 4;

/// Encode `data` into its QR module matrix: `(side_len, modules)` where `modules`
/// is row-major `side_len × side_len`, `true` = dark. `None` if the data cannot be
/// encoded (e.g. too long). Used for terminal/ASCII rendering.
pub fn qr_modules(data: &str) -> Option<(usize, Vec<bool>)> {
    let code = qrcode::QrCode::new(data.as_bytes()).ok()?;
    let side = code.width();
    let modules = code
        .to_colors()
        .into_iter()
        .map(|c| c == qrcode::Color::Dark)
        .collect();
    Some((side, modules))
}

/// Compose `data` as a QR code centred in a `width×height` frame: white background,
/// black modules, spec quiet zone, integer module scale (crisp for a camera). `None`
/// if the data cannot be encoded.
pub fn compose_qr(data: &str, width: u32, height: u32) -> Option<Frame> {
    let (side, modules) = qr_modules(data)?;
    let mut frame = Frame::new(width, height).with_background(Rgba::WHITE);
    if width == 0 || height == 0 {
        return Some(frame);
    }
    let total = side as u32 + 2 * QUIET_MODULES;
    let scale = (width.min(height) / total).max(1);
    let rendered = total * scale;
    // Centre; a frame smaller than one module per side still renders (clipped).
    let ox = (width.saturating_sub(rendered) / 2) as i32 + (QUIET_MODULES * scale) as i32;
    let oy = (height.saturating_sub(rendered) / 2) as i32 + (QUIET_MODULES * scale) as i32;
    for y in 0..side {
        for x in 0..side {
            if modules[y * side + x] {
                frame.push(Layer::Fill {
                    rect: Rect::new(
                        ox + (x as u32 * scale) as i32,
                        oy + (y as u32 * scale) as i32,
                        scale,
                        scale,
                    ),
                    color: Rgba::BLACK,
                });
            }
        }
    }
    Some(frame)
}
