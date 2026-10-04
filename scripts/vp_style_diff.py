#!/usr/bin/env python3
"""Compare VALUES, not pixels: Figma's text/box styles against the built page's computed styles.

A pixel score says "somewhere here differs". This says what: the heading is 26px in Figma and
24px in the build, the card radius is 22 and 16, the eyebrow is centred in the frame and
left-aligned in the page, this sentence exists in the design and nowhere in the build.

    python3 scripts/vp_style_diff.py --slug signin --dom RUN/marketing/signin.blink.dom.json
    python3 scripts/vp_style_diff.py --slug home --dom ... --json out.json --limit 200

Inputs
  * the Figma side: `docs/design/visual-parity/marketing/figma-style/<slug>.json`, produced by
    `scripts/figma_extract_style.js` through the Figma MCP's `use_figma` (read-only);
  * the build side: the `<slug>.<engine>.dom.json` that `vp_capture_marketing.py` writes next
    to every screenshot (computed style of every text node and every painted box).

How texts are paired
  Case- and whitespace-insensitive text equality, paired IN READING ORDER among duplicates
  (the nth "Download free" in the frame with the nth in the page), then a fuzzy pass for copy
  that differs by a few words, then a containment pass for inline-styled runs. Whatever stays
  unpaired is reported as design-only or build-only COPY — which is a finding in its own right.

What it will NOT tell you
  * a verdict. Every difference still has to be classified A to E by a person who has read the
    handoff docs: a 1-3% colour gap through the `--sc-*` token layer is deliberate (class B),
    and the tool only labels it `token-layer` when the build's colour equals the mapped token;
  * anything about states the capture did not photograph (hover, focus, error);
  * vertical position as an absolute: pages diverge in height, so `dy` is reported together with
    `dy_step`, the shift introduced since the previous paired text, which is what locates the
    section that grew or shrank.

Bounded: reads two JSON files, holds at most MAX_NODES figma nodes and MAX_NODES dom items,
and prints at most --limit lines.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402

STYLE_DIR = os.path.join(vp.MARKETING_DIR, "figma-style")
MAX_NODES = 2500

# AUTH-LANDING-PAGES-HANDOFF section 2.2: Figma's legacy `SelahCue Color` variables and the
# Design 2.0 `--sc-*` tokens the build uses for the same role. 1-3% luminance apart, on purpose.
TOKEN_LAYER = {
    "#0e1116": ["#0b0d12", "#0f1116"],  # bg/base -> --sc-base (page) / --sc-inset (input well)
    "#171b22": ["#14161d"],             # bg/panel -> --sc-surface
    "#1e232c": ["#1c1f28"],             # bg/elevated -> --sc-elevated
    "#2b323d": ["#262a34"],             # border -> --sc-border
    "#eef1f6": ["#f4f6fb"],             # text/primary -> --sc-text
    "#9aa4b2": ["#a7aebe"],             # text/muted -> --sc-text-secondary
    "#5b6bd6": ["#6e5cf0"],             # accent/brand -> --sc-primary
    "#ef4444": ["#ff4d4d"],             # accent/live -> --sc-live
    "#2bb673": ["#35c08a"],             # accent/preview -> --sc-preview
    "#f2b53c": ["#f5a524", "#f2b84b"],  # accent/warn -> --sc-warn (or --sc-gold)
}

SAME_COLOUR = 4      # max per-channel delta (0-255) still read as the same colour
TOKEN_COLOUR = 3     # ... and for "equals the mapped --sc-* token"
FS_TOL = 0.5
LH_TOL = 1.5
LS_TOL = 0.3
POS_TOL = 3.0
SIZE_TOL = 6.0
FUZZY = 0.80


def fold_punct(text):
    """Typographic quotes, non-breaking spaces and the ellipsis folded to their plain forms.

    A curly apostrophe against a straight one is NOT a copy difference (the copy deck uses straight, Figma
    draws curly: AUTH-LANDING 6 / audit finding verify-v2-02, class D), so it must not read as one.
    """
    t = (text or "").replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return t.replace("\u00a0", " ").replace("\u2026", "...")


def norm(text):
    return re.sub(r"\s+", " ", fold_punct(text)).strip().lower()


def hex_rgb(value):
    """'#rrggbb' or '#rrggbb@a' -> ((r, g, b), alpha) or (None, 1)."""
    if not value or not value.startswith("#"):
        return None, 1.0
    body, _, alpha = value[1:].partition("@")
    if len(body) != 6:
        return None, 1.0
    try:
        return tuple(int(body[i:i + 2], 16) for i in (0, 2, 4)), float(alpha) if alpha else 1.0
    except ValueError:
        return None, 1.0


def css_rgb(value, bgl=None):
    rgba = vp.parse_css_color(value)
    if rgba is None:
        return None
    if rgba[3] < 255:
        base = vp.composite_layers(bgl or [], base=(14, 17, 22)) or (14, 17, 22)
        return vp.blend_over(rgba, base)
    return rgba[:3]


def delta(a, b):
    return max(abs(a[i] - b[i]) for i in range(3))


def px(value):
    try:
        return float(str(value).replace("px", ""))
    except (TypeError, ValueError):
        return None


def to_hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def classify_colour(figma_value, dom_rgb, bgl=None):
    """Return ('same'|'token-layer'|'different', detail)."""
    f_rgb, alpha = hex_rgb(figma_value)
    if f_rgb is None or dom_rgb is None:
        return "unknown", ""
    if alpha < 1.0:
        base = vp.composite_layers(bgl or [], base=(14, 17, 22)) or (14, 17, 22)
        f_rgb = vp.blend_over(f_rgb + (int(alpha * 255),), base)
    if delta(f_rgb, dom_rgb) <= SAME_COLOUR:
        return "same", ""
    figma_hex = to_hex(f_rgb)
    for mapped in TOKEN_LAYER.get(figma_hex, []):
        m_rgb, _ = hex_rgb(mapped)
        if delta(m_rgb, dom_rgb) <= TOKEN_COLOUR:
            return "token-layer", "%s -> %s (--sc-* layer, AUTH-LANDING-PAGES-HANDOFF 2.2)" % (figma_hex, mapped)
    return "different", "figma %s vs build %s" % (figma_hex, to_hex(dom_rgb))


def load_figma(slug, path=None):
    path = path or os.path.join(STYLE_DIR, slug + ".json")
    data = vp.load_json(path)
    n = len(data.get("texts", [])) + len(data.get("boxes", []))
    if n > MAX_NODES:
        raise SystemExit("figma style file has %d nodes, over MAX_NODES=%d" % (n, MAX_NODES))
    return data


def load_dom(path):
    data = vp.load_json(path)
    if len(data.get("items", [])) > MAX_NODES:
        raise SystemExit("dom dump has %d items, over MAX_NODES=%d" % (len(data["items"]), MAX_NODES))
    return data


# ---------------------------------------------------------------------------
# Pairing
# ---------------------------------------------------------------------------


def may_reach(count_a, len_a, count_b, len_b, threshold):
    """False only when `difflib.SequenceMatcher(a, b).ratio()` provably cannot reach `threshold`.

    ratio = 2*M/T where M is the number of matched characters. M can be no more than the size of the
    multiset intersection (what `quick_ratio` computes), and no more than the shorter length. Both are upper
    bounds, so a pair under the threshold on the bound is under it for real.
    """
    total = len_a + len_b
    if total == 0:
        return True
    if 2.0 * min(len_a, len_b) / total < threshold:
        return False
    matches = sum(min(n, count_b.get(ch, 0)) for ch, n in count_a.items())
    return 2.0 * matches / total >= threshold


def pair_texts(f_texts, d_items):
    """Return (pairs, figma_only, dom_only). `pairs` are 3-tuples (figma_idx, dom_idx, how); the two
    `*_only` lists are the indexes left unpaired, in reading order."""
    f_order = sorted(range(len(f_texts)), key=lambda i: (f_texts[i]["y"], f_texts[i]["x"]))
    d_text_idx = [i for i, it in enumerate(d_items) if it.get("text")]
    d_order = sorted(d_text_idx, key=lambda i: (d_items[i].get("ty", d_items[i]["y"]), d_items[i].get("tx", d_items[i]["x"])))
    pairs = []
    used_f, used_d = set(), set()

    by_text = {}
    for i in d_order:
        by_text.setdefault(norm(d_items[i]["text"]), []).append(i)
    for fi in f_order:
        key = norm(f_texts[fi]["t"])
        queue = by_text.get(key)
        if queue:
            di = queue.pop(0)
            pairs.append((fi, di, "exact"))
            used_f.add(fi)
            used_d.add(di)

    # fuzzy: same-ish copy. `difflib.ratio()` is the expensive part, and it is quadratic over the pairs; its
    # cheap upper bounds (`real_quick_ratio` from lengths, `quick_ratio` from the character multiset) can
    # never be below the real ratio, so a pair whose BOUND is under FUZZY cannot reach it and is skipped.
    # The pairs that remain are scored by the unchanged `SequenceMatcher(None, ft, dt).ratio()`, so the
    # output is identical (checked on all real captures and by a property test in vp_selftest.py).
    left_f = [i for i in f_order if i not in used_f]
    left_d = [i for i in d_order if i not in used_d]
    d_norm = {di: norm(d_items[di]["text"]) for di in left_d}
    d_count = {di: collections.Counter(t) for di, t in d_norm.items()}
    for fi in left_f:
        ft = norm(f_texts[fi]["t"])
        if len(ft) < 6:
            continue
        f_count = collections.Counter(ft)
        best, best_r = None, 0.0
        for di in left_d:
            if di in used_d:
                continue
            dt = d_norm[di]
            if abs(len(dt) - len(ft)) > max(12, len(ft) * 0.5):
                continue
            if not may_reach(f_count, len(ft), d_count[di], len(dt), FUZZY):
                continue
            r = difflib.SequenceMatcher(None, ft, dt).ratio()
            if r > best_r:
                best, best_r = di, r
        if best is not None and best_r >= FUZZY:
            pairs.append((fi, best, "fuzzy:%.2f" % best_r))
            used_f.add(fi)
            used_d.add(best)

    # containment: an inline-styled run that the design draws as one text node
    for fi in [i for i in f_order if i not in used_f]:
        ft = norm(f_texts[fi]["t"])
        if len(ft) < 12:
            continue
        for di in [i for i in d_order if i not in used_d]:
            dt = norm(d_items[di]["text"])
            # `dt in ft` must cover at least half the design's sentence, or any three-word phrase
            # that happens to appear inside a long paragraph would be "paired" with it.
            if len(dt) >= 8 and ((dt in ft and len(dt) >= 0.5 * len(ft)) or (ft in dt and len(ft) >= 0.5 * len(dt))):
                pairs.append((fi, di, "contains"))
                used_f.add(fi)
                used_d.add(di)
                break

    f_only = [i for i in f_order if i not in used_f]
    d_only = [i for i in d_order if i not in used_d]
    pairs.sort(key=lambda p: (f_texts[p[0]]["y"], f_texts[p[0]]["x"]))
    return pairs, f_only, d_only


def text_diffs(ft, dt):
    """The list of differences between one paired Figma text and DOM item."""
    out = []
    if norm(ft["t"]) != norm(dt["text"]):
        out.append(("copy", "figma %r vs build %r" % (ft["t"][:70], dt["text"][:70])))
    elif fold_punct(ft["t"]).strip() != fold_punct(dt["text"]).strip() and dt.get("tt", "none") == "none":
        # Compared after folding typographic punctuation, so a curly vs straight apostrophe is not "case".
        out.append(("copy-case", "figma %r vs build %r" % (ft["t"][:50], dt["text"][:50])))
    f_fs, d_fs = ft.get("fs"), px(dt.get("fs"))
    if f_fs is not None and d_fs is not None and abs(f_fs - d_fs) > FS_TOL:
        out.append(("font-size", "figma %spx vs build %spx" % (f_fs, d_fs)))
    d_fw = int(float(dt.get("fw", 400))) if dt.get("fw") else None
    if ft.get("fw") and d_fw and ft["fw"] != d_fw:
        out.append(("font-weight", "figma %s vs build %s" % (ft["fw"], d_fw)))
    d_lh = px(dt.get("lh")) if dt.get("lh") and dt["lh"] != "normal" else None
    if ft.get("lh") and d_lh and abs(ft["lh"] - d_lh) > LH_TOL:
        out.append(("line-height", "figma %spx vs build %spx" % (ft["lh"], d_lh)))
    d_ls = px(dt.get("ls")) if dt.get("ls") else 0.0
    if d_ls is not None and abs((ft.get("ls") or 0) - d_ls) > LS_TOL:
        out.append(("letter-spacing", "figma %spx vs build %spx" % (ft.get("ls") or 0, d_ls)))
    f_ta = {"LEFT": "left", "CENTER": "center", "RIGHT": "right", "JUSTIFIED": "justify"}.get(ft.get("ta"), "left")
    d_ta = dt.get("ta", "left")
    if d_ta == "start":
        d_ta = "left"
    if f_ta != d_ta:
        # Figma reports LEFT for text that merely hugs its content inside a centring frame, so a LEFT
        # design only counts as a difference when its text box is clearly wider than the ink (a box that
        # could have been aligned); a design that says centre, right or justify always does.
        wide_box = bool(ft.get("w") and dt.get("tw") and ft["w"] > dt["tw"] + 20)
        if f_ta != "left" or wide_box:
            out.append(("text-align", "figma %s vs build %s" % (f_ta, d_ta)))
    return out


def colour_diff(ft, dt):
    if not ft.get("c") or not dt.get("color"):
        return None
    d_rgb = css_rgb(dt["color"], dt.get("bgl"))
    kind, detail = classify_colour(ft["c"], d_rgb, dt.get("bgl"))
    return kind, detail


def x_offset(ft, dt):
    """Horizontal offset of the text's anchor edge/centre; None if the build gave no text box."""
    if dt.get("tx") is None:
        return None
    ta = ft.get("ta", "LEFT")
    if ta == "CENTER":
        return (dt["tx"] + dt["tw"] / 2.0) - (ft["x"] + ft["w"] / 2.0)
    if ta == "RIGHT":
        return (dt["tx"] + dt["tw"]) - (ft["x"] + ft["w"])
    return dt["tx"] - ft["x"]


