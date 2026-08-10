# SelahCue — Marketing & User Portal · UX Gap-Fill Handoff

**Deliverable:** Design specifications for all gaps identified between the Product Brief and the existing Figma designs.  
**Parent Brief:** `product/MARKETING-AND-USER-PORTAL-BRIEF.md`  
**Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ` → page **"Marketing Website"** (id `468:124`)  
**Design System:** reuses `SelahCue Color` variables + **Inter** + Design 2.0 `--sc-*` tokens.  
**Status:** Specification — ready for implementation; Figma frames to be added.

> **Fact labelling.** Design decisions below are **Inferred** from the existing design language, component patterns, and the product brief unless labelled otherwise. All placeholder copy must be product-approved before launch.

---

## Table of Contents

1. [Gap Summary](#1-gap-summary)
2. [Bible Entitlements — Account Portal (NEW)](#2-bible-entitlements--account-portal-new)
3. [Sign In — Full State Matrix](#3-sign-in--full-state-matrix)
4. [Create Account (NEW)](#4-create-account-new)
5. [Forgot Password (NEW)](#5-forgot-password-new)
6. [Contact Form — Full State Matrix](#6-contact-form--full-state-matrix)
7. [Account Portal — Destructive Dialogs & Missing States](#7-account-portal--destructive-dialogs--missing-states)
8. [Responsive Breakpoint Specifications](#8-responsive-breakpoint-specifications)
9. [Detail Page Templates (NEW)](#9-detail-page-templates-new)
10. [Component Additions & Amendments](#10-component-additions--amendments)

---

## 1. Gap Summary

| Gap ID | Surface | Severity | Gap Description |
|--------|---------|----------|-----------------|
| **GAP-01** | Account Portal | **Critical** | Bible Entitlements section entirely missing from `506:124` |
| **GAP-02** | Sign In | **High** | Only default state drawn; 7 additional states needed |
| **GAP-03** | Auth Flow | **High** | Create Account screen missing |
| **GAP-04** | Auth Flow | **High** | Forgot Password flow missing |
| **GAP-05** | Contact | **Medium** | Form states (validation, submitting, success, error) missing |
| **GAP-06** | Account Portal | **High** | Destructive confirmation dialogs, empty states, banners missing |
| **GAP-07** | All Pages | **Medium** | Zero mobile/tablet Figma frames exist |
| **GAP-08** | Blog/Docs/Support | **Low** | Detail page templates missing (index pages only) |

---

## 2. Bible Entitlements — Account Portal (NEW)

**Location:** New card section on `506:124` (Account Dashboard), positioned between "License & Devices" and "Billing History."

### 2a. Section Layout

The Bible Entitlements card follows the same layout pattern as the existing Subscription and License cards on the Account dashboard:
- Card surface: `--sc-surface` (#14161d), 1px `--sc-border` border, 16px radius
- Card header: Semi Bold 18px title "Bible Translations" + secondary text "Manage your scripture entitlements"
- Card body: entitlements list

### 2b. Entitlement Row

Each entitled translation is a row within the card:

```
┌─────────────────────────────────────────────────────────────┐
│  📖  New International Version (NIV)                        │
│      English · Biblica, Inc.                                │
│      ┌──────────┐                                           │
│      │ ● Active  │   Expires: 1 Sep 2027                    │
│      └──────────┘                                           │
│      Downloaded · 42 MB · Last synced 2 Aug 2026            │
│                                          [Re-download]      │
└─────────────────────────────────────────────────────────────┘
```

**Row fields:**
- **Icon:** 📖 book emoji or a small Bible icon in `--sc-gold` (#f2b84b)
- **Title:** Translation name (e.g. "New International Version (NIV)") — Semi Bold 15px, `--sc-text`
- **Subtitle:** Language · Rights holder — 14px, `--sc-text-secondary`
- **Status badge** (using `UiBadge` pattern):
  - `Active` → `--sc-preview` text on `--sc-preview-soft` bg
  - `Pending` → `--sc-warn` text on `--sc-warn-soft` bg
  - `Expiring` → `--sc-warn` text on `--sc-warn-soft` bg, with "Expires: {date}" beside it
  - `Expired` → `--sc-live` text on `--sc-live-soft` bg
  - `Territory Blocked` → `--sc-text-muted` text on `--sc-elevated` bg
- **Download status line:** 13px, `--sc-text-muted`
  - "Downloaded · {size} · Last synced {date}" (green dot)
  - "Not downloaded" (grey dot)
  - "Downloading… {pct}%" (progress indicator, same style as Download Modal `398:124`)
- **Action:** "Re-download" ghost text button, right-aligned. For expired: disabled greyed out.

### 2c. Bundled Translations Section

Below the entitled rows, a separator + section for bundled public-domain translations:

```
──── Included with SelahCue ──────────────────────────────────

  📖  World English Bible (WEB)          ● Installed
  📖  American Standard Version (ASV)     ● Installed
  📖  Berean Standard Bible (BSB)         ● Installed
  📖  Bible in Basic English (BBE)        ● Installed
  📖  Darby Translation                   ● Installed
  📖  Webster Bible                       ● Installed
