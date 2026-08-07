//! Public-API tests for the media library (Design 2.0 node 329:124).

#![allow(clippy::unwrap_used)]

use selahcue_core::media::{
    MediaAsset, MediaId, MediaKind, MediaLibrary, MAX_MEDIA_ASSETS, MAX_MEDIA_PATH_LEN,
};

#[test]
fn media_kind_tags_round_trip_and_reject_unknown() {
    for k in [MediaKind::Image, MediaKind::Video, MediaKind::Audio] {
        assert_eq!(MediaKind::from_tag(k.as_tag()), Some(k), "tag round-trips");
    }
    assert_eq!(MediaKind::from_tag("hologram"), None, "unknown tag → None");
}

fn img(lib: &mut MediaLibrary, path: &str, bytes: u64) -> Option<MediaId> {
    lib.import(
        path,
        MediaKind::Image,
        bytes,
        Some(1920),
        Some(1080),
        None,
        0,
    )
}

#[test]
fn import_assigns_stable_monotonic_ids_and_preserves_order() {
    let mut lib = MediaLibrary::new();
    assert!(lib.is_empty());
    let a = img(&mut lib, "harvest.jpg", 2_400_000).unwrap();
    let b = img(&mut lib, "sunrise.jpg", 3_100_000).unwrap();
    assert_eq!(
        (a, b),
        (MediaId(1), MediaId(2)),
        "ids are 1,2 in import order"
    );
    let paths: Vec<&str> = lib.assets().iter().map(|x| x.path.as_str()).collect();
    assert_eq!(paths, vec!["harvest.jpg", "sunrise.jpg"]);
    // Removing an id retires it: the next import does NOT reuse it.
    assert!(lib.remove(a));
    let c = img(&mut lib, "cross.jpg", 1_800_000).unwrap();
    assert_eq!(c, MediaId(3), "ids are never reused after removal");
    assert!(lib.get(a).is_none(), "the removed asset is gone");
}

#[test]
fn import_is_idempotent_by_path() {
    // Re-importing the same file returns the SAME id (no duplicate row), so the storage
    // total and the usage scan stay correct when one asset is used on several slides.
    let mut lib = MediaLibrary::new();
    let first = img(&mut lib, "loop.mov", 500).unwrap();
    let again = img(&mut lib, "loop.mov", 999).unwrap();
    assert_eq!(first, again, "same path → same id");
    assert_eq!(lib.len(), 1, "no duplicate asset was added");
    assert_eq!(
        lib.get(first).unwrap().size_bytes,
        500,
        "the first import's metadata is retained (idempotent, not overwrite)"
    );
}

#[test]
fn total_bytes_sums_storage_and_saturates() {
    let mut lib = MediaLibrary::new();
    img(&mut lib, "a.jpg", 2_400_000).unwrap();
    img(&mut lib, "b.jpg", 3_100_000).unwrap();
    assert_eq!(lib.total_bytes(), 5_500_000);
    // Saturating: even two near-u64::MAX assets cannot overflow the accounting.
    let mut big = MediaLibrary::new();
    big.import("x", MediaKind::Video, u64::MAX, None, None, Some(1), 0)
        .unwrap();
    big.import("y", MediaKind::Video, 10, None, None, Some(1), 0)
        .unwrap();
    assert_eq!(big.total_bytes(), u64::MAX, "sum saturates, never wraps");
}

#[test]
fn missing_uses_the_injected_existence_probe() {
    let mut lib = MediaLibrary::new();
    img(&mut lib, "present.jpg", 1).unwrap();
    let gone = img(&mut lib, "baptism.jpg", 1).unwrap();
    // Injected probe: everything exists EXCEPT baptism.jpg (the design's "Missing / File moved").
    let missing = lib.missing(|p| p != "baptism.jpg");
    assert_eq!(
        missing,
        vec![gone],
        "only the absent file is reported missing"
    );
    // A probe that finds nothing reports every asset; one that finds all reports none.
    assert_eq!(lib.missing(|_| false).len(), 2);
    assert!(lib.missing(|_| true).is_empty());
}

#[test]
fn import_rejects_empty_and_overlong_paths_without_growing() {
    let mut lib = MediaLibrary::new();
    assert!(
        lib.import("", MediaKind::Image, 1, None, None, None, 0)
            .is_none(),
        "an empty path is rejected"
    );
    let overlong = "a".repeat(MAX_MEDIA_PATH_LEN + 1);
    assert!(
        lib.import(overlong, MediaKind::Image, 1, None, None, None, 0)
            .is_none(),
        "a path over the cap is rejected"
    );
    assert!(lib.is_empty(), "a rejected import never grows the registry");
    assert!(lib.within_bounds());
}

