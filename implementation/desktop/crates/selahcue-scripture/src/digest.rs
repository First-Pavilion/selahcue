//! SHA-256 helpers shared by the installer and the downloader (feature `installed`).

use std::io::Read;
use std::path::Path;

use sha2::{Digest, Sha256};

/// Bytes read per chunk while hashing a file, so a large file is never held whole.
const HASH_CHUNK_BYTES: usize = 64 * 1024;

/// Lowercase-hex encode a byte slice (no external hex dependency).
pub(crate) fn hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        s.push(HEX[(b >> 4) as usize] as char);
        s.push(HEX[(b & 0x0f) as usize] as char);
    }
    s
}

/// Lowercase-hex SHA-256 of `bytes`.
pub(crate) fn sha256_hex(bytes: &[u8]) -> String {
    hex_lower(&Sha256::digest(bytes))
}

/// Lowercase-hex SHA-256 of the file at `path`, read in bounded chunks.
pub(crate) fn sha256_file(path: &Path) -> std::io::Result<String> {
    let mut file = std::fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; HASH_CHUNK_BYTES];
    loop {
        let n = file.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hex_lower(&hasher.finalize()))
}
