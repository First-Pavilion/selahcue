# SelahCue — Candid Capability Assessment (RP-03 Transcription & RP-04 Scripture Detection)

**Research date:** 2026-07-23
**Author role:** AI Engineer + Product Researcher
**Purpose:** An honest, non-marketing assessment of what live transcription and automatic scripture detection can and cannot do in a real church. **No perfect-accuracy claims are made.** All numbers are ranges under stated conditions and degrade in real rooms.

## Classification legend

- **OBSERVED** — measured by us. *(None yet — no in-house benchmarking done; see UNKNOWNs.)*
- **DOCUMENTED** — from a cited doc/paper/benchmark (URL + date).
- **INFERRED** — reasoned from documented facts + engineering judgement; not measured.
- **UNKNOWN** — needs a spike.

---

## 1. Live transcription (RP-03) — realistic capability

### 1.1 What actually works

- Converting reasonably clear, single-speaker, close-mic preaching into a running transcript, **with a 1–5 second lag** and some word churn as interim text is revised. *(INFERRED / Med.)*
- Benchmark WER for the best models is **~2–5% on clean audio** (Whisper large-v3 ~2.1–2.7% test-clean; top cloud ~5–9% on independent tests). *(DOCUMENTED — SayToWords, Hamming via Coval/FutureAGI, 2026-07-23.)*

### 1.2 Expected accuracy in a real church room (be honest)

Benchmark WER is a **floor, not an expectation.** Real-room WER is materially higher because of:

- **Reverberation / room acoustics** and **PA bleed** (the app may hear the loudspeakers, not just the preacher).
- **Accents / non-native English** — WER rises significantly for accented and code-switched speech, and decoder language priors introduce bias. *(DOCUMENTED — arxiv.org/pdf/2604.21276, 2026-07-23, Med.)*
- **Congregational noise, "Amens," music, and pauses.**
- **Domain vocabulary** — archaic/biblical terms, transliterated names (Habakkuk, Nebuchadnezzar), and denomination-specific phrasing are under-represented in training data.

**Honest working estimate:** expect real-room WER **noticeably worse than benchmark** — plausibly **high-single-digit to high-teens %** depending on mic quality, room, and accent, with worse tails on names and quotations. This is **INFERRED / Med-Low** and is exactly what an in-house spike must measure (see UNKNOWNs). It is good enough for *gist/notes* and *reference detection triggering*, **not** good enough to project verbatim as authoritative on-screen text without review.

### 1.3 Failure modes (must design around these)

1. **Hallucination on silence / music / noise.** Whisper fabricates coherent but false text on non-speech, and falls into **repetition loops** on fragmented or heavily-noised audio; risk scales with the share of non-vocal audio. *(DOCUMENTED — arxiv.org/pdf/2501.11378, arxiv.org/pdf/2505.12969, montrealethics.ai, 2026-07-23, High.)* Worship has lots of music and pauses — this is a **first-order risk.** **Mitigation:** mandatory VAD gating before the recognizer; drop/blank low-confidence non-speech segments; never display unverified text during instrumental/silent stretches.
2. **Chunk-boundary churn.** Whisper isn't natively streaming; sliding-window chunking causes interim words to change as context arrives. *(INFERRED / High.)* **Mitigation:** show interim text in a visually distinct "provisional" style; only commit on final.
3. **Real-time shortfall on weak hardware.** FP16 large-v3 **cannot** reach real-time on CPU even at 16 threads; INT4 gets there from 8 threads. *(DOCUMENTED — SayToWords, 2026-07-23, High.)* **Mitigation:** hardware probe → model auto-select → warn if the machine can't keep up.
4. **Cloud outage / dead internet** kills cloud STT mid-service. *(INFERRED / High.)* **Mitigation:** offline default + auto-fallback.

### 1.4 Latency

