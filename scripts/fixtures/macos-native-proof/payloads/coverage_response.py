"""Offline validation and accounting for exact count and inference envelopes."""

import re
from dataclasses import dataclass, field, replace
from typing import Literal

from coverage_compile import CompiledDraft, compile_private
from coverage_contract import CoverageFailure, Diagnostic, validate_options
from coverage_index import SourceBlock, index_source
from coverage_json import encode_diagnostics, strict_json
from coverage_requests import (
    CACHE_OPTIONS, MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, MODEL, REASONING_EFFORT, SERVICE_TIER, STORE, TRUNCATION,
)


_COUNT_BYTES = 16_384
_INFERENCE_BYTES = 524_288
_INPUT_RATE = 20
_CACHE_READ_RATE = 1
_CACHE_WRITE_RATE = 25
_OUTPUT_RATE = 100
_COUNT_FAILURES = frozenset({
    "invalid_transport", "http_status", "byte_limit", "depth_limit", "invalid_json",
    "invalid_envelope", "token_limit", "internal_policy",
})
_COMPILE_TERMINALS = frozenset({
    "byte_limit", "depth_limit", "options_invalid", "source_invalid",
    "local_contract", "reference_invalid", "quote_invalid", "cannot_complete", "internal_policy",
})
_POLICY_ECHOES = (("store", STORE), ("max_output_tokens", MAX_OUTPUT_TOKENS), ("truncation", TRUNCATION))
_SECRET = re.compile(r"\b(?:Bearer\s+\S+|sk-(?:proj-|admin-)?[\w-]{12,}|(?:proj_|org-)[\w-]{12,})", re.I)


class CountFailure(Exception):
    """A bounded count failure that carries no provider body or parser excerpt."""

    def __init__(self, code: str):
        self._code = code if type(code) is str and code in _COUNT_FAILURES else "internal_policy"
        super().__init__(self._code)

    @property
    def code(self) -> str:
        return self._code

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"CountFailure({self.code!r})"


@dataclass(frozen=True)
class MeteredUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    cache_write_breakdown_observed: bool


@dataclass(frozen=True)
class ResponseObservations:
    reasoning_mode_observed: bool
    store_observed: bool
    max_output_tokens_observed: bool
    truncation_observed: bool
    tool_usage_observed: bool


@dataclass(frozen=True)
class ResponseAssessment:
    outcome: Literal["accepted", "repairable", "terminal"]
    reason: str
    cost_units: int | None
    retained_reservation_units: int
    usage: MeteredUsage | None
    observations: ResponseObservations | None
    diagnostics: tuple[Diagnostic, ...]
    compiled: CompiledDraft | None = field(repr=False)
    cannot_complete_reason: Literal["source_ambiguous", "representation_limit"] | None


def _read_envelope(status: int, body: bytes, limit: int) -> dict:
    if type(status) is not int or not 100 <= status <= 599 or type(body) is not bytes:
        raise CountFailure("invalid_transport")
    if len(body) > limit:
        raise CountFailure("byte_limit")
    if status != 200:
        raise CountFailure("http_status")
    try:
        value = strict_json(body, max_bytes=limit)
    except CoverageFailure as exc:
        code = exc.code
    else:
        if type(value) is not dict:
            raise CountFailure("invalid_envelope")
        return value
    raise CountFailure(code)


def parse_count(status: int, body: bytes) -> int:
    envelope = _read_envelope(status, body, _COUNT_BYTES)
    tokens = envelope.get("input_tokens")
    if envelope.get("object") != "response.input_tokens" or type(tokens) is not int or tokens < 0:
        raise CountFailure("invalid_envelope")
    if tokens > MAX_INPUT_TOKENS:
        raise CountFailure("token_limit")
    return tokens


def _validated_controller_inputs(
    counted_input: int, reserved_units: int, options: dict, blocks: tuple[SourceBlock, ...],
    forbidden_strings: tuple[str, ...],
) -> dict:
    if (type(counted_input) is not int or not 0 <= counted_input <= MAX_INPUT_TOKENS
            or type(reserved_units) is not int
            or reserved_units != counted_input * _CACHE_WRITE_RATE + MAX_OUTPUT_TOKENS * _OUTPUT_RATE):
        raise CoverageFailure("internal_policy")
    if type(forbidden_strings) is not tuple or any(type(value) is not str for value in forbidden_strings):
        raise CoverageFailure("internal_policy")
    if type(blocks) is not tuple or not 1 <= len(blocks) <= 512 or any(
        type(block) is not SourceBlock or type(block.id) is not str or type(block.text) is not str
        or not 1 <= len(block.text) <= 1600
        or any(type(offset) is not int for offset in (
            block.scalar_start, block.scalar_end, block.utf8_start, block.utf8_end,
        ))
        for block in blocks
    ):
        raise CoverageFailure("internal_policy")

    try:
        options = validate_options(options)
        canonical_blocks = index_source("".join(block.text for block in blocks))
    except CoverageFailure:
        pass
    else:
        if blocks == canonical_blocks:
            return options
    raise CoverageFailure("internal_policy")


