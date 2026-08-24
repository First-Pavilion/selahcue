#!/usr/bin/env python3
"""Shared core for the SelahCue **visual-parity** harness (`vp_*` scripts).

The harness answers one question with an image, not an assertion: *how far is a
rendered surface from its Figma "Design 2.0" frame, and is the difference
intentional?* It has four parts, each its own script:

  vp_reference.py      ingest/verify the committed Figma reference PNGs
  vp_capture_web.py    screenshot the real operator `dist/` under headless Chrome
  vp_capture_native.py render the Rust stage/audience output to PNG
  vp_compare.py        block-SSIM + diff image + deviation gate + HTML/MD report
  vp_selftest.py       the "does the harness actually bite" gate
  visual_parity.py     orchestrator that runs the above in order

This module holds what all of them share: the two BOUNDED stores, the similarity
metric, the diff renderer, and the WCAG contrast maths.

WHY NOT `selahcue_engine::analysis::ssim` — that function is a GLOBAL SSIM (one
window over the whole image; see `analysis.rs:151`). It is the right oracle for
its job (CPU-vs-GPU parity, where the scene is identical and only rounding
differs) and the wrong one here: a global mean/variance/covariance barely moves
when an element is displaced 30 px, which is exactly the design defect this
harness exists to find. We therefore use LOCAL (blockwise) SSIM — the same
formula and the same C1/C2 constants, evaluated per 8x8 block — which is
displacement-sensitive and gives a per-block map we can localise and aggregate
over regions. Documented in docs/delivery/VISUAL-PARITY-HARNESS.md.

Dependencies: Pillow only (no numpy on this box — verified 2026-08-23). All
pixel maths runs through Pillow's C paths (`Image.resize(BOX)` on "F" images and
`ImageMath.unsafe_eval`), never a Python per-pixel loop.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time

try:
    from PIL import Image, ImageChops, ImageMath
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        "visual-parity harness needs Pillow: python3 -m pip install --user Pillow (%s)" % exc
    )

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN_DIR = os.path.join(REPO, "docs", "design", "visual-parity")
REFERENCE_DIR = os.path.join(DESIGN_DIR, "reference")
SURFACES_PATH = os.path.join(DESIGN_DIR, "surfaces.json")
DEVIATIONS_PATH = os.path.join(DESIGN_DIR, "deviations.json")
ARTIFACT_ROOT = os.environ.get("SELAHCUE_VISUAL_ARTIFACTS") or os.path.join(
    REPO, ".visual-parity"
)

FIGMA_FILE_KEY = "SYQn5hFY8YVQKm3c6rw0eJ"

# ---------------------------------------------------------------------------
# Bounds. Both stores are hard-capped; neither may grow without limit.
# ---------------------------------------------------------------------------

# The reference store is COMMITTED, so its bound is a REFUSAL, not an eviction:
# silently dropping a committed reference would be a worse failure than refusing
# to add one. Sized for the 13 comparable Design 2.0 frames plus headroom.
MAX_REFERENCE_ENTRIES = 32
MAX_REFERENCE_BYTES = 24 * 1024 * 1024
# Compile-time-ish premise pin: the caps must leave headroom over the frames the
# harness actually declares, or the store is full before it is useful and every
# ingest test becomes a test of the refusal path only.
REFERENCE_ENTRY_HEADROOM = 8

# Run artifacts are DISPOSABLE and regenerated every run, so their bound is an
# eviction: keep the newest N runs and delete the rest. Without this, one run per
# CI invocation at ~15 PNGs x ~1 MB grows the working tree without limit.
MAX_RUNS_KEPT = 5
# A second, independent bound: eviction caps how MANY runs survive, not how large
# one run may get. Without this a per-state loop that writes N images per surface
# would grow a single run without limit and never trip the run-count cap.
# Sized well above the current catalogue (10 web surfaces x 2 engines x up to 2
# scales + 8 native + diffs + reports ~= 70) so it flags a structural change, not
# routine growth. Enforced in vp_compare.py; controlled in vp_selftest.py.
MAX_FILES_PER_RUN = 200

assert MAX_REFERENCE_ENTRIES > REFERENCE_ENTRY_HEADROOM
assert MAX_RUNS_KEPT >= 1


class StoreFull(Exception):
    """Raised when an ingest would push a bounded store past its cap."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path, default=None):
    if not os.path.exists(path):
        if default is None:
            raise SystemExit("missing required file: " + path)
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def slug_ok(slug):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug or ""))


