"""Extract public-domain WEB scripture passages (bundled in the repo) as TTS input texts."""
import gzip
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "..", "..", "..", "implementation", "desktop", "crates", "selahcue-scripture", "assets", "web.tsv.gz")

rows = {}
with gzip.open(WEB, "rt") as f:
    for line in f:
        b, c, v, t = line.rstrip("\n").split("\t", 3)
        rows[(int(b), int(c), int(v))] = t


def passage(b, c, v0, v1):
    return " ".join(rows[(b, c, v)] for v in range(v0, v1 + 1))


def clean(t):
    t = (
        t.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", ", ")
        .replace("¶", "")
    )
    return re.sub(r"\s+", " ", t).strip()


SEL = {
    "web_john3": [(43, 3, 1, 21)],
    "web_romans5": [(45, 5, 1, 11)],
    "web_luke15": [(42, 15, 11, 32)],
    "web_psalm23_103": [(19, 23, 1, 6), (19, 103, 1, 14)],
    "web_1cor13": [(46, 13, 1, 13)],
    "web_isaiah6_rev4": [(23, 6, 1, 8), (66, 4, 1, 11)],
    "web_matthew5": [(40, 5, 1, 16)],
    "web_psalm136": [(19, 136, 1, 26)],
}

os.makedirs(os.path.join(HERE, "texts"), exist_ok=True)
for name, parts in SEL.items():
    text = clean(" ".join(passage(*p) for p in parts))
    digits = re.findall(r"\d+", text)
    if digits:
        raise SystemExit(f"{name}: contains digits {digits}")
    with open(os.path.join(HERE, "texts", f"{name}.txt"), "w") as out:
        out.write(text + "\n")
    print(name, len(text.split()), "words")
