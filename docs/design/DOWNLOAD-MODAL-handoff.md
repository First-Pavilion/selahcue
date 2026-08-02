# Offline Download Modal — design handoff (Design 2.0)

**For:** frontend-engineer (operator webview, `crates/selahcue-operator/dist/`)
**Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ` → frame **`SPEC — Offline Download Modal (Design 2.0)`** (node `396:124`)
**Goal Contract:** `docs/delivery/goals/TASK-design2-download-modal.md`
**Backend it drives:** `selahcue-stt::fetch_model(asset, cache, |done,total| …)` (progress callback) → integrity verify (FR-156 / ADR-0012) → load; surfaced today only as stderr lines in `selahcue-operator/src/listening.rs`.

## What this is

One reusable modal that shows **first-time download progress** and every failure/recovery state for **offline assets**: the on-device STT (Whisper) model *and* any Bible translation. It replaces the current silent hang on first "Start listening" (and the equivalent on first offline-Bible add). It is **one component**, parameterised — not two modals.

## Parameterisation

```ts
type OfflineDownload = {
  assetKind: 'model' | 'bible';
  name: string;        // "speech model" | "King James Version"
  sizeBytes: number;   // from ModelAsset.size_bytes / translation manifest
  whyCopy: string;     // one line: why this is needed
  successCopy: string; // one line: what's now possible
};
```
- Title = `Downloading {name}`. Subtitle = the asset descriptor (`Whisper · English · on-device` / `Bible · offline text (KJV)`).
- The same seven states below serve both asset kinds (state 7 is the Bible proof).

## States (each is a Figma card in the frame)

| # | State | Figma node | Key content | Buttons |
|---|-------|-----------|-------------|---------|
| 1 | **Downloading** | `398:124` | determinate bar; `{done} MB of {total} · {pct}%`; `~{eta} left`; "runs once" note | `Hide` (ghost) · `Cancel` (bordered) |
| 2 | **Verifying** | `400:124` | title "Verifying {name}", "Checking integrity…"; full bar; explains the checksum guard | `Cancel` (bordered) |
| 3 | **Ready** | `400:146` | green ✓; "Installed · {size} · verified"; successCopy | `Start listening` (primary) |
| 4 | **Couldn't connect** (network) | `400:168` | gold `!`; "Download interrupted / Paused at {pct}%"; progress kept | `Cancel` (ghost) · `Retry` (primary) |
| 5 | **Couldn't verify** (integrity) | `400:190` | red `!`; "Discarded for your safety"; checksum mismatch → deleted, nothing installed | `Cancel` (ghost) · `Retry` (primary) |
| 6 | **Offline** | `400:212` | grey ⚠; "Connection needed one time"; works offline afterward | `Not now` (ghost) · `Try again` (primary) |
| 7 | **Reuse — Bible** | `400:234` | same layout, `Downloading King James Version`, `42 MB of 118 MB · 36%` | `Hide` · `Cancel` |

Map states to the backend as: *resolving* → **1** (each `progress(done,total)` tick), *sha256 check* → **2**, *load ok* → **3**, transport error → **4**, integrity error (`fetch_model` verify fails / discards) → **5**, no network before start → **6**.

## Placement & scrim

- Centered dialog, **max-width 360**. Scrim = base `#0b0d12` at **72%** over the whole console.
- Scrim blocks console interaction while open, **except** the emergency footer (BLACKOUT / Clear) which stays **above** the scrim and reachable — a dialog must never trap live output (existing console rule).
- Narrow width → 92vw; the card body scrolls, buttons stay pinned.

## Flow & behaviour

- Resolving → Downloading → Verifying → Ready, and **Ready auto-continues** into the triggering action (auto-dismiss ~1.5 s or on the primary button). *(Product to confirm — see Assumptions.)*
- **Hide** = keep downloading in the background; a small pill re-opens the modal. **Cancel** aborts and deletes the partial file.
- **Retry** resumes from kept progress (state 4); an **integrity** failure (state 5) restarts clean.

## Accessibility

- `role="dialog"` `aria-modal="true"`; `aria-labelledby`=title, `aria-describedby`=note.
- Focus trap; initial focus on the primary button (or Cancel when there's no primary). `Esc` = Cancel **when cancelable** — disabled during **Verifying**.
- Progress: `role="progressbar"` with `aria-valuemin/max/now`; an `aria-live="polite"` region announces the percentage in ~10% steps (not every tick).
- `prefers-reduced-motion`: no shimmer / indeterminate animation — show a static "Working…".
- All text ≥ AA on surface; hit targets ≥ 40 px.

## Design 2.0 tokens

| Role | Value | CSS var |
|------|-------|---------|
| Surface (card) | `#14161d` | `--sc-surface` |
| Base (scrim, bar track) | `#0b0d12` | `--sc-base` |
| Border | `#262a34` | `--sc-border` |
| Primary (bar fill, primary btn) | `#6e5cf0` | `--sc-primary` |
| OK (Ready) | `#35c08a` | `--sc-preview` |
| Warn (network error) | `#f2b84b` | `--sc-gold` |
| Integrity error | `#ff4d4d` | `--sc-live` |
| Text / muted | `#f4f6fb` / `#6b7383` | `--sc-text` / `--sc-text-muted` |

Type: Inter — title 15/Semi Bold, body 12–13/Regular–Medium. Card radius 16, buttons radius 10, bar height 8 / radius 999.

## Copy (final)

- Downloading note: *"Runs once. SelahCue works fully offline after it finishes."*
- Verifying: *"This guards against a corrupted or tampered model. Takes a few seconds."*
- Ready: *"On-device transcription is ready. Listening will start now."*
- Network error: *"Couldn't reach the download server. Check your connection — nothing was lost, it resumes where it stopped."*
- Integrity error: *"The file didn't match its security checksum, so SelahCue deleted it and installed nothing. This is usually a bad connection — try again."*
- Offline: *"Connect to the internet once to download the speech model (~1.6 GB). After that, transcription runs fully offline."*

## Assumptions flagged for product

1. **Hide / continue-in-background** is offered for large downloads. If downloads must be modal-blocking, drop the Hide button.
2. **Ready auto-continues** into listening / opening the Bible. If an explicit confirm is required, keep the primary button and remove auto-dismiss.
