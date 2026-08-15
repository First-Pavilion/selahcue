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
        "v1/license:refresh",
        "v1/entitlements/manifest",
        "v1/downloads:prepare",
        "v1/downloads/<lease_id>:complete",
        "v1/usage-events:batch",
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
    """THE browser-shaped test. The suite above pins that a token-less POST is refused; on its
    own that is only half a contract, and the missing half is why every account mutation 403'd
    for every real browser while the whole suite stayed green.

    Django's test client bypasses CSRF unless `enforce_csrf_checks=True`, so the default
    `client` fixture cannot see this class of break at all. The surface declares
    `customer_session_with_csrf` (`route_contracts.py`) and `CsrfViewMiddleware` enforces it,
    but nothing issued a `csrftoken` cookie to the SPA origin — no `get_token`, no
    `@ensure_csrf_cookie` — and the SPA is served as static files, so Django never rendered a
    page that could set one. The token could therefore never exist, and `graphql.ts` (which
    sends the header "whenever the cookie is readable") had nothing to read.

    This walks the real sequence: refused without a token, seed the cookie with the same-origin
    bootstrap GET, then the identical POST succeeds.
    """
    from django.core.cache import cache

    # The resend budget lives in the process-wide LocMemCache; budget spent by an earlier test
    # would 429 this one and hide what it is actually asserting.
    cache.clear()
    # The constant-time floor is not this test's subject — do not pay 0.25s for it.
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0

    client = Client(enforce_csrf_checks=True)
    mutation = {
        "query": 'mutation { resendVerificationEmail(email: "nobody@browser.example") { accepted } }'
    }

    def post_mutation(**extra):
        return client.post(
            "/graphql/account",
            data=json.dumps(mutation),
            content_type="application/json",
            **extra,
        )

    # 1. What every browser got: 403, with an HTML body `graphqlRequest` cannot parse — which
    #    surfaces to the user as a permanent "we couldn't verify your email just now".
    blocked = post_mutation()
    assert blocked.status_code == 403

    # 2. The SPA seeds the cookie on load with a same-origin GET. This is an XHR from the
    #    already-loaded page, so the top-level browsing context is the app's own site and the
    #    SameSite=Strict cookie is both settable here and sent on step 3 — the cross-site
    #    top-level navigation FROM the email link never has to carry it.
    bootstrap = client.get("/graphql/csrf")
    assert bootstrap.status_code == 200
    assert bootstrap.json() == {"ready": True}
    token = bootstrap.cookies[settings.CSRF_COOKIE_NAME].value
    assert token
    # A shared cache must never hand one visitor another visitor's token.
    assert "no-store" in bootstrap["Cache-Control"]

    # 3. The same POST, with the header `graphql.ts` already sends. The cookie rides along
    #    because the test client keeps the jar, exactly as a browser does.
    accepted = post_mutation(HTTP_X_CSRFTOKEN=token)
    assert accepted.status_code == 200
    assert accepted.json()["data"]["resendVerificationEmail"]["accepted"] is True

    # 4. The control is still real: a forged cross-origin POST stays refused.
    forged = post_mutation(HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://evil.example")
    assert forged.status_code == 403


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
