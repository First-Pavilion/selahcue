# Code Review — Batch 8a (Songs: multi-slide items, S8-1)

- **Scope:** story `86ajpzha3` (S8-1) — the first Stage-8 implementation batch. Turn one-slide plan items into real multi-slide **songs**. Executed via the `/goal` engine (`TASK-86ajpzha3-songs.md`, validator `--require-complete` PASS, 6/6).
- **Method:** a 3-lens insertion-point **map** (`wf_247548a0-429`) before editing, then an independent **adversarial review** (`wf_bee2e975-576`, 4 lenses — navigation semantics · migration/persistence safety · wire compatibility · recovery honesty — each finding verified to refute). No self-approval.
- **Raised → confirmed → fixed: 1 → 1 → fixed** (3 lenses clean).

## What shipped

- **Model** (`selahcue-core`): `PlanItem.stanzas: Vec<Stanza>` (a stanza = the lines of one slide) + `slide_count()`; a **total** plain-text importer (`stanzas_from_text`/`to_text`, blank-line split, CRLF-normalizing).
- **Persistence**: migration **v6** (additive) — `plan_item.content` (NULL = title-only, so every existing row is unchanged) + `session_state` live/staged/cursor slide columns; NULL backfill.
- **Controller**: `Next`/`Previous` advance slide-by-slide **within** a song before crossing plan items (`cursor_slide`, surviving a scripture interruption); `GoLive` commits the current slide; the stage "next" follows the song's next stanza then falls back to Preview; the snapshot carries the slide positions; `restore` clamps an out-of-range slide to 0 (recovery honesty); `AddItem` gains optional stanza content.
- **Wire**: `PlanItemView.slide_count`/`slide_index` + `AddItem.content`, all additive (`#[serde(default, skip_serializing_if)]`) — the pinned cross-language fixtures stay **byte-identical**, VERSION unchanged at 2.
- **Clients**: operator webview shows "song · 2/6" + a lyrics box on the add-row; the Flutter `PlanItemView` parses the fields + a `slideBadge`, and plan rows render it.

## Finding and disposition

| Sev | Defect | Fix |
|---|---|---|
| med | **Removing a LIVE song then crashing lost its lyric body.** The free-slide capture stored only `slide.title` (`live_free_text`); recovery rebuilt a title-only `Slide::title`. Lossless *before* 8a because every live slide was title-only — but S8-1's `item_slide` gives songs a body, so a removed-live song recovered as a bare title (the on-screen verse gone). NFR-024 not violated (the title still renders), but the audience content changed across the crash | Capture **and persist the body** (`live_free_body`, migration **v7**, append-only since v6 already shipped to main); `restore` rebuilds `Slide::new(title, body)` verbatim. Regression test `removing_a_live_song_recovers_its_lyric_body_verbatim` added |

3 lenses returned **no confirmed findings**: navigation (end-of-plan clamp, Previous-into-song-last-stanza, cursor coherence across a scripture, title-only regression) — clean; wire compat (fixtures byte-identical, old-JSON parse both sides, both `From` impls updated) — clean; migration safety (v6 nullable + NULL backfill, insert+update both write content, no unbounded growth) — clean.

## Verification

- **+22 Rust tests** (4 core, 3 data, 2 session, 12 controller incl. the regression, 3 wire) + **2 Dart**; full workspace + `--features server` E2E + Flutter all green; fmt + clippy clean.
- **CI green** (run 30156606042 pre-fix; re-run post-fix) — all 11 jobs across 3 OSes.
- Migration version assertions use `target_version()` dynamically (v7-safe); pinned wire fixtures unchanged.

## Residual / follow-ups (tracked, not this batch)

- Long stanzas still truncate at the 6-line compose cap (pagination is a tracked Stage-8 item). The chosen translation is still not persisted across recovery (pre-existing gap). Verse/chorus REPEAT ordering is deferred (a labelled stanza suffices for S8-1).
