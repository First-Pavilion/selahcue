#!/usr/bin/env bash
# Deploy or upgrade the SelahCue production stack on this Docker host.
#
#   implementation/deploy/deploy.sh            build images here, back up, migrate, start, verify
#   implementation/deploy/deploy.sh --pull     pull RELEASE_TAG images from the registry instead
#   implementation/deploy/deploy.sh --no-build use the RELEASE_TAG images already on this host
#
# Order follows docs/ops/DEPLOYMENT.md section 6d: back up, stop every writer, migrate with a
# short lock timeout, start the release, check. Stopping writers first costs a short outage on
# every deploy; it is what makes a column-dropping migration safe without per-release judgement.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here/.."   # implementation/

env_file="deploy/production.env"
compose=(docker compose -f docker-compose.prod.yml --env-file "$env_file")

if [[ ! -f "$env_file" ]]; then
  echo "missing $env_file: copy deploy/production.env.example and fill it in" >&2
  exit 1
fi
for key in SECRET_KEY SELAHCUE_ENTITLEMENT_SIGNING_KEY SQL_PASSWORD REDIS_PASSWORD ACME_EMAIL MAIL_HOST; do
  if ! grep -Eq "^${key}=.+" "$env_file"; then
    echo "$env_file: $key is empty" >&2
    exit 1
  fi
done

"${compose[@]}" config --quiet

case "${1:-}" in
  --pull) "${compose[@]}" pull api website ;;
  --no-build) ;;
  "") "${compose[@]}" build ;;
  *) echo "usage: $0 [--pull|--no-build]" >&2; exit 2 ;;
esac

# Back up only an existing database (first deploy has nothing to back up).
"${compose[@]}" up -d --wait db redis
if [[ -n "$("${compose[@]}" ps -q api 2>/dev/null)" ]]; then
  mkdir -p deploy/backups
  backup="deploy/backups/selahcue-$(date -u +%Y%m%dT%H%M%SZ).dump"
  echo "backing up database to $backup"
  "${compose[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup"
  chmod 600 "$backup"
  echo "stopping writers"
  "${compose[@]}" stop beat worker api
fi

echo "migrating"
"${compose[@]}" run --rm migrate

echo "starting release"
"${compose[@]}" up -d --wait --remove-orphans

echo "post-deploy checks"
"${compose[@]}" exec -T api python manage.py migrate --check
"${compose[@]}" exec -T api python manage.py shell -c \
  'from django.core.cache import cache; from uuid import uuid4; k = f"deploy:{uuid4()}"; cache.set(k, "ok", 30); assert cache.get(k) == "ok"; cache.delete(k)'
"${compose[@]}" exec -T worker celery -A selahcue_api inspect ping --timeout 5 >/dev/null

echo "deployed. From outside this host, verify:"
api_domain="$(grep -E '^API_DOMAIN=' "$env_file" | cut -d= -f2-)"
web_domain="$(grep -E '^WEBSITE_DOMAIN=' "$env_file" | cut -d= -f2-)"
echo "  curl -fsS -D - https://$api_domain/graphql/csrf"
echo "  curl -fsS -D - https://$web_domain/graphql/csrf"
echo "  curl -fsS -o /dev/null https://$web_domain/"
