"""Public read contract: exercise real rows/writers and HTTP, never admin mutations."""
import json
import urllib.request
from http.cookies import SimpleCookie
from selahcue_api.apps.audit.models import AuditEvent
from datetime import timedelta
from unittest.mock import patch

import pytest
import test_nginx_forwarded_proto as guard
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from selahcue_api.apps.catalogue.public_catalogue import PUBLIC_CACHE
from selahcue_api.apps.catalogue.models import CatalogueRevision, Plan, PlanGrant, PlanPrice
from selahcue_api.apps.catalogue.pricing import AppendPlanPriceData, append_plan_price
from selahcue_api.apps.catalogue.services import SetPlanGrantData, set_plan_grant
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

pytestmark = pytest.mark.django_db
URL = "/v1/catalogue/plans"
PLAN_KEYS = {"key", "name", "price_state", "offers", "cloud_transcript_minutes_per_week", "sermon_notes_per_week", "watermark"}
OFFER_KEYS = {"currency", "interval", "price_state", "amount_minor", "minor_unit_exponent"}


@pytest.fixture(autouse=True)
def clean_public_state():
    cache.clear()
    PUBLIC_CACHE.clear()
    yield
    cache.clear()
    PUBLIC_CACHE.clear()


def test_anonymous_seed_is_exact_public_unpriced_data():
    response = Client().get(URL)
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert response["X-Content-Type-Options"] == "nosniff"
    payload = response.json()
    assert set(payload) == {"plans"}
    plans = payload["plans"]
    assert [(p["key"], p["name"], p["cloud_transcript_minutes_per_week"], p["sermon_notes_per_week"], p["watermark"]) for p in plans] == [
        ("FREE", "Free", 20, 1, True), ("CORE", "Core", 50, 5, False), ("PRO", "Pro", 80, 10, False)]
    for plan in plans:
        assert set(plan) == PLAN_KEYS
        assert plan["offers"] == []
        assert plan["price_state"] == "unpriced"
    assert "Access-Control-Allow-Origin" not in response


def _price(*, currency="USD", interval="MONTH", amount=0, at=None, plan="CORE"):
    return PlanPrice.objects.create(plan=Plan.objects.get(code=plan), currency=currency,
        interval=interval, amount_minor=amount, effective_from=at or timezone.now()-timedelta(days=1),
        changed_by_actor_id="public-test-ops", reason="Public price contract test.")


def _core(response):
    assert response.status_code == 200
    return next(p for p in response.json()["plans"] if p["key"] == "CORE")


def test_all_current_pairs_distinguish_zero_null_and_large_amounts():
    now = timezone.now()
    _price(amount=0, at=now-timedelta(hours=2))
    _price(amount=None, at=now-timedelta(hours=1))
    _price(currency="JPY", amount=0)
    _price(currency="KWD", interval="YEAR", amount=9223372036854775807)
    _price(currency="EUR", at=now+timedelta(hours=1), amount=55)
    value = _core(Client().get(URL))
    assert value["price_state"] == "priced"
    assert value["offers"] == [
        {"currency":"JPY", "interval":"MONTH", "price_state":"priced", "amount_minor":"0", "minor_unit_exponent":0},
        {"currency":"KWD", "interval":"YEAR", "price_state":"priced", "amount_minor":"9223372036854775807", "minor_unit_exponent":3},
        {"currency":"USD", "interval":"MONTH", "price_state":"unpriced", "amount_minor":None, "minor_unit_exponent":2}]
    assert all(set(offer) == OFFER_KEYS for offer in value["offers"])


def test_explicit_null_current_offer_stays_unpriced():
    _price(amount=None)
    value = _core(Client().get(URL))
    assert value["price_state"] == "unpriced"
    assert value["offers"][0]["amount_minor"] is None


