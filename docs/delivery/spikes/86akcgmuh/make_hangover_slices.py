"""Scope check: finals the REAL engine closed on the 300 ms hangover (NOT force-closed), >= 4 s.

If these loop at a similar rate to force-closed windows, the defect is not specific to the 10 s
force-close boundary.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
man = {r["id"]: r for r in json.load(open(os.path.join(HERE, "audio_manifest.json")))}
wins = json.load(open(os.path.join(HERE, "results", "engine_windows.json")))
cand = [w for w in wins if not w["forced"] and w["len"] >= 4 * 16000]
random.seed(300)
pick = random.sample(cand, min(150, len(cand)))
out = [{**w, "rec_len": man[w["rec"]]["n_samples"]} for w in pick]
json.dump(out, open(os.path.join(HERE, "slices_hangover.json"), "w"), indent=1)
lens = sorted(w["len"] / 16000 for w in out)
print(len(cand), "candidates;", len(out), "picked; len p10/p50/p90 =",
      round(lens[len(lens) // 10], 2), round(lens[len(lens) // 2], 2), round(lens[9 * len(lens) // 10], 2))
