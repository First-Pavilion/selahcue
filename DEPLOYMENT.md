# Deploy SelahCue with Coolify

This runbook covers the manual release of public self-service Free. Paid subscriptions are deferred. The owner deploys the API at `https://api.selahcueapp.com` and the website at `https://selahcueapp.com`. The installer origin is `https://selahcue-installers.sfo3.digitaloceanspaces.com`.

These instructions are based on main `9dd2105a356e39f6a369d7b2fb4dd1a19b3870bb`. The account stack and native Free activation have source paths to rehearse. Public cloud delivery still needs integrated implementation and qualification. The checked-in website manifest is unpublished, and the current installer publisher requires cloud acceptance evidence before publication.

## Release prerequisites

- Arrange owner access to Coolify, the reviewed repository checkout or approved container registry, and DNS for both domains. Verify TLS issuance and the installed Traefik configuration before opening sign-up.
- Use durable PostgreSQL 16 and authenticated Redis 7 in the included Compose stack. Keep their ports private and back up the data off-host. PostgreSQL row locking enforces activation and licence limits. Redis uses DB 1 for cache and DB 2 for Celery broker and results, with AOF and a named data volume. Broker access can expose queued email tokens or allow task submission. Restrict it to the application network and authorised operators.
- Arrange an SMTP service with STARTTLS, a verified From address and an operator-controlled mailbox. Allow outbound SMTP from the worker. Keep staging and production data and credentials separate.
- Arrange a restricted secret store and recovery access for the Django, database, Redis, SMTP and entitlement secrets. Confirm authorised custody of the entitlement seed matching the final release packages before deploying.
- Arrange scoped release-operator access to the SFO3 Space. Keep credentials, unpublished files and backups private. Use a separate credential-free machine or process for public verification.
- Use clean native build and install environments for Windows x64, macOS arm64 and x64, and Ubuntu 24.04 x64. Pin their toolchains and capture exact OS, architecture and package coverage.

## Runtime environment

Use the checked-in [production environment template](implementation/deploy/production.env.example) as the input reference. Fill the required values and keep secrets in protected deployment and secret storage.

- **New, empty resource.** Bulk-import the example via **Environment Variables → Developer** only if the resource is new and its variable list is empty. Import the blank secret placeholders. Set the scopes and values for those secrets in Normal view as described below.
- **Existing or pre-populated resource.** In **Environment Variables → Normal**, reconcile the intended settings one variable at a time. Developer view saves the complete list and can remove omitted entries. Preserve the approved `API_IMAGE`, `WEBSITE_IMAGE`, `RELEASE_TAG`, database name and user, current HSTS policy and other existing overrides. Use Normal view to update locked entries. Leave a locked value blank when changing its scope only to keep the current value.

