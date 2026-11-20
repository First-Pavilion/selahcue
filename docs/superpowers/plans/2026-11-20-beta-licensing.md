# Beta Licensing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every self-service church gets a time-boxed Beta grant that unlocks everything until the end of 5 May 2027. The grant runs on top of the ordinary Free licence and ends by itself, and the website and desktop show when it ends.

**Architecture:** The catalogue already resolves the effective plan as the licence's plan, overridden by a higher-rank `OrgPlanGrant` that has `starts_at`/`ends_at` (`apps/catalogue/org_plans.py:20`).
- We seed a BETA plan above PRO and create one BETA `OrgPlanGrant` per self-service org.
- Free licences, their 365-day renewal and the fallback plan stay exactly as they are.
- The device limit and the plan's end date are read from the effective plan instead of the licence.
- The end date is surfaced in the signed entitlement, `accountOverview`, the website Account page and desktop Account Setup.

**Tech Stack:** Django + Strawberry GraphQL (`implementation/api`), Rust (`selahcue-licensing`, `selahcue-operator`), operator webview JS, Vue 3 + TypeScript (`implementation/marketing`).

**Spec:** `docs/superpowers/specs/2026-11-19-public-beta-design.md` §W1. This plan amends it as decided on 2026-11-20 (Task 8 records the amendment).
- Beta comes from a time-boxed grant, not from making Beta the fallback.
- The end date is the end of 5 May 2027, not 31 Mar 2027.

## Global Constraints
- **Beta grants:** all grants unlocked. That means no watermark, unlimited screen and NDI outputs, **10** devices, **180** cloud transcription minutes a week (3 h) and **5** sermon notes a week. The weekly reset stays on Monday in the org's timezone, as it is today.
- **Beta end:** `2027-05-06T00:00:00+00:00` (exclusive), which is the end of 5 May 2027 UTC. Show it as "5 May 2027".
- **Free plan:** FREE stays the fallback (`is_fallback=True`). Free licence issuance, the 365-day validity and the 30-day renewal window (`free_lifecycle.py:36-38`) are not changed.
- **No plan code in API source:** none may be written as a literal outside the seed migrations, because `test_no_plan_name_is_hardcoded_in_the_api_source` must keep passing. The beta plan code and end date come from settings. Add the new seed migration to that test's `SEED_MIGRATIONS` allow-list.
- **Beta switch:** settings `SELAHCUE_BETA_PLAN_CODE` (default `""`) and `SELAHCUE_BETA_ENDS_AT` (ISO 8601, default `""`). If either is empty, no beta grants are created. This is the off switch. Add both keys to `implementation/deploy/production.env.example` and `deployments.md` with the production values `BETA` and `2027-05-06T00:00:00+00:00`.
- **Additive changes:** the signed entitlement gains one field, `plan_ends_at` (RFC 3339 string or `null`). The desktop contract ignores unknown fields (`selahcue-licensing/src/contract.rs:448`), so older desktops are unaffected. Do NOT clamp the entitlement `expires_at` to the beta end, because the desktop reads `expires_at < license_expires_at` as "degraded" (`entitlement.rs:53-57`).
- **Usage weeks:** a week that is already open when the grant ends keeps the limits it opened with until the next Monday reset (`usage/services.py:_create_week` snapshots them). That is deliberate, and Task 3 pins it with a test.
- **Gates:** API changes pass `make api-check`. Marketing changes pass `make marketing-check` and `npm run test:core`. Rust passes `cargo test`, `cargo clippy -D warnings` and `cargo fmt --check`.
- **Commits and branches:** one branch and one PR for ClickUp 17tnw2bhkd2, cut from `origin/main`. Commit messages carry no attribution trailers.

## Decisions taken in this plan (owner can override)
- **When the grant is created:** at registration of a self-service org, and again (idempotently) on the first self-service activation, which covers orgs registered before this ships. No grant is created at or after the beta end.
- **Rank and overlap:** BETA has rank 4, above PRO (3). An org with an active staff grant of a higher rank keeps it. Only one active BETA grant exists per org.
- **The grant record:** `granted_by_actor_id = "system:beta"` and reason `"Public beta: all features until the beta end date"`. These satisfy the accountability constraints.
- **The `deviceLimit` shown to the church** is the effective limit: the larger of the licence's own `device_limit` and the effective plan's `device_instances`.

