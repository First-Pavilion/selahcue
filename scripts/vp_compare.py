#!/usr/bin/env python3
"""Comparator + report for the visual-parity harness.

Takes a run directory produced by `vp_capture_web.py` / `vp_capture_native.py`,
pairs every capture with its committed Figma reference, and emits:

  * a per-pair similarity report (dimensions, local SSIM, pixel-delta stats)
  * a diff image per pair (differences in red, low-SSIM blocks tinted blue)
  * the ALLOWED-DEVIATION gate, re-measured from this run's capture
  * a contrast survey of every declared region, against the threshold that
    actually applies to its rendered text size
  * `report.html` (images side by side) and `report.md`

    python3 scripts/vp_compare.py --run DIR [--min-ssim 0.90] [--suite marketing]

SUITES. `--suite operator` (default) is the desktop operator. `--suite marketing` pairs the
marketing site's full-page captures with their Figma frames. Pages there are LONG and their
height legitimately differs from the frame's (the code carries real content where Figma drew
a placeholder), so the pair is compared TOP-ALIGNED over the shared height and the height
delta is reported as a measurement of its own, rather than stretching one image to fit the
other — which would turn a content difference into a phantom layout difference everywhere.

WHAT MAKES A RUN FAIL (exit 1)
  * a capture that did not happen, or came back blank/uniform when it should
    have drawn — asserted BEFORE any similarity number is computed, because a
    blank frame scores like a result and means nothing;
  * an allowed-deviation entry whose region no longer meets its recorded bound;
  * a contrast violation in a declared region that is NOT on the deviation list.

Similarity is REPORTED, not gated, unless you pass --min-ssim. The Design 2.0
surfaces are not converged yet; a hard SSIM gate today would only be satisfied by
lowering it. Turn it on per surface once one is actually converged.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402
from PIL import Image  # noqa: E402


# ---------------------------------------------------------------------------
# Capture loading
# ---------------------------------------------------------------------------


def load_captures(run, groups=("web", "native")):
    out = []
    for group in groups:
        path = os.path.join(run, group, "captures.json")
        if not os.path.exists(path):
            continue
        data = vp.load_json(path)
        for cap in data.get("captures", []):
            cap["group"] = group
            cap["dir"] = os.path.join(run, group)
            out.append(cap)
    return out


def image_of(cap, hi=False):
    name = cap.get("png")
    if not name:
        return None
    if hi:
        name = name.replace(".png", "@2x.png")
    path = os.path.join(cap["dir"], name)
    if not os.path.exists(path):
        return None
    return Image.open(path)


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------


def align_top_crop(ref, act):
    """Crop both images to their shared top-left rectangle. Pure; returns (ref, act, height_delta, width_delta).

    `height_delta` is `act.height - ref.height` and `width_delta` is `act.width - ref.width`: positive
    when the build is TALLER / WIDER than the frame. A page that overflows horizontally is a finding,
    and is compared over the shared width rather than stretched: stretching a 1,959px frame to a
    14,441px capture (the old behaviour) cost 1.6 GB and produced a higher, wrong score.
    """
    w = min(ref.width, act.width)
    h = min(ref.height, act.height)
    box = (0, 0, w, h)
    return ref.crop(box), act.crop(box), act.height - ref.height, act.width - ref.width


def compare_pair(cap, ref_path, out_dir, min_ssim, align="stretch"):
    result = {"reference": os.path.basename(ref_path)}
    actual = image_of(cap)
    with Image.open(ref_path) as ref_im:
        ref = ref_im.convert("RGB")
    act = actual.convert("RGB")
    result["reference_size"] = list(ref.size)
    result["actual_size"] = list(act.size)
    if align == "top-crop":
        ref, act, delta, width_delta = align_top_crop(ref, act)
        result["height_delta"] = delta
        result["width_delta"] = width_delta
        result["compared_height"] = ref.height
        if delta or width_delta:
            result["size_mismatch"] = True
    elif ref.size != act.size:
        result["size_mismatch"] = True
        ref = ref.resize(act.size, Image.LANCZOS)
    mean, blocks, grid = vp.block_ssim(ref, act)
    delta_mean, delta_frac = vp.pixel_delta_stats(ref, act)
    result.update(
        {
            "ssim": mean,
            "grid": list(grid),
            "pixel_delta_mean": delta_mean,
            "pixel_delta_fraction_over_12": delta_frac,
            "verdict": "converged" if mean >= min_ssim else "diverged",
        }
    )
    diff = vp.diff_image(ref, act, blocks, grid)
    diff_name = "%s.%s.diff.png" % (cap["slug"], cap.get("engine", "x"))
    diff.save(os.path.join(out_dir, diff_name))
    result["diff"] = diff_name
    # Worst regions, in reference coordinates, so a human knows where to look.
    bw, bh = grid
    worst = sorted(range(len(blocks)), key=lambda i: blocks[i])[:8]
    result["worst_blocks"] = [
        {
            "x": (i % bw) * vp.SSIM_BLOCK,
            "y": (i // bw) * vp.SSIM_BLOCK,
            "ssim": round(blocks[i], 4),
        }
        for i in worst
    ]
    return result


# ---------------------------------------------------------------------------
# Contrast + deviation gate
# ---------------------------------------------------------------------------


def measure_regions(cap):
    """Contrast/opacity for every declared region of a capture, both ways."""
    lo = image_of(cap)
    hi = image_of(cap, hi=True)
    img, scale = (hi, cap.get("scale", 1) * 2) if hi is not None else (lo, cap.get("scale", 1))
    measured = {}
    for region in cap.get("driver", {}).get("regions", []):
        rec = {
            "id": region["id"],
            "selector": region["selector"],
            "kind": region.get("kind", "text"),
            "painted": region.get("painted"),
            "text": region.get("text", ""),
            "font_px": region.get("fontSize"),
            "font_weight": region.get("fontWeight"),
            "effective_opacity": vp.effective_opacity(region.get("chain") or []),
        }
        dom = vp.dom_region_contrast(region)
        if dom:
            rec["dom"] = dom
        if img is not None:
            pix = vp.region_pixel_contrast(img, region["rect"], scale=scale)
            rec["pixel"] = pix  # may be None — an honest "cannot measure"
        measured[region["id"]] = rec
    return measured


def gate_deviations(deviations, regions_by_capture):
    """Re-measure every allowed-deviation entry against THIS run's capture.

    Checked ONCE PER ENGINE. Collapsing the engines into one row would let a
    WebKit-only regression hide behind a green Blink measurement — and
    WebKit/WKWebView is the engine that actually ships, with recorded defects in
    this codebase that Blink does not reproduce.
    """
    rows = []
    for dev in deviations.get("deviations", []):
        cap_slug = dev["capture"]
        by_engine = regions_by_capture.get(cap_slug) or {}
        engines = sorted(by_engine) or [None]
        for engine in engines:
          for region_id in dev["regions"]:
            row = {
                "id": dev["id"],
                "capture": cap_slug,
                "engine": engine or "",
                "region": region_id,
                "metric": dev["metric"],
                "category": dev.get("category", ""),
                "permanence": dev.get("permanence", ""),
                "retire_when": dev.get("retire_when", ""),
                "requires": dev["requires"],
                "recorded": dev.get("measured", {}),
                "figma": dev.get("figma", {}),
                "reason": dev.get("reason", ""),
            }
            regions = by_engine.get(engine) if engine else None
            if regions is None:
                row.update(status="UNCHECKED", detail="capture %r was not produced in this run" % cap_slug)
                rows.append(row)
                continue
            rec = regions.get(region_id)
            if rec is None:
                row.update(status="FAIL", detail="region %r was not captured — the selector no longer matches" % region_id)
                rows.append(row)
                continue
            if not rec.get("painted"):
                row.update(status="FAIL", detail="region is in the DOM but not painted (display/zero box)")
                rows.append(row)
                continue

            if dev["metric"] == "contrast":
                dom = rec.get("dom")
                if not dom:
                    row.update(status="FAIL", detail="could not resolve a foreground colour for the region")
                    rows.append(row)
                    continue
                value = dom["ratio"]
                need = float(dev["requires"]["min"])
                row["value"] = round(value, 2)
                row["applies"] = dom["threshold"]
                pix = rec.get("pixel")
                row["pixel_value"] = round(pix["ratio"], 2) if pix else None
                ok = value >= need
                row["status"] = "INTENTIONAL" if ok else "FAIL"
                row["detail"] = "composited %.2f:1 vs required %.2f:1 (%s); ink %s on %s at opacity %.3f" % (
                    value, need, dev["requires"]["threshold"], dom["ink_composited"], dom["bg"], dom["opacity"],
                )
                if ok and dom["required"] > need:
                    row["status"] = "WARN"
                    row["detail"] += (
                        " — NOTE the rendered size/weight (%s / %s) demands %.1f:1, stricter than this entry's bound"
                        % (dom["font_px"], dom["font_weight"], dom["required"])
                    )
                if ok and pix and abs(pix["ratio"] - value) / max(value, 0.01) > 0.5:
                    row["detail"] += " — pixel sample disagrees (%.2f:1); one of the two models is wrong, worth a look" % pix["ratio"]
                recorded = dev.get("measured", {}).get("value")
                if isinstance(recorded, (int, float)) and abs(value - recorded) > 0.05:
                    row["drift"] = "recorded %.2f, now %.2f" % (recorded, value)

            elif dev["metric"] == "effective_opacity":
                value = rec["effective_opacity"]
                want = float(dev["requires"]["equals"])
                tol = float(dev["requires"].get("tolerance", 0.001))
                row["value"] = round(value, 4)
                ok = abs(value - want) <= tol
                row["status"] = "INTENTIONAL" if ok else "FAIL"
                row["detail"] = "effective opacity %.4f, required %.4f +/- %.4f (product of every ancestor's opacity)" % (
                    value, want, tol,
                )

            elif dev["metric"] == "text_matches":
                text = rec.get("text", "")
                pattern = dev["requires"]["pattern"]
                forbidden = dev["requires"].get("must_not_match")
                ok = bool(re.search(pattern, text))
                if ok and forbidden and re.search(forbidden, text):
                    ok = False
                row["value"] = text
                row["status"] = "INTENTIONAL" if ok else "FAIL"
                row["detail"] = "rendered text %r must match /%s/%s" % (
                    text, pattern, (" and not /%s/" % forbidden) if forbidden else "",
                )
            else:
                row.update(status="FAIL", detail="unknown metric %r" % dev["metric"])
            rows.append(row)
    return rows


def survey_contrast(regions_by_capture, exempt):
    """Every declared region against the threshold its rendered size demands.

    The useful finding is not "this pairing is under 4.5:1" — plenty of pairings
    legitimately sit between 3 and 4.5 behind large type — but "this pairing
    carries text too small for the ratio it has".
    """
    rows = []
    for cap_slug, by_engine in sorted(regions_by_capture.items()):
      for engine, regions in sorted(by_engine.items()):
        for region_id, rec in sorted(regions.items()):
            dom = rec.get("dom")
            if not dom or rec.get("kind") == "ui":
                continue
            need = dom["required"]
            value = dom["ratio"]
            status = "pass" if value >= need else "FAIL"
            if status == "FAIL" and (cap_slug, region_id) in exempt:
                status = "exempt"
            rows.append(
                {
                    "capture": cap_slug,
                    "engine": engine,
                    "region": region_id,
                    "text": rec.get("text", "")[:40],
                    "font": "%s / %s" % (rec.get("font_px"), rec.get("font_weight")),
                    "threshold": dom["threshold"],
                    "required": need,
                    "value": round(value, 2),
                    "pixel": round(rec["pixel"]["ratio"], 2) if rec.get("pixel") else None,
                    "opacity": round(rec.get("effective_opacity", 1.0), 3),
                    "status": status,
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

ENGINE_NOTE = {
    "blink": "headless Chrome (Blink) — NOT the engine Tauri ships; treat as browser-portable layout evidence only",
    "webkit": "Playwright WebKit (WebCore/JSC) — same engine FAMILY as the shipped WKWebView, but not WKWebView-in-Tauri",
    "cpu-raster": "selahcue-engine CPU rasterizer — the same code the GPU compositor is held to at SSIM >= 0.99",
}


def write_html(path, report):
    def esc(v):
        return html.escape(str(v))

    rows = []
    for pair in report["pairs"]:
        ref_src = pair.get("reference_path", "")
        act_src = pair.get("actual_path", "")
        diff_src = pair.get("diff_path", "")
        imgs = "".join(
            '<figure><figcaption>%s</figcaption><img src="%s" loading="lazy"></figure>' % (esc(lbl), esc(src))
            for lbl, src in (("Figma reference", ref_src), ("captured", act_src), ("diff", diff_src))
            if src
        )
        rows.append(
            """<section class="pair">
  <h3>%s <span class="eng">%s</span></h3>
  <p class="meta">%s</p>
  <div class="strip">%s</div>