@pytest.mark.parametrize("method", ["post", "put", "delete", "head", "options"])
def test_view_level_non_get_refused_without_catalogue_queries(method):
    # Default Client bypasses CSRF checks; this specifically exercises the GET-only view.
    with CaptureQueriesContext(connection) as queries:
        response = getattr(Client(), method)(URL)
    assert response.status_code == 405
    assert response["Allow"] == "GET"
    assert not queries
    assert response["Cache-Control"] == "no-store"


def test_unknown_query_refused_without_catalogue_queries():
    with CaptureQueriesContext(connection) as queries:
        response = Client().get(URL, {"currency":"USD"})
    assert response.status_code == 400
    assert not queries


@pytest.mark.parametrize("mode", ["missing", "negative", "unlimited", "inactive", "wrongtype", "watermark"])
def test_incomplete_or_malformed_required_grants_are_unavailable(mode):
    grant = PlanGrant.objects.select_related("dimension").get(plan__code="CORE", dimension__key="sermon_notes_per_week")
    if mode == "missing":
        grant.delete()
    elif mode in {"negative", "unlimited"}:
        PlanGrant.objects.filter(pk=grant.pk).update(raw_value="-1" if mode == "negative" else "unlimited")
    elif mode in {"inactive", "wrongtype"}:
        dimension = grant.dimension
        if mode == "inactive":
            dimension.is_active = False
        else:
            dimension.value_type = "BOOLEAN"
        dimension.save()
    else:
        PlanGrant.objects.filter(plan__code="CORE", dimension__key="watermark").update(raw_value="not-a-boolean")
    response = Client().get(URL)
    assert response.status_code == 503
    assert response.json() == {"error":{"code":"catalogue_unavailable"}}
    assert response["Cache-Control"] == "no-store"


@override_settings(SELAHCUE_THROTTLE_PUBLIC_CATALOGUE=(2,60), SELAHCUE_TRUSTED_PROXY_COUNT=0)
def test_rate_limit_cannot_be_bypassed_by_spoofed_forwarded_header():
    client = Client(REMOTE_ADDR="198.51.100.20")
    assert client.get(URL, HTTP_X_FORWARDED_FOR="203.0.113.1").status_code == 200
    assert client.get(URL, HTTP_X_FORWARDED_FOR="203.0.113.2").status_code == 200
    response = client.get(URL, HTTP_X_FORWARDED_FOR="203.0.113.3")
    assert response.status_code == 429
    assert response.json() == {"error":{"code":"catalogue_rate_limited"}}
    assert 1 <= int(response["Retry-After"]) <= 60
    assert response["Cache-Control"] == "no-store"
    assert Client(REMOTE_ADDR="198.51.100.21").get(URL).status_code == 200


def test_limiter_outage_refuses_before_database_read():
    with patch("selahcue_api.apps.throttling.services.CacheStore.incr_with_expiry", side_effect=ConnectionError("private store details")):
        with CaptureQueriesContext(connection) as queries:
            response = Client().get(URL)
    assert response.status_code == 429
    assert response.json() == {"error":{"code":"catalogue_rate_limited"}}
    assert response["Retry-After"] == "60"
    assert not queries


def test_actual_grant_writer_changes_next_response_without_admin_e2e_claim():
    assert _core(Client().get(URL))["sermon_notes_per_week"] == 5
    actor = ActorContext(kind=ActorKind.STAFF, actor_id="public-test-ops",
        staff_permissions=frozenset({StaffPermission.GRANT_ENTITLEMENT}))
    set_plan_grant(actor, SetPlanGrantData(idempotency_key="public-grant-0001", plan_code="CORE",
        dimension_key="sermon_notes_per_week", raw_value="6", reason="Public writer invalidation test."))
    assert _core(Client().get(URL))["sermon_notes_per_week"] == 6


