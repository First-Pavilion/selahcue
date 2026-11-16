"""Bounded, test-local receipts for the routed Home anchor assertion."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from importlib import metadata
from pathlib import Path


ASSERTION_MESSAGE = "the navbar's How it works, clicked on /pricing, lands on the section clear of the bar"
HELPER_PATH = Path(__file__).with_suffix(".js")
MAX_RECEIPT_BYTES = 24 * 1024
ENGINES = ("chromium", "webkit")
OUTCOMES = ("pass", "fail", "not_reached")
REASONS = (
    "install_failed", "controller_missing", "wrapper_replaced", "lookup_limit", "command_limit", "route_limit",
    "scroll_limit", "mutation_limit", "counter_saturated", "projection_unavailable", "sample_incomplete",
    "cleanup_incomplete", "action_exception", "export_limit",
)
COUNT_FIELDS = (
    "target_lookups", "lookup_dropped", "scroll_commands", "command_dropped", "route_observations", "route_dropped",
    "scroll_callbacks", "mutation_callbacks", "anchor_clicks", "visibility_changes", "pagehides",
)
STAGE_FIELDS = ("armed", "clicked", "url_matched", "waited", "measured", "asserted")

# Only these keys and scalar types can cross the page-to-stdout boundary.
ROUTE = {
    "path": ("pricing", "home_anchor", "other"),
    "hash": ("none", "how_it_works", "other"),
    "observed_ms": float,
    "source": ("arm", "click", "lookup", "command", "scroll", "hashchange", "popstate",
               "visibilitychange", "pagehide", "mutation", "finish"),
}
VISIBILITY = ("visible", "hidden", "prerender")
SNAPSHOT = {
    "path": ROUTE["path"], "hash": ROUTE["hash"], "visibility": VISIBILITY, "font_status": ("loaded", "loading"),
    "reduced_motion": bool, "inner_width": float, "client_width": float, "client_height": float,
    "scroll_y": float, "target_present": bool,
}
TIMING = {"entry_ms": float, "return_ms": float, "outcome": ("returned", "threw")}
LOOKUP = {**TIMING, "present": bool}
COMMAND = {
    **TIMING, "overload": ("numeric", "options", "other"), "top": float, "left": float,
    "behavior": ("auto", "instant", "smooth", "other", "absent"), "argument_count": (*range(17), "many"),
    "projection_quality": ("numeric", "post_call_own_data", "projection_error", "unsupported"),
}
SCROLL = {key: float for key in ("first_ms", "latest_ms", "first_y", "latest_y", "min_y", "max_y")}
LIFECYCLE = {
    "visibility": VISIBILITY, "visibility_ms": float, "pagehide_persisted": bool, "pagehide_ms": float,
}
GEOMETRY = {
    "document_target_top": float, "navbar_bottom": float, "anchor_gap": float,
    "document_target_top_basis": ("sequential_target_top_and_scroll_y",),
}


def _match(value, pattern, maximum):
    if type(value) is str and len(value) <= maximum and re.fullmatch(pattern, value):
        return value
    return None


def _enum(value, permitted):
    if type(value) in (str, int) and value in permitted:
        return value
    return None


def _dict(value):
    return value if type(value) is dict else {}


def _provenance(value):
    data = _dict(value)
    return {
        "engine": _enum(data.get("engine"), ENGINES),
        "github_context_sha": _match(data.get("github_context_sha"), r"[0-9a-fA-F]{40}", 40),
        "github_run_id": _match(data.get("github_run_id"), r"[0-9]{1,20}", 20),
        "github_run_attempt": _match(data.get("github_run_attempt"), r"[0-9]{1,20}", 20),
        "browser_version": _match(data.get("browser_version"), r"[0-9]+(?:\.[0-9]+)*", 64),
        "playwright_version": _match(data.get("playwright_version"), r"[0-9]+(?:\.[0-9]+)*", 64),
        "helper_sha256": _match(data.get("helper_sha256"), r"[0-9a-f]{64}", 64),
        "harness_sha256": _match(data.get("harness_sha256"), r"[0-9a-f]{64}", 64),
    }


def _optional(probe):
    try:
        return probe()
    except Exception:
        return None


def build_home_anchor_provenance(
    *, engine: str, browser_version: str, environ, harness_path: Path, helper_path: Path,
) -> dict:
    return _provenance({
        "engine": engine,
        "github_context_sha": _optional(lambda: environ.get("GITHUB_SHA")),
        "github_run_id": _optional(lambda: environ.get("GITHUB_RUN_ID")),
        "github_run_attempt": _optional(lambda: environ.get("GITHUB_RUN_ATTEMPT")),
        "browser_version": browser_version,
        "playwright_version": _optional(lambda: metadata.version("playwright")),
        "helper_sha256": _optional(lambda: hashlib.sha256(helper_path.read_bytes()).hexdigest()),
        "harness_sha256": _optional(lambda: hashlib.sha256(harness_path.read_bytes()).hexdigest()),
    })


def _reason_set(raw):
    if type(raw) not in (list, tuple):
        return set()
    return {value for value in raw[:len(REASONS)] if _enum(value, REASONS) is not None}


def _ordered_reasons(reasons):
    return [reason for reason in REASONS if reason in reasons]


def _scalar(raw, kind, reasons):
    if raw is None:
        return None
    if kind is float:
        if type(raw) in (int, float) and -1_000_000_000 <= raw <= 1_000_000_000 and math.isfinite(raw):
            return raw
        reasons.add("sample_incomplete")
    elif kind is int:
        if type(raw) is int and 0 <= raw <= 1_000_000:
            return raw
        reasons.add("projection_unavailable")
    elif kind is bool:
        if type(raw) is bool:
            return raw
        reasons.add("projection_unavailable")
    else:
        value = _enum(raw, kind)
        if value is not None:
            return value
        reasons.add("projection_unavailable")
    return None


def _record(raw, schema, reasons):
    if raw is None:
        return None
    if type(raw) is not dict:
        reasons.add("projection_unavailable")
        return None
    return {key: _scalar(raw.get(key), kind, reasons) for key, kind in schema.items()}


def _records(raw, schema, reasons, limit_reason):
    if raw is None:
        return []
    if type(raw) is not list:
        reasons.add("projection_unavailable")
        return []
    if len(raw) > 16:
        reasons.add(limit_reason)
    return [_record(entry, schema, reasons) for entry in raw[:16]]


def _counts(raw, reasons):
    return _record(raw, dict.fromkeys(COUNT_FIELDS, int), reasons)


def _cleanup(raw, reasons):
    if raw is None:
        return None
    raw = _dict(raw)
    problems = _reason_set(raw.get("reasons"))
    complete = raw.get("complete") is True and not problems
    if not complete and not problems:
        problems.add("cleanup_incomplete")
    reasons.update(problems)
    return {"complete": complete, "reasons": _ordered_reasons(problems)}


def _capture(raw, reasons):
    if raw is None:
        return None
    raw = _dict(raw)
    problems = _reason_set(raw.get("reasons"))
    result = {
        "counts": _counts(raw.get("counts"), problems),
        "lookups": _records(raw.get("lookups"), LOOKUP, problems, "lookup_limit"),
        "commands": _records(raw.get("commands"), COMMAND, problems, "command_limit"),
        "routes": _records(raw.get("routes"), ROUTE, problems, "route_limit"),
        "latest_route_observed_ms": _scalar(raw.get("latest_route_observed_ms"), float, problems),
        "first_presence_ms": _scalar(raw.get("first_presence_ms"), float, problems),
        "first_presence_source": _scalar(raw.get("first_presence_source"), ("arm", "lookup", "mutation", "finish"), problems),
        "click": _record(raw.get("click"), {"observed_ms": float, "is_trusted": bool}, problems),
        "scroll": _record(raw.get("scroll"), SCROLL, problems),
        "lifecycle": _record(raw.get("lifecycle"), LIFECYCLE, problems),
        "snapshot": _record(raw.get("snapshot"), SNAPSHOT, problems),
        "geometry": _record(raw.get("geometry"), GEOMETRY, problems),
        "cleanup": _cleanup(raw.get("cleanup"), problems),
    }
    if raw.get("complete") is not True and not problems:
        problems.add("sample_incomplete")
    reasons.update(problems)
    return {**result, "complete": not problems, "reasons": _ordered_reasons(problems)}


def _project_receipt(raw):
    raw = _dict(raw)
    reasons = _reason_set(raw.get("reasons"))
    identity = {
        "schema_version": 1,
        "marker": "home_anchor_capture",
        "phase": _enum(raw.get("phase"), ("start", "terminal")),
        "engine": _enum(raw.get("engine"), ENGINES),
        "action_id": _match(raw.get("action_id"), r"[0-9a-f]{32}", 32),
        "outcome": _enum(raw.get("outcome"), OUTCOMES),
    }
    provenance = _provenance(raw.get("provenance"))
    if identity["phase"] == "start":
        return {**identity, "provenance": provenance}, identity

    result = {
        **identity, "provenance": provenance,
        "start_emitted": _scalar(raw.get("start_emitted"), bool, reasons),
        "same_controller": _scalar(raw.get("same_controller"), bool, reasons),
        "target_top": _scalar(raw.get("target_top"), float, reasons),
        "stages": _record(raw.get("stages"), dict.fromkeys(STAGE_FIELDS, bool), reasons),
        "arm": _record(raw.get("arm"), SNAPSHOT, reasons),
        "capture": _capture(raw.get("capture"), reasons),
        "cleanup": _cleanup(raw.get("cleanup"), reasons),
        "counts": _counts(raw.get("counts"), reasons),
    }
    return {**result, "complete": raw.get("complete") is True and not reasons,
            "reasons": _ordered_reasons(reasons)}, identity


def emit_home_anchor_receipt(receipt: dict, sink) -> bool:
    def encode(value):
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n"

    try:
        projected, identity = _project_receipt(receipt)
        line = encode(projected)
        if len(line.encode("ascii")) > MAX_RECEIPT_BYTES:
            reasons = _reason_set(projected.get("reasons"))
            reasons.add("export_limit")
            line = encode({**identity, "counts": projected.get("counts"), "complete": False,
                           "reasons": _ordered_reasons(reasons)})
        if len(line.encode("ascii")) > MAX_RECEIPT_BYTES:
            return False
        result = sink.write(line)
        if result is not None and result != len(line):
            return False
        sink.flush()
        return True
    except Exception:
        return False


# Read the controller's own data descriptors without invoking a replacement's getters.
_CONTROLLER_JS = """
  const own = (object, key) => Object.getOwnPropertyDescriptor(object, key)?.value;
  const controller = (() => {
    try {
      const candidate = own(window, '__scHomeAnchorCapture');
      if (candidate && Object.isFrozen(candidate) && own(candidate, 'actionId') === actionId &&
          typeof own(candidate, 'finish') === 'function' && typeof own(candidate, 'dispose') === 'function') {
        return candidate;
      }
    } catch {}
    return null;
  })();
