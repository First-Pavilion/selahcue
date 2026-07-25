# Research Review — Batch 7aq (licensed-translations spike + provider ADR)

- **Scope:** story `86ajpqfyj` Track 2 — the owner's requested copyrighted translations (NIV, NLT, AMPC, NKJV, TPT, MSG). A research spike + architecture ADR; **no code**. Executed via the `/goal` engine (`TASK-86ajpqfyj-licensed-translations-spike.md`, validator `--require-complete` PASS, 5/5).
- **Method:** a 4-lens Workflow research fan-out (`wf_b038fdfb-839`: TPT/AMPC rights · API.Bible commercial specifics · direct publisher routes · comparable products; 140 web tool calls, primary sources wherever reachable, Cloudflare-blocked pages via dated 2026 Wayback snapshots) → synthesis → an **adversarial verification pass** (`wf_e9bd0579-d32`: 6 fact-checkers re-fetching the primary sources of the load-bearing claims). No self-approval.

## Deliverables

| Artifact | Content |
|---|---|
| `docs/research/LICENSED-TRANSLATIONS.md` | Per-translation dossier (rights holder · routes · constraints · costs where public, all classed + dated) · aggregator comparison · 7 comparable products · phased recommendation · unknowns with exact resolution paths |
| `docs/architecture/adr/ADR-0017-translation-providers.md` | The pluggable `TranslationProvider` seam (Proposed; acceptance gated on the owner's route decision) |
| `docs/research/LICENSING-REGISTER.md` | TPT + AMPC rows added; NIV/AMP/MSG rows refined with the verified specifics |
| ClickUp | DECISION `86ajpzb09` (owner + counsel: route/budget, incl. re-confirming TPT) · STORY `86ajpzb0c` (provider implementation, waiting_on the decision) |

## Verification pass — 6 load-bearing claims, 4 CONFIRMED + 2 CORRECTED (0 unverifiable)

| Claim | Verdict | Outcome |
|---|---|---|
| Lockman 1,000-verse policy incl. the electronic-retrieval cap | **CONFIRMED** (verbatim) | + nuance recorded: the slide-abbreviation allowance is for *not-for-sale* digital media |
| API.Bible tiers/FUMS/caching | **CORRECTED** | **Headline: NIV is verifiably EXCLUDED from commercial use on API.Bible** (upgraded from an untraced Low-confidence snippet to OBSERVED/High) → NIV's only commercial route is the direct Biblica Standard Publishing License; also: 30-day cache refresh is the binding rule (14 days is a docs *recommendation*, not a conflict); per-translation tiers pinned ($10 @ 5k users → $250 @ 100k+) |
| NLT gratis grant = print/eBook only | **CONFIRMED** | the strictest of the six; api.nlt.to tiers non-commercial |
| TPT status (BroadStreet; Bible Gateway removal; YouVersion live; ~2029 completion) | **CONFIRMED** | the cross-lens YouVersion contradiction resolved in favour of the live page; risk profile stands |
| ProPresenter $15-per-computer model | **CORRECTED** | $15/licence-per-computer confirmed verbatim; "70+ PD free" → 67 free translations (not all PD); "one-time" unsupported |
| Biblica Express (non-commercial only) vs Standard Publishing License | **CONFIRMED** | incl. worldwide electronic rights routing to Biblica and the no-AI/ML Express clause |

All corrections were applied to the dossier and register before this record.

## What the owner now knows (decision-ready)

1. **None of the six can be bundled** — every gratis policy caps far below a full text (500 verses; Lockman 1,000 incl. an electronic-storage cap).
2. **API.Bible is the only lawful aggregator** — viable for **NKJV (+ NLT/MSG/AMP pending catalog confirmation)** at $29/mo + $10–250/mo per translation (user-count tiers), FUMS + 30-day cache refresh, online-mostly. **NIV is excluded from commercial use there.**
3. **NIV = direct Biblica only** (Standard Publishing License, case-by-case royalties, prefers finished products → post-MVP application).
4. **The industry pattern** is a per-translation in-app Bible store ($15–$39, per computer) built on direct publisher licences — the long-term shape.
5. **TPT = direct BroadStreet only**, with documented stability/reputational risk — the DECISION ticket asks the owner to explicitly re-confirm wanting it.
6. **User-supplied imports** are the zero-licence fallback (OpenLP/FreeShow pattern).
7. **ADR-0017** makes all of these adapters behind one seam — zero client changes, licence constraints enforced structurally.

## Residual unknowns (all with exact resolution paths in the dossier §5)

Per-version commercial availability/pricing for NKJV/NLT/MSG/AMP on API.Bible; AMPC edition availability; offline-TEXT terms under Biblica's Standard License; NKJV/NLT/MSG/AMPC direct-licence fees (unpublished — contact paths recorded); FUMS applicability to a Tauri desktop app; a manual browser re-read of the two Cloudflare-blocked pages before signing anything.
