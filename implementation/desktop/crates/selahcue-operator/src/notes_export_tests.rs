use crate::notes_export::*;
use selahcue_lan::protocol::SermonNoteDraftView;
fn accepted() -> SermonNoteDraftView {
    SermonNoteDraftView { title: "Accepted A edited title".into(), summary: Some("Accepted summary".into()),
        sections_json: r#"[{"heading":"Outline","points":[{"text":"First John 3:16","sub_points":["Child A"]}]},{"heading":"Application","items":["Act today"]}]"#.into(),
        scriptures_json: r#"["Psalm 23:1","John 999:1"]"#.into(), ai_generated: true,
        disclosure: Some("Synthetic disclosure: review before use.".into()), provider: "synthetic".into(), model: None, created_at_ms: 1, edited_at_ms: 2 }
}
#[test]
fn saved_accepted_draft_renders_offline_without_mutation() {
    let draft = accepted();
    let before = draft.clone();
    let result = render_saved_note_pdf(&draft, 42);
    assert!(
        result.is_ok(),
        "valid accepted notes must render: {result:?}"
    );
    assert_eq!(draft, before);
}
#[test]
fn malformed_storage_refuses_instead_of_silent_empty_notes() {
    for bad in [
        "broken",
        "null",
        r#"[{"heading":7}]"#,
        r#"{"sections":false}"#,
    ] {
        let mut draft = accepted();
        draft.sections_json = bad.into();
        assert_eq!(
            render_saved_note_pdf(&draft, 42),
            Err(ExportError::InvalidDraft)
        );
    }
}

#[test]
fn native_save_replaces_existing_file_only_with_complete_bytes() {
    let dir = fixture_dir();
    let target = dir.path().join("notes.pdf");
    std::fs::write(&target, b"old sentinel").expect("sentinel");
    assert_eq!(save::save_pdf(&target, b"new complete PDF"), Ok(()));
    assert_eq!(std::fs::read(&target).expect("read"), b"new complete PDF");
    assert_eq!(std::fs::read_dir(dir.path()).expect("list").count(), 1);
}

#[test]
fn unicode_nfc_nfd_and_missing_glyphs_are_honest() {
    use unicode_normalization::UnicodeNormalization;
    let mut draft = accepted();
    let names =
        "Olúwáfẹ́mi Ṣọlá Ọlátúndé Ẹ̀bùn Chịdị Ịfeọma Ọnwụ Ụzọ A’isha Ɓala Ɗanjuma ƙauna Ƙ Ƴ ƴ ɗ ɓ";
    for name in [names.to_owned(), names.nfd().collect::<String>()] {
        draft.summary = Some(name);
        assert!(render_saved_note_pdf(&draft, 42).is_ok());
    }
    draft.summary = Some("Cannot represent this: 🦄".into());
    assert_eq!(
        render_saved_note_pdf(&draft, 42),
        Err(ExportError::InvalidDraft)
    );
}

#[test]
fn malformed_caveats_and_scriptures_and_ambiguous_hierarchy_are_rejected() {
    for bad in [
        r#"[{"heading":"A","requested_empty":[5]}]"#,
        r#"[{"heading":"A","items":["lost"],"points":[{"text":"kept"}]}]"#,
        r#"[{"heading":"A","points":[{"text":"x","sub_points":null}]}]"#,
    ] {
        let mut d = accepted();
        d.sections_json = bad.into();
        assert_eq!(
            render_saved_note_pdf(&d, 42),
            Err(ExportError::InvalidDraft)
        );
    }
    let mut d = accepted();
    d.scriptures_json = r#"["John 3:16",{}]"#.into();
    assert_eq!(
        render_saved_note_pdf(&d, 42),
        Err(ExportError::InvalidDraft)
    );
}

#[test]
fn page_byte_input_and_concurrency_bounds_are_enforced() {
    let draft = accepted();
    assert_eq!(
        render_with_limits(&draft, 42, 0, MAX_PDF_BYTES),
        Err(ExportError::TooLarge)
    );
    assert_eq!(
        render_with_limits(&draft, 42, MAX_PAGES, 10),
        Err(ExportError::TooLarge)
    );
    let mut huge = draft.clone();
    huge.summary = Some("a".repeat(128 * 1024));
    assert_eq!(render_saved_note_pdf(&huge, 42), Err(ExportError::TooLarge));
    let mut many = draft;
    many.summary = Some("\n".repeat(30000));
    assert_eq!(render_saved_note_pdf(&many, 42), Err(ExportError::TooLarge));
    let permit = ExportPermit::acquire().expect("first export");
    assert!(ExportPermit::acquire().is_err());
    drop(permit);
    assert!(ExportPermit::acquire().is_ok());
}

