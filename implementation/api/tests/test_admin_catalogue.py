"""Admin mutation boundary; dev identity fixtures are not a production sign-in."""
from selahcue_api.apps.catalogue.admin import rename_admin_plan
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connection,close_old_connections
from selahcue_api.apps.catalogue.models import CatalogueAdminMutation
from test_deployment_guards import _fresh_settings,CONFIGURED_POSTGRES
from django.core.exceptions import ImproperlyConfigured
from licensing_test_support import seed_org,seat_plan,issue_key
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import verify_envelope,load_signing_key
import base64
from datetime import timedelta
import json

import pytest
from django.utils import timezone
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.catalogue.models import Plan, PlanPrice
from selahcue_api.apps.catalogue.services import current_revision, resolve_entitlement
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import SafeAPIError
from selahcue_api.apps.catalogue.admin import read_admin_catalogue, set_admin_price, set_admin_grant

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def enabled_dev_catalogue(settings):
    settings.ENVIRONMENT='dev'
    settings.SELAHCUE_ENABLE_ADMIN_CATALOGUE=True


def staff(permission=StaffPermission.MANAGE_PLAN_PRICING, actor_id='catalogue_admin'):
    return ActorContext(kind=ActorKind.STAFF, actor_id=actor_id, staff_permissions=frozenset({permission}))


def price_data(**changes):
    result = dict(plan_code=Plan.objects.order_by('id').first().code, currency='USD', interval='MONTH', amount_minor=0,
                  effective_from=timezone.now()+timedelta(seconds=1), reason='Approved price update',
                  idempotency_key='admin-price-test-0001', expected_revision=current_revision())
    result.update(changes)
    return result


def test_price_history_replay_and_stale_edit():
    actor=staff(); data=price_data(); before=AuditEvent.objects.count()
    result=set_admin_price(actor, **data)
    assert result['replayed'] is False
    assert PlanPrice.objects.get(pk=result['price_id']).amount_minor == 0
    assert current_revision() > data['expected_revision']
    assert set_admin_price(actor, **data)['replayed'] is True
    assert PlanPrice.objects.count() == 1
    assert AuditEvent.objects.count() == before+1
    with pytest.raises(SafeAPIError) as error:
        set_admin_price(staff(actor_id='other_admin'), **{**data,'idempotency_key':'another-admin-price-0001'})
    assert error.value.extensions['code']=='CONFLICT'
    with pytest.raises(SafeAPIError):
        set_admin_price(actor, **{**data,'amount_minor':42})


@pytest.mark.parametrize('actor',[None,staff(StaffPermission.VIEW_CUSTOMERS),ActorContext(kind=ActorKind.CUSTOMER,actor_id='customer'),ActorContext(kind=ActorKind.DEVICE,actor_id='device')])
def test_service_permission_refuses_without_writes(actor):
    before=AuditEvent.objects.count()
    with pytest.raises(SafeAPIError): set_admin_price(actor,**price_data())
    with pytest.raises(SafeAPIError): read_admin_catalogue(actor)
    assert PlanPrice.objects.count()==0 and AuditEvent.objects.count()==before


@pytest.mark.parametrize('changes',[{'amount_minor':-1},{'currency':'ZZZ'},{'reason':''},{'reason':' '},{'expected_revision':-1}])
def test_invalid_price_does_not_write(changes):
    before=current_revision()
    with pytest.raises(SafeAPIError):set_admin_price(staff(),**price_data(**changes))
    assert PlanPrice.objects.count()==0 and current_revision()==before


def test_grant_revision_replay_audit_and_read():
    plan=Plan.objects.order_by('id').first(); before=AuditEvent.objects.count()
    data=dict(plan_code=plan.code,dimension_key='sermon_notes_per_week',raw_value='6',reason='Approved weekly allowance',idempotency_key='admin-grant-test-0001',expected_revision=current_revision())
    result=set_admin_grant(staff(),**data)
    assert result['raw_value']=='6'
    assert set_admin_grant(staff(),**data)['replayed'] is True
    assert AuditEvent.objects.count()==before+1
    assert any(p['code']==plan.code for p in read_admin_catalogue(staff())['plans'])
    with pytest.raises(SafeAPIError):set_admin_grant(staff(),**{**data,'raw_value':'-1','idempotency_key':'admin-grant-test-0002','expected_revision':current_revision()})


