//! Fault-injection matrix — output-failure isolation (NFR-024, FR-160).

#![allow(clippy::unwrap_used)]

use selahcue_engine::engine::{Engine, EngineCommand, EngineEvent};
use selahcue_engine::fault::Fault;
use selahcue_engine::scene::{Frame, Rgba};

fn solid(n: u32, color: Rgba) -> Frame {
    Frame::new(n, n).with_background(color)
}

#[test]
fn fault_holds_last_good_frame_not_blank() {
    let mut engine = Engine::new(16, 16);
    engine.apply(EngineCommand::SetScene {
        frame: solid(16, Rgba::rgb(0, 0, 255)),
    });
    let good = engine.output().bytes().to_vec();
    assert_eq!(engine.output().pixel(8, 8).unwrap(), Rgba::rgb(0, 0, 255));

    let event = engine.apply(EngineCommand::InjectFault {
        fault: Fault::GpuDeviceLost,
    });
    assert_eq!(
        event,
        EngineEvent::OutputHeld {
            fault: Fault::GpuDeviceLost
        }
    );
    assert!(engine.is_faulted());
    // The output is HELD — identical to the last good frame, never blanked.
    assert_eq!(engine.output().bytes(), good.as_slice());
    assert_eq!(engine.output().pixel(8, 8).unwrap(), Rgba::rgb(0, 0, 255));
}

#[test]
fn recovers_on_the_next_good_render() {
    let mut engine = Engine::new(16, 16);
    engine.apply(EngineCommand::SetScene {
        frame: solid(16, Rgba::rgb(0, 0, 255)),
    });
    engine.apply(EngineCommand::InjectFault {
        fault: Fault::DecoderFault,
    });
    let event = engine.apply(EngineCommand::SetScene {
        frame: solid(16, Rgba::rgb(0, 255, 0)),
    });
    assert!(matches!(event, EngineEvent::Recovered { .. }));
    assert!(!engine.is_faulted());
    assert_eq!(engine.output().pixel(1, 1).unwrap(), Rgba::rgb(0, 255, 0));
}

#[test]
fn every_fault_kind_holds_the_output() {
    for fault in Fault::ALL {
        let mut engine = Engine::new(8, 8);
        engine.apply(EngineCommand::SetScene {
            frame: solid(8, Rgba::rgb(200, 100, 50)),
        });
        let good = engine.output().bytes().to_vec();
        let event = engine.apply(EngineCommand::InjectFault { fault });
        assert_eq!(event, EngineEvent::OutputHeld { fault });
        assert_eq!(
            engine.output().bytes(),
            good.as_slice(),
            "{fault:?} blanked the output"
        );
    }
}

#[test]
fn a_fault_on_one_output_does_not_affect_another() {
    let mut a = Engine::new(8, 8);
    let mut b = Engine::new(8, 8);
    a.apply(EngineCommand::SetScene {
        frame: solid(8, Rgba::rgb(255, 0, 0)),
    });
    b.apply(EngineCommand::SetScene {
        frame: solid(8, Rgba::rgb(0, 255, 0)),
    });
    a.apply(EngineCommand::InjectFault {
        fault: Fault::IpcStall,
    });
    // Output B is entirely unaffected by A's fault.
    assert!(!b.is_faulted());
    assert_eq!(b.output().pixel(0, 0).unwrap(), Rgba::rgb(0, 255, 0));
}