#[test]
fn cancellation_and_render_refusal_leave_destination_and_draft_untouched() {
    let dir = fixture_dir();
    let target = dir.path().join("notes.pdf");
    std::fs::write(&target, b"sentinel").expect("write");
    let d = accepted();
    let before = d.clone();
    assert_eq!(
        export_snapshot(d.clone(), 42, || Ok(None)),
        Err(ExportError::Cancelled)
    );
    assert_eq!(d, before);
    let mut invalid = d;
    invalid.sections_json = "bad".into();
    assert_eq!(
        export_snapshot(invalid, 42, || panic!("render refusal precedes dialog")),
        Err(ExportError::InvalidDraft)
    );
    assert_eq!(std::fs::read(&target).expect("read"), b"sentinel");
    assert_eq!(std::fs::read_dir(dir.path()).expect("list").count(), 1);
}

#[test]
fn real_partial_write_sync_and_rename_failures_preserve_sentinel_and_clean_stage() {
    use save::Event;
    for failure in [
        Event::Created,
        Event::PartialWrite,
        Event::Sync,
        Event::Validate,
        Event::Rename,
    ] {
        let dir = fixture_dir();
        let target = dir.path().join("notes.pdf");
        std::fs::write(&target, b"sentinel").expect("write");
        let result = save::with_hook(
            move |event, _, _| {
                if event == failure {
                    Err(std::io::Error::from(std::io::ErrorKind::PermissionDenied))
                } else {
                    Ok(())
                }
            },
            || save::save_pdf(&target, &vec![42; 20000]),
        );
        assert_eq!(result, Err(ExportError::Io), "{failure:?}");
        assert_eq!(std::fs::read(&target).expect("read"), b"sentinel");
        assert_eq!(
            std::fs::read_dir(dir.path()).expect("list").count(),
            1,
            "{failure:?}"
        );
    }
}

#[test]
fn atomic_no_replace_preserves_late_arrival_and_commit_remains_success() {
    use save::Event;
    let dir = fixture_dir();
    let target = dir.path().join("notes.pdf");
    let result = save::with_hook(
        |event, _, target| {
            if event == Event::Rename {
                std::fs::write(target, b"late arrival")?;
            }
            Ok(())
        },
        || save::save_pdf(&target, b"new"),
    );
    assert_eq!(result, Err(ExportError::Io));
    assert_eq!(std::fs::read(&target).expect("read"), b"late arrival");
    assert_eq!(std::fs::read_dir(dir.path()).expect("list").count(), 1);
    let result = save::with_hook(
        |event, _, _| {
            if event == Event::Committed {
                Err(std::io::Error::other("late cancel"))
            } else {
                Ok(())
            }
        },
        || save::save_pdf(&target, b"complete"),
    );
    assert_eq!(result, Ok(()));
    assert_eq!(std::fs::read(&target).expect("read"), b"complete");
}

#[test]
fn collisions_are_bounded_and_never_cleaned_as_owned_files() {
    let dir = fixture_dir();
    let target = dir.path().join("notes.pdf");
    let result = save::with_hook(
        |event, stage, _| {
            if event == save::Event::Candidate {
                std::fs::write(stage, b"unrelated collision")?;
            }
            Ok(())
        },
        || save::save_pdf(&target, b"new"),
    );
    assert_eq!(result, Err(ExportError::Io));
    assert!(!target.exists());
    let files: Vec<_> = std::fs::read_dir(dir.path()).expect("list").collect();
    assert_eq!(files.len(), 16);
    for f in files {
        assert_eq!(
            std::fs::read(f.expect("entry").path()).expect("read"),
            b"unrelated collision"
        );
    }
}