#[test]
fn the_registry_is_bounded_no_unbounded_growth() {
    // Bounded-memory guarantee: import stops at MAX_MEDIA_ASSETS and never grows past it.
    let mut lib = MediaLibrary::new();
    for i in 0..MAX_MEDIA_ASSETS {
        assert!(
            img(&mut lib, &format!("f{i}.jpg"), 1).is_some(),
            "fills up to the cap"
        );
    }
    assert_eq!(lib.len(), MAX_MEDIA_ASSETS);
    assert!(
        img(&mut lib, "one-too-many.jpg", 1).is_none(),
        "import past the cap is rejected"
    );
    assert_eq!(
        lib.len(),
        MAX_MEDIA_ASSETS,
        "the registry never exceeds the cap"
    );
    assert!(lib.within_bounds());
}

#[test]
fn asset_captures_dimensions_and_duration_metadata() {
    // A video asset carries width/height/duration; an image leaves duration None; an audio
    // asset leaves width/height None — the optional metadata the library surfaces per kind.
    let mut lib = MediaLibrary::new();
    let vid = lib
        .import(
            "clip.mp4",
            MediaKind::Video,
            42,
            Some(1920),
            Some(1080),
            Some(134_000),
            7,
        )
        .unwrap();
    let a = lib.get(vid).unwrap();
    assert_eq!(
        (a.width, a.height, a.duration_ms, a.imported_at),
        (Some(1920), Some(1080), Some(134_000), 7)
    );
    assert_eq!(a.kind, MediaKind::Video);

    let audio = MediaAsset {
        id: MediaId(9),
        path: "pad.wav".to_string(),
        kind: MediaKind::Audio,
        size_bytes: 100,
        width: None,
        height: None,
        duration_ms: Some(200_000),
        imported_at: 0,
    };
    assert!(audio.within_bounds());
    assert_eq!(audio.width, None, "audio has no pixel dimensions");
}

#[test]
fn from_assets_rehydrates_next_id_past_the_largest() {
    // The repo persists assets (not next_id); rehydration derives next_id so a fresh import
    // never collides with a persisted id.
    let persisted = vec![
        MediaAsset {
            id: MediaId(4),
            path: "a".into(),
            kind: MediaKind::Image,
            size_bytes: 1,
            width: None,
            height: None,
            duration_ms: None,
            imported_at: 0,
        },
        MediaAsset {
            id: MediaId(9),
            path: "b".into(),
            kind: MediaKind::Image,
            size_bytes: 1,
            width: None,
            height: None,
            duration_ms: None,
            imported_at: 0,
        },
    ];
    let mut lib = MediaLibrary::from_assets(persisted);
    assert_eq!(lib.len(), 2);
    let fresh = img(&mut lib, "c", 1).unwrap();
    assert_eq!(
        fresh,
        MediaId(10),
        "next id is one past the largest persisted id"
    );
}

#[test]
fn import_normalises_paths_like_mediaref_so_usage_keys_match() {
    // A library path must key IDENTICALLY to the `MediaRef` a slide holds (which trims + rejects
    // NUL). Otherwise a whitespace-padded import would be stored under a different key than the
    // slide's reference and be misclassified as unused. Import trims; re-importing the trimmed
    // form is idempotent; a NUL path is rejected.
    let mut lib = MediaLibrary::new();
    let id = lib
        .import("  logo.png  ", MediaKind::Image, 1, None, None, None, 0)
        .unwrap();
    assert_eq!(
        lib.get(id).unwrap().path,
        "logo.png",
        "the stored path is trimmed"
    );
    assert_eq!(
        lib.get_by_path("logo.png").map(|a| a.id),
        Some(id),
        "the trimmed form (what MediaRef yields) finds the asset"
    );
    // Re-importing with surrounding whitespace is idempotent (same trimmed key → same id).
    assert_eq!(
        lib.import("logo.png ", MediaKind::Image, 9, None, None, None, 0),
        Some(id)
    );
    assert_eq!(lib.len(), 1, "no duplicate from a whitespace variant");
    // A NUL in the path is rejected (mirrors MediaRef), and a whitespace-only path is empty.
    assert!(lib
        .import("a\0b", MediaKind::Image, 1, None, None, None, 0)
        .is_none());
    assert!(lib
        .import("   ", MediaKind::Image, 1, None, None, None, 0)
        .is_none());
}

#[test]
fn get_by_path_finds_the_asset_for_usage_correlation() {
    // The usage scan (in `selahcue-present`) matches an `Element::Image` source path back to
    // its asset via this lookup — so it must find an imported path and miss an unknown one.
    let mut lib = MediaLibrary::new();
    let id = img(&mut lib, "harvest.jpg", 1).unwrap();
    assert_eq!(lib.get_by_path("harvest.jpg").map(|a| a.id), Some(id));
    assert!(lib.get_by_path("nope.jpg").is_none());
}
