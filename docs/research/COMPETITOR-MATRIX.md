# SelahCue — Competitor & Adjacent-Tool Research Matrix

**Work items:** RP-01, RP-02, RP-13
**Prepared by:** Product Researcher, SelahCue
**Access date for all findings:** 2026-07-23
**Method:** WebSearch + WebFetch against public product pages, official docs, and third-party reviews. No trials purchased; no paywalled workflows accessed. Proprietary code, branding, and UI were not copied — only described capabilities/workflows.

## Classification legend

| Tag | Meaning |
|-----|---------|
| **OBSERVED** | Directly seen on a page / video / screenshot |
| **DOCUMENTED** | Stated in official docs or the vendor's own site |
| **INFERRED** | Reasoned from indirect evidence; not explicitly confirmed |
| **UNKNOWN** | Could not verify with available (non-paywalled) access |

Confidence (High/Med/Low) reflects source authority + corroboration. Because this research relied on vendor marketing pages, docs, and reviews rather than hands-on trials, most "does feature X exist" findings are DOCUMENTED-High while "how well X works / exact internals" are INFERRED or UNKNOWN.

---

## 1. Capability Comparison Matrix — Church Presentation Products

Legend: **Y** = present (documented) · **~** = partial / add-on / indirect · **N** = not present / not offered · **?** = UNKNOWN (unverified)

| Capability | PewBeam | ProPresenter 7 | OpenLP | FreeShow | EasyWorship | Quelea |
|---|---|---|---|---|---|---|
| Service planning / run sheets | ~ | Y (+ Planning Center sync) | Y | Y (project/show model) | Y (schedules, drag-drop) | Y (schedules) |
| Slide creation / editor | Y (AI Slides) | Y (rich editor) | Y (custom slides) | Y (drag-drop editor) | Y (Presentation Editor) | Y (quick edit) |
| Song-lyrics import | ~ | Y (SongSelect/CCLI, import) | Y (multi-format import) | Y (auto slide gen; import PP/Pro/EW/OpenSong) | Y (CCLI SongSelect built-in) | Y (EW/OpenLP/OpenSong/Kingsway) |
| Scripture search & present | Y (semantic + AI live) | Y | Y (ref + phrase search) | Y (one-click lookup) | Y (built-in DB, multi-translation) | Y (Zefania XML) |
| Stage / confidence display | ? | Y (multiple, styleable) | Y (web stage view) | Y (stage view) | ~ | Y (chords to band) |
| Multiple outputs | Y (multi-output) | Y (multi-screen, edge blend) | Y (multi-screen) | Y (simultaneous views) | Y | ~ |
| Lower thirds | ? | Y (Live Stream L3, key/fill) | ~ | Y (via multi-view/web) | ~ | ? |
| Timers / countdowns | ? | Y (audience + stage) | ~ | Y (slide timers, countdowns) | ~ | ? |
| Templates / themes | Y (themes, designer) | Y (themes) | Y (themes) | Y (templates) | Y | Y |
| Permissions / roles | ? | ~ (via Planning Center collab) | N (single-app) | ~ (cloud multi-user) | ? | N |
| Mobile remote control | ~ (PewNotes app) | Y (iOS/Android remote) | Y (web + iOS/Android) | Y (web remote) | Y (iOS/Android apps) | Y (mobile lyrics push) |
| Crash recovery | Y (offline resilience claim) | ? | Y (documented) | ? | ? | ? |
| NDI output | Y | Y (NDI/SDI over coax/ethernet) | ~ | Y (native, no converter) | Y | ? |
| Pricing model | Freemium (loc-based) | Paid seat + subscription add-on | Free (OSS) | Free (OSS/donation) | Subscription | Free (OSS) |
| Windows | ? | Y | Y | Y | Y | Y |
| macOS | ? | Y | Y | Y | Y | Y |
| Linux | ? | N | Y | Y | N | Y (JVM) |
| Mobile app | Y (PewNotes) | Y (remote only) | Y (remote only) | Y (remote only) | Y (control) | ~ (viewer) |

