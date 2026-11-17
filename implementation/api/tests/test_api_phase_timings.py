"""Behavioral tests for the bounded API phase observer, using only the standard library."""

import math
import tracemalloc
import unittest

from api_phase_timings import ApiPhaseTimingBudget, ApiPhaseTimings


_REVOKE = "tests/test_license_revoke_extend.py"
_SUSPEND = "tests/test_license_suspend_reinstate.py"
_MARKER = "synthetic-token-DO-NOT-EMIT"


def _isolated_timings(selected):
    return ApiPhaseTimings(selected, budget=ApiPhaseTimingBudget())


def _records(timings, path, count):
    records = []
    for index in range(count):
        nodeid = f"{path}::test_matrix[{_MARKER}-{index}]"
        timings.observe(nodeid, "setup", 0.25)
        timings.observe(nodeid, "call", 0.5)
        timings.observe(nodeid, "teardown", 0.125)
        if record := timings.progress(nodeid):
            records.append(record)
    return records


def _fields(record):
    prefix, *fields = record.split()
    assert prefix == "SELAHCUE_API_PHASE_TIMING_V1"
    return dict(field.split("=", 1) for field in fields)


class ApiPhaseTimingsTests(unittest.TestCase):
    def test_only_fixed_relative_paths_are_observed(self):
        ignored = (
            "other/test_license_revoke_extend.py",
            "tests/test_license_suspend_reinstate.py.backup",
            "tests/test_unrelated.py",
        )
        timings = _isolated_timings((*ignored, _REVOKE, _SUSPEND))
        records = []
        for path in (*ignored, _REVOKE, _SUSPEND):
            records += _records(timings, path, 1)
        self.assertEqual(
            [_fields(record)["file"] for record in records],
            ["test_license_revoke_extend.py", "test_license_suspend_reinstate.py"],
        )
        self.assertEqual(list(timings.finish()), [])

    def test_counts_and_sums_each_report_phase_including_missing_call(self):
        nodeid = f"{_REVOKE}::test_matrix[{_MARKER}]"
        timings = _isolated_timings([nodeid, nodeid])
        timings.observe(nodeid, "setup", 0.5)
        timings.observe(nodeid, "teardown", 0.25)
        self.assertIsNone(timings.progress(nodeid))
        timings.observe(nodeid, "setup", 0.25)
        timings.observe(nodeid, "call", 1.5)
        timings.observe(nodeid, "teardown", 0.125)
        record = timings.progress(nodeid)
        self.assertIsNotNone(record)
        fields = _fields(record)
        self.assertEqual(
            fields,
            {
                "file": "test_license_revoke_extend.py",
                "selected": "2",
                "completed_teardowns": "2",
                "setup_reports": "2",
                "setup_seconds": "0.75",
                "call_reports": "1",
                "call_seconds": "1.5",
                "teardown_reports": "2",
                "teardown_seconds": "0.375",
            },
        )
        self.assertNotIn(_MARKER, record)
        self.assertNotIn("test_matrix", record)
        self.assertEqual(len(record.splitlines()), 1)

    def test_canonical_selection_emits_each_fifty_and_the_final_partial(self):
        timings = _isolated_timings([_REVOKE] * 375 + [_SUSPEND] * 178)
        revoke = _records(timings, _REVOKE, 375)
        suspend = _records(timings, _SUSPEND, 178)
        self.assertEqual(
            [int(_fields(record)["completed_teardowns"]) for record in revoke],
            [50, 100, 150, 200, 250, 300, 350, 375],
        )
        self.assertEqual(
            [int(_fields(record)["completed_teardowns"]) for record in suspend],
            [50, 100, 150, 178],
        )
        self.assertEqual(_fields(revoke[-1])["setup_seconds"], "93.75")
        self.assertEqual(_fields(suspend[-1])["call_seconds"], "89")
        self.assertEqual(list(timings.finish()), [])

    def test_exact_bucket_and_final_boundary_emits_once(self):
        timings = _isolated_timings([_REVOKE] * 100)
        records = _records(timings, _REVOKE, 100)
        self.assertEqual(
            [int(_fields(record)["completed_teardowns"]) for record in records], [50, 100]
        )
        self.assertIsNone(timings.progress(_REVOKE))
        self.assertEqual(list(timings.finish()), [])

    def test_early_finish_shows_observed_and_selected_counts_without_duplication(self):
        timings = _isolated_timings([_REVOKE] * 200 + [_SUSPEND] * 300)
        records = _records(timings, _REVOKE, 52)
        self.assertEqual(len(records), 1)
        self.assertEqual(_fields(records[0])["completed_teardowns"], "50")
        tail = list(timings.finish())
        self.assertEqual(len(tail), 1)
        self.assertEqual(_fields(tail[0])["completed_teardowns"], "52")
        self.assertEqual(_fields(tail[0])["selected"], "200")
        self.assertEqual(list(timings.finish()), [])

    def test_empty_ignored_and_new_sessions_are_independent(self):
        for selected in ([], ["tests/test_unrelated.py"]):
            with self.subTest(selected=selected):
                timings = _isolated_timings(selected)
                self.assertEqual(_records(timings, "tests/test_unrelated.py", 51), [])
                self.assertEqual(list(timings.finish()), [])

        active = _isolated_timings([_REVOKE] * 200)
        self.assertEqual(len(_records(active, _REVOKE, 50)), 1)
        fresh = _isolated_timings([_REVOKE])
        self.assertIsNone(fresh.progress(_REVOKE))
        records = _records(fresh, _REVOKE, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(_fields(records[0])["completed_teardowns"], "1")
        self.assertEqual(_fields(records[0])["setup_seconds"], "0.25")

    def test_twelve_line_cap_reserves_both_finals_under_larger_selection(self):
        timings = _isolated_timings([_REVOKE] * 751 + [_SUSPEND] * 800)
        records = _records(timings, _REVOKE, 751) + _records(timings, _SUSPEND, 800)
        records += list(timings.finish())
        self.assertEqual(len(records), 12)
        self.assertEqual(_fields(records[-2])["completed_teardowns"], "751")
        self.assertEqual(_fields(records[-1])["completed_teardowns"], "800")
        self.assertEqual(_fields(records[-2])["file"], "test_license_revoke_extend.py")
        self.assertEqual(_fields(records[-1])["file"], "test_license_suspend_reinstate.py")

    def test_successive_sessions_share_the_line_cap_and_reset_measurements(self):
        budget = ApiPhaseTimingBudget()
        first = ApiPhaseTimings([_REVOKE] * 400, budget=budget)
        first_records = _records(first, _REVOKE, 302) + first.finish()
        self.assertEqual(len(first_records), 7)
        self.assertEqual(_fields(first_records[-1])["completed_teardowns"], "302")

        for selected in ([], ["tests/test_unrelated.py"]):
            with self.subTest(selected=selected):
                ignored = ApiPhaseTimings(selected, budget=budget)
                self.assertEqual(_records(ignored, "tests/test_unrelated.py", 51), [])
                self.assertEqual(ignored.finish(), [])

        second = ApiPhaseTimings([_REVOKE] * 375 + [_SUSPEND] * 178, budget=budget)
        second_records = _records(second, _REVOKE, 375) + _records(second, _SUSPEND, 178)
        second_records += second.finish()
        self.assertEqual(len(first_records + second_records), 12)
        self.assertEqual(
            [int(_fields(record)["completed_teardowns"]) for record in second_records],
            [50, 100, 150, 375, 178],
        )
        self.assertEqual(_fields(second_records[0])["setup_seconds"], "12.5")
        self.assertEqual(_fields(second_records[0])["selected"], "375")

        exhausted = ApiPhaseTimings([_REVOKE] * 90, budget=budget)
        self.assertEqual(_records(exhausted, _REVOKE, 51) + exhausted.finish(), [])

    def test_nonfinite_durations_never_poison_numeric_output(self):
        timings = _isolated_timings([_REVOKE] * 2)
        for duration in (0.25, math.inf):
            timings.observe(_REVOKE, "setup", duration)
            timings.observe(_REVOKE, "call", math.nan)
            timings.observe(_REVOKE, "teardown", 1e308)
        record = timings.progress(_REVOKE)
        self.assertIsNotNone(record)
        fields = _fields(record)
        for phase in ("setup", "call", "teardown"):
            self.assertTrue(math.isfinite(float(fields[f"{phase}_seconds"])))
            self.assertEqual(fields[f"{phase}_reports"], "2")
        self.assertEqual(fields["setup_seconds"], "0.25")

    def test_retained_memory_stays_bounded_with_unique_parameter_ids(self):
        timings = _isolated_timings(_REVOKE for _ in range(20_100))
        already_tracing = tracemalloc.is_tracing()
        if not already_tracing:
            tracemalloc.start()
        try:
            _records(timings, _REVOKE, 100)
            before, _ = tracemalloc.get_traced_memory()
            _records(timings, _REVOKE, 20_000)
            after, _ = tracemalloc.get_traced_memory()
        finally:
            if not already_tracing:
                tracemalloc.stop()
        self.assertLess(after - before, 16_384)


if __name__ == "__main__":
    unittest.main()
