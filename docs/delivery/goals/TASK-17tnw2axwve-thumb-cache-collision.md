# Goal Contract — TASK-17tnw2axwve-thumb-cache-collision

## Identity

- Goal ID: TASK-17tnw2axwve-thumb-cache-collision
- Parent goal ID: NONE (parent epic — Design 2.0 Parity Closure, ClickUp `17tnw2axpt8`; this
  ticket itself was filed as a follow-up out of `17tnw2axptg`'s review, per that ticket's own Goal
  Contract iteration 6)
- Title: Deck-scope `pmThumbCache` and the LIVE-ring match so deck-local slide ids never collide
  across decks
- Role: frontend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2axwve
- Created: 2026-09-24
- Updated: 2026-09-24
- Maximum iterations: 8
- Independent verification required: yes (four-reviewer pipeline: Cody, Sana, Vera, Quinn)

## Objective

Switching the Presentation grid to a different deck (via `pmLibOpen`, `pmLibPresent`, or any
future path) never shows a slide tile's thumbnail or LIVE ring from a *different* deck's slide of
the same local id — fixed in `app.js` alone (no backend/wire-protocol change), with a
mutation-verified headless regression check.

## Baseline

Confirmed by direct code + host-architecture tracing (not assumed), against worktree base
`origin/main` @ `8c2d3d3` (current):

- `pmThumbCache` (`implementation/desktop/crates/selahcue-operator/dist/app.js:9820`) is a
  `Map<slideId, dataURL>` — no deck id in the key. `pmLibOpen`/`pmLibPresent`
  (`app.js:9797-9816`) switch to a different deck's grid without ever clearing it. Only the
  editor-transition handlers (`app.js:9955-9956`) clear it, on a different transition.
- `pmGridSyncLive` (`app.js:9876-9923`) matches tiles against `view().live_authored_id`
  (`selahcue-lan/src/protocol.rs:1063`, a bare slide id with no deck id) alone. `deck_open`
  (`selahcue-operator/src/main.rs:2619-2628`) never touches Live, so this is reachable: deck A's
  slide 1 live → operator opens deck B (same local id 1) via `pmLibOpen` → deck B's tile 1 shows a
  persistent false "LIVE" ring.
- `DeckWorkspace.live` (`selahcue-operator/src/deck_workspace.rs:812`, wire field `dv.live`) is
  already returned on every `DeckView` and is deck-session-scoped (reset to `None` on every real
  deck switch, `deck_workspace.rs:215-222`) but is currently unused by `app.js` — confirmed by
  grep, zero read sites today.

## Inputs and evidence sources

- ClickUp `17tnw2axwve` full description (read via `clickup_get_task`, include: description).
- `implementation/desktop/crates/selahcue-operator/dist/app.js` (`pmThumbCache`, `pmThumb`,
  `pmThumbPut`, `pmRenderGrid`, `pmGridSyncLive`, `pmLibOpen`, `pmLibPresent`, `pmGridGoLive`,
  `pmGridDelta`, `pAct`).
- `implementation/desktop/crates/selahcue-lan/src/protocol.rs` (`OperatorStateView`).
- `implementation/desktop/crates/selahcue-operator/src/main.rs` (`deck_open`, `deck_go_live`,
  `deck_go_live_delta`, `deck_select_slide`, `render_deck_slide`).
- `implementation/desktop/crates/selahcue-operator/src/deck_workspace.rs` (`DeckWorkspace::view`,
  `load_deck`, `go_live`, `go_live_delta`, `fix_cursors`).
- `scripts/operator_headless.py` (mock Tauri `invoke` backend, existing PM/B grid/LIVE-ring check
  block around line 4700-4830, `EXPECTED_MIN_CHECKS` discipline at the file tail).
- `docs/delivery/goals/TASK-17tnw2axptg-presentation-safety-access.md` (sibling ticket from the
  same epic; its Iteration 6 is where this ticket was filed, useful precedent for contract shape
  and reviewer-dispatch mechanics in this repo).

## Scope

### In scope

