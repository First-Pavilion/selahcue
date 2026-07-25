//! The presentation slide model (content). The output *theme* (how content is
//! styled) lives in [`crate::theme`] — content is orthogonal to the theme.

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