</section>"""
            % (
                esc(pair["slug"]),
                esc(pair.get("engine", "")),
                esc(pair.get("summary", "")),
                imgs,
            )
        )

    dev_rows = "".join(
        "<tr class='%s'><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (
            esc(d["status"].lower()),
            esc(d["status"]),
            esc(d.get("engine", "")),
            esc(d["id"]),
            esc(d.get("region", d.get("capture", ""))),
            esc(d.get("value", "")),
            esc(d["requires"].get("min", d["requires"].get("equals", d["requires"].get("pattern", "")))),
            esc(d.get("permanence", "")),
            esc(d.get("detail", "")),
        )
        for d in report["deviations"]
    )
    survey_rows = "".join(
        "<tr class='%s'><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (
            esc(s["status"].lower()),
            esc(s["status"]),
            esc(s.get("engine", "")),
            esc(s["capture"]),
            esc(s["region"]),
            esc(s["font"]),
            esc(s["threshold"]),
            esc(s["required"]),
            esc(s["value"]),
            esc(s["pixel"]),
        )
        for s in report["contrast_survey"]
    )
    doc = """<!doctype html><meta charset="utf-8"><title>SelahCue visual parity — %s</title>
<style>
 :root{color-scheme:dark}
 body{background:#0b0d12;color:#e8eaf0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:28px}
 h1{margin:0 0 4px} h2{margin:32px 0 8px;border-bottom:1px solid #2a2e3a;padding-bottom:6px}
 .warnbox{background:#2a1a0d;border:1px solid #7a4a12;padding:12px 16px;border-radius:8px;margin:16px 0}
 table{border-collapse:collapse;width:100%%;font-size:13px} td,th{border:1px solid #262a35;padding:5px 8px;text-align:left;vertical-align:top}
 th{background:#171a22}
 tr.fail td{background:#2b1114} tr.intentional td{background:#10231b} tr.warn td{background:#2a2411}
 tr.pass td{background:#12151c} tr.exempt td{background:#10231b} tr.unchecked td{background:#1c1c22}
 .pair{margin:24px 0;border:1px solid #222733;border-radius:10px;padding:12px}
 .pair h3{margin:0 0 4px;font-size:15px} .eng{font-weight:400;color:#8b93a5;font-size:12px}
 .meta{margin:0 0 10px;color:#a7aebe;font-size:12px}
 .strip{display:flex;gap:10px;overflow-x:auto} figure{margin:0;flex:1 1 0;min-width:240px}
 figcaption{font-size:11px;color:#8b93a5;margin-bottom:4px} img{width:100%%;border:1px solid #262a35;border-radius:6px}
 code{background:#171a22;padding:1px 5px;border-radius:4px}
</style>
<h1>SelahCue visual parity</h1>
<p class="meta">run %s &middot; %d pairs compared &middot; %d captured but not compared</p>
<div class="warnbox"><b>What this does not prove.</b> %s</div>
<h2>Allowed deviations (re-measured this run)</h2>
<p class="meta">An entry is a GATE: it carries its bound and is re-measured from this run's capture. <code>INTENTIONAL</code> = deliberate and still within bound. <code>FAIL</code> = the deviation no longer holds.</p>
<table><tr><th>status</th><th>engine</th><th>id</th><th>region</th><th>measured</th><th>bound</th><th>permanence</th><th>detail</th></tr>%s</table>
<h2>Contrast survey (threshold chosen by rendered size)</h2>
<table><tr><th>status</th><th>engine</th><th>capture</th><th>region</th><th>px / weight</th><th>threshold</th><th>required</th><th>composited</th><th>pixel-sampled</th></tr>%s</table>
<h2>Pairs</h2>
%s
""" % (
        esc(report["run"]),
        esc(report["run"]),
        len([p for p in report["pairs"] if p.get("ssim") is not None]),
        len([p for p in report["pairs"] if p.get("ssim") is None]),
        esc(report["caveat"]),
        dev_rows,
        survey_rows,
        "\n".join(rows),
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)


def write_md(path, report):
    L = []
    L.append("# SelahCue visual parity — %s\n" % report["run"])
    L.append("**What this does not prove.** %s\n" % report["caveat"])
    L.append("## Engines in this run\n")
    for eng, note in sorted(report["engines"].items()):
        L.append("- `%s` — %s\n" % (eng, note))
    L.append("\n## Allowed deviations (re-measured this run)\n")
    L.append("| status | engine | id | region | measured | bound | permanence |\n|---|---|---|---|---|---|---|\n")
    for d in report["deviations"]:
        bound = d["requires"].get("min", d["requires"].get("equals", d["requires"].get("pattern", "")))
        L.append(
            "| %s | %s | %s | %s | %s | %s | %s |\n"
            % (d["status"], d.get("engine", ""), d["id"], d.get("region", d.get("capture", "")),
               d.get("value", ""), bound, d.get("permanence", ""))
        )
    L.append("\n## Pairs\n")
    L.append("| capture | engine | reference | size | SSIM | mean delta | >12/px | verdict |\n|---|---|---|---|---|---|---|---|\n")
    for p in report["pairs"]:
        L.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s |\n"
            % (
                p["slug"],
                p.get("engine", ""),
                p.get("reference", "—"),
                "x".join(str(v) for v in (p.get("actual_size") or [])),
                ("%.4f" % p["ssim"]) if p.get("ssim") is not None else "—",
                ("%.1f" % p["pixel_delta_mean"]) if p.get("pixel_delta_mean") is not None else "—",
                ("%.1f%%" % (100 * p["pixel_delta_fraction_over_12"])) if p.get("pixel_delta_fraction_over_12") is not None else "—",
                p.get("verdict", p.get("summary", "")),
            )
        )
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(L)


MARKETING_CAVEAT = (
    "Pages are captured full-page at 1440 wide by Playwright (Blink and/or WebKit) from the built "
    "`dist/` with the account API scripted; they say nothing about Safari on iOS, real devices, "
    "other widths, or a signed-in session against a real API. Similarity is computed over the top "
    "of each page where the build and the frame share a height, so a taller build (real content "
    "where Figma drew a placeholder) is reported as a height difference, not as a low score for "
    "the shared part. A low SSIM is a pointer to look, not a verdict: classification is in the "
    "audit report. Inter must have loaded for a capture to be accepted."
)

CAVEAT = (
    "A Blink screenshot is not evidence about WKWebView, which is what Tauri ships on macOS; "
    "recorded defects in this codebase (a class `display` rule defeating the `hidden` attribute, "
    "flex <select> collapse, grid implicit-auto-row overflow) reproduce only in WebKit/WKWebView. "
    "Neither engine here is WKWebView inside a Tauri window. A Figma frame marked `board` is a "
    "multi-state spec sheet, not a screen, and is never scored. Native captures are the CPU "
    "rasterizer, not a photograph of a running output window."
)


# ---------------------------------------------------------------------------
# Marketing suite: DOM-backed gate, contrast survey, source probe
# ---------------------------------------------------------------------------


def load_dom(cap):
    """The capture's DOM/style dump, or None."""
    dom, _problem = load_dom_checked(cap)
    return dom


def load_dom_checked(cap):
    """(dump, problem). A dump that is missing, unreadable, or truncated is a PROBLEM, not a skip.

    The marketing deviation gate reads these dumps. A gate that quietly treats "no dump" as "nothing
    to check" can be switched off by deleting a file (it was: two dumps deleted from a copy of a run
    left exit 0 and "0 failures"), and a truncated dump makes `text_absent` read part of a page.
    """
    name = cap.get("dom")
    if not name:
        return None, "the capture record names no DOM dump"
    path = os.path.join(cap["dir"], name)
    if not os.path.exists(path):
        return None, "DOM dump %s is missing" % name
    try:
        dom = vp.load_json(path)
    except (OSError, ValueError, SystemExit) as exc:
        return None, "DOM dump %s is unreadable (%s)" % (name, str(exc)[:80])
    if not isinstance(dom, dict) or not isinstance(dom.get("items"), list):
        return None, "DOM dump %s has no items list" % name
    if dom.get("truncated"):
        return None, ("DOM dump %s is TRUNCATED at %d items: the text and contrast checks would read part of "
                      "the page" % (name, len(dom["items"])))
    return dom, None


def dom_text(dom):
    """All rendered text on the page, joined — what a visitor could read."""
    return "\n".join(it.get("text", "") for it in (dom or {}).get("items", []) if it.get("text"))


def gate_marketing_deviations(deviations, by_capture):
    """Re-measure every marketing deviation entry against THIS run's captures, once per engine.

    `by_capture` maps slug -> {engine: {"doc": {...}, "text": "...all rendered text..."}}.

    Same contract as the operator gate, including the per-engine rows: collapsing the engines would
    let a WebKit-only regression hide behind a green Blink row. An entry that cannot fail would
    authorise the drift it exists to prevent. Metrics:

      doc_height    the rendered page is at least `requires.min` px tall (a documented
                    "the build carries real content where Figma drew a placeholder")
      text_present  `requires.pattern` matches the page's rendered text
      text_absent   `requires.pattern` matches NOTHING in the page's rendered text
                    (an honest-content decision: the build must not say this)
    """
    rows = []
    for dev in deviations.get("deviations", []):
        base = {
            "id": dev["id"], "capture": dev["capture"], "metric": dev["metric"],
            "category": dev.get("category", ""), "permanence": dev.get("permanence", ""),
            "retire_when": dev.get("retire_when", ""), "requires": dev["requires"],
            "source": dev.get("source", ""), "reason": dev.get("reason", ""),
        }
        by_engine = by_capture.get(dev["capture"])
        if not by_engine:
            rows.append(dict(base, engine="", status="UNCHECKED",
                             detail="capture %r was not produced in this run" % dev["capture"]))
            continue
        for engine, got in sorted(by_engine.items()):
            row = dict(base, engine=engine)
            metric = dev["metric"]
            if metric == "doc_height":
                value = (got.get("doc") or {}).get("h")
                need = int(dev["requires"]["min"])
                ok = isinstance(value, (int, float)) and value >= need
                row.update(value=value, status="INTENTIONAL" if ok else "FAIL",
                           detail="rendered height %s px, required >= %d px" % (value, need))
            elif metric in ("text_present", "text_absent"):
                pattern = dev["requires"]["pattern"]
                found = bool(re.search(pattern, got.get("text", ""), re.I))
                ok = found if metric == "text_present" else not found
                row.update(value=("present" if found else "absent"), status="INTENTIONAL" if ok else "FAIL",
                           detail="/%s/ is %s in the rendered text; required %s" % (
                               pattern, "present" if found else "absent",
                               "present" if metric == "text_present" else "absent"))
            else:
                row.update(status="FAIL", detail="unknown metric %r" % metric)
            rows.append(row)
    return rows


def survey_dom_contrast(dom, limit=25):
    """Text-vs-backdrop contrast for every text node in a DOM dump, judged by its own size.

    Reported, not gated, for the marketing suite: the site has not been through an
    accessibility sweep against these frames, and a gate here would fail the run for
    findings this audit exists to RECORD rather than fix. A node whose backdrop crosses a
    gradient/image is reported as `unknown`, never given an invented number.
    Returns {"checked", "unknown", "failing": [...up to limit...], "failing_total"}.
    """
    checked = unknown = failing_total = 0
    failing = []
    for it in (dom or {}).get("items", []):
        if not it.get("text") or not it.get("color"):
            continue
        fg = vp.parse_css_color(it["color"])
        bg = vp.composite_layers(it.get("bgl") or [], base=(14, 17, 22))
        if fg is None or bg is None or it.get("bgg"):
            unknown += 1
            continue
        fg_flat = vp.blend_over(fg, bg)
        ratio = vp.contrast_ratio(fg_flat, bg)
        try:
            px = float(str(it.get("fs", "0")).replace("px", ""))
        except ValueError:
            px = 0.0
        need, label = vp.required_ratio("text", px, it.get("fw"))
        checked += 1
        if ratio < need:
            failing_total += 1
            if len(failing) < limit:
                failing.append({"text": it["text"][:50], "ratio": round(ratio, 2), "need": need,
                                "threshold": label, "px": px, "weight": it.get("fw"),
                                "color": it["color"], "bg": "rgb(%d, %d, %d)" % bg, "y": it.get("y")})
    return {"checked": checked, "unknown": unknown, "failing_total": failing_total, "failing": failing}


MAX_PROBE_JS_FILES = 400


def source_probe_problem(probe, dist=None):
    """For a `not-rendered` surface: the problem if its state has appeared in the SHIPPED bundle.

    Probes the built `dist/assets/*.js`, not `src/`: source also holds comments and tests that
    quote the very copy a deliberate non-render is about (VerifyView.vue's own comment quotes
    V4's title), and a probe that fires on a comment is a probe nobody trusts. The minifier
    strips comments, so what remains in the bundle is copy a visitor can actually be shown.

    `probe["control"]` is a string that MUST be in the bundle. It proves the probe is reading
    the shipped copy at all; a probe over an empty or wrong directory would otherwise pass
    for every state, forever.

    BOUND: at most MAX_PROBE_JS_FILES `.js` files are read, counting ONLY `.js` files, and a bundle with
    more is a FAILURE, not a pass: a probe that stops reading part-way would clear a state that is in
    the part it never read. (The first version counted every file in the folder and passed silently
    once 400 non-JS assets sorted ahead of the chunk holding the forbidden copy.)
    """
    dist = dist or os.environ.get("SELAHCUE_MARKETING_DIST") or os.path.join(
        vp.REPO, "implementation", "marketing", "dist")
    assets = os.path.join(dist, "assets")
    if not os.path.isdir(assets):
        return "no built bundle under %s to probe — run `npm run build`" % assets
    js_files = sorted(n for n in os.listdir(assets) if n.endswith(".js"))
    if len(js_files) > MAX_PROBE_JS_FILES:
        return (
            "the bundle has %d .js files, over MAX_PROBE_JS_FILES=%d: the probe will not claim it read the whole "
            "bundle, so it cannot clear a state; raise the cap deliberately" % (len(js_files), MAX_PROBE_JS_FILES)
        )
    chunks = []
    for name in js_files:
        with open(os.path.join(assets, name), "r", encoding="utf-8", errors="replace") as fh:
            chunks.append(fh.read())
    text = "\n".join(chunks)
    control = probe.get("control")
    if not control:
        return "source probe has no `control` string, so it cannot prove it is reading the bundle"
    if control not in text:
        return "probe control %r is not in the bundle — the probe is not reading the shipped copy" % control
    hits = [needle for needle in probe.get("must_not_contain", []) if needle in text]
    if hits:
        return (
            "the shipped bundle now contains %r — the state exists, so it is no longer a documented "
            "non-render: capture it and compare it" % hits[0]
        )
    return None


def run_files_problem(run, suite):
    """A sentence if this run holds more files than the suite's cap, counting the report files still to be written.

    Run eviction caps how many runs survive, not how large one run may get, so a per-state loop could
    grow a single run without limit. The three report files (and captures.json) are written AFTER this
    check, so they are counted up front. Pulled out of `main` so `vp_selftest.py` can drive it AND drive
    `main` end to end (the old self-test only looked for the word in this file's source).
    """
    files = vp.count_run_files(run)
    expected = files + suite.report_files
    if expected > suite.max_files_per_run:
        return (
            "this run wrote %d files (+%d report files still to come = %d), over the suite's cap of %d — run "
            "eviction caps how many runs survive, not how large one run may get, so a per-state loop could "
            "grow a single run without limit" % (files, suite.report_files, expected, suite.max_files_per_run)
        )
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="run directory containing the capture group(s)")
    ap.add_argument("--suite", default="operator", choices=list(vp.SUITE_NAMES))
    ap.add_argument("--min-ssim", type=float, default=None, help="gate similarity at this value (default: report only)")
    ap.add_argument("--deviations", default=None)
    ap.add_argument("--surfaces", default=None)
    ap.add_argument(
        "--allow-missing",
        action="store_true",
        help="do not fail when a catalogued surface is absent (use with a --only/--skip run)",
    )
    args = ap.parse_args()

    suite = vp.get_suite(args.suite)
    marketing = suite.name == "marketing"
    run = os.path.abspath(args.run)
    captures = load_captures(run, suite.groups)
    if not captures:
        print("FAIL: no captures found under " + run)
        return 2
    store = suite.store()
    ok_store, store_problems = store.verify()
    deviations = vp.load_json(args.deviations or suite.deviations_path)
    min_ssim = args.min_ssim if args.min_ssim is not None else suite.default_min_ssim
    align = "top-crop" if marketing else "stretch"
    # The catalogue is read ONCE, up front, and is the authority for probe definitions: a
    # probe copied into captures.json at capture time would be a stale copy of a thing the
    # reviewer is looking at in surfaces.json.
    catalogue = vp.load_json(args.surfaces or suite.surfaces_path)
    cat_by_slug = {e["slug"]: e for group in suite.groups for e in catalogue.get(group, [])}

    failures = []
    pairs = []
    regions_by_capture = {}
    dom_by_capture = {}
    contrast_dom = {}
    engines = {}

    for cap in sorted(captures, key=lambda c: (c["group"], c["slug"], c.get("engine", ""))):
        if cap.get("scale", 1) != 1:
            continue
        engines[cap.get("engine", "?")] = (
            cap.get("engine_detail", "") if marketing
            else ENGINE_NOTE.get(cap.get("engine"), cap.get("engine_detail", ""))
        )
        status = cap.get("status", "captured")
        entry = {
            "slug": cap["slug"],
            "engine": cap.get("engine"),
            "engine_detail": cap.get("engine_detail"),
            "node": cap.get("node"),
            "status": status,
            "area": cap.get("area"),
            "actual_size": cap.get("actual_size"),
            "actual_path": os.path.relpath(os.path.join(cap["dir"], cap["png"]), run) if cap.get("png") else None,
        }

        # --- a surface that is catalogued as not built: assert the probe, show Figma only ---
        if status == "unbuilt":
            probe = cap.get("probe") or {}
            ref_slug = cap.get("reference")
            ref_path = store.path_for(ref_slug) if ref_slug else None
            if ref_path and os.path.exists(ref_path):
                entry["reference_path"] = os.path.relpath(ref_path, run)
            if probe.get("confirmed"):
                entry["summary"] = (
                    "NOT BUILT (class E) — %s renders the site's 404 view (h1 %r); the Figma frame is "
                    "exported for the fix ticket, not scored" % (probe.get("path"), (probe.get("h1") or [""])[0])
                )
            else:
                entry["summary"] = "UNBUILT BUT THE ROUTE RESPONDS — probe %s" % json.dumps(probe)
                failures.append("%s: catalogued as unbuilt but the probe did not confirm it" % cap["slug"])
            for e in cap.get("errors", []):
                if e not in failures:
                    failures.append(e)
            pairs.append(entry)
            continue

        img = image_of(cap)

        # --- capture liveness FIRST. A blank frame scores like a result. ---
        if img is None:
            entry["summary"] = "NO IMAGE — the capture step produced nothing, so nothing below was compared"
            failures.append("%s (%s): no image" % (cap["slug"], cap.get("engine")))
            pairs.append(entry)
            continue
        # Header-only size, checked BEFORE any pixel is decoded (see vp_core.MAX_CAPTURE_PIXELS).
        too_big = vp.pixel_budget_problem(img.size, "capture %s (%s)" % (cap["slug"], cap.get("engine")))
        if too_big:
            entry["summary"] = "NOT DECODED — " + too_big
            failures.append(too_big)
            pairs.append(entry)
            continue
        expect_uniform = (not marketing) and (cap["slug"].endswith("blackout") or cap.get("state") == "blackout")
        uniform = vp.is_uniform(img)
        ink, _bg = vp.ink_coverage(img)
        entry["ink_coverage"] = round(ink, 4)
        if uniform and not expect_uniform:
            entry["summary"] = (
                "BLANK CAPTURE — the frame is a single colour, so the similarity number below "
                "would describe nothing that was rendered"
            )
            failures.append("%s (%s): blank capture" % (cap["slug"], cap.get("engine")))
            pairs.append(entry)
            continue
        if expect_uniform and not uniform and cap["slug"] == "audience-blackout":
            failures.append("%s: blackout output is not a single colour" % cap["slug"])

        if cap.get("errors"):
            failures.append("%s (%s): %s" % (cap["slug"], cap.get("engine"), "; ".join(cap["errors"])[:200]))

        regions = measure_regions(cap)
        if regions:
            regions_by_capture.setdefault(cap["slug"], {})[cap.get("engine", "?")] = regions

        if marketing:
            dom, dom_problem = load_dom_checked(cap)
            if dom_problem:
                # FAIL CLOSED. A missing, unreadable or truncated dump must not turn the deviation
                # gate into "unchecked, exit 0".
                failures.append("%s (%s): %s" % (cap["slug"], cap.get("engine"), dom_problem))
                entry["dom_problem"] = dom_problem
            else:
                dom_by_capture.setdefault(cap["slug"], {})[cap.get("engine", "?")] = {
                    "doc": cap.get("doc") or dom.get("doc"), "text": dom_text(dom)}
                survey = survey_dom_contrast(dom)
                contrast_dom[(cap["slug"], cap.get("engine", "?"))] = survey
                entry["contrast"] = {k: survey[k] for k in ("checked", "unknown", "failing_total")}
            if status == "not-rendered":
                probe_def = (cat_by_slug.get(cap["slug"]) or {}).get("source_probe")
                problem = source_probe_problem(probe_def) if probe_def else \
                    "not-rendered surface has no source_probe in the catalogue"
                if problem:
                    failures.append("%s: %s" % (cap["slug"], problem))
                    entry["probe_failed"] = True

        ref_slug = cap.get("reference")
        kind = cap.get("reference_kind", "screen")
        if not ref_slug or kind != "screen":
            entry["summary"] = {
                "board": "captured, NOT scored — the Figma node is a multi-state spec board, not a 1:1 screen",
                "none": "captured, NOT scored — no Figma frame depicts this surface/state",
            }.get(kind, "captured, NOT scored — no reference declared")
            pairs.append(entry)
            continue
        ref_path = store.path_for(ref_slug)
        if not os.path.exists(ref_path):
            entry["summary"] = "reference %r is not in the committed store — run vp_reference.py ingest" % ref_slug
            failures.append("%s: missing reference %s" % (cap["slug"], ref_slug))
            pairs.append(entry)
            continue
        cmp_out = os.path.join(cap["dir"])
        res = compare_pair(cap, ref_path, cmp_out, min_ssim, align=align)
        entry.update(res)
        entry["reference_path"] = os.path.relpath(ref_path, run)
        entry["diff_path"] = os.path.relpath(os.path.join(cmp_out, res["diff"]), run)
        entry["summary"] = "SSIM %.4f (local, 8x8) · mean delta %.1f/255 · %.1f%% of pixels differ >12 · %s" % (
            res["ssim"], res["pixel_delta_mean"], 100 * res["pixel_delta_fraction_over_12"], res["verdict"],
        )
        if marketing and (res.get("height_delta") or res.get("width_delta")):
            entry["summary"] += " · build is %+d px tall and %+d px wide vs the frame (compared over the shared %d px height)" % (
                res.get("height_delta", 0), res.get("width_delta", 0), res["compared_height"])
        elif res.get("size_mismatch"):
            entry["summary"] += " · SIZE MISMATCH (reference resized to compare)"
        if status == "not-rendered":
            entry["summary"] += " · NOT RENDERED BY DESIGN: compared against the shipped substitute state"
            if entry.get("probe_failed"):
                entry["summary"] += " · SOURCE PROBE FAILED"
        if args.min_ssim is not None and res["ssim"] < args.min_ssim:
            failures.append("%s (%s): SSIM %.4f < %.4f" % (cap["slug"], cap.get("engine"), res["ssim"], args.min_ssim))
        pairs.append(entry)

    # COVERAGE FIRST. A run that lost an entire capture group must not report
    # "0 failures" over the groups that survived — that is the same failure mode
    # as a blank frame, one level up: the harness scores what it has and says
    # nothing about what it never captured. (This fired for real the first time
    # the native crate failed to compile mid-run.)
    captured_slugs = {c["slug"] for c in captures}
    missing = [
        e["slug"]
        for group in suite.groups
        for e in catalogue.get(group, [])
        if e["slug"] not in captured_slugs
    ]
    if missing and not args.allow_missing:
        for slug in missing:
            failures.append(
                "catalogued surface %r was never captured in this run — it is NOT covered by any "
                "number in this report" % slug
            )

    files_in_run = vp.count_run_files(run)
    cap_problem = run_files_problem(run, suite)
    if cap_problem:
        failures.append(cap_problem)

    if marketing:
        dev_rows = gate_marketing_deviations(deviations, dom_by_capture)
        survey = []
        for (slug, engine), sv in sorted(contrast_dom.items()):
            for f in sv["failing"]:
                survey.append({"capture": slug, "engine": engine, "region": f["text"],
                               "font": "%spx / %s" % (f["px"], f["weight"]), "threshold": f["threshold"],
                               "required": f["need"], "value": f["ratio"], "pixel": None,
                               "status": "reported"})
    else:
        dev_rows = gate_deviations(deviations, regions_by_capture)
        exempt = {(d["capture"], d["region"]) for d in dev_rows}
        survey = survey_contrast(regions_by_capture, exempt)

    for row in dev_rows:
        if row["status"] == "UNCHECKED" and not args.allow_missing:
            # An unchecked entry is only acceptable in a deliberately narrowed run.
            failures.append("deviation %s/%s was not checked: %s" % (
                row["id"], row.get("region", row.get("capture", "")), row.get("detail", "")))
        if row["status"] == "FAIL":
            failures.append("deviation %s/%s [%s]: %s" % (row["id"], row.get("region", row.get("capture", "")),
                                                          row.get("engine", ""), row.get("detail", "")))
    for row in survey:
        if row["status"] == "FAIL":
            failures.append(
                "contrast %s/%s [%s]: %.2f:1 < %.1f (%s) at %s"
                % (row["capture"], row["region"], row.get("engine", ""), row["value"], row["required"],
                   row["threshold"], row["font"])
            )
    for p in store_problems:
        failures.append("reference store: " + p)

    report = {
        "suite": suite.name,
        "run": os.path.basename(run),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "caveat": MARKETING_CAVEAT if marketing else CAVEAT,
        "engines": engines,
        "pairs": pairs,
        "deviations": dev_rows,
        "contrast_survey": survey,
        "reference_store_ok": ok_store,
        "missing_captures": missing,
        "files_in_run": files_in_run,
        "max_files_per_run": suite.max_files_per_run,
        "failures": failures,
    }
    vp.dump_json(os.path.join(run, "report.json"), report)
    write_html(os.path.join(run, "report.html"), report)
    write_md(os.path.join(run, "report.md"), report)

    print("\n--- allowed deviations ---")
    for row in dev_rows:
        print("%-12s %-8s %-38s %-22s %s" % (row["status"], row.get("engine", ""), row["id"],
                                             row.get("region", row.get("capture", "")), row.get("detail", "")[:100]))
    print("\n--- contrast survey (%s) ---" % ("reported, not gated" if marketing else "threshold by rendered size"))
    for row in survey[:60 if marketing else None]:
        print(
            "%-8s %-8s %-16s %-22s %-12s need %.1f (%-28s) got %.2f"
            % (row["status"], row.get("engine", ""), row["capture"], str(row["region"])[:22], row["font"],
               row["required"], row["threshold"], row["value"])
        )
    print("\n--- pairs ---")
    for p in pairs:
        print("%-26s %-11s %s" % (p["slug"], p.get("engine", ""), p.get("summary", "")))

    print("\nreport: %s" % os.path.join(run, "report.html"))
    if failures:
        print("\n=== %d FAILURE(S) ===" % len(failures))
        for f in failures:
            print("FAIL: " + f)
        return 1
    print("\n=== visual parity [%s]: 0 failures (similarity is reported, not gated%s) ===" % (
        suite.name, "" if args.min_ssim is None else "; SSIM gated at %.2f" % args.min_ssim))
    return 0


if __name__ == "__main__":
    sys.exit(main())
