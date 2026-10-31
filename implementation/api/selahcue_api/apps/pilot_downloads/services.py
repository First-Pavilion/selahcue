"""Trusted n8n orchestration: reserve a fixed row, then confirm its write ACK.

No remote call is held under a database lock. Ambiguous Google outcomes retry a
RAW update of the identical row, never append. A protected, dedicated tab and
preserved allocation ledger are mandatory operational trust boundaries.
"""

from dataclasses import asdict
from datetime import timedelta
import hashlib
import hmac
import json
from uuid import UUID

from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone

from selahcue_api.apps.pilot_downloads.models import PilotRegistrationRecord, PilotSheetDestination
from selahcue_api.apps.pilot_downloads.policy import PilotPolicy, PilotRegistrationError, load_policy
from selahcue_api.apps.pilot_downloads.registration import PilotRegistration, validate_registration


RECEIPT_SALT = "selahcue.pilot-registration.receipt.v1"
SHEET_COLUMNS = (
    "registration_id", "submitted_at", "full_name", "email", "phone",
    "church_name", "church_role", "church_city", "church_country", "platform",
    "source", "notice_version", "schema_version",
)


def _fingerprint(policy: PilotPolicy, purpose: str, value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hmac.new(policy.fingerprint_key.encode(), (purpose + "\0" + canonical).encode(), hashlib.sha256).hexdigest()


def _destination(policy: PilotPolicy) -> str:
    return _fingerprint(policy, "sheet-v1", [policy.spreadsheet_id, policy.sheet_tab])


def _payload_fingerprint(policy: PilotPolicy, registration: PilotRegistration) -> str:
    return _fingerprint(policy, "registration-v1", {"schema_version": 1, **asdict(registration)})


def _check_record(record: PilotRegistrationRecord, policy: PilotPolicy) -> None:
    if record.destination_id != _destination(policy):
        raise PilotRegistrationError("identity_conflict", 409)
    if record.sheet_row > policy.capacity:
        raise PilotRegistrationError("sheet_capacity_exhausted", 503)
    if record.created_at + timedelta(days=policy.retention_days) <= timezone.now():
        raise PilotRegistrationError("registration_retired", 410)


def _claims(record: PilotRegistrationRecord, policy: PilotPolicy) -> dict:
    _check_record(record, policy)
    if record.confirmed_at is None:
        raise PilotRegistrationError("registration_pending", 409)
    expiry = min(record.confirmed_at + timedelta(seconds=policy.receipt_ttl_seconds), policy.pilot_expires_at)
    if expiry <= timezone.now():
        raise PilotRegistrationError("receipt_expired", 410)
    return {
        "schema_version": 1, "registration_id": str(record.registration_id),
        "platform": record.platform, "channel": "pilot",
        "audience": "pilot-download-grant",
        "issued_at": int(record.confirmed_at.timestamp()), "expires_at": int(expiry.timestamp()),
    }


def _confirmed_result(record: PilotRegistrationRecord, policy: PilotPolicy) -> dict:
    claims = _claims(record, policy)
    receipt = signing.dumps(claims, key=policy.signing_key, salt=RECEIPT_SALT, compress=False)
    return {"schema_version": 1, "registration_id": str(record.registration_id), "state": "confirmed",
            "receipt": receipt, "expires_at": claims["expires_at"]}


def _reservation_result(record: PilotRegistrationRecord, registration: PilotRegistration, policy: PilotPolicy) -> dict:
    _check_record(record, policy)
    if record.confirmed_at is not None:
        return _confirmed_result(record, policy)
    cells = registration.to_sheet_row()
    cells["submitted_at"] = record.created_at.isoformat()
    cells["source"] = "selahcue-marketing-pilot"
    row = record.sheet_row
    return {
        "schema_version": 1, "registration_id": str(record.registration_id), "state": "pending",
        "sheet_write": {"spreadsheet_id": policy.spreadsheet_id, "range": f"'{policy.sheet_tab}'!A{row}:M{row}",
                        "majorDimension": "ROWS", "valueInputOption": "RAW",
                        "values": [[cells[column] for column in SHEET_COLUMNS]]},
    }


def reserve_registration(payload: object, *, policy: PilotPolicy | None = None) -> dict:
    policy = policy or load_policy()
    registration = validate_registration(payload)
    if registration.notice_version not in policy.notice_versions:
        raise PilotRegistrationError("notice_not_approved", 400)
    destination = _destination(policy)
    payload_fingerprint = _payload_fingerprint(policy, registration)
    try:
        with transaction.atomic():
            PilotSheetDestination.objects.get_or_create(fingerprint=destination)
            allocator = PilotSheetDestination.objects.select_for_update().get(pk=destination)
            record = PilotRegistrationRecord.objects.filter(pk=registration.registration_id).first()
            if record is None:
                if allocator.next_row > policy.capacity:
                    raise PilotRegistrationError("sheet_capacity_exhausted", 503)
                record = PilotRegistrationRecord.objects.create(
                    registration_id=registration.registration_id, destination=allocator,
                    sheet_row=allocator.next_row, payload_fingerprint=payload_fingerprint,
                    platform=registration.platform, notice_version=registration.notice_version,
                )
                allocator.next_row += 1
                allocator.save(update_fields=["next_row"])
            elif not hmac.compare_digest(record.payload_fingerprint, payload_fingerprint):
                raise PilotRegistrationError("identity_conflict", 409)
            return _reservation_result(record, registration, policy)
    except IntegrityError:
        # Different destinations do not share a lock; global UUID uniqueness is
        # the final arbiter for simultaneous claims of one identity across tabs.
        record = PilotRegistrationRecord.objects.filter(pk=registration.registration_id).first()
        if record is None:
            raise
        if not hmac.compare_digest(record.payload_fingerprint, payload_fingerprint):
            raise PilotRegistrationError("identity_conflict", 409) from None
        return _reservation_result(record, registration, policy)


def _identity(raw: object) -> UUID:
    try:
        if not isinstance(raw, str) or len(raw) != 36:
            raise ValueError
        value = UUID(raw)
        if value.version != 4 or str(value) != raw:
            raise ValueError
        return value
    except ValueError:
        raise PilotRegistrationError("registration_invalid", 400) from None


def confirm_registration(payload: object, *, policy: PilotPolicy | None = None) -> dict:
    policy = policy or load_policy()
    if not isinstance(payload, dict) or set(payload) != {"registration_id", "sheet_ack"}:
        raise PilotRegistrationError("sheet_ack_invalid")
    identity = _identity(payload["registration_id"])
    ack = payload["sheet_ack"]
    with transaction.atomic():
        record = PilotRegistrationRecord.objects.select_for_update().filter(pk=identity).first()
        if record is None:
            raise PilotRegistrationError("registration_unknown", 404)
        _check_record(record, policy)
        row = record.sheet_row
        ranges = {f"'{policy.sheet_tab}'!A{row}:M{row}", f"{policy.sheet_tab}!A{row}:M{row}"}
        expected_keys = {"spreadsheetId", "updatedRange", "updatedRows", "updatedColumns", "updatedCells"}
        if (not isinstance(ack, dict) or set(ack) != expected_keys or
                ack["spreadsheetId"] != policy.spreadsheet_id or not isinstance(ack["updatedRange"], str) or
                ack["updatedRange"] not in ranges or
                any(type(ack[key]) is not int or ack[key] != expected for key, expected in
                    (("updatedRows", 1), ("updatedColumns", 13), ("updatedCells", 13)))):
            raise PilotRegistrationError("sheet_ack_invalid")
        if record.confirmed_at is None:
            record.confirmed_at = timezone.now()
            record.save(update_fields=["confirmed_at"])
        return _confirmed_result(record, policy)


def verify_registration_receipt(receipt: object, *, policy: PilotPolicy | None = None) -> dict:
    """P12 interface: authenticity + live ledger/expiry, never an object URL."""
    policy = policy or load_policy()
    if not isinstance(receipt, str) or not 1 <= len(receipt) <= 2048:
        raise PilotRegistrationError("receipt_invalid", 403)
    try:
        claims = signing.loads(receipt, key=policy.signing_key, salt=RECEIPT_SALT, fallback_keys=[])
        if not isinstance(claims, dict):
            raise ValueError
        identity = _identity(claims.get("registration_id"))
    except (signing.BadSignature, ValueError, TypeError):
        raise PilotRegistrationError("receipt_invalid", 403) from None
    record = PilotRegistrationRecord.objects.filter(pk=identity).first()
    if record is None:
        raise PilotRegistrationError("receipt_invalid", 403)
    expected = _claims(record, policy)
    if claims != expected:
        raise PilotRegistrationError("receipt_invalid", 403)
    return expected