> Note on stage/lower-third/timer "?" cells for PewBeam, EasyWorship, Quelea: the vendor pages reviewed did not clearly confirm these; they may exist but are unverified here. See Key UNKNOWNs (§6).

---

## 2. Per-Product Notes (classified findings + sources)

### 2.1 PewBeam
An AI-native church presentation app (Dara Sobaloju / Nigerian-origin, launched ~2026) whose flagship differentiator is live sermon-following scripture projection.

- **DOCUMENTED that the *capability is claimed* (High); performance figures VENDOR-CLAIMED / UNCORROBORATED (Low)** (re-tagged per DISCOVERY-REVIEW C5/M5): Real-time speech recognition listens to the preacher and surfaces the relevant Bible verse on-screen automatically. The vendor's marketing states detection in ~2 seconds and "under 80 ms" for surfacing — these are **vendor self-reported numbers on a marketing page, not independently measured**, and are consistent with §6 UNKNOWN #8 (real-world sermon-follow latency = UNKNOWN). Treat the *existence of the claim* as documented; treat the *truth of the numbers* as UNKNOWN pending a hands-on trial. Handles exact quotes and paraphrases via semantic search (mechanism claimed, accuracy UNKNOWN). — https://pewbeam.com/ ; https://technext24.com/2026/03/23/pewbeam-all-you-should-know
- **DOCUMENTED (High):** Works fully offline for speed/privacy/reliability. — https://pewbeam.com/
- **DOCUMENTED (Med):** v2.0 adds AI-generated Slides, a Greek/Hebrew "Lexicon" word-meaning tool, live transcripts, and a companion "PewNotes" mobile app; live transcription/translation incl. French, Spanish, Yoruba, Hausa, Igbo. — https://technext24.com/reviews/pewbeam-2-0-launch-ai-slides-pewnotes-lumen/
- **DOCUMENTED (High):** Pricing — Starter Free (40 min/week transcription, 2 built-in + 1 custom theme); Plus $14/mo (unlimited transcription, all themes, no watermark); Core $30/mo (3 devices/license, priority support, advanced AI). Location-based pricing for economic fairness. — https://pewbeam.com/
- **DOCUMENTED (Med):** NDI output and projector display mentioned. — https://pewbeam.com/
- **INFERRED (Low):** Likely desktop-based (Win/Mac) given projector/NDI use, but the page did not explicitly state OS support.
- **UNKNOWN:** OS/platform matrix, stage display, lower thirds, timers, permissions/roles, crash-recovery internals, service-planning depth. Not confirmed on public pages.
- **Notable strength:** Category-defining live sermon-follow AI + strong Global-South language/pricing focus.
- **Notable gap (inferred):** Appears verse-projection-centric; traditional production features (multi-screen layout control, run sheets, roles) are unproven.

### 2.2 ProPresenter 7 (Renewed Vision)
Market-leading pro church/live-event presentation software.

- **DOCUMENTED (High):** Multi-screen output (3-screen edge blend, side screens), multiple independently-styled stage displays, alpha keyer, edge blending, control-protocol comms, and SDI/NDI over coax/ethernet — all now bundled (were paid add-ons pre-7). — https://renewedvision.com/propresenter7/whats-new7/
- **DOCUMENTED (High):** Timers/countdowns for audience and stage; built from Timer + Theme + Message components; Show Controls incl. audio, stage controls, messages, props. — https://www.renewedvision.com/tutorials/how-to-use-timers-countdowns-in-propresenter-7 ; https://www.renewedvision.com/tutorials/propresenter-7-show-controls-audio-stage-controls-timers-messages-props
- **DOCUMENTED (High):** Lower thirds via "Live Stream L3" (green-screen-backed lyrics/scripture/announcements to switchers); ATEM integration. — search corpus (renewedvision support)
- **DOCUMENTED (High):** Planning Center Online integration — services build playlists inside Pro; multi-role collaboration (worship leaders build, admins upload, designers attach graphics); PCO changes auto-appear. — https://www.renewedvision.com/tutorials/planning-center-online-integration-collaboration-with-propresenter-7
- **DOCUMENTED (High):** ProPresenter Remote mobile app (iOS/Android) included with active subscription; controls slides/media/timers, monitors stage displays, over local Wi-Fi. — https://propresenter7.com/propresenter-remote/
- **DOCUMENTED (High):** Cross-platform Mac + Windows; Windows rewritten to 64-bit native sharing Mac codebase. No Linux. — https://www.mediarealm.com.au/articles/propresenter-7-whats-new/
- **DOCUMENTED (High):** Pricing — ~$399 single seat (incl. 1 yr ProPresenter+ upgrades/support); campus ~$999; upgrade paths ~$275/$675. Multi-seat site licenses (5/15/20) sold via resellers. — https://renewedvision.com/propresenter7/whats-new7/ ; Full Compass/Genesis listings
- **INFERRED (Med):** Role-based permission is delivered via Planning Center collaboration, not a native in-app RBAC system.
- **UNKNOWN:** Native crash-recovery behavior (not documented in reviewed sources).
- **Strengths:** Deepest production feature set, pro AV I/O, PCO ecosystem.
- **Gaps:** Steep learning curve; Mac-first (Windows secondary); higher cost; no Linux. — https://ruahcreativehouse.org/blog/church-presentation-software/

