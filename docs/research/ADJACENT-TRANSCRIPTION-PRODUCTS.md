# SelahCue — Adjacent Transcription / Sermon-Note Product Study (RP-03 gap closure)

**Document type:** Product/workflow-level study of dedicated transcription & sermon-note applications
**Closes:** Stage-2 gate condition **C1 (finding M1)** — the un-delivered adjacent-product study
**Author role:** Product Researcher
**Research date / access date:** 2026-07-23
**Research tools:** WebSearch + WebFetch (Chrome MCP not available — RISK-007). No paid trials purchased; no product was run/operated.
**Scope:** Workflow layer only — how these products handle transcript editing, speaker labels, chapters, bookmarks/highlights, timestamps, sermon-note/summary generation, and export/publish. **NOT** the underlying STT/LLM tech (that layer is covered by PROVIDER-TRADEOFFS.md).
**Products:** Descript (post-production transcript editor), Otter.ai (live meeting transcription/notes), CaptionKit (church-oriented live captioning).

> **No proprietary UI, branding, code, or assets are copied.** This study extracts *transferable workflow patterns*, not designs.

---

## Evidence classification legend (aligned to gate condition C3)

- **OBSERVED** — I directly viewed the feature *stated/shown on the vendor's own live page or help doc I fetched this session* (first-hand page observation). **It does NOT mean I observed the product's runtime behaviour** — no product was operated, so no performance, accuracy, latency, or real-room behaviour is OBSERVED here.
- **DOCUMENTED** — stated in official documentation/help centre or a reputable secondary source, read via search snippet or third-party guide (not fetched first-hand this session), with URL.
- **INFERRED** — reasoned from documented facts + engineering/domain knowledge; not directly stated.
- **UNKNOWN** — not established from public sources (paywalled internals, proprietary algorithms, unverifiable real-room behaviour).

> ⚠️ **Caveat on every accuracy/latency/"reads cleanly" claim below:** all such figures are **vendor-claimed** on marketing pages and were measured (if at all) on clean audio, not a reverberant church room with a wall-mounted PA, congregational noise, roving mics, and non-native accents. Per the package convention (M5), a vendor performance number is at best "DOCUMENTED that the *claim exists*," never confidence the claim is *true*. Treat all as **vendor-claimed / uncorroborated / Low**.

---

## 1. Per-product workflow findings

### 1.1 Descript — transcript-driven post-production editor

Descript's signature is a **word-synchronised, "edit-like-a-document" model**: the transcript *is* the editing surface, and every word is bound to its media timecode.

