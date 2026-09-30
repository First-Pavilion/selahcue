"""Latency A/B slice set: the windows production actually decodes.

- interim-shaped windows (1.6 / 3.2 / 4.8 / 6.0 s from an utterance onset; 6.0 s is
  listening.rs's INTERIM_WINDOW_SAMPLES cap, so it is the steady-state interim size)
- the 10.0 s force-closed finals (the real engine-extracted ones)
40 onsets x 4 interim sizes + 40 finals = 200 windows, fixed seed.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
onset = json.load(open(os.path.join(HERE, "slices_onset10.json")))
forced = json.load(open(os.path.join(HERE, "slices_forced.json")))
random.seed(512)
picks = random.sample(onset, 40)
out = []
for s in picks:
    for secs in (1.6, 3.2, 4.8, 6.0):
        n = int(secs * 16000)
        out.append({**s, "id": f"{s['rec']}@{s['start']}/{secs}s", "len": n, "kind": f"interim{secs}"})
for s in random.sample(forced, 40):
    out.append({**s, "kind": "final10"})
json.dump(out, open(os.path.join(HERE, "slices_latency.json"), "w"), indent=1)
print(len(out))
