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

# (what is being broken, the exact text to replace, what to replace it with)
MUTATIONS = [
    ("clean: keep the delimiter space after an opening marker",
     '_OPEN = re.compile(r"\\\\\\+?[A-Za-z][A-Za-z0-9]*[ \\t]?")', '_OPEN = re.compile(r"\\\\\\+?[A-Za-z][A-Za-z0-9]*")'),
    ("clean: collapse NBSP like str.split()", '_ASCII_WS.sub(" ", text).strip(" ")', '" ".join(text.split())'),
    ("clean: drop NFC", 'return unicodedata.normalize("NFC", _ASCII_WS', "return (lambda x: x)(_ASCII_WS"),
    ("parse: keep empty verses as rows", "        if text:\n            verses[key] = text",
     "        if True:\n            verses[key] = text"),
    ("parse: Psalm 119 \\qc label rule off",
     'if marker == "qc" and label == "PSA" and chapter == 119 and "\\\\v" not in line:', "if False:"),
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
    ("gate: ignore copyright drift",
     'if spec.get("expect_copyright", "\\0").lower() not in row["Copyright"].lower():', "if False:"),
    ("gate: ignore --require-cleared", 'elif require_cleared and spec["legal_review"] != "cleared":', "elif False:"),
    ("gate: ignore bundled-code collision", "if code in BUNDLED_CODES:", "if False:"),
    ("gate: ignore duplicate code", "        if code in seen:", "        if False:"),
    ("gate: ignore excluded list", 'if spec.get("ebible_id") in excluded:', "if False:"),
    ("gate: ignore code format", "if not CODE_RE.match(code):", "if False:"),
    ("gate: ignore ebible_id format", 'if not EBIBLE_ID_RE.match(spec.get("ebible_id", "")):', "if False:"),
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
            r = subprocess.run([sys.executable, TARGET, "--self-test"], cwd=tmp, capture_output=True, text=True,
                               timeout=120)
        caught = r.returncode != 0
        print(f"{'caught  ' if caught else 'SURVIVED'}  {name}")
        if not caught:
            bad.append(name)
    print(f"\n{len(MUTATIONS) - len(bad)}/{len(MUTATIONS)} mutations caught")
    if bad:
        print("NOT CAUGHT / NOT APPLIED: " + "; ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
