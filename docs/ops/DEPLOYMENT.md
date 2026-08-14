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
(`api/.env.sample` there). A full sample lives at `implementation/api/.env.sample`.

| Variable | Default | Production |
|----------|---------|-----------|
| `ENVIRONMENT` | `dev` | `staging` / `prod`. Gates the mail backend, Sentry, and the `SECRET_KEY` requirement |
| `SECRET_KEY` | dev-only fallback | **Required — the app refuses to boot when `ENVIRONMENT != dev`** |
| `DEBUG` | `0` | Leave `0` — see the warning below |
| `DJANGO_ALLOWED_HOSTS` | `localhost 127.0.0.1 testserver` | **Required. Space-separated** (commas tolerated) |
| `SQL_ENGINE` | `…backends.sqlite3` | `django.db.backends.postgresql` — row-locking is required, see below |
| `SQL_DATABASE` / `SQL_USER` / `SQL_PASSWORD` / `SQL_HOST` / `SQL_PORT` | SQLite path / `postgres` / `postgres` / `localhost` / `5432` | **Required** for Postgres |
| `DB_CONN_MAX_AGE` | `60` | Tune to your pooling |
| `CELERY_BROKER_URL` | `redis://redis:6379/2` | Point at the real Redis |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Point at the real Redis |
| `CACHE_URL` | empty → LocMemCache | **Set it.** `redis://…/1` — db **1**, never the broker's db 2. See §6b |
| `SELAHCUE_TRUSTED_PROXY_COUNT` | `0` | Number of *your own* proxies in front of Django. See §6b |
| `MAIL_HOST` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` | mailhog on `:1025` in dev | **Required** to send email |
| `DEFAULT_FROM_EMAIL` / `DEFAULT_EMAIL` | SelahCue defaults | Set to your verified sending domain |
| `SENTRY_DSN` | empty | Set in staging/prod only; never locally |
| `SELAHCUE_CORS_ALLOWED_ORIGINS` | empty | Comma-separated origins for the web client |
| `SELAHCUE_TRUST_ACTOR_HEADERS` | follows `DEBUG` | **Must be false.** See below |
| `SELAHCUE_ENTITLEMENT_SIGNING_KEY` | **none** | **Required** to issue offline entitlements. See §6a |
| `SECURE_HSTS_SECONDS` | `31536000` when not debug | Keep the default |

> **`SQL_ENGINE` must be Postgres in production, not merely preferred.** The DEC-004 device
> instance limit is enforced with `select_for_update`, which SQLite silently no-ops
> (`has_select_for_update = False`). On SQLite two concurrent activations can both observe
> `active_devices = 0` and exceed `device_limit`. The guard is not wrong — it simply has no
> effect without a row-locking backend.
| `ACCOUNT_SESSION_TTL_SECONDS` | 30 days | Policy choice |
| `ACCOUNT_EMAIL_VERIFY_TTL_SECONDS` | 24 hours | Policy choice |
| `ACCOUNT_PASSWORD_RESET_TTL_SECONDS` | 1 hour | Policy choice |
| `ACCOUNT_LOGIN_LOCKOUT_THRESHOLD` | `5` | Policy choice |
| `ACCOUNT_LOGIN_LOCKOUT_SECONDS` | `900` | Policy choice |
| `ACCOUNT_MIN_PASSWORD_LENGTH` | `10` | Policy choice |

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

> **`DEBUG` controls more than error pages.** `SELAHCUE_TRUST_ACTOR_HEADERS` defaults to the
> value of `DEBUG`, and when true the API accepts caller-supplied identity headers — turning on
> debug in production would let a client assert any actor. Debug also enables the GraphQL IDE and
> introspection, and zeroes HSTS. Set `DEBUG=0` explicitly rather than relying on the
> default.

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

Three properties the *deployment* must hold. None of them can be fixed in application code:
each is a promise the edge makes that the app then relies on. Deploying without them does not
fail loudly — it just quietly removes a control the app assumes is there.

### The ingress must strip inbound `X-SelahCue-*` headers

Do this **before** `SELAHCUE_TRUST_ACTOR_HEADERS` is ever set true anywhere, including staging.

When that flag is on, the API reads the actor's identity — who they are and what they may do —
from request headers. It has no way to distinguish a header your load balancer set from one the
client typed: by the time Django sees them they are the same bytes. So if the flag is on and the
ingress passes client headers through, any caller can assert any actor, including staff
permissions. That is total authentication bypass, not privilege escalation at the margins.

The safe order is: strip at the edge first, verify a forged header does not survive to the app,
*then* enable the flag. The default is off and follows `DEBUG` (§6) — keep it that way until the
strip rule is deployed and tested.

### Per-IP flood protection belongs at the edge

The app carries a fixed-window rate limiter on the `/v1` device-auth endpoints (activation,
licence refresh, entitlement manifest), keyed on `(endpoint, client IP)` with the budgets in
`SELAHCUE_THROTTLE_*`. Treat it as the **second** layer, never the only one.

It runs *inside* Django, so a request must be accepted, routed and middleware-processed before it
can be refused — a flood large enough to matter has already consumed a worker slot by then. It
also **fails open** by design: if Redis is unavailable the limiter allows the request and logs,
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
