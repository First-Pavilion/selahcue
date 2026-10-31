//! Canonical scripture link storage through the real host command and pinned-TLS paths.
//! Parser Display is the existing contract; these tests do not normalize a copied value.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_app::{handler_for, ControllerReply, LiveController, RemoteOperator};
use selahcue_core::plan::{ItemContent, ItemId, ItemKind, ServicePlan};
use selahcue_lan::protocol::{Command, ContentLinkView, DenyReason, ServerMessage};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlClient, ControlServer, Role, SelfSigned};
use selahcue_present::{Slide, Theme};
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;
use tokio::task::JoinHandle;

fn scripture_link(reference: &str, translation: Option<&str>) -> ContentLinkView {
    ContentLinkView {
        kind: "scripture".into(),
        reference: Some(reference.into()),
        translation: translation.map(str::to_string),
        verses_per_slide: Some(2),
        verse_numbers: Some("superscript".into()),
        id: None,
        slide_count: None,
        status: None,
        label: None,
    }
}

fn controller() -> (LiveController, u64) {
    let mut plan = ServicePlan::new("Sunday");
    let song = plan.add_item(ItemKind::Song, "Opening Song");
    let reading = plan.add_item(ItemKind::Scripture, "Reading");
    let mut c = LiveController::new(plan, 320, 180, Theme::dark());
    assert_eq!(
        c.apply(&Command::SelectItem { item_id: song.0 }),
        ControllerReply::Ack
    );
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
    assert_eq!(
        c.apply(&Command::SelectItem { item_id: reading.0 }),
        ControllerReply::Ack
    );
    c.take_plan_dirty();
    (c, reading.0)
}

fn assert_stored(c: &LiveController, id: u64, expected: &str) {
    let Some(ItemContent::Scripture { reference, .. }) =
        c.plan().get(ItemId(id)).unwrap().content.as_ref()
    else {
        panic!("the actual host plan must hold a scripture link");
    };
    assert_eq!(reference, expected, "the stored plan must be canonical");
    assert_eq!(
        c.operator_view().items[1]
            .link
            .as_ref()
            .unwrap()
            .reference
            .as_deref(),
        Some(expected),
        "the returned view must agree with stored host state"
    );
}

// live_generation deliberately over-counts potentially state-changing commands,
// including a denied edit. Observe actual audience bytes and content instead.
#[derive(PartialEq, Eq)]
struct AudienceSnapshot {
    dimensions: (u32, u32),
    rgba: Vec<u8>,
    slide: Option<Slide>,
    index: Option<usize>,
}

fn audience_snapshot(c: &LiveController) -> AudienceSnapshot {
    let frame = c.presenter().live_output();
    AudienceSnapshot {
        dimensions: (frame.width(), frame.height()),
        rgba: frame.bytes().to_vec(),
        slide: c.presenter().live_slide().cloned(),
        index: c.live_index(),
    }
}

fn assert_controller_canonical(typed: &str) {
    assert_ne!(typed, "Romans 8:28-30", "exercise a noncanonical spelling");
    assert_eq!(
        selahcue_core::scripture::parse_one(typed)
            .unwrap()
            .to_string(),
        "Romans 8:28-30",
        "premise: the existing parser accepts and canonicalizes this spelling"
    );
    let (mut c, id) = controller();
    let live_before = audience_snapshot(&c);
    assert_eq!(
        c.apply(&Command::SetItemContent {
            item_id: id,
            link: Some(scripture_link(typed, None)),
        }),
        ControllerReply::Ack
    );
    assert_stored(&c, id, "Romans 8:28-30");
    assert!(c.take_plan_dirty(), "canonical state must be persisted");
    let view = c.operator_view();
    let link = view.items[1].link.as_ref().unwrap();
    assert_eq!(
        link.translation, None,
        "canonicalization alone is not a fit"
    );
    assert_eq!(link.verses_per_slide, Some(2));
    assert_eq!(link.verse_numbers.as_deref(), Some("superscript"));
    assert_eq!(link.status, None);
    assert_eq!(view.items[1].slide_count, Some(2));
    assert_eq!(view.staged_index, Some(1));
    assert_eq!(view.live_index, Some(0));
    assert!(
        audience_snapshot(&c) == live_before,
        "linking must preserve actual Live pixels, slide and index"
    );
}

#[test]
fn controller_canonicalizes_to_range() {
    assert_controller_canonical("Romans 8:28 to 30");
}

#[test]
fn controller_canonicalizes_en_dash_range() {
    assert_controller_canonical("Romans 8:28 \u{2013} 30");
}

#[test]
fn controller_canonicalizes_through_range() {
    assert_controller_canonical("Romans 8 verses 28 through 30");
}

