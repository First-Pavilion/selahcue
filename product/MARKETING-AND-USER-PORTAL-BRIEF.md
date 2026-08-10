# SelahCue — Marketing Website & User Portal · Product Brief

**Version:** 0.1 · **Status:** Draft — Awaiting Product Sign-off  
**Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ` → page **"Marketing Website"** (id `468:124`)  
**Parent PRD:** `docs/product/prds/SelahCue-PRD.md` (v1.1)  
**Related:** `docs/design/MARKETING-SITE-HANDOFF.md` · `docs/design/ADMIN-CONSOLE-HANDOFF.md`  
**Fact labelling:** Items are marked **Verified**, **Inferred**, **Assumed**, or **Unknown** per policy.

---

## 1. Problem Statement & Opportunity

SelahCue is a cross-platform, offline-first church presentation and ministry-assistance application. The desktop app, mobile controller, and design system are well advanced (**Verified** — see `CLAUDE.md`, the Rust workspace, and Flutter controller). However, the product lacks:

1. **A public marketing presence** — no website exists to communicate the product's value proposition, differentiate from competitors (ProPresenter, EasyWorship, OpenLP, FreeShow, PewBeam), or drive downloads.
2. **A customer self-service portal** — churches that upgrade to a paid plan need a web interface to manage their subscription, license keys, device activations, Bible entitlements, invoices, and account settings.
3. **A commercial acquisition and conversion funnel** — the pricing model (Free / Pro / Church tiers, **Assumed** — see `MARKETING-SITE-HANDOFF.md` §2) needs a public face, a checkout flow, and a way to convert free users to paying customers.

These three surfaces are tightly coupled: the marketing site is the acquisition layer that leads to downloads and sign-ups; the user portal is the retention layer where paid customers manage their relationship with SelahCue.

---

## 2. Target Users

### Marketing Website

| User | Goal | Notes |
|------|------|-------|
| **Church tech volunteer** | Evaluate SelahCue, compare to current tool, download | Primary acquisition target. Volunteer-friendly UX is the key differentiator (**Verified** — PRD). |
| **Worship/tech pastor** | Understand capabilities, compare pricing, make purchase decision | Decision-maker who sees the Features, Pricing, and About pages. |
| **Livestream director** | Evaluate NDI/multi-output, streaming integration | Looks at Features deep-dive and NDI showcase. |
| **Church administrator** | Understand billing, plan management, licensing | Looks at Pricing, Downloads, and will sign in to the portal. |
| **Affiliate partner** | Promote SelahCue, earn commissions, access marketing assets | Reaches Affiliate Program page → Affiliate Portal (separate surface, see `ADMIN-CONSOLE-HANDOFF.md`). |

### User Portal (Account)

| User | Goal | Notes |
|------|------|-------|
| **Church org admin** | Manage subscription plan (upgrade/downgrade/cancel), update payment method, view invoices | Primary portal user. One org admin per church. |
| **Device manager** | Activate/deactivate venue devices against the license key, monitor seat usage | May be same person as org admin or a dedicated tech lead. |
| **Bible entitlement manager** | View purchased/granted Bible translation entitlements, check download status | Copyrighted Bibles are download-on-entitlement, not bundled (**Verified** — `ADM-BR-005`, `FR-020`). |
| **Billing contact** | Download PDF invoices, update credit card, handle past-due states | May differ from org admin. |

---

## 3. Product Scope

### 3a. Marketing Website — In Scope

**16 designed pages** (**Verified** — all frames exist in Figma `468:124`):

| Page | Route | Purpose |
|------|-------|---------|
| Home | `/` | Long-scroll landing: hero → features → reliability → NDI showcase → pricing → testimonials → FAQ → CTA |
| Features | `/features` | 6 alternating deep-dive capability rows |
| Pricing | `/pricing` | 3 plan cards + monthly/annual toggle + full comparison table |
| Download | `/download` | Platform cards (Win/macOS), system requirements, mobile control, install guide |
| About | `/about` | "Why we built SelahCue" story + values grid |
| Contact | `/contact` | Message form + contact-method cards |
| Support | `/support` | Search + 6-category help grid + popular articles |
| Documentation | `/docs` | Sidebar nav + getting-started + topic grid |
| Changelog | `/changelog` | Versioned release cards (New / Improved / Fixed) |
| Blog | `/blog` | Featured post + article grid |
| Careers | `/careers` | Culture perks + open-roles list |
| Privacy Policy | `/privacy` | Legal prose (offline-first, minimal data) |
| Terms of Service | `/terms` | Legal prose (licence, subscription, disclaimers) |
| Sign In | `/signin` | Centered auth card (email/password + Google OAuth) |
| Account | `/account` | Signed-in dashboard: subscription, license, invoices |
| Affiliates | `/affiliates` | Public affiliate program landing |

**Shared elements** across all pages:
- **Navbar** — sticky, glassmorphism blur, brand lockup, route links (Features / Pricing / Download), Sign In, "Download free" CTA, mobile hamburger
- **Footer** — brand + Product / Resources / Company / Legal columns + Affiliates link

**Design system:**
- Dark-only theme matching the app (`bg/base #0e1116`) (**Verified**)
- SelahCue Color variable collection + Inter font (**Verified**)
- Design 2.0 palette tokens (`--sc-*`) (**Verified** — `DESIGN-TOKENS.md`)
- Real brand logo asset (`selahcue-logo.png`) (**Verified** — in the repo)

