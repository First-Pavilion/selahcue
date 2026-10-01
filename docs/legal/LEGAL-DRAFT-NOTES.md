# Legal drafting notes — SelahCue platform Privacy Policy and Terms of Service

> **DRAFT — NOT LEGAL ADVICE — REQUIRES REVIEW BY A QUALIFIED LAWYER BEFORE PUBLICATION**
>
> Internal working notes. Not for publication. Prepared 2026-10-01 by an AI drafting assistant
> (not a lawyer). Review status: **Draft — facts to confirm.**

## 1. Matter profile

| Item | Value |
|---|---|
| Brand | SelahCue |
| Contracting legal entity | **Unknown** — `{{LEGAL_ENTITY_NAME}}`. Owner is described as First Pavilion (firstpavitech.com), Lagos; the exact entity, its registration and its relationship to the SelahCue brand are not confirmed anywhere in the repository. |
| Documents | `docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md` (v0.1), `docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md` (v0.1), this file |
| Requested by | Repository owner, via the coordinating agent; ClickUp delivery ticket `17tnw2b0q93` (from the branch name) |
| Audience | Churches and other organisations worldwide; the individual staff and volunteers who create accounts; website visitors |
| Primary jurisdiction | Nigeria (NDPA 2023 + NDPC GAID 2025) |
| Secondary jurisdictions | EU GDPR, UK GDPR/DPA 2018/PECR as amended by DUAA 2025; US exposure (CCPA, COPPA) flagged |
| Existing documents kept unchanged | `docs/legal/PRIVACY.md` and `docs/legal/TERMS.md` (SelahCue Controller mobile app) |

## 2. How to read the drafts

- **`{{PLACEHOLDER}}`** — a fact or decision nobody has supplied. Never publish with one left in.
- **`[CONDITIONAL — X]`** — text describing something that is designed or decided but **not built
  or not released**. Publish it only when X ships. Each block says what to publish instead.
- **`[CONFIRM ...]`** — a statement I believe is true from the code but could not fully verify (for
  example, whether a UI control exists). Check it, then delete the marker.
- **`[PROPOSED]`** — a new risk allocation I added. It is not an agreed term; the owner must accept,
  change or delete it.

## 3. Placeholder register

