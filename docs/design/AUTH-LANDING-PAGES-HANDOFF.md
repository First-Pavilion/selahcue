# SelahCue — Token landing pages, desktop sign-up & device management · Handoff

**Status:** design complete — all states high-fidelity, implementation-ready.
**Date:** 2026-08-14 · **Role:** `/ui-ux-designer`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ`
**Sections:** web → `743:124` on page **Marketing Website** (`468:124`); desktop → `651:124` on page **Page 1** (`0:1`).
**Goal Contract:** `docs/delivery/goals/GOAL-design-auth-landing-pages.md`
**ClickUp:** none — no ticket covers this work (workspace search 2026-08-14 returns none). See §11.
**Grounding:** `PRODUCT-GAP-AUDIT-2026-08-14.md` §11.3–§11.4 · DEC-004 / DEC-007 · `TRANSACTIONAL-EMAIL-spec.md` ·
`ACCOUNT-SETUP-HANDOFF.md` · `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` · `DESIGN-2.0-HANDOFF.md` ·
API: `implementation/api/selahcue_api/apps/accounts/{services.py,tasks.py}`, `graphql/account_schema.py`,
`apps/devices/{models.py,services.py}`, `settings.py`.

Frame link pattern: `https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=<id-with-dash>`
(e.g. `743-125`).

---

## 1. What this is (product frame)

Four surfaces that the product needs and that had **no design anywhere**:

1. **`/verify`** — where the verification email's button lands. Shipped emails link here **today**; the route 404s.
2. **`/reset`** — where the password-reset email's button lands. Same. This is the continuation of the
   *request reset* / *email sent* steps specified (prose only) in `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §5.
3. **Desktop sign-up + verify-pending** — `ACCOUNT-SETUP-HANDOFF.md` covers sign-**in** (A0–A10) only.
4. **Manage devices** — the account-portal page that desktop frame **A8** and the Account dashboard's
   **"Manage devices"** button (`506:223`) already link to.

**Hard invariant carried through every frame** (inherited from ACCOUNT-SETUP §1): account and licensing state
must **never** block, blank or imply blocking of live presentation (NFR-015 offline, CON-2 offline-core,
NFR-024 never-blank). Every error, expiry and destructive frame states this explicitly.

**Second invariant, specific to these surfaces: no account-existence oracle.** The API deliberately returns an
identical response whether or not an address is registered (`register_customer_user`, `request_password_reset`
both return `accepted: true` unconditionally; `login` equalises timing). Copy on these pages must never leak
existence. This is why V5 reads *"If you@yourchurch.org has a SelahCue account waiting to be verified…"* rather
than *"We've sent…"*, and why **there is no "email already registered" error on sign-up** — see §10.1.

---

## 2. Placement, chrome and the two token layers

### 2.1 Placement

| Surface | Page | Section | Chrome cloned from |
|---|---|---|---|
| `/verify`, `/reset` | Marketing Website `468:124` | `743:124` | **Sign in `505:124`** — bare centred card, no nav/footer |
| Manage devices | Marketing Website `468:124` | `743:124` | **Account `506:124`** — nav + header + sidebar + cards + footer |
| Desktop sign-up | Page 1 `0:1` | `651:124` (existing Account Setup section) | **A0 `652:124` / A1 `654:124`** |

The device frames are literal clones of `506:124`, so nav, header, sidebar and footer are pixel-identical to the
shipped Account page. The auth frames reproduce `505:124`'s card geometry exactly (see §2.3).

### 2.2 The two token layers — read this before implementing

There is a **real divergence** between Figma and code on the marketing surface, and it is not a mistake to
"fix" while implementing:

- **Figma** marketing frames (`505:124`, `506:124`, and everything new in `743:124`) bind fills to the local
  **`SelahCue Color`** variable collection — the *legacy* layer (`bg/base #0e1116`, `accent/brand #5b6bd6`).
- **Shipped Vue** (`SignInView.vue`, `AccountView.vue`) uses the **Design 2.0 `--sc-*`** custom properties
  (`--sc-base #0b0d12`, `--sc-primary #6e5cf0`), which `tokens.css` defines alongside the legacy vars.

I bound to the legacy variables so the new frames are consistent with the frames beside them and **no parallel
variable collection was created** (still exactly 1 collection / 19 variables). **Implement with `--sc-*`** — the
column below is the mapping. The two ramps differ by 1–3% luminance; nothing in this design depends on the gap.

| Role | Figma variable (bound) | Hex | Implement with |
|---|---|---|---|
| page background | `bg/base` | `#0e1116` | `--sc-base` |
| card / panel | `bg/panel` | `#171b22` | `--sc-surface` |
| row / control / input-disabled | `bg/elevated` | `#1e232c` | `--sc-elevated` |
| input well | `bg/base` | `#0e1116` | `--sc-inset` |
| hairline | `border` | `#2b323d` | `--sc-border` |
| primary text | `text/primary` | `#eef1f6` | `--sc-text` |
| secondary / help text | `text/muted` | `#9aa4b2` | `--sc-text-secondary` |
| brand / link / primary button | `accent/brand` | `#5b6bd6` | `--sc-primary` |
| danger / destructive | `accent/live` | `#ef4444` | `--sc-live` |
| success | `accent/preview` | `#2bb673` | `--sc-preview` |
| warning | `accent/warn` | `#f2b53c` | `--sc-warn` |

