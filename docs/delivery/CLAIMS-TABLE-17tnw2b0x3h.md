# Marketing site claims table — ClickUp 17tnw2b0x3h

Date: 2026-10-04. Branch `web/17tnw2b0x3h-remove-unbacked-claims`. Covers the pages the ticket names (Home, Features, Pricing, Contact, Download, Changelog, About, 404) and the pages its comments added (Support, Docs, Blog, Careers, Affiliates).

## How to read this

- **Evidence rule.** A claim is backed only by shipped behaviour: code, the user docs written from what the app does (`implementation/marketing/src/lib/content/docs.ts`, `support.ts`), ADRs, or a recorded owner decision. A PRD *target* is not shipped evidence. This is the rule from the Figma audit (`docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md`).
- **Status.** `BACKED` = shipped behaviour supports it. `HEDGED` = stated as design intent ("designed to", "built so") and backed by an ADR and tests, but with no soak or field result. `OWNER` = kept by a recorded owner decision, not by shipped behaviour.
- **How this was produced.** Every line of copy was read against the repo by two independent read-only audits (2026-10-04). Where they found a claim contradicted or unbuilt, it was reworded or removed (first section). Citations are `file:line` at the commit that introduced this document; a sample was re-opened and confirmed before this was written.

## 1. Removed or corrected in this change

| Page | Was | Why it was unbacked | Now |
|---|---|---|---|
| Home, Pricing | `$19 / month`, a Church tier, "Multi-campus / site licensing", `MOST POPULAR`, annual-price arithmetic | Prices are undecided (D1); the tier lineup was superseded 2026-09-27 (Free/Core/Pro). Plan names and prices are API catalogue data (17tnw2az0gd) | "Plans and prices have not been published yet." Names and prices will come from the API (follow-up tickets) |
| Home, Pricing | "Cancel anytime", "a simple monthly subscription", "free forever" | No billing exists | removed |
| Pricing | Free/Pro/Platinum cards, a limits table (1/3/7 devices, 2/5/10 outputs), a Monthly/Annual toggle | DEC-008 lineup superseded; Core/Pro device, output and NDI limits undecided; no annual plan | removed |
| Pricing | FAQ: proration, a non-profit rule, PayPal / ACH | No billing, no non-profit rule, payment provider undecided (D2) | removed |
| Home | Three testimonials (names, churches, quotes) and their heading | Invented | section and component deleted |
| Home | "controlled from anywhere", "Control from anywhere" | Mobile control is LAN-based (PRD NG-5) | removed / "from your phone" |
| Home | `Windows 10/11 (64-bit)`, `macOS 12+ (Apple Silicon & Intel)` | No source in the repo | "Windows, macOS and Linux" |
| Home | "in minutes — no manual, no setup weekend" | A PRD target (G-4), not a measurement | "in three steps" |
| Home | "each with its own theme", "give any item its own theme" | Unknown whether shipped (FR-038 is R2) | removed |
| Home | `per-output orientation, scaling, mirror` on the NDI feed | Those apply to windows only; the NDI path applies theme and layer mask | "Set orientation, scaling and mirror per window" |
| Home | "a lost GPU" recovery | Whole-device GPU-loss recovery is not wired (`on_device_lost` has no non-test caller) | "a renderer fault, a lost display signal or a dropped phone holds the last good frame" |
| Home | "No runaway caches, no creeping slowdown", "keep every segment on time" | No soak run exists; no per-segment timing | "caps the queues and caches"; "a service countdown" |
| Home | "Build multi-slide song lyrics", "give any item…", songs as plan content | No lyrics entry or song editor; a song item shows only its title | FAQ question and answer reworded to presentations and scripture themes |
| Home | "any iOS or Android phone" | One controller app, not in the stores | "an iOS or Android phone running the SelahCue Controller app" |
| Home | "Start free and go live this Sunday. Cancel anytime…" | Nothing downloads yet; no billing | "Start free. Core live controls keep working with no network." |
| Features | "Countdown and count-up timers" | The app has a single countdown ("no count-up or elapsed timer", `docs.ts:541`) | "service countdown" |
| Features | "More outputs on higher plans", "NDI output on the Pro and Platinum plans" | Plan names and limits are API data; Platinum was retired | "More than one output from one deck", "NDI output is optional" |
| Contact | "A SelahCue specialist will respond within 24 hours", "Message Received!", the 800 ms fake send | The form sends nothing | Send disabled with a visible note; no success state |
| Contact | "Join 1,200+ worship tech leaders on Discord", two `href="#"` links, "enterprise SLAs", "dedicated support team", "partnering with us" | No community, enterprise tier, team or partnership route | one card: `support@selahcueapp.com` |
| Contact | `support@selahcue.app` | Unconfirmed address, wrong domain | `support@selahcueapp.com` (owner-confirmed 2026-10-04) |
| Support | "Our support team is available to assist your church" | A staffing claim | "Can't find what you need? Get in touch." |
| Support, Docs | "There is no macOS or Linux installer yet" | Contradicts the owner's launch framing | sentence removed (the NDI articles keep "the Windows installer is built with it") |
| Changelog | v1.2.0 "Latest Release", v1.1.0, v1.0.0, their dates, an NDI 5 engine, encrypted NIV/ESV/NLT downloads, "35% less VRAM" | App is 0.1.0; no release tagged; nothing benchmarked | empty state; layout kept for the first real release |
| Careers | Three invented roles, three culture cards ("remote-first", "thousands of volunteer tech teams"), Apply buttons | Nothing in the repo opens a role | "There are no open roles right now." |
| Affiliates | `20%`, `60 Days`, `$50`, PayPal / bank payouts, "12 months", an earnings calculator, four FAQ answers, "Apply" in three places | Programme is NOT-V1, terms undecided, no application exists | hero says the programme is not open yet; two steps; no calculator, FAQ or Apply |
| Affiliates | "Add software your customers need", "bundle SelahCue into your builds" | No reseller terms; the draft Terms bar resale and sublicensing (`docs/legal/TERMS.md:26`) | "Tell your customers about SelahCue", "recommend SelahCue to the churches you work with" |
| About | Tools "often assume a fast, always-on internet connection" | Competitor research says the opposite (`docs/research/COMPETITOR-MATRIX.md:177`) | "A worship service is no time for presentation software to depend on a network connection." |
| Download | "scan a QR code and you're connected"; songs and timers as plan content; pairing "after Go Live" | The desktop must approve the device; a song shows its title, a timer is a label; pairing is under Settings → Network & Mobile | reworded |
| 404 | "any devices you have activated are still presenting"; a nested second `<main>` | The page cannot know either (audit shared-chrome-32) | removed; root is a `div` |

