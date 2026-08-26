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
# Captured at import for the same reason and pinned by the same kind of assertion: this pair
# is a settings value shadowing a module fallback, which is exactly the shape that drifted
# apart and produced the timing bug this file also fixes.
PRODUCTION_DEGRADED_CEILING = settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING


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
# A case whose median lands further than this past the floor was not padded by it.
#
# THE SAME ABSOLUTE QUANTITY AS THE SPREAD BUDGET, deliberately, and that identity is a fix
# for a real defect rather than a tidy-up. This used to be a RATIO (`floor * 1.10`) while the
# verdict below stayed ABSOLUTE (30ms). Two bases, and they agree only where 10% of the floor
# happens to equal 30ms — i.e. at a ~300ms floor, which is about what a quiet dev machine
# calibrates to. That is why it survived review: on the machine it was written on it was
# right. At a 900ms floor the diagnosis is 3x looser than the verdict and at 1813ms it is 6x,
# so a case could sit 150ms past the floor, blow the 30ms spread budget, and still be reported
# as having "sat at the floor" — which sent two reviewers hunting a defect that was not there.
#
# Holding both to one number also makes the pair arithmetically consistent. `min(medians) >=
# floor` is asserted before the spread is read, so a spread at or over budget forces
# `max(medians) >= floor + budget`: whenever this test fails at least one case is provably NOT
# sitting at the floor, and the probe can no longer claim otherwise.
PROBE_FLOOR_FIT_TOLERANCE_SECONDS = PROBE_SPREAD_BUDGET_SECONDS
# `max` is the right calibration statistic for a SUSTAINED slowdown and the wrong one for a
# TRANSIENT spike — it cannot tell them apart, and one descheduled sample then sets the floor
# for the whole run. Everything derived from `slowest_branch` inherits that spike, including
# the recalibration escape hatch below, whose threshold is `slowest_branch *
# PROBE_FLOOR_MULTIPLE` — so the one benign explanation for a red is hardest to reach exactly
# when calibration was noisiest, i.e. exactly when it is most likely to be the true one.
# Sanity-checking `max` against the MEDIAN of the same samples separates the two: under a real
# slowdown every sample moves together and `max ~= median`, so this does not bind; under a
# spike it does.
PROBE_CALIBRATION_SPIKE_RATIO = 2.0
# The null control (two cases that are the SAME code path) is this run's noise floor. A spread
# that is not at least this multiple of it was not resolvable by this run, and the failure
# message must say so rather than assert a real difference. WORDING only — never the verdict,
# which stays absolute; see the null control's own comment for why it must never be able to
# excuse a difference.
PROBE_NOISE_RESOLVABLE_MULTIPLE = 3.0
# Beyond this the probe would take minutes for one assertion. A host that slow is reported,
# not measured.
PROBE_MAX_FLOOR_SECONDS = 2.0


def cases_outgrowing_floor(medians, floor):
    """Which cases finished more than the spread budget past `floor`.

    Extracted from the probe so the rule has ONE definition that a deterministic test can
    exercise directly. The probe itself only reaches this line on a red, on a loaded host,
    at whatever floor that host calibrated to — which is precisely how a diagnosis on the
    wrong basis survived review for as long as it did.
    """
    return sorted(c for c, m in medians.items() if m - floor > PROBE_FLOOR_FIT_TOLERANCE_SECONDS)


