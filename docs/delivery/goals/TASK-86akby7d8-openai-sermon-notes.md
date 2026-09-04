# Goal Contract — TASK-86akby7d8

## Identity

- Goal ID: TASK-86akby7d8
- Parent goal ID: NONE
- Title: Pressing Generate on a completed transcript produces a real, structured sermon-note draft from OpenAI GPT, and the Providers & Privacy panel reports that state honestly
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby7d8
- Created: 2026-09-04
- Updated: 2026-09-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

With the `openai` / `openai-notes` features enabled, cloud-notes consent granted and a
developer key present, Generate returns a real GPT-produced draft carrying the full FR-122
structure (including points with genuine sub-points), labelled AI-generated and accompanied
by the fabrication-risk disclosure — and the Providers & Privacy panel reports the true
provider state in all four of its configurations, without fabricating a quota and without
weakening the egress gate.

## Baseline

Verified against `origin/main` at `cb006fc6ce12df1f03341203c3894da2c6c57429` on 2026-09-04:

- `selahcue-cloud` speaks a defined contract to a SelahCue hosted service that **does not
  exist**. `generate_sermon_notes` already does consent gating and FR-135 fallback.
- `LocalNoteProvider` is a deterministic text scaffold, explicitly not an LLM.
- `NoteSection.items` is a flat `Vec<String>` and cannot express points with sub-points.
- `providers_view_of` (`selahcue-operator/src/main.rs:2736`) derived
  `cloud_connected = cloud_base_url().is_some() && account_token_set` — both properties of the
  hosted service. Left alone, working GPT generation would render behind a "coming soon"
  affordance: **the screen denying a feature while producing its output.**
- `quota` was hardcoded `None` (`main.rs:2762`). Correct, and must stay.

## Inputs and evidence sources

- ClickUp 86akby7d8, read fresh including all three amending comments (branch-base correction
  to `origin/main`; the mandatory `cloud_status` scope amendment; the link correction).
- `docs/research/PROVIDER-TRADEOFFS.md` §2 (superseded for note generation by owner decision).
- OpenAI live API, 2026-09-04: `GET /v1/models` (HTTP 200, 118 models) and four captured error
  responses (401/404/400/429).
- `developers.openai.com` Responses API reference for the `text.format` / `max_output_tokens`
  request shape.

## Scope

### In scope

- A GPT-backed `CloudNoteProvider` behind a new off-by-default `openai` feature.
- Extending the core note types so sub-points are structurally subordinate.
- The `cloud_status` / `notes_available` / `notes_provider` view redefinition, plus its
  frontend half in `dist/settings.js` — **same MR, non-negotiable**.
- Naming OpenAI on the panel (FR-132).
- Bounded request and response handling.

### Non-goals

- FR-125 scripture-reference verification (86akby820).
- The retention / DPA disclosure (86akby942). Naming a provider is safe without the DPA work;
  describing its retention posture is not.
- FR-124 timestamps, FR-126/127 export artefacts.
- Anything to do with Deepgram or transcription (lane A).
- A model-choice **setting**; see C-014.

### Constraints

- The egress choke point `ProvidersConfig::build_note_request` is not weakened and gains no
  second path around it.
- `quota` stays `None`. No metering exists, so no number may be invented.
- The default build must compile and behave exactly as before.
- Tests never touch live OpenAI.
- `selahcue-operator/src/main.rs` is shared with lane A: the diff stays inside the
  providers/note-generation region.

### Assumptions and unknowns

- **RESOLVED 2026-09-04:** the owner added credits and the live path was exercised end to end
  through the shipped Rust code (not a Python stand-in). See iteration 7.
- **VERIFIED, narrowly:** `gpt-5.6-terra` produces better FR-122 structure than `gpt-5.6-luna` —
  measured, no longer assumed. But measured on **one transcript, one run each**. That is enough
  to confirm a default and not enough to call the prompt good in general; see the known
  non-determinism in iteration 7.
- **UNKNOWN (new, from the live run):** section population is **not deterministic**. The first
  terra run returned an empty `chapter_markers` despite the toggle being on, and the section was
  dropped; the second run populated it. An enabled section can therefore silently vanish. Not a
  correctness bug — an empty section is correctly not rendered — but it means "the toggles ask
  for it" and "the draft contains it" are not the same statement, and only the first is under
  our control.

## Dependencies and approvals

- 86akby6yy (`.env` loader) — PR #18, Draft. Not merged, so this branch is cut from
  `origin/main` and consumes only the string literal `"OPENAI_API_KEY"`. Coupling is one
  variable name, deliberately, because that ticket is under security review.
