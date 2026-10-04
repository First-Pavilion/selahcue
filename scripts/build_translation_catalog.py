#!/usr/bin/env python3
"""Build the SelahCue translation mirror: curated eBible.org USFM -> pinned, normalised Bible assets.

The app downloads extra Bibles from a SelahCue-hosted mirror, not from eBible.org. eBible re-releases
its files often (the WEB zip changed the day before this was written), so a per-file SHA-256 pin on
eBible's own URLs would break on every release. This script is the build half of the mirror: it turns
the USFM of a curated allowlist into byte-reproducible `<code>.tsv.gz` assets in the SAME row format
as the bundled Bibles (`book<TAB>chapter<TAB>verse<TAB>text`, books 1..66) plus a `catalog.json` that
pins every asset by SHA-256. Publishing the files is a separate, owner-run step (17tnw2b2jfy, A1).

WHY USFM DIRECTLY, AND WHY IT IS STRICT. The bundled Bibles came from eBible's VPL export, which
flattens every heading into a verse line; 17tnw2b2g7q then had to strip psalm titles and Psalm 119
letter labels back out using USFM as the oracle. Reading USFM directly avoids the problem at the
source: headings (`\\d`, `\\qa`, `\\s`, ...) are not verse text and are never emitted. The converter
still REFUSES rather than guesses, and names the verse: an unknown line marker, an unknown INLINE marker
(stripping it would put its content into the verse), a footnote that is not closed (it would delete every
verse up to a later note's closer), a verse bridge (`\\v 3-4`), text outside a verse, a missing or extra
chapter, or leftover markup aborts the whole run. A numbered verse with no text (Acts 8:37 in a text that
omits it) is the one thing it does NOT refuse: it is left out and counted in the catalogue's
`omitted_verses`, exactly as the shipped Bibles leave those verses out.

The spacing USFM puts around a footnote is not text: `egg \\f ...\\f*?` reads "egg?" and the `\\fm ,\\fm*`
separator Biblica puts between two footnote callers is dropped with the notes.

NORMALISATION (the same rules the bundled Bibles satisfy -- see selahcue-scripture's
tests/test_scripture_data.rs): no `[ ] \u00b6 *`; no psalm title or Psalm 119 letter label in any verse;
Habakkuk 3:19 without its musical note; numbered verses that read like titles (Hab 3:1, Isa 38:9,
Song 1:1) stay; canonical Protestant numbering 1..66 with deuterocanon, intros and glossaries
dropped. Text is also NFC-normalised so combining marks (Yoruba and Igbo dot-below letters with tone
marks) have one stable form for search and rendering.

THE LICENCE GATE. Each allowlist entry names a licence from the allowlist's own registry. The build
fails unless ALL of these hold: the licence is marked `permitted`; eBible's catalogue row says
`Redistributable=True` and `downloadable=True`; the row's Copyright column EQUALS the entry's
`expect_copyright` (exactly, so any change to eBible's line stops the run to be looked at); the licence
page inside eBible's own zip (`copr.htm`) still contains every phrase in the entry's `licence_text` and
none of "all rights reserved", "non-commercial", "no derivatives", "not public domain"; and, with
`--require-cleared` (the publish run), every SELECTED entry's `legal_review` is `cleared`. What the gate
does not do: decide a licence is acceptable. `permitted` and `legal_review` are committed human decisions
(A6, 17tnw2b2jg3); the gate only stops the text drifting away from what they were made about.

    python3 scripts/build_translation_catalog.py --work-dir DIR --out-dir NEWDIR [--only BSB ...] [--refresh]
    python3 scripts/build_translation_catalog.py --work-dir DIR --verify-bundled
    python3 scripts/build_translation_catalog.py --self-test

`--work-dir` caches the downloaded `*_usfm.zip` files and eBible's `translations.csv`; an existing file
is used as is (no network), a missing one is fetched, `--refresh` fetches again the catalogue and the zips
of the SELECTED translations, and `--require-cleared` does the same (unless `--offline`) so a publish run
never gates on, or builds from, yesterday's files. `--out-dir` must be absent or empty: a catalogue written beside an earlier run's
files would list some and leave the rest (maybe legal-pending text) in the folder about to be uploaded.
`--verify-bundled` is the positive control: it converts the USFM of the five bundled Bibles and compares
the result with the shipped assets, which proves the converter itself and not just the new translations;
it does NOT download, so put the five zips in `--work-dir` first (it says which are missing). Not run by
`make ci`: it needs the network. `--self-test` needs none and is what `make ci` runs.

Depends on `strip_bible_headings.py` (same folder) for `Mismatch`, `to_gzip` and the bundled-Bible
sources, so it is meant to be run as a script (`scripts/` is then `sys.path[0]`), as `make` and CI do.

Output is byte-reproducible for a given zlib (the gzip header carries no timestamp or filename);
`catalog.json` contains no timestamps. If bytes ever differ on another machine's zlib, compare the
DECOMPRESSED TSV, not the sha.
"""
import argparse
import contextlib
import csv
import gzip
import hashlib
import html
import io
import json
import pathlib
import re
import struct
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib
from unittest import mock

import strip_bible_headings as sbh
from strip_bible_headings import Mismatch

ROOT = pathlib.Path(__file__).resolve().parent.parent
ALLOWLIST = pathlib.Path(__file__).resolve().parent / "translation_allowlist.json"
BUNDLED_ASSETS = ROOT / "implementation/desktop/crates/selahcue-scripture/assets"
EBIBLE = "https://ebible.org/Scriptures"
CATALOG_CSV_URL = f"{EBIBLE}/translations.csv"

# USFM book ids in canonical order; the index + 1 is the book number the TSV assets use.
CANON = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM "
         "EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP "
         "COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
# Chapters per book, Protestant canon (the numbering every bundled translation uses).
CHAPTERS = [50, 40, 27, 36, 34, 24, 21, 4, 31, 24, 22, 25, 29, 36, 10, 13, 10, 42, 150, 31, 12, 8, 66, 52, 5,
            48, 12, 14, 3, 9, 1, 4, 7, 3, 3, 3, 2, 14, 4,
            28, 16, 24, 21, 28, 16, 16, 13, 6, 6, 4, 4, 5, 3, 6, 4, 3, 1, 13, 5, 5, 3, 5, 1, 1, 1, 22]
assert len(CANON) == len(CHAPTERS) == 66 and sum(CHAPTERS) == 1189
OT_BOOKS = 39
PSALMS, HABAKKUK = 19, 35

# The wire/UI code limit of selahcue-core (providers.rs MAX_TRANSLATION_CODE_LEN) and the codes the
# five bundled Bibles already own. A mirrored translation may collide with neither.
CODE_RE = re.compile(r"^[A-Z][A-Z0-9-]{1,15}$")
EBIBLE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,40}$")
BUNDLED_CODES = {"KJV", "WEB", "ASV", "WEBBE", "DBY"}
LEGAL_REVIEW = {"cleared", "pending"}

# Bounds on untrusted input: a zip from the network is data, not something to trust. The caps are on
# bytes ACTUALLY read, never on a size the zip declares about itself (see read_usfm_zip).
MAX_ZIP_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 24 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
# A Bible zip holds about 70 files. ZipFile() has already parsed the whole directory before this cap is checked (200,000
# entries cost 112 MB), so the cap only refuses early; what bounds a hostile directory is the 64 MiB download cap.
MAX_MEMBERS = 500
USER_AGENT = "selahcue-translation-mirror/1 (+https://selahcue.app)"

# --- USFM line markers -------------------------------------------------------------------------
_LINE_MARKER = re.compile(r"\\(\+?[A-Za-z][A-Za-z0-9]*)\*?")
# Lines that are NOT verse text: identification, titles, intro material, headings, references, the
# speaker/descriptive-title/acrostic lines. Their continuation lines (no marker) are skipped with them.
_SKIP = re.compile(
    r"(?:id|ide|h\d?|toc\d|mt\d?|mte\d?|imt\d?|is\d?|ip|ipi|ipq|ipr|im|imi|imq|ib|iq\d?|ili\d?|iot|io\d?|ior|iex|ie"
    r"|periph|rem|sts|s\d?|ms\d?|mr|r|sr|d|sp|cl|cp|cd|qa|b|lit)")
# Paragraph / poetry / list / table markers whose line carries verse text.
_TEXT = re.compile(
    r"(?:p|m|mi|nb|cls|pi\d?|pc|pr|pm|pmo|pmc|pmr|po|ph\d?|q\d?|qr|qc|qm\d?|qd|li\d?|lim\d?|lh|lf"
    r"|tr|tc\d|tcr\d|th\d|thr\d)")
# Character markers that may START a line and continue the current paragraph.
_CHARS = {"w", "wj", "add", "nd", "tl", "qs", "it", "bd", "bdit", "em", "sc", "k", "bk", "pn", "ord", "dc",
          "sig", "no", "ndx", "wg", "wh", "wa"}
# Notes and alternate numbering, which may span lines: dropped whole before any line is read. Found with
# str.find, not a DOTALL lazy regex: `\\f .*?\\f\*` rescans to the end of the file from EVERY unclosed
# opener (140 KB of openers took 5 s, and a 24 MiB member would never return), so an unterminated note
# is refused outright instead.
# `\fm ,\fm*` is the separator mark Biblica's texts put BETWEEN consecutive footnote callers (a comma): apparatus,
# not text. Kept as verse text it doubled the comma in four Hausa verses.
_NOTE_OPEN = re.compile(r"\\(f|fe|ef|fm|x|ex|va|vp|ca|fig)\s")
_NOTE_BREAK = re.compile(r"\\(?:v|c)\s")  # a note never contains a verse or chapter marker: if it seems to, it is unclosed
# Punctuation that closes a phrase. A note sits AFTER the word and BEFORE this, with the USFM spacing around it
# (`egg \f ...\f*?`); dropping the note must not leave the reader "egg ?".
_CLOSING_PUNCT = ",;:.!?)\u201d\u2019"
# The quotes are only closing when no letter or digit follows: Hausa begins words with U+2019 (`\u2019yan`, `\u2019yar`), so
# "Yahuda,\f ..\f* \u2019yan" must keep its space. (A plain `?` or `.` is closing whatever follows.)
_QUOTES_THAT_OPEN_WORDS = "\u201d\u2019"
_MARKER_AHEAD = re.compile(r"[ \t]*\\\+?[A-Za-z][A-Za-z0-9]*(?:\*|[ \t]?)")  # spaces, then one inline marker
_SPACES = re.compile(r"[ \t]*")
_VERSE_TOKEN = re.compile(r"\\v\s+(\S+)\s*")
# `\w word|strong="H1"\w*` -> `word`. USFM defines ONE delimiter space after the marker; `\s+` here let the
# lazy class that follows also match whitespace, which is quadratic on an unclosed `\w` (10,000 spaces took a
# second, 40,000 took sixteen).
_WORD = re.compile(r"\\\+?w\s([^|\\]*?)(?:\|[^\\]*)?\\\+?w\*")
_ASCII_WS = re.compile(r"[ \t\r\n\f\v]+")
# Any inline marker still in the text after notes and `\w` are gone: a closer (`\add*`) or an opener and its one
# delimiter space (`\add `). Only the markers in _CHARS may remain; anything else (`\fm` outside a note, `\rq`,
# `\xt`, `\s1`, `\d` mid-line, a typo) is refused, because stripping it would put its CONTENT into the verse.
_INLINE_MARKER = re.compile(r"\\\+?([A-Za-z][A-Za-z0-9]*)(\*|[ \t]?)")
# A table row's cell markers may sit mid-line (`\tr \tc1 a \tc2 b`) as well as start a line; the cells are verse text.
_TABLE_CELL = re.compile(r"tr|tc\d|tcr\d|th\d|thr\d")
# What Psalm 119's `\qc` letter label looks like once cleaned: a Hebrew letter, then one to three Latin words ("\u05d0 ALEPH.").
# The Hebrew letter is REQUIRED: without it, any short line ("Amen.", "forever.") would pass as a label and vanish.
_LABEL_SHAPE = re.compile(r"[\u0590-\u05ff]+ [A-Za-z]+(?: [A-Za-z]+){0,2}\.?")
# Where the headings that the parser skips are recorded, to prove none of them fused into a verse.
_ORACLE_MARKERS = {"d", "qa"}

ACROSTIC_LETTERS = {
    "ALEPH", "BETH", "GIMEL", "DALETH", "HE", "VAV", "VAU", "ZAIN", "ZAYIN", "HETH", "CHETH", "TETH", "YOD",
    "YODH", "KAPF", "CAPH", "KAPH", "LAMED", "LAMEDH", "MEM", "NUN", "SAMEKH", "SAMECH", "AYIN", "AIN", "PE",
    "TZADHE", "TZADE", "TSADDI", "TSADHE", "QOPH", "KOPH", "RESH", "SHIN", "SIN", "TAV", "TAU"}
# English psalm-title openers the bundled-Bible corpus test also uses: a net on top of the heading
# oracle, which is language-independent but only knows the headings the USFM itself marked.
TITLE_OPENERS = (
    "To the chief", "For the chief", "For the Chief", "For the music", "For the Director", "A Psalm", "A Song",
    "A song", "A Prayer", "A Contemplation", "A contemplation", "A contemplative", "A meditation", "A Poem",
    "A praise psalm", "A teaching", "A Miktam", "A Shiggaion", "Maschil", "Michtam", "Miktam", "Shiggaion",
    "An instruction", "By David", "By Solomon", "For Solomon", "For Jeduthun", "Of David",
    "Of the sons of Korah", "David\u2019s Psalm", "Psalm of David")
# Markup residue and control characters (NUL and the like): neither belongs in a verse.
_RESIDUE = re.compile(r"[\[\]\u00b6*|\\\x00-\x1f\x7f]")


