# Evaluation plan: Whisper fine-tuning for Nigerian-accented English (and Pidgin / code-switching)

- **Status:** DRAFT for owner review. Nothing here has been run yet; every number below is a proposal or an estimate, labelled as such.
- **Role:** AI Engineer (Nova). **Date:** 2026-10-01. **Baseline revision:** `origin/main` at `b73d389`.
- **Realises / feeds:** PRD FR-171 (AI evaluation-set definition, spike S11), FR-101 (offline Whisper default + hardware auto-select), FR-102 (VAD / non-speech hallucination cap), FR-108 (per-church custom vocabulary, ≥20% relative per-term WER cut), FR-121 / METRIC-009 (scripture-detection false positives ≤5%), FR-167 (transcription language / accent selection).
- **Governing decisions:** ADR-0010 (local-first provider abstraction, ≤2 GB resident model budget, model integrity FR-156, AI accuracy is provisional until measured), ADR-0019 (transcript-provider seam, detection is a pure function over committed transcript text), ADR-0012 (packaging and model-file integrity), DEC-008 (cloud STT is metered per org; on-device is not), DEC-001 (TTS removed, so no TTS-generated training audio is on the roadmap either). Research inputs: `docs/research/CAPABILITY-ASSESSMENT.md` §1.2 and §2.4 (accents raise WER; detection is capped by ASR quality), `docs/research/FEASIBILITY.md` S8/S11.
- **Scope guard:** a plan only. No product code, no ClickUp writes.

---

## 0. The question this plan answers

Does a Whisper model adapted to Nigerian speech make SelahCue's live sermon transcript, and the scripture detections built on it, measurably better for Nigerian churches, without making it worse for anyone else, without breaking the live-latency budget, and in a form we are legally allowed to ship?

The plan is built so that a cheap answer ("prompt priming or quantisation alone gets most of the gain") can end the programme early. Fine-tuning is only justified if it beats the zero-training arms by a margin we fix before we look at results.

---

## 1. How the shipped pipeline actually works (what we are evaluating)

These facts come from reading the code at `b73d389`. The evaluation must reproduce this pipeline, not a generic Whisper setup, or its numbers will not predict production.

**Model selection (`implementation/desktop/crates/selahcue-stt/src/model.rs`)**

- `HardwareProbe::select_model()` picks the model from the build and host alone. There is no user, locale or church input.
  - If a GPU backend is compiled in (`metal`, `cuda` or `vulkan` Cargo features): `large-v3-turbo`.
  - Otherwise, with 2 or more threads: `small`. With 1 thread: `base`.
  - `medium` is only ever reached as a budget step-down, which never happens today because turbo fits the 2 GB budget.
  - Decode threads are `available_parallelism - 1`, clamped to 1..8.
- In practice this splits the user base by platform:
  - **macOS** builds enable `metal` (operator `Cargo.toml`), so Macs run **large-v3-turbo on Metal**.
  - **Windows**: the only workflow that ships an installer (`.github/workflows/windows-installer.yml`) builds `--features stt` with no GPU feature, so Windows church PCs run **small on the CPU**.
- The weights are the upstream `ggerganov/whisper.cpp` files from Hugging Face, pinned by SHA-256 and size in `WhisperModel::asset()`. They are the **f16 (unquantised)** files: `ggml-large-v3-turbo.bin` is 1,624,555,275 bytes and `ggml-medium.bin` is 1,533,763,059 bytes. ADR-0010 and the `approx_resident_bytes` doc comment both describe these as INT8 or quantised. They are not.

**Model loading (`implementation/desktop/crates/selahcue-operator/src/listening.rs`, `load_recognizer`)**

- The file is fetched on first use through `selahcue_stt::fetch_model_phased`, SHA-256-verified, installed into `default_cache_dir()`, loaded, and cached as one resident context for the session.
- `SELAHCUE_STT_MODEL` plus `SELAHCUE_STT_MODEL_SHA256` override the download with any local file, integrity-checked against the caller-supplied hash. This is **not** gated to debug builds. For the evaluation it is useful: candidate models can be A/B'd in the real app with no code change.

**Decoding (`implementation/desktop/crates/selahcue-stt/src/recognizer.rs`, `WhisperRecognizer::transcribe`)**

- Greedy decoding, `best_of: 1`. No beam search, and no temperature-fallback settings beyond whisper.cpp defaults.
- **No `initial_prompt` is set anywhere.** There is no prompt priming and no carry-over of previous text.
- **No language is set.** whisper.cpp's default (`whisper_full_default_params`, `.language = "en"` in the vendored `whisper-rs-sys` 0.13 source) forces English. Pidgin and Yoruba/Igbo/Hausa code-switching are decoded as English.
- `set_audio_ctx(512)`: the encoder sees at most 10.24 s of audio (see the long doc comment on `WHISPER_AUDIO_CTX`).
- `set_single_segment(true)`, and a **fresh `WhisperState` per call**, so each utterance is decoded with no context from the previous one.

**Segmentation (`selahcue-stt/src/engine.rs`)**

- Energy VAD brackets utterances. Interim decodes run about every 0.8 s of speech. An utterance is force-closed at 10 s (`max_utterance_samples`), deliberately just under the 10.24 s audio-context horizon.

**What consumes the transcript**

