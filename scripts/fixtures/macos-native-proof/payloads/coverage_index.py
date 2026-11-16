"""Deterministic source block IDs and lossless scalar/UTF-8 offsets."""

from dataclasses import dataclass

from coverage_contract import CoverageFailure, has_lone_surrogate, is_blank


_MAX_SCALARS = 400_000
_MAX_UTF8_BYTES = 1_600_000
_MIN_PREFERRED_BLOCK = 800
_MAX_BLOCK_SCALARS = 1600
_MAX_BLOCKS = 512


@dataclass(frozen=True)
class SourceBlock:
    id: str
    text: str
    scalar_start: int
    scalar_end: int
    utf8_start: int
    utf8_end: int


def _block_end(source: str, start: int) -> int:
    limit = start + _MAX_BLOCK_SCALARS
    if len(source) <= limit:
        return len(source)
    for end in range(limit, start + _MIN_PREFERRED_BLOCK - 1, -1):
        last = source[end - 1]
        if last == "\n" or (last in " \t" and source[end - 2] in ".!?"):
            return end
    return limit


def index_source(source: str) -> tuple[SourceBlock, ...]:
    if type(source) is not str or len(source) > _MAX_SCALARS or has_lone_surrogate(source) or is_blank(source):
        raise CoverageFailure("source_invalid")
    if len(source.encode("utf-8")) > _MAX_UTF8_BYTES:
        raise CoverageFailure("source_invalid")

    blocks = []
    scalar_start = utf8_start = 0
    while scalar_start < len(source):
        if len(blocks) == _MAX_BLOCKS:
            raise CoverageFailure("source_invalid")
        scalar_end = _block_end(source, scalar_start)
        text = source[scalar_start:scalar_end]
        utf8_end = utf8_start + len(text.encode("utf-8"))
        blocks.append(SourceBlock(f"B{len(blocks):04d}", text, scalar_start, scalar_end, utf8_start, utf8_end))
        scalar_start, utf8_start = scalar_end, utf8_end
    return tuple(blocks)
