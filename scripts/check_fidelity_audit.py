#!/usr/bin/env python3
"""Structural checker, summariser and report writer for the Figma fidelity audit.

The audit's source of truth is data, not prose:

    docs/design/visual-parity/marketing/surfaces.json   the 35 Figma frames (16 pages, 19 states)
    docs/design/visual-parity/marketing/findings/*.json one file per audit area, every difference
    docs/design/visual-parity/marketing/tickets.json    area -> the fix ticket raised from it

and the human report (`docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md`) is
GENERATED from them, so the report cannot say something the data does not.

    python3 scripts/check_fidelity_audit.py                  # check; exit 0 only if the audit is complete
    python3 scripts/check_fidelity_audit.py --require-tickets # also: every A/E finding names its fix ticket
    python3 scripts/check_fidelity_audit.py --summary        # counts by class and area
    python3 scripts/check_fidelity_audit.py --write-report PATH
    python3 scripts/check_fidelity_audit.py --self-test      # prove the checker rejects each kind of bad input

What "complete" means (each rule below is one the self-test breaks on purpose):
  * every surface in the catalogue has exactly one entry, with the catalogue's Figma node id;
  * every finding is classified A to E and carries what its class requires: A and E a fix,
    B a citable source (no source means it was never B), C and D a question for the owner/Uma;
  * `matches` surfaces have no A/C/D/E finding; `not-built` surfaces are the catalogue's unbuilt
    ones and carry only E findings; `not-rendered-by-design` ones carry a B finding;
  * ids are unique across the whole audit; a shared-chrome finding names its component;
  * a finding may be marked `dup_of` (the same defect, seen again on another page: counted once, under
    the canonical finding it names) or `owned_by` (a ClickUp id: an A that another ticket already owns,
    so it is reported but raises no fix of its own); both are validated;
  * the fix tickets that exist are real: a ticket that lists a surface must cover its area.

Bounded: reads a few JSON files (each capped at MAX_BYTES), prints at most the report.
"""

from __future__ import annotations

import argparse
import collections
import copy
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402

MARKETING = vp.MARKETING_DIR
FINDINGS_DIR = os.path.join(MARKETING, "findings")
TICKETS_PATH = os.path.join(MARKETING, "tickets.json")
MAX_BYTES = 4 * 1024 * 1024

CLASSES = ("A", "B", "C", "D", "E")
VERDICTS = ("matches", "diverges", "not-built", "not-rendered-by-design")
SEVERITIES = ("high", "medium", "low")
CHROME_COMPONENTS = ("nav", "footer", "ui-button", "tokens", "app-shell")
# Components other than the chrome that several pages use. Area tickets never edit them, so a finding
# that needs one changed goes to the `components` ticket, which lands before the area tickets with the chrome.
SHARED_COMPONENTS = ("ui-badge", "form-field", "faq-accordion", "pricing-card", "confirm-dialog")
COMPONENTS = CHROME_COMPONENTS + SHARED_COMPONENTS
CLASS_NAMES = {
    "A": "code bug (fix to match Figma)",
    "B": "documented deliberate deviation (leave, source recorded)",
    "C": "Figma content the repo does not back (keep layout, ship no claim)",
    "D": "Figma gap (not drawn; raise to Uma)",
    "E": "screen missing in code (build it)",
}
SHARED_SURFACE = "shared-chrome"
# findings-file `area` -> the fix ticket group it feeds (shared-scope findings always go to `chrome`)
TICKET_GROUP = {
    "shared-chrome": "chrome", "home": "home", "marketing-core": "core",
    "secondary-1": "secondary", "secondary-2": "secondary", "auth": "auth", "account": "account",
}
TICKET_GROUPS = ("chrome", "components", "home", "core", "secondary", "auth", "account")
TICKET_RE = re.compile(r"^[0-9a-z]{8,12}$")


def _load(path):
    if os.path.getsize(path) > MAX_BYTES:
        raise SystemExit("%s is over %d bytes" % (path, MAX_BYTES))
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_catalogue(path=None):
    cat = vp.load_json(path or vp.get_suite("marketing").surfaces_path)["marketing"]
    return {e["slug"]: e for e in cat}