**Banner surfaces are unbound hexes** (the legacy collection has no soft tints). They are exactly the Design 2.0
soft tints already in `tokens.css`, so implement them as the named custom property:

| Banner kind | Hex in Figma | Implement with | Glyph ink |
|---|---|---|---|
| info | `#10222b` | `--sc-info-soft` | `--sc-primary` (`◆`) |
| success | `#10231c` | `--sc-preview-soft` | `--sc-preview` (`✓`) |
| warning | `#2a2415` | `--sc-warn-soft` | `--sc-warn` (`!`) |
| danger | `#2a1416` | `--sc-live-soft` | `--sc-live` (`✕`) |

Banner **body text never uses the status colour** — the title is `--sc-text`, the body `--sc-text-secondary`, and
colour appears only on the glyph. That keeps every pair well clear of AA and satisfies WCAG 1.4.1 (the words
carry the meaning, not the hue).

> **Appearance mode.** SelahCue's product surfaces are **dark only** — there is no light variant to produce, and
> `DESIGN-2.0-HANDOFF.md` defines a single dark ramp. The only light surface in the system is transactional
> email, which is light *deliberately* (`TRANSACTIONAL-EMAIL-spec.md` §"Why light-mode"). Note that in this
> codebase a **"theme" always means a slide-design template** (`THEME-MODEL-spec.md`) — it is never a word for
> light/dark appearance, and no string in this handoff uses it that way.

### 2.3 Auth card geometry (cloned from `505:124`, do not re-derive)

- Page frame 1440×900, vertical auto-layout, centred both axes, gap 28, padding 64 top/bottom, `bg/base`.
- Brand lockup: 30×30 logo + "SelahCue" Inter **Bold 22** `text/primary`, gap 10.
- Card: **width 430, height hugs**, gap 18, padding 36, `bg/panel`, 1px `border`, **radius 22**.
- Status icon disc: 56×56, `bg/elevated`, radius 999, glyph Inter Bold 22 in the status ink.
- Title: Inter **Bold 24** (status/result pages) or **Bold 26** (form pages R1/R2/R3/R7), `text/primary`.
- Body: Inter Regular 14.5 / line-height 22, `text/muted`.
- Field: label Inter Medium 13 `text/muted`; input height 44, padding 13/14, `bg/base` fill, 1px `border`,
  radius 10, value Inter Regular 15. Focus = 1.5px `accent/brand`. Error = 1.5px `accent/live`.
- Primary button: full width, height 47, `accent/brand`, radius 12, label Inter Semi Bold 15.5 white.
- Secondary button: full width, height 44, `bg/elevated` + 1px `border`, radius 12, label Semi Bold 14.5.
- Footer link row below the card: muted Regular 14 + link Semi Bold 14 `accent/brand`, gap 6.

Desktop frames follow the **A0–A10** conventions instead: 1760×1000, `#0b0d12`, 57px topbar with the
"Works offline" pill, card **560 wide** at x=600, padding 36/40/32/40, radius 16, inputs 46 tall, primary button
480×45 radius 10. Type is one step smaller than web (title Bold 24, body Regular 14, label Medium 12).

---

## 3. Node map

### 3.1 `/verify` — email-verification landing (web)

| # | State | Node | Reachable today? |
|---|---|---|---|
| V1 | Verifying (loading) | `743:125` | yes |
| V2 | Verified (success) | `743:139` | yes |
| V3 | **Link no longer valid** (merged default) | `746:124` | **yes — ship this one** |
| V4 | Link expired · 24h + resend | `746:148` | no — needs §10.2 |
| V5 | New link sent (resend confirmation) | `746:172` | needs §10.3 |
| V6 | No verification link (missing `?token=`) | `747:124` | yes |

### 3.2 `/reset` — set-new-password landing (web)

| # | State | Node | Reachable today? |
|---|---|---|---|
| R1 | Choose a new password (valid token) | `747:143` | yes |
| R2 | Validation errors (client-side) | `747:173` | yes |
| R3 | Updating password (submitting) | `749:124` | yes |
| R4 | **Link no longer valid** (merged default) | `749:150` | **yes — ship this one** |
| R5 | Link expired · 1h | `749:174` | no — needs §10.2 |
| R6 | Password updated (success) | `749:198` | yes |
| R7 | Server error (submission failed) | `749:217` | yes |

### 3.3 Desktop sign-up (section `651:124`, continuing A0–A10)

| # | State | Node |
|---|---|---|
| A11 | Create your SelahCue account (sign-up) | `752:124` |
| A12 | Sign-up — inline validation (password + terms) | `752:172` |
| A13 | Verify your email (pending) | `752:219` |

### 3.4 Manage devices (web account portal)

| # | State | Node |
|---|---|---|
| D1 | Manage devices — populated (3 of 5) | `753:124` |
| D2 | Deactivate device — confirm dialog | `754:124` |
| D3 | All device slots in use (instance limit, 5 of 5) | `754:257` |
| D4 | No devices activated (empty, 0 of 5) | `755:124` |
| D5 | Couldn't load devices (error) | `755:256` |
| D6 | More devices than the plan allows (over limit, 5 of 3) | `755:385` |

---

## 4. Per-frame specs — `/verify`

