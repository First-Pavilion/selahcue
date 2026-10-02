# Presentation — Media library modal (spec)

Status: **proposed with the implementation** (no prior design exists for this surface; the Design 2.0 frame put the library in a permanent right-hand panel — `PRESENTATION-MEDIA-STATES-spec.md` §2/§5). Owner decision 2026-10-01: the library becomes a **modal picker in the style of Google's file "Open" dialog** — choose, then confirm.

Related: DEC-018 (images are copied into app storage), `PRESENTATION-MEDIA-STATES-spec.md` (tile states), `DESIGN-2.0-PARITY-AUDIT-presentation.md` (PME-038 empty-state call to action).

## 1. What changes

| Before | After |
|---|---|
| Right column has two tabs, **Media** and **Inspector**, auto-switching on selection | Right column is the **Inspector only** |
| Clicking a tile instantly adds the image | A tile is **selected**; **Insert** (or double-click) adds it |
| `🖼 Image` in the toolbar silently added the first library image, or did nothing | `🖼 Image` opens the library |
| Inspector → Replace… armed a hint inside the panel | Inspector → Replace… opens the library in **replace mode** |

## 2. Entry points

1. **Toolbar `🖼 Image`** → insert mode.
2. **Right-panel header `Media library…`** → insert mode (manage and browse; Insert stays disabled until something is selected).
3. **Inspector → `Replace…` / `Relink…`** on an image element → replace mode (images only, exactly one selection, button reads **Replace**).

The modal never opens by itself and never opens while another modal is open.

## 3. Layout

`role="dialog" aria-modal="true"`, labelled by its title ("Media library", or "Replace image" in replace mode). Width `min(760px, 100%)`, height up to `min(80vh, 100%)`; the grid scrolls, the header and footer do not.

1. **Header** — title, close `✕`.
2. **Toolbar** — search field; filter chips **All · Images · Video · Audio** (`aria-pressed`); **+ Import** (primary).
3. *(replace mode only)* a one-line hint: "Pick the image that replaces the selected element."
4. **Status line** — the outcome of an import or a removal (see §5). A `role="status"` live region that is always rendered and visually hidden while empty, never `display: none`, so filling it is a change a screen reader announces. The toast and the error banner sit behind the modal's scrim, so nothing about Import or Remove is reported anywhere else while the modal is open.
5. **Grid** — `repeat(auto-fill, minmax(140px, 1fr))` tiles, then the **Audio** list below the grid.
6. **Inline remove bar** (only while confirming a removal) — see §5.
7. **Footer** — total size and "N missing · M unused" (left); a live "N selected"; **Cancel** and the primary **Insert** / **Replace**.

Tokens are the existing `--sc-*` set. Secondary text uses `--sc-text-secondary`, never `--sc-text-muted` (contrast).

## 4. Tile

Thumbnail (the real picture — see DEC-018 thumbnails), file name, `KIND · size`. States, none colour-only:

- **Selected** — primary ring *and* a check mark; `aria-pressed="true"`.
- **In use** (the selected slide element uses it) — labelled "(in use)" in the accessible name.
- **Unused** — "(unused)" in the accessible name.
- **Missing** — ⚠ and "File moved"; disabled.
- **Can't preview** — "Can't preview" text; still selectable (the engine draws its own placeholder on the slide).
- **Video / audio** — listed, disabled: on-slide playback arrives later (ADR-0020). Importing them is not possible yet, so the Video and Audio filters show an honest "Video import arrives later." empty state.

A hover/focus-visible `✕` removes the asset (see §5). Names truncate with an ellipsis and carry the full name in the accessible name.

## 5. Interactions