- `pmThumbCache`/`pmThumb`/`pmThumbPut`/`pmRenderGrid` — deck-scope the cache key.
- `pmGridSyncLive` — gate the LIVE ring match on `dv.live` agreeing with `live_authored_id`.
- `scripts/operator_headless.py` — mock-backend extension (opt-in, additive) + new
  mutation-verified check block reproducing the two-deck/colliding-slide-id-1 scenario via both
  `pmLibOpen` and `pmLibPresent`.
- `EXPECTED_MIN_CHECKS` bump to the measured post-change count.

### Non-goals

- Any change to `selahcue-lan`'s wire protocol (`OperatorStateView`/`live_authored_id`) or any
  other Rust source file. The fix is provably closeable in `app.js` alone (see Baseline); a wire
  change would need cross-language contract-fixture updates and is out of a frontend ticket's
  scope.
- Fixing `render_deck_slide`'s own deck-blind race (a backend command signature issue, not the
  deterministic cache-collision this ticket targets) — flagged as a follow-up, not fixed here.
- Fully closing the "operator process restart mid-service" cold-boot ring gap (needs a
  `live_authored_deck_id`-shaped wire addition) — flagged as a linked follow-up ClickUp ticket,
  not fixed here; the chosen fix fails closed (no ring shown) rather than fails open (wrong ring
  shown) in that narrow case, which is the safer default per this codebase's own documented
  never-surprise stance.

### Constraints

- One `make ci` at a time in this shared checkout; check `list_sessions`/worktree activity first.
- Never work on `main`/`dev`; own worktree (`scph-worktrees/17tnw2axwve-thumb-cache-collision`),
  own branch (`fix/17tnw2axwve-thumb-cache-collision`), one ticket per branch/PR.
- Never hand-sum `EXPECTED_MIN_CHECKS` — set it only from a real measured run.
- `binaries/` placeholders (`make stage-operator-binaries`) needed before any Rust gate compiles
  in this fresh worktree — confirm wired into `make ci` rather than assuming.

### Assumptions and unknowns

- ASSUMED: only this operator console instance drives `deck_go_live`/`deck_go_live_delta` for a
  given host in normal operation (no LAN-remote deck-authoring client exists — confirmed via
  `docs` memory: "decks live only in selahcue-operator; host has no deck store"), which is what
  makes `dv.live` a reliable, non-racy local corroboration signal for the ring fix. Validation
  owner: this session, via the RBAC/`PresentAuthoredSlide` trace in the Baseline section; flagged
  to reviewers (especially Sana/Quinn) to independently challenge.
- ASSUMED: the mock backend extension can be made fully opt-in (no behaviour change unless a
  `LIB.decks` entry carries the new `.content` field) — validated by running the full existing
  suite unchanged before touching any of the ~1892 pre-existing checks' assertions, and again
  after, diffing pass counts precisely.

## Dependencies and approvals

- Four-reviewer pipeline (Cody/Sana/Vera/Quinn) — required before `VERIFIED_COMPLETE`, dispatched
  after the PR opens, each in its own worktree pinned to the same head SHA.
- No product/architecture decision required — this is a confirmed functional bug fix with a
  fully in-scope frontend fix (see Baseline).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `pmThumbCache` is keyed by `(deckId, slideId)` everywhere it is read or written; two decks sharing a local slide id never share a cache entry, including via paths that never call `pmRenderGrid` directly (deck-create/duplicate/delete-fallback) | `python3 scripts/operator_headless.py`, mutation-verified, independently re-confirmed by round-2 review | new assertions pass; mutation turns exactly the targeted assertion(s) RED | Round 1 (`7118567`) missed the deck-create/duplicate/delete-fallback paths — Sana, corroborated live by Cody and Vera. Fixed in round 2 (Done handler now asks `deck_list` for ground truth). `/tmp/headless_final_postrebase.txt` (1916 checks, 0 FAIL); `/tmp/mutation_cache.txt` + `/tmp/mutation_finding2.txt` (each turns exactly its targeted assertion RED). Self-verification complete; round-2 independent review pending (tracked under C-009) | PENDING |
