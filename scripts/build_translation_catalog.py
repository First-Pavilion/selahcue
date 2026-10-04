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
still REFUSES rather than guesses: an unknown line marker, a verse bridge (`\\v 3-4`), text outside a
verse, a missing or extra chapter, an empty verse, or leftover markup aborts the whole run.

NORMALISATION (the same rules the bundled Bibles satisfy -- see selahcue-scripture's
tests/test_scripture_data.rs): no `[ ] ¶ *`; no psalm title or Psalm 119 letter label in any verse;
Habakkuk 3:19 without its musical note; numbered verses that read like titles (Hab 3:1, Isa 38:9,
Song 1:1) stay; canonical Protestant numbering 1..66 with deuterocanon, intros and glossaries
dropped. Text is also NFC-normalised so combining marks (Yoruba and Igbo dot-below letters with tone
marks) have one stable form for search and rendering.

THE LICENCE GATE. Each allowlist entry names a licence from the allowlist's own registry. The build
fails unless: the licence is marked `permitted`; eBible's catalogue row says `Redistributable=True`
and `downloadable=True`; the row's copyright text still contains the entry's `expect_copyright`
(so an upstream licence change stops the run instead of being mirrored); and, with
`--require-cleared` (use it for the publish run), every entry's `legal_review` is `cleared`.

    python3 scripts/build_translation_catalog.py --work-dir DIR --out-dir DIR [--only BSB ...]
    python3 scripts/build_translation_catalog.py --work-dir DIR --verify-bundled
    python3 scripts/build_translation_catalog.py --self-test

`--work-dir` caches the downloaded `*_usfm.zip` files and eBible's `translations.csv`; an existing
file is used as is (no network), a missing one is fetched. `--verify-bundled` is the positive control:
it converts the USFM of the five bundled Bibles and compares the result with the shipped assets, which
proves the converter itself and not just the new translations. Not run by `make ci`: it needs the
network. `--self-test` needs none and is what `make ci` runs.

