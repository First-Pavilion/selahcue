"""Depth-bounded JSON decoding and deterministic structural feedback."""

import json
import math
import re

from coverage_contract import CoverageFailure, Diagnostic, has_lone_surrogate, is_safe_diagnostic


_MAX_DEPTH = 12
_MAX_DIAGNOSTICS = 20
_MAX_FEEDBACK_BYTES = 2048
_TYPES = {"object": dict, "array": list, "string": str, "integer": int}
_PROPERTY_NAME = re.compile(r"[a-z_]+")
_CLOSERS = {"}": "{", "]": "["}


class _InvalidJSON(ValueError):
    pass


def _preparse(text: str) -> None:
    stack = []
    in_string = escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "{[":
            if len(stack) == _MAX_DEPTH:
                raise CoverageFailure("depth_limit")
            stack.append(char)
        elif char in _CLOSERS:
            if not stack or stack.pop() != _CLOSERS[char]:
                raise _InvalidJSON
    if stack or in_string:
        raise _InvalidJSON


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value or has_lone_surrogate(key):
            raise _InvalidJSON
        value[key] = item
    return value


def _nonfinite(_literal: str) -> None:
    raise _InvalidJSON


def _finite_float(literal: str) -> float:
    value = float(literal)
    if not math.isfinite(value):
        raise _InvalidJSON
    return value


def _integer(literal: str) -> int:
    # Python's process-wide decimal conversion limit must not turn a valid oversized
    # integer into an eligible JSON repair. Bound input first, then combine short chunks.
    if len(literal) <= 640:
        return int(literal)
    negative = literal.startswith("-")
    digits = literal[1:] if negative else literal
    powers = {}

    def parse(start: int, end: int) -> int:
        length = end - start
        if length <= 640:
            return int(digits[start:end])
        right = length // 2
        if right not in powers:
            powers[right] = 10 ** right
        midpoint = end - right
        return parse(start, midpoint) * powers[right] + parse(midpoint, end)

    number = parse(0, len(digits))
    return -number if negative else number


def _check_string_values(value: object) -> None:
    if type(value) is str and has_lone_surrogate(value):
        raise _InvalidJSON
    if type(value) is dict:
        for item in value.values():
            _check_string_values(item)
    if type(value) is list:
        for item in value:
            _check_string_values(item)


def strict_json(raw: bytes, *, max_bytes: int) -> object:
    if type(raw) is not bytes or type(max_bytes) is not int or max_bytes < 0:
        raise CoverageFailure("internal_policy")
    if len(raw) > max_bytes:
        raise CoverageFailure("byte_limit")
    try:
        text = raw.decode("utf-8")
        if text.startswith("\ufeff"):
            raise _InvalidJSON
        _preparse(text)
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_nonfinite,
                           parse_float=_finite_float, parse_int=_integer)
        _check_string_values(value)
    except ValueError:
        pass
    else:
        return value
    # Raise outside the parse exception handler so the parser's excerpt is not retained.
    raise CoverageFailure("invalid_json", (Diagnostic("$", "invalid_json"),))


def _check_schema(schema: object, depth: int = 0) -> None:
    if depth > _MAX_DEPTH or type(schema) is not dict or type(schema.get("type")) is not str:
        raise CoverageFailure("internal_policy")
    kind = schema["type"]
    fields = tuple(schema)
    if kind == "object" and fields == ("type", "properties", "required", "additionalProperties"):
        properties = schema["properties"]
        if (type(properties) is not dict or type(schema["required"]) is not list
                or list(properties) != schema["required"] or schema["additionalProperties"] is not False):
            raise CoverageFailure("internal_policy")
        for field, child in properties.items():
            if type(field) is not str or _PROPERTY_NAME.fullmatch(field) is None:
                raise CoverageFailure("internal_policy")
            _check_schema(child, depth + 1)
    elif kind == "array" and fields == ("type", "items"):
        _check_schema(schema["items"], depth + 1)
    elif kind in ("integer", "string") and fields == ("type",):
        return
    elif kind == "string" and fields == ("type", "enum"):
        choices = schema["enum"]
        if (type(choices) is not list or not choices
                or any(type(item) is not str or has_lone_surrogate(item) for item in choices)
                or len(choices) != len(set(choices))):
            raise CoverageFailure("internal_policy")
    else:
        raise CoverageFailure("internal_policy")


def _diagnose(value: object, schema: dict, path: str):
    kind = schema["type"]
    if type(value) is not _TYPES[kind]:
        yield Diagnostic(path, "wrong_type")
        return
    if "enum" in schema and value not in schema["enum"]:
        yield Diagnostic(path, "invalid_enum")
        return
    if kind == "object":
        properties = schema["properties"]
        for field in properties:
            if field not in value:
                yield Diagnostic(f"{path}.{field}", "missing_required")
        if any(field not in properties for field in value):
            yield Diagnostic(path, "additional_property")
        for field, child in properties.items():
            if field in value:
                yield from _diagnose(value[field], child, f"{path}.{field}")
    elif kind == "array":
        for index, item in enumerate(value):
            yield from _diagnose(item, schema["items"], f"{path}[{index}]")


def _encoded_prefix(entries):
    size = 2  # Opening and closing array brackets.
    for index, entry in enumerate(entries):
        if index == _MAX_DIAGNOSTICS:
            break
        encoded = json.dumps({"path": entry.path, "code": entry.code}, ensure_ascii=True,
                             separators=(",", ":")).encode("ascii")
        size += len(encoded) + bool(index)
        if size > _MAX_FEEDBACK_BYTES:
            break
        yield entry, encoded


def schema_diagnostics(value: object, schema: dict) -> tuple[Diagnostic, ...]:
    _check_schema(schema)
    return tuple(entry for entry, _ in _encoded_prefix(_diagnose(value, schema, "$")))


def encode_diagnostics(entries: tuple[Diagnostic, ...]) -> bytes:
    if type(entries) is not tuple or not all(is_safe_diagnostic(entry) for entry in entries):
        raise CoverageFailure("internal_policy")
    if len(entries) != 1 and any(entry.code == "invalid_json" for entry in entries):
        raise CoverageFailure("internal_policy")
    return b"[" + b",".join(encoded for _, encoded in _encoded_prefix(entries)) + b"]"
