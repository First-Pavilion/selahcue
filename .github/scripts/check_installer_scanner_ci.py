#!/usr/bin/env python3
"""Control scanner-only CI event coverage and fail-closed command wiring.

PyYAML is already pinned by the existing workflow-control step. This checks the
committed event configuration, not GitHub's event delivery service. The scanner's
own stdlib-only self-test remains the sole command in the lightweight workflow.
"""

from copy import deepcopy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMMAND = "python3 scripts/installer_secret_scan.py --self-test"


def check(workflow: dict, ci: dict) -> None:
    events = workflow["on"]
    assert set(events) == {"push", "pull_request"}, "only ordinary push/PR events"
    assert events["push"] == {"branches": ["main"]}, "unfiltered main pushes"
    assert events["pull_request"] == {"types": ["opened", "synchronize", "reopened"]}, "unfiltered PR lifecycle"
    assert workflow["permissions"] == {"contents": "read"}, "read-only token"
    assert set(workflow["jobs"]) == {"self-test"}, "one small job"
    job = workflow["jobs"]["self-test"]
    assert set(job) == {"runs-on", "timeout-minutes", "steps"}, "no job bypass/needs/matrix"
    assert job["runs-on"] == "ubuntu-latest" and job["timeout-minutes"] == "2"
    checkout, gate = job["steps"]
    assert set(checkout) == {"uses", "with"} and checkout["uses"] == "actions/checkout@v7"
    assert checkout["with"] == {
        "persist-credentials": "false",
        "sparse-checkout": "scripts/installer_secret_scan.py",
        "sparse-checkout-cone-mode": "false",
    }, "scanner-only checkout, no persisted token"
    assert set(gate) == {"name", "run"} and gate["run"] == COMMAND, "unmasked self-test only"
    lint = ci["jobs"]["lint-workflows"]
    assert not lint.get("needs"), "API/source CI must not path-gate the shared job"
    gates = [step for step in lint["steps"] if step.get("run") == COMMAND]
    assert len(gates) == 1 and set(gates[0]) == {"name", "run"}, "unmasked ordinary CI invocation"


def main() -> None:
    def load(name: str) -> dict:
        return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)

    workflow, ci = load("installer-scanner-controls.yml"), load("ci.yml")
    check(workflow, ci)
    # A trigger with no paths/paths-ignore covers each representative changed file.
    # Exact event checks above reject either kind of path filtering for both events.
    for event in ("push", "pull_request"):
        for path in ("README.md", "docs/ops/runbook.md", "implementation/api/app.py", "scripts/example.py"):
            assert not {"paths", "paths-ignore"}.intersection(workflow["on"][event]), path
    mutations = []
    for event in ("push", "pull_request"):
        for key in ("paths", "paths-ignore"):
            mutant = deepcopy(workflow)
            mutant["on"][event][key] = ["scripts/**"]
            mutations.append(mutant)
    for key in ("if", "continue-on-error"):
        mutant = deepcopy(workflow)
        mutant["jobs"]["self-test"]["steps"][1][key] = "true"
        mutations.append(mutant)
    mutant = deepcopy(workflow)
    mutant["jobs"]["self-test"]["steps"][1]["run"] += " || true"
    mutations.append(mutant)
    for mutant in mutations:
        try:
            check(mutant, ci)
        except AssertionError:
            continue
        raise AssertionError("a broken CI control passed")
    print(f"installer scanner CI: 8 event/path cases and {len(mutations)} rejected bypass mutations passed")


if __name__ == "__main__":
    main()