def load_findings(directory=None):
    """{area: data} for every findings/*.json."""
    directory = directory or FINDINGS_DIR
    out = {}
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            data = _load(os.path.join(directory, name))
            out[data.get("area", name[:-5])] = data
    return out


def load_tickets(path=None):
    path = path or TICKETS_PATH
    return vp.load_json(path, default={"tickets": {}}) if os.path.exists(path) else {"tickets": {}}


def all_findings(findings):
    """Yield (area, slug, surface, finding)."""
    for area, data in findings.items():
        for slug, surf in (data.get("surfaces") or {}).items():
            for f in surf.get("findings", []):
                yield area, slug, surf, f


def is_counted(finding):
    """A finding counts once: duplicates of another finding are shown but not counted."""
    return not finding.get("dup_of")


def needs_ticket(finding):
    """A and E findings that nobody else already owns raise work in this audit's fix tickets."""
    return finding.get("class") in ("A", "E") and is_counted(finding) and not finding.get("owned_by")


def ticket_group(area, finding):
    if finding.get("scope") == "shared":
        return "chrome" if finding.get("component") in CHROME_COMPONENTS else "components"
    return TICKET_GROUP.get(area, area)


def check(catalogue, findings, tickets=None, require_tickets=False):
    """Return a list of problems. An empty list is a complete audit."""
    problems = []
    seen_ids = {}
    owners = collections.defaultdict(list)
    for area, data in findings.items():
        for slug in (data.get("surfaces") or {}):
            owners[slug].append(area)
    for slug in catalogue:
        if not owners.get(slug):
            problems.append("%s: no audit entry in any findings file" % slug)
        elif len(owners[slug]) > 1:
            problems.append("%s: audited by more than one area (%s)" % (slug, ", ".join(owners[slug])))
    if not owners.get(SHARED_SURFACE):
        problems.append("%s: the shared chrome (nav, footer, buttons, tokens) has no audit entry" % SHARED_SURFACE)
    for slug in owners:
        if slug not in catalogue and slug != SHARED_SURFACE:
            problems.append("%s: not a catalogued surface" % slug)

    for area, slug, surf, f in all_findings(findings):
        where = "%s/%s" % (slug, f.get("id", "?"))
        fid = f.get("id")
        if not fid:
            problems.append("%s: finding has no id" % where)
        elif fid in seen_ids:
            problems.append("%s: duplicate finding id (also in %s)" % (fid, seen_ids[fid]))
        else:
            seen_ids[fid] = slug
        cls = f.get("class")
        if cls not in CLASSES:
            problems.append("%s: class %r is not one of A-E" % (where, cls))
            continue
        if f.get("severity") not in SEVERITIES:
            problems.append("%s: severity %r is not high/medium/low" % (where, f.get("severity")))
        for key in ("title", "figma", "build", "evidence"):
            if not str(f.get(key) or "").strip():
                problems.append("%s: empty %s" % (where, key))
        if cls in ("A", "E") and not str(f.get("fix") or "").strip():
            problems.append("%s: class %s needs a fix" % (where, cls))
        if cls == "B" and not str(f.get("source") or "").strip():
            problems.append("%s: class B needs a citable source (no source means it is A, not B)" % where)
        if cls in ("C", "D") and not str(f.get("decision") or "").strip():
            problems.append("%s: class %s needs the decision/question for the owner or Uma" % (where, cls))
        if f.get("scope") not in ("page", "shared"):
            problems.append("%s: scope %r is not page/shared" % (where, f.get("scope")))
        if f.get("scope") == "shared" and f.get("component") not in COMPONENTS:
            problems.append("%s: shared finding needs component in %s" % (where, "/".join(COMPONENTS)))
        if area == "shared-chrome" and f.get("scope") != "shared":
            problems.append("%s: every shared-chrome finding must have scope shared" % where)

    dup_targets = {f.get("id"): f for _a, _s, _sf, f in all_findings(findings)}
    for _area, slug, _surf, f in all_findings(findings):
        where = "%s/%s" % (slug, f.get("id", "?"))
        target = f.get("dup_of")
        if target:
            if target == f.get("id"):
                problems.append("%s: dup_of names itself" % where)
            elif target not in dup_targets:
                problems.append("%s: dup_of %r is not a finding" % (where, target))
            elif dup_targets[target].get("dup_of"):
                problems.append("%s: dup_of %r is itself a duplicate (point at the canonical finding)" % (where, target))
        owner = f.get("owned_by")
        if owner and not TICKET_RE.match(str(owner)):
            problems.append("%s: owned_by %r is not a ClickUp id" % (where, owner))

    for area, data in findings.items():
        for slug, surf in (data.get("surfaces") or {}).items():
            cat = catalogue.get(slug)
            fl = surf.get("findings", [])
            classes = [f.get("class") for f in fl]
            if surf.get("verdict") not in VERDICTS:
                problems.append("%s: verdict %r is not one of %s" % (slug, surf.get("verdict"), "/".join(VERDICTS)))
            if not str(surf.get("summary") or "").strip():
                problems.append("%s: empty summary" % slug)
            if cat is None:
                continue
            if surf.get("node") != cat["node"]:
                problems.append("%s: node %r does not match the catalogue's %r" % (slug, surf.get("node"), cat["node"]))
            status = cat.get("status", "captured")
            verdict = surf.get("verdict")
            if verdict == "matches" and any(c in ("A", "C", "D", "E") for c in classes):
                problems.append("%s: verdict matches but it has %s findings" % (slug, "/".join(sorted(set(c for c in classes if c in 'ACDE')))))
            if verdict == "diverges" and not any(c in ("A", "C", "D", "E") for c in classes):
                problems.append("%s: verdict diverges but every finding is B (a surface with only documented deviations matches)" % slug)
            if verdict == "not-built":
                if status != "unbuilt":
                    problems.append("%s: verdict not-built but the catalogue says status %s" % (slug, status))
                if not fl or any(c != "E" for c in classes):
                    problems.append("%s: a not-built surface needs class E findings and nothing else" % slug)
            elif status == "unbuilt":
                problems.append("%s: the catalogue says unbuilt but the verdict is %s" % (slug, verdict))
            if verdict == "not-rendered-by-design":
                if status != "not-rendered":
                    problems.append("%s: verdict not-rendered-by-design but the catalogue says status %s" % (slug, status))
                if "B" not in classes:
                    problems.append("%s: a not-rendered-by-design surface needs a class B finding citing why" % slug)
            elif status == "not-rendered":
                problems.append("%s: the catalogue says not-rendered but the verdict is %s" % (slug, verdict))

    if tickets is not None:
        known = tickets.get("tickets", {})
        for group, t in known.items():
            if group not in TICKET_GROUPS and group not in ("sign-out-bug", "devices-api"):
                problems.append("tickets.json: unknown group %r" % group)
            if not TICKET_RE.match(str(t.get("id", ""))):
                problems.append("tickets.json: %s has no valid ClickUp id" % group)
        if require_tickets:
            for area, slug, _surf, f in all_findings(findings):
                if needs_ticket(f):
                    g = ticket_group(area, f)
                    if g not in known:
                        problems.append("%s/%s: class %s finding belongs to the %s ticket, which does not exist yet" % (slug, f.get("id"), f["class"], g))
    return problems


