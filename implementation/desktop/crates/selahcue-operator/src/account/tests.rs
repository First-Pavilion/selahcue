use super::state::*;
use std::sync::{Arc, Barrier};
use std::{fs, io};

fn assert_random_id(id: &str) {
    assert_eq!(id.len(), 32);
    assert!(id
        .bytes()
        .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)));
}

#[test]
fn identity_survives_restart() {
    let directory = tempfile::tempdir().expect("test directory");
    let path = directory.path();
    let before = AccountMetadataStore::new(path.to_path_buf())
        .load_or_create(CredentialPresence::Missing)
        .expect("initial identity");
    assert_random_id(before.fingerprint());
    let after = AccountMetadataStore::new(path.to_path_buf())
        .load_or_create(CredentialPresence::Missing)
        .expect("identity after restart");
    assert_eq!(before, after);
}

#[test]
fn parallel_identity_creation_has_one_winner() {
    let directory = tempfile::tempdir().expect("test directory");
    let barrier = Arc::new(Barrier::new(8));
    let handles: Vec<_> = (0..8)
        .map(|seed| {
            let barrier = Arc::clone(&barrier);
            let path = directory.path().to_path_buf();
            std::thread::spawn(move || {
                let store = AccountMetadataStore::new(path);
                barrier.wait();
                store
                    .load_or_create_with_entropy(CredentialPresence::Missing, |bytes| {
                        bytes.fill(seed);
                        true
                    })
                    .expect("identity")
                    .fingerprint()
                    .to_owned()
            })
        })
        .collect();

    let fingerprints: Vec<_> = handles
        .into_iter()
        .map(|handle| handle.join().expect("worker"))
        .collect();
    let winner = &fingerprints[0];
    assert!(fingerprints.iter().all(|fingerprint| fingerprint == winner));
    assert_eq!(
        AccountMetadataStore::new(directory.path().to_path_buf())
            .load_or_create(CredentialPresence::Missing)
            .expect("disk winner")
            .fingerprint(),
        *winner
    );
}

#[test]
fn pending_retry_preserves_original_identity_and_key() {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let mut metadata = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    let pending = metadata
        .begin_activation(ActivationPath::AccountSession, " macos ", "1.2", " Booth ")
        .expect("pending activation")
        .clone();
    assert_random_id(pending.retry_key().expect("idempotency key").as_str());
    assert_eq!(pending.path(), ActivationPath::AccountSession);
    let identity = pending.device_identity().expect("wire identity");
    assert_eq!(identity.fingerprint, metadata.fingerprint());
    assert_eq!(identity.platform, "macos");
    assert_eq!(identity.app_version, "1.2");
    assert_eq!(identity.display_name, "Booth");
    store.save(&metadata).expect("persist pending request");

    let reopened = AccountMetadataStore::new(directory.path().to_path_buf());
    let mut metadata = reopened
        .load_or_create(CredentialPresence::Missing)
        .expect("restart");
    assert_eq!(
        metadata.begin_activation(ActivationPath::AccountSession, "macos", "2.0", "New Name"),
        Ok(&pending)
    );
    assert!(metadata
        .begin_activation(ActivationPath::EnrollmentKey, "macos", "2.0", "New Name")
        .is_err());
}

#[test]
fn metadata_contains_no_credential() {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let mut metadata = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    metadata.activated_public_id = Some("dev_81818181818181818181818181818181".into());
    metadata
        .begin_activation(ActivationPath::EnrollmentKey, "linux", "1.0", "Booth")
        .expect("pending");
    store.save(&metadata).expect("persist");
    let raw = fs::read(directory.path().join("account-metadata.json")).expect("metadata bytes");
    let value: serde_json::Value = serde_json::from_slice(&raw).expect("JSON");
    let root = value.as_object().expect("object");
    let allowed = [
        "schema_version",
        "revision",
        "install_fingerprint",
        "display_name",
        "platform",
        "app_version",
        "activated_public_id",
        "skipped_setup",
        "pending_activation",
    ];
    assert_eq!(root.len(), allowed.len());
    assert!(allowed.iter().all(|key| root.contains_key(*key)));
    let pending = value["pending_activation"]
        .as_object()
        .expect("pending object");
    assert_eq!(pending.len(), 3);
    assert_eq!(pending["path"], "enrollment_key");
    assert!(pending.contains_key("idempotency_key"));
    let identity = pending["identity"].as_object().expect("identity object");
    assert_eq!(identity.len(), 4);
    assert!([
        "install_fingerprint",
        "display_name",
        "platform",
        "app_version"
    ]
    .iter()
    .all(|key| identity.contains_key(*key)));
}

