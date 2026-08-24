#!/usr/bin/env python3
"""Figma reference exporter/verifier for the visual-parity harness.

Figma asset URLs expire in about a week, so a link is not a reference — the BYTES
have to be committed. This script is the gate on the committed store: it ingests a
downloaded frame PNG, records its node id, size and SHA-256 in
`docs/design/visual-parity/reference/manifest.json`, and refuses to grow the store
past its caps.

    # 1. get a short-lived URL for the frame (agent-side, via the Figma MCP server)
    #    mcp__figma__get_screenshot fileKey=SYQn5hFY8YVQKm3c6rw0eJ nodeId=312:124
    #                               maxDimension=<the frame's longer edge>
    # 2. download the bytes before the URL expires
    curl -L -o /tmp/console.png "<image_url from step 1>"
    # 3. ingest them
    python3 scripts/vp_reference.py ingest --slug console --node 312:124 \
        --file /tmp/console.png --note "Operator Console (Design 2.0)"

    python3 scripts/vp_reference.py verify   # checksums + dimensions + caps + orphans
    python3 scripts/vp_reference.py list

`maxDimension` caps the LONGER edge, so pass the frame's longer edge to get the
node at its native size (1760 for the 1760x1000 console frames, 1000 for the
1000x563 stage frames). `verify` fails if a stored PNG's dimensions no longer
match the frame size the catalogue expects, which is how a silently-rescaled
export gets caught before it becomes a fake diff.

The store is BOUNDED and the bound REFUSES rather than evicts: every entry here is
a checked-in artefact somebody chose to keep, so silently dropping one would be
worse than failing the ingest. `vp_selftest.py` mutation-verifies that bound.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_core as vp  # noqa: E402


def cmd_ingest(args):
    store = vp.ReferenceStore()
    try:
        meta = store.ingest(args.slug, args.file, args.node, note=args.note or "")
    except vp.StoreFull as exc:
        print("FAIL: " + str(exc))
        print(
            "      The reference store is capped on purpose. Retire a reference you no longer "
            "compare against, or raise MAX_REFERENCE_ENTRIES/MAX_REFERENCE_BYTES deliberately."
        )
        return 4
    except ValueError as exc:
        print("FAIL: " + str(exc))
        return 2
    print(
        "ingested %-28s node %-10s %dx%d  %d bytes  sha %s"
        % (args.slug, meta["node_id"], meta["width"], meta["height"], meta["bytes"], meta["sha256"][:12])
    )
    return 0


def expected_sizes():
    """slug -> (w, h) from the capture catalogue, so a rescaled export is caught."""
    out = {}
    if not os.path.exists(vp.SURFACES_PATH):
        return out
    cat = vp.load_json(vp.SURFACES_PATH)
    for group in ("web", "native"):
        for entry in cat.get(group, []):
            ref = entry.get("reference")
            if ref:
                out[ref] = (entry["width"], entry["height"])
    return out


def cmd_verify(_args):
    store = vp.ReferenceStore()
    ok, problems = store.verify()
    entries = store.entries()
    sizes = expected_sizes()
    for slug, meta in sorted(entries.items()):
        want = sizes.get(slug)
        if want and (meta.get("width"), meta.get("height")) != want:
            problems.append(
                "%s: stored %sx%s but the catalogue compares it against a %dx%d capture — "
                "re-export at the frame's native size (maxDimension = its longer edge)"
                % (slug, meta.get("width"), meta.get("height"), want[0], want[1])
            )
            ok = False
    for slug in sorted(sizes):
        if slug not in entries:
            problems.append("%s: catalogue expects a reference that has never been ingested" % slug)
            ok = False
    for p in problems:
        print("FAIL: " + p)
    print(
        "=== reference store: %d/%d entries, %d/%d bytes, %d problem(s) ==="
        % (
            len(entries),
            vp.MAX_REFERENCE_ENTRIES,
            store.total_bytes(),
            vp.MAX_REFERENCE_BYTES,
            len(problems),
        )
    )
    return 0 if ok else 1


def cmd_list(_args):
    store = vp.ReferenceStore()
    entries = store.entries()
    for slug, meta in sorted(entries.items()):
        print(
            "%-28s %-10s %5dx%-5d %8d B  %s  %s"
            % (
                slug,
                meta.get("node_id", "?"),
                meta.get("width", 0),
                meta.get("height", 0),
                meta.get("bytes", 0),
                meta.get("exported_utc", "?"),
                meta.get("note", ""),
            )
        )
    print("=== %d entries, %d bytes ===" % (len(entries), store.total_bytes()))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="install a downloaded frame PNG into the committed store")
    ing.add_argument("--slug", required=True)
    ing.add_argument("--node", required=True, help="Figma node id, e.g. 312:124")
    ing.add_argument("--file", required=True, help="the downloaded PNG")
    ing.add_argument("--note", default="")
    ing.set_defaults(fn=cmd_ingest)
    ver = sub.add_parser("verify", help="checksums, dimensions, caps, orphans, missing references")
    ver.set_defaults(fn=cmd_verify)
    lst = sub.add_parser("list", help="show the store contents")
    lst.set_defaults(fn=cmd_list)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