Before the first build and on each existing-resource preflight, use Normal view to set `SECRET_KEY`, `SELAHCUE_ENTITLEMENT_SIGNING_KEY`, `SQL_PASSWORD`, `REDIS_PASSWORD` and `MAIL_PASSWORD` to **Build time → Not available during build** and **Runtime → Available in the container**. Confirm the saved scope for each variable by name and record only the names and scope flags. Then lock any unlocked secret. New Coolify variables default to build availability. Git-based Compose can pass build-scoped variables as build arguments to services with build definitions. Locking hides the value in the UI and API. Build and runtime scopes are independent settings. [Coolify environment variables](https://coolify.io/docs/applications/configuration/environment-variables) · [Compose build arguments](https://coolify.io/docs/applications/builds/docker-compose#application-build-arguments)

| Compose input | Value and purpose |
|---|---|
| `API_DOMAIN`, `WEBSITE_DOMAIN` | Required. Use `api.selahcueapp.com` and `selahcueapp.com`, without schemes. Compose uses them for routing, Django allowed hosts, the API health-check Host and the HTTPS website URL in account email. |
| `SECRET_KEY` | Required. Generate a strong random Django key for this environment and keep it stable across deploys. It also protects fingerprints for licences, device tokens, sessions and account recovery credentials. Changing it invalidates existing fingerprints. |
| `SELAHCUE_ENTITLEMENT_SIGNING_KEY` | Required. Provision the authorised matching seed as described below. |
| `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD` | Database and role default to `selahcue`. Supply a strong database password. The internal host and port are `db:5432`. |
| `REDIS_PASSWORD` | Required. Use a strong hex password because Compose inserts it directly into the Redis URLs without escaping. |
| `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `DEFAULT_FROM_EMAIL` | Provide the SMTP host and verified sender. The port defaults to `587`. Username and password default to empty in Compose. Fill them for the chosen authenticated SMTP service. The template uses `noreply@selahcueapp.com`. |
| `ENVIRONMENT`, `DEFAULT_EMAIL` | `ENVIRONMENT` defaults to `prod`. Use `staging` for a staging installation. `DEFAULT_EMAIL` is optional and defaults to `info@firstpavitech.com`. |
| `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | Start a new resource at `300`, `0`, `0`. Ramp up to `31536000` seconds after verifying HTTPS. Review subdomain and preload settings separately. Preserve the approved HSTS policy on an existing resource. |
| `API_IMAGE`, `WEBSITE_IMAGE`, `RELEASE_TAG` | Optional image-reference inputs. Defaults are `selahcue-api`, `selahcue-website` and `latest`. Use an approved release tag. The file still declares both builds. Check how Coolify resolves the image and verify the digest actually deployed. |

Compose sets `DEBUG=0`, builds the database and Redis connection settings, and supplies the shared runtime environment for the API, maintenance worker, beat and migration. Keep the dev actor bridge, dev admin catalogue and both legacy pilot flags off. The website uses same-origin account requests and receives no Django or provider secrets. Keep browser CORS and Vite overrides unset for this flow. Additional settings in the [configuration reference](deployments.md) only reach a container if its service definition passes them through. The standard stack passes the two optional scheduling flags only to beat. See [scheduled work](#scheduled-work).

The website release manifest is copied into the website image at build time. The packaged desktop API origin is compiled as `https://api.selahcueapp.com`. Plan final-package acceptance around an authorised endpoint at that hostname. Record separate staging coverage if a staging build has a different compiled origin.

## Entitlement signing key

Use the authorised private Ed25519 seed matching the public trust compiled into the final release. `SELAHCUE_ENTITLEMENT_SIGNING_KEY` is standard base64 for exactly 32 bytes. The reviewed release trust and publisher expect key ID `e506b735`. Confirm authorisation for production use of its private seed. Compare the raw public key and key ID from the signer to the accepted trust in each package before rollout. A newly generated independent seed has a different public key. If the matching seed cannot be recovered with authorised custody, stop and review a client trust rotation before attempting to sign for those packages.

In the restricted API environment, derive only the public key and ID. The ID is the first eight hexadecimal characters of SHA-256 over the raw public bytes.

```sh
python manage.py shell -c 'from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat; from selahcue_api.apps.entitlements.signing import load_signing_key, derive_key_id; public = load_signing_key().public_key(); print(public.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()); print(derive_key_id(public))'
```

Keep the private seed in the API runtime environment and its restricted recovery store. The included Compose shares that runtime environment across API-image processes. Keep the seed out of build arguments, desktop packages, the website, logs and source control. Verify that the installed client accepts a manifest from this signer and rejects an untrusted signature. For planned rotation, ship clients with both public keys, wait for adoption, switch the API signer, and retire the old client trust in a later release. [Signing operations](docs/ops/DEPLOYMENT.md#6a-entitlement-signing-key-platform-api)

## Scheduled work

Run exactly one maintenance beat and the maintenance worker on the `celery` queue. By default beat schedules the minutely usage retention sweep, the hourly licence revocation cascade and the 03:30 credential sweep in Celery's configured time zone (UTC).

| Beat-only Compose input | Optional schedule |
|---|---|
| `SELAHCUE_BEAT_PROVIDER_PROVISIONING_ENABLED` | `providers.sweep` every five seconds on `provider_provisioning`. |
| `SELAHCUE_BEAT_PROVIDER_USAGE_ENABLED` | `usage.sweep` every minute on `provider_usage`. |

Leave both inputs unset or set them to `0` for the account stack. To enable a schedule, first deploy and verify its dedicated consumer and then set the matching input to `1` and recreate beat. Both inputs are independent of the public admission and provider creation flags. Usage reconciliation can run while public admission is disabled. Beat runs in the maintenance role without provider credentials or mounts. See the [configuration reference](deployments.md#provider-process-configuration) for the accepted values.

Rehearse the intended settings in bounded staging with its own broker and a defined stop time. Observe the provider queues across multiple intervals and record maintenance dispatch and worker completion. With both inputs off, confirm beat publishes neither provider sweep. With an input on, verify that its dedicated worker consumes the scheduled work. Stop staging beat at the end of the rehearsal.

To roll back a provider schedule, set its input to `0` and recreate beat. Check that new publishes for that schedule have stopped and reconcile outstanding jobs with the appropriate consumer before stopping it. Redis AOF can retain messages that were already queued. Account-only rollbacks need a version with the maintenance defaults or a verified maintenance scheduler before starting beat.

## Manual deployment control

On resource setup, keep the selected Git branch free of pushes until the following controls are saved and verified. In Coolify, go to **Advanced → Deployment → Auto deploy** and select **Manual deployments only**. GitHub App resources can default to deploy on push. Read back the setting on the production resource before proceeding, including on every later rollout.

The authenticated **Deploy Webhook** is a separate trigger that remains callable in manual mode. Verify that CI workflows, scheduled jobs and other integrations do not call it for this resource. The owner triggers the rollout from the dashboard after confirming the source ref resolves to the recorded release commit. Keep that ref fixed through checkout and confirm the commit in the deployment record. [Coolify automatic deployment controls](https://coolify.io/docs/applications/deployments/automatic-deployments#disable-automatic-git-deployments) · [GitHub App default](https://coolify.io/docs/applications/sources/github/auto-deploy#deploy-through-a-github-app)

## Deploy and verify the platform

1. **Pin the source and the deployment artefacts.** Record the exact reviewed API and website source revisions and installer source SHA. Test the intended combination on staging and record the resolved image digests. The API builds from `implementation/api`, and the marketing Dockerfile uses the repository root as its context. The API image starts Gunicorn on port 8000 and the website image starts nginx on port 80. Preserve the API's unprivileged, read-only service configuration and Compose's 40-second stop period for web and worker. Use the [production Compose](implementation/docker-compose.prod.yml). Its database and Redis hosts are the internal services `db` and `redis`. An external database or Redis deployment needs explicitly reviewed service wiring.

2. **Set up Coolify and the ingress.** Select the **Docker Compose** build pack, base directory `/implementation` and compose location `/docker-compose.prod.yml`. Apply [manual deployment control](#manual-deployment-control), then reconcile the [runtime environment](#runtime-environment) before any build. Leave **every Domains field empty** to avoid a second router without the Compose rules. Check the Traefik `http` and `https` entrypoints, `letsencrypt` resolver, DNS and certificates. The checked-in labels redirect HTTP, route the API hostname directly to Django and route the website's `/graphql/*` directly to Django. The rest of the website goes to nginx. The public application routers strip inbound `X-SelahCue-Actor-Id`, `X-SelahCue-Actor-Kind`, `X-SelahCue-Org-Id` and `X-SelahCue-Staff-Permissions`. The staff GraphQL router on both hosts rewrites to an unrouted path for a Django 404.

   The direct routes use one trusted proxy hop, `SELAHCUE_TRUSTED_PROXY_COUNT=1` and `SELAHCUE_TRUST_FORWARDED_PROTO=1`. Verify that the edge controls forwarded scheme and client address, preserves the public Host, and leaves Django unreachable by any direct public path. The trusted count is process-wide. A CDN, load balancer or the alternate nginx GraphQL proxy can produce paths with different trusted depths. If they share an API service, normalise the forwarded chains at trusted ingress to use one verified count. Otherwise route them to separate API services with the correct process setting for each service. Verify header replacement, the effective client IP and the forwarded scheme on both routes. Keep `DJANGO_CSRF_TRUSTED_ORIGINS` empty when the Origin and forwarded Host match. Use the [Compose deployment details](implementation/deploy/README.md) and [proxy and HSTS guidance](docs/ops/DEPLOYMENT.md#6c-ops-requirements--django-behind-a-tls-terminating-proxy).

3. **Apply and test edge controls before opening sign-up.** The Compose labels supply routing and HTTPS but have no per-IP rate limiter. Configure connection and request-rate limits on both public origins for reachable account and device routes. Cover `/graphql/account`, `POST /v1/sessions`, `POST /v1/sessions:revoke`, `POST /v1/activations:bound-with-session`, `POST /v1/activations:with-session`, `POST /v1/activations:bound`, `POST /v1/activations`, licence refresh and entitlement manifest. Keep Django's application throttles and verify the edge limiting and the actual client IP used by Django. Verify the staff 404 and identity header handling on both hosts.

   Signup also requires a healthy Redis limiter. The shipped defaults admit up to 500 attempts per fixed hour globally and 20 per trusted source. Check the named reset-trace skip alarm and the worker outage limits when tuning these values. [Signup admission and rollback](docs/ops/DEPLOYMENT.md#signup-admission)

   Exclude query strings, authorisation and Cookie headers, bodies and token-bearing referrers from logging and tracing. Exercise both origins with synthetic markers, including the website `/verify` and `/reset` landings. Check Traefik, nginx and application logs separately. The nginx safe logger and its landing-path exclusions cover nginx only. In the alternate nginx GraphQL layout, nginx also suppresses the upstream Referer header. Verify the deployed edge's handling on the direct Django routes and keep account responses out of shared caches. [Ingress and Redis guidance](docs/ops/DEPLOYMENT.md#6b-ops-requirements--ingress-throttling-and-redis)

4. **Review migrations before the owner deploys.** For an existing database, take an encrypted backup and record the current migration frontier, image digests and secret versions. In the new release image with the target settings, inspect `python manage.py check`, `python manage.py showmigrations --plan` and `python manage.py migrate --plan`. If the migration is incompatible with the running release, stop the old writers and scheduled jobs before migration. Allocate a maintenance window for a deployment needing this stop.

   Verify [scheduled work](#scheduled-work) on staging before the owner deploys the recorded revision from the Coolify dashboard. Verify the manual trigger policy and runtime-only secret scopes before selecting **Deploy**. Compose runs the one-off `python manage.py migrate --noinput` with `PGOPTIONS='-c lock_timeout=5000'`. Expect an exit code of zero before API, worker and beat can start. In the deployed API container confirm `python manage.py migrate --check` and record the actual frontier with `python manage.py showmigrations --plan`. Catalogue migration `0007` is irreversible through Django. Use the matching backup for rollback across it. [Migration operations](docs/ops/DEPLOYMENT.md#6d-database-migrations--deploy-order-platform-api)

5. **Check dependencies, mail and scheduled work.** Verify PostgreSQL and Redis health. Check a write/read/delete against the configured Django cache and ping the worker through the broker from the API container. Run one maintenance worker pool on the logical `celery` queue at the Compose default concurrency of two, and exactly one beat. Review the recorded staging dispatch and completion and confirm that the deployed services use the verified schedule.

   ```sh
   python manage.py shell -c 'from django.core.cache import cache; from uuid import uuid4; key = f"deploy:{uuid4()}"; cache.set(key, "ok", 30); assert cache.get(key) == "ok"; cache.delete(key)'
   celery -A selahcue_api inspect ping --timeout 5
   ```

6. **Check both public TLS routes.** From outside the server, confirm the HTTP redirects, then check the HTTPS responses, expected HSTS policy and website rendering.

   ```sh
   curl -fsS -D - https://api.selahcueapp.com/graphql/csrf
   curl -fsS -D - https://selahcueapp.com/graphql/csrf
   curl -fsS -o /dev/null https://selahcueapp.com/
   ```

   Both CSRF requests should return HTTP 200, `{"ready": true}`, a Secure CSRF cookie and `Cache-Control: no-store`. This route is an HTTP liveness probe. Exercise real browser CSRF on the same-origin account POST and complete the mail and device checks below to verify the account stack.

## Free account and activation acceptance

1. From the actual HTTPS website, sign up with a new operator-controlled mailbox. Signup creates a `TRIAL` organisation record and invites its first Admin. That internal state is part of account setup. The Free offering has no trial or payment step. Signup creates no licence. Verify actual delivery of the single-use email link, confirm the account, then exercise sign-in, sign-out and password reset, including delivery of the reset email. Signup can succeed when mail publication is unconfirmed. A broker ping or a successful signup response alone does not establish delivery.
2. Use the installed operator's native sign-in and account activation as that verified Admin. The first eligible bound activation through `POST /v1/activations:bound-with-session` issues a managed Free licence and promotes the self-signup organisation when needed. The Admin needs no enrolment key or manual staff action. Confirm the signed entitlement, repeat activation on the same installation, restart and verify the persisted identity. Try a second independent installation and verify the device-limit refusal.
3. The seeded fallback Free plan provides one device, two screen outputs, zero NDI outputs and a watermark setting, plus 20 STT minutes and one note per week. Verify actual output and watermark behaviour on the installed packages. Catalogue allowances describe plan data. Cloud runtime acceptance is separate. Core and Pro are catalogue seed records. Keep paid checkout deferred.
4. Managed Free is valid for 365 days. Eligible requests start renewing the licence 30 days before expiry, extending it to 365 days from renewal. On staging, exercise eligible authenticated bound activation and device-token refresh. Verify an expired token is refused and exercise verified Admin recovery on the same eligible installation. Verify revocation denies fresh entitlement where the licence or device is ineligible. Exercise loss of the API and provider access while preserving live presentation and supported offline operation with a valid cached entitlement.
5. Record results by target, source SHA, image digest, package digest and time. Use redacted request IDs and test data. Keep account details, credentials, audio and transcript text out of release receipts.

## Public cloud boundary

The API implements device-authenticated, no-store `POST /v1/stt/session` and `GET /v1/quota`, with Deepgram grant, policy, reservation and usage handling. Public native delivery has yet to be qualified. The `cloud-stt` and `openai-notes` Cargo features use development credentials and are barred from release. Keep long-lived provider, admin and usage credentials out of the installer and website. The planned STT flow requires native consent and a short-lived server-issued credential before the client streams audio to Deepgram.

The default production Compose only maps the two beat scheduling inputs for provider work. It supplies neither provider secret-file mounts nor dedicated workers. Adding variables in Coolify alone cannot wire these roles. The following source roles need a reviewed deployment and operational receipts before cloud admission.

| Role | Required boundary |
|---|---|
| `web` | STT admission with a role-local policy and wrapping keyring. |
| `usage` | Worker consumes exactly `provider_usage`, with scoped reader credentials and a policy matching the relevant web parents. |
| `provisioner` | Worker consumes exactly `provider_provisioning`, with policy, administrative credentials, keyring and completed inventory under approved capacity and creation budgets. |
| `maintenance` | Worker consumes `celery`. A separate single beat schedules work. Neither needs provider credentials. |

Use role-scoped read-only mounts at absolute paths from trusted directories. The configuration loader requires regular files, owner-only access and no final symlink. Verify ownership and readability as the actual process user, UID 65534 in the included API-image services. Verify workload and provider policies together, including queue ownership, tenant attribution, weekly quota and reset in the account time zone, concurrent admission, outages, revocation and abuse limits. [Provider configuration and policy](deployments.md#provider-process-configuration)

Enabling notes on the web role, or starting a notes worker, refuses with `PCFG_NOTES_RUNTIME_UNAVAILABLE`. The current API has no public notes execution route, and quota exposes no notes policy. The requested server-side notes design still needs implementation and integrated qualification. Verify consent, selected transcript transfer, temporary content disposal, restricted credential custody, native validation and acknowledgement, allowance accounting, and the **USD 0.25 per note** ceiling including the allowed retry. Measure abuse exposure separately. Keep notes unavailable until the reviewed implementation and evidence exist.

## Package and publish

### Final packages

Use the exact reviewed source and toolchain, with clean build inputs and no real provider, admin or development signing secrets. The checked-in packaging baselines select local `stt`. They supply native packaging references. The current publisher also requires accepted evidence for cloud transcription, notes and quota/provider reconciliation, so those baselines alone cannot satisfy `accepted_for_publication`. Keep the manifest unpublished while those required gates are open.

| Platform | Packaging and final acceptance |
|---|---|
| Windows x64 | Use the [Windows NSIS workflow](.github/workflows/windows-installer.yml) for the `*-setup.exe`, output sidecar, WebView2, NDI dependencies and Portable Whisper settings. Verify actual Authenticode status and record any approved unsigned disclosure separately from macOS. Exercise install, launch, presentation and uninstall on clean Windows. |
| macOS arm64 and x64 | Use the [universal macOS packaging procedure](docs/delivery/evidence/public-release-macos-20261114.md), the pinned Rust and Tauri toolchain, and the licensed universal NDI SDK staged locally by `scripts/fetch_ndi_sdk.sh`. The current source tracks no macOS SDK dylib in Git LFS. Inspect the final DMG with `hdiutil verify`, verify both app and output slices with `lipo -archs`, and check mounted app signing with `codesign --verify --all-architectures --deep --strict`. The approved disclosure is **ad-hoc signed application, unsigned DMG, no Apple Developer ID signature or notarization**. Record Gatekeeper behaviour with a browser-downloaded copy. Record native Apple Silicon, native Intel and any Rosetta coverage as observed. |
| Ubuntu 24.04 x64 | Use the [Linux installer workflow](.github/workflows/linux-installer.yml) and `scripts/build_linux_installer.py` for the DEB and its ELF dependency checks. Install with `sudo apt install ./selahcue-installer.deb`, substituting the exact candidate filename. Exercise operator, output, runtime dependencies, upgrade and uninstall on clean Ubuntu 24.04. |

Record package version, architecture, byte count, SHA-256, build run, selected features and signing status. Independently scan the exact final packages and extracted or mounted binaries. Run `python3 scripts/installer_secret_scan.py --self-test` and the [release development-key exclusion check](scripts/dev_key_not_in_release.sh). Retain scan positive controls, build input custody and exact entitlement key enforcement. On each target verify native sign-in, activation, signature trust, presentation, offline behaviour and any qualified cloud feature on the exact candidate.

### Publisher and website cutover

Use the reviewed [publisher input contract](docs/superpowers/plans/2026-11-15-installer-publication-design.md) and [publication handoff](docs/delivery/evidence/installer-publisher-source.md). Supply the exact source profile, build and inspection receipts, and independent acceptance for all required gates. Work from the repository root with the reviewed publisher on a Unix host. Use Python 3.14 as in the [publisher CI job](.github/workflows/ci.yml), AWS CLI v2 for upload and the [website's Node runtime](implementation/marketing/package.json) for manifest validation. Check that `python3` resolves to the intended interpreter. Replace the sample absolute paths with your private evidence and clean build-source paths. The release directory and verification file must be new.

1. Prepare a private snapshot of all three packages and the nonsecret evidence, using a clean checkout at the recorded installer source SHA.

   ```sh
   python3 scripts/publish_installers.py prepare --input /private/evidence/release-input.json --source-tree /private/clean-checkout --out-dir /private/release
   ```

2. After release acceptance, run the conditional upload. Load scoped `INSTALLER_S3_ACCESS_KEY` and `INSTALLER_S3_SECRET_KEY` only into this operator process. It uses the prepared bytes, immutable version-and-digest object keys and conditional creation in the approved Space. Review the upload receipt and reconcile uncertain writes through the publisher before retrying. Keep the three release objects anonymously readable without exposing the bucket listing or unpublished artefacts.

   ```sh
   python3 scripts/publish_installers.py upload --release-dir /private/release
   ```

3. From an independent credential-free environment, verify all three public HTTPS objects against `public-plan.json`. This checks whole anonymous bytes, SHA-256, length and download headers. Retain that receipt with the independent invocation context.

   ```sh
   python3 scripts/publish_installers.py verify-public --plan /private/release/public-plan.json --out /private/verification.json
   ```

4. Emit a separate candidate from the matching prepare, upload and verification receipts. Review the candidate and confirm [manual deployment control](#manual-deployment-control) before pushing the promotion. Promote its exact bytes to [the website's current manifest](implementation/marketing/public/releases/current.json) and record the promotion commit and manifest digest. Rebuild the website image from that commit for the owner to deploy through Coolify. The checked-in default status is `unpublished`.

   ```sh
   python3 scripts/publish_installers.py emit-manifest --release-dir /private/release --verification /private/verification.json --out /private/current-candidate.json
   ```

5. Verify the live same-origin `/releases/current.json` serves the expected bytes as JSON with `Cache-Control: no-cache, must-revalidate`. Check the homepage and downloads page and all four target links. There are three installer objects because `macos-arm64` and `macos-x64` share the universal DMG. The other targets are `windows-x64` and `ubuntu-24.04-x64`. Check signing disclosures, version, architecture and anonymous contents against the receipts. Complete final native acceptance with the public downloads. Retain the three object receipts, website promotion identity and deployed API and website image digests.

## Backup, rollback and recovery

- Before each rollout, take an encrypted PostgreSQL snapshot or logical dump and rehearse restoring it into an empty database on a disposable PostgreSQL instance and volume with rehearsal-only credentials. Match the release code and relevant database version. Record the recovery point and tested restore time. If retaining Redis backups, protect them as credential-bearing data. Keep secret and receipt backups in restricted storage separate from the database backup. [Isolated restore rehearsal](implementation/deploy/README.md#isolated-restore-rehearsal)
- To withdraw a faulty release, restore the unpublished website manifest or a previous verified manifest compatible with the running API, installer trust and current provider policy. Rebuild and deploy the website and verify the live manifest and links. Remove anonymous access to affected objects where needed, accounting for previously cached or downloaded copies. Retain their exact bytes and hashes privately for investigation.
- For an API rollback with a compatible schema, roll back the image. An incompatible or irreversible migration requires recovery from the tested matching database backup. Before a live restore, close traffic and stop all old and new API writers, workers, beat and any external writers. Verify the intended production host and database and the selected encrypted backup's identity and recovery point. Determine how to retain or replay writes made after that point and record any accepted loss. Restore the backup to the verified recovery target with matching code and secrets. Check migration state, ingress, cache, worker and beat, mail, activation and entitlement verification before reopening traffic.
- For provider credential exposure in a qualified deployment, halt new grants, revoke the affected credential and verify the expiry or cancellation of outstanding sessions through supported provider controls. For an exposed entitlement seed, arrange replacement client trust and account for already-issued offline manifests through expiry or trust replacement.
