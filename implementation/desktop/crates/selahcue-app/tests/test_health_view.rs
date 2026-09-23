//! Output health end to end: a fault reported by the host must reach the operator view
//! and the wire, and must CHANGE what they say.
//!
//! This programme exists because of a field that had a setter, a source, three render
//! sites and no caller — present everywhere, observable nowhere. So these tests refuse to
//! assert on a hand-built view: each one drives the real producer
//! (`LiveController::report_fault`, the method the desktop host calls when its wgpu
//! surface is lost), reads the value back out of `operator_view()`, and serialises it
//! through the actual wire type.

#![allow(clippy::unwrap_used)]

use selahcue_app::LiveController;
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::{to_json, OperatorStateView, ServerMessage};
use selahcue_present::{Fault, Theme};

fn controller() -> LiveController {
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Song, "Closing Song");
    LiveController::new(plan, 320, 180, Theme::dark())
}

/// Put real content on Live, so a hold has a good frame to hold onto.
fn live_controller() -> LiveController {
    let mut c = controller();
    let id = c.plan().items()[0].id.0;
    c.apply(&selahcue_lan::protocol::Command::SelectItem { item_id: id });
    c.apply(&selahcue_lan::protocol::Command::GoLive);
    c
}

#[test]
fn a_healthy_host_reports_health_positively_rather_than_staying_silent() {
    let c = live_controller();
    let h = c
        .operator_view()
        .output_health
        .expect("a host that owns a compositor must always report health, even good news");
    assert!(!h.held);
    assert_eq!(h.fault, None);
    assert_eq!(h.holds, 0);
}

/// The end-to-end bar: drive the REAL producer, and prove the value reaches the view and
/// changes there. A test that built an `OutputHealthView` by hand would pass even if
/// nothing were wired together, which is precisely the defect being remediated.
#[test]
fn a_fault_reported_by_the_host_reaches_the_operator_view_and_changes_it() {
    let mut c = live_controller();
    let before = c.operator_view().output_health.unwrap();

    c.report_fault(Fault::GpuDeviceLost);

    let after = c.operator_view().output_health.unwrap();
    assert_ne!(
        after, before,
        "reporting a fault must CHANGE the view — an unchanged view means the seam is \
         wired at one end only"
    );
    assert!(after.held, "the view must report the output held");
    assert_eq!(
        after.fault.as_deref(),
        Some("gpu_device_lost"),
        "and must name the reason the operator has to act on"
    );
    assert_eq!(after.holds, 1);
}

#[test]
fn recovery_reaches_the_view_and_clears_the_reason() {
    let mut c = live_controller();
    c.report_fault(Fault::DecoderFault);
    assert!(c.operator_view().output_health.unwrap().held, "premise");

    // A successful compose recovers the output — no explicit "recover" call exists.
    let second = c.plan().items()[1].id.0;
    c.apply(&selahcue_lan::protocol::Command::SelectItem { item_id: second });
    c.apply(&selahcue_lan::protocol::Command::GoLive);

    let h = c.operator_view().output_health.unwrap();
    assert!(!h.held, "a good frame must clear the hold in the VIEW too");
    assert_eq!(
        h.fault, None,
        "a recovered output must not still name a fault"
    );
    assert_eq!(h.recoveries, 1, "and the recovery must be counted");
}

