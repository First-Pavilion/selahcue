#!/usr/bin/env python3
"""ADR-0026 revision spike (Aria).

The coordinator's spike established: a script scrollTop write during WebKit's native
keyboard-scroll animation cancels it, relative or absolute alike (8/8). This probe asks
the questions that decide whether ANY clean redesign exists:

  Q1 (op_noop)   -- does re-writing the SAME value cancel? (is it the write, or the change?)
  Q2 (op_spacer) -- does a pure DOM MUTATION that shifts content (top-spacer growth), with
                    NO scrollTop write at all, cancel the animation?  ** DECISIVE **
                    Every virtualizer does this on every render. If this cancels, then no
                    virtualizer design of any kind can coexist with native keyboard
                    scrolling on WebKit, and interception is mandatory, not a choice.
  Q3 (op_churn)  -- does diff-and-patch row churn with NO net height change cancel?
  Q4 (wheel)     -- does WebKit animate WHEEL scrolling too, or only keys?
  Q5 (probe)     -- is there a usable "animation in flight" signal (scrollend etc.)?
  Q6 (anchor)    -- does any of Q2/Q3 differ with native scroll anchoring ENABLED?

Method mirrors the coordinator's spike so results are comparable: trace scrollTop on a rAF
loop across a real trusted keypress, run an uninjected CONTROL press first to learn how far
the animation would still travel after the injection instant, then inject at ~40% of the
animation's settle time and compare.
"""
import asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

FIXTURE = Path(__file__).parent / "fixture.html"
START = 100000
TRIALS = 3


def settle_ms(trace):
    if not trace:
        return 0.0
    t0 = trace[0][0]
    last = 0.0
    for i in range(1, len(trace)):
        if trace[i][1] != trace[i - 1][1]:
            last = trace[i][0] - t0
    return last


def moved_after(trace, inject_t):
    t0 = trace[0][0]
    post = [y for t, y in trace if (t - t0) >= inject_t]
    return (post[-1] - post[0]) if len(post) >= 2 else 0


async def one_press(page, key, inject_at_ms, op_js):
    await page.evaluate(f"window.__setScroll({START})")
    await page.wait_for_timeout(50)
    await page.evaluate("window.__focusLog()")
    await page.evaluate("window.__startTrace()")

    async def inject():
        if inject_at_ms is None:
            return None
        return await page.evaluate(
            "new Promise((resolve)=>{setTimeout(()=>{"
            "var b=window.__getScroll();var a=" + op_js + ";"
            "resolve({t:performance.now(),before:b,after:a});"
            "}," + str(inject_at_ms) + ");})"
        )

    _, inj = await asyncio.gather(page.keyboard.press(key), inject())
    await page.wait_for_timeout(600)
    trace = await page.evaluate("window.__stopTrace()")
    return trace, inj


async def measure(page, engine, key, label, op_js, anchor_off=True):
    await page.evaluate(f"window.__setAnchor({str(anchor_off).lower()})")
    out = []
    for _ in range(TRIALS):
        ctrl, _ = await one_press(page, key, None, "")
        dur = settle_ms(ctrl)
        if dur < 20:
            out.append({"engine": engine, "key": key, "op": label,
                        "verdict": "NO-ANIMATION", "settle_ms": dur})
            continue
        inj_at = max(10, int(dur * 0.40))
        ctrl_rest = moved_after(ctrl, inj_at)
        trace, inj = await one_press(page, key, inj_at, op_js)
        t0 = trace[0][0]
        inj_t = inj["t"] - t0
        rest = moved_after(trace, inj_t)
        # CANCELLED: the animation stopped dead where the injection left it, while the
        # control was still travelling a meaningful distance at the same instant.
        cancelled = abs(ctrl_rest) > 30 and abs(rest) < max(15, abs(ctrl_rest) * 0.15)
        out.append({
            "engine": engine, "key": key, "op": label, "anchor_off": anchor_off,
            "settle_ms": round(dur, 1), "inject_at_ms": inj_at,
            "control_would_move": round(ctrl_rest), "moved_after_inject": round(rest),
            "verdict": "CANCELLED" if cancelled else "SURVIVED",
        })
    return out


async def wheel_animated(page, engine):
    """Q4: after a single wheel tick, does scrollTop keep moving for many frames
    (engine-driven animation) or settle within a frame or two (discrete)?"""
    await page.evaluate(f"window.__setScroll({START})")
    await page.wait_for_timeout(50)
    await page.mouse.move(450, 400)
    await page.evaluate("window.__startTrace()")
    await page.mouse.wheel(0, -300)
    await page.wait_for_timeout(600)
    trace = await page.evaluate("window.__stopTrace()")
    return {"engine": engine, "wheel_settle_ms": round(settle_ms(trace), 1),
            "frames_traced": len(trace)}


async def run(p, engine):
    browser = await getattr(p, engine).launch(headless=True)
    page = await browser.new_page(viewport={"width": 1000, "height": 900})
    await page.goto(f"file://{FIXTURE}")
    res = {"engine": engine, "features": await page.evaluate("window.__probe()"), "trials": []}
    res["wheel"] = await wheel_animated(page, engine)
    for key in ["PageUp", "Home"]:
        res["trials"] += await measure(page, engine, key, "rel-write", "window.__op_rel(50)")
        res["trials"] += await measure(page, engine, key, "noop-write", "window.__op_noop()")
        res["trials"] += await measure(page, engine, key, "spacer-mutate", "window.__op_spacer(200)")
        res["trials"] += await measure(page, engine, key, "row-churn", "window.__op_churn(20)")
    # Q6: repeat the two DOM-only ops with native scroll anchoring ENABLED.
    for key in ["PageUp"]:
        res["trials"] += await measure(page, engine, key, "spacer-mutate[anchor-ON]",
                                       "window.__op_spacer(200)", anchor_off=False)
        res["trials"] += await measure(page, engine, key, "row-churn[anchor-ON]",
                                       "window.__op_churn(20)", anchor_off=False)
    await browser.close()
    return res


async def main():
    async with async_playwright() as p:
        results = [await run(p, e) for e in ("chromium", "webkit")]
    Path(Path(__file__).parent / "spike1_results.json").write_text(json.dumps(results, indent=1))
    for r in results:
        print("=" * 66)
        print(r["engine"].upper(), "features:", json.dumps(r["features"]))
        print("  wheel:", json.dumps(r["wheel"]))
        agg = {}
        for t in r["trials"]:
            k = (t["key"], t["op"])
            agg.setdefault(k, []).append(t["verdict"])
        for (key, op), vs in agg.items():
            c = sum(1 for v in vs if v == "CANCELLED")
            print(f"  {key:<8} {op:<26} CANCELLED {c}/{len(vs)}   {vs}")


asyncio.run(main())
