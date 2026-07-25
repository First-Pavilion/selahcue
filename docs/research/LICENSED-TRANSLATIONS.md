# SelahCue — Licensed Translations Dossier (Track 2 of 86ajpqfyj)

**Research date / access date for all findings: 2026-07-25** · Owner role: Product Researcher · Method: 4-lens web research (primary permissions/terms pages wherever reachable; Cloudflare-blocked pages read via dated 2026 Wayback snapshots and labelled as such) · Discipline per `LICENSING-REGISTER.md`: **OBSERVED / DOCUMENTED / INFERRED / UNKNOWN** + confidence. Contradictory evidence is retained, not silently resolved.

> ⚠️ Due-diligence, **not legal advice**. Nothing here authorizes shipping any copyrighted text. Every licence below must be confirmed by the owner + counsel and/or the rights holder before implementation.

**Question:** the owner wants **NIV, NLT, AMPC, NKJV, TPT, MSG** in SelahCue (a commercial church presentation app). All six are copyrighted and never bundlable gratis. What are the lawful routes, constraints, and costs — and what should we build?

---

## 1. Per-translation dossier

| | Rights holder / licensor | Gratis quotation policy (never covers a full-text app) | Commercial-app route(s) | Key constraints | Class / Conf |
|---|---|---|---|---|---|
| **NIV** | **Biblica** (copyright; electronic rights worldwide) · Zondervan/HarperCollins Christian (NA print) · Hodder & Stoughton (UK/EEC/EFTA) | 500 verses, any form, <25% of work, ≤50% of a Bible book, latest edition only, prescribed notice | **Direct Biblica Standard Publishing License is the ONLY commercial route** (case-by-case royalties, ~10 business days, "generally does not license products still in development"): the verification pass **confirmed NIV is NOT available for commercial use on API.Bible** (it is in the catalog — Bible ID `78a9f6124f344018-01` — but commercial licensing is excluded); Biblica's royalty-free **Express License is non-commercial only** (no sales/ads/monetization, **no AI/ML features**) — SelahCue does not qualify | Biblica restricts offline: audio = streaming-only, "unrestricted download" banned generally; offline TEXT under the Standard License **UNKNOWN** | OBSERVED / High (verification pass 2026-07-25; Biblica page via Wayback 2026-05-07; HCC live) |
| **NLT** | **Tyndale House** | 500 verses **in print or eBook form only** — the gratis grant does NOT extend to electronic display, stricter than the others | **api.nlt.to** with a commercial key ("if your use is commercial, please explain when you sign up"); or API.Bible (NLT listed — DOCUMENTED/Med); or direct via permission@tyndale.com / the Permissions Questionnaire | Anonymous/standard api.nlt.to tiers are non-commercial (50 verses/req, 500/day anon; 500/req, 5 000/day keyed); church screen-projection carve-out ("initials NLT") covers the church's use, not a vendor shipping text | OBSERVED / High (tyndale.com via Wayback 2026-05-18; api.nlt.to live) |
| **AMPC** | **The Lockman Foundation** (AMPC = 1954–1987 notices; AMP 2015 same policy — the licensing difference is essentially which notice/abbreviation, AMPC vs AMP) | **1 000 verses**, any form, ≤50% of work, no complete book, **and ≤1 000 verses in an electronic retrieval system** — so a full-text app always needs written permission | Written grant via Lockman's **Permission to Quote Request Form** (postal declaration; no published program/fees). Lockman demonstrably licenses software vendors (e-Sword, Olive Tree, Accordance, Logos, Bible Hub… per lockman.org/digital) — an established path. AMPC on API.Bible: **UNKNOWN** (catalog mentions "Amplified", edition unspecified) | Apps must show the full notice with a clickable lockman.org link; slides may use "AMPC" abbreviation; "Amplified" is a USPTO trademark | OBSERVED / High (lockman.org live) |
| **NKJV** | **Thomas Nelson / HarperCollins Christian** | 500 verses, any form, <25%, ≤50% of a book, prescribed notice | **HCC Rights & Licensing Division** ("applications for smart devices" — a digital route exists, terms unpublished); or **API.Bible** (NKJV named in the primary docs) | Church screen-projection gratis right belongs to the church, not the vendor | OBSERVED / High (HCC live) |
| **TPT** | **Passion & Fire Ministries** (copyright) · **BroadStreet Publishing** (administers permissions) | 500 verses, any form, ≤20% of work, no complete book; church projection carve-out ("TPT" initials) | **Direct BroadStreet licence only** — no aggregator found offers TPT (absent from API.Bible's public catalog mentions). Precedent exists: TPT's own site logos Proclaim, EasyWorship, BigScreen, ProPresenter as licensed presentation software | ⚠️ **Stability + reputational risk**: removed from Bible Gateway (Jan 2022, no public reason); text under an "expanded review process" — NT frozen at the 2020 edition, full Bible estimated **2029**; scholarly criticism as an interpretive paraphrase; 2026 reporting urging platforms to drop it amid plagiarism allegations. **Contradiction retained:** the YouVersion version page (1849) was OBSERVED live 2026-07-25, while one 2026 report was read by a second lens as YouVersion/Logos removal — the live page is authoritative today; monitor | OBSERVED / High (thepassiontranslation.com/permissions + church-presentation-software pages) |
| **MSG** | **NavPress** (Tyndale alliance — "permissions will be granted from Tyndale on behalf of NavPress") | 500 verses **print or eBook**, <25%, no complete book | Tyndale-administered **Permissions Questionnaire** (navpress.com/permissions/form); "projects produced for sale … may be accompanied by a fee" — no published program; or API.Bible ("The Message" listed — DOCUMENTED/Med). EasyWorship sells MSG at $29 and MediaShout bundles it, so vendor licensing demonstrably happens | "Online platforms/audio" routed through the questionnaire | OBSERVED / High (navpress.com live) |

**Common structure (INFERRED/High):** every publisher converges on (1) a gratis quotation threshold a full-text app always exceeds, (2) **no published software-licensing fee schedule**, and (3) a case-by-case written-permission route. Nobody licenses "in development" products readily — requests go in with a finished, describable product.

## 2. Aggregators compared

| Aggregator | Legal commercial path to the six? | Terms (2026-07-25) | Class / Conf |
|---|---|---|---|
| **API.Bible** (American Bible Society; scripture.api.bible → api.bible) | **Yes — the only aggregator with any lawful commercial path — but NOT for NIV** (verified: NIV is in the catalog yet **excluded from commercial use**). NKJV OBSERVED in catalog; NLT/MSG/"Amplified" DOCUMENTED; AMPC edition + TPT: not found | **Starter $0**: 3 copyrighted Bibles, strictly non-commercial (no ads/fees/freemium/upsells). **Pro from $29/mo**: 150k calls/mo, overage "may be" $1/1k (charged per 1k), copyrighted translations individually licensable **from $10/mo each, tiered by application user count ($10 @ 5k users → $250 @ 100k+)**; "not all Bibles are available for all uses" (NIV = the confirmed commercial exclusion). **FUMS** usage reporting mandatory for webapps (store-distributed mobile exempt; a Tauri desktop app's status **UNKNOWN**). **Caching**: the binding T&C rule is refresh **at least every 30 days** (api.bible/faq agrees); the docs additionally *recommend* clearing every ≤14 days — a stricter advisory, not a conflicting mandate; offline/stored use requires "industry-standard DRM"; delete within 72h of subscription end. Attribution: per-slide abbreviation + a full copyright page | OBSERVED / High (verification pass 2026-07-25) |
| **Biblia API** (Faithlife) | **No** — PD/Faithlife texts only; terms prohibit use in a product competing with Logos (Proclaim competes with SelahCue) and prohibit extraction | OBSERVED / High |
| **Bolls** (bolls.life) | **No** — technically serves NIV/NLT/NKJV/MSG/AMP keyless, but publishes zero licensing/permission statements and grants no commercial licence; treating it as a lawful source would be indefensible | OBSERVED (catalog) + INFERRED (no authorization) / High |
| **Free Use Bible API** (bible.helloao.org) | **No** — verified via its `available_translations.json`: 1 256 translations, all open/PD; none of the six present | OBSERVED / High |

## 3. What comparable products do (observed 2026-07-25)

- **ProPresenter** (Renewed Vision): 67 free translations (mostly PD, plus some copyrighted-but-free via publisher partnerships — corrected by the verification pass from "70+ PD"); **any paid Bible = $15 USD per licence, in-app, licensed per computer** ("10 computers … 10 licenses"; no subscription mentioned, "one-time" not stated verbatim). OBSERVED/High.
- **EasyWorship**: in-app Bible store; NIV 2011 / NKJV / ESV / MSG at **$29** (some $39), tied to an account login. Zondervan withdrew NIV 1984 — publishers control which editions vendors may sell. OBSERVED/High (+ DOCUMENTED for the 1984 withdrawal).
- **Proclaim** (Faithlife): 60+ Bibles ship with the product; more ride the **Logos ecosystem entitlement** (any digital Bible you own appears in Proclaim). DOCUMENTED/High (support article via mirror; live page 403).
- **MediaShout**: markets **24 copyrighted Bibles bundled at no extra charge** on the $499 Site licence (46 PD on the $399 Single) — royalties absorbed in the product price. OBSERVED/High (vendor marketing, labelled).
- **OpenLP** (FOSS): refuses to ship licensed texts ("not allowed to redistribute … without prior permission"); users import their own or use web sources. OBSERVED/High.
- **FreeShow** (FOSS): ships **no texts**; streams from **API.Bible** with an embedded free key + user-supplied imports ("make sure you have the proper rights"). OBSERVED/High (source code read).
- **VideoPsalm** (freeware): distributes copyrighted translations in an online library with **no published licensing basis** — an anti-pattern we must not copy. OBSERVED (what the pages omit) / UNKNOWN (their basis).

**Dominant industry pattern (INFERRED/High):** commercial products sell copyrighted translations as **one-time per-translation in-app purchases (~$15–$39) tied to a vendor account**, per-computer where stated; PD is always free. FOSS products either refuse or delegate to API.Bible/user-supplied.

## 4. Recommendation (for the owner — decision required, not made here)

1. **Architecture now (no licence needed):** land **ADR-0017**'s `TranslationProvider` seam so any of the routes below is an adapter, not a re-architecture. Bundled PD stays the offline core.
2. **Fastest lawful route — API.Bible Pro** for **NKJV (+ NLT/MSG/AMP pending catalog confirmation)** — but **NOT NIV**: the verification pass confirmed **NIV is excluded from commercial use on API.Bible**, so **NIV requires the direct Biblica Standard Publishing License** (case-by-case royalties; Biblica prefers finished products — apply post-MVP). API.Bible: $29/mo + $10–$250/mo per translation tiered by user count, FUMS + the binding 30-day cache-refresh rule enforced by the provider adapter. **Before committing:** confirm with support@api.bible (a) per-version *commercial* availability for NKJV/NLT/MSG, (b) AMPC-vs-AMP edition, (c) whether a Tauri desktop app is a "webapp" for FUMS. Licensed translations will be **online-mostly** (bounded, refresh-bound caching only) — a product expectation to set.
3. **Longer-term — the industry-standard in-app Bible store** (per-translation one-time purchase, ProPresenter-style) via **direct publisher licences** (Biblica standard license; HCC licensing division; Tyndale questionnaire ×2 for NLT/MSG; Lockman form). Case-by-case royalties, unpublished; publishers prefer finished products — apply post-MVP with the shipped app.
4. **TPT: direct BroadStreet only**, and flag the **stability/reputational risk** (Bible Gateway removal, text mutating until ~2029, 2026 plagiarism controversy) — recommend the owner explicitly re-confirm wanting TPT before spending licensing effort.
5. **AMPC:** confirm on API.Bible; else the Lockman form (an established software-vendor path).
6. **Always:** a **user-supplied import** provider (OSIS/Zefania/USFM) for users holding their own licences — zero licensing cost, honest responsibility note (OpenLP/FreeShow pattern).

## 4b. Offline access without bundling (owner refine, verified 2026-07-25)

**Owner question:** can users download the other versions themselves — not bundled — for offline access?

**Answer: yes for offline, no for user-sourced downloads.** Two verified facts shape this:

1. **There is no lawful public download source** for NIV/NLT/AMPC/NKJV/TPT/MSG module files an end user could import. Retail digital copies are **app-locked**: eStudySource (the sole licensed NIV source for e-Sword) states resources "must be opened and read with the software for which they were designed"; Olive Tree's EULA prohibits copying/distribution (5-device limit); Logos content is licensed-not-sold with no redistribution. Sites offering "free NIV modules" are unlicensed — a user download from them is an infringing copy, and owning a print Bible confers no digital-copy right. **OBSERVED/High** (estudysource.com/help, olivetree.com/eula; Logos DOCUMENTED via excerpts). The user-supplied import route therefore only genuinely serves users who hold their own licence or open-licensed texts.

2. **The lawful offline path is download-on-purchase/entitlement under SelahCue's own licence** — exactly the comparable-product model:
   - **EasyWorship (CONFIRMED/OBSERVED):** purchased Bibles "automatically download and install"; a dedicated **"Installing Bibles With Offline Registration"** flow lets users download the purchased Bible on another machine, carry it by USB, and install on a **never-online computer**. Purchased licensed Bibles are demonstrably local, offline-usable files.
   - **ProPresenter (corrected nuance):** "Internet access is required in order to purchase **and install**"; neither article *states* offline use afterwards — consistent with local storage, but INFERRED, not OBSERVED.
   - **API.Bible (CONFIRMED/OBSERVED — conditional permission, not prohibition):** T&C §11 opens "**If you store** API.Bible Content … offline, you must keep it up to date" — offline storage is permitted **provided**: industry-standard **DRM** restricting copying/distribution (§12), a **100-verse print cap**, territory + declared **device limits**, a **30-day update check** (24h on request), and content **removal within 72 hours** of a terminated subscription (§10). (Precision: 72h is the termination-deletion window; 30 days is the refresh-check interval.)

**Implication for SelahCue (feeds ADR-0017):** licensed translations can be **offline after activation** — the app (not the user) downloads the text under its licence into an **encrypted, app-locked local store** honouring DRM/refresh/deletion/device conditions. "Not bundled" = not in the installer and gated behind per-translation entitlement; thereafter Sunday morning works with the network down. This holds under either route (API.Bible per its §10–12, or direct publisher licences per negotiated terms — EasyWorship proves publishers do grant it).

## 5. Unknowns → exact resolution paths

1. ~~Whether NIV commercial is excluded on API.Bible~~ **RESOLVED (verification pass 2026-07-25): NIV is excluded from commercial use.** Remaining: per-version commercial availability + exact tier pricing for **NKJV/NLT/MSG/AMP** → free account + authenticated versions table, and support@api.bible.
2. **AMPC on API.Bible** (edition) → support@api.bible; else Lockman form.
3. **Offline TEXT storage** under Biblica's Standard Publishing License → biblica.com/permissions/contact.
4. **NKJV digital-product terms/fees** → HCC Rights & Licensing Division (domestic-licensing form).
5. **NLT/MSG commercial fees** → api.nlt.to signup (explain commercial use) / permission@tyndale.com.
6. **AMPC/AMP full-text electronic licence cost** → Lockman Permission to Quote Request Form, (714) 879-3055.
7. **TPT licensing for software** → BroadStreet Publishing directly; no public program.
8. **FUMS applicability to a Tauri desktop app**; Starter rate-limit discrepancy (5k/day vs 5k/month) → support@api.bible in writing. ~~Cache 14-vs-30-day conflict~~ **RESOLVED: 30 days is the binding T&C rule; 14 days is a documentation recommendation.**
9. Cloudflare-blocked pages (biblica.com, tyndale.com) verified via May-2026 Wayback snapshots → recommend one manual browser re-read before signing anything.

## 6. Cross-references

- `LICENSING-REGISTER.md` — §1 table updated 2026-07-25 with TPT + AMPC rows and AMP corrections (1 000-verse policy).
- `docs/architecture/adr/ADR-0017-translation-providers.md` — the provider seam this dossier informs.
- ClickUp: story 86ajpqfyj (Track 2); follow-up tickets: owner licensing decision; provider implementation.