#[test]
fn target_or_stage_identity_changes_are_refused_without_deleting_substitutes() {
    for change_stage in [false, true] {
        let dir = fixture_dir();
        let target = dir.path().join("notes.pdf");
        std::fs::write(&target, b"original").expect("write");
        let result = save::with_hook(
            move |event, stage, target| {
                if event == save::Event::Validate {
                    let changed = if change_stage { stage } else { target };
                    std::fs::rename(changed, changed.with_extension("held"))?;
                    std::fs::write(changed, b"substitute")?;
                }
                Ok(())
            },
            || save::save_pdf(&target, b"new PDF"),
        );
        assert_eq!(result, Err(ExportError::Io));
        if change_stage {
            assert_eq!(std::fs::read(&target).expect("read"), b"original");
            assert!(std::fs::read_dir(dir.path())
                .expect("list")
                .any(|p| std::fs::read(p.expect("entry").path()).expect("read") == b"substitute"));
        } else {
            assert_eq!(std::fs::read(&target).expect("read"), b"substitute");
            assert_eq!(
                std::fs::read(target.with_extension("held")).expect("read"),
                b"original"
            );
        }
    }
}

#[cfg(unix)]
#[test]
fn symlinks_hardlinks_and_parent_move_are_refused() {
    use std::os::unix::fs::symlink;
    let dir = fixture_dir();
    let sentinel = dir.path().join("sentinel");
    std::fs::write(&sentinel, b"original").expect("write");
    let link = dir.path().join("link.pdf");
    symlink(&sentinel, &link).expect("symlink");
    assert_eq!(save::save_pdf(&link, b"new"), Err(ExportError::Io));
    let hard = dir.path().join("hard.pdf");
    std::fs::hard_link(&sentinel, &hard).expect("hardlink");
    assert_eq!(save::save_pdf(&hard, b"new"), Err(ExportError::Io));
    let parent = dir.path().join("parent");
    std::fs::create_dir(&parent).expect("mkdir");
    let result = save::with_hook(
        |event, _, target| {
            if event == save::Event::Validate {
                let parent = target.parent().expect("parent");
                std::fs::rename(parent, parent.with_extension("moved"))?;
                std::fs::create_dir(parent)?;
            }
            Ok(())
        },
        || save::save_pdf(&parent.join("notes.pdf"), b"new"),
    );
    assert_eq!(result, Err(ExportError::Io));
    assert!(!parent.join("notes.pdf").exists());
    assert_eq!(std::fs::read(&sentinel).expect("read"), b"original");
}

fn fixture_dir() -> tempfile::TempDir {
    #[cfg(target_os = "macos")]
    {
        tempfile::tempdir_in("/private/tmp").expect("temp dir")
    }
    #[cfg(not(target_os = "macos"))]
    {
        tempfile::tempdir().expect("temp dir")
    }
}

fn input(d: &SermonNoteDraftView) -> selahcue_lan::protocol::SermonNoteDraftInput {
    selahcue_lan::protocol::SermonNoteDraftInput {
        title: d.title.clone(),
        summary: d.summary.clone(),
        sections_json: d.sections_json.clone(),
        scriptures_json: d.scriptures_json.clone(),
        ai_generated: d.ai_generated,
        disclosure: d.disclosure.clone(),
        provider: d.provider.clone(),
        model: d.model.clone(),
    }
}
#[tokio::test]
async fn real_host_load_exports_accepted_a_while_pending_b_is_retained_on_every_result() {
    use tauri::Manager;
    let (app, id) = crate::regenerate_with_retention_tests::state_with_transcript(false);
    let state = app.state::<crate::AppState>();
    assert_eq!(
        load_snapshot(&state.backend, id).await,
        Err(ExportError::NoSavedDraft)
    );
    let a = state
        .backend
        .save_sermon_note_draft(id, input(&accepted()))
        .await
        .expect("host")
        .expect("saved");
    let mut pending = accepted();
    pending.title = "PENDING_B_MUST_NEVER_EXPORT".into();
    state
        .backend
        .stage_sermon_note_regeneration_admitted(id, input(&pending), || true)
        .await
        .expect("host")
        .expect("staged");
    let snapshot = load_snapshot(&state.backend, id).await.expect("A");
    assert_eq!(snapshot, a);
    let dir = fixture_dir();
    let target = dir.path().join("notes.pdf");
    std::fs::write(&target, b"sentinel").expect("write");
    assert_eq!(
        export_snapshot(snapshot.clone(), id, || Ok(None)),
        Err(ExportError::Cancelled)
    );
    assert_eq!(load_snapshot(&state.backend, id).await.expect("reload"), a);
    assert_eq!(
        save::with_hook(
            |event, _, _| if event == save::Event::PartialWrite {
                Err(std::io::Error::other("disk full"))
            } else {
                Ok(())
            },
            || export_snapshot(snapshot.clone(), id, || Ok(Some(target.clone())))
        ),
        Err(ExportError::Io)
    );
    assert_eq!(std::fs::read(&target).expect("read"), b"sentinel");
    assert_eq!(load_snapshot(&state.backend, id).await.expect("reload"), a);
    let receipt = export_snapshot(snapshot, id, || Ok(Some(target))).expect("retry");
    assert_eq!(receipt.saved_edited_at_ms, a.edited_at_ms);
    assert_eq!(load_snapshot(&state.backend, id).await.expect("reload"), a);
    // Explicit promotion after export proves that the exact pending slot survived too.
    let promoted = state
        .backend
        .confirm_sermon_note_regeneration(id)
        .await
        .expect("host")
        .expect("pending survived");
    assert_eq!(promoted.current.expect("current").title, pending.title);
}