def calibration_basis(samples):
    """`(basis, observed_slowest, typical, spiked)` — the branch cost to provision the floor
    from, with the `max` sanity-checked against the median of the same samples.

    Extracted for the same reason as `cases_outgrowing_floor`: the clamp only binds when a
    calibration sample spikes, which no deterministic run reproduces, so without a helper the
    only thing that ever exercises it is the flaky host it exists to protect against.
    """
    observed_slowest = max(samples)
    typical = statistics.median(samples)
    basis = min(observed_slowest, typical * PROBE_CALIBRATION_SPIKE_RATIO)
    return basis, observed_slowest, typical, basis < observed_slowest


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

    HOW TO READ A RED HERE:
    * SPREAD OVER BUDGET, one case sitting more than that same budget past the floor: the
      padding is being OUTRUN — that branch does more work than the floor can hide. This is
      the finding the test exists for, and the message names the branch.
    * `min(medians)` BELOW the floor: the padding did not run. The equalisation is gone, not
      merely degraded.
    * SPREAD OVER BUDGET while the null control reads comparable noise: the run could not
      resolve a difference that fine. The verdict still stands — the null control never
      excuses a failure — but the message says so, and a repeat on a quiet host is what turns
      it into a finding. This probe used to assert "a real difference introduced inside the
      padded window" in exactly this situation, which is both unsound and, once the diagnosis
      and the verdict are held to one basis, arithmetically impossible: `min(medians) >=
      floor` plus an over-budget spread forces some case past the floor by at least the
      budget. Two reviewers lost time to that sentence on unmodified code.
    * SKIPPED, "the host slowed after calibration": before reporting a spread the probe
      re-measures the very branch it calibrated from. If that branch now costs more than the
      whole floor, the host is demonstrably slower than when the floor was provisioned, the
      padding was defeated by the machine rather than by the code, and nothing is claimed
      either way. This is a measurement of the confounder, not an inference from the three
      cases, which matters: the realistic degradation signature is the ELIGIBLE branch
      outgrowing the floor alone, and an earlier version that required all three to outgrow
      turned exactly that case into a false red.

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
            _make_user(f"recal{i}@timing.example", tag=f"t-recal{i}")

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
        #
        # ...but the `max` is SANITY-CHECKED AGAINST THE MEDIAN of the same samples before it
        # is trusted, because `max` cannot tell a sustained slowdown from one descheduled
        # sample and the two want opposite treatment. Under a real slowdown the samples move
        # together, `max ~= median`, and the clamp does not bind. Under a spike it binds, and
        # it has to: an inflated floor propagates into every quantity derived from
        # `slowest_branch`, and the one that matters is the recalibration escape hatch below
        # — its threshold is `slowest_branch * PROBE_FLOOR_MULTIPLE`, so an inflated
        # calibration makes the benign explanation for a red unreachable precisely on the
        # noisy hosts where it is the true one. That is the mechanism behind the false reds
        # this replaces, not a hypothetical.
        settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0
        calibration = [
            timed_resend(f"cal{i}@timing.example") for i in range(calibration_samples)
        ]
        (
            slowest_branch,
            observed_slowest,
            typical_branch,
            calibration_spiked,
        ) = calibration_basis(calibration)
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
        # SAME BASIS AS THE VERDICT — an absolute margin, not a ratio of the floor. See the
        # constant: a relative diagnosis under an absolute verdict is what let this probe
        # report "every case sat at the floor" about a case sitting 150ms past it.
        outgrew = cases_outgrowing_floor(medians, floor)
        # NULL CONTROL, free and measured in the same run under the same load: `unknown` and
        # `verified` are not merely similar, they are the SAME code path — both land in the
        # `not eligible` branch. Whatever separates their medians is therefore instrument
        # noise, not signal, which makes it a direct read of how finely this run could resolve
        # anything at all. Reported rather than asserted on: it must never be able to excuse a
        # real difference, only to say how much weight the numbers below carry. On the CI runs
        # that produced this rewrite it was 0.0ms and 0.7ms while `unverified` sat 66ms out —
        # which is how we know that 66ms was work and not weather.
        instrument_noise = abs(medians["unknown"] - medians["verified"])

        # Guards the equalisation from being satisfied by doing no real work at all: if the
        # padding is gone, every case returns in its own time, which is BELOW the floor. Host
        # slowness can never cause this — it only ever makes calls longer — so this is checked
        # first and is never excused by the recalibration below.
        assert min(medians.values()) >= floor, (
            f"the constant-time floor did not pad these calls at all — the fastest case "
            f"returned in {min(medians.values()) * 1000:.1f}ms against a {floor * 1000:.0f}ms "
            f"floor ({report}). The equalisation is absent, not merely degraded."
        )
        spread = max(medians.values()) - min(medians.values())

        # About to report an oracle — so first rule out the one benign explanation, by
        # measuring it rather than inferring it. The floor was provisioned from the eligible
        # branch BEFORE the probe ran; if the host slowed down in between, that branch outgrows
        # the floor and the padding stops equalising, which is indistinguishable from a leak
        # when you only look at the three cases. Re-measuring the same branch settles it: a
        # branch that now costs more than the entire floor means the machine moved, not the
        # code.
        #
        # LIKE FOR LIKE, and this is the second half of the false-red fix. This used to take
        # `min` of the fresh samples and compare it against a `max`-derived threshold — "so
        # only a real, sustained slowdown counts". That is two different statistics either
        # side of one comparison, and both choices lean the same way: away from skipping.
        # Under bursty load the fresh `min` catches whichever sample the scheduler happened to
        # leave alone, so the branch reads fast even while its median has tripled, and the
        # escape hatch cannot fire. Observed directly while reworking this probe: all three
        # cases sat ~330ms past a 668ms floor — the padding plainly outrun by a host under
        # load 23 — and the probe still reported an oracle. Recalibrating through the SAME
        # `calibration_basis` makes it a comparison of the machine's honest worst case, then
        # against now, and the clamp stops one stalled sample skipping the probe just as it
        # stops one setting the floor.
        #
        # Note what this deliberately does NOT swallow: it re-measures the ELIGIBLE branch
        # specifically, so a leak in a branch the floor was NOT calibrated from still fails
        # loudly — including the Remedy B inversion signature, where the two `not eligible`
        # branches are the expensive ones and the eligible branch stays fast. The case this
        # does hand off is the eligible branch itself growing, which is the KNOWN LIMIT above
        # and belongs to the sibling headroom test.
        if spread >= PROBE_SPREAD_BUDGET_SECONDS:
            settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0
            recalibrated, recal_observed, recal_typical, recal_spiked = calibration_basis(
                [timed_resend(f"recal{i}@timing.example") for i in range(calibration_samples)]
            )
            if recalibrated > slowest_branch * PROBE_FLOOR_MULTIPLE:
                pytest.skip(
                    f"host slowed after calibration: the branch the {floor * 1000:.0f}ms floor "
                    f"was provisioned from cost {slowest_branch * 1000:.0f}ms then and "
                    f"{recalibrated * 1000:.0f}ms now (median {recal_typical * 1000:.0f}ms, "
                    f"slowest {recal_observed * 1000:.0f}ms"
                    f"{', clamped' if recal_spiked else ''}), so it no longer fits inside its "
                    f"own floor and the padding was defeated by the machine, not by the code. "
                    f"Measured {report}, outgrown by {outgrew or 'none'}. Nothing is claimed "
                    f"about the code either way; re-run on a quieter host."
                )
        assert spread < PROBE_SPREAD_BUDGET_SECONDS, (
            f"response time distinguishes the three cases (spread {spread * 1000:.1f}ms "
            f"against a {PROBE_SPREAD_BUDGET_SECONDS * 1000:.0f}ms budget): {report}, at a "
            f"calibrated {floor * 1000:.0f}ms floor"
            + (
                f" (clamped: calibration's slowest sample was {observed_slowest * 1000:.0f}ms "
                f"against a {typical_branch * 1000:.0f}ms median, i.e. a spike rather than a "
                f"slow host, so the floor was provisioned from the clamp)"
                if calibration_spiked
                else ""
            )
            + f". The two same-code-path cases (unknown vs verified) differed by "
            f"{instrument_noise * 1000:.1f}ms, which is this run's instrument noise"
            + (
                f" — NOT FINER THAN the spread being reported "
                f"(x{spread / instrument_noise:.1f}, under the "
                f"x{PROBE_NOISE_RESOLVABLE_MULTIPLE:.0f} this probe needs to resolve one). "
                f"This run could not tell this spread from weather, so read it as a noisy "
                f"host first: re-run on a quiet machine and treat a repeat as the finding."
                if instrument_noise > 0
                and spread < instrument_noise * PROBE_NOISE_RESOLVABLE_MULTIPLE
                else f", comfortably finer than the spread, so the spread is resolvable "
                f"signal rather than weather."
            )
            + (
                f" {outgrew} sat more than the same "
                f"{PROBE_FLOOR_FIT_TOLERANCE_SECONDS * 1000:.0f}ms past the floor, so the "
                f"floor is not covering that branch's work. That is the padding being "
                f"OUTRUN, which is not the same finding as a leak inside it: either the host "
                f"slowed since calibration (the recalibration check above says it did not) "
                f"or that branch now does more work than the floor can hide — raise "
                f"ACCOUNT_RESEND_MIN_SECONDS or make the branch cheaper."
                if outgrew
                else " No case sat more than the budget past the floor, which cannot happen "
                "alongside an over-budget spread once `min(medians) >= floor` has been "
                "asserted: treat this as a defect in the probe's own arithmetic, not as a "
                "finding about the service."
            )
        )
        # The sending path really ran: `samples` probe sends plus the calibration sends. A
        # spread of zero because nothing was ever dispatched would otherwise read as a pass.
        assert len(slow.verify_tokens) == samples + calibration_samples
    finally:
        services.set_email_sender(services.EmailSender())


