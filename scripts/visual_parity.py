#!/usr/bin/env python3
"""Run the whole SelahCue visual-parity harness and open the report.

    python3 scripts/visual_parity.py                 # everything, both web engines
    python3 scripts/visual_parity.py --engine webkit  # closest-to-shipped web engine
    python3 scripts/visual_parity.py --only console stage-worship-running
    python3 scripts/visual_parity.py --skip-native    # web surfaces only

Writes into a fresh run directory under `.visual-parity/` (gitignored) and PRUNES
old runs to `vp_core.MAX_RUNS_KEPT`. That eviction is the harness's own
no-unbounded-growth guard: every run writes ~30 images, so without it the
artefact root grows linearly and forever. `vp_selftest.py` mutation-verifies it.

Read `docs/delivery/VISUAL-PARITY-HARNESS.md` before quoting a number from the
report — especially the section on what it does NOT prove.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("\n$ " + " ".join(cmd))
    return subprocess.run(cmd).returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", default="both", choices=["blink", "webkit", "both"])
    ap.add_argument("--only", nargs="*", default=None, help="limit web captures to these slugs")
    ap.add_argument("--skip-web", action="store_true")
    ap.add_argument("--skip-native", action="store_true")
    ap.add_argument("--min-ssim", type=float, default=None)
    ap.add_argument("--name", default=None, help="run directory name (default: a UTC timestamp)")
    args = ap.parse_args()

    d = vp.run_dir(args.name)
    print("run directory: " + d)

    codes = []
    if not args.skip_web:
        cmd = [sys.executable, os.path.join(HERE, "vp_capture_web.py"), "--out", os.path.join(d, "web"),
               "--engine", args.engine]
        if args.only:
            cmd += ["--only"] + args.only
        codes.append(("web capture", run(cmd)))
    if not args.skip_native:
        codes.append(
            ("native capture", run([sys.executable, os.path.join(HERE, "vp_capture_native.py"),
                                    "--out", os.path.join(d, "native")]))
        )
    cmp_cmd = [sys.executable, os.path.join(HERE, "vp_compare.py"), "--run", d]
    if args.min_ssim is not None:
        cmp_cmd += ["--min-ssim", str(args.min_ssim)]
    # A deliberately narrowed run must not be reported as a full one; only then is
    # an absent catalogued surface acceptable.
    if args.only or args.skip_web or args.skip_native:
        cmp_cmd.append("--allow-missing")
    codes.append(("compare", run(cmp_cmd)))

    print("\n=== visual-parity stages ===")
    for name, code in codes:
        print("  %-16s exit %d" % (name, code))
    kept = sorted(x for x in os.listdir(vp.ARTIFACT_ROOT) if x.startswith("run-"))
    print("  runs kept: %d/%d (%s)" % (len(kept), vp.MAX_RUNS_KEPT, ", ".join(kept)))
    print("  report: %s" % os.path.join(d, "report.html"))
    return max(c for _n, c in codes)


if __name__ == "__main__":
    sys.exit(main())
