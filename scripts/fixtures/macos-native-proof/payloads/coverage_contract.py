"""Frozen wire descriptors and safe metadata for the offline CoverageDraft candidate."""

from dataclasses import dataclass
import re


_TEMPLATES = ("full_outline_scriptures", "full_outline", "summary", "devotional")
_OPTION_KEYS = ("template", "preferred_translation", "include")
_FLAGS = (
    "prayer_points", "scripture_extraction", "social_excerpts", "chapter_markers",
    "notable_quotations", "short_summary", "podcast_show_notes", "short_description",
)
# The native FLAT_SECTIONS order, with introduction appended separately by draft_schema.
_FLAT_SECTIONS = (
    ("illustrations", None), ("quotes", "notable_quotations"), ("prayer_points", "prayer_points"),
    ("calls_to_action", None), ("key_lessons", None), ("chapter_markers", "chapter_markers"),
    ("social_excerpts", "social_excerpts"), ("podcast_show_notes", "podcast_show_notes"),
    ("short_description", "short_description"),
)

EXCLUDED_REASONS = (
    "repetition", "optional_detail", "transition", "unclear_nonessential", "template_compression",
)
_CANNOT_COMPLETE_REASONS = ("source_ambiguous", "representation_limit")
_FAILURE_CODES = (
    "options_invalid", "source_invalid", "byte_limit", "depth_limit", "invalid_json", "invalid_schema",
    "local_contract", "reference_invalid", "quote_invalid", "cannot_complete", "internal_policy",
)
_SCHEMA_ERROR_CODES = ("missing_required", "additional_property", "wrong_type", "invalid_enum")
_WHITESPACE = frozenset(
    "\u0009\u000a\u000b\u000c\u000d\u0020\u0085\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)
_SURROGATE = re.compile(r"[\ud800-\udfff]")
_PATH_STEP = re.compile(r"\.([a-z_]+)|\[(?:0|[1-9][0-9]*)\]")


@dataclass(frozen=True)
class Diagnostic:
    path: str
    code: str


class CoverageFailure(Exception):
    """Safe finite outcome with read-only metadata."""

    def __init__(
        self, code: str, diagnostics: tuple[Diagnostic, ...] = (), *, failure_code: str | None = None,
    ):
        if not _safe_failure(code, diagnostics, failure_code):
            code, diagnostics, failure_code = "internal_policy", (), None
        super().__init__(code)
        self._code = code
        self._diagnostics = diagnostics
        self._failure_code = failure_code

    @property
    def code(self) -> str:
        return self._code

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return self._diagnostics

    @property
    def failure_code(self) -> str | None:
        return self._failure_code


def is_blank(value: str) -> bool:
    return all(scalar in _WHITESPACE for scalar in value)


def has_lone_surrogate(value: str) -> bool:
    return _SURROGATE.search(value) is not None


def validate_options(value: object) -> dict:
    if type(value) is not dict or value.keys() != set(_OPTION_KEYS):
        raise CoverageFailure("options_invalid")
    template, translation, include = (value[key] for key in _OPTION_KEYS)
    if type(template) is not str or template not in _TEMPLATES:
        raise CoverageFailure("options_invalid")
    if type(translation) is not str or len(translation) > 16 or has_lone_surrogate(translation):
        raise CoverageFailure("options_invalid")
    if type(include) is not dict or include.keys() != set(_FLAGS):
        raise CoverageFailure("options_invalid")
    if any(type(include[flag]) is not bool for flag in _FLAGS):
        raise CoverageFailure("options_invalid")
    return {"template": template, "preferred_translation": translation,
            "include": {flag: include[flag] for flag in _FLAGS}}


def _string(*choices: str) -> dict:
    schema = {"type": "string"}
    if choices:
        schema["enum"] = list(choices)
    return schema


def _array(items: dict) -> dict:
    return {"type": "array", "items": items}


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def public_schema(options: dict) -> dict:
    include = validate_options(options)["include"]
    properties = {"title": _string()}
    if include["scripture_extraction"]:
        properties["main_scripture"] = _string()
        properties["supporting_scriptures"] = _array(_string())
    properties["points"] = _array(_object({"text": _string(), "sub_points": _array(_string())}))
    for field, flag in _FLAT_SECTIONS:
        if flag is None or include[flag]:
            properties[field] = _array(_string())
    properties["introduction"] = _array(_string())
    if include["short_summary"]:
        properties["summary"] = _string()
    return _object(properties)


def private_schema(options: dict) -> dict:
    sections = public_schema(options)["properties"]
    del sections["points"]
    return _object({
        "schema_version": _string("1"),
        "outcome": _string("complete", "cannot_complete"),
        "failure_code": _string("none", *_CANNOT_COMPLETE_REASONS),
        "teachings": _array(_object({
            "id": _string(),
            "kind": _string("movement", "supporting_teaching", "application"),
            "text": _string(),
            "source_blocks": _array(_string()),
        })),
        "source_dispositions": _array(_object({
            "block_id": _string(),
            "teaching_ids": _array(_string()),
            "section_paths": _array(_string()),
            "excluded_reasons": _array(_string(*EXCLUDED_REASONS)),
            "repeats_teaching_ids": _array(_string()),
        })),
        "outline": _array(_object({
            "teaching_id": _string(),
            "sub_point_ids": _array(_string()),
        })),
        "sections": _object(sections),
        "section_links": _array(_object({
            "path": _string(),
            "source_blocks": _array(_string()),
        })),
        "quote_spans": _array(_object({
            "quote_index": {"type": "integer"},
            "first_block": _string(),
            "last_block": _string(),
            "occurrence": {"type": "integer"},
        })),
    })


# Feedback can only name paths in the candidate's private response, including gated fields.
_REPAIR_SCHEMA = private_schema({
    "template": _TEMPLATES[0], "preferred_translation": "", "include": dict.fromkeys(_FLAGS, True),
})


def is_safe_diagnostic(entry: Diagnostic) -> bool:
    if type(entry) is not Diagnostic or type(entry.code) is not str or type(entry.path) is not str:
        return False
    if entry.code == "invalid_json":
        return entry.path == "$"
    if entry.code not in _SCHEMA_ERROR_CODES or not entry.path.startswith("$"):
        return False
    schema = _REPAIR_SCHEMA
    position = 1
    while position < len(entry.path):
        step = _PATH_STEP.match(entry.path, position)
        if step is None:
            return False
        field = step.group(1)
        schema = schema.get("items") if field is None else schema.get("properties", {}).get(field)
        if schema is None:
            return False
        position = step.end()
    return True


def _safe_failure(code: str, diagnostics: tuple[Diagnostic, ...], failure_code: str | None) -> bool:
    if type(code) is not str or code not in _FAILURE_CODES or type(diagnostics) is not tuple:
        return False
    if code == "cannot_complete":
        return not diagnostics and type(failure_code) is str and failure_code in _CANNOT_COMPLETE_REASONS
    if failure_code is not None:
        return False
    if code == "invalid_json":
        return diagnostics == (Diagnostic("$", "invalid_json"),)
    if code == "invalid_schema":
        return (
            len(diagnostics) <= 20
            and all(is_safe_diagnostic(entry) and entry.code in _SCHEMA_ERROR_CODES for entry in diagnostics)
        )
    return not diagnostics
