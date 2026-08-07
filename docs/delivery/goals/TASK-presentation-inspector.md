# Goal Contract — TASK-presentation-inspector

## Identity

- Goal ID: TASK-presentation-inspector
- Parent goal ID: EPIC-86ajp07ce (Presentation & Slides)
- Title: Presentation & Media — per-element Inspector + right-panel Media⟷Inspector context switch
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajvjtax
- Created: 2026-08-04
- Updated: 2026-08-04
- Maximum iterations: 12
- Independent verification required: yes (adversarial multi-lens review + headless reproduce)

## Objective

Implement the ui-ux-designer's per-element **Inspector** (design board 509:124 / `PRESENTATION-MEDIA-STATES-spec.md`)
in the Presentation & Media surface: the right column becomes contextual — **Media Library by default,
Inspector when an element is selected** — so **selecting an element opens the Inspector** bound to it, with
per-kind controls (Text / Shape / Image incl. Replace) driving the deck engine.

## Baseline

**Verified:** the surface (86ajvccqr, QA) edits elements with the on-canvas selection box + keyboard only —
**no inspector**. The right panel is a bare `<aside class="pm-media">` (index.html:727). The deck engine
(86ajv8qd9) + the deck_* bridge (deck_workspace.rs / main.rs) are shipped; `element_json` currently exposes
only `{index,kind,label,x,y,w,h,z,visible}` (deck_workspace.rs). `theme::Element` (Text/Shape/Image) + its
enums (TextAlign/VAlign/Fit/ShapeKind, all snake_case serde; Rgba `{r,g,b,a}`) are the model. `renderPresentation`
+ `pmRenderMedia` + the canvas select/keyboard already drive `deck_select_element`. Design: `docs/design/PRESENTATION-MEDIA-STATES-spec.md` §2/§2a + board 509:124.

## Inputs and evidence sources

- `PRESENTATION-MEDIA-STATES-spec.md` (§2 context switch, §2a inspector variants), Figma 509:124.
- `crates/selahcue-operator/{src/{deck_workspace.rs,main.rs},dist/{index.html,app.css,app.js}}`.
- `crates/selahcue-present/src/theme.rs` (Element + enums), `test_tokens.rs`, `operator_headless.py`.

## Scope

### In scope
- **Right panel** `#surface-presentation`: a `Media` / `Inspector` tab header (roving `role="tab"` →
  `role="tabpanel"`); default **Media**; the Inspector tab **disabled** ("Select an element") when nothing is
  selected; **auto-switch to Inspector on element select, back to Media on deselect**; manual tab switching.
- **Rust bridge:** extend `element_json` to expose the full per-element props (serde) + `deck_update_element(index, patch)`
  (merge-patch → deserialize → replace; snapshot only on a real edit; text clamped) + `deck_replace_element_image(index, media_id)`.
- **Inspector bodies** (bound to the selected element): **Text** (content · size · line-height · weight · align H/V ·
  colour · fit) · **Shape** (fill · border + width · corner · kind) · **Image** (source name + **⚠ missing** ·
  **Replace…** · Fit shown as an honest later affordance) · **common** (Arrange z · Opacity · 👁 visibility · 🗑 delete).
- **Media-cell** `selected` (the asset used by the current image element) + `hover/focus` states.

### Non-goals (documented → remain in the design spec / a follow-up)
- Destructive **confirm popovers** (delete-slide / remove-media-in-use) + **system** loading/error/view-only states
  (spec §5/§6) — a linked follow-up. The full **font-family picker** + **Fit render** (letterbox) are noted spec seams.
- Present→live-output routing, video-on-slide, persistence (prior deferrals).

### Constraints
- Deck edits return the operator-local `DeckView` (never the LAN `OperatorView`); compositor stays native (preview
  via `render_deck_slide`); **FR-012** (edit/select never touches Live); `--sc-*` AA; never colour-only; bounded
  (snapshot-on-real-edit; text cap); WKWebView-safe; every pinned needle preserved; `make ci` green.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Right panel has Media/Inspector tabs (roving `role=tab`/`tabpanel`); default Media; Inspector disabled when nothing selected | headless + pin | tabs present + wired | `#pm-tab-media/-inspector` + `#pm-media-body`/`#pm-inspector-body`; headless: default Media, Inspector disabled until select | PASS |
