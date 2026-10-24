//! How [`crate::RemoteOperator`] reads a host reply, and what it says when the reply is not the
//! one it asked for (FR-082; 17tnw2axppb).
//!
//! A non-conforming reply (version skew, a host bug, or a request/response desync -
//! `ControlClient::command` does not correlate `request_id`; the LAN is an untrusted-peer
//! boundary) used to be reported as `TransportError::Protocol(format!("expected X, got:
//! {other:?}"))`. `Debug` on a `ServerMessage` dumps its WHOLE payload, and `OperatorState`,
//! `SermonNoteDraft`, `PairingCode` and `Error` carry live transcript, detection, note, pairing
//! and host-supplied text verbatim. `TransportError::Protocol`'s `Display` prints that string
//! unchanged, so every caller that logged or returned the error (`eprintln!`, a Tauri command's
//! `message` field rendered in the operator UI) leaked it.
//!
//! The cure is structural, not per caller: every reply is read through one of the `expect_*`
//! functions below, and the ONLY way they report a surprise is [`unexpected_reply`], which names
//! the received variant via [`ServerMessage::kind`] and never formats a field. Each function is
//! pure (a reply in, a value or error out) so each branch is unit-tested here with no network;
//! `tests/test_operator_reply_redaction.rs` proves the same over a real control link.

use crate::operator::RemoteSnapshot;
use crate::sermon_note_store::RegenerationSlot;
use selahcue_lan::protocol::{
    AutosaveSlotView, OperatorStateView, ScriptureHitView, SermonNoteDraftView, ServerMessage,
    ThumbView,
};
use selahcue_lan::TransportError;

pub(crate) type PairingCode = (String, String, u64, Option<String>);

/// The error for a reply that is not the one the caller asked for. Names what was expected and
/// the variant that arrived - never any of its contents. Takes the reply by value so the payload
/// is dropped here and cannot be reached by whatever the caller does next.
pub(crate) fn unexpected_reply(expected: &str, got: ServerMessage) -> TransportError {
    TransportError::Protocol(format!("expected {expected}, got: {}", got.kind()))
}

pub(crate) fn expect_pairing_code(reply: ServerMessage) -> Result<PairingCode, TransportError> {
    match reply {
        ServerMessage::PairingCode {
            code,
            fingerprint,
            expires_in_secs,
            uri,
        } => Ok((code, fingerprint, expires_in_secs, uri)),
        other => Err(unexpected_reply("pairing_code", other)),
    }
}

pub(crate) fn expect_remote_devices(
    reply: ServerMessage,
) -> Result<RemoteSnapshot, TransportError> {
    match reply {
        ServerMessage::RemoteDevices { devices, pending } => Ok((devices, pending)),
        other => Err(unexpected_reply("remote_devices", other)),
    }
}

pub(crate) fn expect_autosave_slots(
    reply: ServerMessage,
) -> Result<Vec<AutosaveSlotView>, TransportError> {
    match reply {
        ServerMessage::AutosaveSlots { slots } => Ok(slots),
        other => Err(unexpected_reply("autosave_slots", other)),
    }
}

pub(crate) fn expect_active_transcript_id(
    reply: ServerMessage,
) -> Result<Option<i64>, TransportError> {
    match reply {
        ServerMessage::ActiveTranscriptId { transcript_id } => Ok(transcript_id),
        other => Err(unexpected_reply("active_transcript_id", other)),
    }
}

/// A `LoadSermonNoteDraft` reply: only a `SermonNoteDraft` is acceptable (a `Denied` here is a
/// real failure for a read, not a soft "no draft").
pub(crate) fn expect_sermon_note_draft(
    reply: ServerMessage,
) -> Result<Option<SermonNoteDraftView>, TransportError> {
    match reply {
        ServerMessage::SermonNoteDraft { draft, .. } => Ok(draft),
        other => Err(unexpected_reply("sermon_note_draft", other)),
    }
}