# ---------------------------------------------------------------------------
# Bounded reference store (committed Figma exports)
# ---------------------------------------------------------------------------


class ReferenceStore:
    """The committed Figma reference PNGs + their manifest.

    Bounded by BOTH an entry count and a byte budget. A byte budget alone admits
    unboundedly many tiny entries; an entry count alone admits one enormous one.
    An ingest that would breach either cap raises `StoreFull` — it never evicts,
    because every entry here is a checked-in artefact somebody chose to keep.
    """

    def __init__(self, root=REFERENCE_DIR):
        self.root = root
        self.manifest_path = os.path.join(root, "manifest.json")

    def manifest(self):
        return load_json(self.manifest_path, default={"entries": {}})

    def entries(self):
        return self.manifest().get("entries", {})

    def path_for(self, slug):
        return os.path.join(self.root, slug + ".png")

    def total_bytes(self, entries=None):
        entries = self.entries() if entries is None else entries
        return sum(int(e.get("bytes", 0)) for e in entries.values())

    def ingest(self, slug, src_path, node_id, note=""):
        """Copy `src_path` in as `slug`.png and record it. Bounded; may raise StoreFull."""
        if not slug_ok(slug):
            raise ValueError("bad reference slug: %r" % (slug,))
        with Image.open(src_path) as im:
            width, height = im.size
            fmt = im.format
        if fmt != "PNG":
            raise ValueError("reference must be a PNG, got %s" % fmt)
        size = os.path.getsize(src_path)
        entries = dict(self.entries())
        replacing = slug in entries
        projected_count = len(entries) + (0 if replacing else 1)
        projected_bytes = self.total_bytes(entries) - (
            int(entries[slug].get("bytes", 0)) if replacing else 0
        ) + size
        if projected_count > MAX_REFERENCE_ENTRIES:
            raise StoreFull(
                "reference store full: %d entries would exceed MAX_REFERENCE_ENTRIES=%d"
                % (projected_count, MAX_REFERENCE_ENTRIES)
            )
        if projected_bytes > MAX_REFERENCE_BYTES:
            raise StoreFull(
                "reference store full: %d bytes would exceed MAX_REFERENCE_BYTES=%d"
                % (projected_bytes, MAX_REFERENCE_BYTES)
            )
        os.makedirs(self.root, exist_ok=True)
        dst = self.path_for(slug)
        shutil.copyfile(src_path, dst)
        entries[slug] = {
            "node_id": node_id,
            "file_key": FIGMA_FILE_KEY,
            "width": width,
            "height": height,
            "bytes": size,
            "sha256": sha256_file(dst),
            "exported_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": note,
        }
        dump_json(
            self.manifest_path,
            {
                "_comment": (
                    "Figma reference exports for the visual-parity harness. Regenerate with "
                    "scripts/vp_reference.py (see docs/delivery/VISUAL-PARITY-HARNESS.md). "
                    "Figma asset URLs expire in ~7 days, which is why the BYTES are committed."
                ),
                "file_key": FIGMA_FILE_KEY,
                "entries": entries,
            },
        )
        return entries[slug]

    def verify(self):
        """Return (ok, problems). Checks presence, checksum, dimensions and the caps."""
        problems = []
        entries = self.entries()
        for slug, meta in sorted(entries.items()):
            path = self.path_for(slug)
            if not os.path.exists(path):
                problems.append("%s: file missing (%s)" % (slug, path))
                continue
            actual = sha256_file(path)
            if actual != meta.get("sha256"):
                problems.append(
                    "%s: sha256 mismatch (manifest %s, file %s)"
                    % (slug, str(meta.get("sha256"))[:12], actual[:12])
                )
            with Image.open(path) as im:
                if (im.width, im.height) != (meta.get("width"), meta.get("height")):
                    problems.append(
                        "%s: dimensions %dx%d != manifest %sx%s"
                        % (slug, im.width, im.height, meta.get("width"), meta.get("height"))
                    )
        if len(entries) > MAX_REFERENCE_ENTRIES:
            problems.append(
                "store over cap: %d entries > MAX_REFERENCE_ENTRIES=%d"
                % (len(entries), MAX_REFERENCE_ENTRIES)
            )
        if self.total_bytes(entries) > MAX_REFERENCE_BYTES:
            problems.append(
                "store over cap: %d bytes > MAX_REFERENCE_BYTES=%d"
                % (self.total_bytes(entries), MAX_REFERENCE_BYTES)
            )
        # Orphans: PNGs on disk with no manifest entry are unbounded growth by
        # another name — they are never verified and never evicted.
        if os.path.isdir(self.root):
            for name in sorted(os.listdir(self.root)):
                if name.endswith(".png") and name[:-4] not in entries:
                    problems.append("%s: orphan PNG with no manifest entry" % name)
        return (not problems), problems