#[test]
fn canonical_references_keep_exact_bytes_and_link_metadata() {
    let (mut c, id) = controller();
    let live_before = audience_snapshot(&c);
    for translation in [None, Some("WEB")] {
        let link = scripture_link("Romans 8:28-30", translation);
        assert_eq!(
            c.apply(&Command::SetItemContent {
                item_id: id,
                link: Some(link.clone()),
            }),
            ControllerReply::Ack
        );
        assert_stored(&c, id, "Romans 8:28-30");
        assert_eq!(c.operator_view().items[1].link.as_ref(), Some(&link));
        assert!(
            audience_snapshot(&c) == live_before,
            "canonical edits also leave the real audience output untouched"
        );
    }
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
    assert!(
        audience_snapshot(&c) != live_before,
        "positive control: the oracle detects a real switch from song to scripture"
    );
    assert!(
        c.presenter().live_output().bytes() != live_before.rgba.as_slice(),
        "positive control: a real GoLive changes actual RGBA bytes, not only the index"
    );
}

#[test]
fn canonical_storage_preserves_chapter_fitting_and_translation_pinning() {
    let (mut c, id) = controller();
    for translation in [None, Some("WEB")] {
        let t = translation
            .and_then(selahcue_scripture::Translation::from_code)
            .unwrap_or_default();
        let parsed = selahcue_core::scripture::parse_one("Psalms 1").unwrap();
        let (first, last) = selahcue_scripture::chapter_verse_bounds_in(t, &parsed).unwrap();
        assert!(last < 10 && first == 1, "premise: the range needs fitting");
        for (typed, start) in [("Psalms 1", first), ("Psalms 1:2 to 10", 2)] {
            assert_eq!(
                c.apply(&Command::SetItemContent {
                    item_id: id,
                    link: Some(scripture_link(typed, translation)),
                }),
                ControllerReply::Ack
            );
            assert_stored(&c, id, &format!("Psalms 1:{start}-{last}"));
            let view = c.operator_view();
            let link = view.items[1].link.as_ref().unwrap();
            assert_eq!(link.translation.as_deref(), Some(t.code()));
            assert_eq!(link.verses_per_slide, Some(2));
            assert_eq!(link.verse_numbers.as_deref(), Some("superscript"));
        }
    }
}

#[test]
fn malformed_link_is_denied_without_changing_prior_canonical_plan() {
    let (mut c, id) = controller();
    assert_eq!(
        c.apply(&Command::SetItemContent {
            item_id: id,
            link: Some(scripture_link("Romans 8:28-30", None)),
        }),
        ControllerReply::Ack
    );
    c.take_plan_dirty();
    let before = c.plan().clone();
    let live_before = audience_snapshot(&c);
    for typed in ["Not a reference", "Romans 8:30 to 28", "Romans 8:0 to 3"] {
        assert!(selahcue_core::scripture::parse_one(typed).is_err());
        assert_eq!(
            c.apply(&Command::SetItemContent {
                item_id: id,
                link: Some(scripture_link(typed, None)),
            }),
            ControllerReply::Deny(DenyReason::BadRequest)
        );
        assert_eq!(c.plan(), &before);
        assert!(!c.take_plan_dirty());
        assert!(
            audience_snapshot(&c) == live_before,
            "editing or denying a link must preserve actual Live pixels, slide and index"
        );
    }
}

#[test]
fn parseable_missing_passages_are_still_accepted_and_reported_missing() {
    let (mut c, id) = controller();
    for typed in ["Romans 99:1-3", "Romans 99", "Jude 2:1"] {
        assert!(selahcue_core::scripture::parse_one(typed).is_ok());
        assert_eq!(
            c.apply(&Command::SetItemContent {
                item_id: id,
                link: Some(scripture_link(typed, None)),
            }),
            ControllerReply::Ack
        );
        assert_stored(&c, id, typed);
        let view = c.operator_view();
        assert_eq!(
            view.items[1].link.as_ref().unwrap().status.as_deref(),
            Some("missing")
        );
        assert_eq!(view.items[1].link.as_ref().unwrap().translation, None);
    }
}

#[test]
fn sanitizing_still_precedes_parse_and_canonical_storage() {
    let typed = "Romans 8:2\u{200b}8";
    assert!(selahcue_core::scripture::parse_one(typed).is_err());
    let (mut c, id) = controller();
    assert_eq!(
        c.apply(&Command::SetItemContent {
            item_id: id,
            link: Some(scripture_link(typed, Some("WEB"))),
        }),
        ControllerReply::Ack
    );
    assert_stored(&c, id, "Romans 8:28");
}

