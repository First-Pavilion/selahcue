"""Normalized pilot form contract; validation never authorizes a download.

No HTTP endpoint, storage operation, or receipt issuer is installed by this module.
The orchestration must authenticate n8n and durably deduplicate a stable submission
UUID before writing Sheets, then acknowledge persistence before signing a receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import UUID


_FIELDS = (
    "schema_version", "registration_id", "full_name", "email", "phone",
    "church_name", "church_role", "church_city", "church_country", "platform",
    "notice_version",
)
_TEXT_FIELDS = ("full_name", "church_name", "church_role", "church_city", "church_country")
_PLATFORMS = frozenset({"Windows", "Ubuntu", "macOS"})
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+\Z")
_NOTICE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class RegistrationValidationError(ValueError):
    """Expose fixed field names, never caller-supplied personal data or values."""

    def __init__(self, fields: list[str]):
        self.fields = tuple(dict.fromkeys(fields))
        super().__init__("Invalid registration fields: " + ", ".join(self.fields))


@dataclass(frozen=True)
class PilotRegistration:
    registration_id: UUID
    full_name: str
    email: str
    phone: str
    church_name: str
    church_role: str
    church_city: str
    church_country: str
    platform: str
    notice_version: str

    def to_sheet_row(self) -> dict[str, str]:
        """Return literal cells for a Sheets write that must also use RAW input.

        Encoding stays outside normalized values so it cannot change deduplication
        identity or accumulate apostrophes on retries. No authorization is emitted.
        """
        row = {field: getattr(self, field) for field in _FIELDS if field not in {"schema_version", "registration_id"}}
        row["registration_id"] = str(self.registration_id)
        row["schema_version"] = "1"
        return {key: "'" + value if value.startswith(("=", "+", "-", "@")) else value for key, value in row.items()}


def validate_registration(payload: object) -> PilotRegistration:
    """Validate v1 normalized input; reject unknown fields and draft notice IDs.

    Accept only plain dictionaries from the JSON decoder. Ingress must separately
    enforce a request-size limit, authenticate server callbacks and throttle forms.
    """
    if not isinstance(payload, dict):
        raise RegistrationValidationError(["payload"])
    errors = []
    if payload.keys() - set(_FIELDS):
        errors.append("unexpected_fields")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        errors.append("schema_version")

    def text(field: str, maximum: int, required: bool = True) -> str:
        raw = payload.get(field, "")
        if not isinstance(raw, str) or len(raw) > maximum or _CONTROL.search(raw):
            errors.append(field)
            return ""
        value = raw.strip()
        if required and not value:
            errors.append(field)
        return value

    values = {field: text(field, 200) for field in _TEXT_FIELDS}
    values["email"] = text("email", 254).lower()
    if not _EMAIL.fullmatch(values["email"]):
        errors.append("email")
    values["phone"] = text("phone", 50, required=False)
    values["platform"] = text("platform", 20)
    if values["platform"] not in _PLATFORMS:
        errors.append("platform")
    values["notice_version"] = text("notice_version", 80)
    if not _NOTICE.fullmatch(values["notice_version"]) or "draft" in values["notice_version"].lower():
        errors.append("notice_version")

    identity = payload.get("registration_id")
    registration_id = None
    if isinstance(identity, str) and len(identity) == 36:
        try:
            registration_id = UUID(identity)
        except ValueError:
            pass
    if registration_id is None or registration_id.version != 4 or str(registration_id) != identity:
        errors.append("registration_id")
    if errors:
        raise RegistrationValidationError(errors)
    return PilotRegistration(registration_id=registration_id, **values)
