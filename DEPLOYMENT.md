# Deploy SelahCue with Coolify

This runbook is for the release operator. Deploy the API at `https://api.selahcueapp.com` and the website at `https://selahcueapp.com`. Publish only verified installers under `https://selahcue-installers.sfo3.digitaloceanspaces.com`. The owner selected a controlled pilot with cloud access manually enabled for selected churches. The deployment-readiness deadline is 15 November 2026 at 16:36 UTC (17:36 Africa/Lagos). Set the cohort and licence start/end times during manual provisioning. Unrestricted self-service cloud onboarding is outside this pilot scope.

## Release prerequisites

Pin the approved source commit for each API, website and desktop build. Record the API image digest, website image digest and installer hashes. Use matching API and website revisions and promote only the combination exercised on staging.

- Coolify with access to the repository or an image registry, a Docker private network with service discovery, and a TLS proxy for both public domains. Arrange DNS and certificate issuance before exposing the account flow.
- PostgreSQL with durable storage, a dedicated app database and application role with migration permissions. The local stack uses PostgreSQL 16. Production requires row locking for activation and licence changes.
- A private, authenticated Redis instance with separate logical DBs for the shared cache (DB 1) and Celery broker/result backend (DB 2). The local stack uses Redis 7. Keep broker jobs durable across restarts. Access to the broker can expose email credential tokens or let a caller submit tasks. Restrict access to the application network and authorised operators. Use TLS wherever the connection crosses an untrusted network.
- An SMTP account with STARTTLS, a verified From address/domain and an operator-controlled mailbox for email verification and password reset tests. Allow outbound SMTP from the worker.
- A DigitalOcean Spaces bucket in SFO3 with upload access for the release operator, immutable object paths and anonymous read for the verified release objects. Keep uploads, backups, staging artefacts and credentials private. The release operator holds the Spaces upload credentials. The API and website serve public download links without credentials.
- A durable secret store for the API keys, database, Redis and SMTP credentials. Use dedicated provider projects and scoped credentials for the pilot. Verify billing, model access, limits, expiry and revocation in those projects before admitting participants.
- Native build and clean install hosts for Windows x64, macOS arm64 and x86_64, and Ubuntu 24.04 x86_64. Use the pinned toolchain and fresh build directories. Record exact operating system, architecture and version coverage.

### Source status before enabling cloud features

The API source supports Django account sessions, licence activation and refresh, signed entitlement issuance, catalogue migrations, asynchronous mail and maintenance jobs. The API image uses locked Gunicorn 27.0.1 for the WSGI app. Coolify startup, ingress and service acceptance still need verification.

The Windows, macOS and Ubuntu packaging baselines use local STT. The cloud pilot still needs compiled public entitlement trust, an integrated native account and cloud journey, API grants, usage ledger and reconciliation, and provider and native acceptance. Build and test fresh installers after those changes land. The website keeps standard desktop downloads disabled until the verified immutable links are ready.

See the [configuration reference](deployments.md), [operations and credentials guide](docs/ops/DEPLOYMENT.md), and [direct-provider release decision](docs/superpowers/specs/2026-11-14-public-cloud-release-boundary.md).

## Runtime environment

Set these variables as runtime values in Coolify. Use identical Django, database and broker settings for the web, worker, beat and migration services where applicable. The website is a separate nginx image and uses no Django secrets. Use separate secrets and data stores for staging and production.

