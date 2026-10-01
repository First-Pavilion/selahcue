# SelahCue Privacy Policy

> **DRAFT — NOT LEGAL ADVICE — REQUIRES REVIEW BY A QUALIFIED LAWYER BEFORE PUBLICATION**
>
> Version 0.3 (draft, 2026-10-01). Status: Draft — every `{{PLACEHOLDER}}` must be filled and every
> launch-readiness condition in `docs/legal/LEGAL-DRAFT-NOTES.md` §4 must be satisfied before
> publication. This policy describes SelahCue as it operates at launch. Publishing it while any
> launch-readiness condition is unmet would make it inaccurate. The SelahCue Controller mobile app
> also has its own policy (`docs/legal/PRIVACY.md`), which this policy does not replace.

- **Who we are:** `{{LEGAL_ENTITY_NAME}}`, trading as SelahCue ("SelahCue", "we", "us")
- **Registered address:** `{{REGISTERED_ADDRESS}}`
- **Registration number:** `{{COMPANY_REGISTRATION_NUMBER}}`
- **Privacy contact:** `{{PRIVACY_CONTACT_EMAIL}}`
- **Effective date:** `{{EFFECTIVE_DATE}}`

---

## Summary in plain language

This summary is part of the policy. The full sections below give the detail.

- **Your church's content stays on your church's computers.** Slides, songs, scripture, media,
  service plans, sermon transcripts and sermon notes are stored on the computers where you run
  SelahCue. We do not receive them unless you use a cloud feature or send them to us.
- **Live transcription runs on your computer by default.** Audio is not sent anywhere. The first time
  you use it, the app downloads a speech-recognition model file from Hugging Face, a third-party
  website.
- **Cloud features are optional and off by default.** Only an administrator can turn them on. Cloud
  transcription sends live audio to Deepgram. AI sermon notes send the finished transcript text to
  OpenAI. That data leaves your church's network and can be processed in another country.
- **The mobile controller talks only to your desktop**, over your own local network.
- **Your SelahCue account** holds your email address, a password (stored only in scrambled, one-way
  form), your church or organisation name, your country and time zone, and, if you give it, your name.
- **Licences, devices and downloads.** When you activate SelahCue on a computer, we record a device
  identifier, its platform, app version and the name you give it. We also record what you download.
- **Payments** go through Paystack's checkout. Paystack collects your card or bank details. Your full
  card number never reaches us.
- **Our website uses only the cookies it needs** to keep you signed in and to protect our forms, plus
  Paystack's own cookies on its checkout. We do not use advertising or analytics cookies. Our website
  loads a font from Google, so Google receives your IP address when you visit.
- **We do not sell your personal data, and we do not show ads.**
- **You have choices.** You can delete your account yourself in your account settings. To get a copy
  of your data, or for any other request, email `{{PRIVACY_CONTACT_EMAIL}}`.

---

## 1. Who this policy covers

1.1 This policy explains how `{{LEGAL_ENTITY_NAME}}` handles personal data when you:

- visit our website at `{{WEBSITE_URL}}`;
- create or use a SelahCue account, including signing in, verifying your email and resetting your
  password;
- buy or manage a SelahCue plan;
- activate SelahCue on a computer, or download SelahCue, updates or Bible translations;
- use SelahCue's optional cloud features;
- install and use the SelahCue desktop app; or
- contact us for help.

1.2 We decide why and how the personal data described in section 3 is used. The exception is audio and
transcripts sent to our optional cloud features: we handle those only to provide the feature to your
church (see section 3.8).

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
- transcripts made by live transcription, including corrections and detected scripture references;
  and
- sermon-note drafts.

2.2 We do not have access to this data. Your church decides what is created, how long it is kept and
who can use the computer, and is responsible for it.

2.3 **Transcripts can contain personal data about other people.** Live transcription captures whatever
the selected microphone hears. That can include the words of preachers, worship leaders, congregation
members and children. Sermon content may reveal people's religious beliefs. Before you use live
transcription, your church should:

- tell people that services may be transcribed (the desktop app includes a notice you can display for
  this);
- decide how long transcripts are kept; and
- limit who can access the computers that hold them.

2.4 **How the desktop app protects and manages this data.**

