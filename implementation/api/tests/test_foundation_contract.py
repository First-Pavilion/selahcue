import json

import pytest
from django.test import Client, RequestFactory, override_settings


def test_staff_permission_checks_deny_missing_and_cross_surface_access():
    from selahcue_api.graphql.context import (
        ActorContext,
        ActorKind,
        StaffPermission,
        require_staff_permission,
    )
    from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

    with pytest.raises(SafeAPIError) as missing:
        require_staff_permission(None, StaffPermission.VIEW_PLATFORM_HEALTH)
    assert missing.value.code is ErrorCode.UNAUTHENTICATED

    customer_actor = ActorContext(
        kind=ActorKind.CUSTOMER,
        actor_id="customer_1",
        org_id="org_1",
    )
    with pytest.raises(SafeAPIError) as wrong_surface:
        require_staff_permission(customer_actor, StaffPermission.VIEW_PLATFORM_HEALTH)
    assert wrong_surface.value.code is ErrorCode.PERMISSION_DENIED

    staff_actor = ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_1",
        staff_permissions=frozenset({StaffPermission.VIEW_CUSTOMERS}),
    )
    with pytest.raises(SafeAPIError) as missing_permission:
        require_staff_permission(staff_actor, StaffPermission.GENERATE_LICENSE_KEY)
    assert missing_permission.value.code is ErrorCode.PERMISSION_DENIED


def test_customer_scope_hides_other_tenants():
    from selahcue_api.graphql.context import ActorContext, ActorKind, require_customer_org
    from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

    actor = ActorContext(
        kind=ActorKind.CUSTOMER,
        actor_id="customer_1",
        org_id="org_1",
    )

    assert require_customer_org(actor, "org_1") is actor
    with pytest.raises(SafeAPIError) as other_tenant:
        require_customer_org(actor, "org_2")
    assert other_tenant.value.code is ErrorCode.NOT_FOUND


def test_idempotency_reason_and_redaction_boundaries_are_safe():
    from selahcue_api.graphql.context import require_reason, validate_idempotency_key
    from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
    from selahcue_api.graphql.redaction import (
        assert_no_restricted_payload_fields,
        redact_public_payload,
    )

    assert validate_idempotency_key(" request-2026-08-08-0001 ") == "request-2026-08-08-0001"
    with pytest.raises(SafeAPIError) as short_key:
        validate_idempotency_key("abc")
    assert short_key.value.code is ErrorCode.VALIDATION_FAILED

    assert require_reason("Customer requested pilot extension") == "Customer requested pilot extension"
    with pytest.raises(SafeAPIError) as short_reason:
        require_reason("fix")
    assert short_reason.value.code is ErrorCode.VALIDATION_FAILED

    raw_payload = {
        "license_key": "fixture-placeholder",
        "provider_secret": "fixture-placeholder",
        "bible_text": "fixture-placeholder",
        "nested": {"content": "fixture-placeholder"},
        "safe_code": "NOT_IMPLEMENTED",
    }
    with pytest.raises(SafeAPIError) as unsafe_payload:
        assert_no_restricted_payload_fields(raw_payload)
    assert unsafe_payload.value.code is ErrorCode.VALIDATION_FAILED

    redacted = redact_public_payload(raw_payload)
    assert_no_restricted_payload_fields(redacted)
    assert redacted["safe_code"] == "NOT_IMPLEMENTED"
    assert redacted["license_key"] == "[redacted]"

    camel_payload = {
        "licenseKey": "fixture-placeholder",
        "fullKey": "fixture-placeholder",
        "providerSecret": "fixture-placeholder",
        "bibleText": "fixture-placeholder",
    }
    with pytest.raises(SafeAPIError) as unsafe_camel_payload:
        assert_no_restricted_payload_fields(camel_payload)
    assert unsafe_camel_payload.value.code is ErrorCode.VALIDATION_FAILED

    camel_redacted = redact_public_payload(camel_payload)
    assert_no_restricted_payload_fields(camel_redacted)
    assert camel_redacted["licenseKey"] == "[redacted]"