# The floors two reviewers actually calibrated to on loaded hosts, plus the ~300ms a quiet dev
# machine reaches. 300ms is the ONLY one where a 10%-of-floor diagnosis and a 30ms verdict
# agree, which is exactly why the defect below survived being written, reviewed and run.
@pytest.mark.parametrize("floor", [0.300, 0.900, 1.640, 1.813])
def test_the_probe_diagnoses_an_over_budget_spread_on_the_same_basis_it_judges_it(floor):
    """The probe's verdict is ABSOLUTE (30ms of spread). Its diagnosis — "did this case sit at
    the floor, or outgrow it?" — must be the same quantity, or the two disagree and the probe
    reports something untrue about its own numbers.

    THE DEFECT THIS PINS, which shipped and cost two reviewers real time: the diagnosis was
    `median > floor * 1.10`, a RATIO. Against a 30ms absolute verdict the two coincide only
    near a 300ms floor. At the 1640ms floor one reviewer's loaded host calibrated to, a case
    could sit 150ms past the floor — five times the entire spread budget — and still be
    classified as having "sat at the floor", at which point the probe asserted the difference
    was "a real difference introduced inside the padded window". It was not: the padding was
    being outrun. One reviewer went hunting a service defect that did not exist.

    WHY A SEPARATE TEST. The probe reaches that classification only on a red, only on a loaded
    host, at whatever floor that host happened to calibrate to. Nothing deterministic ever
    executed it, so the basis mismatch was invisible to the suite — the probe was green on the
    machine where the two bases agree. This runs the same rule directly, at the floors real
    hosts produce, with no timing involved at all.
    """
    budget = PROBE_SPREAD_BUDGET_SECONDS
    # The tightest legal shape at the moment of failure: the fastest case sits exactly on the
    # floor (`min(medians) >= floor` is asserted before the spread is read) and the spread has
    # just crossed the budget. Some case is therefore a full budget past the floor.
    medians = {"unknown": floor, "verified": floor, "unverified": floor + budget * 1.001}
    spread = max(medians.values()) - min(medians.values())
    assert spread >= budget, "premise: this fixture must be a FAILING spread, or it pins nothing"

    outgrew = cases_outgrowing_floor(medians, floor)
    assert outgrew == ["unverified"], (
        f"at a {floor * 1000:.0f}ms floor the probe judged a {spread * 1000:.1f}ms spread to "
        f"be over its {budget * 1000:.0f}ms budget, yet its diagnosis did not name the case "
        f"sitting that same {budget * 1000:.0f}ms past the floor (got {outgrew}). Verdict and "
        f"diagnosis are on different bases, so the failure message will claim the difference "
        f"arose INSIDE the padded window when the padding was in fact outrun."
    )

    # POSITIVE CONTROL. Without this the assertion above is satisfied by a rule that flags
    # every case unconditionally — "outgrew" would be indistinguishable from a dead rule that
    # always fires, and the message would misdiagnose in the opposite direction instead.
    settled = {"unknown": floor, "verified": floor + budget * 0.4, "unverified": floor + budget * 0.9}
    assert max(settled.values()) - min(settled.values()) < budget, (
        "premise: this fixture must be a PASSING spread, or the control below proves nothing"
    )
    assert cases_outgrowing_floor(settled, floor) == [], (
        f"at a {floor * 1000:.0f}ms floor three cases that all sat within the spread budget "
        f"of the floor were reported as having outgrown it "
        f"({cases_outgrowing_floor(settled, floor)}); the rule fires unconditionally and "
        f"diagnoses nothing"
    )


