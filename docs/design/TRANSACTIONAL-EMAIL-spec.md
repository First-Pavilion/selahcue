# Transactional email templates — design handoff

- **Status:** Design complete, implementation-ready
- **Date:** 2026-08-14
- **ClickUp:** [86ak0qd9u](https://app.clickup.com/t/86ak0qd9u) · epic [86ajy5v6k](https://app.clickup.com/t/86ajy5v6k)
- **Goal contract:** `docs/delivery/goals/TASK-86ak0qd9u-transactional-email-templates.md`
- **Grounding:** DEC-007 / ADR-0023 · `DESIGN-TOKENS.md`
- **Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ`, page **Transactional Email** (`719:132`)

| Email | Frame node | Trigger | TTL |
|---|---|---|---|
| Verify your email address | `719:133` | `send_email_verification` | 24h (`ACCOUNT_EMAIL_VERIFY_TTL_SECONDS`) |
| Reset your password | `720:124` | `send_password_reset` | 1h (`ACCOUNT_PASSWORD_RESET_TTL_SECONDS`) |
| Someone tried to sign up with your address | `720:136` | `send_account_exists` | n/a — carries no token |

These three are the **only** emails SelahCue sends today. `EmailSender` (`apps/accounts/services.py:220`) is a no-op, so signup currently cannot complete — a user never receives a verification link. This design is what the Celery worker will send.

## Why light-mode, when the product is dark

SelahCue's UI is dark (`bg/base #0e1116`). These emails are **light**, deliberately.

Dark HTML email is a known trap: Gmail (Android/iOS) and Outlook apply their own colour inversion to email bodies, and they do it to *parts* of a document rather than the whole. A dark-designed email routinely arrives with inverted text on a non-inverted background — black on black. An unreadable verification link is a worse failure than an off-brand one, and this is the single most security-sensitive message the product sends.

Brand identity is carried by the wordmark and `accent/brand #5b6bd6` on the CTA instead.

## Palette

Added to the existing **SelahCue Color** collection under an `email/` prefix, so email colours are traceable and never drift into product surfaces (they are scoped to fills/text only).

| Variable | Hex | Use |
|---|---|---|
| `email/page-bg` | `#f4f5f7` | Client viewport behind the card |
| `email/surface` | `#ffffff` | Card |
| `email/border` | `#e2e5ea` | Card border |
| `email/text` | `#1a1d23` | Headings, primary copy |
| `email/text-muted` | `#5c6470` | Body, expiry, footer |
| `email/link` | `#4453b8` | Raw URL fallback |
| `email/warn-surface` | `#fdf3dd` | Security notice band |
| `email/warn-text` | `#7a4a00` | Security notice copy |
| `accent/brand` *(existing)* | `#5b6bd6` | CTA fill, white label |

## Accessibility

Contrast **computed**, not eyeballed — every pair below was calculated with the WCAG 2.x relative-luminance formula.

| Pair | Ratio | AA |
|---|---|---|
| `email/text` on `email/surface` | **16.88:1** | PASS |
| `email/text-muted` on `email/surface` | **5.98:1** | PASS |
| `email/text-muted` on `email/page-bg` | **5.48:1** | PASS |
| White on `accent/brand` (CTA) | **4.65:1** | PASS |
| `email/link` on `email/surface` | **6.61:1** | PASS |
| `email/warn-text` on `email/warn-surface` | **6.78:1** | PASS |

The CTA at 4.65:1 clears AA for all text sizes but has the least headroom. **Do not darken the label or lighten the button** without recomputing.

Also required:
- CTA padding gives a ≥44px tap target.
- Logo `<img>` needs `alt="SelahCue"` — never empty, it is the sender identity.
- Set `lang="en"` on the root element.
- No meaning conveyed by colour alone: the security band leads with words, not just amber.
- Reading order matches visual order (single column, so free — do not add floats).

## Build constraints

Email HTML, not web HTML:

- Table-based layout, **inlined** CSS (no `<style>`-only rules; Gmail strips `<head>`).
- System font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`. **Inter is the Figma rendering font only** — do not attempt a webfont.
- Single column, max **600px**, centred, fluid below 600.
- No flexbox, grid, JavaScript, or load-bearing background images.
- Bulletproof button (table cell with padding and background colour), not a styled `<a>` — Outlook ignores padding on inline anchors.

## Dark mode

Support it, but never depend on it.

```css
@media (prefers-color-scheme: dark) {
  .card    { background: #1e232c !important; }
  .text    { color: #eef1f6 !important; }
  .muted   { color: #9aa4b2 !important; }
  .page-bg { background: #0e1116 !important; }
}
```

Add `<meta name="color-scheme" content="light dark">` and `<meta name="supported-color-schemes" content="light dark">`.

**The failure mode to test for:** Gmail and Outlook ignore the media query and force-invert instead, which can leave white text on a white card. Set explicit background colours on **every** container — an inherited or absent background is what gets inverted independently of its text. Verify in Gmail iOS/Android dark mode specifically; Apple Mail is the well-behaved one and will not surface the bug.

## States

Three per email. There are no loading, empty, or permission states — an email is a static delivered artefact.

| Email | Default | Link expired | Plain-text fallback |
|---|---|---|---|
| Verification | As designed | Landing page says the link expired and offers to resend; the email itself is unchanged | Below |
| Password reset | As designed | Landing page says expired, offers to request a new reset. **Must not** reveal whether the address has an account | Below |
| Account-exists | As designed | n/a — no link, nothing to expire | Below |

Expiry is handled by the **landing page**, not the email — the email cannot know its own age when opened. Those two landing states belong to the desktop/web sign-in work (slice 4, [86ajy7anx](https://app.clickup.com/t/86ajy7anx)) and are noted here so they are not lost.

## Copy deck

Every user-visible string. No placeholders.

### 1 — Verify your email address

- **Subject:** `Verify your SelahCue email address`
- **Preheader:** `Confirm this address to finish setting up your SelahCue account.`
- **H1:** Verify your email address
- **Body:** Thanks for creating a SelahCue account. Confirm this address so we know we can reach you — it is how we send password resets and important service notices.
- **CTA:** Verify email address
- **Fallback:** Button not working? Paste this link into your browser: `{verify_url}`
- **Expiry:** This link expires in 24 hours. If it has already expired, sign in and request a new one.
- **Not-requested:** Did not create a SelahCue account? Ignore this email — no account is active until this address is verified.
- **Footer:** SelahCue · Sent because someone signed up with this address.

### 2 — Reset your password

- **Subject:** `Reset your SelahCue password`
- **Preheader:** `Choose a new password. This link expires in 1 hour.`
- **H1:** Reset your password
- **Body:** We received a request to reset the password for this SelahCue account. Choose a new one using the button below.
- **CTA:** Choose a new password
- **Fallback:** Button not working? Paste this link into your browser: `{reset_url}`
- **Expiry:** This link expires in 1 hour and can be used once. Request a new one if it has expired.
- **Security band:** Did not request this? Your password has not changed and no action is needed. If you keep receiving these, contact your church administrator.
- **Footer:** SelahCue · Sent because a password reset was requested for this address.

### 3 — Someone tried to sign up with your address

- **Subject:** `Someone tried to sign up with your SelahCue address`
- **Preheader:** `An account already exists. Nothing has changed.`
- **H1:** Someone tried to sign up with your address
- **Body:** A SelahCue signup was attempted using this email address, but an account already exists for it. No new account was created and nothing has changed.
- **If it was you:** If that was you, just sign in as normal — there is no need to sign up again. Forgotten your password? Use "Forgot password" on the sign-in screen.
- **Security band:** If it was not you, someone may be probing for accounts. Your account is untouched and no link in this email can access it. Consider changing your password from the sign-in screen.
- **Footer:** SelahCue · Sent because someone attempted a signup with this address.

> ### ⚠ Design constraint — account-exists carries no link
>
> This email intentionally has **no button and no tokenised URL**. It is a warning to the address
> owner, not a credential.
>
> Adding a "sign in" link here would undo the no-enumeration design: signup returns an identical
> response whether or not the address is registered, and the *only* signal that an account exists
> is this email arriving in the real owner's inbox. A link would hand that signal to an attacker
> probing addresses. The constraint is annotated on the Figma canvas so it survives a redesign.

## Plain-text fallbacks

Required — a `multipart/alternative` text part materially affects deliverability and some clients show it by preference.

```
SelahCue — Verify your email address

Thanks for creating a SelahCue account. Confirm this address so we know we can
reach you — it is how we send password resets and important service notices.

Verify your email address:
{verify_url}

This link expires in 24 hours.

Did not create a SelahCue account? Ignore this email — no account is active
until this address is verified.

SelahCue
```

```
SelahCue — Reset your password

We received a request to reset the password for this SelahCue account.

Choose a new password:
{reset_url}

This link expires in 1 hour and can be used once.

Did not request this? Your password has not changed and no action is needed.

SelahCue
```

```
SelahCue — Someone tried to sign up with your address

A SelahCue signup was attempted using this email address, but an account
already exists for it. No new account was created and nothing has changed.

If that was you, sign in as normal. Forgotten your password? Use
"Forgot password" on the sign-in screen.

If it was not you, your account is untouched and no link in this email can
access it. Consider changing your password.

SelahCue
```

## Open, owned elsewhere

| Item | Owner |
|---|---|
| Email provider + credentials (`MAIL_HOST`/`MAIL_PORT`/`MAIL_USERNAME`/`MAIL_PASSWORD`) | Owner |
| Sending domain, `DEFAULT_FROM_EMAIL`, SPF/DKIM/DMARC | Owner |
| `{verify_url}` / `{reset_url}` web routes — **no such route exists yet** | Backend, delivery slice |
| Expired-link landing pages | Slice 4 ([86ajy7anx](https://app.clickup.com/t/86ajy7anx)) |
| Localisation — layout leaves ~30% string-expansion room | Later |

Locally, mailhog on port 1025 (per the yharah compose pattern being adopted) catches everything, so the templates can be verified end to end before any provider exists.
