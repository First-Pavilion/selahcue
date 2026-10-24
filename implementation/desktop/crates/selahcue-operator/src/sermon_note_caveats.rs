//! Requested-but-empty caveats on the PERSISTED sermon-note draft (86akmfn54).
//!
//! 86akc0tua made a section the generator was asked for and could not fill (an enabled
//! `IncludeInNotes` flag, or a section FR-122 always asks for) visible instead of silently
//! dropped: `parse_draft` raises a [`DraftCaveat::SectionRequestedEmpty`], and `draft_json`
//! turns it into the draft-level `caveats` array plus a per-section `empty_requested` flag.
//! That worked for a FRESH generation only. The caveat lives on the in-memory `NoteDraft`,
//! the persisted columns had nowhere to put it, and the persist path (`sections_to_persist`)
//! deliberately DROPPED the empty section so that a reload could not show "a bare heading
//! over an empty list with no explanation". The cost was that every reload, restart, edit-save
//! and regenerate-confirm reverted a caveated section to the pre-fix silent drop.
//!
//! # Where the caveat is stored
//!
//! With the draft, inside the existing `sections_json` column, and nowhere else:
//!
//! - No new column, no migration, no `selahcue-lan` wire change. `sections_json` is already
//!   opaque to the store and to the LAN protocol (the codec for it lives in this crate), and
//!   it is already size-capped (`MAX_SECTIONS_JSON_BYTES`), so this adds no unbounded storage.
//! - The stored value is ALWAYS the legacy array of section objects. A draft that records no
//!   caveat is written exactly as before this ticket, byte for byte.
//! - A draft that records caveats adds ONE extra key, `requested_empty` (the list of headings,
//!   in generation order, that [`DraftCaveat`] carried), to the FIRST section object. It
//!   includes the two fixed labels for requested fields that are not sections (`Summary`,
//!   `Scripture references`), which have no section object of their own, which is why the list
//!   is draft-level rather than a flag on each section. Only a draft with no sections at all
//!   uses an object, `{"sections":[],"requested_empty":[...]}`.
//!
//! # Downgrade safety
//!
//! A build from before this ticket reads `sections_json` as `Vec<NoteSectionInput>`, which
//! ignores unknown keys, and a build that cannot read a value at all treats it as "no
//! sections". The array shape therefore keeps every real section readable by an older build,
//! and an edit-save there rewrites the array without the extra key (the caveat is lost, no
//! section is). The one object shape is only used when there is no section to lose. Pinned by
//! decoding the stored value with the old reader's exact type. Future changes to this value
//! must stay additive in the same way: new keys only, never a new top-level shape.
//!
//! # One source of truth
//!
//! The stored heading list is the only thing persisted. On load it becomes
//! `DraftCaveat::SectionRequestedEmpty` values again and `draft_json` derives `caveats` and
//! `empty_requested` from them exactly as it does for a fresh generation. Nothing else
//! computes either.
//!
//! # A caveat is only honoured while it is still true
//!
//! A stored heading is turned back into a caveat only if the content it describes is still
//! empty ([`still_requested_empty`]): the section with that heading has no content, the
//! summary is blank, the scripture list is empty. So filling a section in, typing a summary,
//! or renaming a heading removes the caveat on the next save or load without anyone having
//! to remember to clear it, and a stale or hostile stored heading can never mark a populated
//! section "nothing came back" (which would hide its content). "Requested" is therefore
//! advisory presentation state, not an authorization: the webview reports what it showed, and
//! the server honours it only as far as the content agrees.
//!
//! # Reading is bounded like writing
//!
//! The write path never stores more than `MAX_SECTIONS_JSON_BYTES`. The read path refuses to
//! look for caveats in anything larger (a row from a build with the old 200 000-byte cap, or a
//! LAN writer): such a value is read exactly as it always was, sections only, and carries no
//! caveat. Within the cap, the shape is chosen by the first non-space byte, and at most
//! [`MAX_STORED_HEADINGS`] entries of the list are collected.

use selahcue_core::providers::{
    DraftCaveat, NoteDraft, NoteSection, SCRIPTURE_REFERENCES_CAVEAT_HEADING,
    SUMMARY_CAVEAT_HEADING,
};

/// Most stored headings collected from `requested_empty`. A draft has a few dozen sections at
/// the very most (the generator's table is fixed), so this is far above any honest value; it
/// exists so a hostile or corrupt column cannot make the reload build an arbitrarily long
/// list. Whatever is kept is further limited to headings that match actual content, so the
/// result is never longer than `sections.len() + 2`.
const MAX_STORED_HEADINGS: usize = 256;

/// The extra key that carries the caveats (see the module docs).
const REQUESTED_EMPTY_KEY: &str = "requested_empty";

/// True when a section carries no content: no non-blank flat item, and no outline point with
/// non-blank text or a non-blank sub-point. Judged on content only, never the heading. The
/// server alone judges emptiness; the webview only reports the caveats it was shown.
pub(crate) fn section_is_empty(s: &NoteSection) -> bool {
    s.items().iter().all(|i| i.trim().is_empty())
        && s.points()
            .iter()
            .all(|p| p.text.trim().is_empty() && p.sub_points.iter().all(|sp| sp.trim().is_empty()))
}

/// The subset of `candidates` that is still a true "requested but came back empty" statement
/// about this content, de-duplicated, in the order given.
///
/// - A blank heading names nothing and is dropped.
/// - `Summary` is true while the summary is absent or blank. A whitespace-only summary counts
///   as blank here although `transcripts.js` renders any non-empty summary string: the caveat
///   then sits beside an invisible summary, which is the honest reading of it.
/// - `Scripture references` is true while the scripture list has no non-blank entry.
/// - Anything else names a section: true while at least one section with exactly that heading
///   is empty. With duplicate headings, the empty ones are the ones the caveat describes; a
///   populated namesake is untouched (see `draft_json`, which flags per section).
///
/// The two labels are reserved: a section renamed to `Summary` is judged by the SUMMARY, not
/// by its own content. A heading that matches nothing is dropped. At most
/// [`MAX_STORED_HEADINGS`] candidates are examined.
pub(crate) fn still_requested_empty<'a>(
    candidates: impl IntoIterator<Item = &'a str>,
    summary: Option<&str>,
    sections: &[NoteSection],
    scriptures: &[String],
) -> Vec<String> {
    let mut kept: Vec<String> = Vec::new();
    for heading in candidates.into_iter().take(MAX_STORED_HEADINGS) {
        if heading.trim().is_empty() || kept.iter().any(|k| k == heading) {
            continue;
        }
        let still_empty = if heading == SUMMARY_CAVEAT_HEADING {
            summary.is_none_or(|s| s.trim().is_empty())
        } else if heading == SCRIPTURE_REFERENCES_CAVEAT_HEADING {
            scriptures.iter().all(|s| s.trim().is_empty())
        } else {
            sections
                .iter()
                .any(|s| s.heading == heading && section_is_empty(s))
        };
        if still_empty {
            kept.push(heading.to_string());
        }
    }
    kept
}

/// Serialise `sections` for the `sections_json` column, recording `requested_empty` with
/// them when it is non-empty. `requested_empty` must already have been through
/// [`still_requested_empty`].
///
/// Empty `requested_empty` writes the legacy array unchanged (see the module docs). Otherwise
/// the list rides on the first section object (an object only when there is no section). If
/// that would exceed the store's own cap, the caveat yields rather than the draft: the empty
/// caveated sections are left out and the plain array is written, which is exactly what was
/// persisted before this ticket. A caveat must never be the reason a draft is refused.
fn encode_sections(sections: &[NoteSection], requested_empty: &[String]) -> String {
    if requested_empty.is_empty() {
        return crate::sections_to_json(sections);
    }
    let mut values = crate::sections_to_values(sections);
    let full = match values
        .first_mut()
        .and_then(serde_json::Value::as_object_mut)
    {
        Some(first) => {
            first.insert(REQUESTED_EMPTY_KEY.to_string(), requested_empty.into());
            serde_json::to_string(&values)
        }
        None => serde_json::to_string(&serde_json::json!({
            "sections": values,
            "requested_empty": requested_empty,
        })),
    }
    .unwrap_or_default();
    if !full.is_empty() && full.len() <= selahcue_data::sermon_note_repo::MAX_SECTIONS_JSON_BYTES {
        return full;
    }
    let without_caveated_empties: Vec<NoteSection> = sections
        .iter()
        .filter(|s| !(requested_empty.contains(&s.heading) && section_is_empty(s)))
        .cloned()
        .collect();
    crate::sections_to_json(&without_caveated_empties)
}

/// The `sections_json` value to persist for a freshly generated draft: its sections, plus the
/// headings of the [`DraftCaveat::SectionRequestedEmpty`] caveats that are true of it.
pub(crate) fn persisted_sections_json(draft: &NoteDraft) -> String {
    let candidates = draft.caveats.iter().filter_map(|c| match c {
        DraftCaveat::SectionRequestedEmpty { heading } => Some(heading.as_str()),
        // About one reference or the scan budget, not a section; both are recomputed fresh
        // from the stored sections and scriptures on every load (`sermon_note_draft_json`).
        DraftCaveat::ScriptureUnverified { .. } => None,
        DraftCaveat::ScriptureVerificationIncomplete => None,
    });
    let kept = still_requested_empty(
        candidates,
        draft.summary.as_deref(),
        &draft.sections,
        &draft.scriptures,
    );
    encode_sections(&draft.sections, &kept)
}

/// The `sections_json` value to persist for an operator edit. `requested_empty` is what the
/// edit surface says the draft carried (it knows which headings the operator was shown a
/// caveat for, and under what name after any rename); it is trusted only as far as the edited
/// content still agrees with it.
pub(crate) fn edited_sections_json(
    sections: &[NoteSection],
    summary: Option<&str>,
    scriptures: &[String],
    requested_empty: &[String],
) -> String {
    let kept = still_requested_empty(
        requested_empty.iter().map(String::as_str),
        summary,
        sections,
        scriptures,
    );
    encode_sections(sections, &kept)
}

