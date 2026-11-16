"""Standalone qualification fixtures. No project imports or runtime services."""

import ast
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import qualify_license_generation as qualification


FILE = "tests/test_route.py"
SELECTOR = f"{FILE}::test_route"
EXTRA = f"{FILE}::test_extra[edge]"
SELECTED_VARIANT = f"{FILE}::test_parameter[allowed]"
WRONG_VARIANT = f"{FILE}::test_parameter[other]"
ASSERTION = "assert response.status_code == 200"
MISMATCH = r"\b500 == 200\b"
PHASES = ("setup", "call", "teardown")


# Literal identities from the accepted seven-control specification. These are
# independent of the configured manifest supplied to qualify_child.
MINIMAL_BASELINE = (
    "tests/test_free_license_lifecycle.py::test_expiring_free_refresh_keeps_live_bearer_and_commits_one_audit",
    "tests/test_free_license_concurrency_postgres.py::test_free_writer_refusal_rolls_back_and_leaves_one_denial",
    "tests/test_license_revoke_extend.py::test_extension_replay_refusal_and_failure_do_not_advance_generation[ACTIVATED]",
    "tests/test_license_revoke_extend.py::test_extension_replay_refusal_and_failure_do_not_advance_generation[EXPIRING]",
    "tests/test_license_revoke_extend.py::test_token_issuance_snapshots_latest_staff_generation",
    "tests/test_free_license_concurrency_postgres.py::test_frozen_clock_two_extensions_then_free_catchup_requires_replacement",
    "tests/test_concurrency_postgres.py::test_ordinary_refresh_does_not_wait_on_licence_write_lock",
)
WRONG_SEVENTH = "tests/test_license_revoke_extend.py::test_generation_overflow_is_atomic[ACTIVATED]"
# Preserve the retired configuration as an independent behavioral regression.
RETIRED_BASELINE = tuple(
    f"tests/{module}.py::{case}"
    for module, cases in (
        ("test_free_license_lifecycle", (
            "test_first_verified_admin_activation_issues_one_free_license",
            "test_expired_token_requires_admin_same_fingerprint_recovery",
            "test_completed_live_replay_leaves_managed_licence_and_receipt_unchanged[False]",
            "test_completed_live_replay_leaves_managed_licence_and_receipt_unchanged[True]",
            "test_expiring_free_refresh_keeps_live_bearer_and_commits_one_audit",
        )),
        ("test_free_license_concurrency_postgres", (
            "test_waiting_free_renewal_rechecks_committed_suspension[refresh]",
            "test_waiting_free_renewal_rechecks_committed_suspension[recover]",
            "test_migration_preserves_existing_licence_without_managing_it",
            "test_free_writer_refusal_rolls_back_and_leaves_one_denial",
            "test_free_success_audit_failure_rolls_back_the_status_expiry_and_bearer",
            "test_frozen_clock_two_extensions_then_free_catchup_requires_replacement",
            "test_refresh_rechecks_expiry_after_eligibility_lock[exact-expiry-assignment-renewal]",
            "test_refresh_rechecks_expiry_after_eligibility_lock[exact-expiry-assignment-catch-up]",
            "test_refresh_rechecks_expiry_after_eligibility_lock[exact-expiry-assignment-rotation]",
            "test_refresh_rechecks_expiry_after_eligibility_lock[exact-expiry-marker-renewal]",
            "test_refresh_rechecks_expiry_after_eligibility_lock[exact-expiry-marker-catch-up]",
            "test_refresh_rechecks_expiry_after_eligibility_lock[exact-expiry-marker-rotation]",
            "test_refresh_rechecks_expiry_after_eligibility_lock[before-expiry-assignment-renewal]",
            "test_refresh_rechecks_expiry_after_eligibility_lock[after-expiry-assignment-renewal]",
            "test_staff_write_and_managed_rotation_follow_row_lock_order[staff-first-extend]",
            "test_staff_write_and_managed_rotation_follow_row_lock_order[staff-first-revoke]",
            "test_staff_write_and_managed_rotation_follow_row_lock_order[refresh-first-extend]",
            "test_staff_write_and_managed_rotation_follow_row_lock_order[refresh-first-revoke]",
            "test_managed_pending_concurrent_rotation_has_one_winning_bearer",
            "test_managed_rotation_rechecks_bearer_after_waiting_to_supersede_sibling",
            "test_different_org_refreshes_do_not_lock_the_shared_fallback_plan[pure-free]",
            "test_different_org_refreshes_do_not_lock_the_shared_fallback_plan[staff-pending]",
            "test_refresh_assignment_lock_serializes_the_staff_assignment_writer",
        )),
        ("test_license_revoke_extend", (
            "test_extension_replay_refusal_and_failure_do_not_advance_generation[ACTIVATED]",
            "test_extension_replay_refusal_and_failure_do_not_advance_generation[EXPIRING]",
            "test_generation_overflow_is_atomic[ACTIVATED]",
            "test_generation_overflow_is_atomic[EXPIRING]",
            "test_token_issuance_snapshots_latest_staff_generation",
            "test_legacy_refresh_does_not_consume_staff_extension",
            "test_negotiated_staff_extension_rotates_ordinary_and_managed_free",
            "test_next_refresh_rotates_a_live_token_and_the_http_caller_adopts_it",
            "test_extension_never_lets_a_dead_token_rotate_itself[expired]",
            "test_extension_never_lets_a_dead_token_rotate_itself[revoked]",
            "test_extension_never_lets_a_dead_token_rotate_itself[device_revoked]",
            "test_rotation_failure_rolls_back_supersession_and_audit",
            "test_refresh_rechecks_token_expiry_after_licence_lock_wait",
            "test_refresh_rejects_token_generation_ahead_of_licence_before_writes",
            "test_refresh_negotiates_with_body_bearer_and_keeps_header_only_legacy",
        )),
        ("test_staff_extension_generation_migration", (
            "test_generation_migration_preserves_expiry_audits_receipts",
            "test_generation_backfill_ignores_invalid_target_and_never_resets_nonzero",
        )),
        ("test_concurrency_postgres", (
            "test_an_extension_and_a_first_activation_on_one_licence_never_deadlock[activation-first]",
            "test_an_extension_and_a_first_activation_on_one_licence_never_deadlock[extension-first]",
            "test_session_activation_and_extension_follow_the_org_then_licence_lock_order[activation-first]",
            "test_session_activation_and_extension_follow_the_org_then_licence_lock_order[extension-first]",
            "test_fifty_unaligned_extension_and_activation_races_never_deadlock_and_end_consistent",
            "test_the_activation_lock_names_the_licence_row_and_not_the_org_it_joins",
            "test_ordinary_refresh_does_not_wait_on_licence_write_lock",
        )),
        ("test_migration_remove_org_device_limit", (
            "test_the_migration_is_a_single_forward_remove_field",
            "test_every_key_grants_exactly_what_it_did_before",
            "test_the_scenarios_really_differ_so_equality_is_not_vacuous",
            "test_an_org_with_no_keys_survives_the_migration",
            "test_the_grandfathered_org_keeps_both_keys_each_with_its_own_limit",
        )),
        ("test_migration_receipt_token_delete", (
            "test_receipt_migration_reversal_and_reapply_preserve_rows_and_database_action",
        )),
    )
    for case in cases
)