| Placeholder | Meaning | Used in | Who decides |
|---|---|---|---|
| `{{LEGAL_ENTITY_NAME}}` | Exact registered name of the contracting/controller entity | Both | Owner |
| `{{REGISTERED_ADDRESS}}` | Registered office address | Both | Owner |
| `{{COMPANY_REGISTRATION_NUMBER}}` | CAC (or other) registration number | Both | Owner |
| `{{EFFECTIVE_DATE}}` | Date each document takes effect | Both | Owner, at publication |
| `{{WEBSITE_URL}}` | Production marketing-site URL | Both | Owner |
| `{{PRIVACY_POLICY_URL}}` | Public URL of the privacy policy | Both | Owner |
| `{{TERMS_URL}}` | Public URL of the terms | Terms | Owner |
| `{{PRIVACY_CONTACT_EMAIL}}` | Mailbox for privacy and rights requests | Privacy | Owner (see risk 1: three different domains in use) |
| `{{SUPPORT_CONTACT_EMAIL}}` | Support mailbox | Both | Owner |
| `{{LEGAL_NOTICES_EMAIL}}` | Address for formal legal notices | Terms | Owner |
| `{{DPO_NAME_AND_CONTACT}}` | Data Protection Officer (required for a data controller of major importance, NDPA s.32) | Privacy | Owner + counsel |
| `{{CONTROLLER_PRIVACY_POLICY_URL}}` | Public URL of the mobile Controller privacy policy | Privacy | Owner |
| `{{CONTROLLER_TERMS_URL}}` | Public URL of the mobile Controller terms | Terms | Owner |
| `{{SENSITIVE_DATA_CONDITION}}` | Sentence stating the legal condition relied on if account data is treated as revealing religious belief (or deleting the sentence if counsel concludes it is not sensitive data) | Privacy 3.1 | Counsel |
| `{{EMAIL_DELIVERY_PROVIDER}}` | Transactional email provider (not chosen; the API uses generic SMTP settings) | Privacy | Owner |
| `{{HOSTING_PROVIDER}}` | Hosting/infrastructure provider for the API and site (undecided per `implementation/api/README.md`) | Privacy | Owner |
| `{{HOSTING_REGION}}` | Country/region of servers | Privacy | Owner |
| `{{COUNTRY_OF_ESTABLISHMENT}}` | Country where the controller is established (assumed Nigeria) | Privacy | Owner |
| `{{TRANSFER_MECHANISMS}}` | Safeguards for transfers (NDPA basis; EU/UK SCCs/IDTA etc.) | Privacy | Counsel |
| `{{SERVER_LOG_RETENTION}}` | Web/API server log retention | Privacy | Owner (deployment) |
| `{{AUDIT_RECORD_RETENTION}}` | Audit-event retention (none set today) | Privacy | Owner + counsel |
| `{{ACCOUNT_RETENTION_AFTER_CLOSURE}}` | How long account data is kept after closure | Privacy | Owner + counsel |
| `{{UNVERIFIED_SIGNUP_RETENTION}}` | Deletion period for never-verified sign-ups (GAID Art. 21(2) suggests 6 months) | Privacy | Owner + counsel |
| `{{LICENCE_RECORD_RETENTION}}` | Licence/device record retention (Platform PRD §16 proposes 24 months post-terminal) | Privacy | Owner |
| `{{FINANCIAL_RECORD_RETENTION}}` | Payment/tax record retention (statutory) | Privacy | Counsel/accountant |
| `{{SUPPORT_RETENTION}}` | Support email retention | Privacy | Owner |
| `{{LIA_REFERENCE}}` | Reference to the Legitimate Interest Assessment (GAID Art. 26, Schedule 8) — or delete the sentence | Privacy | Owner + counsel |
| `{{MINIMUM_ACCOUNT_AGE}}` | Minimum age to hold an account (recommend 18: NDPA "child" follows the Child's Rights Act 2003) | Both | Owner + counsel |
| `{{EU_REPRESENTATIVE}}` / `{{UK_REPRESENTATIVE}}` | GDPR / UK GDPR Art. 27 representatives, if required | Privacy | Counsel |
| `{{DEVICE_FINGERPRINT_METHOD}}` | How the desktop will generate the device identifier (not designed; deliberately left to the shell, `selahcue-licensing/src/device.rs`) | Privacy | Engineering + counsel |
| `{{PAYMENT_PROVIDER}}` | Payment provider / merchant of record (open decision D2) | Both | Owner |
| `{{PAYMENT_DATA_RECEIVED}}` | Exact payment data SelahCue receives from the provider | Privacy | Owner, after D2 |
| `{{TRANSLATION_DOWNLOAD_HOST}}` | Host for downloadable Bible translations (today a non-functional placeholder URL) | Privacy | Owner |
| `{{STT_PROVIDER}}` | Cloud speech-to-text provider (planned: Deepgram, per project notes — not final) | Both | Owner |
| `{{NOTES_PROVIDER}}` | Cloud AI notes provider (planned: OpenAI, per project notes — not final) | Both | Owner |
| `{{NOTES_ROUTE}}` | Whether notes go directly from the desktop to the provider or via SelahCue servers (open: ADR-0028 options A/C) | Privacy | Owner + engineering |
| `{{DPA_REFERENCE}}` | Location of the data processing terms for cloud features | Both | Counsel (DPA not yet drafted) |
| `{{PROVIDER_RETENTION}}` | How long cloud providers keep audio/transcripts | Privacy | Owner, from provider contracts |
| `{{MODEL_TRAINING_STATEMENT}}` | Statement on whether providers may use data to train models — only once verified in the provider contracts | Privacy | Owner + counsel |
| `{{THIRD_PARTY_NOTICES_LOCATION}}` | Where open-source licence notices are published (none found in the repo) | Terms | Engineering |
| `{{ALLOWANCE_RESET_PERIOD}}` | Usage-allowance reset period (conflicting decisions: monthly per DEC-008 vs weekly per later owner decision) | Terms | Owner |
| `{{CURRENCY}}` | Billing currency | Terms | Owner |
| `{{RENEWAL_TERMS}}` | Auto-renewal terms | Terms | Owner + counsel |
| `{{REFUND_POLICY}}` | Refund policy (tied to D2, FR-536) | Terms | Owner + counsel |
| `{{PRICE_CHANGE_NOTICE_DAYS}}` | Notice period for price changes | Terms | Owner |
| `{{NDI_ATTRIBUTION_TEXT}}` | Attribution/trademark wording required by the NDI SDK licence (FR-140) | Terms | Owner, from the NDI licence |
| `{{SUPPORT_TERMS}}` | Support hours/response commitments, if any | Terms | Owner |
| `{{MINIMUM_LIABILITY_AMOUNT}}` | Floor of the liability cap | Terms | Owner + counsel |
| `{{GOVERNING_LAW}}` | Governing law | Terms | Owner + counsel |
| `{{DISPUTE_FORUM}}` | Court or arbitral forum | Terms | Owner + counsel |
| `{{TERMS_CHANGE_NOTICE_DAYS}}` | Notice period for material changes to the Terms | Terms | Owner |

Inline `[CONFIRM]` markers: Privacy 2.4 (transcript delete control and automatic-deletion setting
are exposed in the operator console; the app keeps no audio recordings), 4.1 (`csrftoken` lifetime
on the deployed site), 9.1 (HTTPS on the deployed site); Terms 6.3 (device list and deactivation in
the customer portal).

Conditional blocks: device activation, licence notifications, billing, cloud features, customer
portal, licensed translations, Google Fonts, EU/UK representatives.

## 4. Assumptions

1. The controller/contracting entity is a Nigerian company in Lagos (owner stated "Nigerian-based,
   Lagos"). Not verified; drives NDPA s.2(2)(a) applicability and the governing-law analysis.
2. Accounts are opened by organisations (churches), usually through a staff member or volunteer. Some
   sign-ups may be individuals acting as consumers.
3. The released desktop product is what `.github/workflows/windows-installer.yml` builds
   (`--release`, `--features stt`, plus default at-rest encryption, with NDI bundled). No macOS or
   Linux release pipeline exists in the repo; macOS signing credentials are "not yet supplied"
   (`docs/ops/DEPLOYMENT.md`). If another build is distributed, re-check it.
4. Development builds (`make launch`) can stream audio to Deepgram and send transcripts to OpenAI
   using developer keys. They are not distributed to customers. The drafts describe only distributed
   builds.
5. No ClickUp, deployment console or provider contract was reviewed. Hosting, email and payment
   providers are therefore unknown.
6. "Version" and "date" fields on the live stub pages are not meaningful and were not reused.

## 5. Fact-to-source table

Status key: **V** = verified in code or config in this worktree · **D** = documented decision or
requirement, not necessarily built · **I** = inferred, needs confirmation · **M** = from the
owner's project memory notes, not verified in the tree.

### 5.1 Privacy Policy facts

| # | Claim in the draft | Source | Status |
|---|---|---|---|
| P1 | Plans, slides, decks, songs, themes and screen settings are stored locally | `implementation/desktop/crates/selahcue-data/src/lib.rs` (plan, deck, media, theme, screen, output repos); `docs/architecture/ARCHITECTURE.md` §8 | V |
| P2 | Media files are referenced by path, not copied into the database | `ARCHITECTURE.md` §8; DEC-003 | D |
| P3 | Transcripts, corrections and detected references are stored locally | `selahcue-data/src/transcript_repo.rs` | V |
| P4 | Sermon-note drafts are stored locally | `selahcue-data/src/lib.rs` (`sermon_note_repo`) | V |
| P5 | Released builds send no content, transcripts or audio to SelahCue | Root `Makefile` (`RELEASE_UNSAFE_FEATURES := dev-keys openai-notes cloud-stt`, `release-ai-guard`); `windows-installer.yml` (`cargo tauri build --features stt`); `selahcue-operator/Cargo.toml` (`cloud-live` opt-in, "the live service does not exist yet"); `selahcue-cloud/src/lib.rs` | V (Windows release path) |
| P6 | Transcript database encrypted at rest by default; key in the OS credential store or derived from a passphrase (Argon2id) | `selahcue-desktop/Cargo.toml` (`default = ["encryption"]`); `selahcue-operator/Cargo.toml` (`read-encrypted-transcripts`); `Makefile` `ENCRYPTION_STATUS` | V |
| P7 | Slide-deck library is not encrypted by the app | `selahcue-operator/Cargo.toml` comment on `selahcue-data` ("The operator-local deck DB ... stays unencrypted") | V |
| P8 | Deleting a transcript removes corrections and detections, and by default the sermon note | `transcript_repo.rs` (FK cascade; `RetentionSettings::default` `delete_cascade_to_notes: true`, marked a proposal awaiting owner sign-off) | V (repository); UI exposure not checked |
| P9 | Transcripts kept until deleted | `transcript_repo.rs` (`retention_days: None` default) | V |
| P10 | No audio recordings kept | No audio store among `selahcue-data` modules; PRD FR-153 contemplates raw-audio retention, so this may change | I |
| P11 | Paired mobile devices receive current/next slide, timers and live transcript preview over an encrypted, pinned connection | `docs/legal/PRIVACY.md` §3; `ARCHITECTURE.md` §9; PRD FR-088 | V (per mobile draft) |
| P12 | Desktop announces itself on the local network | `selahcue-desktop/Cargo.toml` (`mdns-sd`); `ARCHITECTURE.md` §9 | V (dependency) |
| P13 | NDI output broadcasts video on the local network | `selahcue-desktop/Cargo.toml` (`ndi` feature); `windows-installer.yml` | V |
| P14 | Account fields: email, password hash, organisation name, country, time zone, optional name, role, status, verification time, sessions, failed-login counter and lock | `implementation/api/selahcue_api/apps/accounts/models.py`; `graphql/account_schema.py` (`RegisterCustomerUserInput`); `implementation/marketing/src/views/SignUpView.vue` | V |
| P15 | Country is suggested from the browser; time zone is detected automatically | `SignUpView.vue` (`guessCountry()`, `detectTimezone()`); helper implementations not read | V (call sites) |
| P16 | Staff can record internal notes about an organisation | `CustomerOrg.internal_notes` in `accounts/models.py` | V |
| P17 | Passwords stored as salted one-way hashes | `CustomerUser.password_hash` (`make_password`); DEC-013 ("passwords keep PBKDF2") | V |
| P18 | Verification link 24 h, reset link 1 h, session 30 days | `selahcue_api/settings.py` (`ACCOUNT_*_TTL_SECONDS`, environment-overridable) | V |
| P19 | "Someone tried to sign up with your address" email | `apps/accounts/tasks.py` (`send_account_exists_task`) | V |
| P20 | No marketing emails | Only three transactional tasks in `apps/accounts/tasks.py` | V (accounts app) |
| P21 | Activation data: device identifier, platform, app version, device name; device token; signed licence file | `apps/devices/models.py`; `account_schema.py` (`ActivateDeviceInput`); `selahcue-licensing/src/device.rs`; `implementation/api/README.md` | V (server); client not shipped |
| P22 | Released desktop does not activate yet | `selahcue-licensing` not a dependency of `selahcue-operator` or `selahcue-desktop` (their `Cargo.toml`); `windows-installer.yml` comment ("nothing here links selahcue-licensing yet"); Platform PRD §2 | V |
| P23 | Activation does not send slides, transcripts, audio or network logs | `ActivateDeviceInput` fields | V |
| P24 | Licence keys stored hashed with a masked prefix/suffix | `apps/license_keys/models.py` | V |
| P25 | No billing yet | `implementation/api/README.md` (billing webhook returns 501); Platform PRD NG-P6 and D2 | V |
| P26 | Rate limiting by IP; IPv6 truncated to /64; windows of at most 1 hour | `apps/throttling/services.py`; `settings.py` `SELAHCUE_THROTTLE_*` | V |
| P27 | Audit records: actor id, action, target, result, time; secrets removed | `apps/audit/models.py`, `apps/audit/services.py`, `graphql/redaction.py` | V |
| P28 | No analytics, telemetry or crash reporting | `selahcue-operator/Cargo.toml`, `selahcue-desktop/Cargo.toml`, `implementation/api/pyproject.toml` (no Sentry SDK, although `SENTRY_DSN` is read in settings), `implementation/mobile/selahcue_controller/pubspec.yaml`, `implementation/marketing/package.json` | V (direct dependencies only; transitive dependencies not audited) |
| P29 | Speech model downloaded from `huggingface.co` on first use; checked before use | `selahcue-stt/src/model.rs` (`BASE_URL`), `selahcue-stt/src/model_fetch.rs` | V |
| P30 | Downloadable translations are not functional | `selahcue-scripture/src/download.rs` (`https://OWNER-SUPPLIED.invalid/...` placeholder) | V |
| P31 | Cloud features off by default; per-feature, Administrator-gated consent; cloud transcription streams live audio; notes send only completed transcript text | `selahcue-core/src/providers.rs` (`ConsentState`, `NoteRequest`); `selahcue-cloud/src/lib.rs`; PRD FR-132/133/137 | V (design, unreleased) |
| P32 | Cookies `selahcue_account_session` (HttpOnly, Secure, SameSite=Strict, 30 days) and `csrftoken`; local storage key `selahcue.session` holding role, organisation id and expiry | `account_schema.py` (`_set_session_cookie`); `settings.py`; `selahcue_api/urls.py` (`graphql/csrf`); `implementation/marketing/src/lib/auth/session.ts` | V (`csrftoken` lifetime is the Django default, not checked on a deployment) |
| P33 | Site loads Inter from Google Fonts | `implementation/marketing/index.html` | V |
| P34 | No analytics or advertising on the site | `package.json` (only `vue`, `vue-router`); `index.html`; `src/main.ts` | V |
| P35 | Password change signs out all sessions; lockout after repeated failures | `accounts/models.py` (`password_changed_at`); DEC-007; `settings.py` (5 attempts / 900 s, overridable) | V |
| P36 | No self-service account deletion or data export | `account_schema.py` has no such mutation; `on_delete=PROTECT` on account models | V |
| P37 | Customer portal shows members/devices | Platform PRD FR-525 (gap: no read surface exists) | D (conditional in draft) |

### 5.2 Terms of Service facts

| # | Claim | Source | Status |
|---|---|---|---|
| T1 | Core presentation works offline without an account | PRD CON-2/NFR-015; `selahcue-licensing/src/lib.rs` ("every failure permits presentation"); `SignUpView.vue` copy | V/D |
| T2 | One email address, one account | `CustomerUser` unique constraint on `email` | V |
| T3 | Bundled translations: KJV, WEB, ASV, WEBBE, Darby | `selahcue-scripture/src/lib.rs` | V |
| T4 | KJV subject to Crown letters patent in the UK | `selahcue-scripture/src/lib.rs` comment; ebible.org copyright page (secondary) | V (secondary source) |
| T5 | Scripture suggestions require operator approval by default; auto-display is opt-in | PRD FR-115/116; `ARCHITECTURE.md` §10 | D (implementation not checked) |
| T6 | AI notes labelled AI-generated with a fabrication disclosure | `selahcue-cloud/src/lib.rs` (`ai_generated`, `FABRICATION_DISCLOSURE`); PRD FR-123/128 | V (code path) |
| T7 | Free-plan watermark | DEC-008; Platform PRD FR-548 | D (not built) |
| T8 | 7-day grace, then the free Plan from the next session | DEC-009; Platform PRD FR-521/549 | D (not built) |
| T9 | Soft suspension: activated devices keep presenting; new activations and cloud stop | DEC-010; Platform PRD FR-504 | D (not built) |
| T10 | A downgrade does not deactivate devices; limit applied at session start | DEC-009; Platform PRD FR-550 | D (not built) |
| T11 | Activation by Administrator sign-in or enrolment key | DEC-005/007/011; `implementation/api/README.md` | V (server) |
| T12 | Signed licence file allows offline use until the licence ends | DEC-004/005; `implementation/api/README.md` (`/v1/entitlements/manifest`) | V (server) |
| T13 | Licence changes take effect at the next session, never mid-presentation | Platform PRD CON-P1, FR-520/549 | D |
| T14 | Administrator device deactivation | Platform PRD FR-511 (no mutation exists today) | D (marked CONFIRM) |
| T15 | Third parties: NDI, Hugging Face, Google Fonts | `selahcue-desktop/Cargo.toml`; `selahcue-stt/src/model.rs`; `implementation/marketing/index.html` | V |
| T16 | Usage-allowance periods | DEC-008 (monthly, billing anniversary) vs owner decision of 2026-09-27 (weekly, Monday 00:00 local) | M — conflict; left as a placeholder |

## 6. Claims on the current live stub pages

Sources: `implementation/marketing/src/views/PrivacyView.vue` and `TermsView.vue`.

### 6.1 False, or not true today

1. **"billing information through our payment processor (Stripe)"** — no payment integration exists;
   the billing webhook returns 501; the provider is open decision D2 (Stripe is only one option).
2. **"Copyrighted translations (e.g. NIV, ESV, NLT) are downloaded post-activation under specific
   publisher entitlement agreements"** — no licensed translation, publisher agreement or download
   pipeline exists (`downloads:*` endpoints return 501; "first licensed translations" is an open
   owner decision in `implementation/api/README.md`).
3. **"Public-domain Bibles (e.g. WEB, ASV, BSB) are bundled"** — BSB is not bundled. The bundled set is
   KJV, WEB, ASV, WEBBE and Darby.
4. **"Pro plans are billed on a monthly or annual recurring basis. You may cancel ... via your
   account portal."** — no billing, and the account portal has no plan or cancellation function.
5. **"the SelahCue desktop software transmits an anonymized hardware fingerprint, platform OS
   version, and app version during activation"** — the released desktop does not activate at all.
   When it does, the identifier is a stable per-device value linked to an account (pseudonymous,
   not anonymised); the server stores the platform, not the OS version; a device name is also sent.
6. **"Sermon audio streams and generated transcripts never leave your local venue machine unless you
   explicitly enable an opt-in cloud AI integration"** — inaccurate in two ways: transcript previews
   go to paired mobile devices over the local network, and no cloud integration exists in released
   builds.
7. **"You agree not to extract, reverse engineer, or redistribute encrypted Bible databases"** — no
   encrypted Bible databases exist; bundled texts are compressed, not encrypted.

### 6.2 Partly true or overstated

8. **"On-device speech-to-text (Whisper AI) runs 100% locally ... using native GPU acceleration"** —
   recognition runs locally (whisper.cpp with Whisper model weights), but the model is downloaded
   from Hugging Face on first use, and only macOS builds compile GPU (Metal) acceleration; the
   Windows installer build is CPU-only.
9. **"we collect your organization name, primary contact name, email address"** — organisation name
   and email are collected; there is no "primary contact name" field (an optional display name
   exists); the stub omits country, time zone and password.
10. **"Data Protection Rights (GDPR & NDPA 2023) ... access, rectify, or request deletion"** — an
    incomplete list (no restriction, objection, portability, withdrawal of consent or complaint to
    a regulator), and "billing data" does not exist.
11. **"license ... up to the seat count specified in your Pro or Church subscription plan"** — plan
    names are unsettled (see risk 9); a "Church" plan does not appear in any decision record.

### 6.3 Not verifiable

12. **`privacy@selahcue.app`** (privacy stub) — no evidence that this mailbox or domain exists. The API
    defaults to `noreply@selahcue.com` as sender and `info@firstpavitech.com` as a default address.
13. **"Last Updated: August 8, 2026"** on both pages — no record of a review or publication.
14. **"your organization agrees to be bound"** by downloading — acceptance is not recorded anywhere
    (see risk 8).
15. **"SelahCue grants ..."** — SelahCue is a brand; no legal entity is named on either page or in
    the footer ("© 2026 SelahCue").

### 6.4 Other site content that creates legal risk (outside the brief, flagged)

- **Contact page** (`ContactView.vue`): the form sends nothing (a timer fakes success) but tells the
  user "A SelahCue specialist will respond within 24 hours". This misleads users and silently loses
  messages. It also lists `support@selahcue.app` (unverified), a Discord community of "1,200+ worship
  tech leaders" (unverified) and links that point to `#`.
- **Pricing page** (`PricingView.vue`): Free/Pro/Church, $19 per month, "Save 20%" annually, "Prorated
  charges will apply", "credit cards, PayPal, and ACH" and a "24/7 SLA" — none of this is built or
  decided, and it conflicts with the recorded tier decisions.
- **Download page** (`DownloadView.vue`): "Version 1.2.0 (Stable)" for Windows and macOS — the app
  version is 0.1.0 (`tauri.conf.json`), there is no macOS release pipeline, and the buttons link
  nowhere.
- **Sign-up page**: the "I agree to the Terms of Service and Privacy Policy" checkbox is checked only
  in the browser; the API stores no acceptance record or version.

## 7. Jurisdiction analysis

### 7.1 Nigeria — NDPA 2023 and GAID 2025 (primary)

- **Application.** The NDPA applies where the controller is domiciled, resident or operating in
  Nigeria, where processing happens in Nigeria, or where data subjects are in Nigeria (s.2(2)). A
  Lagos-based controller is in scope for all its users worldwide. GAID Art. 8(2) reads "operating in
  Nigeria" to include targeting data subjects in Nigeria.
- **GAID 2025.** The General Application and Implementation Directive (NDPC/NDP ACT-GAID/01/2025)
  took effect on 19 September 2025, after which the NDPR 2019 ceased to apply (GAID Art. 3(3)). It is
  the main implementing instrument and shapes several drafting choices below.
- **Privacy notice content.** NDPA s.27(1) requires: identity and contact details; the lawful basis
  under s.25(1) or s.30(1) and purposes; recipients; data-subject rights; retention period; the right
  to complain to the NDPC; and any automated decision-making. Section 27(3) requires a clear,
  concise, accessible privacy policy. GAID Art. 27(3) adds "means of processing" and third-party
  access and its purpose. GAID Art. 7(j)–(m) and (w) require the policy to be published and the
  complaints process explained. **The draft covers each item, but retention periods are still
  placeholders, so it does not yet meet s.27(1)(e).**
- **Lawful bases.** NDPA s.25(1); legitimate interests are excluded where overridden or unexpected
  (s.25(2)). GAID Art. 26 makes a documented Legitimate Interest Assessment (Schedule 8) mandatory
  before relying on legitimate interests. **Action: complete an LIA for security, fraud prevention and
  audit logging.**
- **Sensitive personal data.** "Sensitive personal data" includes religious or similar beliefs
  (s.65). Section 30(1) restricts processing to listed conditions. Section 30(1)(d) covers
  processing by religious non-profits about their own members, which protects churches, not
  SelahCue. GAID Art. 18(1)(b) requires consent for processing sensitive data. Two exposures:
  1. **Account data.** A church name plus a person's email may reveal religious affiliation. Whether
     this is sensitive data depends on interpretation (compare the EU position in 7.2). Counsel
     should decide whether explicit consent at sign-up is needed (`{{SENSITIVE_DATA_CONDITION}}`).
  2. **Cloud features.** Sermon audio and transcripts will often reveal religious beliefs, and
     possibly health or other sensitive data (prayer requests). If SelahCue or its providers
     process them, a s.30 condition, a DPIA and processor terms are required.
- **Children.** "Child" takes its meaning from the Child's Rights Act 2003 (s.65). Under s.31,
  consent must come from a parent or guardian, with appropriate age verification. The draft sets a
  minimum account age placeholder (18 recommended) and puts notice duties for children's voices in
  transcripts on churches.
- **Rights.** Access, copy, correction, erasure and restriction (s.34), withdrawal of consent (s.35),
  objection including to direct marketing (s.36), automated decisions (s.37) and portability (s.38).
  NDPA has no fixed day count ("without constraint or unreasonable delay", s.34(1)); the draft uses
  the stricter GDPR one-month limit globally.
- **Security and breach.** Section 39 requires appropriate measures. Under s.40(2), the controller
  must notify the NDPC within 72 hours of a breach likely to risk individuals' rights, and must tell
  data subjects immediately where risk is high (s.40(3)); GAID Art. 7(p)–(q) restates this.
- **Processors.** Section 29 requires written agreements with processors; GAID Art. 34 covers data
  processing agreements. **Action: sign DPAs with the hosting, email and (later) payment and AI
  providers.**
- **Cross-border transfers.** Sections 41–43 allow transfers where the recipient is subject to
  adequate protection (law, binding corporate rules, contractual clauses, codes, certification), or
  under a s.43 derogation; the basis must be recorded (s.41(2)). **GAID Art. 18(1)(e) additionally
  says consent is required "before personal data may be transferred to a country in respect of which
  the Commission has not made an adequacy decision".** Read literally, this would require consent for
  any transfer to a non-adequacy country (for example, US hosting or email), even where s.41(1)(a)
  safeguards exist. This conflicts with the Act's structure (and the Act prevails, GAID Art. 3(2)), so
  counsel must decide the approach before choosing hosting.
- **Data controller of major importance.** Under s.44 and GAID Schedule 7 (Guidance Notice
  NDPC/HQ/GN/VOL.03/B/24), designation applies to an entity that processes the personal data of more
  than 200 data subjects in six months, or that "carries out commercial Information Communication
  Technology (ICT) services on any digital device which has storage capacity ... and belongs to
  another individual". Tiers are UHL (over 5,000 data subjects in six months; ₦250,000 fee), EHL
  (over 1,000 among its factors; ₦100,000 fee) and OHL (over 200). Obligations include registration,
  a DPO (s.32), an annual compliance audit and CAR filing (GAID Arts. 7, 9, 10) and staff training.
  SelahCue will probably qualify once it has more than 200 account holders, and arguably already by
  supplying software that runs on customers' devices. **Action: counsel to confirm the tier and
  register.**
- **DPIA.** Section 28 requires a DPIA for likely high-risk processing. GAID Art. 28(3) makes a DPIA
  mandatory, **and filed with the Commission**, where sensitive data is involved, for software
  enabling communication with data subjects, and for e-commerce services. Cloud transcription of
  sermons almost certainly triggers this.
- **Cookies.** GAID Art. 19 requires consent for cookies except "necessary cookies" (core functions
  such as security), which "do not need the ticking of a box". GAID Art. 7(l) separately expects a
  cookie notice on the homepage, placed so it obstructs the centre or a side of the page (not the
  bottom), with an option to accept or decline. The site uses only necessary cookies, so consent is
  not needed. Whether a prominent notice is still expected is an interpretive point for counsel; a
  short, dismissible notice is low-cost insurance. The Google Fonts call is not a cookie, but GAID
  Art. 19(8) treats other "tracking tools" like cookies; self-hosting the font avoids the question.
- **Retention defaults.** GAID Art. 49(3): where no period is set by law, storage lapses no later
  than six months after the purpose is accomplished. GAID Art. 21(2): data from a contract that did
  not materialise is destroyed within six months. These support a six-month purge of never-verified
  sign-ups and a defined post-closure period.
- **Third-party sharing.** GAID Art. 41(9) says "explicit consent must be obtained" where data is
  shared with third parties. Applied literally to processors, this would be unworkable; counsel
  should confirm it does not cover service providers acting on instructions.
- **Consumer protection.** The FCCPA 2018 includes s.127 (unfair, unreasonable or unjust contract
  terms), s.128 (notice required for certain terms), s.137 (liability not to be excluded), s.142
  (supply of services) and s.144 (exclusion of implied terms). I verified the section headings only,
  not the text. The warranty, liability and consumer-rights clauses (Terms ss.16–18) are drafted to
  preserve mandatory rights, but counsel must check them against the text.
- **Disputes.** The Arbitration and Mediation Act 2023 (signed 26 May 2023) replaced the Arbitration
  and Conciliation Act 1988, so arbitration seated in Lagos is a credible option. Whether to choose
  courts or arbitration, and which institution, is an owner and counsel decision.

### 7.2 European Union — GDPR

- **Territorial scope.** Article 3(2)(a) applies to a controller outside the EU that offers goods or
  services to people in the EU, whether paid or free. An English-language site with a "global church
  audience", USD pricing and EU country choices at sign-up may be enough to show intent to offer
  services in the EU. **Fact question for the owner: do you intend to serve EU churches?** If so, the
  GDPR applies to EU users' account data.
- **Representative.** Article 27(1) requires a written EU representative; the Art. 27(2)(a) exemption
  covers only "occasional" processing that does not involve large-scale special-category data.
  Ongoing account processing is not occasional, so a representative is likely required.
- **Notice.** Articles 13(1)–(2) list the information required; the draft covers each item. Article
  12(3) requires a response within one month, extendable by two more months.
- **Special categories.** Article 9(1) covers data "revealing ... religious or philosophical beliefs".
  The CJEU in C-184/20 *OT v Vyriausioji tarnybinės etikos komisija* (Grand Chamber, 1 August 2022)
  held that data indirectly revealing a special category (there, sexual orientation through a
  spouse's name) is special-category data. By analogy, a regulator could treat a person's account
  with a church name as revealing religious belief. Counsel should decide whether to rely on explicit
  consent (Art. 9(2)(a)) at sign-up.
- **Children.** Article 8(1) sets 16 as the default age of digital consent for information society
  services (member states may set a lower age; I did not verify the floor in this session). An 18+
  account rule avoids the issue.
- **Cookies and fonts.** The ePrivacy Directive Art. 5(3) applies to cookies (not separately verified
  in this session; strictly necessary cookies are exempt). In *LG München I*, 3 O 17493/20 (20 January
  2022), a German court held that loading Google Fonts from Google's servers without consent
  unlawfully disclosed visitors' IP addresses and awarded €100 damages. This is a first-instance
  German decision, not binding EU-wide, but it prompted waves of demand letters. **Recommendation:
  self-host the Inter font and delete the Google Fonts paragraphs from both drafts.**
- **Transfers.** For EU data the controller collects directly in Nigeria, counsel should confirm
  whether Chapter V applies to the collection itself; onward transfers to providers in third
  countries will need SCCs or an adequacy decision.

### 7.3 United Kingdom

- UK GDPR and the Data Protection Act 2018 mirror the EU analysis, including UK Art. 3(2) and Art. 27
  (UK representative).
- The Data (Use and Access) Act 2025 (2025 c. 18) received Royal Assent on 19 June 2025. Its main
  Part 5 data protection changes commenced on 5 February 2026 (gov.uk commencement plan). Section 103
  (complaints by data subjects; new s.164A DPA 2018) requires controllers to run a complaints process.
  A secondary source reports it commenced on 19 June 2026 under the Commencement No. 6 Regulations;
  **I did not verify this against legislation.gov.uk.** The draft's "contact us first" complaints
  route (Privacy 11.5) supports compliance but needs an actual process.
- Section 112 amends the PECR rules on storage and access technologies; the ICO has issued updated
  guidance, including new exceptions for some analytics. This does not affect the current site,
  which uses only necessary cookies.
- **KJV.** The Terms flag the Crown letters patent restriction on printing and importing the KJV in
  the UK.

### 7.4 United States

- **CCPA/CPRA.** It applies to for-profit businesses that meet one threshold: annual gross revenue
  over $26,625,000 (adjusted 1 January 2025), 100,000 or more California consumers or households, or
  50% or more of revenue from selling or sharing personal information. SelahCue is probably below all
  three today. The draft nonetheless states that SelahCue does not sell or share personal data, which
  is true now.
- **Other state privacy laws** have similar thresholds; not individually researched.
- **COPPA.** It applies to operators of online services directed to children under 13, or with actual
  knowledge that they collect children's data. SelahCue is not directed to children and collects no
  data from children; local transcription by a church is not collection by SelahCue. The amended
  COPPA Rule took effect on 23 June 2025, with compliance due by 22 April 2026 (secondary sources).
  **Exposure returns if cloud transcription sends children's voices to SelahCue's providers;** counsel
  should assess this before launch.
- **Automatic renewal laws** in several states govern subscription disclosures and cancellation; not
  researched. Part C stays unpublished until counsel reviews it.

### 7.5 Governing law and forum

Options for `{{GOVERNING_LAW}}` / `{{DISPUTE_FORUM}}`:

1. **Nigerian law, courts of Lagos State** — simplest for a Lagos company; foreign customers may
   resist it, and consumer law in their countries may still apply.
2. **Nigerian law, arbitration seated in Lagos under the AMA 2023** — confidential and more
   enforceable abroad through the New York Convention; costlier for small claims.
3. **Mixed approach** — Nigerian law for organisations, with consumers keeping home-country rights
   (already in Terms s.22.3).

Recommendation: option 1 or 2, with the s.22.3 consumer carve-out. This needs counsel's decision.

## 8. Source ledger

All checked 2026-10-01.

| Proposition | Authority | Provision | URL | Drafting implication |
|---|---|---|---|---|
| NDPA territorial scope | Nigeria Data Protection Act 2023 | s.2(2) | https://www.dataguidance.com/sites/default/files/data_protection_act_2023.pdf (mirror of the Act; read page images) | NDPA governs all users |
| Lawful bases; legitimate-interest limits | NDPA 2023 | s.25(1)–(2) | as above | Policy s.5 |
| Consent rules | NDPA 2023 | s.26 | as above | Marketing consent; withdrawal |
| Privacy notice content | NDPA 2023 | s.27(1), (3) | as above | Policy structure |
| DPIA | NDPA 2023 | s.28 | as above | Cloud features |
| Processor agreements | NDPA 2023 | s.29 | as above | DPAs required |
| Sensitive data conditions | NDPA 2023 | s.30, s.65 ("religious or similar beliefs") | as above | `{{SENSITIVE_DATA_CONDITION}}` |
| Children | NDPA 2023 | s.31; s.65 ("child" per Child's Rights Act 2003) | as above | Minimum age; transcription notice |
| Data-subject rights | NDPA 2023 | ss.34–38 | as above | Policy s.11 |
| Security; 72-hour breach notice | NDPA 2023 | ss.39–40 | as above | Policy s.9 |
| Cross-border transfers | NDPA 2023 | ss.41–43 | as above | Policy s.7 |
| Registration of DCMI | NDPA 2023 | s.44; s.65 definition | as above | Registration action |
| Complaints to the NDPC | NDPA 2023 | s.46 | as above | Policy s.11.5 |
| GAID displaces NDPR 2019 | GAID 2025 | Art. 3(3) | https://ndpc.gov.ng/wp-content/uploads/2025/07/NDP-ACT-GAID-2025-MARCH-20TH.pdf | Cite GAID, not NDPR |
| GAID effective 19 September 2025 | Secondary (law firm) | — | https://www.banwo-ighodalo.com/grey-matter/are-you-gaid-2025-ready-navigating-nigerias-gaid-2025-what-your-organisation-needs-to-know-how-bi-can-support-your-compliance-journey/ | Commencement (verify on ndpc.gov.ng) |
| Compliance measures; cookie notice placement | GAID 2025 | Art. 7 | GAID URL above | Implementation actions |
| DCMI designation | GAID 2025 | Arts. 8–10; Schedule 7 | GAID URL above | Registration, CAR |
| Consent required: marketing, sensitive data, children, non-adequacy transfers | GAID 2025 | Art. 18(1) | GAID URL above | Transfer risk (risk 4) |
| Cookies | GAID 2025 | Art. 19 | GAID URL above | Policy s.4 |
| Six-month destruction after failed contract | GAID 2025 | Art. 21(2) | GAID URL above | Unverified sign-up retention |
| LIA required | GAID 2025 | Art. 26; Schedule 8 | GAID URL above | `{{LIA_REFERENCE}}` |
| Information to data subjects | GAID 2025 | Art. 27 | GAID URL above | Policy content |
| Mandatory, filed DPIA | GAID 2025 | Art. 28(3) | GAID URL above | Cloud features |
| Explicit consent for third-party sharing | GAID 2025 | Art. 41(9) | GAID URL above | Counsel question |
| Default six-month storage limit | GAID 2025 | Art. 49(3) | GAID URL above | Retention schedule |
| GDPR territorial scope | GDPR | Art. 3(2) | https://gdpr-info.eu/art-3-gdpr/ (unofficial mirror; EUR-Lex not retrievable) | EU applicability |
| Digital consent age 16 | GDPR | Art. 8(1) | https://gdpr-info.eu/art-8-gdpr/ | Minimum age |
| Special categories; explicit consent | GDPR | Art. 9(1), 9(2)(a) | https://gdpr-info.eu/art-9-gdpr/ | Sensitive-data risk |
| One-month response | GDPR | Art. 12(3) | https://gdpr-info.eu/art-12-gdpr/ | Policy s.11.2 |
| Notice contents | GDPR | Art. 13 | https://gdpr-info.eu/art-13-gdpr/ | Policy structure |
| EU representative | GDPR | Art. 27 | https://gdpr-info.eu/art-27-gdpr/ | `{{EU_REPRESENTATIVE}}` |
| Indirect revelation of special-category data | CJEU, C-184/20 (Grand Chamber, 1 August 2022) | — | https://curia.europa.eu/jcms/upload/docs/application/pdf/2022-08/cp220133lt.pdf (press release; identified by search, not opened) | Risk 3 |
| Google Fonts and IP disclosure | LG München I, 3 O 17493/20 (20 January 2022) | — | Secondary: https://www.ihk.de/bergische/recht-und-steuern/wettbewerbsrecht/google-fonts-5646176 | Self-host the font |
| DUAA 2025: c.18, s.103 complaints, s.112 storage and access | Data (Use and Access) Act 2025 | ss.103, 112, 142 | https://www.legislation.gov.uk/ukpga/2025/18/contents | UK complaints process |
| DUAA Royal Assent 19 June 2025; Part 5 commenced 5 February 2026 | UK Government commencement plan | — | https://www.gov.uk/guidance/data-use-and-access-act-2025-plans-for-commencement | UK analysis |
| s.103 commenced 19 June 2026 | Secondary | Commencement No. 6 Regulations 2026 | https://digitalpolicyalert.org/event/40956-data-use-and-access-act-2025-commencement-no-6-and-transitional-and-saving-provisions-regulations-2026-section-103-data-protection-complaints-including-data-protection-regulation-enter-into-force | Verify on legislation.gov.uk |
| CCPA revenue threshold $26,625,000 | California Privacy Protection Agency | CPI adjustment, effective 1 January 2025 | https://www.cppa.ca.gov/regulations/cpi_adjustment.html | US analysis |
| COPPA amendments: effective 23 June 2025; compliance 22 April 2026 | Secondary (law firm) | 16 CFR Part 312 | https://www.whitecase.com/insight-alert/unpacking-ftcs-coppa-amendments-what-you-need-know | US analysis (verify in Federal Register) |
| FCCPA unfair-terms provisions (headings only) | FCCPA 2018 | ss.127, 128, 137, 142, 144 | https://fccpc.gov.ng/wp-content/uploads/2022/07/FCCPA-2018.pdf | Terms ss.16–18 |
| AMA 2023 replaced ACA 1988 | Secondary (law firm) | — | https://www.linklaters.com/insights/blogs/arbitrationlinks/2023/may/nigeria-revises-its-arbitration-act | Forum options |
| KJV Crown letters patent (UK only) | Secondary (ebible.org) | — | https://ebible.org/kjv/copr.htm | Terms s.9.3 |

**Verification gaps.** I could not retrieve EUR-Lex directly, so the GDPR wording comes from the
gdpr-info.eu mirror. The NDPA text came from a DataGuidance mirror, not the official gazette. I did
not read: the Child's Rights Act definition of "child", the FCCPA's substantive text, the COPPA Rule
in the Federal Register, the s.103 commencement regulations, the ePrivacy Directive, EU or UK
consumer-contract law, US automatic-renewal laws, or Django's default CSRF cookie age. The NDPC has
also published a later GAID upload (`https://ndpc.gov.ng/wp-content/uploads/2026/01/NDP-ACT-GAID-2025-MARCH-20-1.pdf`);
I did not compare it with the July 2025 version I read.

## 9. Top 10 open questions and risks

1. **Entity, contacts and domains.** No legal entity is named anywhere. Contact addresses span three
   domains (`selahcue.app` on the site, `selahcue.com` as the API sender, `firstpavitech.com` as the
   API default). *Owner:* supply the entity details and choose one domain and mailbox set.
2. **The live site misleads users today.** The stub pages state as fact a Stripe integration,
   bundled BSB, licensed NIV/ESV/NLT, recurring billing with portal cancellation and GPU
   acceleration. The contact form discards messages while promising a reply within 24 hours, and the
   pricing and download pages advertise plans, payment methods and versions that do not exist. These
   are misrepresentation risks (FCCPA s.125, "false, misleading or deceptive representations", by
   heading). *Owner:* replace the stubs and fix or remove the contact form and pricing claims before
   anything else.
3. **Religious affiliation as sensitive data.** Account data may reveal religious belief (NDPA s.65;
   GDPR Art. 9; C-184/20 by analogy). *Counsel:* decide whether explicit consent at sign-up is needed
   and complete `{{SENSITIVE_DATA_CONDITION}}`.
4. **Cross-border transfers.** GAID Art. 18(1)(e), read literally, requires consent before any
   transfer to a country without an NDPC adequacy decision. Hosting and email providers are not yet
   chosen. *Owner + counsel:* choose providers with transfers in mind and settle the legal basis.
5. **NDPC registration.** SelahCue probably qualifies as a data controller of major importance (over
   200 data subjects in six months, or commercial ICT services on customers' devices), which brings
   registration, a DPO, annual audits and CAR filings. *Counsel:* confirm the tier and timing.
6. **Cloud features.** When cloud transcription or AI notes launch, they will process sermon audio
   and transcripts (sensitive data, possibly children's voices). A filed DPIA (GAID Art. 28(3)),
   provider DPAs, a controller/processor DPA with churches, transfer safeguards, model-training terms
   and a COPPA assessment are all required first. The architecture (direct-to-provider under ADR-0028,
   draft PR #111) is still open. *Owner:* do not release a cloud feature before this work is done.
7. **No deletion, export or retention schedule.** Users cannot delete or export their accounts, no
   retention periods are set, audit rows have no limit and unverified sign-ups are never purged.
   Account models use `on_delete=PROTECT`, so deletion needs engineering. *Owner:* set a retention
   schedule (GAID Art. 49(3) and 21(2) suggest six-month defaults) and build a request workflow.
8. **Acceptance is not recorded.** The sign-up checkbox is checked only in the browser, and the API
   stores no accepted-terms version or timestamp. This weakens enforceability and the evidence that
   users saw the Privacy Policy, and Terms s.23.2 (re-acceptance of material changes) needs it.
   *Engineering:* store the version, timestamp and actor at sign-up and on re-acceptance.
9. **Commercial model unsettled.** Tier names and allowance periods conflict across DEC-008, the
   2026-09-27 owner decision and the pricing page; the payment provider (D2), refund policy, renewal
   terms and tax treatment are open. *Owner:* keep Part C unpublished until these are decided.
10. **Risk-allocation decisions.** The liability cap and floor (Terms 17.3), the customer indemnity
    (s.19), governing law and forum (s.22), the EU/UK representatives, whether to show a GAID-style
    cookie notice, and self-hosting the font all need decisions. *Owner + counsel.*

**Specialist advice recommended:** a Nigerian data protection practitioner (NDPA/GAID registration,
transfers, sensitive data); EU and UK privacy counsel if the owner intends to serve those markets;
US counsel before launching paid subscriptions or cloud features in the US.

## 10. Implementation actions before publication

A policy does not implement anything on its own. These product and operations changes are needed
for the drafts to be accurate when published:

1. Replace the current Privacy and Terms stub pages (see risk 2).
2. Fix the contact form or remove it; remove unverified claims from the contact, pricing and download
   pages.
3. Name the legal entity in the site footer and in both documents.
4. Self-host the Inter font, or keep the Google Fonts disclosures.
5. Record terms and privacy acceptance (version, timestamp, user) at sign-up, and support
   re-acceptance.
6. Build account deletion and data export (self-service or a documented staff workflow), and
   respond to requests within one month.
7. Adopt a retention schedule and automate purging of unverified sign-ups, closed accounts, audit
   rows and logs.
8. Sign DPAs with hosting and email providers; record each transfer basis (NDPA s.41(2)).
9. Complete the LIA (GAID Schedule 8) and keep a record of processing activities.
10. Assess NDPC registration; appoint a DPO if required.
11. Before any cloud feature: DPIA (filed with the NDPC), provider DPAs, a church-facing DPA, the
    consent UI disclosures already specified in PRD FR-132/177, and a model-training review.
12. Confirm the `[CONFIRM]` items: the transcript delete control and retention setting in the
    operator console, that no audio is retained, `csrftoken` lifetime and HTTPS on the deployed
    site, and device deactivation in the portal.
13. Ship the FR-158 congregation-recording notice in the desktop app, because the policy (s.2.3)
    and Terms (s.9.4) rely on churches giving notice.
14. Publish open-source licence notices (`{{THIRD_PARTY_NOTICES_LOCATION}}`) and the NDI attribution.
15. Set up a complaints-handling process (UK DUAA s.103; GAID Art. 7(w) and Art. 40).

## 11. Reconciliation with the existing mobile documents

- `docs/legal/PRIVACY.md` (Controller app) states the app collects and transmits no personal data to
  SelahCue and talks only to the paired desktop. The platform policy is consistent: it points to that
  policy (s.1.3) and repeats the local-network facts (s.2.5).
- `docs/legal/TERMS.md` (Controller app) grants a personal licence and leaves governing law as
  `{{JURISDICTION}}`. Platform Terms s.1.2 makes the Controller terms prevail for the app.
- **Placeholder names differ** between the two document sets: the mobile documents use `{{ADDRESS}}`,
  `{{DATE}}` and `{{JURISDICTION}}`, where the platform drafts use `{{REGISTERED_ADDRESS}}`,
  `{{EFFECTIVE_DATE}}` and `{{GOVERNING_LAW}}`. Fill them with the same values, and consider merging
  the mobile terms into the platform Terms once both are final.
- `PRIVACY.md` §6 leaves the children's posture open; align it with `{{MINIMUM_ACCOUNT_AGE}}`.

## 12. Pending ClickUp audit entry

The ClickUp MCP was at its daily limit and the coordinator directed no ClickUp writes this session.
Nothing was logged. Record this entry once access returns; check the Legal Audit Log list
(`1400430000002076`) for an existing SelahCue privacy/terms matter task first, and set its status to
`awaiting facts / decisions`.

```
[AUDIT] SelahCue — Platform Privacy Policy + Terms of Service — created — 2026-10-01
Entity: {{LEGAL_ENTITY_NAME}} (unconfirmed; owner described as First Pavilion, Lagos)   Jurisdiction(s): Nigeria (NDPA 2023, GAID 2025) primary; EU GDPR, UK GDPR/DUAA 2025, US (CCPA/COPPA) flagged   Requested by: repo owner via coordinating agent (delivery ticket 17tnw2b0q93)
Version/status: v0.1 — Draft — facts to confirm
Facts: confirmed from code — local-only desktop data; transcript DB encrypted by default; on-device STT with model download from huggingface.co; release builds exclude cloud STT/AI and do not activate; account fields (email, password hash, org name, country, time zone, optional name); cookies selahcue_account_session + csrftoken + localStorage hint; Google Fonts; no analytics; billing not built; no account deletion/export; acceptance not recorded. Assumed — Nigerian entity in Lagos; Windows installer is the released build. Open placeholders — 52 (entity, contacts, providers, retention periods, transfers, liability cap, governing law, forum, etc.; see LEGAL-DRAFT-NOTES.md §3)
Law checked: NDPA 2023 ss.2, 25-31, 34-46, 65 (DataGuidance mirror); GAID 2025 Arts 3, 7-10, 18, 19, 21, 26-28, 41, 45, 49, Sch.7 (ndpc.gov.ng); GDPR Arts 3, 8, 9, 12, 13, 27 (gdpr-info.eu mirror; EUR-Lex not retrievable); CJEU C-184/20; LG München I 3 O 17493/20; DUAA 2025 (legislation.gov.uk, gov.uk); CCPA threshold (cppa.ca.gov); COPPA amendments (secondary); FCCPA 2018 headings; AMA 2023 (secondary) — all 2026-10-01. Gaps listed in notes §8.
Risks/decisions: live stub pages and contact form currently misleading; religious-affiliation sensitive-data basis; GAID Art 18(1)(e) transfer consent; NDPC DCMI registration; cloud-feature DPIA/DPAs; no retention/deletion; acceptance not recorded; commercial model unsettled; liability cap/indemnity/governing law. Specialist review: Nigerian data protection counsel; EU/UK privacy counsel if serving those markets.
Boundary: drafted and saved locally only; not committed, published, signed, filed or sent.
Draft: docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md; docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md; docs/legal/LEGAL-DRAFT-NOTES.md (worktree .claude/worktrees/legal-drafts, branch docs/17tnw2b0q93-legal-privacy-terms-drafts)
```