/// The persisted-row input for a freshly generated draft: what `transcript_generate_notes`
/// saves or stages (FR-129). Everything but `sections_json` is carried over unchanged from the
/// outcome; no `NoteProvider` exposes a model id through `GenerationOutcome` today, so `model`
/// stays `None`.
pub(crate) fn draft_input_for(
    outcome: &selahcue_cloud::GenerationOutcome,
) -> selahcue_lan::protocol::SermonNoteDraftInput {
    selahcue_lan::protocol::SermonNoteDraftInput {
        title: outcome.draft.title.clone(),
        summary: outcome.draft.summary.clone(),
        sections_json: persisted_sections_json(&outcome.draft),
        scriptures_json: crate::scriptures_to_json(&outcome.draft.scriptures),
        ai_generated: outcome.ai_generated,
        disclosure: outcome.disclosure.map(str::to_string),
        provider: outcome.provider_label.clone(),
        model: None,
    }
}

/// The store input for an operator edit (`update_sermon_note_draft`).
///
/// `requested_empty` is authoritative when present: the headings of the requested-but-empty
/// caveats the operator was shown, by their current names (the edit form can rename a
/// heading), each kept only while the edited content is still empty. `Some(&[])` clears every
/// caveat. When it is absent (`None`) the caller does not know, and the caveats already stored
/// in `stored_sections_json` are kept for as long as they are still true; absent is never
/// read as "none", because the webview ships with this binary and omitting the argument can
/// only be a bug.
pub(crate) fn edit_input_for(
    title: String,
    summary: Option<String>,
    sections: Vec<crate::NoteSectionInput>,
    scriptures: &[String],
    requested_empty: Option<&[String]>,
    stored_sections_json: Option<&str>,
) -> selahcue_lan::protocol::SermonNoteEditInput {
    let sections = crate::sections_from_input(sections);
    let candidates: Vec<String> = match requested_empty {
        Some(list) => list.to_vec(),
        None => stored_sections_json
            .map(|json| decode_sections(json).1)
            .unwrap_or_default(),
    };
    selahcue_lan::protocol::SermonNoteEditInput {
        sections_json: edited_sections_json(&sections, summary.as_deref(), scriptures, &candidates),
        title,
        summary,
        scriptures_json: crate::scriptures_to_json(scriptures),
    }
}

/// One stored section object: the fields the pre-change reader knew (`NoteSectionInput`,
/// which ignores unknown keys, so any future additive key is ignored too) plus the extra key.
#[derive(serde::Deserialize)]
struct StoredSection {
    #[serde(flatten)]
    section: crate::NoteSectionInput,
    #[serde(default, deserialize_with = "lenient_headings")]
    requested_empty: Vec<String>,
}

/// The object shape, used only for a draft with no sections.
#[derive(serde::Deserialize)]
struct StoredNoSections {
    #[serde(default)]
    sections: Vec<crate::NoteSectionInput>,
    #[serde(default, deserialize_with = "lenient_headings")]
    requested_empty: Vec<String>,
}

/// Read the `requested_empty` field leniently: a list yields at most [`MAX_STORED_HEADINGS`]
/// of its string entries (collection stops there; every other entry is skipped), and ANY other
/// type (null, a string, a number, an object) yields no headings instead of failing, so a
/// damaged field can cost the caveats but never the sections that sit beside it.
fn lenient_headings<'de, D>(deserializer: D) -> Result<Vec<String>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    struct Bounded(Vec<String>);

    impl<'de> serde::Deserialize<'de> for Bounded {
        fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
        where
            D: serde::Deserializer<'de>,
        {
            struct ListVisitor;
            impl<'de> serde::de::Visitor<'de> for ListVisitor {
                type Value = Bounded;
                fn expecting(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                    f.write_str("a list of headings")
                }
                fn visit_seq<A>(self, mut seq: A) -> Result<Bounded, A::Error>
                where
                    A: serde::de::SeqAccess<'de>,
                {
                    let mut out = Vec::new();
                    let mut examined = 0usize;
                    while examined < MAX_STORED_HEADINGS {
                        match seq.next_element::<serde_json::Value>()? {
                            Some(serde_json::Value::String(s)) => out.push(s),
                            Some(_) => {}
                            None => return Ok(Bounded(out)),
                        }
                        examined += 1;
                    }
                    // Past the window: consume without keeping anything.
                    while seq.next_element::<serde::de::IgnoredAny>()?.is_some() {}
                    Ok(Bounded(out))
                }
            }
            deserializer.deserialize_seq(ListVisitor)
        }
    }

    #[derive(serde::Deserialize)]
    #[serde(untagged)]
    enum Field {
        List(Bounded),
        Other(serde::de::IgnoredAny),
    }

    use serde::Deserialize as _;
    Ok(match Field::deserialize(deserializer)? {
        Field::List(Bounded(list)) => list,
        Field::Other(_) => Vec::new(),
    })
}

/// Read a `sections_json` value back: the sections, and the headings stored with them.
///
/// Anything unreadable degrades to nothing, as it always has (a corrupt column must not fail
/// the whole draft load); a damaged `requested_empty` degrades only the caveats. A value over
/// the write cap is read exactly as before this ticket (sections only, no caveats), so the
/// new work is bounded by the same cap the writer obeys. Within the cap the shape is chosen by
/// the first non-space byte.
pub(crate) fn decode_sections(json: &str) -> (Vec<crate::NoteSectionInput>, Vec<String>) {
    if json.len() > selahcue_data::sermon_note_repo::MAX_SECTIONS_JSON_BYTES {
        return (
            serde_json::from_str::<Vec<crate::NoteSectionInput>>(json).unwrap_or_default(),
            Vec::new(),
        );
    }
    match json.trim_start().as_bytes().first() {
        Some(b'[') => match serde_json::from_str::<Vec<StoredSection>>(json) {
            Ok(stored) => {
                // Only the first section object carries the list; the key anywhere else is
                // ignored.
                let headings = stored
                    .first()
                    .map(|s| s.requested_empty.clone())
                    .unwrap_or_default();
                (stored.into_iter().map(|s| s.section).collect(), headings)
            }
            Err(_) => (Vec::new(), Vec::new()),
        },
        Some(b'{') => match serde_json::from_str::<StoredNoSections>(json) {
            Ok(stored) => (stored.sections, stored.requested_empty),
            Err(_) => (Vec::new(), Vec::new()),
        },
        _ => (Vec::new(), Vec::new()),
    }
}

/// The caveats a reloaded draft carries for requested-but-empty content: the stored headings
/// that are still true of it, as the same [`DraftCaveat`] a fresh generation raises.
pub(crate) fn reloaded_caveats(
    stored: &[String],
    summary: Option<&str>,
    sections: &[NoteSection],
    scriptures: &[String],
) -> Vec<DraftCaveat> {
    still_requested_empty(
        stored.iter().map(String::as_str),
        summary,
        sections,
        scriptures,
    )
    .into_iter()
    .map(|heading| DraftCaveat::SectionRequestedEmpty { heading })
    .collect()
}

/// Helpers shared by both test modules below.
#[cfg(test)]
mod support {
    use super::DraftCaveat;
    use serde_json::Value;

    pub(super) fn caveat(heading: &str) -> DraftCaveat {
        DraftCaveat::SectionRequestedEmpty {
            heading: heading.to_string(),
        }
    }