- **Import** — opens the native picker (several files). The outcome is written to the modal's **status line**: a clean import says how many images landed; skipped files are named with the host's reason as a warning (the first three, then "+n more"); a batch the host rolled back because the library could not be saved reports each file and adds no "won't be kept" tail; and a refusal of the whole import (for example no media folder) shows the host's own reason there too, never only in the error banner behind the scrim. If the modal is closed while the import is still in flight and the host then refuses it, the reason falls back to the error banner, whose **Retry** re-runs the import (the command takes no paths: it opens the native picker itself, so a retry is a fresh pick, the same as **+ Import**) and never an earlier, unrelated deck action. New images appear selected-able immediately, with their pictures.
- **Select** — click or Space/Enter toggles. Insert mode allows multi-select, capped at **24** per insert (a 25th click shows "Up to 24 at a time"). Replace mode keeps exactly one.
- **Insert** — closes the modal and adds every selected image to the current slide in **one undo step**, cascaded so they do not stack exactly. **Replace** swaps the selected element's image.
- **Double-click** a tile — insert (or replace) just that image.
- **Remove** — `✕` shows the **inline bar** (a `role="alert"` strip above the footer). It reads "**Remove** *name*? " followed by a body, plus an optional warning; the words come from `pmRemoveMediaWords`, the one place that decides them, and the host decides what happens to the file at removal time (it never deletes a picture another saved deck still shows), so the bar says which:
  - **No other saved deck shows it** — body: "This removes the image from the media library and deletes SelahCue’s copy of it. This can’t be undone." When the open deck uses it, also the warning "Used on k slides — removing it leaves those slides with missing media." ("1 slide … that slide" in the singular).
  - **Other saved decks also show it** — body: "This removes the image from the media library. SelahCue keeps its copy of the file, because other presentations still show it." The warning is "Used on k slides here and in n other presentations — the picture file is kept so they keep showing it." when the open deck uses it too, and "Also used in n other presentations — the picture file is kept so they keep showing it." when it does not ("1 other presentation" in the singular).

  The outcome is reported in the status line — including "Removed from the library. The picture file is kept because n other presentations still use it." and a refused removal ("Couldn’t remove the image: the media library couldn’t be saved …": nothing was removed). If the modal is closed while a removal is still in flight and the host then refuses it, there is no status line, so the reason falls back to the error banner, whose **Retry** re-runs that removal. Buttons **Remove** (danger) and **Keep**; focus lands on **Keep** (the safe default) and the bar's text is its accessible description, and after **Remove** focus moves to the search field. The bar is inline rather than a second modal because the shared confirm dialog is single-instance and refuses to open over another modal.
- **Close** — `✕`, **Cancel**, **Esc** or a click on the scrim. Nothing changes. Focus returns to the control that opened it.

## 6. Keyboard and accessibility

- Focus moves into the dialog on open (the search field) and is **trapped**; Tab cycles header → toolbar → tiles → footer. Tiles are buttons in DOM order; there is no roving grid (kept simple on purpose).
- Esc closes the remove bar first, then the modal.
- Selection count is in a polite live region; the Insert button's label states the count. Import and Remove outcomes are in the status line (a `role="status"` region cleared and refilled across a short tick, so an identical message repeated is announced again).
- The empty library shows "No images yet — Import to get started." with the Import button (PME-038).
- All state is conveyed by text or shape as well as colour (WCAG 1.4.1).

## 7. Live-service safety (non-negotiable)

- The scrim stops **56px above the bottom** so the emergency footer (BLACKOUT, Clear) stays visible and clickable while the library is open — the same rule as the download modal.
- The modal carries the existing `.pm-confirm-back` sentinel class so every global shortcut guard (undo/redo, ⌘1–7 surface switching, plan shortcuts) ignores keystrokes while it is open. The emergency chords ⌘⇧B / ⌘⇧. are **not** intercepted (`selahcue-app/tests/test_keymap.rs`).
- Opening the library never changes what is on air. It only edits the open deck.

## 8. Out of scope

Arrow-key grid navigation, drag-and-drop import from Finder, folders/tags, video and audio import, de-duplication of identical files, and an image *background* picker (the data model has `Background::Image`; the toolbar `Background` button still adds a shape).