## Review Focus
1. **Activating devices 2 to 10 on a Free licence while Beta is active** must succeed, and the 11th must be refused. All three checks that read `license_key.device_limit` (`devices/services.py:390`, `:520`, and the entitlement's `instances_limit` at `:728`) must use the effective limit. Test in Task 3.
2. **After 5 May the church is back on Free.** Cloud quota uses FREE limits from the next Monday, the account page shows Free with no end date, and the 2nd device is refused on new activation. Test in Tasks 3 and 4.
3. **With the beta switch off** (an empty setting), registration and activation behave exactly as they do on `main` today. Test in Task 2.
4. **Registering twice, or activating several times, creates exactly one grant.** Test in Task 2.
5. **An older desktop** receiving an entitlement with `plan_ends_at` still verifies it and shows the plan. Test in Task 5.

---

### Task 1: Seed the BETA plan

**Files:**
- Create: `implementation/api/selahcue_api/apps/catalogue/migrations/0011_beta_plan_reference_data.py`
- Modify: `implementation/api/tests/test_product_catalogue_slice.py:75` (add the new migration to `SEED_MIGRATIONS`), `implementation/api/tests/test_plan_catalogue_migrations.py:95` (expected plan set)
- Test: `implementation/api/tests/test_plan_catalogue_migrations.py`

**Interfaces:**
- Produces a `Plan` with:
  - `code="BETA"`, `display_name="Beta"`, `rank=4`, `sort_order=40`, `is_fallback=False`, and a `reason` of at least 8 characters
  - `PlanGrant` rows: `device_instances="10"`, `screen_outputs="unlimited"`, `ndi_outputs="unlimited"`, `watermark="false"`, `cloud_transcript_minutes_per_week="180"`, `sermon_notes_per_week="5"`
- Seed it the way 0007 does (`migrations/0007_weekly_catalogue_reference_data.py`), with a reverse that deletes only BETA and its grants. Bump `CatalogueRevision` the way 0007 does, if it does.

- [ ] **Step 1: Write the failing tests**
  - In `test_plan_catalogue_migrations.py`:
    - The expected set becomes `{"FREE","CORE","PRO","BETA"}`.
    - Add `test_beta_plan_unlocks_everything`: BETA has rank 4, it is not the fallback, and its grants equal the values above. FREE is still the only fallback.
  - In `test_entitlement_manifest_grants.py`, add a case: the BETA plan publishes `watermark=false` and unlimited outputs, in the same shape as the existing PRO case (`test_the_free_tier_watermarks_and_the_paid_tiers_do_not`, :232).
- [ ] **Step 2: Run** `cd implementation/api && .venv-api-check/bin/python -m pytest tests/test_plan_catalogue_migrations.py tests/test_entitlement_manifest_grants.py -q`. Expected: FAIL, because BETA is missing.
- [ ] **Step 3: Add the migration** and the allow-list entry.
- [ ] **Step 4: Run** the same tests, then `make api-check`. Expected: PASS. `makemigrations --check` is clean.
- [ ] **Step 5: Commit** `api: seed the BETA catalogue plan (17tnw2bhkd2)`.

### Task 2: Create the beta grant for self-service orgs

**Files:**
- Create: `implementation/api/selahcue_api/apps/catalogue/beta.py`
- Modify:
  - `implementation/api/selahcue_api/settings.py` (the two settings)
  - `apps/accounts/services.py` (call it in `register_customer_user`, :824)
  - the self-service activation path that issues the Free licence (`apps/license_keys/free_lifecycle.py` `ensure_free_license_under_org_lock`, :204)
  - `implementation/deploy/production.env.example`
  - `deployments.md`
- Test: `implementation/api/tests/test_beta_grant.py`

**Interfaces:**
- Produces `beta_window() -> tuple[Plan, datetime] | None` in `beta.py`. It returns None when either setting is empty, when the code matches no plan, or when the timestamp doesn't parse. A bad config logs one warning and never raises.
- Produces `ensure_beta_grant(org: CustomerOrg, *, at: datetime) -> OrgPlanGrant | None` in `beta.py`.
  - It is idempotent under the org lock that the caller already holds.
  - It creates a grant `[at, ends_at)` only when `beta_window()` is set, `at < ends_at`, and the org has no BETA grant yet. If the org already has one (active or ended), it returns that grant.
  - It is called only for self-service orgs (`is_self_service_org`, `accounts/services.py:742`).

- [ ] **Step 1: Write the failing tests** in `tests/test_beta_grant.py`, using `override_settings`. Test code may use the literal `"BETA"`.
  - `test_registration_creates_one_beta_grant_until_the_end_date`: after `register_customer_user`, the org has exactly one `OrgPlanGrant` with plan BETA, `ends_at == 2027-05-06T00:00:00Z` and actor `system:beta`.
  - `test_first_activation_creates_the_grant_for_an_org_registered_before_beta`: an org with no grant gets one on its first self-service activation.
  - `test_repeated_registration_and_activation_keep_one_grant` (Review Focus 4).
  - `test_no_grant_when_beta_is_switched_off`: with either setting empty, nothing is created, and registration and activation results are byte-identical to the switch-off baseline (Review Focus 3).
  - `test_no_grant_after_the_beta_end`: at `2027-05-06T00:00:00Z` nothing is created.
  - `test_bad_beta_config_does_not_break_registration`: with an unknown code or a garbage timestamp, registration still succeeds and creates no grant.
  - `test_staff_managed_org_gets_no_beta_grant`: an org that isn't self-service gets nothing.
- [ ] **Step 2: Run** `pytest tests/test_beta_grant.py -q`. Expected: FAIL (no module).
- [ ] **Step 3: Implement** `beta.py`, the settings and the two call sites.
- [ ] **Step 4: Run** `pytest tests/test_beta_grant.py tests/test_free_license_lifecycle.py -q`, then `make api-check`. Expected: PASS. The Free lifecycle tests are unchanged.
- [ ] **Step 5: Commit** `api: time-boxed beta grant for self-service churches (17tnw2bhkd2)`.

### Task 3: Effective device limit and plan end date

**Files:**
- Modify:
  - `apps/catalogue/org_plans.py` (`_select_org_plan` also returns the winning grant's end; `EffectivePlan` gains `ends_at`)
  - `apps/catalogue/contracts.py` (`EffectivePlan`)
  - `apps/devices/services.py:390`, `:520`, `:728`
  - `apps/entitlements/services.py:133-168` (payload)
- Create: `apps/devices/limits.py`
- Test: `tests/test_beta_device_limit.py`, `tests/test_usage_weeks.py` (one added case)

**Interfaces:**
- Consumes `ensure_beta_grant` from Task 2, in test setup.
- Produces `EffectivePlan.ends_at: datetime | None`. It is the grant's `ends_at` when `source == "staff_grant"`, otherwise None. Add it as the last field with default None, so existing constructors keep working.
- Produces `effective_device_limit(license_key: AppLicenseKey, at: datetime) -> int` in `apps/devices/limits.py`. It returns `max(license_key.device_limit, <effective plan device_instances>)`. Read the plan value with `plan_device_instances_for_issuance(plan)` (`catalogue/services.py:255`). If the plan value is None, fall back to `license_key.device_limit`.
- The three device sites call `effective_device_limit(license_key, now)` instead of reading `license_key.device_limit`. That covers the new-device refusal, the re-mint allowance and the entitlement `instances_limit`.
- The entitlement payload adds `"plan_ends_at"`: `EffectivePlan.ends_at` as RFC 3339, or `None`.

- [ ] **Step 1: Write the failing tests** in `tests/test_beta_device_limit.py`:
  - `test_beta_church_activates_ten_devices_and_the_eleventh_is_refused`: the 11th device gets `POLICY_DENIED` (Review Focus 1).
  - `test_entitlement_reports_ten_instances_and_the_beta_end`: the signed payload has `instances_limit == 10` and `plan_ends_at == "2027-05-06T00:00:00Z"`, in the repo's RFC 3339 form, and `grants.watermark is False`.
  - `test_after_the_beta_end_a_second_new_device_is_refused`: with the clock at the end, the effective limit is 1 and `plan_ends_at` is None (Review Focus 2).
  - `test_free_church_without_beta_keeps_one_device`: no grant means limit 1.
  
  In `test_usage_weeks.py`, add `test_week_open_at_beta_end_keeps_its_limits_until_monday`. The week opened under BETA keeps 180 min and 5 notes. The week after the next Monday opens with FREE's 20 min and 1 note.
- [ ] **Step 2: Run** these tests. Expected: FAIL.
- [ ] **Step 3: Implement** the changes described in Interfaces.
- [ ] **Step 4: Run** `make api-check`. Expected: PASS. If an existing payload snapshot test pins the entitlement keys, update it to add `plan_ends_at`, and say so in the report.
- [ ] **Step 5: Commit** `api: effective device limit and plan end from the active plan (17tnw2bhkd2)`.

### Task 4: `accountOverview` shows the effective limit and beta end

**Files:**
- Modify: `apps/accounts/account_overview.py` (:210), `graphql/account_schema.py` (`AccountAllowance` :148, `AccountLicense` :125)
- Test: `tests/test_account_overview.py`

**Interfaces:**
- Consumes `EffectivePlan.ends_at` and `effective_device_limit` from Task 3.
- Produces:
  - `AccountAllowance.planEndsAt: String | null`, as ISO 8601
  - `AccountLicense.deviceLimit`, which now carries the effective limit as a string, the same type as before

- [ ] **Step 1: Write the failing tests:**
  - `test_overview_shows_beta_plan_and_end_date`: `allowance.planDisplayName == "Beta"`, `planEndsAt` is the end, `license.deviceLimit == "10"`, and `allowance.stt.limit == "10800"` (seconds).
  - `test_overview_after_beta_end_shows_free`: `planDisplayName == "Free"`, `planEndsAt is None`, and `deviceLimit == "1"`.
  
  Also update the schema snapshot test, if one exists.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `make api-check`. Expected: PASS.
- [ ] **Step 5: Commit** `api: account overview shows the beta end and effective device limit (17tnw2bhkd2)`.

### Task 5: Desktop Account Setup shows "Beta until 5 May 2027"

**Files:**
- Modify:
  - `implementation/desktop/crates/selahcue-licensing/src/verified.rs:22` (`EntitlementDisplay`) and its parse site
  - `crates/selahcue-operator/src/account/mod.rs:15` (`AccountView`)
  - `crates/selahcue-operator/src/account/controller.rs:1082-1087`
  - `crates/selahcue-operator/dist/account.js:328-340`
  - `dist/index.html:1388-1396`
- Test: `selahcue-licensing` tests for the display parse; `crates/selahcue-operator/src/account/tests/controller.rs`; a headless check in `scripts/operator_headless.py`

**Interfaces:**
- Consumes the entitlement field `plan_ends_at` from Task 3.
- Produces:
  - `EntitlementDisplay.plan_ends_at: Option<String>`, which is None when the field is absent or null
  - `AccountView.plan_ends_at: Option<String>` (RFC 3339)
  - in `account.js`, `formatAccountDate(rfc3339: string): string`, which returns "5 May 2027" (day, full month, year, using the en-GB form). It is used for the licence expiry (today a raw RFC 3339 string), the manifest expiry and the new plan end. When the plan end is present, the plan line reads "Beta until 5 May 2027".

- [ ] **Step 1: Write the failing tests:**
  - **Licensing:** `display_reads_plan_ends_at_when_present`, plus `display_without_plan_ends_at_is_none`. The second is a positive control: an entitlement without the field still verifies (Review Focus 5).
  - **Controller:** `account_view_carries_plan_end`.
  - **Headless:** given a stub account view with `plan_label:"Beta"` and `plan_ends_at:"2027-05-06T00:00:00Z"`, the plan line text is "Beta until 5 May 2027" and the licence expiry shows a formatted date, not RFC 3339. Assert computed visibility.
- [ ] **Step 2: Run** `cargo test -p selahcue-licensing`, `cargo test -p selahcue-operator account`, and `SELAHCUE_HEADLESS_REQUIRE=1 make operator-headless`. Expected: the new checks FAIL. Run `make stage-operator-binaries` first in a fresh worktree.
- [ ] **Step 3: Implement.** The end is midnight UTC on 6 May, which must read as 5 May. Format with `timeZone: "UTC"` and subtract one second from an exclusive midnight end, or format the day before. Pin it in the test.
- [ ] **Step 4: Run** all three, plus `cargo clippy --workspace --all-targets -- -D warnings` and `cargo fmt --check`. Expected: PASS.
- [ ] **Step 5: Commit** `desktop: account setup shows the beta end and readable dates (17tnw2bhkd2)`.

### Task 6: Website Account page on real data

**Files:**
- Modify:
  - `implementation/marketing/src/lib/api/account.ts` (add `ACCOUNT_OVERVIEW` and `accountOverview()` next to `ACCOUNT_VIEWER` :239 / `accountViewer()` :396)
  - `implementation/marketing/src/views/AccountView.vue` (replace the mock data at :65-140 and the tabs at :191-210)
  - `tests/apiSeam.test.ts` (pin the new document)
- Create: `tests/accountView.test.ts`

**Interfaces:**
- Consumes the `accountOverview` fields from Task 4, including `allowance.planEndsAt` and `license.deviceLimit`.
- Produces an `accountOverview(first?: number, after?: string): Promise<AccountOverview>` client that uses `graphqlRequest` (`src/lib/api/graphql.ts:362`) with the relative-import rule at `account.ts:29-32`.
- The page shows only what the API returns:
  - **Overview:** org, display name, email, role
  - **Plan:** plan name, "until 5 May 2027" when `planEndsAt` is set, licence status and expiry
  - **This week:** cloud transcription used and remaining in minutes, notes used and remaining, and the reset date
  - **Devices:** name, last seen, and a deactivate button when `canDeactivateDevices`. It calls the existing `deactivateOwnDevice` mutation and has an in-page confirm step, because `confirm()` is unavailable.
- Remove the mock-only sections: subscription and billing amount, invoices, the fake licence key, and the Bibles tab. Remove the cancel dialog that says "reverts to Free tier".
- Show the loading, error and empty states using the existing view patterns.

- [ ] **Step 1: Write the failing tests:**
  - **`apiSeam.test.ts`:** pins the `ACCOUNT_OVERVIEW` document.
  - **`accountView.test.ts`:** with a mocked `accountOverview` returning Beta, a 10-device limit, 2 devices, 3600 s of STT used and a 10800 s limit, the page shows:
    - "Beta"
    - "until 5 May 2027"
    - "120 min left of 180"
    - both device names
    
    With `planEndsAt: null` and Free, it shows "Free" and no end date.
  - **Error case:** on an API error it shows the error state, with no mock values anywhere. Assert that no "sc_live_", "Pro" or "invoice" text is present.
- [ ] **Step 2: Run** `npm test` in `implementation/marketing`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `make marketing-check`. Expected: PASS.
- [ ] **Step 5: Commit** `marketing: account page on live account data (17tnw2bhkd2)`.

### Task 7: Beta copy replaces the Free offer

**Files:**
- Modify:
  - `implementation/marketing/src/lib/content/freeOffer.ts`. Rename it to `betaOffer.ts` and update every import: `PricingView.vue:5,27-33`, `HomeView.vue:112,138,262,289-290`, `Navbar.vue`, `Footer.vue:33`, `core/CtaBand.vue:23-24`, `VerifyView.vue:227`.
  - Tests: `tests/freeOffer.test.ts` (rename it), `tests/homeView.test.ts:190,513-519,672-689`, `tests/chrome.test.ts`, `tests/core_pages_headless.py:218-222`
- Test: those files

**Interfaces:**
- `betaOffer` exports `endsOn = "5 May 2027"`, `cloudTranscriptionHours = 3`, `sermonNotes = 5`, `devices = 10`, `signupTo = "/signup"`, `downloadTo = "/download#public-downloads"`, `summary` and `afterBeta`.
- Exact copy:
  - **summary:** "The SelahCue public beta is free and includes every feature until 5 May 2027: up to 10 devices, no watermark, and 3 hours of cloud transcription and 5 sermon notes per church each week."
  - **afterBeta:** "After the beta, your church keeps using SelahCue on the Free plan. Paid plans will be announced before the beta ends."
- Pricing h2: "SelahCue Beta".

- [ ] **Step 1: Update the tests** to the exact strings above, including the headless /pricing sentence. Run `npm test`. Expected: FAIL.
- [ ] **Step 2: Implement** the rename and the copy.
- [ ] **Step 3: Run** `make marketing-check` and `npm run test:core`. Expected: PASS.
- [ ] **Step 4: Commit** `marketing: public beta offer copy (17tnw2bhkd2)`.

### Task 8: Record the decision and run the gates

**Files:**
- Modify:
  - `docs/decisions/DECISION-LOG.md`. Add a new DEC entry: the beta is a time-boxed BETA `OrgPlanGrant` for self-service orgs ending at 2027-05-06T00:00Z. FREE stays the fallback. The device limit is effective (licence versus plan). Supersede the W1 "fallback becomes BETA" line.
  - `docs/superpowers/specs/2026-11-19-public-beta-design.md` §W1. Change the end date to 5 May 2027 and the mechanism to the grant. Point to this plan.

- [ ] **Step 1:** Edit both docs and commit `docs: beta licensing decision (17tnw2bhkd2)`.
- [ ] **Step 2:** In the worktree, run `make api-install` and `make marketing-install` once, then `make ci`. Expected: green, apart from any test that also fails on `origin/main` at the same SHA. Name it, and show it failing on main.
- [ ] **Step 3:** On staging, follow the W1 acceptance in the spec:
  1. Sign up, verify the email and activate the desktop app.
  2. Account Setup shows "Beta until 5 May 2027".
  3. Activate a second device; it succeeds.
  4. The website Account page shows Beta, 10 devices and this week's allowance.
  
  Report this as not run if staging isn't deployed.
- [ ] **Step 4:** Push and open a Draft PR against `main` for ClickUp 17tnw2bhkd2.