def test_http_query_and_mutation_with_explicit_dev_identity(client,settings):
    settings.ENVIRONMENT='dev'; settings.SELAHCUE_ENABLE_ADMIN_CATALOGUE=True;settings.SELAHCUE_TRUST_ACTOR_HEADERS=True
    headers={'HTTP_X_SELAHCUE_ACTOR_KIND':'staff','HTTP_X_SELAHCUE_ACTOR_ID':'fixture_admin','HTTP_X_SELAHCUE_STAFF_PERMISSIONS':'manage_plan_pricing'}
    query='{ adminPlanCatalogue { revision plans { code name grants { key rawValue } prices { amountMinor currency interval } } } }'
    response=client.post('/graphql/admin',data=json.dumps({'query':query}),content_type='application/json',**headers)
    assert 'errors' not in response.json(),response.json()
    catalogue=response.json()['data']['adminPlanCatalogue'];plan=catalogue['plans'][0]
    mutation='mutation($input:AdminSetPlanGrantInput!){adminSetPlanGrant(input:$input){revision rawValue replayed}}'
    variables={'input':dict(planCode=plan['code'],dimensionKey='sermon_notes_per_week',rawValue='6',reason='Approved HTTP fixture',idempotencyKey='http-admin-grant-0001',expectedRevision=catalogue['revision'])}
    response=client.post('/graphql/admin',data=json.dumps({'query':mutation,'variables':variables}),content_type='application/json',**headers)
    assert response.json()['data']['adminSetPlanGrant']['rawValue']=='6',response.json()


def test_production_mutation_refused_even_with_injected_actor(settings):
    settings.ENVIRONMENT='production';settings.SELAHCUE_ENABLE_ADMIN_CATALOGUE=True
    with pytest.raises(SafeAPIError):set_admin_price(staff(),**price_data())


def test_rename_retains_identifier_and_audits_actor_old_new():
    plan=Plan.objects.order_by('id').first(); old_name=plan.display_name; before=AuditEvent.objects.count()
    result=rename_admin_plan(staff(),plan_code=plan.code,name='Renamed display',reason='Approved public rename',idempotency_key='rename-plan-test-0001',expected_revision=current_revision())
    assert result['name']=='Renamed display'
    plan.refresh_from_db()
    assert plan.changed_by_actor_id=='catalogue_admin' and plan.reason=='Approved public rename'
    event=AuditEvent.objects.order_by('-id').first()
    assert AuditEvent.objects.count()==before+1
    assert event.actor_id=='catalogue_admin' and event.before['display_name']==old_name and event.after['display_name']=='Renamed display'


def test_http_invalid_value_identifies_field(client,settings):
    settings.SELAHCUE_TRUST_ACTOR_HEADERS=True
    headers={'HTTP_X_SELAHCUE_ACTOR_KIND':'staff','HTTP_X_SELAHCUE_ACTOR_ID':'fixture_admin','HTTP_X_SELAHCUE_STAFF_PERMISSIONS':'manage_plan_pricing'}
    mutation='mutation($input:AdminSetPlanPriceInput!){adminSetPlanPrice(input:$input){revision amountMinor replayed}}'
    variables={'input':dict(planCode=Plan.objects.first().code,currency='ZZZ',interval='MONTH',amountMinor='0',effectiveFrom=(timezone.now()+timedelta(seconds=3)).isoformat(),reason='Approved price change',idempotencyKey='http-admin-price-0001',expectedRevision=current_revision())}
    response=client.post('/graphql/admin',data=json.dumps({'query':mutation,'variables':variables}),content_type='application/json',**headers)
    assert response.json()['errors'][0]['extensions']=={'code':'VALIDATION_FAILED','field':'currency'}
    assert PlanPrice.objects.count()==0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('retry',[False,True])
