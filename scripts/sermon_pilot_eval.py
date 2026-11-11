#!/usr/bin/env python3
"""Offline, text-redacting observations; no providers, model selection or acceptance claims."""
import argparse
import json
import math
import os
import stat
from pathlib import Path
import re
import unicodedata

LANGUAGES = ("English", "Yoruba", "Igbo", "Hausa")
SCENARIOS = ("silence", "ordinary_speech", "ambiguous_scripture", "language_switch", "interpreter_alternation")
HASHES = ("engine_sha256", "model_sha256", "config_sha256")
METRICS = ("omission_count", "error_count", "latency_ms", "peak_process_tree_memory_bytes", "dropped_audio_count")
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs/quality/sermon-pilot"


# Engineering batch guards, not accuracy/projection thresholds or measured Windows budgets.
MAX_INPUT_BYTES = 4 * 1024 * 1024  # each JSON file, checked on the opened fd AND capped read
MAX_SAMPLES = 128
MAX_PROFILES = 4
MAX_RUNS = 256
MAX_MATRIX_ENTRIES = 256
MAX_SEGMENTS_PER_RUN = 128
MAX_TEXT_CHARS = 4096  # each reference, segment, or metadata string
MAX_RUN_TEXT_CHARS = 16_384  # all interim/final segment text combined
MAX_TOTAL_TEXT_CHARS = 262_144  # references plus all segment text, including interims
MAX_WORDS_PER_TEXT = 512  # each reference/segment AND the combined final hypothesis
MAX_TOTAL_TOKENS = 32_768  # references plus all segments, including interim hypotheses
MAX_ALIGNMENT_CELLS = 1_000_000  # sum(reference_words * final_hypothesis_words), whole batch
MAX_TREE_NODES = 50_000
MAX_TREE_DEPTH = 12
MAX_CONTAINER_ITEMS = 256
MAX_TOTAL_STRING_CHARS = 524_288  # metadata/keys included, before schema serialization
MAX_NUMERIC_LITERAL_CHARS = 64
RESOURCE_ERROR = "evaluation resource limit exceeded"


def _within(condition):
    if not condition:
        raise ValueError(RESOURCE_ERROR)


def load_input(path):
    """Read only a bounded regular file, including when it grows after fstat.

    Nonblocking open avoids waiting on a FIFO substituted for the intended file. JSON numeric
    lexemes are capped before conversion; parser recursion errors are content-free failures.
    """
    def integer(value):
        _within(len(value) <= MAX_NUMERIC_LITERAL_CHARS)
        return int(value)

    def real(value):
        _within(len(value) <= MAX_NUMERIC_LITERAL_CHARS)
        result = float(value)
        _within(math.isfinite(result))
        return result

    def constant(_value):
        raise ValueError("invalid evaluation input")

    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as file:
        info = os.fstat(file.fileno())
        _within(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_INPUT_BYTES)
        data = file.read(MAX_INPUT_BYTES + 1)
        _within(len(data) <= MAX_INPUT_BYTES)
    try:
        return json.loads(data, parse_int=integer, parse_float=real, parse_constant=constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError):
        raise ValueError("invalid evaluation input") from None


def _bound_tree(corpus, runs):
    """Bound all metadata/unknown fields too, without serializing or copying containers."""
    pending = [(corpus, 0), (runs, 0)]
    nodes = string_chars = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        _within(nodes <= MAX_TREE_NODES and depth <= MAX_TREE_DEPTH)
        if isinstance(value, str):
            _within(len(value) <= MAX_TEXT_CHARS)
            string_chars += len(value)
            _within(string_chars <= MAX_TOTAL_STRING_CHARS)
        elif isinstance(value, (dict, list)):
            _within(len(value) <= MAX_CONTAINER_ITEMS)
            if isinstance(value, dict):
                for key, child in value.items():
                    if not isinstance(key, str): raise ValueError("invalid evaluation input")
                    pending.append((key, depth + 1))
                    pending.append((child, depth + 1))
            else:
                pending.extend((child, depth + 1) for child in value)
        elif type(value) is int:
            _within(value.bit_length() <= 256)
        elif type(value) is float:
            _within(math.isfinite(value))
        elif value is not None and type(value) is not bool:
            raise ValueError("invalid evaluation input")


