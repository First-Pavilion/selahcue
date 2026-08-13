# Signed Offline Entitlement Manifest + Platform API CI Job — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `501` stub at `GET /v1/entitlements/manifest` with an Ed25519-signed, device-bound, time-boxed entitlement the desktop can cache and verify offline — and give the Platform API its first CI job.

**Architecture:** Three ignorant-of-each-other layers. `signing.py` turns a mapping into a signed envelope and knows nothing about licensing. `services.py` authenticates, applies an allow-list issuance gate, assembles the payload, and audits — knowing nothing about HTTP. The view maps errors to status codes and knows nothing about crypto. No new models: the manifest is a projection of `Device` + `AppLicenseKey`.

**Tech Stack:** Django 5.2, Python 3.12, `cryptography` (Ed25519), pytest-django, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-13-entitlement-manifest-design.md`
**ClickUp:** [86ak0mt8f](https://app.clickup.com/t/86ak0mt8f)

## Global Constraints

- **Signature covers the base64url payload string as transmitted** — never a re-serialization of decoded JSON. This is the whole reason Python and Rust will agree.
- **Issuance is an allow-list**, `license_key.status in ACTIVATABLE_KEY_STATUSES`, never a deny-list. A status added to the enum later must deny by default.
- **Never serve an unsigned manifest.** Missing or malformed key → loud failure. No dev-key fallback, no default value in settings.
- **Do not modify** `apps/devices/services.py`, `POST /v1/activations`, or `POST /v1/license:refresh`. Reuse `authenticate_device_token` unchanged.
- **Do not re-implement device-token auth.** One choke point, already shipped.
- All commands run from `implementation/api/`. Python interpreter: `/private/tmp/selahcue-api-venv/bin/python` (recreated on 3.12 in Task 1).
- Migrations in this project are **hand-committed**; never auto-generate and commit blindly.
- `record_audit_event` requires `request_id`; `source_surface` for `/v1` is `"desktop_v1"`.
- Timestamps serialize with `.isoformat()`, matching `LicenseRefreshResult`.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `.github/workflows/ci.yml` | *Modify* — add `api` path filter + `api` job |
| `selahcue_api/apps/{billing,catalogue,downloads,entitlements}/migrations/__init__.py` | *Create* — make apps visible to `makemigrations --check` |
| `pyproject.toml` | *Modify* — add `cryptography` |
| `selahcue_api/settings.py` | *Modify* — read `SELAHCUE_ENTITLEMENT_SIGNING_KEY` |
| `selahcue_api/apps/entitlements/signing.py` | *Create* — key loading, `key_id` derivation, sign, verify. Pure crypto |
| `selahcue_api/apps/entitlements/services.py` | *Create* — auth, issuance gate, payload, audit |
| `selahcue_api/platform/views.py` | *Modify* — replace the stub view |
| `selahcue_api/platform/urls.py` | *Modify* — point the route at the real view |
| `tests/test_entitlement_signing.py` | *Create* — crypto unit tests, no DB |
| `tests/test_entitlement_manifest_slice.py` | *Create* — service + HTTP integration tests |
| `docs/ops/DEPLOYMENT.md` | *Modify* — signing key + rotation runbook |
| `implementation/api/README.md` | *Modify* — endpoint + verification |

---

### Task 1: Make the migration gate honest, then add the API CI job

The gate must exist *and* be able to see the app the next tasks create. Doing this first means every later task is verified by CI.

**Files:**
- Create: `selahcue_api/apps/billing/migrations/__init__.py`
- Create: `selahcue_api/apps/catalogue/migrations/__init__.py`
- Create: `selahcue_api/apps/downloads/migrations/__init__.py`
- Create: `selahcue_api/apps/entitlements/migrations/__init__.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: a green `api` job other tasks rely on; `entitlements` becomes migration-visible.

- [ ] **Step 1: Recreate the local venv on Python 3.12**

The current venv runs 3.14, outside Django 5.2's supported range. Local and CI must match.

```bash
brew install python@3.12   # skip if already present
rm -rf /private/tmp/selahcue-api-venv
/opt/homebrew/bin/python3.12 -m venv /private/tmp/selahcue-api-venv
/private/tmp/selahcue-api-venv/bin/python -m pip install -q --upgrade pip
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pip install -q -e ".[dev]"
```

- [ ] **Step 2: Prove the migration gate is currently blind**

```bash
cd implementation/api
/private/tmp/selahcue-api-venv/bin/python manage.py makemigrations --check --noinput entitlements
```

Expected: fails with `No installed app with label 'entitlements'` — demonstrating the app is invisible to the autodetector. Record this output; it is the "before" the next step fixes.

- [ ] **Step 3: Create the four empty migration packages**

```bash
cd implementation/api
for app in billing catalogue downloads entitlements; do
  touch "selahcue_api/apps/$app/migrations/__init__.py"
done
```

Note: `touch` alone is enough — the directory is created by the shell only if it exists, so use `mkdir -p` to be safe:

```bash
cd implementation/api
for app in billing catalogue downloads entitlements; do
  mkdir -p "selahcue_api/apps/$app/migrations"
  touch "selahcue_api/apps/$app/migrations/__init__.py"
done
```

- [ ] **Step 4: Verify the gate can now see the app**