/// Explicitly run with C4_PDF_FIXTURES after the PDF skill's operation marker. These are
/// synthetic source-renderer fixtures, never a replacement PDF implementation.
#[tokio::test]
#[ignore = "authors two synthetic PDFs for independent parser and visual inspection"]
async fn author_pdf_inspection_fixtures() {
    use tauri::Manager;
    use unicode_normalization::UnicodeNormalization;
    let output = std::path::PathBuf::from(
        std::env::var_os("C4_PDF_FIXTURES").expect("fixture output directory"),
    );
    std::fs::create_dir_all(&output).expect("mkdir");
    let (app, id) = crate::regenerate_with_retention_tests::state_with_transcript(false);
    let state = app.state::<crate::AppState>();
    let mut a = accepted();
    let names =
        "Olúwáfẹ́mi Ṣọlá Ọlátúndé Ẹ̀bùn Chịdị Ịfeọma Ọnwụ Ụzọ A’isha Ɓala Ɗanjuma ƙauna Ƙ Ƴ ƴ ɗ ɓ";
    a.summary = Some(format!(
        "SYNTHETIC TEST MATERIAL\nNFC: {names}\nNFD: {}",
        names.nfd().collect::<String>()
    ));
    a.sections_json=r#"[{"heading":"Outline","points":[{"text":"FIRST_A John 3:16","sub_points":["CHILD_A with care"]}],"requested_empty":["Application"]},{"heading":"Application","items":[]}]"#.into();
    let accepted = state
        .backend
        .save_sermon_note_draft(id, input(&a))
        .await
        .expect("host")
        .expect("saved");
    let mut b = a.clone();
    b.title = "PENDING_B_MUST_NEVER_EXPORT".into();
    state
        .backend
        .stage_sermon_note_regeneration_admitted(id, input(&b), || true)
        .await
        .expect("host")
        .expect("staged");
    export_snapshot(
        load_snapshot(&state.backend, id).await.expect("A"),
        id,
        || Ok(Some(output.join("saved-a-unicode.pdf"))),
    )
    .expect("single PDF");
    assert_eq!(
        load_snapshot(&state.backend, id).await.expect("reload"),
        accepted
    );
    let mut long = a.clone();
    long.title = "SYNTHETIC long saved notes".into();
    long.summary = Some("Accepted summary line. ".repeat(180));
    let items: Vec<_> = (0..72)
        .map(|i| {
            format!(
                "LONG_{i:03} - {names}. Psalm {}:1. Keep this full paragraph and its final marker.",
                i + 1
            )
        })
        .collect();
    long.sections_json =
        serde_json::json!([{"heading":"Long accepted notes","items":items}]).to_string();
    // <= today's storage caps: this is a long accepted-size fixture, not a claim that
    // output caps prove peak RAM on Windows hardware.
    assert!(long.sections_json.len() <= selahcue_data::sermon_note_repo::MAX_SECTIONS_JSON_BYTES);
    std::fs::write(
        output.join("saved-long.pdf"),
        render_saved_note_pdf(&long, id).expect("long PDF"),
    )
    .expect("write fixture");
    std::fs::write(output.join("expected.json"),serde_json::to_vec_pretty(&serde_json::json!({"names":names,"a_title":a.title,"excluded":["PENDING_B_MUST_NEVER_EXPORT","UNSAVED_C_MUST_NEVER_EXPORT"],"last":"LONG_071", "long_items":items})).expect("json")).expect("expected");
    let python =
        std::env::var_os("C4_PDF_PYTHON").expect("Python interpreter with pypdf and pdfplumber");
    let check = std::process::Command::new(python)
        .arg("-c")
        .arg(INDEPENDENT_PDF_CHECK)
        .arg(&output)
        .output()
        .expect("independent PDF parser starts");
    assert!(
        check.status.success(),
        "independent PDF check: {}",
        String::from_utf8_lossy(&check.stderr)
    );
    println!("{}", String::from_utf8_lossy(&check.stdout));
}

