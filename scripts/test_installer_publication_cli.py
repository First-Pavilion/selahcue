"""Offline CLI, manifest integration and source-only CI routing checks."""

from contextlib import redirect_stderr, redirect_stdout
from fnmatch import fnmatchcase
import importlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from _installer_publication_fixtures import ReleaseFixture, completed_receipts, digest
from installer_publication.contracts import PublicationError, canonical_bytes, derive_object
from installer_publication.prepare import prepare_release

_ROOT = Path(__file__).resolve().parents[1]
_MARKETING = _ROOT / "implementation/marketing"
_PRODUCTION = _MARKETING / "public/releases/current.json"
_WORKFLOW = _ROOT / ".github/workflows/ci.yml"
_STEP = (
    "      - name: Installer publication offline self-test\n"
    "        working-directory: .\n"
    "        run: python3 scripts/publish_installers.py --self-test\n"
)
_ROUTES = {
    "scripts/installer_publication/**": (
        "scripts/installer_publication/__init__.py",
        "scripts/installer_publication/contracts.py",
        "scripts/installer_publication/prepare.py",
        "scripts/installer_publication/public_verify.py",
        "scripts/installer_publication/upload.py",
        "scripts/installer_publication/manifest.py",
    ),
    "scripts/publish_installers.py": ("scripts/publish_installers.py",),
    "scripts/_installer_publication_fixtures.py": ("scripts/_installer_publication_fixtures.py",),
    "scripts/test_installer_publication_*.py": tuple(
        f"scripts/test_installer_publication_{suite}.py" for suite in ("prepare", "verify", "upload", "cli")
    ),
}


def _block(raw, key, spaces):
    indent = " " * spaces
    _, separator, remainder = raw.partition(f"\n{indent}{key}:\n")
    if not separator:
        raise AssertionError(f"Missing {key} block")
    return re.split(rf"(?m)^{indent}[a-zA-Z0-9_-]+:", remainder, maxsplit=1)[0]


class WorkflowTests(unittest.TestCase):
    def assert_publisher_selects_marketing(self, workflow):
        changes = _block(workflow, "changes", 2)
        filters = _block(changes, "marketing", 12)
        paths = re.findall(r"(?m)^ {14}- '([^']+)'$", filters)
        for samples in _ROUTES.values():
            for sample in samples:
                self.assertTrue(any(fnmatchcase(sample, route) for route in paths), sample)
        self.assertIn(
            "      marketing: ${{ steps.tier.outputs.everything == 'true' || "
            "steps.filter.outputs.marketing == 'true' }}",
            _block(changes, "outputs", 4),
        )
        job = _block(workflow, "marketing", 2)
        self.assertIn("    needs: changes\n", job)
        self.assertIn("    if: needs.changes.outputs.marketing == 'true'\n", job)

    def test_publisher_only_paths_select_existing_marketing_checks(self):
        workflow = _WORKFLOW.read_text()
        self.assert_publisher_selects_marketing(workflow)
        for route in _ROUTES:
            with self.subTest(route=route), self.assertRaises(AssertionError):
                # Apply the mutation to the marketing filter alone.
                start = workflow.index("\n            marketing:\n")
                prefix, filters = workflow[:start], workflow[start:]
                self.assert_publisher_selects_marketing(prefix + filters.replace(f"              - '{route}'\n", "", 1))

    def assert_offline_step(self, workflow):
        job = _block(workflow, "marketing", 2)
        steps = _block(job, "steps", 4)
        entries = re.split(r"(?m)(?=^ {6}- )", steps)
        step_index = next((index for index, entry in enumerate(entries) if entry.startswith(_STEP.splitlines()[0])), -1)
        self.assertGreater(step_index, 0, "Marketing offline publisher step is missing")
        self.assertEqual([line for line in entries[step_index].splitlines() if line.strip()],
                         _STEP.splitlines())
        self.assertTrue(entries[step_index - 1].startswith("      - name: Install\n        run: npm ci\n"))
        self.assertTrue(entries[step_index + 1].startswith("      - name: Reject high and critical npm advisories\n"))
        prior = "".join(entries[:step_index - 1])
        self.assertIn("      - uses: actions/setup-node@", prior)
        self.assertIn("          node-version: \"22\"\n", prior)
        self.assertIn("      - uses: actions/setup-python@", prior)
        self.assertIn("          python-version: \"3.14\"\n", prior)
        self.assertNotIn("\n    env:", job)

    def test_marketing_runs_offline_publisher_after_runtime_setup(self):
        workflow = _WORKFLOW.read_text()
        self.assert_offline_step(workflow)
        for replacement in ("", _STEP + "        if: false\n", _STEP + "        env:\n          SKIP: '1'\n"):
            with self.subTest(replacement=replacement), self.assertRaises(AssertionError):
                self.assert_offline_step(workflow.replace(_STEP, replacement))


