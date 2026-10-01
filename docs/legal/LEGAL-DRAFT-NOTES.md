# Legal drafting notes — SelahCue platform Privacy Policy and Terms of Service

> **DRAFT — NOT LEGAL ADVICE — REQUIRES REVIEW BY A QUALIFIED LAWYER BEFORE PUBLICATION**
>
> Internal working notes. Not for publication. Version 0.2, 2026-10-01, prepared by an AI drafting
> assistant (not a lawyer). Review status: **Draft — placeholders and launch-readiness conditions
> must be cleared.**

> **HARD LAUNCH GATE.** At the owner's direction, both policies (v0.2) describe SelahCue as it will
> operate at launch, in the plain present tense. Many of the features they describe are not built
> today. **Publishing either policy while any row in §4 is unsatisfied would make the policy false**,
> exposing SelahCue to misrepresentation claims and to breach of the NDPA transparency duties
> (s.24, s.27). The §4 checklist is therefore a hard launch gate: every row must be satisfied, and
> every `{{PLACEHOLDER}}` filled, before either document is published.

## 1. Matter profile

| Item | Value |
|---|---|
| Brand | SelahCue |
| Contracting legal entity | **Unknown** — `{{LEGAL_ENTITY_NAME}}`. Owner described as First Pavilion (firstpavitech.com), Lagos; the exact entity, its registration and its relationship to the SelahCue brand are not confirmed anywhere in the repository. |
| Documents | `docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md` (v0.2), `docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md` (v0.2), this file (v0.2) |
| Requested by | Repository owner, via the coordinating agent; ClickUp delivery ticket `17tnw2b0q93`; PR #133 |
| Audience | Churches and other organisations worldwide; the staff and volunteers who create accounts; website visitors |
| Primary jurisdiction | Nigeria (NDPA 2023 + NDPC GAID 2025) |
| Secondary jurisdictions | EU GDPR; UK GDPR/DPA 2018/PECR as amended by DUAA 2025; US exposure (CCPA, COPPA) flagged |
| Existing documents kept unchanged | `docs/legal/PRIVACY.md` and `docs/legal/TERMS.md` (SelahCue Controller mobile app) |

## 2. Revision history

- **v0.1 (2026-10-01).** First drafts. Features that were designed but not built sat in feature-gated
  blocks inside the policies, with inline "confirm" markers.
- **v0.2 (2026-10-01).** Revised on owner direction: the policies are written for the launch state.
  - All feature-gated blocks and hedging were removed. Device activation, licence check-ins, the
    customer portal, billing, downloads, cloud transcription, AI notes, licensed translations, and
    account deletion and export are described as live features.
  - Terms Part C is now a full billing section: plans, trials, merchant and payment, Billing Periods,
    renewal, cancellation, refunds, price changes, taxes, invoices, upgrades and downgrades, failed
    payments and suspension, and the end of a paid Plan.
  - Undecided business facts stay as `{{PLACEHOLDER}}` tokens; nine new tokens were added (§5).
  - Every statement that is true only once something is built or decided moved into the §4
    launch-readiness checklist, including the inline "confirm" markers from v0.1.
  - **[PROPOSED] flags:** I moved them out of the clause text into §6 and kept the clauses clean.
    Acceptance of each proposal is gated by checklist row L-50, so the clauses cannot be published
    without an explicit owner/counsel decision.
  - New launch-state statements: the acceptance record, an age confirmation at sign-up, payment
    provider cookies, publisher reporting, the in-app transcription notice, licence check-in
    times, refused cloud-feature requests recorded, and security updates available after a paid
    Plan ends. Each has a checklist row.

## 3. How to read the drafts

- **`{{PLACEHOLDER}}`** — a fact or decision nobody has supplied. Never publish with one left in.
- Everything else in the policies is written as true at launch. Whether it is actually true is
  tracked in §4, not in the policy text.
- New risk allocations and commitments the owner and counsel must accept are listed in §6.

## 4. Launch-readiness conditions (hard launch gate)

Status key, from my verification of this worktree on 2026-10-01: **Built** = present in code and
config · **Partly built** · **Not built** · **Undecided** = an owner or counsel decision is needed
first · **Unknown** = could not be verified from the repository. Ticket IDs marked (M) come from the
owner's project memory notes rather than in-repo documents.