### 3b. User Portal — In Scope

The portal is the **only account-gated surface** (**Verified** — `MARKETING-SITE-HANDOFF.md` §5). The desktop app needs **no account**; sign-in exists solely to manage a paid plan.

**Portal sections:**

1. **Subscription & Billing**
   - Current plan display (Free / Pro / Church), billing cycle, next payment date
   - Change plan (upgrade/downgrade with proration)
   - Update payment method (card on file)
   - Cancel subscription (destructive — confirmation dialog naming the consequence, e.g. "Pro features end on 1 Sep 2026")
   - Past-due / payment-failed banner

2. **License & Devices**
   - Masked license key + Copy button
   - Device-activation meter ("2 of 5 devices activated")
   - Per-device list (name, platform, last active, app version) with Deactivate action
   - "Manage devices" view

3. **Bible Entitlements** (**Verified** — `ADM-FR-051`, `ADM-BR-006`)
   - View purchased/granted Bible translation entitlements
   - Download status per translation
   - Entitlement lifecycle states: Pending → Active → Expiring → Expired
   - Territory and offline-grace-period visibility

4. **Billing History**
   - Invoice table (date, amount, status: Paid/Pending/Failed, Download PDF)
   - Receipt download

5. **Account Settings**
   - Org name, primary contact, billing contact
   - Email and password management
   - Sign out

### 3c. Non-Goals (Explicit)

- **Light theme variant** — the site is dark-only, matching the app (**Verified** — `MARKETING-SITE-HANDOFF.md` §8)
- **Admin Console** — internal staff back-office is a separate surface (see `ADMIN-CONSOLE-HANDOFF.md`)
- **Affiliate Portal** — external affiliate dashboard is a separate surface (see `ADMIN-CONSOLE-HANDOFF.md`)
- **Desktop app account gating** — the app itself needs no account or sign-in (**Verified**)
- **Blog CMS / Docs CMS** — index pages ship as static placeholders; real content management is a follow-up
- **Real legal copy** — Privacy Policy and Terms are placeholder prose; a legal review is required before launch (**Assumed**)
- **Voice cloning or AI features on the marketing site** — marketing communicates these features but does not implement them
- **Payment processing implementation** — backend billing integration (Stripe, etc.) is a separate engineering workstream

---

## 4. Commercial Model (**Assumed** — Needs Product Sign-off)

| Tier | Monthly | Annual | Key Limits |
|------|---------|--------|------------|
| **Free** | $0 forever | — | Single output, bundled public-domain Bibles, basic features |
| **Pro** (most popular) | $19/mo | ~$15/mo (save 20%) | Multi-output, NDI, stage monitor, timers, priority support |
| **Church** | Custom | Custom | Unlimited campuses, enterprise deployment, custom SLA |

**Billing rules (Assumed):**
- Free tier is permanent, no credit card required
- Pro is monthly or annual; cancel anytime
- Annual billing is paid upfront with ~20% discount
- The app runs fully offline on Sunday even without an active subscription check — subscription validation is at activation/sync time, not at presentation time (**Verified** — offline-first architecture)

**Licensing framework (Verified):**
- **App License Key** controls software features and device seats — distinct from Bible entitlements (`ADM-BR-001`)
- Key lifecycle: `Draft → Issued → Activated → Expiring → Expired → Converted` (exceptional: `Revoked`, `Suspended`)
- Keys enforce concurrent device activation limits; devices transmit fingerprints during activation (`ADM-FR-022`)
- Full raw key shown only once upon generation; stored as secure hash, displayed masked (`ADM-FR-027`)

