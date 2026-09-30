"""Representative-set comparison across levers, with ONE consistent slice population.

Population: the onset10 starts (395 windows, 48 recordings) minus the 25 whose audio is not
transcribable at all (uncapped 10 s decode WER > 0.5) -> 370 starts; plus, separately, the 86
intelligible production-faithful force-closed windows.
Per config: loops, whisper.cpp temperature-fallback fires (passes > 1), defect = loop OR WER>0.3,
and decode ms (p50/p95/max; NOTE: config-major runs on a shared, heavily loaded machine, so
cross-config ms is indicative only - the interleaved latency A/B is the real latency evidence).
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402

M = os.path.join(HERE, "audio_manifest.json")


def load(slices, *results):
    return analyze.score(os.path.join(HERE, slices), M, [os.path.join(HERE, r) for r in results])


base10 = load("slices_onset10.json", "results/onset_base.jsonl")
unintel = {(r["rec"], r["slice"].split("@")[1].split("/")[0]) for r in base10
           if r["cfg"] == "unc" and r["wer"] > 0.5}
forced = load("slices_forced.json", "results/forced_base.jsonl")
unintel_f = {r["slice"] for r in forced if r["cfg"] == "unc" and r["wer"] > 0.5}

rows = base10 + load("slices_onset8.json", "results/onset8.jsonl") + \
    load("slices_onset9.json", "results/onset9.jsonl")
extra = [p for p in ["results/all_levers.jsonl", "results/fix_all.jsonl"]
         if os.path.exists(os.path.join(HERE, p))]
allr = load("slices_all.json", *extra) if extra else []
rows += [r for r in allr if r["slice"].endswith("/10s")]
frows = forced + [r for r in allr if not r["slice"].endswith("/10s")]


def key(r):
    rec, rest = r["slice"].split("@")
    return (rec, rest.split("/")[0])


def table(title, rows, keep):
    groups = collections.defaultdict(list)
    for r in rows:
        if keep(r):
            win = r["slice"].split("/")[-1] if "/" in r["slice"] else "10s"
            groups[(win, r["cfg"])].append(r)
    print(f"\n== {title}")
    print(f"{'window':7s} {'cfg':16s} {'N':>4s} {'loops':>5s} {'loop%':>6s} {'loopCI':>14s} "
          f"{'fb':>4s} {'fb%':>6s} {'defect':>6s} {'def%':>6s} {'p50':>6s} {'p95':>6s} {'max':>6s}")
    for (win, cfg), rs in sorted(groups.items()):
        n = len(rs)
        lo = sum(1 for r in rs if r["loop"])
        fb = sum(1 for r in rs if r.get("passes", 0) > 1)
        de = sum(1 for r in rs if r["loop"] or r["wer"] > 0.3)
        ms = sorted(r["ms"] for r in rs)
        a, b = analyze.wilson(lo, n)
        print(f"{win:7s} {cfg:16s} {n:4d} {lo:5d} {lo / n:6.1%} [{a:5.1%},{b:5.1%}] {fb:4d} "
              f"{fb / n:6.1%} {de:6d} {de / n:6.1%} {ms[n // 2]:6.0f} "
              f"{ms[min(n - 1, int(n * 0.95))]:6.0f} {ms[-1]:6.0f}")


table("onset windows (noisy-room scenario), 370 intelligible starts", rows,
      lambda r: key(r) not in unintel)
table("production-faithful force-closed finals, 86 intelligible", frows,
      lambda r: r["slice"] not in unintel_f)