- **Interim (partial) results:** cloud streaming ~150–520 ms P50 (Deepgram/AssemblyAI); local Whisper chunking ~1–5 s depending on window. *(DOCUMENTED cloud / INFERRED local, 2026-07-23.)*
- **Final (committed) results:** add end-of-utterance detection + a chunk of context; typically 1–3 s after speech ends locally.
- **Implication:** on-screen text always lags the spoken word; design for it (don't promise "instant").

### 1.5 Operator responsibilities (transcription)

- Choose/verify the input mic and monitor a live audio-level meter.
- Watch for and correct/blank hallucinated or garbled output before it's shown to the congregation, if verbatim display is enabled.
- Decide offline vs cloud (and accept consent/connectivity trade-offs).

### 1.6 Recommended default mode (transcription)

- **Offline, VAD-gated, hardware-auto-selected Whisper**, interim text shown as provisional.
- **Verbatim on-screen display OFF by default** — transcription primarily *feeds* scripture detection and notes; showing raw ASR to a congregation invites embarrassing errors. Verbatim display is an advanced opt-in.

---

## 2. Automatic scripture detection (RP-04) — realistic capability

The goal: when the preacher **says** a scripture (either by explicit reference — "turn to John chapter 3 verse 16" — or by **quoting/paraphrasing** a passage), detect it and offer the verse for display.

### 2.1 Recommended staged pipeline (and honest per-stage reality)

| Stage | What it does | Realistic behaviour | Class / Conf |
|---|---|---|---|
| **1. Spoken-reference parsing (deterministic)** | Regex/grammar over the transcript for spoken references: "John three sixteen", "first Corinthians thirteen", "Psalm twenty-three". Includes spoken-number normalization and book-name/abbreviation/alias maps. | **Highest-precision path.** When the preacher explicitly names a reference *and ASR heard it correctly*, this is reliable. Fails when ASR mangles the book name or numbers, or when references are colloquial ("the love chapter"). Mature open grammars exist (Bible-Passage-Reference-Parser / BCV, MIT) designed to handle typos & ambiguity — but built for **text**, so ASR errors upstream are the limiter. | DOCUMENTED (parser) / INFERRED (end-to-end) / Med |
| **2. Normalized exact match** | Canonicalize the parsed reference and look it up in the local Bible index (per translation). | Deterministic once the reference is parsed; the easy part. Ambiguity: which translation? verse ranges? | INFERRED / High |
| **3. Fuzzy match** | For *quoted* text, string-similarity (Levenshtein/Jaccard/Smith-Waterman) of a sliding transcript window against verse text. | Works for near-verbatim quotes in a known translation. Degrades fast with paraphrase, translation mismatch, and ASR errors; **allusions share only ~6% of word forms / ~12% lemmata with their target**, so pure fuzzy matching misses paraphrase. | DOCUMENTED (allusion stats, arXiv 1905.02973) / High |
| **4. Semantic retrieval (embeddings + vector search)** | Embed the transcript window; nearest-neighbour against pre-embedded verses to catch paraphrase/allusion. | Recovers paraphrases fuzzy match misses, but **raises false positives** — many verses are semantically close; sermons discuss themes without quoting. Must be confidence-gated, not auto-fired. | INFERRED / Med |
| **5. Confidence scoring** | Combine signals (explicit-ref bonus, string similarity, embedding distance, ASR confidence, translation match) into one score. | Essential. Explicit parsed references = high confidence; semantic-only = low. Single most important component for keeping false positives out of the operator's face. | INFERRED / Med |
| **6. Duplicate / re-fire suppression** | Debounce repeats of the same reference within a window; suppress the passage currently on screen. | Straightforward and high-value — preachers repeat references many times. | INFERRED / High |
| **7. Operator approval** | Surface top candidate(s) as a one-tap suggestion; operator confirms before display. | **The safety net that makes the feature shippable.** Turns "AI guessed wrong on screen" into "operator ignored a suggestion." | INFERRED / High |

### 2.2 Honest accuracy expectation

There is **no published benchmark** for this exact end-to-end task (live sermon audio → detected scripture) that we can cite, so any single accuracy number would be fabricated. Instead, a candid decomposition:

- **Explicit spoken references, clean audio:** the reliable case. When the preacher plainly states book+chapter+verse and ASR transcribes it correctly, detection is dependable. Main losses come from ASR mis-hearing numbers/book names, not from the parser. **INFERRED / Med.**
- **Verbatim quotes in the configured translation:** moderately reliable via fuzzy match. **INFERRED / Med-Low.**
- **Paraphrases / allusions / cross-translation quotes:** **unreliable** as an auto-display source; semantic retrieval will surface candidates but with meaningful false-positive rates. Best treated as *suggestions*, never auto-fired. **DOCUMENTED basis (low lexical overlap) + INFERRED / Med.**

**We explicitly do NOT claim high end-to-end accuracy.** The honest framing for stakeholders: *"reliable as an assistant for explicit references, a helpful-but-fallible suggester for quotes, and not a source of truth for paraphrase."*

### 2.3 False-positive vs false-negative behaviour

- **False positives** (suggesting/displaying a verse that wasn't referenced) are the more damaging error in a live worship setting — wrong scripture on screen is publicly embarrassing and can look doctrinally careless. **Design bias: tune for precision over recall; require operator confirmation.**
- **False negatives** (missing a reference) are lower-cost — the operator can still pull it manually, exactly as they do today. Missing a detection is "no worse than the status quo."

### 2.4 Accent, noisy-room, and language limits

- Detection quality is **capped by upstream ASR quality.** Accented speech, PA bleed, and congregational noise raise WER, which propagates directly into missed/mis-parsed references. *(DOCUMENTED ASR-bias basis + INFERRED / Med.)*
- Number and proper-noun errors are especially damaging because references *are* numbers and names.
- Non-English / multilingual services and non-Western pronunciations of book names are a known weak spot and need per-language lexicons.

### 2.5 Latency

- End-to-end = ASR latency (1–5 s local interim) + windowed matching (sub-second) + operator confirmation (human). Practically, a suggestion can appear **a few seconds after** the reference is spoken — acceptable for an operator-in-the-loop flow, marginal for fully-automatic display. *(INFERRED / Med.)*

### 2.6 Operator responsibilities (scripture detection)

- **Confirm or dismiss** each suggested passage before it goes on screen (default flow).
- Select the **active translation(s)** and preferred display version.
- Handle ambiguous references (ranges, "chapter 3" with no verse, disputed versification).
- Retain the manual scripture-search path as the always-available fallback.

### 2.7 Recommended default mode (scripture detection)

- **Operator-confirmation by default.** Detected references appear as a ranked, one-tap **suggestion queue**, not auto-projected.
- **Precision-first thresholds:** only high-confidence explicit references may (optionally, opt-in) auto-stage; everything semantic stays suggestion-only.
- **Auto-display is an advanced, strongly-discouraged opt-in** with a high confidence floor, and even then only for explicit parsed references — never for semantic-only matches.
- Always keep manual search available.

> ⚠️ **Residual wrong-verse risk in the auto-display opt-in (per DISCOVERY-REVIEW C7/M7).** High *parse* confidence ≠ correct reference. Because the parser is text-based and sits downstream of ASR, a mis-heard digit ("3:16" → "3:6") or book name produces a fully-parsed, high-parse-confidence but **wrong** reference — precisely the most publicly damaging error (§2.3). The one mode that removes the operator safety net therefore carries a real wrong-verse failure path. **Requirement for auto-display:** a corroboration gate before anything fires unattended — cross-check the surrounding transcript context and/or the verse text against what was spoken, or require the reference to be repeated; semantic-only matches remain permanently barred from auto-display. Auto-display is framed as strongly discouraged, not a routine setting. The safe posture remains operator-confirmation.

### 2.8 Speaker diarization (per DISCOVERY-REVIEW m5)

- Whisper does **not** diarize natively. Live-room diarization (roving mics, overlapping speech, PA bleed, "Amens") is unreliable, and any speaker-attributed timestamps in transcripts/notes inherit those errors. **INFERRED / Med.**
- Product posture: treat "multiple speakers where practical" as a best-effort, **editable** label — never an authoritative attribution. Surface as a Stage-3 feature-inventory item, not an MVP guarantee.

---

## 2.9 Sermon-note generation (RP-05) — LLM fabrication failure mode (per DISCOVERY-REVIEW C6/M6)

For completeness of the candid assessment, the AI-generated sermon-notes feature (detailed in [PROVIDER-TRADEOFFS.md](PROVIDER-TRADEOFFS.md) §2) has its own first-order risk that must be stated as plainly as ASR hallucination:

- **LLMs fabricate and misattribute.** Note generation can invent supporting scripture references, fabricate "important quotations," imagine illustrations, or attribute the wrong people/books — and this **compounds** on top of a transcript that (§1.2) has materially elevated real-room WER on exactly the tokens notes depend on (names, numbers, quotations). **DOCUMENTED (LLM hallucination is well-established) + INFERRED / High.**
- **Mitigations (required):** notes are always **human-gated, editable, and labelled AI-generated**, and never overwrite the source transcript. Additionally, **any auto-extracted scripture reference in generated notes must be verified against the local Bible index and flagged "unverified" until it matches** before export — an LLM-claimed reference is not trusted on its face.
- **Honest framing for stakeholders:** sermon notes are a **time-saving draft**, not a system of record. Doctrinal/pastoral sensitivity makes review-before-publish mandatory.

## 3. Summary of honest limitations

- Live ASR in a real room is **worse than benchmark WER** and hallucinates on silence/music — never treat raw transcript as authoritative.
- Scripture detection is **reliable for explicit references, fallible for quotes, unreliable for paraphrase** — ship it as an operator-assist, not an autopilot; auto-display carries a residual wrong-verse risk (§2.7) and is strongly discouraged.
- Sermon-note LLMs **fabricate/misattribute** — notes are an editable draft, human-reviewed before publish, with references verified against the local Bible index (§2.9).
- The safest, shippable posture is **offline-first + operator-in-the-loop + precision-over-recall**, which keeps every AI error recoverable before it reaches the congregation.

## 4. Unmeasured items (UNKNOWNs → spikes) (per DISCOVERY-REVIEW m10)

The "(see UNKNOWNs)" cross-references throughout this document resolve here. None of the following has been measured in-house; each needs a spike (engineering spikes are enumerated in [FEASIBILITY.md](FEASIBILITY.md) §10, notably S8):

- Real-room WER by mic type / room acoustics / speaker accent on target church hardware. **UNKNOWN.**
- End-to-end detection rate for **explicit** spoken references (ASR→parse→match), clean and noisy. **UNKNOWN.**
- Semantic-retrieval **false-positive rate** at candidate thresholds on sermon-style speech. **UNKNOWN.**
- Local-model **real-time headroom** (which Whisper size sustains real-time on CPU-only vs GPU/Apple-Silicon church PCs). **UNKNOWN (partly bounded by DOCUMENTED RTF figures in PROVIDER-TRADEOFFS §1.1).**
- Cloud→local STT failover behaviour on hardware that cannot sustain local real-time (see §1.3 note below). **UNKNOWN.**

> **Graceful-degradation note (per DISCOVERY-REVIEW C13/m9):** the "never let a live service go dark" guarantee applies to the **presentation output** (protected by the AI-never-blocks-slides invariant), **not** to transcription itself. On a church PC that cannot sustain real-time local Whisper (e.g. FP16 large-v3, RTF 1.26 CPU-only, §1.3), the cloud→local fallback cannot guarantee seamless local takeover; transcription must **degrade gracefully** — pause, drop to a smaller model, or show a visible "transcription degraded/paused" status — while slide control continues unaffected.

---

## Sources

- [Whisper Large-v3 WER benchmarks (SayToWords)](https://www.saytowords.com/blogs/Whisper-V3-Benchmarks/)
- [Whisper Large-v3 explained & limits (ConvertAudioToText)](https://convertaudiototext.com/blog/whisper-large-v3-explained)
- [Whisper hallucinations from non-speech audio (arXiv 2501.11378)](https://arxiv.org/pdf/2501.11378)
- [Calm-Whisper — reducing non-speech hallucination (arXiv 2505.12969)](https://arxiv.org/pdf/2505.12969)
- [Careless Whisper — hallucination harms (Montreal AI Ethics)](https://montrealethics.ai/careless-whisper-speech-to-text-hallucination-harms/)
- [Do LLM decoders listen fairly? ASR bias benchmark (arXiv 2604.21276)](https://arxiv.org/pdf/2604.21276)
- [Best STT Providers 2026 — independent benchmarks (Coval)](https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose/)
- [STT benchmarks & latency 2026 (FutureAGI)](https://futureagi.com/blog/speech-to-text-apis-in-2026-benchmarks-pricing-developer-s-decision-guide/)
- [Bible-Passage-Reference-Parser / BCV (GitHub)](https://github.com/openbibleinfo/Bible-Passage-Reference-Parser)
- [openbible.info reference parser demo](https://www.openbible.info/labs/reference-parser/)
- [On the Feasibility of Automated Detection of Allusive Text Reuse (arXiv 1905.02973)](https://arxiv.org/pdf/1905.02973)
