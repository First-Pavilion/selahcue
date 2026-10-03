#!/usr/bin/env python3
"""Build the stand-alone side-by-side page for the Figma fidelity audit.

    python3 scripts/build_fidelity_artifact.py --run RUN_DIR --out OUT_DIR

Writes `OUT_DIR/index.html` (a page fragment: the Artifact tool wraps it in a document) and
`OUT_DIR/img/<slug>.figma.jpg` / `<slug>.build.jpg`, then prints the `files` list to hand to the Artifact
tool. The page reads on its own for someone who was not in the session: what was compared, at which
commit, every surface with Figma beside the build, every difference with its class, evidence and fix, and
the decisions Uma and the owner still have to make.

Data comes from the audit's own files (`surfaces.json`, `findings/*.json`, `tickets.json`) and the
screenshots of a `visual_parity.py --suite marketing` run; nothing here is typed by hand.

Bounded: at most MAX_IMAGES images, each downscaled to IMG_WIDTH px wide as JPEG, and the whole output
is refused if it would exceed MAX_TOTAL_BYTES (the Artifact limit is 16 MB; this leaves headroom).
"""

from __future__ import annotations

import argparse
import collections
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_fidelity_audit as cfa  # noqa: E402
import vp_core as vp  # noqa: E402
from PIL import Image  # noqa: E402

IMG_WIDTH = 720
JPEG_QUALITY = 72
MAX_IMAGES = 80
MAX_TOTAL_BYTES = 13 * 1024 * 1024

CLASS_LABEL = {
    "A": "Code bug", "B": "Documented deviation", "C": "Figma content the repo does not back",
    "D": "Figma gap", "E": "Missing screen",
}
CLASS_TEXT = {
    "A": "The build differs from Figma and nothing documents it as intended. The fix is to match Figma.",
    "B": "Deliberate and documented (a token layer, a handoff decision, an accessibility colour). Left as is, with its source.",
    "C": "Figma draws something the repo does not back. Layout and styling are kept, the claim is not shipped.",
    "D": "Figma does not draw it: a state, a page, or an element the build has that no frame shows. Raised to Uma.",
    "E": "The screen does not exist in code yet (Manage Devices). The build has to create it.",
}
AREA_LABEL = {
    "chrome": "Shared chrome and tokens", "components": "Shared components (badge, form field, FAQ, pricing card, dialog)", "home": "Home", "core": "Pricing, Features, Download, About",
    "secondary": "Contact, Support, Docs, Changelog, Blog, Careers, Legal, Affiliates",
    "auth": "Sign in, Verify, Reset", "account": "Account and Manage Devices",
}
VERDICT_LABEL = {
    "matches": "Matches", "diverges": "Differs", "not-built": "Not built",
    "not-rendered-by-design": "Not rendered by design",
}

