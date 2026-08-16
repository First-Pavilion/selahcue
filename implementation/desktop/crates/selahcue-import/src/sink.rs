//! The write seam: stage validated image bytes, get a slot back.
//!
//! Two properties of the ordering here are load-bearing.
//!
//! **The bytes handed to a sink have already passed the signature allowlist and a bounded decode
//! probe.** The decoder takes a byte slice and does no I/O, so this pure crate can fully validate
//! an image before the shell ever writes one. *No rejected image is ever staged, so there is no
//! cleanup path to get wrong.*
//!
//! **Images are staged one at a time, never collected.** Holding every extracted image before
//! staging any would be up to two hundred times sixteen mebibytes of arena. The callback shape
//! exists precisely so that arena is never built.

use crate::error::StoreError;
use crate::model::MediaSlot;

/// What the decode probe learned about an image. The dimensions are a real gain beyond
/// validation: they populate the `width`/`height` columns that the existing image-import path
/// leaves `None`. They are **post-orientation** dimensions, which is what both the per-mille rect
/// and the media row want.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ImageProbe {
    pub width: u32,
    pub height: u32,
    pub byte_len: usize,
    pub format: selahcue_engine::ImageFormat,
}

/// Stage validated image bytes somewhere the shell owns.
pub trait MediaSink {
    /// Write `bytes` and return the slot they landed in. Nothing is visible to the media library
    /// or the deck library yet.
    ///
    /// The **original encoded bytes** are staged, not the decoded pixels: the store should hold
    /// the file the user's deck contained, and for a JPEG that includes its orientation tag —
    /// only the decoded pixels are rotated, because re-encoding would be lossy and pointless.
    fn stage(&mut self, bytes: &[u8], probe: &ImageProbe) -> Result<MediaSlot, StoreError>;
}

/// A recording sink for tests: it keeps what it was asked to stage so a test can assert both the
/// bytes and the probe, and can be told to start failing at a chosen point to exercise the
/// partial-media path.
#[derive(Debug, Default)]
pub struct RecordingSink {
    staged: Vec<(Vec<u8>, ImageProbe)>,
    /// Fail every `stage` from this index onward, simulating a disk filling mid-import.
    pub fail_from: Option<usize>,
}

impl RecordingSink {
    pub fn new() -> Self {
        Self::default()
    }

    /// Fail every stage call from `index` onward.
    pub fn failing_from(index: usize) -> Self {
        RecordingSink {
            staged: Vec::new(),
            fail_from: Some(index),
        }
    }

    pub fn staged(&self) -> &[(Vec<u8>, ImageProbe)] {
        &self.staged
    }

    pub fn len(&self) -> usize {
        self.staged.len()
    }

    pub fn is_empty(&self) -> bool {
        self.staged.is_empty()
    }
}

impl MediaSink for RecordingSink {
    fn stage(&mut self, bytes: &[u8], probe: &ImageProbe) -> Result<MediaSlot, StoreError> {
        if self.fail_from.is_some_and(|n| self.staged.len() >= n) {
            return Err(StoreError::WriteFailed);
        }
        let slot = MediaSlot(self.staged.len() as u32);
        self.staged.push((bytes.to_vec(), *probe));
        Ok(slot)
    }
}

/// A sink that refuses everything — for asserting that a staging failure degrades to a text-only
/// deck plus an honest report, rather than to a failed import.
#[derive(Debug, Default)]
pub struct RefusingSink;

impl MediaSink for RefusingSink {
    fn stage(&mut self, _bytes: &[u8], _probe: &ImageProbe) -> Result<MediaSlot, StoreError> {
        Err(StoreError::LibraryFull)
    }
}
