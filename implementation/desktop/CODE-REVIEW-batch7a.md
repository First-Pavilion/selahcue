# Code Review — batch7a: `selahcue-core` domain crate

**Reviewer:** Independent Rust reviewer (did **not** author this code)
**Scope:** `crates/selahcue-core/src/{scripture,plan,timer,lib}.rs`
**Date:** 2026-07-23
**Baseline:** `cargo test -p selahcue-core` → 33 passed / 0 failed. `cargo clippy -p selahcue-core --all-targets` → clean. `#![forbid(unsafe_code)]` in effect.

## Verdict: PASS WITH CONDITIONS

The FR-027 parser is genuinely **panic-free on arbitrary string input** (verified by fuzzing ~70 hostile inputs), all FR-027 acceptance cases pass, and the Timer/ServicePlan domain logic is correct. Two real defects and some minor gaps should be addressed, none of which is reachable from untrusted string input.

---

## Findings by severity

### MEDIUM

**M1 — `Reference::verse_count()` panics on overflow (scripture.rs:30–35).**
`match self.verses { Some(r) => r.end - r.start + 1, ... }` uses unchecked `u16` arithmetic. `Reference` and `VerseRange` have **all-`pub` fields**, so the public API lets a caller build `Reference { verses: Some(VerseRange { start: 5, end: 2 }), .. }`. Calling `verse_count()` then does `2 - 5` →

```
thread panicked at crates/selahcue-core/src/scripture.rs:32:24:
attempt to subtract with overflow
```

(Confirmed by direct test.) `start: 0, end: 65535` similarly overflows on the `+ 1`. In release builds this does not panic but silently wraps to a garbage count, which could drive wrong UI/verse logic.

The parser itself always emits `end >= start` and `start >= 1`, so this is **not** reachable from `parse()`/`parse_one()` — string input is safe. But the module doc claims the code "never panics," and this public method contradicts that for hand-built values the public API openly permits.
*Fix:* use saturating arithmetic — `r.end.saturating_sub(r.start).saturating_add(1)` — and/or make the fields private behind a validated constructor.

### LOW

**L1 — Roman-numeral + full-word form for Samuel is unrecognised (scripture.rs:204–205).**
Every other numbered book accepts "roman numeral + full name":

```
"I Kings 1:1"       -> Ok(11)
"I Corinthians 13:4"-> Ok(46)
"I John 1:9"        -> Ok(62)
"I Samuel 1:1"      -> Err(UnknownBook)   <-- inconsistent
"II Samuel 1:1"     -> Err(UnknownBook)   <-- inconsistent
```

Books 9/10 carry only `"isam"`/`"iisam"` (roman + *abbrev*), not `"isamuel"`/`"iisamuel"` (roman + *full word*), unlike `"ikings"`, `"icorinthians"`, `"ijohn"`, etc. Behaviour is safe (returns `UnknownBook`, no panic), but the coverage is inconsistent. `"1 Samuel"`, `"First Samuel"`, and `"I Sam"` all work. *Fix:* add `"isamuel"`/`"firstsamuel"(present)` and `"iisamuel"` aliases. The tests miss this — `roman_and_word_numbered_books` only exercises I John / First John / III John.

**L2 — Other unchecked arithmetic in runtime paths (defence-in-depth).**
- `plan::planned_total_secs` (plan.rs:145–147) uses `.sum()` over `u32`; `PlanItem::planned_secs` is a `pub` field, so two large values panic on overflow in debug. Prefer `fold(0u32, |a,b| a.saturating_add(b))`.
- `timer` uses `Duration + Duration` / `+=` (timer.rs:70, 84). Overflow only at astronomically large accumulated values, so not realistically reachable, but not defended. Note the `saturating_duration_since` guard already correctly handles a `now` earlier than the start, and `add_time`/`subtract_time` already use `saturating_add`/`saturating_sub` — good.

**L3 — Test-coverage gaps (tests are otherwise strong).**
Missing: `pause` idempotency (pause while already paused); `add_time`/`subtract_time` no-op on `CountUp`; `elapsed` with `now < start` (the saturating branch); `reorder` `from == to` early-return; `insert_item` clamp when `index > len`; and the two defects above (M1 verse_count overflow, L1 "I Samuel"). Existing happy/edge/malformed coverage is genuine, not superficial.

---

## Assessment against the brief

**1. Correctness (parser).** All FR-027 acceptance cases pass: `Romans 8:28`, `Rom 8:28-30`, `Ps 23`, `1 Cor 13:4`, `Jn 3:16`, and `"John 3:16; 1 Cor 13:4"` (2 refs). Malformed input is rejected without panic. Attempts to break it — `""`, `"   "`, `";;;"`, `"1 2 3"` (→ UnknownBook), `"Romans 8:28:30"` (→ BadNumbers), `"Romans 8:28-30-40"`, `"Romans 99999:1"` / `"Romans 8:99999999999"` (u16 parse rejects overflow → BadNumbers, no panic), `"Romans 8:0"`, `"Romans 8:30-10"` (descending → BadNumbers), fullwidth digits `"Romans ８:28"`, unicode/NUL/emoji book names (`normalize` drops non-ASCII-alphanumerics → UnknownBook), and weird/tab/newline whitespace — **all return `Result`, none panic** (fuzzed via a throwaway integration test, since removed). The one true parse gap is L1 ("I Samuel").

**2. Safety.** Runtime code from string input is panic-free: no `unwrap`/`expect`/indexing beyond the guarded `tokens[len-1]` slice (guarded by `tokens.len() < 2`), `unsafe` forbidden. The only reachable panic is **M1**, via hand-built `Reference` values (public pub-field API), not via the parser.

**3. Domain logic.** ServicePlan: ids are monotonic and never reused after removal (`next_id` only increments); `reorder` bounds-checks both indices; `insert_item` clamps; `duplicate` deep-clones and keeps an independent `next_id` — all correct. Timer: pause/resume banks the running segment into `accumulated`; elapsed is derived from the injected `Instant` so it is query-frequency-independent (NFR-022); `is_time_up` uses `>=` at expiry with `remaining == ZERO`; overrun and saturating add/subtract are correct.

**4. Test quality.** 33 tests covering happy, edge, and malformed paths, including `all_66_books_resolve_by_canonical_name` and lenient-vs-strict multi-ref behaviour. Solid, not superficial; the gaps in L3 (and the two defects) are the notable omissions.

---

## Independence statement

I did not author, co-author, or previously modify any code in `selahcue-core`. This review is based solely on reading the four source files and on evidence from `cargo test`, `cargo clippy`, and a temporary fuzz/edge integration test that I wrote to probe for panics and then deleted (the crate's source tree is unchanged). Findings M1 and L1 are reproduced defects, not speculation.
