#!/usr/bin/env python3
"""Screenshotter for the visual-parity harness's `marketing` suite.

Serves the REAL production bundle (`implementation/marketing/dist/`) over a local HTTP
server with SPA fallback, drives it in Playwright (Blink and/or WebKit) at 1440 wide, and
writes one full-page PNG per catalogued surface plus a bounded DOM/style dump the audit
reads values from (type size, weight, line height, colours, boxes, focus order).

    python3 scripts/vp_capture_marketing.py --out DIR [--engine blink|webkit|both] [--only SLUG ...]

The catalogue is `docs/design/visual-parity/marketing/surfaces.json`. Its entries name a
route, a scripted API SCENARIO and an optional NAMED ACTION. There is no JavaScript in the
data file, and every scenario/action a catalogue can name is defined below: a screenshot of
a state nobody can name is not evidence of anything.

HOW THE API IS STUBBED
  `page.route` answers `/graphql/account` by operation name (the same shapes
  `scripts/auth_pages_headless.py` scripts: errors travel on HTTP 200 with
  `extensions.code`). A scenario may also HANG a request forever, which is how the
  "verifying" and "updating password" states are held still long enough to photograph.
  Nothing touches a real API.

NETWORK: the capture needs the internet for exactly one thing, Inter from Google Fonts
  (`implementation/marketing/index.html` loads it from fonts.googleapis.com and fonts.gstatic.com).
  That is the only egress: every other request is the loopback server below or a stubbed API call.
  Offline it fails CLOSED: Inter does not load, so every capture is refused (exit 1) rather than
  photographed in a fallback face.

WHAT MAKES A CAPTURE FAIL (and therefore the run)
  * the bundle is missing or STALE (older than `src/`) — a screenshot of last week's build
    would score as a result and describe nothing that ships;
  * Inter did not load. Figma is drawn in Inter; a fallback face re-wraps text and invents
    layout differences that are not in the code, so a capture on a fallback is refused
    rather than compared (override with --allow-fallback-font for a deliberate look);
  * the page threw, or a scripted action found no element to act on;
  * an `unbuilt` surface's probe route renders something other than the site's 404 view
    (the screen now exists: it must be captured and compared, not catalogued as missing).

BOUNDS
  The server is one daemon thread running `serve_forever` on 127.0.0.1 with one short-lived daemon
  handler thread per connection (`ThreadingMixIn`); it serves files from `dist/` only
  (path-traversal guarded) and keeps no cache. Per surface the DOM dump is capped at MAX_DOM_ITEMS
  (the cap is applied in the page AND re-imposed here by `enforce_dump_caps`, and a truncated dump
  fails the capture), the focus list at MAX_FOCUS_ITEMS, the recorded GraphQL calls at MAX_CALLS and
  the settle wait at MAX_SETTLE_MS; a page larger than vp_core.MAX_CAPTURE_PIXELS is refused before it is
  photographed. The run writes three files per surface per engine (screenshot, diff, DOM dump);
  `vp_compare.py` fails the run if it exceeds the suite's file cap. Ctrl-C exits at once without the
  Playwright teardown, which otherwise spins at 100% CPU with the browsers still alive (Vera, N2).

Exit codes: 0 all captures ok, 1 at least one capture failed, 2 infrastructure (no/stale
dist, no engine), 3 SELAHCUE_VISUAL_REQUIRE=1 and an engine is missing.
"""

from __future__ import annotations

import argparse
import http.server
import json
import mimetypes
import os
import re
import socketserver
import sys
import threading
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402
from PIL import Image  # noqa: E402

try:  # Top level, but optional: the self-test imports this module and must run with no browser installed.
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment guard, reported by main()
    sync_playwright = None

MARKETING_ROOT = os.path.join(vp.REPO, "implementation", "marketing")
DIST = os.environ.get("SELAHCUE_MARKETING_DIST") or os.path.join(MARKETING_ROOT, "dist")

MAX_DOM_ITEMS = 1500
MAX_FOCUS_ITEMS = 80
MAX_CALLS = 50
MAX_SETTLE_MS = 5000

VERIFY_TOKEN = "SC-TESTTOKEN-verify"
RESET_TOKEN = "SC-TESTTOKEN-reset"
INTER_PROBE = "600 16px Inter"