# ---------------------------------------------------------------------------
# Boxes
# ---------------------------------------------------------------------------


def contains(box, cx, cy):
    return box["x"] - 1 <= cx <= box["x"] + box["w"] + 1 and box["y"] - 1 <= cy <= box["y"] + box["h"] + 1


def ancestors(items, i):
    chain = []
    seen = 0
    while i is not None and i >= 0 and seen < 64:
        chain.append(i)
        i = items[i].get("p")
        seen += 1
    return chain


def box_like(it):
    return bool(it.get("bg") or it.get("border"))


def dom_box_for(items, member_idx):
    """Smallest dumped box-like ancestor that is shared by every member text (the LCA that paints)."""
    chains = [ancestors(items, i) for i in member_idx]
    if not chains:
        return None
    common = [a for a in chains[0] if all(a in c for c in chains[1:])]
    for a in common:
        if box_like(items[a]):
            return a
    return None


def effective_radius(value, w, h):
    """A border radius in px, as it renders: percentages resolved against the box, capped at half its shorter side."""
    half = min(w, h) / 2.0
    if isinstance(value, str) and value.strip().endswith("%"):
        try:
            return min(half, float(value.strip().rstrip("%")) / 100.0 * min(w, h))
        except ValueError:
            return 0.0
    try:
        r = float(str(value).replace("px", "")) if isinstance(value, str) else float(value)
    except ValueError:
        return 0.0
    return min(half, r)


