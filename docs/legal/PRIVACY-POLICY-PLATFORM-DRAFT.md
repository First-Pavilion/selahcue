# SelahCue Privacy Policy

> **DRAFT — NOT LEGAL ADVICE — REQUIRES REVIEW BY A QUALIFIED LAWYER BEFORE PUBLICATION**
>
> Version 0.1 (draft, 2026-10-01). Status: Draft — facts to confirm. Do not publish while any
> `{{PLACEHOLDER}}` or `[CONDITIONAL]` block remains. Assumptions, sources and open questions are in
> `docs/legal/LEGAL-DRAFT-NOTES.md`. This policy covers the SelahCue website, SelahCue accounts and
> platform services, and the SelahCue desktop app. The SelahCue Controller mobile app also has its
> own policy (`docs/legal/PRIVACY.md`), which this policy does not replace.

- **Who we are:** `{{LEGAL_ENTITY_NAME}}`, trading as SelahCue ("SelahCue", "we", "us")
- **Registered address:** `{{REGISTERED_ADDRESS}}`
- **Registration number:** `{{COMPANY_REGISTRATION_NUMBER}}`
- **Privacy contact:** `{{PRIVACY_CONTACT_EMAIL}}`
- **Data Protection Officer:** `{{DPO_NAME_AND_CONTACT}}`
- **Effective date:** `{{EFFECTIVE_DATE}}`

---

## Summary in plain language

This summary is part of the policy. The full sections below give the detail.

- **Your church's content stays on your church's computers.** Slides, songs, scripture, media,
  service plans, sermon transcripts and sermon notes are stored on the computers where you run
  SelahCue. We do not receive them, and we cannot see them.
- **Live transcription runs on your computer.** In the current desktop app, speech is turned into
  text on the computer itself. Audio is not sent to us. The first time you use it, the app
  downloads a speech-recognition model file from Hugging Face, a third-party website.
- **The mobile controller talks only to your desktop**, over your own local network.
- **If you create a SelahCue account**, we collect your email address, a password (which we store
  only in scrambled, one-way form), your church or organisation name, your country and time zone,
  and, if you give it, your name. We use these to run your account and send you account emails.
- **Our website uses only the cookies it needs** to keep you signed in and to protect our forms.
  We do not use advertising or analytics cookies. Our website currently loads a font from Google,
  so Google receives your IP address when you visit.
- **We do not sell your personal data, and we do not show ads.**
- **Optional cloud features are not available yet.** If we add cloud transcription or AI sermon
  notes, they will be off until an administrator turns them on, and we will update this policy
  first.
- **You have rights** to see, correct, delete and move your data, and to complain to a regulator.
  Email `{{PRIVACY_CONTACT_EMAIL}}` to use them.

---

## 1. Who this policy covers

1.1 This policy explains how `{{LEGAL_ENTITY_NAME}}` handles personal data when you:

- visit our website at `{{WEBSITE_URL}}`;
- create or use a SelahCue account, including signing in, verifying your email and resetting your
  password;
- use SelahCue platform services, such as licences and device activation, when they are available;
- install and use the SelahCue desktop app; or
- contact us for help.

1.2 For the personal data described in section 3, we are the **data controller**. This means we
decide why and how that data is used.

1.3 This policy does **not** cover:

- content your church creates and keeps on its own computers with SelahCue (see section 2);
- the SelahCue Controller mobile app, which has its own privacy policy at
  `{{CONTROLLER_PRIVACY_POLICY_URL}}`; or
- other organisations' websites or services, even if we link to them.

## 2. Data that stays with your church

2.1 SelahCue is built to work offline. The desktop app stores your church's working data on the
computer where it runs. This includes:

- service plans, slides, slide decks, songs, themes and screen settings;
- references to your media files (the files stay where you keep them);
- scripture you search for and display;
- transcripts made by live transcription, including corrections and detected scripture
  references; and
- sermon-note drafts.

2.2 We do not receive this data and we do not have access to it. Your church decides what is
created, how long it is kept and who can use the computer. For this data, **your church is the
data controller**, not us.

2.3 **Transcripts can contain personal data about other people.** Live transcription captures
whatever the selected microphone hears. That can include the words of preachers, worship leaders,
congregation members and children. Sermon content may reveal religious beliefs, which is sensitive
data in many countries. Before you use live transcription, your church should:

- tell people that services may be transcribed;
- decide how long transcripts are kept; and
- limit who can access the computers that hold them.