def fake_plugin(directory, stream):
    """Run the generated plugin class with stand-ins for the pytest hook API."""
    bootstrap = ast.parse(qualification.BOOTSTRAP)
    evidence, = [node for node in bootstrap.body if isinstance(node, ast.ClassDef) and node.name == "Evidence"]
    namespace = {
        "pytest": SimpleNamespace(hookimpl=lambda **kwargs: lambda function: function),
        "receipt_dir": Path(directory), "sys": SimpleNamespace(__stdout__=stream),
        "hashlib": hashlib, "json": json, "math": math, "re": re, "time": time,
    }
    exec(compile(ast.Module(body=[evidence], type_ignores=[]), "<fake qualification plugin>", "exec"), namespace)
    return namespace["Evidence"]()


def finish_phase(plugin, item, phase, *, outcome="passed"):
    wrapper = getattr(plugin, f"pytest_runtest_{phase}")(item)
    next(wrapper)
    try:
        wrapper.send("unmodified hook result")
    except StopIteration as finish:
        assert finish.value == "unmodified hook result"
    plugin.pytest_runtest_logreport(SimpleNamespace(nodeid=item.nodeid, when=phase, outcome=outcome, duration=0.025))


def observed_progress(text):
    return [
        json.loads(line.removeprefix("LICQ "))
        for line in text.splitlines() if line.startswith("LICQ ")
    ]


