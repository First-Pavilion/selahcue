#!/usr/bin/env python3
"""Re-derive the Python halves of the client/server mirrors, from CPython and from Django.

This repository has now had FOUR client/server predicate mirrors drift apart in one week.
The failure mode is always the same: a TypeScript function claims to reproduce a Python
one, a test pins the claim with fixtures drawn from the region where the two already
agree, and the divergence lives outside the sample.

So the Python side is not transcribed by hand and trusted. It is re-derived here, from the
runtime that actually decides, and compared against the constants the TypeScript consumes.
Run this whenever either side changes:

    python3 implementation/marketing/scripts/service_text_reference.py

Exit codes:
    0  every re-derived value matches what the client pins
    1  a mirror has drifted — the message says which, and in which direction
    2  the check could not be performed — a missing or wrong-version Django included,
       because "could not check" must never share an exit code with "checked and agreed"
       (see "NOTHING HERE FALLS BACK, AND NOTHING HERE SKIPS BY DEFAULT" below)

WHAT THIS SCRIPT LEARNED THE HARD WAY
-------------------------------------
Its first version got the email half wrong in three compounding ways, and all three are
fixed structurally rather than by correcting the data:

1. IT TRANSCRIBED THE WRONG DJANGO. The pin is `Django>=6.1,<6.2`, but the pattern
   transcribed was Django <= 5.1's; 5.2 rebuilt `EmailValidator.domain_regex` on
   `DomainNameValidator`. So `a@b.12` and `a@b.-xy` were recorded as server-ACCEPTED when
   6.1 rejects both. FIXED BY: `check_django_matches_the_pin`, which reads the pin out of
   `implementation/api/pyproject.toml` and refuses to certify anything with a Django that
   does not satisfy it. Getting the version wrong is now a failure, not a silent premise.

2. THE SECOND CONSUMER WAS NOT INDEPENDENT. This script "checked" the fixture column
   against a transcription of the same regex the client had — the same wrong rule, typed
   twice — whenever Django was not importable, which is what actually ran. It agreed with
   itself and printed OK. FIXED BY: nothing here computes a verdict from a copy, ever. See
   below.

3. THE CONTROL CASES SAT INSIDE THE AGREEING REGION. The four addresses pinned as proof
   the transcription was faithful (`a@b.c`, `a@b..com`, `a@-b.com`, `a@b-.com`) are all
   inputs where the wrong rule and real Django agree, so they could never have detected the
   error — which is verbatim the failure this docstring says the script exists to prevent.
   FIXED BY: `check_fixture_escapes_the_agreeing_region`, which makes "these rows
   discriminate" a machine-checked property instead of a hope.

NOTHING HERE FALLS BACK, AND NOTHING HERE SKIPS BY DEFAULT
----------------------------------------------------------
There is no transcribed validator in this file any more. It never substitutes a second copy
of the client's rule, because a copy agrees with the thing it was copied from and converts
"unverified" into "verified" with no visible change.

A missing Django is therefore a FAILURE (exit 2), not a skip. That default is the point.
The first version of this file skipped by default and said so loudly — and the loud banner
still exited 0, so `npm run test:mirrors` printed a wall of warnings and then reported
success to a developer who had verified nothing about the email rule. Root cause #2 was not
that the fallback was quiet; it was that "we could not check" and "we checked" were the same
exit code. A safe default is the only version of that fix which does not depend on every
caller remembering to pass a flag.

    SELAHCUE_MIRRORS_ALLOW_SKIP=1   the deliberate opt-out: run the whitespace half alone,
                                    still print the banner, exit 0. For someone who knows
                                    they have no Django and wants the other mirror checked.
    SELAHCUE_MIRRORS_REQUIRE=1      belt and braces: fail even if ALLOW_SKIP is also set.
                                    CI sets this so a stray environment variable on a runner
                                    cannot silently downgrade the gate.

Same shape as `SELAHCUE_HEADLESS_REQUIRE=1` in `auth_pages_headless.py` — with the default
on the other side, because a browser has to be installed and a pip package does not.

To run the email half you need the pinned Django in this interpreter:

    uv venv --python 3.12 /tmp/djenv
    uv pip install --python /tmp/djenv/bin/python 'Django>=6.1,<6.2'
    /tmp/djenv/bin/python implementation/marketing/scripts/service_text_reference.py

THE ONE PRE-5.2 PATTERN THAT REMAINS, AND WHY IT IS NOT AN AUTHORITY
--------------------------------------------------------------------
`PRE_5_2_DOMAIN_RE` is the regex this script used to trust. It is kept for exactly one
purpose: to be DISAGREED WITH. `check_fixture_escapes_the_agreeing_region` asserts the
fixture set contains rows where it and real Django return different answers — one per
divergence class the review found.

It is never consulted to decide whether an address is valid: `django_verdict` is the only
function in this file that answers that question, and it calls Django. `pre_5_2_verdict` is
referenced from exactly one place — the escape check — and `tests/emailPolicy.test.ts`
asserts that stays true, so wiring it back into a validation path is a failing test rather
than a thing a reader has to notice.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETING = HERE.parent
REPO = MARKETING.parent.parent
SERVICE_TEXT_TS = MARKETING / "src" / "lib" / "auth" / "serviceText.ts"
EMAIL_FIXTURES = MARKETING / "tests" / "fixtures" / "email-mirror.json"
EMAIL_PROBE_TS = HERE / "email_mirror_probe.ts"
API_PYPROJECT = REPO / "implementation" / "api" / "pyproject.toml"


def fmt(code_points: list[int]) -> str:
    return " ".join(f"U+{cp:04X}" for cp in code_points)


# --------------------------------------------------------------------- whitespace ---
def derive_python_whitespace() -> list[int]:
    """Exactly what `str.strip()` and `str.split()` treat as whitespace."""
    return [cp for cp in range(0x110000) if chr(cp).strip() == "" and chr(cp) != ""]


def pinned_whitespace() -> list[int]:
    """The `PYTHON_WHITESPACE` array the TypeScript exports, read out of the source."""
    text = SERVICE_TEXT_TS.read_text(encoding="utf-8")
    match = re.search(r"PYTHON_WHITESPACE:\s*readonly number\[\]\s*=\s*\[(.*?)\]", text, re.S)
    if not match:
        print(f"FAIL: could not find PYTHON_WHITESPACE in {SERVICE_TEXT_TS}")
        raise SystemExit(2)
    return [int(token, 16) for token in re.findall(r"0x[0-9a-fA-F]+", match.group(1))]


def check_whitespace() -> bool:
    derived = derive_python_whitespace()
    pinned = pinned_whitespace()
    if derived == pinned:
        print(f"OK   whitespace: {len(derived)} code points, client pin matches CPython exactly")
        return True
    only_python = sorted(set(derived) - set(pinned))
    only_client = sorted(set(pinned) - set(derived))
    print("FAIL whitespace mirror has drifted")
    if only_python:
        print("     CPython strips these and the client does not: " + fmt(only_python))
    if only_client:
        print("     the client strips these and CPython does not: " + fmt(only_client))
    return False


# ------------------------------------------------------------------ the pinned Django ---
def declared_django_pin() -> str:
    """The `Django>=6.1,<6.2` line from the API's pyproject, read rather than remembered."""
    text = API_PYPROJECT.read_text(encoding="utf-8")
    # Anchored on a requirement specifier, not on the word "Django": the project
    # DESCRIPTION in the same file begins "Django and Strawberry Platform API…", and a
    # looser pattern reads that as the pin and dies confusingly.
    match = re.search(r'"Django\s*(?P<spec>(?:[<>=!~]=?[^",]+)(?:,[^"]*)?)"', text)
    if not match:
        print(f"FAIL: no Django version pin found in {API_PYPROJECT}")
        raise SystemExit(2)
    return match.group("spec").strip()


