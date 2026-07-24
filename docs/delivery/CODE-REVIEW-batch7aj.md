# Code Review — Batch 7aj (mDNS host discovery)

- **Scope:** story `86ajp0b0t` remainder — the phone finds nearby hosts (`_selahcue._tcp`) instead of typing an address: host-side mDNS advertising + a mobile "Nearby hosts" list that pairs via the existing code+approval path.
- **Method:** independent adversarial review via the Workflow tool (run `wf_bd3f4a1c-0b4`, 6 agents; security + lifecycle + platform lens, cross-checked against the actual iOS/Android manifests) → per-finding verification. No self-approval.
- **Raised → confirmed → unique:** **5 → 5 (A–E)** · 0 refuted.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | **Rogue-host phishing:** mDNS supplied the cert pin, so the code+approval trust the network chose the pin — a rogue advertising `_selahcue._tcp` with its own pin could harvest the real host's single-use code and pivot to Producer control. The QR path binds host+pin+code atomically; discovery decoupled them | a **short-authentication-string** gate: the host prints its pin **fingerprint** (`AB12-CD34-EF56`), the phone shows the discovered fingerprint, and the pairing code is disclosed **only after the operator confirms they match** (a rogue's fingerprint won't match the real host's display). The advertised host name carries the fingerprint too. Fingerprint format pinned identically in Rust + Dart tests |
| B | high | iOS 14+: no `NSLocalNetworkUsageDescription` / `NSBonjourServices` — the browse was silently dead on iOS | both keys added to `Info.plist` (service `_selahcue._tcp`) |
| C | med | Android: `CHANGE_WIFI_MULTICAST_STATE` missing + no MulticastLock — multicast dropped | permission added to the manifest; the runtime MulticastLock (native) is the recorded remainder for on-device QA |
| D | low | mDNS advertised a single guessed A-record (wrong on multi-NIC hosts) and never auto-detected addresses | `enable_addr_auto()` — every up interface address is advertised |
| E | low | Hardcoded instance name collided across hosts | per-run unique instance (`{device}-{port}`); friendly TXT name carries the fingerprint |

## Verification after remediation

- `cargo test --workspace`: **263 passed** (fingerprint format pinned); `flutter analyze` clean; `flutter test`: **23** (fingerprint mirror + discovery parsing + QR-equivalent invite). Clippy + `cargo deny` green; operator clean.
- Discovery remains **best-effort** by design: an mDNS-hostile network just yields an empty list; the QR and manual-paste paths are unchanged and fully safe.

## Residual notes (recorded on `86ajp0b0t`)

- **Android MulticastLock** runtime acquisition (native MethodChannel) — the manifest permission landed; the lock needs a real device to wire+validate.
- **On-device phone QA** (a real camera scan + a real Nearby-hosts browse on iOS and Android) is the story's standing open item.
- Re-advertising on a mid-session IP change is out of scope (documented).
