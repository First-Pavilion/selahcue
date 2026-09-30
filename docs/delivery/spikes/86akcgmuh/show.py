"""Print the slices where any config looped / fell back, with each config's output side by side.

usage: show.py [cfg,cfg,...]   (reads results/last_scored.json written by analyze.py)
"""
import collections
import json
import os
import sys

res = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results",
                                  "last_scored.json")))
only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
by_slice = collections.defaultdict(dict)
for r in res:
    by_slice[r["slice"]][r["cfg"]] = r
for sid, cfgs in by_slice.items():
    if not any(r["loop"] or r.get("passes", 0) > 1 for r in cfgs.values()):
        continue
    print("=" * 100)
    print(sid)
    for name, r in cfgs.items():
        if only and name not in only:
            continue
        tag = f"LOOP{r['loop']['span']}x{r['loop']['repeats']}" if r["loop"] else "ok"
        print(f"  [{name:14s}] {tag:10s} passes={r.get('passes', 0)} ms={r['ms']:.0f} wer={r['wer']:.2f} ins={r['ins']}")
        print(f"      {r['text']}")
