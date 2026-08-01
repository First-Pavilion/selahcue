# SelahCue Operator — per-screen review copies

The operator UI is a single-page app: [`dist/index.html`](../../implementation/desktop/crates/selahcue-operator/dist/index.html)
holds all five "surfaces" in one document, toggled by a `.active` CSS class and driven by
one `app.js` that references every element ID. That single file is the **runtime source of
truth** and is unchanged by this folder.

To make review easier, `screens/` holds one **standalone, browser-openable copy per screen**.
Open any file directly — it links the real `app.css`, so each screen renders styled and in
isolation.

| File | Screen | Source in `index.html` |
|------|--------|------------------------|
| `screens/00-shell.html` | Shared header nav + emergency footer | `<header>` / `<footer id="emergency">` |
| `screens/01-live-console.html` | Live Console (3-zone operator view) | `#surface-console` |
| `screens/02-theme-designer.html` | Theme Designer | `#surface-theme-designer` |
| `screens/03-screens.html` | Screens (output manager) | `#surface-screens` |
| `screens/04-plan-library.html` | Plan / Library | `#surface-plan` |
| `screens/05-settings.html` | Settings | `#surface-settings` |

## Important

- **Review-only.** These files are **not** wired into the app and never load at runtime.
- **Markup is sliced verbatim** from `index.html`, so the copies can't drift in content.
- **No `app.js`.** JS-populated regions (the plan list, live transcript, canvases, scripture
  results, etc.) render empty — that is expected in a static review copy.
- **Do not hand-edit** the files in `screens/`. Edit `index.html`, then regenerate:

  ```sh
  python3 docs/review/split_screens.py
  ```