def box_diffs(fb, db):
    out = []
    f_fill = fb.get("f")
    if f_fill and f_fill.startswith("#") and db.get("bg"):
        d_rgb = css_rgb(db["bg"])
        kind, detail = classify_colour(f_fill, d_rgb)
        if kind in ("different",):
            out.append(("fill", detail))
        elif kind == "token-layer":
            out.append(("fill~", detail))
    elif f_fill and f_fill.startswith("#") and not db.get("bg"):
        out.append(("fill", "figma %s vs build no fill" % f_fill))
    f_s = fb.get("s")
    if f_s and f_s.startswith("#"):
        if db.get("border"):
            m = re.match(r"([\d.]+)px \w+ (rgba?\([^)]*\))", db["border"])
            if m:
                d_rgb = css_rgb(m.group(2))
                kind, detail = classify_colour(f_s, d_rgb)
                if kind == "different":
                    out.append(("border-colour", detail))
                elif kind == "token-layer":
                    out.append(("border-colour~", detail))
                f_sw = fb.get("sw") or 1
                if abs(float(m.group(1)) - f_sw) > 0.4:
                    out.append(("border-width", "figma %s vs build %s" % (f_sw, m.group(1))))
        else:
            out.append(("border", "figma %s %spx vs build none" % (f_s, fb.get("sw"))))
    fr = fb.get("r")
    if fr is not None and not isinstance(fr, list):
        # Compare EFFECTIVE radii: a radius can never exceed half the shorter side, so Figma's 999 on a
        # 44px pill and CSS's `50%` on a circle both mean "fully round" and must compare equal.
        f_eff = effective_radius(fr, fb["w"], fb["h"])
        d_eff = effective_radius(db.get("radius", "0px"), db["w"], db["h"])
        if abs(f_eff - d_eff) > 0.6:
            out.append(("radius", "figma %s (effective %.1f) vs build %s (effective %.1f)" % (
                fr, f_eff, db.get("radius", "0px"), d_eff)))
    if abs(fb["w"] - db["w"]) > SIZE_TOL:
        out.append(("width", "figma %s vs build %s" % (fb["w"], db["w"])))
    if abs(fb["h"] - db["h"]) > SIZE_TOL:
        out.append(("height", "figma %s vs build %s" % (fb["h"], db["h"])))
    return out