HANG = object()  # a scenario returns this to leave a request unanswered forever
# Scenarios that hold a request in flight FROM PAGE LOAD. `networkidle` can never be reached
# while a request is outstanding, so these wait for `load` instead; waiting for idle here
# would sit out the app's own 15s request timeout and photograph the failure state it ends in
# (the first run of this script did exactly that and drew "We couldn't verify" for V1).
HELD_ON_LOAD = {"verify-loading"}


# ---------------------------------------------------------------------------
# Scripted API scenarios (mirrors of the shapes in auth_pages_headless.py)
# ---------------------------------------------------------------------------


def _err(code):
    return {"errors": [{"message": "scripted", "extensions": {"code": code}}]}


def _viewer():
    return {"data": {"accountViewer": {"surface": "account", "actorId": "user-1", "orgId": "org-1"}}}


SCENARIOS = {
    # Every operation answers UNAUTHENTICATED: a signed-out visitor, the default for
    # every public page (the navbar and any session probe get an honest "no").
    "signed-out": lambda op: _err("UNAUTHENTICATED"),
    "signed-in": lambda op: _viewer() if op == "AccountViewer" else _err("UNAUTHENTICATED"),
    "verify-loading": lambda op: HANG,
    "verify-ok": lambda op: {"data": {"verifyEmail": {"verified": True}}},
    "verify-invalid": lambda op: _err("VALIDATION_FAILED"),
    "verify-resend": lambda op: (
        _err("VALIDATION_FAILED") if op == "VerifyEmail"
        else {"data": {"resendVerificationEmail": {"accepted": True}}}
    ),
    "reset-hang": lambda op: HANG,
    "reset-ok": lambda op: {"data": {"confirmPasswordReset": {"reset": True}}},
    "reset-invalid": lambda op: _err("VALIDATION_FAILED"),
    "reset-error": lambda op: _err("INTERNAL"),
}

SESSION_HINT_KEY = "selahcue.session"


# ---------------------------------------------------------------------------
# Named actions (each one returns an error string, or None when it worked)
# ---------------------------------------------------------------------------


def _fill(page, selector, value):
    loc = page.locator(selector).first
    if loc.count() == 0:
        return "no element matches %s" % selector
    loc.fill(value)
    return None


def _click(page, selector):
    loc = page.locator(selector).first
    if loc.count() == 0:
        return "no element matches %s" % selector
    loc.click()
    return None


def _first_error(*results):
    for r in results:
        if r:
            return r
    return None


def act_none(page):
    return None


def act_verify_resend(page):
    return _first_error(
        _fill(page, '.au-card input[type="email"]', "pastor@yourchurch.org"),
        _click(page, '.au-card form button.ui-button'),
    )


def act_reset_validation(page):
    # Two different values: one too short, one that does not match. R2 draws both errors.
    return _first_error(
        _fill(page, '.au-card input[type="password"] >> nth=0', "abc123"),
        _fill(page, '.au-card input[type="password"] >> nth=1', "different"),
        _click(page, '.au-card form button.ui-button'),
    )


def act_reset_submit(page):
    return _first_error(
        _fill(page, '.au-card input[type="password"] >> nth=0', "correct horse battery staple"),
        _fill(page, '.au-card input[type="password"] >> nth=1', "correct horse battery staple"),
        _click(page, '.au-card form button.ui-button'),
    )


ACTIONS = {
    "none": act_none,
    "verify-resend": act_verify_resend,
    "reset-validation": act_reset_validation,
    "reset-submit": act_reset_submit,
}


