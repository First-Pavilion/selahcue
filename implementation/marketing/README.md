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
- Affiliates: `/affiliates` (marketing) and `/affiliates/{dashboard,referrals,payouts,resources,settings,help}` (portal).
- Staff admin console: `/admin` and `/admin/{customers,customers/:id,users,subscriptions,licenses,affiliates,payouts,settings}`.
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

- **Standard downloads do not exist yet.** `/download` shows the Windows and macOS buttons and the App Store and Google Play badges as disabled, because no installer is served and the downloads backend is not built (ClickUp `86ak10afm`; both endpoints return 501). Store publishing is separate open work (`86ajxz3nj`). Wire these up when those land.
- **Mock data.** `/account` (past the session guard), the affiliate portal and the admin console render hard-coded sample data. The affiliate portal and admin console have no route guard at all, so treat them as unfinished, not as secured.
- **`tests/` and `scripts/email_mirror_probe.ts` are linted but not type-checked.** `tsconfig.node.json` lists only `vite.config.ts` and the two legal scripts, `scripts/legal_markdown.ts` and `scripts/sync_legal.ts`, so `npm run type-check` covers those and nothing else under `scripts/`. Checking `tests/` by hand with `tsc --strict` shows type errors in `tests/authCopy.test.ts` that no gate reports today.
- **Lint covers error prevention only.** It uses the `essential` tier of `eslint-plugin-vue` and has no formatter. The style tiers flagged about 1,300 existing sites and were left out on purpose.
- **Node versions differ.** The `Dockerfile` builds on `node:20-alpine`, while CI and the tests use Node 22.

## Pilot registration journey (P14, 17tnw2bbhxu)

Shared Home/nav/footer download links reach `/download#pilot-downloads`. The pilot panel is separate
from the existing disabled standard/licensed download buttons (`86ak11rt1`). It does not call the licensed
account API, accept a receipt in the URL, store personal/church details, or expose an installer URL.

`public/pilot-downloads.json` is nonsecret, same-origin deployment configuration, fetched without cookies
or caching, with a 10-second timeout and 32-KiB body limit. The committed deployment is deliberately:

```json
{"schema_version":1,"enabled":false}
```

Missing/invalid/unavailable configuration keeps registration closed and offers retry on fetch errors.
Enable only after actual artifacts, P12 grants, deployed n8n form and approved collection policy are ready.
The owner selected a six-month pilot ending **2027-04-30T23:59:59Z**; release manifest expiry remains the
source of truth. Do not turn fixture metadata into a published release or infer data retention from the
six-month credential lifetime. Actual data owner/retention and notice approval are still external decisions.

Enabled schema (every listed field is required; unknown fields rejected):

- `schema_version`: integer `1`; `enabled`: boolean `true`.
- `form_origin`: exact HTTPS origin of the deployed production n8n form, without credentials/query/fragment.
- `notice`: `approved: true`, approved non-draft `version`, HTTPS `url`, public `data_owner` label and
  positive integer `retention_days` (max3650). This public declaration is deployment input; it cannot
  establish legal approval by itself. Confirm approval before publishing it.
- `entries`: up to six unique OS/architecture targets. Each has exact `platform` (`Windows`, `Ubuntu`,
  `macOS`), `architecture` (`x64`, `arm64`), nonempty `version` and `release_id`, strict UTC `expires_at`
  (`YYYY-MM-DDTHH:mm:ssZ`), boolean `available`, and complete opaque HTTPS `registration_url`.
  Omit absent artifacts; mark present unavailable targets `available:false`. No sizes/OS floors inferred.
- `registration_url`: actual production n8n `/form/<slug-or-webhook-id>` on `form_origin`; query-free,
  no fragment or embedded credentials. Provision the correct form per artifact/release; the frontend
  never invents route names, architecture/release query fields, grants or object paths.

The panel appends only non-PII `registration_id` (crypto UUIDv4) and allowlisted `platform` query fields.
The UUID persists in sessionStorage per platform/architecture/release/form attempt across re-click,
reload and return navigation. Selecting another target has its own attempt; selecting the original target
restores its identity. Only the explicitly labelled new-registration action replaces an existing identity.
Storage failure/corruption fails closed; no new UUID silently replaces an ambiguous attempt. A new browser
session/tab may be a distinct attempt; sessionStorage is not a cross-device deduplication guarantee.

The UUID and platform are **untrusted inputs, not authorization**. The backend must bind identity/payload
and reject conflicts. n8n must reserve/reuse the durable row, write Sheets with RAW values, reconcile ambiguous
writes and issue a server receipt only after confirmed persistence; P12 validates it and grants only an
allowlisted available unexpired private artifact. Form-side retries preserve the UUID and unchanged payload.
The site offers no fake success/download step while these services remain unconfigured.

Official [n8n Form Trigger documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.formtrigger/)
confirms query prefill/Hidden Fields operate on **production URLs**, not Test URLs; nodev2.2 custom paths live
at `parameters.options.path`. Actual pinned n8n import/runtime field mapping is a separate P13 gate.
The form must validate/bind the requested target server-side; editing a hidden field cannot grant access.

Verification from this folder:

```sh
node --test tests/pilotDownloads.test.ts
npm test
npm run build
npm run lint
python3 tests/pilot_downloads_headless.py --shots /private/tmp/pilot-shots
```

The runtime harness requires installed Playwright Chromium **and** WebKit, serves the actual built Vue bundle,
and intercepts config/form responses with synthetic fixtures only. It covers selection, keyboard navigation,
retry identity/reset, unavailable/expired/policy/error/storage states and320/375/768/1440px widths. Ready screenshot
metadata is synthetic, not a real package/retention claim. No live registration, Sheet write, provider request
or installer download occurs. Native installer/platform acceptance belongs to separate QA tickets.