def test_one_calibration_spike_cannot_set_the_probes_floor():
    """`max` provisions the floor, and `max` cannot tell a slow host from one stalled sample.

    WHY THIS MATTERS BEYOND AN OVER-SIZED FLOOR. The floor is only the first thing derived
    from the calibration basis; the second is the recalibration escape hatch, which skips the
    probe when the branch it calibrated from no longer fits inside its own floor. That
    threshold is `basis * PROBE_FLOOR_MULTIPLE`. Inflate the basis with a spike and the escape
    hatch rises with it, so the ONE benign explanation for a red becomes least reachable
    exactly on the noisy hosts where it is most likely to be the true one. A performance
    reviewer identified that as the mechanism behind the false reds on unmodified code.

    The clamp must therefore bite on a spike and stay out of the way otherwise — a slow host
    is a real measurement and must still raise the floor.
    """
    # A spike: three honest samples around 300ms, one stalled sample 4x that.
    basis, observed, typical, spiked = calibration_basis([0.30, 0.31, 0.29, 1.20])
    assert spiked, (
        f"a 1200ms sample among ~300ms ones was accepted as the machine's honest worst case "
        f"(basis {basis * 1000:.0f}ms, median {typical * 1000:.0f}ms); one stalled sample "
        f"still sets the floor and inflates the recalibration escape hatch with it"
    )
    assert basis < observed, "the clamp reported itself as binding but did not lower the basis"
    assert basis == pytest.approx(typical * PROBE_CALIBRATION_SPIKE_RATIO), (
        "a bound basis must be the median-derived clamp, not some other number"
    )

    # POSITIVE CONTROL — a genuinely slow host, where every sample moved together. The clamp
    # MUST NOT bind here: without this the assertions above are satisfied by a clamp that
    # always fires, which would cap the floor on real slow hardware and reintroduce the
    # optimistic-floor false red the `max` was chosen to prevent in the first place.
    basis, observed, typical, spiked = calibration_basis([1.15, 1.20, 1.18, 1.22])
    assert not spiked, (
        f"four samples within 7% of each other were treated as a spike (basis "
        f"{basis * 1000:.0f}ms vs observed {observed * 1000:.0f}ms); the clamp fires "
        f"unconditionally and a genuinely slow host would be given a floor too low for it"
    )
    assert basis == observed == 1.22, "an unspiked calibration must keep its measured maximum"


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