- Only **final** (committed) segments reach detection. Interims only update the live partial line (`selahcue-app/src/transcript_sink.rs`, `operator.rs`).
- `selahcue_core::detection::detect(text)` is a pure function. It normalises spoken numbers ("three sixteen", "first Corinthians"), drops "chapter"/"verse" filler, and hands 1–6-token windows to the scripture parser. Detection runs **per segment**, so a reference split across a 10 s force-close boundary ("…turn with me to John chapter three" | "verse sixteen…") cannot be detected.
- `TranscriptEngine::ingest_with_quotes` adds fuzzy quote/paraphrase candidates (`selahcue-scripture/src/quote_match.rs`). Explicit references carry confidence 95, and quote matches carry a coverage score.
- Transcripts also feed sermon notes (R5) and the Transcripts view.

**Cloud path (`selahcue-stt-cloud/src/session.rs`)**

- The cloud path uses Deepgram `nova-3`, `language=en-US`, `smart_format=false`, with no keyterms. It is compiled only under `cloud-stt`, which is `RELEASE: UNSAFE` today (developer key only), so no release build ships it. It can still serve as a reference arm, subject to the consent rules in §3.6.

**Requirements that exist but are not implemented yet**

- FR-108 (per-church glossary): no glossary reaches either recognizer.
- FR-167 (language/accent selection): no setting exists.
- Both are relevant, because the cheapest fixes below are exactly those two features.

---

## 2. Baseline: measure what we ship before training anything

Every arm runs through the **production decode path** (§4.1), on the frozen test set (§3), on the target hardware (§4.5). The zero-training arms matter most, because they are cheap and could make fine-tuning unnecessary.

**Arm A0: shipped models, as configured**

- `base`, `small`, `medium` and `large-v3-turbo`, f16, with production params: greedy, `audio_ctx` 512, single segment, `en`, no prompt.
- Report all four so we know the size/accuracy curve. The two that matter for users are **small on Windows CPU** and **turbo on Mac Metal**.

**Arm A1: static prompt priming (zero training)**

- `set_initial_prompt` gets a fixed church-vocabulary prompt, re-sent on every call because state is fresh per call. The prompt contains:
  - a short natural sentence in the target register, for example "Turn with me to Second Corinthians chapter five verse seventeen. Hallelujah. Amen.", which primes spelling and number style
  - books of the Bible that Whisper commonly mishears (Habakkuk, Ecclesiastes, Philemon, Nahum, Lamentations)
  - frequent Nigerian church terms and names (for example RCCG, Winners, Deeper Life, MFM, Redeemed, Adeboye, Oyedepo, Kumuyi, Lagos, Ibadan, Enugu)
- Keep it well under whisper.cpp's prompt cap (half the 448-token text context). Measure its token length and its latency cost.

**Arm A2: dynamic priming**

- This is A1 plus one of two additions, measured separately:
  - **A2a, per-church glossary.** A church-specific list (pastor and place names) prepended to the prompt. This is FR-108's mechanism, and FR-108's own gate applies: ≥20% relative per-term WER cut against no glossary.
  - **A2b, rolling context.** The previous final segment's text is appended to the prompt, restoring the cross-window context that `single_segment` plus a fresh state removes.
- Known risk to measure explicitly: Whisper sometimes **echoes prompt words on silence or music**. A2 must pass the FR-102 non-speech gate (§4.4) or it is disqualified, whatever its WER.

**Arm A3: quantisation only (zero training)**

- `q8_0` and `q5_0` of the shipped models, produced with whisper.cpp's `quantize`.
- The point is latency, not accuracy. If `q5_0` turbo or medium runs in real time on the Windows CPU tier, Windows users could move up from `small` with no training at all. That could be a larger accuracy gain for Nigerian speakers than fine-tuning `small`.
- This arm also supplies the post-quantisation reference that §5.4 needs.

**Arm A4: language setting (zero training, Pidgin slice only)**

- `language = "en"` (today) against `auto`, on the Pidgin/code-switch slice. This is report-only, to see whether forcing English is hurting.

**Arm R: reference arms (not shippable as they stand, used for calibration)**

- `large-v3` f16 (non-turbo) on a GPU box, as an accuracy ceiling for the Whisper family.
- Deepgram `nova-3`, `en-US` against `en` and with keyterm prompting. **Only** on audio whose consent covers third-party processing (§3.6).

**Deliverable of phase 1:** a baseline report with one row set per arm × model × hardware, covering every metric in §4. If A1–A3 already meet the §4.7 ship thresholds, stop and ship those (glossary, quantised larger model on Windows) before spending on training.

---

## 3. The test set

### 3.1 Principles

- **Frozen and versioned.** A manifest lists every clip's SHA-256, speaker ID, church ID, slice and licence/consent basis, and the manifest itself is hashed. Any change creates a new version, and results always cite the version.
- **Held out by speaker and by church**, not by utterance. No test speaker and no test church appears in any training or dev data. A **dev set** (separate speakers and churches again) is used for hyperparameter and checkpoint selection. The test set is used once per candidate, at the end.
- **Commercially clean where it gates shipping.** Slices that decide ship/no-ship are built only from data we can legally use commercially (§3.5). Non-commercial corpora may appear only in clearly labelled, non-gating diagnostic slices, and only if legal clears even that use (Open decision D1).

### 3.2 Composition (target about 14 h of scored audio)

- **S1: Nigerian English sermons, room conditions (primary slice, about 6 h).**
  - Partner-church recordings under the consent terms in §3.6.
  - At least 8 churches, 30+ distinct speakers (preachers, readers, announcers), across denominations (Pentecostal, Anglican, Catholic, Baptist) and regions (Yoruba, Igbo, Hausa, Niger Delta L1 backgrounds).
  - Two capture paths per service where possible: the **room/ambient mic** the operator laptop would hear (PA bleed, reverb) and the **desk feed** (mixer line out). Score them separately, because the laptop mic is the realistic worst case.
  - Include realistic hard audio: congregational responses, "Amen/Hallelujah" call-and-response, generator hum, interpreted sermons (English with a Yoruba interpreter alternating).
