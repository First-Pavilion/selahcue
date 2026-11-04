#!/usr/bin/env python3
"""Graph export regression checks: complete concrete versions and fail-closed edges."""
import copy
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from packaging.specifiers import SpecifierSet

from api_dependency_snapshot import snapshot

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "implementation/api/uv.lock"


class SnapshotTests(unittest.TestCase):
    def export(self):
        return snapshot(LOCK, "a" * 40, "refs/heads/main", "test")

    def test_complete_known_version_graph_and_scopes(self):
        lock = tomllib.loads(LOCK.read_text())
        packages = {p["name"]: p["version"] for p in lock["package"] if "registry" in p["source"]}
        result = self.export()
        graph = result["manifests"]["implementation/api/uv.lock"]["resolved"]
        self.assertEqual(set(graph), {"pkg:pypi/%s@%s" % item for item in packages.items()})
        for purl, dependency in graph.items():
            self.assertEqual(dependency["package_url"], purl)
            self.assertTrue(set(dependency["dependencies"]) <= graph.keys())
        self.assertEqual(graph["pkg:pypi/redis@" + packages["redis"]]["scope"], "runtime")
        self.assertEqual(graph["pkg:pypi/setuptools@" + packages["setuptools"]]["scope"], "development")
        self.assertEqual(graph["pkg:pypi/psycopg@" + packages["psycopg"]]["relationship"], "direct")

    def test_build_requirements_and_artifacts_are_explicitly_locked(self):
        project = tomllib.loads((LOCK.parent / "pyproject.toml").read_text())
        self.assertEqual(project["build-system"]["requires"], project["dependency-groups"]["build"])
        lock = tomllib.loads(LOCK.read_text())
        versions = {p["name"]: p["version"] for p in lock["package"]}
        for requirement in project["build-system"]["requires"]:
            name, version = requirement.split("==")
            self.assertEqual(versions[name], version)
        for package in lock["package"]:
            if "registry" not in package["source"]:
                continue
            artifacts = package.get("wheels", []) + ([package["sdist"]] if "sdist" in package else [])
            self.assertTrue(artifacts, package["name"])
            for artifact in artifacts:
                self.assertRegex(artifact["hash"], r"^sha256:[0-9a-f]{64}$")

    def test_compatible_bot_patch_does_not_change_bootstrap_pin(self):
        project = tomllib.loads((LOCK.parent / "pyproject.toml").read_text())
        supported = SpecifierSet(project["tool"]["uv"]["required-version"])
        self.assertIn("0.13.4", supported)
        self.assertIn("0.13.5", supported)
        self.assertIn("0.13.99", supported)
        for version in ("0.13.3", "0.12.99", "0.14.0", "0.14.1", "1.0.0"):
            self.assertNotIn(version, supported)
        self.assertEqual((LOCK.parent / ".uv-version").read_text().strip(), "0.13.4")
        self.assertEqual(project["tool"]["uv"]["exclude-newer"], "14 days")
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        api = workflow.split("  api:\n", 1)[1].split("  api-dependency-graph:\n", 1)[0]
        self.assertIn('version: "0.13.4"', api)
        self.assertIn("ghcr.io/astral-sh/uv:0.13.4@sha256:", (LOCK.parent / "Dockerfile").read_text())

    def test_duplicate_versions_refused_instead_of_omitted(self):
        data = tomllib.loads(LOCK.read_text())
        data["package"].append(copy.deepcopy(data["package"][0]))
        with patch("api_dependency_snapshot.tomllib.loads", return_value=data):
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                self.export()

    def test_unknown_edge_refused_instead_of_dropped(self):
        data = tomllib.loads(LOCK.read_text())
        data["package"][0]["dependencies"] = [{"name": "missing-package"}]
        with patch("api_dependency_snapshot.tomllib.loads", return_value=data):
            with self.assertRaisesRegex(ValueError, "unresolved"):
                self.export()


if __name__ == "__main__":
    unittest.main()
