#!/usr/bin/env python3
"""Web-surface screenshotter for the visual-parity harness.

Loads the REAL `selahcue-operator/dist/index.html` with the same `window.__TAURI__`
stub `scripts/operator_headless.py` uses — extracted from that file at run time
rather than copied, so the behavioural gate and the screenshotter cannot drift
into stubbing different applications — routes to a surface, applies a NAMED state,
and captures the frame at the Figma frame's native size.

Every screenshot ships with a machine-readable region manifest measured from the
same laid-out page: bounding rects, font size/weight, the ancestor opacity chain
and each ancestor's background. `vp_compare.py` turns those into contrast numbers
and cross-checks them against the pixels.

    python3 scripts/vp_capture_web.py --out DIR [--engine blink|webkit|both] [--only SLUG ...]

TWO ENGINES, LABELLED — NEVER INTERCHANGEABLE
  blink   headless Chrome CLI. Fast, always available, and NOT what ships.
  webkit  Playwright WebKit (WebCore/JavaScriptCore) — the same engine family as
          the WKWebView Tauri uses on macOS. Closer, still not identical: it is
          not WKWebView inside a Tauri window, has no Tauri IPC, and may be a
          different WebKit build than the OS one.

Blink and WebKit are known to disagree on THIS codebase: a class `display` rule
defeating the `hidden` attribute, flex `<select>` collapse, and grid
implicit-auto-row overflow past the footer are recorded defects that reproduce
only in WebKit/WKWebView. Files are named `<slug>.<engine>.png` and every record
carries `engine` + `engine_detail`, so no image can be quoted as evidence about
an engine that did not draw it.

VIEWPORT EXACTNESS — the trap this script defuses
`chrome --headless=new --window-size=W,H --screenshot` writes a WxH PNG but lays
the page out at innerHeight = H - <window chrome> (87px on this box) while the
driver runs, then re-renders at H for the capture. Region rects measured by the
driver would therefore be offset from the pixels they claim to describe — a
silently wrong contrast sample. So the Blink path probes the delta once, runs the
MEASUREMENT pass at H + delta (asserting innerHeight == H), and the SCREENSHOT
pass at H. The WebKit path sets an exact viewport and has no such gap.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402

HEADLESS = os.path.join(vp.REPO, "scripts", "operator_headless.py")
DIST = os.environ.get("SELAHCUE_OPERATOR_DIST") or os.path.join(
    vp.REPO, "implementation", "desktop", "crates", "selahcue-operator", "dist"
)


# ---------------------------------------------------------------------------
# Engine discovery
# ---------------------------------------------------------------------------


def find_chrome():
    """Same resolution order as operator_headless.py (CHROME_BIN, PATH, app bundle)."""
    env = os.environ.get("CHROME_BIN")
    if env and os.path.exists(env):
        return env
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    for path in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ):
        if os.path.exists(path):
            return path
    return None


def chrome_version(chrome):
    try:
        out = subprocess.run([chrome, "--version"], capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - a version probe must never fail a capture
        return "unknown"


def extract_stub():
    """Pull the `STUB = r\"\"\"...\"\"\"` literal out of operator_headless.py.

    Reused, not duplicated: the behavioural gate and the screenshotter must boot
    the SAME fake host, or a screenshot could show a surface the gate never
    exercised. If the literal moves or is renamed this raises rather than
    silently capturing an unbooted app.
    """
    src = open(HEADLESS, "r", encoding="utf-8").read()
    m = re.search(r'^STUB = r"""(.*?)"""$', src, re.S | re.M)
    if not m:
        raise SystemExit(
            "vp_capture_web: could not find the `STUB = r\"\"\"...\"\"\"` block in "
            + HEADLESS
            + " — the screenshotter reuses that stub on purpose; fix the extraction rather "
            "than pasting a second copy."
        )
    return m.group(1)


# ---------------------------------------------------------------------------
# The capture driver (identical on both engines)
# ---------------------------------------------------------------------------

DRIVER_TEMPLATE = r"""
<div id="__vpdata" style="display:none !important"></div>
<script>
(function(){
  var CFG = __CFG__;
  var out = {slug: CFG.slug, ok:false, steps:[], regions:[], errors:[], viewport:null, done:false};
  function fail(msg){ out.errors.push(String(msg)); }
  function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }

  function click(sel){
    var n = document.querySelector(sel);
    if (!n){ fail("route selector not found: " + sel); return false; }
    n.click();
    out.steps.push("click " + sel);
    return true;
  }

  // Named state handlers. Keep these few and obvious — a screenshot of a state
  // nobody can name is not evidence of anything, and arbitrary JS in the data
  // file would make the catalogue unreviewable.
  var STATES = {
    "default": async function(){},
    "blackout": async function(){
      var b = document.getElementById("blackout");
      if (!b){ fail("blackout: #blackout not found"); return; }
      b.click(); out.steps.push("click #blackout");
      await sleep(150);
    },
    "closed-screen": async function(){
      var row = document.querySelector('.screen-row[data-screen="main"]');
      if (!row){ fail("closed-screen: no .screen-row[data-screen=main]"); return; }
      var cb = row.querySelector(".screen-enable-toggle");
      if (!cb){ fail("closed-screen: no .screen-enable-toggle"); return; }
      if (cb.checked){ cb.click(); out.steps.push("toggle main screen closed"); }
      for (var i=0;i<40;i++){
        await sleep(60);
        var r = document.querySelector('.screen-row[data-screen="main"]');
        if (r && r.classList.contains("screen-disabled")) return;
      }
      fail("closed-screen: card never reached .screen-disabled");
    }
  };

  // The ancestor chain, each entry carrying its OWN opacity and background.
  // Reading opacity on the element alone is a tautology here: the defect this
  // guards against put `opacity: .5` on the CARD, so a control's own computed
  // value read "1" both before and after the fix (see operator_headless.py
  // ~line 1466, which proves the same point behaviourally).
  function chainOf(node){
    var chain = [];
    for (var n = node; n && n.nodeType === 1; n = n.parentElement){
      var cs = getComputedStyle(n);
      var o = parseFloat(cs.opacity);
      chain.push({tag: n.tagName.toLowerCase(),
                  cls: (typeof n.className === "string") ? n.className.slice(0,90) : "",
                  opacity: isNaN(o) ? 1 : o,
                  background: cs.backgroundColor,
                  backgroundImage: cs.backgroundImage === "none" ? "" : cs.backgroundImage.slice(0,240)});
      if (n === document.documentElement) break;
    }
    return chain;
  }

  function measure(region){
    var n = document.querySelector(region.selector);
    if (!n){ fail("region selector not found: " + region.selector + " (" + region.id + ")"); return null; }
    var r = n.getBoundingClientRect();
    var cs = getComputedStyle(n);
    return {
      id: region.id,
      selector: region.selector,
      kind: region.kind || "text",
      rect: [r.left, r.top, r.width, r.height],
      painted: r.width > 0 && r.height > 0 && cs.display !== "none" && cs.visibility !== "hidden",
      display: cs.display,
      color: cs.color,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      text: (n.textContent || "").trim().slice(0, 80),
      chain: chainOf(n)
    };
  }

  async function run(){
    try {
      for (var i=0;i<CFG.route.length;i++){
        if (!click(CFG.route[i])) break;
        await sleep(140);
      }
      var handler = STATES[CFG.state];
      if (!handler){ fail("unknown state handler: " + CFG.state); }
      else { await handler(); }
      await sleep(CFG.settle_ms || 400);
      for (var j=0;j<CFG.regions.length;j++){
        var m = measure(CFG.regions[j]);
        if (m) out.regions.push(m);
      }
      out.viewport = {w: window.innerWidth, h: window.innerHeight,
                      dpr: window.devicePixelRatio,
                      scrollW: document.documentElement.scrollWidth,
                      scrollH: document.documentElement.scrollHeight};
      out.ok = out.errors.length === 0;
    } catch(e){ fail("exception " + e.message); }
    out.done = true;
    window.__vp = out;
    document.getElementById("__vpdata").textContent = "VPDATA" + JSON.stringify(out) + "VPEND";
  }

  var tries = 0;
  var iv = setInterval(function(){
    tries++;
    if (window.__calls && window.__calls.length > 0 && document.querySelector(".nav-item")){
      clearInterval(iv); setTimeout(run, 60);
    } else if (tries > 300){
      clearInterval(iv);
      fail("app never booted");
      out.done = true; window.__vp = out;
      document.getElementById("__vpdata").textContent = "VPDATA" + JSON.stringify(out) + "VPEND";
    }
  }, 30);
})();
</script>
"""


def build_page(stub, cfg, path):
    html = open(os.path.join(DIST, "index.html"), "r", encoding="utf-8").read()
    # The <base> MUST precede the `<link rel=stylesheet href="app.css">` — a <base>
    # only rewrites relative URLs that come AFTER it. operator_headless.py records
    # the same trap: get this wrong and app.css never loads, so every captured
    # pixel is of an unstyled page that still "screenshots fine".
    html = html.replace("<head>", '<head><base href="file://' + DIST + '/">', 1)
    body = stub.replace("<script>", "").replace("</script>", "")
    html = html.replace("</head>", "<script>" + body + "</script></head>", 1)
    html = html.replace("</body>", DRIVER_TEMPLATE.replace("__CFG__", json.dumps(cfg)) + "</body>", 1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


def cfg_for(entry):
    return {
        "slug": entry["slug"],
        "state": entry.get("state", "default"),
        "route": entry.get("route", []),
        "regions": entry.get("regions", []),
        "settle_ms": entry.get("settle_ms", 400),
    }


# ---------------------------------------------------------------------------
# Blink (headless Chrome CLI)
# ---------------------------------------------------------------------------

_PROBE_HTML = (
    '<html><body><div id="o" style="display:none"></div>'
    '<script>document.getElementById("o").textContent="VPPROBE"+innerWidth+"x"+innerHeight+"ENDPROBE";'
    "</script></body></html>"
)


def probe_window_chrome(chrome, w=1200, h=800):
    """Measure how many px `--window-size` loses to window chrome (0x87 on macOS)."""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        fh.write(_PROBE_HTML)
        path = fh.name
    try:
        out = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
             "--window-size=%d,%d" % (w, h), "--virtual-time-budget=800", "--dump-dom",
             "file://" + path],
            capture_output=True, text=True, timeout=60,
        ).stdout
    finally:
        os.unlink(path)
    m = re.search(r"VPPROBE(\d+)x(\d+)ENDPROBE", out)
    if not m:
        raise SystemExit("vp_capture_web: could not probe the headless viewport delta")
    return w - int(m.group(1)), h - int(m.group(2))


def _run_chrome(chrome, page, window, scale, budget, screenshot=None):
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--window-size=%d,%d" % window,
        "--force-device-scale-factor=%d" % scale,
        "--virtual-time-budget=%d" % budget,
    ]
    if screenshot:
        cmd.append("--screenshot=" + screenshot)
    cmd += ["--dump-dom", "file://" + page]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180
    ).stdout


def capture_blink(chrome, delta, stub, entry, out_dir, scale=1, budget=9000):
    w, h = entry["width"], entry["height"]
    png = os.path.join(out_dir, "%s.blink%s.png" % (entry["slug"], "" if scale == 1 else "@%dx" % scale))
    errors = []
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        page = fh.name
    build_page(stub, cfg_for(entry), page)
    try:
        # Pass 1 — MEASURE at a window sized so the layout viewport is exactly WxH.
        dom = _run_chrome(chrome, page, (w + delta[0], h + delta[1]), scale, budget)
        m = re.search(r"VPDATA(\{.*?\})VPEND", dom, re.S)
        data = json.loads(m.group(1)) if m else {"ok": False, "errors": ["no VPDATA block"], "regions": []}
        vpt = data.get("viewport") or {}
        if (vpt.get("w"), vpt.get("h")) != (w, h):
            errors.append(
                "measurement viewport was %sx%s, expected %dx%d — region rects would not line "
                "up with the screenshot pixels" % (vpt.get("w"), vpt.get("h"), w, h)
            )
        # Pass 2 — SCREENSHOT at the window size that yields a WxH image.
        _run_chrome(chrome, page, (w, h), scale, budget, screenshot=png)
    except subprocess.TimeoutExpired:
        errors.append("headless Chrome timed out")
        data = {"ok": False, "errors": ["timeout"], "regions": []}
    finally:
        os.unlink(page)
    return png, data, errors


# ---------------------------------------------------------------------------
# WebKit (Playwright)
# ---------------------------------------------------------------------------


def capture_webkit(stub, entry, out_dir, scale=1, timeout_ms=20000):
    from playwright.sync_api import sync_playwright

    w, h = entry["width"], entry["height"]
    png = os.path.join(out_dir, "%s.webkit%s.png" % (entry["slug"], "" if scale == 1 else "@%dx" % scale))
    errors = []
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        page_path = fh.name
    build_page(stub, cfg_for(entry), page_path)
    data = {"ok": False, "errors": [], "regions": []}
    version = "unknown"
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch()
            version = "Playwright WebKit " + browser.version
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale)
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append("pageerror: " + str(e).splitlines()[0]))
            page.goto("file://" + page_path)
            try:
                page.wait_for_function("() => window.__vp && window.__vp.done", timeout=timeout_ms)
            except Exception as exc:  # noqa: BLE001 — any wait failure is a capture failure
                errors.append("driver never finished on WebKit: " + str(exc).splitlines()[0])
            got = page.evaluate("() => window.__vp || null")
            if got:
                data = got
            page.screenshot(path=png)
            browser.close()
    except Exception as exc:  # noqa: BLE001 — surfaced to the caller as a failed capture
        errors.append("WebKit capture failed: " + str(exc).splitlines()[0])
    finally:
        os.unlink(page_path)
    vpt = data.get("viewport") or {}
    if (vpt.get("w"), vpt.get("h")) != (w, h):
        errors.append("WebKit viewport was %sx%s, expected %dx%d" % (vpt.get("w"), vpt.get("h"), w, h))
    return png, data, errors, version


# ---------------------------------------------------------------------------


def record(entry, engine, engine_detail, png, data, errors, scale):
    ok = bool(data.get("ok")) and os.path.exists(png) and not errors
    size = None
    if os.path.exists(png):
        from PIL import Image

        with Image.open(png) as im:
            size = list(im.size)
        if size != [entry["width"] * scale, entry["height"] * scale]:
            errors = errors + [
                "screenshot is %s, expected %dx%d" % (size, entry["width"] * scale, entry["height"] * scale)
            ]
            ok = False
    else:
        errors = errors + ["no screenshot file was produced"]
        ok = False
    return {
        "slug": entry["slug"],
        "state": entry.get("state", "default"),
        "node": entry.get("node", ""),
        "reference": entry.get("reference", ""),
        "reference_kind": entry.get("reference_kind", "screen"),
        "expected_size": [entry["width"], entry["height"]],
        "actual_size": size,
        "scale": scale,
        "png": os.path.basename(png) if os.path.exists(png) else None,
        "engine": engine,
        "engine_detail": engine_detail,
        "driver": data,
        "errors": errors + list(data.get("errors", [])),
        "ok": ok,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="directory to write PNGs + captures.json into")
    ap.add_argument("--engine", default="both", choices=["blink", "webkit", "both"])
    ap.add_argument("--only", nargs="*", default=None, help="capture only these slugs")
    ap.add_argument("--surfaces", default=vp.SURFACES_PATH)
    args = ap.parse_args()

    catalogue = vp.load_json(args.surfaces)
    entries = [e for e in catalogue.get("web", []) if not args.only or e["slug"] in args.only]
    if not entries:
        print("FAIL: no web surfaces matched")
        return 2
    os.makedirs(args.out, exist_ok=True)
    stub = extract_stub()
    require = os.environ.get("SELAHCUE_VISUAL_REQUIRE") == "1"

    engines = []
    chrome = find_chrome()
    if args.engine in ("blink", "both"):
        if chrome:
            engines.append(("blink", chrome_version(chrome)))
        else:
            msg = "no Chrome/Chromium found (set CHROME_BIN or install google-chrome)"
            if require:
                print("FAIL: SELAHCUE_VISUAL_REQUIRE=1 but " + msg)
                return 3
            print("!! BLINK CAPTURE SKIPPED — " + msg)
    webkit_ready = False
    if args.engine in ("webkit", "both"):
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                b = p.webkit.launch()
                engines.append(("webkit", "Playwright WebKit " + b.version))
                b.close()
            webkit_ready = True
        except Exception as exc:  # noqa: BLE001 — a missing engine is a loud skip, not a crash
            msg = "Playwright WebKit unavailable (%s)" % str(exc).splitlines()[0][:110]
            if require:
                print("FAIL: SELAHCUE_VISUAL_REQUIRE=1 but " + msg)
                return 3
            print("!! WEBKIT CAPTURE SKIPPED — " + msg)

    if not engines:
        print("=" * 68)
        print("!! NO WEB ENGINE AVAILABLE — no web screenshots were produced.")
        print("!! Any parity report from this run covers the NATIVE surfaces only.")
        print("=" * 68)
        return 0

    delta = probe_window_chrome(chrome) if any(e[0] == "blink" for e in engines) else (0, 0)
    if any(e[0] == "blink" for e in engines):
        print("blink window-chrome delta: %dx%d px" % delta)

    results = []
    for entry in entries:
        scales = [1] + ([2] if entry.get("regions") else [])
        for engine, detail in engines:
            for scale in scales:
                if engine == "blink":
                    png, data, errs = capture_blink(chrome, delta, stub, entry, args.out, scale=scale)
                else:
                    if not webkit_ready:
                        continue
                    png, data, errs, detail = capture_webkit(stub, entry, args.out, scale=scale)
                res = record(entry, engine, detail, png, data, errs, scale)
                results.append(res)
                print(
                    "%s %-18s %-7s x%d  %-34s %s"
                    % (
                        "ok  " if res["ok"] else "FAIL",
                        res["slug"],
                        engine,
                        scale,
                        res["png"] or "(no png)",
                        "; ".join(res["errors"])[:150],
                    )
                )

    vp.dump_json(
        os.path.join(args.out, "captures.json"),
        {"dist": DIST, "engines": [{"engine": e, "detail": d} for e, d in engines], "captures": results},
    )
    failed = [r for r in results if not r["ok"]]
    print("=== web capture: %d images, %d FAIL ===" % (len(results), len(failed)))
    for e, d in engines:
        print("    engine %-7s %s" % (e, d))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