def test_route_contracts_keep_admin_account_and_desktop_surfaces_separate():
    from selahcue_api.graphql.route_contracts import (
        billing_webhook_contract,
        desktop_command_contracts,
        graphql_endpoint_contracts,
    )

    graphql_contracts = graphql_endpoint_contracts(debug=False)
    assert [contract.path for contract in graphql_contracts] == [
        "graphql/admin",
        "graphql/account",
    ]
    assert [contract.surface for contract in graphql_contracts] == ["admin", "account"]
    assert all(contract.allow_queries_via_get is False for contract in graphql_contracts)
    assert all(contract.multipart_uploads_enabled is False for contract in graphql_contracts)
    assert all(contract.graphql_ide is None for contract in graphql_contracts)

    debug_contracts = graphql_endpoint_contracts(debug=True)
    assert {contract.graphql_ide for contract in debug_contracts} == {"graphiql"}

    desktop_paths = [contract.path for contract in desktop_command_contracts()]
    assert desktop_paths == [
        "v1/activations",
        "v1/activations:bound",
        "v1/activations:bound-with-session",
        # The native sign-in pair (86ak5t1gw): the desktop reaches account sign-in here, not on
        # `/graphql/account`, which stays CSRF-enforced for browsers.
        "v1/sessions",
        "v1/activations:with-session",
        "v1/sessions:revoke",
        "v1/license:refresh",
        "v1/entitlements/manifest",
        "v1/downloads:prepare",
        "v1/downloads/<lease_id>:complete",
        "v1/usage-events:batch",
        "v1/stt/session",
        "v1/quota",
    ]
    assert billing_webhook_contract().path == "webhooks/billing/<provider>"


def test_header_actor_context_is_trusted_only_when_explicitly_enabled(settings):
    from selahcue_api.graphql.context import ActorKind, StaffPermission, actor_from_request

    request = RequestFactory().get(
        "/graphql/admin",
        HTTP_X_SELAHCUE_ACTOR_KIND="staff",
        HTTP_X_SELAHCUE_ACTOR_ID="staff_1",
        HTTP_X_SELAHCUE_STAFF_PERMISSIONS="view_platform_health",
    )

    assert actor_from_request(request) is None

    with override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True):
        actor = actor_from_request(request)

    assert actor.kind is ActorKind.STAFF
    assert actor.actor_id == "staff_1"
    assert actor.staff_permissions == frozenset({StaffPermission.VIEW_PLATFORM_HEALTH})


@pytest.mark.parametrize("kind", ["staff", "customer", "device", "service", "anonymous"])
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_dev_actor_header_bridge_refuses_only_the_internal_anonymous_kind(kind):
    from selahcue_api.graphql.context import ActorKind, actor_from_request

    request = RequestFactory().get(
        "/graphql/admin",
        HTTP_X_SELAHCUE_ACTOR_KIND=kind,
        HTTP_X_SELAHCUE_ACTOR_ID="actor_1",
    )
    actor = actor_from_request(request)
    if kind == "anonymous":
        assert actor is None
    else:
        assert actor.kind is ActorKind(kind)
        assert actor.actor_id == "actor_1"


@pytest.mark.django_db
def test_django_app_boundaries_are_registered(settings):
    import django
    from django.apps import apps

    django.setup()

    expected_labels = {
        "selahcue_accounts",
        "selahcue_billing",
        "selahcue_license_keys",
        "selahcue_catalogue",
        "selahcue_entitlements",
        "selahcue_downloads",
        "selahcue_devices",
        "selahcue_audit",
    }
    assert expected_labels.issubset({config.label for config in apps.get_app_configs()})
    assert settings.GRAPHQL_ALLOW_QUERIES_VIA_GET is False
    assert settings.GRAPHQL_MULTIPART_UPLOADS_ENABLED is False


@pytest.mark.django_db
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_graphql_endpoints_authorize_staff_and_customer_contexts(client):
    staff_query = {"query": "{ adminHealth { surface ready } }"}
    unauthenticated = client.post(
        "/graphql/admin",
        data=json.dumps(staff_query),
        content_type="application/json",
    )
    assert unauthenticated.status_code == 200
    assert unauthenticated.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"

    allowed_staff = client.post(
        "/graphql/admin",
        data=json.dumps(staff_query),
        content_type="application/json",
        HTTP_X_SELAHCUE_ACTOR_KIND="staff",
        HTTP_X_SELAHCUE_ACTOR_ID="staff_1",
        HTTP_X_SELAHCUE_STAFF_PERMISSIONS="view_platform_health",
    )
    assert allowed_staff.status_code == 200
    assert allowed_staff.json()["data"]["adminHealth"] == {
        "surface": "admin",
        "ready": True,
    }

    account_query = {"query": "{ accountViewer { surface actorId orgId } }"}
    allowed_customer = client.post(
        "/graphql/account",
        data=json.dumps(account_query),
        content_type="application/json",
        HTTP_X_SELAHCUE_ACTOR_KIND="customer",
        HTTP_X_SELAHCUE_ACTOR_ID="customer_1",
        HTTP_X_SELAHCUE_ORG_ID="org_1",
    )
    assert allowed_customer.status_code == 200
    assert allowed_customer.json()["data"]["accountViewer"] == {
        "surface": "account",
        "actorId": "customer_1",
        "orgId": "org_1",
    }