# ---------------------------------------------------------------------------
# Static server with SPA fallback (the app uses createWebHistory)
# ---------------------------------------------------------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    root = DIST

    def log_message(self, *_args):  # a capture run must not grow a log
        return

    def _serve(self, head_only=False):
        path = urllib.parse.urlparse(self.path).path
        rel = urllib.parse.unquote(path).lstrip("/")
        root = os.path.realpath(self.root)
        target = os.path.realpath(os.path.join(root, rel))
        inside = target == root or target.startswith(root + os.sep)
        if not (inside and os.path.isfile(target)):
            # SPA fallback. Only paths with no file extension fall back; a missing asset
            # must 404 rather than be answered with HTML, or a broken script reference
            # would silently "load" as an index page.
            if os.path.splitext(rel)[1]:
                self.send_error(404)
                return
            target = os.path.join(root, "index.html")
        with open(target, "rb") as fh:
            body = fh.read()
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (stdlib naming)
        self._serve()

    def do_HEAD(self):  # noqa: N802
        self._serve(head_only=True)


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_server(root):
    _Handler.root = root
    server = _Server(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, "http://127.0.0.1:%d" % server.server_address[1]


# ---------------------------------------------------------------------------
# Dist freshness
# ---------------------------------------------------------------------------


def newest_mtime(paths):
    newest = 0.0
    for base in paths:
        if os.path.isfile(base):
            newest = max(newest, os.path.getmtime(base))
            continue
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                newest = max(newest, os.path.getmtime(os.path.join(dirpath, name)))
    return newest


def dist_problem(dist=DIST, marketing_root=MARKETING_ROOT):
    """Return a sentence describing why `dist` cannot be trusted, or None."""
    index = os.path.join(dist, "index.html")
    if not os.path.isfile(index):
        return "no built bundle at %s — run `npm run build` in implementation/marketing" % dist
    sources = [os.path.join(marketing_root, "src"), os.path.join(marketing_root, "index.html"),
               os.path.join(marketing_root, "package.json"), os.path.join(marketing_root, "public")]
    sources = [p for p in sources if os.path.exists(p)]
    if newest_mtime(sources) > os.path.getmtime(index) + 1:
        return (
            "the bundle at %s is OLDER than the sources — a screenshot of last build would score "
            "as a result and describe nothing that ships; run `npm run build`" % dist
        )
    return None


# ---------------------------------------------------------------------------
# Page-side measurement (one evaluate call; bounded)
# ---------------------------------------------------------------------------

DOM_DUMP_JS = r"""
([maxItems, maxFocus]) => {
  const out = {items: [], focus: [], truncated: false};
  const sx = window.scrollX, sy = window.scrollY;
  const r1 = (n) => Math.round(n * 10) / 10;
  // The backdrop a piece of text sits on: every translucent layer up to the first opaque one,
  // nearest first. `grad` marks a gradient/image met on the way, where a single colour is a
  // guess and the contrast survey must say "unknown" rather than invent a number.
  const bgLayers = (el) => {
    const layers = []; let grad = false;
    for (let n = el; n && n.nodeType === 1 && layers.length < 6; n = n.parentElement) {
      const c = getComputedStyle(n);
      if (c.backgroundImage !== 'none') grad = true;
      const col = c.backgroundColor;
      if (col !== 'rgba(0, 0, 0, 0)' && col !== 'transparent') {
        layers.push(col);
        const m = col.match(/rgba?\(([^)]+)\)/);
        const parts = m ? m[1].split(',') : [];
        if ((parts.length > 3 ? parseFloat(parts[3]) : 1) >= 0.99) break;
      }
    }
    return {layers: layers, grad: grad};
  };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  // Index of every dumped element, so each item can name its nearest dumped ancestor (`p`).
  // The style diff uses that chain to find the box a group of texts sits in.
  const index = new Map();
  const nearestDumped = (el) => {
    for (let n = el.parentElement; n; n = n.parentElement) if (index.has(n)) return index.get(n);
    return -1;
  };
  // The ink box of an element's OWN text nodes (not its children's), in page coordinates.
  const textBox = (el) => {
    let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
    const range = document.createRange();
    for (const c of el.childNodes) {
      if (c.nodeType !== 3 || !c.textContent.trim()) continue;
      range.selectNodeContents(c);
      for (const q of range.getClientRects()) {
        if (q.width <= 0 || q.height <= 0) continue;
        l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); b = Math.max(b, q.bottom);
      }
    }
    return l === Infinity ? null : {x: Math.round((l + sx) * 10) / 10, y: Math.round((t + sy) * 10) / 10,
                                    w: Math.round((r - l) * 10) / 10, h: Math.round((b - t) * 10) / 10};
  };
  let el;
  while ((el = walker.nextNode())) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    let own = '';
    for (const c of el.childNodes) if (c.nodeType === 3) own += c.textContent;
    own = own.replace(/\s+/g, ' ').trim();
    const tag = el.tagName.toLowerCase();
    const isControl = ['button', 'input', 'select', 'textarea', 'img', 'svg'].includes(tag);
    const hasFill = cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.backgroundImage !== 'none';
    const hasBorder = parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderBottomWidth) > 0 ||
                      parseFloat(cs.borderLeftWidth) > 0;
    if (!own && !isControl && !hasFill && !hasBorder) continue;
    if (out.items.length >= maxItems) { out.truncated = true; break; }
    const it = {tag: tag, x: Math.round(r.left + sx), y: Math.round(r.top + sy), w: r1(r.width), h: r1(r.height)};
    const parent = nearestDumped(el);
    if (parent >= 0) it.p = parent;
    index.set(el, out.items.length);
    const cls = typeof el.className === 'string' ? el.className.trim().slice(0, 60) : '';
    if (cls) it.cls = cls;
    if (own) {
      const tb = textBox(el);
      if (tb) { it.tx = tb.x; it.ty = tb.y; it.tw = tb.w; it.th = tb.h; }
      if (cs.textTransform !== 'none') it.tt = cs.textTransform;
      it.text = own.slice(0, 140);
      it.fs = cs.fontSize; it.fw = cs.fontWeight; it.lh = cs.lineHeight; it.color = cs.color;
      const bl = bgLayers(el);
      it.bgl = bl.layers; if (bl.grad) it.bgg = true;
      if (cs.letterSpacing !== 'normal') it.ls = cs.letterSpacing;
      if (cs.textAlign !== 'start' && cs.textAlign !== 'left') it.ta = cs.textAlign;
    }
    if (hasFill) { it.bg = cs.backgroundColor; if (cs.backgroundImage !== 'none') it.bgi = cs.backgroundImage.slice(0, 120); }
    if (hasBorder) it.border = cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor;
    if (cs.borderTopLeftRadius !== '0px') it.radius = cs.borderTopLeftRadius;
    if (cs.display === 'flex' || cs.display === 'grid' || cs.display === 'inline-flex') {
      it.disp = cs.display;
      if (cs.gap !== 'normal' && cs.gap !== '0px') it.gap = cs.gap;
    }
    if (cs.paddingTop !== '0px' || cs.paddingLeft !== '0px') it.pad = [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].join(' ');
    if (cs.opacity !== '1') it.opacity = cs.opacity;
    if (tag === 'img') { it.alt = el.getAttribute('alt'); it.src = (el.getAttribute('src') || '').slice(0, 80); }
    if (tag === 'a') it.href = (el.getAttribute('href') || '').slice(0, 80);
    if (el.getAttribute('aria-hidden') === 'true') it.ariaHidden = true;
    out.items.push(it);
    // A placeholder is text a visitor reads, and Figma draws it as a text node. Dump it as one,
    // styled with its own ::placeholder colour, so the comparison can pair it.
    if ((tag === 'input' || tag === 'textarea') && el.getAttribute('placeholder') && out.items.length < maxItems) {
      const pcs = getComputedStyle(el, '::placeholder');
      const padL = parseFloat(cs.paddingLeft) || 0;
      out.items.push({tag: 'placeholder', p: out.items.length - 1, x: Math.round(r.left + sx + padL),
        y: Math.round(r.top + sy), w: r1(r.width - padL), h: r1(r.height),
        tx: Math.round((r.left + sx + padL) * 10) / 10, ty: Math.round((r.top + sy + (r.height - parseFloat(cs.fontSize)) / 2) * 10) / 10,
        tw: 0, th: parseFloat(cs.fontSize),
        text: el.getAttribute('placeholder').slice(0, 140), fs: cs.fontSize, fw: cs.fontWeight, lh: cs.lineHeight,
        color: pcs.color, bgl: bgLayers(el).layers});
    }
  }
  const focusable = document.querySelectorAll(
    'a[href], button, input, select, textarea, summary, [tabindex]');
  for (const f of focusable) {
    if (out.focus.length >= maxFocus) break;
    if (f.disabled || f.getAttribute('tabindex') === '-1') continue;
    const cs = getComputedStyle(f);
    const r = f.getBoundingClientRect();
    if (cs.display === 'none' || cs.visibility === 'hidden' || r.width <= 0 || r.height <= 0) continue;
    const name = (f.getAttribute('aria-label') || f.innerText || f.getAttribute('placeholder') ||
                  f.getAttribute('href') || f.getAttribute('name') || '').replace(/\s+/g, ' ').trim().slice(0, 60);
    out.focus.push({tag: f.tagName.toLowerCase(), name: name, y: Math.round(r.top + sy), x: Math.round(r.left + sx)});
  }
  const de = document.documentElement;
  out.doc = {w: de.scrollWidth, h: de.scrollHeight, title: document.title,
             h1: Array.from(document.querySelectorAll('h1')).map(h => h.innerText.trim().slice(0, 100)),
             mains: document.querySelectorAll('main').length,
             inter: (document.fonts && document.fonts.check) ? document.fonts.check(__INTER__) : null,
             overflowX: de.scrollWidth > de.clientWidth};
  return out;
}
""".replace("__INTER__", json.dumps(INTER_PROBE))


# ---------------------------------------------------------------------------
# One capture
# ---------------------------------------------------------------------------


STATUSES = ("captured", "unbuilt", "not-rendered")


def catalogue_problems(entries):
    """Everything wrong with a catalogue before a browser is launched. [] means usable.

    A catalogue is data that names behaviour (scenarios, actions, probes); a typo in it would
    otherwise surface as a half-run, or worse as a surface silently photographed in the wrong
    state. Checked by `vp_selftest.py` against the real file AND a corrupted copy.
    """
    problems = []
    seen = set()
    for e in entries:
        slug = e.get("slug", "?")
        if not vp.slug_ok(slug):
            problems.append("%s: bad slug" % slug)
        if slug in seen:
            problems.append("%s: duplicate slug" % slug)
        seen.add(slug)
        if e.get("scenario", "signed-out") not in SCENARIOS:
            problems.append("%s: unknown scenario %r" % (slug, e.get("scenario")))
        if e.get("action", "none") not in ACTIONS:
            problems.append("%s: unknown action %r" % (slug, e.get("action")))
        if not str(e.get("path", "")).startswith("/"):
            problems.append("%s: path must start with /" % slug)
        status = e.get("status", "captured")
        if status not in STATUSES:
            problems.append("%s: unknown status %r" % (slug, status))
        if not e.get("node") or not re.fullmatch(r"\d+:\d+", e.get("node", "")):
            problems.append("%s: node id missing or malformed" % slug)
        if e.get("reference") != slug:
            problems.append("%s: reference must equal the slug (one reference per surface)" % slug)
        if status == "not-rendered":
            sp = e.get("source_probe") or {}
            if not sp.get("control") or not sp.get("must_not_contain"):
                problems.append("%s: not-rendered needs source_probe.control and must_not_contain" % slug)
        if e.get("width", 1440) != 1440 or not isinstance(e.get("height"), int):
            problems.append("%s: width must be 1440 and height an integer (the Figma frame height)" % slug)
    return problems


def _bind_api(ctx, scenario_name, calls, held):
    scenario = SCENARIOS[scenario_name]
    graphql_op = re.compile(r"\b(?:query|mutation)\s+(\w+)")

    def handler(route, request):
        if request.method == "GET":
            # /graphql/csrf bootstrap. An empty 204 is enough: the stub never checks a token.
            route.fulfill(status=204, body="")
            return
        op = "?"
        try:
            body = request.post_data_json or {}
            m = graphql_op.search(body.get("query", ""))
            op = m.group(1) if m else "?"
        except Exception:  # noqa: BLE001 - a malformed body is answered like any other op
            pass
        if len(calls) < MAX_CALLS:
            calls.append(op)
        reply = scenario(op)
        if reply is HANG:
            # Never answered while the page is photographed. Kept so teardown can abort it
            # explicitly: a handler abandoned at context close leaves a pending task behind.
            if len(held) < MAX_CALLS:
                held.append(route)
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(reply))

    ctx.route("**/graphql/**", handler)


