# Design 2.0 parity audit — Remote Control · Devices

**Role:** UI/UX Designer (Uma) · **Date:** 2026-09-20 · **Type:** read-only audit + gap spec
**Goal Contract:** `docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ`, frame `359:124` "Remote Control · Devices — Design 2.0"
(1760×1000)
**Status:** point-in-time. Figma and `dist/` both move; re-run before acting on a row older than a week.

## What was audited

`#surface-remote` (`index.html:1323-1397`) plus all of `remote.js` (354 lines, read in full) and the
`.rc-*` rules in `app.css`. **This is the desktop host/pairing side** — the operator console screen that
mints a pairing QR, approves/denies requests, and manages paired devices' roles. It is not the mobile
controller app (already covered by `docs/design/MOBILE-2.0-SPEC.md`). Confirmed by grep: no `359:*` id
appears in the three existing desktop parity audits.

## Method

`get_metadata` on `359:124` (one call, full subtree — a single populated mock, no separate states
board), cross-checked against `remote.js`/`app.css` line by line. No bound Figma variables on this
frame.

## Verdict vocabulary

**MATCH** / **DRIFT** / **MISSING** / **EXTRA** / **UNSPECIFIED** / **INTENTIONAL-DEVIATION** /
**A11Y-DEFECT** / **A11Y-CONFLICT**. Severity: **S1** blocks correct/accessible use · **S2** visible
parity break · **S3** cosmetic · **S4** informational.

---

# Summary

**9 numbered findings: RCD-001…RCD-009.**

| Verdict | Count |
|---|---|
| MATCH | 2 |
| DRIFT | 3 |
| MISSING | 1 |
| EXTRA | 1 |
| INTENTIONAL-DEVIATION | 1 |
| A11Y-DEFECT | 1 |

Severity: **0 × S1**, 3 × S2, 5 × S3, 1 × S4. (No S1 on this surface — the recurring gradient/white-text
defect found on every other audited surface this round does **not** appear here at all, on either side.)

## Headline