### 2.3 OpenLP
Mature free/open-source church presentation platform.

- **DOCUMENTED (High):** Searchable song + Bible databases; instant projection or saved order-of-service; custom slides. — https://openlp.org/ ; https://manual.openlp.org/introduction.html
- **DOCUMENTED (High):** Bible import (multiple formats) + verse download; search by reference (e.g. "Luke 12:10-17") or phrase. — https://openlp.org/
- **DOCUMENTED (High):** Themes; VLC-based video/audio; PowerPoint & LibreOffice Impress; PDF; image slideshows. — https://openlp.org/
- **DOCUMENTED (High):** Built-in web-browser stage view + web remote; iOS/Android remote apps; change/route content from phone. — https://manual.openlp.org/web_remote.html
- **DOCUMENTED (High):** Cross-platform — Windows, macOS, Linux, FreeBSD; install unlimited copies. — https://openlp.org/
- **DOCUMENTED (Med):** Crash recovery functionality stated on site. — https://openlp.org/
- **DOCUMENTED (High):** Free, no subscription, no user restrictions.
- **INFERRED (Med):** No native multi-user roles/permissions (single-machine app model).
- **Strengths:** Free, broad OS support incl. Linux/BSD, strong Bible tooling, crash recovery.
- **Gaps:** Utilitarian UI; lacks pro AV routing (edge blend/key-fill) and native cloud collaboration/roles.

### 2.4 FreeShow (ChurchApps / Live Church Solutions, 501c3)
Free, open-source, modern presenter aiming to eliminate software cost for churches.

- **DOCUMENTED (High):** Worship lyrics (auto search + slide creation), scripture display, sermon points, countdown timers, media backgrounds — across multiple screens simultaneously. — https://freeshow.app/ ; https://github.com/ChurchApps/FreeShow
- **DOCUMENTED (High):** Stage display for leaders; web output/remote control from any mobile device; live Edit mode to change text mid-presentation. — https://freeshow.app/
- **DOCUMENTED (High):** Native NDI output (no converters); full MIDI command support (advance slides, trigger lighting/external devices). — https://freeshow.app/
- **DOCUMENTED (High):** Templates + drag-drop editor; import PowerPoint, ProPresenter, EasyWorship, OpenSong formats (eases migration). — https://freeshow.app/
- **DOCUMENTED (Med):** Cloud sync / multi-user collaboration across computers. — https://freeshow.app/
- **DOCUMENTED (High):** Windows, macOS, Linux. Free (donor-supported). — https://www.blog.brightcoding.dev/2025/08/25/freeshow-... ; https://freeshow.app/
- **INFERRED (Med):** Multi-user collaboration exists but formal role/permission model unverified.
- **UNKNOWN:** Crash-recovery behavior; permission granularity.
- **Strengths:** Free + modern UX + NDI + MIDI + broad importers → strongest free challenger and easiest migration target.
- **Gaps:** Newer/less battle-tested than ProPresenter; enterprise AV routing (edge blend, key/fill) unproven.

