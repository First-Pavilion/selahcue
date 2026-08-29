#!/usr/bin/env python3
"""Scan the rlibs cargo just emitted for the development entitlement key.

Invoked by scripts/dev_key_not_in_release.sh. See that script for why this is the gate and
the source-text guards are not.
"""
import json
import pathlib
import re
import sys


def artifacts(json_path: str) -> list[pathlib.Path]:
    """Exactly the rlibs THIS build emitted for selahcue-licensing.

    Read from cargo's `--message-format=json` rather than globbed out of `target/`. The first
    cut of this scan globbed `target/release/deps/libselahcue_licensing*.rlib` and reported a
    clean tree as POISONED, because a stale rlib from an earlier poisoned probe was still
    sitting there under a different hash. Globbing is wrong in both directions: a stale
    poisoned artefact is a false red, and a stale clean one standing in for a build that never
    ran is a false green.
    """
    out: list[pathlib.Path] = []
    for line in pathlib.Path(json_path).read_text().splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("reason") != "compiler-artifact":
            continue
        # cargo reports the TARGET name, which uses underscores (`selahcue_licensing`), not
        # the hyphenated package name. Matching the package name found nothing and the scan
        # reported "no rlib to scan" -- which failed closed, correctly, but only because that
        # case was made an error rather than a pass.
        name = ((msg.get("target") or {}).get("name") or "").replace("-", "_")
        if name != "selahcue_licensing":
            continue
        for f in msg.get("filenames") or []:
            p = pathlib.Path(f)
            if p.suffix == ".rlib" and p.is_file():
                out.append(p)
    return out


def main() -> None:
    trust_rs, release_json, debug_json = (pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3])

    # The key bytes come from trust.rs, so the scan follows the constant instead of
    # duplicating it. A rotated dev key needs no edit here.
    m = re.search(
        r"const DEV_PUBLIC_KEY:\s*\[u8;\s*PUBLIC_KEY_BYTES\]\s*=\s*\[(.*?)\];",
        trust_rs.read_text(),
        re.S,
    )
    if not m:
        sys.exit("DEV KEY SCAN FAILED: could not parse DEV_PUBLIC_KEY out of trust.rs")
    key = bytes(int(b) for b in re.findall(r"\d+", m.group(1)))
    if len(key) != 32:
        sys.exit(f"DEV KEY SCAN FAILED: parsed {len(key)} key bytes, expected 32")

    release_libs, debug_libs = artifacts(release_json), artifacts(debug_json)
    if not release_libs or not debug_libs:
        sys.exit(
            f"DEV KEY SCAN FAILED: cargo emitted no rlib to scan (release={len(release_libs)}, "
            f"debug={len(debug_libs)}). A scan with nothing to scan must never report success."
        )

    def carries(paths):
        return [p for p in paths if key in p.read_bytes()]

    # POSITIVE CONTROL FIRST. A scanner that cannot find the bytes anywhere would report a
    # clean release build for the wrong reason -- and would do so silently, forever.
    debug_hits = carries(debug_libs)
    if not debug_hits:
        sys.exit(
            "DEV KEY SCAN FAILED: the key bytes were not found in ANY debug rlib. The scan is "
            "not working, so its 'release is clean' verdict proves nothing. Check the key "
            "parse and the artefact paths before trusting this gate again."
        )

    release_hits = carries(release_libs)
    if release_hits:
        for p in release_hits:
            print(f"  dev key present in {p}", file=sys.stderr)
        sys.exit(
            "DEV KEY SCAN FAILED: the development entitlement key is present in a RELEASE "
            "artefact. Its seed is committed, so anyone could mint unlimited entitlement "
            "against this build. Something re-enabled debug-assertions for release (a profile "
            "table, a cargo config, RUSTFLAGS) or the cfg gate in bundled() was removed."
        )

    print(
        f"== dev key scan: OK == (present in {len(debug_hits)}/{len(debug_libs)} debug "
        f"rlib(s), absent from {len(release_libs)} release rlib(s))"
    )


if __name__ == "__main__":
    main()
