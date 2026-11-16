"""Reproduce the inactive n8n export; no network calls or live credentials."""

import json
from pathlib import Path
from html import escape


ROOT = Path(__file__).resolve().parent


def node(name, kind, version, x, y, parameters, **extra):
    return {"id": name.lower().replace(" ", "-"), "name": name,
            "type": "n8n-nodes-base." + kind, "typeVersion": version,
            "position": [x, y], "parameters": parameters, **extra}


def request(name, x, y, url, body, *, google=False):
    auth = ({"authentication": "predefinedCredentialType", "nodeCredentialType": "googleSheetsOAuth2Api"}
            if google else {"authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth"})
    return node(name, "httpRequest", 4.2, x, y, {
        "method": "PUT" if google else "POST", "url": url, **auth,
        "sendBody": True, "specifyBody": "json", "jsonBody": body,
        "options": {"timeout": 10000, "response": {"response": {"responseFormat": "json"}}},
    }, onError="continueErrorOutput", retryOnFail=False)


def condition(name, x, y, field, kind="boolean", operation="true", value=""):
    operator = {"type": kind, "operation": operation}
    # n8n 2.45.7 strict If validation otherwise tries to validate the empty
    # rightValue as a boolean, even though this operator is unary.
    if kind == "boolean" and operation == "true":
        operator["singleValue"] = True
    return node(name, "if", 2.2, x, y, {"conditions": {
        "options": {"caseSensitive": True, "typeValidation": "strict", "version": 2},
        "conditions": [{"id": name, "leftValue": "={{ $json." + field + " }}",
                        "rightValue": value, "operator": operator}],
        "combinator": "and"}, "options": {}})


def completion(name, x, y, title, message):
    return node(name, "form", 1, x, y, {"operation": "completion", "respondWith": "text",
        "completionTitle": title, "completionMessage": message, "options": {}})