## 2. Remaining factual claims and their source

### Home and Features

| Claim | Source | Status |
|---|---|---|
| Core live controls work with no network; offline-first | NFR-015; `docs.ts:106-118` | BACKED (sign-in, activation and the speech-model download need the network once, and are not core controls) |
| The output holds the last good frame on a fault ("never blanks", "designed so a fault cannot black out live output") — Home hero, card 1, reliability, Features, About, Affiliates | `selahcue-engine/src/engine.rs:1-9` (NFR-024, ADR-0015); `tests/test_fault.rs`; shipped window reconfigures a lost surface (`selahcue-desktop/src/main.rs:2332-2338`) | HEDGED: not whole-device GPU loss; closing the last output window ends the output (`docs.ts:200-201`); Blackout is deliberate |
| Bundled public-domain Bible, reference parsing, keyword search, offline | `selahcue-scripture/src/lib.rs:1-15`; `docs.ts:323-423` (five translations) | BACKED |
| Order of service; a single service countdown from the console or a phone | `docs.ts:457-481, 541`; phone Timer tab for Producers | BACKED |
| Stage confidence view: current line, next, timer; the audience never sees it | `selahcue-present/src/stage.rs:1-6`; `docs.ts:222-269` | BACKED |
| NDI source for OBS or vMix; optional; orientation, scaling, mirror per window | `docs.ts:272-320`; `selahcue-desktop/src/main.rs:1691` | BACKED. NDI ships in the **Windows installer only** today (`tauri.conf.json:28`, `windows-installer.yml:153-171`) |
| On-device transcript and scripture detection that assist and never gate core controls | `support.ts:361-393`; `selahcue-core/src/detection.rs:1-6`; FR-083 | BACKED (the speech model downloads once) |
| Memory is bounded; starts quickly | `performance/README.md:39`; `04-results/BASELINE-REPORT.md:44`; idle RSS 124 MB and cold start 1.56 s on one Apple M5 (`performance/STATUS.md`) | HEDGED: no soak run, one machine |
| Pair a phone over the local network, scan a QR code, no internet needed | ADR-0008:15; `docs.ts:547-602`; `support.ts:218-257` | BACKED (the desktop approves the device; not tested on client-isolated networks) |
| Multi-slide presentations with text, shapes and images; scripture themes in the Theme Designer | operator `index.html:1080-1090`; `app.js:2956` | BACKED |
| Windows, macOS and Linux available | Owner, 2026-10-04: the installers will exist when the site deploys; PRD G-2 | OWNER (today only a Windows NSIS installer is built) |
| "Free to start", "Download free" | Owner decision 2026-10-04 (label kept everywhere); DEC-008 / D7 Free plan | OWNER (the Free plan is decided but no shipped code enforces any plan) |

