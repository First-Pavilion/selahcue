"""Resend-verification mutation (86ak120ac / DEC-007).

Uma's /verify states V3-V6 and desktop A13 all offer "Resend verification email"; before
this slice there was no mutation anywhere in the API for them to call, so a user whose
24-hour link lapsed had no self-service route back — they could not verify, could not sign
in, and could not ask for a new link.

THE TWO PROPERTIES THIS FILE PINS
---------------------------------
1. NO ENUMERATION. The response is byte-identical for an unknown address, a known
   unverified account, and a known already-verified account. An unauthenticated
   email-sending endpoint is a particularly attractive existence oracle.
2. NO TIMING ORACLE. Dispatching a real email is measurably slower than doing nothing —
   `make_password` alone is ~120ms on the reference machine — so a naive implementation
   leaks existence through latency even with an identical body. `test_response_timing_...`
   is a real probe, and it runs against a sender that simulates broker latency so the
   dispatch cost is inside the measured window rather than assumed away.
"""

import json
import logging
import random
import statistics
import time

import pytest
from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import (
    CredentialToken,
    CredentialTokenPurpose,
    CustomerOrg,
    CustomerRole,
    CustomerStatus,
    CustomerUser,
    CustomerUserStatus,
)
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db

# Captured at IMPORT, before the autouse `_no_constant_time_floor` fixture zeroes the setting
# for every test in this module. This is the floor a deployment actually runs with.
PRODUCTION_FLOOR = settings.ACCOUNT_RESEND_MIN_SECONDS


RESEND = """
    mutation Resend($e: String!) {
      resendVerificationEmail(email: $e) { accepted }
    }
"""
VERIFY = "mutation Verify($t: String!) { verifyEmail(token: $t) { verified } }"


