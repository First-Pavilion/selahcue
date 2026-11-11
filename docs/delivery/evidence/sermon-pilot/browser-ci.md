# Required browser CI: Ubuntu 26 compatibility

Ticket: [17tnw2beykq](https://app.clickup.com/t/17tnw2beykq). Evidence recorded 2026-11-11.

## Failure and selected release

The pre-change [CI run 43008461665](https://github.com/First-Pavilion/selahcue/actions/runs/43008461665), head `62c9e1ea`, used Ubuntu 26.04 image `20261101.186`. The marketing job `130481899591` rejected installation with `ERROR: Playwright does not support chromium on ubuntu26.04-x64`; the operator job `130481899556` also failed WebKit installation. The original marketing log is retained locally at `/private/tmp/sqlite-native-marketing-failure.log`. Subsequent missing-browser failures were required-gate failures, not successful browser coverage.

Select exact Python package **`playwright==1.61.0`**: the first stable release in the minor line whose [official Python release notes](https://playwright.dev/python/docs/release-notes#version-161) introduce Ubuntu 26.04 support. The [published PyPI 1.61.0 metadata](https://pypi.org/pypi/playwright/1.61.0/json) confirms version `1.61.0`, not yanked, Python `>=3.10`, and a Linux x86-64 wheel uploaded `2026-06-29T10:32:59.903990Z`. This is the smallest supported minor update from `1.60.0`, rather than a floating latest release.

The [tagged 1.61.0 browser manifest](https://github.com/microsoft/playwright/blob/v1.61.0/packages/playwright-core/browsers.json) and release notes identify the intended bundled browsers:

| Required engine | Version | Playwright revision |
| --- | --- | --- |
| Chromium and Chromium headless shell | 149.0.7827.55 | 1228 |
| WebKit | 26.5 | 2311 |

These are package/source identities, not browser versions observed in a new Ubuntu run. The [tagged download registry](https://github.com/microsoft/playwright/blob/v1.61.0/packages/playwright-core/src/server/registry/index.ts) includes Ubuntu 26.04 download entries for Chromium, its headless shell and WebKit.

## Change and regression coverage

All three existing Python Playwright installations now pin `1.61.0`: operator WebKit and marketing Chromium/WebKit in `ci.yml`, and legal-drift Chromium. Existing pip options, `--with-deps`, engines, required-run flags, failure propagation, runner policy, shipping-image CSP checks and visual/content assertions are retained. No production dependencies or visual baselines changed.

The existing legal workflow contract had allowed operator and marketing to pin different versions as long as legal-drift matched either one. Its version-independent assertions now require exactly two CI pins sharing one version, legal-drift parity, and pinned pip installation lines in both workflows. With only the operator pin updated, the contract failed as intended (`2 !== 1`, eight passed/one failed). After updating the remaining pins, all nine focused tests passed.

## Local verification

Host: macOS 26.3 / arm64; Node `v22.23.4`; validation interpreter Python 3.14. Local execution does not establish Ubuntu 26 browser installation.

| Command | Observed result |
| --- | --- |
| `node --test implementation/marketing/tests/legalWorkflow.test.ts` | 9 passed, 0 failed/skipped after coordinated update |
| `python3.14 .github/scripts/check_workflows.py --self-test` | 118 legacy cases; 39 cache CLI fixtures; 0 fixture failure diagnostics |
| `python3.14 .github/scripts/check_workflows.py` | 7 workflows / 21 jobs OK |
| `python3.14 .github/scripts/check_ci_minutes.py --self-test` | All cases passed |
| `python3.14 .github/scripts/check_ci_minutes.py` | 7 workflows OK; existing runner policy retained |
| `actionlint` | Exit 0, no diagnostics |
| `make marketing-install` | Exit 0; 188 packages installed from existing lockfile |
| `make marketing-check` | Exit 0: type-check, lint, all 1,250 Node tests in 250 suites, production build; 0 failures/skips |
| `git diff --check` | Exit 0 |

The full marketing-gate log is retained locally at `/private/tmp/sermon-pilot-browser-marketing-check.log`. Node emitted its MockTimers experimental warning and the malformed-URL fixture emitted Vue Router decoding diagnostics; the suite still reported zero failures. Installation reported 11 moderate npm audit findings in the existing dependency tree; no dependency remediation is part of this pin change.

## Required hosted evidence remains pending

The implementation handoff has **not** executed new browser suites on Ubuntu 26.04. No local browser suite, full cross-platform `make ci`, shipping-container CSP run or hosted check is claimed here. The controller must attach run/head and runner-image evidence from the reviewed commit, actual installed browser versions, suite counts and any failures for:

- Operator required WebKit installation and smoke (`SELAHCUE_WEBKIT_REQUIRE=1`).
- Marketing Chromium/WebKit installation, both responsive sweeps, shared components/menu, core, home and secondary page suites, with their existing required flags.
- Marketing shipping-image security-header/CSP checks in both engines.
- Legal-drift Chromium installation and required legal-page browser check.

A hosted installation or geometry/content/CSP failure remains an unresolved gate; do not adjust baselines merely to turn it green. Independent review and hosted verification are controller-owned follow-up work. This evidence establishes a scoped source correction and local checks, not merge, release or QA completion.