| # | Policy clause | What must be true at publication | Current status | Decision or ticket needed |
|---|---|---|---|---|
| L-1 | Privacy header & 13; Terms header & 25; site footer | Legal entity, address, registration number, privacy, support and legal-notice mailboxes are real and monitored; one email domain is used consistently; the footer names the entity | Undecided (no entity named; site uses `selahcue.app`, API uses `selahcue.com` and `firstpavitech.com`) | Owner decision |
| L-2 | Privacy 2.3; Terms 9.4 | The desktop app includes a congregation-recording notice the church can display (PRD FR-158) | Unknown (no evidence found) | Ticket needed (FR-158) |
| L-3 | Privacy 2.4 | Operators can delete a transcript in the operator console, and administrators can set automatic deletion after N days | Partly built (repository supports delete and `retention_days`; console UI not verified) | Engineering to confirm or build |
| L-4 | Privacy 2.4 | Deleting a transcript deletes its sermon-note draft by default | Built in the repository, but the default is flagged in `transcript_repo.rs` as awaiting owner sign-off | Owner decision |
| L-5 | Privacy 2.4 | The desktop app keeps no audio recordings in the launch build | Built for the current build (no audio store found); PRD FR-153 contemplates raw-audio retention | Engineering to confirm for the launch build |
| L-6 | Privacy 2.4, 9.1 | The transcript database is encrypted by default; the deck library and media files are not | Built | Re-check if encryption scope changes |
| L-7 | Privacy 3.1, 10.1; Terms 2.1 | Sign-up asks the user to confirm the minimum age | Not built (no age field or check) | Ticket needed; owner sets `{{MINIMUM_ACCOUNT_AGE}}` |
| L-8 | Privacy 3.1; Terms 2.3, 23.2 | Acceptance of the Terms and Privacy Policy is recorded server-side with version, timestamp and user, at sign-up and on re-acceptance of material changes | Not built (the checkbox is checked only in the browser) | Ticket needed |
| L-9 | Privacy 3.1 | The legal condition for any sensitive-data inference is decided; if explicit consent is chosen, it is captured and recorded at sign-up | Undecided | Counsel decision (`{{SENSITIVE_DATA_CONDITION}}`) |
| L-10 | Privacy 3.2 | Transactional email runs through the chosen provider, and the sender domain matches L-1 | Partly built (SMTP and Celery seam built; provider undecided; default sender `noreply@selahcue.com`) | Owner decision |
| L-11 | Privacy 3.2; Terms 8.13 | Licence and plan emails (renewal reminders, expiry, suspension) and receipts/invoices are sent | Not built (Platform PRD FR-528) | Ticket needed |
| L-12 | Privacy 3.2 | Marketing email is sent only with recorded consent and every message has an unsubscribe link, or no marketing email is sent | Built in the sense that no marketing email exists | Re-check if marketing starts |
| L-13 | Privacy 3.3; Terms 6.1–6.4 | The released desktop activates Devices by Administrator sign-in and by enrolment key, stores the device credential in the OS secure store, and verifies signed licence files | Partly built (API built; `selahcue-licensing` client crate exists but is not linked into released binaries; sign-in activation blocked by CSRF, 86ak5t1gw) | 86ak5mn11, 86ak5mn1d, 86ak5mn1t, 86ak5t1gw |
| L-14 | Privacy 3.3 | The device-identifier method is decided and privacy-reviewed | Undecided (left to the app shell by design, `selahcue-licensing/src/device.rs`) | Engineering + counsel (`{{DEVICE_FINGERPRINT_METHOD}}`) |
| L-15 | Privacy 3.3; Terms 6.2 | Devices refresh licence files automatically when online, and the server records each Device's last check-in time | Partly built (refresh endpoint exists; no last-check-in field on `Device` or `DeviceToken`) | 86ak5mn1h; schema change needed |
| L-16 | Privacy 3.3 | Downloads (installers, updates, translations) go through accounts or activated Devices and are recorded | Not built (`downloads:prepare` and `:complete` return 501; download-page buttons link nowhere) | Ticket needed (Platform PRD FR-530) |
| L-17 | Privacy 6.2; Terms 6.3, 8.6, 8.10, 15.1 | The customer portal shows members, plan, licence, Devices, usage and billing history; Administrators can deactivate a Device, cancel a Plan and close the Account | Not built (`accountViewer` returns only the viewer; no device-deactivation writer) | Tickets needed (FR-525, FR-511) |
| L-18 | Terms 6.5, 8.13, 14.1 | Licence and Plan changes take effect only at the next Session; activated Devices keep running when the platform is unavailable | Not built (decided: DEC-009, Platform PRD CON-P1, FR-549, NFR-504) | 86ak5mn1t |
| L-19 | Terms 7.2 | Free-Plan output shows the watermark | Not built (decided: DEC-008, FR-548; grant dimension exists in the catalogue) | Ticket needed |
| L-20 | Privacy 3.4, 4.4, 6.1; Terms 8.3–8.10 | Billing is integrated end to end: provider and merchant of record chosen, checkout, webhook, automatic licence issuance, receipts and invoices; the payment provider's cookies are captured in Privacy 4.4 | Not built (billing webhook returns 501; `apps/billing` is a scaffold) | Owner decision D2 (86ak10g47); FR-534, FR-537 |
| L-21 | Terms 8.1–8.9, 8.11; pricing page | Prices, currency, Billing Periods, trial, renewal, proration, downgrade timing, refund policy, price-change notice and failed-payment period are decided; the pricing page matches the catalogue | Undecided (tier names and allowance periods conflict across DEC-008, the owner decision of 2026-09-27 and the pricing page) | Owner decision D1 (86ak10gph); catalogue 17tnw2az0gd (M) |
| L-22 | Terms 8.5 | Renewal reminders meet the automatic-renewal laws of each market where paid Plans are sold | Undecided | Counsel review |
| L-23 | Terms 8.11 | Allowance rules on upgrade and downgrade, and session-start Device gating after a downgrade, are implemented | Not built (allowance rules are owner-decided per project memory, not in DECISION-LOG; Device rule decided in DEC-009/FR-550) | Record the decision in DECISION-LOG; ledger 17tnw2az0gj (M) |
| L-24 | Terms 8.12 | Soft suspension works: activated Devices keep presenting; new activations, licence renewals and Cloud Features stop; reinstatement restores the prior state | Partly built (API stores `prior_status` and has a state machine; cascade scoping and client behaviour unverified) | DEC-010; 86ak1099u; 86ak5mn1t |
| L-25 | Terms 8.13 | The 7-day grace, renewal reminder and Free-Plan fallback at the next Session work | Not built (decided: DEC-009, FR-521, FR-549) | Lifecycle jobs (FR-503) + 86ak5mn1t |
| L-26 | Privacy 3.5, 8 | The hosting provider and region are chosen; the server-log retention is set and enforced | Undecided | Owner decision |
| L-27 | Privacy 3.5, 8 | The audit-record retention is set and enforced, and audit records include allowed and refused cloud-feature requests | Not built (no retention limit on `AuditEvent`; refused-request recording is owner-decided per project memory) | Owner decision; tickets 86akby3xu, 17tnw2az0gn (M) |
| L-28 | Privacy 8 | Every retention period in the table is set and enforced by scheduled jobs | Partly built (only the nightly session and credential-token sweep exists) | Owner decision + tickets |
| L-29 | Privacy 11.2; Terms 15.1 | Users can delete their account and export their data in account settings; Administrators can close the organisation's account; deletion anonymises audit actor references | Not built (no such mutation; account models use `on_delete=PROTECT`) | Tickets needed; Platform PRD §16 |
| L-30 | Privacy 11.3–11.5 | A rights-request procedure (identity checks, one-month deadline), a processor-assistance procedure for churches, and a complaints procedure exist (UK DUAA s.103; GAID Art. 7(w), Art. 40) | Unknown (no procedure documented) | Operations |
| L-31 | Privacy 3.6 | The website contact form actually sends messages to a monitored mailbox, and its confirmation text makes only promises staff can keep | Not built (the form fakes success with a timer and promises a reply "within 24 hours") | Ticket needed |
| L-32 | Privacy 3.7 | The launch desktop build has no advertising, analytics, telemetry or crash reporting; its only internet connections are those listed. If it checks for updates automatically, that is added to 3.7 | Built for the current Windows build (verified from direct dependencies); launch build to be re-checked | Engineering re-check at release |
| L-33 | Privacy 3.7; Terms 13.1 | The speech model still downloads from `huggingface.co` | Built | Re-check at release |
| L-34 | Privacy 3.7, 3.9; Terms 9.3 | Bible translations download from the real host in `{{TRANSLATION_DOWNLOAD_HOST}}`; the Young's Literal Translation pin has a real URL and digest | Not built (the catalogue URL is `https://OWNER-SUPPLIED.invalid/...`) | Owner supplies host and pin |
| L-35 | Privacy 3.9, 6.1; Terms 9.3, 13.1 | Licensed translations: publisher agreements signed; translations delivered only to activated Devices on eligible Plans; export restrictions enforced (FR-146); publisher terms published; the publisher reporting data is defined | Not built (story 86ajpqfyj; API README lists licensed translations and reporting as open owner decisions) | Owner decision + 86ajpqfyj |
| L-36 | Privacy 3.8; Terms 12 | Cloud transcription and AI notes ship in the released build with server-issued credentials (no developer keys); per-feature Administrator opt-in with a disclosure naming the provider, data and location (FR-132/FR-177); an active-cloud indicator (FR-133) | Partly built (consent model built in `selahcue-core`; provider paths exist only in developer builds; the hosted path is not built; release builds exclude both) | 86ajy04hz, 86akby3xu, 17tnw2az0gn, 17tnw2az0n2 (M) |
| L-37 | Privacy 3.8; Terms 12.2 | Before cloud release: DPIA filed with the NDPC (GAID Art. 28(3)); DPAs with the speech and notes providers; a church-facing DPA published at `{{DPA_REFERENCE}}`; transfer safeguards; provider retention and model-training terms verified; a COPPA and children's-audio assessment | Not built | Counsel + owner |
| L-38 | Privacy 3.8; Terms 12.4 | Usage records and allowances work as described, including the rule that a failed note generation does not use up the allowance, and the retry terms | Not built (decided per project memory: D7 and the ADR-0028 retry rule, which sits in draft PR #111) | 17tnw2az0gj, 17tnw2az0gn (M); fill `{{RETRY_ALLOWANCE_TERMS}}` |
| L-39 | Privacy 3.10 | No sale, no behavioural advertising, no solely automated decisions with significant effects | Built (true today) | Re-check at release |
| L-40 | Privacy 4.1, 4.5 | A cookie audit of the production site shows only the listed cookies and storage (including the `csrftoken` lifetime) and no analytics or advertising tools | Built in code (the `csrftoken` lifetime is the Django default and is unverified on a deployment) | Cookie audit at release |
| L-41 | Privacy 4.3; Terms 13.1 | Either the site still loads Google Fonts (disclosure stays), or the font is self-hosted and both Google Fonts passages are deleted | Built (the site loads Google Fonts today); self-hosting recommended | Owner decision |
| L-42 | Privacy 4 | Whether to show a GAID Art. 7(l)-style cookie notice is decided | Undecided | Counsel decision |
| L-43 | Privacy 5.1 | A Legitimate Interest Assessment (GAID Art. 26, Schedule 8) is completed and referenced | Not built | Owner + counsel (`{{LIA_REFERENCE}}`) |
| L-44 | Privacy 6.1 | Written processor agreements (NDPA s.29) exist with the hosting, email, payment, speech and notes providers | Not built | Owner + counsel |
| L-45 | Privacy 7 | Transfer mechanisms are in place and recorded (NDPA s.41(2)); the approach to GAID Art. 18(1)(e) is decided | Undecided | Counsel decision (`{{TRANSFER_MECHANISMS}}`) |
| L-46 | Privacy header, 11.6, 13 | NDPC registration as a data controller of major importance is assessed and done if required; the DPO is appointed; EU and UK representatives are appointed, or §11.6 is deleted if counsel confirms they are not needed | Undecided | Counsel decision |
| L-47 | Privacy 9.1 | The deployment serves HTTPS only (HSTS on), Redis-backed rate limiting is configured, and the lockout settings are as described | Built in code; deployment unknown | Operations check at release |
| L-48 | Privacy 9.2 | A breach-response procedure exists, including NDPC notification within 72 hours | Unknown | Operations |
| L-49 | Terms 5.4 | Security updates for a licensed version stay downloadable after a paid Plan ends | Not built (Platform PRD FR-531 is marked "Proposed") | Owner decision (§6) + FR-531 |
| L-50 | Terms 6.5, 14.3, 15.2, 16.1, 17.3, 19, 22.2, 23.2; Privacy 11.2 | The owner and counsel accept each proposal listed in §6, or change or delete the clause | Undecided | Owner + counsel |
| L-51 | Terms 5.5, 13.1 | Open-source licence notices and the NDI attribution are published | Not built | Engineering (`{{THIRD_PARTY_NOTICES_LOCATION}}`, `{{NDI_ATTRIBUTION_TEXT}}`) |
| L-52 | Terms 10.1 | Scripture detection requires operator approval by default; AI notes show the AI-generated label and fabrication warning | Partly built (label and warning in `selahcue-cloud`; the detection default is specified in PRD FR-115 but not verified in code) | Engineering to confirm |
| L-53 | Terms 14.2 | The support mailbox is staffed to the published support terms | Unknown | Operations (`{{SUPPORT_TERMS}}`) |
| L-54 | Terms 22 | Governing law and forum are chosen | Undecided | Owner + counsel |
| L-55 | Terms 1.2; Privacy 1.3 | The Controller app policies are published at the URLs used, with placeholder values aligned (§13) | Not built | Owner |
| L-56 | Website pages | The pricing, download, contact and sign-up pages are consistent with both policies (no PayPal/ACH/SLA/version claims that are untrue; no "Church" plan unless it exists) | Not built (see §9.4) | Ticket needed |

## 5. Placeholder register (61 placeholders; 9 new in v0.2)

| Placeholder | Meaning | Used in | Who decides |
|---|---|---|---|
| `{{LEGAL_ENTITY_NAME}}` | Exact registered name of the contracting and controlling entity | Both | Owner |
| `{{REGISTERED_ADDRESS}}` | Registered office address | Both | Owner |
| `{{COMPANY_REGISTRATION_NUMBER}}` | CAC (or other) registration number | Both | Owner |
| `{{EFFECTIVE_DATE}}` | Date each document takes effect | Both | Owner, at publication |
| `{{WEBSITE_URL}}` | Production website URL | Both | Owner |
| `{{PRIVACY_POLICY_URL}}` | Public URL of the privacy policy | Both | Owner |
| `{{TERMS_URL}}` | Public URL of the terms | Terms | Owner |
| `{{PRIVACY_CONTACT_EMAIL}}` | Mailbox for privacy and rights requests | Privacy | Owner |
| `{{SUPPORT_CONTACT_EMAIL}}` | Support mailbox | Both | Owner |
| `{{LEGAL_NOTICES_EMAIL}}` | Address for formal legal notices | Terms | Owner |
| `{{DPO_NAME_AND_CONTACT}}` | Data Protection Officer (NDPA s.32) | Privacy | Owner + counsel |
| `{{CONTROLLER_PRIVACY_POLICY_URL}}` | Public URL of the mobile Controller privacy policy | Privacy | Owner |
| `{{CONTROLLER_TERMS_URL}}` | Public URL of the mobile Controller terms | Terms | Owner |
| `{{SENSITIVE_DATA_CONDITION}}` | Sentence stating the legal condition relied on if account data is treated as revealing religious belief, or deletion of the sentence | Privacy 3.1 | Counsel |
| `{{EMAIL_DELIVERY_PROVIDER}}` | Transactional email provider | Privacy | Owner |
| `{{HOSTING_PROVIDER}}` | Hosting provider for the API and site | Privacy | Owner |
| `{{HOSTING_REGION}}` | Country or region of the servers | Privacy | Owner |
| `{{COUNTRY_OF_ESTABLISHMENT}}` | Country where the controller is established (assumed Nigeria) | Privacy | Owner |
| `{{TRANSFER_MECHANISMS}}` | Transfer safeguards (NDPA basis; EU/UK SCCs or equivalent) | Privacy | Counsel |
| `{{SERVER_LOG_RETENTION}}` | Server log retention | Privacy | Owner |
| `{{AUDIT_RECORD_RETENTION}}` | Audit-record retention | Privacy | Owner + counsel |
| `{{ACCOUNT_RETENTION_AFTER_CLOSURE}}` | Retention of account data after closure | Privacy | Owner + counsel |
| `{{UNVERIFIED_SIGNUP_RETENTION}}` | Deletion period for never-verified sign-ups (GAID Art. 21(2) suggests 6 months) | Privacy | Owner + counsel |
| `{{LICENCE_RECORD_RETENTION}}` | Retention of licence, device, download and usage records (Platform PRD §16 proposes 24 months after a terminal state) | Privacy | Owner |
| `{{FINANCIAL_RECORD_RETENTION}}` | Payment, invoice and tax record retention (statutory) | Privacy | Counsel or accountant |
| `{{SUPPORT_RETENTION}}` | Support message retention | Privacy | Owner |
| `{{LIA_REFERENCE}}` | Reference to the Legitimate Interest Assessment | Privacy | Owner + counsel |
| `{{MINIMUM_ACCOUNT_AGE}}` | Minimum age to hold an account (18 recommended; NDPA "child" follows the Child's Rights Act 2003) | Both | Owner + counsel |
| `{{EU_REPRESENTATIVE}}` | GDPR Art. 27 representative | Privacy | Counsel |
| `{{UK_REPRESENTATIVE}}` | UK GDPR Art. 27 representative | Privacy | Counsel |
| `{{DEVICE_FINGERPRINT_METHOD}}` | How the desktop generates the device identifier | Privacy | Engineering + counsel |
| `{{PAYMENT_PROVIDER}}` | Payment provider | Both | Owner (D2) |
| `{{PAYMENT_DATA_RECEIVED}}` | Payment data SelahCue receives from the provider | Privacy | Owner (D2) |
| `{{TRANSLATION_DOWNLOAD_HOST}}` | Host for downloadable Bible translations | Privacy | Owner |
| `{{STT_PROVIDER}}` | Cloud speech-to-text provider (project memory names a candidate; undecided for this document) | Both | Owner |
| `{{NOTES_PROVIDER}}` | Cloud AI notes provider (project memory names a candidate; undecided for this document) | Both | Owner |
| `{{NOTES_ROUTE}}` | Whether notes travel directly from the desktop to the provider, or through SelahCue's servers (ADR-0028 options A and C) | Privacy | Owner + engineering |
| `{{DPA_REFERENCE}}` | Location of the data processing terms for the Cloud Features | Both | Counsel |
| `{{PROVIDER_RETENTION}}` | How long cloud providers keep audio and transcripts | Privacy | Owner, from provider contracts |
| `{{MODEL_TRAINING_STATEMENT}}` | Statement on whether providers may train models on the data, once verified in the contracts | Privacy | Owner + counsel |
| `{{THIRD_PARTY_NOTICES_LOCATION}}` | Where open-source licence notices are published | Terms | Engineering |
| `{{ALLOWANCE_RESET_PERIOD}}` | Usage-allowance reset period (DEC-008 says monthly; the 2026-09-27 owner decision says weekly) | Terms | Owner |
| `{{CURRENCY}}` | Billing currency | Terms | Owner |
| `{{RENEWAL_TERMS}}` | Whether and how paid Plans renew | Terms | Owner + counsel |
| `{{REFUND_POLICY}}` | Refund policy (FR-536, tied to D2) | Terms | Owner + counsel |
| `{{PRICE_CHANGE_NOTICE_DAYS}}` | Notice period for price changes | Terms | Owner |
| `{{NDI_ATTRIBUTION_TEXT}}` | Attribution and trademark wording required by the NDI licence | Terms | Owner |
| `{{SUPPORT_TERMS}}` | Support hours and response commitments | Terms | Owner |
| `{{MINIMUM_LIABILITY_AMOUNT}}` | Floor of the liability cap | Terms | Owner + counsel |
| `{{GOVERNING_LAW}}` | Governing law | Terms | Owner + counsel |
| `{{DISPUTE_FORUM}}` | Court or arbitral forum | Terms | Owner + counsel |
| `{{TERMS_CHANGE_NOTICE_DAYS}}` | Notice period for material changes to the Terms | Terms | Owner |
| `{{STT_ROUTE}}` **(new)** | Whether cloud-transcription audio travels directly from the desktop to the provider, or through SelahCue's servers; this decides whether SelahCue itself receives audio | Privacy 3.8 | Owner + engineering |
| `{{PUBLISHER_REPORTING_DATA}}` **(new)** | What usage data the publisher licences require SelahCue to report | Privacy 3.9 | Owner, from publisher agreements |
| `{{TRIAL_TERMS}}` **(new)** | Trial length, features and what happens at the end (sign-up already creates a TRIAL organisation) | Terms 8.2 | Owner (D1 remainder) |
| `{{MERCHANT_OF_RECORD}}` **(new)** | Who the customer buys from. If a reseller is merchant of record, this sentence names it and the contracting structure changes | Terms 8.3 | Owner (D2) + counsel |
| `{{BILLING_PERIODS}}` **(new)** | Billing Periods offered (for example monthly or annual) | Terms 8.4 | Owner |
| `{{PRORATION_TERMS}}` **(new)** | How upgrades are charged part-way through a Billing Period | Terms 8.11 | Owner |
| `{{DOWNGRADE_TIMING}}` **(new)** | When a downgrade takes effect (immediately or at the end of the Billing Period) | Terms 8.11 | Owner |
| `{{FAILED_PAYMENT_GRACE_PERIOD}}` **(new)** | How long after a failed payment before suspension (dunning cadence, D2) | Terms 8.12 | Owner (D2) |
| `{{RETRY_ALLOWANCE_TERMS}}` **(new)** | The note-retry rule (project memory records one retry within 10 minutes against the same reservation, the failed attempt and its retry together costing one unit) | Terms 12.4 | Owner to confirm |

## 6. Proposed risk allocations and commitments

The clause text in v0.2 is clean. These clauses are new allocations of risk, or commitments beyond
what is decided. Each needs owner and counsel acceptance (checklist row L-50) before publication.

| Clause | What it does | Why it is a proposal |
|---|---|---|
| Terms 17.3 | Caps SelahCue's liability at the greater of 12 months' fees and `{{MINIMUM_LIABILITY_AMOUNT}}` | A risk allocation; the floor protects free users' claims from being capped at zero |
| Terms 19 | Customer indemnity for infringing content and unlawful recording | A risk allocation; may be resisted by churches; can be deleted |
| Terms 5.4 | Security updates stay downloadable after a paid Plan ends | Platform PRD FR-531 is marked "Proposed"; the owner may reject it |
| Terms 6.5 | A licence or Plan change never interrupts a running Session | Decided product rule (CON-P1, FR-549); publishing it makes it a contractual promise |
| Terms 14.3 | Refund if a material feature reduction leads to cancellation | Fairness term; commits money |
| Terms 15.2 | 14-day cure period before termination for breach | Process commitment |
| Terms 16.1 | Warranty of reasonable care and skill | Implied by law for consumers in some markets; a contractual warranty for everyone |
| Terms 22.2 | 30 days of good-faith negotiation before formal disputes | Process commitment |
| Terms 23.2 | Administrators re-accept material changes; refund of unused fees if they reject | Needs L-8; commits money |
| Privacy 11.2 | Deletion anonymises audit actor references | Platform PRD §16 design; needs engineering (L-29) |

## 7. Assumptions

1. The controller and contracting entity is a Nigerian company in Lagos (owner stated "Nigerian-based,
   Lagos"). Not verified; this drives NDPA s.2(2)(a) applicability and the governing-law analysis.
2. Accounts are opened by organisations (churches), usually through a staff member or volunteer. Some
   sign-ups may be individuals acting as consumers.
3. At launch, every feature in L-13 to L-38 ships as described. If any feature does not ship, its
   passages must be removed from the policies before publication.
4. Today's released desktop product is what `.github/workflows/windows-installer.yml` builds
   (`--release`, `--features stt`, default at-rest encryption, NDI bundled). No macOS or Linux release
   pipeline exists in the repo; `docs/ops/DEPLOYMENT.md` records the macOS signing credentials as
   not supplied.
5. Development builds (`make launch`) can stream audio to a speech provider and send transcripts to an
   AI provider using developer keys. These builds are not distributed and are not described.
6. No ClickUp, deployment console or provider contract was reviewed.

## 8. Fact-to-source table

Status key: **V** = verified in code or config in this worktree · **D** = documented decision or
requirement, not necessarily built · **I** = inferred, needs confirmation · **M** = from the owner's
project memory notes, not verified in the tree.

### 8.1 Privacy Policy facts

| # | Claim in the draft | Source | Status |
|---|---|---|---|
| P1 | Plans, slides, decks, songs, themes and screen settings are stored locally | `implementation/desktop/crates/selahcue-data/src/lib.rs`; `docs/architecture/ARCHITECTURE.md` §8 | V |
| P2 | Media files are referenced by path | `ARCHITECTURE.md` §8; DEC-003 | D |
| P3 | Transcripts, corrections and detected references are stored locally | `selahcue-data/src/transcript_repo.rs` | V |
| P4 | Sermon-note drafts are stored locally | `selahcue-data/src/lib.rs` (`sermon_note_repo`) | V |
| P5 | Content reaches SelahCue only through cloud features or support | Root `Makefile` (`RELEASE_UNSAFE_FEATURES`, `release-ai-guard`); `windows-installer.yml`; `selahcue-operator/Cargo.toml`; `selahcue-cloud/src/lib.rs` | V (today's build) |
| P6 | Transcript database encrypted by default; key in the OS store or derived from a passphrase | `selahcue-desktop/Cargo.toml`; `selahcue-operator/Cargo.toml`; `Makefile` | V |
| P7 | Deck library not encrypted | `selahcue-operator/Cargo.toml` comment on `selahcue-data` | V |
| P8 | Transcript delete cascade, including the sermon note by default; automatic deletion after N days | `transcript_repo.rs` (`RetentionSettings`) | V (repository); UI is L-3 |
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
| P20 | Download records | Platform PRD FR-530 | D (L-16) |
| P21 | Enrolment keys hashed and masked | `apps/license_keys/models.py` | V |
| P22 | Payment processing by a provider; no card numbers held | Platform PRD D2, NG-P6 | D (L-20) |
| P23 | Rate-limit counters; IPv6 /64 | `apps/throttling/services.py`; `settings.py` | V |
| P24 | Audit records with secrets removed | `apps/audit/models.py`, `apps/audit/services.py`, `graphql/redaction.py` | V |
| P25 | Audit records of allowed and refused cloud requests | Owner decision OD-3 (2026-09-27) | M (L-27) |
| P26 | No analytics, telemetry or crash reporting | Direct dependency manifests (operator, desktop, API, mobile, marketing) | V (direct dependencies only) |
| P27 | Speech model from `huggingface.co`, integrity-checked | `selahcue-stt/src/model.rs`, `model_fetch.rs` | V |
| P28 | Cloud features off by default, Administrator-gated, audio only for transcription, transcript text only for notes | `selahcue-core/src/providers.rs`; `selahcue-cloud/src/lib.rs`; PRD FR-132/133/137 | V (design) |
| P29 | Usage records in time and number of notes | Platform PRD FR-546; owner decisions D7/D8 | D/M |
| P30 | Licensed translations and publisher reporting | `selahcue-scripture/src/lib.rs` (86ajpqfyj); `implementation/api/README.md` | D (L-35) |
| P31 | Cookies and local storage | `account_schema.py`; `settings.py`; `selahcue_api/urls.py`; `src/lib/auth/session.ts` | V (`csrftoken` lifetime is L-40) |
| P32 | Google Fonts | `implementation/marketing/index.html` | V |
| P33 | No analytics on the site | `package.json`; `index.html`; `src/main.ts` | V |
| P34 | Self-service deletion and export; account closure | Platform PRD §16 | D (L-29) |
| P35 | Portal shows members, plan, licence, devices, usage, billing | Platform PRD FR-525 | D (L-17) |

### 8.2 Terms of Service facts

| # | Claim | Source | Status |
|---|---|---|---|
| T1 | Core presentation works offline | PRD CON-2, NFR-015; `selahcue-licensing/src/lib.rs` | V/D |
| T2 | One email, one account | `CustomerUser` unique constraint | V |
| T3 | Bundled translations: KJV, WEB, ASV, WEBBE, Darby | `selahcue-scripture/src/lib.rs` | V |
| T4 | KJV Crown letters patent (UK) | Code comment; ebible.org (secondary) | V (secondary source) |
| T5 | Operator approval of scripture suggestions by default | PRD FR-115/116 | D (L-52) |
| T6 | AI-generated label and fabrication warning | `selahcue-cloud/src/lib.rs`; PRD FR-123/128 | V |
| T7 | Watermark on the free Plan | DEC-008; FR-548 | D (L-19) |
| T8 | 7-day grace, then the free Plan from the next Session | DEC-009; FR-521/549 | D (L-25) |
| T9 | Soft suspension | DEC-010; FR-504/510; `license_keys/models.py` (`prior_status`) | D/partly V (L-24) |
| T10 | A downgrade keeps Devices; limit applied at Session start | DEC-009; FR-550 | D (L-23) |
| T11 | Allowance rules on upgrade and downgrade | Owner decision 2026-09-27 | M (L-23) |
| T12 | Failed note generation not charged; retry rule | Owner decisions D7 and ADR-0028 rev 2 (draft PR #111) | M (L-38) |
| T13 | Activation by sign-in or enrolment key; signed offline licence file | DEC-004/005/011; `implementation/api/README.md` | V (server) |
| T14 | Session-boundary rule; offline when the platform is down | Platform PRD CON-P1, FR-549, NFR-504 | D (L-18) |
| T15 | Security updates after a Plan ends | Platform PRD FR-531 ("Proposed") | D (L-49) |
| T16 | Trial organisation created at sign-up | DEC-007 product answers (TRIAL status) | V |
| T17 | Third parties: NDI, Hugging Face, Google Fonts | `selahcue-desktop/Cargo.toml`; `selahcue-stt/src/model.rs`; `index.html` | V |

## 9. Claims on the old stub pages

Sources: `implementation/marketing/src/views/PrivacyView.vue` and `TermsView.vue`. These pages are
live today and are not replaced by these drafts until published.

### 9.1 False, or not true today

1. **"billing information through our payment processor (Stripe)"** — no payment integration exists;
   the billing webhook returns 501; the provider is open decision D2 (Stripe is only one option).
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
   explicitly enable an opt-in cloud AI integration"** — transcript previews go to paired mobile
   devices over the local network, and no cloud integration exists in released builds.
7. **"You agree not to extract, reverse engineer, or redistribute encrypted Bible databases"** — no
   encrypted Bible databases exist; bundled texts are compressed, not encrypted.

### 9.2 Partly true or overstated

8. **"On-device speech-to-text (Whisper AI) runs 100% locally ... using native GPU acceleration"** —
   recognition runs locally, but the model downloads from Hugging Face on first use, and only macOS
   builds compile GPU acceleration; the Windows installer build is CPU-only.
9. **"we collect your organization name, primary contact name, email address"** — there is no
   "primary contact name" field (an optional display name exists); the stub omits country, time zone
   and password.
10. **"Data Protection Rights (GDPR & NDPA 2023) ... access, rectify, or request deletion"** — an
    incomplete list, and "billing data" does not exist.
11. **"license ... up to the seat count specified in your Pro or Church subscription plan"** — plan
    names are unsettled; a "Church" plan appears in no decision record.

### 9.3 Not verifiable

12. **`privacy@selahcue.app`** — no evidence that this mailbox or domain exists. The API defaults to
    `noreply@selahcue.com` as sender and `info@firstpavitech.com` as a default address.
13. **"Last Updated: August 8, 2026"** on both pages — no record of a review or publication.
14. **"your organization agrees to be bound"** by downloading — acceptance is not recorded.
15. **"SelahCue grants ..."** — SelahCue is a brand; no legal entity is named on either page or in the
    footer ("© 2026 SelahCue").

### 9.4 Other site content that creates legal risk

- **Contact page** (`ContactView.vue`): the form sends nothing (a timer fakes success) but tells the
  user "A SelahCue specialist will respond within 24 hours". It also lists `support@selahcue.app`
  (unverified), a Discord community of "1,200+ worship tech leaders" (unverified) and links that point
  to `#`.
- **Pricing page** (`PricingView.vue`): Free/Pro/Church, $19 per month, "Save 20%" annually, "Prorated
  charges will apply", "credit cards, PayPal, and ACH" and a "24/7 SLA" — none of this is built or
  decided, and it conflicts with the recorded tier decisions.
- **Download page** (`DownloadView.vue`): "Version 1.2.0 (Stable)" for Windows and macOS — the app
  version is 0.1.0 (`tauri.conf.json`), there is no macOS release pipeline, and the buttons link
  nowhere.
- **Sign-up page**: the Terms and Privacy checkbox is checked only in the browser.

## 10. Jurisdiction analysis

### 10.1 Nigeria — NDPA 2023 and GAID 2025 (primary)

- **Application.** The NDPA applies where the controller is domiciled, resident or operating in
  Nigeria, where processing happens in Nigeria, or where data subjects are in Nigeria (s.2(2)). A
  Lagos-based controller is in scope for all its users worldwide. GAID Art. 8(2) reads "operating in
  Nigeria" to include targeting data subjects in Nigeria.
- **GAID 2025.** The General Application and Implementation Directive (NDPC/NDP ACT-GAID/01/2025) took
  effect on 19 September 2025, after which the NDPR 2019 ceased to apply (GAID Art. 3(3)).
- **Privacy notice content.** NDPA s.27(1) requires: identity and contact details; the lawful basis
  under s.25(1) or s.30(1) and purposes; recipients; data-subject rights; retention period; the right
  to complain to the NDPC; and any automated decision-making. Section 27(3) requires a clear, concise,
  accessible privacy policy. GAID Art. 27(3) adds "means of processing" and third-party access and its
  purpose; Art. 7(j)–(m) and (w) require the policy to be published and the complaints process
  explained. The v0.2 Privacy Policy covers each item once the retention placeholders are filled.
- **Transparency and accuracy.** Section 24 requires fair, lawful and transparent processing. A
  policy that describes processing that is not happening, or omits processing that is, breaches
  these duties; this is the legal basis of the §4 hard gate.
- **Lawful bases.** NDPA s.25(1); legitimate interests are excluded where overridden or unexpected
  (s.25(2)). GAID Art. 26 makes a documented Legitimate Interest Assessment (Schedule 8) mandatory
  before relying on legitimate interests.
- **Sensitive personal data.** "Sensitive personal data" includes religious or similar beliefs
  (s.65). Section 30(1) restricts processing to listed conditions; s.30(1)(d) covers processing by
  religious non-profits about their own members, which protects churches, not SelahCue. GAID Art.
  18(1)(b) requires consent for processing sensitive data. Two exposures: account data, where a church
  name plus a person's email may reveal religious affiliation (counsel decides
  `{{SENSITIVE_DATA_CONDITION}}`); and the Cloud Features, which process sermon audio and transcripts
  that will often reveal religious beliefs and sometimes health information (prayer requests).
- **Children.** "Child" takes its meaning from the Child's Rights Act 2003 (s.65). Under s.31, consent
  must come from a parent or guardian, with appropriate age verification. The drafts set a minimum
  account age with a sign-up confirmation (L-7) and put notice duties for children's voices in
  transcripts on churches.
- **Rights.** Access, copy, correction, erasure and restriction (s.34); withdrawal of consent (s.35);
  objection, including to direct marketing (s.36); automated decisions (s.37); portability (s.38). The
  NDPA sets no fixed day count, so the draft applies the GDPR one-month limit globally.
- **Security and breach.** Section 39 requires appropriate measures. Under s.40(2), the controller must
  notify the NDPC within 72 hours of a breach likely to risk individuals' rights, and must tell data
  subjects immediately where risk is high (s.40(3)); GAID Art. 7(p)–(q) restates this.
- **Processors.** Section 29 requires written agreements with processors; GAID Art. 34 covers data
  processing agreements.
- **Cross-border transfers.** Sections 41–43 allow transfers where the recipient is subject to
  adequate protection, or under a s.43 derogation, and the basis must be recorded (s.41(2)). **GAID
  Art. 18(1)(e) additionally says consent is required "before personal data may be transferred to a
  country in respect of which the Commission has not made an adequacy decision".** Read literally, this
  would require consent for any transfer to a non-adequacy country (for example, US hosting, email,
  payment or AI providers), even where s.41(1)(a) safeguards exist. That reading sits uneasily with the
  Act's own structure (and the Act prevails, GAID Art. 3(2)). Counsel must decide the approach before
  providers are chosen.
- **Data controller of major importance.** Under s.44 and GAID Schedule 7 (Guidance Notice
  NDPC/HQ/GN/VOL.03/B/24), designation applies to an entity that processes the personal data of more
  than 200 data subjects in six months, or that "carries out commercial Information Communication
  Technology (ICT) services on any digital device which has storage capacity ... and belongs to another
  individual". Tiers are UHL (over 5,000 data subjects in six months; ₦250,000 fee), EHL (over 1,000
  among its factors; ₦100,000 fee) and OHL (over 200). Obligations include registration, a DPO (s.32),
  an annual compliance audit and CAR filing (GAID Arts. 7, 9, 10) and staff training. SelahCue will
  probably qualify at launch.
- **DPIA.** Section 28 requires a DPIA for likely high-risk processing. GAID Art. 28(3) makes a DPIA
  mandatory, **and filed with the Commission**, where sensitive data is involved, for software
  enabling communication with data subjects, and for e-commerce services. Cloud transcription of
  sermons, and possibly paid online subscriptions, trigger this.
- **Cookies.** GAID Art. 19 requires consent for cookies except "necessary cookies" (core functions
  such as security), which "do not need the ticking of a box"; Art. 19(8) treats other tracking tools
  like cookies. GAID Art. 7(l) separately expects a homepage cookie notice, placed so it obstructs the
  centre or a side of the page (not the bottom), with an option to accept or decline. The site uses only
  necessary cookies, so consent is not needed; whether a notice is still expected is for counsel (L-42).
  Payment-provider cookies at checkout must be added to Privacy 4.4 (L-20).
- **Retention defaults.** GAID Art. 49(3): where no period is set by law, storage lapses no later than
  six months after the purpose is accomplished. GAID Art. 21(2): data from a contract that did not
  materialise is destroyed within six months.
- **Third-party sharing.** GAID Art. 41(9) says "explicit consent must be obtained" where data is shared
  with third parties. Applied literally to processors, this would be unworkable; counsel should confirm
  it does not cover service providers acting on instructions, or publishers receiving reporting data.
- **Consumer protection.** The FCCPA 2018 includes s.125 (false, misleading or deceptive
  representations), s.127 (unfair, unreasonable or unjust contract terms), s.128 (notice required for
  certain terms), s.137 (liability not to be excluded), s.142 (supply of services) and s.144
  (exclusion of implied terms). I verified the headings only, not the text. The billing section,
  warranty and liability clauses, and consumer-rights clause need counsel's check against the text.
- **Disputes.** The Arbitration and Mediation Act 2023 (signed 26 May 2023) replaced the Arbitration
  and Conciliation Act 1988, so arbitration seated in Lagos is a credible option.

### 10.2 European Union — GDPR

- **Territorial scope.** Article 3(2)(a) applies to a controller outside the EU that offers goods or
  services to people in the EU, whether paid or free. Paid Plans sold to EU churches would make this
  clearer still. **Fact question for the owner: will SelahCue sell to EU churches?**
- **Representative.** Article 27(1) requires a written EU representative; the Art. 27(2)(a) exemption
  covers only "occasional" processing that does not involve large-scale special-category data, so a
  representative is likely required.
- **Notice.** Articles 13(1)–(2) list the information required; the draft covers each item. Article
  12(3) requires a response within one month, extendable by two more months.
- **Special categories.** Article 9(1) covers data "revealing ... religious or philosophical beliefs".
  The CJEU in C-184/20 *OT v Vyriausioji tarnybinės etikos komisija* (Grand Chamber, 1 August 2022)
  held that data indirectly revealing a special category is special-category data. By analogy, account
  data could be treated as revealing religious belief, and Cloud Feature audio and transcripts very
  likely are. For the Cloud Features, the church is controller and SelahCue a processor (Art. 28),
  which needs the DPA at `{{DPA_REFERENCE}}`.
- **Children.** Article 8(1) sets 16 as the default age of digital consent (member states may set a
  lower age; the floor was not verified in this session). An 18+ account rule avoids the issue.
- **Cookies and fonts.** The ePrivacy Directive Art. 5(3) applies to cookies (not separately verified in
  this session; strictly necessary cookies are exempt). In *LG München I*, 3 O 17493/20 (20 January
  2022), a German court held that loading Google Fonts from Google's servers without consent unlawfully
  disclosed visitors' IP addresses and awarded €100 damages. This is a first-instance German decision,
  not binding EU-wide, but it prompted waves of demand letters. Self-hosting is recommended (L-41).
- **Consumer law.** EU consumer rules (withdrawal rights for digital services, unfair terms,
  automatic-renewal disclosures) may apply to individual purchasers. Not researched in this session;
  counsel to review Part C.

### 10.3 United Kingdom

- UK GDPR and the Data Protection Act 2018 mirror the EU analysis, including UK Art. 3(2) and Art. 27
  (UK representative).
- The Data (Use and Access) Act 2025 (2025 c. 18) received Royal Assent on 19 June 2025; its main Part 5
  data protection changes commenced on 5 February 2026 (gov.uk commencement plan). Section 103
  (complaints by data subjects; new s.164A DPA 2018) requires controllers to run a complaints process.
  A secondary source reports it commenced on 19 June 2026 under the Commencement No. 6 Regulations; I
  did not verify this on legislation.gov.uk. Covered by L-30.
- Section 112 amends the PECR rules on storage and access technologies; the ICO has issued updated
  guidance. This does not affect a site that uses only necessary cookies.
- The Terms flag the Crown letters patent restriction on the KJV in the UK.

### 10.4 United States

- **CCPA/CPRA.** It applies to for-profit businesses that meet one threshold: annual gross revenue over
  $26,625,000 (adjusted 1 January 2025), 100,000 or more California consumers or households, or 50% or
  more of revenue from selling or sharing personal information. SelahCue is probably below all three at
  launch. The no-sale statement is true.
- **COPPA.** It applies to operators of online services directed to children under 13, or with actual
  knowledge that they collect children's data. SelahCue is not directed to children. **Cloud
  transcription can send children's voices from church services to SelahCue's provider**, so counsel
  should assess COPPA before it ships (L-37). The amended COPPA Rule took effect on 23 June 2025, with
  compliance due by 22 April 2026 (secondary sources).
- **Automatic-renewal laws** in several states govern subscription disclosures and cancellation; not
  researched (L-22).

### 10.5 Governing law and forum

Options for `{{GOVERNING_LAW}}` / `{{DISPUTE_FORUM}}`:

1. **Nigerian law, courts of Lagos State** — simplest for a Lagos company; foreign customers may resist
   it, and consumer law in their countries may still apply.
2. **Nigerian law, arbitration seated in Lagos under the AMA 2023** — confidential and more enforceable
   abroad through the New York Convention; costlier for small claims.
3. **Mixed approach** — Nigerian law for organisations, with consumers keeping home-country rights
   (already in Terms 22.3).

Recommendation: option 1 or 2, with the 22.3 consumer carve-out. If a reseller is merchant of record
(`{{MERCHANT_OF_RECORD}}`), its own terms may govern the sale itself.

## 11. Source ledger

All checked 2026-10-01.

| Proposition | Authority | Provision | URL | Drafting implication |
|---|---|---|---|---|
| NDPA territorial scope | Nigeria Data Protection Act 2023 | s.2(2) | https://www.dataguidance.com/sites/default/files/data_protection_act_2023.pdf (mirror of the Act; page images read) | NDPA governs all users |
| Principles incl. transparency | NDPA 2023 | s.24 | as above | Basis of the hard gate |
| Lawful bases; legitimate-interest limits | NDPA 2023 | s.25(1)–(2) | as above | Privacy 5 |
| Consent rules | NDPA 2023 | s.26 | as above | Marketing consent; withdrawal |
| Privacy notice content | NDPA 2023 | s.27(1), (3) | as above | Policy structure |
| DPIA | NDPA 2023 | s.28 | as above | Cloud Features |
| Processor agreements | NDPA 2023 | s.29 | as above | L-44 |
| Sensitive-data conditions | NDPA 2023 | s.30, s.65 ("religious or similar beliefs") | as above | `{{SENSITIVE_DATA_CONDITION}}` |
| Children | NDPA 2023 | s.31; s.65 ("child" per Child's Rights Act 2003) | as above | Minimum age |
| Data-subject rights | NDPA 2023 | ss.34–38 | as above | Privacy 11 |
| Security; 72-hour breach notice | NDPA 2023 | ss.39–40 | as above | Privacy 9 |
| Cross-border transfers | NDPA 2023 | ss.41–43 | as above | Privacy 7 |
| Registration of DCMI | NDPA 2023 | s.44; s.65 | as above | L-46 |
| Complaints to the NDPC | NDPA 2023 | s.46 | as above | Privacy 11.5 |
| GAID displaces NDPR 2019 | GAID 2025 | Art. 3(3) | https://ndpc.gov.ng/wp-content/uploads/2025/07/NDP-ACT-GAID-2025-MARCH-20TH.pdf | Cite GAID |
| GAID effective 19 September 2025 | Secondary (law firm) | — | https://www.banwo-ighodalo.com/grey-matter/are-you-gaid-2025-ready-navigating-nigerias-gaid-2025-what-your-organisation-needs-to-know-how-bi-can-support-your-compliance-journey/ | Verify on ndpc.gov.ng |
| Compliance measures; cookie notice placement | GAID 2025 | Art. 7 | GAID URL above | L-42 |
| DCMI designation, registration, CAR | GAID 2025 | Arts. 8–10; Schedule 7 | GAID URL above | L-46 |
| Consent needed: marketing, sensitive data, children, non-adequacy transfers | GAID 2025 | Art. 18(1) | GAID URL above | L-45 |
| Cookies | GAID 2025 | Art. 19 | GAID URL above | Privacy 4 |
| Six-month destruction after a failed contract | GAID 2025 | Art. 21(2) | GAID URL above | Unverified sign-ups |
| LIA required | GAID 2025 | Art. 26; Schedule 8 | GAID URL above | L-43 |
| Information to data subjects | GAID 2025 | Art. 27 | GAID URL above | Policy content |
| Mandatory, filed DPIA | GAID 2025 | Art. 28(3) | GAID URL above | L-37 |
| Explicit consent for third-party sharing | GAID 2025 | Art. 41(9) | GAID URL above | Counsel question |
| Default six-month storage limit | GAID 2025 | Art. 49(3) | GAID URL above | Retention schedule |
| GDPR territorial scope | GDPR | Art. 3(2) | https://gdpr-info.eu/art-3-gdpr/ (unofficial mirror; EUR-Lex not retrievable) | EU applicability |
| Digital consent age 16 | GDPR | Art. 8(1) | https://gdpr-info.eu/art-8-gdpr/ | Minimum age |
| Special categories; explicit consent | GDPR | Art. 9(1), 9(2)(a) | https://gdpr-info.eu/art-9-gdpr/ | Sensitive-data risk |
| One-month response | GDPR | Art. 12(3) | https://gdpr-info.eu/art-12-gdpr/ | Privacy 11.3 |
| Notice contents | GDPR | Art. 13 | https://gdpr-info.eu/art-13-gdpr/ | Policy structure |
| EU representative | GDPR | Art. 27 | https://gdpr-info.eu/art-27-gdpr/ | L-46 |
| Indirect revelation of special-category data | CJEU, C-184/20 (Grand Chamber, 1 August 2022) | — | https://curia.europa.eu/jcms/upload/docs/application/pdf/2022-08/cp220133lt.pdf (press release; identified by search, not opened) | Sensitive-data risk |
| Google Fonts and IP disclosure | LG München I, 3 O 17493/20 (20 January 2022) | — | Secondary: https://www.ihk.de/bergische/recht-und-steuern/wettbewerbsrecht/google-fonts-5646176 | L-41 |
| DUAA 2025: c.18, s.103 complaints, s.112 storage and access | Data (Use and Access) Act 2025 | ss.103, 112, 142 | https://www.legislation.gov.uk/ukpga/2025/18/contents | L-30 |
| DUAA Royal Assent 19 June 2025; Part 5 commenced 5 February 2026 | UK Government commencement plan | — | https://www.gov.uk/guidance/data-use-and-access-act-2025-plans-for-commencement | UK analysis |
| s.103 commenced 19 June 2026 | Secondary | Commencement No. 6 Regulations 2026 | https://digitalpolicyalert.org/event/40956-data-use-and-access-act-2025-commencement-no-6-and-transitional-and-saving-provisions-regulations-2026-section-103-data-protection-complaints-including-data-protection-regulation-enter-into-force | Verify on legislation.gov.uk |
| CCPA revenue threshold $26,625,000 | California Privacy Protection Agency | CPI adjustment, effective 1 January 2025 | https://www.cppa.ca.gov/regulations/cpi_adjustment.html | US analysis |
| COPPA amendments: effective 23 June 2025; compliance 22 April 2026 | Secondary (law firm) | 16 CFR Part 312 | https://www.whitecase.com/insight-alert/unpacking-ftcs-coppa-amendments-what-you-need-know | L-37 |
| FCCPA provisions (headings only) | FCCPA 2018 | ss.125, 127, 128, 137, 142, 144 | https://fccpc.gov.ng/wp-content/uploads/2022/07/FCCPA-2018.pdf | Terms Part C, 16–18 |
| AMA 2023 replaced ACA 1988 | Secondary (law firm) | — | https://www.linklaters.com/insights/blogs/arbitrationlinks/2023/may/nigeria-revises-its-arbitration-act | Forum options |
| KJV Crown letters patent (UK only) | Secondary (ebible.org) | — | https://ebible.org/kjv/copr.htm | Terms 9.3 |

**Verification gaps.** I could not retrieve EUR-Lex directly, so the GDPR wording comes from the
gdpr-info.eu mirror. The NDPA text came from a DataGuidance mirror, not the official gazette. I did not
read: the Child's Rights Act definition of "child", the FCCPA's substantive text, the COPPA Rule in the
Federal Register, the s.103 commencement regulations, the ePrivacy Directive, EU or UK consumer-contract
law, US automatic-renewal laws, or Django's default CSRF cookie age. The NDPC has also published a later
GAID upload (`https://ndpc.gov.ng/wp-content/uploads/2026/01/NDP-ACT-GAID-2025-MARCH-20-1.pdf`) that I
did not compare with the July 2025 version I read.

## 12. Top 10 open questions and risks

1. **Entity, contacts and domains.** No legal entity is named anywhere. Contact addresses span three
   domains (`selahcue.app` on the site, `selahcue.com` as the API sender, `firstpavitech.com` as the API
   default). *Owner:* supply the entity details and choose one domain and mailbox set (L-1).
2. **The live site misleads users today.** The current stub pages state as fact a Stripe integration,
   bundled BSB, licensed NIV/ESV/NLT, recurring billing with portal cancellation and GPU acceleration.
   The contact form discards messages while promising a reply within 24 hours, and the pricing and
   download pages advertise plans, payment methods and versions that do not exist. These are
   misrepresentation risks (FCCPA s.125, by heading). *Owner:* replace the stubs and fix or remove the
   contact form and pricing claims before anything else, independent of launch (L-31, L-56).
3. **Publishing before launch-readiness would make the v0.2 policies false.** They describe roughly a
   dozen subsystems that are not built: the desktop activation client, licence check-ins, the customer
   portal, billing, downloads, the hosted cloud path, licensed translations, deletion and export, the
   acceptance record, retention jobs, the age check and the watermark and grace enforcement. *Owner:*
   treat §4 as a release gate with a named sign-off, and remove any passage whose feature does not ship.
4. **Religious affiliation as sensitive data.** Account data may reveal religious belief, and Cloud
   Feature audio and transcripts very likely do (NDPA s.65; GDPR Art. 9; C-184/20 by analogy).
   *Counsel:* decide the condition and complete `{{SENSITIVE_DATA_CONDITION}}` (L-9).
5. **Cross-border transfers.** GAID Art. 18(1)(e), read literally, requires consent before any transfer
   to a country without an NDPC adequacy decision. Hosting, email, payment, speech and notes providers
   are all likely to be abroad. *Owner + counsel:* settle the legal basis before choosing providers
   (L-45).
6. **NDPC registration.** SelahCue will probably qualify as a data controller of major importance at
   launch, which brings registration, a DPO, annual audits and CAR filings (L-46).
7. **Cloud Features.** They need a DPIA filed with the NDPC (GAID Art. 28(3)), provider DPAs, a
   church-facing DPA, transfer safeguards, verified model-training and retention terms, and a COPPA
   assessment. The routes (`{{STT_ROUTE}}`, `{{NOTES_ROUTE}}`) decide whether SelahCue itself receives
   audio or transcripts (L-36 to L-38).
8. **Retention, deletion and export.** No retention periods are set, audit rows have no limit,
   unverified sign-ups are never purged, and account models use `on_delete=PROTECT`, so deletion needs
   engineering (L-27 to L-29).
9. **Acceptance is not recorded.** The sign-up checkbox is checked only in the browser; Terms 2.3 and
   23.2 now promise a server-side record (L-8).
10. **Commercial model and risk allocation.** Tier names and allowance periods conflict across DEC-008,
    the 2026-09-27 owner decision and the pricing page. The payment provider and merchant of record
    (D2), trials, renewal, proration, refunds and the failed-payment period are open. The §6
    proposals (liability cap, indemnity and others), governing law and forum, and the EU/UK
    representatives also need decisions (L-21, L-22, L-50, L-54).

**Specialist advice recommended:** a Nigerian data protection practitioner (NDPA/GAID registration,
transfers, sensitive data); EU and UK privacy and consumer counsel if SelahCue sells in those markets;
US counsel before selling subscriptions or launching cloud transcription in the US.

## 13. Reconciliation with the existing mobile documents

- `docs/legal/PRIVACY.md` (Controller app) states the app collects and transmits no personal data to
  SelahCue and talks only to the paired desktop. The platform policy is consistent: it points to that
  policy (Privacy 1.3) and repeats the local-network facts (Privacy 2.5).
- `docs/legal/TERMS.md` (Controller app) grants a personal licence and leaves governing law as
  `{{JURISDICTION}}`. Platform Terms 1.2 makes the Controller terms prevail for the app.
- **Placeholder names differ** between the two document sets: the mobile documents use `{{ADDRESS}}`,
  `{{DATE}}` and `{{JURISDICTION}}`, where the platform drafts use `{{REGISTERED_ADDRESS}}`,
  `{{EFFECTIVE_DATE}}` and `{{GOVERNING_LAW}}`. Fill them with the same values, and consider merging the
  mobile terms into the platform Terms once both are final.
- `PRIVACY.md` §6 leaves the children's posture open; align it with `{{MINIMUM_ACCOUNT_AGE}}`.

## 14. ClickUp audit entries to record

No ClickUp writes were made in either session, at the coordinator's direction. Record both entries,
in order, on the matter task in the Legal Audit Log list (`1400430000002076`); check for an existing
SelahCue privacy/terms matter task first, and set its status to `awaiting facts / decisions`.

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
Entity: {{LEGAL_ENTITY_NAME}} (unconfirmed)   Jurisdiction(s): Nigeria (NDPA 2023, GAID 2025) primary; EU GDPR, UK GDPR/DUAA 2025, US (CCPA/COPPA) flagged   Requested by: repo owner via coordinating agent (PR #133, ticket 17tnw2b0q93)
Version/status: v0.2 — Draft — placeholders and launch-readiness conditions must be cleared
Revision reason: owner direction to write both policies for the launch state — all feature-gated blocks and hedging removed; activation, licence check-ins, customer portal, billing (full Part C), downloads, cloud transcription and AI notes, licensed translations, and account deletion/export written as live features; undecided business facts kept as placeholders; [PROPOSED] flags moved to notes §6 with acceptance gated by checklist row L-50.
Facts: basis unchanged from v0.1 (code verification 2026-10-01). Launch-state statements not true today are tracked in notes §4 (56 rows, hard launch gate). Open placeholders — 61 (9 new: STT_ROUTE, PUBLISHER_REPORTING_DATA, TRIAL_TERMS, MERCHANT_OF_RECORD, BILLING_PERIODS, PRORATION_TERMS, DOWNGRADE_TIMING, FAILED_PAYMENT_GRACE_PERIOD, RETRY_ALLOWANCE_TERMS).
Law checked: as v0.1; no new research. Added analysis: NDPA s.24 transparency as the legal basis of the launch gate; payment-provider cookies; COPPA exposure from cloud transcription.
Risks/decisions: publishing before every §4 row is satisfied would make the policies false (misrepresentation; NDPA s.24/s.27); plus all v0.1 risks. Specialist review: Nigerian data protection counsel; EU/UK privacy and consumer counsel if selling there; US counsel before US subscriptions/cloud launch.
Boundary: drafted and saved locally only; not committed, published, signed, filed or sent.
Draft: docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md; docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md; docs/legal/LEGAL-DRAFT-NOTES.md (worktree .claude/worktrees/legal-drafts, branch docs/17tnw2b0q93-legal-privacy-terms-drafts)
```
