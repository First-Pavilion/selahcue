#!/usr/bin/env python3
# Evidence for 86ak1090r: the mutation harness exactly as it was run (results: mutation-results.txt).
#
# One textual change to one production file per mutant; the named test FILES run with all their
# siblings (never --exact); the run must go RED; the file is restored byte for byte and checked
# with `cmp`. It ran against a COPY of implementation/api (a sandbox directory, selected with the
# W2_SB environment variable) so the real worktree stayed untouched, through two wrapper scripts
# that are the repo's API_ENV pytest command (env -i, SQL_DATABASE=:memory:) and the same command
# pointed at a throwaway local PostgreSQL. SP, ROOT and those two scripts are therefore the
# author's local scratch paths; to reuse the harness, point ROOT at a copy of implementation/api
# and the two runners at your own venv.
"""Mutation harness for 86ak1090r.

One textual change to one production file per mutant, the named tests run WITH their siblings
(whole files, never --exact), the result must be RED, and the file is restored byte for byte
and checked with `cmp`. Usage: w2-86ak1090r-mutate.py <engine: sqlite|pg> <mutant-id> [...]
"""

import json
import os
import re
import shutil
import subprocess
import sys

SP = os.environ.get("W2_SCRATCH", "/path/to/scratch")  # holds the two runner scripts and the sandbox copies
ROOT = os.environ.get("W2_SB", SP + "/w2-86ak1090r-sandbox") + "/api"
PKG = "selahcue_api"

SM = f"{PKG}/apps/license_keys/state_machine.py"
SV = f"{PKG}/apps/license_keys/services.py"
DV = f"{PKG}/apps/devices/services.py"
RD = f"{PKG}/graphql/redaction.py"

MAIN = "tests/test_license_revoke_extend.py"
DEPTH = "tests/test_redaction_depth_bound.py"
ACT = "tests/test_activation_licence_transition.py"
ACT2 = "tests/test_device_activation_slice.py"
SMT = "tests/test_license_state_machine.py"
SUSP = "tests/test_license_suspend_reinstate.py"
PG = "tests/test_concurrency_postgres.py"