def test_actual_price_writer_changes_next_response_at_effective_boundary():
    now = timezone.now()
    assert _core(Client().get(URL))["offers"] == []
    actor = ActorContext(kind=ActorKind.STAFF, actor_id="public-pricing-ops",
        staff_permissions=frozenset({StaffPermission.MANAGE_PLAN_PRICING}))
    append_plan_price(actor, AppendPlanPriceData(plan_code="CORE", currency="USD", interval="MONTH",
        amount_minor=0, effective_from=now+timedelta(seconds=2), reason="Public writer invalidation test.", idempotency_key="public-price-0001"))
    with patch("selahcue_api.apps.catalogue.public_catalogue.timezone.now", return_value=now+timedelta(seconds=2)):
        value = _core(Client().get(URL))
    assert value["price_state"] == "priced"
    assert value["offers"][0]["amount_minor"] == "0"


def test_cold_queries_are_bounded_and_warm_read_checks_only_revision():
    for day in range(20):
        _price(amount=day, at=timezone.now()-timedelta(days=day+1))
    with CaptureQueriesContext(connection) as cold:
        first = Client().get(URL)
    assert _core(first)["offers"][0]["amount_minor"] == "0"
    assert len(cold) == 6
    with CaptureQueriesContext(connection) as warm:
        second = Client().get(URL)
    assert second.content == first.content
    assert len(warm) == 1
    assert len(first.content) < 1048576


def test_cached_projection_does_not_survive_database_outage():
    assert Client().get(URL).status_code == 200
    with patch("selahcue_api.apps.catalogue.public_catalogue._revision", side_effect=DatabaseError("private DB details")):
        response = Client().get(URL)
    assert response.status_code == 503
    assert response.json() == {"error":{"code":"catalogue_unavailable"}}


def test_cache_expires_at_scheduled_price_change_without_any_write():
    now = timezone.now()
    _price(amount=10, at=now-timedelta(days=1))
    _price(amount=25, at=now+timedelta(seconds=2))
    with patch("selahcue_api.apps.catalogue.public_catalogue.timezone.now", return_value=now):
        assert _core(Client().get(URL))["offers"][0]["amount_minor"] == "10"
    with patch("selahcue_api.apps.catalogue.public_catalogue.timezone.now", return_value=now+timedelta(seconds=2)):
        assert _core(Client().get(URL))["offers"][0]["amount_minor"] == "25"


def test_ttl_bounds_signal_bypassing_edit_and_clock_rollback_refuses_future_cache():
    now = timezone.now()
    with patch("selahcue_api.apps.catalogue.public_catalogue.time.monotonic", return_value=100):
        with patch("selahcue_api.apps.catalogue.public_catalogue.timezone.now", return_value=now):
            assert _core(Client().get(URL))["sermon_notes_per_week"] == 5
    PlanGrant.objects.filter(plan__code="CORE", dimension__key="sermon_notes_per_week").update(raw_value="8")
    with patch("selahcue_api.apps.catalogue.public_catalogue.time.monotonic", return_value=130):
        assert _core(Client().get(URL))["sermon_notes_per_week"] == 8
    # Backward wall time must rebuild rather than reusing a later price snapshot.
    _price(amount=55, at=now-timedelta(hours=1))
    _price(amount=66, at=now+timedelta(hours=1))
    with patch("selahcue_api.apps.catalogue.public_catalogue.timezone.now", return_value=now+timedelta(hours=2)):
        assert _core(Client().get(URL))["offers"][0]["amount_minor"] == "66"
    with patch("selahcue_api.apps.catalogue.public_catalogue.timezone.now", return_value=now):
        assert _core(Client().get(URL))["offers"][0]["amount_minor"] == "55"


def test_data_changes_during_projection_are_not_cached_or_published():
    with patch("selahcue_api.apps.catalogue.public_catalogue._revision", side_effect=[8,9]):
        response = Client().get(URL)
    assert response.status_code == 503
    assert Client().get(URL).status_code == 200


def test_display_name_and_order_come_from_data_without_tier_branch():
    plan = Plan.objects.get(code="CORE")
    plan.display_name = "Choir"
    plan.sort_order = 0
    plan.save()
    first = Client().get(URL).json()["plans"][0]
    assert (first["key"], first["name"], first["sermon_notes_per_week"]) == ("CORE", "Choir", 5)


