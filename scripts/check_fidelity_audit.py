#!/usr/bin/env python3
"""Checker, summariser and report writer for the Figma fidelity audit: it checks MEANING, not only shape.

The audit's source of truth is data, not prose:

    docs/design/visual-parity/marketing/surfaces.json   the 35 Figma frames (16 pages, 19 states)
    docs/design/visual-parity/marketing/findings/*.json one file per audit area, every difference
    docs/design/visual-parity/marketing/tickets.json    area -> the fix ticket raised from it

and the human report (`docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md`) is
GENERATED from them, so the report cannot say something the data does not.

    python3 scripts/check_fidelity_audit.py                  # check; exit 0 only if the audit is complete
    python3 scripts/check_fidelity_audit.py --require-tickets # also: every A/E finding names ITS group's ticket
    python3 scripts/check_fidelity_audit.py --check-report   # the committed report equals what the data generates
    python3 scripts/check_fidelity_audit.py --summary        # counts by class and area
    python3 scripts/check_fidelity_audit.py --write-report PATH
    python3 scripts/check_fidelity_audit.py --self-test      # prove the checker rejects each kind of bad input

What "complete" means (every rule below is one the self-test breaks on purpose):
  * the catalogue is exactly the 35 Figma frames (16 pages, 19 states) this checker knows by node id: deleting a
    surface from surfaces.json cannot make the audit smaller and still pass; every one has exactly one entry;
  * every finding is classified A to E and carries what its class requires, with minimum substance: A and E a fix,
    B a source that RESOLVES (a document that exists under docs/, a file that exists, a DEC id in the decision log,
    a commit that exists, a ClickUp id or PR number, or a contrast measurement that recomputes), C and D a question;
  * `matches` surfaces have no A/C/D/E finding; `not-built` surfaces are the catalogue's unbuilt ones and carry
    only E findings; `not-rendered-by-design` ones carry a B finding;
  * ids are unique; a shared finding names its component; a duplicate (`dup_of`) points at a canonical finding of
    the SAME class in the same area or a shared one; `owned_by` is only for a class A, only a known ticket (the
    allowlist), and only a handful;
  * the per-finding `ticket` is a known ticket and, under --require-tickets, the ticket of the finding's own group;
    a ticket's `url` is exactly https://app.clickup.com/t/<its own id> (it becomes an href on the artifact page);
  * every findings file states the commit it audited and the date, they agree, and the commit exists;
  * `bugs` and `api_gaps` entries are complete and routed to a ticket group.

Bounded: reads a few JSON files (each capped at MAX_BYTES), prints at most the report.
"""

from __future__ import annotations

import argparse
import collections
import copy
import functools
import json
import os
import re
import shutil
import subprocess
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
BUG_GROUPS = TICKET_GROUPS + ("sign-out-bug",)
API_STATUSES = ("exists", "partial", "missing")
TICKET_RE = re.compile(r"^[0-9a-z]{8,12}$")
CLICKUP_TASK_URL = "https://app.clickup.com/t/"


def safe_ticket_url(ticket):
    """The ticket's URL if it is EXACTLY `https://app.clickup.com/t/<its own id>`, else None.

    A ticket's `url` becomes an `href` on the artifact page. HTML-escaping does not stop a `javascript:` URL,
    so the only URL ever linked is the one ClickUp's own task link takes for this ticket.
    """
    tid, url = str((ticket or {}).get("id", "")), (ticket or {}).get("url")
    if TICKET_RE.match(tid) and url == CLICKUP_TASK_URL + tid:
        return url
    return None


# The 35 Figma frames the audit covers (16 pages on page 468:124, 19 states in section 743:124), held HERE as well
# as in surfaces.json: the checker compares the two, so deleting a surface from the catalogue cannot shrink the
# audit and still pass.
EXPECTED_SURFACES = {
    "home": ("468:125", "page"),
    "pricing": ("483:124", "page"),
    "features": ("485:124", "page"),
    "download": ("487:124", "page"),
    "about": ("496:124", "page"),
    "contact": ("497:124", "page"),
    "support": ("498:124", "page"),
    "docs": ("499:124", "page"),
    "changelog": ("501:124", "page"),
    "blog": ("502:124", "page"),
    "careers": ("503:124", "page"),
    "privacy": ("504:124", "page"),
    "terms": ("504:203", "page"),
    "signin": ("505:124", "page"),
    "account": ("506:124", "page"),
    "affiliates": ("541:124", "page"),
    "verify-v1": ("743:125", "state"),
    "verify-v2": ("743:139", "state"),
    "verify-v3": ("746:124", "state"),
    "verify-v4": ("746:148", "state"),
    "verify-v5": ("746:172", "state"),
    "verify-v6": ("747:124", "state"),
    "reset-r1": ("747:143", "state"),
    "reset-r2": ("747:173", "state"),
    "reset-r3": ("749:124", "state"),
    "reset-r4": ("749:150", "state"),
    "reset-r5": ("749:174", "state"),
    "reset-r6": ("749:198", "state"),
    "reset-r7": ("749:217", "state"),
    "devices-d1": ("753:124", "state"),
    "devices-d2": ("754:124", "state"),
    "devices-d3": ("754:257", "state"),
    "devices-d4": ("755:124", "state"),
    "devices-d5": ("755:256", "state"),
    "devices-d6": ("755:385", "state"),
}
# ClickUp tickets that legitimately already own a class A difference (`owned_by`). Anything else is a typo or an
# exemption nobody approved.
OWNER_TICKETS = {"17tnw2b0x3h", "17tnw2b0x3g", "17tnw2b0q9g", "17tnw2b0q9h", "17tnw2b0q9j"}
MAX_OWNED_BY = 10
# ALL-CAPS 3-part tokens that appear in citations but are not document names.
NOT_DOCUMENT_TOKENS = {"YYYY-MM-DD"}
# Minimum substance. "x" and "ok" satisfy "not empty"; these do not. The shortest honest values in the data are
# "Absent." (7) for a build field and a 34-character fix.
MIN_TITLE, MIN_FIELD, MIN_EVIDENCE, MIN_FIX, MIN_DECISION = 12, 7, 20, 25, 40


