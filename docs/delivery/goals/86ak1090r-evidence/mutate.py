#!/usr/bin/env python3
"""Mutation harness for 86ak1090r (staff revoke + extend), results in mutation-results.txt.

Every mutant is ONE textual change to ONE production file. The named test FILES run with all
their siblings (never --exact), and a mutant must go RED. Each mutant also names the tests that
are MEANT to kill it (`kill`, substrings of test names): a mutant that goes red only because some
unrelated test broke is reported as KILLED-ELSEWHERE, not KILLED, because the guard it was about
is then unproven. After every run the file is restored from the repository and compared byte for
byte (filecmp, the equivalent of `cmp`).

It never touches the working tree: it copies `implementation/api` (without the venv) to a
sandbox directory and mutates the copy, so it can run while you keep working, and two copies can
run side by side (give each its own --sandbox).

Usage, from anywhere inside the repository:

    # SQLite, the way `make api-check` runs it (needs `make api-install` once)
    python3 docs/delivery/goals/86ak1090r-evidence/mutate.py \
        --python implementation/api/.venv-api-check/bin/python --out /tmp/mutation-sqlite.txt

    # the Postgres-only mutants (P*): point the SQL_* variables at a DISPOSABLE Postgres first
    SQL_ENGINE=django.db.backends.postgresql SQL_HOST=... SQL_USER=... SQL_PASSWORD=... \
    SQL_DATABASE=... python3 docs/delivery/goals/86ak1090r-evidence/mutate.py --postgres \
        --python <a venv python with psycopg> --out /tmp/mutation-postgres.txt

    --only A1,T2   run just those ids (prefix match, e.g. --only A runs every A mutant)
    --list         print the ids and what each one changes

Exit status is 0 only when every selected mutant was KILLED by one of its intended tests.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = pathlib.Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=pathlib.Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)
API = REPO / "implementation" / "api"

PKG = "selahcue_api"
SM = f"{PKG}/apps/license_keys/state_machine.py"
SV = f"{PKG}/apps/license_keys/services.py"
DV = f"{PKG}/apps/devices/services.py"
RD = f"{PKG}/graphql/redaction.py"
TG = f"{PKG}/apps/throttling/guards.py"
SG = f"{PKG}/graphql/admin_schema.py"

MAIN = "tests/test_license_revoke_extend.py"
DEPTH = "tests/test_redaction_depth_bound.py"
ACT = "tests/test_activation_licence_transition.py"
ACT2 = "tests/test_device_activation_slice.py"
SMT = "tests/test_license_state_machine.py"
SUSP = "tests/test_license_suspend_reinstate.py"
THR = "tests/test_throttling_guards.py"
PG = "tests/test_concurrency_postgres.py"


def mutant(file, old, new, tests, kill=(), postgres=False, note=""):
    return dict(file=file, old=old, new=new, tests=list(tests), kill=list(kill), postgres=postgres, note=note)


MUTANTS = {
    # --- AC 8: the wrapped-transaction tripwire --------------------------------------------
    "T1-tripwire-removed": mutant(
        SM, "if transaction.get_connection().in_atomic_block and not allow_wrapping_transaction:", "if False:",
        [MAIN, ACT], ["tripwire", "wrapped"], note="remove the in_atomic_block check from the writer"),
    "T2-activation-optin-removed": mutant(
        DV, "                allow_wrapping_transaction=True,\n            )", "            )",
        [MAIN, ACT, ACT2], ["first_activation", "activation"], note="device activation stops passing the opt-in"),
    "T3-extend-optin-removed": mutant(
        SV, "                    allow_wrapping_transaction=True,\n                )\n            except IllegalLicenseTransition",
        "                )\n            except IllegalLicenseTransition", [MAIN], ["extend", "writer"],
        note="extend stops passing the opt-in"),
    "T4-tripwire-inverted": mutant(
        SM, "in_atomic_block and not allow_wrapping_transaction:", "in_atomic_block and allow_wrapping_transaction:",
        [MAIN, ACT], ["tripwire", "wrapped", "activation"], note="the check fires only when the caller DID opt in"),
    "T5-tripwire-default-on": mutant(
        SM, "    allow_wrapping_transaction: bool = False,\n) -> LicenseTransitionResult:",
        "    allow_wrapping_transaction: bool = True,\n) -> LicenseTransitionResult:",
        [MAIN, ACT], ["opt_in_is_keyword_only", "tripwire", "refuses_to_run"], note="the opt-in defaults to True"),
    "T6-extra-optin-site": mutant(
        SV, "        action=action,\n    )", "        action=action,\n        allow_wrapping_transaction=True,\n    )",
        [MAIN], ["only_device_activation_and_extend"],
        note="a third caller opts in (the scan that pins the opt-in sites must notice)"),
    # --- AC 11 / AC 2: authorisation and the refusal audit ---------------------------------
    "A1-gate-removed-in-_authorise": mutant(
        SV, "    try:\n        return require_staff_permission(actor, permission)\n    except SafeAPIError as error:",
        "    try:\n        return actor\n    except SafeAPIError as error:", [MAIN, SUSP],
        ["unauthorised", "refuses_missing_or_wrong_permission", "gate"], note="the shared permission gate is a no-op"),
    "A2-revoke-gate-removed": mutant(
        SV, "    staff = _authorise(\n        actor,\n        permission,\n        denied_action=denied_action,",
        "    staff = actor\n    (lambda *a, **k: None)(\n        actor,\n        permission,\n        denied_action=denied_action,",
        [MAIN, SUSP], ["unauthorised", "gate", "permission"], note="the lifecycle (revoke) path skips the gate"),
    "A3-extend-gate-removed": mutant(
        SV, "    staff = _authorise(\n        actor,\n        StaffPermission.EXTEND_LICENSE_KEY,\n        denied_action=EXTEND_PERMISSION_DENIED_ACTION,",
        "    staff = actor\n    (lambda *a, **k: None)(\n        actor,\n        StaffPermission.EXTEND_LICENSE_KEY,\n        denied_action=EXTEND_PERMISSION_DENIED_ACTION,",
        [MAIN, SUSP], ["unauthorised", "gate", "permission"], note="extend skips the gate"),
    "A4-gate-after-lookup-extend": mutant(
        SV, "    staff = _authorise(\n        actor,\n        StaffPermission.EXTEND_LICENSE_KEY,",
        "    _get_license_key_or_not_found(data.license_key_id)\n    staff = _authorise(\n        actor,\n        StaffPermission.EXTEND_LICENSE_KEY,",
        [MAIN], ["gate_runs_before"], note="extend looks the licence up BEFORE the gate"),
    "A5-refusal-audit-per-actor-budget-removed": mutant(
        SV, "    if spend_budget(\n        REFUSAL_AUDIT_SCOPE, identity, REFUSAL_AUDIT_SETTING, REFUSAL_AUDIT_BUDGET\n    ) is BudgetOutcome.DENIED:\n        return\n",
        "", [MAIN], ["bounded_per_actor"], note="per-actor cap on refusal audit rows removed"),
    "A6-refusal-audit-global-cap-removed": mutant(
        SV, "    ) is BudgetOutcome.DENIED:\n        return\n\n    # No lookup:", "    ) is None:\n        return\n\n    # No lookup:",
        [MAIN], ["global_cap"], note="per-kind cap on refusal audit rows removed"),
    "A7-refusal-not-audited": mutant(
        SV, "        if denied_action is not None and actor is not None and error.code is ErrorCode.PERMISSION_DENIED:",
        "        if False:", [MAIN], ["denied_audit_row", "graphql_refuses"], note="a refused caller leaves no audit row"),
    "A8-global-cap-shared-by-every-kind": mutant(
        SV, "        actor.kind.value,\n        REFUSAL_AUDIT_GLOBAL_SETTING,", "        \"all\",\n        REFUSAL_AUDIT_GLOBAL_SETTING,",
        [MAIN], ["crowd_staff_out"], note="one global refusal-audit cap shared by every kind of actor"),
    "A9-refused-reason-stored": mutant(
        SV, "            reason=\"\",\n            result=AuditResult.DENIED,\n            after={\n                \"required_permission\"",
        "            reason=\"text from a refused caller\",\n            result=AuditResult.DENIED,\n            after={\n                \"required_permission\"",
        [MAIN], ["reason_is_never_stored", "hostile_input"], note="the refusal row stores a reason"),
    "A10-actor-id-guard-removed": mutant(
        SV, "    if not actor_id or len(actor_id) > ACTOR_ID_MAX_LENGTH or has_control_characters(actor_id):",
        "    if False:", [MAIN], ["cannot_be_audited"], note="the refusal audit no longer skips an id it cannot store"),
    "A11-audit-failure-escapes": mutant(
        SV, "    except Exception:  # noqa: BLE001 - the record of a refusal must never undo the refusal",
        "    except KeyError:  # noqa: BLE001", [MAIN], ["failure_to_write_the_refusal_row"],
        note="a failure to write the refusal row turns the refusal into a crash"),
    "A12-throttle-log-names-password-reset": mutant(
        TG, "This may be sustained abuse \"\n        \"of this scope's budget;",
        "This may be a DEC-013 password reset attack \"\n        \"of this scope's budget;", [MAIN, THR],
        ["sustained_denial_log_line"], note="the sustained-denial log line talks about password reset again"),
    "A13-refused-target-id-stored-as-sent": mutant(
        SV, "    target_id = _clean_license_key_id(raw_license_key_id) or _UNRESOLVED_TARGET",
        "    target_id = raw_license_key_id[:128]", [MAIN], ["licence_id_is_never_stored_as_sent"],
        note="a refused caller's licence id (a full key, a NUL, a C1 control) is written to the trail as sent"),
    # --- the GraphQL resolvers hand the submitted text through ------------------------------
    "B1-extend-resolver-reason-hardcoded": mutant(
        SG, "                new_expires_at=input.new_expires_at,\n                reason=input.reason,",
        "                new_expires_at=input.new_expires_at,\n                reason=\"Reason supplied by the console\",",
        [MAIN], ["graphql_extend"], note="adminExtendLicenseKey ignores the submitted reason"),
    "B2-revoke-resolver-reason-hardcoded": mutant(
        SG, "            RevokeLicenseKeyData(\n                idempotency_key=input.idempotency_key,\n                license_key_id=str(input.license_key_id),\n                reason=input.reason,",
        "            RevokeLicenseKeyData(\n                idempotency_key=input.idempotency_key,\n                license_key_id=str(input.license_key_id),\n                reason=\"Reason supplied by the console\",",
        [MAIN], ["graphql_revoke"], note="adminRevokeLicenseKey ignores the submitted reason"),
    "B3-extend-resolver-retry-key-hardcoded": mutant(
        SG, "            ExtendLicenseKeyData(\n                idempotency_key=input.idempotency_key,",
        "            ExtendLicenseKeyData(\n                idempotency_key=\"fixed-key-from-the-resolver\",", [MAIN], ["graphql_extend"],
        note="adminExtendLicenseKey ignores the submitted retry key"),
    "B4-revoke-resolver-retry-key-hardcoded": mutant(
        SG, "            RevokeLicenseKeyData(\n                idempotency_key=input.idempotency_key,",
        "            RevokeLicenseKeyData(\n                idempotency_key=\"fixed-key-from-the-resolver\",", [MAIN], ["graphql_revoke"],
        note="adminRevokeLicenseKey ignores the submitted retry key"),
    "Q1-revoke-action-renamed": mutant(
        SM, 'REVOKE_ACTION = "license_key.revoked"', 'REVOKE_ACTION = "license_key.revoke"', [MAIN, SUSP],
        ["action_names_are_a_contract", "revoke"], note="the audit action string for a revoke changes"),
    # --- credential guard (reason and retry key) -------------------------------------------
    "C1-credential-check-removed": mutant(
        SV, "    if _GROUPED_KEY_RE.search(scanned) or _RUN_TOGETHER_KEY_RE.search(scanned):", "    if False:",
        [MAIN], ["full_licence_key_is_refused"], note="a reason containing a full key is accepted and stored"),
    "C2-nfkc-removed": mutant(
        SV, "    folded = unicodedata.normalize(\"NFKC\", text)", "    folded = text", [MAIN], ["fullwidth"],
        note="full-width letters slip past"),
    "C3-format-characters-kept": mutant(
        SV, "if unicodedata.category(ch) != \"Cf\"", "if True", [MAIN], ["inside-a-group", "inside-every-group", "inside-a-run-together"],
        note="zero-width and soft-hyphen characters hide a key"),
    "C4-run-together-not-checked": mutant(
        SV, "    if _GROUPED_KEY_RE.search(scanned) or _RUN_TOGETHER_KEY_RE.search(scanned):",
        "    if _GROUPED_KEY_RE.search(scanned):", [MAIN], ["run-together"], note="a key pasted as 32 characters is accepted"),
    "C5-separators-narrowed": mutant(
        SV, "[\\W_]{{1,3}}", "[\\W_]{{1,1}}", [MAIN], ["dots-and-spaces", "prefix-with-spaces"],
        note="only single-character separators are recognised"),
    "C6-retry-key-check-removed": mutant(
        SV, "    if _GROUPED_KEY_RE.search(_for_credential_scan(key)):", "    if False:", [MAIN],
        ["used_as_the_retry_key", "pasted_key_is_not_stored"], note="a licence key is accepted as a retry key"),
    "C7-lifecycle-uses-plain-reason": mutant(
        SV, "    idempotency_key = _require_retry_key(raw_idempotency_key)\n    reason = _require_reason_without_a_credential(raw_reason)",
        "    idempotency_key = _require_retry_key(raw_idempotency_key)\n    reason = require_reason(raw_reason)",
        [MAIN], ["[suspend", "[reinstate", "[revoke"], note="revoke, suspend and reinstate use the plain reason check"),
    "C8-credential-error-is-generic": mutant(
        SV, "    return SafeAPIError(ErrorCode.CREDENTIAL_IN_INPUT)", "    return SafeAPIError(ErrorCode.VALIDATION_FAILED)",
        [MAIN], ["full_licence_key_is_refused", "own_error_code"], note="the refusal is the generic validation error again"),
    "C9-refusal-row-stores-a-key-shaped-retry-key": mutant(
        SV, "        request_id = _require_retry_key(raw_idempotency_key)\n    except SafeAPIError:",
        "        request_id = validate_idempotency_key(raw_idempotency_key)\n    except SafeAPIError:",
        [MAIN], ["pasted_key_is_not_stored"], note="a refused caller's key-shaped retry key is stored as request_id"),
    "C10-lifecycle-retry-key-unchecked": mutant(
        SV, "    idempotency_key = _require_retry_key(raw_idempotency_key)\n    reason = _require_reason_without_a_credential(raw_reason)",
        "    idempotency_key = validate_idempotency_key(raw_idempotency_key)\n    reason = _require_reason_without_a_credential(raw_reason)",
        [MAIN], ["used_as_the_retry_key"], note="revoke, suspend and reinstate accept a key as a retry key"),
    "C11-extend-retry-key-unchecked": mutant(
        SV, "    idempotency_key = _require_retry_key(data.idempotency_key)\n    reason = _require_reason_without_a_credential(data.reason)",
        "    idempotency_key = validate_idempotency_key(data.idempotency_key)\n    reason = _require_reason_without_a_credential(data.reason)",
        [MAIN], ["used_as_the_retry_key"], note="extend accepts a key as a retry key"),
    "C12-key-ceiling-boundary-removed": mutant(
        SV, '_KEY_CEILING = r"(?![A-Z0-9])"', '_KEY_CEILING = r""', [MAIN], ["not_mistaken_for_a_key"],
        note="the first 32 characters of a longer token count as a key"),
    "C13-key-floor-boundary-removed": mutant(
        SV, '_KEY_FLOOR = r"(?<![A-Z0-9])"', '_KEY_FLOOR = r""', [MAIN], ["not_mistaken_for_a_key"],
        note="the last 32 characters of a longer token count as a key"),
    # --- AC 9: the depth bound --------------------------------------------------------------
    "D0-both-bounds-removed": mutant(
        RD, "        if depth > MAX_PAYLOAD_DEPTH or seen > MAX_PAYLOAD_CONTAINERS:", "        if False:", [DEPTH],
        ["bound", "refused"], note="depth and container bounds removed from the walker"),
    "D1-depth-part-removed": mutant(
        RD, "        if depth > MAX_PAYLOAD_DEPTH or seen > MAX_PAYLOAD_CONTAINERS:", "        if seen > MAX_PAYLOAD_CONTAINERS:",
        [DEPTH, MAIN], ["one_past_the_bound", "mixed_nesting"], note="the depth bound removed (container cap kept)"),
    "D2-writer-boundary-check-removed": mutant(
        SM, "    ensure_payload_depth(extra_before or {})\n    ensure_payload_depth(extra_after or {})\n", "",
        [MAIN], ["writers_boundary", "does_not_destroy"], note="the writer no longer refuses an over-deep payload before its transaction"),
    "D3-container-cap-removed": mutant(
        RD, "        if depth > MAX_PAYLOAD_DEPTH or seen > MAX_PAYLOAD_CONTAINERS:", "        if depth > MAX_PAYLOAD_DEPTH:",
        [DEPTH], ["shared_substructure"], note="the container cap removed (depth bound kept)"),
    "D5-depth-bound-nine": mutant(
        RD, "MAX_PAYLOAD_DEPTH = 8", "MAX_PAYLOAD_DEPTH = 9", [DEPTH], ["exactly_eight"], note="the depth bound is 9 instead of 8"),
    "D6-depth-bound-seven": mutant(
        RD, "MAX_PAYLOAD_DEPTH = 8", "MAX_PAYLOAD_DEPTH = 7", [DEPTH], ["exactly_eight"], note="the depth bound is 7 instead of 8"),
    "D4-container-cap-raised-tenfold": mutant(
        RD, "MAX_PAYLOAD_CONTAINERS = 2000", "MAX_PAYLOAD_CONTAINERS = 20000", [DEPTH], ["exactly_two_thousand"],
        note="the container cap is 20000 instead of 2000"),
    # --- AC 10: writer discipline and the unwritten-status record --------------------------
    "W1-revoke-assigns-status-directly": mutant(
        SV, "    return apply_license_status_transition(\n        license_key,\n        to_status=to_status,",
        "    license_key.status = to_status.value\n    license_key.save(update_fields=[\"status\"])\n    return apply_license_status_transition(\n        license_key,\n        to_status=to_status,",
        [SMT], ["no_production_module_writes_a_licence_status"], note="the mutations assign .status themselves"),
    "W2-unwritten-status-written": mutant(
        SV, "def revoke_license_key(",
        "def _dead_expiry_caller(key, staff):\n    return apply_license_status_transition(key, to_status=LicenseKeyStatus.EXPIRING, actor=staff, reason=\"x\", request_id=\"y\")\n\n\ndef revoke_license_key(",
        [MAIN], ["status_the_record_calls_unwritten"], note="a module starts writing EXPIRING without moving it out of the unwritten record"),
    # --- the autocommit guard ---------------------------------------------------------------
    "G1-lifecycle-autocommit-guard-removed": mutant(
        SV, "    _require_autocommit()\n    _enforce_lifecycle_budget(staff)\n    idempotency_key = _require_retry_key(raw_idempotency_key)",
        "    _enforce_lifecycle_budget(staff)\n    idempotency_key = _require_retry_key(raw_idempotency_key)",
        [MAIN, SUSP], ["autocommit_guard", "transaction"], note="revoke, suspend and reinstate run inside a caller's transaction"),
    "G2-extend-autocommit-guard-removed": mutant(
        SV, "    _require_autocommit()\n    _enforce_lifecycle_budget(staff)\n    idempotency_key = _require_retry_key(data.idempotency_key)",
        "    _enforce_lifecycle_budget(staff)\n    idempotency_key = _require_retry_key(data.idempotency_key)",
        [MAIN], ["autocommit_guard", "inside_a_transaction"], note="extend runs inside a caller's transaction"),
    "G3-extend-budget-removed": mutant(
        SV, "    _require_autocommit()\n    _enforce_lifecycle_budget(staff)\n    idempotency_key = _require_retry_key(data.idempotency_key)",
        "    _require_autocommit()\n    idempotency_key = _require_retry_key(data.idempotency_key)",
        [MAIN], ["budget", "throttle"], note="extend is not throttled"),
    # --- extend behaviour -------------------------------------------------------------------
    "E1-source-precheck-removed": mutant(
        SV, "        if before_status not in EXTENDABLE_SOURCES:", "        if False:", [MAIN],
        ["refuses_a_status_it_may_not_move"], note="extend accepts SUSPENDED, CONVERTED, REVOKED, ARCHIVED"),
    "E2-not-forward-check-removed": mutant(
        SV, "        if new_expires_at <= old_expires_at:", "        if False:", [MAIN], ["bad_date", "second_extension"],
        note="extend accepts a date that is not later than the current one"),
    "E3-ceiling-removed": mutant(
        SV, "        if new_expires_at > max(timezone.now(), old_expires_at) + MAX_EXTENSION_FROM_NOW:", "        if False:",
        [MAIN], ["ceiling", "9999"], note="extend has no five-year ceiling"),
    "E3b-ceiling-from-now": mutant(
        SV, "max(timezone.now(), old_expires_at) + MAX_EXTENSION_FROM_NOW", "timezone.now() + MAX_EXTENSION_FROM_NOW",
        [MAIN], ["already_past_the_ceiling", "five_years_beyond"], note="the ceiling is measured from now alone"),
    "E3c-ceiling-from-old-expiry": mutant(
        SV, "max(timezone.now(), old_expires_at) + MAX_EXTENSION_FROM_NOW", "old_expires_at + MAX_EXTENSION_FROM_NOW",
        [MAIN], ["lapsed_long_ago"], note="the ceiling is measured from the old expiry alone"),
    "E4-naive-accepted": mutant(
        SV, "    if not isinstance(value, datetime) or timezone.is_naive(value):", "    if not isinstance(value, datetime):",
        [MAIN], ["naive"], note="extend accepts a datetime with no UTC offset"),
    "E5-overlap-guard-removed": mutant(
        SV, "            require_no_overlapping_license_key(\n                customer,\n                starts_at=locked.starts_at,",
        "            (lambda *a, **k: None)(\n                customer,\n                starts_at=locked.starts_at,",
        [MAIN], ["overlap"], note="extend ignores another valid licence of the organisation"),
    "E5b-overlap-guard-counts-itself": mutant(
        SV, "                exclude_key_id=locked.pk,\n", "", [MAIN], ["moves_the_date", "extension"],
        note="the overlap check no longer excludes the licence being extended"),
    "E6-retry-lookup-removed": mutant(
        SV, "        if earlier is not None:\n", "        if False:\n", [MAIN], ["retry"], note="extend does not recognise its own retry"),
    "E6b-retry-checked-after-status": mutant(
        SV, "        if earlier is not None:\n", "        if earlier is not None and before_status in EXTENDABLE_SOURCES:\n",
        [MAIN], ["after_another_staff_action"], note="the replay is judged against the state the first call left"),
    "E6c-replay-date-not-compared": mutant(
        SV, "            if not _same_instant(earlier.after.get(\"expires_at\"), new_expires_at):", "            if False:",
        [MAIN], ["different_date"], note="the same key with a different date is reported as a replay"),
    "E7-catch-inside-removed": mutant(
        SV, "            except IllegalLicenseTransition as refusal:\n                writer_refusal = refusal",
        "            except IllegalLicenseTransition as refusal:\n                raise", [MAIN], ["still_durable"],
        note="the writer's refusal propagates out of extend's transaction (the DENIED row is lost)"),
    "E10-status-not-restored": mutant(
        SV, "_EXTENDS_TO_ACTIVATED = frozenset({LicenseKeyStatus.EXPIRING, LicenseKeyStatus.EXPIRED})",
        "_EXTENDS_TO_ACTIVATED = frozenset()", [MAIN], ["returns_a_lapsed_licence"], note="EXPIRING and EXPIRED are not returned to ACTIVATED"),
    "E11-date-move-skipped": mutant(
        SV, "    locked.expires_at = new_expires_at\n    locked.save(update_fields=[\"expires_at\", \"updated_at\"])", "    pass",
        [MAIN], ["moves_the_date"], note="extend writes the status and the audit row but never moves the date"),
    "E12-archived-customer-allowed": mutant(
        SV, "        if customer.status == CustomerStatus.ARCHIVED:\n            raise _ExtendRefused(",
        "        if False:\n            raise _ExtendRefused(", [MAIN], ["archived_customer"], note="extend works on an archived customer's licence"),
    # --- revoke behaviour -------------------------------------------------------------------
    "R1-revoke-targets-suspended": mutant(
        SV, "        to_status=LicenseKeyStatus.REVOKED,\n        raw_idempotency_key", "        to_status=LicenseKeyStatus.SUSPENDED,\n        raw_idempotency_key",
        [MAIN], ["revoke"], note="revoke writes SUSPENDED"),
    "R2-revoke-retry-not-recognised": mutant(
        SV, "        recognise_retry=True,", "        recognise_retry=False,", [MAIN, SUSP], ["retry"],
        note="the lifecycle mutations do not ask the writer to recognise a retry"),
    # --- Postgres only (use --postgres) -----------------------------------------------------
    "P1-extend-org-lock-removed": mutant(
        SV, "        customer = lock_customer_for_key_changes(license_key.customer_id)\n        locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)",
        "        customer = CustomerOrg.objects.get(pk=license_key.customer_id)\n        locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)",
        [PG], ["issuance", "different_dates"], postgres=True, note="extend does not take the organisation row lock"),
    "P2-extend-licence-lock-removed": mutant(
        SV, "        locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)\n        try:\n            before_status",
        "        locked = AppLicenseKey.objects.get(pk=license_key.pk)\n        try:\n            before_status",
        [PG], ["revoke_that_wins", "extension_that_wins"], postgres=True, note="extend reads the licence without FOR UPDATE"),
    "P3-activation-lock-covers-the-org-again": mutant(
        DV, "AppLicenseKey.objects.select_for_update(of=(\"self\",))", "AppLicenseKey.objects.select_for_update()",
        [PG], ["never_deadlock", "activation_lock_names"], postgres=True,
        note="activation's lock query also locks the org row it joins (the deadlock found in round 2)"),
}


def sandbox_copy(destination: pathlib.Path) -> pathlib.Path:
    ignore = shutil.ignore_patterns(".venv-api-check", "__pycache__", "*.egg-info", "db.sqlite3", ".pytest_cache")
    target = destination / "api"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(API, target, ignore=ignore)
    return target


def run_tests(sandbox_api: pathlib.Path, python: str, tests: list[str], postgres: bool) -> tuple[int, str]:
    env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL") if k in os.environ}
    if postgres:
        env.update({k: v for k, v in os.environ.items() if k.startswith("SQL_")})
    else:
        env["SQL_DATABASE"] = ":memory:"
    proc = subprocess.run(
        [python, "-m", "pytest", "-p", "no:cacheprovider", *tests, "-q", "-rf"],
        cwd=sandbox_api, env=env, capture_output=True, text=True, timeout=2400,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=str(API / ".venv-api-check" / "bin" / "python"))
    parser.add_argument("--postgres", action="store_true", help="run the Postgres-only mutants (P*) and no others")
    parser.add_argument("--only", default="", help="comma-separated id prefixes")
    parser.add_argument("--sandbox", default="", help="directory for the working copy (default: a temp dir)")
    parser.add_argument("--out", default="", help="write the result lines (with failing test names) here")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for mid, spec in MUTANTS.items():
            print(f"{mid:46s} {'PG ' if spec['postgres'] else '   '}{spec['note']}")
        return 0

    prefixes = [p.strip() for p in args.only.split(",") if p.strip()]
    chosen = [
        mid for mid, spec in MUTANTS.items()
        if spec["postgres"] == args.postgres and (not prefixes or any(mid.startswith(p) for p in prefixes))
    ]
    holder = pathlib.Path(args.sandbox) if args.sandbox else pathlib.Path(tempfile.mkdtemp(prefix="mutate-86ak1090r-"))
    holder.mkdir(parents=True, exist_ok=True)
    sandbox_api = sandbox_copy(holder)

    lines, failures = [], 0
    for mid in chosen:
        spec = MUTANTS[mid]
        path = sandbox_api / spec["file"]
        original = path.read_bytes()
        text = original.decode("utf-8")
        if text.count(spec["old"]) != 1:
            lines.append(f"{mid}  SPEC-ERROR: the text to change was found {text.count(spec['old'])} times")
            failures += 1
            print(lines[-1], flush=True)
            continue
        started = time.monotonic()
        try:
            path.write_bytes(text.replace(spec["old"], spec["new"], 1).encode("utf-8"))
            code, output = run_tests(sandbox_api, args.python, spec["tests"], args.postgres)
        finally:
            path.write_bytes(original)
        restored = filecmp.cmp(path, API / spec["file"], shallow=False)
        failed = sorted(set(re.findall(r"^FAILED (\S+)", output, re.M)))
        summary = (output.strip().splitlines() or [""])[-1]
        if code == 0:
            verdict = "SURVIVED"
        elif spec["kill"] and not any(any(frag in name for frag in spec["kill"]) for name in failed):
            verdict = "KILLED-ELSEWHERE"
        else:
            verdict = "KILLED"
        if verdict != "KILLED" or not restored:
            failures += 1
        lines.append(f"{mid}  {verdict}  [{summary[:70]}]  restored_identical={restored}  # {spec['note']}")
        for name in failed:
            lines.append(f"      red: {name}")
        print(lines[-1 - len(failed)], f"({time.monotonic() - started:.0f}s)", flush=True)

    if args.out:
        pathlib.Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"{len(chosen)} mutants, {failures} not cleanly killed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
