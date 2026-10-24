"""Seed a THROWAWAY local API database for the 17tnw2b1we2 live run. Local only, never a real environment."""
import json, os, sys
from datetime import timedelta
sys.path.insert(0, os.environ["API_DIR"])
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "selahcue_api.settings")
import django
django.setup()
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import CustomerOrg, CustomerRole, CustomerUser, CustomerUserStatus
from selahcue_api.apps.catalogue.models import Plan
from selahcue_api.apps.license_keys.services import GenerateLicenseKeyData, generate_license_key
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission  # noqa

PASSWORD = "live-run-correct-horse-1"
def org(tag):
    return CustomerOrg.objects.create(name=f"Live {tag}", slug=f"live-{tag}", primary_contact_email=f"office@{tag}.example",
        country="NG", timezone="Africa/Lagos", plan="TRIAL", seat_limit=5, device_limit=9,
        created_by_actor_id="seed", idempotency_key=f"live-org-{tag}")
def user(o, email, role=CustomerRole.ADMIN, verified=True):
    return CustomerUser.objects.create(customer=o, email=email, email_fingerprint=services._fingerprint(email),
        password_hash=make_password(PASSWORD), status=CustomerUserStatus.ACTIVE, role=role,
        email_verified_at=timezone.now() if verified else None, created_by_actor_id="seed", idempotency_key=f"live-user-{email}")

main = org("grace")
user(main, "admin@grace.example")
user(main, "member@grace.example", role=CustomerRole.MEMBER)
user(main, "unverified@grace.example", verified=False)
empty = org("empty")
user(empty, "admin@empty.example")   # a verified admin whose org has NO licence key

actor = ActorContext(kind=ActorKind.STAFF, actor_id="staff_seed", staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}))
plan = Plan.objects.exclude(is_fallback=True).order_by("id").first() or Plan.objects.first()
now = timezone.now().replace(microsecond=0)
result = generate_license_key(actor, GenerateLicenseKeyData(
    idempotency_key="live-license-0001", customer_id=str(main.id), key_type="TRIAL", feature_scope="CHURCH",
    plan_code=plan.code, starts_at=now - timedelta(days=1), expires_at=now + timedelta(days=30),
    timezone="Africa/Lagos", seat_limit=5, device_limit=3, territory="NG", reason="Live run for 17tnw2b1we2."))
out = os.environ["SEED_OUT"]
with open(out, "w") as fh:
    json.dump({"password": PASSWORD, "enrollment_key": result.full_key, "plan": plan.code}, fh)
os.chmod(out, 0o600)
print("seeded: orgs=2 users=4 license issued, plan", plan.code)
