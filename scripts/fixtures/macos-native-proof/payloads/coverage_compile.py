"""Mechanical private ledger validation and public NoteDraft wire projection."""

from dataclasses import dataclass
from hashlib import sha256
import json

from coverage_contract import (
    CoverageFailure, EXCLUDED_REASONS, has_lone_surrogate, is_blank, private_schema, public_schema, validate_options,
)
from coverage_index import SourceBlock
from coverage_json import schema_diagnostics


_MAX_TEACHINGS = 96
_MAX_POINTS = 32
_MAX_SUBPOINTS = 16
_MAX_BLOCKS = 512
_MAX_SECTION_LINKS = 800
_MAX_REFERENCE_TOTAL = 8192
_MAX_BLOCK_REFS = 8
_MAX_QUOTE_WINDOW = 4
_MAX_OCCURRENCE = 6400
_MAX_FLAT_ITEMS = 64
_MAX_SCRIPTURES = 128
_MAX_ORDINARY_SCALARS = 2000
# Final delivery is bounded more tightly than the native/parser transport ceiling.
_MAX_PUBLIC_BYTES = 256 * 1024
_SCALAR_LIMITS = {"title": 200, "main_scripture": _MAX_ORDINARY_SCALARS, "summary": 4000}
_ROOT_ARRAYS = {
    "teachings": _MAX_TEACHINGS,
    "source_dispositions": _MAX_BLOCKS,
    "outline": _MAX_POINTS,
    "section_links": _MAX_SECTION_LINKS,
    "quote_spans": _MAX_FLAT_ITEMS,
}


@dataclass(frozen=True)
class CompiledDraft:
    draft_json: bytes
    result_digest: str


def _bounded_array(container: dict, field: str, limit: int) -> list:
    items = container.get(field)
    if type(items) is not list:
        return []
    if len(items) > limit:
        raise CoverageFailure("local_contract")
    return items


def _bound_string(value: object, limit: int) -> None:
    if type(value) is str and len(value) > limit:
        raise CoverageFailure("local_contract")


def _records(items: list):
    return (item for item in items if type(item) is dict)


def _bound_private(value: object, section_fields: dict) -> None:
    """Find known size excess even in a structurally invalid JSON instance."""
    if type(value) is not dict:
        return
    arrays = {field: _bounded_array(value, field, limit) for field, limit in _ROOT_ARRAYS.items()}
    references = 0
    for teaching in _records(arrays["teachings"]):
        _bound_string(teaching.get("text"), _MAX_ORDINARY_SCALARS)
        references += len(_bounded_array(teaching, "source_blocks", _MAX_BLOCK_REFS))
    for point in _records(arrays["outline"]):
        references += int(type(point.get("teaching_id")) is str)
        references += len(_bounded_array(point, "sub_point_ids", _MAX_SUBPOINTS))
    for link in _records(arrays["section_links"]):
        references += len(_bounded_array(link, "source_blocks", _MAX_BLOCK_REFS))
    for row in _records(arrays["source_dispositions"]):
        references += len(_bounded_array(row, "teaching_ids", _MAX_TEACHINGS))
        references += len(_bounded_array(row, "section_paths", _MAX_SECTION_LINKS))
        references += len(_bounded_array(row, "repeats_teaching_ids", _MAX_TEACHINGS))
        _bounded_array(row, "excluded_reasons", len(EXCLUDED_REASONS))
    for span in _records(arrays["quote_spans"]):
        references += int(type(span.get("first_block")) is str) + int(type(span.get("last_block")) is str)
        occurrence = span.get("occurrence")
        if type(occurrence) is int and occurrence > _MAX_OCCURRENCE:
            raise CoverageFailure("quote_invalid")
    if references > _MAX_REFERENCE_TOTAL:
        raise CoverageFailure("local_contract")

    sections = value.get("sections")
    if type(sections) is not dict:
        return
    for field, schema in section_fields.items():
        if schema["type"] == "string":
            _bound_string(sections.get(field), _SCALAR_LIMITS[field])
        else:
            limit = _MAX_FLAT_ITEMS
            if field == "supporting_scriptures":
                main = sections.get("main_scripture")
                limit = _MAX_SCRIPTURES - int(type(main) is str and not is_blank(main))
            for item in _bounded_array(sections, field, limit):
                _bound_string(item, _MAX_ORDINARY_SCALARS)


def _validate_outcome_and_text(value: dict) -> None:
    failure = value["failure_code"]
    if value["outcome"] == "cannot_complete":
        if failure == "none" or any(value[field] for field in _ROOT_ARRAYS) or any(value["sections"].values()):
            raise CoverageFailure("local_contract")
        raise CoverageFailure("cannot_complete", failure_code=failure)
    if failure != "none":
        raise CoverageFailure("local_contract")
    for teaching in value["teachings"]:
        if is_blank(teaching["text"]) or has_lone_surrogate(teaching["text"]):
            raise CoverageFailure("local_contract")
    for item in value["sections"].values():
        if type(item) is str:
            if item and (is_blank(item) or has_lone_surrogate(item)):
                raise CoverageFailure("local_contract")
        elif any(is_blank(text) or has_lone_surrogate(text) for text in item):
            raise CoverageFailure("local_contract")


def _check_ordered_references(refs: list[str], ids) -> None:
    if any(ref not in ids for ref in refs) or any(prev >= current for prev, current in zip(refs, refs[1:])):
        raise CoverageFailure("reference_invalid")


def _source_references(refs: list[str], reverse_index: dict, value: str) -> None:
    if not refs:
        raise CoverageFailure("reference_invalid")
    _check_ordered_references(refs, reverse_index)
    for ref in refs:
        reverse_index[ref].append(value)