#[tokio::test]
async fn backend_permission_or_read_failure_is_not_reported_as_absence() {
    use tauri::Manager;
    let (app, id, gate) = crate::regenerate_with_retention_tests::flaky_state(false);
    let state = app.state::<crate::AppState>();
    gate.fail_loads(true);
    assert_eq!(
        load_snapshot(&state.backend, id).await,
        Err(ExportError::Io)
    );
    gate.fail_loads(false);
    assert_eq!(
        load_snapshot(&state.backend, id).await,
        Err(ExportError::NoSavedDraft)
    );
}

#[test]
fn empty_envelope_legacy_caveats_and_serialization_caps_remain_recoverable() {
    let mut d = accepted();
    d.summary = None;
    d.scriptures_json = "[]".into();
    d.sections_json =
        r#"{"sections":[],"requested_empty":["Summary","Scripture references"]}"#.into();
    assert!(render_saved_note_pdf(&d, 42).is_ok());
    d.summary = Some(format!("a{}", "\u{0301}".repeat(65)));
    assert_eq!(
        render_saved_note_pdf(&d, 42),
        Err(ExportError::InvalidDraft)
    );
    let dir = fixture_dir();
    let target = dir.path().join("notes.pdf");
    std::fs::write(&target, b"sentinel").expect("write");
    assert_eq!(
        save::save_pdf(&target, &vec![0; MAX_PDF_BYTES + 1]),
        Err(ExportError::TooLarge)
    );
    assert_eq!(std::fs::read(&target).expect("read"), b"sentinel");
    assert_eq!(std::fs::read_dir(dir.path()).expect("list").count(), 1);
}

#[test]
fn observed_same_identity_size_changes_and_parent_directory_changes_refuse_commit() {
    for changed in 0..3 {
        let dir = fixture_dir();
        let target = dir.path().join("notes.pdf");
        std::fs::write(&target, b"sentinel").expect("write");
        let result = save::with_hook(
            move |event, stage, target| {
                if event == save::Event::Validate {
                    match changed {
                        0 => std::fs::write(target, b"external content edit on the same inode")?,
                        1 => std::fs::write(stage, b"external stage content edit")?,
                        _ => std::fs::write(target.with_extension("unrelated"), b"unrelated")?,
                    }
                }
                Ok(())
            },
            || save::save_pdf(&target, b"PDF bytes"),
        );
        assert_eq!(result, Err(ExportError::Io));
        assert_eq!(
            std::fs::read(&target).expect("read"),
            if changed == 0 {
                b"external content edit on the same inode".as_slice()
            } else {
                b"sentinel"
            }
        );
        if changed == 2 {
            assert_eq!(
                std::fs::read(target.with_extension("unrelated")).expect("read"),
                b"unrelated"
            );
        }
    }
}

// Independent parser/geometry assertions are durable with the fixture test; Python is
// explicitly supplied only for this opt-in inspection, never used by the product renderer.
const INDEPENDENT_PDF_CHECK: &str = r##"from pathlib import Path
from pypdf import PdfReader
import pypdf, pdfplumber, unicodedata, json, hashlib, sys
p=Path(sys.argv[1])
e=json.loads((p/'expected.json').read_text())
def normal(t): return ' '.join(unicodedata.normalize('NFC',t).split())
def body_matches(actual, expected): return normal(actual) == normal(' '.join(expected))
def negative_controls(body, expected, first, second):
    t=normal(body); a=normal(first); b=normal(second)
    assert t.count(a)==1 and t.count(b)==1, 'unique mutation anchors'
    mutations={
        'missing': t.replace(a, '', 1),
        'duplicate': t.replace(a, a+' '+a, 1),
        'reordered': t.replace(a, '__SWAP__', 1).replace(b, a, 1).replace('__SWAP__', b, 1),
        'unexpected': t.replace(a, a+' UNEXPECTED BODY PARAGRAPH', 1),
        'body_page_label': t.replace(a, a+' Page 1', 1),
    }
    if 'Accepted summary line.' in t:
        mutations['missing_summary']=t.replace('Accepted summary line.', '', 1)
        mutations['duplicate_summary']=t.replace('Accepted summary line.', 'Accepted summary line. Accepted summary line.', 1)
    for label, changed in mutations.items():
        assert changed != t and not body_matches(changed, expected), ('negative control accepted', label)
    return {label:'REJECT' for label in mutations}
