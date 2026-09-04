//! The `TranscriptProvider` implementation: honest labelling, ordered draining, and the
//! non-blocking guarantee.

#![allow(clippy::unwrap_used)]

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use selahcue_core::transcript::{ManualProvider, ProviderSegment, TranscriptProvider};
use selahcue_stt_cloud::{
    CloudTranscriptProvider, SegmentQueue, SessionState, SessionStatus, StreamParams,
    DEEPGRAM_LABEL, DEGRADED_FALLBACK_NOTICE,
};

fn seg(text: &str) -> ProviderSegment {
    ProviderSegment::final_text(text, 0, 500)
}

/// A poll must be an in-memory drain. This is generous by two orders of magnitude against
/// what a mutex hand-off costs, because the claim being tested is "it does not wait for the
/// network", not "it is fast".
const POLL_CEILING: Duration = Duration::from_millis(250);

#[test]
fn poll_drains_in_order_then_empties() {
    let queue = SegmentQueue::new();
    queue.push(seg("first"));
    queue.push(seg("second"));

    let mut provider = CloudTranscriptProvider::with_label(queue, "deepgram-test");
    let out = provider.poll();

    assert_eq!(
        out.iter().map(|s| s.text.as_str()).collect::<Vec<_>>(),
        ["first", "second"],
        "segments came out in the wrong order; a transcript panel would render the sermon \
         scrambled"
    );
    assert!(provider.poll().is_empty(), "poll returned segments twice");
}

#[test]
fn poll_returns_promptly_while_the_socket_is_still_streaming() {
    // The claim is architectural, not about speed: the render path never waits on AI (FR-083
    // / NFR-024), so a poll must return while the producer is *still producing*. The
    // structural half of that — "the stream was still open when poll returned" — is asserted
    // directly; wall-clock is only a ceiling, so a loaded CI machine cannot fail this for the
    // wrong reason.
    let queue = SegmentQueue::new();
    let producer_queue = queue.clone();
    let stop = Arc::new(AtomicBool::new(false));
    let producer_stop = Arc::clone(&stop);

    let producer = thread::spawn(move || {
        let mut pushed: u64 = 0;
        while !producer_stop.load(Ordering::Relaxed) {
            producer_queue.push(seg(&format!("word-{pushed}")));
            pushed = pushed.wrapping_add(1);
            thread::yield_now();
        }
        pushed
    });

    let mut provider = CloudTranscriptProvider::with_label(queue, "deepgram-test");
    let mut drained_mid_stream = 0usize;
    let mut worst = Duration::ZERO;

    // Poll until the live producer has actually given us something, so what is measured is a
    // poll against a live stream rather than against a static queue.
    let deadline = Instant::now() + Duration::from_secs(5);
    while drained_mid_stream == 0 && Instant::now() < deadline {
        let started = Instant::now();
        let batch = provider.poll();
        worst = worst.max(started.elapsed());
        drained_mid_stream += batch.len();
    }
    for _ in 0..20 {
        let started = Instant::now();
        let batch = provider.poll();
        worst = worst.max(started.elapsed());
        drained_mid_stream += batch.len();
    }

    // Exercised before contract, twice over.
    assert!(
        !stop.load(Ordering::Relaxed),
        "the producer was already stopped, so these polls did not run against a live stream"
    );
    assert!(
        drained_mid_stream > 0,
        "no poll drained anything while the producer was running, so this test never observed \
         a poll against a live stream and the latency ceiling below proves nothing"
    );

    stop.store(true, Ordering::Relaxed);
    let pushed = producer.join().unwrap_or(0);
    assert!(pushed > 0, "the producer thread never pushed anything");

    assert!(
        worst < POLL_CEILING,
        "a poll took {worst:?} while the socket was mid-stream (ceiling {POLL_CEILING:?}); \
         the render path must never wait on AI"
    );
}