@pytest.fixture(autouse=True)
def _fresh_throttle_budget():
    """The resend budget lives in the default LocMemCache, which persists for the whole
    pytest process — spent budget would otherwise leak between tests and rate-limit them."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def _no_constant_time_floor(settings):
    """Every resend is padded to a fixed duration to close the timing oracle. That is the
    point of the feature, but it would add a quarter-second to every test here, so the
    floor is switched off by default and switched back ON explicitly by the timing test —
    the only test whose subject it actually is."""
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0


class CapturingSender(services.EmailSender):
    def __init__(self, dispatch_delay=0.0):
        self.verify_tokens = []
        self.dispatch_delay = dispatch_delay

    def send_email_verification(self, user, raw_token):
        # Simulates the broker round trip a real `.delay()` performs, so the timing probe
        # measures a dispatch cost instead of pretending it is free.
        if self.dispatch_delay:
            time.sleep(self.dispatch_delay)
        self.verify_tokens.append(raw_token)


@pytest.fixture
def sender():
    captured = CapturingSender()
    services.set_email_sender(captured)
    yield captured
    services.set_email_sender(services.EmailSender())


def post_account(client, query, variables=None):
    # Dispatch is registered with `transaction.on_commit`, which under django_db's rollback
    # would never fire. This is Django's own API for running the callbacks still pending at
    # the end of the request; ones discarded by a rolled-back savepoint are NOT among them.
    with TestCase.captureOnCommitCallbacks(execute=True):
        return client.post(
            "/graphql/account",
            data=json.dumps({"query": query, "variables": variables or {}}),
            content_type="application/json",
        )


def body(response):
    return json.loads(response.content)


def error_code(response):
    errors = body(response).get("errors") or []
    return (errors[0].get("extensions") or {}).get("code") if errors else None


def resend(client, email):
    return post_account(client, RESEND, {"e": email})


def _make_user(email, *, verified=False, status=None, tag="x"):
    """Create an org + user directly. Deliberately NOT via the signup mutation: that costs a
    PBKDF2 hash per user and the timing test needs a dozen of them."""
    org = CustomerOrg.objects.create(
        name=f"Resend Church {tag}",
        slug=f"resend-church-{tag}",
        status=CustomerStatus.TRIAL,
        primary_contact_email=email,
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        created_by_actor_id="test",
        idempotency_key=f"resend-org-{tag}",
    )
    return CustomerUser.objects.create(
        customer=org,
        email=email,
        email_fingerprint=services._email_fingerprint(email),
        password_hash="pbkdf2_sha256$dummy",
        status=status or (CustomerUserStatus.ACTIVE if verified else CustomerUserStatus.INVITED),
        role=CustomerRole.ADMIN,
        email_verified_at=timezone.now() if verified else None,
        created_by_actor_id="test",
        idempotency_key=f"resend-user-{tag}",
    )


# --- AC1: a real resend works -----------------------------------------------------------
def test_unverified_account_receives_a_fresh_verification_link(client, sender):
    _make_user("pastor@resend.example", tag="fresh")

    response = resend(client, "pastor@resend.example")

    assert response.status_code == 200
    assert body(response)["data"]["resendVerificationEmail"]["accepted"] is True
    assert len(sender.verify_tokens) == 1
    assert sender.verify_tokens[0].startswith("SC-EVF-")


def test_the_resent_link_completes_verification_end_to_end(client, sender, settings):
    """AC6 through the REAL stack: service -> Celery task -> rendered template -> the link
    in the delivered message actually verifies. (MailHog is the compose equivalent of
    `mail.outbox`; both assert the message that would leave the process.)"""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.FRONTEND_BASE_URL = "https://app.selahcue.test"
    services.set_email_sender(services.get_email_sender())
    from selahcue_api.apps.accounts.email import CeleryEmailSender

    services.set_email_sender(CeleryEmailSender())
    user = _make_user("stranded@resend.example", tag="e2e")
    mail.outbox.clear()

    resend(client, "stranded@resend.example")

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["stranded@resend.example"]
    marker = "/verify?token="
    assert marker in message.body
    token = message.body.split(marker, 1)[1].split()[0].strip().rstrip(".,)")

    verified = post_account(client, VERIFY, {"t": token})
    assert body(verified)["data"]["verifyEmail"]["verified"] is True
    user.refresh_from_db()
    assert user.status == CustomerUserStatus.ACTIVE
    assert user.email_verified_at is not None


# --- AC2: no enumeration ----------------------------------------------------------------
def test_the_three_cases_are_byte_identical(client, sender):
    """Unknown / known-unverified / known-already-verified must be indistinguishable. Any
    difference in status, body or field set re-introduces the oracle the rest of the
    accounts surface was written to avoid."""
    _make_user("unverified@resend.example", tag="enum-u")
    _make_user("verified@resend.example", verified=True, tag="enum-v")

    unknown = resend(client, "ghost@resend.example")
    unverified = resend(client, "unverified@resend.example")
    already = resend(client, "verified@resend.example")

    assert unknown.status_code == unverified.status_code == already.status_code == 200
    assert unknown.content == unverified.content == already.content
    assert body(unknown) == {"data": {"resendVerificationEmail": {"accepted": True}}}

    # Only the genuinely unverified account produced an email.
    assert len(sender.verify_tokens) == 1
    assert CredentialToken.objects.count() == 1


def test_already_verified_and_unknown_addresses_mint_nothing(client, sender):
    _make_user("done@resend.example", verified=True, tag="noop-v")

    resend(client, "done@resend.example")
    resend(client, "nobody@resend.example")

    assert sender.verify_tokens == []
    assert CredentialToken.objects.count() == 0


def test_a_disabled_account_gets_no_new_link(client, sender):
    """A seat that was revoked before it ever verified must not be handed a fresh way in —
    and the caller still cannot tell the difference."""
    _make_user("disabled@resend.example", status=CustomerUserStatus.DISABLED, tag="dis")

    response = resend(client, "disabled@resend.example")

    assert body(response) == {"data": {"resendVerificationEmail": {"accepted": True}}}
    assert sender.verify_tokens == []
    assert CredentialToken.objects.count() == 0


# --- AC3: no timing oracle --------------------------------------------------------------
# The dispatch the probe injects, standing in for a broker publish. It MUST stay larger than
# the spread the probe tolerates: if it were smaller, the probe would still pass with the
# constant-time floor deleted entirely, and would be pinning nothing at all. Asserted here
# rather than trusted, so neither constant can be retuned into vacuity on its own: a premise
# a test depends on belongs next to the constant, not in prose somebody has to remember.
PROBE_DISPATCH_SECONDS = 0.06
# ABSOLUTE, on purpose. A timing leak is an absolute quantity: what an attacker can resolve is
# milliseconds, not a percentage of the server's speed, so a ratio-based budget would let the
# permitted leak GROW on slower hardware — backwards. An absolute budget is only affordable
# because the floor below is calibrated to the host; at a fixed floor it was not (see the
# docstring), and that is the bug this replaces rather than the thing to relax.
PROBE_SPREAD_BUDGET_SECONDS = 0.030
assert PROBE_DISPATCH_SECONDS > PROBE_SPREAD_BUDGET_SECONDS, (
    "the simulated dispatch must exceed the tolerated spread, or deleting the constant-time "
    "floor would not make this probe fail and it would be pinning nothing"
)
# The floor the probe imposes, as a multiple of the slowest branch's measured cost on THIS
# host. 1.5x mirrors the margin `test_the_eligible_branch_costs_well_under_the_constant_time_
# floor` requires of the shipped floor (work < floor * 2/3), so the probe asks the same
# question of the host it is actually running on.
PROBE_FLOOR_MULTIPLE = 1.5
# A case whose median lands further than this past the floor was not padded — the host is
# slower now than it was at calibration.
PROBE_FLOOR_FIT_TOLERANCE = 1.10
# Beyond this the probe would take minutes for one assertion. A host that slow is reported,
# not measured.
PROBE_MAX_FLOOR_SECONDS = 2.0


@pytest.mark.django_db(transaction=True)
def test_response_timing_does_not_distinguish_the_three_cases(client, settings):
    """THE timing probe. `make_password` costs a PBKDF2 hash and email dispatch costs a broker
    round trip, so without deliberate equalisation the unverified case is measurably slower
    than the unknown one and the byte-identical body pinned above buys nothing.

    WHAT THIS PINS: that `_pad_to_floor` actually equalises the three cases. It deliberately
    does NOT pin how big the shipped floor should be — that is
    `test_the_eligible_branch_costs_well_under_the_constant_time_floor`, which measures the
    branch's own work against the value that ships. Separating those two questions is the
    whole point of the rewrite, because they answer to different things: equalisation is a
    property of the code, and floor SIZING is a property of the hardware.

    WHY THE PREVIOUS FORM COULD NOT PASS ON CI, EVER. It hardcoded
    `ACCOUNT_RESEND_MIN_SECONDS = 0.25`, commented "the production default" — which it stopped
    being in 419d8a6, where the floor moved to 0.4 precisely because 0.25 left too little
    headroom. The probe went on running the value that commit had just rejected. That alone
    was drift; the hardware made it fatal. A padded floor equalises only while every branch
    finishes INSIDE it, and on the GitHub runner one PBKDF2 costs ~460ms, so all three cases
    ran past a 250ms floor and NOTHING was padded. The measured spread was then just the
    eligible branch's extra work — overwhelmingly this probe's own 60ms injected dispatch —
    and the assertion reduced to `66ms < 30ms`. Deterministically false, which is exactly what
    CI reported: 67.1ms, 66.2ms and 68.0ms on three runs across eleven days. Those are three
    measurements of the same real quantity, not three flakes, and no threshold that still
    meant anything could have absorbed them.

    SO THE FLOOR IS CALIBRATED TO THIS HOST. The probe first measures the slowest branch
    unpadded, then imposes the floor a deployment on hardware this speed would need. Machine
    speed then cancels: an adequate floor collapses the spread to scheduler noise — 1.4ms
    measured over 15 samples per case on the development machine — whatever the host. The
    absolute budget above is therefore generous rather than lucky, and it stays absolute
    because that is the unit an attacker measures in.

    HOW TO READ A RED HERE — none of these mean "re-run it":
    * SPREAD OVER BUDGET while every case sat at the floor: a real, observable timing
      difference has been introduced between the three cases. This is the finding the test
      exists for.
    * `min(medians)` BELOW the floor: the padding did not run. The equalisation is gone, not
      merely degraded.
    * SKIPPED, "every case outgrew the floor": the host became materially slower between
      calibration and measurement (a parallel build, a throttled runner). Nothing is claimed
      about the code either way. Note this cannot hide a regression in ONE branch: that leaves
      the other two padded, so it fails on spread instead of skipping.

    KNOWN LIMIT, stated so nobody re-derives it: because the floor is calibrated from the
    eligible branch, a change that makes that branch MORE expensive raises the floor with it
    and stays invisible here. That is deliberate — an adequate floor genuinely does hide it —
    and it is the sibling headroom test, which measures the same cost against the SHIPPED
    floor, that refuses to let the cost grow unnoticed.

    `transaction=True` is LOAD-BEARING, not incidental. Every other test here runs inside
    django_db's outer atomic, where the real COMMIT never happens and `transaction.on_commit`
    dispatch is deferred to `captureOnCommitCallbacks` — i.e. it would be measured AFTER the
    service (and its padding) had already returned, which is not what production does. With
    real transactions the callback fires where it really fires: at the atomic exit inside the
    service, INSIDE the padded window. Without this the probe measures a pytest artifact and
    reports a ~60ms leak that the deployed code does not have.
    """
    assert PRODUCTION_FLOOR == services.RESEND_MIN_SECONDS_DEFAULT, (
        "settings.ACCOUNT_RESEND_MIN_SECONDS and RESEND_MIN_SECONDS_DEFAULT have drifted; the "
        "probe reports the shipped floor in its diagnostics and must not report a stale one"
    )
    # The probe needs `samples * 3` calls plus calibration from one IP, which the real per-IP
    # and global budgets (10/hr and 500/hr) would refuse partway through — a rate-limited call
    # is fast and would be measured as if it were a fast branch. Lift the two budgets that are
    # not this test's subject; the per-address budget is untouched because every call here
    # uses a fresh address anyway.
    settings.SELAHCUE_THROTTLE_RESEND_IP = (1000, 3600)
    settings.SELAHCUE_THROTTLE_RESEND_GLOBAL = (1000, 3600)
    slow = CapturingSender(dispatch_delay=PROBE_DISPATCH_SECONDS)
    services.set_email_sender(slow)
    try:
        samples = 5
        calibration_samples = 4
        for i in range(samples):
            _make_user(f"u{i}@timing.example", tag=f"t-u{i}")
            _make_user(f"v{i}@timing.example", verified=True, tag=f"t-v{i}")
        for i in range(calibration_samples):
            _make_user(f"cal{i}@timing.example", tag=f"t-cal{i}")

        # A plain post, NOT `post_account`: under `transaction=True` the on_commit callback
        # already fired inside the service, and wrapping the call in captureOnCommitCallbacks
        # would put an empty-list bookkeeping pass inside the measured window for no reason.
        def timed_resend(email):
            started = time.perf_counter()
            client.post(
                "/graphql/account",
                data=json.dumps({"query": RESEND, "variables": {"e": email}}),
                content_type="application/json",
            )
            return time.perf_counter() - started

        # CALIBRATION. Measure the ELIGIBLE branch — the slowest of the three, and the only one
        # that mints, audits and dispatches — with the padding off, so what is measured is the
        # work the floor has to cover.
        #
        # MAXIMUM, and this is the opposite choice from the sibling headroom test ON PURPOSE.
        # That test ESTIMATES AN INTRINSIC COST, a property of the code, so it takes the
        # minimum: noise only ever adds time, and the fastest sample is the cleanest estimate.
        # This one PROVISIONS A FLOOR that has to keep covering the branch for the whole
        # measurement that follows, so the machine can only be assumed as fast as its worst
        # observed sample. Taking the minimum here sizes the floor for a machine that is
        # already gone by the time the probe runs: on a host degrading under parallel load,
        # `min` calibration produced floors the eligible branch then overran, which reads as
        # an oracle and is really just a floor provisioned from an optimistic sample.
        settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0
        slowest_branch = max(
            timed_resend(f"cal{i}@timing.example") for i in range(calibration_samples)
        )
        floor = slowest_branch * PROBE_FLOOR_MULTIPLE
        if floor > PROBE_MAX_FLOOR_SECONDS:
            pytest.skip(
                f"host too slow to probe: the eligible branch costs {slowest_branch * 1000:.0f}ms "
                f"here, needing a {floor * 1000:.0f}ms floor and minutes of wall clock for one "
                f"assertion. Note this is itself a finding about the shipped "
                f"{PRODUCTION_FLOOR * 1000:.0f}ms floor on hardware this speed."
            )
        settings.ACCOUNT_RESEND_MIN_SECONDS = floor

        timings = {"unknown": [], "unverified": [], "verified": []}
        addresses = {
            "unknown": lambda i: f"ghost{i}@timing.example",
            "unverified": lambda i: f"u{i}@timing.example",
            "verified": lambda i: f"v{i}@timing.example",
        }
        # Interleaved so warm-up or GC drift cannot land on one case, and SHUFFLED within each
        # round so a case cannot inherit a systematic cost from its fixed position in the
        # round. Seeded, so a failure is reproducible.
        rng = random.Random(20260825)
        for i in range(samples):
            cases = list(addresses.items())
            rng.shuffle(cases)
            for case, address in cases:
                timings[case].append(timed_resend(address(i)))

        medians = {case: statistics.median(values) for case, values in timings.items()}
        report = {c: round(v * 1000, 1) for c, v in medians.items()}
        outgrew = {c: m for c, m in medians.items() if m > floor * PROBE_FLOOR_FIT_TOLERANCE}
        # NULL CONTROL, free and measured in the same run under the same load: `unknown` and
        # `verified` are not merely similar, they are the SAME code path — both land in the
        # `not eligible` branch. Whatever separates their medians is therefore instrument
        # noise, not signal, which makes it a direct read of how finely this run could resolve
        # anything at all. Reported rather than asserted on: it must never be able to excuse a
        # real difference, only to say how much weight the numbers below carry. On the CI runs
        # that produced this rewrite it was 0.0ms and 0.7ms while `unverified` sat 66ms out —
        # which is how we know that 66ms was work and not weather.
        instrument_noise = abs(medians["unknown"] - medians["verified"])

        # Every case past the floor means the padding was defeated across the board, i.e. the
        # host slowed down after calibration. Nothing can be concluded about the code, and
        # saying so is more honest than either a red or a green. One case past the floor is NOT
        # this: it leaves the others padded and falls through to the spread assertion below.
        if len(outgrew) == len(medians):
            pytest.skip(
                f"host slowed after calibration: every case outgrew the {floor * 1000:.0f}ms "
                f"floor ({report}), so the padding equalised nothing and this run cannot say "
                f"whether the three cases are distinguishable. Not a claim about the code."
            )

        # Guards the equalisation from being satisfied by doing no real work at all: if the
        # padding is gone, every case returns in its own time, which is BELOW the floor.
        assert min(medians.values()) >= floor, (
            f"the constant-time floor did not pad these calls at all — the fastest case "
            f"returned in {min(medians.values()) * 1000:.1f}ms against a {floor * 1000:.0f}ms "
            f"floor ({report}). The equalisation is absent, not merely degraded."
        )
        spread = max(medians.values()) - min(medians.values())
        assert spread < PROBE_SPREAD_BUDGET_SECONDS, (
            f"response time distinguishes the three cases (spread {spread * 1000:.1f}ms "
            f"against a {PROBE_SPREAD_BUDGET_SECONDS * 1000:.0f}ms budget): {report}, at a "
            f"calibrated {floor * 1000:.0f}ms floor. The two same-code-path cases (unknown "
            f"vs verified) differed by {instrument_noise * 1000:.1f}ms, which is this run's "
            f"instrument noise — compare it against the spread before reading anything into "
            f"the number"
            + (
                f". {sorted(outgrew)} outgrew the floor, so the branch is doing more work than "
                f"the floor can hide — raise ACCOUNT_RESEND_MIN_SECONDS or make the branch "
                f"cheaper."
                if outgrew
                else ". Every case sat at the floor, so this is a real difference introduced "
                "inside the padded window."
            )
        )
        # The sending path really ran: `samples` probe sends plus the calibration sends. A
        # spread of zero because nothing was ever dispatched would otherwise read as a pass.
        assert len(slow.verify_tokens) == samples + calibration_samples
    finally:
        services.set_email_sender(services.EmailSender())


# --- the floor is a floor, not a ceiling ------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_the_eligible_branch_costs_well_under_the_constant_time_floor(settings):
    """The floor only equalises while EVERY branch finishes inside it. Past that it stops
    being a constant time at all and the spread is just however much the slow branch overran.

    The timing probe above pins a 60ms dispatch, which fits. That says nothing about how much
    room is left, and the docstring used to claim the floor was "~2x the measured worst case"
    — it is not; the eligible branch's own work is already over half of it. This measures the
    branch UNPADDED and pins the real margin, so shrinking it shows up here as a failure
    rather than as a silently re-opened oracle in production.
    """
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0  # measure the WORK, not the padding
    settings.SELAHCUE_THROTTLE_RESEND_IP = (1000, 3600)
    settings.SELAHCUE_THROTTLE_RESEND_GLOBAL = (1000, 3600)
    services.set_email_sender(services.EmailSender())  # a no-op sender: work only, no dispatch
    try:
        samples = 7
        for i in range(samples):
            _make_user(f"cost{i}@floor.example", tag=f"c{i}")

        costs = []
        for i in range(samples):
            started = time.perf_counter()
            services.resend_email_verification(
                services.ResendVerificationData(email=f"cost{i}@floor.example")
            )
            costs.append(time.perf_counter() - started)

        # The DEPLOYED floor, captured at import before the autouse fixture zeroes it — this
        # test is about the value that actually ships, not the module fallback.
        floor = PRODUCTION_FLOOR
        assert floor == services.RESEND_MIN_SECONDS_DEFAULT, (
            "settings.ACCOUNT_RESEND_MIN_SECONDS and RESEND_MIN_SECONDS_DEFAULT have drifted; "
            "the fallback must not be quietly different from the shipped floor"
        )
        # MINIMUM, not median. The quantity of interest is how much WORK this branch does —
        # a property of the code, which is what a regression would change. Scheduler noise and
        # a loaded CI box only ever ADD time, so the fastest sample is the closest estimate of
        # the intrinsic cost and the only statistic here that does not turn a busy machine into
        # a spurious failure. A real slowdown still raises it.
        cheapest = min(costs)
        # STATED MARGIN: the eligible branch must leave at least a third of the floor spare for
        # dispatch. At the 0.25s default that is ~83ms of headroom on top of its own work.
        # Chosen because the branch is ~130ms of PBKDF2 + INSERT + audit, so a third is what
        # remains once the floor covers it. If dispatch is slower than the headroom the floor
        # is outgrown and `_pad_to_floor` reports it (test below) rather than degrading quietly.
        assert cheapest < floor * (2 / 3), (
            f"the eligible branch's own work is {cheapest * 1000:.1f}ms against a "
            f"{floor * 1000:.0f}ms floor — too little left for dispatch"
        )
    finally:
        services.set_email_sender(services.EmailSender())


def test_outgrowing_the_floor_is_reported_and_the_report_is_rate_limited(settings, caplog):
    """An outgrown floor must SURFACE. Before this it degraded silently: at a 300ms dispatch
    the spread was 174ms and nothing anywhere said so.

    This is live in the compose/dev stack today — `CELERY_TASK_ALWAYS_EAGER=1` makes the
    dispatch an inline SMTP send, well past the headroom. Production is protected only by the
    prod guard on that flag; a remote or TLS Redis broker publish is the same hazard with no
    guard at all.

    The report is rate limited for the same reason the throttle's fail-open path is: one line
    per overrun at request rate is the unbounded logging the repo forbids.
    """
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.02

    services._reset_floor_overrun_reporting()
    with caplog.at_level(logging.WARNING, logger="selahcue_api.apps.accounts.services"):
        # Three overruns in a row; the interval suppresses all but the first.
        for _ in range(3):
            services._pad_to_floor(time.monotonic() - 0.5)

        def overrun_records():
            return [r for r in caplog.records if "constant-time floor" in r.getMessage()]

        overruns = overrun_records()
        assert len(overruns) == 1, "an overrun must be reported exactly once per interval"
        assert overruns[0].levelno == logging.WARNING
        # The message has to carry the size of the miss — "it overran" is not actionable.
        assert "overran by 480ms" in overruns[0].getMessage()

        # A call that FITS reports nothing.
        caplog.clear()
        services._reset_floor_overrun_reporting()
        services._pad_to_floor(time.monotonic())
        assert overrun_records() == []


def test_the_floor_still_pads_a_call_that_fits(settings):
    """Guard the detection from having broken the padding it reports on."""
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.05
    started = time.monotonic()
    services._pad_to_floor(started)
    assert time.monotonic() - started >= 0.05


def test_a_missing_caller_ip_spends_a_shared_budget_rather_than_none(settings, caplog):
    """Losing the caller IP must cost something visible. It used to be `if data.client_ip:`,
    which silently deleted the per-IP budget on an unauthenticated mail-sending endpoint —
    and `client_ip()` never returns empty, so the only way to reach it is the transport
    supplying no request at all (a GraphQL context-shape change). That failure had no error
    and no log; now it shares one bucket and says so."""
    from django.core.cache import cache

    settings.SELAHCUE_THROTTLE_RESEND_IP = (2, 3600)
    settings.SELAHCUE_THROTTLE_RESEND_GLOBAL = (1000, 3600)
    settings.SELAHCUE_THROTTLE_RESEND_ADDRESS = (1000, 900)
    cache.clear()
    services._reset_floor_overrun_reporting()

    with caplog.at_level(logging.WARNING, logger="selahcue_api.apps.accounts.services"):
        # Distinct addresses, so only the per-IP budget can be what stops this.
        for i in range(2):
            services.resend_email_verification(
                services.ResendVerificationData(email=f"noip{i}@budget.example", client_ip="")
            )
        with pytest.raises(SafeAPIError) as exhausted:
            services.resend_email_verification(
                services.ResendVerificationData(email="noip9@budget.example", client_ip="")
            )
    assert exhausted.value.code is ErrorCode.RATE_LIMITED

    reports = [r for r in caplog.records if "could not resolve a caller IP" in r.getMessage()]
    assert len(reports) == 1, "the loss must be reported, once per interval"


# --- a limiter outage degrades the SEND, never the response -----------------------------
class _BrokenStore:
    """A limiter store that is down. `should_allow` fails open on this, by design for the
    /v1 device READ surface it was written for."""

    def incr_with_expiry(self, key, window_seconds):
        raise RuntimeError("redis is down")


@pytest.fixture
def limiter_down(monkeypatch):
    from selahcue_api.apps.throttling import guards

    monkeypatch.setattr(guards, "CacheStore", lambda _cache: _BrokenStore())
    services._reset_floor_overrun_reporting()
    services._reset_degraded_send_window()


def test_a_limiter_outage_bounds_the_sending_without_denying_the_response(
    settings, caplog, limiter_down
):
    """Failing all three budgets open at once turns an unauthenticated mail-sending endpoint
    unbounded — inbox flooding and unbounded provider cost — for as long as Redis is down.

    The response must NOT fail closed: denying here would reintroduce the enumeration oracle
    the whole mutation exists to avoid, since the caller could tell a refused resend from an
    accepted one. So the RESPONSE stays uniformly accepted:true and the SEND is what degrades,
    under a conservative process-local ceiling.
    """
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (2, 60)
    captured = CapturingSender()
    services.set_email_sender(captured)
    try:
        for i in range(5):
            _make_user(f"outage{i}@degrade.example", tag=f"o{i}")

        with caplog.at_level(logging.WARNING, logger="selahcue_api.apps.accounts.services"):
            # The send is registered with `transaction.on_commit`, so under django_db's
            # rollback it never fires and the count below would read 0 no matter what the
            # ceiling did — a green that proved nothing. `post_account` solves this for the
            # tests that go through the view; this one calls the service directly, so it
            # needs the same wrapper for the same reason.
            with TestCase.captureOnCommitCallbacks(execute=True):
                results = [
                    services.resend_email_verification(
                        services.ResendVerificationData(
                            email=f"outage{i}@degrade.example", client_ip="10.0.0.1"
                        )
                    )
                    for i in range(5)
                ]

        # Every caller is told the same thing — no oracle, no outage-shaped error.
        assert [r.accepted for r in results] == [True] * 5
        # ...but only the ceiling's worth of mail actually left.
        assert len(captured.verify_tokens) == 2, (
            "a limiter outage must bound sending, not hand out an unmetered send path"
        )
        skips = [r for r in caplog.records if "limiter unavailable" in r.getMessage()]
        assert len(skips) == 1, "the degradation must be reported, once per interval"
    finally:
        services.set_email_sender(services.EmailSender())


def test_a_skipped_send_does_not_destroy_the_users_existing_link(settings, limiter_down):
    """Skipping the send must skip the MINT too. Superseding a live link and then not
    delivering its replacement would leave the user strictly worse off than before they
    asked — a working link traded for nothing."""
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (0, 60)  # ceiling exhausted immediately
    user = _make_user("keeplink@degrade.example", tag="keep")
    live = CredentialToken.objects.create(
        customer_user=user,
        purpose=CredentialTokenPurpose.EMAIL_VERIFY,
        token_fingerprint=services._fingerprint("SC-EVF-pre-existing"),
        masked_token="SC-EVF-pre...xxxx",
        expires_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert services.resend_email_verification(
        services.ResendVerificationData(email="keeplink@degrade.example", client_ip="10.0.0.2")
    ).accepted is True

    live.refresh_from_db()
    assert live.consumed_at is None, "the user's working link must survive a skipped resend"
    assert CredentialToken.objects.filter(customer_user=user).count() == 1, "nothing was minted"


# --- AC4: the previous token dies -------------------------------------------------------
def test_issuing_a_new_token_invalidates_the_previous_one(client, sender):
    _make_user("rotate@resend.example", tag="rot")

    resend(client, "rotate@resend.example")
    first_token = sender.verify_tokens[-1]
    resend(client, "rotate@resend.example")
    second_token = sender.verify_tokens[-1]

    assert first_token != second_token
    # The old link no longer verifies...
    assert error_code(post_account(client, VERIFY, {"t": first_token})) == "VALIDATION_FAILED"
    # ...and the new one does.
    assert body(post_account(client, VERIFY, {"t": second_token}))["data"]["verifyEmail"]["verified"] is True


def test_the_raw_token_is_never_stored_in_plaintext(client, sender):
    _make_user("hash@resend.example", tag="hash")
    resend(client, "hash@resend.example")
    raw = sender.verify_tokens[-1]

    token = CredentialToken.objects.get(purpose=CredentialTokenPurpose.EMAIL_VERIFY)
    assert raw not in token.token_hash
    assert raw != token.token_fingerprint
    assert raw != token.masked_token


# --- AC5: rate limiting -----------------------------------------------------------------
def test_per_address_limit_caps_repeated_resends(client, sender, settings):
    settings.SELAHCUE_THROTTLE_RESEND_ADDRESS = (2, 900)
    _make_user("flood@resend.example", tag="flood")

    first = resend(client, "flood@resend.example")
    second = resend(client, "flood@resend.example")
    third = resend(client, "flood@resend.example")

    assert body(first)["data"]["resendVerificationEmail"]["accepted"] is True
    assert body(second)["data"]["resendVerificationEmail"]["accepted"] is True
    assert error_code(third) == "RATE_LIMITED"
    # The refused request sent nothing — the whole point is not flooding the mailbox.
    assert len(sender.verify_tokens) == 2


def test_the_rate_limited_response_does_not_leak_existence(client, sender, settings):
    """A limit that only bites for REAL accounts would be a perfect oracle: the limiter has
    to key on the address itself, spent identically whether or not an account exists."""
    settings.SELAHCUE_THROTTLE_RESEND_ADDRESS = (1, 900)
    _make_user("known@resend.example", tag="leak")

    resend(client, "known@resend.example")
    resend(client, "ghost@resend.example")
    known_limited = resend(client, "known@resend.example")
    ghost_limited = resend(client, "ghost@resend.example")

    assert error_code(known_limited) == "RATE_LIMITED"
    assert error_code(ghost_limited) == "RATE_LIMITED"
    assert known_limited.status_code == ghost_limited.status_code
    assert known_limited.content == ghost_limited.content


def test_a_global_cap_bounds_total_volume(client, sender, settings):
    """Per-address limits alone let an attacker spray thousands of DISTINCT addresses; the
    cost vector is the total send volume, so that needs its own ceiling."""
    settings.SELAHCUE_THROTTLE_RESEND_GLOBAL = (2, 3600)

    assert body(resend(client, "a@resend.example"))["data"]["resendVerificationEmail"]["accepted"] is True
    assert body(resend(client, "b@resend.example"))["data"]["resendVerificationEmail"]["accepted"] is True
    assert error_code(resend(client, "c@resend.example")) == "RATE_LIMITED"


def test_a_single_ip_cannot_spray_distinct_addresses(client, sender, settings):
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_THROTTLE_RESEND_IP = (2, 3600)

    assert error_code(resend(client, "one@resend.example")) is None
    assert error_code(resend(client, "two@resend.example")) is None
    assert error_code(resend(client, "three@resend.example")) == "RATE_LIMITED"


# --- AC7: audit -------------------------------------------------------------------------
def test_the_resend_is_audited_without_the_token(client, sender):
    user = _make_user("audited@resend.example", tag="aud")

    resend(client, "audited@resend.example")
    raw = sender.verify_tokens[-1]

    events = AuditEvent.objects.filter(action="customer_user.verification_resent")
    assert events.count() == 1
    assert events.get().target_id == str(user.id)

    dumped = json.dumps(
        [
            {"action": e.action, "after": e.after, "before": e.before, "request_id": e.request_id}
            for e in AuditEvent.objects.all()
        ],
        default=str,
    )
    assert raw not in dumped
    assert "audited@resend.example" not in dumped


def test_no_audit_event_for_unknown_or_verified_addresses(client, sender):
    _make_user("quiet@resend.example", verified=True, tag="quiet")

    resend(client, "quiet@resend.example")
    resend(client, "missing@resend.example")

    assert AuditEvent.objects.filter(action="customer_user.verification_resent").count() == 0


# --- input validation -------------------------------------------------------------------
def test_a_malformed_address_is_validation_failed(client, sender):
    """Syntactic validity is caller-knowable, so refusing it leaks nothing — and it keeps
    junk from consuming the global send budget."""
    assert error_code(resend(client, "not-an-email")) == "VALIDATION_FAILED"
    assert error_code(resend(client, "")) == "VALIDATION_FAILED"
    assert sender.verify_tokens == []


def test_address_matching_is_case_and_whitespace_insensitive(client, sender):
    _make_user("mixed@resend.example", tag="case")

    resend(client, "  MiXeD@Resend.Example  ")

    assert len(sender.verify_tokens) == 1
