# Goal Contract — TASK-fe-plan-lifecycle-86ak8467m

## Identity

- Goal ID: TASK-fe-plan-lifecycle-86ak8467m
- Parent goal ID: NONE
- Title: The operator console drives the plan lifecycle (create / template / duplicate / import / publish) and renders the host's viewer, publish and template state without fabricating any of it
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: 86ak8467m (ClickUp MCP not connected this session — see "Dependencies and approvals")
- Created: 2026-08-29
- Updated: 2026-08-29 (addendum: PR #14 landed, verified against `69c3161`)
- Maximum iterations: 8
- Independent verification required: yes

## Objective

In the Tauri operator webview, the Service Plan surface offers the five plan-lifecycle
commands and renders the three new view fields, such that: every control is enabled only
when the host actually reports the matching capability, no control is a no-op, and an
absent field is never rendered as a negative verdict.

## Baseline

Verified at `3b39fb5` (origin/main, PR #12 + PR #13 merged) in a dedicated worktree:

- `dist/app.js:7484 planSummaryActions(box)` is the declared seam for the Plan Summary's
  write actions. `#plan-sum-publish` and `#plan-sum-precheck` ship **disabled** with
  `aria-describedby="plan-sum-later"`; `#plan-sum-live` is enabled and is a pure surface
  switch. The panel around them (`planRenderSummaryInto`) belongs to 86ak846ft and is not
  to be rebuilt.
- `dist/app.js:7260` renders the empty state with the honest placeholder line
  "Start from a template · Duplicate a past plan · Import — coming soon".
- No permission state exists on the plan surface at all: nothing reads a role, nothing
  hides an edit control, and there is no "View only" treatment.
- `OperatorStateView` (`selahcue-lan/src/protocol.rs:706`) ends at `summary`. `viewer`,
  `publish` and `plan_templates` do not exist on the wire yet; nor do the five commands.
  The webview therefore receives `undefined` for all three fields today.
- The three-state precedent is established and documented on the struct itself:
  `output_health` / `storage` / `session` / `summary` each carry "`None` = this host does
  not report it", and `planLinkState` implements the same rule for `ContentLinkView.status`.
- Gate baseline: `python3 scripts/operator_headless.py` → **963 checks, 0 FAIL**;
  `EXPECTED_MIN_CHECKS = 955`.
- GitHub Actions minutes are exhausted, so the local gate is the only evidence available.

Re-baselined mid-goal against the backend's shipped work (`69c3161`, PR #14, read directly
rather than taken on report):

- `PublishStateView` is `#[serde(default)]` with skip-if-none / skip-if-zero / skip-if-false.
  **Only `revision` is always present**; a fresh draft arrives as the whole object
  `{"revision":0}`. Missing `version` = 0, missing `published_revision` = null, missing
  `changed` = false.
- `changed` is compared against the published DOCUMENT, not against `published_revision`, so
  `revision != published_revision` with `changed:false` is a normal state — touched, not
  different.
- `ViewerView { role, can_edit }`, `PlanTemplateView { id, name, items: u32 }`, and
  `ImportItemView { kind, title, owner?, planned_secs? }` are as contracted.
- `TemplatePlan { template, name }` — `name` is REQUIRED and the host does no defaulting.
- `DuplicatePlan` under the current name is accepted as a true no-op (Ack, nothing changes).
- **`implementation/desktop/crates/selahcue-operator/src/main.rs` is untouched by PR #14** —
  none of the five Tauri commands is registered, and no `OperatorShell` / `RemoteOperator`
  method exists to back them. See "Dependencies and approvals"; this is the one blocking gap.

## Inputs and evidence sources

- Contract handed to this role: five commands, three appended view fields, three semantics.
- `docs/design/SERVICE-PLAN-2.0-HANDOFF.md` §5 (frame table), §9 (design-QA dispositions).
- `docs/design/UX-STATE-MATRIX.md` §4 (Empty / Populated / Permission-denied rows).
- `docs/design/UX-FLOWS.md` Flow 1 (happy path, branches B1, change badge).
- `docs/product/prds/SelahCue-PRD.md` FR-005, FR-006, FR-139.
- `selahcue-lan/src/protocol.rs` `OperatorStateView` — the wire shape the fields append to.
- `selahcue-core/src/plan.rs` on the sibling `feat/86ajy0hwg-plan-publish-handoff` worktree —
  the in-flight backend WIP carrying `MAX_PLAN_NAME_LEN`, `plan_name_valid`, `PLAN_TEMPLATES`.
  Read-only; never edited from here.

## Scope

### In scope

- `implementation/desktop/crates/selahcue-operator/dist/app.js`, `app.css`, `index.html`.
- `scripts/operator_headless.py` — behavioural checks for everything added.
- The five commands (`publish_plan`, `new_plan`, `template_plan`, `duplicate_plan`,
  `import_plan`) invoked by their wire names with their contract argument names.
- The three view fields (`viewer`, `publish`, `plan_templates`), each read through one
  validating accessor with a single definition.
- Frames 5 (`608:875`), 8 (`611:124`), 14 (`612:342`), 17 (`612:1020`).

### Non-goals

- Any Rust change. The commands and fields are 86ajy0hwg's to implement; a second branch
  touching `protocol.rs` / `controller.rs` / `main.rs` would collide with the worktree that
  is already doing it.
- Frames 13 and 16 (autosave restore, crash-loop recovery) — a different ticket, and
  frame 16 is an open architecture decision with the owner.
- FR-139 portable-bundle import (items + media refs). `import_plan` carries an item list only.
- A saved-plan library. The host persists exactly one plan row, so "Duplicate previous"
  in the empty state has nothing to duplicate from.
- Content links in the import path — set afterwards with the existing `SetItemContent`.
- Re-deriving `can_edit` from `role`, or inventing a `validated` plan state.

### Constraints

- Absent field = "this host does not report it", never a negative verdict.
- `can_edit` is consumed, never recomputed.
- `changed` is not rendered while `published_revision` is absent.
- A control that cannot work is disabled with a stated reason; never a no-op.
- View-only controls are **removed from the DOM**, not greyed and not merely `hidden`
  (a class-level `display` rule defeats the `hidden` attribute in this webview).
- Do not reproduce Figma fills where the console already ships better contrast.
- No new small-type `--sc-text-muted` sites (79 already open on that token).

### Assumptions and unknowns

- ASSUMED: the Tauri command names mirror the wire names one-for-one, as every existing
  plan command does (`add_item`, `move_item`, `set_item_content`, `plan_undo`). Validation
  owner: backend (86ajy0hwg). Recorded as a handoff line, not silently relied on — the UI
  degrades to disabled-with-reason if the commands are absent.
- UNKNOWN: what `publish.version` counts relative to `revision` / `published_revision`.
  Rendered as an opaque "version N" label only, never arithmetic. Validation owner: backend.
- UNKNOWN: whether "Publish to team" should keep network-implying copy when the
  implemented hand-off is local (`SERVICE-PLAN-2.0-HANDOFF.md:105` vs the shipped label).
  Owner: product/design. This goal keeps the shipped label and authors no new network copy.

## Dependencies and approvals

- 86ajy0hwg (backend) — owns the five commands and the three fields. Shipped as **PR #14**
  (`69c3161`). This goal ships the client against that shape and gates every control on the
  host reporting it, so it is correct both before and after PR #14 merges.

- **CLOSED.** This goal raised a blocking gap: at `69c3161` the operator shell's Tauri layer had
  no plumbing for the five commands, while `LiveController::operator_view()` already populated
  `publish` (`controller.rs:2329`) and `plan_templates` (`:2337`) and `console_view()` stamped
  `viewer` with `can_edit: true` — so a merged backend would have made this client enable
  controls the shell could not dispatch. It is implemented at **`a1eadd4`** across all four
  layers, and **verified from that source rather than taken on report**: all five are registered
  in `invoke_handler` (`main.rs:3115-3119`), and every command name and argument name matches
  what this webview invokes —

  | Tauri command | JS arguments | Verified at `a1eadd4` |
  |---|---|---|
  | `publish_plan` | *(none)* | `main.rs:2136` |
  | `new_plan` | `{ name }` | `main.rs:2140` |
  | `template_plan` | `{ template, name }` | `main.rs:2144` |
  | `duplicate_plan` | `{ name }` | `main.rs:2152` |
  | `import_plan` | `{ name, items: [{ kind, title }] }` | `main.rs:2156` |

  The capability gate in this client is **not** a workaround for that gap and is not unwound:
  the shell drives whichever host is on the other end, and a remote output window may be a
  different build. It is the same three-state rule the contract itself mandates, applied to the
  command set rather than to a rendered field.

- ClickUp MCP is **not connected in this session**. No ticket read, status move, or comment
  can be made from here. A structured pending ClickUp update is produced instead of a
  shadow backlog, per the operating contract.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | An absent `viewer` renders no "View only" badge and hides no control; `can_edit:false` hides them; `can_edit:true` shows them | `python3 scripts/operator_headless.py` | the three-state checks PASS | gate output | PASS |
| C-002 | yes | `can_edit` is consumed from the host and never re-derived from `role`: a view with `role:"viewer"` + `can_edit:true` still shows edit controls | `python3 scripts/operator_headless.py` | check PASS | gate output | PASS |
| C-003 | yes | View-only removes edit/add/reorder/publish from the DOM (so they leave the tab order), rather than disabling them | `python3 scripts/operator_headless.py` | computed-display + `querySelector` null checks PASS | gate output | PASS |
| C-004 | yes | No change badge while `published_revision` is absent, even if the host says `changed:true` | `python3 scripts/operator_headless.py` | check PASS with a positive control that the badge does appear when published | gate output | PASS |
| C-005 | yes | Each of the five commands is sent with its contract name and arguments, and only from its own control | `python3 scripts/operator_headless.py` | five send-site checks PASS | gate output | PASS |
| C-006 | yes | A name that is empty, whitespace-only, >120 characters, or contains a control character is refused client-side with an inline message and no command is sent | `python3 scripts/operator_headless.py` | validation checks PASS, incl. a positive control that a valid name IS sent | gate output | PASS |
| C-007 | yes | Name length is counted in Unicode scalar values, not UTF-16 code units, matching `plan_name_valid` | `python3 scripts/operator_headless.py` | an astral-plane name of 120 chars is accepted; 121 refused | gate output | PASS |
| C-008 | yes | Import is capped at `MAX_PLAN_ITEMS` (500) client-side and item titles are validated by the same rule as the plan name | `python3 scripts/operator_headless.py` | cap + per-title checks PASS | gate output | PASS |
| C-009 | yes | Every control whose capability the host does not report is disabled with a stated reason reachable by AT, and none is a no-op | `python3 scripts/operator_headless.py` | disabled + `aria-describedby` checks PASS | gate output | PASS |
| C-010 | yes | "Duplicate previous" (empty state) and FR-139 bundle import ship disabled with a stated reason | `python3 scripts/operator_headless.py` | checks PASS | gate output | PASS |
| C-011 | yes | The Plan Summary panel is not rebuilt: `planRenderSummaryInto`'s card rows are unchanged and all pre-existing SP3 panel checks still pass | `git diff` review + `python3 scripts/operator_headless.py` | no change to the summary card; suite green | diff + gate output | PASS |
| C-012 | yes | A failed command shows an error the operator can read and does not leave a spinner or a false success | `python3 scripts/operator_headless.py` | rejection checks PASS | gate output | PASS |
| C-013 | yes | The whole webview gate passes with no FAIL and the check floor is raised to the real new count | `python3 scripts/operator_headless.py; echo $?` | exit 0, `0 FAIL`, count > 963 | gate output | PASS |
| C-014 | yes | The full local gate passes | `make ci` | ALL GREEN, exit 0 | command output | PASS |
| C-015 | yes | Real WKWebView render inspected — no collapsed flex select control, no grid auto-row overflow, controls visible at the real size | `python3 scripts/operator_webkit_smoke.py` + screenshot | renders correctly | smoke output + screenshot | PASS |
| C-016 | yes | Independent review: Cody, Vera, Sana, Quinn; blocking findings remediated | four review agents | no unremediated blocking findings | review report artifact | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `python3 scripts/operator_headless.py` (headless Blink, real DOM/CSS).
- Broader regression verification: `make ci` (fmt, clippy, all Rust suites, operator check,
  headless webview, Flutter) — run once, serialised against other sessions in this checkout.
- Engine fidelity: `python3 scripts/operator_webkit_smoke.py` (Playwright WebKit) plus a real
  render, because the Blink gate cannot see the WKWebView-only layout traps.
- Independent verifier: Cody / Vera / Sana / Quinn, per the review pipeline.
- Required environment: macOS dev box, Chrome for the Blink gate, Playwright WebKit.

## Iteration ledger

### Iteration 1 — the implementation slice

- Target criterion: C-001 … C-012
- Hypothesis: every control can be made honest without any Rust change, by gating each on the
  host reporting the matching view field — which is also the correct long-run behaviour for an
  older host or a remote peer.
- Change or investigation: capability accessors + validators, then the four frames.
- Verifier executed: `python3 scripts/operator_headless.py`
- Result: 1034 checks, 0 FAIL, exit 0 (baseline was 963)
- New evidence: the pre-existing `SP3 AC-5` checks pinned "publish is disabled" unconditionally,
  and `SP C-002` pinned the empty state's "coming soon" sentence. Both were re-pointed at the
  new rule rather than deleted.
- Decision: iterate

### Iteration 2 — mutation-verify the controls

- Target criterion: every control added in iteration 1
- Hypothesis: the checks bite — each fails if the guard it names is removed.
- Change or investigation: a 12-mutation battery, each running the FULL gate.
- Verifier executed: the battery (see "Verification plan")
- Result: **11 of 12 caught; one survived** — deleting `published &&` from `planPublishState`'s
  `changed` left the suite completely green.
- New evidence: the change-badge renderer branched on `!pub.published` FIRST and only then on
  `pub.changed`, so the control was asserting a **re-derived copy** of the predicate rather than
  the predicate itself — CLAUDE.md's 86ak643rc trap, walked straight into. Fixed by having the
  badge consume `pub.changed` directly; re-run RED.
- Decision: iterate

### Iteration 3 — the contract addendum (PR #14 landed)

- Target criterion: C-004, C-005, C-006
- Hypothesis: the shipped wire shape differs from the relayed one in ways that produce
  correct-looking bugs.
- Change or investigation: read `69c3161` directly; `planPublishState` rewritten to apply the
  omitted defaults before validating; `duplicate_plan` refuses the unchanged name; fixtures
  replaced with the real skip-if-default shapes.
- Verifier executed: `python3 scripts/operator_headless.py`, then the battery (now 16 mutations)
- Result: 1041 checks, 0 FAIL. Battery: 15 of 16 caught by their named check.
- New evidence: two real defects. (1) Requiring `version` made every real `{"revision":0}` draft
  read as UNREPORTED, silencing the panel on a plan it could describe. (2) The control that
  should have caught it **threw** instead — it dereferenced `.plan-pub-line`, which the defect
  removes — aborting the driver at check 728 rather than failing the check that names the rule.
  A null-safe accessor now makes it report.
- Decision: iterate

### Iteration 4 — the real render

- Target criterion: C-015
- Hypothesis: the new states survive WKWebView.
- Change or investigation: a WebKit render probe (Playwright WebKit, the engine Tauri ships on)
  driving all five states with layout assertions plus screenshots, and **looking at them**.
- Verifier executed: `scripts/operator_webkit_smoke.py`; the probe; visual inspection
- Result: smoke 5/0 FAIL. Probe 18 assertions, 0 FAIL — **after fixing a defect the assertions
  did not have and the screenshot did.**
- New evidence: view-only hid the ADD ITEM column with `display:none`, but
  `.plan-builder-grid` declares three fixed tracks (`220px | 1fr | 340px`). Taking the first
  child out of flow does not remove its track — it shifts every remaining child one place left,
  so the run sheet rendered inside the 220px palette column ("G…", "We…") beside a 792px
  inspector and an empty third track. Invisible to both gates, which assert elements rather than
  track widths. Fixed with `.plan-builder-grid.is-viewonly`; now pinned by a resolved-track
  assertion in the fast gate.
- Decision: iterate

### Iteration 5 — floors, contrast and the full gate

- Target criterion: C-013, C-014
- Hypothesis: the suite floor and the full local gate are green.
- Change or investigation: `EXPECTED_MIN_CHECKS` 955 → 1045; the disabled-action reason copy
  moved off `--sc-text-muted` (3.79:1, AA-large only) onto `--sc-text-secondary` (8.12:1), with
  the ratio measured through the live CSS engine and mutation-verified.
- Verifier executed: `python3 scripts/operator_headless.py`; `make ci`
- Result: gate 1045 checks, 0 FAIL, exit 0. `make ci`: see "Final evaluation".
- New evidence: `make ci` cannot run in a FRESH WORKTREE — `cargo clippy` on the operator crate
  fails in `tauri-build` with `resource path binaries/selahcue-output-aarch64-apple-darwin
  doesn't exist`, because `binaries/` is gitignored and only exists in the original checkout as
  zero-byte placeholders. Reproduced the placeholders locally to proceed; raised as a finding.
- Decision: handoff

### Iteration 6 — review round 1

- Target criterion: C-016
- Change or investigation: four reviewers dispatched on `f335a0d`. Remediation applied for the
  security findings, for the coordinator's addendum, and for one defect this goal found in its
  OWN code by applying the coordinator's technique.
- Verifier executed: `python3 scripts/operator_headless.py`; the mutation battery (now 21);
  the WebKit render probe; `make ci`
- Result: gate **1062 checks, 0 FAIL**; **21 of 21** mutations caught by their named check;
  WebKit probe 0 FAIL.
- New evidence, in order of how much it mattered:
  - **`publish_plan` was the one of five that is not like the others.** All five shared
    `planLifecycleRun`, which cleared the operator's selection. Four REPLACE the run sheet and
    must; publish moves a marker and leaves the plan and its item ids intact, so clearing there
    threw the operator back to the Plan Summary for no reason they could name. The battery would
    never have found it — the test and the code agreed with each other. `replacesPlan` is now
    spelled out at all five call sites and pinned by `PL AC-31` plus its inverse control.
  - **Sana M1 (Medium):** `planTemplateList` bounded neither entry count nor rendered string
    length, and `ControlClient` sets no `max_message_size` (`client.rs:70`) while the server caps
    its own inbound at 64 KiB (`server.rs:46`) — verified in source. Bounded on the ENTITY.
  - **Sana L2:** the publish ordinals shared a COUNT's bound, so a long session would have
    degraded the whole panel to "unreported" under a stated reason that was not true.
  - **Sana I2:** `planPublish` lacked the send-site guard its four siblings had. Unreachable, but
    an asymmetric guard across five siblings is the shape a real hole hides in.
  - **Coordinator:** `duplicate_plan` had un-marked the on-air row backend-side. Fixed there; the
    dialog now names what is on air and states that the audience is unaffected, rather than
    blocking an action that is legitimate mid-service.
- Decision: handoff

## Risks and rollback

- The capability predicate keys on the host reporting `publish` and is consumed by all five
  controls. A host that reported `publish` while implementing only some of the commands would
  enable the rest; nothing in the wire shape allows finer discrimination, and the five land as
  one addition, so this is documented rather than defended against.
- `publish.version` is rendered as an opaque label and never used in arithmetic, so a change in
  what it counts cannot produce a wrong number here.
- Rollback: the change is confined to `dist/` and one test script; revert the branch.

## Pause and escalation conditions

- Any need to change `protocol.rs`, `controller.rs` or the operator's `main.rs` — that is
  86ajy0hwg's branch; stop and hand off rather than edit across tickets.
- Any copy decision that would assert a network hand-off — owner: product/design.
- ClickUp write operations — blocked until the MCP connection is restored; owner: user.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-fe-plan-lifecycle-86ak8467m.md --completion`
- Validator result: (run at handoff)
- Independent verification result: pending review pipeline
- Evidence: webview gate **1046 checks, 0 FAIL** (baseline 963; floor raised 955 -> 1046);
  16-mutation battery, every mutation caught by its named check; WebKit boot smoke 5/0 FAIL;
  WebKit render probe 18 assertions, 0 FAIL, screenshots inspected; `make ci` **ALL GREEN**,
  exit 0.
- Independent verification result: pending (C-016)
- Terminal state: pending review
- Remaining failed or blocked criteria: C-016 pending. The Tauri command plumbing is a blocking
  cross-ticket gap, recorded under "Dependencies and approvals" — it does not block this branch,
  it blocks the FEATURE, and it must land with or before PR #14.
- ClickUp final evidence comment: BLOCKED — ClickUp MCP is not connected in this session. The
  handoff text is prepared and returned to the coordinator rather than written to a shadow
  backlog.