```

- Bundled translations show as a compact list (no action buttons — always available)
- Status: "Installed" in `--sc-text-muted`, green dot (`--sc-preview`)

### 2d. States

| State | Visual | Notes |
|-------|--------|-------|
| **Default (populated)** | As described above with entitled + bundled translations | Primary state |
| **No entitlements** | Bundled section only + a prompt: "Upgrade to Pro to access licensed translations like NIV, ESV, and NLT." + "View plans" secondary button | Free-tier users see this |
| **Loading** | Skeleton rows (3 rows of `--sc-elevated` shimmer blocks, matching row height) | While entitlement API loads |
| **Error** | Icon `⚠` + "Couldn't load your entitlements. Check your connection." + "Retry" primary button | API failure |
| **Entitlement expiring** | Amber banner at card top: "⚠ Your NIV entitlement expires on 1 Sep 2026. [Renew now]" | 30 days before expiry |
| **Entitlement expired** | Row badge changes to red "Expired"; download status shows "Access revoked · Data will be removed" | Post-expiry state |
| **Downloading** | Row shows inline progress bar (same token style as Download Modal `398:124`) | In-progress download |
| **Territory blocked** | Row badge "Territory Blocked"; tooltip: "This translation is not available in your region." | Per catalogue constraints |

### 2e. Accessibility

- Each entitlement row is a `<div role="article">` or `<li>` within a `<ul>`
- Status badges include `aria-label` (e.g. "Status: Active, expires September 1, 2027")
- Re-download button has `aria-label="Re-download New International Version"` for context
- Progress bar uses `role="progressbar"` with `aria-valuemin/max/now`
- Expiring/expired banner uses `role="alert"` for screen reader announcement
- All text meets WCAG AA (4.5:1) on `--sc-surface`

---

## 3. Sign In — Full State Matrix

**Location:** Existing frame `505:124`. Spec all states for implementation.

### 3a. Field States

Each form field (Email, Password) cycles through:

| State | Visual | Token Usage |
|-------|--------|-------------|
| **Empty (default)** | As designed — `--sc-elevated` bg, `--sc-border` border, placeholder text in `--sc-text-muted` | As drawn |
| **Focus** | 2px `--sc-primary` ring (#6e5cf0), 2px offset from field edge. Label animates to top-left if using floating labels. | `outline: 2px solid var(--sc-primary); outline-offset: 2px;` |
| **Filled** | Field bg stays `--sc-elevated`; typed text in `--sc-text`. Password shows dots with show/hide toggle (eye icon). | Standard input |
| **Validation error** | Border changes to `--sc-live` (#ff4d4d); inline error message below field in `--sc-live`, 13px. Icon `⚠` before message. | `border-color: var(--sc-live);` |
| **Disabled** | 50% opacity, `cursor: not-allowed` | `opacity: 0.5;` |

### 3b. Page-Level States

| State | Layout | Content | Buttons |
|-------|--------|---------|---------|
| **Default** | As drawn — centered card | Email field + Password field (with "Forgot?" link) + "Sign in" primary btn + divider "or" + "Continue with Google" secondary btn + "Create an account" link | All enabled |
| **Submitting** | Same layout | Both fields disabled. "Sign in" button shows spinner + "Signing in…" text, disabled. Google button disabled. | All disabled |
| **Wrong credentials** | Same layout | Red banner at card top: `⚠ Invalid email or password. Please try again.` (`role="alert"`, `--sc-live` bg soft). Email field keeps value, Password cleared. Focus returns to Password. | All enabled |
| **Rate limited** | Same layout | Red banner: `⚠ Too many attempts. Please wait {n} seconds before trying again.` Countdown timer visible. All fields and buttons disabled until timer expires. | All disabled until timer expires |
| **Server error** | Same layout | Red banner: `⚠ Something went wrong. Please try again later.` + "Retry" primary button. | Retry enabled |
| **Google OAuth redirect** | Same layout | Google button shows spinner + "Redirecting…". Other fields disabled. | Google button loading |
| **Google OAuth error** | Same layout | Red banner: `⚠ Google sign-in failed. Please try again or use email.` | All enabled |
| **Success** | Brief flash | Green banner: `✓ Signed in successfully.` → redirect to `/account` (300ms delay) | N/A (redirecting) |

### 3c. Validation Rules (inline, per-field)

| Field | Validation | Error Message |
|-------|-----------|---------------|
| Email | Empty | "Email is required" |
| Email | Invalid format | "Please enter a valid email address" |
| Password | Empty | "Password is required" |
| Password | Too short (<8 chars) | "Password must be at least 8 characters" |

### 3d. Accessibility

- Form uses `<form>` element with `aria-label="Sign in"`
- Error banner: `role="alert"` + `aria-live="assertive"` for immediate announcement
- Field errors: `aria-invalid="true"` + `aria-describedby="email-error"` pointing to the error message `<span>`
- "Forgot?" link: `aria-label="Forgot your password?"` (full context for screen readers)
- Focus order: Email → Password → Forgot → Sign in → Google → Create account
- Focus-visible ring on all interactive elements (`2px var(--sc-primary)`)
- Google button: `aria-label="Continue with Google"` (not just the Google icon)

---

## 4. Create Account (NEW)

**Location:** New frame, same layout pattern as Sign In (`505:124`). Centered card on 1440×900.

### 4a. Layout

Same centered card as Sign In, with:
- Brand lockup (logo + "SelahCue" wordmark) at top
- **Heading:** "Create your account" — Bold 22px, `--sc-text`
- **Subheading:** "Start managing your SelahCue plan." — 15px, `--sc-text-secondary`
- **Fields:**
  - Church / Organization name (text input)
  - Email (email input)
  - Password (password input with show/hide toggle + strength indicator)
  - Confirm password (password input)
- **Checkbox:** "I agree to the [Terms of Service] and [Privacy Policy]" — links in `--sc-primary`
- **Button:** "Create account" — primary gradient button, full-width
- **Divider:** "or" in `--sc-text-muted`
- **Button:** "Continue with Google" — secondary button with Google icon
- **Footer link:** "Already have an account? [Sign in]" — `--sc-text-muted` + `--sc-primary` link

### 4b. Password Strength Indicator

Below the password field, a 4-segment strength bar:
- **Weak:** 1 segment filled `--sc-live` (#ff4d4d), label "Weak"
- **Fair:** 2 segments filled `--sc-warn` (#f5a524), label "Fair"
- **Good:** 3 segments filled `--sc-gold` (#f2b84b), label "Good"
- **Strong:** 4 segments filled `--sc-preview` (#35c08a), label "Strong"

Each segment is 8px tall, `--sc-border` bg when unfilled, 4px gap between, 999px radius.

### 4c. States

| State | Content |
|-------|---------|
| **Default** | Empty form, all fields enabled |
| **Validation errors** | Per-field inline errors (same style as Sign In §3a) |
| **Terms unchecked** | "Create account" button disabled (50% opacity) until checkbox checked |
| **Submitting** | Spinner on button, all fields disabled |
| **Email taken** | Inline error on email: "An account with this email already exists. [Sign in instead]" |
| **Server error** | Red banner at top |
| **Success** | Green banner "✓ Account created! Redirecting…" → redirect to `/account` |

### 4d. Validation Rules

| Field | Validation | Error Message |
|-------|-----------|---------------|
| Org name | Empty | "Organization name is required" |
| Org name | >100 chars | "Organization name is too long" |
| Email | Empty | "Email is required" |
| Email | Invalid format | "Please enter a valid email address" |
| Password | Empty | "Password is required" |
| Password | <8 chars | "Password must be at least 8 characters" |
| Password | No uppercase + number | "Include at least one uppercase letter and one number" |
| Confirm password | Mismatch | "Passwords do not match" |
| Terms | Unchecked | Button stays disabled (no inline error) |

---

## 5. Forgot Password (NEW)

**Location:** New frame, same centered card pattern. Smaller card (fewer fields).

### 5a. Step 1: Request Reset

- **Heading:** "Reset your password" — Bold 22px
- **Subheading:** "Enter your email and we'll send you a reset link." — 15px, `--sc-text-secondary`
- **Field:** Email input
- **Button:** "Send reset link" — primary button
- **Footer:** "Back to [Sign in]"

### 5b. Step 2: Email Sent (Success)

- **Icon:** ✉ mail icon in `--sc-primary`, 48px
- **Heading:** "Check your inbox" — Bold 22px
- **Body:** "We sent a password reset link to **{email}**. It expires in 15 minutes." — 15px
- **Secondary text:** "Didn't receive it? Check your spam folder or [resend]."
- **Button:** "Back to Sign in" — secondary button

### 5c. States

| State | Content |
|-------|---------|
| **Default** | Empty email field |
| **Validation error** | Inline: "Please enter a valid email address" |
| **Submitting** | Spinner on button, field disabled |
| **Email not found** | Inline: "We couldn't find an account with this email. [Create one]" |
| **Rate limited** | Banner: "Too many requests. Please wait before trying again." |
| **Success** | Transitions to Step 2 (Email Sent) |
| **Resend** | "Resend" link triggers submitting state → success toast "Link resent" |

---

## 6. Contact Form — Full State Matrix

**Location:** Existing frame `497:124`. Only default is drawn.

### 6a. Form Fields

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| Name | text | Yes | Non-empty, max 100 chars |
| Email | email | Yes | Valid email format |
| Church / Organization | text | No | Max 100 chars |
| Message | textarea | Yes | Non-empty, max 2000 chars (show remaining) |

### 6b. States

| State | Visual | Notes |
|-------|--------|-------|
| **Default** | As drawn — all fields empty, placeholder text | |
| **Field focus** | 2px `--sc-primary` ring on active field | Same pattern as Sign In |
| **Field filled** | Text in `--sc-text`, placeholder hidden | |
| **Inline validation** | `--sc-live` border + error below field | On blur or on submit |
| **Character count** | Below textarea: "{remaining}/2000 characters remaining" in `--sc-text-muted` | Turns `--sc-live` at 0 |
| **Submitting** | "Send message" button shows spinner + "Sending…"; all fields disabled | |
| **Success** | Form replaced by success card: ✓ icon (`--sc-preview`), heading "Message sent!", body "We'll get back to you within 1–2 business days.", "Send another" ghost link | Card replaces form |
| **Server error** | Red banner above form: "⚠ Something went wrong. Please try again." | Form retains entered values |
| **Network error** | Red banner: "⚠ Couldn't reach the server. Check your connection." + "Retry" button | Form retains values |

### 6c. Accessibility

- `<form>` with `aria-label="Contact us"`
- Required fields: `aria-required="true"`
- Errors: `aria-invalid="true"` + `aria-describedby`
- Success: `aria-live="polite"` region announces "Your message has been sent"
- Textarea: `aria-label="Your message"` + character count as `aria-describedby`

---

## 7. Account Portal — Destructive Dialogs & Missing States

### 7a. Cancel Subscription Dialog

Reuse the Admin Console destructive-action pattern (`525:124`).

```
┌───────────────────────────────────────────┐
│                 ⚠                          │
│  Cancel your Pro subscription?             │
│                                            │
│  Your Pro features will remain active      │
│  until 1 Sep 2026. After that:             │
│                                            │
│  • Multi-output will be disabled           │
│  • NDI streaming will stop                 │
│  • Stage monitor will be unavailable       │
│  • You'll keep your Free features          │
│                                            │
│  Type "cancel" to confirm:                 │
│  ┌─────────────────────────────────┐       │
│  │                                 │       │
│  └─────────────────────────────────┘       │
│                                            │
│  [Keep my plan]  ██ Cancel subscription ██ │
│                                            │
└───────────────────────────────────────────┘
```

- **Scrim:** `--sc-base` at 72% opacity (matching Download Modal)
- **Card:** `--sc-surface`, 16px radius, max-width 420px centered
- **Warning icon:** `⚠` in `--sc-warn` (#f5a524), 40px
- **Title:** Bold 18px, `--sc-text`
- **Body:** 15px, `--sc-text-secondary` — names the concrete consequence with the exact date
- **Bullet list:** Feature losses in `--sc-text-secondary`
- **Type-to-confirm:** Input field; destructive button stays disabled until "cancel" is typed exactly
- **Buttons:**
  - "Keep my plan" — ghost button (safe action, **receives initial focus**)
  - "Cancel subscription" — `--sc-live` bg (#ff4d4d), white text, disabled until confirmed
- **A11y:** `role="alertdialog"`, `aria-modal="true"`, focus trap, `Esc` = "Keep my plan" (safe action)

### 7b. Deactivate Device Dialog

Same pattern, lighter:

- **Title:** "Deactivate this device?"
- **Body:** "**{Device Name}** ({Platform}) will lose access to Pro features. You can reactivate it later if you have available seats."
- **No type-to-confirm** (lower severity than cancellation)
- **Buttons:** "Keep active" (ghost, initial focus) + "Deactivate" (`--sc-live` bg)

### 7c. Copy Key Success Toast

When user clicks "Copy" on the license key:

- Toast appears at bottom-center, `--sc-surface` bg, `--sc-border` border, 12px radius
- Content: `✓ License key copied to clipboard` — 14px, `--sc-text`
- ✓ icon in `--sc-preview`
- Auto-dismiss after 3 seconds, slide-up entry animation
- `aria-live="polite"` region

### 7d. Past-Due / Payment Failed Banner

Persistent banner at top of Account dashboard (below header, above cards):

- Full-width, `--sc-live-soft` (#2a1416) bg, 1px `--sc-live-border` (#5a2327) border
- Left: `⚠` icon in `--sc-live`
- Body: "Your payment failed on {date}. Update your payment method to keep Pro features." — 14px
- Right: "Update payment" primary button (small)
- Not dismissible (persists until resolved)
- `role="alert"` for screen reader announcement

### 7e. Free-Tier Account View

When the signed-in user is on the Free plan, the Account dashboard adapts:

| Card | Free-Tier Content |
|------|-------------------|
| **Subscription** | Plan: "Free", "Upgrade to Pro to unlock multi-output, NDI, stage monitor, and more." + "View plans" primary button. No billing cycle, no payment method. |
| **License** | Key shown (free key), device meter ("1 of 1 device activated"), single device row. |
| **Bible Entitlements** | Bundled translations only. Prompt: "Upgrade to access licensed translations." |
| **Billing History** | Empty: "No invoices yet." + muted icon. No table. |

### 7f. Loading Skeleton

All Account dashboard cards show skeleton loading on initial load:

- Each card shows 3 rows of shimmer blocks:
  - Title-width block (40% width, 16px height)
  - Full-width block (100%, 12px height)
  - Half-width block (50%, 12px height)
- Shimmer: `--sc-elevated` bg with a subtle left-to-right gradient sweep animation
- `prefers-reduced-motion`: static `--sc-elevated` blocks, no animation
- Skeleton replaces for 0–2 seconds while API loads

---

## 8. Responsive Breakpoint Specifications

All pages share these rules. No Figma frames exist yet — this spec defines the behaviour for implementation.

### 8a. Global Breakpoints

| Breakpoint | Width | Gutters | H1 Size | Grid Columns |
|------------|-------|---------|---------|--------------|
| **Desktop** (designed) | ≥1200px | 96px | 60px/64px | As designed |
| **Tablet** | 768px – 1199px | 48px | 48px/52px | 2-up grids |
| **Mobile** | <768px | 20px | 36px/40px | 1-up stacked |

### 8b. Navbar Responsive

- **Desktop:** Full horizontal links + CTA
- **Tablet:** Same, but tighter spacing; CTA shrinks to icon-only if needed
- **Mobile:** Logo + hamburger icon (☰). Tap opens a full-height slide-out sheet from right:
  - `--sc-surface` bg, full viewport height
  - Links stacked vertically, 56px row height (≥44px touch target)
  - "Download free" CTA at bottom, full-width gradient button
  - Close button (✕) top-right
  - Scrim behind the sheet, tap-to-close
  - `aria-expanded` on hamburger; focus trap in open sheet

### 8c. Footer Responsive

- **Desktop:** 4 columns side-by-side
- **Tablet:** 2×2 grid
- **Mobile:** All columns stack vertically; each column is a collapsible section (tap heading to expand)

### 8d. Page-Specific Rules

| Page | Tablet (768–1199px) | Mobile (<768px) |
|------|---------------------|------------------|
| **Home: Feature grid** | 2-up grid | 1-up stacked |
| **Home: Reliability pillars** | 2-up (third wraps) | 1-up stacked |
| **Home: Pricing cards** | 1-up (Pro card first/prominent) | 1-up stacked, Pro first |
| **Home: Testimonials** | 2-up | 1-up stacked |
| **Home: Steps** | 2-up (third wraps) | 1-up stacked |
| **Home: Outputs showcase** | Image below text | Image below text, full-width |
| **Home: Hero** | Mock scales to container width | Mock full-width, CTAs stack |
| **Pricing: Comparison table** | Horizontal scroll within container | Horizontal scroll, sticky first column |
| **Download: Platform cards** | 2-up side-by-side | 1-up stacked |
| **Account: Cards** | 1-up stacked (no sidebar) | 1-up stacked, full-width |
| **Sign In / Create Account** | Card max-width 480px, centered | Card fills 92vw |

### 8e. Responsive CSS Pattern

```css
/* Use CSS Grid auto-fill for feature grids */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--grid-gap);
}