# --- the converter -----------------------------------------------------------------------------
def _closes_phrase(text, i):
    """Whether text[i] is closing punctuation that a note's leading space must not stand in front of."""
    if i >= len(text) or text[i] not in _CLOSING_PUNCT:
        return False
    if text[i] in _QUOTES_THAT_OPEN_WORDS:
        following = text[i + 1:i + 2]
        return not (following and following.isalnum())
    return True


def strip_notes(text):
    """Remove every footnote and cross-reference (`\\f ... \\f*`, `\\x ... \\x*`, ...). Linear in the text.

    A note that is not closed raises Mismatch. Two shapes, both refused: no closer anywhere (dropping "to the
    end of the file" would delete verses), and a closer that belongs to a LATER note, which shows up as a verse
    or chapter marker, or another opener of the same kind, inside the span (dropping it would delete every verse
    in between). Keeping either would put note text into a verse. Each is a guess, so neither happens.

    The spacing USFM puts before a note is not text: when a closing punctuation mark follows the note, the
    space (and tab) in front of the note goes with it."""
    out, pos = [], 0
    while True:
        m = _NOTE_OPEN.search(text, pos)
        if m is None:
            out.append(text[pos:])
            return "".join(out)
        kind = m.group(1)
        closer = "\\" + kind + "*"
        end = text.find(closer, m.end())
        if end < 0:
            raise Mismatch([f"unterminated \\{kind} note, no {closer} after: {text[m.start():m.start() + 40]!r}"])
        inner = text[m.end():end]
        runs_on = _NOTE_BREAK.search(inner) or re.search(r"\\" + kind + r"\s", inner)
        if runs_on:
            raise Mismatch([f"\\{kind} note at {text[m.start():m.start() + 40]!r} is not closed before "
                            f"{inner[runs_on.start():runs_on.start() + 20]!r}: its {closer} belongs to a later note"])
        out.append(text[pos:m.start()])
        pos = end + len(closer)
        # Look past spaces and inline markers (`\wj* \f ..\f* \wj ?\wj*` is "...\u2019?" in Jesus' words) to the first
        # character that is text. If it closes a phrase, the whitespace on both sides of the note goes.
        # (Index scans, never `text[pos:].lstrip()`: that copies the rest of the text for EVERY note, which is quadratic.)
        ahead = pos
        while True:
            marker = _MARKER_AHEAD.match(text, ahead)
            if marker is None:
                break
            ahead = marker.end()
        ahead = _SPACES.match(text, ahead).end()
        if _closes_phrase(text, ahead):
            while out and not out[-1].rstrip(" \t"):
                out.pop()
            if out:
                out[-1] = out[-1].rstrip(" \t")
            pos = _SPACES.match(text, pos).end()


def clean(text):
    """USFM inline markup -> plain text: notes, `\\w` words, every marker, `[ ] \u00b6 *`, whitespace; NFC.

    The single space after an OPENING marker is USFM's delimiter, not text: `(\\add is\\add* it` reads
    "(is it". sbh.clean_usfm keeps that space (it never mattered for matching VPL-derived rows), so
    reading USFM directly needs its own cleaner or every `(\\add ...` gains a stray space.
    """
    text = strip_notes(text)
    text = _WORD.sub(r"\1", text)

    def known_only(m):
        if m.group(1) not in _CHARS and not _TABLE_CELL.fullmatch(m.group(1)):
            raise Mismatch([f"unknown inline marker \\{m.group(1)} near "
                            f"{m.string[max(0, m.start() - 25):m.end() + 25]!r}: stripping it would put its content "
                            f"into the verse"])
        return ""

    text = _INLINE_MARKER.sub(known_only, text)
    text = text.translate({ord(c): None for c in "[]\u00b6*"})
    # ASCII whitespace only: eBible puts a no-break space between nested quote marks (`\u2019\u00a0\u201d`) so the
    # closing quote cannot wrap onto its own line, and the bundled Bibles keep it.
    return unicodedata.normalize("NFC", _ASCII_WS.sub(" ", text).strip(" "))


def parse_book(usfm, label):
    """One USFM book -> ({(chapter, verse): text}, [(chapter, heading)], [omitted (chapter, verse)]).

    Verses with a number but no text are returned as omitted, not as rows: the shipped Bibles leave
    them out the same way (WEB has 31,103 `\\v` lines and 31,098 rows). Raises Mismatch on anything odd."""
    problems = []

    def bad(msg):
        problems.append(f"{label}: {msg}")

    def tidy(text, where):
        """clean(), but a refusal is recorded against `where` (a chapter or verse) instead of escaping bare."""
        try:
            return clean(text)
        except Mismatch as e:
            for p in e.problems:
                bad(f"{where}: {p}")
            return ""

    verses, headings, parts = {}, [], {}
    chapter, verse, skipping, last_heading = 0, None, False, None
    try:
        usfm = strip_notes(usfm)
    except Mismatch as e:
        raise Mismatch([f"{label}: {p}" for p in e.problems])
    for raw in usfm.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _LINE_MARKER.match(line)
        marker = m.group(1).lstrip("+") if m else None
        if marker == "c":
            cm = re.match(r"\\c\s+(\d+)\s*$", line)
            if not cm or int(cm.group(1)) != chapter + 1:
                bad(f"chapter marker {line[:30]!r} does not follow chapter {chapter}")
                continue
            chapter, verse, skipping, last_heading = chapter + 1, None, False, None
            continue
        # ASV marks Psalm 119's letters with `\qc` (centred poetry), a marker that carries ordinary text
        # elsewhere, so the rule is scoped to Psalm 119, to a line with no verse in it, and to the SHAPE of a
        # label (an optional Hebrew letter and one to three Latin words). The shape is structural on purpose: a
        # list of letter names missed ASV's own spelling "HHETH" and fused it into 119:56. A `\qc` line that is
        # not label-shaped is verse text and falls through to the normal paragraph handling below.
        # A label also sits where a section starts: the verse before it is 8k (or none yet), so it introduces 8k+1.
        if marker == "qc" and label == "PSA" and chapter == 119 and "\\v" not in line and (verse or 0) % 8 == 0:
            rest = tidy(line[m.end():], f"chapter {chapter}")
            if _LABEL_SHAPE.fullmatch(rest):
                skipping, last_heading = True, [chapter, rest]
                headings.append(last_heading)
                continue
        if marker is not None and _SKIP.fullmatch(marker):
            skipping, last_heading = True, None
            if marker in _ORACLE_MARKERS:
                last_heading = [chapter, tidy(line[m.end():], f"chapter {chapter} heading")]
                headings.append(last_heading)
            continue
        if marker == "v":
            body = line
        elif marker is not None and _TEXT.fullmatch(marker):
            body = line[m.end():]
        elif marker is None or marker in _CHARS:
            if skipping:  # a continuation line of the heading that is being skipped
                if last_heading is not None:
                    last_heading[1] = tidy(last_heading[1] + " " + line, f"chapter {chapter} heading")
                continue
            body = line
        else:
            bad(f"unknown line marker \\{marker} at chapter {chapter}: {line[:50]!r}")
            continue
        skipping = False
        if chapter == 0:
            bad(f"text before the first chapter: {line[:50]!r}")
            continue
        pieces = _VERSE_TOKEN.split(body)  # [text, number, text, number, text, ...]
        lead = pieces[0]
        if lead.strip():
            if verse is None:
                bad(f"chapter {chapter}: text outside any verse: {lead.strip()[:50]!r}")
            else:
                parts[(chapter, verse)].append(lead)
        for number, text in zip(pieces[1::2], pieces[2::2]):
            if not re.fullmatch(r"\d+", number):
                bad(f"chapter {chapter}: verse marker {number!r} is not a plain number (a bridge or "
                    f"lettered verse); refusing to guess how to number it")
                verse = None
                continue
            n = int(number)
            if (chapter, n) in parts:
                bad(f"chapter {chapter}: verse {n} appears twice")
            if verse is not None and n <= verse:
                bad(f"chapter {chapter}: verse {n} follows verse {verse}")
            verse = n
            parts[(chapter, n)] = [text]
    omitted = []
    for key, chunks in parts.items():
        text = tidy(" ".join(chunks), f"{key[0]}:{key[1]}")
        if text:
            verses[key] = text
        else:  # a verse the translation deliberately leaves out (Acts 8:37, Luke 17:36 ...): numbered, no text
            omitted.append(key)
    if problems:
        raise Mismatch(problems)
    return verses, [tuple(h) for h in headings], omitted


def _strip_acrostic_label(text):
    """DBY puts Psalm 119's letter inline ("ALEPH. Blessed ..."); eBible's other USFM uses `\\d`/`\\qa`."""
    m = re.match(r"([A-Z]{2,})\.?\s+(\S.*)$", text)
    return m.group(2) if m and m.group(1) in ACROSTIC_LETTERS else text


def _opens_with_title(text):
    for opener in TITLE_OPENERS:
        if text.startswith(opener) and not text[len(opener):len(opener) + 1].isalnum():
            return opener
    return None


def _is_acrostic_label(text):
    first = (text.split() or [""])[0]
    return first.rstrip(".") in ACROSTIC_LETTERS


def _ends_with_acrostic_label(text):
    # ("SIN AND SHIN", WEB's double label, ends in the letter SHIN, so the last word covers it.)
    last = (text.split() or [""])[-1]
    return last.rstrip(".") in ACROSTIC_LETTERS


def _refuse_too_many_members(zip_path, members):
    if len(members) > MAX_MEMBERS:
        raise Mismatch([f"{zip_path}: {len(members)} members, more than the {MAX_MEMBERS} cap; refusing a possible zip bomb"])


def read_usfm_zip(zip_path):
    """{book number: usfm text} for the 66 canonical books in an eBible USFM zip, bounded and read-only."""
    problems, books = [], {}
    try:
        zf = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as e:
        raise Mismatch([f"{zip_path}: not a readable zip ({type(e).__name__}: {e})"])
    with zf:
        everything = zf.infolist()
        _refuse_too_many_members(zip_path, everything)
        # A macOS `__MACOSX/._x.usfm` resource-fork sidecar is not a book; it would otherwise fail as "not UTF-8".
        infos = [i for i in everything if i.filename.lower().endswith(".usfm")
                 and not i.filename.startswith("__MACOSX/") and not pathlib.PurePosixPath(i.filename).name.startswith("._")]
        # The size a member DECLARES is the zip author's claim. It is checked first only to refuse an obvious
        # bomb cheaply; the cap that actually bounds memory is on the bytes read below, because
        # ZipFile.read() would otherwise inflate up to 1 GiB per call before truncating to the claim.
        if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES or any(i.file_size > MAX_MEMBER_BYTES for i in infos):
            raise Mismatch([f"{zip_path}: USFM members declare more than the size caps ({MAX_MEMBER_BYTES} each, "
                            f"{MAX_TOTAL_BYTES} total); refusing a possible zip bomb"])
        total = 0
        for info in infos:
            try:
                with zf.open(info) as member:
                    raw = member.read(MAX_MEMBER_BYTES + 1)  # bounded: never inflates past the cap
            except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, OSError) as e:
                raise Mismatch([f"{zip_path}: cannot read {info.filename!r} ({type(e).__name__}: {e})"])
            total += len(raw)
            if len(raw) > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                raise Mismatch([f"{zip_path}: {info.filename!r} inflates past the size caps ({MAX_MEMBER_BYTES} each, "
                                f"{MAX_TOTAL_BYTES} total) whatever it declares; refusing a zip bomb"])
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError as e:
                raise Mismatch([f"{zip_path}: {info.filename!r} is not UTF-8 ({e.reason} at byte {e.start})"])
            m = re.search(r"^\\id\s+(\w{3})", text, re.M)
            code = m.group(1) if m else None
            if code not in CANON:
                continue  # front matter, glossary, deuterocanon: not part of the canon the app numbers
            n = CANON.index(code) + 1
            if n in books:
                problems.append(f"book {code} appears in two files")
            books[n] = text
    missing = [CANON[n - 1] for n in range(1, 67) if n not in books]
    if missing:
        problems.append(f"{zip_path}: missing canonical books {missing}")
    if problems:
        raise Mismatch(problems)
    return books