def _bound_inputs(corpus, runs):
    """Length/accounting preflight runs before schema validation or text normalization."""
    if not isinstance(corpus, dict) or not isinstance(runs, list):
        raise ValueError("invalid evaluation input")
    samples, profiles = corpus.get("samples"), corpus.get("expected_profiles")
    if not isinstance(samples, list) or not isinstance(profiles, list):
        raise ValueError("invalid evaluation input")
    _within(len(samples) <= MAX_SAMPLES and len(profiles) <= MAX_PROFILES and len(runs) <= MAX_RUNS)
    _within(len(samples) * len(profiles) <= MAX_MATRIX_ENTRIES)
    _bound_tree(corpus, runs)
    total_chars = 0
    for sample in samples:
        if isinstance(sample, dict) and isinstance(sample.get("reference_text"), str):
            total_chars += len(sample["reference_text"])
            _within(total_chars <= MAX_TOTAL_TEXT_CHARS)
    for run in runs:
        if not isinstance(run, dict) or not isinstance(run.get("segments"), list):
            raise ValueError("invalid evaluation input")
        _within(len(run["segments"]) <= MAX_SEGMENTS_PER_RUN)
        run_chars = 0
        for segment in run["segments"]:
            if isinstance(segment, dict) and isinstance(segment.get("text"), str):
                run_chars += len(segment["text"])
                total_chars += len(segment["text"])
                _within(run_chars <= MAX_RUN_TEXT_CHARS and total_chars <= MAX_TOTAL_TEXT_CHARS)


def _bound_alignment(samples, indexed):
    """Preflight the WHOLE batch before the first DP row allocation or score call."""
    counts = {}
    tokens = work = 0
    for sid, sample in samples.items():
        count = len(words(sample["reference_text"]))
        _within(count <= MAX_WORDS_PER_TEXT)
        counts[sid] = count
        tokens += count
        _within(tokens <= MAX_TOTAL_TOKENS)
    for (_profile, sid), run in indexed.items():
        hypothesis_count = 0
        for segment in run["segments"]:
            count = len(words(segment["text"]))
            _within(count <= MAX_WORDS_PER_TEXT)
            tokens += count
            _within(tokens <= MAX_TOTAL_TOKENS)
            if segment["is_final"]:
                hypothesis_count += count
                _within(hypothesis_count <= MAX_WORDS_PER_TEXT)
        work += counts[sid] * hypothesis_count
        _within(work <= MAX_ALIGNMENT_CELLS)


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
                 "minimum", "pattern", "enum", "const", "maxItems", "maxLength"}
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
        if len(value) > schema.get("maxItems", MAX_CONTAINER_ITEMS):
            raise ValueError("invalid evaluation input")
        if len(value) < schema.get("minItems", 0): raise ValueError(f"{path}: too few items")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            raise ValueError(f"{path}: duplicate items")
        for i, item in enumerate(value):
            if "items" in schema: validate_schema(item, schema["items"], f"{path}[{i}]", root)
    if isinstance(value, str):
        if len(value) > schema.get("maxLength", MAX_TEXT_CHARS):
            raise ValueError("invalid evaluation input")
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
    _bound_inputs(corpus, runs)
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
    _bound_alignment(samples, indexed)
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
        corpus = load_input(args.corpus)
        runs = load_input(args.runs)
        report = evaluate(corpus, runs)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, OSError):
        # Never echo input text, JSON decoder excerpts, or potentially private paths.
        parser.exit(1, "Invalid or unavailable evaluation input; no report written.\n")
    print("Evaluation written; outcome=" + report["outcome"])
    return 0 if report["outcome"] == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