Route: `GET /verify?token=<raw_token>`. Built by `apps/accounts/tasks.py:55`.
Mutation: `verifyEmail(token: String!) → { verified: Boolean! }`.

### 4.1 V1 — Verifying — `743:125`
Fires `verifyEmail` on mount. Centred card: `↻` disc in `accent/brand`, title **"Verifying your email address…"**,
body, and a 6px progress track (`bg/elevated`) with a `accent/brand` fill at ~⅓. Footer link row
"Taking too long? **Back to Sign in**".
Announce with `role="status"` + `aria-live="polite"`; honour `prefers-reduced-motion` by holding the bar static.
**Do not** show this for less than ~300 ms — flash it only if the request is genuinely in flight.

### 4.2 V2 — Verified — `743:139`
`✓` disc in `accent/preview`, title **"Email address verified"**, body, full-width primary
**"Continue to sign in"**, then a success banner. Footer "Not your account? **Contact support**".
The banner is the never-blank reassurance and must not be dropped.

### 4.3 V3 — Link no longer valid — `746:124` — **the state that ships**
`✕` disc in `accent/live`, title **"This verification link didn't work"**. Body names all three causes without
claiming to know which — because the API does not tell us (§10.2). Carries an **Email field** and
**"Send a new verification link"**: the token is dead, so the page has no identity and must ask for one.
Info banner "Already verified? Just sign in".

### 4.4 V4 — Link expired (24h) — `746:148`
Same layout, `!` disc in `accent/warn`, title **"This verification link has expired"**, body states the
**24-hour** TTL, warn banner "Why links expire". Identical mechanics to V3.
**Only render this when the backend can prove expiry** (§10.2). Until then V3 is the single failure state.

### 4.5 V5 — New link sent — `746:172`
`✉︎` disc in `accent/brand`, title **"Check your inbox"**. Body is **conditional by construction** —
*"If you@yourchurch.org has a SelahCue account waiting to be verified…"* — this phrasing is load-bearing for
no-enumeration and must not be "improved" into a direct claim. Secondary **"Back to Sign in"**, a muted retry
line, and an info banner "Only the newest link works" (true: minting a token consumes prior unconsumed ones).

### 4.6 V6 — No verification link — `747:124`
Reached when `/verify` is opened without `?token=` (bookmark, stripped query, hand-typed). `!` disc in
`text/muted` — this is not an error, so it is not red. Email field + **"Send a verification link"**.

---

## 5. Per-frame specs — `/reset`

Route: `GET /reset?token=<raw_token>`. Built by `apps/accounts/tasks.py:64`.
Mutation: `confirmPasswordReset(input: {token, newPassword}) → { reset: Boolean! }`.

> **Critical implementation note.** `confirm_password_reset` runs `_validate_password` **before** it looks at the
> token, and *both* failures raise the same `VALIDATION_FAILED`. If you submit a password shorter than 10
> characters, the server's answer is indistinguishable from "your link is dead" — the user would be told their
> link expired when their password was simply too short. **Validate length client-side (R2) and never submit a
> password outside 10–200 characters.** With that guard, a `VALIDATION_FAILED` from this mutation can be safely
> attributed to the token (R4).

### 5.1 R1 — Choose a new password — `747:143`
Title **Bold 26** "Choose a new password". The page **cannot display the user's email address** — the reset
token is opaque and no query exposes the address behind it. Copy is written accordingly; do not add a
"resetting the password for …" line.
Two fields, both with a **Show** affordance: *New password* (focused, hint **"At least 10 characters."**) and
*Confirm new password*. Primary **"Update password"**. Info banner **"This signs you out everywhere"** —
factual: the mutation revokes every ACTIVE `CustomerSession`, and deliberately **not** any `DeviceToken`, which
is why the banner promises devices keep presenting.

### 5.2 R2 — Validation errors — `747:173`
Both fields in error (1.5px `accent/live`), each with `✕ ` + message beneath, primary button at 45% opacity.
Messages: **"Password must be at least 10 characters."** / **"Both passwords must match."**

### 5.3 R3 — Updating password — `749:124`
Fields at 50% opacity, primary button disabled with `↻` + **"Updating password…"**, muted **"Don't close this
tab."** Set `aria-busy="true"` on the form.

### 5.4 R4 — Link no longer valid — `749:150` — **the state that ships**
`✕` disc, title **"This reset link didn't work"**, body states the **1-hour**, single-use rule and asks for an
email to start again. Info banner **"Your password has not changed"**.

### 5.5 R5 — Link expired (1h) — `749:174`
`!` disc in `accent/warn`, title **"This reset link has expired"**. Body explicitly contrasts the two TTLs —
*"1 hour … sooner than verification links, because they can change your password"* — and the warn banner
**"Why only 1 hour"** repeats the contrast. This is the frame that answers the brief's "copy must reflect the
shorter TTL". Needs §10.2 to be reachable.

### 5.6 R6 — Password updated — `749:198`
`✓` disc in `accent/preview`, title **"Password updated"**, body notes the global sign-out, primary
**"Continue to sign in"**, success banner **"Your devices keep presenting"**. Footer
"Didn't do this? **Contact support**".

### 5.7 R7 — Server error — `749:217`
The form again, with a **danger banner at the top of the card** (above the title):
**"We couldn't update your password"** / *"…your password has not been changed and this link still works until
it expires."* That claim is accurate — the mutation is wrapped in `transaction.atomic()`, so a failure rolls the
token's `consumed_at` back. Primary relabelled **"Try again"**; footer offers a fresh link.

