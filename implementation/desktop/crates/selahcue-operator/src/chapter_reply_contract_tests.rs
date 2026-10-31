//! Recorded command-result contracts shared with the actual headless modal (17tnw2b13y0).
//! The Result envelope is test fixture transport: Ok is an invoke resolution; Err is its rejection
//! string. It is not a claim about Tauri's IPC framing. Every payload comes from get_chapter itself.
use super::get_chapter;

// Inputs/classes only, never a second parser, corpus, chapter length or expected ChapterView.
const REQUESTS: [(&str, &str, Option<&str>, bool); 8] = [
    ("bare-chapter", "gen 1", None, true),
    ("single-verse", "2 cor 4 5", None, true),
    ("verse-range", "Psalms 1:2-4", None, true),
    (
        "past-chapter-end",
        "psalm 1 verses 2 through 10",
        None,
        true,
    ),
    ("nonexistent-chapter", "Romans 99", None, false),
    ("unparseable-reference", "Hezekiah 4:4", None, false),
    ("last-chapter", "Rev 22", None, true),
    ("translation-gap", "Luke 17:36", Some("WEB"), true),
];

fn actual_replies() -> serde_json::Value {
    let cases: Vec<_> = REQUESTS
        .iter()
        .map(|&(id, reference, translation, expected_ok)| {
            let result = get_chapter(reference.to_owned(), translation.map(str::to_owned));
            assert_eq!(result.is_ok(), expected_ok, "input-class premise: {id}");
            serde_json::json!({
                "id": id,
                "request": {"reference": reference, "translation": translation},
                "result": result,
            })
        })
        .collect();
    serde_json::json!({"schema_version": 1, "cases": cases})
}

#[test]
fn y0_record_actual_chapter_replies() {
    let replies = actual_replies();
    assert_eq!(
        replies["cases"].as_array().expect("recorded cases").len(),
        REQUESTS.len()
    );
    let gap = &replies["cases"][7]["result"]["Ok"];
    let numbers: Vec<_> = gap["verses"]
        .as_array()
        .expect("real WEB chapter")
        .iter()
        .map(|verse| verse[0].as_u64().expect("verse number"))
        .collect();
    assert!(!numbers.contains(&36), "actual WEB Luke17 omits verse36");
    assert!(
        numbers.contains(&35) && numbers.contains(&37),
        "both real neighboring verses remain"
    );
    // Captured once by the hosted recorder. No source fixture is generated or rewritten by tests.
    println!(
        "Y0_ACTUAL_CHAPTER_FIXTURES={}",
        serde_json::to_string(&replies).expect("command results serialize")
    );
}

#[test]
fn y0_command_serialization_matches_recorded_fixtures() {
    // Frozen hosted output, not expected data regenerated from the implementation under test.
    let recorded: serde_json::Value =
        serde_json::from_str(include_str!("../fixtures/get_chapter/host-replies.json"))
            .expect("committed actual-host fixtures are valid JSON");
    assert_eq!(
        actual_replies(),
        recorded,
        "get_chapter wire payload drifted from the recorded modal contract"
    );
}

// The real modal replaces a past-end input with this canonical cut-back reference before its
// second Link press (dist/app.js resolveTyped/doLink). Input only; response is still real host data.
fn modal_companion_reply() -> serde_json::Value {
    let reference = "Psalms 1:2-6";
    let translation = "KJV";
    let result = get_chapter(reference.to_owned(), Some(translation.to_owned()));
    assert!(result.is_ok(), "the modal's confirmed Psalm1 range exists");
    serde_json::json!({
        "schema_version": 1,
        "cases": [{
            "id": "confirmed-past-chapter-end",
            "request": {"reference": reference, "translation": translation},
            "result": result,
        }],
    })
}

#[test]
fn y0_record_modal_companion_and_default_translation_equivalence() {
    let default_code = selahcue_scripture::Translation::default().code();
    assert_eq!(
        default_code, "KJV",
        "fixture requests record the current default"
    );
    let mut compared = 0;
    for &(id, reference, translation, expected_ok) in &REQUESTS {
        if translation.is_some() {
            continue;
        }
        let default = get_chapter(reference.to_owned(), None);
        let explicit = get_chapter(reference.to_owned(), Some(default_code.to_owned()));
        assert_eq!(
            default.is_ok(),
            expected_ok,
            "default input-class premise: {id}"
        );
        assert_eq!(
            explicit.is_ok(),
            expected_ok,
            "explicit input-class premise: {id}"
        );
        assert_eq!(
            serde_json::to_value(default).expect("default result serializes"),
            serde_json::to_value(explicit).expect("explicit result serializes"),
            "the modal's explicit KJV must match the captured default(None) result for {id}"
        );
        compared += 1;
    }
    assert_eq!(
        compared, 7,
        "all seven default requests, including both errors, are compared"
    );
    println!("Y0_DEFAULT_KJV_EQUIVALENCE={compared}");
    println!(
        "Y0_ACTUAL_MODAL_COMPANION_FIXTURES={}",
        serde_json::to_string(&modal_companion_reply()).expect("actual companion serializes")
    );
}
