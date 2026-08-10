//! Integration tests for `providers_repo` — the Providers & Privacy settings +
//! consent store (FR-131/132/137). Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_core::providers::{
    ConsentState, IncludeInNotes, NotesTemplate, ProvidersConfig, ProvidersSettings,
    TranscriptionMode,
};
use selahcue_data::{providers_repo, Database};

#[test]
fn empty_store_loads_the_safe_defaults() {
    let db = Database::open_in_memory().unwrap();
    // Nothing saved yet → the core's offline-first defaults, not an error.
    let cfg = providers_repo::load(&db).unwrap();
    assert_eq!(cfg, ProvidersConfig::default());
    assert_eq!(cfg.settings.transcription_mode, TranscriptionMode::OnDevice);
    assert!(!cfg.consent.any_cloud_enabled());
}

#[test]
fn save_then_load_round_trips_every_field() {
    let db = Database::open_in_memory().unwrap();
    let cfg = ProvidersConfig {
        settings: ProvidersSettings {
            transcription_mode: TranscriptionMode::Cloud,
            notes_template: NotesTemplate::Devotional,
            preferred_translation: "WEBBE".to_string(),
            include: IncludeInNotes {
                prayer_points: false,
                scripture_extraction: true,
                social_excerpts: true,
                chapter_markers: false,
                notable_quotations: true,
                short_summary: false,
            },
        },
        consent: ConsentState {
            cloud_transcription: true,
            cloud_notes: true,
        },
    };
    providers_repo::save(&db, &cfg).unwrap();
    let loaded = providers_repo::load(&db).unwrap();
    assert_eq!(loaded, cfg);
}

#[test]
fn save_replaces_the_whole_set() {
    let db = Database::open_in_memory().unwrap();

    // First save: consent ON.
    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;
    providers_repo::save(&db, &cfg).unwrap();
    assert!(providers_repo::load(&db).unwrap().consent.cloud_notes);

    // Second save: consent revoked. The replace-the-set write must clear the old row,
    // not leave a stale "true" behind.
    cfg.consent.cloud_notes = false;
    providers_repo::save(&db, &cfg).unwrap();
    assert!(!providers_repo::load(&db).unwrap().consent.cloud_notes);
}
