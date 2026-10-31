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
    ("translation-gap", "Matthew 17:21", Some("WEB"), true),
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
    // Captured once by the hosted recorder. No source fixture is generated or rewritten by tests.
    println!(
        "Y0_ACTUAL_CHAPTER_FIXTURES={}",
        serde_json::to_string(&replies).expect("command results serialize")
    );
}