verification='Verified means the reference address exists in the bundled Bible text — it does not confirm that any words this draft attributes to it are accurate. Always check a quotation against the actual text before you use it.'
results=[]
for name in ['saved-a-unicode.pdf','saved-long.pdf']:
    path=p/name; r=PdfReader(path)
    raw='\n'.join(page.extract_text() for page in r.pages)
    (p/(name+'.txt')).write_text(raw)
    t=normal(raw)
    assert normal(e['names']) in t, 'all Yoruba/Igbo/Hausa names and marks'
    for excluded in e['excluded']: assert excluded not in t
    for required in ['Saved English notes','AI-generated draft','Synthetic disclosure: review before use.','Verified means the reference address exists','does not confirm that any words','John 999:1 - UNVERIFIED']:
        assert required in t,(name,required)
    assert 'transcript 1' not in t and 'Sermon date' not in t
    font_ids=set(); body_pages=[]
    for index,page in enumerate(r.pages):
        # Classify furniture by actual per-page coordinates, never by body text.
        body=[]; footer=[]
        def collect(text, cm, tm, font, size):
            if text.strip():
                assert cm == [1,0,0,1,0,0], 'fixture uses page coordinates'
                (footer if tm[5] < 40 else body).append(text)
        page.extract_text(visitor_text=collect)
        assert normal(' '.join(footer)) == f'Page {index+1}'
        body_pages.append(' '.join(body))
        fonts=page['/Resources']['/Font']; assert len(fonts)==1
        for f in fonts.values():
            font_ids.add(f.idnum)
            descriptor=f.get_object()['/DescendantFonts'][0].get_object()['/FontDescriptor']
            assert '/FontFile2' in descriptor
    assert len(font_ids)==1, 'one font reused across document'
    title=e['a_title'] if name=='saved-a-unicode.pdf' else 'SYNTHETIC long saved notes'
    expected=['SELAHCUE / SAVED SERMON NOTES',title,'Saved English notes','AI-generated draft',
        'Review these notes before use. Scripture checks verify addresses only, not quotations or interpretation.',
        'Synthetic disclosure: review before use.','Summary']
    references=['Referenced passages','Psalm 23:1 - Verified address',
        'John 999:1 - UNVERIFIED - check this reference','References found in the notes']
    if name=='saved-a-unicode.pdf':
        assert len(r.pages)==1 and e['a_title'] in t
        expected += ['SYNTHETIC TEST MATERIAL','NFC: '+e['names'],'NFD: '+e['names'],
            'Outline','1. FIRST_A John 3:16','- CHILD_A with care','Application',
            'Warning: Application was requested but returned empty. Review the source transcript.']
        expected += references + ['John 3:16 - Verified address',verification]
        anchors=['1. FIRST_A John 3:16','- CHILD_A with care']
    else:
        assert len(r.pages)==8 and e['last'] in t and len(e['long_items'])==72
        expected += ['Accepted summary line. '*180,'Long accepted notes']
        expected += ['- '+item for item in e['long_items']]
        expected += references + [f'Psalms {i}:1 - Verified address' for i in range(1,65)]
        expected += [verification,'Warning: scripture verification is incomplete. Some references were not checked; review all references against the actual Bible text.']
        anchors=['- '+item for item in e['long_items'][:2]]
    body=' '.join(body_pages)
    assert body_matches(body, expected), (name,'full normalized body differs')
    controls=negative_controls(body, expected, *anchors)
    with pdfplumber.open(path) as doc:
        for i,page in enumerate(doc.pages):
            for c in page.chars:
                assert c['x0']>=44 and c['x1']<=552 and c['top']>=20 and c['bottom']<=825,(name,i,c)
    results.append({'file':name,'pages':len(r.pages),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'full_body_parts':len(expected),'negative_controls':controls,'font_resources':len(font_ids),'parser':f'pypdf {pypdf.__version__} + pdfplumber {pdfplumber.__version__}','result':'PASS'})
print(json.dumps(results,indent=2));(p/'inspection.json').write_text(json.dumps(results,indent=2))
"##;
