# Pilot Runtime and Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Provide a locked production API server command and an accurate manual Coolify deployment guide.

**Architecture:** The existing Django WSGI app runs under Gunicorn in the API image. The development Compose override remains explicit. DEPLOYMENT.md describes the actual services and source gaps; it does not claim a deployed cloud release.

**Tech Stack:** Python3.14, Django6.1, Gunicorn27.0.1, uv0.13.4, Docker, PostgreSQL, Redis/Celery, nginx/Coolify.

**Spec:** docs/superpowers/specs/2026-11-14-pilot-runtime-deployment.md

**Release task:** [17tnw2b0wqj](https://app.clickup.com/t/17tnw2b0wqj)

## Global Constraints

- Owner deploys manually; no deployment or provider administration is authorized by this slice.
- Public API https://api.selahcueapp.com; intended website https://selahcueapp.com.
- Two sync workers,30-second worker/graceful shutdown timeouts, no preload, no control socket and no request access logs.
- Pin Gunicorn27.0.1 with a package-specific age exception only; preserve unrelated lock versions and the14-day default.
- Gunicorn does not infer secure requests from untrusted forwarded headers; existing Django trusted-proxy settings remain authoritative.
- No reusable provider, admin, signing private key or account secret is baked into source/images/packages.

## Review Focus

- Normal startup serves the existing CSRF liveness route and graceful SIGTERM exits without orphan workers.
- A missing required production setting fails startup rather than serving with development defaults.
- Spoofed forwarded-proto headers are ignored when Django trust is disabled, while the explicitly trusted path works.
- Gunicorn preserves an existing disposable control socket through startup and shutdown.
- The invalid JSON request returns HTTP 400 without logging its synthetic query or body values.
- Development Compose retains its explicit runserver override and the image contains the declared locked server.

---

### Task 1: Production WSGI entrypoint and deployment guide

**Files:** Modify implementation/api/pyproject.toml, implementation/api/uv.lock, implementation/api/Dockerfile, DEPLOYMENT.md, deployments.md and docs/ops/DEPLOYMENT.md only where entrypoint references need correction. Create implementation/api/gunicorn.conf.py and implementation/api/tests/test_production_server.py (or a focused integration script if isolated subprocess lifecycle is unsuitable for the database test fixture). Existing implementation/docker-compose.yml remains a development stack.

**Interfaces:** Consume selahcue_api.wsgi:application, existing settings/environment and /graphql/csrf. Produce image default `gunicorn --config gunicorn.conf.py selahcue_api.wsgi:application`, binding0.0.0.0:8000. Fixed configuration: workers2, worker_class=sync, timeout30, graceful_timeout30, preload_app=False, accesslog=None, errorlog='-', `forwarded_allow_ips=""` (normalizes to an empty list) and `secure_scheme_headers={}` so only Django's explicit proxy configuration supplies forwarded HTTPS. No new application environment variable is required. CLI overrides for the documented resource baseline are an operator deployment choice.

- [x] Add focused process-level tests for serving CSRF through the real command with disposable settings/ephemeral loopback port, controlled startup failure, SIGTERM cleanup, forwarded-proto trust off/on, and absence of a synthetic secret query/body sentinel in captured logs. Assert actual HTTP/process outcomes, not source-string similarity. Use no real .env, external data store, provider call or private key.
- [x] Run these targeted tests before adding the server; record the expected missing-command/config failure.
- [x] Add the exact Gunicorn pin, the narrow uv package age exception using supported pinned-uv syntax, regenerate the lock without unrelated upgrades, supply the config and default image CMD. Keep local Compose's existing explicit dev command.
- [x] Update DEPLOYMENT.md from its current audited draft to give the actual build context, entrypoint and checks. Correct completed-versus-pending features without removing open cloud/native/deployment acceptance. Update existing entrypoint references only where stale.
- [x] Run targeted process tests, existing deployment guard/env documentation checks, uv lock validation and API dependency audit. Build/smoke the image if Docker is available; report unavailable Docker as an explicit evidence limit, not a passing image check. Do not duplicate unrelated full suites; CI covers the changed API after push.
- [x] Commit only this task's source and documentation, preserving unrelated untracked plans/evidence. Append exact commands/results, pin/age rationale and verification limits to the task report.
