# Goal Contract — TASK-design2-download-modal

## Identity

- Goal ID: TASK-design2-download-modal
- Parent goal ID: NONE
- Title: A reusable offline-download progress modal is designed in Figma (Design 2.0) with every operational state and an implementation-ready handoff
- Role: ui-ux-designer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: PENDING (see Dependencies — posted as evidence on the STT / offline-assets story)
- Created: 2026-08-02
- Updated: 2026-08-02
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Design a single, reusable modal in the Design 2.0 Figma file that shows download progress and every failure/recovery state for first-time offline assets — the on-device STT (Whisper) model and any Bible translation — precise enough for the frontend-engineer to implement in the operator webview without guessing.

## Baseline

- The operator "Start listening" flow downloads the Whisper model on first use (`selahcue-operator/src/listening.rs` → `selahcue_stt::fetch_model(asset, cache, progress)` with a `progress(done,total)` callback; integrity-verified before load per FR-156 / ADR-0012). Bible translations are downloaded for offline use the same way.
- Before this task there was **no UI** for that download: progress surfaced only as `eprintln!` lines on stderr. First-time users saw a long silent hang.
- The Design 2.0 language is established in the Figma file (fileKey `SYQn5hFY8YVQKm3c6rw0eJ`): dark surfaces (base `#0b0d12`, surface `#14161d`), purple primary `#6e5cf0`, rounded cards + 1px `#262a34` borders, Inter, semantic green/gold/red, and a "SPEC —" column of state-matrix frames.
- No published component library exists (`search_design_system` returns empty); SPEC frames are hand-built raw-value states.

## Inputs and evidence sources

- Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, Design 2.0 console frame `312:124` and existing `SPEC —` frames (e.g. `346:124` System & Recovery States) for convention.
- `implementation/desktop/crates/selahcue-stt/src/model.rs` (`ModelAsset`: file_name, size_bytes, sha256) and `model_fetch.rs` (`fetch_model` progress callback) — the real states the UI must reflect.
- `implementation/desktop/crates/selahcue-operator/src/listening.rs` — resolve → download(%) → verify → load, and the failure surface.
- Design 2.0 palette frame `310:124`; the operator console emergency-footer rule ("controls always one action away — pierces any dialog").

## Scope

### In scope

- One reusable modal, designed as SPEC frame `396:124` ("SPEC — Offline Download Modal (Design 2.0)").
- All operational states: Downloading (progress), Verifying (integrity), Ready (success), Couldn't connect (recoverable network error), Couldn't verify (integrity failure), Offline (no connection), and a Bible-translation reuse variant.
- Accessibility, placement/scrim, flow, and parameterisation annotations; a written handoff spec.

### Non-goals

- Implementing the modal in code (frontend-engineer, follow-up).
- Changing the download engine, model selection, or integrity logic (already built).
- The mobile controller (Flutter) — this modal targets the operator webview.

### Constraints

- Must reuse the Design 2.0 palette/tokens and Inter; no new component library.
- Must not block or override the concurrent Design-2 operator-console workstream's uncommitted files.
- The modal must never obscure the emergency footer (BLACKOUT / Clear stays reachable above the scrim).

### Assumptions and unknowns

- ASSUMED: Cancel + "Hide (continue in background)" is the desired affordance set for a ~1.6 GB download (no explicit product decision on file). Owner: product — flagged in handoff.
- ASSUMED: Ready auto-continues into the triggering action (listening / opening the Bible). Owner: product.

## Dependencies and approvals

- ClickUp MCP: evidence comment to be posted on the STT / offline-assets story; status is PENDING until posted. Owner: this role.
- Frontend implementation is a downstream follow-up. Owner: frontend-engineer.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A SPEC frame for the download modal exists in the Design 2.0 file | get_metadata / get_screenshot on `396:124` | Frame "SPEC — Offline Download Modal (Design 2.0)" present | Figma `396:124`; scratchpad `dl-final2.png` | PASS |
| C-002 | yes | Progress state shows determinate progress: bar, size-of-size, %, and time remaining | Visual review of state 1 | "620 MB of 1.6 GB · 38%", filled bar, "~2 min left" | Figma `398:124` | PASS |
| C-003 | yes | Integrity verification is a distinct state (FR-156 gate is visible to the user) | Visual review of state 2 | "Verifying speech model / Checking integrity…" | Figma `400:124` | PASS |
| C-004 | yes | Success, network-error, integrity-error, and offline states are all designed | Visual review of states 3–6 | Ready (green), Couldn't connect (gold, Retry), Couldn't verify (red, discarded), Offline (Try again) | Figma `400:146`,`400:168`,`400:190`,`400:212` | PASS |
| C-005 | yes | The modal is demonstrably reusable for a Bible translation, not just the model | Visual review of state 7 | "Downloading King James Version · Bible · offline text" reusing the same layout | Figma `400:234` | PASS |
| C-006 | yes | Accessibility, focus, progress semantics, and reduced-motion are specified | Review of notes panel + handoff spec | role=dialog/progressbar, focus trap, aria-live %, reduced-motion, ≥AA | Figma `403:124`; handoff spec | PASS |
| C-007 | yes | Placement/scrim behaviour keeps the emergency footer reachable | Review of notes panel | "Emergency footer stays ABOVE the scrim and reachable" documented | Figma `403:124` | PASS |
| C-008 | yes | Parameterisation (model vs bible) and Design 2.0 tokens are documented for handoff | Review of notes panel + handoff spec | props `{assetKind,name,sizeBytes,whyCopy,successCopy}` + token list | Figma `403:124`; `docs/design/DOWNLOAD-MODAL-handoff.md` | PASS |
| C-009 | yes | A written, precise handoff spec exists for the frontend-engineer | File exists and covers states + a11y + copy | `docs/design/DOWNLOAD-MODAL-handoff.md` present | repo path | PASS |
| C-010 | yes | Goal Contract is structurally valid | `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-download-modal.md --require-complete` | exit 0 | command output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: screenshot each state frame and the notes panel in Figma; confirm copy, colour semantics, and progress affordances render as specified.
- Broader regression verification: confirm no existing frames were moved/edited (only new nodes `396:124` and descendants were created); the concurrent operator-console files are untouched.
- Independent verifier: frontend-engineer at implementation time (design must be buildable without new questions); a second designer/product review for the two ASSUMED affordance decisions.
- Required environment: Figma MCP (design mode) + repo.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-010
- Hypothesis: A Design-2.0 SPEC frame with seven states + an annotations panel + a written handoff satisfies the reusable-download-modal requirement.
- Change or investigation: Built frame `396:124` with the Downloading anchor card, cloned it into Verifying/Ready/Network-error/Integrity-error/Offline/Bible states, added a 4-column implementation-notes panel, and wrote the handoff spec.
- Verifier executed: get_screenshot on `396:124` (and per-state); goal-contract validator.
- Result: All states render correctly and on-brand; notes legible; validator exit 0.
- New evidence: scratchpad `dl-final2.png`; Figma node IDs above.
- Decision: complete

## Risks and rollback

- Risk: the two ASSUMED affordance decisions (Hide/background, Ready auto-continue) may be revised by product — cheap to change (text/button edits on the cloned states).
- Risk: no shared component library means the frontend must map raw tokens to the existing `--sc-*` CSS variables; mitigated by the token list in the notes panel and handoff.
- Rollback: the work is additive (new nodes only); deleting frame `396:124` fully reverts the design with no impact on other frames.
