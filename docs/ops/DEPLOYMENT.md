# Deployment keys and credentials

Every secret, certificate and licensed payload SelahCue needs to build and ship, and exactly how to
obtain each one.

- **Build/design detail** lives elsewhere: `docs/ops/WINDOWS-INSTALLER.md` and
  `docs/superpowers/specs/2026-08-13-macos-dmg-build-design.md`. This document is about
  *credentials*.
- **Nothing here belongs in git.** Everything is either a GitHub Actions secret, a Git LFS payload,
  or a runtime environment variable on the host.

## Status at a glance

| What | Needed for | Who supplies | State |
|------|-----------|--------------|-------|
| Apple Developer ID (6 secrets) | Signed + notarized macOS DMG | Owner | **Not yet supplied** |
| macOS NDI SDK (`libndi.dylib`) | NDI broadcast in the Mac build | Owner | Vendored locally; not yet in LFS |
| Windows NDI runtime | NDI broadcast in the Windows build | — | **Self-provisioning in CI**; nothing to do |
| Windows code-signing cert | Removing the SmartScreen warning | Owner | Optional; not planned |
| Django API env vars | Running the Platform API | Owner | Deployment-time |

No GitHub Actions secret is referenced by any workflow today — the Apple credentials below will be
the first.

---

## 1. Apple Developer ID — macOS signing and notarization

Six secrets. The names are **Tauri v2's contract**, not arbitrary; do not rename them. When all six
are present, Tauri signs the app, submits it to Apple's notary service, waits for the ticket, and
staples it — no scripting on our side.

| Secret | Example / format |
|--------|------------------|
| `APPLE_CERTIFICATE` | base64 blob of a `.p12` file (a few KB — well within the secret size limit) |
| `APPLE_CERTIFICATE_PASSWORD` | the password you set when exporting the `.p12` |
| `APPLE_SIGNING_IDENTITY` | `Developer ID Application: Your Org (ABCDE12345)` |
| `APPLE_ID` | `you@example.com` |
| `APPLE_PASSWORD` | `abcd-efgh-ijkl-mnop` (app-specific — **not** your Apple ID password) |
| `APPLE_TEAM_ID` | `ABCDE12345` (10 characters) |

### 1.1 Prerequisite: Apple Developer Program