# ---------------------------------------------------------------------------
# Bounded run-artifact store (screenshots, diffs, reports)
# ---------------------------------------------------------------------------


def run_dir(name=None, root=ARTIFACT_ROOT):
    """Create (and return) a run directory, pruning old runs to MAX_RUNS_KEPT."""
    os.makedirs(root, exist_ok=True)
    name = name or time.strftime("run-%Y%m%d-%H%M%S", time.gmtime())
    path = os.path.join(root, name)
    os.makedirs(path, exist_ok=True)
    prune_runs(root)
    return path


def prune_runs(root=ARTIFACT_ROOT, keep=MAX_RUNS_KEPT):
    """Delete all but the newest `keep` run directories. Returns the names removed.

    This is the harness's no-unbounded-growth guard: every invocation writes a
    fresh run directory of ~15 PNGs, so without eviction the artefact root grows
    linearly and forever. `vp_selftest.py` mutation-verifies it.
    """
    if not os.path.isdir(root):
        return []
    runs = sorted(
        d for d in os.listdir(root) if d.startswith("run-") and os.path.isdir(os.path.join(root, d))
    )
    removed = []
    while len(runs) > keep:
        victim = runs.pop(0)
        shutil.rmtree(os.path.join(root, victim), ignore_errors=True)
        removed.append(victim)
    return removed


def count_run_files(path):
    total = 0
    for _root, _dirs, files in os.walk(path):
        total += len(files)
    return total


# ---------------------------------------------------------------------------
# Similarity: local (blockwise) SSIM, Pillow-only
# ---------------------------------------------------------------------------

SSIM_BLOCK = 8
# Wang et al. stabilisation constants on an 0..255 scale. Identical semantics to
# `selahcue_engine::analysis::channel_ssim`, which uses (0.01)^2 / (0.03)^2 on an
# 0..1 scale — the same numbers, scaled by L^2.
_C1 = (0.01 * 255.0) ** 2
_C2 = (0.03 * 255.0) ** 2


def _mean_of(img_f):
    """Exact mean of an "F" image via a C-path 1x1 BOX resize (no Python loop)."""
    return float(img_f.resize((1, 1), Image.BOX).getpixel((0, 0)))


def _block_means(img_f, bw, bh, block):
    return img_f.resize((bw, bh), Image.BOX)


def _channel_block_ssim(a_f, b_f, bw, bh, block):
    mu_a = _block_means(a_f, bw, bh, block)
    mu_b = _block_means(b_f, bw, bh, block)
    aa = _block_means(ImageMath.unsafe_eval("a*a", a=a_f), bw, bh, block)
    bb = _block_means(ImageMath.unsafe_eval("b*b", b=b_f), bw, bh, block)
    ab = _block_means(ImageMath.unsafe_eval("a*b", a=a_f, b=b_f), bw, bh, block)
    return ImageMath.unsafe_eval(
        "((2*ma*mb + c1) * (2*(mab - ma*mb) + c2)) / "
        "(((ma*ma) + (mb*mb) + c1) * ((maa - ma*ma) + (mbb - mb*mb) + c2))",
        ma=mu_a,
        mb=mu_b,
        maa=aa,
        mbb=bb,
        mab=ab,
        c1=_C1,
        c2=_C2,
    )