2.4 **How the desktop app protects this data.**

- The database that holds transcripts is encrypted on disk by default. The encryption key is kept
  in your operating system's secure credential store, or is derived from a passphrase on systems
  that do not have one.
- Some other local files are **not** encrypted by the app, including the slide-deck library and
  your media files. Protect access to the computer itself.
- Transcripts stay on the computer until they are deleted.
  `[CONFIRM BEFORE PUBLISHING: the delete control and the automatic-deletion setting are available
  in the operator console]` Deleting a transcript also deletes its corrections and detected
  scripture references, and, by default, the sermon-note draft made from it.
- The current desktop app does not keep audio recordings. It converts speech to text and keeps the
  text. `[CONFIRM BEFORE PUBLISHING]`

2.5 **Local network features.** When you use them, these features send data across your church's
local network, but not to us:

- **Mobile controller.** A paired phone or tablet receives the current and next slide, timers and,
  where enabled, a live transcript preview. The connection is encrypted and tied to the specific
  desktop the device was paired with.
- **Discovery.** The desktop app announces itself on the local network so paired devices can find
  it.
- **NDI output.** If you turn on NDI output, the app broadcasts your presentation video on the local
  network for other NDI equipment to receive.

2.6 **If you share church data with us.** If you send us a transcript, screenshot or file, for
example to get help, we handle it as described in section 3.6.

## 3. Personal data we collect and why

### 3.1 Your SelahCue account

You do not need an account to use SelahCue's core presentation features. You need one to manage
your church's plan, licence and devices.

| What we collect | Where it comes from | Why we use it | Lawful basis |
|---|---|---|---|
| Email address | You, at sign-up | To create your account, sign you in and send account emails | Contract |
| Password | You, at sign-up or reset | To sign you in. We store only a salted one-way hash, never the password itself | Contract |
| Church or organisation name | You, at sign-up | To set up your organisation's account | Contract |
| Country | You, at sign-up (the form suggests one from your browser settings) | To set up your account and apply the right terms and taxes | Contract |
| Time zone | Your browser, automatically at sign-up | To show dates and times correctly and to time account events | Contract |
| Your name (optional) | You, at sign-up | To address you and show who manages the account | Contract |
| Account role (administrator or member) and status | Created by our system | To control who can manage licences and devices | Contract |
| Email-verification status and time | Created by our system | To confirm you control the email address | Contract |
| Sign-in sessions (a masked identifier, issue, expiry and last-used times) | Created by our system | To keep you signed in and let you sign out everywhere | Contract |
| Failed sign-in count and temporary lock time | Created by our system | To protect your account from password guessing | Legitimate interests (security) |
| Notes our staff record about your account, and licence and plan details | Our staff | To support you and manage your licence | Contract; legitimate interests (running our business) |

Because SelahCue is made for churches, holding an account may suggest a religious affiliation. We
use account details only to provide the service. We do not use them to profile anyone's beliefs.
`{{SENSITIVE_DATA_CONDITION}}`

### 3.2 Emails we send you

We send you these emails because they are needed to run your account:

- an email-verification link, which expires after 24 hours;
- a password-reset link, which expires after 1 hour; and
- a notice if someone tries to create an account with your email address. We send this instead of
  telling the person signing up that the address is already registered.

We send these emails through `{{EMAIL_DELIVERY_PROVIDER}}`.

We do not currently send marketing emails. If we start, we will ask for your consent first, and you
can withdraw it at any time.

> **[CONDITIONAL — LICENCE NOTIFICATIONS]** Publish this paragraph only once licence-lifecycle
> emails are built. We also send service emails about your licence, such as renewal reminders and
> notices that a licence has expired or been suspended.

### 3.3 Licences and device activation

> **[CONDITIONAL — DEVICE ACTIVATION]** Publish this section only once the released desktop app can
> activate devices. Until then, replace it with: "The current desktop app does not contact our
> servers to activate or check a licence."

When you activate the desktop app on a computer, the app sends us:

- a device identifier generated by the app (`{{DEVICE_FINGERPRINT_METHOD}}`);
- the platform (for example, Windows or macOS);
- the app version; and
- a device name, if you choose one (for example, "Sound booth PC").

We record which licence the device uses, when it was activated and its status. We send back a
device credential, which the app keeps in your operating system's secure credential store, and a
signed licence file, which the app keeps so it can run offline until the licence period ends.

