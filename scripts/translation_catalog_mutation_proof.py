#!/usr/bin/env python3
"""Mutation proof for scripts/build_translation_catalog.py's self-test (17tnw2b2jfy).

A self-test is only worth having if it fails when the thing it guards is broken. This breaks one guard
of the converter at a time (in a temporary copy; the real file is never touched) and requires
`--self-test` to go RED each time. A guard that can be removed with the self-test still green is a guard
nobody tests.

    python3 scripts/translation_catalog_mutation_proof.py

Exits 0 only if EVERY mutation is caught. Exits 1 if any survives, and also if a mutation can no longer be
applied: each entry names an exact line of the script, so a refactor that moves or rewrites that line makes
this fail loudly instead of quietly proving nothing. Update the entry with the refactor.

Not run by `make ci`: it spawns about fifty processes. Run it whenever the converter's guards change, and
paste the result in the review.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
TARGET = "build_translation_catalog.py"
TIMEOUT_SECONDS = 90  # the self-test takes about 1 s; a quadratic-regex mutant takes about 16 s before its time bound fires

# (what is being broken, the exact text to replace, what to replace it with)
MUTATIONS = [
    ("clean: keep the delimiter space after an opening marker", '(\\*|[ \\t]?)")', '(\\*|)")'),
    ("clean: collapse NBSP like str.split()", '_ASCII_WS.sub(" ", text).strip(" ")', '" ".join(text.split())'),
    ("clean: drop NFC", 'return unicodedata.normalize("NFC", _ASCII_WS', "return (lambda x: x)(_ASCII_WS"),
    ("parse: keep empty verses as rows", "        if text:\n            verses[key] = text",
     "        if True:\n            verses[key] = text"),
    ("parse: Psalm 119 \\qc label rule off",
     'if marker == "qc" and label == "PSA" and chapter == 119 and "\\\\v" not in line and (verse or 0) % 8 == 0:', "if False:"),
    ("parse: a Psalm 119 `\\qc` label is accepted anywhere in the psalm", " and (verse or 0) % 8 == 0:", ":"),
    ("parse: a Psalm 119 `\\qc` label needs no Hebrew letter", "_LABEL_SHAPE = re.compile(r\"[\\u0590-\\u05ff]+ [A-Za-z]", "_LABEL_SHAPE = re.compile(r\"(?:[\\u0590-\\u05ff]+ )?[A-Za-z]"),
    ("source: non-ASCII characters are not detected", "if ord(c) > 127})", "if ord(c) > 12700})"),
    ("source: bidirectional and format characters are not detected", '(kind in ("Cf", "Cc", "Zl", "Zp") and c not in "\\n\\t")', '(kind in ("Cc", "Zl", "Zp") and c not in "\\n\\t")'),
    ("source: non-ASCII spaces are not detected", '(kind == "Zs" and c != " ")', "(False)"),
    ("parse: accept verse bridges", 'if not re.fullmatch(r"\\d+", number):', "if False:"),
    ("parse: accept unknown line markers", "        elif marker is None or marker in _CHARS:", "        elif True:"),
    ("parse: skip chapter sequence check", "if not cm or int(cm.group(1)) != chapter + 1:", "if not cm:"),
    ("parse: allow duplicate verses", "            if (chapter, n) in parts:", "            if False:"),
    ("parse: allow verses out of order", "            if verse is not None and n <= verse:", "            if False:"),
    ("zip: no missing-book check", "    if missing:\n        problems.append", "    if False:\n        problems.append"),
    ("zip: no size caps",
     "        if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES or any(i.file_size > MAX_MEMBER_BYTES for i in infos):",
     "        if False:"),
    ("zip: no duplicate-book check", "            if n in books:\n                problems.append",
     "            if False:\n                problems.append"),
    ("convert: no verse-count pin", 'if (ot, nt) != (pinned.get("ot"), pinned.get("nt")):', "if False:"),
    ("convert: no heading-fusion oracle",
     'if len(h) >= 3 and (text == h or text.startswith(h + " ") or text.endswith(" " + h)):', "if False:"),
    ("convert: no English title-opener net", "if b == PSALMS and v == 1 and eng and _opens_with_title(text):",
     "if False:"),
    ("convert: no Psalm 119 label net",
     "if b == PSALMS and c == 119 and (_is_acrostic_label(text) or _ends_with_acrostic_label(text)):", "if False:"),
    ("convert: no Hab 3:19 note net",
     'if (b, c, v) == (HABAKKUK, 3, 19) and eng and "stringed instruments" in text:', "if False:"),
    ("convert: never strip the Hab note", 'if note and row is not None and row[3].endswith(" " + note):', "if False:"),
    ("convert: no residue check", "if not text or text != text.strip() or _RESIDUE.search(text):", "if False:"),
    ("convert: no starts-at-verse-1 check", "            if min(v for cc, v in verses if cc == c) != 1:",
     "            if False:"),
    ("convert: no chapter-count check", "        if got != list(range(1, CHAPTERS[n - 1] + 1)):", "        if False:"),
    ("convert: no Psalm 119 verse-count check", "if sum(1 for k in by_key if k[:2] == (PSALMS, 119)) != 176:",
     "if False:"),
    ("convert: never strip inline DBY labels", "row[3] = _strip_acrostic_label(row[3])", "pass"),
    ("gate: ignore licence permitted flag", 'elif not lic.get("permitted"):', "elif False:"),
    ("gate: ignore unknown licence", "        if lic is None:", "        if False:"),
    ("gate: ignore Redistributable", 'if row["Redistributable"] != "True":', "if False:"),
    ("gate: ignore downloadable", 'if row["downloadable"] != "True":', "if False:"),
    ("gate: ignore language", 'if row["languageCode"] != spec.get("language"):', "if False:"),
    ("gate: ignore copyright drift", 'elif _squash(expected) != _squash(row["Copyright"]):', "elif False:"),
    ("gate: ignore --require-cleared",
     'elif require_cleared and (only is None or code in only) and spec["legal_review"] != "cleared":', "elif False:"),
    ("gate: ignore bundled-code collision", "if code in BUNDLED_CODES:", "if False:"),
    ("gate: ignore duplicate code", "        if code in seen:", "        if False:"),
    ("gate: ignore excluded list", 'if spec.get("ebible_id") in excluded:', "if False:"),
    ("gate: ignore code format", "if not CODE_RE.fullmatch(code):", "if False:"),
    ("gate: code format accepts a trailing newline", "if not CODE_RE.fullmatch(code):", "if not CODE_RE.match(code):"),
    ("gate: ignore ebible_id format", 'if not (isinstance(spec.get("ebible_id"), str) and EBIBLE_ID_RE.fullmatch(spec["ebible_id"])):', "if False:"),
    ("gate: ebible_id format accepts a trailing newline", 'EBIBLE_ID_RE.fullmatch(spec["ebible_id"])', 'EBIBLE_ID_RE.match(spec["ebible_id"])'),
    ("gate: ignore missing catalogue row", "        if row is None:\n            why.append",
     "        if False:\n            why.append"),
    ("gate: ignore legal_review value", 'if spec.get("legal_review") not in LEGAL_REVIEW:', "if False:"),
    ("fetch: no size cap", "                if total > max_bytes:", "                if False:"),
    ("fetch: leave .part behind", "    finally:\n        with contextlib.suppress(OSError):\n            part.unlink()",
     "    finally:\n        pass"),
    ("build: write despite failures", "    if problems:\n        raise Mismatch(problems)\n    catalog = {",
     "    catalog = {"),
    ("build: ignore --only typos", "    if only and len(specs) != len(set(only)):", "    if False:"),
    ("write_all: leave temp files after a staging failure",
     "        for tmp in staged:\n            with contextlib.suppress(OSError):\n                tmp.unlink()", "        pass"),
    ("verify_bundled: always ok", "        ok = differ == expected", "        ok = True"),
    ("verify_bundled: ignore stale pins", "        for k in sorted(differ ^ expected)[:8]:",
     "        for k in sorted(differ - expected)[:8]:"),
    # Added after Shadow's review of PR 181: the denial-of-service and zip-bound guards.
    ("clean: `\\w` takes `\\s+` again (quadratic on an unclosed marker)", 'r"\\\\\\+?w\\s([^|\\\\]*?)', 'r"\\\\\\+?w\\s+([^|\\\\]*?)'),
    ("notes: an unterminated note is accepted", "        if end < 0:\n            raise Mismatch(", "        if False:\n            raise Mismatch("),
    ("zip: members are read without the cap", "member.read(MAX_MEMBER_BYTES + 1)", "member.read()"),
    ("zip: no check on bytes actually read", "            if len(raw) > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:", "            if False:"),
    ("zip: no member-count cap", "    if len(members) > MAX_MEMBERS:", "    if False:"),
    ("licence: no member-count cap on the licence-page path",
     "        _refuse_too_many_members(zip_path, everything)\n        info = next(", "        info = next("),
    ("zip: non-UTF-8 member is a traceback", "            except UnicodeDecodeError as e:", "            except ZeroDivisionError as e:"),
    ("zip: a corrupt member is a traceback", "            except (zipfile.BadZipFile, zlib.error,", "            except (zlib.error,"),
    # Added after the review round on PR 181 (Quinn B1/B2, Cody F1, M1-M5, Shadow C1/C2): inline markers, note spacing,
    # the licence page, and clause-level mutants (a guard is not tested because its whole `if` is, only its clauses).
    ("notes: `\\fm` is not a note", r"\\(f|fe|ef|fm|x|ex|va|vp|ca|fig)\s", r"\\(f|fe|ef|x|ex|va|vp|ca|fig)\s"),
    ("notes: a note may run on past a verse or chapter marker", "runs_on = _NOTE_BREAK.search(inner) or", "runs_on = None or"),
    ("notes: a note may contain another note of its own kind", ' or re.search(r"\\\\" + kind + r"\\s", inner)', " or None"),
    ("notes: keep the space before a note when punctuation follows", "        if _closes_phrase(text, ahead):", "        if False:"),
    ("notes: do not look past inline markers for the punctuation", "            ahead = marker.end()", "            break"),
    ("notes: keep the space after a note when punctuation follows", "            pos = _SPACES.match(text, pos).end()", "            pos = pos"),
    ("notes: the look-ahead copies the rest of the text per note (quadratic)", "        ahead = _SPACES.match(text, ahead).end()",
     '        ahead = len(text) - len(text[ahead:].lstrip(" \\t"))'),
    ("notes: a word that begins with an apostrophe loses its space (the Hausa regression)", "        return not (following and following.isalnum())", "        return True"),
    ("notes: `;` does not close a phrase", '_CLOSING_PUNCT = ",;:.!?)\\u201d\\u2019"', '_CLOSING_PUNCT = ",:.!?)\\u201d\\u2019"'),
    ("notes: `:` does not close a phrase", '_CLOSING_PUNCT = ",;:.!?)\\u201d\\u2019"', '_CLOSING_PUNCT = ",;.!?)\\u201d\\u2019"'),
    ("notes: `!` does not close a phrase", '_CLOSING_PUNCT = ",;:.!?)\\u201d\\u2019"', '_CLOSING_PUNCT = ",;:.?)\\u201d\\u2019"'),
    ("notes: `)` does not close a phrase", '_CLOSING_PUNCT = ",;:.!?)\\u201d\\u2019"', '_CLOSING_PUNCT = ",;:.!?\\u201d\\u2019"'),
    ("notes: only one empty piece is dropped before punctuation", '            while out and not out[-1].rstrip(" \\t"):', '            if out and not out[-1].rstrip(" \\t"):'),
    ("notes: no guard on an empty output", '            if out:\n                out[-1] = out[-1].rstrip(" \\t")', '            out[-1] = out[-1].rstrip(" \\t")'),
    ("notes: a tab before a note is not spacing", 'out[-1] = out[-1].rstrip(" \\t")', 'out[-1] = out[-1].rstrip(" ")'),
    ("notes: the look-ahead does not cross a closing marker", '_MARKER_AHEAD = re.compile(r"[ \\t]*\\\\\\+?[A-Za-z][A-Za-z0-9]*(?:\\*|[ \\t]?)")', '_MARKER_AHEAD = re.compile(r"[ \\t]*\\\\\\+?[A-Za-z][A-Za-z0-9]*(?:[ \\t]?)")'),
    ("notes: the look-ahead does not cross a `+` marker", '_MARKER_AHEAD = re.compile(r"[ \\t]*\\\\\\+?[A-Za-z]', '_MARKER_AHEAD = re.compile(r"[ \\t]*\\\\[A-Za-z]'),
    ("notes: `ex`, `va`, `vp` and `ca` are not notes", "|x|ex|va|vp|ca|fig)\\s", "|x|fig)\\s"),
    ("inline: `th` and `thr` table cells are refused", 'tr|tc\\d|tcr\\d|th\\d|thr\\d")', 'tr|tc\\d|tcr\\d")'),
    ("parse: a heading's continuation line is not cleaned", 'last_heading[1] = tidy(last_heading[1] + " " + line, f"chapter {chapter} heading")', 'last_heading[1] = last_heading[1] + " " + line'),
    ("convert: English-only checks run on every language", '    eng = spec.get("language") == "eng"', "    eng = True"),
    ("catalog: keys are not sorted", "sort_keys=True", "sort_keys=False"),
    ("zip: a loose `.usfm` suffix match", 'if i.filename.lower().endswith(".usfm")', 'if ".usfm" in i.filename.lower()'),
    ("csv: the UTF-8 BOM is not skipped", 'text = pathlib.Path(path).read_text(encoding="utf-8-sig")', 'text = pathlib.Path(path).read_text(encoding="utf-8")'),
    ("csv: a csv error is a traceback", "except (OSError, UnicodeDecodeError, csv.Error, KeyError) as e:", "except (OSError, UnicodeDecodeError, KeyError) as e:"),
    ("csv: a missing column is a traceback", "except (OSError, UnicodeDecodeError, csv.Error, KeyError) as e:", "except (OSError, UnicodeDecodeError, csv.Error) as e:"),
    ("fetch: a redirect to plain http is followed", '        if urllib.parse.urlsplit(newurl).scheme != "https":', "        if False:"),
    ("fetch: the default opener follows any redirect", "_OPENER = urllib.request.build_opener(_HttpsOnlyRedirects)", "_OPENER = urllib.request.build_opener()"),
    ("fetch: a planted `.part` symlink is not removed first", '            part.unlink()\n        with opener(req, timeout=60) as resp, open(part, "xb") as out:', '            pass\n        with opener(req, timeout=60) as resp, open(part, "xb") as out:'),
    ("write_all: a planted staging symlink is followed", 'with open(tmp, "xb") as staging:', 'with open(tmp, "wb") as staging:'),
    ("write_all: a file it did not create is removed on failure",
     '            with open(tmp, "xb") as staging:\n                staged.append(tmp)\n                staging.write(data)',
     '            staged.append(tmp)\n            with open(tmp, "xb") as staging:\n                staging.write(data)'),
    ("main: `--refresh` is not passed on", "refresh=args.refresh)", "refresh=False)"),
    ("main: `--require-cleared` is not passed on", "args.require_cleared, args.base_url, args.offline,", "False, args.base_url, args.offline,"),
    ("main: `--offline` is not passed on", "args.require_cleared, args.base_url, args.offline,", "args.require_cleared, args.base_url, False,"),
    ("main: `--base-url` is not passed on", "args.require_cleared, args.base_url, args.offline,", "args.require_cleared, None, args.offline,"),
    ("main: `--only` is not passed on", "args.out_dir, args.only,", "args.out_dir, None,"),
    ("main: `--allowlist` is ignored", "build(load_allowlist(args.allowlist)", "build(load_allowlist(ALLOWLIST)"),
    ("main: `--verify-bundled` always exits 0", "            return 0 if ok else 1", "            return 0"),
    ("main: `--verify-bundled` prints nothing", '            print("\\n".join(report))', "            pass"),
    ("notes: closing quotes are not closing punctuation", '_CLOSING_PUNCT = ",;:.!?)\\u201d\\u2019"', '_CLOSING_PUNCT = ",;:.!?)"'),
    ("notes: an opening quote counts as closing punctuation", '_CLOSING_PUNCT = ",;:.!?)\\u201d\\u2019"', '_CLOSING_PUNCT = ",;:.!?)\\u201d\\u2019\\u201c"'),
    ("inline: unknown markers are stripped, not refused", "        if m.group(1) not in _CHARS and not _TABLE_CELL.fullmatch(m.group(1)):", "        if False:"),
    ("inline: table cell markers are refused", "        if m.group(1) not in _CHARS and not _TABLE_CELL.fullmatch(m.group(1)):", "        if m.group(1) not in _CHARS:"),
    ("parse: a `\\qc` line in Psalm 119 is always a label", "            if _LABEL_SHAPE.fullmatch(rest):", "            if True:"),
    ("parse: a note refusal loses its book", '        raise Mismatch([f"{label}: {p}" for p in e.problems])', "        raise"),
    ("convert: heading equal to the whole verse is not fused", 'if len(h) >= 3 and (text == h or text.startswith(h + " ") or text.endswith(" " + h)):',
     'if len(h) >= 3 and (text.startswith(h + " ") or text.endswith(" " + h)):'),
    ("convert: heading at the end of the verse is not fused", 'if len(h) >= 3 and (text == h or text.startswith(h + " ") or text.endswith(" " + h)):',
     'if len(h) >= 3 and (text == h or text.startswith(h + " ")):'),
    ("convert: an untrimmed verse is accepted", "if not text or text != text.strip() or _RESIDUE.search(text):", "if not text or _RESIDUE.search(text):"),
    ("convert: control characters are accepted", '_RESIDUE = re.compile(r"[\\[\\]\\u00b6*|\\\\\\x00-\\x1f\\x7f]")', '_RESIDUE = re.compile(r"[\\[\\]\\u00b6*|\\\\]")'),
    ("zip: the declared TOTAL is not capped", "if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES or any(", "if any("),
    ("zip: sidecars are read as books",
     ' and not i.filename.startswith("__MACOSX/") and not pathlib.PurePosixPath(i.filename).name.startswith("._")]', "]"),
    ("zip: `.USFM` is not a book", 'if i.filename.lower().endswith(".usfm")', 'if i.filename.endswith(".usfm")'),
    ("gate: the licence_text pin is optional", 'if not (isinstance(phrases, list) and phrases and all(isinstance(p, str) and p.strip() for p in phrases)):', "if False:"),
    ("gate: expect_copyright is optional", "if not isinstance(expected, str) or not expected.strip():", "if False:"),
    ("gate: `--require-cleared` ignores which entries are built", "(only is None or code in only)", "True"),
    ("gate: copyright compare is case- and space-sensitive", '    return " ".join(text.casefold().split())', "    return text"),
    ("licence: the page is never checked", "            check_licence_text(zip_path, spec)", "            pass"),
    ("licence: required phrases are not required", "if not any(_squash(p) in form for form in forms)]", "if False]"),
    ("licence: forbidden phrases are allowed", "for p in _FORBIDDEN_LICENCE_TEXT if any(p in form for form in forms)]", "for p in _FORBIDDEN_LICENCE_TEXT if False]"),
    ("licence: a missing page is accepted", "    if forms is None:", "    if False:"),
    ("licence: no cap on the page size", "    if len(raw) > MAX_LICENCE_PAGE_BYTES:", "    if False:"),
    ("licence: direction marks are not removed", 'forms.append(_squash("".join(c for c in text if unicodedata.category(c) != "Cf")))', "forms.append(_squash(text))"),
    ("licence: HTML entities are not decoded", 'text = html.unescape(_HTML_TAG.sub(glue, raw.decode("utf-8", "replace")))', 'text = _HTML_TAG.sub(glue, raw.decode("utf-8", "replace"))'),
    ("licence: the tag regex is quadratic again", '_HTML_TAG = re.compile(r"<[^<>]*>")', '_HTML_TAG = re.compile(r"<[^>]+>")'),
    ("licence: only the tag-as-space form is checked", 'for glue in (" ", ""):', 'for glue in (" ",):'),
    ("licence: only the tag-as-nothing form is checked", 'for glue in (" ", ""):', 'for glue in ("",):'),
    ("licence: `noncommercial` is allowed", '_FORBIDDEN_LICENCE_TEXT = ("all rights reserved", "noncommercial",', '_FORBIDDEN_LICENCE_TEXT = ("all rights reserved",'),
    ("licence: `noderivs` is allowed", '"noderivs", "no derivs", "by-nc", "not public domain")', '"no derivs", "by-nc", "not public domain")'),
    ("licence: `no derivs` is allowed", '"noderivs", "no derivs", "by-nc", "not public domain")', '"noderivs", "by-nc", "not public domain")'),
    ("licence: `by-nc` is allowed", '"noderivs", "no derivs", "by-nc", "not public domain")', '"noderivs", "no derivs", "not public domain")'),
    ("licence: `not public domain` is allowed", '"noderivs", "no derivs", "by-nc", "not public domain")', '"noderivs", "no derivs", "by-nc")'),
    ("licence: a corrupt zip is a traceback", "    except (OSError, zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError) as e:\n        raise Mismatch([f\"{zip_path}: cannot read the licence page",
     "    except (zlib.error,) as e:\n        raise Mismatch([f\"{zip_path}: cannot read the licence page"),
    ("allowlist: schema is not checked", 'if data.get("schema") != 1:', "if False:"),
    ("build: a used output folder is accepted", "    if used:", "    if False:"),
    ("build: a file as the output folder is a traceback", "(not out.is_dir() or any(out.iterdir()))", "(any(out.iterdir()))"),
    ("build: an unreadable output folder is a traceback", "    except OSError as e:  # e.g. a folder this user cannot read", "    except ZeroDivisionError as e:  # e.g. a folder this user cannot read"),
    ("build: a publish run does not refetch at all", "    fresh = refresh or (require_cleared and not offline)", "    fresh = refresh"),
    ("build: a publish run does not refetch the catalogue", 'ensure(work, "translations.csv", CATALOG_CSV_URL, offline, opener, refresh=fresh)', 'ensure(work, "translations.csv", CATALOG_CSV_URL, offline, opener)'),
    ("build: a publish run builds from a cached zip", "                              offline, opener, refresh=fresh)", "                              offline, opener)"),
    ("ensure: --refresh does not refetch", "    if refresh or not path.is_file():", "    if not path.is_file():"),
    ("catalog: the catalogue's own digest is not recorded", '"translations_csv_sha256": sha256_file(csv_path),', '"translations_csv_sha256": "",'),
    ("catalog: attribution is dropped", '"attribution": spec.get("attribution"),', '"attribution": None,'),
    ("catalog: trademark note is dropped", '"trademark_note": spec.get("trademark_note"),', '"trademark_note": None,'),
    ("catalog: modification notice is dropped", '"modifications": spec.get("modifications"),', '"modifications": None,'),
    ("catalog: share-alike flag is wrong", '"share_alike": licence["share_alike"]}', '"share_alike": False}'),
    ("catalog: attribution-required flag is wrong", '"attribution_required": licence["attribution_required"],', '"attribution_required": False,'),
    ("catalog: eBible update date is dropped", '"ebible_update_date": row["UpdateDate"],', '"ebible_update_date": "",'),
    ("catalog: source URL is dropped", '''"url": f"{EBIBLE}/{spec['ebible_id']}_usfm.zip",''', '"url": "",'),
    ("catalog: entries are not sorted", 'sorted(entries, key=lambda e: e["code"])', "entries"),
    ("catalog: non-ASCII is escaped", "ensure_ascii=False,", "ensure_ascii=True,"),
    ("fetch: no timeout", "opener(req, timeout=60)", "opener(req, timeout=6000)"),
    ("fetch: no User-Agent", 'headers={"User-Agent": USER_AGENT}', "headers={}"),
    ("catalog: wrong digest", '"sha256": hashlib.sha256(gz).hexdigest(),', '"sha256": hashlib.sha256(gz + b"x").hexdigest(),'),
    ("catalog: drop the omitted-verse count", '"omitted_verses": len(omitted),', '"omitted_verses": 0,'),
]


def main():
    text = (HERE / TARGET).read_text(encoding="utf-8")
    bad = []
    for name, find, repl in MUTATIONS:
        if text.count(find) != 1:
            print(f"CANNOT APPLY ({text.count(find)} matches)  {name}")
            bad.append(name)
            continue
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            for f in ("strip_bible_headings.py", "translation_allowlist.json"):
                shutil.copy(HERE / f, tmp / f)
            (tmp / TARGET).write_text(text.replace(find, repl), encoding="utf-8")
            try:
                r = subprocess.run([sys.executable, TARGET, "--self-test"], cwd=tmp, capture_output=True, text=True,
                                   timeout=TIMEOUT_SECONDS)
                caught = r.returncode != 0
            except subprocess.TimeoutExpired:
                caught = True  # a mutant that hangs (an unbounded loop or a quadratic regex) is not a green self-test
        print(f"{'caught  ' if caught else 'SURVIVED'}  {name}")
        if not caught:
            bad.append(name)
    print(f"\n{len(MUTATIONS) - len(bad)}/{len(MUTATIONS)} mutations caught")
    if bad:
        print("NOT CAUGHT / NOT APPLIED: " + "; ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