def test_bounded_plan_and_offer_capacity_refuses_instead_of_truncating(monkeypatch):
    monkeypatch.setattr("selahcue_api.apps.catalogue.public_catalogue.MAX_PUBLIC_PLANS", 2)
    assert Client().get(URL).status_code == 503
    monkeypatch.setattr("selahcue_api.apps.catalogue.public_catalogue.MAX_PUBLIC_PLANS", 64)
    monkeypatch.setattr("selahcue_api.apps.catalogue.public_catalogue.MAX_OFFERS_PER_PLAN", 2)
    for currency in ("USD", "JPY", "EUR"):
        _price(currency=currency)
    assert Client().get(URL).status_code == 503


def test_unknown_current_currency_scale_does_not_guess_cents():
    _price()
    with patch("selahcue_api.apps.catalogue.public_catalogue.currency_minor_units", return_value=None):
        assert Client().get(URL).status_code == 503


def test_missing_revision_and_missing_catalogue_are_unavailable():
    CatalogueRevision.objects.all().delete()
    assert Client().get(URL).status_code == 503
    Plan.objects.all().delete()
    assert Client().get(URL).status_code == 503


@override_settings(SELAHCUE_THROTTLE_PUBLIC_CATALOGUE=(1,60), SELAHCUE_TRUSTED_PROXY_COUNT=1)
def test_trusted_proxy_sources_and_ipv6_64_bucket_follow_shared_policy():
    client = Client(REMOTE_ADDR="10.0.0.5")
    assert client.get(URL, HTTP_X_FORWARDED_FOR="2001:db8:1:2::1").status_code == 200
    assert client.get(URL, HTTP_X_FORWARDED_FOR="2001:db8:1:2::2").status_code == 429
    assert client.get(URL, HTTP_X_FORWARDED_FOR="2001:db8:1:3::1").status_code == 200


def test_new_exact_marketing_proxy_preserves_own_trusted_proto_directives():
    matches = [b for b in guard._blocks() if b["header"] == "location = /v1/catalogue/plans"]
    assert len(matches) == 1
    own = guard._statements(matches[0]["body"])
    assert ("proxy_pass", "$selahcue_api$request_uri") in own
    assert ("proxy_set_header", "X-Forwarded-Proto", "$selahcue_client_proto") in own
    assert ("proxy_set_header", "Referer", "") in own
    assert not any(b["header"] == "location /v1/" for b in guard._blocks())


@pytest.mark.parametrize("raw", ["+7", "0007", "٧"])
def test_existing_governed_integer_vocabulary_projects_as_a_finite_count(raw):
    actor = ActorContext(kind=ActorKind.STAFF, actor_id="public-test-ops",
        staff_permissions=frozenset({StaffPermission.GRANT_ENTITLEMENT}))
    set_plan_grant(actor, SetPlanGrantData(idempotency_key="public-vocabulary-0001", plan_code="CORE",
        dimension_key="sermon_notes_per_week", raw_value=raw, reason="Public numeric vocabulary test."))
    assert _core(Client().get(URL))["sermon_notes_per_week"] == 7


def test_exact_proxy_unavailable_fallback_keeps_json_no_store_and_security_headers():
    blocks = guard._blocks()
    location = next(b for b in blocks if b["header"] == "location = /v1/catalogue/plans")
    assert ("error_page", "502", "504", "=503", "@public_catalogue_unavailable") in guard._statements(location["body"])
    fallback = next(b for b in blocks if b["header"] == "location @public_catalogue_unavailable")
    own = guard._statements(fallback["body"])
    assert ("default_type", "application/json") in own
    assert ("return", "503", '{"error":{"code":"catalogue_unavailable"}}') in own
    assert ("add_header", "Cache-Control", "no-store", "always") in own
    server = next(b for b in blocks if b["header"] == "server")
    # Cache-Control disables nginx inheritance; every server security header must
    # therefore be repeated unchanged in the local error response.
    headers = [statement for statement in guard._statements(server["body"]) if statement[0] == "add_header"]
    assert headers
    assert all(header in own for header in headers)


