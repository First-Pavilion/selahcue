"""Seed a THROWAWAY local API database for the 17tnw2b1we2 live run.

SAFETY. This creates administrator accounts and a licence key. It therefore refuses to run unless
BOTH hold, checked before Django is imported and again against the live settings:

  * the database engine is SQLite (SQL_ENGINE unset or ending in "sqlite3"), and
  * SQL_DATABASE is set EXPLICITLY, to a path whose real location (symlinks resolved) is under the
    system temp directory.

Anything else - Postgres, a relative path, the default implementation/api/db.sqlite3, a
non-"dev" ENVIRONMENT, a symlink that leaves the temp directory - is refused with a reason and a
non-zero exit. The password is random per run and exists only in the 0600 SEED_OUT file (also
under the temp directory), which the live harness reads. Nothing is printed that contains it.

  python3 seed_live_api.py --self-test   prove the refusal works (no Django, no database touched)
  python3 seed_live_api.py --check       dry run: validate THIS environment, change nothing
  python3 seed_live_api.py               seed (needs API_DIR, SQL_DATABASE, SEED_OUT)
"""
import json
import os
import secrets
import sys
import tempfile
from datetime import timedelta


def temp_roots():
    """The system temp directories: Python's own (TMPDIR, or /var/folders/... on macOS) and /tmp."""
    return [tempfile.gettempdir(), "/tmp"]


def _under(path, roots):
    """True when `path`, with symlinks resolved, is strictly inside one of `roots`."""
    real = os.path.realpath(path)
    for root in roots:
        base = os.path.realpath(root)
        try:
            if os.path.commonpath([real, base]) == base and real != base:
                return True
        except ValueError:  # different drives on Windows
            continue
    return False


def refusal(env, roots):
    """Why `env` must NOT be seeded, or None when it is a throwaway SQLite file under one of `roots`."""
    engine = env.get("SQL_ENGINE", "django.db.backends.sqlite3")
    if not engine.endswith("sqlite3"):
        return f"SQL_ENGINE is {engine!r}; only SQLite is allowed"
    if env.get("ENVIRONMENT", "dev") != "dev":
        return f"ENVIRONMENT is {env.get('ENVIRONMENT')!r}; only 'dev' is allowed"
    if env.get("DJANGO_SETTINGS_MODULE", "selahcue_api.settings") != "selahcue_api.settings":
        return "DJANGO_SETTINGS_MODULE is not selahcue_api.settings"
    db = env.get("SQL_DATABASE")
    if not db:
        return "SQL_DATABASE is not set (the API would default to implementation/api/db.sqlite3)"
    if not os.path.isabs(db):
        return "SQL_DATABASE is not an absolute path"
    if not _under(db, roots):
        return "SQL_DATABASE is not under the system temp directory"
    out = env.get("SEED_OUT")
    if not out:
        return "SEED_OUT is not set"
    if not os.path.isabs(out) or not _under(out, roots):
        return "SEED_OUT must be an absolute path under the system temp directory"
    return None


