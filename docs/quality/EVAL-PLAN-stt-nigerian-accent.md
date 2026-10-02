# Evaluation plan: Whisper fine-tuning for Nigerian-accented English (and Pidgin / code-switching)

- **Status:** DRAFT for owner review. Nothing here has been run yet; every number below is a proposal or an estimate, labelled as such.
- **Role:** AI Engineer (Nova). **Date:** 2026-10-01; revised 2026-10-02 after review. **Baseline revision:** `origin/main` at `b73d389`; the code facts in §1, §4.1 and §10 were re-checked against `origin/main` at `feaee70` on 2026-10-02.
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
- In practice the build target decides the model. There is no distribution data in the repo, so how many users run each is **unknown**:
  - **macOS** builds enable `metal` (a `cfg(target_os = "macos")` dependency in the operator `Cargo.toml`), so a macOS build selects **large-v3-turbo on Metal**. No workflow in the repo builds or ships a macOS installer, so this is what a macOS build selects, not a measured user population.
  - **Windows**: the only workflow that ships an installer (`.github/workflows/windows-installer.yml`) builds `--features stt` with no GPU feature, so that installer's builds select **small on the CPU**.
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

- Energy VAD brackets utterances. An utterance is force-closed at 10 s (`max_utterance_samples`), deliberately just under the 10.24 s audio-context horizon. Closing depends only on the VAD and that sample cap, never on what the recognizer returned (`SttEngine::process_current_frame`), so segment boundaries are a property of the audio and the engine config alone (this matters for §4.3).
- **Interims are a production override, not the engine default.** `EngineConfig::default()` has interims **off** (`interim_interval: Duration::ZERO`, `interim_max_samples: 0`; `engine.rs`). The capture path in the operator (`selahcue-operator/src/listening.rs`, `run_on_device_with_recognizer`, about L1172-1176) builds the engine with `interim_interval` 800 ms and `interim_max_samples: INTERIM_WINDOW_SAMPLES` (a 6 s sliding window, 96,000 samples; the const is at about L110). The 800 ms is wall-clock measured from when the previous interim's decode **completed**, so the real cadence is 800 ms plus the decode time. Each interim therefore decodes at most the most recent 6 s, and only the final decodes the whole utterance (up to 10 s). Both values live in the operator today, not in `selahcue-stt`.

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

**Arm A0: shipped models, as configured (the baseline)**

- `base`, `small`, `medium` and `large-v3-turbo`, f16, with production params: greedy, `audio_ctx` 512, single segment, `en`, no prompt, and the production engine config of §4.1 (interims on).
- Report all four so we know the size/accuracy curve. The two that matter are **small on the Windows CPU tier** and **turbo on the Mac Metal tier**, because those are what the code selects for each build today (§1).
- **A0 is the comparator for every zero-training arm (A1-A3)**, on the same tier. A zero-training arm is never measured against "the best zero-training arm", which would include itself. Fine-tuned candidates are measured against the best zero-training arm (Z-best), defined in §4.7.

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
- A quantised **larger** model replacing `small` is a **size change**, so the §4.7 latency and memory gates use their absolute form (RTF and the 2 GiB budget), not "within 10% of the model it replaces", which no larger model could meet.
- This arm also supplies the post-quantisation reference that §5.4 needs.

**Arm A4: language setting (zero training, Pidgin slice only)**

- `language = "en"` (today) against `auto`, on the Pidgin/code-switch slice. This is report-only, to see whether forcing English is hurting.

**Arm R: reference arms (not shippable as they stand, used for calibration)**

- `large-v3` f16 (non-turbo) on a GPU box, as an accuracy ceiling for the Whisper family.
- Deepgram `nova-3`, `en-US` against `en` and with keyterm prompting. **Only** on audio whose consent covers third-party processing (§3.6).

**Deliverable of phase 1:** a baseline report with one row set per arm × model × hardware, covering every metric in §4. If A1–A3 (alone or combined, for example A3 plus A1) already meet the §4.7 ship thresholds **measured against A0**, stop and ship those (glossary, quantised larger model on Windows) before spending on training.