- The `cloud_status` representation was agreed with the coordinator before implementation and
  handed to lane A (86akby7th), which consumes it.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | With consent OFF, Generate performs no network call and returns `ConsentRequired`, proven by a transport that fails the test if contacted | `cargo test -p selahcue-cloud --features openai` | `with_consent_off_generate_makes_no_network_call_and_says_consent_is_required` passes; `ForbiddenTransport` panics on contact | test output | PASS |
| C-002 | yes | `build_note_request` remains the only producer of a request, and the body carries the transcript with no audio field | same | `build_note_request_is_the_only_way_to_reach_the_provider` passes | test output | PASS |
| C-003 | yes | The draft carries every FR-122 element the toggles ask for | same | `a_generated_draft_carries_every_fr122_element_the_toggles_ask_for` passes | test output | PASS |
| C-004 | yes | Sub-points are structurally subordinate to their parent point, not flattened | same | `sub_points_are_subordinate_to_their_parent_point_and_not_flattened` passes; outline `items` is empty | test output | PASS |
| C-005 | yes | A section switched off in `IncludeInNotes` does not appear even when the model returns it | same | `a_section_the_operator_switched_off_...` passes, with a positive control | test output | PASS |
| C-006 | yes | A model draft is labelled AI-generated and carries the fabrication disclosure; the offline scaffold is not | same | both label tests pass; `disclosure.is_some() == ai_generated` asserted in both directions | test output | PASS |
| C-007 | yes | The transcript is byte-identical after generation and after editing the draft | same | `generation_and_draft_editing_leave_the_source_transcript_byte_identical` passes | test output | PASS |
| C-008 | yes | Transport failure degrades locally; `NotConfigured` and `QuotaExceeded` propagate | same | `transport_failure_degrades_locally_...` passes | test output | PASS |
| C-009 | yes | The API key appears in no error, draft, request body or `Debug` output — asserted against the REAL 401 body, which contains a masked key fragment | same | `the_api_key_never_appears_in_an_error_a_draft_or_a_debug_rendering` passes | test output | PASS |
| C-010 | yes | Transcript input and every response field are bounded by count and length; each bound test names its own bound via a per-key accessor and carries a positive control | same | 6 bounded-memory tests pass | test output | PASS |
| C-011 | yes | Every named control FAILS when removed, mutation-verified with siblings running, never `--exact` | 11 scripted mutations, each run against the whole crate suite | 11/11 RED, tree restored byte-identical afterwards | mutation log in PR body | PASS |
| C-012 | yes | The default build (features off) compiles and every existing `selahcue-cloud` test passes unchanged | `cargo test --workspace` | green; no existing test file edited | `make ci` output | PASS |
| C-013 | yes | `cloud_status` distinguishes hosted / direct-provider / key-missing / not-configured, and `notes_provider.is_some() == notes_available` in both directions | `cargo test` (operator) | `notes_provider_matches_availability_in_both_directions` + `the_status_is_always_one_of_the_four_defined_states` pass | test output | PASS |
| C-014 | yes | The chosen model, its price and the reasoning are recorded, confirmed against the live account | `GET /v1/models` + task comment | `gpt-5.6-terra` confirmed callable; cost stated; non-benchmark stated plainly | ClickUp comment + `openai.rs` docs | PASS |
| C-015 | yes | `quota` stays `null` and no meter is fabricated, including on the success path | operator test + headless | `quota_is_null_and_no_meter_is_fabricated` passes; headless asserts the placeholder survives a working generation | test + headless output | PASS |
| C-016 | yes | The panel does not show "coming soon" when generation works, names OpenAI, and does not over-report when no key is present | `python3 scripts/operator_headless.py` | all four states asserted on computed display and rendered text | headless output | PASS |
| C-017 | yes | Every view field name is pinned by a test, and the `settings.js` change ships in the same commit | `cargo test` (operator) + `git show --stat` | `the_frontend_contract_field_names_are_pinned` passes; both files in one commit | test output + commit | PASS |
| C-018 | yes | `PROVIDER-TRADEOFFS.md` records that the owner selected GPT and that its Haiku recommendation is superseded | review | superseded block present with evidence and the non-benchmark caveat | `docs/research/PROVIDER-TRADEOFFS.md` | PASS |
| C-019 | yes | `make ci` passes | `make ci` | ALL GREEN | run output | PASS |
| C-020 | yes | The new feature is actually linted and tested by the gates, not merely added | review of `Makefile` + `ci.yml` | `--features openai` clippy + test lines present in both | diff | PASS |
| C-021 | no | A real GPT draft is produced against the live API through the shipped Rust path | live run, 2026-09-04, `gpt-5.6-terra` and `gpt-5.6-luna` on a 1,431-word sermon | a structured FR-122 draft returns and the bounded parser handles it | Both models returned all 8 enabled sections, 4 points, 13 sub-points, and honoured the disabled `social_excerpts` toggle. All 16 references verified against the bundled KJV. **One transcript, one run each — not a claim that the prompt is good in general.** | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `cargo test -p selahcue-cloud --features openai --no-fail-fast`;
  `cargo test` and `cargo clippy --features openai-notes --all-targets -- -D warnings` in the
  operator crate; `python3 scripts/operator_headless.py`.