### 2.5 EasyWorship
Commercial, volunteer-friendly Windows/Mac presentation software.

- **DOCUMENTED (High):** Song lyrics, built-in Scripture DB (multi-translation), playlist-based service scheduling with drag-drop; live output preview. — https://easyworship.com/software/features
- **DOCUMENTED (High):** CCLI SongSelect built in (pre-formatted lyrics, automatic copyright reporting). — https://easyworship.com/
- **DOCUMENTED (High):** NDI output for streaming; Presentation Editor for sermon content. — search corpus (easyworship features)
- **DOCUMENTED (High):** Native iOS + Android apps to monitor/control services. — https://easyworship.com/
- **DOCUMENTED (High):** Pricing — Basic $17.50/mo ($210/yr); Premium $27.50/mo ($330/yr); both include a campus license (multiple computers, one location); 30-day trial. Mac + Windows. — https://easyworship.com/software/pricing
- **INFERRED (High):** Positioned as the low-training, Windows-friendly, volunteer-run alternative to ProPresenter. — https://ruahcreativehouse.org/blog/church-presentation-software/
- **UNKNOWN:** Stage-display depth, lower-thirds/timers specifics, permission/roles, crash recovery.
- **Strengths:** Ease of use, CCLI integration, campus licensing, big licensed-song library.
- **Gaps:** Subscription-only; no Linux; less pro AV routing than ProPresenter.

### 2.6 Quelea
Free, open-source (JVM/JavaFX) church projection app.

- **DOCUMENTED (High):** Projects song lyrics, Bible passages, images, video backgrounds, PowerPoint; create/open/save/print schedules; notices management; quick-edit. — https://github.com/quelea-projection/Quelea ; https://quelea.org/
- **DOCUMENTED (High):** Separate stage view showing chords to band (not congregation). — https://quelea.org/
- **DOCUMENTED (High):** Real-time mobile lyrics push to any internet-connected device (user-selectable colors). — https://quelea.org/
- **DOCUMENTED (High):** Bible via Zefania XML; song import from EasyWorship/OpenLP/OpenSong/Survivor/Kingsway; 10+ UI languages; projector calibration test patterns. — https://quelea.org/
- **DOCUMENTED (High):** 100% free, open source, no time/user limits; distributed via Flathub/SourceForge. — https://flathub.org/en/apps/org.quelea.Quelea
- **INFERRED (Med):** Cross-platform (Win/macOS/Linux) via Java runtime; Flathub confirms Linux.
- **UNKNOWN:** Lower thirds, timers, NDI output, permissions, crash recovery.
- **Strengths:** Free, strong importers, chord stage view, mobile lyric push.
- **Gaps:** Java dependency; less active/polished; pro AV I/O unproven.

---

## 3. Adjacent Production / Control Tooling

Focus: output routing, browser source, transparent/lower-third output, control surfaces (MIDI/OSC), and integration relevance to a church presentation app.

### 3.1 OBS Studio (free, OSS)
- **DOCUMENTED (High):** Browser Source renders web-based overlays (chat, alerts, custom graphics) from URLs or local files — a natural integration surface: SelahCue could expose an HTML/URL "lower-third" or "stage" endpoint OBS ingests. — https://ndi.video/product-finder/obs-studio/
- **DOCUMENTED (High):** NDI output via obs-ndi plugin (Tools ▸ NDI Output Settings) publishes Program/Preview to LAN; also broadcast graphics (lower thirds, chyrons) in NDI workflows. — https://streamgeeks.us/how-to-use-ndi-with-obs/
- **DOCUMENTED (High):** Virtual Camera output for Zoom/Teams/YouTube etc. — https://ndi.video/product-finder/obs-studio/
- **DOCUMENTED (Med):** obs-websocket plugin enables external programmatic control (referenced in results; well-known standard for scene/source control). — search corpus
- **INFERRED (High):** Best integration path for SelahCue = emit a transparent Browser-Source URL + NDI feed, and optionally drive OBS scenes via obs-websocket.
- **UNKNOWN:** Native transparent NDI alpha out of OBS without alpha-aware plugin config (transparency generally requires browser-source compositing rather than alpha NDI).