/// Health has to survive the trip the remote operator console actually makes:
/// `OperatorView` → `OperatorStateView` → JSON → back. A field that is populated locally
/// but dropped by the wire conversion would leave the remote console exactly as blind as
/// it is today.
#[test]
fn health_survives_the_round_trip_a_remote_console_makes() {
    let mut c = live_controller();
    c.report_fault(Fault::IpcStall);

    let wire: OperatorStateView = c.operator_view().into();
    let json = to_json(&ServerMessage::OperatorState { view: wire }).unwrap();
    assert!(
        json.contains(r#""output_health":{"held":true,"fault":"ipc_stall""#),
        "health must be on the wire in the pinned shape; got: {json}"
    );

    let parsed: ServerMessage = selahcue_lan::protocol::from_json(&json).unwrap();
    let ServerMessage::OperatorState { view } = parsed else {
        panic!("expected an operator_state frame");
    };
    let back: selahcue_app::OperatorView = view.into();
    let h = back
        .output_health
        .expect("health must survive the wire round trip, or the remote console stays blind");
    assert!(h.held);
    assert_eq!(h.fault.as_deref(), Some("ipc_stall"));
}

/// The acceptance bar restated on the wire: an unreported health ("this host cannot say")
/// and a reported-healthy output must NOT produce the same bytes. If they did, a client
/// could not tell a working output from one it simply has no news about — which is the
/// exact confusion that makes absent telemetry render as a hard fault today.
#[test]
fn unknown_health_and_healthy_health_are_different_on_the_wire() {
    let healthy: OperatorStateView = live_controller().operator_view().into();
    assert!(
        healthy.output_health.is_some(),
        "premise: this host reports"
    );

    let mut unknown = healthy.clone();
    unknown.output_health = None; // what an older host sends

    let healthy_json = to_json(&ServerMessage::OperatorState { view: healthy }).unwrap();
    let unknown_json = to_json(&ServerMessage::OperatorState { view: unknown }).unwrap();
    assert_ne!(
        healthy_json, unknown_json,
        "\"healthy\" and \"cannot say\" must be distinguishable on the wire"
    );
    assert!(healthy_json.contains("output_health"));
    assert!(
        !unknown_json.contains("output_health"),
        "an older host's frame must stay byte-identical to what it sends today"
    );
}

/// Every fault kind must arrive at the view as its own operator-facing reason. Collapsing
/// them would let a full disk and a lost GPU present the same recovery advice.
#[test]
fn every_fault_kind_reaches_the_view_with_its_own_reason() {
    let mut tags = Vec::new();
    for fault in Fault::ALL {
        let mut c = live_controller();
        c.report_fault(fault);
        let h = c.operator_view().output_health.unwrap();
        assert!(h.held, "{fault:?} must hold the output");
        tags.push(h.fault.expect("a held output must name its reason"));
    }
    let mut unique = tags.clone();
    unique.sort();
    unique.dedup();
    assert_eq!(
        unique.len(),
        tags.len(),
        "each fault kind needs its own reason string: {tags:?}"
    );
}

/// Pin the JSON the **webview** actually receives from `invoke("view")`.
///
/// `docs/delivery/HOST-SIGNAL-WEBVIEW-CONTRACT.md` tells the webview that on the Tauri path an
/// absent seam is `null` (key present) while on the wire path the key is omitted, and that the
/// health counters are skipped when zero. Those are two different encodings of the same
/// "unknown", and a consumer that assumes the wrong one silently misreads every seam — so the
/// claim is pinned here rather than left as prose someone has to trust.
#[test]
fn the_tauri_view_matches_the_shape_promised_to_the_webview() {
    let mut c = live_controller();
    let json = serde_json::to_string(&c.operator_view()).unwrap();

    // Healthy: `held` present and false, counters SKIPPED at zero.
    assert!(
        json.contains(r#""output_health":{"held":false}"#),
        "healthy shape must be exactly {{held:false}} — counters skip at zero; got: {json}"
    );

    // Seams this host does not report are `null` on the Tauri path, NOT missing keys.
    assert!(
        json.contains(r#""storage":null"#) && json.contains(r#""session":null"#),
        "an unreported seam must be null on the Tauri path (the key stays present); got: {json}"
    );

    // Faulted: reason present, counters now emitted.
    c.report_fault(Fault::DiskFull);
    let json = serde_json::to_string(&c.operator_view()).unwrap();
    assert!(
        json.contains(r#""output_health":{"held":true,"fault":"disk_full","holds":1}"#),
        "held shape must carry the reason and the hold count; got: {json}"
    );
    assert!(
        !json.contains("recoveries"),
        "recoveries must still skip at zero, or the contract's ?? 0 advice is wrong"
    );
}

// --- Storage + session health (C-015) -------------------------------------------------------

#[test]
fn a_controller_no_host_is_driving_reports_no_storage_or_session_health() {
    let v = live_controller().operator_view();
    assert_eq!(
        (v.storage.is_none(), v.session.is_none()),
        (true, true),
        "the stand-alone shell has no host autosaving, so the honest answer is 'unknown' — \
         not a fabricated healthy verdict"
    );
}

#[test]
fn storage_health_reported_by_the_host_reaches_the_view_and_changes_it() {
    let mut c = live_controller();
    c.set_storage_health("ok", Some(900_000), false);
    let before = c.operator_view().storage.unwrap();
    assert_eq!(before.status, "ok");
    assert!(!before.checkpoints_paused);

    c.set_storage_health("critical", Some(1_024), true);

    let after = c.operator_view().storage.unwrap();
    assert_ne!(after, before, "a changed verdict must change the view");
    assert_eq!(after.status, "critical");
    assert_eq!(after.available_bytes, Some(1_024));
    assert!(
        after.checkpoints_paused,
        "the operator has to be told persistence has stopped — that is the actionable part"
    );
}

/// `"unknown"` must survive to the view as itself. Collapsing it into `"ok"` would tell the
/// operator their disk is fine when nothing could check it.
#[test]
fn an_unknown_storage_verdict_stays_unknown_at_the_view() {
    let mut c = live_controller();
    c.set_storage_health("unknown", None, false);
    let s = c.operator_view().storage.unwrap();
    assert_eq!(s.status, "unknown");
    assert_eq!(
        s.available_bytes, None,
        "no figure may be invented for a disk nothing could read"
    );
}

#[test]
fn an_autosave_failure_reaches_the_view_and_clears_when_it_recovers() {
    let mut c = live_controller();
    c.set_session_health(true, false, None, Some("disk I/O error"));
    let down = c.operator_view().session.unwrap();
    assert!(down.restored);
    assert_eq!(down.autosave_error.as_deref(), Some("disk I/O error"));

    c.set_session_health(true, false, None, None);
    let up = c.operator_view().session.unwrap();
    assert_eq!(
        up.autosave_error, None,
        "a recovered autosave must stop displaying the failure it recovered from"
    );
}

/// The breaker's COUNT has to survive, not just the boolean: "started clean after 3 rapid
/// restarts" is a different message from "started clean", and the second reads as data loss.
#[test]
fn a_tripped_crash_loop_breaker_reports_its_count() {
    let mut c = live_controller();
    c.set_session_health(false, true, Some(3), None);
    let s = c.operator_view().session.unwrap();
    assert!(s.crash_loop);
    assert_eq!(s.rapid_launches, Some(3));
    assert!(
        !s.restored,
        "a breaker trip starts CLEAN — the session is preserved on disk, not restored"
    );
}

/// Bounded memory: exactly one autosave error is retained and it is length-capped. A host error
/// (a SQLite message with a nested cause) can be arbitrarily long.
#[test]
fn the_retained_autosave_error_is_capped() {
    let mut c = live_controller();
    c.set_session_health(false, false, None, Some(&"x".repeat(10_000)));
    let stored = c.operator_view().session.unwrap().autosave_error.unwrap();
    assert!(
        stored.len() <= selahcue_lan::protocol::MAX_ERROR_TEXT_LEN,
        "retained autosave error must be capped, got {} bytes",
        stored.len()
    );
    // Positive control: a short error survives verbatim, so the cap above is not merely
    // proving the field stores nothing.
    c.set_session_health(false, false, None, Some("short"));
    assert_eq!(
        c.operator_view().session.unwrap().autosave_error.as_deref(),
        Some("short")
    );
}

#[test]
fn storage_and_session_health_survive_the_wire_round_trip() {
    let mut c = live_controller();
    c.set_storage_health("low", Some(64), false);
    c.set_session_health(true, false, None, Some("autosave failed"));

    let wire: OperatorStateView = c.operator_view().into();
    let json = to_json(&ServerMessage::OperatorState { view: wire }).unwrap();
    let parsed: ServerMessage = selahcue_lan::protocol::from_json(&json).unwrap();
    let ServerMessage::OperatorState { view } = parsed else {
        panic!("expected an operator_state frame");
    };
    let back: selahcue_app::OperatorView = view.into();

    let s = back.storage.expect("storage health must survive the wire");
    assert_eq!((s.status.as_str(), s.available_bytes), ("low", Some(64)));
    let se = back.session.expect("session health must survive the wire");
    assert!(se.restored);
    assert_eq!(se.autosave_error.as_deref(), Some("autosave failed"));
}

// --- NDI availability (CON-158, 17tnw2axptc) ------------------------------------------------
//
// Same shape as storage/session health above, and for the same reason: `ndi_available` had
// exhaustive coverage in the headless JS suite (which drives a hand-written stub), but nothing
// exercised the REAL Rust producer — `LiveController::set_ndi_available`, the `From` impls, or
// the wire byte shape (Cody's + Sana's independent PR #85 review findings). A test against a
// hand-built `OperatorView`/`OperatorStateView` would pass even if the setter were never wired
// to `operator_view()` at all, which is exactly the defect class this file's own header warns
// about.

#[test]
fn a_controller_no_host_set_ndi_available_on_reports_it_as_unknown_not_unavailable() {
    let v = live_controller().operator_view();
    assert_eq!(
        v.ndi_available, None,
        "the stand-alone/Local shell never calls set_ndi_available (no real output host), so \
         the honest answer is 'unknown' — never a fabricated 'unavailable'"
    );
}

#[test]
fn ndi_available_reported_by_the_host_reaches_the_view_and_changes_it() {
    let mut c = live_controller();
    c.set_ndi_available(true);
    let healthy = c.operator_view().ndi_available;
    assert_eq!(healthy, Some(true));

    c.set_ndi_available(false);
    let unavailable = c.operator_view().ndi_available;
    assert_ne!(
        unavailable, healthy,
        "a changed report must change the view — an unchanged view means the setter is wired \
         at one end only"
    );
    assert_eq!(unavailable, Some(false));
}

/// `Some(true)`, `Some(false)` and `None` must all be distinguishable on the wire — the exact
/// three-way rule `unknown_health_and_healthy_health_are_different_on_the_wire` above already
/// pins for `output_health`. Collapsing any two of these would let "cannot transmit" and
/// "cannot say" render as the same state to the console.
#[test]
fn ndi_available_true_false_and_unknown_are_all_different_on_the_wire() {
    let mut c = live_controller();
    c.set_ndi_available(true);
    let available: OperatorStateView = c.operator_view().into();
    assert_eq!(available.ndi_available, Some(true));

    let mut unavailable = available.clone();
    unavailable.ndi_available = Some(false);

    let mut unknown = available.clone();
    unknown.ndi_available = None; // what an older host, or the Local shell, sends

    let available_json = to_json(&ServerMessage::OperatorState {
        view: available.clone(),
    })
    .unwrap();
    let unavailable_json = to_json(&ServerMessage::OperatorState {
        view: unavailable.clone(),
    })
    .unwrap();
    let unknown_json = to_json(&ServerMessage::OperatorState { view: unknown }).unwrap();

    assert_ne!(available_json, unavailable_json);
    assert_ne!(available_json, unknown_json);
    assert_ne!(unavailable_json, unknown_json);

    // Pin the actual bytes, not just "they differ" — a rename or a type change (e.g. to a
    // string) would still make three DIFFERENT strings while silently breaking every real
    // client's field-name/type assumption.
    assert!(
        available_json.contains(r#""ndi_available":true"#),
        "got: {available_json}"
    );
    assert!(
        unavailable_json.contains(r#""ndi_available":false"#),
        "got: {unavailable_json}"
    );
    assert!(
        !unknown_json.contains("ndi_available"),
        "an unreported host must stay byte-identical to a pre-CON-158 frame; got: {unknown_json}"
    );
}

#[test]
fn ndi_available_survives_the_wire_round_trip_both_ways() {
    for reported in [true, false] {
        let mut c = live_controller();
        c.set_ndi_available(reported);

        let wire: OperatorStateView = c.operator_view().into();
        let json = to_json(&ServerMessage::OperatorState { view: wire }).unwrap();
        let parsed: ServerMessage = selahcue_lan::protocol::from_json(&json).unwrap();
        let ServerMessage::OperatorState { view } = parsed else {
            panic!("expected an operator_state frame");
        };
        let back: selahcue_app::OperatorView = view.into();

        assert_eq!(
            back.ndi_available,
            Some(reported),
            "ndi_available={reported} must survive the wire round trip, or the remote console \
             stays blind to it"
        );
    }
}