class QualificationFixtures(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix="license-qualification-fixture-")
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name)
        self.junit = self.root / "junit.xml"
        self.collected = self.root / "collected.json"

    def evidence(self, *cases, collected=(SELECTOR,), calls=None):
        """Cases contain selector, optional outcome, and failure message and trace."""
        suite = ET.Element("testsuite", tests=str(len(cases)))
        for kind, attr in (("failure", "failures"), ("error", "errors"), ("skipped", "skipped")):
            suite.set(attr, str(sum(case[1] == kind for case in cases)))
        for selector, outcome, *detail in cases:
            file, name = selector.split("::", 1)
            case = ET.SubElement(suite, "testcase", classname=file[:-3].replace("/", "."), name=name)
            if outcome is not None:
                element = ET.SubElement(case, outcome, message=detail[0] if detail else "")
                if len(detail) == 2:
                    element.text = detail[1]
        ET.ElementTree(suite).write(self.junit, encoding="utf-8")
        if calls is None:
            calls = [[case[0], "passed" if case[1] is None else "failed"] for case in cases]
        receipt = {"nodes": collected, "calls": calls, "deselected": 0}
        self.collected.write_text(json.dumps(receipt), encoding="utf-8")

    def verify(self, returncode=0, *, mutant=False, expected=(SELECTOR,)):
        return qualification.verify_results(
            self.junit, self.collected, returncode, selectors=expected,
            failures={SELECTOR: (ASSERTION, MISMATCH)} if mutant else None,
        )

    def child(self, script, seconds=0.4):
        return qualification.run_child(
            [sys.executable, "-B", "-c", script], cwd=self.root, env=os.environ.copy(),
            deadline=time.monotonic() + seconds,
            stdout=self.root / "stdout.log", stderr=self.root / "stderr.log",
        )

    def baseline_child(self, nodes, *, configured=None, required=None):
        """Fake only the process boundary; keep stage/evidence verification real."""
        self.evidence(*[(node, None) for node in nodes], collected=nodes)
        with tempfile.TemporaryDirectory(dir=self.root) as area, ExitStack() as stack:
            scratch = Path(area)
            api = scratch / "api"
            evidence = scratch / "evidence"
            api.mkdir()
            evidence.mkdir()
            receipt = {"children": []}

            def passing_child(command, *, cwd, env, deadline, stdout, stderr):
                self.assertEqual(command[command.index("--junitxml") + 2:], list(nodes))
                stage = stdout.parent
                (stage / "junit.xml").write_bytes(self.junit.read_bytes())
                (stage / "collected.json").write_bytes(self.collected.read_bytes())
                (stage / "backend.json").write_text(json.dumps({
                    "vendor": "postgresql", "database": command[8], "server_version_num": 160016,
                    "installed_app": str(api / "selahcue_api" / "__init__.py"),
                }))
                stdout.write_text(
                    "ordinary refresh SQL statements: 3\n"
                    "ordinary refresh elapsed seconds: 0.012345\n"
                )
                stderr.write_bytes(b"")
                return 0

            stack.enter_context(patch.dict(os.environ, {
                "SQL_ENGINE": "django.db.backends.postgresql", "SQL_DATABASE": "selahcue_test",
                "SQL_USER": "selahcue", "SQL_HOST": "localhost", "SQL_PORT": "5432",
                "SQL_PASSWORD": "fixture-only", "CACHE_URL": "redis://localhost:6379/1",
                "CELERY_BROKER_URL": "redis://localhost:6379/2", "TEST_STT_REDIS_URL": "redis://localhost:6379/3",
                "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            }))
            stack.enter_context(patch.object(qualification, "run_child", passing_child))
            stack.enter_context(redirect_stdout(io.StringIO()))
            if configured is not None:
                stack.enter_context(patch.object(qualification, "BASELINE_SELECTORS", configured))
            if required is not None:
                stack.enter_context(patch.object(qualification, "REQUIRED", required))
            qualification.qualify_child(
                api, scratch, evidence, receipt, deadline=time.monotonic() + 0.9, index=0,
            )
            return json.loads((evidence / "receipt.json").read_text())["children"][0]

    def assert_minimal_baseline_passes(self, *, configured=None):
        try:
            record = self.baseline_child(MINIMAL_BASELINE, configured=configured)
        except qualification.QualificationError as error:
            self.fail(f"the exact seven-control baseline was refused: {error}")
        self.assertEqual(record["status"], "baseline-passed")
        self.assertEqual(record["files"], {
            "tests/test_free_license_lifecycle.py": 1,
            "tests/test_free_license_concurrency_postgres.py": 2,
            "tests/test_license_revoke_extend.py": 3,
            "tests/test_concurrency_postgres.py": 1,
        })
        self.assertEqual(record["sql_statements"], "3")
        self.assertEqual(record["ordinary_refresh_elapsed_seconds"], "0.012345")

    def test_default_baseline_runs_exact_seven_controls(self):
        self.assert_minimal_baseline_passes()

    def test_policy_accepts_exact_seven_with_complete_passing_evidence(self):
        self.assert_minimal_baseline_passes(configured=MINIMAL_BASELINE)

    def test_policy_rejects_retired_58_even_with_complete_passing_evidence(self):
        with self.assertRaisesRegex(qualification.QualificationError, "baseline manifest"):
            self.baseline_child(RETIRED_BASELINE, configured=RETIRED_BASELINE)

    def test_policy_rejects_wrong_seventh_even_with_complete_passing_evidence(self):
        wrong = (*MINIMAL_BASELINE[:-1], WRONG_SEVENTH)
        with self.assertRaisesRegex(qualification.QualificationError, "baseline manifest"):
            self.baseline_child(wrong, configured=wrong)

    def test_policy_rejects_missing_extra_duplicate_or_changed_parameter(self):
        for configured in (
            MINIMAL_BASELINE[:-1],
            (*MINIMAL_BASELINE, WRONG_SEVENTH),
            (*MINIMAL_BASELINE[:-1], MINIMAL_BASELINE[0]),
            (*MINIMAL_BASELINE[:2],
             "tests/test_license_revoke_extend.py::test_extension_replay_refusal_and_failure_do_not_advance_generation[EXPIRED]",
             *MINIMAL_BASELINE[3:]),
        ):
            with self.subTest(configured=configured):
                with self.assertRaisesRegex(qualification.QualificationError, "baseline manifest"):
                    self.baseline_child(configured, configured=configured)

    def test_policy_requires_six_unique_recipe_controls(self):
        # Seven recipe identities that already include ordinary refresh would
        # satisfy a union-only guard, so cardinality needs its own check.
        with self.assertRaisesRegex(qualification.QualificationError, "baseline manifest"):
            self.baseline_child(MINIMAL_BASELINE, configured=MINIMAL_BASELINE, required=MINIMAL_BASELINE)

    def test_exact_baseline_outcomes_pass(self):
        self.evidence((SELECTOR, None), (EXTRA, None), collected=(SELECTOR, EXTRA))
        self.verify(expected=(SELECTOR, EXTRA))

    def test_baseline_rejects_extra_identity_even_with_complete_passing_evidence(self):
        self.evidence(
            (SELECTOR, None), (SELECTED_VARIANT, None), (EXTRA, None),
            collected=(SELECTOR, SELECTED_VARIANT, EXTRA),
        )
        with self.assertRaises(qualification.QualificationError):
            self.verify(expected=(SELECTOR, SELECTED_VARIANT))

    def test_baseline_rejects_missing_identity_even_with_matching_call_and_junit_totals(self):
        self.evidence((SELECTOR, None))
        with self.assertRaises(qualification.QualificationError):
            self.verify(expected=(SELECTOR, SELECTED_VARIANT))

    def test_baseline_rejects_wrong_parameter_at_same_case_count(self):
        self.evidence((SELECTOR, None), (WRONG_VARIANT, None), collected=(SELECTOR, WRONG_VARIANT))
        with self.assertRaises(qualification.QualificationError):
            self.verify(expected=(SELECTOR, SELECTED_VARIANT))

    def test_baseline_rejects_duplicate_selected_identity(self):
        self.evidence(
            (SELECTOR, None), (SELECTED_VARIANT, None), (SELECTED_VARIANT, None),
            collected=(SELECTOR, SELECTED_VARIANT, SELECTED_VARIANT),
        )
        with self.assertRaises(qualification.QualificationError):
            self.verify(expected=(SELECTOR, SELECTED_VARIANT))

    def test_exact_behavioral_failure_qualifies_a_mutant(self):
        self.evidence((SELECTOR, "failure", "assert 500 == 200", "\n    " + ASSERTION))
        self.verify(1, mutant=True)

    def test_baseline_rejects_missing_collected_case(self):
        self.evidence((SELECTOR, None), collected=(SELECTOR, EXTRA))
        with self.assertRaises(qualification.QualificationError):
            self.verify(expected=(SELECTOR, EXTRA))

    def test_baseline_rejects_wrong_returncode(self):
        self.evidence((SELECTOR, None))
        with self.assertRaises(qualification.QualificationError):
            self.verify(1)

    def test_junit_cannot_replace_an_absent_call_phase(self):
        self.evidence((SELECTOR, "failure", "assert 500 == 200", ASSERTION), calls=[])
        with self.assertRaisesRegex(qualification.QualificationError, "call-phase"):
            self.verify(1, mutant=True)

    def test_progress_hard_kill_leaves_collection_and_the_last_attempted_phase(self):
        for stopped in PHASES:
            with self.subTest(stopped=stopped):
                script = (
                    "import sys, time; from types import SimpleNamespace; "
                    f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r}); "
                    "from test_qualify_license_generation import fake_plugin, finish_phase; "
                    "plugin = fake_plugin('.', sys.stdout); "
                    f"item = SimpleNamespace(nodeid={SELECTOR!r}); "
                    "plugin.pytest_collection_finish(SimpleNamespace(items=[item])); "
                    f"previous = {PHASES[:PHASES.index(stopped)]!r}; "
                    "[finish_phase(plugin, item, phase) for phase in previous]; "
                    f"hook = plugin.pytest_runtest_{stopped}(item); next(hook); time.sleep(0.75)"
                )
                with self.assertRaisesRegex(qualification.QualificationError, "deadline"):
                    self.child(script, seconds=0.35)
                progress = observed_progress((self.root / "stdout.log").read_text())
                self.assertTrue(progress, "hard termination left no progress")
                self.assertEqual(progress[0], ["collection", 1, [SELECTOR], False])
                self.assertEqual(progress[-1][:3], ["start", 0, stopped])
                self.assertFalse((self.root / "collected.json").exists())
                with self.assertRaises(qualification.QualificationError):
                    self.verify()

    def test_progress_is_indexed_and_does_not_change_the_final_call_receipt(self):
        stream = io.StringIO()
        plugin = fake_plugin(self.root, stream)
        items = [SimpleNamespace(nodeid=node) for node in (SELECTOR, EXTRA)]
        plugin.pytest_collection_finish(SimpleNamespace(items=items))
        for item in items:
            for phase in PHASES:
                finish_phase(plugin, item, phase)
        plugin.pytest_sessionfinish()
        self.assertEqual(json.loads((self.root / "collected.json").read_text()), {
            "nodes": [SELECTOR, EXTRA], "calls": [[SELECTOR, "passed"], [EXTRA, "passed"]], "deselected": 0,
        })
        progress = observed_progress(stream.getvalue())
        self.assertTrue(progress, "collection and phase timing were never written")
        self.assertEqual(progress[0][0:2], ["collection", 2])
        self.assertEqual(sum(event[0] == "collection" for event in progress), 1)
        self.assertEqual(
            [event[1:3] for event in progress if event[0] == "start"],
            [[index, phase] for index in range(2) for phase in PHASES],
        )
        results = [event for event in progress if event[0] == "result"]
        self.assertEqual([event[3:5] for event in results], [["passed", 25000]] * 6)
        elapsed = [event[-1] for event in progress[1:]]
        self.assertEqual(elapsed, sorted(elapsed))
        self.assertEqual(stream.getvalue().count(SELECTOR), 1)

    def test_progress_bounds_output_and_does_not_echo_parameter_values(self):
        stream = io.StringIO()
        plugin = fake_plugin(self.root, stream)
        plugin.MANIFEST_LIMIT = 180
        plugin.PROGRESS_LIMIT = 300
        items = [
            SimpleNamespace(nodeid=f"{SELECTOR}[sensitive fixture payload {index}]" + "secret" * 50)
            for index in range(20)
        ]
        plugin.pytest_collection_finish(SimpleNamespace(items=items))
        for item in items:
            for phase in PHASES:
                finish_phase(plugin, item, phase)
        data = stream.getvalue()
        self.assertNotIn("sensitive fixture payload", data)
        self.assertNotIn("secret", data)
        self.assertLessEqual(len(data.encode()), 300)
        progress = observed_progress(data)
        self.assertTrue(progress, "collection and explicit truncation were never written")
        self.assertEqual(progress[0][:2], ["collection", 20])
        self.assertTrue(progress[0][3])
        self.assertEqual(progress[-1], ["progress-truncated"])

    def test_progress_preserves_inner_hook_exceptions_and_bounds_report_values(self):
        stream = io.StringIO()
        plugin = fake_plugin(self.root, stream)
        item = SimpleNamespace(nodeid=SELECTOR)
        plugin.pytest_collection_finish(SimpleNamespace(items=[item]))
        wrapper = plugin.pytest_runtest_setup(item)
        next(wrapper)
        failure = RuntimeError("sensitive inner exception value")
        with self.assertRaises(RuntimeError) as raised:
            wrapper.throw(failure)
        self.assertIs(raised.exception, failure)
        plugin.pytest_runtest_logreport(SimpleNamespace(
            nodeid=SELECTOR, when="setup", outcome="sensitive report value", duration=math.inf,
        ))
        self.assertNotIn("sensitive", stream.getvalue())
        self.assertEqual(observed_progress(stream.getvalue())[-1][0:5], ["result", 0, "setup", "unknown", None])

    def test_baseline_rejects_a_case_hidden_in_a_nested_suite(self):
        self.evidence((SELECTOR, None))
        root = ET.parse(self.junit)
        ET.SubElement(ET.SubElement(root.getroot(), "testsuite"), "testcase", classname="tests.other", name="extra")
        root.write(self.junit, encoding="utf-8")
        with self.assertRaisesRegex(qualification.QualificationError, "nested JUnit"):
            self.verify()

    def test_rejects_malformed_or_oversized_xml(self):
        self.evidence((SELECTOR, None))
        for xml in (b"<testsuites>", b"x" * (qualification.MAX_OUTPUT + 1)):
            with self.subTest(size=len(xml)):
                self.junit.write_bytes(xml)
                with self.assertRaises(qualification.QualificationError):
                    self.verify()

    def test_rejects_skip_error_duplicate_extra_unexpected_pass_and_other_assertion(self):
        intended = (SELECTOR, "failure", "assert 500 == 200", ASSERTION)
        for cases in (
            ((SELECTOR, "skipped"),),
            ((SELECTOR, "error", "assert 500 == 200", ASSERTION),),
            (intended, intended),
            (intended, (EXTRA, None)),
            ((SELECTOR, None),),
            ((SELECTOR, "failure", "assert 500 == 200", "assert unrelated"),),
            ((SELECTOR, "failure", "assert 409 == 200", ASSERTION),),
        ):
            with self.subTest(cases=cases):
                self.evidence(*cases)
                with self.assertRaises(qualification.QualificationError):
                    self.verify(1, mutant=True)

    def test_rejects_wrong_junit_class_even_with_matching_test_name(self):
        self.evidence((SELECTOR, "failure", "assert 500 == 200", ASSERTION))
        self.junit.write_text(self.junit.read_text().replace("tests.test_route", "tests.other_route"))
        with self.assertRaisesRegex(qualification.QualificationError, "unexpected or duplicate"):
            self.verify(1, mutant=True)

    def test_restores_source_after_failing_and_timed_out_child(self):
        source = self.root / "source.py"
        original = b"generation = 1\n"
        source.write_bytes(original)
        for script, seconds in (("raise SystemExit(1)", 0.4), ("import time; time.sleep(0.6)", 0.2)):
            with self.subTest(seconds=seconds), self.assertRaises(qualification.QualificationError):
                with qualification.mutation(source, b"= 1", b"= 0", {source: original}):
                    self.assertEqual(source.read_bytes(), b"generation = 0\n")
                    status = self.child(script, seconds)
                    if status:
                        raise qualification.QualificationError("controlled child failed")
            with self.subTest(restored=seconds):
                self.assertEqual(source.read_bytes(), original)
            source.write_bytes(original)

    def test_rejects_nonunique_edit_without_changing_bytes(self):
        source = self.root / "source.py"
        original = b"generation = 1\nother = 1\n"
        source.write_bytes(original)
        with self.assertRaises(qualification.QualificationError):
            with qualification.mutation(source, b"= 1", b"= 0", {source: original}):
                pass
        self.assertEqual(source.read_bytes(), original)

    def test_normal_child_retains_separate_output(self):
        self.assertEqual(self.child("import sys; print('one'); print('two', file=sys.stderr)"), 0)
        self.assertEqual((self.root / "stdout.log").read_bytes(), b"one\n")
        self.assertEqual((self.root / "stderr.log").read_bytes(), b"two\n")

    def test_evidence_redacts_credentials_and_keeps_the_observed_assertion(self):
        device_token = b"SC-DEV-" + b"ABCD-" * 7 + b"ABCD"
        failure = b"assert 500 == 200\n"
        data = b"Authorization: Bearer " + device_token + b"\nSQL_PASSWORD=\"placeholder!\"\n" + failure
        redacted = qualification.redact_evidence(data)
        self.assertNotIn(device_token, redacted)
        self.assertNotIn(b"placeholder!", redacted)
        self.assertIn(failure, redacted)

    def test_child_stdout_overflow_is_refused_and_bounded(self):
        with self.assertRaises(qualification.QualificationError):
            self.child(f"import sys; sys.stdout.buffer.write(b'x' * {qualification.MAX_OUTPUT + 1})")
        self.assertLessEqual((self.root / "stdout.log").stat().st_size, qualification.MAX_OUTPUT)

    def test_owned_timeout_kills_a_pipe_holding_descendant(self):
        for parent_wait in (0.0, 0.7):
            with self.subTest(parent_wait=parent_wait):
                late_write = "from pathlib import Path; import time; time.sleep(0.45); Path('survived').touch()"
                script = (
                    "import subprocess, sys, time; "
                    f"subprocess.Popen([sys.executable, '-c', {late_write!r}]); "
                    f"print('started', flush=True); time.sleep({parent_wait})"
                )
                started = time.monotonic()
                with self.assertRaisesRegex(qualification.QualificationError, "deadline"):
                    self.child(script, 0.25)
                self.assertEqual((self.root / "stdout.log").read_text(), "started\n")
                self.assertLess(time.monotonic() - started, 1)
                time.sleep(0.5)
                self.assertFalse((self.root / "survived").exists())


if __name__ == "__main__":
    unittest.main()
