# Bundled output font (ADR-0014, ADR-0012)

- **NotoSans-Latin.ttf** — Noto Sans, Regular instance, subset to Latin +
  Latin-1/Extended-A/B/Additional + combining diacritical marks + the
  punctuation/symbols the output uses (FR-017: Yoruba/Hausa/Igbo/French/Spanish
  diacritics). Derived from Google Fonts `ofl/notosans/NotoSans[wdth,wght].ttf`
  (pinned to wght=400,wdth=100, then `fontTools.subset`). ~127 KB.
- **License:** SIL Open Font License 1.1 — see `OFL.txt` (Copyright The Noto
  Project Authors). OFL permits bundling + subsetting; the derived subset keeps
  the OFL. This is the single deterministic shaper/rasterizer font for the
  AUDIENCE output (`font: None`) on all three OSes (no system-font divergence →
  NFR-014 parity).

## Stage / confidence-monitor typeface (Inter)

- **Inter-Latin.ttf** — Inter **Regular (400)**, Latin subset (basic Latin +
  Latin-1 + `·`/curly quotes/dashes). ~89 KB.
- **Inter-Bold-Latin.ttf** — Inter **Bold (700)**, same Latin subset. ~89 KB.
- Both are *static* instances (`wght` pinned, `opsz=14`, then `fontTools.subset`)
  of Google Fonts `ofl/inter/Inter[opsz,wght].ttf`. **Both weights are bundled on
  purpose:** with only a single Regular face loaded, cosmic-text resolves
  `(Inter, 700)` to a *system monospace* once system fonts are in the DB — so the
  stage's bold text needs a real 700 face. They are loaded ONLY into the
  named-font shaper (never the default), so `Family::Name("Inter")` — used by the
  confidence monitor (Figma 373-375) — resolves to these bundled faces, while the
  audience output stays byte-identical on Noto Sans.
- **License:** SIL Open Font License 1.1 — see `Inter-OFL.txt` (Copyright The
  Inter Project Authors). OFL permits bundling + subsetting; the subsets keep the
  OFL.
