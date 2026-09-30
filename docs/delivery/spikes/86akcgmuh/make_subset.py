"""Build the lever-sweep subset from the baseline runs.

hard    = every intelligible slice (forced + onset10) where the production config looped OR
          whisper.cpp's temperature fallback fired (passes > 1)
control = a fixed-seed random sample of 80 intelligible slices where production was clean,
          so a lever that fixes loops but damages ordinary text shows up as 'worse'.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sets = [("slices_forced.json", "results/forced_base.jsonl"),
        ("slices_onset10.json", "results/onset_base.jsonl")]
hard, clean, allslices = [], [], {}
for sl, rp in sets:
    for s in json.load(open(os.path.join(HERE, sl))):
        allslices[s["id"]] = s
    res = analyze.score(os.path.join(HERE, sl), os.path.join(HERE, "audio_manifest.json"),
                        [os.path.join(HERE, rp)])
    by = {}
    for r in res:
        by.setdefault(r["slice"], {})[r["cfg"]] = r
    for sid, c in by.items():
        if "unc" in c and c["unc"]["wer"] > 0.5:
            continue
        p = c["prod+inst"]
        (hard if (p["loop"] or p["passes"] > 1) else clean).append(sid)
def dedupe(ids):
    seen, out = set(), []
    for sid in ids:
        s = allslices[sid]
        key = (s["rec"], s["start"], s["len"])
        if key not in seen:
            seen.add(key)
            out.append(sid)
    return out


hard = dedupe(hard)
clean = [c for c in dedupe(clean) if c not in set(hard)]
random.seed(86)
control = random.sample(sorted(clean), 80)
out = [allslices[s] for s in hard] + [allslices[s] for s in control]
json.dump(out, open(os.path.join(HERE, "slices_sweep.json"), "w"), indent=1)
json.dump({"hard": hard, "control": control}, open(os.path.join(HERE, "sweep_groups.json"), "w"))
print("hard", len(hard), "control", len(control))