def inter_problem(slug, dump, require_inter=True):
    """A sentence if Inter did not load on the page (so the capture must be refused), else None.

    Figma is drawn in Inter; a fallback face re-wraps text and invents layout differences the code does
    not have. A function so `vp_selftest.py` can call it with a stubbed page result.
    """
    if require_inter and not (dump.get("doc") or {}).get("inter"):
        return (
            "%s: Inter did not load (document.fonts.check(%r) is false) — Figma is drawn in "
            "Inter and a fallback face would invent layout differences; refusing to capture"
            % (slug, INTER_PROBE)
        )
    return None


def enforce_dump_caps(dump):
    """Re-impose the DOM/focus caps on what the page returned, and flag it when they bite.

    The page applies MAX_DOM_ITEMS / MAX_FOCUS_ITEMS itself, but that is JavaScript running in someone
    else's page: a bug there (or a page that returns more) must not become an unbounded file. Returns the
    same dict, trimmed. `truncated` is set when the DOM list was cut (the capture then FAILS: the text and
    contrast checks would read part of the page); `focus_capped` is informational.
    """
    items = dump.get("items") or []
    if len(items) > MAX_DOM_ITEMS:
        dump["items"] = items[:MAX_DOM_ITEMS]
        dump["truncated"] = True
    focus = dump.get("focus") or []
    if len(focus) > MAX_FOCUS_ITEMS:
        dump["focus"] = focus[:MAX_FOCUS_ITEMS]
    if len(dump.get("focus") or []) >= MAX_FOCUS_ITEMS:
        dump["focus_capped"] = True
    return dump


