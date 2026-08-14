FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# psycopg needs libpq; build-essential for any wheel that lacks a manylinux build.
# curl backs the `api` healthcheck in docker-compose.yml.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# --- Dependency layer: cached on pyproject.toml alone ------------------------
# No source is present yet, so setuptools' auto-discovery finds no packages and
# this installs the third-party dependencies plus an EMPTY selahcue-api
# distribution. The empty distribution is fine and expected here: the only thing
# this layer is meant to cache is the slow dependency resolve/build, so that
# editing application code does not re-run it. The install is completed below,
# once the package actually exists.
# Postgres driver is only needed inside the container; local dev stays on SQLite.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[dev]" "psycopg[binary]>=3.2,<4"

# --- Source layer ------------------------------------------------------------
# .dockerignore — not .gitignore — is what keeps .env and db.sqlite3 out of this
# layer. See the comments there before changing this line.
COPY . .

# Re-run the editable install now that selahcue_api is on disk, so the installed
# distribution really points at the package. Without this the import only
# resolves by accident: WORKDIR happens to be sys.path[0] for manage.py, and
# Celery's find_app happens to insert the cwd. Anything invoked from another
# working directory (a one-off `docker compose run`, a cron/exec shell) would
# fail to import selahcue_api.
# --no-deps scopes this to the package itself — every dependency is already
# installed in the cached layer above, so nothing is re-resolved or re-fetched.
RUN pip install --no-cache-dir --no-deps -e .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