def test_the_degraded_ceiling_is_spent_whether_or_not_the_account_exists(settings, limiter_down):
    """The fallback ceiling must not become an account-existence oracle.

    While the store is down this ceiling is the only thing rationing mail, and it is SHARED
    across callers. If it were charged only to calls that actually send, an attacker holding
    one unverified account of their own could read one bit of state off any address: probe the
    target once, then spend the rest of the ceiling on their own address and count what
    arrives. A target that was eligible consumed a unit; a target that was not, did not. One
    request per target, no guessing.

    `resend_email_verification`'s own docstring already forbids exactly this for the three
    real budgets — "a limiter that only bit for real accounts would itself be the oracle this
    function exists to avoid" — so the fallback that stands in for them has to behave the same
    way. It costs something real: during an outage a flood of probes can starve legitimate
    resends. That is the trade the global budget already makes, and it is the cheaper side.
    """
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (2, 60)
    captured = CapturingSender()
    services.set_email_sender(captured)
    try:
        _make_user("real@oracle.example", tag="oracle-real")
        _make_user("done@oracle.example", verified=True, tag="oracle-done")

        # POSITIVE CONTROL, and THE WINDOW IS PINNED HERE rather than in the `limiter_down`
        # fixture. Both halves of that are load-bearing, and neither is defensive tidiness:
        #
        # The contract below is a pure negative — "nothing was sent". A ceiling that arrives
        # already drained satisfies it for free, and then the test passes whether or not the
        # non-sending probes were charged, which is the whole property it exists to pin. The
        # window is process-global module state, so "already drained" is not hypothetical: any
        # earlier test in the file that leaves it spent has that effect. It was reachable by
        # deleting ONE line from a fixture that does not mention this test — at which point the
        # account-existence oracle this guards against reappeared with the whole file green,
        # 25 passed, exit 0. Verified before this rework, and again after it.
        #
        # So the premise is established here, in the test, at the point it is relied on: with a
        # fresh window the eligible address really does send. That makes the negative below
        # mean "refused because the probes spent the ceiling" instead of the untestable
        # "refused, for some reason, possibly that the mechanism is dead".
        services._reset_degraded_send_window()
        with TestCase.captureOnCommitCallbacks(execute=True):
            assert services.resend_email_verification(
                services.ResendVerificationData(
                    email="real@oracle.example", client_ip="10.0.0.9"
                )
            ).accepted is True
        assert len(captured.verify_tokens) == 1, (
            f"the positive control did not send ({len(captured.verify_tokens)} sends): with a "
            f"fresh ceiling an eligible address must still be delivered to during an outage. "
            f"Either the ceiling arrived already spent or the degraded path refuses "
            f"everything — either way the negative assertion below is satisfied for free and "
            f"the account-existence property it names went unexercised"
        )

        # Now the actual question, from a window pinned the same way for the same reason.
        services._reset_degraded_send_window()
        sends_before = len(captured.verify_tokens)
        with TestCase.captureOnCommitCallbacks(execute=True):
            # Two addresses that can never send: one unknown, one already verified. If the
            # ceiling only bit for real accounts these would cost nothing at all.
            for address in ("ghost@oracle.example", "done@oracle.example"):
                assert services.resend_email_verification(
                    services.ResendVerificationData(email=address, client_ip="10.0.0.9")
                ).accepted is True

            # The ceiling is now spent, so the one address that COULD send must not — and the
            # control above has already established that it otherwise would.
            assert services.resend_email_verification(
                services.ResendVerificationData(
                    email="real@oracle.example", client_ip="10.0.0.9"
                )
            ).accepted is True

        assert captured.verify_tokens[sends_before:] == [], (
            "two non-sending probes did not spend the degraded ceiling, so its depletion "
            "tracks whether an address was eligible — an account-existence oracle readable "
            "from the attacker's own inbox"
        )
    finally:
        services.set_email_sender(services.EmailSender())


