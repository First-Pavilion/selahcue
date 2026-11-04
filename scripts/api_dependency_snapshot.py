#!/usr/bin/env python3
"""Export the complete universal uv graph for GitHub dependency submission (Python >=3.12).

No resolution, installation or network. Fail closed on ambiguous versions or missing edges.
GitHub's static graph currently does not parse uv.lock; the main-only CI job submits this snapshot.
"""
import argparse
import datetime
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import quote


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def snapshot(lock, sha, ref, run_id):
    data = tomllib.loads(Path(lock).read_text())
    packages = data["package"]
    roots = [p for p in packages if "editable" in p.get("source", {})]
    if len(roots) != 1:
        raise ValueError("expected exactly one editable API root")
    root = roots[0]
    resolved = {}
    by_name = {}
    for package in packages:
        if package is root:
            continue
        name, version = canonical(package["name"]), package["version"]
        if name in by_name or not version or "registry" not in package["source"]:
            raise ValueError("ambiguous or unversioned registry dependency: " + name)
        by_name[name] = package
    purls = {name: "pkg:pypi/%s@%s" % (quote(name), quote(p["version"])) for name, p in by_name.items()}
    def edges(package):
        dependencies = list(package.get("dependencies", []))
        # uv.lock records the selected extras on non-root packages (e.g. celery/redis,
        # psycopg/binary). Their edges are part of the universal locked graph too.
        if package is not root:
            for optional in package.get("optional-dependencies", {}).values():
                dependencies.extend(optional)
        names = {canonical(d["name"]) for d in dependencies}
        if not names <= by_name.keys():
            raise ValueError("unresolved dependency edges: " + str(names - by_name.keys()))
        return names
    runtime = edges(root)
    pending = list(runtime)
    while pending:
        for name in edges(by_name[pending.pop()]):
            if name not in runtime:
                runtime.add(name)
                pending.append(name)
    direct = edges(root)
    for deps in root.get("optional-dependencies", {}).values():
        direct.update(canonical(d["name"]) for d in deps)
    for deps in root.get("dev-dependencies", {}).values():
        direct.update(canonical(d["name"]) for d in deps)
    if not direct <= by_name.keys():
        raise ValueError("unresolved optional/build dependency")
    for name, package in by_name.items():
        purl = purls[name]
        resolved[purl] = {"package_url": purl,
            "relationship": "direct" if name in direct else "indirect",
            "scope": "runtime" if name in runtime else "development",
            "dependencies": sorted(purls[n] for n in edges(package))}
    manifest = "implementation/api/uv.lock"
    return {"version": 0, "sha": sha, "ref": ref,
        "job": {"correlator": "api-uv-lock", "id": str(run_id)},
        "detector": {"name": "selahcue-uv-lock", "version": "1.0.0",
                     "url": "https://github.com/First-Pavilion/selahcue"},
        "scanned": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "manifests": {manifest: {"name": "SelahCue API universal locked profiles",
            "file": {"source_location": manifest}, "resolved": resolved}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", default="implementation/api/uv.lock")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = snapshot(args.lock, args.sha, args.ref, args.run_id)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print("API graph: %d exact versioned packages" % len(next(iter(result["manifests"].values()))["resolved"]))


if __name__ == "__main__":
    main()
