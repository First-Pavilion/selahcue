# Bible sources and a competitor's delivery model — October 2026

- Date: 2026-10-10 (pages read on 2026-10-09)
- ClickUp: **17tnw2b4p1f** (this note), story **17tnw2b4p1e** (three-tier Bible library)
- Companion decision record: `docs/architecture/adr/ADR-0030-bible-delivery-tiers.md` (Proposed)
- Related: `docs/research/LICENSING-REGISTER.md`, `docs/research/LICENSED-TRANSLATIONS.md`, ADR-0017

## The question

The owner asked two things. First, can SelahCue take Bible versions from BibleGateway, Bible Hub or open.bible, and keep them on the free plan? Second, after seeing how WorshipPro (a competing church presentation product) does it, can SelahCue do the same?

## How to read the labels

Every claim below carries one of these labels, so a reader can tell how far to trust it.

- **VERIFIED** — read on the primary page on the date shown. The pages were read through a page-summarising tool, so re-read the primary text before putting exact wording in a legal document.
- **OBSERVED** — read on a third party's public page. We have not seen any contract behind it.
- **INFERRED** — our reasoning from observations. It could be wrong.
- **UNVERIFIED** — not checked, or the check failed. Listed again at the end.

## Can SelahCue use text from these three sites?

Short answer: BibleGateway and Bible Hub, no. open.bible, yes, under its licence. All three are places to read Bibles. None of them is where SelahCue should get text from; the sources behind them are.

### BibleGateway — no