    /// `kind: section_empty` headings of a wire draft, in order.
    pub(super) fn caveat_headings(j: &Value) -> Vec<String> {
        j["caveats"]
            .as_array()
            .expect("caveats is an array")
            .iter()
            .filter(|c| c["kind"] == "section_empty")
            .map(|c| c["heading"].as_str().expect("heading").to_string())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::support::{caveat, caveat_headings};
    use super::*;
    use crate::{draft_json, scriptures_to_json, sections_from_input, sermon_note_draft_json};
    use selahcue_core::providers::{NotePoint, OUTLINE_HEADING};
    use selahcue_data::sermon_note_repo::MAX_SECTIONS_JSON_BYTES;
    use selahcue_lan::protocol::SermonNoteDraftView;
    use serde_json::{json, Value};

    const SUMMARY: &str = SUMMARY_CAVEAT_HEADING;
    const SCRIPTURES: &str = SCRIPTURE_REFERENCES_CAVEAT_HEADING;

    fn draft(
        summary: Option<&str>,
        sections: Vec<NoteSection>,
        scriptures: &[&str],
        caveats: Vec<DraftCaveat>,
    ) -> NoteDraft {
        NoteDraft {
            title: "Faith that Endures".to_string(),
            summary: summary.map(str::to_string),
            sections,
            scriptures: scriptures.iter().map(|s| s.to_string()).collect(),
            caveats,
            scripture_verdicts: Vec::new(),
            timestamps: Vec::new(),
        }
    }

    fn view(
        sections_json: String,
        summary: Option<&str>,
        scriptures: &[String],
    ) -> SermonNoteDraftView {
        SermonNoteDraftView {
            title: "Faith that Endures".to_string(),
            summary: summary.map(str::to_string),
            sections_json,
            scriptures_json: scriptures_to_json(scriptures),
            ai_generated: true,
            disclosure: Some("AI-generated. Verify before use.".to_string()),
            provider: "SelahCue AI".to_string(),
            model: None,
            created_at_ms: 1,
            edited_at_ms: 1,
        }
    }

    /// The wire view a draft has after the real persist step wrote its columns.
    fn persisted_view(d: &NoteDraft) -> SermonNoteDraftView {
        view(
            persisted_sections_json(d),
            d.summary.as_deref(),
            &d.scriptures,
        )
    }

    /// What the console receives when it reloads `d` from storage.
    fn reload(d: &NoteDraft) -> Value {
        sermon_note_draft_json(&persisted_view(d), &[]).0
    }

    /// Headings of the sections the wire marks `empty_requested`, in order.
    fn flagged_sections(j: &Value) -> Vec<String> {
        j["sections"]
            .as_array()
            .expect("sections is an array")
            .iter()
            .filter(|s| s["empty_requested"] == true)
            .map(|s| s["heading"].as_str().expect("heading").to_string())
            .collect()
    }

    fn strings(v: &[&str]) -> Vec<String> {
        v.iter().map(|s| s.to_string()).collect()
    }

    // --- the bug: the defect as the ticket reports it ----------------------------------------

    #[test]
    fn a_fresh_generation_marks_the_requested_empty_section() {
        // Positive control for everything below: the FRESH path already worked, so the
        // reload tests are comparing against something real, not against nothing.
        let d = draft(
            None,
            vec![
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Chapter markers", Vec::new()),
            ],
            &[],
            vec![caveat("Chapter markers")],
        );
        let fresh = draft_json(&d);
        assert_eq!(flagged_sections(&fresh), ["Chapter markers"]);
        assert_eq!(caveat_headings(&fresh), ["Chapter markers"]);
    }

    #[test]
    fn a_requested_empty_section_keeps_its_caveat_after_persist_and_reload() {
        let d = draft(
            None,
            vec![
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Chapter markers", Vec::new()),
                NoteSection::flat("Key lessons", vec!["Stay".into()]),
            ],
            &[],
            vec![caveat("Chapter markers")],
        );
        let reloaded = reload(&d);
        assert_eq!(caveat_headings(&reloaded), ["Chapter markers"]);
        assert_eq!(flagged_sections(&reloaded), ["Chapter markers"]);
        // It keeps its natural position between its neighbours (Uma's design), rather than
        // being appended or dropped, and it is genuinely empty.
        let order: Vec<&str> = reloaded["sections"]
            .as_array()
            .expect("sections array")
            .iter()
            .map(|s| s["heading"].as_str().expect("heading"))
            .collect();
        assert_eq!(order, ["Illustrations", "Chapter markers", "Key lessons"]);
        assert_eq!(reloaded["sections"][1]["items"], json!([]));
    }

    #[test]
    fn the_reloaded_wire_draft_equals_the_fresh_one_for_caveats_and_sections() {
        // The doc comment on `sermon_note_draft_json` promises "the same shape
        // generate_sermon_notes already returns"; for requested-but-empty content that promise
        // is the whole bug, so it is asserted as an equality, over every kind of caveat at once.
        let d = draft(
            None,
            vec![
                NoteSection::outline(
                    OUTLINE_HEADING,
                    vec![NotePoint {
                        text: "Be faithful".into(),
                        sub_points: vec!["In little".into()],
                    }],
                ),
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Chapter markers", Vec::new()),
                NoteSection::flat("Prayer points", Vec::new()),
            ],
            &[],
            vec![
                caveat(SUMMARY),
                caveat(SCRIPTURES),
                caveat("Chapter markers"),
                caveat("Prayer points"),
            ],
        );
        let fresh = draft_json(&d);
        let reloaded = reload(&d);
        assert_eq!(reloaded["sections"], fresh["sections"]);
        assert_eq!(reloaded["caveats"], fresh["caveats"]);
        assert_eq!(reloaded["summary"], fresh["summary"]);
        assert_eq!(reloaded["scriptures"], fresh["scriptures"]);
    }

    // --- every kind of caveat, several at once --------------------------------------------------

    #[test]
    fn the_two_non_section_caveats_survive_a_reload() {
        // `Summary` and `Scripture references` are requested fields, not sections: they are
        // why the caveat cannot live on the section objects alone.
        let d = draft(None, vec![], &[], vec![caveat(SUMMARY), caveat(SCRIPTURES)]);
        assert_eq!(caveat_headings(&reload(&d)), [SUMMARY, SCRIPTURES]);
    }

    #[test]
    fn several_empty_sections_all_survive_in_generation_order() {
        let d = draft(
            None,
            vec![
                NoteSection::flat("Prayer points", Vec::new()),
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Key lessons", Vec::new()),
                NoteSection::flat("Chapter markers", Vec::new()),
            ],
            &[],
            vec![
                caveat("Prayer points"),
                caveat("Key lessons"),
                caveat("Chapter markers"),
            ],
        );
        let reloaded = reload(&d);
        assert_eq!(
            caveat_headings(&reloaded),
            ["Prayer points", "Key lessons", "Chapter markers"]
        );
        assert_eq!(
            flagged_sections(&reloaded),
            ["Prayer points", "Key lessons", "Chapter markers"]
        );
        // The populated neighbour is never touched.
        assert_eq!(reloaded["sections"][1]["items"], json!(["a lantern"]));
        assert_eq!(reloaded["sections"][1]["empty_requested"], false);
    }

    #[test]
    fn an_outline_section_that_came_back_empty_keeps_its_caveat() {
        let d = draft(
            None,
            vec![NoteSection::flat(OUTLINE_HEADING, Vec::new())],
            &[],
            vec![caveat(OUTLINE_HEADING)],
        );
        assert_eq!(caveat_headings(&reload(&d)), [OUTLINE_HEADING]);
    }

    // --- nothing to record: the stored shape is unchanged ----------------------------------

    #[test]
    fn a_draft_with_no_caveats_is_stored_in_the_old_shape_byte_for_byte() {
        let d = draft(
            Some("A summary"),
            vec![
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::outline(
                    OUTLINE_HEADING,
                    vec![NotePoint {
                        text: "Be faithful".into(),
                        sub_points: vec!["In little".into()],
                    }],
                ),
            ],
            &["John 3:16"],
            vec![],
        );
        assert_eq!(
            persisted_sections_json(&d),
            crate::sections_to_json(&d.sections)
        );
        // ... and the claim itself, as a literal rather than a call to the function under
        // test: these are the exact bytes a build from before this ticket wrote.
        assert_eq!(
            persisted_sections_json(&d),
            concat!(
                r#"[{"heading":"Illustrations","items":["a lantern"],"points":[]},"#,
                r#"{"heading":"Main points","items":[],"points":"#,
                r#"[{"sub_points":["In little"],"text":"Be faithful"}]}]"#
            )
        );
        assert!(persisted_sections_json(&d).starts_with('['));
        assert_eq!(caveat_headings(&reload(&d)), Vec::<String>::new());
    }

    #[test]
    fn scripture_caveats_are_recomputed_not_stored() {
        // `ScriptureUnverified` / `ScriptureVerificationIncomplete` are re-derived from the
        // stored scriptures on every load; storing them as well would be a second source of
        // truth that could disagree with the fresh check.
        let d = draft(
            None,
            vec![NoteSection::flat("Illustrations", vec!["a lantern".into()])],
            &["3 John 4:12"],
            vec![
                DraftCaveat::ScriptureUnverified {
                    reference: "3 John 4:12".into(),
                },
                DraftCaveat::ScriptureVerificationIncomplete,
            ],
        );
        let stored = persisted_sections_json(&d);
        assert_eq!(stored, crate::sections_to_json(&d.sections));
        assert!(!stored.contains("requested_empty"));
    }

    #[test]
    fn an_offline_placeholder_section_is_not_mistaken_for_a_caveat() {
        // `local.rs` pushes deliberately empty "fill this in yourself" sections and never
        // raises a caveat for them. They persist and reload exactly as before: present,
        // empty, and NOT flagged.
        let d = draft(
            None,
            vec![NoteSection::flat("Prayer points", Vec::new())],
            &[],
            vec![],
        );
        let reloaded = reload(&d);
        assert_eq!(reloaded["sections"][0]["heading"], "Prayer points");
        assert_eq!(reloaded["sections"][0]["empty_requested"], false);
        assert_eq!(caveat_headings(&reloaded), Vec::<String>::new());
    }

    // --- rows written before this ticket ---------------------------------------------------

    #[test]
    fn a_row_written_before_this_ticket_loads_exactly_as_it_did() {
        let legacy = r#"[{"heading":"Main points","items":[],"points":[{"text":"Be faithful","sub_points":["In little"]}]},{"heading":"Prayer points","items":[],"points":[]}]"#;
        let (j, _) = sermon_note_draft_json(&view(legacy.to_string(), None, &[]), &[]);
        assert_eq!(j["sections"][0]["points"][0]["text"], "Be faithful");
        assert_eq!(j["sections"][1]["heading"], "Prayer points");
        // A legacy row cannot say whether its empty section was requested, so it must not
        // be claimed to have been.
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
        assert_eq!(flagged_sections(&j), Vec::<String>::new());
    }

    #[test]
    fn a_legacy_row_with_the_caveated_section_already_dropped_gains_nothing() {
        // What 86akc0tua's `sections_to_persist` stored. The section is gone for good; the
        // reload shows no section and invents no caveat for it.
        let legacy = r#"[{"heading":"Illustrations","items":["a lantern"],"points":[]}]"#;
        let (j, _) = sermon_note_draft_json(&view(legacy.to_string(), None, &[]), &[]);
        assert_eq!(j["sections"].as_array().expect("sections array").len(), 1);
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
    }

    #[test]
    fn the_plain_array_and_the_caveat_carrying_array_decode_to_the_same_sections() {
        // Equivalence between the two stored forms: only the caveat list may differ.
        let sections = vec![
            NoteSection::flat("Illustrations", vec!["a lantern".into()]),
            NoteSection::flat("Chapter markers", Vec::new()),
        ];
        let legacy = crate::sections_to_json(&sections);
        let envelope = encode_sections(&sections, &strings(&["Chapter markers"]));
        assert!(envelope.starts_with('['), "still an array of sections");
        let (from_legacy, legacy_headings) = decode_sections(&legacy);
        let (from_envelope, envelope_headings) = decode_sections(&envelope);
        assert_eq!(
            sections_from_input(from_legacy),
            sections_from_input(from_envelope)
        );
        assert!(legacy_headings.is_empty());
        assert_eq!(envelope_headings, ["Chapter markers"]);
    }

    // --- a caveat is only honoured while it is still true ----------------------------------

    #[test]
    fn filling_a_caveated_section_in_clears_its_caveat_and_keeps_the_content() {
        let filled = vec![NoteSection::flat(
            "Chapter markers",
            vec!["Opening prayer".into()],
        )];
        let stored = edited_sections_json(&filled, None, &[], &strings(&["Chapter markers"]));
        assert_eq!(
            stored,
            crate::sections_to_json(&filled),
            "no caveat left to record"
        );
        let (j, _) = sermon_note_draft_json(&view(stored, None, &[]), &[]);
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
        assert_eq!(j["sections"][0]["items"], json!(["Opening prayer"]));
        assert_eq!(j["sections"][0]["empty_requested"], false);
    }

    #[test]
    fn an_edit_that_leaves_the_section_empty_keeps_the_caveat() {
        let sections = vec![
            NoteSection::flat("Illustrations", vec!["a lantern".into()]),
            NoteSection::flat("Chapter markers", Vec::new()),
        ];
        let stored = edited_sections_json(&sections, None, &[], &strings(&["Chapter markers"]));
        let (j, _) = sermon_note_draft_json(&view(stored, None, &[]), &[]);
        assert_eq!(caveat_headings(&j), ["Chapter markers"]);
    }

    #[test]
    fn a_whitespace_only_fill_does_not_count_as_content() {
        let sections = vec![NoteSection::flat(
            "Chapter markers",
            vec!["   ".into(), "".into()],
        )];
        let kept = still_requested_empty(["Chapter markers"], None, &sections, &[]);
        assert_eq!(kept, ["Chapter markers"]);
    }

    #[test]
    fn typing_a_summary_clears_the_summary_caveat_and_a_blank_one_keeps_it() {
        let req = strings(&[SUMMARY]);
        let filled = edited_sections_json(&[], Some("It is about grace."), &[], &req);
        assert_eq!(filled, "[]");
        let blank = edited_sections_json(&[], Some("  \n"), &[], &req);
        let (j, _) = sermon_note_draft_json(&view(blank, Some("  \n"), &[]), &[]);
        assert_eq!(caveat_headings(&j), [SUMMARY]);
        let none = edited_sections_json(&[], None, &[], &req);
        let (j, _) = sermon_note_draft_json(&view(none, None, &[]), &[]);
        assert_eq!(caveat_headings(&j), [SUMMARY]);
    }

    #[test]
    fn a_scripture_list_that_gains_an_entry_clears_the_scripture_caveat() {
        let req = strings(&[SCRIPTURES]);
        assert_eq!(
            edited_sections_json(&[], None, &strings(&["John 3:16"]), &req),
            "[]"
        );
        assert!(edited_sections_json(&[], None, &[], &req).contains("requested_empty"));
    }

    #[test]
    fn a_renamed_empty_section_keeps_its_caveat_under_the_new_name_only() {
        // The edit form lets the operator rename a heading; the surface sends the headings
        // by their new names. The old name no longer matches any section, so it is dropped.
        let sections = vec![NoteSection::flat("Sunday highlights", Vec::new())];
        let stored = edited_sections_json(
            &sections,
            None,
            &[],
            &strings(&["Sunday highlights", "Chapter markers"]),
        );
        let (j, _) = sermon_note_draft_json(&view(stored, None, &[]), &[]);
        assert_eq!(caveat_headings(&j), ["Sunday highlights"]);
    }

    #[test]
    fn re_saving_a_reloaded_draft_is_stable_and_never_grows() {
        let d = draft(
            None,
            vec![
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Chapter markers", Vec::new()),
            ],
            &[],
            vec![caveat(SUMMARY), caveat("Chapter markers")],
        );
        let mut stored = persisted_sections_json(&d);
        let first = stored.clone();
        for _ in 0..5 {
            let (j, _) = sermon_note_draft_json(&view(stored.clone(), None, &[]), &[]);
            // Exactly what the edit surface does: send back the sections it was shown and the
            // headings of the caveats it was shown.
            let input: Vec<crate::NoteSectionInput> =
                serde_json::from_value(j["sections"].clone()).expect("sections shape");
            let sections = sections_from_input(input);
            stored = edited_sections_json(&sections, None, &[], &caveat_headings(&j));
        }
        assert_eq!(stored, first);
    }

    // --- regeneration (FR-129) -------------------------------------------------------------

    #[test]
    fn a_regenerated_draft_carries_its_own_caveats_not_the_previous_ones() {
        let first = draft(
            None,
            vec![NoteSection::flat("Chapter markers", Vec::new())],
            &[],
            vec![caveat("Chapter markers")],
        );
        // Same sermon regenerated: the markers now fill in, a different section comes back empty.
        let second = draft(
            None,
            vec![
                NoteSection::flat("Chapter markers", vec!["Opening prayer".into()]),
                NoteSection::flat("Prayer points", Vec::new()),
            ],
            &[],
            vec![caveat("Prayer points")],
        );
        assert_eq!(caveat_headings(&reload(&first)), ["Chapter markers"]);
        let after = reload(&second);
        assert_eq!(caveat_headings(&after), ["Prayer points"]);
        assert_eq!(flagged_sections(&after), ["Prayer points"]);
        // A regenerate that comes back with nothing to caveat is stored in the old shape.
        let clean = draft(
            None,
            vec![NoteSection::flat(
                "Chapter markers",
                vec!["Opening prayer".into()],
            )],
            &[],
            vec![],
        );
        assert_eq!(caveat_headings(&reload(&clean)), Vec::<String>::new());
    }

    // --- heading edge cases ----------------------------------------------------------------

    #[test]
    fn duplicate_empty_headings_are_all_flagged_and_listed_once() {
        let sections = vec![
            NoteSection::flat("Key lessons", Vec::new()),
            NoteSection::flat("Key lessons", Vec::new()),
        ];
        let d = draft(
            None,
            sections,
            &[],
            vec![caveat("Key lessons"), caveat("Key lessons")],
        );
        let reloaded = reload(&d);
        assert_eq!(caveat_headings(&reloaded), ["Key lessons"]);
        assert_eq!(flagged_sections(&reloaded), ["Key lessons", "Key lessons"]);
    }

    #[test]
    fn a_populated_namesake_is_never_marked_empty_and_never_hides_its_content() {
        // The dangerous case: the console renders an `empty_requested` section as "nothing
        // came back" INSTEAD of its items, so flagging a populated section would hide real
        // content. A rename can make two sections share a heading.
        let sections = vec![
            NoteSection::flat("Key lessons", Vec::new()),
            NoteSection::flat("Key lessons", vec!["Stay faithful".into()]),
        ];
        let d = draft(None, sections, &[], vec![caveat("Key lessons")]);
        let reloaded = reload(&d);
        assert_eq!(reloaded["sections"][0]["empty_requested"], true);
        assert_eq!(reloaded["sections"][1]["empty_requested"], false);
        assert_eq!(reloaded["sections"][1]["items"], json!(["Stay faithful"]));
    }

    #[test]
    fn draft_json_never_flags_a_populated_section_even_for_a_stale_caveat() {
        let d = draft(
            None,
            vec![NoteSection::flat(
                "Chapter markers",
                vec!["Opening prayer".into()],
            )],
            &[],
            vec![caveat("Chapter markers")],
        );
        let fresh = draft_json(&d);
        assert_eq!(fresh["sections"][0]["empty_requested"], false);
    }

    #[test]
    fn very_long_and_unicode_headings_round_trip_exactly() {
        // 2_000 two-byte characters: ~4 KB, stored twice (section + heading list), so well
        // inside the 15 KB column cap; the over-the-cap behaviour has its own tests below.
        let long = "\u{416}".repeat(2_000);
        let headings = [
            long.as_str(),
            "Pri\u{e8}re du soir \u{1F54A}\u{FE0F}",
            "\u{5E9}\u{5DC}\u{5D5}\u{5DD} \u{627}\u{644}\u{633}\u{644}\u{627}\u{645}",
            "e\u{301} combining",
            "quote \" backslash \\ newline \n tab \t",
        ];
        for h in headings {
            let d = draft(
                None,
                vec![NoteSection::flat(h, Vec::new())],
                &[],
                vec![caveat(h)],
            );
            let reloaded = reload(&d);
            // `assert!`, not `assert_eq!`: a failure must not dump a 2_000-character heading.
            assert!(
                caveat_headings(&reloaded) == [h],
                "caveat heading lost or altered (starts {:?})",
                h.chars().take(12).collect::<String>()
            );
            assert!(
                flagged_sections(&reloaded) == [h],
                "section flag lost or altered"
            );
        }
    }

    #[test]
    fn heading_matching_is_exact() {
        let sections = vec![NoteSection::flat("Chapter markers", Vec::new())];
        for near in [
            "chapter markers",
            "Chapter markers ",
            " Chapter markers",
            "Chapter  markers",
        ] {
            assert!(
                still_requested_empty([near], None, &sections, &[]).is_empty(),
                "{near:?} must not match"
            );
        }
        assert_eq!(
            still_requested_empty(["Chapter markers"], None, &sections, &[]),
            ["Chapter markers"]
        );
    }

    // --- stored data that cannot be trusted ------------------------------------------------

    #[test]
    fn a_stored_heading_naming_nothing_is_ignored() {
        let json = r#"[{"heading":"Illustrations","items":["a lantern"],"points":[],"requested_empty":["Chapter markers","Nonsense"]}]"#;
        let (j, _) = sermon_note_draft_json(&view(json.to_string(), None, &[]), &[]);
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
        assert_eq!(j["sections"][0]["items"], json!(["a lantern"]));
    }

    #[test]
    fn a_stored_label_is_ignored_once_the_field_it_names_has_content() {
        let json = r#"{"sections":[],"requested_empty":["Summary","Scripture references"]}"#;
        let v = view(
            json.to_string(),
            Some("Real summary"),
            &strings(&["John 3:16"]),
        );
        let (j, _) = sermon_note_draft_json(&v, &[]);
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
    }

    /// A stored array of two empty sections whose first carries `list` as `requested_empty`.
    fn stored_with_list(list: &[Value]) -> String {
        json!([
            {"heading": "Chapter markers", "items": [], "points": [], "requested_empty": list},
            {"heading": "Prayer points", "items": [], "points": []},
        ])
        .to_string()
    }

    #[test]
    fn a_long_heading_list_within_the_cap_is_collected_only_up_to_the_window() {
        // Bounded-memory test that bites: ~1,500 entries (about 12 KB, so UNDER the 15 KB read
        // cap and parsed for caveats) must come out as at most MAX_STORED_HEADINGS strings.
        // Removing the collection window turns this red (it would return all 1,500).
        let mut list: Vec<Value> = (0..1_500).map(|i| json!(format!("j{i}"))).collect();
        list.insert(0, json!("Chapter markers"));
        list.push(json!("Prayer points")); // real, but past the window
        let stored = stored_with_list(&list);
        assert!(
            stored.len() < MAX_SECTIONS_JSON_BYTES,
            "premise: under the cap, got {}",
            stored.len()
        );
        let (sections, headings) = decode_sections(&stored);
        assert_eq!(
            sections.len(),
            2,
            "the sections are untouched by the window"
        );
        assert!(
            headings.len() <= MAX_STORED_HEADINGS,
            "collected {} entries",
            headings.len()
        );
        assert_eq!(headings.len(), MAX_STORED_HEADINGS);
        let (j, _) = sermon_note_draft_json(&view(stored, None, &[]), &[]);
        assert_eq!(
            caveat_headings(&j),
            ["Chapter markers"],
            "only the window counts; Prayer points is past it"
        );
    }

    #[test]
    fn a_value_over_the_write_cap_is_read_for_sections_only_never_for_caveats() {
        // A row from a build with the old 200 000-byte cap, or a LAN writer: 200,000 junk
        // entries, a real heading FIRST (so a window alone would still honour it). Over the
        // cap the new work is not done at all, but the sections load exactly as they always
        // did. Removing the size check turns this red.
        let mut list: Vec<Value> = (0..200_000).map(|i| json!(format!("junk {i}"))).collect();
        list.insert(0, json!("Chapter markers"));
        let stored = stored_with_list(&list);
        assert!(
            stored.len() > MAX_SECTIONS_JSON_BYTES * 100,
            "premise: far over the cap"
        );
        let (sections, headings) = decode_sections(&stored);
        assert_eq!(
            sections.len(),
            2,
            "sections still load, as before this ticket"
        );
        assert!(headings.is_empty(), "no caveat work over the cap");
        let (j, _) = sermon_note_draft_json(&view(stored, None, &[]), &[]);
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
        assert_eq!(j["sections"][1]["heading"], "Prayer points");
    }

    #[test]
    fn the_candidate_window_is_a_constant_not_a_function_of_the_input() {
        let many: Vec<String> = (0..MAX_STORED_HEADINGS * 4)
            .map(|i| format!("h{i}"))
            .collect();
        let sections: Vec<NoteSection> = many
            .iter()
            .map(|h| NoteSection::flat(h.clone(), Vec::new()))
            .collect();
        let kept = still_requested_empty(many.iter().map(String::as_str), None, &sections, &[]);
        assert_eq!(kept.len(), MAX_STORED_HEADINGS);
    }

    #[test]
    fn non_string_entries_degrade_only_the_caveat_never_the_sections() {
        let json = r#"[{"heading":"Chapter markers","items":[],"points":[],"requested_empty":[7,null,{"a":1},["x"],"Chapter markers"]}]"#;
        let (j, _) = sermon_note_draft_json(&view(json.to_string(), None, &[]), &[]);
        assert_eq!(j["sections"][0]["heading"], "Chapter markers");
        assert_eq!(caveat_headings(&j), ["Chapter markers"]);
    }

    #[test]
    fn malformed_stored_sections_degrade_to_an_empty_draft_without_panicking() {
        for bad in [
            "",
            "null",
            "7",
            "\"text\"",
            "{}",
            "[1,2]",
            r#"{"sections":"nope"}"#,
            r#"{"sections":[{"no_heading":true}],"requested_empty":[]}"#,
            "{\"sections\":[",
        ] {
            let (j, _) = sermon_note_draft_json(&view(bad.to_string(), None, &[]), &[]);
            assert_eq!(j["sections"], json!([]), "input {bad:?}");
            assert_eq!(caveat_headings(&j), Vec::<String>::new(), "input {bad:?}");
        }
    }

    // --- size: a caveat must never cost the draft ------------------------------------------

    /// A draft whose populated section is padded so the envelope is exactly `target` bytes.
    fn padded_draft_with_envelope_of(target: usize) -> NoteDraft {
        let build = |pad: usize| {
            draft(
                None,
                vec![
                    NoteSection::flat("Illustrations", vec!["x".repeat(pad)]),
                    NoteSection::flat("Chapter markers", Vec::new()),
                ],
                &[],
                vec![caveat("Chapter markers")],
            )
        };
        let base = persisted_sections_json(&build(10)).len();
        build(10 + target - base)
    }

    #[test]
    fn a_draft_exactly_at_the_cap_keeps_its_caveat() {
        let d = padded_draft_with_envelope_of(MAX_SECTIONS_JSON_BYTES);
        let stored = persisted_sections_json(&d);
        assert_eq!(stored.len(), MAX_SECTIONS_JSON_BYTES);
        assert!(
            stored.contains("requested_empty"),
            "at the cap the caveat still fits"
        );
        assert_eq!(caveat_headings(&reload(&d)), ["Chapter markers"]);
    }

    #[test]
    fn a_draft_one_byte_over_the_cap_yields_the_caveat_not_the_draft() {
        let d = padded_draft_with_envelope_of(MAX_SECTIONS_JSON_BYTES + 1);
        let stored = persisted_sections_json(&d);
        assert!(
            stored.len() <= MAX_SECTIONS_JSON_BYTES,
            "the store would refuse this and the whole draft would be lost: {}",
            stored.len()
        );
        let reloaded = reload(&d);
        assert_eq!(reloaded["sections"][0]["heading"], "Illustrations");
        assert_eq!(
            reloaded["sections"][0]["items"][0].as_str().map(str::len),
            d.sections[0].items()[0].len().into(),
            "the populated content is intact"
        );
        // The documented degrade: exactly what was stored before this ticket, so the bare
        // caveated heading is OMITTED, not kept as an unexplained empty section.
        assert!(!stored.contains("requested_empty"));
        assert_eq!(reloaded["sections"].as_array().expect("array").len(), 1);
        assert_eq!(caveat_headings(&reloaded), Vec::<String>::new());
    }

    // --- the two command-level mappings -------------------------------------------------------

    fn outcome_of(d: NoteDraft, ai_generated: bool) -> selahcue_cloud::GenerationOutcome {
        selahcue_cloud::GenerationOutcome {
            draft: d,
            provider_label: "SelahCue AI".to_string(),
            degraded: !ai_generated,
            quota: None,
            ai_generated,
            disclosure: ai_generated.then_some("AI-generated. Verify before use."),
        }
    }

    #[test]
    fn the_saved_input_for_a_generated_draft_carries_its_caveats_and_the_rest_unchanged() {
        let d = draft(
            Some("A summary"),
            vec![
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Chapter markers", Vec::new()),
            ],
            &["John 3:16"],
            vec![caveat("Chapter markers")],
        );
        let input = draft_input_for(&outcome_of(d.clone(), true));
        assert_eq!(input.title, d.title);
        assert_eq!(input.summary.as_deref(), Some("A summary"));
        assert_eq!(input.scriptures_json, r#"["John 3:16"]"#);
        assert!(input.ai_generated);
        assert_eq!(
            input.disclosure.as_deref(),
            Some("AI-generated. Verify before use.")
        );
        assert_eq!(input.provider, "SelahCue AI");
        assert_eq!(input.model, None);
        let reloaded = sermon_note_draft_json(
            &view(
                input.sections_json,
                Some("A summary"),
                &strings(&["John 3:16"]),
            ),
            &[],
        )
        .0;
        assert_eq!(caveat_headings(&reloaded), ["Chapter markers"]);
    }

    #[test]
    fn the_saved_input_for_a_degraded_draft_has_no_caveats_and_no_disclosure() {
        // The offline scaffold: no caveats by construction, not AI-generated, so no disclosure.
        let d = draft(
            None,
            vec![NoteSection::flat("Prayer points", Vec::new())],
            &[],
            vec![],
        );
        let input = draft_input_for(&outcome_of(d.clone(), false));
        assert!(!input.ai_generated);
        assert_eq!(input.disclosure, None);
        assert_eq!(input.sections_json, crate::sections_to_json(&d.sections));
    }

    fn form_sections() -> Vec<crate::NoteSectionInput> {
        serde_json::from_value(json!([
            {"heading": "Illustrations", "items": ["a lantern"], "points": []},
            {"heading": "Chapter markers", "items": [], "points": []},
        ]))
        .expect("form sections")
    }

    #[test]
    fn the_saved_input_for_an_edit_keeps_the_caveats_the_form_reports() {
        let req = strings(&["Chapter markers", SUMMARY]);
        let input = edit_input_for(
            "New title".to_string(),
            None,
            form_sections(),
            &[],
            Some(&req),
            None,
        );
        assert_eq!(input.title, "New title");
        assert_eq!(input.summary, None);
        assert_eq!(input.scriptures_json, "[]");
        let j = sermon_note_draft_json(&view(input.sections_json, None, &[]), &[]).0;
        assert_eq!(caveat_headings(&j), ["Chapter markers", SUMMARY]);
    }

    #[test]
    fn an_edit_that_omits_the_list_and_has_nothing_stored_stores_the_plain_array() {
        let input = edit_input_for("t".to_string(), None, form_sections(), &[], None, None);
        assert_eq!(
            input.sections_json,
            r#"[{"heading":"Illustrations","items":["a lantern"],"points":[]},{"heading":"Chapter markers","items":[],"points":[]}]"#
        );
    }

    #[test]
    fn an_edit_that_omits_the_list_keeps_the_stored_caveats_that_are_still_true() {
        // `None` means "unknown", never "none": the webview ships with this binary, so an
        // omitted argument can only be a bug, and a bug must not silently wipe caveats.
        let stored = encode_sections(
            &[
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Chapter markers", Vec::new()),
                NoteSection::flat("Prayer points", Vec::new()),
            ],
            &strings(&["Chapter markers", "Prayer points", SUMMARY]),
        );
        // The edit fills Prayer points in and types a summary; Chapter markers stays empty.
        let sections: Vec<crate::NoteSectionInput> = serde_json::from_value(json!([
            {"heading": "Illustrations", "items": ["a lantern"], "points": []},
            {"heading": "Chapter markers", "items": [], "points": []},
            {"heading": "Prayer points", "items": ["Thank God"], "points": []},
        ]))
        .expect("sections");
        let input = edit_input_for(
            "t".to_string(),
            Some("Now a summary".to_string()),
            sections,
            &[],
            None,
            Some(&stored),
        );
        let j =
            sermon_note_draft_json(&view(input.sections_json, Some("Now a summary"), &[]), &[]).0;
        assert_eq!(caveat_headings(&j), ["Chapter markers"]);
    }

    #[test]
    fn an_edit_that_reports_an_empty_list_clears_every_caveat() {
        // `Some(&[])` is authoritative, unlike `None`.
        let stored = encode_sections(
            &[NoteSection::flat("Chapter markers", Vec::new())],
            &strings(&["Chapter markers"]),
        );
        let sections: Vec<crate::NoteSectionInput> = serde_json::from_value(json!([
            {"heading": "Chapter markers", "items": [], "points": []},
        ]))
        .expect("sections");
        let input = edit_input_for(
            "t".to_string(),
            None,
            sections,
            &[],
            Some(&[]),
            Some(&stored),
        );
        assert!(!input.sections_json.contains("requested_empty"));
    }

    #[test]
    fn an_edit_that_types_a_summary_stores_it_and_drops_the_summary_caveat() {
        let req = strings(&[SUMMARY]);
        let input = edit_input_for(
            "t".to_string(),
            Some("Now there is one.".to_string()),
            Vec::new(),
            &[],
            Some(&req),
            None,
        );
        assert_eq!(input.summary.as_deref(), Some("Now there is one."));
        assert_eq!(input.sections_json, "[]");
    }

    // --- downgrade safety: what a build from BEFORE this ticket makes of the stored value ------

    /// The pre-change reader, verbatim: `sermon_note_draft_json` used to do exactly
    /// `serde_json::from_str::<Vec<NoteSectionInput>>(&v.sections_json).unwrap_or_default()`.
    fn old_reader(sections_json: &str) -> Vec<NoteSection> {
        let input: Vec<crate::NoteSectionInput> =
            serde_json::from_str(sections_json).unwrap_or_default();
        sections_from_input(input)
    }

    #[test]
    fn an_older_build_still_reads_every_section_of_a_draft_that_carries_caveats() {
        let sections = vec![
            NoteSection::flat("Illustrations", vec!["a lantern".into()]),
            NoteSection::flat("Chapter markers", Vec::new()),
            NoteSection::outline(
                OUTLINE_HEADING,
                vec![NotePoint {
                    text: "Be faithful".into(),
                    sub_points: vec!["In little".into()],
                }],
            ),
            NoteSection::flat("Prayer points", Vec::new()),
        ];
        let d = draft(
            None,
            sections.clone(),
            &[],
            vec![
                caveat("Chapter markers"),
                caveat("Prayer points"),
                caveat(SUMMARY),
            ],
        );
        let stored = persisted_sections_json(&d);
        assert!(
            stored.contains("requested_empty"),
            "premise: caveats were recorded"
        );
        assert_eq!(
            old_reader(&stored),
            sections,
            "an older build must get every section back, populated ones included"
        );
        // Without caveats it is the plain array, trivially readable.
        let plain = persisted_sections_json(&draft(None, sections.clone(), &[], vec![]));
        assert_eq!(old_reader(&plain), sections);
    }

    #[test]
    fn an_older_build_that_edit_saves_a_caveat_carrying_draft_loses_the_caveat_and_no_section() {
        // The downgrade-then-edit consequence, end to end: older build reads, edits the title,
        // writes with the OLD serialiser. Real sections survive; only the caveat is gone.
        let sections = vec![
            NoteSection::flat("Illustrations", vec!["a lantern".into()]),
            NoteSection::flat("Chapter markers", Vec::new()),
        ];
        let stored = persisted_sections_json(&draft(
            None,
            sections.clone(),
            &[],
            vec![caveat("Chapter markers")],
        ));
        let written_by_old_build = crate::sections_to_json(&old_reader(&stored));
        assert_eq!(old_reader(&written_by_old_build), sections);
        assert!(!written_by_old_build.contains("requested_empty"));
        // And this build, reading what the old build wrote, simply shows no caveat.
        let (j, _) = sermon_note_draft_json(&view(written_by_old_build, None, &[]), &[]);
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
        assert_eq!(j["sections"].as_array().expect("array").len(), 2);
    }

    #[test]
    fn a_draft_with_no_sections_uses_the_object_shape_and_loses_nothing_to_an_older_build() {
        // The one object shape: only when there is no section an older build could lose.
        let d = draft(None, vec![], &[], vec![caveat(SUMMARY), caveat(SCRIPTURES)]);
        let stored = persisted_sections_json(&d);
        assert_eq!(
            stored,
            r#"{"requested_empty":["Summary","Scripture references"],"sections":[]}"#
        );
        assert_eq!(old_reader(&stored), Vec::<NoteSection>::new());
        assert_eq!(caveat_headings(&reload(&d)), [SUMMARY, SCRIPTURES]);
    }

    #[test]
    fn the_extra_key_is_only_honoured_on_the_first_section() {
        let json = r#"[{"heading":"A","items":[],"points":[]},{"heading":"B","items":[],"points":[],"requested_empty":["B"]}]"#;
        let (j, _) = sermon_note_draft_json(&view(json.to_string(), None, &[]), &[]);
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
        assert_eq!(j["sections"].as_array().expect("array").len(), 2);
    }

    #[test]
    fn unknown_keys_in_the_stored_value_are_ignored() {
        // Forward compatibility depends on this: a future additive key must not break a reader
        // built from this code. Unknown keys on a section, on the no-sections object, and a
        // deeply nested one.
        let on_section = r#"[{"heading":"A","items":["kept"],"points":[],"requested_empty":["A"],"future":{"x":[[[[1]]]]}}]"#;
        let (sections, headings) = decode_sections(on_section);
        assert_eq!(sections_from_input(sections)[0].items(), ["kept"]);
        assert!(headings.contains(&"A".to_string()));
        let on_object = r#"{"sections":[],"requested_empty":["Summary"],"future":[1,2,3]}"#;
        assert_eq!(decode_sections(on_object).1, ["Summary"]);
    }

    // --- a damaged requested_empty field costs the caveats, never the sections ----------------

    #[test]
    fn a_wrong_typed_requested_empty_field_never_costs_the_sections() {
        for bad in [
            r#""text""#,
            "null",
            "7",
            r#"{"a":1}"#,
            "true",
            "[[1]]",
            r#"[{"a":1}]"#,
        ] {
            let on_section = format!(
                r#"[{{"heading":"A","items":["kept"],"points":[],"requested_empty":{bad}}}]"#
            );
            let (sections, headings) = decode_sections(&on_section);
            assert_eq!(sections.len(), 1, "sections lost for requested_empty={bad}");
            assert!(headings.is_empty(), "requested_empty={bad}");
            let (j, _) = sermon_note_draft_json(&view(on_section, None, &[]), &[]);
            assert_eq!(
                j["sections"][0]["items"],
                json!(["kept"]),
                "requested_empty={bad}"
            );

            let on_object = format!(r#"{{"sections":[],"requested_empty":{bad}}}"#);
            let (sections, headings) = decode_sections(&on_object);
            assert!(
                sections.is_empty() && headings.is_empty(),
                "object, requested_empty={bad}"
            );
        }
    }

    // --- the shape is chosen by the first non-space byte -------------------------------------

    #[test]
    fn leading_whitespace_does_not_change_how_the_value_is_read() {
        let arr = format!(
            "  \n\t{}",
            r#"[{"heading":"A","items":[],"points":[],"requested_empty":["A"]}]"#
        );
        assert_eq!(decode_sections(&arr).1, ["A"]);
        let obj = format!("\n {}", r#"{"sections":[],"requested_empty":["Summary"]}"#);
        assert_eq!(decode_sections(&obj).1, ["Summary"]);
        for other in ["", "   ", "null", "\"x\"", "7", "true", "x"] {
            let (s, h) = decode_sections(other);
            assert!(s.is_empty() && h.is_empty(), "{other:?}");
        }
    }

    // --- the "empty" rule, and the corners around it -------------------------------------------

    #[test]
    fn an_outline_point_with_blank_text_but_a_real_sub_point_is_not_empty() {
        // The sub-point arm of `section_is_empty`: dropping it would let a stale caveat mark
        // this populated outline "nothing came back" and hide the sub-point.
        let outline = NoteSection::outline(
            OUTLINE_HEADING,
            vec![NotePoint {
                text: String::new(),
                sub_points: vec!["real".into()],
            }],
        );
        assert!(!section_is_empty(&outline));
        let d = draft(None, vec![outline], &[], vec![caveat(OUTLINE_HEADING)]);
        let reloaded = reload(&d);
        assert_eq!(caveat_headings(&reloaded), Vec::<String>::new());
        assert_eq!(reloaded["sections"][0]["empty_requested"], false);
        assert_eq!(
            reloaded["sections"][0]["points"][0]["sub_points"],
            json!(["real"])
        );
        // The mirror: blank text AND only blank sub-points is empty.
        let blank = NoteSection::outline(
            OUTLINE_HEADING,
            vec![NotePoint {
                text: " ".into(),
                sub_points: vec!["  ".into()],
            }],
        );
        assert!(section_is_empty(&blank));
    }

    #[test]
    fn a_blank_heading_names_nothing_and_is_never_a_caveat() {
        // Decision (Quinn X2): an empty section whose heading was blanked in the edit form is
        // not given a caveat, whatever is stored, because there is no name to show it under.
        for h in ["", "  ", "\t"] {
            let sections = vec![NoteSection::flat(h, Vec::new())];
            let stored = edited_sections_json(&sections, None, &[], &[h.to_string()]);
            assert_eq!(stored, crate::sections_to_json(&sections), "heading {h:?}");
            let (j, _) = sermon_note_draft_json(&view(stored, None, &[]), &[]);
            assert_eq!(caveat_headings(&j), Vec::<String>::new(), "heading {h:?}");
        }
    }

    #[test]
    fn the_reserved_labels_win_over_a_section_with_the_same_name() {
        // Pinned behaviours (Quinn X4b, Cody N4), not endorsements.
        //
        // 1. An EMPTY section renamed "Summary" while the summary has text: the label is judged
        //    by the SUMMARY, so the caveat is dropped and a bare heading remains.
        let sections = vec![NoteSection::flat("Summary", Vec::new())];
        let stored = edited_sections_json(&sections, Some("has text"), &[], &strings(&["Summary"]));
        let (j, _) = sermon_note_draft_json(&view(stored, Some("has text"), &[]), &[]);
        assert_eq!(caveat_headings(&j), Vec::<String>::new());
        assert_eq!(j["sections"][0]["empty_requested"], false);
        // 2. The same empty section while the summary is blank: the Summary caveat holds, and
        //    draft_json also flags the empty namesake section.
        let stored = edited_sections_json(&sections, None, &[], &strings(&["Summary"]));
        let (j, _) = sermon_note_draft_json(&view(stored, None, &[]), &[]);
        assert_eq!(caveat_headings(&j), ["Summary"]);
        assert_eq!(j["sections"][0]["empty_requested"], true);
        // 3. A POPULATED section named "Summary" is never hidden by the Summary caveat.
        let populated = vec![NoteSection::flat("Summary", vec!["real".into()])];
        let stored = edited_sections_json(&populated, None, &[], &strings(&["Summary"]));
        let (j, _) = sermon_note_draft_json(&view(stored, None, &[]), &[]);
        assert_eq!(j["sections"][0]["empty_requested"], false);
        assert_eq!(j["sections"][0]["items"], json!(["real"]));
    }

    #[test]
    fn a_whitespace_only_summary_is_blank_to_the_server() {
        // `transcripts.js` renders any non-empty summary string, so a "   " summary shows as a
        // blank line next to the caveat; the server's reading (blank) is the honest one.
        assert_eq!(
            still_requested_empty([SUMMARY], Some("   \n"), &[], &[]),
            [SUMMARY]
        );
        assert!(still_requested_empty([SUMMARY], Some("x"), &[], &[]).is_empty());
    }

    // --- the size fallback ---------------------------------------------------------------------

    #[test]
    fn the_size_fallback_keeps_a_populated_namesake_of_an_empty_caveated_section() {
        // Over the cap the empty caveated sections are left out, but a POPULATED section that
        // shares a heading with one of them must stay. Removing the emptiness half of the
        // fallback filter would drop it.
        let build = |pad: usize| {
            vec![
                NoteSection::flat("Key lessons", vec!["x".repeat(pad)]),
                NoteSection::flat("Key lessons", Vec::new()),
            ]
        };
        let req = strings(&["Key lessons"]);
        let base = edited_sections_json(&build(10), None, &[], &req).len();
        let over = build(10 + MAX_SECTIONS_JSON_BYTES + 1 - base);
        let stored = edited_sections_json(&over, None, &[], &req);
        assert!(stored.len() <= MAX_SECTIONS_JSON_BYTES);
        let got = old_reader(&stored);
        assert_eq!(got.len(), 1, "only the empty namesake is left out");
        assert_eq!(got[0].items()[0].len(), over[0].items()[0].len());
    }

    #[test]
    fn the_edit_path_has_the_same_cap_boundary_as_the_generate_path() {
        for over in [0usize, 1] {
            let build = |pad: usize| {
                vec![
                    NoteSection::flat("Illustrations", vec!["x".repeat(pad)]),
                    NoteSection::flat("Chapter markers", Vec::new()),
                ]
            };
            let req = strings(&["Chapter markers"]);
            let base = edited_sections_json(&build(10), None, &[], &req).len();
            let stored = edited_sections_json(
                &build(10 + MAX_SECTIONS_JSON_BYTES + over - base),
                None,
                &[],
                &req,
            );
            assert!(stored.len() <= MAX_SECTIONS_JSON_BYTES, "over={over}");
            assert_eq!(stored.contains("requested_empty"), over == 0, "over={over}");
        }
    }
}

/// The same guarantees through the REAL store (`selahcue-data`'s sermon-note repo, a real
/// file, reopened), and through every command-level function that reloads a draft. The unit
/// tests above prove the codec; these prove nothing between the codec and the disk, or between
/// the disk and the console, loses the caveat again.
#[cfg(test)]
mod store_tests {
    use super::support::{caveat, caveat_headings};
    use super::*;
    use crate::{build_transcript_detail_view, sermon_note_draft_json, sermon_note_view_ok_json};
    #[cfg(feature = "openai-notes")]
    use selahcue_core::providers::IncludeInNotes;
    use selahcue_data::sermon_note_repo::{self, DraftEdit, NewSermonNote, PendingRegeneration};
    use selahcue_data::{transcript_repo, Database};
    use selahcue_lan::protocol::SermonNoteDraftView;
    use serde_json::Value;

    /// A generated draft with `Chapter markers` and `Prayer points` requested but empty.
    fn generated_with_two_empty() -> NoteDraft {
        NoteDraft {
            title: "Faith that Endures".to_string(),
            summary: None,
            sections: vec![
                NoteSection::flat("Illustrations", vec!["a lantern".to_string()]),
                NoteSection::flat("Chapter markers", Vec::new()),
                NoteSection::flat("Prayer points", Vec::new()),
            ],
            scriptures: Vec::new(),
            caveats: vec![caveat("Chapter markers"), caveat("Prayer points")],
            scripture_verdicts: Vec::new(),
            timestamps: Vec::new(),
        }
    }

    fn new_transcript(db: &Database) -> i64 {
        transcript_repo::create(
            db,
            &transcript_repo::NewTranscript {
                label: "Sunday Service".to_string(),
                provider: "manual".to_string(),
                plan_id: None,
                started_at_ms: 1_000,
            },
        )
        .expect("create transcript")
    }

    fn note_of(transcript_id: i64, d: &NoteDraft) -> NewSermonNote {
        NewSermonNote {
            transcript_id,
            title: d.title.clone(),
            summary: d.summary.clone(),
            sections_json: persisted_sections_json(d),
            scriptures_json: crate::scriptures_to_json(&d.scriptures),
            ai_generated: true,
            disclosure: Some("AI-generated. Verify before use.".to_string()),
            provider: "SelahCue AI".to_string(),
            model: None,
            created_at_ms: 1_000,
        }
    }

    fn pending_of(d: &NoteDraft) -> PendingRegeneration {
        PendingRegeneration {
            title: d.title.clone(),
            summary: d.summary.clone(),
            sections_json: persisted_sections_json(d),
            scriptures_json: crate::scriptures_to_json(&d.scriptures),
            ai_generated: true,
            disclosure: Some("AI-generated. Verify before use.".to_string()),
            provider: "SelahCue AI".to_string(),
            model: None,
            generated_at_ms: 2_000,
        }
    }

    fn view_of(r: &sermon_note_repo::SermonNoteRecord) -> SermonNoteDraftView {
        SermonNoteDraftView {
            title: r.title.clone(),
            summary: r.summary.clone(),
            sections_json: r.sections_json.clone(),
            scriptures_json: r.scriptures_json.clone(),
            ai_generated: r.ai_generated,
            disclosure: r.disclosure.clone(),
            provider: r.provider.clone(),
            model: r.model.clone(),
            created_at_ms: r.created_at_ms,
            edited_at_ms: r.edited_at_ms,
        }
    }

    fn loaded(db: &Database, transcript_id: i64) -> Value {
        let record = sermon_note_repo::find_by_transcript(db, transcript_id)
            .expect("find")
            .expect("a draft is stored");
        sermon_note_draft_json(&view_of(&record), &[]).0
    }

    #[test]
    fn the_caveats_survive_an_app_restart() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("selahcue.db");
        let transcript_id = {
            let db = Database::open(&path).expect("open");
            let id = new_transcript(&db);
            sermon_note_repo::create(&db, &note_of(id, &generated_with_two_empty()))
                .expect("persist");
            assert_eq!(
                caveat_headings(&loaded(&db, id)),
                ["Chapter markers", "Prayer points"],
                "sanity: present before the restart"
            );
            id
            // `db` dropped here: the connection is closed, nothing is held in memory.
        };
        let reopened = Database::open(&path).expect("reopen");
        let j = loaded(&reopened, transcript_id);
        assert_eq!(caveat_headings(&j), ["Chapter markers", "Prayer points"]);
        assert_eq!(j["sections"][1]["empty_requested"], true);
        assert_eq!(j["sections"][2]["empty_requested"], true);
        assert_eq!(j["sections"][0]["empty_requested"], false);
    }

    #[test]
    fn an_edit_save_keeps_the_caveats_it_was_shown_across_a_restart() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("selahcue.db");
        let transcript_id = {
            let db = Database::open(&path).expect("open");
            let id = new_transcript(&db);
            sermon_note_repo::create(&db, &note_of(id, &generated_with_two_empty()))
                .expect("persist");
            // Exactly what `update_sermon_note_draft` does with the edit form's payload: a new
            // title, every section as shown, and the headings of the caveats that were shown.
            let shown = loaded(&db, id);
            let input: Vec<crate::NoteSectionInput> =
                serde_json::from_value(shown["sections"].clone()).expect("sections shape");
            let sections = crate::sections_from_input(input);
            sermon_note_repo::update(
                &db,
                id,
                &DraftEdit {
                    title: "A better title".to_string(),
                    summary: None,
                    sections_json: edited_sections_json(
                        &sections,
                        None,
                        &[],
                        &caveat_headings(&shown),
                    ),
                    scriptures_json: "[]".to_string(),
                },
                3_000,
            )
            .expect("update");
            id
        };
        let reopened = Database::open(&path).expect("reopen");
        let j = loaded(&reopened, transcript_id);
        assert_eq!(j["title"], "A better title");
        assert_eq!(caveat_headings(&j), ["Chapter markers", "Prayer points"]);
    }

    #[test]
    fn filling_one_caveated_section_in_clears_only_that_caveat_across_a_restart() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("selahcue.db");
        let transcript_id = {
            let db = Database::open(&path).expect("open");
            let id = new_transcript(&db);
            sermon_note_repo::create(&db, &note_of(id, &generated_with_two_empty()))
                .expect("persist");
            let sections = vec![
                NoteSection::flat("Illustrations", vec!["a lantern".to_string()]),
                NoteSection::flat("Chapter markers", vec!["Opening prayer".to_string()]),
                NoteSection::flat("Prayer points", Vec::new()),
            ];
            sermon_note_repo::update(
                &db,
                id,
                &DraftEdit {
                    title: "Faith that Endures".to_string(),
                    summary: None,
                    sections_json: edited_sections_json(
                        &sections,
                        None,
                        &[],
                        &["Chapter markers".to_string(), "Prayer points".to_string()],
                    ),
                    scriptures_json: "[]".to_string(),
                },
                3_000,
            )
            .expect("update");
            id
        };
        let reopened = Database::open(&path).expect("reopen");
        let j = loaded(&reopened, transcript_id);
        assert_eq!(caveat_headings(&j), ["Prayer points"]);
        assert_eq!(
            j["sections"][1]["items"],
            serde_json::json!(["Opening prayer"])
        );
        assert_eq!(j["sections"][1]["empty_requested"], false);
    }

    #[test]
    fn a_staged_regeneration_does_not_disturb_the_accepted_drafts_caveats() {
        let db = Database::open_in_memory().expect("open");
        let id = new_transcript(&db);
        sermon_note_repo::create(&db, &note_of(id, &generated_with_two_empty())).expect("persist");

        let mut regenerated = generated_with_two_empty();
        regenerated.sections[1] =
            NoteSection::flat("Chapter markers", vec!["Opening prayer".to_string()]);
        regenerated.caveats = vec![caveat("Prayer points")];
        sermon_note_repo::stage_regeneration(&db, id, &pending_of(&regenerated)).expect("stage");

        // FR-129: the accepted draft is untouched, caveats included.
        assert_eq!(
            caveat_headings(&loaded(&db, id)),
            ["Chapter markers", "Prayer points"]
        );
        // And the pending draft's own caveats are its own.
        let record = sermon_note_repo::find_by_transcript(&db, id)
            .expect("find")
            .expect("a draft is stored");
        let pending = record.pending.expect("staged");
        let pending_view = SermonNoteDraftView {
            title: pending.title,
            summary: pending.summary,
            sections_json: pending.sections_json,
            scriptures_json: pending.scriptures_json,
            ai_generated: pending.ai_generated,
            disclosure: pending.disclosure,
            provider: pending.provider,
            model: pending.model,
            created_at_ms: pending.generated_at_ms,
            edited_at_ms: pending.generated_at_ms,
        };
        let pending_json = sermon_note_draft_json(&pending_view, &[]).0;
        assert_eq!(caveat_headings(&pending_json), ["Prayer points"]);
    }

    #[test]
    fn confirming_a_regeneration_replaces_the_caveats_with_the_new_drafts() {
        let db = Database::open_in_memory().expect("open");
        let id = new_transcript(&db);
        sermon_note_repo::create(&db, &note_of(id, &generated_with_two_empty())).expect("persist");

        let mut regenerated = generated_with_two_empty();
        regenerated.sections[1] =
            NoteSection::flat("Chapter markers", vec!["Opening prayer".to_string()]);
        regenerated.caveats = vec![caveat("Prayer points")];
        sermon_note_repo::stage_regeneration(&db, id, &pending_of(&regenerated)).expect("stage");
        let confirmed = sermon_note_repo::confirm_regeneration(&db, id).expect("confirm");

        // The confirm/discard/update reply the console renders from.
        let reply = sermon_note_view_ok_json(id, &view_of(&confirmed), &[]);
        assert_eq!(caveat_headings(&reply["draft"]), ["Prayer points"]);
        assert_eq!(caveat_headings(&loaded(&db, id)), ["Prayer points"]);
    }

    #[test]
    fn discarding_a_regeneration_keeps_the_accepted_drafts_caveats() {
        let db = Database::open_in_memory().expect("open");
        let id = new_transcript(&db);
        sermon_note_repo::create(&db, &note_of(id, &generated_with_two_empty())).expect("persist");
        let mut regenerated = generated_with_two_empty();
        regenerated.caveats = Vec::new();
        sermon_note_repo::stage_regeneration(&db, id, &pending_of(&regenerated)).expect("stage");
        sermon_note_repo::discard_regeneration(&db, id).expect("discard");
        assert_eq!(
            caveat_headings(&loaded(&db, id)),
            ["Chapter markers", "Prayer points"]
        );
    }

    #[test]
    fn opening_the_transcript_shows_the_caveats_on_its_saved_notes() {
        // The Transcripts workspace's reload path (`transcript_get`), through the same
        // builder the command itself calls.
        let db = Database::open_in_memory().expect("open");
        let id = new_transcript(&db);
        sermon_note_repo::create(&db, &note_of(id, &generated_with_two_empty())).expect("persist");
        let record = sermon_note_repo::find_by_transcript(&db, id)
            .expect("find")
            .expect("a draft is stored");
        let t = transcript_repo::load(&db, id).expect("load");
        let detail = build_transcript_detail_view(t, true, Some(&view_of(&record)));
        let draft = detail.draft.expect("the saved draft reaches the console");
        assert_eq!(
            caveat_headings(&draft),
            ["Chapter markers", "Prayer points"]
        );
        assert_eq!(draft["sections"][1]["empty_requested"], true);
    }

    /// The whole chain with the REAL parser: a model response in which four requested things
    /// come back empty (a section, the outline's neighbour, the summary, the scripture list),
    /// parsed by `selahcue_cloud::openai::parse_draft`, persisted to a file, the file reopened.
    /// Only built with `openai-notes` (the feature that compiles the parser in); `make ci`
    /// runs the operator's tests with it.
    #[cfg(feature = "openai-notes")]
    #[test]
    fn a_really_parsed_response_keeps_every_kind_of_caveat_across_a_restart() {
        let all_on = IncludeInNotes {
            prayer_points: true,
            scripture_extraction: true,
            social_excerpts: true,
            chapter_markers: true,
            notable_quotations: true,
            short_summary: true,
            podcast_show_notes: true,
            short_description: true,
        };
        let model_output = serde_json::json!({
            "title": "The Bread of Life",
            "main_scripture": "",
            "supporting_scriptures": [],
            "introduction": ["Hunger that eating does not settle."],
            "points": [{"text": "The crowd came back", "sub_points": ["They ate"]}],
            "illustrations": ["The mill closed after nineteen years."],
            "quotes": ["I am the bread of life"],
            "prayer_points": [],
            "calls_to_action": ["Come to him"],
            "key_lessons": ["The provision and the provider are the same"],
            "chapter_markers": [],
            "podcast_show_notes": ["Title: The Bread of Life"],
            "short_description": ["A sermon on John 6."],
            "summary": ""
        })
        .to_string();
        let response = serde_json::json!({
            "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": model_output}]}]
        })
        .to_string();
        let (parsed, _log) = selahcue_cloud::openai::parse_draft(&response, &all_on)
            .expect("a well-formed response");
        let fresh = crate::draft_json(&parsed);
        let fresh_caveats = caveat_headings(&fresh);
        assert!(
            [
                "Summary",
                "Scripture references",
                "Prayer points",
                "Chapter markers"
            ]
            .iter()
            .all(|h| fresh_caveats.iter().any(|c| c == h)),
            "premise: the parser raised all four caveats, got {fresh_caveats:?}"
        );

        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("selahcue.db");
        let id = {
            let db = Database::open(&path).expect("open");
            let id = new_transcript(&db);
            sermon_note_repo::create(&db, &note_of(id, &parsed)).expect("persist");
            id
        };
        let reopened = Database::open(&path).expect("reopen");
        let reloaded = loaded(&reopened, id);
        assert_eq!(caveat_headings(&reloaded), fresh_caveats);
        assert_eq!(reloaded["sections"], fresh["sections"]);
        assert_eq!(reloaded["summary"], fresh["summary"]);
    }

    #[test]
    fn stage_discard_stage_confirm_on_a_real_file_with_a_restart_between_every_step() {
        // The regeneration lifecycle (FR-129) against a real file, reopened after EVERY step,
        // so each caveat read below came off the disk and not out of a live connection.
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("selahcue.db");
        let first = generated_with_two_empty();
        let mut second = generated_with_two_empty();
        second.caveats = vec![caveat("Prayer points")];
        second.sections[1] = NoteSection::flat("Chapter markers", vec!["Opening prayer".into()]);

        let id = {
            let db = Database::open(&path).expect("open");
            let id = new_transcript(&db);
            sermon_note_repo::create(&db, &note_of(id, &first)).expect("persist");
            id
        };
        let reopen = || Database::open(&path).expect("reopen");
        sermon_note_repo::stage_regeneration(&reopen(), id, &pending_of(&second)).expect("stage");
        assert_eq!(
            caveat_headings(&loaded(&reopen(), id)),
            ["Chapter markers", "Prayer points"],
            "the accepted draft is unchanged by a staged regeneration, across a restart"
        );
        sermon_note_repo::discard_regeneration(&reopen(), id).expect("discard");
        assert_eq!(
            caveat_headings(&loaded(&reopen(), id)),
            ["Chapter markers", "Prayer points"],
            "and by discarding it"
        );
        sermon_note_repo::stage_regeneration(&reopen(), id, &pending_of(&second)).expect("stage");
        sermon_note_repo::confirm_regeneration(&reopen(), id).expect("confirm");
        let j = loaded(&reopen(), id);
        assert_eq!(
            caveat_headings(&j),
            ["Prayer points"],
            "confirmed, across a restart"
        );
        assert_eq!(
            j["sections"][1]["items"],
            serde_json::json!(["Opening prayer"])
        );
        assert_eq!(j["sections"][2]["empty_requested"], true);
    }

    #[test]
    fn the_real_store_accepts_a_draft_exactly_at_the_cap_and_one_byte_over() {
        // The store's `check_bounds` is the authority on size; the codec's own cap constant is
        // only as good as its agreement with it. Both sides of the boundary must be accepted
        // (the over-cap one by yielding the caveat), never refused.
        for pad_over_cap in [0usize, 1] {
            let build = |pad: usize| NoteDraft {
                title: "t".to_string(),
                summary: None,
                sections: vec![
                    NoteSection::flat("Illustrations", vec!["x".repeat(pad)]),
                    NoteSection::flat("Chapter markers", Vec::new()),
                ],
                scriptures: Vec::new(),
                caveats: vec![caveat("Chapter markers")],
                scripture_verdicts: Vec::new(),
                timestamps: Vec::new(),
            };
            let base = persisted_sections_json(&build(10)).len();
            let cap = sermon_note_repo::MAX_SECTIONS_JSON_BYTES;
            let d = build(10 + cap + pad_over_cap - base);
            let db = Database::open_in_memory().expect("open");
            let id = new_transcript(&db);
            sermon_note_repo::create(&db, &note_of(id, &d))
                .expect("a caveat must never be the reason the store refuses a draft");
        }
    }
}