Remote Control · Devices is a **close structural match** to its single Figma mock — QR pairing card,
fingerprint readout, expiry countdown, pending-request approval row, paired-devices table — and the
implementation is, if anything, more careful than the frame about security-adjacent honesty (the QR
canvas paints a real, backend-generated code or explicitly says it can't, never a placeholder graphic
that looks scannable but isn't). Two things stand out:

1. **Role naming is a different vocabulary on each side, by design.** Figma's mock shows illustrative
   role labels ("Scripture Operator", "Production Op.", "Worship Leader", "Observer"); the shipped code
   uses the actual `selahcue-lan` RBAC roles (Operator/Producer/Assistant/Viewer) and explicitly refuses
   to ever assign "Operator" to a remotely-paired device. **RCD-005, INTENTIONAL-DEVIATION** — this is
   the desktop-Remote-Control analogue of the already-known mobile role-naming case
   (`docs/delivery/CODE-REVIEW-batch-mobile-design2-b.md`), and this audit records it the same way:
   code is the real RBAC model, Figma's labels are illustrative mock content.
2. **This is the one surface in the round where the recurring gradient/white-text defect appears on
   neither side.** The `↻ New code` button (**RCD-003**) is flat in both the frame and the code — worth
   naming explicitly given every other audited surface this round (Theme Designer, Service Plan,
   Preservice, Download modal) found at least one instance of it.

---

# Frame `359:124`

## Header

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Brand row + "Remote Control" surface label | `359:126-132` | Global app header (same relocation pattern as every other audited surface) | MATCH | S4 |
| **RCD-001** | "N devices paired" pill with status dot | `359:133-136`: 141×25, live green dot + count + `▾` | `#rc-count`/`#rc-count-n` (`index.html:1334-1337`), `.rc-count-dot { background: var(--sc-preview) }` — the count is live, updated by `renderCount()` (`remote.js:211-214`); the trailing `▾` caret in Figma implies a dropdown, but **no such affordance exists** in code (a static, non-interactive pill) | DRIFT — the caret reads as decorative-only in the frame too (no described behaviour), so this is likely a minor mock artifact rather than a real missing control | S4 |

## LEFT — Pair a device

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | "Pair a device" heading + "Open the SelahCue app on a phone or tablet and scan this code." | `359:140-141` | `index.html:1343-1345`, word-for-word | MATCH | — |
| — | QR canvas, 192×192 | `359:142-143` | `#rc-qr` `width="192" height="192"` (`index.html:1348-1349`) | MATCH | — |
| **RCD-002** | QR content | Implied to be a real, scannable code | `drawQR()` (`remote.js:124-148`) paints a **real** module grid from the backend's own tested encoder over the actual `selahcue://pair?...` invite URI — and when the host supplies no invite (an older host, or one bound only to loopback), it **draws explanatory text instead of a fake code**: "Scan the code shown on the output window to pair a device." The code comment is explicit that this is deliberate: a phone-unscannable placeholder that *looks* like a QR code would be worse than admitting there isn't one. | **MATCH** (+ meaningfully more careful than a literal reading of the frame requires) | — |
| — | Fingerprint row: "Fingerprint" label + "7F · 2A · 9C · E1" | `359:253-255` | `#rc-fp` (`index.html:1354-1355`), populated by `genCode()` (`remote.js:151-171`) from the real host cert fingerprint, truncated to a readable prefix with the full value on `title` hover | MATCH | — |
| — | "⏱ Single-use · expires in 0:52" | `359:257-258` | `#rc-expiry-txt`, `tickCountdown()` (`remote.js:175-185`) — a real, ticking, bounded single `setInterval`, with an explicit `rc-expired` state ("code expired — generate a new one") the static frame doesn't draw | MATCH (+ EXTRA state) | — |
| **RCD-003** | `↻ New code` button | `359:259-260`: implied styling, drawn as a plain button in the mock with no gradient | `#rc-newcode` `.rc-newcode` (`app.css:6174-6180`) — **flat** `--sc-elevated` fill, `--sc-text` label, hover to `#232733`. **No gradient anywhere on this control.** | MATCH — see **A11Y** below for why this control is notable *because* it avoided the defect other surfaces' equivalent primary actions did not | — |
| — | "🔒 TLS 1.3 · QR-pinned host fingerprint · pairing keys never leave this machine." | `359:261-263` | `.rc-note-ok` (`index.html:1365-1368`), word-for-word, on `--sc-preview-soft`/`--sc-preview` | MATCH | — |

## RIGHT — Pending request + paired devices

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | "PENDING REQUEST" overline | `359:265` | `.rc-section-label`, `index.html:1373` | MATCH | — |
| — | Pending card: 📱 icon + name + "wants to pair · verify fingerprint…" + Role select + Approve/Deny | `359:266-279`: "Anna's iPhone", "wants to pair · verify fingerprint 7F·2A·9C matches the phone" | `renderPending()` (`remote.js:216-247`): identical structure — icon, name, `"wants to pair" + platform + " — approve only a device you recognize"` (copy differs in wording from the frame's verify-fingerprint phrasing but carries the same caution), a role `<select>` defaulting to `DEFAULT_ROLE = "producer"`, Approve/Deny buttons each with a named `aria-label` | MATCH structurally; DRIFT on the exact pending-card copy (see **RCD-004**) | S3 |
| **RCD-004** | Pending-card caution copy: "verify fingerprint 7F·2A·9C matches the phone" | `359:271` | `"wants to pair" + (platform ? " · " + platform : "") + " — approve only a device you recognize"` (`remote.js:228-229`) | DRIFT — the frame's copy ties the caution to a concrete, checkable action (match the fingerprint shown on the phone); the shipped copy is a general caution with no fingerprint cross-check instruction. The fingerprint *is* shown elsewhere on the same screen (the left column), but the pending card itself doesn't point the operator at it | S3 |
| — | "PAIRED DEVICES" overline + table | `359:280-360` | `.rc-section-label` + `.rc-table` (`index.html:1376-1387`), columns DEVICE / ROLE / LAST SEEN / STATUS / (actions) | MATCH | — |
| **RCD-006** | Device cell: 📱 + name + "platform · ip" | `359:296-300` | `renderRows()` (`remote.js:266-307`): `.rc-devname`/`.rc-devmeta`, `mapDevice()` builds `(d.platform || "controller") + (d.pinned ? " · pinned" : "")` — **no IP address** in the meta line | DRIFT — Figma's mock shows a LAN IP (`192.168.1.20`) in the device meta; the code shows platform + pinned status instead. Possibly a deliberate privacy-conscious omission (an IP is more identifying than needed for this UI) rather than an oversight | S3 |
| — | Role select, coloured pill per role | `359:302-305` | `roleSelect()` (`remote.js:188-208`): a real `<select>` styled per-role via `.rc-role-<id>` classes (`app.css:6231-6234`) — Operator gold, Producer green, Assistant violet, Viewer grey | MATCH on mechanism | — |
| **RCD-005** | Role vocabulary | Figma's mock role values: **"Scripture Operator"**, **"Production Op."**, **"Worship Leader"**, **"Observer"** (`359:274`, `359:304`, `359:327`, `359:350`) | `ROLES` (`remote.js:20-25`): the real `selahcue-lan` RBAC roles — **Operator, Producer, Assistant, Viewer** — with `ASSIGNABLE` explicitly excluding `operator` (*"a remotely-paired device is capped at Producer (Operator is refused by the host), so the assignable roles are Producer/Assistant/Viewer"*, `remote.js:11-12, 28`) | **INTENTIONAL-DEVIATION** — the code implements the real, backend-enforced RBAC model; Figma's four labels are illustrative mock content with no 1:1 mapping onto the actual roles (only "Production Op." ↔ "Producer" and "Observer" ↔ "Viewer" are even loosely recognisable). This is the desktop-surface counterpart to the already-known mobile 4-vs-7-role naming case. **Do not "fix" the code toward Figma's labels** — RISK-205's logic applies: the real permission model is the source of truth | S2 (recorded as a decision, not a defect) |
| — | Last seen: "just now" / "2 min ago" / "18 min ago" | `359:307/330/353` | `humanizeSeen()` (`remote.js:61-67`): `"just now"` / `"Ns ago"` / `"N min ago"` / `"Nh ago"` — matches the frame's format exactly, derived from real `idle_secs` | MATCH | — |
| — | Status pill: Online / Idle (green/amber dot + text) | `359:309-311, 332-334, 355-357` | `STATUS` map (`remote.js:30-34`) + `statusFor()` (`remote.js:68-73`): three real thresholds (`<30s` online, `<300s` idle, else offline) driving `.rc-status-online`/`-idle`/`-offline` (`app.css:6262-6267`) — text label plus dot, not colour alone | MATCH (+ a third `offline` state the frame's two-row mock doesn't show) | — |
| — | Revoke action | `359:313-314, 336-337, 359-360` | `wireRevoke()` (`remote.js:249-264`): a real **two-click arm/confirm** pattern (label flips to "Confirm?" for 4s, then reverts) — the frame draws a single static "Revoke" button with no visible confirm step | EXTRA — the implementation is *more* cautious than the frame for an irreversible, safety-relevant action (a device losing live-console access mid-service) | — |
| — | Footer note: "Roles are enforced server-side… deny-by-default… logged in the audit trail." | `359:361-363` | `.rc-note` (`index.html:1388-1393`), word-for-word | MATCH | — |

## States Figma does not draw, that the code adds

| # | Component | Verdict | Sev |
|---|---|---|---|
| **RCD-007** | Empty pending / empty paired-devices states (`"No pending requests…"` / `"No devices paired yet — scan the code on a phone to add one."`, `remote.js:220, 270`) — Figma's single mock always shows one pending request and three paired devices | EXTRA (necessary — the real surface starts empty every time) | S4 |
| **RCD-008** | No-host-connection state: with `INVOKE` absent (opened outside the Tauri shell), every `invoke()` call rejects and the surface silently renders empty rather than erroring (`remote.js:37-43, 108-112`) — no host-connection banner exists, unlike Pre-service Check's explicit "no output window" verdict | MISSING (arguably; Figma has no equivalent frame either, so this is a genuine coverage gap rather than a drift) | S3 |

---

# Accessibility

## A11Y-1 — A11Y-CONFLICT (the frame is the defect — do not build it as drawn)

**None found on this surface.** The one gradient-styled control this audit expected to find
(`↻ New code`) turned out to be **flat**, both in the frame and in the code (RCD-003 above). Recorded
here explicitly because every other surface in this round found at least one instance of the recurring
gradient/white-text defect somewhere — this is the one clean exception worth naming rather than silently
omitting.

## A11Y-2 — Real defect

| # | Where | Measured | Why it fails | Fix |
|---|---|---|---|---|
| **RCD-009** | `.rc-role-viewer` (`app.css:6234`): `background-color: var(--sc-elevated)`, `border: 1px solid rgba(107, 115, 131, 0.5)`, `color: var(--sc-text-muted)` — the Viewer-role select pill | `--sc-text-muted #6B7383` on `--sc-elevated #1C1F28` ≈ **3.45:1** (the pre-existing elevated-surface figure already measured in the Presentation audit's A11Y-3) | The role pill's label is the role NAME itself — "Viewer" — which is essential, decision-relevant text (an operator deciding whether to grant more access needs to read it), not supplementary micro-copy. At the select's implied ~13px this fails AA-normal. | Promote `.rc-role-viewer`'s ink to `--sc-text-secondary` (7.40:1+), matching the `PME-006…011` promotion pattern already applied elsewhere for essential small text that was sitting on the muted tier by omission rather than design. |

## A11Y-3 — Clear

- Status (Online/Idle/Offline) pairs a coloured dot with a text label throughout — WCAG 1.4.1.
- Role changes announce via `aria-live` (`#rc-live`, `announce()`, `remote.js:55-58`) — e.g. *"Booth
  iPad is now Assistant"* — so a screen-reader user gets the outcome of a select change without having
  to re-read the row.
- The Revoke two-click confirm updates both `textContent` and `aria-label` on arm (`"Confirm?"` /
  `"Confirm revoke <name>"`) — not a colour-only "armed" state (`.armed` also changes fill, but the
  label change is what carries the information).

---

# Open questions

- **RCD-OQ-1 (product, already effectively answered — recorded for completeness).** RCD-005 — confirm
  the four real RBAC roles (Operator/Producer/Assistant/Viewer, with Operator never assignable to a
  remote device) are the intended, final model, and that Figma's illustrative labels should be corrected
  to match rather than the reverse. Given the code's own comment states this is enforced *server-side*,
  this reads as settled — flagged as a question only because no doc was found explicitly recording the
  Figma-side correction as done.
- **RCD-OQ-2 (design, minor).** RCD-004 — should the pending-request card's caution copy explicitly
  reference the fingerprint shown in the left column (as Figma's copy does), so the two panels visibly
  cooperate on the same verification step?
- **RCD-OQ-3 (product/privacy).** RCD-006 (device meta line) — is omitting the LAN IP from the paired-
  device row a deliberate privacy choice, or should it be restored to help an operator disambiguate two
  devices with the same platform and name?
