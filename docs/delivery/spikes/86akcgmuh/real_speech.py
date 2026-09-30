"""17tnw2b0nkq C-009: real-human-speech validation, after the user has approved the download.

usage:
  real_speech.py prepare   # audio_real/*.mp3 -> 16 kHz mono WAV + real_manifest.json
  (then: harness extract real_manifest.json results/real_engine_windows.json)
  real_speech.py slices    # -> slices_real.json (10.0 s windows from engine utterance onsets)
  (then: harness decode slices_real.json results/real.jsonl prod+inst,recog,fix,unc)
  real_speech.py report    # loop rates, paired new/fixed, and EVERY trim listed for inspection

There is no reference script for these recordings, so a "loop" is a back-to-back repeat (the
same definition as analyze.find_loop) that the UNCAPPED decode of the same window does not also
contain. The uncapped decode looped on 1 of 370 synthetic windows, so it is a good-but-imperfect
pseudo-reference: every flagged window and every trim is printed for manual inspection.
"""
import collections
import json
import math
import os
import random
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402

REAL = os.path.join(HERE, "audio_real")
SR = 16000
# LibriVox "Spurgeon's Sermons May 1858" (public domain in the USA), one reader per sermon.
READERS = {
    "sermon_0191_spurgeon_64kb": "Mark Barnes",
    "sermon_0192_spurgeon_64kb": "Andy Minter",
    "sermon_0193_spurgeon_64kb": "Justin Brett",
    "sermon_0194_spurgeon_64kb": "Vivian Bush",
    "sermon_0195_spurgeon_64kb": "Alan Chant",
    "sermon_0196_spurgeon_64kb": "Tim Bulkeley",
}
PER_RECORDING = 60


def prepare():
    man = []
    for base, reader in READERS.items():
        mp3 = os.path.join(REAL, base + ".mp3")
        wav = os.path.join(REAL, base + ".wav")
        if not os.path.exists(wav):
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", mp3, wav],
                           check=True)
        with wave.open(wav) as w:
            n = w.getnframes()
        man.append({"id": base, "wav": wav, "reader": reader, "reference": "", "n_samples": n})
        print(base, reader, round(n / SR / 60, 1), "min")
    json.dump(man, open(os.path.join(HERE, "real_manifest.json"), "w"), indent=1)


def slices():
    man = {r["id"]: r for r in json.load(open(os.path.join(HERE, "real_manifest.json")))}
    wins = json.load(open(os.path.join(HERE, "results", "real_engine_windows.json")))
    forced = sum(1 for w in wins if w["forced"])
    by_rec = collections.defaultdict(list)
    for w in sorted(wins, key=lambda w: (w["rec"], w["start"])):
        rec = man[w["rec"]]
        if w["start"] < 30 * SR or w["start"] + 10 * SR > rec["n_samples"]:
            continue  # skip the LibriVox spoken preamble at the start of each file
        lst = by_rec[w["rec"]]
        if lst and w["start"] - lst[-1]["start"] < 8 * SR:
            continue
        lst.append({"id": f"{w['rec']}@{w['start']}/10s", "rec": w["rec"], "wav": w["wav"],
                    "start": w["start"], "len": 10 * SR, "rec_len": rec["n_samples"],
                    "engine_forced": w["forced"] and w["len"] >= 10 * SR})
    random.seed(17)
    out = []
    for rec, lst in sorted(by_rec.items()):
        out += sorted(random.sample(lst, min(PER_RECORDING, len(lst))), key=lambda s: s["start"])
    json.dump(out, open(os.path.join(HERE, "slices_real.json"), "w"), indent=1)
    print("engine finals:", len(wins), "force-closed by the real engine:", forced,
          "| sampled 10 s onset windows:", len(out), "from", len(by_rec), "readers")


def wilson(k, n):
    return analyze.wilson(k, n)


def report():
    rows = collections.defaultdict(dict)
    for line in open(os.path.join(HERE, "results", "real.jsonl")):
        r = json.loads(line)
        rows[r["slice"]][r["cfg"]] = r
    reader = {s["id"]: READERS[s["rec"]] for s in json.load(open(os.path.join(HERE, "slices_real.json")))}
    cfgs = ["prod+inst", "recog", "fix"]
    loops = {c: {} for c in cfgs}
    unintel = 0
    for sid, c in rows.items():
        ref = c["unc"]["text"]
        rj = " " + " ".join(analyze.norm_words(ref)) + " "
        if len(analyze.norm_words(ref)) < 5:
            unintel += 1
            continue
        for cfg in cfgs:
            loops[cfg][sid] = analyze.find_loop(analyze.norm_words(c[cfg]["text"]), rj)
    n = len(loops["fix"])
    print(f"windows: {len(rows)} (excluded, uncapped decode < 5 words: {unintel}); scored: {n}")
    for cfg in cfgs:
        k = sum(1 for v in loops[cfg].values() if v)
        lo, hi = wilson(k, n)
        new = sum(1 for s, v in loops[cfg].items() if v and not loops["prod+inst"][s])
        fixed = sum(1 for s, v in loops[cfg].items() if not v and loops["prod+inst"][s])
        per = collections.Counter(reader[s] for s, v in loops[cfg].items() if v)
        print(f"  {cfg:10s} loops {k:3d}/{n} = {k / n:5.1%} [{lo:4.1%},{hi:4.1%}]  fixed vs main "
              f"{fixed:2d}  new vs main {new:2d}  by reader {dict(per)}")
    print("\nEvery window where a config looped:")
    for sid in sorted(loops["fix"]):
        if any(loops[c][sid] for c in cfgs):
            print("=" * 90, "\n", sid, reader[sid])
            for cfg in cfgs + ["unc"]:
                t = rows[sid][cfg]["text"]
                flag = loops[cfg].get(sid) if cfg != "unc" else None
                print(f"   [{cfg:9s}] {'LOOP ' + str(flag['span']) + 'x' + str(flag['repeats']) if flag else 'ok':10s} ...{t[-170:]}")
    print("\nEvery trim the production trim applied (recog -> fix), for manual inspection:")
    trims = 0
    for sid in sorted(rows):
        a, b = rows[sid]["recog"]["text"], rows[sid]["fix"]["text"]
        if a != b:
            trims += 1
            print("-" * 90, "\n", sid, reader[sid])
            print("   before:", a[-200:])
            print("   after :", b[-200:])
            print("   unc   :", rows[sid]["unc"]["text"][-200:])
    print("trims applied:", trims)


if __name__ == "__main__":
    {"prepare": prepare, "slices": slices, "report": report}[sys.argv[1]]()
