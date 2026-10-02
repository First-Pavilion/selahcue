# Legal drafting notes — SelahCue platform Privacy Policy and Terms of Service

> **DRAFT — NOT LEGAL ADVICE — REQUIRES REVIEW BY A QUALIFIED LAWYER BEFORE PUBLICATION**
>
> Internal working notes. Not for publication. Version 0.3, 2026-10-01, prepared by an AI drafting
> assistant (not a lawyer). Review status: **Draft — placeholders and launch-readiness conditions must
> be cleared.**

> **HARD LAUNCH GATE.** Both policies (v0.3) describe SelahCue as it will operate at launch, in the
> plain present tense. Many of the features they describe are not built today. **Publishing either
> policy while any row marked "Gate" in §4 is unsatisfied would make the policy false**, exposing
> SelahCue to misrepresentation claims. Every "Gate" row must be satisfied, and every
> `{{PLACEHOLDER}}` filled, before either document is published. Rows marked "Deferred" are accepted
> risks under the owner's decision of 2026-10-01 (§7); they do not block publication because the
> policies no longer claim them.

## 1. Matter profile

| Item | Value |
|---|---|
| Brand | SelahCue |
| Contracting legal entity | **Unknown** — `{{LEGAL_ENTITY_NAME}}`. Owner described as First Pavilion (firstpavitech.com), Lagos; the exact entity, its registration and its relationship to the SelahCue brand are not confirmed anywhere in the repository. |
| Documents | `docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md` (v0.3), `docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md` (v0.3), this file (v0.3) |
| Requested by | Repository owner, via the coordinating agent; ClickUp delivery ticket `17tnw2b0q93`; PR #133 |
| Audience | Churches and other organisations worldwide; the staff and volunteers who create accounts; website visitors |
| Legal posture | **Generic** (owner decision 2026-10-01): no regulator-specific citations, registrations or filings claimed; see §7 |
| Jurisdictions analysed | Nigeria (NDPA 2023, GAID 2025); EU GDPR; UK GDPR/DPA 2018/PECR as amended by DUAA 2025; US (CCPA, COPPA). Kept in §10 for counsel. |
| Existing documents kept unchanged | `docs/legal/PRIVACY.md` and `docs/legal/TERMS.md` (SelahCue Controller mobile app) |

## 2. Revision history

- **v0.1 (2026-10-01).** First drafts. Features that were designed but not built sat in feature-gated
  blocks inside the policies.
- **v0.2 (2026-10-01).** Owner direction: write for the launch state in plain present tense; full
  billing section; every launch-dependent statement tracked in a hard-gate checklist; [PROPOSED] flags
  moved to §6.
- **v0.3 (2026-10-01).** Owner decisions relayed by the coordinator:
  - **Payments: Paystack.** Paystack is the payment processor, not a merchant of record, so SelahCue
    is the seller (Terms 8.3, 8.7, 8.9). Paystack collects card and bank details on its hosted
    checkout; SelahCue never receives full card numbers (Privacy 3.4). Paystack's checkout cookies and
    scripts are in the cookie table (Privacy 4.1).
  - **Downloads.** Installers sit in a private, encrypted, versioned S3-compatible bucket (DigitalOcean
    Spaces or Hetzner Object Storage, provider undecided). CI uploads Releases; users always receive the
    latest Release; earlier Releases are kept for rollback; delivery is by expiring link (Privacy 3.3,
    7, 9.1; Terms 5.4, 5.5, 13.1).
  - **Account deletion** is self-service (ticket 17tnw2b0wqk). **Data export is by request only**: the
    customer emails us, we verify identity and deliver the export by expiring link within
    `{{DSAR_RESPONSE_TIME}}` (ticket 17tnw2b0wqm) (Privacy 11.2–11.4; Terms 15.1).
  - **Generic legal posture.** All NDPA/GAID/NDPC citations, the DPO, EU/UK representatives,
    regulator-filing statements and jurisdiction-specific rights lists are removed. Rights are stated
    generically, international processing is described truthfully, and governing law and forum stay
    placeholders.
  - **Cloud features** keep the live, opt-in description, now naming **Deepgram** (transcription) and
    **OpenAI** (notes), both documented in the repository (§8.1, P28), and stating that data leaves the
    church's network and can be processed in another country. Regulator-facing framing (controller and
    processor roles, DPA references, model-training claims) is removed.
  - The §4 checklist now has a Gate/Deferred column. Regulator-facing rows are "Deferred — accepted risk"
    unless a policy statement depends on them. Accepted risks are recorded in §7. Terms 5.4 (latest
    Release after a Plan ends) moved out of §6 because the owner's always-latest download decision
    covers it.

## 3. How to read the drafts

- **`{{PLACEHOLDER}}`** — a fact or decision nobody has supplied. Never publish with one left in.
- Everything else in the policies is written as true at launch. Whether it is actually true is tracked
  in §4, not in the policy text.
- New risk allocations and commitments the owner and counsel must accept are listed in §6.
- **The site pages are generated from these files.** After editing either policy, run
  `npm run sync:legal` in `implementation/marketing` and commit the generated files; CI fails if they are out
  of sync. A page stays in draft mode (banner, highlighted placeholders, `noindex`) while any placeholder
  remains, while the DRAFT banner is still in the markdown, or while the version line is not `final`.
  To publish: fill every placeholder, clear every gated row in §4, get lawyer sign-off, delete the DRAFT
  banner, add a `Version X.Y (final, YYYY-MM-DD).` paragraph directly under the title, then regenerate. The
  full procedure is in `implementation/marketing/README.md`.

## 4. Launch-readiness conditions

Status key, from my verification of this worktree on 2026-10-01: **Built** = present in code and
config · **Partly built** · **Not built** · **Ticketed** = a ticket exists, nothing found in the code ·
**Undecided** = an owner or counsel decision is needed first · **Unknown** = could not be verified from
the repository. Ticket IDs marked (M) come from the owner's project memory notes; IDs marked (O) were
supplied by the owner through the coordinator on 2026-10-01.

**Gate** = must be satisfied before publication. **Deferred** = owner decision 2026-10-01: deferred,
generic posture; accepted risk (§7); not a publication blocker.