def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text))


def satisfies(version: str, spec: str) -> bool:
    """Enough of PEP 440 for `>=6.1,<6.2`, which is the only shape this pin has ever had."""
    for clause in (piece.strip() for piece in spec.split(",") if piece.strip()):
        match = re.match(r"(?P<op>>=|<=|==|<|>)\s*(?P<version>[\d.]+)", clause)
        if not match:
            print(f"FAIL: cannot interpret the Django pin clause {clause!r}")
            raise SystemExit(2)
        op, want = match.group("op"), version_tuple(match.group("version"))
        have = version_tuple(version)[: len(want)] if op in ("<", ">=") else version_tuple(version)
        if op == ">=" and not have >= want:
            return False
        if op == "<" and not version_tuple(version)[: len(want)] < want:
            return False
        if op == "<=" and not have <= want:
            return False
        if op == ">" and not have > want:
            return False
        if op == "==" and have != want:
            return False
    return True


def check_django_matches_the_pin(version: str) -> bool:
    """Root cause #1, made into a gate.

    A verdict column derived from the wrong Django is worse than no column, because it
    looks exactly like a right one. The transcription this replaces was Django <= 5.1's and
    was labelled 6.1 in two files.
    """
    spec = declared_django_pin()
    if satisfies(version, spec):
        print(f"     Django {version} installed, and it satisfies the API's pin ({spec})")
        return True
    print(
        f"FAIL the installed Django is {version}, which does NOT satisfy the API's pin "
        f"({spec} in {API_PYPROJECT}).\n"
        "     Django rebuilt EmailValidator.domain_regex on DomainNameValidator in 5.2, so "
        "a column\n"
        "     derived from the wrong side of that boundary is confidently wrong. Install the "
        "pinned version."
    )
    return False


