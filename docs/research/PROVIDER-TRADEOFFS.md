# SelahCue — Provider Trade-offs (RP-03 / RP-05 / RP-06)

**Research date:** 2026-07-23
**Author role:** AI Engineer + Product Researcher
**Scope:** Transcription (STT), Sermon-notes LLM, Text-to-Speech (TTS)
**Design bias:** Offline-first, opt-in cloud, provider abstraction with fallback.

## Evidence classification legend

Every finding is tagged with one of:

- **OBSERVED** — we ran/measured it ourselves. (None yet — no local benchmarking has been done; see UNKNOWNs.)
- **DOCUMENTED** — stated in a vendor doc, model card, paper, or reputable benchmark, with URL.
- **INFERRED** — reasoned from documented facts + general engineering knowledge; not directly measured.
- **UNKNOWN** — not established; needs a spike.

Confidence = Low / Med / High. **No perfect-accuracy claims are made anywhere in this document.** All accuracy numbers are ranges under stated conditions and degrade in real church rooms (reverb, PA bleed, accents, crosstalk).

> ⚠️ **Caveat on all cited numbers:** Vendor and blog WER/latency figures are measured on clean benchmark corpora (LibriSpeech, FLEURS, curated call audio). A live church with a wall-mounted PA, congregational noise, roving mic, and non-native accents will be materially worse. Treat all cited WER as a *floor*, not an expectation. Independent benchmarks also warn that vendor self-tests are not comparable across providers (Coval, 2026-07-23).

---

## 1. Transcription (RP-03)

### 1.1 Offline / on-device (Whisper family)

| Model | WER (clean English, benchmark) | Speed / Real-time factor | Memory (approx) | Church-PC reality | Offline | Streaming | License | Class / Conf |
|---|---|---|---|---|---|---|---|---|
| whisper tiny / base | High (roughly 2–3× worse than large; usable only for keyword-level) | Fastest; real-time on modest CPU | ~0.2–0.5 GB | Runs real-time CPU-only, but too inaccurate for on-screen scripture text | Yes | Chunked only | MIT | DOCUMENTED / Med |
| whisper small | Moderate | Real-time on decent CPU (INT8) | ~1 GB | Reasonable CPU-only compromise for MVP | Yes | Chunked only | MIT | INFERRED / Med |
| whisper medium | Better | ~Real-time only with GPU or aggressive INT8 CPU | ~2–3 GB | Marginal CPU-only; comfortable on modest GPU | Yes | Chunked only | MIT | INFERRED / Med |
| whisper large-v3 | ~2.1–2.7% (test-clean); ~13% on YouTube-Commons long-form | GPU RTF ~0.15 (55× RT); FP16 CPU **cannot** hit real-time even at 16 threads (RTF 1.26); INT4 CPU real-time from 8 threads (RTF 0.91) | ~5–6 GB (FP16); less quantized | **CPU-only: not real-time.** Needs GPU or heavy quantization | Yes | Chunked only | MIT | DOCUMENTED / High |
| large-v3-turbo | Within ~0.3–0.4 pts of large-v3; 13.40% vs 13.20% long-form | ~129× RT GPU; ~5× faster than v3 on Mac | ~2–4 GB | Best accuracy/speed balance where a GPU/Apple-Silicon exists | Yes | Chunked only | MIT | DOCUMENTED / High |
| distil-large-v3 (faster-distil) | Within ~1 pt of large-v3 on English; distil-large-v2 avg 10.1% | ~6× faster than large-v3; up to 90× RT | ~1.5–3 GB | Strong offline default when a GPU is present | Yes (English-centric) | Chunked only | MIT | DOCUMENTED / High |

**Runtime notes:**
- **whisper.cpp** (MIT) and **faster-whisper / CTranslate2** (MIT) are the two practical engines. faster-whisper is generally faster on x86 with INT8; whisper.cpp is easiest to embed cross-platform and strong on Apple Silicon (Metal). *(DOCUMENTED — github.com/SYSTRAN/faster-whisper; INFERRED for the head-to-head — promptquorum comparison, 2026-07-23, Conf Med.)*
- Whisper is **not natively streaming**. "Live" transcription is faked by sliding-window chunking (e.g. 1–5 s chunks with overlap), which trades latency vs stability and can cause word churn at chunk boundaries. *(INFERRED / High.)*
- **Key failure mode — hallucination on non-speech:** Whisper fabricates coherent text on silence, music, and noise, and produces repetition loops on fragmented/heavily-noised audio; hallucination rate rises with the share of non-vocal audio. Mitigations (VAD gating, Calm-Whisper) reduce but do not eliminate it. *(DOCUMENTED — arxiv.org/pdf/2501.11378, arxiv.org/pdf/2505.12969, montrealethics.ai, 2026-07-23, High.)* **This is a first-order risk for a live worship room with music and pauses.**