def capture_entry(browser, base, entry, out_dir, engine, require_inter=True, settle_cap=MAX_SETTLE_MS):
    """Capture one surface. Returns (record, error_list)."""
    errors = []
    slug = entry["slug"]
    png_name = "%s.%s.png" % (slug, engine)
    png_path = os.path.join(out_dir, png_name)
    width = int(entry.get("width", 1440))
    scenario_name = entry.get("scenario", "signed-out")
    action_name = entry.get("action", "none")
    if scenario_name not in SCENARIOS:
        return None, ["%s: unknown scenario %r (define it in vp_capture_marketing.py)" % (slug, scenario_name)]
    if action_name not in ACTIONS:
        return None, ["%s: unknown action %r (define it in vp_capture_marketing.py)" % (slug, action_name)]

    ctx = browser.new_context(
        viewport={"width": width, "height": int(entry.get("viewport_height", 900))},
        device_scale_factor=1,
        reduced_motion="reduce",
        locale="en-GB",
        timezone_id="UTC",
    )
    calls = []
    held = []
    page_errors = []
    record = {"calls": calls, "page_errors": page_errors}
    interrupted = False
    try:
        _bind_api(ctx, scenario_name, calls, held)
        if entry.get("session"):
            ctx.add_init_script(
                "try{localStorage.setItem(%s, %s)}catch(e){}"
                % (json.dumps(SESSION_HINT_KEY), json.dumps(json.dumps({
                    "role": "ADMIN", "orgId": "org-1", "expiresAt": "2099-01-01T00:00:00.000Z"})))
            )
        page = ctx.new_page()
        page.on("pageerror", lambda e: page_errors.append(str(e).splitlines()[0][:160]))
        wait_until = "load" if scenario_name in HELD_ON_LOAD else "networkidle"
        page.goto(base + entry["path"], wait_until=wait_until, timeout=30000)
        try:
            page.evaluate("document.fonts && document.fonts.ready")
        except Exception:  # noqa: BLE001 - a missing FontFaceSet is treated as 'not loaded' below
            pass
        # Route transitions and lazy chunks: wait for the app to put something in <main>/#app.
        page.wait_for_selector("#app > *", timeout=15000)

        if entry.get("status", "captured") == "unbuilt":
            return _probe_unbuilt(page, entry, record)

        act_err = ACTIONS[action_name](page)
        if act_err:
            errors.append("%s: action %s failed: %s" % (slug, action_name, act_err))
        page.wait_for_timeout(min(int(entry.get("settle_ms", 700)), settle_cap))
        if entry.get("wait_for"):
            try:
                page.wait_for_selector(entry["wait_for"], timeout=8000)
            except Exception as exc:  # noqa: BLE001
                errors.append("%s: wait_for %r never appeared (%s)" % (slug, entry["wait_for"], str(exc).splitlines()[0][:80]))

        dump = enforce_dump_caps(page.evaluate(DOM_DUMP_JS, [MAX_DOM_ITEMS, MAX_FOCUS_ITEMS]))
        inter_err = inter_problem(slug, dump, require_inter)
        if inter_err:
            errors.append(inter_err)
        if dump.get("truncated"):
            errors.append(
                "%s: the DOM dump hit MAX_DOM_ITEMS=%d and was truncated; the text and contrast checks would "
                "read part of the page, so this capture fails (raise the cap deliberately)" % (slug, MAX_DOM_ITEMS))
        doc = dump.get("doc") or {}
        too_big = vp.pixel_budget_problem((int(doc.get("w") or 0), int(doc.get("h") or 0)), "%s page" % slug)
        if too_big:
            errors.append(too_big)
            record.update({"png": None, "doc": doc})
            return record, errors
        page.screenshot(path=png_path, full_page=True, animations="disabled")
        dom_name = "%s.%s.dom.json" % (slug, engine)
        vp.dump_json(os.path.join(out_dir, dom_name), {
            "slug": slug, "engine": engine, "path": entry["path"], "scenario": scenario_name,
            "action": action_name, "calls": calls, **dump,
        })
        record.update({"png": png_name, "dom": dom_name, "doc": dump.get("doc"),
                       "inter_loaded": bool((dump.get("doc") or {}).get("inter"))})
    except KeyboardInterrupt:
        # Ctrl-C: do NOT run the teardown below. Playwright's `ctx.close()` after a KeyboardInterrupt spins
        # at 100% CPU with the driver and every browser still alive (reproduced 3 of 3 by Vera, N2).
        # Skipping it and re-raising lets the `with sync_playwright()` exit stop the driver cleanly.
        interrupted = True
        raise
    except Exception as exc:  # noqa: BLE001 - any driver failure is a failed capture, surfaced loudly
        errors.append("%s: capture raised %s: %s" % (slug, type(exc).__name__, str(exc).splitlines()[0][:160]))
    finally:
        if not interrupted:
            # A HANG scenario leaves requests unanswered on purpose. Abort them explicitly now
            # that the frame is taken, so closing the context abandons nothing.
            for route in held:
                try:
                    route.abort()
                except Exception:  # noqa: BLE001 - teardown must never mask the capture's own result
                    pass
            ctx.close()
    if page_errors:
        errors.append("%s: page errors: %s" % (slug, "; ".join(page_errors)[:200]))
    return record, errors


