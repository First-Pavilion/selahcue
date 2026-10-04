# Figma fidelity audit — marketing site and account screens

**Ticket:** [17tnw2b2c75](https://app.clickup.com/t/17tnw2b2c75) · **Date:** 2026-10-03 · **Audited build:** `origin/main` at `3fb96da8` · **Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ`, page *Marketing Website* (`468:124`) and section `743:124`

This file is **generated** by `python3 scripts/check_fidelity_audit.py --write-report` from `docs/design/visual-parity/marketing/{surfaces.json,findings/*.json,tickets.json}`. Edit the data, not this file. It records Phase 0 only: nothing was fixed.

## How to read this

Every one of the 16 pages and 19 auth/device states is a Figma frame with a node id. Each was rendered from the built `dist/` at 1440 wide, compared by picture (`scripts/vp_compare.py`) and by value (`scripts/vp_style_diff.py`: type size, weight, line height, colour, position, radius, spacing), then every difference was classified:

- **A** — code bug (fix to match Figma)
- **B** — documented deliberate deviation (leave, source recorded)
- **C** — Figma content the repo does not back (keep layout, ship no claim)
- **D** — Figma gap (not drawn; raise to Uma)
- **E** — screen missing in code (build it)

Binding owner decisions applied: **honest content wins** over Figma where the repo does not back a claim (layout and styling are kept, the claim is not shipped; removal from the live pages belongs to ClickUp 17tnw2b0x3h); **accessibility does not regress** (a Figma colour that fails AA stays accessible in code and is recorded as B); the Figma legacy variables versus the code `--sc-*` tokens are a **deliberate layer** (AUTH-LANDING-PAGES-HANDOFF 2.2), reported as `colour~`, never as a defect.

## Totals

| area (fix ticket) | A | B | C | D | E | total |
|---|---|---|---|---|---|---|
| chrome | 28 | 2 | 2 | 6 | 0 | 38 |
| components | 12 | 0 | 0 | 0 | 1 | 13 |
| home | 24 | 2 | 8 | 3 | 0 | 37 |
| core | 34 | 2 | 10 | 3 | 0 | 49 |
| secondary | 48 | 14 | 18 | 8 | 0 | 88 |
| auth | 23 | 5 | 2 | 7 | 0 | 37 |
| account | 13 | 2 | 7 | 7 | 7 | 36 |
| **all** | 182 | 27 | 47 | 34 | 8 | 298 |

Class A and E findings that raise fix work, by severity: high 84, medium 82, low 22. Not counted anywhere: 32 duplicates (the same defect seen again on another page; each names its canonical finding). Counted in the totals above but left out of this severity tally because they raise no fix here: 2 class A findings that another ClickUp ticket already owns (they carry `owned_by`).

## Fix tickets raised from this audit

- **chrome** — [17tnw2b2cev](https://app.clickup.com/t/17tnw2b2cev) · branch `web/17tnw2b2cev-shared-chrome` · [Web] Figma fidelity: shared chrome and tokens (Nav, Footer, UiButton, tokens.css, app shell)
  - footprint: `implementation/marketing/src/components/Navbar.vue`, `Footer.vue`, `UiButton.vue`; `src/assets/styles/tokens.css` and the global rules in `main.css`; `src/App.vue`; `src/router/scroll.ts`; their tests under `tests/`.
  - parallel: Runs in parallel with the shared-components ticket. All six area tickets wait for this one to merge before they finish (they may start earlier and rebase).
- **components** — [17tnw2b2cew](https://app.clickup.com/t/17tnw2b2cew) · branch `web/17tnw2b2cew-shared-components` · [Web] Figma fidelity: shared components (UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog)
  - footprint: `implementation/marketing/src/components/UiBadge.vue`, `FormField.vue`, `FaqAccordion.vue`, `PricingCard.vue`, `ConfirmDialog.vue`; their tests.
  - parallel: Runs in parallel with the chrome ticket (different files). All area tickets wait for it.
- **home** — [17tnw2b2cex](https://app.clickup.com/t/17tnw2b2cex) · branch `web/17tnw2b2cex-home` · [Web] Figma fidelity: Home page · depends on: chrome, components
  - footprint: `implementation/marketing/src/views/HomeView.vue`, `src/components/ConsoleMockup.vue`, `OutputManagerMockup.vue`, `TestimonialCard.vue`, `FeatureCard.vue`, `ReliabilityPillar.vue` (the Features page must not edit the two mockups: it builds its own panels), `tests/`.
  - parallel: Runs in parallel with the other area tickets once the chrome and components tickets have merged.
- **core** — [17tnw2b2cey](https://app.clickup.com/t/17tnw2b2cey) · branch `web/17tnw2b2cey-pricing-features-download-about` · [Web] Figma fidelity: Pricing, Features, Download and About · depends on: chrome, components
  - footprint: `implementation/marketing/src/views/PricingView.vue`, `FeaturesView.vue`, `DownloadView.vue`, `AboutView.vue`; new page-local components if needed (do NOT edit ConsoleMockup or OutputManagerMockup: the Home ticket owns them); `tests/` including `downloadView.test.ts`.
  - parallel: Runs in parallel with the other area tickets once the chrome and components tickets have merged.
- **secondary** — [17tnw2b2cez](https://app.clickup.com/t/17tnw2b2cez) · branch `web/17tnw2b2cez-secondary-pages` · [Web] Figma fidelity: Contact, Support, Docs, Changelog, Blog, Careers, Privacy, Terms and Affiliates · depends on: chrome, components
  - footprint: `implementation/marketing/src/views/ContactView.vue`, `SupportView.vue`, `DocsView.vue`, `ChangelogView.vue`, `BlogView.vue`, `CareersView.vue`, `PrivacyView.vue`, `TermsView.vue`, `AffiliatesView.vue`, `src/components/legal/*`, `src/components/article/*`; `tests/`.
  - parallel: Runs in parallel with the other area tickets once the chrome and components tickets have merged.
- **auth** — [17tnw2b2cf1](https://app.clickup.com/t/17tnw2b2cf1) · branch `web/17tnw2b2cf1-auth-pages` · [Web] Figma fidelity: Sign in, Verify (V1-V6) and Reset (R1-R7) · depends on: chrome, components
  - footprint: `implementation/marketing/src/views/SignInView.vue`, `VerifyView.vue`, `ResetView.vue`, `src/components/auth/*`, `src/assets/styles/auth.css`; `tests/authCopy.test.ts`, `authViews.test.ts`, `scripts/auth_pages_headless.py` (raise `EXPECTED_MIN_CHECKS` honestly).
  - parallel: Runs in parallel with the other area tickets once the chrome and components tickets have merged.
- **account** — [17tnw2b2cf2](https://app.clickup.com/t/17tnw2b2cf2) · branch `web/17tnw2b2cf2-account-and-devices` · [Web] Figma fidelity: Account page and Manage Devices (D1-D6) · depends on: chrome, components, sign-out-bug
  - footprint: `implementation/marketing/src/views/AccountView.vue`, a new `src/views/AccountDevicesView.vue`, the new `/account/devices` route in `src/router/index.ts`, `src/lib/api/account.ts` (device operations once the API exists), `tests/`, `scripts/auth_pages_headless.py` scenarios for the new states.
  - parallel: Runs in parallel with the other area tickets once the chrome and components tickets have merged. Starts after the Sign Out bug ticket lands (same file).
- **decisions** — [17tnw2b2cf3](https://app.clickup.com/t/17tnw2b2cf3) · [Design] Decisions needed from the Figma audit: claims the repo does not back (class C) and gaps in the designs (class …
- **devices-api** — [17tnw2b2cf4](https://app.clickup.com/t/17tnw2b2cf4) · [Backend] Customer-session GraphQL for Manage Devices: list devices, last seen, limit and used, deactivate, viewer role
- **sign-out-bug** — [17tnw2b2cbr](https://app.clickup.com/t/17tnw2b2cbr) · [Web] Account page "Sign Out" button never signs out: it only navigates to /signin
- **selftest-ci** — [17tnw2b2fum](https://app.clickup.com/t/17tnw2b2fum) · [CI] Run the visual-parity self-test and the audit checker's self-test in make ci and CI (no browser, about 1 second)

## Class C — Figma content the repo does not back (for Uma and the owner)

Keep Figma's layout and styling; ship no invented claim. Where the build already carries the claim, removal is [17tnw2b0x3h](https://app.clickup.com/t/17tnw2b0x3h)'s work, not a fix ticket from this audit. A few items run the other way: copy the repo already carries that contradicts something product has since said; each says so in its decision.

- **account-16** `account` (high) — Licensed-translation entitlements (NIV, ESV, NLT) are shown as granted; the repo has none
  - Figma: Not drawn.
  - Build: Hard-coded `bibles` ref (AccountView.vue:97-101): NIV (Biblica, Inc., 42 MB), ESV (Crossway, 38 MB), NLT (Tyndale House, 40 MB, 'EXPIRING 28 Aug 2026'), with last-synced and expiry dates and a working-looking 'Re-download'. Header badge '3 Entitled' on the tab and '3 Entitlements Granted'.
  - Decision needed: Honest content wins: do not show licensed entitlements that do not exist. Ship the GAP-FILL 2d 'No entitlements' state (bundled list + 'Upgrade to Pro to access licensed translations' prompt) or hide the card until licensed translations ship? Owner/Uma to choose; the bundled public-domain list is repo-backed. · owned by 17tnw2b0x3h
- **account-17** `account` (high) — Customer identity is invented: org, contact, email, role and plan are hard-coded for every signed-in visitor
  - Figma: Sample data: avatar 'GC', 'Grace Community Church', 'billing@gracecommunity.org', pill 'PRO PLAN' (506:124, handoff 8 lists these as Assumed placeholders).
  - Build: `user` ref (AccountView.vue:42-48): 'Grace Community Church', 'Sarah Jenkins', 'sarah@gracechurch.org', 'Organization Owner', 'March 2025' - rendered as the signed-in user's own details; the Settings form edits the same local copy.
  - Decision needed: What does the header show until the account API exposes profile fields? Options: derive nothing and render only what accountViewer gives (an empty/neutral header), or add org name / email / plan label to the API first (api-07). Not a design change - an honesty rule. · owned by 17tnw2b0x3h
- **account-18** `account` (high) — Subscription and payment details are invented (price, cycle, next payment, card)
  - Figma: 'Monthly - $19.00 / month', '1 September 2026', 'Visa **** 4242', plan 'Pro'; invoices '$19.00 Pro - Monthly PAID' for 1 Jun / 1 Jul / 1 Aug 2026.
  - Build: '$15 / month (billed annual)' and '1 Sep 2026' (AccountView.vue:51-60), plan 'Pro Tier', no payment-method row; two invoices 'Annual Pro Plan $180.00' dated 1 Sep 2025 / 1 Sep 2024 with ids INV-2026-008 / INV-2024-008 (the first id carries 2026 on a 2025 date); 'Cancel subscription' confirm claims …
  - Decision needed: Pricing numbers belong to 17tnw2b0x3h and decision D1; not argued here. Question for the owner: until billing exists, show the Subscription and Billing-history cards with real data only (plan name from the licence, nothing else) or an honest 'Billing is not available yet' state? · owned by 17tnw2b0x3h
- **account-19** `account` (medium) — Device list and 'N of 5' meter are invented; the sample slot count contradicts the Pro tier
  - Figma: 506:210 sample devices 'Studio PC . Windows 11 . active now', 'Booth MacBook . macOS 14 . 2 days ago'; meter '2 of 5 used' beside a PRO pill.
  - Build: `devices` ref (AccountView.vue:71-74): 'Sanctuary Main PC' (Windows 11 Pro, 192.168.1.104, Today at 10:45 AM, v1.2.0, this device) and 'Youth Room Mac Studio' (macOS Sonoma 14.5, 192.168.1.112, Yesterday at 4:15 PM); `subscription.seatsTotal: 5` (line 59); deactivate removes a row from the local ar…
  - Decision needed: Sample data is acceptable in Figma, not in the product. Confirm the real limit and device list come from the API (api-01, api-04) and that no '5' is hard-coded; if a design sample is wanted for docs, show Pro as '2 of 3'. · owned by 17tnw2b0x3h
- **account-20** `account` (high) — License key shown and copyable: the API stores only a hash and a masked key
  - Figma: 506:196 key 'SCUE-8F3A-2B9C-Q7X1-4KD2' (15/500) with 'Copy key' 506:198; handoff prose calls it 'masked key + Copy'.
  - Build: `licenseKey` = 'sc_live_9f82k3m4n5p6q7r8s9t0' (AccountView.vue:63); 'Reveal' unmasks it and 'Copy Key' writes the full mock key to the visitor's clipboard and toasts 'License key copied to clipboard!' (66-69).
  - Decision needed: 'Copy key' and 'Reveal' cannot work: the full key is show-once. Show the masked key as read-only text (and explain that activation is by signing in, DEC-005), drop Copy/Reveal, or add a different mechanism? Product/security call. · owned by 17tnw2b0x3h
- **account-28** `account` (medium) — Manage devices (D1, D3, D6): 'Last seen', recency dots and the 'THIS DEVICE' tag have no backing data
  - Figma: D1 rows show 'Last seen today at 10:42 / 2 days ago / 3 Aug 2026', a green/grey recency dot per row (753:317/326/333) and a 'THIS DEVICE' tag (753:321) on the first row.
  - Build: Not built.
  - Decision needed: Ship 'Last seen' and the dot only after a Device.last_seen_at (or equivalent) exists (handoff 10.4, owner: backend); until then show platform + version only. 'THIS DEVICE' needs a defined signal from the desktop app or should be dropped from the web page. Owner/Uma to confirm.
- **account-33** `account` (medium) — Manage devices (D4): 'open Settings > Account and sign in' points at a screen that does not exist yet
  - Figma: D4 body: 'Install SelahCue on the computer that runs your service, then open Settings > Account and sign in. The device appears here as soon as it activates.'
  - Build: Not built.
  - Decision needed: Ship the copy now as the target state (the path will exist when 86ajy7anx lands) or hold the Devices page until then? Product to decide; if shipped early, soften to 'sign in from SelahCue Settings'.
- **signin-02** `signin` (medium) — Sign-in body copy names billing and a paid plan
  - Figma: Body 'Sign in to manage your plan, billing and license. You don't need an account to run SelahCue — only to manage a paid plan.' 14.5/22 text/muted, three lines (h=66).
  - Build: 'Manage your plan, license and the devices you have activated.' (SignInView.vue:319). 'billing' and 'paid plan' are not claimed; the 'no account needed' sentence was moved into an info banner (see signin-04).
  - Decision needed: Owner: Figma promises 'billing' and 'a paid plan'; there is no billing or checkout in the repo and the commercial model (pricing decision D1) is open. Approve a body that keeps Figma's layout (three lines, same sentence order) but ships no billing/paid-plan claim, e.g. 'Sign in to manage your plan and license. You don't need an account to run SelahCue.' — or confirm billing is real. The build cur…
- **signin-03** `signin` (high) — 'Continue with Google' button and 'or' divider
  - Figma: Divider row (505:144: two 1px #2b323d rules + 'or' 13/400 text/muted) and a secondary button 'Continue with Google' (505:148: h44 r12 fill #1e232c, 1px #2b323d border, label 14.5/600 text/primary, 18px #f2b53c ellipse standing in for the Google mark 505:149).
  - Build: Neither is rendered. SignInView.vue header comment records why: DEC-007 chose SelahCue-owned email/password and rejected OIDC; the account GraphQL schema has no social mutation; no config key for a provider exists.
  - Decision needed: Owner/Uma: remove the 'or' divider and the Google button from the Sign in frame (DEC-007: email/password only), or reopen DEC-007 to add a social provider. The build correctly ships neither today. ClickUp 17tnw2b0x3h is NOT the owner of this: it removes unbacked claims the build already shows, whereas this is a feature the build never had.
- **home-18** `home` (high) — 'Watch 2-min demo' advertises a demo video that does not exist and links to a missing anchor
  - Figma: 469:133 'Watch 2-min demo' (with play glyph) under the hero CTA; handoff section 8 lists 'real screenshots + a demo video' as out-of-scope follow-ups.
  - Build: UiButton variant=outline href="#demo" (HomeView.vue:130); no element has id="demo" and no video asset exists in src/ or public/, so the button does nothing; the label still promises a 2-minute demo.
  - Decision needed: Owner/Uma: until a real demo exists, either remove the button (hero keeps one CTA) or relabel it to something true that links to a real page (e.g. 'See how it works'). Keep Figma's layout; do not ship a link to nothing. · owned by 17tnw2b0x3h
- **home-23** `home` (medium) — 'Sub-3-second cold start' rests on a control-server-ready proxy, not on time to a usable window
  - Figma: Reliability pillar 3 (474:144): 'Sub-3-second cold start and a tight, capped memory footprint.' (handoff section 2 words it '<=3 s cold start, capped memory').
  - Build: Pillar reads '≤3s cold start, capped GPU memory usage, and zero lag when triggering live slides.' with a '≤3S START' badge (HomeView.vue:221-222). Same number, plus 'zero lag' (no measurement exists).
  - Decision needed: Owner: either keep 'cold start under 3 seconds' only if Stage 5 measures time-to-first-frame on Tier-A hardware, or ship a claim the repo backs today (e.g. 'Starts fast and keeps memory bounded') with no number. Remove 'zero lag' and the '≤3S START' badge. Keep Figma's layout. · owned by 17tnw2b0x3h
- **home-33** `home` (high) — Pricing teaser asserts prices, a billing model, tier gating and a 'most popular' plan that the repo has not decided or built
  - Figma: 477:124: Pro '$19 / month' with 'Billed monthly, or save 20% yearly' and a 'MOST POPULAR' chip; Free '$0 / forever' with 'One physical output'; a 'Church / Custom' tier ('Multi-campus / site licensing', 'Guided onboarding & training', 'Priority support'); 'cancel anytime' repeated in the pricing su…
  - Build: Build ships the same $19, 'save 20%', MOST POPULAR, Church/Custom and 'Cancel anytime' copy (HomeView.vue:15-59, :298, :358); the module's isAnnual toggle is declared but never rendered.
  - Decision needed: Owner (pricing decision D1): the numbers are not argued here. Decide: (1) hide the price and 'save 20%' until D1 closes, or show 'Pricing coming soon'; (2) drop 'MOST POPULAR' and 'Cancel anytime' while no billing exists; (3) align tier names/limits with DEC-008 (Free 2 outputs, Pro 3 seats) or confirm 'Church' as a real tier. · owned by 17tnw2b0x3h
- **home-34** `home` (high) — Build-only plan limits contradict the tier decision (seats, outputs) and invent SKUs
  - Figma: Figma lists no seat counts and no Bible-entitlement line items.
  - Build: Pro 'Up to 5 Venue Device seats' (DEC-008: 3), Church 'Unlimited Venue Device seats' (DEC-008 top tier: 7), Free 'Single display projector output' (DEC-008: 2 outputs), plus 'Licensed Bible Entitlements', 'Custom Bible entitlement SLAs' and 'Dedicated Solutions Architect' (no such product or servic…
  - Decision needed: Owner: remove these invented bullets and use the Figma bullets as filtered by home-33. Confirm that a SLA / solutions-architect offer is not being promised before anything like it appears. · owned by 17tnw2b0x3h
- **home-36** `home` (high) — Testimonials are invented named quotes (Figma and build use different invented people)
  - Figma: 478:128: three named quotes - Marcus Bediako (Tech Director · Grace City), Dela Amenya (Worship Lead · Hope Chapel), Sam Okoro (Stream Team · New Life) - saying e.g. 'We moved three campuses to SelahCue' and 'dropped straight into our OBS stream', under the heading 'Run by volunteers. Trusted on Su…
  - Build: Three different invented people: Sarah Jenkins (Worship Director @ Grace Community), Mark Davis (Technical Director @ Redeemer Church), Pastor Paul Miller (Lead Pastor @ Hope Chapel) with fabricated quotes ('volunteer onboarding time dropped to zero', 'works 100% offline'); initials avatars SJ / MD…
  - Decision needed: Owner (binding rule: honest content wins): keep the section layout, ship NO invented person or church. Options: omit the section until real, consented quotes exist; or replace with product-voiced statements without attribution. The heading 'Run by volunteers. Trusted on Sunday.' is itself a trust claim and should be reworded until real users exist. · owned by 17tnw2b0x3h
- **home-40** `home` (medium) — Build FAQ states false facts about Bible translations and platform versions
  - Figma: Figma FAQ makes no claim about copyrighted translations or OS versions.
  - Build: Answer 3: 'Public-domain Bibles (WEB, ASV, BSB) are bundled ... Copyrighted translations (NIV, ESV, NLT) are granted via post-activation entitlement and downloaded to an encrypted local store'; answer 2: 'Windows 10/11 (64-bit) and macOS 12+ (Apple Silicon & Intel)'; answer 1: 'built desktop-author…
  - Decision needed: Owner: remove the licensed-translation answer (restore Figma Q3) and either cite real minimum OS versions from a release matrix or drop the version numbers. Platforms: product says Windows, Linux and macOS are available (2026-10-04), so naming the platforms is backed; the version numbers are not. · owned by 17tnw2b0x3h
- **home-42** `home` (high) — Build-only capability claims the repo cannot back (NDI 5, alpha, Wirecast, 4K, 60fps, internal NFR ids)
  - Figma: Figma's NDI copy says 'NDI source for OBS or vMix', 'NDI output - broadcast to OBS, vMix, or another machine'; it draws '1920 × 1080' only; no 'NDI 5', no alpha, no Wirecast, no 4K, no 60fps.
  - Build: 'Direct NDI 5 broadcast streams to OBS, vMix, and Wirecast with transparent lower thirds' (feature card, HomeView.vue:183), 'NDI 5 Stream · Alpha Channel' and 'Display 2 · 1920x1080 · 60fps' (OutputManagerMockup.vue:19,43), 'Full 4K resolution' and 'Direct IP feed with alpha channel transparency' (…
  - Decision needed: Owner (binding rule: honest content wins): remove 'NDI 5', alpha / transparent lower thirds, Wirecast, 4K, 60fps, 'zero lag', 'hardware', the NFR ids and 'Whisper AI' from the copy and mock sub-lines; describe NDI only as 'NDI output for OBS or vMix' and only if the shipped installer includes the NDI runtime (ADR-0013 legal gate OD-06/08 is still open). · owned by 17tnw2b0x3h
- **home-43** `home` (medium) — 'Computed entirely on-device' and '100% offline speech-to-text' overstate the AI privacy position
  - Figma: Feature 6 (472:165 block): 'AI that assists but never gates: live captions and spoken-scripture suggestions, computed entirely on-device.' FAQ 1: 'Internet is only needed to download the app or extra Bible translations.'
  - Build: Feature 6: '100% offline speech-to-text powered by local Whisper AI without relying on cloud services.' (HomeView.vue:188); FAQ: 'All core features ... run 100% locally'.
  - Decision needed: Owner: reword to the true position, e.g. 'Live captions run on-device by default; cloud providers are opt-in', and add the first-use model download to the FAQ 'internet' answer. · owned by 17tnw2b0x3h
- **pricing-15** `pricing` (high) — Plan names, prices and the 'Free forever / $19 per month / Custom' structure are assumed, and the tier set contradicts DEC-008
  - Figma: Free '$0 / forever'; Pro '$19 / month', 'MOST POPULAR'; Church 'Custom'; copy 'Start free forever... Cancel anytime'.
  - Build: Build shows the same numbers (Free $0 forever, Pro $19 / month, Church mis-shown as $0 / month). MARKETING-SITE-HANDOFF sections 2 and 8 mark all pricing figures and the tier set 'Assumed'. Repo evidence: DECISION-LOG DEC-008 decides Free / Pro / Platinum (not Church), price points and tier naming …
  - Decision needed: Owner: do we publish any price and tier name now? If not, keep Figma's card layout but show no price figure and no 'Church' tier until D1 closes. Do not argue the number here. · owned by 17tnw2b0x3h
- **pricing-16** `pricing` (high) — Feature-to-tier assignments in the cards and comparison table contradict the decided entitlement table
  - Figma: Figma: Free = 'One physical output', no NDI, no mobile control, no Theme Designer, no transcript; Pro = 'Unlimited' outputs, NDI, mobile control, Theme Designer, on-device transcript, 'Always on the latest version'; Church = multi-campus / site licensing, guided onboarding, priority support.
  - Build: Build repeats a different invented set (Pro 'Priority support'; Church '24/7 SLA', 'Custom integrations', 'Unlimited campuses', 'Enterprise deployment'). DEC-008 (docs/decisions/DECISION-LOG.md) decides: screens/outputs Free 2 / Pro 5 / Platinum 10; NDI outputs none / 5 / 10; STT 30 minutes / 5 hou…
  - Decision needed: Owner/Uma: re-derive the cards and the comparison table from the decided entitlement table (2/5/10 outputs, NDI 0/5/10, STT 30 min/5 h/10 h, Free watermark) or mark each row 'to be confirmed'. Free's watermark is a material disclosure the design omits. · owned by 17tnw2b0x3h
- **pricing-17** `pricing` (medium) — Pro action: Figma 'Get Pro' has no purchase flow behind it; the build's 'Start free trial' invents a trial
  - Figma: Pro card action 483:186: filled brand button 'Get Pro' 15/600 white, full width.
  - Build: PricingView.vue:25 labels it 'Start free trial' (still a dead button, see pricing-03). Platform PRD FR-506 defers trial/conversion terms (D1); the repo has account sign-in, licences and devices but no purchase/checkout path.
  - Decision needed: Owner: what does the Pro action do today (sign in to the portal? contact us? waitlist?) and what is it called? Remove 'free trial' unless a trial is decided. · owned by 17tnw2b0x3h
- **pricing-18** `pricing` (medium) — 'Annual · save 20%' and the Annual price: no annual plan exists in the repo, and the build invents a computed discount
  - Figma: Toggle label 'Annual · save 20%' (483:147) and Pro description 'Billed monthly, or save 20% yearly.' No annual price drawn.
  - Build: PricingCard.vue:27 computes Math.round(price * 0.8) when Annual is selected, so the Pro card shows '$15 / month' with no 'billed yearly' wording; the discount badge itself never renders (pricing-05). grep of the billing and catalogue apps finds no annual/yearly interval; handoff section 8 marks mon…
  - Decision needed: Owner: is annual billing real and at what discount? Until decided, remove the toggle's discount behaviour (keep layout) rather than computing a price. · owned by 17tnw2b0x3h
- **features-10** `features` (high) — 'Unlimited virtual outputs' and 'Per-output theme & framing' are not shipped and contradict the decided output caps
  - Figma: Row 5 bullets: 'Unlimited virtual outputs', 'Per-output theme & framing'; pricing table 'Simultaneous physical outputs ... Unlimited'.
  - Build: Build has no equivalent bullet (it says 'Independent graphics styling for house vs. broadcast' and mock '1080p60'). Repo: DEC-008 caps outputs at 2 / 5 / 10 per tier; Platform PRD FR-544 keeps counts as data; Core PRD FR-038/039 (independent per-output config, 3+ outputs) and NFR-005/006 are R2 and…
  - Decision needed: Owner: keep these two bullets? If kept, reword to what ships (a stated number of outputs per tier, per-output theme only when FR-038 lands) and do not say 'Unlimited'. · owned by 17tnw2b0x3h
- **features-11** `features` (medium) — 'An optional live transcript runs entirely on the machine — nothing leaves the building' is stated as absolute
  - Figma: Row 6 paragraph and bullets 'Live transcript, fully on-device' / 'Nothing leaves the machine'.
  - Build: On-device Whisper STT ships (selahcue-stt, bundled by the Windows installer with --features stt), but the repo also has an opt-in cloud speech path (selahcue-stt-cloud / cloud-stt, ADR-0010 'cloud STT remains an opt-in accuracy path') and DEC-008 meters STT hours per tier (30 min / 5 h / 10 h), whi…
  - Decision needed: Owner: is the on-device claim unconditional? If cloud transcription can be enabled, say 'on-device by default; cloud only if you turn it on'. Also: is on-device transcript a paid-only feature (Figma) or on Free (30 min per DEC-008)? · owned by 17tnw2b0x3h
- **download-04** `download` (high) — Installer version, format, size and OS-floor claims on the platform cards are unbacked
  - Figma: 'v1.0 · .msi installer · ~84 MB', 'v1.0 · universal .dmg · ~92 MB', 'Windows 10 & 11 · 64-bit', 'macOS 12 Monterey+ · Apple silicon & Intel'.
  - Build: Build shows no version or size (disabled state) but still states 'Windows 10 / 11 (64-bit)' and 'macOS 11.0 or later (Intel & Apple Silicon)', which also disagrees with Figma's macOS 12. Repo: operator version is 0.1.0 (crates/selahcue-operator/tauri.conf.json); bundle target is only 'nsis' and CI …
  - Decision needed: Owner: what are the shipped formats and supported OS floors? Product (owner, 2026-10-04): SelahCue is available for Windows, Linux and macOS. The repo packages only a Windows NSIS .exe, so is a macOS or Linux installer downloadable today? Show no version or size until a release exists. macOS floor: Figma says 12 Monterey+, the build says 11.0 (keep this finding). · owned by 17tnw2b0x3h
- **download-05** `download` (high) — System requirements: Figma, the build, the PRD and the owner requirement all disagree; the repo has no single backed figure
  - Figma: Minimum: Dual-core 2 GHz / 4 GB RAM / Integrated GPU / 500 MB free / One output (audience). Recommended: Quad-core 3 GHz+ / 8 GB RAM or more / Discrete GPU (NDI / multi-out) / SSD 1 GB free / Audience + stage display.
  - Build: Build minimum: OS Windows 10 / macOS 11, CPU Intel Core i3, RAM 4GB, Storage 500MB, Graphics DirectX 10 capable. Recommended: OS Windows 11 / macOS 13+, CPU Intel Core i5 / Apple M1, RAM 8GB+, Storage 2GB SSD, Dedicated GPU for NDI. Repo: SelahCue-PRD.md reference hardware tiers (line 373): Tier A …
  - Decision needed: Owner: choose the published minimum and recommended specs (RAM 4 GB vs PRD Tier A 8 GB is the headline conflict). Not picking a number here; the page should carry only figures the repo backs. · owned by 17tnw2b0x3h
- **download-09** `download` (medium) — 'Available for iOS and Android' and the 'Download on App Store / Google Play' badges claim availability the repo does not have
  - Figma: Bullet 'Available for iOS and Android'; badge captions 'Download on' above both 'App Store' and 'Google Play'.
  - Build: Build already says 'Coming soon' (download-08). Repo: mobile store publishing is open work; docs/release/mobile/RELEASE-CHECKLIST.md and STORE-LISTING.md are pre-launch drafts; no listing URL exists.
  - Decision needed: Owner: reword the bullet to the true status ('iOS and Android apps coming soon' or equivalent) and keep the badges in the disabled state; the Google badge caption 'Download on' should not be reused when real badges ship. · owned by 17tnw2b0q9j
- **about-08** `about` (low) — 'Capped memory, fast cold start, and no account or tracking required' states targets and a negative the repo does not evidence
  - Figma: Values card 4 'Bounded & respectful': 'Capped memory, fast cold start, and no account or tracking required.'
  - Build: Build has a different value but similar assumptions elsewhere. Repo: Core PRD NFR-001 sets a cold start target of 3 seconds or less on reference hardware (a target, not a measurement) and NFR-002/003 bound memory; no document states that the app or marketing site does no tracking, and Platform bill…
  - Decision needed: Owner: keep 'fast cold start' only if measured against NFR-001; confirm the 'no tracking' statement matches the privacy policy before publishing. · owned by 17tnw2b0x3h
- **contact-04** `contact` (high) — Contact addresses and community channel drawn in Figma are not backed
  - Figma: 'Email us' hello@selahcue.app (497:172), 'Support' support@selahcue.app (497:181), 'Community — Tips from other churches' community.selahcue.app (497:191).
  - Build: Ships 'Support & Sales Email' with mailto:support@selahcue.app (ContactView.vue:61) and a 'Community & Discord' card 'Join 1,200+ worship tech leaders on Discord for instant help.' whose link is href='#' (ContactView.vue:48-53). hello@ and community.selahcue.app are not shown.
  - Decision needed: Which real channels does the owner want listed (a verified mailbox, none yet, or form-only)? Keep Figma's three-card layout and styling, show only channels that exist, and no member count. · owned by 17tnw2b0x3h
- **contact-05** `contact` (high) — Response-time promises (Figma note card and form footnote)
  - Figma: Note card 497:195 (604x105, fill #1e232c, r16, pad 20/22): label 'Response time' 12/700 ls 0.7 #9aa4b2 and 'Mon–Fri, within one business day. SelahCue keeps running offline whether or not we're at our desks.' 14.5/22. Under the Send button: 'We usually reply within one business day. No account requ…
  - Build: Neither block is built. The only reply promise is in the success card: 'A SelahCue specialist will respond within 24 hours.' (ContactView.vue:81).
  - Decision needed: No SLA or staffed-hours claim is backed. Keep the note card and footnote styling but with honest copy (only 'no account needed' and 'SelahCue works offline' are true today), or omit them until a reply process exists. Owner to confirm the wording. · owned by 17tnw2b0x3h
- **contact-06** `contact` (high) — Form sends nothing but reports success and a 24-hour reply
  - Figma: Default state only: name / email / church / message and 'Send message'. No success or error state is drawn (MARKETING-SITE-HANDOFF 5). MARKETING-PORTAL-GAP-FILL-HANDOFF 6b specifies the success card 'Message sent!' / 'We'll get back to you within 1–2 business days.' (another SLA).
  - Build: handleSubmit validates, then setTimeout(800) sets isSubmitted; no request is made (ContactView.vue:16-33). Success card 'Message Received!' / 'Thank you for reaching out, {name}. A SelahCue specialist will respond within 24 hours.' / 'Send Another Message' (ContactView.vue:78-85).
  - Decision needed: Until a delivery path exists, should the form be removed or disabled with an honest note, or wired to an endpoint? Whatever ships, the success copy must not promise a reply time (the build's 24 h and the spec's 1–2 business days are both unbacked). · owned by 17tnw2b0x3h
- **support-06** `support` (medium) — 'Popular articles' heading is a popularity claim
  - Figma: Heading 'Popular articles' 26/700 centred above five rows: 'Pairing your phone over the local network', 'Setting up a stage display', 'Sending your program to OBS with NDI', 'Building your first service plan', 'Why the screen never blanks — and what to do if it does'.
  - Build: Heading 'Start here' with two rows (SupportView.vue:96-109). types.ts:68-73 records that startHere is a curation flag, not a popularity claim, because no analytics exist to say what is popular.
  - Decision needed: Keep Figma's centred heading and panel layout but label it honestly (for example 'Start here'). How many rows: Figma five, the content layer flags two? Row titles in Figma are placeholders; the build lists real articles (see support-09). · owned by 17tnw2b0q9h
- **support-08** `support` (medium) — 'Still stuck' line promises a one-business-day reply; build shows a CTA card instead
  - Figma: Centred 15/400 #9aa4b2 line inside the band: 'Still stuck? Contact support — we reply within one business day.' (no card or button; no distinct link colour is drawn).
  - Build: .help-cta card (r20, pad 40): h3 'Still need help?' 24px, 'Our support team is available to assist your church with technical questions.', gradient 'Contact Support Team' button to /contact (SupportView.vue:112-119, 263-279).
  - Decision needed: 'We reply within one business day' is an unbacked SLA (and 'support team' implies staffing). Keep Figma's single centred line under the list with 'Contact support' linking to /contact and have the owner approve honest copy with no reply time; the CTA card is not drawn. · owned by 17tnw2b0x3h
- **support-11** `support` (medium) — Support article says 'There is no macOS or Linux installer yet', which contradicts what product says
  - Figma: Figma draws no such sentence; the NDI troubleshooting article is part of the undrawn content layer (support-08).
  - Build: support.ts:108 (NDI article): 'Use a build that includes NDI. The Windows installer is built with it and carries the NDI runtime. There is no macOS or Linux installer yet.'
  - Decision needed: Owner: It is NOT yet known whether 'available' means a downloadable installer exists today on each platform, or that the app supports all three while only the Windows installer is packaged. Reconcile the sentence with the answer. Until then no page may claim a downloadable macOS or Linux installer (Download buttons stay disabled, PR #134).
- **docs-04** `docs` (medium) — '10 minutes' and installation / update / audio-setup claims
  - Figma: Callout 'New here? Run your first service in 10 minutes' / 'Install, build a plan, and go live — start to finish.'; tile 'Installation — Windows & macOS install and updates.'; tile 'Setup guides — Displays, audio, and per-output config.'; intro 'This hub covers installation...'.
  - Build: None of it is built. The content layer has no installation article and omits unverified workflows (docs.ts header: a workflow that could not be verified in the code is not written).
  - Decision needed: '10 minutes' is an unmeasured claim; 'Windows & macOS install and updates': product says macOS is available (2026-10-04) but no macOS installer or update mechanism is evidenced in the repo (open question: docs-09); 'audio' configuration is unverified. Keep the callout and tile layout with honest copy or omit those tiles; owner decision. · owned by 17tnw2b0x3h
- **docs-09** `docs` (medium) — Docs known-limits note says 'There is no macOS or Linux installer yet', which contradicts what product says
  - Figma: Figma draws no such note; it sits in the undrawn article layer (docs-06).
  - Build: docs.ts:317 (callout 'Known limits'): 'There is no macOS or Linux installer yet, so the Windows installer is the only packaged build that includes NDI.'
  - Decision needed: Owner: It is NOT yet known whether 'available' means a downloadable installer exists today on each platform, or that the app supports all three while only the Windows installer is packaged. Reconcile the sentence with the answer (same question as support-11). Until then no page may claim a downloadable macOS or Linux installer.
- **changelog-04** `changelog` (high) — Versions, dates and entries are unbacked in both Figma and the build
  - Figma: v1.0.0 'August 2026' [LATEST], v0.9.0 'June 2026', v0.8.0 'April 2026' with illustrative entries including 'Faster cold start (≤3 s on a release build)', 'Optional on-device live transcript', 'NDI streaming output to OBS / vMix'. MARKETING-SITE-HANDOFF 1a and 8 call the versions and dates illustrat…
  - Build: ChangelogView.vue:4-34: v1.2.0 'August 8, 2026' (Latest Release), v1.1.0 'June 15, 2026', v1.0.0 'March 1, 2026' with invented entries: 'Native NDI 5 Output Engine ... without extra plugins', 'Licensed Bible Entitlement Sync ... NIV, ESV, and NLT', 'Reduced GPU VRAM usage by 35% on 4K motion backgr…
  - Decision needed: Keep the card and list layout; replace the content with what is true (for example one honest card for the current 0.1.0 state, or 'No public releases yet'). Owner/Priya to decide what the changelog says before a release exists. · owned by 17tnw2b0x3h
- **changelog-05** `changelog` (medium) — Subtitle promises free updates and always-latest; 'LATEST' pill on an unreleased version
  - Figma: 'Every SelahCue release, big and small. Updates are free on your plan — you're always on the latest version.' and a 'LATEST' pill on v1.0.0.
  - Build: Subtitle copy is different (see changelog-01) and does not repeat the claim; a 'Latest Release' badge sits on v1.2.0, a version that does not exist.
  - Decision needed: 'Updates are free on your plan' (plans undecided) and 'you're always on the latest version' (no auto-update evidenced) are unbacked; keep the drawn layout with honest copy and show a LATEST pill only once a release exists. · owned by 17tnw2b0x3h
- **careers-07** `careers` (high) — Open roles are invented in both Figma and the build (and differ from each other)
  - Figma: Five roles: Senior Rust Engineer (Engineering, Remote, Full-time); Flutter / Mobile Engineer (Engineering, Remote, Full-time); Product Designer (Design, Remote, Full-time); Developer Advocate (Church Tech) (Community, Remote, Full-time); Support Specialist (Support, Remote, Part-time).
  - Build: Three different hard-coded roles (src/views/CareersView.vue:5-9): 'Rust Systems & Graphics Engineer' (Core Engine, 'Remote (US/EU/Africa)', Full-time), 'Senior Vue / Frontend Engineer' (Web & Dashboard), 'Worship Tech Solutions Specialist' (Customer Success). 'Remote (US/EU/Africa)' is an extra geo…
  - Decision needed: Keep Figma's list layout (careers-04) but ship no role the company has not opened. What does the page say when the list is empty (see careers-09)? Owner to confirm whether any real role exists to list. · owned by 17tnw2b0x3h
- **careers-08** `careers` (medium) — Company claims and the careers@ mailbox
  - Figma: Hero: 'We're a small, remote team...'. Card 'Remote-first', 'Ship features churches use live, every week.', 'Sustainable pace - we build for the long run.' Footer line: 'reach out at careers@selahcue.app'.
  - Build: 'remote-first team' (hero), 'Fully Remote & Flexible - Work from anywhere in the world with flexible hours built around your life and family', 'Remote (US/EU/Africa)' and the build-only claim 'Your work directly supports thousands of volunteer tech teams and worship leaders every single Sunday.' (C…
  - Decision needed: Owner: what can we honestly say about team size and remote policy? Remove 'thousands of volunteer tech teams' (no usage data). Does careers@selahcue.app exist (and on which domain: selahcue.app or selahcueapp.com)? Until confirmed, Figma's closing line ships without an address. · owned by 17tnw2b0x3h
- **privacy-11** `privacy` (medium) — Figma privacy mailbox and date are not backed
  - Figma: 'Questions about privacy? Email privacy@selahcue.app.'; 'Last updated: August 2026'.
  - Build: The draft names support@selahcueapp.com as the Privacy contact (domain selahcueapp.com); ContactView.vue uses support@selahcue.app (domain selahcue.app). Date shown is the document's version date (1 October 2026).
  - Decision needed: Owner: which domain and privacy mailbox are real (L-1 gate)? Do not copy Figma's privacy@ address; legal wording itself is not part of this audit. · owned by 17tnw2b0x3h
- **terms-12** `terms` (medium) — Figma legal mailbox and plan names are not backed
  - Figma: 'Questions about these terms? Email legal@selahcue.app.'; 'Paid (Pro / Church): the features and outputs described on the Pricing page'; 'Free: run a service on a single machine, forever, at no cost.'; 'Last updated: August 2026'.
  - Build: The draft names support@selahcueapp.com as Contact and Legal notices (domain selahcueapp.com); ContactView.vue uses support@selahcue.app (domain selahcue.app). Plan names and limits come from the draft, not from Figma. Date shown is the document version date.
  - Decision needed: Owner: which domain and which legal/support mailboxes are real (L-1 gate)? Do not copy Figma's legal@ address. Plan names in the final Terms must follow DEC-008 (Free / Pro / Platinum), not Figma's 'Pro / Church'. · owned by 17tnw2b0x3h
- **affiliates-12** `affiliates` (high) — The 20% commission rate is not backed anywhere in the repo
  - Figma: '20%' stat card; H1 'Earn 20% recurring...'; hero sub 'earn 20% of every payment for a full year'; step 3 'Get 20% of every payment for a year'; earnings example '20% of $19 / mo'; FAQ answer 'There's no cap'.
  - Build: H1 'Earn 20% Recurring Commission', card '20% Recurring Commission', FAQ 'You earn a 20% recurring commission for 12 months on every paid subscription', and the calculator constant 3.8 = 20% of $19 (AffiliatesView.vue:7-16, :31, :46-49, :19).
  - Decision needed: Owner: the programme is marked NOT-V1 and its terms are undecided, so no rate may be advertised. Decide whether /affiliates ships at all in V1 (the footer links it on every page) and, if it does, what the page says without a rate (e.g. an interest/waitlist page). Layout and styling stay as Figma per the owner rule. · owned by 17tnw2b0x3h
- **affiliates-13** `affiliates` (high) — Programme terms, payout methods and promises are invented
  - Figma: '12 months' (renewals), '60 days' cookie/attribution, 'Monthly' payouts, 'Free to join · No audience minimum · Monthly payouts via PayPal, Wise or bank', 'pass $50', 'Most applications are reviewed within a couple of days', 'ready-made banners', 'Banners, links and email copy are done for you', FAQ…
  - Build: '60 Days' card plus FAQ 'Our referral tracking uses a 60-day last-click attribution window', '$50' threshold card, 'Monthly payouts direct to your PayPal or bank account with clear real-time reporting', FAQ 'Payouts are processed on the 1st of every month via PayPal or Direct Bank Transfer once you…
  - Decision needed: Owner: none of these figures or promises can ship until the affiliate terms exist (DEC-008). Remove or replace with honest placeholders when 17tnw2b0x3h lands; affiliates-07, 03 and 08 keep Figma's layout around whatever copy remains. · owned by 17tnw2b0x3h
- **affiliates-14** `affiliates` (medium) — Earnings example figures, the $19 Pro price and 'Read the terms'
  - Figma: '25 Pro churches', '20% of $19 / mo', '12 months each', '$95 / month recurring' (25 x $3.80); closing band button 'Read the terms'.
  - Build: Calculator output '$38/mo' and '$456/yr' at the default 10 churches, from the hard-coded $19 (AffiliatesView.vue:9-16). No 'Read the terms' control; no affiliate terms document exists.
  - Decision needed: Owner: the earnings maths cannot be shown without a price and a rate. Show no figure, or a clearly labelled placeholder; 'Read the terms' needs a target document or must be dropped. · owned by 17tnw2b0x3h
- **affiliates-15** `affiliates` (low) — Checklist claims: one backed, one unbacked, two depend on the programme
  - Figma: 'A product churches actually keep using - it never blanks the screen'; 'Offline-first reliability that sells itself, no internet required'; 'Recurring commission for a year, not a one-time bounty'; 'Banners, links and email copy are done for you'.
  - Build: Not built (affiliates-03).
  - Decision needed: Owner: keep the two backed lines, drop 'actually keep using' and the two programme lines until they are true. · owned by 17tnw2b0x3h
- **shared-chrome-13** `shared-chrome` (medium) — 'Download free' CTA leads to a page where nothing downloads
  - Figma: 'Download free' (468:138, label 14/Bold) is the nav CTA on every page, and the same promise is the primary CTA in the hero (469:131), Pricing, Features and About bands.
  - Build: Navbar.vue:216 (and the mobile sheet :280) route 'Download free' to /download. DownloadView.vue:22-43 and :98-109 state 'No installer is served from this page yet' and render every download button disabled; implementation/api/selahcue_api/apps/downloads and billing contain only __init__/apps/migrat…
  - Decision needed: Owner: keep Figma's 'Download free' (honest /download state already explains the wait), or relabel the CTA (nav, hero, bands) to the honest action until the first signed installer ships? The relabel/removal is owned by 17tnw2b0x3h; this finding only records the nav instance. · owned by 17tnw2b0x3h
- **shared-chrome-19** `shared-chrome` (medium) — Footer tagline and legal line carry 'subscription-simple' and 'Cancel anytime', which the repo does not back
  - Figma: Tagline 'Church presentation, done right. Offline-first, subscription-simple, built for the moment that matters.' (479:135, 14/21) and legal line '© 2026 SelahCue · Works offline · Cancel anytime' (479:160), with 'Windows · macOS' on the right.
  - Build: The build shows neither claim and neither wording: Footer.vue:98 tagline 'Church presentation, reengineered', Footer.vue:129 '© 2026 SelahCue. All rights reserved.'
  - Decision needed: Owner (binding rule: honest content wins): adopt Figma's layout and wording minus the unbacked parts, e.g. tagline 'Church presentation, done right. Offline-first, built for the moment that matters.' and legal line '© 2026 SelahCue · Works offline', plus the right-hand 'Windows · macOS'. Confirm the exact wording with product before it ships. 'Windows · macOS' stays as drawn.

## Class D — Figma gaps (for Uma)

Things Figma does not draw (a state, a page, or an element the build has that no frame shows). Not invented here.

- **account-21** `account` (medium) — Sidebar behaviour and the Overview / Settings destinations are undefined; the build invents a Settings form
  - Figma: Five sidebar rows; 'Subscription & billing' is drawn selected while all three cards are visible, so the frame does not say whether rows scroll to a card or switch views. No frame for Overview, Invoices or Settings content, no sidebar entry for Bible translations.
  - Build: Tabs filter the cards (AccountView.vue:170-391): 'Overview' shows everything, other tabs show one card; 'Settings' shows a built-from-nothing form 'Account Settings' (Organization Name, Primary Contact, Email Address, 'Save Changes', lines 361-390) that edits local mock state and toasts 'Settings s…
  - Decision needed: Uma: do sidebar rows anchor-scroll a single page (as the frame suggests) or switch views? Is a Settings view wanted at all, and which fields can actually be saved (no account-update mutation exists - account_schema.py has none)? Does Bible translations get its own sidebar row?
- **account-25** `account` (high) — Brand accent ink (#5b6bd6 / --sc-primary) fails AA as small text on panel and elevated surfaces
  - Figma: Accent text on Account frame: selected sidebar 'Subscription & billing' 14.5/600 and 'PRO PLAN' 11/700 on #1e232c = 3.39:1; 'Download' links 13.5/600 on #171b22 = 3.72:1; AUTH-LANDING-PAGES-HANDOFF 12 states these tokens are 'audited AA'. They are not.
  - Build: --sc-primary #6e5cf0 used as text: 'Download PDF' 13/400 on --sc-surface = 3.83:1, role tag 14/500 on --sc-base = 4.12:1, selected-state ink wherever added. Slightly better than Figma but still below 4.5.
  - Decision needed: Uma: define a text-grade brand ink (>= 4.5:1 on --sc-surface and --sc-elevated) for small accent text, used for links, selected nav labels, pills and tags; keep #6e5cf0 for fills. Until then neither Figma nor the build passes.
- **account-29** `account` (high) — Manage devices (D1-D6): Figma draws four sidebar labels in #000000 on #171b22
  - Figma: Rows Overview (753:152), License (753:156), Invoices (753:158) and Settings (753:160) have text fill #000000 (contrast about 1.2:1 against #171b22); 'Subscription & billing' is #eef1f6. In the Account frame 506:124 all non-selected rows are #eef1f6.
  - Build: Not built (so nothing to copy by mistake - but a literal implementation would render invisible labels).
  - Decision needed: Uma: confirm this is an authoring slip from cloning 506:124 and that 506:124's #eef1f6 governs the sidebar (this audit's fix text assumes so). Please correct the six frames.
- **account-30** `account` (medium) — Manage devices: states the page needs but Figma does not draw
  - Figma: D1-D6 cover populated, confirm, limit reached, empty, load error, over limit.
  - Build: Not built.
  - Decision needed: Uma: draw (1) loading skeleton for the list (GAP-FILL 7f pattern), (2) Deactivate pending (button disabled + 'Deactivating...') and failure (inline message; never a fake success), (3) read-only variant for MEMBER users with Deactivate hidden, (4) Free tier '1 of 1'. Frontend needs the viewer role (api-07).
- **account-31** `account` (medium) — Manage devices (D2): white label on the red Deactivate button is 3.76:1
  - Figma: Button 754:254 fill #ef4444, label 14/600 #ffffff = 3.76:1 (AA normal text needs 4.5:1).
  - Build: Not built. The build's --sc-live #ff4d4d with white is 3.27:1; --sc-live as a fill with --sc-base ink (#0b0d12) is 5.16:1 on #ef4444.
  - Decision needed: Uma: choose an accessible destructive button (dark ink on #ef4444, or a deeper red fill with white). Do not copy white-on-#ef4444. Same decision applies to the Cancel-subscription dialog's confirm button (GAP-FILL 7a).
- **account-32** `account` (medium) — Manage devices (D3, D4, D6): 'How device slots work' and 'How to activate a device' have no destination
  - Figma: Two ghost buttons (D3/D6 and D4) with no linked frame or article.
  - Build: Not built. No page in the site covers device slots or activation: grep of src/lib/content (docs.ts, support.ts) finds 'Manage devices' only for paired phones (Settings > Network & Mobile), a different feature.
  - Decision needed: Wren/Uma: which doc or support article do these open (new article, or an anchor in Documentation)? Without one the buttons must not ship; do not point them at the paired-phones docs, which describe a different thing.
- **account-34** `account` (low) — Manage devices (D6): danger-banner glyph is '!' in the frame, '✕' in handoff 2.2
  - Figma: 755:526 glyph is '!' (#ef4444). AUTH-LANDING-PAGES-HANDOFF 2.2 table: danger banner glyph '✕'. D5 uses '✕' on the error disc, D3 uses '!' for warning.
  - Build: Not built. components/auth/AuthBanner.vue GLYPHS: danger '✕', warning '!'.
  - Decision needed: Uma: which glyph is canonical for danger banners? The shared AuthBanner ships '✕' (handoff text); the frame shows '!'. The build will follow whichever you confirm.
- **account-35** `account` (medium) — Manage devices (D6): '5 OF 3 ACTIVE' pill is 4.19:1 (#ef4444 on #1e232c at 11/700)
  - Figma: Pill 755:431 label #ef4444 on #1e232c = 4.19:1, below the 4.5:1 AA threshold for 11px text. The meter value '5 of 3 used' 14/600 #ef4444 on #171b22 = 4.59:1 passes.
  - Build: Not built. --sc-live #ff4d4d on --sc-elevated #1c1f28 = 5.03:1.
  - Decision needed: Build the pill with the mapped --sc-live (#ff4d4d, 5.03:1), which clears AA; confirm with Uma that the lighter red is acceptable for this one pill.
- **signin-04** `signin` (medium) — Build-only info banner on Sign in
  - Figma: No banner on the card. The 'you don't need an account to run SelahCue' message is the second sentence of the body paragraph (505:124).
  - Build: AuthBanner kind=info 'You don't need an account to run SelahCue' / 'Signing in manages your plan, license and devices. Live presentation works offline, always.' closes the card (SignInView.vue:369), about 107px of height. No handoff specifies a banner for Sign in: AUTH-LANDING-PAGES-HANDOFF.md §1 c…
  - Decision needed: Uma: should Sign in carry the reassurance banner (build) or the in-body sentence (Figma)? If the banner stays, draw it in 505:124 and drop the sentence from the body; if not, remove the banner and restore the sentence (subject to signin-02).
- **signin-14** `signin` (medium) — Sign-in states other than the default have no frame
  - Figma: Only the default state is drawn (505:124). MARKETING-PORTAL-GAP-FILL-HANDOFF.md §3b specifies submitting, wrong credentials, rate limited, server error and success in prose; its Figma frames are 'to be added' (GAP-07).
  - Build: The build renders submitting (button spinner, fields 50%), a rejection banner 'Invalid email or password' / 'Check both and try again.' (§3b says 'Please try again.'), 'Too many attempts' / 'Wait a few minutes, then try again.' (§3b specifies a countdown; the API gives no retry-after), an unreachab…
  - Decision needed: Uma: draw frames for these states (or confirm the prose) so the build can be reviewed against a design, and say which validation wording is canonical (GAP-FILL §3c or the shipped emailPolicy wording).
- **verify-v1-03** `verify-v1` (low) — V1 title wraps to two lines in the build because the web font measures wider than Figma's Inter
  - Figma: V1 (743:125) draws 'Verifying your email address…' on one line in a 358px column, so the card is 239px tall.
  - Build: The title wraps to two lines and the card is 272px (+33px): its natural width in the browser is 360px, wider than both the build's column (356px) and Figma's (358px). Making the column 358px (signin-11) alone will not stop the wrap.
  - Decision needed: Uma: allow the V1 title to wrap (and redraw the frame at two lines), or give the title a slightly smaller size or tighter tracking so it fits in 358px. The cause is the web font's metrics against Figma's Inter, not a layout bug, so no engineer fix can make both true. · owned by verify-v1-01; signin-11
- **verify-v2-02** `verify-v2` (low) — Typographic apostrophes in Figma copy, ASCII in the build and the copy deck
  - Figma: Figma auth copy uses U+2019: 'You don’t need an account to run SelahCue', 'didn’t', 'we’ll', 'Don’t close this tab.' (Sign in's own copy in Figma uses straight apostrophes).
  - Build: The build renders ASCII ' everywhere (VerifyView.vue, ResetView.vue, lib/auth/messages.ts), as does the handoff copy deck (§8). The pinned test strings (tests/authCopy.test.ts, scripts/auth_pages_headless.py) also use ASCII.
  - Decision needed: Uma: which is canonical? Typographic apostrophes are the better typography; adopting them means changing the copy constants and the pinned test strings together.
- **verify-v3-02** `verify-v3` (low) — Transport-failure state and resend errors have no frame
  - Figma: /verify has no server-error frame (/reset has R7). The resend form has no pending or error frame.
  - Build: VerifyView.vue:332-348 renders a warning disc '!', 'We couldn't verify your email just now', 'We couldn't reach SelahCue. Check your connection and try again — this page is the only thing affected.', primary 'Try again' and a success banner 'Your link still works', extrapolated from R7 (comment at …
  - Decision needed: Uma: draw the V-series transport-failure state and the resend pending/error states, or confirm the R7-derived layout and copy.
- **reset-r4-02** `reset-r4` (low) — /reset 'no link' and 'link sent' states have no frame
  - Figma: The R-series has no frame for opening /reset without ?token= or for the 'new link requested' confirmation; /verify has V6 and V5.
  - Build: ResetView.vue:382-435 renders 'This page needs a reset link' (neutral disc, 'Send a reset link' form) and 'Check your inbox' ('If … has a SelahCue account, a new reset link is on its way. It expires in 1 hour.'), both extrapolated from V6 and V5.
  - Decision needed: Uma: draw R-series equivalents of V6 and V5, or confirm that the V6/V5 frames are reused with the 1-hour copy.
- **reset-r7-02** `reset-r7` (low) — PASSWORD_INVALID state has no frame
  - Figma: R7 is the only form-with-danger-banner frame ('We couldn't update your password').
  - Build: ResetView.vue:252-260 renders the same layout with 'That password wasn't accepted' / 'Your password has not been changed and this reset link still works. Choose a different password and try again.' for a server-side PASSWORD_INVALID. DEC-017 sanctioned the distinct code after the R-series was drawn.
  - Decision needed: Uma: draw the 'password not accepted' variant of R7 and confirm its copy.
- **home-19** `home` (low) — Build-only decoration and interaction states that no frame draws
  - Figma: Hero has no glow; the final CTA card has no outer shadow; feature cards have no hover state; the Pro pricing card is a flat #171b22 with a 2px #5b6bd6 border and no glow (handoff section 5 specifies only nav, button, FAQ, form states).
  - Build: hero-bg-glow (900x600 radial rgba(110,92,240,.15), HomeView.vue:422-434); final-cta-card box-shadow 0 25px 60px rgba(79,70,229,.3) (:688); FeatureCard hover translateY(-4px) + border/shadow (FeatureCard.vue:31-35); pricing-card.popular box-shadow glow + gradient background (PricingCard.vue:66-70); …
  - Decision needed: Uma: keep or drop these additions? If kept they need to be drawn (hover lift on cards, popular-card glow, hero glow) so QA has a reference; otherwise remove for pixel parity.
- **home-22** `home` (medium) — Build adds a metric badge to every reliability pillar that no frame draws
  - Figma: Pillar cards 474:130/137/144 end after the description (223px tall, no footer element).
  - Build: ReliabilityPillar.vue:20-24 adds a footer badge: '0 BLANKS', '100% OFFLINE', '≤3S START' (cards 285.7px tall); with the unstyled accent/warn variants (home-10) two of them render as bare white text. '≤3s' is also the proxy-only startup claim (home-23).
  - Decision needed: Uma: the three metric badges are not in the design. Remove them (recommended: '0 Blanks' is a zero-count claim with no counter behind it and '≤3s' is a proxy number, home-23) or draw and approve them. Pending that, they add 62px to the section.
- **home-44** `home` (medium) — Figma's own small coloured text fails AA (brand ink, LIVE, white initials on green and gold)
  - Figma: Drawn colours: eyebrows and 'MOST POPULAR'/'MAIN' tags in #5b6bd6 on #0e1116 / #171b22 / #1e232c = 4.07 / 3.72 / 3.39:1 (13px, 10px, 9.5px bold); LIVE #ef4444 on #1e232c = 4.19:1 (10.5px); testimonial avatars 478:140 / 478:148 draw white 14/700 initials on #2bb673 (2.61:1) and #f2b53c (1.83:1).
  - Build: The build copies the avatar failure ('MD' white on #2bb673 2.61:1, 'PP' white on #f2b53c 1.83:1, both in the report's failing list) and its LIVE mock label is 3.89:1; the eyebrows currently render white by accident (home-10), so they pass only because the variant is broken.
  - Decision needed: Uma: choose accessible inks for small brand text (e.g. a lighter brand tint such as the #a5b4fc already used in the hero pill, 8.96:1), for LIVE/READY chips, and dark initials on the green/gold avatars (#0e1116 gives >7:1). This decides the fix for home-10 and home-15.
- **pricing-19** `pricing` (medium) — Annual-selected state of the toggle and cards is not drawn
  - Figma: Only the Monthly-selected state is in frame 483:124; no frame shows the Annual-selected pill, the Pro price, the billing caption or the Church card under Annual.
  - Build: Build switches Pro to $15 and leaves '/ month'; Free and Church are unchanged.
  - Decision needed: Uma: if annual billing stays (see pricing-18), draw the Annual state: price, 'billed yearly' caption, and how Free/Church read.
- **pricing-20** `pricing` (medium) — A 'Pricing FAQ' section exists in the build but not in Figma, and its answers carry unbacked claims
  - Figma: Frame 483:124 ends with the comparison table then the footer (MARKETING-SITE-HANDOFF 1a: 'hero + toggle + cards + comparison table + footer'). The FAQ lives on Home only.
  - Build: PricingView.vue:151-158: 'Pricing FAQ' (40px) with 3 accordion items. Answers include 'Prorated charges will apply.', 'Our pricing is already optimized for churches and non-profits.' and 'We accept all major credit cards, PayPal, and ACH transfers for annual plans.' (payment methods and proration a…
  - Decision needed: Uma: keep a pricing FAQ (needs a frame) or remove the section? Either way the payment-method, proration and non-profit answers must go until decided. · owned by 17tnw2b0x3h
- **features-12** `features` (low) — Internal requirement ID 'NFR-024' appears in a customer-facing bullet
  - Figma: Row 1 bullet 'Never-blank guarantee (NFR-024)'.
  - Build: Build prints 'Zero-blank hardware frame buffer protection (NFR-024)'.
  - Decision needed: Uma/owner: NFR-024 is an internal PRD identifier; keep it in public copy or drop it?
- **contact-07** `contact` (medium) — 'Enterprise & Multi-Campus' card exists only in the build
  - Figma: Three method cards only: Email us, Support, Community.
  - Build: Third card 'Enterprise & Multi-Campus — Talk to our church solutions architect for enterprise SLAs.' with 'Schedule a Demo Call →' href='#' (ContactView.vue:65-72): a dead link and an unbacked offer (enterprise SLAs, a solutions architect, demo calls).
  - Decision needed: Remove it (Figma draws no enterprise card) or have Uma design it? The repo has no enterprise tier, SLA or demo process. · owned by 17tnw2b0x3h
- **contact-19** `contact` (medium) — FormField styling: two handoffs disagree and one decision has to settle it for Contact and the auth pages
  - Figma: Contact (497:124) and every auth frame draw the field label as Inter Medium 13 in the secondary text colour and the input well on the inset fill, 44 high (AUTH-LANDING-PAGES-HANDOFF 2.2 and 2.3).
  - Build: FormField.vue follows MARKETING-PORTAL-GAP-FILL-HANDOFF 10a: label 14/600 in the primary text colour, input on --sc-elevated, 3px focus glow. It is used by Contact, Sign up, Forgot password, Sign in, Reset and the affiliate and admin settings pages.
  - Decision needed: Uma: which spec governs FormField for Contact and the auth pages together? If AUTH-LANDING 2.3: the auth variant (signin-06, signin-07) is built and contact-10 flips from class B to class A. If GAP-FILL 10a: signin-06 and signin-07 become class B citing it, and the frames are the ones to redraw. Settle it before the shared-components ticket (FormField) and the auth ticket finish. · owned by contact-10; signin-06; signin-07
- **support-05** `support` (high) — Undrawn content layer (GAP-08) accounts for the +805px
  - Figma: Category cards are link tiles with no article list or count (170px); the list is one panel of five chevron rows; no search-results state, no empty-search state, no per-category anchors.
  - Build: Added by ClickUp 17tnw2b0q9h (commits 4f3a8592, cc6dc1cd): every card lists its real articles (.cat-articles, 44px-min rows) and an 'N article(s)' count (SupportView.vue:84-89); a 'Start here' list of curated articles with 'Category · N min read'; client-side search (searchSupport) that replaces th…
  - Decision needed: Neither MARKETING-SITE-HANDOFF nor the frame draws this (MARKETING-PORTAL-GAP-FILL-HANDOFF 9c specs only the article detail route). Uma: design the index layer (article lists inside cards or on category pages, counts, search results and empty state), or keep the drawn tiles and list and move article lists to category pages? Detail pages have no frame either (layout in 9c only) and were not audite… · owned by 17tnw2b0q9h
- **docs-05** `docs` (high) — Undrawn article-index layer accounts for the +1787px
  - Figma: No article rows: a six-tile grid (two rows of 83px) is the whole hub body (content column 521px tall).
  - Build: Six category sections (h2 22/700, 15px description, article cards) inside .docs-content (2541px tall): eleven article links as rows (.topic-link: --sc-elevated, r12, pad 16/18, title 16/600, 14px summary, '2 min read'), ids per category used by the sidebar and breadcrumbs (DocsView.vue:39-51, 287-3…
  - Decision needed: Not drawn, and MARKETING-PORTAL-GAP-FILL-HANDOFF 9b describes only the article detail layout. Uma: design the docs index, or keep Figma's hub and move the per-category article lists to category pages? Article detail pages have no frame either (9b layout only) and were not audited. · owned by 17tnw2b0q9h
- **docs-06** `docs` (medium) — Sidebar entries and tiles with no backing article
  - Figma: Introduction, Installation, Your first service, Setup guides, Themes & templates and Keyboard shortcuts appear as sidebar items or tiles; Outputs & displays, Scripture & plans, NDI & streaming, Mobile control and Troubleshooting exist in some form.
  - Build: The content layer has 11 articles in six categories (getting-started, display-outputs, scripture-bibles, timers-plans, mobile-control, troubleshooting); there is no article for Installation, Your first service, Setup guides, Themes & templates or Keyboard shortcuts, and 'Timers & Service Plans' exi…
  - Decision needed: Do we write the missing articles (Keyboard shortcuts and Themes exist in the app), map tiles to existing articles, or drop them? MARKETING-SITE-HANDOFF 1 says the footer 'Setup guides' link points to the Documentation page. · owned by 17tnw2b0q9h
- **blog-04** `blog` (medium) — Card count and build-only summary / Read link; detail pages have no frame
  - Figma: Featured post plus six grid cards (seven articles); no summary paragraph and no 'Read' link on cards; no frame for an article page.
  - Build: blogPosts has five posts: one featured plus four grid cards (blog.ts); each grid card adds a summary paragraph and a 'Read →' link; articles open at /blog/:slug (router/index.ts:22-26 spreads articleRoutes from router/articleRoutes.ts).
  - Decision needed: Write two more real posts, or show four cards in the 3-column grid (a short last row)? Does the owner want the card summary and 'Read →' link kept (undrawn)? Blog post detail (/blog/:slug) has no Figma frame (MARKETING-PORTAL-GAP-FILL-HANDOFF 9a layout only) and was not audited. · owned by 17tnw2b0q9h
- **careers-09** `careers` (medium) — Role destination and the empty-roles state are not designed
  - Figma: Each row has a 'View role' button but no role-detail frame exists, and no frame shows the page with zero open roles. MARKETING-SITE-HANDOFF section 8 lists 'deeper article/doc/role detail pages' as out of scope.
  - Build: Every row links to /contact via UiButton to="/contact" (CareersView.vue:56) labelled 'Apply Now →'. With careers-07 resolved honestly the list may be empty, and the build has no empty state.
  - Decision needed: Uma: where does a role link go (role detail page, mailto, external ATS) and what does the Open roles band show when nothing is open ('No open roles right now' plus the 'reach out' line)? Needed before careers-04 and careers-07 can ship.
- **affiliates-10** `affiliates` (high) — Interactive earnings calculator is build-only; Figma draws a static 'Earnings example'
  - Figma: Card 542:178 (x924 y1752, 420x307, radius 20, fill #171b22, 1px #2b323d, padding 28, gap 16) beside the checklist: 'Earnings example' 17px/600 with an 'ILLUSTRATIVE' pill (10px/700, tracking 0.6, #9aa4b2 on #1e232c, radius 999); rows 'You refer / 25 Pro churches', 'Commission / 20% of $19 / mo', 'A…
  - Build: AffiliatesView.vue:64-97 and :125-140: a 700-wide card 'Estimate Your Earnings' with a range slider (1-100 'Referred Active Churches', default 10) and two result boxes ('$38/mo', '$456/yr') computed as churches x 3.8 (line 11, the hard-coded '20% of $19/mo'). No 'illustrative' label. Three defects …
  - Decision needed: Uma / owner: keep an interactive calculator (needs a frame, an 'illustrative' label and AA-safe inks) or replace it with Figma's static, labelled 'Earnings example'? Either way the numbers are C (affiliates-13). If the calculator stays: give the slider an accessible name (aria-label or a label element), raise the three failing inks to 4.5:1, and label the result 'estimate'. · owned by 17tnw2b0x3h
- **shared-chrome-11** `shared-chrome` (low) — 'Active route underline' in handoff section 5 is not drawn in any frame and contradicts section 1
  - Figma: Features/Pricing/Download frames (485:125, 483:125, 487:125) draw the active link as Semi Bold text/primary with no underline or pill. Handoff section 1 says exactly that ('text/primary + Semi Bold').
  - Build: No underline in the build (.nav-item.active is colour-only), which agrees with the frames.
  - Decision needed: Uma: should the active link also carry an underline? The frames and section 1 say no; section 5 says yes. Recommend: no underline (match the frames) and strike the phrase from section 5.
- **shared-chrome-12** `shared-chrome` (medium) — Signed-in nav state is not designed: the code swaps 'Sign in' for 'Account' + 'Sign out'
  - Figma: Only the signed-out nav is drawn, on every frame, including the Account frame 506:124 (its nav 506:125 shows 'Sign in' + 'Download free' even though Account is signed-in only). The Account frame has its own Sign out outline button (506:148, 92x41, r10).
  - Build: Navbar.vue:204-215 (isProbablySignedIn): 'Account' (router-link /account, same muted ink, no active style) and a 'Sign out' <button> (signOut() then router.push('/'), error banner 'We couldn't sign you out...') replace 'Sign in'; the 'Download free' CTA stays. /account therefore shows Sign out twic…
  - Decision needed: Uma: draw the signed-in nav. Open points: Account link vs avatar/menu, whether Sign out lives in the nav or only on the Account page (it is drawn there at 506:148), whether 'Download free' stays for signed-in users, and the active treatment for Account. Until then the build keeps Account + Sign out.
- **shared-chrome-31** `shared-chrome` (medium) — Hover state is not drawn and the specified direction fails AA: UiButton primary hover is 3.78:1, the nav CTA hover darkens
  - Figma: Frames draw no hover. Handoff section 5: buttons 'hover (lightness shift)' and nav CTA hover 'brand-hover (+8% lightness)'. +8% lightness of #5b6bd6 is about #7c88de, white on it is 3.26:1.
  - Build: UiButton.vue:104-106 primary hover --sc-primary-hover #7e6eff with white 15-16px/600 label = 3.78:1 (resting #6e5cf0 is 4.72:1). Navbar.vue:436-438 nav CTA hover goes DARKER (#4f5ec7, 5.59:1), the opposite direction, so the two primaries behave differently. Gradient hover is a glow (:128-130), seco…
  - Decision needed: Uma: choose the hover value for primary. A lighter hover cannot hold a white 15px label at 4.5:1 on this indigo; recommend darkening (e.g. the nav's #4f5ec7, 5.59:1) for every primary, and amend section 5 ('+8% lightness') accordingly.
- **shared-chrome-33** `shared-chrome` (medium) — Every public page shares one document title
  - Figma: Not drawn (the frames have no browser chrome).
  - Build: index.html:6 sets 'SelahCue — Church presentation, reengineered' and only /privacy, /terms and the article detail pages change it (lib/legal, lib/useDocumentMeta). Home, Features, Pricing, Download, About, Contact, Support, Docs, Changelog, Blog, Careers, Sign in and Account all report the same tit…
  - Decision needed: Uma/product: agree the title scheme (e.g. 'Pricing — SelahCue', 'Sign in — SelahCue') and a route meta.title the shell applies on navigation. WCAG 2.4.2 expects a title that describes the page.
- **shared-chrome-35** `shared-chrome` (medium) — Linux is not drawn anywhere platforms are named (footer, Download cards, Home FAQ) although product says it is available
  - Figma: Footer 479:133 bottom bar draws 'Windows · macOS' only; the Download frame (487:124) draws a Windows card and a macOS card only; the Home FAQ row 'Which platforms are supported?' (478:155) answers with Windows and macOS and says Linux is on the roadmap.
  - Build: Footer.vue has no platform line; DownloadView.vue:28-46 has Windows and macOS cards and no Linux card; HomeView.vue:86-89 names Windows 10/11 and macOS 12+ only. No platform list on the site names Linux.
  - Decision needed: Uma: draw Linux wherever platforms are named (footer line, a Download card or entry, the FAQ answer) or confirm Windows and macOS only. Figma's 'Linux is on the roadmap' now contradicts product and must change either way. Do not add Linux to the build until it is drawn. It is NOT yet known whether 'available' means a downloadable installer exists today on each platform, or that the app supports a…

## Accessibility findings

- **account-10** `account` class A (high) — Secondary labels use --sc-text-muted (3.45:1) where Figma uses the secondary grey (6.25:1): Same roles painted with --sc-text-muted #6b7383: .summary-col .label (AccountView.vue:606-612), .key-info .label (655-658), .data-table th (691-700), .ent-meta (786-789). 12px text at 3.45:1 on --sc-elevated #1c1f28 and 3.79:1 on --sc-surface; AA normal text …
- **account-25** `account` class D (high) — Brand accent ink (#5b6bd6 / --sc-primary) fails AA as small text on panel and elevated surfaces: --sc-primary #6e5cf0 used as text: 'Download PDF' 13/400 on --sc-surface = 3.83:1, role tag 14/500 on --sc-base = 4.12:1, selected-state ink wherever added. Slightly better than Figma but still below 4.5.
- **account-29** `account` class D (high) — Manage devices (D1-D6): Figma draws four sidebar labels in #000000 on #171b22: Not built (so nothing to copy by mistake - but a literal implementation would render invisible labels).
- **account-31** `account` class D (medium) — Manage devices (D2): white label on the red Deactivate button is 3.76:1: Not built. The build's --sc-live #ff4d4d with white is 3.27:1; --sc-live as a fill with --sc-base ink (#0b0d12) is 5.16:1 on #ef4444.
- **account-35** `account` class D (medium) — Manage devices (D6): '5 OF 3 ACTIVE' pill is 4.19:1 (#ef4444 on #1e232c at 11/700): Not built. --sc-live #ff4d4d on --sc-elevated #1c1f28 = 5.03:1.
- **signin-08** `signin` class A (high) — Placeholder text fails AA: Placeholder uses --sc-text-muted #6b7383 on --sc-elevated #1c1f28 = 3.45:1, below the 4.5:1 AA minimum for normal text (FormField.vue:158-160; even on --sc-inset it would be 3.96:1). Same on verify-v3, verify-v6, reset-r4.
- **verify-v5-01** `verify-v5` class A (high) — Helper note ('Didn't arrive?') fails AA: au-note is 13px/20px --sc-text-muted #6b7383 on --sc-surface #14161d = 3.79:1, below 4.5:1 (auth.css:106-111). The same class carries R3's 'Don't close this tab.' (reset-r3) and every resend-error note.
- **reset-r1-03** `reset-r1` class A (high) — Field hint fails AA: FormField .field-hint is 13px/19.5px --sc-text-muted #6b7383 on --sc-surface = 3.79:1 (FormField.vue:247-250). Same on reset-r3 and reset-r7.
- **reset-r2-04** `reset-r2` class A (high) — Primary button hover fill fails AA with the white label: UiButton .variant-primary:hover uses --sc-primary-hover #7e6eff under a white 15.5/600 label = 3.78:1 (UiButton.vue:104-106). The scripted click leaves the pointer on the button, so the R2, R3 and R4 captures show the hover fill (dom button bg rgb(126,110,255…
- **home-07** `home` class A (high) — Text colours use off-token greys and pure white, and the muted ink used for secondary copy fails AA on the cards: Headings are literal #ffffff, section subtitles/blurbs/hero sub are literal #8c97a8 (not the mapped token, darker), and tertiary copy uses #717d93 in roles where Figma has muted: price period '/ month' 4.39:1 on the #12151e card, author roles 4.39:1, output-m…
- **home-13** `home` class A (medium) — The console mock has no accessible name or alt text; its fake UI text is exposed as page content: ConsoleMockup.vue renders ordinary divs/h2s/p (● LIVE, MAIN OUTPUT, FOR GOD SO LOVED THE WORLD..., CURRENT, NEXT) with no role='img', aria-label or aria-hidden, so a screen reader reads the mock as content (and a second h2 per pane sits in the heading outline…
- **home-15** `home` class B (low) — Hero eyebrow text keeps an accessible light-indigo ink instead of Figma brand #5b6bd6: hero-eyebrow colour #a5b4fc on #141722 = 8.96:1 (HomeView.vue:454).
- **home-39** `home` class A (low) — FAQ accordion: collapsed answers are still exposed to assistive tech and buttons lack aria-controls: FaqAccordion.vue: native <button aria-expanded> (Enter/Space work, aria-expanded present), but no aria-controls and the collapsed answer wrapper only uses grid-template-rows 0fr, so the hidden <p> stays in the accessibility tree and a screen reader reads clos…
- **home-44** `home` class D (medium) — Figma's own small coloured text fails AA (brand ink, LIVE, white initials on green and gold): The build copies the avatar failure ('MD' white on #2bb673 2.61:1, 'PP' white on #f2b53c 1.83:1, both in the report's failing list) and its LIVE mock label is 3.89:1; the eyebrows currently render white by accident (home-10), so they pass only because the var…
- **pricing-06** `pricing` class A (medium) — Billing toggle has no accessible name and no group semantics: PricingView.vue:55-58: <label class="switch"><input type="checkbox" v-model="isAnnual"/><span class="slider"/></label>. The label wraps only the slider, 'Monthly'/'Annual' are separate sibling spans, so the checkbox has no accessible name; the input is width:…
- **pricing-11** `pricing` class A (medium) — Comparison check marks are white glyphs, not green icons (undefined colour token): PricingView.vue:278-281 colours .check with var(--sc-success), which is not defined in tokens.css, so the colour falls back to the inherited #f4f6fb: the dom shows td.check colour rgb(244,246,251), 16/700, glyph '✓'. There is no accent-numeric cell style at a…
- **pricing-13** `pricing` class A (high) — Muted text on the pricing page fails AA where Figma's muted ink passes: The build uses --sc-text-muted #6b7383 (and card hex values) for the same roles: subline 'Transparent pricing with no hidden fees.' 20px 4.08:1; '/ forever' and '/ month' 15px #717d93 on the card 4.39:1; the six comparison dashes 16px 3.79:1 on --sc-surface; …
- **pricing-25** `pricing` class A (high) — Tokens referenced by these views are undefined, and --sc-text-muted fails AA: Views reference var(--sc-success) (PricingView.vue:279, check marks) and var(--sc-surface-alt) (DownloadView.vue:214, 307); neither exists in tokens.css, so they silently fall back (white checks; the Download requirements band has no fill). --sc-text-muted #6…
- **features-08** `features` class A (high) — Small text on the features page fails AA (muted ink on dark and elevated fills): Mock window titles 12px/400 --sc-text-muted on --sc-elevated 3.45:1 (x5: 'Audience Output · 4K 60fps', 'Scripture Search...', 'Service Run Sheet...', 'Stage Monitor Output', 'NDI Broadcast Feed...', 'Whisper AI...'); badge 'CAPABILITIES DEEP DIVE' 11/600 3.38…
- **download-11** `download` class A (high) — Muted text on the download page fails AA: --sc-text-muted #6b7383 is used for: hero line 20px (4.08:1), 'Windows 10 / 11 (64-bit)' and 'macOS 11.0 or later...' 16px (3.79:1), mobile paragraph 17.6px (4.08:1), store note 15px (4.08:1), 'Mobile App Mockup' 16/700 (4.08:1), three install-step bodies 16p…
- **about-05** `about` class A (high) — Small text on the about page fails AA: Badge 'Our Story & Mission' 11/600 3.38:1; footer copyright 14px 3.79:1. Required 4.5:1.
- **contact-12** `contact` class A (medium) — Form states and ARIA below the gap-fill spec: Spec items not built: the form has no aria-label='Contact us'; no aria-required on required fields (FormField sets only aria-invalid/aria-describedby for errors); the success card has no aria-live='polite' region; the textarea has no aria-label and its counte…
- **contact-13** `contact` class A (medium) — Placeholder and counter text fail AA (muted ink in the wrong role): ::placeholder uses --sc-text-muted #6b7383 on --sc-elevated #1c1f28 = 3.45:1 at 15px (FormField.vue:158-160); the '0/2000' counter 12px #6b7383 on #14161d = 3.79:1.
- **support-03** `support` class A (medium) — Search placeholder uses the browser default grey and fails AA; focus is a 1px border change only: No ::placeholder rule, so the default rgb(117,117,117) on #14161d = 3.92:1. :focus sets outline none and only changes border-color (SupportView.vue:177-180).
- **support-10** `support` class A (medium) — Muted ink below AA on counts and article meta: 'N articles' 12/600 --sc-primary on #14161d = 3.83:1; 'Category · 2 min read' 13px --sc-text-muted #6b7383 on #14161d = 3.79:1 (.article-meta SupportView.vue:258-261).
- **docs-07** `docs` class A (medium) — Sidebar title and breadcrumb use the muted ink below AA: 'DOCUMENTATION' sidebar title 14/700 and the 'Docs' breadcrumb 13px use --sc-text-muted #6b7383 on #14161d = 3.79:1 (DocsView.vue:91-99, 139-143).
- **changelog-06** `changelog` class A (low) — Release date uses the muted ink below AA: .release-date 13px --sc-text-muted #6b7383 on --sc-base #0b0d12 = 4.08:1 (ChangelogView.vue:136-139).
- **blog-07** `blog` class A (medium) — Meta text, 'Read →' links and badges below AA: '1 Oct 2026 · 2 min read' 13px --sc-text-muted #6b7383 on #14161d = 3.79:1; 'Read →' 13/600 --sc-primary 3.83:1; 'SelahCue Journal' badge 11/600 3.38:1; footer copyright 3.79:1 (BlogView.vue:72, 85-86).
- **careers-02** `careers` class A (medium) — Eyebrow pill style (UiBadge) - weight, tracking, padding, fill and ink: UiBadge variant='featured' size='sm' (CareersView.vue:16): 11px/600, letter-spacing 0.55px (0.05em), padding 4px 8px, height 26.5, fill #201f3a (accent-soft), ink #6e5cf0 = 3.38:1 (fails AA). Same component and same values appear in the hero of every page in …
- **careers-05** `careers` class A (high) — Role meta line fails AA (muted ink on surface): src/views/CareersView.vue:82 .role-meta: 13px/400, --sc-text-muted #6b7383 on the row fill #14161d = 3.79:1, on all three rows.
- **careers-06** `careers` class A (low) — Apply links have identical names with no role context: Three links named 'Apply Now →' (CareersView.vue:56). Nothing ties each link to its role title: the title is an h3 sibling in the row div, not an ancestor list item, label or description.
- **affiliates-09** `affiliates` class A (low) — FAQ panels: collapsed answers stay in the accessibility tree; no aria-controls; icon not hidden: FaqAccordion.vue: each question is a native button with aria-expanded (good, keyboard Enter/Space work), but the answer wrapper only collapses by grid-template-rows 0fr, so collapsed answers are still readable by assistive tech and find-in-page; no aria-contr…
- **affiliates-10** `affiliates` class D (high) — Interactive earnings calculator is build-only; Figma draws a static 'Earnings example': AffiliatesView.vue:64-97 and :125-140: a 700-wide card 'Estimate Your Earnings' with a range slider (1-100 'Referred Active Churches', default 10) and two result boxes ('$38/mo', '$456/yr') computed as churches x 3.8 (line 11, the hard-coded '20% of $19/mo').…
- **shared-chrome-20** `shared-chrome` class A (high) — Footer copyright fails AA: --sc-text-muted on --sc-surface is 3.79:1 at 14px (Figma's equivalent is 7.5:1): Footer.vue:264-268 .copyright color var(--sc-text-muted) #6b7383 on --sc-surface #14161d, 14px/400: 3.79:1 against the required 4.5:1.
- **shared-chrome-21** `shared-chrome` class A (high) — --sc-text-muted (#6b7383) fails AA for small text on every surface it is used on; 40+ consumers: tokens.css:13 --sc-text-muted #6b7383 = 4.08:1 on --sc-base, 3.79:1 on --sc-surface, 3.45:1 on --sc-elevated. Consumers beyond the footer and shell: FormField.vue (4 rules), DataTable.vue (4), Toast.vue:102, AdminShell.vue (2), auth.css:110, and 39 sites in v…
- **shared-chrome-30** `shared-chrome` class A (medium) — UiButton's focus ring is a box-shadow with outline:none, so it disappears in forced-colors (Windows High Contrast) mode: UiButton.vue:66 outline: none and :72-74 box-shadow 0 0 0 2px var(--sc-base), 0 0 0 4px var(--sc-primary). The look matches the spec on screen (2px gap + 2px ring, 4.1:1 against --sc-base, 3.8:1 against --sc-surface), but box-shadow is removed in forced-color…
- **shared-chrome-31** `shared-chrome` class D (medium) — Hover state is not drawn and the specified direction fails AA: UiButton primary hover is 3.78:1, the nav CTA hover darkens: UiButton.vue:104-106 primary hover --sc-primary-hover #7e6eff with white 15-16px/600 label = 3.78:1 (resting #6e5cf0 is 4.72:1). Navbar.vue:436-438 nav CTA hover goes DARKER (#4f5ec7, 5.59:1), the opposite direction, so the two primaries behave differently. G…
- **shared-chrome-33** `shared-chrome` class D (medium) — Every public page shares one document title: index.html:6 sets 'SelahCue — Church presentation, reengineered' and only /privacy, /terms and the article detail pages change it (lib/legal, lib/useDocumentMeta). Home, Features, Pricing, Download, About, Contact, Support, Docs, Changelog, Blog, Careers, Sig…
- **shared-chrome-34** `shared-chrome` class A (medium) — Route-loading fallback 'Loading...' fails AA (--sc-text-muted on --sc-base, 4.08:1 at 19px): App.vue:49-56 .loading color var(--sc-text-muted) #6b7383 on --sc-base #0b0d12, 1.2rem (19.2px) at weight 400: 4.08:1, and it is not large text (needs 24px, or 18.66px bold). It is plain text with no status role.

## Devices API check (for the backend ticket)

- **api-01** (missing) List the signed-in customer's devices: name, platform, app version, status (ACTIVE only for the list), over a customer session on /graphql/account. Evidence: implementation/api/selahcue_api/graphql/account_schema.py:148-153 - AccountQuery exposes only account_viewer (surface, actor_id, org_id; type at :33-37). Data exists in the DB: apps/devices/models.py:14-43 (display_name, platform, app_version, status). AUTH-LANDING-PAGES-HANDOFF 10.4: 'There is no devices query.'. Owner: Kenji (backend).
- **api-02** (missing) Per-device last-seen timestamp for the 'Last seen ...' text and recency dot. Evidence: apps/devices/models.py:14-43 - Device has no last_seen_at; apps/devices/services.py:587-617 authenticate_device_token is read-only; only CustomerSession has last_seen_at (apps/accounts/models.py:158) and that is a browser login, not a device. DeviceToken.issued_at (models.py:80) is a token issue, not a sighting (handoff 10.4).. Owner: Kenji (backend).
- **api-03** (missing) 'This device' flag for the row matching the install the user is on. Evidence: No field or mechanism: customer sessions (apps/accounts) and device tokens (apps/devices) are unrelated principals, and the browser has no device fingerprint. Handoff 10.4 lists 'a flag for this device' as needed; the web page cannot derive it. Needs a product decision before any API work.. Owner: Kenji (backend) with product.
- **api-04** (partial) The plan's device limit and the used count, readable by a customer session (meter, pill, limit-reached state). Evidence: Values exist but not for a customer session: AppLicenseKey.device_limit (apps/license_keys/models.py:50); active count + limit returned by refresh_license as instances_used / instances_limit (apps/devices/services.py:627-645) over device-token REST POST /v1/license:refresh (platform/urls.py), and in the signed manifest (apps/entitlements/services.py:150-157); staff-only via admin GraphQL (graphql/admin_schema.py:62,102,145). Nothing on /graphql/account. Note an org-level CustomerOrg.device_limi…. Owner: Kenji (backend).
- **api-05** (missing) Deactivate a device (session-authed, Administrator only): set Device.status = REVOKED, revoke its DeviceTokens, audit, free the slot. Evidence: No mutation in AccountMutation (graphql/account_schema.py:157-282) and no code sets DeviceStatus.REVOKED (grep of apps/devices: only DeviceTokenStatus.REVOKED in services.py:239-240 and tasks.py:49-59). _assert_device_activatable treats a revoked device as terminal (services.py:149-153), so re-activating a restored machine is a further decision. Handoff 10.5. Authz precedent: require_customer_role(ADMIN) at services.py:566.. Owner: Kenji (backend).
- **api-06** (partial) Over-limit signal (used > limit) for the D6 banner, pill and 'Deactivate N' count, plus a way for the limit to actually drop after a downgrade. Evidence: Policy is decided and partly enforced (Platform PRD FR-516/FR-550, DEC-009; activation refused at services.py:437-439; re-mint rule _remint_is_within_plan_allowance services.py:271-312). The signal is derivable once api-01 and api-04 exist (used > limit), but nothing exposes it, and device_limit is written only at issuance because FR-516's write-back is not built (apps/catalogue/models.py:30-33; apps/entitlements/services.py:150-156), so D6 is reachable only through a staff-issued key with a lo…. Owner: Kenji (backend).
- **api-07** (missing) Viewer role (ADMIN vs MEMBER) so the UI can hide Deactivate for read-only users; also the account header fields (org display name, email, plan label). Evidence: AccountViewer = surface, actor_id, org_id only (graphql/account_schema.py:33-37, :148-153; mirrored by ACCOUNT_VIEWER in marketing/src/lib/api/account.ts). Role enum exists (apps/accounts/models.py:59-60) but is not returned; login returns role once (LoginPayload.role) and the web client keeps it only as a localStorage hint.. Owner: Kenji (backend).
- **api-08** (missing) Account page data: subscription (plan, cycle, price, next payment), payment method, invoices + PDF download. Evidence: apps/billing contains only migrations/__init__.py; billing webhook is billing_webhook_not_implemented (platform/views.py:421-422); no customer-session query for any of it. Billing integration is a stated non-goal until D1/D2 are decided (Platform PRD NG-P6); refund policy FR-536 open.. Owner: Kenji (backend) after owner pricing decision.
- **api-09** (partial) License display: the key in a form the page may show (masked) for the signed-in org. Evidence: AppLicenseKey.masked_key / key_prefix / key_suffix exist (apps/license_keys/models.py:40-43, services.py:97-100) but no customer-session query returns them; the full key is show-once at issuance (graphql/admin_schema.py:243 full_key). A Copy-key control cannot work (account-20).. Owner: Kenji (backend) with product/security.
- **api-10** (missing) Bible entitlement list (licensed translations granted, status, sizes, sync/expiry). Evidence: No model, field or query: grep -i 'bible|translation' in selahcue_api finds only graphql/redaction.py and apps/catalogue/__init__.py. PRD CON-3: licensed translations are later (FR-034, R4).. Owner: Kenji (backend) - not before licensed translations are scoped.

## Defects found that are not fidelity items

- **bug-01** (sign-out-bug) Account page 'Sign Out' never signs out - it is a link to /signin. Evidence: src/views/AccountView.vue:136 `<UiButton variant="outline" size="sm" to="/signin">Sign Out</UiButton>`; UiButton renders `to` as a router-link (src/lib/ui/buttonElement.ts:31). AccountView.vue imports nothing from lib/auth (grep signOut|sessionStore: no match). The real sign-out is Navbar.vue:34-70 `handleSignOut` -> sessionStore.ts:137 `signOut()` -> logout mutation (account_schema.py:222-229 re…. Fix: Replace the link with a <button> that runs the same sign-out as the navbar: extract handleSignOut (pending flag, SIGN_OUT_FAILED role="alert" message, router.push('/') with the window.location.assign('/') fallback, Navbar.vue:34-70) into a shared composable and call it from Navbar and the account header; label 'Sign out'; do not clear local state unless the mutation succeeded. Ticket: 17tnw2b2cbr.
- **bug-02** (account) Account tabs expose no selected state to assistive technology. Evidence: src/views/AccountView.vue:150-160: six <button class="tab-btn"> with `active` as a CSS class only; no aria-current, aria-selected or role="tab". A screen-reader user cannot tell which section is showing. Moot if account-01 (sidebar with aria-current="page") is built.. Fix: Until the sidebar replaces the tabs: aria-current="true" on the active button. Ticket: 17tnw2b2cf2.
- **bug-03** (account) Mock actions report success as if real; several buttons are dead. Evidence: src/views/AccountView.vue: copyLicenseKey toasts 'License key copied to clipboard!' without awaiting or catching navigator.clipboard.writeText and copies a hard-coded key (66-69); confirmDeactivateDevice only filters a local array and toasts 'Deactivated "X" successfully' (81-89) - no request is made; confirmCancelSubscription flips a local flag and toasts 'Subscription cancelled. Pro access ends…. Fix: Until each API exists, disable the control with an honest 'Not available yet' state or remove it; never toast success for an action that did not happen. When wired, await the mutation and report its real outcome. Ticket: 17tnw2b2cf2.
- **bug-04** (account) Existing Deactivate dialog tells the user the device 'will lose access to Pro features'; ConfirmDialog has no focus management. Evidence: src/views/AccountView.vue:412-420 copy 'Are you sure you want to deactivate "{name}"? It will lose access to Pro features.' contradicts AUTH-LANDING-PAGES-HANDOFF 1 (never imply blocking of live presentation) and D2's copy (8.4); its confirm button is 'secondary' grey (ConfirmDialog.vue variant 'warning'). components/ConfirmDialog.vue has no focus trap, no initial focus on the safe action and no …. Fix: Use the D2 copy (devices-d2-01) and add focus trap / initial focus on 'Keep active' / aria-describedby to ConfirmDialog; also fixes the Cancel-subscription dialog. Ticket: 17tnw2b2cf2.
- **bug-05** (account) Hard-coded customer identity, key, devices and invoices are shown as the signed-in user's own data. Evidence: src/views/AccountView.vue:42-74,97-101,117-120 (user, subscription, licenseKey, devices, bibles, invoices refs). Every visitor with a session sees 'Grace Community Church / Sarah Jenkins' and a '$15/month' plan; accountViewer returns only org_id (account_schema.py:33-37). Tracked by 17tnw2b0x3h ('Account mock data'); recorded here because it is a mock presented as real, not a styling difference.. Fix: Render only API-backed values; show neutral loading/empty states for the rest (see account-17..20). Ticket: 17tnw2b2cf2.
- **account-bug-06** (account) Heading levels skip on Account: h2 jumps to h4 for the Bible translations. Evidence: account.blink.dom.json: h2 then h4 'New International Version (NIV)' (y 1275); same class of defect QA found on five other pages (Quinn Q-1). Fix: Make the entitlement titles h3 so the outline never skips a level; a code accessibility defect independent of Figma Ticket: 17tnw2b2cf2.
- **home-bug-01** (home) Heading levels skip on Home: h2 jumps to h4 for the output cards and the testimonial names. Evidence: home.blink.dom.json: h2 then h4 'Audience - Main' (y 2871) and h4 'Sarah Jenkins' (y 5213); found by QA (Quinn Q-1) and re-measured here. Fix: Make those headings h3 (or plain strong text where they are not section headings) so the outline never skips a level; a code accessibility defect independent of Figma Ticket: 17tnw2b2cex.
- **pricing-bug-01** (core) Heading levels skip on Pricing: h1 jumps to h3 for the plan names. Evidence: pricing.blink.dom.json heading sequence 1 3 3 3 2 2 3 3 3 3: the plan-name headings (y 424) are h3 directly under the h1; found by QA (Quinn Q-1) and re-measured here. Fix: Make the plan names h2 (or add a visually hidden h2 'Plans' above them) so the outline never skips a level; this is a code accessibility defect independent of Figma, which draws no heading levels Ticket: 17tnw2b2cey.
- **download-bug-01** (core) Heading levels skip on Download: h2 jumps to h4 for the install steps. Evidence: download.blink.dom.json heading sequence 1 2 2 2 3 3 2 2 4 4 4 3 3 3 3: 'Download the installer' (y 2360) is an h4 under an h2; found by QA (Quinn Q-1) and re-measured here. Fix: Make the install-step titles h3 so the outline never skips a level; a code accessibility defect independent of Figma Ticket: 17tnw2b2cey.
- **contact-bug-01** (secondary) Heading levels skip on Contact: h1 jumps to h4 for the contact-method cards. Evidence: contact.blink.dom.json heading sequence 1 4 4 4 2 3 3 3 3: 'Community & Discord' (y 412) is an h4 directly under the h1; found by QA (Quinn Q-1) and re-measured here. Fix: Make the contact-method card titles h2 or h3 to match the page outline so no level is skipped; a code accessibility defect independent of Figma Ticket: 17tnw2b2cez.
- **changelog-bug-01** (secondary) Heading levels skip on Changelog: h1 jumps to h3 for each change. Evidence: changelog.blink.dom.json heading sequence 1 3 3 3 3 3 3 3 3 3 3 3 3: 'Native NDI 5 Output Engine' (y 372) is an h3 directly under the h1; found by QA (Quinn Q-1) and re-measured here. Fix: Make the release version headings h2 and keep the per-change titles h3 so the outline never skips a level; a code accessibility defect independent of Figma Ticket: 17tnw2b2cez.

## Decisions that are not findings

- **How the side-by-side Artifact page is shared: DECIDED, team only (the owner, 2026-10-04).** It is shared with members of the organisation, not with the public, so an anonymous request returning 403 is the intended state, and the page may keep every finding's evidence, the devices API-gap table and the bug list (security review finding 2: resolved by decision). Owner action still open: set sharing from the page's Share menu (the author cannot) and have a team member open it; until then "opens for a member of the team who was not in the session" is not shown.

## Index: every page and state, its Figma node and its verdict

| surface | Figma node | route | verdict | A | B | C | D | E |
|---|---|---|---|---|---|---|---|---|
| Home (`home`) | `468:125` | `/` | diverges | 28 | 2 | 8 | 3 | 0 |
| Pricing (`pricing`) | `483:124` | `/pricing` | diverges | 14 | 0 | 4 | 2 | 0 |
| Features (`features`) | `485:124` | `/features` | diverges | 9 | 0 | 2 | 1 | 0 |
| Download (`download`) | `487:124` | `/download` | diverges | 7 | 2 | 3 | 0 | 0 |
| About (`about`) | `496:124` | `/about` | diverges | 6 | 0 | 1 | 0 | 0 |
| Contact (`contact`) | `497:124` | `/contact` | diverges | 7 | 2 | 3 | 2 | 0 |
| Support (Help Center) (`support`) | `498:124` | `/support` | diverges | 6 | 1 | 3 | 1 | 0 |
| Documentation (`docs`) | `499:124` | `/docs` | diverges | 5 | 0 | 2 | 2 | 0 |
| Changelog (`changelog`) | `501:124` | `/changelog` | diverges | 4 | 0 | 2 | 0 | 0 |
| Blog (`blog`) | `502:124` | `/blog` | diverges | 5 | 1 | 0 | 1 | 0 |
| Careers (`careers`) | `503:124` | `/careers` | diverges | 6 | 0 | 2 | 1 | 0 |
| Privacy Policy (`privacy`) | `504:124` | `/privacy` | diverges | 4 | 5 | 1 | 0 | 0 |
| Terms of Service (`terms`) | `504:203` | `/terms` | diverges | 5 | 5 | 1 | 0 | 0 |
| Sign in (`signin`) | `505:124` | `/signin` | diverges | 8 | 2 | 2 | 2 | 0 |
| Account dashboard (`account`) | `506:124` | `/account` | diverges | 14 | 2 | 7 | 8 | 0 |
| Affiliate program (`affiliates`) | `541:124` | `/affiliates` | diverges | 9 | 0 | 4 | 1 | 0 |
| V1 Verifying (`verify-v1`) | `743:125` | `/verify?token=SC-TESTTOKEN-verify` | diverges | 2 | 0 | 0 | 1 | 0 |
| V2 Verified (`verify-v2`) | `743:139` | `/verify?token=SC-TESTTOKEN-verify` | diverges | 1 | 1 | 0 | 1 | 0 |
| V3 Link no longer valid (`verify-v3`) | `746:124` | `/verify?token=SC-TESTTOKEN-verify` | diverges | 1 | 0 | 0 | 1 | 0 |
| V4 Link expired (24h) (`verify-v4`) | `746:148` | `/verify?token=SC-TESTTOKEN-verify` | not-rendered-by-design | 0 | 1 | 0 | 0 | 0 |
| V5 New link sent (`verify-v5`) | `746:172` | `/verify?token=SC-TESTTOKEN-verify` | diverges | 2 | 0 | 0 | 0 | 0 |
| V6 No verification link (`verify-v6`) | `747:124` | `/verify` | diverges | 1 | 0 | 0 | 0 | 0 |
| R1 Choose a new password (`reset-r1`) | `747:143` | `/reset?token=SC-TESTTOKEN-reset` | diverges | 3 | 0 | 0 | 0 | 0 |
| R2 Validation errors (`reset-r2`) | `747:173` | `/reset?token=SC-TESTTOKEN-reset` | diverges | 4 | 0 | 0 | 0 | 0 |
| R3 Updating password (`reset-r3`) | `749:124` | `/reset?token=SC-TESTTOKEN-reset` | diverges | 2 | 0 | 0 | 0 | 0 |
| R4 Link no longer valid (`reset-r4`) | `749:150` | `/reset?token=SC-TESTTOKEN-reset` | diverges | 1 | 0 | 0 | 1 | 0 |
| R5 Link expired (1h) (`reset-r5`) | `749:174` | `/reset?token=SC-TESTTOKEN-reset` | not-rendered-by-design | 0 | 1 | 0 | 0 | 0 |
| R6 Password updated (`reset-r6`) | `749:198` | `/reset?token=SC-TESTTOKEN-reset` | diverges | 1 | 0 | 0 | 0 | 0 |
| R7 Server error (`reset-r7`) | `749:217` | `/reset?token=SC-TESTTOKEN-reset` | diverges | 1 | 0 | 0 | 1 | 0 |
| D1 Populated (3 of 5) (`devices-d1`) | `753:124` | `/account/devices` | not-built | 0 | 0 | 0 | 0 | 2 |
| D2 Deactivate confirm (`devices-d2`) | `754:124` | `/account/devices` | not-built | 0 | 0 | 0 | 0 | 1 |
| D3 All slots in use (5 of 5) (`devices-d3`) | `754:257` | `/account/devices` | not-built | 0 | 0 | 0 | 0 | 2 |
| D4 No devices (0 of 5) (`devices-d4`) | `755:124` | `/account/devices` | not-built | 0 | 0 | 0 | 0 | 1 |
| D5 Could not load devices (`devices-d5`) | `755:256` | `/account/devices` | not-built | 0 | 0 | 0 | 0 | 1 |
| D6 Over the plan limit (5 of 3) (`devices-d6`) | `755:385` | `/account/devices` | not-built | 0 | 0 | 0 | 0 | 1 |

Counts here are per surface and exclude duplicates. They include findings that are fixed in the shared chrome or shared components tickets, which is why the per-ticket totals above differ.

## Surfaces

### shared-chrome — `shared-chrome` (Figma `468:126, 479:133`)

Verdict: **diverges** · area: shared-chrome · route: `—`

The shared chrome is recognisably the same product but not the same layout: the nav is 10px short, inset 76px a side and uses a pill CTA with a smaller logo, the footer has the wrong link columns (one dead link), wrong layout and wrong ink, and every button is a pill where Figma uses 10-12px rectangles. The biggest problems are two dead links ('How it works' in the nav, /how-it-works in the footer), the footer link inventory, and two AA contrast failures (--sc-text-muted in the footer and Loading text), plus tokens that pages do not use (gutters, section padding, type ramp).

- **shared-chrome-01** · class **A** · medium · shared · nav — Nav bar is 69px tall, Figma draws 79px
  - Figma: Nav frame 468:126 is 1440x79: padding 20/48/20/48 around a 39px CTA, with a 1px #2b323d bottom stroke inside the frame. All 14 page frames carry an identical Nav (485:125, 483:125, 487:125, 496:125, 506:125 ...), and the first section of every page starts at y=79.
  - Build: header.navbar-header measures 1440x69: .navbar-container height 68px (Navbar.vue:310) plus 1px border-bottom (Navbar.vue:294). tokens.css:66 --nav-height is 68px, which is itself 1px short of the real 69. Every page's content therefore starts 10px higher than in Figma (build y=69 vs Figma y=79), which shows up as a -10px offset in every page's style diff.
  - Evidence: home.blink.dom.json items[0] header h=69. Figma extract 468:126 h=79. use_figma scan of all 15 page frames: every Nav child h=79, pad [20,48,20,48].
  - Fix: Make the header 79px: .navbar-container height 78px (+1px border) or padding 20px + 39px CTA. Set --nav-height: 79px in tokens.css:66; AdminShell, AffiliateShell, anchors.css, LegalPage and DocsArticleView all read the token, so they follow. Land this first: the page tickets' dy figures were measured against a 69px nav.
  - Linked: 17tnw2b2cev
- **shared-chrome-02** · class **A** · medium · shared · nav — Nav content is inset 124px by a 1240px max-width, Figma runs the bar at 48px gutters
  - Figma: Nav content spans the full 1440 frame: logo (494:124) at x=48, CTA (468:138) right edge at x=1392. Gutter 48px. (The page body uses 96px gutters; only the nav is 48.)
  - Build: Navbar.vue:305-309 .navbar-container max-width 1240px, margin 0 auto, padding 0 24px, so at 1440 the logo is at x=124 and the CTA right edge at x=1316 (76px more inset each side than Figma).
  - Evidence: vp_style_diff --figma chrome-nav.json: SelahCue x +70.0 (figma 88, build 158); Features x +71.5; How it works x +70.6; Pricing x +70.5; Download x +70.2; Sign in x -84.0; Download free x -76.6. dom brand-logo x=124. Slice nav-home.png.
  - Fix: Drop the 1240px max-width cap (or raise it above 1440) and set padding-inline: 48px from 1200px up. The existing tablet/mobile steps (24px/20px) can stay. Result: lockup starts at x=48 and the CTA ends at x=1392 at 1440.
  - Linked: 17tnw2b2cev
- **shared-chrome-03** · class **A** · medium · shared · nav — Brand lockup: mark renders about 15px instead of 32px (nav) and 19px instead of 28px (footer); gaps, wordmark and alt text differ
  - Figma: Nav lockup 468:128: logo 494:124 32x32 (tight-cropped mark), gap 8, wordmark 19/Bold #eef1f6 with 0 tracking; lockup-to-links gap 40 (468:127). Footer lockup 479:136: logo 494:128 28x28, gap 8, wordmark 18/Bold #eef1f6. Handoff section 7: 32px nav / 28px footer, and the source PNG has ~33% transparent padding so either trim it or size the img up to compensate.
  - Build: Navbar.vue:333-336 img.brand-logo height 24px (a 24x24 box of the untrimmed 1254x1254 PNG whose mark bbox is 760x835, so the visible mark is about 15x16px), brand gap 10 (:326), wordmark 19/700 in #ffffff with -0.01em tracking (:338-343), lockup-to-links gap 44 (:320). Footer.vue:166-177 img.logo 32px untrimmed (visible mark about 19x21px), gap 12, wordmark 20/700 -0.02em in --sc-text. Both img carry alt='SelahCue Logo' inside a link that also contains the visible wordmark, so it is announced t…
  - Evidence: dom: nav img.brand-logo w=24 h=24 x=124; footer img.logo w=32 h=32; footer wordmark fs 20px ls -0.4px. marketing/public/selahcue-logo.png alpha bbox (247,215,1007,1050) of 1254x1254. vp_style_diff: SelahCue colour figma #eef1f6 vs build #ffffff. Slice nav-home.png shows the mark visibly smaller in …
  - Fix: Ship a tight-cropped logo (crop to the alpha bbox on a square canvas) or scale the img by 1/0.67 with matching negative margin, so the visible mark is 32px in the nav and 28px in the footer. Gaps 8/8, lockup-to-links 40, footer wordmark 18px with 0 tracking, nav and footer wordmark colour var(--sc-text). Give the img alt='' aria-hidden='true' (the wordmark names the link).
  - Linked: 17tnw2b2cev
- **shared-chrome-04** · class **A** · medium · shared · nav — Active route is Medium/white in the build, Figma is Semi Bold in text/primary
  - Figma: Features frame 485:125 draws 'Features' as Inter Semi Bold 14 #eef1f6 (text/primary); Pricing (483:125) and Download (487:125) do the same for their own link; inactive links are Medium 14 #9aa4b2. Handoff section 1: the current route is highlighted with text/primary + Semi Bold.
  - Build: Navbar.vue:362-365 .nav-item:hover, .nav-item.active only sets color:#ffffff, so the active link stays weight 500 (the highlight is colour-only and pure white, not --sc-text).
  - Evidence: features.blink.dom.json: cls 'active router-link-exact-active nav-item' fw '500' color rgb(255,255,255); same on pricing and download captures. Figma scan: 485:125 Features 'Semi Bold' #eef1f6.
  - Fix: .nav-item.active { color: var(--sc-text); font-weight: 600; } and keep the hover rule colour-only. Accept the ~1px link shift the Figma frames themselves show (How it works x=305 vs 306 on Features).
  - Linked: 17tnw2b2cev
- **shared-chrome-05** · class **A** · medium · shared · nav — 'Sign in' link uses the muted ink and a 24px gap, Figma uses text/primary and 18px; wordmark and active ink are pure white
  - Figma: Right group 468:136: 'Sign in' Inter Medium 14 #eef1f6 (text/primary) at x=1192, 18px gap to the CTA. Wordmark 19/Bold and all emphasised nav ink are #eef1f6. Handoff section 3: pure #ffffff is reserved for text/icons on coloured fills.
  - Build: Navbar.vue:371 .right-group gap 24px; :374-383 .signin-btn colour #9aa4b2 (the muted role: a quiet link where Figma has the bright one); .signout-btn the same (:391-402); wordmark colour #ffffff (:341); hover and active #ffffff.
  - Evidence: vp_style_diff: Sign in colour figma #eef1f6 vs build #9aa4b2; SelahCue colour figma #eef1f6 vs build #ffffff. dom features: signin-btn colour rgb(154,164,178), x=1108, CTA x=1177 (gap 24).
  - Fix: .signin-btn and .signout-btn: color var(--sc-text), hover keeps it; .right-group gap 18px; .brand-wordmark and the active/hover ink: var(--sc-text) instead of #ffffff.
  - Linked: 17tnw2b2cev
- **shared-chrome-06** · class **A** · medium · shared · nav — 'Download free' nav CTA is a 999px pill at weight 600, Figma is a 10px-radius rectangle at weight 700
  - Figma: Btn/Download 468:138 (cloned on all 14 pages): 136x39, radius 10, fill #5b6bd6 (accent/brand), padding 11/18, label Inter Bold 14 white (#ffffff).
  - Build: Navbar.vue:422-434 .download-cta: 138.6x39, border-radius 999px, padding 9px 20px, font-weight 600, background literal #5b6bd6, hover #4f5ec7 (:437). It is a hand-rolled button, not UiButton, so UiButton changes will not reach it.
  - Evidence: vp_style_diff boxes: Btn/Download 468:138 radius figma 10 vs build 999.0; text 'Download free' font-weight figma 700 vs build 600. dom download-cta radius 999px pad '9px 20px 9px 20px' fw 600 w 138.6.
  - Fix: border-radius: 10px; padding: 11px 18px; font-weight: 700; background var(--sc-primary) (the 2.2 mapping of accent/brand; see the tokens finding on the three brand spellings). Hover value is a decision (ui-button hover finding). Preferably render it through UiButton (primary, compact) once the ui-button findings land so the nav stops carrying a private copy of the button.
  - Linked: 17tnw2b2cev
- **shared-chrome-07** · class **A** · high · shared · nav — Nav 'How it works' is a dead link on every page: nothing carries id='how-it-works'
  - Figma: The nav draws 'How it works' as the second link on every page (frame 468:131, x=305). Handoff section 1: 'How it works' is an in-page anchor on Home (Home section 6, node 476:124).
  - Build: Navbar.vue:191 (desktop) and :261 (mobile sheet) render <a href='#how-it-works'>, but no element in the app has that id: HomeView.vue:263-264 <section class='steps-section'> has no id, and grep finds the string only in the navbar, the footer and a comment in router/scroll.ts:13. On Home the click changes the hash and scrolls nowhere; on every other page it only appends #how-it-works to the current URL (the href is not rooted at '/').
  - Evidence: grep -rn 'how-it-works' src: Navbar.vue:191,261; Footer.vue:25; router/scroll.ts:13 (comment). dom: nav-item href '#how-it-works' on features, pricing, download, about, account captures.
  - Fix: Navbar.vue:191 and :261 -> <router-link :to="{ path: '/', hash: '#how-it-works' }" class='nav-item'>. Add id='how-it-works' to HomeView's steps section in the Home ticket (with scroll-margin-top: var(--sc-anchor-offset)), and add 'home' to ANCHORED_ROUTES in router/scroll.ts so the heading clears the sticky bar.
  - Linked: 17tnw2b2cev
- **shared-chrome-08** · class **A** · low · shared · nav — Desktop nav links, brand and CTA have no :focus-visible style, they fall back to the browser default ring
  - Figma: Figma draws no focus state; handoff section 5: focus-visible is a 2px accent/brand ring with a 2px offset, and section 6: every button/link needs that visible ring.
  - Build: Navbar.vue declares :focus-visible only for .mobile-toggle and .sheet-close (:458-462) and .mobile-link/.sheet-cta (:571, :622). .brand, .nav-item, .signin-btn, .signout-btn and .download-cta have no rule, so they show the UA default (Footer links and UiButton do use the 2px --sc-primary ring). main.css has no global a:focus-visible either.
  - Evidence: grep -n 'focus-visible' Navbar.vue: lines 458, 459, 571, 622 only; main.css: none; Footer.vue:227-233 has the 2px --sc-primary / 2px offset recipe.
  - Fix: Add a global default in main.css (a:focus-visible, button:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; border-radius: 6px }) so no component can forget it, and keep the existing component overrides.
  - Linked: 17tnw2b2cev
- **shared-chrome-09** · class **A** · low · shared · nav — Nav surface is a hard-coded #090a0f band with a dim 8% border, and the sticky blur state is only computed after a scroll event
  - Figma: The Nav frame has no fill (it sits on the page fill #0e1116 = bg/base, mapped --sc-base) and a 1px #2b323d bottom border (= --sc-border). Handoff section 5: sticky on scroll with a subtle bg/base blur + bottom border.
  - Build: Navbar.vue:289-302: position sticky OK, but background is the literal #090a0f (not a token and not --sc-base #0b0d12, so on every page except Home it is a visibly darker band over the page; HomeView.vue:376 hard-codes the same #090a0f for Home only), border-bottom rgba(255,255,255,0.08) = about #1d1e22 (Figma #2b323d), blur(16px) + 0.9 alpha only once scrollY>10. isScrolled is set only by the scroll listener (Navbar.vue:72-74; onMounted :163-168 never calls it), so a reload or hash jump into a …
  - Evidence: dom header bg rgb(9,10,15) vs body background --sc-base rgb(11,13,18); Figma extract 468:126 root.fill null, strokeBottom 1 #2b323d.
  - Fix: background: var(--sc-base); border-bottom: 1px solid var(--sc-border); scrolled state color-mix(in srgb, var(--sc-base) 90%, transparent) with the existing blur; call handleScroll() once in onMounted.
  - Linked: 17tnw2b2cev
- **shared-chrome-10** · class **B** · low · shared · nav — 44px touch-target floor on nav links, brand and (coarse pointer) CTA exceeds the drawn 17px/39px boxes
  - Figma: Figma text boxes for nav links are 17px tall and the CTA is 39px; no 44px hit areas are drawn.
  - Build: Navbar.vue:354, :377, :395 .nav-item/.signin-btn/.signout-btn min-height 44px; :330 .brand min-height 44px; :675-677 CTA min-height 44px on coarse pointers only; UiButton.vue:169-173 min-height 44px below 768px and on coarse pointers. The painted desktop sizes are unchanged (the hit area grows, the glyphs do not).
  - Evidence: dom: nav-item h=44 while text th=17; download-cta h=39 on a fine pointer.
  - Source: MARKETING-SITE-HANDOFF.md section 6 ('Touch targets: nav links and mobile CTAs >= 44 px tall').
- **shared-chrome-11** · class **D** · low · shared · nav — 'Active route underline' in handoff section 5 is not drawn in any frame and contradicts section 1
  - Figma: Features/Pricing/Download frames (485:125, 483:125, 487:125) draw the active link as Semi Bold text/primary with no underline or pill. Handoff section 1 says exactly that ('text/primary + Semi Bold').
  - Build: No underline in the build (.nav-item.active is colour-only), which agrees with the frames.
  - Evidence: Figma scan of the Nav subtree on the three top-nav pages: no stroke/line boxes besides the CTA; MARKETING-SITE-HANDOFF.md section 5 line 'active route underline' vs section 1 line 26-28.
  - Decision: Uma: should the active link also carry an underline? The frames and section 1 say no; section 5 says yes. Recommend: no underline (match the frames) and strike the phrase from section 5.
- **shared-chrome-12** · class **D** · medium · shared · nav — Signed-in nav state is not designed: the code swaps 'Sign in' for 'Account' + 'Sign out'
  - Figma: Only the signed-out nav is drawn, on every frame, including the Account frame 506:124 (its nav 506:125 shows 'Sign in' + 'Download free' even though Account is signed-in only). The Account frame has its own Sign out outline button (506:148, 92x41, r10).
  - Build: Navbar.vue:204-215 (isProbablySignedIn): 'Account' (router-link /account, same muted ink, no active style) and a 'Sign out' <button> (signOut() then router.push('/'), error banner 'We couldn't sign you out...') replace 'Sign in'; the 'Download free' CTA stays. /account therefore shows Sign out twice (nav and the page header).
  - Evidence: account.blink.dom.json (scenario signed-in): signin-btn 'Account' x=1018 and signout-btn 'Sign out' x=1098 in the header; Figma extract of 506:125 texts: Sign in, Download free.
  - Decision: Uma: draw the signed-in nav. Open points: Account link vs avatar/menu, whether Sign out lives in the nav or only on the Account page (it is drawn there at 506:148), whether 'Download free' stays for signed-in users, and the active treatment for Account. Until then the build keeps Account + Sign out.
- **shared-chrome-13** · class **C** · medium · shared · nav — 'Download free' CTA leads to a page where nothing downloads
  - Figma: 'Download free' (468:138, label 14/Bold) is the nav CTA on every page, and the same promise is the primary CTA in the hero (469:131), Pricing, Features and About bands.
  - Build: Navbar.vue:216 (and the mobile sheet :280) route 'Download free' to /download. DownloadView.vue:22-43 and :98-109 state 'No installer is served from this page yet' and render every download button disabled; implementation/api/selahcue_api/apps/downloads and billing contain only __init__/apps/migrations (no models, no endpoints). The label is identical to Figma, so the claim is already in the build.
  - Evidence: dom download capture: ui-button variant-primary size-md is-disabled x2; source reads above; ls selahcue_api/apps/downloads.
  - Decision: Owner: keep Figma's 'Download free' (honest /download state already explains the wait), or relabel the CTA (nav, hero, bands) to the honest action until the first signed installer ships? The relabel/removal is owned by 17tnw2b0x3h; this finding only records the nav instance.
  - Linked: 17tnw2b0x3h
- **shared-chrome-14** · class **A** · high · shared · footer — Footer link columns do not match Figma: wrong entries, wrong order, missing 'Setup guides' / 'NDI & streaming', a fourth Legal column
  - Figma: Footer 479:133 (identical on all 14 pages) draws three link columns: PRODUCT (Features, Pricing, Download, Changelog), RESOURCES (Documentation, Setup guides, NDI & streaming, Support), COMPANY (About, Blog, Contact, Careers, Affiliates). Privacy and Terms sit in the bottom bar (479:162) next to 'Windows · macOS'. Handoff section 1: 'NDI & streaming' points to Features, 'Setup guides' to Documentation, Company includes Affiliates.
  - Build: Footer.vue:18-53 builds FOUR columns: Product (Features, Pricing, Download, How it works), Resources (Documentation, Support, Blog, Changelog), Company (About, Careers, Contact, Affiliates), Legal (Privacy Policy, Terms of Service). Changelog moved to Resources, Blog moved to Resources, 'How it works' added, 'Setup guides' and 'NDI & streaming' absent, Company order differs, Legal is a column with longer labels instead of two short bottom-bar links, and there is no 'Windows · macOS' tag.
  - Evidence: vp_style_diff --figma chrome-footer.json: design-only copy 'Setup guides', 'NDI & streaming', 'Privacy', 'Terms', 'Windows · macOS'; dom footer link list (focus order): Features Pricing Download How it works / Documentation Support Blog Changelog / About Careers Contact Affiliates / Privacy Policy …
  - Fix: Footer.vue columns to Figma: Product = Features /features, Pricing /pricing, Download /download, Changelog /changelog. Resources = Documentation /docs, Setup guides /docs, NDI & streaming /features, Support /support. Company = About /about, Blog /blog, Contact /contact, Careers /careers, Affiliates /affiliates. Remove the Legal column; render Privacy /privacy and Terms /terms (13px, muted, gap 22) plus the 'Windows · macOS' text in the bottom bar's right group. Every target exists in router/index.ts. Keep 'Windows · macOS' exactly as drawn (it is product-backed); do not add Linux here, that i…
  - Linked: 17tnw2b2cev
- **shared-chrome-15** · class **A** · high · shared · footer — Footer 'How it works' links to /how-it-works, which has no route and renders the 404 page
  - Figma: Figma's Product column has no 'How it works' entry (Features, Pricing, Download, Changelog). Handoff section 1: every footer link must resolve to a real page.
  - Build: Footer.vue:25 { to: '/how-it-works', label: 'How it works' }. router/index.ts has no such path, so it falls to the catch-all NotFoundView ('We couldn't find that page'). The other 12 footer targets (/features /pricing /download /docs /support /blog /changelog /about /careers /contact /affiliates /privacy /terms) all resolve.
  - Evidence: grep -n 'how-it-works' router/index.ts router/articleRoutes.ts: no match; router/index.ts:88-92 catch-all; dom home: footer-link href '/how-it-works'.
  - Fix: Delete the entry (Figma has none) as part of the column rebuild above; Product's fourth entry becomes Changelog.
  - Linked: 17tnw2b2cev
- **shared-chrome-16** · class **A** · medium · shared · footer — Footer layout: 4 equal columns in a 1088px container, 80px top padding, 37px link pitch; Figma is 3 hugging columns at 96px gutters, 56px padding, 30px pitch
  - Figma: Footer 1440x358: fill #0e1116, padding 56/96/40/96, 1px #2b323d top stroke. Brand column 300 wide at x=96. Link columns hug their content with 64px gaps and end at x=1344 (PRODUCT x=973, RESOURCES x=1109, COMPANY x=1280). Link pitch 30 (17px line + 13 gap), heading to first link 28. 1px divider at y=261, 40px gap, 16px bottom row, 40px bottom padding.
  - Build: Footer.vue:136-190, 272-281: padding-top 80; .container (main.css:67-71 max-width 1280 border-box with --gutter 96) gives content x=176..1264 (1088 wide) instead of 96..1344 (1248); .links-grid is four equal 1fr tracks (112.8px, 24px gap) at x=741/878/1014/1151; link pitch 37 (21px line + 16 gap); .footer-top margin-bottom 64 and .footer-bottom padding 32/32; total height 405.5 vs 358.
  - Evidence: vp_style_diff footer: PRODUCT x -232.1 px (figma 973 vs build 740.9), RESOURCES x -231.3, COMPANY x -265.5; dom footer h=405.5, footer-link y 6770/6807/6844/6881 (pitch 37), brand logo x=176. Slice footer-home.png.
  - Fix: Inner width 1248 (96px gutters at >=1200). .links-grid -> display:flex; gap:64px; justify-content:flex-end with three hugging columns; padding-top 56; link gap 13px; 40px between the columns and the divider, 40px between divider and bottom row, 40px bottom padding. Tablet/mobile blocks stay as they are.
  - Linked: 17tnw2b2cev
- **shared-chrome-17** · class **A** · low · shared · footer — Footer is a lighter --sc-surface panel, Figma's footer is the page colour
  - Figma: Footer 479:133 fill #0e1116 = the page fill (bg/base, mapped --sc-base), separated from the page only by the 1px #2b323d top stroke (= --sc-border).
  - Build: Footer.vue:136-140 background var(--sc-surface) #14161d (the panel colour) with border-top var(--sc-border).
  - Evidence: dom footer bg rgb(20,22,29); Figma extract 479:133 root.fill #0e1116.
  - Fix: .footer { background: var(--sc-base); } border-top stays var(--sc-border).
  - Linked: 17tnw2b2cev
- **shared-chrome-18** · class **A** · medium · shared · footer — Footer type and ink: headings are bright sentence-case 15/600, links dim; Figma has muted 12px uppercase headings over bright links
  - Figma: Column headings 12/Bold, typed in capitals, +0.1px tracking, #9aa4b2 (muted). Links 14/Regular #eef1f6 (text/primary). Tagline 14/21 #9aa4b2 in a 300px box. Bottom row 13/Regular #9aa4b2. Wordmark 18/Bold #eef1f6. (The one muted link is Affiliates, #9aa4b2, read as an authoring slip.)
  - Build: Footer.vue:205-210 .column-title 15px/600 sentence case in --sc-text (#f4f6fb); :245-250 .footer-link 14px/400 --sc-text-secondary (#a7aebe), so the hierarchy is inverted (heading brighter than links); :179-183 tagline 15px/22.5 --sc-text-secondary; :264-268 copyright 14px; :171-177 wordmark 20px.
  - Evidence: vp_style_diff footer: PRODUCT / RESOURCES / COMPANY copy-case 'PRODUCT' vs 'Product', font-size figma 12px vs build 15.0px, font-weight 700 vs 600, colour #9aa4b2 vs #f4f6fb; Documentation, About, Blog, Contact, Changelog, Support, Careers colour figma #eef1f6 vs build #a7aebe; Affiliates colour~ #…
  - Fix: .column-title: font 700 12px/15px, letter-spacing 0.1px, text-transform uppercase, color var(--sc-text-secondary) (2.2 mapping of text/muted). .footer-link: color var(--sc-text) (text/primary), hover unchanged; keep Affiliates identical to its siblings (Uma to confirm Figma's muted Affiliates is a slip). Tagline 14px/21px var(--sc-text-secondary), max-width 300. Wordmark 18px, 0 tracking. Bottom row 13px.
  - Linked: 17tnw2b2cev
- **shared-chrome-19** · class **C** · medium · shared · footer — Footer tagline and legal line carry 'subscription-simple' and 'Cancel anytime', which the repo does not back
  - Figma: Tagline 'Church presentation, done right. Offline-first, subscription-simple, built for the moment that matters.' (479:135, 14/21) and legal line '© 2026 SelahCue · Works offline · Cancel anytime' (479:160), with 'Windows · macOS' on the right.
  - Build: The build shows neither claim and neither wording: Footer.vue:98 tagline 'Church presentation, reengineered', Footer.vue:129 '© 2026 SelahCue. All rights reserved.'
  - Evidence: Footer.vue:98,129; implementation/api/selahcue_api/apps/billing and apps/downloads hold no models or endpoints (no subscription, no cancel flow); MARKETING-SITE-HANDOFF.md section 8 lists the subscription tiers and billing terms (monthly/annual, cancel-anytime) as Assumed. 'Works offline' is backed…
  - Decision: Owner (binding rule: honest content wins): adopt Figma's layout and wording minus the unbacked parts, e.g. tagline 'Church presentation, done right. Offline-first, built for the moment that matters.' and legal line '© 2026 SelahCue · Works offline', plus the right-hand 'Windows · macOS'. Confirm the exact wording with product before it ships. 'Windows · macOS' stays as drawn.
- **shared-chrome-20** · class **A** · high · shared · footer · a11y — Footer copyright fails AA: --sc-text-muted on --sc-surface is 3.79:1 at 14px (Figma's equivalent is 7.5:1)
  - Figma: Footer legal line 13/Regular #9aa4b2 on #0e1116 = 7.5:1, passes AA.
  - Build: Footer.vue:264-268 .copyright color var(--sc-text-muted) #6b7383 on --sc-surface #14161d, 14px/400: 3.79:1 against the required 4.5:1.
  - Evidence: report.json contrast_survey: '© 2026 SelahCue. All rights reserved.' value 3.79 (required 4.5, AA-normal) on all 14 public-page captures (about, affiliates, blog, careers, changelog, contact, docs, download, features, home, pricing, privacy, support, terms). Computed: #9aa4b2 on #0e1116 = 7.50.
  - Fix: .copyright color var(--sc-text-secondary) (the AUTH-LANDING-PAGES-HANDOFF 2.2 mapping of Figma text/muted: 8.1:1 on --sc-surface, 8.7:1 on --sc-base).
  - Linked: 17tnw2b2cev
- **shared-chrome-21** · class **A** · high · shared · tokens · a11y — --sc-text-muted (#6b7383) fails AA for small text on every surface it is used on; 40+ consumers
  - Figma: Figma text/muted #9aa4b2: 7.5:1 on #0e1116, 7.2:1 on #14161d, 6.5:1 on #1c1f28 (passes everywhere). The 2.2 mapping sends text/muted to --sc-text-secondary, not --sc-text-muted.
  - Build: tokens.css:13 --sc-text-muted #6b7383 = 4.08:1 on --sc-base, 3.79:1 on --sc-surface, 3.45:1 on --sc-elevated. Consumers beyond the footer and shell: FormField.vue (4 rules), DataTable.vue (4), Toast.vue:102, AdminShell.vue (2), auth.css:110, and 39 sites in views/. The marketing legacy token --text-muted #9aa4b2 (tokens.css:43) passes.
  - Evidence: Computed from the hexes; report.json contrast_survey has 166 entries below 4.5:1 across the run (footer 3.79 on 14 pages, 'Back to Sign in' x10, table headers, '/ month' 4.39 ...). grep -rn 'sc-text-muted' src.
  - Fix: Pick one: (a) re-point small-text uses to var(--sc-text-secondary), which is the documented mapping of text/muted; or (b) raise the token itself so it clears 4.5:1 on --sc-elevated, e.g. #868ea0 (5.0 on elevated, 5.5 on surface, 5.9 on base). Either removes the footer and Loading instances in the same change; page tickets keep their own uses.
  - Linked: 17tnw2b2cev
- **shared-chrome-22** · class **A** · medium · shared · tokens — Gutter and content-width tokens are not what pages use: designed content is 96..1344 (1248 wide), pages render 150..1290 (1140 wide)
  - Figma: Home/Features/Pricing/About section frames: padding 96 left/right at 1440, widest content 1248 at x=96 (Home Features 472:124, Pricing 477:124, Final CTA 479:124, Footer 479:133; hero mock 1140 at x=150 is the one narrower block). Handoff section 3: 96px horizontal gutters.
  - Build: tokens.css:60 --gutter 96px is consumed only by main.css:67-71 .container (used by the footer) and three article views; every public view re-declares .container locally with --page-gutter 24px (tokens.css:64) and its own max-width: Home/About/Features/Support/Contact/Account/Blog 1140, Pricing/Download/Docs 1200, Careers 1000, Navbar 1240, legal 1120. At 1440 that puts content at x=150..1290 instead of 96..1344.
  - Evidence: grep -rn 'max-width: 1[0-9][0-9][0-9]px' src/views src/components; dom about cta-card x=150 w=1140; Figma scan: About 496:124 children widest 1248 at x=96.
  - Fix: Define one token (e.g. --content-max: 1248px, gutter 96 at >=1200 / 48 / 20) and one shared .container; page tickets then delete their local max-width/padding overrides. The footer and nav findings above depend on the same token.
  - Linked: 17tnw2b2cev
- **shared-chrome-23** · class **A** · medium · shared · tokens — Section padding token is 100px; Figma sections use 88-90px, and three overlapping section tokens exist
  - Figma: Home sections: Features 88/88, Reliability 90/90, Showcase 90/90, How it works 88/88, Pricing 90/90, Testimonials 90/90, FAQ 90/90, Final CTA 90/90 (frames 472:124 ... 479:124). Handoff section 3: ~88-90px vertical section padding.
  - Build: tokens.css:68 --section-pad: 100px (the one Home, Download and the mobile footer consume: 11 uses), :69 --section-pad-sm: 80px (11 uses), :70 --section-padding: 88px (the right value, consumed only by the unused .section class in main.css:73). --card-radius (16px, :71) and --grid-gap (24px, :73) have no consumers at all.
  - Evidence: grep -rn 'var(--section-pad' src: 22 uses of the 100/80 pair, 1 of --section-padding; by padding alone each Home section is 20-24px taller than its Figma frame (100 vs 88-90 top and bottom).
  - Fix: Set --section-pad to 90px (88px sections are within 2px), delete --section-padding, keep one small step for mobile; remove or start consuming --card-radius/--grid-gap (Figma card radii 14-18, grid gaps 20-28).
  - Linked: 17tnw2b2cev
- **shared-chrome-24** · class **A** · medium · shared · tokens — Type-scale tokens match the handoff ramp for Home but nothing consumes them; views hard-code 26-58px headings at weight 800
  - Figma: Handoff section 3 ramp (Inter): H1 60/64 Bold, H2 38-42 Bold, card title 18-21 Semi Bold, body 17-19, small 14-15, eyebrow 13 Bold with tracking. Measured across 14 Figma pages: H1 60/64 (Home) and 46-54 on sub-pages (Features 52/58, Download 52/58, Pricing 52/56, Contact 50/56, Support 48/54, Changelog 48/54, Docs 46/52, Affiliates 54/60); H2 38-42 (Home), 32-40 elsewhere; eyebrow 13/Bold +0.3px; all headings weight 700.
  - Build: tokens.css:51-57: --font-h1 700 60/64, --font-h2 700 42/48, --font-h3 600 21/28, --font-body 400 17/26, --font-small 400 15/22 agree with the ramp, but --font-eyebrow 700 13px/16px has no tracking (a font shorthand cannot carry it) and UiBadge.vue:35 renders eyebrows at 11px. Only BlogPostView.vue:154 uses --font-h1; the .font-h1/.font-h2/.font-h3/.font-body/.font-small/.font-eyebrow classes (main.css:77-82) are unused. Views hard-code: hero H1 58 (Home) / 44 (Features, About) / 40 (Support, Ch…
  - Evidence: grep -rn 'var(--font-' src: 1 consumer; vp_style_diff on home/features/about shows font-weight figma 700 vs build 800 on every title; Figma aggregate of 14 frames (use_figma text census).
  - Fix: Make the ramp the source: add --font-h1-page (52/58 for sub-page heroes, per the census), give the eyebrow a letter-spacing token (0.3px) and a 13px UiBadge size, set heading weight 700, and let the page tickets replace their local font-size/weight declarations with the tokens.
  - Linked: 17tnw2b2cev
- **shared-chrome-25** · class **A** · low · shared · tokens — Brand indigo is spelled four ways and the nav hard-codes colours instead of using the token layer
  - Figma: One accent/brand #5b6bd6 across nav CTA, hero, cards and bands; CTA gradient is accent/brand -> #2b2a6b on a 1248x337 r24 CARD (479:125), not on buttons. The 2.2 mapping says to implement accent/brand as --sc-primary.
  - Build: Navbar.vue hard-codes #090a0f, #9aa4b2, #ffffff, #5b6bd6 (:425) and #4f5ec7 (:437) (no var()); tokens.css:81 --gradient-cta starts at #5b6bd6; UiButton primary uses --sc-primary #6e5cf0; Home's CTA band uses #4f46e5 -> #312e81 (HomeView.vue:684). So the nav CTA, the gradient CTAs, the primary buttons and the band are four different indigos on one page.
  - Evidence: dom home: download-cta bg rgb(91,107,214); ui-button variant-primary bg rgb(110,92,240); final-cta-card bgi linear-gradient(135deg, rgb(79,70,229) ..., rgb(49,46,129)); grep -rn 'gradient-cta' src.
  - Fix: Nav CTA and any brand fill: var(--sc-primary); derive --gradient-cta from var(--sc-primary) -> #2b2a6b and use it for the CTA band cards (the page tickets), not for buttons.
  - Linked: 17tnw2b2cev
- **shared-chrome-26** · class **B** · low · shared · tokens — Button and text colours go through the --sc-* layer (primary #6e5cf0, elevated #1c1f28, border #262a34, text #f4f6fb), a 1-3% luminance gap from Figma's legacy hexes
  - Figma: Figma binds fills to the legacy collection: accent/brand #5b6bd6, bg/elevated #1e232c, border #2b323d, text/primary #eef1f6, text/muted #9aa4b2.
  - Build: UiButton.vue and the shared components use var(--sc-primary) #6e5cf0, var(--sc-elevated) #1c1f28, var(--sc-border) #262a34, var(--sc-text) #f4f6fb, var(--sc-text-secondary) #a7aebe. White on --sc-primary is 4.72:1 (AA), white on Figma's #5b6bd6 is 4.65:1.
  - Evidence: vp_style_diff labels these colour~/fill~ (token layer); computed contrast above.
  - Source: AUTH-LANDING-PAGES-HANDOFF.md section 2.2 (the two token layers: 'Implement with --sc-*').
- **shared-chrome-27** · class **A** · medium · shared · ui-button — UiButton is a 999px pill everywhere; Figma buttons are 10-12px rounded rectangles, pills only for toggles
  - Figma: Radius measured over every button frame on 15 page frames: 10 (nav CTA 468:138, card actions 'Start guide', 'View role', 'Sign out', 'Manage devices', h39-41), 11 (hero primary 469:131 h49, hero secondary 469:133 h47, pricing card CTAs 477:137/477:166 h44, band buttons h47-49), 12 (sign-in Sign in 505:142 h47 and Google 505:148 h44, affiliates Apply now 541:145 h49). 999 appears only on the Monthly/Annual toggle (483:145, h34) and the hero eyebrow pill (469:125).
  - Build: UiButton.vue:60 border-radius var(--pill-radius) (999px) for every variant and size; auth.css:254-257 already overrides it to 12px for the auth card; the nav CTA is a private 999px pill (Navbar.vue:430).
  - Evidence: dom: ui-button variant-gradient/outline/primary radius '999px' on home, about, features, account, pricing; au-btn radius 12px on signin/reset. vp_style_diff boxes Btn/Download radius figma 10 vs build 999.0.
  - Fix: Default radius by size: sm 10px (h39-41), md/lg 11px (h44-49); keep the 12px au-btn override; keep --pill-radius only for toggles and badges. Remove the auth override's reason to exist by making 12px a UiButton prop if the auth ticket prefers.
  - Linked: 17tnw2b2cev
- **shared-chrome-28** · class **A** · medium · shared · ui-button — UiButton height depends on the parent's line-height: the same size renders 41-47 (sm), 47-50.5 (md), 51-58 (lg); Figma uses fixed 39/41/44/47/49
  - Figma: Fixed heights: nav 39 (pad 11/18, 14/Bold), card actions 41 and 39 (pad 12/18, 14/Semi Bold), full-width card CTAs 44 (pad 13/0, 15/Semi Bold), hero and band primary 49 (pad 15/26-28, 15.5/Bold), secondary 47 (pad 14/24, 15.5/Semi Bold).
  - Build: UiButton.vue:85-97: sm 12px 20px / 14px, md 14px 28px / 15px, lg 16px 32px / 16px, weight 600 for all, and no line-height of its own, so height = padding + inherited line box. Measured: lg 58 (Home, About, Features) vs 52 (Contact) vs 51-55 (auth); md 47 (Home/Pricing gradient) vs 50.5 (Support); sm 41-47. Label sizes 14/15/16 vs Figma 14/15/15.5; weight 600 vs Figma 700 on the hero/nav/band primaries.
  - Evidence: dom aggregation of ui-button instances across the 29 captures: 'variant-gradient size-lg' h=58; 'size-lg full-btn' h=52; 'variant-gradient size-md' h=47 vs 50.5; 'variant-outline size-sm' h=43 and 47; Figma scan of all Btn frames (use_figma button census).
  - Fix: Set .ui-button line-height: 1.21 (Inter normal) and re-cut sizes to Figma: sm pad 12px 18px / 14px / h41 (nav compact 11px 18px / 700 / h39), md pad 13px 24px / 15px / h44, lg pad 15px 26px / 15.5px / h49 (secondary lg 14px 24px / h47). Primary lg and nav weight 700, others 600.
  - Linked: 17tnw2b2cev
- **shared-chrome-29** · class **A** · medium · shared · ui-button — Variant set does not match Figma: 'gradient' stands in for the solid primary, 'secondary' has no border, and the white/outlined pair for CTA bands does not exist
  - Figma: Figma draws no gradient-filled button (the gradient is the CTA card 479:125, 1248x337 r24). Primary is solid #5b6bd6 (hero 469:131, Get Pro 477:166). Secondary is #1e232c + 1px #2b323d (hero 'Watch 2-min demo' 469:133 with a leading play glyph, pricing 'Download free'/'Talk to us', careers 'View role', sign-in Google). Outline is transparent + 1px #2b323d ('Sign out', 'Manage devices'). On the gradient band: white fill with #5b6bd6 label 15.5/Bold (479:129) and a transparent button with a 1px #…
  - Build: UiButton.vue:124-130 gradient variant is used for the hero 'Download free' and Pricing 'Get Pro' (dom home: variant-gradient size-lg/md) where Figma is solid; :108-114 secondary has no border, so pages use 'outline' (transparent) where Figma has the filled secondary (Home hero 'Watch 2-min demo', free-tier card); there is no inverse pair, so HomeView.vue:712-716 forces .cta-btn-white with !important, and About/Features put a gradient button and an outline button on their gradient card.
  - Evidence: dom home: hero Download free 'ui-button variant-gradient size-lg', Watch 2-min demo 'variant-outline size-lg', final CTA 'variant-ghost size-lg cta-btn-white'; about 'variant-gradient size-lg' + 'variant-outline size-lg' inside .cta-card. Figma button census: signatures h49 r11 #fff, h47 r11 stroke…
  - Fix: Make 'primary' the solid CTA (page tickets stop using 'gradient' for buttons), give 'secondary' the 1px var(--sc-border) stroke, keep 'outline', and add 'inverse' (white fill, brand ink, 700) and 'inverse-outline' (1px rgba(255,255,255,.5)) for gradient bands so views stop overriding with !important.
  - Linked: 17tnw2b2cev
- **shared-chrome-30** · class **A** · medium · shared · ui-button · a11y — UiButton's focus ring is a box-shadow with outline:none, so it disappears in forced-colors (Windows High Contrast) mode
  - Figma: Handoff sections 5 and 6: focus-visible is a 2px accent/brand ring with a 2px offset on every button; Figma draws no focus state.
  - Build: UiButton.vue:66 outline: none and :72-74 box-shadow 0 0 0 2px var(--sc-base), 0 0 0 4px var(--sc-primary). The look matches the spec on screen (2px gap + 2px ring, 4.1:1 against --sc-base, 3.8:1 against --sc-surface), but box-shadow is removed in forced-colors mode, so keyboard users there get no indicator at all (WCAG 2.4.7 / 1.4.11).
  - Evidence: Source read; computed ring contrast #6e5cf0 on #0b0d12 4.12, on #14161d 3.83.
  - Fix: Replace outline:none with outline: 2px solid transparent (a transparent outline is drawn in forced-colors), keep the box-shadow ring for normal mode; or use outline: 2px solid var(--sc-primary); outline-offset: 2px on :focus-visible directly.
  - Linked: 17tnw2b2cev
- **shared-chrome-31** · class **D** · medium · shared · ui-button · a11y — Hover state is not drawn and the specified direction fails AA: UiButton primary hover is 3.78:1, the nav CTA hover darkens
  - Figma: Frames draw no hover. Handoff section 5: buttons 'hover (lightness shift)' and nav CTA hover 'brand-hover (+8% lightness)'. +8% lightness of #5b6bd6 is about #7c88de, white on it is 3.26:1.
  - Build: UiButton.vue:104-106 primary hover --sc-primary-hover #7e6eff with white 15-16px/600 label = 3.78:1 (resting #6e5cf0 is 4.72:1). Navbar.vue:436-438 nav CTA hover goes DARKER (#4f5ec7, 5.59:1), the opposite direction, so the two primaries behave differently. Gradient hover is a glow (:128-130), secondary/outline/ghost hovers shift to --sc-elevated/--sc-border.
  - Evidence: Computed contrast: white on #7e6eff 3.78, white on #4f5ec7 5.59, white on #7c88de 3.26.
  - Decision: Uma: choose the hover value for primary. A lighter hover cannot hold a white 15px label at 4.5:1 on this indigo; recommend darkening (e.g. the nav's #4f5ec7, 5.59:1) for every primary, and amend section 5 ('+8% lightness') accordingly.
- **shared-chrome-32** · class **A** · low · shared · app-shell — Catch-all 404 view renders a second <main> inside the shell's <main>
  - Figma: Not drawn. Handoff section 6 asks for sound semantics (one h1, nav is a <nav>); App.vue:22 provides the page's single <main>, and the captured public pages all have exactly one.
  - Build: NotFoundView.vue:29 <component :is="embedded ? 'div' : 'main'"> renders <main> when not embedded (the catch-all route in router/index.ts:88-92), nested in App.vue's <main class='main-content'>; AdminShell.vue:76 and AffiliateShell.vue:47 (out-of-scope routes) do the same.
  - Evidence: grep -rn '<main' src: App.vue:22, NotFoundView.vue:29 (component :is main), AdminShell.vue:76, AffiliateShell.vue:47; doc.mains is 1 on all 29 captures because no 404 is captured.
  - Fix: NotFoundView: always render a <div class='nf-page'> (drop the :is main branch and the embedded prop's special case), likewise in the two portal shells.
  - Already owned by ClickUp 17tnw2b0x3h: no fix ticket from this audit.
- **shared-chrome-33** · class **D** · medium · shared · app-shell · a11y — Every public page shares one document title
  - Figma: Not drawn (the frames have no browser chrome).
  - Build: index.html:6 sets 'SelahCue — Church presentation, reengineered' and only /privacy, /terms and the article detail pages change it (lib/legal, lib/useDocumentMeta). Home, Features, Pricing, Download, About, Contact, Support, Docs, Changelog, Blog, Careers, Sign in and Account all report the same title, so tabs, history and screen-reader page announcements cannot tell them apart.
  - Evidence: doc.title in each marketing/*.blink.dom.json: identical on about, account, affiliates, blog, careers, changelog, contact, docs, download, features, home, pricing, reset-*, signin, support, verify-*; distinct only on privacy ('SelahCue Privacy Policy') and terms ('SelahCue Terms of Service').
  - Decision: Uma/product: agree the title scheme (e.g. 'Pricing — SelahCue', 'Sign in — SelahCue') and a route meta.title the shell applies on navigation. WCAG 2.4.2 expects a title that describes the page.
- **shared-chrome-34** · class **A** · medium · shared · app-shell · a11y — Route-loading fallback 'Loading...' fails AA (--sc-text-muted on --sc-base, 4.08:1 at 19px)
  - Figma: Handoff section 5 asks for a skeleton/bg-elevated placeholder while content loads; Figma draws no loading text.
  - Build: App.vue:49-56 .loading color var(--sc-text-muted) #6b7383 on --sc-base #0b0d12, 1.2rem (19.2px) at weight 400: 4.08:1, and it is not large text (needs 24px, or 18.66px bold). It is plain text with no status role.
  - Evidence: Computed contrast #6b7383 on #0b0d12 = 4.08; source App.vue:49-56.
  - Fix: .loading color var(--sc-text-secondary) (8.7:1) and add role='status' to the fallback (or render SkeletonLoader).
  - Linked: 17tnw2b2cev
- **shared-chrome-35** · class **D** · medium · shared · footer — Linux is not drawn anywhere platforms are named (footer, Download cards, Home FAQ) although product says it is available
  - Figma: Footer 479:133 bottom bar draws 'Windows · macOS' only; the Download frame (487:124) draws a Windows card and a macOS card only; the Home FAQ row 'Which platforms are supported?' (478:155) answers with Windows and macOS and says Linux is on the roadmap.
  - Build: Footer.vue has no platform line; DownloadView.vue:28-46 has Windows and macOS cards and no Linux card; HomeView.vue:86-89 names Windows 10/11 and macOS 12+ only. No platform list on the site names Linux.
  - Evidence: Product (owner, 2026-10-04): SelahCue is available for Windows, Linux and macOS. grep -i linux in implementation/marketing/src finds support.ts:108, docs.ts:145 and docs.ts:317 (and a CSS comment): none is a platform list. docs/product/prds/SelahCue-PRD.md:33 (G-2) targets Windows, macOS and Linux.
  - Decision: Uma: draw Linux wherever platforms are named (footer line, a Download card or entry, the FAQ answer) or confirm Windows and macOS only. Figma's 'Linux is on the roadmap' now contradicts product and must change either way. Do not add Linux to the build until it is drawn. It is NOT yet known whether 'available' means a downloadable installer exists today on each platform, or that the app supports a…

### Home — `home` (Figma `468:125`)

Verdict: **diverges** · area: home · route: `/`

The build has all eleven designed sections in the right order and the interactions the handoff asks for (CTA links, accordion with aria-expanded, first item open), but it is a loose re-interpretation rather than a match: SSIM 0.64, 32.5% of pixels differ, and the page is 7052px against 6814px. The biggest gaps are rewritten copy in every section, emoji instead of the SVG icons, narrower 1092px content column with 100px section padding (the +238px comes mainly from the Screens & Outputs section, +112, and Testimonials, +94, offset by the collapsed FAQ, -170), unstyled eyebrows from a missing UiBadge variant, a different hero console and output-manager mock, and inert pricing buttons.

- **home-01** · class A · duplicate of **shared-chrome-01** — Nav bar geometry and roles differ from the Home frame
- **home-02** · class A · duplicate of **shared-chrome-27** — Buttons are pills with gradient fills and the wrong sizes; the pricing 'block' prop does nothing
- **home-03** · class A · duplicate of **shared-chrome-14** — Footer columns, links, tagline and bottom bar differ from the Home frame (and one link is dead)
- **home-04** · class **A** · medium · page — Content column is 1092px wide instead of 1248px, so every grid and the console mock are narrower
  - Figma: 96px page gutters at 1440 (handoff section 3), content 1248 wide: feature cards 402 (gap 20), reliability/step cards 397.3 (gap 28), pricing cards 400 (gap 24), testimonial cards 400 (gap 24), console mock 1140, final CTA card 1248, showcase split 470 / 706 (gap 72).
  - Build: HomeView.vue scoped .container is max-width 1140 with padding 0 var(--page-gutter) (24px) = 1092 content: feature/reliability/step/pricing/testimonial cards are 348 wide with 24px gaps, console mock max-width 1040, final CTA card 1092, showcase is 50/50 columns with 60px gap. HomeView.vue:380-384, :500-504, :511-515.
  - Evidence: dom items: feature-card x=174 w=348 vs Figma 472:130 x=96 w=402; pillar-card w=348 vs 397.3; pricing-card w=348 vs 400; final-cta-card w=1092 vs Figma 479:125 w=1248; console-mockup w=1040 vs 470:124 w=1140. vp_style_diff boxes list all of them as 'width figma 402 vs build 348' etc.
  - Fix: HomeView.vue .container: max-width 1440px; padding-inline var(--gutter) (96px, tokens.css:60) stepping to 48 / 20 at the existing breakpoints; grid gaps per section (features 20, reliability 28, steps 28, pricing 24, testimonials 24); mock max-width 1140; showcase grid 470px / 1fr with gap 72.
  - Linked: 17tnw2b2cex
- **home-05** · class **A** · medium · page — Section vertical rhythm is looser than designed: 100px padding vs 88/90 and 56px header gaps; page is +238px, mostly the Screens & Outputs and Testimonials sections
  - Figma: Section padding 88 (Features 472:124, How it works 476:124) or 90 (Reliability 474:124, Showcase 475:124, Pricing 477:124, Testimonials 478:124, FAQ 478:153, Final CTA 479:124); hero padding 96 top / 72 bottom; header-to-grid gap 48 / 52 / 50 / 48 / 46 / 40 per section. Section heights: nav 79, hero 966, features 824, reliability 651, showcase 516, how it works 604, pricing 869, testimonials 499, FAQ 931 (all answers open), final CTA 517, footer 358 = 6814.
  - Build: Every section uses var(--section-pad) = 100px top and bottom, every .section-header has margin-bottom 56px, hero is 90/80, final CTA section is 40 top / 100 bottom. tokens.css already has --section-padding: 88px (the designed value) but HomeView uses --section-pad. Heights in the build: nav 69, hero 1014.5, features 863.1, reliability 708.1, showcase 628.1, how it works 610.4, pricing 903.3, testimonials 593, FAQ 761.5 (collapsed by design, see home-37), final CTA 495.6, footer 405.5 = 7052.
  - Evidence: Per-section delta = build height minus Figma height (derived from dom item y positions vs the Figma frame): nav -10, hero +48.5, features +39.1, reliability +57.1, showcase +112.1, how it works +6.4, pricing +34.3, testimonials +94.0, FAQ -169.5, final CTA -21.4, footer +47.5; sum +238.1 = report.j…
  - Fix: HomeView.vue: padding-block 88px for .features-section and .steps-section, 90px for reliability/outputs/pricing/testimonials/faq/final-cta (use --section-padding, not --section-pad); hero 96/72; .section-header margin-bottom per section (48/52/50/48/46/40); the biggest recoveries come from the showcase (home-26) and testimonials (home-35) sections.
  - Linked: 17tnw2b2cex
- **home-06** · class **A** · medium · page — Reliability and Testimonials are not full-width panel bands, and the page ground and card fills are hard-coded hexes
  - Figma: Reliability 474:124 and Testimonials 478:124 are full-width bands (#171b22 bg/panel with 1px #2b323d top and bottom edges) with cards in #0e1116 inside; the page is #0e1116 (bg/base, mapped to --sc-base #0b0d12) and cards are #171b22 (mapped --sc-surface #14161d).
  - Build: All sections sit on one flat .home background #090a0f (not a token, darker than --sc-base); cards are hard-coded #12151e; the two bands do not exist, so there is no band edge between sections. HomeView.vue:375-378, FeatureCard/ReliabilityPillar/PricingCard/TestimonialCard/StepCard CSS (#12151e), ConsoleMockup/OutputManagerMockup CSS (#0e1017, #090a0f, #12151f).
  - Evidence: vp_style_diff boxes: 'Reliability 474:124 fill figma #171b22 vs build #090a0f, height 651 vs 6577.9 (matched to .home)'; 'Testimonials 478:124 fill figma #171b22 vs build #090a0f'; 'Frame 474:130 fill figma #0e1116 vs build #12151e'. Slice home-3.png (Figma band vs flat page).
  - Fix: HomeView.vue: wrap Reliability and Testimonials in full-bleed sections with background var(--sc-surface) and border-block 1px var(--sc-border); give their cards var(--sc-base); replace the literal #090a0f/#12151e with var(--sc-base) / var(--sc-surface).
  - Linked: 17tnw2b2cex
- **home-07** · class **A** · high · page · a11y — Text colours use off-token greys and pure white, and the muted ink used for secondary copy fails AA on the cards
  - Figma: Headings text/primary #eef1f6 (mapped --sc-text #f4f6fb); all body, subtitle, blurb and meta copy text/muted #9aa4b2 (mapped --sc-text-secondary #a7aebe), 6.9:1 on #171b22; no #717d93 anywhere.
  - Build: Headings are literal #ffffff, section subtitles/blurbs/hero sub are literal #8c97a8 (not the mapped token, darker), and tertiary copy uses #717d93 in roles where Figma has muted: price period '/ month' 4.39:1 on the #12151e card, author roles 4.39:1, output-manager sub-lines 4.04:1, console panel labels 4.09:1, window title 4.30:1. Home hard-codes these in the scoped CSS of HomeView.vue and the Feature/Pillar/Pricing/Testimonial/Mockup components rather than using --sc-* tokens.
  - Evidence: vp_style_diff colour lines: 'Everything you need... colour figma #eef1f6 vs build #ffffff' (all H1/H2/card titles), 'hero sub colour figma #9aa4b2 vs build #8c97a8', '/ month colour figma #9aa4b2 vs build #717d93', 'Works fully offline ... #717d93'. $RUN/report.json contrast_survey capture=home: 15…
  - Fix: Replace literals with tokens: headings -> var(--sc-text), body/subtitle/blurb -> var(--sc-text-secondary), and use --sc-text-secondary (not #717d93) for price period, author role, output sub-lines, panel labels and the hero trust line so all pass 4.5:1.
  - Linked: 17tnw2b2cex
- **home-08** · class **A** · medium · page — Heading weight is 800 and sizes are flattened; Figma uses Bold 700 and per-section sizes
  - Figma: H1 60/64 Bold 700, ls 0. Section H2 per section: 40/46 (Features, How it works, Pricing), 42/48 (Reliability), 40/46 left-aligned (Showcase), 38 (Testimonials, FAQ), 44/50 (Final CTA), all Bold 700, ls 0. Card/step titles 18.5/600 (features), 20/600 (pillars), 21/600 (steps); plan names 17/600; prices 44/700 (Custom 44/700).
  - Build: H1 58px/800 with -0.02em; every H2 is 38px/800 with -0.01em (.section-title; outputs-title 38, cta-title 40/800 with 60px line height); card/pillar/step titles 18px/700; plan names 22px/800, prices 44/800, 'Custom' 36/800. HomeView.vue:396-403, :462-470, :540-546, :691-696; FeatureCard.vue:53, ReliabilityPillar.vue:68, PricingCard.vue:78-101.
  - Evidence: vp_style_diff: 'Run your service... font-size figma 60 vs build 58.0, font-weight 700 vs 800, letter-spacing figma 0px vs build -1.16px'; 'Built for the one moment... font-size 42 vs 38, weight 700 vs 800'; 'Ready to run... font-size 44 vs 40, line-height 50 vs 60'; 'Plan your service font-size 21 …
  - Fix: Set H1 60/64/700/0; H2 per the Figma sizes and 700/0 tracking (use --font-h2 for 42, 40 for the others, 38 for testimonials/FAQ, 44/50 for the CTA); titles 18.5/600, 20/600, 21/600; plan names 17/600; 'Custom' 44/700.
  - Linked: 17tnw2b2cex
- **home-09** · class **A** · high · page — Icons are emoji and text glyphs, not the feather-style SVG set the handoff specifies
  - Figma: Feature icons 472:131 etc.: 44px black r11 squares with 1.74px-stroke white SVGs (monitor, tablet, list, layout, broadcast, mic: nodes 473:125-473:141); reliability icons 474:131/138/145: 46px r12 FILLED brand / green / gold squares with white shield-check, wifi-off, zap SVGs; showcase and pricing checks are green 1.8px stroke tick SVGs; handoff section 7: 'Icons are inline feather-style SVGs - reuse the same set in the built site'.
  - Build: FeatureCard renders the icon prop as text: 📊 📖 📋 🖥️ 📡 🎤 in a 44px #1b1f2c r10 box; ReliabilityPillar uses ⚡ 📶 ⚡ (the same bolt twice) in tinted boxes; OutputManagerMockup uses 📺 🖥️ 📡; showcase and pricing checks are a '✓' text glyph (circle-tinted in the showcase). Emoji render differently per OS and cannot take the brand colours. HomeView.vue:161-188, :205-222; FeatureCard.vue:11-13; ReliabilityPillar.vue:15-17; OutputManagerMockup.vue:16,28,40; PricingCard.vue:47; HomeView.vue:242.
  - Evidence: vp_style_diff build-only: '20px 📊 (icon-text) ... 🎤', '20px ⚡ 📶 ⚡ (icon-text)', '18px 📺 🖥️ 📡 (output-icon)', '14px ✓ (check-icon)' x12; Figma boxes list VECTOR nodes 473:125-473:141, 474:133-474:147, 477:143-477:218. Slices home-2.png, home-3.png.
  - Fix: Inline the Figma feather SVGs (export from the vector nodes above) as small Vue icon components; features: black 44px r11 box + white stroke 1.74; reliability: filled --sc-primary / --sc-preview / --sc-warn 46px r12 box + white icon (shield-check, wifi-off, zap); showcase and pricing: green 1.8px tick SVG, no circle.
  - Linked: 17tnw2b2cex
- **home-10** · class **A** · medium · shared · ui-badge — UiBadge has no 'accent' or 'warn' variant, so every section eyebrow, the pillar metrics and 'MOST POPULAR' render unstyled
  - Figma: Section eyebrows are plain text: 13/700, +0.3px tracking, UPPERCASE, brand ink #5b6bd6, no pill (FEATURES 472, WHY SELAHCUE 474, SCREENS & OUTPUTS 475, HOW IT WORKS 476, PRICING 477, FROM THE TECH BOOTH 478), 14px above the H2. 'MOST POPULAR' is a 10/700 brand chip on #1e232c inside the Pro card header row (477:160).
  - Build: HomeView.vue passes <UiBadge variant="accent"> (lines 154, 198, 234, 267, 296, 322) and ReliabilityPillar passes 'accent' / 'warn'; UiBadge.vue only defines live, preview, ready, ndi, featured, new (validator at UiBadge.vue:6), so `variant-accent`/`variant-warn` have no rules: dom shows the eyebrows as 11px/600, 0.55px tracking, uppercase, #ffffff text on a transparent pill, '≤3s Start' and '0 Blanks' unstyled, and 'MOST POPULAR' white text floating over the card border.
  - Evidence: dom items: 'ui-badge variant-accent size-sm' color rgb(255,255,255), fs 11px, fw 600, no bg (FEATURES, RELIABILITY, SCREENS & OUTPUTS, HOW IT WORKS, PRICING, TESTIMONIALS, 0 Blanks, 3 OUTPUTS ACTIVE, MOST POPULAR); 'variant-warn' same. vp_style_diff: 'FEATURES font-size figma 13px vs build 11.0px, …
  - Fix: Add a plain .eyebrow style (13px/700, +0.3px, uppercase, ink per home-44) and use it for the six section labels; add 'accent' (brand) and 'warn' (map to the ready/warn tokens) variants to UiBadge or switch the callers to defined variants; MOST POPULAR as a 10/700 chip on --sc-elevated inside the card header row.
  - Linked: 17tnw2b2cew
- **home-11** · class **A** · high · page — 'How it works' anchor has no target on Home, so the nav link does nothing
  - Figma: Handoff 1b: 'How it works' is an in-page anchor on Home (nav 468:131 links to the How it works section 476:124).
  - Build: Navbar.vue:191 and :261 link to href='#how-it-works' but the steps section is <section class="steps-section"> with no id (HomeView.vue:264); the router comment in router/scroll.ts:13 assumes the id exists. Clicking it scrolls nowhere; from any other page the plain hash link never navigates to Home. The footer 'How it works' link points at a non-existent route (see home-03).
  - Evidence: grep 'id=' src/views/HomeView.vue returns nothing; Navbar.vue lines 191/261 use '#how-it-works'; dom focus list: 'How it works' (a, x=376).
  - Fix: HomeView.vue: add id="how-it-works" to the steps section (and scroll-margin-top for the sticky 79px nav); Navbar.vue: use router-link to '/#how-it-works' so it works from other pages.
  - Linked: 17tnw2b2cex
- **home-12** · class **A** · high · page — Hero console mock shows different content and structure from the designed product window
  - Figma: Hero/Product window 470:124: 1140x348 at x=150, radius 16, title bar 45px with traffic lights, 'SelahCue — Live Console' (12/500) and a red LIVE chip on the right; body #0e1116 with two 544x236 slide panes, PREVIEW (green, left) 'PSALM 46:10' / 'Be still, and know that I am God.' and LIVE (red, right) 'JOHN 3:16' / 'For God so loved the world…'; each pane has a '1920 × 1080' label; reference 15/700 gold +0.2 tracking, verse 22/600 white on #080a17 radius 10; soft shadow 0/34/70.
  - Build: ConsoleMockup.vue: 1040 max width, 42px header titled 'SelahCue Operator Console' (13px, centred, #717d93), no LIVE chip; panes are LIVE/'MAIN OUTPUT' on the LEFT and PREVIEW/'STAGE DISPLAY' on the RIGHT; copy 'FOR GOD SO LOVED THE WORLD...' (uppercase, 18/700 gold, ASCII dots) with 'JOHN 3:16 · WEB BIBLE', CURRENT / NEXT tags and 'THAT HE GAVE HIS ONE AND ONLY SON'; no resolution labels, panes are 491 wide with a 220 min-height. src/components/ConsoleMockup.vue:5-44.
  - Evidence: vp_style_diff figma-only: 'SelahCue — Live Console', 'LIVE', 'PSALM 46:10', 'JOHN 3:16', 'Be still, and know that I am God.', '1920 × 1080' x2; build-only: 'SelahCue Operator Console', 'MAIN OUTPUT', 'STAGE DISPLAY', 'CURRENT', 'NEXT', 'JOHN 3:16 · WEB BIBLE'; pair 'For God so loved the world…' fon…
  - Fix: ConsoleMockup.vue: rebuild to Figma: title 'SelahCue — Live Console' + LIVE chip, PREVIEW pane first then LIVE pane, copy 'PSALM 46:10' / 'Be still, and know that I am God.' and 'JOHN 3:16' / 'For God so loved the world…' (22/600 white, reference 15/700 --sc-warn +0.2), '1920 × 1080' labels, slide fill #080a17 radius 10, window radius 16, width 1140.
  - Linked: 17tnw2b2cex
- **home-13** · class **A** · medium · page · a11y — The console mock has no accessible name or alt text; its fake UI text is exposed as page content
  - Figma: Handoff section 6: 'the product-console mock ... need descriptive alt (e.g. "SelahCue operator console showing a Preview and Live scripture slide")'; decorative glyphs aria-hidden; section 5: the hero mock needs a skeleton to avoid layout shift.
  - Build: ConsoleMockup.vue renders ordinary divs/h2s/p (● LIVE, MAIN OUTPUT, FOR GOD SO LOVED THE WORLD..., CURRENT, NEXT) with no role='img', aria-label or aria-hidden, so a screen reader reads the mock as content (and a second h2 per pane sits in the heading outline); no loading placeholder. Its small labels also fail contrast (3.89-4.30:1).
  - Evidence: grep -n 'aria\|role' src/components/ConsoleMockup.vue returns nothing; report.json contrast_survey: '● LIVE' 3.89, 'MAIN OUTPUT' 4.09, 'STAGE DISPLAY' 4.09, 'SelahCue Operator Console' 4.3 (home capture).
  - Fix: Wrap the mock in role="img" with aria-label 'SelahCue operator console showing a Preview and a Live scripture slide' (children aria-hidden), turn the in-mock h2s into divs, and add a --sc-elevated skeleton until it paints.
  - Linked: 17tnw2b2cex
- **home-14** · class **A** · medium · page — Hero eyebrow pill uses a sparkle emoji instead of the brand logo
  - Figma: 469:125: 272x32 pill, radius 999, 'Church presentation, reengineered' 12.5/600 with the SelahCue logo (image 494:132, 18px) before it (handoff section 7: logo placed 'in the hero eyebrow pill').
  - Build: hero-eyebrow renders <span class="sparkle">✨</span> then the text (HomeView.vue:112-115), 13/600 in a 276.5x33.5 pill.
  - Evidence: vp_style_diff build-only: '12px ✨ (sparkle)'; boxes 'Frame 469:125 fill figma #0d0f14 vs build #141722'. Slice home-1.png.
  - Fix: HomeView.vue:113: replace the sparkle with <img src="/selahcue-logo.png" alt="" width="18" height="18"> (tight-cropped per handoff section 7) and set the text to 12.5/600.
  - Linked: 17tnw2b2cex
- **home-15** · class **B** · low · page · a11y — Hero eyebrow text keeps an accessible light-indigo ink instead of Figma brand #5b6bd6
  - Figma: 469:125 text #5b6bd6 on the pill (composite #0d0f14): 4.12:1 for 12.5px/600 text, below AA 4.5.
  - Build: hero-eyebrow colour #a5b4fc on #141722 = 8.96:1 (HomeView.vue:454).
  - Evidence: Computed contrast: #5b6bd6 on #0d0f14 = 4.12:1 (fails 4.5), #a5b4fc on #141722 = 8.96:1; vp_style_diff 'Church presentation, reengineered colour figma #5b6bd6 vs build #a5b4fc'.
  - Source: Measurement: Figma #5b6bd6 on #0d0f14 is 4.12:1 and fails AA for 12.5px text; build keeps #a5b4fc at 8.96:1. FLAG FOR UMA: pick one accessible brand ink for all small brand-coloured text (see home-44).
- **home-16** · class **A** · medium · page — Hero typography: H1 and sub are smaller/heavier, trust line is darker and larger
  - Figma: H1 60/64 Bold ls 0 in a 920 box centred at y=233; sub 19/29 #9aa4b2 in 720 (3 lines); CTA row at y=508; trust line 13.5/400 #9aa4b2 ls 0.1 at y=583 (454 wide); eyebrow-to-H1 gap 26.
  - Build: H1 58/800/-0.02em max-width 900; sub 18px #8c97a8 max-width 780 lh 1.6; trust line 14px #717d93 with 10px gaps; eyebrow margin-bottom 24, hero stack uses ad-hoc margins (24/36/20/60). HomeView.vue:462-494.
  - Evidence: vp_style_diff: 'Run your service... font-size 60 vs 58.0, weight 700 vs 800, letter-spacing 0 vs -1.16'; 'SelahCue is the offline-first... font-size figma 19px vs build 18.0px, colour #9aa4b2 vs #8c97a8'; build-only 'Free to start / · / Windows, macOS & mobile control (14px, three separate spans)';…
  - Fix: HomeView.vue: H1 60/64/700/0 in a 920 box; sub 19/29 var(--sc-text-secondary) in 720; trust line 13.5px var(--sc-text-secondary) +0.1; use a 26px flex gap for the hero stack (eyebrow, H1, sub, CTAs 4px under) and 72px bottom padding.
  - Linked: 17tnw2b2cex
- **home-17** · class **A** · low · page — 'Watch 2-min demo' is missing its play glyph and secondary-button treatment
  - Figma: 469:133: the label is preceded by a '▶' glyph (11px, #eef1f6, aria-hidden per handoff section 6), button fill #1e232c with 1px #2b323d, 9px gap.
  - Build: UiButton variant=outline renders text only, transparent fill, no glyph (HomeView.vue:130-132).
  - Evidence: vp_style_diff figma-only: '▶ (11x400)'; boxes 'Frame 469:133 fill figma #1e232c vs build no fill'. Slice home-1.png.
  - Fix: HomeView.vue:130: add <span aria-hidden="true">▶</span> before the label and use the secondary (elevated fill) button variant from home-02.
  - Linked: 17tnw2b2cex
- **home-18** · class **C** · high · page — 'Watch 2-min demo' advertises a demo video that does not exist and links to a missing anchor
  - Figma: 469:133 'Watch 2-min demo' (with play glyph) under the hero CTA; handoff section 8 lists 'real screenshots + a demo video' as out-of-scope follow-ups.
  - Build: UiButton variant=outline href="#demo" (HomeView.vue:130); no element has id="demo" and no video asset exists in src/ or public/, so the button does nothing; the label still promises a 2-minute demo.
  - Evidence: grep -rn 'demo' src (excluding admin/affiliate views) shows only HomeView.vue:130-131; no .mp4/.webm/embed under implementation/marketing; dom focus list: 'Watch 2-min demo' a href '#demo'.
  - Decision: Owner/Uma: until a real demo exists, either remove the button (hero keeps one CTA) or relabel it to something true that links to a real page (e.g. 'See how it works'). Keep Figma's layout; do not ship a link to nothing.
  - Linked: 17tnw2b0x3h
- **home-19** · class **D** · low · page — Build-only decoration and interaction states that no frame draws
  - Figma: Hero has no glow; the final CTA card has no outer shadow; feature cards have no hover state; the Pro pricing card is a flat #171b22 with a 2px #5b6bd6 border and no glow (handoff section 5 specifies only nav, button, FAQ, form states).
  - Build: hero-bg-glow (900x600 radial rgba(110,92,240,.15), HomeView.vue:422-434); final-cta-card box-shadow 0 25px 60px rgba(79,70,229,.3) (:688); FeatureCard hover translateY(-4px) + border/shadow (FeatureCard.vue:31-35); pricing-card.popular box-shadow glow + gradient background (PricingCard.vue:66-70); FAQ question hover colour.
  - Evidence: Source review; slices home-1.png (glow behind H1) and home-9.png (CTA card glow) show them, Figma slices do not.
  - Decision: Uma: keep or drop these additions? If kept they need to be drawn (hover lift on cards, popular-card glow, hero glow) so QA has a reference; otherwise remove for pixel parity.
- **home-20** · class **A** · high · page — Features section copy differs from the handoff and Figma (subtitle and all six blurbs)
  - Figma: 472:124: subtitle 'One app for the whole ministry moment — from planning the order of service to the last slide, on stage and online.' (18/27, 640 wide). Blurbs (14.5/22, 350 wide): 'Stage scripture, songs, and slides in Preview, then Go Live to the audience — the output never blanks, even on a fault.' / 'A bundled public-domain Bible with instant reference parsing and keyword search. Add more translations any time.' / 'Build the order of service, run countdowns, and keep every segment on time …
  - Build: Subtitle 'All the tools you need to run a seamless service, built into one reliable application.' (16px); blurbs: 'Real-time multi-screen output with a zero-blank hardware buffer guarantee.' / 'Built-in WEB Bible with instant verse-by-verse reference lookup and quick search.' / 'Bounded run-sheet planning with automated stage countdown timers and TIME UP alerts.' / 'Dedicated stage display showing current lyrics, next slide, presenter notes, and service clocks.' / 'Direct NDI 5 broadcast stream…
  - Evidence: vp_style_diff figma-only: 'One app for the whole ministry moment...', six 14.5x400 blurbs; build-only: 'All the tools you need...' (16px section-subtitle), six 14px card-desc lines. Slice home-2.png.
  - Fix: HomeView.vue:156-189: restore the Figma subtitle and the six Figma blurbs verbatim (apply the C-class edits in home-23/home-42/home-43 where Figma itself overclaims); card body 14.5/22 in --sc-text-secondary, subtitle 18/27 in a 640px box.
  - Linked: 17tnw2b2cex
- **home-21** · class **A** · high · page — Reliability section copy and labels differ (eyebrow, subtitle, three descriptions)
  - Figma: 474:124: eyebrow 'WHY SELAHCUE'; H2 'Built for the one moment you can't repeat'; sub 'Sunday morning doesn't wait for a spinning cursor. SelahCue is engineered so the audience output is always up — reliable, offline, and fast.'; pillars: 'Never blanks the screen — No component failure — a bad slide, a lost GPU, a dropped controller — is ever allowed to black the live output.' / 'Works fully offline — Everything runs on-device — no internet, no account, no cloud dependency during the service. It…
  - Build: Eyebrow 'RELIABILITY'; sub 'Core engineering guarantees designed for live Sunday worship environments.'; descriptions: 'Hardware frame buffer holds the last-good image if any output glitches (NFR-024).' / '100% local presentation engine. Internet backhaul drops will never stop your service (NFR-015).' / '≤3s cold start, capped GPU memory usage, and zero lag when triggering live slides.' - internal requirement ids shown to visitors, 'zero lag' and 'hardware frame buffer' are unbacked. HomeView.v…
  - Evidence: vp_style_diff figma-only: 'WHY SELAHCUE', 'Sunday morning doesn't wait...', three 15x400 descriptions; build-only: 'RELIABILITY (ui-badge)', 'Core engineering guarantees...', three 14px pillar-desc lines with '(NFR-024)' / '(NFR-015)'. Slice home-3.png.
  - Fix: HomeView.vue:195-226: eyebrow 'WHY SELAHCUE', Figma subtitle (18/27, 660 wide) and the three Figma descriptions (15/23); drop the NFR ids; pillar title 20/600, card padding 28/24, card radius 14.
  - Linked: 17tnw2b2cex
- **home-22** · class **D** · medium · page — Build adds a metric badge to every reliability pillar that no frame draws
  - Figma: Pillar cards 474:130/137/144 end after the description (223px tall, no footer element).
  - Build: ReliabilityPillar.vue:20-24 adds a footer badge: '0 BLANKS', '100% OFFLINE', '≤3S START' (cards 285.7px tall); with the unstyled accent/warn variants (home-10) two of them render as bare white text. '≤3s' is also the proxy-only startup claim (home-23).
  - Evidence: vp_style_diff build-only: '11px 0 Blanks', '11px 100% Offline', '11px ≤3s Start' (ui-badge); boxes 'Frame 474:130 height figma 223 vs build 285.7'. Slice home-3.png.
  - Decision: Uma: the three metric badges are not in the design. Remove them (recommended: '0 Blanks' is a zero-count claim with no counter behind it and '≤3s' is a proxy number, home-23) or draw and approve them. Pending that, they add 62px to the section.
- **home-23** · class **C** · medium · page — 'Sub-3-second cold start' rests on a control-server-ready proxy, not on time to a usable window
  - Figma: Reliability pillar 3 (474:144): 'Sub-3-second cold start and a tight, capped memory footprint.' (handoff section 2 words it '<=3 s cold start, capped memory').
  - Build: Pillar reads '≤3s cold start, capped GPU memory usage, and zero lag when triggering live slides.' with a '≤3S START' badge (HomeView.vue:221-222). Same number, plus 'zero lag' (no measurement exists).
  - Evidence: docs/product/prds/SelahCue-PRD.md section 14: NFR-001 'Cold start <=3s; warm <=1s on reference hardware', the table being 'proposals to be ratified in Stage 5'. The only measurement is scripts/measure_nfr.sh (make nfr), which states it is a PROXY (process launch to control-server endpoint, 'first v…
  - Decision: Owner: either keep 'cold start under 3 seconds' only if Stage 5 measures time-to-first-frame on Tier-A hardware, or ship a claim the repo backs today (e.g. 'Starts fast and keeps memory bounded') with no number. Remove 'zero lag' and the '≤3S START' badge. Keep Figma's layout.
  - Linked: 17tnw2b0x3h
- **home-24** · class **A** · high · page — Screens & Outputs copy and checklist differ from Figma
  - Figma: 475:124: eyebrow 'SCREENS & OUTPUTS' (brand, 13/700), H2 'One live moment, every output' 40/46 in 470px (2 lines), body 17/26 'Send the same live content to your projector, a stage confidence monitor, and an NDI stream — each with its own theme, orientation, scaling, ...' (text clipped at 140 chars by the extractor); three single-line checks (15px, #eef1f6): 'Audience projector — the program the room sees', 'Stage display — current, next & timer, for the speaker only', 'NDI output — broadcast t…
  - Build: Body 'Send clean lyrics to your main venue projectors, custom current/next slides to stage monitors, and transparent lower thirds to your livestream switcher — all simultaneously from one seat.' (16px); checklist items are bold lead + muted detail with wrapped second lines: 'Audience projector · Full 4K resolution, clean typography, motion backgrounds', 'Stage display (current/next/timer) · Current slide, next item preview, countdown clock', 'NDI output to OBS / vMix / Wirecast · Direct IP feed…
  - Evidence: vp_style_diff figma-only: 'Send the same live content...', 'Audience projector — the program the room sees', 'Stage display — current, next & timer, for the speaker only', 'NDI output — broadcast to OBS, vMix, or another machine'; build-only: 'Send clean lyrics...' (outputs-body), three checklist s…
  - Fix: HomeView.vue:236-253: use the Figma body (17/26) and the three Figma one-line items (15px --sc-text, green tick SVG, 13px row gap, no circle, no second line).
  - Linked: 17tnw2b2cex
- **home-25** · class **A** · high · page — Output-manager mock is a different component from the designed 'Screens & Outputs' window
  - Figma: 475:142: 706x306 window, radius 16, title bar 52px with 'Screens & Outputs' 14/600 and a '+ Add output' brand button (95x26, r8, 11.5/600 white); three 678x68 rows (r11) each with a 78x46 slide thumbnail (#241c4a / #0f121a / #0d1221, r7), name 14/600 + a tag chip (MAIN brand, STAGE green, NDI green) and a right status chip (● LIVE red, ● READY gold, ● BROADCASTING green) on #1e232c pills; shadow 0/24/56.
  - Build: OutputManagerMockup.vue: 516 wide card titled 'OUTPUT MANAGER' with a '3 OUTPUTS ACTIVE' badge (unstyled accent variant), no '+ Add output' button, rows have a 40px emoji tile instead of a thumbnail, name 15/700 'Audience - Main' (hyphen), a muted sub-line ('Display 2 · 1920x1080 · 60fps', 'Display 3 · Confidence View', 'NDI 5 Stream · Alpha Channel') and a single combined badge ('MAIN · LIVE', 'STAGE · READY', 'NDI · BROADCASTING', last one sky-blue); rows 84.5 tall. src/components/OutputManag…
  - Evidence: vp_style_diff figma-only: 'Screens & Outputs', '+ Add output', 'MAIN', 'LIVE', 'STAGE', 'READY', 'NDI', 'BROADCASTING' as separate chips; build-only: 'OUTPUT MANAGER', '3 OUTPUTS ACTIVE', 'MAIN · LIVE', 'STAGE · READY', 'NDI · BROADCASTING', three output-sub lines; pair 'Audience — Main' copy figma…
  - Fix: OutputManagerMockup.vue: rebuild to 475:142: title 'Screens & Outputs' + '+ Add output' button; 68px rows with 78x46 thumbnails, em-dash names, tag chip + separate status chip (● dot) in the Figma colours; delete the sub-lines (they carry the unbacked 60fps / NDI 5 / alpha text, home-42).
  - Linked: 17tnw2b2cex
- **home-26** · class **A** · medium · page — Showcase layout: columns are 50/50 and centred instead of 470 / 706 top-aligned; this section is +112px
  - Figma: 475:124 pad 90/96, two columns gap 72: text column 470 wide aligned to the top (eyebrow at y=2610), mock 706 wide starting at y=2625 beside it; section height 516.
  - Build: .outputs-layout is grid 1fr 1fr, gap 60, align-items center, so the 516px mock and the taller text column are vertically centred with the mock 34px lower than the text top; the wrapped 2-line checklist items and 38px H2 make the text column ~428px; section height 628.1 (+112.1 vs Figma, the largest single contributor to the +238px).
  - Evidence: dom: output-manager-card x=750 y=2789 w=516 h=359.5; vp_style_diff boxes 'Frame 475:142 width 706 vs build 1440 (matched to .home)'; y-shift 'SCREENS & OUTPUTS +77.7', 'HOW IT WORKS +59.5'.
  - Fix: HomeView.vue:533-538: grid-template-columns 470px minmax(0,1fr); gap 72px; align-items start; mock width 706; section padding 90.
  - Linked: 17tnw2b2cex
- **home-27** · class **A** · medium · page — How it works: step markers and card styling differ
  - Figma: 476:130/135/140 cards 397.3x232, radius 16, padding 30/28, gap 16; marker is a 46px brand-filled CIRCLE (r999) holding a white 21/700 '1' / '2' / '3'; title 21/600 #eef1f6; body 15/23 muted; all three markers brand.
  - Build: step-card padding 32/28 radius 16, 348x234; marker is a 44px rounded SQUARE (radius 10) with a tinted fill and '01' / '02' / '03' in 16/800 indigo - the second one green; title 18/700 white; body 14px/1.6 #8c97a8. HomeView.vue:603-643.
  - Evidence: vp_style_diff figma-only: '1','2','3' (21x700); build-only: '01','02','03' (16px step-icon-box, one 'green'); pairs 'Plan your service font-size 21 vs 18, weight 600 vs 700', 'step body 15/23 vs 14'. Slice home-5.png.
  - Fix: HomeView.vue:273-287,610-629: 46px circle fill --sc-primary with white 21/700 '1'/'2'/'3' (no green variant); title 21/600; body 15/23 --sc-text-secondary; padding 30/28.
  - Linked: 17tnw2b2cex
- **home-28** · class **A** · medium · page — How it works subtitle and step descriptions are reworded
  - Figma: 476:125 sub 'From an empty plan to a running service in minutes — no manual, no setup weekend.' Steps: 'Add songs, scripture, and sections to the order of service. Set countdowns and give any item its own theme.' / 'Stage the next item in Preview, then Go Live. The audience, stage, and NDI outputs all update together.' / 'Drive it from the console — or pair your phone over the local network. No internet, no lag, no surprises.'
  - Build: Sub 'Designed for volunteer simplicity without sacrificing professional control.' Steps: 'Import songs, search scripture, add media, and set countdown timer thresholds in minutes.' / 'Stage content safely in Preview before sending to Live with a single click or keyboard shortcut.' / 'Drive slides from the desktop operator console or pair any mobile phone over local Wi-Fi.' HomeView.vue:269-286.
  - Evidence: vp_style_diff figma-only: 'From an empty plan...', three 15x400 step bodies; build-only: 'Designed for volunteer simplicity...' (16px), three 14px bodies. Slice home-5.png.
  - Fix: HomeView.vue:269-286: replace with the Figma subtitle and step bodies verbatim ('No internet, no lag' is acceptable: on-LAN control is local, NFR-009/015).
  - Linked: 17tnw2b2cex
- **home-29** · class **A** · high · page — Free plan shows '$0 / month' instead of '$0 / forever'
  - Figma: 477:133: '$0' 44/700 followed by '/ forever' (15, muted); Pro '/ month'.
  - Build: pricingPlans[0] has period: 'month' (HomeView.vue:19) so PricingCard renders '$0 / month', which reads as a recurring charge and contradicts the FAQ ('Free tier is free forever').
  - Evidence: dom/diff: build-only '15px / month (price-period)' for the Free card; figma-only '/ forever' (y=4024, 15x400).
  - Fix: HomeView.vue:19: Free period 'forever' (render '/ forever'); Church keeps no period.
  - Linked: 17tnw2b2cex
- **home-30** · class **A** · medium · shared · pricing-card — Pricing cards: equal-height stretched cards with floating tag, auto-width pill CTAs and different type, vs top-aligned cards with an in-header chip and full-width CTA
  - Figma: 477:130/157/194: Free 400x408 and Church 400x408 (r18, pad 32/30), Pro 400x495 with a 2px #5b6bd6 border (pad 34/30/32/30), cards top-aligned (the Pro card is taller); header row = plan name 17/600 + 'MOST POPULAR' chip (Pro); price 44/700; description 15/22; CTA 340x44 r11 full card width with the divider BELOW it; features 14/20, 11px gap, green tick SVG.
  - Build: .pricing-grid align-items: stretch makes all three cards 499.5 tall; padding 36/30 radius 20; plan name 22/800; 'MOST POPULAR' is an absolutely positioned unstyled badge half-over the top border (top -14px, right 24px); Pro has a 1px --sc-primary border + glow + gradient fill; CTA is a 109-164px pill (block prop ignored); description 14px min-height 42; features 14px/1.4 with a '✓' glyph, gap 14. PricingCard.vue:18-51, :55-142.
  - Evidence: vp_style_diff boxes: 'Frame 477:130 radius figma 18 vs build 20.0, width 400 vs 348, height 408 vs 499.5'; 'Frame 477:157 border figma #5b6bd6 2px vs build none (matched to .home)'; 'Frame 477:166 width 340 vs 109.6'; pairs 'MOST POPULAR x -31.5px', 'Free font-size 17 vs 22', 'Custom font-size 44 v…
  - Fix: PricingCard.vue / HomeView.vue:650-655: align-items start; padding 32/30 (popular 34/30/32/30), radius 18; Pro border 2px solid --sc-primary, no glow/gradient; header row with the chip; CTA width 100% height 44 radius 11 placed above the divider; plan name 17/600; features 14/20 gap 11 with SVG ticks; fix the UiButton block prop (home-02).
  - Linked: 17tnw2b2cew
- **home-31** · class **A** · high · page — Pricing heading, plan descriptions and feature bullets differ from Figma
  - Figma: 477:125 sub 'Start free, upgrade when you're ready, and cancel anytime — it still runs fully offline on Sunday.' Free: 'Everything to run a service on one machine.' + 'Live audience output + stage display / Bundled public-domain scripture + search / Service plans, timers & themes / One physical output'. Pro: 'For multi-output and streaming churches. Billed monthly, or save 20% yearly.' + 'Everything in Free / NDI + multiple simultaneous outputs / Mobile control over your local network / Theme D…
  - Build: Sub 'Start free, upgrade when your church is ready, cancel anytime. Billed monthly or save 20% annually.' Free: 'Everything your church needs to start presenting' + '1 Venue Device seat / Bundled Public Domain Bibles / Basic service plan run-sheet / Single display projector output'. Pro: 'For churches requiring NDI, stage monitors, and multi-output' + 'Up to 5 Venue Device seats / Licensed Bible Entitlements / NDI 5 direct broadcast streaming / Stage confidence monitor & timers / Mobile control…
  - Evidence: vp_style_diff figma-only: 'Start free, upgrade when you're ready...', 'Everything to run a service on one machine.', 'For multi-output and streaming churches...', 'For multi-site teams and larger ministries.', 14 bullet lines; build-only: 'Start free, upgrade when your church is ready...', 'Everyth…
  - Fix: HomeView.vue:15-59,298: replace the plan descriptions and bullet lists with the Figma ones, then apply the owner's honest-content decision (home-33, home-34) to whatever Figma lines are not backed.
  - Linked: 17tnw2b2cex
- **home-32** · class **A** · high · shared · pricing-card — Pricing CTAs ('Download free', 'Get Pro', 'Talk to us') are buttons with no action
  - Figma: 477:137/166/200: three CTAs; handoff section 5: 'Download / Talk-to-us: link to app-store/download or a contact form'; section 6: 'pricing CTAs fully operable'.
  - Build: PricingCard.vue:38 renders <UiButton ... block> with no to/href, and UiButton falls back to a <button> with no handler (lib/ui/buttonElement.ts); the three CTAs are in the tab order (dom focus: button 'Download free', 'Get Pro', 'Talk to us') but do nothing when activated.
  - Evidence: dom focus list: {name:'Download free', tag:'button', y:4405}, {name:'Get Pro', tag:'button'}, {name:'Talk to us', tag:'button', y:4397}.
  - Fix: PricingCard.vue: add a 'to' prop per plan: Free -> /download, Pro -> /pricing (or the checkout route once D1 lands), Church -> /contact; render them as router-link buttons so they get href and Enter/Space.
  - Linked: 17tnw2b2cew
- **home-33** · class **C** · high · page — Pricing teaser asserts prices, a billing model, tier gating and a 'most popular' plan that the repo has not decided or built
  - Figma: 477:124: Pro '$19 / month' with 'Billed monthly, or save 20% yearly' and a 'MOST POPULAR' chip; Free '$0 / forever' with 'One physical output'; a 'Church / Custom' tier ('Multi-campus / site licensing', 'Guided onboarding & training', 'Priority support'); 'cancel anytime' repeated in the pricing sub, FAQ, final CTA, hero trust line ('Free to start') and footer. Handoff section 8 marks all pricing, tiers and billing terms 'Assumed'.
  - Build: Build ships the same $19, 'save 20%', MOST POPULAR, Church/Custom and 'Cancel anytime' copy (HomeView.vue:15-59, :298, :358); the module's isAnnual toggle is declared but never rendered.
  - Evidence: docs/decisions/DECISION-LOG.md DEC-008: tier STRUCTURE decided as Free / Pro / Platinum (Free = 1 device, 2 outputs, no NDI, 30 min STT, watermark; Pro 3 seats, 5 outputs, 5 NDI, 5 h STT; Platinum 7 seats, 10 outputs) but 'Pricing/price points ... tier naming' stay open in D1; there is no 'Church' …
  - Decision: Owner (pricing decision D1): the numbers are not argued here. Decide: (1) hide the price and 'save 20%' until D1 closes, or show 'Pricing coming soon'; (2) drop 'MOST POPULAR' and 'Cancel anytime' while no billing exists; (3) align tier names/limits with DEC-008 (Free 2 outputs, Pro 3 seats) or confirm 'Church' as a real tier.
  - Linked: 17tnw2b0x3h
- **home-34** · class **C** · high · page — Build-only plan limits contradict the tier decision (seats, outputs) and invent SKUs
  - Figma: Figma lists no seat counts and no Bible-entitlement line items.
  - Build: Pro 'Up to 5 Venue Device seats' (DEC-008: 3), Church 'Unlimited Venue Device seats' (DEC-008 top tier: 7), Free 'Single display projector output' (DEC-008: 2 outputs), plus 'Licensed Bible Entitlements', 'Custom Bible entitlement SLAs' and 'Dedicated Solutions Architect' (no such product or service exists). HomeView.vue:22-55.
  - Evidence: docs/decisions/DECISION-LOG.md DEC-008 table (seats 1/3/7, outputs 2/5/10); docs/legal/LEGAL-DRAFT-NOTES.md section 9.1 #2: no licensed translation, publisher agreement or download pipeline exists; vp_style_diff build-only: 'Up to 5 Venue Device seats', 'Unlimited Venue Device seats', 'Custom Bible…
  - Decision: Owner: remove these invented bullets and use the Figma bullets as filtered by home-33. Confirm that a SLA / solutions-architect offer is not being promised before anything like it appears.
  - Linked: 17tnw2b0x3h
- **home-35** · class **A** · medium · page — Testimonial cards: typography, avatar and copy format differ; eyebrow reads 'TESTIMONIALS' not 'FROM THE TECH BOOTH'
  - Figma: 478:124 band with eyebrow 'FROM THE TECH BOOTH' and H2 38/700; cards 400x198, fill #0e1116, radius 16, padding 28, gap 22; quote 17/26 regular #eef1f6 INCLUDING curly quotes; avatar 42px circle (brand / green / gold) with 14/700 white initials; name 14.5/600; role 12.5 muted written 'Tech Director · Grace City'.
  - Build: Quote 15px/1.6 ITALIC #c5cedc with no quote marks; cards 348x253.5 (+55px) fill #12151e padding 32/28; avatar 40px; name 15/700; role 13px '@' form ('Worship Director @ Grace Community'); eyebrow 'TESTIMONIALS'. TestimonialCard.vue:36-88, HomeView.vue:322.
  - Evidence: vp_style_diff figma-only: 'FROM THE TECH BOOTH', three 17x400 quotes, three 14.5x600 names, three 12.5x400 roles with '·'; build-only: 'TESTIMONIALS', three 15px quote-text, 15px author-name, 13px author-role with '@'; boxes 'Frame 478:129 height 198 vs 253.5'. Slice home-7.png.
  - Fix: TestimonialCard.vue: quote 17/26 regular --sc-text with curly quotes, no italics; card radius 16 padding 28 gap 22 fill --sc-base on the #171b22 band; avatar 42; name 14.5/600; role 12.5 muted with ' · '; HomeView.vue:322 eyebrow 'FROM THE TECH BOOTH' (subject to home-36).
  - Linked: 17tnw2b2cex
- **home-36** · class **C** · high · page — Testimonials are invented named quotes (Figma and build use different invented people)
  - Figma: 478:128: three named quotes - Marcus Bediako (Tech Director · Grace City), Dela Amenya (Worship Lead · Hope Chapel), Sam Okoro (Stream Team · New Life) - saying e.g. 'We moved three campuses to SelahCue' and 'dropped straight into our OBS stream', under the heading 'Run by volunteers. Trusted on Sunday.' Handoff section 8 marks names/quotes/churches 'Assumed'.
  - Build: Three different invented people: Sarah Jenkins (Worship Director @ Grace Community), Mark Davis (Technical Director @ Redeemer Church), Pastor Paul Miller (Lead Pastor @ Hope Chapel) with fabricated quotes ('volunteer onboarding time dropped to zero', 'works 100% offline'); initials avatars SJ / MD / PP. HomeView.vue:61-80, :323.
  - Evidence: vp_style_diff figma-only: 'Marcus Bediako', 'Dela Amenya', 'Sam Okoro', 'MB', 'DA', 'SO'; build-only: 'Sarah Jenkins', 'Mark Davis', 'Pastor Paul Miller', 'SJ', 'MD', 'PP'. MARKETING-SITE-HANDOFF.md section 8 lists names, quotes and churches as 'Assumed'; no customer, case-study or consent record e…
  - Decision: Owner (binding rule: honest content wins): keep the section layout, ship NO invented person or church. Options: omit the section until real, consented quotes exist; or replace with product-voiced statements without attribution. The heading 'Run by volunteers. Trusted on Sunday.' is itself a trust claim and should be reworded until real users exist.
  - Linked: 17tnw2b0x3h
- **home-37** · class **B** · low · page — FAQ ships collapsed with the first item open; Figma draws all five answers open
  - Figma: FAQ 478:153 draws all five rows expanded (each 133px, section height 931) 'for review'.
  - Build: FaqAccordion defaultOpen=0: first answer open, others collapsed with a rotating +/x; FAQ section is 761.5px (-169.5).
  - Evidence: dom: faq-item heights 169 / 73 / 73 / 73 / 73.
  - Source: MARKETING-SITE-HANDOFF.md section 5 (FAQ): 'Designed expanded for review; ship collapsed-by-default with the first item open.' The +→× rotation also follows that section.
- **home-38** · class **A** · high · page — FAQ questions and answers are reworded and two questions are replaced
  - Figma: 478:155 five rows (18/600 questions, 15.5/24 answers): 'Do I need an internet connection?' / 'Which platforms are supported?' / 'Can I use my own songs, slides, and designs?' / 'What is NDI, and do I need it?' / 'How does billing work?' with the Figma answers (internet, Windows+macOS with mobile companion and Linux on the roadmap, multi-slide lyrics and Theme Designer, NDI optional and off by default, free forever / cancel anytime).
  - Build: 'Does SelahCue work fully offline on Sunday morning?' / 'What platforms and operating systems are supported?' / 'How do copyrighted Bible translation entitlements work?' (replaces 'own songs, slides...') / 'Does SelahCue support NDI streaming to OBS and vMix?' (replaces 'What is NDI...') / 'How does billing work and can I cancel anytime?' with different answers; questions 17/600, answers 15/1.6; list 800 wide vs 780. HomeView.vue:82-103, FaqAccordion.vue:84, :125.
  - Evidence: vp_style_diff figma-only: all five Figma questions and answers (y=5210.5 ... 5777); build-only: 'Does SelahCue work fully offline on Sunday morning?', 'What platforms and operating systems are supported?', 'How do copyrighted Bible translation entitlements work?', 'Does SelahCue support NDI streami…
  - Fix: HomeView.vue:82-103: restore the five Figma Q&As verbatim EXCEPT the platforms answer: Figma's 'Linux is on the roadmap' contradicts product (available for Windows, Linux and macOS, 2026-10-04) and waits for Uma (shared-chrome-35), so keep the build's platforms wording until it is redrawn and claim no downloadable macOS or Linux installer (home-40); billing and offline wording per home-33/43; FaqAccordion: question 18/600, answer 15.5/24, list width 780.
  - Linked: 17tnw2b2cex
- **home-39** · class **A** · low · shared · faq-accordion · a11y — FAQ accordion: collapsed answers are still exposed to assistive tech and buttons lack aria-controls
  - Figma: Handoff section 6: accordion toggles on Enter/Space and exposes aria-expanded (FAQ as a disclosure pattern); '+' is a 22px glyph.
  - Build: FaqAccordion.vue: native <button aria-expanded> (Enter/Space work, aria-expanded present), but no aria-controls and the collapsed answer wrapper only uses grid-template-rows 0fr, so the hidden <p> stays in the accessibility tree and a screen reader reads closed answers; toggle is a 24px SVG plus. FaqAccordion.vue:29-53.
  - Evidence: Source review of FaqAccordion.vue; dom focus list shows the 5 buttons in order after the pricing CTAs.
  - Fix: FaqAccordion.vue: give each answer an id + role='region' aria-labelledby, set aria-controls on the button, and add visibility:hidden (or inert) to the collapsed wrapper after the transition; icon 22px.
  - Linked: 17tnw2b2cew
- **home-40** · class **C** · medium · page — Build FAQ states false facts about Bible translations and platform versions
  - Figma: Figma FAQ makes no claim about copyrighted translations or OS versions.
  - Build: Answer 3: 'Public-domain Bibles (WEB, ASV, BSB) are bundled ... Copyrighted translations (NIV, ESV, NLT) are granted via post-activation entitlement and downloaded to an encrypted local store'; answer 2: 'Windows 10/11 (64-bit) and macOS 12+ (Apple Silicon & Intel)'; answer 1: 'built desktop-authoritative'. HomeView.vue:88-93.
  - Evidence: docs/legal/LEGAL-DRAFT-NOTES.md section 9.1: #3 'BSB is not bundled; the bundled set is KJV, WEB, ASV, WEBBE and Darby', #2 'no licensed translation, publisher agreement or download pipeline exists'; grep for 'macOS 12' / 'Windows 10' in docs, tauri config and CI returns no supported-version statem…
  - Decision: Owner: remove the licensed-translation answer (restore Figma Q3) and either cite real minimum OS versions from a release matrix or drop the version numbers. Platforms: product says Windows, Linux and macOS are available (2026-10-04), so naming the platforms is backed; the version numbers are not.
  - Linked: 17tnw2b0x3h
- **home-41** · class **A** · medium · page — Final CTA band: gradient, card width, copy colour and secondary button differ
  - Figma: 479:125: 1248x337 card, radius 24, fill = brand-to-indigo gradient (token --gradient-cta #5b6bd6 -> #2b2a6b), padding 64/48, gap 22, H2 44/50 white 700, sub 19/28 #dbe0fa, buttons 'Download free' (white, label brand #5b6bd6, 15.5/700, 167x49 r11) and 'See pricing' (transparent, 1px white@50% stroke, 137x47 r11), no outer shadow.
  - Build: final-cta-card 1092x355.6 with a hard-coded linear-gradient(135deg,#4f46e5,#312e81) (HomeView.vue:684) instead of --gradient-cta, glow shadow, H2 40/800 with 60px line height, sub 18px rgba(255,255,255,.85) (renders #dadadb grey), white button label #312e81 on a 177.8x58 pill, second button 'View pricing' with a 1px --sc-border outline that is nearly invisible on the purple. HomeView.vue:679-716.
  - Evidence: vp_style_diff: 'Ready to run... font-size 44 vs 40, line-height 50 vs 60'; 'Start free and go live... colour figma #dbe0fa vs build #dadadb, font-size 19 vs 18'; 'Download free colour figma #5b6bd6 vs build #312e81'; figma-only 'See pricing'; boxes 'Frame 479:125 width 1248 vs 1092, height 337 vs 3…
  - Fix: HomeView.vue:679-716: background var(--gradient-cta), remove box-shadow, H2 44/50/700, sub 19/28 #dbe0fa, white button with --sc-primary label, second button label 'See pricing' with 1px rgba(255,255,255,.5) border and transparent fill; section padding 90/96.
  - Linked: 17tnw2b2cex
- **home-42** · class **C** · high · page — Build-only capability claims the repo cannot back (NDI 5, alpha, Wirecast, 4K, 60fps, internal NFR ids)
  - Figma: Figma's NDI copy says 'NDI source for OBS or vMix', 'NDI output - broadcast to OBS, vMix, or another machine'; it draws '1920 × 1080' only; no 'NDI 5', no alpha, no Wirecast, no 4K, no 60fps.
  - Build: 'Direct NDI 5 broadcast streams to OBS, vMix, and Wirecast with transparent lower thirds' (feature card, HomeView.vue:183), 'NDI 5 Stream · Alpha Channel' and 'Display 2 · 1920x1080 · 60fps' (OutputManagerMockup.vue:19,43), 'Full 4K resolution' and 'Direct IP feed with alpha channel transparency' (HomeView.vue:243,251), 'NDI 5 direct broadcast streaming' (Pro bullet), 'Hardware frame buffer holds the last-good image' and '(NFR-024)/(NFR-015)' shown to visitors (:207,:214), 'zero lag' (:221), 'W…
  - Evidence: crates/selahcue-desktop/Cargo.toml:43 'grafton-ndi (Apache-2.0; NDI SDK 6). OFF by default' and ADR-0013 ('6.x EULA'), so 'NDI 5' is wrong; video_sink.rs sends RGBA frames but the transparent-output path is only a spike (ADR-0004 S3, FR-048 R2); Wirecast appears nowhere in docs or code outside the …
  - Decision: Owner (binding rule: honest content wins): remove 'NDI 5', alpha / transparent lower thirds, Wirecast, 4K, 60fps, 'zero lag', 'hardware', the NFR ids and 'Whisper AI' from the copy and mock sub-lines; describe NDI only as 'NDI output for OBS or vMix' and only if the shipped installer includes the NDI runtime (ADR-0013 legal gate OD-06/08 is still open).
  - Linked: 17tnw2b0x3h
- **home-43** · class **C** · medium · page — 'Computed entirely on-device' and '100% offline speech-to-text' overstate the AI privacy position
  - Figma: Feature 6 (472:165 block): 'AI that assists but never gates: live captions and spoken-scripture suggestions, computed entirely on-device.' FAQ 1: 'Internet is only needed to download the app or extra Bible translations.'
  - Build: Feature 6: '100% offline speech-to-text powered by local Whisper AI without relying on cloud services.' (HomeView.vue:188); FAQ: 'All core features ... run 100% locally'.
  - Evidence: implementation/desktop/CLAUDE.md: the dev launch builds with 'cloud (Deepgram) STT' and 'openai-notes' ON and Settings chooses the recognizer; docs/legal/LEGAL-DRAFT-NOTES.md section 9.2 #8: local recognition is real but the model downloads from Hugging Face on first use and Windows builds are CPU-…
  - Decision: Owner: reword to the true position, e.g. 'Live captions run on-device by default; cloud providers are opt-in', and add the first-use model download to the FAQ 'internet' answer.
  - Linked: 17tnw2b0x3h
- **home-44** · class **D** · medium · page · a11y — Figma's own small coloured text fails AA (brand ink, LIVE, white initials on green and gold)
  - Figma: Drawn colours: eyebrows and 'MOST POPULAR'/'MAIN' tags in #5b6bd6 on #0e1116 / #171b22 / #1e232c = 4.07 / 3.72 / 3.39:1 (13px, 10px, 9.5px bold); LIVE #ef4444 on #1e232c = 4.19:1 (10.5px); testimonial avatars 478:140 / 478:148 draw white 14/700 initials on #2bb673 (2.61:1) and #f2b53c (1.83:1).
  - Build: The build copies the avatar failure ('MD' white on #2bb673 2.61:1, 'PP' white on #f2b53c 1.83:1, both in the report's failing list) and its LIVE mock label is 3.89:1; the eyebrows currently render white by accident (home-10), so they pass only because the variant is broken.
  - Evidence: Computed from the style dump: contrast(#5b6bd6,#0e1116)=4.07, (#5b6bd6,#171b22)=3.72, (#5b6bd6,#1e232c)=3.39, (#ef4444,#1e232c)=4.19, (#ffffff,#2bb673)=2.61, (#ffffff,#f2b53c)=1.83; report.json contrast_survey home: 'MD' 2.61, 'PP' 1.83, '● LIVE' 3.89.
  - Decision: Uma: choose accessible inks for small brand text (e.g. a lighter brand tint such as the #a5b4fc already used in the hero pill, 8.96:1), for LIVE/READY chips, and dark initials on the green/gold avatars (#0e1116 gives >7:1). This decides the fix for home-10 and home-15.
- **home-45** · class D · duplicate of **shared-chrome-35** — Home FAQ 'Which platforms are supported?' says Linux is on the roadmap; product says it is available

### Pricing — `pricing` (Figma `483:124`)

Verdict: **diverges** · area: marketing-core · route: `/pricing`

The page keeps Figma's order (hero, billing toggle, three plan cards, comparison table) but almost every section differs: the hero copy and eyebrow, the card geometry and styling, the toggle control and the whole comparison table are not what Figma draws, and the build adds a FAQ the design does not have. The worst defects are real bugs: the Church card shows '$0 / month' instead of 'Custom', all three plan buttons do nothing, 'MOST POPULAR' and 'Save 20%' do not render as badges, and muted text fails AA.

- **pricing-01** · class **A** · high · page — Hero copy and structure differ (no eyebrow, different headline and subline)
  - Figma: Frame 483:139 (y79-449, pad 80/96/8, gap 16): eyebrow 'PRICING' 13/700, +0.3 tracking, brand #5b6bd6 (no pill); H1 'Pricing that grows with your church' 52px/56 lh/700, centred, wraps to 2 lines (box 465w); subline 18/27 muted #9aa4b2, 660w: 'Start free forever. Upgrade to Pro for streaming and multi-output. Cancel anytime — the app always runs fully offline during your service.'
  - Build: src/views/PricingView.vue:48-62: no eyebrow; H1 'Choose the plan that's right for your church' 48px/700, line-height 72 (inherited 1.5), one line; subline 'Transparent pricing with no hidden fees.' 20/30 in --sc-text-muted #6b7383. The toggle starts at y315 and the cards at y387, so the hero is ~102px shorter than Figma (cards at y489).
  - Evidence: python3 scripts/vp_style_diff.py --slug pricing: 'in the design, not in the build' y=191 52x700 'Pricing that grows...', y=319 18x400 'Start free forever...'; 'in the build' y=155 48px 'Choose the plan...', y=240 20px 'Transparent pricing...'; PRICING [exact] copy-case 'PRICING' vs 'Pricing' 13/700…
  - Fix: In PricingView.vue replace the hero with the Figma content: add the eyebrow 'PRICING' (13/700, 0.3px tracking, brand ink), H1 52/56/700 (use --font-h1 sizing, not the inherited 1.5 line-height), subline 18/27 in --sc-text-secondary, max-width ~660. Restore the 16px hero gap and 40px section top padding so the cards start at y489.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **pricing-02** · class **A** · high · page — Third plan card prints '$0 / month', a price nobody decided; Figma's 'Custom' tier is not shipped until D1 closes
  - Figma: Church card 483:214: plan name 'Church', price text 'Custom' 44/700 in the price slot (170w), no period text, description 'For multi-site teams and larger ministries.'
  - Build: src/views/PricingView.vue:28-35 declares the Church plan with price: 0, period: 'month'; PricingCard.vue:26-29 renders every numeric price as '$' + value + '/ period', so the Church card reads '$0 / month' (and stays $0 when Annual is toggled because the discount only applies when price > 0). A string price renders .price-val.custom at 36px (PricingCard.vue:99-101) instead of Figma's 44.
  - Evidence: vp_style_diff pricing, 'in the build, not in the design': y=468 44px '$0' (price-val) and y=496 15px '/ month' (price-period) with no Figma pair; slice pricing-0.png (Church card).
  - Fix: Stop printing a numeric price on the third card: in PricingView.vue pass a string for the price slot (PricingCard already renders a string as .price-val.custom, so no card change is needed) and make it 44/700 as Figma draws it. Do NOT build a 'Church' or 'Custom' tier or name: the tier set and names are open (pricing-15; DEC-008 decides Free/Pro/Platinum and leaves prices and names to D1). Until D1 closes the string is an honest 'Pricing to be announced' (or drop the card); the layout, slot size and spacing still follow the frame. Annual must not change it.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **pricing-03** · class A · duplicate of **home-32** — Plan call-to-action buttons do nothing (no destination, no handler)
- **pricing-04** · class **A** · high · shared · ui-badge — 'MOST POPULAR' renders as unstyled text, straddling the card edge instead of a pill in the header row
  - Figma: 483:180: pill 103x22, fill #1e232c, radius 999, padding 5/11, text 10px/700, +0.1 tracking, brand #5b6bd6; sits in the Pro card's header row, right-aligned on the same line as 'Pro' (x787-890, y523).
  - Build: PricingCard.vue:19-21 uses <UiBadge variant="accent">; UiBadge only accepts live|preview|ready|ndi|featured|new (UiBadge.vue:5-8), so 'accent' gets no variant styling: dom shows class 'ui-badge variant-accent size-sm', colour #f4f6fb, no fill, 11px/600, 0.55px tracking, absolutely positioned top:-14px right:24px (PricingCard.vue:72-76) over the card's top border.
  - Evidence: dom pricing.blink.dom.json item cls 'ui-badge variant-accent size-sm' (bgg true, colour rgb(244,246,251)); vp_style_diff MOST POPULAR: font-size 10 vs 11, font-weight 700 vs 600, letter-spacing 0.1 vs 0.55, colour #5b6bd6 vs #f4f6fb; slice pricing-0.png.
  - Fix: Add a real accent variant to UiBadge (fill --sc-elevated, brand ink) or reuse 'featured', and move the badge into the card header row (flex, space-between) at 10/700. See pricing-21 for the contrast caveat on Figma's brand-on-elevated ink.
  - Linked: 17tnw2b2cew
- **pricing-05** · class **A** · medium · page — Billing toggle is a switch with plain labels; Figma draws a segmented pill, and the 'Save 20%' badge never renders
  - Figma: 483:144/143: segmented pill 257x42, fill #1e232c, 1px #2b323d, radius 999, 4px inset; selected segment 483:145 90x34 filled #5b6bd6, radius 999, label 'Monthly' 13.5/600 white; unselected 'Annual · save 20%' 13.5/600 muted #9aa4b2. Only the Monthly-selected state is drawn.
  - Build: PricingView.vue:53-60: 'Monthly' text, a 50x24 slider switch (.switch/.slider, lines 192-239), then 'Annual <UiBadge text="Save 20%" variant="accent"/>'. UiBadge has no `text` prop and the badge has no slot content, so it renders an empty pill: the dom shows 'Annual' only. Labels are 16/400 #f4f6fb, both identical in weight and colour, so nothing marks the active side except the knob.
  - Evidence: dom pricing.blink.dom.json: spans 'Monthly' (16/400) and 'Annual' (box 74.8w holding only 'Annual'); vp_style_diff Monthly: font-size 13.5 vs 16, weight 600 vs 400; design-only 'Annual · save 20%' y=412.
  - Fix: Rebuild the control to Figma's STRUCTURE: a segmented pill with two segments, the active one filled with the brand colour and white 13.5/600 text, the inactive one muted, with a group name and arrow-key operation (pricing-06). The wording follows pricing-18, not the frame: label the segments 'Monthly' and 'Annual' and ship NO discount ('Save 20%' / 'Annual · save 20%') until an annual price exists and the owner has decided it; remove the empty UiBadge rather than filling it.
  - Linked: 17tnw2b2cey
- **pricing-06** · class **A** · medium · page · a11y — Billing toggle has no accessible name and no group semantics
  - Figma: Figma draws two named options ('Monthly', 'Annual · save 20%') in one pill: reads as a two-option choice.
  - Build: PricingView.vue:55-58: <label class="switch"><input type="checkbox" v-model="isAnnual"/><span class="slider"/></label>. The label wraps only the slider, 'Monthly'/'Annual' are separate sibling spans, so the checkbox has no accessible name; the input is width:0/height:0/opacity:0 with the focus ring on the sibling .slider. (The harness focus list skips it because it is zero-sized, but it is natively focusable.)
  - Evidence: Source read of PricingView.vue:53-60; dom focus list for pricing has no entry between 'Download free' (nav) and the first card button.
  - Fix: Render the pill as role=radiogroup with two labelled radios (or buttons with aria-pressed), arrow-key operable, accessible names 'Monthly' / 'Annual'; announce the price change in an aria-live region.
  - Linked: 17tnw2b2cey
- **pricing-07** · class **A** · medium · page — Plan card geometry and chrome differ (width, height, radius, padding, Pro card glow)
  - Figma: 483:149 row: three cards 400 wide, gap 24, spanning x96-1344. Free/Church 408 high, Pro 495 high (six bullets), top-aligned. Radius 18, border 1px #2b323d, fill #171b22, padding 32/30. Pro 483:177: border 2px #5b6bd6, fill #171b22, padding 34/30, no shadow.
  - Build: PricingView.vue:244-248 + PricingCard.vue:55-70: container max-width 1200 so cards are 362.7 wide, gap 32, all stretched to 467.9 high; radius 20; padding 36/30; fill hard-coded #12151e; Pro card has 1px border, a 0 0 40px violet glow plus a 0 20px 40px black shadow and a gradient fill #161926>#12141e.
  - Evidence: vp_style_diff boxes: Frame 483:150 width 400 vs 362.7, height 408 vs 467.9, radius 18 vs 20; Frame 483:177 border-width 2 vs 1, fill #171b22 vs #0e1116, height 495 vs 467.9.
  - Fix: Cards: width 400 (grid of three, 24 gap, 1248 content width), radius 18, padding 32/30, fill --sc-surface; Pro 2px --sc-primary border with no glow; align-items:start so Pro is taller than the others as drawn.
  - Linked: 17tnw2b2cey
- **pricing-08** · class **A** · medium · page — Plan card typography and colours differ and bypass the tokens
  - Figma: Plan name 17/600 primary #eef1f6; price 44/700; period '/ forever' 15 muted #9aa4b2; description 15/22 muted; features 14/20 muted #9aa4b2 with 11px gap; check = 10.6x7.8 vector stroke #2bb673 (1.84).
  - Build: PricingCard.vue:78-149: plan name 22/800 #ffffff; price 44/800 #ffffff; period 15px #717d93; description 14px #8c97a8 (line-height 1.5, min-height 42); feature text 14px #c5cedc, gap 14; check is the glyph character '✓' 14/800. Every colour is hard-coded hex rather than a --sc-* token.
  - Evidence: vp_style_diff: Free font-size 17 vs 22, weight 600 vs 800; $0 weight 700 vs 800; '/ forever' and '/ month' colour #9aa4b2 vs #717d93 (4.39:1 on the card, fails AA, see pricing-13).
  - Fix: Plan name 17/600 --sc-text; price 44/700; period and description 15/22 --sc-text-secondary; features 14/20 --sc-text-secondary, 11px gap; replace the ✓ glyph with a stroke icon in --sc-preview; remove the hard-coded hex.
  - Linked: 17tnw2b2cey
- **pricing-09** · class **A** · high · page — Card descriptions and bullet lists use different copy and different bullet counts
  - Figma: Free (4): Live audience output + stage display / Bundled public-domain scripture + search / Service plans, timers & themes / One physical output. Pro (6): Everything in Free / NDI + multiple simultaneous outputs / Mobile control over your local network / Theme Designer & saved templates / On-device transcript & scripture detection / Always on the latest version. Church (4): Everything in Pro / Multi-campus / site licensing / Guided onboarding & training / Priority support. Descriptions: 'Everyt…
  - Build: PricingView.vue:9-37: Free (3): Basic presentation / Built-in Bible / Offline support. Pro (4): Multi-screen output / NDI support / Stage monitor / Priority support. Church (4): Unlimited campuses / Enterprise deployment / Custom integrations / 24/7 SLA. Descriptions: 'Everything you need to get started' / 'For churches ready to go further' / 'For multi-campus and enterprise'. Build-only claims with no repo backing: 'Priority support' (Pro), '24/7 SLA', 'Custom integrations', 'Unlimited campuse…
  - Evidence: vp_style_diff 'in the design, not in the build' y=752..932 (14x400 bullets) and y=631/634 descriptions; 'in the build' y=531.5 plan-desc, y=696.5-799.3 bullets.
  - Fix: Rebuild the cards to Figma's STRUCTURE (card geometry, type, spacing, bullet rhythm, Pro-first on mobile) with wording that follows pricing-15/16/18, not the frame. Backed today (DEC-008): tiers Free/Pro/Platinum; outputs 2/5/10; NDI outputs none/5/10; speech-to-text 30 min/5 h/10 h; a watermark on all Free output; 1/3/7 seats; prices and tier names open under D1. So do NOT copy Figma's 'One physical output' (Free gets 2), 'Always on the latest version', 'Priority support' or 'Guided onboarding' (no source), and drop the build's '24/7 SLA', 'Priority support', 'Custom integrations', 'Unlimite…
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **pricing-10** · class **A** · high · page — Comparison table is a full-bleed band with a different layout, heading and header treatment
  - Figma: 484:124/126: heading 'Compare every plan' 32/700 centred; a contained card 1040 wide at x200, radius 16, 1px #2b323d border, fill #171b22; header band 484:127 45px high, fill #1e232c, 'PLANS' 12/700 +0.1 tracking muted caps, plan names 'Free'/'Pro'/'Church' 15/600 centred over 150px columns; 10 rows 48px high with 1px hairlines; first column 14.5/500 primary; value cells centred.
  - Build: PricingView.vue:83-149, 250-300: <section class="comparison-section"> with a --sc-surface band across the full 1440 width (y935, 855 high) behind a 1152-wide table; heading 'Compare features' 40/700; header row 'Feature | Free | Pro | Church' 17.6/600 left-aligned (th padding 20); body rows 65px high, 16/400, left-aligned cells, even rows get rgba(0,0,0,0.02).
  - Evidence: vp_style_diff boxes: Frame 484:126 width 1040 vs 1440, height 525 vs 855.4, radius 16 vs 0, border 1px vs none; Frame 484:127 fill #1e232c vs #14161d, height 45 vs 855.4; Compare every plan 32/700 vs 'Compare features' 40/700; slice pricing-1.png.
  - Fix: Wrap the table in a 1040-wide card (radius 16, 1px --sc-border, --sc-surface fill) on the page background (drop the full-bleed band), header band --sc-elevated 45px with 'PLANS' label (12/700, 0.1px, muted caps) and centred 15/600 plan names, rows 48px with centred value cells; heading 'Compare every plan' 32/700.
  - Linked: 17tnw2b2cey
- **pricing-11** · class **A** · medium · page · a11y — Comparison check marks are white glyphs, not green icons (undefined colour token)
  - Figma: 484:139 etc.: stroke check vectors 11.9x8.7, stroke #2bb673 (2.06) centred in the Free/Pro/Church cells; the simultaneous-outputs row shows accent text '1' / 'Unlimited' 13.5/600 #5b6bd6.
  - Build: PricingView.vue:278-281 colours .check with var(--sc-success), which is not defined in tokens.css, so the colour falls back to the inherited #f4f6fb: the dom shows td.check colour rgb(244,246,251), 16/700, glyph '✓'. There is no accent-numeric cell style at all.
  - Evidence: dom pricing.blink.dom.json td cls 'check' colour rgb(244, 246, 251); grep '--sc-success' src/assets/styles/*.css finds no definition; slice pricing-1.png.
  - Fix: Use --sc-preview for the check (stroke icon, not a text glyph) and add the accent numeric cell style (13.5/600, brand ink). Also add visually hidden 'Included' / 'Not included' text so the table is not read as bare glyphs.
  - Linked: 17tnw2b2cey
- **pricing-12** · class **A** · high · page — Comparison rows list different features and a different number of rows
  - Figma: 10 rows: Live output + stage display; Bundled scripture + keyword search; Service plans, timers & themes; Simultaneous physical outputs (1 / Unlimited / Unlimited); NDI streaming output; Mobile control over your network; Theme Designer & saved templates; On-device transcript & detection; Multi-campus / site licensing; Onboarding & priority support.
  - Build: PricingView.vue:97-144, 8 rows: Audience Output; Offline Support; Built-in Scripture; Stage Monitor; NDI Output; Timers & Clocks; Priority Support; Custom SLA. 'Custom SLA' is an unbacked claim.
  - Evidence: vp_style_diff design-only y=1219..1651 (14.5x500 row labels) vs build-only y=1212.3..1667.3 'Audience Output' ... 'Custom SLA'.
  - Fix: Rebuild the comparison table to Figma's STRUCTURE (full-bleed band, header treatment, row height, check and dash icons, column widths) with row labels and cell values that follow pricing-15/16, not the frame. Keep rows the repo backs (live output and stage display, bundled scripture and search, service plans and timers, simultaneous outputs with the DEC-008 values 2 / 5 / 10, NDI output none / 5 / 10, mobile control, Theme Designer, on-device transcript) and leave out or mark 'to be confirmed' the rows with no source ('Multi-campus / site licensing', 'Onboarding & priority support', 'Unlimite…
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **pricing-13** · class **A** · high · page · a11y — Muted text on the pricing page fails AA where Figma's muted ink passes
  - Figma: Figma muted text is #9aa4b2 (maps to --sc-text-secondary #a7aebe under AUTH-LANDING-PAGES-HANDOFF 2.2): 7.50:1 on #0e1116 and 6.85:1 on #171b22.
  - Build: The build uses --sc-text-muted #6b7383 (and card hex values) for the same roles: subline 'Transparent pricing with no hidden fees.' 20px 4.08:1; '/ forever' and '/ month' 15px #717d93 on the card 4.39:1; the six comparison dashes 16px 3.79:1 on --sc-surface; footer copyright 14px 3.79:1. Required 4.5:1.
  - Evidence: report.json contrast_survey (capture pricing): 4.08, 4.39 x2, 3.79 x6 (all 'reported', required 4.5); vp_style_diff colour lines for '/ forever' (#9aa4b2 vs #717d93) and the dashes (#9aa4b2 vs #6b7383). Contrast computed: #6b7383 on #14161d = 3.79, on #0b0d12 = 4.08; #a7aebe on #0b0d12 = 8.74.
  - Fix: Use --sc-text-secondary for these roles (subline, period, dashes, descriptions). The footer copyright is a shared-chrome item (see pricing-24).
  - Linked: 17tnw2b2cey
- **pricing-14** · class **A** · low · page — Content column is narrower than Figma (1200 container vs 96px gutters on a 1440 frame)
  - Figma: All sections span x96-1344 (1248 wide, 96px side padding): cards at x96/520/944, table card centred 1040.
  - Build: PricingView.vue:163-167 .container max-width 1200 + --page-gutter 48 -> content x144-1296 (1152 wide). Left edges sit ~49px right of Figma's.
  - Evidence: vp_style_diff paired texts: Free and $0 x +49.0 px (figma 126.0, build 175.0); Church x -9.7 px.
  - Fix: Set the shared page container to 1248 max with 96px side padding at 1440 (this applies to all four pages and should be fixed once, with the app-shell/container token).
  - Linked: 17tnw2b2cey
- **pricing-15** · class **C** · high · page — Plan names, prices and the 'Free forever / $19 per month / Custom' structure are assumed, and the tier set contradicts DEC-008
  - Figma: Free '$0 / forever'; Pro '$19 / month', 'MOST POPULAR'; Church 'Custom'; copy 'Start free forever... Cancel anytime'.
  - Build: Build shows the same numbers (Free $0 forever, Pro $19 / month, Church mis-shown as $0 / month). MARKETING-SITE-HANDOFF sections 2 and 8 mark all pricing figures and the tier set 'Assumed'. Repo evidence: DECISION-LOG DEC-008 decides Free / Pro / Platinum (not Church), price points and tier naming 'still open (D1)'; Platform PRD FR-544/545 make tier names data, not copy.
  - Evidence: grep: docs/decisions/DECISION-LOG.md DEC-008 ('Still open in D1. Pricing/price points ... tier naming'); docs/design/MARKETING-SITE-HANDOFF.md lines 96 and 160; no price in implementation/api catalogue seeds.
  - Decision: Owner: do we publish any price and tier name now? If not, keep Figma's card layout but show no price figure and no 'Church' tier until D1 closes. Do not argue the number here.
  - Linked: 17tnw2b0x3h
- **pricing-16** · class **C** · high · page — Feature-to-tier assignments in the cards and comparison table contradict the decided entitlement table
  - Figma: Figma: Free = 'One physical output', no NDI, no mobile control, no Theme Designer, no transcript; Pro = 'Unlimited' outputs, NDI, mobile control, Theme Designer, on-device transcript, 'Always on the latest version'; Church = multi-campus / site licensing, guided onboarding, priority support.
  - Build: Build repeats a different invented set (Pro 'Priority support'; Church '24/7 SLA', 'Custom integrations', 'Unlimited campuses', 'Enterprise deployment'). DEC-008 (docs/decisions/DECISION-LOG.md) decides: screens/outputs Free 2 / Pro 5 / Platinum 10; NDI outputs none / 5 / 10; STT 30 minutes / 5 hours / 10 hours; watermark on all Free output; seats 1 / 3 / 7. Platform PRD: output counts are data (FR-544), 3+ independent outputs and per-output configuration are R2 (FR-038/039), not shipped.
  - Evidence: DEC-008 table vs Figma rows 'Simultaneous physical outputs' (1 / Unlimited / Unlimited) and 'On-device transcript & detection' (Free dash); no repo source for 'Unlimited', 'Always on the latest version', site licensing, onboarding or priority support.
  - Decision: Owner/Uma: re-derive the cards and the comparison table from the decided entitlement table (2/5/10 outputs, NDI 0/5/10, STT 30 min/5 h/10 h, Free watermark) or mark each row 'to be confirmed'. Free's watermark is a material disclosure the design omits.
  - Linked: 17tnw2b0x3h
- **pricing-17** · class **C** · medium · page — Pro action: Figma 'Get Pro' has no purchase flow behind it; the build's 'Start free trial' invents a trial
  - Figma: Pro card action 483:186: filled brand button 'Get Pro' 15/600 white, full width.
  - Build: PricingView.vue:25 labels it 'Start free trial' (still a dead button, see pricing-03). Platform PRD FR-506 defers trial/conversion terms (D1); the repo has account sign-in, licences and devices but no purchase/checkout path.
  - Evidence: grep 'trial' docs/product/prds/SelahCue-Platform-PRD.md: FR-506 DEFERRED (D1); no checkout in implementation/api or marketing src/lib.
  - Decision: Owner: what does the Pro action do today (sign in to the portal? contact us? waitlist?) and what is it called? Remove 'free trial' unless a trial is decided.
  - Linked: 17tnw2b0x3h
- **pricing-18** · class **C** · medium · page — 'Annual · save 20%' and the Annual price: no annual plan exists in the repo, and the build invents a computed discount
  - Figma: Toggle label 'Annual · save 20%' (483:147) and Pro description 'Billed monthly, or save 20% yearly.' No annual price drawn.
  - Build: PricingCard.vue:27 computes Math.round(price * 0.8) when Annual is selected, so the Pro card shows '$15 / month' with no 'billed yearly' wording; the discount badge itself never renders (pricing-05). grep of the billing and catalogue apps finds no annual/yearly interval; handoff section 8 marks monthly/annual billing 'Assumed'.
  - Evidence: Source read PricingCard.vue:27; grep -i annual|yearly|billing_cycle in implementation/api/selahcue_api/apps/billing and catalogue returns nothing.
  - Decision: Owner: is annual billing real and at what discount? Until decided, remove the toggle's discount behaviour (keep layout) rather than computing a price.
  - Linked: 17tnw2b0x3h
- **pricing-19** · class **D** · medium · page — Annual-selected state of the toggle and cards is not drawn
  - Figma: Only the Monthly-selected state is in frame 483:124; no frame shows the Annual-selected pill, the Pro price, the billing caption or the Church card under Annual.
  - Build: Build switches Pro to $15 and leaves '/ month'; Free and Church are unchanged.
  - Evidence: Frame 483:143 children (one selected segment only); PricingCard.vue:27.
  - Decision: Uma: if annual billing stays (see pricing-18), draw the Annual state: price, 'billed yearly' caption, and how Free/Church read.
- **pricing-20** · class **D** · medium · page — A 'Pricing FAQ' section exists in the build but not in Figma, and its answers carry unbacked claims
  - Figma: Frame 483:124 ends with the comparison table then the footer (MARKETING-SITE-HANDOFF 1a: 'hero + toggle + cards + comparison table + footer'). The FAQ lives on Home only.
  - Build: PricingView.vue:151-158: 'Pricing FAQ' (40px) with 3 accordion items. Answers include 'Prorated charges will apply.', 'Our pricing is already optimized for churches and non-profits.' and 'We accept all major credit cards, PayPal, and ACH transfers for annual plans.' (payment methods and proration are not backed by the repo).
  - Evidence: vp_style_diff 'in the build, not in the design' y=1875.3 'Pricing FAQ', y=2004-2246 questions and answers; dom focus has 3 FAQ buttons after the table.
  - Decision: Uma: keep a pricing FAQ (needs a frame) or remove the section? Either way the payment-method, proration and non-profit answers must go until decided.
  - Linked: 17tnw2b0x3h
- **pricing-21** · class D · duplicate of **account-25** — Figma's brand-coloured small labels fail AA on their pill fills
- **pricing-22** · class A · duplicate of **shared-chrome-01** — Navbar differs from the Home frame on this page (width, height, border, active state, button radius)
- **pricing-23** · class A · duplicate of **shared-chrome-16** — Footer differs from the Home frame (columns, label style, copy, height, fill)
- **pricing-24** · class A · duplicate of **shared-chrome-27** — UiButton radius and weight differ from every Figma action button
- **pricing-25** · class **A** · high · shared · tokens · a11y — Tokens referenced by these views are undefined, and --sc-text-muted fails AA
  - Figma: Figma bg tiers #0e1116 / #171b22 / #1e232c and muted #9aa4b2 (7.50:1 on base).
  - Build: Views reference var(--sc-success) (PricingView.vue:279, check marks) and var(--sc-surface-alt) (DownloadView.vue:214, 307); neither exists in tokens.css, so they silently fall back (white checks; the Download requirements band has no fill). --sc-text-muted #6b7383 is 4.08:1 on --sc-base and 3.79:1 on --sc-surface, below AA for normal text; the tokens file maps Figma's text/muted to --sc-text-secondary, not -muted.
  - Evidence: grep -n '--sc-success\|--sc-surface-alt' src/assets/styles/tokens.css returns nothing; contrast computed #6b7383 vs #0b0d12 4.08, vs #14161d 3.79.
  - Fix: Shared tokens ticket: define --sc-surface-alt (or replace with --sc-surface) and use --sc-preview for success; raise --sc-text-muted to an AA ink (>= 4.5:1 on --sc-surface) or retire it for body text.
  - Linked: 17tnw2b2cev

### Features — `features` (Figma `485:124`)

Verdict: **diverges** · area: marketing-core · route: `/features`

Section order and row alternation match Figma, and both closing buttons go to the right pages, but the hero, all six rows' copy, the product panels and the closing band are different designs: Figma draws abstract skeleton panels with a coloured icon tile, the build draws realistic mockups full of invented claims (4K 60fps, NDI 5, 1080p60, a named pastor). Several of Figma's own claims (unlimited outputs, nothing leaves the machine) are also not backed by the repo.

- **features-01** · class **A** · high · page — Hero: different eyebrow, headline and subline
  - Figma: Frame 485:139 (y79-516, pad 96/96/64, gap 22): eyebrow pill 485:140 97x27 (fill #1e232c, radius 999) with 'FEATURES' 12/700, +1.4 tracking, brand #5b6bd6; H1 'Everything you need to run a confident service' 52/58/700 centred, 2 lines; subline 19/30 muted, 760w: 'From the first slide to the final blessing, SelahCue keeps your scripture, songs, timers, stage display and streaming outputs in one offline-first console — with a phone in your hand as the remote.'
  - Build: src/views/FeaturesView.vue:9-15: badge 'CAPABILITIES DEEP DIVE' (UiBadge featured, 11/600, +0.55 tracking, 3.38:1); H1 'Powerful features for modern worship' 44/800, line-height 66; subline 'Everything you need to run a flawless Sunday service, built into one reliable application.' 18/27 --sc-text-secondary, max-width 640.
  - Evidence: vp_style_diff features: FEATURES copy-case 'FEATURES' vs 'Features', 12/700/+1.4/#5b6bd6 vs 14/400/#a7aebe; design-only y=224 52x700 'Everything you need...', y=362 19x400 'From the first slide...'; build-only y=156 'CAPABILITIES DEEP DIVE', y=198.5 44px 'Powerful features...'. Slice features-0.png.
  - Fix: FeaturesView.vue hero: eyebrow pill 'FEATURES' (12/700, 1.4px tracking, elevated fill), H1 52/58/700 with Figma wording, subline 19/30 --sc-text-secondary at 760 max-width.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **features-02** · class **A** · high · page — All six rows use different headings, paragraphs and bullets
  - Figma: Row headings 30/36/700 sentence case, paragraphs 17/27 muted, three 15.5px primary bullets each: (1) 'Live presentation & outputs' - 'Stage everything in Preview, then Go Live with a single tap...' - Preview → Live with one Go Live / Never-blank guarantee (NFR-024) / Audience + stage from one deck. (2) 'Scripture at your fingertips' - 'A full public-domain translation is bundled in the app...' - Bundled WEB translation, fully offline / Reference parsing + keyword search / Send to Preview, then …
  - Build: FeaturesView.vue:19-207: headings 32/800/40 Title Case ('Live Presentation & Outputs', 'Scripture at Your Fingertips', 'NDI 5 & Multi-Output', 'On-Device AI Transcript'), paragraphs 16/1.6, bullets 15px with a '✓' text glyph; none of Figma's paragraphs or bullets appear. Bullets are different claims, e.g. 'Sub-second fuzzy and reference search', 'Monotonic clock accuracy independent of frame rendering', 'Local GPU hardware acceleration (Metal / Direct3D)'.
  - Evidence: vp_style_diff: 'Live presentation & outputs' copy-case, 30 vs 32, weight 700 vs 800, line-height 36 vs 40; 'NDI & multi-output' vs 'NDI 5 & Multi-Output'; design-only y=656..2466 (17x400 paragraphs, 15.5x400 bullets) vs build-only y=465..2839.
  - Fix: Replace every row's heading, paragraph and bullets with the Figma copy; headings 30/36/700 sentence case, paragraph 17/27, bullets 15.5/19 primary with a 10x7.3 stroke check (#2bb673 1.73). Subject to features-10/11 for the unbacked bullets.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **features-03** · class **A** · high · page — Product panels are realistic invented mockups; Figma draws abstract skeleton panels
  - Figma: Panel frames 486:131/168/205/241/278/315: 548x256, radius 20, fill #171b22, 1px #2b323d, padding 24. Each: window chrome (3 dots 10px red/gold/green + a title chip OUTPUTS/SCRIPTURE/PLANNING/STAGE/STREAMING/ASSIST), a 60x60 radius-16 icon tile in the capability colour (red, brand, gold, green, brand, green) with a white stroke glyph, two skeleton bars 500x14 and 320x14 (radius 7, #1e232c), and two status chips (e.g. LIVE / TIMERS / READY / NDI / ON-DEVICE).
  - Build: FeaturesView.vue:33-205, 318-393: 220px-high mock cards with invented content: 'Audience Output · 4K 60fps' with lyric text, 'Scripture Search · Romans 8:28' with verse text, a 24:13 'SERMON COUNTDOWN', 'Stage Monitor Output' CURRENT/NEXT lyrics, 'NDI Broadcast Feed · 1080p60' with a lower third 'Pastor John Davies', 'Whisper AI · Local Engine'. Panel fills are per-panel hex gradients (#1b1b36>#0e0d21, #12141a, #0b0d12, #000, #090b10, #14161d).
  - Evidence: vp_style_diff 'in the build, not in the design': y=474.1 'Audience Output · 4K 60fps', y=2346.8 'Pastor John Davies' (lt-title), y=1446.2 '24:13', y=2610 'Whisper AI · Local Engine'; boxes list 486:131.. have no build counterpart. Slices features-0/1/2.png.
  - Fix: Rebuild the six panels as the Figma skeleton panels (shared ConsoleMockup-style component: chrome row, 60x60 icon tile in the row colour, two skeleton bars, chips). Remove all mock text, resolutions and the named person.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **features-04** · class **A** · medium · page — Row layout differs: 1140 container, alternating full-bleed bands, 427px rows, type scale
  - Figma: Six rows, each 336px high (pad 40/96, gap 56), full width on the page background with no bands or rules; text column 644 wide at x96 (or x700 on reversed rows), panel 548 wide at x796 (or x96); rows alternate text-left / panel-left as drawn.
  - Build: FeaturesView.vue:225-290: .container max-width 1140 (content x174-1266), grid 2 x 1fr with 60px gap, rows padding 80 -> 427px pitch (page is 396px taller overall: 3803 vs 3407); rows 2/4/6 get a --sc-surface band with top and bottom borders. Order and alternation match Figma.
  - Evidence: dom badge y positions 465.5, 892.7, 1319.9, 1747.1, 2174.3, 2601.4 (pitch 427) vs Figma row tops 516, 852, 1188, 1524, 1860, 2196 (pitch 336); vp_style_diff y-shift lines; slices features-0/1.png.
  - Fix: Rows 336px (pad 40/96, 56 gap), page-background throughout, 644/548 columns; remove the alternating bands and borders.
  - Linked: 17tnw2b2cey
- **features-05** · class **A** · medium · page — Row eyebrow chips use different labels and colours (one off-palette cyan)
  - Figma: Eyebrow pills (fill #1e232c, radius 999, 11/700, +1.1 tracking) with category colours: OUTPUTS #ef4444, SCRIPTURE #5b6bd6, PLANNING #f2b53c, STAGE #2bb673, STREAMING #5b6bd6, ASSIST #2bb673.
  - Build: FeaturesView.vue badges: ZERO-BLANK GUARANTEE (live), SCRIPTURE SEARCH (preview green), BOUNDED WORKFLOW (warn), CONFIDENCE DISPLAY and BROADCAST INTEGRATION ('ndi' variant, cyan #38bdf8, not a Figma colour), LOCAL AI SPEECH (preview). Pill fills for ndi #10222b.
  - Evidence: vp_style_diff STREAMING vs 'NDI STREAMING': colour #5b6bd6 vs #38bdf8, weight 700 vs 600, letter-spacing 1.1 vs 0.55; Frame 486:273 fill #1e232c vs #10222b.
  - Fix: Use Figma's six labels and colours (and the 1.1px tracking); drop the cyan 'ndi' variant on this page.
  - Linked: 17tnw2b2cey
- **features-06** · class **A** · high · page — Closing call-to-action band differs in surface, copy and button styling (destinations match)
  - Figma: Final CTA 486:345/346: gradient panel 1248x337, radius 24, linear #6675e5 > #2b296b, pad 64/48; H2 'Ready to run your best service yet?' 44/50/700 white; subline 19/28 #dbe0fa 'Start free and go live this Sunday. Cancel anytime — and it runs fully offline when it matters most.'; buttons 486:350 white fill 167x49 radius 11 'Download free' (brand text 15.5/700) and 486:352 outline 137x47 radius 11, 1px white 50% alpha, 'See pricing' white 15.5/600.
  - Build: FeaturesView.vue:211-220, 395-399: dark card 1140 wide (surface > #1c1a3a, 1px --sc-primary border, radius 24); H2 'Experience the SelahCue difference' 32/800; subline 'Start free today and experience flawless Sunday services.' 16px; 'Download SelahCue Free' (UiButton gradient, to /download) and 'View Pricing' (outline, to /pricing). Destinations match Figma's intent; labels, fills and shapes do not.
  - Evidence: vp_style_diff design-only y=2686 44x700 'Ready to run...', y=2861 15.5x700 'Download free', 15.5x600 'See pricing'; build-only y=3086.6 32px 'Experience the SelahCue difference'. Slice features-2.png. dom focus: links 'Download SelahCue Free' and 'View Pricing'.
  - Fix: Extract the Figma CTA band (shared with About, 496:181) as one component: gradient #6675e5>#2b296b, 44/50 heading, #dbe0fa subline, white primary + outlined secondary buttons, radius 11; labels 'Download free' -> /download and 'See pricing' -> /pricing.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **features-07** · class **A** · high · page — Build-only capability claims with no repo backing (to be removed with the rewrite)
  - Figma: Figma carries none of these.
  - Build: Build copy and mock text: 'NDI 5' (heading), 'Audience Output · 4K 60fps', 'NDI Broadcast Feed · 1080p60', 'Alpha channel transparency for lower-third overlays', 'Zero capture-card latency over Gigabit Ethernet', 'Wirecast', 'Pastor John Davies' (an invented named person), 'Copyrighted Bible entitlements (NIV, ESV, NLT) post-activation', 'Sub-second fuzzy and reference search', 'Local GPU hardware acceleration (Metal / Direct3D)', 'Whisper AI'. Repo: PRD cites NDI 6.x licensing, 1080p60 and 3+ …
  - Evidence: FeaturesView.vue lines 36, 56-57, 152-156, 164, 168, 184-188, 195; grep NDI 5 / Gigabit / Wirecast / 4K in docs/product/prds returns nothing; PRD line 471 'NDI 6.x EULA'; PRD NFR-005/006 R2.
  - Fix: Delete these strings by adopting the Figma rows (features-02/03). Nothing replaces them.
  - Already owned by ClickUp 17tnw2b0x3h: no fix ticket from this audit.
  - Linked: 17tnw2b0x3h
- **features-08** · class **A** · high · page · a11y — Small text on the features page fails AA (muted ink on dark and elevated fills)
  - Figma: Figma muted #9aa4b2: 7.50:1 on base, 6.25:1 on elevated.
  - Build: Mock window titles 12px/400 --sc-text-muted on --sc-elevated 3.45:1 (x5: 'Audience Output · 4K 60fps', 'Scripture Search...', 'Service Run Sheet...', 'Stage Monitor Output', 'NDI Broadcast Feed...', 'Whisper AI...'); badge 'CAPABILITIES DEEP DIVE' 11/600 3.38:1; 'NEXT' 11px and 'Singing Holy, Holy, Holy' 14px 4.41:1; footer copyright 3.79:1. Required 4.5:1.
  - Evidence: report.json contrast_survey capture features: 3.38, 3.45 x5, 4.41 x2, 3.79.
  - Fix: Most of these disappear with features-03/01. Any remaining muted text must use --sc-text-secondary.
  - Linked: 17tnw2b2cey
- **features-09** · class **A** · low · page — Content column narrower than Figma
  - Figma: Content x96-1344 (1248 wide) at 1440.
  - Build: FeaturesView.vue:230-234 .container max-width 1140 -> x174-1266 (78px inset each side); headings and bullets sit +78px right (Live presentation heading x174 vs 96).
  - Evidence: vp_style_diff Live presentation & outputs: x +78.0 px (figma 96.0, build 174.0).
  - Fix: Same shared container fix as pricing-14.
  - Linked: 17tnw2b2cey
- **features-10** · class **C** · high · page — 'Unlimited virtual outputs' and 'Per-output theme & framing' are not shipped and contradict the decided output caps
  - Figma: Row 5 bullets: 'Unlimited virtual outputs', 'Per-output theme & framing'; pricing table 'Simultaneous physical outputs ... Unlimited'.
  - Build: Build has no equivalent bullet (it says 'Independent graphics styling for house vs. broadcast' and mock '1080p60'). Repo: DEC-008 caps outputs at 2 / 5 / 10 per tier; Platform PRD FR-544 keeps counts as data; Core PRD FR-038/039 (independent per-output config, 3+ outputs) and NFR-005/006 are R2 and spike-gated, not MVP.
  - Evidence: docs/decisions/DECISION-LOG.md DEC-008 table; docs/product/prds/SelahCue-PRD.md FR-038, FR-039, NFR-005/006 (R2).
  - Decision: Owner: keep these two bullets? If kept, reword to what ships (a stated number of outputs per tier, per-output theme only when FR-038 lands) and do not say 'Unlimited'.
  - Linked: 17tnw2b0x3h
- **features-11** · class **C** · medium · page — 'An optional live transcript runs entirely on the machine — nothing leaves the building' is stated as absolute
  - Figma: Row 6 paragraph and bullets 'Live transcript, fully on-device' / 'Nothing leaves the machine'.
  - Build: On-device Whisper STT ships (selahcue-stt, bundled by the Windows installer with --features stt), but the repo also has an opt-in cloud speech path (selahcue-stt-cloud / cloud-stt, ADR-0010 'cloud STT remains an opt-in accuracy path') and DEC-008 meters STT hours per tier (30 min / 5 h / 10 h), which only makes sense for a hosted path. The build says 'zero cloud data transmission'.
  - Evidence: implementation/desktop/crates/selahcue-operator/Cargo.toml (stt vs cloud-stt features); ADR-0010 line 'Cloud STT remains an opt-in accuracy path'; DEC-008.
  - Decision: Owner: is the on-device claim unconditional? If cloud transcription can be enabled, say 'on-device by default; cloud only if you turn it on'. Also: is on-device transcript a paid-only feature (Figma) or on Free (30 min per DEC-008)?
  - Linked: 17tnw2b0x3h
- **features-12** · class **D** · low · page — Internal requirement ID 'NFR-024' appears in a customer-facing bullet
  - Figma: Row 1 bullet 'Never-blank guarantee (NFR-024)'.
  - Build: Build prints 'Zero-blank hardware frame buffer protection (NFR-024)'.
  - Evidence: vp_style_diff design-only y=756 'Never-blank guarantee (NFR-024)'; FeaturesView.vue:27.
  - Decision: Uma/owner: NFR-024 is an internal PRD identifier; keep it in public copy or drop it?
- **features-13** · class D · duplicate of **account-25** — Figma's coloured row eyebrows fail AA on their pill fill

### Download — `download` (Figma `487:124`)

Verdict: **diverges** · area: marketing-core · route: `/download`

Section order matches Figma (hero, platform cards, requirements, mobile control, install steps) and the disabled download and store controls are a documented honest deviation, but every section is laid out and styled differently: centred 400px cards with emoji icons instead of 610px left-aligned cards, a bullet list instead of the label/value requirement cards, an empty placeholder phone, and no eyebrow, trust line or mobile bullets. The system-requirement figures, installer details and mobile availability in Figma are not backed by the repo, and the build's own figures disagree with Figma and the PRD.

- **download-01** · class **A** · high · page — Hero: different headline, no eyebrow, no body paragraph, no trust line
  - Figma: Frame 487:139 (y79-495, pad 96/96/40, gap 20): eyebrow pill 487:140 107x27 'DOWNLOAD' 12/700 +1.4 brand; H1 'Get SelahCue for your platform' 52/58/700 centred (432w, 2 lines); paragraph 19/30 muted 720w 'Free to start, fully offline, no account required. Pick your desktop platform below — mobile control pairs over your local network in seconds.'; trust line 14/400 muted 'Free to start · Works fully offline · No account required'.
  - Build: src/views/DownloadView.vue:7-12: H1 'Download SelahCue' 48/700 (line-height 72); one line 'Start presenting with total confidence.' 20/30 in --sc-text-muted (#6b7383, 4.08:1, fails AA); no eyebrow, no paragraph, no trust line.
  - Evidence: vp_style_diff download: DOWNLOAD copy-case, 12/700/+1.4/#5b6bd6 vs 14/400/#a7aebe; design-only y=222 52x700 'Get SelahCue...', y=358 19x400, y=438 14x400 trust line; build-only y=155 48px 'Download SelahCue', y=240 20px. Slice download-0.png.
  - Fix: Rebuild the hero with the Figma eyebrow, 52/58 H1, 19/30 paragraph and trust line (--sc-text-secondary for muted).
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **download-02** · class **A** · high · page — Platform cards: different size, alignment, icons and type
  - Figma: 487:146 row: two cards 610x316 (gap 28, x96-1344), radius 20, fill #171b22, 1px #2b323d, padding 32; left-aligned: 64x64 radius-16 brand tile with a white stroke glyph (four-square grid for Windows, laptop for macOS), title 26/700, subline 15/22 muted ('Windows 10 & 11 · 64-bit' / 'macOS 12 Monterey+ · Apple silicon & Intel'), full-width action 546x47 radius 12 brand fill with download icon, caption 13 muted.
  - Build: DownloadView.vue:14-48, 178-210: two 400x418 cards centred in the row, radius 12, text centred, emoji icons 🪟 and 🍎 at 64px (rendering varies by OS font), title 24, subline 16px --sc-text-muted (3.79:1 on the card, fails AA), pill-shaped auto-width button (disabled, see download-03), caption 14px.
  - Evidence: vp_style_diff boxes: Frame 487:147 width 610 vs 400, height 316 vs 418, radius 20 vs 12; Windows font-size 26 vs 24; 'Windows 10 & 11 · 64-bit' text-align left vs center, 15 vs 16, colour #9aa4b2 vs #6b7383. Slice download-0.png.
  - Fix: Cards 610x316 side by side (28 gap), left-aligned, radius 20, 64px brand icon tile with SVG stroke glyphs (not emoji), title 26/700, subline 15/22 --sc-text-secondary, full-width radius-12 action (disabled state per download-03).
  - Linked: 17tnw2b2cey
- **download-03** · class **B** · high · page — Download buttons are disabled with 'Not available to download yet' instead of live buttons plus a version/size caption
  - Figma: Figma draws live primary buttons 'Download for Windows' / 'Download for macOS' (with a download icon) and captions 'v1.0 · .msi installer · ~84 MB' / 'v1.0 · universal .dmg · ~92 MB'.
  - Build: DownloadView.vue:21-47: both buttons are disabled, aria-disabled, aria-describedby the status line 'Not available to download yet' (--sc-text-secondary); the version line was replaced with the real status. They are not focusable (correct for a disabled control).
  - Evidence: dom download.blink.dom.json focus list has no button between nav and footer; tests/downloadView.test.ts asserts every button is disabled or wired; view comment lines 21-27.
  - Source: ClickUp 17tnw2b0q9j / PR #134 (honest disabled download controls); DownloadView.vue comment lines 21-27 (downloads backend not built, ClickUp 86ak10afm, endpoints return 501); tests/downloadView.test.ts
- **download-04** · class **C** · high · page — Installer version, format, size and OS-floor claims on the platform cards are unbacked
  - Figma: 'v1.0 · .msi installer · ~84 MB', 'v1.0 · universal .dmg · ~92 MB', 'Windows 10 & 11 · 64-bit', 'macOS 12 Monterey+ · Apple silicon & Intel'.
  - Build: Build shows no version or size (disabled state) but still states 'Windows 10 / 11 (64-bit)' and 'macOS 11.0 or later (Intel & Apple Silicon)', which also disagrees with Figma's macOS 12. Repo: operator version is 0.1.0 (crates/selahcue-operator/tauri.conf.json); bundle target is only 'nsis' and CI uploads *-setup.exe (.github/workflows/windows-installer.yml:218) - there is no .msi, no macOS bundle, no .dmg, no recorded installer size, and no documented macOS or Windows minimum version.
  - Evidence: tauri.conf.json bundle.targets ['nsis']; grep .dmg / notariz / universal in docs, workflows and src returns nothing; docs/ops/WINDOWS-INSTALLER.md.
  - Decision: Owner: what are the shipped formats and supported OS floors? Product (owner, 2026-10-04): SelahCue is available for Windows, Linux and macOS. The repo packages only a Windows NSIS .exe, so is a macOS or Linux installer downloadable today? Show no version or size until a release exists. macOS floor: Figma says 12 Monterey+, the build says 11.0 (keep this finding).
  - Linked: 17tnw2b0x3h
- **download-05** · class **C** · high · page — System requirements: Figma, the build, the PRD and the owner requirement all disagree; the repo has no single backed figure
  - Figma: Minimum: Dual-core 2 GHz / 4 GB RAM / Integrated GPU / 500 MB free / One output (audience). Recommended: Quad-core 3 GHz+ / 8 GB RAM or more / Discrete GPU (NDI / multi-out) / SSD 1 GB free / Audience + stage display.
  - Build: Build minimum: OS Windows 10 / macOS 11, CPU Intel Core i3, RAM 4GB, Storage 500MB, Graphics DirectX 10 capable. Recommended: OS Windows 11 / macOS 13+, CPU Intel Core i5 / Apple M1, RAM 8GB+, Storage 2GB SSD, Dedicated GPU for NDI. Repo: SelahCue-PRD.md reference hardware tiers (line 373): Tier A (minimum) = quad-core CPU, 8 GB RAM, integrated GPU; Tier B (recommended) = 6-core+, 16 GB, discrete GPU or Apple Silicon. Owner requirement 2026-10-03: minimum hardware 4 GB RAM / 250 GB disk. No sou…
  - Evidence: docs/product/prds/SelahCue-PRD.md line 373 (Tier A / Tier B); owner requirement per audit brief; Figma 488:127/145 vs DownloadView.vue:56-75.
  - Decision: Owner: choose the published minimum and recommended specs (RAM 4 GB vs PRD Tier A 8 GB is the headline conflict). Not picking a number here; the page should carry only figures the repo backs.
  - Linked: 17tnw2b0x3h
- **download-06** · class **A** · high · page — System requirements section: different structure, headings and rows; band fill token undefined
  - Figma: Band 488:124 full width (y883-1395, 512 high, fill #171b22) with heading 'System requirements' 32/700; cards 488:127/145 610x349, radius 18, fill #0e1116, border #2b323d, padding 28; each starts with a chip (MINIMUM muted 11/700 +0.9; RECOMMENDED green #2bb673) then five label/value rows 38px high with hairlines: label 14.5/400 muted left, value 14.5/600 primary right-aligned (Processor, Memory, Graphics, Storage, Display).
  - Build: DownloadView.vue:52-78, 212-244: heading 'System Requirements' 24px; cards 400 wide, radius 12; h3 'Minimum'/'Recommended' 18.72/700; a <ul> with bold 'OS:' 'CPU:' 'RAM:' 'Storage:' 'Graphics:' labels 16px; no Display row, an extra OS row; the section background is var(--sc-surface-alt), which is undefined, so the band has no fill (pricing-25).
  - Evidence: vp_style_diff boxes: Frame 488:127 width 610 vs 400, height 349 vs 307.1, radius 18 vs 12, fill #0e1116 vs #14161d; MINIMUM/RECOMMENDED copy-case, 11/700/#9aa4b2 and #2bb673 vs 18.72/#f4f6fb; System requirements 32 vs 24. Slice download-1.png.
  - Fix: Build the band with --sc-surface and the 32/700 heading; two 610-wide radius-18 cards with a chip and five label/value rows (Processor, Memory, Graphics, Storage, Display), right-aligned values 14.5/600. Row values are subject to download-05.
  - Linked: 17tnw2b2cey
- **download-07** · class **A** · high · page — Mobile-control section: different layout, no bullets, and a visible placeholder phone
  - Figma: Section 489:124 (y1395-1854, pad 64/96, gap 64): left block (904w): pill 'MOBILE CONTROL' (11/700 +1.1 brand), H2 'Control from your phone' 34/40/700, paragraph 17/27 muted, three 15.5px bullets with green checks ('Pairs over your LAN — no internet or account', 'Available for iOS and Android', 'Desktop stays authoritative if the phone drops'), store badges. Right: controller mock 489:154, 280x305, radius 40: 'Controller' header + 'CONNECTED' chip, 'ON SCREEN NOW' card with 'John 3:16' and two s…
  - Build: DownloadView.vue:80-124, 246-313: no pill, H2 'Mobile Control' 40/700, paragraph 'Control your presentation from anywhere on the stage or in the auditorium...' 17.6px --sc-text-muted (4.08:1 fails AA), no bullets; phone is an empty 300x600 frame (12px #333 border, radius 36) with the visible label 'Mobile App Mockup' (4.08:1).
  - Evidence: vp_style_diff design-only y=1501 'Controller', y=1547 'ON SCREEN NOW', y=1566 'John 3:16', y=1663 'Go Live', y=1721 'Blank', 'Next'; build-only y=1734.1 'Mobile App Mockup' (phone-mockup), y=1673.5 paragraph. Slice download-2.png.
  - Fix: Implement the Figma split: eyebrow pill, 34/40 H2, 17/27 paragraph in --sc-text-secondary, bullets with stroke checks (wording subject to download-09), and the controller mock (SVG/HTML, no placeholder text).
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **download-08** · class **B** · medium · page — Store badges are disabled 'Coming soon' boxes with a note, not live 'Download on' badges
  - Figma: 489:144/149: filled badges (fill #1e232c, 1px #2b323d, radius 12) with a brand dot, caption 'Download on' 10px and 'App Store' / 'Google Play' 15/600.
  - Build: DownloadView.vue:85-118, 270-297: native disabled <button>s with a dashed outline, transparent fill, no hover, status 'Coming soon' and the note 'The SelahCue Controller app is not in the App Store or Google Play yet.' (aria-describedby wired).
  - Evidence: tests/downloadView.test.ts; vp_style_diff boxes Frame 489:144 fill #1e232c vs none, radius 12 vs 8; build-only 'Coming soon' x2 and the note.
  - Source: ClickUp 17tnw2b0q9j / PR #134 (honest disabled store badges); DownloadView.vue comment lines 85-93 (no store listing exists)
- **download-09** · class **C** · medium · page — 'Available for iOS and Android' and the 'Download on App Store / Google Play' badges claim availability the repo does not have
  - Figma: Bullet 'Available for iOS and Android'; badge captions 'Download on' above both 'App Store' and 'Google Play'.
  - Build: Build already says 'Coming soon' (download-08). Repo: mobile store publishing is open work; docs/release/mobile/RELEASE-CHECKLIST.md and STORE-LISTING.md are pre-launch drafts; no listing URL exists.
  - Evidence: docs/release/mobile/*; DownloadView.vue comment lines 85-93.
  - Decision: Owner: reword the bullet to the true status ('iOS and Android apps coming soon' or equivalent) and keep the badges in the disabled state; the Google badge caption 'Download on' should not be reused when real badges ship.
  - Linked: 17tnw2b0q9j
- **download-10** · class **A** · medium · page — Install steps: different heading, card style and copy
  - Figma: Heading 'Up and running in three steps' 32/700; three cards 489:177/182/187 400x197, radius 18, fill #171b22, 1px border, pad 28/26; a 44x44 radius-12 elevated tile holding '01'/'02'/'03' (17/700 brand), titles 19/600 ('Download & install', 'Build your first plan', 'Go live & pair your phone'), bodies 15/23 muted.
  - Build: DownloadView.vue:126-147, 315-352: heading 'Installation Guide' 24/700; steps are centred with 48px filled brand circles (24px numerals '1/2/3'), h4 16/700 ('Download the installer', 'Run the setup wizard', 'Launch and start presenting'), body 16px --sc-text-muted (3.79:1 fails AA); section sits on a full-bleed --sc-surface band.
  - Evidence: vp_style_diff 'Download & install' fuzzy 0.85, font-size 19 vs 16, text-align left vs center; design-only y=1902 32x700, y=2008.5 '01/02/03', y=2092 15x400 bodies; build-only y=2207.1 'Installation Guide', y=2297.1 numerals, y=2394.1 bodies. Slice download-2.png.
  - Fix: Heading 'Up and running in three steps', three 400x197 radius-18 cards with the 44px number tile, Figma titles and bodies (--sc-text-secondary), page background (no band).
  - Linked: 17tnw2b2cey
- **download-11** · class **A** · high · page · a11y — Muted text on the download page fails AA
  - Figma: Figma muted #9aa4b2: 7.50:1 on base, 6.85:1 on the card fill.
  - Build: --sc-text-muted #6b7383 is used for: hero line 20px (4.08:1), 'Windows 10 / 11 (64-bit)' and 'macOS 11.0 or later...' 16px (3.79:1), mobile paragraph 17.6px (4.08:1), store note 15px (4.08:1), 'Mobile App Mockup' 16/700 (4.08:1), three install-step bodies 16px (3.79:1), footer copyright (3.79:1). Required 4.5:1.
  - Evidence: report.json contrast_survey capture download: 4.08 x5, 3.79 x5 (10 failures).
  - Fix: Use --sc-text-secondary for all of these (see pricing-25 for the token).
  - Linked: 17tnw2b2cey
- **download-12** · class **A** · low · page — Content column and section bands differ from Figma
  - Figma: Content x96-1344 (1248 wide); only the requirements band is filled (#171b22); the mobile and steps sections sit on the page background.
  - Build: DownloadView.vue .container max-width 1200 (x144-1296); install-guide has a full-bleed --sc-surface band; cards centred in 400px max-width columns.
  - Evidence: vp_style_diff Frame 489:177 build[0,2124,1440,396] install-guide (band, not a card); boxes widths 610 vs 400.
  - Fix: Shared container fix (pricing-14); remove the install-guide band.
  - Linked: 17tnw2b2cey
- **download-13** · class D · duplicate of **account-25** — Figma's mobile-control and eyebrow labels fail AA on their pill fills
- **download-14** · class D · duplicate of **shared-chrome-35** — The Download page draws no Linux card although product says Linux is available

### About — `about` (Figma `496:124`)

Verdict: **diverges** · area: marketing-core · route: `/about`

Only the closing band and the four-values idea survive from Figma: the hero copy differs, the two-column 'Why we built SelahCue' story section is missing entirely, the values are four different statements in a 2x2 emoji grid instead of one row of icon cards, and the closing band uses an invented 'thousands of churches' claim and a different second button. Muted text and the eyebrow badge fail AA.

- **about-01** · class **A** · high · page — Hero: different eyebrow, headline and subline
  - Figma: Frame 496:139 (y79-492, pad 96/96/48, gap 20): eyebrow pill 496:140 72x27 'ABOUT' 12/700 +1.2 brand; H1 'Built for the people running the service' 50/56/700 centred (476w, 2 lines); subline 19/30 muted 760w: 'SelahCue started with one conviction: the moment a congregation is worshipping is not the moment your software should fail. So we built a church presentation app that stays up, stays offline, and stays out of the way.'
  - Build: src/views/AboutView.vue:9-17: badge 'Our Story & Mission' (11/600, 3.38:1, fails AA); H1 'Reengineering how the church presents the Gospel' 44/800 (line-height 55, wraps to 2 lines at 1092 max); subline 'We built SelahCue because worship leaders and media volunteers deserve tools that are 100% reliable, offline-first, and effortless to operate.' 18/28.8 secondary.
  - Evidence: vp_style_diff about: ABOUT copy-case, 12/700/+1.2/#5b6bd6 vs 14/400/#a7aebe; design-only y=222 50x700 'Built for the people...', y=354 19x400; build-only y=156 'Our Story & Mission', y=196.5 44px 'Reengineering how...', y=329.5 18px. Slice about-0.png.
  - Fix: Eyebrow pill 'ABOUT' (12/700, 1.2px tracking), H1 50/56/700 with the Figma wording, subline 19/30 --sc-text-secondary at 760 max-width.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **about-02** · class **A** · high · page — The 'Why we built SelahCue' two-column story section is missing
  - Figma: Section 496:144 (y492-917, pad 40/96/56, gap 56): left column 596w: H2 'Why we built SelahCue' 30/36/700 at x96,y532; right column 596w at x748: three paragraphs 17/27 muted ('Too many services are one crashed slide away from a blank screen...', 'We wanted the opposite: a desktop-authoritative app where the compositor never blanks live output...', 'That's what SelahCue is — presentation, scripture, timers, stage display and streaming outputs in one console, with a phone in your hand as the remo…
  - Build: AboutView.vue has no story section; the page goes hero -> 'The Principles Behind SelahCue' values grid -> CTA.
  - Evidence: vp_style_diff design-only y=532 30x700 'Why we built SelahCue', y=532/629/753 17x400 paragraphs. Slice about-0.png.
  - Fix: Add the story section: two 596px columns (heading left, three paragraphs right, 16px paragraph gap) with the Figma copy.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **about-03** · class **A** · high · page — Values section: different band, heading, grid, icons and four different values
  - Figma: Band 496:151 full width (y917-1302, fill #171b22, pad 40/96/56, gap 28): H2 'What we stand for' 32/700 centred; four cards in one row 496:154/161/167/173, each 294x222, radius 18, fill #0e1116, 1px border, pad 26/24, gap 14: 52x52 radius-14 tile (green shield, brand wifi, gold sparkle, red gauge; white stroke glyph), title 18/600/24, body 14.5/22 muted. Copy: 'Reliability comes first' / 'Offline by default' / 'AI assists, never gates' / 'Bounded & respectful' with their one-sentence bodies.
  - Build: AboutView.vue:19-50, 99-141: no band; H2 'The Principles Behind SelahCue' 32/700; 2x2 grid (28 gap), cards radius 16, pad 32, emoji icons 🛡️ 📶 ⚡ 📖 at 36px, titles 20/700, bodies 15/24. Different values: 'Never Blank the Screen', 'Offline First, Always', 'Volunteer-Friendly Speed' ('run a service within 5 minutes'), 'Scripture & Rights Protection' ('copyrighted translations are safely entitled and encrypted post-activation').
  - Evidence: vp_style_diff design-only y=957 32x700 'What we stand for', y=1116 18x600 x4, y=1154 14.5x400 x4; build-only y=508.1 'The Principles Behind SelahCue', y=706-984 20px titles, y=638-916 emoji. Slice about-0.png. Repo: PRD METRIC-006 target is time-to-first-slide <= 10 minutes (not 5); copyrighted tra…
  - Fix: Build the full-bleed band and four 294x222 radius-18 cards in one row to Figma's STRUCTURE (SVG icon tiles in green/brand/gold/red, titles 18/600, bodies 14.5/22 muted). Copy follows what the repo backs, not the frame wholesale: 'Reliability comes first' (NFR-024, never blank) and 'Offline by default' (NFR-015) are backed; check 'AI assists, never gates' against the AI ADRs before shipping its body; for 'Bounded & respectful' keep the card and title but ship only the backed part (memory is bounded, NFR-002/003) and leave out 'fast cold start' and 'no account or tracking required' until about-…
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **about-04** · class **A** · high · page — Closing CTA: different surface and copy, an invented community claim, and the second button goes elsewhere
  - Figma: Final CTA 496:180/181: same gradient band as Features (1248x337, radius 24, #6675e5>#2b296b); H2 'Ready to run your best service yet?' 44/50 white; subline 19/28 #dbe0fa 'Start free and go live this Sunday. Cancel anytime — and it runs fully offline when it matters most.'; buttons 'Download free' (white fill, radius 11) and 'See pricing' (outline).
  - Build: AboutView.vue:53-62, 143-176: dark card (surface > #1c1a3a, 1px primary border); H2 'Ready to upgrade your church's presentation?' 32/700; subline 'Join thousands of churches running services with total confidence.' (no repo evidence of any customer count); buttons 'Download SelahCue Free' (to /download) and 'Contact Our Team' (to /contact) - Figma's second action is 'See pricing' (/pricing).
  - Evidence: vp_style_diff design-only y=1456 44x700, y=1528 19x400, y=1631 'Download free' / 'See pricing'; build-only y=1293.1 'Ready to upgrade...', y=1355.1 'Join thousands of churches...', y=1428.1 'Contact Our Team'. dom focus links 'Download SelahCue Free', 'Contact Our Team'. Slice about-1.png.
  - Fix: Use the shared Figma CTA band (see features-06) with the Figma copy; 'Download free' -> /download, 'See pricing' -> /pricing. Remove 'thousands of churches'.
  - Linked: 17tnw2b0x3h, 17tnw2b2cey
- **about-05** · class **A** · high · page · a11y — Small text on the about page fails AA
  - Figma: Figma eyebrow/body inks pass on their fills except the brand eyebrow (see about-07); muted body is 7.50:1.
  - Build: Badge 'Our Story & Mission' 11/600 3.38:1; footer copyright 14px 3.79:1. Required 4.5:1.
  - Evidence: report.json contrast_survey capture about: 3.38 and 3.79.
  - Fix: Removing the badge (about-01) and using the Figma eyebrow ink with an AA fix (about-07) clears the first; footer is shared (pricing-23).
  - Linked: 17tnw2b2cey
- **about-06** · class **A** · low · page — Content column narrower than Figma
  - Figma: Content x96-1344 (1248 wide); story columns at x96 and x748.
  - Build: AboutView.vue .container max-width 1140 with 24px gutters (content x174-1266, 1092 wide); values grid 2 columns.
  - Evidence: dom about.blink.dom.json: h1 box x251.9 w1092 (content column x174-1266) vs Figma H1 box x482 w476 and content x96-1344.
  - Fix: Shared container fix (pricing-14).
  - Linked: 17tnw2b2cey
- **about-07** · class D · duplicate of **account-25** — Figma's 'ABOUT' eyebrow fails AA on its pill fill
- **about-08** · class **C** · low · page — 'Capped memory, fast cold start, and no account or tracking required' states targets and a negative the repo does not evidence
  - Figma: Values card 4 'Bounded & respectful': 'Capped memory, fast cold start, and no account or tracking required.'
  - Build: Build has a different value but similar assumptions elsewhere. Repo: Core PRD NFR-001 sets a cold start target of 3 seconds or less on reference hardware (a target, not a measurement) and NFR-002/003 bound memory; no document states that the app or marketing site does no tracking, and Platform billing/usage attribution exists.
  - Evidence: docs/product/prds/SelahCue-PRD.md NFR-001 (line 377); no 'tracking' or 'telemetry' statement in the PRD (grep empty).
  - Decision: Owner: keep 'fast cold start' only if measured against NFR-001; confirm the 'no tracking' statement matches the privacy policy before publishing.
  - Linked: 17tnw2b0x3h

### Contact — `contact` (Figma `497:124`)

Verdict: **diverges** · area: secondary-1 · route: `/contact`

The build is a different composition from the frame: Figma has a centred 'Let's talk' hero above a form-left, contact-cards-right split, while the build has no hero and puts the intro plus three method cards on the left with the form on the right. Fields, cards, copy, icons and the button all differ in size and styling, and the build's contact channels, '1,200+' Discord count, 24-hour reply and fake success message are unbacked claims.

- **contact-01** · class **A** · high · page — Centred hero missing; page opens with the split and a left-aligned h1
  - Figma: Hero 497:139 (y 79-390, pad 96/96/32/96, gap 20): eyebrow pill 497:140 (91x27, fill #1e232c, r999, 'CONTACT' 12/700 ls 1.2 #5b6bd6); H1 'Let's talk' 50/56 700 centred #eef1f6; sub 19/30 400 #9aa4b2 centred, 680 wide, two lines: 'Questions about SelahCue, a hand getting set up, or partnering with us — here's how to reach a real person.' (the phrase 'a hand getting set up' reads like a typo for 'a hand with getting set up').
  - Build: No hero. ContactView.vue:41-44 opens the left column with UiBadge featured 'Get in Touch' (11/600), h1.info-title 'We're here to help your church succeed' 38/700 lh 45.6, left-aligned (.info-title ContactView.vue:162-168), p.info-sub 16px 'Have a question about SelahCue, pricing, licensing, or custom deployment? Reach out to our team.' The page h1 (doc.h1) is therefore the build's own sentence.
  - Evidence: vp_style_diff contact: pair CONTACT -> 'Contact' (copy-case, font-size 12 vs 14, weight 700 vs 400, ls 1.2 vs 0); design-only y=222 50x700 'Let's talk' and y=298 19x400 'Questions about SelahCue...'; build-only y=191.5 38px h1 and y=156 'Get in Touch'; slice contact-0.png
  - Fix: Add a centred hero section above the split: eyebrow 'CONTACT' (12/700, tracking 1.2px, pill fill --sc-elevated, padding 6/12), h1 'Let's talk' 50px/56 weight 700 centred, sub 19/30 --sc-text-secondary max-width 680 centred; hero padding 96 top / 32 bottom, gap 20. Take the badge/h1/sub out of the left column. Use the Figma copy; confirm the 'a hand getting set up' wording with Uma before shipping it.
  - Linked: 17tnw2b2cez
- **contact-02** · class **A** · high · page — Two-column split: column order, widths, gap and focus order
  - Figma: Row 497:144 (y 390-1099, pad 40/96/64/96, gap 40): LEFT the form card 497:145 at x=96 w604; RIGHT column 497:166 at x=740 w604 holding three method cards (99px tall, gap 16) and the response-time note. Content width 1248 (96px gutters, MARKETING-SITE-HANDOFF 3). Reading and tab order: form first, then cards.
  - Build: .contact-layout is a 2 x minmax(0,1fr) grid, gap 60, inside .container max-width 1140 plus --page-gutter (ContactView.vue:149-160): columns are 516 wide, intro and method cards LEFT (x=174), form card RIGHT (x=750). DOM and Tab order: three card links, then name, email, church, message, Send.
  - Evidence: box diff 'Frame 497:145 figma[96,430,604,605] build[750,149,516,718] contact-form-card width 604 vs 516'; dom focus list (links at y 472/614/755 precede the inputs); slice contact-0.png
  - Fix: Put the form card first in the DOM and in the left column; method cards plus response note in the right column. Use a 1248 content width, two 604 columns, gap 40, align-items start; keep the stacked layout below 1024 with the form first.
  - Linked: 17tnw2b2cez
- **contact-03** · class **A** · medium · page — Contact-method cards: emoji icons, radius, padding and type sizes
  - Figma: Cards 497:167/176/185: 604x99, fill #171b22, 1px #2b323d, r16, pad 20/22, gap 16 inside; icon tile 46x46 r12 filled #5b6bd6 / #2bb673 / #f2b53c with a white 1.9px stroke icon (envelope, chat bubbles, users); title 16.5/600 #eef1f6; sub 13.5/400 #9aa4b2; link 14/500 #5b6bd6 with no arrow; 16px between cards.
  - Build: .method-card (ContactView.vue:183-190): 516x121.5, r14, pad 20, gap 16, OS emoji icons at 24px (speech balloon, e-mail, office; .method-icon), h4 16/600, p 13px, .method-link 13/600 with ' →' appended, 20px between cards.
  - Evidence: slice contact-0.png; dom method-card 516x121.5 r14, method-icon fs 24px, method-link fs 13px fw 600; style-diff pair 'Support' font-size 16.5 vs 14, weight 600 vs 400
  - Fix: Replace the emoji with the feather-style inline SVG set (MARKETING-SITE-HANDOFF 7) in 46px r12 tiles (brand / preview / warn fills, white stroke); cards r16, pad 20/22, 16px gap; title 16.5/600, description 13.5, link 14/500 without the arrow.
  - Linked: 17tnw2b2cez
- **contact-04** · class **C** · high · page — Contact addresses and community channel drawn in Figma are not backed
  - Figma: 'Email us' hello@selahcue.app (497:172), 'Support' support@selahcue.app (497:181), 'Community — Tips from other churches' community.selahcue.app (497:191).
  - Build: Ships 'Support & Sales Email' with mailto:support@selahcue.app (ContactView.vue:61) and a 'Community & Discord' card 'Join 1,200+ worship tech leaders on Discord for instant help.' whose link is href='#' (ContactView.vue:48-53). hello@ and community.selahcue.app are not shown.
  - Evidence: docs/legal/LEGAL-DRAFT-NOTES.md 9.3 item 12 and 9.4: no evidence any @selahcue.app mailbox exists (API defaults to noreply@selahcue.com / info@firstpavitech.com); the 1,200+ count and the '#' links are unverified. grep of the repo finds no Discord invite or community domain.
  - Decision: Which real channels does the owner want listed (a verified mailbox, none yet, or form-only)? Keep Figma's three-card layout and styling, show only channels that exist, and no member count.
  - Linked: 17tnw2b0x3h
- **contact-05** · class **C** · high · page — Response-time promises (Figma note card and form footnote)
  - Figma: Note card 497:195 (604x105, fill #1e232c, r16, pad 20/22): label 'Response time' 12/700 ls 0.7 #9aa4b2 and 'Mon–Fri, within one business day. SelahCue keeps running offline whether or not we're at our desks.' 14.5/22. Under the Send button: 'We usually reply within one business day. No account required to reach us.' 13/400 centred muted.
  - Build: Neither block is built. The only reply promise is in the success card: 'A SelahCue specialist will respond within 24 hours.' (ContactView.vue:81).
  - Evidence: design-only list y=795 'Response time', y=816 'Mon–Fri...', y=987 'We usually reply...'; LEGAL-DRAFT-NOTES 9.4 quotes the 24-hour line as unbacked; no support rota or mailbox exists in the repo
  - Decision: No SLA or staffed-hours claim is backed. Keep the note card and footnote styling but with honest copy (only 'no account needed' and 'SelahCue works offline' are true today), or omit them until a reply process exists. Owner to confirm the wording.
  - Linked: 17tnw2b0x3h
- **contact-06** · class **C** · high · page — Form sends nothing but reports success and a 24-hour reply
  - Figma: Default state only: name / email / church / message and 'Send message'. No success or error state is drawn (MARKETING-SITE-HANDOFF 5). MARKETING-PORTAL-GAP-FILL-HANDOFF 6b specifies the success card 'Message sent!' / 'We'll get back to you within 1–2 business days.' (another SLA).
  - Build: handleSubmit validates, then setTimeout(800) sets isSubmitted; no request is made (ContactView.vue:16-33). Success card 'Message Received!' / 'Thank you for reaching out, {name}. A SelahCue specialist will respond within 24 hours.' / 'Send Another Message' (ContactView.vue:78-85).
  - Evidence: ContactView.vue:26-32 (timer, no fetch); no contact endpoint anywhere in implementation/api (grep contact_message / contact_form / submit_contact finds nothing); LEGAL-DRAFT-NOTES 9.4: 'the form sends nothing (a timer fakes success)'
  - Decision: Until a delivery path exists, should the form be removed or disabled with an honest note, or wired to an endpoint? Whatever ships, the success copy must not promise a reply time (the build's 24 h and the spec's 1–2 business days are both unbacked).
  - Linked: 17tnw2b0x3h
- **contact-07** · class **D** · medium · page — 'Enterprise & Multi-Campus' card exists only in the build
  - Figma: Three method cards only: Email us, Support, Community.
  - Build: Third card 'Enterprise & Multi-Campus — Talk to our church solutions architect for enterprise SLAs.' with 'Schedule a Demo Call →' href='#' (ContactView.vue:65-72): a dead link and an unbacked offer (enterprise SLAs, a solutions architect, demo calls).
  - Evidence: dom method-card #3 at y=674; focus list 'Schedule a Demo Call →' (x=235,y=755); build-only list y=696.9 'Enterprise & Multi-Campus', y=755.4 'Schedule a Demo Call →'; LEGAL-DRAFT-NOTES 9.4 on the '#' links
  - Decision: Remove it (Figma draws no enterprise card) or have Uma design it? The repo has no enterprise tier, SLA or demo process.
  - Linked: 17tnw2b0x3h
- **contact-08** · class **A** · medium · page — Form card and control geometry
  - Figma: Card 497:145: 604x605, fill #171b22, 1px #2b323d, r20, pad 32, gap 18, no shadow. Title 'Send us a message' 20/600. Inputs 540x44 r10 pad 13/14 value 15; textarea 540x120 pad 14 (497:161); Send button 540x49 (497:163) solid #5b6bd6, r12, label 15.5/600 white.
  - Build: .contact-form-card 516x718, r20, pad 40, box-shadow 0 20px 50px rgba(0,0,0,.4) (ContactView.vue:220-226); .form-title 22/700 (:228); inputs 434x45 pad 12/16; textarea 110 tall (FormField.vue:168); Send is the gradient UiButton lg, 434x52, r999, 16/600.
  - Evidence: box diff 'Frame 497:145 width 604 vs 516, height 605 vs 718', 'Frame 497:157 width 540 vs 434', 'Frame 497:163 fill #5b6bd6 vs transparent gradient, radius 12 vs 999'; pair 'Send us a message' font-size 20 vs 22, weight 600 vs 700
  - Fix: Card width 604, pad 32, no drop shadow, title 20/600; field rows 67px (16 label + 7 gap + 44 input), textarea min-height 120; Send button full width 49px high, solid brand, r12, label 15.5/600 (button skin itself is the shared ui-button item contact-15).
  - Linked: 17tnw2b2cez
- **contact-09** · class **A** · medium · page — Form copy: labels, placeholders and button label
  - Figma: Labels 13/500 #9aa4b2: 'Full name', 'Email', 'Church / organization', 'How can we help?'. Placeholders 15 #9aa4b2: 'Jane Pastor', 'jane@yourchurch.org', 'Grace Community Church', 'Tell us a little about what you need…'. Button 'Send message'.
  - Build: 'Your Name *', 'Email Address *', 'Church / Organization (Optional)', 'Your Message *' (ContactView.vue:90-125); placeholders 'Sarah Jenkins', 'sarah@gracechurch.org', 'Grace Community Church', 'Tell us how we can help...'; button 'Send Message'; red '*' required stars.
  - Evidence: style-diff: pair 'Church / organization' [contains] copy; pair 'Send message' copy-case; design-only y=504 'Full name', y=540 'Jane Pastor', y=589 'Email', y=625 'jane@yourchurch.org', y=759 'How can we help?', y=796 'Tell us a little...'
  - Fix: Use the Figma strings verbatim (sentence case labels, no asterisks or '(Optional)' unless Uma adds them; gap-fill 6a only lists Required yes/no), the ellipsis character in the textarea placeholder, and the button label 'Send message'.
  - Linked: 17tnw2b2cez
- **contact-10** · class **B** · low · page — Label and input skin follow the FormField spec, not the Contact frame
  - Figma: Label 13/500 #9aa4b2 (text/muted); input well fill #0e1116 (bg/base), 44 high; focus not drawn.
  - Build: FormField.vue: label 14/600 --sc-text, input fill --sc-elevated #1c1f28, 12/16 padding, focus = --sc-primary border plus 3px glow (FormField.vue:127-166).
  - Evidence: dom field-label fs 14 fw 600 color rgb(244,246,251); field-input bg rgb(28,31,40); box diff 'Frame 497:157 fill #0e1116 vs #1c1f28'
  - Source: MARKETING-PORTAL-GAP-FILL-HANDOFF 10a (FormField: label 14px Semi Bold --sc-text, input --sc-elevated background, focus ring). FLAG FOR UMA: AUTH-LANDING-PAGES-HANDOFF 2.2/2.3 say the opposite for field wells (input well -> --sc-inset, label 13/500 --sc-text-secondary) and the Contact frame follows…
  - Linked: contact-19
- **contact-11** · class **B** · low · page — Character counter under the message box
  - Figma: No counter drawn.
  - Build: FormField shows '0/2000' (12px, right-aligned) under the textarea because maxLength is 2000.
  - Evidence: dom char-count '0/2000' at (1183,739) 12px; ContactView.vue:122
  - Source: MARKETING-PORTAL-GAP-FILL-HANDOFF 6a (message max 2000, show remaining) and 6b (character-count row). Wording differs from 6b ('N/2000 characters remaining'): the build shows 'count/limit'.
- **contact-12** · class **A** · medium · page · a11y — Form states and ARIA below the gap-fill spec
  - Figma: Only the default state is drawn; no frame for validation, submitting, success or error (MARKETING-SITE-HANDOFF 5). The states are specified in MARKETING-PORTAL-GAP-FILL-HANDOFF 6b/6c.
  - Build: Spec items not built: the form has no aria-label='Contact us'; no aria-required on required fields (FormField sets only aria-invalid/aria-describedby for errors); the success card has no aria-live='polite' region; the textarea has no aria-label and its counter is not in aria-describedby; validation runs on submit only (spec: blur or submit); the submitting state shows a spinner but not the 'Sending…' label and hides the label (UiButton .content.hidden); no server-error or network-error banner o…
  - Evidence: grep for aria-required|aria-live|aria-label in ContactView.vue and FormField.vue returns only the password toggle label; ContactView.vue:16-33 and 77-87
  - Fix: Add aria-label='Contact us' on the form, aria-required='true' on name/email/message, an aria-live='polite' success region ('Your message has been sent'), aria-describedby from the textarea to the counter, blur validation, 'Sending…' button text, the 6b error banners once a send path exists, and maxlength 100 on name and church.
  - Linked: 17tnw2b2cez
- **contact-13** · class **A** · medium · page · a11y — Placeholder and counter text fail AA (muted ink in the wrong role)
  - Figma: Placeholders #9aa4b2 on the #0e1116 well = 7.5:1 (text/muted, mapped to --sc-text-secondary by AUTH-LANDING-PAGES-HANDOFF 2.2).
  - Build: ::placeholder uses --sc-text-muted #6b7383 on --sc-elevated #1c1f28 = 3.45:1 at 15px (FormField.vue:158-160); the '0/2000' counter 12px #6b7383 on #14161d = 3.79:1.
  - Evidence: report.json contrast_survey capture=contact: 'Sarah Jenkins', 'sarah@gracechurch.org', 'Grace Community Church', 'Tell us how we can help...' 3.45; '0/2000' 3.79 (required 4.5); dom placeholder color rgb(107,115,131); style-diff pair 'Grace Community Church' colour #9aa4b2 vs #6b7383 (not colour~)
  - Fix: Use --sc-text-secondary (#a7aebe, 7.4:1 on --sc-elevated) for placeholders and the counter; the 2.2 mapping text/muted -> --sc-text-secondary applies.
  - Linked: 17tnw2b2cez
- **contact-14** · class D · duplicate of **account-25** — Small brand-coloured text is below AA in Figma and in the build
- **contact-15** · class A · duplicate of **shared-chrome-29** — Primary button skin: solid #5b6bd6 r10/r12 versus gradient pill
- **contact-16** · class A · duplicate of **shared-chrome-01** — Navbar geometry and colours (identical on all five surfaces)
- **contact-17** · class A · duplicate of **shared-chrome-16** — Footer structure, columns and styling (identical on all five surfaces)
- **contact-18** · class C · duplicate of **shared-chrome-19** — Footer bottom-bar claims 'Cancel anytime', which the repo does not back
- **contact-19** · class **D** · medium · page — FormField styling: two handoffs disagree and one decision has to settle it for Contact and the auth pages
  - Figma: Contact (497:124) and every auth frame draw the field label as Inter Medium 13 in the secondary text colour and the input well on the inset fill, 44 high (AUTH-LANDING-PAGES-HANDOFF 2.2 and 2.3).
  - Build: FormField.vue follows MARKETING-PORTAL-GAP-FILL-HANDOFF 10a: label 14/600 in the primary text colour, input on --sc-elevated, 3px focus glow. It is used by Contact, Sign up, Forgot password, Sign in, Reset and the affiliate and admin settings pages.
  - Evidence: contact-10 (class B, follows 10a), signin-06 and signin-07 (class A, follow AUTH 2.3); the cited sections quote opposite values; reported by the code review of PR 171 (finding 6)
  - Decision: Uma: which spec governs FormField for Contact and the auth pages together? If AUTH-LANDING 2.3: the auth variant (signin-06, signin-07) is built and contact-10 flips from class B to class A. If GAP-FILL 10a: signin-06 and signin-07 become class B citing it, and the frames are the ones to redraw. Settle it before the shared-components ticket (FormField) and the auth ticket finish.
  - Linked: contact-10; signin-06; signin-07

### Support (Help Center) — `support` (Figma `498:124`)

Verdict: **diverges** · area: secondary-1 · route: `/support`

The sections and their order match (hero with search, six category cards, article list, still-stuck line) but the build is 805px taller and looks different: hero copy and sizes differ, the category cards carry emoji, article lists and counts instead of coloured icon tiles, and Figma's 'Popular articles' panel is a 'Start here' list of separate cards followed by a CTA box. The extra height is the GAP-08 content layer from ClickUp 17tnw2b0q9h, which neither the frame nor any handoff section draws.

- **support-01** · class **A** · high · page — Hero: eyebrow, h1 copy and size, missing subtitle, radial glow
  - Figma: Hero 498:139 (y 79-450, pad 96/96/48/96, gap 22): pill 498:140 'HELP CENTER' 12/700 ls 1.2 #5b6bd6 on #1e232c r999; H1 'How can we help?' 48/54 700 centred; sub 'Guides, answers and troubleshooting for running SelahCue on Sunday.' 18/28 #9aa4b2, 620 wide; flat #0e1116 background.
  - Build: SupportView.vue:37-56: UiBadge featured 'Support & Help Center' 11/600; h1.hero-title 'How can we help you today?' 40/60 weight 800 (:141-146); no subtitle; .support-hero radial-gradient glow rgba(110,92,240,.12) (:135-139); padding 80/60.
  - Evidence: style-diff support design-only y=181 'HELP CENTER', y=224 'How can we help?', y=300 'Guides, answers and troubleshooting...'; build-only y=156 'Support & Help Center', y=197.5 40px 'How can we help you today?'; slice support-0.png
  - Fix: Eyebrow 'HELP CENTER' (12/700, tracking 1.2px, pill --sc-elevated); h1 'How can we help?' 48px/54 weight 700; add the 18/28 subtitle (max-width 620); remove the radial glow; hero padding 96 top / 48 bottom, gap 22.
  - Linked: 17tnw2b2cez
- **support-02** · class **A** · medium · page — Search field shape, size, icon and placeholder
  - Figma: Search 498:144: 620x52 at (410,350), fill #171b22, 1px #2b323d, r14, pad 16/18, gap 12; magnifier vector 13.3px #9aa4b2 (1.67 stroke); placeholder 'Search help articles…' 15.5/400 #9aa4b2; no shadow.
  - Build: .search-input 640x54, r999 pill, padding 16/24/16/54, 16px, box-shadow 0 10px 30px rgba(0,0,0,.3), 20px icon at left 20 (SupportView.vue:42-54, 148-180); placeholder 'Search help articles (e.g. stage display, pairing, crash recovery)...'.
  - Evidence: dom search-input 640x54 radius 999px pad 16px 24px 16px 54px; box diff of the hero; slice support-0.png
  - Fix: 620x52, r14, 1px --sc-border, no shadow, 13px magnifier, placeholder 'Search help articles…' at 15.5px; keep type='search', role='search' and the aria-label.
  - Linked: 17tnw2b2cez
- **support-03** · class **A** · medium · page · a11y — Search placeholder uses the browser default grey and fails AA; focus is a 1px border change only
  - Figma: Placeholder #9aa4b2 on #171b22 = 6.85:1; MARKETING-SITE-HANDOFF 5 and gap-fill 10a call for a 2px --sc-primary focus ring.
  - Build: No ::placeholder rule, so the default rgb(117,117,117) on #14161d = 3.92:1. :focus sets outline none and only changes border-color (SupportView.vue:177-180).
  - Evidence: report.json contrast_survey support 'Search help articles (e.g. stage display, pairing, ...' 3.92 (required 4.5); dom placeholder color rgb(117,117,117)
  - Fix: ::placeholder { color: var(--sc-text-secondary) }; replace outline:none with a 2px --sc-primary :focus-visible ring (offset 2px).
  - Linked: 17tnw2b2cez
- **support-04** · class **A** · high · page — Category cards: size, icon tiles, titles, descriptions and an extra section heading
  - Figma: Grid 498:150/171: 3 x 2 cards 400x170, gap 24 (x=96/520/944, y=458/652), fill #171b22, 1px #2b323d, r18, pad 26/24, gap 13; icon tile 48x48 r13 filled #5b6bd6 / #2bb673 / #f2b53c / #5b6bd6 / #2bb673 / #ef4444 with white 2px vector icons; title 18/600 #eef1f6; description 14.5/22 #9aa4b2; no heading above the grid. Titles: Getting started, Outputs & displays, Scripture & plans, NDI & streaming, Mobile control, Troubleshooting.
  - Build: .category-card 348 wide (container 1092), r16, pad 28, gap 24; OS emoji icons 32px; h3 18/600; description 14px/1.5 --sc-text-secondary; an h2 'Knowledge Base Categories' 26/700 with 32px margin above the grid (SupportView.vue:78, 182-233). Titles Getting Started, Display & Outputs, Scripture & Bibles, Timers & Clocks, Mobile Control, Troubleshooting (support.ts:27-34); the 'Getting Started' description 'The audience screen is blank, or something is not appearing' describes an article, not the …
  - Evidence: box diff 'Frame 498:151 figma[96,458,400,170] build[174,520,348,341] radius 18 vs 16, width 400 vs 348, height 170 vs 341'; pairs 'Scripture & plans' -> 'Scripture & Bibles' (copy), 'Getting started'/'Mobile control' (copy-case); build-only cat-icon and section-title 'Knowledge Base Categories'
  - Fix: Remove the section heading; 400x170 cards on a 1248 container, gap 24, r18, pad 26/24; replace emoji with 48px r13 coloured tiles and feather-style SVGs (zap, monitor, book/tablet, radio, smartphone, alert-circle); sentence-case titles and Figma descriptions where the topic exists; correct the Getting Started description. Article lists and counts: see support-05.
  - Linked: 17tnw2b2cez
- **support-05** · class **D** · high · page — Undrawn content layer (GAP-08) accounts for the +805px
  - Figma: Category cards are link tiles with no article list or count (170px); the list is one panel of five chevron rows; no search-results state, no empty-search state, no per-category anchors.
  - Build: Added by ClickUp 17tnw2b0q9h (commits 4f3a8592, cc6dc1cd): every card lists its real articles (.cat-articles, 44px-min rows) and an 'N article(s)' count (SupportView.vue:84-89); a 'Start here' list of curated articles with 'Category · N min read'; client-side search (searchSupport) that replaces the page body with 'Search results' and a live status line; detail routes /support/:category/:slug (no Figma frame). Height: cards 341/377 vs 170 (+378 over two rows) + heading and margins (+71) = about…
  - Evidence: doc.h 2475 vs frame 1670; dom category-card heights 341 and 377.2; build-only list (cat-article-link, cat-count, article-meta, 'Start here', 'Still need help?')
  - Decision: Neither MARKETING-SITE-HANDOFF nor the frame draws this (MARKETING-PORTAL-GAP-FILL-HANDOFF 9c specs only the article detail route). Uma: design the index layer (article lists inside cards or on category pages, counts, search results and empty state), or keep the drawn tiles and list and move article lists to category pages? Detail pages have no frame either (layout in 9c only) and were not audite…
  - Linked: 17tnw2b0q9h
- **support-06** · class **C** · medium · page — 'Popular articles' heading is a popularity claim
  - Figma: Heading 'Popular articles' 26/700 centred above five rows: 'Pairing your phone over the local network', 'Setting up a stage display', 'Sending your program to OBS with NDI', 'Building your first service plan', 'Why the screen never blanks — and what to do if it does'.
  - Build: Heading 'Start here' with two rows (SupportView.vue:96-109). types.ts:68-73 records that startHere is a curation flag, not a popularity claim, because no analytics exist to say what is popular.
  - Evidence: types.ts:68-73; support.ts startHere flags (2 articles); design-only y=910 26x700 'Popular articles'
  - Decision: Keep Figma's centred heading and panel layout but label it honestly (for example 'Start here'). How many rows: Figma five, the content layer flags two? Row titles in Figma are placeholders; the build lists real articles (see support-09).
  - Linked: 17tnw2b0q9h
- **support-07** · class **A** · medium · page — Article list: full-width band and single grouped panel versus separate cards
  - Figma: Band 498:193: 1440x442 fill #171b22 (y 870-1312, pad 40/96/48/96, gap 20); heading centred; list 498:195 880x265 at x=280, fill #0e1116, 1px #2b323d, r16, five 53px rows separated by 1px #2b323d hairlines, title 15.5/500 #eef1f6 at pad 17/22, chevron-right (4.5x9 vector #9aa4b2) at the right; the whole row is the affordance.
  - Build: .articles-list = separate cards (gap 16, r12, pad 20/24, 94 tall): title 16/600 + 'Category · N min read' 13px meta + ghost button 'Read article →' (SupportView.vue:235-261); heading left-aligned; the section background is the page colour (no #171b22 band); only the button is the link.
  - Evidence: slice support-0.png; dom article-row 1092x94 r12 pad 20/24; design-only y=978..1190 15.5x500 rows
  - Fix: Full-width --sc-surface band, centred 26/700 heading, one bordered panel (880 wide, --sc-inset fill, r16) with hairline-separated 53px rows, chevron icon and the whole row as one router-link; keep the real article titles.
  - Linked: 17tnw2b2cez
- **support-08** · class **C** · medium · page — 'Still stuck' line promises a one-business-day reply; build shows a CTA card instead
  - Figma: Centred 15/400 #9aa4b2 line inside the band: 'Still stuck? Contact support — we reply within one business day.' (no card or button; no distinct link colour is drawn).
  - Build: .help-cta card (r20, pad 40): h3 'Still need help?' 24px, 'Our support team is available to assist your church with technical questions.', gradient 'Contact Support Team' button to /contact (SupportView.vue:112-119, 263-279).
  - Evidence: design-only y=1246 15x400 'Still stuck?...'; build-only y=1770.7 'Still need help?' and y=1873.2 'Contact Support Team'
  - Decision: 'We reply within one business day' is an unbacked SLA (and 'support team' implies staffing). Keep Figma's single centred line under the list with 'Contact support' linking to /contact and have the owner approve honest copy with no reply time; the CTA card is not drawn.
  - Linked: 17tnw2b0x3h
- **support-09** · class **B** · low · page — Article titles, summaries, counts and read times come from the local content layer
  - Figma: Five placeholder row titles; six categories with fixed one-line descriptions.
  - Build: Titles, summaries and read times derive from lib/content/support.ts (11 real articles, e.g. 'Nothing is showing on the audience screen', 'My phone will not pair'); counts and 'N min read' are computed (readMinutes), not typed.
  - Evidence: support.ts article list; dom cat-count and article-meta values; no Licensing & Billing category by design (support.ts header)
  - Source: ClickUp 17tnw2b0q9h / GAP-08 and implementation/marketing/src/lib/content/types.ts (honesty rules: no invented claims; support.ts documents a deliberately absent 'Licensing & Billing' category because billing is not built); MARKETING-PORTAL-GAP-FILL-HANDOFF 1 (GAP-08) and 12 (content-source follow-…
  - Linked: 17tnw2b0q9h
- **support-10** · class **A** · medium · page · a11y — Muted ink below AA on counts and article meta
  - Figma: Secondary text #9aa4b2 on #171b22 = 6.85:1.
  - Build: 'N articles' 12/600 --sc-primary on #14161d = 3.83:1; 'Category · 2 min read' 13px --sc-text-muted #6b7383 on #14161d = 3.79:1 (.article-meta SupportView.vue:258-261).
  - Evidence: report.json contrast_survey support: 'Getting Started · 2 min read' 3.79, 'Mobile Control · 2 min read' 3.79, '1 article' / '2 articles' / '3 articles' 3.83 (required 4.5)
  - Fix: Meta text to --sc-text-secondary (AUTH-LANDING-PAGES-HANDOFF 2.2 mapping); counts use the AA ink chosen under contact-14.
  - Linked: 17tnw2b2cez
- **support-11** · class **C** · medium · page — Support article says 'There is no macOS or Linux installer yet', which contradicts what product says
  - Figma: Figma draws no such sentence; the NDI troubleshooting article is part of the undrawn content layer (support-08).
  - Build: support.ts:108 (NDI article): 'Use a build that includes NDI. The Windows installer is built with it and carries the NDI runtime. There is no macOS or Linux installer yet.'
  - Evidence: Product (owner, 2026-10-04): SelahCue is available for Windows, Linux and macOS. For: docs/product/prds/SelahCue-PRD.md:33 (G-2) targets Windows, macOS and Linux; .github/workflows/ci.yml builds and tests on ubuntu, macOS and Windows; docs.ts:145 documents a Linux data folder. Against: tauri bundle…
  - Decision: Owner: It is NOT yet known whether 'available' means a downloadable installer exists today on each platform, or that the app supports all three while only the Windows installer is packaged. Reconcile the sentence with the answer. Until then no page may claim a downloadable macOS or Linux installer (Download buttons stay disabled, PR #134).

### Documentation — `docs` (Figma `499:124`)

Verdict: **diverges** · area: secondary-1 · route: `/docs`

Figma is a hub: centred hero, a grouped sidebar with an active item, a 'Getting started' intro, a 'run your first service' callout and a 2x3 topic grid. The build drops the hero, intro, callout and grid and renders a long article index (six category sections, eleven article rows) inside one 844px card, which makes it 1787px taller; that index is the undrawn ClickUp 17tnw2b0q9h content layer, and the sidebar has no active state.

- **docs-01** · class **A** · high · page — Centred hero missing; h1 sits inside the content card
  - Figma: Hero 499:139 (y 79-374, pad 88/96/36/96, gap 18): pill 499:140 'DOCS' (63x27, #1e232c, 12/700 ls 1.2 #5b6bd6); H1 'Documentation' 46/52 700 centred; lead 'Everything you need to install, set up and run SelahCue with confidence.' 18/28 #9aa4b2, 600 wide, centred.
  - Build: No hero. h1.doc-title 'Documentation' 36/54 weight 800, left-aligned inside .docs-content, under a 'Docs' breadcrumb (13px) and over the lead 'How-to guides for running SelahCue, written from what the app actually does.' 18px with a bottom rule (DocsView.vue:34-37, 139-158).
  - Evidence: style-diff docs pair 'DOCS' -> 'Docs' (copy-case, 12 vs 13, weight 700 vs 400, ls 1.2 vs 0); pair 'Documentation' font-size 46 vs 36, text-align center vs left; design-only y=282 18x400 lead; slice docs-0.png
  - Fix: Add the centred hero above the split: pill 'DOCS' (12/700, tracking 1.2px, --sc-elevated), h1 'Documentation' 46px/52 weight 700, lead 18/28 --sc-text-secondary max-width 600; padding 88 top / 36 bottom, gap 18. Remove the breadcrumb, h1 and lead from the card.
  - Linked: 17tnw2b2cez
- **docs-02** · class **A** · high · page — Sidebar: grouping, sizes and the missing active state
  - Figma: Sidebar 499:145 at (96,398) 248x529, #171b22, 1px #2b323d, r16, pad 22/18, gap 18: groups GETTING STARTED (Introduction [active: fill #1e232c r8, 14.5/600 #5b6bd6], Installation, Your first service), GUIDES (Outputs & displays, Scripture & plans, NDI & streaming, Mobile control, Themes & templates), REFERENCE (Keyboard shortcuts, Troubleshooting); group labels 11/700 ls 0.9 #9aa4b2; items 14.5/400 #eef1f6 in 32px rows with 9px gaps.
  - Build: aside.docs-sidebar 260 wide at x=144, pad 20, r16, sticky top 100; title 'DOCUMENTATION' 14/700 uppercase --sc-text-muted; six hash links (Getting Started, Display & Outputs, Scripture & Bibles, Timers & Service Plans, Mobile Control, Troubleshooting) 14px --sc-text-secondary in 41px rows; no groups; no active styling: .nav-item.active (DocsView.vue:125-129) is never applied, and all six links carry router-link-active and router-link-exact-active with no CSS for them.
  - Evidence: dom: six 'a router-link-active router-link-exact-active nav-item'; box diff 'Frame 499:145 figma[96,398,248,529]'; slice docs-0.png
  - Fix: Rebuild the sidebar to the frame: 248 wide, pad 22/18, grouped labels (11/700, ls 0.9), 32px rows at 14.5px, and a single active item (fill --sc-elevated, r8, --sc-primary, 600) driven by scroll position or the current hash; group the real categories under GETTING STARTED / GUIDES / REFERENCE; keep aria-current='false' behaviour so only one item is ever announced as current. Entries with no article: see docs-06.
  - Linked: 17tnw2b2cez
- **docs-03** · class **A** · high · page — 'Getting started' intro, callout and 2x3 topic grid missing
  - Figma: Content column x=384 w960: H2 'Getting started' 28/700; intro 16.5/26 #9aa4b2 ('SelahCue is a desktop-authoritative, offline-first church presentation app. This hub covers installation, running your first service, and every output and control in depth — no internet required to follow along.'); callout 499:175 (960x84, #1e232c, 1px #2b323d, r16, pad 20/22, gap 18) with a 44px brand tile r11, title 16.5/600, sub 14, 'Start guide' button 112x41 #5b6bd6 r10; grid of six 471x83 tiles (2 columns, gap…
  - Build: None of these exist: DocsView.vue renders breadcrumb, h1, lead and category sections inside one card (.docs-content 844 wide, r20, pad 48, #14161d).
  - Evidence: design-only list: 'Getting started' 28x700, y=454 intro, y=550 'New here?...', y=561.5 'Start guide', six tile titles/descriptions; box diff 'Frame 499:209 figma[873,735,471,83] build docs-content 844x2541'
  - Fix: Add the H2 and intro (Figma copy, minus claims flagged in docs-04), the callout with a real destination, and the 2x3 tile grid (471x83 tiles, r16, pad 20) with the coloured 40px icon tiles; each tile links to its category section or first article.
  - Linked: 17tnw2b2cez
- **docs-04** · class **C** · medium · page — '10 minutes' and installation / update / audio-setup claims
  - Figma: Callout 'New here? Run your first service in 10 minutes' / 'Install, build a plan, and go live — start to finish.'; tile 'Installation — Windows & macOS install and updates.'; tile 'Setup guides — Displays, audio, and per-output config.'; intro 'This hub covers installation...'.
  - Build: None of it is built. The content layer has no installation article and omits unverified workflows (docs.ts header: a workflow that could not be verified in the code is not written).
  - Evidence: LEGAL-DRAFT-NOTES 9.4: app version is 0.1.0 and there is no macOS release pipeline; docs.ts article list has no install, update or audio-config article; no measurement of a first service duration exists
  - Decision: '10 minutes' is an unmeasured claim; 'Windows & macOS install and updates': product says macOS is available (2026-10-04) but no macOS installer or update mechanism is evidenced in the repo (open question: docs-09); 'audio' configuration is unverified. Keep the callout and tile layout with honest copy or omit those tiles; owner decision.
  - Linked: 17tnw2b0x3h
- **docs-05** · class **D** · high · page — Undrawn article-index layer accounts for the +1787px
  - Figma: No article rows: a six-tile grid (two rows of 83px) is the whole hub body (content column 521px tall).
  - Build: Six category sections (h2 22/700, 15px description, article cards) inside .docs-content (2541px tall): eleven article links as rows (.topic-link: --sc-elevated, r12, pad 16/18, title 16/600, 14px summary, '2 min read'), ids per category used by the sidebar and breadcrumbs (DocsView.vue:39-51, 287-311); articles at /docs/:category/:slug. Page 3136 vs 1349: body +1749, footer +47.5, nav -10.
  - Evidence: doc.h 3136 vs frame 1349; dom docs-content 844x2541.3; build-only list (topic-title, topic-desc, topic-link-title/-sum/-meta); commit 4f3a8592 'generate blog, docs and support indexes from the content source and link every entry (17tnw2b0q9h)'
  - Decision: Not drawn, and MARKETING-PORTAL-GAP-FILL-HANDOFF 9b describes only the article detail layout. Uma: design the docs index, or keep Figma's hub and move the per-category article lists to category pages? Article detail pages have no frame either (9b layout only) and were not audited.
  - Linked: 17tnw2b0q9h
- **docs-06** · class **D** · medium · page — Sidebar entries and tiles with no backing article
  - Figma: Introduction, Installation, Your first service, Setup guides, Themes & templates and Keyboard shortcuts appear as sidebar items or tiles; Outputs & displays, Scripture & plans, NDI & streaming, Mobile control and Troubleshooting exist in some form.
  - Build: The content layer has 11 articles in six categories (getting-started, display-outputs, scripture-bibles, timers-plans, mobile-control, troubleshooting); there is no article for Installation, Your first service, Setup guides, Themes & templates or Keyboard shortcuts, and 'Timers & Service Plans' exists in the build but not in Figma.
  - Evidence: docs.ts categories and article list (docs.ts:25-32 and slugs); sidebar text list in docs.blink.dom.json
  - Decision: Do we write the missing articles (Keyboard shortcuts and Themes exist in the app), map tiles to existing articles, or drop them? MARKETING-SITE-HANDOFF 1 says the footer 'Setup guides' link points to the Documentation page.
  - Linked: 17tnw2b0q9h
- **docs-07** · class **A** · medium · page · a11y — Sidebar title and breadcrumb use the muted ink below AA
  - Figma: Group labels 11/700 #9aa4b2 on #171b22 = 6.85:1 (text/muted maps to --sc-text-secondary, AUTH-LANDING-PAGES-HANDOFF 2.2).
  - Build: 'DOCUMENTATION' sidebar title 14/700 and the 'Docs' breadcrumb 13px use --sc-text-muted #6b7383 on #14161d = 3.79:1 (DocsView.vue:91-99, 139-143).
  - Evidence: report.json contrast_survey docs: 'Documentation' 14px/700 3.79, 'Docs' 13px 3.79 (required 4.5); style-diff pair 'Documentation' colour #eef1f6 vs #6b7383 (not colour~)
  - Fix: Use --sc-text-secondary for the sidebar group labels (and the breadcrumb if it survives).
  - Linked: 17tnw2b2cez
- **docs-08** · class **A** · low · page — Page width and spacing: 1104 container versus 1248
  - Figma: Split row 499:144 pad 24/96/64/96, gap 40: sidebar x=96 w248, content x=384 w960 (to x=1344); 96px gutters.
  - Build: .container max-width 1200 plus --page-gutter: sidebar x=144 w260, gap 48, content card x=452..1296 (w844); .docs-page padding 60 (DocsView.vue:59-79).
  - Evidence: dom aside.docs-sidebar xywh 144,129,260,345; docs-content 452,129,844; figma boxes 499:145 and 499:172
  - Fix: 1248 content width (96px gutters), sidebar 248, gap 40, content 960, split padding 24 top / 64 bottom.
  - Linked: 17tnw2b2cez
- **docs-09** · class **C** · medium · page — Docs known-limits note says 'There is no macOS or Linux installer yet', which contradicts what product says
  - Figma: Figma draws no such note; it sits in the undrawn article layer (docs-06).
  - Build: docs.ts:317 (callout 'Known limits'): 'There is no macOS or Linux installer yet, so the Windows installer is the only packaged build that includes NDI.'
  - Evidence: Product (owner, 2026-10-04): SelahCue is available for Windows, Linux and macOS. Same evidence for and against as support-11 (PRD G-2 line 33; CI matrix; docs.ts:145 Linux data folder; tauri target nsis only).
  - Decision: Owner: It is NOT yet known whether 'available' means a downloadable installer exists today on each platform, or that the app supports all three while only the Windows installer is packaged. Reconcile the sentence with the answer (same question as support-11). Until then no page may claim a downloadable macOS or Linux installer.

### Changelog — `changelog` (Figma `501:124`)

Verdict: **diverges** · area: secondary-1 · route: `/changelog`

The idea matches (stacked release cards grouped New / Improved / Fixed) but the structure differs: Figma is one 900px card per release with grouped bullet lists, the build is a timeline with a left meta column and a titled row per change. Every version, date and entry in the build is invented (the app is 0.1.0 with no releases), as are Figma's illustrative ones, and the 'Fixed' badge uses a variant that does not exist so it renders unstyled.

- **changelog-01** · class **A** · high · page — Hero: eyebrow, h1 copy and size, subtitle size
  - Figma: Hero 501:139 (y 79-388, pad 96/96/40/96, gap 18): pill 'CHANGELOG' 12/700 ls 1.2 #5b6bd6 on #1e232c; H1 'What's new' 48/54 700 centred; sub 18/28 #9aa4b2, 620 wide.
  - Build: UiBadge featured 'Product Updates' 11/600; h1.hero-title 'Changelog & Release Notes' 40/60 weight 800; .hero-sub 16px 'Stay up to date with new features, performance improvements, and bug fixes in SelahCue.'; padding 80/50 (ChangelogView.vue:39-45, 90-105).
  - Evidence: design-only y=220 48x700 'What's new', y=292 18x400 sub; build-only y=156 'Product Updates', y=197.5 40px 'Changelog & Release Notes', y=270.5 16px sub; slice changelog-0.png
  - Fix: Eyebrow 'CHANGELOG' (12/700, tracking 1.2, pill --sc-elevated); h1 'What's new' 48px/54 weight 700; sub 18/28 max-width 620 (copy per changelog-05); hero padding 96 top / 40 bottom, gap 18.
  - Linked: 17tnw2b2cez
- **changelog-02** · class **A** · high · page — Release layout: one grouped card per release versus meta column plus per-change rows
  - Figma: Cards 501:145/193/231: 900 wide centred (x=270), fill #171b22, 1px #2b323d, r20, pad 28/30, gap 18, 24 between cards. Header row: version 22/700 + date 14/400 #9aa4b2 + 'LATEST' pill (64x21, #1e232c, r999, 10.5/700 ls 0.6 green) on the newest only; 1px hairline; then one block per type: label pill (New #2bb673, Improved #5b6bd6, Fixed #f2b53c; 10.5/700 on #1e232c r999 pad 4/10) beside a bullet list (6px dot in the type colour + 15/23 #eef1f6, 9px between lines).
  - Build: .timeline-item = grid 200px | 1fr, gap 36: sticky left meta column (version 24/800, date 13px muted, tag badge 'Latest Release' / 'Feature Update' / 'Major Release') and a right .timeline-content card 616 wide, r16, pad 28, #14161d with one .change-entry per change: the type badge repeated on every row, h3 16/600 title, 14px description, hairline between rows (ChangelogView.vue:50-70, 107-176); container max 900 gives 852 wide.
  - Evidence: slice changelog-0.png; box diff 'Frame 501:145 figma[270,412,900,353] build changelog-page'; build-only list entry-title / entry-desc / version-code / release-date / ui-badge tags
  - Fix: One card per release (900 wide, r20, pad 28/30): header row version 22/700 + date 14 + LATEST pill on the newest only, hairline, then changes grouped by type with one label pill per group and dotted 15/23 bullet lines; drop the left meta column, the per-change titles/descriptions and the tag badges.
  - Linked: 17tnw2b2cez
- **changelog-03** · class **A** · medium · shared · ui-badge — Change-type badges: 'warn' is not a UiBadge variant, 'ndi' is the wrong hue
  - Figma: New = green label #2bb673, Improved = brand #5b6bd6, Fixed = warn #f2b53c, each on a #1e232c pill.
  - Build: ChangelogView.vue:60 maps fixed to variant 'warn', which UiBadge does not define (UiBadge.vue:6 validator allows live / preview / ready / ndi / featured / new): 'FIXED' renders with no background or border and --sc-text ink, and Vue logs a prop-validation warning in dev. 'improved' uses 'ndi' (cyan #38bdf8 on info-soft) instead of brand.
  - Evidence: dom: span ui-badge variant-warn size-sm 'FIXED' bg None color rgb(244,246,251); span variant-ndi 'IMPROVED' color rgb(56,189,248) bg rgb(16,34,43); slice changelog-0.png (FIXED shows as plain text)
  - Fix: Fixed -> variant 'ready' (warn-soft background, --sc-warn ink); Improved -> 'featured' (accent) or a dedicated tone matching #5b6bd6; New -> 'preview'; add a test that every UiBadge variant used in a view is defined.
  - Linked: 17tnw2b2cew
- **changelog-04** · class **C** · high · page — Versions, dates and entries are unbacked in both Figma and the build
  - Figma: v1.0.0 'August 2026' [LATEST], v0.9.0 'June 2026', v0.8.0 'April 2026' with illustrative entries including 'Faster cold start (≤3 s on a release build)', 'Optional on-device live transcript', 'NDI streaming output to OBS / vMix'. MARKETING-SITE-HANDOFF 1a and 8 call the versions and dates illustrative placeholders.
  - Build: ChangelogView.vue:4-34: v1.2.0 'August 8, 2026' (Latest Release), v1.1.0 'June 15, 2026', v1.0.0 'March 1, 2026' with invented entries: 'Native NDI 5 Output Engine ... without extra plugins', 'Licensed Bible Entitlement Sync ... NIV, ESV, and NLT', 'Reduced GPU VRAM usage by 35% on 4K motion backgrounds', 'Flutter Mobile Companion App', 'Display Reconnect Recovery'.
  - Evidence: implementation/desktop/Cargo.toml and selahcue-operator tauri.conf.json both say version 0.1.0; no git release tags, no CHANGELOG file; LEGAL-DRAFT-NOTES 9.4 (version claim); NIV/ESV/NLT are not shipped (the blog post 'Which Bible translations ship with SelahCue' says licensed translations are not …
  - Decision: Keep the card and list layout; replace the content with what is true (for example one honest card for the current 0.1.0 state, or 'No public releases yet'). Owner/Priya to decide what the changelog says before a release exists.
  - Linked: 17tnw2b0x3h
- **changelog-05** · class **C** · medium · page — Subtitle promises free updates and always-latest; 'LATEST' pill on an unreleased version
  - Figma: 'Every SelahCue release, big and small. Updates are free on your plan — you're always on the latest version.' and a 'LATEST' pill on v1.0.0.
  - Build: Subtitle copy is different (see changelog-01) and does not repeat the claim; a 'Latest Release' badge sits on v1.2.0, a version that does not exist.
  - Evidence: design-only y=292 18x400 sub, y=447 10.5x700 'LATEST'; build-only y=416 'Latest Release' badge; plan and pricing are undecided (D1); no auto-update mechanism is evidenced in the repo
  - Decision: 'Updates are free on your plan' (plans undecided) and 'you're always on the latest version' (no auto-update evidenced) are unbacked; keep the drawn layout with honest copy and show a LATEST pill only once a release exists.
  - Linked: 17tnw2b0x3h
- **changelog-06** · class **A** · low · page · a11y — Release date uses the muted ink below AA
  - Figma: Date 14/400 #9aa4b2 on #171b22 = 6.85:1.
  - Build: .release-date 13px --sc-text-muted #6b7383 on --sc-base #0b0d12 = 4.08:1 (ChangelogView.vue:136-139).
  - Evidence: report.json contrast_survey changelog: 'August 8, 2026', 'June 15, 2026', 'March 1, 2026' 13px 4.08 (required 4.5)
  - Fix: Use --sc-text-secondary (AUTH-LANDING-PAGES-HANDOFF 2.2 mapping) at 14px.
  - Linked: 17tnw2b2cez

### Blog — `blog` (Figma `502:124`)

Verdict: **diverges** · area: secondary-1 · route: `/blog`

Same sections (hero, featured post, article grid) but the build is 152px shorter and visibly different: no 584px illustration panel and no card thumbnails, a 2-column text-only grid instead of 3 columns with media tiles, a red 'Featured Article' badge, a brand-bordered gradient featured card and a different hero. The cards do link to real /blog/:slug pages; only four grid posts exist against Figma's six.

- **blog-01** · class **A** · high · page — Hero: eyebrow, h1 copy and size, subtitle copy and size
  - Figma: Hero 502:139 (y 79-388, pad 96/96/40/96, gap 18): pill 'BLOG' 12/700 ls 1.2 #5b6bd6 on #1e232c; H1 'The SelahCue blog' 48/54 700 centred; sub 'Practical notes on running a confident service — reliability, outputs, and the craft of church tech.' 18/28 #9aa4b2, 640 wide.
  - Build: UiBadge featured 'SelahCue Journal' 11/600; h1.hero-title 'Insights for Modern Worship & Tech Ministry' 40/60 weight 800; .hero-sub 16px 'Articles, technical guides, and best practices for church presentation teams.'; padding 80/40 (BlogView.vue:14-20, 57-61).
  - Evidence: design-only y=220 48x700 'The SelahCue blog', y=292 18x400 sub; build-only y=156 'SelahCue Journal', y=197.5 40px h1, y=270.5 16px sub; slice blog-0.png
  - Fix: Eyebrow 'BLOG' (12/700, tracking 1.2, pill --sc-elevated); h1 'The SelahCue blog' 48px/54 weight 700; sub 18/28 with the Figma sentence; padding 96 top / 40 bottom, gap 18.
  - Linked: 17tnw2b2cez
- **blog-02** · class **A** · high · page — Featured post: no media panel, gradient and brand border, red 'Featured Article' badge, extra button
  - Figma: Card 502:145: 1248x348, fill #171b22, 1px #2b323d, r22, pad 24, gap 32: left media panel 584x300 (#1e232c, r14) with a 102px brand tile and shield-check icon; right column: category pill 'RELIABILITY' (brand text on #1e232c) + 'Featured' 12/500 muted label, title 28/700 lh 34, summary 16/25 muted, meta 'SelahCue Team · Jul 2026 · 6 min read' 13.5; no button.
  - Build: .featured-card text-only 1092x300: background linear-gradient(135deg, --sc-surface, #1b1938) (hard-coded hex), 1px --sc-primary border, r20, pad 40; badge 'Featured Article' uses UiBadge variant 'live' (the red LIVE status style); title 28/700 lh 42; meta 13px + gradient pill 'Read story →' (BlogView.vue:25-33, 63-72).
  - Evidence: box diff 'Frame 502:145 figma[96,412,1248,348] build[174,333,1092,299.7] fill #171b22 vs #0e1116, border-colour #2b323d vs #6e5cf0, radius 22 vs 20'; dom ui-badge variant-live color rgb(255,77,77); slice blog-0.png
  - Fix: Two-column card to the frame (1248 container, pad 24, gap 32, r22, flat --sc-surface, hairline border): media panel 584x300 with the 102px tile and icon on the left; on the right a category pill plus 'Featured' label, 28/34 title, 16/25 summary, 13.5 meta; no live-red badge; make the title/card the link (Figma draws no button).
  - Linked: 17tnw2b2cez
- **blog-03** · class **A** · high · page — Article grid: 3 columns with media thumbnails and per-category pill colours versus 2 text-only columns
  - Figma: Grid 502:159/193: three 400px columns, gap 24, cards r18, fill #171b22, 1px #2b323d, pad 14/14/20/14, gap 14: thumbnail panel 372x150 (#1e232c, r14) with a 51px coloured icon tile r14 (white icon), category pill 10.5/700 ls 0.6 in its own colour (Guides green, Streaming brand, Mobile warn, Design green, Operations red, Engineering brand), title 17/600 lh 23, meta 12.5.
  - Build: .blog-grid 2 x 532, gap 28, cards r16, pad 28, no thumbnail; every category pill is the green 'preview' variant 11/600; title 20/700 lh 26; extra 14px summary paragraph; footer with 'date · N min read' and a 'Read →' link (BlogView.vue:41-49, 74-86).
  - Evidence: slice blog-0.png; dom blog-card 532x245.2 r16 pad 28; design-only y=1010 17x600 titles, y=983 10.5x700 pills; build-only y=750.7 20px card-title, y=787.7 14px card-desc
  - Fix: 3-column grid of 400px cards (1248 container, gap 24, r18, pad 14/14/20/14) with the 150px thumbnail panel and coloured icon tile per card, per-category pill colours, 17/600 title, 12.5 meta; keep the 'Read' link as the card's single link.
  - Linked: 17tnw2b2cez
- **blog-04** · class **D** · medium · page — Card count and build-only summary / Read link; detail pages have no frame
  - Figma: Featured post plus six grid cards (seven articles); no summary paragraph and no 'Read' link on cards; no frame for an article page.
  - Build: blogPosts has five posts: one featured plus four grid cards (blog.ts); each grid card adds a summary paragraph and a 'Read →' link; articles open at /blog/:slug (router/index.ts:22-26 spreads articleRoutes from router/articleRoutes.ts).
  - Evidence: blog.ts slug list (5 posts, one featured:true); dom shows 4 blog-card elements; focus list: five 'Read ... →' links, each resolves to a real route (tests/contentLinks.test.ts and articleRoutes.test.ts cover it)
  - Decision: Write two more real posts, or show four cards in the 3-column grid (a short last row)? Does the owner want the card summary and 'Read →' link kept (undrawn)? Blog post detail (/blog/:slug) has no Figma frame (MARKETING-PORTAL-GAP-FILL-HANDOFF 9a layout only) and was not audited.
  - Linked: 17tnw2b0q9h
- **blog-05** · class **B** · low · page — Article titles, categories, dates and read times are real content, not Figma placeholders
  - Figma: Placeholder titles ('Why your presentation software should never need the internet', 'NDI 101: sending your service into OBS', ...), categories (Reliability, Guides, Streaming, Mobile, Design, Operations, Engineering), dates Apr-Jul 2026 and read times 3-8 min.
  - Build: Real articles from lib/content/blog.ts: 'Why offline-first matters for Sunday morning', 'What your stage team sees on the stage display', ... categories Product Strategy / Worship Tech / Scripture / Mobile / Livestreaming, published 1 Oct 2026 (the day written), read time computed from the body.
  - Evidence: blog.ts slugs/titles/categories/published; dom meta-text '1 Oct 2026 · 2 min read'
  - Source: MARKETING-SITE-HANDOFF 1a ('Titles/authors are placeholders') and 8 (blog titles assumed); implementation/marketing/src/lib/content/types.ts honesty rules (SelahCue Team only, no invented dates or statistics); ClickUp 17tnw2b0q9h.
  - Linked: 17tnw2b0q9h
- **blog-06** · class **A** · medium · page — Card meta line drops the 'SelahCue Team' author and changes the format
  - Figma: Every card: 'SelahCue Team · Jun 2026 · 5 min' 12.5/400 #9aa4b2 (featured: 'SelahCue Team · Jul 2026 · 6 min read' 13.5).
  - Build: Grid cards show '1 Oct 2026 · 2 min read' 13px with no author; only the featured card shows 'SelahCue Team' (BlogView.vue:29-31, 46).
  - Evidence: design-only y=1042/1065/1382/1405 12.5x400 meta lines; build-only meta-text '1 Oct 2026 · 2 min read' on all four cards
  - Fix: Prefix every grid card's meta with 'SelahCue Team · ' (the handoff keeps the author as the team, never a person) and use 12.5px; keep real dates and computed read times.
  - Linked: 17tnw2b2cez
- **blog-07** · class **A** · medium · page · a11y — Meta text, 'Read →' links and badges below AA
  - Figma: Meta #9aa4b2 on #171b22 = 6.85:1; category pills 10.5/700 on #1e232c (green 6.04:1, warn 8.6:1; brand and red are below AA in Figma too, see contact-14).
  - Build: '1 Oct 2026 · 2 min read' 13px --sc-text-muted #6b7383 on #14161d = 3.79:1; 'Read →' 13/600 --sc-primary 3.83:1; 'SelahCue Journal' badge 11/600 3.38:1; footer copyright 3.79:1 (BlogView.vue:72, 85-86).
  - Evidence: report.json contrast_survey blog: '1 Oct 2026 · 2 min read' 3.79 x4, 'Read →' 3.83 x4, 'SelahCue Journal' 3.38 (required 4.5)
  - Fix: Meta to --sc-text-secondary; link and badge ink per the AA ink chosen under contact-14.
  - Linked: 17tnw2b2cez

### Careers — `careers` (Figma `503:124`)

Verdict: **diverges** · area: secondary-2 · route: `/careers`

The build keeps Figma's order (hero, culture strip, open-roles list) but is a visibly different page: 3 emoji cards instead of 4 icon-tile cards, 3 invented roles instead of Figma's 5 placeholder roles, smaller hero type with different copy, no full-bleed roles band, no tag pills and no closing 'reach out' line; it is 169px shorter (1661 vs 1830). The role meta line and eyebrow pill also fail AA, and the Apply links all share one name.

- **careers-01** · class **A** · high · page — Hero copy and type scale
  - Figma: Frame 503:139 (y79, pad 96/96/44/96, gap 20). Eyebrow pill 'CAREERS'. H1 'Build tools churches rely on' 50px/700, line-height 56, centred, 498 wide so it breaks as 'Build tools churches / rely on', ink #eef1f6. Sub 'We're a small, remote team building dependable software for a moment that can't be repeated. If that resonates, we'd love to meet you.' 19px/400, line-height 30, #9aa4b2, 700 wide. Hero ends at y458.
  - Build: src/views/CareersView.vue:14-20 and :67-69. Badge 'Join Our Team'. H1 'Build software that serves local churches worldwide' 40px/800 with an inherited 60px line-height (h=120, 952 wide). Sub 'We are an engineering-driven, remote-first team committed to high-performance, offline-first worship presentation technology.' 16px/400, line-height 24, 640 wide. .hero-section padding 80px 0 50px.
  - Evidence: python3 scripts/vp_style_diff.py --slug careers --dom $RUN/marketing/careers.blink.dom.json --limit 0 -> 'in the design, not in the build': y=222 50x700 'Build tools churches rely on' and y=354 19x400 'We're a small, remote team...'; 'in the build, not in the design': y=197.5 40px 'Build software t…
  - Fix: Match Figma's hero: H1 50px / 700 / line-height 56px with max-width about 500px; sub 19px / 30px, max-width 700px; hero padding 96px 0 44px, gap 20px between pill, H1 and sub; hero copy as Figma, subject to the owner decision in careers-07/careers-08 on company claims ('small, remote team').
  - Linked: 17tnw2b2cez
- **careers-02** · class **A** · medium · shared · ui-badge · a11y — Eyebrow pill style (UiBadge) - weight, tracking, padding, fill and ink
  - Figma: Pill 503:140 at x676, 88x27: padding 6/12, radius 999, fill #1e232c (elevated), text 'CAREERS' 12px/700 uppercase, letter-spacing 1.2px, ink #5b6bd6. Note Figma's own ink is 3.39:1 on that fill (below AA 4.5:1).
  - Build: UiBadge variant='featured' size='sm' (CareersView.vue:16): 11px/600, letter-spacing 0.55px (0.05em), padding 4px 8px, height 26.5, fill #201f3a (accent-soft), ink #6e5cf0 = 3.38:1 (fails AA). Same component and same values appear in the hero of every page in this area.
  - Evidence: dom ui-badge variant-featured: fs 11px fw 600 ls 0.55px pad 4px 8px; $RUN/report.json contrast_survey careers 'Join Our Team' 11.0px/600 = 3.38 (required 4.5).
  - Fix: Use the size-md geometry (padding 6px 12px, 12px text) with weight 700 and letter-spacing 0.1em on an elevated (#1c1f28) fill, as Figma. Because Figma's ink also fails AA (3.39:1) and #7e6eff only reaches 4.36:1 on #1c1f28, the ink needs an Uma-approved lighter primary that reaches 4.5:1; do not copy #5b6bd6 across. One fix in src/components/UiBadge.vue serves careers, affiliates, privacy and terms.
  - Linked: 17tnw2b2cew
- **careers-03** · class **A** · high · page — Culture strip: 3 emoji cards instead of 4 icon-tile cards, plus an extra heading
  - Figma: Strip 503:144 (y458, pad 32/96/48/96) directly under the hero, no heading. Four cards 294x191 at x96/414/732/1050, gap 24, radius 18, fill #171b22, 1px #2b323d, padding 26/24, gap 13. Each has a 50x50 radius-13 icon tile (fills #5b6bd6, #2bb673, #f2b53c, #ef4444) with a white 2.08px feather icon, a 17.5px/600 title (Remote-first, Real impact, Craft & ownership, Rest matters) and 14px/21px #9aa4b2 body.
  - Build: src/views/CareersView.vue:23-44 and :73-77. h2 'Why Work With Us' 26px/700, left-aligned, at y427 (not in Figma). Three cards (grid repeat(3)) 301x237, radius 16, padding 28. Icons are text emoji (globe, rocket, church) at 32px with no tile and no aria-hidden. Titles 18px/700; body 14px/21px. Container max-width 1000 (Figma content width 1248).
  - Evidence: vp_style_diff careers: design-only 'Remote-first', 'Real impact', 'Craft & ownership', 'Rest matters' (17.5x600) and their 14x400 bodies; build-only 'Why Work With Us' (section-title 26px), three icon divs 32px, h3 18px 'Fully Remote & Flexible' / 'High Technical Standards' / 'Impact for the Local …
  - Fix: Four-column grid, gap 24, content width 1248 (padding 0 96px); cards radius 18, padding 26px 24px, gap 13px, fill --sc-surface, 1px --sc-border; replace the emoji with the 50x50 radius-13 icon tile in Figma's four fills using the site's inline feather-style SVG set (MARKETING-SITE-HANDOFF 7); titles 17.5px/600, body 14px/21px; delete the 'Why Work With Us' h2; copy as Figma subject to careers-08.
  - Linked: 17tnw2b2cez
- **careers-04** · class **A** · high · page — Open roles list: heading, band, row anatomy and button
  - Figma: Band 503:173 full-bleed y729-1472, fill #171b22, pad 44/96/48/96, gap 24. H2 'Open roles' 30px/700 centred (y773). List 940 wide at x250, gap 14. Row 940x95, radius 16, fill #0e1116, 1px #2b323d, padding 20/24, gap 16: title 18px/600; below it three tag pills (department, 'Remote', 'Full-time'/'Part-time'; 12px/500 #9aa4b2 on #1e232c, radius 999, padding 5/10, h25, gap 8); at right a 99x39 'View role' button (radius 10, fill #1e232c, 1px #2b323d, 14px/600). Closing line centred, 640 wide, 15px …
  - Build: src/views/CareersView.vue:47-60 and :79-82. No band (page base #0b0d12). h2 'Open Positions' 26px/700, left-aligned (x244). Rows 952x92.5, radius 12, fill #14161d, padding 20/24, gap 16: title 18px/600, ONE meta line 'Core Engine · Remote (US/EU/Africa) · Full-time' 13px/400 in #6b7383, and a UiButton outline sm 'Apply Now →' (132x47, pill radius). No closing 'Don't see your role?' line.
  - Evidence: vp_style_diff careers: design-only 'Open roles' (30x700), 'View role' x5, tag texts, y=1388 15x400 'Don't see your role?...'; build-only 'Open Positions' (section-title 26px), 'Apply Now →' x3, role-meta 13px. dom role-row h 92.5 radius 12px; role-meta color rgb(107,115,131). Slice careers-full.png.
  - Fix: Wrap the list in a full-bleed --sc-surface band (padding 44px 96px 48px, gap 24); centre the h2 'Open roles' at 30px/700; rows 940 wide, radius 16, fill --sc-base, padding 20px 24px, gap 14 between rows; split the meta string into three pills (12px/500, --sc-text-secondary on --sc-elevated, radius 999, padding 5px 10px); button 'View role' 99x39, radius 10, elevated fill with 1px border (see careers-12); add the centred closing line below the list (its mailbox is a C item, careers-08).
  - Linked: 17tnw2b2cez
- **careers-05** · class **A** · high · page · a11y — Role meta line fails AA (muted ink on surface)
  - Figma: Department / location / type are drawn as pills with #9aa4b2 text on #1e232c = 6.25:1.
  - Build: src/views/CareersView.vue:82 .role-meta: 13px/400, --sc-text-muted #6b7383 on the row fill #14161d = 3.79:1, on all three rows.
  - Evidence: $RUN/report.json contrast_survey careers: 'Core Engine · Remote (US/EU/Africa) · Full-time', 'Web & Dashboard · Remote · Full-time', 'Customer Success · Remote · Full-time', each 13.0px/400 = 3.79 (required 4.5).
  - Fix: Set the meta text/pills in --sc-text-secondary (#a7aebe: 7.4:1 on #1c1f28), never --sc-text-muted, as part of the careers-04 restructure.
  - Linked: 17tnw2b2cez
- **careers-06** · class **A** · low · page · a11y — Apply links have identical names with no role context
  - Figma: Five 'View role' buttons, identical text, one per row (the same ambiguity exists in Figma).
  - Build: Three links named 'Apply Now →' (CareersView.vue:56). Nothing ties each link to its role title: the title is an h3 sibling in the row div, not an ancestor list item, label or description.
  - Evidence: dom focus list careers: 'Apply Now →' at y888, y997, y1105 (tag a, same accessible name).
  - Fix: Add aria-label="Apply for {role title}" (or aria-describedby pointing at the row's h3 id) to each link. No visual change.
  - Linked: 17tnw2b2cez
- **careers-07** · class **C** · high · page — Open roles are invented in both Figma and the build (and differ from each other)
  - Figma: Five roles: Senior Rust Engineer (Engineering, Remote, Full-time); Flutter / Mobile Engineer (Engineering, Remote, Full-time); Product Designer (Design, Remote, Full-time); Developer Advocate (Church Tech) (Community, Remote, Full-time); Support Specialist (Support, Remote, Part-time).
  - Build: Three different hard-coded roles (src/views/CareersView.vue:5-9): 'Rust Systems & Graphics Engineer' (Core Engine, 'Remote (US/EU/Africa)', Full-time), 'Senior Vue / Frontend Engineer' (Web & Dashboard), 'Worship Tech Solutions Specialist' (Customer Success). 'Remote (US/EU/Africa)' is an extra geography claim.
  - Evidence: grep -ri 'hiring|job posting|open roles|ATS' over docs/ and implementation/ finds nothing but MARKETING-SITE-HANDOFF (section 1a: 'Roles are illustrative placeholders'; section 8 lists open roles under 'Assumed'). dom role-title x3.
  - Decision: Keep Figma's list layout (careers-04) but ship no role the company has not opened. What does the page say when the list is empty (see careers-09)? Owner to confirm whether any real role exists to list.
  - Linked: 17tnw2b0x3h
- **careers-08** · class **C** · medium · page — Company claims and the careers@ mailbox
  - Figma: Hero: 'We're a small, remote team...'. Card 'Remote-first', 'Ship features churches use live, every week.', 'Sustainable pace - we build for the long run.' Footer line: 'reach out at careers@selahcue.app'.
  - Build: 'remote-first team' (hero), 'Fully Remote & Flexible - Work from anywhere in the world with flexible hours built around your life and family', 'Remote (US/EU/Africa)' and the build-only claim 'Your work directly supports thousands of volunteer tech teams and worship leaders every single Sunday.' (CareersView.vue:40). The build has no careers@ line.
  - Evidence: No user, install or customer count exists in the repo (README 'Known gaps': downloads do not exist yet; no installer is served). careers@selahcue.app appears only in Figma; mailboxes in the repo are support@selahcue.app (ContactView.vue:61) and affiliates@selahcue.app (AffiliateHelpView.vue:29); do…
  - Decision: Owner: what can we honestly say about team size and remote policy? Remove 'thousands of volunteer tech teams' (no usage data). Does careers@selahcue.app exist (and on which domain: selahcue.app or selahcueapp.com)? Until confirmed, Figma's closing line ships without an address.
  - Linked: 17tnw2b0x3h
- **careers-09** · class **D** · medium · page — Role destination and the empty-roles state are not designed
  - Figma: Each row has a 'View role' button but no role-detail frame exists, and no frame shows the page with zero open roles. MARKETING-SITE-HANDOFF section 8 lists 'deeper article/doc/role detail pages' as out of scope.
  - Build: Every row links to /contact via UiButton to="/contact" (CareersView.vue:56) labelled 'Apply Now →'. With careers-07 resolved honestly the list may be empty, and the build has no empty state.
  - Evidence: src/views/CareersView.vue:56; docs/design/MARKETING-SITE-HANDOFF.md section 8 ('Out of scope').
  - Decision: Uma: where does a role link go (role detail page, mailto, external ATS) and what does the Open roles band show when nothing is open ('No open roles right now' plus the 'reach out' line)? Needed before careers-04 and careers-07 can ship.
- **careers-10** · class A · duplicate of **shared-chrome-01** — Navbar frame differs from the Figma nav bar
- **careers-11** · class A · duplicate of **shared-chrome-16** — Footer frame differs from the Figma footer
- **careers-12** · class A · duplicate of **shared-chrome-27** — Buttons are pills where Figma uses 10-12px radii

### Privacy Policy — `privacy` (Figma `504:124`)

Verdict: **diverges** · area: secondary-2 · route: `/privacy`

The header treatment (centred title, muted centred last-updated line, dark page) follows Figma, but the page is 13,407px against 1,772px because the real legal draft replaced Figma's placeholder prose (class B, ClickUp 17tnw2b0x3g, PR #142). What Figma designs and the build does not match is the title (36/800 vs 44/700), section headings (22/700 vs 20/600), body (15 vs 16px), the green eyebrow pill, and header spacing.

- **privacy-01** · class **B** · low · page — Page is 7-8x taller than the frame: the real legal draft replaced Figma's placeholder prose
  - Figma: Placeholder legal prose, 1772px tall (node 504:124): intro paragraph plus eight short numbered sections, one paragraph each. MARKETING-SITE-HANDOFF section 1a/8 labels it 'placeholder - not legal advice; a real legal pass is required before launch'.
  - Build: 13407px tall: the real Privacy Policy rendered from src/lib/legal/privacy.generated.ts (generated from docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md by scripts/sync_legal.ts) through src/components/legal/LegalPage.vue, LegalBlocks.vue, LegalList.vue, LegalTable.vue. Paragraph-level differences are not reported.
  - Evidence: $RUN/report.json pairs privacy: build 13407px vs frame 1772px (height_delta +11635); vp_style_diff privacy: 461 build text nodes against 49 Figma text nodes, and only the navbar/footer words pair by text.
  - Source: ClickUp 17tnw2b0x3g, delivered by PR #142 (commit e7566a96): 'The old hand-written stubs (with the false claims) are replaced'; implementation/marketing/README.md 'Legal pages'; docs/legal/LEGAL-DRAFT-NOTES.md section 3; MARKETING-SITE-HANDOFF.md section 8 (Figma legal copy is Assumed placeholder).
- **privacy-02** · class **B** · low · page — Title, last-updated line, section titles and clause numbering come from the document itself
  - Figma: H1 'Privacy Policy'; 'Last updated: August 2026'; intro paragraph; headings '1. Our approach' style with a single paragraph per section.
  - Build: H1 'SelahCue Privacy Policy' (the document's own '#' title); 'Version 0.3 (draft) · Last updated 1 October 2026' (the document's version line); no intro paragraph, instead a 'Summary in plain language' box; 13 sections with hanging clause numbers (1.1, 1.2, ...), nested lists, tables, bold and inline code.
  - Evidence: dom h1 'SelahCue Privacy Policy'; dom time 'Version 0.3 (draft) · Last updated 1 October 2026' 14px/400 centred #a7aebe (same treatment as Figma's 14px muted centred line); dom lb-clause / lb-num spans.
  - Source: implementation/marketing/README.md 'Legal pages': the generator renders headings, numbered clauses, lists, tables, bold, inline code and safe links, and generation fails if there is no 'Version X.Y (final, YYYY-MM-DD)' line so 'Last updated' cannot silently disappear. Treatment of the last-updated …
- **privacy-03** · class **B** · medium · page — Contents sidebar with scroll-spy and a skip link are build-only
  - Figma: No table of contents, no sidebar, no skip link: a single centred 780px text column (x330-1110).
  - Build: Two-column layout (LegalPage.vue .legal-layout: 260px Contents + 48px gap + 760px text). Sticky 'Contents' nav (top 88px, scrolls within itself), active entry highlighted by scroll-spy (src/lib/legal/useScrollSpy.ts), collapses to a toggle below 820px. 'Skip to the document text' link is the first focus stop after the navbar; the Contents links are the next stops, then the document's own links.
  - Evidence: dom: .toc-label 'Contents' at x184, 14 .toc-link entries, .legal-text at x492 w760; focus list: navbar, 'Skip to the document text', 'Summary in plain language', then the remaining Contents links, then the document's own links; tests/legalPage.test.ts and scripts/legal_pages_headless.py pin it. No …
  - Source: ClickUp 17tnw2b0x3g, delivered by PR #142 (commit e7566a96): 'Contents sidebar with scroll-spy (stacks and collapses below 820px), numbered sections with deep-linkable anchors that clear the sticky navbar, summary box, accessible scrollable tables, skip link.' Also implementation/marketing/README.m…
- **privacy-04** · class **B** · medium · page — Draft banner, 'Key details' box and 'Summary in plain language' box are build-only
  - Figma: None of these are drawn. Header goes straight from the last-updated line to the intro paragraph.
  - Build: Amber 'Draft, pending legal review' banner (1072 wide, radius 12, left border 4px) with the document's own notes and highlighted {{PLACEHOLDER}} chips; a bordered 'Key details' list (entity, address, registration number, contacts, effective date); the 'Summary in plain language' box. Together they push the first section to y1581 (first section heading).
  - Evidence: dom: .draft-banner h167.4 (y308), .legal-facts h191.5 (y507), .summary-box h802.5 (y739). src/components/legal/LegalPage.vue (state.draft, doc.facts, doc.summary); src/lib/legal/document.ts legalPageState.
  - Source: docs/legal/LEGAL-DRAFT-NOTES.md section 3 and implementation/marketing/README.md 'Legal pages': a page shows the draft banner, highlights placeholders and sends noindex while any placeholder remains, the DRAFT banner is still in the markdown, or the version status is not exactly 'final' (fails clos…
- **privacy-05** · class **A** · medium · page — Page title size, weight and leading
  - Figma: H1 'Privacy Policy' 44px/700, line-height 50, centred, #eef1f6, 16px above the last-updated line (y218, h50).
  - Build: src/components/legal/LegalPage.vue .legal-title: 36px/800, line-height 1.15 (41.4px), margin 16px 0 8px, overflow-wrap anywhere.
  - Evidence: dom legal-title fs 36px fw 800 lh 41.4px; figma-style/privacy.json text 'Privacy Policy' fs 44 fw 700 lh 50.
  - Fix: LegalPage.vue .legal-title: font-size 44px; font-weight 700; line-height 50px; margin 16px 0 16px (title to version gap 16). Keep the existing 30px mobile size (out of scope).
  - Linked: 17tnw2b2cez
- **privacy-06** · class A · duplicate of **careers-02** — Eyebrow pill: wrong variant and label
- **privacy-07** · class **A** · medium · page — Header block spacing and divider
  - Figma: Hero 504:139 / 504:218: 96px above the pill, pill-to-title 16, title-to-updated 16; no rule under the header; the first text starts 40px below the last-updated line.
  - Build: LegalPage.vue .legal-page padding-top 60px (pill top 60px below the navbar, Figma 96px); title margin gives about 10px to the version line; .legal-header carries padding-bottom 32px plus a 1px --sc-border bottom rule and 32px margin before the banner/facts/body.
  - Evidence: dom legal-header y129 h146.9 border-bottom; dom ui-badge y130 (navbar bottom 69); figma-style pill y175 under a nav that ends at 79; title y218, last-updated y284 (gap 16 vs build 9.6).
  - Fix: Raise .legal-page top padding to 96px; set the title/version gap to 16px; remove the .legal-header bottom border (or confirm with Uma that the divider is wanted).
  - Linked: 17tnw2b2cez
- **privacy-08** · class **A** · medium · page — Section heading scale and numbering ink
  - Figma: Section heading ('1. Our approach' style): ONE text run 20px/600, line-height 26, #eef1f6 (number and title the same ink); 10px to its paragraph; 28px between sections.
  - Build: LegalPage.vue .sec-h2: 22px/700, line-height 1.3 (28.6px), margin 36px 0 12px; the number is a separate .sec-num span in --sc-text-secondary (#a7aebe), so '1.' is muted next to a bright title.
  - Evidence: dom sec-title sec-h2 fs 22px fw 700 lh 28.6px (e.g. 'Who this policy covers' y1581); sec-num color rgb(167,174,190); figma-style/privacy.json '1. Our approach' fs 20 fw 600 lh 26 c #eef1f6; heading-to-body gap 10 (Figma) vs 12.4 (build).
  - Fix: LegalPage.vue .sec-h2: font-size 20px; font-weight 600; line-height 26px; margin 28px 0 10px; .sec-num inherits the heading ink. Hanging clause numbers (1.1, 1.2) in the body stay (B, privacy-02).
  - Linked: 17tnw2b2cez
- **privacy-09** · class **A** · medium · page — Body type scale and text measure
  - Figma: Body 16px/400, line-height 26, #9aa4b2; intro paragraph 17px/27; text column 780 wide at x330 (centred); Figma draws one paragraph per section, so paragraph-to-paragraph spacing, lists inside clauses and tables are not drawn.
  - Build: LegalBlocks.vue .lb-p and LegalList.vue .ll-item: 15px, line-height 1.7 (25.5px), --sc-text-secondary (#a7aebe, a mapped colour: B); paragraph margin-bottom 16px; text column .legal-text max-width 760px at x492 (the Contents column takes x184-440).
  - Evidence: dom lb-p fs 15px lh 25.5px; legal-text w 760 x 492; figma-style/privacy.json body nodes fs 16 lh 26 w 780 x 330.
  - Fix: Body 16px / 26px in LegalBlocks.vue and LegalList.vue; .legal-text max-width 780px; keep 16px paragraph spacing inside multi-paragraph sections (undrawn, so it is a designer call, not a mismatch).
  - Linked: 17tnw2b2cez
- **privacy-10** · class **B** · low · page — Inline link colour is --sc-primary-hover with an underline
  - Figma: No inline links are drawn on this frame (other frames use primary #5b6bd6, 4.07:1 on #0e1116).
  - Build: LegalInline.vue .li-link: #7e6eff (--sc-primary-hover), underlined, 3px offset; hover turns to --sc-text.
  - Evidence: dom li-link color rgb(126,110,255). Measured: --sc-primary #6e5cf0 on #0b0d12 = 4.12:1 (fails AA 4.5:1); #7e6eff on #0b0d12 = 5.15:1.
  - Source: Measurement: --sc-primary 4.12:1 on the page base fails AA for 15px text; the build keeps an accessible ink at 5.15:1. Flag for Uma: the 'links in --sc-primary' rule in MARKETING-PORTAL-GAP-FILL-HANDOFF.md line 193 cannot be met on this background without this lighter token.
- **privacy-11** · class **C** · medium · page — Figma privacy mailbox and date are not backed
  - Figma: 'Questions about privacy? Email privacy@selahcue.app.'; 'Last updated: August 2026'.
  - Build: The draft names support@selahcueapp.com as the Privacy contact (domain selahcueapp.com); ContactView.vue uses support@selahcue.app (domain selahcue.app). Date shown is the document's version date (1 October 2026).
  - Evidence: grep: privacy@selahcue.app appears only in Figma and docs/legal/LEGAL-DRAFT-NOTES.md, which says in item 12 (around line 443) there is 'no evidence that this mailbox or domain exists'; row L-1 requires one real email domain before publication.
  - Decision: Owner: which domain and privacy mailbox are real (L-1 gate)? Do not copy Figma's privacy@ address; legal wording itself is not part of this audit.
  - Linked: 17tnw2b0x3h

### Terms of Service — `terms` (Figma `504:203`)

Verdict: **diverges** · area: secondary-2 · route: `/terms`

Same shape as Privacy: header treatment follows Figma, but the page is 14,441px against 1,959px because the real Terms of Service draft replaced the placeholder prose (class B, ClickUp 17tnw2b0x3g, PR #142). Title, section heading and body type scales, the eyebrow pill, header spacing and the list-marker colour do not match what Figma draws.

- **terms-01** · class **B** · low · page — Page is 7-8x taller than the frame: the real legal draft replaced Figma's placeholder prose
  - Figma: Placeholder legal prose, 1959px tall (node 504:203): intro paragraph plus nine short numbered sections, one paragraph each. MARKETING-SITE-HANDOFF section 1a/8 labels it 'placeholder - not legal advice; a real legal pass is required before launch'.
  - Build: 14441px tall: the real Terms of Service rendered from src/lib/legal/terms.generated.ts (generated from docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md by scripts/sync_legal.ts) through src/components/legal/LegalPage.vue, LegalBlocks.vue, LegalList.vue, LegalTable.vue. Paragraph-level differences are not reported.
  - Evidence: $RUN/report.json pairs terms: build 14441px vs frame 1959px (height_delta +12482); vp_style_diff terms: 538 build text nodes against 53 Figma text nodes, and only the navbar/footer words pair by text.
  - Source: ClickUp 17tnw2b0x3g, delivered by PR #142 (commit e7566a96): 'The old hand-written stubs (with the false claims) are replaced'; implementation/marketing/README.md 'Legal pages'; docs/legal/LEGAL-DRAFT-NOTES.md section 3; MARKETING-SITE-HANDOFF.md section 8 (Figma legal copy is Assumed placeholder).
- **terms-02** · class **B** · low · page — Title, last-updated line, section titles and clause numbering come from the document itself
  - Figma: H1 'Terms of Service'; 'Last updated: August 2026'; intro paragraph; headings '1. Our approach' style with a single paragraph per section; a two-item bullet list under 2. Your licence.
  - Build: H1 'SelahCue Terms of Service' (the document's own '#' title); 'Version 0.3 (draft) · Last updated 1 October 2026' (the document's version line); no intro paragraph, instead a 'Summary in plain language' box; 25+ sections in Parts A-F with hanging clause numbers (1.1, 1.2, ...), nested lists, tables, bold and inline code.
  - Evidence: dom h1 'SelahCue Terms of Service'; dom time 'Version 0.3 (draft) · Last updated 1 October 2026' 14px/400 centred #a7aebe (same treatment as Figma's 14px muted centred line); dom lb-clause / lb-num spans.
  - Source: implementation/marketing/README.md 'Legal pages': the generator renders headings, numbered clauses, lists, tables, bold, inline code and safe links, and generation fails if there is no 'Version X.Y (final, YYYY-MM-DD)' line so 'Last updated' cannot silently disappear. Treatment of the last-updated …
- **terms-03** · class **B** · medium · page — Contents sidebar with scroll-spy and a skip link are build-only
  - Figma: No table of contents, no sidebar, no skip link: a single centred 780px text column (x330-1110).
  - Build: Two-column layout (LegalPage.vue .legal-layout: 260px Contents + 48px gap + 760px text). Sticky 'Contents' nav (top 88px, scrolls within itself), active entry highlighted by scroll-spy (src/lib/legal/useScrollSpy.ts), collapses to a toggle below 820px. 'Skip to the document text' link is the first focus stop after the navbar; the Contents links are the next stops, then the document's own links.
  - Evidence: dom: .toc-label 'Contents' at x184, 26 .toc-link entries, .legal-text at x492 w760; focus list: navbar, 'Skip to the document text', 'Summary in plain language', then the remaining Contents links, then the document's own links; tests/legalPage.test.ts and scripts/legal_pages_headless.py pin it. No …
  - Source: ClickUp 17tnw2b0x3g, delivered by PR #142 (commit e7566a96): 'Contents sidebar with scroll-spy (stacks and collapses below 820px), numbered sections with deep-linkable anchors that clear the sticky navbar, summary box, accessible scrollable tables, skip link.' Also implementation/marketing/README.m…
- **terms-04** · class **B** · medium · page — Draft banner, 'Key details' box and 'Summary in plain language' box are build-only
  - Figma: None of these are drawn. Header goes straight from the last-updated line to the intro paragraph.
  - Build: Amber 'Draft, pending legal review' banner (1072 wide, radius 12, left border 4px) with the document's own notes and highlighted {{PLACEHOLDER}} chips; a bordered 'Key details' list (entity, address, registration number, contacts, effective date); the 'Summary in plain language' box. Together they push the first section to y1685 (first Part title) / y1752 (first section heading).
  - Evidence: dom: .draft-banner h167.4 (y308), .legal-facts h191.5 (y507), .summary-box h898.5 (y739). src/components/legal/LegalPage.vue (state.draft, doc.facts, doc.summary); src/lib/legal/document.ts legalPageState.
  - Source: docs/legal/LEGAL-DRAFT-NOTES.md section 3 and implementation/marketing/README.md 'Legal pages': a page shows the draft banner, highlights placeholders and sends noindex while any placeholder remains, the DRAFT banner is still in the markdown, or the version status is not exactly 'final' (fails clos…
- **terms-05** · class **A** · medium · page — Page title size, weight and leading
  - Figma: H1 'Terms of Service' 44px/700, line-height 50, centred, #eef1f6, 16px above the last-updated line (y218, h50).
  - Build: src/components/legal/LegalPage.vue .legal-title: 36px/800, line-height 1.15 (41.4px), margin 16px 0 8px, overflow-wrap anywhere.
  - Evidence: dom legal-title fs 36px fw 800 lh 41.4px; figma-style/terms.json text 'Terms of Service' fs 44 fw 700 lh 50.
  - Fix: LegalPage.vue .legal-title: font-size 44px; font-weight 700; line-height 50px; margin 16px 0 16px (title to version gap 16). Keep the existing 30px mobile size (out of scope).
  - Linked: 17tnw2b2cez
- **terms-06** · class A · duplicate of **careers-02** — Eyebrow pill: wrong variant and label
- **terms-07** · class **A** · medium · page — Header block spacing and divider
  - Figma: Hero 504:139 / 504:218: 96px above the pill, pill-to-title 16, title-to-updated 16; no rule under the header; the first text starts 40px below the last-updated line.
  - Build: LegalPage.vue .legal-page padding-top 60px (pill top 60px below the navbar, Figma 96px); title margin gives about 10px to the version line; .legal-header carries padding-bottom 32px plus a 1px --sc-border bottom rule and 32px margin before the banner/facts/body.
  - Evidence: dom legal-header y129 h146.9 border-bottom; dom ui-badge y130 (navbar bottom 69); figma-style pill y175 under a nav that ends at 79; title y218, last-updated y284 (gap 16 vs build 9.6).
  - Fix: Raise .legal-page top padding to 96px; set the title/version gap to 16px; remove the .legal-header bottom border (or confirm with Uma that the divider is wanted).
  - Linked: 17tnw2b2cez
- **terms-08** · class **A** · medium · page — Section heading scale and numbering ink
  - Figma: Section heading ('1. Our approach' style): ONE text run 20px/600, line-height 26, #eef1f6 (number and title the same ink); 10px to its paragraph; 28px between sections.
  - Build: LegalPage.vue .sec-h3 (the Terms render every section as an h3 under a Part h2): 17px/600, line-height 1.4 (23.8px), margin 22px 0 8px; the Part titles are h2 13px/700 uppercase, tracking 0.78px, in muted ink (documented structure, see terms-02/04). The number is a separate .sec-num span in --sc-text-secondary (#a7aebe), so '1.' is muted next to a bright title.
  - Evidence: dom sec-title sec-h3 fs 17px fw 600 lh 23.8px (e.g. 'About these Terms' y1752); sec-num color rgb(167,174,190); figma-style/terms.json '2. Your licence' fs 20 fw 600 lh 26 c #eef1f6; Figma heading-to-body gap 10.
  - Fix: LegalPage.vue .sec-h3 (Terms) and .sec-h2 (Privacy): font-size 20px; font-weight 600; line-height 26px; margin 28px 0 10px; .sec-num inherits the heading ink. Keep the Part titles and hanging clause numbers (B, terms-02).
  - Linked: 17tnw2b2cez
- **terms-09** · class **A** · medium · page — Body type scale and text measure
  - Figma: Body 16px/400, line-height 26, #9aa4b2; intro paragraph 17px/27; text column 780 wide at x330 (centred); Figma draws one paragraph per section, so paragraph-to-paragraph spacing, lists inside clauses and tables are not drawn.
  - Build: LegalBlocks.vue .lb-p and LegalList.vue .ll-item: 15px, line-height 1.7 (25.5px), --sc-text-secondary (#a7aebe, a mapped colour: B); paragraph margin-bottom 16px; text column .legal-text max-width 760px at x492 (the Contents column takes x184-440).
  - Evidence: dom lb-p fs 15px lh 25.5px; legal-text w 760 x 492; figma-style/terms.json body nodes fs 16 lh 26 w 780 x 330.
  - Fix: Body 16px / 26px in LegalBlocks.vue and LegalList.vue; .legal-text max-width 780px; keep 16px paragraph spacing inside multi-paragraph sections (undrawn, so it is a designer call, not a mismatch).
  - Linked: 17tnw2b2cez
- **terms-10** · class **B** · low · page — Inline link colour is --sc-primary-hover with an underline
  - Figma: No inline links are drawn on this frame (other frames use primary #5b6bd6, 4.07:1 on #0e1116).
  - Build: LegalInline.vue .li-link: #7e6eff (--sc-primary-hover), underlined, 3px offset; hover turns to --sc-text.
  - Evidence: dom li-link color rgb(126,110,255). Measured: --sc-primary #6e5cf0 on #0b0d12 = 4.12:1 (fails AA 4.5:1); #7e6eff on #0b0d12 = 5.15:1.
  - Source: Measurement: --sc-primary 4.12:1 on the page base fails AA for 15px text; the build keeps an accessible ink at 5.15:1. Flag for Uma: the 'links in --sc-primary' rule in MARKETING-PORTAL-GAP-FILL-HANDOFF.md line 193 cannot be met on this background without this lighter token.
- **terms-11** · class **A** · low · page — List markers: dot colour and indent
  - Figma: Bullets under '2. Your licence': 5px dots in #5b6bd6 (primary) at x330, text starting at x345 (10px gap), 16px/26.
  - Build: LegalList.vue .ll-item::before: 5px dot in --sc-text-secondary, left 4px, text indent 20px, 15px/1.7.
  - Evidence: dom ll-item pad 0 0 0 20px; Figma boxes Ellipse 504:233 / 504:237 fill #5b6bd6 5x5 at x330; slice reference/terms.png crop (300,530,1140,720).
  - Fix: LegalList.vue: marker colour var(--sc-primary), left 0, item padding-left 15px (dot-to-text gap 10px); size and type per terms-09.
  - Linked: 17tnw2b2cez
- **terms-12** · class **C** · medium · page — Figma legal mailbox and plan names are not backed
  - Figma: 'Questions about these terms? Email legal@selahcue.app.'; 'Paid (Pro / Church): the features and outputs described on the Pricing page'; 'Free: run a service on a single machine, forever, at no cost.'; 'Last updated: August 2026'.
  - Build: The draft names support@selahcueapp.com as Contact and Legal notices (domain selahcueapp.com); ContactView.vue uses support@selahcue.app (domain selahcue.app). Plan names and limits come from the draft, not from Figma. Date shown is the document version date.
  - Evidence: grep: legal@selahcue.app exists only in Figma; docs/legal/LEGAL-DRAFT-NOTES.md row L-1 (one email domain, real mailboxes) and item 12 (no evidence the mailbox/domain exists). DECISION-LOG DEC-008 fixes the tiers as Free / Pro / Platinum (not Pro / Church); pricing itself is owned by D1.
  - Decision: Owner: which domain and which legal/support mailboxes are real (L-1 gate)? Do not copy Figma's legal@ address. Plan names in the final Terms must follow DEC-008 (Free / Pro / Platinum), not Figma's 'Pro / Church'.
  - Linked: 17tnw2b0x3h

### Sign in — `signin` (Figma `505:124`)

Verdict: **diverges** · area: auth · route: `/signin`

Page geometry, the brand lockup, the footer row and the primary-button colour are close, and the card is left-aligned in both (it is NOT centred on this frame). The biggest differences are the heading and body copy, the missing 'Continue with Google' button and 'or' divider (no OAuth exists in the repo), the 'Forgot?' link moved out of the label row, an extra info banner, and the field styling (label ink and size, input well fill, a placeholder that fails AA at 3.45:1). Card-level differences that repeat on every auth state (fields, buttons, card width, banner) are listed once here.

- **signin-01** · class **A** · high · page — Sign-in heading copy
  - Figma: Heading 'Welcome back', Inter Bold 26 text/primary, left-aligned (node 505:124, text at x=541 y=233.5, ta LEFT).
  - Build: Heading 'Sign in to SelahCue' (SignInView.vue:318, .au-title.au-title-form 26px/700). Size, weight and ink match; the words do not. 'Sign in to SelahCue' is the DESKTOP A1 title (ACCOUNT-SETUP-HANDOFF.md:63), not the web frame.
  - Evidence: python3 scripts/vp_style_diff.py --slug signin --dom $RUN/marketing/signin.blink.dom.json --limit 0 -> figma-only 'Welcome back' (y=233.5, 26x700); build-only 'Sign in to SelahCue' (au-title au-title-form, y=197.4). Figma text-align is LEFT, so the heading is not centred.
  - Fix: Change the h1 text in SignInView.vue:318 to 'Welcome back' (keep the h1, tabindex=-1 and the focusHeading behaviour). Update the strings pinned in tests/authViews.test.ts and scripts/auth_pages_headless.py if they assert the old heading.
  - Linked: 17tnw2b2cf1
- **signin-02** · class **C** · medium · page — Sign-in body copy names billing and a paid plan
  - Figma: Body 'Sign in to manage your plan, billing and license. You don't need an account to run SelahCue — only to manage a paid plan.' 14.5/22 text/muted, three lines (h=66).
  - Build: 'Manage your plan, license and the devices you have activated.' (SignInView.vue:319). 'billing' and 'paid plan' are not claimed; the 'no account needed' sentence was moved into an info banner (see signin-04).
  - Evidence: Style diff: figma-only y=282.5 (14.5x400) vs build-only 'Manage your plan, license…' (au-body, y=249.9). MARKETING-SITE-HANDOFF.md §8 (line 160) lists 'subscription tiers & billing terms' as Assumed. AUTH-LANDING-PAGES-HANDOFF.md §14: no checkout/plan-change/payment-method frames, 'blocked on the c…
  - Decision: Owner: Figma promises 'billing' and 'a paid plan'; there is no billing or checkout in the repo and the commercial model (pricing decision D1) is open. Approve a body that keeps Figma's layout (three lines, same sentence order) but ships no billing/paid-plan claim, e.g. 'Sign in to manage your plan and license. You don't need an account to run SelahCue.' — or confirm billing is real. The build cur…
- **signin-03** · class **C** · high · page — 'Continue with Google' button and 'or' divider
  - Figma: Divider row (505:144: two 1px #2b323d rules + 'or' 13/400 text/muted) and a secondary button 'Continue with Google' (505:148: h44 r12 fill #1e232c, 1px #2b323d border, label 14.5/600 text/primary, 18px #f2b53c ellipse standing in for the Google mark 505:149).
  - Build: Neither is rendered. SignInView.vue header comment records why: DEC-007 chose SelahCue-owned email/password and rejected OIDC; the account GraphQL schema has no social mutation; no config key for a provider exists.
  - Evidence: Style diff: figma-only 'or' (y=601.5) and 'Continue with Google' (y=648.5). DECISION-LOG.md:293 (DEC-007). MARKETING-SITE-HANDOFF.md §8 (line 161) lists 'the OAuth provider(s) on Sign in' as an Assumed placeholder. grep of implementation/api finds OIDC only as a redaction pattern (graphql/redaction…
  - Decision: Owner/Uma: remove the 'or' divider and the Google button from the Sign in frame (DEC-007: email/password only), or reopen DEC-007 to add a social provider. The build correctly ships neither today. ClickUp 17tnw2b0x3h is NOT the owner of this: it removes unbacked claims the build already shows, whereas this is a feature the build never had.
- **signin-04** · class **D** · medium · page — Build-only info banner on Sign in
  - Figma: No banner on the card. The 'you don't need an account to run SelahCue' message is the second sentence of the body paragraph (505:124).
  - Build: AuthBanner kind=info 'You don't need an account to run SelahCue' / 'Signing in manages your plan, license and devices. Live presentation works offline, always.' closes the card (SignInView.vue:369), about 107px of height. No handoff specifies a banner for Sign in: AUTH-LANDING-PAGES-HANDOFF.md §1 carries the never-blank invariant on the new /verify and /reset frames, not on 505:124.
  - Evidence: Style diff build-only: '◆' / 'You don't need an account to run SelahCue' (au-banner-title y=642.4) / 'Signing in manages your plan…' (au-banner-body y=663.6). Slice signin-0.png shows the banner under the button.
  - Decision: Uma: should Sign in carry the reassurance banner (build) or the in-body sentence (Figma)? If the banner stays, draw it in 505:124 and drop the sentence from the body; if not, remove the banner and restore the sentence (subject to signin-02).
- **signin-05** · class **A** · medium · shared · form-field — 'Forgot?' link position and label
  - Figma: 'Forgot?' 13/500 accent/brand sits in the Password LABEL row, right-aligned against the label (505:137, x=851 y=451.5 w=48). MARKETING-PORTAL-GAP-FILL-HANDOFF.md §3d: visible text 'Forgot?', aria-label 'Forgot your password?'.
  - Build: A separate row BELOW the password input, text 'Forgot your password?' 13/400 --sc-primary, right-aligned (SignInView.vue:346-348; auth.css:166-170 .au-inline-link margin -4px 0 4px). The comment at auth.css:163 says 'matching Sign in 505:124' but the frame puts it in the label row.
  - Evidence: Style diff: figma-only 'Forgot?' (y=451.5, 13x500) vs build-only 'Forgot your password?' (y=534.9, 13px). Slice signin-0.png.
  - Fix: Add a label-row slot to FormField (label left, link right) and render the link there with visible text 'Forgot?' (13px/500 --sc-primary) and aria-label='Forgot your password?'. Keep the DOM order input then link (position it with CSS) so the tab order stays Email, Password, Forgot, Sign in (GAP-FILL §3d).
  - Linked: 17tnw2b2cew
- **signin-06** · class **A** · medium · page — Field label size, weight and ink (all auth forms)
  - Figma: Label Inter Medium 13, text/muted #9aa4b2 (maps to --sc-text-secondary), 16px line, 7px gap to the input (AUTH-LANDING-PAGES-HANDOFF.md §2.3; e.g. 505:132).
  - Build: Label 14px/600 --sc-text (#f4f6fb): primary ink where Figma has muted, and larger and heavier. 6px gap (FormField.vue:119-134). Same on verify-v3, verify-v6, reset-r1, reset-r2, reset-r3, reset-r4, reset-r7. MARKETING-PORTAL-GAP-FILL-HANDOFF.md §10a documents 14px SemiBold --sc-text for the generic FormField; AUTH §2.3 (later, written for these frames) is the governing spec for auth cards and Figma agrees with it.
  - Evidence: Style diff 'Email' / 'Password': font-size figma 13px vs build 14.0px; font-weight 500 vs 600; colour figma #9aa4b2 vs build #f4f6fb (no '~', so not the token layer).
  - Fix: Auth variant of FormField (FormField is also used by Contact, SignUp, ForgotPassword, Affiliate and Admin settings, so do not change the generic style): label font 500 13px/16px, color var(--sc-text-secondary), gap 7px. Uma to confirm the generic component keeps §10a.
  - Linked: contact-19, 17tnw2b2cf1
- **signin-07** · class **A** · medium · page — Input well fill, padding and focus/error stroke (all auth forms)
  - Figma: Input 358x44, padding 13/14, radius 10, fill bg/base (AUTH §2.2: 'input well' maps to --sc-inset #0f1116, darker than the card), 1px --sc-border; focus 1.5px accent/brand and error 1.5px accent/live with no halo (747:153, 747:183 sw 1.5).
  - Build: Fill --sc-elevated #1c1f28 (a lighter chip than the card), padding 12/16, painted 45px tall; focus = 1px primary border plus 3px rgba(110,92,240,.25) halo; error = 1px --sc-live (FormField.vue:145-180). GAP-FILL §3a/§10a say --sc-elevated, but AUTH §2.2 maps the input well to --sc-inset and the frames draw it. Same on every state with a field.
  - Evidence: Style diff boxes: 'Frame 505:134 … fill figma #0e1116 vs build #1c1f28'; 'field-input build[542,337,356,45]' vs figma[541,389.5,358,44].
  - Fix: Auth variant: background var(--sc-inset); padding 13px 14px; height 44px; focus and error as a 1.5px stroke in --sc-primary / --sc-live (inset box-shadow so layout does not move) and remove the 3px halo.
  - Linked: contact-19, 17tnw2b2cf1
- **signin-08** · class **A** · high · page · a11y — Placeholder text fails AA
  - Figma: Placeholder 'you@yourchurch.org' 15/400 #9aa4b2 on the #0e1116 well = 7.50:1.
  - Build: Placeholder uses --sc-text-muted #6b7383 on --sc-elevated #1c1f28 = 3.45:1, below the 4.5:1 AA minimum for normal text (FormField.vue:158-160; even on --sc-inset it would be 3.96:1). Same on verify-v3, verify-v6, reset-r4.
  - Evidence: $RUN/report.json contrast_survey: the placeholder address on signin, verify-v3, verify-v4, verify-v6, reset-r4, reset-r5 = 3.45 (required 4.5). Style diff colour: figma #9aa4b2 vs build #6b7383.
  - Fix: Auth cards: .field-input::placeholder { color: var(--sc-text-secondary) } (#a7aebe = 7.40:1 on --sc-elevated, 8.49:1 on --sc-inset).
  - Linked: 17tnw2b2cf1
- **signin-09** · class **A** · medium · page — Vertical rhythm between fields (all auth forms)
  - Figma: A field is label 16 + gap 7 + input 44 (plus gap 7 + 17px hint/error when one shows); fields sit 18px apart (card gap 18). E.g. 505:131 h67, next field starts +85px.
  - Build: FormField reserves .field-meta min-height 20px under EVERY field even when empty, adds margin-bottom 16px, and the label line box is 21px: pitch 21+6+45+6+20+16 = 114px vs Figma 85px, about +29px per field (FormField.vue:119-125, 224-230). The verify-v6 card is 475 vs 438 tall.
  - Evidence: verify-v3: Figma input bottom 516.5 to button top 534.5 = 18px; build input 456+45=501 to button 543 = 42px (diff y-shift +25.0 at the button label). Boxes: 'card 505:128 height figma 518 vs build 591.3'.
  - Fix: Auth variant: .form-field { gap: 7px; margin-bottom: 0 }, .field-meta { min-height: 0 } and render the meta row only when a hint or error exists (17px line, 7px above); make the form a flex column with gap 18px.
  - Linked: 17tnw2b2cf1
- **signin-10** · class **A** · medium · page — Button heights and the secondary button border (all auth states)
  - Figma: Primary 358x47 radius 12, label 15.5/600 (505:142); secondary 358x44 radius 12, fill --sc-elevated plus a 1px --sc-border (746:181), label 14.5/600.
  - Build: UiButton size-lg padding 16px makes a <button> 51px tall (auth.css:259-267 only sets min-height, which cannot shrink it); link buttons ('Continue to sign in', 'Back to Sign in') are 55.3px and 53.8px because they inherit the page line-height; the secondary variant has no border (UiButton.vue:108-111). Radius 12 and fonts match.
  - Evidence: Boxes: signin 'ui-button variant-primary … build[542,557,356,51]'; verify-v2 'btn-primary 743:148 height figma 47 vs build 55.3'; verify-v5 'btn-secondary 746:181 border figma #2b323d 1px vs build none; height figma 44 vs build 53.8'.
  - Fix: auth.css: .au-btn.ui-button { height: 47px; min-height: 47px; padding-block: 0; line-height: 1.2 }, .au-btn.au-btn-secondary { height: 44px; border: 1px solid var(--sc-border) }. Auth-scoped override, so the shared UiButton does not have to change.
  - Linked: 17tnw2b2cf1
- **signin-11** · class **A** · medium · page — Card content is 356px wide, Figma 358px
  - Figma: Card 430 wide, padding 36, 1px stroke drawn INSIDE the frame, so the content column is 358px (x=541 to 899).
  - Build: border-box 430 with a 1px CSS border plus 36px padding leaves 356px (x=542) (auth.css:54-65). Every text box, input and button is 2px narrower. Visible effect: on verify-v1 the title 'Verifying your email address…' is one 29px line in Figma but wraps to two 30px lines in the build (h1 h=60), making that card 33px taller (272 vs 239). Likely cause: the title's natural width is about 357px, between 356 and 358 (not measured directly).
  - Evidence: Boxes: 'input … figma[541,.,358,44] build[542,.,356,45]'; verify-v1 dom h1 h=60 th=59; verify-v1 diff 'card 743:129 height figma 239 vs build 272'; slice verify-v1-0.png.
  - Fix: auth.css:54-65: .au-card { padding: 35px } (35 + 1px border = 36px inset, content 358px) and the mobile paddings 24 to 23 and 20/18 to 19/17. Re-check the V1 title stays on one line.
  - Linked: 17tnw2b2cf1
- **signin-12** · class D · duplicate of **account-25** — Brand-coloured link text fails AA in the design and in the build
- **signin-13** · class **B** · low · page — Eye toggle inside the password field
  - Figma: Password field drawn with bullets only, no show/hide control (505:140).
  - Build: FormField draws an eye / eye-off icon button inside the field, a tab stop between Password and Forgot (FormField.vue:81-97, 187-210). Tab order is Email, Password, Show password, Forgot, Sign in, Create an account.
  - Evidence: dom focus list for signin: input, input, button 'Show password', a 'Forgot your password?', button 'Sign in', a 'Create an account'.
  - Source: MARKETING-PORTAL-GAP-FILL-HANDOFF.md §3a ('Filled' row: password shows dots with a show/hide toggle, eye icon) and §10a (password toggle: eye / eye-off icon inside the field). On /reset the later AUTH handoff §5.1/§8.2/§12 specifies the text 'Show' instead: see reset-r1-01.
- **signin-14** · class **D** · medium · page — Sign-in states other than the default have no frame
  - Figma: Only the default state is drawn (505:124). MARKETING-PORTAL-GAP-FILL-HANDOFF.md §3b specifies submitting, wrong credentials, rate limited, server error and success in prose; its Figma frames are 'to be added' (GAP-07).
  - Build: The build renders submitting (button spinner, fields 50%), a rejection banner 'Invalid email or password' / 'Check both and try again.' (§3b says 'Please try again.'), 'Too many attempts' / 'Wait a few minutes, then try again.' (§3b specifies a countdown; the API gives no retry-after), an unreachable banner, a session-expired notice 'You've been signed out', 'This account isn't ready to sign in yet' (POLICY_DENIED), a signed-in-but-redirect-failed card, and a resend-sent card. Field errors read…
  - Evidence: SignInView.vue (state machine and template); lib/auth/messages.ts; lib/auth/emailPolicy.ts:81-82; GAP-FILL §3b, §3c.
  - Decision: Uma: draw frames for these states (or confirm the prose) so the build can be reviewed against a design, and say which validation wording is canonical (GAP-FILL §3c or the shipped emailPolicy wording).
- **signin-15** · class **B** · low · page — No password-length rule on Sign in
  - Figma: GAP-FILL §3c: password 'Too short (<8 chars)' shows 'Password must be at least 8 characters'. Figma draws no validation state.
  - Build: Sign in validates only email format and an empty password ('Enter your password.'); a short password is submitted to the server (SignInView.vue:131-146 validate(), comment inside it).
  - Evidence: SignInView.vue:131-146.
  - Source: AUTH-LANDING-PAGES-HANDOFF.md §11.2: GAP-FILL §3c/§4d password rules are wrong (API is 10-200 characters, length-only). SignInView.vue:131-146 (comment): a length message on a sign-in form would leak policy and lock out legacy passwords.
- **signin-16** · class D · duplicate of **shared-chrome-33** — Every auth state keeps the site-default document title

### Account dashboard — `account` (Figma `506:124`)

Verdict: **diverges** · area: account · route: `/account`

The page is structurally a different design: a top tab bar over one 1092px column with six tabs and a fourth Bible card, where Figma has a header band, a 240px sidebar and three 976px cards, and no copy or sample data matches. The biggest gaps are the missing sidebar, the missing activation meter and 'Manage devices' button, a device table with a fabricated IP column, secondary labels that fail AA, and a Sign out that never signs out.

- **account-01** · class **A** · high · page — Section navigation is a top tab bar; Figma draws a left sidebar card
  - Figma: Left sidebar card 506:151 (x96,y205, 240x250, fill #171b22, 1px #2b323d, r16, pad 18/14, gap 6) holding five rows 506:152-160, each 212x38 pad 10/12, label 14.5px: Overview, Subscription & billing, License, Invoices, Settings. Selected row 506:154 = fill #1e232c, r9, label 600 #5b6bd6; the others 400 #eef1f6. The three cards sit to its right (x368, w976).
  - Build: No sidebar. <nav class="portal-tabs"> (src/views/AccountView.vue:150-160, CSS 517-552) is a horizontal row of six <button class="tab-btn">: Overview, Subscription, License, Bibles (+ '3 Entitled' badge), Invoices, Settings. 15px/500 --sc-text-secondary, r8, active = --sc-elevated 600, 1px rule under the row (y227, h44). Labels differ: 'Subscription' not 'Subscription & billing', extra 'Bibles', no 'Devices'.
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 -> 'Overview' x +70 (122 -> 192), text-align left -> center, weight 400 -> 600 (active tab); 'Subscription & billing' fuzzy-pairs with build h2 'Subscription & Plan'; box 'Frame 506:151 width 240 v…
  - Fix: Replace .portal-tabs with a sidebar column per 506:151: 240px card (--sc-surface, 1px --sc-border, r16, pad 18/14, gap 6) of links 212x38 pad 10/12, 14.5px/400 --sc-text; order Overview, Subscription & billing, License, Devices (position 4, AUTH-LANDING-PAGES-HANDOFF 7), Invoices, Settings. Selected = --sc-elevated fill, r9, 600, aria-current="page". Real links (router-link / in-page anchors), not <button>; keep aria-label="Account sections". Below 1200px the sidebar stacks above the content (GAP-FILL 8d). See account-25 for the accent-ink contrast problem on the selected label.
  - Linked: 17tnw2b2cf2
- **account-02** · class **A** · high · page — Page grid and card geometry: single 1092px column vs sidebar + 976px column
  - Figma: Content band x96-1344 (1248 wide, 96px gutters): sidebar 240 + gap 32 + column 976 (x368). Cards stack with gap 24, starting 8px below the header band. Card: fill #171b22, 1px #2b323d, r20, pad 26/28, inner gap 18. Heights: Subscription 506:163 = 283, License 506:190 = 399, Billing 507:124 = 282.
  - Build: .container max-width 1140 + 24px gutter = one 1092px column at x174-1266 (AccountView.vue:438-442); cards stack with gap 32 (555-559); .portal-card r16, pad 32 (561-566), card-header margin-bottom 24 (568-573); fill --sc-surface. Measured card heights 317 / 446 / 298 (+ the two build-only cards).
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 boxes: 'Frame 506:163 radius figma 20 vs build 16; width figma 976 vs build 1092'; 'Frame 506:190 radius 20 vs 16, height 399 vs 446'. Every x delta on the page (e.g. 'Subscription' -90.9, 'Change …
  - Fix: Page container 1248px max (96px gutters at 1440) with a two-column grid: grid-template-columns: 240px minmax(0,1fr); gap 32px. Cards r20, padding 26px 28px, inner gap 18, inter-card gap 24; first card 8px below the header band. The 1140 container is a shared/app-shell decision - see account-26.
  - Linked: 17tnw2b2cf2
- **account-03** · class **A** · high · page — Account header band: avatar, identity lines, plan pill and Sign out differ
  - Figma: Band 506:139 (y79-197, pad 44/96/24, gap 16), one left-aligned row: avatar 506:140 50x50 circle, solid #5b6bd6, 'GC' 18/700 white; org name 20/700 #eef1f6 over email 14/400 #9aa4b2 (gap 3); 'PRO PLAN' pill 506:146 80x23 r999 fill #1e232c, 11/700 ls 0.7 #5b6bd6; 'Sign out' 506:148 92x41, 1px #2b323d, r10, label 14/600 #eef1f6, sitting right after the pill (x554). No rule under the band.
  - Build: .portal-header (AccountView.vue:127-138, CSS 445-452) is space-between: avatar 48x48 r12 with linear-gradient(135deg, --sc-primary, #2b2a6b) and ONE initial 'G' 20/700; h1 24/700 (36px line); second line 'Sarah Jenkins (sarah@gracechurch.org) . Organization Owner' 14px with the role in --sc-primary; no plan pill; 'Sign Out' = UiButton outline sm 99.9x47 r999 pushed to the far right edge; 1px bottom border, 24px padding, 32px margin.
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 -> 'Grace Community Church' font-size figma 20px vs build 24.0px, x +76; design-only: 'GC', 'PRO PLAN', 'billing@gracecommunity.org'; build-only: 'G' (avatar), 'Sarah Jenkins (sarah@gracechurch.org…
  - Fix: One left-aligned flex row, gap 16: 50px circle avatar (solid --sc-primary, two initials from the org name, 18/700 white); name 20/700 --sc-text over email 14/400 --sc-text-secondary (gap 3); plan pill (11/700, ls .7px, uppercase, --sc-elevated fill, r999, pad 5/10); then 'Sign out' (outline, r10, 92x41, pad 12/18, 14/600) wired to the real sign-out (bug-01). Remove the role tag and the primary-contact name (not drawn; the API returns neither - see account-17) and the bottom border.
  - Linked: 17tnw2b2cf2
- **account-04** · class **A** · high · page — Subscription card: summary grid and subtitle instead of the four-row key/value list; payment-method row missing
  - Figma: 506:163 titled 'Subscription' 20/600 with no subtitle, 'ACTIVE' pill 506:166 (65x23, fill #1e232c, 11/700 ls 0.7 #2bb673). Four rows (gap 13), label 14.5/400 #9aa4b2 left, value 14.5/600 #eef1f6 right-aligned: Plan -> Pro; Billing cycle -> Monthly - $19.00 / month; Next payment -> 1 September 2026; Payment method -> Visa **** 4242. 1px #2b323d divider (506:181), then one left-aligned action row, gap 12.
  - Build: AccountView.vue:172-211: heading 'Subscription & Plan' 20/700 + subtitle 'Manage your tier and billing terms'; ACTIVE UiBadge; a 3-column .plan-summary-box (--sc-elevated, r12, pad 20) with uppercase 12/600 muted labels 'CURRENT PLAN / BILLING RATE / RENEWAL DATE' and values 'Pro Tier' (22/700 --sc-primary), '$15 / month (billed annual)', '1 Sep 2026'. No 'Billing cycle' row and no 'Payment method' row. 'Cancel Subscription' is pushed to the far right (.danger-text margin-left:auto, lines 632-6…
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 design-only: Plan, Pro, Billing cycle, 'Monthly - $19.00 / month', Next payment, '1 September 2026', 'Visa **** 4242', 'Update payment'; build-only: 'Current Plan', 'Billing Rate', 'Renewal Date', …
  - Fix: Title 'Subscription' 20/600, no subtitle. Replace the summary grid with the four-row list (flex, justify-content:space-between, row gap 13px, label 14.5/400 --sc-text-secondary, value 14.5/600 --sc-text, 1px --sc-border divider before the actions). Actions in one left-aligned row, gap 12, copy per account-11; remove margin-left:auto. Row VALUES are placeholders until a billing API exists (account-18): render a row only when the API supplies its value, but keep this layout.
  - Linked: 17tnw2b2cf2
- **account-05** · class **A** · high · page — License card: gold monospace key with Reveal toggle and secondary Copy, no plan pill
  - Figma: 506:190 'License' 20/600 + 'PRO' pill 506:193 (45x23). Key row 506:195 (h44): well 506:196 809x44, fill #0e1116, 1px #2b323d, r10, pad 13/16, key text 15/500 ls 0.3 #eef1f6; 'Copy key' 506:198 99x41, fill #5b6bd6, r10, 14/600 white (primary).
  - Build: AccountView.vue:214-238: heading 'App License & Devices' + subtitle, info-blue badge '2 / 5 SEATS ACTIVE' (ndi variant). .license-key-box (--sc-inset, r12, pad 16/20, 80 tall) with a 12px label 'App License Key' and the key in monospace 16/600 --sc-gold #f2b84b ('sc_live_9f' + 12 bullets); two buttons: 'Reveal' (ghost) and 'Copy Key' (secondary, grey fill).
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 -> design-only 'License' (20/600), 'PRO', 'SCUE-8F3A-2B9C-Q7X1-4KD2', 'Copy key'; build-only 'App License & Devices', '2 / 5 Seats Active', 'App License Key', 'Reveal', 'sc_live_9f...'; 'Copy key' …
  - Fix: Heading 'License' 20/600 with a plan pill instead of the seats badge. Key well 44px tall, r10, --sc-inset fill, 1px --sc-border, no inner label, text 15/500 ls .3px --sc-text (not gold, not monospace). One primary 'Copy key' button (99x41, r10). Delete the Reveal toggle: the API holds only a masked key (account-20). Show the API's masked key as returned.
  - Linked: 17tnw2b2cf2
- **account-06** · class **A** · high · page — Device-activation meter missing from the License card
  - Figma: 506:200 (h34, gap 9): row 506:201 'Device activations' 14/400 #9aa4b2 (left) + '2 of 5 used' 14/600 #eef1f6 (right); track 506:204 = 920x8, five segments 179.2x8 r4, gap 6; used = #5b6bd6, free = #1e232c.
  - Build: No meter on /account. The only seat figure is the info-blue badge '2 / 5 SEATS ACTIVE' in the card header (AccountView.vue:220).
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 design-only: 'Device activations', '2 of 5 used'; no build box matches 506:204-209 in the boxes section.
  - Fix: Add one meter component, reused by /account/devices (devices-d1): label row + five-segment track; role="progressbar" with aria-valuemin 0, aria-valuemax = limit, aria-valuenow = used, and the literal 'N of M used' text (AUTH-LANDING-PAGES-HANDOFF 12). Segment count = max(limit, used); used = --sc-primary, free = --sc-elevated, r4, gap 6, height 8. Remove the 'Seats Active' badge.
  - Linked: 17tnw2b2cf2
- **account-07** · class **A** · high · page — Device list is a six-column table; Figma draws two-line rows with status dots and a 'Manage devices' button
  - Figma: 506:210: list in a well (fill #0e1116, 1px #2b323d, r12), two rows 66 tall (pad 15/18, gap 12, hairline between): 9px dot (#2bb673 recent / #9aa4b2 stale), name 15/600 #eef1f6 over meta 13/400 #9aa4b2 ('Windows 11 . active now' / 'macOS 14 . 2 days ago'), 'Deactivate' 13/500 #ef4444 right. Then 'Manage devices' 506:223 (147x41, 1px #2b323d, r10, 14/600) - the button that opens /account/devices.
  - Build: AccountView.vue:240-273: h3 'Registered Venue Devices' 16/600 over a table (.data-table, th 12/600 uppercase muted): Device Name | OS / Platform | IP Address | Last Active | App Version | Action; '(This device)' tag in --sc-preview; 'v1.2.0' badge per row; 'Deactivate' 13/400; no dots; no 'Manage devices' button anywhere.
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 build-only: 'Device Name', 'OS / Platform', 'IP Address', 'Last Active', 'App Version', 'Action', 'Sanctuary Main PC', '(This device)', 'v1.2.0'; design-only: 'Manage devices', 'Windows 11 . active…
  - Fix: Replace the table with the row list of 506:210 (dot + name + meta '{platform} . active now | N days ago' + Deactivate 13/500 --sc-live), delete the App Version badge column and the 'Registered Venue Devices' heading. Add 'Manage devices' (outline, 147x41, r10) linking to /account/devices once devices-d1 exists (AUTH-LANDING-PAGES-HANDOFF 11.5: 'can be wired unchanged'). Row data comes from the devices query in api-01.
  - Linked: 17tnw2b2cf2
- **account-08** · class **A** · high · page — Fabricated IP-address column in the device table
  - Figma: No IP anywhere. Meta line is platform + recency only (506:213, 506:219).
  - Build: AccountView.vue:30,72-73,248,261 render a hard-coded IP per device ('192.168.1.104', '192.168.1.112') in a code cell under the 'IP Address' column.
  - Evidence: AUTH-LANDING-PAGES-HANDOFF 7: 'The IP-address column that AccountView.vue currently renders is dropped: Device has no IP field, so it is fabricated, and it is needless PII on a page a church admin shares'; 10.4 repeats it. apps/devices/models.py:14-43: Device has no IP field. DOM dump: build-only '…
  - Fix: Delete the ip field from the Device interface and mock (AccountView.vue:30,72-73), the 'IP Address' th and the <td><code>{{ dev.ip }}</code></td>. Do not reintroduce it when the real devices query lands.
  - Linked: 17tnw2b2cf2
- **account-09** · class **A** · medium · page — Billing-history table: columns, order, header type and alignment differ
  - Figma: 507:124 'Billing history' 20/600, no subtitle. Table well 507:126 (920x188, fill #0e1116, 1px #2b323d, r12): header row 507:127 h41 fill #1e232c, 14/700 uppercase #9aa4b2: DATE | DESCRIPTION | AMOUNT (right) | STATUS | INVOICE (right). Rows h49 pad 14/18: date 14/500 #eef1f6, description 14/400 #9aa4b2, amount 14/600 right-aligned, PAID pill 47x21 (fill #1e232c, 10.5/700 ls 0.6 #2bb673), 'Download' 13.5/600 #5b6bd6 right-aligned.
  - Build: AccountView.vue:323-359: 'Billing History & Invoices' + subtitle 'Download PDF receipts and view payment ledger'; .data-table columns Invoice ID (monospace) | Date | Description | Amount | Status | Receipt, no well; th 12/600 uppercase ls .6 --sc-text-muted #6b7383, all left-aligned; PAID = green UiBadge on soft tint; link 'Download PDF' 13/400 --sc-primary.
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 -> DATE / DESCRIPTION / AMOUNT / STATUS font-size 14 -> 12, weight 700 -> 600, letter-spacing 0 -> 0.6, colour #9aa4b2 -> #6b7383; AMOUNT text-align right -> left; 'INVOICE' fuzzy-pairs 'Invoice ID…
  - Fix: Order Date | Description | Amount | Status | Invoice; th 14/700 --sc-text-secondary; amount and action columns right-aligned; row height 49; table inside an --sc-inset well (r12, 1px --sc-border) with a --sc-elevated header row 41px; action link 'Download' 13.5/600; drop the Invoice ID column (use the id in the link's aria-label); title 'Billing history', no subtitle.
  - Linked: 17tnw2b2cf2
- **account-10** · class **A** · high · page · a11y — Secondary labels use --sc-text-muted (3.45:1) where Figma uses the secondary grey (6.25:1)
  - Figma: Every secondary label is text/muted #9aa4b2, which AUTH-LANDING-PAGES-HANDOFF 2.2 maps to --sc-text-secondary: table headers 14/700, row labels 14.5/400, 'Device activations' 14/400, meta lines 13/400. #9aa4b2 on #1e232c = 6.25:1, on #171b22 = 6.85:1.
  - Build: Same roles painted with --sc-text-muted #6b7383: .summary-col .label (AccountView.vue:606-612), .key-info .label (655-658), .data-table th (691-700), .ent-meta (786-789). 12px text at 3.45:1 on --sc-elevated #1c1f28 and 3.79:1 on --sc-surface; AA normal text needs 4.5.
  - Evidence: $RUN/report.json contrast_survey, capture 'account' (26 rows, all status 'reported'): 'Current Plan' / 'Billing Rate' / 'Renewal Date' 3.45; 'Device Name'..'Action' 3.45; 'Invoice ID' / 'Date' / 'Description' 3.45; 'Downloaded (42 MB)', 'Last synced', 'Expires' 3.45; 'App License Key' 3.96. python3…
  - Fix: Role mapping per 2.2: Figma text/muted -> --sc-text-secondary (#a7aebe, 8.12:1 on --sc-surface). Change colour to var(--sc-text-secondary) on .summary-col .label, .key-info .label, .data-table th, .ent-meta and any other secondary text in AccountView.vue; keep --sc-text-muted for non-essential decoration only.
  - Linked: 17tnw2b2cf2
- **account-11** · class **A** · medium · page — Button and heading copy is Title Case and reworded; Figma is sentence case
  - Figma: Strings, word for word: 'Sign out', 'Subscription', 'Change plan', 'Update payment', 'Cancel subscription', 'License', 'Copy key', 'Manage devices', 'Billing history', 'Deactivate', 'Download', sidebar 'Subscription & billing'.
  - Build: 'Sign Out' (AccountView.vue:136), 'Subscription & Plan' (175), 'Change Plan' (199), 'Update Payment Method' (200), 'Cancel Subscription' (208), 'App License & Devices' (217), 'Copy Key' (235), 'Billing History & Invoices' (326), 'Download PDF' (352), tab 'Subscription' (157).
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 -> copy-case: 'Change plan' vs 'Change Plan'; 'Cancel subscription' vs 'Cancel Subscription'; 'Copy key' vs 'Copy Key'; 'Update payment' pairs fuzzy (0.80) with 'Update Payment Method'; 'Billing hi…
  - Fix: Use Figma's strings verbatim at those lines (list in the Figma column). Headings: 'Subscription', 'License', 'Billing history'. The Cancel-subscription dialog already uses sentence case ('Cancel subscription' / 'Keep my plan') and is unchanged.
  - Linked: 17tnw2b2cf2
- **account-12** · class **A** · low · shared · ui-badge — Status pills: weight and surface differ (ACTIVE, PAID)
  - Figma: 506:166 'ACTIVE' 65x23 and 507:139 'PAID' 47x21: fill #1e232c, r999, 11/700 ls 0.7 (ACTIVE) and 10.5/700 ls 0.6 (PAID), ink #2bb673.
  - Build: UiBadge variant 'preview': 11/600 ls .55px uppercase on --sc-preview-soft (#10231c) with 1px transparent border, pad 4/8, h26.5; ink --sc-preview #35c08a.
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 -> ACTIVE font-weight 700 vs 600, colour~ #2bb673 -> #35c08a (mapped layer, fine); PAID weight 700 vs 600.
  - Fix: UiBadge account pills: weight 700, fill --sc-elevated, height 23 (ACTIVE) / 21 (PAID). Colour is the mapped token and stays.
  - Linked: 17tnw2b2cew
- **account-13** · class **A** · low · page — Documented states not built: Free-tier account view, empty invoices, entitlement error/expiring/loading states
  - Figma: Not drawn (Figma shows the populated default only).
  - Build: AccountView.vue renders only the populated default plus a past-due banner (140-147), a skeleton (162-167) whose isLoading ref is never set (line 13), and the two confirm dialogs. No Free-tier variant, no 'No invoices yet' empty state, none of the Bible-card states.
  - Evidence: MARKETING-PORTAL-GAP-FILL-HANDOFF 7e (Free-tier view: plan 'Free', 'Upgrade to Pro...', 'View plans', '1 of 1 device', 'No invoices yet.'), 2d (no-entitlements, loading, error, expiring banner, expired, downloading, territory-blocked), 7f (skeleton on first load). grep AccountView.vue for 'No invoi…
  - Fix: Build the 7e Free-tier variant and the 2d card states once the account API supplies a plan and entitlements; drive isLoading from the real fetch. Until then the page should show nothing it cannot back (see the C findings).
  - Linked: 17tnw2b2cf2
- **account-14** · class **B** · medium · page — Bible Entitlements card present with no Figma frame
  - Figma: 506:124 draws three cards (Subscription, License, Billing history). No Bible card exists in any frame.
  - Build: A fourth card between License and Billing history (AccountView.vue:276-320, CSS 739-818): heading 'Bible Translation Entitlements', three entitlement rows (NIV, ESV, NLT) with book icon, ACTIVE/EXPIRING badge, 'Rights Holder', 'Downloaded (N MB) . Last synced . Expires', 'Re-download' button, then 'Bundled Public-Domain Bibles (Always Included)' - six chips.
  - Evidence: python3 scripts/vp_style_diff.py --slug account --dom $RUN/marketing/account.blink.dom.json --limit 0 build-only list, y=1179-1806 (Bible Translation Entitlements through Darby Translation / Webster Bible).
  - Source: MARKETING-PORTAL-GAP-FILL-HANDOFF 2 (GAP-01, Critical): 'New card section on 506:124 ... positioned between License & Devices and Billing History' with entitlement rows (2b), bundled list (2c) and states (2d). Placement and the existence of the card are documented; the copy deviations from the pros…
- **account-15** · class **A** · low · page — Bible card copy and structure deviate from the GAP-FILL section 2 spec
  - Figma: No frame. Spec: header 'Bible Translations' (Semi Bold 18px) + 'Manage your scripture entitlements'; row = icon, title (Semi Bold 15px), 'English . Biblica, Inc.', status badge + 'Expires: {date}', 'Downloaded . {size} . Last synced {date}', ghost 'Re-download'; separator 'Included with SelahCue' with six rows 'Installed' in muted text with a green dot and no action.
  - Build: Header 'Bible Translation Entitlements' 20/700 + 'Licensed Bibles authorized for encrypted download on your venue hardware' + extra badge '3 Entitlements Granted'; rows use 16/600 titles and 'Rights Holder: X'; bundled section titled 'Bundled Public-Domain Bibles (Always Included)' as 3-column chips with an INSTALLED badge; outline 'Re-download' pill buttons; badge variants only Active/Expiring.
  - Evidence: Source lines AccountView.vue:278-284, 291-300, 311-319 against GAP-FILL 2a-2c. DIFF build-only list: 'Rights Holder: Biblica, Inc.', 'INSTALLED' x6, 'Bundled Public-Domain Bibles (Always Included)'.
  - Fix: Match 2a-2c: title 'Bible Translations' 18/600, subtitle 'Manage your scripture entitlements', separator label 'Included with SelahCue', bundled rows as a compact list with 'Installed' (muted) + --sc-preview dot, no badge chips, no header count badge. Add the Pending / Expired / Territory Blocked badge variants (GAP-FILL 10e).
  - Linked: 17tnw2b2cf2
- **account-16** · class **C** · high · page — Licensed-translation entitlements (NIV, ESV, NLT) are shown as granted; the repo has none
  - Figma: Not drawn.
  - Build: Hard-coded `bibles` ref (AccountView.vue:97-101): NIV (Biblica, Inc., 42 MB), ESV (Crossway, 38 MB), NLT (Tyndale House, 40 MB, 'EXPIRING 28 Aug 2026'), with last-synced and expiry dates and a working-looking 'Re-download'. Header badge '3 Entitled' on the tab and '3 Entitlements Granted'.
  - Evidence: docs/product/prds/SelahCue-PRD.md CON-3: 'MVP bundles only public-domain Bible translations; licensed translations are API-only/user-supplied (later)'; FR-034 is release R4; the PRD's legal-confirmation list (SelahCue-PRD.md:447,471) gates ESV/API.Bible commercial terms behind those later features.…
  - Decision: Honest content wins: do not show licensed entitlements that do not exist. Ship the GAP-FILL 2d 'No entitlements' state (bundled list + 'Upgrade to Pro to access licensed translations' prompt) or hide the card until licensed translations ship? Owner/Uma to choose; the bundled public-domain list is repo-backed.
  - Linked: 17tnw2b0x3h
- **account-17** · class **C** · high · page — Customer identity is invented: org, contact, email, role and plan are hard-coded for every signed-in visitor
  - Figma: Sample data: avatar 'GC', 'Grace Community Church', 'billing@gracecommunity.org', pill 'PRO PLAN' (506:124, handoff 8 lists these as Assumed placeholders).
  - Build: `user` ref (AccountView.vue:42-48): 'Grace Community Church', 'Sarah Jenkins', 'sarah@gracechurch.org', 'Organization Owner', 'March 2025' - rendered as the signed-in user's own details; the Settings form edits the same local copy.
  - Evidence: accountViewer returns only surface, actorId, orgId (graphql/account_schema.py:33-37 and :148-153; src/lib/api/account.ts ACCOUNT_VIEWER). No org name, email, role or plan field is reachable by a customer session. The page performs no API call of its own (grep fetch/graphqlRequest in AccountView.vue…
  - Decision: What does the header show until the account API exposes profile fields? Options: derive nothing and render only what accountViewer gives (an empty/neutral header), or add org name / email / plan label to the API first (api-07). Not a design change - an honesty rule.
  - Linked: 17tnw2b0x3h
- **account-18** · class **C** · high · page — Subscription and payment details are invented (price, cycle, next payment, card)
  - Figma: 'Monthly - $19.00 / month', '1 September 2026', 'Visa **** 4242', plan 'Pro'; invoices '$19.00 Pro - Monthly PAID' for 1 Jun / 1 Jul / 1 Aug 2026.
  - Build: '$15 / month (billed annual)' and '1 Sep 2026' (AccountView.vue:51-60), plan 'Pro Tier', no payment-method row; two invoices 'Annual Pro Plan $180.00' dated 1 Sep 2025 / 1 Sep 2024 with ids INV-2026-008 / INV-2024-008 (the first id carries 2026 on a 2025 date); 'Cancel subscription' confirm claims 'Pro access ends on 1 Sep 2026' (line 93).
  - Evidence: No billing backend: apps/billing contains only migrations/__init__.py; the provider webhook is billing_webhook_not_implemented (platform/views.py:421-422, platform/urls.py webhooks/billing); no subscription, payment-method or invoice model or query exists. Platform PRD NG-P6 makes 'building billing…
  - Decision: Pricing numbers belong to 17tnw2b0x3h and decision D1; not argued here. Question for the owner: until billing exists, show the Subscription and Billing-history cards with real data only (plan name from the licence, nothing else) or an honest 'Billing is not available yet' state?
  - Linked: 17tnw2b0x3h
- **account-19** · class **C** · medium · page — Device list and 'N of 5' meter are invented; the sample slot count contradicts the Pro tier
  - Figma: 506:210 sample devices 'Studio PC . Windows 11 . active now', 'Booth MacBook . macOS 14 . 2 days ago'; meter '2 of 5 used' beside a PRO pill.
  - Build: `devices` ref (AccountView.vue:71-74): 'Sanctuary Main PC' (Windows 11 Pro, 192.168.1.104, Today at 10:45 AM, v1.2.0, this device) and 'Youth Room Mac Studio' (macOS Sonoma 14.5, 192.168.1.112, Yesterday at 4:15 PM); `subscription.seatsTotal: 5` (line 59); deactivate removes a row from the local array (81-89).
  - Evidence: No customer-session devices query exists (account_schema.py AccountQuery has only account_viewer, line 148-153). Platform PRD AS-P8 / FR-515: 'A Pro org holds one key with device_limit = 3, Platinum 7, Free 1' - a PRO plan with 5 slots is not a decided tier. The real limit is AppLicenseKey.device_l…
  - Decision: Sample data is acceptable in Figma, not in the product. Confirm the real limit and device list come from the API (api-01, api-04) and that no '5' is hard-coded; if a design sample is wanted for docs, show Pro as '2 of 3'.
  - Linked: 17tnw2b0x3h
- **account-20** · class **C** · high · page — License key shown and copyable: the API stores only a hash and a masked key
  - Figma: 506:196 key 'SCUE-8F3A-2B9C-Q7X1-4KD2' (15/500) with 'Copy key' 506:198; handoff prose calls it 'masked key + Copy'.
  - Build: `licenseKey` = 'sc_live_9f82k3m4n5p6q7r8s9t0' (AccountView.vue:63); 'Reveal' unmasks it and 'Copy Key' writes the full mock key to the visitor's clipboard and toasts 'License key copied to clipboard!' (66-69).
  - Evidence: apps/license_keys/services.py:81-100: real keys are 'SC-{TYPE}-xxxx-xxxx-...'; only secret_hash, key_prefix (12 chars), key_suffix (4) and masked_key ('prefix...suffix') are stored (models.py:40-43); the full key is returned once at issuance (admin_generate_license_key full_key, graphql/admin_schem…
  - Decision: 'Copy key' and 'Reveal' cannot work: the full key is show-once. Show the masked key as read-only text (and explain that activation is by signing in, DEC-005), drop Copy/Reveal, or add a different mechanism? Product/security call.
  - Linked: 17tnw2b0x3h
- **account-21** · class **D** · medium · page — Sidebar behaviour and the Overview / Settings destinations are undefined; the build invents a Settings form
  - Figma: Five sidebar rows; 'Subscription & billing' is drawn selected while all three cards are visible, so the frame does not say whether rows scroll to a card or switch views. No frame for Overview, Invoices or Settings content, no sidebar entry for Bible translations.
  - Build: Tabs filter the cards (AccountView.vue:170-391): 'Overview' shows everything, other tabs show one card; 'Settings' shows a built-from-nothing form 'Account Settings' (Organization Name, Primary Contact, Email Address, 'Save Changes', lines 361-390) that edits local mock state and toasts 'Settings saved successfully!'.
  - Evidence: The Settings card is not in the capture (it renders only on the Settings tab): source AccountView.vue:361-390. grep of docs/design finds no Settings-card spec for the account portal (MARKETING-SITE-HANDOFF 1a and GAP-FILL list none). Tab logic at AccountView.vue:10,172,214,277,323,362.
  - Decision: Uma: do sidebar rows anchor-scroll a single page (as the frame suggests) or switch views? Is a Settings view wanted at all, and which fields can actually be saved (no account-update mutation exists - account_schema.py has none)? Does Bible translations get its own sidebar row?
- **account-22** · class **B** · low · page — Dialogs, toast, past-due banner and loading skeleton exist without Figma frames
  - Figma: No frame for them on 506:124.
  - Build: Cancel-subscription ConfirmDialog with type-to-confirm 'cancel' (AccountView.vue:395-410), Deactivate dialog (412-420), Toast (423-427), past-due banner (140-147), SkeletonLoader (162-167).
  - Evidence: Source lines above; components/ConfirmDialog.vue, Toast.vue, SkeletonLoader.vue.
  - Source: MARKETING-PORTAL-GAP-FILL-HANDOFF 7a (cancel dialog, type-to-confirm), 7b (deactivate), 7c (toast), 7d (past-due banner), 7f (skeleton) and 10b-10d (components). The deactivate dialog copy is superseded by AUTH-LANDING-PAGES-HANDOFF 7.2 / 8.4 D2 - see devices-d2.
- **account-23** · class D · duplicate of **shared-chrome-12** — Figma draws the signed-out navbar on a signed-in page
- **account-24** · class A · duplicate of **shared-chrome-27** — UiButton: pill radius and taller sizes where Figma buttons are r10, 41px, 14/600
- **account-25** · class **D** · high · shared · tokens · a11y — Brand accent ink (#5b6bd6 / --sc-primary) fails AA as small text on panel and elevated surfaces
  - Figma: Accent text on Account frame: selected sidebar 'Subscription & billing' 14.5/600 and 'PRO PLAN' 11/700 on #1e232c = 3.39:1; 'Download' links 13.5/600 on #171b22 = 3.72:1; AUTH-LANDING-PAGES-HANDOFF 12 states these tokens are 'audited AA'. They are not.
  - Build: --sc-primary #6e5cf0 used as text: 'Download PDF' 13/400 on --sc-surface = 3.83:1, role tag 14/500 on --sc-base = 4.12:1, selected-state ink wherever added. Slightly better than Figma but still below 4.5.
  - Evidence: Computed WCAG ratios (python): #5b6bd6/#1e232c 3.39, #5b6bd6/#171b22 3.72, #6e5cf0/#14161d 3.83, #6e5cf0/#0b0d12 4.12; text-grade candidates #8f82ff = 5.86:1 on --sc-surface and 5.33:1 on --sc-elevated; --sc-primary-hover #7e6eff = 4.79 / 4.36 (not enough on elevated). Applies equally to the D1-D6 …
  - Decision: Uma: define a text-grade brand ink (>= 4.5:1 on --sc-surface and --sc-elevated) for small accent text, used for links, selected nav labels, pills and tags; keep #6e5cf0 for fills. Until then neither Figma nor the build passes.
- **account-26** · class A · duplicate of **shared-chrome-22** — Page container 1092/1140px wide and navbar 69px; Figma is a 1248px band at 96px gutters and a 79px nav
- **account-27** · class A · duplicate of **shared-chrome-16** — Footer on the Account frame differs from the build (copy, columns, type)
- **account-28** · class **C** · medium · page — Manage devices (D1, D3, D6): 'Last seen', recency dots and the 'THIS DEVICE' tag have no backing data
  - Figma: D1 rows show 'Last seen today at 10:42 / 2 days ago / 3 Aug 2026', a green/grey recency dot per row (753:317/326/333) and a 'THIS DEVICE' tag (753:321) on the first row.
  - Build: Not built.
  - Evidence: apps/devices/models.py:14-43: Device has display_name, platform, app_version, status, created_at/updated_at but no last_seen_at (handoff 10.4 says the same). Nothing updates a timestamp on device-token calls (authenticate_device_token, services.py:587-617, is read-only). A browser session has no wa…
  - Decision: Ship 'Last seen' and the dot only after a Device.last_seen_at (or equivalent) exists (handoff 10.4, owner: backend); until then show platform + version only. 'THIS DEVICE' needs a defined signal from the desktop app or should be dropped from the web page. Owner/Uma to confirm.
- **account-29** · class **D** · high · page · a11y — Manage devices (D1-D6): Figma draws four sidebar labels in #000000 on #171b22
  - Figma: Rows Overview (753:152), License (753:156), Invoices (753:158) and Settings (753:160) have text fill #000000 (contrast about 1.2:1 against #171b22); 'Subscription & billing' is #eef1f6. In the Account frame 506:124 all non-selected rows are #eef1f6.
  - Build: Not built (so nothing to copy by mistake - but a literal implementation would render invisible labels).
  - Evidence: figma-style/devices-d1.json texts 'Overview', 'License', 'Invoices', 'Settings' c '#000000'; same in devices-d2..d6; compare account.json (all #eef1f6). Visible in reference/devices-d1.png (those four labels are barely legible).
  - Decision: Uma: confirm this is an authoring slip from cloning 506:124 and that 506:124's #eef1f6 governs the sidebar (this audit's fix text assumes so). Please correct the six frames.
- **account-30** · class **D** · medium · page — Manage devices: states the page needs but Figma does not draw
  - Figma: D1-D6 cover populated, confirm, limit reached, empty, load error, over limit.
  - Build: Not built.
  - Evidence: Handoff 7 and 12 specify no loading, in-flight deactivate, deactivate-failure, Free-tier single-device, or non-admin view. Backend: only Administrators manage devices (apps/accounts/models.py:59 'ADMIN may manage devices/account (FR-137); MEMBER is read-only'; activate_device_with_session requires …
  - Decision: Uma: draw (1) loading skeleton for the list (GAP-FILL 7f pattern), (2) Deactivate pending (button disabled + 'Deactivating...') and failure (inline message; never a fake success), (3) read-only variant for MEMBER users with Deactivate hidden, (4) Free tier '1 of 1'. Frontend needs the viewer role (api-07).
- **account-31** · class **D** · medium · page · a11y — Manage devices (D2): white label on the red Deactivate button is 3.76:1
  - Figma: Button 754:254 fill #ef4444, label 14/600 #ffffff = 3.76:1 (AA normal text needs 4.5:1).
  - Build: Not built. The build's --sc-live #ff4d4d with white is 3.27:1; --sc-live as a fill with --sc-base ink (#0b0d12) is 5.16:1 on #ef4444.
  - Evidence: Computed ratios: #ffffff/#ef4444 3.76, #ffffff/#ff4d4d 3.27, #0b0d12/#ef4444 5.16.
  - Decision: Uma: choose an accessible destructive button (dark ink on #ef4444, or a deeper red fill with white). Do not copy white-on-#ef4444. Same decision applies to the Cancel-subscription dialog's confirm button (GAP-FILL 7a).
- **account-32** · class **D** · medium · page — Manage devices (D3, D4, D6): 'How device slots work' and 'How to activate a device' have no destination
  - Figma: Two ghost buttons (D3/D6 and D4) with no linked frame or article.
  - Build: Not built. No page in the site covers device slots or activation: grep of src/lib/content (docs.ts, support.ts) finds 'Manage devices' only for paired phones (Settings > Network & Mobile), a different feature.
  - Evidence: grep -rn 'device slots\|How to activate a device' docs src returns only AUTH-LANDING-PAGES-HANDOFF and the figma-style dumps.
  - Decision: Wren/Uma: which doc or support article do these open (new article, or an anchor in Documentation)? Without one the buttons must not ship; do not point them at the paired-phones docs, which describe a different thing.
- **account-33** · class **C** · medium · page — Manage devices (D4): 'open Settings > Account and sign in' points at a screen that does not exist yet
  - Figma: D4 body: 'Install SelahCue on the computer that runs your service, then open Settings > Account and sign in. The device appears here as soon as it activates.'
  - Build: Not built.
  - Evidence: implementation/desktop/crates/selahcue-operator/dist has settings pages general/appearance/network/outputs/scripture/security/storage/about only; grep for 'Settings > Account', 'Activate SelahCue' in implementation/desktop finds nothing. The desktop activation client is a planned story (86ajy7anx; …
  - Decision: Ship the copy now as the target state (the path will exist when 86ajy7anx lands) or hold the Devices page until then? Product to decide; if shipped early, soften to 'sign in from SelahCue Settings'.
- **account-34** · class **D** · low · page — Manage devices (D6): danger-banner glyph is '!' in the frame, '✕' in handoff 2.2
  - Figma: 755:526 glyph is '!' (#ef4444). AUTH-LANDING-PAGES-HANDOFF 2.2 table: danger banner glyph '✕'. D5 uses '✕' on the error disc, D3 uses '!' for warning.
  - Build: Not built. components/auth/AuthBanner.vue GLYPHS: danger '✕', warning '!'.
  - Evidence: figma-style/devices-d6.json text '!' c #ef4444 at (412,311); AuthBanner.vue lines 24-29.
  - Decision: Uma: which glyph is canonical for danger banners? The shared AuthBanner ships '✕' (handoff text); the frame shows '!'. The build will follow whichever you confirm.
- **account-35** · class **D** · medium · page · a11y — Manage devices (D6): '5 OF 3 ACTIVE' pill is 4.19:1 (#ef4444 on #1e232c at 11/700)
  - Figma: Pill 755:431 label #ef4444 on #1e232c = 4.19:1, below the 4.5:1 AA threshold for 11px text. The meter value '5 of 3 used' 14/600 #ef4444 on #171b22 = 4.59:1 passes.
  - Build: Not built. --sc-live #ff4d4d on --sc-elevated #1c1f28 = 5.03:1.
  - Evidence: Computed ratios: #ef4444/#1e232c 4.19; #ef4444/#171b22 4.59; #ff4d4d/#1c1f28 5.03.
  - Decision: Build the pill with the mapped --sc-live (#ff4d4d, 5.03:1), which clears AA; confirm with Uma that the lighter red is acceptable for this one pill.

### Affiliate program — `affiliates` (Figma `541:124`)

Verdict: **diverges** · area: secondary-2 · route: `/affiliates`

Only the hero, a three-card highlight strip and the FAQ exist; the build is 1,073px shorter (2351 vs 3424) because 'How it works', 'Made for people who talk to churches', the recommend checklist and the closing gradient CTA band are missing, and an interactive earnings calculator (not in Figma) stands in for the static earnings card. Every commission, window, payout and price figure is unbacked (the programme is NOT-V1), and the Apply button leads to the customer sign-in.

- **affiliates-01** · class **A** · high · page — 'How it works' three-step section is missing
  - Figma: Band 541:163, y822-1288 (466 high), fill #171b22, pad 64/96/64/96, gap 32. H2 'How it works' 38px/700 centred (y886), sub 'Up and earning in three steps - no code, no cost.' 18px/400 #9aa4b2. Three step cards 400x226 (third 202 high) at x96/520/944, gap 24, radius 18, fill #0e1116, 1px #2b323d, padding 28/26, gap 14: 46x46 radius-12 chip (#1e232c) holding '01'/'02'/'03' 18px/700 #5b6bd6; title 20px/600 ('Apply in minutes', 'Share your link', 'Earn every month'); body 15.5px/24 #9aa4b2.
  - Build: Absent. The page goes from the highlight cards straight to the earnings calculator (AffiliatesView.vue:41-97).
  - Evidence: vp_style_diff affiliates: design-only y=886 38x700 'How it works', y=944 'Up and earning in three steps', '01'/'02'/'03', 'Apply in minutes', 'Share your link', 'Earn every month' and their 15.5x400 bodies; paired 'How it works' lands on the footer link (y-shift +1376). Slice affiliates-1.png (Figm…
  - Fix: Add the section between the highlights and the audience cards with the dimensions and type listed, with an id="how-it-works" so the navbar link has a target. Step copy follows Figma; the figures in steps 1 and 3 ('reviewed within a couple of days', '20% ... pass $50') are C items (affiliates-12/13).
  - Linked: 17tnw2b2cez
- **affiliates-02** · class **A** · high · page — 'Made for people who talk to churches' audience section is missing
  - Figma: Frame 542:124, y1288-1696, pad 64/96/56/96, gap 32. H2 'Made for people who talk to churches' 34px/700 centred (y1352). Four cards 295.5 wide at x96/413.5/731/1048.5, gap 22, radius 18, fill #171b22, 1px #2b323d, padding 26/24, gap 13: 50x50 radius-14 icon tile (#5b6bd6, #2bb673, #f2b53c, #5b6bd6) with a white feather icon; title 17.5px/600; body 14.5px/22 #9aa4b2. Titles: Church tech creators, AV & gear resellers, Ministry networks, Consultants & integrators.
  - Build: Absent.
  - Evidence: vp_style_diff affiliates: design-only y=1352 34x700, four 17.5x600 titles, four 14.5x400 bodies. Slice affiliates-1.png.
  - Fix: Add the 4-card section (grid of 4, gap 22, content width 1248) with the type and tile colours listed; audience descriptions are not product claims and can follow Figma copy.
  - Linked: 17tnw2b2cez
- **affiliates-03** · class **A** · high · page — 'Why it's easy to recommend' checklist is missing
  - Figma: Frame 542:154, y1696-2123, pad 56/96/64/96, two columns with gap 56. Left column (772 wide): H2 'Why it's easy to recommend' 30px/700 (line-height 36), then four rows (gap 14) with an 18x20 green (#2bb673, 1.95px stroke) check and 16.5px/24 text in #eef1f6: 'A product churches actually keep using - it never blanks the screen' / 'Offline-first reliability that sells itself, no internet required' / 'Recurring commission for a year, not a one-time bounty' / 'Banners, links and email copy are done …
  - Build: Absent. In its place the build has the interactive calculator card (see affiliates-10).
  - Evidence: vp_style_diff affiliates: design-only y=1809.5 30x700 and the four 16.5x400 rows. Slice affiliates-1.png.
  - Fix: Add the two-column row: checklist on the left exactly as drawn; right column per the decision in affiliates-10. Checklist copy to be reconciled with the C items (affiliates-12 to 14).
  - Linked: 17tnw2b2cez
- **affiliates-04** · class **A** · high · page — Closing gradient CTA band is missing
  - Figma: Frame 542:228 (y2645-3066, pad 64/96). Band 542:227: 1248x293 at x96, radius 24, gradient #5b6bd6 to #2b2a6b, padding 48/64, gap 20. H2 'Ready to start earning?' 40px/700 white (y2757); sub 'Join the SelahCue affiliate program free and turn your recommendations into recurring income.' 18px/27 white at 90% opacity, 640 wide; two buttons: 'Apply now' 128x49 radius 12, white fill, #5b6bd6 text 15.5px/600, and 'Read the terms' 162x49 radius 12, 1px white at 50%, white text.
  - Build: Absent. The page ends with the FAQ then the footer (AffiliatesView.vue:99-107).
  - Evidence: vp_style_diff affiliates: design-only y=2757 40x700 'Ready to start earning?', y=2825 18x400, y=2920 'Apply now' and 'Read the terms'. Slice affiliates-fig-faq.png (Figma y2123-3066).
  - Fix: Add the band with the values listed, reusing --gradient-cta only if its stops equal #5b6bd6 to #2b2a6b after the 2.2 mapping; 'Apply now' target per affiliates-06; 'Read the terms' is a C item (affiliates-14).
  - Linked: 17tnw2b2cez
- **affiliates-05** · class **A** · medium · page — Hero: copy, type scale and spacing
  - Figma: Frame 541:139 (y79-628, pad 96/96/56/96, gap 22). H1 'Earn 20% recurring for every church you refer' 54px/700, line-height 60, 597 wide on two lines, #eef1f6. Sub 'Love SelahCue? Get paid to share it. Recommend the offline-first presentation app churches trust on Sunday and earn 20% of every payment for a full year - paid out every month.' 19px/30 #9aa4b2, 760 wide, three lines. Pill 'AFFILIATE PROGRAM' (see affiliates-11).
  - Build: src/views/AffiliatesView.vue:28-39 and :114-117. Pill 'SelahCue Partner Program'. H1 'Recommend SelahCue. Earn 20% Recurring Commission.' 42px/800, line-height 52.5, in a 1140 container. Sub 'Help churches upgrade their live worship presentation. Earn passive recurring income on every paid referral for 12 months.' 18px/28.8, max-width 720. .hero-section padding 80px 0 60px.
  - Evidence: vp_style_diff affiliates: design-only y=224 54x700 'Earn 20% recurring...' and y=366 19x400 'Love SelahCue?...'; build-only y=196.5 42px hero-title and y=324.5 18px hero-sub. dom hero-title fs 42px fw 800 lh 52.5px; hero-sub fs 18px lh 28.8px.
  - Fix: H1 54px/700 / 60px, max-width about 600px; sub 19px/30px, max-width 760px; padding 96px 0 56px; gap 22px; copy as Figma, minus whatever the owner removes under affiliates-12/13.
  - Linked: 17tnw2b2cez
- **affiliates-06** · class **A** · high · page — Hero CTAs: 'Apply' goes to the customer sign-in and 'Affiliate sign in' is missing
  - Figma: Two buttons side by side, gap 14: 'Apply now' (541:145, 128x49, radius 12, fill #5b6bd6, white 15.5px/600) and 'Affiliate sign in' (541:147, 160x49, radius 12, 1px #2b323d, #eef1f6 15.5px/600). MARKETING-SITE-HANDOFF section 1a: they lead to the affiliate portal Apply (539:155) and Sign in (539:124) screens. A line below reads 'Free to join · No audience minimum · Monthly payouts via PayPal, Wise or bank' (14px #9aa4b2; a C item).
  - Build: AffiliatesView.vue:34-37: 'Apply to Join Program' (UiButton gradient lg, 235x58, pill) goes to /signin, which is the CUSTOMER account sign-in card (router/index.ts, meta.bare), not an application; the second button is 'Calculate Earnings' (outline lg) scrolling to #calculator. No 'Affiliate sign in' control and no footnote line. No route exists for an affiliate Apply or affiliate Sign in screen (router has only /affiliates and /affiliates/dashboard|referrals|payouts|resources|settings|help).
  - Evidence: dom focus list affiliates: 'Apply to Join Program' (href /signin), 'Calculate Earnings' (href #calculator); vp_style_diff affiliates: design-only 'Apply now', 'Affiliate sign in', y=555 14x400 footnote; build-only 'Apply to Join Program', 'Calculate Earnings'. src/router/index.ts lines 58-66.
  - Fix: Relabel to 'Apply now' (primary) and 'Affiliate sign in' (secondary), 128x49 / 160x49, radius 12, 15.5px/600 (see affiliates-17 for the shared button geometry). Point them at the affiliate Apply (539:155) and Sign in (539:124) screens; those screens are outside this audit's 35-surface catalogue and have no route, so the coordinator should raise them as missing screens (E) or agree an interim target. Do not send applicants to the customer /signin.
  - Linked: 17tnw2b2cez
- **affiliates-07** · class **A** · medium · page — Highlight cards: three centred cards instead of four stat cards
  - Figma: Strip 541:150 (y628, pad 8/96/64/96, gap 22). Four cards 295.5x122 at x96/413.5/731/1048.5, radius 18, fill #171b22, 1px #2b323d, padding 26/24, gap 8, left-aligned: value 34px/700 in four inks (#5b6bd6, #2bb673, #f2b53c, #5b6bd6) over a one-line 14.5px/21 #9aa4b2 caption: '20%' Commission on every payment / '12 months' Paid on renewals, not just signup / '60 days' Cookie / attribution window / 'Monthly' Automatic, reliable payouts.
  - Build: AffiliatesView.vue:44-61 and :119-123. Three cards 348x226 (grid repeat(3)), radius 16, padding 32, centred: value 36px/800 always --sc-primary, then an h3 18px/700 and a 14px paragraph: '20%' Recurring Commission / '60 Days' Cookie Attribution / '$50' Low Payout Threshold. The h3s follow the page h1 with no h2 between (heading level skipped).
  - Evidence: vp_style_diff affiliates: boxes 'Frame 541:151 ... width 295.5 vs 348, height 122 vs 226, radius 18 vs 16'; paired '20%' font-size 34 vs 36, weight 700 vs 800, x +186; '60 days' colour #f2b53c vs #6e5cf0; design-only '12 months', 'Monthly' and their captions. dom highlight-card w 348 h 226 radius 1…
  - Fix: Four cards, gap 22, radius 18, padding 26px 24px, left-aligned, 295.5 wide inside a 1248 content width; value 34px/700 with the four inks (primary, success #2bb673, warn #f2b53c, primary); caption 14.5px/21px as a p (drop the h3s so the heading order stays h1 then h2s); values and captions per the C decision (affiliates-12/13).
  - Linked: 17tnw2b2cez
- **affiliates-08** · class **A** · medium · shared · faq-accordion — FAQ: boxed accordion card, five questions and larger heading in Figma
  - Figma: Band 542:197 (y2123-2645, fill #171b22, pad 56/96/64/96, gap 28). H2 'Affiliate FAQ' 34px/700 centred. Card 542:199: 880x333 at x280, radius 16, fill #0e1116, 1px #2b323d, rows divided by 1px #2b323d, row padding 18/22, gap 12; question 16px/600 #eef1f6; answer 15px/23 #9aa4b2 (790 wide); 9-10.5px icon at the right, 1.5px stroke, primary when open (first row open, drawn as a rotated plus), muted otherwise. Five questions: How much can I earn? / When and how do I get paid? / What counts as a ref…
  - Build: src/components/FaqAccordion.vue (shared with Home, Pricing and AffiliateHelp) in .faq-wrapper max-width 800 (AffiliatesView.vue:144). h2 'Affiliate Program FAQ' 28px/700. Bare rows with only a bottom hairline, no card or fill, no band behind it; row padding 24px 0, question 17px/600, answer 15px/24, 24px icon (2px stroke). Four questions: What is the commission rate? / How long does the referral cookie last? / When are affiliate payouts made? / Who can join the affiliate program?
  - Evidence: vp_style_diff affiliates: design-only y=2179 34x700 'Affiliate FAQ', y=2266 16x600 'How much can I earn?', four more 16x600 questions, y=2297 15x400; build-only y=1372.6 28px 'Affiliate Program FAQ', four 17px questions. dom faq-item w 800, faq-question pad 24px 0, svg 24x24. Slices affiliates-1.pn…
  - Fix: Style change in FaqAccordion.vue behind a prop or class, because the Home and Pricing FAQ frames must be checked first (the same boxed look may or may not be drawn there): card 880 wide, radius 16, --sc-base fill with 1px --sc-border, row padding 18px 22px, question 16px/600, answer 15px/23px, 10px icon with 1.5px stroke; put the section on the --sc-surface band; heading 34px/700 'Affiliate FAQ'; five questions per Figma (answers are C items, affiliates-13).
  - Linked: 17tnw2b2cew
- **affiliates-09** · class **A** · low · page · a11y — FAQ panels: collapsed answers stay in the accessibility tree; no aria-controls; icon not hidden
  - Figma: Interaction not drawn beyond first row open / others closed.
  - Build: FaqAccordion.vue: each question is a native button with aria-expanded (good, keyboard Enter/Space work), but the answer wrapper only collapses by grid-template-rows 0fr, so collapsed answers are still readable by assistive tech and find-in-page; no aria-controls/id pairing or region; the plus SVG has no aria-hidden. The same component is used on Home, Pricing and AffiliateHelp.
  - Evidence: dom items: collapsed answers ('Our referral tracking uses a 60-day last-click attribution window.', 'Payouts are processed on the 1st...', 'Worship leaders, tech consultants...') exist as p nodes h 48-72 w 800 although their rows are closed; focus list shows the four question buttons in order, no e…
  - Fix: Add id/aria-controls on each button/panel pair, set the closed panel hidden-from-AT (inert or visibility:hidden after the transition, or the hidden attribute with a height transition), and aria-hidden="true" on the icon svg.
  - Linked: 17tnw2b2cez
- **affiliates-10** · class **D** · high · page · a11y — Interactive earnings calculator is build-only; Figma draws a static 'Earnings example'
  - Figma: Card 542:178 (x924 y1752, 420x307, radius 20, fill #171b22, 1px #2b323d, padding 28, gap 16) beside the checklist: 'Earnings example' 17px/600 with an 'ILLUSTRATIVE' pill (10px/700, tracking 0.6, #9aa4b2 on #1e232c, radius 999); rows 'You refer / 25 Pro churches', 'Commission / 20% of $19 / mo', 'Attribution / 12 months each' (14.5px, values 600 #eef1f6); 1px divider; '$95' 34px/700 #2bb673 with '/ month recurring' 15px; note 'Grows every month as more of your referrals stay subscribed.' 13px/1…
  - Build: AffiliatesView.vue:64-97 and :125-140: a 700-wide card 'Estimate Your Earnings' with a range slider (1-100 'Referred Active Churches', default 10) and two result boxes ('$38/mo', '$456/yr') computed as churches x 3.8 (line 11, the hard-coded '20% of $19/mo'). No 'illustrative' label. Three defects inside it: the range input has no accessible name (focus list entry with name '', x421 y1062); 12px labels 'MONTHLY RECURRING INCOME' / 'ESTIMATED ANNUAL PAYOUT' in #6b7383 are 3.45:1 (on #1c1f28) and…
  - Evidence: vp_style_diff affiliates: build-only 'Estimate Your Earnings', 'Slide to see...', '10 churches', 'Referred Active Churches:', 'Monthly Recurring Income', 'Estimated Annual Payout', '$38/mo', '$456/yr'; $RUN/report.json contrast_survey affiliates: 'Monthly Recurring Income' 3.45, 'Estimated Annual P…
  - Decision: Uma / owner: keep an interactive calculator (needs a frame, an 'illustrative' label and AA-safe inks) or replace it with Figma's static, labelled 'Earnings example'? Either way the numbers are C (affiliates-13). If the calculator stays: give the slider an accessible name (aria-label or a label element), raise the three failing inks to 4.5:1, and label the result 'estimate'.
  - Linked: 17tnw2b0x3h
- **affiliates-11** · class A · duplicate of **careers-02** — Eyebrow pill: label, style and spacing
- **affiliates-12** · class **C** · high · page — The 20% commission rate is not backed anywhere in the repo
  - Figma: '20%' stat card; H1 'Earn 20% recurring...'; hero sub 'earn 20% of every payment for a full year'; step 3 'Get 20% of every payment for a year'; earnings example '20% of $19 / mo'; FAQ answer 'There's no cap'.
  - Build: H1 'Earn 20% Recurring Commission', card '20% Recurring Commission', FAQ 'You earn a 20% recurring commission for 12 months on every paid subscription', and the calculator constant 3.8 = 20% of $19 (AffiliatesView.vue:7-16, :31, :46-49, :19).
  - Evidence: grep -ri 'affiliate|commission|referral|payout' over implementation/api and implementation/desktop finds no code or schema; docs/product/prds/SelahCue-Platform-PRD.md line 51 (NG-P1: affiliate programme NOT-V1, ClickUp 86ak11w7g) and docs/decisions/DECISION-LOG.md line 287 (DEC-008: 'affiliate term…
  - Decision: Owner: the programme is marked NOT-V1 and its terms are undecided, so no rate may be advertised. Decide whether /affiliates ships at all in V1 (the footer links it on every page) and, if it does, what the page says without a rate (e.g. an interest/waitlist page). Layout and styling stay as Figma per the owner rule.
  - Linked: 17tnw2b0x3h
- **affiliates-13** · class **C** · high · page — Programme terms, payout methods and promises are invented
  - Figma: '12 months' (renewals), '60 days' cookie/attribution, 'Monthly' payouts, 'Free to join · No audience minimum · Monthly payouts via PayPal, Wise or bank', 'pass $50', 'Most applications are reviewed within a couple of days', 'ready-made banners', 'Banners, links and email copy are done for you', FAQ 'no cap'.
  - Build: '60 Days' card plus FAQ 'Our referral tracking uses a 60-day last-click attribution window', '$50' threshold card, 'Monthly payouts direct to your PayPal or bank account with clear real-time reporting', FAQ 'Payouts are processed on the 1st of every month via PayPal or Direct Bank Transfer once you reach the $50 minimum threshold', and 'for 12 months' (AffiliatesView.vue:19-22, :51-58).
  - Evidence: No attribution window, threshold, payout rail or review-time exists in docs/ or implementation/ (grep above); the platform's payment provider in the legal draft is Paystack, not PayPal or Wise; affiliate resources and payouts views are mock data (README 'Known gaps'). docs/product/prds/SelahCue-Pla…
  - Decision: Owner: none of these figures or promises can ship until the affiliate terms exist (DEC-008). Remove or replace with honest placeholders when 17tnw2b0x3h lands; affiliates-07, 03 and 08 keep Figma's layout around whatever copy remains.
  - Linked: 17tnw2b0x3h
- **affiliates-14** · class **C** · medium · page — Earnings example figures, the $19 Pro price and 'Read the terms'
  - Figma: '25 Pro churches', '20% of $19 / mo', '12 months each', '$95 / month recurring' (25 x $3.80); closing band button 'Read the terms'.
  - Build: Calculator output '$38/mo' and '$456/yr' at the default 10 churches, from the hard-coded $19 (AffiliatesView.vue:9-16). No 'Read the terms' control; no affiliate terms document exists.
  - Evidence: No price is decided: DEC-008 fixes the tier structure as Free / Pro / Platinum and lists 'Pricing/price points' and 'affiliate terms' as still open (docs/decisions/DECISION-LOG.md line 287). Pricing numbers belong to 17tnw2b0x3h and pricing decision D1, not argued here.
  - Decision: Owner: the earnings maths cannot be shown without a price and a rate. Show no figure, or a clearly labelled placeholder; 'Read the terms' needs a target document or must be dropped.
  - Linked: 17tnw2b0x3h
- **affiliates-15** · class **C** · low · page — Checklist claims: one backed, one unbacked, two depend on the programme
  - Figma: 'A product churches actually keep using - it never blanks the screen'; 'Offline-first reliability that sells itself, no internet required'; 'Recurring commission for a year, not a one-time bounty'; 'Banners, links and email copy are done for you'.
  - Build: Not built (affiliates-03).
  - Evidence: 'never blanks the screen' is backed by NFR-024 (selahcue-engine tests 'a fault must never blank the live output'); 'no internet required' is backed by the offline-first, desktop-authoritative architecture; 'keep using' is a retention claim with no data in the repo (pre-release, no downloads); the l…
  - Decision: Owner: keep the two backed lines, drop 'actually keep using' and the two programme lines until they are true.
  - Linked: 17tnw2b0x3h
- **affiliates-16** · class A · duplicate of **shared-chrome-07** — Navbar 'How it works' is an in-page anchor with no target here; footer 'How it works' is a dead route
- **affiliates-17** · class A · duplicate of **shared-chrome-27** — CTA button geometry: pill gradient/outline lg vs 12px-radius 49px buttons

### V1 Verifying — `verify-v1` (Figma `743:125`)

Verdict: **diverges** · area: auth · route: `/verify?token=SC-TESTTOKEN-verify`

Copy, glyph, the 6px progress track (about one third full, static under reduced motion) and the footer row match. The build left-aligns the disc, title and body where Figma centres them, and the title wraps onto two lines (card 33px taller) because the card content is 2px narrower (signin-11).

- **verify-v1-01** · class **A** · medium · page — Disc, title and body are left-aligned; Figma centres them (V1 and V2 only)
  - Figma: Disc centred (743:130 x=692 in a card spanning 505-935), title and body text-align CENTER (x=541 w=358). Only V1 and V2 are centred: V3-V6 and every /reset frame left-align the disc at x=541, as does Sign in.
  - Build: auth.css:64 .au-card { text-align: left } with no centred modifier, so the disc sits at x=542 and title/body are left (dom: disc x=542, text-align left). Same on verify-v2. The V1 title also wraps (see verify-v1-03).
  - Evidence: python3 scripts/vp_style_diff.py --slug verify-v1 --dom $RUN/marketing/verify-v1.blink.dom.json --limit 0 -> 'text-align figma center vs build left' on the title and body; '↻ x -148.6 px (figma 709.5, build 560.9)'. Slice verify-v1-0.png.
  - Fix: Add a centred modifier (e.g. AuthShell prop align='center' adding .au-card-center) used only by VerifyView states 'verifying' and 'verified': .au-card-center .au-disc { align-self: center }, .au-card-center .au-title, .au-card-center .au-body { text-align: center }. Leave banners, buttons and the footer unchanged (the V2 banner copy stays left at x=583).
  - Linked: 17tnw2b2cf1
- **verify-v1-02** · class **A** · low · page — V1 live region contains no text
  - Figma: AUTH-LANDING-PAGES-HANDOFF.md §4.1 and §12: V1 is announced with role=status aria-live=polite.
  - Build: VerifyView.vue:206-208 puts role=status on a div that wraps only the progress track, with an aria-label and no text node. Assistive tech announces live-region text changes, not an aria-label on insertion, and the h1 is outside the region, so the announcement may be silent.
  - Evidence: VerifyView.vue:206-208; dom: the role=status element has no text.
  - Fix: Put text inside the live region: the body sentence ('This only takes a moment. Keep this tab open.') or an sr-only 'Verifying your email address…'.
  - Linked: 17tnw2b2cf1
- **verify-v1-03** · class **D** · low · page — V1 title wraps to two lines in the build because the web font measures wider than Figma's Inter
  - Figma: V1 (743:125) draws 'Verifying your email address…' on one line in a 358px column, so the card is 239px tall.
  - Build: The title wraps to two lines and the card is 272px (+33px): its natural width in the browser is 360px, wider than both the build's column (356px) and Figma's (358px). Making the column 358px (signin-11) alone will not stop the wrap.
  - Evidence: Measured by QA in Chromium (Quinn Q-2): natural title width 360px; the V1 style diff shows the title as two lines; the Inter cause is inferred, not measured
  - Decision: Uma: allow the V1 title to wrap (and redraw the frame at two lines), or give the title a slightly smaller size or tighter tracking so it fits in 358px. The cause is the web font's metrics against Figma's Inter, not a layout bug, so no engineer fix can make both true.
  - Linked: verify-v1-01; signin-11

### V2 Verified — `verify-v2` (Figma `743:139`)

Verdict: **diverges** · area: auth · route: `/verify?token=SC-TESTTOKEN-verify`

Content, success disc and banner colours, the primary action and the 'Not your account? Contact support' footer match. Differences are the left alignment (as V1), the banner typography and spacing that every banner in the build shares, and a focus ring the heading shows on arrival.

- **verify-v2-01** · class **A** · medium · page — Banner typography, glyph size and spacing (all banners)
  - Figma: Banner 358 wide, padding 14/16, radius 12, 12px between glyph and copy; glyph Inter Bold 15 in the status ink; title Semi Bold 13 text/primary; body Regular 12.5/17 text/muted; 3px title-to-body gap; a three-line body gives 98px (745:124).
  - Build: gap 10px; glyph 13px/700 on a 20px line (it reads as a dot); title 13.5/600; body 13px/19px; title margin-bottom 2px (auth.css:121-159). Same three lines give 107.3px (+9.3). Same on verify-v3, verify-v5, reset-r1, reset-r2, reset-r3, reset-r4, reset-r6, reset-r7: V5 88.3 vs 81, R1 126.3 vs 115, R7 107.3 vs 98.
  - Evidence: python3 scripts/vp_style_diff.py --slug verify-v2 --dom $RUN/marketing/verify-v2.blink.dom.json --limit 0 -> '✓ font-size figma 15px vs build 13.0px'; 'line-height figma 17px vs build 19.0px'; 'banner 745:124 height figma 98 vs build 107.3'; banner text x -3.2 to -7.6 px.
  - Fix: auth.css: .au-banner { gap: 12px }; .au-banner-glyph { font-size: 15px; line-height: 18px }; .au-banner-title { font-size: 13px; line-height: 16px; margin: 0 0 3px }; .au-banner-body { font-size: 12.5px; line-height: 17px }.
  - Linked: 17tnw2b2cf1
- **verify-v2-02** · class **D** · low · page — Typographic apostrophes in Figma copy, ASCII in the build and the copy deck
  - Figma: Figma auth copy uses U+2019: 'You don’t need an account to run SelahCue', 'didn’t', 'we’ll', 'Don’t close this tab.' (Sign in's own copy in Figma uses straight apostrophes).
  - Build: The build renders ASCII ' everywhere (VerifyView.vue, ResetView.vue, lib/auth/messages.ts), as does the handoff copy deck (§8). The pinned test strings (tests/authCopy.test.ts, scripts/auth_pages_headless.py) also use ASCII.
  - Evidence: Style diff 'copy-case' lines on verify-v2, verify-v3, verify-v5, reset-r1..r4, r6, r7.
  - Decision: Uma: which is canonical? Typographic apostrophes are the better typography; adopting them means changing the copy constants and the pinned test strings together.
- **verify-v2-03** · class **B** · low · page — Heading takes programmatic focus and shows a 2px brand outline on arrival
  - Figma: No focus indicator on the title.
  - Build: On arrival at a terminal state focusHeading() moves focus to the h1 (tabindex=-1) and .au-title:focus-visible paints a 2px --sc-primary outline, offset 4px (VerifyView.vue:111-114, 378-381). It shows in the verify-v2 and verify-v3 captures; the h1 is not a tab stop.
  - Evidence: Slice verify-v2-0.png (outline around 'Email address verified'); dom focus list has no h1.
  - Source: AUTH-LANDING-PAGES-HANDOFF.md §12 (focus order brand then card title; 2px accent/brand ring with offset); implementation/marketing/scripts/auth_pages_headless.py:1289 pins 'V2 focus moved to the heading'; VerifyView.vue:102-110 explains why.

### V3 Link no longer valid — `verify-v3` (Figma `746:124`)

Verdict: **diverges** · area: auth · route: `/verify?token=SC-TESTTOKEN-verify`

This is the state that ships and its structure, copy, disc, resend form and banner all match; the card reads 46px taller than Figma. Every difference is one of the card-level ones listed under signin, verify-v2 and reset-r2.

- **verify-v3-01** · class **A** · medium · page — Card is 46px taller than Figma (acceptance numbers for this state)
  - Figma: Card 746:128 is 430x554: disc 56, two-line title 58, three-line body 66, one field 67, button 47, banner 98, all 18px apart.
  - Build: Card is 430x600.3: field block +29 (label line box, reserved meta row, margin-bottom), button +4, banner +9.3, title lines +2 (about +44 of the +46). Disc, title wrap, body lines and banner lines all match.
  - Evidence: python3 scripts/vp_style_diff.py --slug verify-v3 --dom $RUN/marketing/verify-v3.blink.dom.json --limit 0 -> 'card 746:128 height figma 554 vs build 600.3'; 'input … build[542,456,356,45]'; 'btn-primary … build 51'; 'banner 746:140 height figma 98 vs build 107.3'.
  - Fix: No separate change: closes when signin-06, signin-07, signin-09, signin-10, signin-11 and verify-v2-01 land. Acceptance: at 1440x900 the card is 554px tall, the input top sits 23px below the label top, the button is 47px, the banner 98px.
  - Linked: 17tnw2b2cf1
- **verify-v3-02** · class **D** · low · page — Transport-failure state and resend errors have no frame
  - Figma: /verify has no server-error frame (/reset has R7). The resend form has no pending or error frame.
  - Build: VerifyView.vue:332-348 renders a warning disc '!', 'We couldn't verify your email just now', 'We couldn't reach SelahCue. Check your connection and try again — this page is the only thing affected.', primary 'Try again' and a success banner 'Your link still works', extrapolated from R7 (comment at :326-331). Resend failures show a role=alert note (RESEND_FAILED / RESEND_RATE_LIMITED, lib/auth/messages.ts).
  - Evidence: VerifyView.vue:326-348; scripts/auth_pages_headless.py scenario 'verify-unreachable'.
  - Decision: Uma: draw the V-series transport-failure state and the resend pending/error states, or confirm the R7-derived layout and copy.

### V4 Link expired (24h) — `verify-v4` (Figma `746:148`)

Verdict: **not-rendered-by-design** · area: auth · route: `/verify?token=SC-TESTTOKEN-verify`

V4 ('This verification link has expired', 24-hour TTL) is deliberately not rendered: the API cannot tell an expired token from an invalid one, so the build ships the merged V3 for every token failure. The verify-v4 capture is the V3 card, the shipped substitute.

- **verify-v4-01** · class **B** · low · page — V4 'link expired' is designed but not rendered; V3 ships for every failure
  - Figma: Warn disc '!' #f2b53c, title 'This verification link has expired', body 'Verification links expire 24 hours after they are sent…', Email field + 'Send a new verification link', warn banner 'Why links expire', footer 'Wrong address? Back to Sign in' (746:148).
  - Build: Not rendered. VerifyView.vue state 'invalid' (V3) covers every token failure with copy that names expiry, reuse and a bad copy without asserting which (VerifyView.vue:8-23, 230-266). The verify-v4 capture is scenario 'verify-invalid' (dom h1 = V3 title).
  - Evidence: surfaces.json: status not-rendered with source_probe must_not_contain 'This verification link has expired'. Style diff: 7 figma-only texts ('!', title, body, banner title/body/glyph, 'Wrong address?') vs the V3 equivalents. The 24-hour TTL itself is real (implementation/api/selahcue_api/settings.py…
  - Source: AUTH-LANDING-PAGES-HANDOFF.md §4.4 ('Only render this when the backend can prove expiry') and §10.2 (verify_email collapses unknown/consumed/expired into one VALIDATION_FAILED; owner decision product + security). ClickUp 86ak120fz is named in VerifyView.vue:22 as the owner of any change.

### V5 New link sent — `verify-v5` (Figma `746:172`)

Verdict: **diverges** · area: auth · route: `/verify?token=SC-TESTTOKEN-verify`

Reachable only through the resend form (the capture drives it). Copy, conditional no-enumeration wording, secondary 'Back to Sign in', banner and 'Need a hand? Contact support' footer match. The spam-folder note fails AA, and the envelope glyph renders half the drawn size.

- **verify-v5-01** · class **A** · high · page · a11y — Helper note ('Didn't arrive?') fails AA
  - Figma: Note 12.5/400, 17px line, text/muted #9aa4b2 on #171b22 = 6.85:1 (746:172 text at y=523.5).
  - Build: au-note is 13px/20px --sc-text-muted #6b7383 on --sc-surface #14161d = 3.79:1, below 4.5:1 (auth.css:106-111). The same class carries R3's 'Don't close this tab.' (reset-r3) and every resend-error note.
  - Evidence: $RUN/report.json contrast_survey verify-v5 "Didn't arrive? Check your spam folder…" 3.79; reset-r3 "Don't close this tab." 3.79. Style diff 'colour figma #9aa4b2 vs build #6b7383' and 'line-height figma 17px vs build 20.0px'.
  - Fix: auth.css .au-note: color var(--sc-text-secondary) (8.12:1 on --sc-surface), font-size 12.5px, line-height 17px.
  - Linked: 17tnw2b2cf1
- **verify-v5-02** · class **A** · low · page — Envelope glyph renders at about 13px, drawn at 22px
  - Figma: '✉︎' (U+2709 + U+FE0E text variation selector) Inter Bold 22 in accent/brand, 22px wide (746:172 text x=558 w=22).
  - Build: StatusDisc glyph '✉' without the selector (VerifyView.vue:303, ResetView.vue:415, SignInView.vue:432); it falls back to a symbol font and measures 13.3px wide at 22px, visibly smaller than the ✓ and ✕ discs (19.8px and 16.8px).
  - Evidence: dom verify-v5 au-disc text '✉' tw 13.3; slice verify-v5-0.png (build envelope is a small purple mark, Figma's is a full-size envelope).
  - Fix: Use '✉︎' (U+2709 U+FE0E) in all three views and check the glyph width is about 22px; if the fallback font still renders it small, pin a font-family that has the glyph.
  - Linked: 17tnw2b2cf1

### V6 No verification link — `verify-v6` (Figma `747:124`)

Verdict: **diverges** · area: auth · route: `/verify`

Copy, the muted (not red) '!' disc, the email form and the 'Already verified? Back to Sign in' footer all match. Only the card-level differences remain; the card reads 37px taller than Figma.

- **verify-v6-01** · class **A** · medium · page — Card is 37px taller than Figma (acceptance numbers for this state)
  - Figma: Card 747:128 is 430x438: disc 56, two-line title 58, three-line body 66, one field 67, button 47, all 18px apart; no banner.
  - Build: Card is 430x475: field block +29, button +4, title lines +2. Title and body wrap exactly as Figma. The neutral disc ink is --sc-text-secondary #a7aebe, the mapped text/muted.
  - Evidence: python3 scripts/vp_style_diff.py --slug verify-v6 --dom $RUN/marketing/verify-v6.blink.dom.json --limit 0 -> 'card 747:128 height figma 438 vs build 475'; 'input … build[542,519,356,45]'; 'btn-primary … build 51'.
  - Fix: No separate change: closes when signin-06, signin-07, signin-09, signin-10 and signin-11 land. Acceptance: card 438px tall at 1440x900.
  - Linked: 17tnw2b2cf1

### R1 Choose a new password — `reset-r1` (Figma `747:143`)

Verdict: **diverges** · area: auth · route: `/reset?token=SC-TESTTOKEN-reset`

Title, body, both field labels, the hint, 'Update password', the 'This signs you out everywhere' banner and the footer match in copy. The build shows an eye icon where Figma has the text 'Show', does not focus the New password field on arrival, and its hint fails AA at 3.79:1.

- **reset-r1-01** · class **A** · medium · shared · form-field — Password reveal control is an icon, Figma draws the text 'Show' (R1, R2, R3, R7)
  - Figma: Trailing text 'Show' 12.5/500 text/muted inside both inputs (x=851, y=362.5 and 471.5). AUTH-LANDING-PAGES-HANDOFF.md §5.1 'both with a Show affordance', §8.2 trailing 'Show', §12 'Show toggles need aria-pressed and a label that is not just an icon'.
  - Build: A 20px eye / eye-off SVG in a 28x28 button (FormField.vue:81-97, 187-210). aria-label 'Show password'/'Hide password' and aria-pressed are present, but the visible control is only an icon and the desktop hit area is 28px (handoff §12: targets of at least 44px).
  - Evidence: python3 scripts/vp_style_diff.py --slug reset-r1 --dom $RUN/marketing/reset-r1.blink.dom.json --limit 0 -> figma-only 'Show' (y=362.5) and 'Show' (y=471.5); dom password-toggle w=28 h=28.
  - Fix: On /reset render the visible text 'Show' / 'Hide' (12.5px/500 --sc-text-secondary) in the toggle, keep aria-pressed and the aria-label, and give it a 44px-tall hit area. Keep the eye icon on /signin (signin-13).
  - Linked: 17tnw2b2cew
- **reset-r1-02** · class **A** · low · page — New password is not focused on arrival
  - Figma: R1 draws the New password input focused: 1.5px accent/brand stroke (747:153 s #5b6bd6 sw 1.5); handoff §5.1 '(focused …)'.
  - Build: No field is focused on arrival: ResetView.vue onMounted only sets the state, and the capture shows no focus stroke.
  - Evidence: Slice reset-r1-0.png (no brand stroke on the build's first field); ResetView.vue:217-225.
  - Fix: When a token is present, focus the New password input after mount (nextTick). The h1 stays first in the DOM so screen readers still read the title.
  - Linked: 17tnw2b2cf1
- **reset-r1-03** · class **A** · high · page · a11y — Field hint fails AA
  - Figma: Hint 'At least 10 characters.' 12.5/400, 17px line, text/muted #9aa4b2 on #171b22 = 6.85:1 (747:143 text y=399).
  - Build: FormField .field-hint is 13px/19.5px --sc-text-muted #6b7383 on --sc-surface = 3.79:1 (FormField.vue:247-250). Same on reset-r3 and reset-r7.
  - Evidence: $RUN/report.json contrast_survey reset-r1, reset-r3, reset-r7 'At least 10 characters.' 3.79. Style diff 'colour figma #9aa4b2 vs build #6b7383', 'line-height figma 17px vs build 19.5px'.
  - Fix: Auth variant: .field-hint { color: var(--sc-text-secondary); font-size: 12.5px; line-height: 17px }.
  - Linked: 17tnw2b2cf1

### R2 Validation errors — `reset-r2` (Figma `747:173`)

Verdict: **diverges** · area: auth · route: `/reset?token=SC-TESTTOKEN-reset`

Both messages match word for word and both fields turn red, but the message format differs, the submit button is not dimmed, and the build keeps the 'signs you out everywhere' banner that Figma drops, making the card 162px taller.

- **reset-r2-01** · class **A** · medium · shared · form-field — Field error format: icon instead of the text '✕ '
  - Figma: Messages '✕ Password must be at least 10 characters.' and '✕ Both passwords must match.' 12.5/500, 17px line, accent/live, flush with the field edge (x=541). AUTH §12: 'Field errors carry ✕ in the message text itself'.
  - Build: A 14px circle-exclamation SVG plus the message, 13/500 on a 19.5px line, text starting at x=560 (FormField.vue:100-106, 232-245); there is no ✕ character.
  - Evidence: python3 scripts/vp_style_diff.py --slug reset-r2 --dom $RUN/marketing/reset-r2.blink.dom.json --limit 0 -> 'copy figma ✕ Password … vs build Password …', 'x +19.0 px', 'line-height figma 17px vs build 19.5px'.
  - Fix: Auth variant: drop the SVG and prefix '✕ ' to the message (an aria-hidden glyph span is fine, the message keeps role=alert); 12.5px/500, 17px line.
  - Linked: 17tnw2b2cew
- **reset-r2-02** · class **A** · medium · page — Submit button is not dimmed while errors show
  - Figma: 'Update password' at 45% opacity while both fields are in error (747:194; handoff §5.2).
  - Build: Full-strength button (hover fill in the capture), enabled (ResetView.vue:292-301).
  - Evidence: Style diff boxes: 'btn-primary 747:194 fill figma #5b6bd6 vs build #7e6eff'; slice reset-r2-0.png.
  - Fix: While field errors are present set the button to 45% opacity (aria-disabled, still focusable; submitting re-validates) and clear it when either field changes.
  - Linked: 17tnw2b2cf1
- **reset-r2-03** · class **A** · medium · page — Info banner kept on R2 and R3; Figma drops it
  - Figma: R2 and R3 end with the button and the footer row; the 'This signs you out everywhere' banner appears on R1 only (747:173, 749:124).
  - Build: ResetView.vue:314 shows the banner in every form state except R7/PASSWORD_INVALID (v-if="!showsErrorBanner"). R2 card is 609.8px tall vs 448; R3 is 647.8 vs 435.
  - Evidence: Style diff build-only on reset-r2 and reset-r3: '◆', 'This signs you out everywhere', 'Updating your password ends every active…'. Boxes: 'card 747:177 height figma 448 vs build 609.8'.
  - Fix: Hide the banner while field errors show (R2) and while submitting (R3). If Uma says the frames abbreviated, close this item.
  - Linked: 17tnw2b2cf1
- **reset-r2-04** · class **A** · high · shared · ui-button · a11y — Primary button hover fill fails AA with the white label
  - Figma: No hover frame. Rest state: white label on accent/brand #5b6bd6 = 4.65:1.
  - Build: UiButton .variant-primary:hover uses --sc-primary-hover #7e6eff under a white 15.5/600 label = 3.78:1 (UiButton.vue:104-106). The scripted click leaves the pointer on the button, so the R2, R3 and R4 captures show the hover fill (dom button bg rgb(126,110,255)). Rest fill #6e5cf0 is 4.72:1 and passes.
  - Evidence: $RUN/report.json contrast_survey: reset-r2 'Update password', reset-r3 'Updating password…', reset-r4 'Send a new reset link' value 3.78 (required 4.5).
  - Fix: Make the hover fill darker than --sc-primary instead of lighter, e.g. #5f4de6 (white 5.69:1), for every primary UiButton, so the label holds 4.5:1 on hover. Uma may choose the exact hover colour under shared-chrome-31; whichever is chosen must measure at least 4.5:1 with the white label. This is a shipped accessibility failure, so it is class A here and the open choice of colour is the class D finding.
  - Linked: shared-chrome-31, 17tnw2b2cev

### R3 Updating password — `reset-r3` (Figma `749:124`)

Verdict: **diverges** · area: auth · route: `/reset?token=SC-TESTTOKEN-reset`

aria-busy on the form, the disabled fields and button, and the polite 'Don't close this tab.' status are all in place. But the button hides its 'Updating password…' label behind a generic spinner, the fields are dimmed twice, and the hint and banner Figma omits are still shown.

- **reset-r3-01** · class **A** · high · page — Submitting button hides its 'Updating password…' label
  - Figma: Disabled button at 50% opacity showing '↻' (14/700 white) and 'Updating password…' (15.5/600 white) centred (749:143; texts at x=629.5 and x=651.5). Copy deck §8.2: bold 'Updating password…'.
  - Build: UiButton loading=true sets .content.hidden { opacity: 0 } and shows a 20px generic spinner only (UiButton.vue:48-51, 149-161); the button stays at full strength. The designed '↻' class .au-spinner (auth.css:324-345, static under reduced motion) is defined but used nowhere. The same happens on Sign in ('Signing in…', SignInView.vue:357) and the resend buttons.
  - Evidence: dom: button class 'is-loading', child span.content.hidden opacity 0 text 'Updating password…'; style diff figma-only '↻' and 'Updating password… x -11.8'; slice reset-r3-0.png (build shows a lone spinner).
  - Fix: For auth buttons keep the label visible while loading: .au-btn.is-loading .content { opacity: 1 }, hide .spinner, prefix the label with <span class="au-spinner" aria-hidden="true">↻</span> (static under prefers-reduced-motion already), and set the button to 50% opacity. Apply to Sign in and the resend buttons too.
  - Linked: 17tnw2b2cf1
- **reset-r3-02** · class **A** · medium · page — Fields are dimmed twice and the toggles stay live
  - Figma: Only the two input frames are at 50% (749:134, 749:140); labels stay full strength; the hint is absent.
  - Build: ResetView.vue:467-469 sets .form-field { opacity: .5 } and FormField.vue:182-185 sets .is-disabled .field-input { opacity: .5 }, so inputs sit at 25% and labels at 50%; the hint 'At least 10 characters.' is still drawn; the two 'Show password' buttons remain enabled tab stops (dom focus list: button, button, Back to Sign in).
  - Evidence: dom reset-r3: input opacity '0.5' inside a .form-field at 0.5; style diff build-only 'At least 10 characters.'; slice reset-r3-0.png (labels and inputs visibly faint).
  - Fix: Dim only the input (and its toggle) to 50%, once; leave labels at full strength; hide the hint while submitting; set disabled on the toggle buttons.
  - Linked: 17tnw2b2cf1

### R4 Link no longer valid — `reset-r4` (Figma `749:150`)

Verdict: **diverges** · area: auth · route: `/reset?token=SC-TESTTOKEN-reset`

This is the state that ships and its copy (including the 1-hour, single-use sentence), the danger disc, the resend form, the 'Your password has not changed' banner and the footer all match. The card reads 45px taller than Figma, from the shared field, button and banner differences.

- **reset-r4-01** · class **A** · medium · page — Card is 45px taller than Figma (acceptance numbers for this state)
  - Figma: Card 749:154 is 430x547: disc 56, one-line title 29, four-line body 88, one field 67, button 47, banner 98, all 18px apart.
  - Build: Card is 430x592.3: field block +29, button +4, banner +9.3, title line +1. Body wraps to four lines in both.
  - Evidence: python3 scripts/vp_style_diff.py --slug reset-r4 --dom $RUN/marketing/reset-r4.blink.dom.json --limit 0 -> 'card 749:154 height figma 547 vs build 592.3'; 'input … build[542,452,356,45]'; 'banner 749:166 height figma 98 vs build 107.3'.
  - Fix: No separate change: closes when signin-06, signin-07, signin-09, signin-10, signin-11 and verify-v2-01 land. Acceptance: card 547px tall at 1440x900.
  - Linked: 17tnw2b2cf1
- **reset-r4-02** · class **D** · low · page — /reset 'no link' and 'link sent' states have no frame
  - Figma: The R-series has no frame for opening /reset without ?token= or for the 'new link requested' confirmation; /verify has V6 and V5.
  - Build: ResetView.vue:382-435 renders 'This page needs a reset link' (neutral disc, 'Send a reset link' form) and 'Check your inbox' ('If … has a SelahCue account, a new reset link is on its way. It expires in 1 hour.'), both extrapolated from V6 and V5.
  - Evidence: ResetView.vue:98-101 (state comments), :378-435; scripts/auth_pages_headless.py reset scenarios.
  - Decision: Uma: draw R-series equivalents of V6 and V5, or confirm that the V6/V5 frames are reused with the 1-hour copy.

### R5 Link expired (1h) — `reset-r5` (Figma `749:174`)

Verdict: **not-rendered-by-design** · area: auth · route: `/reset?token=SC-TESTTOKEN-reset`

R5 ('This reset link has expired', 1-hour TTL) is deliberately not rendered: the API cannot tell an expired reset token from an invalid one, so R4 ships for every token failure. The reset-r5 capture is the R4 card, the shipped substitute.

- **reset-r5-01** · class **B** · low · page — R5 'link expired' is designed but not rendered; R4 ships for every failure
  - Figma: Warn disc '!' #f2b53c, title 'This reset link has expired', body contrasting the 1-hour and 24-hour TTLs, Email field + 'Send a new reset link', warn banner 'Why only 1 hour', footer 'Remembered it? Back to Sign in' (749:174).
  - Build: Not rendered. ResetView.vue state 'invalid' (R4) covers every VALIDATION_FAILED and names the 1-hour single-use rule without asserting a cause (ResetView.vue:48-58, 322-357). The reset-r5 capture is scenario 'reset-invalid' (dom h1 = R4 title).
  - Evidence: surfaces.json: status not-rendered with source_probe must_not_contain 'This reset link has expired'. Style diff: 6 figma-only texts ('!', title, body, banner x3) vs the R4 equivalents. The 1-hour TTL is real (implementation/api/selahcue_api/settings.py:372 ACCOUNT_PASSWORD_RESET_TTL_SECONDS default…
  - Source: AUTH-LANDING-PAGES-HANDOFF.md §5.5 ('Needs §10.2 to be reachable') and §10.2 (confirm_password_reset collapses unknown/consumed/expired into one VALIDATION_FAILED; owner decision product + security). ClickUp 86ak120fz is named in ResetView.vue:53 as the owner of any change.

### R6 Password updated — `reset-r6` (Figma `749:198`)

Verdict: **diverges** · area: auth · route: `/reset?token=SC-TESTTOKEN-reset`

Copy, success disc, 'Continue to sign in', the 'Your devices keep presenting' banner and the 'Didn't do this? Contact support' footer match. Only the shared button-height and banner differences remain; the card reads 20px taller than Figma.

- **reset-r6-01** · class **A** · low · page — Card is 20px taller than Figma (acceptance numbers for this state)
  - Figma: Card 749:202 is 430x440: disc 56, title 29, three-line body 66, button 47, banner 98, all 18px apart.
  - Build: Card is 430x460.5: the link-button 'Continue to sign in' is 55.3px (+8.3), banner +9.3, title line +1 (about +19 of the +20). Disc, copy and wrapping match.
  - Evidence: python3 scripts/vp_style_diff.py --slug reset-r6 --dom $RUN/marketing/reset-r6.blink.dom.json --limit 0 -> 'card 749:202 height figma 440 vs build 460.5'; 'btn-primary 749:207 height figma 47 vs build 55.3'; 'banner 749:209 height figma 98 vs build 107.3'.
  - Fix: No separate change: closes when signin-10 and verify-v2-01 land. Acceptance: card 440px tall at 1440x900.
  - Linked: 17tnw2b2cf1

### R7 Server error — `reset-r7` (Figma `749:217`)

Verdict: **diverges** · area: auth · route: `/reset?token=SC-TESTTOKEN-reset`

Danger banner above the title, form, 'Try again' and the reassurance copy match. The footer offers 'Back to Sign in' where Figma offers 'Request a new reset link', and the build also has a PASSWORD_INVALID state no frame covers.

- **reset-r7-01** · class **A** · high · page — Footer link offers sign-in instead of a new reset link
  - Figma: 'Still stuck?' + 'Request a new reset link' 14/600 accent/brand (749:244). Handoff §5.7 'footer offers a fresh link'; copy deck §8.2 R7.
  - Build: 'Still stuck?' + 'Back to Sign in' linking to /signin (ResetView.vue:443). On a state whose banner says the link still works, the way out offered is the wrong page.
  - Evidence: python3 scripts/vp_style_diff.py --slug reset-r7 --dom $RUN/marketing/reset-r7.blink.dom.json --limit 0 -> figma-only 'Request a new reset link' (y=754.5); build-only 'Back to Sign in'; 'Still stuck? x +32.8 px'.
  - Fix: Change the R7 footer link (ResetView.vue:443) to the text 'Request a new reset link' pointing at /forgot-password (route exists, router/index.ts:36).
  - Linked: 17tnw2b2cf1
- **reset-r7-02** · class **D** · low · page — PASSWORD_INVALID state has no frame
  - Figma: R7 is the only form-with-danger-banner frame ('We couldn't update your password').
  - Build: ResetView.vue:252-260 renders the same layout with 'That password wasn't accepted' / 'Your password has not been changed and this reset link still works. Choose a different password and try again.' for a server-side PASSWORD_INVALID. DEC-017 sanctioned the distinct code after the R-series was drawn.
  - Evidence: ResetView.vue:92-97, 248-260; DECISION-LOG.md:36 (DEC-017).
  - Decision: Uma: draw the 'password not accepted' variant of R7 and confirm its copy.

### D1 Populated (3 of 5) — `devices-d1` (Figma `753:124`)

Verdict: **not-built** · area: account · route: `/account/devices`

/account/devices does not exist and renders the 404 view; the populated Manage devices page (3 of 5) needs a route, the portal shell with a Devices sidebar item, a meter, device rows and a footnote. Figma-side defects found while extracting it (black sidebar labels, accent ink below AA, undrawn states) are recorded as account-25, account-28 to account-30.

- **devices-d1-01** · class **E** · high · page — Route /account/devices and the account portal shell with the Devices sidebar item at position 4
  - Figma: Portal shell cloned from 506:124: nav, header band 753:139 (y79-197, pad 44/96/24, gap 16: avatar 50x50, org 20/700, email 14/400, 'PRO PLAN' pill 80x23, 'Sign out' 92x41), body 753:150 (pad 8/96/64, gap 32), sidebar card 753:151 (240 wide, fill #171b22, 1px #2b323d, r16, pad 18/14, gap 6, rows 212x38 pad 10/12). Sidebar has SIX rows: Overview y223, Subscription & billing y267, License y311, Devices y355 (selected: 753:296 fill #1e232c, r9, label 14.5/600 #5b6bd6), Invoices y399, Settings y443.…
  - Build: Nothing. No route, no view, no sidebar (the /account sidebar itself is missing, account-01). The 'Manage devices' button 506:223 that should open this page is not rendered either (account-07).
  - Evidence: Router: only '/account' is registered (src/router/index.ts:53-57); '/account/devices' falls through to the '/:pathMatch(.*)*' catch-all (index.ts:89) and renders NotFoundView. $RUN/report.md row for this slug: 'NOT BUILT (class E) - /account/devices renders the site's 404 view'. Style dump figma-st…
  - Fix: 1) Add { path: '/account/devices', name: 'account-devices', component: () => import('@/views/AccountDevicesView.vue'), meta: { requiresSession: true } } next to '/account' in router/index.ts. 2) Extract the header band + sidebar from AccountView into AccountShell.vue (precedent: AdminShell.vue, AffiliateShell.vue) and use it from both views so chrome is pixel-identical (handoff 2.1). 3) Sidebar: six links, 'Devices' fourth with the selected treatment above and aria-current="page"; the shell's Sign out must call signOut (bug-01). 4) Card header: title + subtitle + state pill (ink --sc-primary …
  - Linked: 17tnw2b2cf2
- **devices-d1-02** · class **E** · high · page — Device list: activation meter, device rows and deactivation footnote
  - Figma: Meter 753:305 (y297, h34, gap 9): row 753:306 'Device activations' 14/400 #9aa4b2 + '3 of 5 used' 14/600 #eef1f6 right; track 753:309 (y323) 920x8, five segments 179.2x8 r4 gap 6 (used #5b6bd6, free #1e232c). List 753:315 (y349, 920x201): fill #0e1116, 1px #2b323d, r12, three rows 753:316/325/332, each 67 tall, pad 15/18, gap 12, 1px #2b323d between: dot 9px (x414; #2bb673 recent / #9aa4b2 stale), info column (gap 3): name 15/600 #eef1f6 (name-row gap 8; 'THIS DEVICE' tag 753:321 80x18 fill #1e…
  - Build: No device list, no meter, no footnote anywhere. /account has a six-column table with an IP column (account-07, account-08) that is NOT the target.
  - Evidence: Router: only '/account' is registered (src/router/index.ts:53-57); '/account/devices' falls through to the '/:pathMatch(.*)*' catch-all (index.ts:89) and renders NotFoundView. $RUN/report.md row for this slug: 'NOT BUILT (class E) - /account/devices renders the site's 404 view'. figma-style/devices…
  - Fix: Components: ActivationMeter (shared with /account, account-06; segments = max(limit, used), role="progressbar" aria-valuemin/max/now + the 'N of M used' text), DeviceRow (dot, name, optional THIS DEVICE tag, meta line, Deactivate), DeviceList (well --sc-inset, 1px --sc-border, r12). Row height 67, effective Deactivate hit area >= 44px (handoff 12). Meta recency format: 'today at HH:mm' | 'N days ago' | 'D Mon YYYY'. Sort most-recently-seen first. Dot ink: --sc-preview when seen recently, --sc-text-secondary when stale (threshold is a product call; the text always carries the same fact). Footn…
  - Linked: 17tnw2b2cf2

### D2 Deactivate confirm — `devices-d2` (Figma `754:124`)

Verdict: **not-built** · area: account · route: `/account/devices`

The deactivate confirm dialog is not built; the closest piece, ConfirmDialog, differs in size, surface, icon, banner, button colour and focus handling, and the page's existing deactivate copy contradicts the never-blank invariant. The red button label is 3.76:1 and needs a design decision (account-31).

- **devices-d2-01** · class **E** · high · shared · confirm-dialog — Deactivate confirm dialog with the 'Nothing goes dark' banner
  - Figma: Scrim 754:241 full frame 1440x1054, fill #0e1116 at opacity 0.70 (handoff text says 72%). Dialog 754:242 420x391 centred (x510,y332): fill #1e232c, 1px #2b323d, r16, pad 28/28/24/28, gap 16. Contents: '!' 30/700 #f2b53c (no disc) at top-left; title 'Deactivate Youth Hall PC?' 18/600 #eef1f6; body 14/400 lh20 #9aa4b2 'This frees one of your 5 device slots straight away. Youth Hall PC keeps presenting offline until its cached entitlement expires, then it must be activated again.'; success banner …
  - Build: Closest existing piece: components/ConfirmDialog.vue + AccountView.vue:412-420. ConfirmDialog: max-width 440, pad 32, fill --sc-surface, blur(8px) scrim at 0.75, an SVG warning triangle inside a tinted disc, no banner slot, no hint line; the 'warning' variant renders the confirm button as 'secondary' (grey), not a red fill; no focus trap, no initial focus and no aria-describedby (grep focus/trap/inert/aria-describedby in ConfirmDialog.vue: none; only aria-label). AccountView's copy: 'Deactivate…
  - Evidence: Router: only '/account' is registered (src/router/index.ts:53-57); '/account/devices' falls through to the '/:pathMatch(.*)*' catch-all (index.ts:89) and renders NotFoundView. $RUN/report.md row for this slug: 'NOT BUILT (class E) - /account/devices renders the site's 404 view'. figma-style/devices…
  - Fix: Extend ConfirmDialog (do not fork): width 420, pad 28/28/24/28, gap 16, --sc-elevated fill, r16; glyph slot '!' 30/700 --sc-warn without a disc; add a `banner` slot rendered with AuthBanner kind="success" ('Nothing goes dark' + body) and a `hint` line (12/400, --sc-text-secondary, 'Esc keeps the device active.'); cancel button = outline with 1.5px --sc-primary ring and receives initial focus; confirm = --sc-live fill, r10 (label ink per account-31); trap focus, restore it on close, aria-labelledby + aria-describedby, lock page scroll, scrim --sc-base at 0.72. Copy interpolates {name} and {lim…
  - Linked: 17tnw2b2cew

### D3 All slots in use (5 of 5) — `devices-d3` (Figma `754:257`)

Verdict: **not-built** · area: account · route: `/account/devices`

The all-slots-in-use state (5 of 5) is not built: it needs the warning banner, a full meter, five rows and two plan CTAs, one of which has no destination page (account-32).

- **devices-d3-01** · class **E** · high · page — Instance-limit state: all slots in use (5 of 5) with warning banner
  - Figma: Pill 754:303 '5 OF 5 ACTIVE' ink #f2b53c. Warning banner 754:388 directly under the card header: 920x85 at y297, fill #2a2415 (= --sc-warn-soft), r12, pad 14/16, gap 12; glyph '!' 15/700 #f2b53c; title 'All device slots are in use' 13.5/600 #eef1f6; body 13/400 lh19 #9aa4b2 'Your plan includes 5 devices and all 5 are active. Deactivate one you no longer use to free a slot, or move to a larger plan. Activating a new device is refused until a slot is free.' Meter 754:305 moves to y400 with all fi…
  - Build: Not built (no page).
  - Evidence: Router: only '/account' is registered (src/router/index.ts:53-57); '/account/devices' falls through to the '/:pathMatch(.*)*' catch-all (index.ts:89) and renders NotFoundView. $RUN/report.md row for this slug: 'NOT BUILT (class E) - /account/devices renders the site's 404 view'. figma-style/devices…
  - Fix: State = used === limit (and limit > 0). Render AuthBanner kind="warning" role="alert" with the title/body above (interpolate {limit} and {used}) between the card header and the meter, 18px gap; pill ink --sc-warn (8.6:1 on --sc-elevated); meter all used; row list unchanged. Banner body uses --sc-text-secondary, never the status colour (handoff 2.2).
  - Linked: 17tnw2b2cf2
- **devices-d3-02** · class **E** · medium · page — Plan CTAs under the list: 'View plans' and 'How device slots work'
  - Figma: CTA row 754:393 (y861, h41, gap 10; 18px below the footnote): 'View plans' 754:394 110x41 fill #5b6bd6 r10 pad 12/18, 14/600 #ffffff; 'How device slots work' 754:396 189x41, 1px #2b323d, r10, 14/600 #eef1f6. Present in D3 and D6; absent in D1.
  - Build: Not built.
  - Evidence: Router: only '/account' is registered (src/router/index.ts:53-57); '/account/devices' falls through to the '/:pathMatch(.*)*' catch-all (index.ts:89) and renders NotFoundView. $RUN/report.md row for this slug: 'NOT BUILT (class E) - /account/devices renders the site's 404 view'. Handoff 7.3 and 14:…
  - Fix: Render only in the limit-reached and over-limit states. 'View plans' = primary link to /pricing (UiButton to="/pricing", per account-24 sizing). 'How device slots work' = outline link; destination per account-32. White on #5b6bd6 is 4.65:1 (passes).
  - Linked: 17tnw2b2cf2

### D4 No devices (0 of 5) — `devices-d4` (Figma `755:124`)

Verdict: **not-built** · area: account · route: `/account/devices`

The empty state (0 of 5) is not built: centred disc, title, body, two buttons and an info banner. Its body points users at Settings > Account, which the desktop app does not have yet (account-33).

- **devices-d4-01** · class **E** · high · page — Empty state: no devices activated yet (0 of 5)
  - Figma: Pill 755:170 '0 OF 5 ACTIVE' ink #9aa4b2; meter 755:172 with five empty #1e232c segments, '0 of 5 used'. Empty state 755:241 (y349, 920x286): fill #0e1116, 1px #2b323d, r12, pad 44/28, gap 14, centred: icon disc 755:242 52x52 #1e232c r999 with '◆' 20/700 #9aa4b2; title 'No devices activated yet' 17/600 #eef1f6; body 14/400 lh21 #9aa4b2 centred, 520 wide: 'Install SelahCue on the computer that runs your service, then open Settings > Account and sign in. The device appears here as soon as it acti…
  - Build: Not built.
  - Evidence: Router: only '/account' is registered (src/router/index.ts:53-57); '/account/devices' falls through to the '/:pathMatch(.*)*' catch-all (index.ts:89) and renders NotFoundView. $RUN/report.md row for this slug: 'NOT BUILT (class E) - /account/devices renders the site's 404 view'. figma-style/devices…
  - Fix: State = used === 0 and load succeeded. Reuse StatusDisc (auth/StatusDisc.vue; note it is 56px, this frame is 52px) with glyph '◆' tone neutral, AuthBanner kind="info" for the footer banner. 'Download SelahCue' = primary link to /download (account-24 sizing); second button per account-32. Title uses the typographic apostrophe exactly as drawn. Pill ink --sc-text-secondary, meter empty (all --sc-elevated).
  - Linked: 17tnw2b2cf2

### D5 Could not load devices — `devices-d5` (Figma `755:256`)

Verdict: **not-built** · area: account · route: `/account/devices`

The couldn't-load error state is not built: header pill and meter are removed, a centred error well with Retry and a reassurance banner are drawn.

- **devices-d5-01** · class **E** · high · page — Error state: couldn’t load devices, with Retry and reassurance banner
  - Figma: Header 755:298 loses the pill and meter: titles 755:299 fill the full 920px (no right pill). Error state 755:373 (y297, 920x286): fill #0e1116, 1px #2b323d, r12, pad 44/28, gap 14, centred: disc 755:374 52x52 #1e232c with '✕' 20/700 #ef4444; title 'Couldn’t load your devices' 17/600 #eef1f6; body 14/400 lh21 #9aa4b2, 520 wide: 'We couldn’t reach SelahCue just now. Check your connection and try again — this page is the only thing affected.'; 'Retry' 755:378 73x41 fill #5b6bd6 r10 14/600 white. S…
  - Build: Not built.
  - Evidence: Router: only '/account' is registered (src/router/index.ts:53-57); '/account/devices' falls through to the '/:pathMatch(.*)*' catch-all (index.ts:89) and renders NotFoundView. $RUN/report.md row for this slug: 'NOT BUILT (class E) - /account/devices renders the site's 404 view'. figma-style/devices…
  - Fix: State = devices query rejected with a network/server error (not UNAUTHENTICATED - that must go to /signin via the existing session handling, not this card). Hide pill and meter entirely. Error container role="alert" (consistent with D3/D6, handoff 12); Retry re-runs the query with a pending state (disable + 'Retrying...', not drawn - account-30). AuthBanner kind="success" for the footer banner. Use ’ (U+2019) exactly as drawn.
  - Linked: 17tnw2b2cf2

### D6 Over the plan limit (5 of 3) — `devices-d6` (Figma `755:385`)

Verdict: **not-built** · area: account · route: `/account/devices`

The over-limit state (5 of 3) is not built; it is backed by the PRD and DEC-009 (a downgrade never revokes devices) but needs a danger banner, a red-segment meter and an over-limit signal the API does not expose (api-06). Figma-side notes: account-34, account-35.

- **devices-d6-01** · class **E** · high · page — Over-limit state: more devices active than the plan allows (5 of 3)
  - Figma: Pill 755:431 '5 OF 3 ACTIVE' ink #ef4444. Danger banner 755:526 under the header: 920x85, fill #2a1416 (= --sc-live-soft), r12, pad 14/16, gap 12; glyph '!' 15/700 #ef4444 (the handoff 2.2 table says '✕' for danger - the frame draws '!'); title 'You have more devices than your plan allows' 13.5/600 #eef1f6; body 13/400 lh19 #9aa4b2 'Your plan now includes 3 devices and 5 are still active. Deactivate 2 to come back within your plan. Nothing has been switched off — every device keeps presenting, …
  - Build: Not built.
  - Evidence: Router: only '/account' is registered (src/router/index.ts:53-57); '/account/devices' falls through to the '/:pathMatch(.*)*' catch-all (index.ts:89) and renders NotFoundView. $RUN/report.md row for this slug: 'NOT BUILT (class E) - /account/devices renders the site's 404 view'. figma-style/devices…
  - Fix: State = used > limit. Render AuthBanner kind="danger" role="alert" with the copy above ({limit}, {used}, {used - limit} computed client-side); pill and meter value ink --sc-live; meter segments = max(limit, used) with the first `limit` segments --sc-primary and the remainder --sc-live. Deactivate stays available on every row (it is the fix path); CTA row as D3. Needs an over-limit-capable devices query (api-06): the limit must come from the licence, and today it only changes at issuance.
  - Linked: 17tnw2b2cf2

## How to re-run

```bash
(cd implementation/marketing && npm ci && npm run build)
python3 scripts/visual_parity.py --suite marketing            # capture all 35 surfaces from dist/ and compare
python3 scripts/vp_style_diff.py --slug home --dom .visual-parity/run-*/marketing/home.blink.dom.json --limit 0
python3 scripts/vp_slice.py --slug home --run .visual-parity/run-<stamp> --y 0 --h 900 --out /tmp/home-0.png
python3 scripts/vp_reference.py --suite marketing verify      # 35 references + style dumps, caps, checksums
python3 scripts/vp_selftest.py                                # prove the harness itself still bites
python3 scripts/check_fidelity_audit.py                        # this audit's structure
```

## What this audit does not show

- Only 1440 wide; mobile and tablet layouts belong to ClickUp 17tnw2b0q9g.
- Only the states the capture can drive (the account API is scripted); hover, focus rings, and real-API behaviour are read from source, not photographed.
- Chromium rendering; Safari/WebKit and real devices are not evidenced (the harness can capture WebKit with `--engine both`).
- Figma's own text metrics (Inter) can differ from the web font by a pixel or two: differences under 3px are not reported.
- A low similarity score points at where to look; the classification in the findings is the verdict.