# ---------------------------------------------------------------- the email verdicts ---
def real_django_is_valid(value: str) -> bool:
    """Django's own verdict. The ONLY authority in this file for what the server accepts."""
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    try:
        validate_email(value)
        return True
    except ValidationError:
        return False


def normalize(raw: str) -> str:
    """`_normalize_email` (services.py:484): `(raw or "").strip().lower()`."""
    return (raw or "").strip().lower()


def django_verdict(raw: str) -> bool:
    return real_django_is_valid(normalize(raw))


# ------------------------------------------------------------- the discriminator only ---
# Django <= 5.1's `EmailValidator.domain_regex`, the pattern this script used to treat as
# the answer. It is NOT consulted to validate anything. Its only job is to be disagreed
# with, so that `check_fixture_escapes_the_agreeing_region` can prove the fixture rows sit
# where the old rule and the real one differ.
PRE_5_2_DOMAIN_RE = re.compile(
    r"((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+)(?:[A-Z]{2,63}|[A-Z0-9-]{2,63}(?<!-))\Z",
    re.IGNORECASE,
)
PRE_5_2_USER_RE = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*\Z"
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"\Z)',
    re.IGNORECASE,
)
# Note the SHAPE-ONLY literal branch and the invented `[IPv6:` alternative — both were in
# the client too, and both are divergence classes the fixture must now cover.
PRE_5_2_LITERAL_RE = re.compile(r"\[([A-F0-9:.]+|\[IPv6:[a-f0-9:.]+\])\]\Z", re.IGNORECASE)


def pre_5_2_verdict(raw: str) -> bool:
    """What the OLD, WRONG mirror said. Used only as a discriminator."""
    value = normalize(raw)
    if not value or "@" not in value:
        return False
    user, _, domain = value.rpartition("@")
    if not PRE_5_2_USER_RE.match(user):
        return False
    if domain == "localhost":
        return True
    if PRE_5_2_DOMAIN_RE.match(domain):
        return True
    return bool(PRE_5_2_LITERAL_RE.match(domain))


# The divergence classes the PR #17 review round found, each named by the reviewer who
# found it. Every one of these must have at least one fixture row on which the OLD rule and
# real Django DISAGREE — that is what "chosen outside the agreeing region" means as a
# checkable property rather than an intention.
DIVERGENCE_CLASSES: dict[str, str] = {
    "digit-in-tld": "Cody: Django 6.1's TLD class has no digits (a@b.12, a@b.c0m)",
    "leading-hyphen-tld": "Cody: a leading hyphen in the TLD is refused (a@b.-xy)",
    "length-cap": "Cody/Sana: the 320-character RFC 3696 cap, absent from the old mirror",
    "ip-literal-semantics": "Sana: IP literals were shape-checked and never validated",
    "ipv6-tagged-branch": "Sana: a dead `[IPv6:` branch Django has never had",
    "idn-domain": "the lockout this PR introduced: Django 6.1 accepts IDN domains",
    "case-fold-residual": (
        "Quinn: what `.lower()` leaves behind reaches a class that `ul` widened in 6.1 "
        "(a@b.İ lowercases to `i` + U+0307, which the 6.1 TLD class contains and the "
        "pre-5.2 one did not)"
    ),
}


