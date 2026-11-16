# Standalone STT model downloads

This crate is excluded from the desktop workspace. A workspace or operator CI pass does not
establish its standalone test or clippy results. Run both forms explicitly with the repository's
pinned compiler:

```sh
cargo test --locked --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml --no-fail-fast
cargo test --locked --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml --features download --no-fail-fast
cargo clippy --locked --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml --all-targets -- -D warnings
cargo clippy --locked --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml --all-targets --features download -- -D warnings
```

Model fetching requires HTTPS at the initial request and every redirect hop, and follows at
most five redirects, matching the scripture downloader's rule. Pinned ureq3.5.0 checks the
HTTPS-only setting before opening each hop and resolves legitimate relative/scheme-relative
HTTPS redirects. It retains the downloader's existing no-proxy setting and timeout defaults.
The stream still uses64KiB chunks, verifies the pinned SHA-256, removes partial/bad/cancelled
files and atomically installs verified content; a valid cached file needs no network.

The real redirect tests use tiny pinned `abc` bytes and throwaway-CA TLS servers, never real
model weights or provider endpoints. A private `cfg(test)` thread-local CA injection enables
those fixtures in the shipped builder; it does not change redirect/proxy/deadline policy or
exist in a production build. There is no production trust override or HTTP test setting.
The new rcgen/rustls dependencies and their Cargo-generated lock additions are dev-only TLS
fixture support. Existing default test ignores/platform exclusions remain explicit.