def _teaching_index(teachings: list, by_block: dict) -> dict:
    indexed = {}
    for position, teaching in enumerate(teachings):
        id_ = teaching["id"]
        if id_ != f"T{position:03d}":
            raise CoverageFailure("reference_invalid")
        _source_references(teaching["source_blocks"], by_block, id_)
        indexed[id_] = teaching
    return indexed


def _validate_outline(outline: list, teaching_by_id: dict) -> None:
    used = set()
    for point in outline:
        for index, id_ in enumerate([point["teaching_id"], *point["sub_point_ids"]]):
            teaching = teaching_by_id.get(id_)
            if teaching is None or id_ in used or (teaching["kind"] == "movement") != (index == 0):
                raise CoverageFailure("reference_invalid")
            used.add(id_)
    if used != teaching_by_id.keys():
        raise CoverageFailure("reference_invalid")


def _link_index(sections: dict, links: list, by_block: dict) -> dict:
    expected = []
    for field, value in sorted(sections.items()):
        if type(value) is list:
            expected.extend(f"/{field}/{index}" for index in range(len(value)))
        elif value:
            expected.append(f"/{field}")
    if [link["path"] for link in links] != expected:
        raise CoverageFailure("reference_invalid")
    by_path = {}
    for link in links:
        path = link["path"]
        refs = link["source_blocks"]
        _source_references(refs, by_block, path)
        by_path[path] = refs
    return by_path


def _validate_dispositions(rows: list, by_teaching: dict, by_section: dict, teachings: dict, template: str) -> None:
    if [row["block_id"] for row in rows] != list(by_teaching):
        raise CoverageFailure("reference_invalid")
    for row in rows:
        block = row["block_id"]
        if row["teaching_ids"] != by_teaching[block] or row["section_paths"] != by_section[block]:
            raise CoverageFailure("reference_invalid")

        reasons = row["excluded_reasons"]
        repeats = row["repeats_teaching_ids"]
        if (reasons != [reason for reason in EXCLUDED_REASONS if reason in reasons]
                or ("repetition" in reasons) != bool(repeats)
                or ("template_compression" in reasons and template not in ("summary", "devotional"))
                or not (row["teaching_ids"] or row["section_paths"] or reasons)):
            raise CoverageFailure("local_contract")
        _check_ordered_references(repeats, teachings)


def _validate_quotes(
    quotes: list, spans: list, blocks: tuple[SourceBlock, ...], positions: dict, links: dict,
) -> None:
    if len(spans) != len(quotes):
        raise CoverageFailure("quote_invalid")
    for index, (quote, span) in enumerate(zip(quotes, spans)):
        first = positions.get(span["first_block"])
        last = positions.get(span["last_block"])
        occurrence = span["occurrence"]
        if (span["quote_index"] != index or not 1 <= occurrence <= _MAX_OCCURRENCE
                or first is None or last is None or not 0 <= last - first < _MAX_QUOTE_WINDOW):
            raise CoverageFailure("quote_invalid")
        window = blocks[first:last + 1]
        text = "".join(block.text for block in window)
        start = -1
        for _ in range(occurrence):
            start = text.find(quote, start + 1)
            if start == -1:
                raise CoverageFailure("quote_invalid")
        if (start >= len(window[0].text) or start + len(quote) <= len(text) - len(window[-1].text)
                or links[f"/quotes/{index}"] != [block.id for block in window]):
            raise CoverageFailure("quote_invalid")


def compile_private(value: object, blocks: tuple[SourceBlock, ...], options: dict) -> CompiledDraft:
    options = validate_options(options)
    private = private_schema(options)
    _bound_private(value, private["properties"]["sections"]["properties"])
    diagnostics = schema_diagnostics(value, private)
    if diagnostics:
        raise CoverageFailure("invalid_schema", diagnostics)
    _validate_outcome_and_text(value)

    # Blocks are the locally produced index. Only their IDs and exact text are needed here.
    if type(blocks) is not tuple or not 1 <= len(blocks) <= _MAX_BLOCKS or any(
        type(block) is not SourceBlock or block.id != f"B{position:04d}"
        for position, block in enumerate(blocks)
    ):
        raise CoverageFailure("internal_policy")
    positions = {block.id: index for index, block in enumerate(blocks)}
    by_block_teachings = {id_: [] for id_ in positions}
    by_block_sections = {id_: [] for id_ in positions}
    teachings = _teaching_index(value["teachings"], by_block_teachings)
    _validate_outline(value["outline"], teachings)
    sections = value["sections"]
    links = _link_index(sections, value["section_links"], by_block_sections)
    _validate_dispositions(value["source_dispositions"], by_block_teachings, by_block_sections,
                           teachings, options["template"])
    _validate_quotes(sections.get("quotes", []), value["quote_spans"], blocks, positions, links)

    points = [
        {
            "text": teachings[point["teaching_id"]]["text"],
            "sub_points": [teachings[id_]["text"] for id_ in point["sub_point_ids"]],
        }
        for point in value["outline"]
    ]
    public = public_schema(options)
    fields = {**sections, "points": points}
    draft = {field: fields[field] for field in public["properties"]}
    if schema_diagnostics(draft, public):
        raise CoverageFailure("internal_policy")
    draft_json = json.dumps(draft, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(draft_json) > _MAX_PUBLIC_BYTES:
        raise CoverageFailure("byte_limit")
    return CompiledDraft(draft_json, sha256(draft_json).hexdigest())