- The database that holds transcripts is encrypted on disk by default. The encryption key is kept in
  your operating system's secure credential store, or is derived from a passphrase on systems that do
  not have one.
- Some other local files are **not** encrypted by the app, including the slide-deck library and your
  media files. Protect access to the computer itself.
- Transcripts stay on the computer until they are deleted. An operator can delete a transcript in the
  operator console, and an administrator can set the app to delete transcripts automatically after a
  chosen number of days. Deleting a transcript also deletes its corrections and detected scripture
  references, and, by default, the sermon-note draft made from it.
- The desktop app does not keep audio recordings. It converts speech to text and keeps the text.

2.5 **Local network features.** These features send data across your church's local network, but not to
us:

- **Mobile controller.** A paired phone or tablet receives the current and next slide, timers and,
  where enabled, a live transcript preview. The connection is encrypted and tied to the specific
  desktop the device was paired with.
- **Discovery.** The desktop app announces itself on the local network so paired devices can find it.
- **NDI output.** If you turn on NDI output, the app broadcasts your presentation video on the local
  network for other NDI equipment to receive.

2.6 **If you share church data with us.** If you send us a transcript, screenshot or file, for example to
get help, we handle it as described in section 3.6. Cloud features are described in section 3.8.

## 3. Personal data we collect and why

### 3.1 Your SelahCue account

You do not need an account to use SelahCue's core presentation features. You need one to buy and manage
a plan, activate SelahCue on your computers, manage your devices, and use cloud features.

| What we collect | Where it comes from | Why we use it | Our reason |
|---|---|---|---|
| Email address | You, at sign-up | To create your account, sign you in and send account emails | To provide the service |
| Password | You, at sign-up or reset | To sign you in. We store only a salted one-way hash, never the password itself | To provide the service |
| Church or organisation name | You, at sign-up | To set up your organisation's account | To provide the service |
| Country | You, at sign-up (the form suggests one from your browser settings) | To set up your account and apply the right terms and taxes | To provide the service |
| Time zone | Your browser, automatically at sign-up | To show dates and times correctly and to time account events and allowance periods | To provide the service |
| Your name (optional) | You, at sign-up | To address you and show who manages the account | To provide the service |
| Billing contact email (optional) | You | To send invoices and billing notices | To provide the service |
| Account role (administrator or member) and status | Created by our system | To control who can manage plans, licences and devices | To provide the service |
| Email-verification status and time | Created by our system | To confirm you control the email address | To provide the service |
| Record of your acceptance of our Terms and this policy (version and time) | Created by our system when you accept | To show which terms apply to you and when you agreed | To provide the service; to meet legal requirements |
| Sign-in sessions (a masked identifier, issue, expiry and last-used times) | Created by our system | To keep you signed in and let you sign out everywhere | To provide the service |
| Failed sign-in count and temporary lock time | Created by our system | To protect your account from password guessing | To keep our services secure |
| Notes our staff record about your account, and your plan and licence details | Our staff and our system | To support you and manage your plan and licence | To provide the service; to run our business |

Because SelahCue is made for churches, holding an account may suggest a religious affiliation. We use
account details only to provide the service. We do not use them to profile anyone's beliefs.

### 3.2 Emails we send you

We send you these emails because they are needed to run your account and your plan:

- an email-verification link, which expires after 24 hours;
- a password-reset link, which expires after 1 hour;
- a notice if someone tries to create an account with your email address. We send this instead of
  telling the person signing up that the address is already registered;
- notices about your licence and plan, such as renewal reminders, and notices that a licence has
  expired or been suspended; and
- receipts, invoices and payment notices.

We send these emails through `{{EMAIL_DELIVERY_PROVIDER}}`.

We send marketing emails only to people who have agreed to receive them, and you can withdraw that
consent at any time using the link in each email or by contacting us.

### 3.3 Licences, devices and downloads

**Activation.** When you activate the desktop app on a computer, the app sends us:

- a device identifier generated by the app (`{{DEVICE_FINGERPRINT_METHOD}}`);
- the platform (for example, Windows or macOS);
- the app version; and
- a device name, if you choose one (for example, "Sound booth PC").

We record which licence the device uses, when it was activated and its status. We send back a device
credential, which the app keeps in your operating system's secure credential store, and a signed
licence file, which the app keeps so it can run offline until the licence period ends.