@pytest.mark.django_db
def test_graphql_endpoints_keep_browser_csrf_and_reject_get_queries():
    client = Client(enforce_csrf_checks=True)
    query = {"query": "{ adminHealth { surface ready } }"}

    csrf_blocked = client.post(
        "/graphql/admin",
        data=json.dumps(query),
        content_type="application/json",
        HTTP_X_SELAHCUE_ACTOR_KIND="staff",
        HTTP_X_SELAHCUE_ACTOR_ID="staff_1",
        HTTP_X_SELAHCUE_STAFF_PERMISSIONS="view_platform_health",
    )
    assert csrf_blocked.status_code == 403

    get_rejected = client.get(
        "/graphql/admin",
        data={"query": "{ adminHealth { surface ready } }"},
    )
    assert get_rejected.status_code in {400, 405}


@pytest.mark.django_db
def test_a_browser_can_obtain_a_csrf_token_and_post_an_account_mutation(settings):
    """Run the protected account resolver through actual CSRF middleware."""
    from django.core.cache import cache

    cache.clear()
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0
    settings.CSRF_COOKIE_SECURE = True

    client = Client(enforce_csrf_checks=True)
    other_client = Client(enforce_csrf_checks=True)
    mutation = {
        "query": 'mutation { resendVerificationEmail(email: "nobody@browser.example") { accepted } }'
    }

    def post_mutation(browser, origin="https://testserver", **extra):
        return browser.post(
            "/graphql/account",
            data=json.dumps(mutation),
            content_type="application/json",
            secure=True,
            HTTP_ORIGIN=origin,
            **extra,
        )

    assert post_mutation(client).status_code == 403
    bootstrap = client.get("/graphql/csrf", secure=True, HTTP_ORIGIN="https://evil.example")
    assert bootstrap.status_code == 200
    assert bootstrap.json() == {"ready": True}
    assert bootstrap["Cache-Control"] == "no-store"
    assert "cookie" in {name.strip().lower() for name in bootstrap["Vary"].split(",")}
    assert not any(name.lower().startswith("access-control-") for name in bootstrap.headers)

    cookie = bootstrap.cookies[settings.CSRF_COOKIE_NAME]
    assert len(cookie.value) == 32 and cookie.value.isascii() and cookie.value.isalnum()
    assert cookie["path"] == "/"
    assert cookie["samesite"] == "Strict"
    assert cookie["secure"]
    assert not cookie["httponly"]
    assert not cookie["domain"]

    assert "X-CSRFToken" in bootstrap.headers
    masked_token = bootstrap["X-CSRFToken"]
    assert len(masked_token) == 64 and masked_token.isascii() and masked_token.isalnum()

    head = client.head("/graphql/csrf", secure=True)
    assert head.status_code == 405
    assert head["Allow"] == "GET"
    assert client.post(
        "/graphql/csrf",
        secure=True,
        HTTP_ORIGIN="https://testserver",
        HTTP_X_CSRFTOKEN=masked_token,
    ).status_code == 405

    # Try the header before giving the second client any cookie, then with its own.
    assert post_mutation(other_client, HTTP_X_CSRFTOKEN=masked_token).status_code == 403
    assert other_client.get("/graphql/csrf", secure=True).status_code == 200
    assert post_mutation(other_client, HTTP_X_CSRFTOKEN=masked_token).status_code == 403
    assert post_mutation(client).status_code == 403
    assert post_mutation(
        client, origin="https://evil.example", HTTP_X_CSRFTOKEN=masked_token
    ).status_code == 403

    for token in (masked_token, cookie.value):
        accepted = post_mutation(client, HTTP_X_CSRFTOKEN=token)
        assert accepted.status_code == 200
        assert accepted.json()["data"]["resendVerificationEmail"]["accepted"] is True


def test_the_csrf_bootstrap_route_is_declared_like_every_other_route():
    from selahcue_api.graphql.route_contracts import browser_bootstrap_contract

    contract = browser_bootstrap_contract()
    assert (contract.surface, contract.path, contract.method) == (
        "browser",
        "graphql/csrf",
        "GET",
    )
    # Unauthenticated by design: it hands out a CSRF token, which is not a credential.
    assert contract.auth_context == "none_issues_csrf_cookie"


@pytest.mark.django_db
def test_graphql_errors_are_safely_coded_without_internal_messages(client):
    malformed = client.post(
        "/graphql/admin",
        data=json.dumps({"query": "{ definitelyMissingField }"}),
        content_type="application/json",
    )

    assert malformed.status_code == 200
    error = malformed.json()["errors"][0]
    assert error["extensions"]["code"] == "VALIDATION_FAILED"
    assert error["message"] == "The request is invalid."