| C-002 | yes | The grid's LIVE ring never highlights a tile from a deck that is not actually the one live, even when the local slide id collides with the actually-live deck's, AND does not regress the ordinary same-session case (A→B→A revisit; a deck slide presented from the Service Plan / Live Console surface; an editor-mode Present via topbar or command palette) | `python3 scripts/operator_headless.py`, mutation-verified, independently re-confirmed by round-3 review | new assertions pass; mutation turns exactly the targeted assertion(s) RED | Round 1's `dv.live`-based gate (`7118567`) broke the ring on ordinary same-session use — Sana, corroborated live by Quinn. Redesigned around client-tracked `pmLiveAuthoredDeckId` in round 2. Round 2 review then found a FIFTH JS entry point (`pmPresent()`, editor topbar/palette) the redesign itself missed — fixed round 3 with the `deck_list` ground-truth pattern (not the risky `pmGridDeckId`, mutation-verified against that specific wrong-fix too). `/tmp/headless_r3_final.txt` (1918 checks, 0 FAIL); `/tmp/mutation_ring.txt`, `/tmp/mutation_finding1.txt`, `/tmp/mutation_findingA2.txt`, `/tmp/mutation_findingA3.txt` (each turns exactly its targeted assertion(s) RED, nothing else). Self-verification complete; round-3 independent review from Sana pending (tracked under C-009) | PENDING |
| C-003 | yes | The ring-gate fix does not regress the ordinary single-deck case (go-live, transport arrows `deck_go_live_delta`) | `python3 scripts/operator_headless.py` (existing PM/B/PM/B2/PM/B3 block, unmodified assertions) | all pre-existing PM/B* assertions still pass unchanged | `/tmp/headless_final_postrebase.txt` — all pre-existing PM/B*/PME-* assertions PASS, unchanged | PASS |
| C-004 | yes | Revisiting a previously-viewed deck still hits the thumbnail cache (option (b) is not defeated by the fix — no unnecessary re-fetch) | new headless assertion: reopen a deck already visited this session, assert no new `render_deck_slide` call for an already-rendered tile | assertion passes | `/tmp/headless_final_postrebase.txt` — "switching back to Deck X (pmLibPresent) hits the thumbnail cache" PASS | PASS |
| C-005 | yes | `pmThumbCache` stays bounded at `PM_THUMB_MAX` entries total regardless of how many distinct decks are visited (not per-deck) | Vera's independent review + a per-key bounded-memory check per this repo's own bar (not a global counter), mutation-verified, independently re-confirmed by round-2 review | cache size never exceeds `PM_THUMB_MAX`; Vera confirms in her review | Round 1: no such test existed — Vera (blocking). She wrote and mutation-verified `window.__pmGridDebug` + a 5-assertion check (70 distinct (deck,slide) pairs vs cap 60), applied verbatim in round 2. `/tmp/headless_final_postrebase.txt`. Round-2 confirmation from Vera pending (tracked under C-009) | PENDING |
| C-006 | yes | `EXPECTED_MIN_CHECKS` reflects a real measured run, never hand-summed | `python3 scripts/operator_headless.py` final run | constant equals the printed count exactly | `scripts/operator_headless.py` — bumped to 1916 (post-rebase onto `main`'s PR #93, which independently bumped it too; combined total re-measured for real, not assumed by arithmetic), matching two independent clean runs (`/tmp/headless_postrebase2.txt`, `/tmp/headless_postrebase3.txt`) before the constant was edited, then a third confirming run after (`/tmp/headless_final_postrebase.txt`) | PASS |
| C-007 | yes | Full headless suite green (no regression to any pre-existing check) | `python3 scripts/operator_headless.py` | 0 FAIL | `/tmp/headless_final_postrebase.txt` — exit 0, 1916 checks, 0 FAIL | PASS |
| C-008 | yes | `make ci` green on the branch | `make ci` (one at a time; check for concurrent sessions first) + real GitHub Actions CI | ALL GREEN | Local `make ci` against `b3ebfd6`: `== local Rust/Flutter gate: ALL GREEN ==` (`/tmp/make_ci_run2.log`). Real CI (`gh pr checks 92` against confirmed current head `df539ee`): every applicable job `pass` across the full ubuntu/macOS/Windows matrix (`rust`, `operator shell`, `operator shell — release & native-toolchain features`, `launch-smoke`, dependency audit, supply chain, workflow lint); `api`/`flutter controller`/`marketing` correctly path-filter-skipped (no changes in those areas) | PASS |
| C-009 | yes | Four-reviewer pipeline run, blocking findings remediated and re-verified | reviewer reports, each own worktree pinned to head SHA; consolidated report published as a shareable Artifact | all four clear; report linked on PR + ClickUp | Round 1 (`7118567`): Sana 2 blocking, Cody 1 blocking, Vera 2 blocking, Quinn 1 blocking — all real, all remediated (see Iteration 3). Round 2 against `df539ee`: **Cody — Pass, no blocking findings**. **Sana — 2 more blocking** (a 5th present entry point + a comment-accuracy issue), remediated in Iteration 5 (head `4838c1b`), Sana re-dispatched for round 3. Vera/Quinn round-2 verdicts still pending against `df539ee` | PENDING |
| C-010 | yes | PR opened against `main`, Draft initially, citing the ticket with a before/after repro; not self-merged | `gh pr view` | PR exists, Draft→Ready only once C-009 clears, base=`main`, body cites `17tnw2axwve` | PR #92: https://github.com/First-Pavilion/selahcue/pull/92 (Draft, base=main, head=`fix/17tnw2axwve-thumb-cache-collision`). Opening criterion satisfied; the Draft→Ready flip is a separate, later action gated on C-009 | PASS |
| C-011 | no | Follow-up ClickUp ticket(s) filed for the two accepted residual limitations (cold-boot ring gap; `render_deck_slide` deck-blind race) | `clickup_create_task` / task URL | tickets exist, linked from this one and from the PR | https://app.clickup.com/t/17tnw2ayevf (cold-boot ring gap), https://app.clickup.com/t/17tnw2ayevg (render_deck_slide race) — both subtasks of `17tnw2axwve`, linked on PR #92 | PASS |

## Verification plan

- Focused verification: `python3 scripts/operator_headless.py` after each change; targeted
  `Read`/`grep` against `app.js` for exact line-level correctness.
- Broader regression verification: full `scripts/operator_headless.py` run before and after the
  batch (pass-count diff must be explainable entirely by intentionally added assertions); full
  `make ci` before marking the PR ready.
- Independent verifier: four-reviewer pipeline (Cody, Sana, Vera, Quinn), each in its own
  worktree pinned to the same head SHA.
- Required environment: this worktree, macOS, Rust toolchain per `rust-toolchain.toml`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-003, C-004, C-006, C-007.
- Hypothesis: both bugs close in `app.js` alone — thumbnail cache via a deck-id-qualified key
  threaded explicitly through render calls (not a mutable "current deck" global, to avoid a
  lazy-thumbnail race), LIVE ring via gating `live_authored_id` on agreement with the
  already-shipped-but-unused `dv.live` field.
- Change or investigation: implemented `pmThumbKey`/`pmThumbPut(deckId, id, url)`/
  `pmThumb(deckId, id, cv)`/`pmRenderGrid(dv, deckId)` and the `pmGridSyncLive` ring-gate; updated
  all call sites (`pmLibOpen`, `pmLibPresent`, the editor→grid "Done" handler). Extended
  `scripts/operator_headless.py`'s mock backend opt-in (`deck_open`'s content-swap only fires for
  a `LIB.decks` entry carrying its own `.content`; `render_deck_slide`'s mock output now varies by
  `(LIB.open, args.id)`, both pixels in the 2×1 frame identical to eliminate any scaling/
  interpolation ambiguity when a cache-hit redraw scales it into a differently-sized canvas) and
  added a 9-assertion check block (two synthetic decks, ids `70001`/`70002`, each with local slide
  id `1`) covering: fresh-open thumbnail render, cross-deck thumbnail non-collision via
  `pmLibOpen`, cross-deck-switch-back cache-hit + correctness via `pmLibPresent`, the LIVE-ring
  non-collision, and a positive control that the ring still works for the deck it belongs to. The
  block snapshots and fully restores `D`/`window.__LIB`/`V.live_authored_id` around itself.