def summarise(findings):
    """Counts by ticket group and class (duplicates not counted), a per-class total, A/E severity,
    and how many findings were set aside as duplicates or as owned by another ticket."""
    by_group = {g: collections.Counter() for g in TICKET_GROUPS}
    total = collections.Counter()
    sev = collections.Counter()
    set_aside = collections.Counter()
    for area, _slug, _surf, f in all_findings(findings):
        if not is_counted(f):
            set_aside["duplicates"] += 1
            continue
        g = ticket_group(area, f)
        by_group.setdefault(g, collections.Counter())[f.get("class")] += 1
        total[f.get("class")] += 1
        if f.get("owned_by"):
            set_aside["owned elsewhere"] += 1
        elif f.get("class") in ("A", "E"):
            sev[f.get("severity")] += 1
    return by_group, total, sev, set_aside


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _one_line(text, limit=400):
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def render_report(catalogue, findings, tickets, meta):
    by_group, total, sev, set_aside = summarise(findings)
    L = []
    w = L.append
    w("# Figma fidelity audit — marketing site and account screens\n")
    w("**Ticket:** [%s](%s) · **Date:** %s · **Audited build:** `origin/main` at `%s` · **Figma:** file `%s`, "
      "page *Marketing Website* (`468:124`) and section `743:124`\n" % (
          meta["ticket"], meta["ticket_url"], meta["date"], meta["origin_main"], vp.FIGMA_FILE_KEY))
    w("This file is **generated** by `python3 scripts/check_fidelity_audit.py --write-report` from "
      "`docs/design/visual-parity/marketing/{surfaces.json,findings/*.json,tickets.json}`. Edit the data, not this file. "
      "It records Phase 0 only: nothing was fixed.\n")
    w("## How to read this\n")
    w("Every one of the 16 pages and 19 auth/device states is a Figma frame with a node id. Each was rendered from the built "
      "`dist/` at 1440 wide, compared by picture (`scripts/vp_compare.py`) and by value (`scripts/vp_style_diff.py`: type size, "
      "weight, line height, colour, position, radius, spacing), then every difference was classified:\n")
    for c in CLASSES:
        w("- **%s** — %s" % (c, CLASS_NAMES[c]))
    w("")
    w("Binding owner decisions applied: **honest content wins** over Figma where the repo does not back a claim (layout and styling "
      "are kept, the claim is not shipped; removal from the live pages belongs to ClickUp 17tnw2b0x3h); **accessibility does not "
      "regress** (a Figma colour that fails AA stays accessible in code and is recorded as B); the Figma legacy variables versus "
      "the code `--sc-*` tokens are a **deliberate layer** (AUTH-LANDING-PAGES-HANDOFF 2.2), reported as `colour~`, never as a defect.\n")

    w("## Totals\n")
    w("| area (fix ticket) | A | B | C | D | E | total |\n|---|---|---|---|---|---|---|")
    for g in TICKET_GROUPS:
        c = by_group.get(g, collections.Counter())
        w("| %s | %d | %d | %d | %d | %d | %d |" % (g, c["A"], c["B"], c["C"], c["D"], c["E"], sum(c.values())))
    w("| **all** | %d | %d | %d | %d | %d | %d |\n" % (total["A"], total["B"], total["C"], total["D"], total["E"], sum(total.values())))
    w("Class A and E findings that raise fix work, by severity: high %d, medium %d, low %d. Set aside and not counted: "
      "%d duplicates (the same defect seen again on another page; each names its canonical finding) and %d findings "
      "already owned by another ticket (they carry `owned_by`).\n" % (
          sev["high"], sev["medium"], sev["low"], set_aside["duplicates"], set_aside["owned elsewhere"]))

    if tickets.get("tickets"):
        w("## Fix tickets raised from this audit\n")
        for g, t in tickets["tickets"].items():
            w("- **%s** — [%s](%s) · branch `%s` · %s%s" % (
                g, t.get("id"), t.get("url", ""), t.get("branch", ""), _one_line(t.get("title", ""), 120),
                (" · depends on: " + ", ".join(t.get("depends_on", []))) if t.get("depends_on") else ""))
            if t.get("footprint"):
                w("  - footprint: %s" % t["footprint"])
            if t.get("parallel"):
                w("  - parallel: %s" % t["parallel"])
        w("")

    def group_list(cls, heading, hint):
        items = [(a, s, f) for a, s, _sf, f in all_findings(findings) if f.get("class") == cls and is_counted(f)]
        w("## %s\n" % heading)
        w(hint + "\n")
        if not items:
            w("_None._\n")
            return
        for a, s, f in items:
            w("- **%s** `%s` (%s) — %s" % (f["id"], s, f.get("severity"), f["title"]))
            w("  - Figma: %s" % _one_line(f["figma"], 300))
            w("  - Build: %s" % _one_line(f["build"], 300))
            w("  - Decision needed: %s%s" % (_one_line(f.get("decision"), 400),
                                              (" · owned by " + f["link"]) if f.get("link") else ""))
        w("")

    group_list("C", "Class C — Figma content the repo does not back (for Uma and the owner)",
               "Keep Figma's layout and styling; ship no invented claim. Where the build already carries the claim, removal is "
               "[17tnw2b0x3h](https://app.clickup.com/t/17tnw2b0x3h)'s work, not a fix ticket from this audit.")
    group_list("D", "Class D — Figma gaps (for Uma)",
               "Things Figma does not draw (a state, a page, or an element the build has that no frame shows). Not invented here.")

    a11y = [(a, s, f) for a, s, _sf, f in all_findings(findings) if f.get("a11y") and is_counted(f)]
    w("## Accessibility findings\n")
    if a11y:
        for a, s, f in a11y:
            w("- **%s** `%s` class %s (%s) — %s: %s" % (f["id"], s, f["class"], f.get("severity"), f["title"], _one_line(f["build"], 260)))
    else:
        w("_None flagged._")
    w("")

    api = []
    bugs = []
    for area, data in findings.items():
        api += [dict(x, area=area) for x in data.get("api_gaps", [])]
        bugs += [dict(x, area=area) for x in data.get("bugs", [])]
    if api:
        w("## Devices API check (for the backend ticket)\n")
        for x in api:
            w("- **%s** %s — `%s`: %s (evidence: %s; owner: %s)" % (x.get("id"), x.get("need"), x.get("status"), "", x.get("evidence"), x.get("owner")))
        w("")
    if bugs:
        w("## Defects found that are not fidelity items\n")
        for x in bugs:
            w("- **%s** %s — %s (evidence: %s). Fix: %s" % (x.get("id"), x.get("title"), "", x.get("evidence"), x.get("fix")))
        w("")

    w("## Surfaces\n")
    order = list(catalogue)
    area_of = {}
    for area, data in findings.items():
        for slug in data.get("surfaces", {}):
            area_of[slug] = area
    for slug in [SHARED_SURFACE] + order:
        area = area_of.get(slug)
        if area is None:
            continue
        surf = findings[area]["surfaces"][slug]
        cat = catalogue.get(slug, {})
        w("### %s — `%s` (Figma `%s`)\n" % (cat.get("label") or slug, slug, surf.get("node", "")))
        w("Verdict: **%s** · area: %s · route: `%s`\n" % (surf["verdict"], area, cat.get("path", "—")))
        w(_one_line(surf.get("summary"), 700) + "\n")
        for f in surf.get("findings", []):
            tk = f.get("ticket")
            if f.get("dup_of"):
                w("- **%s** · class %s · duplicate of **%s** — %s" % (f["id"], f["class"], f["dup_of"], f["title"]))
                continue
            w("- **%s** · class **%s** · %s · %s%s%s — %s" % (
                f["id"], f["class"], f.get("severity"), f.get("scope"),
                (" · " + f["component"]) if f.get("component") else "",
                " · a11y" if f.get("a11y") else "", f["title"]))
            w("  - Figma: %s" % _one_line(f["figma"], 500))
            w("  - Build: %s" % _one_line(f["build"], 500))
            w("  - Evidence: %s" % _one_line(f["evidence"], 300))
            if f.get("fix"):
                w("  - Fix: %s" % _one_line(f["fix"], 600))
            if f.get("source"):
                w("  - Source: %s" % _one_line(f["source"], 300))
            if f.get("decision"):
                w("  - Decision: %s" % _one_line(f["decision"], 400))
            if f.get("owned_by"):
                w("  - Already owned by ClickUp %s: no fix ticket from this audit." % f["owned_by"])
            if f.get("link") or tk:
                w("  - Linked: %s" % ", ".join(x for x in (f.get("link"), tk) if x))
        if not surf.get("findings"):
            w("_No differences recorded._")
        w("")

    w("## How to re-run\n")
    w("```bash\n(cd implementation/marketing && npm ci && npm run build)\n"
      "python3 scripts/visual_parity.py --suite marketing            # capture all 35 surfaces from dist/ and compare\n"
      "python3 scripts/vp_style_diff.py --slug home --dom .visual-parity/run-*/marketing/home.blink.dom.json --limit 0\n"
      "python3 scripts/vp_slice.py --slug home --run .visual-parity/run-<stamp> --y 0 --h 900 --out /tmp/home-0.png\n"
      "python3 scripts/vp_reference.py --suite marketing verify      # 35 references + style dumps, caps, checksums\n"
      "python3 scripts/vp_selftest.py                                # prove the harness itself still bites\n"
      "python3 scripts/check_fidelity_audit.py                        # this audit's structure\n```\n")
    w("## What this audit does not show\n")
    w("- Only 1440 wide; mobile and tablet layouts belong to ClickUp 17tnw2b0q9g.\n"
      "- Only the states the capture can drive (the account API is scripted); hover, focus rings, and real-API behaviour are read from source, not photographed.\n"
      "- Chromium rendering; Safari/WebKit and real devices are not evidenced (the harness can capture WebKit with `--engine both`).\n"
      "- Figma's own text metrics (Inter) can differ from the web font by a pixel or two: differences under 3px are not reported.\n"
      "- A low similarity score points at where to look; the classification in the findings is the verdict.\n")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Self-test: the checker must reject every kind of bad input, and accept a good one
