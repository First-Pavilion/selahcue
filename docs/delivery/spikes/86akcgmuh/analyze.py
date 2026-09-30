"""Score decode results: repetition-loop detection + alignment against the known TTS script.

usage: analyze.py <slices.json> <audio_manifest.json> <results.jsonl> [more.jsonl ...]

Per (slice, cfg):
  loop      - the hypothesis contains a back-to-back verbatim repeat of a word span (span >= 3
              words repeated >= 2x, or a 2-word span repeated >= 3x) that the reference script
              does NOT itself contain. This is the ticket's failure mode ("X, X, X").
  ins/sub/dele/wer - semi-global word alignment against the reference script (free gaps at
              the reference start/end, since the window starts and ends mid-script).
  ref_end   - last reference word the hypothesis aligned to (to spot tail content a config
              drops relative to another config on the SAME slice).

Slices whose UNCAPPED decode ('unc') has WER > 0.5 are reported separately as
'unintelligible' (the rendered audio itself is not transcribable - a TTS artefact, not the
boundary defect) and excluded from the headline rates.

A virtual config '<cfg>+collapse' is added for 'prod+inst': the deterministic text-level
trailing-repeat collapse candidate (see collapse_trailing_repeat), applied to prod's output.
"""
import collections
import json
import math
import os
import re
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "last_scored.json")


def norm_words(s):
    s = s.lower().replace("’", "'").replace("-", " ")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return [w.strip("'") for w in s.split() if w.strip("'")]


def find_loop(h, ref_joined):
    best = None
    m = len(h)
    for n in range(2, 21):
        for i in range(0, m - 2 * n + 1):
            if h[i:i + n] != h[i + n:i + 2 * n]:
                continue
            k = 2
            while h[i:i + n] == h[i + k * n:i + (k + 1) * n]:
                k += 1
            if n == 2 and k < 3:
                continue
            doubled = " " + " ".join(h[i:i + 2 * n]) + " "
            if doubled in ref_joined:
                continue
            cand = (n * k, n, k, " ".join(h[i:i + n]))
            if best is None or cand > best:
                best = cand
    if best is None:
        return None
    return {"span": best[1], "repeats": best[2], "text": best[3]}


def collapse_trailing_repeat(text, min_span=3):
    """Deterministic post-filter candidate: if the output ENDS inside a back-to-back repeat of a
    span of >= min_span words (the second copy possibly partial, cut by the window end), drop
    everything after the first copy. Operates on whitespace words, punctuation-insensitive
    matching. Only touches a repeat that runs to the very end of the output."""
    raw = text.split()
    w = [re.sub(r"[^a-z0-9']", "", x.lower()) for x in raw]
    m = len(w)
    for n in range(min_span, m // 2 + 1):
        # the repeat must reach the end: find i such that w[i:i+n] == w[i+n:i+2n] and the
        # remainder after 2n (if any) is a prefix of w[i:i+n] (partial third copy), with the
        # whole pattern ending at m.
        for i in range(m - 2 * n, -1, -1):
            if w[i:i + n] != w[i + n:i + 2 * n]:
                continue
            j = i + 2 * n
            ok = True
            while j < m:
                chunk = w[j:j + n]
                if chunk != w[i:i + len(chunk)]:
                    ok = False
                    break
                j += n
            if ok:
                return " ".join(raw[:i + n])
    return text


def align(h, r):
    m, n = len(h), len(r)
    D = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        D[i][0] = i
    for i in range(1, m + 1):
        hi = h[i - 1]
        Di, Dp = D[i], D[i - 1]
        for j in range(1, n + 1):
            c = Dp[j - 1] + (0 if hi == r[j - 1] else 1)
            a = Dp[j] + 1
            b = Di[j - 1] + 1
            Di[j] = c if c <= a and c <= b else (a if a <= b else b)
    jend = min(range(n + 1), key=lambda j: (D[m][j], -j))
    i, j = m, jend
    ins = sub = dele = cor = 0
    while i > 0 and j > 0:
        if D[i][j] == D[i - 1][j - 1] + (0 if h[i - 1] == r[j - 1] else 1):
            if h[i - 1] == r[j - 1]:
                cor += 1
            else:
                sub += 1
            i -= 1
            j -= 1
        elif D[i][j] == D[i - 1][j] + 1:
            ins += 1
            i -= 1
        else:
            dele += 1
            j -= 1
    ins += i
    span = max(1, jend - j)
    return {"ins": ins, "sub": sub, "dele": dele, "cor": cor, "ref_start": j, "ref_end": jend,
            "wer": (ins + sub + dele) / span}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    e = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - e) / d, (c + e) / d)


