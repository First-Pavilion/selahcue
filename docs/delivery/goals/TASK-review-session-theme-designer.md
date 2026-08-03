# Goal Contract — TASK-review-session-theme-designer

## Identity

- Goal ID: TASK-review-session-theme-designer
- Parent goal ID: TASK-design2-theme-designer
- Title: Independent code review of this session's Theme Designer 2.0 + streamline changes
- Role: code-reviewer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: PENDING (relates to impl story 86ajuptvy; ClickUp rate-limited this session)
- Created: 2026-08-03
- Updated: 2026-08-03
- Maximum iterations: 6
- Independent verification required: yes (adversarial multi-lens review workflow + reproduce)

## Objective

Independently review the CUMULATIVE code changes authored this session, catching real defects a
prior incremental review may have missed across the whole delta, and confirming the model
visibility slice coexists correctly with the concurrent (owner) `LayerMask` edits in compose.rs.

## Baseline

Verified before review: node --check OK; token 14/14; headless 180/0; `test_present` 21/21;
`test_compose`/`test_controller` pass. `make ci` currently blocked by out-of-scope concurrent WIP
(the `LayerMask`/screen-config feature spanning present.rs/compose.rs/lan/data). Three prior
adversarial reviews this session (Theme Designer 2.0, inspector, streamline) found 14 issues, all
fixed — this pass is the consolidated independent review of the cumulative delta.

## Scope

