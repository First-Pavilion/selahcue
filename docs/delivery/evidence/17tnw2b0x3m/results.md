# Marketing production / CI hardening — 17tnw2b0x3m

Base: `c0325d52e809847fac141a605b74a7e6d7de7021` on main (fresh fetch verified).
Branch: `codex/17tnw2b0x3m-marketing-hardening`. No deployment or registration activation.

## Implemented behavior

- Marketing job has only contents:read and disables persisted checkout credentials.
- `.npmrc` suppresses dependency lifecycle scripts. Explicit npm tasks remain enabled.
- Unsuppressed `npm audit --audit-level=high` rejects high/critical findings and registry errors; no overrides or advisory waivers.
- Supported Node 22 builder matches CI. Actual production build exposed preexisting TS2307: PilotPrivacyView imported canonical notice.json outside the old marketing context. Kept the reviewed notice/import unchanged, corrected compose/CI build context, copied only explicit required files. Dockerfile-specific ignore denies unrelated repository contents and credentials/local caches.
- Enforced CSP denies inline scripts/styles, eval, objects, foreign connections/forms/frames. Shared header include preserves headers on immutable assets and errors despite nginx add_header inheritance.
- Preserve existing fonts and privacy disclosure via exact Google stylesheet/font hosts. Self-hosting considered and deferred pending verified font artifact/licensing and coordinated disclosure update. Existing desktop Inter-named assets carry a Noto license attribution, so they were not reused blindly.
- Repository-wide Actions SHA pinning belongs to separate ticket 17tnw2b1wx5. Existing action versions, visual/installer/NDI controls and 15-minute timeout preserved. Public-repository workflow comments corrected.

## Verification environment

Local Node v26.7.0/npm11.19.0; shipping Docker build runs actual Node22-alpine. Python3.14.5, pinned Django6.1.2/PyYAML6.0.3, Playwright1.60.0 (Chromium148 and WebKit), Docker29.8.0. Both actual browser engines ran against built production nginx on loopback, not Vite preview. Only GraphQL data was stubbed; real Google stylesheet/font HTTP responses were verified. No live account, registration or collection request.

| Check | Actual result |
|---|---|
| New focused regression tests before implementation | exit1, 3 failing hardening cases |
| Final focused hardening tests | exit0, 4 passing cases |
| Fresh npm ci --ignore-scripts | exit0, 188 packages installed |
| npm audit --audit-level=high, real registry | exit0, 0 high/critical; 13 moderate package nodes |
| Same audit threshold, local synthetic high advisory fixture | exit1, 13 high package nodes; expected refusal |
| make marketing-check | exit0, type-check/lint/build and 1250 tests pass |
| docker build --pull -f implementation/marketing/Dockerfile .; nginx -t | both exit0, real Node22 build and nginx1.31.8 image/config |
| Production CSP browser gate | exit0, Chromium68 + WebKit68 routes, fonts/auth/mobile/header/error and blocked-inline-script probes |
| Client/server mirrors | exit0, 6453 generated email addresses agree with pinned Django |
| Shared components both engines | exit0, 646 checks |
| Core pages both engines + frame regression | exit0, exact geometry /20 nominal widths/20 overflow negatives |
| Home both engines | exit0, 260 checks |
| Secondary pages both engines | exit0, 362 checks |
| Responsive Chromium | exit0, 2363 checks, 41 routes ×5 widths |
| Final sequential auth states | exit0, 77 scenarios /2765 checks /0 FAIL |
| Final sequential responsive WebKit | exit0, 2363 checks /41 routes ×5 widths /0 failed |
| actionlint .github/workflows/ci.yml | exit0 |
| check_workflows.py --self-test / normal | both exit0, 118 self-tests and6 workflows/19 jobs |
| check_ci_minutes.py --self-test / normal | both exit0; runner/matrix/alarm controls preserved |
| py_compile production harness; git diff --check | both exit0 |

`production-csp.txt` and `audit-summary.json` retain compact actual output. Full local verifier logs are `/tmp/selahcue-marketing-*.log` for independent review.

The initial parallel browser run let a rebuilding suite remove dist while auth/WebKit responsive were reading it. Those attempts are invalidated; affected auth process was explicitly terminated (143) and reaped. Final affected checks run sequentially against stable dist; no result is inferred from launch or output alone.

## Policy sources

- [Node release schedule](https://github.com/nodejs/Release#release-schedule): Node20 EOL and Node22 supported line.
- [npm configuration](https://docs.npmjs.com/cli/using-npm/config/): ignore-scripts and explicit npm run semantics.
- [nginx header module](https://nginx.org/en/docs/http/ngx_http_headers_module.html): add_header inheritance and always behavior.
- [CSP style-src-attr](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src-attr): attribute restrictions and direct style property behavior.
- [Docker build context](https://docs.docker.com/build/concepts/context/): Dockerfile-specific ignore precedence and context exclusion.

## Remaining gate

Root must obtain independent Cody, Shadow, Quinn and Vera PASS verdicts on the final head, real GitHub CI success and fresh-main integration before merge. Ticket moves to QA only after confirmed merge on main. This implementation has no self-approval or deployment claim.

Final affected browser checks both finished exit0; no verifier process remains running.
A separate existing Linux WebKit Home harness issue was diagnosed from PR350 CI:
outer viewport1440 has document client1428 due external12px scrollbar. Home's nominal
Figma measurement lacks Core/Secondary's measured frame compensation. Local macOS
Home260 checks pass; actual Linux CI remains an independent gate, with a separate
minimal harness-fix ticket/PR owned by root/Diego. No product CSS or geometry tolerances
were changed or waived in this hardening ticket.

## Review remediation — iteration4

All four first-round reviews of f76e6a9f identified one root cause: the downstream notice JSON area filter could not run because both top-level events excluded docs/**. The active ticket remained In Progress; root posted the consolidated review and remediation start via authenticated ClickUp UI after connector quota exhaustion.

The regression was added first: the real checker exited1 naming push and the canonical notice. Both event lists now re-include only `docs/release/pilot-registration/notice.json` after their exclusions. The existing checker explicitly recognizes that path and preserves its original20 cases, adding8 cases across push/PR: the notice is included; neighboring markdown, other JSON and a notice backup remain excluded. The complete28-case check passes. In scratch copies, removing either exception makes the actual CLI exit1 naming the corresponding event and notice; compact receipts are in `trigger-mutations.json`. These verify committed ordered configuration, not delivery of a synthetic GitHub event.

Final focused rerun: `npm test`1250 pass/0 fail; workflow118 self-tests and6workflow/19job normal checks; minute self-test/rules; actionlint; shared visual/audit check,28 path cases and browser wiring all exit0. Shared visual gate measured3.968s, below its unchanged10-second cap. Each exit is captured individually under `verifier-status.json` review-remediation. Initial sandbox runs could not open the visual test's loopback listener or write Vite's managed-worktree temporary config (two npm tests); these are explicitly failed attempts. Scoped permission reruns completed all checks successfully.

This correction changes only workflow event routing, its ordered-path regression data and execution evidence. Product source, Docker context/configuration, CSP, fonts, test geometry and browser suites are byte-unchanged from f76e6a9f. Retain that revision's actual author and independent production/browser evidence for those unchanged paths; no new browser execution is claimed here. Root confirmed that revision's hosted marketing job126339030128 succeeded at02:15:40UTC with production build/CSP step02:13:13–02:15:38 (145s), within the unchanged15-minute job budget. Corrected-head CI and four refreshed reviews remain required before merge.