def block_ssim(img_a, img_b, block=SSIM_BLOCK):
    """Local SSIM of two same-size RGB images.

    Returns (mean_ssim, block_map, (bw, bh)) where `block_map` is a flat list of
    per-block SSIM values in row-major order, each the MINIMUM across R/G/B — the
    same channel-reduction `analysis::ssim` uses, so a chroma-only divergence
    (right luminance, wrong hue) cannot pass.
    """
    if img_a.size != img_b.size:
        raise ValueError("block_ssim needs equal sizes, got %r vs %r" % (img_a.size, img_b.size))
    w, h = img_a.size
    bw, bh = max(1, w // block), max(1, h // block)
    cw, ch = bw * block, bh * block
    a = img_a.convert("RGB").crop((0, 0, cw, ch))
    b = img_b.convert("RGB").crop((0, 0, cw, ch))
    per_channel = []
    for ch_idx in range(3):
        a_f = a.getchannel(ch_idx).convert("F")
        b_f = b.getchannel(ch_idx).convert("F")
        per_channel.append(_channel_block_ssim(a_f, b_f, bw, bh, block))
    combined = per_channel[0]
    for other in per_channel[1:]:
        # ImageChops rejects "F" images, so reduce with ImageMath's min() instead.
        combined = ImageMath.unsafe_eval("min(a, b)", a=combined, b=other)
    values = list(combined.getdata())
    mean = _mean_of(combined)
    return mean, values, (bw, bh)


def pixel_delta_stats(img_a, img_b, threshold=12):
    """Per-pixel max-channel delta: (mean_delta, fraction_over_threshold)."""
    a = img_a.convert("RGB")
    b = img_b.convert("RGB")
    d = ImageChops.difference(a, b)
    r, g, bl = d.split()
    m = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    hist = m.histogram()
    total = sum(hist) or 1
    mean = sum(i * n for i, n in enumerate(hist)) / total
    over = sum(n for i, n in enumerate(hist) if i > threshold)
    return mean, over / total


def is_uniform(img, tolerance=2):
    """True if the image is (near-)single-colour — the blank-capture signature.

    A capture step that silently failed usually yields a solid white or solid
    black frame, which scores well against nothing and badly against everything.
    Callers assert on this BEFORE similarity so a dead capture cannot be read as
    a diff result.
    """
    ext = img.convert("RGB").getextrema()
    return all((hi - lo) <= tolerance for lo, hi in ext)


def ink_coverage(img, background=None, tolerance=24):
    """Fraction of pixels that differ from the modal (background) colour."""
    rgb = img.convert("RGB")
    if background is None:
        colors = rgb.getcolors(maxcolors=1 << 20)
        if not colors:
            small = rgb.resize((min(rgb.width, 256), min(rgb.height, 256)), Image.BOX)
            colors = small.getcolors(maxcolors=1 << 20) or [(1, (0, 0, 0))]
        background = max(colors)[1]
    flat = Image.new("RGB", rgb.size, tuple(background))
    d = ImageChops.difference(rgb, flat)
    r, g, b = d.split()
    m = ImageChops.lighter(ImageChops.lighter(r, g), b)
    hist = m.histogram()
    total = sum(hist) or 1
    return sum(n for i, n in enumerate(hist) if i > tolerance) / total, background


def diff_image(img_ref, img_actual, block_values=None, grid=None, block=SSIM_BLOCK):
    """A red-over-grey diff: the actual frame desaturated, differences in red.

    Where a block map is supplied, blocks with low SSIM are outlined so a
    structural (displacement) difference is visible even when the per-pixel delta
    is small — the case a raw pixel diff misses.
    """
    ref = img_ref.convert("RGB")
    act = img_actual.convert("RGB")
    if ref.size != act.size:
        ref = ref.resize(act.size, Image.LANCZOS)
    grey = act.convert("L").point(lambda v: 40 + v // 4).convert("RGB")
    d = ImageChops.difference(ref, act)
    r, g, b = d.split()
    mag = ImageChops.lighter(ImageChops.lighter(r, g), b)
    boosted = mag.point(lambda v: min(255, v * 3))
    red = Image.merge("RGB", (boosted, Image.new("L", act.size, 0), Image.new("L", act.size, 0)))
    out = ImageChops.add(grey, red)
    if block_values and grid:
        bw, bh = grid
        marks = Image.new("L", (bw, bh), 0)
        marks.putdata([255 if v < 0.90 else 0 for v in block_values])
        marks = marks.resize(act.size, Image.NEAREST)
        blue = Image.merge(
            "RGB", (Image.new("L", act.size, 0), Image.new("L", act.size, 0), marks.point(lambda v: v // 3))
        )
        out = ImageChops.add(out, blue)
    return out


# ---------------------------------------------------------------------------
# WCAG contrast — mirrors selahcue_present::tokens::contrast_ratio exactly
# ---------------------------------------------------------------------------

AA_TEXT = 4.5  # normal text (PRD NFR-020)
AA_LARGE = 3.0  # large text AND non-text UI components (PRD NFR-020)
# WCAG 2.x "large text": >= 18.66px bold, or >= 24px regular.
LARGE_PX_REGULAR = 24.0
LARGE_PX_BOLD = 18.66
BOLD_WEIGHT = 700


def relative_luminance(rgb):
    def channel(v):
        s = v / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb[0], rgb[1], rgb[2]
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg, bg):
    la, lb = relative_luminance(fg), relative_luminance(bg)
    hi, lo = (la, lb) if la >= lb else (lb, la)
    return (hi + 0.05) / (lo + 0.05)


def is_large_text(font_px, font_weight):
    try:
        px = float(font_px)
        weight = int(float(font_weight))
    except (TypeError, ValueError):
        return False
    return px >= LARGE_PX_REGULAR or (weight >= BOLD_WEIGHT and px >= LARGE_PX_BOLD)


def required_ratio(kind, font_px=None, font_weight=None):
    """The AA threshold that applies. `kind` is "text" or "ui".

    Applying 4.5:1 to everything is wrong and noisy: PRD NFR-020 sets 4.5:1 for
    normal text and 3:1 for large text AND non-text UI. The useful finding is not
    "this pairing is under 4.5:1" but "this pairing carries text too small for
    the ratio it has".
    """
    if kind == "ui":
        return AA_LARGE, "AA-large (non-text UI)"
    if is_large_text(font_px, font_weight):
        return AA_LARGE, "AA-large (>=24px, or >=18.66px bold)"
    return AA_TEXT, "AA-normal"


def blend_over(fg_rgba, bg_rgb, opacity=1.0):
    """Composite an RGBA foreground over an opaque backdrop at `opacity`.

    Alpha and inherited opacity BOTH reduce the effective ink. Comparing raw
    token pairs (ignoring both) is how a card-level `opacity: .5` stayed
    invisible to a checker that read `getComputedStyle(el).opacity` on the
    control itself and saw "1".
    """
    a = float(fg_rgba[3]) / 255.0 if len(fg_rgba) > 3 else 1.0
    a = max(0.0, min(1.0, a * float(opacity)))
    return tuple(round(fg_rgba[i] * a + bg_rgb[i] * (1.0 - a)) for i in range(3))


def parse_css_color(value):
    """Parse `rgb(...)`/`rgba(...)`/`#rrggbb` into an (r, g, b, a) tuple, or None."""
    if not value:
        return None
    value = value.strip()
    m = re.match(r"rgba?\(([^)]+)\)", value)
    if m:
        parts = [p.strip() for p in re.split(r"[,\s/]+", m.group(1)) if p.strip()]
        if len(parts) < 3:
            return None
        try:
            r, g, b = (int(round(float(p))) for p in parts[:3])
        except ValueError:
            return None
        a = 255
        if len(parts) > 3:
            try:
                alpha = float(parts[3].rstrip("%"))
                if parts[3].endswith("%"):
                    alpha /= 100.0
                a = int(round(max(0.0, min(1.0, alpha)) * 255))
            except ValueError:
                a = 255
        return (r, g, b, a)
    m = re.fullmatch(r"#([0-9a-fA-F]{3,8})", value)
    if m:
        hx = m.group(1)
        if len(hx) == 3:
            hx = "".join(c * 2 for c in hx)
        if len(hx) == 6:
            hx += "ff"
        if len(hx) != 8:
            return None
        return tuple(int(hx[i : i + 2], 16) for i in (0, 2, 4, 6))
    return None


def sampled_contrast(img, rect, min_population=0.004):
    """Estimate the RENDERED contrast of a text region straight from the pixels.

    Immune, by construction, to every compositing mistake a DOM-side calculation
    can make (inherited opacity, alpha over the wrong backdrop, a rule that only
    applies in one engine): whatever the screenshot shows is what a human sees.

    Background = the most populous colour in the crop. Foreground = the colour
    with the largest luminance distance from it that still holds `min_population`
    of the crop, which skips antialiasing fringes (each individual fringe colour
    is rare) while keeping the solid glyph core. Returns
    (ratio, fg, bg, fg_population) or None when the crop has no second colour
    with enough population to measure.
    """
    x, y, w, h = (int(round(v)) for v in rect)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(img.width, x + max(1, w)), min(img.height, y + max(1, h))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = img.convert("RGB").crop((x0, y0, x1, y1))
    total = crop.width * crop.height
    colors = crop.getcolors(maxcolors=1 << 22)
    if not colors:
        return None
    colors.sort(reverse=True)
    bg = colors[0][1]
    bg_lum = relative_luminance(bg)
    best = None
    for count, color in colors[1:]:
        if count / total < min_population:
            continue
        dist = abs(relative_luminance(color) - bg_lum)
        if best is None or dist > best[0]:
            best = (dist, color, count)
    if best is None:
        return None
    _dist, fg, count = best
    return contrast_ratio(fg, bg), fg, bg, count / total


def contrast_from_luminance(l1, l2):
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


def gradient_stops(css_background_image):
    """Every colour stop in a `linear-gradient(...)`/`radial-gradient(...)` string.

    A gradient has to be checked at EVERY stop. Sampling one background colour is
    exactly how a button whose light end fails AA passes a checker: white on
    `#3ed39a` is 1.91:1 while white on `#28a579` is 3.11:1 — same button.
    """
    if not css_background_image:
        return []
    stops = []
    for token in re.findall(r"rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}", css_background_image):
        parsed = parse_css_color(token)
        if parsed:
            stops.append(parsed)
    return stops


def resolve_backdrops(chain):
    """Every opaque backdrop actually behind an element, nearest painted layer first.

    `chain` is the element-to-root list the capture driver records, each entry
    carrying its own `opacity`, `background` and `backgroundImage`.

    Three composition traps this has to survive, all of them shipped in this
    codebase and all invisible to a checker that compares a foreground token
    against a background token:

    1. A TRANSLUCENT fill over non-flat ground. `button.golive .key` is
       `rgba(255,255,255,.18)` sitting on the GO LIVE gradient; the ink is white
       on the COMPOSITE, not on either endpoint. So a translucent layer is
       blended over everything still behind it rather than terminating the walk.
    2. A GRADIENT needs every stop. Collapsing to one stop passes a button whose
       light end fails — so the candidate set is carried forward as a LIST, and a
       translucent layer above a gradient produces one composite per stop.
    3. Opacity composes down the ancestor chain — handled by `effective_opacity`.

    Returns a list of opaque RGB tuples: every distinct backdrop the ink can sit
    on. Callers must evaluate ALL of them and report the worst.
    """
    layers = []
    for node in chain:
        stops = gradient_stops(node.get("backgroundImage"))
        if stops:
            layers.append(stops)
            break
        color = parse_css_color(node.get("background"))
        if color and color[3] > 0:
            layers.append([color])
            if color[3] == 255:
                break
    if not layers:
        return [(0, 0, 0)]
    candidates = [(0, 0, 0)]
    for colors in reversed(layers):
        candidates = [blend_over(c, base) for base in candidates for c in colors]
    # De-duplicate while preserving order; a 4-stop chain can repeat composites.
    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out or [(0, 0, 0)]


def effective_opacity(chain):
    """Product of every ancestor's own opacity, element included.

    The value that matters is the PRODUCT: the defect this guards against put
    `opacity: .5` on the card, so the control's own computed opacity read "1"
    both before and after the fix.
    """
    v = 1.0
    for node in chain:
        try:
            v *= float(node.get("opacity", 1))
        except (TypeError, ValueError):
            pass
    return v


def dom_region_contrast(region):
    """Worst-case contrast for a captured region, computed from the DOM record.

    Composites the ink over EVERY candidate backdrop (all gradient stops) at the
    composited opacity, and returns the worst pairing — plus the AA threshold that
    actually applies to this region's rendered text size/weight.
    """
    fg = parse_css_color(region.get("color"))
    if not fg:
        return None
    chain = region.get("chain") or []
    opacity = effective_opacity(chain)
    # The element's OWN background is behind its own text, so the walk starts at
    # the element, not at its parent — and a translucent own-background is
    # composited over whatever is behind it rather than checked as an endpoint.
    backdrops = resolve_backdrops(chain)
    candidates = []
    for bg in backdrops:
        ink = blend_over(fg, bg, opacity)
        candidates.append((contrast_ratio(ink, bg), bg, ink))
    if not candidates:
        return None
    ratio, bg, ink = min(candidates, key=lambda t: t[0])
    need, name = required_ratio(
        region.get("kind", "text"), region.get("fontSize", "").replace("px", ""), region.get("fontWeight")
    )
    return {
        "ratio": ratio,
        "fg": list(fg[:3]),
        "ink_composited": list(ink),
        "bg": list(bg),
        "opacity": opacity,
        "required": need,
        "threshold": name,
        "font_px": region.get("fontSize"),
        "font_weight": region.get("fontWeight"),
        "candidates": len(candidates),
    }


def region_pixel_contrast(img, rect, scale=1, min_population=0.005, family_ratio=0.45,
                          min_span_ratio=1.5):
    """Measure a region's rendered contrast from the PIXELS.

    Independent of every compositing assumption a DOM calculation makes
    (inherited opacity, alpha over the wrong backdrop, an engine-specific rule),
    and it handles gradients without being told they exist.

    Colours are first grouped into 5-bit-per-channel BUCKETS. That step is
    load-bearing: in a 300px-wide gradient every individual RGB value occupies one
    thin column and holds well under 1% of the crop, so a population filter over
    exact colours discards the entire background and leaves only the text — which
    is how a naive sampler reports 19:1 for a button that measures 7.19:1. Each
    surviving bucket is represented by its most populous EXACT colour, so the
    precision of the final ratio is not reduced by the bucketing.

    The most populous bucket is the backdrop; the ink is the populous bucket
    furthest from it in luminance; the backdrop FAMILY is every populous bucket
    within `family_ratio` of that distance (this is what collects the stops of a
    gradient fill), and the reported ratio is the WORST pairing in that family.

    Returns None — not a number — when the crop has no ink population large enough
    (`min_population`) or far enough (`min_span_ratio`) to measure honestly. A
    refusal is the correct answer for a small label whose glyph core never covers
    half a percent of its box; inventing a ratio there would be worse than silence.
    """
    x, y, w, h = (float(v) * scale for v in rect)
    x0, y0 = max(0, int(round(x))), max(0, int(round(y)))
    x1, y1 = min(img.width, int(round(x + w))), min(img.height, int(round(y + h)))
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    crop = img.convert("RGB").crop((x0, y0, x1, y1))
    total = crop.width * crop.height
    colors = crop.getcolors(maxcolors=1 << 22)
    if not colors:
        colors = crop.quantize(colors=256).convert("RGB").getcolors(maxcolors=1 << 22) or []
    buckets = {}
    for n, c in colors:
        key = (c[0] >> 3, c[1] >> 3, c[2] >> 3)
        entry = buckets.get(key)
        if entry is None:
            buckets[key] = [n, n, c]
        else:
            entry[0] += n
            if n > entry[1]:
                entry[1], entry[2] = n, c
    populous = [
        (relative_luminance(rep), tot, rep)
        for tot, _best, rep in buckets.values()
        if tot / total >= min_population
    ]
    if len(populous) < 2:
        return None
    bg0 = max(populous, key=lambda t: t[1])
    ink = max(populous, key=lambda t: abs(t[0] - bg0[0]))
    if contrast_from_luminance(ink[0], bg0[0]) < min_span_ratio:
        return None
    span = abs(ink[0] - bg0[0])
    family = [t for t in populous if abs(t[0] - bg0[0]) <= family_ratio * span]
    worst = min(family, key=lambda t: contrast_from_luminance(ink[0], t[0]))
    best = max(family, key=lambda t: contrast_from_luminance(ink[0], t[0]))
    return {
        "ratio": contrast_from_luminance(ink[0], worst[0]),
        "ratio_best": contrast_from_luminance(ink[0], best[0]),
        "ink": list(ink[2]),
        "ink_population": ink[1] / total,
        "bg_worst": list(worst[2]),
        "bg_population": worst[1] / total,
        "bg_family": len(family),
        "crop": [x0, y0, x1 - x0, y1 - y0],
    }
