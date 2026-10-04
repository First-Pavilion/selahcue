#!/usr/bin/env python3
"""Strip psalm titles, Psalm 119 acrostic labels and the Habakkuk 3:19 note from the bundled Bibles.

The five assets in selahcue-scripture/assets/ were converted from eBible.org VPL exports. VPL
flattens every heading into a verse line, so Psalm 42:1 was stored as "To the chief Musician,
Maschil, for the sons of Korah. As the hart panteth ..." and the title was shown to the congregation
as scripture (17tnw2b2g7q). Verse NUMBERING is unaffected -- the headings live inside a verse's
text, not in a verse 0 -- so this changes text only.

Why USFM is the oracle and not a heuristic: a title ends where the verse begins, and nothing in
the flattened text says where that is. "Cut at the first `. `" is wrong for KJV Psalms 18 and 54,
and the other four translations use multi-sentence titles ("For the Chief Musician. A Psalm by
David, when ..."). eBible's USFM keeps each title on its own `\\d` line, so it tells us the exact
string to remove. We keep the existing, audited verse text and remove ONLY what USFM names.

WHERE VPL PUT EACH HEADING (this is what the first version of this script got wrong, and why the
check below is "start of this verse OR end of the previous verse", never "start only"):

- at the START of the verse it precedes: every psalm title, and DBY's 22 Psalm 119 letters
  ("\\v 1 ALEPH. Blessed ...", inline in USFM too);
- at the END of the PREVIOUS verse: WEB/WEBBE's 21 Psalm 119 letters after the first, because VPL
  hangs a heading on the line before it ("... Don't utterly forsake me. BETH" is 119:8, and the
  verse that BETH introduces, 119:9, starts clean). WEB's "ALEPH" is at the start of 119:1 only
  because nothing precedes it.

The other edit is the musical note that closes Habakkuk 3:19, tagged differently in every USFM
(inline, `\\p`, `\\d`), so it is an explicit per-translation table below, not parsed.

Genuine numbered verses stay: Habakkuk 3:1, Isaiah 38:9, Song 1:1.

Every heading the USFM names must be found, as a literal string, at the start of its own verse or
at the end of the previous one. A heading found in neither, or in both, ABORTS the run with the
full list of misses and writes nothing: eBible re-releases its files, and a changed or misplaced
heading must be looked at by a person, not guessed around or skipped. Nothing is "left alone".
Writing is all-or-nothing across the five translations: if any one aborts, no asset is touched.
After the edit the old and new rows are compared and the run fails unless exactly the expected
rows changed, each by exactly the removed string.

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
afterwards is the corpus scan in selahcue-scripture/tests/test_scripture_data.rs (it checks how
verses START and how they END). Running the script again on an already-cleaned asset aborts
(nothing matches); `git checkout -- <assets>` first.

Output is byte-reproducible for a given zlib: the gzip header carries no timestamp or filename.
If bytes ever differ on another machine's zlib, compare the DECOMPRESSED TSV, not the sha.
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
_INLINE_LABEL = re.compile(r"^([A-Z]{2,}\.)\s")  # DBY: "ALEPH. Blessed ..." inside the verse


class Mismatch(Exception):
    """One or more headings could not be placed, or a check failed; carries every problem."""

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
    # One-for-one, so a length measured on the mapped text is valid on the original.
    return s.translate(str.maketrans("\u2018\u2019\u201c\u201d", "''\"\""))


def headings_from_usfm(text):
    """{(chapter, verse): heading} for every title/label that precedes a verse in a Psalms file."""
    found, pending, chapter = {}, [], 0
    for raw in text.splitlines():
        line = raw.strip()
        if pending and line and not line.startswith("\\"):
            # A marker-less line continues the paragraph before it, i.e. the heading. Taking only
            # its first line would truncate it, and a truncated heading still passes a prefix check.
            raise Mismatch([f"Psalm {chapter}: heading {pending[-1]!r} continues on the next line "
                            f"({line[:40]!r}); the parser does not join continuation lines"])
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


def _starts(text, heading):
    n = len(heading)
    return _quotes(text[:n]) == _quotes(heading) and text[n:n + 1] == " " and bool(text[n:].strip())


def _ends(text, heading):
    n = len(heading)
    return (len(text) > n and _quotes(text[len(text) - n:]) == _quotes(heading)
            and text[len(text) - n - 1] == " " and bool(text[:len(text) - n].strip()))


def strip_rows(lines, headings, hab_tail):
    """Return (new_lines, edits). Raises Mismatch listing EVERY heading that could not be placed.

    `edits` is a list of (row key, removed text, line index, where) with where in
    "start" | "end" | "note". Each row may be edited at most once (verify() relies on it).
    """
    rows = parse_rows(lines)
    new_lines, edits, problems, done = list(lines), [], [], set()

    def text_of(key):
        return new_lines[rows[key]].split("\t")[3] if key in rows else None

    def put(key, removed, new_text, where):
        i = rows[key]
        if i in done:
            problems.append(f"{key}: would be edited twice (second removal {removed!r})")
            return
        done.add(i)
        book, chapter, verse, _ = new_lines[i].split("\t")
        new_lines[i] = "\t".join((book, chapter, verse, new_text))
        edits.append((key, removed, i, where))

    for (chapter, verse), heading in sorted(headings.items()):
        here_key, prev_key = (PSALMS, chapter, verse), (PSALMS, chapter, verse - 1)
        here = text_of(here_key)
        there = text_of(prev_key) if verse > 1 else None
        at_start = here is not None and _starts(here, heading)
        at_end = there is not None and _ends(there, heading)
        label = f"Psalm {chapter}:{verse}"
        if at_start and at_end:
            problems.append(f"{label}: {heading!r} is at the start of this verse AND at the end of "
                            f"the previous one; refusing to guess which is the heading")
        elif at_start:
            put(here_key, here[:len(heading)], here[len(heading) + 1:], "start")
        elif at_end:
            put(prev_key, there[len(there) - len(heading):], there[:len(there) - len(heading) - 1], "end")
        else:
            problems.append(
                f"{label}: USFM names {heading!r} but it is neither at the start of this verse "
                f"({(here or '(no such row)')[:50]!r}) nor at the end of the previous one "
                f"({(there or '(none)')[-50:]!r})")

    key = (HABAKKUK, 3, 19)
    text = text_of(key)
    if text is None:
        problems.append("Habakkuk 3:19: no such row in the asset")
    elif not text.endswith(" " + hab_tail):
        problems.append(f"Habakkuk 3:19: row ends {text[-60:]!r}, expected {hab_tail!r}")
    else:
        put(key, hab_tail, text[:-len(hab_tail) - 1], "note")

    if problems:
        raise Mismatch(problems)
    return new_lines, edits


def verify(old_lines, new_lines, edits):
    """Row-by-row proof that exactly the edited rows changed, and changed only by the removal."""
    if len(old_lines) != len(new_lines):
        raise Mismatch([f"line count changed: {len(old_lines)} -> {len(new_lines)}"])
    expected = {i for _, _, i, _ in edits}
    changed = {i for i, (o, n) in enumerate(zip(old_lines, new_lines)) if o != n}
    if changed != expected:
        raise Mismatch([f"changed rows differ from the edit list by {sorted(changed ^ expected)[:10]}"])
    for (key, removed, i, _) in edits:
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
            raise Mismatch([f"{zip_path}: expected exactly one Psalms .usfm, found {names}"])
        return z.read(names[0]).decode("utf-8")


def process(name, asset, usfm_zip):
    """Check and compute one translation. Returns (new gzip bytes, edits, old size). Writes nothing."""
    before = asset.stat().st_size
    try:
        raw = gzip.decompress(asset.read_bytes()).decode("utf-8")
        trailing = raw.endswith("\n")
        lines = raw.split("\n")[:-1] if trailing else raw.split("\n")
        headings = headings_from_usfm(psalms_usfm(usfm_zip))
        if len(headings) != EXPECTED_HEADINGS[name]:
            raise Mismatch([f"{name}: USFM yields {len(headings)} headings, expected "
                            f"{EXPECTED_HEADINGS[name]}"])
        new_lines, edits = strip_rows(lines, headings, SOURCES[name][1])
    except (KeyError, ValueError, OSError, zipfile.BadZipFile, gzip.BadGzipFile) as e:
        raise Mismatch([f"{name}: unreadable or malformed input ({type(e).__name__}: {e})"])
    verify(lines, new_lines, edits)
    data = ("\n".join(new_lines) + ("\n" if trailing else "")).encode("utf-8")
    return to_gzip(data), edits, before


def report_lines(name, edits):
    out = [f"## {name}"]
    for (book, chapter, verse), removed, _, where in sorted(edits):
        if where == "note":
            out.append(f"- Habakkuk 3:19 (trailing note): {removed}")
        elif where == "end":
            out.append(f"- Psalm {chapter}:{verse} (label at the END of the verse, introducing "
                       f"{chapter}:{verse + 1}): {removed}")
        else:
            out.append(f"- Psalm {chapter}:{verse}: {removed}")
    return out


def run(usfm_dir, assets, write, report=None, names=None):
    """The whole job. All-or-nothing: if any translation aborts, nothing is written for any."""
    names = list(names or SOURCES)
    results, failed = {}, False
    for name in names:
        ebible_id = SOURCES[name][0]
        zip_path = usfm_dir / f"{ebible_id}_usfm.zip"
        if not zip_path.is_file():
            sys.exit(f"missing {zip_path}; download https://eBible.org/Scriptures/{ebible_id}_usfm.zip")
        try:
            results[name] = process(name, assets / f"{name}.tsv.gz", zip_path)
        except Mismatch as e:
            failed = True
            print(f"{name}: ABORTED\n  " + "\n  ".join(e.problems[:25]))
            if len(e.problems) > 25:
                print(f"  ... and {len(e.problems) - 25} more")
    if failed:
        print("NOTHING WRITTEN: at least one translation aborted, and the write is all-or-nothing.")
        return 1

    report_md = []
    for name, (out, edits, before) in results.items():
        titles = sum(1 for k, _, _, w in edits if w != "note")
        print(f"{name}: {titles} headings + 1 Habakkuk note = {len(edits)} rows changed "
              f"({'written' if write else 'dry run'}; asset {before} -> {len(out)} bytes)")
        report_md += report_lines(name, edits)
    if write:
        tmps = []
        for name, (out, _, _) in results.items():
            asset = assets / f"{name}.tsv.gz"
            tmp = asset.with_suffix(asset.suffix + ".tmp")
            tmp.write_bytes(out)
            tmps.append((tmp, asset))
        for tmp, asset in tmps:
            tmp.replace(asset)
    if report:
        report.write_text("\n".join(report_md) + "\n", encoding="utf-8")
    return 0


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
    return run(args.usfm_dir, args.assets, args.write, args.report)


def self_test():
    def tsv(*rows):
        return ["\t".join(map(str, r)) for r in rows]

    def raises(fn, what, needle=None):
        try:
            fn()
        except Mismatch as e:
            if needle:
                assert needle in "\n".join(e.problems), (needle, e.problems)
            return e
        raise AssertionError(what)

    # One fixture exercising every placement: titles at the START of verse 1 (with markup, curly
    # quotes, a two-line `\d`), a bracketed DBY-style title at verse 3, a Psalm 119 label at the
    # START of 119:1, TRAILING labels on 119:8 and 119:16 (the WEB/WEBBE shape), a DBY-style inline
    # label at 119:25, and the Habakkuk note.
    usfm = "\n".join([
        "\\c 1 ", "\\d To the chief \\w Musician|strong=\"H1\"\\w*, for David\u2019s sons.  ",
        "\\q1", "\\v 1 As the \\w hart|strong=\"H2\"\\w* panteth", "\\c 2 ",
        r"\d For the Chief Musician.", r"\d A Psalm by David.", r"\v 1 Why do the nations rage?",
        r"\c 3 ", r"\d [A Psalm] of David.", r"\v 3 Many say of my soul",
        r"\c 119 ", r"\d ALEPH", r"\v 1 Blessed are those", r"\v 8 I will observe",
        r"\d BETH", r"\v 9 How can a young man", r"\v 16 I will not forget",
        r"\d GIMEL", r"\v 17 Do good to your servant", r"\v 25 DALETH. My soul cleaveth",
    ])
    h = headings_from_usfm(usfm)
    assert h[(1, 1)] == "To the chief Musician, for David\u2019s sons.", h
    assert h[(2, 1)] == "For the Chief Musician. A Psalm by David.", h
    assert h[(3, 3)] == "A Psalm of David.", h  # brackets are gone, as in the asset
    assert h[(119, 1)] == "ALEPH" and h[(119, 9)] == "BETH" and h[(119, 17)] == "GIMEL", h
    assert h[(119, 25)] == "DALETH.", h
    tail = "To the chief singer on my stringed instruments."

    def fixture(hab_tail=tail):
        return tsv(
            (19, 1, 1, "To the chief Musician, for David's sons. As the hart panteth"),
            (19, 2, 1, "For the Chief Musician. A Psalm by David. Why do the nations rage?"),
            (19, 3, 3, "A Psalm of David. Many say of my soul"),
            (19, 119, 1, "ALEPH Blessed are those"),
            (19, 119, 8, "I will observe your statutes. Don\u2019t utterly forsake me. BETH"),
            (19, 119, 9, "How can a young man keep his way pure?"),
            (19, 119, 16, "I will not forget your word. GIMEL"),
            (19, 119, 17, "Do good to your servant."),
            (19, 119, 25, "DALETH. My soul cleaveth to the dust"),
            (35, 3, 19, "He will make me walk. " + hab_tail),
        )

    old = fixture()
    new, edits = strip_rows(old, h, tail)
    verify(old, new, edits)
    got = [l.split("\t")[3] for l in new]
    assert got == ["As the hart panteth", "Why do the nations rage?", "Many say of my soul",
                   "Blessed are those",
                   "I will observe your statutes. Don\u2019t utterly forsake me.",   # BETH stripped from the END of 119:8
                   "How can a young man keep his way pure?",                         # ...and 119:9 untouched
                   "I will not forget your word.", "Do good to your servant.",
                   "My soul cleaveth to the dust", "He will make me walk."], got
    assert sorted(w for _, _, _, w in edits) == ["end", "end", "note", "start", "start", "start", "start", "start"], edits
    assert gzip.decompress(to_gzip(b"x\n")) == b"x\n" and to_gzip(b"x") == to_gzip(b"x")

    # The regression this script shipped with: a trailing label must be FOUND, not skipped. With the
    # label's row removed from the asset there is nowhere to find it, so the run must ABORT.
    no_trailing = [r for r in old if not r.startswith("19\t119\t8\t")]
    raises(lambda: strip_rows(no_trailing, h, tail), "a heading found nowhere was skipped",
           "neither at the start of this verse")

    # A title that is not a prefix aborts and names it; nothing is guessed. Case matters: "HE"
    # must not match the start of a verse that begins "He ..." (no case-blind compare).
    raises(lambda: strip_rows(old, {(1, 1): "A different title."}, tail), "mismatched heading accepted")
    raises(lambda: strip_rows(old, {(1, 9): "No such verse."}, tail), "heading for a missing verse accepted")
    he_old = tsv((19, 119, 32, "for I fear. HE"), (19, 119, 33, "He taught me"), (35, 3, 19, "x. " + tail))
    he_new, _ = strip_rows(he_old, {(119, 33): "HE"}, tail)
    assert [l.split("\t")[3] for l in he_new[:2]] == ["for I fear.", "He taught me"], he_new
    raises(lambda: strip_rows(tsv((19, 119, 33, "He taught me"), (35, 3, 19, "x. " + tail)), {(119, 33): "HE"}, tail),
           "'HE' matched a verse starting 'He' (case-blind compare)")
    raises(lambda: strip_rows(old, {}, "A note that is not there."), "missing Habakkuk note accepted")
    raises(lambda: strip_rows([r for r in old if not r.startswith("35\t")], {}, tail),
           "missing Habakkuk row accepted", "no such row")

    # Ambiguity is refused: heading at the end of the previous verse AND the start of this one.
    amb = tsv((19, 119, 8, "Some verse. BETH"), (19, 119, 9, "BETH How can"), (35, 3, 19, "x. " + tail))
    raises(lambda: strip_rows(amb, {(119, 9): "BETH"}, tail), "ambiguous heading accepted", "refusing to guess")

    # verify() catches an unlisted change, and a bad remainder (here a leading space left behind).
    sneaky = list(new)
    sneaky[7] = sneaky[7].replace("Do good", "Did good")
    raises(lambda: verify(old, sneaky, edits), "verify() missed a row that changed without being listed")
    spacey_old = tsv((19, 1, 1, "Title.  Verse"))
    raises(lambda: verify(spacey_old, tsv((19, 1, 1, " Verse")), [((19, 1, 1), "Title.", 0, "start")]),
           "verify() accepted a leading space", "bad remainder")

    # Parser guards: a heading with no verse after it, and a heading that continues on a second line.
    raises(lambda: headings_from_usfm("\\c 5 \n\\d Orphan title.\n\\c 6 \n\\v 1 Text"), "orphan heading accepted")
    raises(lambda: headings_from_usfm("\\c 5 \n\\d A title that runs\nonto a second line.\n\\v 1 Text"),
           "a continued heading was truncated silently", "continues on the next line")

    # End to end through real zips and real assets, and the ALL-OR-NOTHING write.
    global EXPECTED_HEADINGS
    saved = EXPECTED_HEADINGS
    EXPECTED_HEADINGS = {**saved, "kjv": 7, "web": 7}
    try:
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            web_tail = SOURCES["web"][1]
            for name, ebible_id, rows in (("kjv", "eng-kjv", fixture()), ("web", "engwebp", fixture(web_tail))):
                (d / f"{name}.tsv.gz").write_bytes(to_gzip(("\n".join(rows) + "\n").encode()))
                with zipfile.ZipFile(d / f"{ebible_id}_usfm.zip", "w") as zf:
                    zf.writestr("20-PSA.usfm", usfm)
            kjv_before, web_before = (d / "kjv.tsv.gz").read_bytes(), (d / "web.tsv.gz").read_bytes()

            assert run(d, d, write=False, names=["kjv", "web"]) == 0
            assert (d / "kjv.tsv.gz").read_bytes() == kjv_before, "dry run changed an asset"

            # Corrupt ONE title in web's asset: web aborts, and with --write kjv must NOT be rewritten.
            bad = fixture(web_tail)
            bad[0] = bad[0].replace("Musician", "Musicien")
            (d / "web.tsv.gz").write_bytes(to_gzip(("\n".join(bad) + "\n").encode()))
            web_bad = (d / "web.tsv.gz").read_bytes()
            assert run(d, d, write=True, names=["kjv", "web"]) == 1
            assert (d / "kjv.tsv.gz").read_bytes() == kjv_before, "a failure in web still rewrote kjv"
            assert (d / "web.tsv.gz").read_bytes() == web_bad

            # Malformed / unreadable input is a tidy abort, not a traceback.
            (d / "web.tsv.gz").write_bytes(to_gzip(b"19\t1\tnot-a-number\ttext\n"))
            assert run(d, d, write=False, names=["web"]) == 1
            (d / "web.tsv.gz").write_bytes(b"this is not gzip")
            assert run(d, d, write=False, names=["web"]) == 1

            # The heading-count guard fires when upstream gains or loses a heading.
            (d / "web.tsv.gz").write_bytes(web_before)
            EXPECTED_HEADINGS = {**saved, "kjv": 7, "web": 99}
            assert run(d, d, write=False, names=["web"]) == 1
            EXPECTED_HEADINGS = {**saved, "kjv": 7, "web": 7}

            # Both good: written, and the rewrite is what the pure functions computed.
            assert run(d, d, write=True, names=["kjv", "web"]) == 0
            rows = gzip.decompress((d / "web.tsv.gz").read_bytes()).decode().split("\n")
            assert rows[-1] == "" and rows[0].endswith("\tAs the hart panteth"), rows
            assert rows[4].endswith("forsake me."), rows[4]
            assert not list(d.glob("*.tmp")), "left a temp file behind"
    finally:
        EXPECTED_HEADINGS = saved
    print("strip_bible_headings self-test: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