#[test]
fn corrupt_metadata_does_not_silently_reenroll() {
    let directory = tempfile::tempdir().expect("test directory");
    let path = directory.path().join("account-metadata.json");
    fs::write(&path, b"{broken").expect("corrupt fixture");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    for presence in [
        CredentialPresence::Missing,
        CredentialPresence::Present,
        CredentialPresence::Unavailable,
    ] {
        assert_eq!(
            store.load_or_create_with_entropy(presence, |_| panic!(
                "must not mint another identity"
            )),
            Err(AccountStorageError::Malformed)
        );
    }
    assert_eq!(fs::read(path).expect("original bytes"), b"{broken");
}

#[test]
fn skip_survives_restart() {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let mut metadata = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    assert!(!metadata.skipped_setup);
    metadata.skipped_setup = true;
    store.save(&metadata).expect("save skip");
    let reopened = AccountMetadataStore::new(directory.path().to_path_buf());
    assert!(
        reopened
            .load_or_create(CredentialPresence::Missing)
            .expect("restart")
            .skipped_setup
    );
}

#[test]
fn missing_metadata_and_missing_credential_mint_identity() {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let metadata = store
        .load_or_create_with_entropy(CredentialPresence::Missing, |bytes| {
            bytes.fill(0x3a);
            true
        })
        .expect("minted identity");
    assert_eq!(metadata.fingerprint(), "3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a");
    assert!(directory.path().join("account-metadata.json").is_file());
}

#[test]
fn missing_metadata_and_present_credential_require_recovery() {
    assert_absent_refused(
        CredentialPresence::Present,
        AccountStorageError::IdentityRecoveryRequired,
    );
}

#[test]
fn missing_metadata_and_unavailable_custody_report_outage() {
    assert_absent_refused(
        CredentialPresence::Unavailable,
        AccountStorageError::CredentialPresenceUnavailable,
    );
}

fn assert_absent_refused(presence: CredentialPresence, error: AccountStorageError) {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    assert_eq!(
        store.load_or_create_with_entropy(presence, |_| panic!("must not mint identity")),
        Err(error)
    );
    assert!(!directory.path().join("account-metadata.json").exists());
    assert!(!directory.path().join("account-metadata.stage").exists());
    assert_eq!(
        fs::read_dir(directory.path()).expect("directory").count(),
        0
    );
}

#[test]
fn valid_metadata_loads_under_every_presence_result() {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let existing = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    for presence in [
        CredentialPresence::Missing,
        CredentialPresence::Present,
        CredentialPresence::Unavailable,
    ] {
        assert_eq!(
            store.load_or_create_with_entropy(presence, |_| panic!("existing identity must win")),
            Ok(existing.clone())
        );
    }
}

#[test]
fn presence_resolution_errors_become_unavailable() {
    assert!(matches!(
        CredentialPresence::from_check(Ok::<_, ()>(true)),
        CredentialPresence::Present
    ));
    assert!(matches!(
        CredentialPresence::from_check(Ok::<_, ()>(false)),
        CredentialPresence::Missing
    ));
    assert!(matches!(
        CredentialPresence::from_check(Err(io::ErrorKind::NotFound)),
        CredentialPresence::Unavailable
    ));
    assert!(matches!(
        CredentialPresence::from_check(Err(io::ErrorKind::PermissionDenied)),
        CredentialPresence::Unavailable
    ));
}

#[cfg(unix)]
#[test]
fn unreadable_metadata_is_never_treated_as_absent() {
    use std::os::unix::fs::PermissionsExt;
    let directory = tempfile::tempdir().expect("test directory");
    let path = directory.path().join("account-metadata.json");
    fs::write(&path, b"existing").expect("existing metadata");
    fs::set_permissions(&path, fs::Permissions::from_mode(0o000)).expect("deny read");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    for presence in [
        CredentialPresence::Missing,
        CredentialPresence::Present,
        CredentialPresence::Unavailable,
    ] {
        assert_eq!(
            store.load_or_create_with_entropy(presence, |_| panic!("must not mint identity")),
            Err(AccountStorageError::Io(io::ErrorKind::PermissionDenied))
        );
    }
}