/// A `SaveSermonNoteDraft`/`UpdateSermonNoteDraft` reply: a host refusal (`Denied`) fails soft
/// to `Ok(None)`, exactly like the draft being absent.
pub(crate) fn expect_sermon_note_draft_or_denied(
    reply: ServerMessage,
) -> Result<Option<SermonNoteDraftView>, TransportError> {
    match reply {
        ServerMessage::SermonNoteDraft { draft, .. } => Ok(draft),
        ServerMessage::Denied { .. } => Ok(None),
        other => Err(unexpected_reply("sermon_note_draft", other)),
    }
}

/// A Stage/Confirm/Discard sermon-note regeneration reply (FR-129): a host refusal fails soft
/// to `Ok(None)`.
pub(crate) fn expect_regeneration_state(
    reply: ServerMessage,
) -> Result<Option<RegenerationSlot>, TransportError> {
    match reply {
        ServerMessage::SermonNoteRegenerationState {
            current, pending, ..
        } => Ok(Some(RegenerationSlot { current, pending })),
        ServerMessage::Denied { .. } => Ok(None),
        other => Err(unexpected_reply("sermon_note_regeneration_state", other)),
    }
}

pub(crate) fn expect_scripture_results(
    reply: ServerMessage,
) -> Result<Vec<ScriptureHitView>, TransportError> {
    match reply {
        ServerMessage::ScriptureResults {
            hits, references, ..
        } => {
            // A pre-7ad host sends only bare references: synthesize text-less hits so results
            // still render (snippets empty).
            if hits.is_empty() && !references.is_empty() {
                Ok(references
                    .into_iter()
                    .map(|reference| ScriptureHitView {
                        reference,
                        text: String::new(),
                    })
                    .collect())
            } else {
                Ok(hits)
            }
        }
        other => Err(unexpected_reply("scripture_results", other)),
    }
}

pub(crate) fn expect_console_thumbnails(
    reply: ServerMessage,
) -> Result<(Option<ThumbView>, Option<ThumbView>), TransportError> {
    match reply {
        ServerMessage::ConsoleThumbnails { preview, live } => Ok((preview, live)),
        other => Err(unexpected_reply("console_thumbnails", other)),
    }
}

pub(crate) fn expect_screen_frame(
    reply: ServerMessage,
) -> Result<Option<ThumbView>, TransportError> {
    match reply {
        ServerMessage::ScreenFrame { frame, .. } => Ok(frame),
        other => Err(unexpected_reply("screen_frame", other)),
    }
}

/// The reply to a mutating command: an `Ack`, or a `Denied` (an RBAC/app refusal is NOT an
/// error - the caller re-reads the unchanged state).
pub(crate) fn expect_ack_or_denied(reply: ServerMessage) -> Result<(), TransportError> {
    match reply {
        ServerMessage::Ack { .. } | ServerMessage::Denied { .. } => Ok(()),
        other => Err(unexpected_reply("ack or denied", other)),
    }
}

