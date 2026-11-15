# SelahCue Privacy Policy

> **DRAFT — NOT LEGAL ADVICE — REQUIRES REVIEW BY A QUALIFIED LAWYER BEFORE PUBLICATION**
>
> Version 0.4 (draft, 2026-11-15). Status: Draft — every `{{PLACEHOLDER}}` must be filled and every
> launch-readiness condition in `docs/legal/LEGAL-DRAFT-NOTES.md` §4 must be satisfied before
> publication. This draft describes the planned Free desktop release. The operational checks
> required before publication are recorded in the launch-readiness notes.

- **Who we are:** First Pavilion Technologies, trading as SelahCue ("SelahCue", "we", "us")
- **Registered address:** 4, Law Castle, Taiwo Street, Omida, Abeokuta, Ogun State, Nigeria
- **Registration number:** 1557879
- **Privacy contact:** `support@selahcueapp.com`
- **Effective date:** October 31, 2026

---

## Summary in plain language

This summary is part of the policy. The full sections below give the detail.

- **Your church's content is stored on your church's computers.** This includes slides, songs, scripture,
  service plans, sermon transcripts and sermon notes. Section 3 explains what leaves those computers when
  you request a cloud feature or send us content for support.
- **Local transcription runs on your computer.** The first time you use it, the app may need to download
  a speech-recognition model from Hugging Face.
- **Cloud features require opt-in.** Cloud transcription streams audio directly to Deepgram. For
  a notes request, the app sends the selected transcript text to SelahCue for temporary processing
  with OpenAI. This processing can happen outside your country.
- **Your SelahCue account** holds your email address, a one-way password hash, your church or
  organisation name, your country and time zone, and your name if you give it.
- **Licences, devices and downloads.** Activation registers your device with your account. When
  installers are published, you can download them without signing in.
- **Website cookies and storage** support sign-in and security. The website loads a font from Google,
  so Google receives your IP address when your browser requests it.
- **We do not sell your personal data, and we do not show ads.**
- **Privacy requests.** Contact us at `support@selahcueapp.com` (see section 11).

---

## 1. Who this policy covers

1.1 This policy explains how First Pavilion Technologies, trading as SelahCue, handles personal data when you:

- visit our website at `https://selahcueapp.com`;
- create or use a SelahCue account, including signing in, verifying your email and resetting your
  password;
- activate SelahCue on a computer, or download the desktop software;
- use SelahCue's optional cloud features;
- install and use the SelahCue desktop app; or
- contact us for help.

1.2 We decide why and how the personal data described in section 3 is used. The exception is audio and
transcript text you send to SelahCue for a sermon-note draft. We process it to provide the requested
feature to your church. Cloud transcription audio goes from your device directly to Deepgram (see
section 3.8).

1.3 This policy does **not** cover:

- content your church creates and keeps on its own computers with SelahCue (see section 2);
- the separately documented SelahCue Controller app; or
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

2.2 Your church controls what it creates and keeps on its computers, who can access it and how
long it stays there. Sections 2.6 and 3.8 explain what happens if you send us content.

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

2.5 **Local network features.** Where enabled, discovery advertises the desktop app on your church's
local network. NDI output sends presentation video to other equipment on that network. These local
connections do not send your presentation content to SelahCue.

2.6 **If you share church data with us.** If you send us a transcript, screenshot or file, for example to
get help, we handle it as described in section 3.6. Cloud features are described in section 3.8.

## 3. Personal data we collect and why

### 3.1 Your SelahCue account

You need an account to activate SelahCue on your computers, manage devices and use optional cloud
features. See section 3.3 for public desktop downloads.