def score(slices_path, manifest_path, paths):
    slices = {s["id"]: s for s in json.load(open(slices_path))}
    recs = {r["id"]: r for r in json.load(open(manifest_path))}
    rows = []
    for path in paths:
        for line in open(path):
            row = json.loads(line)
            if row["slice"] in slices:
                rows.append(row)
    extra = []
    for r in rows:
        if r["cfg"] in ("prod+inst", "ctx576+inst", "ctx640+inst", "ctx1024+inst"):
            e = dict(r)
            e["cfg"] = r["cfg"].replace("+inst", "") + "+collapse"
            e["text"] = collapse_trailing_repeat(r["text"])
            extra.append(e)
    rows += extra
    refcache = {}
    out = []
    for row in rows:
        s = slices[row["slice"]]
        rec = recs[s["rec"]]
        if rec["id"] not in refcache:
            rw = norm_words(rec["reference"])
            refcache[rec["id"]] = (rw, " " + " ".join(rw) + " ")
        rw, rj = refcache[rec["id"]]
        total = rec["n_samples"]
        lo = max(0, int(s["start"] / total * len(rw)) - 40)
        hi = min(len(rw), int((s["start"] + s["len"]) / total * len(rw)) + 40)
        h = norm_words(row["text"])
        a = align(h, rw[lo:hi])
        a["ref_start"] += lo
        a["ref_end"] += lo
        out.append({**row, "loop": find_loop(h, rj), **a, "n_words": len(h),
                    "mid_word": s.get("mid_word"), "rec": s["rec"]})
    return out


def report(res, baseline="prod+inst"):
    by_slice = collections.defaultdict(dict)
    for r in res:
        by_slice[r["slice"]][r["cfg"]] = r
    unintel = {sid for sid, c in by_slice.items() if "unc" in c and c["unc"]["wer"] > 0.5}
    best_end = {sid: max(r["ref_end"] for r in c.values()) for sid, c in by_slice.items()}
    cfgs = []
    for r in res:
        if r["cfg"] not in cfgs:
            cfgs.append(r["cfg"])
    print(f"slices: {len(by_slice)}  unintelligible (unc WER>0.5, excluded): {len(unintel)}")
    hdr = (f"{'cfg':24s} {'N':>4s} {'loops':>5s} {'rate':>6s} {'95%CI':>13s} {'WER':>6s} "
           f"{'ins':>4s} {'tail3':>5s} {'fb':>4s} {'worse':>5s} {'fixed':>5s} {'p50':>6s} "
           f"{'p95':>6s} {'max':>6s} {'trunc':>5s} {'defect':>6s} {'dCI':>13s}")
    print(hdr)

    def defect(r):
        """loop, OR garbled (WER > 0.3), OR truncated: aligned reference span < 70% of what the
        full-context ('unc') decode of the same slice recovered."""
        u = by_slice[r["slice"]].get("unc")
        span = r["ref_end"] - r["ref_start"]
        trunc = bool(u) and span < 0.7 * (u["ref_end"] - u["ref_start"])
        return bool(r["loop"]) or r["wer"] > 0.3 or trunc, trunc

    for cfg in cfgs:
        rs = [c[cfg] for sid, c in by_slice.items() if cfg in c and sid not in unintel]
        n = len(rs)
        if not n:
            continue
        dres = [defect(r) for r in rs]
        ndef = sum(1 for d, _ in dres if d)
        ntrunc = sum(1 for _, t in dres if t)
        dlo, dhi = wilson(ndef, n)
        loops = sum(1 for r in rs if r["loop"])
        lo, hi = wilson(loops, n)
        wer = sum(r["wer"] for r in rs) / n
        ins = sum(r["ins"] for r in rs)
        tail = sum(1 for r in rs if best_end[r["slice"]] - r["ref_end"] >= 3)
        fb = sum(1 for r in rs if r.get("passes", 0) > 1)
        worse = fixed = 0
        for r in rs:
            b = by_slice[r["slice"]].get(baseline)
            if b is None:
                continue
            if r["wer"] > b["wer"] + 0.1:
                worse += 1
            if b["loop"] and not r["loop"]:
                fixed += 1
        ms = sorted(r["ms"] for r in rs)
        print(f"{cfg:24s} {n:4d} {loops:5d} {loops / n:6.1%} [{lo:5.1%},{hi:5.1%}] {wer:6.3f} "
              f"{ins:4d} {tail:5d} {fb:4d} {worse:5d} {fixed:5d} {ms[n // 2]:6.0f} "
              f"{ms[min(n - 1, int(n * 0.95))]:6.0f} {ms[-1]:6.0f} {ntrunc:5d} {ndef:6d} "
              f"[{dlo:5.1%},{dhi:5.1%}]")
    return by_slice, unintel


if __name__ == "__main__":
    res = score(sys.argv[1], sys.argv[2], sys.argv[3:])
    report(res)
    json.dump(res, open(OUT, "w"))