def _repo_root(repo=None):
    return repo or vp.REPO


@functools.lru_cache(maxsize=4)
def _doc_stems(repo):
    """{document stem: path} for every .md under docs/ (a citation like AUTH-LANDING-PAGES-HANDOFF must be one of them)."""
    out = {}
    for dirpath, _dirs, files in os.walk(os.path.join(repo, "docs")):
        for fn in files:
            if fn.endswith(".md"):
                out[fn[:-3]] = os.path.join(dirpath, fn)
    return out


@functools.lru_cache(maxsize=4)
def _basenames(repo):
    """Every file basename under docs/, scripts/ and implementation/marketing (a bare `DownloadView.vue` must exist)."""
    names = set()
    for top in ("docs", "scripts", os.path.join("implementation", "marketing")):
        for dirpath, dirs, files in os.walk(os.path.join(repo, top)):
            dirs[:] = [d for d in dirs if d not in ("node_modules", "dist", ".git")]
            names.update(files)
    return names


@functools.lru_cache(maxsize=4)
def _decision_ids(repo):
    path = os.path.join(repo, "docs", "decisions", "DECISION-LOG.md")
    if not os.path.exists(path):
        return frozenset()
    with open(path, "r", encoding="utf-8") as fh:
        return frozenset(re.findall(r"^#+\s*(DEC-\d+)", fh.read(), re.M))


