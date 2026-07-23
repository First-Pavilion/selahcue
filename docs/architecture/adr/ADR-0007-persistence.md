# ADR-0007: Persistence and at-rest encryption

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** High
- **Validating spike:** None required (no make-or-break unknown). Validation is by benchmark/soak measurement during build, not a gating discovery spike — see *Fallback / validation*.
- **Owner:** Software Architect
- **Related:** ARCHITECTURE §4 (Data layer), §8 (Persistence & data model), §12 (Reliability); FEASIBILITY §7 (Persistence notes)

## Decision (summary)

The desktop host persists all structured state in **SQLite in WAL mode**, **encrypted at rest with SQLCipher**. Large media is stored as **files referenced by path**, not as database BLOBs. Schema evolves through **versioned forward-migrations** with a mandatory pre-migration backup. Backups are **crash-safe** (checkpoint-then-copy, or the SQLite online backup API — never a naive file copy). Integrity is verified with **`PRAGMA integrity_check`** on demand and periodically, with a corruption-recovery path to the last good backup.

---

## Context

SelahCue is a **desktop-authoritative, offline-first** live-production tool (ARCHITECTURE §1 principles 1–2; PRD CON-2, NFR-015). The desktop host owns all live and library state; there is no server. The persistence layer must satisfy several forces simultaneously:

1. **Single-user, single-host, offline.** All creation and storage happen locally on the desktop host (PRD §Data model, l.415). There is no multi-tenant or networked-database requirement — the mobile controller holds *no* authoritative state (ARCHITECTURE §5) and reaches data only via the Rust core, never the DB directly.
2. **Crash-survivable, low work-loss.** Continuous autosave must bound work loss to ≤5s on a hard kill (FR-074, NFR-023) and crash recovery must restore exact live state (FR-075). The store must therefore survive forced shutdown without corrupting committed data.
3. **Integrity + crash-safe backups are an MVP requirement.** FR-079 requires a runnable integrity check and backups that are *never corrupt* even though the DB is live. This is explicitly cited to RP-08 §7 (the feasibility persistence notes).
4. **At-rest confidentiality of sensitive data.** Sermon audio, transcripts, and notes are sensitive under NDPA 2023 + GDPR (PRD §21). FR-154 requires at-rest confidentiality for the primary datastore + captured audio, with **app-managed SQLCipher as the default acceptance path**; OS full-disk encryption is an alternative the app must *verify* (AS-5, OD-21). FR-154 is an R3 acceptance row, but the encryption boundary is an architectural property that is far cheaper to build in from the start than to retrofit onto a plaintext store.
5. **Secrets never in plaintext.** All secrets/tokens — including the DB encryption key — live only in the OS secret store (NFR-017).
6. **Relational data model.** The entity set is relational with foreign-key relationships and joins: `service_plan`, `plan_item`, `document`, `song`+`section`, `scripture_set`, `media_ref`, `template`/`theme`, `output_profile`, `device_pairing`, `role_grant`, `audit_log`, `provider_consent`, and later `transcript`/`detection`/`sermon_note` (ARCHITECTURE §8). It needs indexed search, an append-only audit log, and forward schema evolution across releases.
7. **Storage-exhaustion safety.** Pre-write low-disk detection must protect autosave/checkpoint/backup writes, with reserved checkpoint headroom (FR-169).
8. **Bounded resource use / large media.** Media assets (video backgrounds, images, later captured audio) are large and are consumed by the GStreamer HW-decode pipeline (ADR-0005), which streams from file paths — not from encrypted DB BLOBs.

### Evidence base (FEASIBILITY §7)

The feasibility report is **evidence only, non-binding**, and contains **no OBSERVED (directly executed) findings** — all persistence findings are DOCUMENTED or INFERRED, and nothing here was benchmarked in that environment. The relevant findings:

- **DOCUMENTED (High):** SQLite in WAL mode allows concurrent readers with a single writer; on crash only uncommitted WAL transactions are lost and DB integrity is preserved. Recommended production config: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000` [P1][P2].
- **DOCUMENTED (High):** Integrity via `PRAGMA integrity_check`; backups **must include `.db` + `-wal` (+ `-shm`)**, or checkpoint first with `PRAGMA wal_checkpoint(TRUNCATE)` then copy [P2][P3].
- **DOCUMENTED (Med):** A naive `fs.copyFile` of a live WAL-mode DB **can corrupt** the backup — use the SQLite online backup API or checkpoint-then-copy [P3].
- **INFERRED (High):** SQLite is well-suited to SelahCue (single-user desktop, offline-first, library/playlist/settings, no server); store large media as **files referenced by path, not BLOBs** [§7].

**Honest gap:** FEASIBILITY §7 validates SQLite/WAL strongly but is **silent on SQLCipher / at-rest encryption**. The SQLCipher choice is grounded in FR-154, AS-5, and the privacy/threat posture (PRD §21) — **not** in a benchmarked feasibility finding. SQLCipher's runtime overhead and its C-dependency build cost are therefore *unmeasured here* and carried as residual risks below, not as proven quantities.

---

## Options considered

### Option A — SQLite (WAL) + SQLCipher  *(chosen)*

Structured data in SQLite/WAL, the whole database file transparently encrypted by SQLCipher (a page-level AES fork of SQLite that fully supports WAL, migrations, and `integrity_check`). DB key held in the OS secret store (NFR-017).

**Pros**
- Directly realises the **relational** data model (§8) with mature SQL, indexing, joins, and an append-only audit log — no query/index engine to build.
- WAL gives crash-survivable commits and concurrent-reader access, so periodic `integrity_check` and checkpoint-then-copy backups can run **without blocking the writer** or the render/control path (FR-079; NFR-024 output-isolation) [P1][P2].
- **App-managed encryption is the FR-154 default acceptance path** and does not depend on the deployment machine's disk-encryption posture. It satisfies at-rest confidentiality of the primary datastore *by construction* (ARCHITECTURE §1 principle 5), which matters for sensitive sermon data under NDPA/GDPR (PRD §21).
- Encryption is **transparent to the rest of the stack**: repositories, migrations, `integrity_check`, and checkpoint/backup all operate identically to plain SQLite; the on-disk `.db`/`-wal` are ciphertext, so a checkpoint-then-copy backup is *already* encrypted at rest — good synergy with FR-157 (backup encryption, R2).
- Mature, battle-tested, ubiquitous tooling; well-understood WAL semantics and recommended production PRAGMAs are documented [P2].

**Cons / costs**
- **SQLCipher is a C dependency** (build/link complexity across Win/macOS/Linux, and per-target signing/packaging) — heavier than a pure-Rust store. INFERRED cost; not measured here.
- **Crypto overhead** on every page read/write (commonly cited in the 5–15% range for SQLCipher, workload-dependent). **Unmeasured in FEASIBILITY** — treated as a residual risk to benchmark, not a settled figure.
- **Key management burden:** a lost/rotated key means an unreadable DB; key custody in the OS secret store (NFR-017) plus a documented key-rotation/rekey procedure is now mandatory.
- Media stored as path-referenced files sits **outside** the SQLCipher boundary (see *Consequences*), so R3 captured audio needs its own file-level encryption to satisfy FR-154.
- Adopting SQLCipher from MVP incurs the C-dependency/overhead cost before the FR-154 acceptance row lands (R3) — a deliberate forward-investment (see *Decision*).

### Option B — Plain SQLite (WAL) + OS full-disk encryption (FDE)

Same SQLite/WAL store, but confidentiality delegated to BitLocker / FileVault / LUKS at the OS level; the app verifies FDE is enabled (AS-5) and warns/blocks sensitive capture when it is not (FR-154 alternative path).

**Pros**
- No SQLCipher C dependency, **no crypto overhead** in the DB engine, simpler build/link and packaging.
- FDE protects *everything* on disk (media, logs, captured audio) uniformly, not just the DB — which the app-managed boundary does not.
- Fully retains the SQLite/WAL evidence base [P1][P2][P3] with none of the encryption unknowns.

**Cons**
- **Confidentiality then depends on a control the app does not own.** Many church deployments run on machines where FDE is off or unavailable (e.g., Windows Home lacking BitLocker without specific hardware/config). The app can *detect and warn* but cannot *guarantee* it — so this is not an acceptable **default** for sensitive sermon data under NDPA/GDPR.
- Contradicts ARCHITECTURE principle 5 ("security by construction") for the datastore: at-rest confidentiality becomes a deployment prerequisite rather than an app-guaranteed property.
- FR-154/AS-5 explicitly name **SQLCipher as the default acceptance path** and FDE as the *documented alternative the app verifies* (OD-21). Choosing FDE as the primary contradicts the requirement's stated default.

**Disposition:** Not chosen as the primary posture, but **retained as a verified alternative deployment mode.** Where an operator relies on OS FDE, the app must verify FDE is enabled and warn/block sensitive capture when unconfirmed (AS-5, FR-154, §21/§21-verification, OD-21). So Option B is not rejected outright — it is the second supported at-rest posture layered on the same SQLite/WAL substrate.

### Option C — Embedded key-value store (e.g., sled / redb / LMDB / RocksDB)

Replace SQL with an embedded KV/log-structured store, several of which are pure-Rust (sled, redb).

**Pros**
- Pure-Rust options (sled/redb) remove the C-dependency/build-complexity of SQLCipher; strong write throughput.
- Simple embedding, no SQL surface.

**Cons**
- **No relational query layer.** The §8 model (joins across plan/document/song/section, indexed scripture search, foreign-key integrity, append-only audit) would require hand-building secondary indexes, query logic, and referential integrity — reinventing what SQLite provides for free.
- **No standard migration or integrity tooling.** FR-079's `integrity_check` and versioned-migration expectations have no turnkey equivalent; we would build corruption-detection and schema-evolution machinery ourselves.
- **No transparent at-rest encryption** comparable to SQLCipher; encryption would be app-level per value, adding complexity to satisfy FR-154.
- **Maturity risk:** sled is long-lived beta (not 1.0); redb is comparatively young. Against a live-service reliability bar (RISK-005) and 8–12h soak stability (NFR-010), SQLite's decades of production hardening is a decisive advantage.
- FEASIBILITY §7 evidence base is entirely about SQLite; choosing a KV store would move us off the one persistence path the discovery work actually examined.

**Disposition:** Rejected. The relational model, mature migration/integrity tooling, and production hardening outweigh the pure-Rust build-simplicity benefit.

---

## Decision

Adopt **Option A: SQLite (WAL) + SQLCipher**, with:

1. **Engine & mode.** SQLite via SQLCipher; `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000` as the baseline production PRAGMAs [P2], tuned by measurement. WAL is retained under SQLCipher (SQLCipher supports WAL).
2. **Single-writer discipline.** The Rust core's Data layer is the **sole** DB owner; the LAN server, Tauri UI shell, and services access data only through repositories, never the DB directly. WAL's concurrent readers cover background integrity checks and backup reads; `busy_timeout` absorbs contention.
3. **Key custody.** The SQLCipher key lives **only** in the OS secret store (NFR-017); it is never written to logs, plaintext files, or diagnostics bundles (FR-082). A documented rekey/rotation procedure exists; loss of key = loss of DB (accepted, mitigated by backups + key custody).
4. **Media as path-referenced files.** Large media is stored on disk and referenced by `media_ref` path, not as BLOBs — keeping the DB small (fast `integrity_check`/backups) and letting the GStreamer HW-decode pipeline stream files directly (ADR-0005). Missing media → placeholder, never black (FR-070).
5. **Versioned forward-migrations.** Schema version tracked (e.g., `PRAGMA user_version` / a `schema_migrations` table); **forward-only** migrations run at startup. **Every migration is preceded by a crash-safe backup** (below); the documented rollback is *restore the pre-migration backup* — downgrade of an already-migrated DB is not supported (ARCHITECTURE §8).
6. **Crash-safe backups (checkpoint-then-copy).** Backups **never** use a naive live file copy [P3]. Either: `PRAGMA wal_checkpoint(TRUNCATE)` then copy the (ciphertext) `.db`, **or** use the SQLite online backup API [P2][P3]. Backups run off the render/control path (NFR-024) and honour the reserved checkpoint headroom (FR-169). Because the file is SQLCipher-encrypted, the copied artifact is encrypted at rest, feeding FR-157 (R2) and warning on export to untrusted locations.
7. **Integrity + recovery.** `PRAGMA integrity_check` is runnable on demand and periodically; on detected corruption the app surfaces it (never silent) and offers restore from the last good backup — the corruption-recovery path (FR-079; RP-08 §7).
8. **At-rest posture: SQLCipher default, OS-FDE verified alternative.** SQLCipher is the default (FR-154 acceptance path). Where an operator instead relies on OS FDE, the app verifies FDE is enabled and warns/blocks sensitive capture when unconfirmed (AS-5, FR-154, OD-21).

**Why adopt SQLCipher from MVP even though FR-154 lands at R3:** the at-rest encryption boundary is structural. Building repositories, migrations, backup, and integrity tooling to be encryption-aware from the first release is far cheaper and lower-risk than retrofitting encryption onto a plaintext store once R3 sensitive data (transcripts/notes/captured audio) arrives. The MVP cost is a small, measurable overhead and a C dependency; the payoff is R3 privacy-readiness with no migration of existing plaintext data.

---

## Consequences

### Positive
- Relational model, indexed search, FK integrity, and an append-only audit log come from a mature engine — minimal bespoke storage code (RISK-005 reliability, NFR-010 soak).
- Crash-survivable commits + concurrent-reader WAL let integrity checks and backups run **without touching live output** (NFR-024; FR-079).
- At-rest confidentiality of the primary datastore is guaranteed by the app, independent of deployment disk posture (FR-154 default; PRD §21; principle 5).
- Encrypted backups fall out naturally (ciphertext on disk), aligning with FR-157 (R2).
- Small DB (media externalised) → fast `integrity_check`, fast backup/restore, and a clean handoff to the GStreamer HW-decode pipeline (ADR-0005).

### Negative / costs
- **SQLCipher C dependency** raises per-OS build, link, and code-signing complexity (ADR-0012) versus a pure-Rust store.
- **Unmeasured crypto overhead** on DB I/O (residual risk; to be benchmarked, see below). Must fit within performance and soak budgets (NFR bounds).
- **Key-loss = data-loss:** DB is unrecoverable without the SQLCipher key; mandates disciplined key custody (NFR-017) + reliable backups.
- **Media outside the encryption boundary:** path-referenced media files are *not* inside SQLCipher. General presentation media (backgrounds/images) is user-supplied and non-confidential, so this is acceptable. **But R3 captured audio is sensitive (FR-154) and must be given its own file-level at-rest encryption** — an explicit R3 obligation this ADR flags, not something SQLCipher covers for free.

### What this commits us to
- A **single-writer** data layer as the only DB owner; all other components go through repositories.
- The SQLCipher key in the **OS secret store only**, plus a documented rekey/rotation procedure.
- **Encryption-aware** migration, backup, and integrity tooling from MVP.
- **Forward-only** schema evolution with a mandatory pre-migration backup as the rollback mechanism.
- Backups implemented **only** via checkpoint-then-copy or the online backup API (a naive copy is prohibited).
- An **R3 file-level encryption** mechanism for captured audio to close the FR-154 gap on path-referenced sensitive media.
- Implementing and verifying the **OS-FDE alternative** path (FDE-enabled detection + warn/block on unconfirmed capture) per AS-5/OD-21.

---

## Fallback / validation

Confidence is **High** and **no gating discovery spike is required**: each element is individually well-evidenced (SQLite/WAL DOCUMENTED-High [P1][P2][P3]; the split-store and path-referenced-media design INFERRED-High [§7]), and there is no make-or-break unknown analogous to ADR-0006's zero-copy interop. This is deliberately *not* overstated — the two items FEASIBILITY did **not** measure are carried as build-time validations with fallbacks, not as proven facts:

1. **SQLCipher overhead (unmeasured).** *Validation:* benchmark encrypted vs. plaintext read/write and include the encrypted DB in the 8–12h soak (NFR-010; METRIC-003). *Fallback if overhead breaches budgets on Tier-A hardware:* tune SQLCipher (page size, KDF iteration count, cipher settings) and cache; only if that fails, degrade to **Option B** (plain SQLite + verified OS FDE) as the at-rest posture — the substrate (SQLite/WAL, migrations, backups, integrity) is unchanged, so this is a configuration change, not a re-architecture. This is the concrete reason Option B is retained rather than discarded.
2. **Crash-safe backup + corruption recovery.** *Validation:* fault-injection tests — kill mid-write, then verify checkpoint-then-copy / online-backup restores cleanly, and that `integrity_check` + restore recover a deliberately corrupted DB (FR-079; NFR-024 fault-injection).
3. **OS-FDE verification path.** *Validation:* confirm FDE-enabled detection and warn/block-on-unconfirmed behaviour on Windows (BitLocker), macOS (FileVault), and Linux (LUKS) (AS-5, FR-154, OD-21).

---

## Requirement / PRD references

- **FR-074 / NFR-023** — Continuous autosave; ≤5s work-loss bound (crash-survivable store).
- **FR-075** — Crash recovery + crash-loop breaker (restore exact live state).
- **FR-079** — Database integrity check + crash-safe (WAL-aware) backup (cites RP-08 §7). *(MVP)*
- **FR-138 / FR-139** — Safe import + plan export/import with media refs intact (path-referenced media model). *(MVP)*
- **FR-154** — At-rest confidentiality for primary datastore + captured audio; SQLCipher default, OS-FDE verified alternative (C9, OD-21). *(R3)*
- **FR-157** — Backup encryption + untrusted-location warning. *(R2)*
- **FR-169** — Storage-exhaustion detection; reserved checkpoint headroom. *(MVP)*
- **FR-070** — Missing-media placeholder (path-referenced media may be absent). *(MVP)*
- **FR-082** — No secrets/transcripts in logs or diagnostics (key never logged). *(MVP)*
- **NFR-015 / CON-2** — Offline operation of the core (local persistence, no server). *(MVP)*
- **NFR-017** — Secrets/tokens (incl. DB key) only in OS secret store. *(MVP)*
- **NFR-024** — Output-failure isolation (integrity/backup work must not blank output). *(MVP)*
- **NFR-010 / METRIC-003** — 8–12h soak stability (encrypted store included in soak).
- **AS-5** — At-rest confidentiality defaults to SQLCipher; OS FDE is a verified deployment prerequisite (§21).
- **OD-21** — Open decision: OS-FDE-reliance verification behaviour.
- **ARCHITECTURE** §4 (Data layer), §8 (Persistence & data model), §12 (Reliability).
- **FEASIBILITY** §7 (Persistence notes) — sources [P1] micrologics.org SQLite-in-production; [P2] oneuptime.com 2026-02-02 SQLite production setup; [P3] scottspence.com SQLite corruption / fs.copyFile. All accessed 2026-07-23; DOCUMENTED-secondary, to be re-verified by the validations above.