#[cfg(unix)]
#[test]
fn dangling_symlink_is_unsafe_even_with_missing_custody() {
    let directory = tempfile::tempdir().expect("test directory");
    let link = directory.path().join("account-metadata.json");
    let target = directory.path().join("missing-target");
    std::os::unix::fs::symlink(&target, &link).expect("symlink fixture");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    assert_eq!(
        store.load_or_create_with_entropy(CredentialPresence::Missing, |_| panic!(
            "must not mint identity"
        )),
        Err(AccountStorageError::UnsafePath)
    );
    assert_eq!(fs::read_link(link).expect("untouched symlink"), target);
}

#[test]
fn oversize_metadata_is_not_replaced() {
    let directory = tempfile::tempdir().expect("test directory");
    let path = directory.path().join("account-metadata.json");
    let oversized = vec![b' '; 16 * 1024 + 1];
    fs::write(&path, &oversized).expect("oversize metadata");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    assert_eq!(
        store.load_or_create(CredentialPresence::Missing),
        Err(AccountStorageError::Oversize)
    );
    assert_eq!(fs::read(path).expect("preserved bytes"), oversized);
}

#[test]
fn stale_save_cannot_discard_frozen_activation() {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let mut first = store
        .load_or_create(CredentialPresence::Missing)
        .expect("initial identity");
    let mut stale = first.clone();
    let pending = first
        .begin_activation(ActivationPath::EnrollmentKey, "macos", "1.0", "booth")
        .expect("pending request")
        .clone();
    store.save(&first).expect("persist pending request");
    stale.skipped_setup = true;
    assert_eq!(store.save(&stale), Err(AccountStorageError::Changed));
    assert_eq!(
        store
            .load_or_create(CredentialPresence::Missing)
            .expect("reload")
            .pending_activation(),
        Some(&pending)
    );
}

#[test]
fn local_view_reports_only_observed_account_state() {
    use super::AccountView;

    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let mut metadata = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    let fresh = serde_json::to_value(AccountView::local(1, None, CredentialPresence::Unavailable))
        .expect("view");
    assert_eq!(
        fresh,
        serde_json::json!({
            "revision": 1,
            "setup_state": "unknown",
            "device_state": "unknown",
            "entitlement_state": "unavailable",
            "operation_state": "idle",
            "pending_cleanup": false
        })
    );

    metadata.skipped_setup = true;
    metadata.activated_public_id = Some("dev_81818181818181818181818181818181".into());
    metadata
        .begin_activation(ActivationPath::AccountSession, "macos", "1.2", "Booth")
        .expect("pending operation");
    let committed = store.save(&metadata).expect("committed metadata");
    let projected = serde_json::to_value(AccountView::local(
        2,
        Some(&committed),
        CredentialPresence::Missing,
    ))
    .expect("view");
    assert_eq!(
        projected,
        serde_json::json!({
            "revision": 2,
            "setup_state": "skipped",
            "device_state": "credential_missing",
            "entitlement_state": "unavailable",
            "operation_state": "retry_pending",
            "display_name": "Booth",
            "platform": "macos",
            "app_version": "1.2",
            "pending_cleanup": false
        })
    );
}

#[test]
fn controller_registration_leaves_metadata_unopened() {
    let directory = tempfile::tempdir().expect("test directory");
    let app = tauri::test::mock_app();
    use tauri::Manager;
    app.manage(super::AccountState::new(Some(
        directory.path().to_path_buf(),
    )));
    let managed = app.state::<super::AccountState>();
    assert!(managed.metadata_store.is_some());
    assert_eq!(
        fs::read_dir(directory.path()).expect("directory").count(),
        0
    );
    assert_eq!(
        serde_json::to_value(&*managed.view.lock().expect("cached view")).expect("view"),
        serde_json::json!({
            "revision": 0,
            "setup_state": "unknown",
            "device_state": "unknown",
            "entitlement_state": "unavailable",
            "operation_state": "idle",
            "pending_cleanup": false
        })
    );
}