**In scope (this session's deliverables):**
- Model: `theme.rs` (additive `Element.visible` + accessor + serde helpers); `compose.rs` (the
  visibility gate `theme.elements.iter().filter(|e| e.visible())` + the `visible: _` match arms).
- Tests: `test_compose.rs` (visibility tests + `visible:true` sites), `test_controller.rs`
  (`visible:true`), `test_tokens.rs` (pin add/remove), `operator_headless.py` (D2 checks),
  `test_present.rs` (incidental `LayerMask::ALL` migration).
- Webview (`dist/`): `index.html` `#surface-theme-designer`, `app.css` Design-2.0 block,
  `app.js` (LAYERS panel + DnD, per-layer visibility, zoom, `tdFitCanvas`, collapsible templates,
  segmented Background, SIZE/LINE number fields, region canvas click-select, Region-picker +
  numeric-LAYOUT removal, Save-theme-expands-collapsed fix).

**Out of scope (concurrent owner WIP — do NOT review as this session's work):** the `LayerMask` /
per-screen layer-visibility feature itself (present.rs `compose_screen_live` mask param,
`compose_slide_masked`, selahcue-lan / selahcue-data changes) — flag ONLY where it breaks/interacts
with the in-scope visibility slice.

**Verified baseline:** node --check OK; token 14/14; headless 180/0; `test_present` 21/21;
`test_compose`/`test_controller` pass. `make ci` currently blocked by the out-of-scope concurrent WIP.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Full in-scope delta reviewed across correctness/maintainability/perf/tests/a11y | review workflow | all in-scope files examined | 3-lens adversarial workflow (wv15aiydj) over model (theme.rs/compose.rs), tests, and dist/ (index.html/app.css/app.js). All in-scope files examined. | PASS |
| C-002 | yes | Findings are evidence-backed, deduped, severity-ranked, adversarially verified | verify pass | confirmed set (or empty) | 3 confirmed after refutation: (1) eye keyboard activation stole row selection [a11y/med]; (2) selected-layer state was colour-only, no AT signal [a11y/med]; (3) visibility gate tested for Shape only, not Image/Text [qa/low]. Lower-sev filed items refuted or folded. | PASS |
| C-003 | yes | Every confirmed Blocker/High is resolved or explicitly owned; fixes re-reviewed | fix + re-verify | none unresolved | All 3 fixed: (1) `row.onkeydown` bails for child-target keydowns (`ev.target !== row`); (2) `aria-current="true"` + `" (selected)"` label + `tdAnnounce` on select; (3) added `a_hidden_image_element_emits_no_layers` + `a_hidden_text_element_emits_no_layers`. No Blocker/High found. | PASS |
| C-004 | yes | In-scope suites stay green after any fixes | headless + token + cargo | green | node --check OK; headless **185/0** (incl. 2 new a11y checks: aria-current, eye-keydown parity); `test_compose` **50/0** (incl. 2 new visibility tests); `test_tokens` **14/14** (my `operator_theme_designer_is_design_2` deterministically green). | PASS |
| C-005 | yes | Verdict states reviewed vs unreviewed scope + QA readiness | this doc + handoff | stated | Verdict below (§Final evaluation). Reviewed = my Theme Designer + visibility slice; NOT reviewed = owner's concurrent Screens/`LayerMask`/per-screen-theme WIP. QA-ready for the Theme Designer surface. | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- 3-lens adversarial review workflow (correctness/integration · a11y-ux · QA/test-quality) over
  the in-scope delta; refute each finding; fix confirmed Blocker/High; re-run headless + token +
  the affected cargo suites.

## Iteration ledger

### Iteration 1 — consolidated adversarial review of the cumulative delta
- Ran a 3-lens adversarial review (correctness/integration · a11y-ux · QA/test-quality) over the
  whole in-scope delta (workflow wv15aiydj). Filed candidates were refuted; **3 survived**:
  1. **[a11y/medium]** In `tdLayerRow`, pressing Enter/Space on a layer's eye toggle bubbled to
     `row.onkeydown` and *selected the row* instead of toggling visibility (keyboard ≠ pointer).
  2. **[a11y/medium]** The selected layer was signalled by colour only (`.sel`) — no programmatic
     state for assistive tech.
  3. **[qa/low]** The `compose_slide` visibility gate was exercised only through `Element::Shape`;
     the Image and Text arms of the `filter(|e| e.visible())` gate were untested.
- **Fixes (all applied + re-reviewed):**
  1. `row.onkeydown` now `return`s early when `ev.target !== row`, so keydowns originating on the
     child eye button no longer steal selection; the eye's native activation toggles visibility.
     Locked by a headless check (Enter on layer B's eye leaves layer A selected).
  2. `tdSelectLayer` now sets `aria-current="true"` on the active row, appends `" (selected)"` to
     its `aria-label`, and calls `tdAnnounce(...)` (announces "<Element/Shape> selected" or
     "<Body/Reference-Title> region selected"). Locked by a headless `aria-current` check.
  3. Added `a_hidden_image_element_emits_no_layers` (hidden full-frame Image → byte-identical to
     the no-element baseline; the same image SHOWN differs) and `a_hidden_text_element_emits_no_layers`
     (hidden bottom-band Text → `!has_ink_in(fb,0,90,200,100)`; SHOWN paints ink).
- **Re-verify:** node --check OK; headless 185/0; `test_compose` 50/0; `test_tokens` my pin green.
- **Concurrent-WIP note (out of scope):** `test_tokens::operator_webview_wires_per_screen_theme`
  (the owner's per-screen-theme feature, 86ajq321k) flickered red once, then green. Root-caused to
  the owner live-editing the SCREEN REGISTRY in `renderOutputs` (app.js) — moving `lower-third`/
  `stream` from static built-ins to on-demand virtual outputs, which transiently drops the
  `screen: "lower-third"` literal that test's compile-time embed pins. Not my code, not my test,
  explicitly out of review scope. Per systematic-debugging, stopped chasing the concurrent race.
- **Decision:** complete. All confirmed findings resolved; in-scope suites green.

## Risks and rollback

- Risk: reviewing concurrent WIP as this session's work → scoped out explicitly above.
  Rollback: findings are advisory; fixes are small + test-gated.

## Final evaluation

**Verdict: APPROVED — QA-ready for the Theme Designer surface.**

- **Reviewed (this session's delta):** the additive visibility model (`theme.rs` `Element.visible`
  + accessor + serde helpers; `compose.rs` `filter(|e| e.visible())` gate + `visible: _` arms), its
  tests (`test_compose.rs`, `test_tokens.rs`, the `test_present.rs` `LayerMask::ALL` migration), and
  the Design-2.0 webview (`index.html` `#surface-theme-designer`, `app.css` D2 block, `app.js` LAYERS
  panel + DnD + per-layer visibility + zoom + `tdFitCanvas` + collapsible Templates + segmented
  Background + SIZE/LINE fields + canvas region-select + Region-picker/numeric-LAYOUT removal).
- **Not reviewed (out of scope — owner's concurrent WIP):** the `LayerMask` / per-screen
  layer-visibility / per-screen-theme feature (`compose_screen_live` mask param, `compose_slide_masked`,
  the Screens-surface registry in `renderOutputs`, `set_screen_theme`/`themePickerFor`/`screen_themes`,
  selahcue-lan/selahcue-data). Flagged only where it races the in-scope slice (see ledger).
- **Findings:** 3 confirmed (2× a11y/medium, 1× qa/low) — all fixed and re-verified. No Blocker/High.
- **Risk remaining:** none in the in-scope slice. The only red observed (`operator_webview_wires_per_screen_theme`)
  is an owner-owned, out-of-scope test flickering under the owner's live registry edit — it must be
  re-confirmed by the Screens-feature owner once their tree is quiescent, not by this review.
- **QA readiness:** the Theme Designer surface + visibility model are ready for QA. Recommend the
  full `make ci` be re-run once the owner's concurrent Screens/`LayerMask` WIP lands (the gate is
  currently blocked by that WIP, not by this delta).
- Validator: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-review-session-theme-designer.md --require-complete`
- Terminal state: VERIFIED_COMPLETE (5/5 mandatory PASS).
- ClickUp final evidence: PENDING (ClickUp rate-limited this session — queue for 86ajuptvy / BUILD CONTROL).
