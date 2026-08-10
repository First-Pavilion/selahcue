import json
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone


def post_admin_graphql(client, query, variables=None, *, permissions=""):
    return client.post(
        "/graphql/admin",
        data=json.dumps({"query": query, "variables": variables or {}}),
        content_type="application/json",
        HTTP_X_SELAHCUE_ACTOR_KIND="staff",
        HTTP_X_SELAHCUE_ACTOR_ID="staff_ops_1",
        HTTP_X_SELAHCUE_STAFF_PERMISSIONS=permissions,
    )


CREATE_CUSTOMER_MUTATION = """
    mutation CreateCustomer($input: AdminCreateCustomerInput!) {
      adminCreateCustomer(input: $input) {
        created
        customer {
          id
          name
          status
          primaryContactEmail
          country
          timezone
          plan
          seatLimit
          deviceLimit
        }
      }
    }
"""


GENERATE_KEY_MUTATION = """
    mutation GenerateKey($input: AdminGenerateLicenseKeyInput!) {
      adminGenerateLicenseKey(input: $input) {
        created
        fullKey
        licenseKey {
          id
          keyType
          status
          keyPrefix
          keySuffix
          maskedKey
          featureScope
          startsAt
          expiresAt
          customer {
            id
            name
          }
        }
      }
    }
"""


def create_customer_input(idempotency_key="customer-create-0001", **overrides):
    payload = {
        "idempotencyKey": idempotency_key,
        "name": "River City Church",
        "primaryContactEmail": "ops@rivercity.example",
        "country": "NG",
        "timezone": "Africa/Lagos",
        "status": "PROSPECT",
        "plan": "TRIAL",
        "seatLimit": 5,
        "deviceLimit": 3,
    }
    payload.update(overrides)
    return payload


def generate_key_input(customer_id, idempotency_key="license-generate-0001", **overrides):
    starts_at = timezone.now().replace(microsecond=0)
    expires_at = starts_at + timedelta(days=30)
    payload = {
        "idempotencyKey": idempotency_key,
        "customerId": str(customer_id),
        "keyType": "TRIAL",
        "featureScope": "CHURCH",
        "startsAt": starts_at.isoformat().replace("+00:00", "Z"),
        "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
        "timezone": "Africa/Lagos",
        "seatLimit": 5,
        "deviceLimit": 3,
        "territory": "NG",
        "reason": "Prospect requested a thirty day pilot.",
    }
    payload.update(overrides)
    return payload


def create_customer_via_graphql(client, *, idempotency_key="customer-create-0001", permissions=None):
    response = post_admin_graphql(
        client,
        CREATE_CUSTOMER_MUTATION,
        {"input": create_customer_input(idempotency_key)},
        permissions=permissions or "manage_customers,view_customers,generate_license_key",
    )
    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body
    return body["data"]["adminCreateCustomer"]["customer"]


@pytest.mark.django_db
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_staff_can_create_customer_and_generate_show_once_license_key(client):
    create_response = post_admin_graphql(
        client,
        CREATE_CUSTOMER_MUTATION,
        {"input": create_customer_input()},
        permissions="manage_customers,view_customers,generate_license_key",
    )
    assert create_response.status_code == 200
    create_body = create_response.json()
    assert "errors" not in create_body
    customer = create_body["data"]["adminCreateCustomer"]["customer"]
    assert create_body["data"]["adminCreateCustomer"]["created"] is True
    assert customer["name"] == "River City Church"
    assert customer["primaryContactEmail"] == "ops@rivercity.example"

    key_response = post_admin_graphql(
        client,
        GENERATE_KEY_MUTATION,
        {"input": generate_key_input(customer["id"])},
        permissions="manage_customers,view_customers,generate_license_key",
    )
    assert key_response.status_code == 200
    key_body = key_response.json()
    assert "errors" not in key_body
    key_payload = key_body["data"]["adminGenerateLicenseKey"]
    full_key = key_payload["fullKey"]
    license_key = key_payload["licenseKey"]
    assert key_payload["created"] is True
    assert full_key.startswith("SC-TRIAL-")
    assert license_key["maskedKey"] != full_key
    assert license_key["keyPrefix"] == full_key[:12]
    assert license_key["keySuffix"] == full_key[-4:]
    assert license_key["customer"]["id"] == customer["id"]

    search_customers = """
        query SearchCustomers($search: String!) {
          adminCustomers(search: $search, first: 10) {
            totalCount
            nodes {
              id
              name
              licenseKeys {
                totalCount
                nodes {
                  id
                  maskedKey
                  keyPrefix
                  keySuffix
                  status
                }
              }
            }
          }
        }
    """
    search_response = post_admin_graphql(
        client,
        search_customers,
        {"search": "rivercity"},
        permissions="view_customers",
    )
    assert search_response.status_code == 200
    search_body = search_response.json()
    assert "errors" not in search_body
    assert search_body["data"]["adminCustomers"]["totalCount"] == 1
    listed_key = search_body["data"]["adminCustomers"]["nodes"][0]["licenseKeys"]["nodes"][0]
    assert listed_key["maskedKey"] == license_key["maskedKey"]
    assert full_key not in json.dumps(search_body)

    from selahcue_api.apps.audit.models import AuditEvent
    from selahcue_api.apps.license_keys.models import AppLicenseKey

    key_record = AppLicenseKey.objects.get()
    assert key_record.secret_hash
    assert key_record.secret_fingerprint
    assert full_key not in key_record.secret_hash
    assert full_key != key_record.secret_fingerprint
    assert key_record.key_prefix == full_key[:12]
    assert key_record.key_suffix == full_key[-4:]

    audit_events = list(AuditEvent.objects.order_by("created_at"))
    assert [event.action for event in audit_events] == [
        "customer.created",
        "license_key.generated",
    ]
    assert full_key not in json.dumps(
        [
            {
                "action": event.action,
                "target": event.target_id,
                "before": event.before,
                "after": event.after,
                "reason": event.reason,
            }
            for event in audit_events
        ],
        default=str,
    )