#[cfg(unix)]
#[test]
fn readable_metadata_in_read_only_directory_without_lock_loads_for_every_presence() {
    use std::os::unix::fs::PermissionsExt;

    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let existing = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    let lock = directory.path().join("account-metadata.lock");
    fs::remove_file(&lock).expect("remove lock");
    let original_permissions = directory.path().metadata().expect("metadata").permissions();
    fs::set_permissions(directory.path(), fs::Permissions::from_mode(0o500))
        .expect("make directory read-only");

    let observed: Vec<_> = [
        CredentialPresence::Missing,
        CredentialPresence::Present,
        CredentialPresence::Unavailable,
    ]
    .into_iter()
    .map(|presence| {
        store.load_or_create_with_entropy(presence, |_| panic!("existing identity must win"))
    })
    .collect();
    let created_lock = lock.exists();

    fs::set_permissions(directory.path(), original_permissions).expect("restore permissions");
    assert!(observed
        .into_iter()
        .all(|result| result == Ok(existing.clone())));
    assert!(!created_lock);
}

#[test]
fn custody_outage_leaves_existing_setup_unknown_and_preserves_a_skip() {
    use super::AccountView;
    use serde_json::json;

    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let mut metadata = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    metadata.activated_public_id = Some("dev_81818181818181818181818181818181".into());
    let mut metadata = store.save(&metadata).expect("record activation");
    let project = |revision, metadata: &AccountMetadata, presence| {
        serde_json::to_value(AccountView::local(revision, Some(metadata), presence)).expect("view")
    };

    let present = project(1, &metadata, CredentialPresence::Present);
    let outage = project(2, &metadata, CredentialPresence::Unavailable);
    let missing = project(3, &metadata, CredentialPresence::Missing);
    assert_eq!(present["setup_state"], json!("completed"));
    assert_eq!(present["device_state"], json!("credential_present"));
    assert_eq!(outage["setup_state"], json!("unknown"));
    assert_eq!(outage["device_state"], json!("custody_unavailable"));
    assert_eq!(missing["setup_state"], json!("needed"));
    assert_eq!(missing["device_state"], json!("credential_missing"));

    metadata.skipped_setup = true;
    let metadata = store.save(&metadata).expect("record skip");
    let skipped = project(4, &metadata, CredentialPresence::Unavailable);
    assert_eq!(skipped["setup_state"], json!("skipped"));
    assert_eq!(skipped["device_state"], json!("custody_unavailable"));
}

#[test]
fn save_reestablishes_a_missing_lock_for_a_readable_identity() {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    let lock = directory.path().join("account-metadata.lock");
    fs::remove_file(&lock).expect("remove lock");

    let mut metadata = store
        .load_or_create(CredentialPresence::Present)
        .expect("load identity");
    assert!(!lock.exists());
    metadata.skipped_setup = true;
    let saved = store.save(&metadata).expect("save existing identity");
    assert!(lock.is_file());
    assert_eq!(store.load_or_create(CredentialPresence::Present), Ok(saved));
}

#[cfg(unix)]
#[test]
fn opened_metadata_remains_valid_after_atomic_replacement() {
    use std::os::unix::fs::MetadataExt;

    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let original = store
        .load_or_create(CredentialPresence::Missing)
        .expect("initial generation");
    let old_handle = fs::File::open(directory.path().join("account-metadata.json"))
        .expect("open published generation");
    assert_eq!(old_handle.metadata().expect("file metadata").nlink(), 1);

    let mut candidate = original.clone();
    candidate.skipped_setup = true;
    let committed = store.save(&candidate).expect("replace metadata generation");
    assert_eq!(old_handle.metadata().expect("file metadata").nlink(), 0);

    assert_eq!(read_metadata_file(old_handle), Ok(original));
    assert_eq!(
        store.load_or_create(CredentialPresence::Missing),
        Ok(committed)
    );
}

#[cfg(any(unix, windows))]
#[test]
fn multiply_linked_metadata_and_writer_lock_are_unsafe() {
    let directory = tempfile::tempdir().expect("test directory");
    let store = AccountMetadataStore::new(directory.path().to_path_buf());
    let original = store
        .load_or_create(CredentialPresence::Missing)
        .expect("initial generation");
    let alias = directory.path().join("alias");

    fs::hard_link(directory.path().join("account-metadata.json"), &alias)
        .expect("create second metadata link");
    assert_eq!(
        store.load_or_create(CredentialPresence::Missing),
        Err(AccountStorageError::UnsafePath)
    );
    fs::remove_file(&alias).expect("remove second metadata link");

    fs::hard_link(directory.path().join("account-metadata.lock"), &alias)
        .expect("create second lock link");
    assert_eq!(store.save(&original), Err(AccountStorageError::UnsafePath));
}
