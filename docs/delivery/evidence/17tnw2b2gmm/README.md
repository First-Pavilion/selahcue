# Auth-card accessibility — 17tnw2b2gmm

Task: https://app.clickup.com/t/17tnw2b2gmm
Design decision: Uma comment 1400430000277443 (existing glyph errors; custom country and terms crosses decorative).
Base: 9801fc587adba59a30ddee066efb5d0da26fc425, main.

Scope: SignUpView and ForgotPasswordView only, their browser regressions, and execution evidence. Shared components/tokens/copy/API requests remain existing behavior.

## Verification

- Unit suite: 1246 tests passed, no failures or skips.
- Type-check, production build, and lint: passed.
- Full driver measurement using isolated Playwright pages: 77 scenarios, 2765 checks, zero behavioral failures, including enumeration/surface comparisons and all six rate-limit claim scans. The old strict2645 equality check alone rejected the run; updated to the observed2765. `full-measurement.log` records that diagnostic, not a passing command. Exact final `npm run test:states` confirmation remains pending.
- `npm run build && python3 scripts/auth_card_responsive.py`: all six route/viewport cases passed at actual 375px and 1440px. Covers blank and malformed email, optional name length, missing/short password and mismatch, missing country, unaccepted terms, first-invalid focus and ARIA association, exactly one decorative cross, wrapping and horizontal overflow.
- `red.log`: behavioral failures observed against baseline before implementation.
- `negative.log`: nine independent restored-defect builds were rejected by the target behavioral assertion. Each mutated source was built to its own temporary output, served using the existing auth driver, and restored in a finally block. The full auth gate's production output was never overwritten by a mutant.

Negative cases: each card's wrapper opacity restored; signup fieldset disabled removed; each card's invalid-submit focus removed; each card's FormField circle style restored; signup country cross removed; signup terms cross removed. All nine failed the intended browser assertion, not infrastructure.

## Environment and limitations

macOS, installed Google Chrome, locked local npm dependencies; deterministic scripted GraphQL responses, no real account/provider requests. CLI Chrome clamps the requested 375px window to 500px on this machine; the focused responsive check uses Playwright's explicit viewport and asserts `innerWidth === 375`. The full auth suite preserves its desktop 358px column checks; the focused narrow variant checks the column fits the viewport.

Independent Cody, Shadow, Quinn and Vera review remains with root. No deployment, collection enablement, merge, or QA status transition by Farah.
