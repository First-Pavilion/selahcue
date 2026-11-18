# Production deploy on Coolify (Docker Compose)

`implementation/docker-compose.prod.yml` is the whole platform as one Coolify resource, deployed
with Coolify's **Docker Compose** build pack:

| Service | Image | Role |
|---|---|---|
| `api` | API image | Gunicorn on :8000 (default image command) |
| `worker` | API image | Celery maintenance worker on `celery`, concurrency two. Sends account mail. |
| `beat` | API image | Celery beat in the maintenance role. Run exactly one. |
| `migrate` | API image | One-off `manage.py migrate`. The app processes wait for it to succeed |
| `website` | marketing image | nginx serving the SPA on :80 |
| `db` | `postgres:16-alpine` | PostgreSQL, volume `selahcue-pgdata` |
| `redis` | `redis:7-alpine` | Password-protected, cache in DB 1, broker/results in DB 2, AOF on volume `selahcue-redisdata` |

No service publishes a host port. Coolify's Traefik proxy reaches `api` and `website` over the
resource network. The API image processes run as `nobody`, with a read-only root filesystem,
every capability dropped and a writable `/tmp` only.

Everything in the Coolify runbook [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md) still applies:
release prerequisites, entitlement key handling, acceptance, backups and rollback. This file
covers how this compose file maps onto that runbook.

## Routing lives in the compose file

Traefik labels on `api` and `website` define every router. **Leave each service's Domains field
empty in Coolify.** A domain set there makes Coolify generate a second router for the same
service, and that router has none of the rules below.

| Request | Goes to | Why |
|---|---|---|
| `https://API_DOMAIN/*` | `api:8000` | Native client and API traffic |
| `https://WEBSITE_DOMAIN/graphql/*` | `api:8000` directly | Same origin for the SPA, and one hop, like native traffic |
| `https://WEBSITE_DOMAIN/*` | `website:80` | The SPA |
| `/graphql/admin*` on either domain | rewritten to an unrouted path (Django 404) | Production staff auth does not exist yet |
| `http://` on either domain | 301 to `https://` | |

The API, website and website GraphQL routers strip the four `X-SelahCue-*` identity headers
the API reads (`Actor-Id`, `Actor-Kind`, `Org-Id`, `Staff-Permissions`). The dedicated staff
router rewrites the request to the unrouted path. If the API ever reads a new identity header,
add it to the `selahcue-strip-identity` middleware.

