//! Where live transcription should actually run — the decision `TranscriptionMode::Cloud`
//! was missing entirely (86akby7th). Before this module, `listening.rs` unconditionally built
//! the on-device engine: the setting persisted correctly but nothing downstream ever read it
//! back, so choosing Cloud in Settings silently ran Whisper anyway.
//!
//! # Why this is its own module, and not folded into `listening.rs`
//!
//! [`TranscriptionRoute::decide`] is pure — no thread, no socket, no mic — so it is testable,
//! and mutation-testable, without the `stt` feature `listening.rs` requires. Keeping it here
//! means the routing decision itself is exercised by `cargo test -p selahcue-operator` with
//! **no feature flags at all**, rather than only under `--features stt,cloud-stt` the way the
//! rest of the capture path must be. That matters for coverage: this repo has been bitten
//! before by controls that live behind a feature no CI line ever turns on.
//!
//! # The conjunction is consumed, not re-derived
//!
//! `may_stream_cloud_audio()` (`selahcue_core::providers::ProvidersConfig`) is the core's
//! single choke point for "is streaming live audio to a cloud service currently permitted".
//! [`TranscriptionRoute::decide`] calls it directly rather than re-reading
//! `transcription_mode` and `cloud_transcription` consent as two separate fields and
//! re-assembling the `&&` here. A control that reassembles a conjunction from parts is
//! asserting something about a *copy* of the predicate and survives mutation of the real one
//! (this repo's own postmortem, 86ak643rc) — consuming the core's function instead means a
//! bug in the real conjunction changes this function's answer too, so a test against this
//! function also exercises that one.
//!
//! The one field this module reads directly is `transcription_mode` itself, and only to tell
//! "on-device was explicitly chosen" apart from "cloud was chosen but is not currently usable"
//! — a distinction `may_stream_cloud_audio()`'s single boolean cannot make on its own, and one
//! the console needs so it never silently substitutes one engine for another (see
//! [`FallbackReason`]).

use selahcue_core::providers::{ProvidersConfig, TranscriptionMode};
use selahcue_stt_cloud::readiness::CloudSttReadiness;

/// Why transcription is running on-device even though Cloud is what was selected. `None`
/// means on-device was the actual choice — there is nothing to explain.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FallbackReason {
    /// Cloud mode is selected, but the operator has not granted cloud-transcription consent
    /// (or granted it and then revoked it) — `may_stream_cloud_audio()` says no.
    ConsentNotGranted,
    /// Cloud mode is selected and consented, but this build has no Deepgram transport
    /// compiled in (`cloud-stt` feature off).
    NotInBuild,
    /// Cloud mode is selected, consented, and the transport is built, but no usable
    /// `DEEPGRAM_API_KEY` credential is present.
    KeyMissing,
}

impl FallbackReason {
    /// One line naming the cause, safe to show on the console (FR-120 / FR-135 honest
    /// disclosure) — never blank, never "unavailable" with no next action.
    pub fn detail(self) -> &'static str {
        match self {
            FallbackReason::ConsentNotGranted => {
                "Cloud transcription is selected in Settings, but cloud-transcription consent \
                 has not been granted; using on-device transcription instead."
            }
            FallbackReason::NotInBuild => {
                "Cloud transcription is selected in Settings, but this build does not include \
                 it; using on-device transcription instead."
            }
            FallbackReason::KeyMissing => {
                "Cloud transcription is selected in Settings, but no Deepgram credential is \
                 configured; using on-device transcription instead."
            }
        }
    }
}

/// Where live transcription should run, decided once when the operator presses "Start
/// listening". Not re-evaluated for the lifetime of a capture session — a mid-service
/// **failure** of an active Cloud session is handled separately, as a runtime fallback in
/// `listening.rs`, not by re-running this decision.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TranscriptionRoute {
    /// Stream to Deepgram.
    Cloud,
    /// Run the on-device engine. `reason` is `Some` exactly when Cloud was selected but is
    /// not currently usable, so the console can say so rather than silently substituting.
    OnDevice { reason: Option<FallbackReason> },
}

