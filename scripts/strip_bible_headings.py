#!/usr/bin/env python3
"""Strip psalm titles, Psalm 119 acrostic labels and the Habakkuk 3:19 note from the bundled Bibles.

The five assets in selahcue-scripture/assets/ were converted from eBible.org VPL exports. VPL
flattens every heading into the verse that follows it, so Psalm 42:1 was stored as "To the chief
Musician, Maschil, for the sons of Korah. As the hart panteth ..." and the title was shown to the
congregation as scripture (17tnw2b2g7q). Verse NUMBERING is unaffected -- the titles live inside
verse 1, not in a verse 0 -- so this changes text only.

Why USFM is the oracle and not a heuristic: a title ends where the verse begins, and nothing in
the flattened text says where that is. "Cut at the first `. `" is wrong for KJV Psalms 18 and 54,
and the other four translations use multi-sentence titles ("For the Chief Musician. A Psalm by
David, when ..."). eBible's USFM keeps each title on its own `\\d` line, so it tells us the exact
string to remove. We keep the existing, audited verse text and remove ONLY what USFM names:

- every `\\d` line in Psalms (116 titles; WEB/WEBBE also tag the 22 Psalm 119 letters as `\\d`,
  but VPL fused only the first, "ALEPH", and dropped the other 21 -- see strip_rows)
- DBY's 22 Psalm 119 letters, which USFM leaves inline in the verse ("\\v 1 ALEPH. ...")
- the trailing musical note at the end of Habakkuk 3:19, tagged differently in every USFM (inline,
  `\\p`, `\\d`), so it is an explicit per-translation table below, not parsed

Genuine numbered verses stay: Habakkuk 3:1, Isaiah 38:9, Song 1:1.

Every title must be a literal prefix of the current row. A heading that does not match ABORTS the
run with the full list of misses and writes nothing -- eBible re-releases its files, and a changed
title must be looked at by a person, not guessed around. After a run the old and new assets are
compared row by row and the run fails unless exactly the expected rows changed.

The script does no network access. Download the five USFM zips yourself:

    https://eBible.org/Scriptures/eng-kjv_usfm.zip    (KJV)
    https://eBible.org/Scriptures/engwebp_usfm.zip    (WEB)
    https://eBible.org/Scriptures/engwebpb_usfm.zip   (WEBBE)
    https://eBible.org/Scriptures/eng-asv_usfm.zip    (ASV)
    https://eBible.org/Scriptures/engDBY_usfm.zip     (DBY)

    python3 scripts/strip_bible_headings.py --usfm-dir DIR            # dry run: check + report
    python3 scripts/strip_bible_headings.py --usfm-dir DIR --write    # rewrite the assets
    python3 scripts/strip_bible_headings.py --self-test

Not run by `make ci`: this is a one-shot maintenance tool, and the guard that keeps the data clean
afterwards is the corpus scan in selahcue-scripture/tests/test_scripture_data.rs. Running it again
on an already-cleaned asset aborts (nothing matches); `git checkout -- <assets>` first.
"""
import argparse
import gzip
import io
import pathlib
import re
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "implementation/desktop/crates/selahcue-scripture/assets"
PSALMS, HABAKKUK = 19, 35  # canonical book numbers used by the TSVs

# asset name -> (eBible id, the note that ends Habakkuk 3:19 in that translation)
SOURCES = {
    "kjv": ("eng-kjv", "To the chief singer on my stringed instruments."),
    "web": ("engwebp", "For the music director, on my stringed instruments."),
    "webbe": ("engwebpb", "For the music director, on my stringed instruments."),
    "asv": ("eng-asv", "For the Chief Musician, on my stringed instruments."),
    "dby": ("engDBY", "To the chief Musician. On my stringed instruments."),
}
# Headings USFM must yield per translation: 116 psalm titles, plus the 22 Psalm 119 letters
# where the translation has them. A different count means upstream changed; stop and look.
EXPECTED_HEADINGS = {"kjv": 116, "web": 138, "webbe": 138, "asv": 116, "dby": 138}

_NOTE = re.compile(r"\\(?:f|x)\s.*?\\(?:f|x)\*", re.S)  # footnotes and cross references
_WORD = re.compile(r"\\\+?w\s+([^|\\]*?)(?:\|[^\\]*)?\\\+?w\*")  # \w word|strong="H1"\w*
_MARK = re.compile(r"\\\+?[A-Za-z][A-Za-z0-9]*\*?")  # any remaining character/paragraph marker
_LETTER = re.compile(r"^[A-Za-z]+\.?$")  # a lone word: an acrostic letter, compared case-blind
_INLINE_LABEL = re.compile(r"^([A-Z]{2,}\.)\s")  # DBY: "ALEPH. Blessed ..." inside the verse