**Licence check-ins.** When an activated device is online, the app contacts us from time to time, using
its device credential, to refresh its licence file. We record when each device last checked in.

**Downloads.** We keep SelahCue installers in private, encrypted storage provided by
`{{DOWNLOAD_HOSTING_PROVIDER}}` in `{{DOWNLOAD_HOSTING_REGION}}`. When you download SelahCue, an update or
an additional Bible translation through your account or an activated device, we give you a download link
that expires after a short time. We record what was downloaded, for which platform, when, and for which
account or device. The file comes directly from `{{DOWNLOAD_HOSTING_PROVIDER}}`, which receives your IP
address and standard request information when you download.

We use this information to apply your plan's device limit and usage allowances, to show your
administrators which devices are active, to let them remove devices, to deliver the software and content
your plan includes, and to prevent misuse of licences.

Activation, check-ins and downloads do not send us your slides, transcripts, audio or network logs.

If your organisation uses an enrolment key to activate, we store the key only in hashed form, plus a
short masked version so you and our staff can recognise it.

### 3.4 Plans and payments

When you buy a paid plan, you pay on a checkout page provided by Paystack, our payment processor.
Paystack collects your card or bank details directly. Your full card number never reaches our servers,
and we do not store it. Paystack sends us `{{PAYMENT_DATA_RECEIVED}}`, and Paystack handles your payment
details under its own terms and privacy policy.

We keep your plan, billing history, invoices and billing contact details. We use them to take payment,
manage your subscription, send receipts and notices, handle refunds and failed payments, and keep the
tax and accounting records the law requires.

### 3.5 Website visits, security and server records

When you use our website or our online services, our servers and our hosting provider
`{{HOSTING_PROVIDER}}` process technical information, including your IP address, browser type, and the
pages and requests you make. We use it to deliver the website, keep it secure, and fix problems.

- **Rate limiting.** To stop abuse, such as repeated password-reset requests, we count requests from
  each network address for a short time. For IPv6 addresses we keep only the network part. These
  counters expire within one hour.
- **Server logs.** We keep server logs for `{{SERVER_LOG_RETENTION}}`.
- **Security and audit records.** We record important account, licence, plan and cloud-feature actions,
  such as sign-up, device activation, licence changes, and cloud-feature requests that were allowed or
  refused. Each record says who acted (by internal identifier), what changed, the result and when.
  Passwords, keys and access credentials are never included. We keep these records for
  `{{AUDIT_RECORD_RETENTION}}`.

### 3.6 Support and contact

If you use the contact form on our website, or email us at `{{SUPPORT_CONTACT_EMAIL}}` or
`{{PRIVACY_CONTACT_EMAIL}}`, we use your name, contact details and message, and anything you attach, to
reply and to improve our help. Please do not send us transcripts or other church content unless we need
it to solve your problem.

### 3.7 The desktop app's internet connections

The desktop app does not include advertising, analytics, telemetry or crash-reporting tools. It uses
your microphone or audio input only when an operator starts live transcription.

The desktop app connects to the internet only to:

- **activate, check in and download**, as described in section 3.3;
- **use cloud features** that an administrator has turned on, as described in section 3.8;
- **download the speech-recognition model.** The first time you use live transcription, the app
  downloads a model file from Hugging Face (`huggingface.co`). Your computer's IP address and a standard
  web request go to Hugging Face, as with any download. The app checks the file has not been altered
  before using it. Hugging Face handles that request under its own privacy policy; and
- **download Bible translations** that are not built into the app, from `{{TRANSLATION_DOWNLOAD_HOST}}`.
  The translations built into the app need no download.

### 3.8 Optional cloud features

SelahCue offers two optional cloud features:

- **Cloud transcription.** While it is switched on and listening, the desktop app streams live audio from
  the selected microphone directly to Deepgram, using a short-lived access credential our servers issue.
  Deepgram returns text. We do not receive the audio.
- **AI sermon notes.** When an operator presses Generate, the app sends the completed transcript text
  (never audio) to OpenAI `{{NOTES_ROUTE}}`, which returns a draft.

These features are off by default. Only an administrator can turn them on, separately for each feature,
after the app shows what data is sent, to which provider, and that it can be processed in another
country. While cloud transcription is active, the app shows an indicator.

