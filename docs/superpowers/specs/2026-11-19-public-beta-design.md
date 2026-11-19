# SelahCue Public Beta — 15 December 2026 (design)

Status: approved by the owner on 2026-11-19.

## Context
The core of SelahCue is in place. It has plans, slides, themes, scripture, preview and live output, stage output, recovery and mobile control. The platform API has accounts, sign-up, device activation and signed offline entitlements. Nothing has been published: `implementation/marketing/public/releases/current.json` is `unpublished`.

The plan on file (17 Nov, `docs/superpowers/specs/2026-11-17-public-free-deployment-guide.md`) is a Free public release with limits and a watermark. The owner has now chosen a **public beta**. Anyone can download it, everything is unlocked, and it launches on 15 Dec 2026. This design replaces the 17 Nov plan's licensing and scope sections. Its deployment mechanics (Coolify, DO Spaces, publisher) are kept.

## Owner decisions (from this conversation)
1. **Audience:** a public download, with open sign-up on the website.
2. **Licensing:** everything is unlocked in the beta. No payments, no watermark, no output or device limits.
3. **Cloud AI is included, with weekly caps per church:** 3 hours of cloud transcription and 5 AI sermon notes. Allowances reset on Monday.
4. **New features required:** signed auto-update, multiple timers with a configurable TIME UP (FR-056/058/059), per-layer clear (FR-078), scripture history and favourites (FR-031), and plan export/import bundles (FR-139).
5. **Out of the beta:** video and audio playback (DEC-003 stands), payments and billing, and enforcement of paid tiers.
6. **Installers:** Windows signed (Authenticode); macOS signed with Developer ID and notarised (this reverses the waiver); Ubuntu 24.04 `.deb` unsigned.
7. **Mobile:** a full public App Store and Google Play release.
8. **Launch:** one launch day, about **15 Dec**. Go/no-go is on **12 Dec**. If a piece isn't ready, the launch goes ahead without it. Cloud AI gets switched on from the server later, and the phone app follows once it's approved.
9. **Legal:** Nathan finishes the privacy policy and terms drafts. The owner signs them off for the beta. A lawyer reviews them later.

## Approaches considered
- **A. Single launch on about 15 Dec (chosen).** It gives one clear announcement. The risk of a slipping piece is reduced by decision 8: the launch goes ahead without that piece.
- B. Staged: desktop on about 8 Dec, cloud AI and mobile on about 20 Dec. It has the least calendar risk, but the owner preferred a single launch moment.
- C. Harden now and ship the new features in January. The date is safe, but this isn't the beta the owner described.

## Design by workstream

### W1. Beta licensing (small; it reuses what exists)
- Add a **BETA plan** to the catalogue (`implementation/api/selahcue_api/apps/catalogue/`, new data migration alongside `0007_weekly_catalogue_reference_data.py`). It gets all grants, no watermark, unlimited outputs, a high device limit, and weekly allowances of 3 hours of cloud STT and 5 notes.
- Assign BETA to new self-service sign-ups. Today they get the Free licence via `apps/license_keys/free_lifecycle.py`. This also settles DEC-014's LEGACY fallback for the beta: the fallback becomes BETA while the beta runs.
- The entitlement already expires; the beta's end date is set as that expiry. **My call:** the beta ends on **31 Mar 2027**, and that date is shown on the website and in Account Setup (`crates/selahcue-operator/src/account/`). After it, DEC-009's 7-day grace applies and the account falls back to Free. The grace envelope itself isn't built yet (`devices/services.py:254`). It must exist before 31 Mar, not before 15 Dec.
- The desktop app still enforces nothing. The crate's "never blank" rule in `selahcue-licensing/tests/test_never_blank.rs` stays. Only the cloud allowance is enforced, on the server, by the existing ledger in `apps/usage/` and `/v1/quota`.
- Wire the marketing `AccountView.vue` to the existing `accountOverview` query and remove the mock data. The page should show the plan, the beta end date, devices, and the AI allowance used this week. Replace Free-offer copy (`lib/content/freeOffer.ts`, `PricingView.vue`) with beta copy.

### W2. Cloud AI to production (the critical path, so start now)
- Qualify Deepgram (STT) and OpenAI (notes) under the "Public cloud boundary" in `DEPLOYMENT.md` and ADR-0028. That covers the provider spikes, and OI-8 to OI-16 as they apply to the beta.
- Deploy the provider workers and secret mounts in `implementation/docker-compose.prod.yml`. Remove the `PCFG_NOTES_RUNTIME_UNAVAILABLE` refusal in `providers/bootstrap.py` once it's qualified.
- Change `cloud-stt` and `openai-notes` from `RELEASE: UNSAFE` to `SAFE`. That means updating the Cargo feature tags and the Makefile's `RELEASE_UNSAFE_FEATURES`; `scripts/check_launch_reachability.py` checks both. They are compiled into the release build.
- **There must be a server-side switch** that turns cloud AI off, either for everyone or for one org, without a new build. This is what makes "launch without it" work.
- Change the installer publisher's cloud-acceptance gate (`scripts/publish_installers.py`). Publishing must be possible while cloud AI is switched off on the server.

