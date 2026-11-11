"""Clearly synthetic fixtures: these exercise bookkeeping, never ASR quality."""
import copy
import importlib.util
import json
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

if __name__ == "__main__": unittest.main()
