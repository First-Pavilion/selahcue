# Sermon pilot evaluation tooling (A3)

**Current decision: insufficient. No production profile or automatic output policy is selected.**
The target is Windows 10, 4 GB total RAM, 128 GB SSD and intermittent internet. English,
Yoruba, Igbo and Hausa, language changes and interpreter alternation remain required.
The service timer must keep its current behavior. Synthetic fixtures only test accounting;
they are never recognition, retrieval, memory, Windows or installed-release evidence.

## Private inputs and reproducible scoring

Keep recordings, transcripts, recognizer output and full run files outside Git in an
access-controlled directory. Get permission for each recording and its evaluation use;
`authorized_use: true` is an attestation, not a consent document. Use pseudonymous sample
and speaker IDs. Hash the exact bytes fed to the recognizer. If audio is converted, retain
the original hash privately and use the converted input hash as `audio_sha256`.
No provider calls or model/dataset downloads are made by these tools.

`corpus.schema.json` defines the private input. Top-level fields are `schema_version: 1`,
`evidence_kind` (`synthetic`, `authorized_real`, `unavailable`), `expected_profiles`, and
`samples`. Declare the entire expected engine/model/configuration matrix **before** running
any candidate: each profile has `id`, `role` (`production_baseline`/`experimental`), exact
`engine_sha256`, `model_sha256`, `config_sha256`, `languages`, `rights_source` and
`configuration`. Null hashes/rights represent an unpinned investigation and cannot pass.
A candidate with no returned rows remains visible. Every profile is expected to run every
supplied sample; unsupported languages produce an explicit gap, not omitted rows.

Samples require `id`, `audio_sha256`, `speaker_id`, `languages` (full names), `split`
(`tuning`/`held_out`), positive `duration_ms`, `reference_text`, `expected_references`,
`authorized_use`, and `scenario`. Scenarios are `ordinary_speech`, `silence`,
`ambiguous_scripture`, `language_switch`, `interpreter_alternation`. A silence reference
must be empty. Speaker overlap between tuning and held-out is rejected, even across
languages. Fluent speakers should annotate language changes, omissions, uncertainty,
expected passages and unsupported/ambiguous contexts privately. Use short, bounded clips
and separate continuous-speech trials. Never tune on held-out speakers.

`runs` is a JSON array of objects with this shape (strings below are clearly synthetic):

```json
{
  "corpus_id": "synthetic-clip", "profile_id": "production-baseline",
  "engine_sha256": "<64 lowercase hex>", "model_sha256": "<64 lowercase hex>",
  "config_sha256": "<64 lowercase hex>", "audio_sha256": "<same input hash as corpus>",
  "segments": [{"text": "synthetic words", "start_ms": 0, "end_ms": 1000, "is_final": true}],
  "omission_count": null, "error_count": null, "latency_ms": null,
  "peak_process_tree_memory_bytes": null, "dropped_audio_count": null,
  "switch_recovery_ms": null,
  "retrieval": {"references": ["John 3:16"], "query_source": "asr"}
}
```

The hash placeholders are documentation, not runnable hashes. `segments` is mandatory;
an observed empty recognition is `[]`, never a missing run. Supply a hash only for the
configuration actually used. A supplied audio hash must match the corpus. Missing/null
metrics stay unknown; do not fill in zeros. `omission_count` and `error_count` are separate
human annotation totals, not inferred measurements. Nonnegative metrics must be finite;
counts are integers. `latency_ms` should use the same documented final-text lag boundary
for all candidates (last spoken sample to committed text), with clock/method recorded
privately. `switch_recovery_ms` is annotated/measured after a language boundary. Process-tree
memory needs an external observer; file-replay queue behavior is not microphone loss.

For retrieval, record ranked unique passage identifiers, including an empty list for an
observed no-suggestion result. `query_source` separates clean and ASR-derived queries in
sample rows; aggregate retrieval summaries combine observed rows, so compare those sources
using the sample rows. Retrieval is not inferred from recognition text. Supply `null` or
omit retrieval when unmeasured. Recall@5 is expected passages present in the top five;
MRR is the first expected passage's reciprocal rank. False suggestions count unsupported
passages in the top five, including expected-no-passage contexts. Retrieval metrics are
macro averages over observed eligible samples, with counts; unmeasured rows are excluded
and remain incomplete. Passage identifiers are not copied into the redacted report.