def check_fixture_escapes_the_agreeing_region(fixtures: list[dict]) -> bool:
    """Root cause #3, made into a gate.

    A fixture row only carries evidence if a WRONG implementation could fail it. Rows where
    the old rule and real Django agree cannot distinguish the two no matter how many of them
    there are, and the previous fixture set was made entirely of those.
    """
    covered: dict[str, list[str]] = {name: [] for name in DIVERGENCE_CLASSES}
    for case in fixtures:
        for name in case.get("divergence", []):
            if name in covered:
                covered[name].append(case["address"])

    ok = True
    for name, description in DIVERGENCE_CLASSES.items():
        rows = covered[name]
        if not rows:
            ok = False
            print(f"FAIL no fixture row covers the divergence class {name!r} — {description}")
            continue

        # And the claim on the row is checked, not taken: the old rule and real Django must
        # actually disagree here. A row mislabelled with a class it does not exercise would
        # otherwise satisfy the coverage check while proving nothing.
        discriminating = [row for row in rows if pre_5_2_verdict(row) != django_verdict(row)]
        if not discriminating:
            ok = False
            print(
                f"FAIL the rows tagged {name!r} do not discriminate: the pre-5.2 rule and "
                f"Django 6.1 AGREE on all of {rows}.\n"
                "     A row inside the agreeing region cannot detect a wrong transcription — "
                "that is the bug this check exists for."
            )
    if ok:
        total = sum(len(rows) for rows in covered.values())
        print(
            f"OK   agreeing region: {total} row(s) across "
            f"{len(DIVERGENCE_CLASSES)} divergence classes, every one of them a row where "
            "the pre-5.2 rule and Django 6.1 give DIFFERENT answers"
        )
    return ok


# ------------------------------------------------------------------- the differential ---
def corpus() -> list[str]:
    """A generated corpus that sweeps the domain far more widely than the fixture file.

    The fixture is the readable, reviewable, per-class record. This is the net: several
    thousand addresses built from the parts that matter plus seeded fuzz, so a divergence
    nobody thought to name still has to survive being looked for.
    """
    import itertools
    import random

    emoji = "\U0001f600"
    # The four code points Python's full-case-folding `re.IGNORECASE` pulls into an ASCII
    # letter class. They belong in the LOCAL part specifically: `ul` already covers them on
    # the domain side, so a domain-only appearance sits inside the agreeing region and
    # proves nothing — which is what the previous corpus did with `ſ` (it appeared only as
    # `"b.ſ"`) and why a 4,908-address differential reported total agreement while the
    # client rejected `ſmith@example.com` and every other address like it.
    folded = "ıſİK"
    locals_ = [
        "a", "pastor", "a+tag", "first.last", '"quoted"', '"a@b"', "a..b", ".a", "a.",
        "josé", "a b", "", "A" * 64, "a" * 65,
        *folded,
        *(f"{ch}mith" for ch in folded),
        *(f"b{ch}lgi" for ch in folded),
        *(f'"{ch}"' for ch in folded),
        *(f'"\\{ch}"' for ch in folded),
    ]
    domains = [
        "b.com", "example.co.uk", "sub.domain.example", "my-church.org", "b", "b.c", "b.12",
        "b.-xy", "b.xy-", "-b.com", "b-.com", "b..com", "b.c0m", "b.1com", "b.com1", "1.com",
        "b1.com", "localhost", "LOCALHOST", "b.xn--p1ai", "b.xn--", "b.xn--0",
        "xn--mnchen-3ya.de", "münchen.de", "éxample.com", "b.cé",
        "例え.テスト", "b.com.", "b.co", "b." + "x" * 63, "b." + "x" * 64,
        ("y" * 63) + ".com", ("y" * 64) + ".com", "b.museum", "b.travel",
        "[192.168.1.1]", "[999.999.999.999]", "[1.2.3]", "[01.2.3.4]", "[::1]", "[::]",
        "[dead:beef::1]", "[1::2::3]", "[IPv6:::1]", "[::ffff:1.2.3.4]", "[::ffff:256.1.1.1]",
        "[g::1]", "[1:2:3:4:5:6:7:8]", "[1:2:3:4:5:6:7:8:9]",
        "[0000:0000:0000:0000:0000:0000:0000:0001]",
        "[00000:0000:0000:0000:0000:0000:0000:0001]", "[1:2:3:4:5:6:7::]", "[1:2:3:4:5:6:7:8::]",
        "[not-an-ip]", "[]", "[1.2.3.4]", "b.co1", "b.c-m", "b.-", "b.--", "b.a-b", "b.a--b",
        # The nested-bracket shape the invented `[IPv6:...]` branch actually matched.
        # Both cases, because the client sees an already-lowercased domain and the
        # uppercase form is what made that branch unreachable rather than merely wrong.
        "[[IPv6:::1]]", "[[ipv6:::1]]", "[IPv6:::1]", "[ipv6:::1]",
        "exam ple.com", "b." + emoji, emoji + ".com", "b.İ", "b.ǅ", "b.K",
        "b.ß", "b.ſ", "b_c.com", "b.com:80", "b.com/", "b.<script>",
    ]

    out = [f"{local}@{domain}" for local, domain in itertools.product(locals_, domains)]
    out += [
        "a@b@c.com", '"a@b"@c.com', "a@", "@b.com", "@", "nobody", "", "  a@b.com  ",
        "a@b.com", "﻿a@b.com", "A@B.COM", "a@b.com\n", "a@b.com\t", "a @b.com",
    ]
    for n in (300, 306, 307, 308, 309, 310, 311, 312, 313):
        out.append("a" * n + "@example.com")
    for n in (61, 62, 63, 64):
        out.append("a@" + "b" * n + ".com")

    rng = random.Random(20260830)
    # `folded` is in the alphabet as well as in the structured rows. The structured rows
    # say "we thought of this"; the fuzz is what catches the thing nobody thought of, and
    # an alphabet missing a character can only ever generate agreement about it. The
    # previous alphabet had no `ı` and no `ſ` in it at all.
    alphabet = "abz09.-@[]:\"\\ " + "é¡￿" + emoji + "xn" + folded
    for _ in range(4000):
        out.append("".join(rng.choice(alphabet) for _ in range(rng.randint(1, 22))))

    seen: set[str] = set()
    unique: list[str] = []
    for address in out:
        if address not in seen:
            seen.add(address)
            unique.append(address)
    return unique


