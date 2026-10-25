"""One organisation, one number, on every surface (86ak5mn0m).

The ticket's expected behaviour: "A church on Pro sees one licence with 3 instance slots, in
the portal, in the manifest and in the admin console — the same 3 everywhere."

Before this change the admin console showed `AdminCustomer.deviceLimit`, the ORG's number, which
nothing enforced and which could differ from the licence's. This file issues ONE licence on a
plan with its own seat count and reads the number back from every place it is reported:

*   the admin console (`AdminLicenseKey.deviceLimit`),
*   the signed entitlement manifest (`instances_limit`),
*   the refresh endpoint (`instances.limit`),
*   and the activation REFUSAL POINT (the device that is turned away is the one after that many).

If any surface ever reads a different source, one of the equalities below fails. The customer
PORTAL has no limit API yet (follow-up); it is not asserted here because there is nothing to
assert.
"""

from __future__ import annotations

import base64
import json

import pytest
from django.core.cache import cache
from django.test import override_settings

from licensing_test_support import issue_key, seat_plan, seed_org
from selahcue_api.apps.entitlements.signing import load_signing_key, verify_envelope
from selahcue_api.graphql.admin_schema import schema as admin_schema

pytestmark = pytest.mark.django_db

SEATS = 4
TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")


@pytest.fixture(autouse=True)
def _fresh_budgets_and_signing_key(settings):
    cache.clear()
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1000, 60)


def _post(client, path, body, **extra):
    return client.post(path, data=json.dumps(body), content_type="application/json", **extra)


def _activate(client, full_key, fingerprint):
    return _post(
        client,
        "/v1/activations",
        {
            "idempotency_key": f"act-{fingerprint}-0001",
            "license_key": full_key,
            "device_fingerprint": fingerprint,
            "platform": "macos",
        },
    )


def _admin_reported_limit(client, customer_id):
    query = """
        query ($search: String!) {
          adminCustomers(search: $search, first: 5) {
            nodes { id licenseKeys { nodes { id deviceLimit } } }
          }
        }
    """
    response = client.post(
        "/graphql/admin",
        data=json.dumps({"query": query, "variables": {"search": "Seat Church"}}),
        content_type="application/json",
        HTTP_X_SELAHCUE_ACTOR_KIND="staff",
        HTTP_X_SELAHCUE_ACTOR_ID="staff_ops_1",
        HTTP_X_SELAHCUE_STAFF_PERMISSIONS="view_customers",
    )
    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body, body
    (customer,) = [n for n in body["data"]["adminCustomers"]["nodes"] if n["id"] == str(customer_id)]
    (key,) = customer["licenseKeys"]["nodes"]
    return key["deviceLimit"]


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_one_org_reports_the_same_limit_on_every_surface(client):
    plan = seat_plan("OWN-EVERYWHERE", SEATS)
    org = seed_org("everywhere")
    result = issue_key(org, tag="everywhere", plan_code=plan.code)
    full_key = result.full_key

    # Admin console.
    admin_limit = _admin_reported_limit(client, org.id)

    # Fill the key to its limit; the device after the last one is the refusal point.
    first = _activate(client, full_key, "fp-0")
    assert first.status_code == 200, first.content
    token = first.json()["activation_token"]
    for index in range(1, SEATS):
        assert _activate(client, full_key, f"fp-{index}").status_code == 200
    refused = _activate(client, full_key, "fp-over")
    assert refused.status_code == 403
    admitted_before_refusal = SEATS  # the loop above admitted exactly this many

    # Signed manifest.
    manifest = client.get("/v1/entitlements/manifest", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert manifest.status_code == 200, manifest.content
    payload = verify_envelope(
        manifest.json(), public_key=load_signing_key(TEST_SEED_B64).public_key()
    )
    manifest_limit = payload["instances_limit"]

    # Refresh endpoint.
    refresh = _post(client, "/v1/license:refresh", {}, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert refresh.status_code == 200, refresh.content
    refresh_limit = refresh.json()["instances"]["limit"]

    assert admin_limit == manifest_limit == refresh_limit == admitted_before_refusal == SEATS, (
        f"surfaces disagree: admin={admin_limit} manifest={manifest_limit} "
        f"refresh={refresh_limit} refusal-point={admitted_before_refusal} plan={SEATS}"
    )
    assert refresh.json()["instances"]["used"] == SEATS


def test_the_admin_schema_no_longer_exposes_an_org_level_device_limit():
    customer_fields = {f.name for f in admin_schema.get_type_by_name("AdminCustomer").fields}
    key_fields = {f.name for f in admin_schema.get_type_by_name("AdminLicenseKey").fields}
    create_input = {
        f.name for f in admin_schema.get_type_by_name("AdminCreateCustomerInput").fields
    }
    generate_input = {
        f.name for f in admin_schema.get_type_by_name("AdminGenerateLicenseKeyInput").fields
    }

    assert "device_limit" not in customer_fields, "AdminCustomer reports a number nothing enforces"
    assert "device_limit" not in create_input, "staff can type an org-level limit"
    assert "device_limit" not in generate_input, "staff can type a licence limit that contradicts its plan"
    # POSITIVE CONTROL: the same introspection finds the one place the number now lives, so the
    # absences above are not a lookup that returns nothing for every name.
    assert "device_limit" in key_fields
    assert "plan_code" in generate_input
