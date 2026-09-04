//! The bounded audio ring the capture side fills and the socket drains.
//!
//! The outbound direction has the same unbounded-growth shape as the inbound one, and it is
//! the easier of the two to overlook. A microphone callback runs on the audio thread and does
//! not stop when the network does: if the socket is reconnecting, or slow, or gone, whatever
//! it was draining keeps filling. Sixteen-kilohertz mono PCM is 32 KB per second, so an
//! unbounded buffer during a five-minute outage is roughly ten megabytes of audio nobody will
//! ever want.
//!
//! # Two bounds, and a per-chunk one
//!
//! - [`MAX_QUEUED_AUDIO_CHUNKS`] bounds the **chunk count**.
//! - [`MAX_QUEUED_AUDIO_BYTES`] bounds the **retained PCM bytes** — about sixteen seconds at
//!   16 kHz mono.
//! - [`MAX_AUDIO_CHUNK_BYTES`] bounds a **single** chunk, and one larger than that is refused
//!   rather than queued. A capture callback producing a two-second buffer is already wrong;
//!   admitting it would let one chunk own most of the byte budget.
//!
//! As with the segment queue, the two ring bounds are pinned at compile time to be
//! independently reachable, so neither bounded-memory test can be quietly made vacuous by a
//! later edit to a constant.
//!
//! # Drop policy: oldest first
//!
//! Stale audio is worse than absent. Sending a backlog after a reconnection produces a
//! transcript permanently running minutes behind the preacher, which is a worse failure than
//! a gap — so the ring drops the **oldest** audio and stays current.

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

/// Upper bound on **chunks** buffered between capture and the socket.
pub const MAX_QUEUED_AUDIO_CHUNKS: usize = 128;

/// Upper bound on **retained PCM bytes** buffered between capture and the socket
/// (≈16 s at 16 kHz mono 16-bit).
pub const MAX_QUEUED_AUDIO_BYTES: usize = 512 * 1024;

/// Upper bound on a **single** chunk (≈2 s at 16 kHz mono 16-bit). Larger is refused.
pub const MAX_AUDIO_CHUNK_BYTES: usize = 64 * 1024;

// --- The premise both bounded-memory tests rest on, pinned at compile time -----------------

const _: () = assert!(
    MAX_QUEUED_AUDIO_CHUNKS * MAX_AUDIO_CHUNK_BYTES > MAX_QUEUED_AUDIO_BYTES,
    "the byte budget must be reachable before the chunk budget for maximum-size chunks; \
     otherwise the byte bound can never bite and its bounded-memory test is vacuous"
);

const _: () = assert!(
    MAX_QUEUED_AUDIO_BYTES > MAX_QUEUED_AUDIO_CHUNKS * 2,
    "the chunk budget must be reachable before the byte budget for minimal (one-sample) \
     chunks; otherwise the chunk bound can never bite and its bounded-memory test is vacuous"
);

const _: () = assert!(
    MAX_QUEUED_AUDIO_CHUNKS > 1,
    "a cap of one makes 'the oldest is dropped, the newest is kept' unstateable"
);

/// One buffer of PCM audio, already in the encoding Deepgram is told to expect:
/// **signed 16-bit little-endian** ([`crate::session::Encoding::Linear16`]).
///
/// Encoding at the boundary rather than at send time means the ring's byte accounting is the
/// number of bytes that will actually go on the wire, not an estimate of it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AudioChunk {
    bytes: Vec<u8>,
}

impl AudioChunk {
    /// Encode 16-bit samples as little-endian PCM.
    pub fn from_pcm_i16(samples: &[i16]) -> Self {
        let mut bytes = Vec::with_capacity(samples.len() * 2);
        for s in samples {
            bytes.extend_from_slice(&s.to_le_bytes());
        }
        AudioChunk { bytes }
    }

    /// Wrap bytes that are already PCM signed-16-bit little-endian.
    pub fn from_pcm_bytes(bytes: Vec<u8>) -> Self {
        AudioChunk { bytes }
    }

    /// The bytes to put on the wire.
    pub fn as_bytes(&self) -> &[u8] {
        &self.bytes
    }

    /// Size on the wire.
    pub fn len(&self) -> usize {
        self.bytes.len()
    }