def _effective_policy(result: dict) -> bool:
    if (result.get("object") != "response" or result.get("model") != MODEL
            or result.get("service_tier") != SERVICE_TIER):
        return False

    reasoning = result.get("reasoning")
    if (type(reasoning) is not dict or reasoning.get("effort") != REASONING_EFFORT
            or ("mode" in reasoning and reasoning["mode"] != "standard")):
        return False
    if (result.get("previous_response_id") is not None or result.get("conversation") is not None
            or result.get("tools") not in (None, []) or result.get("tool_choice") not in (None, "auto", "none")):
        return False

    cache = result.get("prompt_cache_options")
    if (type(cache) is not dict or cache.keys() - {"mode", "ttl", "prewarm", "comparison_response_id"}
            or any(cache.get(key) != expected for key, expected in CACHE_OPTIONS)
            or cache.get("prewarm", False) is not False or cache.get("comparison_response_id") is not None):
        return False
    return all(
        key not in result or (type(result[key]) is type(expected) and result[key] == expected)
        for key, expected in _POLICY_ECHOES
    )


def _exact_fields(value: object, required: set[str], optional=frozenset()) -> bool:
    return type(value) is dict and required <= value.keys() <= (required | optional)


def _in_range(count: object, limit: int) -> bool:
    return type(count) is int and 0 <= count <= limit


def _zero_fields(value: object, fields: set[str]) -> bool:
    return _exact_fields(value, fields) and all(_in_range(count, 0) for count in value.values())


def _no_tool_usage(result: dict) -> bool:
    if "tool_usage" not in result:
        return True
    usage = result["tool_usage"]
    if not _exact_fields(usage, {"image_gen", "web_search"}) or not _zero_fields(
        usage["web_search"], {"num_requests"}
    ):
        return False

    image = usage["image_gen"]
    totals = {"input_tokens", "output_tokens", "total_tokens"}
    breakdowns = {
        "input_tokens_details": {"image_tokens", "text_tokens"},
        "output_tokens_details": {"image_tokens", "text_tokens"},
        "cached_tokens_details": {"cached_image_tokens", "cached_text_tokens"},
    }
    if not _exact_fields(image, totals | {"input_tokens_details"},
                         {"cached_tokens", "output_tokens_details", "cached_tokens_details"}):
        return False
    return all(_zero_fields(value, breakdowns[key]) if key in breakdowns else _in_range(value, 0)
               for key, value in image.items())


def _has_visible_output(output: object) -> bool:
    if type(output) is not list:
        return False
    for item in output:
        if type(item) is not dict or item.get("type") != "message":
            continue
        parts = item.get("content")
        if type(parts) is list and any(
            type(part) is dict and part.get("type") == "output_text"
            and type(part.get("text")) is str and part["text"]
            for part in parts
        ):
            return True
    return False


def _meter_usage(usage: object, output: object) -> tuple[MeteredUsage | None, str]:
    if not _exact_fields(usage, {"input_tokens", "output_tokens", "total_tokens",
                                 "input_tokens_details", "output_tokens_details"}):
        return None, "usage_invalid"
    incoming, outgoing, total = (usage[key] for key in ("input_tokens", "output_tokens", "total_tokens"))
    if (not _in_range(incoming, MAX_INPUT_TOKENS) or not _in_range(outgoing, MAX_OUTPUT_TOKENS)
            or type(total) is not int or total != incoming + outgoing):
        return None, "usage_invalid"

    input_details = usage["input_tokens_details"]
    if not _exact_fields(input_details, {"cached_tokens", "cache_write_tokens"}, {"cache_write_tokens_details"}):
        return None, "usage_invalid"
    reads, writes = (input_details[key] for key in ("cached_tokens", "cache_write_tokens"))
    if not _in_range(reads, incoming) or not _in_range(writes, incoming - reads):
        return None, "usage_invalid"

    breakdown_observed = "cache_write_tokens_details" in input_details
    if writes or breakdown_observed:
        breakdown = input_details.get("cache_write_tokens_details")
        if not _exact_fields(breakdown, {"ttl_30m_tokens", "ttl_12h_tokens"}):
            return None, "usage_invalid"
        short_ttl, long_ttl = (breakdown[key] for key in ("ttl_30m_tokens", "ttl_12h_tokens"))
        if not _in_range(short_ttl, writes) or short_ttl != writes or not _in_range(long_ttl, 0):
            return None, "usage_invalid"

    output_details = usage["output_tokens_details"]
    if not _exact_fields(output_details, {"reasoning_tokens"}):
        return None, "usage_invalid"
    reasoning = output_details["reasoning_tokens"]
    if not _in_range(reasoning, outgoing):
        return None, "usage_invalid"
    if reasoning == outgoing and _has_visible_output(output):
        return None, "usage_visibility"

    return MeteredUsage(incoming, outgoing, total, reads, writes, reasoning, breakdown_observed), ""


