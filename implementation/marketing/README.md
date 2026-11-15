# SelahCue marketing site and customer portal

The public website (`/`, `/features`, `/pricing`, `/download`, ...) and the customer account
pages (sign up, sign in, verify, reset, `/account`). A Vue 3 + TypeScript + Vite single-page
app using `vue-router` in history mode. It builds to static files served by nginx (see
`Dockerfile` and `nginx.conf`).

## Commands

Run from `implementation/marketing`. Run `npm ci` first. Use Node 22.18 or newer (`package.json` says so
in `engines`): `npm test` runs `.ts` files directly, and Node only strips types by default from 22.18.0.
CI runs Node 22.

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server on port 2000. The port matters: emails the API sends link to `http://localhost:2000`. |
| `npm run build` | `type-check`, then the production build into `dist/`. |
| `npm run type-check` | `vue-tsc --build`. Covers `src/`, `vite.config.ts` and the two legal scripts, `scripts/legal_markdown.ts` and `scripts/sync_legal.ts`. |
| `npm run lint` | ESLint with `--max-warnings 0`, so a warning fails it. Config: `eslint.config.js`. |
| `npm test` | Node's built-in test runner over `tests/*.test.ts`. |
| `npm run test:states` | Builds, then drives the real bundle in headless Chrome and checks every auth page state. Skips with a loud message when Chrome is missing, unless `SELAHCUE_HEADLESS_REQUIRE=1`. |
| `npm run sync:legal` | Regenerates `src/lib/legal/*.generated.ts` from the legal drafts in `docs/legal`. See Legal pages below. |
| `npm run check:legal` | Fails (exit 1) if the generated legal files differ from what `sync:legal` would write; exit 2 means it could not run. Not part of `make marketing-check`; the `legal-drift` workflow runs it. |
| `npm run test:legal-pages` | Builds, then drives `/privacy` and `/terms` in real Chrome at five widths. Needs `pip install playwright` and a Chromium. |
| `npm run test:mirrors` | Re-derives the client's whitespace and email rules from CPython and the Django the API pins, and fails on drift. Needs that Django installed. |

From the repository root:

- `make marketing-install` runs `npm ci`. Needed once per clone or worktree, and after the lockfile changes.
- `make marketing-check` runs `type-check`, `lint`, `npm test` and `build`. It does not install anything, and refuses to run against a missing or stale `node_modules`.
- `make ci` runs `marketing-check`, and the `marketing (vue spa)` job in `.github/workflows/ci.yml` runs the same target, so the two cannot drift.
- `test:mirrors` and `test:states` run in CI only, because they need Django and Chrome. `check:legal` and `test:legal-pages` run in the separate `legal-drift` workflow (`.github/workflows/legal-drift.yml`), not in `marketing-check`.

### Home Figma layout viewport regression (17tnw2bcadw)

`npm run test:home` retains all130 strict checks per engine. Only its explicit1440px
Figma measurement uses Core's existing measured `fit_figma_frame`; nominal responsive
requests remain exact. Horizontal overflow compares real document scrollWidth/clientWidth,
because innerWidth may include external scrollbar chrome.

The required both-engine Home gate automatically runs `tests/home_frame_regression.py` with a
120-second bound. It verifies zero-gap behavior, eight unchanged strict width assertions,
12px simulated external window chrome (plus any host-native scrollbar), exact nominal
320/375/768/1024/1440 requests, five zero-overflow controls and15 genuine1px/12px/24px
overflow rejections through the normal Home assertion path. It never changes product CSS
or fakes document clientWidth/scrollWidth. Run it directly after a production build with
`python3 tests/home_frame_regression.py` from `implementation/marketing` using the pinned
Playwright Chromium and WebKit engines. Hosted Linux CI remains required evidence.

## Routes

Defined in `src/router/index.ts`; every page except the home page is lazy-loaded.

- Marketing: `/`, `/features`, `/pricing`, `/download`, `/about`, `/contact`, `/support`, `/docs`, `/changelog`, `/blog`, `/careers`, `/privacy`, `/terms`.
- Auth, with no site nav or footer (`meta.bare`): `/signin`, `/signup`, `/forgot-password`, `/verify`, `/reset`. The last two are linked from emails that are already delivered, so their paths must not change.
- Account: `/account`, behind a guard that asks the server whether the session is live. The guard is a convenience, not a security boundary; the API authorises every request.
- `/affiliates` describes the closed affiliate program. Former staff and affiliate portal paths resolve to the public not-found view.
- Anything else renders `NotFoundView`.

