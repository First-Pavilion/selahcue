"""Fixture controls for the stdlib-only Home anchor adapter."""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from home_anchor_capture import (
    build_home_anchor_provenance,
    emit_home_anchor_receipt,
    run_pricing_anchor_check,
)


TARGET_TOP_JS = "\n(id) => { const e = document.getElementById(id); return e ? e.getBoundingClientRect().top : null; }\n"
MESSAGE = "the navbar's How it works, clicked on /pricing, lands on the section clear of the bar"


class FakePage:
    def __init__(self, *, top=95, error_at=None, install_failed=False, controller_missing=False, cleanup_failed=False):
        self.log = []
        self.action_id = None
        self.top = top
        self.error_at = error_at
        self.sentinel = RuntimeError("private exception https://user:pass@example.test/")
        self.install_failed = install_failed
        self.controller_missing = controller_missing
        self.cleanup_failed = cleanup_failed

    def _step(self, stage, *args):
        self.log.append((stage, *args))
        if stage == self.error_at:
            raise self.sentinel

    def get_by_role(self, role, *, name):
        assert (role, name) == ("link", "How it works")
        return self

    @property
    def first(self):
        return self

    def click(self):
        self._step("click")

    def wait_for_url(self, url):
        self._step("url", url)

    def wait_for_timeout(self, ms):
        self._step("wait", ms)

    def evaluate(self, source, arg=None):
        if "function installHomeAnchorCapture" in source:
            self._step("arm")
            if self.install_failed:
                raise self.sentinel
            self.action_id = arg["actionId"]
            return {
                "installed": True, "actionId": self.action_id, "reasons": [],
                "snapshot": {"path": "pricing", "hash": "none", "target_present": False},
            }
        if ".finish(" in source:
            assert arg == self.action_id
            assert TARGET_TOP_JS in source
            self._step("sample")
            if self.controller_missing:
                return {"top": self.top, "same_controller": False, "capture": None}
            return {
                "top": self.top, "same_controller": True,
                "capture": {"complete": True, "counts": {"target_lookups": 1}, "reasons": []},
            }
        if ".dispose(" in source:
            self._step("dispose")
            if self.cleanup_failed:
                raise OSError("private cleanup exception")
            return {"complete": True, "reasons": []}
        assert source == TARGET_TOP_JS and arg == "how-it-works"
        self._step("sample")
        return self.top


class FakeRun:
    def __init__(self, page):
        self.page = page
        self.failures = []

    def near(self, top, want, tolerance, message):
        self.page.log.append(("near", top, want, tolerance, message))
        if top is None or abs(top - want) > tolerance:
            self.failures.append(message)


class BrokenSink:
    def write(self, text):
        raise OSError("private sink path")


class FlushFailure(io.StringIO):
    def flush(self):
        raise OSError("private sink path")


def run_action(page, sink=None):
    if sink is None:
        sink = io.StringIO()
    run = FakeRun(page)
    run_pricing_anchor_check(page, run, engine="webkit", target_top_js=TARGET_TOP_JS, provenance={}, sink=sink)
    return run, sink