Enrol at [developer.apple.com/programs](https://developer.apple.com/programs/) — **$99/year**.
Enrolment is not instant; organisation accounts need a D-U-N-S number and can take days. There is no
way to notarize without it.

> For an organisation account, only the **Account Holder** can create a Developer ID certificate.
> If you are on a team without that role, see §1.7 for the App Store Connect API alternative.

### 1.2 `APPLE_SIGNING_IDENTITY` — create the certificate

You need a **Developer ID Application** certificate. This is a specific type — "Apple Development"
and "Apple Distribution" certificates will *not* notarize.

Easiest route, in Xcode:

> Settings → Accounts → select your team → Manage Certificates → **+** → **Developer ID Application**

It installs straight into your login keychain. Then read back the exact identity string:

```bash
security find-identity -v -p codesigning
```

Copy the full quoted name, e.g. `Developer ID Application: Your Org (ABCDE12345)`. That whole string
is `APPLE_SIGNING_IDENTITY`.

### 1.3 `APPLE_CERTIFICATE` and `APPLE_CERTIFICATE_PASSWORD` — export it

CI has no keychain, so the certificate travels as a base64-encoded `.p12`:

1. Open **Keychain Access** → **login** keychain → **My Certificates**.
2. Find the "Developer ID Application: …" entry and expand it — it **must** show a private key
   underneath. Without the key it cannot sign.
3. Right-click the certificate → **Export** → format **Personal Information Exchange (.p12)**.
4. Set a strong password. That password is `APPLE_CERTIFICATE_PASSWORD`.

Encode it:

```bash
base64 -i DeveloperID.p12 | pbcopy   # now on your clipboard as APPLE_CERTIFICATE
```

Then delete the `.p12` from disk — it is a signing key, and anything signed with it is attributed to
you.

### 1.4 `APPLE_ID`

The email address of the Apple account enrolled in the Developer Program.

### 1.5 `APPLE_PASSWORD` — app-specific password

**Not your Apple ID password.** Apple rejects account passwords for notarization.

> [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security → **App-Specific Passwords**
> → **+** → name it something like `selahcue-notarize`

You get a `xxxx-xxxx-xxxx-xxxx` string, shown **once**. Copy it immediately.

### 1.6 `APPLE_TEAM_ID`

> [developer.apple.com/account](https://developer.apple.com/account) → Membership details → **Team ID**

It is also the 10-character code in parentheses at the end of your signing identity.

### 1.7 Alternative: App Store Connect API key

If the app-specific password route is blocked (common on organisation accounts where the Apple ID
lacks the right role), Tauri also accepts an API key. Supply these *instead of* `APPLE_ID`,
`APPLE_PASSWORD` and `APPLE_TEAM_ID`:

| Secret | Where |
|--------|-------|
| `APPLE_API_ISSUER` | App Store Connect → Users and Access → Integrations → Issuer ID |
| `APPLE_API_KEY` | the key ID of a generated key |
| `APPLE_API_KEY_PATH` | path to the downloaded `AuthKey_<id>.p8` on the runner |

The `.p8` downloads **once** and cannot be retrieved again.

### 1.8 Renewal

Developer ID certificates last 5 years; app-specific passwords do not expire but are revoked if the
Apple ID password changes; **Developer Program membership lapses annually and takes notarization
with it.** An expired membership fails the build at the notarization step, not at signing.

---

## 2. NDI SDK

### macOS — owner-supplied

The NDI SDK for Apple is licence-gated and cannot be fetched unattended (it returns HTTP 403 to
scripted downloads — this is why the Windows job takes a different route).

1. Download the **NDI SDK for Apple** from [ndi.video](https://ndi.video/for-developers/ndi-sdk/)
   (accept the licence; they email a link).
2. Install it, then vendor it into the repo layout:
   ```bash
   scripts/fetch_ndi_sdk.sh              # auto-detects /Library/NDI SDK for Apple
   ```
3. Commit `libndi.dylib` via Git LFS (§3).

The vendored dylib is already Universal (`x86_64 arm64`) with an `@rpath` install name, so it needs
no further processing.

### Windows — nothing to do

CI self-provisions: it downloads the **public** NDI runtime redistributable, generates an import
library from the DLL's exports, and builds against that. No licence-gated download, no secret.

### Redistribution

Both platforms ship the NDI runtime unmodified and must not rename it. Installer docs carry the
attribution: *"NDI® is a registered trademark of Vizrt NDI AB."*

---

## 3. Git LFS

`libndi.dylib` is 28 MB — orders of magnitude past GitHub's per-secret size limit — so it is
committed as an LFS object rather than passed to CI as a secret.

```bash
brew install git-lfs
git lfs install
git lfs track "implementation/desktop/vendor/ndi/macos/lib/*.dylib"
git add .gitattributes implementation/desktop/vendor/ndi/macos/
```

Any workflow that needs the real bytes must check out with `lfs: true`; without it, the file
arrives as a small pointer and the link fails with a confusing error. Only the macOS installer job
needs this.

---

## 4. Adding secrets to GitHub

Repository → Settings → Secrets and variables → Actions → **New repository secret**. Or:

```bash
gh secret set APPLE_CERTIFICATE < cert.b64
gh secret set APPLE_CERTIFICATE_PASSWORD
gh secret set APPLE_SIGNING_IDENTITY
gh secret set APPLE_ID
gh secret set APPLE_PASSWORD
gh secret set APPLE_TEAM_ID
```

Secrets are write-only — you cannot read one back to check it, only overwrite it. A typo surfaces as
a build failure, so verify each value before setting it.

---

## 5. Windows code signing (optional, not planned)

The Windows installer is deliberately unsigned for internal test builds; users click through
SmartScreen. Removing that warning needs an **OV or EV code-signing certificate** from a CA
(DigiCert, Sectigo, …) at roughly $200–600/year, and since June 2023 the private key must live on
approved hardware (HSM or cloud signing service) — so it is not a simple "add a secret" change. EV
certificates get SmartScreen reputation immediately; OV certificates must build it over time.

---

## 6. Platform API (Django) runtime environment

Not GitHub secrets — environment variables on whatever host runs `implementation/api`. Defaults are
development-safe, which means **an unset production variable is usually the insecure choice**.

Key names follow the **First Pavilion house convention** — the same ones yharah-logistics uses
(`api/.env.sample` there). A full sample lives at `implementation/api/.env.sample`; its `SECRET_KEY` is blank on purpose, so a copy of it boots only in `dev` (where blank means the dev key) and is refused everywhere else until you set a real one.

| Variable | Default | Production |
|----------|---------|-----------|
| `ENVIRONMENT` | `dev` | **Required: `staging` / `prod`.** Genuinely unset with an absent/empty raw `SECRET_KEY` and any non-local `DJANGO_ALLOWED_HOSTS` entry refuses settings import. Local-only defaults still select dev; explicit `dev` and a configured raw key remain outside that narrow guard. See the precise boundary below. It also gates the mail backend, the `SECRET_KEY` check below, and refusal of enabled `DEBUG` or `SELAHCUE_TRUST_ACTOR_HEADERS` outside exact `dev` |
| `SECRET_KEY` | dev-only fallback | **Required, and not a public value. The app refuses to boot when `ENVIRONMENT != dev` and this is empty, equals the dev key, or equals the `replace-me-with-a-fresh-key` placeholder that earlier copies of `.env.sample` carried (letter case, whitespace, matched ASCII quotes and invisible format characters such as a BOM, zero-width space or joiner, or soft hyphen are ignored when comparing).** It is also the HMAC pepper for licence-key, device-token and account-session fingerprints: rotating it invalidates them all |
| `DEBUG` | `0` | **Startup refuses true outside exact `dev`, including staging.** Leave `0` or unset; see below |
| `DJANGO_ALLOWED_HOSTS` | `localhost 127.0.0.1 testserver` | **Required. Space-separated** (commas tolerated). Non-local entries trigger the omitted-environment/empty-key guard described below |
| `SQL_ENGINE` | `…backends.sqlite3` in dev only | **Startup refuses unset/blank or SQLite outside exact `dev`**, naming `SQL_ENGINE` and `ENVIRONMENT`. Configure `django.db.backends.postgresql`; row-locking is required, see below |
| `SQL_DATABASE` / `SQL_USER` / `SQL_HOST` / `SQL_PORT` | SQLite path / `postgres` / `localhost` / `5432` | **Required** for Postgres |
| `SQL_PASSWORD` | `postgres` in dev only | **Startup refuses unset/blank or exact `postgres` outside exact `dev`**, naming `SQL_PASSWORD` and `ENVIRONMENT` without echoing the value |
| `DB_CONN_MAX_AGE` | `60` | Tune to your pooling |
| `CELERY_BROKER_URL` | `redis://redis:6379/2` | Point at the real Redis |
| `CELERY_BROKER_SOCKET_CONNECT_TIMEOUT` | `0.5` (seconds) | Redis broker TCP connect timeout; allowed `0.05` to `10`, invalid values refuse startup. See §6b |
| `CELERY_BROKER_SOCKET_TIMEOUT` | `0.5` (seconds) | Redis broker per-command timeout; allowed `0.05` to `10`, invalid values refuse startup. See §6b |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Point at the real Redis |
| `CACHE_URL` | empty → LocMemCache | **Set it.** `redis://…/1` — db **1**, never the broker's db 2. See §6b |
| `CACHE_SOCKET_CONNECT_TIMEOUT` | `0.5` (seconds) | Leave the default. How long the cache waits to open a connection to Redis. Allowed `0.05` to `10`; anything else refuses to boot. See §6b |
| `CACHE_SOCKET_TIMEOUT` | `0.5` (seconds) | Leave the default. How long the cache waits for Redis to answer one command. Allowed `0.05` to `10`; anything else refuses to boot. See §6b |
| `CACHE_CIRCUIT_FAILURE_THRESHOLD` | `3` | Integer `1` to `100`; consecutive cache errors before this worker bypasses the store. See §6b |
| `CACHE_CIRCUIT_COOLDOWN` | `5` (seconds) | Finite `0.1` to `60`; bypass duration before a single recovery probe. See §6b |
| `SELAHCUE_TRUSTED_PROXY_COUNT` | `0` | Number of *your own* proxies in front of Django. See §6b |
| `SELAHCUE_TRUST_FORWARDED_PROTO` | `0` (off) | Set `1` (or `true`/`yes`/`on`) behind a TLS-terminating proxy that overwrites `X-Forwarded-Proto`, else browser CSRF fails and HSTS is never sent. Opt-in because the header is forgeable, and it makes HSTS live. See §6c |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Exact `https://host[:port]` origins (no `*`, no path), only if the browser `Origin` differs from the forwarded `Host`. A bad entry refuses to boot. See §6c |
| `MAIL_HOST` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` | mailhog on `:1025` in dev | **Required** to send email |
| `DEFAULT_FROM_EMAIL` / `DEFAULT_EMAIL` | SelahCue defaults | Set to your verified sending domain |
| `SENTRY_DSN` | empty | Read into settings, but nothing consumes it yet (no Sentry SDK is wired), so setting it changes nothing today. Intended for staging/prod only, never locally |
| `SELAHCUE_CORS_ALLOWED_ORIGINS` | empty | Leave empty. It is read but **not enforced**: no CORS middleware is installed (the SPA is served same-origin), and `selahcue_accounts.W001` warns if it is set |
| `SELAHCUE_TRUST_ACTOR_HEADERS` | follows `DEBUG` in dev; false elsewhere | **Startup refuses true outside exact `dev`, including staging and explicit opt-in.** See below |
| `SELAHCUE_ENTITLEMENT_SIGNING_KEY` | **none** | **Required** to issue offline entitlements. See §6a |
| `SECURE_HSTS_SECONDS` | `31536000` when not debug | Keep the default. Only emitted once Django knows the request is secure: see §6c |
| `ACCOUNT_SESSION_TTL_SECONDS` | 30 days | Policy choice |
| `ACCOUNT_EMAIL_VERIFY_TTL_SECONDS` | 24 hours | Policy choice |
| `ACCOUNT_PASSWORD_RESET_TTL_SECONDS` | 1 hour | Policy choice |
| `ACCOUNT_LOGIN_LOCKOUT_THRESHOLD` | `5` | Policy choice |
| `ACCOUNT_LOGIN_LOCKOUT_SECONDS` | `900` | Policy choice |
| `ACCOUNT_MIN_PASSWORD_LENGTH` | `10` | Policy choice |

> **`SQL_ENGINE` must be Postgres in production, not merely preferred.** The DEC-004 device
> instance limit is enforced with `select_for_update`, which SQLite silently no-ops
> (`has_select_for_update = False`). On SQLite two concurrent activations can both observe
> `active_devices = 0` and exceed `device_limit`. The guard is not wrong — it simply has no
> effect without a row-locking backend.

Database validation runs at settings import, including under gunicorn/uwsgi without system
checks. Any `ENVIRONMENT` other than exact `dev` refuses missing/whitespace-only `SQL_ENGINE`
or an engine ending in `sqlite3`; it also refuses missing/whitespace-only `SQL_PASSWORD` or the
exact public default `postgres`. The guard does not restrict all other backends to an allowlist
or impose a password-strength policy. Password values are not normalized or logged. Exact dev
retains SQLite fallback and the existing non-SQLite password default; no database data is changed
by these checks. Configure Postgres and a real password before starting a deployed API.

The omitted-environment guard runs when settings are imported, including under gunicorn or
uwsgi; it does not rely on `manage.py check`. It refuses only the conjunction of genuinely
unset `ENVIRONMENT`, absent/empty raw `SECRET_KEY`, and at least one non-local
`DJANGO_ALLOWED_HOSTS` entry. The local set is exactly `localhost`, `127.0.0.1`, `::1`
(including Django's bracketed `[::1]` spelling), and `testserver`. Wildcards, suffix patterns,
and other addresses are non-local. A mixed local/non-local list is refused too.

This uses option (a) from [17tnw2b9d9y](https://app.clickup.com/t/17tnw2b9d9y): it works for every settings entry point without
assuming Coolify uses a particular Dockerfile, while keeping bare local development available.
It is a narrow omission guard, not a universal deployment detector: explicit `dev` and a
configured nonempty raw key retain their existing behavior. Set `ENVIRONMENT=staging` or
`ENVIRONMENT=prod` and a real key in deployed environments; those modes also select the real
SMTP defaults and enable the TLS-proxy warning.

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

> **`DEBUG` and the actor-header bridge are dev-only.** Startup raises an actionable error
> naming the flag and environment if either `DEBUG` or `SELAHCUE_TRUST_ACTOR_HEADERS` is true
> when `ENVIRONMENT` is anything other than exact `dev`. This includes staging: an explicit
> bridge opt-in is refused even behind an ingress that strips identity headers. In dev the
> bridge follows `DEBUG` unless explicitly overridden; debug also enables the GraphQL IDE and
> introspection and zeroes HSTS. The bridge rejects `anonymous`, which remains available only
> for internally generated failed-confirm audit actors. Keep both flags false/unset outside dev;
> production staff identity integration remains a separate prerequisite.

---

## 6a. Entitlement signing key (Platform API)

`SELAHCUE_ENTITLEMENT_SIGNING_KEY` — the Ed25519 private seed that signs offline entitlement
manifests (DEC-004). **It has no default**, and unlike `SECRET_KEY` it has no dev fallback either: if it is unset,
`GET /v1/entitlements/manifest` fails loudly rather than serving an unsigned manifest. A
well-known dev fallback would let anyone forge an entitlement and void the offline model.

Generate one:

```bash
python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
```

Store it as an environment variable on the API host, alongside `SECRET_KEY`. Never commit
it — anything signed with it is accepted by every SelahCue install that trusts the corresponding
public key.

### Rotation

The `key_id` in each envelope is derived from the public key (first 8 hex of its SHA-256), so
clients select the right key without a registry:

1. Generate the new seed; derive its public key and `key_id`.
2. Ship a desktop release whose trusted-key set contains **both** the old and new public keys.
3. Wait for adoption — manifests signed by the old key keep verifying throughout.
4. Switch `SELAHCUE_ENTITLEMENT_SIGNING_KEY` on the server to the new seed.
5. Drop the old public key in a later release.

Never sign with two keys at once; the envelope carries exactly one signature. Rotation is
**not** a revocation mechanism — an already-issued manifest stays valid until the licence
expires (DEC-005), regardless of key changes.

---

## 6b. Ops requirements — ingress, throttling and Redis

The deployment remains responsible for stripping identity headers, edge flood protection and
shared Redis. The startup guards in §6 refuse the dev identity bridge outside dev; those guards
do not replace the edge and Redis controls below.

### The ingress must strip inbound `X-SelahCue-*` headers

Strip inbound identity headers at the edge and verify a forged header does not survive to
Django. Keep `SELAHCUE_TRUST_ACTOR_HEADERS` false/unset in every shared deployment, including
staging. **Stripping does not permit enabling the bridge outside dev:** startup refuses it.

The dev bridge cannot distinguish a caller's identity headers from headers an ingress added.
When enabled locally it trusts caller-selected identities and staff permissions, so use it only
in a trusted local development environment. It rejects the `anonymous` kind; internal
failed-confirm audit rows still use that kind. Real customer session authentication takes
precedence over the bridge. Production staff identity integration remains separate.

### Per-IP flood protection belongs at the edge

The app carries a fixed-window rate limiter on the `/v1` device-auth endpoints (activation,
licence refresh, entitlement manifest, and the native account sign-in pair `POST /v1/sessions` and
`POST /v1/activations:with-session` — ADR-0029), keyed on `(endpoint, client IP)` with the budgets
in `SELAHCUE_THROTTLE_*`. Treat it as the **second** layer, never the only one. If your ingress
rate rule is keyed on `/graphql/account`, extend it to the two native paths: it does not cover them.

It runs *inside* Django, so a request must be accepted, routed and middleware-processed before it
can be refused — a flood large enough to matter has already consumed a worker slot by then. It
also **fails open** by design (this includes `POST /v1/sessions`, where the only remaining brake on
password guessing during an outage is the per-account lockout): if Redis is unavailable the limiter allows the request and logs,
because refusing all device traffic during a cache outage would cause the outage it exists to
prevent. Both properties are deliberate, and both mean the app limiter cannot absorb a real
flood. Put connection- and request-rate limits on the ingress; the app layer is there to catch
per-endpoint abuse that looks like ordinary traffic at the edge.

`SELAHCUE_TRUSTED_PROXY_COUNT` ties the two together. It is the count of **your own** proxies
between the client and Django, and it defaults to `0`, meaning the limiter keys on `REMOTE_ADDR`
and ignores `X-Forwarded-For` entirely. Raise it only to the real number of hops you control:
the header is caller-supplied, so a count that is too high makes the limiter read an attacker-
controlled value and hands out a fresh budget per request — one header, limiter gone. Too low is
merely inaccurate (everyone behind the proxy shares a bucket); too high is a bypass.

### Redis must not be publicly reachable

Bind it to the private network, or require auth and TLS if it must cross one. It has no
authentication by default and no per-key authorisation at all.

It holds two things that matter. Db **1** is the throttle counters: write access is enough to
zero anyone's budget, or to set every counter past its limit and 429 the whole device fleet. Db
**2** is the Celery broker: queued messages are task names plus arguments, and anyone who can
write to that queue can make the worker execute any registered task with arguments of their
choosing — including the transactional-email tasks, which carry credential tokens. Read access
alone exposes those tokens in flight.

Keep the two on separate databases as configured. `CACHE_URL` ends in `/1` and the Celery URLs
end in `/2` so that a `FLUSHDB` on either — during an incident, say, to clear a poisoned queue —
cannot take the other with it.

### A Redis that stops answering must not stall requests

"Fails open when Redis is unavailable" (above) is only true if the app gives up on a Redis that has
gone quiet. A Redis that is **up but wedged** — a failing node, a network partition, memory pressure
— still accepts the connection and then never replies. With no socket timeout the app waits forever
for that reply, so the limiter never gets to fail open: every request that spends a throttle budget
is held for as long as Redis stays wedged, and a cache fault becomes a full API outage.

Routes that spend a budget, and how many:

- **One budget:** `POST /v1/activations`, `POST /v1/sessions`, `POST /v1/activations:with-session`,
  `POST /v1/license:refresh`, `GET /v1/entitlements/manifest`, and the GraphQL mutations
  `verifyEmail` and `confirmPasswordReset`.
- **Three budgets:** the GraphQL mutations `requestPasswordReset` and `resendVerificationEmail`.

The cache connection therefore carries two timeouts, in seconds, both read from the environment:

| Variable | Default | Allowed range | What it bounds |
|----------|---------|---------------|----------------|
| `CACHE_SOCKET_CONNECT_TIMEOUT` | `0.5` | `0.05` to `10` | Opening the TCP connection to Redis, and nothing after it |
| `CACHE_SOCKET_TIMEOUT` | `0.5` | `0.05` to `10` | Waiting on Redis for anything once the TCP connection is open: each command, and on a new connection the handshake too |

- **Per-process cache circuit (17tnw2b2kab).** After `CACHE_CIRCUIT_FAILURE_THRESHOLD`
  consecutive budget-store errors (default `3`), that worker skips store access for
  `CACHE_CIRCUIT_COOLDOWN` seconds (default `5`). A successful counter operation, including a
  real denial, resets the consecutive error count. The threshold accepts integers `1` to `100`;
  cooldown accepts finite seconds `0.1` to `60`. Blank uses the default; invalid values refuse
  startup with a diagnostic naming only the setting. These operational limits prevent a typo
  from making every transient error open the circuit indefinitely or allowing an excessive
  run of failing requests before protection starts. Tune against measured traffic and recovery.
  After cooldown exactly one request probes Redis; concurrent requests continue to receive
  the existing unavailable outcome. Success closes the circuit; failure starts a fresh cooldown.
  Calls already in flight may still finish; their older results cannot close or extend a newer
  outage. No circuit lock is held during Redis I/O. State is a few counters, a timestamp and a
  lock per worker, shared across identities; restart clears it. Workers recover independently.
  Bypassed checks retain the unavailable outcome, caller-specific admission and degraded mail
  ceilings, plus the existing once-per-minute outage report. They do not consume a Redis budget.
  The first three sequential stalls still pay the socket timeout; cooldown traffic does not.
  This circuit does not detect a slow store that keeps answering within its socket timeout.
  Celery broker publication is a separate connection and ticket; it has no cache circuit.
- **Healthy Redis: nothing changes.** A healthy Redis answered one command in a few milliseconds
  (26 ms at worst in this change's performance review), so the default is at least 19 times the
  worst healthy sample.
- **A stalled Redis is treated exactly like a down one.** The call raises, the throttle **permits
  the request** except native `POST /v1/sessions`: bootstrap login returns429 before password
  work when its budget cannot be checked (17tnw2b1wq9; see the API README). Already activated
  devices and other native routes retain their existing fail-open availability. The degraded
  send ceilings apply (`SELAHCUE_RESEND_DEGRADED_SEND_CEILING`,
  `SELAHCUE_RESET_SEND_DEGRADED_CEILING`), and the same one-line `rate-limit store unavailable`
  warning is logged (once a minute per worker; for a stall it names `TimeoutError`).
- **What a bad Redis costs a request.** The timeout applies to each Redis *command*, not to each
  budget. Spending one budget takes one to three commands (`SET NX`, and once the counter exists
  also `EXISTS` and `INCR`; in the rare race where a counter's window lapses between those two,
  one `EXPIRE` and sometimes a second `SET NX` more), and opening a new connection adds three
  more (two `CLIENT SETINFO` and a `SELECT`). Those handshake commands, and with a `rediss://`
  URL the TLS handshake itself, run under `CACHE_SOCKET_TIMEOUT`, not the connect timeout: redis-py
  applies the read timeout as soon as the TCP connect returns (checked against redis-py 6.4.0, with
  a listener that accepts and never speaks TLS: it gave up at the read timeout, not the connect
  timeout).
  - **Stalled** (accepts, never answers): the first command of a budget times out and the rest of
    that budget is skipped, so a request costs about one timeout per budget: about 0.5 s on a
    one-budget route and about 1.5 s on a three-budget route. Measured on a frozen Redis.
  - **Slow but answering** (every reply just under the timeout): nothing times out and nothing
    fails open, and each command costs nearly the full timeout: up to about 1.5 s on a one-budget
    route and 4.5 s on a three-budget route, plus about 1.5 s when the connection has to be
    reopened. Measured with a proxy that answered every command 0.4 s late, so each figure sits at
    about 0.8 of the maximum just given: 1.21 s for a steady one-budget call, 3.64 s for three
    budgets (a reset or resend), and 1.69 s for the **first** call on a fresh connection (it also
    paid the three handshake commands).

  A shared `/v1` throttle **denial** also reads the existing counter's PTTL on the primary
  to provide `Retry-After` (17tnw2b1wqc). That is one extra command under the same socket timeout:
  up to about 0.5 s more at the defaults if Redis becomes slow after the counter decision.
  Allowed and fail-open requests do not pay it. If this metadata read fails, the response remains
  429 with a full-window retry hint; no new key, counter write or retry is introduced.

  It is a ceiling, not a retry: a timed-out call is not repeated.
- **Allowed range.** Each variable must be from `0.05` to `10` seconds, inclusive; a blank value
  means the default. Anything else makes the API refuse to start, with an error naming the
  variable, even when `CACHE_URL` is unset. Each end of the range exists to stop a typo that
  would otherwise switch the protection off while the app starts and looks healthy:
  - Too small (`0.001`, `1e-9`): working calls start timing out and the limiter fails open for no
    fault of Redis's. `0` is not "no timeout" either: redis-py reads it as non-blocking, so every
    call fails at once. The floor is about twice the worst healthy sample above.
  - Too big: `1e10` or `1e308` is rejected by Python's socket layer on every call, so the limiter
    fails open forever with only the once-a-minute warning to show for it; `86400` is a 24-hour
    wait and `500` (milliseconds typed as seconds) holds a request for minutes. The ceiling is
    ten seconds because a three-budget route can spend nine commands, which at 10 s each is
    90 s for one request.
- **Supported timeout channels.** Set timeouts only through `CACHE_SOCKET_CONNECT_TIMEOUT`
  and `CACHE_SOCKET_TIMEOUT` above. The API refuses to start if `CACHE_URL` contains the query
  option `socket_connect_timeout` or `socket_timeout`, including percent-encoded option names,
  blank values and values inside the allowed range. Redis URL query options otherwise override
  the backend's validated settings, so even an in-range URL timeout is refused to keep one
  authoritative channel. Remove the option from the URL and set the corresponding environment
  variable instead. The error names the option and supported variables without echoing the URL,
  credentials or query value. A malformed URL that the parser cannot read also refuses startup
  with a fixed syntax diagnostic, suppressing the parser exception that can contain credentials.
  Other query options and well-formed URLs without timeout options retain their existing behavior;
  an unset `CACHE_URL` still selects the local memory cache.
- **Tuning.** Keep the defaults unless you have measured a reason not to. Raise a timeout only when
  the slowest healthy round trips you can measure on your own Redis (including, on `rediss://`, the
  TLS and handshake round trips of a reconnect, which all count against `CACHE_SOCKET_TIMEOUT`)
  come within a few times of 0.5 s; a managed or TLS Redis that needs it is likely to be well served
  by a value between `0.2` and `5`. Raising a timeout multiplies every figure above, so stay as low
  as the measurements allow, even with the circuit bypass, and keep the
  timeout times the commands a route spends (up to 9, rarely a few more, on a three-budget route;
  12 on a fresh connection) below any request timeout your host or proxy enforces. Size threads or
  workers for arrival rate times the added latency.
- **No server timeout is configured here.** This repository ships only Django's development server
  (`manage.py runserver`, in the `Dockerfile` and the compose file), which has no request timeout
  and starts a thread per connection with no cap. No production application server (gunicorn,
  uvicorn and the like) is configured in this repo, so there is no "worker timeout" to stay under
  until one is chosen; until then a stall shows up as extra in-flight requests (arrival rate times
  the added latency), not as refused ones.
- **Alert on it.** Failing open is now quiet inside the app: the only in-app signal is one WARNING
  per worker per minute (`rate-limit store unavailable (TimeoutError)`, plus `limiter unavailable`
  when a mail send is skipped). This repo configures no `LOGGING` and has no Sentry integration
  wired (`SENTRY_DSN` is read into settings but nothing consumes it), so those lines reach only
  whatever collects your process output: page on them there. It is also visible from outside:
  while it lasts, every throttled response is slower by the figures above and `RATE_LIMITED`
  (429) answers stop appearing, so a flood is no longer refused.
- **The task broker has its own socket limits (17tnw2b2k4x).** The two broker timeout
  variables in the API environment table use the same inclusive 0.05–10 second validation as
  the cache, with 0.5 second defaults. They configure Kombu's Redis transport through the Python setting
  `CELERY_BROKER_TRANSPORT_OPTIONS` (not another environment variable);
  cache settings do not configure the broker. Set them using the explicit environment variables.
  Kombu does not accept socket-timeout or retry options in the Redis broker URL query; these
  unsupported query options cannot override the transport settings and publishing fails safely.
  Email publishing opens a dedicated connection and sets connection retries to zero and publish
  retries off. This avoids waiting for a pooled producer and bounds a completely silent broker
  to one read timeout after connecting, plus request/database/password work and scheduler jitter.
  Redis command retries on timeout are disabled. These email callers consume no task results,
  so each email publish sets `ignore_result=True`. This prevents Celery from subscribing to the
  independent `CELERY_RESULT_BACKEND` before sending: broker socket limits do not configure that
  result client's socket limits. Email task defaults, global result settings, worker reconnect
  and unrelated task-publisher retry/result policies are unchanged. The per-message result flag
  applies only to emails submitted through this sender.
- **A socket timeout is per command, not a request deadline.** An answering-but-slow broker can
  perform several bounded reads (authentication, CLIENT SETINFO, SELECT, PING, queue declaration,
  and publish); TLS handshakes use the read timeout. DNS resolution is controlled by the host's
  resolver, not these socket limits. Keep those cumulative costs below the host/proxy request
  budget. There is still no application-server request deadline in this repository.
- **A failed publish has an unknown delivery outcome.** A lost response can follow a successful
  enqueue. The sender does not automatically retry, does not return broker errors or account
  existence to callers, and logs only the fixed task name and exception type, at most once per
  process per minute. Alert on `email delivery unconfirmed`. The existing accepted response
  confirms processing, not email delivery; the request acknowledgements explain checking the
  inbox and requesting another link if nothing arrives. Account and token commits remain intact,
  so a user can use the existing resend/reset flows. Do not infer guaranteed delivery from an
  accepted request or silently replay uncertain publishes. The reset timing-floor follow-up
  remains separate: finite broker waits alone do not equalise registered/unknown response times.


### The failed password-reset confirm trace (86ak5r2pt)

Every `confirmPasswordReset` that fails past the per-IP budget writes one audit row
(`customer_user.password_reset_confirm_failed`, result DENIED). It holds the outcome, a random
attempt id, the account id when the token resolved, and the source as a keyed, daily-rotating
pseudonym `src:v1:<32 hex>` (never the address). Four knobs bound how many rows are written; they
skip the **row**, never the response, and ship in `settings.py`:

- `SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE` (1000 an hour): outcomes that name no account (an unknown
  or malformed token, or an internal error before any account was identified), shared by everyone.
- `SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT` (60 an hour): outcomes that name an account, **per
  account**, so noise cannot hide a probe of one account's link.
- `SELAHCUE_RESET_CONFIRM_TRACE_DEGRADED_CEILING` (200 an hour) and
  `SELAHCUE_RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING` (30 an hour per account, at most 1024
  accounts tracked): the same two, per worker, applying only while the rate-limit store is down.

A skipped or unwritable row is counted and logged once a minute per worker (`skipped N audit
row(s)` / `could not write the audit row`), with the first one's outcome and pseudonym. The
**skip** line also lists up to 20 account ids; the **could not write** line does not. That line is
the signal to look.

Two things to know when reading the counts:

- **Allowance is charged before the write.** A row's allowance is spent before the INSERT. With a
  healthy cache and a down audit store, each lost write still spends the account's allowance for
  that hour (60), so after that hour's allowance is gone later rows are reported as skipped while the
  real cause is the audit store. Bounded to the hour, and both lines are counted.
- **Rows that name an account have no aggregate ceiling.** Each account has its own 60 an hour; there
  is no limit across accounts. The per-source budget (20 an hour per source) only bounds that when
  `SELAHCUE_TRUSTED_PROXY_COUNT` is right, and in an outage the per-worker table holds 1024 accounts
  and evicts the oldest, so rotating through more than 1024 accounts gets a fresh window each time.
  Recorded and accepted for now; a follow-up adds an aggregate ceiling and a registration throttle.

To find the rows from a known address: `python manage.py failed_reset_confirms --ip <address>
[--date YYYY-MM-DD]`. It prints account ids, so **do not run it in CI or put its output in a log
that is kept**. A pseudonymised address is still personal data. Rotating `SECRET_KEY` makes older
rows unfindable by address (the pseudonym is recomputed from the current key only;
`SECRET_KEY_FALLBACKS` is not consulted); the rows stay until retention removes them
(17tnw2b9dp1).

---

## 6c. Ops requirements — Django behind a TLS-terminating proxy

In production TLS ends at the edge and Django receives plain HTTP. Django is not told otherwise
unless you tell it, and when it is not told, two things fail without any error at boot:

- **Browser account and admin mutations are refused with 403.** A browser served over TLS sends
  `Origin: https://<host>`; Django's CSRF check compares that with `http://<host>` (because
  `request.is_secure()` is false) and refuses it, even with a valid `csrftoken` cookie and
  `X-CSRFToken` header. Sign-in, sign-up and every other `/graphql/account` mutation break for
  every real browser. (17tnw2b1wtr)
- **HSTS is never sent.** `SecurityMiddleware` emits `Strict-Transport-Security` only over a
  request it believes is secure, so `SECURE_HSTS_SECONDS` and its siblings do nothing.

`manage.py check` now warns about this (`selahcue_accounts.W002`) whenever `ENVIRONMENT` is not
`dev`, `DEBUG` is off and the flag below is off. It is a Warning, never an Error: a Django that
terminates TLS itself needs no proxy, and can silence it with
`SILENCED_SYSTEM_CHECKS = ['selahcue_accounts.W002']`.

The fix is two environment variables on the API host:

| Variable | Default | Production |
|----------|---------|-----------|
| `SELAHCUE_TRUST_FORWARDED_PROTO` | `0` (off) | `1` **only if** every route to Django goes through a proxy that overwrites `X-Forwarded-Proto`. See below |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Only when the browser's `Origin` differs from `<scheme>://<Host header>`. See below |

**Accepted spellings of `SELAHCUE_TRUST_FORWARDED_PROTO`.** On: `1`, `true`, `yes`, `on`, in any
letter case and with surrounding whitespace ignored. Anything else is off, including unset,
empty, `0`, `false`, `off`, `no` and near-misses such as `y`, `t`, `enabled` or `2`. A typo
therefore fails closed: you keep the original 403 rather than silently trusting a header.

**`DJANGO_CSRF_TRUSTED_ORIGINS` entries are exact origins.** Separate entries with a comma or any
whitespace (space, tab, newline); empty entries are ignored and duplicates are merged. Each entry
must be `https://host` or `https://host:port`: no `*` or wildcard subdomain, no path, no query,
no credentials, and no trailing slash (one is forgiven and removed, since a browser's `Origin`
never has a path). The host is lowercased. `http://` is accepted only when `DEBUG` is on. The
API also refuses, at boot, entries that no browser `Origin` can ever equal, so they cannot sit
there silently never matching: the default port (`:443` on https, `:80` on http; write the origin
without it), port `0`, a backslash anywhere, and a non-ASCII host (use the punycode `xn--` form,
which is what a browser sends). A host with a leading dot (`https://.example.com`), a trailing dot
or an empty label (`a..b`) is refused too: Django reads a leading-dot host as "this domain and
every subdomain", so it would behave as the wildcard the previous rule forbids. A bad entry makes
the API refuse to boot with an error naming the variable and the entry (a pasted
`https://user:secret@host` is shown as `https://***@host`, never with the password), so a typo
cannot silently weaken or disable the check. The only intended value is the SPA's own public
origin; every entry is a cross-origin trust grant.

`SELAHCUE_TRUST_FORWARDED_PROTO=1` sets Django's `SECURE_PROXY_SSL_HEADER` to
`("HTTP_X_FORWARDED_PROTO", "https")`. Django then reads the header like this: it takes the
**first** comma-separated element, strips surrounding whitespace, and compares it to `https`
**case-sensitively**. So `https`, ` https ` and `https, http` count as secure; `HTTPS`, `http`,
`http, https`, an empty value, any other junk and an absent header all leave the request insecure.
That first-element rule is why rule 1 below matters: a proxy that *appends* to the header instead
of replacing it lets the client's own first value win.

### Why it is off by default

`X-Forwarded-Proto` is an ordinary request header. If a client can reach Django without passing
through a proxy that **replaces** the header, it can send `https` itself and be believed: Django
would treat a plain-HTTP request as secure (HSTS, the CSRF origin comparison and secure-redirect
logic all read it). So the app never assumes a proxy exists. It is a separate switch from
`SELAHCUE_TRUSTED_PROXY_COUNT` (§6b) on purpose: that one decides how many `X-Forwarded-For`
entries to believe for rate limiting, this one decides whether to believe a different header, and
turning on the first must not quietly decide the second. Local development and the compose stack
leave it off and are unchanged.

### What the proxy must do before you turn it on

1. **Overwrite, never append or pass through, `X-Forwarded-Proto`** with the scheme the *client*
   used. A proxy that forwards whatever the client sent is exactly the forgery described above.
   The TLS edge (Cloudflare, Coolify's Traefik) sets it itself. The marketing nginx is the
   trusted hop behind it: `implementation/marketing/nginx.conf` passes the edge's `https` through
   (any other value, or none, becomes the scheme nginx itself saw) and replaces any inbound copy
   with `proxy_set_header`.
2. **Make that proxy the only way in.** Django's port must not be published to the internet or to
   any network a client can reach, and any intermediate hop (the marketing nginx container) must
   be reachable only from the TLS edge. Verify with a request that goes around the proxy and
   sends `X-Forwarded-Proto: https` by hand: with the flag on, anything that answers it as secure
   is a hole.
3. **Forward the public `Host`** (`proxy_set_header Host $host;`, already done by
   `implementation/marketing/nginx.conf`). Then the browser's `Origin` equals
   `https://<host>` and `DJANGO_CSRF_TRUSTED_ORIGINS` can stay empty. Set it when the proxy
   rewrites `Host` to an internal name, and also when the public site is on a non-default port:
   nginx's `$host` drops the port, so a browser `Origin` of `https://selahcue.example:8443` no
   longer matches the forwarded Host.
4. **Know what each hop reports.** Browser traffic reaches Django through the marketing nginx (the
   same-origin `/graphql/` proxy), which sits behind the TLS edge, so nginx's own `$scheme` is
   `http` and the `X-Forwarded-Proto` the edge side sends is the only source of `https`. If any hop
   does not preserve it, Django sees `http` and the flag cannot fix the 403. Check the hop after
   Cloudflare first: Cloudflare sends the header, but the next hop (for example a Traefik that
   trusts no inbound forwarded headers) may replace it with the scheme of its own plain-HTTP
   connection. Configure Traefik `forwardedHeaders.trustedIPs` with Cloudflare's published
   address ranges. Never use `forwardedHeaders.insecure=true`: it accepts client-supplied
   forwarded headers whenever the origin can be reached without Cloudflare. Cloudflare in
   "Flexible" mode (plain HTTP to the origin) can have the same effect.
   That fails closed (you keep the 403), never open. Native clients (`/v1/...`) do not go through
   nginx; their route to Django is the edge directly, and the same two rules hold.

### HSTS goes live the first time you turn this on

The HSTS defaults in §6 were never in effect behind the proxy, so enabling the flag publishes a
**one-year, `includeSubDomains`, `preload`** policy for the first time. Browsers that see it will
refuse plain HTTP to the host and every subdomain for that long, so roll it out deliberately:

1. Confirm every subdomain of the host serves valid HTTPS before enabling `includeSubDomains`.
2. Start small and narrow: `SECURE_HSTS_SECONDS=300` (five minutes),
   `SECURE_HSTS_INCLUDE_SUBDOMAINS=0` and `SECURE_HSTS_PRELOAD=0`. Watch for breakage, then raise
   `SECURE_HSTS_SECONDS` in steps to the one-year default.
3. Switch `SECURE_HSTS_INCLUDE_SUBDOMAINS` back on only once step 1 is true for every subdomain, and
   `SECURE_HSTS_PRELOAD` on only when you have decided, on purpose, to submit the domain to the
   browser preload list. Removal from that list takes months.
4. **Rollback.** Turning the flag off, or setting `SECURE_HSTS_SECONDS=0`, only makes Django stop
   *sending* the header. It does not send `max-age=0`, so browsers that already cached a policy keep
   enforcing it until its `max-age` runs out. The in-app way to shorten what browsers hold is to
   deploy `SECURE_HSTS_SECONDS=1` together with `SECURE_HSTS_INCLUDE_SUBDOMAINS=0` and
   `SECURE_HSTS_PRELOAD=0`: every returning browser replaces its stored policy with a one-second,
   host-only one on its next API response over HTTPS. Django sends this header on API responses;
   the SPA requests `/graphql/csrf` lazily, so visitors who only browse pages may retain the old
   policy. Serve the shorter policy at the TLS edge for coverage of those page responses too.
   Leave it in place for as long as the old `max-age` (so returning visitors pick it up), and
   only then turn the flag off. A true
   `Strict-Transport-Security: max-age=0` must be served by the edge. Starting small (step 2) is
   what keeps this recoverable; a policy already on the preload list cannot be rolled back this way.

### Non-browser clients must send an Origin

With the flag on, a request counts as https, and Django's CSRF check for an https request with
**no `Origin` header** falls back to the `Referer` header. nginx blanks the `Referer` on its way to
Django, so the fallback fails and the POST is refused (403), token or not. Browsers always send
`Origin` on a POST, so the SPA is unaffected. A script or `curl` calling `/graphql/account` or
`/graphql/admin` must send `Origin: https://<host>` along with its CSRF cookie and header. The
native `/v1` routes need none of this.

### Verify after deploying

- `curl -si https://<host>/graphql/csrf` shows `Strict-Transport-Security` (with the values you
  chose in the HSTS section above).
- Sign in from a browser: the `/graphql/account` POST returns 200, not 403.
- Django: `curl -si http://<django-internal-host>:8000/graphql/csrf -H 'X-Forwarded-Proto: https'`
  from outside the proxy is **unreachable** (rule 2). If it answers, the flag is unsafe in that
  environment until that is fixed.
- The marketing nginx container: `curl -si http://<marketing-container-or-host-port>/graphql/csrf
  -H 'X-Forwarded-Proto: https'` from outside the edge must be unreachable, or must not return
  `Strict-Transport-Security`. If it answers as secure, anyone who can reach the container can
  claim https.
- Optionally rehearse the nginx map without the stack: run the image with `nginx -t` against
  `implementation/marketing/nginx.conf`, and a server that echoes `$selahcue_client_proto`, then
  send no header, `https`, `http` and a junk value; expect `http`, `https`, `http`, `http`. The
  map's shape and those outcomes are also pinned by `tests/test_nginx_forwarded_proto.py` in the API
  suite.

The native `/v1` routes (`POST /v1/sessions`, `POST /v1/activations:with-session`) are
`csrf_exempt` and unaffected either way.

---

## 6d. Database migrations — deploy order (Platform API)

**Nothing in this repository runs `migrate` for you.** The API image ends in `manage.py
runserver`, the compose file does the same, and no workflow, Makefile target or script applies
migrations to a deployed database. **How your deploys sequence `migrate` is not known to the
engineering team; confirm it before the first release that contains a column drop.** (Owner
question, ClickUp 86ak5mn0m.)

Most migrations only add things and can run beside the running release. A **column drop cannot**.
The first one is `selahcue_accounts` 0004, which removes `CustomerOrg.device_limit`
(ClickUp 86ak5mn0m). Measured on Postgres 16.2 with 10,002 organisations and 32,000 keys:

- The `ALTER` takes an `ACCESS EXCLUSIVE` lock for about 3 ms and rewrites nothing.
- The **previous** release cannot run against the migrated schema: every organisation read
  fails (`column selahcue_accounts_customerorg.device_limit does not exist`), including the join
  device activation uses, and so does creating an organisation.
- The **new** release cannot create an organisation against the old schema (the column is
  `NOT NULL` with no database default), so the new code must not run before the migration.
- The `ALTER` waits for any open transaction that touched the table, and while it waits every
  ordinary query on that table queues behind it. An idle reader holding the table for 3 s held
  up organisation traffic for 2.67 s.

**Deploy a release that drops a column, in this order:**

1. Stop the old instances.
2. Migrate, with a short lock timeout so a long reader cannot queue all organisation traffic:
   `PGOPTIONS='-c lock_timeout=5000' python manage.py migrate` (5 s; if it times out, nothing was
   changed, so find the long reader and run it again).
3. Start the new release.

**Roll back** the same migration by migrating down **before** starting the old image:
`PGOPTIONS='-c lock_timeout=5000' python manage.py migrate selahcue_accounts 0003`. This puts the
column back (about 12 ms) with the value 1 for every organisation; the old release only displays
it in the admin console, and activation never read it. Only then start the old image.

**If the API ever runs more than one instance at once during a deploy** (a rolling or blue/green
release), a column drop must be split into two releases: the first makes the column nullable (or
gives it a database default) and stops reading it, the second drops it. Delaying the drop alone
does not work, because of the `NOT NULL` point above.

---

## 7. What must never be committed

- The `.p12` certificate, its password, or any exported private key.
- App-specific passwords and App Store Connect `.p8` keys.
- `SECRET_KEY`, `SQL_PASSWORD`, or any production database credentials.
- NDI SDK **headers and libraries** are the exception: the Windows headers and the macOS dylib are
  committed deliberately (the latter via LFS) under the redistribution terms in §2.

If a signing credential leaks, revoke the certificate at
[developer.apple.com](https://developer.apple.com/account/resources/certificates/list) immediately —
anything signed with it is attributed to you.