def _probe_unbuilt(page, entry, record):
    """An `unbuilt` surface is only honestly unbuilt while its route is the site's 404 view."""
    h1s = page.evaluate("Array.from(document.querySelectorAll('h1')).map(h => h.innerText.trim())")
    expect = entry.get("unbuilt_h1", "We couldn't find that page")
    confirmed = expect in h1s
    record.update({
        "png": None,
        "probe": {"path": entry["path"], "h1": h1s[:3], "expected_h1": expect, "confirmed": confirmed},
    })
    errors = []
    if not confirmed:
        errors.append(
            "%s: catalogued as unbuilt but %s now renders %r instead of the 404 view — the screen "
            "exists: capture it and compare it, then drop `status: unbuilt` from the catalogue"
            % (entry["slug"], entry["path"], h1s[:2])
        )
    return record, errors


# ---------------------------------------------------------------------------
# Engines and main
# ---------------------------------------------------------------------------


def launch(p, engine):
    if engine == "blink":
        try:
            return p.chromium.launch(), "Playwright Chromium"
        except Exception:  # noqa: BLE001 - fall back to the system Chrome channel
            return p.chromium.launch(channel="chrome"), "Google Chrome (channel)"
    return p.webkit.launch(), "Playwright WebKit"


def result_record(entry, engine, engine_detail, rec, errors, out_dir):
    png = rec.get("png") if rec else None
    size = None
    if png:
        with Image.open(os.path.join(out_dir, png)) as im:
            size = list(im.size)
    status = entry.get("status", "captured")
    ok = not errors and (status != "captured" or bool(png))
    return {
        "slug": entry["slug"],
        "kind": entry.get("kind", "page"),
        "area": entry.get("area", ""),
        "state": entry.get("scenario", "signed-out") + "/" + entry.get("action", "none"),
        "status": status,
        "node": entry.get("node", ""),
        "reference": entry.get("reference", ""),
        "reference_kind": entry.get("reference_kind", "screen"),
        "expected_size": [entry.get("width", 1440), entry.get("height")],
        "actual_size": size,
        "scale": 1,
        "png": png,
        "dom": (rec or {}).get("dom"),
        "doc": (rec or {}).get("doc"),
        "probe": (rec or {}).get("probe"),
        "calls": (rec or {}).get("calls", []),
        "engine": engine,
        "engine_detail": engine_detail,
        "driver": {"ok": ok, "errors": [], "regions": []},
        "errors": errors,
        "ok": ok,
    }