| # | Finding | Class / Conf | Source (access 2026-07-23) |
|---|---|---|---|
| D1 | **Transcript-driven editing** — editing works at the text level, not the timeline; deleting/rearranging text deletes/rearranges the corresponding audio/video. Transcription runs automatically on import/record. | OBSERVED / Med | descript.com/tools/audio-text |
| D2 | **Non-destructive "Correct" layer** — highlight text and press **`C`** to "correct the script **without changing the audio**." Fixing a misspelled name changes the displayed text, not the media. This is a correction overlay separate from the recognised tokens. | OBSERVED / Med | descript.com/tools/audio-text; help.descript.com "Edit like a doc" (403 — via search) |
| D3 | **Speaker detection + editable labels** — "Speaker Detective" auto-identifies and labels each speaker; labels are editable before export. | DOCUMENTED / Med | descript.com/tools/audio-text; languagesunlimited.com guide |
| D4 | **Filler-word removal** — "Remove Filler Words" flags and strips "uh/um/like" in bulk. | OBSERVED / Med | descript.com/tools/audio-text |
| D5 | **Chapters / markers** — "Chapter Generator" auto-creates chapters with timestamps for navigation; editable before export. | OBSERVED / Med | descript.com/tools/podcast-show-notes-generator |
| D6 | **Timestamps** — every word carries a timecode; searchable transcript with AI-generated markers/highlights; timecodes editable. | DOCUMENTED / Med | work-management.org review; descript.com/tools |
| D7 | **AI sermon-note analogue ("Underlord")** — from the transcript, generates **show notes, summaries, key takeaways, titles, YouTube descriptions, chapter markers, timestamps**; requires the transcript first; output is **editable/customisable**. Driven by plain-language prompts ("Podcast Show Notes"). | OBSERVED / Med | descript.com/tools/podcast-show-notes-generator; descript.com/underlord (via search) |
| D8 | **Export/publish formats** — TXT, RTF, Markdown (.md), HTML, Word (.docx), **SRT**, **VTT**, shareable web link, embedded player. .docx preserves speaker labels as headings. | OBSERVED / High | descript.com/tools/audio-text; languagesunlimited.com |
| D9 | Processing is **cloud** (transcription on import via Descript's servers); no documented fully-offline transcription mode. | INFERRED / Med | Product is web/cloud SaaS; no offline claim found |
| D10 | Underlying ASR engine, diarization algorithm, and real-room accuracy/error rates. | UNKNOWN | Proprietary; not disclosed |

### 1.2 Otter.ai — live meeting transcription + auto-notes

Otter's signature is **live transcription with real-time highlighting** plus **auto-generated structured notes** (Summary / Action Items / Outline) and **voiceprint-based speaker ID**.

| # | Finding | Class / Conf | Source (access 2026-07-23) |
|---|---|---|---|
| O1 | **Live transcription** with speakers identified and "key moments" marked as they happen; vendor claims **98% accuracy** (**vendor-claimed / Low**). | OBSERVED (claim) / Low | otter.ai/ |
| O2 | **Transcript correction** — edit text to fix errors directly in the Transcript tab; corrections and speaker tags also *train* recognition. | DOCUMENTED / Med | help.otter.ai (via search); enterprisetimes.co.uk guide |
| O3 | **Speaker identification + voiceprint training** — "My Voiceprint" enrols your voice; tag a speaker (click circle next to text) to teach Otter; reuses known/shared workspace speakers to auto-ID in later conversations. | DOCUMENTED / Med | help.otter.ai "Speaker Identification Overview" (via search) |
| O4 | **Live highlights** — participants highlight important points during the session; highlights persist into the summary and can be included in export. | OBSERVED / Med | otter.ai/; help.otter.ai (via search) |
| O5 | **Auto-Outline / auto-chapters** — long conversations are broken into titled **chapters** you can scan to jump to sections; Summary + Action Items + Outline are all auto-generated. | DOCUMENTED / Med | otter.ai/blog/ai-to-summarize-transcripts; help center (via search) |
| O6 | **Takeaways / Summary / Action Items** — post-session summary organised by topic with bullet points and auto-extracted action items; "Otter AI Chat" lets you ask questions of the transcript. | OBSERVED / Med | otter.ai/; dreamhost.com review |
| O7 | **Timestamps** — per-line timestamps; click to seek; included optionally in export. | DOCUMENTED / Med | help.otter.ai "Export conversations" (via search) |
| O8 | **Export/publish formats** — TXT, **DOCX** (rich formatting, highlights, photos), **PDF**, **SRT** (with optional automatic line breaks, Premium/Teams-gated); export options let you include/exclude speaker names, timestamps, highlights. | OBSERVED / High | otter.ai/blog/word-docx-export-auto-cut-srt |
| O9 | Otter is **cloud-only** (accounts, workspace, live-agent join); no offline/on-device mode. | INFERRED / High | Cloud SaaS architecture; no offline claim found |
| O10 | Underlying ASR/diarization models, real-room accuracy, and live-caption latency. | UNKNOWN | Proprietary; not disclosed |

### 1.3 CaptionKit — church-oriented live captioning (the church tool)

Chosen as the church-oriented live-captioning tool. Purpose-built for services: real-time captions to screens **and** attendee phones, translation, and presentation-software integration.

| # | Finding | Class / Conf | Source (access 2026-07-23) |
|---|---|---|---|
| C1 | **Real-time captions** delivered "straight to attendees' phones or up on screen." | OBSERVED / Med | captionkit.com |
| C2 | **Display modes** — (a) **lower-third** scrolling captions (adjustable lines/font), (b) **full-screen** scrolling (dedicated accessibility monitors), (c) **styled** non-scrolling custom layouts. | OBSERVED / High | captionkit.com |
| C3 | **Per-device access** — attendees join via **caption link or QR code**, in browser or free iOS/Android apps (also Apple TV). Each person can pick their own language. | OBSERVED / High | captionkit.com; faith.tools listing |
| C4 | **Presentation integrations** — ProPresenter, OBS, vMix, FreeShow, Worship Extreme; automation via cURL, **Bitfocus Companion**, ProPresenter (API). | OBSERVED / High | captionkit.com; faith.tools |
| C5 | **Translation** — understands sermons in **65+ languages**, translates into **85+**; simultaneous bilingual (e.g. English + Spanish) mode; audio translation + TTS to Bluetooth hearing aids via app. | OBSERVED / Med | captionkit.com |
| C6 | **Custom vocabulary — "Keywords"** — boost recognition of names/locations, block unwanted words, filter profanity. (Direct analogue of a per-church glossary.) | OBSERVED / High | captionkit.com |
| C7 | **Post-service** — **downloadable sermon transcripts** + **History & analytics** (past sessions, view metrics). | OBSERVED / Med | captionkit.com; faith.tools |
| C8 | **No sermon-summary / AI-notes feature** — the public site describes transcripts + analytics only; no auto-summary/notes/outline mentioned. | OBSERVED (absence) / Med | captionkit.com (feature not present) |
| C9 | **Pricing** — freemium; ~4 free trial hours then from **$16/mo**, no credit card, no lock-in. | OBSERVED / Med | captionkit.com |
| C10 | **Cloud-based** (web dashboard, cloud STT/translation); no offline mode documented. | INFERRED / Med | Web-dashboard SaaS; no offline claim found |
| C11 | Downloaded-transcript **file format(s)** (txt/docx/srt?), whether they carry **speaker labels or timestamps**, and live-caption **latency** in a real room. | UNKNOWN | Not stated on public pages; behind sign-up |
| C12 | Underlying STT/translation engine and correction-during-live capability. | UNKNOWN | Proprietary; not disclosed |

---

## 2. Capability comparison (transcript-editing / diarization / chapters / export)

| Capability | **Descript** | **Otter.ai** | **CaptionKit** |
|---|---|---|---|
| Primary use | Post-production edit | Live meetings + notes | **Live church captioning** |
| Transcript-driven media edit | **Yes** — text edit = media edit (D1) | No (transcript is read/annotate) | No (live display) |
| Correction UX | Press `C` → correct text **without** changing audio (D2) | Edit text in Transcript tab; also trains ID (O2) | Live "Keywords" boosting; no per-word live edit found (C6/C11) |
| Non-destructive correction layer | **Yes** (correction ≠ media change, D2) | Edits mutate transcript; version detail UNKNOWN | UNKNOWN |
| Speaker labels / diarization | Auto ("Speaker Detective"), editable (D3) | Auto + **voiceprint training**, editable, non-authoritative (O3) | Not surfaced as a user feature (UNKNOWN, C11) |
| Chapters / markers | **Chapter Generator**, auto + editable, timestamped (D5) | **Auto-Outline** titled chapters (O5) | None (live scroll only) |
| Bookmarks / highlights | AI highlights + searchable markers (D6) | **Live highlights** persist to summary/export (O4) | None documented |
| Timestamps | Per-word timecode, click-to-seek (D6) | Per-line, click-to-seek (O7) | Live only; in download UNKNOWN (C11) |
| Sermon-note / summary gen | **Underlord**: show notes, summary, takeaways, titles, chapters (D7) | **Takeaways**: summary + action items + outline + AI Chat (O6) | **None** (C8) |
| Export: TXT | Yes (D8) | Yes (O8) | Transcript download, format UNKNOWN (C11) |
| Export: MD | **Yes** (D8) | No | UNKNOWN |
| Export: DOCX | Yes, speaker labels as headings (D8) | Yes, rich + highlights (O8) | UNKNOWN |
| Export: PDF | Not found (RTF/HTML instead) | **Yes** (O8) | UNKNOWN |
| Export: SRT | **Yes** (D8) | **Yes**, optional line-breaks (O8) | N/A (live overlay, not file) |
| Export: VTT | **Yes** (D8) | Not found | N/A |
| Export: JSON (token-level) | **Not found** | **Not found** | **Not found** |
| Offline / on-device | No (cloud, D9) | No (cloud-only, O9) | No (cloud, C10) |
| Live vs post-service | Post | Live + post | **Live** (+ transcript download) |

**Cross-cutting observations:**
- **No product exposes a JSON / token-level timestamped export** — a genuine gap SelahCue can turn into a differentiator (programmatic re-cueing, scripture-cue correlation).
- **All three are cloud SaaS** — none offers an offline/on-device mode. SelahCue's offline-first default is a *deliberate difference*, not a copy.
- **Only Otter and Descript generate structured notes**; the church tool (CaptionKit) does **not** — confirming sermon-intelligence (Phase 5) is an open lane in the church-captioning niche specifically.

---

## 3. Transferable workflow patterns for SelahCue

### 3.1 Phase 3 — Transcription (editing / diarization / chapters / export)

**Adopt:**

1. **Word-synced transcript ↔ media, click-to-seek (from Descript D1/D6).** Store a per-token timestamp so the post-service editor lets an operator click any word to seek the recorded audio. This is the backbone of every correction, highlight, and clip workflow. *(Transferable / High.)*
2. **Non-destructive correction layer (from Descript D2 — press `C` corrects text, not audio).** SelahCue keeps the **raw ASR token stream immutable** and stores corrections as a separate overlay. This is not just UX polish — it is required by gate condition **C6**: the live scripture-detection path reads raw tokens, corrections must be auditable/undoable, and notes must "never overwrite the source transcript." Descript proves the two-layer model is usable at scale. *(Transferable / High.)*
3. **Custom vocabulary / keyword boosting (from CaptionKit C6 "Keywords", Descript glossary).** A **per-church glossary** — pastor/staff names, place names, ministry terms, biblical proper nouns ("Habakkuk", "Melchizedek") — directly attacks the proper-noun/number errors the CAPABILITY-ASSESSMENT flags as the *most publicly damaging* class of error. Doubles as the pronunciation-lexicon source for RP-06 TTS. *(Transferable / High.)*
4. **Editable, explicitly non-authoritative speaker labels (from Otter O3 + Descript D3).** Offer auto-diarization (Preacher / Worship Leader / Reader) with **editable labels** and *optional* voiceprint enrolment, but treat labels as convenience — matching review finding **m5 / condition C11** ("multiple speakers where practical / labels editable, not authoritative"). Never block transcription or notes on diarization confidence. *(Transferable / High.)*
5. **Broad, caption-first export set (from Descript D8 + Otter O8).** Phase 3 should ship **SRT + VTT** (captions), **TXT + MD** (plain/notes), and **DOCX/PDF** (shareable), with include/exclude toggles for speaker names, timestamps, and highlights (Otter's export-options model). **Add a JSON token-level export** none of the three offers — the differentiator. *(Transferable / High; JSON = differentiate.)*
6. **Live caption as an output type with per-device access (from CaptionKit C2/C3).** SelahCue already owns multi-output + lower-thirds; adding **live captions as a selectable output** (lower-third / full-screen / styled) plus an optional **caption link/QR to attendee phones** closes the accessibility gap (review m4) using the church-proven pattern. *(Transferable / Med.)*
7. **Presentation-stack automation hooks (from CaptionKit C4).** CaptionKit integrates with OBS/ProPresenter and **Bitfocus Companion** — the same ecosystem interop SelahCue's COMPETITOR-MATRIX already calls table-stakes. Captions should be drivable/embeddable the same way. *(Transferable / Med.)*

**Deliberately differ:**

8. **Do NOT make live text-edit destructive to source media (contra Descript D1).** Descript's "delete text = delete audio" is right for post-production but wrong for a live/authoritative service record. SelahCue keeps source audio + raw tokens immutable; editing is overlay-only.
9. **Do NOT display live captions as authoritative on-screen scripture (contra CaptionKit's "reads cleanly enough to project without editing").** SelahCue's honesty stance stands: live captions are best-effort/opt-in, **VAD-gated** (Whisper silence-hallucination risk), and any on-screen *scripture* still requires the operator-confirmation/verification gate. Captions ≠ verified scripture text.
10. **Do NOT default to cloud (contra all three).** All three send sermon audio to the cloud by default. SelahCue stays **offline-first, opt-in cloud, consent-gated** (LICENSING-REGISTER / NDPA-GDPR).

### 3.2 Phase 5 — Sermon intelligence (notes / summary)

**Adopt:**

1. **Transcript-first, then generate (from Descript D7 + Otter O6 — both require the transcript before notes).** Validates SelahCue's transcript → notes pipeline ordering. *(Transferable / High.)*
2. **Structured note schema (from Otter Takeaways O6 + Descript show notes D7).** Both converge on: **summary → key takeaways → outline/chapters with timestamps → titles → action items**. SelahCue's sermon-note structure should adopt **summary, key points, sermon outline (titled sections + timestamps), quotable lines, and detected scripture references** — with each section timestamp-anchored to the transcript for jump-to-audio. *(Transferable / High.)*
3. **Auto-chaptering by topic (from Otter Outline O5 + Descript Chapter Generator D5).** Break a long sermon into titled **movements/sections** with timestamps — high value for navigation, re-preaching, and clip creation. *(Transferable / High.)*
4. **Live highlights/bookmarks feeding the notes (from Otter O4).** Let the operator or a mobile role **flag "highlight this moment" live**; flagged timestamps seed the post-service notes and clip selection. Low-risk, high-value, and fits SelahCue's mobile-controller model. *(Transferable / Med.)*
5. **Editable, human-gated, AI-labelled output (from Descript D7 + Otter — both make AI output editable).** Reinforces SelahCue's existing stance (human-gated, editable, labelled AI-generated, never auto-published). *(Transferable / High.)*
6. **Optional "ask the transcript" chat (from Otter AI Chat O6).** A later-phase, cloud-consent-gated Q&A over the sermon transcript for the post-service editor persona. *(Transferable / Low — post-MVP.)*

**Deliberately differ:**

7. **Add a scripture-verification gate none of these products has (gate condition C6).** Descript/Underlord and Otter generate freely and **can fabricate** — invented links, wrong takeaways, misattributed quotes — with **no ground-truth check**. SelahCue must **verify every auto-extracted scripture reference against the local Bible index and flag it `unverified` until matched** before it can enter notes or export. This is the single most important *difference* from the adjacent products and directly closes review finding **M6**.
8. **Offline-first, sensitive-content default (contra Otter/CaptionKit cloud-default).** Sermon notes carry doctrinal/pastoral sensitivity; SelahCue's default is **local LLM, no egress**, cloud only on explicit per-church consent (PROVIDER-TRADEOFFS §2.1). Meeting-SaaS cloud-default is the wrong posture for a church record.
9. **Never let notes overwrite the source transcript (reinforced by the Descript two-layer model D2).** Notes are a derived, labelled artifact over an immutable transcript.

---

## 4. Key UNKNOWNs

| # | UNKNOWN | Why it matters | How to close |
|---|---|---|---|
| U1 | **Real-room accuracy/latency of all three** in a reverberant church with PA bleed, roving mics, accents. All figures (Otter "98%", "reads cleanly without editing") are **vendor-claimed / uncorroborated**. | Sets realistic expectations for SelahCue's own live captions and correction burden. | Hands-on trial in a real service (Stage 5 spike) — cannot be inferred from marketing. |
| U2 | **Proprietary diarization/ASR internals & error rates** (Descript "Speaker Detective", Otter voiceprint). | We can adopt the *UX pattern* but not benchmark reliability. | Vendor black-box; treat diarization as best-effort per m5. |
| U3 | **CaptionKit transcript download format** — txt/docx/srt? Does it carry speaker labels + timestamps? Live-caption latency? | Determines whether it's a usable reference for our export schema. | Behind sign-up; would need a trial account. |
| U4 | **No JSON / token-level timestamped export found in any product** — is this truly absent or just undocumented? | If absent, it's a SelahCue differentiator; if present, a pattern to match. | Confirm via trial; otherwise proceed treating it as a differentiator. |
| U5 | **Exact export-format ↔ pricing-tier gating** (only Otter SRT auto-line-break confirmed Premium/Teams). | Affects which formats we treat as table-stakes vs premium. | Vendor pricing pages / trial. |
| U6 | **Non-destructive-edit / version-history model in Otter & CaptionKit** (only Descript's is documented). | Confirms whether the immutable-source pattern is industry-standard or SelahCue-specific. | Trial accounts. |
| U7 | **Offline capability** — inferred cloud-only for all three; not explicitly confirmed for CaptionKit/Descript. | Confirms SelahCue's offline-first is a genuine differentiator. | Vendor docs / trial. |

---

## 5. Sources (access date 2026-07-23)

**Descript**
- [Audio to Text — Descript](https://www.descript.com/tools/audio-text) *(fetched)*
- [Podcast Show Notes Generator (Underlord) — Descript](https://www.descript.com/tools/podcast-show-notes-generator) *(fetched)*
- [Underlord — Descript](https://www.descript.com/underlord)
- [Edit like a doc — Descript Help](https://help.descript.com/hc/en-us/articles/15726742913933-Edit-like-a-doc) *(403; via search snippet)*
- [Descript Transcription guide — Languages Unlimited](https://www.languagesunlimited.com/descript-transcription/)
- [Descript Review 2026 — work-management.org](https://work-management.org/marketing/podcast/descript-review/)

**Otter.ai**
- [Otter Meeting Agent — otter.ai](https://otter.ai/) *(fetched)*
- [Word DOCX export & auto-cut SRT — Otter blog](https://otter.ai/blog/word-docx-export-auto-cut-srt) *(fetched)*
- [How to Use AI to Summarize Transcripts — Otter blog](https://otter.ai/blog/ai-to-summarize-transcripts)
- [Conversation Page Overview — Otter Help](https://help.otter.ai/hc/en-us/articles/5093228433687-Conversation-Page-Overview) *(403; via search snippet)*
- [Speaker Identification Overview — Otter Help](https://help.otter.ai/hc/en-us/articles/21665587209367-Speaker-Identification-Overview) *(via search snippet)*
- [Export conversations — Otter Help](https://help.otter.ai/hc/en-us/articles/360047733634-Export-conversations) *(via search snippet)*
- [How to update the Summary and transcript in Otter — Enterprise Times](https://www.enterprisetimes.co.uk/2025/06/20/how-to-update-the-summary-and-transcript-in-otter-ai/)
- [Otter AI meeting summaries — DreamHost](https://www.dreamhost.com/blog/meeting-summaries-otter-ai/)

**CaptionKit (church tool)**
- [CaptionKit — captionkit.com](https://captionkit.com/) *(fetched; captionkit.io 308-redirects here)*
- [CaptionKit — faith.tools listing](https://faith.tools/app/1187-captionkit) *(fetched)*
- [Live Sermon Transcription 2026 guide — sermon-transcription.com](https://sermon-transcription.com/blog/live-sermon-transcription-real-time-captions)

---

*End of adjacent-product workflow study. Feeds Stage 3 requirements for Phase 3 (transcription) and Phase 5 (sermon intelligence); closes gate condition C1.*