**Bible entitlements (Verified):**
- Only public-domain translations are bundled (WEB, ASV, BSB, BBE, Darby, Webster) — KJV excluded (UK Crown copyright) (`FR-025`)
- Copyrighted translations (NIV, ESV, NLT, etc.) are **never** in the installer (`CON-3`, `FR-020`)
- Copyrighted Bibles are downloaded post-activation into an encrypted local store only with a valid entitlement (`ADM-FR-051`)
- Revocation blocks new downloads and triggers background deletion (`ADM-FR-053`)

---

## 5. Marketing Copy Guidelines

### What to communicate (**Verified** product invariants)
- Never blanks the screen (NFR-024)
- Works fully offline — no internet required for core presentation
- Fast & bounded (≤3s cold start, capped memory)
- Desktop-authoritative architecture — mobile peers are untrusted
- AI assists but never gates core controls
- LAN control from paired phones, no cloud needed
- Public-domain Bibles included; copyrighted translations available with entitlement

### What NOT to claim
- Do NOT claim copyrighted Bibles are included unless entitled (`ADM-BR-010`)
- Do NOT suggest AI features work without operator confirmation (default mode requires operator approval for scripture detection) (**Verified**)
- Do NOT omit data egress disclosures for cloud AI features (`FR-132`, `FR-177`)
- Do NOT fabricate testimonial names or quotes — use "SelahCue Team" or real approved testimonials
- Pricing figures are **Assumed** placeholders — need product/marketing sign-off

---

## 6. Key User Journeys

### Journey 1: First Visit → Download
1. Land on Home page (organic search, referral, or ad)
2. Scan hero + feature cards → understand value proposition
3. Review pricing → see "Free to start" messaging
4. Click "Download free" CTA → land on Download page
5. Choose platform (Windows / macOS) → download installer
6. Follow 3-step install guide

### Journey 2: Free User → Paid Upgrade
1. Use the free app; hit a feature limit (e.g., multi-output)
2. See upgrade prompt in-app → link to `/pricing`
3. Compare Free vs Pro vs Church
4. Toggle Annual to see 20% savings
5. Click "Start free trial" → redirected to Sign In / Create Account
6. Complete checkout → receive license key
7. Activate license in app

### Journey 3: Account Management (Paid User)
1. Sign in at `/signin` (email/password or Google OAuth)
2. Land on Account dashboard
3. View subscription status, license key, device activations
4. Can: Change plan, Update payment, Deactivate devices, Download invoices, Cancel

### Journey 4: Affiliate Discovery
1. Discover "Affiliates" link in footer
2. Land on `/affiliates` → see "20% recurring commission" pitch
3. Click "Apply now" → redirected to Affiliate Portal apply form (separate surface)

---

## 7. Technical Architecture

### Frontend Stack (**Verified** — implemented)
- **Vue 3** + TypeScript + Vite (project bootstrapped in `marketing/`)
- **Vue Router** with all 16 routes configured
- **Vanilla CSS** with SelahCue design tokens (`--sc-*` variables)
- **Inter** font from Google Fonts
- Responsive: 1440px (designed) / 768–1199px (tablet) / <768px (mobile)

### Reusable Component Library (**Verified** — built)
| Component | Purpose |
|-----------|---------|
| `Navbar` | Sticky nav with glassmorphism, mobile hamburger |
| `Footer` | 4-column responsive footer |
| `UiButton` | Multi-variant (primary/secondary/ghost/gradient/outline) |
| `UiBadge` | Status pills (LIVE/PREVIEW/READY/NDI/FEATURED) |
| `FeatureCard` | Capability cards with hover glow |
| `ReliabilityPillar` | Product invariant cards |
| `ConsoleMockup` | Interactive operator console simulation |
| `PricingCard` | Plan tier cards with annual/monthly toggle |
| `TestimonialCard` | Quote cards with star ratings |
| `FaqAccordion` | Accessible disclosure accordion |

### Backend Requirements (Not Yet Built — **Assumed**)
- **Auth:** Email/password + Google OAuth (Firebase Auth or similar)
- **Billing:** Stripe integration for subscriptions, invoices, payment methods
- **License API:** Key generation, activation, device management, entitlement checks
- **Bible Entitlement API:** Catalogue, grants, download tokens, revocation
- **Analytics:** Privacy-respecting event tracking (no sermon/transcript data)

### Deployment (**Unknown** — needs decision)
- Static marketing pages can deploy via any CDN (Vercel, Netlify, Firebase Hosting)
- Account portal requires server-side API routes or a backend service
- Consider: Firebase App Hosting for the Vue 3 app + Cloud Functions for APIs

---

## 8. Security, Privacy & Compliance

