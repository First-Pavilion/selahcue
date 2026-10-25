"""`CustomerOrg.device_limit` is gone, and nothing can quietly bring a second limit back (86ak5mn0m).

Before this change two fields were called `device_limit`. The org's was written at sign-up and
returned by the admin console but never consulted by activation; the licence key's was the
only one anything enforced. An org holding two keys therefore had a capacity equal to the SUM of
its keys' limits, and the console showed a number that meant nothing.

The decision (architect, approved by the owner) was to remove the org field rather than give it
a job: with at most one valid key per org there is nothing for an org-level cap to compare
against, and keeping it would mean three copies of one number (the catalogue's
`device_instances`, the key's `device_limit`, and the org's).

These are tripwires. Re-adding the field, or letting a staff caller type a seat count again,
fails here with the reason written down.
"""

from __future__ import annotations

import dataclasses

import pytest
from django.core.exceptions import FieldDoesNotExist

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.accounts.services import CreateCustomerData
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.license_keys.services import GenerateLicenseKeyData

# These tests read no rows. The mark is for the suite's autouse session fixtures
# (`conftest._catalogue_reference_snapshot` reads the catalogue tables), which need a built
# test database even when no test in the run touches one; without it this file errors on its
# own with "no such table" and only passes when another file happens to have built the DB.
pytestmark = pytest.mark.django_db


def test_the_org_model_has_no_device_limit_field():
    with pytest.raises(FieldDoesNotExist):
        CustomerOrg._meta.get_field("device_limit")


def test_the_licence_key_still_carries_the_one_device_limit():
    """POSITIVE CONTROL. The tripwire above would pass just as well if `get_field` were
    broken for every name; this shows the same lookup finds the field that must remain."""
    assert AppLicenseKey._meta.get_field("device_limit").name == "device_limit"


def test_creating_an_org_takes_no_device_limit():
    names = {field.name for field in dataclasses.fields(CreateCustomerData)}
    assert "device_limit" not in names, (
        "staff can type an org-level device limit again; nothing enforces it"
    )
    # POSITIVE CONTROL: the dataclass introspection finds a field that does exist.
    assert "name" in names


def test_issuing_a_key_takes_no_device_limit_from_staff():
    """The key's limit comes from the plan (see `test_key_seats_from_plan.py`). A staff-typed
    number beside it is how a licence ended up displayed as one thing and enforced as another."""
    names = {field.name for field in dataclasses.fields(GenerateLicenseKeyData)}
    assert "device_limit" not in names, (
        "staff can type a licence's device limit again, so it can contradict its plan"
    )
    assert "plan_code" in names  # POSITIVE CONTROL, as above.
