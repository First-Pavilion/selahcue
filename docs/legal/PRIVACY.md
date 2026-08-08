# SelahCue Controller — Privacy Policy

> **STATUS: DRAFT — REQUIRES LEGAL REVIEW before store submission.** This draft is written
> by /mobile-engineer, grounded in the app's *actual* runtime behaviour (verified in code), so
> legal has an accurate technical basis. Replace every `{{PLACEHOLDER}}` and confirm jurisdiction,
> controller/processor roles, and children's-data posture before publishing. Store submission needs
> this hosted at a public URL (Apple App Privacy + Google Data safety forms must match it).

- App: **SelahCue Controller** (mobile companion for the SelahCue desktop presentation app)
- Publisher: `{{LEGAL_ENTITY_NAME}}`, `{{ADDRESS}}`
- Contact: `{{PRIVACY_CONTACT_EMAIL}}`
- Effective date: `{{DATE}}` · Version: 1.0 (draft)

## 1. Summary (plain language)

SelahCue Controller is a **remote control** for a SelahCue desktop running on your church's own
local network. It is **offline-first and LAN-only**: it talks *only* to the desktop you pair it
with, over an encrypted, certificate-pinned connection on your local Wi-Fi. **We do not collect,
transmit, sell, or share your personal data.** There are no accounts, no advertising, no analytics
or tracking SDKs, and no third-party servers involved in normal operation.

## 2. What the app stores on your device

| Data | Purpose | Where | Leaves the device? |
|---|---|---|---|
| Pairing credential (a device id + revocable token) | Reconnect to the paired desktop without re-scanning a QR | OS secure storage (iOS Keychain / Android Keystore) | Only sent to the **paired desktop** over pinned TLS |
| App preferences (keep-screen-awake, haptics, reduce-motion) | Remember your settings | OS secure storage | No |
| Certificate pin / host address of the paired desktop | Trust + reconnect to the correct desktop | OS secure storage | No |

The app holds no account, profile, contacts, photos, location, or advertising identifier.

## 3. What the app transmits

Only **control messages** (e.g. "next slide", "go live", "start timer", "approve scripture") and
read-only state (current/next item, timer, live transcript preview) exchanged with the **paired
desktop on your local network**, over TLS 1.3 with the server certificate pinned by SHA-256. Nothing
is sent to `{{LEGAL_ENTITY_NAME}}` or any third party. The app keeps no analytics or crash-reporting
telemetry by default.

## 4. Sermon audio, transcripts, and notes

Live transcription, scripture detection, and sermon notes are produced and stored **on the desktop**,
not on this mobile app. The controller may *display* a read-only live-transcript preview it receives
from the paired desktop, but it does not record audio or persist transcripts. Retention and any
optional cloud AI features are configured and disclosed **on the desktop**, under the operator's
control.

## 5. Device permissions

| Permission | Why | Notes |
|---|---|---|
| **Camera** | Scan the pairing QR code shown on the desktop | Frames are processed on-device to read the code; no image is stored or transmitted. You can decline and pair via manual invite instead. |
| **Local network** (iOS) | Discover (mDNS) and connect to the desktop on your Wi-Fi | Used only to find and reach the paired desktop. |

The app requests the **least privilege** needed and functions with camera denied (manual pairing).

## 6. Children's privacy

The app is a technical tool for church A/V volunteers and does not knowingly collect data from
children. `{{LEGAL: confirm COPPA/age posture and target audience declaration for the stores.}}`

## 7. Data sharing, sale, and international transfer

We do **not** sell or share personal data, and — because the app operates on your local network —
there is **no international transfer** of your data by the app in normal operation.

## 8. Your rights & data deletion

Because the app stores only local pairing credentials + preferences on your device, you can erase all
app-held data at any time by **disconnecting the device** (About → Disconnect) or uninstalling the
app. An administrator can also revoke the device from the desktop, which invalidates its credentials
immediately.

## 9. Security

Transport is TLS 1.3 with the desktop's certificate pinned by SHA-256 (no reliance on public CAs).
Credentials are held in the OS secure enclave/keystore. Pairing requires the operator to confirm the
device on the desktop.

## 10. Changes & contact

We will update this policy as the app changes and post the revised version at `{{PRIVACY_POLICY_URL}}`.
Questions: `{{PRIVACY_CONTACT_EMAIL}}`.

---

### Store-form crosswalk (for the release manager)
- **Apple "App Privacy":** Data Not Collected (no data leaves the device to us). Declare camera use
  (app functionality, not linked to identity, no tracking). No tracking → no ATT prompt.
- **Google "Data safety":** No data collected or shared. Encrypted in transit (LAN). Data deletable
  via disconnect/uninstall. `{{Confirm against final build before submitting.}}`