- Broader regression verification: the whole `make ci` target, re-run end to end after any fix
  rather than assuming later recipe lines were reached.
- Mutation verification: each named control removed in turn, the **whole crate suite** run with
  siblings, RED confirmed, and the file restored and diffed.
- Independent verifier: Cody (code), Sana (security — this ticket carries a key-handling
  finding), Vera (performance), Quinn (QA).
- Required environment: macOS dev machine; `.env` copied into the worktree root because the
  loader resolves its path at compile time from `CARGO_MANIFEST_DIR`.

## Iteration ledger

### Iteration 1 — the view contract, decided before any code

- Target criterion: C-013.
- Hypothesis: `cloud_status` can be widened without breaking `settings.js`, because the field is
  in the view contract but nothing branches on it.
- Change or investigation: read `settings.js` end to end. Confirmed `cloud_status` appears only
  in `defaultView()`; the renderer branches on `cloud_connected` (line 270) and on the *error
  code* `not_configured` (line 501), which is a different thing.
- Verifier executed: `grep` over the tree for both names; coordinator verified independently.
- Result: confirmed — one branching consumer, no mobile consumer.
- New evidence: the redefinition is safe; the load-bearing field is the boolean.
- Decision: iterate.

### Iteration 2 — four states, not three

- Target criterion: C-013.
- Hypothesis: three states suffice.
- Change or investigation: challenged on the three dev-key truths. "No key present" was
  collapsing into "not configured" — the same under-reporting bug the amendment exists to fix,
  one level down. Split `key_missing` out.
- Verifier executed: `the_status_is_always_one_of_the_four_defined_states`.
- Result: four states; `key_missing` is the state a fresh checkout is actually in.
- New evidence: the state is immediately useful rather than theoretical.
- Decision: iterate.

### Iteration 3 — confirming the model against the account

- Target criterion: C-014.
- Hypothesis: the model id can be taken from documentation.
- Change or investigation: ran `GET /v1/models` with the owner's key. `gpt-5.6-terra` is
  callable; `gpt-6-astra`, which the public docs list, is **not on this account**.
- Verifier executed: `GET /v1/models` → HTTP 200, 118 models.
- Result: hypothesis wrong; the account is the authority, not the docs.
- New evidence: a live generation then returned **429 `insufficient_quota`** — the account has
  no credits. C-021 is blocked and no live draft can be produced.
- Decision: iterate; report the gate rather than assert an unverified success.

### Iteration 4 — the 401 leak

- Target criterion: C-009.
- Hypothesis: keeping our own code free of the key is sufficient to satisfy "the key never
  appears in an error message".
- Change or investigation: drove a real 401. The body contains
  `"Incorrect API key provided: sk-proj-********************-key"` — prefix and trailing
  characters survive the masking. The existing hosted client's `status_error` forwards response
  bodies into `NoteError::Malformed`. A provider wired that way violates C-009 via the
  *provider's own response*, not via anything we wrote.
- Verifier executed: `the_api_key_never_appears_in_an_error_...` against the captured body;
  mutation M9 (401 forwards the body) → RED.
- Result: error mapping reads only `error.code` / `error.type` and never echoes a body.
- New evidence: also found OpenAI overloads 429 (terminal `insufficient_quota` vs transient
  rate limit); flattening them would report a two-second throttle as an exhausted quota. The
  same two flaws exist in the hosted client and were **routed to a follow-on ticket rather than
  fixed here** — different provider, different ticket, no live exposure today.
- Decision: iterate.

### Iteration 5 — making illegal states unbuildable