#[test]
fn the_label_names_deepgram_and_is_distinguishable_from_the_on_device_engine() {
    let provider = CloudTranscriptProvider::new(SegmentQueue::new(), &StreamParams::default());

    assert_eq!(provider.label(), DEEPGRAM_LABEL);
    assert_eq!(
        provider.label(),
        "deepgram-nova-3",
        "the disclosed label changed; FR-120 requires the console to name the engine honestly"
    );
    // The on-device engine labels itself `whisper-<model>` (selahcue-stt/src/recognizer.rs);
    // the always-present default labels itself "manual".
    assert!(
        !provider.label().starts_with("whisper-"),
        "the cloud engine is claiming the on-device engine's label"
    );
    assert_ne!(
        provider.label(),
        ManualProvider::new().label(),
        "the cloud engine is indistinguishable from the manual default"
    );
}

#[test]
fn the_label_tracks_the_model_actually_requested() {
    let params = StreamParams {
        model: "nova-2".to_string(),
        ..StreamParams::default()
    };
    let provider = CloudTranscriptProvider::new(SegmentQueue::new(), &params);
    assert_eq!(
        provider.label(),
        "deepgram-nova-2",
        "the label is hardcoded rather than derived from the model on the wire, so the console \
         would disclose a model that is not the one transcribing"
    );
}

#[test]
fn session_state_distinguishes_retrying_from_stopped_for_good() {
    // The console needs this distinction to choose between "reconnecting…" and an actionable
    // message. Collapsing them leaves an operator watching a spinner that will never resolve.
    let reconnecting = SessionState::Reconnecting { attempt: 2, of: 5 };
    assert!(
        !reconnecting.is_terminal(),
        "a retry was reported as terminal"
    );
    assert!(!reconnecting.is_streaming());

    assert!(SessionState::Stopped.is_terminal());
    assert!(SessionState::Failed {
        action: selahcue_stt_cloud::OperatorAction::CheckNetwork,
        message: "gave up".to_string(),
    }
    .is_terminal());

    assert!(SessionState::Streaming.is_streaming());
    assert!(!SessionState::Connecting.is_terminal());
    assert_eq!(SessionState::default(), SessionState::Idle);
}

#[test]
fn session_status_is_shared_and_holds_exactly_one_state() {
    let status = SessionStatus::new();
    let observer = status.clone();
    assert_eq!(observer.get(), SessionState::Idle);

    status.set(SessionState::Streaming);
    assert_eq!(
        observer.get(),
        SessionState::Streaming,
        "a clone did not observe the update, so the console would never see the session change"
    );

    // Replaced, not accumulated: polling this at 1 Hz for three hours must retain nothing.
    for attempt in 0..1_000 {
        status.set(SessionState::Reconnecting { attempt, of: 5 });
    }
    assert_eq!(
        observer.get(),
        SessionState::Reconnecting {
            attempt: 999,
            of: 5
        },
        "the status is not a single replaced cell"
    );
}

#[test]
fn the_degraded_fallback_notice_names_both_the_cause_and_the_consequence() {
    // The operator asked for cloud transcription and is getting something else. A notice that
    // says only "cloud transcription failed" leaves them wondering whether the panel is dead;
    // one that says only "using on-device" hides that anything went wrong. Both halves, or it
    // misleads.
    assert!(
        DEGRADED_FALLBACK_NOTICE.contains("Cloud transcription could not be reached"),
        "the notice does not name the cause: {DEGRADED_FALLBACK_NOTICE}"
    );
    assert!(
        DEGRADED_FALLBACK_NOTICE.contains("on-device"),
        "the notice does not say where the transcript is now coming from: \
         {DEGRADED_FALLBACK_NOTICE}"
    );
    assert!(
        !DEGRADED_FALLBACK_NOTICE.contains("  "),
        "the notice has a double space from a line continuation: {DEGRADED_FALLBACK_NOTICE}"
    );
}