---

## 6. Per-frame specs — desktop sign-up (`651:124`)

Extends the A-series. Row 4 of the section grid; section grown to 7700×4720.

### 6.1 A11 — Create your SelahCue account — `752:124`
A1's chrome and card. Back link, title **Bold 24**, subtitle that repeats the account's *actual* job
("…it is not needed to run a service"). Fields, in order: **Church or organisation** (focused), **Your name**,
**Email**, **Password** (Show + hint "At least 10 characters. Use something you don't use anywhere else.").
A muted meta line — **"This device: Windows 11 · SelahCue 1.0.0 · United Kingdom — detected automatically"** —
mirrors A2's detected-device line and covers `country` / `timezone` / `platform` / `app_version`, which
`register_customer_user` requires but should never be asked for.
Terms checkbox (unchecked), primary **"Create account"** **disabled until checked**, then
"Already have an account? **Sign in**" and the info banner **"You can skip this entirely"**.

Maps to `registerCustomerUser(input: {idempotencyKey, email, password, orgName, country, displayName, timezone})`.

### 6.2 A12 — Inline validation — `752:172`
The A4 precedent (a dedicated inline-error frame). Password field in error with
**"Use at least 10 characters — that is 4 more."** — a counting message, because the rule is purely length.
Terms unchecked with a `warn` line **"Accept the terms to continue."** Button disabled.
Info banner **"Nothing has been sent yet"**.

### 6.3 A13 — Verify your email (pending) — `752:219`
The answer to "what the desktop does while unverified". `✉︎` disc, title **"Check your email to finish setting
up"**, body naming the address and the **24-hour** window, then:

- a **success banner** — "You are ready to present right now" — the flagship never-blank statement;
- a **"WHILE THIS ADDRESS IS UNVERIFIED"** panel (`bg/inset`, 1px border, radius 12) with four honest rows:
  - `✓` Live presentation, scripture, media and timers — all working
  - `✓` Your work is saved locally as normal
  - `–` Signing in and activating this device — available once verified
  - `–` Cloud AI notes, plan and device management — available once verified
- primary **"I've verified — continue"**, ghost **"Resend verification email"**, and a muted line offering
  *Go back and change it* / *Skip — set up later*.

The two `–` rows are not a guess: `login` raises `POLICY_DENIED` for an unverified user *after* a correct
password, so activation genuinely cannot proceed until verification lands.

---

## 7. Per-frame specs — Manage devices (`/account/devices`)

Portal shell cloned from `506:124`. **Sidebar gains a `Devices` item at position 4** (after *License*, before
*Invoices*) with the standard selected treatment — `bg/elevated` fill, label Semi Bold `accent/brand`. This is
the destination of the existing, currently-dead **"Manage devices"** button `506:223`.

**Columns are name, platform + version, last seen** — the three the brief asks for. The
**IP-address column that `AccountView.vue` currently renders is dropped**: `Device` has no IP field, so it is
fabricated, and it is needless PII on a page a church admin shares. See §10.4.

### 7.1 D1 — Populated — `753:124`
Card header **"Devices"** + subtitle + pill **"3 OF 5 ACTIVE"**. Activation meter (`3 of 5 used`, 5 segments,
used = `accent/brand`, free = `bg/elevated`) reusing the pattern from `506:204`. Device list in a `bg/base`
well, radius 12, rows separated by 1px `border`:

| Dot | Name | Tag | Meta | Action |
|---|---|---|---|---|
| `accent/preview` | Studio PC | `THIS DEVICE` (brand) | Windows 11 · SelahCue 1.0.0 · Last seen today at 10:42 | Deactivate |
| `accent/preview` | Booth MacBook | — | macOS 14 · SelahCue 1.0.0 · Last seen 2 days ago | Deactivate |
| `text/muted` | Youth Hall PC | — | Windows 11 · SelahCue 0.9.4 · Last seen 3 Aug 2026 | Deactivate |

Dot = recency (green recently seen, muted stale) and is **never the only cue** — the "Last seen" text carries it.
Footnote states what deactivation actually does (see §8 copy deck).

### 7.2 D2 — Deactivate confirm — `754:124`
Scrim `bg/base` @72% over the page; dialog 420 wide, `bg/elevated`, 1px `border`, radius 16, centred.
`!` in `accent/warn`, title **"Deactivate Youth Hall PC?"**, body, a success banner **"Nothing goes dark"**, then
**"Keep active"** (ghost with a 1.5px `accent/brand` ring — it takes initial focus) and **"Deactivate"**
(`accent/live`, white label). Muted **"Esc keeps the device active."**
Per `MARKETING-PORTAL-GAP-FILL` §7b this is a **simple confirm — no type-to-confirm** (that is reserved for
subscription cancellation). `role="alertdialog"`, `aria-modal="true"`, focus trapped, `Esc` = Keep active.

### 7.3 D3 — Instance limit reached — `754:257`
Pill **"5 OF 5 ACTIVE"** in `accent/warn`, meter full, five rows, and a **warn banner directly under the card
header**: "All device slots are in use". CTAs **"View plans"** + **"How device slots work"**.
Mirrors desktop **A5** (`656:124`) — the same condition seen from the portal instead of the app, and the same
`POLICY_DENIED` from `activate_device`.