### 1.2 Cloud streaming STT

| Provider / model | WER (benchmark) | Streaming latency (P50) | Cost | Streaming | Languages | License / hosting | Class / Conf |
|---|---|---|---|---|---|---|---|
| **Deepgram Nova-3** | ~5.26% (own real-world test); ~9.87% (Hamming independent) | ~516 ms P50 (Hamming) | ~$0.0043/min voice-agent tier | Yes (native, strong endpointing) | Many | Cloud API (also on-prem enterprise) | DOCUMENTED / Med |
| **AssemblyAI Universal-3 Pro Streaming** | ~8.14% (Hamming); vendor ~150 ms P50 post-VAD | ~307 ms P50 (Hamming) / ~150 ms (vendor) | ~$0.45/hr (~$0.0075/min); ~65% session overhead on short sessions | Yes | Many | Cloud API | DOCUMENTED / Med |
| **OpenAI gpt-4o-transcribe / mini** | Within 1–2 pts of top tier on LibriSpeech/FLEURS | Streaming deltas | ~$0.003 (mini) – $0.006/min; realtime-whisper ~$0.017/min | Yes (gpt-4o-transcribe, realtime) | Many | Cloud API | DOCUMENTED / Med |
| **Google Cloud STT** | Competitive | Streaming | ~$0.024/min standard; ~$0.036 enhanced | Yes | Very many | Cloud API | DOCUMENTED / Med |
| **Azure Speech (real-time)** | Competitive | Streaming | ~$1/audio-hr (~$0.017/min) real-time; $0.36/hr fast; $0.18/hr batch | Yes | Very many; custom lexicons | Cloud API (+ containers) | DOCUMENTED / Med |
| **ElevenLabs Scribe v2 / MS MAI-Transcribe-1** | Within 1–2 pts of top tier | — | — | Varies | Many | Cloud API | DOCUMENTED / Low |

**Cloud notes:**
- Top providers cluster within ~1–2 WER points on clean benchmarks; the real differentiators are streaming latency, end-of-turn detection, multilingual depth, and cost at scale. *(DOCUMENTED — coval.ai, futureagi, 2026-07-23, Med.)*
- Cloud adds **network dependency** (dead internet = dead feature during a live service) and **data-egress/consent** concerns — sermon audio leaves the building. This directly conflicts with offline-first and must be opt-in with clear consent. *(INFERRED / High.)*

### 1.3 Transcription recommendation (MVP)

- **MVP default: offline `whisper small` or `distil-large-v3` via faster-whisper/whisper.cpp**, selected by a hardware probe at first run:
  - CPU-only church PC → `small` (INT8) with VAD gating.
  - Apple Silicon / modest GPU → `distil-large-v3` or `large-v3-turbo`.
- **VAD gating is mandatory** in front of Whisper to suppress silence/music hallucination.
- **Opt-in cloud tier** (Deepgram or AssemblyAI streaming) for churches that want lowest latency + best accuracy and accept data egress + connectivity risk. Deepgram favoured for latency/endpointing; AssemblyAI for accuracy.
- Ship a hardware-warning if the selected model can't sustain real-time on the detected machine.

---

## 2. Sermon-notes LLM (RP-05)

| Option | Quality for summarization | Latency | Cost | Data retention / consent | License / hosting | Class / Conf |
|---|---|---|---|---|---|---|
| **Local 7B–8B (llama.cpp / Ollama)** | "Handles summarization and drafting well" for a 7B on a modern laptop; weaker on long-context reasoning & structure | Much slower than cloud on modest HW (orders of magnitude on big tasks); acceptable for short post-service summaries | $0 marginal; one-time HW | Fully local — no data leaves device | Model-dependent (Llama community, Apache/MIT variants) | DOCUMENTED / Med |
| **Claude Haiku 4.5** | Strong at classification/extraction/summarization | Fast cloud | $1 in / $5 out per 1M tok; batch −50%, cache −90% | Cloud; needs consent + retention policy | Cloud API | DOCUMENTED / High |
| **Claude Sonnet 4.6** | Higher-quality structured notes/reasoning | Fast cloud | $3 in / $15 out per 1M tok | Cloud | Cloud API | DOCUMENTED / High |
| **OpenAI GPT-4o-mini** | Good for simple summarization | Fast cloud | $0.15 in / $0.60 out per 1M tok (cheapest tier) | Cloud | Cloud API | DOCUMENTED / High |
| **OpenAI GPT-4o** | Strong general | Fast cloud | $2.50 in / $10 out per 1M tok | Cloud | Cloud API | DOCUMENTED / High |

