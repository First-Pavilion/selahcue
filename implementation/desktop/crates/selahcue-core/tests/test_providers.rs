//! Integration tests for the Providers & Privacy domain (R3). Public API.
//!
//! These assert the **privacy invariants** first — offline by default, no cloud
//! egress without a per-provider opt-in, and note requests that only ever carry the
//! completed transcript (never live audio) — because those are the properties the
//! whole feature exists to guarantee (FR-131/132/135/137, NFR-018, CON-5).

#![allow(clippy::unwrap_used)]

use selahcue_core::providers::{
    ConsentState, IncludeInNotes, NoteError, NotesTemplate, ProvidersConfig, ProvidersSettings,
    Quota, TranscriptionMode, MAX_TRANSLATION_CODE_LEN,
};

#[test]
fn defaults_are_offline_and_private() {
    let cfg = ProvidersConfig::default();
    // Transcription runs on-device by default; audio never leaves the machine.
    assert_eq!(cfg.settings.transcription_mode, TranscriptionMode::OnDevice);
    // Both cloud opt-ins default OFF.
    assert!(!cfg.consent.cloud_transcription);
    assert!(!cfg.consent.cloud_notes);
    assert!(!cfg.consent.any_cloud_enabled());
    // The default template + translation match the shipped design/code.
    assert_eq!(
        cfg.settings.notes_template,
        NotesTemplate::FullOutlineWithScriptures
    );
    assert_eq!(cfg.settings.preferred_translation, "KJV");
    // Include-in-notes defaults: social excerpts, podcast show notes and short
    // description OFF, the rest ON.
    let i = cfg.settings.include;
    assert!(i.prayer_points && i.scripture_extraction && i.chapter_markers);
    assert!(i.notable_quotations && i.short_summary);
    assert!(!i.social_excerpts);
    assert!(!i.podcast_show_notes);
    assert!(!i.short_description);
}

#[test]
fn podcast_and_short_description_toggle_independently_and_round_trip() {
    // Each carries its own persisted key, distinct from the other and from every
    // pre-existing toggle (86akgqdwc, following the exact pattern the ticket asks
    // for — mirrors `kv_round_trips_every_field` but isolates just these two so a
    // future regression here is unambiguous about which key broke).
    let mut cfg = ProvidersConfig::default();
    cfg.settings.include.podcast_show_notes = true;
    let restored = ProvidersConfig::from_kv(cfg.to_kv());
    assert!(restored.settings.include.podcast_show_notes);
    assert!(
        !restored.settings.include.short_description,
        "toggling podcast_show_notes must not also flip short_description"
    );

    let mut cfg2 = ProvidersConfig::default();
    cfg2.settings.include.short_description = true;
    let restored2 = ProvidersConfig::from_kv(cfg2.to_kv());
    assert!(restored2.settings.include.short_description);
    assert!(
        !restored2.settings.include.podcast_show_notes,
        "toggling short_description must not also flip podcast_show_notes"
    );
}

#[test]
fn default_config_can_never_stream_cloud_audio() {
    let cfg = ProvidersConfig::default();
    assert!(!cfg.may_stream_cloud_audio());
}

#[test]
fn cloud_audio_requires_both_cloud_mode_and_consent() {
    // Consent set but still on-device → no streaming.
    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_transcription = true;
    assert!(!cfg.may_stream_cloud_audio());

    // Cloud mode but no consent → no streaming.
    let mut cfg = ProvidersConfig::default();
    cfg.settings.transcription_mode = TranscriptionMode::Cloud;
    assert!(!cfg.may_stream_cloud_audio());

    // Both → streaming permitted.
    let mut cfg = ProvidersConfig::default();
    cfg.settings.transcription_mode = TranscriptionMode::Cloud;
    cfg.consent.cloud_transcription = true;
    assert!(cfg.may_stream_cloud_audio());
}

#[test]
fn note_request_is_refused_without_consent() {
    let cfg = ProvidersConfig::default();
    // No consent, Generate pressed → refused, nothing to send.
    let err = cfg
        .build_note_request("full sermon transcript", true)
        .unwrap_err();
    assert_eq!(err, NoteError::ConsentRequired);
}