```bash
cd implementation/api
/private/tmp/selahcue-api-venv/bin/python manage.py makemigrations --check --noinput
echo "exit=$?"
```

Expected: `exit=0` and no changes detected. The command no longer errors on `entitlements`.

- [ ] **Step 5: Add the `api` path filter to `ci.yml`**

In the `changes` job, add `api` to `outputs`:

```yaml
    outputs:
      desktop: ${{ steps.filter.outputs.desktop }}
      mobile: ${{ steps.filter.outputs.mobile }}
      android: ${{ steps.filter.outputs.android }}
      api: ${{ steps.filter.outputs.api }}
```

And add this filter alongside the existing ones, after the `android:` block:

```yaml
            # The Django Platform API. Before this filter existed, implementation/api
            # matched NO filter — an API-only push ran nothing at all.
            api:
              - 'implementation/api/**'
              - '.github/workflows/ci.yml'
```

- [ ] **Step 6: Add the `api` job to `ci.yml`**

Add as a new top-level job (place it after the `flutter` job):

```yaml
  api:
    name: api (django)
    needs: changes
    if: needs.changes.outputs.api == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    defaults:
      run:
        working-directory: implementation/api
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - name: Install
        run: pip install -e ".[dev]"
      - name: Django system checks
        run: python manage.py check
      # --check has implied --dry-run since Django 4.2. --noinput is load-bearing:
      # without it a field rename picks the interactive questioner, which calls
      # input() and dies on a TTY-less runner with an EOFError traceback.
      - name: Migrations are committed
        run: python manage.py makemigrations --check --noinput
      - name: Tests
        run: python -m pytest tests -q
```

