# Legal drafting notes — SelahCue platform Privacy Policy and Terms of Service

> **DRAFT — NOT LEGAL ADVICE — REQUIRES REVIEW BY A QUALIFIED LAWYER BEFORE PUBLICATION**
>
> Internal working notes. Version 0.4 (draft, 2026-11-15). Review status: **Draft — facts to confirm.**
>
> **Publication gate.** The policy drafts describe the intended Free desktop release. Clear every
> applicable Gate in §4, fill every factual placeholder and obtain qualified counsel's sign-off
> before publication. Earlier decisions and legal research remain in the history for counsel.

## 1. Matter profile

| Item | Value |
|---|---|
| Brand | SelahCue |
| Contracting legal entity | First Pavilion Technologies, trading as SelahCue. The repository owner confirmed ownership on 2026-10-02. Owner commit `e7566a96f` supplied 4, Law Castle, Taiwo Street, Omida, Abeokuta, Ogun State, Nigeria, registration number 1557879, `support@selahcueapp.com` for support, privacy and legal notices, and `selahcueapp.com`. No entity suffix was supplied. These are owner-supplied draft particulars. |
| Documents | `docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md`, `docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md` and these notes (v0.4). Both policies retain the owner-supplied effective-date entry of October 31, 2026. |
| Requested by | Repository owner via the coordinating agent, Free public website Task 4. Prior delivery reference: ClickUp `17tnw2b0q93`, PR #133. |
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
- **v0.3, review edit (PR #133 review, 2026-10-02).** No version bump and no new decisions. Terms 9.3 no
  longer says that *importing* printed copies of the King James Version is covered by the Crown letters
  patent: the code comment says only "printing within the UK" (the licensing register calls it a Crown/CUP
  patent and an open item for counsel), and "importing" came from a secondary source (T4, §11). §8.3 is new: one list of the facts the policies or these notes rely on that the
  repository cannot confirm, and who must confirm them. §11's introduction no longer says every entry was
  checked, and the §14 audit entries no longer say "Law checked". A second review pass (2026-10-02) corrected
  §8.3 where the merge with `main` had made it stale (86ak10afm, and the ADR-0027 and ADR-0028 files with the
  ticket ids they cite, now appear in the repository) and recorded a read-only ClickUp check of every ticket
  id. It also records that Terms 12.4's "a failed note generation does not use up your allowance" does not
  match ADR-0028 D5 under option A (L-38, §8.3). Nothing in the policies was
  verified by these edits; they only record what is still unverified.
- **v0.3, entity edit (2026-10-02).** No version bump; the policies stay drafts. Owner statement: First
  Pavilion Technologies owns SelahCue, which is a product its developers built, so licensing and the roles
  of licensor, data controller and seller belong to First Pavilion Technologies. `{{LEGAL_ENTITY_NAME}}` is
  filled with that name in both policies, and `{{NDI_ATTRIBUTION_TEXT}}` with the wording the repository
  already shows (§5). Every other placeholder is unchanged, and the launch gate in §4 is unchanged except
  that L-1 and L-51 now record these two fills.

- **v0.4 (2026-11-15).** Factual synchronization for the approved Free public desktop release.
  Section 4 supersedes the v0.3 publication matrix where this release changes scope. Public
  immutable SFO3 desktop downloads replace the account-bound installer proposal. The notes route is
  server-side option C, following an explicit request. The 2026-10-03 draft named Hetzner Cloud in
  Falkenstein, AWS SES, and earlier retention and support values. These are historical draft
  particulars and require operational evidence for the manual Free deployment. Paid features
  remain deferred.

## 3. How to read the drafts

- **`{{PLACEHOLDER}}`** — a fact or decision nobody has supplied. Never publish with one left in.
- The drafts describe intended Free release behaviour. Section 4 distinguishes approved design,
  evidence in source and evidence from the selected release artifacts or deployment.
- New risk allocations and commitments the owner and counsel must accept are listed in §6.
- **The site pages are generated from these files.** After editing either policy, run
  `npm run sync:legal` in `implementation/marketing` and commit the generated files; CI fails if they are out
  of sync. A page stays in draft mode (banner, highlighted placeholders, `noindex`) while any placeholder
  remains, while the DRAFT banner is still in the markdown, or while the version line is not `final`.
  To publish: fill every placeholder, clear every gated row in §4, get lawyer sign-off, delete the DRAFT
  banner, add a `Version X.Y (final, YYYY-MM-DD).` paragraph directly under the title, then regenerate. The
  full procedure is in `implementation/marketing/README.md`.

## 4. Launch-readiness conditions

Read the source and the operational evidence separately. In this table **Gate** means evidence or
approval is still required before publication. **Out of scope** preserves prior feature requirements
for later work. **Deferred** carries forward the prior regulatory posture in §7 for counsel review.
The approved release source is `docs/superpowers/specs/2026-11-14-self-service-public-release.md`.
Desktop, backend and website integration evidence must match the actual packages and deployment.

| # | Gate | Policy clause | What must be true at publication | Current status | Decision or ticket needed |
|---|---|---|---|---|---|
| L-1 | Gate | Privacy header and 13, Terms header and 25, site footer | Use the owner-supplied identity and contacts in §1. Check footer attribution against the intended launch presentation. | Owner commit e7566a96f supplied the particulars. ContactView uses the same mailto. Neither confirms receipt or staffing. | Operations verifies routing and monitoring of the support, privacy and legal-notice mailbox. |
| L-2 | Gate | Privacy 2.3; Terms 9.4 | The desktop app includes a congregation-recording notice the church can display (PRD FR-158) | Unknown (no evidence found) | Ticket needed (FR-158) |
| L-3 | Gate | Privacy 2.4 | Operators can delete a transcript in the operator console, and administrators can set automatic deletion after N days | Partly built (repository supports delete and `retention_days`; console UI not verified) | Engineering to confirm or build |
| L-4 | Gate | Privacy 2.4 | Deleting a transcript deletes its sermon-note draft by default | Built in the repository; the default is flagged in `transcript_repo.rs` as awaiting owner sign-off | Owner decision |
| L-5 | Gate | Privacy 2.4 | The desktop app keeps no audio recordings in the launch build | Built for the current build (no audio store found); PRD FR-153 contemplates raw-audio retention | Engineering to confirm for the launch build |
| L-6 | Gate | Privacy 2.4, 9.1 | The transcript database is encrypted by default; the deck library and media files are not | Built | Re-check if encryption scope changes |
| L-7 | Gate | Privacy 10.1, Terms 2.1 | Confirm the stated minimum age and how it applies to signup. | Drafts state 18. Signup UI does not evidence a separate age confirmation. | Owner and counsel confirm the age requirement and appropriate acceptance control. |
| L-8 | Gate | Terms 2.3 and 23.2 | Confirm acceptance and change-notice wording matches the deployed signup, public download and re-acceptance flows. | SignUpView links both routes and requires a browser checkbox. Neither the local checkbox nor an anonymous download proves a server acceptance record. | Engineering and counsel verify the actual record/version flow and assent wording, including anonymous installer use. |
| L-9 | Deferred | (was Privacy 3.1 sensitive-data condition) | Legal condition for religious-affiliation inference | Placeholder removed; the policy states only that account data is not used to profile beliefs (true by design) | Accepted risk (§7) |
| L-10 | Gate | Privacy 3.2 and 6.1 | Confirm account email provider, sender, and verification and reset delivery. | Account email and SMTP plumbing exist in source. AWS SES was identified in the earlier owner-supplied draft. | Operations verifies the provider, region and sender for the actual deployment, rather than filling from the earlier draft. |
| L-11 | Out of scope | Prior Privacy 3.2 and Terms 8.13 | Paid renewal reminders, billing receipts and invoices. | Deferred with paid service. Licence email claims were removed from this release draft. | Revisit alongside any later payment or licence-notice work. |
| L-12 | Gate | Privacy 3.2 | Marketing email is sent only with recorded consent and every message has an unsubscribe link, or no marketing email is sent | Built in the sense that no marketing email exists | Re-check if marketing starts |
| L-13 | Gate | Privacy 3.3; Terms 6.1–6.4 | The released desktop activates Devices by Administrator sign-in and by enrolment key, stores the device credential in the OS secure store, and verifies signed licence files | Partly built (API built; `selahcue-licensing` client crate exists but is not linked into released binaries; its sign-in activation now uses the native `/v1` routes, 17tnw2b1we2, PR #215, after 86ak5t1gw added them) | 86ak5mn11, 86ak5mn1d, 86ak5mn1t, 86ak5t1gw, 17tnw2b1we2 |
| L-14 | Gate | Privacy 3.3 | The device-identifier method is decided and privacy-reviewed | Undecided (left to the app shell by design, `selahcue-licensing/src/device.rs`) | Engineering + counsel (`{{DEVICE_FINGERPRINT_METHOD}}`) |
| L-15 | Gate | Privacy 3.3; Terms 6.2 | Devices refresh licence files automatically when online, and the server records each Device's last check-in time | Partly built (refresh endpoint exists; no last-check-in field on `Device` or `DeviceToken`) | 86ak5mn1h; schema change needed |
| L-16 | Gate | Privacy 3.3, 6.1 and 7.1, Terms 5.5 and 13.1 | Public anonymous installer delivery from immutable DigitalOcean Spaces SFO3 objects using the website manifest. | Task 1 manifest is unpublished. Release storage verification covers a private object only. No public artifact is asserted. | Release owner verifies all four accepted installers, public manifest and anonymous download from their final URLs. Installer evidence does not establish API or Bible hosting. |
| L-17 | Gate | Privacy 6.2, Terms 6.3 | Portal shows the actual licence, devices and weekly allowance and provides authorized device deactivation. | Current website source has mock account data. Backend Task 8 owns the real account contract and UI integration. | Engineering and operations demonstrate the real account flow. Paid history, cancellation and self-service closure are excluded from these claims. |
| L-18 | Gate | Terms 6.5, 8.13, 14.1 | Licence and Plan changes take effect only at the next Session; activated Devices keep running when the platform is unavailable | Not built (decided: DEC-009, Platform PRD CON-P1, FR-549, NFR-504) | 86ak5mn1t |
| L-19 | Gate | Terms 7.2 | Free-Plan output shows the watermark | Not built (decided: DEC-008, FR-548; grant dimension exists in the catalogue) | Ticket needed |
| L-20 | Out of scope | Prior Privacy 3.4, 4.1 and 6.1, Terms 8.3–8.10 and 13.1 | Paystack hosted checkout, cookies, webhook, payment data, invoices, and refund delivery. | Historical owner decision 2026-10-01. Free signup, activation and download have no payment step. | Revisit with any paid release and validate integration and provider terms. |
| L-21 | Out of scope | Prior Terms 8.1–8.9 and 8.11 | Prices, currencies, billing periods, trial, renewal, proration, refunds, price changes and failed-payment terms. | Current scope is ongoing Free access with no trial. Weekly allowance is specified in L-38. | Revisit for paid service. |
| L-22 | Out of scope | Prior Terms 8.5 | Paid automatic-renewal reminders. | Deferred with paid subscriptions. | Counsel reviews for the actual paid markets when in scope. |
| L-23 | Out of scope | Prior Terms 8.11 | Paid upgrades, downgrades and proration of allowances. | One Free offering for this release. | Revisit with future plans. |
| L-24 | Gate | Terms 6.5 and 15 | Verify how account/security suspension affects devices, activation and optional cloud features. | Earlier soft-suspension design in DEC-010; paid non-payment copy was removed. | Engineering verifies Free suspension behaviour and running-session protection. |
| L-25 | Out of scope | Prior Terms 8.13 | Seven-day paid grace period, reminder and fallback to Free. | Deferred with paid subscriptions. | Revisit with the paid lifecycle. |
| L-26 | Gate | Privacy 3.5, 7 and 8 | Verify deployment hosting and operational log handling. | Historical draft named Hetzner Cloud, Falkenstein. Coolify and the native API hostname establish deployment method and endpoint naming. Installer SFO3 verification is separate. | Owner records actual site/API/database/worker/ephemeral store/log providers and regions and verifies retention and configuration. |
| L-27 | Gate | Privacy 3.5, 3.8 and 8 | Verify which security and cloud decision metadata is retained, its retention, and exclusion of sermon content. | Accepted design excludes audio and sermon content from usage records. Earlier two-year retention is unverified. | Engineering and operations verify record fields, access and lifecycle with actual deployment evidence. |
| L-28 | Gate | Privacy 8 | Verify account, unverified signup, session, credential, audit, licence, usage and support retention and enforcement. | Account source has expiry and maintenance code. Usable lifetime is separate from deletion. Earlier draft periods and scheduled-deletion statements require operational support. | Operations supplies actual periods or meaningful criteria and verifies jobs, logs and backup behaviour. |
| L-29a | Gate | Privacy 11.2, Terms 15.1 | Verify email intake and handling of closure or deletion requests. | Earlier self-service plan 17tnw2b0wqk is unverified and omitted from this draft. No deletion or audit-anonymisation guarantee is stated. | Operations and counsel confirm identity/authority checks, deletion scope, exceptions, workflow and timing. |
| L-29b | Gate | Privacy 11.3 | Verify access and data-copy request handling by email. | Prior export proposal 17tnw2b0wqm and its expiring-link and timing commitments lack operational evidence. | Operations verifies identity checks, export process, secure delivery and timing. |
| L-30 | Gate | Privacy 11.4–11.5 | Verify the general rights-request process and support for church requests about cloud data. | Contact address is supplied. Staffing, timelines and cloud/provider coordination remain unverified. | Operations and counsel confirm the process and timing before completing the placeholder. |
| L-31 | Gate | Privacy 3.6 | Support copy matches how messages are actually received. | ContactView has a disabled, validation-only form and a support mailto. It shows no send, receipt or reply claim. | Operations verifies the email route and monitoring. Reassess if a form goes live. |
| L-32 | Gate | Privacy 3.7 | The launch desktop build has no advertising, analytics, telemetry or crash reporting; its only internet connections are those listed. If it checks for updates automatically, that is added to 3.7 | Built for the current Windows build (verified from direct dependencies); launch build to be re-checked | Engineering re-check at release |
| L-33 | Gate | Privacy 3.7; Terms 13.1 | The speech model still downloads from `huggingface.co` | Built | Re-check at release |
| L-34 | Gate | Privacy 3.7 and 3.9, Terms 9.3 | Verify the accepted desktop build’s bundled text list and any separate remote Bible fetch in that build. | Downloadable Bible content is separate from public SFO3 installers. No Bible hosting or remote availability claim is made. | Engineering verifies actual packaged texts and applicable fetch path; confirm hosting and disclose it if a remote fetch ships. |
| L-35 | Out of scope | Prior Privacy 3.9 and 6.1, Terms 9.3 and 13.1 | Licensed translations, publisher contracts, entitlement and usage reporting. | Earlier design at 86ajpqfyj. Current drafts cover bundled texts. | Verify distribution rights and reporting if licensed translations are added. |
| L-36 | Gate | Privacy 3.8, Terms 12 | Verify per-feature consent, status display, direct Deepgram audio and the requested option C transcript flow with server-only OpenAI credentials. | Approved release spec: Direct Deepgram after opt-in; notes go to SelahCue’s C worker; the native app validates, saves and ACKs. Source input 5 minutes, retrieval up to 15 minutes from staging, physical expiry up to 20 minutes from staging on cleanup failure. Quality/budget qualification remains open. | Engineering demonstrates accepted integrated native/API behaviour and measures staging/cleanup bounds, key custody and exclusions from the durable database, broker, logs, traces and backups. |
| L-37 | Gate (part) / Deferred (part) | Privacy 3.8, 7 and 8, Terms 12.2 | Verify cloud provider terms, processing locations, retention, use of content and relevant transfer safeguards. See §7 for earlier regulatory deferrals. | SelahCue’s staging bounds concern its own temporary storage. Provider retention, processing settings and safeguards remain open. | Owner and qualified counsel verify the actual Deepgram and OpenAI arrangements and fill the provider and transfer text. |
| L-38 | Gate | Privacy 3.8, Terms 8 and 12.4 | 20 cloud transcription minutes and one note per church weekly. One note unit on successful publication, zero on failure. A single original-week credit on backend-confirmed early result loss before expiry or ACK. | Approved C design in the release spec. ACK follows native validation and durable save, and leaves quota unchanged. No credits for expiry, ACK, transient errors or client reports alone. | Engineering and operations verify end-to-end weekly accounting, durable save/ACK and content-free delivery credit/audit records under failure. |
| L-39 | Gate | Privacy 3.10 | No sale, no behavioural advertising, no solely automated decisions with significant effects | Built (true today) | Re-check at release |
| L-40 | Gate | Privacy 4.1 and 4.4 | Verify browser cookies and local storage and reconcile the stated lifetimes and scope. | Browser account code uses the session cookie and same-origin CSRF and a local session hint. No Paystack cookie claim remains. | Operations verifies headers, storage, Google Fonts and analytics in the actual deployment. |
| L-41 | Gate | Privacy 4.3; Terms 13.1 | Either the site still loads Google Fonts (disclosure stays), or the font is self-hosted and both Google Fonts passages are deleted | Built (the site loads Google Fonts today); self-hosting recommended | Owner decision |
| L-42 | Deferred | (Privacy 4) | GAID Art. 7(l)-style homepage cookie notice | The policy does not claim a notice | Accepted risk (§7) |
| L-43 | Deferred | (was Privacy 5.1 LIA reference) | Legitimate Interest Assessment | Placeholder removed; the policy no longer claims an assessment | Accepted risk (§7) |
| L-44 | Deferred | (Privacy 6.1) | Written data processing agreements with hosting, storage and email providers beyond their standard terms | The policy now describes providers only as running parts of the service | Accepted risk (§7) |
| L-45 | Gate (part) / Deferred (part) | Privacy 7.2 | Complete the factual transfer-safeguards disclosure. See §7 for earlier regulatory deferrals. | The prior draft’s provider-commitments language does not establish deployed safeguards. | Operations and qualified counsel verify approach for the actual providers and processing locations. |
| L-46 | Deferred | (was Privacy header, 11.6, 13) | NDPC registration as a data controller of major importance; DPO; EU and UK representatives | Placeholders and sections removed; nothing is claimed | Accepted risk (§7) |
| L-47 | Gate | Privacy 9.1 | Verify deployment transport security, credential protections, lockout and rate-limiter setup. | API and same-origin proxy controls are in source. Public installer delivery in L-16 now has its own gate. | Operations verifies HTTPS and the actual deployment settings. |
| L-48 | Gate (part) / Deferred (part) | Privacy 9.2 | **Gate:** an internal breach-response procedure exists so affected users are told without undue delay and authorities are informed where the law requires. **Deferred:** NDPC-specific 72-hour notification mechanics | Unknown | Operations; accepted risk (deferred part, §7) |
| L-49 | Out of scope | Prior Terms 5.4 | Installer access after a paid plan ends. | Deferred with paid plans. Anonymous Free delivery and release selection are tracked in L-16. | Revisit with any paid scope. |
| L-50 | Gate | Terms 6.5, 14.3, 15.2, 16.1, 17.3, 19, 22.2 and 23.2 | Owner and qualified counsel accept or amend the proposals in §6. | This revision removed paid refund commitments and narrowed the rights handling claims. Remaining proposed allocations need approval. | Owner and counsel. |
| L-51 | Gate | Terms 5.6, 13.1 | Open-source licence notices and the NDI attribution are published | Not built | Engineering (`{{THIRD_PARTY_NOTICES_LOCATION}}`; the NDI attribution wording is filled in Terms 13.1, §5) |
| L-52 | Gate | Terms 10.1 | Scripture detection requires operator approval by default; AI notes show the AI-generated label and fabrication warning | Partly built (label and warning in `selahcue-core`/`selahcue-cloud`; the detection default is specified in PRD FR-115 but not verified in code) | Engineering to confirm |
| L-53 | Gate | Terms 14.2, Privacy 3.6 and 11 | Verify the support mailbox is staffed for the intended service and rights requests. | Address is owner-supplied. The prior fixed response targets lack evidence and were removed. | Operations confirms mailbox handling and rights timing. |
| L-54 | Gate | Terms 22 | Confirm the governing law and forum before publication | Nigerian law and the courts of Abeokuta, Ogun State, Nigeria are drafted. Owner and counsel review is pending. | Owner + counsel |
| L-55 | Out of scope | Privacy 1.3 and 3.11, Terms 1.2 | Controller app release and store policy operation. | Separate Controller documents remain in source. These drafts make no Controller distribution claim. | Reconcile with the separate mobile release. |
| L-56 | Gate | Website pages | Confirm home, pricing/FAQ copy, download, contact, signup and linked legal routes match the Free public release. | Website source exposes separate signup-linked /privacy and /terms. Public manifest remains unpublished. | Verify actual accepted build and manual deployment, including no paid or unverified shipping claims. |
| L-57 | Out of scope | Prior Terms 8.3 and 8.9 | Paid service invoices and tax collection and remittance. | Historical paid-service readiness gate. No payments are collected in this release. | Owner and accountant verify requirements before paid service. |

All 58 gate IDs are retained, including prior rows now out of scope. Keep actual package/deployment
proof and counsel sign-off with this matrix as evidence arrives.

## 5. Placeholder register

At Task 4 BASE, neither policy contained a factual placeholder token. Both contained the explanatory
`{{PLACEHOLDER}}` in the draft warning. The v0.3 50-token register predated owner commit `e7566a96f`
and did not reflect the draft text. This revision makes the following unresolved operational fields
visible in the Privacy draft. The Terms draft retains its warning and the applicable gates in §4.

| Current token | What completes it | Gate |
|---|---|---|
| `{{TRANSACTIONAL_EMAIL_PROVIDER}}` | Confirm provider and operating setup for account email | L-10 |
| `{{CLOUD_PROVIDER_RETENTION_AND_USE}}` | State actual Deepgram audio and OpenAI transcript/output retention and use | L-37 |
| `{{SERVICE_HOSTING_LOCATIONS}}` | Verify actual site, account API, database, notes worker, and logging locations and providers | L-26 |
| `{{TRANSFER_SAFEGUARDS_SUMMARY}}` | Confirm factual safeguards and suitable disclosure with counsel | L-37, L-45 |
| `{{ACCOUNT_RETENTION}}` | Verify closure and unverified-account retention | L-28 |
| `{{SESSION_RECORD_RETENTION}}` | Verify deletion or retention of sign-in session records | L-28 |
| `{{CREDENTIAL_RECORD_RETENTION}}` | Verify deletion or retention of used and expired email credential records | L-28 |
| `{{OPERATIONAL_LOG_RETENTION}}` | Verify rates/counters and access, proxy, worker and operational log classes and retention | L-26, L-28 |
| `{{SECURITY_AND_USAGE_RETENTION}}` | Verify retention of audit, licence, device and content-free usage records | L-27, L-28 |
| `{{SUPPORT_RETENTION}}` | Verify support-message handling and retention | L-28 |
| `{{RIGHTS_REQUEST_PROCESS_AND_TIMING}}` | Verify request response, identity, deletion, copy and escalation procedures and timing | L-29a, L-29b, L-30 |

The entity particulars, contact address and effective-date entry remain as supplied in §1.
The existing NDI attribution remains in Terms 13.1. See L-51 for package notice evidence.

## 6. Proposed risk allocations and commitments

The clause text is clean. These clauses are new allocations of risk, or commitments beyond what is
decided. Each needs owner and counsel acceptance (checklist row L-50) before publication.

| Clause | What it does | Why it is a proposal |
|---|---|---|
| Terms 17.3 | Caps SelahCue's liability at the greater of 12 months' fees and US$25,000 | A risk allocation; the floor protects free users' claims from being capped at zero |
| Terms 19 | Customer indemnity for infringing content and unlawful recording | A risk allocation; may be resisted by churches; can be deleted |
| Terms 6.5 | A licence or Plan change never interrupts a running Session | Decided product rule (CON-P1, FR-549); publishing it makes it a contractual promise |
| Terms 14.3 | Ability to change, add or remove features | Review alongside the Free service description and consumer-rights savings. Earlier paid refund language is deferred. |
| Terms 15.2 | 14-day cure period before termination for breach | Process commitment |
| Terms 16.1 | Warranty of reasonable care and skill | A contractual warranty for everyone |
| Terms 22.2 | 30 days of good-faith negotiation before formal disputes | Process commitment |
| Terms 23.2 | Administrators re-accept material changes and the service records acceptance | Requires L-8 evidence. Earlier paid refund language is deferred. |
| Privacy 11.2 | Account closure and deletion requests by email | Verify the actual handling under L-29a. Earlier audit anonymisation was a design proposal. |

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

## 8. Historical v0.3 fact-to-source table

This section records the October draft review. The current Free release matrix in §4 supersedes its
feature, clause-reference and status entries where they differ.

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
| T4 | In the UK, printing of the KJV is subject to Crown letters patent (Terms 9.3). The earlier draft also said "importing printed copies"; that was removed | `selahcue-scripture/src/lib.rs` ~L96 ("covers printing within the UK"); `docs/research/LICENSING-REGISTER.md` §1 table ("Crown copyright in UK (Cambridge/CUP patent)") and §7 item 4 ("Crown/CUP patent; confirm before UK distribution", marked Legal, confidence Med), which do not say what the patent covers; ebible.org (secondary, the only source for "importing") | D for printing within the UK (the code comment only); the scope of the patent beyond that is **unverified, counsel to confirm** (§8.3) |
| T5 | Operator approval of scripture suggestions by default | PRD FR-115/116 | D (L-52) |
| T6 | AI-generated label and fabrication warning | `selahcue-core/src/providers.rs` (`AI_GENERATED_LABEL`, `FABRICATION_DISCLOSURE`); `selahcue-cloud/src/lib.rs` | V |
| T7 | Watermark on the free Plan | DEC-008; FR-548 | D (L-19) |
| T8 | 7-day grace, then the free Plan from the next Session | DEC-009; FR-521/549 | D (L-25) |
| T9 | Soft suspension | DEC-010; FR-504/510; `license_keys/models.py` (`prior_status`) | D/partly V (L-24) |
| T10 | A downgrade keeps Devices; limit applied at Session start | DEC-009; FR-550 | D (L-23) |
| T11 | Allowance rules on upgrade and downgrade | Owner decision 2026-09-27 | M (L-23) |
| T12 | Failed note generation not charged; retry rule | Owner decision D7 as amended: ADR-0028 D5 (in the repository, **Proposed**, not Accepted) and ClickUp tickets 17tnw2az0gj and 17tnw2az0gn (read 2026-10-02). "Not charged" holds exactly only under option C; under option A the ADR says it cannot be fully kept (§8.3) | D (Proposed ADR); the claim as drafted in Terms 12.4 is not supported under option A (L-38) |
| T13 | Activation by sign-in or enrolment key; signed offline licence file | DEC-004/005/011; `implementation/api/README.md` | V (server) |
| T14 | Session-boundary rule; offline when the platform is down | Platform PRD CON-P1, FR-549, NFR-504 | D (L-18) |
| T15 | SelahCue is the seller; Paystack processes payments | Owner decision | O (L-20, L-57) |
| T16 | Always-latest downloads, rollback of a bad Release, latest Release after a Plan ends | Owner decision | O (L-16, L-49) |
| T17 | Trial organisation created at sign-up | DEC-007 product answers (TRIAL status) | V |
| T18 | Third parties: NDI, Hugging Face, Google Fonts, Deepgram, OpenAI | `selahcue-desktop/Cargo.toml`; `selahcue-stt/src/model.rs`; `index.html`; P28 sources | V |

### 8.3 Facts the repository cannot confirm (consolidated flags)

The facts below are stated in the policy text or relied on in these notes, and the repository cannot
confirm them. The repository was searched (the whole tree, including `docs/` and `implementation/`, after
merging `main` at df9db6c, re-run 2026-10-02) for each one; "no hit" means that search found nothing outside
`docs/legal/`. The ClickUp ids were also looked up read-only in ClickUp on 2026-10-02. `main` was merged again
after PR #111 landed (2026-10-02, 11:44 UTC); the rows below are as of that merge. This list does not verify the facts themselves: it names who must confirm each item, from a
primary source, before publication. The
O, M and I flags are the ones defined at the top of §8; "Verify on X" follows §11's convention.

| Item | Where it appears | What the repository shows | Flag | Who confirms, and from what |
|---|---|---|---|---|
| **Paystack** is the payment processor and SelahCue is the seller; Paystack's hosted checkout, cookies and scripts; what Paystack sends us | Privacy 3.4, 4.1, 6, 7.1; Terms summary, 8.3, 8.7, 13.1; P22, T15, L-20 | No hit for Paystack in `docs/` or `implementation/` outside these drafts. `DECISION-LOG.md` has no record of it. The Platform PRD's D2 entry (ticket 86ak10g47) lists Stripe, Paddle and FastSpring-class options and does not name Paystack. ClickUp ticket 17tnw2b0wqk (read 2026-10-02) mentions "any active Paystack subscription (once billing exists, 86ak10a7n)", so ClickUp names Paystack in a ticket (the id 86ak10a7n is as quoted there and was not itself looked up), but that is not a decision record. The delivery ticket for these drafts, 17tnw2b0q93, says in its scope "Do not state a payment processor as fact"; v0.3 states Paystack on the owner's decision of 2026-10-01. Paystack's own terms, privacy policy and cookie list were not read (§11) | O | Owner records the decision against D2 and in `DECISION-LOG.md`; engineering confirms the checkout cookies and `{{PAYMENT_DATA_RECEIVED}}` from the integration; counsel reads Paystack's terms |
| **ADR-0028** (direct-to-provider credentials: the note-retry rule `{{RETRY_ALLOWANCE_TERMS}}` and the notes route `{{NOTES_ROUTE}}`) | These notes: L-38, §5, T12. The policies carry the two placeholders, and Terms 12.4 states an allowance rule (see the caution) | `docs/architecture/adr/ADR-0028-direct-to-provider-credentials-and-usage-attribution.md` and ADR-0027 are now in the repository (PR #111 merged to `main` on 2026-10-02), both **Proposed**, not Accepted; ADR-0028 was at revision 5 and ADR-0027 at revision 6 when read, and revisions keep changing, so none is pinned here. ADR-0028 D5 records the owner's D7 amendment: one retry per notes session, within 10 minutes, against the same reservation; a failed generation and its retry together cost one unit; if the retry also fails the unit is still charged. ADR-0028 D4 chooses option A for notes (the desktop calls OpenAI directly with a client secret), subject to an OpenAI Realtime spike (ClickUp 17tnw2az0n2) that had not reported, and option C (server-side) if the spike fails. **Caution for Terms 12.4:** ADR-0028 D5 says owner D7's "failures are never charged" cannot be fully kept under option A, because the server cannot see a generation that failed partway, and holds exactly only under option C. Terms 12.4's sentence "A note generation that fails because of an error on our side or our provider's side does not use up your allowance" is therefore not accurate under option A. The ClickUp tickets 17tnw2az0gj and 17tnw2az0gn carry the same amendment | D (documented in a Proposed ADR, not Accepted); the spike is pending | Owner and counsel reword or qualify that Terms 12.4 sentence once the route is known, and fill `{{RETRY_ALLOWANCE_TERMS}}` from ADR-0028 D5; engineering fills `{{NOTES_ROUTE}}` after the spike |
| **Download-bucket provider**: DigitalOcean Spaces or Hetzner Object Storage; a private, encrypted, versioned S3-compatible bucket; CI uploads; expiring links | These notes only (v0.3 revision, L-16, §5, P20, T16). The policies carry `{{DOWNLOAD_HOSTING_PROVIDER}}` and `{{DOWNLOAD_HOSTING_REGION}}` and name neither provider | No hit for DigitalOcean or Hetzner anywhere outside these notes. `downloads:prepare` and `:complete` return 501 (L-16). No bucket, CI upload step or expiring-link code exists in the tree. ClickUp 17tnw2b0wqj (read 2026-10-02) records the owner decision of 2026-10-01 to use DigitalOcean Spaces or Hetzner Object Storage and leaves the choice open | O | Owner chooses the provider and region; engineering confirms the bucket properties and the delivery path |
| **ClickUp ids** that no other repository document mentions: 17tnw2b0wqj, 17tnw2b0wqk, 17tnw2b0wqm (O); 86akby5hk (consent-screen ticket); 17tnw2b0q93 and 17tnw2b0x3g (this PR pair's own delivery tickets) | These notes only (§4 "Decision or ticket needed" column, §8, §12, §14). The policies cite no ticket id | For each id in the first column: no hit in the merged tree outside these notes (grep re-run 2026-10-02). **86ak10afm (downloads backend, L-16, L-49) is not in that list:** since `main` was merged it appears in `docs/delivery/goals/17tnw2b0q9j-marketing-gates-download.md` (lines 32, 36 and 52), `implementation/marketing/README.md` (line 53) and `implementation/marketing/src/views/DownloadView.vue` (line 23), which call it the downloads backend whose two endpoints return 501. 17tnw2az0gd (catalogue; ADR-0027 only) and 17tnw2az0gj, 17tnw2az0gn and 17tnw2az0n2 (ADR-0027, ADR-0028 and `docs/delivery/goals/ARCH-17tnw2az0g6-direct-to-provider.md`) were notes-only until PR #111 merged and now also appear there. The other ids cited in §4 (for example 86ak5mn11, 86ak5mn1t, 86ak5t1gw, 86akby3xu, 86ajpqfyj, 86ak10g47) also appear in other repository documents. Read-only ClickUp lookup, 2026-10-02: every id in the first column, 86ak10afm, 17tnw2az0gd, 17tnw2az0gj, 17tnw2az0gn and 17tnw2az0n2, resolves to a ticket whose title and scope match how §4 uses it; no ticket was edited. For 86akby5hk the ticket text is in ClickUp, not in the repository | O or M, as marked in §4. Existence confirmed in ClickUp 2026-10-02; still not an in-repo record | Owner or whoever maintains ClickUp keeps the tickets and §4 in step as the work proceeds |
| **Terms 9.3, KJV and the UK Crown letters patent** | Terms 9.3; T4 | Only the code comment (`selahcue-scripture/src/lib.rs:96`) says the patent "covers printing within the UK". `LICENSING-REGISTER.md` says "Crown copyright in UK (Cambridge/CUP patent)" (§1 table) and "Crown/CUP patent; confirm before UK distribution" (§7 item 4, marked Legal): it does not limit the right to printing, and it lists the UK position as an open item for counsel. "Importing" came from ebible.org and is no longer in the Terms | D (printing); I (anything beyond printing) | Counsel: does the patent reach importing, distribution or on-screen display, and does the Terms need to say more than printing. Verify with the rights holder |
| **CJEU C-184/20** (1 August 2022) on indirectly revealed special-category data | §10.2 | An external authority, so nothing in the repository bears on it. The §11 ledger records it as "identified by search, not opened"; only a press-release URL is cited | I | Verify on curia.europa.eu or EUR-Lex against the judgment text before any reliance |
| **DUAA 2025 commencement**: Part 5 changes from 5 February 2026; s.103 on 19 June 2026 | §10.3; L-30; §7 | The notes themselves call the s.103 date "secondary source, unverified". The commencement regulations were not read (§11) | I | Verify on legislation.gov.uk (commencement regulations) |
| **COPPA dates**: amended Rule effective 23 June 2025, compliance by 22 April 2026 | §10.4; §7 | Law-firm summary only. The COPPA Rule text was not read (§11) | I | Verify against the Federal Register notice or ftc.gov |
| **NDPC fee tiers and thresholds**: UHL, EHL and OHL, the ₦250,000 and ₦100,000 fees, and the 200-data-subject threshold | §10.1; §7 | §10.1 attributes the tiers and fees to NDPA s.44 and GAID Schedule 7, and the §11 ledger lists Schedule 7 under the GAID PDF on ndpc.gov.ng. Whether the amounts were actually read there is not recorded, and the NDPA text itself came from a DataGuidance mirror. Treat them as attributed to GAID Schedule 7, not confirmed. Nothing in the policies depends on them | I | Verify on ndpc.gov.ng against the current fee schedule and the Act as published |

## 9. Historical claims on the old stub pages

This is an October review record. Current ContactView uses a disabled validation-only form and a
support mailto. The previously described fake send/reply behaviour is absent from the Task 4 BASE.

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

The October draft considered Nigerian law with the courts of Lagos State or arbitration seated in
Lagos under the AMA 2023. Terms 22.1–22.2 now draft Nigerian law and the courts of Abeokuta, Ogun
State, Nigeria. Terms 22.3 preserves applicable consumer rights to bring a claim where the consumer
lives. Owner and counsel review of the drafted law and forum remains pending under L-54.

## 11. Source ledger

Retrieved or searched 2026-10-01, with no new legal research for v0.3. That is not the same as verified: the entries that were not opened, or that rest on a secondary source or a mirror, are flagged in the Authority column and listed in §8.3 and in the verification gaps below.

| Proposition | Authority | Provision | URL | Drafting implication |
|---|---|---|---|---|
| NDPA scope, principles, bases, notice, DPIA, processors, sensitive data, children, rights, security, breach, transfers, registration, complaints | Nigeria Data Protection Act 2023 | ss.2, 24–31, 34–46, 65 | https://www.dataguidance.com/sites/default/files/data_protection_act_2023.pdf (mirror of the Act; page images read) | §10.1; accepted risks §7; the registration tiers and fee amounts in §10.1 are attributed to GAID Schedule 7 and are not confirmed (§8.3) |
| GAID: NDPR displaced; compliance measures; DCMI; consent cases; cookies; LIA; information; DPIA; third-party sharing; retention | GAID 2025 | Arts. 3, 7–10, 18, 19, 21, 26–28, 41, 49; Schedule 7 | https://ndpc.gov.ng/wp-content/uploads/2025/07/NDP-ACT-GAID-2025-MARCH-20TH.pdf | §10.1; §7 |
| GAID effective 19 September 2025 | Secondary (law firm) | — | https://www.banwo-ighodalo.com/grey-matter/are-you-gaid-2025-ready-navigating-nigerias-gaid-2025-what-your-organisation-needs-to-know-how-bi-can-support-your-compliance-journey/ | Verify on ndpc.gov.ng |
| GDPR scope, child consent, special categories, response time, notice, representative | GDPR | Arts. 3(2), 8(1), 9, 12(3), 13, 27 | https://gdpr-info.eu/ (unofficial mirror; EUR-Lex not retrievable) | §10.2 |
| Indirect revelation of special-category data | CJEU C-184/20 (Grand Chamber, 1 August 2022) | — | https://curia.europa.eu/jcms/upload/docs/application/pdf/2022-08/cp220133lt.pdf (press release; identified by search, not opened) | §10.2; verify against the judgment itself before any reliance (§8.3) |
| Google Fonts and IP disclosure | LG München I, 3 O 17493/20 (20 January 2022) | — | Secondary: https://www.ihk.de/bergische/recht-und-steuern/wettbewerbsrecht/google-fonts-5646176 | L-41 |
| DUAA 2025 | Data (Use and Access) Act 2025 | ss.103, 112, 142 | https://www.legislation.gov.uk/ukpga/2025/18/contents; https://www.gov.uk/guidance/data-use-and-access-act-2025-plans-for-commencement | §10.3 |
| s.103 commenced 19 June 2026 | Secondary | Commencement No. 6 Regulations 2026 | https://digitalpolicyalert.org/event/40956-data-use-and-access-act-2025-commencement-no-6-and-transitional-and-saving-provisions-regulations-2026-section-103-data-protection-complaints-including-data-protection-regulation-enter-into-force | Verify on legislation.gov.uk (§8.3) |
| CCPA revenue threshold $26,625,000 | California Privacy Protection Agency | CPI adjustment, 1 January 2025 | https://www.cppa.ca.gov/regulations/cpi_adjustment.html | §10.4 |
| COPPA amendments: effective 23 June 2025, compliance by 22 April 2026 | Secondary (law firm) | 16 CFR Part 312 | https://www.whitecase.com/insight-alert/unpacking-ftcs-coppa-amendments-what-you-need-know | §10.4; the Rule text was not read; verify the dates against the Federal Register notice or ftc.gov (§8.3) |
| FCCPA provisions (headings only) | FCCPA 2018 | ss.125, 127, 128, 137, 142, 144 | https://fccpc.gov.ng/wp-content/uploads/2022/07/FCCPA-2018.pdf | Terms 18 |
| AMA 2023 replaced ACA 1988 | Secondary (law firm) | — | https://www.linklaters.com/insights/blogs/arbitrationlinks/2023/may/nigeria-revises-its-arbitration-act | §10.5 |
| KJV Crown letters patent (UK only) | Secondary (ebible.org); repository code comment (`selahcue-scripture/src/lib.rs` ~L96) and `docs/research/LICENSING-REGISTER.md` | — | https://ebible.org/kjv/copr.htm | Terms 9.3 now says printing only, which is what the code comment at `selahcue-scripture/src/lib.rs:96` says; the register calls it a Crown/CUP patent and an open item for counsel. "Importing" came from ebible.org and was removed. Counsel to confirm the scope of the patent (§8.3, T4) |

**Verification gaps.** I could not retrieve EUR-Lex directly; the NDPA text came from a DataGuidance
mirror; I did not read the Child's Rights Act, the FCCPA's substantive text, the COPPA Rule, the DUAA
commencement regulations, the ePrivacy Directive, consumer-contract law, automatic-renewal laws,
Paystack's, Deepgram's or OpenAI's current terms, or Django's default CSRF cookie age. The text of
consent-screen ticket 86akby5hk was not found in the repository.

Also unverified, and now listed with an owner in §8.3: the CJEU judgment in C-184/20 (a press-release
URL was found by search and not opened); the DUAA commencement dates (secondary source); the COPPA dates
(law-firm summary); the NDPC registration tiers and fee amounts (attributed to GAID Schedule 7, not confirmed); the
scope of the KJV Crown letters patent beyond printing; and Paystack as the chosen provider and the
download-bucket providers, which the repository does not contain. ADR-0028 is now in the repository but only as
Proposed, with the OpenAI notes route pending a spike, so Terms 12.4's allowance sentence has no accepted basis
(§8.3). The ClickUp ids that no other repository document mentions were looked up read-only
in ClickUp on 2026-10-02 and exist; that shows the tickets exist, not that what they record is built or true.

## 12. Historical v0.3 open questions and risks

These entries reflect the October draft. Use §4 and §5 for current release gates and open facts.

1. **Entity, contacts and domains.** No repository file named a legal entity until the owner's statement of
   2026-10-02 (First Pavilion Technologies, now in both policies); its registered address, registration
   number and legal form are still missing, and contact addresses span three domains. *Owner:* supply the
   missing entity details and choose one domain and mailbox set (L-1).
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

## 14. Historical ClickUp audit entries

No ClickUp writes were made in any session, at the coordinator's direction. Record the entries in order on
the matter task in the Legal Audit Log list (`1400430000002076`); check for an existing SelahCue
privacy/terms matter task first, and set its status to `awaiting facts / decisions`.

**Entry 1 — v0.1**

```
[AUDIT] SelahCue — Platform Privacy Policy + Terms of Service — created — 2026-10-01
Entity: {{LEGAL_ENTITY_NAME}} (unconfirmed; owner described as First Pavilion, Lagos)   Jurisdiction(s): Nigeria (NDPA 2023, GAID 2025) primary; EU GDPR, UK GDPR/DUAA 2025, US (CCPA/COPPA) flagged   Requested by: repo owner via coordinating agent (delivery ticket 17tnw2b0q93)
Version/status: v0.1 — Draft — facts to confirm
Facts: confirmed from code — local-only desktop data; transcript DB encrypted by default; on-device STT with model download from huggingface.co; release builds exclude cloud STT/AI and do not activate; account fields; cookies; Google Fonts; no analytics; billing not built; no account deletion/export; acceptance not recorded. Assumed — Nigerian entity in Lagos. Open placeholders — 52.
Law retrieved or searched, not all verified (see §8.3, §11): NDPA 2023; GAID 2025; GDPR Arts 3, 8, 9, 12, 13, 27; CJEU C-184/20 (press release found by search, judgment not opened); LG München I 3 O 17493/20; DUAA 2025 (commencement regulations not read); CCPA threshold; COPPA amendments (Rule text not read); FCCPA 2018 headings; AMA 2023 — retrieved or searched 2026-10-01.
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
Law retrieved or searched, not all verified (see §8.3, §11): as v0.1; no new research.
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
Law retrieved or searched, not all verified (see §8.3, §11): no new research; v0.1 ledger retained.
Risks/decisions: accepted regulatory risk recorded in notes §7 (NDPC registration, DPO, transfer mechanics, DPIA, EU/UK reps, DPAs, LIA, cookie notice, COPPA assessment) with revisit triggers; publishing before gated rows are satisfied would make the policies false; Paystack seller tax setup; cloud data abroad; retention/deletion/export; acceptance record; commercial terms open.
Boundary: drafted and saved locally only; not committed, published, signed, filed or sent.
Draft: docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md; docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md; docs/legal/LEGAL-DRAFT-NOTES.md (worktree .claude/worktrees/legal-drafts, branch docs/17tnw2b0q93-legal-privacy-terms-drafts)
```

## 15. Local audit entry

[AUDIT] SelahCue — Platform Privacy Policy and Terms of Service — factual revision and handoff — 2026-11-15

- Entity and jurisdiction: First Pavilion Technologies, trading as SelahCue, Abeokuta, Nigeria.
  The wider jurisdiction analysis is retained in §10 for counsel.
- Requested by the repository owner via the coordinating agent. Version 0.4, draft — facts to confirm.
- Basis: approved Free release spec, owner-provided particulars in `e7566a96f`, and source verification
  against website BASE `ec6bcc585993cb6df4b84717242bb22ca6b7adf0`. The operating and counsel gates are
  in §4 and the live factual tokens are in §5.
- Legal research: this revision aligns existing draft facts. Section 11 records the earlier research.
  Current applicability, provider arrangements and approval remain for qualified counsel.
- Evidence: the two source drafts and generated pages, with local Task 4 verification and delivery
  evidence in the coordinator’s ledger.
- Scope: local drafts and review evidence only. Nothing published, signed, filed or sent.
- Pending ClickUp: daily quota exhausted. Check the designated legal-audit list for the existing SelahCue
  platform-policy matter, then log this v0.4 revision and the draft paths with status
  `awaiting facts / decisions` when audit access and authorization are available.