class ActionTests(unittest.TestCase):
    def assert_action(self, page, prefix, top):
        self.assertEqual(page.log, [
            *prefix, ("click",), ("url", "**/#how-it-works"), ("wait", 1200), ("sample",),
            ("near", top, 95, 2, MESSAGE),
        ])

    def test_control_original_action_calls_once_in_order(self):
        page = FakePage(install_failed=True)
        run, _ = run_action(page)
        action_index = page.log.index(("click",))
        self.assert_action(page, page.log[:action_index], 95)
        self.assertFalse(run.failures)

    def test_pass_and_fail_preserve_action_order_and_write_linked_receipts(self):
        for top, expected in [(96.5, "pass"), (1686, "fail")]:
            with self.subTest(top=top):
                page = FakePage(top=top)
                run, sink = run_action(page)
                receipts = [json.loads(line) for line in sink.getvalue().splitlines()]
                self.assertEqual([receipt["phase"] for receipt in receipts], ["start", "terminal"])
                self.assert_action(page, [("arm",)], top)
                start, terminal = receipts
                self.assertEqual(terminal["outcome"], expected)
                self.assertEqual(bool(run.failures), expected == "fail")
                self.assertEqual(start["outcome"], "not_reached")
                self.assertRegex(start["action_id"], r"^[0-9a-f]{32}$")
                self.assertEqual(terminal["action_id"], start["action_id"])
                self.assertEqual(terminal["provenance"], start["provenance"])
                self.assertTrue(terminal["complete"])
                self.assertTrue(terminal["stages"]["measured"])
                self.assertEqual(terminal["target_top"], top)

    def test_install_failure_runs_original_measurement_once(self):
        page = FakePage(install_failed=True)
        _, sink = run_action(page)
        receipts = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(len(receipts), 2)
        terminal = receipts[-1]
        self.assertFalse(terminal["complete"])
        self.assertEqual(terminal["outcome"], "pass")
        self.assertIn("install_failed", terminal["reasons"])
        self.assertEqual(page.log.count(("arm",)), 1)
        prefix = page.log[:page.log.index(("click",))]
        self.assert_action(page, prefix, 95)

    def test_missing_controller_keeps_one_original_measurement_and_incomplete_receipt(self):
        page = FakePage(controller_missing=True)
        _, sink = run_action(page)
        receipts = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(len(receipts), 2)
        terminal = receipts[-1]
        self.assert_action(page, [("arm",)], 95)
        self.assertEqual(terminal["outcome"], "pass")
        self.assertFalse(terminal["complete"])
        self.assertIn("controller_missing", terminal["reasons"])
        self.assertIn("cleanup_incomplete", terminal["reasons"])
        self.assertIsNone(terminal["cleanup"])
        self.assertEqual(terminal["same_controller"], False)

    def test_action_exception_survives_cleanup_with_original_identity(self):
        for stage in ("click", "url", "sample"):
            with self.subTest(stage=stage):
                page = FakePage(error_at=stage)
                sink = io.StringIO()
                with self.assertRaises(RuntimeError) as error:
                    run_action(page, sink)
                self.assertIs(error.exception, page.sentinel)
                self.assertEqual(sum(entry[0] == stage for entry in page.log), 1)
                self.assertEqual(page.log[-1], ("dispose",))
                self.assertFalse(any(step[0] == "near" for step in page.log))
                receipts = [json.loads(line) for line in sink.getvalue().splitlines()]
                self.assertEqual(len(receipts), 2)
                terminal = receipts[-1]
                self.assertEqual(terminal["outcome"], "not_reached")
                self.assertIn("action_exception", terminal["reasons"])
                self.assertFalse(terminal["stages"]["measured"])
                self.assertNotIn("private exception", sink.getvalue())

    def test_cleanup_exception_is_contained_after_an_original_url_error(self):
        page = FakePage(error_at="url", cleanup_failed=True)
        sink = io.StringIO()
        with self.assertRaises(RuntimeError) as error:
            run_action(page, sink)
        self.assertIs(error.exception, page.sentinel)
        self.assertEqual(page.log, [("arm",), ("click",), ("url", "**/#how-it-works"), ("dispose",)])
        terminal = json.loads(sink.getvalue().splitlines()[-1])
        self.assertIn("cleanup_incomplete", terminal["reasons"])
        self.assertIsNone(terminal["cleanup"])
        self.assertNotIn("private cleanup", sink.getvalue())

    def test_sink_failures_preserve_original_pass_failure_and_exception(self):
        for sink in (BrokenSink(), FlushFailure()):
            for top in (95, 1686):
                with self.subTest(sink=type(sink), top=top):
                    page = FakePage(top=top)
                    run, _ = run_action(page, sink)
                    self.assertEqual(len(run.failures), int(top != 95))
                    self.assertEqual(page.log.count(("sample",)), 1)
            page = FakePage(error_at="url")
            with self.assertRaises(RuntimeError) as error:
                run_action(page, sink)
            self.assertIs(error.exception, page.sentinel)
            self.assertEqual(page.log.count(("url", "**/#how-it-works")), 1)
            self.assertEqual(page.log[-1], ("dispose",))