- [ ] **Step 7: Validate the workflow YAML parses**

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ci.yml parses')"
```

Expected: `ci.yml parses`

- [ ] **Step 8: Run the full suite locally**

```bash
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pytest tests -q
```

Expected: `63 passed`

- [ ] **Step 9: Commit**

```bash
git add .github/workflows/ci.yml implementation/api/selahcue_api/apps/*/migrations/__init__.py
git commit -m "ci(api): first Platform API job + unblind the migration gate

implementation/api matched no path filter, so an API-only push ran nothing.
makemigrations --check also skips apps with no migrations package, which
included entitlements, billing, catalogue and downloads — the gate would
have been green and blind."
```

---

### Task 2: Ed25519 signing module

**Files:**
- Modify: `implementation/api/pyproject.toml`
- Modify: `implementation/api/selahcue_api/settings.py`
- Create: `implementation/api/selahcue_api/apps/entitlements/signing.py`
- Test: `implementation/api/tests/test_entitlement_signing.py`
- Modify: `docs/ops/DEPLOYMENT.md`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces, all imported by Task 3:
  - `SigningKeyUnavailable(RuntimeError)`
  - `InvalidEnvelope(ValueError)`
  - `ENVELOPE_VERSION: int` (= 1), `ALGORITHM: str` (= `"Ed25519"`)
  - `load_signing_key(seed_b64: str | None = None) -> Ed25519PrivateKey`
  - `derive_key_id(public_key: Ed25519PublicKey) -> str`
  - `sign_envelope(payload: dict[str, Any], *, private_key: Ed25519PrivateKey) -> dict[str, Any]`
  - `verify_envelope(envelope: dict[str, Any], *, public_key: Ed25519PublicKey) -> dict[str, Any]`

- [ ] **Step 1: Add the dependency**

In `implementation/api/pyproject.toml`, change the `dependencies` list to:

```toml
dependencies = [
  "Django>=5.2,<5.3",
  "strawberry-graphql-django>=0.86,<0.87",
  # Ed25519 for the signed offline entitlement envelope. Django ships no
  # asymmetric primitives.
  "cryptography>=43,<47",
]
```

Install it:

```bash
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pip install -q -e ".[dev]"
```

- [ ] **Step 2: Read the signing key in settings**

In `implementation/api/selahcue_api/settings.py`, add near the other `SELAHCUE_*` settings (after `SELAHCUE_TRUST_ACTOR_HEADERS`):

```python
# Ed25519 seed (32 bytes, standard base64) used to sign offline entitlement manifests.
# DELIBERATELY has no default: an absent key must fail loudly at issuance rather than
# degrade to unsigned or to a well-known dev key, which would void the offline model.
ENTITLEMENT_SIGNING_KEY = os.getenv("SELAHCUE_ENTITLEMENT_SIGNING_KEY", "")
```

- [ ] **Step 3: Write the failing tests**

Create `implementation/api/tests/test_entitlement_signing.py`:

```python
"""Ed25519 envelope signing — pure crypto, no database.

The load-bearing test here is `tampered_payload_fails_verification`: without it every
other assertion would still pass against a no-op signer.
"""

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from selahcue_api.apps.entitlements.signing import (
    ALGORITHM,
    ENVELOPE_VERSION,
    InvalidEnvelope,
    SigningKeyUnavailable,
    derive_key_id,
    load_signing_key,
    sign_envelope,
    verify_envelope,
)

# A fixed seed so signatures are byte-reproducible across runs. Test-only.
TEST_SEED = bytes(range(32))
TEST_SEED_B64 = base64.b64encode(TEST_SEED).decode("ascii")

PAYLOAD = {"device_public_id": "dev-1", "feature_scope": "pro", "instances_used": 2}


def _key() -> Ed25519PrivateKey:
    return load_signing_key(TEST_SEED_B64)


def test_load_signing_key_accepts_a_valid_seed():
    assert isinstance(_key(), Ed25519PrivateKey)


def test_load_signing_key_rejects_absent_key():
    with pytest.raises(SigningKeyUnavailable):
        load_signing_key("")


def test_load_signing_key_rejects_non_base64():
    with pytest.raises(SigningKeyUnavailable):
        load_signing_key("not!valid!base64!")


def test_load_signing_key_rejects_wrong_length_seed():
    short = base64.b64encode(b"too-short").decode("ascii")
    with pytest.raises(SigningKeyUnavailable):
        load_signing_key(short)


def test_key_id_is_derived_and_stable():
    first = derive_key_id(_key().public_key())
    second = derive_key_id(_key().public_key())
    assert first == second
    assert len(first) == 8
    assert all(c in "0123456789abcdef" for c in first)


def test_key_id_differs_for_a_different_key():
    other = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    assert derive_key_id(_key().public_key()) != derive_key_id(other.public_key())


def test_envelope_has_the_declared_shape():
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    assert envelope["envelope_version"] == ENVELOPE_VERSION
    assert envelope["alg"] == ALGORITHM
    assert envelope["key_id"] == derive_key_id(_key().public_key())
    assert isinstance(envelope["payload"], str)
    assert isinstance(envelope["signature"], str)


def test_roundtrip_returns_the_original_payload():
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    assert verify_envelope(envelope, public_key=_key().public_key()) == PAYLOAD


def test_signing_is_deterministic_for_a_fixed_seed():
    # Ed25519 is deterministic — the same key and message always yield the same signature.
    a = sign_envelope(PAYLOAD, private_key=_key())
    b = sign_envelope(PAYLOAD, private_key=_key())
    assert a == b


def test_tampered_payload_fails_verification():
    """THE test. Flip one byte of the payload; verification must reject it."""
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    raw = envelope["payload"]
    flipped = ("A" if raw[5] != "A" else "B")
    envelope["payload"] = raw[:5] + flipped + raw[6:]
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=_key().public_key())


def test_signature_from_a_different_key_is_rejected():
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    attacker = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=attacker.public_key())


def test_unexpected_alg_is_rejected_before_any_verification():
    """Algorithm confusion: a verifier must allow-list, not dispatch on the field."""
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    envelope["alg"] = "HS256"
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=_key().public_key())


def test_signature_covers_the_encoded_string_not_a_reserialization():
    """Re-encoding the decoded payload with different JSON formatting must NOT verify —
    proof that the signature is over the transmitted bytes."""
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    decoded = verify_envelope(envelope, public_key=_key().public_key())
    padded = json.dumps(decoded, sort_keys=True, indent=2)  # different whitespace
    envelope["payload"] = (
        base64.urlsafe_b64encode(padded.encode("utf-8")).decode("ascii").rstrip("=")
    )
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=_key().public_key())
```

- [ ] **Step 4: Run the tests to verify they fail**

```bash
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_entitlement_signing.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'selahcue_api.apps.entitlements.signing'`

- [ ] **Step 5: Write the implementation**

Create `implementation/api/selahcue_api/apps/entitlements/signing.py`:

```python
"""Ed25519 signing of the offline entitlement envelope (DEC-004).

Bytes in, envelope out. This module knows nothing about licensing, devices or HTTP —
it is the only place that touches key material.

**The signature covers the base64url payload string exactly as transmitted**, not a
re-serialization of the decoded JSON. Signing a canonical serialization would require
Python and Rust to agree byte-for-byte on key ordering, separators, unicode escaping
and float formatting; every one of those is a place a signature silently fails to
verify. Signing the transmitted encoding removes the entire class of problem.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.conf import settings

ENVELOPE_VERSION = 1
ALGORITHM = "Ed25519"
_SEED_BYTES = 32


class SigningKeyUnavailable(RuntimeError):
    """The signing key is absent or malformed. Never degrade to unsigned output."""


class InvalidEnvelope(ValueError):
    """The envelope is malformed, uses an unexpected algorithm, or fails verification."""


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def load_signing_key(seed_b64: str | None = None) -> Ed25519PrivateKey:
    """Load the Ed25519 private key from a base64 seed.

    `seed_b64` is for tests; production passes nothing and reads settings. Raises rather
    than returning a fallback key — an unsigned or dev-signed manifest would void the
    offline entitlement model entirely.
    """
    raw = settings.ENTITLEMENT_SIGNING_KEY if seed_b64 is None else seed_b64
    if not raw:
        raise SigningKeyUnavailable("SELAHCUE_ENTITLEMENT_SIGNING_KEY is not set")
    try:
        seed = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as error:
        raise SigningKeyUnavailable("signing key is not valid base64") from error
    if len(seed) != _SEED_BYTES:
        raise SigningKeyUnavailable(
            f"signing key must decode to {_SEED_BYTES} bytes, got {len(seed)}"
        )
    return Ed25519PrivateKey.from_private_bytes(seed)


def derive_key_id(public_key: Ed25519PublicKey) -> str:
    """First 8 hex characters of SHA-256 over the raw public key.

    Derived rather than configured, so a key and its id cannot drift apart and rotation
    needs no registry: the client trusts a set of public keys and selects by this id.
    """
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:8]


def sign_envelope(
    payload: dict[str, Any], *, private_key: Ed25519PrivateKey
) -> dict[str, Any]:
    encoded = _b64u_encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = private_key.sign(encoded.encode("ascii"))
    return {
        "envelope_version": ENVELOPE_VERSION,
        "alg": ALGORITHM,
        "key_id": derive_key_id(private_key.public_key()),
        "payload": encoded,
        "signature": _b64u_encode(signature),
    }


def verify_envelope(
    envelope: dict[str, Any], *, public_key: Ed25519PublicKey
) -> dict[str, Any]:
    """Verify and decode. The reference implementation the Rust verifier mirrors.

    `alg` is checked against a one-element allow-list before any key material is used —
    dispatching on a caller-supplied algorithm field is how confusion attacks work.
    """
    if envelope.get("alg") != ALGORITHM:
        raise InvalidEnvelope(f"unsupported alg: {envelope.get('alg')!r}")
    if envelope.get("envelope_version") != ENVELOPE_VERSION:
        raise InvalidEnvelope(f"unsupported envelope_version: {envelope.get('envelope_version')!r}")
    encoded = envelope.get("payload")
    signature = envelope.get("signature")
    if not isinstance(encoded, str) or not isinstance(signature, str):
        raise InvalidEnvelope("payload and signature must both be strings")
    try:
        public_key.verify(_b64u_decode(signature), encoded.encode("ascii"))
    except (InvalidSignature, binascii.Error, ValueError) as error:
        raise InvalidEnvelope("signature verification failed") from error
    try:
        return json.loads(_b64u_decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidEnvelope("payload is not valid JSON") from error
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_entitlement_signing.py -q
```

Expected: `13 passed`

- [ ] **Step 7: Document the key in DEPLOYMENT.md**

In `docs/ops/DEPLOYMENT.md`, add a new section immediately before `## 7. What must never be committed`:

```markdown
## 6a. Entitlement signing key (Platform API)

`SELAHCUE_ENTITLEMENT_SIGNING_KEY` — the Ed25519 private seed used to sign offline
entitlement manifests. **No default.** If it is unset, `GET /v1/entitlements/manifest`
fails loudly rather than serving an unsigned manifest.

Generate one:

```bash
python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
```

Store it as an environment variable on the API host, alongside `DJANGO_SECRET_KEY`.
Never commit it; anything signed with it is accepted by every SelahCue install that
trusts the corresponding public key.

**Rotation.** The `key_id` in each envelope is derived from the public key, so clients
select the right one without a registry:

1. Generate the new seed and derive its public key and `key_id`.
2. Ship a desktop release whose trusted-key set contains **both** the old and new public keys.
3. Wait for adoption — old manifests keep verifying throughout.
4. Switch `SELAHCUE_ENTITLEMENT_SIGNING_KEY` on the server to the new seed.
5. Drop the old public key in a later release.

Never sign with two keys at once; the envelope carries exactly one signature.
```

- [ ] **Step 8: Commit**

```bash
git add implementation/api/pyproject.toml implementation/api/selahcue_api/settings.py \
        implementation/api/selahcue_api/apps/entitlements/signing.py \
        implementation/api/tests/test_entitlement_signing.py docs/ops/DEPLOYMENT.md
git commit -m "feat(api): Ed25519 entitlement envelope signing

Signs the transmitted base64url payload string rather than a canonical
re-serialization, so Python and Rust never have to agree on key order,
whitespace or unicode escaping. key_id is derived from the public key so
rotation needs no registry. No key default — absent key fails loudly."
```

---

### Task 3: Entitlement manifest service

**Files:**
- Create: `implementation/api/selahcue_api/apps/entitlements/services.py`
- Test: `implementation/api/tests/test_entitlement_manifest_slice.py`

**Interfaces:**
- Consumes from Task 2: `load_signing_key`, `sign_envelope`, `SigningKeyUnavailable`.
- Consumes (shipped, unchanged): `selahcue_api.apps.devices.services.authenticate_device_token`, `ACTIVATABLE_KEY_STATUSES`.
- Produces, used by Task 4:
  - `ENTITLEMENT_VERSION: int` (= 1)
  - `EntitlementManifestResult` frozen dataclass with fields `envelope: dict[str, Any]`, `payload: dict[str, Any]`, `device_public_id: str`
  - `build_entitlement_manifest(presented_token: str) -> EntitlementManifestResult`

- [ ] **Step 1: Write the failing tests**

Create `implementation/api/tests/test_entitlement_manifest_slice.py`:

```python
"""Signed offline entitlement manifest — service + HTTP behaviour.

Issuance is an ALLOW-LIST. The parametrised licence-status test is driven off
`LicenseKeyStatus.choices`, so adding a ninth status fails this suite rather than
silently qualifying for a signed multi-year entitlement.
"""

import base64
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import Device, DeviceStatus
from selahcue_api.apps.devices.services import ACTIVATABLE_KEY_STATUSES
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import load_signing_key, verify_envelope
from selahcue_api.apps.license_keys.models import LicenseKeyStatus
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")

pytestmark = pytest.mark.django_db


# Module-local seeding helpers, mirroring tests/test_license_refresh_slice.py. The shipped
# slices each build their own rather than sharing a conftest.py — follow that, do not
# introduce a shared fixture as part of this slice.
def _seed_license_key(*, tag, device_limit=3, starts_at=None, expires_at=None):
    """Returns (AppLicenseKey, full_key)."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Manifest Church {tag}",
        slug=f"manifest-church-{tag}",
        primary_contact_email=f"ops+{tag}@manifest.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=device_limit,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"customer-org-{tag}",
    )
    now = timezone.now().replace(microsecond=0)
    actor = ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_ops_1",
        staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
    )
    result = generate_license_key(
        actor,
        GenerateLicenseKeyData(
            idempotency_key=f"license-key-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            starts_at=starts_at or now,
            expires_at=expires_at or (now + timedelta(days=30)),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
            territory="NG",
            reason="Pilot for entitlement-manifest tests.",
        ),
    )
    return result.license_key, result.full_key


def _activate(client, *, full_key, tag):
    """Activate over HTTP, as the refresh slice does. Returns (device_token, device_public_id)."""
    body = {
        "idempotency_key": f"manifest-act-{tag}",
        "license_key": full_key,
        "device_fingerprint": f"fp-manifest-{tag}",
        "platform": "macos",
    }
    resp = client.post("/v1/activations", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200, resp.content
    payload = resp.json()
    return payload["activation_token"], payload["device"]["device_public_id"]


@pytest.fixture(autouse=True)
def signing_key(settings):
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    return TEST_SEED_B64


@pytest.fixture
def activated(client):
    """An activated device on a live licence. Returns (Device, device_token, AppLicenseKey)."""
    key, full_key = _seed_license_key(tag="m1")
    token, device_public_id = _activate(client, full_key=full_key, tag="m1")
    device = Device.objects.get(device_public_id=device_public_id)
    return device, token, key


def _payload(token):
    result = build_entitlement_manifest(token)
    return verify_envelope(
        result.envelope, public_key=load_signing_key(TEST_SEED_B64).public_key()
    )


def test_manifest_is_signed_and_verifies(activated):
    device, token, _key = activated
    result = build_entitlement_manifest(token)
    assert result.envelope["alg"] == "Ed25519"
    payload = verify_envelope(
        result.envelope, public_key=load_signing_key(TEST_SEED_B64).public_key()
    )
    assert payload["device_public_id"] == device.device_public_id


def test_manifest_is_bound_to_the_requesting_device(activated):
    device, token, _key = activated
    payload = _payload(token)
    assert payload["device_public_id"] == device.device_public_id
    assert payload["device_fingerprint"] == device.device_fingerprint


def test_expiry_equals_the_licence_window_exactly(activated):
    _device, token, key = activated
    payload = _payload(token)
    assert payload["expires_at"] == key.expires_at.isoformat()
    assert payload["not_before"] == key.starts_at.isoformat()


def test_license_status_passes_through_verbatim(activated):
    _device, token, key = activated
    payload = _payload(token)
    assert payload["license_status"] == key.status
    assert payload["license_status"] in {s.value for s in LicenseKeyStatus}


@pytest.mark.parametrize("status", [s.value for s in LicenseKeyStatus])
def test_only_activatable_statuses_are_issued_a_manifest(activated, status):
    """Every enum member, so a newly added status denies by default."""
    _device, token, key = activated
    # Keep expires_at in the future so the device token stays live and auth still passes —
    # this is what makes the REVOKED case reachable at all.
    key.status = status
    key.save(update_fields=["status", "updated_at"])

    if status in {s.value for s in ACTIVATABLE_KEY_STATUSES}:
        assert build_entitlement_manifest(token).envelope["alg"] == "Ed25519"
    else:
        with pytest.raises(SafeAPIError) as caught:
            build_entitlement_manifest(token)
        assert caught.value.code == ErrorCode.POLICY_DENIED


def test_licence_not_yet_started_is_denied(activated):
    _device, token, key = activated
    key.starts_at = timezone.now() + timedelta(days=1)
    key.save(update_fields=["starts_at", "updated_at"])
    with pytest.raises(SafeAPIError) as caught:
        build_entitlement_manifest(token)
    assert caught.value.code == ErrorCode.POLICY_DENIED


def test_unknown_token_is_unauthenticated(activated):
    with pytest.raises(SafeAPIError) as caught:
        build_entitlement_manifest("not-a-real-token")
    assert caught.value.code == ErrorCode.UNAUTHENTICATED


def test_empty_token_is_unauthenticated(activated):
    with pytest.raises(SafeAPIError) as caught:
        build_entitlement_manifest("")
    assert caught.value.code == ErrorCode.UNAUTHENTICATED


def test_revoked_device_is_unauthenticated_not_policy_denied(activated):
    """DeviceStatus has only ACTIVE and REVOKED; the shipped auth helper owns this."""
    device, token, _key = activated
    device.status = DeviceStatus.REVOKED
    device.save(update_fields=["status", "updated_at"])
    with pytest.raises(SafeAPIError) as caught:
        build_entitlement_manifest(token)
    assert caught.value.code == ErrorCode.UNAUTHENTICATED


def test_missing_signing_key_fails_loudly(activated, settings):
    from selahcue_api.apps.entitlements.signing import SigningKeyUnavailable

    _device, token, _key = activated
    settings.ENTITLEMENT_SIGNING_KEY = ""
    with pytest.raises(SigningKeyUnavailable):
        build_entitlement_manifest(token)


def test_instances_are_reported(activated):
    _device, token, key = activated
    payload = _payload(token)
    assert payload["instances_limit"] == key.device_limit
    assert payload["instances_used"] == Device.objects.filter(
        license_key=key, status=DeviceStatus.ACTIVE
    ).count()


def test_issuance_is_audited(activated):
    _device, token, _key = activated
    before = AuditEvent.objects.filter(action="entitlement.manifest_issued").count()
    build_entitlement_manifest(token)
    assert AuditEvent.objects.filter(action="entitlement.manifest_issued").count() == before + 1


def test_no_token_material_in_the_payload(activated):
    _device, token, _key = activated
    payload = _payload(token)
    flat = str(payload)
    assert token not in flat
    for banned in ("device_token", "full_key", "secret", "token_hash"):
        assert banned not in payload
```

> **Fixture note:** the `_seed_license_key` / `_activate` helpers above are modelled on
> `implementation/api/tests/test_license_refresh_slice.py`, which is the established pattern — there
> is no `conftest.py` and no shared factory in this project, and each slice seeds its own data. Keep
> them module-local; do not import test helpers across modules, and do not introduce a shared
> `conftest.py` as part of this slice.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_entitlement_manifest_slice.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'selahcue_api.apps.entitlements.services'`

- [ ] **Step 3: Write the implementation**

Create `implementation/api/selahcue_api/apps/entitlements/services.py`:

```python
"""Signed offline entitlement manifest (DEC-004 / DEC-005).

Assembles the payload a desktop install caches and verifies locally. Knows nothing
about HTTP; the view maps `SafeAPIError` codes to statuses.

**Issuance is an allow-list, and deliberately stricter than `/v1/license:refresh`.**
That endpoint reports honestly rather than denying, because it mints nothing. This one
mints a signed, device-bound credential cacheable until the licence expiry, and with no
revocation list issuance is the ONLY enforcement point that exists. Revoking a licence
key does not cascade to `DeviceToken`, and `authenticate_device_token` never consults
licence status — so without this gate a device under a REVOKED licence would
authenticate fine and be handed a freshly signed multi-year entitlement. The signed
artefact must never be laxer than the unsigned one. Do not harmonise the two endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.devices.models import Device, DeviceStatus
from selahcue_api.apps.devices.services import (
    ACTIVATABLE_KEY_STATUSES,
    authenticate_device_token,
)
from selahcue_api.apps.entitlements.signing import load_signing_key, sign_envelope
from selahcue_api.graphql.context import ActorContext, ActorKind
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from selahcue_api.graphql.redaction import assert_no_restricted_payload_fields

ENTITLEMENT_VERSION = 1


@dataclass(frozen=True)
class EntitlementManifestResult:
    envelope: dict[str, Any]
    payload: dict[str, Any]
    device_public_id: str


def build_entitlement_manifest(presented_token: str) -> EntitlementManifestResult:
    token = authenticate_device_token(presented_token)
    device = token.device
    license_key = device.license_key
    now = timezone.now()

    # Allow-list, not a deny-list: a status added to LicenseKeyStatus later denies by
    # default instead of silently qualifying for a signed entitlement.
    valid_now = (
        license_key.status in ACTIVATABLE_KEY_STATUSES
        and license_key.starts_at <= now < license_key.expires_at
    )
    if not valid_now:
        raise SafeAPIError(ErrorCode.POLICY_DENIED)

    instances_used = Device.objects.filter(
        license_key=license_key, status=DeviceStatus.ACTIVE
    ).count()

    payload = {
        "entitlement_version": ENTITLEMENT_VERSION,
        "device_public_id": device.device_public_id,
        "device_fingerprint": device.device_fingerprint,
        "customer_org_id": str(license_key.customer_id),
        "license_status": license_key.status,
        "license_valid_now": valid_now,
        "license_starts_at": license_key.starts_at.isoformat(),
        "license_expires_at": license_key.expires_at.isoformat(),
        "feature_scope": license_key.feature_scope,
        "territory": license_key.territory,
        "instances_used": instances_used,
        "instances_limit": license_key.device_limit,
        "issued_at": now.isoformat(),
        "not_before": license_key.starts_at.isoformat(),
        "expires_at": license_key.expires_at.isoformat(),
    }
    # Run redaction HERE, on the mapping — this is the only layer where the payload is
    # still walkable. Against the envelope it would be theatre: the payload is by then an
    # opaque base64 string the assertion walks straight past.
    assert_no_restricted_payload_fields(payload)

    envelope = sign_envelope(payload, private_key=load_signing_key())

    record_audit_event(
        ActorContext(kind=ActorKind.DEVICE, actor_id=device.device_public_id),
        action="entitlement.manifest_issued",
        target_type="device",
        target_id=str(device.id),
        request_id=device.device_public_id,
        source_surface="desktop_v1",
        after={"key_id": envelope["key_id"], "expires_at": payload["expires_at"]},
    )

    return EntitlementManifestResult(
        envelope=envelope,
        payload=payload,
        device_public_id=device.device_public_id,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_entitlement_manifest_slice.py -q
```

Expected: all pass. If the parametrised status test errors on fixture construction, fix the fixture per the note in Step 1 — do **not** weaken the assertion.

- [ ] **Step 5: Commit**

```bash
git add implementation/api/selahcue_api/apps/entitlements/services.py \
        implementation/api/tests/test_entitlement_manifest_slice.py
git commit -m "feat(api): entitlement manifest service with allow-list issuance gate

Signs only for ACTIVATABLE_KEY_STATUSES inside the validity window. Stricter
than license:refresh on purpose: with no revocation list, issuance is the only
enforcement point, and revoking a key does not cascade to DeviceToken."
```

---

### Task 4: Wire up the endpoint

**Files:**
- Modify: `implementation/api/selahcue_api/platform/views.py`
- Modify: `implementation/api/selahcue_api/platform/urls.py`
- Modify: `implementation/api/tests/test_entitlement_manifest_slice.py` (append HTTP tests)
- Modify: `implementation/api/README.md`

**Interfaces:**
- Consumes from Task 3: `build_entitlement_manifest`, `EntitlementManifestResult`.
- Consumes from Task 2: `SigningKeyUnavailable`.
- Produces: `GET /v1/entitlements/manifest` returning the envelope as JSON.

- [ ] **Step 1: Write the failing HTTP tests**

Append to `implementation/api/tests/test_entitlement_manifest_slice.py`:

```python
# --- HTTP surface -------------------------------------------------------------------

MANIFEST_URL = "/v1/entitlements/manifest"


def test_http_returns_a_signed_envelope(client, activated):
    _device, token, _key = activated
    resp = client.get(MANIFEST_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["alg"] == "Ed25519"
    assert body["surface"] == "desktop"
    assert body["operation"] == "entitlement_manifest"
    verify_envelope(body, public_key=load_signing_key(TEST_SEED_B64).public_key())


def test_http_without_a_token_is_401(client, activated):
    resp = client.get(MANIFEST_URL)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_http_with_a_bad_token_is_401(client, activated):
    resp = client.get(MANIFEST_URL, HTTP_AUTHORIZATION="Bearer nonsense")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_http_revoked_licence_is_403(client, activated):
    _device, token, key = activated
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])
    resp = client.get(MANIFEST_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "POLICY_DENIED"


def test_http_missing_signing_key_is_500_and_leaks_nothing(client, activated, settings):
    _device, token, _key = activated
    settings.ENTITLEMENT_SIGNING_KEY = ""
    resp = client.get(MANIFEST_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL"
    # A misconfiguration must never describe the key material or its absence in detail.
    assert "SELAHCUE_ENTITLEMENT_SIGNING_KEY" not in resp.content.decode()
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_entitlement_manifest_slice.py -q -k http
```

Expected: FAIL — the route still returns the `501` stub, so `test_http_returns_a_signed_envelope` fails on `501 != 200`.

- [ ] **Step 3: Add an INTERNAL error code**

`SAFE_MESSAGES` and `_STATUS_BY_CODE` have no 500 entry. In `implementation/api/selahcue_api/graphql/errors.py`, add to `ErrorCode`:

```python
    INTERNAL = "INTERNAL"
```

and to `SAFE_MESSAGES`:

```python
    ErrorCode.INTERNAL: "The request could not be completed.",
```

- [ ] **Step 4: Map it to 500 in the view layer**

In `implementation/api/selahcue_api/platform/views.py`, add to `_STATUS_BY_CODE`:

```python
    ErrorCode.INTERNAL: 500,
```

- [ ] **Step 5: Replace the stub view**

In `implementation/api/selahcue_api/platform/views.py`, add to the imports:

```python
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import SigningKeyUnavailable
```

Replace `entitlement_manifest_not_implemented` with:

```python
@require_GET
def entitlement_manifest(request):
    """GET /v1/entitlements/manifest — the signed, device-bound, time-boxed offline
    entitlement (DEC-004). Device-token auth; pure read. The response IS the envelope:
    its `payload` is an opaque base64url string the client verifies before decoding."""
    try:
        result = build_entitlement_manifest(_device_bearer_token(request))
    except SafeAPIError as error:
        return command_error_response(
            code=error.code, surface="desktop", operation="entitlement_manifest"
        )
    except SigningKeyUnavailable:
        # Misconfiguration, not a client error. Fail loudly in the log; say nothing
        # specific to the caller — never serve an unsigned manifest.
        logger.exception("entitlement signing key unavailable; refusing to issue a manifest")
        return command_error_response(
            code=ErrorCode.INTERNAL, surface="desktop", operation="entitlement_manifest"
        )
    payload = {
        **result.envelope,
        "surface": "desktop",
        "operation": "entitlement_manifest",
    }
    # Defense in depth over the envelope's own fields. The signed payload was already
    # checked as a mapping inside the service, which is the only layer that can see it.
    assert_no_restricted_payload_fields(payload)
    return JsonResponse(payload, status=200)
```

Add the logger near the top of the file, below the imports:

```python
import logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 6: Point the route at the real view**

In `implementation/api/selahcue_api/platform/urls.py`, change the entitlements line to:

```python
    path("entitlements/manifest", views.entitlement_manifest, name="entitlement-manifest"),
```

- [ ] **Step 7: Run the whole suite**

```bash
cd implementation/api && /private/tmp/selahcue-api-venv/bin/python -m pytest tests -q
```

Expected: everything passes — the previous 63, plus 13 signing tests, plus the manifest slice.

- [ ] **Step 8: Run the same gates CI will run**

```bash
cd implementation/api
/private/tmp/selahcue-api-venv/bin/python manage.py check
/private/tmp/selahcue-api-venv/bin/python manage.py makemigrations --check --noinput
/private/tmp/selahcue-api-venv/bin/python -m compileall -q selahcue_api >/dev/null && echo "compileall OK"
```

Expected: no issues; `exit=0` from the migration check; `compileall OK`.

- [ ] **Step 9: Document the endpoint**

In `implementation/api/README.md`, replace the `entitlements/manifest` stub mention with:

```markdown
### `GET /v1/entitlements/manifest`

The signed offline entitlement (DEC-004). Device-token auth via
`Authorization: Bearer <device_token>`. Returns an Ed25519 envelope whose `payload` is
an opaque base64url string — **verify the signature over that string, then decode it.**
Do not re-serialize the decoded JSON and verify against that; the signature covers the
transmitted bytes.

Issued only for a licence in `ACTIVATABLE_KEY_STATUSES` inside its validity window —
stricter than `license:refresh`, because this endpoint mints a cacheable credential.

Requires `SELAHCUE_ENTITLEMENT_SIGNING_KEY` (see `docs/ops/DEPLOYMENT.md`); without it
the endpoint returns 500 rather than serving an unsigned manifest.
```

- [ ] **Step 10: Commit**

```bash
git add implementation/api/selahcue_api/platform/views.py \
        implementation/api/selahcue_api/platform/urls.py \
        implementation/api/selahcue_api/graphql/errors.py \
        implementation/api/tests/test_entitlement_manifest_slice.py \
        implementation/api/README.md
git commit -m "feat(api): serve the signed entitlement manifest at GET /v1/entitlements/manifest

Replaces the 501 stub. Adds ErrorCode.INTERNAL (500) so a missing signing key
is a loud misconfiguration rather than an unsigned manifest or a misleading
NOT_IMPLEMENTED."
```

---

## Self-Review

**Spec coverage**

| Spec section | Task |
|---|---|
| Envelope shape, `envelope_version`, `alg` allow-list | Task 2 |
| Sign the transmitted encoding | Task 2 (`sign_envelope`, plus the re-serialization test) |
| Payload fields incl. `license_status` verbatim, `license_valid_now` | Task 3 |
| Key management, derived `key_id`, no default, fail loud | Task 2 (+ view mapping in Task 4) |
| Rotation runbook | Task 2, Step 7 |
| Issuance gate (allow-list) + divergence rationale | Task 3 |
| Error handling table (UNAUTHENTICATED / POLICY_DENIED / 500) | Task 3 (service) + Task 4 (HTTP) |
| Three-layer architecture, no new models | Tasks 2–4 |
| Redaction on the payload mapping | Task 3 |
| Testing: tamper, wrong key, binding, expiry, all statuses, window edges, auth modes, audit | Tasks 2–3 |
| CI job + filter | Task 1 |
| Migration-blindness fix | Task 1 |
| `--check --noinput`, no `--dry-run` | Task 1 |
| Python 3.12 alignment | Task 1, Step 1 |
| No aggregator claim (recorded, out of scope) | Not a task — correctly excluded |
| `DEPLOYMENT.md`, `README.md` | Tasks 2 and 4 |

**Type consistency:** `build_entitlement_manifest` returns `EntitlementManifestResult` with `.envelope`, `.payload`, `.device_public_id` — defined in Task 3, consumed with those exact names in Task 4. `sign_envelope`/`verify_envelope`/`load_signing_key`/`derive_key_id` signatures are identical between Task 2's definition and Tasks 3–4's use. `SigningKeyUnavailable` and `InvalidEnvelope` are raised in Task 2 and caught in Tasks 3–4.

**Fixtures:** verified against the real code rather than invented. There is no `conftest.py` and no shared factory — the shipped slices each seed their own data, so Task 3 carries module-local `_seed_license_key` / `_activate` helpers modelled directly on `tests/test_license_refresh_slice.py`. `generate_license_key` returns `GenerateLicenseKeyResult(license_key, full_key, created)`, so the helper can hand back the `AppLicenseKey` the status tests need to mutate. The activation response nests the device id at `payload["device"]["device_public_id"]` with the token at `payload["activation_token"]`, both confirmed against `platform/views.py:94-115`.

**One thing the implementer must not do:** if the parametrised licence-status test proves awkward, do not narrow it to a hand-picked list of statuses. Driving it off `LicenseKeyStatus` is the entire point — it is what makes a future ninth status fail the suite instead of silently qualifying for a signed multi-year entitlement.