When you use these features, your sermon audio or transcript leaves your church's network and is
processed on Deepgram's or OpenAI's servers, which can be in a different country from yours. Deepgram
and OpenAI handle this data under their own terms and privacy policies, which say how long they keep it
and whether they use it to improve their services. We and they handle it only to provide the feature to
your church. Data sent to cloud features is kept for `{{PROVIDER_RETENTION}}`.

To apply your plan's usage allowances, we record how much of each feature your organisation uses (for
example, transcription time and number of note drafts), and each request that was allowed or refused,
with the reason. These usage records do not contain audio or sermon content.

### 3.9 Licensed Bible translations

Some plans include copyrighted Bible translations licensed from their publishers. When your plan
includes one, the app downloads it after your device is activated. Our licences with publishers require
us to report `{{PUBLISHER_REPORTING_DATA}}` to them. We do not send publishers your sermon content or
transcripts.

### 3.10 What we do not do

- We do not sell personal data.
- We do not share personal data for targeted or cross-context behavioural advertising.
- We do not make decisions about you based solely on automated processing that have legal or similarly
  significant effects. Applying plan limits and usage allowances is automatic, but it only controls
  access to features you have chosen, and you can contact us about any decision.

## 4. Cookies and similar technologies

4.1 Our website uses only these technologies:

| Name | Type | Purpose | How long |
|---|---|---|---|
| `selahcue_account_session` | Cookie (secure, not readable by page scripts, sent only to our own site) | Keeps you signed in | Until you sign out, or up to 30 days |
| `csrftoken` | Cookie | Protects our forms against cross-site request forgery | Up to 1 year |
| `selahcue.session` | Browser local storage | Remembers your account role, organisation reference and session expiry, so the page can show that you are signed in. It contains no password or session credential | Removed when you sign out, or ignored once the session has expired |
| Paystack checkout cookies and scripts | Set by Paystack on its checkout page | Process your payment securely and prevent fraud | As set by Paystack; Paystack's cookie policy applies |

4.2 Our own cookies and storage are strictly necessary for signing in and security, so we do not ask for
consent to use them. You can block them in your browser settings, but you will not be able to sign in.

4.3 **Google Fonts.** Our website loads the Inter font from Google's servers (`fonts.googleapis.com` and
`fonts.gstatic.com`). When it does, your browser sends your IP address and standard browser information
to Google. Google handles that data under its own privacy policy.

4.4 We do not use analytics, advertising or social-media tracking cookies or pixels.

## 5. Our reasons for using personal data

5.1 We use personal data only where we have a good reason that the law recognises:

- **To provide the service** you asked for, including your account, plan, licences, downloads and cloud
  features.
- **To meet legal requirements**, such as keeping tax and accounting records and responding to lawful
  requests.
- **To keep our services secure and run our business**, such as preventing fraud and abuse, where this
  does not override your rights.
- **With your consent**, where we ask for it, such as for marketing emails. You can withdraw consent at
  any time. Withdrawing does not affect anything we did before.

5.2 If you do not give us the information marked as needed at sign-up or checkout, we cannot create your
account or process your purchase.

## 6. Who we share personal data with

6.1 We share personal data only with:

- **Service providers** that run parts of our service for us:
  - hosting: `{{HOSTING_PROVIDER}}`
  - installer storage and downloads: `{{DOWNLOAD_HOSTING_PROVIDER}}`
  - email delivery: `{{EMAIL_DELIVERY_PROVIDER}}`
- **Paystack**, which processes payments for us (section 3.4).
- **Deepgram and OpenAI**, when an administrator has turned on a cloud feature (section 3.8).
- **Bible publishers**, to the extent described in section 3.9.
- **Google**, when our website loads the Inter font (section 4.3).
- **Professional advisers**, such as lawyers and accountants, under a duty of confidentiality.
- **Authorities**, when the law requires it or to protect people's safety or our legal rights.
- **A buyer or successor**, if our business or its assets are sold or reorganised. We would tell you
  before your data became subject to a different privacy policy.

6.2 Your organisation's administrators can see, in the customer portal, the account information of
members of the same organisation, and the organisation's plan, licence, devices, usage and billing
history.

## 7. Where your data is processed

