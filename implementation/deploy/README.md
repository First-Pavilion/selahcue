# Production deploy on Coolify (Docker Compose)

`implementation/docker-compose.prod.yml` is the whole platform as one Coolify resource, deployed
with Coolify's **Docker Compose** build pack:

| Service | Image | Role |
|---|---|---|
| `api` | API image | Gunicorn on :8000 (default image command) |
| `worker` | API image | Celery worker; the only process that sends mail |
| `beat` | API image | Celery beat. Run exactly one |
| `migrate` | API image | One-off `manage.py migrate`. The app processes wait for it to succeed |
| `website` | marketing image | nginx serving the SPA on :80 |
| `db` | `postgres:16-alpine` | PostgreSQL, volume `selahcue-pgdata` |
| `redis` | `redis:7-alpine` | Password-protected; cache in DB 1, broker in DB 2; AOF on |

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

Every HTTPS router strips the four `X-SelahCue-*` identity headers the API reads (`Actor-Id`,
`Actor-Kind`, `Org-Id`, `Staff-Permissions`). If the API ever reads a new one, add it to the
`selahcue-strip-identity` middleware.

Django sees exactly one proxy hop on every route, so the compose file fixes
`SELAHCUE_TRUSTED_PROXY_COUNT=1` and `SELAHCUE_TRUST_FORWARDED_PROTO=1`. That holds because
Traefik replaces a client's `X-Forwarded-For`/`-Proto` unless its entrypoint trusts that client.
**If the production server sits behind Cloudflare, a load balancer, or a Traefik configured with
`forwardedHeaders.trustedIPs`, re-derive both values before going live** (docs/ops/DEPLOYMENT.md
sections 6b and 6c).

The labels assume Coolify's default Traefik configuration: entrypoints named `http` and `https`,
and a certificate resolver named `letsencrypt`. Check the production server's proxy configuration
(Servers, then Proxy) before the first deploy. If the names differ, change the labels to match.

## First deploy

1. Point DNS for both domains at the production Coolify server.
2. Create a resource from the repository with build pack **Docker Compose**, base directory
   `/implementation` and compose location `/docker-compose.prod.yml`. Coolify builds `api` from
   `implementation/api` and `website` from the repository root, as the runbook requires.
3. Environment Variables, Developer view: paste [`production.env.example`](production.env.example),
   fill every value and lock the secrets. Values marked `:?` in the compose file stop the deploy
   when empty.
4. Leave every Domains field empty (see above). Deploy.
5. Run the runbook's checks (DEPLOYMENT.md "Deploy and verify the platform", steps 6 and 7) from
   the `api` and `worker` containers' terminals, and the `curl` checks from outside.

## Every later deploy

Each deploy runs `migrate` before the new `api`, `worker` and `beat` start. The previous release
keeps serving while the migration runs. That is fine for additive migrations. **For a release
that drops a column (docs/ops/DEPLOYMENT.md section 6d), stop the resource in Coolify first,
then deploy.** Take a database backup before any deploy that migrates.

Pin each deploy to the reviewed commit and record the image digests, as the release prerequisites
require. To deploy prebuilt images instead of building on the server, set `API_IMAGE`,
`WEBSITE_IMAGE` and `RELEASE_TAG` to the registry images.

## Backups

The database lives in this resource (`selahcue-pgdata`), not in a Coolify-managed database. Add a
Coolify **Scheduled Task** on the `db` container that writes a dump to storage you mount for
backups, and ship it off the server encrypted:

```sh
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /backups/selahcue-$(date -u +%Y%m%dT%H%M%SZ).dump
```

Rehearse a restore with the `db` writers stopped (stop `api`, `worker` and `beat`):

```sh
pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /backups/<file>.dump
```

Back up `SECRET_KEY` and the entitlement seed outside Coolify too. Neither can be regenerated
without invalidating every token and offline manifest.

## Rehearse locally

```bash
cd implementation
cp deploy/production.env.example deploy/production.env   # gitignored; fill in test values
docker compose -f docker-compose.prod.yml --env-file deploy/production.env up -d --wait
```

The app comes up without a proxy. To exercise the routing, run Traefik v3 on the project network
with `http`/`https` entrypoints and a `letsencrypt` resolver, the way Coolify does.

## Not handled by this stack

- **Per-IP rate limiting at the edge.** The application's account and device throttles stay on.
  Add a Traefik `ratelimit` middleware or a CDN/WAF rule for `/graphql/account`, `/v1/sessions`
  and `/v1/activations:with-session` before opening sign-up.
- **Network isolation.** Coolify attaches every service to the resource network, which has
  outbound access. The web process only needs the database and Redis.
- **Error reporting.** `SENTRY_DSN` is read, but no SDK is wired.
