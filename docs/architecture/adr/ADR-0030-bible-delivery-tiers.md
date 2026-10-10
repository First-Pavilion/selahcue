# ADR-0030: Three-tier Bible delivery — public domain bundled, open-licensed on demand and free on every plan, licensed versions on paid plans

- Status: Proposed — waits on the owner's decision D1 (ClickUp 17tnw2b4p1h) for the free/paid split, and on the API.Bible spike B0 (ClickUp 17tnw2b2jg4) before the licensed tier is real
- Date: 2026-10-10
- Confidence: High that tiers 1 and 2 are feasible (built or ticketed). Medium that tier 3 is feasible (unproven until B0). Low on whether a CC BY-SA text may be put behind a paywall (counsel's question).
- Owner: Software Architect
- Related: ClickUp story **17tnw2b4p1e**, this record **17tnw2b4p1f**; ADR-0017 (translation providers, Proposed), ADR-0021 (entitlement leases), ADR-0027 (plan catalogue); `docs/research/BIBLE-SOURCES-AND-COMPETITOR-MODEL-2026-10.md` (the evidence and its confidence labels); `docs/research/LICENSED-TRANSLATIONS.md`; `docs/research/LICENSING-REGISTER.md`

## Context

- SelahCue bundles five public-domain versions (KJV, WEB, ASV, WEBBE, Darby). A1 and A2 of story 17tnw2b2jfv (merged) turn eBible.org text into pinned, normalised assets and load them at run time. A3 to A7 and B0 are ticketed. That work covers a curated handful: BSB, Yoruba, Igbo and Hausa.
- Nothing ties a Bible version to a plan. The plan catalogue grants devices, outputs, NDI, speech-to-text minutes and a watermark; none is for Bible versions. No decision-log entry says which versions are free or paid.
- A competing product, WorshipPro, publishes terms that describe three kinds of version: public domain, CC BY-SA, and licensed versions delivered through API.Bible with some behind its paid plan. It advertises "1,000+ translations to download on demand" on its free plan. What we know of it is labelled OBSERVED in the research note; we have not seen its contracts.
- Three sites the owner asked about (BibleGateway, Bible Hub, open.bible) are reading sites. The first two forbid reuse; open.bible is a real CC BY-SA source. The sources to build on are eBible.org, Biblica's open editions and API.Bible.

## Decision (proposed)

SelahCue delivers Bible versions in three tiers. The tiers are defined by who holds the rights and what it costs us, not by popularity.

**Tier 1 — public domain, bundled.**
- Source: eBible.org exports. Shipped inside the installer. Works with no network.
- Plans: every plan. Today's five versions. A version whose public-domain status holds in only some countries (BBE) stays out unless the owner decides otherwise.

**Tier 2 — open-licensed, downloaded on demand.**
- Source: eBible.org and Biblica's open editions, in classes we may redistribute commercially: public domain, CC0, CC BY, CC BY-SA. Never non-commercial, no-derivatives or all-rights-reserved texts.
- Delivery: a SelahCue-hosted mirror of normalised, SHA-256-pinned assets (story 17tnw2b2jfv), behind a licence gate that must pass before a version is offered. The user reads the licence and attribution and accepts before download.
- Plans: **proposed free on every plan.** These texts cost us nothing to license, and CC BY-SA texts should not carry extra restrictions.
- To reach 1,000+ versions the work is scale, not a new idea: a rule-based licence gate (C2), a runtime signed catalogue (C3), a script-support decision (C4) and a catalogue browser (C5), all fed by a census of what is lawful (C1).

**Tier 3 — licensed versions through API.Bible.**
- Candidates: NLT, Amplified, The Message and Good News, to be confirmed by B0. NIV is not available this way (Biblica licenses it directly) and is out of scope.
- Delivery: the platform API holds the API.Bible key, checks the plan, and issues time-limited download leases (L2). The desktop stores the text encrypted and app-locked, with the publisher's refresh and removal rules (L3). Usage is reported where API.Bible requires it, with no personal data.
- Plans: **proposed paid plans only**, because each licensed version has a monthly cost to us (about $29 plus $10 to $250 per version according to the research doc, to be confirmed by B0). Which paid plan is waiting on ADR-0027's Core and Pro values.
- Entitlement is a per-plan list of version codes in the signed manifest (L1), enforced by the client even offline.

## Options considered

For the tier 2 plan policy (decision D1):

- **(A) Open versions free on every plan; licensed versions paid.** Proposed. Matches cost (open is free to license, licensed is not) and the competitor's published split.
- **(B) Every download needs an account, no plan difference.** Simple, but gives away the one feature that carries a real per-version cost.
- **(C) Some open versions reserved for paid plans.** Highest legal risk: CC BY-SA 4.0 appears to bar adding restrictions on recipients (section 2(a)(5)(C), our reading), and a paywall or DRM on the text itself may do that. Charging for the app or for licensed text is a different matter. Counsel confirms.

For the catalogue mechanism:

- **Compile-time catalogue** (today): every asset pinned in the build. Safe, but a new version needs a release, and a licence takedown cannot be acted on without one.
- **Runtime signed catalogue** (C3): the app fetches a signed manifest, falls back to the embedded one, and honours a `withdrawn` state. Needed at scale and for takedowns. Preferred once built.

## Consequences

- The free plan can honestly say it includes open-licensed Bible versions. Marketing and the Terms (section 9.3) must not name licensed versions until B0 confirms them (L4).
- Licensed text brings obligations open text does not: publisher notices, verse caps, no export, withdrawal, and likely usage reporting to API.Bible. The Privacy draft must say what is reported (L4).
- Rendering 1,000+ versions means many writing systems. Some may not display correctly on the output screen; C4 decides whether to hide, warn, or fix.
- Each tier fails differently: a tier 2 gate failure means a version is not offered; a tier 3 lease failure never interrupts what is already live on the output.
- Memory stays bounded: a capped number of decoded versions in memory at a time, with a test that fails when the cap is removed.

## Open questions

1. **D1 (owner, counsel):** the free/paid policy, which paid plan, and the CC BY-SA gating question.
2. **B0 (research):** which licensed versions API.Bible's commercial terms allow us to deliver offline, at what cost, with what usage reporting.
3. **C1 (research):** how many eBible versions are lawfully mirrorable.
4. **C3 (owner):** what happens to an installed copy of a withdrawn version — keep serving it, warn, or stop at next launch. On 2026-10-05 the owner accepted keep-serving for the current release only.
5. **A6 (counsel):** how CC BY-SA share-alike applies to our converted texts and to the app.

## What this does not change

- Quote detection stays KJV-only.
- The first curated set and its tickets under 17tnw2b2jfv are unchanged.
- No version is published to the translations bucket until the owner says so; only BSB is legally cleared today.
- ADR-0017 and `docs/research/LICENSING-REGISTER.md` are not edited here; ticket A6 owns them and will fold this in.
