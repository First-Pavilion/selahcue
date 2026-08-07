# SelahCue — Admin Console & Affiliate Program · Design Handoff

**Deliverable:** internal **Admin Console** (SelahCue staff manage customers, users & the affiliate program) plus the external **Affiliate Portal** (affiliates manage their own account). Both are separate audiences from the marketing site / customer Account portal.

**Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ`.
- Page **"Admin Console"** (`518:124`) — internal back-office (staff only).
- Page **"Affiliate Portal"** (`526:124`) — external affiliate-facing dashboard.

**Design system:** reuses the file's local **"SelahCue Color"** variable collection and **Inter** throughout, matching the marketing site and the operator app (dark, `bg/base` #0e1116 canvas). Every frame is desktop 1440-wide.

> **Fact labelling.** The information architecture, permissions model, and flows are **design proposals**. All data shown — customer/affiliate names, emails, revenue, MRR, license keys, commissions, invoices, KPI numbers, changelog/dates — is **placeholder** and must be replaced with real data + approved by product before build. There is no admin/affiliate backend yet; this is a UX spec, not an implemented surface.

---

## 1. Information architecture

### 1a. Admin Console (page `518:124`)

Shared **shell** on every frame: a left **sidebar** (brand + `ADMIN` badge · Overview / Customers / Users / Affiliates / Subscriptions / Licenses / Support / Settings · staff profile pinned bottom) and a **top bar** (page title · global search · notifications). Current route is highlighted (`bg/elevated` pill + `accent/brand` text/icon).

| # | Screen | Figma frame | x | Purpose |
|---|--------|-------------|---|---------|
| 1 | **Overview** | `518:125` | 0 | KPIs (customers, active subs, MRR, churn), revenue chart, recent signups, recent customers |
| 2 | **Customers** (list) | `519:124` | 1580 | Filterable/paginated table of church/org accounts (plan, status, seats, MRR, joined) |
| 3 | **Customer detail** | `520:124` | 3160 | Subscription, license & devices, invoices + info/activity/internal-notes sidebar; actions: Message, Impersonate, Change plan, Issue refund, Cancel |
| 4 | **Users** (list) | `521:124` | 4740 | Individual end-user accounts across orgs (role, status, last active); actions: Invite, Impersonate, Reset password, Suspend |
| 5 | **Affiliates** (list) | `522:124` | 6320 | Affiliate KPIs + table (referral code, clicks, signups, earned, owed, status); Run payouts, Add affiliate |
| 6 | **Confirm dialog** (overlay) | `525:124` | 7900 | Reusable destructive-action pattern (scrim + type-to-confirm) — shown for Cancel subscription |
| 7 | **Affiliate detail** | `527:124` | 9480 | Referral setup, referred customers, commission ledger + balance/details/status sidebar; actions: Pay now, Adjust balance, Pause, Remove |
| 8 | **Affiliate payouts** | `528:124` | 11060 | Payout-run table (select, method, amount, Approved/Pending/On-hold) + release payout |
| 9 | **Affiliate program settings** | `529:124` | 12640 | Commission, attribution, payouts, approvals, program status |

Subscriptions / Licenses / Support / Settings are present in the sidebar as **planned** destinations (not yet designed) — see §7 follow-ups.

### 1b. Affiliate Portal (page `526:124`)

External, affiliate-facing — a **full multi-page portal**. Shared top bar (brand + `AFFILIATES` badge · Dashboard / Referrals / Payouts / Resources / Settings · a Help icon · affiliate identity), current route highlighted. Frames are laid out left-to-right on the "Affiliate Portal" page.

| Screen | Figma frame | x | Purpose |
|--------|-------------|---|---------|
| **Dashboard** | `526:125` | 0 | Referral link (copy / get assets), KPIs (clicks, signups, conversion, pending commission), commission-earned chart, next-payout card, referrals preview |
| **Referrals** | `533:124` | 1540 | Summary stats + filterable/paginated table of every referred church (plan, joined, status, your commission) |
| **Payouts** | `534:124` | 3080 | Available balance + lifetime totals, commission-activity ledger, payout history (with receipts) |
| **Resources** | `535:124` | 4620 | Referral-link + deep-link builder, banner/creative downloads (every size + logo pack), ready-to-send email/social copy |
| **Settings** | `536:124` | 6160 | Profile, payout method/currency/tax form, notification toggles |
| **Help & FAQ** | `537:124` | 7700 | Search + FAQ accordion (commissions, payouts, attribution, self-referral, assets) + contact-support CTA |
| **Sign in** | `539:124` | 9240 | Affiliate-branded auth card (email/password + Google + "apply") |
| **Apply / Join** | `539:155` | 10780 | Public program landing (hero + 20%/60-day/monthly highlights) + application form |

The affiliate journey is complete end-to-end: **Apply → Sign in → Dashboard / Referrals / Payouts / Resources / Settings / Help**.

### 1c. The affiliate program (end-to-end)

The affiliate feature spans **three surfaces**, all designed:
1. **Admin** manages the program — approve/pause affiliates, see performance, run & release payouts, and configure the program (rate, attribution, schedule, approvals). Frames 5, 7, 8, 9.
2. **Affiliates** self-serve via the full portal — grab their link/assets, watch performance, track referrals, and manage payouts & settings. Frames `526:125`, `533:124`, `534:124`, `535:124`, `536:124`, `537:124`.
3. **Public acquisition & auth** — the **Apply/Join** landing + application (`539:155`, i.e. `selahcue.app/affiliates`) and the affiliate **Sign in** (`539:124`).

**Commission model (proposed, placeholder):** 20% recurring for 12 months · 60-day last-click attribution · monthly payouts on the 1st, Net-30, $50 minimum · manual affiliate approval, auto-approve commissions after a 30-day hold.

---

## 2. Design system usage

- **Colors** bound to `SelahCue Color` variables: `bg/base` (canvas) · `bg/panel` (sidebar, cards, tables) · `bg/elevated` (active nav, chips, avatars, inputs, table headers) · `border` (1 px hairlines) · `text/primary` · `text/muted` · `accent/brand` #5b6bd6 (primary buttons, active nav, links, code pills, chart) · `accent/preview` #2bb673 (Active/Paid/Approved status, positive deltas) · `accent/warn` #f2b53c (Trial/Pending/On-hold, Gold tier) · `accent/live` #ef4444 (Past-due/Suspended/Churned, destructive actions).
- **Status is always a solid `bg/elevated` chip** with colored text (never colored-text-on-same-tint). Deltas use `accent/preview` (good) / `accent/live` (bad).
- **Two intentional non-token colors:** pure white on filled buttons/avatars, and the real `selahcue-logo.png` raster in the sidebar/topbar brand.
- **Type ramp (Inter):** page title 22 Bold · card title 17–18 Semi Bold · KPI value 24–29 Bold · table header 13.5 Bold +tracking muted · body/cell 13.5–14 · micro/badge 10–12.
- **Components used repeatedly** (candidates for a real component library): sidebar nav item, top bar, KPI stat card, data-table (header + row + status chip + row-actions ⋯ + pagination), filter tabs + search + dropdown, card, primary/secondary/danger button, toggle switch, segmented control, field/dropdown, referral-code pill, avatar, confirm dialog.

---

## 3. States (what is drawn vs. what to spec before build)

Only **default / populated** states are drawn. The following MUST be specified before implementation:

- **Tables (every list):** loading (skeleton rows), **empty** ("No customers yet" / "No affiliates yet" / no referrals), filtered-empty ("No results for these filters"), error (failed to load + retry), row-hover, sort-active, and the ⋯ **row-action menu** contents (e.g. Customers: View · Impersonate · Suspend; Affiliates: View · Pause · Adjust · Remove).
- **Pagination:** first/last page (disabled Prev/Next), loading next page.
- **Forms & inputs** (Invite user, Add customer/affiliate, Adjust balance, Program settings fields): focus, filled, inline validation-error, disabled, submitting, success toast, server-error.
- **Toggles / segmented / dropdowns:** the open/expanded state of every dropdown; focus rings; the on↔off transition.
- **Destructive confirmations** (reusable `525:124` pattern): Cancel subscription, Issue refund, Suspend/Remove user, Pause/Remove affiliate, Revoke license, Deactivate device, Release payout. Each names the concrete consequence; high-severity ones use type-to-confirm. Include success + failure results.
- **Payout run:** all-selected / partial / none-selected header checkbox states; per-row On-hold (unselectable) rationale tooltip; "Release payout" confirmation + processing + per-affiliate success/failure result; empty run ("nothing to pay this cycle").
- **Permissions / roles:** admin roles are assumed uniform here. Before build, define staff roles (e.g. Support vs Finance vs Owner) and which actions each can see — especially refunds, payouts, impersonation, and program settings. Impersonation needs an explicit banner + audit-log entry.
- **Notifications (bell):** default, unread badge, open panel, empty.

---

## 4. Responsive behaviour (designed at 1440)

Internal tools are desktop-first; still spec:
- **≥1280 (designed):** as shown — 248 px sidebar + fluid content; KPI rows 4-up; detail pages 2-col (main + 340 px sidebar).
- **1024–1279:** sidebar collapses to icon-only rail (label on hover); KPI rows 2-up; detail right-sidebar drops below main.
- **<1024 (tablet/phone, low priority for staff):** sidebar becomes a drawer behind a hamburger; tables switch to horizontal scroll within a container (never break the page) or a stacked card view; the Affiliate **Portal** should be genuinely mobile-friendly (affiliates check earnings on phones) even if the Admin console stays desktop-only.
- Data tables scroll inside their own `overflow-x:auto` container; the page body never scrolls sideways.

---

## 5. Accessibility

- **Contrast:** status chips are colored text on solid `bg/elevated` (readable); verify each accent on `bg/elevated` at the 10–11 px chip size and bump weight if needed. `text/muted` on `bg/panel` passes AA for body.
- **Tables:** real `<table>` semantics (`<th scope=col>`, row headers where sensible); sortable headers expose `aria-sort`; row-action ⋯ is a labelled menu button (`aria-haspopup`, `aria-expanded`); the payout header checkbox controls row checkboxes with correct `aria-checked`/indeterminate.
- **Keyboard:** full keyboard nav for sidebar, tables, menus, toggles (Space), segmented (arrow keys), dialogs (focus-trap, Esc to cancel-not-confirm, initial focus on the safe action). Every interactive element needs a visible `:focus-visible` ring (`accent/brand`).
- **Dialogs:** `role="dialog"` + `aria-modal`, labelled by the title; destructive confirm defaults focus to **Keep/Cancel-out**, never the destructive button.
- **Semantics/announcements:** toasts use a polite live region; the impersonation banner is announced; KPI deltas include text (▲/▼ + "vs last month"), not color alone.
- **Touch targets** ≥ 40 px on the portal.

---

## 6. Implementation notes & assets

- Built from auto-layout frames + variable-bound fills + Inter. The only raster asset is the **brand logo** (`implementation/desktop/crates/selahcue-operator/dist/selahcue-logo.png`, tight-cropped) in the sidebar/topbar; use it as `<img alt="SelahCue logo">`.
- The sidebar/top-bar shell is identical across all 9 admin frames — build it **once** as a layout component; the active nav item is the only per-page difference.
- Charts (revenue / commission) are **vector bar mocks** — wire to a real charting lib against live series; keep the `accent/brand` bars, rounded-top.
- Data tables share one structure (header row `bg/elevated`, 1 px row dividers, status chip, right-aligned numerics, ⋯ actions, pagination footer) — implement as one reusable `<DataTable>`.
- Toggles/segmented/dropdowns are static mocks — back them with real controls; the drawn state (on/off, active segment) shows intended defaults.

---

## 7. Assumptions & follow-ups

- **Assumed (needs product sign-off):** the whole admin IA & permissions model; the affiliate **commission/attribution/payout** parameters; all displayed data. None of this exists in the codebase yet.
- **Built this pass:** Admin — Overview, Customers (list + detail), Users, Affiliates (list + detail + payouts + program settings), reusable confirm dialog. **Affiliate Portal (full, 8 frames)** — Dashboard, Referrals, Payouts, Resources, Settings, Help, Sign in, Apply/Join.
- **Out of scope (recommend as follow-ups):**
  - Admin screens still stubbed in the nav: **Subscriptions**, **Licenses**, **Support/tickets**, **Settings** (staff/roles, billing config, audit log).
  - **User detail** screen (mirror of Customer detail) and **Add customer / Invite user / Add affiliate** forms.
  - All non-default **states** in §5 (biggest gap before build) — including the portal forms (Apply, Settings, Sign in) and empty/loading/error states for the portal tables.
  - **Affiliate acquisition polish**: the application **approval** flow on the admin side (approve/reject a pending affiliate) and the "application received / approved / rejected" states.
  - **Roles & audit**: staff RBAC, impersonation banner + audit trail, refund/payout approvals — a security review is required before any of these ship.
  - Mobile/tablet frames — the **Affiliate Portal is the priority** here (affiliates check earnings on phones).
- **Next role:** product to confirm the model & permissions; then frontend-engineer (tokens map 1:1 to the app's `--sc-*` variables) + backend-engineer for the admin/affiliate/billing APIs; security review on impersonation, refunds, and payouts.