## How it talks to the API

Only the auth and session code calls the API (sign-up, sign-in, forgot-password, verify, reset, sign-out and the `/account` session check). It does so through one
place, `src/lib/api/graphql.ts`, with typed wrappers in `src/lib/api/account.ts`.

- Requests go to a relative `/graphql/account` (and `/graphql/csrf` to seed the CSRF cookie), so the site is same-origin with the API. `vite.config.ts` proxies `/graphql` to `SELAHCUE_API_ORIGIN` (default `http://localhost:8008`) in development, and `nginx.conf` proxies it to the `api` service in production.
- Same-origin is deliberate: the API sends no CORS headers, its session cookie is `SameSite=Strict`, and Django checks the request origin. Leave `VITE_API_BASE_URL` unset unless all three are solved first. See `.env.example`.
- The API returns errors with HTTP 200, so the seam reads the response body, not the status.

## Legal pages (`/privacy`, `/terms`)

The Privacy Policy and Terms of Service are **not written in this package**. The source of truth is
`docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md` and `docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md`.
`scripts/sync_legal.ts` turns them into typed content in `src/lib/legal/*.generated.ts` (committed, because
the Docker build context is this folder only and cannot read `docs/`). The pages render that content with
templates only (no `v-html`).

- **After editing a draft in `docs/legal`, run `npm run sync:legal` and commit the regenerated files.**
  `npm run check:legal` reports whether they are in step (exit 0 ok, 1 stale, 2 could not run).
  The `legal-drift` workflow runs it on every change to `docs/legal/**`, because `ci.yml` ignores docs.
- The generator **throws, naming file and line, on any markdown it does not support** instead of dropping
  it. It understands headings, numbered clauses (`3.8 ...`), `-` lists, tables, bold, inline code, safe
  links and the DRAFT blockquote; see the header of `scripts/legal_markdown.ts`.
- **A draft fails closed.** A page shows the draft banner, highlights placeholders and sends `noindex`
  while ANY of these holds: a `{{PLACEHOLDER}}` remains, the document still has its DRAFT banner, or its
  version status is anything other than exactly `final` (so `final draft`, `pending review` or a typo stay drafts). Filling every placeholder is not publishing.
- **To publish** (only once the launch-readiness conditions in `docs/legal/LEGAL-DRAFT-NOTES.md`
  section 4 are met): in the markdown, delete the DRAFT `>` banner, make sure a
  `Version X.Y (final, YYYY-MM-DD).` paragraph sits directly under the `#` title (generation fails if there
  is no version line, so "Last updated" cannot silently disappear), and fill every placeholder; then run
  `npm run sync:legal`. No code changes.
- Tests: `npm test` (content pipeline, drift, rendering). `npm run test:legal-pages` builds the site and
  drives `/privacy` and `/terms` in real Chrome at five widths (needs `pip install playwright`).

## Known gaps

- **Mock data.** `/account` (past the session guard) still renders hard-coded sample data pending the account API integration.
- **`tests/` and `scripts/email_mirror_probe.ts` are linted but not type-checked.** `tsconfig.node.json` lists only `vite.config.ts` and the two legal scripts, `scripts/legal_markdown.ts` and `scripts/sync_legal.ts`, so `npm run type-check` covers those and nothing else under `scripts/`. Checking `tests/` by hand with `tsc --strict` shows type errors in `tests/authCopy.test.ts` that no gate reports today.
- **Lint covers error prevention only.** It uses the `essential` tier of `eslint-plugin-vue` and has no formatter. The style tiers flagged about 1,300 existing sites and were left out on purpose.
- **Node versions differ.** The `Dockerfile` builds on `node:20-alpine`, while CI and the tests use Node 22.

## Public desktop download configuration

The public download section at `/download#public-downloads` revalidates the same-origin
`/releases/current.json` manifest. It omits credentials, rejects redirects, and uses a
five-second timeout and 64 KiB limit. The source file `public/releases/current.json`
ships with this inventory:

```json
{"schema_version":1,"status":"unpublished","artifacts":[]}
```