```sh
python3 -m unittest discover -s scripts/tests -p test_sermon_pilot_eval.py
python3 scripts/sermon_pilot_eval.py --corpus "$SELAHCUE_PILOT_CORPUS" \
  --runs "$SELAHCUE_PILOT_RUNS" --out "$SELAHCUE_PILOT_REPORT"
```

Exit 2 means a report was written with `insufficient`; exit 1 means invalid/unavailable
input; exit 0 is reserved for accepted results. **This observational tool always returns
insufficient:** owner thresholds, real device acceptance and profile approval are not
machine-invented. `profile.schema.json` reserves accepted/insufficient/infeasible for the
wider decision record, defines selected-profile hashes/configuration/rights and per-language
observations, and validates this tool's redacted output. Built-in stdlib validation handles
the exact schema subset and fails unsupported keywords. Standard draft-2020-12 validators
can consume the same files.

Scoring normalizes a temporary copy to NFC and casefolds, preserves diacritics, replaces
punctuation with spaces and splits whitespace word tokens. Word edit distance reports
substitutions/deletions/insertions (ties prefer S, D, I). Only final segments score, so
interims cannot double-count speech. Silence insertions/hallucinated words are reported
separately; zero reference words yields null WER. Saved speech is never rewritten by this
evaluator. Mixed utterance WER is reported separately: it is **not** independently measured
word error per language without aligned language labels. Per-language WER uses monolingual
rows only. Tuning/held-out summaries are separate; the aggregate includes both. Every
sample row retains its split, unknown metrics and missing-metric list. Reports contain
hashes, pseudonymous IDs and numeric observations, never reference/recognized speech.

## Enforced evaluator workload limits

These are conservative engineering guards for a small offline evaluation batch, **not**
recognition quality, automatic-output or measured Windows memory thresholds. Oversized
input is refused with a content-free error before report output. No speech, segment,
model or sample is silently dropped or truncated. Split larger experiments into explicit
batches with declared model/sample matrices and preserve every batch's result for review.

| Guard | Inclusive limit |
| --- | --- |
| Each corpus/run JSON file | 4 MiB; regular file, opened-descriptor size check plus read capped at 4 MiB + 1 byte |
| Samples / expected profiles / runs | 128 / 4 / 256 |
| Declared profile × sample matrix | 256 entries, including entirely missing runs |
| Segments per run | 128, including interims |
| Each reference, segment or metadata string | 4,096 Unicode characters; sample/profile/speaker IDs 128 |
| Combined segment text in one run | 16,384 characters, including interims |
| All reference + segment text in a batch | 262,144 characters, including interims |
| Normalized tokens | 512 per reference, per segment, and per combined final hypothesis |
| All normalized reference + segment tokens | 32,768, including interims |
| Aggregate word-alignment work | 1,000,000 reference-token × final-hypothesis-token cells across the entire batch |
| Generic JSON/direct-call structure | Depth 12, 50,000 nodes, 256 entries/container, 524,288 string/key characters total |
| Numeric parsing/direct-call values | 64-character numeric lexemes; finite numbers; integer magnitude at most 256 bits |
| Expected passage identifiers | 32/sample, at most 256 characters each |

The 128-sample/four-profile ceiling allows small four-language/switch/silence rounds; the
256-entry matrix ceiling bounds report/index growth independently of missing runs. The
512-word ceiling permits bounded speech clips, while a one-million-cell whole-batch budget
caps quadratic alignment even when every individual clip fits. Character, segment and
aggregate text/token caps include interim hypotheses, which are not scored as finals but
still consume resources. Generic structure/key/string limits also cover arbitrary model
configuration metadata and unknown fields before schema validation can serialize anything.

The 4 MiB file cap bounds buffered parsing; a size check alone would miss a growing input,
so the read itself is capped. Numeric lexemes are bounded before conversion, non-regular
inputs are refused, and parser recursion failures produce a content-free CLI error.
Direct `evaluate` callers have equivalent collection/text/tree/token/work guards; their
already allocated caller-owned input is not copied or normalized before length refusal.
All input/schema checks and the entire batch's token/work preflight finish before the first
alignment loop. Exact-limit batches remain intact; exceeding any guard yields no score.
`corpus.schema.json` exposes applicable cardinality/string bounds; cross-field, token,
file and whole-batch work budgets are enforced by the evaluator. Local tracemalloc
regressions test refusal allocations; they establish no whole-process or Windows 4 GB fit.

## Existing production decoder replay