### Contact, Support, Docs, Blog, Changelog, Careers, Affiliates, 404

| Page | Remaining claim | Source | Status |
|---|---|---|---|
| Contact | Email `support@selahcueapp.com` | Owner-confirmed 2026-10-04; the generated Privacy and Terms use the same address | OWNER |
| Contact | "The contact form is not available yet" | No contact endpoint exists | BACKED |
| Support, Docs, Blog | Guides, articles, troubleshooting | `content.test.ts` guards each article's cited source; written from the console's wording | BACKED |
| Changelog | "No release notes yet" | App is 0.1.0; no release tagged | BACKED |
| Careers | "There are no open roles right now." / "SelahCue is offline-first presentation software for churches." | No role in the repo; `docs.ts:106-118` | BACKED |
| Careers | h1 "Build tools churches rely on" | — | Aspirational (not a claim that churches rely on it today; ADR-0027 records "pre-launch, no customers"). Left as Figma's headline |
| Affiliates | "The affiliate program is not open yet"; the two checklist lines | No application or portal route exists; checklist as Features | BACKED / HEDGED |
| Affiliates | Audience descriptions | Descriptions of who it is for, not product claims | n/a |
| 404 | "The link may be out of date, or the address may have a typo in it." | — | BACKED |

### Download and About

| Page | Remaining claim | Source | Status |
|---|---|---|---|
| Download | "Windows desktop app · 64-bit" | `windows-installer.yml:146, 162` (x64 only); `docs/ops/WINDOWS-INSTALLER.md:11` | BACKED |
| Download | Downloads "not available yet"; system requirements "To be confirmed"; iOS and Android apps "not available yet" | Honest placeholders (PR #134) | BACKED |
| Download | Controller pairs over the LAN; the desktop stays the authority if the phone drops | ADR-0008:15-19, 33; `docs.ts:558, 633-636` | BACKED |
| Download | "Free plan · Core live controls work offline" | `docs.ts:106-118`; DEC-008 / D7 | OWNER (Free plan not enforced in shipped code) |
| About | Founder narrative; "designed so a fault cannot blank live output"; "memory use is designed to stay within fixed limits" | engine.rs:1-9; `performance/README.md:39` | HEDGED |

## 3. Left on purpose (not changed here)

- **The "designed so it never blanks" family** — hedged ("designed", "built to"), ADR-0015-backed and tested; the audit rated it PARTIAL because a render fault holds the last frame while closing the last output window or choosing Blackout does blank it. Reviewed in earlier PRs; an owner/Uma call whether to soften.
- **"Free to start", "Download free", the Free-plan lines on Download and CtaBand** — kept by the 2026-10-04 owner decision. The shipped app enforces no plan, and DEC-008's Free tier would exclude NDI and cap speech-to-text at 30 minutes, which conflicts with the NDI and transcript headlines if enforced. Worth settling with D7/D8.
- **NDI is Windows-only today.** The pages say "NDI" without a platform. macOS and Linux NDI packaging is a follow-up (`vendor/ndi/README.md`).
- **The Account page** (`AccountView.vue`) still shows an invented organisation, contact, plan, `$15 / month`, a licence key, devices with `v1.2.0`, NIV/ESV/NLT entitlements and invoices (audit account-16 to 18). It is a signed-in surface being rebuilt from the API under 17tnw2b2cf2 and 86ak11rjz, and CI's responsive sweep uses its mock Cancel Subscription dialog and toast to exercise the shared overlays, so stripping it needs the sweep re-pointed first. **This is the one place a real signed-in customer would still see fiction.**
- **The admin console and affiliate portal shells** (`views/admin/*`, `views/affiliates/*`) hold sample people, payouts and PayPal addresses. They are NOT-V1 presentation shells (86ak11w7g, 86ak11t1f).
- **The legal pages** (Privacy, Terms) are generated from the platform drafts and owned by 17tnw2b0x3g.
- **`PricingCard` and `SegmentedToggle`** stay in the component library, with their tests, for the API-driven plan cards.