We use this information to apply your plan's device limit, to let your administrator see and
remove devices, and to prevent misuse of licence keys. Our lawful bases are contract and, for fraud
prevention, legitimate interests.

Activation and licence checks do not send us your slides, transcripts, audio or network logs.

If your organisation uses a licence key to activate, we store the key only in hashed form, plus a
short masked version so you and our staff can recognise it.

### 3.4 Plans and payments

> **[CONDITIONAL — BILLING]** We do not take payments yet. Publish this section only when billing
> is live, and complete it with the provider's details. Until then, replace it with: "We do not
> currently collect payment information."

Payments are processed by `{{PAYMENT_PROVIDER}}`. We do not receive or store your full card
number. We receive `{{PAYMENT_DATA_RECEIVED}}`. We use it to manage your subscription, keep tax
and accounting records, and handle refunds. Our lawful bases are contract and legal obligation.

### 3.5 Website visits, security and server records

When you use our website or our account services, our servers and our hosting provider
`{{HOSTING_PROVIDER}}` process technical information, including your IP address, browser type, and
the pages and requests you make. We use it to deliver the website, keep it secure, and fix
problems.

- **Rate limiting.** To stop abuse, such as repeated password-reset requests, we count requests
  from each network address for a short time. For IPv6 addresses we keep only the network part.
  These counters expire within one hour.
- **Server logs.** We keep server logs for `{{SERVER_LOG_RETENTION}}`.
- **Security and audit records.** We record important account and licence actions, such as sign-up,
  device activation and licence changes. Each record says who acted (by internal identifier), what
  changed, the result and when. Passwords, keys and tokens are never included. We keep these
  records for `{{AUDIT_RECORD_RETENTION}}`.

Our lawful basis is legitimate interests: keeping our services secure and working.

### 3.6 Support and contact

If you email us at `{{SUPPORT_CONTACT_EMAIL}}` or `{{PRIVACY_CONTACT_EMAIL}}`, we use your name,
contact details and message, and anything you attach, to reply and to improve our help. Please do
not send us transcripts or other church content unless we need it to solve your problem. Our lawful
basis is legitimate interests, or contract where the request is about your account.

### 3.7 The desktop app

Apart from device activation (section 3.3), where that is available, the current desktop app:

- does **not** send us your content, transcripts or audio;
- does **not** include advertising, analytics, telemetry or crash-reporting tools; and
- uses your microphone or audio input only when an operator starts live transcription.

The desktop app connects to the internet only when you ask it to download a file:

- **Speech-recognition model.** The first time you use live transcription, the app downloads a
  model file from Hugging Face (`huggingface.co`). Your computer's IP address and a standard web
  request go to Hugging Face, as with any download. The app checks the file has not been altered
  before using it. Hugging Face handles that request under its own privacy policy.
- **Additional Bible translations.** Where the app offers a downloadable translation, it downloads
  it from `{{TRANSLATION_DOWNLOAD_HOST}}`. The translations built into the app need no download.

### 3.8 Optional cloud features

The released versions of SelahCue do not include cloud transcription or cloud AI sermon notes.

> **[CONDITIONAL — CLOUD FEATURES]** Publish this section only when a cloud feature is released,
> after the provider contracts, transfer safeguards and impact assessment described in the notes
> file are in place. Complete every placeholder.
>
> SelahCue may offer these optional cloud features:
>
> - **Cloud transcription.** While it is switched on and listening, the desktop app streams live
>   audio from the selected microphone to `{{STT_PROVIDER}}`, which returns text.
> - **AI sermon notes.** When an operator presses Generate, the app sends the completed transcript
>   text (never audio) to `{{NOTES_PROVIDER}}` `{{NOTES_ROUTE}}`, which returns a draft.
>
> These features are off by default. Only an administrator can turn them on, separately for each
> feature, after seeing what data is sent, to whom, and where. While cloud transcription is
> active, the app shows an indicator.
>
> For these features, your church remains the controller of the audio and transcripts. We and our
> providers process them only to provide the feature, under the data processing terms in
> `{{DPA_REFERENCE}}`. Providers keep this data for `{{PROVIDER_RETENTION}}`.
> `{{MODEL_TRAINING_STATEMENT}}`
>
> To apply your plan's usage allowance, we record how much of each feature your organisation uses
> (for example, minutes of transcription and number of note drafts) and when requests were allowed
> or refused. These usage records do not contain sermon content.

### 3.9 What we do not do