def convert(zip_path, spec):
    """USFM zip + allowlist entry -> (sorted [(book, chapter, verse, text)], [omitted (book, chapter, verse)]).

    Checks everything or raises Mismatch naming every problem."""
    books = read_usfm_zip(zip_path)
    rows, headings, problems, omitted = [], {}, [], []
    for n in range(1, 67):
        label = CANON[n - 1]
        try:
            verses, heads, gaps = parse_book(books[n], label)
        except Mismatch as e:
            problems += e.problems
            continue
        omitted += [(n, c, v) for c, v in gaps]
        got = sorted({c for c, _ in verses})
        if got != list(range(1, CHAPTERS[n - 1] + 1)):
            problems.append(f"{label}: chapters are {got[:3]}..{got[-3:]} ({len(got)}), expected 1..{CHAPTERS[n - 1]}")
        for c in got:
            if min(v for cc, v in verses if cc == c) != 1:
                problems.append(f"{label} {c}: does not start at verse 1")
        for (c, v), text in sorted(verses.items()):
            rows.append([n, c, v, text])
        for c, h in heads:
            headings.setdefault((n, c), []).append(h)
    if problems:
        raise Mismatch(problems)

    by_key = {(b, c, v): row for row in rows for b, c, v in [row[:3]]}
    # Psalm 119: DBY's inline letter labels, then proof that no letter survives at either end of a verse.
    for key, row in by_key.items():
        if key[0] == PSALMS and key[1] == 119 and (key[2] - 1) % 8 == 0:
            row[3] = _strip_acrostic_label(row[3])
    # Habakkuk 3:19's musical note is tagged differently in every USFM. Where it is fused into the verse
    # (KJV, WEB, WEBBE, DBY) the entry names it and it is cut here; where it is its own heading line
    # (ASV, BSB, the Biblica texts) it never reaches the verse. A note that is fused but NOT named is
    # caught below by the "stringed instruments" check, so naming it is never optional for English.
    note = spec.get("hab_3_19_note")
    row = by_key.get((HABAKKUK, 3, 19))
    if note and row is not None and row[3].endswith(" " + note):
        row[3] = row[3][:-len(note) - 1]

    eng = spec.get("language") == "eng"
    for (b, c, v), (_, _, _, text) in sorted(by_key.items()):
        where = f"{CANON[b - 1]} {c}:{v}"
        if not text or text != text.strip() or _RESIDUE.search(text):
            problems.append(f"{where}: empty, untrimmed or carries markup residue: {text[:60]!r}")
        for h in headings.get((b, c), []):
            if len(h) >= 3 and (text == h or text.startswith(h + " ") or text.endswith(" " + h)):
                problems.append(f"{where}: heading {h!r} fused into the verse text")
        if b == PSALMS and v == 1 and eng and _opens_with_title(text):
            problems.append(f"{where}: opens with a psalm title ({_opens_with_title(text)!r}): {text[:60]!r}")
        if b == PSALMS and c == 119 and (_is_acrostic_label(text) or _ends_with_acrostic_label(text)):
            problems.append(f"{where}: still carries a Psalm 119 letter label: {text[:40]!r}..{text[-20:]!r}")
        if (b, c, v) == (HABAKKUK, 3, 19) and eng and "stringed instruments" in text:
            problems.append(f"{where}: still carries the musical note: {text[-60:]!r}")
    if sum(1 for k in by_key if k[:2] == (PSALMS, 119)) != 176:
        problems.append("Psalm 119 must keep 176 verses")
    ot = sum(1 for k in by_key if k[0] <= OT_BOOKS)
    nt = len(by_key) - ot
    pinned = spec.get("verses") or {}
    if (ot, nt) != (pinned.get("ot"), pinned.get("nt")):
        problems.append(f"verse counts are OT {ot} / NT {nt}, the allowlist pins {pinned.get('ot')} / "
                        f"{pinned.get('nt')} (eBible changed the text, or the pin is wrong: look, then re-pin)")
    if problems:
        raise Mismatch(problems)
    return sorted(by_key.values()), sorted(omitted)


def tsv_bytes(rows):
    return "".join("\t".join(map(str, r)) + "\n" for r in rows).encode("utf-8")


# --- allowlist, gates, catalogue ---------------------------------------------------------------
def load_allowlist(path):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise Mismatch([f"{path}: unsupported allowlist schema {data.get('schema')!r}"])
    return data


def load_catalog_csv(path):
    """eBible's `translations.csv` as {translationId: row}. A corrupt or hostile file is a refusal, not a traceback."""
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8-sig")  # eBible's file starts with a UTF-8 BOM
        return {r["translationId"]: r for r in csv.DictReader(io.StringIO(text))}
    except (OSError, UnicodeDecodeError, csv.Error, KeyError) as e:
        raise Mismatch([f"{path}: not a usable eBible catalogue ({type(e).__name__}: {e})"])


def non_ascii_characters(text):
    """The distinct non-ASCII characters in `text`, as hex code points. The two scripts must have none (see self_test)."""
    return sorted({hex(ord(c)) for c in text if ord(c) > 127})


def invisible_characters(text):
    """Characters a reviewer cannot see in a diff: format and control characters (bidirectional marks, a BOM, NUL), line
    and paragraph separators, and every space except the plain one. ("Trojan Source": hiding code in such characters.)"""
    hidden = []
    for c in text:
        kind = unicodedata.category(c)
        if (kind in ("Cf", "Cc", "Zl", "Zp") and c not in "\n\t") or (kind == "Zs" and c != " "):
            hidden.append(hex(ord(c)))
    return sorted(set(hidden))


def _squash(text):
    """Casefold and collapse whitespace, so a licence phrase compares the same however the page wrapped it."""
    return " ".join(text.casefold().split())


def gate(allow, rows, require_cleared, only=None):
    """The licence gate over the catalogue. Returns nothing; raises Mismatch naming EVERY entry that fails and why.

    Everything is checked for every entry (a bad allowlist is a bad allowlist) EXCEPT `--require-cleared`, which
    applies only to the entries being built (`only`; None means all), so a cleared translation can be published
    while another is still waiting on legal review."""
    problems, seen = [], set()
    licences = allow.get("licences", {})
    excluded = {e["ebible_id"] for e in allow.get("excluded", [])}
    for spec in allow["translations"]:
        code = spec.get("code", "?")
        why = []
        if spec.get("ebible_id") in excluded:
            why.append("is on the allowlist's own excluded list")
        if not CODE_RE.fullmatch(code):  # fullmatch: `$` alone accepts a trailing newline ("KJV\n" passed every gate)
            why.append("code must match ^[A-Z][A-Z0-9-]{1,15}$")
        if code in BUNDLED_CODES:
            why.append("code collides with a bundled translation")
        if code in seen:
            why.append("duplicate code")
        seen.add(code)
        if not (isinstance(spec.get("ebible_id"), str) and EBIBLE_ID_RE.fullmatch(spec["ebible_id"])):
            why.append("ebible_id is not a plain identifier")
        lic = licences.get(spec.get("licence"))
        if lic is None:
            why.append(f"licence {spec.get('licence')!r} is not in the allowlist's registry")
        elif not lic.get("permitted"):
            why.append(f"licence {spec['licence']!r} is not permitted")
        if spec.get("legal_review") not in LEGAL_REVIEW:
            why.append("legal_review must be 'cleared' or 'pending'")
        elif require_cleared and (only is None or code in only) and spec["legal_review"] != "cleared":
            why.append("legal_review is still pending (--require-cleared)")
        phrases = spec.get("licence_text")
        if not (isinstance(phrases, list) and phrases and all(isinstance(p, str) and p.strip() for p in phrases)):
            why.append("has no licence_text: the phrases that must appear in the licence page inside eBible's zip")
        row = rows.get(spec.get("ebible_id"))
        if row is None:
            why.append("not in eBible's catalogue")
        else:
            if row["Redistributable"] != "True":
                why.append("eBible does not mark it Redistributable")
            if row["downloadable"] != "True":
                why.append("eBible does not mark it downloadable")
            if row["languageCode"] != spec.get("language"):
                why.append(f"eBible language is {row['languageCode']!r}, the entry says {spec.get('language')!r}")
            # EXACT, not a substring: "public domain" is also inside "not public domain", and "Biblica, Inc." names the
            # rights holder, not the licence. Any change to eBible's copyright line stops the run to be looked at.
            expected = spec.get("expect_copyright")
            if not isinstance(expected, str) or not expected.strip():
                why.append("has no expect_copyright (the exact copyright line eBible shows today)")
            elif _squash(expected) != _squash(row["Copyright"]):
                why.append(f"eBible's copyright line is now {row['Copyright']!r}, the entry expects {expected!r}")
        if why:
            problems.append(f"{code}: " + "; ".join(why))
    if problems:
        raise Mismatch(problems)


# Phrases that mean the text is NOT freely redistributable. If one appears in the licence page of a translation the
# allowlist calls free, the run stops: the entry is wrong or the licence changed. These are ENGLISH words, so on a
# Yoruba, Igbo or Hausa page the real protection is the required phrase (the licence's own name, which is English).
_FORBIDDEN_LICENCE_TEXT = ("all rights reserved", "noncommercial", "non-commercial", "noderivative", "no derivative",
                           "noderivs", "no derivs", "by-nc", "not public domain")
MAX_LICENCE_PAGE_BYTES = 1024 * 1024
# `<` followed by anything but `<` or `>`, up to `>`: linear. (`<[^>]+>` rescans to the end of the page from every `<`;
# 160,000 of them took 6 s and a 1 MiB page would take minutes.)
_HTML_TAG = re.compile(r"<[^<>]*>")


def licence_page_texts(zip_path):
    """The words of `copr.htm` inside eBible's zip, casefolded, in TWO forms, or None if the zip has no such page.

    Tags become a space in one form and nothing in the other, so a phrase a tag splits ("Non-<b>commercial</b>")
    is seen in one of them, and a phrase two block elements would otherwise glue together is seen in the other."""
    with zipfile.ZipFile(zip_path) as zf:
        everything = zf.infolist()
        _refuse_too_many_members(zip_path, everything)
        info = next((i for i in everything if pathlib.PurePosixPath(i.filename).name.lower() == "copr.htm"), None)
        if info is None:
            return None
        with zf.open(info) as page:
            raw = page.read(MAX_LICENCE_PAGE_BYTES + 1)
    if len(raw) > MAX_LICENCE_PAGE_BYTES:
        raise Mismatch([f"{zip_path}: copr.htm is larger than {MAX_LICENCE_PAGE_BYTES} bytes"])
    forms = []
    for glue in (" ", ""):
        text = html.unescape(_HTML_TAG.sub(glue, raw.decode("utf-8", "replace")))
        # Invisible direction marks (U+202A and friends) sit inside some licence names ("4\u202a.0"); drop them.
        forms.append(_squash("".join(c for c in text if unicodedata.category(c) != "Cf")))
    return forms


def check_licence_text(zip_path, spec):
    """Prove the licence page inside eBible's own zip still says what the allowlist entry relies on.

    A required phrase may appear in either form of the page; a forbidden one in EITHER form stops the run."""
    try:
        forms = licence_page_texts(zip_path)
    except (OSError, zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError) as e:
        raise Mismatch([f"{zip_path}: cannot read the licence page ({type(e).__name__}: {e})"])
    if forms is None:
        raise Mismatch([f"{zip_path}: no copr.htm, so the licence cannot be confirmed"])
    problems = [f"the licence page no longer contains {p!r}" for p in spec["licence_text"]
                if not any(_squash(p) in form for form in forms)]
    problems += [f"the licence page contains {p!r}" for p in _FORBIDDEN_LICENCE_TEXT if any(p in form for form in forms)]
    if problems:
        raise Mismatch(problems)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_entry(spec, row, licence, zip_path, rows, omitted, gz):
    ot = sum(1 for r in rows if r[0] <= OT_BOOKS)
    return {
        "code": spec["code"],
        "name": spec["name"],
        "language": spec["language"],
        "language_name": spec.get("language_name", spec["language"]),
        "file_name": spec["code"].lower() + ".tsv.gz",
        "size_bytes": len(gz),
        "sha256": hashlib.sha256(gz).hexdigest(),
        "verses": {"ot": ot, "nt": len(rows) - ot},
        "omitted_verses": len(omitted),
        "licence": {"id": spec["licence"], "name": licence["name"], "summary": licence["summary"],
                    "url": licence.get("url"), "attribution_required": licence["attribution_required"],
                    "share_alike": licence["share_alike"]},
        "attribution": spec.get("attribution"),
        "trademark_note": spec.get("trademark_note"),
        "modifications": spec.get("modifications"),
        "legal_review": spec["legal_review"],
        "source": {"ebible_id": spec["ebible_id"], "url": f"{EBIBLE}/{spec['ebible_id']}_usfm.zip",
                   "title": row["title"], "copyright": row["Copyright"], "ebible_update_date": row["UpdateDate"],
                   "usfm_zip_sha256": sha256_file(zip_path)},
    }


