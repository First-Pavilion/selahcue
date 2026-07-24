# Code Review — Batch 7ai (SQLCipher key acquisition)

- **Scope:** story `86ajp5vp6` — the app shell acquires the at-rest encryption key: OS secret store (random 256-bit, generated on first run) with an **Argon2id passphrase** path (`SELAHCUE_PASSPHRASE`, OWASP parameters, per-install persisted salt), wired into `SessionStore` behind the `encryption` feature; CI/make encryption lanes extended to the desktop crate.
- **Method:** independent security review via the Workflow tool (run `wf_e8603008-4db`, 7 agents, security lens with **empirical reproduction** — the verifier actually built SQLCipher and exercised the failure modes) → per-finding verification. No self-approval.
- **Raised → confirmed → unique:** **6 → 6 (A–F)** · 0 refuted.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | A first-run keychain hiccup **minted a plaintext store**, after which every healthy run keyed-opened the plain file, failed with a corruption-looking error, and ran in-memory — persistence dead forever, real data unencrypted on disk | `open_store` is now a **header-discriminated state machine**: the SQLite magic identifies a plaintext store, which keeps opening plain (with an honest "migration pending" note) — a keyed open of a plain file can never happen |
| B | high | Wrong key / no key / real corruption were **indistinguishable** ("file is not a database"), preceded by a **false** "opening UNENCRYPTED" message — inviting the operator to delete weeks of data that was one keychain-unlock away | encrypted-store failures **hard-stop persistence with the true cause** ("the acquired key does not open it… file is UNTOUCHED; do NOT delete it"); the unencrypted fallback exists **only** for a nonexistent file |
| C | med | Switching key sources (keychain ↔ passphrase) silently locked the store out with no migration path | the mismatch now names the likely causes explicitly; a **rekey/migration tool is the recorded story remainder** |
| D | med | The backup story was false without `key.salt`; a missing salt was silently regenerated next to an existing store | loud "restore key.salt from backup" warning when a store exists; the backup requirement documented in the module |
| E | low | Only the pure functions were CI-tested | 3 state-machine tests reproduce the review's scenarios with **byte-level file-untouched assertions** (fresh-encrypted round-trip + wrong-key stop; plaintext store keeps working beside an acquired key; encrypted + no key stops) |
| F | low | The env passphrase `String` was never wiped; generation buffers lingered | passphrase + hex + buffers zeroized; residual stack copies documented as accepted |

## Verification after remediation

- `cargo test -p selahcue-desktop --features encryption`: **11 passed** (3 key-derivation/salt/hex + 3 open-state-machine + guards/keys); workspace **262** + Flutter **20**; clippy clean both feature sets; `cargo deny` green with the new deps (keyring/argon2/getrandom/zeroize — all permissive).
- CI/make encryption lanes now build+test the desktop crate with the feature on Linux/macOS (Windows keeps its documented SQLCipher-toolchain skip).

## Residual notes (recorded on the story)

- **Rekey/migration tool** (plaintext→encrypted in place via `sqlcipher_export`, and key rotation) — the state machine deliberately defers rather than guesses.
- Env-var passphrase visibility to same-user processes is accepted for a single-operator machine; a config-file secret is the refinement.
- Single-instance assumption on `key.salt` (no cross-process lock) — matches the app's one-instance reality.