### 3.2 vMix (commercial, Windows-only)
- **DOCUMENTED (High):** Inputs incl. NDI, SRT, cameras, video calls, Zoom, virtual sets, titles. — https://www.vmix.com/software/features.aspx
- **DOCUMENTED (High):** CGI Titles incl. lower-thirds/scoreboard templates; high-quality lower-third graphics. — https://www.vmix.com/software/features.aspx
- **DOCUMENTED (High):** Web Controller (iPad/iPhone/Android/touch) + MIDI controllers + external control systems. — https://www.vmix.com/software/features.aspx
- **DOCUMENTED (High):** Key & Fill output support; alpha NDI where source contains alpha and device supports fill/key. — https://www.vmix.com/help23/KeyFill.html
- **DOCUMENTED (Med):** Multi-output — up to 4 outputs in 4K/Pro, 1 on lower tiers; pricing from ~$60 (Basic HD), no free tier. — vMix pricing/help
- **INFERRED (High):** SelahCue integration path = supply an alpha-capable NDI feed (lyrics/lower-thirds) that vMix keys; or be controlled via vMix's API/Web layer.

### 3.3 Blackmagic ATEM Software Control (free w/ ATEM hardware)
- **DOCUMENTED (High):** Software Control has switcher, audio, macros, media, deck pages; keyers, transitions, media player palettes. — https://www.blackmagicdesign.com/products/atemmini/software
- **DOCUMENTED (High):** Graphics used for titles/bugs/lower thirds; key/fill supported; where NDI source contains alpha and BMD device supports fill+key, fill/key output is possible (often via NDI-to-SDI bridges like NDI Outlet). — https://newbluefx.com/atem-graphics/ ; https://sienna-tv.com/ndi/ndi-outlet.html
- **DOCUMENTED (High):** Macros allow recorded/automated switcher actions synchronized with graphics. — Blackmagic software page
- **INFERRED (High):** SelahCue lyrics/lower-thirds would reach ATEM as a fill+key pair over SDI/HDMI (or NDI→SDI), driven as an upstream/downstream keyer. This is the classic church "lyrics keyed over camera" workflow.

### 3.4 Bitfocus Companion (free, OSS) + Elgato Stream Deck (hardware)
- **DOCUMENTED (High):** Companion turns Stream Deck into a pro shotbox for many switchers/playback/broadcast systems; triggers buttons via OSC, TCP, UDP, HTTP, WebSocket, ArtNet; interacts with other software via MIDI/OSC; includes an emulator + touchscreen webpage (no hardware required). — https://bitfocus.io/companion ; https://companion.free/
- **DOCUMENTED (High):** Elgato Stream Deck = programmable button surface controlled via hotkeys or plugins from the Elgato Marketplace (most free). Modules exist for many production apps. — https://www.elgato.com/us/en/p/stream-deck ; https://marketplace.elgato.com/stream-deck/plugins
- **INFERRED (High):** High-value integration: publishing a **Companion module** (and/or Stream Deck plugin) for SelahCue would let operators trigger slides/scenes/timers from physical buttons — an expected capability in the church-tech ecosystem and a cheap credibility win.
- **DOCUMENTED (High):** ProPresenter and OBS are already commonly controlled via Companion/Stream Deck — sets the integration expectation SelahCue must meet.

### 3.5 NDI Tools (free suite, NewTek/Vizrt)
- **DOCUMENTED (High):** Suite incl. Screen Capture (share desktop as NDI), Studio Monitor (view/verify NDI sources + routing), Virtual Input (NDI→webcam for conferencing), Scan Converter (workstation as multi-source NDI input). — https://docs.ndi.video/all/using-ndi/ndi-tools/ndi-tools-for-windows
- **INFERRED (High):** If SelahCue emits standards-compliant NDI, these free tools give churches monitoring/routing/virtual-cam plumbing "for free," lowering SelahCue's own burden — strong reason to prioritize clean NDI (incl. alpha) output.

---

## 4. Market / Positioning Notes