| Variable | Required for deployment and default |
|---|---|
| `ENVIRONMENT`, `DEBUG` | Set `ENVIRONMENT=prod` and `DEBUG=0`. Use `staging` on the staging installation. Defaults are `dev` and off. |
| `SECRET_KEY` | Required secret. Generate a strong random key and keep it stable across Django processes and redeployments. It also peppers fingerprints for licence keys, device tokens, account sessions and credential tokens. Changing it invalidates fingerprints. |
| `DJANGO_ALLOWED_HOSTS` | Set `api.selahcueapp.com selahcueapp.com` for the two public Host values. Defaults to local/test names. Use exact names without schemes. Set the health-check Host to an allowed value. |
| `FRONTEND_BASE_URL` | Set `https://selahcueapp.com` without a trailing slash. Set on web and worker. Used in verification and password-reset emails. Defaults to `http://localhost:2000`. |
| `SELAHCUE_TRUST_FORWARDED_PROTO` | Defaults to off. Set `1` once every ingress path overwrites `X-Forwarded-Proto` at the TLS edge and only trusted services can reach Django directly. |
| `SELAHCUE_TRUSTED_PROXY_COUNT` | Defaults to `0`. Set to the verified trusted hop count of the routes that share a deployment. It controls client-IP extraction for app throttles. See the topology check below. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Leave empty when the browser Origin and forwarded Host match. If your proxy intentionally changes the Host, list the exact HTTPS origins. Defaults to empty. |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Default to true with debug off. Keep on for HTTPS. |
| `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | Defaults with debug off are `31536000`, true, true. Use a short ramp-up and leave includeSubDomains/preload off during TLS validation. Revisit the policy once all in-scope hosts use HTTPS. |
| `SELAHCUE_TRUST_ACTOR_HEADERS`, `SELAHCUE_CORS_ALLOWED_ORIGINS` | Leave the former off and the latter empty. Actor headers are a dev-only bridge. The CORS setting is read without middleware to enforce it. |
| `SQL_ENGINE`, `SQL_HOST`, `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD` | Set `SQL_ENGINE=django.db.backends.postgresql`, the private database host/name/user and a strong database password. The engine and password are checked at startup outside dev. |
| `SQL_PORT`, `DB_CONN_MAX_AGE` | Optional. Defaults `5432` and `60` seconds. |
| `CACHE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Set private authenticated Redis URLs. Use DB 1 for cache and DB 2 for broker and results. Default cache is process-local and broker/results default to `redis://redis:6379/2`. Treat URLs containing credentials as secrets. |
| `CACHE_SOCKET_CONNECT_TIMEOUT`, `CACHE_SOCKET_TIMEOUT`, `CELERY_BROKER_SOCKET_CONNECT_TIMEOUT`, `CELERY_BROKER_SOCKET_TIMEOUT` | Optional. Each defaults to `0.5` seconds, accepted range `0.05`–`10`. Set timeout values through the named variables. |
| `CACHE_CIRCUIT_FAILURE_THRESHOLD`, `CACHE_CIRCUIT_COOLDOWN` | Optional. Defaults to `3` failures and a `5` second cooldown. Bounds are `1`–`100` and `0.1`–`60` respectively. |
| `CELERY_TASK_ALWAYS_EAGER`, `CELERY_TASK_EAGER_PROPAGATES` | Leave unset. These controls are for tests and default off with eager disabled. |
| `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `DEFAULT_FROM_EMAIL` | Set the verified SMTP host, credentials and sender on the worker. Non-dev SMTP uses STARTTLS on port `587` by default. The sender default is `noreply@selahcue.com`. `DEFAULT_EMAIL` is optional and defaults to `info@firstpavitech.com`. |
| `SELAHCUE_ENTITLEMENT_SIGNING_KEY` | API-only secret required to issue signed manifests. Standard base64 encoding of exactly 32 random bytes. Startup and CSRF smoke checks can succeed with this unset. |
| `ACCOUNT_SESSION_TTL_SECONDS`, `ACCOUNT_EMAIL_VERIFY_TTL_SECONDS`, `ACCOUNT_PASSWORD_RESET_TTL_SECONDS` | Optional. Defaults `2592000`, `86400`, `3600`. The session TTL is independent of the licence and pilot window. |
| `ACCOUNT_LOGIN_LOCKOUT_THRESHOLD`, `ACCOUNT_LOGIN_LOCKOUT_SECONDS`, `ACCOUNT_MIN_PASSWORD_LENGTH` | Optional. Defaults `5`, `900`, `10`. |
| `ACCOUNT_RESEND_MIN_SECONDS`, `ACCOUNT_RESET_REQUEST_MIN_SECONDS` | Optional. Defaults `0.4` and `0.1`. Tune only against measured request behaviour. |
| `SENTRY_DSN` | Defaults to empty. The inspected API reads this variable and has no Sentry integration. |
| `SELAHCUE_PILOT_REGISTRATION_ENABLED`, `SELAHCUE_PILOT_GRANT_ENABLED` | Leave both off for the manual cohort flow. These flags belong to the earlier n8n/Sheets and private download flows. |
| `VITE_API_BASE_URL`, `SELAHCUE_API_ORIGIN` | Leave unset for production. The former defaults to a relative `/graphql/account` request. The latter is read by the Vite development proxy. |

The disabled registration flow also reads `SELAHCUE_PILOT_N8N_TOKEN`, `SELAHCUE_PILOT_RECEIPT_KEY`, `SELAHCUE_PILOT_FINGERPRINT_KEY`, `SELAHCUE_PILOT_SHEET_ID`, `SELAHCUE_PILOT_SHEET_TAB`, `SELAHCUE_PILOT_SHEET_ROW_CAPACITY`, `SELAHCUE_PILOT_APPROVED_NOTICE_VERSIONS`, `SELAHCUE_PILOT_COLLECTION_OWNER`, `SELAHCUE_PILOT_RETENTION_DAYS`, `SELAHCUE_PILOT_SHEET_LAYOUT_PROTECTED`, `SELAHCUE_PILOT_RECEIPT_TTL_SECONDS` and `SELAHCUE_PILOT_EXPIRES_AT`. The disabled private grants flow reads `SELAHCUE_PILOT_GRANT_N8N_TOKEN`, `SELAHCUE_PILOT_GRANT_STORAGE_TARGET`, `SELAHCUE_PILOT_GRANT_DOWNLOAD_ORIGIN`, `SELAHCUE_PILOT_GRANT_COHORT_ID`, `SELAHCUE_PILOT_GRANT_MANIFEST_PATH`, `SELAHCUE_PILOT_GRANT_MANIFEST_SHA256`, `SELAHCUE_PILOT_GRANT_MAX_TTL_SECONDS`, `SELAHCUE_PILOT_GRANT_SIGNED_QUERY_KEYS`, `SELAHCUE_PILOT_GRANT_SIGNING_REQUIREMENTS` and `SELAHCUE_PILOT_GRANT_REQUIRED_PLATFORMS` (default Windows, Ubuntu, macOS). Leave these unset for this release. See the [pilot registration contract](docs/release/pilot-registration/notice.json) and [private download grant contract](docs/release/pilot-download-grants.md).

Populate the cloud settings from the merged release revision once the owning code exists. Scope long-lived provider keys to the server processes that mint or reconcile credentials. An OpenAI administrative key belongs only to the server process administering or reading usage of that project. The website receives no provider keys. Installers contain the public API address and public entitlement verification key. At runtime, the operator gets SelahCue account/device credentials and short-lived provider credentials through authenticated flows.

## Entitlement signing key

On a trusted operator machine or restricted shell, generate `SECRET_KEY` and the entitlement seed separately. These commands print secret values. Run them in a private terminal with logging disabled, then store the results directly in the approved secret store.

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
python3 -c 'import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode("ascii"))'
```