### W3. Desktop features
- **Auto-update:** the Tauri updater plugin in `selahcue-operator` signs updates with a separate Ed25519 updater key in owner custody. The feed is a JSON file next to `releases/current.json` on DO Spaces, written by `publish_installers.py emit-manifest`. Updates are offered only when nothing is live. The app never restarts during a service. This replaces the disabled "coming soon" button (`dist/index.html:1621,1932`), ticket 86ak0qmza.
- **Timers:** turn the single `timer: Option<Timer>` (`selahcue-app/src/controller.rs:102`) into a bounded set. **My call:** at most 8 timers. Each timer has a configurable TIME UP message and behaviour. Ticket 86ajpzhbh.
- **Per-layer clear:** route `ClearLayer` to clearing that one layer rather than clearing everything (`selahcue-desktop/src/main.rs:3925`). Ticket 86ajpy59e.
- **Scripture history and favourites:** enable the disabled controls (`dist/settings-scripture.js:14-19`). The history is bounded (**my call:** the last 100 entries). Ticket 86ak0qn2u.
- **Plan export/import bundles:** import goes through the existing `selahcue-import/src/safe_extract.rs`. Ticket 86ak0qn15.
- Follow the repo rules: every buffer is bounded with a test that actually fails if the bound breaks, and the LAN protocol fixtures change together with their tests.

### W4. Installers and signing (start the paperwork this week)
- **Windows:** add Authenticode signing to `.github/workflows/windows-installer.yml`. **My call:** use Azure Trusted Signing if the company is eligible. Otherwise use an OV certificate. The owner applies for one of them now, because issuing takes 1–3 weeks.
- **macOS:** use a Developer ID certificate on team 3N4DASU994 with `hardenedRuntime: true` and notarise and staple the app (`tauri.macos.conf.json`, `scripts/build_macos_installer.py`). Update `docs/release/pilot-download-grants.md` so its policy matches. Builds stay local on a Mac, which keeps macOS CI minutes at zero.
- **Linux:** keep the unsigned `.deb`.
- Update the website download page so it lists each platform's status honestly.

### W5. Platform deployment
Follow `DEPLOYMENT.md` "Release prerequisites":
- production Coolify deployment
- DNS and TLS
- SMTP
- the entitlement signing key (`e506b735`) held by the owner
- backups and a rehearsed restore
- edge rate limits before sign-up opens

Test the whole sign-up → verify → activate → refresh flow on staging first.

**My call:** add Sentry crash reporting, using the existing `SENTRY_DSN`. It goes in the API, the desktop app (Rust panic hook plus the existing crash journals) and mobile. Events are scrubbed of personal data, and the privacy policy says so.

### W6. Mobile store release
Follow `docs/release/mobile/RELEASE-CHECKLIST.md`:
- the Play upload keystore (`ANDROID-UPLOAD-SIGNING.md`)
- the iOS distribution certificate and profiles
- the Play Data safety form and the App Store privacy labels
- the final store listing and screenshots (`STORE-LISTING.md`)
- a test on a real device

**Submit to both stores by 5 Dec**, ahead of Apple's holiday slowdown. The 4-role access model stays for the beta (the 7-role model is ticket 86ajxuf81).

### W7. Legal and support
- Nathan fills the placeholders in `docs/legal/`: PRIVACY 9, TERMS 10, platform privacy 12, notes 30. Add the beta terms (no warranty, the 31 Mar end date, the AI allowances) and the Sentry disclosure. The owner signs them off, and they are published without noindex.
- Write a short support page for installing, activating, pairing the phone, and what to do when something breaks.

### W8. Quality gate before go/no-go
- Run the 12-hour soak and the time-to-first-slide check from PRD §32. Neither has been run so far.
- Run the installed-app acceptance on all three platforms.
- On 12 Dec, go/no-go means all of the following: W1, W3, W4, W5 and W7 are done, and `make ci` is green. W2 and W6 can follow after launch.

## Schedule
| Week | Milestone |
|---|---|
| 19–22 Nov | Start the Windows certificate application and the Apple and Play accounts and keystore. Start the Deepgram and OpenAI qualification. Create the tickets. |
| 23 Nov–5 Dec | Build W1, W3, W5 on staging, Sentry, and the legal drafts. **5 Dec: release candidate freeze and the store submissions.** |
| 6–11 Dec | Soak test, installed-app acceptance, fix only. |
| 12 Dec | Go/no-go. |
| 15 Dec | Launch: publish the manifest and open sign-up. |

## Process
- Each piece of work gets its own ClickUp ticket, branch, worktree and PR against `main`.
- Diego (delivery) creates a **Public Beta 15 Dec** milestone under Build Control `86ajnx548` and updates BUILD_STATE.md.
- Run the full review gate (code, security, QA, and performance where it applies) before each PR is merged.
- Once this design is approved, commit it to `docs/superpowers/specs/2026-11-19-public-beta-design.md` in a worktree, then write the implementation plan, one plan per workstream.

## Left to the builder
- Timer UI layout, the export bundle format details, the update prompt wording, and the Sentry sampling rates.

## Verification
- `make ci` is green, and `scripts/check_launch_reachability.py` passes once the cloud features are reclassified.
- On staging, the flow works end to end: sign up → verify email → activate the desktop app → the Beta plan shows the 31 Mar end date → use 3 hours of STT and the server refuses more → on Monday the allowance resets.
- Updates: install version N, publish version N+1, and N updates itself while nothing is live. It does not update while something is live.
- Signing: on Windows, `signtool verify` passes and SmartScreen shows no warning. On macOS, `spctl -a -vv` and `stapler validate` pass.
- The 12-hour soak report and the time-to-first-slide report are attached to the go/no-go ticket.
