# Preserve PDF shaping through the HarfRust update

PR #395's direct HarfRust 0.13.3 update changes `Shaper::shape` from accepting a feature slice to `ShapeOptions`. Existing operator code still passes `&[]`, causing E0308 in both archived ordinary and native-toolchain operator jobs. Four independent reviewers confirmed the owning compile blocker. The user authorizes a minimal fix, current validation, re-review and merge after passing.

The authoritative source evidence is `release-evidence/open-pr-review/pr395-cody-review.md`, `pr395-quinn-review.md` and `pr395-vera-review.md` in the evidence workspace. Exact original/current desktop, operator and pinned compiler equivalence makes the retained compiler failure applicable to this unchanged call. It is an actual build-gate RED with zero test assertions, not a claimed behavioral assertion failure.

## Required correction

Only change `implementation/desktop/crates/selahcue-operator/src/notes_export.rs` at the existing shaping call. Replace `self.face.shape(buffer, &[])` with `self.face.shape(buffer, harfrust::ShapeOptions::default())`. The verified 0.13.3 default uses an empty custom feature list and leaves scale absent, retaining font-unit output. Preserve existing segment-property inference, one shaping operation per grapheme, glyph handling, and the caller's point-size/units-per-em conversion. Do not add scale or change font selection, normalization, pagination, serialization or save lifecycle.

The updated dependency pins and both locks are already integrated with current main in the isolated worktree. Do not change them, the frozen proof inputs, workflows, tests or any other source path in this task. WinSafe 0.29's reviewed signatures remain a separate Windows execution requirement.

## Verification and scope

Read the complete actual compiler failure and pinned API evidence before changing source. No redundant failing baseline compile is needed. Static source/whitespace checks are allowed; all local project execution remains held for active paging. Root must obtain exact repaired operator and native-feature compilation/tests, existing PDF/export tests, the existing ignored independent PDF fixture/oracle and relevant Windows compilation/save checks before final merge qualification. The independent PDF gate and platform orchestration are controller-owned follow-up; this one-line source correction must not claim those checks passed.

No new test that mirrors the one-line source spelling is appropriate. Existing compiler and renderer tests exercise the real consumer. Any behavior regression found by those tests is a new fix requirement, not a reason to weaken the original oracle or skip a platform. Installed native chooser, physical display/NDI and full installer qualification remain their release tasks.