def self_test():
    """Exercise `refusal` on hostile and benign environments. Exit code 1 on any mismatch."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = os.path.realpath(raw)
        os.symlink("/", os.path.join(tmp, "escape"))  # a link INSIDE tmp that leaves it
        ok = {"SQL_DATABASE": f"{tmp}/live.sqlite3", "SEED_OUT": f"{tmp}/seed.json"}
        cases = [
            ("a throwaway sqlite file under tmp", ok, False, [tmp]),
            ("nothing set (the default would be the repo's db.sqlite3)", {}, True, [tmp]),
            ("postgres engine", {**ok, "SQL_ENGINE": "django.db.backends.postgresql"}, True, [tmp]),
            ("ENVIRONMENT=prod", {**ok, "ENVIRONMENT": "prod"}, True, [tmp]),
            ("ENVIRONMENT=staging", {**ok, "ENVIRONMENT": "staging"}, True, [tmp]),
            ("a different settings module", {**ok, "DJANGO_SETTINGS_MODULE": "other.settings"}, True, [tmp]),
            ("relative database path", {**ok, "SQL_DATABASE": "live.sqlite3"}, True, [tmp]),
            ("database outside tmp", {**ok, "SQL_DATABASE": "/etc/live.sqlite3"}, True, [tmp]),
            ("database that climbs out of tmp", {**ok, "SQL_DATABASE": f"{tmp}/../live.sqlite3"}, True, [tmp]),
            ("database through a symlink that leaves tmp", {**ok, "SQL_DATABASE": f"{tmp}/escape/etc/live.sqlite3"}, True, [tmp]),
            ("database equal to tmp itself", {**ok, "SQL_DATABASE": tmp}, True, [tmp]),
            ("SEED_OUT missing", {"SQL_DATABASE": ok["SQL_DATABASE"]}, True, [tmp]),
            ("SEED_OUT outside tmp", {**ok, "SEED_OUT": "/var/seed.json"}, True, [tmp]),
        ]
        # With the REAL roots: /tmp is accepted (it is what the README uses), and so is the
        # platform's own temp dir; the repo's default database is not (unless the repo itself
        # lives under a temp dir, in which case the case cannot say anything and is skipped).
        cases.append(("/tmp with the real roots", {"SQL_DATABASE": "/tmp/live.sqlite3", "SEED_OUT": "/tmp/seed.json"}, False, temp_roots()))
        repo_default = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../implementation/api/db.sqlite3"))
        if not _under(repo_default, temp_roots()):
            cases.append(("the repo's own default database with the real roots", {"SQL_DATABASE": repo_default, "SEED_OUT": "/tmp/seed.json"}, True, temp_roots()))
        failures = 0
        for label, env, should_refuse, roots in cases:
            reason = refusal(env, roots)
            good = (reason is not None) == should_refuse
            failures += not good
            print(("ok   " if good else "FAIL ") + label + (f"  -> refused: {reason}" if reason else "  -> accepted"))
        print("self-test:", "FAILED" if failures else "passed")
        return 1 if failures else 0


if "--self-test" in sys.argv:
    sys.exit(self_test())

_reason = refusal(os.environ, temp_roots())
if _reason:
    sys.exit(f"REFUSING TO SEED: {_reason}. This tool only seeds a throwaway SQLite file under the temp directory.")
if "--check" in sys.argv:
    print("check: this environment would be accepted (nothing was changed)")
    sys.exit(0)

sys.path.insert(0, os.environ["API_DIR"])
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "selahcue_api.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.contrib.auth.hashers import make_password  # noqa: E402
from django.utils import timezone  # noqa: E402
from selahcue_api.apps.accounts import services  # noqa: E402
from selahcue_api.apps.accounts.models import CustomerOrg, CustomerRole, CustomerUser, CustomerUserStatus  # noqa: E402
from selahcue_api.apps.catalogue.models import Plan, PlanGrant  # noqa: E402
from selahcue_api.apps.license_keys.services import GenerateLicenseKeyData, generate_license_key  # noqa: E402
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission  # noqa: E402

# Defence in depth: what Django actually loaded must be the file that was checked.
_db = settings.DATABASES["default"]
if not _db["ENGINE"].endswith("sqlite3") or os.path.realpath(str(_db["NAME"])) != os.path.realpath(os.environ["SQL_DATABASE"]):
    sys.exit("REFUSING TO SEED: Django's live database settings differ from SQL_DATABASE")

PASSWORD = secrets.token_urlsafe(18)  # random per run; written only to the 0600 SEED_OUT file


def org(tag):
    return CustomerOrg.objects.create(name=f"Live {tag}", slug=f"live-{tag}", primary_contact_email=f"office@{tag}.example",
        country="NG", timezone="Africa/Lagos", plan="TRIAL", seat_limit=5,
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
# This run used to seed a licence with 3 devices. A licence now takes its device limit from its plan
# (86ak5mn0m), so pick a sellable plan whose `device_instances` is 3 instead of "the first one by id"
# (which is a 1-seat plan in the seeded catalogue); fall back to the old choice if none has 3.
three_seat = (
    PlanGrant.objects.filter(dimension__key="device_instances", raw_value="3", plan__is_fallback=False)
    .select_related("plan").order_by("plan_id").first()
)
plan = (three_seat.plan if three_seat else None) or Plan.objects.exclude(is_fallback=True).order_by("id").first() or Plan.objects.first()
now = timezone.now().replace(microsecond=0)
# 86ak5mn0m: the licence's device limit is copied from this plan's `device_instances` (no
# longer typed here), and the org has no device limit of its own.
result = generate_license_key(actor, GenerateLicenseKeyData(
    idempotency_key="live-license-0001", customer_id=str(main.id), key_type="TRIAL", feature_scope="CHURCH",
    plan_code=plan.code, starts_at=now - timedelta(days=1), expires_at=now + timedelta(days=30),
    timezone="Africa/Lagos", seat_limit=5, territory="NG", reason="Live run for 17tnw2b1we2."))
out = os.environ["SEED_OUT"]
# Created 0600 from the start (no window where it is world-readable), replacing any earlier run.
if os.path.lexists(out):
    os.remove(out)
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as fh:
    json.dump({"password": PASSWORD, "enrollment_key": result.full_key, "plan": plan.code}, fh)
print("seeded: orgs=2 users=4 license issued, plan", plan.code, "(credentials are in SEED_OUT only)")
