from dataclasses import dataclass
from datetime import datetime
import re

from django.conf import settings
from django.utils import timezone


class PilotRegistrationError(ValueError):
    def __init__(self, code: str, status: int = 400):
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True, repr=False)
class PilotPolicy:
    n8n_token: str
    signing_key: str
    fingerprint_key: str
    spreadsheet_id: str
    sheet_tab: str
    capacity: int
    notice_versions: tuple[str, ...]
    retention_days: int
    receipt_ttl_seconds: int
    pilot_expires_at: datetime


def load_policy() -> PilotPolicy:
    raw = getattr(settings, "SELAHCUE_PILOT_REGISTRATION", {})
    if not isinstance(raw, dict) or raw.get("enabled") is not True:
        raise PilotRegistrationError("registration_disabled", 404)
    try:
        secrets = [raw[k] for k in ("n8n_token", "signing_key", "fingerprint_key")]
        if any(not isinstance(v, str) or not 32 <= len(v) <= 256 or not v.isascii() or any(c.isspace() for c in v) for v in secrets):
            raise ValueError
        if len(set(secrets)) != 3:
            raise ValueError
        document = raw["spreadsheet_id"]
        tab = raw["sheet_tab"]
        if not isinstance(document, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", document):
            raise ValueError
        if not isinstance(tab, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_ -]{0,79}", tab):
            raise ValueError
        # Config values are strings from env or integers in test/deployment settings.
        numbers = [raw[k] for k in ("capacity", "retention_days", "receipt_ttl_seconds")]
        if any(type(v) not in (str, int) for v in numbers):
            raise ValueError
        capacity, retention, ttl = map(int, numbers)
        if not (2 <= capacity <= 100000 and 1 <= retention <= 3650 and 30 <= ttl <= 3600):
            raise ValueError
        notices = raw["notice_versions"]
        if not isinstance(notices, (tuple, list)) or not 1 <= len(notices) <= 20:
            raise ValueError
        if any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", v) or "draft" in v.lower() for v in notices):
            raise ValueError
        owner = raw["collection_owner"]
        if not isinstance(owner, str) or not owner.strip() or len(owner) > 200 or raw.get("layout_protected") is not True:
            raise ValueError
        expiry = datetime.fromisoformat(raw["pilot_expires_at"])
        if timezone.is_naive(expiry):
            raise ValueError
    except (KeyError, ValueError, TypeError, OverflowError):
        # No raw configuration value or secret is exposed in errors/logs.
        raise PilotRegistrationError("configuration_required", 503) from None
    if expiry <= timezone.now():
        raise PilotRegistrationError("pilot_expired", 410)
    return PilotPolicy(*secrets, document, tab, capacity, tuple(notices), retention, ttl, expiry)
