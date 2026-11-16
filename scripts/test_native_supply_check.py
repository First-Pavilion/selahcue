"""Finite offline controls for the fixed audit-only native dependency mirror."""
import copy
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import time
import tarfile
import tempfile
import tomllib
import unittest
from unittest.mock import patch

try:
    from scripts import prepare_native_supply_check as helper
except ImportError:
    helper = None

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import check_rust_supply_ci as policy


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(helper, 'fixed native supply preparation is absent')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.temp = Path(self.tmp.name).resolve()
        self.mirror = helper.Mirror(ROOT, self.temp, {'run': '123', 'attempt': '1', 'head': 'a' * 40})

    def test_frozen_inputs_and_exact_three_path_relocation(self):
        inputs, pins = helper.inputs(ROOT)
        self.assertEqual(len(pins), 102)
        original = inputs['Cargo.toml']
        relocated = helper.relocate_manifest(original)
        self.assertEqual(relocated.count(b'../source/implementation/desktop/crates/'), 3)
        before, after = tomllib.loads(original.decode()), tomllib.loads(relocated.decode())
        for name in ('selahcue-core', 'selahcue-cloud', 'selahcue-scripture'):
            after['dependencies'][name]['path'] = before['dependencies'][name]['path']
        self.assertEqual(before, after)
        for name in inputs:
            bad = dict(inputs)
            bad[name] += b'\n'
            with self.assertRaises(helper.Failure):
                helper.verify_fixture_inputs(bad)
        with self.assertRaises(helper.Failure):
            helper.relocate_manifest(original.replace(b'features = ["openai"]', b'features = ["http"]'))

    def test_exclusive_ownership_and_foreign_paths_are_preserved(self):
        self.mirror.root.mkdir()
        (self.mirror.root / 'foreign').write_text('keep')
        with self.assertRaises(helper.Failure):
            self.mirror.initialize()
        with self.assertRaises(helper.Failure):
            self.mirror.cleanup()
        self.assertEqual((self.mirror.root / 'foreign').read_text(), 'keep')

    def test_owned_cleanup_after_failure_and_absent_state(self):
        self.assertEqual(self.mirror.cleanup(), 'absent')
        self.mirror.initialize()
        (self.mirror.root / 'partial').write_text('incomplete')
        self.assertEqual(self.mirror.cleanup(), 'removed')
        self.assertFalse(self.mirror.root.exists())

    def test_symlink_replacement_and_foreign_binding_cannot_authorize_cleanup(self):
        self.mirror.initialize()
        outside = self.temp / 'outside'; outside.write_text('keep')
        (self.mirror.root / 'link').symlink_to(outside)
        with self.assertRaises(helper.Failure):
            self.mirror.cleanup()
        self.assertEqual(outside.read_text(), 'keep')
        (self.mirror.root / 'link').unlink()
        other = helper.Mirror(ROOT, self.temp, {'run': '999', 'attempt': '1', 'head': 'a' * 40})
        with self.assertRaises(helper.Failure):
            other.cleanup()
        self.assertTrue(self.mirror.root.is_dir())

    def test_archive_confined_complete_git_blob_inventory(self):
        raw = b'public fixture\n'
        oid = helper.git_blob(raw)
        expected = {'implementation/desktop/Cargo.toml': oid}
        def archive(name='implementation/desktop/Cargo.toml', kind=tarfile.REGTYPE, body=raw, duplicate=False):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as tar:
                member = tarfile.TarInfo(name); member.type = kind
                member.size = len(body) if kind == tarfile.REGTYPE else 0
                tar.addfile(member, io.BytesIO(body) if member.size else None)
                if duplicate: tar.addfile(member, io.BytesIO(body))
            return stream.getvalue()
        for label, data in [('good', archive()), ('traversal', archive('../outside')),
                            ('extra', archive('unexpected')), ('symlink', archive(kind=tarfile.SYMTYPE)),
                            ('duplicate', archive(duplicate=True)), ('drift', archive(body=b'changed'))]:
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=self.temp) as directory:
                dest = Path(directory) / 'source'
                if label == 'good':
                    helper.extract_source(data, dest, expected)
                    self.assertEqual((dest / next(iter(expected))).read_bytes(), raw)
                else:
                    with self.assertRaises(helper.Failure): helper.extract_source(data, dest, expected)
        with self.assertRaises(helper.Failure):
            helper.extract_source(archive(), self.temp/'missing', expected | {'missing': '0'*40})

    def test_normative_inventory_is_complete_and_rejects_source_identity_drift(self):
        raw = subprocess.check_output(['git','ls-tree','-r',
              '1ea22e1ce6e52ab8aa2e0fd83fda1c9d90b094da','--',
              'implementation/desktop','rust-toolchain.toml'], cwd=ROOT)
        self.assertEqual(len(helper.source_inventory(raw)),497)
        for changed in (raw+b'extra',raw.replace(b'100644',b'120000',1),raw[:-1]):
            with self.assertRaises(helper.Failure): helper.source_inventory(changed)

    def test_command_deadline_nonzero_and_direct_stream_cap_fail(self):
        for code, budget, cap in [('import sys;sys.exit(23)',2,1024),
                                  ('print("x"*10000)',2,1024),
                                  ('import time;time.sleep(1)',.05,1024)]:
            with self.subTest(code=code), self.assertRaises(helper.Failure):
                helper.command([sys.executable,'-I','-c',code],cwd=self.temp,
                               env={'PATH':'/usr/bin:/bin'},deadline=time.monotonic()+budget,cap=cap)

    def graph_fixture(self):
        # Literal archived lock is independent of the verifier's graph decoder.
        lock = tomllib.loads((ROOT / policy.NATIVE_ROOT / 'Cargo.lock').read_text())
        rows = lock['package']
        ids = {(p['name'], p['version']): p['name'] + '@' + p['version'] for p in rows}
        self.assertEqual(len(ids), 60)
        def dep_id(value):
            fields = value.split()
            candidates = [v for k,v in ids.items() if k[0] == fields[0] and (len(fields)==1 or k[1]==fields[1])]
            self.assertEqual(len(candidates), 1)
            return candidates[0]
        packages, nodes = [], []
        for p in rows:
            name = p['name']
            manifest = (self.mirror.adapter/'Cargo.toml' if name == 'coverage-native-golden'
                        else self.mirror.root/'source/implementation/desktop/crates'/name/'Cargo.toml')
            packages.append({'id': ids[(name, p['version'])], 'name': name, 'version': p['version'],
                             'source': p.get('source'), 'manifest_path': str(manifest)})
            nodes.append({'id': ids[(name, p['version'])], 'features': ['openai'] if name == 'selahcue-cloud' else [],
                          'dependencies': [dep_id(d) for d in p.get('dependencies', [])]})
        return {'packages': packages, 'resolve': {'root': ids[('coverage-native-golden', '0.1.0')], 'nodes': nodes},
                'workspace_members': [ids[('coverage-native-golden', '0.1.0')]], 'workspace_root': str(self.mirror.adapter)}

    def test_locked_metadata_exact_identities_features_edges_and_all_platforms(self):
        inputs, _ = helper.inputs(ROOT)
        good = self.graph_fixture()
        helper.verify_metadata(good, self.mirror.root, inputs['Cargo.lock'])
        mutations = [
            ('missing registry', lambda d: d['packages'].pop()),
            ('extra registry', lambda d: d['packages'].append(dict(d['packages'][-1]))),
            ('wrong version', lambda d: d['packages'][0].update(version='9.9.9')),
            ('registry source', lambda d: next(p for p in d['packages'] if p['source']).update(source='registry+other')),
            ('local path', lambda d: next(p for p in d['packages'] if not p['source']).update(manifest_path='/outside/Cargo.toml')),
            ('feature drift', lambda d: next(n for n in d['resolve']['nodes'] if n['id'].startswith('selahcue-cloud@')).update(features=['http'])),
            ('missing graph node', lambda d: d['resolve']['nodes'].pop()),
            ('changed graph edge', lambda d: next(n for n in d['resolve']['nodes'] if n['dependencies'])['dependencies'].pop()),
            ('alternate workspace', lambda d: d.update(workspace_root='/other')),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                candidate = copy.deepcopy(good); mutate(candidate)
                with self.assertRaises(helper.Failure): helper.verify_metadata(candidate, self.mirror.root, inputs['Cargo.lock'])

    def test_lock_policy_manifest_source_and_metadata_drift_fail_postcheck(self):
        # Use the real integrity gate with a tiny owned tree; avoid any Cargo/Git extraction.
        self.mirror.initialize()
        self.mirror.adapter.mkdir()
        for name, raw in {'Cargo.lock': b'locked', 'Cargo.toml': b'manifest', 'deny.toml': b'policy'}.items():
            (self.mirror.adapter/name).write_bytes(raw)
        (self.mirror.root/'source').mkdir()
        (self.mirror.root/'source/input.rs').write_bytes(b'code')
        (self.mirror.root/'metadata.json').write_bytes(b'{}')
        snapshot = helper.snapshot(self.mirror.root)
        helper.write_json(self.mirror.root/'prepared.json', {'files': snapshot, 'binding': self.mirror.binding})
        with patch.object(self.mirror, 'canonical_check'):
            self.mirror.postcheck()
            for path in [self.mirror.adapter/name for name in ('Cargo.lock', 'Cargo.toml', 'deny.toml')] + [self.mirror.root/'source/input.rs', self.mirror.root/'metadata.json']:
                before = path.read_bytes();path.write_bytes(before+b'changed')
                with self.assertRaises(helper.Failure): self.mirror.postcheck()
                path.write_bytes(before)

    def test_metadata_command_is_locked_all_features_without_platform_or_build(self):
        self.assertEqual(helper.METADATA_ARGS, ['cargo', 'metadata', '--locked', '--all-features',
                                               '--format-version', '1', '--manifest-path', 'Cargo.toml'])
        env = helper.metadata_environment(self.mirror.root, {'PATH': '/bin', 'HOME': '/home/runner',
            'GITHUB_TOKEN': 'private', 'CARGO_REGISTRIES_X_TOKEN': 'private', 'CARGO_ALIAS_METADATA': 'build',
            'RUSTC_WRAPPER': 'wrapper'})
        self.assertFalse(any('TOKEN' in k or 'ALIAS' in k or 'WRAPPER' in k for k in env))
        self.assertEqual(env['CARGO_HOME'], str(self.mirror.root/'cargo'))


class WorkflowTests(unittest.TestCase):
    def test_real_workflow_and_future_discovered_root(self):
        roots = policy.discover_required_roots(ROOT)
        self.assertEqual(len(roots), 4)
        self.assertIn(policy.NATIVE_ROOT, roots)
        self.assertEqual(policy.problems(policy.load_workflow(), roots), [])
        self.assertTrue(policy.problems(policy.load_workflow(), roots | {'future/workspace'}))

    def test_native_preparation_audit_deny_and_postcheck_mutations(self):
        good = policy.load_workflow(); roots = policy.discover_required_roots(ROOT)
        self.assertEqual(policy.problems(good, roots), [])
        def stage(w, ident): return next(s for s in w['jobs']['supply-chain']['steps'] if s.get('id') == ident)
        mutations = [
            ('missing prep', lambda w: w['jobs']['supply-chain']['steps'].remove(stage(w, 'native-supply-prepare'))),
            ('duplicate prep', lambda w: w['jobs']['supply-chain']['steps'].append(copy.deepcopy(stage(w,'native-supply-prepare')))),
            ('relocated prep', lambda w: stage(w,'native-supply-prepare').update(**{'working-directory': '/other'})),
            ('masked prep', lambda w: stage(w,'native-supply-prepare').update(**{'continue-on-error': True})),
            ('alternate prep', lambda w: stage(w,'native-supply-prepare').update(run='python3 other.py')),
            ('conditional deny', lambda w: stage(w,'native-supply-deny').update(**{'if': 'false'})),
            ('alias deny', lambda w: stage(w,'native-supply-deny').update(run='cargo deny check licenses sources bans')),
            ('unlocked deny', lambda w: stage(w,'native-supply-deny').update(run=stage(w,'native-supply-deny')['run'].replace('--locked ',''))),
            ('alternate policy', lambda w: stage(w,'native-supply-deny').update(run=stage(w,'native-supply-deny')['run'].replace('deny.toml','other.toml'))),
            ('alternate stage', lambda w: stage(w,'native-supply-deny').update(**{'working-directory': '/other'})),
            ('missing postcheck', lambda w: w['jobs']['supply-chain']['steps'].remove(stage(w,'native-supply-postcheck'))),
            ('masked postcheck', lambda w: stage(w,'native-supply-postcheck').update(**{'if': 'false'})),
            ('duplicate deny', lambda w: w['jobs']['supply-chain']['steps'].append(copy.deepcopy(stage(w,'native-supply-deny')))),
            ('cleanup not always', lambda w: stage(w,'native-supply-cleanup').pop('if')),
            ('misordered prep', lambda w: w['jobs']['supply-chain']['steps'].reverse()),
            ('missing audit', lambda w: w['jobs']['audit']['steps'].pop()),
            ('masked audit', lambda w: w['jobs']['audit']['steps'][-1].update(run='cargo-audit audit || true')),
            ('duplicate audit', lambda w: w['jobs']['audit']['steps'].append(copy.deepcopy(w['jobs']['audit']['steps'][-1]))),
            ('shallow history', lambda w: w['jobs']['supply-chain']['steps'][0]['with'].update(**{'fetch-depth': 1})),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                candidate=copy.deepcopy(good);mutate(candidate)
                self.assertTrue(policy.problems(candidate, roots), label)


if __name__ == '__main__':
    unittest.main()
