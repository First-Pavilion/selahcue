"""Own-account wire, principal and projection contracts; SQLite is not lock evidence."""
import base64
import importlib
import json
from dataclasses import replace
from datetime import timedelta
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError, connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from selahcue_api.apps.accounts import services as accounts
from selahcue_api.apps.accounts.models import CustomerSession, CustomerUser
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan
from selahcue_api.apps.devices.models import Device, DeviceToken
from selahcue_api.apps.license_keys.models import AppLicenseKey, FreeLicenseLifecycle
from selahcue_api.apps.usage.models import UsageWeek
from selahcue_api.graphql.context import ACCOUNT_SESSION_COOKIE, ActorContext, ActorKind
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from test_effective_org_plan import NOW, church, device, licence, staff_grant

pytestmark = pytest.mark.django_db
QUERY = '''query AccountOverview($first: Int! = 20, $after: String) {
  accountOverview(first: $first, after: $after) {
    orgName displayName email role canDeactivateDevices
    license { status startsAt expiresAt validNow renewal deviceLimit activeDeviceCount }
    allowance { planDisplayName
      stt { limit settled held carriedDebt remaining asOf resetsAt status }
      notes { limit settled held carriedDebt remaining asOf resetsAt status }
    }
    devices { nodes { publicId displayName platform appVersion createdAt status } nextCursor }
  }
}'''
MUTATION = '''mutation DeactivateOwnDevice($devicePublicId: String!, $requestId: String!) {
  deactivateOwnDevice(devicePublicId: $devicePublicId, requestId: $requestId) { alreadyInactive }
}'''


def overview_module():
    return importlib.import_module('selahcue_api.apps.accounts.account_overview')


def deactivate(actor, public_id, request_id='account-deactivate-0001'):
    return importlib.import_module('selahcue_api.apps.devices.deactivation').deactivate_own_device(
        actor, public_id, request_id,
    )


def principal(org=None, *, role='ADMIN', verified=True):
    org = org or church()
    org.status = 'ACTIVE'
    org.save(update_fields=['status'])
    nonce = uuid4().hex
    user = CustomerUser.objects.create(
        customer=org, email=f'{nonce}@example.test', email_fingerprint=nonce,
        password_hash='unused', status='ACTIVE', role=role, display_name='',
        email_verified_at=NOW if verified else None,
        created_by_actor_id='fixture', idempotency_key=nonce,
    )
    return user, ActorContext(ActorKind.CUSTOMER, str(user.pk), str(org.pk), role=role)


def browser(user, settings):
    settings.SELAHCUE_TRUST_ACTOR_HEADERS = False
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    raw = f'synthetic-session-{uuid4().hex}'
    CustomerSession.objects.create(
        customer_user=user, token_prefix='synthetic', token_suffix='fixture',
        masked_token='synthetic...fixture', token_hash=make_password(raw),
        token_fingerprint=accounts._fingerprint(raw), issued_at=timezone.now()-timedelta(minutes=1),
        expires_at=timezone.now()+timedelta(days=1),
    )
    client = Client(enforce_csrf_checks=True)
    client.cookies[ACCOUNT_SESSION_COOKIE] = raw
    csrf = client.get('/graphql/csrf')['X-CSRFToken']
    return client, csrf


def post(client, csrf, query=QUERY, variables=None):
    return client.post('/graphql/account', data=json.dumps({
        'query': query, 'variables': variables or {},
    }), content_type='application/json', HTTP_X_CSRFTOKEN=csrf)


def assert_code(call, code):
    with pytest.raises(SafeAPIError) as caught:
        call()
    assert caught.value.code == code


def token(install, *, expired=False):
    return DeviceToken.objects.create(
        device=install, token_prefix='synthetic', token_suffix='fixture',
        masked_token='synthetic...fixture', token_hash='unused', token_fingerprint=uuid4().hex,
        issued_at=NOW-timedelta(days=2),
        expires_at=NOW-timedelta(days=1) if expired else NOW+timedelta(days=20),
    )


def test_http_populated_admin_uses_real_session_and_no_store(settings, monkeypatch):
    user, _ = principal()
    key = licence(user.customer)
    install = device(key)
    client, csrf = browser(user, settings)
    monkeypatch.setattr(timezone, 'now', lambda: NOW)
    # Session remains valid at the deterministic projection instant.
    CustomerSession.objects.update(issued_at=NOW-timedelta(days=1), expires_at=NOW+timedelta(days=1))
    response = post(client, csrf)
    assert 'errors' not in response.json(), response.content
    data = response.json()['data']['accountOverview']
    assert data['role'] == 'ADMIN' and data['canDeactivateDevices'] is True
    assert data['displayName'] == '' and data['email'] == user.email
    assert data['license']['activeDeviceCount'] == '1'
    assert data['devices']['nodes'][0]['publicId'] == install.device_public_id
    assert data['allowance']['stt']['status'] == 'NOT_INITIALIZED'
    assert data['allowance']['stt']['limit'] == '1200'
    assert 'no-store' in response['Cache-Control']