### 7.4 D4 — Empty — `755:124`
Pill **"0 OF 5 ACTIVE"** in `text/muted`, empty meter, no list. Centred empty state in the `bg/base` well:
`◆` disc, **"No devices activated yet"**, body pointing at *Settings › Account*, buttons
**"Download SelahCue"** + **"How to activate a device"**, then an info banner restating that activation is
optional.

### 7.5 D5 — Couldn't load — `755:256`
Header pill and meter removed (no truthful number to show), `✕` disc, **"Couldn't load your devices"**,
**"Retry"** primary, and a success banner **"Your devices are unaffected"**.

### 7.6 D6 — Over limit — `755:385`
Reachable after a plan downgrade: 5 active devices against a limit of 3. Pill **"5 OF 3 ACTIVE"** and the meter
value in `accent/live`; meter shows 3 `accent/brand` + 2 `accent/live` segments. Danger banner
**"You have more devices than your plan allows"** whose body insists nothing was switched off.
This state is a genuine consequence of DEC-004 (the limit gates *activation*, it does not revoke in place) and
is easy to forget.

---

## 8. Copy deck — every user-visible string

### 8.1 `/verify`

**V1** · "Verifying your email address…" / "This only takes a moment. Keep this tab open." /
"Taking too long?" + "Back to Sign in"

**V2** · "Email address verified" / "Thanks — your SelahCue account is active. Sign in to manage your plan,
license and devices." / **Continue to sign in** / banner "You don't need an account to run SelahCue" —
"Verification only unlocks plan, license and device management. Live presentation works offline, always." /
"Not your account?" + "Contact support"

**V3** · "This verification link didn't work" / "The link may have expired, already been used, or been copied
incompletely. Enter your email address and we'll send a fresh one." / label "Email", placeholder
"you@yourchurch.org" / **Send a new verification link** / banner "Already verified? Just sign in" — "A
verification link stops working once it has been used. If you have already confirmed this address, sign in as
normal." / "Remembered everything?" + "Back to Sign in"

**V4** · "This verification link has expired" / "Verification links expire 24 hours after they are sent. Enter
your email address and we'll send you a new one." / **Send a new verification link** / banner "Why links
expire" — "A 24-hour window limits how long the link is useful if the email is forwarded or sits in a shared
inbox." / "Wrong address?" + "Back to Sign in"

**V5** · "Check your inbox" / "If you@yourchurch.org has a SelahCue account waiting to be verified, a new link
is on its way. It expires in 24 hours." / **Back to Sign in** / "Didn't arrive? Check your spam folder, then
request another link." / banner "Only the newest link works" — "Sending a new link cancels the previous one.
Use the most recent email you received." / "Need a hand?" + "Contact support"

**V6** · "This page needs a verification link" / "Open the link in the email we sent you. If you no longer have
it, enter your address and we'll send a new one." / **Send a verification link** / "Already verified?" +
"Back to Sign in"

### 8.2 `/reset`

**R1** · "Choose a new password" / "Pick a password you don't use anywhere else. You'll be signed in again with
the new one." / labels "New password", "Confirm new password", trailing "Show" / hint "At least 10 characters."
/ **Update password** / banner "This signs you out everywhere" — "Updating your password ends every active
SelahCue session on this account. Devices you have already activated keep presenting offline — live output is
never interrupted." / "Remembered it?" + "Back to Sign in"

**R2** · errors "Password must be at least 10 characters." · "Both passwords must match."

**R3** · **Updating password…** / "Don't close this tab."

**R4** · "This reset link didn't work" / "The link may have expired, already been used, or been copied
incompletely. Reset links last 1 hour and work once. Enter your email address to start again." /
**Send a new reset link** / banner "Your password has not changed" — "A link that fails changes nothing on your
account. Your old password still works until you set a new one."

**R5** · "This reset link has expired" / "Password reset links expire 1 hour after they are sent — sooner than
verification links, because they can change your password. Enter your email address and we'll send a new one." /
**Send a new reset link** / banner "Why only 1 hour" — "A reset link can take over an account, so it is
short-lived and single-use. Verification links, which only confirm an address, last 24 hours."

**R6** · "Password updated" / "Sign in with your new password. For your security, every other session on this
account has been signed out." / **Continue to sign in** / banner "Your devices keep presenting" — "Activated
SelahCue devices are not signed out and keep working offline. Changing your password never interrupts live
output." / "Didn't do this?" + "Contact support"

**R7** · banner "We couldn't update your password" — "Something went wrong on our side. Your password has not
been changed and this link still works until it expires." / **Try again** / "Still stuck?" +
"Request a new reset link"

### 8.3 Desktop sign-up

**A11** · "Back" / "Create your SelahCue account" / "One account per church. It manages your plan, license and
the devices you activate — it is not needed to run a service." / labels "Church or organisation", "Your name",
"Email", "Password" / hint "At least 10 characters. Use something you don't use anywhere else." /
"This device: Windows 11 · SelahCue 1.0.0 · United Kingdom — detected automatically" / "I agree to the SelahCue
Terms of Service and Privacy Policy." / **Create account** / "Already have an account?  Sign in" / banner
"You can skip this entirely" — "SelahCue works offline. Slides, scripture, media, blackout/clear and timers all
run without an account — signing up only unlocks cloud features, licensing and device management."

