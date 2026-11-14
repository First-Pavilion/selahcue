"""The active licence selector shared by session activation and the catalogue."""

from datetime import datetime

from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

ACTIVATABLE_KEY_STATUSES = frozenset(
    {LicenseKeyStatus.ISSUED, LicenseKeyStatus.ACTIVATED, LicenseKeyStatus.EXPIRING}
)


def find_eligible_org_license(org_id: int, at: datetime) -> AppLicenseKey | None:
    return (
        AppLicenseKey.objects.select_related("customer")
        .filter(
            customer_id=org_id,
            status__in=ACTIVATABLE_KEY_STATUSES,
            starts_at__lte=at,
            expires_at__gt=at,
        )
        .order_by("-expires_at")
        .first()
    )
