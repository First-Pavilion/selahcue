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

    python3 scripts/vp_compare.py --run DIR [--min-ssim 0.90]

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
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402
from PIL import Image  # noqa: E402


# ---------------------------------------------------------------------------
# Capture loading
# ---------------------------------------------------------------------------


def load_captures(run):
    out = []
    for group in ("web", "native"):
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


def compare_pair(cap, ref_path, out_dir, min_ssim):
    result = {"reference": os.path.basename(ref_path)}
    actual = image_of(cap)
    with Image.open(ref_path) as ref_im:
        ref = ref_im.convert("RGB")
    act = actual.convert("RGB")
    result["reference_size"] = list(ref.size)
    result["actual_size"] = list(act.size)
    if ref.size != act.size:
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
                import re as _re

                ok = bool(_re.search(pattern, text))
                if ok and forbidden and _re.search(forbidden, text):
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
            esc(d["region"]),
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
            % (d["status"], d.get("engine", ""), d["id"], d["region"], d.get("value", ""), bound,
               d.get("permanence", ""))
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


CAVEAT = (
    "A Blink screenshot is not evidence about WKWebView, which is what Tauri ships on macOS; "
    "recorded defects in this codebase (a class `display` rule defeating the `hidden` attribute, "
    "flex <select> collapse, grid implicit-auto-row overflow) reproduce only in WebKit/WKWebView. "
    "Neither engine here is WKWebView inside a Tauri window. A Figma frame marked `board` is a "
    "multi-state spec sheet, not a screen, and is never scored. Native captures are the CPU "
    "rasterizer, not a photograph of a running output window."
)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="run directory containing web/ and/or native/")
    ap.add_argument("--min-ssim", type=float, default=None, help="gate similarity at this value (default: report only)")
    ap.add_argument("--deviations", default=vp.DEVIATIONS_PATH)
    ap.add_argument("--surfaces", default=vp.SURFACES_PATH)
    ap.add_argument(
        "--allow-missing",
        action="store_true",
        help="do not fail when a catalogued surface is absent (use with a --only/--skip run)",
    )
    args = ap.parse_args()

    run = os.path.abspath(args.run)
    captures = load_captures(run)
    if not captures:
        print("FAIL: no captures found under " + run)
        return 2
    store = vp.ReferenceStore()
    ok_store, store_problems = store.verify()
    deviations = vp.load_json(args.deviations)
    min_ssim = args.min_ssim if args.min_ssim is not None else 0.90

    failures = []
    pairs = []
    regions_by_capture = {}
    engines = {}

    for cap in sorted(captures, key=lambda c: (c["group"], c["slug"], c.get("engine", ""))):
        if cap.get("scale", 1) != 1:
            continue
        engines[cap.get("engine", "?")] = ENGINE_NOTE.get(cap.get("engine"), cap.get("engine_detail", ""))
        entry = {
            "slug": cap["slug"],
            "engine": cap.get("engine"),
            "engine_detail": cap.get("engine_detail"),
            "node": cap.get("node"),
            "actual_size": cap.get("actual_size"),
            "actual_path": os.path.relpath(os.path.join(cap["dir"], cap["png"]), run) if cap.get("png") else None,
        }
        img = image_of(cap)

        # --- capture liveness FIRST. A blank frame scores like a result. ---
        if img is None:
            entry["summary"] = "NO IMAGE — the capture step produced nothing, so nothing below was compared"
            failures.append("%s (%s): no image" % (cap["slug"], cap.get("engine")))
            pairs.append(entry)
            continue
        expect_uniform = cap["slug"].endswith("blackout") or cap.get("state") == "blackout"
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
        res = compare_pair(cap, ref_path, cmp_out, min_ssim)
        entry.update(res)
        entry["reference_path"] = os.path.relpath(ref_path, run)
        entry["diff_path"] = os.path.relpath(os.path.join(cmp_out, res["diff"]), run)
        entry["summary"] = "SSIM %.4f (local, 8x8) · mean delta %.1f/255 · %.1f%% of pixels differ >12 · %s" % (
            res["ssim"], res["pixel_delta_mean"], 100 * res["pixel_delta_fraction_over_12"], res["verdict"],
        )
        if res.get("size_mismatch"):
            entry["summary"] += " · SIZE MISMATCH (reference resized to compare)"
        if args.min_ssim is not None and res["ssim"] < args.min_ssim:
            failures.append("%s (%s): SSIM %.4f < %.4f" % (cap["slug"], cap.get("engine"), res["ssim"], args.min_ssim))
        pairs.append(entry)

    # COVERAGE FIRST. A run that lost an entire capture group must not report
    # "0 failures" over the groups that survived — that is the same failure mode
    # as a blank frame, one level up: the harness scores what it has and says
    # nothing about what it never captured. (This fired for real the first time
    # the native crate failed to compile mid-run.)
    catalogue = vp.load_json(args.surfaces)
    captured_slugs = {c["slug"] for c in captures}
    missing = [
        e["slug"]
        for group in ("web", "native")
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
    if files_in_run > vp.MAX_FILES_PER_RUN:
        failures.append(
            "this run wrote %d files, over MAX_FILES_PER_RUN=%d — run eviction caps how many runs "
            "survive, not how large one run may get, so a per-state loop could grow a single run "
            "without limit" % (files_in_run, vp.MAX_FILES_PER_RUN)
        )

    dev_rows = gate_deviations(deviations, regions_by_capture)
    exempt = {(d["capture"], d["region"]) for d in dev_rows}
    survey = survey_contrast(regions_by_capture, exempt)

    for row in dev_rows:
        if row["status"] == "FAIL":
            failures.append("deviation %s/%s [%s]: %s" % (row["id"], row["region"], row.get("engine", ""), row.get("detail", "")))
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
        "run": os.path.basename(run),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "caveat": CAVEAT,
        "engines": engines,
        "pairs": pairs,
        "deviations": dev_rows,
        "contrast_survey": survey,
        "reference_store_ok": ok_store,
        "missing_captures": missing,
        "files_in_run": files_in_run,
        "max_files_per_run": vp.MAX_FILES_PER_RUN,
        "failures": failures,
    }
    vp.dump_json(os.path.join(run, "report.json"), report)
    write_html(os.path.join(run, "report.html"), report)
    write_md(os.path.join(run, "report.md"), report)

    print("\n--- allowed deviations ---")
    for row in dev_rows:
        print("%-12s %-8s %-38s %-22s %s" % (row["status"], row.get("engine", ""), row["id"], row["region"], row.get("detail", "")[:100]))
    print("\n--- contrast survey (threshold by rendered size) ---")
    for row in survey:
        print(
            "%-7s %-8s %-16s %-22s %-12s need %.1f (%-28s) got %.2f"
            % (row["status"], row.get("engine", ""), row["capture"], row["region"], row["font"],
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
    print("\n=== visual parity: 0 failures (similarity is reported, not gated%s) ===" % (
        "" if args.min_ssim is None else "; SSIM gated at %.2f" % args.min_ssim))
    return 0


if __name__ == "__main__":
    sys.exit(main())
