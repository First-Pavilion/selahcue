import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_pilot_registration_service import payload, pilot_policy
from selahcue_api.apps.pilot_downloads.services import reserve_registration


ROOT = Path(__file__).parents[3] / "docs/release/pilot-registration"
EXPORT = ROOT / "selahcue-pilot-registration.n8n.json"


def workflow():
    return json.loads(EXPORT.read_text())


def node(name):
    return next(value for value in workflow()["nodes"] if value["name"] == name)


def run_code(code, value, original=None):
    if not shutil.which("node"):
        pytest.fail("Node is required to verify the shipped n8n Code logic")
    program = """const fs=require('node:fs'); const data=JSON.parse(fs.readFileSync(0,'utf8'));
try { const result=new Function('$input','$',data.code)({first:()=>({json:data.value})},()=>({first:()=>({json:{payload:data.original}})}));
process.stdout.write(JSON.stringify({result})); } catch(error) {process.stdout.write(JSON.stringify({error:error.message}));}"""
    result = subprocess.run(["node", "-e", program], input=json.dumps({"code": code, "value": value, "original": original}),
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def form(**changes):
    value = {"registration_id": "67df125a-c17e-4a15-a5fe-6cfab08dba47", "platform": "Ubuntu",
             "Full name": "Test Operator", "Email": " TEST@example.invalid ", "Church name": "Test church",
             "Role at church": "Operator", "Church city": "Lagos", "Church country": "Nigeria"}
    value.update(changes)
    return value


def configured_code():
    return (ROOT / "validate-registration.js").read_text().replace("https://REPLACE_WITH_API_HOST.invalid", "https://sandbox.example.invalid").replace("REPLACE_WITH_APPROVED_NOTICE", "test-notice-v1")


def test_export_is_deterministic_inactive_and_contains_no_credentials():
    spec = importlib.util.spec_from_file_location("pilot_workflow_builder", ROOT / "build_workflow.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert workflow() == builder.build()
    assert workflow()["active"] is False
    assert workflow()["settings"]["saveDataSuccessExecution"] == "none"
    assert workflow()["settings"]["saveDataErrorExecution"] == "none"
    assert workflow()["settings"]["saveManualExecutions"] is False
    for value in workflow()["nodes"]:
        assert "credentials" not in value
        if value["type"].endswith("httpRequest"):
            assert value["onError"] == "continueErrorOutput"
            assert value["retryOnFail"] is False


def test_production_hidden_fields_and_supported_path_match_runtime_probe():
    trigger = node("Pilot registration")["parameters"]
    assert trigger["options"]["path"] == "selahcue-pilot-registration"
    assert "path" not in trigger
    hidden = [value for value in trigger["formFields"]["values"] if value["fieldType"] == "hiddenField"]
    assert {value["fieldName"] for value in hidden} == {"registration_id", "platform"}
    assert all(value["fieldValue"] == "" for value in hidden)


def test_boolean_if_uses_the_unary_descriptor_required_by_n8n_runtime():
    # Root reproduced an execution failure on n8n 2.45.7 without this flag:
    # the strict filter validates rightValue='' as boolean before routing.
    condition = node("Valid registration")["parameters"]["conditions"]["conditions"][0]
    assert condition["operator"] == {"type": "boolean", "operation": "true", "singleValue": True}
    binary = node("Already confirmed")["parameters"]["conditions"]["conditions"][0]
    assert binary["rightValue"] == "confirmed"
    assert binary["operator"] == {"type": "string", "operation": "equals"}


def test_validation_requires_stable_identity_and_explicit_deployment_configuration():
    result = run_code(node("Validate registration")["parameters"]["jsCode"], form())["result"][0]["json"]
    assert result["valid"] is False  # Shipped placeholders cannot collect.
    result = run_code(configured_code(), form())["result"][0]["json"]
    assert result["valid"] is True
    assert result["payload"]["email"] == "test@example.invalid"
    assert result["payload"]["registration_id"] == form()["registration_id"]
    for changes in ({"registration_id": ""}, {"registration_id": "pilot-execution-123"}, {"platform": ""},
                    {"Full name": "a" * 201}, {"Email": "private-secret"}):
        invalid = run_code(configured_code(), form(**changes))["result"][0]["json"]
        assert invalid["valid"] is False
        assert "private-secret" not in invalid["errors"]


def test_fixed_row_request_is_raw_put_not_an_append():
    write = node("Write fixed Sheet row")["parameters"]
    assert write["method"] == "PUT"
    assert "sheets.googleapis.com/v4/spreadsheets/" in write["url"]
    assert "valueInputOption=RAW" in write["url"]
    assert "append" not in write["url"]
    assert write["nodeCredentialType"] == "googleSheetsOAuth2Api"
    connections = workflow()["connections"]
    assert connections["Write fixed Sheet row"]["main"][0][0]["node"] == "Confirm acknowledged write"
    assert connections["Already confirmed"]["main"][0][0]["node"] == "Validate saved receipt"
    for name in ("Reserve registration", "Validate reserved row", "Write fixed Sheet row", "Confirm acknowledged write", "Validate saved receipt"):
        assert connections[name]["main"][1][0]["node"] == "Retry registration"


def test_invalid_reserved_row_or_receipt_never_reaches_success():
    original = {"registration_id": form()["registration_id"]}
    check = node("Validate reserved row")["parameters"]["jsCode"]
    assert "error" in run_code(check, {"state": "pending", "sheet_write": {}}, original)
    check = node("Validate saved receipt")["parameters"]["jsCode"]
    assert "error" in run_code(check, {"state": "confirmed", "receipt": "arbitrary"}, original)


@pytest.mark.django_db
def test_valid_max_length_literal_email_passes_workflow_row_boundary(pilot_policy):
    email = "=" + "a" * 243 + "@x.invalid"
    assert len(email) == 254
    data = payload(email=email)
    reserved = reserve_registration(data)
    assert len(reserved["sheet_write"]["values"][0][3]) == 255
    check = node("Validate reserved row")["parameters"]["jsCode"]
    result = run_code(check, reserved, data)
    assert "error" not in result
    assert result["result"][0]["json"]["sheet_write"] == reserved["sheet_write"]