def capture_all(engines, entries, args, base, require, results):
    """Run every entry under every engine, appending records to `results`.

    Returns an exit code to stop with (3: a required engine is missing), or None to carry on.
    """
    with sync_playwright() as p:
        for engine in engines:
            try:
                browser, detail = launch(p, engine)
            except Exception as exc:  # noqa: BLE001 - a missing engine is loud, not a crash
                msg = "%s engine unavailable (%s)" % (engine, str(exc).splitlines()[0][:110])
                if require:
                    print("FAIL: SELAHCUE_VISUAL_REQUIRE=1 but " + msg)
                    return 3
                print("!! %s CAPTURE SKIPPED — %s" % (engine.upper(), msg))
                continue
            detail = "%s %s" % (detail, browser.version)
            for entry in entries:
                if engine == "webkit" and entry.get("status", "captured") != "captured":
                    continue  # the probe is engine-independent; run it once, under blink
                rec, errs = capture_entry(browser, base, entry, args.out, engine,
                                          require_inter=not args.allow_fallback_font)
                if rec is None:
                    res = {"slug": entry["slug"], "engine": engine, "ok": False, "png": None,
                           "errors": errs, "status": entry.get("status", "captured")}
                else:
                    res = result_record(entry, engine, detail, rec, errs, args.out)
                results.append(res)
                print("%s %-26s %-7s %-34s %s" % (
                    "ok  " if res["ok"] else "FAIL", res["slug"], engine,
                    res.get("png") or "(%s)" % res.get("status", "no png"),
                    "; ".join(res["errors"])[:160]))
            browser.close()
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="directory to write PNGs, DOM dumps and captures.json into")
    ap.add_argument("--engine", default="blink", choices=["blink", "webkit", "both"])
    ap.add_argument("--only", nargs="*", default=None, help="capture only these slugs")
    ap.add_argument("--surfaces", default=None)
    ap.add_argument("--allow-fallback-font", action="store_true")
    args = ap.parse_args()

    suite = vp.get_suite("marketing")
    catalogue = vp.load_json(args.surfaces or suite.surfaces_path)
    entries = [e for e in catalogue.get("marketing", []) if not args.only or e["slug"] in args.only]
    if not entries:
        print("FAIL: no marketing surfaces matched")
        return 2
    bad = catalogue_problems(catalogue.get("marketing", []))
    if bad:
        print("FAIL: the catalogue is not usable:\n  " + "\n  ".join(bad))
        return 2

    problem = dist_problem()
    if problem:
        print("FAIL: " + problem)
        return 2
    os.makedirs(args.out, exist_ok=True)
    require = os.environ.get("SELAHCUE_VISUAL_REQUIRE") == "1"

    if sync_playwright is None:
        print("FAIL: Playwright is not installed (python3 -m pip install --user playwright && python3 -m playwright install chromium webkit)")
        return 3

    engines = ["blink", "webkit"] if args.engine == "both" else [args.engine]
    server, base = start_server(DIST)
    results = []
    interrupted = False
    try:
        try:
            status = capture_all(engines, entries, args, base, require, results)
        except KeyboardInterrupt:
            # capture_entry skipped its teardown on purpose; leaving the `with` in capture_all stopped the driver.
            interrupted = True
            status = None
    finally:
        server.shutdown()
        server.server_close()
    if status is not None:
        return status
    if interrupted:
        print("interrupted: no captures.json written; nothing left running")
        return 130

    vp.dump_json(os.path.join(args.out, "captures.json"), {
        "suite": "marketing", "dist": DIST, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "captures": results,
    })
    failed = [r for r in results if not r["ok"]]
    print("=== marketing capture: %d records, %d FAIL ===" % (len(results), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
