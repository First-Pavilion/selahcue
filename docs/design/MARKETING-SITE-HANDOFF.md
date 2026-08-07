# SelahCue — Marketing Website · Design Handoff

**Deliverable:** a full, **multi-page** marketing website for SelahCue, designed on a new Figma page.
**Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ` → page **"Marketing Website"** (id `468:124`).
Each site page is its own 1440-px auto-layout frame, laid out left-to-right on the canvas:

| Site page | Figma frame | x | Notes |
|-----------|-------------|---|-------|
| **Home** | `468:125` | 0 | Long-scroll landing (hero → features → pricing → FAQ → CTA) |
| **Features** | `485:124` | 1740 | Deep-dive: 6 alternating capability rows |
| **Pricing** | `483:124` | 3480 | Plans + monthly/annual toggle + full comparison table |
| **Download** | `487:124` | 5220 | Platform cards, system requirements, mobile app, install steps |
| **About** | `496:124` | 6960 | Story (2-col) + "What we stand for" values grid + CTA |
| **Contact** | `497:124` | 8700 | Message form + contact-method cards + response note |
| **Support** (Help Center) | `498:124` | 10440 | Search + 6-category grid + popular-articles list |
| **Documentation** | `499:124` | 12180 | Sidebar nav + getting-started + topic grid (absorbs "Setup guides") |
| **Changelog** | `501:124` | 13920 | Versioned release cards (New / Improved / Fixed) |
| **Blog** | `502:124` | 15660 | Featured post + 6-card article grid |
| **Careers** | `503:124` | 17400 | Culture perks + open-roles list |
| **Privacy Policy** | `504:124` | 19140 | Legal prose (offline-first, minimal data) |
| **Terms of Service** | `504:203` | 20880 | Legal prose (licence, subscription/billing, disclaimers) |
| **Sign in** | `505:124` | 22620 | Centered auth card (email/password + Google) |
| **Account** | `506:124` | 24360 | Signed-in dashboard: subscription/billing, license & devices, invoices |
| **Affiliate program** | `541:124` | 26100 | Public program landing: hero (20% recurring) + highlights + how-it-works + who-it's-for + earnings example + FAQ + gradient CTA |

Nav and footer are **shared** — cloned from Home into each page, with the current route highlighted
(`text/primary` + Semi Bold) in the nav. `Features / Pricing / Download` are top-nav pages; the remaining
pages are reached from the **footer** columns (so no footer link is a dead end) and the **Sign in** nav link.
`How it works` is an in-page anchor on Home; `NDI & streaming` (footer) points to the Features page;
`Setup guides` (footer) points to the Documentation page. The footer **Company** column now includes an
**Affiliates** link (added site-wide across all 15 footers) → the Affiliate program page. **Sign in** is only
for managing a paid plan — the app itself needs no account (see the Account/Sign-in note in §5).
**Design system:** reuses the file's local **"SelahCue Color"** variable collection and **Inter** throughout.

> **Fact labelling.** Product capabilities described below are **Verified** from the codebase
> (`CLAUDE.md`, the desktop workspace, and the Screens/Outputs/NDI work). Pricing numbers,
> testimonial names/quotes, and specific FAQ answers are **Assumed** placeholder marketing
> copy — they must be reviewed/approved by product + a real customer/legal pass before launch.
> Pricing is a **subscription** model (see §2) — the figures/tiers are placeholders pending sign-off.

---

## 1. Information architecture

### 1a. Site map (pages)

- **Home** (`468:125`) — landing page; the full narrative below.
- **Features** (`485:124`) — hero + 6 alternating capability rows (Live outputs · Scripture · Plans & timers · Stage monitor · NDI & multi-output · On-device transcript), each with a bullet list and a stylized product panel + closing CTA + footer.
- **Pricing** (`483:124`) — hero + Monthly / Annual (save 20%) toggle + the three plan cards + a full **feature comparison table** (Free / Pro / Church) + footer.
- **Download** (`487:124`) — hero + Windows & macOS platform cards + Minimum/Recommended system requirements + mobile-control split (phone mock + iOS/Android) + a 3-step install guide + footer.
- **About** (`496:124`) — hero + "Why we built SelahCue" story (2-col) + a 4-card values grid + closing CTA + footer.
- **Contact** (`497:124`) — hero + a 2-col split: a message **form** (name / email / church / message + Send) beside contact-method cards (email, support, community) and a response-time note.
- **Support / Help Center** (`498:124`) — hero with a **search** field + a 6-category grid + a popular-articles list + "still stuck → contact" line.
- **Documentation** (`499:124`) — hero + a **sidebar** category nav beside a getting-started intro, a "run your first service" callout, and a 6-topic grid. Absorbs the footer's "Setup guides".
- **Changelog** (`501:124`) — hero + stacked **release cards** (v1.0.0 latest, v0.9.0, v0.8.0), each grouped into New / Improved / Fixed. Version numbers/dates are illustrative placeholders.
- **Blog** (`502:124`) — hero + a large **featured post** + a 6-card article grid. Titles/authors are placeholders (author shown as "SelahCue Team", no fabricated individuals).
- **Careers** (`503:124`) — hero + a 4-card culture strip + an **open-roles** list (title · dept · location · type). Roles are illustrative placeholders.
- **Privacy Policy** (`504:124`) & **Terms of Service** (`504:203`) — legal prose pages sharing one layout (title + last-updated + numbered sections). Content reflects the real **offline-first / no-account** architecture and the **subscription** billing model, but is **placeholder — not legal advice**; a real legal pass is required before launch.
- **Sign in** (`505:124`) — a focused, centered **auth** screen (brand lockup + email/password with "Forgot?" + Sign in + "or" + Continue with Google + "Create an account"). Designed at 1440×900; the wrapper has a fixed height so the card sits centered.
- **Account** (`506:124`) — the signed-in **dashboard** for managing a paid plan: an account header (avatar, org name, email, plan pill, Sign out), a left section-nav, and three cards — **Subscription & billing** (plan, cycle, next payment, payment method, Change plan / Update payment / Cancel), **License** (masked key + Copy, device-activation meter "2 of 5", per-device list with Deactivate, Manage devices), and **Billing history** (invoice table with Paid status + Download). All values are placeholders.
- **Affiliate program** (`541:124`) — public marketing landing for the affiliate program: hero ("Earn 20% recurring…") + Apply/Sign-in CTAs, four commission-highlight cards, a 3-step "How it works", a 4-card "who it's for", a "why it's easy to recommend" checklist beside an **illustrative earnings-example** card, an affiliate FAQ accordion, and a gradient CTA band. Its **Apply now / sign in** CTAs lead to the affiliate **portal** (Apply `539:155` / Sign in `539:124` — see `ADMIN-CONSOLE-HANDOFF.md`); commission figures are placeholders. Reachable from the footer's new **Affiliates** link on every page.

### 1b. Home page sections (top → bottom)

| # | Section | Figma node | Purpose |
|---|---------|-----------|---------|
| 1 | Nav bar | `468:126` | Brand + Features / How it works / Pricing / Download · Sign in · **Download free** |
| 2 | Hero | `469:124` (mock `470:124`) | Positioning headline + primary/secondary CTA + product-console mock |
| 3 | Features | `472:124` | 6-card grid of core capabilities |
| 4 | Reliability band | `474:124` | "Built for the one moment you can't repeat" + 3 pillars |
| 5 | Screens & Outputs / NDI showcase | `475:124` | Split text + mini output-manager mock |
| 6 | How it works | `476:124` | 3 numbered steps |
| 7 | Pricing | `477:124` | Free / **Pro (most popular)** / Church |
| 8 | Testimonials | `478:124` | 3 quote cards |
| 9 | FAQ | `478:153` | 5 Q&A |
| 10 | Final CTA | `479:124` | Gradient band, "Ready to run your best service yet?" |
| 11 | Footer | `479:133` | Brand + Product/Resources/Company columns + legal |

---

## 2. Content (copy)

**Hero** — eyebrow "Church presentation, reengineered"; H1 "Run your service with total confidence.";
sub "SelahCue is the offline-first presentation & ministry-assistance app that never blanks the screen — scripture, songs, timers, stage display, and NDI outputs, controlled from anywhere.";
CTAs "Download free" / "Watch 2-min demo"; trust "Free to start · Works fully offline · Windows, macOS & mobile control".

**Features** (icon · title · blurb) — all **Verified** capabilities:
Live presentation & outputs · Scripture at your fingertips · Service plans & timers · Stage & confidence monitor · NDI & multi-output · On-device transcript.

**Reliability pillars** — Never blanks the screen (NFR-024) · Works fully offline · Fast & bounded (≤3 s cold start, capped memory). All **Verified** product invariants.

**Screens & Outputs showcase** — checklist: Audience projector · Stage display (current/next/timer) · NDI output to OBS/vMix. Mock shows Audience–Main (MAIN·LIVE), Stage Display (STAGE·READY), Livestream Program (NDI·BROADCASTING).

**How it works** — 1) Plan your service · 2) Go live with one tap · 3) Control from anywhere (console or paired phone over LAN).

**Pricing** (**Assumed** figures — **subscription** model): Free $0 forever · **Pro $19 / month** (most popular; billed monthly or ~20% off annually) · Church Custom. Feature checklists per tier on Home; a full Free/Pro/Church comparison table on the Pricing page. Copy stresses *start free, upgrade when ready, cancel anytime — still fully offline on Sunday.*

**Testimonials / FAQ** — **Assumed** placeholder quotes & answers; 5 FAQs cover offline, platforms, custom content, NDI, and **billing** ("How does billing work?" — free tier forever, paid tiers monthly/annual, cancel anytime, no internet needed to keep running).

**Final CTA** — "Ready to run your best service yet?" / "Start free and go live this Sunday. Cancel anytime — and it runs fully offline when it matters most."

---

## 3. Design system usage

**Colors** — bound to the `SelahCue Color` variables (never hardcoded except two cases noted below):
`bg/base` #0e1116 (page) · `bg/panel` #171b22 (cards, bands) · `bg/elevated` #1e232c (titlebars, chips, secondary buttons) · `border` #2b323d (1 px hairlines) · `text/primary` #eef1f6 · `text/muted` #9aa4b2 · `accent/brand` #5b6bd6 (primary CTA, links, focus) · `accent/preview` #2bb673 (checks, stage/broadcast status) · `accent/live` #ef4444 (LIVE) · `accent/warn` #f2b53c (READY, gold accents).

**Type ramp (Inter):** H1 60/64 Bold · Section H2 38–42 Bold · Card/step title 18–21 Semi Bold · Body/sub 17–19 Regular · Small/blurb 14–15 · Eyebrow 13 Bold +200 tracking · Micro/badges 10–12.

**Spacing:** 96 px horizontal gutters; ~88–90 px vertical section padding; 20–28 px grid gaps; 14–18 px card radii, 999 px pills.

**Two intentional non-token colors:** pure white (`#ffffff`) for text/icons on colored fills (CTA buttons, feature icons, avatars), and the CTA gradient (`accent/brand` → deep indigo `#2b2a6b`). Everything else is variable-bound.

