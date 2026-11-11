"""Clearly synthetic fixtures: these exercise bookkeeping, never ASR quality."""
import copy
import importlib.util
import json
import stat
import tracemalloc
from types import SimpleNamespace
from unittest import mock
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sermon_pilot_eval", ROOT / "scripts/sermon_pilot_eval.py")
# A missing evaluator is an explicit assertion failure during the initial RED run.
if SPEC.origin and Path(SPEC.origin).exists():
    evaluator = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(evaluator)
else:
    evaluator = None

LANGUAGES = ["English", "Yoruba", "Igbo", "Hausa"]

def fixture():
    profile = dict(id="baseline", engine_sha256="a" * 64, model_sha256="b" * 64,
                   config_sha256="c" * 64, languages=LANGUAGES, rights_source="synthetic test only",
                   configuration={"synthetic": True}, role="production_baseline")
    samples = [dict(id=language, audio_sha256="d" * 64, speaker_id=language,
                    languages=[language], split="held_out", duration_ms=1000,
                    reference_text="synthetic reference words", expected_references=["John 3:16"],
                    authorized_use=True, scenario="ordinary_speech") for language in LANGUAGES]
    corpus = dict(schema_version=1, expected_profiles=[profile], samples=samples,
                  evidence_kind="synthetic")
    runs = [dict(corpus_id=sample["id"], profile_id="baseline", engine_sha256="a" * 64,
                 model_sha256="b" * 64, config_sha256="c" * 64,
                 segments=[dict(text=sample["reference_text"], start_ms=0, end_ms=1000, is_final=True)],
                 omission_count=0, error_count=0, latency_ms=30, peak_process_tree_memory_bytes=1024,
                 dropped_audio_count=0, switch_recovery_ms=None,
                 retrieval={"references": ["John 3:16"], "query_source": "asr"}) for sample in samples]
    return corpus, runs

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(evaluator, "evaluator implementation is missing")
        self.corpus, self.runs = fixture()

    def report(self):
        return evaluator.evaluate(self.corpus, self.runs)

    def test_missing_language_is_incomplete(self):
        self.corpus["samples"] = self.corpus["samples"][:2] + self.corpus["samples"][3:]
        self.runs = [r for r in self.runs if r["corpus_id"] != "Igbo"]
        report = self.report()
        self.assertEqual(report["outcome"], "insufficient")
        self.assertIn("Igbo", report["coverage"]["missing_languages"])
        self.assertIsNone(report["per_profile"][0]["per_language"]["Igbo"]["word_error_rate"])

    def test_overlapping_speakers_across_splits_is_rejected(self):
        extra = copy.deepcopy(self.corpus["samples"][0])
        extra.update(id="tuning", split="tuning")
        self.corpus["samples"].append(extra)
        with self.assertRaisesRegex(ValueError, "speaker.*splits"):
            self.report()

    def test_missing_model_result_is_failure(self):
        other = copy.deepcopy(self.corpus["expected_profiles"][0])
        other.update(id="absent-model", model_sha256="e" * 64, role="experimental")
        self.corpus["expected_profiles"].append(other)
        report = self.report()
        self.assertEqual(report["outcome"], "insufficient")
        self.assertEqual(report["per_profile"][1]["missing_run_ids"], LANGUAGES)
        self.assertEqual(report["per_profile"][1]["completed_runs"], 0)

    def test_poor_igbo_result_is_not_hidden_by_english(self):
        self.runs[2]["segments"][0]["text"] = "wrong unrelated tokens"
        report = self.report()
        language = report["per_profile"][0]["per_language"]
        self.assertEqual(language["English"]["word_error_rate"], 0)
        self.assertEqual(language["Igbo"]["word_error_rate"], 1)
        self.assertEqual(report["outcome"], "insufficient")

    def test_silence_hallucination_counts_as_error(self):
        self.corpus["samples"][0].update(reference_text="", scenario="silence", expected_references=[])
        self.runs[0]["segments"][0]["text"] = "invented speech"
        language = self.report()["per_profile"][0]["per_language"]["English"]
        self.assertEqual(language["insertions"], 2)
        self.assertEqual(language["silence_hallucination_words"], 2)
        self.assertIsNone(language["word_error_rate"])

    def test_every_supplied_sample_requires_each_expected_run(self):
        self.runs.pop()
        profile = self.report()["per_profile"][0]
        self.assertEqual(profile["missing_run_ids"], ["Hausa"])
        self.assertFalse(profile["complete"])

    def test_missing_metrics_are_unknown(self):
        del self.runs[0]["latency_ms"]
        del self.runs[0]["peak_process_tree_memory_bytes"]
        del self.runs[0]["omission_count"]
        profile = self.report()["per_profile"][0]
        row = profile["samples"][0]
        self.assertIsNone(row["latency_ms"])
        self.assertIsNone(row["peak_process_tree_memory_bytes"])
        self.assertIsNone(row["omission_count"])
        self.assertIn("latency_ms", row["missing_metrics"])
        self.assertFalse(profile["complete"])

    def test_mixed_language_errors_are_not_assigned_to_each_language(self):
        self.corpus["samples"][0]["languages"] = ["English", "Igbo"]
        self.runs[0]["segments"][0]["text"] = "wrong"
        profile = self.report()["per_profile"][0]
        self.assertEqual(profile["per_language"]["English"]["scored_monolingual_samples"], 0)
        self.assertIsNone(profile["per_language"]["English"]["word_error_rate"])
        self.assertEqual(profile["mixed_language"]["scored_samples"], 1)
        self.assertGreater(profile["mixed_language"]["word_error_rate"], 0)

    def test_reports_never_contain_sermon_text(self):
        report = self.report()
        self.assertNotIn("synthetic reference words", json.dumps(report))
        self.assertNotIn("reference_text", json.dumps(report))
        self.assertNotIn('"segments"', json.dumps(report))

    def test_bad_hash_unauthorized_duplicate_and_unknown_runs_rejected(self):
        mutations = [lambda c, r: c["samples"][0].update(authorized_use=False),
                     lambda c, r: r[0].update(model_sha256="f" * 64),
                     lambda c, r: r.append(copy.deepcopy(r[0])),
                     lambda c, r: r[0].update(corpus_id="unknown"),
                     lambda c, r: c["samples"][0].update(audio_sha256="bad")]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.corpus, self.runs = fixture()
                mutation(self.corpus, self.runs)
                with self.assertRaises(ValueError):
                    self.report()

    def test_invalid_timing_numeric_and_missing_segments_rejected(self):
        for field, value in [("latency_ms", -1), ("dropped_audio_count", True),
                             ("latency_ms", float("nan"))]:
            with self.subTest(field=field, value=value):
                self.corpus, self.runs = fixture()
                self.runs[0][field] = value
                with self.assertRaises(ValueError): self.report()
        self.corpus, self.runs = fixture()
        self.runs[0]["segments"][0]["end_ms"] = 2000
        with self.assertRaises(ValueError): self.report()
        self.corpus, self.runs = fixture()
        del self.runs[0]["segments"]
        with self.assertRaises(ValueError): self.report()

    def test_interims_do_not_duplicate_final_and_retrieval_is_separate(self):
        self.runs[0]["segments"].insert(0, dict(text="interim wrong", start_ms=0, end_ms=500, is_final=False))
        self.runs[2]["retrieval"]["references"] = ["wrong passage"]
        profile = self.report()["per_profile"][0]
        self.assertEqual(profile["per_language"]["English"]["word_error_rate"], 0)
        self.assertEqual(profile["per_language"]["Igbo"]["retrieval_recall_at_5"], 0)
        self.assertEqual(profile["per_language"]["Igbo"]["word_error_rate"], 0)

    def test_schemas_validate_inputs_and_report(self):
        evaluator.validate_schema(self.corpus, evaluator.load_schema("corpus.schema.json"))
        evaluator.validate_schema(self.report(), evaluator.load_schema("profile.schema.json"))
        bad = self.report(); bad["outcome"] = "pass"
        with self.assertRaises(ValueError):
            evaluator.validate_schema(bad, evaluator.load_schema("profile.schema.json"))

    def test_unknown_retrieval_and_separate_split_results_stay_visible(self):
        for run in self.runs: run.pop("retrieval")
        profile = self.report()["per_profile"][0]
        self.assertIsNone(profile["aggregate"]["false_passage_suggestions"])
        extra = copy.deepcopy(self.corpus["samples"][0])
        extra.update(id="training-control", speaker_id="tuning-speaker", split="tuning")
        self.corpus["samples"].append(extra)
        run = copy.deepcopy(self.runs[0]); run["corpus_id"] = extra["id"]
        self.runs.append(run)
        self.runs[0]["segments"][0]["text"] = "unrelated wrong output"
        profile = self.report()["per_profile"][0]
        self.assertEqual(profile["per_split"]["tuning"]["word_error_rate"], 0)
        self.assertGreater(profile["per_split"]["held_out"]["word_error_rate"], 0)

    def test_supplied_audio_hash_must_match_corpus(self):
        self.runs[0]["audio_sha256"] = "0" * 64
        with self.assertRaises(ValueError): self.report()

    def test_cli_writes_redacted_report_and_insufficient_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "corpus.json").write_text(json.dumps(self.corpus))
            (directory / "runs.json").write_text(json.dumps(self.runs))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/sermon_pilot_eval.py"),
                                     "--corpus", str(directory / "corpus.json"), "--runs", str(directory / "runs.json"),
                                     "--out", str(directory / "report.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads((directory / "report.json").read_text())["outcome"], "insufficient")
            self.assertNotIn("synthetic reference words", (directory / "report.json").read_text())


class ResourceLimitTests(unittest.TestCase):
    def setUp(self):
        self.corpus, self.runs = fixture()

    def assert_refused(self, corpus=None, runs=None):
        with self.assertRaisesRegex(ValueError, "evaluation resource limit exceeded"):
            evaluator.evaluate(self.corpus if corpus is None else corpus,
                               self.runs if runs is None else runs)

    def test_oversize_collections_and_matrix_refused_before_schema_validation(self):
        cases = []
        for key, count in [("samples", 129), ("expected_profiles", 5)]:
            corpus = copy.deepcopy(self.corpus)
            corpus[key] = [corpus[key][0]] * count
            cases.append((corpus, self.runs))
        cases.append((self.corpus, [self.runs[0]] * 257))
        runs = copy.deepcopy(self.runs); runs[0]["segments"] *= 129
        cases.append((self.corpus, runs))
        corpus = copy.deepcopy(self.corpus)
        corpus["samples"] = [corpus["samples"][0]] * 65
        corpus["expected_profiles"] *= 4
        cases.append((corpus, []))
        with mock.patch.object(evaluator, "validate_schema", side_effect=AssertionError("schema reached")):
            for corpus, runs in cases:
                with self.subTest(samples=len(corpus["samples"]), runs=len(runs)):
                    self.assert_refused(corpus, runs)

    def test_collection_and_matrix_exact_boundaries_preserve_all_rows(self):
        sample, profile, run = self.corpus["samples"][0], self.corpus["expected_profiles"][0], self.runs[0]
        self.corpus["samples"] = [dict(sample, id=f"sample-{i}") for i in range(64)]
        self.corpus["expected_profiles"] = [dict(profile, id=f"profile-{i}") for i in range(4)]
        self.runs = [dict(run, corpus_id=sample["id"], profile_id=profile["id"])
                     for profile in self.corpus["expected_profiles"] for sample in self.corpus["samples"]]
        report = evaluator.evaluate(self.corpus, self.runs)
        self.assertEqual(sum(profile["completed_runs"] for profile in report["per_profile"]), 256)
        self.corpus["samples"] = [dict(sample, id=f"sample-{i}") for i in range(128)]
        self.corpus["expected_profiles"] = self.corpus["expected_profiles"][:2]
        report = evaluator.evaluate(self.corpus, [])
        self.assertEqual(report["coverage"]["sample_count"], 128)
        self.assertEqual([len(p["missing_run_ids"]) for p in report["per_profile"]], [128, 128])

    def test_text_and_segment_exact_boundaries_are_not_truncated(self):
        sample, run = self.corpus["samples"][0], self.runs[0]
        self.corpus["samples"] = [dict(sample, id=f"sample-{i}", reference_text="") for i in range(64)]
        self.runs = [dict(run, corpus_id=sample["id"], segments=[dict(text="x" * 4096,
                     start_ms=0, end_ms=1000, is_final=True)]) for sample in self.corpus["samples"]]
        report = evaluator.evaluate(self.corpus, self.runs)  # exactly 262,144 transcript chars
        self.assertEqual(report["per_profile"][0]["aggregate"]["insertions"], 64)
        self.runs[0]["segments"].append(dict(text="x", start_ms=0, end_ms=1000, is_final=True))
        self.assert_refused()
        self.corpus, self.runs = fixture()
        self.runs[0]["segments"] = [dict(text="x" * 4096, start_ms=0, end_ms=1000, is_final=True)] * 4
        row = evaluator.evaluate(self.corpus, self.runs)["per_profile"][0]["samples"][0]
        self.assertEqual((row["substitutions"], row["deletions"], row["insertions"]), (3, 0, 1))
        self.runs[0]["segments"] = [dict(text="x", start_ms=0, end_ms=1000, is_final=False)] * 127 + [dict(
            text="synthetic reference words", start_ms=0, end_ms=1000, is_final=True)]
        self.assertEqual(evaluator.evaluate(self.corpus, self.runs)["per_profile"][0]["samples"][0]["word_error_rate"], 0)

    def test_text_metadata_depth_and_aggregate_bounds_precede_normalization(self):
        cases = []
        corpus = copy.deepcopy(self.corpus); corpus["samples"][0]["reference_text"] = "x" * 4097
        cases.append((corpus, self.runs))
        runs = copy.deepcopy(self.runs); runs[0]["segments"][0]["text"] = "x" * 4097
        cases.append((self.corpus, runs))
        runs = copy.deepcopy(self.runs)
        runs[0]["segments"] = [dict(text="x" * 4096, start_ms=0, end_ms=1000, is_final=True)] * 5
        cases.append((self.corpus, runs))
        runs = [dict(self.runs[0], segments=[dict(text="x" * 4096, start_ms=0, end_ms=1000, is_final=True)])] * 65
        cases.append((self.corpus, runs))
        corpus = copy.deepcopy(self.corpus); corpus["expected_profiles"][0]["configuration"] = {"private": "x" * 4097}
        cases.append((corpus, self.runs))
        corpus = copy.deepcopy(self.corpus)
        nested = {}
        for _ in range(20): nested = {"nested": nested}
        corpus["expected_profiles"][0]["configuration"] = nested
        cases.append((corpus, self.runs))
        with mock.patch.object(evaluator, "words", side_effect=AssertionError("normalization reached")):
            for corpus, runs in cases:
                with self.subTest(): self.assert_refused(corpus, runs)

    def test_512_token_boundary_and_excess_rejected_before_dp(self):
        self.corpus["samples"] = self.corpus["samples"][:1]; self.runs = self.runs[:1]
        # Use one-character tokens to keep this test below the separate text-character cap.
        self.corpus["samples"][0]["reference_text"] = " ".join(["x"] * 512)
        self.runs[0]["segments"][0]["text"] = self.corpus["samples"][0]["reference_text"]
        self.assertEqual(evaluator.evaluate(self.corpus, self.runs)["per_profile"][0]["aggregate"]["reference_words"], 512)
        for target in (self.corpus["samples"][0], self.runs[0]["segments"][0]):
            field = "reference_text" if "reference_text" in target else "text"
            old = target[field]; target[field] = " ".join(["x"] * 513)
            with mock.patch.object(evaluator, "edit_counts", side_effect=AssertionError("DP reached")):
                self.assert_refused()
            target[field] = old

    def test_final_segments_share_one_hypothesis_token_budget(self):
        text = " ".join(["x"] * 257)
        self.runs[0]["segments"] = [dict(text=text, start_ms=0, end_ms=1000, is_final=True)] * 2
        with mock.patch.object(evaluator, "edit_counts", side_effect=AssertionError("DP reached")):
            self.assert_refused()

    def test_aggregate_token_budget_includes_reference_and_interim_text(self):
        sample = self.corpus["samples"][0]
        self.corpus["samples"] = [dict(sample, id=f"sample-{i}", speaker_id=f"speaker-{i}",
                                      reference_text=" ".join(["x"] * 512)) for i in range(65)]
        with mock.patch.object(evaluator, "edit_counts", side_effect=AssertionError("DP reached")):
            self.assert_refused(runs=[])
        self.corpus, self.runs = fixture()
        sample, run = self.corpus["samples"][0], self.runs[0]
        self.corpus["samples"] = [dict(sample, id=f"sample-{i}", reference_text="x") for i in range(8)]
        self.runs = [dict(run, corpus_id=sample["id"], segments=[dict(text=" ".join(["x"] * 257),
                     start_ms=0, end_ms=1000, is_final=False)] * 17) for sample in self.corpus["samples"]]
        with mock.patch.object(evaluator, "edit_counts", side_effect=AssertionError("DP reached")):
            self.assert_refused()

    def test_generic_metadata_node_and_string_budgets_precede_validation(self):
        for metadata in ({"groups": [[None] * 256] * 200}, {"strings": ["x" * 4096] * 129}):
            with self.subTest(metadata_kind=next(iter(metadata))):
                self.corpus["expected_profiles"][0]["configuration"] = metadata
                with mock.patch.object(evaluator, "validate_schema", side_effect=AssertionError("schema reached")):
                    self.assert_refused()

    def test_schema_length_and_collection_boundaries(self):
        evaluator.validate_schema("abc", {"type": "string", "maxLength": 3})
        evaluator.validate_schema([1, 2], {"type": "array", "maxItems": 2})
        for value, schema in [("abcd", {"type": "string", "maxLength": 3}),
                              ([1, 2, 3], {"type": "array", "maxItems": 2})]:
            with self.subTest(schema=schema):
                with self.assertRaises(ValueError): evaluator.validate_schema(value, schema)

    def test_alignment_budget_boundary_and_refusal_before_any_dp(self):
        for sample in self.corpus["samples"]: sample["reference_text"] = " ".join(["x"] * 500)
        for run in self.runs: run["segments"][0]["text"] = " ".join(["x"] * 500)
        report = evaluator.evaluate(self.corpus, self.runs)  # exactly 4 * 500 * 500 cells
        self.assertEqual(report["per_profile"][0]["aggregate"]["word_error_rate"], 0)
        self.corpus["samples"][0]["reference_text"] += " x"  # 1,000,500 cells
        with mock.patch.object(evaluator, "edit_counts", side_effect=AssertionError("DP reached")):
            self.assert_refused()

    def test_direct_oversize_text_refusal_does_not_copy_the_input(self):
        self.corpus["samples"][0]["reference_text"] = "x" * (16 * 1024 * 1024)
        tracemalloc.start()
        try:
            self.assert_refused()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 256 * 1024, "oversize refusal must precede text copies/normalization")

    def test_capped_file_read_handles_growth_and_bounds_additional_memory(self):
        reader = getattr(evaluator, "load_input", None)
        self.assertIsNotNone(reader, "capped JSON input reader is missing")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            with path.open("wb") as file: file.truncate(16 * 1024 * 1024)
            # A real descriptor plus a guarded body-read proves stat refusal precedes reading.
            real_fdopen = evaluator.os.fdopen
            class RefuseBodyRead:
                def __init__(self, fd, mode): self.file = real_fdopen(fd, mode)
                def __enter__(self): return self
                def __exit__(self, *args): self.file.close()
                def fileno(self): return self.file.fileno()
                def read(self, _size): raise AssertionError("oversize file body read")
            with mock.patch.object(evaluator.os, "fdopen", side_effect=RefuseBodyRead):
                with mock.patch.object(evaluator.json, "loads", side_effect=AssertionError("parser reached")):
                    with self.assertRaisesRegex(ValueError, "evaluation resource limit exceeded"):
                        reader(path)
            # Simulate a file growing after the size observation; capped read is still required.
            with mock.patch.object(evaluator.os, "fstat", return_value=SimpleNamespace(st_size=0, st_mode=stat.S_IFREG)):
                with mock.patch.object(evaluator.json, "loads", side_effect=AssertionError("parser reached")):
                    tracemalloc.start()
                    try:
                        with self.assertRaisesRegex(ValueError, "evaluation resource limit exceeded"):
                            reader(path)
                        _, peak = tracemalloc.get_traced_memory()
                    finally:
                        tracemalloc.stop()
            self.assertLess(peak, 12 * 1024 * 1024, "input growth must not trigger an unbounded read")

    def test_input_file_exact_byte_boundary_and_bounded_numeric_literals(self):
        reader = getattr(evaluator, "load_input", None)
        self.assertIsNotNone(reader, "capped JSON input reader is missing")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "boundary.json"
            path.write_bytes(b"[]" + b" " * (4 * 1024 * 1024 - 2))
            self.assertEqual(reader(path), [])
            path.write_text("1" * 65)
            with self.assertRaisesRegex(ValueError, "evaluation resource limit exceeded"):
                reader(path)

    def test_cli_oversize_input_returns_content_free_error_and_no_report(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            corpus = directory / "private-corpus.json"
            with corpus.open("wb") as file: file.truncate(4 * 1024 * 1024 + 1)
            runs = directory / "runs.json"; runs.write_text("[]")
            output = directory / "report.json"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/sermon_pilot_eval.py"),
                                     "--corpus", str(corpus), "--runs", str(runs), "--out", str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())
            self.assertEqual(result.stderr, "Invalid or unavailable evaluation input; no report written.\n")
            self.assertNotIn(str(corpus), result.stderr)

if __name__ == "__main__": unittest.main()