# ---------------------------------------------------------------------------
# The diff
# ---------------------------------------------------------------------------


def diff(figma, dom):
    f_texts = figma.get("texts", [])
    items = dom.get("items", [])
    pairs, f_only, d_only = pair_texts(f_texts, items)
    rows = []
    prev_dy = 0.0
    for fi, di, how in pairs:
        ft, dt = f_texts[fi], items[di]
        diffs = text_diffs(ft, dt)
        col = colour_diff(ft, dt)
        if col and col[0] == "different":
            diffs.append(("colour", col[1]))
        elif col and col[0] == "token-layer":
            diffs.append(("colour~", col[1]))
        dx = x_offset(ft, dt)
        dy = (dt.get("ty", dt["y"]) - ft["y"])
        step = dy - prev_dy
        prev_dy = dy
        if dx is not None and abs(dx) > POS_TOL:
            diffs.append(("x", "%+.1f px (figma %.1f, build %.1f)" % (dx, ft["x"], dt.get("tx", dt["x"]))))
        if abs(step) > POS_TOL:
            diffs.append(("y-shift", "%+.1f px introduced here (running dy %+.1f)" % (step, dy)))
        rows.append({"text": ft["t"][:80], "how": how, "figma": {"x": ft["x"], "y": ft["y"], "fs": ft.get("fs"),
                     "fw": ft.get("fw"), "c": ft.get("c")}, "build": {"x": dt.get("tx", dt["x"]),
                     "y": dt.get("ty", dt["y"]), "fs": dt.get("fs"), "fw": dt.get("fw"), "color": dt.get("color")},
                     "dy": round(dy, 1), "diffs": [{"kind": k, "detail": d} for k, d in diffs]})
    # boxes
    f_boxes = [b for b in figma.get("boxes", []) if (b.get("f") or b.get("s")) and b.get("f") != "image"
               and b["w"] >= 24 and b["h"] >= 24]
    text_pair_by_f = {fi: di for fi, di, _ in pairs}
    box_rows = []
    for fb in f_boxes:
        members = []
        for fi, di in text_pair_by_f.items():
            ft = f_texts[fi]
            if contains(fb, ft["x"] + ft["w"] / 2.0, ft["y"] + ft["h"] / 2.0):
                members.append(di)
        if not members:
            continue
        dbi = dom_box_for(items, members)
        if dbi is None:
            box_rows.append({"figma_box": fb["n"], "id": fb["id"], "rect": [fb["x"], fb["y"], fb["w"], fb["h"]],
                             "diffs": [{"kind": "no-box", "detail": "the build paints no box around the %d text(s) "
                                        "that sit in this Figma box" % len(members)}]})
            continue
        db = items[dbi]
        bd = box_diffs(fb, db)
        if bd:
            box_rows.append({"figma_box": fb["n"], "id": fb["id"], "rect": [fb["x"], fb["y"], fb["w"], fb["h"]],
                             "build_rect": [db["x"], db["y"], db["w"], db["h"]], "build_cls": db.get("cls", ""),
                             "diffs": [{"kind": k, "detail": d} for k, d in bd]})
    return {
        "summary": {
            "figma_texts": len(f_texts), "build_texts": sum(1 for it in items if it.get("text")),
            "paired": len(pairs), "figma_only": len(f_only), "build_only": len(d_only),
            "text_rows_with_diffs": sum(1 for r in rows if r["diffs"]), "boxes_with_diffs": len(box_rows),
            "build_dom_truncated": bool(dom.get("truncated")),
        },
        "pairs": rows,
        "figma_only": [{"text": f_texts[i]["t"][:100], "x": f_texts[i]["x"], "y": f_texts[i]["y"],
                        "fs": f_texts[i].get("fs"), "fw": f_texts[i].get("fw")} for i in f_only],
        "build_only": [{"text": items[i]["text"][:100], "y": items[i].get("ty", items[i]["y"]),
                        "cls": items[i].get("cls", ""), "fs": items[i].get("fs")} for i in d_only],
        "boxes": box_rows,
    }