@pytest.mark.django_db
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_customer_creation_requires_permission_and_is_idempotent(client):
    variables = {"input": create_customer_input("customer-create-idempotent")}

    first_response = post_admin_graphql(
        client,
        CREATE_CUSTOMER_MUTATION,
        variables,
        permissions="manage_customers,view_customers",
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()["data"]["adminCreateCustomer"]
    assert first_payload["created"] is True

    second_response = post_admin_graphql(
        client,
        CREATE_CUSTOMER_MUTATION,
        variables,
        permissions="manage_customers,view_customers",
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()["data"]["adminCreateCustomer"]
    assert second_payload["created"] is False
    assert second_payload["customer"]["id"] == first_payload["customer"]["id"]

    denied_response = post_admin_graphql(
        client,
        CREATE_CUSTOMER_MUTATION,
        {"input": create_customer_input("customer-create-denied")},
        permissions="view_customers",
    )
    assert denied_response.status_code == 200
    assert denied_response.json()["errors"][0]["extensions"]["code"] == "PERMISSION_DENIED"

    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.audit.models import AuditEvent

    assert CustomerOrg.objects.count() == 1
    assert AuditEvent.objects.filter(action="customer.created").count() == 1


@pytest.mark.django_db
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_license_key_generation_is_idempotent_and_never_replays_full_key(client):
    customer = create_customer_via_graphql(client, idempotency_key="customer-create-0002")
    variables = {"input": generate_key_input(customer["id"], "license-generate-0002")}

    first_response = post_admin_graphql(
        client,
        GENERATE_KEY_MUTATION,
        variables,
        permissions="generate_license_key",
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()["data"]["adminGenerateLicenseKey"]
    assert first_payload["created"] is True
    assert first_payload["fullKey"]

    second_response = post_admin_graphql(
        client,
        GENERATE_KEY_MUTATION,
        variables,
        permissions="generate_license_key",
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()["data"]["adminGenerateLicenseKey"]
    assert second_payload["created"] is False
    assert second_payload["fullKey"] is None
    assert second_payload["licenseKey"]["id"] == first_payload["licenseKey"]["id"]

    from selahcue_api.apps.audit.models import AuditEvent
    from selahcue_api.apps.license_keys.models import AppLicenseKey

    assert AppLicenseKey.objects.count() == 1
    assert AuditEvent.objects.filter(action="license_key.generated").count() == 1
    assert first_payload["fullKey"] not in json.dumps(second_response.json())


@pytest.mark.django_db
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_license_key_generation_rejects_unsafe_requests_without_committing(client):
    customer = create_customer_via_graphql(client, idempotency_key="customer-create-0003")
    starts_at = timezone.now().replace(microsecond=0)
    expires_at = starts_at - timedelta(days=1)

    invalid_window = post_admin_graphql(
        client,
        GENERATE_KEY_MUTATION,
        {
            "input": generate_key_input(
                customer["id"],
                "license-generate-invalid-window",
                startsAt=starts_at.isoformat().replace("+00:00", "Z"),
                expiresAt=expires_at.isoformat().replace("+00:00", "Z"),
            )
        },
        permissions="generate_license_key",
    )
    assert invalid_window.status_code == 200
    assert invalid_window.json()["errors"][0]["extensions"]["code"] == "VALIDATION_FAILED"

    short_reason = post_admin_graphql(
        client,
        GENERATE_KEY_MUTATION,
        {
            "input": generate_key_input(
                customer["id"],
                "license-generate-short-reason",
                reason="trial",
            )
        },
        permissions="generate_license_key",
    )
    assert short_reason.status_code == 200
    assert short_reason.json()["errors"][0]["extensions"]["code"] == "VALIDATION_FAILED"

    zero_limits = post_admin_graphql(
        client,
        GENERATE_KEY_MUTATION,
        {
            "input": generate_key_input(
                customer["id"],
                "license-generate-zero-limits",
                seatLimit=0,
                deviceLimit=0,
            )
        },
        permissions="generate_license_key",
    )
    assert zero_limits.status_code == 200
    assert zero_limits.json()["errors"][0]["extensions"]["code"] == "VALIDATION_FAILED"

    missing_permission = post_admin_graphql(
        client,
        GENERATE_KEY_MUTATION,
        {"input": generate_key_input(customer["id"], "license-generate-no-perm")},
        permissions="view_customers",
    )
    assert missing_permission.status_code == 200
    assert missing_permission.json()["errors"][0]["extensions"]["code"] == "PERMISSION_DENIED"

    missing_customer = post_admin_graphql(
        client,
        GENERATE_KEY_MUTATION,
        {"input": generate_key_input("999999", "license-generate-missing-customer")},
        permissions="generate_license_key",
    )
    assert missing_customer.status_code == 200
    assert missing_customer.json()["errors"][0]["extensions"]["code"] == "NOT_FOUND"

    from selahcue_api.apps.license_keys.models import AppLicenseKey

    assert AppLicenseKey.objects.count() == 0


SEARCH_CUSTOMERS_COUNT = """
    query SearchCustomers($search: String!, $first: Int!) {
      adminCustomers(search: $search, first: $first) {
        totalCount
        nodes { id name }
      }
    }
"""


@pytest.mark.django_db
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_admin_customers_total_count_is_the_true_match_count_not_the_page_size(client):
    perms = "manage_customers,view_customers"
    for i in range(3):
        resp = post_admin_graphql(
            client,
            CREATE_CUSTOMER_MUTATION,
            {
                "input": create_customer_input(
                    idempotency_key=f"count-customer-{i:04d}",
                    name=f"Countable Grace Church {i}",
                    primaryContactEmail=f"ops+count{i}@countable.example",
                )
            },
            permissions=perms,
        )
        assert resp.status_code == 200 and "errors" not in resp.json()

    # Page of 2, but 3 match — totalCount must report 3 (the true count), not the page size.
    resp = post_admin_graphql(
        client,
        SEARCH_CUSTOMERS_COUNT,
        {"search": "countable grace church", "first": 2},
        permissions="view_customers",
    )
    assert resp.status_code == 200
    conn = resp.json()["data"]["adminCustomers"]
    assert len(conn["nodes"]) == 2
    assert conn["totalCount"] == 3


@pytest.mark.django_db
def test_license_key_generation_rolls_back_when_audit_write_fails(monkeypatch):
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.models import AppLicenseKey
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name="Audit Rollback Church",
        slug="audit-rollback-church",
        primary_contact_email="ops@rollback.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=3,
        created_by_actor_id="staff_ops_1",
        idempotency_key="customer-rollback-0001",
    )

    def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated audit storage failure")

    monkeypatch.setattr("selahcue_api.apps.license_keys.services.record_audit_event", fail_audit)

    starts_at = timezone.now().replace(microsecond=0)
    actor = ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_ops_1",
        staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
    )

    with pytest.raises(RuntimeError):
        generate_license_key(
            actor,
            GenerateLicenseKeyData(
                idempotency_key="license-generate-audit-fails",
                customer_id=str(customer.id),
                key_type="TRIAL",
                feature_scope="CHURCH",
                starts_at=starts_at,
                expires_at=starts_at + timedelta(days=30),
                timezone="Africa/Lagos",
                seat_limit=5,
                device_limit=3,
                territory="NG",
                reason="Prospect requested a thirty day pilot.",
            ),
        )

    assert AppLicenseKey.objects.count() == 0