| C-002 | yes | Selecting an element AUTO-OPENS the Inspector bound to it; deselect returns to Media | headless | select → inspector; deselect → media | `pmSyncRightPanel` auto-switch; headless: add/select → Inspector auto-opens + binds; tab-switch both ways | PASS |
| C-003 | yes | Bridge: `element_json` full props + `deck_update_element` + `deck_replace_element_image`; operator compiles + clippy clean | `cargo check`+`clippy` operator | clean | serde full props + short aliases; both commands registered; `cargo check`+`clippy` clean | PASS |
| C-004 | yes | Inspector · Text controls drive `deck_update_element` + update the preview | headless | text edits fire the command | headless: size/colour({r,g,b,a})/align_h patches fire deck_update_element | PASS |
| C-005 | yes | Inspector · Shape controls (fill/border/corner/kind) | headless | shape edits fire | Shape body renders fill/border/corner/variant → deck_update_element | PASS |
| C-006 | yes | Inspector · Image — source name + missing; Replace → `deck_replace_element_image`; Fit honest-later | headless | image body + replace | headless: Image inspector + Replace arms flow → picking a media image fires deck_replace_element_image; Fit disabled + note | PASS |
| C-007 | yes | Common inspector: Arrange (z) · Opacity · visibility · delete | headless | common controls fire | headless: Bring-to-front → deck_set_element_z; opacity/visibility/delete wired | PASS |
| C-008 | yes | Media-cell selected (asset in use) + hover/focus states | headless + css | states render | `.pm-asset.in-use` (path match) + `:hover`/`:focus-visible` | PASS |
| C-009 | yes | a11y: tablist roving + arrows, auto-switch announced without stealing canvas focus, AA, keyboard-operable, FR-012 | headless | a11y checks pass | tablist roving + Left/Right; auto-switch announces + never `.focus()`; AA `--sc-*`; FR-012 (no deck_go_live on edit) | PASS |
| C-010 | yes | Bounded: `deck_update_element` snapshots only on a real edit; text clamped; no-op safe | operator unit test | green | 2 unit tests (valid patch + snapshot-on-change; malformed patch = no-op, no panic) — operator tests 5/5 | PASS |
| C-011 | yes | `test_tokens` pin (inspector needles) + `operator_headless` checks + `EXPECTED_MIN_CHECKS` bump | `cargo test` + headless | green | pin 15/15 (inspector needles); headless **235/0** (+12 inspector checks); `EXPECTED_MIN_CHECKS` 223→235 | PASS |
| C-012 | yes | Full CI gate green | `make ci` | ALL GREEN | `make ci` == **ALL GREEN** (exit 0), re-confirmed after the 11 review fixes: fmt/clippy/all Rust suites/operator check/headless **238/0**/flutter | PASS |
| C-013 | yes | Independent adversarial review; confirmed Blocker/High fixed + re-verified | review workflow | none unresolved | 3-lens workflow (w4o3q6gyt): **11 confirmed (4 med, 7 low); no Blocker/High**; **all 11 fixed + re-verified** (operator tests 6/6, headless 238/0) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `node --check`; `cargo check`+`clippy`+`test` (operator); `operator_headless.py`; `test_tokens`.
- Broader: `make ci`. Existing PM checks stay green (the inspector is additive to the shipped surface).
- Independent: 3–4-lens adversarial review (bridge/state · a11y-ux · webview-integration · test-quality).

## Iteration ledger

### Iteration 1 — build the inspector + right-panel switch
- **Rust:** `element_json` now serialises the full element props (+ short `x/y/w/h/z/visible/opacity` aliases
  the canvas reads); generic `deck_update_element(index, patch)` (merge → `from_value` → replace; snapshot
  on real edit; clamp geometry + text; malformed patch = no-op); `deck_replace_element_image`; media `path`.
- **Webview:** right panel wrapped with a `Media`/`Inspector` tablist + `#pm-panel` (media-body + inspector-body);
  `pmSyncRightPanel` auto-opens the Inspector on select (no focus-steal), back to Media on deselect;
  `pmRenderInspector` (Text/Shape/Image bodies + Arrange/Opacity/visibility/delete); the Replace flow;
  media-cell `.in-use`/hover.
- **Tests:** pin needles; 3 operator unit tests; 12 headless inspector checks (→ 235/0).
- **Verify:** `make ci` == ALL GREEN (first pass); adversarial review then run.

### Iteration 2 — adversarial review + fixes
- **C-013:** 3-lens review (w4o3q6gyt; 17 agents, each finding refuted) → **11 confirmed (4 medium, 7 low;
  no Blocker/High)**. **Fixed all 11:**
  - *[med state ×2]* the image-**Replace** flow's `pmReplaceTarget` survived a slide/selection change → could
    replace the wrong element → a `pmEndReplace()` helper (clears target + hides hint + resets the media
    filter), called on a selection change and on pick/cancel. + headless deselect check.
  - *[med a11y ×2]* activating an inspector **button** (Align/Arrange/eye) lost focus to `<body>` on the
    re-render → `data-ik` focus save/restore in `pmRenderInspector` (WCAG 2.4.3). + a focus-restore headless check.
  - *[low]* serde skip-default fields (weight/variant/corner/border/align/fit) rendered blank → JS defaults.
  - *[low]* non-placeable **video** grid cells were enabled no-ops → disabled + honest "playback arrives later" label.
  - *[low]* `--sc-primary` text/link on dark below AA → `--sc-primary-hover`.
  - *[low test]* added: deselect→Media check, focus-not-stolen check, Replace `{mediaId,index}` arg assertion,
    an `update_element` clamp unit test.
- **Re-verify:** node OK; operator `clippy`+`test` (6/6) clean; headless **238/0** (`EXPECTED_MIN_CHECKS`
  235→238); re-running `make ci` for the final sign-off.
- **Decision:** complete on the final `make ci` green.

## Risks and rollback

- Risk: `element_json` short-key change breaks the shipped canvas JS. Mitigation: KEEP the short `x/y/w/h/z/visible`
  keys AND add the full serde props. Rollback: additive.
- Risk: `deck_update_element` accepts a malformed patch → panic. Mitigation: merge→`from_value` returns `Err` → no-op
  (never unwrap); text/geometry clamped; unit-tested.
- Risk: auto-switch steals canvas focus mid-drag. Mitigation: switch panel mode without moving focus on selection.

## Pause and escalation conditions

- Stop at `make ci` green + review clean + owner visual gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-presentation-inspector.md --require-complete`
- Validator result: PASS (13/13 mandatory PASS)
- Independent verification result: 3-lens adversarial review (w4o3q6gyt) — 11 confirmed (4 med, 7 low),
  no Blocker/High; all 11 fixed + re-verified.
- Terminal state: **VERIFIED_COMPLETE**
- Remaining failed or blocked criteria: none.
- Scope note: this pass built the **inspector core** (the owner's explicit ask). The remaining spec states
  (destructive confirm popovers, system loading/error/view-only, the full font-family picker, Fit render)
  stay documented in `PRESENTATION-MEDIA-STATES-spec.md` §5/§6/§8 as follow-on.
- ClickUp final evidence comment: posted to 86ajvjtax + BUILD CONTROL 86ajnx548.
