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
| C-001 | yes | `pmThumbCache` is keyed by `(deckId, slideId)` everywhere it is read or written; two decks sharing a local slide id never share a cache entry | `python3 scripts/operator_headless.py`, mutation-verified (revert the key fix, confirm the new thumbnail-collision assertion goes RED, restore) | new assertions pass; mutation turns exactly that assertion RED | `/tmp/headless_final_clean.txt` (1901 checks, 0 FAIL); `/tmp/mutation_cache.txt` (1 FAIL, exactly the collision assertion, X=Y colour proving the leak) | PASS |
| C-002 | yes | The grid's LIVE ring never highlights a tile from a deck that is not actually the one live, even when the local slide id collides with the actually-live deck's | `python3 scripts/operator_headless.py`, mutation-verified (revert the ring gate, confirm the new ring-collision assertion goes RED, restore) | new assertion passes; mutation turns it RED | `/tmp/headless_final_clean.txt`; `/tmp/mutation_ring.txt` (1 FAIL, exactly the ring-collision assertion; the positive control still passed, proving the ring mechanism itself was untouched) | PASS |
| C-003 | yes | The ring-gate fix does not regress the ordinary single-deck case (go-live, transport arrows `deck_go_live_delta`) | `python3 scripts/operator_headless.py` (existing PM/B/PM/B2/PM/B3 block, unmodified assertions) | all pre-existing PM/B* assertions still pass unchanged | `/tmp/headless_final_clean.txt` — all pre-existing PM/B*/PME-* assertions PASS, unchanged | PASS |
| C-004 | yes | Revisiting a previously-viewed deck still hits the thumbnail cache (option (b) is not defeated by the fix — no unnecessary re-fetch) | new headless assertion: reopen a deck already visited this session, assert no new `render_deck_slide` call for an already-rendered tile | assertion passes | `/tmp/headless_final_clean.txt` — "switching back to Deck X (pmLibPresent) hits the thumbnail cache" PASS | PASS |
| C-005 | yes | `pmThumbCache` stays bounded at `PM_THUMB_MAX` entries total regardless of how many distinct decks are visited (not per-deck) | Vera's independent review + a per-key bounded-memory check per this repo's own bar (not a global counter) | cache size never exceeds `PM_THUMB_MAX`; Vera confirms in her review | Vera's review comment / consolidated report | PENDING |
| C-006 | yes | `EXPECTED_MIN_CHECKS` reflects a real measured run, never hand-summed | `python3 scripts/operator_headless.py` final run | constant equals the printed count exactly | `scripts/operator_headless.py` — bumped to 1901, matching two independent clean runs (`/tmp/headless_run2.txt`, `/tmp/headless_run3.txt`) before the constant was edited, then a third confirming run after (`/tmp/headless_final_clean.txt`) | PASS |
| C-007 | yes | Full headless suite green (no regression to any pre-existing check) | `python3 scripts/operator_headless.py` | 0 FAIL | `/tmp/headless_final_clean.txt` — exit 0, 1901 checks, 0 FAIL | PASS |
| C-008 | yes | `make ci` green on the branch | `make ci` (one at a time; check for concurrent sessions first) | ALL GREEN | terminal output (this ledger) | PENDING |
| C-009 | yes | Four-reviewer pipeline run, blocking findings remediated and re-verified | reviewer reports, each own worktree pinned to head SHA; consolidated report published as a shareable Artifact | all four clear; report linked on PR + ClickUp | PR comments + Artifact URL | PENDING |
| C-010 | yes | PR opened against `main`, Draft initially, citing the ticket with a before/after repro; not self-merged | `gh pr view` | PR exists, Draft→Ready only once C-009 clears, base=`main`, body cites `17tnw2axwve` | PR URL/number | PENDING |
| C-011 | no | Follow-up ClickUp ticket(s) filed for the two accepted residual limitations (cold-boot ring gap; `render_deck_slide` deck-blind race) | `clickup_create_task` / task URL | tickets exist, linked from this one and from the PR | ClickUp URLs | PENDING |

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