Set `SELAHCUE_ENTITLEMENT_SIGNING_KEY` in the API runtime. Inside that image you can derive the raw Ed25519 public key and its ID without printing the seed.

```sh
python manage.py shell -c 'from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat; from selahcue_api.apps.entitlements.signing import load_signing_key, derive_key_id; public = load_signing_key().public_key(); print(public.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()); print(derive_key_id(public))'
```

Compile those 32 public bytes into the desktop release's trusted key set. The key ID is the first eight hex characters of SHA-256 over the raw public key bytes. Confirm the exact packaged operator accepts a manifest from this API and rejects a manifest signed by a different key. Keep the seed out of Cargo/Tauri environments, build arguments, packages, logs and the repository. For a normal rotation, ship clients with both public keys, wait for adoption, switch the API to the new seed, then remove the old public key in a later client release. Existing offline manifests can remain valid until their licence expires. Retain an encrypted backup of the initial key and the record of key IDs used by each release. See [signing operations](docs/ops/DEPLOYMENT.md#6a-entitlement-signing-key-platform-api).

## Deploy and verify the platform

1. Provision PostgreSQL and Redis with persistent volumes or managed services. Create the separate app database and database role. Confirm private DNS and connectivity from the containers. Set the runtime values above.
2. Build the API and website from the same reviewed checkout. The API Dockerfile uses `implementation/api` as its build context. The website uses the repository root because it copies the pilot notice from `docs/release`. For a private baseline build, the checked-in Dockerfiles accept these commands from the root.

   ```sh
   docker build -f implementation/api/Dockerfile implementation/api
   docker build -f implementation/marketing/Dockerfile .
   ```

   The API image starts `gunicorn --config gunicorn.conf.py selahcue_api.wsgi:application` on `0.0.0.0:8000`. Its baseline is two synchronous workers with 30-second worker and graceful shutdown timeouts and no preloading. Gunicorn disables the local control socket and request access logs. Error logs go to stderr and can include request paths and query strings on exceptions. Restrict log access and redact sensitive fields before exporting those logs. Keep Gunicorn’s forwarded-header trust disabled and use Django’s explicit setting at the verified proxy boundary. Give Coolify at least 30 seconds to stop the container so Gunicorn can finish its graceful shutdown. Size any Coolify worker override from staging measurements.

   The checked-in `implementation/docker-compose.yml` is a development stack with an explicit Django `runserver` command, source mounts, host port mappings, example passwords and MailHog. For a self-hosted Docker host without Coolify, `implementation/docker-compose.prod.yml` runs these same images and processes behind a Caddy TLS edge. See [the Docker Compose runbook](implementation/deploy/README.md).