CSS = """
:root{
  /* Layout concept: an inspection ledger. A quiet cool-grey sheet, ink text, one indigo accent borrowed from the
     product, and five class marks that each carry a letter so colour is never the only cue. */
  --bg:#f2f4f8; --panel:#ffffff; --panel-2:#e9edf4; --ink:#161b24; --ink-2:#4a5568; --line:#d4dae5; --accent:#4a54c4;
  --accent-ink:#ffffff; --focus:#2f6df6;
  --cA:#b3361c; --cB:#4b5668; --cC:#8a5a00; --cD:#6a3fc4; --cE:#0b6b63;
  --cA-bg:#fbe9e5; --cB-bg:#e9edf3; --cC-bg:#fbf0d6; --cD-bg:#eee8fb; --cE-bg:#dcf2ee;
  --sev-high:#b3361c; --sev-med:#8a5a00; --sev-low:#4b5668;
  --font-body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --font-mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --font-display:"IBM Plex Sans Condensed","IBM Plex Sans",system-ui,sans-serif;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0f131a; --panel:#171c26; --panel-2:#1f2633; --ink:#e8ecf4; --ink-2:#a5afc2; --line:#2b3445; --accent:#8c96f0;
  --accent-ink:#0f131a; --focus:#7aa2ff;
  --cA:#ff8f78; --cB:#a9b4c7; --cC:#f0c25a; --cD:#c0a6ff; --cE:#5fd3c6;
  --cA-bg:#3a1c18; --cB-bg:#222a38; --cC-bg:#392f14; --cD-bg:#2a2144; --cE-bg:#12302d;
  --sev-high:#ff8f78; --sev-med:#f0c25a; --sev-low:#a9b4c7; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f131a; --panel:#171c26; --panel-2:#1f2633; --ink:#e8ecf4; --ink-2:#a5afc2; --line:#2b3445; --accent:#8c96f0;
  --accent-ink:#0f131a; --focus:#7aa2ff;
  --cA:#ff8f78; --cB:#a9b4c7; --cC:#f0c25a; --cD:#c0a6ff; --cE:#5fd3c6;
  --cA-bg:#3a1c18; --cB-bg:#222a38; --cC-bg:#392f14; --cD-bg:#2a2144; --cE-bg:#12302d;
  --sev-high:#ff8f78; --sev-med:#f0c25a; --sev-low:#a9b4c7; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--font-body);padding-inline:clamp(16px,4vw,48px);padding-block:24px 64px}
.wrap{max-width:1180px;margin-inline:auto}
a{color:var(--accent)} a:focus-visible,button:focus-visible,summary:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
h1,h2,h3{font-family:var(--font-display);line-height:1.15;text-wrap:balance;margin:0}
h1{font-size:clamp(30px,5vw,46px);font-weight:600;letter-spacing:-.01em}
h2{font-size:24px;font-weight:600;margin-block:44px 12px}
h3{font-size:17px;font-weight:600}
code,.mono{font-family:var(--font-mono);font-size:.88em}
.eyebrow{font:600 11.5px/1 var(--font-mono);letter-spacing:.09em;text-transform:uppercase;color:var(--ink-2);margin:0 0 14px}
.lede{max-width:68ch;color:var(--ink-2);font-size:16.5px;margin:14px 0 0}
.meta{display:flex;flex-wrap:wrap;gap:6px 18px;margin:18px 0 0;color:var(--ink-2);font-size:13px}
.meta span b{color:var(--ink);font-weight:600}
.totals{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:26px}
.tot{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 14px 12px;min-width:0}
.tot .n{font:600 34px/1 var(--font-display);font-variant-numeric:tabular-nums}
.tot .l{font-size:12.5px;color:var(--ink-2);margin-top:6px}
.chip{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;padding-inline:6px;border-radius:5px;font:700 12px/1 var(--font-mono);flex:none}
.chip.cA{background:var(--cA-bg);color:var(--cA)} .chip.cB{background:var(--cB-bg);color:var(--cB)}
.chip.cC{background:var(--cC-bg);color:var(--cC)} .chip.cD{background:var(--cD-bg);color:var(--cD)} .chip.cE{background:var(--cE-bg);color:var(--cE)}
.tot.cA{border-top:3px solid var(--cA)} .tot.cB{border-top:3px solid var(--cB)} .tot.cC{border-top:3px solid var(--cC)}
.tot.cD{border-top:3px solid var(--cD)} .tot.cE{border-top:3px solid var(--cE)}
.tbl{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font:600 11.5px/1.2 var(--font-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2);background:var(--panel-2)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}
.tickets li{margin-bottom:8px} .tickets{padding-left:20px}
.legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin:0;padding:0;list-style:none}
.legend li{display:flex;gap:10px;align-items:flex-start;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:11px 12px;font-size:13.5px}
.decision{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:10px}
.decision .h{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.decision p{margin:6px 0 0;font-size:13.5px;color:var(--ink-2)} .decision p b{color:var(--ink);font-weight:600}
.controls{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);padding-block:10px;display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;border-bottom:1px solid var(--line);margin-top:8px}
.controls label{font-size:12.5px;color:var(--ink-2)}
.controls input,.controls select{font:inherit;font-size:13.5px;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:6px 9px;min-width:0}
.fchip{font:700 12px/1 var(--font-mono);border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:6px;padding:7px 9px;cursor:pointer}
.fchip[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.count{margin-left:auto;font-size:12.5px;color:var(--ink-2)}
details.surface{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin-top:12px}
details.surface>summary{list-style:none;cursor:pointer;padding:13px 16px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 14px;align-items:center}
details.surface>summary::-webkit-details-marker{display:none}
.s-title{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;min-width:0}
.s-title h3{overflow-wrap:anywhere}
.node{font:500 12px/1 var(--font-mono);color:var(--ink-2)}
.verdict{font:600 11px/1 var(--font-mono);letter-spacing:.05em;text-transform:uppercase;border:1px solid var(--line);border-radius:999px;padding:4px 9px;color:var(--ink-2);white-space:nowrap}
.verdict.v-diverges{color:var(--cA);border-color:var(--cA)} .verdict.v-matches{color:var(--cE);border-color:var(--cE)}
.verdict.v-not-built{color:var(--cE);border-color:var(--cE)} .verdict.v-not-rendered-by-design{color:var(--cB)}
.s-right{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.s-sum{grid-column:1/-1;color:var(--ink-2);font-size:13.5px;margin:2px 0 0;max-width:90ch}
.sbody{padding:0 16px 18px;border-top:1px solid var(--line)}
.pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;margin-top:14px;align-items:start}
.pair figure{margin:0;min-width:0}
.pair figcaption{font:600 11.5px/1 var(--font-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2);margin-bottom:6px}
.pair img{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:6px;background:#0e1116}
.pair .none{border:1px dashed var(--line);border-radius:6px;padding:28px 16px;color:var(--ink-2);font-size:13.5px;text-align:center;background:var(--panel-2)}
.pair a.open{display:block}
ol.finds{list-style:none;margin:18px 0 0;padding:0;display:grid;gap:10px}
.find{border:1px solid var(--line);border-left-width:4px;border-radius:8px;padding:11px 13px;background:var(--panel)}
.find.cA{border-left-color:var(--cA)} .find.cB{border-left-color:var(--cB)} .find.cC{border-left-color:var(--cC)}
.find.cD{border-left-color:var(--cD)} .find.cE{border-left-color:var(--cE)}
.fh{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.fh strong{font-weight:600;min-width:0;overflow-wrap:anywhere}
.fid{font:500 11.5px/1 var(--font-mono);color:var(--ink-2)}
.sev{font:600 10.5px/1 var(--font-mono);letter-spacing:.05em;text-transform:uppercase}
.sev.high{color:var(--sev-high)} .sev.medium{color:var(--sev-med)} .sev.low{color:var(--sev-low)}
.tag{font:600 10.5px/1 var(--font-mono);letter-spacing:.04em;text-transform:uppercase;border:1px solid var(--line);border-radius:4px;padding:3px 5px;color:var(--ink-2)}
dl.fd{display:grid;grid-template-columns:78px minmax(0,1fr);gap:4px 12px;margin:9px 0 0;font-size:13.5px}
dl.fd dt{font:600 11px/1.5 var(--font-mono);letter-spacing:.05em;text-transform:uppercase;color:var(--ink-2);padding-top:2px}
dl.fd dd{margin:0;min-width:0;overflow-wrap:anywhere}
.empty{color:var(--ink-2);font-size:13.5px;margin-top:14px}
.method li{margin-bottom:6px}
footer{margin-top:48px;color:var(--ink-2);font-size:12.5px;border-top:1px solid var(--line);padding-top:14px}
@media (max-width:760px){
  .totals{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pair{grid-template-columns:minmax(0,1fr)}
  dl.fd{grid-template-columns:minmax(0,1fr)} dl.fd dt{padding-top:6px}
  details.surface>summary{grid-template-columns:minmax(0,1fr)} .s-right{justify-content:flex-start}
  .count{margin-left:0;width:100%}
  .controls{position:static}
}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
"""