def test_a_healthy_limiter_never_engages_the_degraded_ceiling(settings, sender):
    """The fallback must stay out of the way while the store is UP.

    This is the negative half of the two tests above, and without it they are satisfied by a
    fallback that is ALWAYS on. If `enforce_budget_reporting_outage` ever reported a fail-open
    against a healthy limiter — a wrong return, a swapped enum member, an inverted check —
    every resend in normal operation would be rationed by this per-worker fallback instead of
    the real budgets, silently capping ALL verification mail at the fallback's rate with no
    error raised and nothing logged. Both outage tests run with the store down, so they pass
    either way and cannot see it.

    The ceiling here is set to 1: if the degraded path engaged at all, only the first of the
    three sends would leave.
    """
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (1, 3600)
    settings.SELAHCUE_THROTTLE_RESEND_ADDRESS = (10, 900)
    services._reset_degraded_send_window()

    with TestCase.captureOnCommitCallbacks(execute=True):
        for i in range(3):
            _make_user(f"healthy{i}@limiter.example", tag=f"h{i}")
            assert services.resend_email_verification(
                services.ResendVerificationData(
                    email=f"healthy{i}@limiter.example", client_ip="10.0.0.8"
                )
            ).accepted is True

    assert len(sender.verify_tokens) == 3, (
        f"the degraded ceiling engaged while the limiter was HEALTHY: only "
        f"{len(sender.verify_tokens)} of 3 sends left. A fail-open misreported on a working "
        f"store would cap all resend mail at the fallback ceiling in normal operation."
    )


