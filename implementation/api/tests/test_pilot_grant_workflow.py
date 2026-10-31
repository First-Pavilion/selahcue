"""Run shipped workflow Code against literal package/response boundary fixtures."""

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from test_pilot_workflow import form


pytestmark = pytest.mark.django_db

ROOT = Path(__file__).parents[3] / "docs/release/pilot-registration"
NOW = 1793476800
SHA = "a" * 64
PACKAGE = {
    "schema_version": 1, "api_origin": "https://api.example.invalid",
    "notice_version": "approved-fixture-v1", "form_path": "pilot-fixture-ubuntu",
    "artifact_id": "ubuntu-fixture-1", "release_id": "fixture-release-1", "version": "1.2.3",
    "platform": "Ubuntu", "architectures": ["x86_64"], "sha256": SHA,
    "size_bytes": 35737754, "object_key": "pilot/fixture-release-1/" + SHA + "/SelahCue.deb",
    "download_origin": "https://downloads.example.invalid",
    "signed_query_keys": ["signature", "expires"], "max_ttl_seconds": 300,
}


def built(config=None):
    spec = importlib.util.spec_from_file_location("grant_workflow_builder", ROOT / "build_workflow.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build(deployment=PACKAGE if config is None else config)


def named(name, config=None):
    return next(n for n in built(config)["nodes"] if n["name"] == name)


def execute(name, value, *, config=None, selected=None, saved=None, now=NOW):
    code = named(name, config)["parameters"]["jsCode"]
    program = """const fs=require('node:fs'); const d=JSON.parse(fs.readFileSync(0,'utf8'));
const nodes={'Validate registration':d.selected,'Validate saved receipt':d.saved};
const clock=class extends Date {static now(){return d.now*1000;}};
try { const result=new Function('$input','$','Date',d.code)(
 {first:()=>({json:d.value})}, name=>({first:()=>({json:nodes[name]})}), clock);
 process.stdout.write(JSON.stringify({result}));
} catch(e) {process.stdout.write(JSON.stringify({error:e.message}));}"""
    run = subprocess.run(["node", "-e", program], text=True, capture_output=True, check=True,
                         input=json.dumps(dict(code=code, value=value, selected=selected, saved=saved, now=now)))
    return json.loads(run.stdout)


def selected():
    return execute("Validate registration", form())["result"][0]["json"]


def grant(**changes):
    value = {"schema_version": 1, "artifact_id": "ubuntu-fixture-1", "release_id": "fixture-release-1",
             "platform": "Ubuntu", "architectures": ["x86_64"], "sha256": SHA, "size_bytes": 35737754,
             "download_url": "https://downloads.example.invalid/pilot/fixture-release-1/" + SHA + "/SelahCue.deb?signature=synthetic%26proof&expires=1793476920",
             "expires_at": NOW + 120}
    value.update(changes)
    return value


def receipt():
    return {"schema_version": 1, "registration_id": form()["registration_id"], "state": "confirmed",
            "receipt": "SYNTHETIC-RECEIPT-NOT-AUTHORIZATION", "expires_at": NOW + 600}


def test_fixed_package_is_shown_and_wrong_os_refused_before_reservation():
    trigger = named("Pilot registration")["parameters"]
    assert all(part in trigger["formDescription"] for part in ("Ubuntu", "x86_64", "1.2.3"))
    good = selected()
    assert good["valid"] is True
    assert good["deployment"]["artifact_id"] == "ubuntu-fixture-1"
    bad = execute("Validate registration", form(platform="macOS"))["result"][0]["json"]
    assert bad["valid"] is False
    assert "return" in bad["errors"].lower()
    # Client-supplied release/path selections must not replace fixed deployment.
    injected = execute("Validate registration", form(artifact_id="other", object_key="other"))["result"][0]["json"]
    assert injected["deployment"]["artifact_id"] == "ubuntu-fixture-1"


@pytest.mark.parametrize("change", [
    {"artifact_id": "REPLACE_WITH_ARTIFACT"}, {"architectures": ["aarch64"]}, {"platform": "Android"},
    {"api_origin": "http://api.example.invalid"}, {"download_origin": "https://user@downloads.example.invalid"},
    {"sha256": "not-a-sha"}, {"size_bytes": 0}, {"object_key": "../SelahCue.deb"},
    {"max_ttl_seconds": 301}, {"signed_query_keys": ["email"]}, {"signed_query_keys": ["signature", "signature"]},
])
def test_invalid_deployment_cannot_reserve_registration(change):
    value = execute("Validate registration", form(), config={**PACKAGE, **change})["result"][0]["json"]
    assert value["valid"] is False


def test_both_confirmed_paths_join_one_dedicated_grant_and_failure_never_completes_download():
    graph = built()["connections"]
    assert graph["Already confirmed"]["main"][0][0]["node"] == "Validate saved receipt"
    assert graph["Confirm acknowledged write"]["main"][0][0]["node"] == "Validate saved receipt"
    assert graph["Validate saved receipt"]["main"][0][0]["node"] == "Request private download"
    assert graph["Request private download"]["main"][0][0]["node"] == "Validate private download"
    assert graph["Validate private download"]["main"][0][0]["node"] == "Download ready"
    for name in ("Write fixed Sheet row", "Confirm acknowledged write", "Validate saved receipt", "Request private download", "Validate private download"):
        assert graph[name]["main"][1][0]["node"] == "Retry registration"
    request = named("Request private download")["parameters"]
    assert request["genericAuthType"] == "httpHeaderAuth"
    assert "downloads:grant" in request["url"]
    # Execute the actual JSON body expression: only receipt and fixed ID cross this boundary.
    expression = request["jsonBody"][3:-3].strip()
    program = "const x=JSON.parse(process.argv[1]);const $json=x.saved;const $=()=>({first:()=>({json:x.selected})});process.stdout.write(" + expression + ");"
    actual = subprocess.run(["node", "-e", program, json.dumps({"saved": receipt(), "selected": selected()})],
                            text=True, capture_output=True, check=True)
    assert json.loads(actual.stdout) == {"schema_version": 1, "receipt": "SYNTHETIC-RECEIPT-NOT-AUTHORIZATION", "artifact_id": "ubuntu-fixture-1"}


def test_valid_grant_returns_escaped_package_link_and_no_registration_data():
    checked = execute("Validate private download", grant(), selected=selected(), saved=receipt())
    result = checked["result"][0]["json"]
    assert "href=\"https://downloads.example.invalid/" in result["completion_html"]
    assert "&amp;expires=" in result["completion_html"]
    assert "Ubuntu" in result["completion_html"] and "1.2.3" in result["completion_html"]
    serialized = json.dumps(result)
    for forbidden in ("SYNTHETIC-RECEIPT-NOT-AUTHORIZATION", form()["registration_id"], "Test Operator", "test@example.invalid", "Test church"):
        assert forbidden not in serialized
    assert set(result) == {"completion_html"}


@pytest.mark.parametrize("change", [
    {"schema_version": True}, {"artifact_id": "other"}, {"release_id": "other"}, {"platform": "Windows"},
    {"architectures": ["aarch64"]}, {"sha256": "b" * 64}, {"size_bytes": 123},
    {"expires_at": NOW}, {"expires_at": NOW + 301}, {"expires_at": NOW + 601},
    {"download_url": "https://evil.example.invalid/file?signature=x"},
    {"download_url": "https://downloads.example.invalid/other?signature=x"},
    {"download_url": "https://downloads.example.invalid/pilot/fixture-release-1/" + SHA + "/SelahCue.deb?email=private%40example.invalid"},
    {"download_url": "https://downloads.example.invalid/pilot/fixture-release-1/" + SHA + "/SelahCue.deb?signature=x&signature=y"},
    {"download_url": "https://downloads.example.invalid/pilot/fixture-release-1/" + SHA + "/SelahCue.deb?signature=%3Cscript%3E#bad"},
    {"receipt": "should-not-be-here"},
])
def test_malformed_or_mismatched_grant_never_releases_a_link(change):
    result = execute("Validate private download", grant(**change), selected=selected(), saved=receipt())
    assert set(result) == {"error"}
    assert "private@example.invalid" not in result["error"]
    assert "https://" not in result["error"]


def test_grant_cannot_outlive_the_original_receipt_or_fixed_cohort():
    saved = {**receipt(), "expires_at": NOW + 30}
    assert "error" in execute("Validate private download", grant(), selected=selected(), saved=saved)
    cutoff = 1809129599
    assert "error" in execute("Validate private download", grant(expires_at=cutoff + 1), selected=selected(),
                              saved={**saved, "expires_at": cutoff + 10}, now=cutoff - 10)