class Mismatch(Exception):
    """One or more headings could not be matched to the asset; carries every one."""

    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


def clean_usfm(s):
    s = _NOTE.sub("", s)
    s = _WORD.sub(r"\1", s)
    s = _MARK.sub("", s)
    # The assets were already stripped of these (batch 7ae: test_scripture_data.rs asserts none
    # survive), so the oracle must lose them too or "[A Psalm] of David." never matches the row.
    s = s.translate({ord(c): None for c in "[]¶*"})
    return " ".join(s.split())


def _quotes(s):
    # One-for-one, so a prefix length measured on the mapped text is valid on the original.
    return s.translate(str.maketrans("\u2018\u2019\u201c\u201d", "''\"\""))


def headings_from_usfm(text):
    """{(chapter, verse): heading} for every title/label that precedes a verse in a Psalms file."""
    found, pending, chapter = {}, [], 0
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"\\c\s+(\d+)\b", line)
        if m:
            if pending:
                raise Mismatch([f"Psalm {chapter}: heading {pending!r} has no verse after it"])
            chapter = int(m.group(1))
            continue
        m = re.match(r"\\d\s+(.*)", line)
        if m:
            pending.append(clean_usfm(m.group(1)))
            continue
        m = re.match(r"\\v\s+(\d+)\s*(.*)", line)
        if not m:
            continue
        verse = int(m.group(1))
        if pending:
            found[(chapter, verse)] = " ".join(pending)
            pending = []
        elif chapter == 119:
            label = _INLINE_LABEL.match(clean_usfm(m.group(2)))
            if label:
                found[(chapter, verse)] = label.group(1)
    if pending:
        raise Mismatch([f"Psalm {chapter}: heading {pending!r} has no verse after it"])
    return found


def parse_rows(lines):
    rows = {}
    for i, line in enumerate(lines):
        parts = line.split("\t")
        if len(parts) != 4:
            raise ValueError(f"line {i + 1}: expected 4 tab-separated fields, got {len(parts)}")
        rows[(int(parts[0]), int(parts[1]), int(parts[2]))] = i
    return rows


def strip_rows(lines, headings, hab_tail):
    """Return (new_lines, edits, absent). Raises Mismatch listing every heading that is not a prefix.

    A title before a chapter's FIRST verse must be a prefix of that row -- VPL fused it, so it has
    to be there. A heading before a later verse (the Psalm 119 letters in WEB/WEBBE) was dropped by
    VPL rather than fused, so its row legitimately does not start with it: those come back in
    `absent` and are reported, never silently ignored. If one does start with it, it is stripped.
    """
    rows = parse_rows(lines)
    new_lines, edits, absent, problems = list(lines), [], [], []

    def put(key, removed, new_text):
        i = rows[key]
        book, chapter, verse, _ = lines[i].split("\t")
        new_lines[i] = "\t".join((book, chapter, verse, new_text))
        edits.append((key, removed, i))

    for (chapter, verse), heading in sorted(headings.items()):
        key = (PSALMS, chapter, verse)
        text = lines[rows[key]].split("\t")[3] if key in rows else None
        if text is None:
            problems.append(f"Psalm {chapter}:{verse}: no such row in the asset")
            continue
        a, b = _quotes(text[: len(heading)]), _quotes(heading)
        if (a.casefold() != b.casefold()) if _LETTER.match(heading) else (a != b):
            if verse > 1:
                absent.append((key, heading))
            else:
                problems.append(f"Psalm {chapter}:{verse}: row starts {text[:60]!r}, USFM says {heading!r}")
            continue
        rest = text[len(heading):]
        if not rest.startswith(" ") or not rest.strip():
            problems.append(f"Psalm {chapter}:{verse}: nothing (or no space) after {heading!r}")
            continue
        put(key, text[: len(heading)], rest[1:])  # the row's own spelling, not USFM's

    key = (HABAKKUK, 3, 19)
    text = lines[rows[key]].split("\t")[3]
    if not text.endswith(" " + hab_tail):
        problems.append(f"Habakkuk 3:19: row ends {text[-60:]!r}, expected {hab_tail!r}")
    else:
        put(key, hab_tail, text[: -len(hab_tail) - 1])

    if problems:
        raise Mismatch(problems)
    return new_lines, edits, absent