**A12** · "Use at least 10 characters — that is 4 more." / "Accept the terms to continue." / banner
"Nothing has been sent yet" — "Your details stay on this computer until you press Create account."

**A13** · "Check your email to finish setting up" / "We sent a verification link to alex@gracecommunity.org.
Open it within 24 hours to activate the account. You can leave SelahCue open — this screen updates on its own."
/ banner "You are ready to present right now" — "SelahCue works fully offline. Slides, local scripture, media,
blackout/clear and timers all work while this address is unverified — verification is never required to run
your service." / "WHILE THIS ADDRESS IS UNVERIFIED" / "Live presentation, scripture, media and timers — all
working" · "Your work is saved locally as normal" · "Signing in and activating this device — available once
verified" · "Cloud AI notes, plan and device management — available once verified" /
**I've verified — continue** / **Resend verification email** / "Wrong address? Go back and change it.   ·
Skip — set up later"

### 8.4 Manage devices

**Shared** · "Devices" / "Every SelahCue install activated against this account uses one device slot on your
plan." / "Device activations" / "Deactivating frees the slot straight away. That device keeps presenting offline
until its cached entitlement expires, then it must be activated again. Live output is never interrupted."

**D1** · "3 OF 5 ACTIVE" · "3 of 5 used" · "THIS DEVICE" · row action "Deactivate"

**D2** · "Deactivate Youth Hall PC?" / "This frees one of your 5 device slots straight away. Youth Hall PC keeps
presenting offline until its cached entitlement expires, then it must be activated again." / banner
"Nothing goes dark" — "Deactivating never blanks or stops a live service — it only removes the device from your
plan." / **Keep active** · **Deactivate** / "Esc keeps the device active."

**D3** · "5 OF 5 ACTIVE" · "5 of 5 used" / banner "All device slots are in use" — "Your plan includes 5 devices
and all 5 are active. Deactivate one you no longer use to free a slot, or move to a larger plan. Activating a
new device is refused until a slot is free." / **View plans** · **How device slots work**

**D4** · "0 OF 5 ACTIVE" · "0 of 5 used" / "No devices activated yet" / "Install SelahCue on the computer that
runs your service, then open Settings › Account and sign in. The device appears here as soon as it activates." /
**Download SelahCue** · **How to activate a device** / banner "You don't have to activate anything to run a
service" — "SelahCue presents fully offline. Activating a device only links it to your plan for licensing and
cloud features."

**D5** · "Couldn't load your devices" / "We couldn't reach SelahCue just now. Check your connection and try
again — this page is the only thing affected." / **Retry** / banner "Your devices are unaffected" — "Every
activated device keeps presenting offline. Nothing here changes what is running in your building."

**D6** · "5 OF 3 ACTIVE" · "5 of 3 used" / banner "You have more devices than your plan allows" — "Your plan now
includes 3 devices and 5 are still active. Deactivate 2 to come back within your plan. Nothing has been switched
off — every device keeps presenting, and no live output is affected."

---

## 9. Traceability (control → source)

| Frame / control | Source |
|---|---|
| `/verify` and `/reset` routes exist at all | `apps/accounts/tasks.py:55,64` — `{FRONTEND_BASE_URL}/verify?token=`, `/reset?token=` |
| "expires in 24 hours" (V4, V5, A13) | `ACCOUNT_EMAIL_VERIFY_TTL_SECONDS = 24*3600` (`settings.py:269`) |
| "expire 1 hour … single-use" (R4, R5) | `ACCOUNT_PASSWORD_RESET_TTL_SECONDS = 3600` (`settings.py:270`) |
| "At least 10 characters" (R1, R2, A11, A12) | `ACCOUNT_MIN_PASSWORD_LENGTH = 10` (`settings.py:273`); `_validate_password` is **length-only**, 10–200 |
| V3 / R4 merged failure state | `verify_email` + `confirm_password_reset` collapse unknown/wrong-purpose/consumed/expired to one `VALIDATION_FAILED` |
| "Only the newest link works" (V5) | `request_password_reset` consumes prior unconsumed tokens before minting |
| "signs you out everywhere" (R1, R6) | `confirm_password_reset` revokes every ACTIVE `CustomerSession` |
| "your devices keep presenting" (R1, R6) | `logout_session` docstring — revokes the ACCOUNT session only, never a `DeviceToken` or cached entitlement |
| "this link still works until it expires" (R7) | `confirm_password_reset` is `transaction.atomic()` — a failure rolls back `consumed_at` |
| Conditional phrasing in V5; no "email already registered" | `register_customer_user` / `request_password_reset` always return `accepted: true`; `login` equalises timing |
| A13's two unavailable rows | `login` raises `POLICY_DENIED` for unverified users only *after* a correct password |
| A11 field set + detected meta line | `RegisterCustomerUserInput{idempotencyKey,email,password,orgName,country,displayName,timezone}` |
| Device slot meter, "N of M used" | DEC-004; `AppLicenseKey.device_limit`; active `Device` count |
| D3 instance-limit copy | `activate_device` instance-limit `POLICY_DENIED`; matches desktop A5 `656:124` |
| D6 over-limit state | DEC-004 — the limit gates activation and does not revoke in place |
| Never-blank copy on every error/expiry/destructive frame | NFR-015, CON-2, NFR-024 |
| D2 simple confirm (no type-to-confirm) | `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §7b |
| Portal shell, sidebar, card geometry | Account `506:124`; auth card geometry from Sign in `505:124` |

---

## 10. Backend that does not exist yet — read before estimating

These are **not** design assumptions; each was verified against the source. Four of the five block a frame.

### 10.1 There is no "email already registered" error — by design
`register_customer_user` returns `accepted: true` whether or not the address exists; the real owner instead
receives the *"Someone tried to sign up with your address"* email (`TRANSACTIONAL-EMAIL-spec.md` §3).
**A11 therefore always proceeds to A13** on submit. `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §4c specifies an
inline "An account with this email already exists" error — **do not build it**; it would re-introduce exactly
the enumeration oracle the backend was written to avoid. §11 records the correction.

