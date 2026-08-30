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
    2  the client sources could not be read

WHAT IS AND IS NOT AUTHORITATIVE HERE
-------------------------------------
The whitespace half is fully authoritative: `str.strip()` is CPython's own answer and this
script asks it directly.

The email half is not, unless Django is installed. `EMAIL_FIXTURES` carries a verdict
column, and this script checks it two ways:

  - against Django's REAL `validate_email`, when `django` imports. That is the authority,
    and it is what makes the fixture column evidence rather than assertion.
  - otherwise against a transcription of Django 6.1's `EmailValidator` regexes, printed
    with a loud notice that the real validator was not available. The transcription is
    checked against the four verdicts obtained from real Django during the PR #17 review
    (`a@b.c`, `a@b..com`, `a@-b.com`, `a@b-.com` are all REJECTED), so a transcription
    that has silently drifted from Django fails those.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETING = HERE.parent
SERVICE_TEXT_TS = MARKETING / "src" / "lib" / "auth" / "serviceText.ts"
EMAIL_FIXTURES = MARKETING / "tests" / "fixtures" / "email-mirror.json"


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


def fmt(code_points: list[int]) -> str:
    return " ".join(f"U+{cp:04X}" for cp in code_points)


# -------------------------------------------------------------------------- email ---
# Django 6.1 `django/core/validators.py::EmailValidator`, transcribed. Used ONLY when the
# real Django is not importable; see the module docstring.
_USER_RE = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*\Z"
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"\Z)',
    re.IGNORECASE,
)
_DOMAIN_RE = re.compile(
    r"((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+)(?:[A-Z]{2,63}|[A-Z0-9-]{2,63}(?<!-))\Z",
    re.IGNORECASE,
)
_LITERAL_RE = re.compile(r"\[([A-F0-9:.]+|\[IPv6:[a-f0-9:.]+\])\]\Z", re.IGNORECASE)
_ALLOWLIST = ("localhost",)


def transcribed_is_valid(value: str) -> bool:
    if not value or "@" not in value:
        return False
    user, _, domain = value.rpartition("@")
    if not _USER_RE.match(user):
        return False
    if domain in _ALLOWLIST:
        return True
    if _DOMAIN_RE.match(domain):
        return True
    return bool(_LITERAL_RE.match(domain))


def real_django_is_valid(value: str):
    """Django's own verdict, or None when Django is not installed."""
    try:
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email
    except Exception:
        return None
    try:
        validate_email(value)
        return True
    except ValidationError:
        return False


def normalize(raw: str) -> str:
    """`_normalize_email` (services.py:484): `(raw or "").strip().lower()`."""
    return (raw or "").strip().lower()


def check_email() -> bool:
    if not EMAIL_FIXTURES.is_file():
        print(f"FAIL: no fixture file at {EMAIL_FIXTURES}")
        raise SystemExit(2)
    fixtures = json.loads(EMAIL_FIXTURES.read_text(encoding="utf-8"))["cases"]

    using_real = real_django_is_valid("probe@example.com") is not None
    if using_real:
        print("     using the REAL django.core.validators.validate_email")
    else:
        print("!!   django is NOT installed here — using the transcribed EmailValidator.")
        print("!!   The verdict column is only as good as the transcription; the four")
        print("!!   real-Django verdicts recorded on PR #17 are checked below as a control.")

    ok = True
    for case in fixtures:
        raw = case["address"]
        expected = case["serverAccepts"]
        actual = (
            real_django_is_valid(normalize(raw))
            if using_real
            else transcribed_is_valid(normalize(raw))
        )
        if actual != expected:
            ok = False
            print(
                f"FAIL email mirror: {raw!r} — fixture says serverAccepts={expected}, "
                f"the server says {actual}"
            )

    # The control on the transcription itself, from real-Django verdicts obtained
    # independently during the PR #17 review. These must be rejected however the verdict
    # is computed; if the transcription drifts to accept them, this fires.
    for address in ("a@b.c", "a@b..com", "a@-b.com", "a@b-.com"):
        verdict = (
            real_django_is_valid(address) if using_real else transcribed_is_valid(address)
        )
        if verdict is not False:
            ok = False
            print(f"FAIL the reject-control for {address!r} did not hold (got {verdict})")

    if ok:
        print(f"OK   email: {len(fixtures)} fixtures agree with the server's verdict")
    return ok


def main() -> int:
    print("Re-deriving the client/server mirrors from the runtimes that decide.\n")
    results = [check_whitespace(), check_email()]
    print()
    if all(results):
        print("ALL MIRRORS AGREE")
        return 0
    print("A MIRROR HAS DRIFTED — fix the client, or re-derive the pinned constant.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