7.1 We are based in `{{COUNTRY_OF_ESTABLISHMENT}}`. Our servers run with `{{HOSTING_PROVIDER}}` in
`{{HOSTING_REGION}}`, and our installers are stored with `{{DOWNLOAD_HOSTING_PROVIDER}}` in
`{{DOWNLOAD_HOSTING_REGION}}`. Paystack, Deepgram, OpenAI and our other providers process data on their
own servers.

7.2 These places can be outside your country, and the data protection rules there may differ from the
rules where you live. `{{TRANSFER_SAFEGUARDS_SUMMARY}}`

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
| Licence, device, download and usage records | While your organisation's account is open, then `{{LICENCE_RECORD_RETENTION}}` |
| Payment, invoice and tax records | `{{FINANCIAL_RECORD_RETENTION}}` |
| Support messages | `{{SUPPORT_RETENTION}}` |
| Audio and transcripts sent to cloud features | `{{PROVIDER_RETENTION}}` |

When we no longer need personal data, we delete it or make it anonymous. We may keep some data for longer
if the law requires it or if we need it to establish, exercise or defend legal claims.

## 9. How we protect personal data

9.1 We use technical and organisational measures suited to the risk. They include:

- storing passwords only as salted one-way hashes;
- storing session, email-link, enrolment-key and device credentials only in hashed form;
- signing everyone out of all sessions when a password changes;
- temporarily locking sign-in after repeated failed attempts;
- limiting the rate of sensitive requests;
- serving our website and services only over encrypted connections (HTTPS);
- keeping installers in private, encrypted storage and delivering them only through expiring links; and
- in the desktop app, encrypting the transcript database on disk, keeping credentials in the operating
  system's secure store, and encrypting the local-network link to paired mobile devices.

9.2 No system is perfectly secure. If a breach affects your personal data and puts you at risk, we tell
you without undue delay, and we inform the authorities where the law requires us to.

## 10. Children

10.1 SelahCue is a tool for church production teams. It is not directed at children. You must be at
least `{{MINIMUM_ACCOUNT_AGE}}` to create an account, and we ask you to confirm this at sign-up.

10.2 We do not knowingly collect personal data from children. If you believe a child has given us
personal data, contact us and we will delete it.

10.3 Churches using live transcription, and especially cloud transcription, should take particular care
where children may be heard, for example in family services or children's ministry (see section 2.3).

## 11. Your choices and rights

11.1 Depending on where you live, you may have rights such as to:

- find out what personal data we hold about you, and get a copy;
- have inaccurate data corrected;
- have your data deleted;
- object to, or ask us to limit, how we use your data;
- receive your data in a format you can take elsewhere; and
- withdraw consent, where we rely on it.

11.2 **Deleting your account.** You can delete your user account yourself in your account settings. An
administrator can close your organisation's account in the customer portal. When we delete an account,
we delete or anonymise the personal data in it, and we keep security and audit records only in a form
that no longer identifies you, except where the law requires us to keep them.

11.3 **Getting a copy of your data.** Email `{{PRIVACY_CONTACT_EMAIL}}`. We confirm your identity, then
prepare an export of your account data and send it to you through a download link that expires. We do
this within `{{DSAR_RESPONSE_TIME}}`.

11.4 **Other requests.** For any other request about your personal data, email
`{{PRIVACY_CONTACT_EMAIL}}`. We may ask you to confirm your identity, and we reply within
`{{DSAR_RESPONSE_TIME}}`. We do not charge for requests unless a request is clearly unfounded or
excessive.

11.5 **Data your church holds.** We cannot access transcripts or other content stored on your church's
computers. To ask about that data, contact the church. For data sent to our cloud features, we help your
church respond to your request.

11.6 **Concerns.** Please contact us first so we can try to help. You can also contact the data
protection authority where you live.

## 12. Changes to this policy

12.1 We update this policy when our services or the law change. We post the new version at
`{{PRIVACY_POLICY_URL}}` and change the effective date.

12.2 If a change materially affects how we use your personal data, we tell account holders by email or
in the product before it takes effect. Where the law requires your consent to a change, we ask for it.

## 13. Contact us

- **Email:** `{{PRIVACY_CONTACT_EMAIL}}`
- **Post:** `{{LEGAL_ENTITY_NAME}}`, `{{REGISTERED_ADDRESS}}`
