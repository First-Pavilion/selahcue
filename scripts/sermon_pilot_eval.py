#!/usr/bin/env python3
"""Offline, text-redacting observations; no providers, model selection or acceptance claims."""
import argparse
import json
import math
from pathlib import Path
import re
import unicodedata

LANGUAGES = ("English", "Yoruba", "Igbo", "Hausa")
SCENARIOS = ("silence", "ordinary_speech", "ambiguous_scripture", "language_switch", "interpreter_alternation")
HASHES = ("engine_sha256", "model_sha256", "config_sha256")
METRICS = ("omission_count", "error_count", "latency_ms", "peak_process_tree_memory_bytes", "dropped_audio_count")
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs/quality/sermon-pilot"


def load_schema(name):
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def validate_schema(value, schema, path="$", root=None):
    """Validate the explicit JSON Schema subset used in these two standalone schemas.

    These files are also standard draft-2020-12 schemas for external validators.
    Unknown validation keywords fail closed, rather than being silently ignored.
    """
    root = schema if root is None else root
    if "$ref" in schema:
        ref = schema["$ref"]
        if set(schema) != {"$ref"} or not isinstance(ref, str) or not ref.startswith("#/$defs/"):
            raise ValueError("only standalone local definition references are supported")
        definition = root.get("$defs", {}).get(ref[len("#/$defs/"):])
        if definition is None: raise ValueError("unknown schema definition")
        return validate_schema(value, definition, path, root)
    supported = {"$schema", "$id", "$defs", "title", "description", "type", "properties", "required",
                 "additionalProperties", "items", "uniqueItems", "minItems", "minLength",
                 "minimum", "pattern", "enum", "const"}
    if set(schema) - supported:
        raise ValueError("unsupported schema keyword")
    types = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
             "string": lambda v: isinstance(v, str), "null": lambda v: v is None,
             "integer": lambda v: type(v) is int,
             "number": lambda v: type(v) in (int, float) and math.isfinite(v),
             "boolean": lambda v: type(v) is bool}
    if "type" in schema:
        wanted = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(types[t](value) for t in wanted):
            raise ValueError(f"{path}: invalid type")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError(f"{path}: invalid constant")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: invalid enum")
    if isinstance(value, dict):
        if set(schema.get("required", [])) - value.keys():
            raise ValueError(f"{path}: required fields missing")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - props.keys():
            raise ValueError(f"{path}: unknown fields")
        for key, sub in props.items():
            if key in value: validate_schema(value[key], sub, f"{path}.{key}", root)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0): raise ValueError(f"{path}: too few items")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            raise ValueError(f"{path}: duplicate items")
        for i, item in enumerate(value):
            if "items" in schema: validate_schema(item, schema["items"], f"{path}[{i}]", root)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0): raise ValueError(f"{path}: empty string")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ValueError(f"{path}: invalid pattern")
    if type(value) in (int, float) and "minimum" in schema and value < schema["minimum"]:
        raise ValueError(f"{path}: below minimum")


def words(text):
    # Scoring only: keep diacritics and never rewrite the stored/recognized speech.
    normalized = unicodedata.normalize("NFC", text).casefold()
    return "".join(c if unicodedata.category(c)[0] in "LMN" else " " for c in normalized).split()


def edit_counts(reference, hypothesis):
    """Word Levenshtein counts (S,D,I), linear memory, deterministic tie breaking."""
    previous = [(0, 0, i) for i in range(len(hypothesis) + 1)]
    for index, word in enumerate(reference, 1):
        current = [(0, index, 0)]
        for j, candidate in enumerate(hypothesis, 1):
            diagonal = previous[j - 1]
            if word == candidate:
                current.append(diagonal)
            else:
                s, d, i = diagonal; substitution = (s + 1, d, i)
                s, d, i = previous[j]; deletion = (s, d + 1, i)
                s, d, i = current[j - 1]; insertion = (s, d, i + 1)
                current.append(min((substitution, deletion, insertion), key=sum))
        previous = current
    return previous[-1]


