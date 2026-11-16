# Free public website integration evidence

Source candidate `f097d38bfe3b47077e122dbd5490dbe8dcf279b7`, based on `45d7c89e63bc4c3e954d3b2a50c262676e0a0a98`. Independent review and hosted CI are pending for this candidate. The committed and built installer manifests are unpublished.

## Source verification

Commands ran from `implementation/marketing` on macOS arm64 with Node 22.23.4 and npm 10.9.9 using the installed worktree dependencies.

| Command | Result |
| --- | --- |
| `npm run check:legal` | Exit 0. Both checked-in generated pages match the owning drafts. |
| `node --test --test-concurrency=1 "tests/*.test.ts"` | Exit 0. 1,329 passed, zero failed or skipped. |
| `npm run type-check` | Exit 0. |
| `npm run lint` | Exit 0 with the zero-warning ESLint limit. |
| `npm run build` | Exit 0. Vite transformed 255 modules. Built `index.html` SHA-256 `e9674d15d04c9e055506090ed65112d6b8a1e9d44e604c68843dd7e252afe09d`. |
| `actionlint .github/workflows/ci.yml` | Exit 0 with actionlint 1.7.12. |
| `python3 .github/scripts/check_workflows.py --self-test` and `python3 .github/scripts/check_workflows.py` | Exit 0. 118 legacy cases, 39 cache CLI fixtures and 21 jobs across seven workflows. |
| `python3 .github/scripts/check_installer_scanner_ci.py` | Exit 0. Existing installer workflow controls passed. |

The responsive test now compares the registered route paths and explicit sample URLs with the full sweep inventory. The 15 former-portal probes remain deliberate catch-all checks. Removing an excluded URL in an isolated fixture failed the guard. Six HomeIcon negative renders each assert their exact Vue validator warning in that render's app context.

The inherited auth states run reached 78 scenarios and 2,816 checks with zero behavioral failures and **exited 4**. The verified state lost one assertion for superseded banner copy, with the body and CTA checks replaced one-for-one. The title, offline banner, success glyph, alignment, focus and shared checks remain. The guard still requires exact equality, now at the previously measured 2,816. The current source needs the hosted Chrome rerun.

The API contract test failed on the exact integrated base because the shared server enum gained 11 codes emitted by the native device-token STT session command. The test now asserts the existing browser `UNKNOWN` fallback for those named native-only codes and exact round-tripping for the other server codes. A planted unclassified code failed the revised guard. Production API and browser client code were outside this correction.

## Hosted browser checks

Local browser and container runs were held during sustained host paging. The existing 25-minute marketing CI job retains its original engines, permissions and requirements. The following steps use the production `dist/` and already installed Playwright browsers.

| Required hosted check | Coverage to verify |
| --- | --- |
| `npm run test:states` under `SELAHCUE_HEADLESS_REQUIRE=1` | Chrome, 78 scenarios and exactly 2,816 checks, including verification, resend, reset, account, signup and session fixtures. |
| Existing Responsive, Shared, Core, Home, Secondary and production-header suites | Chromium and WebKit. Secondary records focus, `:focus-visible` matching and activation. WebKit forced-colors remains unsupported. |
| `python3 scripts/legal_pages_headless.py --only all` under `SELAHCUE_HEADLESS_REQUIRE=1` | Full Chromium legal suite, including all pages, anchors and navigation. The separate legal workflow still handles legal-only document changes. |
| `python3 tests/public_routes_headless.py --engine both` | Chromium and WebKit. Desktop/mobile keyboard navbar, legacy download fragment, 19 former portal paths, signup and synthetic verification. |
| `python3 tests/public_downloads_headless.py --engine both` | Chromium and WebKit. Archived pilot notice, unpublished and failing manifests, two consecutive failed Enter retries with retained focus, successful retry, four synthetic artifact links and metadata, four viewport sizes, and no unexpected requests or session credentials. |

## Release readiness

| Area | Current evidence and outstanding acceptance |
| --- | --- |
| Website source | Local source checks passed. Independent review and exact-candidate hosted browser results remain pending. |
| Installer manifest and publication | The committed payload is unpublished with an empty artifact array. Release operations need accepted Windows x64, macOS arm64 and x64, and Ubuntu 24.04 x64 packages. Retain the release version, source SHA, exact filename, immutable Spaces URL, bytes, SHA-256, signature and notarization receipts as applicable. A shared macOS package requires proof of both architecture slices. |
| Anonymous downloads | Synthetic navigations exercise the approved URL contract. After publication and owner manual deployment, verify public-read access, attachment headers and an anonymous browser download of each complete artifact from the homepage or navbar. Compare received bytes and SHA-256 with retained build receipts. Exercise unpublished/fetch-failure behavior, keyboard and mobile layout, disclosures, the legacy anchor and excluded URLs. |
| Self-service lifecycle | Verify deployed signup, verification, resend, reset, native sign-in and activation, Free licence and cloud readiness without operator approval. Browser account traffic remains same-origin and native uses `https://api.selahcueapp.com`. Exact DNS, TLS, origin/cookie/CSRF and email delivery are still pending deployment evidence. |
| Account data and native acceptance | Backend Task 8 owns real AccountView licence, device, quota and deactivation behavior. Native owners supply activation, supported packaging/signing, installer and platform acceptance receipts. |
| Cloud transcription and notes | Ongoing Free has 20 cloud transcription minutes and one sermon note per church per week. Production Deepgram consent, direct-audio routing and allowance behavior require receipts. The C server worker notes path still needs quality/budget and native save/ACK qualification. |
| Legal publication | Draft markers, noindex and outstanding factual placeholders stay in place. Terms 17.3 tracks the drafted US$25,000 floor. Terms 22 tracks drafted Nigerian law and the courts of Abeokuta, Ogun State, Nigeria. Owner and counsel review remains pending. Resolve operating facts, retention, processor use, rights requests, final version and acceptance before publishing signup documents. |
| Ingress and log privacy | Task 5's isolated nginx run covered normalized access records, token landing/error privacy and a standalone same-origin proxy fixture. After manual Coolify deployment, verify router precedence, forwarded metadata, actual Django acceptance and synthetic token absence across nginx, Coolify, API/error and email logs. |

Only accepted publisher receipts can populate `public/releases/current.json`. Final launch also requires the deployed lifecycle, cloud, platform and legal acceptance above.