- Target criterion: C-004.
- Hypothesis: `items` and `points` as two public lists, with a convention that exactly one is
  populated, is good enough.
- Change or investigation: it is not — a section with both populated was constructible, and the
  webview renders whatever it is handed, so it would print the same content twice. Made both
  fields **private** behind `NoteSection::flat` / `NoteSection::outline` with accessors.
- Verifier executed: `every_section_is_a_flat_list_or_an_outline_and_never_both`, with a
  positive control asserting both shapes actually occurred.
- Result: the illegal state is not tested for; it cannot be built.
- Decision: iterate.

### Iteration 6 — the silence on the degraded path

- Target criterion: C-006.
- Hypothesis: `ai_generated: false` on the offline fallback is complete and correct.
- Change or investigation: correct but incomplete. The fabrication disclosure rightly does not
  apply to a scaffold that invents nothing — but the operator asked for AI notes and did not get
  them, and a scaffold shown in silence reads as though it *were* the notes. Added
  `DEGRADED_FALLBACK_NOTICE` (FR-135), `Some` exactly when `degraded`.
- Verifier executed: headless `PP C-011 (FR-135)` assertions on computed display.
- Result: a new under-reporting bug closed before it shipped.
- Decision: complete pending review.

### Iteration 7 — the live run, once credits existed

- Target criterion: C-021.
- Hypothesis: the prompt and schema, never having met a real model, would work as written.
- Change or investigation: built a **throwaway** example driving the real `OpenAiNoteProvider`
  over `ReqwestTransport` — the shipped instruction, schema, transport and bounded parser, called
  the way the operator calls them — and ran a 1,431-word sermon through `gpt-5.6-terra` and
  `gpt-5.6-luna`. Deleted afterwards: **the suite stays on mocks**, because a test that needs
  network and credits breaks CI for everyone and bills the owner on every run.
- Verifier executed: the live runs; then the produced references checked against the bundled KJV.
- Result: **the path works.** Both models returned title, main + supporting scripture,
  introduction, 4 points with 13 nested sub-points, illustrations, quotes, prayer points,
  calls-to-action, key lessons, chapter markers and summary. `social_excerpts` was off and stayed
  absent. `quota` came back `None`. `ai_generated` and the disclosure were both set. The parser
  needed no change and **no mock fixture had to be corrected** — the real envelope matched the
  shape the tests already assert.
- New evidence, three things worth more than the pass itself:
  1. **Non-determinism.** The first terra run omitted `chapter_markers` entirely; the second
     produced 7. Same prompt, same transcript. Recorded as an UNKNOWN above rather than smoothed
     over.
  2. **A prompt gap the benchmark exposed.** Luna numbered its point headings by hand ("1. ",
     "2. ") and packed explanations into them. The prompt never says not to. Terra inferred it;
     luna did not. Left unfixed in this MR **on purpose** — Cody is mid-review at `8601ef4` and
     terra is the default, so this is not a shipping defect today. Raised for a decision.
  3. **Zero fabrications** on this transcript: all 16 references across the two runs resolve in
     the bundled KJV. Encouraging, and no basis for relaxing FR-125 (86akby820) — one clean
     transcript says nothing about the case that check exists for.
- Decision: complete pending review.

## Risks and rollback

- **Risks:** the model has never produced a real draft, so prompt and schema quality are
  unproven (C-021). `main.rs` is shared with lane A. The `openai-notes` feature pulls `reqwest`,
  lengthening `make ci`.
- **Rollback or recovery:** both features are off by default, so reverting is deleting two
  feature lines; the default build path is unchanged and covered by the existing suites. The
  view rename is pinned by a test, so a revert is a failing test rather than a silent
  `undefined`.

## Pause and escalation conditions

- Live generation requires credits on the OpenAI account — **owner**. Escalated; C-021 stays
  BLOCKED rather than being claimed.
- The `status_error` body-echo and flat `402 | 429` mapping on the hosted client — **Diego**,
  as a follow-on ticket, with the captured evidence.
- A model-choice **setting** on `ProvidersSettings` — **Diego**. It belongs there, it expands
  the frontend contract, and it is therefore a ticket rather than a hunk of this MR.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86akby7d8-openai-sermon-notes.md --completion`
- Validator result: see PR body.
- Independent verification result: pending the four-reviewer gate.
- Terminal state: pending review. All 21 criteria PASS, including C-021 after the owner added
  credits. The honest scope of C-021 is "one draft generated successfully from one transcript on
  each of two models", which is **not** the same claim as "the prompt is good".
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: pending.
