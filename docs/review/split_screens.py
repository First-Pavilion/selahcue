#!/usr/bin/env python3
"""Extract each SelahCue Operator surface into a standalone, review-only HTML page.

The real dist/index.html stays the single runtime source. These are REVIEW COPIES:
markup is sliced VERBATIM from index.html (so they can't drift), wrapped in the shared
header/footer chrome, with the surface forced `active` so it renders when opened in a
browser. No app.js is included, so JS-populated regions render empty — that is expected.

Run:  python3 docs/review/split_screens.py   (from the repo root, or anywhere)
Output: docs/review/screens/*.html
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # docs/review/ -> repo root
SRC = ROOT / "implementation/desktop/crates/selahcue-operator/dist/index.html"
OUT = ROOT / "docs/review/screens"
OUT.mkdir(parents=True, exist_ok=True)

# stylesheet path relative to docs/review/screens/*.html back to the real app.css
CSS_HREF = "../../../implementation/desktop/crates/selahcue-operator/dist/app.css"

text = SRC.read_text()


def between(open_pat, close_pat, s=text):
    """Inclusive slice from the line matching open_pat through the first line
    matching close_pat at/after it."""
    lines = s.splitlines()
    start = next(i for i, ln in enumerate(lines) if re.search(open_pat, ln))
    end = next(i for i, ln in enumerate(lines) if i >= start and re.search(close_pat, ln))
    return "\n".join(lines[start:end + 1])


HEADER = between(r"^\s*<header>", r"^\s*</header>")
FOOTER = between(r'<footer id="emergency"', r"^\s*</footer>")

SURFACES = [
    # (out-file, nav data-surface, block open anchor, block close anchor)
    ("01-live-console.html",   "console",        r'<div id="surface-console"',           r"<!-- /surface-console -->"),
    ("02-theme-designer.html", "theme-designer", r'<section id="surface-theme-designer"', r"^\s*</section>"),
    ("03-screens.html",        "screens",        r'<section id="surface-screens"',        r"^\s*</section>"),
    ("04-plan-library.html",   "plan",           r'<section id="surface-plan"',           r"^\s*</section>"),
    ("05-settings.html",       "settings",       r'<section id="surface-settings"',       r"^\s*</section>"),
]

NAV_LABEL = {
    "console": "Live Console", "theme-designer": "Theme Designer",
    "screens": "Screens", "plan": "Plan / Library", "settings": "Settings",
}


def force_active(block):
    """Add `active` to the surface's own class list so it renders when opened."""
    if 'class="surface-page"' in block:  # surface-console
        return re.sub(r'(class="surface-page)(")', r"\1 active\2", block, count=1)
    return re.sub(r'(class="surface-page)( )', r"\1 active\2", block, count=1)


def set_current_nav(header, surface):
    """Mark this screen's nav item with aria-current on its own copy."""
    h = header.replace(' aria-current="page"', "")
    return re.sub(r'(data-surface="%s")' % re.escape(surface),
                  r'\1 aria-current="page"', h, count=1)


def page(title, header, block):
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SelahCue Operator — {title} (review copy)</title>
    <link rel="stylesheet" href="{CSS_HREF}" />
    <!--
      REVIEW COPY — NOT wired into the app. Markup is sliced verbatim from
      dist/index.html by docs/review/split_screens.py. Do not hand-edit; edit
      index.html and regenerate. No app.js: this is static markup for review,
      so JS-populated regions (plan list, transcript, canvases) render empty.
    -->
  </head>
  <body>
{header}
    <main>
{block}
    </main>
{FOOTER}
  </body>
</html>
"""


made = []
for fname, surface, op, cl in SURFACES:
    block = force_active(between(op, cl))
    header = set_current_nav(HEADER, surface)
    (OUT / fname).write_text(page(NAV_LABEL[surface], header, block))
    made.append(fname)

shell = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SelahCue Operator — Shared chrome (review copy)</title>
    <link rel="stylesheet" href="{CSS_HREF}" />
    <!-- REVIEW COPY — shared header nav + emergency footer that wrap every screen. -->
  </head>
  <body>
{HEADER}
    <main>
      <section class="surface-page active surface-pad">
        <h1>Shared chrome</h1>
        <p class="coming-soon">The header (app menu / route status / live chip / clock)
        and the always-reachable emergency footer wrap all five screens. Each screen's
        review copy includes this chrome for context.</p>
      </section>
    </main>
{FOOTER}
  </body>
</html>
"""
(OUT / "00-shell.html").write_text(shell)
made.insert(0, "00-shell.html")

print("Wrote to", OUT)
for f in made:
    print("  ", f, (OUT / f).stat().st_size, "bytes")