---

## 3. The test set

### 3.1 Principles

- **Frozen and versioned.** A manifest lists every clip's SHA-256, speaker ID, church ID, slice and licence/consent basis, and the manifest itself is hashed. Any change creates a new version, and results always cite the version.
- **Held out by speaker and by church**, not by utterance. No test speaker and no test church appears in any training or dev data. A **dev set** (separate speakers and churches again; sized and costed in §3.2) is used for hyperparameter and checkpoint selection. The test set is used once per candidate, at the end.
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

**Dev set (separate speakers and churches; sizing proposed, the owner ratifies it under D5):**

- Used for checkpoint selection, the stage 1 screen (§4.1) and the variance estimate in the sizing rationale below. It shares **no** speaker, church or recording with the test set or with any training data (§3.1, §9).
- **Dev S1: about 2 h** of Nigerian sermon audio from **at least 3 churches and at least 10 speakers**, both capture paths where possible.
- **Dev S2: about 0.5 h** of scripted references: at least 150 references (a quarter of S2's 600) from at least 10 readers.
- **Dev S5: about 0.5 h** from the public dev splits (LibriSpeech `dev-clean`/`dev-other`, FLEURS `en_us` dev, Common Voice dev). These are already transcribed, so they carry no transcription cost.
- **Dev S6: about 0.25 h** of non-speech.
- **Dev S3 (Pidgin): about 0.5 h**, only if D2 includes Pidgin.
- Total about 3.25 h (3.75 h with S3). Only dev S1 and S2 need human transcription: 2.5 h = 150 min.
- **Cost, from this plan's own unit costs (§8):**
  - transcription at the test-set protocol (two passes at $1.5–3 per audio minute per pass): 150 min × 2 × $1.5–3 = $450–900. With the adjudication allowance the test-set line carries (about +19%: $3k against 840 min × 2 × $1.5 = $2,520, and $6k against 840 min × 2 × $3 = $5,040), about $540–1,070
  - scripted reads: 10 contributors × $10–20 = $100–200
  - **total about $0.6k–1.3k** ($640–1,270). Dev S3 would add 30 min × 2 × $1.5–3 = $90–180
  - recording logistics, legal review and consent costs are not costed for any set in this plan

**Sizing rationale (estimate; it replaces the earlier "±1–1.5 WER points" claim, which was not shown):**

- **Where the WER level comes from.** The 15–25% real-room WER used here is **this plan's own planning assumption**, not a CAPABILITY-ASSESSMENT figure. CAPABILITY-ASSESSMENT §1.2 gives "plausibly high-single-digit to high-teens %" for real-room WER, marked INFERRED / Med-Low and not specific to Nigerian accents, and its §4 lists accent-specific real-room WER as UNKNOWN. The plan's range reaches above that on the assumption that Nigerian accents plus PA bleed add to it. Phase 2 replaces it with a measurement. At 15–25% the 15% relative bar is 2.25–3.75 WER points absolute (0.15 × 15 and 0.15 × 25).
- **What is being sized.** The ship gate (§4.7) is a *paired relative* WER reduction of at least 15%, checked on each gated sub-slice (room-mic, desk-feed) and on each hardware tier. The independent units are speakers (and, for room and PA effects, churches), not words. At an assumed 130 spoken words per minute (an assumption, to be measured on the pilot), 6 h is about 46,800 words (6 × 60 × 130), and word-level sampling error is small: at 15% WER it is √(0.15 × 0.85 / 46,800) = 0.17 points.
- **Formula.** Let σ_r be the standard deviation, across speakers, of each speaker's relative WER reduction (candidate against comparator), and K the number of distinct speakers in the sub-slice. The 95% CI half-width on the mean reduction is about 1.96 × σ_r / √K. For 80% power to exclude zero when the true reduction is exactly the 15% threshold, 0.15 ≥ (1.96 + 0.84) × σ_r / √K, so **K ≥ (2.8 × σ_r / 0.15)²**. This is a speaker-mean approximation of the pooled-WER reduction the gate uses.

  | σ_r (assumed) | speakers needed, K |
  |---|---|
  | 0.15 | 8 (7.8) |
  | 0.25 | 22 (21.8) |
  | 0.35 | 43 (42.7) |
  | 0.50 | 88 (87.1) |

  Read the other way: K = 30 is enough only if σ_r ≤ 0.15 × √30 / 2.8 = 0.29; K = 15 only if σ_r ≤ 0.15 × √15 / 2.8 = 0.21; and 8 churches only if the church-to-church spread of the gain is ≤ 0.15 × √8 / 2.8 = 0.15.
- **σ_r is unknown: it has not been measured.** The earlier "±1–1.5 points at 6 h and 30+ speakers" figure implied an unpaired between-speaker WER standard deviation of 2.8–4.2 points (1.96 × σ / √30 = 1 to 1.5), which was an assumption. The table is a *requirement to be met*, not a result.
- **Sub-slices.** "30+ speakers" is a count across S1. A speaker counts in the room-mic or the desk-feed sub-slice only if captured on that path, so a sub-slice can hold fewer than 30 (this plan does not fix how the ~6 h divides between the two paths). Each gated sub-slice needs K at or above the formula's value on its own. A sub-slice below its K cannot gate: it is reported with its CI, and the owner decides under D7 whether to extend recruitment (which re-opens Phase 1 collection) or keep it report-only.
- **Hardware tiers.** Every tier scores the **same clips**, so tiers share K and add no power. What differs per tier is the comparator, the baseline WER and σ_r (a tier with a lower baseline WER has fewer errors per speaker, so its σ_r may be larger). K is therefore re-derived **per tier**, from σ_r measured in Phase 2 on the dev set as the paired per-speaker spread between A0 and each zero-training arm. That is a proxy, because a fine-tune's spread may differ, and with 10 or more dev speakers the estimate is itself rough, so re-check it on the test set after scoring.
- **Churches.** With 8+ churches as the independent units for room and PA effects, resample at the church level (church, then speaker) as well as at the speaker level, and report both.
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
  1. streams each test recording through the **real** `SttEngine` (VAD, resample, interims, 10 s force-close), **built with the production engine config (below)**, using the crate's fake audio source at real-time pace, with the real `WhisperRecognizer`
  2. collects final segments with timestamps, feeds them through `selahcue_core::detection::TranscriptEngine::ingest_with_quotes` (with the real quote matcher)
  3. writes hypotheses, detections, per-decode latency and lag to JSON
- Only stage 2 numbers gate shipping. Stage 1 numbers are for iteration speed. A model that wins stage 1 but loses stage 2 (for example because segmentation interacts with it) does not ship.
- **Production parity is by construction, not by copy.** What the harness has to read from the crate, and where that stands today:
  - **Engine config: it must be the production config, not `EngineConfig::default()`.** The default has interims off (`interim_interval: Duration::ZERO`, `interim_max_samples: 0`; `engine.rs`). Production overrides it to an 800 ms interim interval and a 6 s sliding window (`interim_max_samples: INTERIM_WINDOW_SAMPLES`) in an inline struct literal in the operator's `listening.rs` (about L1172-1176; the const is at about L110). Neither is reachable from `selahcue-stt`, where the harness lives, so a harness that read the default would run with no interims and report wrong interim-latency and lag numbers (§4.4). Phase 0 therefore has to **expose the production config as a named constant or constructor in `selahcue-stt`** (for example `EngineConfig::production()`; the name is the ticket's call), switch `listening.rs` to call it, and have the harness read that same definition. This is a small production-code change, so it gets its own ticket and review (Phase 0).
  - **Audio-context horizon.** `WHISPER_AUDIO_CTX` is private to the `whisper` module in `recognizer.rs`, and its always-compiled mirror `engine::WHISPER_AUDIO_CTX_HORIZON_SAMPLES` is `pub(crate)`. A harness in a `tests/` or `src/bin/` target cannot read either until one is made public.
  - **Decode params.** The `FullParams` builder is inline in `WhisperRecognizer::transcribe`. Stage 2 inherits it by driving the real recognizer, so there is nothing to copy. Stage 1's CLI flags are hand-mirrored from it, which is one more reason stage 1 does not gate.
  - A later retune of any of these then flows into the harness automatically. §10 C-2 says how that is proven and where the proof runs.

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
- **Detection outcomes, defined once and used by every gate.** The harness matches each detection `TranscriptEngine` enqueues to the `<ref>` tags by time overlap, one to one, and classifies it as exactly one of:
  - *correct*: it carries the tagged canonical reference
  - *wrong-verse*: it overlaps a `<ref>` of the same book but carries a different chapter or verse. This is the most harmful error, because an operator can approve it.
  - *spurious*: it overlaps no `<ref>`, or one of a different book. A further detection inside an already-matched `<ref>` span also counts as spurious, so duplicate enqueues show up as errors.
