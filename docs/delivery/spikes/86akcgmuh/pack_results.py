"""Pack every decode (slice, cfg, text, ms, fallback passes) + the slice/manifest metadata into one
gzip so the spike's numbers can be re-scored without re-decoding (the audio itself is not kept)."""
import glob
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
rows = []
for p in sorted(glob.glob(os.path.join(HERE, "results", "*.jsonl"))):
    name = os.path.basename(p)
    if name.startswith("paced_"):
        try:
            rows.append({"file": name, "paced": json.loads(open(p).readline())})
        except ValueError:
            pass
        continue
    for line in open(p):
        r = json.loads(line)
        rows.append({"file": name, "slice": r["slice"], "cfg": r["cfg"], "text": r["text"],
                     "ms": round(r["ms"], 1), "passes": r.get("passes", 0),
                     "used_len": r.get("used_len")})
meta = {"manifest": [{k: v for k, v in r.items() if k != "wav"}
                     for r in json.load(open(os.path.join(HERE, "audio_manifest.json")))]}
for p in sorted(glob.glob(os.path.join(HERE, "slices_*.json"))):
    meta[os.path.basename(p)] = [{k: v for k, v in s.items() if k != "wav"}
                                 for s in json.load(open(p))]
with gzip.open(out, "wt") as f:
    json.dump({"meta": meta, "decodes": rows}, f)
print(len(rows), "rows ->", out, os.path.getsize(out), "bytes")