    /// Whether this chunk carries no audio.
    pub fn is_empty(&self) -> bool {
        self.bytes.is_empty()
    }
}

#[derive(Debug, Default)]
struct Inner {
    chunks: VecDeque<AudioChunk>,
    retained_bytes: usize,
    admitted: u64,
    dropped_for_bound: u64,
    refused_oversize: u64,
}

impl Inner {
    /// **The** bound predicate — one expression, consumed by the drop loop and by the tests.
    /// See the equivalent note in [`crate::queue`] for why it has exactly one definition.
    fn is_within_bounds(&self) -> bool {
        self.chunks.len() <= MAX_QUEUED_AUDIO_CHUNKS
            && self.retained_bytes <= MAX_QUEUED_AUDIO_BYTES
    }
}

/// A bounded, cloneable, thread-safe ring of captured audio. The capture thread pushes; the
/// socket thread drains. Clones share one ring.
#[derive(Debug, Clone, Default)]
pub struct AudioRing {
    inner: Arc<Mutex<Inner>>,
}

impl AudioRing {
    /// An empty ring.
    pub fn new() -> Self {
        AudioRing::default()
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, Inner> {
        self.inner.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Offer a chunk to the ring.
    ///
    /// An empty chunk is ignored. A chunk larger than [`MAX_AUDIO_CHUNK_BYTES`] is **refused**
    /// — counted in [`AudioRing::refused_oversize`] and never queued — so a single oversized
    /// buffer cannot own the byte budget. Otherwise the oldest chunks are dropped until the
    /// ring is within bounds again.
    ///
    /// Never blocks beyond the ring's own lock: an audio callback that blocks is a glitch on
    /// the machine's audio output, which in a service is audible to the congregation.
    pub fn push(&self, chunk: AudioChunk) {
        let mut inner = self.lock();
        if chunk.is_empty() {
            return;
        }
        if chunk.len() > MAX_AUDIO_CHUNK_BYTES {
            inner.refused_oversize = inner.refused_oversize.saturating_add(1);
            return;
        }
        inner.retained_bytes = inner.retained_bytes.saturating_add(chunk.len());
        inner.chunks.push_back(chunk);
        inner.admitted = inner.admitted.saturating_add(1);
        while !inner.is_within_bounds() {
            match inner.chunks.pop_front() {
                Some(dropped) => {
                    inner.retained_bytes = inner.retained_bytes.saturating_sub(dropped.len());
                    inner.dropped_for_bound = inner.dropped_for_bound.saturating_add(1);
                }
                None => break,
            }
        }
    }

    /// Take every buffered chunk in order, leaving the ring empty.
    pub fn drain(&self) -> Vec<AudioChunk> {
        let mut inner = self.lock();
        inner.retained_bytes = 0;
        inner.chunks.drain(..).collect()
    }

    /// Whether a chunk with exactly these bytes is retained **right now** — the per-entity
    /// accessor the bounded-memory tests assert on, rather than a count several different
    /// ring states could produce.
    pub fn retains_chunk(&self, chunk: &AudioChunk) -> bool {
        self.lock().chunks.iter().any(|c| c == chunk)
    }

    /// Number of buffered chunks (never exceeds [`MAX_QUEUED_AUDIO_CHUNKS`]).
    pub fn len(&self) -> usize {
        self.lock().chunks.len()
    }

    /// Whether the ring is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Retained PCM bytes (never exceeds [`MAX_QUEUED_AUDIO_BYTES`]).
    pub fn retained_bytes(&self) -> usize {
        self.lock().retained_bytes
    }

    /// The ring's own bound verdict — the same expression its drop loop consumes.
    pub fn is_within_bounds(&self) -> bool {
        self.lock().is_within_bounds()
    }

    /// How many chunks this ring has admitted since it was created (per-instance).
    pub fn admitted(&self) -> u64 {
        self.lock().admitted
    }

    /// How many chunks have been dropped to stay inside the bounds.
    pub fn dropped_for_bound(&self) -> u64 {
        self.lock().dropped_for_bound
    }

    /// How many chunks have been refused for exceeding [`MAX_AUDIO_CHUNK_BYTES`].
    pub fn refused_oversize(&self) -> u64 {
        self.lock().refused_oversize
    }
}

// Tests live in `tests/test_audio.rs` (public-API integration tests).