---

## 4. Responsive behaviour (spec for build — desktop is designed at 1440)

- **≥1200 (desktop, designed):** as shown. Feature grid 3-up (cards min 320, `auto-fill`), pricing/steps/pillars 3-up, testimonials 3-up.
- **768–1199 (tablet):** gutters → 48 px; feature grid 2-up; pricing/steps/pillars/testimonials 2-up (or 1-up for pricing to keep the Pro card prominent); hero mock scales to width.
- **<768 (mobile):** gutters → 20 px; nav collapses to a hamburger (links + CTA in a sheet); all grids 1-up; H1 → ~36/40; hero mock full-width; footer columns stack; CTA gutters reduce.
- Use CSS Grid `repeat(auto-fill, minmax(320px, 1fr))` for the feature grid (the operator app already uses this pattern) and flex-wrap for pricing/testimonials.

---

## 5. States

- **Nav:** default; **sticky** on scroll with a subtle `bg/base` blur + bottom `border`; link **hover** → `text/primary`; active route underline; CTA hover → brand-hover (+8% lightness).
- **Buttons:** default / hover (lightness shift) / focus-visible (2 px `accent/brand` ring, 2 px offset) / active (scale 0.98) / disabled (50% opacity).
- **FAQ:** rows are an **accordion** — the `+` glyph is the affordance; collapsed shows the question only, expanded reveals the answer and rotates `+`→`×`. Designed expanded for review; ship collapsed-by-default with the first item open.
- **Download / Talk-to-us:** link to app-store/download or a **contact form** — spec the form's empty, focus, validation-error, submitting (spinner), success, and error states before build (out of scope for this static page).
- **Contact & Sign-in forms:** only the **default** state is drawn. Before build, spec each field's focus (2 px `accent/brand` ring), filled, inline validation-error (`accent/live` border + message), disabled, submitting (spinner), success, and server-error states. Sign-in also needs wrong-credentials and rate-limited states; "Continue with Google" needs its OAuth redirect/loading state.
- **Account portal (Sign in + Account):** these are the **only account-gated screens** — everything else is public. The desktop app needs **no account**; sign-in exists solely to manage a paid plan (billing + license). Spec the additional states before build: signed-out redirect → Sign in; loading/skeleton for the dashboard cards; **Cancel subscription** and **Deactivate device** are destructive → confirmation dialogs (name the consequence, e.g. "Pro features end on 1 Sep 2026"); Copy-key success toast; empty states (no invoices yet, free-tier account with nothing to bill); payment-failed / past-due banner on the Subscription card.
- **Loading:** hero product mock and any imagery need a skeleton/`bg/elevated` placeholder to avoid layout shift.