def client_verdicts(addresses: list[str]) -> list[bool] | None:
    """The REAL client module's answers, obtained by running it under Node."""
    with tempfile.TemporaryDirectory() as workdir:
        request = Path(workdir) / "addresses.json"
        response = Path(workdir) / "verdicts.json"
        request.write_text(json.dumps({"addresses": addresses}), encoding="utf-8")
        try:
            done = subprocess.run(
                ["node", str(EMAIL_PROBE_TS), str(request), str(response)],
                capture_output=True,
                text=True,
                cwd=MARKETING,
                timeout=180,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            print(f"FAIL could not run the client half of the differential: {exc}")
            return None
        if done.returncode != 0:
            print(f"FAIL {EMAIL_PROBE_TS.name} exited {done.returncode}:\n{done.stderr[:2000]}")
            return None
        return json.loads(response.read_text(encoding="utf-8"))


def check_differential() -> bool:
    """Drive the same addresses through BOTH runtimes and diff the verdicts.

    This is the check the fixture file cannot be: the curated rows are a record of what was
    reasoned about, and this is a search for what was not. It reports the two directions
    separately because they are different bugs — the client being LOOSER misattributes a
    permanent server rejection to the wrong cause, and the client being STRICTER locks a
    real customer out of every auth surface.
    """
    addresses = corpus()
    theirs = [django_verdict(address) for address in addresses]
    ours = client_verdicts(addresses)
    if ours is None:
        return False
    if len(ours) != len(addresses):
        print(f"FAIL the client returned {len(ours)} verdicts for {len(addresses)} addresses")
        return False

    stricter = [a for a, t, o in zip(addresses, theirs, ours) if t and not o]
    looser = [a for a, t, o in zip(addresses, theirs, ours) if o and not t]
    if not stricter and not looser:
        print(
            f"OK   differential: {len(addresses)} generated addresses, "
            f"{sum(theirs)} accepted by Django, client agrees on every one"
        )
        return True

    print(f"FAIL the client and Django disagree on {len(stricter) + len(looser)} addresses")
    if stricter:
        print(
            f"     CLIENT IS STRICTER on {len(stricter)} — every one of these is a customer "
            "locked out of sign-in, signup, forgot-password and resend:"
        )
        for address in stricter[:15]:
            print(f"       {address!r}")
    if looser:
        print(
            f"     CLIENT IS LOOSER on {len(looser)} — every one of these reaches the server "
            "and comes back as an unattributed VALIDATION_FAILED:"
        )
        for address in looser[:15]:
            print(f"       {address!r}")
    return False


# ------------------------------------------------------------------------ the fixture ---
def load_fixtures() -> dict:
    if not EMAIL_FIXTURES.is_file():
        print(f"FAIL: no fixture file at {EMAIL_FIXTURES}")
        raise SystemExit(2)
    return json.loads(EMAIL_FIXTURES.read_text(encoding="utf-8"))


def regenerate(document: dict) -> None:
    """Rewrite every `serverAccepts` from Django. The reason the file says not to edit by hand."""
    changed = []
    for case in document["cases"]:
        verdict = django_verdict(case["address"])
        if case.get("serverAccepts") != verdict:
            changed.append((case["address"], case.get("serverAccepts"), verdict))
        case["serverAccepts"] = verdict
    EMAIL_FIXTURES.write_text(
        json.dumps(document, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"Rewrote {len(document['cases'])} verdicts from Django into {EMAIL_FIXTURES}")
    for address, was, now in changed:
        print(f"  {address!r}: {was} -> {now}")
    if not changed:
        print("  (no verdict changed)")


def check_email_column(fixtures: list[dict]) -> bool:
    ok = True
    for case in fixtures:
        expected = case["serverAccepts"]
        actual = django_verdict(case["address"])
        if actual != expected:
            ok = False
            print(
                f"FAIL email mirror: {case['address']!r} — fixture says serverAccepts="
                f"{expected}, Django says {actual}"
            )
    if ok:
        print(f"OK   email: {len(fixtures)} fixture verdicts re-derived from Django, all agree")
    return ok


def check_email(version: str) -> bool:
    document = load_fixtures()
    fixtures = document["cases"]
    return all(
        [
            check_django_matches_the_pin(version),
            check_email_column(fixtures),
            check_fixture_escapes_the_agreeing_region(fixtures),
            check_differential(),
        ]
    )


# ------------------------------------------------------------------------------ main ---
def django_version() -> str | None:
    try:
        import django
    except Exception:
        return None
    return django.get_version()


def main() -> int:
    print("Re-deriving the client/server mirrors from the runtimes that decide.\n")
    results = [check_whitespace()]
    email_checked = True

    version = django_version()
    # FAIL CLOSED. The opt-out has to be asked for; the gate does not have to be asked for.
    # `SELAHCUE_MIRRORS_REQUIRE=1` outranks the opt-out so that CI's intent cannot be
    # undone by an environment variable that happens to be set on a runner.
    allowed_to_skip = (
        os.environ.get("SELAHCUE_MIRRORS_ALLOW_SKIP") == "1"
        and os.environ.get("SELAHCUE_MIRRORS_REQUIRE") != "1"
    )

    if version is None:
        email_checked = False
        # The one thing this branch must never do is compute a verdict. See the module
        # docstring: a fallback to a transcription agrees with itself and reports success.
        print("!! " * 20)
        print("!! SKIPPING every email check: django is not importable in this interpreter.")
        print("!! NOTHING was verified about the email mirror — no fallback rule was used,")
        print("!! because a copy of the client's own rule can only ever agree with it.")
        print("!! " * 20)
        if not allowed_to_skip:
            print(
                "\nFAIL: the email mirror could not be checked, and this script does not "
                "report success\n"
                "      for a check it did not perform. Install the pinned Django (see the "
                "module\n"
                "      docstring), or set SELAHCUE_MIRRORS_ALLOW_SKIP=1 to run the "
                "whitespace half alone."
            )
            return 2
        print("SELAHCUE_MIRRORS_ALLOW_SKIP=1 — continuing with the whitespace mirror only.")
    else:
        if "--regenerate" in sys.argv:
            if not check_django_matches_the_pin(version):
                return 2
            regenerate(load_fixtures())
            return 0
        results.append(check_email(version))

    print()
    if not all(results):
        print("A MIRROR HAS DRIFTED — fix the client, or re-derive the pinned constant.")
        return 1
    if not email_checked:
        # Never "ALL MIRRORS AGREE" here. Exactly one mirror was checked, and a summary
        # that does not say so is the same defect in a different place: a run that verified
        # nothing about the email rule, reading as a run that verified everything.
        print("THE WHITESPACE MIRROR AGREES. THE EMAIL MIRROR WAS NOT CHECKED AT ALL.")
        return 0
    print("ALL MIRRORS AGREE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