@pytest.mark.django_db
def test_graphql_http_request_errors_use_safe_json_envelope(client):
    malformed = client.post(
        "/graphql/admin",
        data="{not-json",
        content_type="application/json",
    )
    assert malformed.status_code == 400
    assert malformed["content-type"].startswith("application/json")
    assert malformed.json()["errors"][0]["extensions"]["code"] == "VALIDATION_FAILED"
    assert malformed.json()["errors"][0]["message"] == "The request is invalid."

    missing_query = client.post(
        "/graphql/admin",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert missing_query.status_code == 400
    assert missing_query["content-type"].startswith("application/json")
    assert missing_query.json()["errors"][0]["extensions"]["code"] == "VALIDATION_FAILED"


@pytest.mark.django_db
def test_graphql_introspection_is_disabled_when_debug_is_false(client):
    result = client.post(
        "/graphql/admin",
        data=json.dumps({"query": "{ __schema { queryType { name } } }"}),
        content_type="application/json",
    )

    assert result.status_code == 200
    assert result.json()["errors"][0]["extensions"]["code"] == "VALIDATION_FAILED"


@pytest.mark.django_db
def test_desktop_and_webhook_stubs_return_safe_not_implemented_payloads(client):
    for path in [
        # /v1/activations is implemented (device-activation slice) — covered in its own test file.
        # /v1/license:refresh is implemented (device-token auth) — covered in its own test file.
        "/v1/downloads:prepare",
        "/v1/downloads/lease_1:complete",
        "/v1/usage-events:batch",
        "/webhooks/billing/manual",
    ]:
        response = client.post(path, data=json.dumps({}), content_type="application/json")
        assert response.status_code == 501
        body = response.json()
        assert body["error"]["code"] == "NOT_IMPLEMENTED"
        assert "license_key" not in body
        assert "secret" not in body
        assert "bible_text" not in body
        assert "content" not in body

    # /v1/entitlements/manifest is implemented (signed offline entitlement, DEC-004) —
    # covered in tests/test_entitlement_manifest_slice.py. It is no longer a stub, but it
    # must still deny an unauthenticated caller rather than leak anything, so the contract
    # this test guards is preserved here in its post-implementation form.
    manifest = client.get("/v1/entitlements/manifest")
    assert manifest.status_code == 401
    body = manifest.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "license_key" not in body
    assert "secret" not in body


@pytest.mark.django_db
def test_desktop_and_webhook_stubs_are_not_blocked_by_browser_csrf():
    client = Client(enforce_csrf_checks=True)

    for path in [
        # /v1/activations is implemented — its CSRF-exemption is covered in its own test file.
        # /v1/license:refresh is implemented (device-token auth) — covered in its own test file.
        "/v1/downloads:prepare",
        "/v1/downloads/lease_1:complete",
        "/v1/usage-events:batch",
        "/webhooks/billing/manual",
    ]:
        response = client.post(path, data=json.dumps({}), content_type="application/json")
        assert response.status_code == 501
        assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"


def test_every_error_code_has_a_chosen_http_status():
    """`_STATUS_BY_CODE` must be TOTAL over `ErrorCode`.

    `command_error_response` reads it as `_STATUS_BY_CODE.get(code, 400)`, so a member with no
    row does not raise — it silently inherits 400. That default is not always right: an
    UNAUTHENTICATED served as 400 would break a client's retry logic, and a 500-class failure
    reported as 400 blames the caller for the server's fault. The gap is therefore invisible at
    runtime and only shows up as a wrong status on a surface nobody was watching.

    This is not hypothetical bookkeeping. `PASSWORD_INVALID` was added to `ErrorCode` in this
    slice and shipped through review with no row here; the `.get` default absorbed it and no
    test noticed.
    """
    from selahcue_api.graphql.errors import ErrorCode
    from selahcue_api.platform.responses import _STATUS_BY_CODE

    assert set(_STATUS_BY_CODE) == set(ErrorCode), (
        "the /v1 code-to-status map is no longer total over ErrorCode. Missing members fall "
        f"through to the 400 default in `command_error_response`. Missing: "
        f"{sorted(c.value for c in set(ErrorCode) - set(_STATUS_BY_CODE))}; "
        f"unknown keys: {sorted(str(c) for c in set(_STATUS_BY_CODE) - set(ErrorCode))}"
    )
    # Every status must be a real HTTP error status, not a default that happens to be an int.
    # Without this the assertion above passes on a row added as `None` or `0` to silence it.
    assert all(400 <= status <= 599 for status in _STATUS_BY_CODE.values()), (
        f"a code maps to a status outside the 4xx/5xx range: {sorted(set(_STATUS_BY_CODE.values()))}"
    )