Both public Django routes use one Traefik hop, so Compose fixes
`SELAHCUE_TRUSTED_PROXY_COUNT=1` and `SELAHCUE_TRUST_FORWARDED_PROTO=1`. That holds because
Traefik replaces a client's `X-Forwarded-For`/`-Proto` unless its entrypoint trusts that client.
The trusted count applies to the entire Django process. If Cloudflare, a load balancer or the
alternate nginx route produces different trusted depths, normalise the chains at trusted ingress
or use separate API services with their own correct count. Verify forwarded headers and effective
client IP on both routes. [Proxy trust](../../docs/ops/DEPLOYMENT.md#6c-ops-requirements--django-behind-a-tls-terminating-proxy)

Compose passes the signup and named reset-trace hourly limits to the API image. Signup needs a healthy Redis cache. Restore the previous limits and recreate the API workers to roll back a tuning change. [Defaults and outage behavior](../../docs/ops/DEPLOYMENT.md#signup-admission)

The labels require Traefik entrypoints named `http` and `https` and a certificate resolver
named `letsencrypt`. Check the server's proxy configuration (Servers, then Proxy) before the
first deploy. Verify that the configured labels match. Start a new resource's HSTS at the
template values `300/0/0`. For the initial HSTS rollout, follow the
[HSTS ramp-up](../../docs/ops/DEPLOYMENT.md#6c-ops-requirements--django-behind-a-tls-terminating-proxy)
after verifying both HTTPS routes. Retain the approved policy on existing resources.

## First deploy

1. Point DNS for both domains at the production Coolify server.
2. Create a resource from the repository with build pack **Docker Compose**, base directory
   `/implementation` and compose location `/docker-compose.prod.yml`. Keep the selected branch
   free of pushes during setup. Set **Advanced → Deployment → Auto deploy → Manual deployments
   only** and confirm no automated workflow or integration uses the authenticated Deploy Webhook
   for this resource. Coolify builds `api` from `implementation/api` and `website` from the
   repository root. [Manual deployment control](../../DEPLOYMENT.md#manual-deployment-control)
3. Import [`production.env.example`](production.env.example) in Developer view only for a new
   resource with an empty variable list. In an existing or pre-populated resource, edit only
   the intended entries in Normal view and preserve the selected image references, database
   identity, HSTS and other overrides. Use Normal view for locked entries.
   Before the first build, set `SECRET_KEY`, `SELAHCUE_ENTITLEMENT_SIGNING_KEY`, `SQL_PASSWORD`,
   `REDIS_PASSWORD` and `MAIL_PASSWORD` to **Not available during build** and **Available in
   the container**. Verify their saved scopes by name without recording values, then lock any
   unlocked secret. Compose inputs marked `:?` stop the deploy when empty. Use the
   [runtime environment procedure](../../DEPLOYMENT.md#runtime-environment) and
   [matching entitlement seed](../../DEPLOYMENT.md#entitlement-signing-key).
4. Leave every Domains field empty. Apply the edge controls below and review the migration plan.
   Rehearse [scheduled work](../../DEPLOYMENT.md#scheduled-work) in bounded isolated staging.
   Check the selected source ref against the recorded release commit, then have the owner
   select **Deploy** in Coolify.
5. Verify the deployed commit and image digests. Run the
   [platform checks](../../DEPLOYMENT.md#deploy-and-verify-the-platform) from the runtime
   containers and the `curl` checks from outside. Complete the
   [Free journey](../../DEPLOYMENT.md#free-account-and-activation-acceptance), including actual
   delivered email and native activation.

## Every later deploy

Each deploy runs `migrate` before the new `api`, `worker` and `beat` start. The previous release
keeps serving while the migration runs. That is fine for additive migrations. **For a release
that drops a column (docs/ops/DEPLOYMENT.md section 6d), stop the resource in Coolify first,
then deploy.** Take a database backup before any deploy that migrates.

Recheck the manual trigger policy and runtime-only secret scopes before the owner deploys
the recorded commit. `API_IMAGE`, `WEBSITE_IMAGE` and
`RELEASE_TAG` set the image references. The Compose build declarations remain active. Verify how
Coolify resolves the images and record the actual deployed digests.

## Beat schedules

For the account stack, leave both `SELAHCUE_BEAT_PROVIDER_PROVISIONING_ENABLED` and
`SELAHCUE_BEAT_PROVIDER_USAGE_ENABLED` unset or `0`. Compose passes them only to beat.
Beat retains the usage retention, licence revocation and expired credential jobs on `celery`.

Set either input to `1` only after verifying the matching dedicated worker
(`provider_provisioning` or `provider_usage`). To disable a sweep, set its input to `0`, recreate
beat and reconcile pending messages before stopping the consumer. Follow the
[verification and rollback procedure](../../DEPLOYMENT.md#scheduled-work).

## Backups

The database lives in this resource (`selahcue-pgdata`), not in a Coolify-managed database. Add a
Coolify **Scheduled Task** on the `db` container that writes a dump to storage you mount for
backups, and ship it off the server encrypted:

```sh
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /backups/selahcue-$(date -u +%Y%m%dT%H%M%SZ).dump
```

Back up `SECRET_KEY` and the matching entitlement seed in restricted storage outside Coolify.
Rotating `SECRET_KEY` invalidates credential fingerprints. Rotate the entitlement signer only
with compatible client trust.

### Isolated restore rehearsal

Provision a disposable PostgreSQL instance and volume on an isolated rehearsal host. Use the
same PostgreSQL major version as production. Bind this instance to loopback on the rehearsal host.
Create a `selahcue_restore_rehearsal` login role and make it the owner of a new empty database
named `selahcue_restore_rehearsal`. Use rehearsal-only credentials and connection settings.
The drill runs entirely outside the production Coolify resource. Keep the live database and its
writers running during the drill.

From the rehearsal host, check the exact destination before restoring. For the sample
commands, the disposable instance listens on `127.0.0.1:55432`. Compare the reported host,
port, database and connected role with the rehearsal inventory. Verify that the listed owner
of the target database is `selahcue_restore_rehearsal`, the database is empty and the instance
uses the disposable volume. Stop if any check fails or if any live connection is possible.

```sh
psql -X --host=127.0.0.1 --port=55432 \
  --username=selahcue_restore_rehearsal --dbname=selahcue_restore_rehearsal \
  --command='\conninfo' --command='\list selahcue_restore_rehearsal'
```

Set `backup_file` to the path of the selected dump copied into protected rehearsal storage.
Restore into the empty database.

```sh
backup_file='/restore-rehearsal/approved-selahcue-backup.dump'
pg_restore --host=127.0.0.1 --port=55432 \
  --username=selahcue_restore_rehearsal --dbname=selahcue_restore_rehearsal \
  --exit-on-error --single-transaction --no-owner --no-privileges "$backup_file"
```

Verify the restored migration frontier and expected data. Record the recovery point and time,
then dispose of the instance, volume and protected backup copy according to the backup retention
policy. For a deliberate live recovery, follow the
[rollback procedure](../../DEPLOYMENT.md#backup-rollback-and-recovery).

## Rehearse locally

Use isolated data, broker and volumes and set a stop time before starting. Stop the rehearsal
stack at the end.

```bash
cd implementation
cp deploy/production.env.example deploy/production.env   # gitignored; fill in test values
docker compose -f docker-compose.prod.yml --env-file deploy/production.env up -d --wait
```

The app comes up without a proxy. To exercise the routing, run Traefik v3 on the project network
with `http`/`https` entrypoints and a `letsencrypt` resolver, the way Coolify does.

## Not handled by this stack

- **Edge rate limiting and log rules.** Before opening sign-up, configure per-IP protection on
  both public origins for reachable routes. Include `/graphql/account`, `POST /v1/sessions`,
  `POST /v1/activations:bound-with-session`, `POST /v1/activations:with-session` and the
  other device routes in the [ingress procedure](../../DEPLOYMENT.md#deploy-and-verify-the-platform).
  Check actual client IP and verify edge and nginx log exclusions with synthetic tokens.
- **Cloud roles.** The stack supplies the beat schedule inputs. Dedicated provider workers
  and their role-specific settings and mounts require deployment wiring. See
  [the public cloud boundary](../../DEPLOYMENT.md#public-cloud-boundary) for the open requirements.
- **Network isolation.** Coolify attaches every service to the resource network, which has
  outbound access. The web process only needs the database and Redis.
- **Error reporting.** `SENTRY_DSN` is read, but no SDK is wired.
