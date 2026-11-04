FROM ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b AS uv
FROM python:3.14-slim
COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /usr/src/app

# psycopg needs libpq; build-essential for any wheel that lacks a manylinux build.
# curl backs the `api` healthcheck in docker-compose.yml.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# Hash-locked dependency/build layer. Only wheels: no untracked PEP517 build downloads.
COPY pyproject.toml uv.lock .uv-version ./
RUN uv sync --locked --extra dev --group build --no-install-project --no-build --no-python-downloads

# --- Source layer ------------------------------------------------------------
# .dockerignore — not .gitignore — is what keeps .env and db.sqlite3 out of this
# layer. See the comments there before changing this line.
COPY . .

# Install the actual application after source exists, with the locked backend and no network.
# /opt/venv is outside the compose source bind mount; imports work from any cwd.
RUN uv sync --locked --extra dev --group build --offline --no-build-isolation --no-cache --no-python-downloads

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
