# Bundled output font (ADR-0014, ADR-0012)

- **NotoSans-Latin.ttf** — Noto Sans, Regular instance, subset to Latin +
  Latin-1/Extended-A/B/Additional + combining diacritical marks + the
  punctuation/symbols the output uses (FR-017: Yoruba/Hausa/Igbo/French/Spanish
  diacritics). Derived from Google Fonts `ofl/notosans/NotoSans[wdth,wght].ttf`
  (pinned to wght=400,wdth=100, then `fontTools.subset`). ~127 KB.
- **License:** SIL Open Font License 1.1 — see `OFL.txt` (Copyright The Noto
  Project Authors). OFL permits bundling + subsetting; the derived subset keeps
  the OFL. This is the single deterministic shaper/rasterizer font on all three
  OSes (no system-font divergence → NFR-014 parity).
