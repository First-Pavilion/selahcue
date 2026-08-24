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

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402
import vp_compare  # noqa: E402
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
    ok("MAX_FILES_PER_RUN" in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "vp_compare.py")).read(),
       "per-run cap: vp_compare.py actually READS the cap (a declared-but-unchecked bound is "
       "decoration)")


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