def test_parser_errors_are_no_store_before_context(settings):
    client = Client(enforce_csrf_checks=True)
    csrf = client.get('/graphql/csrf')['X-CSRFToken']
    response = client.post('/graphql/account', data='{invalid', content_type='application/json',
                           HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 400
    assert response.json()['errors'][0]['extensions']['code'] == 'VALIDATION_FAILED'
    assert 'no-store' in response.get('Cache-Control', '')


@pytest.mark.parametrize('first', [True, False, 0, 101, 1.5, '20', None])
def test_invalid_direct_page_size_is_refused_before_queries(first):
    with CaptureQueriesContext(connection) as queries:
        assert_code(lambda: overview_module().account_overview(None, NOW, None, first),
                    ErrorCode.VALIDATION_FAILED)
    assert len(queries) == 0


@pytest.mark.parametrize('value', ['', '0', '01', '-1', '+1', '１', '1.0', ' 1', '1\n',
                                   str(2**63), 1, None, '9'*5000])
@pytest.mark.parametrize('field,code', [('actor_id', ErrorCode.UNAUTHENTICATED),
                                      ('org_id', ErrorCode.NOT_FOUND)])
def test_canonical_principal_ids_are_bounded_before_queries(value, field, code):
    actor = replace(ActorContext(ActorKind.CUSTOMER, '1', '1'), **{field: value})
    with CaptureQueriesContext(connection) as queries:
        assert_code(lambda: overview_module().account_overview(actor, NOW, None), code)
    assert not queries


@pytest.mark.parametrize('actor,code', [(None, ErrorCode.UNAUTHENTICATED),
    (SimpleNamespace(kind=ActorKind.CUSTOMER, actor_id='1', org_id='1'), ErrorCode.UNAUTHENTICATED),
    (ActorContext(ActorKind.STAFF, '1', '1'), ErrorCode.PERMISSION_DENIED)])
def test_typed_customer_principal_required(actor, code):
    assert_code(lambda: overview_module().account_overview(actor, NOW, None), code)


def test_persisted_member_and_exact_org_are_authoritative():
    user, actor = principal(role='MEMBER')
    service = overview_module().account_overview
    result = service(replace(actor, role='ADMIN'), NOW, None)
    assert result.role == 'MEMBER' and result.can_deactivate_devices is False
    assert result.license is None and result.devices.nodes == ()
    assert_code(lambda: service(replace(actor, org_id=str(church().pk)), NOW, None),
                ErrorCode.UNAUTHENTICATED)
    user.status = 'DISABLED'
    user.save(update_fields=['status'])
    assert_code(lambda: service(actor, NOW, None), ErrorCode.UNAUTHENTICATED)


def test_selected_license_tie_breaker_and_managed_recovery(settings, monkeypatch):
    from selahcue_api.apps.catalogue.org_plans import effective_plan
    monkeypatch.setattr(timezone, 'now', lambda: NOW)
    user, actor = principal()
    first = licence(user.customer, 'CORE')
    second = licence(user.customer, 'PRO')
    # Equal expiry must not let an overview-only lower-PK selection go unnoticed.
    first.status = 'ISSUED'
    first.save(update_fields=['status'])
    second.status, second.device_limit = 'EXPIRING', 5
    second.starts_at = NOW - timedelta(days=2)
    second.save(update_fields=['status', 'device_limit', 'starts_at'])
    device(first)
    device(second)
    device(second)
    assert first.pk < second.pk and first.expires_at == second.expires_at
    service = overview_module().account_overview
    result = service(actor, NOW, None)
    pro = Plan.objects.get(code='PRO')
    assert effective_plan(user.customer, NOW).plan_id == pro.pk
    assert result.allowance.plan_display_name == pro.display_name
    assert (result.license.status, result.license.starts_at, result.license.expires_at,
            result.license.device_limit, result.license.active_device_count) == (
        'EXPIRING', NOW - timedelta(days=2), second.expires_at, 5, 2,
    )
    assert result.license.renewal == 'NOT_MANAGED'
    # Enter the actual cookie/CSRF account-session activation path at the same instant.
    client, csrf = browser(user, settings)
    activated = post(client, csrf, '''mutation($input: ActivateDeviceInput!) {
      activateDeviceWithSession(input: $input) { created devicePublicId }
    }''', {'input': {
        'idempotencyKey': 'equal-expiry-activation-001', 'deviceFingerprint': 'equal-expiry-install',
        'platform': 'macos',
    }})
    assert 'errors' not in activated.json(), activated.content
    activation = activated.json()['data']['activateDeviceWithSession']
    assert activation['created'] is True
    created = Device.objects.get(device_public_id=activation['devicePublicId'])
    assert created.license_key_id == second.pk
    assert Device.objects.filter(license_key=first).count() == 1
    AppLicenseKey.objects.filter(pk__in=[first.pk, second.pk]).update(status='EXPIRED', expires_at=NOW)
    marker = FreeLicenseLifecycle.objects.create(customer=user.customer, license_key=first, policy_version=1)
    LicensePlanAssignment.objects.filter(license_key=first).update(plan=Plan.objects.get(code='FREE'))
    result = service(actor, NOW, None)
    assert result.license.status == 'EXPIRED' and not result.license.valid_now
    assert result.license.renewal == 'AUTOMATIC'
    marker.renewal_enabled = False
    marker.save(update_fields=['renewal_enabled'])
    assert service(actor, NOW, None).license.renewal == 'UNAVAILABLE'


def test_pagination_exact_legacy_text_and_anchor_revocation_constant_queries():
    user, actor = principal()
    key = licence(user.customer)
    ids = [' a ', 'b', 'c', 'd']
    for public_id in ids:
        install = device(key)
        Device.objects.filter(pk=install.pk).update(device_public_id=public_id)
    service = overview_module().account_overview
    with CaptureQueriesContext(connection) as small:
        first = service(actor, NOW, None, 1)
    with CaptureQueriesContext(connection) as large:
        all_rows = service(actor, NOW, None, 100)
    assert len(small) == len(large)
    assert [row.public_id for row in all_rows.devices.nodes] == ids
    assert first.devices.next_cursor == base64.urlsafe_b64encode(b'\x01 a ').decode().rstrip('=')
    Device.objects.filter(device_public_id=' a ').update(status='REVOKED')
    following = service(actor, NOW, first.devices.next_cursor, 2)
    assert [row.public_id for row in following.devices.nodes] == ['b', 'c']
    assert all_rows.devices.next_cursor is None
    page_queries = [q['sql'] for q in small if 'selahcue_devices_device' in q['sql'] and 'ORDER BY' in q['sql']]
    assert len(page_queries) == 1 and 'LIMIT 2' in page_queries[0]


@pytest.mark.parametrize('cursor', ['', 'A', 'AmE', 'AWE=', 'AWE\n', '***', 'A'*344,
    base64.urlsafe_b64encode(b'\x01\x00').decode().rstrip('='),
    base64.urlsafe_b64encode(b'\x01\xff').decode().rstrip('='), 'AWF'])
def test_malformed_cursor_is_not_authority(cursor):
    assert_code(lambda: overview_module().account_overview(None, NOW, cursor), ErrorCode.VALIDATION_FAILED)


def test_unavailable_allowance_and_unexpected_fault_are_distinct(monkeypatch):
    user, actor = principal()
    mod = overview_module()
    monkeypatch.setattr(mod, 'effective_plan', lambda *_: (_ for _ in ()).throw(LookupError()))
    assert mod.account_overview(actor, NOW, None).allowance is None
    monkeypatch.setattr(mod, 'effective_plan', lambda *_: (_ for _ in ()).throw(DatabaseError('SECRET SQL')))
    assert_code(lambda: mod.account_overview(actor, NOW, None), ErrorCode.INTERNAL)


def test_deactivation_revokes_all_tokens_and_repeat_never_reaudits():
    user, actor = principal()
    key = licence(user.customer)
    install = device(key)
    tokens = [token(install), token(install, expired=True)]
    untouched = token(device(key))
    assert deactivate(actor, install.device_public_id).already_inactive is False
    assert deactivate(actor, install.device_public_id).already_inactive is True
    assert deactivate(actor, install.device_public_id, 'different-correlation').already_inactive is True
    install.refresh_from_db()
    assert install.status == 'REVOKED'
    assert list(DeviceToken.objects.filter(pk__in=[t.pk for t in tokens]).values_list('status', flat=True)) == ['REVOKED']*2
    untouched.refresh_from_db()
    assert untouched.status == 'ACTIVE'
    events = AuditEvent.objects.filter(action='device.deactivated')
    assert events.count() == 1 and events.get().actor_kind == 'service'
    assert events.get().source_surface == 'account_graphql'


def test_deactivation_rolls_back_on_audit_failure(monkeypatch):
    user, actor = principal()
    install = device(licence(user.customer))
    issued = token(install)
    mod = importlib.import_module('selahcue_api.apps.devices.deactivation')
    monkeypatch.setattr(mod, 'record_audit_event', lambda *a, **k: (_ for _ in ()).throw(DatabaseError('secret sql')))
    assert_code(lambda: deactivate(actor, install.device_public_id), ErrorCode.INTERNAL)
    install.refresh_from_db()
    issued.refresh_from_db()
    assert install.status == issued.status == 'ACTIVE'
    assert not AuditEvent.objects.filter(action='device.deactivated').exists()


@pytest.mark.parametrize('change', ['role', 'email_verified_at'])
def test_mutation_rechecks_persisted_authority_before_target(change):
    user, actor = principal()
    setattr(user, change, 'MEMBER' if change == 'role' else None)
    user.save(update_fields=[change])
    assert_code(lambda: deactivate(actor, 'missing-valid-id'), ErrorCode.PERMISSION_DENIED)


def test_blocked_org_license_deactivation_and_correlation_reuse():
    user, actor = principal()
    key = licence(user.customer)
    first, second = device(key), device(key)
    user.customer.status = 'SUSPENDED'
    user.customer.save(update_fields=['status'])
    key.status = 'REVOKED'
    key.save(update_fields=['status'])
    assert not deactivate(actor, first.device_public_id).already_inactive
    assert not deactivate(actor, second.device_public_id).already_inactive
    assert_code(lambda: deactivate(actor, device(licence(church())).device_public_id), ErrorCode.NOT_FOUND)


@pytest.mark.parametrize('public_id', ['', ' ', 'x'*65, 'x\x00', '\ud800', 123])
def test_invalid_device_ids(public_id):
    assert_code(lambda: deactivate(None, public_id), ErrorCode.VALIDATION_FAILED)


def test_duplicate_mutation_alias_rejection_preserves_first_commit(settings, monkeypatch):
    from selahcue_api.graphql import account_schema
    calls = []
    real = account_schema.deactivate_own_device
    def counted(*args):
        calls.append(1)
        return real(*args)
    monkeypatch.setattr(account_schema, 'deactivate_own_device', counted)
    user, _ = principal()
    install = device(licence(user.customer))
    client, csrf = browser(user, settings)
    args = f'devicePublicId: "{install.device_public_id}", requestId: "alias-correlation-001"'
    response = post(client, csrf, f'mutation {{ a: deactivateOwnDevice({args}) {{ alreadyInactive }} ...Again }} fragment Again on AccountMutation {{ b: deactivateOwnDevice({args}) {{ alreadyInactive }} }}')
    assert response.json()['errors'][0]['extensions']['code'] == 'VALIDATION_FAILED'
    install.refresh_from_db()
    assert install.status == 'REVOKED'
    assert AuditEvent.objects.filter(action='device.deactivated').count() == 1
    assert len(calls) == 1


def test_duplicate_overview_is_claimed_before_actor_lookup(settings, monkeypatch):
    from selahcue_api.graphql import account_schema
    user, _ = principal()
    client, csrf = browser(user, settings)
    calls = []
    real = account_schema.actor_from_info
    service_calls = []
    service = account_schema.account_overview
    def counted_service(*args):
        service_calls.append(1)
        return service(*args)
    monkeypatch.setattr(account_schema, 'account_overview', counted_service)
    def counted(info):
        calls.append(1)
        return real(info)
    monkeypatch.setattr(account_schema, 'actor_from_info', counted)
    response = post(client, csrf, 'query { a: accountOverview { email } ...Again } fragment Again on AccountQuery { b: accountOverview { email } }')
    assert response.json()['errors'][0]['extensions']['code'] == 'VALIDATION_FAILED'
    assert len(calls) == len(service_calls) == 1


def test_safe_field_fault_logs_no_query_or_exception(settings, monkeypatch, caplog):
    user, _ = principal()
    client, csrf = browser(user, settings)
    mod = overview_module()
    monkeypatch.setattr(mod, 'effective_plan', lambda *_: (_ for _ in ()).throw(DatabaseError('PRIVATE DATABASE SQL')))
    response = post(client, csrf, QUERY.replace('query AccountOverview', 'query PRIVATE_BODY'))
    assert response.json()['errors'][0]['extensions']['code'] == 'INTERNAL'
    assert 'PRIVATE' not in response.content.decode() and 'PRIVATE' not in caplog.text
    assert 'accountOverview' in caplog.text


@pytest.mark.parametrize('state', ['absent', 'expired', 'revoked', 'epoch'])
def test_real_session_failures_are_safe_no_store(settings, state):
    user, _ = principal()
    client, csrf = browser(user, settings)
    if state == 'absent':
        del client.cookies[ACCOUNT_SESSION_COOKIE]
    elif state == 'expired':
        CustomerSession.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
    elif state == 'revoked':
        CustomerSession.objects.update(status='REVOKED')
    else:
        user.password_changed_at = timezone.now()
        user.save(update_fields=['password_changed_at'])
    response = post(client, csrf)
    assert response.json()['errors'][0]['extensions']['code'] == 'UNAUTHENTICATED'
    assert 'no-store' in response['Cache-Control']


def test_cookie_mutation_still_requires_csrf(settings):
    user, _ = principal()
    install = device(licence(user.customer))
    client, _ = browser(user, settings)
    response = post(client, '', MUTATION, {'devicePublicId': install.device_public_id, 'requestId': 'csrf-correlation-001'})
    assert response.status_code == 403
    install.refresh_from_db()
    assert install.status == 'ACTIVE'


def test_corrupt_stored_device_id_is_internal_not_client_validation():
    user, actor = principal()
    install = device(licence(user.customer))
    Device.objects.filter(pk=install.pk).update(device_public_id=' ')
    assert_code(lambda: overview_module().account_overview(actor, NOW, None), ErrorCode.INTERNAL)


@pytest.mark.parametrize('value', [-1, 2**63, True, '2', 1.5])
def test_invalid_ledger_counter_fails_closed(value, monkeypatch):
    user, actor = principal()
    mod = overview_module()
    snapshots = mod.remaining(user.customer, NOW)
    monkeypatch.setattr(mod, 'remaining', lambda *_: (replace(snapshots[0], held=value), snapshots[1]))
    assert_code(lambda: mod.account_overview(actor, NOW, None), ErrorCode.INTERNAL)


def test_lossless_max_counter_projection(monkeypatch):
    user, actor = principal()
    mod = overview_module()
    snapshots = mod.remaining(user.customer, NOW)
    calls = []
    def snapshot(*args):
        calls.append(args)
        return replace(snapshots[0], settled=2**63-1), snapshots[1]
    monkeypatch.setattr(mod, 'remaining', snapshot)
    result = mod.account_overview(actor, NOW, None)
    assert len(calls) == 1 and result.allowance.stt.settled == 2**63-1


@pytest.mark.parametrize('change,value', [
    ('status', 'SUSPENDED'), ('status', 'REVOKED'), ('status', 'CONVERTED'), ('status', 'ARCHIVED'),
    ('starts_at', NOW+timedelta(seconds=1)), ('policy_version', 2), ('renewal_enabled', False),
    ('assignment', None), ('org_status', 'SUSPENDED'),
])
def test_marked_ineligible_license_is_unavailable(change, value):
    user, actor = principal()
    key = licence(user.customer)
    marker = FreeLicenseLifecycle.objects.create(customer=user.customer, license_key=key, policy_version=1)
    if change == 'assignment':
        LicensePlanAssignment.objects.filter(license_key=key).delete()
    elif change == 'org_status':
        user.customer.status = value
        user.customer.save(update_fields=['status'])
    else:
        target = marker if change in {'policy_version', 'renewal_enabled'} else key
        setattr(target, change, value)
        if change == 'status' and value == 'SUSPENDED':
            target.prior_status = 'ACTIVATED'
            target.save(update_fields=[change, 'prior_status'])
        else:
            target.save(update_fields=[change])
    assert overview_module().account_overview(actor, NOW, None).license.renewal == 'UNAVAILABLE'


def test_staff_plan_and_selected_license_are_independent():
    user, actor = principal()
    key = licence(user.customer)
    staff_grant(user.customer, 'PRO', NOW, NOW+timedelta(days=1))
    result = overview_module().account_overview(actor, NOW, None)
    assert result.allowance.plan_display_name == Plan.objects.get(code='PRO').display_name
    assert result.license.device_limit == key.device_limit
    assert result.allowance.stt.limit == 4800


def test_default_page_size_and_count_are_not_limited_by_page_or_device_limit():
    user, actor = principal()
    key = licence(user.customer)
    for _ in range(23):
        device(key)
    result = overview_module().account_overview(actor, NOW, None)
    assert len(result.devices.nodes) == 20 and result.devices.next_cursor
    assert result.license.active_device_count == 23
    assert result.license.device_limit == key.device_limit < 23


@pytest.mark.parametrize('request_id', [None, 12, '', 'short', 'x'*129, 'space not permitted'])
def test_deactivation_correlation_validation(request_id):
    assert_code(lambda: deactivate(None, 'valid-device', request_id), ErrorCode.VALIDATION_FAILED)


def test_request_guard_stays_claimed_after_failed_first_call():
    from selahcue_api.graphql.account_schema import AccountQuery
    from django.http import HttpRequest
    info = SimpleNamespace(context=SimpleNamespace(request=HttpRequest()))
    query = AccountQuery()
    assert_code(lambda: query.account_overview(info), ErrorCode.UNAUTHENTICATED)
    assert_code(lambda: query.account_overview(info), ErrorCode.VALIDATION_FAILED)


# These are the actual Task6 synthetic observed-scan publication builders. No providers run.
from provider_helpers import DEEPGRAM, cold_provider_cache, provider_mounts  # noqa: E402, F401
from test_provider_observations import NOW as OBSERVED_AT, begin_scan, clock, usage_runtime  # noqa: E402, F401
from test_provider_reservation_binding import active_mapping  # noqa: E402
from test_usage_reconciliation import MONDAY, observed  # noqa: E402
from selahcue_api.apps.usage.contracts import UTCInterval  # noqa: E402
from selahcue_api.apps.usage.reconciliation import reconcile_org  # noqa: E402


def publish_current(org, usage_runtime, clock):
    mapping = active_mapping(org)
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, OBSERVED_AT), org=org, mapping=mapping.mapping_id)
    observed(scan, [], OBSERVED_AT)
    reconcile_org(org.pk, OBSERVED_AT, clock=clock)
    return mapping