MUTANTS = {
    # --- AC 8: the tripwire ---------------------------------------------------------------
    "T1-tripwire-removed": dict(
        file=SM,
        old="if transaction.get_connection().in_atomic_block and not allow_wrapping_transaction:",
        new="if False:",
        tests=[MAIN, ACT],
    ),
    "T2-activation-optin-removed": dict(
        file=DV,
        old="                allow_wrapping_transaction=True,\n            )",
        new="            )",
        tests=[MAIN, ACT, ACT2],
    ),
    "T3-extend-optin-removed": dict(
        file=SV,
        old="                    allow_wrapping_transaction=True,\n                )\n            except IllegalLicenseTransition",
        new="                )\n            except IllegalLicenseTransition",
        tests=[MAIN],
    ),
    "T4-tripwire-inverted": dict(
        file=SM,
        old="in_atomic_block and not allow_wrapping_transaction:",
        new="in_atomic_block and allow_wrapping_transaction:",
        tests=[MAIN, ACT],
    ),
    # --- AC 11: authorisation gate --------------------------------------------------------
    "A1-gate-removed-in-_authorise": dict(
        file=SV,
        old="    try:\n        return require_staff_permission(actor, permission)\n    except SafeAPIError as error:",
        new="    try:\n        return actor\n    except SafeAPIError as error:",
        tests=[MAIN, SUSP],
    ),
    "A2-revoke-gate-removed": dict(
        file=SV,
        old="    staff = _authorise(\n        actor,\n        permission,\n        denied_action=denied_action,",
        new="    staff = actor\n    (lambda *a, **k: None)(\n        actor,\n        permission,\n        denied_action=denied_action,",
        tests=[MAIN, SUSP],
    ),
    "A3-extend-gate-removed": dict(
        file=SV,
        old="    staff = _authorise(\n        actor,\n        StaffPermission.EXTEND_LICENSE_KEY,\n        denied_action=EXTEND_PERMISSION_DENIED_ACTION,",
        new="    staff = actor\n    (lambda *a, **k: None)(\n        actor,\n        StaffPermission.EXTEND_LICENSE_KEY,\n        denied_action=EXTEND_PERMISSION_DENIED_ACTION,",
        tests=[MAIN, SUSP],
    ),
    "A4-gate-after-lookup-extend": dict(
        # moves the lookup BEFORE the gate: the ordering test must notice
        file=SV,
        old="    staff = _authorise(\n        actor,\n        StaffPermission.EXTEND_LICENSE_KEY,",
        new="    _get_license_key_or_not_found(data.license_key_id)\n    staff = _authorise(\n        actor,\n        StaffPermission.EXTEND_LICENSE_KEY,",
        tests=[MAIN],
    ),
    "A5-refusal-audit-per-actor-budget-removed": dict(
        file=SV,
        old="    if spend_budget(\n        REFUSAL_AUDIT_SCOPE, identity, REFUSAL_AUDIT_SETTING, REFUSAL_AUDIT_BUDGET\n    ) is BudgetOutcome.DENIED:\n        return\n",
        new="",
        tests=[MAIN],
    ),
    "A6-refusal-audit-global-cap-removed": dict(
        file=SV,
        old="    ) is BudgetOutcome.DENIED:\n        return\n\n    # No lookup:",
        new="    ) is None:\n        return\n\n    # No lookup:",
        tests=[MAIN],
    ),
    "A7-refusal-not-audited": dict(
        file=SV,
        old="        if denied_action is not None and actor is not None and error.code is ErrorCode.PERMISSION_DENIED:",
        new="        if False:",
        tests=[MAIN],
    ),
    "A8-hostile-reason-stored": dict(
        file=SV,
        old="    try:\n        reason = _require_reason_without_a_credential(raw_reason)\n    except SafeAPIError:\n        reason = \"\"\n",
        new="    reason = raw_reason\n",
        tests=[MAIN],
    ),
    "C1-credential-check-removed": dict(
        file=SV,
        old="    if _FULL_KEY_IN_TEXT_RE.search(reason):",
        new="    if False:",
        tests=[MAIN],
    ),
    # --- AC 9: depth bound ----------------------------------------------------------------
    "D1-depth-part-removed": dict(
        file=RD,
        old="        if depth > MAX_PAYLOAD_DEPTH or seen > MAX_PAYLOAD_CONTAINERS:",
        new="        if seen > MAX_PAYLOAD_CONTAINERS:",
        tests=[DEPTH, MAIN],
    ),
    "D0-both-bounds-removed": dict(
        file=RD,
        old="        if depth > MAX_PAYLOAD_DEPTH or seen > MAX_PAYLOAD_CONTAINERS:",
        new="        if False:",
        tests=[DEPTH],
    ),
    "D2-writer-boundary-check-removed": dict(
        file=SM,
        old="    ensure_payload_depth(extra_before or {})\n    ensure_payload_depth(extra_after or {})\n",
        new="",
        tests=[MAIN],
    ),
    "D3-container-cap-removed": dict(
        file=RD,
        old="        if depth > MAX_PAYLOAD_DEPTH or seen > MAX_PAYLOAD_CONTAINERS:",
        new="        if depth > MAX_PAYLOAD_DEPTH:",
        tests=[DEPTH],
    ),
    # --- AC 10: writer discipline ---------------------------------------------------------
    "W1-revoke-assigns-status-directly": dict(
        file=SV,
        old="    return apply_license_status_transition(\n        license_key,\n        to_status=to_status,",
        new="    license_key.status = to_status.value\n    license_key.save(update_fields=[\"status\"])\n    return apply_license_status_transition(\n        license_key,\n        to_status=to_status,",
        tests=[SMT],
    ),
    # --- extend behaviour -----------------------------------------------------------------
    "E1-source-precheck-removed": dict(
        file=SV,
        old="        if before_status not in EXTENDABLE_SOURCES:",
        new="        if False:",
        tests=[MAIN],
    ),
    "E2-not-forward-check-removed": dict(
        file=SV,
        old="        if new_expires_at <= old_expires_at:",
        new="        if False:",
        tests=[MAIN],
    ),
    "E3-ceiling-removed": dict(
        file=SV,
        old="    if instant <= now or instant > now + MAX_EXTENSION_FROM_NOW:",
        new="    if instant <= now:",
        tests=[MAIN],
    ),
    "E4-naive-accepted": dict(
        file=SV,
        old="    if not isinstance(value, datetime) or timezone.is_naive(value):",
        new="    if not isinstance(value, datetime):",
        tests=[MAIN],
    ),
    "E5-overlap-guard-removed": dict(
        file=SV,
        old="            require_no_overlapping_license_key(\n                customer,\n                starts_at=locked.starts_at,",
        new="            (lambda *a, **k: None)(\n                customer,\n                starts_at=locked.starts_at,",
        tests=[MAIN],
    ),
    "E6-retry-lookup-removed": dict(
        file=SV,
        old="        if earlier is not None:\n            return LicenseTransitionResult(\n                license_key=locked,",
        new="        if False:\n            return LicenseTransitionResult(\n                license_key=locked,",
        tests=[MAIN],
    ),
    "E7-catch-inside-removed": dict(
        file=SV,
        old="            except IllegalLicenseTransition as refusal:\n                writer_refusal = refusal",
        new="            except IllegalLicenseTransition as refusal:\n                raise",
        tests=[MAIN],
    ),
    "E8-autocommit-guard-removed-in-extend": dict(
        file=SV,
        old="    _require_autocommit()\n    _enforce_lifecycle_budget(staff)\n    idempotency_key = validate_idempotency_key(data.idempotency_key)",
        new="    _enforce_lifecycle_budget(staff)\n    idempotency_key = validate_idempotency_key(data.idempotency_key)",
        tests=[MAIN],
    ),
    "E9-extend-budget-removed": dict(
        file=SV,
        old="    _require_autocommit()\n    _enforce_lifecycle_budget(staff)\n    idempotency_key = validate_idempotency_key(data.idempotency_key)",
        new="    _require_autocommit()\n    idempotency_key = validate_idempotency_key(data.idempotency_key)",
        tests=[MAIN],
    ),
    "E10-status-not-restored": dict(
        file=SV,
        old="_EXTENDS_TO_ACTIVATED = frozenset({LicenseKeyStatus.EXPIRING, LicenseKeyStatus.EXPIRED})",
        new="_EXTENDS_TO_ACTIVATED = frozenset()",
        tests=[MAIN],
    ),
    "E11-date-move-skipped": dict(
        file=SV,
        old="    locked.expires_at = new_expires_at\n    locked.save(update_fields=[\"expires_at\", \"updated_at\"])",
        new="    pass",
        tests=[MAIN],
    ),
    "E12-archived-customer-allowed": dict(
        file=SV,
        old="        if customer.status == CustomerStatus.ARCHIVED:\n            raise _ExtendRefused(",
        new="        if False:\n            raise _ExtendRefused(",
        tests=[MAIN],
    ),
    # --- revoke behaviour -----------------------------------------------------------------
    "R1-revoke-targets-suspended": dict(
        file=SV,
        old="        to_status=LicenseKeyStatus.REVOKED,\n        raw_idempotency_key",
        new="        to_status=LicenseKeyStatus.SUSPENDED,\n        raw_idempotency_key",
        tests=[MAIN],
    ),
    "R2-revoke-retry-not-recognised": dict(
        file=SV,
        old="        recognise_retry=True,",
        new="        recognise_retry=False,",
        tests=[MAIN, SUSP],
    ),
    # --- Postgres-only (use engine=pg) ---------------------------------------------------
    "P1-extend-org-lock-removed": dict(
        file=SV,
        old="        customer = lock_customer_for_key_changes(license_key.customer_id)\n        locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)",
        new="        customer = CustomerOrg.objects.get(pk=license_key.customer_id)\n        locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)",
        tests=[PG],
    ),
    "P2-extend-licence-lock-removed": dict(
        file=SV,
        old="        locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)\n        try:\n            before_status",
        new="        locked = AppLicenseKey.objects.get(pk=license_key.pk)\n        try:\n            before_status",
        tests=[PG],
    ),
}