- **Pricing spectrum:** Free/OSS (OpenLP, FreeShow, Quelea) ↔ subscription (EasyWorship $17.50–$27.50/mo; PewBeam $14–$30/mo freemium) ↔ perpetual-seat + support subscription (ProPresenter ~$399 seat / ~$999 campus). — vendor pages above.
- **Deployment:** All six church products are desktop-installed (no dominant SaaS-only church presenter). FreeShow adds cloud sync; ProPresenter leans on Planning Center (cloud) for collaboration. Self-hosting/offline is the norm and is treated as a reliability feature (PewBeam explicitly markets offline). — corpus.
- **Recurring pain points (DOCUMENTED-Med, review sites):** (1) ProPresenter's steep learning curve + Mac-first bias; (2) volunteer operability — churches want "anyone can run it with minimal training" (why EasyWorship/MediaShout are recommended); (3) cost sensitivity driving free-tool adoption; (4) migration friction — importers (FreeShow) are a decisive switching lever. — https://ruahcreativehouse.org/blog/church-presentation-software/ ; https://theleadpastor.com/tools/church-presentation-software/
- **Emerging frontier:** AI (PewBeam) — live sermon-follow scripture, semantic search, AI slides, live translation, and location-based/Global-South pricing represent the newest competitive axis. — https://technext24.com/reviews/pewbeam-2-0-launch-ai-slides-pewnotes-lumen/
- **Ecosystem expectation:** Serious tools are expected to interoperate with OBS (browser source/NDI/websocket), NDI generally, ATEM (key/fill), and Companion/Stream Deck. Meeting these is table stakes for credibility with tech-forward churches. — corpus.

---

## 5. Differentiation Opportunities for SelahCue

Grounded in the gaps and expectations above:

1. **Volunteer-first UX with pro depth underneath.** The dominant, repeated complaint is ProPresenter's learning curve. A genuinely "any volunteer can run it in 10 minutes" mode — with an opt-in advanced surface — is an open, validated need. (Addresses pain point #2.)
2. **True cross-platform incl. Linux + mobile parity.** ProPresenter and EasyWorship exclude Linux; only OSS tools cover it. A polished commercial-quality app that runs Win/macOS/Linux and offers real mobile operation (not just remote) would be differentiated.
3. **Native, alpha-capable NDI + Browser-Source + Companion module out of the box.** Ship clean NDI (with alpha for key/fill), a transparent HTML lower-third endpoint OBS/vMix can ingest, and an official Bitfocus Companion module + Stream Deck plugin. Most competitors bolt these on; making them first-class is a fast credibility and integration win. (Addresses §3 expectations.)
4. **First-class collaboration + role-based permissions natively.** Only ProPresenter (via Planning Center) approaches multi-role collaboration; most tools are single-machine. Native RBAC (worship leader / operator / designer / admin) with cloud-synced service plans is largely unmet.
5. **Responsible AI assist as a feature, not the whole product.** PewBeam proves demand for AI sermon-follow, semantic scripture, and AI slides — but appears verse-projection-centric. SelahCue can pair AI assistance (auto-cue scripture, AI slide drafts, live translation) with a complete production suite (run sheets, multi-output, stage displays, timers, key/fill), which PewBeam has not proven it has.
6. **Offline-first reliability + crash recovery as an explicit guarantee.** Reliability sells in live services; only OpenLP and PewBeam clearly market recovery/offline. Explicit auto-save, crash recovery, and offline operation would be a trust differentiator.
7. **Migration importers as an on-ramp.** FreeShow shows importers (ProPresenter/EasyWorship/OpenSong) drive switching. SelahCue should import from ProPresenter, EasyWorship, OpenSong, OpenLP, and FreeShow to lower switching cost.
8. **Fair/global pricing.** PewBeam's location-based pricing signals an underserved Global-South market; a tiered/regional model (plus a free tier) could widen reach where ProPresenter's price is prohibitive.

---

## 6. Key UNKNOWNs (require trials, demos, or vendor confirmation)