3. In Coolify, create separate processes from the same API image. Expose only the API and website through the proxy. Use a single beat instance initially. The Django and Celery working directory is `/usr/src/app`.

   | Process | Image, startup and routing |
   |---|---|
   | API web | Use the API image’s default Gunicorn command, HTTP :8000 and private Docker alias `api`. Route the API hostname to this service. |
   | Website | Marketing image, nginx HTTP :80. Route the website hostname to this service. Its `/graphql/` location resolves `api:8000` through Docker DNS. Put it on the API's private network with that service alias. |
   | Worker | API image with `celery -A selahcue_api worker --loglevel=info --concurrency=2`. Private and no HTTP route. |
   | Beat | API image with `celery -A selahcue_api beat --loglevel=info --pidfile=/tmp/celerybeat.pid --schedule=/tmp/celerybeat-schedule`. Private and no HTTP route. Currently schedules hourly licence revocation propagation and a nightly credential sweep. |
   | Migration | A one-off container on the same private network, API release image and database settings. Run once per deployment before starting the release processes. |

4. Point the two DNS names at the Coolify ingress, obtain valid certificates and redirect HTTP to HTTPS. Keep the website account browser traffic same-origin. At the ingress strip incoming `X-SelahCue-*` identity headers and control forwarded headers. Rate-limit `/graphql/account` at both reachable ingresses and cover the native `/v1/sessions` and `/v1/activations:with-session` paths. Retain account and device rate limits in the application. Several app throttles degrade during Redis outages. See [edge rules and cache behaviour](docs/ops/DEPLOYMENT.md#6b-ops-requirements--ingress-throttling-and-redis).

   Native calls reach Django from the public API edge and browser account calls go through website nginx. These paths can have different proxy depths. Check the effective `X-Forwarded-For` chain on both. Where one settings value cannot resolve both client IPs correctly, normalise the chain at trusted ingress or use distinct web services with the correct per-route setting. Keep throttles at the edge until the application sees the intended address on both routes. Enable forwarded-proto trust only after verifying the boundary. Block or restrict the staff graph at the edge while the staff authentication path is unavailable.

5. Back up PostgreSQL before migrating an existing instance. Save the pre-deploy image digests and secret versions. Inspect the migration plan in the new image. For incompatible schema changes, stop old writers before migrating. Take a maintenance window if there is any difference in the migration compatibility of the two releases.

   ```sh
   python manage.py check
   python manage.py migrate --plan
   PGOPTIONS='-c lock_timeout=5000' python manage.py migrate
   python manage.py migrate --check
   ```

   The migrations seed Free, Core and Pro. They carry weekly transcription allowances of 20, 50 and 80 minutes and note allowances of 1, 5 and 10. The current seed has one device per plan and restrictive paid output limits pending launch configuration. Catalogue migration `0007` reseeds historical references and is irreversible through Django. Restore the matching pre-migration backup if that change must be rolled back. See [migration operations](docs/ops/DEPLOYMENT.md#6d-database-migrations--deploy-order-platform-api).

6. Start web, worker and beat after the database is current. From a runtime container run the checks below. Run the cache probe once per deployment. The worker ping needs a worker attached to the configured broker. On staging, verify beat dispatches a scheduled maintenance task and the worker completes it. Verify email delivery through the account flow below.

   ```sh
   python manage.py migrate --check
   python manage.py shell -c 'from django.core.cache import cache; from uuid import uuid4; key = f"deploy:{uuid4()}"; cache.set(key, "ok", 30); assert cache.get(key) == "ok"; cache.delete(key)'
   celery -A selahcue_api inspect ping --timeout 5
   ```

7. Check both TLS paths from outside the server.

   ```sh
   curl -fsS -D - https://api.selahcueapp.com/graphql/csrf
   curl -fsS -D - https://selahcueapp.com/graphql/csrf
   curl -fsS -o /dev/null https://selahcueapp.com/
   ```

   Each CSRF route should return 200, `{"ready": true}`, a Secure CSRF cookie, and `Cache-Control: no-store`. Check the expected HSTS header on HTTPS once the policy is enabled. Use `GET /graphql/csrf` as the web liveness check on port `8000` with an allowed Host header, such as `api.selahcueapp.com` in production. The probe checks HTTP routing and response. A ready deployment also needs passing database and cache checks, responding worker and beat processes, delivered email and a successful real account/device journey. Keep the general `/graphql/account` response out of shared caches. Configure nginx and the Coolify proxy to omit request query strings, cookies, authorization headers, bodies and token-bearing referrers from access logs. Verify log output with a synthetic token on both ingress paths. Review email logging for verification and reset links.

## Manual pilot accounts and licensing

Use the operator-approved set of churches and the intended start/end instants. The website's existing `/signup` and verification flow can create a test or invited customer and its first customer Admin. Control access to cohort onboarding during the pilot. Public signup currently creates a Trial organisation only. A licence must be issued separately, and provider admission must use the approved organisation record and its activated device. Use the approved edge/invitation controls or leave the signup surface gated during the internal test. The earlier pilot registration and grant flags do not implement cloud admission.

For each approved participant, check the verified customer user belongs to the intended organisation. Assign the approved catalogue plan and issue a time-bounded `PILOT` licence for that exact organisation. Record the accountable operator, reason and ID of the issue request. Ask the participant to sign in as the customer Admin once the public operator integration lands. Account-based activation uses that person's licence and consumes a device slot without requiring an enrolment key.

The inspected API does not authenticate production staff to `/graphql/admin`. A Django `createsuperuser` account does not create a SelahCue customer or a staff GraphQL actor. Use the reviewed server-only provisioning command if one lands. For an authorised private pilot fixture, the existing catalogue and licence service can also be used from a restricted Django shell. The following source-based example must first be tested on the staging image. Substitute only the approved cohort times, IDs and plan. Use stdin prompts or an audited script for private fields. Print only the licence ID, never the issued full key.

```python
from datetime import datetime
from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.license_keys.services import GenerateLicenseKeyData, generate_license_key
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

org = CustomerOrg.objects.get(pk=input("Verified cohort organisation ID: ").strip())
actor = ActorContext(
    kind=ActorKind.STAFF,
    actor_id=input("Accountable operator ID: ").strip(),
    staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
)
result = generate_license_key(actor, GenerateLicenseKeyData(
    idempotency_key=input("Stable pilot issuance request ID: ").strip(),
    customer_id=str(org.pk),
    key_type="PILOT",
    feature_scope=input("Approved feature scope: ").strip(),
    plan_code=input("Approved catalogue plan code: ").strip().upper(),
    starts_at=datetime.fromisoformat(input("Pilot start with UTC offset: ").strip()),
    expires_at=datetime.fromisoformat(input("Pilot end with UTC offset: ").strip()),
    timezone=org.timezone,
    seat_limit=org.seat_limit,
    territory=org.country,
    reason=input("Pilot issuance reason: ").strip(),
))
print(result.license_key.pk, result.created)
```

If the cohort uses manual provider provisioning, prepare the organisation-to-provider mapping and approved limits in the relevant locked-down projects, then record the mapping through the release's server-side provisioning path. Keep unattended provisioning off until the supported provider limits, rate bounding, retries and failure handling are verified. Do not grant cloud access just because a Trial account exists. No deployed batch onboarding or provider reconciliation procedure is documented for these source revisions.

## Package and publish

1. Build the exact reviewed cloud-enabled commit with the public API origin and compiled entitlement public key. Build in isolated environments without provider, admin or development entitlement credentials. Preserve base presentation, output, local fallback and data protections.
2. Use the checked-in native build definitions as packaging baselines. The Windows and Ubuntu workflows dispatch on `main` and produce private CI artefacts. Their current commands enable local STT. A cloud release must use the landed public cloud build path and pass the same native checks.

   | Platform | Packaging and evidence |
   |---|---|
   | Windows x64 | The [Windows installer workflow](.github/workflows/windows-installer.yml) builds the NSIS `*-setup.exe`, real output sidecar and NDI dependencies. Follow its Rust/Tauri, MSVC, WebView2, NDI import library and Portable Whisper setup. Record actual Authenticode status and verify install, run and uninstall on clean Windows. Unsigned Windows distribution requires the release's explicit signing decision and matching disclosure. |
   | macOS arm64/x86_64 | Use Xcode, both Rust targets, the pinned Tauri CLI and the licensed universal NDI SDK staged by `scripts/fetch_ndi_sdk.sh`. The [macOS packaging receipt](docs/delivery/evidence/public-release-macos-20261114.md) documents the local-STT baseline and `scripts/build_macos_installer.py --tauri … --output …`. Inspect the actual DMG with `hdiutil verify`, both app and output slices with `lipo -archs`, and the mounted app with `codesign --verify --all-architectures --deep --strict`. Disclose **ad-hoc signed app, unsigned DMG, no Apple Developer ID signature and no notarization**. Record observed Gatekeeper behaviour with a browser-downloaded copy. Test native Apple Silicon and Intel or state the exact emulation coverage separately. |
   | Ubuntu 24.04 x86_64 | The [Linux installer workflow](.github/workflows/linux-installer.yml) lists GTK/WebKitGTK and other system dependencies and pins the Tauri CLI and driver. `scripts/build_linux_installer.py` packs a `.deb`, verifies ELF dependencies and scans unpacked binaries. Install the candidate with `sudo apt install ./<installer>.deb` in a clean Ubuntu 24.04 environment. Test operator, output, runtime closure, upgrade and uninstall. |

3. Record source SHA, version, platform/arch, build run, selected features, public entitlement key ID, signature state, byte count and SHA-256 of the exact candidate. Run `python3 scripts/installer_secret_scan.py --self-test` and the platform's package scan on the final bundle and unpacked or mounted executable payload. Run the release development-key exclusion check. Record the positive controls and scan results. Known-marker scans complement build environment and input custody checks. Publish only the candidate that passed native acceptance.
4. Upload using the release operator's write credentials to a new versioned, digest-specific key in the approved Space. Upload the matching checksum list or release manifest. Apply anonymous read only to the release objects. Keep their keys immutable so a checksum continues to name the bytes that were tested. Set the appropriate download content type and attachment name, and keep the bucket root, upload credentials and unpublished artefacts outside the public listing. Use the real filename captured in the release receipt for the website link.
5. Download each object from an external machine without credentials using its exact HTTPS object URL. Verify the SHA-256 with `sha256sum` on Linux, `shasum -a 256` on macOS, or `Get-FileHash -Algorithm SHA256` on Windows. Compare the published checksum and byte count to the independently retained build receipt. Verify the website links download those bytes and display the correct version, architecture and signing status. Set the general download URLs in the release website and verify that both its homepage and download page route participants to the intended artefacts.

## Acceptance before inviting the cohort

- **Website and mail** — On the real website over HTTPS, verify sign-up for an approved test mailbox, delivery, verification, sign-in, sign-out and password reset with the production SMTP/worker path. Verify CSRF on the real browser origin. Confirm unapproved identities have no cloud access.
- **Native account and activation** — Install the publicly downloaded candidate on each target. Sign in from the actual operator UI with no environment setup. Activate, check the licence in the UI, restart and confirm the expected persisted state. Verify manifest signature enforcement, device-limit refusal, and online refusal after revocation and expiry. Exercise the required offline presentation path using the valid cached entitlement.
- **Cloud transcription and notes** — Use a synthetic sermon fixture. Confirm the desktop uses the SelahCue API for entitlement, allowance and expiring credentials, sends audio directly to Deepgram, and sends note input directly to OpenAI for the qualified flow. Verify provider-observed records reconcile to the correct church. Exercise provisional vs reconciled usage, weekly allowance and Monday reset in the account timezone, concurrent grants, refusal on depletion, provider timeout and the allowed note retry. Record cost for representative normal notes including the retry against the USD 0.25 target. Verify actual provider abuse limits separately from normal cost.
- **Degradation and closing the pilot** — Exercise an unavailable provider and a revoked device. Presentation and the supported fallback paths should behave as specified for the release. Confirm the procedure and exact cutoff timestamp to stop admitting new usage when the window ends. Test the actual control and account/licence state used for the cutoff.
- **Evidence** — Record the deployed API/website revisions, three downloaded hashes, OS coverage, UTC time, checks and outcomes. Capture redacted request IDs and usage counts. Store neither account data nor credentials, audio or sermon notes in the release evidence.

## Backup, rollback and recovery

- Before each rollout, take an encrypted PostgreSQL snapshot or logical dump and rehearse restoring into an isolated database with matching code and secret versions. Record the source revision, database recovery point and tested restoration time. Protect backups of Redis if retained, since queued mail jobs can contain credential tokens. Back up `SECRET_KEY`, the entitlement seed and the release receipts separately in restricted storage.
- For a faulty installer or website, withdraw its website link and remove anonymous access to the affected object as needed. Keep the exact bytes and hashes privately for diagnosis. Point at an earlier release only after verifying it against the running API, active entitlement keys and provider policy.
- For an API failure, stop admitting new pilot cloud usage at the verified control, stop writes and scheduled jobs if necessary, then restore matching service and database revisions. A compatible database can remain in place for an application-only rollback. For incompatible or irreversible migrations, restore the tested database backup before starting the previous revision and account for writes after the backup. Confirm web routes, email, worker/beat, device activation and entitlement verification after rollback.
- For provider credential exposure, halt new grants, revoke the affected credential at the provider and verify outstanding session expiry or cancellation using that provider's supported controls. Do not infer cancellation from disabling a website or API route. If the signing seed is exposed, arrange replacement clients and treat already-issued offline manifests as valid until their licence expires or the client trust is replaced.
