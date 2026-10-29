"""Run the customer-auth siblings with only reset's final padding call removed.

Usage, from implementation/api:
    python /path/to/mutate_reset_pad.py /path/to/evidence-directory

The source is restored byte-for-byte even if pytest is interrupted. This diagnostic is
successful only if the actual real-broker uniformity test fails with its siblings running.
It neither changes the floor setting nor removes the resend pad.
"""

import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    source = Path("selahcue_api/apps/accounts/services.py")
    evidence = Path(sys.argv[1]).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    original = source.read_bytes()
    tree = ast.parse(original)
    reset = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "request_password_reset")
    calls = [
        node for node in ast.walk(reset)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id == "_pad_to_floor"
    ]
    assert len(calls) == 1, "expected exactly one reset padding expression"
    call = calls[0]
    lines = original.splitlines(keepends=True)
    replacement = b" " * call.col_offset + b"pass  # diagnostic: only reset padding removed\n"
    mutated = b"".join(lines[:call.lineno - 1] + [replacement] + lines[call.end_lineno:])
    receipt = {"source_sha256": hashlib.sha256(original).hexdigest(), "mutation": "remove reset's _pad_to_floor expression only"}
    environment = os.environ.copy()
    environment.pop("RESET_FLOOR_MEASUREMENT_MODE", None)
    environment["RESET_FLOOR_EVIDENCE_DIR"] = str(evidence / "timing")
    junit = evidence / "mutation.xml"
    try:
        source.write_bytes(mutated)
        with (evidence / "mutation.log").open("w") as log:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/test_customer_auth_slice.py", "-q", "-s", f"--junitxml={junit}"],
                env=environment, stdout=log, stderr=subprocess.STDOUT, check=False,
            )
        receipt["pytest_exit_code"] = result.returncode
        assert result.returncode == 1, "mutation must fail assertions, not collection or setup"
        root = ET.parse(junit).getroot()
        testcases = list(root.iter("testcase"))
        uniformity = [case for case in testcases if case.attrib.get("name") == "test_reset_request_real_publisher_timing_is_uniform"]
        assert len(uniformity) == 1
        failure = uniformity[0].find("failure")
        assert failure is not None, "actual uniformity test must fail; a wiring-only red is insufficient"
        failure_text = failure.attrib.get("message", "") + (failure.text or "")
        assert "paired timing interval" in failure_text
        timing = json.loads((evidence / "timing" / "candidate-timing.json").read_text())
        verdict = timing["timing_protocol"]["verdict"]
        assert verdict["passed"] is False
        assert verdict["classification"] in {"signed_mean_gap", "signed_median_gap"}, (
            "mutation must demonstrate a signed timing gap, not inconclusive precision or a null/wiring-only failure"
        )
        assert verdict["classification"] in failure_text
        receipt["timing_classification"] = verdict["classification"]
        assert len(testcases) > 100, "mutation must execute the module siblings, not only an exact test"
        assert not list(root.iter("error")), "setup errors cannot masquerade as the required mutation red"
        receipt["uniformity_failed"] = True
        receipt["sibling_testcases"] = len(testcases)
        receipt["failed_testcases"] = [case.attrib["name"] for case in testcases if case.find("failure") is not None]
    finally:
        source.write_bytes(original)
        receipt["restored_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        receipt["source_restored_exactly"] = source.read_bytes() == original
        (evidence / "mutation-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
        assert receipt["source_restored_exactly"]
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
