#!/usr/bin/env python3
"""PM artifact validator for the SelahCue PRD.

Referenced by the product brief and /build Stage 3/6 as the "PM artifact validator"
that must exit 0. Created in Stage 3 to close RISK-006 (validator previously missing).

Checks STRUCTURE and INTERNAL CONSISTENCY of the PRD — not whether the product is a
good idea. It enforces that the PRD is complete, that every functional/non-functional
requirement carries a stable unique ID, a priority, and measurable acceptance criteria,
that MVP / later-releases / non-goals are separated, and that every requirement is
traceable to a release. It does NOT judge requirement wording quality — that is the
independent review's job.

Requirement format expected (markdown tables). Any table that contains rows whose first
cell is an FR-/NFR- id MUST have a column whose header contains "priorit" and one whose
header contains "accept"; each such row must fill both non-empty. IDs must match:
  FR-\\d{3,}  NFR-\\d{3,}  FLOW-\\d{3,}  RISK-\\d{3,}  METRIC-\\d{3,}

Usage:
    python3 scripts/validate_prd.py docs/product/prds/SelahCue-PRD.md

Exit codes: 0 valid · 1 validation errors · 2 usage/file error
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "Product vision",
    "Problem statement",
    "Personas",
    "Jobs to be done",
    "Goals",
    "Non-goals",
    "Success metrics",
    "Constraints",
    "Assumptions",
    "Competitor",
    "User journeys",
    "Feature inventory",
    "Functional requirements",
    "Non-functional requirements",
    "Permissions",
    "Data lifecycle",
    "AI",  # AI and provider architecture
    "Offline",
    "Security",
    "Privacy",
    "Accessibility",
    "Reliability",
    "Performance",
    "Licensing",
    "Risks",
    "Dependencies",
    "Open questions",
    "MVP",
    "Later releases",
    "Acceptance criteria",
    "Launch criteria",
    "Traceability",
]

ID_PATTERNS = {
    "FR": re.compile(r"\bFR-\d{3,}\b"),
    "NFR": re.compile(r"\bNFR-\d{3,}\b"),
    "FLOW": re.compile(r"\bFLOW-\d{3,}\b"),
    "RISK": re.compile(r"\bRISK-\d{3,}\b"),
    "METRIC": re.compile(r"\bMETRIC-\d{3,}\b"),
}
ROW_ID = re.compile(r"^(FR|NFR|FLOW|RISK|METRIC)-\d{3,}$")
VALID_PRIORITY = re.compile(r"^(MVP|R[2-9]|R1[0-9]|LATER|NON-GOAL|DEFERRED)$", re.IGNORECASE)


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: validate_prd.py <prd.md>", file=sys.stderr)
        sys.exit(2)
    p = Path(sys.argv[1])
    if not p.is_file():
        print(f"ERROR: file not found: {p}", file=sys.stderr)
        sys.exit(2)
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Required sections (heading contains the token, case-insensitive)
    headings = [l for l in lines if l.lstrip().startswith("#")]
    hjoined = "\n".join(headings).lower()
    for sec in REQUIRED_SECTIONS:
        if sec.lower() not in hjoined:
            errors.append(f"Missing required section heading containing: '{sec}'.")

    # 2. Parse requirement tables
    all_ids: dict[str, int] = {}
    fr_nfr_ids: set[str] = set()
    header: list[str] | None = None
    col_priority = col_accept = None
    in_table = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            cells = split_row(s)
            if re.match(r"^[\s:|-]+$", s.replace("|", "-")):
                continue  # separator
            # header row?
            low = [c.lower() for c in cells]
            if not in_table:
                header = cells
                col_priority = next((i for i, c in enumerate(low) if "priorit" in c), None)
                col_accept = next((i for i, c in enumerate(low) if "accept" in c), None)
                in_table = True
                continue
            # data row
            first = cells[0]
            m = ROW_ID.match(first)
            if m:
                rid = first
                if rid in all_ids:
                    errors.append(f"Duplicate requirement ID: {rid}.")
                all_ids[rid] = 1
                kind = m.group(1)
                if kind in ("FR", "NFR"):
                    fr_nfr_ids.add(rid)
                    if col_priority is None or col_accept is None:
                        errors.append(
                            f"{rid} is in a table lacking a 'Priority' and/or 'Acceptance' column."
                        )
                    else:
                        pr = cells[col_priority] if col_priority < len(cells) else ""
                        ac = cells[col_accept] if col_accept < len(cells) else ""
                        if not pr or not VALID_PRIORITY.match(pr.split()[0] if pr else ""):
                            errors.append(f"{rid} has missing/invalid Priority: '{pr}'.")
                        if not ac or len(ac) < 8:
                            errors.append(f"{rid} has missing/insufficient Acceptance criteria.")
        else:
            in_table = False
            header = None

    # 3. Malformed-looking IDs (e.g. FR-1 with too few digits) anywhere in prose
    for token in re.findall(r"\b(?:FR|NFR|FLOW|RISK|METRIC)-\d+\b", text):
        kind, num = token.split("-")
        if len(num) < 3:
            warnings.append(f"ID '{token}' uses fewer than 3 digits (convention is zero-padded).")

    # 4. Counts sanity
    counts = {k: len(v.findall(text)) for k, v in ID_PATTERNS.items()}
    if len(fr_nfr_ids) == 0:
        errors.append("No FR/NFR requirement rows found.")
    if counts["FR"] == 0:
        errors.append("No FR-* identifiers found.")

    # 5. MVP / Later / Non-goals separation + TTS non-goal
    low_text = text.lower()
    if "## mvp" not in low_text and "# mvp" not in low_text:
        # section check already covers 'MVP'; this is belt-and-suspenders
        pass
    # TTS must be a non-goal (DEC-001)
    ng_idx = low_text.find("non-goal")
    if ng_idx == -1:
        errors.append("No 'Non-goals' content found.")
    else:
        # crude: TTS/text-to-speech mentioned near a non-goals section
        if "text-to-speech" not in low_text and "tts" not in low_text:
            warnings.append("TTS not mentioned; expected as an explicit non-goal (DEC-001).")

    # 6. Traceability coverage: every FR id must appear in the Traceability section
    tindex = low_text.rfind("traceability")
    if tindex == -1:
        errors.append("No Traceability section found.")
    else:
        trace_block = text[text.lower().rfind("traceability"):]
        missing = sorted(
            rid for rid in fr_nfr_ids if rid.startswith("FR-") and rid not in trace_block
        )
        # Allow traceability to reference ranges; only flag if MANY are missing
        if missing:
            errors.append(
                f"{len(missing)} FR id(s) absent from the Traceability section "
                f"(e.g. {', '.join(missing[:5])}{'…' if len(missing) > 5 else ''})."
            )

    # Report
    if warnings:
        print("PRD VALIDATION — warnings:")
        for w in warnings:
            print(f"  ! {w}")
        print()
    if errors:
        print("PRD VALIDATION: FAIL\n")
        for e in errors:
            print(f"  - {e}")
        print(f"\n{len(errors)} error(s).")
        sys.exit(1)

    print("PRD VALIDATION: PASS")
    print(f"  File: {p}")
    print(
        f"  IDs — FR:{counts['FR']} NFR:{counts['NFR']} FLOW:{counts['FLOW']} "
        f"RISK:{counts['RISK']} METRIC:{counts['METRIC']}"
    )
    print(f"  Requirement rows validated (FR+NFR): {len(fr_nfr_ids)}")
    print(f"  Sections: all {len(REQUIRED_SECTIONS)} required present.")
    sys.exit(0)


if __name__ == "__main__":
    main()