pub(crate) fn expect_operator_state(
    reply: ServerMessage,
) -> Result<OperatorStateView, TransportError> {
    match reply {
        ServerMessage::OperatorState { view } => Ok(view),
        other => Err(unexpected_reply("operator_state", other)),
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    //! Every `expect_*` branch x every possible `ServerMessage` variant: the matching reply
    //! succeeds, every other reply is an error that names the variant it got and the one it
    //! wanted and contains NONE of the reply's payload, in `Display` or in `Debug`.
    use super::*;
    use selahcue_lan::protocol::{
        from_json, DenyReason, RemoteDeviceView, ScriptureHitView, SermonNoteDraftView, VerseView,
    };
    use selahcue_lan::Role;

    const SECRET: &str = "SECRET-LIVE-TEXT-7f3a";

    fn draft() -> SermonNoteDraftView {
        SermonNoteDraftView {
            title: format!("{SECRET}-title"),
            summary: Some(format!("{SECRET}-summary")),
            sections_json: format!(r#"[{{"heading":"{SECRET}"}}]"#),
            scriptures_json: "[]".into(),
            ai_generated: true,
            disclosure: Some(format!("{SECRET}-disclosure")),
            provider: format!("{SECRET}-provider"),
            model: Some(format!("{SECRET}-model")),
            created_at_ms: 1,
            edited_at_ms: 2,
        }
    }

    /// One reply of EVERY `ServerMessage` variant, each carrying `SECRET` in every free-text
    /// field it has. `OperatorState` is the realistic worst case: the live transcript, the
    /// partial transcript and a detection (reference + verse text), all planted.
    fn every_reply() -> Vec<ServerMessage> {
        let operator_state: ServerMessage = from_json(&format!(
            r#"{{"event":"operator_state","view":{{"plan_name":"{SECRET}-plan","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":[{{"id":0,"start_ms":0,"end_ms":1,"text":"{SECRET}-transcript"}}],"partial_transcript":"{SECRET}-partial","detections":[{{"id":1,"reference":"{SECRET}-ref","text":"{SECRET}-detection"}}]}}}}"#
        ))
        .unwrap();
        vec![
            ServerMessage::Ack { request_id: 1 },
            ServerMessage::Denied {
                request_id: 2,
                reason: DenyReason::Forbidden,
            },
            ServerMessage::State {
                live_item: Some(5),
                blackout: false,
            },
            ServerMessage::ScriptureResults {
                query: format!("{SECRET}-query"),
                references: vec![format!("{SECRET}-reference")],
                hits: vec![ScriptureHitView {
                    reference: format!("{SECRET}-hit-ref"),
                    text: format!("{SECRET}-hit-text"),
                }],
            },
            ServerMessage::Chapter {
                book_name: format!("{SECRET}-book"),
                chapter: 1,
                translation: "KJV".into(),
                verses: vec![VerseView {
                    number: 1,
                    text: format!("{SECRET}-verse"),
                }],
                prev_ref: None,
                next_ref: None,
            },
            operator_state,
            ServerMessage::ConsoleThumbnails {
                preview: Some(ThumbView::from_rgba(1, 1, &[1, 2, 3, 4])),
                live: None,
            },
            ServerMessage::ScreenFrame {
                screen: format!("{SECRET}-screen"),
                frame: None,
            },
            ServerMessage::RemoteDevices {
                devices: vec![RemoteDeviceView {
                    device_id: format!("{SECRET}-device"),
                    name: format!("{SECRET}-name"),
                    platform: "iOS".into(),
                    role: Role::Viewer,
                    idle_secs: 0,
                    pinned: false,
                }],
                pending: vec![],
            },
            ServerMessage::PairingCode {
                code: format!("{SECRET}-code"),
                fingerprint: format!("{SECRET}-fingerprint"),
                expires_in_secs: 120,
                uri: Some(format!("selahcue://pair?code={SECRET}")),
            },
            ServerMessage::ActiveTranscriptId {
                transcript_id: Some(7),
            },
            ServerMessage::SermonNoteDraft {
                transcript_id: 7,
                draft: Some(draft()),
            },
            ServerMessage::SermonNoteRegenerationState {
                transcript_id: 7,
                current: Some(draft()),
                pending: Some(draft()),
            },
            ServerMessage::AutosaveSlots {
                slots: vec![AutosaveSlotView {
                    slot: 1,
                    saved_at_ms: 1,
                    label: Some(format!("{SECRET}-label")),
                }],
            },
            ServerMessage::Error {
                message: format!("{SECRET}-error"),
            },
        ]
    }

    /// One row per `expect_*` function: what it says it expected, which reply kinds it ACCEPTS,
    /// and the function itself reduced to `Result<(), TransportError>`.
    struct Branch {
        name: &'static str,
        expected_label: &'static str,
        accepts: &'static [&'static str],
        call: fn(ServerMessage) -> Result<(), TransportError>,
    }

    fn branches() -> Vec<Branch> {
        vec![
            Branch {
                name: "expect_pairing_code",
                expected_label: "pairing_code",
                accepts: &["pairing_code"],
                call: |r| expect_pairing_code(r).map(|_| ()),
            },
            Branch {
                name: "expect_remote_devices",
                expected_label: "remote_devices",
                accepts: &["remote_devices"],
                call: |r| expect_remote_devices(r).map(|_| ()),
            },
            Branch {
                name: "expect_autosave_slots",
                expected_label: "autosave_slots",
                accepts: &["autosave_slots"],
                call: |r| expect_autosave_slots(r).map(|_| ()),
            },
            Branch {
                name: "expect_active_transcript_id",
                expected_label: "active_transcript_id",
                accepts: &["active_transcript_id"],
                call: |r| expect_active_transcript_id(r).map(|_| ()),
            },
            Branch {
                name: "expect_sermon_note_draft",
                expected_label: "sermon_note_draft",
                accepts: &["sermon_note_draft"],
                call: |r| expect_sermon_note_draft(r).map(|_| ()),
            },
            Branch {
                name: "expect_sermon_note_draft_or_denied",
                expected_label: "sermon_note_draft",
                accepts: &["sermon_note_draft", "denied"],
                call: |r| expect_sermon_note_draft_or_denied(r).map(|_| ()),
            },
            Branch {
                name: "expect_regeneration_state",
                expected_label: "sermon_note_regeneration_state",
                accepts: &["sermon_note_regeneration_state", "denied"],
                call: |r| expect_regeneration_state(r).map(|_| ()),
            },
            Branch {
                name: "expect_scripture_results",
                expected_label: "scripture_results",
                accepts: &["scripture_results"],
                call: |r| expect_scripture_results(r).map(|_| ()),
            },
            Branch {
                name: "expect_console_thumbnails",
                expected_label: "console_thumbnails",
                accepts: &["console_thumbnails"],
                call: |r| expect_console_thumbnails(r).map(|_| ()),
            },
            Branch {
                name: "expect_screen_frame",
                expected_label: "screen_frame",
                accepts: &["screen_frame"],
                call: |r| expect_screen_frame(r).map(|_| ()),
            },
            Branch {
                name: "expect_ack_or_denied",
                expected_label: "ack or denied",
                accepts: &["ack", "denied"],
                call: expect_ack_or_denied,
            },
            Branch {
                name: "expect_operator_state",
                expected_label: "operator_state",
                accepts: &["operator_state"],
                call: |r| expect_operator_state(r).map(|_| ()),
            },
        ]
    }

    #[test]
    fn the_matrix_covers_every_branch_and_every_reply_variant() {
        // 12 `expect_*` functions and 15 `ServerMessage` variants (the 15 is also pinned by
        // `selahcue-lan`'s `kind()` test): if either grows, this forces the matrix to grow too.
        assert_eq!(branches().len(), 12, "one row per expect_* function");
        let kinds: std::collections::BTreeSet<_> =
            every_reply().iter().map(ServerMessage::kind).collect();
        assert_eq!(
            kinds.len(),
            15,
            "one sample reply per ServerMessage variant"
        );
        // Every accepted kind a row names is a real variant (a typo would silently turn an
        // "accepted" row into a row that never accepts anything).
        for b in branches() {
            for k in b.accepts {
                assert!(kinds.contains(k), "{}: unknown accepted kind {k}", b.name);
            }
        }
    }

    #[test]
    fn a_non_matching_reply_is_a_protocol_error_that_names_both_variants_and_leaks_nothing() {
        let mut errors_checked = 0;
        for b in branches() {
            for reply in every_reply() {
                let got = reply.kind();
                let outcome = (b.call)(reply);
                if b.accepts.contains(&got) {
                    assert!(outcome.is_ok(), "{} must accept a {got} reply", b.name);
                    continue;
                }
                let err = outcome.expect_err(&format!("{} must refuse a {got} reply", b.name));
                assert!(
                    matches!(err, TransportError::Protocol(_)),
                    "{} / {got}: wrong error variant: {err}",
                    b.name
                );
                let shown = err.to_string();
                let debugged = format!("{err:?}");
                for (how, text) in [("Display", &shown), ("Debug", &debugged)] {
                    assert!(
                        !text.contains(SECRET) && !text.contains("SECRET"),
                        "{} / {got}: {how} leaked reply payload: {text}",
                        b.name
                    );
                    assert!(
                        text.contains(&format!("got: {got}")),
                        "{} / {got}: {how} must name the variant received: {text}",
                        b.name
                    );
                    assert!(
                        text.contains(b.expected_label),
                        "{} / {got}: {how} must name what was expected: {text}",
                        b.name
                    );
                }
                errors_checked += 1;
            }
        }
        // 12 branches x 15 variants, minus the accepted pairs (1+1+1+1+1+2+2+1+1+1+2+1 = 15).
        assert_eq!(
            errors_checked,
            12 * 15 - 15,
            "no branch/variant pair skipped"
        );
    }

    #[test]
    fn the_error_text_is_exactly_the_stable_label_form() {
        // Pins the one wording every downstream message and log search relies on, and that it is
        // the variant NAME: a payload-bearing format (Debug, Display of a field) cannot produce
        // this exact string.
        let err = expect_active_transcript_id(every_reply().remove(5)).unwrap_err();
        assert_eq!(
            err.to_string(),
            "protocol error: expected active_transcript_id, got: operator_state"
        );
        let err = expect_ack_or_denied(ServerMessage::Error {
            message: SECRET.into(),
        })
        .unwrap_err();
        assert_eq!(
            err.to_string(),
            "protocol error: expected ack or denied, got: error"
        );
    }

    #[test]
    fn unexpected_reply_takes_ownership_so_the_payload_is_gone() {
        // The signature is the guard: it consumes the reply. (Compile-time property; this
        // exercises it with the worst-case payload and checks the output once more.)
        let operator_state = every_reply().remove(5);
        let err = unexpected_reply("anything", operator_state);
        assert!(!err.to_string().contains("SECRET"));
        assert!(!format!("{err:?}").contains("SECRET"));
    }

    // ---- the matching replies still succeed, with their payload intact ----

    #[test]
    fn matching_replies_succeed_and_keep_their_payload() {
        let pc = expect_pairing_code(ServerMessage::PairingCode {
            code: "abcd1234".into(),
            fingerprint: "A1 B2".into(),
            expires_in_secs: 120,
            uri: Some("selahcue://pair?code=abcd1234".into()),
        })
        .unwrap();
        assert_eq!(
            pc,
            (
                "abcd1234".into(),
                "A1 B2".into(),
                120,
                Some("selahcue://pair?code=abcd1234".into())
            )
        );
        let pc_no_uri = expect_pairing_code(ServerMessage::PairingCode {
            code: "c".into(),
            fingerprint: "f".into(),
            expires_in_secs: 0,
            uri: None,
        })
        .unwrap();
        assert_eq!(pc_no_uri.3, None, "an absent invite stays None");

        assert_eq!(
            expect_active_transcript_id(ServerMessage::ActiveTranscriptId {
                transcript_id: Some(9)
            })
            .unwrap(),
            Some(9)
        );
        assert_eq!(
            expect_active_transcript_id(ServerMessage::ActiveTranscriptId {
                transcript_id: None
            })
            .unwrap(),
            None,
            "no transcript ever recorded is Ok(None), not an error"
        );

        let (devices, pending) = expect_remote_devices(ServerMessage::RemoteDevices {
            devices: vec![],
            pending: vec![],
        })
        .unwrap();
        assert!(devices.is_empty() && pending.is_empty());

        assert!(
            expect_autosave_slots(ServerMessage::AutosaveSlots { slots: vec![] })
                .unwrap()
                .is_empty()
        );
        assert_eq!(
            expect_autosave_slots(ServerMessage::AutosaveSlots {
                slots: vec![AutosaveSlotView {
                    slot: 3,
                    saved_at_ms: 4,
                    label: None
                }]
            })
            .unwrap()
            .len(),
            1
        );

        let view = expect_operator_state(every_reply().remove(5)).unwrap();
        assert_eq!(view.plan_name, format!("{SECRET}-plan"));
        assert_eq!(
            view.transcript.len(),
            1,
            "the matching reply keeps its content"
        );
    }

    #[test]
    fn sermon_note_draft_replies_distinguish_present_absent_and_refused() {
        let found = ServerMessage::SermonNoteDraft {
            transcript_id: 7,
            draft: Some(draft()),
        };
        let none = ServerMessage::SermonNoteDraft {
            transcript_id: 7,
            draft: None,
        };
        let denied = || ServerMessage::Denied {
            request_id: 1,
            reason: DenyReason::Forbidden,
        };
        // Load: a draft, or "no draft yet" (the common, expected Ok(None)); a refusal is an
        // error for a READ.
        assert_eq!(
            expect_sermon_note_draft(found.clone()).unwrap(),
            Some(draft())
        );
        assert_eq!(expect_sermon_note_draft(none.clone()).unwrap(), None);
        let err = expect_sermon_note_draft(denied()).unwrap_err();
        assert!(err.to_string().ends_with("got: denied"), "{err}");
        // Save/Update: the same, but a host refusal fails soft to Ok(None).
        assert_eq!(
            expect_sermon_note_draft_or_denied(found).unwrap(),
            Some(draft())
        );
        assert_eq!(expect_sermon_note_draft_or_denied(none).unwrap(), None);
        assert_eq!(expect_sermon_note_draft_or_denied(denied()).unwrap(), None);
    }

    #[test]
    fn regeneration_replies_map_state_and_refusal() {
        let slot = expect_regeneration_state(ServerMessage::SermonNoteRegenerationState {
            transcript_id: 7,
            current: Some(draft()),
            pending: None,
        })
        .unwrap()
        .unwrap();
        assert_eq!(slot.current, Some(draft()));
        assert_eq!(slot.pending, None, "an empty pending slot stays empty");
        // The honest (should-not-happen) case: nothing accepted and nothing pending is still a
        // well-formed state, not a refusal.
        let empty = expect_regeneration_state(ServerMessage::SermonNoteRegenerationState {
            transcript_id: 7,
            current: None,
            pending: None,
        })
        .unwrap();
        assert_eq!(empty, Some(RegenerationSlot::default()));
        assert_eq!(
            expect_regeneration_state(ServerMessage::Denied {
                request_id: 1,
                reason: DenyReason::Forbidden
            })
            .unwrap(),
            None
        );
    }

    #[test]
    fn scripture_results_prefer_hits_and_synthesize_for_a_legacy_host() {
        let hit = ScriptureHitView {
            reference: "John 3:16".into(),
            text: "For God so loved".into(),
        };
        // Hits present: returned as sent (references are only the compatibility fallback).
        let got = expect_scripture_results(ServerMessage::ScriptureResults {
            query: "q".into(),
            references: vec!["ignored 1:1".into()],
            hits: vec![hit.clone()],
        })
        .unwrap();
        assert_eq!(got, vec![hit]);
        // A pre-7ad host: bare references become text-less hits.
        let got = expect_scripture_results(ServerMessage::ScriptureResults {
            query: "q".into(),
            references: vec!["Romans 8:28".into(), "Jude 3".into()],
            hits: vec![],
        })
        .unwrap();
        assert_eq!(
            got.iter().map(|h| h.reference.as_str()).collect::<Vec<_>>(),
            ["Romans 8:28", "Jude 3"]
        );
        assert!(got.iter().all(|h| h.text.is_empty()));
        // No results at all is an empty list, not an error.
        assert!(expect_scripture_results(ServerMessage::ScriptureResults {
            query: "q".into(),
            references: vec![],
            hits: vec![],
        })
        .unwrap()
        .is_empty());
    }

    #[test]
    fn thumbnails_frames_and_acks_pass_through() {
        let thumb = ThumbView::from_rgba(1, 1, &[1, 2, 3, 4]);
        let (p, l) = expect_console_thumbnails(ServerMessage::ConsoleThumbnails {
            preview: Some(thumb.clone()),
            live: None,
        })
        .unwrap();
        assert_eq!((p, l), (Some(thumb.clone()), None));
        assert_eq!(
            expect_screen_frame(ServerMessage::ScreenFrame {
                screen: "s".into(),
                frame: Some(thumb.clone())
            })
            .unwrap(),
            Some(thumb)
        );
        assert_eq!(
            expect_screen_frame(ServerMessage::ScreenFrame {
                screen: "unknown".into(),
                frame: None
            })
            .unwrap(),
            None,
            "an unknown screen is Ok(None)"
        );
        // A mutating command's refusal is NOT an error: the caller re-reads the unchanged state.
        expect_ack_or_denied(ServerMessage::Ack { request_id: 1 }).unwrap();
        expect_ack_or_denied(ServerMessage::Denied {
            request_id: 1,
            reason: DenyReason::Forbidden,
        })
        .unwrap();
    }
}