- **S2: explicit scripture references (about 1.5 h, at least 600 references).**
  - Scripted read-aloud prompts by Nigerian speakers (at least 40, balanced gender and age, on at least 3 phone/laptop mics), plus every reference that occurs naturally in S1.
  - Cover numbered books ("First Corinthians", "1st John", "Second Kings"), ranges ("verses one to six", "through"), chapter-only, "verse" omitted ("John three sixteen"), and Nigerian pronunciations of hard book names.
  - This is FR-171's **explicit-reference set** and doubles as METRIC-009's.
- **S3: Nigerian Pidgin and code-switching (about 2 h, report-only unless D2 makes it gating).**
  - Pidgin exhortation, testimony-style segments (consented speakers only), and English with embedded Yoruba/Igbo/Hausa phrases (for example "Olorun", "Chineke", "Allah ya").
- **S4: entity-dense speech (about 1 h).** Announcements, dedications and prayer lists naming people, places, churches and ministries. This is the entity-accuracy slice. It overlaps with S1 announcements; entities are also tagged across all slices.
- **S5: non-Nigerian regression slice (about 2.5 h).**
  - LibriSpeech `test-clean` and `test-other` subsets (CC BY 4.0), FLEURS `en_us` test (CC BY 4.0), and Common Voice English test clips with non-Nigerian accent tags (CC0).
  - Ideally also consented sermons from US/UK/Ghanaian/Kenyan preachers, because sermon register matters and the product is not Nigeria-only.
  - This slice guards against catastrophic forgetting.
- **S6: non-speech (about 1 h).** Worship music (live band and backing tracks), silence, room tone, applause, crowd noise, generator hum, and PA feedback. This is FR-171's **non-speech set** and FR-102's gate.

**Sizing rationale (estimate):**

- With speaker-level bootstrap, 6 h and 30+ speakers typically gives a 95% CI of about ±1–1.5 WER points at the 15–25% WER we expect in rooms (CAPABILITY-ASSESSMENT §1.2).
- That is tight enough to detect the ≥15% relative improvement the ship gate asks for.
- Smaller slices (S3, S4) are reported with their CIs and not over-read.

### 3.3 Transcription and verification protocol

- **Written guideline first**, piloted on 30 minutes and revised. It covers:
  - Verbatim with light normalisation. Keep repetitions that carry meaning. Drop pure fillers ("uh") and score them as optional.
  - Numbers **as spoken words** in the reference ("John three sixteen"). A scripture-aware normaliser (§4.2) maps both reference and hypothesis to canonical form before scoring, so "John 3:16" and "John three sixteen" match.
  - **Inline tags**: `<ref canon="John 3:16">…</ref>` on scripture references and `<ent type="person|place|church|org|bible-name">…</ent>` on entities, for the entity and reference metrics.
  - `[inaudible]`, `[crosstalk]`, `[music]` markers, excluded from scoring.
  - **Pidgin orthography**: a pinned spelling list following Naija Langwej Akademi conventions where one exists ("dey", "wetin", "abi", "sef"), with common variants (de/dey) accepted as equivalents in the normaliser. Transcribe Pidgin as Pidgin. **Never translate it into Standard English.**
  - Yoruba/Igbo/Hausa words written in standard orthography **without** tone marks for scoring (Whisper will not produce them). The tone-marked form is kept in a side field.
- **Two-pass, native-listener transcription.**
  - Pass 1 by a Nigerian transcriber. To avoid anchoring on any candidate, pass 1 is either from scratch or from a draft produced by a system **not under evaluation** (for example Deepgram on cloud-consented audio only). **Never** draft from a Whisper arm.
  - Pass 2 is an independent review by a second Nigerian transcriber, with disagreements adjudicated by a third.
  - Pidgin and code-switch audio is transcribed by speakers of that language.