`examples/sermon_pilot_eval.rs` loads the current hardware selector's pinned existing model
through `WhisperRecognizer::load` and the actual
`Recognizer::transcribe(&mut self, &[f32], u64, u64) -> Vec<RecognizedSegment>` boundary.
It feeds bounded 20 ms 16 kHz mono normalized little-endian f32 PCM chunks through the
real `SttEngine`, default `EnergyVad`, feedback guard and provider. It emits the exact
provider segments, including interim/final flags. Current repeat trimming and all decoder
settings remain unchanged. It never pretends another CLI uses the same settings.

`engine::production_engine_config()` is the shared capture/replay factory, preserving:
15 hangover frames; 3 minimum voiced frames; 160,000 maximum utterance samples;
800 ms interim wait **after the previous decode completes**; 96,000 interim-window samples.
Capture polling (50 ms), recognition polling (30 ms), five-second hand-off and native device
configuration remain unchanged. The timer and presentation paths are untouched.

```sh
export CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target
cargo test --offline --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml
cargo test --offline --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml \
  --example sermon_pilot_eval
cargo build --offline --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml \
  --features whisper --example sermon_pilot_eval
# Use the SAME feature set for describing and replaying; e.g. metal implies whisper on Mac.
"$CARGO_TARGET_DIR/debug/examples/sermon_pilot_eval" --describe
"$CARGO_TARGET_DIR/debug/examples/sermon_pilot_eval" \
  "$CORPUS_ID" "$PROFILE_ID" "$PRIVATE_PCM" "$EXISTING_PINNED_MODEL" "$PRIVATE_RUN_JSON"
```

`--describe` works without assets; its pin is expected, not verified, and `model_verified`
is false. Actual replay refuses missing/mismatched assets and nonfinite/partial PCM.
Output is a private one-run JSON array (merge such arrays privately for the evaluator).
The output file must not exist; Unix creation mode is 0600. On Windows use a private
user-controlled directory/ACL. Partial failed output is removed. The example's own failure
line is content-free; native Whisper initialization may print model paths in local diagnostic
streams. Keep raw native diagnostics private and redact them before sharing. The evaluator's
redacted report never copies speech. JSON escaping is independently round-tripped through
Python in Rust tests with control characters, quotes, backslashes and Yoruba/Igbo/Hausa Unicode.

Engine hash is length-prefixed SHA-256 over the actual STT source files, Cargo manifest
and STT lockfile; it is a source/lock identity, **not** an installed operator binary hash.
Configuration hash is SHA-256 of the exact emitted descriptor: actual factory values,
VAD defaults, selected model/threads/backend, OS/architecture, native features and replay
input/pacing. Recompute after source/settings/features change. Production integration
also needs installed binary/build identity, compiler/runtime and device configuration.

Replay is paced file input with no capture thread, hardware hand-off or device. Slow
recognition causes file backlog, not measured microphone drops; memory, omissions/errors,
latency, switch recovery and retrieval remain null until external observation/annotation.
No development-Mac figures establish Windows feasibility. The no-model default binary
supports `--describe` and fails replay explicitly; it never fabricates recognition.

## Candidates and open acceptance work

The current stock Whisper tokenizer explicitly lists English/Yoruba/Hausa, with no Igbo
token; this baseline alone cannot pass four-language acceptance ([official tokenizer](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py)).
An explicit all-four experimental investigation is Omnilingual CTC 300M int8 via sherpa:
[Meta coverage/rights](https://github.com/facebookresearch/omnilingual-asr),
[sherpa model/native route](https://k2-fsa.github.io/sherpa/onnx/omnilingual-asr/models.html).
The linked research shortlist also considers stock base/small controls, rights-gated SBPN
and Igbo-only NCAIR controls; source research supplies no measurements or download permission.
Any external CLI/model stays experimental, pinned with its own exact assets/settings/rights.
No new dependency, model, custom training, cloud-only route or production default is added.

Remaining gates: authorized real speech/reference transcripts and split speakers for all
four languages; realistic switches, interpreter alternation, silence, ordinary/ambiguous
contexts; rights-cleared exact candidate assets; separate recognition/lost-speech/switch
recovery/retrieval observations; owner-approved limits; actual Windows 10/4 GB installed
app with timer and stage/audience output plus each candidate. Record CPU/build/free disk,
screen scaling, whole-process memory/paging, cold start, controls, lag and storage growth.
Compare isolated candidates separately from integrated installed releases. Owner review
is required for scope/hardware changes and before automatic congregation output.
The redacted delivery evidence intentionally remains insufficient until those gates close.