def verify(old_lines, new_lines, edits):
    """Row-by-row proof that exactly the edited rows changed, and changed only by the removal."""
    if len(old_lines) != len(new_lines):
        raise Mismatch([f"line count changed: {len(old_lines)} -> {len(new_lines)}"])
    expected = {i for _, _, i in edits}
    changed = {i for i, (o, n) in enumerate(zip(old_lines, new_lines)) if o != n}
    if changed != expected:
        raise Mismatch([f"changed rows differ from the edit list by {sorted(changed ^ expected)[:10]}"])
    for (key, removed, i) in edits:
        old, new = old_lines[i].split("\t")[3], new_lines[i].split("\t")[3]
        if old != removed + " " + new and old != new + " " + removed:
            raise Mismatch([f"{key}: {old!r} is not {removed!r} + {new!r}"])
        if not new or new != new.strip():
            raise Mismatch([f"{key}: bad remainder {new!r}"])


def to_gzip(data):
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as g:
        g.write(data)
    return buf.getvalue()


def psalms_usfm(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if "PSA" in n.upper() and n.lower().endswith(".usfm")]
        if len(names) != 1:
            raise SystemExit(f"{zip_path}: expected exactly one Psalms .usfm, found {names}")
        return z.read(names[0]).decode("utf-8")


def process(name, asset, usfm_zip, write):
    before = asset.stat().st_size
    raw = gzip.decompress(asset.read_bytes()).decode("utf-8")
    trailing = raw.endswith("\n")
    lines = raw.split("\n")[:-1] if trailing else raw.split("\n")
    headings = headings_from_usfm(psalms_usfm(usfm_zip))
    if len(headings) != EXPECTED_HEADINGS[name]:
        raise Mismatch([f"{name}: USFM yields {len(headings)} headings, expected {EXPECTED_HEADINGS[name]}"])
    new_lines, edits, absent = strip_rows(lines, headings, SOURCES[name][1])
    verify(lines, new_lines, edits)
    data = ("\n".join(new_lines) + ("\n" if trailing else "")).encode("utf-8")
    out = to_gzip(data)
    if write:
        tmp = asset.with_suffix(asset.suffix + ".tmp")
        tmp.write_bytes(out)
        tmp.replace(asset)
    return edits, absent, before, len(out)


def report_lines(name, edits, absent):
    out = [f"## {name}"]
    for (book, chapter, verse), removed, _ in sorted(edits):
        ref = "Habakkuk 3:19 (trailing note)" if book == HABAKKUK else f"Psalm {chapter}:{verse}"
        out.append(f"- {ref}: {removed}")
    for (_, chapter, verse), heading in sorted(absent):
        out.append(f"- Psalm {chapter}:{verse}: {heading} (mid-chapter heading, not fused into the asset; unchanged)")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--usfm-dir", type=pathlib.Path, help="directory holding the five *_usfm.zip files")
    ap.add_argument("--assets", type=pathlib.Path, default=ASSETS)
    ap.add_argument("--write", action="store_true", help="rewrite the assets (default: dry run)")
    ap.add_argument("--report", type=pathlib.Path, help="write the removed strings as markdown")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.usfm_dir:
        ap.error("--usfm-dir is required (see the URLs in the module docstring)")

    report, failed = [], False
    for name, (ebible_id, _) in SOURCES.items():
        zip_path = args.usfm_dir / f"{ebible_id}_usfm.zip"
        if not zip_path.is_file():
            sys.exit(f"missing {zip_path}; download https://eBible.org/Scriptures/{ebible_id}_usfm.zip")
        try:
            edits, absent, before, after = process(name, args.assets / f"{name}.tsv.gz", zip_path, args.write)
        except Mismatch as e:
            failed = True
            print(f"{name}: ABORTED, nothing written for it\n  " + "\n  ".join(e.problems[:25]))
            if len(e.problems) > 25:
                print(f"  ... and {len(e.problems) - 25} more")
            continue
        titles = sum(1 for k, _, _ in edits if k[0] == PSALMS)
        skipped = f" ({len(absent)} mid-chapter headings were never fused, left alone)" if absent else ""
        print(f"{name}: {titles} psalm headings{skipped} + 1 Habakkuk note = {len(edits)} rows changed "
              f"({'written' if args.write else 'dry run'}; asset {before} -> {after} bytes)")
        report += report_lines(name, edits, absent)
    if args.report and not failed:
        args.report.write_text("\n".join(report) + "\n", encoding="utf-8")
    return 1 if failed else 0