- Report:
  - **false-positive (FP) rate = (spurious + wrong-verse) ÷ all detections**, which is 1 − precision. It is a per-detection percentage, the form METRIC-009 / FR-121 state ("≤5%"). The PRD does not name the denominator, so this is the plan's reading of it, for D7 to ratify. The ≤5% bar is evaluated on S2, the explicit-reference set METRIC-009 names, and the rate is reported on S1 too. At 600 detections the 95% interval around 5% is about ±1.7 points (1.96 × √(0.05 × 0.95 / 600)), so "no worse than the comparator" is judged on the paired same-clip comparison with its CI, not by comparing two rounded percentages.
  - **wrong-verse rate = wrong-verse ÷ all detections** (a subset of the FP rate, gated separately because of its harm), and the **spurious share** likewise.
  - **spurious detections per hour of speech** on S1: report-only, as the noise an operator feels. It has no threshold and is not a gate.
  - **detection recall** = correct detections ÷ `<ref>` tags, computed two ways (next bullet)
  - **time-to-detection**: detection timestamp minus the end of the spoken reference
- **Boundary-split rate and recall.** A `<ref>` whose audio span crosses a final-segment boundary is *straddling*, and is undetectable by construction because detection runs per segment. This is a pipeline property, not a model property. Segment boundaries come from the VAD and the 10 s force-close, which depend on the audio and engine config only and not on what the recognizer returns (§1), so the **straddling set is identical for every arm** and the non-straddling set is a like-for-like comparison. Report **recall over all references** and **recall over non-straddling references**, plus the **boundary-split rate** (straddling ÷ all references). The ship gate (§4.7) uses the non-straddling recall, so training is not asked to fix segmentation. If the boundary-split rate is material, it points to a detection change (cross-segment windowing), not training.
- **Quote-match impact:** precision and recall of fuzzy quote candidates on S1 passages where the preacher reads scripture aloud.
- **Sermon-notes impact (secondary, report-only):** run the notes path on transcripts from the baseline and the best candidate for a handful of sermons, and have a human rate factual errors attributable to transcription.