class _HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """The stdlib follows a redirect to http:// (or ftp://); a download that starts on HTTPS must stay on it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise urllib.error.HTTPError(newurl, code, f"refusing a redirect to a non-HTTPS URL: {newurl}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpsOnlyRedirects)


def fetch(url, dest, opener=None, max_bytes=MAX_ZIP_BYTES):
    """Download `url` to `dest` through a .part file with a hard size cap; never leaves a partial file.

    A `.part` that already exists (a crashed run, or a planted symlink) is removed first, never followed: the new one is
    created exclusively. The timeout is per socket operation, so a server that trickles bytes is bounded by the size cap
    and not by the clock (accepted: this is an owner-run build, not a service)."""
    part = dest.with_suffix(dest.suffix + ".part")
    opener = opener or _OPENER.open
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        total = 0
        with contextlib.suppress(OSError):
            part.unlink()
        with opener(req, timeout=60) as resp, open(part, "xb") as out:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise Mismatch([f"{url}: larger than the {max_bytes}-byte cap; aborting the download"])
                out.write(chunk)
        part.replace(dest)
    except (OSError, ValueError) as e:
        raise Mismatch([f"could not download {url} ({type(e).__name__}: {e})"])
    finally:
        with contextlib.suppress(OSError):
            part.unlink()


def ensure(work, name, url, offline, opener, refresh=False):
    """The cached file `work/name`, fetched when it is missing or `refresh` is set. Never touches the network offline."""
    path = work / name
    if refresh or not path.is_file():
        if offline:
            raise Mismatch([f"{path} is missing or must be refreshed, and --offline was given"])
        fetch(url, path, opener)
    return path


def build(allow, work, out, only=None, require_cleared=False, base_url=None, offline=False,
          opener=None, refresh=False):
    """The whole job. Everything is computed before any file is written; a failure writes nothing.

    `out` must be absent or empty: a catalogue written beside files from an earlier run would list some of them
    and leave the rest (possibly legal-pending text) lying in the folder an owner is about to upload."""
    try:
        used = out.exists() and (not out.is_dir() or any(out.iterdir()))
    except OSError as e:  # e.g. a folder this user cannot read
        raise Mismatch([f"--out-dir {out} cannot be inspected ({type(e).__name__}: {e})"])
    if used:
        raise Mismatch([f"--out-dir {out} must be absent or an empty directory (build into a new folder)"])
    work.mkdir(parents=True, exist_ok=True)
    # A publish run gates on eBible's catalogue AND builds from eBible's files as they are NOW, never from copies cached
    # on an earlier day: the licence page the gate reads and the bytes that get published come out of the same zip.
    fresh = refresh or (require_cleared and not offline)
    csv_path = ensure(work, "translations.csv", CATALOG_CSV_URL, offline, opener, refresh=fresh)
    rows_by_id = load_catalog_csv(csv_path)
    gate(allow, rows_by_id, require_cleared, set(only) if only else None)
    specs = [s for s in allow["translations"] if not only or s["code"] in only]
    if only and len(specs) != len(set(only)):
        raise Mismatch([f"--only names codes that are not in the allowlist: {sorted(set(only) - {s['code'] for s in specs})}"])
    outputs, entries, problems = {}, [], []
    for spec in specs:
        try:
            zip_path = ensure(work, f"{spec['ebible_id']}_usfm.zip", f"{EBIBLE}/{spec['ebible_id']}_usfm.zip",
                              offline, opener, refresh=fresh)
            check_licence_text(zip_path, spec)
            rows, omitted = convert(zip_path, spec)
        except Mismatch as e:
            problems += [f"{spec['code']}: {p}" for p in e.problems[:20]]
            if len(e.problems) > 20:
                problems.append(f"{spec['code']}: ... and {len(e.problems) - 20} more")
            continue
        gz = sbh.to_gzip(tsv_bytes(rows))
        outputs[spec["code"].lower() + ".tsv.gz"] = gz
        entries.append(build_entry(spec, rows_by_id[spec["ebible_id"]], allow["licences"][spec["licence"]],
                                   zip_path, rows, omitted, gz))
    if problems:
        raise Mismatch(problems)
    catalog = {"schema": 1, "base_url": base_url, "translations_csv_sha256": sha256_file(csv_path),
               "translations": sorted(entries, key=lambda e: e["code"])}
    outputs["catalog.json"] = (json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    write_all(out, outputs)
    return catalog


def write_all(out, files):
    """Stage every file, then rename: a failure while staging removes what was staged and changes nothing."""
    staged = []
    try:
        out.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            tmp = out / (name + ".tmp")
            # Created exclusively (a pre-planted file or symlink there is an error, never followed or overwritten), and
            # only a file THIS call created is ever removed on failure.
            with open(tmp, "xb") as staging:
                staged.append(tmp)
                staging.write(data)
    except OSError as e:
        for tmp in staged:
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise Mismatch([f"could not stage the output ({type(e).__name__}: {e}); nothing was written"])
    for tmp in staged:
        tmp.replace(tmp.with_name(tmp.name[:-4]))


# Where converting eBible's CURRENT USFM is EXPECTED to differ from the shipped assets, as exact
# (book, chapter, verse) sets. The control passes only when the differing rows are exactly these, so a
# new, unexplained difference fails it and a pinned one that stops differing fails it too.
#   upstream: eBible revised the World English Bible after the assets were imported (a living text).
#   speaker:  Song of Solomon `\sp` speaker labels ("Friends", "Beloved", "Lover") that the VPL import
#             fused into the verse text -- the same defect class as 17tnw2b2g7q; USFM does not emit them.
#   selah:    the VPL import put a space in "Lord\u2014 Selah\u2014"; the USFM has none.
#   nbsp:     WEBBE's asset lost the no-break space between nested quote marks that WEB's kept.
_UPSTREAM = {(16, 13, 5), (27, 4, 19), (27, 4, 26), (27, 6, 20), (27, 9, 11), (27, 11, 20), (27, 11, 21),
             (27, 11, 24), (30, 3, 2), (33, 3, 11), (43, 3, 2), (44, 26, 2)}
_SPEAKER = {(22, 1, 4), (22, 5, 1), (22, 6, 13), (22, 8, 5)}
_SELAH = {(19, 68, 32)}
_NBSP = {(43, 5, 11), (44, 20, 35), (44, 22, 21)}
KNOWN_DIVERGENCE = {"web": _UPSTREAM | _SPEAKER | _SELAH, "webbe": _UPSTREAM | _SPEAKER | _SELAH | _NBSP}


def verify_bundled(work, assets=BUNDLED_ASSETS, known=None):
    """Positive control: convert the USFM of the five bundled Bibles and diff against the shipped assets."""
    known = KNOWN_DIVERGENCE if known is None else known
    report, bad = [], False
    for name, (ebible_id, hab_note) in sbh.SOURCES.items():
        old = {tuple(map(int, l.split("\t", 3)[:3])): l.split("\t", 3)[3] for l in gzip_lines(assets / f"{name}.tsv.gz")}
        zip_path = work / f"{ebible_id}_usfm.zip"
        if not zip_path.is_file():
            raise Mismatch([f"missing {zip_path}; download {EBIBLE}/{ebible_id}_usfm.zip"])
        ot = sum(1 for k in old if k[0] <= OT_BOOKS)
        spec = {"language": "eng", "hab_3_19_note": hab_note, "verses": {"ot": ot, "nt": len(old) - ot}}
        try:
            new = {tuple(r[:3]): r[3] for r in convert(zip_path, spec)[0]}
        except Mismatch as e:
            bad = True
            report.append(f"{name}: CONVERSION ABORTED\n  " + "\n  ".join(e.problems[:15]))
            continue
        differ = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
        expected = set(known.get(name, ()))
        ok = differ == expected
        bad |= not ok
        label = "IDENTICAL" if not differ and ok else ("DIFFERS AS PINNED" if ok else "UNEXPECTED DIFFERENCES")
        report.append(f"{name}: {label} ({len(old)} bundled rows, {len(new)} converted, {len(differ)} differ, "
                      f"{len(expected)} pinned)")
        for k in sorted(differ ^ expected)[:8]:
            why = "not pinned" if k in differ else "pinned but identical"
            report.append(f"    {k} {why}\n      bundled  {old.get(k, '(none)')[:100]}\n      usfm     {new.get(k, '(none)')[:100]}")
    return not bad, report


def gzip_lines(path):
    return gzip.decompress(path.read_bytes()).decode("utf-8").splitlines()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--allowlist", type=pathlib.Path, default=ALLOWLIST)
    ap.add_argument("--work-dir", type=pathlib.Path, help="cache of downloaded zips and translations.csv")
    ap.add_argument("--out-dir", type=pathlib.Path, help="where assets and catalog.json are written")
    ap.add_argument("--only", nargs="+", metavar="CODE", help="build just these allowlist codes")
    ap.add_argument("--base-url", help="URL prefix the app will download assets from (recorded in catalog.json)")
    ap.add_argument("--require-cleared", action="store_true", help="publish run: refuse any legal_review=pending entry")
    ap.add_argument("--offline", action="store_true", help="never touch the network; missing inputs are an error")
    ap.add_argument("--refresh", action="store_true", help="re-download translations.csv and every zip, even if cached")
    ap.add_argument("--verify-bundled", action="store_true", help="positive control against the five bundled assets")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.work_dir:
        ap.error("--work-dir is required")
    if args.refresh and args.offline:
        ap.error("--refresh needs the network and --offline forbids it")
    try:
        if args.verify_bundled:
            ok, report = verify_bundled(args.work_dir, BUNDLED_ASSETS)
            print("\n".join(report))
            return 0 if ok else 1
        if not args.out_dir:
            ap.error("--out-dir is required to build")
        catalog = build(load_allowlist(args.allowlist), args.work_dir, args.out_dir, args.only,
                        args.require_cleared, args.base_url, args.offline, refresh=args.refresh)
    except Mismatch as e:
        print("ABORTED, nothing written:\n  " + "\n  ".join(e.problems))
        return 1
    for t in catalog["translations"]:
        print(f"{t['code']:6} {t['verses']['ot'] + t['verses']['nt']:6} verses  {t['size_bytes']:8} bytes  "
              f"sha256 {t['sha256'][:12]}..  {t['licence']['id']}  legal:{t['legal_review']}")
    return 0


# --- self-test (no network) --------------------------------------------------------------------
HAB_NOTE = "To the chief singer on my stringed instruments."


def _fixture_book(n, patch):
    """A tiny but structurally honest USFM book: every chapter, 2 verses each, plus the special cases."""
    code = CANON[n - 1]
    out = [f"\\id {code} fixture", f"\\h {code}", f"\\mt1 {code}"]
    for c in range(1, CHAPTERS[n - 1] + 1):
        out.append(f"\\c {c}")
        out.append("\\d A Psalm of David, when he fled." if (n, c) == (PSALMS, 3) else "\\s1 A section heading")
        out.append("\\p")
        for v in range(1, 177 if (n, c) == (PSALMS, 119) else 20 if (n, c) == (HABAKKUK, 3) else 3):
            if (n, c) == (PSALMS, 119) and v == 1:
                out.append("\\qa ALEPH")
            if (n, c) == (PSALMS, 119) and v == 9:
                out.append("\\qc \u05d1 HHETH.")  # ASV-style label, a spelling no list of letter names has
            note = f" {HAB_NOTE}" if (n, c, v) == (HABAKKUK, 3, 19) else ""
            out.append(f"\\v {v} {code} {c}:{v} text.{note}")
    text = "\n".join(out) + "\n"
    return patch[code](text) if code in patch else text


def _fixture_counts():
    ot = nt = 0
    for n in range(1, 67):
        per = sum(176 if (n, c) == (PSALMS, 119) else 19 if (n, c) == (HABAKKUK, 3) else 2
                  for c in range(1, CHAPTERS[n - 1] + 1))
        ot, nt = (ot + per, nt) if n <= OT_BOOKS else (ot, nt + per)
    return {"ot": ot, "nt": nt}


LICENCE_PAGE = "<html><body><p>This text is in the Public&nbsp;Domain.</p></body></html>"


def _fixture_zip(path, patch=None, drop=(), duplicate=(), licence_page=LICENCE_PAGE, upper=(), sidecars=False, extras=None):
    patch = patch or {}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for extra_name, extra_data in (extras or {}).items():
            zf.writestr(extra_name, extra_data)
        zf.writestr("00-FRT.usfm", "\\id FRT front matter\n\\mt1 Front\n")
        zf.writestr("99-TOB.usfm", "\\id TOB deuterocanon\n\\c 1\n\\p\n\\v 1 Not in the canon.\n")
        zf.writestr("style.css", "body {}")
        if licence_page is not None:
            zf.writestr("copr.htm", licence_page)
        if sidecars:  # macOS resource-fork debris: not UTF-8, not a book
            zf.writestr("__MACOSX/._01-GEN.usfm", b"\xff\xfe\x00junk")
            zf.writestr("._02-EXO.usfm", b"\xff\xfe\x00junk")
        for n in range(1, 67):
            if CANON[n - 1] not in drop:
                name = f"{n:02d}-{CANON[n - 1]}." + ("USFM" if CANON[n - 1] in upper else "usfm")
                zf.writestr(name, _fixture_book(n, patch))
        for code in duplicate:
            zf.writestr(f"dup-{code}.usfm", _fixture_book(CANON.index(code) + 1, {}))
    return path


def _csv_text(rows):
    cols = ["translationId", "languageCode", "title", "Redistributable", "downloadable", "Copyright", "UpdateDate"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, cols)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def self_test():
    def raises(fn, needle, what="expected a Mismatch"):
        try:
            fn()
        except Mismatch as e:
            joined = "\n".join(e.problems)
            assert needle in joined, (needle, joined[:600])
            return e
        raise AssertionError(f"{what}: nothing raised, wanted {needle!r}")

    def parse(usfm, label="GEN"):
        return parse_book(usfm, label)

    # ---- clean(): the delimiter space, word attributes, notes, NBSP, NFC ----
    assert clean("(\\add is\\add* it not)") == "(is it not)", "the space after an opening marker is a delimiter"
    assert clean('\\w God|strong="H0430"\\w* \\w said|strong="H0559"\\w*, Let') == "God said, Let"
    assert clean("x\\f + \\fr 1.1 \\ft a\nnote\\f* y") == "x y"
    assert clean("\\qs Selah\\qs*") == "Selah"
    assert clean("a\u00a0b  c [d] \u00b6 e*") == "a\u00a0b c d e", "NBSP survives; brackets, pilcrow, star go"
    assert clean("o\u0323\u0300") == unicodedata.normalize("NFC", "o\u0323\u0300"), "NFC"
    assert clean("\\+bd \\+w he|strong=\"G1\"\\+w*\\+bd* is") == "he is"

    # ---- parse_book(): what is verse text, what is not, and what is refused ----
    usfm = "\n".join([
        "\\id GEN", "\\h Genesis", "\\c 1", "\\s1 A section heading", "\\r (Mark 1:1)",
        "\\d A descriptive title that", "runs onto a second line.", "\\q1",
        "\\v 1 In the \\w beginning|strong=\"H1\"\\w* God\\f + \\fr 1.1 \\ft a note", "that spans lines\\f* created.",
        "\\q2 the heavens", "\\v 2 And the earth.\\x - \\xo 1.2 \\xt Job 1\\x*", "\\b",
        "\\p \\v 3 Third \\add verse\\add*, \\v 4 fourth inline.", "\\v 5", "\\q1 \\v 6 Six", "\\qc Selah",
        "\\c 2", "\\p", "\\v 1 Next chapter\u00a0\u201d", "\\tr \\tc1 \\v 2 table \\tcr2 cell"])
    verses, heads, omitted = parse(usfm)
    assert verses[(1, 1)] == "In the beginning God created. the heavens", verses[(1, 1)]
    assert verses[(1, 2)] == "And the earth." and verses[(1, 3)] == "Third verse,"
    assert verses[(1, 4)] == "fourth inline." and verses[(1, 6)] == "Six Selah", "\\qc is TEXT outside Psalm 119"
    assert omitted == [(1, 5)] and (1, 5) not in verses, "a numbered verse with no text is omitted, not a row"
    assert verses[(2, 1)] == "Next chapter\u00a0\u201d" and verses[(2, 2)] == "table cell"
    assert heads == [(1, "A descriptive title that runs onto a second line.")], heads
    assert not any("heading" in t or "Mark" in t for t in verses.values()), "headings never become verse text"
    for snippet, needle in [
        ("\\c 1\n\\p\n\\v 1-2 text", "not a plain number"),
        ("\\c 1\n\\p\n\\v 1a text", "not a plain number"),
        ("\\c 1\n\\p lead text\n\\v 1 x", "text outside any verse"),
        ("\\c 1\n\\zz foo\n\\v 1 x", "unknown line marker \\zz"),
        ("\\c 2\n\\p\n\\v 1 x", "does not follow chapter 0"),
        ("\\c 1\n\\p\n\\v 1 a\n\\c 3\n\\p\n\\v 1 b", "does not follow chapter 1"),
        ("\\c 1\n\\p\n\\v 1 a\n\\v 1 b", "appears twice"),
        ("\\c 1\n\\p\n\\v 2 a\n\\v 1 b", "follows verse"),
        ("\\p\n\\v 1 before any chapter", "text before the first chapter")]:
        raises(lambda: parse(snippet), needle, f"parse_book accepted {snippet!r}")
    # Psalm 119: a `\qc` line with no verse in it is a letter label, whatever the translation spells it.
    psa = "\n".join(f"\\c {c}\n\\p\n\\v 1 x" for c in range(1, 119))
    v119, h119, _ = parse(psa + "\n\\c 119\n\\qc \u05d0 ALEPH.\n\\q1\n\\v 1 Blessed\n\\v 8 Ends.\n\\qc \u05d1 HHETH.\n\\q1\n"
                          "\\v 9 How can\n\\qc \\v 10 verse on a qc line", "PSA")
    assert v119[(119, 8)] == "Ends." and v119[(119, 9)] == "How can", v119
    assert v119[(119, 10)] == "verse on a qc line", "a `\\qc` line that holds a verse is text"
    assert [h for c, h in h119 if c == 119] == ["\u05d0 ALEPH.", "\u05d1 HHETH."], h119

    # ---- read_usfm_zip(): canon only, complete, bounded ----
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        z = _fixture_zip(d / "ok.zip")
        books = read_usfm_zip(z)
        assert sorted(books) == list(range(1, 67)), "front matter and deuterocanon are ignored"
        raises(lambda: read_usfm_zip(_fixture_zip(d / "miss.zip", drop=("REV",))), "missing canonical books ['REV']")
        raises(lambda: read_usfm_zip(_fixture_zip(d / "dup.zip", duplicate=("GEN",))), "appears in two files")
        (d / "junk.zip").write_bytes(b"not a zip")
        raises(lambda: read_usfm_zip(d / "junk.zip"), "not a readable zip")
        global MAX_MEMBER_BYTES
        saved_cap, MAX_MEMBER_BYTES = MAX_MEMBER_BYTES, 1000
        try:
            raises(lambda: read_usfm_zip(z), "possible zip bomb")
        finally:
            MAX_MEMBER_BYTES = saved_cap

        # The cap that bounds memory is on bytes ACTUALLY read. Every read of a member must be limited to the
        # cap plus one byte: an unbounded `read()` inflates up to 1 GiB inside one call before ZipFile truncates
        # to the size the zip claims (measured: 201 MiB for a member declared as 1000 bytes).
        module = sys.modules[__name__]
        real_read, reads = zipfile.ZipExtFile.read, []

        def spy(self, n=-1):
            reads.append(n)
            return real_read(self, n)

        with mock.patch.object(zipfile.ZipExtFile, "read", spy):
            read_usfm_zip(z)
        assert reads and set(reads) == {MAX_MEMBER_BYTES + 1}, f"a member was read without the cap: {sorted(set(reads))}"
        # A member that LIES (declares 100 bytes, inflates to 2 MB) is refused with a message, not a traceback.
        lying = d / "lying.zip"
        with zipfile.ZipFile(lying, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("01-GEN.usfm", b"\\id GEN\n" + b"A" * 2_000_000)
        blob = lying.read_bytes().replace(struct.pack("<I", 2_000_008), struct.pack("<I", 100))
        assert blob != lying.read_bytes(), "the fixture did not patch the declared size"
        lying.write_bytes(blob)
        with mock.patch.object(module, "MAX_MEMBER_BYTES", 1000):
            raises(lambda: read_usfm_zip(lying), "cannot read '01-GEN.usfm'")
        # The post-read cap is defence in depth for a stdlib that stops truncating: force an oversize read.
        with mock.patch.object(zipfile.ZipExtFile, "read", lambda self, n=-1: b"x" * (MAX_MEMBER_BYTES + 1)):
            raises(lambda: read_usfm_zip(z), "inflates past the size caps")
        with zipfile.ZipFile(z) as zf:
            declared = sum(i.file_size for i in zf.infolist() if i.filename.endswith(".usfm"))
        # The total cap equals the declared total, so the declared-size check passes and only the check on
        # what was actually read can refuse (each read returns far more than any member declared).
        with mock.patch.object(module, "MAX_TOTAL_BYTES", declared), \
                mock.patch.object(zipfile.ZipExtFile, "read", lambda self, n=-1: b"\\id GEN\n" * (declared // 4)):
            raises(lambda: read_usfm_zip(z), "inflates past the size caps")
        # Too many members, and a member that is not UTF-8.
        with mock.patch.object(module, "MAX_MEMBERS", 5):
            raises(lambda: read_usfm_zip(z), "more than the 5 cap")
        # The total of the sizes the members declare is capped too, not just each one.
        with mock.patch.object(module, "MAX_TOTAL_BYTES", 1000):
            raises(lambda: read_usfm_zip(z), "declare more than the size caps")
        # An upper-case `.USFM` name is a book; macOS resource-fork sidecars are ignored, not a crash.
        assert sorted(read_usfm_zip(_fixture_zip(d / "odd.zip", upper=("GEN", "REV"), sidecars=True))) == list(range(1, 67))
        # Only a name that ENDS in .usfm is a book: `.usfm.bak` and `.usfm.txt` are not (a loose match would read them).
        loose = _fixture_zip(d / "loose.zip", extras={"01-GEN.usfm.bak": b"\\id GEN\n\xff", "notes.usfm.txt": b"\xff\xfe"})
        assert sorted(read_usfm_zip(loose)) == list(range(1, 67))
        badutf = d / "badutf.zip"
        with zipfile.ZipFile(badutf, "w") as zf:
            zf.writestr("01-GEN.usfm", b"\\id GEN\n\xff\xfe\xfa")
        raises(lambda: read_usfm_zip(badutf), "is not UTF-8")

        # ---- the regexes cannot be made quadratic by one malformed verse ----
        def linear(work_for, size):
            """`work_for(n)` must scale LINEARLY: four times the input may take about four times as long, never sixteen.

            A ratio, not a wall-clock bound, so a slow or busy machine does not make it flaky; the floor stops timer noise
            on a fast one. (A quadratic regex ran 16x slower at 4x the input: 0.25 s then 4 s.)"""
            def timed_run(n):
                start = time.perf_counter()
                try:
                    work_for(n)
                except Mismatch:
                    pass  # refusing the input is fine; being slow about it is not
                return time.perf_counter() - start

            small_took, big_took = timed_run(size), timed_run(size * 4)
            assert big_took < 10 * max(small_took, 0.02), \
                f"{size} -> {size * 4}: {small_took:.3f}s -> {big_took:.3f}s ({big_took / max(small_took, 1e-9):.0f}x for 4x the input)"

        linear(lambda n: clean("\\w" + " " * n + "x"), 5_000)
        linear(lambda n: clean("\\w " * n + "x" * 100_000), 10_000)
        # Many CLOSED notes must be linear too: copying the rest of the text per note (`text[pos:].lstrip()`) is quadratic.
        linear(lambda n: clean("word\\f + n\\f* " * n), 25_000)
        linear(lambda n: clean("word \\f + n\\f* \\wj ?\\wj* " * n), 15_000)
        raises(lambda: clean("\\f + a " * 20_000), "unterminated \\f note")
        raises(lambda: parse("\\c 1\n\\p\n\\v 1 x\\f + a " * 20_000), "GEN: unterminated \\f note")
        assert strip_notes("a\\f + x\\f* b\\x - y\\x* c\\fe + z\\fe* d") == "a b c d"
        assert strip_notes("no notes here") == "no notes here" and strip_notes("") == ""
        assert strip_notes("\\fr 1:1 is not an opener\\f + n\\f*") == "\\fr 1:1 is not an opener"
        raises(lambda: strip_notes("a \\x - never closed"), "unterminated \\x note")
        raises(lambda: strip_notes("a \\f + closed\\f* b \\f + not\\fe*"), "unterminated \\f note")

        # A note whose closer belongs to a LATER note would delete every verse in between: refused, not guessed.
        # Each case isolates ONE reason: a verse marker, a chapter marker, or a second opener, inside the span.
        raises(lambda: strip_notes("\\v 1 a\\f + open\n\\v 2 b\\f* c"), "belongs to a later note")
        raises(lambda: strip_notes("\\v 1 a\\f + open\n\\c 2\nb\\f* c"), "belongs to a later note")
        raises(lambda: strip_notes("x \\f + a \\f + b\\f* y"), "belongs to a later note")
        raises(lambda: strip_notes("\\v 1 a\\f + open\n\\v 2 b\\f + c\\f* d"), "belongs to a later note")  # all three at once
        raises(lambda: parse("\\c 1\n\\p\n\\v 1 text\\f + unclosed\n\\v 2 two\\f + b\\f*"), "GEN: ")

        # `\fm ,\fm*` is the separator Biblica puts between two footnote callers: apparatus, dropped with the notes.
        assert clean("Ya\u2019ar,\\f + a\\f*\\fm ,\\fm*\\f + b\\f*") == "Ya\u2019ar,", "the \\fm comma doubled Hausa verses"
        assert strip_notes("a\\fm ,\\fm*b") == "ab"

        # The spacing USFM puts around a note is not text: `egg \f..\f*?` is "egg?", not "egg ?".
        assert clean("egg \\f + n\\f*?") == "egg?" and clean("egg \\f + n\\f* more") == "egg more"
        assert clean("x \\f + n\\f*\u201d") == "x\u201d" and clean("x \\f + n\\f*\u2019") == "x\u2019"
        assert clean("x \\f + n\\f*\u201cy") == "x \u201cy", "an OPENING quote is not closing punctuation"
        assert clean("a \\f + n\\f* \\f + m\\f*.") == "a." and clean("a \\f + n\\f*  , b") == "a, b"
        assert clean("\u2019\\wj* \\f + n\\f* \\wj ?\\wj*") == "\u2019?", "punctuation behind an inline marker still closes the phrase"
        assert clean("a\\f + n\\f* b") == "a b" and clean("a \\f + n\\f*") == "a"
        # A word that BEGINS with an apostrophe (Hausa `\u2019yan`, `\u2019yar`) keeps the space that sat before the note: the
        # first version of the spacing rule fused six real Hausa verses ("Abiya\u2019yar Zakariya").
        assert clean("Yahuda,\\f + n\\f* \u2019yan\u2019uwanka") == "Yahuda, \u2019yan\u2019uwanka"
        assert clean("Abiya \\f + n\\f* \u2019yar Zakariya") == "Abiya \u2019yar Zakariya"
        assert clean("x \\f + n\\f*\u2019 y") == "x\u2019 y" and clean("x \\f + n\\f*?\u2019\u201d") == "x?\u2019\u201d"
        assert clean("x \\f + n\\f*\u2019") == "x\u2019" and clean("x \\f + n\\f*\u201d, y") == "x\u201d, y"
        # Each closing mark closes (a literal list: the code's own set must not be the thing under test).
        for mark in ",;:.!?)":
            assert clean(f"x \\f + n\\f*{mark}") == f"x{mark}", mark
        assert clean("x\t\\f + n\\f*.") == "x." and clean("x \t\\f + n\\f*\t.") == "x.", "a tab is spacing too"
        assert clean("a \\f + n\\f* \\f + m\\f* \\f + o\\f*.") == "a.", "three notes in a row"
        assert clean("\\f + n\\f*.") == "." and clean(".\\f + n\\f*") == ".", "a note at the very start or end"
        assert clean("x \\f + n\\f*\\add*.") == "x." and clean("x \\f + n\\f*\\+nd*.") == "x.", "closers between note and mark"
        assert strip_notes("a\\ca 1\\ca*b\\vp 2\\vp*c\\ex t\\ex*d\\ef t\\ef*e\\va 3\\va*f\\fig x\\fig*g") == "abcdefg", "every note kind"
        assert clean("\\th1 a \\thr2 b \\tc1 c") == "a b c", "table cell markers mid-line"
        # A heading may continue on a line that starts with an inline marker; its markup is cleaned like any other.
        _, heads_c, _ = parse("\\c 1\n\\d For the \\w chief|strong=\"H1\"\\w*\n\\sc musician\\sc* here.\n\\p\n\\v 1 x")
        assert heads_c == [(1, "For the chief musician here.")], heads_c

        # Inline markers: the known ones go, anything else is refused (stripping it would keep its CONTENT).
        assert clean("\\+nd LORD\\+nd* said \\bd it\\bd*") == "LORD said it"
        for bad_inline, name in [("a \\rq Isa 1:1\\rq* b", "rq"), ("a \\xt Jon 1:1\\xt* b", "xt"), ("a \\s1 HEADING", "s1"),
                                 ("a \\d A title \\q1 more", "d"), ("a \\foo secret\\foo* b", "foo")]:
            raises(lambda: clean(bad_inline), f"unknown inline marker \\{name} ", f"clean() accepted {bad_inline!r}")
        raises(lambda: parse("\\c 1\n\\p\n\\v 1 ok\n\\v 3 a \\rq b\\rq* c"), "GEN: 1:3: unknown inline marker \\rq")
        raises(lambda: parse("\\c 1\n\\p\n\\v 1 text. \\s1 INLINE HEADING \\p"), "unknown inline marker \\s1")
        raises(lambda: parse("\\c 1\n\\d A title \\foo x\\foo*\n\\p\n\\v 1 x"), "GEN: chapter 1 heading: unknown inline marker")

        # A `\qc` line in Psalm 119 is dropped only if it is shaped like a letter label; a verse's own words stay.
        psa119 = "\n".join(f"\\c {c}\n\\p\n\\v 1 x" for c in range(1, 119))
        v119b, _, _ = parse(psa119 + "\n\\c 119\n\\q1\n\\v 5 First part.\n\\qc more words of verse five, with commas.", "PSA")
        assert v119b[(119, 5)] == "First part. more words of verse five, with commas.", v119b[(119, 5)]
        # ...and a short line is not a label either unless it has a Hebrew letter and sits where a section starts (after
        # verse 8k): "Amen." at 119:8 must stay verse text, and a real label at 119:5 is in the wrong place.
        v119c, h119c, _ = parse(psa119 + "\n\\c 119\n\\q1\n\\v 8 Last words.\n\\qc Amen.\n\\v 9 Next.", "PSA")
        assert v119c[(119, 8)] == "Last words. Amen." and not [h for c, h in h119c if c == 119], (v119c[(119, 8)], h119c)
        v119d, h119d, _ = parse(psa119 + "\n\\c 119\n\\q1\n\\v 5 Five.\n\\qc \u05d1 HHETH.\n\\v 6 Six.", "PSA")
        assert v119d[(119, 5)] == "Five. \u05d1 HHETH." and not [h for c, h in h119d if c == 119], "a label mid-section is text"

        # ---- convert(): the whole translation, every post-check ----
        counts = _fixture_counts()
        spec = {"language": "eng", "hab_3_19_note": HAB_NOTE, "verses": counts}
        rows, omitted = convert(z, spec)
        got = {tuple(r[:3]): r[3] for r in rows}
        assert omitted == [] and len(got) == counts["ot"] + counts["nt"]
        assert got[(19, 3, 1)] == "PSA 3:1 text.", "the \\d title is a heading and is never emitted"
        assert got[(35, 3, 19)] == "HAB 3:19 text.", "the fused musical note is cut"
        assert got[(19, 119, 8)] == "PSA 119:8 text." and got[(19, 119, 9)] == "PSA 119:9 text."
        assert rows == sorted(rows) and tsv_bytes(rows) == tsv_bytes(convert(z, spec)[0]), "deterministic, sorted"

        def conv(patch, **over):
            p = _fixture_zip(d / "case.zip", patch)
            return lambda: convert(p, {**spec, **over})

        raises(conv({}, verses={"ot": counts["ot"] + 1, "nt": counts["nt"]}), "the allowlist pins")
        raises(conv({}, hab_3_19_note=None), "still carries the musical note")
        raises(conv({"PSA": lambda t: t.replace("\\v 1 PSA 3:1 text.", "\\v 1 A Psalm of David, when he fled. PSA 3:1 text.")}),
               "fused into the verse text")
        raises(conv({"PSA": lambda t: t.replace("\\v 1 PSA 3:1 text.", "\\v 1 A Psalm of David. PSA 3:1 text.")}),
               "opens with a psalm title")
        raises(conv({"PSA": lambda t: t.replace("\\v 8 PSA 119:8 text.", "\\v 8 PSA 119:8 text. BETH")}),
               "still carries a Psalm 119 letter label")
        # A label at the START of a verse that is not on a letter boundary (v 18) is not stripped: it is caught.
        raises(conv({"PSA": lambda t: t.replace("\\v 18 ", "\\v 18 BETH. ")}), "still carries a Psalm 119 letter label")
        bracketed = conv({"GEN": lambda t: t.replace("\\v 2 GEN 1:2 text.", "\\v 2 GEN 1:2 [supplied] text.")})()[0]
        assert [r[3] for r in bracketed if r[:3] == [1, 1, 2]] == ["GEN 1:2 supplied text."], "[ ] are stripped, not refused"
        raises(conv({"GEN": lambda t: t.replace("\\v 2 GEN 1:2 text.", "\\v 2 GEN 1:2 a | b")}), "markup residue")
        raises(conv({"GEN": lambda t: t.replace("\\v 2 GEN 1:2 text.", "\\v 2 GEN 1:2 stray \\ slash")}), "markup residue")
        raises(conv({"GEN": lambda t: t.replace("\\c 5\n", "\\c 6\n")}), "does not follow chapter 4")
        # A book that is merely SHORT or LONG still has an unbroken chapter sequence: only the count catches it.
        raises(conv({"EXO": lambda t: t[:t.index("\\c 40\n")]}), "expected 1..40")
        raises(conv({"EXO": lambda t: t + "\\c 41\n\\p\n\\v 1 EXO 41:1 text.\n"}), "expected 1..40")
        # Psalm 119 keeps 176 verses: with one verse missing, the pin is adjusted so ONLY this rule can object.
        raises(conv({"PSA": lambda t: t.replace("\\v 100 PSA 119:100 text.\n", "")},
                    verses={"ot": counts["ot"] - 1, "nt": counts["nt"]}), "Psalm 119 must keep 176 verses")
        raises(conv({"EXO": lambda t: t.replace("\\v 1 EXO 1:1 text.\n", "")}), "does not start at verse 1")
        # The fusion oracle has three shapes, each its own clause: the heading is the whole verse, its start, or its end.
        title = lambda t: t.replace("\\d A Psalm of David, when he fled.", "\\d Orin Dafidi.")
        raises(conv({"PSA": lambda t: title(t).replace("\\v 1 PSA 3:1 text.", "\\v 1 Orin Dafidi.")}, language="yor"),
               "fused into the verse text")
        raises(conv({"PSA": lambda t: title(t).replace("\\v 1 PSA 3:1 text.", "\\v 1 PSA 3:1 text. Orin Dafidi.")}, language="yor"),
               "fused into the verse text")
        # English-only nets do not run on other languages: a Yoruba verse may legitimately begin "A Psalm".
        opener_patch = {"PSA": lambda t: t.replace("\\v 1 PSA 3:1 text.", "\\v 1 A Psalm of nothing. PSA 3:1 text.")}
        assert conv(opener_patch, language="yor")()[0], "the English title-opener net ran on a Yoruba text"
        raises(conv(opener_patch, language="eng"), "opens with a psalm title")
        # Control characters and a trailing no-break space are not verse text (NUL, and a space the strip does not see).
        raises(conv({"GEN": lambda t: t.replace("\\v 2 GEN 1:2 text.", "\\v 2 GEN 1:2 a\x00b")}), "markup residue")
        raises(conv({"GEN": lambda t: t.replace("\\v 2 GEN 1:2 text.", "\\v 2 GEN 1:2 text.\\add \u00a0\\add*")}), "untrimmed")
        # A language-independent heading oracle: no English opener list is involved for a Yoruba text.
        raises(conv({"PSA": lambda t: t.replace("\\d A Psalm of David, when he fled.", "\\d Orin Dafidi.")
                     .replace("\\v 1 PSA 3:1 text.", "\\v 1 Orin Dafidi. PSA 3:1 text.")}, language="yor"),
               "fused into the verse text")
        # DBY puts Psalm 119's letter inline; a verse that merely starts in capitals is left alone.
        inline = convert(_fixture_zip(d / "dby.zip", {"PSA": lambda t: t.replace("\\v 1 PSA 119:1", "\\v 1 ALEPH. PSA 119:1")
                                                       .replace("\\v 9 PSA 119:9", "\\v 9 BETH PSA 119:9")}), spec)[0]
        inl = {tuple(r[:3]): r[3] for r in inline}
        assert inl[(19, 119, 1)] == "PSA 119:1 text." and inl[(19, 119, 9)] == "PSA 119:9 text."
        assert inl[(19, 119, 17)] == "PSA 119:17 text.", "a verse starting 'PSA' is not a label"
        # An empty verse is omitted (and the pin counts rows); decomposed Yoruba text is composed (NFC).
        gap_rows, gap = convert(_fixture_zip(d / "gap.zip", {"GEN": lambda t: t.replace("\\v 2 GEN 1:2 text.", "\\v 2")}),
                                {**spec, "verses": {"ot": counts["ot"] - 1, "nt": counts["nt"]}})
        assert gap == [(1, 1, 2)] and (1, 1, 2) not in {tuple(r[:3]) for r in gap_rows}
        nfc_rows, _ = convert(_fixture_zip(d / "nfc.zip", {"GEN": lambda t: t.replace("GEN 1:1 text.", "o\u0323\u0300 text.")}), spec)
        assert nfc_rows[0][3] == unicodedata.normalize("NFC", "o\u0323\u0300 text.") and nfc_rows[0][3] != "o\u0323\u0300 text."

        # ---- gate(): every reason, all reported together ----
        real = load_allowlist(ALLOWLIST)
        row = {"translationId": "fixbible", "languageCode": "eng", "title": "Fixture Bible", "Redistributable": "True",
               "downloadable": "True", "Copyright": "public domain", "UpdateDate": "2026-01-01"}
        entry = {"code": "FIX", "ebible_id": "fixbible", "name": "Fixture Bible", "language": "eng", "licence": "public-domain",
                 "expect_copyright": "public domain", "licence_text": ["public domain"], "legal_review": "cleared",
                 "verses": counts, "hab_3_19_note": HAB_NOTE}

        def allow(**over):
            return {"schema": 1, "licences": real["licences"], "translations": [{**entry, **over}],
                    "excluded": [{"ebible_id": "engylt"}]}

        gate(allow(), {"fixbible": row}, True)
        for over, rowover, needle in [
                ({"licence": "cc-by-nc-nd-4.0"}, {}, "is not permitted"),
                ({"licence": "nope"}, {}, "not in the allowlist's registry"),
                ({}, {"Redistributable": "False"}, "does not mark it Redistributable"),
                ({}, {"downloadable": "False"}, "does not mark it downloadable"),
                ({}, {"languageCode": "yor"}, "eBible language is 'yor'"),
                ({}, {"Copyright": "Copyright (c) Somebody"}, "the entry expects"),
                ({}, {"Copyright": "not public domain"}, "the entry expects"),  # a substring match would pass this
                ({"expect_copyright": ""}, {}, "has no expect_copyright"),
                ({"expect_copyright": None}, {}, "has no expect_copyright"),
                ({"licence_text": []}, {}, "has no licence_text"),
                ({"licence_text": [""]}, {}, "has no licence_text"),
                ({"licence_text": "public domain"}, {}, "has no licence_text"),
                ({"code": "kjv"}, {}, "code must match"),
                ({"code": "KJV"}, {}, "collides with a bundled translation"),
                ({"code": "TOO-LONG-A-CODE-X"}, {}, "code must match"),
                ({"ebible_id": "../etc"}, {}, "not a plain identifier"),
                ({"ebible_id": "engylt"}, {}, "excluded list"),
                ({"legal_review": "maybe"}, {}, "must be 'cleared' or 'pending'"),
                ({"legal_review": "pending"}, {}, "--require-cleared")]:
            catalogue = {over.get("ebible_id", "fixbible"): {**row, **rowover}}
            raises(lambda: gate(allow(**over), catalogue, True), needle)
        gate(allow(legal_review="pending"), {"fixbible": row}, False)  # pending is fine until the publish run
        raises(lambda: gate(allow(), {}, False), "not in eBible's catalogue")
        two = raises(lambda: gate(allow(licence="cc-by-nc-nd-4.0"), {"fixbible": {**row, "Redistributable": "False"}}, False),
                     "is not permitted")
        assert "Redistributable" in "\n".join(two.problems), "every reason for one entry is reported, not just the first"
        dup = allow()
        dup["translations"].append(dict(entry))
        raises(lambda: gate(dup, {"fixbible": row}, False), "duplicate code")
        gate(allow(expect_copyright="PUBLIC  Domain"), {"fixbible": row}, False)  # case and spacing are not a licence change
        # `--require-cleared` applies to the entries being BUILT: a cleared one can publish while another waits on legal.
        pend = {**entry, "code": "PEND", "ebible_id": "pendbible", "legal_review": "pending"}
        two = {"schema": 1, "licences": real["licences"], "translations": [entry, pend], "excluded": []}
        both = {"fixbible": row, "pendbible": {**row, "translationId": "pendbible"}}
        gate(two, both, True, {"FIX"})
        raises(lambda: gate(two, both, True, {"PEND"}), "PEND: legal_review is still pending")
        raises(lambda: gate(two, both, True, None), "PEND: legal_review is still pending")
        gate(two, both, False, {"PEND"})
        # Every other rule still applies to entries that are NOT being built.
        raises(lambda: gate({**two, "translations": [entry, {**pend, "licence": "cc-by-nc-nd-4.0"}]}, both, True, {"FIX"}),
               "is not permitted")
        # `$` alone accepts a trailing newline: "KJV\n" slipped past the format AND the bundled-collision checks.
        raises(lambda: gate(allow(code="FIX\n"), {"fixbible": row}, False), "code must match")
        raises(lambda: gate(allow(code="KJV\n"), {"fixbible": row}, False), "code must match")
        raises(lambda: gate(allow(ebible_id="fixbible\n"), {"fixbible\n": row}, False), "not a plain identifier")
        raises(lambda: gate(allow(ebible_id=None), {"fixbible": row}, False), "not a plain identifier")
        bad_schema = d / "schema2.json"
        bad_schema.write_text(json.dumps({"schema": 2}), encoding="utf-8")
        raises(lambda: load_allowlist(bad_schema), "unsupported allowlist schema")

        # ---- the licence page inside eBible's zip: what the allowlist entry relies on must still be there ----
        def page(html_text):
            return _fixture_zip(d / "page.zip", licence_page=html_text)

        check_licence_text(page(LICENCE_PAGE), entry)  # <p>, &nbsp; and wrapping do not matter
        cc = {**entry, "licence_text": ["creative commons attribution-sharealike 4.0"]}
        check_licence_text(page("<p>Creative Commons Attribution-ShareAlike 4\u202a.0\n International (CC BY-SA)</p>"), cc)
        raises(lambda: check_licence_text(page("<p>Creative Commons Attribution 4.0</p>"), cc), "no longer contains")
        raises(lambda: check_licence_text(page("<p>Public Domain. All rights reserved.</p>"), entry), "contains 'all rights reserved'")
        raises(lambda: check_licence_text(page("<p>This is NOT public domain.</p>"), entry), "contains 'not public domain'")
        raises(lambda: check_licence_text(page("<p>Free for Non-Commercial use. Public Domain</p>"), entry), "'non-commercial'")
        raises(lambda: check_licence_text(page("<p>Public Domain. No Derivatives.</p>"), entry), "'no derivative'")
        raises(lambda: check_licence_text(page(None), entry), "no copr.htm")
        raises(lambda: check_licence_text(page("x" * (MAX_LICENCE_PAGE_BYTES + 1)), entry), "copr.htm is larger than")
        (d / "notzip.zip").write_bytes(b"nope")
        raises(lambda: check_licence_text(d / "notzip.zip", entry), "cannot read the licence page")
        # A phrase a tag splits ("Non-<b>commercial</b>") is still seen; so is one that two block tags would glue together.
        raises(lambda: check_licence_text(page("<p>Public Domain. Non-<b>commercial</b> use</p>"), entry), "'non-commercial'")
        check_licence_text(page("<p>Public</p><p>Domain</p>"), entry)
        # Every forbidden phrase, from a literal list (the code's own tuple must not be the thing under test).
        for term in ["all rights reserved", "noncommercial", "non-commercial", "noderivative", "no derivative", "noderivs",
                     "no derivs", "by-nc", "not public domain"]:
            raises(lambda: check_licence_text(page(f"<p>Public Domain. {term.upper()}</p>"), entry), f"contains {term!r}")
        # A hostile licence page of `<` with no `>` (the tag regex rescans to the end from every `<`) stays linear.
        linear(lambda n: check_licence_text(page("<" * n), entry), 20_000)
        linear(lambda n: check_licence_text(page("<b " * n), entry), 20_000)
        # A zip with a huge central directory is refused on the licence-page path too, before it is scanned.
        with mock.patch.object(module, "MAX_MEMBERS", 5):
            raises(lambda: check_licence_text(page(LICENCE_PAGE), entry), "more than the 5 cap")
        # The COMMITTED allowlist must itself pass every static rule (this is what guards a bad edit in CI).
        gate(real, {t["ebible_id"]: {"languageCode": t["language"], "Redistributable": "True", "downloadable": "True",
                                     "Copyright": t["expect_copyright"], "title": "", "UpdateDate": ""}
                    for t in real["translations"]}, False)
        for t in real["translations"]:
            assert t["verses"]["ot"] and t["verses"]["nt"], f"{t['code']} has no pinned verse counts"
            assert t["legal_review"] == "cleared" or t["licence"] == "cc-by-sa-4.0", t["code"]
            assert (t["licence"] != "cc-by-sa-4.0") or (t["attribution"] and t["modifications"]), \
                f"{t['code']}: a CC BY-SA entry needs its attribution and modification notice"
        assert not {t["ebible_id"] for t in real["translations"]} & {e["ebible_id"] for e in real["excluded"]}

        # ---- fetch(): capped, atomic, tidy ----
        def serve(data):
            return lambda req, timeout: contextlib.nullcontext(io.BytesIO(data))

        dest = d / "dl.bin"
        timeouts = []

        def timed(req, timeout):
            timeouts.append(timeout)
            assert req.get_header("User-agent") == USER_AGENT, "downloads identify themselves"
            return contextlib.nullcontext(io.BytesIO(b"hello"))

        fetch("https://example.invalid/x", dest, timed)
        assert dest.read_bytes() == b"hello" and not list(d.glob("*.part"))
        assert timeouts == [60], "a stalled connection must time out"
        big = d / "big.bin"
        raises(lambda: fetch("https://example.invalid/big", big, serve(b"x" * 200_000), max_bytes=100_000), "cap")
        assert not big.exists() and not list(d.glob("*.part")), "an over-cap download leaves nothing behind"

        def refuse(req, timeout):
            raise OSError("connection refused")

        raises(lambda: fetch("https://example.invalid/y", d / "y.bin", refuse), "could not download")
        assert not (d / "y.bin").exists() and not list(d.glob("*.part"))
        # A `.part` that is a planted symlink is removed, never followed: its target is not written.
        victim = d / "victim.txt"
        victim.write_text("keep me")
        (d / "z.bin.part").symlink_to(victim)
        fetch("https://example.invalid/z", d / "z.bin", serve(b"fresh"))
        assert victim.read_text() == "keep me" and (d / "z.bin").read_bytes() == b"fresh" and not (d / "z.bin.part").exists()
        (d / "w.bin.part").mkdir()  # a directory squatting on the name cannot be replaced: refused, not a traceback
        raises(lambda: fetch("https://example.invalid/w", d / "w.bin", serve(b"x")), "could not download")
        (d / "w.bin.part").rmdir()
        # A redirect from HTTPS to anything but HTTPS is refused; an HTTPS one is followed.
        redirects = _HttpsOnlyRedirects()
        original = urllib.request.Request("https://ebible.org/a")
        for scheme in ("http://evil.example/x", "ftp://evil.example/x", "file:///etc/passwd"):
            try:
                redirects.redirect_request(original, None, 302, "Found", {}, scheme)
            except urllib.error.HTTPError as refusal:
                assert "non-HTTPS" in str(refusal), refusal
            else:
                raise AssertionError(f"a redirect to {scheme} was followed")
        followed = redirects.redirect_request(original, io.BytesIO(b""), 302, "Found", {}, "https://ebible.org/b")
        assert followed.full_url == "https://ebible.org/b"
        assert any(isinstance(h, _HttpsOnlyRedirects) for h in _OPENER.handlers), "the default opener lacks the redirect rule"

        # ---- build(): end to end, offline, deterministic, all-or-nothing ----
        work, out = d / "work", d / "out"
        work.mkdir()
        _fixture_zip(work / "fixbible_usfm.zip")
        (work / "translations.csv").write_text(_csv_text([row]), encoding="utf-8")
        cat = build(allow(), work, out, offline=True)
        (e,) = cat["translations"]
        gz = (out / "fix.tsv.gz").read_bytes()
        assert e["sha256"] == hashlib.sha256(gz).hexdigest() and e["size_bytes"] == len(gz) and e["file_name"] == "fix.tsv.gz"
        assert e["verses"] == counts and e["omitted_verses"] == 0 and e["legal_review"] == "cleared"
        assert e["source"]["usfm_zip_sha256"] == sha256_file(work / "fixbible_usfm.zip") and e["licence"]["id"] == "public-domain"
        parsed = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
        assert parsed["translations"][0]["code"] == "FIX" and parsed["translations_csv_sha256"] == sha256_file(work / "translations.csv")
        assert e["source"] == {"ebible_id": "fixbible", "url": f"{EBIBLE}/fixbible_usfm.zip", "title": "Fixture Bible",
                               "copyright": "public domain", "ebible_update_date": "2026-01-01",
                               "usfm_zip_sha256": sha256_file(work / "fixbible_usfm.zip")}
        assert gzip.decompress(gz) == tsv_bytes(convert(work / "fixbible_usfm.zip", spec)[0])
        first = {p.name: p.read_bytes() for p in out.iterdir()}
        build(allow(), work, d / "out2", offline=True, base_url="https://mirror.example/bibles")
        assert (d / "out2" / "fix.tsv.gz").read_bytes() == first["fix.tsv.gz"], "byte-reproducible"
        assert json.loads((d / "out2" / "catalog.json").read_text())["base_url"] == "https://mirror.example/bibles"

        def keys_sorted(node):
            if isinstance(node, dict):
                return list(node) == sorted(node) and all(keys_sorted(v) for v in node.values())
            return all(keys_sorted(v) for v in node) if isinstance(node, list) else True

        assert keys_sorted(parsed), "catalog.json keys are sorted, so a diff between two runs shows only what changed"
        # eBible's real translations.csv starts with a UTF-8 BOM; without `utf-8-sig` its first column is "\ufefftranslationId".
        (work / "translations.csv").write_text("\ufeff" + _csv_text([row]), encoding="utf-8")
        build(allow(), work, d / "out-bom", offline=True)
        (work / "translations.csv").write_text(_csv_text([row]), encoding="utf-8")
        # A corrupt or hostile catalogue is a refusal, not a traceback.
        bad_csv = d / "bad.csv"
        for label, content in [("a field over the csv limit", ("translationId\n" + "x" * 200_000 + "\n").encode()),
                               ("no translationId column", b"foo,bar\n1,2\n"), ("not UTF-8", b"\xff\xfe\x00")]:
            bad_csv.write_bytes(content)
            raises(lambda: load_catalog_csv(bad_csv), "not a usable eBible catalogue", label)
        raises(lambda: load_catalog_csv(d / "missing.csv"), "not a usable eBible catalogue")
        raises(lambda: build(allow(legal_review="pending"), work, d / "out3", require_cleared=True, offline=True),
               "--require-cleared")
        raises(lambda: build(allow(), work, d / "out3", only=["NOPE"], offline=True), "not in the allowlist")
        assert not (d / "out3").exists(), "a refused run writes nothing at all"
        raises(lambda: build(allow(), d / "empty", d / "out3", offline=True), "--offline was given")
        # The output folder must be absent or empty: files from an earlier run would be listed by neither run's catalogue.
        raises(lambda: build(allow(), work, out, offline=True), "must be absent or an empty directory")
        assert {p.name: p.read_bytes() for p in out.iterdir()} == first, "a refused run changed the existing output"
        (d / "afile").write_text("x")
        raises(lambda: build(allow(), work, d / "afile", offline=True), "must be absent or an empty directory")
        (d / "emptydir").mkdir()
        build(allow(), work, d / "emptydir", offline=True)
        assert (d / "emptydir" / "fix.tsv.gz").read_bytes() == first["fix.tsv.gz"], "an existing EMPTY folder is fine"
        # A translation that deliberately omits a verse: counted in the catalogue, not mistaken for a row.
        _fixture_zip(work / "fixbible_usfm.zip", {"GEN": lambda t: t.replace("\\v 2 GEN 1:2 text.", "\\v 2")})
        gap_cat = build(allow(verses={"ot": counts["ot"] - 1, "nt": counts["nt"]}), work, d / "out4", offline=True)
        assert gap_cat["translations"][0]["omitted_verses"] == 1 and gap_cat["translations"][0]["verses"]["ot"] == counts["ot"] - 1
        # A failing translation aborts the whole run and writes nothing: no folder is even created.
        _fixture_zip(work / "fixbible_usfm.zip", {"PSA": lambda t: t.replace("\\v 8 PSA 119:8 text.", "\\v 8 PSA 119:8 text. BETH")})
        raises(lambda: build(allow(), work, d / "out5", offline=True), "FIX: ")
        assert not (d / "out5").exists(), "a failed run left a folder behind"
        # More than 20 problems in one translation: the first 20 are shown and the rest are counted, not dropped silently.
        _fixture_zip(work / "fixbible_usfm.zip", {"GEN": lambda t: t.replace(" text.", " te|xt.")})
        many = raises(lambda: build(allow(), work, d / "out5", offline=True), "FIX: ... and ")
        assert len(many.problems) == 21, len(many.problems)
        # The licence page is part of the build: a zip with none cannot be mirrored.
        _fixture_zip(work / "fixbible_usfm.zip", licence_page=None)
        raises(lambda: build(allow(), work, d / "out5", offline=True), "no copr.htm")
        # The legal fields reach the catalogue exactly as the allowlist (and its licence registry) say.
        cc_spec = {**entry, "code": "AAA", "ebible_id": "ccbible", "language": "eng", "language_name": "Yor\u00f9b\u00e1",
                   "licence": "cc-by-sa-4.0", "expect_copyright": "Copyright \u00a9 2020 Someone",
                   "licence_text": ["creative commons attribution-sharealike 4.0"], "legal_review": "pending",
                   "attribution": "ATTRIBUTION TEXT", "modifications": "MODIFICATIONS TEXT", "trademark_note": "TM NOTE"}
        both_rows = {"fixbible": row, "ccbible": {**row, "translationId": "ccbible", "Copyright": "Copyright \u00a9 2020 Someone",
                                                  "title": "CC Bible", "UpdateDate": "2026-02-02"}}
        (work / "translations.csv").write_text(_csv_text(list(both_rows.values())), encoding="utf-8")
        _fixture_zip(work / "fixbible_usfm.zip")
        _fixture_zip(work / "ccbible_usfm.zip", licence_page="<p>Creative Commons Attribution-ShareAlike 4.0 International</p>")
        two_allow = {"schema": 1, "licences": real["licences"], "translations": [entry, cc_spec], "excluded": []}
        both_cat = build(two_allow, work, d / "out6", offline=True)
        assert [t["code"] for t in both_cat["translations"]] == ["AAA", "FIX"], "catalogue entries are sorted by code"
        aaa = both_cat["translations"][0]
        assert (aaa["attribution"], aaa["modifications"], aaa["trademark_note"]) == ("ATTRIBUTION TEXT", "MODIFICATIONS TEXT", "TM NOTE")
        assert aaa["licence"] == {"id": "cc-by-sa-4.0", "name": real["licences"]["cc-by-sa-4.0"]["name"],
                                  "summary": real["licences"]["cc-by-sa-4.0"]["summary"],
                                  "url": "https://creativecommons.org/licenses/by-sa/4.0/",
                                  "attribution_required": True, "share_alike": True}
        assert aaa["source"]["ebible_update_date"] == "2026-02-02" and aaa["source"]["copyright"] == "Copyright \u00a9 2020 Someone"
        assert aaa["source"]["title"] == "CC Bible" and aaa["language_name"] == "Yor\u00f9b\u00e1" and aaa["legal_review"] == "pending"
        assert "Yor\u00f9b\u00e1".encode("utf-8") in (d / "out6" / "catalog.json").read_bytes(), "catalog.json keeps non-ASCII readable"
        # `--only` with `--require-cleared` builds the cleared translation and ignores the one still in review.
        only_cat = build(two_allow, work, d / "out7", only=["FIX"], require_cleared=True, offline=True)
        assert [t["code"] for t in only_cat["translations"]] == ["FIX"] and sorted(p.name for p in (d / "out7").iterdir()) == ["catalog.json", "fix.tsv.gz"]
        raises(lambda: build(two_allow, work, d / "out8", only=["AAA"], require_cleared=True, offline=True), "AAA: legal_review is still pending")
        # A publish run gates on eBible's catalogue as it is NOW: --require-cleared refetches translations.csv.
        stale = {"fixbible": {**row, "Redistributable": "False"}}
        (work / "translations.csv").write_text(_csv_text(list(stale.values())), encoding="utf-8")
        fresh_csv, fresh_zip = _csv_text([row]).encode("utf-8"), (work / "fixbible_usfm.zip").read_bytes()
        calls = []

        def eBible(req, timeout):
            calls.append(req.full_url)
            return contextlib.nullcontext(io.BytesIO({CATALOG_CSV_URL: fresh_csv, f"{EBIBLE}/fixbible_usfm.zip": fresh_zip}[req.full_url]))

        raises(lambda: build(allow(), work, d / "out9", offline=True), "does not mark it Redistributable")  # cached: stale
        assert calls == []
        stale_zip = _fixture_zip(work / "fixbible_usfm.zip", licence_page="<p>All rights reserved</p>").read_bytes()
        assert stale_zip != fresh_zip
        raises(lambda: build(allow(), work, d / "out9", offline=True), "does not mark it Redistributable")  # stale csv too
        build(allow(), work, d / "out9", require_cleared=True, opener=eBible)
        assert calls == [CATALOG_CSV_URL, f"{EBIBLE}/fixbible_usfm.zip"], f"--require-cleared refetches the catalogue and the zip: {calls}"
        assert (work / "translations.csv").read_bytes() == fresh_csv and (work / "fixbible_usfm.zip").read_bytes() == fresh_zip, \
            "a publish run must build from the fresh zip, not the stale cached one (whose licence page said 'all rights reserved')"
        # `--refresh` refetches everything; offline it refuses rather than quietly using the cache.
        del calls[:]
        build(allow(), work, d / "out10", refresh=True, opener=eBible)
        assert calls == [CATALOG_CSV_URL, f"{EBIBLE}/fixbible_usfm.zip"], calls
        raises(lambda: build(allow(), work, d / "out11", refresh=True, offline=True), "must be refreshed")
        assert not (d / "out11").exists()
        (work / "translations.csv").write_text(_csv_text([row]), encoding="utf-8")
        # Staging failure: a directory squats on a temp name; nothing is renamed, no temp file is left.
        stage = d / "stage"
        (stage / "catalog.json.tmp").mkdir(parents=True)
        raises(lambda: write_all(stage, {"a.bin": b"1", "catalog.json": b"2"}), "nothing was written")
        assert not (stage / "a.bin").exists() and not (stage / "a.bin.tmp").exists() and not (stage / "catalog.json").exists()
        # Staging is exclusive: a planted symlink is never followed, and a file this call did not create is never removed.
        guarded, target = d / "guarded", d / "target.txt"
        guarded.mkdir()
        target.write_text("keep me")
        (guarded / "a.bin.tmp").symlink_to(target)
        raises(lambda: write_all(guarded, {"a.bin": b"new"}), "nothing was written")
        assert target.read_text() == "keep me", "the symlink's target was overwritten"
        assert (guarded / "a.bin.tmp").is_symlink(), "a pre-existing file this call did not create was removed"
        # An output folder this user cannot read is a refusal, not a traceback.
        (d / "locked").mkdir()
        with mock.patch.object(pathlib.Path, "iterdir", side_effect=PermissionError("denied")):
            raises(lambda: build(allow(), work, d / "locked", offline=True), "cannot be inspected")

        # ---- main(): the command line end to end, flag by flag ----
        _fixture_zip(work / "fixbible_usfm.zip")
        (d / "allow.json").write_text(json.dumps(allow()), encoding="utf-8")
        (d / "pending.json").write_text(json.dumps(allow(legal_review="pending")), encoding="utf-8")
        argv = sys.argv

        def cli(*args, allowlist="allow.json", work_dir=None):
            """Run main() with `args`; returns (exit code, stdout). Nothing here touches the network."""
            sys.argv = ["x", "--allowlist", str(d / allowlist), "--work-dir", str(work_dir or work), *args]
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                    return main(), buf.getvalue()
            except SystemExit as exit_:  # argparse errors
                return exit_.code, buf.getvalue()
            finally:
                sys.argv = argv

        code, printed = cli("--out-dir", str(d / "cli"), "--offline")
        assert code == 0 and "FIX" in printed and (d / "cli" / "catalog.json").is_file()
        assert json.loads((d / "cli" / "catalog.json").read_text())["base_url"] is None
        code, _ = cli("--out-dir", str(d / "cli-base"), "--offline", "--base-url", "https://m.example/b")
        assert code == 0 and json.loads((d / "cli-base" / "catalog.json").read_text())["base_url"] == "https://m.example/b"
        # --require-cleared is wired to the gate: a pending entry is refused, nothing is written; without the flag it builds.
        code, printed = cli("--out-dir", str(d / "cli-pub"), "--offline", "--require-cleared", allowlist="pending.json")
        assert code == 1 and "legal_review is still pending" in printed and not (d / "cli-pub").exists()
        code, _ = cli("--out-dir", str(d / "cli-nopub"), "--offline", allowlist="pending.json")
        assert code == 0 and (d / "cli-nopub" / "catalog.json").is_file()
        # --only is wired: an unknown code is refused; a known one builds just that.
        code, printed = cli("--out-dir", str(d / "cli-only"), "--offline", "--only", "NOPE")
        assert code == 1 and "not in the allowlist" in printed and not (d / "cli-only").exists()
        code, _ = cli("--out-dir", str(d / "cli-only"), "--offline", "--only", "FIX")
        assert code == 0
        # --offline is wired: a missing input is refused with a message and no network attempt. The default opener is
        # bound when fetch() is defined, so patch the layer UNDER urlopen: any real attempt reaches OpenerDirector.open.
        no_network = mock.Mock(side_effect=AssertionError("the network was touched"))
        with mock.patch.object(urllib.request.OpenerDirector, "open", no_network):
            code, printed = cli("--out-dir", str(d / "cli-off"), "--offline")
            assert code == 0, "everything is cached: nothing to fetch"
            (work / "fixbible_usfm.zip").rename(work / "moved.zip")
            code, printed = cli("--out-dir", str(d / "cli-off2"), "--offline")
            (work / "moved.zip").rename(work / "fixbible_usfm.zip")
        assert code == 1 and "--offline was given" in printed and no_network.call_count == 0
        # --refresh is wired: it fetches again the catalogue and the zip of the selected translation (a local stand-in for eBible).
        served = {CATALOG_CSV_URL: _csv_text([row]).encode("utf-8"),
                  f"{EBIBLE}/fixbible_usfm.zip": (work / "fixbible_usfm.zip").read_bytes()}
        fetched = []

        def stand_in(self, req, data=None, timeout=None):
            fetched.append(req.full_url)
            return contextlib.nullcontext(io.BytesIO(served[req.full_url]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", stand_in):
            code, _ = cli("--out-dir", str(d / "cli-refresh"), "--refresh")
            assert code == 0 and fetched == [CATALOG_CSV_URL, f"{EBIBLE}/fixbible_usfm.zip"], fetched
            del fetched[:]
            code, _ = cli("--out-dir", str(d / "cli-cached"))
            assert code == 0 and fetched == [], f"without --refresh a complete cache is used as it is: {fetched}"
        # --refresh cannot be combined with --offline; --out-dir is required to build; --work-dir is always required.
        assert cli("--out-dir", str(d / "cli-r"), "--offline", "--refresh")[0] == 2
        assert cli("--offline")[0] == 2
        sys.argv = ["x", "--allowlist", str(d / "allow.json"), "--out-dir", str(d / "cli-w")]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                main()
            raise AssertionError("--work-dir was not required")
        except SystemExit as exit_:
            assert exit_.code == 2
        finally:
            sys.argv = argv
        code, printed = cli("--out-dir", str(d / "cli"), "--offline")
        assert code == 1 and "must be absent or an empty directory" in printed, "re-running into a used folder is refused"

        # ---- verify_bundled(): the positive control, and that it can fail ----
        bundled, wk = d / "bundled", d / "wk"
        bundled.mkdir()
        wk.mkdir()
        base_rows = convert(z, spec)[0]
        for name, (ebible_id, hab_note) in sbh.SOURCES.items():  # each real translation has its own note text
            _fixture_zip(wk / f"{ebible_id}_usfm.zip", {"HAB": lambda t, n=hab_note: t.replace(HAB_NOTE, n)})
            (bundled / f"{name}.tsv.gz").write_bytes(sbh.to_gzip(tsv_bytes(base_rows)))
        ok, report = verify_bundled(wk, bundled, known={})
        assert ok and all("IDENTICAL" in l for l in report), report
        # A bundled asset that LACKS a row the USFM has fails the control (here through the verse-count pin it derives
        # from the asset; the row-level comparison reports the same row once the counts agree).
        (bundled / "kjv.tsv.gz").write_bytes(sbh.to_gzip(tsv_bytes(base_rows[1:])))
        ok, report = verify_bundled(wk, bundled, known={})
        assert not ok and report[0].startswith("kjv: "), report
        (bundled / "kjv.tsv.gz").write_bytes(sbh.to_gzip(tsv_bytes(base_rows)))
        key = (1, 1, 1)
        edited = [r for r in base_rows]
        edited[0] = [*edited[0][:3], "something else"]
        (bundled / "kjv.tsv.gz").write_bytes(sbh.to_gzip(tsv_bytes(edited)))
        ok, report = verify_bundled(wk, bundled, known={})
        assert not ok and any("UNEXPECTED DIFFERENCES" in l for l in report) and any("not pinned" in l for l in report), report
        ok, report = verify_bundled(wk, bundled, known={"kjv": {key}})
        assert ok and any("DIFFERS AS PINNED" in l for l in report), report
        (bundled / "kjv.tsv.gz").write_bytes(sbh.to_gzip(tsv_bytes(base_rows)))
        ok, report = verify_bundled(wk, bundled, known={"kjv": {key}})
        assert not ok and any("pinned but identical" in l for l in report), "a stale pin must fail the control"
        # --verify-bundled is wired through main(): exit 0 and a printed report when the control holds, exit 1 when not.
        with mock.patch.object(module, "BUNDLED_ASSETS", bundled), mock.patch.object(module, "KNOWN_DIVERGENCE", {}):
            code, printed = cli("--verify-bundled", work_dir=wk)
            assert code == 0 and printed.count("IDENTICAL") == 5, printed
            (bundled / "kjv.tsv.gz").write_bytes(sbh.to_gzip(tsv_bytes(edited)))
            code, printed = cli("--verify-bundled", work_dir=wk)
            assert code == 1 and "UNEXPECTED DIFFERENCES" in printed, printed
            (bundled / "kjv.tsv.gz").write_bytes(sbh.to_gzip(tsv_bytes(base_rows)))
        os_ = wk / "eng-kjv_usfm.zip"
        os_.unlink()
        raises(lambda: verify_bundled(wk, bundled, known={}), "missing")

    # No invisible or bidirectional character may sit in the source where a reviewer cannot see it. The tool that edits
    # these files once turned typed escapes into real characters, including U+202A and a BOM, so this is enforced.
    assert non_ascii_characters("abc") == [] and non_ascii_characters("caf" + chr(0xe9)) == [hex(0xe9)]
    assert set(invisible_characters("a" + chr(0x202a) + "b" + chr(0xfeff) + chr(0xa0) + chr(0) + chr(0x2028))) == \
        {hex(0x202a), hex(0xfeff), hex(0xa0), hex(0), hex(0x2028)}
    assert invisible_characters("plain text\twith a tab\nand a newline, " + chr(0xe9)) == [], "visible letters are fine"
    here = pathlib.Path(__file__).resolve().parent
    for script in ("build_translation_catalog.py", "translation_catalog_mutation_proof.py"):
        if (here / script).is_file():  # the mutation proof copies only some files
            source = (here / script).read_text(encoding="utf-8")
            assert not non_ascii_characters(source), f"{script} has non-ASCII characters {non_ascii_characters(source)}: write escapes"
    allowlist_hidden = invisible_characters(ALLOWLIST.read_text(encoding="utf-8"))
    assert not allowlist_hidden, f"invisible characters in the allowlist: {allowlist_hidden}"
    # The real pins are what was measured against eBible's USFM on 2026-10-04 (17 WEB rows, 20 WEBBE rows), every one
    # a real verse address. (That WEBBE = WEB + the NBSP rows is how the sets are BUILT, so it is not asserted.)
    assert (len(KNOWN_DIVERGENCE["web"]), len(KNOWN_DIVERGENCE["webbe"])) == (17, 20), "re-measure with --verify-bundled"
    assert all(1 <= b <= 66 and c >= 1 and v >= 1 and c <= CHAPTERS[b - 1] for s in KNOWN_DIVERGENCE.values() for b, c, v in s)
    assert OT_BOOKS == 39 and CANON[OT_BOOKS - 1] == "MAL" and CANON[OT_BOOKS] == "MAT", "the testament boundary"
    assert (PSALMS, HABAKKUK) == (CANON.index("PSA") + 1, CANON.index("HAB") + 1)
    print("build_translation_catalog self-test: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