JS = """
(function(){
  var cards=[].slice.call(document.querySelectorAll('details.surface'));
  var chips=[].slice.call(document.querySelectorAll('.fchip'));
  var area=document.getElementById('area'), q=document.getElementById('q'), out=document.getElementById('shown');
  var active={};
  function apply(){
    var term=(q.value||'').toLowerCase().trim(), a=area.value, any=Object.keys(active).length>0, shown=0;
    cards.forEach(function(c){
      var okArea=(a==='all')||c.getAttribute('data-area')===a;
      var finds=[].slice.call(c.querySelectorAll('.find')), visible=0;
      finds.forEach(function(f){
        var okC=!any||active[f.getAttribute('data-class')];
        var okT=!term||f.textContent.toLowerCase().indexOf(term)!==-1;
        f.hidden=!(okC&&okT); if(!f.hidden) visible++;
      });
      var titleMatch=term&&c.querySelector('summary').textContent.toLowerCase().indexOf(term)!==-1;
      var show=okArea&&(visible>0||(!any&&(!term||titleMatch)));
      if(any&&finds.length===0) show=false;
      c.hidden=!show; if(show) shown++;
    });
    out.textContent=shown+' of '+cards.length+' surfaces shown';
  }
  chips.forEach(function(b){b.addEventListener('click',function(){
    var k=b.getAttribute('data-class');
    if(active[k]){delete active[k];b.setAttribute('aria-pressed','false');}else{active[k]=true;b.setAttribute('aria-pressed','true');}
    apply();});});
  area.addEventListener('change',apply); q.addEventListener('input',apply);
  document.getElementById('openall').addEventListener('click',function(){cards.forEach(function(c){if(!c.hidden)c.open=true;});});
  document.getElementById('closeall').addEventListener('click',function(){cards.forEach(function(c){c.open=false;});});
  function fromHash(){var id=location.hash.slice(1);if(!id)return;var el=document.getElementById(id);
    if(el&&el.tagName==='DETAILS'){el.open=true;el.scrollIntoView();}}
  window.addEventListener('hashchange',fromHash); fromHash(); apply();
})();
"""