- **Quality control.**
  - 10% of audio is double-transcribed blind. Inter-annotator WER must be ≤5% (≤8% on S3). A slice that misses this is re-done, not scored.
  - Every `<ref>` tag is checked against the canonical book list by script (`selahcue-core`'s parser can do this).
- **Transcribers** are under NDA and a data-processing agreement, work on encrypted storage, and never upload audio to third-party tools unless that audio's consent covers it.

### 3.4 Speaker, church and condition metadata

- Metadata per clip: speaker ID (pseudonymous), gender, age band, L1, region, church ID (pseudonymous), denomination, capture path (room mic, desk feed, phone), device, SNR estimate, and slice.
- Results are broken down along each axis, so a gain for Yoruba-L1 men on desk feeds cannot hide a loss for Hausa-L1 women on room mics.

### 3.5 Data sources and licences (training and evaluation)

- **AfriSpeech-200** (Intron Health): about 200 h, 120 African accents, heavily Nigerian, clinical and general domains.
  - **Licence: CC BY-NC-SA 4.0. Non-commercial.** SelahCue is a commercial product. Training a shipped model on it is very likely a licence breach, and ShareAlike raises a further question about whether the weights must carry the same licence.
  - **Proposed default:** do not use it for training shipped models. At most, use it for a non-gating diagnostic eval slice, and only if legal confirms that even internal evaluation by a commercial entity is acceptable. Alternatively, ask Intron about a commercial licence.
- **NaijaVoices** (Igbo, Hausa, Yoruba; large, community-recorded).
  - **Licence: to be verified before any use.** As far as we know, access is gated and the terms are non-commercial or research-oriented. Treat it as unusable for shipping until legal reads the actual terms.
  - It is also mostly Nigerian *languages* rather than Nigerian-accented *English*, so its value is for S3/code-switching, not the primary slice.
- **Mozilla Common Voice**: **CC0**, commercially clean.
  - Includes English clips with a self-reported "Nigerian" or West African accent (small, read speech), plus Yoruba/Igbo/Hausa subsets of variable size and quality.
  - Use it for training mix and for the S5 regression slice.
- **Google FLEURS**: **CC BY 4.0**, commercially usable with attribution.
  - Has Yoruba, Igbo and Hausa (read speech, around 10 h each).
  - Use `en_us` for S5. The Nigerian-language portions are useful for S3 diagnostics and for mixing, but they are not Nigerian-accented English.
- **LibriSpeech**: **CC BY 4.0**. Used for S5 and the replay mix.
- **Partner-church recordings** (consented, §3.6). This is the **only source that matches the target domain** (sermon register, PA acoustics, church vocabulary) and is commercially clean *if* the consent is drafted correctly. It is the backbone of both training and the gating test slices.
- **Scripted read-aloud of references and entities** (paid, consented contributors). Commercially clean, cheap per hour, and it targets exactly the tokens that matter downstream.

### 3.6 Privacy and consent

- **Legal basis.** Sermon audio is personal data under NDPA 2023 and GDPR (PRD §Privacy, ADR-0010 CON-5). A voice recording can also be biometric data, which NDPA treats as sensitive. Consent must be explicit, informed and written.
- **Two scopes of consent, never merged:** (a) *evaluation only*, and (b) *training a model that is distributed commercially*. Most speakers will sign (a) more readily than (b). A clip's scope travels in the manifest and gates which pipeline may read it.
- **Third-party processing is a separate tick-box.** It is needed for any clip sent to Deepgram (arm R) or to an external transcription vendor.
- **Who signs:**
  - Every identifiable speaker on the scored audio. Preachers and readers sign individually.
  - The church signs a data-sharing agreement covering the recording, the setting and its congregation.
  - Congregational background speech that is not scored is covered by church notice. **Individual testimonies, prayer requests, altar calls, counselling moments and anything health-related are cut out** at intake, because they carry third-party sensitive data.
  - No minors' voices are scored. Children's segments are removed at intake.
- **Withdrawal.** A speaker can withdraw. Eval clips are removed and the test-set version bumped. For training data, withdrawal applies to the **next** model version: we cannot un-train shipped weights, and the consent form must say so plainly.
- **Storage:**
  - Raw audio lives on encrypted, access-controlled storage (named individuals only), never in the git repo and never on a shared drive.
  - Transcripts are pseudonymised: names in *text* stay, because entity accuracy needs them, but speaker identities are replaced by IDs.
  - Retention runs until the programme ends plus a fixed period chosen by the owner. After that, deletion covers derived artefacts too (the FR-153 posture).
- **Compute.** Training on a cloud GPU is third-party processing. Use a provider under a DPA, in a region the consent covers, and state the cross-border transfer in the consent (FR-177 posture).
- Models trained on consented data will **not** be published as open weights unless the consent explicitly covers that.

---

## 4. Metrics

### 4.1 Harness: evaluate the production pipeline, not a notebook

- **Stage 1: fast screen.**
  - Run whisper.cpp's CLI (or HF `transformers` before conversion) over the pre-segmented test set, using production params: greedy, `language=en`, `audio_ctx=512`, single segment, segments ≤10 s.
  - This is cheap, handles every checkpoint, and is used on the dev set for checkpoint selection.
- **Stage 2: decisive run.** A small Rust harness in `selahcue-stt` (new, test or bin target, behind the `whisper` feature) that:
  1. streams each test recording through the **real** `SttEngine` (VAD, resample, interims, 10 s force-close) using the crate's fake audio source at real-time pace, with the real `WhisperRecognizer`
  2. collects final segments with timestamps, feeds them through `selahcue_core::detection::TranscriptEngine::ingest_with_quotes` (with the real quote matcher)
  3. writes hypotheses, detections, per-decode latency and lag to JSON
- Only stage 2 numbers gate shipping. Stage 1 numbers are for iteration speed. A model that wins stage 1 but loses stage 2 (for example because segmentation interacts with it) does not ship.
- Production parity is pinned by reading `WHISPER_AUDIO_CTX`, `EngineConfig::default()` and the `FullParams` builder from the crate itself, not copying them. A later retune then flows into the harness automatically.

### 4.2 Accuracy metrics

- **WER**, after normalisation: Whisper's `EnglishTextNormalizer`, plus a scripture-aware pass (canonicalise references through the same `detect()` normalisation), plus the Pidgin variant list. Reported per slice, per metadata axis, with **speaker-level bootstrap 95% CIs**.
- **CER**, reported alongside WER on every slice, and the **primary** metric on S3 (Pidgin/code-switch), where word boundaries and spelling are unstable.
- **Scripture-reference accuracy** on S2 and naturally occurring references. There are two levels, and both matter:
  - **Transcript-level:** was the tagged reference span transcribed so that the canonical reference is recoverable (book, chapter and verse all correct)? This is reported as *reference exact-match rate*, with partial credit broken out (book correct, chapter wrong, and so on).
  - **Detection-level (end to end):** see §4.3.
- **Entity accuracy** on `<ent>` tags across all slices:
  - *entity recall*: the normalised entity string appears in the aligned hypothesis span
  - *entity CER*: character error within entity spans
  - broken out by entity type (person, place, church/org, biblical name)
  - This is also where FR-108's per-term WER metric is computed for the glossary arm.
- **Hallucination** on S6: committed (final) transcript characters per minute of non-speech, and the **share of non-speech seconds that produce committed text**, which is FR-102's metric.
- **Repetition-loop rate:** share of final segments with a repeated n-gram run above a threshold (Whisper's known failure mode on noisy audio).

### 4.3 Downstream detection impact

This is the metric that matters most to operators, because a correct transcript is not the product; a correct verse in Preview is.

- Ground truth is the `<ref>` tags, canonicalised. Hypotheses are what `TranscriptEngine` actually enqueues from stage 2 output, so the dedup ring and the per-segment boundary behaviour are included.
- Report:
  - **detection recall** for explicit references
  - **detection precision** and **false-positive rate** per hour of speech (METRIC-009: ≤5% on the explicit-reference set)
  - **wrong-verse rate**: detections for the right book but the wrong chapter or verse. This is the most harmful error, because an operator can approve it.
  - **time-to-detection**: detection timestamp minus the end of the spoken reference
- **Boundary-split rate:** the share of references that straddle a segment boundary and are therefore undetectable by construction. This is a pipeline property, not a model property. If it is material, it points to a detection change (cross-segment windowing), not training.
- **Quote-match impact:** precision and recall of fuzzy quote candidates on S1 passages where the preacher reads scripture aloud.
- **Sermon-notes impact (secondary, report-only):** run the notes path on transcripts from the baseline and the best candidate for a handful of sermons, and have a human rate factual errors attributable to transcription.

### 4.4 Operational metrics

- **Per-decode latency**: p50/p95/p99, measured separately for interim decodes and 10 s finals, on each target machine (§4.5).
- **Real-time factor** (decode time ÷ audio duration) for a 10 s final.
- **Transcript lag over a paced run**: mean and max lag across the 126 s paced replay already used in the `audio_ctx` work (86akcfp3u measured 3.6 s rising to 14.0 s before that fix). A candidate must not reintroduce lag growth.
- **Cold-start**: download size, first-load time, SHA-256 verify time.
- **Memory**: peak RSS and resident model bytes against `MAX_MODEL_RESIDENT_BYTES` (2 GiB). The `approx_resident_bytes` table must be corrected with measured values for any new variant.
- **Energy/thermal (report-only)**: sustained 60-minute run on a fanless or low-end laptop, and whether throttling pushes RTF above 1.

### 4.5 Target hardware matrix

- **Mac, Apple Silicon, Metal:** one base M1 8 GB (the floor) and one current M-series. The production model is turbo.
- **Windows, CPU-only:** a typical church PC, for example a 4-core/8-thread Intel i5 (8th–10th gen) with 8 GB RAM, plus one low-end 2-core/4-thread laptop. The production model is small. This tier decides whether a quantised larger model (A3) is viable.
- **Windows with discrete GPU (optional):** only if a CUDA/Vulkan build is planned. Today no shipped build enables it.
- Record exact CPU/GPU, RAM, OS build, power profile and thread count. Run each measurement three times and report the median.

### 4.6 Statistics and anti-cheating rules

- Paired comparisons (same clips, arm vs baseline) with speaker-level bootstrap for Δ-WER CIs.
- Choose thresholds, slices and the primary metric **before** the first candidate is scored (this document, once ratified). No post-hoc slice picking.
- The test set is scored once per final candidate. All tuning uses the dev set.
- Every result row records: model file SHA-256, quantisation, harness commit, test-set manifest version, hardware ID and decode params.

### 4.7 Ship / no-ship thresholds (proposed; owner ratifies, see D7)

A candidate ships for a hardware tier only if **all** of the following hold on that tier, measured by the stage 2 harness against the **best zero-training arm** for the same tier (not just A0):

- **Primary gain:** S1 WER relative reduction **≥15%**, with the 95% CI of Δ-WER excluding zero. The gate is checked on the room-mic sub-slice and on the desk-feed sub-slice separately; both must improve, and the room-mic one must reach ≥15%.
- **Scripture references:**
  - explicit-reference **detection recall improves by ≥10% relative**, or is already ≥95% and does not drop
  - **false-positive rate ≤5%** (METRIC-009) **and** no worse than baseline
  - **wrong-verse rate no worse than baseline**
- **Entities:** entity recall improves by **≥20% relative** (mirrors FR-108's bar). No entity type gets worse by more than 5% relative.
- **No regression elsewhere (forgetting guard):**
  - S5 WER is no worse than baseline by more than **5% relative** overall, and by no more than **0.5 WER points absolute** on LibriSpeech `test-clean`
  - no single S5 accent group worsens by more than 10% relative
- **Non-speech:** FR-102, **≤1% of non-speech seconds produce committed text**, and no worse than baseline. The repetition-loop rate is no worse than baseline.
- **Latency:** p95 final-decode latency within **+10%** of the model it replaces on the same tier. RTF for a 10 s final is **≤0.5** on the tier's floor machine. No lag growth over the paced run.
- **Memory:** resident ≤2 GiB, and peak RSS within +10% of the replaced model.
- **Download:** no larger than the file it replaces, unless the owner accepts the increase (a Windows move from small at 488 MB to a quantised larger model is a deliberate trade).
- **Licence:** every training clip's licence and consent covers commercial distribution of weights (§3.5, §3.6). This gate is binary and has no tolerance.

**Pidgin/code-switch (S3):** report-only by default. If D2 makes it a goal, add "S3 CER relative reduction ≥15%, and no S1/S5 gate broken".

**Outcomes:**

- **Ship.** All gates pass.
- **Ship zero-training only.** A1–A3 pass and fine-tuning adds less than the primary-gain margin over them.
- **Iterate.** A candidate misses only by being within the CI, so collect more data.
- **Stop.** Fine-tuning regresses S5 or FR-102 beyond tolerance after two data-mix iterations.

---

## 5. Fine-tuning arms

### 5.1 Which model sizes

- **small** (244M params), because it is **what every Windows user runs today**. It is the likeliest place for a big relative gain, and it is cheap to train.
- **large-v3-turbo** (809M params; full large-v3 encoder, 4-layer decoder), because it is what every Mac user runs.
  - The shrunken decoder carries less of the language model, so accent adaptation mostly has to happen in the encoder. LoRA target modules must include encoder attention, not just the decoder.
- **medium**: only if A3 shows a quantised medium is the best real-time fit for the Windows tier. Otherwise skip it.
- **base**: skip. It only serves 1-thread hosts, a negligible share of the target.

### 5.2 Method arms

- **B1: LoRA / PEFT.**
  - Rank 16–32 on encoder and decoder q/k/v/o projections. Adapter lr around 1e-4 to 5e-4. Frozen base.
  - Lower forgetting risk by construction, and cheap. whisper.cpp has **no runtime LoRA support**, so adapters are **merged into the base weights before conversion**. Shipping is identical to a full fine-tune, a whole new ggml file.
- **B2: full fine-tune.**
  - lr around 1e-5 with warmup. Encoder unfrozen, or partially frozen: the lower encoder layers are frozen in B2a and nothing is frozen in B2b.
  - Higher ceiling and higher forgetting risk. Run it only if B1 plateaus below the primary-gain gate.
- **Common to both:**
  - SpecAugment and speed perturbation (0.9–1.1).
  - Room-impulse-response and PA-bleed augmentation (convolve clean read speech with measured church IRs, add music at -5 to +10 dB SNR), because most commercially clean data is read, close-mic speech and the target is reverberant PA audio.
  - Early stopping on dev-set S1 WER **and** dev S5 WER together.
- **Match the inference shape.** Production decodes ≤10 s windows with `audio_ctx=512`, so train on segments ≤10 s. It is also worth one ablation to train with the truncated audio context too: a model tuned on 30 s padded inputs and then run at 512 context is a train/serve mismatch the stock model tolerates, but a tuned one may not.

### 5.3 Data mixes

- **M1: Nigerian only.** Partner-church training data, scripted reads, and Common Voice Nigerian-accent English. This is the forgetting upper bound, kept as a diagnostic.
- **M2: Nigerian plus replay.** M1 plus 25–35% general English (LibriSpeech train, Common Voice English other accents) to anchor the original distribution. This is the default candidate.
- **M3: M2 plus domain.** M2 plus consented non-Nigerian sermons and church-register text-matched read speech (scripture readings, announcements), so the domain gain is not credited to the accent gain. It also tells us how much comes from *church* adaptation versus *Nigerian* adaptation.
- **M4: M3 plus code-switch (only if D2 includes Pidgin).** Add Pidgin/code-switch audio, transcribed in Pidgin orthography, with the language token kept as `en` so production decode settings do not change.
- **Label hygiene:** the same normalisation and transcription guideline as the test set, with numbers as words. Verify that the tuned model's output style (digits vs words, punctuation) still feeds `detect()` correctly. A style drift can silently break detection even when WER improves.
- **Rough data need (estimate):**
  - LoRA on small shows gains from about 20–50 h of in-domain accented audio.
  - Turbo likely needs 50–150 h for a robust gain.
  - The commercially clean supply is the binding constraint, which is why partner-church collection sits on the critical path.

### 5.4 Conversion, quantisation and re-evaluation

- **Convert.** Merge adapters, save as HF `transformers` checkpoint, then convert with whisper.cpp's `models/convert-h5-to-ggml.py`. Pin the whisper.cpp commit that matches the vendored `whisper-rs-sys` 0.13.1, so the file format and the loader agree.
- **Quantise.** Use whisper.cpp `quantize` to produce `q8_0` and `q5_0` (and `q5_1` for turbo), and keep f16 as the reference.
- **Re-evaluate every quantised file on the full stage 2 harness.** The f16 fine-tune's numbers do **not** carry over. Accent-specific gains can be fragile under quantisation, so compare each quantised file with its **own quantised stock counterpart** (from A3) as well as with the f16 fine-tune.
- **Metal alignment check.** The `audio_ctx % 4 == 0` rule in `recognizer.rs` concerns whisper.cpp kernels, not weights, so it should hold. Still, run the whole paced replay on Metal once per file to catch a SIGABRT early.
- **Supply chain.** Record the SHA-256 and byte size of each shipped file at conversion time. These become the pinned values in `ModelAsset` (§6).

---

## 6. Shipping through download-on-first-use

### 6.1 What has to change (and what does not)

**Hosting**

- `WhisperModel::asset()` hardcodes the upstream `ggerganov/whisper.cpp` Hugging Face URL for every variant. A tuned model needs a **SelahCue-controlled host**: an org-owned HF repo, or the product's own CDN/object store.
- The URL, SHA-256 and size travel together in the manifest, exactly as today (FR-156 / ADR-0012).
- ADR-0012's Stage-13 signature custody applies. A self-hosted model is a stronger reason to add signing than the upstream mirror was.

**Asset identity**

- The tuned model needs a **distinct file name**, for example `ggml-small-selahcue-ng-v1-q5_0.bin`. The cache is keyed by file name in `default_cache_dir()`, and a distinct name keeps stock and tuned models side by side for instant rollback.
- It also needs its own measured `approx_resident_bytes`.

**Selection (the real design decision, D3)**

- Today selection is `HardwareProbe` only. Choosing a tuned model needs a second input: a **locale or accent choice**, which is FR-167, not yet built. The options are:
  - **(a) Replace the stock asset for a size.** Every user of that tier gets the tuned model. This is only defensible if the S5 regression gate passes with margin.
  - **(b) Locale-aware selection.** Settings → Transcription → "Accent / region: Nigeria", which maps size × locale to an asset. This implements FR-167 and keeps non-Nigerian users on stock weights.
  - **(c) Default by region, overridable.** Pre-select from OS locale or licence country, and let the operator change it.
  - The recommendation is **(b), with (c) as a later nicety**. It limits the blast radius of a forgetting regression to users who opted into the Nigerian model.
- **Switching models** at runtime changes the `MODEL_CACHE` key (a path), so the one-entry cache correctly drops the old context. A switch should take effect at the next "Start listening", never mid-service.

**Labelling and provenance**

- The recognizer label `whisper-{model}` is recorded against each transcript session. Extend it to name the tuned version (`whisper-small-ng-v1-q5_0`), so transcripts, bug reports and quality telemetry are attributable.

**Prompt priming (if A1/A2 ship)**

- This is a decode-param change in `WhisperRecognizer::transcribe`, fed from settings (FR-108 glossary). It needs no new model file.
- `whisper-rs`'s `set_initial_prompt` **panics on an interior NUL byte**. User-entered glossary text must be sanitised first, which matters because this crate's `unwrap_used` lint is currently enforced by nothing (`implementation/desktop/CLAUDE.md`).
- Bound the glossary length (number of terms and total tokens), per the repo's bounded-memory rule, with a test that bites.

**Rollback**

- Keep the stock asset definitions. The locale setting reverts to "Standard" in one click, and a bad tuned version is withdrawn by shipping a manifest that points back to the previous pinned asset.

### 6.2 Feature flags and `LAUNCH_REACHABILITY`

- **Recommended: no new Cargo feature.** A tuned model is a **runtime asset choice** (data plus a setting), not a compile-time capability. The existing `stt` feature already compiles everything needed, and `stt` is tagged `LAUNCH_REACHABILITY: AUTO` / `RELEASE: SAFE` and is what the Windows installer builds.
- **If someone does add a feature** (for example `stt-ng-model` to keep the manifest entry out of some builds), then under `scripts/check_launch_reachability.py`:
  - it **must** carry both a `LAUNCH_REACHABILITY: REQUIRED|AUTO|OPT-IN` tag and a `RELEASE: SAFE|UNSAFE` tag in its comment block in the operator's `Cargo.toml`, or `make ci` hard-fails
  - it would need to be reachable from `make launch` / `make operator` (the repo has been bitten three times by AI features built but unreachable: 86akcmzyq, 86akby7th, 86akd10dq)
  - the Windows installer hardcodes `--features stt`, so it would need editing there too, or Windows (the main beneficiary) would silently not get it
  - Avoiding the flag avoids all three traps.
- **Release safety.** A tuned model reads no developer credential, so it is `RELEASE: SAFE` by nature. The concern is licence cleanliness (§3.5), which no build flag can enforce. Add a model card (training data sources, licences, consent scope, eval results) next to each hosted file. The release checklist should require the card's licence section to be signed off.
- **The `SELAHCUE_STT_MODEL` override** stays as the QA and eval path for side-loading candidates in real builds.

### 6.3 Quality monitoring after ship

- Opt-in only (telemetry is off by default, per ADR-0011). Collect aggregate, content-free signals per model version:
  - detection approve vs dismiss ratio
  - operator transcript-correction rate (FR-106 edits per minute)
  - lag and degraded-status events (FR-104)
- Never collect audio or transcript text without separate consent.
- A drop in the approve ratio on the tuned model relative to stock is the rollback trigger.

---

## 7. Open decisions for the owner

- **D1: Non-commercial corpora.** Do we use AfriSpeech-200 (CC BY-NC-SA 4.0) or NaijaVoices at all?
  - Proposed default: **not for training shipped models**. Evaluation use only after legal review, or never.
  - Alternatively: approach Intron Health for a commercial AfriSpeech licence.
- **D2: Language scope.** Choose one:
  - Nigerian-accented English only (the proposed MVP)
  - plus Nigerian Pidgin and code-switching as a gated goal
  - plus Yoruba/Igbo/Hausa transcription (a different product: language ID, tone marks, scripture detection in those languages; out of scope here)
- **D3: Delivery model.** Choose one:
  - replace the stock model for everyone
  - opt-in "Accent / region" setting (FR-167; proposed)
  - region-defaulted but overridable
- **D4: Platform priority.** Windows CPU / small first (larger user base, bigger expected gain, and it is also where the zero-training quantisation arm may help), or Mac turbo first?
- **D5: Partner-church data programme.** Which churches, who runs consent, how much budget, the retention period, and whether training consent (not just evaluation consent) is sought. This is the critical path.
- **D6: Hosting and signing** of SelahCue-owned model files: an org HF repo or a CDN, and whether to pull ADR-0012 Stage-13 signing forward for self-hosted weights.
- **D7: Ratify the thresholds** in §4.7, in particular:
  - the 15% primary gain
  - the 5% relative S5 regression tolerance
  - whether S3 is gating
- **D8: Cloud reference arm.** May consented evaluation audio be sent to Deepgram for the reference comparison and first-pass drafting? It is data egress, so it needs per-clip consent.
- **D9: Quantisation independent of fine-tuning.** Stock models ship as f16, while ADR-0010 assumed INT8. If A3 shows quantised models are accurate enough and faster, should that change ship on its own, ahead of any fine-tuning? The ADR-0010 wording should be corrected either way.
- **D10: Transcription vendor vs in-house.** Who does the two-pass Nigerian transcription, and under what DPA?

---

## 8. Phasing, effort and cost (rough estimates)

All figures are **estimates** (INFERRED / Low–Med confidence), in 2026 USD, for planning only.

**Phase 0: harness and plumbing (about 2–3 engineer-weeks)**

- Stage 2 Rust harness (§4.1), scripture-aware normaliser, bootstrap/report script, hardware matrix runs.
- A1/A2 need `set_initial_prompt` wired through a param seam. That is a small code change, but it gets its own ticket and review.

**Phase 1: test set (about 4–8 weeks elapsed, 1–2 engineer-weeks of effort)**

- Consent drafting and legal review: owner/legal time.
- Recording at partner churches: 8+ churches, about 2 services each.
- Scripted reference reads: 40+ contributors × about 15 min at about $10–20 per contributor, **about $0.5k–1k**.
- Two-pass transcription of about 14 h at about $1.5–3 per audio minute per pass, with a third-party adjudication share: **about $3k–6k**.

**Phase 2: baselines A0–A4 and R (about 1–2 engineer-weeks)**

- Hardware is the machines listed in §4.5. Budget **about $1.5k–3k** if a floor Windows PC and a base M1 must be bought.
- Deepgram reference runs cost a few dollars.
- **Decision point:** if zero-training arms pass §4.7, stop and ship those.

**Phase 3: training data collection (about 6–12 weeks elapsed, can overlap phase 1)**

- 50–150 h of consented, training-scope audio from partner churches, plus Common Voice/FLEURS/LibriSpeech mixes.
- Transcribing training data needs less rigour: single pass plus spot-check at about $1–1.5/min, which for 100 h is **about $6k–9k**. This is the largest cost line.
- Pseudo-labelling with a large model plus a human spot-check is a cheaper option (about 30–50% of that), with a known risk of teaching the model its own errors.

**Phase 4: training arms (about 2–3 engineer-weeks)**

- Cloud GPU (A100/H100 class, about $2–4/GPU-hour under a DPA):
  - LoRA on small across 3 mixes: about 10–30 GPU-h
  - LoRA on turbo: about 30–80 GPU-h
  - full fine-tune of small: about 20–40 GPU-h
  - one full fine-tune of turbo if needed: about 60–150 GPU-h
- With about 2× for reruns, the total is **about $0.5k–2.5k compute**.
- Conversion, quantisation and stage 2 re-evaluation of about 12–20 files: about 1 engineer-week, which is included above.

**Phase 5: ship (about 2–3 engineer-weeks)**

- Asset hosting, manifest and pinning, FR-167 locale setting, label and provenance, model card, rollback path, the four-reviewer gate (code, security, QA, performance), and the Windows installer check.

**Totals (estimate)**

- About **10–16 engineer-weeks**.
- About **$12k–25k** in direct spend, dominated by transcription.
- About **3–5 months** elapsed, gated by partner-church consent and collection rather than engineering.
- The zero-training exit after phase 2 costs about 20–25% of the full programme.

---

## 9. Risks (beyond those already gated above)

- **Catastrophic forgetting.** Guarded by the S5 slice, the replay mix M2, LoRA-first, and locale-scoped delivery (D3), which limits the blast radius.
- **Licence contamination.** A single non-commercial clip in the training mix taints the weights. Enforce it with the manifest's licence field, a training-pipeline assertion that refuses any clip whose scope is not "commercial-training", and the model card sign-off.
- **Consent drift.** A church leadership change can withdraw consent. Mitigated by per-version training manifests and the "next version" withdrawal wording.
- **Output-style drift breaks detection.** A tuned model that writes "Jn 3:16" or drops "verse" may lower WER but break `detect()`. Guarded by the downstream gate (§4.3) and label hygiene (§5.3).
- **Prompt echo.** Priming arms can hallucinate glossary terms on music. Guarded by the FR-102 gate on S6.
- **Pipeline-bound limits misread as model limits.** The boundary-split rate (§4.3) and the 10 s / `audio_ctx` envelope cap what any model can do. Report them separately, so training is not asked to fix segmentation.
- **Evaluation leakage.** The same preacher appears at two churches, or a sermon is re-broadcast. De-duplicate by speaker and by audio fingerprint across splits.

---

## 10. Completion predicate for the evaluation programme (for the Goal Contract, when approved)

- C-1: test-set manifest v1 exists, with a licence and consent scope for every clip, and inter-annotator WER ≤5% on the double-transcribed sample.
- C-2: stage 2 harness reproduces production params by reading them from the crate, proven by a test that fails if `WHISPER_AUDIO_CTX` or `EngineConfig::default()` diverges from what the harness uses.
- C-3: baseline report covering A0–A4 on every §4.5 tier, with CIs.
- C-4: the §4.7 thresholds ratified by the owner (D7) **before** any fine-tuned candidate is scored on the test set.
- C-5: each candidate's stage 2 report on its shipped quantisation, with a ship, zero-training ship, iterate or stop outcome recorded against §4.7.
- C-6: for a "ship" outcome: a model card with licence sign-off, a pinned asset (URL, SHA-256, size), locale selection behind FR-167, and passed code, security, QA and performance reviews.
