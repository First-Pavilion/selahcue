//! Engine command→event behaviour, the never-blank invariant, IPC serde, and a
//! bounded-state (no-leak) guard.

#![allow(clippy::unwrap_used)]

use selahcue_engine::engine::{Engine, EngineCommand, EngineEvent, IPC_VERSION};
use selahcue_engine::fault::Fault;
use selahcue_engine::scene::{Frame, Rgba};

fn solid(n: u32, color: Rgba) -> Frame {
    Frame::new(n, n).with_background(color)
}

#[test]
fn command_event_sequence() {
    let mut e = Engine::new(8, 8);
    assert_eq!(
        e.apply(EngineCommand::SetScene {
            frame: solid(8, Rgba::WHITE)
        }),
        EngineEvent::FrameRendered { seq: 1 }
    );
    assert_eq!(
        e.apply(EngineCommand::InjectFault {
            fault: Fault::GpuDeviceLost
        }),
        EngineEvent::OutputHeld {
            fault: Fault::GpuDeviceLost
        }
    );
    assert_eq!(
        e.apply(EngineCommand::SetScene {
            frame: solid(8, Rgba::rgb(1, 2, 3))
        }),
        EngineEvent::Recovered { seq: 2 }
    );
    assert_eq!(
        e.apply(EngineCommand::Capture),
        EngineEvent::Captured { seq: 2 }
    );
    assert_eq!(
        e.apply(EngineCommand::Blackout { on: true }),
        EngineEvent::FrameRendered { seq: 3 }
    );
    assert_eq!(
        e.apply(EngineCommand::Clear),
        EngineEvent::FrameRendered { seq: 4 }
    );
}

#[test]
fn blackout_output_is_all_black() {
    let mut e = Engine::new(4, 4);
    e.apply(EngineCommand::SetScene {
        frame: solid(4, Rgba::WHITE),
    });
    e.apply(EngineCommand::Blackout { on: true });
    for y in 0..4 {
        for x in 0..4 {
            assert_eq!(e.output().pixel(x, y).unwrap(), Rgba::BLACK);
        }
    }
}

#[test]
fn output_never_blanks_across_a_fault() {
    let mut e = Engine::new(4, 4);
    e.apply(EngineCommand::SetScene {
        frame: solid(4, Rgba::WHITE),
    });
    e.apply(EngineCommand::InjectFault {
        fault: Fault::DiskFull,
    });
    // Still white (held) — a fault must never blank the live output.
    assert_eq!(e.output().pixel(0, 0).unwrap(), Rgba::WHITE);
}

#[test]
fn ipc_commands_and_events_round_trip() {
    assert_eq!(IPC_VERSION, 1);
    let commands = vec![
        EngineCommand::SetScene {
            frame: solid(2, Rgba::rgb(9, 9, 9)),
        },
        EngineCommand::Blackout { on: false },
        EngineCommand::Clear,
        EngineCommand::InjectFault {
            fault: Fault::IpcStall,
        },
        EngineCommand::Capture,
    ];
    for c in commands {
        let json = serde_json::to_string(&c).unwrap();
        let back: EngineCommand = serde_json::from_str(&json).unwrap();
        assert_eq!(back, c, "command round-trip failed for {json}");
    }
    let events = vec![
        EngineEvent::FrameRendered { seq: 1 },
        EngineEvent::OutputHeld {
            fault: Fault::GpuDeviceLost,
        },
        EngineEvent::Recovered { seq: 2 },
        EngineEvent::Captured { seq: 2 },
        EngineEvent::Rejected {
            reason: "bad".into(),
        },
    ];
    for ev in events {
        let json = serde_json::to_string(&ev).unwrap();
        let back: EngineEvent = serde_json::from_str(&json).unwrap();
        assert_eq!(back, ev, "event round-trip failed for {json}");
    }
}

#[test]
fn oversized_frame_is_rejected_and_output_is_held() {
    let mut e = Engine::new(16, 16);
    e.apply(EngineCommand::SetScene {
        frame: solid(16, Rgba::WHITE),
    });
    let good = e.output().bytes().to_vec();
    // A pathological resolution must not crash the engine — it is rejected and the
    // live output holds its last good frame (never-blank, NFR-024).
    let event = e.apply(EngineCommand::SetScene {
        frame: Frame::new(100_000, 100_000),
    });
    assert!(matches!(event, EngineEvent::Rejected { .. }));
    assert_eq!(
        e.output().bytes(),
        good.as_slice(),
        "a rejected command changed the output"
    );
    assert_eq!(e.output().pixel(0, 0).unwrap(), Rgba::WHITE);
}

#[test]
fn extreme_engine_dimensions_do_not_panic() {
    // Zero clamps up to 1×1; oversized clamps down to MAX_DIMENSION — never a panic
    // or unbounded allocation.
    assert!(Engine::new(0, 0).output().byte_len() > 0);
    assert!(Engine::new(20_000, 4).output().byte_len() > 0);
}

#[test]
fn engine_state_is_bounded_over_many_commands() {
    // No-leak guard: processing thousands of frames must not grow retained state.
    // The engine holds exactly one output buffer (O(1)) — never a frame history.
    let mut e = Engine::new(32, 32);
    let expected_bytes = e.output().byte_len();
    for i in 0..5000u32 {
        let c = (i & 0xff) as u8;
        e.apply(EngineCommand::SetScene {
            frame: solid(32, Rgba::rgb(c, c, c)),
        });
    }
    assert_eq!(
        e.output().byte_len(),
        expected_bytes,
        "output buffer size changed / grew"
    );
    assert_eq!(e.seq(), 5000);
}