def validate_run(run, samples, profiles):
    if not isinstance(run, dict): raise ValueError("run must be an object")
    if run.get("corpus_id") not in samples or run.get("profile_id") not in profiles:
        raise ValueError("unknown corpus/profile run")
    sample, profile = samples[run["corpus_id"]], profiles[run["profile_id"]]
    if "audio_sha256" in run and run["audio_sha256"] != sample["audio_sha256"]:
        raise ValueError("run audio hash differs from corpus")
    for key in HASHES:
        if not isinstance(run.get(key), str) or not re.fullmatch("[0-9a-f]{64}", run[key]):
            raise ValueError("run requires exact asset/config hashes")
        if run[key] != profile[key]: raise ValueError("run hash differs from expected profile")
    if not isinstance(run.get("segments"), list): raise ValueError("run segments required")
    for segment in run["segments"]:
        validate_schema(segment, {"type": "object", "required": ["text", "start_ms", "end_ms", "is_final"],
            "properties": {"text": {"type": "string"}, "start_ms": {"type": "integer", "minimum": 0},
                           "end_ms": {"type": "integer", "minimum": 0}, "is_final": {"type": "boolean"}},
            "additionalProperties": False})
        if not 0 <= segment["start_ms"] <= segment["end_ms"] <= sample["duration_ms"]:
            raise ValueError("segment timing outside sample")
    for key in (*METRICS, "switch_recovery_ms"):
        value = run.get(key)
        if value is not None:
            kind = "number" if key in ("latency_ms", "switch_recovery_ms") else "integer"
            validate_schema(value, {"type": kind, "minimum": 0})
    retrieval = run.get("retrieval")
    if retrieval is not None:
        validate_schema(retrieval, {"type": "object", "required": ["references", "query_source"],
            "properties": {"references": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                           "query_source": {"enum": ["asr", "clean"]}}, "additionalProperties": False})


def score(sample, run):
    reference = words(sample["reference_text"])
    # Only committed finals score accuracy; interim hypotheses are not added twice.
    hypothesis = words(" ".join(s["text"] for s in run["segments"] if s["is_final"]))
    substitutions, deletions, insertions = edit_counts(reference, hypothesis)
    retrieval = run.get("retrieval")
    expected = set(sample["expected_references"])
    recall = mrr = false_suggestions = None
    if retrieval is not None:
        references = retrieval["references"]
        false_suggestions = sum(item not in expected for item in references[:5])
        if expected:
            recall = len(expected.intersection(references[:5])) / len(expected)
            mrr = next((1 / rank for rank, item in enumerate(references, 1) if item in expected), 0)
    row = {"corpus_id": sample["id"], "split": sample["split"], "languages": sample["languages"],
           "reference_words": len(reference), "substitutions": substitutions, "deletions": deletions,
           "insertions": insertions, "word_error_rate": (substitutions + deletions + insertions) / len(reference) if reference else None,
           "silence_hallucination_words": len(hypothesis) if sample["scenario"] == "silence" else 0,
           "retrieval_recall_at_5": recall, "retrieval_mrr": mrr,
           "false_passage_suggestions": false_suggestions,
           "retrieval_query_source": retrieval["query_source"] if retrieval else None,
           "switch_recovery_ms": run.get("switch_recovery_ms"),
           **{key: run.get(key) for key in METRICS}}
    row["missing_metrics"] = [key for key in METRICS if run.get(key) is None]
    if retrieval is None: row["missing_metrics"].append("retrieval")
    if len(sample["languages"]) > 1 and run.get("switch_recovery_ms") is None:
        row["missing_metrics"].append("switch_recovery_ms")
    return row


def summarize(rows, monolingual_only=False):
    scored = [r for r in rows if not monolingual_only or len(r["languages"]) == 1]
    count = sum(r["reference_words"] for r in scored)
    totals = {key: sum(r[key] for r in scored) for key in
              ("substitutions", "deletions", "insertions", "silence_hallucination_words")}
    retrieval = [r for r in rows if r["retrieval_recall_at_5"] is not None]
    return {"represented_samples": len(rows), "scored_monolingual_samples": sum(len(r["languages"]) == 1 for r in scored),
            "mixed_language_samples": sum(len(r["languages"]) > 1 for r in rows),
            "reference_words": count, **totals,
            "word_error_rate": sum(totals[k] for k in ("substitutions", "deletions", "insertions")) / count if count else None,
            "retrieval_evaluated_samples": len(retrieval),
            "retrieval_recall_at_5": sum(r["retrieval_recall_at_5"] for r in retrieval) / len(retrieval) if retrieval else None,
            "retrieval_mrr": sum(r["retrieval_mrr"] for r in retrieval) / len(retrieval) if retrieval else None,
            "false_passage_suggestions": (sum(r["false_passage_suggestions"] or 0 for r in rows)
                                           if any(r["false_passage_suggestions"] is not None for r in rows) else None)}