def _commit_exists(sha, repo):
    try:
        out = subprocess.run(["git", "-C", repo, "cat-file", "-t", sha], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None  # git unavailable: cannot tell, do not claim
    return out.returncode == 0 and out.stdout.strip() == "commit"


def _contrast(fg_hex, bg_hex):
    return vp.contrast_ratio(tuple(int(fg_hex[i:i + 2], 16) for i in (0, 2, 4)),
                             tuple(int(bg_hex[i:i + 2], 16) for i in (0, 2, 4)))


def source_problems(source, repo=None):
    """Why a class B `source` does not count as a citation: a list of sentences, empty when it resolves.

    A B finding says "this difference is documented and deliberate". That is only true if the document
    exists and the claim in it can be found, so the source must contain at least ONE citation that resolves
    and NONE that does not:
      * a document name (AUTH-LANDING-PAGES-HANDOFF, LEGAL-DRAFT-NOTES ...) that is a .md under docs/;
      * a file path or file name (src/views/DownloadView.vue, README.md) that exists; a `:12-30` suffix is ignored;
      * a DEC-nnn id that is a heading in docs/decisions/DECISION-LOG.md;
      * `commit <sha>` that exists in this repository;
      * a ClickUp id, or `PR #n` (format only: they cannot be resolved offline);
      * `Measurement:` with a contrast ratio, recomputed whenever the source names both hex colours.
    """
    repo = _repo_root(repo)
    text = source or ""
    resolved, problems = 0, []
    stems = _doc_stems(repo)
    # Any ALL-CAPS name with 3+ parts (AUTH-LANDING-PAGES-HANDOFF, LEGAL-DRAFT-NOTES) is read as a document name,
    # so a typo like AUTH-LANDING-PAGES-HANDOFFF is reported rather than silently ignored.
    for tok in sorted(set(re.findall(r"\b[A-Z][A-Z0-9]+(?:-[A-Z0-9]+){2,}\b", text))):
        if tok in NOT_DOCUMENT_TOKENS:
            continue
        if tok in stems:
            resolved += 1
        else:
            problems.append("cites %s, which is not a document under docs/" % tok)
    for tok in sorted(set(re.findall(r"\b[\w./-]+\.(?:md|vue|ts|py|css|rs|json)\b", text))):
        base = os.path.basename(tok)
        if "/" in tok:
            exists = any(os.path.exists(os.path.join(repo, *prefix, tok)) for prefix in
                         ((), ("implementation", "marketing"), ("docs",), ("implementation", "marketing", "src")))
        else:
            exists = base in _basenames(repo)
        if exists:
            resolved += 1
        else:
            problems.append("cites the file %s, which does not exist" % tok)
    for dec in sorted(set(re.findall(r"\bDEC-\d+\b", text))):
        if dec in _decision_ids(repo):
            resolved += 1
        else:
            problems.append("cites %s, which is not in docs/decisions/DECISION-LOG.md" % dec)
    for sha in sorted(set(re.findall(r"\bcommit\s+([0-9a-f]{7,40})\b", text))):
        found = _commit_exists(sha, repo)
        if found:
            resolved += 1
        elif found is False:
            problems.append("cites commit %s, which is not in this repository" % sha)
    if re.search(r"\b(?:17tnw[0-9a-z]{6}|86[0-9a-z]{6,8})\b", text) or re.search(r"\bPR\s*#\d{2,5}\b", text):
        resolved += 1
    if re.search(r"Measurement:", text):
        pairs = re.findall(r"#([0-9a-fA-F]{6}) on #([0-9a-fA-F]{6}) is (\d+(?:\.\d+)?):1", text)
        if pairs:
            for fg, bg, claimed in pairs:
                actual = _contrast(fg, bg)
                if abs(actual - float(claimed)) > 0.06:
                    problems.append("measurement says #%s on #%s is %s:1 but it recomputes to %.2f:1" % (fg, bg, claimed, actual))
                else:
                    resolved += 1
        elif re.search(r"\d+\.\d+:1", text):
            resolved += 1
    if resolved == 0 and not problems:
        problems.append("cites nothing that resolves (a document, a file, DEC-nnn, a commit, a ClickUp id, a PR or a measurement)")
    return problems


def audit_meta(findings):
    """(meta, problems): the commit and date the findings say they audited. They must agree across the files."""
    origins = sorted({str(d.get("origin_main") or "") for d in findings.values()})
    dates = sorted({str(d.get("audited_utc") or "") for d in findings.values()})
    problems = []
    if "" in origins or len(origins) != 1:
        problems.append("findings files disagree about, or omit, origin_main: %s" % origins)
    if "" in dates or len(dates) != 1:
        problems.append("findings files disagree about, or omit, audited_utc: %s" % dates)
    meta = {"ticket": "17tnw2b2c75", "ticket_url": CLICKUP_TASK_URL + "17tnw2b2c75",
            "date": dates[0] if dates else "", "origin_main": origins[0] if origins else ""}
    return meta, problems


def meta_problems(findings, repo=None):
    """Problems with the audited-commit metadata, including that the commit exists in this repository."""
    meta, problems = audit_meta(findings)
    repo = _repo_root(repo)
    sha = meta["origin_main"]
    if sha and not problems:
        found = _commit_exists(sha, repo)
        if found is False:
            problems.append("origin_main %s is not a commit in this repository" % sha)
    return problems


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


def _short(text, minimum):
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    return len(t) < minimum or len(set(t)) < 3


def check(catalogue, findings, tickets=None, require_tickets=False, expected_surfaces=None, repo=None):
    """Return a list of problems. An empty list is a complete audit.

    `expected_surfaces` (the real run passes EXPECTED_SURFACES) is what makes deleting a surface from the
    catalogue a failure; the synthetic data in the self-test passes None.
    """
    problems = []
    seen_ids = {}
    owners = collections.defaultdict(list)
    area_of_slug = {}
    for area, data in findings.items():
        for slug in (data.get("surfaces") or {}):
            owners[slug].append(area)
            area_of_slug[slug] = area
    if expected_surfaces is not None:
        for slug, (node, kind) in expected_surfaces.items():
            got = catalogue.get(slug)
            if got is None:
                problems.append("%s: the catalogue is missing this Figma frame (%s); the audit covers all %d" % (slug, node, len(expected_surfaces)))
            elif got.get("node") != node or got.get("kind") != kind:
                problems.append("%s: the catalogue says node %s/%s but the Figma frame is %s/%s" % (
                    slug, got.get("node"), got.get("kind"), node, kind))
        for slug in catalogue:
            if slug not in expected_surfaces:
                problems.append("%s: not one of the %d known Figma frames" % (slug, len(expected_surfaces)))
        pages = sum(1 for v in expected_surfaces.values() if v[1] == "page")
        states = sum(1 for v in expected_surfaces.values() if v[1] == "state")
        if (pages, states) != (16, 19):
            problems.append("the checker's own table holds %d pages and %d states, not 16 and 19" % (pages, states))
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

    known_ids = {str(t.get("id")): g for g, t in (tickets or {}).get("tickets", {}).items()}
    by_id = {}
    for area, slug, surf, f in all_findings(findings):
        by_id.setdefault(f.get("id"), (area, slug, f))
    owned_count = 0
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
        for key, minimum in (("title", MIN_TITLE), ("figma", MIN_FIELD), ("build", MIN_FIELD), ("evidence", MIN_EVIDENCE)):
            if not str(f.get(key) or "").strip():
                problems.append("%s: empty %s" % (where, key))
            elif _short(f.get(key), minimum):
                problems.append("%s: %s is too thin to be evidence (under %d characters, or one repeated character)" % (where, key, minimum))
        if cls in ("A", "E"):
            if not str(f.get("fix") or "").strip():
                problems.append("%s: class %s needs a fix" % (where, cls))
            elif _short(f.get("fix"), MIN_FIX):
                problems.append("%s: the fix is too thin to act on (under %d characters)" % (where, MIN_FIX))
        if cls == "B":
            if not str(f.get("source") or "").strip():
                problems.append("%s: class B needs a citable source (no source means it is A, not B)" % where)
            else:
                for why in source_problems(f["source"], repo):
                    problems.append("%s: class B source does not resolve: %s" % (where, why))
        if cls in ("C", "D"):
            if not str(f.get("decision") or "").strip():
                problems.append("%s: class %s needs the decision/question for the owner or Uma" % (where, cls))
            elif _short(f.get("decision"), MIN_DECISION):
                problems.append("%s: the decision is too thin to answer (under %d characters)" % (where, MIN_DECISION))
        if f.get("scope") not in ("page", "shared"):
            problems.append("%s: scope %r is not page/shared" % (where, f.get("scope")))
        if f.get("scope") == "shared" and f.get("component") not in COMPONENTS:
            problems.append("%s: shared finding needs component in %s" % (where, "/".join(COMPONENTS)))
        if area == "shared-chrome" and f.get("scope") != "shared":
            problems.append("%s: every shared-chrome finding must have scope shared" % where)

        target = f.get("dup_of")
        if target:
            if target == fid:
                problems.append("%s: dup_of names itself" % where)
            elif target not in by_id:
                problems.append("%s: dup_of %r is not a finding" % (where, target))
            else:
                t_area, _t_slug, t = by_id[target]
                if t.get("dup_of"):
                    problems.append("%s: dup_of %r is itself a duplicate (point at the canonical finding)" % (where, target))
                if t.get("class") != cls:
                    problems.append("%s: a class %s finding cannot be a duplicate of %s, which is class %s (a duplicate must "
                                    "be the same defect, so the same class)" % (where, cls, target, t.get("class")))
                if t_area != area and t.get("scope") != "shared" and t_area != "shared-chrome":
                    problems.append("%s: dup_of %s is in another area (%s) and is not a shared finding" % (where, target, t_area))
        owner = f.get("owned_by")
        if owner:
            owned_count += 1
            if cls != "A":
                problems.append("%s: owned_by is only for a class A (an A another ticket already owns), not class %s" % (where, cls))
            if owner not in OWNER_TICKETS:
                problems.append("%s: owned_by %r is not a ticket that owns this kind of work (allowed: %s)" % (
                    where, owner, ", ".join(sorted(OWNER_TICKETS))))
        t_ref = f.get("ticket")
        if t_ref and tickets is not None and t_ref not in known_ids:
            problems.append("%s: ticket %r is not one of the tickets in tickets.json" % (where, t_ref))
    if owned_count > MAX_OWNED_BY:
        problems.append("%d findings use owned_by, over the cap of %d: that is an exemption list, not an exception" % (owned_count, MAX_OWNED_BY))

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

        bug_ids = set()
        for b in data.get("bugs", []):
            bwhere = "%s/%s" % (area, b.get("id", "?"))
            if not b.get("id"):
                problems.append("%s: a bug has no id" % area)
            elif b["id"] in bug_ids or b["id"] in seen_ids:
                problems.append("%s: duplicate bug id" % bwhere)
            bug_ids.add(b.get("id"))
            for key, minimum in (("title", MIN_TITLE), ("evidence", MIN_EVIDENCE), ("fix", MIN_FIX)):
                if _short(b.get(key), minimum):
                    problems.append("%s: bug %s is missing or too thin" % (bwhere, key))
            if b.get("group") not in BUG_GROUPS:
                problems.append("%s: bug group %r is not one of %s (a defect must be routed to a ticket)" % (bwhere, b.get("group"), "/".join(BUG_GROUPS)))
            elif require_tickets and tickets is not None:
                want = tickets.get("tickets", {}).get(b["group"], {}).get("id")
                if not want or b.get("ticket") != want:
                    problems.append("%s: bug ticket %r is not the %s ticket (%s)" % (bwhere, b.get("ticket"), b["group"], want))
        for g in data.get("api_gaps", []):
            gwhere = "%s/%s" % (area, g.get("id", "?"))
            if g.get("status") not in API_STATUSES:
                problems.append("%s: api gap status %r is not exists/partial/missing" % (gwhere, g.get("status")))
            for key, minimum in (("need", MIN_FIX), ("evidence", MIN_EVIDENCE)):
                if _short(g.get(key), minimum):
                    problems.append("%s: api gap %s is missing or too thin" % (gwhere, key))

    if tickets is not None:
        known = tickets.get("tickets", {})
        for group, t in known.items():
            if group not in TICKET_GROUPS and group not in ("sign-out-bug", "devices-api", "decisions", "selftest-ci"):
                problems.append("tickets.json: unknown group %r" % group)
            if not TICKET_RE.match(str(t.get("id", ""))):
                problems.append("tickets.json: %s has no valid ClickUp id" % group)
            elif safe_ticket_url(t) is None:
                problems.append("tickets.json: %s url %r must be exactly %s<its own id> (it becomes an href on the artifact page)" % (
                    group, t.get("url"), CLICKUP_TASK_URL))
        if require_tickets:
            for area, slug, _surf, f in all_findings(findings):
                if needs_ticket(f):
                    g = ticket_group(area, f)
                    if g not in known:
                        problems.append("%s/%s: class %s finding belongs to the %s ticket, which does not exist yet" % (slug, f.get("id"), f["class"], g))
                    elif f.get("ticket") != known[g].get("id"):
                        problems.append("%s/%s: a class %s finding must carry the ticket of its group (%s: %s), not %r" % (
                            slug, f.get("id"), f["class"], g, known[g].get("id"), f.get("ticket")))
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
    w("Class A and E findings that raise fix work, by severity: high %d, medium %d, low %d. Not counted anywhere: %d "
      "duplicates (the same defect seen again on another page; each names its canonical finding). Counted in the totals "
      "above but left out of this severity tally because they raise no fix here: %d class A findings that another "
      "ClickUp ticket already owns (they carry `owned_by`).\n" % (
          sev["high"], sev["medium"], sev["low"], set_aside["duplicates"], set_aside["owned elsewhere"]))

    if tickets.get("tickets"):
        w("## Fix tickets raised from this audit\n")
        for g, t in tickets["tickets"].items():
            w("- **%s** — [%s](%s)%s · %s%s" % (
                g, t.get("id"), t.get("url", ""), (" · branch `%s`" % t["branch"]) if t.get("branch") else "",
                _one_line(t.get("title", ""), 120),
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
            w("- **%s** (%s) %s Evidence: %s. Owner: %s." % (x.get("id"), x.get("status"), x.get("need"), _one_line(x.get("evidence"), 500), x.get("owner")))
        w("")
    if bugs:
        w("## Defects found that are not fidelity items\n")
        for x in bugs:
            tk = x.get("ticket")
            w("- **%s** (%s) %s. Evidence: %s. Fix: %s%s" % (
                x.get("id"), x.get("group"), x.get("title"), _one_line(x.get("evidence"), 400), _one_line(x.get("fix"), 400),
                (" Ticket: " + tk + ".") if tk else ""))
        w("")
    w("## Decisions that are not findings\n")
    w("- **How the side-by-side Artifact page is shared: DECIDED, team only (the owner, 2026-10-04).** It is shared with members "
      "of the organisation, not with the public, so an anonymous request returning 403 is the intended state, and the page may "
      "keep every finding's evidence, the devices API-gap table and the bug list (security review finding 2: resolved by "
      "decision). Owner action still open: set sharing from the page's Share menu (the author cannot) and have a team member "
      "open it; until then \"opens for a member of the team who was not in the session\" is not shown.\n")

    w("## Index: every page and state, its Figma node and its verdict\n")
    w("| surface | Figma node | route | verdict | A | B | C | D | E |\n|---|---|---|---|---|---|---|---|---|")
    area_by_slug = {}
    for area, data in findings.items():
        for slug in data.get("surfaces", {}):
            area_by_slug[slug] = area
    for slug, cat in catalogue.items():
        surf = findings[area_by_slug[slug]]["surfaces"][slug] if slug in area_by_slug else None
        cnt = collections.Counter(f["class"] for f in (surf or {}).get("findings", []) if is_counted(f))
        w("| %s (`%s`) | `%s` | `%s` | %s | %d | %d | %d | %d | %d |" % (
            cat.get("label") or slug, slug, cat["node"], cat.get("path", ""), (surf or {}).get("verdict", "—"),
            cnt["A"], cnt["B"], cnt["C"], cnt["D"], cnt["E"]))
    w("")
    w("Counts here are per surface and exclude duplicates. They include findings that are fixed in the shared chrome or shared components "
      "tickets, which is why the per-ticket totals above differ.\n")
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


REPORT_PATH = os.path.join(vp.REPO, "docs", "delivery", "FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md")


def report_drift(catalogue, findings, tickets, path):
    """None when the committed report at `path` equals what the data generates; else a sentence naming the first difference.

    The report is generated, and a finding edited without regenerating it would leave a committed document
    that says something the data no longer does.
    """
    meta, _problems = audit_meta(findings)
    want = render_report(catalogue, findings, tickets, meta)
    if not os.path.exists(path):
        return "the committed report %s does not exist; run --write-report" % path
    with open(path, "r", encoding="utf-8") as fh:
        have = fh.read()
    if have == want:
        return None
    a, b = have.splitlines(), want.splitlines()
    for n, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            return "the committed report differs from the data at line %d (committed %r, generated %r); run --write-report" % (
                n, x[:70], y[:70])
    return "the committed report has %d lines but the data generates %d; run --write-report" % (len(a), len(b))


def _sub(cls, i, **kw):
    base = {"id": i, "class": cls, "scope": "page", "component": None, "severity": "medium",
            "title": "A finding with a usable title", "figma": "What Figma draws here",
            "build": "What the build renders here", "evidence": "python3 scripts/vp_style_diff.py --slug page",
            "fix": None, "source": None, "decision": None, "a11y": False, "link": None}
    base.update(kw)
    return base


def _good():
    cat = {
        "page": {"slug": "page", "node": "1:1", "kind": "page", "path": "/"},
        "gone": {"slug": "gone", "node": "1:2", "kind": "state", "path": "/x", "status": "unbuilt"},
        "skip": {"slug": "skip", "node": "1:3", "kind": "state", "path": "/y", "status": "not-rendered"},
    }
    def fnd(i, cls, **kw):
        return _sub(cls, i, **kw)

    findings = {
        "home": {"area": "home", "origin_main": "3fb96da8", "audited_utc": "2026-10-03", "surfaces": {
            "page": {"node": "1:1", "verdict": "diverges", "summary": "s", "findings": [
                fnd("page-01", "A", fix="Change the heading text to the Figma wording"),
                fnd("page-02", "B", source="AUTH-LANDING-PAGES-HANDOFF 2.2"),
                fnd("page-03", "C", decision="Ask the owner whether this claim is backed by anything"),
                fnd("page-04", "D", decision="Ask Uma to draw the missing state for this surface")]},
            "gone": {"node": "1:2", "verdict": "not-built", "summary": "s", "findings": [
                fnd("gone-01", "E", fix="Build the route and its states from the Figma frame")]},
            "skip": {"node": "1:3", "verdict": "not-rendered-by-design", "summary": "s",
                     "findings": [fnd("skip-01", "B", source="AUTH-LANDING-PAGES-HANDOFF 5.5")]},
        }, "bugs": [{"id": "bug-01", "title": "A defect found on the way", "evidence": "AccountView.vue:136 is a link",
                     "fix": "Call the logout mutation from the button", "group": "home"}],
            "api_gaps": [{"id": "api-01", "need": "List the customer's devices over the session",
                          "status": "missing", "evidence": "account_schema.py exposes only account_viewer", "owner": "Kenji"}]},
        "shared-chrome": {"area": "shared-chrome", "origin_main": "3fb96da8", "audited_utc": "2026-10-03", "surfaces": {
            SHARED_SURFACE: {"node": "x", "verdict": "diverges", "summary": "s", "findings": [
                fnd("chrome-01", "A", scope="shared", component="nav", fix="Make the navbar 79px tall at 1440 wide")]}}},
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
    ok(check(cat, good) == [], "checker: a complete synthetic audit has no problems: %s" % check(cat, good)[:2])

    def breaks(label, mutate, expect, **kw):
        cat2, f2 = copy.deepcopy(cat), copy.deepcopy(good)
        mutate(cat2, f2)
        got = check(cat2, f2, **kw)
        ok(any(expect in p for p in got), "checker rejects %s (looking for %r in %d problem(s))" % (label, expect, len(got)))

    def finding(f, area="home", slug="page", index=0):
        return f[area]["surfaces"][slug]["findings"][index]

    breaks("a surface with no entry", lambda c, f: f["home"]["surfaces"].pop("page"), "no audit entry")
    breaks("a missing shared-chrome entry", lambda c, f: f.pop("shared-chrome"), "shared chrome")
    breaks("a wrong node id", lambda c, f: f["home"]["surfaces"]["page"].update(node="9:9"), "does not match the catalogue")
    breaks("a class outside A-E", lambda c, f: finding(f).update({"class": "F"}), "not one of A-E")
    breaks("a class A with no fix", lambda c, f: finding(f).update(fix=""), "needs a fix")
    breaks("a class B with no source", lambda c, f: finding(f, index=1).update(source=None), "citable source")
    breaks("a class C with no decision", lambda c, f: finding(f, index=2).update(decision=""), "decision/question")
    breaks("a duplicate id", lambda c, f: finding(f, index=1).update(id="page-01"), "duplicate finding id")
    breaks("a shared finding with no component", lambda c, f: finding(f, "shared-chrome", SHARED_SURFACE).update(component=None), "needs component")
    breaks("a bad severity", lambda c, f: finding(f).update(severity="urgent"), "severity")
    breaks("an unknown verdict", lambda c, f: f["home"]["surfaces"]["page"].update(verdict="fine"), "verdict")
    breaks("`matches` with an A finding", lambda c, f: f["home"]["surfaces"]["page"].update(verdict="matches"), "verdict matches")
    breaks("`diverges` with only B findings", lambda c, f: f["home"]["surfaces"]["page"].update(findings=[finding(f, index=1)]), "every finding is B")
    breaks("not-built for a surface the catalogue says is built", lambda c, f: c["gone"].pop("status"), "not-built but the catalogue")
    breaks("a not-built surface with a non-E finding", lambda c, f: f["home"]["surfaces"]["gone"]["findings"].append(
        dict(finding(f), id="gone-02")), "class E findings and nothing else")
    breaks("an unbuilt catalogue entry judged as built", lambda c, f: f["home"]["surfaces"]["gone"].update(verdict="diverges"), "catalogue says unbuilt")
    breaks("a not-rendered surface with no B", lambda c, f: f["home"]["surfaces"]["skip"]["findings"].clear(), "needs a class B")
    breaks("a surface judged by two areas", lambda c, f: f.setdefault("other", {"area": "other", "surfaces": {}})["surfaces"].update(
        page=copy.deepcopy(f["home"]["surfaces"]["page"])), "more than one area")
    breaks("an unknown surface", lambda c, f: f["home"]["surfaces"].update(ghost={"node": "0:0", "verdict": "matches", "summary": "s", "findings": []}), "not a catalogued surface")

    # --- minimum substance
    for key, bad in (("figma", "x"), ("build", "ok"), ("evidence", "see slice"), ("title", "bad one")):
        breaks("a finding whose %s is %r" % (key, bad), lambda c, f, key=key, bad=bad: finding(f).update({key: bad}), "too thin")
    breaks("a one-character repeated build field", lambda c, f: finding(f).update(build="aaaaaaaa"), "too thin")
    breaks("a fix of three words", lambda c, f: finding(f).update(fix="make it match"), "too thin to act on")
    breaks("a decision that is a bare word", lambda c, f: finding(f, index=2).update(decision="ask owner"), "too thin to answer")

    # --- B sources must RESOLVE
    for label, src, expect in (
        ("a B source of 'x'", "x", "cites nothing that resolves"),
        ("a B source with no citation", "the handoff says so, trust us", "cites nothing that resolves"),
        ("a B source citing a document that does not exist", "AUTH-LANDING-PAGES-HANDOFFF 2.2", "not a document under docs/"),
        ("a B source citing a decision that does not exist", "DEC-999 settled this", "not in docs/decisions"),
        ("a B source citing a file that does not exist", "implementation/marketing/src/views/NopeView.vue says so", "does not exist"),
        ("a B source citing a bare file name that does not exist", "NopeView.vue explains it", "does not exist"),
        ("a B source citing a commit that does not exist", "commit 0123456789abcdef0123456789abcdef01234567", "not in this repository"),
        ("a B source with a wrong contrast measurement", "Measurement: #5b6bd6 on #0d0f14 is 9.9:1", "recomputes to"),
    ):
        breaks(label, lambda c, f, src=src: finding(f, index=1).update(source=src), expect)
    for label, src in (
        ("a document name that exists", "AUTH-LANDING-PAGES-HANDOFF 4.4 and 10.2"),
        ("a file that exists", "implementation/marketing/src/views/DownloadView.vue comments"),
        ("a bare file name that exists", "DownloadView.vue comment lines 21-27"),
        ("a decision that exists", "DEC-008 fixed the tiers"),
        ("a real commit", "commit e7566a96 (PR #142)"),
        ("a ClickUp id", "ClickUp 17tnw2b0q9j (honest disabled downloads)"),
        ("a correct measurement", "Measurement: #5b6bd6 on #0d0f14 is 4.12:1 and fails AA"),
    ):
        cat2, f2 = copy.deepcopy(cat), copy.deepcopy(good)
        finding(f2, index=1)["source"] = src
        ok(check(cat2, f2) == [], "B source: %s is accepted (positive control)" % label)

    # --- duplicates and ownership
    def dup(target):
        def m(c, f):
            finding(f)["dup_of"] = target
        return m

    breaks("a dup_of that names a missing finding", dup("nope-99"), "is not a finding")
    breaks("a dup_of that names itself", dup("page-01"), "names itself")
    breaks("a dup_of that points at another duplicate", lambda c, f: (
        finding(f).update(dup_of="chrome-01"), finding(f, "shared-chrome", SHARED_SURFACE).update(dup_of="page-02")), "itself a duplicate")
    breaks("a duplicate of a finding of another class", dup("page-03"), "cannot be a duplicate of page-03")
    breaks("a duplicate of a non-shared finding in another area", lambda c, f: (
        f.setdefault("auth", {"area": "auth", "origin_main": "3fb96da8", "audited_utc": "2026-10-03", "surfaces": {}})["surfaces"].update(
            other={"node": "2:2", "verdict": "diverges", "summary": "s", "findings": [_sub("A", "other-01", fix="A fix that is long enough to act on")]}),
        c.update(other={"slug": "other", "node": "2:2", "kind": "page", "path": "/o"}),
        finding(f).update(dup_of="other-01")), "is in another area")
    breaks("an owned_by that is not a ClickUp id", lambda c, f: finding(f).update(owned_by="!!"), "owned_by")
    breaks("an owned_by that is an unapproved ticket-shaped word", lambda c, f: finding(f).update(owned_by="makefixes"), "not a ticket that owns")
    breaks("an owned_by on a class that is not A", lambda c, f: finding(f, index=2).update(owned_by="17tnw2b0x3h"), "only for a class A")
    breaks("owned_by used as a blanket exemption", lambda c, f: [finding(f, index=0).update(owned_by="17tnw2b0x3h")] and [
        f["home"]["surfaces"]["page"]["findings"].append(_sub("A", "bulk-%02d" % n, fix="A fix that is long enough to act on", owned_by="17tnw2b0x3h"))
        for n in range(MAX_OWNED_BY + 1)], "an exemption list")
    dupd = copy.deepcopy(good)
    finding(dupd)["dup_of"] = "chrome-01"
    ok(check(cat, dupd) == [], "checker: a valid dup_of (same class, shared canonical) is accepted")
    _g, dup_total, _s, aside = summarise(dupd)
    ok(dup_total["A"] == good_total_a(good) - 1 and aside["duplicates"] == 1,
       "summary: a duplicate is set aside, not counted (A %d, set aside %d)" % (dup_total["A"], aside["duplicates"]))

    # --- tickets
    full = {"tickets": {g: {"id": "86abc1234", "url": CLICKUP_TASK_URL + "86abc1234"} for g in TICKET_GROUPS}}
    with_ticket = copy.deepcopy(good)
    for area, _slug, _surf, f in all_findings(with_ticket):
        if needs_ticket(f):
            f["ticket"] = full["tickets"][ticket_group(area, f)]["id"]
    for b in with_ticket["home"]["bugs"]:
        b["ticket"] = full["tickets"][b["group"]]["id"]
    ok(check(cat, with_ticket, tickets=full, require_tickets=True) == [], "checker: --require-tickets passes when every A/E carries its group's ticket")
    ok(any("must carry the ticket of its group" in p for p in check(cat, good, tickets=full, require_tickets=True)),
       "checker: --require-tickets fails when an A/E finding has no ticket field at all")
    wrong = copy.deepcopy(with_ticket)
    full2 = {"tickets": dict(full["tickets"], home={"id": "86zzz9999", "url": CLICKUP_TASK_URL + "86zzz9999"})}
    ok(any("must carry the ticket of its group" in p for p in check(cat, wrong, tickets=full2, require_tickets=True)),
       "checker: a finding carrying ANOTHER group's ticket is rejected")
    unknown = copy.deepcopy(with_ticket)
    finding(unknown)["ticket"] = "86nosuch99"
    ok(any("not one of the tickets in tickets.json" in p for p in check(cat, unknown, tickets=full)),
       "checker: a finding naming a ticket that does not exist is rejected (Quinn Q-6)")
    ok(any("does not exist yet" in p for p in check(cat, good, tickets={"tickets": {}}, require_tickets=True)),
       "checker: --require-tickets fails while an A/E finding has no ticket for its area")
    ok(any("no valid ClickUp id" in p for p in check(cat, good, tickets={"tickets": {"home": {"id": "!!"}}})),
       "checker: a ticket with a malformed id is rejected")
    for label, url in (("a javascript: URL", "javascript:alert(1)"), ("another ticket's URL", CLICKUP_TASK_URL + "86other999"),
                       ("an http (not https) URL", "http://app.clickup.com/t/86abc1234"), ("a lookalike host", "https://app.clickup.com.evil.example/t/86abc1234"),
                       ("a URL with a trailing path", CLICKUP_TASK_URL + "86abc1234/../x"), ("no URL at all", None)):
        bad = {"tickets": dict(full["tickets"], home={"id": "86abc1234", "url": url})}
        ok(any("must be exactly" in p for p in check(cat, with_ticket, tickets=bad)),
           "checker: a ticket url that is %s is rejected (it becomes an href on the artifact page)" % label)
    ok(safe_ticket_url({"id": "86abc1234", "url": CLICKUP_TASK_URL + "86abc1234"}) == CLICKUP_TASK_URL + "86abc1234"
       and safe_ticket_url({"id": "86abc1234", "url": "javascript:alert(1)"}) is None,
       "safe_ticket_url: only the exact ClickUp task URL of the ticket's own id passes")

    # --- the catalogue is the 35 frames
    real_cat = {slug: {"slug": slug, "node": node, "kind": kind} for slug, (node, kind) in EXPECTED_SURFACES.items()}
    ok(len(EXPECTED_SURFACES) == 35 and sum(1 for v in EXPECTED_SURFACES.values() if v[1] == "page") == 16
       and sum(1 for v in EXPECTED_SURFACES.values() if v[1] == "state") == 19,
       "expected surfaces: the checker's own table is 16 pages and 19 states")
    for label, mutate, expect in (
        ("terms deleted from the catalogue", lambda c: c.pop("terms"), "missing this Figma frame"),
        ("a Manage Devices state deleted", lambda c: c.pop("devices-d4"), "missing this Figma frame"),
        ("a wrong node id", lambda c: c["home"].update(node="1:1"), "the Figma frame is"),
        ("an extra surface", lambda c: c.update(extra={"slug": "extra", "node": "9:9", "kind": "page"}), "not one of the"),
        ("a page relabelled as a state", lambda c: c["home"].update(kind="state"), "the Figma frame is"),
    ):
        c2 = copy.deepcopy(real_cat)
        mutate(c2)
        got = check(c2, {}, expected_surfaces=EXPECTED_SURFACES)
        ok(any(expect in p for p in got), "expected surfaces: %s is rejected (%r)" % (label, expect))

    # --- audited commit metadata
    def meta_with(**kw):
        f2 = copy.deepcopy(good)
        for d in f2.values():
            d.update(kw)
        return f2

    ok(meta_problems(meta_with()) == [] or any("not a commit" in p for p in meta_problems(meta_with())) is False,
       "meta: a findings set with one agreed commit and date is accepted")
    ok(any("omit" in p for p in meta_problems(meta_with(origin_main=""))), "meta: a missing origin_main is rejected")
    ok(any("disagree" in p for p in meta_problems({"a": {"origin_main": "3fb96da8", "audited_utc": "d"},
                                                    "b": {"origin_main": "e7566a96", "audited_utc": "d"}})),
       "meta: findings files that audited different commits are rejected")
    ok(any("not a commit in this repository" in p for p in meta_problems(meta_with(origin_main="0123456789abcdef"))),
       "meta: a commit that is not in the repository is rejected")

    # --- bugs and api gaps
    breaks("a bug with no group", lambda c, f: f["home"]["bugs"][0].pop("group"), "bug group")
    breaks("a bug with a thin evidence", lambda c, f: f["home"]["bugs"][0].update(evidence="x"), "bug evidence")
    breaks("a bug id that collides with a finding id", lambda c, f: f["home"]["bugs"][0].update(id="page-01"), "duplicate bug id")
    breaks("an api gap with an invented status", lambda c, f: f["home"]["api_gaps"][0].update(status="maybe"), "api gap status")
    breaks("a bug whose ticket is not its group's", lambda c, f: f["home"]["bugs"][0].update(ticket="86nosuch99"), "bug ticket",
           tickets=full, require_tickets=True)

    by_group, total, _sev, _aside = summarise(good)
    ok(total["A"] == 2 and by_group["chrome"]["A"] == 1 and by_group["home"]["A"] == 1,
       "summary: shared-scope findings count toward the chrome ticket (A: %d, chrome A: %d)" % (total["A"], by_group["chrome"]["A"]))
    owned_only = copy.deepcopy(good)
    finding(owned_only)["owned_by"] = "17tnw2b0x3h"
    _g2, tot2, sev2, aside2 = summarise(owned_only)
    ok(tot2["A"] == 2 and aside2["owned elsewhere"] == 1 and sum(sev2.values()) == 2 + 1 - 1,
       "summary: an owned_by A is IN the class total (A %d) and out of the severity tally only (%d) — the report says exactly that" % (
           tot2["A"], sum(sev2.values())))
    meta = {"ticket": "X", "ticket_url": "u", "date": "d", "origin_main": "sha"}
    text = render_report(cat, owned_only, {"tickets": {}}, meta)
    ok("Class C" in text and "Ask the owner" in text and "page-01" in text and "## Surfaces" in text,
       "report: the generated report carries the C list, the finding text and every surface")
    ok("counted in the totals above but left out of this severity tally" in text.lower()
       and "not counted anywhere" in text.lower() and "set aside and not counted" not in text.lower(),
       "report: the owned_by wording is the corrected one (counted in the totals, left out of the severity tally only)")
    seg = text.split("## Decisions that are not findings")[1].split("## Index")[0].lower()
    ok("decided, team only" in seg and "public build" not in seg and "anyone with the link" not in seg,
       "report: the sharing decision is recorded as team-only and no public option is offered")

    # --- the committed report equals the generated one
    root = tempfile.mkdtemp(prefix="fa-")
    try:
        rp = os.path.join(root, "report.md")
        m2, _p = audit_meta(good)
        with open(rp, "w", encoding="utf-8") as fh:
            fh.write(render_report(cat, good, {"tickets": {}}, m2))
        ok(report_drift(cat, good, {"tickets": {}}, rp) is None, "check-report: a report generated from the data has no drift")
        edited = copy.deepcopy(good)
        finding(edited)["title"] = "A title edited after the report was written"
        got = report_drift(cat, edited, {"tickets": {}}, rp)
        ok(got is not None and "differs from the data" in got, "check-report: a finding edited without regenerating the report is caught (%s)" % (got or "")[:60])
        ok(report_drift(cat, good, {"tickets": {}}, os.path.join(root, "missing.md")) is not None,
           "check-report: a missing committed report is a failure")

        # round-trip through files, as the real run does
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
    ap.add_argument("--check-report", action="store_true", help="fail if the committed report differs from what the data generates")
    ap.add_argument("--report", default=REPORT_PATH, help="the committed report --check-report compares against")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    catalogue = load_catalogue()
    findings = load_findings()
    tickets = load_tickets()
    problems = check(catalogue, findings, tickets, require_tickets=args.require_tickets,
                     expected_surfaces=EXPECTED_SURFACES)
    problems += meta_problems(findings)
    if args.check_report and not problems:
        drift = report_drift(catalogue, findings, tickets, args.report)
        if drift:
            problems.append(drift)
    by_group, total, sev, set_aside = summarise(findings)
    if args.summary or not problems:
        print("surfaces catalogued: %d · findings files: %d" % (len(catalogue), len(findings)))
        for g in TICKET_GROUPS:
            c = by_group.get(g, collections.Counter())
            print("  %-10s A=%-3d B=%-3d C=%-3d D=%-3d E=%-3d" % (g, c["A"], c["B"], c["C"], c["D"], c["E"]))
        print("  %-10s A=%-3d B=%-3d C=%-3d D=%-3d E=%-3d   (A/E severity, excluding owned_by: %s; duplicates set aside: %d; owned_by: %d)" % (
            "all", total["A"], total["B"], total["C"], total["D"], total["E"], dict(sev), set_aside["duplicates"], set_aside["owned elsewhere"]))
    for p in problems:
        print("FAIL: " + p)
    if args.write_report and not problems:
        meta, _p = audit_meta(findings)
        os.makedirs(os.path.dirname(os.path.abspath(args.write_report)), exist_ok=True)
        with open(args.write_report, "w", encoding="utf-8") as fh:
            fh.write(render_report(catalogue, findings, tickets, meta))
        print("wrote " + args.write_report)
    print("=== fidelity audit: %d problem(s) ===" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