| What we collect | Where it comes from | Why we use it | Our reason |
|---|---|---|---|
| Email address | You, at sign-up | To create your account, sign you in and send account emails | To provide the service |
| Password | You, at sign-up or reset | To sign you in. We store only a salted one-way hash, never the password itself | To provide the service |
| Church or organisation name | You, at sign-up | To set up your organisation's account | To provide the service |
| Country | You, at sign-up (the form suggests one from your browser settings) | To set up your account | To provide the service |
| Time zone | Your browser, automatically at sign-up | To show dates and times correctly and to time account events and allowance periods | To provide the service |
| Your name (optional) | You, at sign-up | To address you and show who manages the account | To provide the service |
| Account role (administrator or member) and status | Created by our system | To control who can manage licences and devices | To provide the service |
| Email-verification status and time | Created by our system | To confirm you control the email address | To provide the service |
| Sign-in sessions (a masked identifier, issue, expiry and last-used times) | Created by our system | To keep you signed in and let you sign out everywhere | To provide the service |
| Failed sign-in count and temporary lock time | Created by our system | To protect your account from password guessing | To keep our services secure |
| Notes our staff record about your account, and licence details | Our staff and our system | To support you and manage your licence | To provide the service; to run our business |

Because SelahCue is made for churches, holding an account may suggest a religious affiliation. We use
account details only to provide the service. We do not use them to profile anyone's beliefs.

### 3.2 Emails we send you

These emails help you set up and recover your account:

- an email-verification link, which expires after 24 hours;
- a password-reset link, which expires after 1 hour;
- a notice if someone tries to create an account with your email address. We send this instead of
  telling the person signing up that the address is already registered.

We use an email delivery provider to send these messages: `{{TRANSACTIONAL_EMAIL_PROVIDER}}`.

We send marketing emails only to people who have agreed to receive them, and you can withdraw that
consent at any time using the link in each email or by contacting us.

### 3.3 Licences, devices and downloads

**Activation.** When you activate the desktop app on a computer, the app sends us:

- a device identifier generated by the app (a random identifier the app creates for the computer);
- the platform (for example, Windows or macOS);
- the app version; and
- a device name, if you choose one (for example, "Sound booth PC").

We record which licence the device uses, when it was activated and its status. We send back a device
credential, which the app keeps in your operating system's secure credential store, and a signed
licence file, which the app keeps so it can run offline until the licence period ends.

**Licence check-ins.** When an activated device is online, the app contacts us from time to time, using
its device credential, to refresh its licence file. We record when each device last checked in.

**Downloads.** When installers are published, you can download them without an account or an activated
device. The public installer files use immutable release paths in DigitalOcean Spaces in SFO3 (San
Francisco). Your browser connects directly to that service, which receives your IP address and standard
request information. The public links use no SelahCue account or device credential.

We use activation and check-in information to apply device limits and usage allowances, manage
devices and prevent misuse of licences. Activation and check-ins do not send us slides, transcripts
or audio.

If your organisation uses an enrolment key to activate, we store the key in hashed form, with a
short masked version for recognition.

### 3.4 Free service

This release offers ongoing Free access. It has no paid checkout, and we do not ask for payment
details when you sign up, activate a device or download a public installer.

### 3.5 Website visits, security and server records

When you use our website or online services, we and our hosting providers process technical information
such as your IP address, browser type and requests. We use it to deliver the service, keep it secure
and fix problems.

- **Rate limiting.** We use short-lived counters to limit repeated requests, such as password resets.
- **Operational logs.** See section 8 for retention.
- **Security and audit records.** We record important account, licence and cloud-feature actions such
  as sign-up, device activation and cloud access decisions. These records can include an internal
  identifier, the action, its outcome and the time. Cloud usage records are described in section 3.8.

### 3.6 Support and contact

When you email us at `support@selahcueapp.com`, we use your contact details, message and any
attachments to deal with your request and improve our support. Please avoid sending transcripts
or other church content unless we need it to help you.

### 3.7 The desktop app's internet connections

The desktop app does not include advertising, analytics, telemetry or crash-reporting tools. It uses
your microphone or audio input only when an operator starts live transcription.

The desktop app connects to the internet only to:

- **activate and check in**, as described in section 3.3;
- **use cloud features** that an administrator has turned on, as described in section 3.8;
- **download the speech-recognition model.** The first time you use live transcription, the app
  downloads a model file from Hugging Face (`huggingface.co`). Your computer's IP address and a standard
  web request go to Hugging Face, as with any download. The app checks the file has not been altered
  before using it. Hugging Face handles that request under its own privacy policy.

### 3.8 Optional cloud features

This Free release is designed to provide two optional cloud features:

- **Cloud transcription.** After an administrator opts in and an operator starts cloud transcription,
  the desktop app streams live audio directly to Deepgram using a short-lived access credential.
  Deepgram returns text to the app. SelahCue does not receive the audio.
- **AI sermon notes.** When an operator requests a draft, the desktop app sends the selected transcript
  text to SelahCue. A SelahCue server worker uses a server-held OpenAI credential to process the text
  with OpenAI and stage the draft for the desktop app to retrieve. The notes request contains
  transcript text rather than audio.

The features are off by default and an administrator opts in to each separately. The app explains
what it sends, who receives it and that processing can occur abroad. The app shows when cloud
transcription is active.

**Temporary staging for notes.** The intended limit for keeping source text in temporary storage is
5 minutes. The staged draft is retrievable for up to 15 minutes from staging. The desktop app
validates the draft and acknowledges receipt after it durably saves it locally. Acknowledgement
triggers deletion of the staged copy. The intended physical limit for the staged draft is
20 minutes from staging if cleanup fails. The design excludes source text and drafts from the
account database, job broker, logs, traces and backups.

**Provider retention.** The temporary staging limits apply to SelahCue's storage. Deepgram's
handling of audio and OpenAI's handling of transcript text and responses are separate.
`{{CLOUD_PROVIDER_RETENTION_AND_USE}}`

**Usage records.** We use records such as organisation and request identifiers, timestamps, outcomes
and usage units to administer weekly allowances and investigate errors or misuse. These records
exclude audio, transcript text and generated drafts.

### 3.9 Bible texts

Bundled Bible texts can be used locally. The installer storage described in section 3.3 is for the
desktop software.

### 3.10 What we do not do

- We do not sell personal data.
- We do not share personal data for targeted or cross-context behavioural advertising.
- We do not make decisions about you based solely on automated processing that have legal or similarly
  significant effects. Applying plan limits and usage allowances is automatic, but it only controls
  access to features you have chosen, and you can contact us about any decision.

### 3.11 The SelahCue Controller mobile app

The SelahCue Controller has a separate privacy policy in `docs/legal/PRIVACY.md`. This policy covers
the desktop and website release.

## 4. Cookies and similar technologies

4.1 Our website uses only these technologies:

| Name | Type | Purpose | How long |
|---|---|---|---|
| `selahcue_account_session` | Cookie (secure, not readable by page scripts, sent only to our own site) | Keeps you signed in | Until you sign out, or up to 30 days |
| `csrftoken` | Cookie | Protects our forms against cross-site request forgery | Up to 1 year |
| `selahcue.session` | Browser local storage | Remembers your account role, organisation reference and session expiry, so the page can show that you are signed in. It contains no password or session credential | Removed when you sign out, or ignored once the session has expired |

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

5.2 We need the information marked as required at sign-up to create your account.

## 6. Who we share personal data with

6.1 Recipients include:

- **Hosting and infrastructure providers** that operate the website and account services (section 7).
- **DigitalOcean Spaces**, which receives public installer requests (section 3.3).
- **Our email delivery provider**, which sends account emails (section 3.2).
- **Deepgram**, which receives audio from your device for cloud transcription, and **OpenAI**, which
  processes transcript text for requested sermon notes (section 3.8).
