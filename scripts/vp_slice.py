#!/usr/bin/env python3
"""Cut a side-by-side slice of a Figma frame and the matching build capture, for a human to read.

    python3 scripts/vp_slice.py --slug home --run RUN_DIR --y 0 --h 900 --out /tmp/home-0.png
    python3 scripts/vp_slice.py --slug home --run RUN_DIR --y 900 --build-y 1010 --h 900 --scale 1 \
        --x 0 --w 720 --out /tmp/zoom.png

Figma on the left, the build on the right, same crop of each. A long page grows or shrinks as it
goes (the build carries real content where Figma drew a placeholder), so `--build-y` lets the
build crop start somewhere else once you have seen where a section moved to; `vp_style_diff.py`
prints that offset as `dy`. The output is a plain PNG; nothing here is stored in the repo.

Bounded: one output image per call, at most MAX_OUT_PIXELS pixels.
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


def main():
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
    args = ap.parse_args()

    suite = vp.get_suite("marketing")
    ref_path = suite.store().path_for(args.slug)
    build_path = os.path.join(args.run, "marketing", "%s.%s.png" % (args.slug, args.engine))
    for p in (ref_path, build_path):
        if not os.path.exists(p):
            print("FAIL: missing " + p)
            return 2
    by = args.y if args.build_y is None else args.build_y
    with Image.open(ref_path) as ref_im, Image.open(build_path) as build_im:
        ref = ref_im.convert("RGB")
        build = build_im.convert("RGB")
        a = ref.crop((args.x, args.y, args.x + args.w, min(args.y + args.h, ref.height)))
        b = build.crop((args.x, by, args.x + args.w, min(by + args.h, build.height)))
    h = max(a.height, b.height, 1)
    panel_w = int(args.w * args.scale)
    panel_h = int(h * args.scale)
    if (2 * panel_w + GAP) * panel_h > MAX_OUT_PIXELS:
        print("FAIL: output would exceed MAX_OUT_PIXELS=%d; lower --h or --scale" % MAX_OUT_PIXELS)
        return 2
    out = Image.new("RGB", (2 * panel_w + GAP, panel_h + 16), (40, 40, 48))
    for i, (img, label) in enumerate(((a, "FIGMA y=%d" % args.y), (b, "BUILD y=%d" % by))):
        tile = img.resize((max(1, int(img.width * args.scale)), max(1, int(img.height * args.scale))), Image.LANCZOS)
        out.paste(tile, (i * (panel_w + GAP), 16))
        ImageDraw.Draw(out).text((4 + i * (panel_w + GAP), 2), label, fill=(255, 220, 120))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    out.save(args.out)
    print("wrote %s (%dx%d); figma frame %dx%d, build capture %dx%d" % (
        args.out, out.width, out.height, ref.width, ref.height, build.width, build.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
