//! SQLCipher key acquisition (FR-154; story 86ajp5vp6).
//!
//! Key sources, in order:
//! 1. **Passphrase** — if `SELAHCUE_PASSPHRASE` is set, the key derives via
//!    **Argon2id** (OWASP parameters) with a per-install random salt persisted
//!    beside the store (`key.salt`). Deterministic: the same passphrase + salt
//!    file always yields the same key, so backups restore across machines.
//! 2. **OS secret store** — a random 256-bit key generated on first run and
//!    held by the platform keychain (macOS Keychain / Windows Credential
//!    Manager / Linux Secret Service).
//! 3. **None** — no store reachable: the caller falls back to an UNENCRYPTED
//!    open with a loud warning (a service must never be blocked by a keychain
//!    hiccup; FR-154 is best-effort at-rest protection, not a boot gate).
//!
//! Key bytes ride in [`EncryptionKey`], which zeroizes on drop; transient
//! copies (the keychain hex, generation buffers, the env passphrase) are wiped
//! best-effort. Stack copies of the 32-byte array during moves are accepted.
//!
//! **Backup note:** a passphrase-derived key needs BOTH the passphrase and the
//! per-install `key.salt` file — back up `key.salt` alongside the store, or a
//! restore cannot derive the same key (the app warns loudly when it detects a
//! regenerated salt next to an existing store).

use selahcue_data::EncryptionKey;
use std::path::Path;
use zeroize::Zeroize;

const KEYRING_SERVICE: &str = "SelahCue";
const KEYRING_USER: &str = "database-key";
const SALT_FILE: &str = "key.salt";

/// Where an acquired key came from (reported, never silent).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeySource {
    Passphrase,
    SecretStore,
}

/// Derive a 256-bit key from `passphrase` + `salt` via Argon2id (OWASP m=19MiB,
/// t=2, p=1). Pure and deterministic — unit-tested.
pub fn derive_key(passphrase: &str, salt: &[u8]) -> Option<[u8; 32]> {
    use argon2::{Algorithm, Argon2, Params, Version};
    let params = Params::new(19 * 1024, 2, 1, Some(32)).ok()?;
    let argon = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);
    let mut out = [0u8; 32];
    argon
        .hash_password_into(passphrase.as_bytes(), salt, &mut out)
        .ok()?;
    Some(out)
}

/// Load (or create) the per-install salt beside the store. A REGENERATED salt
/// next to an existing store is loudly flagged: the previously derived key is
/// no longer reproducible (the store's open will hard-stop rather than guess).
fn salt(data_dir: &Path) -> Option<Vec<u8>> {
    let path = data_dir.join(SALT_FILE);
    if let Ok(existing) = std::fs::read(&path) {
        if existing.len() >= 16 {
            return Some(existing);
        }
    }
    if data_dir.join("selahcue.db3").exists() {
        eprintln!(
            "SelahCue: key.salt is MISSING but a store exists — a passphrase key \
             derived now will NOT match the store. Restore key.salt from backup."
        );
    }
    let fresh: Vec<u8> = random_bytes(16)?;
    if let Err(e) = std::fs::write(&path, &fresh) {
        eprintln!("SelahCue: could not persist the key salt ({e}).");
        return None;
    }
    Some(fresh)
}

fn random_bytes(n: usize) -> Option<Vec<u8>> {
    let mut buf = vec![0u8; n];
    getrandom::getrandom(&mut buf).ok()?;
    Some(buf)
}

/// Acquire the database key per the source order above.
pub fn acquire(data_dir: &Path) -> Option<(EncryptionKey, KeySource)> {
    // 1. Passphrase (explicit operator choice wins). NOTE: env vars are
    // visible to same-user processes — acceptable for a single-operator
    // machine; a config-file secret is the later refinement.
    if let Ok(mut passphrase) = std::env::var("SELAHCUE_PASSPHRASE") {
        if !passphrase.is_empty() {
            let salt = salt(data_dir)?;
            let key = derive_key(&passphrase, &salt);
            passphrase.zeroize();
            return key.map(|k| (EncryptionKey::from_raw(k), KeySource::Passphrase));
        }
    }
    // 2. OS secret store: fetch, or generate + store on first run.
    let entry = match keyring::Entry::new(KEYRING_SERVICE, KEYRING_USER) {
        Ok(e) => e,
        Err(e) => {
            eprintln!("SelahCue: no OS secret store available ({e}).");
            return None;
        }
    };
    match entry.get_password() {
        Ok(mut hex) => {
            let parsed = parse_hex_key(&hex);
            hex.zeroize(); // key-bearing string must not linger
            parsed.map(|k| (EncryptionKey::from_raw(k), KeySource::SecretStore))
        }
        Err(keyring::Error::NoEntry) => {
            let mut fresh = random_bytes(32)?;
            let mut key = [0u8; 32];
            key.copy_from_slice(&fresh);
            let mut hex = String::with_capacity(64);
            for b in &fresh {
                use std::fmt::Write as _;
                let _ = write!(hex, "{b:02x}");
            }
            fresh.zeroize();
            let stored = entry.set_password(&hex);
            hex.zeroize();
            if let Err(e) = stored {
                eprintln!("SelahCue: could not store the database key ({e}).");
                key.zeroize();
                return None;
            }
            Some((EncryptionKey::from_raw(key), KeySource::SecretStore))
        }
        Err(e) => {
            eprintln!("SelahCue: could not read the database key ({e}).");
            None
        }
    }
}

fn parse_hex_key(hex: &str) -> Option<[u8; 32]> {
    let hex = hex.trim();
    if hex.len() != 64 || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
        eprintln!("SelahCue: the stored database key is malformed.");
        return None;
    }
    let mut key = [0u8; 32];
    for (i, byte) in key.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&hex[i * 2..i * 2 + 2], 16).ok()?;
    }
    Some(key)
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn argon2id_derivation_is_deterministic_and_sensitive() {
        let salt = b"0123456789abcdef";
        let a = derive_key("shepherd", salt).unwrap();
        let b = derive_key("shepherd", salt).unwrap();
        assert_eq!(a, b, "same passphrase + salt = same key");
        assert_ne!(
            derive_key("shepherd", salt).unwrap(),
            derive_key("Shepherd", salt).unwrap(),
            "passphrase-sensitive"
        );
        assert_ne!(
            derive_key("shepherd", salt).unwrap(),
            derive_key("shepherd", b"fedcba9876543210").unwrap(),
            "salt-sensitive"
        );
    }

    #[test]
    fn salt_persists_and_round_trips() {
        let dir = std::env::temp_dir().join(format!("selahcue-keys-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let first = salt(&dir).unwrap();
        assert!(first.len() >= 16);
        assert_eq!(salt(&dir).unwrap(), first, "stable across calls");
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn hex_keys_round_trip_and_garbage_is_rejected() {
        let key = [0xabu8; 32];
        let hex: String = key.iter().map(|b| format!("{b:02x}")).collect();
        assert_eq!(parse_hex_key(&hex), Some(key));
        assert_eq!(parse_hex_key("short"), None);
        assert_eq!(parse_hex_key(&"zz".repeat(32)), None);
    }
}
