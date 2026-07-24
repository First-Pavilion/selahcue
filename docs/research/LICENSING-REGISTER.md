# SelahCue — Licensing & Compliance Register (RP-07 / RP-11)

Owner: Security Reviewer + Product Manager · Access date for all findings: **2026-07-23**
Org context: First Pavilion (appears Nigeria-based) → NDPA/NDPR + GDPR both in scope.

**Discipline.** Every finding is classified **OBSERVED** (seen directly in a primary licence/terms text), **DOCUMENTED** (stated by a credible secondary source), **INFERRED** (reasoned from evidence, not stated verbatim), or **UNKNOWN** (needs confirmation). Nothing is assumed redistributable. Confidence = High/Med/Low. "Bundle" = ship the asset/text inside the installed app; "User-supplied" = the user imports their own licensed copy; "API-only" = fetched live from a licensed service, not stored/redistributed.

> ⚠️ This register is engineering/product due-diligence, **not legal advice**. Copyrighted-text, codec-patent, and cross-border data items marked below must be confirmed by qualified counsel and/or the rights holder before ship.

---

## 1. Bible-translation licensing table

| Translation | Copyright status | Bundle? | User-supplied? | API-only? | Attribution required | Class / Conf | Source (accessed 2026-07-23) |
|---|---|---|---|---|---|---|---|
| **KJV** (King James Version) | Public domain **outside UK**; **Crown copyright in UK** (Cambridge/CUP patent) | ✅ (outside UK) | ✅ | n/a | No (courtesy only) | DOCUMENTED / High | get.bible, JollyNotes, inspiringtips |
| **WEB** (World English Bible) | Public domain — copyright deliberately surrendered | ✅ | ✅ | n/a | No (courtesy only) | DOCUMENTED / High | worldenglish.bible, get.bible |
| **ASV** (American Standard Version, 1901) | Public domain (copyright expired) | ✅ | ✅ | n/a | No | DOCUMENTED / High | get.bible, blueletterbible |
| **YLT** (Young's Literal Translation, 1862/1898) | Public domain | ✅ | ✅ | n/a | No | DOCUMENTED / High | Wikipedia (YLT), get.bible |
| **BSB / Berean family** (Berean Standard Bible, Berean Literal, Majority) | Public domain via **CC0** since **2023-04-30** | ✅ | ✅ | n/a | Appreciated, **not required** | DOCUMENTED / High | bereanbible.com, archive.org, bsb.freely.giving |
| **Darby**, **Webster** | Public domain (worldwide) | ✅ | ✅ | n/a | No | DOCUMENTED / Med | get.bible |
| **BBE** (Bible in Basic English) | **US-only PD** (UCC non-notice); Cambridge UP copyright plausibly runs to 2038 in life+70 jurisdictions (UK/EU/Nigeria — translator S. H. Hooke d. 1968) | ⚠️ US-only | ❌ not bundled (batch 7ae review) | n/a | Owner decision needed for US-only distribution | VERIFIED / High | ebible.org engBBE copyright page (2026-07-24) |
| **LEB** (Lexham English Bible) | Free use **with attribution** (Lexham/Logos terms; CC-style) | ⚠️ likely, verify | ✅ | ✅ | **Yes** | DOCUMENTED / Med | get.bible (confirm lexhampress terms) |
| **NET Bible** | Free for **non-commercial**; commercial needs licence | ❌ (commercial app) | ✅ | ✅ (bible.org web service) | Yes | DOCUMENTED / Med | get.bible, bible.org |
| **unfoldingWord / ULB / UST** | Open-licensed (**CC BY-SA 4.0**) | ✅ (with share-alike caveat) | ✅ | ✅ | **Yes (CC BY-SA)** | DOCUMENTED / Med | get.bible, unfoldingWord |
| **ESV** (English Standard Version) | Copyrighted (Crossway). API = **non-commercial only**, ≤500-verse cache/display, no wording changes, attribution+link; commercial needs separate licence | ❌ | ✅ (user's licence) | ✅ (ESV API, non-comm) | **Yes** (notice on every page + link) | OBSERVED / High | esv.org/api |
| **NIV** (Biblica/Zondervan) | Copyrighted — licence required | ❌ | ✅ | ✅ (via API.Bible licensed tier) | Yes | DOCUMENTED / High | biblica.com/permissions, API.Bible |
| **NLT** (Tyndale) | Copyrighted; api.nlt.to free **non-commercial** only | ❌ | ✅ | ✅ (non-comm) | Yes | DOCUMENTED / High | get.bible, api.nlt.to |
| **NKJV, NASB, CSB** | Copyrighted (Thomas Nelson / Lockman / Holman) — licence required | ❌ | ✅ | ✅ (API.Bible licensed tier) | Yes | DOCUMENTED / High | API.Bible, blueletterbible |
| **The Message (MSG)** | Copyrighted (NavPress) — licence required | ❌ | ✅ | ✅ (API.Bible) | Yes | DOCUMENTED / High | API.Bible |
| **Amplified (AMP)** | Copyrighted (Lockman) — licence required | ❌ | ✅ | ✅ (API.Bible) | Yes | DOCUMENTED / High | API.Bible |

### Data sources / formats (how to obtain bundlable text)
- **eBible.org / open.bible / worldenglish.bible** — public-domain & CC texts in **USFM, USX, plain text, ePub, SQL**. Suitable to bundle PD/CC translations. Class DOCUMENTED / High (get.bible).
- **SWORD / OSIS / USFM / USX / Zefania** — open interchange formats; the *format* is free, but the *text inside* keeps its own copyright. Bundling a SWORD module does **not** launder a copyrighted translation. Class INFERRED / High.
- **API.Bible** (American Bible Society) — two tiers: **open-access** (PD + Creative Commons, no restriction) vs **copyright-protected** (Starter = up to 3 licensed versions **non-commercial**; commercial = paid). Licensed content requires **FUMS** (Fair Use Management System) usage reporting to rights holders; caching/offline of licensed text not granted by default. Class OBSERVED / High (docs.api.bible).
- **Free Use Bible API** (bible.helloao.org) — **MIT-licensed codebase**, 1250+ translations, no key/limits. ⚠️ MIT covers the *code*, **not** each translation's underlying copyright — verify per-translation status before bundling; treat non-PD entries as UNKNOWN. Class DOCUMENTED / Med (faith.tools, bible.helloao.org).
- **Bible Gateway / YouVersion** — no general redistribution/bundling licence; display governed by their own terms; treat as reference only, not a bundling source. Class INFERRED / Med.

**Bottom line:** Bundlable for MVP = **KJV, WEB, WEBBE, ASV, YLT, BSB/Berean, Darby, Webster** (PD worldwide), plus **LEB/unfoldingWord with attribution/share-alike caveats**. **BBE is US-only PD — excluded from the bundle (batch 7ae) pending an owner decision.** Everything copyrighted (NIV/ESV/NLT/NKJV/NASB/CSB/MSG/AMP) must be **API-only or user-supplied**, never bundled. *(As bundled 2026-07-24: KJV, WEB, WEBBE, ASV, Darby — YLT has no usable ebible export.)*

---

## 2. Codecs, fonts, icons, STT/TTS models, NDI

### 2.1 Media codecs (patent, not copyright) — highest hidden risk
| Item | Finding | Class / Conf | Source |
|---|---|---|---|
| **H.264 / AVC** | Patent pool administered by **Via LA** (ex-MPEG LA). Royalties can apply to encoders, decoders, and distributed content. A commercially distributed app that ships its **own** H.264 codec (e.g. bundled FFmpeg/libavcodec) may owe royalties / need a pool licence. | DOCUMENTED / Med | via-la.com, streamingmedia |
| **HEVC / H.265** | Fragmented licensing — **Via LA + Access Advance** pools **plus** unpooled patent holders; more expensive/complex than AVC. Avoid for MVP if possible. | DOCUMENTED / Med | streamingmediaglobal |
| **AAC** | Patent pool via **Via LA**; single agreement but still a paid pool for implementers. | DOCUMENTED / Med | scconline (Via/AAC) |
| **OS system codecs** (Windows Media Foundation, macOS/iOS AV Foundation, Android MediaCodec) | Playback through the **platform-provided** decoder is generally covered by the OS vendor's own patent licence → lowest-risk path. Shipping your **own** decoder shifts patent liability to you. | INFERRED / Med | archwiki, Mozilla bug 851290 |
| **libavcodec / FFmpeg** | LGPL **software** licence — but LGPL does **not** grant patent rights. Patent exposure for H.264/HEVC/AAC remains with the distributor. | DOCUMENTED / High | Wikipedia (libavcodec) |
| **Royalty-free alternatives** | **VP9 / AV1** (video), **Opus / Vorbis / FLAC** (audio) are royalty-free — prefer these for any app-generated/exported media. | INFERRED / High | general codec landscape |

**Recommendation:** MVP should **rely on OS-native playback** for H.264/AAC (delegate patent licensing to the platform) and **prefer VP9/AV1 + Opus** for anything SelahCue itself encodes/exports. Do **not** bundle a self-contained H.264/HEVC/AAC encoder without a Via LA (and, for HEVC, Access Advance) licence review.

### 2.2 Fonts
| Item | Finding | Class / Conf | Source |
|---|---|---|---|
| **SIL Open Font License (OFL)** fonts | May be **embedded/bundled** in commercial software and redistributed; **cannot be sold on their own**; **Reserved Font Names** must not be reused by modifications. Safe to bundle. | OBSERVED / High | openfontlicense.org, SIL FAQ |
| **Apache-2.0 fonts** (e.g. Roboto, Material) / **Google Fonts** | Generally bundlable in commercial apps; check per-family licence (most OFL or Apache-2.0). | DOCUMENTED / High | openfontlicense.org |

### 2.3 Icons
| Library | Licence | Bundle? | Class / Conf | Source |
|---|---|---|---|---|
| **Lucide** (Feather fork) | ISC | ✅ | DOCUMENTED / High | mockflow, dev.to |
| **Heroicons, Tabler, Phosphor, Bootstrap Icons** | MIT | ✅ | DOCUMENTED / High | mockflow |
| **Material Symbols** | Apache-2.0 | ✅ | DOCUMENTED / High | mockflow |
| **Font Awesome (free tier)** | Icons CC BY 4.0 (attribution) + fonts OFL + code MIT | ✅ w/ attribution | DOCUMENTED / Med | fontalternatives |

### 2.4 Speech-to-text (STT) models
| Model | Licence | Bundle? | Class / Conf | Source |
|---|---|---|---|---|
| **OpenAI Whisper** (+ whisper.cpp, faster-whisper) | **MIT** — commercial use, redistribution, no fees | ✅ | DOCUMENTED / High | Wikipedia (Whisper) |
| Cloud STT (Google/Azure/Deepgram) | Per-provider ToS, usage fees, **data leaves device** → privacy disclosure needed | n/a (API) | INFERRED / Med | provider docs |

### 2.5 Text-to-speech (TTS) voices
| Item | Finding | Class / Conf | Source |
|---|---|---|---|
| **Piper TTS** | MIT-licensed; note repo **archived 2025-10-06** (read-only) → maintenance risk | DOCUMENTED / Med | dev.to, kunalganglani |
| **OpenVoice** | MIT-licensed, cross-lingual cloning | DOCUMENTED / Med | tderflinger |
| **Coqui XTTS v2** | Model lives on as open source **but** XTTS ships under the **Coqui Public Model License (non-commercial)** — do **not** assume commercial use. VERIFY. | DOCUMENTED→UNKNOWN / Low | github/openedai-speech |
| **OS/platform voices** (SAPI, AVSpeechSynthesizer, Android TTS) | Covered by OS licence; availability varies per platform; no redistribution of voice data | INFERRED / Med | platform docs |
| Cloud TTS voices (ElevenLabs/Google/Azure) | Per-provider commercial terms + fees; voice output usage rights vary | UNKNOWN / Low | provider docs |

### 2.6 NDI SDK
| Item | Finding | Class / Conf | Source |
|---|---|---|---|
| NDI SDK licence | **Royalty-free**; may bundle the NDI **redistributable** object code in your installer for free or commercial products | OBSERVED / High | NDI License Agreement (Nov 2024), docs.ndi.video |
| Attribution / linking | Must place a **link to ndi.video** near every place NDI is used/selected in the UI, on your website, and in docs | OBSERVED / High | docs.ndi.video/licensing |
| Versioning | Must make reasonable effort to keep redistributed NDI runtime **up to date** | OBSERVED / High | docs.ndi.video/software-distribution |
| Codec caveat | NDI explicitly states **AAC/H.264/H.265 licensing is YOUR responsibility** — ties back to §2.1 | OBSERVED / High | NDI SDK License PDF |
| Recent change | 2025 discussion of tightened commercial-use terms → **re-read current 6.x SDK EULA before ship** | DOCUMENTED / Med | LinkedIn/Reddit thread |

---

## 3. Song lyrics / CCLI guidance

| Finding | Class / Conf | Source |
|---|---|---|
| Copyrighted worship lyrics may be **projected/printed** by a church that holds a **CCLI Church Copyright License**; the **licence belongs to the church, not the software vendor**. | DOCUMENTED / High | ccli.com, mediashout |
| SelahCue must **not bundle or ship copyrighted lyrics**. Lyrics should be **user-supplied** (typed/imported by the licensed church) or pulled via an **authorized SongSelect integration** available to CCLI subscribers. | INFERRED / High | mediashout, ccli.com |
| When displaying copyrighted lyrics, the church must show **title, author(s), copyright year, publisher, and CCLI licence number**. SelahCue should provide **fields + an on-slide copyright-footer feature** to make this easy. | DOCUMENTED / High | renewingworshipnc, ccli.com |
| Churches must **report usage** so royalties flow to rights holders; **streaming** (livestream to congregation online) needs a **separate CCLI Streaming Licence**. If SelahCue outputs to a livestream, surface this obligation. | DOCUMENTED / High | ccli.com/streaming |
| **Public-domain hymns** (e.g. pre-1929 classics) may be bundled freely — maintain a clearly-marked PD hymn set separate from user/CCLI content. | INFERRED / Med | general PD rules |

**Product posture:** treat lyrics like the Bible copyrighted tier — **user-supplied / integration-only**, with first-class copyright-metadata capture and an optional auto-generated copyright footer. Compliance responsibility is the church's; SelahCue is a tool.

---

## 4. User recordings / transcripts / cloud storage & data protection

| Finding | Class / Conf | Source |
|---|---|---|
| Sermon **audio recordings and transcripts are personal data** where a speaker is identifiable → NDPA & GDPR apply. | INFERRED / High | NDPA text, GDPR |
| **Nigeria NDPA 2023** repealed/replaced NDPR 2019; GDPR-aligned: lawful basis, **informed specific consent**, sensitive-data & children's safeguards, **72-hour breach notice**, data-subject rights (access/erasure), data-processing agreements with processors. | DOCUMENTED / High | cookieyes, securiti, iclg |
| Any **cloud storage** provider is a **data processor** → a signed **Data Processing Agreement** is required; consider **data-residency / cross-border transfer** rules under both NDPA and GDPR. | DOCUMENTED / High | cookieyes (NDPA) |
| **Ownership**: recordings/transcripts should remain the **church's/user's data**; SelahCue's ToS must state it does not claim ownership and processes only on the customer's instruction. | INFERRED / High | best practice |
| **AI processing** (Whisper/LLM sermon notes): if audio is sent to a **cloud** AI provider, that is a cross-border transfer + processor relationship → disclose, get consent, prefer **on-device** (Whisper MIT local) for MVP to minimise exposure. | INFERRED / High | NDPA automated-processing note |
| Recording people (congregation/speakers) may need **notice/consent** at capture time; provide a consent-capture affordance. | INFERRED / Med | NDPA consent rules |

**Posture:** default to **local/offline processing**; make any cloud sync **opt-in with consent**; ship a **privacy policy**, **DPA template**, retention controls, and export/delete. Minimise data; encrypt at rest and in transit.

---

## 5. App-store & OSS-dependency compliance

| Finding | Class / Conf | Source |
|---|---|---|
| **Apple App Store**: mandatory **privacy policy** + **App Privacy "nutrition label"** disclosures in App Store Connect, including third-party SDK data practices. | DOCUMENTED / High | cookieyes, termly |
| **Google Play**: mandatory **privacy policy** link in Play Console **and** a completed **Data Safety** form. | DOCUMENTED / High | cookieyes |
| **Microsoft Store**: privacy policy required for apps that access personal/sensitive data or network. | INFERRED / Med | store policy norms |
| **OSS licence hygiene**: maintain an **SBOM**; avoid **copyleft (GPL/AGPL)** components linked into proprietary distribution; **LGPL** (FFmpeg, GStreamer core) usually OK if dynamically linked + relink rights preserved; ship a **third-party notices** file (MIT/BSD/ISC/Apache/OFL attributions). | INFERRED / High | licence texts |
| **Apache-2.0** carries a patent grant + NOTICE-file obligation; **GStreamer "ugly"/libav** plugins carry the codec-patent caveats of §2.1. | DOCUMENTED / Med | archwiki, Apache-2.0 |

---

## 6. Recommended MVP licensing posture

**Safe to ship / bundle now:**
- **Bibles (bundle):** KJV, WEB, WEBBE, ASV, Darby (shipped 2026-07-24) + YLT/BSB/Webster candidates — public domain worldwide. **BBE excluded (US-only PD).** Sourced as **VPL plain text** from eBible.org. Include a courtesy attribution/copyright-metadata screen even where not required.
- **Bibles (user-supplied / API-only):** NIV, ESV, NLT, NKJV, NASB, CSB, MSG, AMP — never bundled. Offer **API.Bible** (licensed tier, commercial plan) and/or **user import** of the user's licensed module. If using ESV API, respect ≤500-verse limits + non-commercial boundary (needs a commercial licence for a paid app).
- **STT:** Whisper (MIT), on-device.
- **Fonts:** OFL/Apache families. **Icons:** Lucide/MIT sets. **NDI:** bundle redistributable + add ndi.video link, keep updated.
- **Media playback:** use **OS-native decoders**; export in **VP9/AV1 + Opus** where SelahCue encodes.

**Key restrictions to enforce in product:**
1. No copyrighted Bible text or worship lyrics in the shipped binary — API/user-supplied only.
2. Copyright-metadata + on-slide attribution features for Bible and lyrics; CCLI licence-number field + streaming-licence reminder.
3. Codec patent responsibility: no self-bundled H.264/HEVC/AAC encoder without a Via LA / Access Advance review.
4. Privacy-by-default: local processing, opt-in cloud, consent capture, privacy policy + DPA, retention/erase controls (NDPA + GDPR).
5. NDI attribution + up-to-date runtime; third-party-notices file + SBOM; no GPL/AGPL in the proprietary build.

---

## 7. Key UNKNOWNs / needs legal or rights-holder confirmation

1. **Commercial ESV / API.Bible pricing & caching rights** — ESV API is non-commercial; a paid app needs a **commercial ESV licence** (Crossway) and clarity on **offline caching** of licensed text. **[Legal + rights holder]** — Confidence Low.
2. **API.Bible offline/bundling & FUMS obligations** for licensed translations in a distributed desktop app (vs web). **[Rights holder]** — Low.
3. **LEB / unfoldingWord exact terms** — confirm CC BY-SA share-alike implications for a proprietary app (attribution + adaptation clauses). **[Legal]** — Med.
4. **KJV in UK market** — Crown/CUP patent; confirm before UK distribution. **[Legal]** — Med.
5. **Codec patent exposure** — whether SelahCue's actual media path bundles any H.264/HEVC/AAC encoder/decoder, and resulting Via LA / Access Advance obligations. **[Legal + eng audit]** — Med.
6. **Coqui XTTS commercial licence** — XTTS ships under a **non-commercial** model licence; confirm before any commercial TTS use. **[Rights holder]** — Low.
7. **Cloud AI provider terms** (LLM sermon notes, cloud STT/TTS) — data-use, training-on-input, cross-border transfer under NDPA/GDPR. **[Legal + provider ToS]** — Low.
8. **NDI current 6.x EULA** — re-read for any 2025 commercial-use tightening before ship. **[Legal]** — Med.
9. **Full OSS dependency inventory** — SBOM not yet produced; copyleft contamination unverified. **[Eng]** — Med.

---

### Source index (all accessed 2026-07-23)
get.bible/bible-data-sets · docs.api.bible/quick-start/licensing-and-access · esv.org/api · bereanbible.com / archive.org (BSB CC0) · worldenglish.bible · blueletterbible.org/versions · biblica.com/permissions · bible.helloao.org · via-la.com (AVC/H.264) · streamingmediaglobal.com (codec licensing) · scconline.com (Via/AAC) · en.wikipedia.org/wiki/Libavcodec · en.wikipedia.org/wiki/Whisper · openfontlicense.org + SIL font FAQ · mockflow.com (icon libraries) · downloads.ndi.tv NDI License Agreement + docs.ndi.video · ccli.com + mediashout.com + renewingworshipnc.org · cookieyes.com/securiti.ai/iclg.com (NDPA 2023) · termly.io (app-store privacy).
