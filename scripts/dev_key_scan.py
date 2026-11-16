#!/usr/bin/env python3
"""Scan current Cargo artifacts for the development entitlement key.

Invoked by scripts/dev_key_not_in_release.sh. See that script for why this is the gate and
the source-text guards are not.
"""
import json
import pathlib
import re
import sys


def artifacts(json_path: str) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """The licensing rlibs and operator executable from this invocation.

    Read from cargo's `--message-format=json` rather than globbed out of `target/`. The first
    cut of this scan globbed `target/release/deps/libselahcue_licensing*.rlib` and reported a
    clean tree as POISONED, because a stale rlib from an earlier poisoned probe was still
    sitting there under a different hash. Globbing is wrong in both directions: a stale
    poisoned artefact is a false red, and a stale clean one standing in for a build that never
    ran is a false green.
    """
    libraries: list[pathlib.Path] = []
    executables: list[pathlib.Path] = []
    for line in pathlib.Path(json_path).read_text(encoding="utf-8").splitlines():
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
        if name == "selahcue_operator" and "bin" in msg["target"]["kind"]:
            executable = msg.get("executable")
            if executable and pathlib.Path(executable).is_file():
                executables.append(pathlib.Path(executable))
        if name != "selahcue_licensing":
            continue
        for f in msg.get("filenames") or []:
            p = pathlib.Path(f)
            if p.suffix == ".rlib" and p.is_file():
                libraries.append(p)
    return libraries, executables


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

    release_libs, release_bins = artifacts(release_json)
    debug_libs, debug_bins = artifacts(debug_json)
    mode = sys.argv[4] if len(sys.argv) > 4 else "desktop"
    if mode not in {"desktop", "operator"}:
        sys.exit(f"DEV KEY SCAN FAILED: unknown mode {mode!r}")
    if mode == "operator" and (not release_bins or not debug_bins):
        sys.exit("DEV KEY SCAN FAILED: expected a linked operator executable in both profiles")
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

    if mode == "operator" and not carries(debug_bins):
        sys.exit("DEV KEY SCAN FAILED: the linked debug operator does not contain the development key")

    release_artifacts = release_libs + release_bins if mode == "operator" else release_libs
    release_hits = carries(release_artifacts)
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
        f"rlib(s), absent from {len(release_artifacts)} {mode} release artifact(s))"
    )


if __name__ == "__main__":
    main()