**Notes:**
- Cloud frontier models remain materially better for complex reasoning/structure; local 7B is adequate for "tidy up this transcript into bullet notes." *(DOCUMENTED — daily.dev, claude5.com, 2026-07-23, Med.)*
- Sermon-notes is **not latency-critical** (runs post-segment or post-service), which makes cloud consent-gating easy and local generation tolerable even if slow.
- **Consent/retention is the dominant axis here**, not raw quality — sermon content can be doctrinally/pastorally sensitive.

### 2.1 LLM recommendation (MVP)
- **Default: local 7B–8B via bundled llama.cpp/Ollama-class runtime** for "notes from transcript," offline, no data egress.
- **Opt-in cloud tier via provider abstraction:** default cloud = **Claude Haiku 4.5** (cheap, strong at summarization) with **Sonnet 4.6** as a "high-quality" toggle; **GPT-4o-mini** as an alternate cheap provider. Cloud calls require explicit per-church consent and a stated retention policy.

---

## 3. Text-to-Speech (RP-06)

| Option | Quality | First-token latency | Cost | Offline | Per-platform availability | License / hosting | Class / Conf |
|---|---|---|---|---|---|---|---|
| **OS voices** — macOS AVSpeechSynthesizer, Windows SAPI/WinRT, Linux espeak-ng | Robotic→decent (OS-dependent); modern OS neural voices are acceptable | Very low (local) | $0 | Yes | Built into each OS; voice set differs per machine/install | OS-bundled | INFERRED / Med |
| **Piper** (local neural) | Good, natural; 30+ languages, 100+ voices | Very low (on-device) | $0 | Yes | Cross-platform (bundled models) | MIT | DOCUMENTED / High |
| **Kokoro-82M / other on-device neural** | Good | Very low (on-device, e.g. Orca ~128 ms FTTS) | $0 | Yes | Cross-platform | Open (model-dependent) | DOCUMENTED / Med |
| **ElevenLabs** | Top-tier naturalness, cloning | ~335 ms streaming FTTS (higher end-to-end) | Per-char, premium | No | Cloud | Cloud API | DOCUMENTED / Med |
| **Azure TTS** | High, custom lexicons/SSML | ~1,580 ms standard | ~$16/1M chars (commit tiers from $7.50) | No (containers option) | Cloud | Cloud API | DOCUMENTED / Med |
| **Amazon Polly** | High | ~1,540 ms standard | Per-char | No | Cloud | Cloud API | DOCUMENTED / Med |
| **Google Cloud TTS** | High | Streaming | Per-char, free tier | No | Cloud | Cloud API | DOCUMENTED / Med |

**Notes:**
- On-device engines are **2.6–11× lower first-token latency** than cloud and work with no network — decisive for live-service use. *(DOCUMENTED — picovoice.ai on-device TTS benchmark, 2026-07-23, High.)*
- **Pronunciation dictionaries** matter for scripture/names (e.g. "Habakkuk", "Melchizedek"). Azure/Polly/ElevenLabs support SSML lexicons; Piper needs a phoneme/lexicon layer; OS voices vary. SelahCue should own a **custom pronunciation lexicon** regardless of engine. *(INFERRED / Med.)*
- **Audio routing / feedback safety:** TTS output played into a room with open mics risks feedback loops and re-transcription of the app's own voice. Requires an output-device selection + a "mute STT while TTS speaks" (half-duplex) guard. *(INFERRED / High — this is an architectural requirement, not a provider choice.)*

### 3.1 TTS recommendation
- **TTS is NOT MVP — defer to a later release.** It is the lowest-value of the four features for a presentation app (the congregation reads the screen), and it carries the highest live-room risk (feedback, mic bleed, routing). Ship transcription + scripture detection + notes first.
- **When built: default to on-device (Piper, cross-platform) or OS voices**, cloud (Azure for lexicon control, ElevenLabs for quality) as opt-in for pre-rendered (non-live) audio only.

---

## 4. Recommended provider-abstraction architecture

A single internal interface per capability, with a local default implementation and pluggable cloud adapters:

```
STTProvider        { startStream(), pushAudio(), onInterim(), onFinal(), capabilities }
NoteGenProvider    { summarize(transcript, opts), capabilities }
TTSProvider        { synthesize(text, voice, opts) -> audioStream, capabilities }
```

Principles:
1. **Offline-first defaults.** Local implementation is always present and is the shipped default; the app is fully functional with the network unplugged.
2. **Opt-in cloud, consent-gated.** Cloud adapters are disabled until a church enables them and accepts a per-capability consent + data-retention notice. Audio/transcript/sermon text is sensitive.
3. **Capability negotiation, not assumption.** Providers advertise `{streaming, languages, maxLatency, offline}`; the app selects based on detected hardware + operator preference.
4. **Graceful fallback.** If a cloud provider errors or the network drops mid-service, auto-fall back to the local provider without interrupting the live output. Never let a live service go dark because an API 500'd.
5. **Config-driven credentials.** No hard-coded keys; per-church keys stored in OS keychain/credential store.
6. **Cost/latency guardrails.** Cloud usage metered and surfaced to the operator; batch/cache used for LLM notes.