def test_postgres_same_revision_competing_admins_and_concurrent_retry(settings,retry):
    if connection.vendor!='postgresql':pytest.skip('Real PostgreSQL concurrency is exercised by hosted API CI')
    data=price_data(); barrier=Barrier(2)
    def invoke(index):
        close_old_connections();barrier.wait(timeout=10)
        try:
            actor=staff(actor_id='race_admin' if retry else 'race_admin_'+str(index))
            return ('success',set_admin_price(actor,**data))
        except SafeAPIError as error:return ('error',error.extensions['code'])
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(invoke,[0,1]))
    assert CatalogueAdminMutation.objects.count()==1 and PlanPrice.objects.count()==1
    assert AuditEvent.objects.filter(action='catalogue.plan_price_added').count()==1
    if retry:
        assert all(r[0]=='success' for r in results)
        assert sorted(r[1]['replayed'] for r in results)==[False,True]
    else:
        assert sorted(r[0] for r in results)==['error','success']
        assert next(r[1] for r in results if r[0]=='error')=='CONFLICT'


def test_immediate_price_is_current_on_next_read_and_history_is_retained():
    data=price_data(effective_from=None)
    first=set_admin_price(staff(),**data)
    second=set_admin_price(staff(),**{**data,'amount_minor':25,'expected_revision':current_revision(),'idempotency_key':'immediate-price-test-0002'})
    plan=next(p for p in read_admin_catalogue(staff())['plans'] if p['code']==data['plan_code'])
    assert plan['prices'][0]['amount_minor']=='25'
    assert PlanPrice.objects.count()==2 and PlanPrice.objects.get(pk=first['price_id']).amount_minor==0


@pytest.mark.parametrize('environment',['prod','production','staging'])
def test_actual_settings_refuse_catalogue_enablement_outside_dev(monkeypatch,environment):
    with pytest.raises(ImproperlyConfigured,match='real staff authenticator'):
        _fresh_settings(monkeypatch,ENVIRONMENT=environment,SECRET_KEY='non-public-test-key',SELAHCUE_ENABLE_ADMIN_CATALOGUE='1',**CONFIGURED_POSTGRES)


def test_actual_admin_http_grant_reaches_next_signed_manifest(client,settings):
    settings.ENTITLEMENT_SIGNING_KEY=base64.b64encode(bytes(range(32))).decode()
    settings.SELAHCUE_TRUST_ACTOR_HEADERS=True
    plan=seat_plan('CATALOGUE-ADMIN-FIXTURE',2,other_grants={'sermon_notes_per_week':'1'})
    issued=issue_key(seed_org('catalogue-admin'),tag='catalogue-admin',plan_code=plan.code)
    activation=client.post('/v1/activations',data=json.dumps(dict(idempotency_key='catalogue-admin-activate',license_key=issued.full_key,device_fingerprint='catalogue-admin-device',platform='macos')),content_type='application/json')
    assert activation.status_code==200,activation.content
    token=activation.json()['activation_token']
    def manifest():return verify_envelope(build_entitlement_manifest(token).envelope,public_key=load_signing_key(settings.ENTITLEMENT_SIGNING_KEY).public_key())
    assert manifest()['grants']['sermon_notes_per_week']==1
    query='mutation($input:AdminSetPlanGrantInput!){adminSetPlanGrant(input:$input){revision rawValue replayed}}'
    variables={'input':dict(planCode=plan.code,dimensionKey='sermon_notes_per_week',rawValue='6',reason='Approved weekly allowance',idempotencyKey='manifest-admin-grant-0001',expectedRevision=current_revision())}
    response=client.post('/graphql/admin',data=json.dumps({'query':query,'variables':variables}),content_type='application/json',HTTP_X_SELAHCUE_ACTOR_KIND='staff',HTTP_X_SELAHCUE_ACTOR_ID='fixture_admin',HTTP_X_SELAHCUE_STAFF_PERMISSIONS='manage_plan_pricing')
    assert 'errors' not in response.json(),response.json()
    assert manifest()['grants']['sermon_notes_per_week']==6