- **VERIFIED 2026-10-09** ([terms](https://www.biblegateway.com/legal/terms/)): the terms forbid copying, downloading, reproducing, archiving, redistributing and selling site content. They allow quoting up to a stated limit with attribution, which is a rule for quoting in a document, not for shipping text inside a product. They also say the service is for personal use and not for commercial purposes unless the company has approved it.
- **VERIFIED 2026-10-09** ([permission page](https://www.biblegateway.com/support/KA-01408)): public-domain Bibles may be used freely, though public-domain status can differ by country. For copyrighted Bibles the site says it cannot give permission, because it does not own them; the publisher must be asked. It does not say whether software may include the text.
- Consequence: most of what BibleGateway shows (NIV, ESV and so on) is licensed to BibleGateway by publishers and cannot be passed on. The public-domain versions it shows are free to use, but we already get those from eBible.org, so BibleGateway adds nothing.
- This matches the existing register: "reference only, not a bundling source" (`LICENSING-REGISTER.md`).

### Bible Hub — no

- **VERIFIED 2026-10-09** ([terms](https://biblehub.com/terms.htm)): the terms say the site may not be used to provide any content or service in a commercial manner without the site editor's prior written consent. The page does not list which translations the site hosts or their licences.
- Correction recorded for honesty: an early search snippet credited Bible Hub with a Creative Commons licence. That text was from a different site's terms page (png.bible). We discarded it and read Bible Hub's own terms.

### open.bible — yes, with conditions

- **VERIFIED 2026-10-09** ([description of the project](https://scripture-engagement.org/content/open-bible/)): open.bible is Biblica's initiative. Its texts are licensed CC BY-SA (Creative Commons Attribution-ShareAlike). Anyone may copy, adapt and use them for any purpose, including commercially, provided they credit Biblica and release adaptations under the same licence. Files come as USFM, USX, RTF and PDF.
- **UNVERIFIED**: the exact list of languages. The same page lists five (Arabic, Asante Twi, Kiswahili, Luo, Yoruba); another search result said eight (adding Kurdish and Vietnamese). open.bible itself returned an access-denied error to our fetch. No English version appeared in either list.
- **Already in the repo**: our Yoruba, Igbo and Hausa catalogue entries are the same Biblica "Open" editions, taken from eBible.org, marked CC BY-SA 4.0 and still `legal_review: pending` (ticket A6, 17tnw2b2jg3).
- Share-alike is the thing to get right. Our converter changes the text's layout (it strips headings and re-packs it), which is likely an adaptation. Whether share-alike reaches only the converted text or also the app is a question for counsel in A6.

### What to use instead

- **eBible.org** for public-domain, CC0 and CC BY-SA texts, which is what the converter (`scripts/build_translation_catalog.py`) already does.
- **open.bible / Biblica** directly where eBible does not carry a Biblica edition.
- **API.Bible** for licensed versions, subject to the spike B0 (17tnw2b2jg4).

## WorshipPro's published model

All of this is **OBSERVED 2026-10-09** on WorshipPro's own public pages: the [home page](https://worshippro.org/), the [pricing page](https://worshippro.org/pricing) and section 4 of the [terms](https://worshippro.org/terms). We have not seen their contract with any publisher or with API.Bible, and we have not run their app.

Their terms describe three arrangements:

1. **Public domain.** Bundled versions include KJV, WEB, ASV, BBE and YLT, with no restrictions from them.
2. **CC BY-SA 4.0.** Bundled Hausa, Igbo and Yoruba (credited to Biblica) and "a number of versions" in an in-app Bible store. They say these may be used commercially if the displayed attribution is kept and share-alike is respected, and that a Version credits screen lists the required attributions.
3. **Licensed versions through API.Bible.** They name The Message and the New Living Translation (Tyndale House Publishers), the Amplified Bible (The Lockman Foundation) and the Good News Translation (American Bible Society). The rules they pass on to users: use only inside the app; no copying, export or redistribution; no changes to the text; the copyright notice stays visible; a cap on consecutive verses shown at once; versions can be withdrawn and local copies removed; offline copies only where the licence allows and re-checked periodically; and non-personal usage information is reported to API.Bible's Fair Use Management System (FUMS). Some of these versions need an active Pro subscription.

Their home page advertises "1,000+ translations to download on demand", and the pricing page lists "1,000+ Bible translations" under both Free and Pro. So the free plan, as they describe it, includes the open versions; the paid plan unlocks some of the API.Bible versions.

**What they do that we do not yet:** bundle BBE and YLT. Our repo excludes BBE (public domain in the US only; `LICENSING-REGISTER.md`) and our converter allowlist excludes YLT because its eBible source lacks the markup we need.

### Where do their open versions come from?

**INFERRED, moderate confidence: eBible.org.**

- eBible.org's catalogue had 1,551 rows when we checked on 2026-10-04, so a "1,000+" figure is the right size for its redistributable part. No other open source we know of has that many.
- Their Yoruba credit uses the same copyright years (2009, 2017) and owner as the eBible record behind our own Yoruba entry (`assets/catalog.json`).
- Against: API.Bible's open-access tier also carries public-domain and Creative Commons versions, and they use API.Bible for the licensed ones. Both could be true.
- Only watching their app's network traffic would settle it. We have not done that.

## What this means for SelahCue

The reasoning and the proposal are in ADR-0030. In one paragraph: public-domain and open-licensed versions are the same kind of thing and can be free on every plan; licensed versions cost money per version and are the natural paid-plan feature; the work to reach "1,000+" is scale (a rule-based licence gate, a runtime catalogue, rendering many scripts), not a new idea; and the licensed tier is likely but unproven until B0 reports.

## Unverified items (one list)

1. open.bible's current language list (five or eight; fetch was refused).
2. API.Bible's commercial terms for a desktop app: per-version availability (NLT, Amplified, The Message, Good News), per-version fees, offline storage rules, and whether FUMS reporting applies to us. Owner: B0.
3. How many of eBible's 1,551 versions are redistributable, complete, and in which licence classes and scripts. Owner: C1.
4. Which of those scripts our output renderer displays correctly. Owner: C4.
5. Whether charging for, or technically restricting access to, a CC BY-SA text conflicts with the licence (our reading: section 2(a)(5)(C) of CC BY-SA 4.0 bars adding restrictions on recipients). Owner: counsel, via D1.
6. Where WorshipPro's open versions come from, and the terms of their API.Bible agreement.

## Sources

- BibleGateway terms: https://www.biblegateway.com/legal/terms/ (read 2026-10-09)
- BibleGateway permission page: https://www.biblegateway.com/support/KA-01408 (read 2026-10-09)
- Bible Hub terms: https://biblehub.com/terms.htm (read 2026-10-09)
- open.bible description: https://scripture-engagement.org/content/open-bible/ (read 2026-10-09)
- API.Bible licence categories: https://care.api.bible/article/388-how-to-find-copyright-and-public-domain-status-of-bibles (read 2026-10-09)
- WorshipPro: https://worshippro.org/, https://worshippro.org/pricing, https://worshippro.org/terms (read 2026-10-09)
