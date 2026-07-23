# SelahCue — Open Product Decisions (Stage 2 → for user / Stage 3 PRD)

Date: 2026-07-23 · Owner: Product Manager · Status: Awaiting user input at Stage 2 gate / to be resolved in Stage 3–5

These are unresolved **product** decisions surfaced by discovery. Engineering-only spikes (S1-S9) live in [FEASIBILITY.md](FEASIBILITY.md) §10 and are Stage 5 concerns. Each decision has a recommended default so the build can proceed without blocking; the user can override at the gate.

## A. Scope & platform

| ID | Decision | Options | Recommendation | Owner |
|---|---|---|---|---|
| OD-01 | MVP platform breadth | (a) All 5 platforms at once; (b) Desktop-first (Win/macOS/Linux) with mobile controller in a fast-follow; (c) Windows+macOS desktop first, Linux + mobile later | **(b)** Desktop tri-platform + a thin mobile controller — but bound MVP feature scope hard (RISK-001). Full 5-platform parity is a later release. | User + PM |
| OD-02 | Is TTS in the product? | (a) MVP; (b) Defer to later release; (c) Remove from roadmap | ✅ **DECIDED (c) — removed from roadmap** (user, 2026-07-23, [DEC-001](../decisions/DECISION-LOG.md)). TTS is a **non-goal / on-hold**; revisit only on explicit future request. Discovery had recommended deferral; the user de-scoped it entirely. | User (decided) |
| OD-03 | MVP AI scope | (a) Full (transcription + detection + sermon notes) in MVP; (b) Presentation-only MVP, AI in later phases per brief's phased plan | **(b)** Ship presentation foundation first (Phase 1), layer transcription → scripture intelligence → sermon notes as later releases. Keeps first release implementable. | User + PM |
| OD-04 | Product positioning/pricing model | Free/OSS · freemium · subscription · perpetual+support | Defer to Stage 3; discovery suggests a **free tier + fair/regional paid tiers** lane (vs ProPresenter price, PewBeam Global-South). Not needed to start building. | User |

## B. Scripture & content licensing

| ID | Decision | Options | Recommendation | Owner |
|---|---|---|---|---|
| OD-05 | MVP Bible translations | Bundle PD set only; add API-only licensed tier; add user-import | **Bundle PD set** (KJV ex-UK, WEB, ASV, YLT, BSB, BBE, Darby, Webster) for MVP; design API-only + user-import paths for licensed translations as a later feature. | PM + Security |
| OD-06 | Licensed-translation strategy (NIV/ESV/…) | API.Bible commercial tier · user-supplied module import · both · none for MVP | Design for **both** (API + import) but treat as post-MVP; requires commercial licence/legal (see legal-confirmation list). | User (commercial) + Legal |
| OD-07 | Song-lyrics strategy | User-supplied only · CCLI SongSelect integration · PD hymn bundle | **User-supplied + PD hymn bundle** for MVP; CCLI SongSelect integration later. Never bundle copyrighted lyrics. | PM |
| OD-08 | Legal items needing confirmation before ship | ESV/API.Bible commercial+caching, LEB/unfoldingWord share-alike, UK KJV, codec-patent path, Coqui XTTS, cloud-AI data terms, NDI 6.x EULA, OSS SBOM | **Escalate to user/legal** — none block MVP presentation build if we ship PD Bibles + OS-native codecs; block only the licensed-translation and cloud-AI features. | User + Legal |

## C. Privacy & data

| ID | Decision | Options | Recommendation | Owner |
|---|---|---|---|---|
| OD-09 | Default data-retention for recordings/transcripts/notes | Keep indefinitely · conservative default (e.g. transcript kept, raw audio purged after N days) · keep nothing | **Conservative default** — keep transcript/notes, do not retain raw audio beyond need; user-configurable. Exact N = Stage 3. | User + Security |
| OD-10 | Congregation-recording consent | App-enforced notice · guidance only · none | **Guidance + consent-capture affordance** (NDPA/GDPR); recommend churches disclose recording. Legal review for jurisdictional consent laws. | User + Legal |
| OD-11 | Cloud AI/transcription posture | On-device only for MVP · opt-in cloud from MVP | **On-device default; opt-in cloud** with visible disclosure + "cloud active" indicator + secure key storage. (Cloud features are post-MVP anyway per OD-03.) | PM + Security |

## D. Roles & permissions (from PERSONAS §4)

