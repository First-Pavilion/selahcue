"""Latency A/B from the two ABBA passes (pass 1: prod..unc, pass 2: unc..prod).

Per (window kind, cfg): median / p90 / p95 decode ms over BOTH passes, the per-pass medians
(stability), and the PAIRED median ratio vs prod (each window's mean-of-two-passes time divided by
prod's on the same window - linear drift across a pass cancels in the ABBA mean).
"""
import collections
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
kinds = {s["id"]: s["kind"] for s in json.load(open(os.path.join(HERE, "slices_latency.json")))}
t = collections.defaultdict(lambda: collections.defaultdict(list))  # (kind,cfg) -> slice -> [ms]
per_pass = collections.defaultdict(list)
for p in ("lat_pass1", "lat_pass2"):
    for line in open(os.path.join(HERE, "results", p + ".jsonl")):
        r = json.loads(line)
        k = kinds[r["slice"]]
        t[(k, r["cfg"])][r["slice"]].append(r["ms"])
        per_pass[(k, r["cfg"], p)].append(r["ms"])


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


order = ["prod", "ctx576", "ctx640", "ctx768", "ctx1024", "unc"]
for kind in ["interim1.6", "interim3.2", "interim4.8", "interim6.0", "final10"]:
    print(f"\n== {kind}")
    print(f"{'cfg':8s} {'n':>4s} {'p50':>6s} {'p90':>6s} {'p95':>6s} {'pass1 p50':>9s} "
          f"{'pass2 p50':>9s} {'paired ratio vs prod (median)':>30s}")
    base = {s: statistics.mean(v) for s, v in t[(kind, "prod")].items()}
    for cfg in order:
        d = t.get((kind, cfg))
        if not d:
            continue
        allv = [x for v in d.values() for x in v]
        means = {s: statistics.mean(v) for s, v in d.items()}
        ratios = [means[s] / base[s] for s in means if s in base]
        p1 = statistics.median(per_pass[(kind, cfg, "lat_pass1")])
        p2 = statistics.median(per_pass[(kind, cfg, "lat_pass2")]) if per_pass[(kind, cfg, "lat_pass2")] else float("nan")
        print(f"{cfg:8s} {len(allv):4d} {statistics.median(allv):6.0f} {pct(allv, .9):6.0f} "
              f"{pct(allv, .95):6.0f} {p1:9.0f} {p2:9.0f} {statistics.median(ratios):30.2f}")