- **Google**, when your browser loads the site font (section 4.3).
- **Professional advisers**, such as lawyers and accountants, under a duty of confidentiality.
- **Authorities**, when the law requires it or to protect people's safety or our legal rights.
- **A buyer or successor**, if our business or its assets are sold or reorganised. We would tell you
  before your data became subject to a different privacy policy.

6.2 The customer portal is intended to show administrators the licence, device and weekly allowance
information for their organisation.

## 7. Where your data is processed

7.1 We are based in Nigeria. Public desktop installer requests go to DigitalOcean Spaces in SFO3
(San Francisco). The providers and locations for the site, account API, database, notes worker and
logs are `{{SERVICE_HOSTING_LOCATIONS}}`. Deepgram, OpenAI and other service providers may process
data outside the country where the church is located.

7.2 Data protection rules can differ between countries. `{{TRANSFER_SAFEGUARDS_SUMMARY}}`

## 8. How long we keep personal data

| Data | How long |
|---|---|
| Account details, including unverified sign-ups | `{{ACCOUNT_RETENTION}}` |
| Sign-in sessions | Usable until revoked or expired, up to 30 days. Stored-record retention: `{{SESSION_RECORD_RETENTION}}` |
| Email-verification and password-reset links | Usable until used or expired, after 24 hours or 1 hour respectively. Stored-record retention: `{{CREDENTIAL_RECORD_RETENTION}}` |
| Rate-limiting counters and operational logs | `{{OPERATIONAL_LOG_RETENTION}}` |
| Security, licence, device and content-free usage records | `{{SECURITY_AND_USAGE_RETENTION}}` |
| Support messages | `{{SUPPORT_RETENTION}}` |
| SelahCue's temporary notes source and draft | See the intended staging limits in section 3.8 |
| Audio and transcript text processed by cloud providers | See provider retention in section 3.8 |

When we no longer need personal data, we delete it or make it anonymous. We may keep some data for longer
if the law requires it or if we need it to establish, exercise or defend legal claims.

## 9. How we protect personal data

9.1 We use technical and organisational measures suited to the risk. They include:

- storing passwords only as salted one-way hashes;
- storing session, email-link, enrolment-key and device credentials only in hashed form;
- signing everyone out of all sessions when a password changes;
- temporarily locking sign-in after repeated failed attempts;
- limiting the rate of sensitive requests;
- serving our website and online services over encrypted connections (HTTPS); and
- in the desktop app, encrypting the transcript database on disk and keeping credentials in the
  operating system's secure store.

9.2 No system is perfectly secure. If a breach affects your personal data and puts you at risk, we tell
you without undue delay, and we inform the authorities where the law requires us to.

## 10. Children

10.1 SelahCue is a tool for church production teams. It is not directed at children. You must be at
least 18 years old to create an account.

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

11.2 **Requests to close or delete an account.** Email `support@selahcueapp.com` to request closure or
deletion. We may ask you to confirm your identity or your authority to act for your organisation.

11.3 **Access and data copies.** Email `support@selahcueapp.com` to request a copy of your personal
data. We may ask you to confirm your identity before providing it.

11.4 **Other requests.** For other requests about your personal data, email `support@selahcueapp.com`.
`{{RIGHTS_REQUEST_PROCESS_AND_TIMING}}`

11.5 **Data your church holds.** We cannot access transcripts or other content stored on your church's
computers. To ask about that data, contact the church. For data sent to our cloud features, we help your
church respond to your request.

11.6 **Concerns.** Please contact us first so we can try to help. You can also contact the data
protection authority where you live.

## 12. Changes to this policy

12.1 We update this policy when our services or the law change. We post the new version at
`https://selahcueapp.com/privacy` and change the effective date.

12.2 If a change materially affects how we use your personal data, we tell account holders by email or
in the product before it takes effect. Where the law requires your consent to a change, we ask for it.

## 13. Contact us

- **Email:** `support@selahcueapp.com`
- **Post:** First Pavilion Technologies, 4, Law Castle, Taiwo Street, Omida, Abeokuta, Ogun State, Nigeria