# --- a PARTIAL outage: three budgets, three keys, three independent failures -------------
class _SelectivelyBrokenStore:
    """Down for ONE scope, healthy for the others.

    `_BrokenStore` above fails every key at once, which is the easy case and not the likely
    one. The three budgets are three different keys, and a real store fails per key: a hot
    shard, one evicted slot, a key whose value went unparseable. Every test on this path used
    the all-or-nothing store, so nothing here had ever seen a partial outage.
    """

    def __init__(self, broken_scope):
        self.broken_scope = broken_scope
        self.counts = {}

    def incr_with_expiry(self, key, window_seconds):
        if key.startswith(f"throttle:{self.broken_scope}:"):
            raise RuntimeError(f"redis is down for {self.broken_scope}")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def spent(self, scope):
        return sum(n for key, n in self.counts.items() if key.startswith(f"throttle:{scope}:"))


@pytest.fixture
def partial_outage(monkeypatch):
    """Install a store that is down for exactly one of the three resend scopes."""
    from selahcue_api.apps.throttling import guards

    def _install(broken_scope):
        store = _SelectivelyBrokenStore(broken_scope)
        monkeypatch.setattr(guards, "CacheStore", lambda _cache: store)
        services._reset_floor_overrun_reporting()
        services._reset_degraded_send_window()
        return store

    return _install


@pytest.mark.parametrize(
    "broken_scope", ["resend_verify", "resend_verify_ip", "resend_verify_addr"]
)
def test_an_outage_on_any_one_of_the_three_budgets_degrades_the_send(
    settings, partial_outage, broken_scope
):
    """Each budget's fail-open must be reported, not just the first one's.

    `limiter_degraded` accumulates with `|=` across three separate statements precisely so
    that a fail-open ANYWHERE is carried to the send path. Collapse it to one budget — keep
    the global and drop the other two, an entirely natural simplification — and an outage
    confined to the per-address or per-IP key stops degrading the send while still failing
    open. The endpoint then has no ceiling at all for that key, which is the unmetered,
    unauthenticated send path this whole mechanism exists to prevent.

    Nothing covered this: every other test on this path uses a store that fails all three keys
    at once, and under that store keeping only the global budget passes everything.
    """
    store = partial_outage(broken_scope)
    # Exhausted on arrival, so "was the outage noticed?" is the only question left: a noticed
    # outage sends nothing, an unnoticed one sends normally.
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (0, 60)
    captured = CapturingSender()
    services.set_email_sender(captured)
    try:
        _make_user(f"partial-{broken_scope}@degrade.example", tag=f"p-{broken_scope}")

        with TestCase.captureOnCommitCallbacks(execute=True):
            assert services.resend_email_verification(
                services.ResendVerificationData(
                    email=f"partial-{broken_scope}@degrade.example", client_ip="10.0.0.7"
                )
            ).accepted is True

        # The hit first: prove this call really did reach the store for the scopes that were
        # UP, so a red below means "the outage was not noticed" and not "the store was never
        # consulted and nothing was exercised".
        healthy = [s for s in ("resend_verify", "resend_verify_ip", "resend_verify_addr")
                   if s != broken_scope]
        for scope in healthy:
            assert store.spent(scope) == 1, (
                f"{scope} was not spent, so this call did not exercise the three-budget path "
                f"at all and the outage assertion below pins nothing"
            )

        assert captured.verify_tokens == [], (
            f"an outage confined to the {broken_scope} budget failed open without degrading "
            f"the send, so that budget bounded nothing while it was down. An unauthenticated "
            f"mail endpoint had no ceiling on that key for the length of the outage"
        )
    finally:
        services.set_email_sender(services.EmailSender())