struct Host {
    addr: SocketAddr,
    pin: CertPin,
    controller: Arc<Mutex<LiveController>>,
    reading: u64,
    task: JoinHandle<()>,
}

impl Drop for Host {
    fn drop(&mut self) {
        self.task.abort();
    }
}

async fn host() -> Host {
    // Pay corpus/font cold start before a client opens its unchanged command deadline,
    // just as existing test_operator_remote does. This does not relax a wire timeout.
    selahcue_scripture::warm();
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let (controller, reading) = controller();
    let controller = Arc::new(Mutex::new(controller));
    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    {
        let mut reg = registry.lock().await;
        let now = Instant::now();
        for (id, role) in [("operator", Role::Operator), ("viewer", Role::Viewer)] {
            reg.offer_pairing(format!("pair-{id}"), role, now, Duration::from_secs(300));
            reg.redeem(
                &format!("pair-{id}"),
                DeviceId(id.into()),
                SessionToken::new(format!("tok-{id}")),
                now,
            )
            .unwrap();
        }
    }
    let server =
        Arc::new(ControlServer::new(&identity, registry, handler_for(controller.clone())).unwrap());
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let task = tokio::spawn(async move {
        let _ = server.run(listener).await;
    });
    Host {
        addr,
        pin,
        controller,
        reading,
        task,
    }
}

async fn assert_remote_canonical(typed: &str) {
    let h = host().await;
    let live_before = audience_snapshot(&h.controller.lock().unwrap());
    let mut op = RemoteOperator::connect(h.addr, "localhost", h.pin, "operator", "tok-operator")
        .await
        .unwrap();
    let view = op
        .set_item_content(h.reading, Some(scripture_link(typed, Some("WEB"))))
        .await
        .unwrap();
    assert_eq!(
        view.items[1].link.as_ref().unwrap().reference.as_deref(),
        Some("Romans 8:28-30"),
        "the real authenticated wire response must expose canonical host storage"
    );
    assert_eq!(
        view.items[1].link.as_ref().unwrap().translation.as_deref(),
        Some("WEB")
    );
    assert_eq!(
        view.items[1].link.as_ref().unwrap().verses_per_slide,
        Some(2)
    );
    assert_eq!(
        view.items[1]
            .link
            .as_ref()
            .unwrap()
            .verse_numbers
            .as_deref(),
        Some("superscript")
    );
    assert_eq!(view.live_index, Some(0));
    assert_eq!(view.staged_index, Some(1));
    let c = h.controller.lock().unwrap();
    assert_stored(&c, h.reading, "Romans 8:28-30");
    assert!(
        audience_snapshot(&c) == live_before,
        "editing or denying a link must preserve actual Live pixels, slide and index"
    );
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn remote_operator_canonicalizes_to_range() {
    assert_remote_canonical("Romans 8:28 to 30").await;
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn remote_operator_canonicalizes_en_dash_range() {
    assert_remote_canonical("Romans 8:28 \u{2013} 30").await;
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn remote_operator_canonicalizes_through_range() {
    assert_remote_canonical("Romans 8 verses 28 through 30").await;
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn remote_operator_keeps_already_canonical_bytes() {
    assert_remote_canonical("Romans 8:28-30").await;
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn wire_denials_do_not_mutate_the_host_plan_or_live_output() {
    let h = host().await;
    let before = h.controller.lock().unwrap().plan().clone();
    let live_before = audience_snapshot(&h.controller.lock().unwrap());
    let mut viewer = ControlClient::connect(h.addr, "localhost", h.pin, "viewer", "tok-viewer")
        .await
        .unwrap();
    assert!(matches!(
        viewer
            .command(Command::SetItemContent {
                item_id: h.reading,
                link: Some(scripture_link("Romans 8:28 to 30", None)),
            })
            .await
            .unwrap(),
        ServerMessage::Denied {
            reason: DenyReason::Forbidden,
            ..
        }
    ));
    viewer.close().await.unwrap();
    let mut operator =
        ControlClient::connect(h.addr, "localhost", h.pin, "operator", "tok-operator")
            .await
            .unwrap();
    assert!(matches!(
        operator
            .command(Command::SetItemContent {
                item_id: h.reading,
                link: Some(scripture_link("Not a reference", None)),
            })
            .await
            .unwrap(),
        ServerMessage::Denied {
            reason: DenyReason::BadRequest,
            ..
        }
    ));
    operator.close().await.unwrap();
    let c = h.controller.lock().unwrap();
    assert_eq!(c.plan(), &before);
    assert!(
        audience_snapshot(&c) == live_before,
        "editing or denying a link must preserve actual Live pixels, slide and index"
    );
    assert_eq!(c.live_index(), Some(0));
}
