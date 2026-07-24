# Code Review — Batch 7ad (search-hit highlighting + crash-loop breaker + storage guard)

- **Scope reviewed:** enriched scripture search results (verse-text snippets with match highlighting, keyboard hit selection) and the FR-169/NFR-023 guards (crash-loop breaker, low-disk/critical-disk handling) with their `guard.rs` module.
- **Method:** independent adversarial review via the Workflow tool (run `wf_a3c5448f-f47`, 12 agents; 2 lenses: guard semantics · hits UI/wire) → per-finding adversarial verification. No self-approval.
- **Raised → confirmed → unique:** **10 confirmed → 8 unique (A–H)** · 0 refuted.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | The breaker's "start clean" **clobbered the session it promised to preserve**: the first-run path UPSERTed the singleton session row with demo state (and each breaker trip inserted an orphan demo-plan row — unbounded growth under a supervisor) | a breaker-tripped launch runs in **clean mode with checkpointing fully disabled** — `ensure_plan`, the first-run write, autosave, and the exit save are all skipped; the preserved session is untouched and a later stable relaunch resumes it (the banner now says exactly that) |
| B | med | A CRITICAL disk at startup printed "checkpoint writes are PAUSED" but the halt only engaged after the first 60s check — plan inserts + session UPSERTs ran on the full disk meanwhile | the startup status seeds `disk_critical`; `ensure_plan` and the first-run write are skipped when critical |
| C | low | The clean-exit final save bypassed the disk-critical halt | the exit save honours both halts |
| D | low | An fs4 read failure while halted left checkpoints paused **silently** forever | unknown-free-space while halted reports every check ("checkpoints remain paused") |
| E | med | A new operator against a pre-7ad host showed **zero search results** (it read only the new `hits` field) | the remote client synthesizes text-less hits from the compat `references` list |
| F | med | The highlight could be entirely invisible: snippets always started at the verse start, so matches deep in a long verse sat past the ellipsis | the snippet windows onto the first match (word-boundary trim + leading "…") |
| G | low | ArrowUp from the unselected state skipped the last hit (modulo off-by-one) | explicit first-press cases (Down → first, Up → last) |
| H | low | The translation chip read the live dropdown (mislabeling stale hits after a switch), and the highlight tie-break could leave match tails unbolded | hits carry the translation they were searched in; equal-index ties prefer the longest word |

## Verification after remediation

- `cargo test --workspace --features selahcue-lan/server`: **259 passed** (+3 guard tests: breaker window/limit/skew, disk thresholds, journal boundedness; the wire E2E now asserts hit snippets). Clippy `-D warnings` clean; operator crate clean; JS syntax-checked; Flutter **20**.
- Fixture byte-stability: the pinned `scripture_results` fixture (hits empty → omitted) is unchanged; `hits` verified skip-if-empty.
- Guard invariants: the stability mark precedes the disk-critical early return (a full disk cannot spuriously trip the breaker — verified by the review); the launch journal is bounded by the window.

## Residual notes (owner disposition on `86ajp09td`)

- The FR's interactive **Resume-vs-Start-clean dialog** is delivered as automatic start-clean + preserved session (relaunch-to-resume); a GUI dialog is a UI-story slice.
- **Per-item disable** ("disable suspected item") needs crash attribution that doesn't exist yet.
- Storage-exhaustion fault-injection is unit-level (pure threshold + journal tests); a full end-to-end disk-full simulation needs a loopback volume harness (CI-hostile).