def esc(v):
    return html.escape(str(v if v is not None else ""), quote=True)


def make_image(src, dst):
    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > IMG_WIDTH:
            im = im.resize((IMG_WIDTH, max(1, round(im.height * IMG_WIDTH / im.width))), Image.LANCZOS)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return os.path.getsize(dst)


def finding_html(f):
    if f.get("dup_of"):
        return ('<li class="find c%s" data-class="%s" id="%s"><div class="fh"><span class="chip c%s">%s</span>'
                '<span class="fid">%s</span><strong>%s</strong><span class="tag">duplicate of <a href="#%s">%s</a></span></div></li>') % (
            f["class"], f["class"], esc(f["id"]), f["class"], f["class"], esc(f["id"]), esc(f["title"]),
            esc(f["dup_of"]), esc(f["dup_of"]))
    parts = ['<li class="find c%s" data-class="%s" id="%s">' % (f["class"], f["class"], esc(f["id"])),
             '<div class="fh"><span class="chip c%s" title="%s">%s</span><span class="sev %s">%s</span>'
             '<span class="fid">%s</span><strong>%s</strong>' % (
                 f["class"], esc(CLASS_LABEL[f["class"]]), f["class"], esc(f.get("severity")), esc(f.get("severity")),
                 esc(f["id"]), esc(f["title"]))]
    if f.get("scope") == "shared":
        parts.append('<span class="tag">shared: %s</span>' % esc(f.get("component")))
    if f.get("a11y"):
        parts.append('<span class="tag">accessibility</span>')
    if f.get("owned_by"):
        parts.append('<span class="tag">owned by ClickUp %s</span>' % esc(f["owned_by"]))
    parts.append("</div><dl class=\"fd\">")
    rows = [("Figma", f["figma"]), ("Build", f["build"]), ("Evidence", f["evidence"])]
    if f.get("fix"):
        rows.append(("Fix", f["fix"]))
    if f.get("source"):
        rows.append(("Source", f["source"]))
    if f.get("decision"):
        rows.append(("Decision", f["decision"]))
    if f.get("link"):
        rows.append(("Linked", f["link"]))
    if f.get("ticket"):
        rows.append(("Ticket", f["ticket"]))
    for k, v in rows:
        parts.append("<dt>%s</dt><dd>%s</dd>" % (k, esc(v)))
    parts.append("</dl></li>")
    return "".join(parts)