### 4.4 Operational metrics

- **Per-decode latency**: p50/p95/p99, measured separately for interim decodes (each over the production 6 s sliding window) and 10 s finals, on each target machine (§4.5).
- **Interim cadence** implied by the production config: 800 ms plus the p95 interim decode time (§1). Report it; it is not a gate on its own, the paced-run lag below is.
- **These numbers are only valid under the production engine config** (§4.1). Under `EngineConfig::default()` interims are off, so a harness reading the default would measure no interim latency at all and would understate decode load, and with it transcript lag.
- **Real-time factor** (RTF: decode time ÷ audio duration) for a 10 s final.
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

- Paired comparisons (same clips, arm vs its comparator, §4.7) with speaker-level bootstrap for Δ-WER CIs, plus the church-level resampling of §3.2.
- Choose thresholds, slices and the primary metric **before** the first candidate is scored (this document, once ratified). No post-hoc slice picking.
- The test set is scored once per final candidate. All tuning uses the dev set.
- Every result row records: model file SHA-256, quantisation, harness commit, test-set manifest version, hardware ID and decode params.

### 4.7 Ship / no-ship thresholds (proposed; owner ratifies, see D7)

A candidate ships for a hardware tier only if **all** of the following hold on that tier, measured by the stage 2 harness against its **comparator** for the same tier:

- **Comparators (so that no arm is compared with itself).**
  - **A0 is the baseline** (§2): the shipped model for that tier, as configured.
  - A **zero-training arm** (A1, A2, A3, or a combination such as A3 plus A1) is compared with **A0**.
  - A **fine-tuned candidate** (§5) is compared with **Z-best**, the best zero-training arm for that tier: the arm or combination with the lowest S1 WER among those that pass the safety gates below (forgetting guard, non-speech, latency, memory, licence) against A0. An arm that fails one of those, for example a prompt that echoes on music, cannot be Z-best. If no zero-training arm beats A0 on S1 WER while passing them, **Z-best = A0**. A4 is report-only and is never Z-best.
  - "Baseline" and "comparator" below mean A0 for a zero-training arm and Z-best for a fine-tuned candidate.
- **Primary gain:** S1 WER relative reduction **≥15%** against the comparator, with the 95% CI of Δ-WER excluding zero. The gate is checked on the room-mic sub-slice and on the desk-feed sub-slice separately; both must improve, and the room-mic one must reach ≥15%. A sub-slice with fewer distinct speakers than the §3.2 sizing formula requires for that tier cannot gate: it is reported with its CI, and the owner decides under D7.
- **Scripture references** (definitions in §4.3):
  - explicit-reference **detection recall over non-straddling references improves by ≥10% relative**, or is already ≥95% and does not drop. References that straddle a segment boundary are excluded because they are undetectable by construction; recall over all references and the boundary-split rate are reported next to it, not gated.
  - **FP rate ≤5%** on S2 (METRIC-009; FP rate = (spurious + wrong-verse) ÷ all detections) **and** no worse than the comparator on S2 and on S1
  - **wrong-verse rate no worse than the comparator**