---

## 5. Recommended MVP defaults (summary)

| Capability | MVP default (offline-first) | Opt-in cloud | Ship in MVP? |
|---|---|---|---|
| Transcription (RP-03) | faster-whisper/whisper.cpp; `small` (CPU) or `distil-large-v3`/`turbo` (GPU/Apple Silicon), VAD-gated | Deepgram (latency) or AssemblyAI (accuracy) streaming | **Yes** |
| Scripture detection (RP-04) | Local staged pipeline (parse → exact → fuzzy → embeddings), operator-confirmation default | — (runs on local transcript) | **Yes** (with operator confirmation) |
| Sermon notes (RP-05) | Local 7B–8B (llama.cpp/Ollama) | Claude Haiku 4.5 (default) / Sonnet 4.6 (HQ) / GPT-4o-mini | **Yes** (offline default) |
| TTS (RP-06) | Piper / OS voices | Azure / ElevenLabs (pre-render only) | **No — defer** |

---

## Sources

- [SYSTRAN/faster-whisper (GitHub)](https://github.com/SYSTRAN/faster-whisper/issues/1030)
- [How Accurate Is Whisper — WER by language (NovaScribe)](https://novascribe.ai/how-accurate-is-whisper)
- [Faster-Whisper GPU production guide (Spheron)](https://www.spheron.network/blog/faster-whisper-gpu-cloud-production-deployment-guide/)
- [Whisper V3 Benchmarks (SayToWords)](https://www.saytowords.com/blogs/Whisper-V3-Benchmarks/)
- [Distil-Whisper paper (arXiv 2311.00430)](https://arxiv.org/pdf/2311.00430)
- [Whisper.cpp vs faster-whisper 2026 (PromptQuorum)](https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026)
- [Whisper Large V3 Turbo benchmark (Whisper Notes)](https://whispernotes.app/blog/introducing-whisper-large-v3-turbo)
- [Whisper Large-v3 explained & limits (ConvertAudioToText)](https://convertaudiototext.com/blog/whisper-large-v3-explained)
- [Deepgram vs Google vs AssemblyAI (Deepgram)](https://deepgram.com/learn/deepgram-vs-google-vs-assemblyai)
- [Best STT APIs 2026 benchmarks (FutureAGI)](https://futureagi.com/blog/speech-to-text-apis-in-2026-benchmarks-pricing-developer-s-decision-guide/)
- [Best STT Providers 2026 — independent benchmarks (Coval)](https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose/)
- [OpenAI transcription pricing (CostGoat)](https://costgoat.com/pricing/openai-transcription)
- [Deepgram vs Google vs Azure STT (Deepgram)](https://deepgram.com/learn/deepgram-vs-google-vs-azure-speech-to-text)
- [Whisper hallucinations induced by non-speech (arXiv 2501.11378)](https://arxiv.org/pdf/2501.11378)
- [Calm-Whisper (arXiv 2505.12969)](https://arxiv.org/pdf/2505.12969)
- [Careless Whisper — hallucination harms (Montreal AI Ethics)](https://montrealethics.ai/careless-whisper-speech-to-text-hallucination-harms/)
- [Anthropic Claude API pricing 2026 (CloudZero)](https://www.cloudzero.com/blog/claude-api-pricing/)
- [Claude API pricing — Opus/Sonnet/Haiku (MetaCTO)](https://www.metacto.com/blogs/anthropic-api-pricing-a-full-breakdown-of-costs-and-integration)
- [Running LLMs locally 2026 (daily.dev)](https://daily.dev/blog/running-llms-locally-ollama-llama-cpp-self-hosted-ai-developers/)
- [Local LLMs for coding — what a laptop can/can't do (Vibehackers)](https://vibehackers.io/blog/local-llm-coding-2026)
- [On-device TTS benchmark 2026 (Picovoice)](https://picovoice.ai/blog/on-device-tts/)
- [Best TTS APIs 2026 (Gladia)](https://www.gladia.io/blog/best-tts-apis-for-developers-in-2026-top-7-text-to-speech-services)
- [Best TTS Providers 2026 — why vendor benchmarks lie (Coval)](https://www.coval.ai/blog/best-text-to-speech-providers-in-2026-how-to-choose-(and-why-vendor-benchmarks-lie)/)
- [Azure TTS pricing 2026 (TextToLab)](https://texttolab.com/blog/azure-text-to-speech-pricing)
- [Bible-Passage-Reference-Parser (GitHub)](https://github.com/openbibleinfo/Bible-Passage-Reference-Parser)