- Verifier executed: `python3 scripts/operator_headless.py`, run three times independently at the
  final state, plus two independent mutation runs (one per fix).
- Result: **1901 checks, 0 FAIL** (up from 1892; +9 new assertions, `EXPECTED_MIN_CHECKS` bumped
  to the measured value, itself confirmed by two independent pre-bump runs both reporting 1901).
  Mutation A (thumbnail key reverted to bare-id): exactly 1 FAIL — the cross-deck thumbnail
  assertion, with both decks' tile 1 reporting the identical colour, directly showing the leak.
  Mutation B (ring gate disabled): exactly 1 FAIL — the ring-collision assertion; the positive
  control in the same block still PASSED, proving the mutation disabled only the gate, not the
  ring mechanism itself. Both mutations restored; final re-run clean (exit 0, 1901/1901).
- New evidence: `/tmp/headless_run2.txt`, `/tmp/headless_run3.txt` (pre-bump, both 1901/1901 with
  only the expected-count guard failing), `/tmp/headless_final_clean.txt` (post-bump, exit 0),
  `/tmp/mutation_cache.txt`, `/tmp/mutation_ring.txt`.
- Decision: complete for C-001–C-004, C-006, C-007; iterate on C-005 (Vera's dedicated review),
  C-008 (`make ci`), C-009 (four-reviewer pipeline), C-010 (PR), C-011 (follow-up tickets).

### Iteration 2 — four-reviewer pipeline round 1

- Target criterion: C-005, C-009.
- Change or investigation: dispatched Cody/Sana/Vera/Quinn in parallel, each its own worktree
  pinned to head `7118567`.
- Result: **Sana — 2 blocking.** (1) The `dv.live`-based LIVE-ring gate suppressed the ring on the
  routine same-session A→B→A deck revisit, not just a rare cold-boot edge case as the original
  design assumed — `load_deck` resets `dv.live` on every real deck switch including switching
  back; also never set at all by a deck slide presented via the separate Service Plan / Live
  Console path (`present_plan_deck_slide`). Proven live (isolated A/B probe against `origin/main`
  vs the PR head). (2) `pmGridDeckId` staleness at the "+ New presentation"/duplicate/delete-
  fallback paths (never call `pmRenderGrid`) resurrects the exact thumbnail collision this ticket
  targets. **Cody — 1 blocking**, independently corroborating Sana's finding 2, reproduced live
  via the Duplicate path. **Vera — 2 blocking**: independently corroborated finding 2 via the
  Blank-deck path (the harder case — no id in the `deck_new` response at all); and found no
  bounded-memory test existed for `pmThumbCache`'s widened key space (root `CLAUDE.md` requires
  one for changed buffering code) — she wrote and mutation-verified one in her own worktree.
  **Quinn — 1 blocking**, independently corroborating Sana's finding 1 via her own isolated A/B
  probe, confirming it as a genuine regression from ordinary same-session use, not the narrower
  scope the PR description claimed.