def test_actual_task6_current_and_stale_publication(usage_runtime, clock):
    user, actor = principal()
    mod = overview_module()
    publish_current(user.customer, usage_runtime, clock)
    current = mod.account_overview(actor, OBSERVED_AT, None)
    assert current.allowance.stt.status == 'current_observed'
    stale = mod.account_overview(actor, OBSERVED_AT+timedelta(seconds=300), None)
    assert stale.allowance.stt.status == 'stale'
    # Notes always use their ledger status, independently of STT readiness.
    assert current.allowance.notes.status == mod.remaining(user.customer, OBSERVED_AT)[1].status


def test_real_reader_without_publication_and_absent_mapping_with_week(usage_runtime, clock):
    from selahcue_api.apps.usage.services import _open_week
    from selahcue_api.apps.catalogue.org_plans import effective_plan
    from django.db import transaction
    user, actor = principal()
    with transaction.atomic():
        _open_week(user.customer, effective_plan(user.customer, NOW), NOW)
    assert overview_module().account_overview(actor, NOW, None).allowance.stt.status == 'not_initialized'
    active_mapping(user.customer)
    assert overview_module().account_overview(actor, NOW, None).allowance.stt.status == 'not_initialized'


def test_wire_schema_names_nullability_and_default():
    from graphql import Undefined
    from selahcue_api.graphql.account_schema import schema
    # Literal expectations from the accepted v4 contract, independent of wire fixtures.
    expected_objects = {
        'AccountOverview': {
            'orgName': 'String!', 'displayName': 'String!', 'email': 'String!',
            'role': 'AccountRole!', 'canDeactivateDevices': 'Boolean!',
            'license': 'AccountLicense', 'allowance': 'AccountAllowance',
            'devices': 'AccountDevicePage!',
        },
        'AccountLicense': {
            'status': 'AccountLicenseStatus!', 'startsAt': 'String!', 'expiresAt': 'String!',
            'validNow': 'Boolean!', 'renewal': 'AccountRenewal!', 'deviceLimit': 'Int!',
            'activeDeviceCount': 'String!',
        },
        'AccountAllowance': {
            'planDisplayName': 'String!', 'planEndsAt': 'String', 'stt': 'AccountQuota!', 'notes': 'AccountQuota!',
        },
        'AccountQuota': {
            'limit': 'String!', 'settled': 'String!', 'held': 'String!',
            'carriedDebt': 'String!', 'remaining': 'String!', 'asOf': 'String!',
            'resetsAt': 'String!', 'status': 'AccountQuotaStatus!',
        },
        'AccountDevicePage': {'nodes': '[AccountDevice!]!', 'nextCursor': 'String'},
        'AccountDevice': {
            'publicId': 'String!', 'displayName': 'String!', 'platform': 'String!',
            'appVersion': 'String!', 'createdAt': 'String!', 'status': 'AccountDeviceStatus!',
        },
        'DeactivationResult': {'alreadyInactive': 'Boolean!'},
    }
    for name, expected in expected_objects.items():
        fields = schema._schema.get_type(name).fields
        assert {key: str(field.type) for key, field in fields.items()} == expected, name
        assert all(not field.args for field in fields.values()), name
    expected_enums = {
        'AccountRole': {'ADMIN', 'MEMBER'},
        'AccountLicenseStatus': {
            'ISSUED', 'ACTIVATED', 'EXPIRING', 'EXPIRED', 'SUSPENDED', 'REVOKED',
            'CONVERTED', 'ARCHIVED',
        },
        'AccountRenewal': {'AUTOMATIC', 'UNAVAILABLE', 'NOT_MANAGED'},
        'AccountQuotaStatus': {'CURRENT_OBSERVED', 'STALE', 'NOT_INITIALIZED'},
        'AccountDeviceStatus': {'ACTIVE', 'REVOKED'},
    }
    for name, expected in expected_enums.items():
        assert set(schema._schema.get_type(name).values) == expected, name
    overview = schema._schema.query_type.fields['accountOverview']
    assert str(overview.type) == 'AccountOverview!'
    assert {name: (str(arg.type), arg.default_value) for name, arg in overview.args.items()} == {
        'first': ('Int!', 20), 'after': ('String', None),
    }
    deactivation = schema._schema.mutation_type.fields['deactivateOwnDevice']
    assert str(deactivation.type) == 'DeactivationResult!'
    assert {name: (str(arg.type), arg.default_value) for name, arg in deactivation.args.items()} == {
        'devicePublicId': ('String!', Undefined), 'requestId': ('String!', Undefined),
    }