impl TranscriptionRoute {
    /// The single decision point. Total (every input combination maps to exactly one route)
    /// and pure (same inputs, same answer, always) — see `route_selects_cloud_iff_mode_consent_and_readiness_all_agree`
    /// for the property this must hold.
    pub fn decide(config: &ProvidersConfig, readiness: CloudSttReadiness) -> Self {
        if config.settings.transcription_mode != TranscriptionMode::Cloud {
            return TranscriptionRoute::OnDevice { reason: None };
        }
        if !config.may_stream_cloud_audio() {
            return TranscriptionRoute::OnDevice {
                reason: Some(FallbackReason::ConsentNotGranted),
            };
        }
        match readiness {
            CloudSttReadiness::NotInBuild => TranscriptionRoute::OnDevice {
                reason: Some(FallbackReason::NotInBuild),
            },
            CloudSttReadiness::KeyMissing => TranscriptionRoute::OnDevice {
                reason: Some(FallbackReason::KeyMissing),
            },
            CloudSttReadiness::Ready => TranscriptionRoute::Cloud,
        }
    }

    /// The fallback reason to surface on the console, if this route did not select Cloud
    /// because Cloud was not usable (as opposed to not selected at all).
    pub fn fallback_reason(self) -> Option<FallbackReason> {
        match self {
            TranscriptionRoute::OnDevice { reason } => reason,
            TranscriptionRoute::Cloud => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use selahcue_core::providers::ConsentState;

    fn config(mode: TranscriptionMode, cloud_transcription_consent: bool) -> ProvidersConfig {
        let mut cfg = ProvidersConfig::default();
        cfg.settings.transcription_mode = mode;
        cfg.consent = ConsentState {
            cloud_transcription: cloud_transcription_consent,
            ..cfg.consent
        };
        cfg
    }

    /// Test-only: whether a route selects the cloud provider. Not a production method (nothing
    /// in `listening.rs` needs it — it matches `TranscriptionRoute` directly), kept here only so
    /// the property test below can compare against a plain `bool`.
    fn is_cloud(route: TranscriptionRoute) -> bool {
        matches!(route, TranscriptionRoute::Cloud)
    }

    // --- The positive case: everything agrees, Cloud is actually selected ------------------

    #[test]
    fn cloud_mode_plus_consent_plus_ready_routes_to_cloud() {
        let cfg = config(TranscriptionMode::Cloud, true);
        let route = TranscriptionRoute::decide(&cfg, CloudSttReadiness::Ready);
        assert_eq!(
            route,
            TranscriptionRoute::Cloud,
            "selecting Cloud with consent granted and the build ready must route to Cloud — \
             this is the exact bug 86akby7th exists to fix"
        );
        assert!(is_cloud(route));
        assert_eq!(route.fallback_reason(), None);
    }

    // --- On-device was actually chosen: no fallback story to tell --------------------------

    #[test]
    fn on_device_mode_routes_to_on_device_with_no_reason_even_when_cloud_would_be_ready() {
        // Consent granted AND cloud ready — but on-device is what was selected. Must not
        // report a fallback reason: nothing was "fallen back" from.
        let cfg = config(TranscriptionMode::OnDevice, true);
        let route = TranscriptionRoute::decide(&cfg, CloudSttReadiness::Ready);
        assert_eq!(route, TranscriptionRoute::OnDevice { reason: None });
        assert!(!is_cloud(route));
    }

    // --- Cloud selected but not eligible: each ineligibility reason distinctly reachable ---

    #[test]
    fn cloud_mode_without_consent_falls_back_with_consent_not_granted() {
        let cfg = config(TranscriptionMode::Cloud, false);
        // Readiness varies independently — even a Ready build must not stream without consent.
        let route = TranscriptionRoute::decide(&cfg, CloudSttReadiness::Ready);
        assert_eq!(
            route,
            TranscriptionRoute::OnDevice {
                reason: Some(FallbackReason::ConsentNotGranted)
            },
            "consent must gate streaming even when the build is otherwise ready"
        );
    }

    #[test]
    fn cloud_mode_with_consent_but_not_in_build_falls_back_with_not_in_build() {
        let cfg = config(TranscriptionMode::Cloud, true);
        let route = TranscriptionRoute::decide(&cfg, CloudSttReadiness::NotInBuild);
        assert_eq!(
            route,
            TranscriptionRoute::OnDevice {
                reason: Some(FallbackReason::NotInBuild)
            }
        );
    }

    #[test]
    fn cloud_mode_with_consent_but_key_missing_falls_back_with_key_missing() {
        let cfg = config(TranscriptionMode::Cloud, true);
        let route = TranscriptionRoute::decide(&cfg, CloudSttReadiness::KeyMissing);
        assert_eq!(
            route,
            TranscriptionRoute::OnDevice {
                reason: Some(FallbackReason::KeyMissing)
            }
        );
    }

    // --- The conjunction is consumed, not re-derived: proven by varying inputs independently

    #[test]
    fn route_selects_cloud_iff_mode_consent_and_readiness_all_agree() {
        // Every one of the eight (mode × consent × readiness-is-ready) combinations, checked
        // against the single ground truth: Cloud selected AND may_stream_cloud_audio() AND
        // readiness == Ready. A positive AND a negative control for every axis — flipping any
        // one input must flip the verdict.
        for mode in [TranscriptionMode::OnDevice, TranscriptionMode::Cloud] {
            for consent in [false, true] {
                for readiness in [
                    CloudSttReadiness::NotInBuild,
                    CloudSttReadiness::KeyMissing,
                    CloudSttReadiness::Ready,
                ] {
                    let cfg = config(mode, consent);
                    let expected_cloud = mode == TranscriptionMode::Cloud
                        && cfg.may_stream_cloud_audio()
                        && readiness == CloudSttReadiness::Ready;
                    let route = TranscriptionRoute::decide(&cfg, readiness);
                    assert_eq!(
                        is_cloud(route),
                        expected_cloud,
                        "mode={mode:?} consent={consent} readiness={readiness:?}: \
                         expected is_cloud={expected_cloud}, got {route:?}"
                    );
                }
            }
        }
    }

    // --- A rejected/absent consent must never be silently reported as "on-device chosen" ---

    #[test]
    fn ineligible_cloud_selection_always_carries_a_reason_never_none() {
        // Whatever the readiness state, Cloud-selected-but-ineligible must always explain
        // itself. `reason: None` is reserved for "on-device was actually chosen" — collapsing
        // the two would let the console show plain "on-device" text when the operator's
        // actual setting still says Cloud, which is exactly the honesty gap this ticket exists
        // to close.
        for consent in [false, true] {
            for readiness in [CloudSttReadiness::NotInBuild, CloudSttReadiness::KeyMissing] {
                let cfg = config(TranscriptionMode::Cloud, consent);
                let route = TranscriptionRoute::decide(&cfg, readiness);
                assert!(
                    route.fallback_reason().is_some(),
                    "Cloud selected but ineligible (consent={consent}, readiness={readiness:?}) \
                     must carry a fallback reason, got {route:?}"
                );
            }
        }
    }

    // --- Every reason names an actionable cause on the console, never a blank string --------

    #[test]
    fn every_fallback_reason_has_a_non_blank_actionable_detail() {
        for reason in [
            FallbackReason::ConsentNotGranted,
            FallbackReason::NotInBuild,
            FallbackReason::KeyMissing,
        ] {
            let detail = reason.detail();
            assert!(
                !detail.trim().is_empty(),
                "{reason:?} must have a non-blank console message"
            );
            assert!(
                detail.contains("Cloud transcription"),
                "{reason:?}'s detail should name what it is talking about: {detail:?}"
            );
        }
    }
}