def run(engine, tests):
    script = f"{SP}/w2-86ak1090r-pytest-sb.sh" if engine == "sqlite" else f"{SP}/w2-86ak1090r-pgpytest-sb.sh"
    exitfile = f"{SP}/w2-86ak1090r-mut-{os.getpid()}.exit"
    if os.path.exists(exitfile):
        os.remove(exitfile)
    proc = subprocess.run(
        [script, exitfile, *tests, "-q", "-rf"],
        capture_output=True,
        text=True,
        timeout=1500,
    )
    out = proc.stdout + proc.stderr
    failed = sorted(set(re.findall(r"^FAILED (\S+)", out, re.M)))
    errors = sorted(set(re.findall(r"^ERROR (\S+)", out, re.M)))
    summary = out.strip().splitlines()[-1] if out.strip() else ""
    code = open(exitfile).read().strip() if os.path.exists(exitfile) else "no-exit-file"
    return code, failed, errors, summary


def main():
    engine = sys.argv[1]
    ids = sys.argv[2:]
    results = {}
    for mid in ids:
        spec = MUTANTS[mid]
        path = os.path.join(ROOT, spec["file"])
        backup = os.path.join(SP, f"w2-86ak1090r-backup-{os.getpid()}-" + os.path.basename(path))
        shutil.copyfile(path, backup)
        original = open(path, "rb").read()
        text = original.decode("utf-8")
        if text.count(spec["old"]) != 1:
            results[mid] = {"error": f"old string found {text.count(spec['old'])} times"}
            print(mid, results[mid], flush=True)
            continue
        mutated = text.replace(spec["old"], spec["new"], 1)
        try:
            open(path, "wb").write(mutated.encode("utf-8"))
            code, failed, errors, summary = run(engine, spec["tests"])
        finally:
            open(path, "wb").write(original)
        same = subprocess.run(["cmp", path, backup]).returncode == 0
        results[mid] = {
            "exit": code,
            "red": code != "exit=0",
            "failed": len(failed),
            "errors": len(errors),
            "summary": summary,
            "restored_identical": same,
            "sample": (failed + errors)[:4],
        }
        print(mid, json.dumps(results[mid]), flush=True)
        os.remove(backup)
    with open(f"{SP}/w2-86ak1090r-mutation-{engine}-{os.getpid()}.json", "w") as handle:
        json.dump(results, handle, indent=1)


main()
