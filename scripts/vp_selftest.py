#!/usr/bin/env python3
"""Does the visual-parity harness actually BITE? — the harness's own gate.

A visual-diff harness fails silently in a way an ordinary test does not: if the
capture step breaks, it produces a blank frame; if the comparator breaks, it
produces a flattering number. Both look exactly like "no problem found". CLAUDE.md
names this class of failure directly ("Bounded-memory tests"), and its rule
generalises: *this test must fail if the control it names is removed.*

So every mechanism the harness relies on is exercised here in BOTH directions —
the hostile case is refused AND the benign case still runs, so "refused" cannot be
confused with a dead mechanism.

    python3 scripts/vp_selftest.py

Exit 0 = every control demonstrated live. Exit 1 = at least one is dead or wrong.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import random
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402
import vp_compare  # noqa: E402
import vp_capture_marketing as vcm  # noqa: E402
import vp_style_diff as vsd  # noqa: E402
import vp_slice  # noqa: E402
import build_fidelity_artifact as bfa  # noqa: E402
import check_fidelity_audit as cfa  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

RESULTS = []


def ok(passed, msg):
    RESULTS.append((bool(passed), msg))
    print(("PASS: " if passed else "FAIL: ") + msg)


def synthetic_frame(seed=0):
    img = Image.new("RGB", (640, 360), (11, 13, 23))
    d = ImageDraw.Draw(img)
    for i in range(12):
        x = 20 + i * 50 + seed
        d.rectangle([x, 40, x + 30, 300], fill=(124, 92, 255))
    d.text((40, 320), "SelahCue visual parity self-test", fill=(255, 255, 255))
    return img


# ---------------------------------------------------------------------------
# 1. The comparator
# ---------------------------------------------------------------------------


def test_comparator():
    a = synthetic_frame(0)
    same, _v, _g = vp.block_ssim(a, a.copy())
    ok(abs(same - 1.0) < 1e-6, "comparator: identical frames score SSIM 1.0 (got %.6f)" % same)

    # POSITIVE CONTROL — a deliberately wrong reference must score badly. Without
    # this, "the diff passed" is indistinguishable from a comparator that returns
    # a constant.
    wrong, _v, _g = vp.block_ssim(a, synthetic_frame(37))
    ok(
        wrong < 0.85,
        "comparator: a deliberately WRONG reference scores %.4f (< 0.85) — a comparator that "
        "cannot fail would report ~1.0 here" % wrong,
    )
    ok(
        wrong < same,
        "comparator: the wrong reference scores strictly worse than the identical one "
        "(%.4f < %.4f)" % (wrong, same),
    )

    # Chroma sensitivity: a channel swap preserves luminance structure. A
    # luminance-only metric would pass it; the per-channel minimum must not.
    swapped = Image.merge("RGB", (a.getchannel(2), a.getchannel(1), a.getchannel(0)))
    hue, _v, _g = vp.block_ssim(a, swapped)
    ok(hue < 0.95, "comparator: a chroma-only divergence is caught (%.4f < 0.95)" % hue)

    # Displacement sensitivity — the reason this harness does NOT reuse
    # selahcue_engine::analysis::ssim, which is a GLOBAL SSIM.
    shifted = a.transform(a.size, Image.AFFINE, (1, 0, -12, 0, 1, 0))
    local, _v, _g = vp.block_ssim(a, shifted)
    ok(
        local < 0.90,
        "comparator: a 12px displacement drops local SSIM to %.4f — the defect a global SSIM "
        "would barely register" % local,
    )


# ---------------------------------------------------------------------------
# 2. Blank-capture detection
# ---------------------------------------------------------------------------


def test_blank_detection():
    flat = Image.new("RGB", (320, 200), (255, 255, 255))
    ok(vp.is_uniform(flat), "blank detector: a solid frame reads as uniform")
    ok(
        not vp.is_uniform(synthetic_frame()),
        "blank detector: a drawn frame does NOT read as uniform — the positive control that "
        "keeps the detector from being hardwired to True",
    )
    ink_flat, _ = vp.ink_coverage(flat)
    ink_drawn, _ = vp.ink_coverage(synthetic_frame())
    ok(ink_flat == 0.0 and ink_drawn > 0.05,
       "blank detector: ink coverage separates flat (%.3f) from drawn (%.3f)" % (ink_flat, ink_drawn))


# ---------------------------------------------------------------------------
# 3. Bounded stores
# ---------------------------------------------------------------------------


def test_run_store_is_bounded():
    root = tempfile.mkdtemp(prefix="vp-runs-")
    try:
        names = []
        for i in range(vp.MAX_RUNS_KEPT + 3):
            name = "run-20260101-%06d" % i
            os.makedirs(os.path.join(root, name))
            with open(os.path.join(root, name, "big.png"), "wb") as fh:
                fh.write(b"0" * 1024)
            names.append(name)
        before = len(os.listdir(root))
        removed = vp.prune_runs(root)
        after = sorted(os.listdir(root))
        ok(
            len(after) == vp.MAX_RUNS_KEPT,
            "run store: %d runs pruned to %d (cap MAX_RUNS_KEPT=%d) — without this every "
            "invocation adds ~30 images to the tree, forever"
            % (before, len(after), vp.MAX_RUNS_KEPT),
        )
        ok(
            after == names[-vp.MAX_RUNS_KEPT :],
            "run store: the NEWEST runs survive and the oldest %d were evicted (%s)"
            % (len(removed), ", ".join(removed[:3])),
        )
        # Positive control: at or under the cap, nothing is deleted. Otherwise a
        # prune that deletes everything would also pass the assertion above.
        kept = sorted(os.listdir(root))
        vp.prune_runs(root)
        ok(sorted(os.listdir(root)) == kept,
           "run store: a second prune under the cap deletes NOTHING (the eviction is bounded, "
           "not indiscriminate)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_per_run_file_cap_is_enforced():
    """The per-run file cap must be CHECKED by the real comparator, not merely declared.

    Run eviction caps how many runs survive, not how large one run may get. Both bounds are needed, and
    a bound nothing reads is decoration. (This used to test that the string `suite.max_files_per_run`
    appeared in vp_compare.py's source, which passed with the check switched off.) The behavioural test
    of `vp_compare.main` over an over-cap run is in `test_comparator_main_wiring`; here: the counter, the
    suite caps, and the sizing arithmetic.
    """
    root = tempfile.mkdtemp(prefix="vp-files-")
    try:
        os.makedirs(os.path.join(root, "web"))
        for i in range(3):
            open(os.path.join(root, "web", "f%d.png" % i), "wb").close()
        ok(vp.count_run_files(root) == 3,
           "per-run cap: the file counter walks the run tree (%d files)" % vp.count_run_files(root))
        suite = vp.get_suite("operator")
        ok(vp_compare.run_files_problem(root, suite) is None,
           "per-run cap: a small run is accepted by run_files_problem")
        for i in range(vp.MAX_FILES_PER_RUN + 5):
            open(os.path.join(root, "web", "x%04d.png" % i), "wb").close()
        got = vp_compare.run_files_problem(root, suite)
        ok(got is not None and "cap of %d" % vp.MAX_FILES_PER_RUN in got,
           "per-run cap: an over-cap run is REFUSED by run_files_problem (%s)" % (got or "")[:60])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    ok(vp.get_suite("operator").max_files_per_run == vp.MAX_FILES_PER_RUN
       and vp.get_suite("marketing").max_files_per_run == vp.MARKETING_MAX_FILES_PER_RUN,
       "per-run cap: each suite carries its own cap (operator %d, marketing %d), so growing one "
       "cannot raise the other's" % (vp.MAX_FILES_PER_RUN, vp.MARKETING_MAX_FILES_PER_RUN))
    n = len(vp.load_json(vp.get_suite("marketing").surfaces_path)["marketing"])
    worst = n * vp.MARKETING_FILES_PER_SURFACE * 2 + vp.MARKETING_REPORT_FILES
    ok(worst <= vp.MARKETING_MAX_FILES_PER_RUN <= 2 * worst,
       "per-run cap: the marketing cap (%d) holds the real worst case (%d surfaces x %d files x 2 engines + %d "
       "report files = %d) and is not absurdly above it" % (
           vp.MARKETING_MAX_FILES_PER_RUN, n, vp.MARKETING_FILES_PER_SURFACE, vp.MARKETING_REPORT_FILES, worst))


def test_reference_store_refuses_to_overflow():
    root = tempfile.mkdtemp(prefix="vp-refs-")
    src = os.path.join(root, "src.png")
    Image.new("RGB", (8, 8), (1, 2, 3)).save(src)
    try:
        store = vp.ReferenceStore(root=os.path.join(root, "store"))
        for i in range(vp.MAX_REFERENCE_ENTRIES):
            store.ingest("frame-%03d" % i, src, "1:%d" % i)
        at_cap = len(store.entries())
        ok(at_cap == vp.MAX_REFERENCE_ENTRIES,
           "reference store: filled to the cap (%d entries)" % at_cap)
        refused = False
        try:
            store.ingest("one-too-many", src, "1:999")
        except vp.StoreFull:
            refused = True
        ok(refused, "reference store: the entry OVER the cap is refused (StoreFull)")
        ok(
            len(store.entries()) == at_cap,
            "reference store: the refusal left the store unchanged at %d entries — it refuses, "
            "it never silently evicts a committed reference" % at_cap,
        )
        # Positive control: replacing an EXISTING entry at the cap still works,
        # otherwise "refused" would be indistinguishable from a store that has
        # stopped accepting anything at all.
        replaced = True
        try:
            store.ingest("frame-000", src, "1:0")
        except vp.StoreFull:
            replaced = False
        ok(replaced, "reference store: replacing an existing entry at the cap still succeeds")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. Contrast maths + threshold selection
# ---------------------------------------------------------------------------


def test_contrast_matches_the_rust_oracle():
    # These four are pinned in selahcue-present/tests/test_tokens.rs. Two
    # implementations of contrast that disagree by a shade are a bug generator,
    # so the harness is held to the same numbers as the crate.
    cases = [
        ((255, 255, 255), (110, 92, 240), 4.72, "white on --sc-primary #6e5cf0"),
        ((255, 255, 255), (126, 110, 255), 3.78, "white on --sc-primary-hover #7e6eff (AA-large only)"),
        ((107, 115, 131), (20, 22, 29), 3.79, "--sc-text-muted on --sc-surface"),
        ((167, 174, 190), (20, 22, 29), 8.12, "--sc-text-secondary on --sc-surface"),
    ]
    for fg, bg, want, name in cases:
        got = vp.contrast_ratio(fg, bg)
        ok(abs(got - want) < 0.01, "contrast: %s = %.2f:1 (pinned %.2f)" % (name, got, want))


def test_threshold_selection():
    ok(vp.required_ratio("text", 14, 600)[0] == vp.AA_TEXT,
       "threshold: 14px/600 demands AA-normal 4.5 (below the 18.66px-bold large floor)")
    ok(vp.required_ratio("text", 24, 400)[0] == vp.AA_LARGE,
       "threshold: 24px/400 is large text -> 3.0")
    ok(vp.required_ratio("text", 19, 700)[0] == vp.AA_LARGE,
       "threshold: 19px/700 is large text -> 3.0")
    ok(vp.required_ratio("text", 18, 700)[0] == vp.AA_TEXT,
       "threshold: 18px/700 is NOT large (floor is 18.66px) -> 4.5")
    ok(vp.required_ratio("ui")[0] == vp.AA_LARGE,
       "threshold: a non-text UI component uses 3.0")


def test_gradient_is_measured_at_its_worst_stop():
    """A gradient must be checked at EVERY stop, not at one sampled colour."""
    region = {
        "color": "rgb(255, 255, 255)",
        "fontSize": "14px",
        "fontWeight": "600",
        "kind": "text",
        "chain": [
            {"opacity": 1, "background": "rgba(0, 0, 0, 0)",
             "backgroundImage": "linear-gradient(90deg, rgb(62, 211, 154), rgb(40, 165, 121))"},
            {"opacity": 1, "background": "rgb(11, 13, 18)", "backgroundImage": ""},
        ],
    }
    got = vp.dom_region_contrast(region)
    ok(got is not None and abs(got["ratio"] - 1.91) < 0.02,
       "gradient: white on the GO LIVE green measures its WORST stop, %.2f:1 (light stop 1.91, "
       "dark stop 3.11) — sampling one stop is how the failing end hides"
       % (got["ratio"] if got else -1))
    ok(got and got["candidates"] >= 2, "gradient: both stops were evaluated (%s candidates)"
       % (got["candidates"] if got else 0))


def test_known_composition_traps():
    """Three SHIPPED cases with independently-measured answers, used as fixtures.

    A checker that cannot reproduce these is not ready, whatever it reports
    elsewhere. Each is invisible to a foreground-token-vs-background-token
    comparison, which is the shape of most automated colour audits.
    """
    # 1. TRANSLUCENT FILL OVER NON-FLAT GROUND. `button.golive .key` is white on
    #    rgba(255,255,255,.18) sitting on the GO LIVE gradient. app.css:3899 says
    #    "white for AA on the fill" — a real check that compared #fff against the
    #    green and never saw the 18%-white chip in between. The comment then
    #    vouches for the wrong answer, which is worse than no check at all.
    key = {"color": "rgb(255, 255, 255)", "fontSize": "12px", "fontWeight": "700", "kind": "text",
           "chain": [
               {"opacity": 1, "background": "rgba(255, 255, 255, 0.18)", "backgroundImage": ""},
               {"opacity": 1, "background": "rgba(0, 0, 0, 0)",
                "backgroundImage": "linear-gradient(90deg, rgb(62, 211, 154), rgb(40, 165, 121))"},
               {"opacity": 1, "background": "rgb(11, 13, 18)", "backgroundImage": ""}]}
    got = vp.dom_region_contrast(key)
    ok(got and abs(got["ratio"] - 1.72) < 0.02,
       "composition trap 1: a translucent chip over a gradient composites to %.2f:1 (known 1.72). "
       "Comparing #fff to the green endpoint gives ~1.91 and comparing it to the chip gives 1.0 — "
       "neither is what a human sees" % (got["ratio"] if got else -1))
    ok(got and got["candidates"] >= 2,
       "composition trap 1: the translucent layer was composited over BOTH gradient stops "
       "(%s candidates), not collapsed to one" % (got["candidates"] if got else 0))

    # 2. SMALL TEXT ON A TOKEN FILL. `.pm-slide-live-badge` is white on --sc-live at
    #    9px/700 — the ratio clears AA-large, and AA-large does not apply.
    badge = {"color": "rgb(255, 255, 255)", "fontSize": "9px", "fontWeight": "700", "kind": "text",
             "chain": [{"opacity": 1, "background": "rgb(255, 77, 77)", "backgroundImage": ""},
                       {"opacity": 1, "background": "rgb(20, 22, 29)", "backgroundImage": ""}]}
    got = vp.dom_region_contrast(badge)
    ok(got and abs(got["ratio"] - 3.27) < 0.02 and got["required"] == vp.AA_TEXT,
       "composition trap 2: white on --sc-live at 9px/700 is %.2f:1 and is judged against %.1f "
       "(AA-normal) — 9px is not large text, so the 3.0 threshold must NOT rescue it"
       % (got["ratio"] if got else -1, got["required"] if got else -1))

    # 3. A HOVER FILL. Not capturable by the CLI driver, so it is pinned here.
    hover = {"color": "rgb(255, 255, 255)", "fontSize": "13px", "fontWeight": "600", "kind": "text",
             "chain": [{"opacity": 1, "background": "rgb(126, 110, 255)", "backgroundImage": ""},
                       {"opacity": 1, "background": "rgb(20, 22, 29)", "backgroundImage": ""}]}
    got = vp.dom_region_contrast(hover)
    ok(got and abs(got["ratio"] - 3.78) < 0.02,
       "composition trap 3: white on --sc-primary-hover is %.2f:1 (known 3.78)"
       % (got["ratio"] if got else -1))


def test_inherited_opacity_is_composited():
    """The opacity that matters lives on an ANCESTOR, not on the control."""
    base = [
        {"opacity": 1, "background": "rgba(0,0,0,0)", "backgroundImage": ""},
        {"opacity": 1, "background": "rgb(20, 22, 29)", "backgroundImage": ""},
    ]
    dimmed = [dict(base[0]), dict(base[1], opacity=0.5)]
    region = {"color": "rgb(107, 115, 131)", "fontSize": "12px", "fontWeight": "500", "kind": "text"}
    full = vp.dom_region_contrast(dict(region, chain=base))
    half = vp.dom_region_contrast(dict(region, chain=dimmed))
    ok(
        half and full and half["ratio"] < full["ratio"] - 1.0,
        "composited opacity: an ANCESTOR's opacity .5 drops the ratio %.2f -> %.2f. Reading "
        "opacity on the control alone reports 1 both times, which is how the whole-card "
        "dimming defect stayed invisible" % (full["ratio"] if full else -1, half["ratio"] if half else -1),
    )
    ok(half and abs(half["opacity"] - 0.5) < 1e-6,
       "composited opacity: the effective opacity is the PRODUCT down the chain (%.3f)"
       % (half["opacity"] if half else -1))


# ---------------------------------------------------------------------------
# 5. The deviation gate can go RED
# ---------------------------------------------------------------------------


def _region_record(color, chain=None, text="GO LIVE", px="14px", weight="600", kind="text", opacity=1.0):
    chain = chain or [
        {"opacity": opacity, "background": "rgba(0,0,0,0)",
         "backgroundImage": "linear-gradient(90deg, rgb(62, 211, 154), rgb(40, 165, 121))"},
        {"opacity": 1, "background": "rgb(11, 13, 18)", "backgroundImage": ""},
    ]
    region = {"id": "x", "selector": "#x", "kind": kind, "rect": [0, 0, 100, 40], "painted": True,
              "display": "flex", "color": color, "fontSize": px, "fontWeight": weight,
              "text": text, "chain": chain}
    rec = {
        "id": "x", "selector": "#x", "kind": kind, "painted": True, "text": text,
        "font_px": px, "font_weight": weight,
        "effective_opacity": vp.effective_opacity(chain),
    }
    dom = vp.dom_region_contrast(region)
    if dom:
        rec["dom"] = dom
    return rec


def test_deviation_gate_can_fail():
    """In-harness proof that an allowed-deviation entry is a GATE, not a comment.

    Feeds the gate the FIGMA value the entry exists to reject, and requires a
    FAIL. If this passes as INTENTIONAL, every entry in deviations.json is
    decoration and the whole file authorises drift.
    """
    deviations = vp.load_json(vp.DEVIATIONS_PATH)
    entry = next(d for d in deviations["deviations"] if d["id"] == "golive-primary-ink")

    # NB: the gate is keyed {capture: {engine: {region: record}}} — it checks EVERY
    # engine, so a WebKit-only regression cannot hide behind a green Blink row.
    shipped = {"console": {"blink": {"golive-button": _region_record("rgb(6, 35, 26)")}}}
    rows = vp_compare.gate_deviations({"deviations": [entry]}, shipped)
    ok(rows and rows[0]["status"] == "INTENTIONAL",
       "deviation gate: the SHIPPED dark ink is accepted as INTENTIONAL (%.2f:1) — the benign "
       "case still exercises the gate" % rows[0].get("value", -1))

    reverted = {"console": {"blink": {"golive-button": _region_record("rgb(255, 255, 255)")}}}
    rows = vp_compare.gate_deviations({"deviations": [entry]}, reverted)
    ok(rows and rows[0]["status"] == "FAIL",
       "deviation gate: reverting to the FIGMA white ink turns the entry RED (%.2f:1 < 4.5) — "
       "the entry can fail, so it is a gate" % rows[0].get("value", -1))

    # The opacity metric, same two directions.
    opacity_entry = next(d for d in deviations["deviations"]
                         if d["id"] == "closed-card-dimming-scoped-to-thumbnail")
    plain_chain = [{"opacity": 1, "background": "rgba(0,0,0,0)", "backgroundImage": ""},
                   {"opacity": 1, "background": "rgb(20,22,29)", "backgroundImage": ""}]
    dim_chain = [{"opacity": 1, "background": "rgba(0,0,0,0)", "backgroundImage": ""},
                 {"opacity": 0.5, "background": "rgb(20,22,29)", "backgroundImage": ""}]
    good = {"screens-closed": {"blink": {r: _region_record("rgb(167,174,190)", chain=plain_chain, text="No output window")
                                        for r in opacity_entry["regions"]}}}
    bad = {"screens-closed": {"blink": {r: _region_record("rgb(167,174,190)", chain=dim_chain, text="No output window")
                                       for r in opacity_entry["regions"]}}}
    rows_good = vp_compare.gate_deviations({"deviations": [opacity_entry]}, good)
    rows_bad = vp_compare.gate_deviations({"deviations": [opacity_entry]}, bad)
    ok(all(r["status"] == "INTENTIONAL" for r in rows_good),
       "deviation gate: undimmed controls on a closed card are accepted")
    ok(all(r["status"] == "FAIL" for r in rows_bad),
       "deviation gate: restoring whole-CARD opacity .5 turns every control entry RED "
       "(measured %.3f) — the composited walk is what makes this possible"
       % rows_bad[0].get("value", -1))

    # The wording metric, same two directions.
    text_entry = next(d for d in deviations["deviations"] if d["id"] == "closed-built-in-reads-CLOSED")
    closed = {"screens-closed": {"blink": {"closed-card-pill": _region_record("rgb(167,174,190)", text="● CLOSED")}}}
    muted = {"screens-closed": {"blink": {"closed-card-pill": _region_record("rgb(167,174,190)", text="● MUTED")}}}
    ok(vp_compare.gate_deviations({"deviations": [text_entry]}, closed)[0]["status"] == "INTENTIONAL",
       "deviation gate: a built-in screen reading CLOSED is accepted")
    ok(vp_compare.gate_deviations({"deviations": [text_entry]}, muted)[0]["status"] == "FAIL",
       "deviation gate: reverting the pill to MUTED turns the entry RED")

    # A missing region must FAIL, not quietly pass. A selector that no longer
    # matches is exactly how a deviation entry rots into a no-op.
    rows = vp_compare.gate_deviations({"deviations": [entry]}, {"console": {"blink": {}}})
    ok(rows and rows[0]["status"] == "FAIL",
       "deviation gate: a region whose selector no longer matches FAILS rather than passing "
       "vacuously")

    # Per-engine coverage: a regression present in ONE engine must produce a FAIL row
    # for that engine while the other stays INTENTIONAL — not one collapsed verdict.
    mixed = {"console": {"blink": {"golive-button": _region_record("rgb(6, 35, 26)")},
                         "webkit": {"golive-button": _region_record("rgb(255, 255, 255)")}}}
    rows = vp_compare.gate_deviations({"deviations": [entry]}, mixed)
    by_engine = {r["engine"]: r["status"] for r in rows}
    ok(by_engine.get("blink") == "INTENTIONAL" and by_engine.get("webkit") == "FAIL",
       "deviation gate: a WebKit-only regression is reported per engine (blink=%s, webkit=%s) — "
       "collapsing the engines would hide the one that actually ships"
       % (by_engine.get("blink"), by_engine.get("webkit")))


# ---------------------------------------------------------------------------
# 6. The committed reference store is intact
# ---------------------------------------------------------------------------


def test_committed_references():
    store = vp.ReferenceStore()
    good, problems = store.verify()
    ok(good, "reference store: committed references verify (checksums, sizes, no orphans)%s"
       % ("" if good else " — " + "; ".join(problems[:3])))
    ok(len(store.entries()) > 0, "reference store: it is not empty (a comparison needs a reference)")

# ---------------------------------------------------------------------------
# 7. The marketing suite
# ---------------------------------------------------------------------------


def _png(path, size=(8, 8), colour=(1, 2, 3)):
    Image.new("RGB", size, colour).save(path)


def test_marketing_suite_has_its_own_bounded_store():
    marketing = vp.get_suite("marketing")
    operator = vp.get_suite("operator")
    ok(marketing.reference_dir != operator.reference_dir
       and marketing.max_entries != operator.max_entries,
       "suites: marketing has its own reference store and caps (%d entries) apart from the "
       "operator's (%d), so 35 frames cannot be squeezed into a store sized for 13"
       % (marketing.max_entries, operator.max_entries))
    root = tempfile.mkdtemp(prefix="vp-mkt-")
    src = os.path.join(root, "src.png")
    _png(src)
    try:
        store = vp.ReferenceStore(root=os.path.join(root, "store"), max_entries=3, max_bytes=10 ** 7)
        for i in range(3):
            store.ingest("frame-%d" % i, src, "1:%d" % i)
        refused = False
        try:
            store.ingest("one-too-many", src, "1:99")
        except vp.StoreFull:
            refused = True
        ok(refused, "suite store: the entry over a suite's OWN cap (3) is refused")
        ok(len(store.entries()) == 3, "suite store: the refusal left the store at its cap, nothing evicted")
        small = vp.ReferenceStore(root=os.path.join(root, "small"), max_entries=10,
                                  max_bytes=os.path.getsize(src) - 1)
        raised = False
        try:
            small.ingest("big", src, "1:1")
        except vp.StoreFull:
            raised = True
        ok(raised, "suite store: a byte cap smaller than the PNG refuses it (the byte bound bites on its own)")
        ok(len(vp.ReferenceStore().entries()) == len(vp.get_suite("operator").store().entries()),
           "suite store: ReferenceStore() with no arguments is still the operator store")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    ok(vp.MARKETING_MAX_REFERENCE_ENTRIES - len(vp.get_suite("marketing").store().entries())
       >= vp.MARKETING_ENTRY_HEADROOM or len(vp.get_suite("marketing").store().entries()) == 0,
       "suite store: the marketing cap leaves its pinned headroom over the committed references")


def test_style_dump_registration_is_validated_and_bounded():
    root = tempfile.mkdtemp(prefix="vp-style-")
    src = os.path.join(root, "src.png")
    _png(src)
    try:
        store = vp.ReferenceStore(root=os.path.join(root, "ref"), max_entries=5, max_bytes=10 ** 6,
                                  style_dir=os.path.join(root, "style"), require_style=True)
        store.ingest("page", src, "5:1")
        os.makedirs(store.style_dir)

        def write(obj, name="page"):
            with open(store.style_path_for(name), "w") as fh:
                json.dump(obj, fh)

        good = {"node": "5:1", "texts": [{"t": "x", "x": 0, "y": 0, "w": 1, "h": 1}], "boxes": [],
                "counts": {"capped": False}}
        ok(not store.verify()[0], "style store: a reference with NO style dump fails verify when styles are required")
        write(good)
        meta = store.register_style("page")
        ok(meta["texts"] == 1 and store.verify()[0], "style store: a valid dump registers and verify passes")

        for label, bad in (
            ("a dump for a DIFFERENT node", dict(good, node="9:9")),
            ("a dump the extractor capped", dict(good, counts={"capped": True})),
            ("an extractor error", {"error": "node not found"}),
            ("a dump with no texts list", {"node": "5:1", "boxes": []}),
        ):
            write(bad)
            raised = False
            try:
                store.register_style("page")
            except ValueError:
                raised = True
            ok(raised, "style store: %s is refused, not silently registered" % label)

        write(good)
        store.register_style("page")
        with open(store.style_path_for("page"), "a") as fh:
            fh.write(" ")
        good_after, problems = store.verify()
        ok(not good_after and any("sha256" in p for p in problems),
           "style store: a style file edited after registration is caught by its checksum")
        write(good)
        store.register_style("page")
        write(good, name="stray")
        problems = store.verify()[1]
        ok(any("orphan style" in p for p in problems),
           "style store: a style dump with no manifest entry is reported as an orphan (unbounded growth by another name)")
        os.remove(store.style_path_for("stray"))

        tiny = vp.ReferenceStore(root=os.path.join(root, "ref2"), max_entries=5, max_bytes=os.path.getsize(src) + 10,
                                 style_dir=os.path.join(root, "style2"))
        tiny.ingest("page", src, "5:1")
        os.makedirs(tiny.style_dir)
        with open(tiny.style_path_for("page"), "w") as fh:
            json.dump(good, fh)
        raised = False
        try:
            tiny.register_style("page")
        except vp.StoreFull:
            raised = True
        ok(raised, "style store: a dump that would push the store over its byte cap is refused (it counts like a PNG)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_top_crop_alignment_reports_height_not_a_phantom_diff():
    a = synthetic_frame(0)
    taller = Image.new("RGB", (a.width, a.height + 120), (11, 13, 23))
    taller.paste(a, (0, 0))
    ref_c, act_c, delta, wdelta = vp_compare.align_top_crop(a, taller)
    ok(delta == 120 and wdelta == 0 and ref_c.size == act_c.size == a.size,
       "top-crop: a build 120px taller than the frame is cropped to the shared %s and reports +%d" % (a.size, delta))
    same, _v, _g = vp.block_ssim(ref_c, act_c)
    ok(same > 0.999, "top-crop: identical shared content scores %.4f — extra page height does not lower it" % same)
    stretched = taller.resize(a.size, Image.LANCZOS)
    stretch_score, _v, _g = vp.block_ssim(a, stretched)
    ok(stretch_score < same - 0.02,
       "top-crop: stretching the taller page to fit scores %.4f, worse than cropping — the phantom layout "
       "diff the alignment exists to avoid" % stretch_score)
    wrong_ref, wrong_act, _d, _w = vp_compare.align_top_crop(synthetic_frame(37), taller)
    wrong, _v, _g = vp.block_ssim(wrong_ref, wrong_act)
    ok(wrong < 0.9, "top-crop: a genuinely different top still scores badly (%.4f)" % wrong)
    wide = Image.new("RGB", (a.width + 24, a.height + 5000), (11, 13, 23))
    wide.paste(a, (0, 0))
    r2, a2, dh, dw = vp_compare.align_top_crop(a, wide)
    narrow = Image.new("RGB", (a.width - 16, a.height), (11, 13, 23))
    r3, a3, dh3, dw3 = vp_compare.align_top_crop(a, narrow)
    ok(r3.size == narrow.size and a3.size == narrow.size and dw3 == -16 and dh3 == 0,
       "top-crop: a build NARROWER than the frame is compared over the build's width (no padded blank strip): %s %s" % (r3.size, a3.size))
    ok(r2.size == a.size and a2.size == a.size and dw == 24 and dh == 5000,
       "top-crop: a page 24px WIDER (a horizontal overflow) is cropped to the shared width, never stretched, "
       "and both deltas are reported (+%dw +%dh); stretching it cost 1.6 GB and scored higher than the real page" % (dw, dh))


def test_bundle_probe_and_freshness():
    root = tempfile.mkdtemp(prefix="vp-dist-")
    try:
        assets = os.path.join(root, "assets")
        os.makedirs(assets)
        with open(os.path.join(assets, "a.js"), "w") as fh:
            fh.write('const t = "Email address verified"; const u = "This verification link didn\'t work";')
        probe = {"control": "Email address verified", "must_not_contain": ["This verification link has expired"]}
        ok(vp_compare.source_probe_problem(probe, dist=root) is None,
           "bundle probe: a bundle without the forbidden copy passes")
        with open(os.path.join(assets, "b.js"), "w") as fh:
            fh.write('const v = "This verification link has expired";')
        got = vp_compare.source_probe_problem(probe, dist=root)
        ok(got is not None and "no longer a documented non-render" in got,
           "bundle probe: shipping the forbidden copy makes the probe FAIL (%s)" % (got or "")[:60])
        os.remove(os.path.join(assets, "b.js"))
        dead = dict(probe, control="a string that is not in this bundle")
        got = vp_compare.source_probe_problem(dead, dist=root)
        ok(got is not None and "control" in got,
           "bundle probe: a control string that is absent fails — a probe over the wrong directory cannot pass for every state")
        ok(vp_compare.source_probe_problem(dict(probe, control=None), dist=root) is not None,
           "bundle probe: a probe with no control string is refused")
        ok(vp_compare.source_probe_problem(probe, dist=os.path.join(root, "missing")) is not None,
           "bundle probe: a missing bundle is a failure, not a pass")

        # freshness
        marketing = os.path.join(root, "m")
        os.makedirs(os.path.join(marketing, "src"))
        os.makedirs(os.path.join(marketing, "dist"))
        index = os.path.join(marketing, "dist", "index.html")
        srcfile = os.path.join(marketing, "src", "App.vue")
        open(index, "w").write("<html></html>")
        open(srcfile, "w").write("<template/>")
        now = time.time()
        os.utime(srcfile, (now - 100, now - 100))
        os.utime(index, (now, now))
        ok(vcm.dist_problem(dist=os.path.join(marketing, "dist"), marketing_root=marketing) is None,
           "dist freshness: a bundle newer than its sources is accepted")
        os.utime(srcfile, (now + 100, now + 100))
        got = vcm.dist_problem(dist=os.path.join(marketing, "dist"), marketing_root=marketing)
        ok(got is not None and "OLDER" in got,
           "dist freshness: a bundle OLDER than its sources is refused — last build's screenshot would score as a result")
        ok(vcm.dist_problem(dist=os.path.join(marketing, "none"), marketing_root=marketing) is not None,
           "dist freshness: no bundle at all is refused")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _bc(slug, text="", h=13407, engine="blink"):
    return {slug: {engine: {"doc": {"h": h}, "text": text}}}


def test_marketing_deviation_gate_can_fail():
    gate = vp_compare.gate_marketing_deviations
    height = {"id": "legal-full-drafts", "capture": "privacy", "metric": "doc_height", "requires": {"min": 5000}}
    rows = gate({"deviations": [height]}, _bc("privacy", "Privacy Policy"))
    ok(rows[0]["status"] == "INTENTIONAL", "marketing gate: a page at the documented height is INTENTIONAL (%s px)" % rows[0]["value"])
    rows = gate({"deviations": [height]}, _bc("privacy", h=1772))
    ok(rows[0]["status"] == "FAIL", "marketing gate: reverting to the Figma placeholder height (1772px) turns it RED")
    absent = {"id": "no-pro-price", "capture": "pricing", "metric": "text_absent", "requires": {"pattern": r"\$19"}}
    ok(gate({"deviations": [absent]}, _bc("pricing", "Free\nChurch\nCustom"))[0]["status"] == "INTENTIONAL",
       "marketing gate: an honest page (no $19) satisfies text_absent")
    ok(gate({"deviations": [absent]}, _bc("pricing", "Pro\n$19 / month"))[0]["status"] == "FAIL",
       "marketing gate: the invented price reappearing turns text_absent RED")
    present = {"id": "resend-cta", "capture": "verify-v3", "metric": "text_present", "requires": {"pattern": "send a new verification link"}}
    ok(gate({"deviations": [present]}, _bc("verify-v3", "Send a new verification link"))[0]["status"] == "INTENTIONAL",
       "marketing gate: text_present is case-insensitive and passes when the copy is there")
    ok(gate({"deviations": [present]}, _bc("verify-v3", ""))[0]["status"] == "FAIL",
       "marketing gate: text_present FAILS when the copy is gone")
    ok(gate({"deviations": [absent]}, {})[0]["status"] == "UNCHECKED",
       "marketing gate: a capture that was not produced is UNCHECKED, never a quiet pass")
    ok(gate({"deviations": [dict(absent, metric="nope")]}, _bc("pricing", "x"))[0]["status"] == "FAIL",
       "marketing gate: an unknown metric fails rather than passing vacuously")
    both = {"pricing": {"blink": {"doc": {"h": 1}, "text": "Free"}, "webkit": {"doc": {"h": 1}, "text": "Pro $19"}}}
    by_engine = {r["engine"]: r["status"] for r in gate({"deviations": [absent]}, both)}
    ok(by_engine == {"blink": "INTENTIONAL", "webkit": "FAIL"},
       "marketing gate: with --engine both a WebKit-only regression is its own FAIL row (blink=%s, webkit=%s); "
       "the gate used to read only the first engine's page" % (by_engine.get("blink"), by_engine.get("webkit")))


def test_dom_contrast_survey():
    muted = {"text": "Muted line", "color": "rgb(107, 115, 131)", "fs": "14px", "fw": "400", "bgl": ["rgb(20, 22, 29)"], "y": 5}
    white = dict(muted, text="White line", color="rgb(255, 255, 255)")
    big = dict(muted, text="Big muted", fs="28px")
    gradient = dict(muted, text="On a gradient", bgg=True)
    got = vp_compare.survey_dom_contrast({"items": [muted, white, big, gradient]})
    ok(got["failing_total"] == 1 and got["failing"][0]["text"] == "Muted line"
       and abs(got["failing"][0]["ratio"] - 3.79) < 0.02,
       "dom contrast: --sc-text-muted on --sc-surface at 14px reads %.2f:1 and FAILS AA-normal (pinned 3.79)"
       % (got["failing"][0]["ratio"] if got["failing"] else -1))
    ok(got["checked"] == 3 and got["unknown"] == 1,
       "dom contrast: white passes, 28px muted is judged against the LARGE threshold and passes (3:1), "
       "and a gradient backdrop is reported unknown (%d checked, %d unknown) — never given an invented number"
       % (got["checked"], got["unknown"]))


def _figma(texts, boxes=None):
    return {"node": "1:1", "texts": texts, "boxes": boxes or []}


def _ft(t, x=100, y=100, fs=16, fw=400, c="#eef1f6", ta="LEFT", w=300, h=20, lh=None):
    return {"t": t, "x": x, "y": y, "w": w, "h": h, "fs": fs, "fw": fw, "lh": lh, "ls": 0, "c": c, "ta": ta}


def _dt(text, x=100, y=100, fs="16px", fw="400", color="rgb(238, 241, 246)", tw=300, **kw):
    it = {"tag": "p", "x": x, "y": y, "w": tw, "h": 20, "text": text, "fs": fs, "fw": fw, "lh": "normal",
          "color": color, "tx": x, "ty": y, "tw": tw, "th": 20, "bgl": ["rgb(14, 17, 22)"]}
    it.update(kw)
    return it


def _kinds(result):
    return {d["kind"] for r in result["pairs"] for d in r["diffs"]}


def test_style_diff_finds_what_it_claims():
    base = vsd.diff(_figma([_ft("Hello world")]), {"items": [_dt("Hello world")]})
    ok(base["summary"]["paired"] == 1 and not _kinds(base),
       "style diff: an identical text pairs and reports NO differences (the benign case still runs)")
    size = vsd.diff(_figma([_ft("Hello world", fs=26)]), {"items": [_dt("Hello world", fs="24px")]})
    ok("font-size" in _kinds(size), "style diff: 26px vs 24px is reported as font-size")
    weight = vsd.diff(_figma([_ft("Hello world", fw=700)]), {"items": [_dt("Hello world", fw="600")]})
    ok("font-weight" in _kinds(weight), "style diff: weight 700 vs 600 is reported")
    lh = vsd.diff(_figma([_ft("Hello world", lh=22)]), {"items": [_dt("Hello world")] and [dict(_dt("Hello world"), lh="20px")]})
    ok("line-height" in _kinds(lh), "style diff: line-height 22px vs 20px is reported")
    shift = vsd.diff(_figma([_ft("Hello world", x=541)]), {"items": [_dt("Hello world", x=577)]})
    ok("x" in _kinds(shift), "style diff: a 36px horizontal offset is reported")
    centred = vsd.diff(_figma([_ft("Hello world", x=570, w=300, ta="CENTER")]),
                       {"items": [_dt("Hello world", x=540, tw=360, ta="left")]})
    ok("text-align" in _kinds(centred), "style diff: a centred design rendered left-aligned is reported as text-align")

    # colour: the three-way classification is the point
    layer = vsd.diff(_figma([_ft("Hello world", c="#9aa4b2")]), {"items": [_dt("Hello world", color="rgb(167, 174, 190)")]})
    ok(_kinds(layer) == {"colour~"},
       "style diff: #9aa4b2 rendered as the mapped --sc-text-secondary #a7aebe is `colour~` (token layer, class B), "
       "not a defect: got %s" % sorted(_kinds(layer)))
    role = vsd.diff(_figma([_ft("Hello world", c="#9aa4b2")]), {"items": [_dt("Hello world", color="rgb(244, 246, 251)")]})
    ok("colour" in _kinds(role),
       "style diff: a muted label rendered in primary text is `colour` (a role mismatch is NOT excused by the token layer)")
    same = vsd.diff(_figma([_ft("Hello world", c="#eef1f6")]), {"items": [_dt("Hello world", color="rgb(238, 241, 246)")]})
    ok(not _kinds(same), "style diff: the exact Figma colour reports nothing")

    # copy
    only = vsd.diff(_figma([_ft("Welcome back"), _ft("Shared line", y=200)]),
                    {"items": [_dt("Sign in to SelahCue"), _dt("Shared line", y=200)]})
    ok(only["summary"]["figma_only"] == 1 and only["summary"]["build_only"] == 1
       and only["figma_only"][0]["text"] == "Welcome back",
       "style diff: reworded copy is reported on BOTH sides (design-only 'Welcome back', build-only 'Sign in to SelahCue')")
    fuzzy = vsd.diff(_figma([_ft("Download the installer for Windows")]), {"items": [_dt("Download the installer for Windows.")]})
    ok(fuzzy["summary"]["paired"] == 1, "style diff: copy differing by punctuation still pairs")
    upper = vsd.diff(_figma([_ft("FEATURES")]), {"items": [_dt("Features", tt="uppercase")]})
    ok("copy-case" not in _kinds(upper), "style diff: CSS text-transform uppercase of the same words is not a copy difference")
    lower = vsd.diff(_figma([_ft("FEATURES")]), {"items": [_dt("Features")]})
    ok("copy-case" in _kinds(lower), "style diff: a case-only copy difference WITHOUT text-transform is reported")

    # ordered pairing among duplicates, and the containment guard
    dup = vsd.diff(_figma([_ft("Download free", y=20, fs=15), _ft("Download free", y=900, fs=18)]),
                   {"items": [_dt("Download free", y=24, fs="15px"), _dt("Download free", y=950, fs="16px")]})
    sizes = [d["detail"] for r in dup["pairs"] for d in r["diffs"] if d["kind"] == "font-size"]
    ok(dup["summary"]["paired"] == 2 and len(sizes) == 1 and "18" in sizes[0],
       "style diff: duplicates pair in reading order (the nav CTA with the nav CTA, the footer CTA with the footer CTA)")
    long_text = "Sign in to manage your plan, billing and license. You don't need an account to run SelahCue only to manage a paid plan."
    guard = vsd.diff(_figma([_ft(long_text)]), {"items": [_dt("You don't need an account to run SelahCue")]})
    ok(guard["summary"]["paired"] == 0,
       "style diff: a short banner that merely appears inside a long design paragraph is NOT paired with it")


def test_style_diff_review_fixes():
    # radius: effective radii (Cody 7: a circle's `50%` was reported as radius 0)
    box = {"n": "Frame", "ty": "FRAME", "id": "1:2", "x": 100, "y": 100, "w": 44, "h": 44, "f": "#171b22", "r": 999}
    text = dict(_dt("Go", x=110, y=112, tw=20), p=0)

    def radius_kinds(figma_r, dom_radius, w=44, h=44):
        """The text must sit INSIDE the Figma box or no box is matched and every assertion below is vacuous."""
        fb = dict(box, r=figma_r, w=w, h=h)
        card = {"tag": "div", "x": 100, "y": 100, "w": w, "h": h, "cls": "c", "bg": "rgb(20, 22, 29)", "radius": dom_radius}
        res = vsd.diff(_figma([_ft("Go", x=110, y=112, w=20, h=16)], [fb]), {"items": [card, text]})
        assert res["summary"]["paired"] == 1 and res["boxes"] is not None
        return {d["kind"] for b in res["boxes"] for d in b["diffs"]}

    matched = vsd.diff(_figma([_ft("Go", x=110, y=112, w=20, h=16)], [dict(box, r=4)]),
                       {"items": [{"tag": "div", "x": 100, "y": 100, "w": 44, "h": 44, "cls": "c", "bg": "rgb(20, 22, 29)", "radius": "50%"}, text]})
    ok(matched["boxes"], "style diff radius: the harness really matches the Figma box to the DOM box (a pill drawn as r=4 against 50% is reported), "
                         "so the 'not reported' controls below are not vacuous")

    ok("radius" not in radius_kinds(999, "50%"), "style diff radius: Figma's 999 on a 44px circle equals CSS `border-radius: 50%` (was reported as 0)")
    ok("radius" not in radius_kinds(999, "999px"), "style diff radius: Figma 999 equals CSS 999px on a pill (both clamp to half the shorter side)")
    ok("radius" not in radius_kinds(22, "22px", 430, 300), "style diff radius: an ordinary matching radius reports nothing")
    ok("radius" in radius_kinds(22, "16px", 430, 300), "style diff radius: 22 against 16 is still reported (positive control)")
    ok("radius" in radius_kinds(999, "4px"), "style diff radius: a pill drawn but a square built is still reported")

    # apostrophes: curly vs straight is not a case difference (Cody 7)
    curly = vsd.diff(_figma([_ft("Don\u2019t panic here")]), {"items": [_dt("Don't panic here")]})
    ok(not _kinds(curly), "style diff copy: a curly apostrophe against a straight one is NOT a copy or case difference")
    ok("copy-case" in _kinds(vsd.diff(_figma([_ft("Don't panic here")]), {"items": [_dt("don't panic here")]})),
       "style diff copy: a real case difference is still reported (positive control)")

    # text-align condition (Cody 7)
    def align_kinds(ta, w, dom_ta, tw):
        res = vsd.diff(_figma([_ft("Centred line", ta=ta, w=w)]), {"items": [_dt("Centred line", tw=tw, ta=dom_ta)]})
        return _kinds(res)

    ok("text-align" in align_kinds("CENTER", 300, "left", 120), "style diff align: a centred design built left-aligned is reported")
    ok("text-align" not in align_kinds("LEFT", 120, "center", 118), "style diff align: a LEFT text box that merely hugs its ink is not a difference")
    ok("text-align" in align_kinds("LEFT", 400, "center", 118), "style diff align: a LEFT box far wider than its ink built centred is reported")
    ok("text-align" not in align_kinds("LEFT", 300, "left", 120), "style diff align: matching left alignment reports nothing")

    # pair_texts contract (Cody 7): three lists, pairs are 3-tuples
    pairs, f_only, d_only = vsd.pair_texts([_ft("Hello world")], [_dt("Hello world")])
    ok(len(pairs) == 1 and len(pairs[0]) == 3 and f_only == [] and d_only == [],
       "style diff pairing: pair_texts returns (pairs, figma_only, build_only) and each pair is a 3-tuple, as its docstring says")

    # the fuzzy prefilter can never discard a pair that would have reached the threshold (Vera N4)
    import_difflib = vsd.difflib
    rng = random.Random(11)
    words = "the church service scripture output screen live stage download version install account sign in".split()
    wrongly_skipped = skipped = 0
    for _ in range(3000):
        a_txt = " ".join(rng.choice(words) for _ in range(rng.randint(2, 9)))
        b_txt = a_txt if rng.random() < 0.3 else " ".join(rng.choice(words) for _ in range(rng.randint(2, 9)))
        if rng.random() < 0.4 and len(a_txt) > 6:
            i = rng.randint(0, len(a_txt) - 2)
            b_txt = a_txt[:i] + a_txt[i + 1:]
        reach = vsd.may_reach(vsd.collections.Counter(a_txt), len(a_txt), vsd.collections.Counter(b_txt), len(b_txt), vsd.FUZZY)
        ratio = import_difflib.SequenceMatcher(None, a_txt, b_txt).ratio()
        if not reach:
            skipped += 1
            if ratio >= vsd.FUZZY:
                wrongly_skipped += 1
    ok(wrongly_skipped == 0 and skipped > 200,
       "fuzzy prefilter: over 3000 random pairs it skipped %d and wrongly skipped %d that would have reached the threshold "
       "(it must be 0; and it must actually skip, or it is not a prefilter)" % (skipped, wrongly_skipped))
    ok(not vsd.may_reach(vsd.collections.Counter("abcdef"), 6, vsd.collections.Counter("uvwxyz"), 6, 0.8)
       and vsd.may_reach(vsd.collections.Counter("hello world"), 11, vsd.collections.Counter("hello world"), 11, 0.8),
       "fuzzy prefilter: disjoint text is skipped and identical text is kept")


def test_reingest_keeps_style_registration():
    root = tempfile.mkdtemp(prefix="vp-reingest-")
    src = os.path.join(root, "s.png")
    Image.new("RGB", (8, 8), (1, 2, 3)).save(src)
    try:
        store = vp.ReferenceStore(root=os.path.join(root, "ref"), max_entries=5, max_bytes=10 ** 7,
                                  style_dir=os.path.join(root, "style"), require_style=True)
        store.ingest("page", src, "5:1")
        os.makedirs(store.style_dir)
        with open(store.style_path_for("page"), "w") as fh:
            json.dump({"node": "5:1", "texts": [{"t": "x", "x": 0, "y": 0, "w": 1, "h": 1}], "boxes": [], "counts": {"capped": False}}, fh)
        store.register_style("page")
        store.ingest("page", src, "5:1")
        ok(store.entries()["page"].get("style") and store.verify()[0],
           "re-ingest: re-exporting a frame keeps its style registration, and the store still verifies")
        store.ingest("page", src, "5:99")
        ok(not store.entries()["page"].get("style") and not store.verify()[0],
           "re-ingest: a re-export under a DIFFERENT node drops the style (it described another node) and verify says so")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_orchestrator_rejects_operator_only_flags_for_marketing():
    import_vp = __import__("visual_parity")
    old = sys.argv
    out = io.StringIO()
    try:
        results = []
        for flag in ("--skip-web", "--skip-native"):
            sys.argv = ["visual_parity.py", "--suite", "marketing", flag]
            with contextlib.redirect_stdout(out):
                results.append(import_vp.main())
    finally:
        sys.argv = old
    ok(results == [2, 2] and "operator suite only" in out.getvalue(),
       "orchestrator: --skip-web and --skip-native are REJECTED for the marketing suite (exit 2), not silently ignored")


def test_style_diff_boxes():
    figma = _figma([_ft("Card title", x=140, y=140)],
                   [{"n": "Frame", "ty": "FRAME", "id": "1:2", "x": 100, "y": 100, "w": 430, "h": 300,
                     "f": "#171b22", "s": "#2b323d", "sw": 1, "r": 22}])
    card = {"tag": "div", "x": 100, "y": 100, "w": 430, "h": 300, "cls": "card", "bg": "rgb(20, 22, 29)",
            "border": "1px solid rgb(38, 42, 52)", "radius": "22px"}
    text = dict(_dt("Card title", x=140, y=140), p=0)
    ok(vsd.diff(figma, {"items": [card, text]})["boxes"] == [] or
       all(d["kind"].endswith("~") for b in vsd.diff(figma, {"items": [card, text]})["boxes"] for d in b["diffs"]),
       "box diff: a card matching radius, size and the mapped token fill/border reports only token-layer notes")
    wrong = dict(card, radius="16px", w=400, bg="rgb(28, 31, 40)")
    kinds = {d["kind"] for b in vsd.diff(figma, {"items": [wrong, text]})["boxes"] for d in b["diffs"]}
    ok({"radius", "width", "fill"} <= kinds,
       "box diff: radius 22 vs 16, width 430 vs 400 and a different fill are all reported (%s)" % sorted(kinds))
    ok(vsd.diff(figma, {"items": [text]})["boxes"][0]["diffs"][0]["kind"] == "no-box",
       "box diff: a build that paints no box around the card's text reports `no-box`")


def test_marketing_catalogue_is_usable():
    cat = vp.load_json(vp.get_suite("marketing").surfaces_path)["marketing"]
    ok(vcm.catalogue_problems(cat) == [], "catalogue: every marketing surface names a defined scenario, action, status and node id")
    broken = [dict(cat[0], scenario="no-such-scenario"), dict(cat[1], node="nope"), dict(cat[1]),
              dict(cat[2], action="no-such-action"), dict(cat[3], status="not-rendered")]
    problems = vcm.catalogue_problems(broken)
    ok(len(problems) >= 5,
       "catalogue: a corrupted copy is rejected (%d problems: unknown scenario, bad node, duplicate slug, unknown action, "
       "not-rendered without a probe)" % len(problems))
    ok(len(cat) == 35 and sum(1 for e in cat if e["kind"] == "page") == 16 and sum(1 for e in cat if e["kind"] == "state") == 19,
       "catalogue: 16 pages and 19 states, the whole of the Figma scope (%d surfaces)" % len(cat))
    sizes = vp.get_suite("marketing").store().entries()
    ok(all(sizes[e["slug"]]["node_id"] == e["node"] and (sizes[e["slug"]]["width"], sizes[e["slug"]]["height"]) == (1440, e["height"])
           for e in cat if e["slug"] in sizes) and len(sizes) == len(cat),
       "catalogue: every surface's committed reference is the catalogued node at the catalogued size")


def test_capture_server_is_confined():
    root = tempfile.mkdtemp(prefix="vp-srv-")
    try:
        dist = os.path.join(root, "dist")
        os.makedirs(os.path.join(dist, "assets"))
        open(os.path.join(dist, "index.html"), "w").write("<html>SPA</html>")
        open(os.path.join(dist, "assets", "a.js"), "w").write("var a=1")
        open(os.path.join(root, "secret.txt"), "w").write("do not serve me")
        server, base = vcm.start_server(dist)
        try:
            def get(path):
                try:
                    with urllib.request.urlopen(base + path, timeout=5) as r:
                        return r.status, r.read().decode()
                except urllib.error.HTTPError as e:
                    return e.code, ""

            ok(get("/pricing") == (200, "<html>SPA</html>"), "capture server: an extensionless route falls back to index.html (the app uses history routing)")
            ok(get("/assets/a.js") == (200, "var a=1"), "capture server: a real asset is served as itself")
            ok(get("/assets/missing.js")[0] == 404, "capture server: a missing asset is a 404, not HTML posing as a script")
            code, body = get("/..%2Fsecret.txt")
            ok("do not serve me" not in body, "capture server: a path-traversal request cannot read outside dist/")
        finally:
            server.shutdown()
            server.server_close()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_committed_marketing_references():
    store = vp.get_suite("marketing").store()
    good, problems = store.verify()
    ok(good, "marketing store: committed references and style dumps verify (checksums, sizes, no orphans)%s"
       % ("" if good else " — " + "; ".join(problems[:3])))
    ok(len(store.entries()) == 35, "marketing store: all 35 Figma frames are committed (%d)" % len(store.entries()))


# ---------------------------------------------------------------------------
# 8. Every new cap bites (Vera B1: a cap with no test that fails when it is removed is decoration)
# ---------------------------------------------------------------------------


def _rand_frame(w, h, seed):
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), (10, 12, 20))
    d = ImageDraw.Draw(img)
    for _ in range(60):
        x0, y0 = rng.randint(0, w - 2), rng.randint(0, h - 2)
        d.rectangle([x0, y0, rng.randint(x0, w), rng.randint(y0, h)],
                    fill=(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)))
    return img


def test_banded_similarity_equals_the_whole_image_result():
    a, b = _rand_frame(701, 1301, 1), _rand_frame(701, 1301, 2)
    m_band, v_band, g_band = vp.block_ssim(a, b)
    m_whole, v_whole, g_whole = vp._block_ssim_whole(a, b)
    ok(g_band == g_whole and len(v_band) == len(v_whole) and abs(m_band - m_whole) < 1e-9
       and max(abs(x - y) for x, y in zip(v_band, v_whole)) < 1e-9,
       "banded SSIM: %d blocks over 3 bands score %.9f, the same as the whole-image oracle (%.9f), block for block "
       "— the bands exist to cut peak memory, not to change the answer" % (len(v_band), m_band, m_whole))
    ok(vp.diff_image(a, b, v_band, g_band).tobytes() == vp._diff_image_whole(a, b, v_whole, g_whole).tobytes(),
       "banded diff picture: byte-identical to the whole-image oracle")
    flat = Image.new("RGB", (701, 1301), (30, 30, 30))
    ok(abs(vp.block_ssim(flat, flat.copy())[0] - 1.0) < 1e-9, "banded SSIM: identical images still score 1.0")


def test_pixel_statistics_are_pinned():
    """`pixel_delta_stats` and `ink_coverage` print on every pair; replacing either with a constant must go red (Quinn Q-5)."""
    a = Image.new("RGB", (40, 3000), (0, 0, 0))
    ok(vp.pixel_delta_stats(a, a.copy()) == (0.0, 0.0),
       "pixel stats: identical frames are exactly (0, 0)")
    white = Image.new("RGB", (40, 3000), (255, 255, 255))
    mean, frac = vp.pixel_delta_stats(a, white)
    ok(abs(mean - 255.0) < 1e-9 and frac == 1.0,
       "pixel stats: black vs white is mean 255 and 100%% over threshold (got %.3f, %.3f)" % (mean, frac))
    half = a.copy()
    half.paste(Image.new("RGB", (40, 1500), (100, 0, 0)), (0, 0))
    mean, frac = vp.pixel_delta_stats(a, half)
    ok(abs(mean - 50.0) < 1e-9 and abs(frac - 0.5) < 1e-9,
       "pixel stats: half the rows differing by 100 is mean 50 and 50%% over threshold, across 3 bands (got %.3f, %.3f)" % (mean, frac))
    ok(vp.ink_coverage(a)[0] == 0.0, "ink coverage: a flat frame has none")
    inked = a.copy()
    inked.paste(Image.new("RGB", (40, 750), (200, 200, 200)), (0, 0))
    cover, bg = vp.ink_coverage(inked)
    ok(abs(cover - 0.25) < 1e-9 and tuple(bg) == (0, 0, 0),
       "ink coverage: a quarter of the frame inked reads exactly 0.25 over band boundaries (got %.4f)" % cover)


def test_pixel_budget_refuses_before_decoding():
    ok(vp.pixel_budget_problem((1440, 14441)) is None,
       "pixel budget: today's largest capture (Terms, 1440x14441, 20.8 Mpx) is inside the cap")
    got = vp.pixel_budget_problem((3000, 40000), "capture x")
    ok(got is not None and "MAX_CAPTURE_PIXELS" in got and "refusing to decode" in got,
       "pixel budget: a 120 Mpx capture is refused with a clear message, from the header size alone")
    # the comparator wires it in: lower the cap under the committed signin frame and run the real main()
    root = tempfile.mkdtemp(prefix="vp-px-")
    old = vp.MAX_CAPTURE_PIXELS
    try:
        run, surf, dev = _synth_run(root, [{"slug": "signin"}])
        vp.MAX_CAPTURE_PIXELS = 1000
        code, out = _compare(run, surf, dev)
        ok(code == 1 and "MAX_CAPTURE_PIXELS" in out,
           "pixel budget: vp_compare.main FAILS a capture over the cap instead of decoding it (exit %d)" % code)
    finally:
        vp.MAX_CAPTURE_PIXELS = old
        shutil.rmtree(root, ignore_errors=True)


def test_slice_output_cap_is_checked_before_allocation():
    try:
        vp_slice.plan_slice((1440, 900), (1440, 900), 0, 0, 0, 100000, 900, 0.5)
        refused = False
    except vp_slice.SliceTooLarge:
        refused = True
    ok(refused, "slice cap: a 100,000px-wide request is refused by plan_slice from the numbers alone")
    ref_box, build_box, pw, ph = vp_slice.plan_slice((1440, 900), (1440, 900), 0, 0, 0, 1440, 900, 0.5)
    ok(ref_box == (0, 0, 1440, 900) and pw == 720 and ph == 450,
       "slice cap: a normal request is planned (%s, panel %dx%d)" % (ref_box, pw, ph))
    clipped = vp_slice.plan_slice((1440, 900), (1440, 900), 5000, 5000, 5000, 1440, 900, 0.5)[0]
    ok(clipped[2] - clipped[0] == 0 and clipped[3] - clipped[1] == 0,
       "slice cap: a crop box far outside the image is clipped to nothing, so PIL cannot pad a huge blank crop")
    # end to end through main(): the refusal must happen before ANY crop is allocated
    root = tempfile.mkdtemp(prefix="vp-slice-")
    calls = []
    real_crop = Image.Image.crop

    def counting_crop(self, *args, **kw):
        calls.append(args)
        return real_crop(self, *args, **kw)

    try:
        shutil.copyfile(vp.get_suite("marketing").store().path_for("signin"),
                        os.path.join(root, "x.png"))
        os.makedirs(os.path.join(root, "marketing"))
        shutil.copyfile(os.path.join(root, "x.png"), os.path.join(root, "marketing", "signin.blink.png"))
        Image.Image.crop = counting_crop
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vp_slice.main(["--slug", "signin", "--run", root, "--w", "100000", "--out", os.path.join(root, "o.png")])
        ok(code == 2 and not calls and "MAX_OUT_PIXELS" in out.getvalue(),
           "slice cap: main() refuses a huge --w with exit 2 and allocates NO crop (%d crop calls) — it used "
           "to allocate 902 MB first and refuse afterwards" % len(calls))
        with contextlib.redirect_stdout(io.StringIO()):
            code = vp_slice.main(["--slug", "signin", "--run", root, "--out", os.path.join(root, "o.png")])
        ok(code == 0 and len(calls) >= 2 and os.path.exists(os.path.join(root, "o.png")),
           "slice cap: a normal call still crops and writes the image (positive control)")
    finally:
        Image.Image.crop = real_crop
        shutil.rmtree(root, ignore_errors=True)


def test_bundle_probe_counts_only_js_and_fails_at_its_cap():
    root = tempfile.mkdtemp(prefix="vp-probe-")
    try:
        assets = os.path.join(root, "assets")
        os.makedirs(assets)
        for i in range(vp_compare.MAX_PROBE_JS_FILES):  # non-JS assets sorting BEFORE the real chunk
            open(os.path.join(assets, "a%04d.css" % i), "w").close()
        with open(os.path.join(assets, "z.js"), "w") as fh:
            fh.write('const t="Email address verified"; const v="This verification link has expired";')
        probe = {"control": "Email address verified", "must_not_contain": ["This verification link has expired"]}
        got = vp_compare.source_probe_problem(probe, dist=root)
        ok(got is not None and "no longer a documented non-render" in got,
           "probe cap: 400 CSS files ahead of the one JS chunk do not stop the probe reading it — the "
           "forbidden copy is still found (the first version counted every file and PASSED here)")
        for i in range(vp_compare.MAX_PROBE_JS_FILES + 1):
            open(os.path.join(assets, "chunk%04d.js" % i), "w").write("var x=%d" % i)
        got = vp_compare.source_probe_problem(probe, dist=root)
        ok(got is not None and "MAX_PROBE_JS_FILES" in got,
           "probe cap: more than MAX_PROBE_JS_FILES .js files is a FAILURE ('%s...'), not a probe that quietly "
           "stops reading part-way" % (got or "")[:50])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dump_and_call_caps_bite():
    big = {"items": [{"tag": "p", "text": "x"}] * (vcm.MAX_DOM_ITEMS + 5), "focus": [{"tag": "a"}] * (vcm.MAX_FOCUS_ITEMS + 3)}
    got = vcm.enforce_dump_caps(big)
    ok(len(got["items"]) == vcm.MAX_DOM_ITEMS and got.get("truncated") is True,
       "dump cap: a page returning %d items is cut to MAX_DOM_ITEMS=%d and flagged truncated (re-imposed in "
       "Python, so a bug in the page-side cap cannot make an unbounded file)" % (vcm.MAX_DOM_ITEMS + 5, vcm.MAX_DOM_ITEMS))
    ok(len(got["focus"]) == vcm.MAX_FOCUS_ITEMS and got.get("focus_capped") is True,
       "focus cap: the focus list is cut to MAX_FOCUS_ITEMS=%d and flagged" % vcm.MAX_FOCUS_ITEMS)
    small = vcm.enforce_dump_caps({"items": [{"tag": "p"}], "focus": []})
    ok(not small.get("truncated") and not small.get("focus_capped"),
       "dump cap: a small dump is left alone and not flagged (positive control)")

    class Ctx:
        handler = None

        def route(self, _pattern, handler):
            self.handler = handler

    class Req:
        method = "POST"
        post_data_json = {"query": "mutation VerifyEmail($t: String!) { verifyEmail(token: $t) { verified } }"}

    class Route:
        def fulfill(self, **_kw):
            pass

        def abort(self):
            pass

    for scenario in ("signed-out", "verify-loading"):
        ctx, calls, held = Ctx(), [], []
        vcm._bind_api(ctx, scenario, calls, held)
        for _ in range(vcm.MAX_CALLS + 30):
            ctx.handler(Route(), Req())
        ok(len(calls) == vcm.MAX_CALLS and len(held) <= vcm.MAX_CALLS,
           "call cap: %d GraphQL calls under scenario %r record at most MAX_CALLS=%d (calls %d, held %d)" % (
               vcm.MAX_CALLS + 30, scenario, vcm.MAX_CALLS, len(calls), len(held)))


class _FakePage:
    """Just enough of a Playwright page for capture_entry: no browser, no network."""

    def __init__(self, dump, h1s=None, screenshot_raises=None):
        self.dump, self.h1s, self.waits, self.shots = dump, h1s or [], [], 0
        self.screenshot_raises = screenshot_raises

    def on(self, *_a, **_k):
        pass

    def goto(self, *_a, **_k):
        pass

    def evaluate(self, js, arg=None):
        if js == vcm.DOM_DUMP_JS:
            return json.loads(json.dumps(self.dump))
        if "document.fonts" in js:
            return None
        return list(self.h1s)

    def wait_for_selector(self, *_a, **_k):
        pass

    def wait_for_timeout(self, ms):
        self.waits.append(ms)

    def screenshot(self, path=None, **_k):
        if self.screenshot_raises:
            raise self.screenshot_raises
        self.shots += 1
        Image.new("RGB", (8, 8), (1, 2, 3)).save(path)


class _FakeCtx:
    def __init__(self, page):
        self.page, self.closed = page, False

    def route(self, *_a, **_k):
        pass

    def add_init_script(self, *_a, **_k):
        pass

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self, page):
        self.ctx = _FakeCtx(page)

    def new_context(self, **_k):
        return self.ctx


def _dump(inter=True, truncated=False, w=1440, h=900, items=3):
    return {"items": [{"tag": "p", "x": 0, "y": 0, "w": 1, "h": 1, "text": "t%d" % i} for i in range(items)],
            "focus": [], "truncated": truncated,
            "doc": {"w": w, "h": h, "title": "t", "h1": [], "mains": 1, "inter": inter, "overflowX": False}}


def _capture(page, entry_extra=None, **kw):
    entry = {"slug": "signin", "path": "/signin", "width": 1440, "height": 900}
    entry.update(entry_extra or {})
    root = tempfile.mkdtemp(prefix="vp-cap-")
    try:
        browser = _FakeBrowser(page)
        rec, errs = vcm.capture_entry(browser, "http://127.0.0.1:1", entry, root, "blink", **kw)
        return rec, errs, browser.ctx, root
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def test_capture_entry_wiring():
    page = _FakePage(_dump())
    rec, errs, ctx, root = _capture(page, {"settle_ms": 10 ** 6})
    try:
        ok(not errs and rec["png"] and os.path.exists(os.path.join(root, rec["png"])) and ctx.closed,
           "capture wiring: a healthy page captures, writes the screenshot and its DOM dump, and closes its context")
        ok(page.waits == [vcm.MAX_SETTLE_MS],
           "settle cap: a catalogue settle_ms of 1,000,000 waits only MAX_SETTLE_MS=%d (waited %s)" % (vcm.MAX_SETTLE_MS, page.waits))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    rec, errs, _c, root = _capture(_FakePage(_dump(inter=False)))
    shutil.rmtree(root, ignore_errors=True)
    ok(any("Inter did not load" in e for e in errs),
       "Inter gate: a page where Inter did not load FAILS the capture through capture_entry itself, not just the helper")
    rec, errs, _c, root = _capture(_FakePage(_dump(inter=False)), require_inter=False)
    shutil.rmtree(root, ignore_errors=True)
    ok(not any("Inter" in e for e in errs), "Inter gate: --allow-fallback-font lets a fallback capture through (positive control)")
    ok(vcm.inter_problem("x", {"doc": {"inter": True}}) is None and vcm.inter_problem("x", {"doc": {"inter": False}}) is not None
       and vcm.inter_problem("x", {}) is not None and vcm.inter_problem("x", {}, require_inter=False) is None,
       "Inter gate: inter_problem is True/False/missing/overridden as documented")

    rec, errs, _c, root = _capture(_FakePage(_dump(truncated=True)))
    shutil.rmtree(root, ignore_errors=True)
    ok(any("truncated" in e for e in errs), "truncated dump: a dump the page flagged truncated FAILS the capture")
    rec, errs, _c, root = _capture(_FakePage(_dump(items=vcm.MAX_DOM_ITEMS + 10)))
    shutil.rmtree(root, ignore_errors=True)
    ok(any("truncated" in e for e in errs), "truncated dump: an over-cap dump is cut AND fails the capture")

    huge = _FakePage(_dump(w=1440, h=60000))
    rec, errs, _c, root = _capture(huge)
    shutil.rmtree(root, ignore_errors=True)
    ok(huge.shots == 0 and not rec["png"] and any("MAX_CAPTURE_PIXELS" in e for e in errs),
       "pixel cap: a page 1440x60000 (86 Mpx) is refused BEFORE it is photographed (screenshots taken: %d)" % huge.shots)

    interrupter = _FakePage(_dump(), screenshot_raises=KeyboardInterrupt())
    browser = _FakeBrowser(interrupter)
    root = tempfile.mkdtemp(prefix="vp-cap-")
    try:
        try:
            vcm.capture_entry(browser, "http://x", {"slug": "signin", "path": "/signin", "width": 1440, "height": 900},
                              root, "blink")
            raised = False
        except KeyboardInterrupt:
            raised = True
        ok(raised and not browser.ctx.closed,
           "Ctrl-C: KeyboardInterrupt propagates and the context is NOT closed (Playwright's close() after an "
           "interrupt spins at 100%% CPU with the browsers alive; closed=%s)" % browser.ctx.closed)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    probe_page = _FakePage(_dump(), h1s=["We couldn't find that page"])
    rec, errs, _c, root = _capture(probe_page, {"status": "unbuilt", "path": "/account/devices"})
    shutil.rmtree(root, ignore_errors=True)
    ok(not errs and rec["probe"]["confirmed"] is True,
       "unbuilt probe: a route that renders the 404 view is confirmed unbuilt")
    probe_page = _FakePage(_dump(), h1s=["Manage devices"])
    rec, errs, _c, root = _capture(probe_page, {"status": "unbuilt", "path": "/account/devices"})
    shutil.rmtree(root, ignore_errors=True)
    ok(rec["probe"]["confirmed"] is False and any("now renders" in e for e in errs),
       "unbuilt probe: a route that now renders a real page FAILS ('capture it and compare it')")


def test_style_and_figma_node_caps_bite():
    root = tempfile.mkdtemp(prefix="vp-nodes-")
    src = os.path.join(root, "s.png")
    Image.new("RGB", (8, 8), (1, 2, 3)).save(src)
    try:
        store = vp.ReferenceStore(root=os.path.join(root, "ref"), max_entries=5, max_bytes=10 ** 9,
                                  style_dir=os.path.join(root, "style"))
        store.ingest("page", src, "5:1")
        os.makedirs(store.style_dir)

        def dump(n):
            return {"node": "5:1", "texts": [{"t": "x", "x": 0, "y": 0, "w": 1, "h": 1}] * n, "boxes": [],
                    "counts": {"capped": False}}

        with open(store.style_path_for("page"), "w") as fh:
            json.dump(dump(vp.MAX_STYLE_NODES + 1), fh)
        try:
            store.register_style("page")
            refused = False
        except ValueError as exc:
            refused = "MAX_STYLE_NODES" in str(exc)
        ok(refused, "style cap: a dump of MAX_STYLE_NODES+1 (%d) nodes is refused" % (vp.MAX_STYLE_NODES + 1))
        with open(store.style_path_for("page"), "w") as fh:
            json.dump(dump(vp.MAX_STYLE_NODES), fh)
        ok(store.register_style("page")["texts"] == vp.MAX_STYLE_NODES,
           "style cap: exactly MAX_STYLE_NODES (%d) is accepted (positive control)" % vp.MAX_STYLE_NODES)

        over = os.path.join(root, "over.json")
        with open(over, "w") as fh:
            json.dump({"items": [{"tag": "p", "text": "x"}] * (vsd.MAX_NODES + 1)}, fh)
        try:
            vsd.load_dom(over)
            refused = False
        except SystemExit as exc:
            refused = "MAX_NODES" in str(exc)
        ok(refused, "style diff cap: a DOM dump of MAX_NODES+1 (%d) items is refused" % (vsd.MAX_NODES + 1))
        with open(over, "w") as fh:
            json.dump({"node": "1:1", "texts": [{"t": "x", "x": 0, "y": 0, "w": 1, "h": 1}] * (vsd.MAX_NODES + 1), "boxes": []}, fh)
        try:
            vsd.load_figma("x", over)
            refused = False
        except SystemExit as exc:
            refused = "MAX_NODES" in str(exc)
        ok(refused, "style diff cap: a Figma style dump of MAX_NODES+1 nodes is refused")
        with open(over, "w") as fh:
            json.dump({"items": [{"tag": "p", "text": "x"}] * vsd.MAX_NODES}, fh)
        ok(len(vsd.load_dom(over)["items"]) == vsd.MAX_NODES, "style diff cap: exactly MAX_NODES is accepted (positive control)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_artifact_links_only_exact_ticket_urls():
    good = bfa.linked(cfa.CLICKUP_TASK_URL + "86abc1234", "86abc1234", "T")
    ok(good == '<a href="%s86abc1234">T</a>' % cfa.CLICKUP_TASK_URL,
       "artifact links: a ticket's exact ClickUp URL becomes an anchor")
    for label, url in (("a javascript: URL", "javascript:alert(1)"), ("another ticket's URL", cfa.CLICKUP_TASK_URL + "86other999"),
                       ("a lookalike host", "https://app.clickup.com.evil.example/t/86abc1234"), ("no URL", None)):
        out = bfa.linked(url, "86abc1234", "T")
        ok("<a" not in out and "href" not in out and out == "T",
           "artifact links: %s renders as plain text, never an href (HTML-escaping does not stop javascript: URLs)" % label)


def test_artifact_builder_caps_refuse_before_writing():
    root = tempfile.mkdtemp(prefix="vp-art-")
    saved = (bfa.MAX_IMAGES, bfa.MAX_TOTAL_BYTES, bfa.encode_image)
    try:
        run = os.path.join(root, "run")
        os.makedirs(os.path.join(run, "marketing"))
        cat = vp.load_json(vp.get_suite("marketing").surfaces_path)["marketing"]
        for e in cat:
            if e.get("status") != "unbuilt":
                open(os.path.join(run, "marketing", "%s.blink.png" % e["slug"]), "wb").close()
        meta = {"ticket": "17tnw2b2c75", "origin_main": "3fb96da8", "date": "2026-10-03"}
        bfa.encode_image = lambda src: b"j" * 100
        out = os.path.join(root, "out-images")
        bfa.MAX_IMAGES = 3
        try:
            bfa.build(run, out, meta)
            refused = False
        except SystemExit as exc:
            refused = "MAX_IMAGES" in str(exc)
        ok(refused and not os.path.exists(out),
           "artifact cap: more images than MAX_IMAGES is refused BEFORE encoding and nothing is written")
        bfa.MAX_IMAGES = saved[0]
        bfa.MAX_TOTAL_BYTES = 1000
        encoded_calls = []

        def counting_encode(src):
            encoded_calls.append(src)
            return b"j" * 600

        bfa.encode_image = counting_encode
        out2 = os.path.join(root, "out-bytes")
        try:
            bfa.build(run, out2, meta)
            refused = False
        except SystemExit as exc:
            refused = "MAX_TOTAL_BYTES" in str(exc)
        ok(refused and not os.path.exists(out2),
           "artifact cap: images over MAX_TOTAL_BYTES are refused and NOTHING is written (it used to write first, check after)")
        ok(len(encoded_calls) <= 2,
           "artifact cap: the byte cap stops ENCODING at the image that crosses it (%d of the planned images encoded), "
           "not after all of them" % len(encoded_calls))
        # images alone fit, but images + the page do not: only the final page-size check can catch this
        bfa.encode_image = lambda src: b"j" * 100
        n_images = len([e for e in cat if e.get("status") != "unbuilt"]) + len(cat)
        bfa.MAX_TOTAL_BYTES = n_images * 100 + 1000
        out4 = os.path.join(root, "out-page")
        try:
            bfa.build(run, out4, meta)
            refused = False
        except SystemExit as exc:
            refused = "artifact would be" in str(exc)
        ok(refused and not os.path.exists(out4),
           "artifact cap: images that fit but a page that tips the total over MAX_TOTAL_BYTES is refused with nothing written")
        bfa.encode_image = lambda src: b"j" * 100
        bfa.MAX_TOTAL_BYTES = saved[1]
        out3 = os.path.join(root, "out-ok")
        files, total = bfa.build(run, out3, meta)
        ok(os.path.exists(os.path.join(out3, "index.html")) and len(files) == len(os.listdir(os.path.join(out3, "img")))
           and len(files) <= saved[0],
           "artifact cap: within both caps the build writes the page and %d images (positive control)" % len(files))
    finally:
        bfa.MAX_IMAGES, bfa.MAX_TOTAL_BYTES, bfa.encode_image = saved
        shutil.rmtree(root, ignore_errors=True)


def _synth_run(root, caps, pad_files=0, deviations=None, dist_forbidden=None):
    """A minimal marketing run + a matching synthetic catalogue, built from the COMMITTED references.

    Lets `vp_compare.main` be driven end to end with no browser. Returns (run, surfaces_path, deviations_path).
    Each cap: slug, status (captured/unbuilt/not-rendered), engine, dom (dict | "missing" | "garbage" | None
    for the default healthy dump), probe, source_probe.
    """
    suite = vp.get_suite("marketing")
    real = {e["slug"]: e for e in vp.load_json(suite.surfaces_path)["marketing"]}
    run = os.path.join(root, "run-synth")
    d = os.path.join(run, "marketing")
    os.makedirs(d)
    records, entries = [], {}
    for c in caps:
        slug, status, engine = c["slug"], c.get("status", "captured"), c.get("engine", "blink")
        entry = dict(real[slug])
        entry["status"] = status
        if c.get("source_probe"):
            entry["source_probe"] = c["source_probe"]
        entries[slug] = entry
        rec = {"slug": slug, "kind": entry["kind"], "area": entry["area"], "state": "x/none", "status": status,
               "node": entry["node"], "reference": slug, "reference_kind": "screen",
               "expected_size": [1440, entry["height"]], "scale": 1, "engine": engine, "engine_detail": "stub",
               "driver": {"ok": True, "errors": [], "regions": []}, "errors": [], "ok": True, "calls": [],
               "png": None, "dom": None, "doc": None, "probe": c.get("probe")}
        if status != "unbuilt":
            png = "%s.%s.png" % (slug, engine)
            shutil.copyfile(suite.store().path_for(slug), os.path.join(d, png))
            rec["png"], rec["actual_size"] = png, [1440, entry["height"]]
            dom = c.get("dom")
            doc = {"w": 1440, "h": entry["height"], "inter": True}
            rec["doc"] = doc
            rec["dom"] = "%s.%s.dom.json" % (slug, engine)
            if dom != "missing":
                path = os.path.join(d, rec["dom"])
                if dom == "garbage":
                    open(path, "w").write("{not json")
                else:
                    body = dom or {"items": [{"tag": "p", "x": 0, "y": 0, "w": 10, "h": 10, "text": "hello"}],
                                   "doc": doc, "truncated": False}
                    with open(path, "w") as fh:
                        json.dump(body, fh)
        records.append(rec)
    vp.dump_json(os.path.join(d, "captures.json"), {"suite": "marketing", "captures": records})
    for i in range(pad_files):
        open(os.path.join(d, "pad%04d.txt" % i), "w").close()
    surf = os.path.join(root, "surfaces.json")
    vp.dump_json(surf, {"marketing": list(entries.values())})
    dev = os.path.join(root, "deviations.json")
    vp.dump_json(dev, {"deviations": deviations or []})
    return run, surf, dev


def _compare(run, surfaces, deviations, *extra, dist=None):
    argv = ["vp_compare.py", "--run", run, "--suite", "marketing", "--surfaces", surfaces,
            "--deviations", deviations] + list(extra)
    old_argv, old_env = sys.argv, os.environ.get("SELAHCUE_MARKETING_DIST")
    buf = io.StringIO()
    try:
        sys.argv = argv
        if dist:
            os.environ["SELAHCUE_MARKETING_DIST"] = dist
        with contextlib.redirect_stdout(buf):
            code = vp_compare.main()
    finally:
        sys.argv = old_argv
        if old_env is None:
            os.environ.pop("SELAHCUE_MARKETING_DIST", None)
        else:
            os.environ["SELAHCUE_MARKETING_DIST"] = old_env
    return code, buf.getvalue()


def _synth_dist(root, forbidden=False):
    assets = os.path.join(root, "dist", "assets")
    os.makedirs(assets)
    with open(os.path.join(assets, "a.js"), "w") as fh:
        fh.write('const a="Email address verified";' + ('const b="This verification link has expired";' if forbidden else ""))
    return os.path.join(root, "dist")


def test_comparator_main_wiring():
    """Drive the REAL vp_compare.main over synthetic runs: each wiring path must turn the run red when broken."""
    absent = {"id": "no-google", "capture": "signin", "metric": "text_absent", "requires": {"pattern": "Continue with Google"}}
    mk = lambda: tempfile.mkdtemp(prefix="vp-main-")  # noqa: E731
    cases = []

    root = mk()
    cases.append(root)
    run, surf, dev = _synth_run(root, [{"slug": "signin"}])
    code, out = _compare(run, surf, dev)
    ok(code == 0, "main wiring: a healthy synthetic run exits 0 (positive control; exit %d)" % code)

    root = mk()
    cases.append(root)
    run, surf, dev = _synth_run(root, [{"slug": "signin"}], pad_files=vp.MARKETING_MAX_FILES_PER_RUN)
    code, out = _compare(run, surf, dev)
    ok(code == 1 and "cap of %d" % vp.MARKETING_MAX_FILES_PER_RUN in out,
       "per-run cap: the real comparator FAILS a run with %d files (exit %d) — the old test only looked for the "
       "word in the source and passed with the check switched off" % (vp.MARKETING_MAX_FILES_PER_RUN + 4, code))
    root = mk()
    cases.append(root)
    run, surf, dev = _synth_run(root, [{"slug": "signin"}], pad_files=vp.MARKETING_MAX_FILES_PER_RUN - 8)
    code, out = _compare(run, surf, dev)
    ok(code == 0, "per-run cap: a run just under the cap passes (positive control; exit %d)" % code)
    root = mk()
    cases.append(root)
    # captures.json + the screenshot + its DOM dump + the diff picture compare writes = 4 files besides the pad,
    # so pad = cap - 6 leaves the run at cap - 2: under the cap by itself, over it once the 3 reports are counted.
    run, surf, dev = _synth_run(root, [{"slug": "signin"}], pad_files=vp.MARKETING_MAX_FILES_PER_RUN - 6)
    code, out = _compare(run, surf, dev)
    ok(code == 1,
       "per-run cap: the 3 report files still to be written are COUNTED (the run is at cap-2 on disk and over the "
       "cap with them: exit %d); ignoring them lets a run through that then writes past its cap" % code)

    for label, kw, expect in (
        ("a missing DOM dump", {"dom": "missing"}, "missing"),
        ("an unreadable DOM dump", {"dom": "garbage"}, "unreadable"),
        ("a truncated DOM dump", {"dom": {"items": [{"tag": "p", "text": "x"}], "truncated": True,
                                        "doc": {"w": 1440, "h": 900}}}, "TRUNCATED"),
    ):
        root = mk()
        cases.append(root)
        run, surf, dev = _synth_run(root, [dict(slug="signin", **kw)], deviations=[absent])
        code, out = _compare(run, surf, dev)
        ok(code == 1 and expect in out,
           "fail closed: %s turns the run RED (exit %d); the deviation gate cannot be switched off by deleting a file" % (label, code))

    root = mk()
    cases.append(root)
    dirty = {"items": [{"tag": "button", "x": 0, "y": 0, "w": 1, "h": 1, "text": "Continue with Google"}],
             "doc": {"w": 1440, "h": 900}, "truncated": False}
    run, surf, dev = _synth_run(root, [{"slug": "signin", "dom": dirty}], deviations=[absent])
    code, out = _compare(run, surf, dev)
    ok(code == 1 and "FAIL" in out, "deviation gate via main: the forbidden copy on the page turns the run RED (exit %d)" % code)

    root = mk()
    cases.append(root)
    run, surf, dev = _synth_run(root, [{"slug": "signin"}], deviations=[dict(absent, id="x2", capture="pricing")])
    code, out = _compare(run, surf, dev)
    ok(code == 1 and "was not checked" in out,
       "unchecked entry: a deviation whose capture was not produced FAILS a full run (exit %d)" % code)
    code2, _o = _compare(run, surf, dev, "--allow-missing")
    ok(code2 == 0, "unchecked entry: ... and is tolerated only under --allow-missing (exit %d)" % code2)

    root = mk()
    cases.append(root)
    both_bad = {"items": [{"tag": "button", "x": 0, "y": 0, "w": 1, "h": 1, "text": "Continue with Google"}],
                "doc": {"w": 1440, "h": 900}, "truncated": False}
    run, surf, dev = _synth_run(root, [{"slug": "signin"}, {"slug": "signin", "engine": "webkit", "dom": both_bad}],
                                deviations=[absent])
    code, out = _compare(run, surf, dev)
    ok(code == 1 and "webkit" in out,
       "engine-aware gate: a regression in the WebKit capture alone fails the run (exit %d); the gate used to keep only the first engine" % code)

    for confirmed, want in ((False, 1), (True, 0)):
        root = mk()
        cases.append(root)
        probe = {"path": "/account/devices", "h1": ["We couldn't find that page" if confirmed else "Manage devices"],
                 "expected_h1": "We couldn't find that page", "confirmed": confirmed}
        run, surf, dev = _synth_run(root, [{"slug": "devices-d1", "status": "unbuilt", "probe": probe}])
        code, out = _compare(run, surf, dev)
        ok(code == want,
           "unbuilt probe wiring: confirmed=%s exits %d (want %d); forcing the probe to 'confirmed' in main() turns "
           "the False case green and fails this" % (confirmed, code, want))

    sp = {"scope": "dist", "control": "Email address verified", "must_not_contain": ["This verification link has expired"]}
    for forbidden, want in ((True, 1), (False, 0)):
        root = mk()
        cases.append(root)
        dist = _synth_dist(root, forbidden=forbidden)
        run, surf, dev = _synth_run(root, [{"slug": "verify-v4", "status": "not-rendered", "source_probe": sp}])
        code, out = _compare(run, surf, dev, dist=dist)
        ok(code == want and (not forbidden or "no longer a documented non-render" in out),
           "not-rendered probe wiring: forbidden copy in the bundle exits %d (want %d); removing the probe call from "
           "main() turns the forbidden case green and fails this" % (code, want))
    for c in cases:
        shutil.rmtree(c, ignore_errors=True)


def main():
    for fn in (
        test_comparator,
        test_blank_detection,
        test_run_store_is_bounded,
        test_per_run_file_cap_is_enforced,
        test_reference_store_refuses_to_overflow,
        test_contrast_matches_the_rust_oracle,
        test_threshold_selection,
        test_gradient_is_measured_at_its_worst_stop,
        test_known_composition_traps,
        test_inherited_opacity_is_composited,
        test_deviation_gate_can_fail,
        test_committed_references,
        test_marketing_suite_has_its_own_bounded_store,
        test_style_dump_registration_is_validated_and_bounded,
        test_top_crop_alignment_reports_height_not_a_phantom_diff,
        test_bundle_probe_and_freshness,
        test_marketing_deviation_gate_can_fail,
        test_dom_contrast_survey,
        test_style_diff_finds_what_it_claims,
        test_style_diff_review_fixes,
        test_reingest_keeps_style_registration,
        test_orchestrator_rejects_operator_only_flags_for_marketing,
        test_style_diff_boxes,
        test_marketing_catalogue_is_usable,
        test_capture_server_is_confined,
        test_committed_marketing_references,
        test_banded_similarity_equals_the_whole_image_result,
        test_pixel_statistics_are_pinned,
        test_pixel_budget_refuses_before_decoding,
        test_slice_output_cap_is_checked_before_allocation,
        test_bundle_probe_counts_only_js_and_fails_at_its_cap,
        test_dump_and_call_caps_bite,
        test_capture_entry_wiring,
        test_style_and_figma_node_caps_bite,
        test_artifact_links_only_exact_ticket_urls,
        test_artifact_builder_caps_refuse_before_writing,
        test_comparator_main_wiring,
    ):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — a crashing control is a failed control
            ok(False, "%s raised %s: %s" % (fn.__name__, type(exc).__name__, exc))
    fails = [m for good, m in RESULTS if not good]
    print("\n=== visual-parity selftest: %d checks, %d FAIL ===" % (len(RESULTS), len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
