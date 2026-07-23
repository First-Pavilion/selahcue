#!/usr/bin/env python3
"""Structural validator for Goal Contracts.

Referenced by .claude/team/GOAL_EXECUTION_PROTOCOL.md as the mandatory check that
must exit 0 before the first iteration of a goal and before claiming completion.

This validator checks STRUCTURE and INTERNAL CONSISTENCY only. It deliberately does
NOT decide whether the underlying work is done — that is the job of the completion
predicate's verifiers and independent verification. Its purpose is to guarantee that
a contract is well-formed, that every mandatory criterion names a verifier / expected
result / evidence location, and that no mandatory criterion is silently left blank.

Usage:
    python3 scripts/validate_goal_contract.py docs/delivery/goals/<goal-id>.md [--require-complete]

Exit codes:
    0  contract is structurally valid (and, with --require-complete, all mandatory rows PASS)
    1  contract has structural errors
    2  usage / file error
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "## Identity",
    "## Objective",
    "## Baseline",
    "## Scope",
    "## Completion predicate",
    "## Verification plan",
    "## Iteration ledger",
]

REQUIRED_IDENTITY_FIELDS = [
    "Goal ID",
    "Role",
    "Status",
    "Execution engine",
    "Maximum iterations",
    "Independent verification required",
]

VALID_STATUSES = {"PENDING", "PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE"}
VALID_ENGINES = {"goal", "ralph"}
VALID_MANDATORY = {"yes", "no"}


def fail(errors: list[str]) -> None:
    print("GOAL CONTRACT VALIDATION: FAIL\n")
    for e in errors:
        print(f"  - {e}")
    print(f"\n{len(errors)} error(s).")
    sys.exit(1)


def parse_predicate_rows(text: str) -> list[dict]:
    """Parse the markdown completion-predicate table into row dicts."""
    rows: list[dict] = []
    in_table = False
    header_seen = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "Criterion" in stripped and "Verifier" in stripped:
            in_table = True
            header_seen = True
            continue
        if in_table:
            if not stripped.startswith("|"):
                # blank / non-table line ends the table
                if stripped == "":
                    continue
                break
            if re.match(r"^\|[\s:|-]+\|$", stripped):
                continue  # separator row
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 7:
                continue
            rows.append(
                {
                    "id": cells[0],
                    "mandatory": cells[1].lower(),
                    "criterion": cells[2],
                    "verifier": cells[3],
                    "expected": cells[4],
                    "evidence": cells[5],
                    "status": cells[6].upper(),
                }
            )
    if not header_seen:
        return []
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument(
        "--require-complete",
        action="store_true",
        help="Also require every mandatory criterion to be PASS (completion check).",
    )
    args = ap.parse_args()

    p = Path(args.path)
    if not p.is_file():
        print(f"ERROR: file not found: {p}", file=sys.stderr)
        sys.exit(2)

    text = p.read_text(encoding="utf-8")
    errors: list[str] = []

    if not re.search(r"^#\s+Goal Contract", text, re.MULTILINE):
        errors.append("Missing top-level '# Goal Contract' heading.")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"Missing required section: '{section}'.")

    # Identity fields
    identity_block = text.split("## Objective")[0]
    for field in REQUIRED_IDENTITY_FIELDS:
        if not re.search(rf"-\s*{re.escape(field)}\s*:", identity_block):
            errors.append(f"Missing Identity field: '{field}'.")

    # Execution engine value
    m = re.search(r"-\s*Execution engine\s*:\s*(\S+)", identity_block)
    if m and m.group(1).lower() not in VALID_ENGINES:
        errors.append(
            f"Execution engine '{m.group(1)}' invalid; must be one of {sorted(VALID_ENGINES)}."
        )

    # Maximum iterations must be a positive integer
    m = re.search(r"-\s*Maximum iterations\s*:\s*(\S+)", identity_block)
    if m:
        try:
            if int(m.group(1)) <= 0:
                errors.append("Maximum iterations must be a positive integer.")
        except ValueError:
            errors.append(f"Maximum iterations '{m.group(1)}' is not an integer.")

    # Completion predicate table
    rows = parse_predicate_rows(text)
    if not rows:
        errors.append(
            "Completion predicate table not found or has no data rows "
            "(expected a markdown table with columns ID | Mandatory | Criterion | "
            "Verifier | Expected result | Evidence | Status)."
        )

    seen_ids: set[str] = set()
    for r in rows:
        rid = r["id"]
        if rid in seen_ids:
            errors.append(f"Duplicate criterion ID: '{rid}'.")
        seen_ids.add(rid)
        if r["mandatory"] not in VALID_MANDATORY:
            errors.append(f"[{rid}] Mandatory column must be 'yes' or 'no', got '{r['mandatory']}'.")
        if r["status"] not in VALID_STATUSES:
            errors.append(
                f"[{rid}] Status '{r['status']}' invalid; must be one of {sorted(VALID_STATUSES)}."
            )
        # Mandatory rows must fully specify verifier / expected / evidence.
        if r["mandatory"] == "yes":
            for col in ("criterion", "verifier", "expected", "evidence"):
                val = r[col]
                if not val or val in {"-", "TBD", "<...>"}:
                    errors.append(f"[{rid}] Mandatory criterion has empty/placeholder '{col}'.")

    if args.require_complete:
        for r in rows:
            if r["mandatory"] == "yes" and r["status"] != "PASS":
                errors.append(
                    f"[{r['id']}] Mandatory criterion is '{r['status']}', not PASS "
                    f"(--require-complete)."
                )

    if errors:
        fail(errors)

    mandatory = sum(1 for r in rows if r["mandatory"] == "yes")
    print("GOAL CONTRACT VALIDATION: PASS")
    print(f"  File: {p}")
    print(f"  Criteria: {len(rows)} total, {mandatory} mandatory.")
    if args.require_complete:
        print("  Completion check: all mandatory criteria PASS.")
    sys.exit(0)


if __name__ == "__main__":
    main()
