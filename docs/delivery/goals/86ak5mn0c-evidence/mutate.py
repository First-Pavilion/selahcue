#!/usr/bin/env python3
"""Mutation checks for 86ak5mn0c (staff suspend / reinstate), PR #218.

Every mutant alters ONE behaviour of the production code, runs the tests that are meant to
guard it with their siblings still running, and records which went red. A mutant is

* KILLED   - every test in `must_fail` went red (and at least one test failed);
* WEAK     - some test went red but not every `must_fail` one: the guard is incomplete;
* SURVIVED - nothing went red: the behaviour is unguarded.

The script exits non-zero if any mutant that is not declared `equivalent` is not KILLED. An
`equivalent` mutant is expected to survive (its edit cannot change observable behaviour); if
one is ever killed the script says so, so the declaration cannot go stale silently.

Safety: it edits production files in place, so it REFUSES to run unless

* the working tree is clean (so the restore is byte-exact and nothing of yours is touched),
* it is a linked git worktree and not the main checkout (so no other session shares it).

Each file is restored in a `finally` block and verified byte-for-byte; the tree must be clean
again when the run ends.

Usage, from a dedicated worktree of the branch:

    python docs/delivery/goals/86ak5mn0c-evidence/mutate.py --python <venv>/bin/python \
        [--postgres] [--only M01,M02] [--log run.log]

`--postgres` selects the Postgres-only mutants (row-lock races); the SQL_* environment
variables must already point at a disposable Postgres. Without it those mutants are listed
as SKIPPED and the script exits non-zero unless `--allow-skip` is given.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import subprocess
import sys

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

SVC = "selahcue_api/apps/license_keys/services.py"
SM = "selahcue_api/apps/license_keys/state_machine.py"
TASKS = "selahcue_api/apps/devices/tasks.py"
DEVSVC = "selahcue_api/apps/devices/services.py"
SCHEMA = "selahcue_api/graphql/admin_schema.py"
CTX = "selahcue_api/graphql/context.py"
ROUTES = "selahcue_api/graphql/route_contracts.py"
SETTINGS = "selahcue_api/settings.py"

MAIN = "tests/test_license_suspend_reinstate.py"
CASCADE = "tests/test_revocation_cascade.py"
PG = "tests/test_concurrency_postgres.py"
SM_TESTS = "tests/test_license_state_machine.py"


@dataclasses.dataclass
class Mutant:
    id: str
    what: str
    edits: list[tuple[str, str, str]]
    targets: list[str]
    must_fail: list[str]
    should_fail: list[str] = dataclasses.field(default_factory=list)
    pg: bool = False
    equivalent: bool = False


def m(id, what, edits, targets, must_fail, **kw):
    return Mutant(id, what, edits, targets, must_fail, **kw)


MUTANTS = [
    m("M01", "remove the staff permission gate",
      [(SVC, "    staff = require_staff_permission(actor, permission)\n", "    staff = actor\n")],
      [MAIN],
      ["test_suspend_is_refused_to_anyone_without_the_suspend_permission",
       "test_reinstate_is_refused_to_anyone_without_the_reinstate_permission",
       "test_an_unauthorised_caller_cannot_tell_whether_a_licence_exists"]),
    m("M02", "suspend is gated by the REVOKE permission instead",
      [(SVC, "        permission=StaffPermission.SUSPEND_LICENSE_KEY,", "        permission=StaffPermission.REVOKE_LICENSE_KEY,")],
      [MAIN], ["test_the_two_permissions_are_separate_authorities",
               "test_graphql_suspend_then_reinstate_happy_path"]),
    m("M03", "reinstate is gated by the SUSPEND permission instead",
      [(SVC, "        permission=StaffPermission.REINSTATE_LICENSE_KEY,", "        permission=StaffPermission.SUSPEND_LICENSE_KEY,")],
      [MAIN], ["test_the_two_permissions_are_separate_authorities"]),
    m("M04", "customer actors pass the kind check (service-level customer test must bite alone)",
      [(CTX, "    if actor.kind is not ActorKind.STAFF:\n        raise SafeAPIError(ErrorCode.PERMISSION_DENIED)\n    # An identity",
        "    # An identity")],
      [MAIN], ["test_suspend_is_refused_to_anyone_without_the_suspend_permission",
               "test_reinstate_is_refused_to_anyone_without_the_reinstate_permission"]),
    m("M05", "remove the in-transaction guard",
      [(SVC, "    _require_autocommit()\n    _enforce_lifecycle_budget(staff)", "    _enforce_lifecycle_budget(staff)")],
      [MAIN], ["test_a_call_inside_a_transaction_fails_closed_before_changing_anything"]),
    m("M06", "the writer never recognises a retry (lookup disabled)",
      [(SM, "            if recognise_retry:\n", "            if False:\n")],
      [MAIN],
      ["test_the_same_suspend_request_sent_twice_takes_effect_once",
       "test_the_same_reinstate_request_sent_twice_takes_effect_once",
       "test_a_duplicate_reinstate_after_another_staff_member_suspended_again_changes_nothing",
       "test_a_duplicate_suspend_after_another_staff_member_reinstated_changes_nothing",
       "test_a_stale_suspend_retry_cannot_undo_a_reinstatement_made_since",
       "test_a_stale_reinstate_retry_cannot_lift_a_later_suspension"]),
    m("M07", "the service does not ask the writer to recognise retries",
      [(SVC, "        recognise_retry=True,\n", "")],
      [MAIN], ["test_writes_go_through_the_state_machine_not_a_direct_status_write",
               "test_the_same_suspend_request_sent_twice_takes_effect_once"]),
    m("M08", "retry lookup ignores the action",
      [(SM, "            action=action,\n            target_type=AUDIT_TARGET_TYPE,\n            target_id=target_id,", "            target_type=AUDIT_TARGET_TYPE,\n            target_id=target_id,")],
      [MAIN], ["test_one_key_used_for_suspend_then_reinstate_is_two_requests"]),
    m("M09", "retry lookup ignores the actor",
      [(SM, "            actor_kind=actor.kind.value,\n            actor_id=actor.actor_id,\n            action=action,", "            action=action,")],
      [MAIN], ["test_another_staff_member_reusing_a_key_is_not_a_replay"]),
    m("M10", "retry lookup ignores the licence",
      [(SM, "            target_type=AUDIT_TARGET_TYPE,\n            target_id=target_id,\n            request_id=request_id,", "            target_type=AUDIT_TARGET_TYPE,\n            request_id=request_id,")],
      [MAIN], ["test_one_key_used_on_two_licences_is_two_requests_and_both_take_effect"]),
    m("M11", "retry lookup counts non-SUCCESS rows (EQUIVALENT: refusal rows carry a different action name)",
      [(SM, "            request_id=request_id,\n            result=AuditResult.SUCCESS,\n        )\n        .order_by", "            request_id=request_id,\n        )\n        .order_by")],
      [MAIN], [], equivalent=True),
    m("M12", "reinstate targets a hardcoded ACTIVATED instead of the recorded status",
      [(SVC, "        to_status=PRIOR_STATUS,", "        to_status=LicenseKeyStatus.ACTIVATED,")],
      [MAIN], ["test_reinstate_returns_the_exact_prior_status",
               "test_graphql_suspend_then_reinstate_happy_path"]),
    m("M13", "reinstate always lands on EXPIRED (activations then stay refused)",
      [(SM, "    return resolved\n\n\ndef _sync", "    return LicenseKeyStatus.EXPIRED\n\n\ndef _sync")],
      [MAIN], ["test_a_second_device_is_refused_while_suspended_and_admitted_after_reinstatement",
               "test_a_never_activated_licence_can_be_suspended_reinstated_and_then_first_activated",
               "test_reinstate_returns_the_exact_prior_status"]),
    m("M14", "the cascade kills SUSPENDED tokens again",
      [(TASKS, "    return Q(device__license_key__status__in=activatable) | Q(\n        device__license_key__status=LicenseKeyStatus.SUSPENDED,\n        device__license_key__prior_status__in=activatable,\n    )",
        "    return Q(device__license_key__status__in=activatable)")],
      [MAIN, CASCADE],
      ["test_suspension_leaves_every_issued_device_token_valid_through_a_cascade_run",
       "test_suspended_and_revoked_differ_observably_on_device_tokens",
       "test_cascade_kills_tokens_for_every_non_activatable_status_except_a_suspension_from_an_activatable_one"]),
    m("M15", "the cascade spares SUSPENDED whatever it was suspended from",
      [(TASKS, "        device__license_key__prior_status__in=activatable,\n", "")],
      [MAIN, CASCADE],
      ["test_the_cascade_spares_a_suspended_licences_tokens_only_if_it_came_from_an_activatable_status",
       "test_cascade_kills_tokens_for_every_non_activatable_status_except_a_suspension_from_an_activatable_one"]),
    m("M16", "the cascade also spares EXPIRED licences",
      [(TASKS, "    activatable = list(ACTIVATABLE_KEY_STATUSES)\n", "    activatable = list(ACTIVATABLE_KEY_STATUSES) + [LicenseKeyStatus.EXPIRED]\n")],
      [MAIN, CASCADE],
      ["test_cascade_kills_tokens_for_every_non_activatable_status_except_a_suspension_from_an_activatable_one"]),
    m("M17", "suspending a licence revokes its device tokens",
      [(SVC, "    return _lifecycle_mutation(\n        actor,\n        permission=StaffPermission.SUSPEND_LICENSE_KEY,",
        "    from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus\n"
        "    DeviceToken.objects.filter(device__license_key_id=int(data.license_key_id)).update(status=DeviceTokenStatus.REVOKED)\n"
        "    return _lifecycle_mutation(\n        actor,\n        permission=StaffPermission.SUSPEND_LICENSE_KEY,")],
      [MAIN], ["test_suspension_leaves_every_issued_device_token_valid_through_a_cascade_run",
               "test_suspension_touches_no_device_or_token_row"]),
    m("M18", "no throttle",
      [(SVC, "    _enforce_lifecycle_budget(staff)\n    idempotency_key", "    idempotency_key")],
      [MAIN], ["test_the_lifecycle_mutations_are_rate_limited_per_staff_member",
               "test_the_shipped_throttle_default_allows_thirty_calls_a_minute_and_refuses_the_next"]),
    m("M19", "one throttle bucket shared by every staff member",
      [(SVC, '    identity = hashlib.sha256(staff.actor_id.encode("utf-8")).hexdigest()[:32]', '    identity = "everyone"')],
      [MAIN], ["test_the_lifecycle_mutations_are_rate_limited_per_staff_member"]),
    m("M20", "the throttle is spent before the permission gate",
      [(SVC, "    staff = require_staff_permission(actor, permission)\n    _require_autocommit()\n    _enforce_lifecycle_budget(staff)\n",
        "    _enforce_lifecycle_budget(actor)\n    staff = require_staff_permission(actor, permission)\n    _require_autocommit()\n")],
      [MAIN], ["test_refused_callers_cannot_spend_a_staff_members_budget"]),
    m("M21", "the shipped budget default is ten times too generous",
      [(SETTINGS, "SELAHCUE_THROTTLE_ADMIN_LICENCE_LIFECYCLE = (30, 60)", "SELAHCUE_THROTTLE_ADMIN_LICENCE_LIFECYCLE = (300, 60)")],
      [MAIN], ["test_the_shipped_throttle_default_allows_thirty_calls_a_minute_and_refuses_the_next"]),
    m("M22", "lenient licence-id parsing",
      [(SVC, "        or not (cleaned.isascii() and cleaned.isdecimal())\n", "        or not cleaned.lstrip('+-').replace('_', '').isalnum()\n")],
      [MAIN], ["test_a_licence_reference_that_names_nothing_is_one_uniform_not_found",
               "test_spellings_of_a_real_licence_id_that_python_would_parse_do_not_resolve"]),
    m("M23", "an unknown licence is VALIDATION_FAILED instead of NOT_FOUND",
      [(SVC, "    except AppLicenseKey.DoesNotExist as error:\n        raise SafeAPIError(ErrorCode.NOT_FOUND) from error", "    except AppLicenseKey.DoesNotExist as error:\n        raise SafeAPIError(ErrorCode.VALIDATION_FAILED) from error")],
      [MAIN], ["test_a_licence_reference_that_names_nothing_is_one_uniform_not_found"]),
    m("M24", "the NOT_FOUND refusal carries a bespoke message (a lookup oracle)",
      [(SVC, "        or not (cleaned.isascii() and cleaned.isdecimal())\n    ):\n        raise SafeAPIError(ErrorCode.NOT_FOUND)",
        "        or not (cleaned.isascii() and cleaned.isdecimal())\n    ):\n        raise SafeAPIError(ErrorCode.NOT_FOUND, 'malformed licence reference')")],
      [MAIN], ["test_a_licence_reference_that_names_nothing_is_one_uniform_not_found"]),
    m("M25", "idempotency keys are not validated",
      [(SVC, "    idempotency_key = validate_idempotency_key(raw_idempotency_key)\n", "    idempotency_key = raw_idempotency_key\n")],
      [MAIN], ["test_an_invalid_idempotency_key_is_refused"]),
    m("M26", "the writer is handed a different reason",
      [(SVC, "        reason=reason,\n        request_id=idempotency_key,", "        reason='Placeholder reason text',\n        request_id=idempotency_key,")],
      [MAIN], ["test_suspend_succeeds_from_every_suspendable_status_and_records_where_it_came_from",
               "test_reinstate_returns_the_exact_prior_status"]),
    m("M27", "the admin read type reports no prior status",
      [(SCHEMA, "        prior_status=license_key.prior_status,\n        key_prefix=license_key.key_prefix,\n        key_suffix=license_key.key_suffix,\n        masked_key=license_key.masked_key,\n        feature_scope=license_key.feature_scope,\n        starts_at=license_key.starts_at.isoformat(),\n        expires_at=license_key.expires_at.isoformat(),\n    )\n\n\ndef license_key_to_type",
        "        prior_status='',\n        key_prefix=license_key.key_prefix,\n        key_suffix=license_key.key_suffix,\n        masked_key=license_key.masked_key,\n        feature_scope=license_key.feature_scope,\n        starts_at=license_key.starts_at.isoformat(),\n        expires_at=license_key.expires_at.isoformat(),\n    )\n\n\ndef license_key_to_type")],
      [MAIN], ["test_graphql_suspend_then_reinstate_happy_path"]),
    m("M28", "the suspend payload returns the full licence view, customer included",
      [(SCHEMA, "class AdminSuspendLicenseKeyPayload:\n    license_key: AdminLicenseKeySummary", "class AdminSuspendLicenseKeyPayload:\n    license_key: AdminLicenseKey"),
       (SCHEMA, "        return AdminSuspendLicenseKeyPayload(\n            license_key=license_key_to_summary(result.license_key),", "        return AdminSuspendLicenseKeyPayload(\n            license_key=license_key_to_type(result.license_key),")],
      [MAIN], ["test_a_suspend_only_actor_cannot_read_customer_details_through_the_payload"]),
    m("M29", "a replayed request is never flagged",
      [(SCHEMA, "    return (not result.changed) and result.audit_event is not None", "    return False")],
      [MAIN], ["test_graphql_retry_reports_changed_false"]),
    m("M30", "actor ids longer than the audit column are accepted (service gate)",
      [(CTX, "    if not actor.actor_id or len(actor.actor_id) > ACTOR_ID_MAX_LENGTH:", "    if not actor.actor_id:")],
      [MAIN], ["test_an_actor_id_longer_than_the_audit_column_is_refused_before_any_write"]),
    m("M31", "actor ids longer than the audit column are accepted (header bridge)",
      [(CTX, "    if not kind_value or not actor_id or len(actor_id) > ACTOR_ID_MAX_LENGTH:", "    if not kind_value or not actor_id:")],
      [MAIN], ["test_the_header_bridge_drops_an_actor_id_longer_than_the_audit_column"]),
    m("M32", "the commercial gate admits any licence status",
      [(DEVSVC, "    if license_key.status not in ACTIVATABLE_KEY_STATUSES:\n        raise SafeAPIError(ErrorCode.POLICY_DENIED)\n    if not (license_key.starts_at <= now < license_key.expires_at):",
        "    if not (license_key.starts_at <= now < license_key.expires_at):")],
      [MAIN], ["test_the_enforcement_point_admits_only_activatable_statuses",
               "test_a_suspended_licence_refuses_manifest_issuance_and_reinstatement_restores_it",
               "test_a_suspended_licence_refuses_a_new_activation_with_a_coded_error"]),
    m("M33", "the commercial gate ignores the licence window",
      [(DEVSVC, "    if not (license_key.starts_at <= now < license_key.expires_at):\n        raise SafeAPIError(ErrorCode.POLICY_DENIED)\n\n\ndef _new_device_token",
        "\n\ndef _new_device_token")],
      [MAIN], ["test_the_enforcement_point_also_refuses_outside_the_licence_window"]),
    m("M34", "the manifest route is declared allowed while suspended but still enforces",
      [(ROUTES, '"desktop", "v1/entitlements/manifest", "GET", "device_token",\n            licence_gate=LICENCE_GATE_COMMERCIAL,',
        '"desktop", "v1/entitlements/manifest", "GET", "device_token",\n            licence_gate=LICENCE_GATE_ALLOWED_WHILE_SUSPENDED,')],
      [MAIN], ["test_each_declaration_matches_what_the_route_does_for_a_suspended_licence"]),
    m("M35", "a device-token route stops declaring a licence gate",
      [(ROUTES, '"desktop", "v1/usage-events:batch", "POST", "device_token",\n            licence_gate=LICENCE_GATE_COMMERCIAL,',
        '"desktop", "v1/usage-events:batch", "POST", "device_token",')],
      [MAIN], ["test_every_device_token_route_declares_how_it_treats_a_suspended_licence"]),
    m("M36", "assign the licence status directly instead of going through the writer",
      [(SVC, "    return apply_license_status_transition(\n        license_key,\n        to_status=to_status,",
        "    if to_status == LicenseKeyStatus.SUSPENDED:\n        AppLicenseKey.objects.filter(pk=license_key.pk).update(status='SUSPENDED', prior_status=license_key.status)\n        return LicenseTransitionResult(license_key, LicenseKeyStatus(license_key.status), LicenseKeyStatus.SUSPENDED, True, None)\n    return apply_license_status_transition(\n        license_key,\n        to_status=to_status,")],
      [MAIN, SM_TESTS], ["test_no_production_module_writes_a_licence_status_outside_the_state_machine",
                         "test_writes_go_through_the_state_machine_not_a_direct_status_write"]),
    # ---- Postgres-only: the row lock and the lookup UNDER it -------------------------------
    m("P01", "the writer no longer locks the licence row",
      [(SM, "locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)", "locked = AppLicenseKey.objects.get(pk=license_key.pk)")],
      [PG],
      ["test_a_suspension_that_wins_the_race_against_a_first_activation_refuses_the_device",
       "test_a_suspension_that_loses_the_race_against_a_first_activation_suspends_the_activated_licence",
       "test_a_suspension_racing_a_revoke_leaves_a_consistent_trail_whichever_wins",
       "test_two_concurrent_suspensions_write_exactly_one_audit_row",
       "test_a_reinstate_retried_while_the_original_is_in_flight_succeeds_once_and_never_errors",
       "test_a_duplicate_request_with_another_staff_action_between_the_copies_is_not_reapplied",
       "test_concurrent_transitions_write_exactly_one_audit_row"],
      pg=True),
    m("P02", "the writer never recognises a retry (lookup disabled)",
      [(SM, "            if recognise_retry:\n", "            if False:\n")],
      [PG],
      ["test_a_reinstate_retried_while_the_original_is_in_flight_succeeds_once_and_never_errors"],
      should_fail=["test_a_duplicate_request_with_another_staff_action_between_the_copies_is_not_reapplied"],
      pg=True),
    m("P03", "the retry lookup runs BEFORE the row lock (the pre-lock shape this PR replaced)",
      [(SM, "        with transaction.atomic():\n            locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)\n            before = _coerce_status(locked.status)\n            before_prior = locked.prior_status\n\n            if recognise_retry:\n                earlier = _earlier_success(\n                    actor,\n                    action=_intended_action(requested, cleaned_action),\n                    target_id=str(locked.pk),\n                    request_id=cleaned_request_id,\n                )\n                if earlier is not None:\n                    _sync(license_key, locked)\n                    return LicenseTransitionResult(\n                        license_key=locked,\n                        from_status=before,\n                        to_status=before,\n                        changed=False,\n                        audit_event=earlier,\n                    )\n",
        "        pre = None\n        if recognise_retry:\n            pre = _earlier_success(\n                actor,\n                action=_intended_action(requested, cleaned_action),\n                target_id=str(license_key.pk),\n                request_id=cleaned_request_id,\n            )\n        with transaction.atomic():\n            locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)\n            before = _coerce_status(locked.status)\n            before_prior = locked.prior_status\n\n            if pre is not None:\n                _sync(license_key, locked)\n                return LicenseTransitionResult(\n                    license_key=locked,\n                    from_status=before,\n                    to_status=before,\n                    changed=False,\n                    audit_event=pre,\n                )\n")],
      [PG],
      ["test_a_reinstate_retried_while_the_original_is_in_flight_succeeds_once_and_never_errors"],
      should_fail=["test_a_duplicate_request_with_another_staff_action_between_the_copies_is_not_reapplied"],
      pg=True),
    m("P04", "actor ids longer than the audit column are accepted (Postgres: the DENIED row is lost)",
      [(CTX, "    if not actor.actor_id or len(actor.actor_id) > ACTOR_ID_MAX_LENGTH:", "    if not actor.actor_id:")],
      [MAIN + "::test_an_actor_id_longer_than_the_audit_column_is_refused_before_any_write",
       MAIN + "::test_an_actor_id_at_the_limit_still_gets_a_clean_conflict_and_a_durable_denial"],
      ["test_an_actor_id_longer_than_the_audit_column_is_refused_before_any_write"],
      pg=True),
]


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def refuse_unless_safe():
    if git("status", "--porcelain").strip():
        sys.exit("refusing to run: the working tree is not clean (commit or stash your changes)")
    if git("rev-parse", "--git-dir").strip() == git("rev-parse", "--git-common-dir").strip():
        sys.exit("refusing to run in the main checkout: use a dedicated linked worktree")


def run_mutant(mutant, python, log):
    originals = {}
    try:
        for rel, old, new in mutant.edits:
            path = API / rel
            originals.setdefault(rel, path.read_bytes())
            text = path.read_text(encoding="utf-8")
            if text.count(old) != 1:
                return "ERROR", f"edit pattern matched {text.count(old)} times in {rel}", []
            path.write_text(text.replace(old, new), encoding="utf-8")
        proc = subprocess.run(
            [python, "-m", "pytest", *mutant.targets, "-q", "-p", "no:cacheprovider",
             "--maxfail=1000", "-rf"],
            cwd=API, capture_output=True, text=True,
        )
        output = proc.stdout + proc.stderr
        log.write(f"\n===== {mutant.id} {mutant.what}\n{output[-6000:]}\n")
        red = sorted({re.sub(r"\[.*", "", f.split("::")[-1]) for f in re.findall(r"^FAILED (\S+)", output, re.M)})
        summary = output.strip().splitlines()[-1] if output.strip() else "?"
        return summary, "", red
    finally:
        for rel, original in originals.items():
            path = API / rel
            path.write_bytes(original)
            if path.read_bytes() != original:
                sys.exit(f"FATAL: could not restore {rel}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True)
    parser.add_argument("--postgres", action="store_true", help="run only the Postgres mutants")
    parser.add_argument("--allow-skip", action="store_true")
    parser.add_argument("--only")
    parser.add_argument("--check", action="store_true", help="only verify every edit pattern matches once")
    parser.add_argument("--log", default="mutation.log")
    args = parser.parse_args()

    if args.check:
        bad = 0
        for mutant in MUTANTS:
            for rel, old, _new in mutant.edits:
                count = (API / rel).read_text(encoding="utf-8").count(old)
                if count != 1:
                    bad += 1
                    print(f"{mutant.id}: pattern matches {count} times in {rel}")
        print("all patterns match exactly once" if not bad else f"{bad} bad pattern(s)")
        sys.exit(1 if bad else 0)
    refuse_unless_safe()
    selected = [mu for mu in MUTANTS if not args.only or mu.id in args.only.split(",")]
    failures = 0
    results = []
    with open(args.log, "w") as log:
        for mutant in selected:
            if mutant.pg != args.postgres:
                results.append((mutant, "SKIPPED", "needs --postgres" if mutant.pg else "SQLite mutant", []))
                continue
            summary, error, red = run_mutant(mutant, args.python, log)
            if error:
                status = "ERROR"
            elif mutant.equivalent:
                status = "EQUIVALENT-SURVIVED" if not red else "EQUIVALENT-KILLED (declaration is stale)"
            elif not red:
                status = "SURVIVED"
            elif all(any(name == r for r in red) for name in mutant.must_fail):
                status = "KILLED"
            else:
                status = "WEAK"
            if status not in ("KILLED", "EQUIVALENT-SURVIVED") and not status.startswith("EQUIVALENT"):
                failures += 1
            missing = [n for n in mutant.must_fail if n not in red]
            probable = [n for n in mutant.should_fail if n not in red]
            line = f"{mutant.id} {status}: {mutant.what} | {summary} | {len(red)} red"
            if missing:
                line += f" | NOT RED: {missing}"
            if probable:
                line += f" | probabilistic guard stayed green this run: {probable}"
            if error:
                line += f" | {error}"
            print(line, flush=True)
            log.write(f"{line}\n")
    skipped = [mu for mu, status, *_ in results if status == "SKIPPED" and mu.pg and not args.postgres]
    for mutant, status, why, _ in results:
        print(f"{mutant.id} {status}: {mutant.what} ({why})")
    if skipped and not args.allow_skip:
        print("some Postgres mutants were not run; pass --allow-skip or run with --postgres")
        failures += 1
    if git("status", "--porcelain").strip():
        print("FATAL: the tree is dirty after the run")
        failures += 1
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
