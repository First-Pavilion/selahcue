"""Build slice sets from the engine-extracted finals.

usage: make_slices.py   (paths are fixed to this spike's scratch layout)

Writes:
  slices_forced.json  - every final the REAL SttEngine force-closed at exactly 10.000 s
                        (production-faithful: starts at a VAD onset, ends wherever 10 s lands).
  slices_onset10.json - a 10.000 s window starting at each engine utterance onset (starts >= 8 s
                        apart per recording), i.e. what force-close produces when the room never
                        goes quiet for the 300 ms hangover (reverb, music bed, fast speaker).
Each slice records whether its last 40 ms is still voiced (the "cut lands mid-word" proxy).
"""
import json
import math
import os
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 16000
WIN = 10 * SR

man = json.load(open(os.path.join(HERE, "audio_manifest.json")))
for r in man:
    with wave.open(r["wav"]) as w:
        r["n_samples"] = w.getnframes()
json.dump(man, open(os.path.join(HERE, "audio_manifest.json"), "w"), indent=1)
recs = {r["id"]: r for r in man}

wins = json.load(open(os.path.join(HERE, "results", "engine_windows.json")))


def tail_voiced(wav, end):
    with wave.open(wav) as w:
        w.setpos(max(0, end - 640))
        raw = w.readframes(640)
    vals = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767 for i in range(0, len(raw), 2)]
    rms = math.sqrt(sum(v * v for v in vals) / max(1, len(vals)))
    return rms > 0.01


forced = []
for w in wins:
    if w["forced"]:
        s = dict(w)
        s["rec_len"] = recs[w["rec"]]["n_samples"]
        s["mid_word"] = tail_voiced(w["wav"], w["start"] + w["len"])
        forced.append(s)

onset = []
last = {}
for w in sorted(wins, key=lambda w: (w["rec"], w["start"])):
    rec = recs[w["rec"]]
    if w["start"] + WIN > rec["n_samples"]:
        continue
    if w["rec"] in last and w["start"] - last[w["rec"]] < 8 * SR:
        continue
    last[w["rec"]] = w["start"]
    onset.append({"id": f"{w['rec']}@{w['start']}/10s", "rec": w["rec"], "wav": w["wav"],
                  "start": w["start"], "len": WIN, "rec_len": rec["n_samples"],
                  "mid_word": tail_voiced(w["wav"], w["start"] + WIN)})

json.dump(forced, open(os.path.join(HERE, "slices_forced.json"), "w"), indent=1)
json.dump(onset, open(os.path.join(HERE, "slices_onset10.json"), "w"), indent=1)
print("forced:", len(forced), "mid-word:", sum(s["mid_word"] for s in forced))
print("onset10:", len(onset), "mid-word:", sum(s["mid_word"] for s in onset),
      "recordings:", len({s["rec"] for s in onset}))