class ProjectionTests(unittest.TestCase):
    def test_provenance_accepts_only_fixed_context_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            helper, harness = [Path(directory) / name for name in ("helper", "harness")]
            helper.write_bytes(b"helper")
            harness.write_bytes(b"harness")
            with patch("home_anchor_capture.metadata.version", return_value="1.51.0"):
                gathered = build_home_anchor_provenance(
                    engine="webkit", browser_version="18.4",
                    environ={"GITHUB_SHA": "b" * 40, "GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "1",
                             "PRIVATE_TOKEN": "https://user:pass@example.test/"},
                    harness_path=harness, helper_path=helper,
                )
            self.assertEqual(gathered, {
                "engine": "webkit", "github_context_sha": "b" * 40, "github_run_id": "1234",
                "github_run_attempt": "1", "browser_version": "18.4", "playwright_version": "1.51.0",
                "helper_sha256": hashlib.sha256(b"helper").hexdigest(),
                "harness_sha256": hashlib.sha256(b"harness").hexdigest(),
            })
            gathered = build_home_anchor_provenance(
                engine="browser with arbitrary data", browser_version="18.4beta",
                environ={"GITHUB_SHA": "G" * 40, "GITHUB_RUN_ID": "1" * 21, "GITHUB_RUN_ATTEMPT": "１２３"},
                harness_path=harness / "missing", helper_path=helper / "missing",
            )
            for key in ("engine", "github_context_sha", "browser_version", "github_run_id", "github_run_attempt",
                        "helper_sha256", "harness_sha256"):
                self.assertIsNone(gathered[key])

    def test_malformed_fields_and_nonfinite_numbers_never_escape(self):
        secret = "https://user:secret@example.test/"
        sink = io.StringIO()
        emitted = emit_home_anchor_receipt({
            "phase": "terminal", "engine": "webkit", "outcome": "pass", "action_id": "a" * 32,
            "complete": True, "target_top": float("inf"), "reasons": [secret],
            "provenance": {"engine": "webkit", "github_context_sha": secret, "helper_sha256": "a" * 63,
                           "unknown": secret, "harness_sha256": "c" * 64},
            "capture": {"geometry": {"anchor_gap": float("nan"), "navbar_bottom": 1_000_000_001},
                        "commands": [{"top": 10 ** 400, "behavior": secret, "bogus": secret}] * 10000},
            "arbitrary": "ñ" * 30000 + secret,
        }, sink)
        self.assertTrue(emitted)
        output = sink.getvalue()
        self.assertLessEqual(len(output.encode("ascii")), 24 * 1024)
        for forbidden in (secret, "NaN", "Infinity", "bogus", "arbitrary"):
            self.assertNotIn(forbidden, output)
        receipt = json.loads(output)
        self.assertEqual(receipt["marker"], "home_anchor_capture")
        self.assertEqual(receipt["schema_version"], 1)
        self.assertEqual(receipt["action_id"], "a" * 32)
        self.assertIsNone(receipt["provenance"]["github_context_sha"])
        self.assertIsNone(receipt["provenance"]["helper_sha256"])
        self.assertEqual(receipt["provenance"]["harness_sha256"], "c" * 64)
        self.assertIsNone(receipt["target_top"])
        self.assertIsNone(receipt["capture"]["geometry"]["anchor_gap"])
        self.assertIsNone(receipt["capture"]["geometry"]["navbar_bottom"])
        self.assertEqual(len(receipt["capture"]["commands"]), 16)
        self.assertIsNone(receipt["capture"]["commands"][0]["top"])
        self.assertIsNone(receipt["capture"]["commands"][0]["behavior"])
        self.assertFalse(receipt["complete"])

    def test_full_bounded_payload_and_smaller_budget_export_fallback(self):
        action_id = "d" * 32
        counts = {
            "target_lookups": 16, "lookup_dropped": 0, "scroll_commands": 16, "command_dropped": 0,
            "route_observations": 16, "route_dropped": 0, "scroll_callbacks": 256, "mutation_callbacks": 128,
            "anchor_clicks": 1, "visibility_changes": 1, "pagehides": 1,
        }
        snapshot = {
            "path": "pricing", "hash": "none", "visibility": "visible", "font_status": "loaded",
            "reduced_motion": False, "inner_width": 1456, "client_width": 1440, "client_height": 900,
            "scroll_y": 0, "target_present": False,
        }
        cleanup = {"complete": True, "reasons": []}
        receipt = {
            "phase": "terminal", "engine": "webkit", "outcome": "fail", "action_id": action_id,
            "complete": True, "counts": counts, "target_top": 1686.750123456, "start_emitted": True,
            "same_controller": True, "arm": snapshot, "cleanup": cleanup,
            "stages": {"armed": True, "clicked": True, "url_matched": True, "waited": True, "measured": True,
                       "asserted": True},
            "provenance": {"engine": "webkit", "github_context_sha": "b" * 40, "github_run_id": "1" * 20,
                           "github_run_attempt": "1", "browser_version": "26.0", "playwright_version": "1.51.0",
                           "helper_sha256": "c" * 64, "harness_sha256": "d" * 64},
            "capture": {
                "counts": counts, "complete": True, "cleanup": cleanup, "first_presence_ms": 5.1,
                "first_presence_source": "mutation", "latest_route_observed_ms": 19.3,
                "snapshot": {**snapshot, "path": "home_anchor", "hash": "how_it_works", "target_present": True},
                "click": {"observed_ms": 1.4, "is_trusted": True},
                "scroll": {"first_ms": 10.1, "latest_ms": 15.9, "first_y": 0, "latest_y": 7.2,
                           "min_y": 0, "max_y": 7.2},
                "lifecycle": {"visibility": "visible", "visibility_ms": 30.7, "pagehide_ms": 12.8,
                              "pagehide_persisted": True},
                "geometry": {"document_target_top": 1686.750123456, "navbar_bottom": 79, "anchor_gap": 16,
                             "document_target_top_basis": "sequential_target_top_and_scroll_y"},
                "lookups": [{"present": True, "outcome": "returned", "entry_ms": 123456.789012345,
                             "return_ms": 123456.789012345}] * 16,
                "commands": [{"top": 1686.750123456, "left": 0, "behavior": "smooth", "outcome": "returned",
                              "overload": "options", "projection_quality": "post_call_own_data", "argument_count": 1,
                              "entry_ms": 123456.789012345, "return_ms": 123456.789012345}] * 16,
                "routes": [{"observed_ms": 123456.789012345, "path": "home_anchor",
                            "hash": "how_it_works", "source": "command"}] * 16,
            },
        }
        sink = io.StringIO()
        self.assertTrue(emit_home_anchor_receipt(receipt, sink))
        self.assertLessEqual(len(sink.getvalue().encode("ascii")), 24 * 1024)
        self.assertEqual(len(json.loads(sink.getvalue())["capture"]["commands"]), 16)

        smaller_sink = io.StringIO()
        with patch("home_anchor_capture.MAX_RECEIPT_BYTES", 1024):
            self.assertTrue(emit_home_anchor_receipt(receipt, smaller_sink))
        line = smaller_sink.getvalue()
        self.assertLessEqual(len(line.encode("ascii")), 1024)
        self.assertEqual(len(line.splitlines()), 1)
        exported = json.loads(line)
        self.assertEqual(exported["action_id"], action_id)
        self.assertEqual(exported["outcome"], "fail")
        self.assertEqual(exported["counts"]["target_lookups"], 16)
        self.assertIn("export_limit", exported["reasons"])
        self.assertFalse(exported["complete"])
        self.assertNotIn("capture", exported)


if __name__ == "__main__":
    unittest.main()