def render(slug, result, limit):
    lines = []
    s = result["summary"]
    lines.append("=== %s: %d figma texts, %d build texts, %d paired, %d figma-only, %d build-only; "
                 "%d paired texts differ, %d boxes differ%s ===" % (
                     slug, s["figma_texts"], s["build_texts"], s["paired"], s["figma_only"], s["build_only"],
                     s["text_rows_with_diffs"], s["boxes_with_diffs"],
                     " (BUILD DOM TRUNCATED)" if s["build_dom_truncated"] else ""))
    lines.append("--- paired texts with differences (kind: detail) ---")
    for r in result["pairs"]:
        if r["diffs"]:
            lines.append("%-46s [%s]" % (r["text"][:46], r["how"]))
            for d in r["diffs"]:
                lines.append("    %-14s %s" % (d["kind"], d["detail"]))
    lines.append("--- in the design, not in the build (copy or element missing) ---")
    for r in result["figma_only"]:
        lines.append("  y=%-6s %sx%s  %s" % (r["y"], r["fs"], r["fw"], r["text"]))
    lines.append("--- in the build, not in the design ---")
    for r in result["build_only"]:
        lines.append("  y=%-6s %s  %s  (%s)" % (r["y"], r["fs"], r["text"], r["cls"]))
    lines.append("--- boxes (Figma frame vs the build's painted box around the same texts) ---")
    for b in result["boxes"]:
        lines.append("%s %s figma%s%s" % (b["figma_box"], b["id"], b["rect"], " build%s %s" % (b["build_rect"], b["build_cls"][:30]) if b.get("build_rect") else ""))
        for d in b["diffs"]:
            lines.append("    %-14s %s" % (d["kind"], d["detail"]))
    if limit and len(lines) > limit:
        lines = lines[:limit] + ["... %d more line(s); re-run with --limit 0 or --json" % (len(lines) - limit)]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dom", required=True, help="<slug>.<engine>.dom.json from vp_capture_marketing.py")
    ap.add_argument("--figma", default=None, help="override the figma-style file")
    ap.add_argument("--json", default=None, help="also write the full result here")
    ap.add_argument("--limit", type=int, default=300, help="max printed lines (0 = all)")
    args = ap.parse_args()
    result = diff(load_figma(args.slug, args.figma), load_dom(args.dom))
    print(render(args.slug, result, args.limit))
    if args.json:
        vp.dump_json(args.json, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
