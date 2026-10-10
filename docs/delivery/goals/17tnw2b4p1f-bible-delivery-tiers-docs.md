# Goal Contract — 17tnw2b4p1f

## Identity

- Goal ID: 17tnw2b4p1f
- Parent goal ID: 17tnw2b4p1e
- Title: The repo records the three-tier Bible delivery model, its evidence and its open questions, without deciding anything the owner has not decided
- Role: documentation-writer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b4p1f
- Created: 2026-10-10T00:00:00Z
- Updated: 2026-10-10T00:00:00Z
- Maximum iterations: 4
- Independent verification required: yes

## Objective

A reader can open ADR-0030 and the research note and learn, from the repo alone, how SelahCue proposes to deliver Bible versions in three tiers, what evidence supports it and how far to trust each piece, and which questions are still open. The ADR is marked Proposed and makes no decision that belongs to the owner or to counsel.

## Baseline

Verified on 2026-10-10 against `origin/main` at 5ecb944e:

- The highest ADR is ADR-0029; no open pull request or remote branch uses ADR-0030.
- `docs/research/LICENSING-REGISTER.md` already says BibleGateway and YouVersion are "reference only, not a bundling source" and lists eBible.org, open.bible and API.Bible as sources. It says nothing about Bible Hub, nothing about a competitor's delivery model, and nothing about a free/paid split.
- No decision-log entry mentions Bible versions and plans. The plan catalogue has no grant for Bible versions.
- ClickUp story 17tnw2b2jfv covers the first open versions (A1 to A7) and the API.Bible spike (B0); A6 (17tnw2b2jg3) owns edits to the licensing register, ADR-0017 and `docs/legal`.

## Inputs and evidence sources

- The 2026-10-09 reads of BibleGateway, Bible Hub, open.bible, API.Bible and WorshipPro pages, listed with URLs in the research note.
- `docs/research/LICENSING-REGISTER.md`, `docs/research/LICENSED-TRANSLATIONS.md`, ADR-0017, ADR-0021, ADR-0027.
- `implementation/desktop/crates/selahcue-scripture/assets/catalog.json` (copyright lines for Yoruba, Igbo, Hausa, BSB).
- ClickUp story 17tnw2b4p1e and its ten children.

## Scope

### In scope

- `docs/architecture/adr/ADR-0030-bible-delivery-tiers.md` (Proposed).
- `docs/research/BIBLE-SOURCES-AND-COMPETITOR-MODEL-2026-10.md`.
- This contract.

### Non-goals

- Any edit to `docs/research/LICENSING-REGISTER.md`, ADR-0017 or `docs/legal/*` (ticket A6 owns them).
- A decision-log entry (the owner has not decided; ticket D1 produces it).
- Code, workflows, publishing, or any change to a ClickUp ticket other than this one.

### Constraints

- Every claim about a third party is labelled VERIFIED, OBSERVED, INFERRED or UNVERIFIED, with a date.
- Third-party terms are paraphrased, not quoted at length.
- No credential, token or private data appears in the files.

### Assumptions and unknowns

- ASSUMED: ADR-0030 is still the next free number when the pull request is opened. Verified again immediately before opening.
- UNKNOWN: WorshipPro's contracts and where its open versions come from. Recorded as UNVERIFIED or INFERRED in the note, not resolved.

## Dependencies and approvals

