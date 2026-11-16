# Native account foundation evidence — 14 November 2026

This source checkpoint implements durable install identity, verified entitlement display, native credential custody and an account worker. The Account Setup screens and installed production acceptance remain later work. This is not a public release readiness claim.

## Recovery and compatibility

New strict native activation routes freeze the protocol version, mode, nonce and expected device identity. Durable operation receipts keep recovery on its original device and licence, preventing accidental extra seats. A lost response followed by deletion or expiry of its original token can produce an authenticated identity proof containing no secret. Reminting requires a separate, explicit recovery action. Unsupported servers and ambiguous legacy operations cannot silently fall back to allocating another device. Existing legacy endpoints preserve their callers.

Metadata generation checks precede every bound dispatch and accepted response before credential storage. A proven first-attempt refusal can retire its operation; an ambiguous request keeps its identity. A short lock serializes cooperating processes' local account-session writes and matching removal. HTTP and device credential operations stay outside that lock. Account reads reflect exact signed expiry while network work is pending.

## Scoped validation

- Initial Task 3 implementation: 524 standalone operator tests and 189 licensing tests, plus 21 PostgreSQL/API tests including five Rust/Django cases. Linked desktop and operator release scans used the separate Cargo root and installer feature profile with a debug positive control. These were macOS arm64 builds, not final Windows installer bytes.
- Bound protocol fix: 136 scoped PostgreSQL/API tests, including seven Rust/Django cases; 48 focused operator and 190 licensing tests; strict Clippy and migration drift checks. Cases cover competing licences, an entirely lost initial response, token deletion, nonce contention, authorization boundaries and explicit recovery of the same device.
- Refusal and generation fix: 55 focused operator, 191 licensing and 31 scoped PostgreSQL/API tests, including those seven wire cases; strict Clippy. Deterministic tests cover competing processes, stale retirement versus retry admission, and refusal to write credentials from an already stale response.
- Matching cleanup fix: 58 focused operator tests, 11 licensing custody tests and strict Clippy and formatting checks. A failing regression reproduced replacement-session loss; passing tests cover contention, preserved retry authority, acknowledged cleanup without another HTTP request, and unsafe lock paths.

Each task and fix received independent scoped code review. The final controller review passed at `7e894cd6`. The branch was then integrated with main `7e168771` without conflicts. Whole-branch review and hosted CI are separate gates. These counts do not represent one full suite on the eventual release commit.

## Limits

PostgreSQL tests used a disposable local PostgreSQL 17 server with synthetic trust and data. Native wire tests used actual Rust/Django HTTP with in-memory credential storage. File locking was exercised on macOS. Real Keychain, Credential Manager and Secret Service behavior, Windows and Ubuntu locking, WebView flows, physical outputs, production issuer/DNS/mail and final packaged builds remain unverified.

Metadata and OS credential changes do not form one atomic transaction. The short lock protects cooperating native writers, not arbitrary external keyring tools.