| # | UNKNOWN | Why it matters | How to resolve |
|---|---|---|---|
| 1 | PewBeam OS/platform matrix (Win/macOS/Linux/mobile) | Determines whether it's a true head-to-head desktop competitor | Install/trial or vendor confirmation |
| 2 | PewBeam presence/depth of stage display, lower thirds, timers, run sheets, roles | Whether it's a full presenter or a verse-projection add-on | Hands-on trial |
| 3 | ProPresenter native crash-recovery / auto-save behavior | Reliability comparison + differentiation claim #6 | Trial + docs/support |
| 4 | ProPresenter native RBAC vs. Planning-Center-only collaboration | Validates differentiation #4 | Trial / support KB |
| 5 | EasyWorship stage-display depth, lower-thirds/timers, permissions, crash recovery | Fill "?" cells in matrix | 30-day trial |
| 6 | Quelea NDI/lower-thirds/timers/crash recovery | Fill "?" cells; assess as free competitor | Install + test |
| 7 | FreeShow permission granularity + crash recovery | Assess strongest free challenger | Install + test |
| 8 | Real-world reliability/latency of PewBeam's live sermon-follow AI | Whether sermon-follow is production-grade or demo-grade | Live-service trial |
| 9 | OBS transparent/alpha NDI output feasibility without browser-source compositing | Affects SelahCue's chosen output architecture (§3.1) | Bench test with obs-ndi |
| 10 | Exact multi-seat/site license terms & renewal costs across paid tools | Competitive pricing positioning | Vendor quotes |
| 11 | Whether any competitor already ships an official Bitfocus Companion module | Sizing differentiation #3 | Search Companion module registry |

---

## 7. Findings Count by Classification

Approximate tally across §2–§3 (per bulleted finding):

| Classification | Count |
|---|---|
| DOCUMENTED | ~41 |
| INFERRED | ~11 |
| OBSERVED | 0 (no hands-on trials; all evidence via public pages/docs/reviews) |
| UNKNOWN | ~11 (see §6) |

> **Access limitation note:** No trials or paid tiers were exercised; findings rest on vendor sites, official docs, and third-party review/directory pages accessed 2026-07-23. "OBSERVED" is intentionally zero because no live product workflow was directly operated. Any capability marked "?" in the matrix or listed in §6 must be confirmed hands-on before SelahCue scoping decisions rely on it.

---

## Sources (primary)

- PewBeam — https://pewbeam.com/ · https://technext24.com/2026/03/23/pewbeam-all-you-should-know · https://technext24.com/reviews/pewbeam-2-0-launch-ai-slides-pewnotes-lumen/
- ProPresenter — https://renewedvision.com/propresenter7/whats-new7/ · https://www.mediarealm.com.au/articles/propresenter-7-whats-new/ · https://www.renewedvision.com/tutorials/how-to-use-timers-countdowns-in-propresenter-7 · https://www.renewedvision.com/tutorials/planning-center-online-integration-collaboration-with-propresenter-7 · https://propresenter7.com/propresenter-remote/
- OpenLP — https://openlp.org/ · https://manual.openlp.org/introduction.html · https://manual.openlp.org/web_remote.html
- FreeShow — https://freeshow.app/ · https://github.com/ChurchApps/FreeShow
- EasyWorship — https://easyworship.com/software/features · https://easyworship.com/software/pricing
- Quelea — https://quelea.org/ · https://github.com/quelea-projection/Quelea · https://flathub.org/en/apps/org.quelea.Quelea
- OBS — https://ndi.video/product-finder/obs-studio/ · https://streamgeeks.us/how-to-use-ndi-with-obs/
- vMix — https://www.vmix.com/software/features.aspx · https://www.vmix.com/help23/KeyFill.html
- ATEM — https://www.blackmagicdesign.com/products/atemmini/software · https://newbluefx.com/atem-graphics/
- Companion / Stream Deck — https://bitfocus.io/companion · https://companion.free/ · https://www.elgato.com/us/en/p/stream-deck · https://marketplace.elgato.com/stream-deck/plugins
- NDI Tools — https://docs.ndi.video/all/using-ndi/ndi-tools/ndi-tools-for-windows
- Market — https://ruahcreativehouse.org/blog/church-presentation-software/ · https://theleadpastor.com/tools/church-presentation-software/
