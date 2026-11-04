#!/usr/bin/env python3
"""Refuse an operator CycloneDX SBOM that omits the shipped STT feature tree.

The Windows installer enables operator `stt`; its selahcue-stt dependency enables
whisper, capture and download (Cargo.toml). Check each branch, not merely the
optional path crate. This validates a metadata inventory, not a compiled binary.
Python standard library only. Run after generation and before artifact upload.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import unittest
from urllib.parse import unquote

REQUIRED = frozenset({"selahcue-stt", "whisper-rs", "whisper-rs-sys", "cpal", "ureq"})


def check(document: object) -> None:
    if not isinstance(document, dict) or document.get("bomFormat") != "CycloneDX":
        raise ValueError("Expected a CycloneDX JSON document")
    metadata = document.get("metadata")
    root = metadata.get("component") if isinstance(metadata, dict) else None
    if not isinstance(root, dict) or root.get("name") != "selahcue-operator":
        raise ValueError("Expected the selahcue-operator SBOM, not another crate's document")
    root_ref = root.get("bom-ref")
    dependencies = document.get("dependencies")
    if not isinstance(root_ref, str) or not root_ref or not isinstance(dependencies, list):
        raise ValueError("Expected the operator dependency graph")
    graph = {}
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise ValueError("Expected dependency objects")
        ref, children = dependency.get("ref"), dependency.get("dependsOn", [])
        if (not isinstance(ref, str) or not ref or ref in graph
                or not isinstance(children, list) or any(not isinstance(c, str) for c in children)):
            raise ValueError("Expected unique dependency refs and string dependsOn entries")
        graph[ref] = children
    reachable = set()
    pending = [root_ref]
    while pending:
        ref = pending.pop()
        if ref not in reachable:
            reachable.add(ref)
            pending.extend(graph.get(ref, []))
    components = document.get("components")
    if not isinstance(components, list):
        raise ValueError("Expected a components array")
    present = set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("Expected component objects")
        name, version, purl = (component.get(key) for key in ("name", "version", "purl"))
        if not isinstance(name, str):
            raise ValueError("Expected a component name")
        if name not in REQUIRED:
            continue
        # Matching display text alone could accept another ecosystem/package.
        if (component.get("type") == "library" and isinstance(component.get("bom-ref"), str)
                and component["bom-ref"] in reachable and isinstance(version, str) and version
                and isinstance(purl, str)
                and unquote(purl.split("?", 1)[0].split("#", 1)[0]) == f"pkg:cargo/{name}@{version}"):
            present.add(name)
    missing = REQUIRED - present
    if missing:
        raise ValueError("Operator SBOM missing shipped STT Cargo components: " + ", ".join(sorted(missing)))


def fixture() -> dict:
    return {
        "bomFormat": "CycloneDX",
        "metadata": {"component": {"name": "selahcue-operator", "bom-ref": "operator"}},
        "dependencies": [{"ref": "operator", "dependsOn": sorted(REQUIRED)}],
        "components": [{"type": "library", "name": name, "version": "1.0.0", "bom-ref": name,
                        "purl": f"pkg:cargo/{name}@1.0.0"} for name in sorted(REQUIRED)],
    }


class Controls(unittest.TestCase):
    def test_complete(self):
        check(fixture())

    def test_each_required_component_is_necessary(self):
        for name in REQUIRED:
            with self.subTest(name=name):
                document = fixture()
                document["components"] = [c for c in document["components"] if c["name"] != name]
                with self.assertRaisesRegex(ValueError, name):
                    check(document)

    def test_wrong_document(self):
        for document in (None, [], {}, {"bomFormat": "SPDX"}):
            with self.subTest(document=document), self.assertRaises(ValueError):
                check(document)

    def test_wrong_root(self):
        document = fixture()
        document["metadata"]["component"]["name"] = "selahcue-desktop"
        with self.assertRaisesRegex(ValueError, "selahcue-operator"):
            check(document)

    def test_malformed_components(self):
        for components in (None, {}, ["whisper-rs"], [{"name": []}]):
            document = fixture()
            document["components"] = components
            with self.subTest(components=components), self.assertRaises(ValueError):
                check(document)

    def test_names_alone_do_not_satisfy(self):
        for change in ({"purl": "pkg:npm/cpal@1.0.0"}, {"purl": "pkg:cargo/cpal-extra@1.0.0"},
                       {"purl": "pkg:cargo/cpal@2.0.0"}, {"purl": None},
                       {"version": ""}, {"type": "application"}):
            document = fixture()
            next(c for c in document["components"] if c["name"] == "cpal").update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "cpal"):
                check(document)

    def test_disconnected_component_is_not_coverage(self):
        document = fixture()
        document["dependencies"][0]["dependsOn"].remove("whisper-rs")
        with self.assertRaisesRegex(ValueError, "whisper-rs"):
            check(document)

    def test_malformed_graph(self):
        for dependencies in (None, {}, ["bad"], [{"ref": "operator", "dependsOn": [None]}],
                             [{"ref": "operator", "dependsOn": []}] * 2):
            document = fixture()
            document["dependencies"] = dependencies
            with self.subTest(dependencies=dependencies), self.assertRaises(ValueError):
                check(document)

    def test_leaf_can_omit_depends_on(self):
        document = fixture()
        document["dependencies"].append({"ref": "cpal"})
        check(document)

    def test_transitive_graph_with_cycle_terminates(self):
        document = fixture()
        document["dependencies"] = [{"ref": "operator", "dependsOn": ["stt-branch"]},
                                    {"ref": "stt-branch", "dependsOn": ["operator", *sorted(REQUIRED)]}]
        check(document)

    def test_local_package_url_qualifiers(self):
        document = copy.deepcopy(fixture())
        next(c for c in document["components"] if c["name"] == "selahcue-stt")["purl"] += "?download_url=file%3A..%2Fselahcue-stt"
        check(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sbom", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        return 0 if result.wasSuccessful() else 1
    if args.sbom is None:
        parser.error("provide the generated operator .cdx.json path or --self-test")
    try:
        check(json.loads(args.sbom.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        print(f"SBOM check failed: {error}", file=sys.stderr)
        return 1
    print("Operator SBOM includes shipped STT Cargo components: " + ", ".join(sorted(REQUIRED)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