- We do not sell personal data.
- We do not share personal data for targeted or cross-context behavioural advertising.
- We do not make decisions about you based solely on automated processing that have legal or
  similarly significant effects.

## 4. Cookies and similar technologies

4.1 Our website uses only these technologies:

| Name | Type | Purpose | How long |
|---|---|---|---|
| `selahcue_account_session` | Cookie (secure, not readable by page scripts, sent only to our own site) | Keeps you signed in | Until you sign out, or up to 30 days |
| `csrftoken` | Cookie | Protects our forms against cross-site request forgery | Up to 1 year `[CONFIRM ON DEPLOYED SITE]` |
| `selahcue.session` | Browser local storage | Remembers your account role, organisation reference and session expiry, so the page can show that you are signed in. It contains no password or session credential | Removed when you sign out, or ignored once the session has expired |

4.2 These are strictly necessary for signing in and security, so we do not ask for consent to use
them. You can block them in your browser settings, but you will not be able to sign in.

4.3 **Google Fonts.** `[CONDITIONAL — remove this paragraph if the font is self-hosted before
publication]` Our website loads the Inter font from Google's servers (`fonts.googleapis.com` and
`fonts.gstatic.com`). When it does, your browser sends your IP address and standard browser
information to Google. Google handles that data under its own privacy policy.

4.4 We do not use analytics, advertising or social-media tracking cookies or pixels. If we add any,
we will ask for your consent first and update this policy.

## 5. Lawful bases

5.1 We rely on these lawful bases under the Nigeria Data Protection Act 2023 (NDPA) section 25 and,
where it applies, Article 6 of the EU and UK General Data Protection Regulation (GDPR):

- **Contract:** to provide your account and the services you ask for.
- **Legal obligation:** to keep records the law requires, such as tax and accounting records once
  billing exists, and to respond to lawful requests.
- **Legitimate interests:** to keep our services secure, prevent fraud and abuse, and run and
  improve our business, where those interests are not overridden by your rights. We have assessed
  these interests. `{{LIA_REFERENCE}}`
- **Consent:** where we ask for it, such as for marketing emails. You can withdraw consent at any
  time. Withdrawing does not affect processing that happened before.

5.2 If you do not give us the information marked as needed at sign-up, we cannot create your
account.

## 6. Who we share personal data with

6.1 We share personal data only with:

- **Service providers** that work for us under contract and only on our instructions:
  - hosting: `{{HOSTING_PROVIDER}}`
  - email delivery: `{{EMAIL_DELIVERY_PROVIDER}}`
  - `[CONDITIONAL — BILLING]` payments: `{{PAYMENT_PROVIDER}}`
  - `[CONDITIONAL — CLOUD FEATURES]` cloud transcription and AI notes: `{{STT_PROVIDER}}`,
    `{{NOTES_PROVIDER}}`
- **Google**, when our website loads the Inter font (section 4.3).
- **Professional advisers**, such as lawyers and accountants, under a duty of confidentiality.
- **Authorities**, when the law requires it or to protect people's safety or our legal rights.
- **A buyer or successor**, if our business or its assets are sold or reorganised. We would tell
  you before your data became subject to a different privacy policy.

6.2 `[CONDITIONAL — CUSTOMER PORTAL]` Your organisation's administrators can see the account
information of members of the same organisation, and the organisation's licence and Devices.

## 7. International transfers

7.1 We are based in `{{COUNTRY_OF_ESTABLISHMENT}}`. Our servers are in `{{HOSTING_REGION}}`. Some of
our service providers are in other countries, which may include the United States.

7.2 If you are outside the country where we or our providers are based, your personal data will be
transferred there. When we transfer personal data:

- out of Nigeria, we do so only on a basis allowed by NDPA sections 41 to 43 and the Nigeria Data
  Protection Commission's directives; and
- out of the European Economic Area or the United Kingdom, we use a recognised safeguard, such as
  an adequacy decision or standard contractual clauses.

The safeguards we use are: `{{TRANSFER_MECHANISMS}}`. You can ask us for a copy.

## 8. How long we keep personal data