"""
_DISPOSE_JS = "(actionId) => {" + _CONTROLLER_JS + "return controller ? controller.dispose() : null; }"


def _finish_js(target_top_js):
    # target_top_js is the existing checked-in measurement expression. The token is a separate evaluate argument.
    return "(actionId) => {" + _CONTROLLER_JS + f"""
      const measure = () => ({target_top_js})('how-it-works');
      if (!controller) return {{top: measure(), same_controller: false, capture: null}};
      return {{...controller.finish(measure), same_controller: true}};
    }}
    """


def _try_dispose(page, action_id):
    return _optional(lambda: page.evaluate(_DISPOSE_JS, action_id))


def _arm(page, action_id):
    if action_id is None:
        return {}
    source = _optional(lambda: HELPER_PATH.read_text(encoding="utf-8"))
    if source is None:
        return {}
    try:
        return _dict(page.evaluate(source, {"actionId": action_id}))
    except Exception:
        return {"cleanup": _try_dispose(page, action_id)}


def run_pricing_anchor_check(page, run, *, engine: str, target_top_js: str, provenance: dict, sink) -> None:
    finish_source = _finish_js(target_top_js)
    action_id = _optional(lambda: uuid.uuid4().hex)
    receipt = {"engine": engine, "action_id": action_id, "provenance": provenance, "outcome": "not_reached"}
    receipt["start_emitted"] = emit_home_anchor_receipt({**receipt, "phase": "start"}, sink)

    stages = dict.fromkeys(STAGE_FIELDS, False)
    reasons = set()
    armed = False
    try:
        arm = _arm(page, action_id)
        armed = action_id is not None and arm.get("installed") is True and arm.get("actionId") == action_id
        stages["armed"] = armed
        receipt["arm"] = arm.get("snapshot")
        receipt["cleanup"] = arm.get("cleanup")
        reasons.update(_reason_set(arm.get("reasons")))
        if not armed:
            reasons.add("install_failed")

        page.get_by_role("link", name="How it works").first.click()
        stages["clicked"] = True
        page.wait_for_url("**/#how-it-works")
        stages["url_matched"] = True
        page.wait_for_timeout(1200)
        stages["waited"] = True
        if armed:
            result = _dict(page.evaluate(finish_source, action_id))
            top = result.get("top")
            same_controller = result.get("same_controller") is True
            receipt["same_controller"] = same_controller
            capture = _dict(result.get("capture"))
            if not same_controller:
                reasons.update(("controller_missing", "cleanup_incomplete"))
            elif capture.get("complete") is not True and not capture.get("reasons"):
                reasons.add("sample_incomplete")
            receipt["capture"] = capture or None
            receipt["counts"] = capture.get("counts")
            receipt["cleanup"] = capture.get("cleanup")
        else:
            top = page.evaluate(target_top_js, "how-it-works")
        stages["measured"] = True
        receipt["target_top"] = top
        previous_failures = len(run.failures)
        run.near(top, 95, 2, ASSERTION_MESSAGE)
        stages["asserted"] = True
        receipt["outcome"] = "pass" if len(run.failures) == previous_failures else "fail"
    except BaseException:
        reasons.add("action_exception")
        if armed and not stages["measured"]:
            receipt["cleanup"] = _try_dispose(page, action_id)
            if receipt["cleanup"] is None:
                reasons.add("cleanup_incomplete")
        raise
    finally:
        emit_home_anchor_receipt({
            **receipt, "phase": "terminal", "stages": stages, "reasons": _ordered_reasons(reasons),
            "complete": bool(armed and receipt["start_emitted"] and stages["asserted"] and not reasons),
        }, sink)