| Requirement | Source | Status |
|-------------|--------|--------|
| NDPA 2023 + GDPR compliance | `FR-132`, `NFR-018` | **Verified** (PRD requirement) |
| Sermon transcripts/audio are local-only by default | `FR-132` | **Verified** |
| Cloud data egress is opt-in with visible disclosure | `FR-133`, `FR-177` | **Verified** |
| Append-only audit logs for sensitive operations | `FR-150`, `ADM-FR-070` | **Verified** (PRD requirement) |
| WCAG 2.1 AA contrast (≥4.5:1 text, ≥3:1 UI) | `NFR-020` | **Verified** |
| Portal forms need CSRF, rate limiting, input sanitization | — | **Inferred** |
| Sign-in needs wrong-credentials + rate-limited states | `MARKETING-SITE-HANDOFF.md` §5 | **Verified** (spec'd but not built) |
| Cancel/Deactivate are destructive → confirmation dialogs | `MARKETING-SITE-HANDOFF.md` §5 | **Verified** (spec'd but not built) |
| License keys displayed masked (shown once, stored as hash) | `ADM-FR-027`, `ADM-BR-004` | **Verified** |
| Impersonation requires banner + audit trail | `ADM-FR-060` | **Verified** (admin-only) |
| Bible copyright attributions displayed per entitlement | `FR-034`, `ADM-FR-042` | **Verified** |
| No copyleft (GPL/AGPL) dependencies in frontend | `NFR-027` | **Verified** |

---

## 9. Accessibility

- WCAG 2.1 AA throughout (**Verified** — PRD requirement)
- One `<h1>` per page with proper heading hierarchy
- Semantic HTML (`<nav>`, `<main>`, `<section>`, `<table>`)
- All interactive elements: visible `:focus-visible` ring (`accent/brand`)
- FAQ accordion: `aria-expanded`, Enter/Space toggle
- Nav links and mobile CTAs ≥ 44px touch targets
- `prefers-reduced-motion` respected (no parallax/auto-animation)
- Status conveyed by text labels, not colour alone (WCAG 1.4.1)
- `text/muted` (#9aa4b2 / #6b7383) restricted to tertiary/label-only (AA-large only) (**Verified** — `DESIGN-TOKENS.md`)

---

## 10. Assumptions & Open Questions

### Assumptions (Need Product Sign-off)
1. Pricing tiers and figures ($0 / $19 / Custom) are placeholders
2. Testimonial quotes are placeholder — need real customer approval or removal
3. Blog/Docs/Changelog content is placeholder — need CMS decision
4. Legal pages (Privacy/Terms) need a real legal review
5. Affiliate commission model (20% recurring, 60-day attribution, $50 min payout) is placeholder
6. Trial period duration (if any) for Pro tier is undefined

### Open Questions
1. **Checkout flow:** Will we use Stripe Checkout (hosted) or build a custom checkout in the portal?
2. **Auth provider:** Firebase Auth, Auth0, or custom?
3. **Deployment:** Firebase Hosting, Vercel, Netlify, or self-hosted?
4. **Blog/Docs CMS:** Static markdown, headless CMS (Contentful, Sanity), or custom?
5. **Mobile app distribution:** Will iOS/Android app store pages link from the Download page?
6. **Demo video:** "Watch 2-min demo" CTA needs a real video asset
7. **Analytics:** What events to track? PostHog, Plausible, or GA4?

---

## 11. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Placeholder pricing published before sign-off | Customer confusion, billing disputes | Gate launch behind product approval on pricing |
| Copyrighted Bible claims on marketing copy | Legal liability (publisher agreements) | Strict copy review per `ADM-BR-010` |
| No backend for account portal | Portal is non-functional | Prioritize billing/license API before portal launch |
| Legal pages not reviewed | Compliance risk | Block public launch until legal review |
| Testimonials fabricated | Trust damage | Use "SelahCue Team" or get real approvals |
| Missing form states (validation, error, loading) | Poor UX on sign-in/contact forms | Spec all states before build (per `MARKETING-SITE-HANDOFF.md` §5) |

---

## 12. Recommended Next Steps

1. **Product sign-off** on pricing tiers, billing terms, and trial structure
2. **Auth + billing backend** — choose provider (Firebase Auth + Stripe recommended)
3. **Form states** — spec validation/error/loading/success for Sign In, Contact, and Account forms
4. **Real content** — approved testimonials, blog posts, docs articles, changelog entries
5. **Legal review** — Privacy Policy and Terms of Service
6. **Demo video** — produce a 2-minute product walkthrough
7. **Deployment pipeline** — CI/CD for the `marketing/` Vue 3 app
8. **SEO + analytics** — meta tags (done), structured data, sitemap, robots.txt, analytics integration
