"""Pure contract tests: runnable without a database or deployment credentials."""

import importlib.util
from pathlib import Path
import sys
import unittest

# Import the pure boundary directly: importing selahcue_api itself starts Celery.
# Keep this suite runnable before a fresh worktree has its Django/Celery venv.
_MODULE = "pilot_registration_contract_under_test"
_PATH = Path(__file__).parents[1] / "selahcue_api/apps/pilot_downloads/registration.py"
_SPEC = importlib.util.spec_from_file_location(_MODULE, _PATH)
_CONTRACT = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE] = _CONTRACT
_SPEC.loader.exec_module(_CONTRACT)
RegistrationValidationError = _CONTRACT.RegistrationValidationError
validate_registration = _CONTRACT.validate_registration


def submission(**overrides):
    value = {
        "schema_version": 1,
        "registration_id": "67df125a-c17e-4a15-a5fe-6cfab08dba47",
        "full_name": "  Jane Pastor  ",
        "email": " JANE@example.org ",
        "phone": "",
        "church_name": "Grace Community",
        "church_role": "Operator",
        "church_city": "Lagos",
        "church_country": "Nigeria",
        "platform": "Ubuntu",
        "notice_version": "pilot-registration-v1-approved",
    }
    value.update(overrides)
    return value


class RegistrationContractTests(unittest.TestCase):
    def test_valid_payload_is_normalized_without_mutating_input(self):
        payload = submission()
        registration = validate_registration(payload)
        self.assertEqual(registration.full_name, "Jane Pastor")
        self.assertEqual(registration.email, "jane@example.org")
        self.assertEqual(payload["full_name"], "  Jane Pastor  ")
        self.assertEqual(str(registration.registration_id), payload["registration_id"])

    def test_platform_is_explicit_and_case_sensitive(self):
        for platform in ("Windows", "Ubuntu", "macOS"):
            self.assertEqual(validate_registration(submission(platform=platform)).platform, platform)
        for platform in ("linux", "macos", "Android", "", None):
            with self.subTest(platform=platform), self.assertRaises(RegistrationValidationError):
                validate_registration(submission(platform=platform))

    def test_required_field_types_controls_and_boundaries(self):
        for field in ("full_name", "church_name", "church_role", "church_city", "church_country"):
            for value in ("", "   ", 123, None, "a" * 201, "name\x00tail"):
                with self.subTest(field=field, value=value), self.assertRaises(RegistrationValidationError):
                    validate_registration(submission(**{field: value}))
            self.assertEqual(getattr(validate_registration(submission(**{field: "a" * 200})), field), "a" * 200)

    def test_optional_phone_is_bounded_and_typed(self):
        payload = submission()
        payload.pop("phone")
        self.assertEqual(validate_registration(payload).phone, "")
        for value in (None, False, "a" * 51):
            with self.subTest(value=value), self.assertRaises(RegistrationValidationError):
                validate_registration(submission(phone=value))

    def test_version_and_registration_identity_are_not_workflow_execution_ids(self):
        for value in (None, True, "1", 0, 2):
            with self.subTest(version=value), self.assertRaises(RegistrationValidationError):
                validate_registration(submission(schema_version=value))
        for value in ("pilot-execution-123", "not-a-uuid", None, 123, "00000000-0000-0000-0000-000000000000"):
            with self.subTest(identity=value), self.assertRaises(RegistrationValidationError):
                validate_registration(submission(registration_id=value))

    def test_email_is_validated_and_values_are_not_disclosed_in_errors(self):
        for email in ("private-secret", "a@b", "a b@example.org", "a@example.org\x00", "a" * 255):
            with self.subTest(email=email):
                with self.assertRaises(RegistrationValidationError) as caught:
                    validate_registration(submission(email=email))
                self.assertNotIn(email, str(caught.exception))
                self.assertIn("email", caught.exception.fields)

    def test_unknown_fields_and_draft_notices_fail_closed(self):
        for payload in (submission(provider_key="secret"), submission(notice_version="pilot-v1-DRAFT"), [], None):
            with self.subTest(payload=payload), self.assertRaises(RegistrationValidationError):
                validate_registration(payload)

    def test_sheet_encoding_is_separate_from_normalized_identity(self):
        for marker in ("=", "+", "-", "@"):
            registration = validate_registration(submission(full_name=marker + "literal", phone="+234000"))
            self.assertEqual(registration.full_name, marker + "literal")
            row = registration.to_sheet_row()
            self.assertEqual(row["full_name"], "'" + marker + "literal")
            self.assertEqual(row["phone"], "'+234000")
            self.assertNotIn("receipt", row)
            self.assertNotIn("download_url", row)


if __name__ == "__main__":
    unittest.main()
