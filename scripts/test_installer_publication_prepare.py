import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _installer_publication_fixtures import ReleaseFixture, VERSION_PATH, completed_receipts, digest


from installer_publication import prepare as prepare_module
from installer_publication.contracts import (
    PublicationError,
    parse_public_plan,
    parse_upload_receipt,
    parse_verification,
)
from installer_publication.prepare import load_prepared_release, prepare_release


class PrepareTests(unittest.TestCase):
    def fixture(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        return ReleaseFixture(Path(root.name))

    def prepare(self, fixture):
        return prepare_release(fixture.input_path, fixture.source_tree, fixture.output)

    def reject(self, fixture):
        with self.assertRaises(PublicationError) as failure:
            self.prepare(fixture)
        self.assertEqual(failure.exception.exit_code, 2)
        self.assertFalse((fixture.output / "prepare-receipt.json").exists())

    def test_ci_local_union_rejects_mixed_identity(self):
        for artifact_id, field, value in (
            ("universalMac", "run_id", 123), ("windows", "build_id", "synthetic"),
            ("windows", "run_attempt", None), ("universalMac", "operator", None),
        ):
            with self.subTest(artifact_id=artifact_id, field=field):
                fixture = self.fixture()
                if value is None:
                    del fixture.builds[artifact_id][field]
                else:
                    fixture.builds[artifact_id][field] = value
                fixture.save()
                self.reject(fixture)

    def test_missing_native_acceptance_is_not_a_boolean_override(self):
        for omitted in ("macos-x64-native", "cloud-notes"):
            with self.subTest(omitted=omitted):
                fixture = self.fixture()
                fixture.acceptance["gates"] = [gate for gate in fixture.acceptance["gates"] if gate["id"] != omitted]
                self.reject_prepared_fixture(fixture)
        fixture = self.fixture()
        fixture.acceptance["qualified"] = True
        self.reject_prepared_fixture(fixture)
        fixture = self.fixture()
        fixture.inspections["universalMac"]["architectures"] = ["arm64"]
        self.reject_prepared_fixture(fixture)

    def reject_prepared_fixture(self, fixture):
        fixture.save()
        self.reject(fixture)

    def test_source_profile_version_key_and_artifact_identity_must_agree(self):
        cases = (
            lambda f: f.data.update(source_commit="0" * 40),
            lambda f: f.builds["windows"].update(workflow_sha256="1" * 64),
            lambda f: f.builds["windows"].update(repository="elsewhere/another"),
            lambda f: f.source(VERSION_PATH, b'{"version":"9.3.0"}'),
            lambda f: f.builds["universalMac"].update(version="9.3.0"),
            lambda f: f.profile.update(entitlement_public_key_sha256="0" * 64),
            lambda f: f.source_evidence["build_inputs"].pop(),
            lambda f: f.profile["builds"][0].update(command_argv=["unlogged-command"]),
            lambda f: f.inspection_versions["windows"].update(version="9.3.0"),
            lambda f: f.inspection_versions["ubuntu"].update(entitlement_key_id="0" * 8),
            lambda f: f.inspections["ubuntu"].update(package_sha256="2" * 64),
            lambda f: f.acceptance["artifacts"][2].update(sha256="2" * 64),
        )
        for index, change in enumerate(cases):
            with self.subTest(case=index):
                fixture = self.fixture()
                change(fixture)
                self.reject_prepared_fixture(fixture)

    def test_prepare_snapshots_and_reloads_without_original_paths(self):
        fixture = self.fixture()
        leaf = fixture.raw_evidence("evidence/opaque.json", b'{"path":"../none","sha256":"opaque"}')
        fixture.inspection_versions["windows"]["evidence"] = leaf
        fixture.save()
        original_bytes = fixture.input_path.read_bytes()
        prepared = self.prepare(fixture)
        receipt = prepared.prepare_receipt
        self.assertEqual(receipt.input_sha256, digest(original_bytes))
        self.assertEqual((fixture.output / "input.json").read_bytes(), original_bytes)
        self.assertEqual(stat.S_IMODE(fixture.output.stat().st_mode), 0o700)
        plan_bytes = (fixture.output / "public-plan.json").read_bytes()
        self.assertEqual(receipt.plan_sha256, digest(plan_bytes))
        self.assertEqual(plan_bytes, (json.dumps(json.loads(plan_bytes), sort_keys=True, separators=(",", ":")) + "\n").encode())
        self.assertEqual(parse_public_plan(plan_bytes), prepared.public_plan)
        self.assertEqual(
            prepared.public_plan.objects[0].url,
            "https://selahcue-installers.sfo3.digitaloceanspaces.com/installers/"
            f"1.2.3-rc.1%2Bsynthetic/{fixture.data['artifacts'][0]['sha256']}/Operator%20Setup.exe",
        )
        copied_leaf = next(row for row in receipt.evidence if row.original_path == leaf["path"])
        self.assertEqual((fixture.output / copied_leaf.snapshot_path).read_bytes(),
                         b'{"path":"../none","sha256":"opaque"}')
        shutil.rmtree(fixture.original)
        shutil.rmtree(fixture.source_tree)
        self.assertEqual(load_prepared_release(fixture.output), prepared)

    def test_duplicate_keys_bounds_symlinks_and_mutation_fail_closed(self):
        fixture = self.fixture()
        fixture.input_path.write_bytes(b'{"schema_version":1,' + fixture.input_path.read_bytes()[1:])
        self.reject(fixture)
        fixture = self.fixture()
        fixture.input_path.write_bytes(b" " * (1024 * 1024) + fixture.input_path.read_bytes())
        self.reject(fixture)
        fixture = self.fixture()
        fixture.data["artifacts"][0]["size_bytes"] = 4_000_000_001
        self.reject_prepared_fixture(fixture)
        fixture = self.fixture()
        fixture.data["artifacts"][0]["path"] = "../outside.exe"
        self.reject_prepared_fixture(fixture)
        fixture = self.fixture()
        package_root = fixture.original / "packages"
        package_root.rename(fixture.original / "shadow")
        package_root.symlink_to("shadow", target_is_directory=True)
        self.reject(fixture)
        fixture = self.fixture()
        fixture.output.symlink_to(fixture.original, target_is_directory=True)
        self.reject(fixture)
        fixture = self.fixture()
        os.mkfifo(fixture.original / "fifo")
        leaf = fixture.original / fixture.inspections["windows"]["bundle_scan"]["path"]
        leaf.unlink()
        os.rename(fixture.original / "fifo", leaf)
        self.reject(fixture)
        for collection in ("packages", "evidence"):
            with self.subTest(collection=collection):
                fixture = self.fixture()
                prepared = self.prepare(fixture)
                target = fixture.output / getattr(prepared.prepare_receipt, collection)[0].snapshot_path
                target.chmod(0o600)
                target.write_bytes(b"mutated")
                with self.assertRaises(PublicationError) as failure:
                    load_prepared_release(fixture.output)
                self.assertEqual(failure.exception.exit_code, 2)

    def test_rehashed_workflow_evidence_cannot_replace_committed_source(self):
        fixture = self.fixture()
        workflow = fixture.source_evidence["build_inputs"][2]
        workflow["evidence"] = fixture.raw_evidence("evidence/substitute.yml", b"name: synthetic substitution\n")
        fixture.builds["windows"]["workflow_sha256"] = workflow["evidence"]["sha256"]
        self.reject_prepared_fixture(fixture)

    def test_same_length_package_mutation_during_copy_refuses_prepare(self):
        fixture = self.fixture()
        target = fixture.original / fixture.data["artifacts"][0]["path"]
        original_hash = prepare_module._stream_hash

        def mutate_after_copy(source, size, destination=None):
            result = original_hash(source, size, destination)
            if destination is not None and os.path.samestat(os.fstat(source.fileno()), target.stat()):
                before = target.stat()
                target.write_bytes(b"Z" * size)
                os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            return result

        with patch.object(prepare_module, "_stream_hash", side_effect=mutate_after_copy):
            self.reject(fixture)

    def test_public_plan_derived_fields_and_closed_remote_receipts(self):
        fixture = self.fixture()
        self.prepare(fixture)
        raw = (fixture.output / "public-plan.json").read_bytes()
        plan = json.loads(raw)
        verification, upload = completed_receipts(plan)
        self.assertEqual(parse_verification(json.dumps(verification).encode()).plan_sha256, digest(raw))
        self.assertIsNone(parse_upload_receipt(json.dumps(upload).encode()).objects[0].head.request_id)

        plan["objects"][1]["url"] = plan["objects"][1]["url"].replace("%28", "%2528")
        with self.assertRaises(PublicationError):
            parse_public_plan(json.dumps(plan).encode())
        upload["objects"][0]["acl"]["grants"][1]["permission"] = "WRITE"
        with self.assertRaises(PublicationError):
            parse_upload_receipt(json.dumps(upload).encode())
        verification["objects"][0]["headers"]["content_encoding"] = "gzip"
        with self.assertRaises(PublicationError):
            parse_verification(json.dumps(verification).encode())

    def test_git_source_must_be_clean_even_outside_retained_build_inputs(self):
        fixture = self.fixture()
        fixture.source("implementation/untracked-source", b"synthetic untracked input")
        self.reject(fixture)
        fixture = self.fixture()
        fixture.source(VERSION_PATH, b'{"version":"9.3.0"}')
        fixture.git("update-index", "--assume-unchanged", VERSION_PATH)
        self.reject(fixture)

    def test_opaque_evidence_bounds_are_distinct_from_structured_json(self):
        fixture = self.fixture()
        opaque = b"fixture command output\n" * 50_000
        ref = fixture.raw_evidence("evidence/large.log", opaque)
        fixture.builds["windows"]["build_log"] = ref
        fixture.save()
        prepared = self.prepare(fixture)
        mapping = next(item for item in prepared.prepare_receipt.evidence if item.original_path == ref["path"])
        self.assertEqual((fixture.output / mapping.snapshot_path).stat().st_size, len(opaque))
        self.assertEqual(load_prepared_release(fixture.output), prepared)

        fixture = self.fixture()
        fixture.builds["windows"]["build_log"] = fixture.raw_evidence("evidence/oversized.log", b"X" * 1001)
        fixture.save()
        with patch.object(prepare_module, "MAX_OPAQUE_EVIDENCE_BYTES", 1000):
            self.reject(fixture)

        fixture = self.fixture()
        with patch.object(prepare_module, "MAX_TOTAL_EVIDENCE_BYTES", 1000):
            self.reject(fixture)

        fixture = self.fixture()
        version = fixture.inspection_versions["windows"]
        oversized = b" " * (1024 * 1024) + json.dumps(version).encode()
        ref = fixture.raw_evidence("evidence/version.log", oversized)
        fixture.inspections["windows"]["version_evidence"] = ref
        fixture.data["artifacts"][0]["inspection"] = fixture.record("windows-inspection.json", fixture.inspections["windows"])
        fixture.record(fixture.input_path.name, fixture.data)
        self.reject(fixture)