- The pull request is opened as Draft and is not merged by this goal. Merge is the owner's.
- Independent review: Cody (code-reviewer) reads both documents for accuracy against their sources.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | ADR-0030 exists, is marked Proposed, and describes the three tiers | `grep -n -E "^- Status: Proposed" docs/architecture/adr/ADR-0030-bible-delivery-tiers.md` and `grep -c -E "^\*\*Tier [123]" docs/architecture/adr/ADR-0030-bible-delivery-tiers.md` | Status line found; count is 3 | docs/architecture/adr/ADR-0030-bible-delivery-tiers.md | PASS |
| C-002 | yes | ADR-0030 presents the free/paid split as a proposal waiting on D1 and names the CC BY-SA gating question | `grep -n -F -e "D1" -e "17tnw2b4p1h" -e "2(a)(5)(C)" docs/architecture/adr/ADR-0030-bible-delivery-tiers.md` | Matches in Status, Options and Open questions | docs/architecture/adr/ADR-0030-bible-delivery-tiers.md | PASS |
| C-003 | yes | The research note answers BibleGateway, Bible Hub and open.bible with a source URL and read date each | `grep -n -F -e "biblegateway.com/legal/terms" -e "biblehub.com/terms" -e "scripture-engagement.org/content/open-bible" docs/research/BIBLE-SOURCES-AND-COMPETITOR-MODEL-2026-10.md` | Each URL present in the body and in Sources, each with 2026-10-09 | docs/research/BIBLE-SOURCES-AND-COMPETITOR-MODEL-2026-10.md | PASS |
| C-004 | yes | Every WorshipPro statement is labelled OBSERVED or INFERRED and none is presented as a verified contract | Manual read of the "WorshipPro's published model" section | Section opens with the OBSERVED label and the no-contract caveat; the source inference is labelled INFERRED | docs/research/BIBLE-SOURCES-AND-COMPETITOR-MODEL-2026-10.md | PASS |
| C-005 | yes | The unverified items sit in one numbered list of six | `awk '/^## Unverified items/,/^## Sources/ { if ($0 ~ /^[0-9]+\./) n++ } END { print n }' docs/research/BIBLE-SOURCES-AND-COMPETITOR-MODEL-2026-10.md` | 6 | docs/research/BIBLE-SOURCES-AND-COMPETITOR-MODEL-2026-10.md | PASS |
| C-006 | yes | The diff against origin/main contains exactly the three new files and nothing under docs/legal, no licensing register, no ADR-0017 | `git diff --name-status origin/main...HEAD` | Three A (added) lines, the ADR, the note and this contract | command output in the pull request description | PASS |
| C-007 | yes | This contract is valid and the files contain no invisible or odd characters | `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b4p1f-bible-delivery-tiers-docs.md` and a scan for zero-width, bidirectional, BOM and non-breaking-space code points | Validator PASS; scan finds none | command output in the pull request description | PASS |
| C-008 | yes | Every repo path named in backticks in the two documents exists on this branch, apart from paths the text says do not exist yet | link-check script in the scratchpad (bt_linkcheck.py) | No missing path | command output in the pull request description | PASS |
| C-009 | yes | An independent reviewer finds no claim stronger than its source | Cody reads both documents against the cited pages and the repo | No blocking finding | review comment on the pull request | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-008 run by the author from the worktree.
- Broader regression verification: none needed; the change adds three documents and touches no code or workflow. CI path filters skip docs-only changes.
- Independent verifier: Cody, as C-009.
- Required environment: the worktree on branch `docs/17tnw2b4p1f-bible-delivery-tiers`, cut from `origin/main` 5ecb944e.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 to C-008
- Hypothesis: the three files satisfy the structural and consistency checks as first written.
- Change or investigation: wrote the research note, the ADR and this contract.
- Verifier executed: the grep checks for C-001 to C-006, `scripts/validate_goal_contract.py`, and `bt_linkcheck.py` (invisible-character scan and path check). The scan was first shown to catch a planted U+202A and a non-breaking space.
- Result: C-001 to C-008 PASS. The only non-ASCII character in the three files is the em dash (U+2014), as elsewhere in the repo docs. A first draft of three verifier cells used `|` inside a regex, which would have split the table; they were rewritten with `grep -F -e` and `awk`.
- New evidence: validator PASS (9 criteria, 9 mandatory); link check PASS; diff against origin/main is exactly the three new files.
- Decision: handoff (C-009 needs Cody; the pull request stays Draft until then)

## Risks and rollback

- Risks: a paraphrase reads stronger than its source; the next ADR number is taken by another branch before opening; a third-party page changes after 2026-10-09.
- Rollback or recovery: close the Draft pull request and delete the branch. Nothing else is touched.

## Pause and escalation conditions

- If counsel or the owner asks for the free/paid split to be stated as decided: stop; that is ticket D1's output, not this one's.
- If a source page contradicts a labelled claim on re-read: correct the label and note the change in the ledger.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b4p1f-bible-delivery-tiers-docs.md --require-complete`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
