# Self-hosting Logto on Coolify — SelahCue customer IdP deployment runbook

**Status:** Execution-ready runbook (plan). No live instance is provisioned by this document.
**Owner role:** DevOps · **Grounding:** [ADR-0022](../architecture/adr/ADR-0022-customer-identity-oidc-logto.md) §5, [DEC-006](../decisions/DECISION-LOG.md), [deployments.md](../../deployments.md).
**ClickUp:** task [86ajy7aa3](https://app.clickup.com/t/86ajy7aa3) (this work) under epic [86ajy5v6k](https://app.clickup.com/t/86ajy5v6k); security conditions from [86ajy7aqw](https://app.clickup.com/t/86ajy7aqw) (verdict **APPROVED-WITH-CONDITIONS**).

This runbook stands up **self-hosted Logto** as the SelahCue **customer identity IdP** (DEC-006): the OIDC issuer the desktop signs in against (Auth Code + PKCE, public client) and the Platform API validates tokens from (relying party / resource server). Logto owns password storage, MFA, and the sign-in UI; SelahCue owns none of that crypto. Identity is **one-time-online** at activation and is **off the live-output path** — a down IdP never blanks or blocks a service (NFR-024).

> **Before you execute:** this is a human runbook, not automation. Read [§0 Owner inputs required to execute](#0-owner-inputs-required-to-execute) first and gather every input. Do nothing in production until the topology choice (§1) and the residency decision (§9) are made by the owner. Version-sensitive Logto facts are labelled **(verify against your pinned Logto version)** — confirm them from the live discovery document / admin console at deploy time; do not assume.

---

## 0. Owner inputs required to execute

The runbook cannot run without these. Nothing here can be sourced by the author — the owner must supply them.

### 0.1 Server / instance + spec
- **Decision:** dedicated IdP VM (recommended, §1 Option A) **or** segmented shared server (§1 Option B).
- **Host:** a Coolify-managed server (Coolify already installed, or a fresh VM to add to Coolify).
- **Spec (baseline):** 2 vCPU · **4 GB RAM** · 40+ GB SSD for Logto + its Postgres together. Logto's app service is modest; Postgres wants the RAM headroom. Scale up before adding replicas (§10). **(Inferred from Logto's documented low footprint — right-size after a soak.)**

### 0.2 Domain / DNS
- A **stable issuer host**, e.g. `auth.selahcue.<domain>` → `A`/`AAAA` to the server IP. This host is permanent: it is baked into `SELAHCUE_OIDC_ISSUER` and every already-issued token's `iss`. **Never change it after go-live** (see §4).
- An **admin host** only if you choose to expose the admin console over the internet behind an IP-allowlist, e.g. `id-admin.selahcue.<domain>`. Preferred: keep admin **off the public internet** entirely (§3.3) and no admin DNS is needed.

### 0.3 Region decision (residency)
- Hosting **region/jurisdiction** for the Logto Postgres (church PII: emails, names). This is an owner/legal decision under NDPA/GDPR + cross-border transfer (§9). Must be settled before provisioning.

### 0.4 Secret values to supply (never committed, never in this repo)
Provide these into Coolify's encrypted store / your secret manager at deploy time:
| Secret | Where it goes | Notes |
|---|---|---|
| Logto Postgres password | component of `LOGTO_DB_URL` | generate ≥32-char random; unique to this DB |
| Offsite backup storage credentials | Coolify backup destination (S3-compatible) | access key id + secret; bucket in a **separate** account/region |
| Backup encryption passphrase/key | backup pipeline (§5) | if not using storage-side SSE-with-managed-keys |
| Admin-console first-run account password | created interactively on first `ENDPOINT` visit | strong; store in a password manager, not here |

**Produced by Logto after deploy (owner copies them onward, §8):** the M2M management app secret (`LOGTO_MGMT_APP_SECRET`, SECRET), the desktop native app id (`SELAHCUE_OIDC_CLIENT_ID`, public), and the API resource indicator (`SELAHCUE_OIDC_AUDIENCE`, public). These are outputs of §8, then handed to the backend (86ajy7add) and desktop (86ajy7ak8) tasks.

---

## 1. Topology — pick one (owner decision)

Logto is one stateless app container + one Postgres. The choice is **where it lives relative to the Platform API**, and it is driven by security finding **H6** (a compromised IdP or its signing key forges tokens for *any* church — the single largest blast radius).

### Option A — Dedicated IdP instance/VM (RECOMMENDED)
Logto + its Postgres run on their **own** VM / Coolify server, separate from the Platform API host.

- **Pros:** smallest blast radius — a Platform API host compromise cannot reach the signing keys in Logto's DB; independent patching, backup, and network policy; clean least-privilege boundary (H6).
- **Cons:** one more server to run and pay for; the Platform API reaches Logto over the network (still fine — JWKS validation is local and cached, §8).
- **Choose when:** production, or any deployment holding real church identities. This is the default.

### Option B — Segmented shared server (documented fallback)
Logto runs on the same Coolify server as the Platform API, in its **own Coolify project** with an **isolated Docker network** and **separate DB credentials**.

- **Pros:** no extra host; simpler/cheaper for staging or a pilot.
- **Cons:** shared kernel and host — a host or Platform API compromise can potentially reach Logto's DB/volume (weaker H6 posture). Mitigate with: dedicated Coolify project + dedicated Docker network (no shared network with the API), a distinct non-root DB user, restrictive host firewall, and full-disk encryption.
- **Choose when:** staging, pilots, or cost-constrained early production **with the owner explicitly accepting the reduced isolation** (record in §11).

**Both options** keep the admin endpoint off the public internet (§3.3) and Postgres unpublished to the internet (§3.2). The rest of this runbook is written to be identical for A and B except where noted.

---

## 2. Prerequisites

1. Coolify ≥ v4 installed and reachable, with a **Project** created (e.g. `selahcue-idp`) and, for Option A, a dedicated **Server** added.
2. DNS from §0.2 pointing at the server; port 80/443 reachable for Let's Encrypt HTTP-01.
3. Logto image + version **pinned** to an exact tag (e.g. `svhd/logto:1.x.y`) — never `:latest` in prod. **(Verify the current stable tag on the Logto release page before pinning.)**
4. Access to Coolify's encrypted environment/secret store (§4) — you will paste secrets there, not into files.
5. Offsite S3-compatible backup destination provisioned (§5).

---

## 3. Coolify service definition (Logto + dedicated Postgres)

Deploy as a **Docker Compose** resource in the `selahcue-idp` project so Logto and its Postgres are one unit on a private network. Coolify fronts it with its reverse proxy (Traefik/Caddy) and manages TLS (§4).

### 3.1 Compose (reference — Coolify-managed)

```yaml
# Coolify: Project selahcue-idp → New Resource → Docker Compose
services:
  logto:
    image: svhd/logto:1.x.y            # PIN an exact version — never :latest (verify current stable)
    depends_on:
      logto-postgres:
        condition: service_healthy
    environment:
      # --- see §4 for which of these are Coolify SECRET vs plain, and the deployments.md mapping ---
      DB_URL: ${LOGTO_DB_URL}          # SECRET (contains the Postgres password)
      ENDPOINT: ${LOGTO_ENDPOINT}      # public issuer host, e.g. https://auth.selahcue.<domain>
      ADMIN_ENDPOINT: ${LOGTO_ADMIN_ENDPOINT}
      PORT: "3001"
      ADMIN_PORT: "3002"
      TRUST_PROXY_HEADER: "1"          # REQUIRED behind Coolify's TLS-terminating proxy
    # Coolify maps the PUBLIC issuer host (443) -> container :3001 only.
    # The admin console (:3002) is NOT published publicly — see §3.3.
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:3001/api/status"]  # verify path per version
      interval: 30s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  logto-postgres:
    image: postgres:16                 # Logto requires Postgres >= 14; 16 recommended (verify)
    environment:
      POSTGRES_DB: logto
      POSTGRES_USER: logto
      POSTGRES_PASSWORD: ${LOGTO_POSTGRES_PASSWORD}   # SECRET
    volumes:
      - logto-pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U logto -d logto"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    # Do NOT publish 5432 to the host/internet — internal network only (§3.2).

volumes:
  logto-pgdata:
```

`LOGTO_DB_URL` is then `postgres://logto:<password>@logto-postgres:5432/logto` (internal service name). On first start Logto seeds its schema into the empty DB automatically; the admin console is then reachable to create the first admin account.

### 3.2 Ports

| Service | Container port | Exposure | Purpose |
|---|---|---|---|
| Logto core | 3001 | **Public** via Coolify proxy on 443 (issuer host) | OIDC issuer, discovery, JWKS, token/authorize, sign-in UI, **Management API** (`/api`) |
| Logto admin console | 3002 | **Locked down — not public** (§3.3) | Admin UI for app/resource/user/org management |
| Postgres | 5432 | **Internal only** (never published) | Logto's database |

> The **Management API** (used by the Platform API's M2M app, §8.3) is served by the **core service on 3001**, not the admin console. So the core host stays public for OIDC, and the admin *console* can be fully private without breaking backend provisioning.

### 3.3 Admin endpoint lockdown (H6 / security condition)

The admin console **must never be openly public**. Choose one:
1. **Do not publish 3002 at all (preferred).** Reach the admin console over an SSH tunnel or the private network / VPN: `ssh -L 3002:127.0.0.1:3002 <server>` then browse `http://127.0.0.1:3002`. No admin DNS, no public attack surface.
2. **Publish behind an IP-allowlist.** If admins need browser access without a tunnel, put the admin host behind a Coolify/Traefik IP-allowlist middleware restricted to office/VPN egress IPs, plus TLS. Treat any public admin exposure as a residual risk to record in §11.

Never expose the admin console broadly "for convenience." Compromise of the admin console = full control of the IdP = H6 blast radius.

---

## 4. TLS & the stable issuer host

1. In Coolify, set the Logto core service's public domain to the **issuer host** from §0.2 (e.g. `auth.selahcue.<domain>`). Coolify provisions and renews a **Let's Encrypt** certificate automatically (HTTP-01; keep 80/443 reachable).
2. Set `ENDPOINT=https://auth.selahcue.<domain>` (`LOGTO_ENDPOINT`). This is the OIDC **base**; the issuer is `ENDPOINT + /oidc`.
3. Set `TRUST_PROXY_HEADER=1` so Logto honours `X-Forwarded-Proto/Host` from Coolify's proxy and emits correct `https` URLs in discovery/redirects. Without it, redirect/issuer URLs come out wrong.
4. **Issuer alignment (load-bearing):** the value the Platform API and desktop use as `SELAHCUE_OIDC_ISSUER` MUST be exactly `https://auth.selahcue.<domain>/oidc`. Derived URLs (verify from the live discovery doc):
   - Discovery: `<issuer>/.well-known/openid-configuration`
   - JWKS: `<issuer>/jwks`
   - Token: `<issuer>/token` · Authorize: `<issuer>/auth` · End-session: from discovery `end_session_endpoint`
5. **Do not change the issuer host after go-live.** `iss` is embedded in every issued token; changing the host invalidates live sessions and breaks RP validation. If it must ever change, treat it as a migration with coordinated RP + desktop config updates.
6. **HSTS:** enable HSTS on the issuer host at the proxy (consistent with the Platform API's `SECURE_HSTS_*` posture in deployments.md §1a).

---

## 5. Environment & secrets

**Rule (M5):** secrets are injected from **Coolify's encrypted environment store** (or an external secret manager), **never** as a plaintext `.env` committed to the repo or left on disk in prod. `deployments.md` documents key **names only**. `DJANGO_DEBUG`/Logto verbose modes must not leak env in error pages. No secret is ever echoed to logs or audit (ADR-0008/ADR-0011).

### 5.1 Logto env keys → deployments.md mapping

| Coolify env | Logto var | Secret? | Value shape | deployments.md |
|---|---|---|---|---|
| `LOGTO_DB_URL` | `DB_URL` | **SECRET** | `postgres://logto:<pw>@logto-postgres:5432/logto` | §2 (present) |
| `LOGTO_POSTGRES_PASSWORD` | (Postgres `POSTGRES_PASSWORD`) | **SECRET** | random ≥32 chars | §2 (append, §12) |
| `LOGTO_ENDPOINT` | `ENDPOINT` | public | `https://auth.selahcue.<domain>` | §2 (present) |
| `LOGTO_ADMIN_ENDPOINT` | `ADMIN_ENDPOINT` | public | admin URL (or internal) | §2 (present) |
| `LOGTO_PORT` / `LOGTO_ADMIN_PORT` | `PORT` / `ADMIN_PORT` | public | `3001` / `3002` | §2 (present) |
| `LOGTO_TRUST_PROXY_HEADER` | `TRUST_PROXY_HEADER` | public | `1` behind the proxy | §2 (present) |

### 5.2 Keys the Platform API (RP) reads — produced here, consumed by 86ajy7add

| Key | Secret? | Sourced from | deployments.md |
|---|---|---|---|
| `SELAHCUE_OIDC_ISSUER` | public | `<LOGTO_ENDPOINT>/oidc` (§4) | §1c / §3b (present) |
| `SELAHCUE_OIDC_AUDIENCE` | public | the API resource indicator (§8.1) | §1c (present) |
| `SELAHCUE_OIDC_JWKS_URL` | public | `<issuer>/jwks` (override only if non-standard) | §1c (present) |
| `SELAHCUE_OIDC_INTROSPECTION_URL` | public | discovery `introspection_endpoint` (for high-value ops, H5) | §1c (present) |
| `LOGTO_MGMT_ENDPOINT` | public | Management API base (§8.3) | §1c (present) |
| `LOGTO_MGMT_APP_ID` | public | M2M app id (§8.3) | §1c (present) |
| `LOGTO_MGMT_APP_SECRET` | **SECRET** | M2M app secret (§8.3) | §1c (present) |

### 5.3 Desktop native client keys — produced here, consumed by 86ajy7ak8

| Key | Secret? | Sourced from | deployments.md |
|---|---|---|---|
| `SELAHCUE_OIDC_ISSUER` | public | same issuer as the RP | §3b (present) |
| `SELAHCUE_OIDC_CLIENT_ID` | public (no secret) | native app id (§8.2) | §3b (present) |
| `SELAHCUE_OIDC_REDIRECT_URI` | public | `http://127.0.0.1:<port>/callback` + `selahcue://auth/callback` | §3b (present) |

> **The desktop ships NO client secret** (public client, PKCE only — INFO finding in 86ajy7aqw). Do not create a "confidential" desktop app in Logto.

### 5.4 Secrets NOT in env — Logto's own keys

Logto **generates and stores its OIDC signing keys and cookie keys inside its Postgres** (`logto_configs`), not as env vars. You do not set them; you protect the DB and rotate them via the CLI (§7). This is the crux of H6.

---

## 6. Backup & restore (identity is now a system of record)

Logto's Postgres holds church **identities + the OIDC signing keys**. Losing it loses accounts and the ability to validate/issue tokens; leaking it is an H6 compromise. Backups are therefore mandatory, encrypted, offsite, and **restore-tested**.

### 6.1 Backup policy
1. Use **Coolify's scheduled database backups** for the `logto-postgres` resource (logical `pg_dump`), e.g. daily + a pre-upgrade on-demand backup (§10).
2. Destination: an **offsite, separate-account/region** S3-compatible bucket (§0.4). Do not keep the only copy on the same host.
3. **Encryption at rest:** enable storage-side SSE **and/or** encrypt the dump with the §0.4 backup key before upload. Backups contain signing keys — treat every dump as SECRET.
4. **Retention:** keep enough history to recover from a late-detected corruption (e.g. 7 daily + 4 weekly), bounded — align the retention window with the identity-data retention decision (§9). Access to the bucket is least-privilege (backup writer ≠ restore reader ≠ admin).

### 6.2 Restore drill (run in staging, on a schedule — do not wait for an incident)
1. Provision a **staging** Postgres (empty) and a staging Logto pointed at a **staging** issuer host (never the prod issuer).
2. Pull the latest encrypted dump, decrypt, and restore: `pg_restore`/`psql` into the staging DB.
3. Point staging Logto's `DB_URL` at the restored DB and start it.
4. **Verify:** discovery + `<issuer>/jwks` return 200 over TLS; admin console sign-in works; a test app's OIDC flow completes. Record time-to-restore.
5. Tear down staging. File the drill result (date, dump used, RTO observed) — the task's "restore drill documented" gate.

### 6.3 RPO / RTO (set with owner)
- **RPO:** ≤ 24 h with daily backups (tighten to hourly WAL/PITR if the owner needs it). **RTO:** target from the drill (single logical restore is typically minutes for a small identity DB).
- **Signing-key caveat:** restoring an **older** dump after a key **rotation** (§7) reintroduces the old keys and invalidates tokens signed by the newer key. After any restore, confirm the active key set and re-issue/rotate as needed. Keep a note of rotation timestamps alongside backups.

---

## 7. Signing keys — H6 reconciliation & residual risk

**Finding H6 (must-fix condition, DevOps-owned):** a compromised Logto or its signing key can forge a token for any church — the largest blast radius in the system.

**Reality:** Logto OSS keeps its OIDC private keys (and cookie keys) **in its Postgres**, and has **no native HSM/KMS** integration. **(Verify the key-storage location + CLI for your pinned version.)** We cannot move the private key into an HSM without forking Logto, so H6 is mitigated, not eliminated, and the residual is accepted-by-design per DEC-006 (self-hosting was chosen deliberately).

### 7.1 Controls (all required)
1. **Encrypt the DB at rest** — full-disk/volume encryption on the Postgres volume (and on backup dumps, §6). Prefer the dedicated-VM topology (§1 Option A) so the key material shares no host with the Platform API.
2. **Strict, least-privilege DB access** — Postgres never published to the internet (§3.2); a dedicated non-root DB user scoped to the `logto` database; DB credentials in the secret store; no shared credentials with any other service.
3. **Network-restricted admin + Management API** — admin console not public (§3.3); the Management API (on 3001) reachable by the Platform API over the private network / TLS only, and the M2M app scoped least-privilege (§8.3).
4. **JWKS over validated TLS** — the RP fetches JWKS only over the pinned-cert issuer host (§4); the RP pins the expected signing **alg** (H1, backend-owned) so a forged `alg` is rejected.
5. **Signing-key rotation (procedure).** Rotate OIDC keys on a schedule and after any suspected exposure, via the Logto CLI against the DB config, e.g.:
   ```bash
   # (verify exact CLI for your pinned Logto version)
   logto db config rotate --config oidc.privateKeys
   logto db config rotate --config oidc.cookieKeys
   ```
   Rotation adds a new key and keeps the previous one in JWKS for overlap so in-flight tokens validate until they expire; the RP's `kid`-aware JWKS cache (M2, backend-owned) picks up the new key. Back up the DB **before** rotating.
6. **Monitoring** on key use / admin actions / auth error spikes (§10) to detect misuse early.

### 7.2 Residual risk (record for owner acceptance in §11)
> DB or host compromise of the Logto instance exposes the signing keys and enables token forgery for any org until keys are rotated and sessions invalidated. This is inherent to self-hosting an OSS IdP without an HSM (DEC-006). Mitigations above reduce likelihood and blast radius (dedicated VM, encryption, network isolation, rotation, monitoring) but do not remove it. **Owner sign-off required.**

---

## 8. Post-deploy: Logto app registration (in the admin console)

Do this once, after the instance is up and the first admin account is created (via `ENDPOINT`). These produce the `deployments.md` values the backend and desktop tasks need. **(Menu names may vary by version — match the intent.)**

### 8.1 API resource → `SELAHCUE_OIDC_AUDIENCE`
1. Admin console → **API resources** → **Create**.
2. Set an **API identifier** (resource indicator), e.g. `https://api.selahcue.<domain>` (a stable URI; it is an identifier, need not be a live URL).
3. Define the permissions/scopes the account surfaces need (coordinate with 86ajy7add).
4. **Output:** the API identifier is `SELAHCUE_OIDC_AUDIENCE` (public). The RP must require `aud` = this value and reject other audiences (H2).

### 8.2 Desktop native app → `SELAHCUE_OIDC_CLIENT_ID` (+ redirect URIs)
1. Admin console → **Applications** → **Create** → **Native app** (public client).
2. **Redirect URIs:**
   - `http://127.0.0.1:<port>/callback` (loopback primary — the desktop uses an ephemeral port; register the exact form your desktop client expects, RFC 8252)
   - `selahcue://auth/callback` (custom-scheme fallback)
3. **Post sign-out redirect URIs:** the desktop's logout return targets (RP-initiated logout).
4. **PKCE:** ensure the app is PKCE-enforced and **rejects `plain`/no-verifier** (require **S256**). Native apps are PKCE by default — confirm no "allow plain"/secret option is enabled (DevOps PKCE-only condition).
5. **Refresh tokens:** enable `offline_access`; turn on **refresh-token rotation** with **reuse detection**, and confirm a detected replay revokes the **whole token family** (M3). Set a **short access-token TTL** (order of minutes–1h) so JWKS-only validation stays safe (H5).
6. **Output:** the app id is `SELAHCUE_OIDC_CLIENT_ID` (public, **no secret**). Redirect URIs feed `SELAHCUE_OIDC_REDIRECT_URI`.

### 8.3 M2M management app → `LOGTO_MGMT_APP_ID` / `LOGTO_MGMT_APP_SECRET`
1. Admin console → **Applications** → **Create** → **Machine-to-machine**.
2. Grant it access to the **Logto Management API** with **least privilege** — only the roles/permissions the Platform API actually needs for JIT user + org/role provisioning (H4/H6). Do not grant blanket admin if a narrower role suffices. **(Confirm the Management API resource indicator for your version — typically the core `/api` resource; the Platform API requests a client-credentials token for it.)**
3. **Output:**
   - `LOGTO_MGMT_APP_ID` (public), `LOGTO_MGMT_APP_SECRET` (**SECRET** — inject into the Platform API's secret store, never commit).
   - `LOGTO_MGMT_ENDPOINT` = the Management API base URL (on the core host).

### 8.4 Organizations & roles
Enable **Organizations** and define at least **Admin** and **Member/Operator** org roles (map to FR-137 admin-gating + the A10 read-only Member view). The backend maps the Logto org id → `CustomerOrg.external_org_id` and membership → `OrgMembership` (86ajy7add) — no self-serve org creation from the desktop (H4).

### 8.5 Publish for downstream tasks
Hand the backend (86ajy7add) and desktop (86ajy7ak8) the resolved values: issuer, JWKS, discovery, `SELAHCUE_OIDC_AUDIENCE`, `SELAHCUE_OIDC_CLIENT_ID`, redirect URIs, `LOGTO_MGMT_*`. Confirm from the **live discovery doc** that `iss`, `jwks_uri`, `token_endpoint`, `end_session_endpoint`, and `id_token_signing_alg_values_supported` are what the RP will pin.

---

## 9. Region, residency & retention (owner + legal decisions)

Logto's Postgres is now a **system of record for church PII** (emails, display names) — self-hosting keeps it on SelahCue-controlled infrastructure (the DEC-006 privacy rationale), but the following are **owner/legal decisions**, not DevOps calls (M7, FR-176/FR-177):

- **Hosting region / jurisdiction** — deliberate residency choice under **NDPA (Nigeria)** + **GDPR** and cross-border-transfer rules given the Global-South positioning. Pick before provisioning (§0.3).
- **Retention** — how long identity records persist; bound backup retention (§6.1) to match.
- **Deletion / right-to-erasure** — must span **both** Logto (the user) **and** the Platform API `AccountUser`/`OrgMembership` (audit tombstone as needed). This is a cross-system procedure to be defined with the backend task; hosting provides the Logto-side deletion + backup-expiry mechanics.
- **Disclosures** — the privacy policy + app-store data disclosures (FR-176) and DPA/cross-border handling (FR-177) must reflect that identity data is stored in the chosen region.

Flag these to the owner; do not decide them here.

---

## 10. Upgrades, rollback, health/monitoring, SPOF & HA

### 10.1 Upgrades (staging first)
1. Read the Logto release notes for the target tag; note any breaking DB alterations.
2. Apply the upgrade in **staging** first (a staging tenant/instance on a restored copy, §6.2).
3. **Take an on-demand DB backup immediately before** the prod upgrade.
4. Bump the pinned image tag in Coolify and redeploy. Logto applies its DB **alterations (migrations) on start**.
5. Smoke-check: discovery + JWKS 200; admin sign-in; a test OIDC flow.

### 10.2 Rollback
- **Caveat:** Logto DB alterations are **forward-oriented** and may not cleanly reverse. Rolling the image back after alterations ran can break against the migrated schema.
- **Safe rollback = restore the pre-upgrade DB backup + redeploy the previous pinned image**, as a pair. This is why §10.1 step 3 is mandatory. Validate with the §6.2 checks.

### 10.3 Health checks & monitoring (detect user-impacting failure, not just host health)
- **Health:** the compose healthcheck (§3.1) + Coolify container health; Postgres `pg_isready`.
- **External uptime:** probe `<issuer>/.well-known/openid-configuration` and `<issuer>/jwks` over TLS from outside; alert on non-200 or TLS/cert-expiry.
- **Signals to alert on:** container restart loops, Postgres connection saturation, disk usage on the pgdata volume, auth-error spikes / unusual admin or Management-API activity (§7 monitoring), backup job success/failure, cert renewal failure.
- **SLO framing:** the IdP gates **new sign-ins + new account-based activations only** — it never touches live presentation or already-activated devices (offline entitlement = license window, DEC-005; revocation independence, ADR-0022 §3). So a short IdP outage degrades onboarding, not services. Set the availability target accordingly (e.g. business-hours-weighted), and keep it out of the never-blank critical path.

### 10.4 SPOF & HA-later
- **Today:** one Logto container + one Postgres = a single point of failure. Acceptable given §10.3's SLO framing, but record it (§11).
- **HA path (later):** Logto's app service is **stateless** (all state in Postgres), so scale to **2+ replicas** behind Coolify's proxy, and move Postgres to a **replicated/managed** HA setup (or streaming replication + failover). Add this when onboarding volume or an availability commitment justifies it; it is not required for correctness of live presentation.

---

## 11. Security-conditions checklist (H1–H7 + MEDIUMs → controls)

From the APPROVED-WITH-CONDITIONS review (task [86ajy7aqw](https://app.clickup.com/t/86ajy7aqw)). "Owner" = who satisfies it. Items marked **this runbook** are covered by the sections above; the rest belong to the backend/desktop/security tasks and are shown so hosting does **not** falsely claim them.

| ID | Condition | Control | Owner | Satisfied by this runbook? |
|---|---|---|---|---|
| **H1** | Reject `alg:none` / key-confusion; pin expected signing alg | RP pins the alg from discovery; hosting publishes JWKS over pinned TLS (§4, §8.5) | Backend 86ajy7add | No (hosting enables; backend enforces) |
| **H2** | Audience / token-type confusion | RP requires `aud` = API resource (§8.1) and rejects ID-token-as-bearer / other audiences | Backend 86ajy7add | No (hosting defines the audience; backend enforces) |
| **H3** | Org-crossing / takeover via mapping | Map on immutable `sub`; org claim membership-verified; Organizations+roles enabled (§8.4) | Backend 86ajy7add | Partial (hosting enables orgs/roles; backend enforces mapping) |
| **H4** | JIT must not self-create/join orgs | No self-serve org creation from desktop; membership via invite/admin; least-priv M2M (§8.3, §8.4) | Backend 86ajy7add | Partial (hosting: least-priv M2M + org model; backend enforces the rule) |
| **H5** | Revoked-account activation window | Short access-token TTL (§8.2); introspection for high-value ops (§5.2 `INTROSPECTION_URL`) | Backend 86ajy7ag8 | Partial (hosting: TTL + introspection endpoint; backend classifies ops) |
| **H6** | IdP-compromise blast radius | **Dedicated VM (§1A), DB encryption + least-priv access (§7), admin/Mgmt-API network-restricted (§3.3, §7), separate DB creds (§5), key rotation (§7.1.5), monitoring (§10.3)** | **This runbook (DevOps)** | **Yes — mitigated; residual accepted (§7.2)** |
| **H7** | Account/enrollment coexistence org-scoped + locked limit path | RP resolves caller org from token; reuse the existing `select_for_update` limit path | Backend 86ajy7ag8 | No (backend logic) |
| **M1** | Loopback/custom-scheme redirect hardening | Loopback binds 127.0.0.1, single-use state, fast timeout; document custom-scheme residual | Desktop 86ajy7ak8 | No (desktop) — redirect URIs registered here (§8.2) |
| **M2** | JWKS cache bounded + rotation-safe + refetch-rate-limited | `kid`-triggered, bounded TTL, over TLS, bounded cache + bounded-memory test | Backend 86ajy7add | No (backend) — TLS JWKS host provided here (§4) |
| **M3** | Refresh rotation + reuse-detection revokes whole family | **Configure rotation + reuse detection + family revocation on the native app (§8.2)** | **This runbook (Logto app config)** | **Yes** |
| **M4** | Redaction list missing OIDC secrets | Backend denylist extended | Backend (already fixed, comment 90130303357432) | N/A (done) |
| **M5** | Env-var secret hygiene | **Secrets from Coolify encrypted store / secret manager; no plaintext env files; names-only deployments.md; no secrets in logs (§5)** | **This runbook (DevOps)** | **Yes** |
| **M6** | Rate-limiting on auth surfaces | Rate-limit code→token, refresh, both activation endpoints | Backend 86ajy62xz / 86ajy7ag8 | No (backend) — coordinate |
| **M7** | Privacy / NDPA-GDPR residency + retention | **Residency region + retention/erasure spanning Logto + AccountUser flagged as owner/legal (§9)** | **This runbook flags; owner/legal decides** | **Yes (flagged)** |
| **M8** | Account-activation idempotency + deterministic key selection | Reuse enrollment idempotency + deterministic canonical key selection | Backend 86ajy7ag8 | No (backend) |
| **L1** | state/nonce single-use + CSPRNG entropy | Desktop enforces + tests | Desktop 86ajy7ak8 | No (desktop) |
| **L2** | Bearer migration hygiene (CORS, no GraphiQL in prod) | Lock CORS; introspection/IDE off in prod | Backend 86ajy7add | No (backend) |
| **L3** | Logout ≠ instant API cutoff | Documented expectation (short TTL + introspection for immediate cutoff, §10.3, §8.2) | This runbook + backend | Partial (documented here) |
| **L4** | Desktop token handling (redacting `Token`, access token in memory) | Desktop wraps refresh/ID tokens; redaction assertions | Desktop 86ajy7ak8 | No (desktop) |

**Net:** the DevOps-routed conditions **H6, M3, M5, M7** (plus the **PKCE-only** app-config requirement, §8.2) are satisfied as concrete controls by this runbook. H1–H5, H7, M1, M2, M6, M8, L1, L2, L4 remain owned by the backend/desktop tasks and their code-level re-test on 86ajy7aqw before release — hosting does not close them.

---

## 12. deployments.md additions

This runbook appends the following **names-only** keys to `deployments.md` §2 (Logto/hosting), marked SECRET vs public, consistent with the existing style:
- `LOGTO_POSTGRES_PASSWORD` (**SECRET**) — the password component of `LOGTO_DB_URL`, i.e. the dedicated Logto Postgres user's password.
- Backup/hosting (Coolify-managed backup destination): `LOGTO_BACKUP_S3_BUCKET`, `LOGTO_BACKUP_S3_REGION` (public), `LOGTO_BACKUP_S3_ACCESS_KEY_ID`, `LOGTO_BACKUP_S3_SECRET_ACCESS_KEY`, `LOGTO_BACKUP_ENCRYPTION_KEY` (**SECRET**).

All other Logto/OIDC keys this runbook uses already exist in `deployments.md` (§1c, §2, §3b) and are unchanged.

---

## 13. Execution checklist (owner run-order)

1. Owner inputs gathered (§0); topology chosen (§1); region decided (§9).
2. Coolify project/server + DNS + pinned image ready (§2).
3. Deploy the compose (Logto + Postgres) with secrets from the encrypted store (§3, §5); Postgres internal-only; admin locked down (§3.2/§3.3).
4. TLS on the stable issuer host; `TRUST_PROXY_HEADER=1`; confirm discovery + JWKS over TLS (§4). *(Owner-gated verifier C-101.)*
5. Create the first admin account; register API resource, native app (PKCE-only, refresh rotation), M2M app; enable Organizations/roles (§8).
6. Configure scheduled encrypted offsite backups; run the restore drill in staging (§6). *(Owner-gated verifier C-103.)*
7. Apply the H6 controls (encryption, least-priv, rotation schedule, monitoring) (§7, §10.3).
8. Hand issuer/JWKS/discovery + client_id + audience + M2M secret to the backend (86ajy7add) and desktop (86ajy7ak8); run a staging PKCE E2E (§8.5). *(Owner-gated verifier C-102.)*
9. Record the H6/topology/residency residual-risk acceptances with named owners; independent review before QA.

---

## First-run verification (owner)

This deployment cannot be exercised without a server, DNS, and secrets, so the following are **owner-gated** and must be recorded on task 86ajy7aa3 at execution (they are the task's stated verify gates):
1. `curl` the discovery + `<issuer>/jwks` URLs over TLS **from the Platform API host** → 200 + valid JSON on a valid cert.
2. A full **Auth Code + PKCE** run against the registered desktop native app completes end-to-end in **staging** and the RP validates the token.
3. The **restore drill** (§6.2) has been executed against a real backup with sign-in verified, and the RTO recorded.
4. Refresh-token rotation + reuse detection confirmed active (§8.2 / M3); admin console confirmed **not** publicly reachable (§3.3).

Until these pass in a non-production environment, the task stays pre-release; this document is the plan that makes them runnable.