def test_a_degraded_budget_does_not_stop_the_later_budgets_being_spent(settings, partial_outage):
    """The accumulation must never short-circuit — the code comment forbids `or` and nothing
    checked it.

    `a or b or c` stops evaluating at the first truthy operand. Since a fail-open returns True,
    writing the accumulation that way means an outage on the FIRST budget silently stops the
    per-IP and per-address budgets being spent at all — while their store is perfectly
    healthy. The endpoint would then be rate-limited by nothing but a global key that is
    already down, and one address could be flooded without limit.

    This is invisible to every other test here: with the all-or-nothing store there are no
    later budgets left to skip, so `or` and `|=` behave identically and both pass.

    Only the GLOBAL store is broken. The per-address budget is healthy, small, and must still
    bite.
    """
    store = partial_outage("resend_verify")
    settings.SELAHCUE_THROTTLE_RESEND_ADDRESS = (2, 900)
    # Generous: this test is about the budgets being SPENT, not about the fallback ceiling.
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (100, 3600)
    _make_user("shortcircuit@partial.example", tag="short-circuit")

    def call():
        return services.resend_email_verification(
            services.ResendVerificationData(
                email="shortcircuit@partial.example", client_ip="10.0.0.6"
            )
        )

    for _ in range(2):
        assert call().accepted is True

    # The hit, before the contract: the per-address budget must actually have been reached.
    # Under `or` this reads 0 and the RATE_LIMITED below never arrives.
    assert store.spent("resend_verify_addr") == 2, (
        f"the per-address budget was spent {store.spent('resend_verify_addr')} times across "
        f"two calls: an outage on the global budget short-circuited the accumulation, so the "
        f"later budgets were never spent and the address key bounded nothing while its own "
        f"store was healthy"
    )

    with pytest.raises(SafeAPIError) as exhausted:
        call()
    assert exhausted.value.code is ErrorCode.RATE_LIMITED, (
        "a healthy per-address budget must still refuse past its limit while a different "
        "budget's store is down"
    )


def test_the_degraded_window_rolls_over_so_one_outage_does_not_stop_mail_for_good(settings):
    """The ceiling is a fixed window and must actually roll.

    Drop the rollover branch and the ceiling is spent once per PROCESS, not once per window:
    the first N sends of the first outage exhaust it and this worker sends no verification
    mail again until it is restarted — including long after the store has recovered, because
    nothing on the healthy path ever resets it. That is a permanent, silent loss of a
    self-service recovery route, and it survives the outage that caused it.
    """
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (1, 0.05)
    services._reset_degraded_send_window()

    assert services._claim_degraded_send() is True, (
        "the first claim in a fresh window was refused, so the ceiling is dead rather than "
        "bounding and the rollover below would prove nothing"
    )
    assert services._claim_degraded_send() is False, (
        "a second claim inside the same window was granted against a ceiling of 1 — the "
        "window is not bounding anything"
    )

    time.sleep(0.08)  # comfortably past the 50ms window

    assert services._claim_degraded_send() is True, (
        "the window never rolled over: the ceiling is spent once per process, so this worker "
        "would send no verification mail again until restarted — long after the outage that "
        "spent it had ended"
    )


def test_the_degraded_ceiling_setting_and_module_default_have_not_drifted():
    """The shipped setting and the module fallback must agree.

    Same guard as the floor's, for the same reason and after the same accident: this file's
    timing probe went wrong because a settings value and a module default were allowed to
    drift while a test pinned the stale one. `getattr(settings, ..., DEFAULT)` means a
    deployment that never sets the setting silently runs the module value, so the two being
    different is a difference nobody would see.
    """
    assert PRODUCTION_DEGRADED_CEILING == services.RESEND_DEGRADED_SEND_CEILING, (
        "settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING and "
        "services.RESEND_DEGRADED_SEND_CEILING have drifted; the fallback must not be "
        "quietly different from the shipped ceiling"
    )


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
