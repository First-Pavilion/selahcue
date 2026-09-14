#!/usr/bin/env python3
"""ADR-0026 revision spike, part 2 (Aria).

Part 1 established the real constraint:
  * WebKit cancels an in-flight native keyboard-scroll animation on ANY scrollTop write,
    including a NO-OP write of the value it already holds (3/3).
  * A pure DOM mutation that shifts content and changes scrollHeight (top-spacer growth,
    row churn) does NOT cancel it (0/3), on either engine, anchoring on or off.

So a virtualizer that NEVER writes scrollTop coexists with native keyboard scrolling.
The only reason the component writes scrollTop is to compensate when content above the
viewport changes height. The question this probe answers:

  Q7  Does NATIVE SCROLL ANCHORING actually work -- on WebKit specifically -- i.e. when a
      spacer ABOVE the viewport grows by N px, does the engine adjust scrollTop by ~N on its
      own so the content the user is reading stays put?
      If yes, the compensation is the ENGINE'S job, needs no script write, and the whole
      JS compensation/echo/guard apparatus deletes.
      `'overflowAnchor' in style` is only proof the property PARSES. This tests BEHAVIOUR.

  Q8  Positive control: with overflow-anchor:none (what transcripts.js ships today), the
      same mutation must NOT be compensated -- content must jump by ~N. Without this the
      Q7 result is not a discriminator.

  Q9  Does anchoring still hold DURING a native keyboard-scroll animation (the case the
      redesign needs), not just at rest?
"""
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

FIXTURE = Path(__file__).parent / "fixture.html"
START = 100000
GROW = 200
TRIALS = 3


async def anchoring_at_rest(page, anchor_off):
    """Grow the TOP spacer (entirely above the viewport) by GROW px while sitting still.
    Measure whether the content under the reader stays put."""
    await page.evaluate(f"window.__setAnchor({str(anchor_off).lower()})")
    await page.evaluate(f"window.__setScroll({START})")
    await page.wait_for_timeout(120)
    # Position of a row that is currently visible, before the mutation.
    before = await page.evaluate("""(() => {
        var host = document.getElementById('log');
        var hb = host.getBoundingClientRect();
        var kids = document.getElementById('rows').children;
        for (var i = 0; i < kids.length; i++) {
          var r = kids[i].getBoundingClientRect();
          if (r.bottom > hb.top && r.top < hb.bottom) {
            return {text: kids[i].textContent, top: r.top - hb.top, scrollTop: host.scrollTop};
          }
        }
        return null;
      })()""")
    await page.evaluate(f"window.__op_spacer({GROW})")
    await page.wait_for_timeout(250)  # give the engine its anchoring adjustment
    after = await page.evaluate("""((txt) => {
        var host = document.getElementById('log');
        var hb = host.getBoundingClientRect();
        var kids = document.getElementById('rows').children;
        for (var i = 0; i < kids.length; i++) {
          if (kids[i].textContent === txt) {
            var r = kids[i].getBoundingClientRect();
            return {top: r.top - hb.top, scrollTop: host.scrollTop};
          }
        }
        return null;
      })(%s)""" % json.dumps(before["text"]))
    await page.evaluate(f"window.__op_spacer({-GROW})")
    await page.wait_for_timeout(150)
    drift = round(after["top"] - before["top"]) if after else None
    return {
        "anchor_off": anchor_off,
        "scrollTop_before": before["scrollTop"],
        "scrollTop_after": after["scrollTop"] if after else None,
        "scrollTop_delta": (after["scrollTop"] - before["scrollTop"]) if after else None,
        "reader_row_drift_px": drift,
        # Anchoring worked iff the row the reader was looking at did NOT move, which
        # requires the engine to have moved scrollTop by ~GROW on its own.
        "anchored": (drift is not None and abs(drift) <= 4),
    }


async def anchoring_during_animation(page):
    """Q9: same mutation, but injected mid-flight during a native PageUp animation with
    anchoring ENABLED. Does the animation survive AND the content stay anchored?"""
    await page.evaluate("window.__setAnchor(false)")
    await page.evaluate(f"window.__setScroll({START})")
    await page.wait_for_timeout(80)
    await page.evaluate("window.__focusLog()")
    await page.evaluate("window.__startTrace()")

    async def inject():
        return await page.evaluate(
            "new Promise((res)=>{setTimeout(()=>{"
            "var b=window.__getScroll();window.__op_spacer(%d);"
            "res({t:performance.now(),before:b});},60);})" % GROW)

    _, inj = await asyncio.gather(page.keyboard.press("PageUp"), inject())
    await page.wait_for_timeout(600)
    trace = await page.evaluate("window.__stopTrace()")
    await page.evaluate(f"window.__op_spacer({-GROW})")
    t0 = trace[0][0]
    post = [y for t, y in trace if (t - t0) >= (inj["t"] - t0)]
    return {"moved_after_inject": round(post[-1] - post[0]) if len(post) >= 2 else 0,
            "samples_after": len(post)}


async def run(p, engine):
    browser = await getattr(p, engine).launch(headless=True)
    page = await browser.new_page(viewport={"width": 1000, "height": 900})
    await page.goto(f"file://{FIXTURE}")
    out = {"engine": engine, "rest_anchor_ON": [], "rest_anchor_OFF": []}
    for _ in range(TRIALS):
        out["rest_anchor_ON"].append(await anchoring_at_rest(page, anchor_off=False))
        out["rest_anchor_OFF"].append(await anchoring_at_rest(page, anchor_off=True))
    out["during_animation_anchor_ON"] = await anchoring_during_animation(page)
    await browser.close()
    return out


async def main():
    async with async_playwright() as p:
        res = [await run(p, e) for e in ("chromium", "webkit")]
    Path(Path(__file__).parent / "spike2_results.json").write_text(json.dumps(res, indent=1))
    for r in res:
        print("=" * 70)
        print(r["engine"].upper())
        for label in ("rest_anchor_ON", "rest_anchor_OFF"):
            for t in r[label]:
                print(f"  {label:<17} scrollTop {t['scrollTop_before']} -> {t['scrollTop_after']} "
                      f"(delta {t['scrollTop_delta']:+}) | reader row drifted "
                      f"{t['reader_row_drift_px']:+}px | anchored={t['anchored']}")
        print("  during PageUp animation, anchoring ON:",
              json.dumps(r["during_animation_anchor_ON"]))


asyncio.run(main())