---

## 6. Accessibility

- **Contrast:** body/heading text on `bg/base`/`bg/panel` passes AA. `text/muted` (#9aa4b2) on `bg/base` ≈ 5.6:1 (AA for body). Colored status text sits on solid `bg/elevated` pills (readable) — do **not** put same-color text on a same-color tinted fill (a bug that was fixed in this design). White CTA text on `accent/brand` passes AA-large; verify AA for the 15.5 px label or bump weight.
- **Focus order:** nav → hero CTAs → each section's interactive elements top-to-bottom → footer. Every button/link needs a visible `:focus-visible` ring (`accent/brand`).
- **Keyboard:** nav menu, FAQ accordion, and pricing CTAs fully operable; accordion toggles on Enter/Space and exposes `aria-expanded`.
- **Semantics:** one `<h1>` (hero); sections use `<h2>`; FAQ as a definition/disclosure pattern; nav is a `<nav>`; the brand logo is an `<img>` with alt "SelahCue logo" (or `aria-hidden` when adjacent to the "SelahCue" wordmark to avoid double-announcing); remaining decorative glyphs (▶, dots) are `aria-hidden`.
- **Touch targets:** nav links and mobile CTAs ≥ 44 px tall.
- **Reduced motion:** the CTA gradient and any hover transitions must respect `prefers-reduced-motion` (no parallax/auto-animation).
- **Alt text:** the product-console mock and any real screenshots need descriptive alt (e.g. "SelahCue operator console showing a Preview and Live scripture slide").

---

## 7. Implementation notes & assets

- Built almost entirely from auto-layout frames + variable-bound fills + `Inter`. The only raster asset is the **brand logo** (below). The hero/showcase "product windows" are still vector mocks — for production, replace them with real console screenshots (transfer image hashes per the figma-generate-design image workflow, or export from the app).
- **Brand logo (real asset, in use):** the SelahCue open-book-with-flame mark — source `implementation/desktop/crates/selahcue-operator/dist/selahcue-logo.png` (1254×1254, transparent-background PNG, indigo `#6E5CF0`). It replaced the placeholder `◆` glyph in every nav lockup, every footer lockup, the hero eyebrow pill, the phone-mock topbar, and the Sign-in/Account brand marks — placed as a square `IMAGE`/`FIT` fill (**32 px nav · 28 px footer · 18 px hero · 16 px phone · 30 px Sign-in**) beside the "SelahCue" wordmark. **Note:** the source PNG has ~33% transparent padding baked in (the mark fills only 61%×67% of the canvas), so for Figma the mark was **tight-cropped** to fill its box; in the built site either trim the source's padding the same way or size the `<img>` up to compensate. Use the asset as an `<img>` with descriptive alt "SelahCue logo".
- Icons are inline feather-style SVGs (`createNodeFromSvg`) — reuse the same set in the built site for consistency.

---

## 8. Assumptions & follow-ups

- **Assumed (needs product/marketing/legal sign-off):** all pricing figures, the **subscription tiers & billing terms** (monthly/annual, cancel-anytime, free-tier limits), testimonial names/quotes/churches, specific FAQ answers, changelog versions/dates, blog titles, open roles, and the placeholder legal copy on Privacy/Terms. Replace with approved copy; the legal pages in particular need a real legal review.
- **Assumed placeholders on the account portal:** the org name, email, license key, device list, payment method, and invoice history on the Account dashboard, and the OAuth provider(s) on Sign in.
- **Built (this pass):** the full site at desktop 1440 with shared nav/footer + active-route states — **Home, Features, Pricing, Download, About, Contact, Support, Documentation, Changelog, Blog, Careers, Privacy, Terms**, plus the account portal (**Sign in** + **Account** dashboard). Every footer link resolves to a real page. The real **brand logo** is placed across all lockups.
- **Out of scope (recommend as follow-ups):** mobile & tablet breakpoint frames for all pages; the non-default form/portal **states** enumerated in §5 (validation, submitting, success/error, destructive confirmations, empty & past-due states); the real auth + billing/checkout + license backend; a create-account / forgot-password screen; light-theme variant (the site is dark-only, matching the app); real screenshots + a demo video; deeper article/doc/role detail pages behind the index pages.
- **Next role:** frontend-engineer to implement (the app's existing `--sc-*` tokens map 1:1 to these variables), after product signs off the placeholder copy; a security/legal pass on the account portal + legal pages before launch.
