# Goal Contract — TASK-86ak0qd9u-transactional-email-templates

## Identity

- Goal ID: TASK-86ak0qd9u-transactional-email-templates
- Parent goal ID: NONE
- Title: Three SelahCue transactional email templates designed in Figma with a implementation-ready handoff
- Role: ui-ux-designer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak0qd9u
- Created: 2026-08-14
- Updated: 2026-08-14
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Email verification, password reset, and account-exists notice exist as Figma frames plus a
handoff spec precise enough for an engineer to build the HTML and for QA to verify it, covering
every state, the plain-text fallback, and dark-mode behaviour.

## Baseline

**Verified** against the repository on 2026-08-14:

- `apps/accounts/services.py:220` — `EmailSender` is a no-op seam; `send_email_verification`,
  `send_password_reset` and `send_account_exists` all `pass`. No email is sent today, so signup
  cannot complete end to end.
- TTLs exist as settings: `ACCOUNT_EMAIL_VERIFY_TTL_SECONDS` (24h),
  `ACCOUNT_PASSWORD_RESET_TTL_SECONDS` (1h).
- `docs/design/DESIGN-TOKENS.md` — the product UI is dark (`bg/base #0e1116`,
  `accent/brand #5b6bd6`); tokens are pinned by `selahcue-present/tests/test_tokens.rs`.
- Figma design system file: `SYQn5hFY8YVQKm3c6rw0eJ`.
- No email template, HTML or design, exists anywhere in the repository. **Verified** by search.

## Inputs and evidence sources

- DEC-007 / ADR-0023 (customer auth, opaque sessions, no-enumeration posture)
- `docs/design/DESIGN-TOKENS.md`, `docs/design/DESIGN-2.0-HANDOFF.md`
- `implementation/api/selahcue_api/apps/accounts/services.py` (the three send seams + TTLs)
- Figma design system `SYQn5hFY8YVQKm3c6rw0eJ`
- ClickUp [86ak0qd9u](https://app.clickup.com/t/86ak0qd9u), epic [86ajy5v6k](https://app.clickup.com/t/86ajy5v6k)

## Scope

### In scope

- Three email designs: verification (24h), password reset (1h), account-exists notice (no token).
- Per email: default state, expired-link guidance, plain-text fallback, dark-mode rendering.
- Accessibility annotations: contrast, target size, alt text, language, reading order.
- Content/copy for every string, including the "you did not request this" path.
- A handoff spec in `docs/design/` an engineer can build from without guessing.

### Non-goals

- Email provider selection, credentials, SPF/DKIM/DMARC configuration (owner decision).
- The Celery delivery task and `EmailSender` implementation (hardening slice).
- Marketing email, receipts, or any non-auth transactional message.
- Localisation beyond leaving layout room for string expansion.

### Constraints

- **Email HTML, not web HTML**: table layout, inlined CSS, system font stack, single column,
  ≤600px. No flexbox, grid, web fonts, JavaScript, or load-bearing background images.
- **Light-mode primary**, dark via `prefers-color-scheme` as progressive enhancement. Dark-first
  is rejected: Gmail and Outlook force-invert unpredictably and produce black-on-black text.
- **Account-exists carries no token and no action link** — it is a warning to the real owner.
  Adding a login link would convert a no-enumeration safeguard into an enumeration oracle.
- One primary CTA per email, with the raw URL as readable text beneath it.

### Assumptions and unknowns

- **ASSUMED**: the verification/reset links point at a web route on `FRONTEND_BASE_URL`. The
  Platform API has no such route yet. Validation owner: backend, in the delivery slice.
- **UNKNOWN**: sending domain and From address. Validation owner: product/owner.
- **ASSUMED**: English only at launch; layout leaves ~30% expansion room.

## Dependencies and approvals

- Email provider + credentials — **owner**, not blocking design.
- `EmailSender` implementation + Celery worker — hardening slice, consumes this design.
- Figma write access via MCP — required to produce the frames.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Three email frames exist in Figma (verification, reset, account-exists) | Read back node IDs via Figma MCP | 3 frames: 719:133, 720:124, 720:136 | Figma page 719:132; node IDs in spec header | PASS |
| C-002 | yes | Every frame uses design-system colour values, not invented hexes | Compare frame fills against DESIGN-TOKENS.md | All fills bound to SelahCue Color variables (email/* + accent/brand) | spec §Palette; setBoundVariableForPaint used throughout | PASS |
| C-003 | yes | Each email specifies default + expired-link + plain-text fallback | Review handoff state matrix | 3 emails x default/expired/plain-text populated | spec §States + §Plain-text fallbacks | PASS |
| C-004 | yes | Account-exists contains no token and no action link | Review frame + copy | No CTA node and no tokenised URL in 720:136; constraint annotated on canvas | spec §Design constraint; frame 720:136 | PASS |
| C-005 | yes | Every user-visible string is specified, including expiry and not-requested copy | Review handoff copy deck | Every string specified incl. expiry + not-requested | spec §Copy deck | PASS |
| C-006 | yes | CTA and body contrast ≥4.5:1 on the light palette, computed not asserted | Contrast calculation per pair | 6 pairs computed, min 4.65:1, all >= 4.5:1 | spec §Accessibility table | PASS |
| C-007 | yes | Dark-mode behaviour is specified rather than left to the client | Review handoff | prefers-color-scheme rules + forced-invert failure mode documented | spec §Dark mode | PASS |
| C-008 | yes | Handoff is committed and linked from ClickUp | git log + ClickUp comment | Committed and linked from ClickUp | see commit + task 86ak0qd9u comment | PASS |
| C-009 | no | Figma frames screenshotted for review without opening Figma | Figma MCP screenshot | Inline screenshots captured for all three frames | use_figma screenshot output | PASS |

## Verification plan

- Focused verification: read back the Figma nodes; compute every contrast pair; check the
  handoff against C-001…C-008 line by line.
- Broader regression verification: none — this task adds design artefacts only and touches no
  code, so no test suite is affected. `make ci` is unaffected by design.
- Independent verifier: the engineer implementing `EmailSender` must be able to build from the
  handoff without asking a question; unanswered questions at that point are a C-008 failure.
- Required environment: Figma MCP write access.

## Iteration ledger

### Iteration 1

- Planned: ClickUp task + contract, then Figma frames, then handoff.
- Result: VERIFIED_COMPLETE — 3 frames, palette, handoff spec, all 9 criteria PASS
