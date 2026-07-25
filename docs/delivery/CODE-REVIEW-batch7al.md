# Code Review — Batch 7al (mobile Producer revamp: tabbed shell + connection flow)

- **Scope:** story `86ajpx7bd` — implement the `/ui-ux-designer` mobile redesign (7ak) in Flutter. Restructured the one crammed `ControllerView` into a **tabbed shell** (bottom `NavigationBar`: Live/Plan/Scripture/Timer via `IndexedStack`) with a **persistent EmergencyStrip** (Blackout/Clear All) above the nav on every tab, a compact top bar, a branded Splash→Connect→Controller flow, and the "Nearby hosts" Connect screen. Plus three owner refines folded in: **single-tap = preview / double-tap = live** (plan + scripture), an **About/connection drawer with Disconnect**, and **scripture autocomplete**.
- **Method:** independent adversarial review via the Workflow tool (run `wf_40675e8e-899`, 13 agents; 3 review lenses — tab-state, connection-flow, a11y-tokens — each finding then adversarially verified by an independent agent instructed to refute). No self-approval.
- **Raised → confirmed → unique:** **6 confirmed (2 were the same denial defect from two lenses) → 5 unique (A–E)** · 3 refuted.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | med | **Command-denial banner never readable:** `act()` set `_error='Not allowed…'`, then its trailing `refresh()` — and the 1s poll — unconditionally did `_error=null` on success, wiping the denial within ~one round-trip (sub-frame on a fast LAN). The RBAC-limited Producer would tap a denied CLEAR ALL/BLACKOUT, see nothing, and hammer it mid-service | split the single `_error` into a **transient `_statusError`** (connection state; cleared by refresh/reconnect) and a **sticky `_denial`** (survives the poll; cleared only by `dismissError()` or when a later command actually goes through). `error` getter prioritises the connection status while reconnecting, else the actionable denial. Regression-tested (3 controller tests) |
| B | med | **Prev/Next transport buttons had no accessible name** — glyph-only `◀`/`▶` on a raw InkWell (no Text, no Semantics); TalkBack/VoiceOver announced "black left-pointing triangle" with no function (WCAG 1.1.1/4.1.2) | wrapped each `_TransportBtn` in `Semantics(button: true, label: 'Previous/Next item', excludeSemantics: true)` so the glyph isn't spoken |
| C | low | **AppBar title blank on an unnamed plan** — `view?.planName ?? _titles[_tab]` only fell back on null, but `planName` defaults to `''` (non-null) once connected, so an empty name rendered `Text('')` on every tab | fall back to the tab title when planName is null **or** empty |
| D | low | **Connect screen "Nearby hosts" never auto-searched** — the promoted primary path told the user to "Pick it below" but no `_discovery.refresh()` ran on entry, stranding a first-run user on "None found…" until they found the refresh icon | kick off `_discovery.refresh()` in `initState` |
| E | low | **Splash could leak the open session** — on the reconnect-success path, if the Launcher unmounted during the 900ms brand delay the `if (!mounted) return` dropped a fully-open pinned-TLS session with no `close()` (no dispose hook) | `unawaited(session.close())` before the `!mounted` early-return |
| — | low | **Custom InkWell controls lacked the button role** (GO LIVE, transport, EmergencyStrip) — folded into A11y fixes B; also wrapped GO LIVE and the BLACKOUT/CLEAR ALL `_EmgButton` in `Semantics(button: true, label: …)` (plain word, not the `■`/`✕` glyph) | same pass as B |

## Refuted (correctly, by the verify pass)

- **Dialog `mounted` guard** — `_pairDiscovered`'s post-`showDialog` write can't throw: the SAS dialog is a same-Navigator route with no disposal path.
- **`outputBlack` #000000 token divergence** — factually accurate but not a defect; the token is the intended on-screen black behind slides, not a claim to mirror the engine surface.
- **NavigationBar animates under Reduce Motion** — false: it's a stock Material 3 `NavigationBar` whose indicator honours `MediaQuery.disableAnimations`; also mislocated to main.dart.

## Verification after remediation

- `flutter analyze`: **clean**. `flutter test`: **29** (was 26; +3 `live_controller` denial-lifecycle tests, +existing autocomplete/widget suites). New `ControllerSession` interface extracted so the controller is unit-testable against a fake without a real socket.
- All six confirmed defects reproduce from the pre-fix code and are closed forward; the refuted three left unchanged with rationale.

## Residual notes (recorded on `86ajpx7bd`)

- **On-device QA** (the tab flow, double-tap-to-live, the About drawer's Disconnect, autocomplete, and a real Nearby-hosts browse) is the story's standing open item — QA steps posted on the ticket.
- Full scripture **verse-list browser** on mobile stays desktop-only by design (mobile stages a reference over the wire); reaching parity needs a scripture verse-list wire path, tracked on the story.