def self_test():
    def tsv(*rows):
        return ["\t".join(map(str, r)) for r in rows]

    # 1. Markup, curly quotes, a multi-line title, a letter label (case-blind) and the trailer.
    usfm = "\n".join([
        "\\c 1 ", "\\d To the chief \\w Musician|strong=\"H1\"\\w*, for David\u2019s sons.  ",
        "\\q1", "\\v 1 As the \\w hart|strong=\"H2\"\\w* panteth", "\\c 2 ",
        r"\d For the Chief Musician.", r"\d A Psalm by David.", r"\v 1 Why do the nations rage?",
        r"\c 3 ", r"\d [A Psalm] of David.", r"\v 3 Many say of my soul",  # DBY marks supplied words
        r"\c 119 ", r"\d ALEPH", r"\v 1 Blessed are those", r"\v 9 BETH. Wherewithal shall",
        r"\d GIMEL", r"\v 17 Untouched verse",  # a mid-chapter heading VPL never fused
    ])
    h = headings_from_usfm(usfm)
    assert h[(1, 1)] == "To the chief Musician, for David\u2019s sons.", h
    assert h[(2, 1)] == "For the Chief Musician. A Psalm by David.", h
    assert h[(3, 3)] == "A Psalm of David.", h  # brackets are gone, as in the asset
    assert h[(119, 1)] == "ALEPH" and h[(119, 9)] == "BETH." and h[(119, 17)] == "GIMEL", h
    old = tsv(
        (19, 1, 1, "To the chief Musician, for David's sons. As the hart panteth"),
        (19, 2, 1, "For the Chief Musician. A Psalm by David. Why do the nations rage?"),
        (19, 3, 3, "A Psalm of David. Many say of my soul"),
        (19, 119, 1, "Aleph Blessed are those"), (19, 119, 9, "BETH. Wherewithal shall"),
        (19, 119, 17, "Untouched verse"),
        (35, 3, 19, "He will make me walk. To the chief singer on my stringed instruments."),
    )
    tail = "To the chief singer on my stringed instruments."
    new, edits, absent = strip_rows(old, h, tail)
    verify(old, new, edits)
    got = [l.split("\t")[3] for l in new]
    assert got == ["As the hart panteth", "Why do the nations rage?", "Many say of my soul",
                   "Blessed are those", "Wherewithal shall", "Untouched verse",
                   "He will make me walk."], got
    assert [k for k, _ in absent] == [(19, 119, 17)], absent  # reported, and the row is untouched
    assert gzip.decompress(to_gzip(b"x\n")) == b"x\n" and to_gzip(b"x") == to_gzip(b"x")

    # 2. A title that is not a prefix aborts and names it; nothing is guessed.
    for bad_heading in ({(1, 1): "A different title."}, {(1, 9): "No such verse."}):
        try:
            strip_rows(old, bad_heading, "To the chief singer on my stringed instruments.")
        except Mismatch as e:
            assert e.problems, e
        else:
            raise AssertionError("mismatched heading was accepted")
    try:
        strip_rows(old, {}, "A note that is not there.")
    except Mismatch:
        pass
    else:
        raise AssertionError("missing Habakkuk note was accepted")

    # 3. verify() catches a row that changed without being listed, and a bad remainder.
    sneaky = list(new)
    sneaky[5] = sneaky[5].replace("Untouched", "Touched")
    try:
        verify(old, sneaky, edits)
    except Mismatch:
        pass
    else:
        raise AssertionError("verify() missed a row that changed without being listed")

    # 4. A heading with no verse after it (chapter ends) is refused rather than dropped.
    try:
        headings_from_usfm("\\c 5 \n\\d Orphan title.\n\\c 6 \n\\v 1 Text")
    except Mismatch:
        pass
    else:
        raise AssertionError("orphan heading was accepted")

    # 5. End to end through a real zip and a real asset: dry run leaves it byte-identical.
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        asset = d / "kjv.tsv.gz"
        asset.write_bytes(to_gzip(("\n".join(old) + "\n").encode()))
        before = asset.read_bytes()
        z = d / "eng-kjv_usfm.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("20-PSAeng-kjv.usfm", usfm)
        global EXPECTED_HEADINGS
        saved, EXPECTED_HEADINGS = EXPECTED_HEADINGS, {**EXPECTED_HEADINGS, "kjv": 6}
        try:
            edits, absent, _, _ = process("kjv", asset, z, write=False)
            assert asset.read_bytes() == before and len(edits) == 6 and len(absent) == 1
            process("kjv", asset, z, write=True)
            rows = gzip.decompress(asset.read_bytes()).decode().split("\n")
            assert rows[-1] == "" and rows[0].endswith("\tAs the hart panteth"), rows
        finally:
            EXPECTED_HEADINGS = saved
    print("strip_bible_headings self-test: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