Output is byte-reproducible for a given zlib (the gzip header carries no timestamp or filename);
`catalog.json` contains no timestamps. If bytes ever differ on another machine's zlib, compare the
DECOMPRESSED TSV, not the sha.
"""
import argparse
import contextlib
import csv
import gzip
import hashlib
import io
import json
import pathlib
import re
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile

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

# Bounds on untrusted input: a zip from the network is data, not something to trust.
MAX_ZIP_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 24 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
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
# Notes and alternate numbering, which may span lines: dropped whole before any line is read.
_NOTES = re.compile(r"\\(f|fe|ef|x|ex|va|vp|ca|fig)\s.*?\\\1\*", re.S)
_VERSE_TOKEN = re.compile(r"\\v\s+(\S+)\s*")
_WORD = re.compile(r"\\\+?w\s+([^|\\]*?)(?:\|[^\\]*)?\\\+?w\*")  # \w word|strong="H1"\w*  ->  word
_ASCII_WS = re.compile(r"[ \t\r\n\f\v]+")
_CLOSE = re.compile(r"\\\+?[A-Za-z][A-Za-z0-9]*\*")  # a closing marker, e.g. \add*
_OPEN = re.compile(r"\\\+?[A-Za-z][A-Za-z0-9]*[ \t]?")  # an opening marker and its one delimiter space
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
_RESIDUE = re.compile(r"[\[\]¶*|\\]")


# --- the converter -----------------------------------------------------------------------------
def clean(text):
    """USFM inline markup -> plain text: notes, `\\w` words, every marker, `[ ] ¶ *`, whitespace; NFC.

    The single space after an OPENING marker is USFM's delimiter, not text: `(\\add is\\add* it` reads
    "(is it". sbh.clean_usfm keeps that space (it never mattered for matching VPL-derived rows), so
    reading USFM directly needs its own cleaner or every `(\\add ...` gains a stray space.
    """
    text = _NOTES.sub("", text)
    text = _WORD.sub(r"\1", text)
    text = _CLOSE.sub("", text)
    text = _OPEN.sub("", text)
    text = text.translate({ord(c): None for c in "[]¶*"})
    # ASCII whitespace only: eBible puts a no-break space between nested quote marks (`’ ”`) so the
    # closing quote cannot wrap onto its own line, and the bundled Bibles keep it.
    return unicodedata.normalize("NFC", _ASCII_WS.sub(" ", text).strip(" "))


def parse_book(usfm, label):
    """One USFM book -> ({(chapter, verse): text}, [(chapter, heading)], [omitted (chapter, verse)]).

    Verses with a number but no text are returned as omitted, not as rows: the shipped Bibles leave
    them out the same way (WEB has 31,103 `\\v` lines and 31,098 rows). Raises Mismatch on anything odd."""
    problems = []

    def bad(msg):
        problems.append(f"{label}: {msg}")

    verses, headings, parts = {}, [], {}
    chapter, verse, skipping, last_heading = 0, None, False, None
    for raw in _NOTES.sub("", usfm).splitlines():
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
        # elsewhere, so the rule is scoped to Psalm 119 and to a line with no verse in it. It is structural
        # on purpose: a list of letter names missed ASV's own spelling "HHETH" and fused it into 119:56.
        if marker == "qc" and label == "PSA" and chapter == 119 and "\\v" not in line:
            skipping, last_heading = True, [chapter, clean(line[m.end():])]
            headings.append(last_heading)
            continue
        if marker is not None and _SKIP.fullmatch(marker):
            skipping, last_heading = True, None
            if marker in _ORACLE_MARKERS:
                last_heading = [chapter, clean(line[m.end():])]
                headings.append(last_heading)
            continue
        if marker == "v":
            body = line
        elif marker is not None and _TEXT.fullmatch(marker):
            body = line[m.end():]
        elif marker is None or marker in _CHARS:
            if skipping:  # a continuation line of the heading that is being skipped
                if last_heading is not None:
                    last_heading[1] = clean(last_heading[1] + " " + line)
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
        text = clean(" ".join(chunks))
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
    if text.endswith("SIN AND SHIN"):
        return True
    last = (text.split() or [""])[-1]
    return last.rstrip(".") in ACROSTIC_LETTERS


def read_usfm_zip(zip_path):
    """{book number: usfm text} for the 66 canonical books in an eBible USFM zip, bounded and read-only."""
    problems, books = [], {}
    try:
        zf = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as e:
        raise Mismatch([f"{zip_path}: not a readable zip ({type(e).__name__}: {e})"])
    with zf:
        infos = [i for i in zf.infolist() if i.filename.lower().endswith(".usfm")]
        if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES or any(i.file_size > MAX_MEMBER_BYTES for i in infos):
            raise Mismatch([f"{zip_path}: USFM members exceed the size caps ({MAX_MEMBER_BYTES} each, "
                            f"{MAX_TOTAL_BYTES} total); refusing a possible zip bomb"])
        for info in infos:
            text = zf.read(info).decode("utf-8-sig")
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
    text = pathlib.Path(path).read_text(encoding="utf-8-sig")
    return {r["translationId"]: r for r in csv.DictReader(io.StringIO(text))}


def gate(allow, rows, require_cleared):
    """The licence gate. Returns nothing; raises Mismatch naming EVERY entry that fails and why."""
    problems, seen = [], set()
    licences = allow.get("licences", {})
    excluded = {e["ebible_id"] for e in allow.get("excluded", [])}
    for spec in allow["translations"]:
        code = spec.get("code", "?")
        why = []
        if spec.get("ebible_id") in excluded:
            why.append("is on the allowlist's own excluded list")
        if not CODE_RE.match(code):
            why.append("code must match ^[A-Z][A-Z0-9-]{1,15}$")
        if code in BUNDLED_CODES:
            why.append("code collides with a bundled translation")
        if code in seen:
            why.append("duplicate code")
        seen.add(code)
        if not EBIBLE_ID_RE.match(spec.get("ebible_id", "")):
            why.append("ebible_id is not a plain identifier")
        lic = licences.get(spec.get("licence"))
        if lic is None:
            why.append(f"licence {spec.get('licence')!r} is not in the allowlist's registry")
        elif not lic.get("permitted"):
            why.append(f"licence {spec['licence']!r} is not permitted")
        if spec.get("legal_review") not in LEGAL_REVIEW:
            why.append("legal_review must be 'cleared' or 'pending'")
        elif require_cleared and spec["legal_review"] != "cleared":
            why.append("legal_review is still pending (--require-cleared)")
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
            if spec.get("expect_copyright", "\0").lower() not in row["Copyright"].lower():
                why.append(f"eBible copyright is now {row['Copyright']!r}, which no longer contains "
                           f"{spec.get('expect_copyright')!r}")
        if why:
            problems.append(f"{code}: " + "; ".join(why))
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
        "modifications": spec.get("modifications"),
        "legal_review": spec["legal_review"],
        "source": {"ebible_id": spec["ebible_id"], "title": row["title"], "copyright": row["Copyright"],
                   "ebible_update_date": row["UpdateDate"], "usfm_zip_sha256": sha256_file(zip_path)},
    }


def fetch(url, dest, opener=urllib.request.urlopen, max_bytes=MAX_ZIP_BYTES):
    """Download `url` to `dest` through a .part file with a hard size cap; never leaves a partial file."""
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        total = 0
        with opener(req, timeout=60) as resp, open(part, "wb") as out:
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


def ensure(work, name, url, offline, opener):
    path = work / name
    if not path.is_file():
        if offline:
            raise Mismatch([f"missing {path} and --offline was given"])
        fetch(url, path, opener)
    return path


def build(allow, work, out, only=None, require_cleared=False, base_url=None, offline=False,
          opener=urllib.request.urlopen):
    """The whole job. Everything is computed before any file is written; a failure writes nothing."""
    work.mkdir(parents=True, exist_ok=True)
    csv_path = ensure(work, "translations.csv", CATALOG_CSV_URL, offline, opener)
    rows_by_id = load_catalog_csv(csv_path)
    gate(allow, rows_by_id, require_cleared)
    specs = [s for s in allow["translations"] if not only or s["code"] in only]
    if only and len(specs) != len(set(only)):
        raise Mismatch([f"--only names codes that are not in the allowlist: {sorted(set(only) - {s['code'] for s in specs})}"])
    outputs, entries, problems = {}, [], []
    for spec in specs:
        try:
            zip_path = ensure(work, f"{spec['ebible_id']}_usfm.zip", f"{EBIBLE}/{spec['ebible_id']}_usfm.zip",
                              offline, opener)
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
    catalog = {"schema": 1, "base_url": base_url, "translations": sorted(entries, key=lambda e: e["code"])}
    outputs["catalog.json"] = (json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    write_all(out, outputs)
    return catalog


def write_all(out, files):
    """Stage every file, then rename: a failure while staging removes what was staged and changes nothing."""
    out.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for name, data in files.items():
            tmp = out / (name + ".tmp")
            staged.append(tmp)
            tmp.write_bytes(data)
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
#   selah:    the VPL import put a space in "Lord— Selah—"; the USFM has none.
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
    ap.add_argument("--verify-bundled", action="store_true", help="positive control against the five bundled assets")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.work_dir:
        ap.error("--work-dir is required")
    try:
        if args.verify_bundled:
            ok, report = verify_bundled(args.work_dir)
            print("\n".join(report))
            return 0 if ok else 1
        if not args.out_dir:
            ap.error("--out-dir is required to build")
        catalog = build(load_allowlist(args.allowlist), args.work_dir, args.out_dir, args.only,
                        args.require_cleared, args.base_url, args.offline)
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


def _fixture_zip(path, patch=None, drop=(), duplicate=()):
    patch = patch or {}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("00-FRT.usfm", "\\id FRT front matter\n\\mt1 Front\n")
        zf.writestr("99-TOB.usfm", "\\id TOB deuterocanon\n\\c 1\n\\p\n\\v 1 Not in the canon.\n")
        zf.writestr("style.css", "body {}")
        for n in range(1, 67):
            if CANON[n - 1] not in drop:
                zf.writestr(f"{n:02d}-{CANON[n - 1]}.usfm", _fixture_book(n, patch))
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
                 "expect_copyright": "public domain", "legal_review": "cleared", "verses": counts,
                 "hab_3_19_note": HAB_NOTE}

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
                ({}, {"Copyright": "Copyright (c) Somebody"}, "no longer contains"),
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
        fetch("https://example.invalid/x", dest, serve(b"hello"))
        assert dest.read_bytes() == b"hello" and not list(d.glob("*.part"))
        big = d / "big.bin"
        raises(lambda: fetch("https://example.invalid/big", big, serve(b"x" * 200_000), max_bytes=100_000), "cap")
        assert not big.exists() and not list(d.glob("*.part")), "an over-cap download leaves nothing behind"

        def refuse(req, timeout):
            raise OSError("connection refused")

        raises(lambda: fetch("https://example.invalid/y", d / "y.bin", refuse), "could not download")
        assert not (d / "y.bin").exists() and not list(d.glob("*.part"))

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
        assert json.loads((out / "catalog.json").read_text())["translations"][0]["code"] == "FIX"
        assert gzip.decompress(gz) == tsv_bytes(convert(work / "fixbible_usfm.zip", spec)[0])
        first = {p.name: p.read_bytes() for p in out.iterdir()}
        build(allow(), work, d / "out2", offline=True, base_url="https://mirror.example/bibles")
        assert (d / "out2" / "fix.tsv.gz").read_bytes() == first["fix.tsv.gz"], "byte-reproducible"
        assert json.loads((d / "out2" / "catalog.json").read_text())["base_url"] == "https://mirror.example/bibles"
        raises(lambda: build(allow(legal_review="pending"), work, d / "out3", require_cleared=True, offline=True),
               "--require-cleared")
        raises(lambda: build(allow(), work, d / "out3", only=["NOPE"], offline=True), "not in the allowlist")
        assert not (d / "out3").exists(), "a refused run writes nothing at all"
        raises(lambda: build(allow(), d / "empty", d / "out3", offline=True), "--offline was given")
        # A translation that deliberately omits a verse: counted in the catalogue, not mistaken for a row.
        _fixture_zip(work / "fixbible_usfm.zip", {"GEN": lambda t: t.replace("\\v 2 GEN 1:2 text.", "\\v 2")})
        gap_cat = build(allow(verses={"ot": counts["ot"] - 1, "nt": counts["nt"]}), work, d / "out4", offline=True)
        assert gap_cat["translations"][0]["omitted_verses"] == 1 and gap_cat["translations"][0]["verses"]["ot"] == counts["ot"] - 1
        _fixture_zip(work / "fixbible_usfm.zip")
        # A failing translation aborts the whole run and leaves existing output untouched.
        _fixture_zip(work / "fixbible_usfm.zip", {"PSA": lambda t: t.replace("\\v 8 PSA 119:8 text.", "\\v 8 PSA 119:8 text. BETH")})
        raises(lambda: build(allow(), work, out, offline=True), "FIX: ")
        assert {p.name: p.read_bytes() for p in out.iterdir()} == first, "a failed run changed existing output"
        # Staging failure: a directory squats on a temp name; nothing is renamed, no temp file is left.
        stage = d / "stage"
        (stage / "catalog.json.tmp").mkdir(parents=True)
        raises(lambda: write_all(stage, {"a.bin": b"1", "catalog.json": b"2"}), "nothing was written")
        assert not (stage / "a.bin").exists() and not (stage / "a.bin.tmp").exists() and not (stage / "catalog.json").exists()

        # ---- main(): the command line end to end ----
        _fixture_zip(work / "fixbible_usfm.zip")
        (d / "allow.json").write_text(json.dumps(allow()), encoding="utf-8")
        argv, buf = sys.argv, io.StringIO()
        sys.argv = ["x", "--allowlist", str(d / "allow.json"), "--work-dir", str(work), "--out-dir", str(d / "cli"), "--offline"]
        try:
            with contextlib.redirect_stdout(buf):
                assert main() == 0
            assert "FIX" in buf.getvalue() and (d / "cli" / "catalog.json").is_file()
            sys.argv = ["x", "--allowlist", str(d / "allow.json"), "--work-dir", str(d / "nowhere"), "--out-dir", str(d / "cli2"),
                        "--offline"]
            with contextlib.redirect_stdout(io.StringIO()):
                assert main() == 1, "a refused run exits non-zero"
        finally:
            sys.argv = argv

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
        os_ = wk / "eng-kjv_usfm.zip"
        os_.unlink()
        raises(lambda: verify_bundled(wk, bundled, known={}), "missing")

    # The real pins are internally consistent: WEBBE differs from WEB only by the NBSP rows.
    assert KNOWN_DIVERGENCE["webbe"] - KNOWN_DIVERGENCE["web"] == _NBSP and KNOWN_DIVERGENCE["web"] < KNOWN_DIVERGENCE["webbe"]
    assert all(1 <= b <= 66 and c >= 1 and v >= 1 for s in KNOWN_DIVERGENCE.values() for b, c, v in s)
    print("build_translation_catalog self-test: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