| ID | Decision | Recommendation | Owner |
|---|---|---|---|
| OD-12 | Should Blackout be available to lower roles as an emergency panic button? | **No by default**; keep to Production/Admin. Desktop operator + Emergency Clear covers the panic case. Admin-configurable. | User + UX |
| OD-13 | Any mobile role that displays scripture without desktop approval? | **No** — human-in-the-loop approval always mandatory for auto-detected scripture (precision-over-recall). Manual scripture display by Scripture Operator is fine. | User + PM |
| OD-14 | Per-output permissions (e.g. stream-only control)? | **Post-MVP** — model as a later enhancement; MVP uses the flat role matrix. Livestream Director implies it but it adds complexity. | PM |
| OD-15 | Time-boxed/event-scoped volunteer grants (auto-revoke)? | **Yes, desirable** — include revocation now; auto-expiry as a fast-follow. | PM + Security |
| OD-16 | Dedicated Pastor read-only "confidence" mobile profile vs Observer? | **Later** — Observer covers MVP; add a Pastor confidence profile in a mobile-polish release. | UX |
| OD-17 | Macro triggering: granular allow-list vs all-or-nothing? | **Granular (per-macro)** eventually; MVP may defer macros entirely (brief lists macros as later). | PM |

## E. Security architecture (decided in Stage 5, flagged here)

| ID | Decision | Recommendation | Owner |
|---|---|---|---|
| OD-18 | LAN transport: TLS 1.3 + pinned self-signed cert vs Noise-style app-layer crypto | Lean **TLS 1.3 + QR-pinned fingerprint**; final call = Stage 5 ADR + Stage 13 security review. | Architect + Security |
| OD-19 | Linux secret-storage fallback when no Secret Service present | Must **not** silently store plaintext; decide passphrase-derived encryption vs refuse-to-persist in Stage 5. | Architect + Security |
| OD-20 | Multi-controller conflict resolution (two operators, conflicting live commands) | Define authoritative-desktop last-writer + role precedence in Stage 5; flag for UX. | Architect + UX |

## F. Carried from Stage 2 independent review (resolve in Stage 3–5)

Architecture/requirements-shaping conditions from [DISCOVERY-REVIEW.md](DISCOVERY-REVIEW.md), each with a pre-loaded recommendation so Stage 3/5 can close them without re-litigation. Full dispositions in [CONDITION-DISPOSITIONS.md](CONDITION-DISPOSITIONS.md).

| ID | Decision | Recommendation | Owner |
|---|---|---|---|
| OD-21 (C9) | At-rest confidentiality for the primary datastore + captured audio (currently only backups are encrypted per threat-model T15) | Encrypt the primary store — **SQLCipher with key custody tied to the OS secret store** — OR require + verify OS full-disk encryption (FileVault/BitLocker/LUKS) as a documented deployment prerequisite. Reconcile LICENSING §4 / threat-model T15 / FEASIBILITY §7 into one PRD requirement (NFR). | Architect + Security |
| OD-22 (C2) | MVP language/script scope + complex-script/RTL text shaping | State MVP scope = **Latin + the cited Nigerian/European languages that are LTR**; add a text-shaping spike (confirm HarfBuzz/cosmic-text-class shaping in the chosen renderer) before committing the GPU text stack; **defer RTL/complex-script (Arabic/Hebrew) past MVP as an explicit scoped-later decision**. | Architect + PM |
| OD-23 (C10) | wgpu multi-output topology has no fallback if spike S2 (zero-copy HW-decode→wgpu) fails | Define a fallback (GStreamer glvideomixer / per-OS native compositor / accept 1080p30 or fewer outputs); **gate** the "2–3 independent 1080p60 outputs" promise on S1/S2 results before it becomes a committed PRD requirement. | Architect |
| OD-08a (C8) | Codec-patent safe harbor depends on OS-native decode, but FEASIBILITY commits to GStreamer without constraining decoders | Add a build constraint: media engine uses **platform/HW-decode GStreamer elements only** (d3d11/va/vtdec/nvdec); **exclude gst-libav** (avdec_h264/h265) for encumbered codecs. Downgrade OD-08 codec item to **conditional pending legal confirmation** (register UNKNOWN #5). VP9/AV1+Opus preference covers only SelahCue-generated media, not user-imported H.264 backgrounds. | Architect + Legal |
| OD-24 (m12) | "Bundle KJV outside UK" has no geo-exclusion mechanism in a globally downloadable app | **Drop KJV from the bundled set** (WEB/ASV/BSB are worldwide-PD and cover the need) OR make UK exposure an explicit accepted-risk decision. Do not carry "bundle KJV" unresolved into the PRD. | PM + Legal |

## Summary for the gate

**Nothing here blocks starting the build**, provided the user confirms the MVP-shaping recommendations (OD-01 desktop-first bounded MVP, OD-02 defer TTS, OD-03 presentation-first with phased AI, OD-05 bundle PD Bibles). The licensed-translation, cloud-AI, and legal-confirmation items (OD-06/08/10) gate only their specific later features, not the presentation foundation. These recommendations are carried into the Stage 3 PRD as the proposed MVP boundary unless the user directs otherwise.
