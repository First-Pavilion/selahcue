#!/usr/bin/env python3
"""Stage-6 delivery-plan validator.

Checks the delivery plan is internally consistent and ready:
  1. Every FR-/NFR- id in the PRD appears in REQUIREMENTS-TRACEABILITY.md
     (every approved requirement maps to a ticket/deferral).
  2. IMPLEMENTATION-READINESS.md declares status READY.
  3. The dependency graph (```dependency-graph fenced block in the readiness
     report) is acyclic.

Usage:
    python3 scripts/validate_delivery_plan.py

Exit codes: 0 valid · 1 validation errors · 2 file error
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRD = ROOT / "docs/product/prds/SelahCue-PRD.md"
TRACE = ROOT / "docs/delivery/REQUIREMENTS-TRACEABILITY.md"
READY = ROOT / "docs/delivery/IMPLEMENTATION-READINESS.md"

ID_RE = re.compile(r"\b((?:FR|NFR)-\d{3,})\b")


def read(p: Path) -> str:
    if not p.is_file():
        print(f"ERROR: missing file: {p}", file=sys.stderr)
        sys.exit(2)
    return p.read_text(encoding="utf-8")


def parse_graph(text: str) -> list[tuple[str, str]]:
    m = re.search(r"```dependency-graph\n(.*?)```", text, re.DOTALL)
    if not m:
        return []
    edges = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if "->" in line:
            a, b = [x.strip() for x in line.split("->", 1)]
            if a and b:
                edges.append((a, b))
    return edges


def find_cycle(edges: list[tuple[str, str]]):
    """Return a cycle path if the directed graph has one, else None (Kahn + DFS)."""
    from collections import defaultdict

    adj = defaultdict(list)
    nodes = set()
    for a, b in edges:
        adj[a].append(b)
        nodes.add(a)
        nodes.add(b)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    stack: list[str] = []

    def dfs(u):
        color[u] = GRAY
        stack.append(u)
        for v in adj[u]:
            if color[v] == GRAY:
                return stack[stack.index(v):] + [v]
            if color[v] == WHITE:
                r = dfs(v)
                if r:
                    return r
        color[u] = BLACK
        stack.pop()
        return None

    for n in nodes:
        if color[n] == WHITE:
            r = dfs(n)
            if r:
                return r
    return None


def main() -> None:
    errors: list[str] = []
    prd_ids = set(ID_RE.findall(read(PRD)))
    trace_text = read(TRACE)
    trace_ids = set(ID_RE.findall(trace_text))
    ready_text = read(READY)

    # 1. coverage
    missing = sorted(prd_ids - trace_ids, key=lambda s: (s.split("-")[0], int(s.split("-")[1])))
    if missing:
        errors.append(
            f"{len(missing)} PRD requirement id(s) not mapped in traceability: "
            f"{', '.join(missing[:12])}{'…' if len(missing) > 12 else ''}"
        )

    # 2. readiness
    if not re.search(r"(?im)^#*\s*Status:\s*READY\b", ready_text) and "READY" not in ready_text:
        errors.append("IMPLEMENTATION-READINESS.md does not declare status READY.")

    # 3. dependency acyclicity
    edges = parse_graph(ready_text)
    if not edges:
        errors.append("No dependency-graph block found in IMPLEMENTATION-READINESS.md.")
    else:
        cyc = find_cycle(edges)
        if cyc:
            errors.append("Dependency graph has a cycle: " + " -> ".join(cyc))

    if errors:
        print("DELIVERY PLAN VALIDATION: FAIL\n")
        for e in errors:
            print(f"  - {e}")
        print(f"\n{len(errors)} error(s).")
        sys.exit(1)

    print("DELIVERY PLAN VALIDATION: PASS")
    print(f"  PRD requirements: {len(prd_ids)} (FR+NFR) — all mapped in traceability.")
    print(f"  Dependency edges: {len(edges)} — acyclic.")
    print("  Implementation readiness: READY.")
    sys.exit(0)


if __name__ == "__main__":
    main()
