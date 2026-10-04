#!/usr/bin/env python3
"""Cut a side-by-side slice of a Figma frame and the matching build capture, for a human to read.

    python3 scripts/vp_slice.py --slug home --run RUN_DIR --y 0 --h 900 --out /tmp/home-0.png
    python3 scripts/vp_slice.py --slug home --run RUN_DIR --y 900 --build-y 1010 --h 900 --scale 1 \
        --x 0 --w 720 --out /tmp/zoom.png

Figma on the left, the build on the right, same crop of each. A long page grows or shrinks as it
goes (the build carries real content where Figma drew a placeholder), so `--build-y` lets the
build crop start somewhere else once you have seen where a section moved to; `vp_style_diff.py`
prints that offset as `dy`. The output is a plain PNG; nothing here is stored in the repo.

Bounded: one output image per call, at most MAX_OUT_PIXELS pixels, and that bound is checked from
the requested numbers BEFORE any crop is allocated. (It used to be checked afterwards, so a huge
`--w` allocated the huge image first and only then refused; `vp_selftest.py` now fails if the check
moves back after the allocation.)
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

MAX_OUT_PIXELS = 12_000_000
GAP = 8


class SliceTooLarge(Exception):
    """The requested slice would exceed MAX_OUT_PIXELS."""


def plan_slice(ref_size, build_size, x, y, build_y, w, h, scale):
    """Work out both crop boxes and the output size from NUMBERS ONLY, no image allocated.

    Returns (ref_box, build_box, panel_w, panel_h). Boxes are clipped to the image first, so a
    request far outside the image cannot make PIL pad a huge blank crop. Raises SliceTooLarge
    when the output would exceed MAX_OUT_PIXELS.
    """
    if w <= 0 or h <= 0 or scale <= 0:
        raise SliceTooLarge("width, height and scale must be positive")

    def clip(box_x, box_y, size):
        left = max(0, min(box_x, size[0]))
        top = max(0, min(box_y, size[1]))
        right = max(left, min(box_x + w, size[0]))
        bottom = max(top, min(box_y + h, size[1]))
        return (left, top, right, bottom)

    ref_box = clip(x, y, ref_size)
    build_box = clip(x, build_y, build_size)
    panel_w = max(1, int(w * scale))
    panel_h = max(1, int(max(ref_box[3] - ref_box[1], build_box[3] - build_box[1], 1) * scale))
    if (2 * panel_w + GAP) * (panel_h + 16) > MAX_OUT_PIXELS:
        raise SliceTooLarge(
            "output would be about %d pixels, over MAX_OUT_PIXELS=%d; lower --w, --h or --scale"
            % ((2 * panel_w + GAP) * (panel_h + 16), MAX_OUT_PIXELS)
        )
    # the crops themselves are bounded by the clipped boxes, which never exceed the images
    return ref_box, build_box, panel_w, panel_h


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--run", required=True, help="a run directory containing marketing/<slug>.<engine>.png")
    ap.add_argument("--engine", default="blink")
    ap.add_argument("--y", type=int, default=0, help="top of the crop in the Figma frame (px)")
    ap.add_argument("--build-y", type=int, default=None, help="top of the crop in the build (default: same as --y)")
    ap.add_argument("--h", type=int, default=900)
    ap.add_argument("--x", type=int, default=0)
    ap.add_argument("--w", type=int, default=1440)
    ap.add_argument("--scale", type=float, default=0.5, help="output scale (0.5 reads a 1440px page in one glance)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    suite = vp.get_suite("marketing")
    ref_path = suite.store().path_for(args.slug)
    build_path = os.path.join(args.run, "marketing", "%s.%s.png" % (args.slug, args.engine))
    for p in (ref_path, build_path):
        if not os.path.exists(p):
            print("FAIL: missing " + p)
            return 2
    by = args.y if args.build_y is None else args.build_y
    # Image.open reads only the header: sizes are known before any pixel is decoded.
    with Image.open(ref_path) as ref_im, Image.open(build_path) as build_im:
        ref_size, build_size = ref_im.size, build_im.size
        try:
            ref_box, build_box, panel_w, panel_h = plan_slice(
                ref_size, build_size, args.x, args.y, by, args.w, args.h, args.scale)
        except SliceTooLarge as exc:
            print("FAIL: " + str(exc))
            return 2
        a = ref_im.convert("RGB").crop(ref_box)
        b = build_im.convert("RGB").crop(build_box)
    out = Image.new("RGB", (2 * panel_w + GAP, panel_h + 16), (40, 40, 48))
    for i, (img, label) in enumerate(((a, "FIGMA y=%d" % args.y), (b, "BUILD y=%d" % by))):
        tile = img.resize((max(1, int(img.width * args.scale)), max(1, int(img.height * args.scale))), Image.LANCZOS)
        out.paste(tile, (i * (panel_w + GAP), 16))
        ImageDraw.Draw(out).text((4 + i * (panel_w + GAP), 2), label, fill=(255, 220, 120))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    out.save(args.out)
    print("wrote %s (%dx%d); figma frame %dx%d, build capture %dx%d" % (
        args.out, out.width, out.height, ref_size[0], ref_size[1], build_size[0], build_size[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