# ---------------------------------------------------------------------------


def _good():
    cat = {
        "page": {"slug": "page", "node": "1:1", "kind": "page", "path": "/"},
        "gone": {"slug": "gone", "node": "1:2", "kind": "state", "path": "/x", "status": "unbuilt"},
        "skip": {"slug": "skip", "node": "1:3", "kind": "state", "path": "/y", "status": "not-rendered"},
    }

    def fnd(i, cls, **kw):
        base = {"id": i, "class": cls, "scope": "page", "component": None, "severity": "medium", "title": "t",
                "figma": "f", "build": "b", "evidence": "e", "fix": None, "source": None, "decision": None,
                "a11y": False, "link": None}
        base.update(kw)
        return base

    findings = {
        "home": {"area": "home", "surfaces": {
            "page": {"node": "1:1", "verdict": "diverges", "summary": "s", "findings": [
                fnd("page-01", "A", fix="do it"), fnd("page-02", "B", source="doc 2.2"),
                fnd("page-03", "C", decision="ask owner"), fnd("page-04", "D", decision="ask uma")]},
            "gone": {"node": "1:2", "verdict": "not-built", "summary": "s", "findings": [fnd("gone-01", "E", fix="build")]},
            "skip": {"node": "1:3", "verdict": "not-rendered-by-design", "summary": "s",
                     "findings": [fnd("skip-01", "B", source="handoff 5.5")]},
        }},
        "shared-chrome": {"area": "shared-chrome", "surfaces": {
            SHARED_SURFACE: {"node": "x", "verdict": "diverges", "summary": "s", "findings": [
                fnd("chrome-01", "A", scope="shared", component="nav", fix="fix nav")]}}},
    }
    return cat, findings