- Decision: iterate — all four findings are real; remediate before any further review.

### Iteration 3 — remediation of round-1 findings

- Target criterion: C-001 (re-verify), C-002, C-005.
- Hypothesis: Finding 1 needs a signal that (a) survives a deck switch away-and-back and (b) is
  updated by every path that can set `live_authored_id`, not just the grid's own. No such signal
  exists host-side (confirmed: `AuthoredSlide`/`Presenter` are deck-blind by architecture) — the
  correct fix is a client-tracked variable (`pmLiveAuthoredDeckId`), set only on client-OBSERVED
  successful presents (grid go-live/delta, and both `present_plan_deck_slide` call sites), cleared
  when host truth says nothing authored is live. Finding 2 needs the "Done" handler to stop
  trusting a variable only `pmRenderGrid` ever wrote, and instead ask `deck_list` (whose `open`
  field is always fresh, computed live host-side) — a single fix at the point of consumption
  rather than patching every upstream path that can silently change the open deck.
- Change or investigation: implemented both redesigns in `app.js`; applied Vera's bounded-memory
  patch verbatim; added 10 new headless assertions (A→B→A revisit, cross-surface present, deck-
  create staleness, plus premises) on top of Vera's 5. Rebased onto `main` (picked up an unrelated
  Theme Designer fix from PR #93, which also bumped `EXPECTED_MIN_CHECKS` — resolved by keeping
  both chains' comments and re-measuring the combined total for real rather than by arithmetic,
  per this repo's own documented convention for exactly this conflict shape).
