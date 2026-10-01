# SelahCue marketing site and customer portal

The public website (`/`, `/features`, `/pricing`, `/download`, ...) and the customer account
pages (sign up, sign in, verify, reset, `/account`). A Vue 3 + TypeScript + Vite single-page
app using `vue-router` in history mode. It builds to static files served by nginx (see
`Dockerfile` and `nginx.conf`).

## Commands

Run from `implementation/marketing`. Run `npm ci` first. Use Node 22 or newer: CI runs 22, and
`npm test` relies on Node's built-in TypeScript stripping.

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server on port 2000. The port matters: emails the API sends link to `http://localhost:2000`. |
| `npm run build` | `type-check`, then the production build into `dist/`. |
| `npm run type-check` | `vue-tsc --build`. Covers `src/` and `vite.config.ts`. |
| `npm run lint` | ESLint with `--max-warnings 0`, so a warning fails it. Config: `eslint.config.js`. |
| `npm test` | Node's built-in test runner over `tests/*.test.ts`. |
| `npm run test:states` | Builds, then drives the real bundle in headless Chrome and checks every auth page state. Skips with a loud message when Chrome is missing, unless `SELAHCUE_HEADLESS_REQUIRE=1`. |
| `npm run test:mirrors` | Re-derives the client's whitespace and email rules from CPython and the Django the API pins, and fails on drift. Needs that Django installed. |

From the repository root:

- `make marketing-install` runs `npm ci`. Needed once per clone or worktree, and after the lockfile changes.
- `make marketing-check` runs `type-check`, `lint`, `npm test` and `build`. It does not install anything, and refuses to run against a missing or stale `node_modules`.
- `make ci` runs `marketing-check`, and the `marketing (vue spa)` job in `.github/workflows/ci.yml` runs the same target, so the two cannot drift.
- `test:mirrors` and `test:states` run in CI only, because they need Django and Chrome.

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

## Known gaps

- **Downloads do not exist yet.** `/download` shows the Windows and macOS buttons and the App Store and Google Play badges as disabled, because no installer is served and the downloads backend is not built (ClickUp `86ak10afm`; both endpoints return 501). Store publishing is separate open work (`86ajxz3nj`). Wire these up when those land.
- **Mock data.** `/account` (past the session guard), the affiliate portal and the admin console render hard-coded sample data. The affiliate portal and admin console have no route guard at all, so treat them as unfinished, not as secured.
- **`tests/` and `scripts/*.ts` are linted but not type-checked.** Checking them by hand with `tsc --strict` shows type errors in `tests/authCopy.test.ts` that no gate reports today.
- **Lint covers error prevention only.** It uses the `essential` tier of `eslint-plugin-vue` and has no formatter. The style tiers flagged about 1,300 existing sites and were left out on purpose.
- **Node versions differ.** The `Dockerfile` builds on `node:20-alpine`, while CI and the tests use Node 22.
