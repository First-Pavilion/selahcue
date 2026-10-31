#!/usr/bin/env python3
"""Offline P04 contract controls. Every credential here is a disposable synthetic canary."""
from __future__ import annotations
import base64
import contextlib
import io
import json
from pathlib import Path
import struct
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

try:
    import pilot_installer_scan as scan
except ImportError:
    scan = None


def payload(openai='synthetic-openai-7f3ac9-canary', deepgram='synthetic-deepgram-b4a826-canary'):
    return json.dumps({'schema': 1, 'cohort': 'field-test-2026-10', 'cutoff': 1809129599,
                       'openai': {'key': openai, 'expires_at': 1809129599, 'model': 'approved-fixture-model'},
                       'deepgram': {'key': deepgram, 'expires_at': 1809129599, 'model': 'nova-3'}},
                      sort_keys=True, separators=(',', ':')).encode()


def elf(contents):
    size = 120 + len(contents)
    ident = b'\x7fELF\x02\x01\x01' + bytes(9)
    header = struct.pack('<16sHHIQQQIHHHHHH', ident, 2, 62, 1, 0x400000, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    ph = struct.pack('<IIQQQQQQ', 1, 5, 0, 0x400000, 0x400000, size, size, 4096)
    return header + ph + contents


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(scan, 'P04 policy module is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected = scan.admit_payload(payload(), cohort='field-test-2026-10',
                                           openai_model='approved-fixture-model', now=1700000000)

    def candidate(self, body):
        p = self.root / 'operator'
        p.write_bytes(elf(body + bytes(max(0, 1_000_000 - 120 - len(body)))))
        return p

    def evidence(self, path):
        return scan.BuildEvidence(source_sha='a' * 40, ref='refs/heads/main', event='workflow_dispatch',
                                  operator_sha256=scan.file_digest(path)[1], architectures=('x86_64',))

    def run_pilot(self, body, **kwargs):
        p = self.candidate(body)
        return scan.scan_component(p, profile='pilot', operator=True, expected=self.expected,
                                   evidence=self.evidence(p), expected_source_sha='a' * 40, **kwargs)

    def test_valid_two_spans_allow_only_intended_entries(self):
        result = self.run_pilot(scan.frame_payload(payload()))
        self.assertEqual(result.envelopes, 1)
        self.assertEqual(result.profile, 'pilot')

    def test_allowed_first_copy_does_not_hide_later_key(self):
        with self.assertRaisesRegex(scan.PolicyError, 'credential-outside-designation'):
            self.run_pilot(scan.frame_payload(payload()) + b'synthetic-openai-7f3ac9-canary')

    def test_ordinary_denies_pilot_even_without_secret_inventory(self):
        p = self.candidate(scan.frame_payload(payload()))
        with self.assertRaisesRegex(scan.PolicyError, 'pilot-in-ordinary'):
            scan.scan_component(p)

    def test_original_markers_remain_denied(self):
        for marker, _ in scan.SIGNATURES:
            for encoding in ('utf-8', 'utf-16-le'):
                with self.subTest(marker=marker, encoding=encoding):
                    p = self.candidate(marker.encode(encoding))
                    with self.assertRaises(scan.PolicyError):
                        scan.scan_component(p)

    def test_endpoints_allowed_only_in_verified_pilot_operator(self):
        self.run_pilot(scan.frame_payload(payload()) + b'https://api.openai.com\0wss://api.deepgram.com/v1/listen')
        p = self.candidate(b'api.openai.com')
        with self.assertRaises(scan.PolicyError):
            scan.scan_component(p, profile='pilot', expected=self.expected)

    def test_all_six_developer_markers_stay_denied_in_pilot(self):
        for marker, _ in scan.SIGNATURES:
            if marker not in scan.ENDPOINTS:
                with self.subTest(marker=marker):
                    with self.assertRaisesRegex(scan.PolicyError, 'forbidden-marker'):
                        self.run_pilot(scan.frame_payload(payload()) + marker.encode())

    def test_duplicate_complete_payload_is_rejected(self):
        with self.assertRaisesRegex(scan.PolicyError, 'envelope-count'):
            self.run_pilot(scan.frame_payload(payload()) * 2)

    def test_encoded_copy_is_denied(self):
        with self.assertRaisesRegex(scan.PolicyError, 'credential-outside-designation'):
            self.run_pilot(scan.frame_payload(payload()) + b'synthetic-deepgram-b4a826-canary'.decode().encode('utf-16-le'))

    def test_known_unrelated_secret_and_development_seed_are_never_excepted(self):
        with self.assertRaisesRegex(scan.PolicyError, 'known-secret'):
            self.run_pilot(scan.frame_payload(payload()) + b'fixture-development-signing-seed',
                           known_secrets=(b'fixture-development-signing-seed',))

    def test_provenance_mismatch_refuses_pilot(self):
        p = self.candidate(scan.frame_payload(payload()))
        evidence = scan.BuildEvidence(source_sha='b'*40, ref='refs/heads/main', event='workflow_dispatch',
                                      operator_sha256=scan.file_digest(p)[1], architectures=('x86_64',))
        with self.assertRaisesRegex(scan.PolicyError, 'provenance'):
            scan.scan_component(p, profile='pilot', operator=True, expected=self.expected,
                                evidence=evidence, expected_source_sha='a'*40)

    def test_cross_chunk_and_overlapping_occurrences_are_enumerated(self):
        p = self.root / 'matches'
        p.write_bytes(b'x' * 31 + b'abababa')
        hits = list(scan.occurrences(p, (b'ababa',), chunk_size=32))
        self.assertEqual(hits, [(0, 31), (0, 33)])

    def test_no_secret_or_payload_hash_in_repr_errors_or_output(self):
        output = io.StringIO()
        secret = b'synthetic-openai-7f3ac9-canary'
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                self.run_pilot(scan.frame_payload(payload()) + secret)
            except scan.PolicyError as exc:
                output.write(str(exc))
            output.write(repr(self.expected))
        value = output.getvalue()
        for index in range(len(secret) - 7):
            self.assertNotIn(secret[index:index+8].decode(), value)


    def test_payload_schema_expiry_and_ambiguous_values_fail(self):
        baseline = json.loads(payload())
        mutations = []
        for key, value in [('schema', True), ('cutoff', 1809129600), ('cohort', 'other'), ('extra', 'x')]:
            obj = json.loads(payload()); obj[key] = value; mutations.append(obj)
        for provider, field, value in [('openai', 'expires_at', 1700000000), ('deepgram', 'model', 'other'),
                                        ('openai', 'key', 'has-unsupported-quote-"'),
                                        ('deepgram', 'key', baseline['openai']['key'])]:
            obj = json.loads(payload()); obj[provider][field] = value; mutations.append(obj)
        for obj in mutations:
            with self.subTest(fields=tuple(obj)):
                with self.assertRaises(scan.PolicyError):
                    scan.admit_payload(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode(),
                                       cohort='field-test-2026-10', openai_model='approved-fixture-model', now=1700000000)
        with self.assertRaises(scan.PolicyError):
            scan.admit_payload(payload().replace(b'"schema":1', b'"schema":1,"schema":1'),
                               cohort='field-test-2026-10', openai_model='approved-fixture-model', now=1700000000)

    def test_noncanonical_and_overlimit_input_fail(self):
        for value in (b' ' + payload(), b'{' * 16385, b'not-json', payload() + b'\x00'):
            with self.assertRaises(scan.PolicyError):
                scan.admit_payload(value, cohort='field-test-2026-10',
                                   openai_model='approved-fixture-model', now=1700000000)

    def test_malformed_length_trailer_and_input_binding_fail(self):
        framed = scan.frame_payload(payload())
        variants = [framed[:-2], framed[:-1] + b'X',
                    scan.MAGIC + struct.pack('<I', 16385) + b'{' + b'x' * 32,
                    scan.frame_payload(payload().replace(b'field-test-2026-10', b'field-test-2026-11'))]
        for value in variants:
            with self.assertRaises(scan.PolicyError):
                self.run_pilot(value)

    def test_native_wrong_architecture_and_loader_bounds_fail(self):
        p = self.candidate(scan.frame_payload(payload()))
        data = bytearray(p.read_bytes()); struct.pack_into('<H', data, 18, 183); p.write_bytes(data)
        with self.assertRaises(scan.PolicyError):
            scan.native_images(p, ('x86_64',))
        p = self.candidate(scan.frame_payload(payload()))
        data = bytearray(p.read_bytes()); struct.pack_into('<Q', data, 64 + 32, len(data) + 1); p.write_bytes(data)
        with self.assertRaises(scan.PolicyError):
            scan.native_images(p, ('x86_64',))

    def test_universal_requires_both_slices_and_one_frame_in_each(self):
        def thin(cpu, body):
            size = 104 + len(body)
            header = struct.pack('<8I', 0xFEEDFACF, cpu, 0, 2, 1, 72, 0, 0)
            segment = struct.pack('<II16sQQQQIIII', 0x19, 72, b'__TEXT', 0, size, 0, size, 7, 5, 0, 0)
            return header + segment + body
        first = thin(0x01000007, scan.frame_payload(payload()))
        second = thin(0x0100000C, scan.frame_payload(payload()))
        offset = 4096; other = 8192
        fat = struct.pack('>II', 0xCAFEBABE, 2) + struct.pack('>5I', 0x01000007, 0, offset, len(first), 12) + struct.pack('>5I', 0x0100000C, 0, other, len(second), 12)
        data = fat.ljust(offset, b'\x00') + first
        data = data.ljust(other, b'\x00') + second
        p = self.root / 'universal'; p.write_bytes(data.ljust(1000000, b'\x00'))
        ev = scan.BuildEvidence('a'*40, 'refs/heads/main', 'workflow_dispatch', scan.file_digest(p)[1], ('arm64', 'x86_64'))
        result = scan.scan_component(p, profile='pilot', operator=True, expected=self.expected, evidence=ev, expected_source_sha='a'*40)
        self.assertEqual(result.envelopes, 2)
        with self.assertRaises(scan.PolicyError):
            scan.native_images(p, ('arm64',))
        p.write_bytes(p.read_bytes() + b'synthetic-openai-7f3ac9-canary')
        ev = scan.BuildEvidence('a'*40, 'refs/heads/main', 'workflow_dispatch', scan.file_digest(p)[1], ('arm64', 'x86_64'))
        with self.assertRaisesRegex(scan.PolicyError, 'credential-outside-designation'):
            scan.scan_component(p, profile='pilot', operator=True, expected=self.expected, evidence=ev, expected_source_sha='a'*40)

    def test_actual_compiler_native_header_is_accepted_without_running_binary(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('tiny native fixture compiler unavailable')
        p = self.root / 'tiny-native'
        result = subprocess.run([compiler, '-x', 'c', '-', '-o', str(p)], input=b'int main(void) { return 0; }',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0)
        magic = p.read_bytes()[:4]
        architecture = ('arm64',) if magic == b'\xcf\xfa\xed\xfe' and struct.unpack_from('<I', p.read_bytes(), 4)[0] == 0x0100000C else ('x86_64',)
        self.assertEqual(scan.native_images(p, architecture)[0][2], architecture[0])

    def test_closed_inventory_refuses_extra_missing_changed_or_symlink(self):
        root = self.root / 'unpacked'; root.mkdir()
        member = root / 'operator'; member.write_bytes(b'fixture-file')
        expected = {'operator': scan.file_digest(member)[1]}
        self.assertEqual(scan.verify_inventory(root, expected), ('operator',))
        (root / 'extra').write_bytes(b'not-in-inventory')
        with self.assertRaisesRegex(scan.PolicyError, 'package-inventory'):
            scan.verify_inventory(root, expected)
        (root / 'extra').unlink(); member.write_bytes(b'changed')
        with self.assertRaisesRegex(scan.PolicyError, 'package-hash'):
            scan.verify_inventory(root, expected)
        member.unlink(); member.symlink_to(self.root / 'operator')
        with self.assertRaises(scan.PolicyError):
            scan.verify_inventory(root, expected)


    def test_committed_public_development_inventory_is_always_denied(self):
        inventory = scan.development_inventory(Path(__file__).resolve().parents[1])
        self.assertGreaterEqual(len(inventory), 2)
        for value in inventory:
            with self.assertRaisesRegex(scan.PolicyError, 'known-secret'):
                self.run_pilot(scan.frame_payload(payload()) + value)

    def test_first_allowed_then_forbidden_across_real_eight_mib_boundary(self):
        framed = scan.frame_payload(payload())
        key = self.expected.credentials[0]
        body = framed + bytes(scan.CHUNK - 120 - len(framed) - 5) + key
        with self.assertRaisesRegex(scan.PolicyError, 'credential-outside-designation'):
            self.run_pilot(body)

    def test_base64_and_hex_key_copies_fail(self):
        key = self.expected.credentials[0]
        for copy in (base64.b64encode(key), key.hex().encode()):
            with self.assertRaisesRegex(scan.PolicyError, 'credential-outside-designation'):
                self.run_pilot(scan.frame_payload(payload()) + copy)

    def test_package_limits_and_invalid_names_fail_closed(self):
        root = self.root / 'limits'; root.mkdir()
        member = root / 'one'; member.write_bytes(b'fixture')
        digest = scan.file_digest(member)[1]
        for expected, options in [({'../one': digest}, {}), ({'C:one': digest}, {}),
                                  ({'one': digest}, {'max_bytes': 1}),
                                  ({'one': digest}, {'max_depth': 0})]:
            with self.assertRaises(scan.PolicyError):
                scan.verify_inventory(root, expected, **options)


    def test_broken_matcher_cannot_pass_clean_artifact(self):
        p = self.candidate(b'ordinary-safe-fixture')
        with patch.object(scan, 'occurrences', return_value=iter(())):
            with self.assertRaisesRegex(scan.PolicyError, 'positive-control'):
                scan.scan_component(p)

    def test_real_compiler_retains_exactly_one_consumed_synthetic_frame(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('tiny native fixture compiler unavailable')
        framed = scan.frame_payload(payload())
        values = ','.join(str(value) for value in framed)
        source = ('__attribute__((used)) static const unsigned char payload[]={' + values + '};'
                  'int main(void){return ((const volatile unsigned char*)payload)[sizeof(payload)-1];}')
        p = self.root / 'consumed-native'
        built = subprocess.run([compiler, '-Os', '-x', 'c', '-', '-o', str(p)], input=source.encode(),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(built.returncode, 0)
        data = p.read_bytes()
        self.assertEqual(data.count(framed), 1)
        architecture = ('arm64',) if data[:4] == b'\xcf\xfa\xed\xfe' and struct.unpack_from('<I', data, 4)[0] == 0x0100000C else ('x86_64',)
        p.write_bytes(data.ljust(1000000, b'\x00'))
        evidence = scan.BuildEvidence('a'*40, 'refs/heads/main', 'workflow_dispatch', scan.file_digest(p)[1], architecture)
        accepted = scan.scan_component(p, profile='pilot', operator=True, expected=self.expected,
                                       evidence=evidence, expected_source_sha='a'*40)
        self.assertEqual(accepted.envelopes, 1)


    def test_pe_headers_and_section_bounds_are_verified(self):
        contents = scan.frame_payload(payload())
        dos = bytearray(64); dos[:2] = b'MZ'; struct.pack_into('<I', dos, 60, 64)
        coff = b'PE\x00\x00' + struct.pack('<HHIIIHH', 0x8664, 1, 0, 0, 0, 240, 2)
        optional = bytearray(240); struct.pack_into('<H', optional, 0, 0x20B)
        section = bytearray(40); section[:6] = b'.rdata'; struct.pack_into('<II', section, 16, len(contents), 512)
        data = (bytes(dos) + coff + optional + section).ljust(512, b'\x00') + contents
        p = self.root / 'windows'; p.write_bytes(data.ljust(1000000, b'\x00'))
        ev = self.evidence(p)
        accepted = scan.scan_component(p, profile='pilot', operator=True, expected=self.expected, evidence=ev, expected_source_sha='a'*40)
        self.assertEqual(accepted.envelopes, 1)
        changed = bytearray(p.read_bytes()); struct.pack_into('<I', changed, 64 + 24 + 240 + 20, 2000000); p.write_bytes(changed)
        with self.assertRaisesRegex(scan.PolicyError, 'native-bounds'):
            scan.native_images(p, ('x86_64',))

    def test_small_resource_is_scanned_without_lowering_native_artifact_floor(self):
        resource = self.root / 'app.js'; resource.write_bytes(b'public safe resource')
        self.assertEqual(scan.scan_resource(resource).size, len(b'public safe resource'))
        resource.write_bytes(b'OPENAI_API_KEY')
        with self.assertRaisesRegex(scan.PolicyError, 'forbidden-marker'):
            scan.scan_resource(resource)
        with self.assertRaisesRegex(scan.PolicyError, 'component-size'):
            scan.scan_component(resource)

    def test_secret_bearing_payload_error_codes_never_quote_input(self):
        secret = b'synthetic-openai-7f3ac9-canary'
        variants = [payload() + b'error', payload().replace(b'"schema":1', b'"schema":true'),
                    payload().replace(b'1809129599', b'9999999999'),
                    payload().replace(b'approved-fixture-model', secret)]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            for value in variants:
                try:
                    scan.admit_payload(value, cohort='field-test-2026-10', openai_model='approved-fixture-model', now=1700000000)
                except scan.PolicyError as error:
                    output.write(str(error))
        for index in range(len(secret) - 7):
            self.assertNotIn(secret[index:index+8].decode(), output.getvalue())


    def test_complete_nonobject_or_nonjson_second_frame_is_not_ignored(self):
        valid = scan.frame_payload(payload())
        for body in (b'[]', b'not-json', b''):
            extra = scan.MAGIC + struct.pack('<I', len(body)) + body + scan.TRAILER
            with self.subTest(body_kind=len(body)):
                with self.assertRaises(scan.PolicyError):
                    self.run_pilot(valid + extra)

    def test_standalone_runtime_magic_next_to_valid_frame_remains_allowed(self):
        valid = scan.frame_payload(payload())
        for body in (scan.MAGIC + valid, valid + scan.MAGIC):
            self.assertEqual(self.run_pilot(body).envelopes, 1)

    def test_complete_overlength_second_frame_fails_before_payload_read(self):
        extra = scan.MAGIC + struct.pack('<I', scan.MAX_PAYLOAD + 1) + b'[' * (scan.MAX_PAYLOAD + 1) + scan.TRAILER
        with self.assertRaisesRegex(scan.PolicyError, 'envelope-malformed'):
            self.run_pilot(scan.frame_payload(payload()) + extra)


if __name__ == '__main__':
    unittest.main()