def build():
    notice = json.loads((ROOT / "notice.json").read_text())
    notice_description = "<p><strong>" + escape(notice["title"]) + "</strong> (" + escape(notice["version"]) + ")</p>"
    for section in notice["sections"]:
        notice_description += "<p><strong>" + escape(section["title"]) + "</strong></p>"
        notice_description += "".join("<p>" + escape(paragraph) + "</p>" for paragraph in section["paragraphs"])
    fields = [{"fieldLabel": "registration_id", "fieldName": "registration_id",
               "fieldType": "hiddenField", "fieldValue": ""},
              # Keep label and output name identical for the pinned 2.2 query
              # prefill contract. The user sees and confirms the selected OS.
              {"fieldLabel": "platform", "fieldName": "platform", "fieldType": "dropdown",
               "requiredField": True, "fieldOptions": {"values": [
                   {"option": value} for value in ("Windows", "Ubuntu", "macOS")]}}]
    fields += [{"fieldLabel": label, "fieldType": "email" if label == "Email" else "text",
                "requiredField": label != "Phone (optional)"}
               for label in ("Full name", "Email", "Phone (optional)", "Church name", "Role at church", "Church city", "Church country")]
    nodes = [node("Pilot registration", "formTrigger", 2.2, 0, 0, {
        "authentication": "none", "formTitle": "SelahCue field-test registration",
        "formDescription": notice_description,
        "formFields": {"values": fields}, "responseMode": "lastNode",
        "options": {"path": "selahcue-pilot-registration", "buttonLabel": "Register for the pilot", "ignoreBots": True},
    }, webhookId="a3a78a22-b62e-439a-a19a-d9eccb9db960"),
    node("Validate registration", "code", 2, 240, 0, {"jsCode": (ROOT / "validate-registration.js").read_text()}),
    condition("Valid registration", 460, 0, "valid"),
    request("Reserve registration", 680, 0,
            "={{ $json.api_origin + '/v1/pilot/registrations:reserve' }}", "={{ JSON.stringify($json.payload) }}"),
    condition("Already confirmed", 900, 0, "state", "string", "equals", "confirmed"),
    node("Validate reserved row", "code", 2, 1120, 100, {"jsCode": """const value = $input.first().json;
const original = $('Validate registration').first().json.payload;
const write = value.sheet_write;
// The literal-cell apostrophe may add one character to a valid field. Keep
// serializer bounds (especially a 254-character email -> 255), not a global cap.
const cellLimits = [36, 40, 201, 255, 51, 201, 201, 201, 201, 20, 40, 80, 1];
const match = write && typeof write.range === 'string' && write.range.match(/^'[A-Za-z][A-Za-z0-9_ -]{0,79}'!A([0-9]+):M([0-9]+)$/);
if (value.schema_version !== 1 || value.registration_id !== original.registration_id || value.state !== 'pending' ||
    !write || !/^[A-Za-z0-9_-]{1,200}$/.test(write.spreadsheet_id) || !match || match[1] !== match[2] ||
    Number(match[1]) < 2 || Number(match[1]) > 100000 || write.valueInputOption !== 'RAW' ||
    write.majorDimension !== 'ROWS' || !Array.isArray(write.values) || write.values.length !== 1 ||
    !Array.isArray(write.values[0]) || write.values[0].length !== 13 ||
    write.values[0].some((v, i) => typeof v !== 'string' || v.length > cellLimits[i]) ||
    write.values[0][0] !== original.registration_id || write.values[0][9] !== original.platform)
  throw new Error('The reserved registration row was not valid. No write was performed.');
return [{json:value}];"""}, onError="continueErrorOutput"),
    request("Write fixed Sheet row", 1340, 100,
            "={{ 'https://sheets.googleapis.com/v4/spreadsheets/' + encodeURIComponent($json.sheet_write.spreadsheet_id) + '/values/' + encodeURIComponent($json.sheet_write.range) + '?valueInputOption=RAW' }}",
            "={{ JSON.stringify({range:$json.sheet_write.range,majorDimension:'ROWS',values:$json.sheet_write.values}) }}", google=True),
    request("Confirm acknowledged write", 1560, 100,
            "={{ $('Validate registration').first().json.api_origin + '/v1/pilot/registrations:confirm' }}",
            "={{ JSON.stringify({registration_id:$('Reserve registration').first().json.registration_id,sheet_ack:{spreadsheetId:$json.spreadsheetId,updatedRange:$json.updatedRange,updatedRows:$json.updatedRows,updatedColumns:$json.updatedColumns,updatedCells:$json.updatedCells}}) }}"),
    node("Validate saved receipt", "code", 2, 1780, -100, {"jsCode": """const result = $input.first().json;
const original = $('Validate registration').first().json.payload;
const now = Date.now() / 1000;
if (result.schema_version !== 1 || result.state !== 'confirmed' || result.registration_id !== original.registration_id ||
    typeof result.receipt !== 'string' || !result.receipt.length || result.receipt.length > 2048 ||
    !Number.isSafeInteger(result.expires_at) || result.expires_at <= now || result.expires_at > now + 3600)
  throw new Error('Registration was not confirmed. No download is authorized.');
return [{json:result}];"""}, onError="continueErrorOutput"),
    completion("Registration saved", 2000, -100, "Registration saved",
               "Your pilot registration has been recorded. Download delivery is not connected in this inactive handoff; complete the separate private download-grant integration before publishing."),
    completion("Correct registration", 700, 450, "Check your registration",
               "={{ $('Validate registration').first().json.errors }}"),
    completion("Retry registration", 1780, 450, "Registration needs a retry",
               "Registration or download confirmation could not complete. Return through the same marketing download choice to retry the same attempt. A failed/ambiguous Sheet write does not authorize a download and retries reuse the reserved row."),
    node("Setup required", "stickyNote", 1, 0, -340, {"content": "## INACTIVE — do not publish until configured\nSee README.md. Configure approved notice/API origin and select server Header Auth + scoped Google Sheets OAuth credentials. Dedicated protected A:M tab; no inserts/sorts/deletes. Stable UUIDv4 comes from marketing production form query, never execution ID. Fixed RAW update, never append. P12 download grant is a separate unconnected step.", "width": 800, "height": 240}),
    ]
    connections = {}

    def wire(source, output, target):
        outputs = connections.setdefault(source, {"main": []})["main"]
        while len(outputs) <= output:
            outputs.append([])
        outputs[output].append({"node": target, "type": "main", "index": 0})

    for source, target in [("Pilot registration", "Validate registration"), ("Validate registration", "Valid registration"),
                           ("Valid registration", "Reserve registration"), ("Reserve registration", "Already confirmed"),
                           ("Already confirmed", "Validate saved receipt"), ("Validate reserved row", "Write fixed Sheet row"),
                           ("Write fixed Sheet row", "Confirm acknowledged write"), ("Confirm acknowledged write", "Validate saved receipt"),
                           ("Validate saved receipt", "Registration saved")]:
        wire(source, 0, target)
    wire("Valid registration", 1, "Correct registration")
    wire("Already confirmed", 1, "Validate reserved row")
    for source in ("Reserve registration", "Validate reserved row", "Write fixed Sheet row", "Confirm acknowledged write", "Validate saved receipt"):
        wire(source, 1, "Retry registration")
    return {"name": "SelahCue pilot registration — fixed-row durable handoff (inactive)",
            "nodes": nodes, "connections": connections, "active": False, "pinData": {},
            "settings": {"executionOrder": "v1", "timezone": "UTC", "saveDataSuccessExecution": "none",
                         "saveDataErrorExecution": "none", "saveManualExecutions": False}, "tags": []}


if __name__ == "__main__":
    (ROOT / "selahcue-pilot-registration.n8n.json").write_text(json.dumps(build(), indent=2) + "\n")
