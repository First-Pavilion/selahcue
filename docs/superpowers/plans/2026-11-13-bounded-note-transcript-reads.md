# Bounded Note Transcript Reads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound persisted transcript reads for note timestamp linking to the same ordered 5,000-segment prefix already used by the matcher.

**Architecture:** Add a segment-only SQL-LIMIT repository read and use it in the operator's best-effort timestamp reload helper. The existing full transcript loader remains available unchanged to generation, viewing and export. The core matcher and its constant are the source of the cap and behavior.

**Tech Stack:** Rust, rusqlite/SQLite, Tauri operator, existing cargo tests and make ci.

**Spec:** `docs/delivery/goals/17tnw2axpru-bounded-note-transcript-reads.md`, transcribed from https://app.clickup.com/t/17tnw2axpru on 2026-11-13.

## Global Constraints

- MAX_LINK_SEGMENTS = 5_000; use the existing core constant, never another literal in production.
- Timestamp matching and positional bounds must use exactly the same original ordered prefix as before.
- Full transcript generation, viewing, export and persistence remain uncapped; no schema or dependency change.
- No raw transcript, correction or detected-reference text in production diagnostics.
- Missing stores, missing transcripts and database errors preserve the best-effort empty-timestamps behavior.
- One existing ClickUp ticket per PR; memoization is a separate ticket and outside this change.
- Full local make ci is mandatory; Windows CI setup is explicitly cancelled by the user.

## Review Focus

- Large transcripts: stored rows beyond the prefix must not be materialized, including corrections/detections not needed by timestamp linking.
- Ordering: sparse ord values and database IDs must preserve the same original order as the full loader.
- Prefix boundary: text matching and positional fallback must remain unchanged when later segments contain better matches or later timestamps.
- Missing/error data: note drafts still load without timestamps when their store is absent or their bounded read fails.
- Other consumers: the full loader still returns all persisted segments and related data.

---

### Task 1: Bound the timestamp-linking repository read

**Files:**
- Modify: `implementation/desktop/crates/selahcue-data/src/transcript_repo.rs`
- Modify: `implementation/desktop/crates/selahcue-operator/src/main.rs` (timestamp read helper and its tests only)
- Test: `implementation/desktop/crates/selahcue-data/tests/test_transcript_repo.rs`
- Test: `implementation/desktop/crates/selahcue-core/tests/test_note_timestamps.rs` (reuse unchanged unless a missing boundary assertion requires an addition)
- Update: this plan's checkboxes and goal contract evidence, without adding unverified passes.

**Interfaces:**
- Consumes: `selahcue_core::providers::MAX_LINK_SEGMENTS: usize`; `TranscriptSegment`; `with_transcript_db`; existing `link_timestamps` and `sermon_note_draft_json`.
- Produces: `pub fn load_segments_prefix(db: &Database, transcript_id: i64, limit: usize) -> Result<Vec<TranscriptSegment>>` in transcript_repo; returns an ordered segment-only prefix, empty for a missing transcript or zero limit. Use a checked/clamped nonnegative SQL integer limit so an oversized usize cannot become SQLite's unlimited negative LIMIT.
- Keeps: `load(db: &Database, transcript_id: i64) -> Result<TranscriptDetail>` unchanged in observable behavior.

- [x] **Step 1: Write failing behavior and query-bound tests.** Seed at least 20,001 stored segments with distinct order/times; verify bounded output equals the full loader's first MAX_LINK_SEGMENTS and full load still returns all rows. Include noncontiguous ord ordering and zero/missing/small/oversized limits. Prove the read itself is bounded with a malformed text row just beyond the prefix (bounded read succeeds; full load or an unbounded-then-truncated mutation fails). A malformed row inside the prefix must error without leaking its text. Add operator regression showing JSON timestamps equal the original full-input result, including unmatched chapter positional fallback and a stronger match past the cap; cover empty-store/missing-ID graceful fallback with existing fixtures.
- [x] **Step 2: Run the new focused tests before production changes and record the expected failure.** Use `cargo test -p selahcue-data --test test_transcript_repo` and `cargo test --manifest-path crates/selahcue-operator/Cargo.toml --bin selahcue-operator persisted_timestamp_read` from `implementation/desktop`; compilation failure only because the new function is absent is an acceptable initial red, then demonstrate the unbounded-read mutation is caught after implementation.
- [x] **Step 3: Implement the bounded reader and wire the helper.** Use the existing (transcript_id, ord) index with WHERE, ORDER BY ord and SQL LIMIT; decode rows consistently with the full loader, sharing a small private row decoder if it avoids duplication. Do not read corrections, detections or entire parent detail. `transcript_segments_for` passes MAX_LINK_SEGMENTS directly and retains unwrap_or_default. Leave all full-loader callers alone.
- [x] **Step 4: Verify focused behavior and bounded work.** Run the repository integration suite, `cargo test -p selahcue-core --test test_note_timestamps`, and affected operator tests with the repository's existing feature configuration. Record commands, result counts, timing and fixture size. Temporarily remove the SQL limit in a safe local mutation, run the bound regression to observe failure, then restore and rerun that regression. Do not claim timing on the target Windows device.
- [x] **Step 5: Self-review and commit implementation.** Ensure the diff stays within this scope; no generated artifacts, secrets, unrelated Windows diagnostics, schema or lockfile edits. Controller runs full `make ci` once on the final reviewed source and coordinates independent code, security, QA and performance review, fixes/re-review, PR, authorized merge and ClickUp QA readback.

The pre-change data run failed on the absent prefix API. Host paging interrupted the pre-change operator build. The post-change operator filters passed, including the retention suite with local loopback enabled.
