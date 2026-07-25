# Goal Contract — STAGE8-core-presentation

## Identity

- Goal ID: STAGE8-core-presentation
- Parent goal ID: BUILD-selahcue
- Title: Core presentation implementation — songs/slides with themes and a real editor, media playback via sandboxed platform decoders, and the epic remainders (missing-media check, timer surfaces, per-layer clearing once layers exist)
- Role: build (stage goal; specialists per batch)
- Status: ACTIVE (gate-approved 2026-07-25, songs-first)
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 40
- Independent verification required: yes

## Objective

Turn the foundation's single-static-slide items into real presentation content: multi-slide **songs** with structure and copyright footers, **themes/templates** applied without content loss, a keyboard-first **editor** with undo/redo, proper **text shaping** (Unicode/diacritics, ADR-0014), and **media** (images → video/audio) through the ADR-0016 sandboxed decode path with a missing-media placeholder that never blanks an output — driven by the same preview→live safety the foundation proved.

## Baseline

Stage 7 closed (pending the owner's on-device QA disposition) at 44 batches: plan CRUD + authoring, one-slide-per-item rendering (glyph text via font8x8), 5 PD translations with the chapter browser, timers with TIME UP, displays + identify, emergency controls, autosave/recovery + breaker, pinned-TLS remote + mobile controller, 3-OS CI incl. launch smoke + gated NFR. No songs (multi-slide items), no themes, no editor UI, no media of any kind, no real text shaping.

## Inputs and evidence sources

- Epics: Presentation & Slides `86ajp07ce` (FR-009..024) · Media Playback `86ajp0815` (FR-066..073, FR-173) · Service Planning `86ajp072p` remainders (FR-006..008, FR-138/139) · Timers `86ajp07nr` remainders (FR-054..065, FR-175) · deferrals `86ajpy59e` (per-layer clearing), `86ajpzbxf` item 3 (library surface).
- ADR-0002 (compositor), ADR-0014 (text shaping), ADR-0016 (decode sandbox); spike S2 (GStreamer→wgpu), S10 (Unicode text); Figma: Presentation Editor / Theme Designer / Song Editor (to be designed per batch), operator-console frames `150:124`/`165:124`.

## Scope

### In scope — proposed story breakdown (created in ClickUp on gate approval)

| # | Proposed story | Epic | Owner role | Requirements | Acceptance sketch |
|---|---|---|---|---|---|
| S8-1 | **Song model + multi-slide items** (verse/chorus/bridge structure, slide-per-stanza, current/next navigation *within* an item, PD-hymn import format) | 86ajp07ce | backend-engineer | FR-009/010/019/020 | a 6-stanza song advances slide-by-slide with Space; next-line on stage; plan shows "Song · N slides" truthfully |
| S8-2 | **Text shaping** (real font stack + shaping per ADR-0014, replacing font8x8: Unicode, diacritics, fallback) | 86ajp07ce | backend-engineer | FR-023/024, S10 | "María" + Yoruba diacritics render correctly on the output; parity tests hold on 3 backends |
| S8-3 | **Themes + templates** (theme model, apply w/o content loss, per-item override; template slides) | 86ajp07ce | frontend-engineer + ui-ux-designer | FR-015/016/017 | switching theme re-renders every slide, zero content loss; theme designer per Figma |
| S8-4 | **Slide/song editor in the console** (keyboard-first, ≥20-step undo/redo, command palette) | 86ajp07ce | frontend-engineer | FR-011/014/021/022 | edit→stage→go-live E2E; editing never touches Live (FR-012 held) |
| S8-5 | **CCLI/copyright metadata + on-slide footer** for songs | 86ajp07ce | backend-engineer | FR-020 | footer renders licence line on song slides; metadata persisted |
| S8-6 | **Sandboxed decode skeleton + image slides** (out-of-process decode per ADR-0016; PNG/JPEG/WebP/GIF/BMP; bounded cache; **missing-media placeholder — never black**) | 86ajp0815 | backend-engineer + software-architect | FR-066/070/173 | a crafted/corrupt image contains to placeholder; other outputs unaffected (NFR-024) |
| S8-7 | **Missing-media detection + pre-service check** (unblocks `86ajp0az9` once media exists) | 86ajp072p | backend-engineer | FR-138/139 | opening a plan flags every missing item; checklist screen per Figma |
| S8-8 | **Video/audio playback** (platform decoders H.264/HEVC/AAC — no gst-libav; audio device routing; GStreamer→wgpu texture handoff **spike S2 first**) | 86ajp0815 | backend-engineer | FR-067/068/073 | video plays on main via HW path; decoder crash → placeholder, bounded recovery (FR-160) |
| S8-9 | **Timer epic remainders** (pause/resume UI, per-output visibility, count-up/segment types, FR-175 flash analyzer assertion) | 86ajp07nr | frontend-engineer | FR-054..065/175 | analyzer-verified TIME UP; per-output routing honest |
| S8-10 | **Per-layer clearing becomes real** (`86ajpy59e`: layered live output arrives with songs/media overlays → Backspace clears the top layer only) | 86ajp083m | backend-engineer | FR-076..078 | clearing one layer leaves others on air; keybindings unchanged |

### Non-goals

- Transcription (R3), scripture intelligence (R4), sermon intelligence (R5), licensed-translation providers (awaiting DECISION `86ajpzb09`), TTS (de-scoped, DEC-001), themes marketplace, media beyond the codec safe-harbour set.

### Constraints

- Preview→live safety (FR-012), never-blank-live (NFR-024), no-unbounded-growth, canonical keybindings/design tokens, wire-fixture compatibility (additive only), codec-patent safe harbour (FR-073: platform decoders only), sandboxed decode (FR-173), seizure safety (FR-175). Every batch: adversarial review + CI green + ClickUp updated + gate.

### Assumptions and unknowns

- UNKNOWN (gate choice): **songs-first (recommended)** vs media-first. Songs-first is lowest-risk (pure Rust on the proven compose path, immediate service value) while the S2 media spike de-risks in parallel. Media-first front-loads the hardest integration (sandbox + GPU interop) before the content model needs it.
- ASSUMED: text shaping (S8-2) lands before themes (S8-3) polish — themes without real shaping would be re-done.

## Dependencies and approvals

- Stage-7 closure (owner's on-device QA + milestone disposition) precedes or parallels the first Stage-8 batch (owner's call at the gate).
- Story creation in ClickUp: on gate approval.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`. (Stage-level; each batch adds its own predicate block like Stage 7's.)

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Songs: multi-slide items with structure, in-item navigation, CCLI footer — E2E from plan to live | batch predicates + E2E | S8-1/S8-5 accepted | STAGE8 batch blocks | PENDING |
| C-002 | yes | Text shaping: Unicode/diacritics correct on output, 3-backend parity held | shaping + parity tests | S8-2 accepted | batch blocks | PENDING |
| C-003 | yes | Themes/templates apply without content loss; editor with ≥20-step undo, edit-never-touches-Live E2E | UI/E2E tests | S8-3/S8-4 accepted | batch blocks | PENDING |
| C-004 | yes | Media: images + video/audio via sandboxed platform decoders; crafted-media containment to placeholder; missing-media pre-service check | fault-injection + E2E | S8-6/7/8 accepted | batch blocks | PENDING |
| C-005 | yes | Timer remainders incl. FR-175 analyzer assertion; per-layer clearing real once layers exist | analyzer + tests | S8-9/10 accepted | batch blocks | PENDING |
| C-006 | yes | Every batch independently reviewed; CI green throughout; ClickUp current | per-batch review records | all batches gate-reviewed | CODE-REVIEW-batch8*.md | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Per-batch: adversarial Workflow review, full test suites, CI matrix; media batches add fault-injection (decoder crash, malformed media) and the security lens (FR-173).
- Independent verifier: per-batch reviews + the Stage-8 closing demo (songs + themes + media end-to-end).
- Required environment: 3-OS CI + owner hardware for media/audio device QA.

## Proposed batch sequence (critical path → · parallel-safe ∥)

1. **8a Songs** (S8-1) → 2. **8b Text shaping** (S8-2) → 3. **8c Themes + templates** (S8-3) → 4. **8d Editor** (S8-4) → 5. **8e Song copyright** (S8-5, small, may fold into 8a/8d)
∥ **8f Media spike S2 + sandbox skeleton + images** (S8-6) — starts alongside 8b → 6. **8g Missing-media + pre-service check** (S8-7) → 7. **8h Video/audio** (S8-8, the biggest risk — spike-gated)
∥ **8i Timer remainders** (S8-9) — any time; **8j Per-layer clearing** (S8-10) — after 8a introduces layers.

Critical path: **8a → 8b → 8c → 8d** (content model → shaping → themes → editor). Biggest risk: **8h** (GPU interop + sandbox), de-risked by the S2 spike inside 8f. Likely conflict surfaces: `selahcue-present` compose (8a/8b/8c serialise), `selahcue-operator` console (8d/8g serialise); the media crates are additive (∥-safe).

## Iteration ledger

### Iteration 0 — planning (batch 7as)

- Drafted; gate-approved 2026-07-25 (songs-first). Stories created in ClickUp: S8-1 `86ajpzha3` · S8-2 `86ajpzha7` · S8-3 `86ajpzhak` (waiting_on S8-2) · S8-4 `86ajpzhan` (waiting_on S8-3) · S8-5 `86ajpzhb8` (waiting_on S8-1) · S8-6 `86ajpzhbc` · S8-8 `86ajpzhbg` (waiting_on S8-6) · S8-9 `86ajpzhbh`; existing S8-7 = `86ajp0az9` (now waiting_on S8-6) and S8-10 = `86ajpy59e` (now waiting_on S8-1). Batch 8a (Songs) opened.

## Risks and rollback

- Risks: media decode integration (sandbox + HW paths per OS) is the stage's long pole; text-shaping regressions on the parity oracle. Rollback: per-batch git; additive crates for media.

## Pause and escalation conditions

- Codec/licensing questions → owner + counsel; design sign-off per batch via the Figma flow.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/STAGE8-core-presentation.md`
- Validator result: PENDING (structure validated at draft time)
- Independent verification result: PENDING
- Terminal state: ACTIVE (in progress)
- Remaining failed or blocked criteria: all PENDING
- ClickUp final evidence comment: PENDING
