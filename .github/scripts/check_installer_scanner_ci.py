#!/usr/bin/env python3
"""Control scanner-only CI event coverage and fail-closed command wiring.

PyYAML is already pinned by the existing workflow-control step. This checks the
committed event configuration, not GitHub's event delivery service. The scanner's
own stdlib-only self-test remains the sole command in the lightweight workflow.
"""

from copy import deepcopy
from pathlib import Path
import runpy

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


# Independent additive baseline: the scanner's own signature/pin/count/floor can
# otherwise be rolled back together and its old45 controls still report success.
# A planned provider-policy removal must explicitly update this baseline too.
BASELINE_SIGNATURES = frozenset({
    "selahcue dev-keys:", "api.deepgram.com", "api.openai.com", "/../../../../.env",
    "DEEPGRAM_API_KEY", "OPENAI_API_KEY", ".env.sample", "repo-root .env",
    "SELAHCUE_UNSAFE_STT_DEVELOPER_OVERRIDE_V1",
})
OPERATOR = "implementation/desktop/crates/selahcue-operator"
BASELINE_TARGETS = frozenset({
    f"{OPERATOR}/target/release/selahcue-operator.exe",
    f"{OPERATOR}/binaries/selahcue-output-*.exe",
    f"{OPERATOR}/binaries/Processing.NDI.Lib.x64.dll",
    f"{OPERATOR}/target/release/bundle/nsis/*-setup.exe",
})
POLICY_FIELDS = (
    "SIGNATURES", "REQUIRED_SIGNATURES", "REQUIRED_SIGNATURE_COUNT",
    "SELF_TEST_CASE_FLOOR", "ENCODINGS", "REQUIRED_ENCODINGS", "REQUIRED_ENCODING_COUNT",
    "TARGETS", "REQUIRED_TARGETS", "REQUIRED_TARGET_COUNT", "MIN_ARTEFACT_BYTES",
    "ARTEFACT_FLOOR_MINIMUM", "ALLOWED_SKIPS",
)


def check_scanner_policy(policy: dict) -> None:
    declared = {name for name, _reason in policy["SIGNATURES"]}
    assert BASELINE_SIGNATURES <= declared, "lost declared scanner baseline signature"
    assert BASELINE_SIGNATURES <= policy["REQUIRED_SIGNATURES"], "lost required scanner baseline signature"
    assert policy["REQUIRED_SIGNATURE_COUNT"] >= 9, "scanner signature floor below9"
    assert policy["SELF_TEST_CASE_FLOOR"] >= 47, "scanner self-test floor below47"
    assert {"utf-8", "utf-16-le"} <= set(policy["ENCODINGS"]), "lost baseline encoding"
    assert {"utf-8", "utf-16-le"} <= policy["REQUIRED_ENCODINGS"], "lost encoding pin"
    assert policy["REQUIRED_ENCODING_COUNT"] >= 2, "encoding floor below2"
    targets = {name: minimum for name, minimum, _reason in policy["TARGETS"]}
    assert BASELINE_TARGETS <= targets.keys(), "lost baseline artifact target"
    assert BASELINE_TARGETS <= policy["REQUIRED_TARGETS"], "lost baseline target pin"
    assert policy["REQUIRED_TARGET_COUNT"] >= 4, "target floor below4"
    assert all(targets[name] >= 1_000_000 for name in BASELINE_TARGETS), "lowered target byte floor"
    assert policy["MIN_ARTEFACT_BYTES"] >= 1_000_000, "lowered artifact byte floor"
    assert policy["ARTEFACT_FLOOR_MINIMUM"] >= 1_000_000, "lowered floor pin"
    assert policy["ALLOWED_SKIPS"] == frozenset({"unreadable_file"}), "expanded scanner skip policy"


def scanner_policy_controls() -> int:
    namespace = runpy.run_path(str(ROOT / "scripts/installer_secret_scan.py"))
    policy = {name: namespace[name] for name in POLICY_FIELDS}
    check_scanner_policy(policy)
    needle = "SELAHCUE_UNSAFE_STT_DEVELOPER_OVERRIDE_V1"
    mutants = []
    for field in ("SIGNATURES", "REQUIRED_SIGNATURES"):
        mutant = deepcopy(policy)
        if field == "SIGNATURES":
            mutant[field] = tuple(row for row in mutant[field] if row[0] != needle)
        else:
            mutant[field] -= {needle}
        mutants.append(mutant)
    for field, value in (("REQUIRED_SIGNATURE_COUNT", 8), ("SELF_TEST_CASE_FLOOR", 45)):
        mutant = deepcopy(policy)
        mutant[field] = value
        mutants.append(mutant)
    mutant = deepcopy(policy)
    mutant["SIGNATURES"] = tuple(row for row in mutant["SIGNATURES"] if row[0] != needle)
    mutant["REQUIRED_SIGNATURES"] -= {needle}
    mutant.update(REQUIRED_SIGNATURE_COUNT=8, SELF_TEST_CASE_FLOOR=45)
    mutants.append(mutant)
    mutant = deepcopy(policy)
    mutant.update(ENCODINGS=("utf-8",), REQUIRED_ENCODINGS=frozenset({"utf-8"}), REQUIRED_ENCODING_COUNT=1)
    mutants.append(mutant)
    mutant = deepcopy(policy)
    removed = next(iter(BASELINE_TARGETS))
    mutant["TARGETS"] = tuple(row for row in mutant["TARGETS"] if row[0] != removed)
    mutant["REQUIRED_TARGETS"] -= {removed}
    mutant["REQUIRED_TARGET_COUNT"] = 3
    mutants.append(mutant)
    mutant = deepcopy(policy)
    mutant["TARGETS"] = tuple((name, 0, reason) for name, _minimum, reason in mutant["TARGETS"])
    mutant.update(MIN_ARTEFACT_BYTES=0, ARTEFACT_FLOOR_MINIMUM=0)
    mutants.append(mutant)
    mutant = deepcopy(policy)
    mutant["ALLOWED_SKIPS"] |= {"missing_file"}
    mutants.append(mutant)
    for mutant in mutants:
        try:
            check_scanner_policy(mutant)
        except AssertionError:
            continue
        raise AssertionError("a regressed scanner baseline passed")
    return len(mutants)


def main() -> None:
    def load(name: str) -> dict:
        return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)

    baseline_mutants = scanner_policy_controls()
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
    print(f"installer scanner CI: 8 event/path cases, {len(mutations)} rejected wiring bypasses and {baseline_mutants} rejected scanner baseline regressions passed (9 signatures/47 controls)")


if __name__ == "__main__":
    main()