def test_real_csrf_middleware_rejects_unsafe_post_without_writes():
    before = (Plan.objects.count(), PlanGrant.objects.count(), PlanPrice.objects.count())
    response = Client(enforce_csrf_checks=True).post(URL, data="{}", content_type="application/json")
    assert response.status_code == 403
    assert response.headers["Content-Type"].startswith("text/html")
    assert (Plan.objects.count(), PlanGrant.objects.count(), PlanPrice.objects.count()) == before


def test_exact_public_proxy_has_finite_outage_timeouts_below_client_deadline():
    location=next(b for b in guard._blocks() if b['header']=='location = /v1/catalogue/plans')
    own=guard._statements(location['body'])
    for directive,value in [('resolver_timeout','2s'),('proxy_connect_timeout','2s'),('proxy_send_timeout','5s'),('proxy_read_timeout','5s')]:
        assert (directive,value) in own


@pytest.mark.django_db(transaction=True)
def test_real_http_admin_mutations_reach_next_public_response_without_restart(live_server,settings):
    # Explicit exact-dev identity fixture; this proves HTTP/schema/service/DB/cache,
    # not the separately gated production staff authenticator.
    settings.ENVIRONMENT='dev'
    settings.SELAHCUE_ENABLE_ADMIN_CATALOGUE=True
    settings.SELAHCUE_TRUST_ACTOR_HEADERS=True
    base=live_server.url
    bootstrap=urllib.request.urlopen(base+'/graphql/csrf',timeout=10)
    cookies=SimpleCookie();cookies.load(bootstrap.headers['Set-Cookie']);bootstrap.close()
    csrf=cookies['csrftoken'].value
    def request(path,body=None):
        headers={'Accept':'application/json'}
        if body is not None:
            headers.update({'Content-Type':'application/json','Cookie':'csrftoken='+csrf,'X-CSRFToken':csrf,
                'X-SelahCue-Actor-Kind':'staff','X-SelahCue-Actor-Id':'catalogue-http-fixture','X-SelahCue-Staff-Permissions':'manage_plan_pricing'})
        req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
        with urllib.request.urlopen(req,timeout=10) as response:
            assert response.status==200
            return json.load(response)
    def core():return next(plan for plan in request(URL)['plans'] if plan['key']=='CORE')
    initial=core();assert initial['sermon_notes_per_week']==5 and initial['price_state']=='unpriced'
    query='{adminPlanCatalogue{revision}}'
    revision=request('/graphql/admin',{'query':query})['data']['adminPlanCatalogue']['revision']
    mutation='mutation($input:AdminSetPlanGrantInput!){adminSetPlanGrant(input:$input){revision rawValue replayed}}'
    data={'query':mutation,'variables':{'input':dict(planCode='CORE',dimensionKey='sermon_notes_per_week',rawValue='6',reason='Approved HTTP propagation',idempotencyKey='public-http-grant-0001',expectedRevision=revision)}}
    grant=request('/graphql/admin',data)['data']['adminSetPlanGrant']
    assert core()['sermon_notes_per_week']==6
    price='mutation($input:AdminSetPlanPriceInput!){adminSetPlanPrice(input:$input){revision amountMinor replayed}}'
    body={'query':price,'variables':{'input':dict(planCode='CORE',currency='USD',interval='MONTH',amountMinor='0',reason='Approved HTTP propagation',idempotencyKey='public-http-price-0001',expectedRevision=grant['revision'])}}
    result=request('/graphql/admin',body)['data']['adminSetPlanPrice']
    assert result['amountMinor']=='0' and result['replayed'] is False
    projected=core();assert projected['price_state']=='priced' and projected['offers'][0]['amount_minor']=='0'
    assert request('/graphql/admin',body)['data']['adminSetPlanPrice']['replayed'] is True
    assert AuditEvent.objects.filter(actor_id='catalogue-http-fixture').count()==2
