"""Paired (same-slice) comparison vs production: loops fixed / newly introduced, exact McNemar p.

Population: the 370 intelligible onset starts; each candidate is compared with prod on the SAME
start (the 8 s / 9 s cap variants compare a shorter window from the same onset).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa: E402  (reuses its loaded + scored rows)


def key(r):
    rec, rest = r["slice"].split("@")
    return (rec, rest.split("/")[0])


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


by = {}
for r in compare.rows:
    if key(r) in compare.unintel:
        continue
    win = r["slice"].split("/")[-1]
    by.setdefault((win, r["cfg"]), {})[key(r)] = r
base = by[("10s", "prod+inst")]
FORCED = {}
for r in compare.frows:
    if r["slice"] not in compare.unintel_f:
        FORCED.setdefault(r["cfg"], {})[r["slice"]] = r
print(f"{'candidate':24s} {'loop: fixed':>11s} {'new':>4s} {'p':>8s}   "
      f"{'defect: fixed':>13s} {'new':>4s} {'p':>8s}   {'fallback: fixed':>15s} {'new':>4s}")
for (win, cfg), rs in sorted(by.items()):
    if (win, cfg) == ("10s", "prod+inst"):
        continue
    lf = ln = df = dn = ff = fn = 0
    for k, r in rs.items():
        b = base[k]
        bl, rl = bool(b["loop"]), bool(r["loop"])
        bd, rd = bl or b["wer"] > 0.3, rl or r["wer"] > 0.3
        bf, rf = b.get("passes", 0) > 1, r.get("passes", 0) > 1
        lf += bl and not rl
        ln += rl and not bl
        df += bd and not rd
        dn += rd and not bd
        ff += bf and not rf
        fn += rf and not bf
    print(f"{win + ' ' + cfg:24s} {lf:11d} {ln:4d} {mcnemar_exact(lf, ln):8.1e}   "
          f"{df:13d} {dn:4d} {mcnemar_exact(df, dn):8.1e}   {ff:15d} {fn:4d}")

print("\nproduction-faithful force-closed finals (86): loops per cfg, and new loops vs prod+inst")
fb = FORCED["prod+inst"]
for cfg, rs in sorted(FORCED.items()):
    loops = sum(1 for r in rs.values() if r["loop"])
    new = sum(1 for k, r in rs.items() if r["loop"] and not fb[k]["loop"])
    print(f"  {cfg:20s} N={len(rs):3d} loops={loops} new_vs_main={new}")