def evaluate(corpus: dict, runs: list[dict]) -> dict:
    validate_schema(corpus, load_schema("corpus.schema.json"))
    if not isinstance(runs, list): raise ValueError("runs must be a list")
    samples, profiles, speakers = {}, {}, {}
    for sample in corpus["samples"]:
        if sample["id"] in samples: raise ValueError("duplicate sample ID")
        samples[sample["id"]] = sample
        split = speakers.setdefault(sample["speaker_id"], sample["split"])
        if split != sample["split"]: raise ValueError("speaker overlaps tuning and held_out splits")
        if sample["scenario"] == "silence" and words(sample["reference_text"]):
            raise ValueError("silence reference must be empty")
    for profile in corpus["expected_profiles"]:
        if profile["id"] in profiles: raise ValueError("duplicate profile ID")
        profiles[profile["id"]] = profile
    indexed = {}
    for run in runs:
        validate_run(run, samples, profiles)
        key = run["profile_id"], run["corpus_id"]
        if key in indexed: raise ValueError("duplicate run")
        indexed[key] = run
    represented = {lang for s in samples.values() for lang in s["languages"]}
    held_out = {lang for s in samples.values() if s["split"] == "held_out" for lang in s["languages"]}
    coverage = {"required_languages": list(LANGUAGES), "missing_languages": sorted(set(LANGUAGES) - represented),
                "held_out_missing_languages": sorted(set(LANGUAGES) - held_out), "sample_count": len(samples),
                "missing_scenarios": sorted(set(SCENARIOS) - {s["scenario"] for s in samples.values()})}
    missing = ["owner-approved quality/operating thresholds and acceptance decision",
               "actual Windows 10 / 4 GB integrated installed-app evidence with timer and stage/audience output"]
    if corpus["evidence_kind"] != "authorized_real": missing.append("authorized real four-language corpus and fluent-speaker references")
    for key in ("missing_languages", "held_out_missing_languages", "missing_scenarios"):
        if coverage[key]: missing.append(key + ": " + ", ".join(coverage[key]))
    if not profiles: missing.append("independently declared expected model/configuration matrix")
    result_profiles = []
    for profile_id, profile in profiles.items():
        absent = [sid for sid in samples if (profile_id, sid) not in indexed]
        rows = [score(sample, indexed[profile_id, sid]) for sid, sample in samples.items() if (profile_id, sid) in indexed]
        unpinned = any(profile[key] is None for key in HASHES) or not profile["rights_source"]
        if absent: missing.append("missing runs for profile " + profile_id)
        if unpinned: missing.append("unpinned assets/configuration or rights for profile " + profile_id)
        if set(profile["languages"]) != set(LANGUAGES): missing.append("profile language coverage incomplete: " + profile_id)
        if any(r["missing_metrics"] for r in rows): missing.append("unknown run metrics for profile " + profile_id)
        mixed = [r for r in rows if len(r["languages"]) > 1]
        mixed_summary = summarize(mixed)
        result_profiles.append({"profile_id": profile_id, **{k: profile[k] for k in (*HASHES, "languages", "rights_source", "role")},
            "completed_runs": len(rows), "complete": bool(samples) and not absent and not unpinned and not any(r["missing_metrics"] for r in rows),
            "missing_run_ids": absent, "samples": rows,
            "per_language": {lang: summarize([r for r in rows if lang in r["languages"]], True) for lang in LANGUAGES},
            "mixed_language": {"scored_samples": len(mixed), "reference_words": mixed_summary["reference_words"], "word_error_rate": mixed_summary["word_error_rate"]},
            "per_split": {split: summarize([r for r in rows if r["split"] == split]) for split in ("tuning", "held_out")},
            "aggregate": summarize(rows)})
    report = {"schema_version": 1, "outcome": "insufficient", "selected_profile": None,
              "evidence_kind": corpus["evidence_kind"], "normalization": "Scoring only: NFC, casefold, Unicode letters/marks/numbers; punctuation to spaces; whitespace word tokens. Diacritics retained. WER S/D/I tie order; silence insertions separate. Mixed WER not attributed per language. Tuning and held_out rows retain split; aggregate includes both. Retrieval macro averages across observed rows only.",
              "coverage": coverage, "missing_evidence": missing, "per_profile": result_profiles}
    validate_schema(report, load_schema("profile.schema.json"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--runs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
        runs = json.loads(Path(args.runs).read_text(encoding="utf-8"))
        report = evaluate(corpus, runs)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, OSError):
        # Never echo input text, JSON decoder excerpts, or potentially private paths.
        parser.exit(1, "Invalid or unavailable evaluation input; no report written.\n")
    print("Evaluation written; outcome=" + report["outcome"])
    return 0 if report["outcome"] == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
