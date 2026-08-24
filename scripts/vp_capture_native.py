#!/usr/bin/env python3
"""Native-surface capture for the visual-parity harness.

The stage/confidence monitor and the audience output are composed by the CPU
rasterizer in `selahcue-engine` and never exist as a DOM, so no browser can
screenshot them. This runs the Rust capture target that renders them to PNG:

    cargo test -p selahcue-present --test visual_parity_render \
        export_captures_when_the_harness_asks_for_them -- --nocapture

with `SELAHCUE_VISUAL_OUT` pointing at the run directory. The same Rust file
asserts, on every ordinary `cargo test -p selahcue-present`, that each capture
renders at its Figma frame's size and actually drew ink — so a silently blank
native capture fails the normal test suite, not just this harness.

    python3 scripts/vp_capture_native.py --out DIR

ENGINE: `selahcue-engine`'s deterministic CPU rasterizer — the SAME code path the
GPU compositor is held to at SSIM >= 0.99 by `selahcue-gpu/tests/test_parity.rs`.
These images are therefore faithful to what the output window draws, up to that
parity bound; they are not screenshots of a running app's window chrome.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402

MANIFEST = os.path.join(vp.REPO, "implementation", "desktop", "Cargo.toml")
TEST_TARGET = "visual_parity_render"
TEST_NAME = "export_captures_when_the_harness_asks_for_them"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--surfaces", default=vp.SURFACES_PATH)
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, SELAHCUE_VISUAL_OUT=out)
    cmd = [
        "cargo", "test", "--manifest-path", MANIFEST,
        "-p", "selahcue-present", "--test", TEST_TARGET, TEST_NAME, "--", "--nocapture",
    ]
    print("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    tail = (proc.stdout or "").strip().splitlines()[-12:]
    for line in tail:
        print("  " + line)
    if proc.returncode != 0:
        print((proc.stderr or "").strip()[-2000:])
        print("FAIL: the native capture target did not pass (exit %d)" % proc.returncode)
        return 1

    index_path = os.path.join(out, "index.json")
    if not os.path.exists(index_path):
        print("FAIL: the capture target ran but wrote no index.json to " + out)
        return 2
    with open(index_path, "r", encoding="utf-8") as fh:
        index = json.load(fh)

    catalogue = vp.load_json(args.surfaces)
    declared = {e["slug"]: e for e in catalogue.get("native", [])}
    results = []
    problems = []
    for cap in index.get("captures", []):
        slug = cap["slug"]
        entry = declared.get(slug)
        png = os.path.join(out, cap["file"])
        if entry is None:
            problems.append("%s: rendered but absent from surfaces.json `native`" % slug)
            continue
        if not os.path.exists(png):
            problems.append("%s: index.json lists %s but the file is missing" % (slug, cap["file"]))
            continue
        results.append(
            {
                "slug": slug,
                "state": slug,
                "node": entry.get("node", ""),
                "reference": entry.get("reference", ""),
                "reference_kind": entry.get("reference_kind", "screen"),
                "expected_size": [entry["width"], entry["height"]],
                "actual_size": [cap["width"], cap["height"]],
                "scale": 1,
                "png": cap["file"],
                "engine": "cpu-raster",
                "engine_detail": index.get("engine", "selahcue-engine CPU rasterizer"),
                "ink": cap.get("ink"),
                "driver": {"regions": []},
                "errors": [],
                "ok": True,
            }
        )
    for slug in declared:
        if slug not in {r["slug"] for r in results}:
            problems.append("%s: declared in surfaces.json but never rendered" % slug)

    vp.dump_json(
        os.path.join(out, "captures.json"),
        {"engines": [{"engine": "cpu-raster", "detail": index.get("engine", "")}], "captures": results},
    )
    for p in problems:
        print("FAIL: " + p)
    print("=== native capture: %d images, %d problem(s) ===" % (len(results), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