def _cost(usage: MeteredUsage) -> int:
    uncached = usage.input_tokens - usage.cached_tokens - usage.cache_write_tokens
    return (uncached * _INPUT_RATE + usage.cached_tokens * _CACHE_READ_RATE
            + usage.cache_write_tokens * _CACHE_WRITE_RATE + usage.output_tokens * _OUTPUT_RATE)


def _output_text(output: object) -> str | None:
    if type(output) is not list or any(
        type(item) is not dict or item.get("type") not in ("message", "reasoning") for item in output
    ):
        return None
    messages = [item for item in output if item["type"] == "message"]
    if len(messages) != 1:
        return None
    message = messages[0]
    if message.get("role") != "assistant" or message.get("status") != "completed":
        return None
    content = message.get("content")
    if type(content) is not list or len(content) != 1 or type(content[0]) is not dict:
        return None
    part = content[0]
    if part.get("type") != "output_text" or type(part.get("text")) is not str:
        return None
    return part["text"]


def _contains_secret(value: object, forbidden: tuple[str, ...]) -> bool:
    if type(value) is str:
        return bool(_SECRET.search(value) or any(part and part in value for part in forbidden))
    if type(value) is list:
        return any(_contains_secret(item, forbidden) for item in value)
    if type(value) is dict:
        return any(_contains_secret(key, forbidden) or _contains_secret(item, forbidden)
                   for key, item in value.items())
    return False


def _propose_repair(
    result: ResponseAssessment, reason: str, diagnostics: tuple[Diagnostic, ...],
) -> ResponseAssessment:
    try:
        if encode_diagnostics(diagnostics) != b"[]":
            return replace(result, outcome="repairable", reason=reason, diagnostics=diagnostics)
    except CoverageFailure:
        pass
    return replace(result, reason="internal_policy")


def _assess_private(
    result: ResponseAssessment, text: str, options: dict, blocks: tuple[SourceBlock, ...],
    forbidden: tuple[str, ...],
) -> ResponseAssessment:
    if _contains_secret(text, forbidden):
        return replace(result, reason="secret_material")
    try:
        private = strict_json(text.encode("utf-8"), max_bytes=_INFERENCE_BYTES)
    except CoverageFailure as exc:
        if exc.code == "invalid_json":
            return _propose_repair(result, "private_json", exc.diagnostics)
        return replace(result, reason=exc.code if exc.code in _COMPILE_TERMINALS else "internal_policy")

    if _contains_secret(private, forbidden):
        return replace(result, reason="secret_material")
    try:
        compiled = compile_private(private, blocks, options)
    except CoverageFailure as exc:
        if exc.code == "invalid_schema":
            return _propose_repair(result, "private_schema", exc.diagnostics)
        reason = exc.code if exc.code in _COMPILE_TERMINALS else "internal_policy"
        return replace(result, reason=reason, cannot_complete_reason=exc.failure_code)
    return replace(result, outcome="accepted", reason="accepted", compiled=compiled)


def assess_response(
    status: int, body: bytes, *, counted_input: int, reserved_units: int, options: dict,
    blocks: tuple[SourceBlock, ...], forbidden_strings: tuple[str, ...],
) -> ResponseAssessment:
    options = _validated_controller_inputs(counted_input, reserved_units, options, blocks, forbidden_strings)
    assessment = ResponseAssessment("terminal", "internal_policy", None, reserved_units, None, None, (), None, None)
    try:
        result = _read_envelope(status, body, _INFERENCE_BYTES)
    except CountFailure as exc:
        reason = {"invalid_json": "outer_json", "invalid_envelope": "outer_envelope"}.get(exc.code, exc.code)
        return replace(assessment, reason=reason)
    if not _effective_policy(result):
        return replace(assessment, reason="effective_policy")
    if not _no_tool_usage(result):
        return replace(assessment, reason="tool_usage")

    observations = ResponseObservations(
        reasoning_mode_observed="mode" in result["reasoning"],
        store_observed="store" in result,
        max_output_tokens_observed="max_output_tokens" in result,
        truncation_observed="truncation" in result,
        tool_usage_observed="tool_usage" in result,
    )
    assessment = replace(assessment, observations=observations)
    output = result.get("output")
    usage, failure = _meter_usage(result.get("usage"), output)
    if usage is None:
        return replace(assessment, reason=failure)
    cost = _cost(usage)
    metered = replace(assessment, usage=usage, cost_units=cost, retained_reservation_units=0)
    if usage.input_tokens != counted_input:
        return replace(metered, reason="count_mismatch")
    if cost > reserved_units:
        return replace(metered, reason="cost_exceeds_reservation")
    if (result.get("status") != "completed" or result.get("error") is not None
            or result.get("incomplete_details") is not None):
        return replace(metered, reason="response_state")
    text = _output_text(output)
    if text is None:
        return replace(metered, reason="output_envelope")
    return _assess_private(metered, text, options, blocks, forbidden_strings)