/* Pricing cards: flex-wrap for natural reflow */
.pricing-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--grid-gap);
}
.pricing-card {
  flex: 1 1 320px;
  min-width: 280px;
}

/* Tables: horizontal scroll, never break page */
.table-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
```

---

## 9. Detail Page Templates (NEW)

### 9a. Blog Post Detail

- **Route:** `/blog/:slug`
- **Layout:** Single column, max-width 720px centered
- **Header:** Category badge (UiBadge) + H1 title + author line ("SelahCue Team · 8 Aug 2026 · 5 min read") + hero image (full-width, 16:9, 16px radius)
- **Body:** Styled markdown prose (H2, H3, paragraphs, lists, code blocks, blockquotes, images)
- **Sidebar** (desktop only, right rail): Table of contents (sticky) + "Related articles" (3 small cards)
- **Footer:** Author card + "Share" buttons (copy link, Twitter/X) + "Next/Previous" article navigation

### 9b. Documentation Article Detail

- **Route:** `/docs/:category/:slug`
- **Layout:** 2-column — sticky sidebar nav (left, 280px) + content (right)
- **Sidebar:** Collapsible category tree (same as Docs index). Active article highlighted.
- **Content:** Styled markdown with anchor heading links, copy-to-clipboard code blocks, info/warning/tip callout boxes (using `--sc-info-soft`, `--sc-warn-soft`, `--sc-preview-soft` backgrounds)
- **Breadcrumb:** "Docs > {Category} > {Article Title}"
- **Footer:** "Was this helpful?" thumbs up/down + "Edit on GitHub" link

### 9c. Support Article Detail

- **Route:** `/support/:category/:slug`
- **Layout:** Single column, max-width 720px
- **Content:** Styled markdown similar to docs
- **Footer:** "Still stuck?" → Contact support CTA

---

## 10. Component Additions & Amendments

### 10a. New Component: FormField.vue

A reusable form field wrapper handling all label, input, error, and hint states:

**Props:**
- `label`: string
- `type`: 'text' | 'email' | 'password' | 'textarea'
- `placeholder`: string
- `required`: boolean
- `error`: string (empty = no error)
- `hint`: string (helper text below field)
- `disabled`: boolean
- `maxLength`: number (for textarea character count)
- `showPasswordToggle`: boolean (for password fields)

**Visual:**
- Label: 14px Semi Bold, `--sc-text`, above field
- Input: `--sc-elevated` bg, `--sc-border` 1px border, 12px radius, 14px padding, 15px `--sc-text` value
- Focus: 2px `--sc-primary` outline
- Error: `--sc-live` border + error text (13px `--sc-live`) below, `⚠` icon
- Hint: 13px `--sc-text-muted` below field (hidden when error shows)
- Textarea: min-height 120px, resize vertical
- Password toggle: eye/eye-off icon inside field, right side, `--sc-text-muted`

### 10b. New Component: ConfirmDialog.vue

Reusable destructive confirmation dialog (matches Admin pattern `525:124`):

**Props:**
- `title`: string
- `description`: string
- `consequences`: string[] (bullet list)
- `confirmLabel`: string ("Cancel subscription", "Deactivate")
- `cancelLabel`: string ("Keep my plan", "Keep active")
- `requireType`: string | null (type-to-confirm value, null = no confirmation)
- `variant`: 'danger' | 'warning'

**Slots:**
- `default` — additional body content

### 10c. New Component: Toast.vue

Floating notification toast:

**Props:**
- `message`: string
- `variant`: 'success' | 'error' | 'info'
- `duration`: number (ms, default 3000, 0 = persistent)

**Visual:**
- Fixed bottom-center, 16px from viewport bottom
- `--sc-surface` bg, `--sc-border` border, 12px radius, shadow
- Icon + message text, 14px
- Slide-up entry, fade-out exit (CSS animation)
- `aria-live="polite"`

### 10d. New Component: SkeletonLoader.vue

Shimmer loading placeholder:

**Props:**
- `lines`: number (rows of skeleton blocks)
- `widths`: number[] (percentage widths per line, e.g. [40, 100, 50])

**Visual:**
- `--sc-elevated` bg blocks with gradient sweep animation
- `prefers-reduced-motion`: static blocks, no animation
- `aria-hidden="true"` + parent `aria-busy="true"`

### 10e. Amendment: UiBadge.vue

Add new variants to support entitlement and account states:

| New Variant | Text Color | Background | Border |
|-------------|-----------|------------|--------|
| `expired` | `--sc-live` | `--sc-live-soft` | `--sc-live-border` |
| `expiring` | `--sc-warn` | `--sc-warn-soft` | `--sc-warn-border` |
| `pending` | `--sc-warn` | `--sc-warn-soft` | `--sc-warn-border` |
| `active` | `--sc-preview` | `--sc-preview-soft` | `--sc-preview-border` |
| `blocked` | `--sc-text-muted` | `--sc-elevated` | `--sc-border` |
| `accent` | `--sc-primary` | `--sc-accent-soft` | — |

---

## 11. Implementation Priority

| Priority | Gap | Effort | Dependency |
|----------|-----|--------|------------|
| **P0** | Bible Entitlements (§2) | Medium | Backend entitlement API |
| **P0** | Sign In states (§3) | Medium | Auth provider selection |
| **P0** | Create Account (§4) | Medium | Auth provider selection |
| **P1** | Account destructive dialogs (§7a–b) | Low | Backend cancel/deactivate APIs |
| **P1** | Forgot Password (§5) | Low | Auth provider selection |
| **P1** | Contact form states (§6) | Low | Form submission backend |
| **P1** | Account banner/skeleton/empty (§7c–f) | Low | Billing API |
| **P2** | Responsive breakpoints (§8) | Medium | CSS only, no API |
| **P2** | New components (§10) | Medium | Used by P0/P1 items |
| **P3** | Detail page templates (§9) | Low | CMS decision |

---

## 12. Assumptions & Follow-ups

> [!WARNING]
> **All pricing figures, subscription terms, and Bible entitlement states are placeholder assumptions.** Product must sign off before implementation.

- **Assumed:** The Account portal sign-in redirects to `/account`; there is no separate create-account-then-verify-email flow yet
- **Assumed:** Type-to-confirm is used only for Cancel Subscription (highest severity); lower-severity destructive actions use a simple confirm
- **Assumed:** Free-tier users can sign in and see a minimal account dashboard (not blocked from portal access)
- **Follow-up:** Mobile/tablet Figma frames should be created for Sign In, Account, and Download as highest priority
- **Follow-up:** Detail page templates (Blog, Docs, Support articles) depend on CMS decision
- **Next role:** frontend-engineer to implement gap-fill components and states; backend-engineer for auth + billing + entitlement APIs