For publication, the release operator sets `status` to `published`, supplies the
`release_id`, `version` and 40-digit lowercase hex `source_commit`, and supplies exactly
one artifact each for `windows-x64`, `macos-arm64`, `macos-x64` and `ubuntu-24.04-x64`.
Each artifact requires `target`, verified `architectures`, `url`, `filename`, positive
integer `size_bytes`, lowercase 64-digit `sha256`, `app_signature`, `package_signature`,
`notarization` and `publisher`. See `src/lib/releases/downloads.ts` for allowed states.
The selected macOS package has an ad hoc app signature, an unsigned DMG and no
notarization. A shared macOS object must contain both verified architecture slices
and carry matching metadata on its two records.

Copy the HTTPS object URLs and safe basenames from the release receipts. The host
is `selahcue-installers.sfo3.digitaloceanspaces.com` and the immutable object keys
contain the recorded version and SHA-256 as complete path segments. Keep the
manifest unpublished until the operator verifies receipt provenance and independently
checks the uploaded bytes, checksum, signing state, and attachment disposition and
filename on the actual objects. Serve `/releases/current.json` with cache revalidation
separately from the immutable hashed SPA assets.

Verification from this folder:

```sh
node --test tests/publicDownloads.test.ts tests/downloadView.test.ts tests/corePages.test.ts
npm run build
python3 tests/public_downloads_headless.py --engine both
```

The browser check uses the built site, installed Playwright Chromium and WebKit, and
synthetic fixtures for publication and installer navigation.

## Archived pilot notice and tooling

`/pilot-privacy` displays the historical notice from
`docs/release/pilot-registration/notice.json`. Keep the source and its Docker
copy together. The public site no longer collects pilot registrations.
Bookmarks to `/download#pilot-downloads` open the public installer section.

The pilot registration component, its fixtures and
`public/pilot-downloads.json` are retained as historical tooling. The
committed configuration stays disabled (`{"schema_version":1,"enabled":false}`).
The public installer cards use only `/releases/current.json`.

### Production security gate (17tnw2b0x3m)

Marketing CI runs with `contents: read`, disables checkout credential persistence, and
uses `.npmrc` to disable dependency lifecycle hooks. Explicit `npm run` tasks still run;
a fresh script-free install, type-check, lint, tests and both production builds verify
that this lockfile does not require install hooks. `npm audit --audit-level=high` is a
required, unsuppressed gate over development and production dependencies. Registry or
request failures also fail CI. The current lock has a moderate minimatch glob-amplification
advisory (GHSA-g3hv-75wg-m249) propagated through the eslint toolchain; no advisory is
waived and no forced major downgrade is applied.

The image matches CI's supported Node 22 line. Build from repository root:

```sh
docker build --pull -f implementation/marketing/Dockerfile -t selahcue-marketing .
docker run --rm -p 127.0.0.1:4188:80 selahcue-marketing
# In another terminal with the pinned CI Playwright browsers installed:
python3 implementation/marketing/scripts/security_headers_headless.py --base-url http://127.0.0.1:4188
```

The repository context is needed for the existing canonical public pilot notice import.
`Dockerfile.dockerignore` denies everything except explicit marketing source/configuration
and that notice. Compose uses the same context. No notice contents or collection policy
change as part of this ticket.

nginx repeats the identical CSP/security directives directly in the server and asset
location, applying them to documents, immutable assets and error responses. No server
include hides directives from the existing forwarded-proto trust guard. Scripts and API
connections stay same-origin; inline scripts, inline style
attributes, eval, plugins, foreign frames and foreign form submissions are prohibited.
Google Fonts remains an explicit exception for stylesheet/font hosts only, matching the
existing Inter delivery and privacy disclosure. Self-hosting was considered and deferred:
changing the font supply and its legal disclosure would require separately verified font
artifacts/licensing. The browser gate fetches real fonts, visits every static route and
published article, exercises auth submission/mobile menu styles, checks header inheritance,
and proves an injected inline script cannot execute. Missing browsers or external font
failures fail this gate; fonts are never aborted or replaced by fixtures. API responses
use synthetic data and no live account is contacted.

Actions SHA pinning is deferred to its dedicated delivery ticket `17tnw2b1wx5`, which
covers the repository consistently. This change preserves the current action versions,
existing visual/installer/NDI controls and the marketing job's 15-minute timeout.
