"""The active licence selector shared by session activation and the catalogue."""

from datetime import UTC, datetime

from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

ACTIVATABLE_KEY_STATUSES = frozenset(
    {LicenseKeyStatus.ISSUED, LicenseKeyStatus.ACTIVATED, LicenseKeyStatus.EXPIRING}
)


def aware_utc(at: datetime) -> datetime:
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    return at.astimezone(UTC)


def license_window_allows_service(
    *, status: str, starts_at: datetime, expires_at: datetime, at: datetime,
) -> bool:
    return status in ACTIVATABLE_KEY_STATUSES and starts_at <= at < expires_at


def find_eligible_org_license(org_id: int, at: datetime) -> AppLicenseKey | None:
    return (
        AppLicenseKey.objects.select_related("customer")
        .filter(
            customer_id=org_id,
            status__in=ACTIVATABLE_KEY_STATUSES,
            starts_at__lte=at,
            expires_at__gt=at,
        )
        .order_by("-expires_at", "-pk")
        .first()
    )