def decision_html(f, slug):
    link = (' · owned by <b>%s</b>' % esc(f["link"])) if f.get("link") else ""
    return ('<div class="decision"><div class="h"><span class="chip c%s">%s</span><strong>%s</strong>'
            '<span class="fid">%s · %s</span></div><p><b>Figma</b> %s</p><p><b>Build</b> %s</p>'
            '<p><b>Question</b> %s%s</p></div>') % (
        f["class"], f["class"], esc(f["title"]), esc(slug), esc(f["id"]), esc(f["figma"]), esc(f["build"]),
        esc(f.get("decision")), link)


def build(run_dir, out_dir, meta):
    catalogue = cfa.load_catalogue()
    findings = cfa.load_findings()
    tickets = cfa.load_tickets()
    problems = cfa.check(catalogue, findings, tickets)
    if problems:
        raise SystemExit("the audit data is not complete; fix it first:\n  " + "\n  ".join(problems[:15]))
    store = vp.get_suite("marketing").store()
    area_of, surf_of = {}, {}
    for area, data in findings.items():
        for slug, surf in data.get("surfaces", {}).items():
            area_of[slug] = area
            surf_of[slug] = surf
    by_group, total, sev, set_aside = cfa.summarise(findings)

    img_dir = os.path.join(out_dir, "img")
    images, total_bytes, files = {}, 0, []
    for slug, cat in catalogue.items():
        ref = store.path_for(slug)
        built = os.path.join(run_dir, "marketing", "%s.blink.png" % slug)
        entry = {}
        for key, src in (("figma", ref), ("build", built)):
            if cat.get("status") == "unbuilt" and key == "build":
                continue
            if not os.path.exists(src):
                raise SystemExit("missing image: " + src)
            dst = os.path.join(img_dir, "%s.%s.jpg" % (slug, key))
            total_bytes += make_image(src, dst)
            entry[key] = "img/%s.%s.jpg" % (slug, key)
            files.append(entry[key])
        images[slug] = entry
    if len(files) > MAX_IMAGES or total_bytes > MAX_TOTAL_BYTES:
        raise SystemExit("output over bounds: %d images, %d bytes" % (len(files), total_bytes))

    H = []
    w = H.append
    w("<title>Figma Fidelity Audit</title>")
    w("<style>%s</style>" % CSS)
    w('<div class="wrap"><header>')
    w('<p class="eyebrow">SelahCue · marketing site and account screens · ClickUp %s</p>' % esc(meta["ticket"]))
    w("<h1>Figma fidelity audit</h1>")
    w('<p class="lede">What was designed in Figma beside what the built site renders, for all 16 pages and all 19 sign-in, '
      "verify, reset and device states, with every difference classified. This is Phase 0: nothing was fixed. "
      "Fix tickets were raised from it.</p>")
    w('<div class="meta"><span><b>Built from</b> origin/main <code>%s</code></span><span><b>Figma</b> file <code>%s</code>, '
      "page Marketing Website <code>468:124</code>, section <code>743:124</code></span><span><b>Rendered</b> 1440px wide, Chromium, API scripted</span>"
      "<span><b>Audited</b> %s</span></div>" % (esc(meta["origin_main"]), esc(vp.FIGMA_FILE_KEY), esc(meta["date"])))
    w("</header>")

    w("<h2>At a glance</h2>")
    w('<div class="totals">')
    for c in cfa.CLASSES:
        w('<div class="tot c%s"><div class="n">%d</div><div class="l"><span class="chip c%s">%s</span> %s</div></div>' % (
            c, total[c], c, c, esc(CLASS_LABEL[c])))
    w("</div>")
    w('<div class="tbl" style="margin-top:14px"><table><thead><tr><th>Fix ticket group</th><th class="num">A</th><th class="num">B</th>'
      '<th class="num">C</th><th class="num">D</th><th class="num">E</th></tr></thead><tbody>')
    for g in cfa.TICKET_GROUPS:
        c = by_group.get(g, collections.Counter())
        t = tickets.get("tickets", {}).get(g)
        label = esc(AREA_LABEL.get(g, g))
        if t and t.get("url"):
            label += ' · <a href="%s">%s</a>' % (esc(t["url"]), esc(t["id"]))
        w("<tr><td>%s</td>%s</tr>" % (label, "".join('<td class="num">%d</td>' % c[k] for k in cfa.CLASSES)))
    w("</tbody></table></div>")
    extra = [(k, tickets.get("tickets", {}).get(k)) for k in ("decisions", "devices-api", "sign-out-bug")]
    extra = [(k, t) for k, t in extra if t]
    if extra:
        w('<ul class="tickets">')
        for k, t in extra:
            w('<li><a href="%s">%s</a> %s</li>' % (esc(t["url"]), esc(t["id"]), esc(t["title"])))
        w("</ul>")
    w('<p class="empty">Counted once each. Set aside: %d duplicates (the same defect seen on another page, each pointing at its canonical finding) '
      'and %d findings that another ticket already owns.</p>' % (set_aside["duplicates"], set_aside["owned elsewhere"]))

    w("<h2>What the classes mean</h2>")
    w('<ul class="legend">')
    for c in cfa.CLASSES:
        w('<li><span class="chip c%s">%s</span><span><b>%s.</b> %s</span></li>' % (c, c, esc(CLASS_LABEL[c]), esc(CLASS_TEXT[c])))
    w("</ul>")

    for cls, heading, note in (
        ("C", "Decisions for the owner: content the repo does not back",
         "Figma's layout stays, the claim does not ship. Where the build already shows the claim, removal belongs to "
         "ClickUp 17tnw2b0x3h."),
        ("D", "Decisions for Uma: things Figma does not draw", "Each is raised, not invented."),
    ):
        items = [(s, f) for _a, s, _sf, f in cfa.all_findings(findings) if f["class"] == cls and cfa.is_counted(f)]
        w("<h2>%s</h2><p class=\"empty\" style=\"margin-top:0\">%s</p>" % (esc(heading), esc(note)))
        if not items:
            w('<p class="empty">None.</p>')
        for s, f in items:
            w(decision_html(f, s))

    w("<h2>Surfaces</h2>")
    w('<div class="controls" role="group" aria-label="Filter surfaces">')
    for c in cfa.CLASSES:
        w('<button type="button" class="fchip" data-class="%s" aria-pressed="false" title="%s">%s</button>' % (c, esc(CLASS_LABEL[c]), c))
    w('<label for="area">Area</label><select id="area"><option value="all">All areas</option>')
    for g in cfa.TICKET_GROUPS:
        w('<option value="%s">%s</option>' % (g, esc(AREA_LABEL[g])))
    w('</select><label for="q">Search</label><input id="q" type="search" placeholder="text, id or node" autocomplete="off">')
    w('<button type="button" class="fchip" id="openall">Open all</button><button type="button" class="fchip" id="closeall">Close all</button>')
    w('<span class="count" id="shown" role="status"></span></div>')

    order = [cfa.SHARED_SURFACE] + list(catalogue)
    for slug in order:
        surf = surf_of.get(slug)
        if surf is None:
            continue
        cat = catalogue.get(slug, {})
        area = area_of[slug]
        group = cfa.TICKET_GROUP.get(area, area)
        counts = collections.Counter(f["class"] for f in surf["findings"] if cfa.is_counted(f))
        label = cat.get("label") or (slug.replace("-", " ").title() if slug != cfa.SHARED_SURFACE else "Shared chrome: nav, footer, buttons, tokens")
        w('<details class="surface" id="%s" data-area="%s"><summary><div class="s-title"><h3>%s</h3><span class="node">%s</span></div>'
          '<div class="s-right"><span class="verdict v-%s">%s</span>%s</div><p class="s-sum">%s</p></summary><div class="sbody">' % (
              esc(slug), esc(group), esc(label), esc(("Figma " + surf.get("node", "")) if slug != cfa.SHARED_SURFACE else "Home nav 468:126, footer 479:133"),
              esc(surf["verdict"]), esc(VERDICT_LABEL[surf["verdict"]]),
              "".join('<span class="chip c%s" title="%s">%s %d</span>' % (c, esc(CLASS_LABEL[c]), c, counts[c]) for c in cfa.CLASSES if counts[c]),
              esc(surf["summary"])))
        if slug in images:
            im = images[slug]
            w('<div class="pair"><figure><figcaption>Figma %s</figcaption><a class="open" href="%s"><img src="%s" alt="Figma frame for %s" loading="lazy"></a></figure>' % (
                esc(surf.get("node", "")), esc(im["figma"]), esc(im["figma"]), esc(label)))
            if "build" in im:
                cap = "Build, %s" % esc(cat.get("path", ""))
                if cat.get("status") == "not-rendered":
                    cap += " (the shipped substitute state)"
                w('<figure><figcaption>%s</figcaption><a class="open" href="%s"><img src="%s" alt="Built page for %s" loading="lazy"></a></figure></div>' % (
                    cap, esc(im["build"]), esc(im["build"]), esc(label)))
            else:
                w('<figure><figcaption>Build, %s</figcaption><div class="none">Not built. This route shows the site\'s "We couldn\'t find that page" screen.</div></figure></div>' % esc(cat.get("path", "")))
        if surf["findings"]:
            w('<ol class="finds">%s</ol>' % "".join(finding_html(f) for f in surf["findings"]))
        else:
            w('<p class="empty">No differences recorded.</p>')
        w("</div></details>")

    api, bugs = [], []
    for data in findings.values():
        api += data.get("api_gaps", [])
        bugs += data.get("bugs", [])
    if api:
        w("<h2>What the Manage Devices screen needs from the API</h2><div class=\"tbl\"><table><thead><tr><th>Need</th><th>Status</th><th>Evidence</th></tr></thead><tbody>")
        for x in api:
            w("<tr><td>%s</td><td><code>%s</code></td><td>%s</td></tr>" % (esc(x.get("need")), esc(x.get("status")), esc(x.get("evidence"))))
        w("</tbody></table></div>")
    if bugs:
        w("<h2>Defects found along the way</h2><ul class=\"method\">")
        for x in bugs:
            w("<li><b>%s</b> %s <span class=\"fid\">%s</span></li>" % (esc(x.get("title")), esc(x.get("fix") or ""), esc(x.get("evidence"))))
        w("</ul>")

    w("<h2>How it was measured, and what it does not show</h2><ul class=\"method\">")
    for line in (
        "Each frame was exported from Figma at its native size. Each page was rendered from the built site at 1440px wide, full page, with the account API scripted so sign-in, verify, reset and account states can be photographed.",
        "Two comparisons ran for every surface: a picture comparison (where the build and the frame share a height) and a value comparison of type size, weight, line height, colour, alignment, position, radius and copy.",
        "Differences under 3px are not reported. Figma's Inter and the web font can differ by a pixel or two.",
        "Figma's legacy colour variables against the code's design-2.0 tokens are a deliberate layer, not a defect.",
        "Only 1440px is covered here. Mobile and tablet layouts belong to ClickUp 17tnw2b0q9g.",
        "Hover, focus rings and real-API behaviour are read from the source, not photographed. Safari and real devices are not evidenced.",
        "The audit data and the tools to re-run it are in the repository under docs/design/visual-parity/marketing and scripts/vp_*.py.",
    ):
        w("<li>%s</li>" % esc(line))
    w("</ul><footer>Generated from the audit's own data files and a harness run at origin/main <code>%s</code>.</footer></div>" % esc(meta["origin_main"]))
    w("<script>%s</script>" % JS)

    os.makedirs(out_dir, exist_ok=True)
    page = "\n".join(H)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    total = total_bytes + len(page.encode("utf-8"))
    if total > MAX_TOTAL_BYTES:
        raise SystemExit("artifact would be %d bytes, over MAX_TOTAL_BYTES=%d" % (total, MAX_TOTAL_BYTES))
    return files, total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ticket", default="17tnw2b2c75")
    ap.add_argument("--origin-main", default="3fb96da8")
    ap.add_argument("--date", default="2026-10-03")
    args = ap.parse_args()
    files, total = build(os.path.abspath(args.run), os.path.abspath(args.out),
                         {"ticket": args.ticket, "origin_main": args.origin_main, "date": args.date})
    print("wrote %s/index.html and %d images, %.1f MB" % (args.out, len(files), total / 1048576.0))
    print("files: " + ", ".join(files[:3]) + (" ..." if len(files) > 3 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
