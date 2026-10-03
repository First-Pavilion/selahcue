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

import json
import os
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
    """The per-run file cap must be CHECKED, not merely declared.

    Run eviction caps how many runs survive, not how large one run may get. Both
    bounds are needed, and a bound nothing reads is decoration.
    """
    root = tempfile.mkdtemp(prefix="vp-files-")
    try:
        os.makedirs(os.path.join(root, "web"))
        for i in range(3):
            open(os.path.join(root, "web", "f%d.png" % i), "wb").close()
        ok(vp.count_run_files(root) == 3,
           "per-run cap: the file counter walks the run tree (%d files)" % vp.count_run_files(root))
        for i in range(vp.MAX_FILES_PER_RUN + 5):
            open(os.path.join(root, "web", "x%04d.png" % i), "wb").close()
        ok(vp.count_run_files(root) > vp.MAX_FILES_PER_RUN,
           "per-run cap: an over-cap run is detectable (%d > %d) — vp_compare.py turns this into "
           "a failure" % (vp.count_run_files(root), vp.MAX_FILES_PER_RUN))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    compare_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vp_compare.py")).read()
    ok("suite.max_files_per_run" in compare_src,
       "per-run cap: vp_compare.py actually READS the suite's cap (a declared-but-unchecked bound is "
       "decoration)")
    ok(vp.get_suite("operator").max_files_per_run == vp.MAX_FILES_PER_RUN
       and vp.get_suite("marketing").max_files_per_run == vp.MARKETING_MAX_FILES_PER_RUN,
       "per-run cap: each suite carries its own cap (operator %d, marketing %d), so growing one "
       "cannot raise the other's" % (vp.MAX_FILES_PER_RUN, vp.MARKETING_MAX_FILES_PER_RUN))


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
    ref_c, act_c, delta = vp_compare.align_top_crop(a, taller)
    ok(delta == 120 and ref_c.size == act_c.size == a.size,
       "top-crop: a build 120px taller than the frame is cropped to the shared %s and reports +%d" % (a.size, delta))
    same, _v, _g = vp.block_ssim(ref_c, act_c)
    ok(same > 0.999, "top-crop: identical shared content scores %.4f — extra page height does not lower it" % same)
    stretched = taller.resize(a.size, Image.LANCZOS)
    stretch_score, _v, _g = vp.block_ssim(a, stretched)
    ok(stretch_score < same - 0.02,
       "top-crop: stretching the taller page to fit scores %.4f, worse than cropping — the phantom layout "
       "diff the alignment exists to avoid" % stretch_score)
    wrong_ref, wrong_act, _d = vp_compare.align_top_crop(synthetic_frame(37), taller)
    wrong, _v, _g = vp.block_ssim(wrong_ref, wrong_act)
    ok(wrong < 0.9, "top-crop: a genuinely different top still scores badly (%.4f)" % wrong)
    narrow = Image.new("RGB", (a.width - 10, a.height))
    r2, a2, _d = vp_compare.align_top_crop(a, narrow)
    ok(r2.size == a.size and a2.size == narrow.size,
       "top-crop: a WIDTH mismatch is not cropped (it is a different problem and the caller resizes)")


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


def test_marketing_deviation_gate_can_fail():
    doc = {"h": 13407}
    cap = {"privacy": {"doc": doc, "text": "Privacy Policy\nLast updated"}}
    height = {"id": "legal-full-drafts", "capture": "privacy", "metric": "doc_height", "requires": {"min": 5000}}
    rows = vp_compare.gate_marketing_deviations({"deviations": [height]}, cap)
    ok(rows[0]["status"] == "INTENTIONAL", "marketing gate: a page at the documented height is INTENTIONAL (%s px)" % rows[0]["value"])
    rows = vp_compare.gate_marketing_deviations({"deviations": [height]}, {"privacy": {"doc": {"h": 1772}, "text": ""}})
    ok(rows[0]["status"] == "FAIL", "marketing gate: reverting to the Figma placeholder height (1772px) turns it RED")
    absent = {"id": "no-pro-price", "capture": "pricing", "metric": "text_absent", "requires": {"pattern": r"\$19"}}
    clean = {"pricing": {"doc": doc, "text": "Free\nChurch\nCustom"}}
    dirty = {"pricing": {"doc": doc, "text": "Pro\n$19 / month"}}
    ok(vp_compare.gate_marketing_deviations({"deviations": [absent]}, clean)[0]["status"] == "INTENTIONAL",
       "marketing gate: an honest page (no $19) satisfies text_absent")
    ok(vp_compare.gate_marketing_deviations({"deviations": [absent]}, dirty)[0]["status"] == "FAIL",
       "marketing gate: the invented price reappearing turns text_absent RED")
    present = {"id": "resend-cta", "capture": "verify-v3", "metric": "text_present", "requires": {"pattern": "send a new verification link"}}
    ok(vp_compare.gate_marketing_deviations({"deviations": [present]}, {"verify-v3": {"doc": doc, "text": "Send a new verification link"}})[0]["status"] == "INTENTIONAL",
       "marketing gate: text_present is case-insensitive and passes when the copy is there")
    ok(vp_compare.gate_marketing_deviations({"deviations": [present]}, {"verify-v3": {"doc": doc, "text": ""}})[0]["status"] == "FAIL",
       "marketing gate: text_present FAILS when the copy is gone")
    ok(vp_compare.gate_marketing_deviations({"deviations": [absent]}, {})[0]["status"] == "UNCHECKED",
       "marketing gate: a capture that was not produced is UNCHECKED, never a quiet pass")
    ok(vp_compare.gate_marketing_deviations({"deviations": [dict(absent, metric="nope")]}, clean)[0]["status"] == "FAIL",
       "marketing gate: an unknown metric fails rather than passing vacuously")


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
        test_style_diff_boxes,
        test_marketing_catalogue_is_usable,
        test_capture_server_is_confined,
        test_committed_marketing_references,
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