#[test]
fn note_request_is_refused_until_generate_is_pressed() {
    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;
    // Consent set but Generate not pressed → still refused ("nothing sent until Generate").
    let err = cfg
        .build_note_request("full sermon transcript", false)
        .unwrap_err();
    assert_eq!(err, NoteError::ConsentRequired);
}

#[test]
fn consented_generate_builds_a_transcript_only_request() {
    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;
    cfg.settings.notes_template = NotesTemplate::Summary;
    cfg.settings.preferred_translation = "WEBBE".to_string();

    let req = cfg
        .build_note_request("the completed sermon transcript", true)
        .unwrap();

    // The request carries the completed transcript and the chosen options only.
    assert_eq!(req.transcript, "the completed sermon transcript");
    assert_eq!(req.options.template, NotesTemplate::Summary);
    assert_eq!(req.options.preferred_translation, "WEBBE");
    // (There is no audio field on NoteRequest by construction — live audio can never
    // be included. This is enforced at the type level.)
}

#[test]
fn kv_round_trips_every_field() {
    let cfg = ProvidersConfig {
        settings: ProvidersSettings {
            transcription_mode: TranscriptionMode::Cloud,
            notes_template: NotesTemplate::Devotional,
            preferred_translation: "ASV".to_string(),
            include: IncludeInNotes {
                prayer_points: false,
                scripture_extraction: false,
                social_excerpts: true,
                chapter_markers: false,
                notable_quotations: false,
                short_summary: false,
                podcast_show_notes: true,
                short_description: true,
            },
        },
        consent: ConsentState {
            cloud_transcription: true,
            cloud_notes: true,
        },
    };
    let restored = ProvidersConfig::from_kv(cfg.to_kv());
    assert_eq!(restored, cfg);
}

#[test]
fn from_kv_is_tolerant_and_never_enables_cloud_on_garbage() {
    // Missing keys → defaults; garbage consent value → stays false (fail-safe).
    let pairs = vec![
        ("transcription_mode", "wat"),
        ("notes_template", "nonsense"),
        ("consent.cloud_notes", "YES"), // not exactly "true" → must stay false
        ("unknown.key", "ignored"),
    ];
    let cfg = ProvidersConfig::from_kv(pairs);
    assert_eq!(cfg.settings.transcription_mode, TranscriptionMode::OnDevice);
    assert_eq!(
        cfg.settings.notes_template,
        NotesTemplate::FullOutlineWithScriptures
    );
    assert!(!cfg.consent.cloud_notes, "garbage must not enable cloud");
    // Missing preferred_translation falls back to the default.
    assert_eq!(cfg.settings.preferred_translation, "KJV");
}

#[test]
fn translation_code_is_length_bounded() {
    let long = "X".repeat(MAX_TRANSLATION_CODE_LEN + 50);
    let cfg = ProvidersConfig::from_kv(vec![("preferred_translation", long.as_str())]);
    assert!(cfg.settings.preferred_translation.len() <= MAX_TRANSLATION_CODE_LEN);
}

#[test]
fn quota_remaining_is_saturating() {
    let q = Quota {
        used: 12,
        limit: 40,
        resets_label: "Sep 1".into(),
    };
    assert_eq!(q.remaining(), 28);
    assert!(!q.is_exhausted());

    // Over-used never underflows.
    let over = Quota {
        used: 100,
        limit: 40,
        resets_label: "Sep 1".into(),
    };
    assert_eq!(over.remaining(), 0);
    assert!(over.is_exhausted());
}

#[test]
fn template_parse_round_trips_and_tolerates_garbage() {
    for t in NotesTemplate::ALL {
        assert_eq!(NotesTemplate::parse(t.as_str()), t);
        assert!(!t.label().is_empty());
    }
    assert_eq!(
        NotesTemplate::parse("???"),
        NotesTemplate::FullOutlineWithScriptures
    );
}