### 10.2 The API cannot distinguish "expired" from "invalid" — owner decision
`verify_email` and `confirm_password_reset` both collapse *unknown / wrong-purpose / already-consumed / expired*
into a single `VALIDATION_FAILED`, deliberately ("no oracle").
**Consequence:** V4 and R5 — the frames the brief asks for, which name the TTL and explain it — are **not
reachable today**. V3 and R4 are the merged states that ship now and cover the same ground without claiming
knowledge the client does not have.
Making V4/R5 reachable needs a product/security decision plus a backend change: return a distinguishable
`EXPIRED` for a token that was well-formed, matched a row, had the right purpose, was unconsumed, and was only
past `expires_at`. That leaks strictly less than a working link does, but it is a security posture change and
**not mine to make**. Owner: product + security. Until then, ship V3/R4 and keep V4/R5 as the target design.

### 10.3 There is no resend-verification mutation
`account_schema.py` exposes `registerCustomerUser`, `verifyEmail`, `login`, `refreshSession`, `logout`,
`requestPasswordReset`, `confirmPasswordReset`, `activateDeviceWithSession` — and **no resend**. A workspace
grep for "resend" across `implementation/api` returns nothing.
V3, V4, V5, V6 and A13's **"Resend verification email"** all depend on a new mutation, which must mirror
`request_password_reset`'s shape: take an email, always return `accepted: true`, consume prior unconsumed
`EMAIL_VERIFY` tokens, and be rate-limited. Owner: backend.

### 10.4 Device data the list needs
- **`Device` has no `last_seen_at`.** The "Last seen …" column in D1/D3/D6 has no backing field. Either add one
  (updated on each `device_token`-authed call) or derive from the newest `DeviceToken.issued_at` — but a token
  issue is not a sighting, so the honest fix is the new field. Owner: backend.
- **There is no devices query.** `AccountQuery` exposes only `accountViewer`. D1 needs a session-authed list of
  the org's devices (`display_name`, `platform`, `app_version`, `status`, last-seen, and a flag for
  "this device"). Owner: backend.
- **The IP-address column shipped in `AccountView.vue` is not backed by any model field** and is dropped here.

### 10.5 Device deactivation does not exist
Confirmed by a concurrent API audit and by reading `apps/devices/services.py`: **no code path sets
`DeviceStatus.REVOKED`**. The instance limit is therefore a one-way ratchet today — a church that replaces a
laptop is permanently locked out once it hits the limit, and D3 has no exit.
**D1/D2's deactivate flow is designed as the target state for that work, not against a live endpoint.** It needs
a session-authed mutation that flips `Device.status` to `REVOKED`, revokes the device's `DeviceToken`s, writes an
audit event, and frees the slot for the next activation. Note `_assert_device_activatable` currently treats a
revoked device as **terminal** ("re-provisioning a revoked install is a separate future flow"), so
re-activating a replaced-then-restored machine is a second decision the ticket should settle.
Owner: backend (being ticketed).

---

## 11. Corrections to existing design docs

Found while grounding this work. None are addressed by the audit.