- **Entities:** entity recall improves by **≥20% relative** (mirrors FR-108's bar). No entity type gets worse by more than 5% relative.
- **No regression elsewhere (forgetting guard):**
  - S5 WER is no worse than the comparator by more than **5% relative** overall, and by no more than **0.5 WER points absolute** on LibriSpeech `test-clean`
  - no single S5 accent group worsens by more than 10% relative
- **Non-speech:** FR-102, **≤1% of non-speech seconds produce committed text**, and no worse than the comparator. The repetition-loop rate is no worse than the comparator.
- **Latency.** There are two forms, chosen by whether the candidate changes the Whisper size relative to its comparator:
  - **Like for like** (same Whisper size as the comparator, any quantisation; for example a tuned `small` against `small`, or a prompt-priming arm against A0): p95 final-decode latency within **+10%** of the comparator on the same tier.
  - **Size change** (a different Whisper size from the comparator; for example A3 replacing `small` with a quantised `medium` or turbo, or a tuned turbo replacing `small`): the +10% test does not apply, because a larger model is slower by construction and could never pass it. Only the absolute bound below applies, and the cost is accepted explicitly through the Download and Memory gates.
  - **Both forms:** **p95 RTF ≤0.5** for a 10 s final on the tier's floor machine (§4.5), and **no lag growth** over the paced run. The implied interim cadence (§4.4) is reported.
- **Memory.** Resident model bytes ≤2 GiB (`MAX_MODEL_RESIDENT_BYTES`) for every candidate. For a like-for-like candidate, peak RSS must also be within +10% of the comparator; for a size change that relative test does not apply, and measured peak RSS is reported against the budget.
- **Download:** no larger than the file it replaces, unless the owner accepts the increase (a Windows move from small at 488 MB to a quantised larger model is a deliberate trade).
- **Licence:** every training clip's licence and consent covers commercial distribution of weights (§3.5, §3.6). This gate is binary and has no tolerance.

**Pidgin/code-switch (S3):** report-only by default. If D2 makes it a goal, add "S3 CER relative reduction ≥15%, and no S1/S5 gate broken".

**Outcomes:**

- **Ship.** All gates pass against the comparator.
- **Ship zero-training only.** A zero-training arm (or combination) passes every gate against A0, and no fine-tuned candidate clears the gates against Z-best (that is, fine-tuning adds less than the primary-gain margin over the zero-training arms).
- **Iterate.** A candidate misses only by being within the CI, so collect more data.
- **Stop.** Fine-tuning regresses S5 or FR-102 beyond tolerance after two data-mix iterations.

---

## 5. Fine-tuning arms

### 5.1 Which model sizes

- **small** (244M params), because it is **what the Windows installer's builds select today** (the only installer workflow in the repo, `windows-installer.yml`; how many users that is, is not known). It is the likeliest place for a big relative gain, and it is cheap to train.
- **large-v3-turbo** (809M params; full large-v3 encoder, 4-layer decoder), because it is what a macOS build selects today (Metal). No workflow ships a macOS installer yet, so this is not a count of Mac users.
  - The shrunken decoder carries less of the language model, so accent adaptation mostly has to happen in the encoder. LoRA target modules must include encoder attention, not just the decoder.
- **medium**: only if A3 shows a quantised medium is the best real-time fit for the Windows tier. Otherwise skip it.
- **base**: skip. Only 1-thread hosts select it, which we expect to be a small share of the target (unmeasured).

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
- `whisper-rs`'s `set_initial_prompt` reportedly **panics on an interior NUL byte**. This claim is **unverified**: it has not been checked against the `whisper-rs` 0.14.4 sources in this revision, so confirm it before relying on it. Either way, user-entered glossary text must be sanitised (NUL stripped or rejected) before it reaches the call, which matters because this crate's `unwrap_used` lint is currently enforced by nothing (`implementation/desktop/CLAUDE.md`).
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
- **D4: Platform priority.** Windows CPU / small first (it has the only shipping installer workflow today, the expected gain is bigger on the smaller model (§5.1), and it is also where the zero-training quantisation arm may help), or Mac turbo first? The relative size of the Windows and Mac user bases is **not known**: no macOS installer ships and the repo holds no usage data, so the owner supplies that input.
- **D5: Partner-church data programme.** Which churches, who runs consent, how much budget, the retention period, and whether training consent (not just evaluation consent) is sought. This is the critical path. Test, dev and training data must come from **disjoint** churches and speakers (§3.1, §9), so the programme needs the sum of three church counts:
  - **test:** at least 8 churches and 30+ speakers (§3.2)
  - **dev:** at least 3 churches and at least 10 speakers (proposed, §3.2), costed at about $0.6k–1.3k (§8)
  - **training: not yet fixed.** It follows from how many hours each church can contribute: N_train = ⌈training hours ÷ hours per church⌉. At 10 h per church, the plan's 50–150 h needs 5–15 churches; at 100 h, 5 h per church needs 20 and 2 h per church needs 50 (arithmetic only, not a forecast). The owner sets the target.
  - **total: at least 8 + 3 + N_train = 11 + N_train disjoint partner churches** (for example 21 at N_train = 10), plus the same preacher never appearing in two splits.
- **D6: Hosting and signing** of SelahCue-owned model files: an org HF repo or a CDN, and whether to pull ADR-0012 Stage-13 signing forward for self-hosted weights.
- **D7: Ratify the thresholds** in §4.7, in particular:
  - the 15% primary gain
  - the 5% relative S5 regression tolerance
  - whether S3 is gating
  - the FP-rate definition (per detection, §4.3) and the non-straddling recall basis
  - the size-change latency gate (p95 RTF ≤0.5, no relative test) and what happens to a sub-slice that is under-powered under the §3.2 sizing
- **D8: Cloud reference arm.** May consented evaluation audio be sent to Deepgram for the reference comparison and first-pass drafting? It is data egress, so it needs per-clip consent.
- **D9: Quantisation independent of fine-tuning.** Stock models ship as f16, while ADR-0010 assumed INT8. If A3 shows quantised models are accurate enough and faster, should that change ship on its own, ahead of any fine-tuning? The ADR-0010 wording should be corrected either way.
- **D10: Transcription vendor vs in-house.** Who does the two-pass Nigerian transcription, and under what DPA?

---

## 8. Phasing, effort and cost (rough estimates)

All figures are **estimates** (INFERRED / Low–Med confidence), in 2026 USD, for planning only.

**Phase 0: harness and plumbing (about 2–3 engineer-weeks)**

- Stage 2 Rust harness (§4.1), scripture-aware normaliser, bootstrap/report script, hardware matrix runs.
- A1/A2 need `set_initial_prompt` wired through a param seam. That is a small code change, but it gets its own ticket and review.
- Expose the production engine config as a named definition in `selahcue-stt` that `listening.rs` also calls (§4.1), and give the parity test a CI route (§10 C-2). Both are small production-code and CI changes, each with its own ticket and review.

**Phase 1: test and dev sets (about 4–8 weeks elapsed, 1–2 engineer-weeks of effort; the dev set is not separately estimated and is assumed to fit in this range)**

- Consent drafting and legal review: owner/legal time.
- Recording at partner churches: 8+ test churches, about 2 services each, plus 3+ separate dev churches (§3.2).
- Scripted reference reads: 40+ contributors × about 15 min at about $10–20 per contributor, **about $0.5k–1k**.
- Two-pass transcription of about 14 h at about $1.5–3 per audio minute per pass, with a third-party adjudication share: **about $3k–6k**.
- Dev set (§3.2): **about $0.6k–1.3k** (transcription $540–1,070 plus scripted reads $100–200).

**Phase 2: baselines A0–A4 and R (about 1–2 engineer-weeks)**

- Hardware is the machines listed in §4.5. Budget **about $1.5k–3k** if a floor Windows PC and a base M1 must be bought.
- Deepgram reference runs cost a few dollars.
- **Decision point:** if zero-training arms pass §4.7 against A0, stop and ship those.

**Phase 3: training data collection (about 6–12 weeks elapsed, can overlap phase 1)**

- 50–150 h of consented, training-scope audio from partner churches, plus Common Voice/FLEURS/LibriSpeech mixes.
- Transcribing training data needs less rigour: single pass plus spot-check at about $1–1.5/min, which for 100 h is **about $6k–9k**. This is the largest cost line. Across the plan's 50–150 h range it is 50 h × 60 min × $1–1.5 = $3k–4.5k up to 150 h × 60 min × $1–1.5 = $9k–13.5k.
- Pseudo-labelling with a large model plus a human spot-check is a cheaper option (about 30–50% of that), with a known risk of teaching the model its own errors.
- Engineering effort for this phase (ingest, normalisation, de-duplication, the licence/consent manifest assertion of §9) is **not estimated** in this plan.

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

**Totals (estimate), rebuilt from the phase lines above.** The earlier totals (10–16 engineer-weeks, $12k–25k, and "the zero-training exit costs about 20–25%") did not reconcile with the phase lines and are withdrawn.

| Phase | Engineer-weeks | Direct spend |
|---|---|---|
| 0 harness and plumbing | 2–3 | none listed |
| 1 test and dev sets | 1–2 | reads $0.5k–1k + test transcription $3k–6k + dev set $0.6k–1.3k = $4.1k–8.3k |
| 2 baselines | 1–2 | hardware $1.5k–3k (only if bought); Deepgram runs a few dollars, counted as 0 |
| 3 training data | not estimated | training transcription $3k–13.5k over 50–150 h ($6k–9k at 100 h) |
| 4 training arms | 2–3 | compute $0.5k–2.5k |
| 5 ship | 2–3 | none listed (hosting is not costed) |
| **Sum** | **8–13, plus Phase 3 (not estimated)** | **$9.1k–27.3k over 50–150 h; $12.1k–22.8k at 100 h** |

- **Engineer-weeks:** 2+1+1+2+2 = 8 at the low ends and 3+2+2+3+3 = 13 at the high ends. Phase 3's engineering is missing from the sum, so read **8–13 as a lower bound**.
- **Direct spend:** low = 4.1 + 1.5 + 3.0 + 0.5 = $9.1k (50 h, $1/min); high = 8.3 + 3 + 13.5 + 2.5 = $27.3k (150 h, $1.5/min). At the 100 h planning point it is 4.1 + 1.5 + 6 + 0.5 = $12.1k up to 8.3 + 3 + 9 + 2.5 = $22.8k. The earlier "$12k–25k" sat near the 100 h case only and did not cover the 150 h that §5.3 and Phase 3 allow (the same lines without the dev set give $11.5k–21.5k at 100 h and $8.5k–26.0k across 50–150 h). If the Windows PC and base M1 already exist, subtract the $1.5k–3k hardware line. Transcription (test, dev and training together) is the largest cost. Recording logistics, legal review, consent fees and hosting are not costed.
- **Elapsed:** about **3–5 months**, gated by partner-church consent and collection rather than engineering (unchanged; not derived from the phase lines).
- **Zero-training exit after phase 2** (phases 0–2): 4–7 of the listed 8–13 engineer-weeks (4/8 = 50%, 7/13 = 54%), and $5.6k–11.3k of $12.1k–22.8k at the 100 h point (46% to 50%). That is about **half** of the programme, not 20–25%, because the harness, test set, dev set and baselines are needed whatever the outcome. Counting Phase 3's missing engineering effort would lower the effort share somewhat.

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
- C-2: the stage 2 harness reproduces production by reading it, not copying it. Concretely, it builds `SttEngine` from a **single named production engine config** in `selahcue-stt` (interim 800 ms, 6 s sliding window; **not** `EngineConfig::default()`, where interims are off) that the operator's `listening.rs` also calls, and it reads the audio-context horizon from the crate (§4.1). This is proven by a test that fails if the config the capture path actually builds diverges from that definition, or if the harness stops reading it.
  - **The test must bite.** Per `implementation/desktop/CLAUDE.md`'s methodology, assert against the single definition, not a re-derived copy, and mutation-verify it: hand-edit the 800 ms or the 6 s window in the capture path (or in the harness) and confirm the test goes red, then restore.
  - **How it runs in CI.** `selahcue-stt` is excluded from the workspace and no CI job runs its tests (only `cargo audit` touches it; `implementation/desktop/CLAUDE.md`, tracked on 86ak5rjh7), so a test placed only there would not run in CI. C-2 is met only when one of these holds, and the Phase 0 ticket names which:
    - (i) a `make ci` and CI step runs `cargo test --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml`. The config half of the parity test needs no model file and no native toolchain, because `engine::WHISPER_AUDIO_CTX_HORIZON_SAMPLES` is always compiled and pinned equal to the real constant by a compile-time assertion, so the default-feature test run is enough.
    - (ii) the capture-path assertion lives in `selahcue-operator`, whose tests do run in CI (the `operator-native` job, with `--features stt,cloud-stt`), and checks that the engine config `listening.rs` builds equals the named production config.
  - Until (i) or (ii) lands, C-2 is evidenced only by a local run whose output is attached to the ticket, and is **not CI-enforced**. The stage 2 runs themselves need a model file and real hardware, so they stay manual by nature; only the parity test is CI-shaped.
- C-3: baseline report covering A0–A4 on every §4.5 tier, with CIs.
- C-4: the §4.7 thresholds ratified by the owner (D7) **before** any fine-tuned candidate is scored on the test set.
- C-5: each candidate's stage 2 report on its shipped quantisation, with a ship, zero-training ship, iterate or stop outcome recorded against §4.7.
- C-6: for a "ship" outcome: a model card with licence sign-off, a pinned asset (URL, SHA-256, size), locale selection behind FR-167, and passed code, security, QA and performance reviews.