| Data | How long |
|---|---|
| Account details | While your account is open, then `{{ACCOUNT_RETENTION_AFTER_CLOSURE}}` |
| Accounts that are never verified | `{{UNVERIFIED_SIGNUP_RETENTION}}` |
| Sign-in sessions | Until you sign out or they expire (up to 30 days); expired records are deleted by a nightly job |
| Email-verification and password-reset links | Until used or expired (24 hours and 1 hour); expired records are deleted by a nightly job |
| Rate-limiting counters | Up to 1 hour |
| Server logs | `{{SERVER_LOG_RETENTION}}` |
| Security and audit records | `{{AUDIT_RECORD_RETENTION}}` |
| `[CONDITIONAL — DEVICE ACTIVATION]` Licence and device records | While your organisation's account is active, then `{{LICENCE_RECORD_RETENTION}}` |
| `[CONDITIONAL — BILLING]` Payment and tax records | `{{FINANCIAL_RECORD_RETENTION}}` |
| Support emails | `{{SUPPORT_RETENTION}}` |

When we no longer need personal data, we delete it or make it anonymous. We may keep some data for
longer if the law requires it or if we need it to establish, exercise or defend legal claims.

## 9. How we protect personal data

9.1 We use technical and organisational measures suited to the risk. They include:

- storing passwords only as salted one-way hashes;
- storing session, email-link and device credentials only in hashed form;
- signing everyone out of all sessions when a password changes;
- temporarily locking sign-in after repeated failed attempts;
- limiting the rate of sensitive requests;
- serving our website and services over encrypted connections `[CONFIRM ON DEPLOYMENT]`; and
- in the desktop app, encrypting the transcript database on disk, keeping credentials in the
  operating system's secure store, and encrypting the local-network link to paired mobile devices.

9.2 No system is perfectly secure. If a breach affects your personal data and is likely to put your
rights at risk, we will notify the regulator as the law requires, which in Nigeria is within 72
hours of becoming aware of it. If the risk to you is high, we will also tell you without delay.

## 10. Children

10.1 SelahCue is a tool for church production teams. Our website and accounts are not meant for
children. You must be at least `{{MINIMUM_ACCOUNT_AGE}}` to create an account.

10.2 We do not knowingly collect personal data from children. If you believe a child has given us
personal data, contact us and we will delete it.

10.3 Churches using live transcription should take particular care where children may be heard, for
example in family services or children's ministry (see section 2.3).

## 11. Your rights

11.1 Depending on where you live, you have the right to:

- find out whether we hold personal data about you, and get a copy;
- have inaccurate data corrected;
- have your data deleted;
- restrict how we use your data while a concern is resolved;
- object to processing based on our legitimate interests, and to any direct marketing;
- receive your data in a structured, commonly used, machine-readable format and have it sent to
  another organisation;
- withdraw consent at any time, where we rely on consent; and
- not be subject to decisions based solely on automated processing that significantly affect you.

11.2 **How to use your rights.** Email `{{PRIVACY_CONTACT_EMAIL}}`. We may ask you to confirm your
identity. We will reply without undue delay and within one month at the latest. If a request is
complex, we may extend this by up to two more months where the law allows, and we will tell you why.
We do not charge for requests unless the law allows us to and a request is clearly unfounded or
excessive.

11.3 You cannot yet delete your account or download your data from the website yourself. Email us
and we will do it for you.

11.4 **Data your church holds.** We cannot access transcripts or other content stored on your
church's computers. To ask about that data, contact the church.

11.5 **Complaints.** Please contact us first so we can try to help. You also have the right to
complain to a data protection authority:

- in Nigeria, the Nigeria Data Protection Commission (`ndpc.gov.ng`);
- in the European Economic Area, the authority in your country;
- in the United Kingdom, the Information Commissioner's Office (`ico.org.uk`); or
- elsewhere, the authority where you live.

11.6 **Representatives.** `[CONDITIONAL — complete if counsel confirms one is required]` Our
representative in the European Union is `{{EU_REPRESENTATIVE}}`. Our representative in the United
Kingdom is `{{UK_REPRESENTATIVE}}`.

## 12. Changes to this policy

12.1 We will update this policy when our services or the law change. We will post the new version
at `{{PRIVACY_POLICY_URL}}` and change the effective date.

12.2 If a change materially affects how we use your personal data, we will tell account holders by
email or in the product before it takes effect. Where the law requires your consent to a change, we
will ask for it.

## 13. Contact us

- **Email:** `{{PRIVACY_CONTACT_EMAIL}}`
- **Post:** `{{LEGAL_ENTITY_NAME}}`, `{{REGISTERED_ADDRESS}}`
- **Data Protection Officer:** `{{DPO_NAME_AND_CONTACT}}`
