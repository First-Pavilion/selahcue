# Code Review — batch 7d: LAN control core (protocol · RBAC · sessions)

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context workflow. No self-approval.
**Date:** 2026-07-23
**Scope:** `selahcue-lan` — `protocol.rs`, `rbac.rs`, `session.rs`, `lib.rs`,
`Cargo.toml`, and the `tests/` suite. (The TLS WebSocket transport is a separate later
batch and was out of scope by design.)

## Verdict: PASS (1 confirmed finding remediated; targeted hardening added)

14 agents ran (4 review lenses + 10 verify). **10 findings raised → 1 confirmed** after
adversarial verification; **9 dismissed** (each empirically refuted — mostly
"reachable only via an out-of-scope caller/transport bug" or "hardening nit already
covered by a sibling assertion"). Re-verified: `cargo test -p selahcue-lan` **30/30**,
full workspace **80/80**, clippy clean.

## Confirmed & fixed

### M1 (Medium) — `AuthRequest`'s derived `Debug` leaked the bearer token in cleartext
The crate establishes a test-enforced invariant that bearer tokens are never printable
(`SessionToken` has a redacted `Debug` guarded by `token_debug_is_redacted`). But
`AuthRequest` — the wire frame that actually *carries* a live token — derived `Debug`,
so a transport logging a received auth frame (`tracing::debug!(?auth_request)`) would
write the credential to logs in cleartext.

**Fix:** removed the derived `Debug` and hand-wrote one that redacts `token` (shows `v`
and `device_id` for diagnostics). **Regression test:** `auth_request_debug_redacts_the_token`.

## Hardening added (dismissed findings that were still worth closing on a security boundary)

Although verified as *not reachable defects* in the pure core (they require an
out-of-scope caller to violate the documented token/code-generation contract), these are
cheap and this is auth code, so defence-in-depth was added:

- **Empty token / empty code accepted** — `authenticate` now rejects an empty presented
  token before any comparison; `offer_pairing`/`redeem` reject empty codes. Tests:
  `empty_token_never_authenticates`, `empty_code_cannot_be_offered_or_redeemed`.
- **Version-check convenience** — added `Request::version_supported()` /
  `AuthRequest::version_supported()` so the future transport can gate inbound frames
  correct-by-construction; documented that the transport MUST call it. Test:
  `version_support_check`.
- **Regression tests for invariants the reviewers noted were correct-but-untested:**
  cross-device token confusion (`a_device_cannot_use_another_devices_token`),
  prefix/length-mismatch tokens (`prefix_and_length_mismatched_tokens_are_rejected`),
  exact expiry boundary (`expiry_is_inclusive_at_the_exact_boundary`), and a direct
  Producer×scripture RBAC assertion.

## Notable dismissed finding (surfaced for a product decision)

- **Assistant can `Clear` the live output** (map: `Clear` → `Navigate`, which Assistant
  holds). Verified as *deliberate and tested*, not a bug — but whether an Assistant
  should be able to blank the live output (vs. only prepare/stage) is a genuine **RBAC
  policy question** worth confirming with the product owner. Flagged at the build gate;
  no code change made.

## Design notes

- `authorize()` is the single choke point; each `Command` maps to exactly one
  `Permission` via an exhaustive `match` (adding a command without updating the map fails
  to compile). Roles are strict supersets (asserted by
  `permission_sets_are_strictly_ordered_supersets`).
- Token/code generation and the clock are caller-injected, keeping the core pure and
  exhaustively testable; token comparison is constant-time (`subtle`).

## Independence statement

Reviewed by fresh-context agents that did not author the code, over the listed files,
using the crate's own test/lint tooling. Findings were adversarially verified
(default-to-not-real) before being reported; the confirmed defect was fixed and
re-verified.