- Verifier executed: `python3 scripts/operator_headless.py`, run four times independently across
  the remediation + rebase; two dedicated mutation runs (Finding 1: reverted to the old `dv.live`
  gate — exactly the two new Finding-1 assertions went RED, nothing else; Finding 2: reverted the
  `deck_list` lookup — exactly the one new Finding-2 assertion went RED, nothing else).
- Result: **1916 checks, 0 FAIL**, stable across all runs. Head SHA `b3ebfd6`.
- New evidence: `/tmp/headless_remediation1.txt`, `/tmp/headless_remediation2.txt`,
  `/tmp/mutation_finding1.txt` (2 FAIL, exactly the A→B→A and cross-surface assertions),
  `/tmp/mutation_finding2.txt` (1 FAIL, exactly the deck-create staleness assertion),
  `/tmp/headless_postrebase2.txt`, `/tmp/headless_postrebase3.txt`, `/tmp/headless_final_postrebase.txt`.
- Decision: iterate — re-dispatch all four reviewers against `b3ebfd6` (round 2) before claiming
  C-009 PASS; `make ci` re-launched fresh against this commit (the round-1 background run was
  discarded — started before this remediation landed, would have been evidence about an
  inconsistent tree, per this repo's own established practice for exactly this situation).

### Iteration 5 — four-reviewer pipeline round 2, and round-3 remediation

- Target criterion: C-009.
- Change or investigation: dispatched all four reviewers fresh against `df539ee` (docs-only commit
  on top of `b3ebfd6`), each a NEW worktree, explicitly asked not to rubber-stamp since the ring
  mechanism changed materially.
- Result: **Cody — Pass, no blocking findings** (independently re-verified both round-1 fixes with
  his own mutation tests and his own repro of his original finding; traced the Rust side
  independently to confirm the redesign's premises; confirmed real GitHub Actions CI green across
  the full matrix). **Sana — 2 more blocking.** Finding A: a FIFTH JS entry point to an
  authored-slide present — `pmPresent()` (editor-mode "▶ Present", reached from both the topbar via
  `pmPresentFromTopbar` and the ⌘K command palette's editor-mode "Present slide") — did not record
  `pmLiveAuthoredDeckId` at all, reproducing round-1 Finding 1's exact failure mode via a path round
  1 never covered. Sana proved this live and additionally proved the "obvious" fix
  (`pmLiveAuthoredDeckId = pmGridDeckId`) is actively WRONG here, since `pmGridDeckId` can itself be
  stale in the editor (e.g. right after "+ New presentation") — she verified this via Vera's
  `window.__pmGridDebug.deckId()` hook. Finding B (docs-only): the residual-limitation comment
  overclaimed scope on two points — framing the gap as "another operator console" when the real
  RBAC surface (`selahcue-lan/src/rbac.rs`) is any GoLive-privileged peer (Operator OR Producer
  role), and claiming "both fail CLOSED" when she proved a real fail-OPEN sub-case (a foreign peer
  presenting a different deck while this client stays parked on the deck it last drove live).
- Change or investigation: fixed Finding A with the same `deck_list` ground-truth pattern the
  "Done" handler uses (confirmed, not `pmGridDeckId`); corrected Finding B's comment in place (no
  code change — pre-existing behaviour on `main` too, not a new regression) and updated the linked
  follow-up ticket (ClickUp `17tnw2ayevf`) to match the corrected, broader residual scope. Added 2
  new headless assertions. Reverted an incidental `pubspec.lock` change from `make ci`'s Flutter
  gate before committing (unrelated to this ticket, per this repo's own established convention for
  exactly this situation).
- Verifier executed: `python3 scripts/operator_headless.py`, run four times independently; two
  dedicated mutation runs for Finding A (reverting to "record nothing", and separately reverting to
  the specific risky wrong-fix `pmGridDeckId` — both turn exactly the new assertion RED, nothing
  else).
- Result: **1918 checks, 0 FAIL**, stable across all runs. Head SHA `4838c1b`.
- New evidence: `/tmp/headless_findingA.txt`, `/tmp/headless_findingA2.txt`,
  `/tmp/mutation_findingA.txt` (1 FAIL as expected, but traced to a test-sequencing bug — an
  earlier "Done" click in the same block had already exited editor mode, so the mutation was
  silently exercising the already-fixed grid path instead; test restructured to keep the Present
  click genuinely inside the editor before any Done click), `/tmp/mutation_findingA2.txt` (1 FAIL,
  correct target this time), `/tmp/mutation_findingA3.txt` (the `pmGridDeckId` wrong-fix, 1 FAIL,
  same target), `/tmp/headless_r3_clean1.txt`, `/tmp/headless_r3_clean2.txt`, `/tmp/headless_r3_final.txt`.
  Cody's round-2 PR comment: https://github.com/First-Pavilion/selahcue/pull/92#issuecomment-5809754897.
  Sana's round-2 PR comment: https://github.com/First-Pavilion/selahcue/pull/92#issuecomment-5810626748.
  Remediation PR comment: https://github.com/First-Pavilion/selahcue/pull/92#issuecomment-5810772384.
- Decision: iterate — `make ci` re-launched fresh against `4838c1b`; Sana re-dispatched (resumed
  her round-2 agent) for a round-3 check of both new fixes; Vera and Quinn's round-2 verdicts still
  pending against `df539ee` (their findings, once in, need re-verification against `4838c1b` too if
  they touch overlapping code).

### Iteration 4 — `make ci` + four-reviewer pipeline round 2

- Target criterion: C-008, C-009.
- Change or investigation: re-launched `make ci` fresh against `b3ebfd6` after discarding the
  stale round-1 background run; dispatched all four reviewers for a genuine round-2 pass (not a
  rubber-stamp) against `df539ee`, each a fresh worktree.
- Result (in progress): `make ci` — `ALL GREEN`. Real GitHub Actions CI independently confirmed
  green across the full matrix (`gh pr checks 92`, cross-checked the head SHA matched). Cody round
  2 — **Pass, no blocking findings**, with independent mutation verification of both fixes, an
  independent Rust-side trace confirming the redesign's premises, and independent confirmation of
  real CI. Sana/Vera/Quinn round 2 still running.
- New evidence: `/tmp/make_ci_run2.log`; `gh pr checks 92` output (this ledger); Cody's PR comment
  https://github.com/First-Pavilion/selahcue/pull/92#issuecomment-5809754897.
- Decision: iterate — awaiting Sana/Vera/Quinn round 2 before C-009 can PASS.

## Risks and rollback

- Risk: the ring-gate fix fails closed in the cold-boot/process-restart case (never fails open) —
  accepted and documented as a Non-goal with a linked follow-up ticket, not silently dropped.
- Risk: extending `scripts/operator_headless.py`'s shared mock state (`D`/`LIB`) could leak into
  later, unrelated checks — mitigated by snapshotting and restoring both before/after the new
  check block, and by running the full suite (not just the new block) to catch any leakage as a
  newly-failing later assertion.
- Rollback: revert the branch; no data migration, no destructive change, nothing merged to `main`
  until the user's own merge action.

## Pause and escalation conditions

- None anticipated — this is a confirmed, fully in-scope frontend fix. Escalate if the headless
  mock extension proves impossible to make truly additive without behavioural drift in existing
  checks (would require stopping to re-scope the test-harness change itself).

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2axwve-thumb-cache-collision.md --completion`
- Validator result: (pending — run before claiming VERIFIED_COMPLETE)
- Independent verification result: (pending)
- Terminal state: (pending)
- Remaining failed or blocked criteria: (pending)
- ClickUp final evidence comment: (pending)
