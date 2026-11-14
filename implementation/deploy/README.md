# Production deploy with Docker Compose

`implementation/docker-compose.prod.yml` runs the whole platform on one Docker host:

| Service | Image | Role | Networks |
|---|---|---|---|
| `caddy` | `caddy:2-alpine` | TLS edge, the only container with published ports (80, 443) | backend, egress |
| `api` | API image | Gunicorn on :8000 (default image command) | backend |
| `worker` | API image | Celery worker; the only process that sends mail | backend, egress |
| `beat` | API image | Celery beat. Run exactly one | backend |
| `migrate` | API image | One-off `manage.py migrate`; the app processes wait for it | backend |
| `website` | marketing image | nginx serving the SPA on :80 | backend |
| `db` | `postgres:16-alpine` | PostgreSQL, volume `pgdata` | backend |
| `redis` | `redis:7-alpine` | Password-protected; cache in DB 1, broker in DB 2; AOF on | backend |

`backend` is an internal network with no route off the host. The API image processes run as
`nobody`, with a read-only root filesystem, every capability dropped and a writable `/tmp` only.

This is the self-hosted alternative to the Coolify runbook in [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md).
The images, environment variables, process commands and release checks are the same in both.
Everything in that runbook about releases, backups, acceptance and rollback still applies.

## What you need

- A Linux host with Docker Engine 25+ and the Compose plugin (v2.24+, for `env_file.required`).
  Two vCPU and 4 GB RAM is a reasonable pilot starting point; size it from staging measurements.
- DNS A/AAAA records for both domains (`API_DOMAIN`, `WEBSITE_DOMAIN`) pointing at the host, and
  inbound 80/tcp, 443/tcp and 443/udp open. Caddy obtains the certificates on first start.
- Outbound SMTP from the host (STARTTLS, port 587 by default) and SMTP credentials on a verified
  sending domain.
- The secrets listed at the top of `production.env.example`, generated on a trusted machine.

## First deploy

```bash
cd implementation
cp deploy/production.env.example deploy/production.env
chmod 600 deploy/production.env
# edit deploy/production.env: every empty value must be filled in
deploy/deploy.sh
```

`deploy.sh` validates the env file and Compose config, then builds both images. On an upgrade it
also backs up Postgres to `deploy/backups/` (gitignored, mode 600). It then stops the API, worker
and beat, runs the migration with a 5 s lock timeout, starts everything, waits for the
healthchecks, and runs the post-deploy checks from the runbook: `migrate --check`, a cache
round-trip and a worker ping. It finishes by printing the external `curl` checks to run from
another machine.

Use `deploy/deploy.sh --pull` to deploy images from a registry (set `API_IMAGE`, `WEBSITE_IMAGE`
and `RELEASE_TAG`). Use `--no-build` for images already loaded on the host. Pin `RELEASE_TAG` to
the reviewed commit and record the image digests (`docker image inspect --format '{{.Id}}'`), as
the release prerequisites require.

Stopping the writers before every migration means each deploy has a short outage, typically under
a minute. That makes a column-dropping migration (docs/ops/DEPLOYMENT.md section 6d) safe without
anyone having to judge it per release.

## Day-2 operations

```bash
C="docker compose -f docker-compose.prod.yml --env-file deploy/production.env"
$C ps                               # health of every service
$C logs -f --tail=100 api worker    # logs (json-file, 5 x 10 MB per container)
$C exec api python manage.py shell  # restricted Django shell (manual licence issuance)
$C exec worker celery -A selahcue_api inspect ping --timeout 5
```

**Backups.** `deploy.sh` takes a backup only on upgrade. Schedule a daily
`pg_dump -Fc` off-host (cron on the host running the `exec -T db pg_dump` line from `deploy.sh`),
encrypt it, and rehearse a restore. Back up `deploy/production.env` separately: `SECRET_KEY` and
the entitlement seed cannot be regenerated without invalidating every token and manifest.

**Restore.**

```bash
$C stop api worker beat
$C exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < deploy/backups/<file>.dump
```

Then start the release that matches that backup.

**Rollback.** Set `RELEASE_TAG` back to the previous release. If the newer release migrated the
schema incompatibly, restore its pre-deploy backup first, then run `deploy/deploy.sh --no-build`.

## Behind Coolify or another proxy

On Coolify, deploy this file with Coolify's Docker Compose build pack and **remove the `caddy`
service**. Then route `API_DOMAIN` to `api:8000`, and route `WEBSITE_DOMAIN` to `website:80` with
`/graphql/*` sent to `api:8000`. Reproduce the Caddyfile's guarantees in Coolify's proxy: strip
`X-SelahCue-*`, overwrite `X-Forwarded-For`/`-Proto`, and return 404 for `/graphql/admin`. Then
re-derive `SELAHCUE_TRUSTED_PROXY_COUNT` (docs/ops/DEPLOYMENT.md section 6b). The stack sets it
to `1` because Caddy is exactly one hop on every route. Any CDN or load balancer in front changes
that number and `SELAHCUE_TRUST_FORWARDED_PROTO`.

## Not handled by this stack

- **Per-IP rate limiting at the edge.** Stock Caddy has none. The application's own account and
  device throttles stay on. Add a CDN/WAF rule (or a Caddy build with a rate-limit module) for
  `/graphql/account`, `/v1/sessions` and `/v1/activations:with-session` before opening sign-up.
- **Error reporting.** `SENTRY_DSN` is read, but no SDK is wired.
- **Production staff authentication.** `/graphql/admin` is blocked at the edge until it exists.