| # | Gate | Policy clause | What must be true at publication | Current status | Decision or ticket needed |
|---|---|---|---|---|---|
| L-1 | Gate | Privacy header & 13; Terms header & 25; site footer | Legal entity, address, registration number, privacy, support and legal-notice mailboxes are real and monitored; one email domain is used consistently; the footer names the entity | Undecided (no entity named; site uses `selahcue.app`, API uses `selahcue.com` and `firstpavitech.com`) | Owner decision |
| L-2 | Gate | Privacy 2.3; Terms 9.4 | The desktop app includes a congregation-recording notice the church can display (PRD FR-158) | Unknown (no evidence found) | Ticket needed (FR-158) |
| L-3 | Gate | Privacy 2.4 | Operators can delete a transcript in the operator console, and administrators can set automatic deletion after N days | Partly built (repository supports delete and `retention_days`; console UI not verified) | Engineering to confirm or build |
| L-4 | Gate | Privacy 2.4 | Deleting a transcript deletes its sermon-note draft by default | Built in the repository; the default is flagged in `transcript_repo.rs` as awaiting owner sign-off | Owner decision |
| L-5 | Gate | Privacy 2.4 | The desktop app keeps no audio recordings in the launch build | Built for the current build (no audio store found); PRD FR-153 contemplates raw-audio retention | Engineering to confirm for the launch build |
| L-6 | Gate | Privacy 2.4, 9.1 | The transcript database is encrypted by default; the deck library and media files are not | Built | Re-check if encryption scope changes |
| L-7 | Gate | Privacy 3.1, 10.1; Terms 2.1 | Sign-up asks the user to confirm the minimum age | Not built (no age field or check) | Ticket needed; owner sets `{{MINIMUM_ACCOUNT_AGE}}` |
| L-8 | Gate | Privacy 3.1; Terms 2.3, 23.2 | Acceptance of the Terms and Privacy Policy is recorded server-side with version, timestamp and user, at sign-up and on re-acceptance of material changes | Not built (the checkbox is checked only in the browser) | Ticket needed |
| L-9 | Deferred | (was Privacy 3.1 sensitive-data condition) | Legal condition for religious-affiliation inference | Placeholder removed; the policy states only that account data is not used to profile beliefs (true by design) | Accepted risk (§7) |
| L-10 | Gate | Privacy 3.2 | Transactional email runs through the chosen provider, and the sender domain matches L-1 | Partly built (SMTP and Celery seam built; provider undecided; default sender `noreply@selahcue.com`) | Owner decision |
| L-11 | Gate | Privacy 3.2; Terms 8.13 | Licence and plan emails (renewal reminders, expiry, suspension) and receipts/invoices are sent | Not built (Platform PRD FR-528) | Ticket needed |
| L-12 | Gate | Privacy 3.2 | Marketing email is sent only with recorded consent and every message has an unsubscribe link, or no marketing email is sent | Built in the sense that no marketing email exists | Re-check if marketing starts |
| L-13 | Gate | Privacy 3.3; Terms 6.1–6.4 | The released desktop activates Devices by Administrator sign-in and by enrolment key, stores the device credential in the OS secure store, and verifies signed licence files | Partly built (API built; `selahcue-licensing` client crate exists but is not linked into released binaries; sign-in activation blocked by CSRF, 86ak5t1gw) | 86ak5mn11, 86ak5mn1d, 86ak5mn1t, 86ak5t1gw |
| L-14 | Gate | Privacy 3.3 | The device-identifier method is decided and privacy-reviewed | Undecided (left to the app shell by design, `selahcue-licensing/src/device.rs`) | Engineering + counsel (`{{DEVICE_FINGERPRINT_METHOD}}`) |
| L-15 | Gate | Privacy 3.3; Terms 6.2 | Devices refresh licence files automatically when online, and the server records each Device's last check-in time | Partly built (refresh endpoint exists; no last-check-in field on `Device` or `DeviceToken`) | 86ak5mn1h; schema change needed |
| L-16 | Gate | Privacy 3.3, 7.1, 9.1; Terms 5.4, 5.5, 13.1 | Installers live in a private, encrypted, versioned S3-compatible bucket with the chosen provider and region; CI uploads Releases; downloads go through accounts or activated Devices by expiring link; the latest Release is always served; earlier Releases are kept and a Release can be withdrawn and rolled back; each download is recorded (what, platform, when, account or device) | Ticketed (`downloads:prepare` and `:complete` return 501; download-page buttons link nowhere) | Bucket 17tnw2b0wqj (O); downloads backend 86ak10afm (O); owner chooses `{{DOWNLOAD_HOSTING_PROVIDER}}` and `{{DOWNLOAD_HOSTING_REGION}}` |
| L-17 | Gate | Privacy 6.2, 11.2; Terms 6.3, 8.6, 8.10, 15.1 | The customer portal shows members, plan, licence, Devices, usage and billing history; Administrators can deactivate a Device, cancel a Plan and close the Account | Not built (`accountViewer` returns only the viewer; no device-deactivation writer) | Tickets needed (FR-525, FR-511) |
| L-18 | Gate | Terms 6.5, 8.13, 14.1 | Licence and Plan changes take effect only at the next Session; activated Devices keep running when the platform is unavailable | Not built (decided: DEC-009, Platform PRD CON-P1, FR-549, NFR-504) | 86ak5mn1t |
| L-19 | Gate | Terms 7.2 | Free-Plan output shows the watermark | Not built (decided: DEC-008, FR-548; grant dimension exists in the catalogue) | Ticket needed |
| L-20 | Gate | Privacy 3.4, 4.1, 6.1; Terms 8.3–8.10, 13.1 | Paystack is integrated end to end: hosted checkout so no card data touches SelahCue servers; subscription billing; webhook; automatic licence issuance; receipts and invoices issued by SelahCue as seller; refunds through Paystack; the data Paystack sends us is defined; Paystack's checkout cookies and scripts match the cookie table | Not built (billing webhook returns 501; `apps/billing` is a scaffold). Payment provider decided: Paystack (owner, 2026-10-01) | D2 86ak10g47 (Paystack decided); FR-534, FR-537; record the Paystack decision in DECISION-LOG |
| L-21 | Gate | Terms 8.1–8.9, 8.11; pricing page | Prices, currency, Billing Periods, trial, renewal, proration, downgrade timing, refund policy, price-change notice and failed-payment period are decided; the pricing page matches the catalogue | Undecided (DEC-008/009/010 decide tiers, grace and suspension only; tier names and allowance periods conflict across DEC-008, the owner decision of 2026-09-27 and the pricing page) | Owner decision D1 (86ak10gph); catalogue 17tnw2az0gd (M) |
| L-22 | Gate | Terms 8.5 | Renewal reminders meet the automatic-renewal laws of each market where paid Plans are sold | Undecided | Counsel review |
| L-23 | Gate | Terms 8.11 | Allowance rules on upgrade and downgrade, and session-start Device gating after a downgrade, are implemented | Not built (allowance rules are owner-decided per project memory, not in DECISION-LOG; Device rule decided in DEC-009/FR-550) | Record the decision in DECISION-LOG; ledger 17tnw2az0gj (M) |
| L-24 | Gate | Terms 8.12 | Soft suspension works: activated Devices keep presenting; new activations, licence renewals and Cloud Features stop; reinstatement restores the prior state | Partly built (API stores `prior_status` and has a state machine; cascade scoping and client behaviour unverified) | DEC-010; 86ak1099u; 86ak5mn1t |
| L-25 | Gate | Terms 8.13 | The 7-day grace, renewal reminder and Free-Plan fallback at the next Session work | Not built (decided: DEC-009, FR-521, FR-549) | Lifecycle jobs (FR-503) + 86ak5mn1t |
| L-26 | Gate | Privacy 3.5, 7.1, 8 | The hosting provider and region are chosen; the server-log retention is set and enforced | Undecided | Owner decision |
| L-27 | Gate | Privacy 3.5, 8 | The audit-record retention is set and enforced, and audit records include allowed and refused cloud-feature requests | Not built (no retention limit on `AuditEvent`; refused-request recording is owner-decided per project memory) | Owner decision; tickets 86akby3xu, 17tnw2az0gn (M) |
| L-28 | Gate | Privacy 8 | Every retention period in the table is set and enforced by scheduled jobs | Partly built (only the nightly session and credential-token sweep exists) | Owner decision + tickets |
| L-29a | Gate | Privacy 11.2; Terms 15.1 | Users can delete their user account in account settings; Administrators can close the organisation's account; deletion deletes or anonymises personal data and anonymises audit actor references | Not built / ticketed (no such mutation; account models use `on_delete=PROTECT`) | Self-service deletion 17tnw2b0wqk (O); Platform PRD §16 |
| L-29b | Gate | Privacy 11.3; Terms 15.1 | Export by request: a support runbook and admin tooling exist to verify identity, produce an account-data export and deliver it by expiring link within `{{DSAR_RESPONSE_TIME}}` | Not built / ticketed | Export-by-request 17tnw2b0wqm (O); owner sets `{{DSAR_RESPONSE_TIME}}` |
| L-30 | Gate | Privacy 11.4–11.5 | Other privacy requests are answered within `{{DSAR_RESPONSE_TIME}}` after identity checks, and there is a procedure for helping churches with requests about cloud-feature data. (A formal complaints-handling process under UK DUAA s.103 or the GAID is Deferred, §7.) | Unknown (no procedure documented) | Operations (shares the 17tnw2b0wqm runbook) |
| L-31 | Gate | Privacy 3.6 | The website contact form actually sends messages to a monitored mailbox, and its confirmation text makes only promises staff can keep | Not built (the form fakes success with a timer and promises a reply "within 24 hours") | Ticket needed |
| L-32 | Gate | Privacy 3.7 | The launch desktop build has no advertising, analytics, telemetry or crash reporting; its only internet connections are those listed. If it checks for updates automatically, that is added to 3.7 | Built for the current Windows build (verified from direct dependencies); launch build to be re-checked | Engineering re-check at release |
| L-33 | Gate | Privacy 3.7; Terms 13.1 | The speech model still downloads from `huggingface.co` | Built | Re-check at release |
| L-34 | Gate | Privacy 3.7, 3.9; Terms 9.3 | Bible translations download from the real host in `{{TRANSLATION_DOWNLOAD_HOST}}`; the Young's Literal Translation pin has a real URL and digest | Not built (the catalogue URL is `https://OWNER-SUPPLIED.invalid/...`) | Owner supplies host and pin (may be the 17tnw2b0wqj bucket) |
| L-35 | Gate | Privacy 3.9, 6.1; Terms 9.3, 13.1 | Licensed translations: publisher agreements signed; translations delivered only to activated Devices on eligible Plans; export restrictions enforced (FR-146); publisher terms published; the publisher reporting data is defined | Not built (story 86ajpqfyj; API README lists licensed translations and reporting as open owner decisions) | Owner decision + 86ajpqfyj |
| L-36 | Gate | Privacy 3.8; Terms 12 | Cloud transcription (Deepgram, audio streamed directly from the desktop with a server-minted short-lived credential) and AI notes (OpenAI, route per `{{NOTES_ROUTE}}`) ship in the released build with no developer keys; per-feature Administrator opt-in; the consent screen names Deepgram and OpenAI, says what data is sent and that it leaves the church's network and can be processed in another country (86akby5hk asks it to say sermon data leaves the country; the policy wording must match whatever the screen finally says); an active-cloud indicator (FR-133) | Partly built (consent model in `selahcue-core`; Deepgram and OpenAI paths exist only in developer builds; hosted credential path not built; consent-screen ticket text not found in the repo) | 86akby5hk (consent screen); 86ajy04hz, 86akby3xu; 17tnw2az0gn, 17tnw2az0n2 (M) |
| L-37 | Gate (part) / Deferred (part) | Privacy 3.8, 8; Terms 12.2 | **Gate:** Deepgram's and OpenAI's current terms are reviewed so that the Privacy 3.8 statement (they say how long they keep data and whether they use it to improve their services) is accurate, and `{{PROVIDER_RETENTION}}` is filled from them. **Deferred:** a DPIA filed with the NDPC, signed DPAs with the providers, a church-facing DPA, transfer instruments and a formal COPPA assessment | Not done | Owner (gate part); accepted risk (deferred part, §7) |
| L-38 | Gate | Privacy 3.8; Terms 12.4 | Usage records and allowances work as described, including the rule that a failed note generation does not use up the allowance, and the retry terms | Not built (decided per project memory: D7 and the ADR-0028 retry rule, which sits in draft PR #111) | 17tnw2az0gj, 17tnw2az0gn (M); fill `{{RETRY_ALLOWANCE_TERMS}}` |
| L-39 | Gate | Privacy 3.10 | No sale, no behavioural advertising, no solely automated decisions with significant effects | Built (true today) | Re-check at release |
| L-40 | Gate | Privacy 4.1, 4.4 | A cookie audit of the production site shows only the listed cookies and storage (including the `csrftoken` lifetime and Paystack's checkout cookies) and no analytics or advertising tools | Built in code (the `csrftoken` lifetime is the Django default and is unverified on a deployment) | Cookie audit at release |
| L-41 | Gate | Privacy 4.3; Terms 13.1 | Either the site still loads Google Fonts (disclosure stays), or the font is self-hosted and both Google Fonts passages are deleted | Built (the site loads Google Fonts today); self-hosting recommended | Owner decision |
| L-42 | Deferred | (Privacy 4) | GAID Art. 7(l)-style homepage cookie notice | The policy does not claim a notice | Accepted risk (§7) |
| L-43 | Deferred | (was Privacy 5.1 LIA reference) | Legitimate Interest Assessment | Placeholder removed; the policy no longer claims an assessment | Accepted risk (§7) |
| L-44 | Deferred | (Privacy 6.1) | Written data processing agreements with hosting, storage and email providers beyond their standard terms | The policy now describes providers only as running parts of the service | Accepted risk (§7) |
| L-45 | Deferred / placeholder | Privacy 7.2 | NDPA transfer bases and GAID Art. 18(1)(e) consent mechanics | Deferred; the policy states plainly that processing can be outside the user's country. `{{TRANSFER_SAFEGUARDS_SUMMARY}}` must still be filled with a true statement (or deleted) | Accepted risk (§7); owner fills the placeholder truthfully |
| L-46 | Deferred | (was Privacy header, 11.6, 13) | NDPC registration as a data controller of major importance; DPO; EU and UK representatives | Placeholders and sections removed; nothing is claimed | Accepted risk (§7) |
| L-47 | Gate | Privacy 9.1 | The deployment serves HTTPS only (HSTS on), Redis-backed rate limiting is configured, the lockout settings are as described, and installers are stored encrypted and delivered only by expiring link | Built in code for the API; deployment and bucket unknown | Operations check at release; 17tnw2b0wqj (O) |
| L-48 | Gate (part) / Deferred (part) | Privacy 9.2 | **Gate:** an internal breach-response procedure exists so affected users are told without undue delay and authorities are informed where the law requires. **Deferred:** NDPC-specific 72-hour notification mechanics | Unknown | Operations; accepted risk (deferred part, §7) |
| L-49 | Gate | Terms 5.4 | The latest Release stays downloadable after a paid Plan ends | Ticketed (owner decision 2026-10-01: always-latest downloads) | 86ak10afm (O) |
| L-50 | Gate | Terms 6.5, 14.3, 15.2, 16.1, 17.3, 19, 22.2, 23.2; Privacy 11.2 | The owner and counsel accept each proposal listed in §6, or change or delete the clause | Undecided | Owner + counsel |
| L-51 | Gate | Terms 5.6, 13.1 | Open-source licence notices and the NDI attribution are published | Not built | Engineering (`{{THIRD_PARTY_NOTICES_LOCATION}}`, `{{NDI_ATTRIBUTION_TEXT}}`) |
| L-52 | Gate | Terms 10.1 | Scripture detection requires operator approval by default; AI notes show the AI-generated label and fabrication warning | Partly built (label and warning in `selahcue-core`/`selahcue-cloud`; the detection default is specified in PRD FR-115 but not verified in code) | Engineering to confirm |
| L-53 | Gate | Terms 14.2 | The support mailbox is staffed to the published support terms | Unknown | Operations (`{{SUPPORT_TERMS}}`) |
| L-54 | Gate | Terms 22 | Governing law and forum are chosen | Undecided | Owner + counsel |
| L-55 | Gate | Terms 1.2; Privacy 1.3 | The Controller app policies are published at the URLs used, with placeholder values aligned (§13) | Not built | Owner |
| L-56 | Gate | Website pages | The pricing, download, contact and sign-up pages are consistent with both policies (no PayPal/ACH/SLA/version claims that are untrue; no "Church" plan unless it exists) | Not built (see §9.4) | Ticket needed |
| L-57 | Gate | Terms 8.3, 8.9 | As the seller, SelahCue is set up to issue invoices and to collect and remit any value added tax or sales tax it must collect where it sells | Unknown | Owner + accountant |

**Totals:** 58 rows (L-29 split into L-29a and L-29b; L-57 new). 50 rows are fully gated, 6 are fully
deferred (L-9, L-42, L-43, L-44, L-45, L-46), and 2 are split between gated and deferred parts (L-37,
L-48).

## 5. Placeholder register (52 placeholders)

**Removed in v0.3 (13):** `DPO_NAME_AND_CONTACT`, `EU_REPRESENTATIVE`, `UK_REPRESENTATIVE`,
`LIA_REFERENCE`, `DPA_REFERENCE`, `SENSITIVE_DATA_CONDITION`, `MODEL_TRAINING_STATEMENT`,
`TRANSFER_MECHANISMS` (replaced by `TRANSFER_SAFEGUARDS_SUMMARY`), `PAYMENT_PROVIDER` (now Paystack),
`MERCHANT_OF_RECORD` (SelahCue is the seller), `STT_PROVIDER` (now Deepgram), `NOTES_PROVIDER` (now
OpenAI), `STT_ROUTE` (the repository documents a direct desktop-to-Deepgram stream with a
server-minted credential).

**New in v0.3 (4):** `DOWNLOAD_HOSTING_PROVIDER`, `DOWNLOAD_HOSTING_REGION`, `DSAR_RESPONSE_TIME`,
`TRANSFER_SAFEGUARDS_SUMMARY`.

| Placeholder | Meaning | Used in | Who decides |
|---|---|---|---|
| `{{LEGAL_ENTITY_NAME}}` | Exact registered name of the contracting entity and seller | Both | Owner |
| `{{REGISTERED_ADDRESS}}` | Registered office address | Both | Owner |
| `{{COMPANY_REGISTRATION_NUMBER}}` | CAC (or other) registration number | Both | Owner |
| `{{EFFECTIVE_DATE}}` | Date each document takes effect | Both | Owner, at publication |
| `{{WEBSITE_URL}}` | Production website URL | Both | Owner |
| `{{PRIVACY_POLICY_URL}}` | Public URL of the privacy policy | Both | Owner |
| `{{TERMS_URL}}` | Public URL of the terms | Terms | Owner |
| `{{PRIVACY_CONTACT_EMAIL}}` | Mailbox for privacy requests, export requests and concerns | Privacy | Owner |
| `{{SUPPORT_CONTACT_EMAIL}}` | Support mailbox | Both | Owner |
| `{{LEGAL_NOTICES_EMAIL}}` | Address for formal legal notices | Terms | Owner |
| `{{CONTROLLER_PRIVACY_POLICY_URL}}` | Public URL of the mobile Controller privacy policy | Privacy | Owner |
| `{{CONTROLLER_TERMS_URL}}` | Public URL of the mobile Controller terms | Terms | Owner |
| `{{EMAIL_DELIVERY_PROVIDER}}` | Transactional email provider | Privacy | Owner |
| `{{HOSTING_PROVIDER}}` | Hosting provider for the API and site | Privacy | Owner |
| `{{HOSTING_REGION}}` | Country or region of the servers | Privacy | Owner |
| `{{DOWNLOAD_HOSTING_PROVIDER}}` **(new)** | Object-storage provider for installers (DigitalOcean Spaces or Hetzner Object Storage; undecided) | Both | Owner |
| `{{DOWNLOAD_HOSTING_REGION}}` **(new)** | Region of the installer bucket | Privacy | Owner |
| `{{COUNTRY_OF_ESTABLISHMENT}}` | Country where SelahCue is established (assumed Nigeria) | Privacy | Owner |
| `{{TRANSFER_SAFEGUARDS_SUMMARY}}` **(new)** | One or two true sentences on what SelahCue does to protect data processed abroad (for example, choosing providers with published security and privacy commitments), or delete it. Must not claim instruments that do not exist | Privacy 7.2 | Owner + counsel |
| `{{SERVER_LOG_RETENTION}}` | Server log retention | Privacy | Owner |
| `{{AUDIT_RECORD_RETENTION}}` | Audit-record retention | Privacy | Owner |
| `{{ACCOUNT_RETENTION_AFTER_CLOSURE}}` | Retention of account data after closure | Privacy | Owner |
| `{{UNVERIFIED_SIGNUP_RETENTION}}` | Deletion period for never-verified sign-ups | Privacy | Owner |
| `{{LICENCE_RECORD_RETENTION}}` | Retention of licence, device, download and usage records | Privacy | Owner |
| `{{FINANCIAL_RECORD_RETENTION}}` | Payment, invoice and tax record retention (statutory minimums apply) | Privacy | Owner + accountant |
| `{{SUPPORT_RETENTION}}` | Support message retention | Privacy | Owner |
| `{{PROVIDER_RETENTION}}` | How long audio and transcripts sent to cloud features are kept (by SelahCue, and by Deepgram and OpenAI under their terms) | Privacy 3.8, 8 | Owner, from provider terms (L-37) |
| `{{DSAR_RESPONSE_TIME}}` **(new)** | Time within which SelahCue answers privacy requests and delivers data exports | Privacy 11.3, 11.4 | Owner |
| `{{MINIMUM_ACCOUNT_AGE}}` | Minimum age to hold an account (18 recommended) | Both | Owner |
| `{{DEVICE_FINGERPRINT_METHOD}}` | How the desktop generates the device identifier | Privacy | Engineering |
| `{{PAYMENT_DATA_RECEIVED}}` | Data Paystack sends SelahCue (for example, transaction reference, amount, status, card type and last four digits) | Privacy 3.4 | Owner, from the Paystack integration |
| `{{TRANSLATION_DOWNLOAD_HOST}}` | Host for downloadable Bible translations | Privacy | Owner |
| `{{NOTES_ROUTE}}` | Whether notes travel directly from the desktop to OpenAI, or through SelahCue's servers (`selahcue-cloud/src/openai.rs` says proxied; ADR-0028 in draft PR #111 proposes direct) | Privacy 3.8 | Owner + engineering |
| `{{PUBLISHER_REPORTING_DATA}}` | What usage data publisher licences require SelahCue to report | Privacy 3.9 | Owner, from publisher agreements |
| `{{THIRD_PARTY_NOTICES_LOCATION}}` | Where open-source licence notices are published | Terms | Engineering |
| `{{ALLOWANCE_RESET_PERIOD}}` | Usage-allowance reset period (DEC-008 says monthly; the 2026-09-27 owner decision says weekly) | Terms | Owner |
| `{{TRIAL_TERMS}}` | Trial length, features and what happens at the end (sign-up already creates a TRIAL organisation) | Terms 8.2 | Owner |
| `{{BILLING_PERIODS}}` | Billing Periods offered | Terms 8.4 | Owner |
| `{{CURRENCY}}` | Billing currency | Terms 8.4 | Owner |
| `{{RENEWAL_TERMS}}` | Whether and how paid Plans renew (Paystack subscriptions or manual renewal) | Terms 8.5 | Owner + counsel |
| `{{REFUND_POLICY}}` | Refund policy | Terms 8.7 | Owner + counsel |
| `{{PRICE_CHANGE_NOTICE_DAYS}}` | Notice period for price changes | Terms 8.8 | Owner |
| `{{PRORATION_TERMS}}` | How upgrades are charged part-way through a Billing Period | Terms 8.11 | Owner |
| `{{DOWNGRADE_TIMING}}` | When a downgrade takes effect | Terms 8.11 | Owner |
| `{{FAILED_PAYMENT_GRACE_PERIOD}}` | How long after a failed payment before suspension | Terms 8.12 | Owner |
| `{{RETRY_ALLOWANCE_TERMS}}` | The note-retry rule (project memory records one retry within 10 minutes against the same reservation, the failed attempt and its retry together costing one unit) | Terms 12.4 | Owner to confirm |
| `{{NDI_ATTRIBUTION_TEXT}}` | Attribution and trademark wording required by the NDI licence | Terms | Owner |
| `{{SUPPORT_TERMS}}` | Support hours and response commitments | Terms | Owner |
| `{{MINIMUM_LIABILITY_AMOUNT}}` | Floor of the liability cap | Terms | Owner + counsel |
| `{{GOVERNING_LAW}}` | Governing law | Terms | Owner + counsel |
| `{{DISPUTE_FORUM}}` | Court or arbitral forum | Terms | Owner + counsel |
| `{{TERMS_CHANGE_NOTICE_DAYS}}` | Notice period for material changes to the Terms | Terms | Owner |

## 6. Proposed risk allocations and commitments

The clause text is clean. These clauses are new allocations of risk, or commitments beyond what is
decided. Each needs owner and counsel acceptance (checklist row L-50) before publication.

| Clause | What it does | Why it is a proposal |
|---|---|---|
| Terms 17.3 | Caps SelahCue's liability at the greater of 12 months' fees and `{{MINIMUM_LIABILITY_AMOUNT}}` | A risk allocation; the floor protects free users' claims from being capped at zero |
| Terms 19 | Customer indemnity for infringing content and unlawful recording | A risk allocation; may be resisted by churches; can be deleted |
| Terms 6.5 | A licence or Plan change never interrupts a running Session | Decided product rule (CON-P1, FR-549); publishing it makes it a contractual promise |
| Terms 14.3 | Refund if a material feature reduction leads to cancellation | Fairness term; commits money |
| Terms 15.2 | 14-day cure period before termination for breach | Process commitment |
| Terms 16.1 | Warranty of reasonable care and skill | A contractual warranty for everyone |
| Terms 22.2 | 30 days of good-faith negotiation before formal disputes | Process commitment |
| Terms 23.2 | Administrators re-accept material changes; refund of unused fees if they reject | Needs L-8; commits money |
| Privacy 11.2 | Deletion anonymises audit actor references | Platform PRD §16 design; needs engineering (L-29a) |

## 7. Accepted risks (owner decision 2026-10-01)

The owner has decided that SelahCue, as a very small startup, will adopt a generic legal posture and
will **not** pursue the following now. The policies make no claim about any of them.

- Registration with the Nigeria Data Protection Commission as a data controller of major importance,
  and the related annual compliance audits and filings.
- Appointing a Data Protection Officer.
- GAID cross-border transfer mechanics, including consent before transfers to countries without an
  NDPC adequacy decision (GAID Art. 18(1)(e)), and formal transfer instruments.
- Data privacy impact assessments, including any DPIA filed with the NDPC for cloud transcription.
- EU and UK representatives.
- Signed data processing agreements with providers beyond their standard terms, and a church-facing
  data processing agreement for the cloud features.
- A documented Legitimate Interest Assessment.
- A formal legal condition for any religious-affiliation inference from account data.
- A GAID-style homepage cookie notice.
- NDPC-specific 72-hour breach notification mechanics, and a formal complaints process under UK DUAA
  s.103.
- A formal COPPA assessment for cloud transcription.

**Why a lawyer may still disagree.** Statutory duties to register, appoint a DPO, assess high-risk
processing, safeguard transfers and notify regulators can apply regardless of company size, once the
legal thresholds are met. The NDPC's registration threshold (more than 200 data subjects in six months,
or commercial ICT services on other people's devices) is low, and the GDPR and UK GDPR can apply to a
non-EU, non-UK company that offers services to people there. Cloud transcription sends sermon audio,
which can reveal religious beliefs and children's voices, to providers abroad. Revisit these items when
budget allows, and in any case before targeting EU or UK customers, before selling in Nigeria at scale,
or before cloud transcription reaches many churches.

The owner's decision stands. These notes record it so that the trade-off is visible to any reviewer.

## 8. Fact-to-source table

Status key: **V** = verified in code or config in this worktree · **D** = documented decision or
requirement, not necessarily built · **I** = inferred, needs confirmation · **M** = from the owner's
project memory notes, not verified in the tree · **O** = owner decision relayed by the coordinator on
2026-10-01, with no in-repo decision record so far.

### 8.1 Privacy Policy facts

| # | Claim in the draft | Source | Status |
|---|---|---|---|
| P1 | Plans, slides, decks, songs, themes and screen settings are stored locally | `implementation/desktop/crates/selahcue-data/src/lib.rs`; `docs/architecture/ARCHITECTURE.md` §8 | V |
| P2 | Media files are referenced by path | `ARCHITECTURE.md` §8; DEC-003 | D |
| P3 | Transcripts, corrections and detected references are stored locally | `selahcue-data/src/transcript_repo.rs` | V |
| P4 | Sermon-note drafts are stored locally | `selahcue-data/src/lib.rs` (`sermon_note_repo`) | V |
| P5 | Content reaches SelahCue only through cloud features or support | Root `Makefile`; `windows-installer.yml`; `selahcue-operator/Cargo.toml`; `selahcue-cloud/src/lib.rs` | V (today's build) |
| P6 | Transcript database encrypted by default | `selahcue-desktop/Cargo.toml`; `selahcue-operator/Cargo.toml`; `Makefile` | V |
| P7 | Deck library not encrypted | `selahcue-operator/Cargo.toml` comment on `selahcue-data` | V |
| P8 | Transcript delete cascade; automatic deletion after N days | `transcript_repo.rs` (`RetentionSettings`) | V (repository); UI is L-3 |
| P9 | No audio recordings kept | No audio store in `selahcue-data` | I (L-5) |
| P10 | Mobile devices receive slides, timers and the transcript preview over an encrypted, pinned link | `docs/legal/PRIVACY.md` §3; `ARCHITECTURE.md` §9 | V |
| P11 | LAN discovery; NDI broadcast | `selahcue-desktop/Cargo.toml` (`mdns-sd`, `ndi`) | V |
| P12 | Account fields | `apps/accounts/models.py`; `graphql/account_schema.py`; `SignUpView.vue` | V |
| P13 | Billing contact email field | `CustomerOrg.billing_contact_email` | V (field exists; nothing collects it today) |
| P14 | Staff notes | `CustomerOrg.internal_notes` | V |
| P15 | Password hashing; session TTLs; lockout; sessions revoked on password change | `accounts/models.py`; `settings.py`; DEC-007; DEC-013 | V |
| P16 | Account emails (verify, reset, account-exists) | `apps/accounts/tasks.py` | V |
| P17 | Licence and plan emails | Platform PRD FR-528 | D (L-11) |
| P18 | Activation data and device credential | `apps/devices/models.py`; `ActivateDeviceInput`; `selahcue-licensing/src/device.rs` | V (server) |
| P19 | Licence check-ins with last-check-in time | `implementation/api/README.md` (`license:refresh`); Platform PRD FR-519, FR-525 | D (L-15) |
| P20 | Installers in a private, encrypted, versioned bucket; expiring links; always-latest; rollback; download records | Owner decision; Platform PRD FR-530 | O/D (L-16, tickets 17tnw2b0wqj, 86ak10afm) |
| P21 | Enrolment keys hashed and masked | `apps/license_keys/models.py` | V |
| P22 | Paystack hosted checkout; no full card numbers held | Owner decision (the Platform PRD's D2 option list names Stripe, Paddle and FastSpring, not Paystack) | O (L-20) |
| P23 | Rate-limit counters; IPv6 /64 | `apps/throttling/services.py`; `settings.py` | V |
| P24 | Audit records with secrets removed | `apps/audit/models.py`, `apps/audit/services.py`, `graphql/redaction.py` | V |
| P25 | Audit records of allowed and refused cloud requests | Owner decision OD-3 (2026-09-27) | M (L-27) |
| P26 | No analytics, telemetry or crash reporting | Direct dependency manifests (operator, desktop, API, mobile, marketing) | V (direct dependencies only) |
| P27 | Speech model from `huggingface.co`, integrity-checked | `selahcue-stt/src/model.rs`, `model_fetch.rs` | V |
| P28 | Cloud transcription streams audio directly to Deepgram with a server-minted short-lived credential; notes go to OpenAI; off by default; Administrator-gated; audio only for transcription, transcript text only for notes | `selahcue-stt-cloud/src/lib.rs` (Deepgram; Phase 2 grant token, 86akby3xu); `selahcue-cloud/src/openai.rs` (`PROVIDER_LABEL = "OpenAI"`); `selahcue-core/src/providers.rs`; `implementation/desktop/CLAUDE.md`; PRD FR-132/133/137/177 | V (design and developer builds) |
| P29 | Consent screen names the providers and says data leaves the country | Ticket 86akby5hk (text not found in the repo); PRD FR-132 and FR-177 require naming the provider and stating that data leaves the local network and jurisdiction | D (L-36) |
| P30 | Usage records in time and number of notes | Platform PRD FR-546; owner decisions D7/D8 | D/M |
| P31 | Licensed translations and publisher reporting | `selahcue-scripture/src/lib.rs` (86ajpqfyj); `implementation/api/README.md` | D (L-35) |
| P32 | Cookies and local storage | `account_schema.py`; `settings.py`; `selahcue_api/urls.py`; `src/lib/auth/session.ts` | V (`csrftoken` lifetime is L-40) |
| P33 | Google Fonts | `implementation/marketing/index.html` | V |
| P34 | No analytics on the site | `package.json`; `index.html`; `src/main.ts` | V |
| P35 | Self-service account deletion; export by request with expiring link | Owner decision; tickets 17tnw2b0wqk, 17tnw2b0wqm | O (L-29a, L-29b) |
| P36 | Portal shows members, plan, licence, devices, usage, billing | Platform PRD FR-525 | D (L-17) |

### 8.2 Terms of Service facts

| # | Claim | Source | Status |
|---|---|---|---|
| T1 | Core presentation works offline | PRD CON-2, NFR-015; `selahcue-licensing/src/lib.rs` | V/D |
| T2 | One email, one account | `CustomerUser` unique constraint | V |
| T3 | Bundled translations: KJV, WEB, ASV, WEBBE, Darby | `selahcue-scripture/src/lib.rs` | V |
| T4 | KJV Crown letters patent (UK) | Code comment; ebible.org (secondary) | V (secondary source) |
| T5 | Operator approval of scripture suggestions by default | PRD FR-115/116 | D (L-52) |
| T6 | AI-generated label and fabrication warning | `selahcue-core/src/providers.rs` (`AI_GENERATED_LABEL`, `FABRICATION_DISCLOSURE`); `selahcue-cloud/src/lib.rs` | V |
| T7 | Watermark on the free Plan | DEC-008; FR-548 | D (L-19) |
| T8 | 7-day grace, then the free Plan from the next Session | DEC-009; FR-521/549 | D (L-25) |
| T9 | Soft suspension | DEC-010; FR-504/510; `license_keys/models.py` (`prior_status`) | D/partly V (L-24) |
| T10 | A downgrade keeps Devices; limit applied at Session start | DEC-009; FR-550 | D (L-23) |
| T11 | Allowance rules on upgrade and downgrade | Owner decision 2026-09-27 | M (L-23) |
| T12 | Failed note generation not charged; retry rule | Owner decisions D7 and ADR-0028 rev 2 (draft PR #111) | M (L-38) |
| T13 | Activation by sign-in or enrolment key; signed offline licence file | DEC-004/005/011; `implementation/api/README.md` | V (server) |
| T14 | Session-boundary rule; offline when the platform is down | Platform PRD CON-P1, FR-549, NFR-504 | D (L-18) |
| T15 | SelahCue is the seller; Paystack processes payments | Owner decision | O (L-20, L-57) |
| T16 | Always-latest downloads, rollback of a bad Release, latest Release after a Plan ends | Owner decision | O (L-16, L-49) |
| T17 | Trial organisation created at sign-up | DEC-007 product answers (TRIAL status) | V |
| T18 | Third parties: NDI, Hugging Face, Google Fonts, Deepgram, OpenAI | `selahcue-desktop/Cargo.toml`; `selahcue-stt/src/model.rs`; `index.html`; P28 sources | V |

## 9. Claims on the old stub pages

Sources: `implementation/marketing/src/views/PrivacyView.vue` and `TermsView.vue` as they were before the
legal pages were wired to these drafts (ClickUp 17tnw2b0x3g, PR #142). Those stubs are replaced by the
generated pages when that PR merges; until a draft is published, the pages show a "Draft, pending legal
review" banner and are sent with `noindex`. The claims below describe the old stub text, kept so counsel can
see what was wrong.

### 9.1 False, or not true today

1. **"billing information through our payment processor (Stripe)"** — no payment integration exists; the
   billing webhook returns 501. The owner has since chosen Paystack, not Stripe.
2. **"Copyrighted translations (e.g. NIV, ESV, NLT) are downloaded post-activation under specific
   publisher entitlement agreements"** — no licensed translation, publisher agreement or download
   pipeline exists.
3. **"Public-domain Bibles (e.g. WEB, ASV, BSB) are bundled"** — BSB is not bundled. The bundled set is
   KJV, WEB, ASV, WEBBE and Darby.
4. **"Pro plans are billed on a monthly or annual recurring basis. You may cancel ... via your account
   portal."** — no billing, and the account portal has no plan or cancellation function.
5. **"the SelahCue desktop software transmits an anonymized hardware fingerprint, platform OS version,
   and app version during activation"** — the released desktop does not activate. The identifier is a
   stable per-device value linked to an account (pseudonymous, not anonymised); the server stores the
   platform, not the OS version; a device name is also sent.
6. **"Sermon audio streams and generated transcripts never leave your local venue machine unless you
   explicitly enable an opt-in cloud AI integration"** — transcript previews go to paired mobile devices
   over the local network, and no cloud integration exists in released builds.
7. **"You agree not to extract, reverse engineer, or redistribute encrypted Bible databases"** — no
   encrypted Bible databases exist; bundled texts are compressed, not encrypted.

### 9.2 Partly true or overstated

8. **"On-device speech-to-text (Whisper AI) runs 100% locally ... using native GPU acceleration"** —
   recognition runs locally, but the model downloads from Hugging Face on first use, and only macOS
   builds compile GPU acceleration; the Windows installer build is CPU-only.
9. **"we collect your organization name, primary contact name, email address"** — there is no "primary
   contact name" field (an optional display name exists); the stub omits country, time zone and
   password.
10. **"Data Protection Rights (GDPR & NDPA 2023) ... access, rectify, or request deletion"** — an
    incomplete list, and "billing data" does not exist.
11. **"license ... up to the seat count specified in your Pro or Church subscription plan"** — plan names
    are unsettled; a "Church" plan appears in no decision record.

### 9.3 Not verifiable

12. **`privacy@selahcue.app`** — no evidence that this mailbox or domain exists. The API defaults to
    `noreply@selahcue.com` as sender and `info@firstpavitech.com` as a default address.
13. **"Last Updated: August 8, 2026"** on both pages — no record of a review or publication.
14. **"your organization agrees to be bound"** by downloading — acceptance is not recorded.
15. **"SelahCue grants ..."** — SelahCue is a brand; no legal entity is named on either page or in the
    footer ("© 2026 SelahCue").

### 9.4 Other site content that creates legal risk

- **Contact page** (`ContactView.vue`): the form sends nothing (a timer fakes success) but tells the user
  "A SelahCue specialist will respond within 24 hours". It also lists `support@selahcue.app`
  (unverified), a Discord community of "1,200+ worship tech leaders" (unverified) and links that point
  to `#`.
- **Pricing page** (`PricingView.vue`): Free/Pro/Church, $19 per month, "Save 20%" annually, "Prorated
  charges will apply", "credit cards, PayPal, and ACH" and a "24/7 SLA" — none of this is built or
  decided, and it conflicts with the recorded tier decisions and the Paystack decision.
- **Download page** (`DownloadView.vue`): "Version 1.2.0 (Stable)" for Windows and macOS — the app
  version is 0.1.0 (`tauri.conf.json`), there is no macOS release pipeline, and the buttons link nowhere.
- **Sign-up page**: the Terms and Privacy checkbox is checked only in the browser.

## 10. Jurisdiction analysis (retained for counsel)

The owner has adopted a generic posture (§7). This analysis is kept so that counsel can see what the
generic posture leaves out. The v0.3 policies no longer map clause by clause to any statute.

### 10.1 Nigeria — NDPA 2023 and GAID 2025

- **Application.** The NDPA applies where the controller is domiciled, resident or operating in Nigeria,
  where processing happens in Nigeria, or where data subjects are in Nigeria (s.2(2)). GAID Art. 8(2)
  reads "operating in Nigeria" to include targeting data subjects in Nigeria.
- **GAID 2025.** The General Application and Implementation Directive (NDPC/NDP ACT-GAID/01/2025) took
  effect on 19 September 2025, after which the NDPR 2019 ceased to apply (GAID Art. 3(3)).
- **Privacy notice content.** NDPA s.27(1) lists identity and contact details, lawful basis and purposes,
  recipients, rights, retention, the right to complain to the NDPC, and automated decision-making. The
  generic v0.3 policy covers identity, purposes, recipients, rights, retention and automated decisions,
  but describes reasons for processing in plain terms rather than s.25 lawful bases, and refers users to
  "the data protection authority where you live" rather than naming the NDPC. Counsel may want the NDPC
  named for Nigerian users; this is part of the accepted generic posture.
- **Transparency and accuracy.** Section 24 requires fair, lawful and transparent processing. A policy
  that describes processing that is not happening, or omits processing that is, breaches this; this is
  why §4's gated rows remain a hard gate.
- **Sensitive personal data.** "Sensitive personal data" includes religious or similar beliefs (s.65).
  Section 30(1) restricts processing to listed conditions, and GAID Art. 18(1)(b) requires consent for
  processing sensitive data. Account data (a church name with a person's email) and cloud-feature audio
  and transcripts are the exposures; deferred under §7.
- **Children.** "Child" takes its meaning from the Child's Rights Act 2003 (s.65); s.31 requires parental
  consent with age verification where consent is relied on.
- **Security and breach.** Section 40(2) requires notifying the NDPC within 72 hours of a breach likely
  to risk individuals' rights; s.40(3) requires telling data subjects where risk is high.
- **Processors.** Section 29 requires written agreements with processors.
- **Cross-border transfers.** Sections 41–43; GAID Art. 18(1)(e) additionally requires consent before
  transfers to countries without an NDPC adequacy decision. Deferred under §7.
- **Data controller of major importance.** Under s.44 and GAID Schedule 7, designation applies above 200
  data subjects in six months, or for commercial ICT services on other people's devices; tiers are UHL
  (over 5,000; ₦250,000 fee), EHL (over 1,000 among its factors; ₦100,000 fee) and OHL (over 200).
  Deferred under §7.
- **DPIA.** Section 28; GAID Art. 28(3) makes a DPIA mandatory and filed with the NDPC where sensitive
  data is involved. Deferred under §7.
- **Cookies.** GAID Art. 19 exempts necessary cookies from consent; GAID Art. 7(l) expects a homepage
  cookie notice. Deferred under §7.
- **Retention defaults.** GAID Art. 49(3) (six months after the purpose is accomplished, where no period
  is set) and Art. 21(2) (six months for contracts that did not materialise) are useful defaults for the
  retention placeholders.
- **Consumer protection.** FCCPA 2018 ss.125, 127, 128, 137, 142 and 144 (headings verified only). The
  generic Terms 18 preserves consumer rights without naming statutes.
- **Disputes.** The Arbitration and Mediation Act 2023 (signed 26 May 2023) replaced the Arbitration and
  Conciliation Act 1988.

### 10.2 European Union — GDPR

- **Scope.** Article 3(2)(a) can apply to a non-EU company offering services to people in the EU.
- **Representative.** Article 27 (deferred, §7).
- **Special categories.** Article 9(1) covers data revealing religious beliefs; the CJEU in C-184/20
  (1 August 2022) held that indirectly revealing data counts. Cloud-feature audio and transcripts are
  likely special-category data.
- **Rights and timing.** Article 12(3) sets one month for responses; `{{DSAR_RESPONSE_TIME}}` should not
  exceed it if EU users are served.
- **Children.** Article 8(1): 16 by default for consent to online services.
- **Google Fonts.** *LG München I*, 3 O 17493/20 (20 January 2022) held that loading Google Fonts from
  Google's servers without consent disclosed IP addresses unlawfully; self-hosting is recommended (L-41).

### 10.3 United Kingdom

- UK GDPR and the DPA 2018 mirror the EU position. The Data (Use and Access) Act 2025 (c. 18) received
  Royal Assent on 19 June 2025; its main Part 5 changes commenced on 5 February 2026; s.103 (complaints by
  data subjects) is reported to have commenced on 19 June 2026 (secondary source, unverified).

### 10.4 United States

- **CCPA/CPRA.** Thresholds include annual gross revenue over $26,625,000 (from 1 January 2025); SelahCue
  is probably below all three. The no-sale statement is true.
- **COPPA.** SelahCue is not directed at children, but cloud transcription can send children's voices to
  Deepgram; the amended COPPA Rule took effect on 23 June 2025 with compliance by 22 April 2026
  (secondary sources). Deferred under §7.
- **Automatic-renewal laws** in several states govern subscription disclosures (L-22).

### 10.5 Governing law and forum

Options for `{{GOVERNING_LAW}}` / `{{DISPUTE_FORUM}}`: Nigerian law with the courts of Lagos State;
Nigerian law with arbitration seated in Lagos under the AMA 2023; or either with consumers keeping
home-country rights (already in Terms 22.3).

## 11. Source ledger

All checked 2026-10-01. No new legal research was done for v0.3.

| Proposition | Authority | Provision | URL | Drafting implication |
|---|---|---|---|---|
| NDPA scope, principles, bases, notice, DPIA, processors, sensitive data, children, rights, security, breach, transfers, registration, complaints | Nigeria Data Protection Act 2023 | ss.2, 24–31, 34–46, 65 | https://www.dataguidance.com/sites/default/files/data_protection_act_2023.pdf (mirror of the Act; page images read) | §10.1; accepted risks §7 |
| GAID: NDPR displaced; compliance measures; DCMI; consent cases; cookies; LIA; information; DPIA; third-party sharing; retention | GAID 2025 | Arts. 3, 7–10, 18, 19, 21, 26–28, 41, 49; Schedule 7 | https://ndpc.gov.ng/wp-content/uploads/2025/07/NDP-ACT-GAID-2025-MARCH-20TH.pdf | §10.1; §7 |
| GAID effective 19 September 2025 | Secondary (law firm) | — | https://www.banwo-ighodalo.com/grey-matter/are-you-gaid-2025-ready-navigating-nigerias-gaid-2025-what-your-organisation-needs-to-know-how-bi-can-support-your-compliance-journey/ | Verify on ndpc.gov.ng |
| GDPR scope, child consent, special categories, response time, notice, representative | GDPR | Arts. 3(2), 8(1), 9, 12(3), 13, 27 | https://gdpr-info.eu/ (unofficial mirror; EUR-Lex not retrievable) | §10.2 |
| Indirect revelation of special-category data | CJEU C-184/20 (Grand Chamber, 1 August 2022) | — | https://curia.europa.eu/jcms/upload/docs/application/pdf/2022-08/cp220133lt.pdf (press release; identified by search, not opened) | §10.2 |
| Google Fonts and IP disclosure | LG München I, 3 O 17493/20 (20 January 2022) | — | Secondary: https://www.ihk.de/bergische/recht-und-steuern/wettbewerbsrecht/google-fonts-5646176 | L-41 |
| DUAA 2025 | Data (Use and Access) Act 2025 | ss.103, 112, 142 | https://www.legislation.gov.uk/ukpga/2025/18/contents; https://www.gov.uk/guidance/data-use-and-access-act-2025-plans-for-commencement | §10.3 |
| s.103 commenced 19 June 2026 | Secondary | Commencement No. 6 Regulations 2026 | https://digitalpolicyalert.org/event/40956-data-use-and-access-act-2025-commencement-no-6-and-transitional-and-saving-provisions-regulations-2026-section-103-data-protection-complaints-including-data-protection-regulation-enter-into-force | Verify on legislation.gov.uk |
| CCPA revenue threshold $26,625,000 | California Privacy Protection Agency | CPI adjustment, 1 January 2025 | https://www.cppa.ca.gov/regulations/cpi_adjustment.html | §10.4 |
| COPPA amendments | Secondary (law firm) | 16 CFR Part 312 | https://www.whitecase.com/insight-alert/unpacking-ftcs-coppa-amendments-what-you-need-know | §10.4 |
| FCCPA provisions (headings only) | FCCPA 2018 | ss.125, 127, 128, 137, 142, 144 | https://fccpc.gov.ng/wp-content/uploads/2022/07/FCCPA-2018.pdf | Terms 18 |
| AMA 2023 replaced ACA 1988 | Secondary (law firm) | — | https://www.linklaters.com/insights/blogs/arbitrationlinks/2023/may/nigeria-revises-its-arbitration-act | §10.5 |
| KJV Crown letters patent (UK only) | Secondary (ebible.org) | — | https://ebible.org/kjv/copr.htm | Terms 9.3 |

**Verification gaps.** I could not retrieve EUR-Lex directly; the NDPA text came from a DataGuidance
mirror; I did not read the Child's Rights Act, the FCCPA's substantive text, the COPPA Rule, the DUAA
commencement regulations, the ePrivacy Directive, consumer-contract law, automatic-renewal laws,
Paystack's, Deepgram's or OpenAI's current terms, or Django's default CSRF cookie age. The text of
consent-screen ticket 86akby5hk was not found in the repository.

## 12. Top 10 open questions and risks

1. **Entity, contacts and domains.** No legal entity is named anywhere, and contact addresses span three
   domains. *Owner:* supply the entity details and choose one domain and mailbox set (L-1).
2. **The live site misleads users today.** The stub pages claim Stripe, bundled BSB, licensed
   NIV/ESV/NLT, recurring billing with portal cancellation and GPU acceleration. The contact form
   discards messages while promising a reply within 24 hours, and the pricing and download pages
   advertise plans, payment methods and versions that do not exist. *Owner:* fix these before anything
   else, independent of launch (L-31, L-56).
3. **Publishing before the gate is cleared would make the policies false.** They describe roughly a
   dozen subsystems that are not built (activation client, check-ins, customer portal, Paystack billing,
   the download bucket and backend, the hosted cloud path, licensed translations, account deletion,
   export runbook, acceptance record, retention jobs, age check, watermark and grace enforcement).
   *Owner:* treat §4 as a release gate with a named sign-off, and remove any passage whose feature does
   not ship.
4. **Accepted regulatory risk.** The generic posture (§7) defers NDPC registration, a DPO, transfer
   mechanics, DPIAs, EU/UK representatives, DPAs and related steps. Statutory duties can apply regardless
   of size. *Owner:* revisit at the triggers in §7.
5. **Cloud features send sermon data to providers that can be abroad.** The policies now name Deepgram and OpenAI and say data can
   be processed in another country; the consent screen (86akby5hk) must say the same, and the notes
   route (`{{NOTES_ROUTE}}`) decides whether SelahCue's servers also receive transcripts. Children's
   voices can be included (L-36, L-37).
6. **Paystack billing as seller.** SelahCue, not Paystack, is the seller, so invoices, refunds and any
   VAT or sales tax collection are SelahCue's. The integration must use a hosted checkout so card data
   never touches SelahCue servers. *Owner + accountant:* confirm tax setup (L-20, L-57), and record the
   Paystack decision in DECISION-LOG.
7. **Downloads infrastructure.** The bucket (17tnw2b0wqj) and downloads backend (86ak10afm) must deliver
   expiring links, always-latest Releases and rollback before the policies describe them (L-16, L-49).
8. **Retention, deletion and export.** No retention periods are set, audit rows have no limit, and
   deletion (17tnw2b0wqk) and export-by-request (17tnw2b0wqm) are ticketed but not built (L-27 to L-29b).
9. **Acceptance is not recorded.** The sign-up checkbox is checked only in the browser; Terms 2.3 and
   23.2 promise a server-side record (L-8).
10. **Commercial model and risk allocation.** Prices, currency, Billing Periods, trials, renewal,
    proration, refunds, the failed-payment period and allowance periods are open; tier names conflict
    across DEC-008, the 2026-09-27 decision and the pricing page. The §6 proposals and governing law and
    forum need decisions (L-21, L-22, L-50, L-54).

**Specialist advice recommended** (optional under the owner's generic posture): a Nigerian data
protection practitioner before selling in Nigeria at scale; EU/UK privacy and consumer counsel before
targeting those markets; a tax adviser on VAT as seller of record.

## 13. Reconciliation with the existing mobile documents

- `docs/legal/PRIVACY.md` (Controller app) states the app collects and transmits no personal data to
  SelahCue and talks only to the paired desktop. The platform policy is consistent (Privacy 1.3, 2.5).
- `docs/legal/TERMS.md` (Controller app) leaves governing law as `{{JURISDICTION}}`; Platform Terms 1.2
  makes the Controller terms prevail for the app.
- **Placeholder names differ**: the mobile documents use `{{ADDRESS}}`, `{{DATE}}` and `{{JURISDICTION}}`,
  where the platform drafts use `{{REGISTERED_ADDRESS}}`, `{{EFFECTIVE_DATE}}` and `{{GOVERNING_LAW}}`.
  Fill them with the same values.
- `PRIVACY.md` still has inline drafting markers for children and store forms (written by the mobile
  engineer); align its children's posture with `{{MINIMUM_ACCOUNT_AGE}}` and the generic posture.

## 14. ClickUp audit entries to record

No ClickUp writes were made in any session, at the coordinator's direction. Record the entries in order on
the matter task in the Legal Audit Log list (`1400430000002076`); check for an existing SelahCue
privacy/terms matter task first, and set its status to `awaiting facts / decisions`.

**Entry 1 — v0.1**

```
[AUDIT] SelahCue — Platform Privacy Policy + Terms of Service — created — 2026-10-01
Entity: {{LEGAL_ENTITY_NAME}} (unconfirmed; owner described as First Pavilion, Lagos)   Jurisdiction(s): Nigeria (NDPA 2023, GAID 2025) primary; EU GDPR, UK GDPR/DUAA 2025, US (CCPA/COPPA) flagged   Requested by: repo owner via coordinating agent (delivery ticket 17tnw2b0q93)
Version/status: v0.1 — Draft — facts to confirm
Facts: confirmed from code — local-only desktop data; transcript DB encrypted by default; on-device STT with model download from huggingface.co; release builds exclude cloud STT/AI and do not activate; account fields; cookies; Google Fonts; no analytics; billing not built; no account deletion/export; acceptance not recorded. Assumed — Nigerian entity in Lagos. Open placeholders — 52.
Law checked: NDPA 2023; GAID 2025; GDPR Arts 3, 8, 9, 12, 13, 27; CJEU C-184/20; LG München I 3 O 17493/20; DUAA 2025; CCPA threshold; COPPA amendments; FCCPA 2018 headings; AMA 2023 — all 2026-10-01.
Risks/decisions: misleading live stub pages and contact form; sensitive-data basis; GAID Art 18(1)(e) transfers; NDPC registration; cloud DPIA/DPAs; retention/deletion; acceptance record; commercial model; liability cap/indemnity/governing law.
Boundary: drafted and saved locally only; not committed, published, signed, filed or sent.
Draft: docs/legal/ (three files), branch docs/17tnw2b0q93-legal-privacy-terms-drafts
```

**Entry 2 — v0.2**

```
[AUDIT] SelahCue — Platform Privacy Policy + Terms of Service — version bump (revised) — 2026-10-01
Entity: {{LEGAL_ENTITY_NAME}} (unconfirmed)   Jurisdiction(s): as v0.1   Requested by: repo owner via coordinating agent (PR #133, ticket 17tnw2b0q93)
Version/status: v0.2 — Draft — placeholders and launch-readiness conditions must be cleared
Revision reason: owner direction to write both policies for the launch state; feature-gated blocks and hedging removed; full billing Part C; launch-dependent statements moved to a 56-row hard-gate checklist; [PROPOSED] flags moved to notes §6.
Facts: basis unchanged from v0.1. Open placeholders — 61 (9 new).
Law checked: as v0.1; no new research.
Risks/decisions: publishing before the checklist is satisfied would make the policies false; plus all v0.1 risks.
Boundary: drafted and saved locally only; not committed, published, signed, filed or sent.
Draft: docs/legal/ (three files), branch docs/17tnw2b0q93-legal-privacy-terms-drafts
```

**Entry 3 — v0.3**

```
[AUDIT] SelahCue — Platform Privacy Policy + Terms of Service — version bump (owner decisions applied) — 2026-10-01
Entity: {{LEGAL_ENTITY_NAME}} (unconfirmed; SelahCue entity is the seller)   Jurisdiction(s): generic posture by owner decision; NDPA/GAID/GDPR/UK/US analysis retained in notes §10 for counsel   Requested by: repo owner via coordinating agent (PR #133, ticket 17tnw2b0q93)
Version/status: v0.3 — Draft — placeholders and launch-readiness conditions must be cleared
Revision reason: owner decisions 2026-10-01 — (1) payments via Paystack as processor, SelahCue as seller, hosted checkout, no card data on SelahCue servers; (2) installers in a private, encrypted, versioned S3-compatible bucket (DigitalOcean Spaces or Hetzner, provider undecided), CI uploads, always-latest with rollback, expiring links; (3) self-service account deletion, data export by request only; (4) generic legal posture — NDPA/GAID citations, DPO, EU/UK representatives, regulator-filing statements and jurisdiction-specific rights lists removed; (5) cloud features name Deepgram and OpenAI (documented in repo) and state that data leaves the church network and can be processed abroad; regulator framing removed.
Facts: Deepgram and OpenAI confirmed from selahcue-stt-cloud/src/lib.rs and selahcue-cloud/src/openai.rs; consent-screen ticket 86akby5hk text not found in repo. Checklist now 58 rows (L-29 split; L-57 seller tax added): 50 gated, 6 deferred as accepted risk, 2 split. Placeholders 52 (13 removed; 4 new: DOWNLOAD_HOSTING_PROVIDER, DOWNLOAD_HOSTING_REGION, DSAR_RESPONSE_TIME, TRANSFER_SAFEGUARDS_SUMMARY). Tickets: bucket 17tnw2b0wqj, downloads 86ak10afm, deletion 17tnw2b0wqk, export 17tnw2b0wqm, billing D2 86ak10g47 (Paystack).
Law checked: no new research; v0.1 ledger retained.
Risks/decisions: accepted regulatory risk recorded in notes §7 (NDPC registration, DPO, transfer mechanics, DPIA, EU/UK reps, DPAs, LIA, cookie notice, COPPA assessment) with revisit triggers; publishing before gated rows are satisfied would make the policies false; Paystack seller tax setup; cloud data abroad; retention/deletion/export; acceptance record; commercial terms open.
Boundary: drafted and saved locally only; not committed, published, signed, filed or sent.
Draft: docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md; docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md; docs/legal/LEGAL-DRAFT-NOTES.md (worktree .claude/worktrees/legal-drafts, branch docs/17tnw2b0q93-legal-privacy-terms-drafts)
```