class PublisherTests(unittest.TestCase):
    def load_module(self, name):
        self.assertIsNotNone(importlib.util.find_spec(name), f"Missing publisher module {name}")
        return importlib.import_module(name)

    def capture_cli(self, main, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            return main(argv), stdout.getvalue(), stderr.getvalue()

    def test_closed_cli_surface_and_exit_codes(self):
        cli = self.load_module("publish_installers")
        for invalid in (
            [], ["--help"], ["publish"], ["--self-test", "secret-marker"], ["upload"],
            ["upload", "--release-dir", "fixture", "--release-dir", "other"],
            ["upload", "--release-dir", "fixture", "--endpoint", "secret-marker"],
            ["pre", "--input", "in", "--source-tree", "tree", "--out-dir", "out"],
            ["prepare", "--in", "in", "--source-tree", "tree", "--out-dir", "out"],
            ["verify-public", "--plan", "in", "--out", "out", "--force"],
            ["emit-manifest", "--release-dir", "dir", "--verification", "in", "--out"],
        ):
            with self.subTest(argv=invalid):
                code, stdout, stderr = self.capture_cli(cli.main, invalid)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertNotIn("secret-marker", stderr)

        from installer_publication import upload
        for expected in (0, 2, 3, 4, 5):
            error = PublicationError(expected, "Bounded synthetic failure") if expected else None
            with self.subTest(code=expected), patch.object(upload, "upload_release", side_effect=error) as stage:
                code, stdout, stderr = self.capture_cli(cli.main, ["upload", "--release-dir", "fixture"])
                stage.assert_called_once_with(Path("fixture"))
                self.assertEqual(code, expected)
                if expected:
                    self.assertEqual(stdout, "")
                    self.assertIn("Bounded synthetic failure", stderr)
                else:
                    self.assertIn("upload-receipt.json", stdout)
                    self.assertEqual(stderr, "")

    def test_no_production_manifest_or_remote_call_during_self_test(self):
        cli = self.load_module("publish_installers")
        original = _PRODUCTION.read_bytes()
        with (
            patch.object(cli, "_self_test", return_value=True) as suites,
            patch("installer_publication.public_verify._connect_https") as connect,
            patch("installer_publication.upload.AwsCli") as aws,
        ):
            code, _, stderr = self.capture_cli(cli.main, ["--self-test"])
        self.assertEqual(code, 0, stderr)
        suites.assert_called_once_with()
        connect.assert_not_called()
        aws.assert_not_called()
        self.assertEqual(_PRODUCTION.read_bytes(), original)
        with patch.object(cli, "_self_test", return_value=False):
            self.assertEqual(self.capture_cli(cli.main, ["--self-test"])[0], 5)

    def test_verify_public_uses_its_credential_boundary_and_canonical_plan(self):
        cli = self.load_module("publish_installers")
        with TemporaryDirectory() as directory:
            fixture, independent, _ = self.completed_release(Path(directory))
            plan = fixture.output / "public-plan.json"
            out = independent.with_name("new-verification.json")
            args = ["verify-public", "--plan", str(plan), "--out", str(out)]
            with (
                patch.dict(os.environ, {"INSTALLER_S3_ACCESS_KEY": "synthetic-secret-marker"}, clear=True),
                patch("installer_publication.public_verify._connect_https") as connect,
            ):
                code, stdout, stderr = self.capture_cli(cli.main, args)
            self.assertEqual(code, 3, stderr)
            self.assertNotIn("synthetic-secret-marker", stdout + stderr)
            connect.assert_not_called()
            self.assertFalse(out.exists())
            from installer_publication.contracts import parse_verification
            with patch("installer_publication.public_verify.verify_public_plan",
                       return_value=parse_verification(independent.read_bytes())) as verify:
                self.assertEqual(self.capture_cli(cli.main, args)[0], 0)
                self.assertEqual(out.read_bytes(), independent.read_bytes())
                out.unlink()
                plan.chmod(0o600)
                plan.write_bytes(plan.read_bytes() + b" ")
                self.assertEqual(self.capture_cli(cli.main, args)[0], 2)
                verify.assert_called_once()
                self.assertFalse(out.exists())

    def completed_release(self, directory):
        fixture = ReleaseFixture(directory)
        prepared = prepare_release(fixture.input_path, fixture.source_tree, fixture.output)
        verification, upload = completed_receipts(json.loads((fixture.output / "public-plan.json").read_bytes()))
        upload["input_sha256"] = prepared.prepare_receipt.input_sha256
        upload["prepare_receipt_sha256"] = digest((fixture.output / "prepare-receipt.json").read_bytes())
        # Separate synthetic invocations with matching observations.
        verification["verifier_version"] = f"installer-publication/1 sha256:{prepared.prepare_receipt.publisher_source_sha256}"
        verification["started_at"] = "2026-11-15T10:03:00Z"
        verification["finished_at"] = "2026-11-15T10:05:00Z"
        verification["objects"] = [
            {**row, "completed_at": "2026-11-15T10:04:00Z"} for row in verification["objects"]
        ]
        independent = fixture.directory / "independent-verification.json"
        independent.write_bytes(canonical_bytes(verification))
        upload_path = fixture.output / "upload-receipt.json"
        upload_path.write_bytes(canonical_bytes(upload))
        return fixture, independent, upload_path

    def assert_emit_error(self, emit, fixture, verification, out, code=2):
        with self.assertRaises(PublicationError) as failure:
            emit(fixture.output, verification, out)
        self.assertEqual(failure.exception.exit_code, code)
        self.assertFalse(out.exists())

    def test_independent_verification_is_required_and_plan_bound(self):
        emit = self.load_module("installer_publication.manifest").emit_manifest
        with TemporaryDirectory() as directory:
            fixture, independent, upload = self.completed_release(Path(directory))
            original = json.loads(independent.read_bytes())
            out = independent.with_name("candidate.json")
            self.assert_emit_error(emit, fixture, independent.with_name("missing.json"), out)
            self.assert_emit_error(emit, fixture, upload, out)
            stale = {**original, "plan_sha256": "f" * 64}
            independent.write_bytes(canonical_bytes(stale))
            self.assert_emit_error(emit, fixture, independent, out)
            stale = {**original, "verifier_version": "installer-publication/1 sha256:" + "f" * 64}
            independent.write_bytes(canonical_bytes(stale))
            self.assert_emit_error(emit, fixture, independent, out)
            uploader = json.loads(upload.read_bytes())
            reused = {
                **original, "started_at": uploader["started_at"], "finished_at": uploader["finished_at"],
                "objects": [row["anonymous_readback"] for row in uploader["objects"]],
            }
            independent.write_bytes(canonical_bytes(reused))
            self.assert_emit_error(emit, fixture, independent, out)
            # The receipt claims the right plan digest but describes a different internally valid object.
            row = original["objects"][0]
            other = derive_object("windows", fixture.data["version"], "other.exe",
                                  row["observed_size_bytes"], row["observed_sha256"])
            row["url"] = other.url
            row["headers"]["content_disposition"] = other.content_disposition
            independent.write_bytes(canonical_bytes(original))
            self.assert_emit_error(emit, fixture, independent, out)

    def test_universal_pair_projects_identical_metadata_to_actual_parser(self):
        emit = self.load_module("installer_publication.manifest").emit_manifest
        production_bytes = _PRODUCTION.read_bytes()
        with TemporaryDirectory() as directory:
            fixture, independent, _ = self.completed_release(Path(directory))
            candidate = emit(fixture.output, independent, independent.with_name("candidate.json"))
            rows = json.loads(candidate.read_bytes())["artifacts"]
            self.assertEqual([row["target"] for row in rows],
                             ["windows-x64", "macos-arm64", "macos-x64", "ubuntu-24.04-x64"])
            self.assertEqual({k: v for k, v in rows[1].items() if k != "target"},
                             {k: v for k, v in rows[2].items() if k != "target"})
            self.assertEqual(rows[1]["architectures"], ["arm64", "x64"])
            self.assertTrue(rows[1]["url"].endswith("/Operator%20%28Universal%29.dmg"))
            self.assertEqual((rows[1]["app_signature"], rows[1]["package_signature"],
                              rows[1]["notarization"], rows[1]["publisher"]),
                             ("ad_hoc", "unsigned", "not_notarized", None))
            validated = subprocess.run(
                ["node", str(_MARKETING / "scripts/validate_release_manifest.ts"), str(candidate)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(_PRODUCTION.read_bytes(), production_bytes)

    def test_thin_mac_inspection_blocks_preparation(self):
        with TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            fixture.inspections["universalMac"]["architectures"] = ["arm64"]
            fixture.save()
            with self.assertRaisesRegex(PublicationError, "must have both slices"):
                prepare_release(fixture.input_path, fixture.source_tree, fixture.output)

    def test_parser_failure_and_partial_receipts_leave_no_output(self):
        manifest = self.load_module("installer_publication.manifest")
        with TemporaryDirectory() as directory:
            fixture, independent, upload = self.completed_release(Path(directory))
            out = independent.with_name("candidate.json")
            upload_bytes = upload.read_bytes()
            partial = json.loads(upload_bytes)
            partial["objects"].pop()
            upload.write_bytes(canonical_bytes(partial))
            self.assert_emit_error(manifest.emit_manifest, fixture, independent, out)
            stale = json.loads(upload_bytes)
            stale["prepare_receipt_sha256"] = "f" * 64
            upload.write_bytes(canonical_bytes(stale))
            self.assert_emit_error(manifest.emit_manifest, fixture, independent, out)
            upload.write_bytes(upload_bytes)
            with patch.object(manifest, "_project", return_value={"schema_version": 1, "unexpected": True}):
                self.assert_emit_error(manifest.emit_manifest, fixture, independent, out)
            evidence = next((fixture.output / "evidence").iterdir())
            evidence.chmod(0o600)
            evidence.write_bytes(b"changed after preparation")
            self.assert_emit_error(manifest.emit_manifest, fixture, independent, out)

    def test_existing_output_must_be_identical(self):
        emit = self.load_module("installer_publication.manifest").emit_manifest
        with TemporaryDirectory() as directory:
            fixture, independent, _ = self.completed_release(Path(directory))
            out = independent.with_name("candidate.json")
            emit(fixture.output, independent, out)
            identity = out.stat().st_ino
            self.assertEqual(emit(fixture.output, independent, out), out)
            self.assertEqual(out.stat().st_ino, identity)
            out.chmod(0o600)
            out.write_bytes(b"different")
            with self.assertRaises(PublicationError) as failure:
                emit(fixture.output, independent, out)
            self.assertEqual(failure.exception.exit_code, 2)
            self.assertEqual(out.read_bytes(), b"different")
            alias = independent.with_name("alias.json")
            alias.symlink_to(out)
            with self.assertRaises(PublicationError) as failure:
                emit(fixture.output, independent, alias)
            self.assertEqual(failure.exception.exit_code, 2)
            self.assertTrue(alias.is_symlink())
            with self.assertRaises(PublicationError):
                emit(fixture.output, independent, _PRODUCTION)
