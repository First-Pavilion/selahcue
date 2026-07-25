# ADR-0017 — Pluggable translation providers (bundled PD + licensed remote)

- Status: Proposed (accepting is gated on the owner's licensing-route decision — see docs/research/LICENSED-TRANSLATIONS.md)
- Date: 2026-07-25
- Confidence: High (seam) / Medium (remote-provider specifics, pending the chosen licensor)
- Owner: Software Architect (+ Product Researcher for the licensing constraints)
- Supersedes/relates: relates ADR-0007 (persistence), the 7ae host-advertised-translations wire surface, batch 7ai key storage
- Raised by: story 86ajpqfyj Track 2 (owner request: NIV, NLT, AMPC, NKJV, TPT, MSG)

## Context

`selahcue-scripture` today is **bundled-PD-only**: a static `Translation` enum (KJV/WEB/WEBBE/ASV/Darby) over gzipped TSV corpora compiled into the binary, decoded lazily once, and served through synchronous free functions (`chapter_in`, `passage_text_in`, `search_in`, …). The host advertises its translation list on the wire (batch 7ae), and every client (operator webview, Flutter controller) offers **only** what the host advertises.

The owner wants NIV, NLT, AMPC, NKJV, TPT, and MSG. Per `docs/research/LICENSING-REGISTER.md` (and the Track-2 dossier), all six are **copyrighted and never bundlable**; the lawful routes are a licensed **remote API** (e.g. API.Bible's copyright-protected tier) or **user-supplied** text under the user's own licence. Licensed-API terms impose constraints PD text never had: **no offline persistence by default**, **usage reporting** (e.g. API.Bible FUMS), **mandatory attribution lines**, quotas, and per-version approval. Hard-wiring any one licensor into the scripture crate would couple the product to a single commercial contract and make every new translation a re-architecture.

## Decision

Introduce a **`TranslationProvider` seam** in the host (desktop) — clients are untouched:

1. **The trait.** A provider supplies: `descriptor()` (code, display name, licence class `Bundled | LicensedApi | UserSupplied`, required **attribution line**, `offline_capable: bool`) and fallible content operations mirroring today's surface — `chapter(&Reference)`, `passage(&Reference)`, `search(query, limit)` — returning a closed error taxonomy: `NotFound | NotLicensed | Offline | QuotaExhausted | ProviderError`. The existing bundled corpus becomes `BundledProvider` (infallible, offline, attribution-free), preserving current behaviour byte-for-byte.
2. **The registry.** The host composes providers at startup: bundled always; remote providers only when configured with credentials. The **host-advertised translation list is the union of currently-AVAILABLE translations** — the 7ae wire surface is unchanged, so the operator webview and the mobile controller need **zero changes**: a licensed translation appears in their pickers exactly like a bundled one.
3. **Licence-honouring cache policy, per provider.** Bundled = compiled-in (permanent). LicensedApi default = **in-memory, session-bounded cache only** (bounded LRU by chapter, fixed capacity, per the no-unbounded-growth rule). **Licensed offline store (verified lawful, owner refine 2026-07-25):** where the licence grants stored/offline use — API.Bible's T&C §10–12 explicitly permit it conditionally, and the EasyWorship precedent proves publishers grant it — a provider may declare `offline_capable` and persist its text into an **encrypted, app-locked local store** that structurally honours the licence conditions: DRM-style copy/export prevention (the store is keyed via the OS keychain, unreadable outside SelahCue), a **print/export cap** hook (e.g. API.Bible's 100-verse print limit), **device-entitlement binding**, a **refresh check at least every 30 days** (updating/deleting content to mirror the source, within 24h on request), and **full removal within 72h** of licence/subscription termination. This is the download-on-purchase model: not bundled (not in the installer, gated behind per-translation entitlement), but fully offline for the service after activation. UserSupplied = stored like a bundle, flagged with the user's own responsibility notice — and the UI must be honest that there is **no lawful public download source** for the major copyrighted translations (retail digital copies are app-locked), so this route serves users holding their own licences or open texts.
4. **Usage-reporting hook.** Content responses may carry an opaque `usage_token`; the presenter fires a `displayed(token)` event when the verse actually reaches the Live output. Providers that require reporting (FUMS) consume these events; providers that don't ignore them. Reporting is fire-and-forget and never blocks presentation.
5. **Attribution surface.** The provider's required copyright line is part of the content response; the slide composer renders it on the output (small, canonical position) and the console shows it in the browser. Bundled PD providers return none.
6. **Honest degradation.** A remote provider that is offline / out of quota / unlicensed **drops its translations from the host-advertised list** (or marks them unavailable), so clients can never stage what the host can't serve — the same version-safety contract as 7ae. Content already on the Live output is untouched (no blanking, NFR-024). Scripture commands against an unavailable translation are denied with the true cause (`Offline`/`QuotaExhausted` map to an honest operator message, never a silent empty result).
7. **Sync command layer, async fetch.** The controller's command handling stays synchronous. Remote providers sit behind a host-side **prefetch + cache facade**: a chapter request against a cold cache returns an honest "fetching…" status (a new, additive reply state) and triggers the async fetch; the operator's next poll (the console already polls) serves it from cache. No event-loop or wire-protocol redesign.
8. **Credentials.** API keys live in the OS keychain via the batch-7ai key infrastructure — never in the SQLite store, never in plaintext config, never logged.

## Options considered

- **(Chosen) Provider seam behind the existing host surface.** Pros: clients unchanged; each licensor is an isolated adapter; licence constraints (cache/reporting/attribution) are per-provider policy, not global rewrites; PD behaviour untouched. Cons: an async-fetch facade and a new "fetching" status.
- **Hard-wire API.Bible into selahcue-scripture.** Rejected: couples the crate to one commercial contract; every future licensor is another rewrite; bundled-vs-remote semantics (offline, attribution) get tangled in one code path.
- **User-supplied modules only (no remote API).** Rejected as the *only* route: highest friction for the owner's actual ask; but it remains a supported provider class for users who hold their own licences.
- **Bundle licensed text under a negotiated redistribution licence.** Rejected for now: no publisher offers app-bundle redistribution at accessible terms (register/dossier); revisit only if a direct publisher deal materialises.

## Consequences

- **Positive:** licensed translations become an adapter + a contract, not a re-architecture; clients (webview, Flutter) require zero changes; licence compliance (no offline persistence, reporting, attribution) is enforced structurally, per provider; the PD offline core keeps working with the network down — the show goes on.
- **Negative:** licensed translations are **online-only by default**, and fully offline only after a per-translation entitlement + licensed download (the encrypted offline store) where the licence grants it; a new "fetching" reply state must be added additively (skip-if-none, fixtures preserved); quota/report failures need surfacing in the console's status line; the offline store adds refresh-check + revocation obligations the implementation must honour.
- **Commits us to:** keeping the bundled PD path fully offline and first-class; a bounded in-memory cache; keychain-held credentials; and the honest-degradation rule (unavailable translations disappear from the advertised list rather than failing silently).

## References

- `docs/research/LICENSING-REGISTER.md` + `docs/research/LICENSED-TRANSLATIONS.md` (Track-2 dossier: routes, constraints, recommendation).
- Batch 7ae (host-advertised translations, version safety), batch 7ai (keychain), NFR-024 (never blank live output), the no-unbounded-growth rule.
- ClickUp: 86ajpqfyj (story), follow-up implementation + owner-decision tickets.
