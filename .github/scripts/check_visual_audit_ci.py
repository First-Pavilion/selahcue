#!/usr/bin/env python3
"""Check visual/audit CI wiring and ordered trigger-path cases; optionally run/time its shared gate.

The event patterns used here contain only **, exclusions and literals, for which
fnmatch matches the documented GitHub ordered path semantics. This is a control
of the committed workflow, not a claim to execute GitHub's event service locally.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[2]
TARGET = "visual-audit-check"
PATTERNS = {"**", "!docs/**", "!**.md", "!TODO", "docs/design/visual-parity/**",
            "docs/release/pilot-registration/notice.json"}
CASES = {
    "scripts/vp_selftest.py": True,
    "scripts/vp_compare.py": True,
    "docs/design/visual-parity/marketing/findings/home.json": True,
    "docs/design/visual-parity/README.md": True,
    "docs/ops/DEPLOYMENT.md": False,
    "docs/elsewhere/data.json": False,
    "docs/release/pilot-registration/notice.json": True,
    "docs/release/pilot-registration/notice.md": False,
    "docs/release/pilot-registration/other.json": False,
    "docs/release/pilot-registration/notice.json.backup": False,
    "README.md": False,
    "implementation/desktop/README.md": False,
    "TODO": False,
    "implementation/marketing/src/App.vue": True,
}


def selected(path: str, patterns: list[str]) -> bool:
    included = False
    for pattern in patterns:
        negative = pattern.startswith("!")
        if fnmatch.fnmatchcase(path, pattern[1:] if negative else pattern):
            included = not negative
    return included


def check(root: Path) -> None:
    workflow = yaml.load((root / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    for event in ("push", "pull_request"):
        config = workflow["on"][event]
        patterns = config.get("paths")
        if ("paths-ignore" in config or not isinstance(patterns, list)
                or any(p not in PATTERNS for p in patterns)):
            raise ValueError(f"{event}: unsupported paths or paths-ignore; update trigger controls explicitly")
        for path, expected in CASES.items():
            if selected(path, patterns) != expected:
                raise ValueError(f"{event}: wrong trigger result for {path}; expected {expected}")
    lint = workflow["jobs"]["lint-workflows"]
    # Gate is intentionally unconditional within this existing job; no expensive
    # desktop/browser filter is needed for visual-audit-doc-only changes.
    gate = [s for s in lint["steps"] if s.get("run") == "python3 .github/scripts/check_visual_audit_ci.py --run"]
    if len(gate) != 1 or "if" in gate[0] or lint.get("needs"):
        raise ValueError("Expected one unconditional shared visual gate in lint-workflows")
    checkout = [s for s in lint["steps"] if s.get("uses", "").startswith("actions/checkout@")]
    if not checkout or checkout[0].get("with", {}).get("fetch-depth") != "0":
        raise ValueError("Visual audit CI needs full checkout history")
    makefile = (root / "Makefile").read_text()
    recipe = re.search(r"^visual-audit-check:[^\n]*\n((?:\t[^\n]*\n)+)", makefile, re.M)
    expected = ["python3 scripts/vp_selftest.py", "python3 scripts/check_fidelity_audit.py --self-test",
                "python3 scripts/check_fidelity_audit.py --require-tickets --check-report"]
    if not recipe or [line.strip() for line in recipe.group(1).splitlines()] != expected:
        raise ValueError("Shared target does not run all three existing visual/audit checks")
    ci = re.search(r"^ci:[^\n]*\n((?:\t[^\n]*\n)+)", makefile, re.M)
    if not ci or "$(MAKE_RECURSE) --no-print-directory visual-audit-check" not in ci.group(1):
        raise ValueError("make ci does not call the shared visual-audit-check target")
    scripts = json.loads((root / "implementation/marketing/package.json").read_text())["scripts"]
    marketing = workflow["jobs"]["marketing"]
    for suite in ("components", "core", "home", "secondary"):
        steps = [s for s in marketing["steps"] if s.get("run") == f"npm run test:{suite}"]
        if (len(steps) != 1 or steps[0].get("env", {}).get("SELAHCUE_HEADLESS_REQUIRE") != "1"
                or steps[0].get("if") != "${{ !cancelled() }}"):
            raise ValueError(f"Missing required-engine/not-cancelled browser suite: {suite}")
        if "--engine both" not in scripts[f"test:{suite}"]:
            raise ValueError(f"Both browser engines are required: {suite}")
    print(f"Visual CI wiring: {len(CASES) * 2} ordered push/PR path cases and shared/browser gates pass")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="also execute/time the same Makefile target as make ci")
    args = parser.parse_args()
    try:
        check(ROOT)
        if args.run:
            start = time.monotonic()
            subprocess.run(["make", TARGET], cwd=ROOT, check=True)
            elapsed = time.monotonic() - start
            print(f"visual-audit-check elapsed: {elapsed:.3f}s (limit <10s)", flush=True)
            if elapsed >= 10:
                raise ValueError("No-browser visual/audit gate exceeded the 10-second budget")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Visual CI gate failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
