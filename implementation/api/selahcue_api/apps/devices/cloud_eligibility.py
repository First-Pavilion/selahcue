"""Pure eligibility of the exact device, licence and token behind a cloud demand."""
from dataclasses import dataclass
from datetime import datetime

from selahcue_api.apps.license_keys.selection import aware_utc, license_window_allows_service


@dataclass(frozen=True, slots=True)
class CloudEligibilityFacts:
    org_id: int
    org_status: str
    license_id: int
    license_org_id: int
    license_status: str
    license_starts_at: datetime
    license_expires_at: datetime
    device_id: int
    device_org_id: int
    device_license_id: int
    device_status: str
    token_id: int
    token_device_id: int
    token_status: str
    token_issued_at: datetime
    token_expires_at: datetime


def cloud_eligibility(facts: CloudEligibilityFacts, *, at: datetime) -> bool:
    now = aware_utc(at)
    ids = (
        facts.org_id, facts.license_id, facts.license_org_id, facts.device_id,
        facts.device_org_id, facts.device_license_id, facts.token_id, facts.token_device_id,
    )
    return (
        all(type(value) is int and value > 0 for value in ids)
        and facts.org_id == facts.license_org_id == facts.device_org_id
        and facts.license_id == facts.device_license_id
        and facts.device_id == facts.token_device_id
        and facts.org_status in ("PROSPECT", "TRIAL", "ACTIVE", "PAST_DUE")
        and facts.device_status == facts.token_status == "ACTIVE"
        and facts.token_issued_at <= now < facts.token_expires_at
        and license_window_allows_service(
            status=facts.license_status, starts_at=facts.license_starts_at,
            expires_at=facts.license_expires_at, at=now,
        )
    )
