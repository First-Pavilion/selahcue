//! The presentation slide model and output theme.

use selahcue_engine::scene::Rgba;
use serde::{Deserialize, Serialize};

/// A basic static slide: a title and zero or more body lines rendered over the
/// theme background (FR-009). Richer content (media, columns) extends this later.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Slide {
    pub title: String,
    pub body: Vec<String>,
}

impl Slide {
    /// A slide with a title and no body lines.
    pub fn title(title: impl Into<String>) -> Self {
        Slide {
            title: title.into(),
            body: Vec::new(),
        }
    }

    /// A slide with a title and body lines.
    pub fn new(
        title: impl Into<String>,
        body: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        Slide {
            title: title.into(),
            body: body.into_iter().map(Into::into).collect(),
        }
    }

    /// Every text line, title first.
    pub fn lines(&self) -> impl Iterator<Item = &str> {
        std::iter::once(self.title.as_str()).chain(self.body.iter().map(String::as_str))
    }

    /// True if the slide has no visible text (renders as background only).
    pub fn is_blank(&self) -> bool {
        self.title.trim().is_empty() && self.body.iter().all(|l| l.trim().is_empty())
    }
}

/// The audience-output theme (background, text colour, safe-area inset).
///
/// This is the *program/audience* look — not the operator's green/red preview/live
/// chrome, which is UI decoration on the operator's monitors.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Theme {
    pub background: Rgba,
    pub text: Rgba,
    /// Safe-area inset as a fraction of each dimension (0.0..0.5), keeping text
    /// off screen edges for overscan/framing.
    pub safe_margin_permille: u16,
}

impl Theme {
    /// A dark theme (near-black background, white text) — the common worship default.
    pub fn dark() -> Self {
        Theme {
            background: Rgba::rgb(8, 10, 20),
            text: Rgba::WHITE,
            safe_margin_permille: 50, // 5%
        }
    }

    /// Safe margin as a fraction (clamped to a sane range).
    pub fn safe_margin(&self) -> f64 {
        (self.safe_margin_permille as f64 / 1000.0).clamp(0.0, 0.4)
    }
}

impl Default for Theme {
    fn default() -> Self {
        Theme::dark()
    }
}