def good_total_a(findings):
    return sum(1 for _a, _s, _sf, f in all_findings(findings) if f.get("class") == "A")


def self_test():
    results = []

    def ok(passed, msg):
        results.append(bool(passed))
        print(("PASS: " if passed else "FAIL: ") + msg)

    cat, good = _good()
    ok(check(cat, good) == [], "checker: a complete synthetic audit has no problems")

    def breaks(label, mutate, expect):
        cat2, f2 = copy.deepcopy(cat), copy.deepcopy(good)
        mutate(cat2, f2)
        got = check(cat2, f2)
        ok(any(expect in p for p in got), "checker rejects %s (looking for %r in %d problem(s))" % (label, expect, len(got)))

    breaks("a surface with no entry", lambda c, f: f["home"]["surfaces"].pop("page"), "no audit entry")
    breaks("a missing shared-chrome entry", lambda c, f: f.pop("shared-chrome"), "shared chrome")
    breaks("a wrong node id", lambda c, f: f["home"]["surfaces"]["page"].update(node="9:9"), "does not match the catalogue")
    breaks("a class outside A-E", lambda c, f: f["home"]["surfaces"]["page"]["findings"][0].update({"class": "F"}), "not one of A-E")
    breaks("a class A with no fix", lambda c, f: f["home"]["surfaces"]["page"]["findings"][0].update(fix=""), "needs a fix")
    breaks("a class B with no source", lambda c, f: f["home"]["surfaces"]["page"]["findings"][1].update(source=None), "citable source")
    breaks("a class C with no decision", lambda c, f: f["home"]["surfaces"]["page"]["findings"][2].update(decision=""), "decision/question")
    breaks("a duplicate id", lambda c, f: f["home"]["surfaces"]["page"]["findings"][1].update(id="page-01"), "duplicate finding id")
    breaks("a shared finding with no component", lambda c, f: f["shared-chrome"]["surfaces"][SHARED_SURFACE]["findings"][0].update(component=None), "needs component")
    breaks("a bad severity", lambda c, f: f["home"]["surfaces"]["page"]["findings"][0].update(severity="urgent"), "severity")
    breaks("an unknown verdict", lambda c, f: f["home"]["surfaces"]["page"].update(verdict="fine"), "verdict")
    breaks("`matches` with an A finding", lambda c, f: f["home"]["surfaces"]["page"].update(verdict="matches"), "verdict matches")
    breaks("`diverges` with only B findings", lambda c, f: f["home"]["surfaces"]["page"].update(findings=[f["home"]["surfaces"]["page"]["findings"][1]]), "every finding is B")
    breaks("not-built for a surface the catalogue says is built", lambda c, f: c["gone"].pop("status"), "not-built but the catalogue")
    breaks("a not-built surface with a non-E finding", lambda c, f: f["home"]["surfaces"]["gone"]["findings"].append(
        dict(f["home"]["surfaces"]["page"]["findings"][0], id="gone-02")), "class E findings and nothing else")
    breaks("an unbuilt catalogue entry judged as built", lambda c, f: f["home"]["surfaces"]["gone"].update(verdict="diverges"), "catalogue says unbuilt")
    breaks("a not-rendered surface with no B", lambda c, f: f["home"]["surfaces"]["skip"]["findings"].clear(), "needs a class B")
    breaks("a surface judged by two areas", lambda c, f: f.setdefault("other", {"area": "other", "surfaces": {}})["surfaces"].update(
        page=copy.deepcopy(f["home"]["surfaces"]["page"])), "more than one area")
    breaks("an unknown surface", lambda c, f: f["home"]["surfaces"].update(ghost={"node": "0:0", "verdict": "matches", "summary": "s", "findings": []}), "not a catalogued surface")

    def dup(target, base="chrome-01"):
        def m(c, f):
            f["home"]["surfaces"]["page"]["findings"][0]["dup_of"] = target
        return m

    breaks("a dup_of that names a missing finding", dup("nope-99"), "is not a finding")
    breaks("a dup_of that names itself", dup("page-01"), "names itself")
    breaks("a dup_of that points at another duplicate", lambda c, f: (
        f["home"]["surfaces"]["page"]["findings"][0].update(dup_of="chrome-01"),
        f["shared-chrome"]["surfaces"][SHARED_SURFACE]["findings"][0].update(dup_of="page-02")), "itself a duplicate")
    breaks("an owned_by that is not a ClickUp id", lambda c, f: f["home"]["surfaces"]["page"]["findings"][0].update(owned_by="!!"), "owned_by")
    dupd = copy.deepcopy(good)
    dupd["home"]["surfaces"]["page"]["findings"][0]["dup_of"] = "chrome-01"
    ok(check(cat, dupd) == [], "checker: a valid dup_of is accepted")
    _g, dup_total, _s, aside = summarise(dupd)
    ok(dup_total["A"] == good_total_a(good) - 1 and aside["duplicates"] == 1,
       "summary: a duplicate is set aside, not counted (A %d, set aside %d)" % (dup_total["A"], aside["duplicates"]))
    no_home = {"tickets": {g: {"id": "86abc1234"} for g in TICKET_GROUPS if g != "home"}}
    owned = copy.deepcopy(good)
    owned["home"]["surfaces"]["page"]["findings"][0]["owned_by"] = "17tnw2b0x3h"
    got = check(cat, owned, tickets=no_home, require_tickets=True)
    ok(len(got) == 1 and "gone-01" in got[0],
       "checker: owning the A elsewhere removes ITS ticket requirement, but the E in the same area still needs the home ticket")
    owned["home"]["surfaces"]["gone"]["findings"][0]["owned_by"] = "17tnw2b0x3h"
    ok(check(cat, owned, tickets=no_home, require_tickets=True) == [],
       "checker: once nothing in an area raises work, that area needs no ticket")
    cat2, f2 = copy.deepcopy(cat), copy.deepcopy(good)
    ok(any("does not exist yet" in p for p in check(cat2, f2, tickets={"tickets": {}}, require_tickets=True)),
       "checker: --require-tickets fails while an A/E finding has no ticket for its area")
    full = {"tickets": {g: {"id": "86abc1234"} for g in TICKET_GROUPS}}
    ok(check(cat2, f2, tickets=full, require_tickets=True) == [], "checker: --require-tickets passes once every area has its ticket")
    ok(any("no valid ClickUp id" in p for p in check(cat2, f2, tickets={"tickets": {"home": {"id": "!!"}}})),
       "checker: a ticket with a malformed id is rejected")

    by_group, total, _sev, _aside = summarise(good)
    ok(total["A"] == 2 and by_group["chrome"]["A"] == 1 and by_group["home"]["A"] == 1,
       "summary: shared-scope findings count toward the chrome ticket (A: %d, chrome A: %d)" % (total["A"], by_group["chrome"]["A"]))
    text = render_report(cat, good, {"tickets": {}}, {"ticket": "X", "ticket_url": "u", "date": "d", "origin_main": "sha"})
    ok("Class C" in text and "ask owner" in text and "page-01" in text and "## Surfaces" in text,
       "report: the generated report carries the C list, the finding text and every surface")

    # round-trip through files, as the real run does
    root = tempfile.mkdtemp(prefix="fa-")
    try:
        os.makedirs(os.path.join(root, "findings"))
        with open(os.path.join(root, "findings", "home.json"), "w") as fh:
            json.dump(good["home"], fh)
        loaded = load_findings(os.path.join(root, "findings"))
        ok(set(loaded) == {"home"} and check(cat, {**loaded, "shared-chrome": good["shared-chrome"]}) == [],
           "loader: findings files round-trip through disk and still check clean")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    bad = [m for m in results if not m]
    print("\n=== check_fidelity_audit self-test: %d checks, %d FAIL ===" % (len(results), len(bad)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--require-tickets", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--write-report", default=None)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--ticket", default="17tnw2b2c75")
    ap.add_argument("--origin-main", default="3fb96da8")
    ap.add_argument("--date", default="2026-10-03")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    catalogue = load_catalogue()
    findings = load_findings()
    tickets = load_tickets()
    problems = check(catalogue, findings, tickets, require_tickets=args.require_tickets)
    by_group, total, sev, set_aside = summarise(findings)
    if args.summary or not problems:
        print("surfaces catalogued: %d · findings files: %d" % (len(catalogue), len(findings)))
        for g in TICKET_GROUPS:
            c = by_group.get(g, collections.Counter())
            print("  %-10s A=%-3d B=%-3d C=%-3d D=%-3d E=%-3d" % (g, c["A"], c["B"], c["C"], c["D"], c["E"]))
        print("  %-10s A=%-3d B=%-3d C=%-3d D=%-3d E=%-3d   (A/E severity: %s)" % (
            "all", total["A"], total["B"], total["C"], total["D"], total["E"], dict(sev)))
    for p in problems:
        print("FAIL: " + p)
    if args.write_report and not problems:
        meta = {"ticket": args.ticket, "ticket_url": "https://app.clickup.com/t/" + args.ticket,
                "date": args.date, "origin_main": args.origin_main}
        os.makedirs(os.path.dirname(os.path.abspath(args.write_report)), exist_ok=True)
        with open(args.write_report, "w", encoding="utf-8") as fh:
            fh.write(render_report(catalogue, findings, tickets, meta))
        print("wrote " + args.write_report)
    print("=== fidelity audit: %d problem(s) ===" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