FIXTURE_PATH = Path(__file__).resolve().parents[3] / 'docs/contracts/account-overview-v1.json'


@pytest.mark.parametrize('name', [
    'null_license_allowance', 'administrator_current', 'member', 'large_counter',
    'page_first', 'page_next', 'first_deactivation', 'repeated_deactivation', 'foreign_target',
])
def test_shared_producer_fixture_against_actual_http(name, settings, monkeypatch, usage_runtime, clock):
    """Exact consumer bytes come from actual HTTP/session/schema execution of synthetic state."""
    from django.db import transaction
    from selahcue_api.apps.usage.services import _open_week
    from selahcue_api.apps.catalogue.org_plans import effective_plan
    contract = json.loads(FIXTURE_PATH.read_text())
    case = next(case for case in contract['cases'] if case['name'] == name)
    user, actor = principal(role='MEMBER' if name == 'member' else 'ADMIN')
    user.customer.name = 'Grace Chapel'
    user.customer.save(update_fields=['name'])
    user.display_name, user.email = 'Ada', 'admin@grace.example.test'
    user.save(update_fields=['display_name', 'email'])
    if name == 'null_license_allowance':
        Plan.objects.filter(is_fallback=True).update(is_fallback=False)
    else:
        key = licence(user.customer)
        for suffix in ('a', 'b'):
            install = device(key)
            Device.objects.filter(pk=install.pk).update(
                device_public_id='account-device-'+suffix,
                display_name='Main booth' if suffix == 'a' else '', created_at=OBSERVED_AT,
            )
    if name == 'administrator_current':
        publish_current(user.customer, usage_runtime, clock)
    if name == 'large_counter':
        with transaction.atomic():
            week = _open_week(user.customer, effective_plan(user.customer, OBSERVED_AT), OBSERVED_AT)
        UsageWeek.objects.filter(pk=week.pk).update(notes_settled=2**63-1)
    if name == 'repeated_deactivation':
        deactivate(actor, 'account-device-a', case['request']['variables']['requestId'])
    if name == 'foreign_target':
        foreign = device(licence(church()))
        Device.objects.filter(pk=foreign.pk).update(device_public_id='foreign-device')
    client, csrf = browser(user, settings)
    response = client.post('/graphql/account', data=json.dumps(case['request']),
                           content_type='application/json', HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200
    assert response.json() == case['response'], json.dumps(response.json(), sort_keys=True)
    assert 'no-store' in response['Cache-Control']
    assert case['request']['query'] == contract['operations'][
        'deactivateOwnDevice' if 'deactivation' in name or name == 'foreign_target' else 'accountOverview'
    ]['query']


def test_account_no_store_preserves_other_directives_without_changing_admin(monkeypatch):
    from django.http import HttpRequest, HttpResponse
    from selahcue_api.graphql.views import AccountGraphQLView, AdminGraphQLView, SafeGraphQLView
    def response(*args, **kwargs):
        reply = HttpResponse('{}', content_type='application/json')
        reply['Cache-Control'] = 'private, max-age=0'
        return reply
    monkeypatch.setattr(SafeGraphQLView, 'dispatch', response)
    account = AccountGraphQLView(schema=None).dispatch(HttpRequest())
    admin = AdminGraphQLView(schema=None).dispatch(HttpRequest())
    assert set(account['Cache-Control'].split(', ')) == {'private', 'max-age=0', 'no-store'}
    assert admin['Cache-Control'] == 'private, max-age=0'


def test_mutation_fault_is_safe_after_http_transaction_rollback(settings, monkeypatch, caplog):
    user, _ = principal()
    install = device(licence(user.customer))
    issued = token(install)
    client, csrf = browser(user, settings)
    mod = importlib.import_module('selahcue_api.apps.devices.deactivation')
    def fail(*args, **kwargs):
        raise DatabaseError('PRIVATE SQL and bearer material')
    monkeypatch.setattr(mod, 'record_audit_event', fail)
    response = post(client, csrf, MUTATION, {
        'devicePublicId': install.device_public_id, 'requestId': 'http-fault-correlation',
    })
    assert response.json()['errors'][0]['extensions']['code'] == 'INTERNAL'
    assert 'no-store' in response['Cache-Control']
    assert 'PRIVATE' not in response.content.decode() and 'PRIVATE' not in caplog.text
    assert 'deactivateOwnDevice' in caplog.text
    install.refresh_from_db()
    issued.refresh_from_db()
    assert install.status == issued.status == 'ACTIVE'


@pytest.mark.parametrize('seconds,valid', [(-1, True), (0, False), (1, False)])
def test_license_half_open_window_and_renewal_ignore_reader_wall_time(seconds, valid):
    user, actor = principal()
    key = licence(user.customer)
    FreeLicenseLifecycle.objects.create(customer=user.customer, license_key=key, policy_version=1)
    user.customer.status = 'SUSPENDED'
    user.customer.save(update_fields=['status'])
    result = overview_module().account_overview(actor, key.expires_at+timedelta(seconds=seconds), None)
    assert result.license.valid_now is valid
    assert result.license.renewal == 'UNAVAILABLE'


def test_missing_org_and_missing_active_user_have_distinct_boundaries():
    user, actor = principal()
    missing = str(2**63-1)
    assert_code(lambda: overview_module().account_overview(replace(actor, org_id=missing), NOW, None), ErrorCode.NOT_FOUND)
    assert_code(lambda: overview_module().account_overview(replace(actor, actor_id=missing), NOW, None), ErrorCode.UNAUTHENTICATED)


def test_explicitly_unavailable_snapshot_is_null_allowance(monkeypatch):
    user, actor = principal()
    mod = overview_module()
    monkeypatch.setattr(mod, 'remaining', lambda *_: None)
    assert mod.account_overview(actor, NOW, None).allowance is None


def test_request_flags_do_not_survive_to_a_retry_http_request(settings):
    user, _ = principal()
    install = device(licence(user.customer))
    client, csrf = browser(user, settings)
    variables = {'devicePublicId': install.device_public_id, 'requestId': 'retry-correlation-001'}
    first, second = post(client, csrf, MUTATION, variables), post(client, csrf, MUTATION, variables)
    assert first.json()['data']['deactivateOwnDevice']['alreadyInactive'] is False
    assert second.json()['data']['deactivateOwnDevice']['alreadyInactive'] is True
    assert AuditEvent.objects.filter(action='device.deactivated').count() == 1


@pytest.mark.parametrize('variables', [
    {'first': 0}, {'first': 101}, {'after': ''}, {'after': 'AWE='}, {'after': 'A'*344},
])
def test_http_invalid_pagination_precedes_actor_and_session_queries(settings, monkeypatch, variables):
    from selahcue_api.graphql import account_schema
    user, _ = principal()
    client, csrf = browser(user, settings)
    actor_calls, session_calls = [], []
    real_actor, real_session = account_schema.actor_from_info, accounts.actor_from_session_token
    def actor_spy(info):
        actor_calls.append(1)
        return real_actor(info)
    def session_spy(*args, **kwargs):
        session_calls.append(1)
        return real_session(*args, **kwargs)
    monkeypatch.setattr(account_schema, 'actor_from_info', actor_spy)
    monkeypatch.setattr(accounts, 'actor_from_session_token', session_spy)
    with CaptureQueriesContext(connection) as queries:
        response = post(client, csrf, variables=variables)
    assert response.json() == {'data': None, 'errors': [{
        'message': 'The request is invalid.', 'extensions': {'code': 'VALIDATION_FAILED'},
    }]}
    assert 'no-store' in response['Cache-Control']
    assert actor_calls == session_calls == []
    assert len(queries) == 0
    # A later valid request on the same cookie still performs real authentication.
    valid = post(client, csrf, variables={'first': 1})
    assert 'errors' not in valid.json(), valid.content
    assert valid.json()['data']['accountOverview']['email'] == user.email
    assert actor_calls == session_calls == [1]


@pytest.mark.parametrize('state', [
    'uninitialized', 'ledger_week',
    pytest.param('published_current', marks=pytest.mark.skipif(
        connection.vendor != 'postgresql', reason='published read-only CTE uses the reviewed PostgreSQL SQL pin',
    )),
    pytest.param('published_stale', marks=pytest.mark.skipif(
        connection.vendor != 'postgresql', reason='published read-only CTE uses the reviewed PostgreSQL SQL pin',
    )),
])
def test_real_overview_snapshot_is_once_and_read_only(monkeypatch, request, state):
    from django.db import transaction
    from selahcue_api.apps.catalogue.org_plans import effective_plan
    from selahcue_api.apps.usage.services import _open_week
    from test_quota_read_only_sql import quota_read_only_query
    user, actor = principal()
    at = OBSERVED_AT
    if state == 'ledger_week':
        with transaction.atomic():
            _open_week(user.customer, effective_plan(user.customer, at), at)
    elif state.startswith('published_'):
        # Real Task6 publication writes are setup, outside the guarded account read.
        publish_current(user.customer, request.getfixturevalue('usage_runtime'), request.getfixturevalue('clock'))
        if state == 'published_stale':
            at += timedelta(seconds=300)
    weeks_before = list(UsageWeek.objects.filter(org=user.customer).values())
    assert bool(weeks_before) is (state != 'uninitialized')
    mod = overview_module()
    real_remaining = mod.remaining
    calls, rejection = [], []
    def counted_remaining(org, instant):
        calls.append((org.pk, instant))
        return real_remaining(org, instant)
    monkeypatch.setattr(mod, 'remaining', counted_remaining)
    # Reuse the reviewed SELECT / exact PostgreSQL readiness-CTE classifier;
    # no generic WITH allowance or implementation-generated SQL fingerprint.
    guard = partial(quota_read_only_query, rejection=rejection)
    with CaptureQueriesContext(connection) as queries, connection.execute_wrapper(guard):
        result = mod.account_overview(actor, at, None)
    assert not rejection, rejection[0]
    assert calls == [(user.customer_id, at)]
    assert len(queries) > 0
    assert any('selahcue_usage_usageweek' in query['sql'] for query in queries)
    assert not any(clause in query['sql'].upper() for query in queries for clause in (
        'FOR UPDATE', 'FOR NO KEY UPDATE', 'FOR SHARE', 'FOR KEY SHARE',
    ))
    assert list(UsageWeek.objects.filter(org=user.customer).values()) == weeks_before
    assert result.allowance.notes.status == ('not_initialized' if state == 'uninitialized' else 'stale')
    assert result.allowance.stt.status == {
        'uninitialized': 'not_initialized', 'ledger_week': 'not_initialized',
        'published_current': 'current_observed', 'published_stale': 'stale',
    }[state]


# --- beta end date and effective device limit (17tnw2bhkd2) ----------------
BETA_ON = {'SELAHCUE_BETA_PLAN_CODE': 'BETA', 'SELAHCUE_BETA_ENDS_AT': '2027-05-06T00:00:00+00:00'}


def _beta_org():
    from django.test import override_settings
    from selahcue_api.apps.catalogue.beta import ensure_beta_grant
    user, actor = principal()
    licence(user.customer, 'FREE', length=400)
    with override_settings(**BETA_ON):
        assert ensure_beta_grant(user.customer, at=NOW) is not None
    return actor


def test_overview_shows_beta_plan_and_end_date():
    actor = _beta_org()
    result = overview_module().account_overview(actor, NOW, None)
    assert result.allowance.plan_display_name == 'Beta'
    assert result.allowance.plan_ends_at.isoformat() == '2027-05-06T00:00:00+00:00'
    assert result.license.device_limit == 10
    assert result.allowance.stt.limit == 10800


def test_overview_after_beta_end_shows_free():
    actor = _beta_org()
    result = overview_module().account_overview(actor, NOW + timedelta(days=200), None)
    assert result.allowance.plan_display_name == 'Free'
    assert result.allowance.plan_ends_at is None
    assert result.license.device_limit == 1


def test_beta_end_and_limit_reach_the_wire(settings):
    from selahcue_api.graphql.account_schema import schema
    fields = schema._schema.get_type('AccountAllowance').fields
    assert str(fields['planEndsAt'].type) == 'String'