1. **`MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §4c** — "Email taken → *An account with this email already
   exists*" contradicts the shipped no-enumeration API. Must not be implemented (§10.1).
2. **Same doc §3c and §4d** — password rules given as "at least 8 characters" plus "one uppercase letter and one
   number". The API enforces **10–200 characters, length only, no complexity rule**. The rules in this handoff
   are the correct ones.
3. **Same doc §5b** — "It expires in 15 minutes" for the reset link. The real TTL is **1 hour**
   (`ACCOUNT_PASSWORD_RESET_TTL_SECONDS = 3600`). Fix the request/email-sent copy when those frames are built.
4. **Same doc §6/§2** — states it "reuses … Design 2.0 `--sc-*` tokens", but the Figma frames on that page bind
   to the legacy `SelahCue Color` collection. Both statements are half-true; §2.2 is the reconciliation.
5. **The audit's "Manage devices … designed nowhere" is slightly overstated.** Account `506:124` already ships a
   device *summary*: a two-row device list (`506:210`), an activation meter (`506:204`) and the
   **"Manage devices"** button (`506:223`). What was missing is the page that button opens — which is what
   D1–D6 now are. The button can be wired to `/account/devices` unchanged.
6. **`ACCOUNT-SETUP-HANDOFF.md` §9.4** asks whether an in-app device list is wanted. D1–D6 answer the *portal*
   half; the desktop A8 link-out remains correct and unchanged.

---

## 12. Accessibility (testable)

- **Contrast.** Body, label and status text use tokens audited AA on `bg/base` / `bg/panel` / `bg/elevated`.
  Banner bodies use `text/muted` on the soft tints, never the status ink, so no small text depends on a
  same-hue pair. `text/muted` is never used for essential body copy at small sizes on these frames — headline
  and action text are `text/primary`.
- **Colour is never the only cue.** Every status pairs a glyph *and* a word: `✓` + "verified", `✕` + "didn't
  work", `!` + "has expired", `THIS DEVICE` tag, "Last seen …" beside every recency dot, "5 of 5 used" beside
  every meter. Field errors carry `✕ ` in the message text itself.
- **Focus and keyboard.** Focus order follows visual order (brand → card title → fields → primary → alternate
  link → banner → footer link). Focus ring is 2px `accent/brand` with offset — distinct from the 1.5px field
  focus stroke. D2 is a modal: `role="alertdialog"`, `aria-modal="true"`, focus trapped, initial focus on
  **Keep active** (the safe action), `Esc` = Keep active. Every target is ≥44px effective height (inputs 44/46,
  buttons 44–47, sidebar rows 38 with 12px padding → 46, device rows 66).
- **Screen reader.** V1/R3 are `role="status"` + `aria-live="polite"` with `aria-busy` on the form. Field errors
  use `aria-invalid="true"` + `aria-describedby` pointing at the message. Card-level banners (R7, D3, D6) are
  `role="alert"`. The activation meter is `role="progressbar"` with `aria-valuemin/max/now` **and** the literal
  "N of M used" text. Password *Show* toggles need `aria-pressed` and a label that is not just an icon.
- **Reduced motion.** V1's progress bar and R3's `↻` must be static under `prefers-reduced-motion`; nothing else
  on these frames relies on motion.
- **Autocomplete.** `autocomplete="new-password"` on both R1 fields, `autocomplete="email"` on every email
  field, `autocomplete="organization"` / `"name"` on A11.
- **Never-blank as an a11y guarantee.** These are web pages and the desktop first-run screen; none may occlude
  the app's emergency footer or intercept its global chords.

---

## 13. Responsive

Follows `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §8 — no new rules.

- **Auth cards (V*, R*)**: max-width 480 centred at tablet; at <768px the card fills 92vw, padding drops
  36 → 24, and the title steps 24/26 → 22. The card never becomes full-bleed — the surrounding `bg/base` margin
  is what marks it as a focused task.
- **Manage devices (D*)**: at tablet the sidebar collapses above the content (per §8d "Account: 1-up stacked");
  at mobile the device row becomes two lines — name + tag on the first, meta on the second — with
  **Deactivate** dropping to its own full-width row so it clears 44px. The meter keeps its segments.
- **D2 dialog**: max-width 420, 92vw at mobile, vertically centred, page scroll locked while open.
- Desktop A11–A13 are fixed-size app frames; no responsive behaviour applies.

---

## 14. What I did not do

- **No light-appearance variants** — the product's design system defines a single dark ramp (§2.2). Not
  applicable rather than skipped.
- **No mobile/tablet Figma frames** — GAP-07 in the marketing gap-fill remains open and is tracked there; §13
  specifies the behaviour in prose, as that doc does.
- **No checkout, plan-change, payment-method, dunning or tax frames** — out of scope, blocked on the commercial
  model. D3/D4's **"View plans"** deliberately stops at the existing Pricing page (`483:124`).
- **No admin-console work** — its handoff is a v0.1 gate draft pending the Platform PRD.
- **No ClickUp tickets created** — ticket creation is PM-owned and needs owner approval. §15 is the pending
  update.

---

## 15. Pending ClickUp update (no ticket exists to receive it)

A workspace search on 2026-08-14 returns **no task** covering the `/verify` + `/reset` landing pages — matching
audit §11.3. Recommended, for the owner/PM to create:

| Proposed work | Owner role | Depends on |
|---|---|---|
| STORY — `/verify` + `/reset` landing pages (Vue 3, marketing SPA) | `/frontend-engineer` | this handoff; §10.3 for resend |
| TASK — `resendVerification` mutation (no-enumeration, rate-limited) | `/backend-engineer` | — |
| SPIKE/DECISION — expose a distinguishable `EXPIRED` for token failures? | product + `/security-reviewer` | unblocks V4 + R5 |
| STORY — desktop sign-up + verify-pending (A11–A13) | `/frontend-engineer` (Tauri) | `86ajy7anx` adjacency |
| STORY — Manage devices page + devices query + `last_seen_at` | `/frontend-engineer` + `/backend-engineer` | §10.4 |
| TASK — device deactivation (`DeviceStatus.REVOKED`, token revoke, audit, slot release) | `/backend-engineer` | being ticketed; §10.5 |

---

## 16. Independent design-QA

**Not yet run.** Per the protocol used for `ACCOUNT-SETUP-HANDOFF.md` §10, a separate read-only reviewer should
inspect all 22 rendered frames against §5 (state matrix), the API contract in §9, and the two invariants in §1
(never-blank, no-enumeration) before this is treated as accepted.

Self-verification completed: all 22 frames rendered and inspected at readable zoom; no clipped text, no
collapsed auto-layout, no overlapping frames (checked programmatically — 0 overlaps across 19 web frames);
variable collection unchanged at 1 collection / 19 variables, so no parallel token set was introduced.
