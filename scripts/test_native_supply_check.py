"""Finite offline controls for the fixed audit-only native dependency mirror."""
import copy
from hashlib import sha256
import importlib.util
import io
import json
import os
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


    def _prepare_ancestor_case(self, label, forbidden=None):
        home=self.temp/label/'home/runner'
        runner_temp=home/'work/_temp';runner_temp.mkdir(parents=True)
        cargo=home/'.cargo';(cargo/'bin').mkdir(parents=True)
        (cargo/'bin/cargo-deny').write_bytes(b'ordinary binary')
        if forbidden:
            path=home/forbidden
            if forbidden.endswith('link'):
                path=cargo/'config.toml';path.symlink_to(self.temp/'absent')
            else:
                path.write_bytes(b'blocked configuration')
        mirror=helper.Mirror(ROOT,runner_temp,{'run':'123','attempt':'1','head':'a'*40})
        return mirror

    def test_hosted_bin_only_cargo_ancestor_reaches_git_preparation(self):
        # Git is the next external boundary after the real ancestor guard.
        class ReachedGit(Exception): pass
        mirror=self._prepare_ancestor_case('bin-only')
        def stop_at_git(argv, **kwargs):
            self.assertEqual(argv[:3],['git','merge-base','--is-ancestor'])
            raise ReachedGit()
        with patch.object(helper,'command',side_effect=stop_at_git):
            try:
                mirror.prepare()
            except ReachedGit:
                pass
            except helper.Failure as exc:
                self.fail('bin-only hosted Cargo ancestor rejected before Git: '+str(exc))
            else:
                self.fail('preparation did not reach the required Git boundary')

    def test_actual_ancestor_configuration_remains_rejected(self):
        for index,path in enumerate(('.cargo/config','.cargo/config.toml','Cargo.toml',
                                     'deny.exceptions.toml','.deny.exceptions.toml','config-link')):
            with self.subTest(path=path):
                mirror=self._prepare_ancestor_case('blocked-'+str(index),path)
                with patch.object(helper,'command',side_effect=AssertionError('configuration must fail before any command')):
                    with self.assertRaises(helper.Failure): mirror.prepare()

    def test_capture_exact_limits_and_excess_have_bounded_retained_disk_bytes(self):
        # Observe actual spool lengths at close, independent of wrapper diagnostics.
        original_file=tempfile.TemporaryFile
        retained=[]
        class ObservedFile:
            def __init__(self,*args,**kwargs):
                self.file=original_file(*args,**kwargs)
            def __getattr__(self,name): return getattr(self.file,name)
            def __enter__(self): return self
            def __exit__(self,*args):
                retained.append(os.fstat(self.file.fileno()).st_size)
                self.file.close()
        for stream,limit in ((1,1024),(2,1024*1024)):
            for amount in (limit,limit+1,8*1024*1024):
                with self.subTest(stream=stream,amount=amount):
                    retained.clear()
                    code=f'import os,signal;signal.alarm(3);os.write({stream},b"x"*{amount})'
                    with patch.object(tempfile,'TemporaryFile',ObservedFile):
                        if amount==limit:
                            result=helper.command([sys.executable,'-I','-c',code],cwd=self.temp,
                                env={'PATH':'/usr/bin:/bin'},deadline=time.monotonic()+5,cap=1024)
                            self.assertEqual(result,b'x'*1024 if stream==1 else b'')
                        else:
                            with self.assertRaises(helper.Failure):
                                helper.command([sys.executable,'-I','-c',code],cwd=self.temp,
                                    env={'PATH':'/usr/bin:/bin'},deadline=time.monotonic()+5,cap=1024)
                    # Baseline closes stderr then stdout. No disk spool is also valid.
                    self.assertLessEqual(len(retained),2,'unexpected output spool inventory')
                    if len(retained)==2:
                        self.assertLessEqual(retained[0],1024*1024,'stderr retained disk bytes exceeded 1 MiB')
                        self.assertLessEqual(retained[1],1024,'stdout retained disk bytes exceeded 1024')

    def test_exited_leader_cannot_leave_live_same_group_descendant(self):
        # Independent alarm and survival marker bound descendants on broken code too.
        for exit_code in (0,23):
            for inherited in (True,False):
                with self.subTest(exit_code=exit_code,inherited=inherited):
                    marker=self.temp/f'survived-{exit_code}-{inherited}'
                    code='''import os,sys,time,signal
signal.alarm(3)
r,w=os.pipe()
child=os.fork()
if child==0:
 signal.alarm(2)
 os.close(r)
 if sys.argv[2]=='False':
  os.close(1);os.close(2)
 os.write(w,b'ready');os.close(w)
 time.sleep(.4)
 open(sys.argv[1],'w').write('survived')
 os._exit(0)
os.close(w);os.read(r,5);os.close(r)
os._exit(int(sys.argv[3]))
'''
                    argv=[sys.executable,'-I','-c',code,str(marker),str(inherited),str(exit_code)]
                    if exit_code:
                        with self.assertRaisesRegex(helper.Failure,'exit 23'):
                            helper.command(argv,cwd=self.temp,env={'PATH':'/usr/bin:/bin'},deadline=time.monotonic()+3)
                    else:
                        self.assertEqual(helper.command(argv,cwd=self.temp,env={'PATH':'/usr/bin:/bin'},deadline=time.monotonic()+3),b'')
                    time.sleep(.5)
                    self.assertFalse(marker.exists(),'same-group child survived leader shutdown')

    def test_leader_exit_at_deadline_is_not_success(self):
        # Advance the observation clock only when a real child exit is observed.
        real_clock,real_waitid=time.monotonic,os.waitid
        original_process=subprocess.Popen
        deadline=real_clock()+3
        exited=False
        class ObservedProcess(original_process):
            def poll(self):
                nonlocal exited
                result=super().poll();exited=exited or result is not None
                return result
        def observe_waitid(*args):
            nonlocal exited
            result=real_waitid(*args);exited=exited or result is not None
            return result
        def clock(): return deadline+1 if exited else real_clock()
        with patch.object(subprocess,'Popen',ObservedProcess), patch.object(os,'waitid',side_effect=observe_waitid), patch.object(time,'monotonic',side_effect=clock):
            with self.assertRaisesRegex(helper.Failure,'deadline',msg='leader exit bypassed the deadline'):
                helper.command([sys.executable,'-I','-c','import signal;signal.alarm(2)'],cwd=self.temp,
                    env={'PATH':'/usr/bin:/bin'},deadline=deadline)


class CargoResolutionTests(unittest.TestCase):
    def test_actual_alias_path_selects_installed_cargo_for_direct_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory).resolve();toolchains=home/'.rustup/toolchains'
            binary=toolchains/'1.98.0-test-host/bin/cargo'
            binary.parent.mkdir(parents=True)
            proxy=home/'bin/cargo';proxy.parent.mkdir()
            rustup=home/'bin/rustup';selected=home/'selected.log'
            # Inert adapters exercise path selection and the existing real shell
            # sentinels. They never invoke Cargo/rustup, resolve dependencies or build.
            header=f'#!{sys.executable}\nimport sys,signal\nsignal.alarm(2)\n'
            binary.write_text(header+f'open({str(selected)!r},"a").write("installed\\n")\n'
                +'print("cargo 1.98.0 (inert fixture)" if sys.argv[1:]==["--version"] else "alias fixture")\n')
            rustup.write_text(header+f'open({str(selected)!r},"a").write("proxy\\n")\nsys.exit(44)\n')
            binary.chmod(0o755);rustup.chmod(0o755)
            workflow={'jobs':{'audit':{'steps':[{'working-directory':'fixture','run':'cargo-audit audit'}]},
                              'supply-chain':{'steps':[{'working-directory':'fixture','run':'cargo-deny check licenses sources bans'}]}}}
            ambient={'HOME':str(home),'RUSTUP_HOME':str(home/'.rustup'),'PATH':str(proxy.parent)+os.pathsep+os.defpath}
            for kind in ('direct','symlink','hardlink'):
                with self.subTest(kind=kind):
                    if kind=='direct': proxy.write_bytes(binary.read_bytes());proxy.chmod(0o755)
                    elif kind=='symlink': proxy.symlink_to(rustup)
                    else: os.link(rustup,proxy)
                    selected.unlink(missing_ok=True)
                    try:
                        with patch.dict(os.environ,ambient,clear=True):
                            try:
                                count=policy.alias_probes(workflow,{'fixture'})
                            except AssertionError as exc:
                                self.fail(kind+' Cargo path rejected despite installed pinned binary: '+str(exc))
                        self.assertEqual(count,12)
                        self.assertEqual(set(selected.read_text().splitlines()),{'installed'},'proxy executed instead of installed Cargo')
                    finally:
                        proxy.unlink()
            # Missing/ambiguous installed directories must fail without a proxy run.
            proxy.symlink_to(rustup)
            other=toolchains/'1.98.0-other-host/bin/cargo';other.parent.mkdir(parents=True)
            other.write_bytes(binary.read_bytes());other.chmod(0o755)
            for kind in ('ambiguous','missing'):
                with self.subTest(kind=kind):
                    if kind=='missing': other.unlink();binary.unlink()
                    selected.unlink(missing_ok=True)
                    with patch.dict(os.environ,ambient,clear=True):
                        with self.assertRaises(AssertionError): policy.alias_probes(workflow,{'fixture'})
                    self.assertFalse(selected.exists(),'invalid installed inventory dispatched a proxy')


class WorkflowTests(unittest.TestCase):
    def test_real_workflow_and_future_discovered_root(self):
        roots = policy.discover_required_roots(ROOT)
        self.assertEqual(len(roots), 4)
        self.assertIn(policy.NATIVE_ROOT, roots)
        self.assertEqual(policy.problems(policy.load_workflow(), roots), [])
        self.assertTrue(policy.problems(policy.load_workflow(), roots | {'future/workspace'}))

    def test_frozen_audit_cannot_precede_checkout_coverage_or_install(self):
        good=policy.load_workflow();roots=policy.discover_required_roots(ROOT)
        self.assertEqual(policy.problems(good,roots),[])
        for index in (0,1,2):
            with self.subTest(index=index):
                candidate=copy.deepcopy(good);steps=candidate['jobs']['audit']['steps']
                step=next(s for s in steps if s.get('working-directory')==policy.NATIVE_ROOT)
                steps.remove(step);steps.insert(index,step)
                self.assertTrue(policy.problems(candidate,roots),f'frozen audit accepted before prerequisite {index}')
        for index in (0,1,2):
            with self.subTest(masked=index):
                candidate=copy.deepcopy(good)
                candidate['jobs']['audit']['steps'][index]['if']='false'
                self.assertTrue(policy.problems(candidate,roots),'masked audit prerequisite accepted')
        candidate=copy.deepcopy(good)
        next(s for s in candidate['jobs']['audit']['steps'] if s.get('working-directory')==policy.NATIVE_ROOT)['working-directory']='elsewhere'
        self.assertTrue(policy.problems(candidate,roots),'relocated audit accepted')

    def test_lint_toolchain_setup_must_be_pinned_unmasked_and_before_controls(self):
        good=policy.load_workflow();roots=policy.discover_required_roots(ROOT)
        steps=good['jobs']['lint-workflows']['steps']
        steps[:]=[s for s in steps if not str(s.get('uses','')).startswith('dtolnay/rust-toolchain@')]
        steps.insert(1,{'uses':'dtolnay/rust-toolchain@stable','with':{'toolchain':'1.98.0'}})
        self.assertEqual(policy.problems(good,roots),[])
        for mode in ('missing','masked','wrong version','components','duplicate','late'):
            with self.subTest(mode=mode):
                candidate=copy.deepcopy(good);steps=candidate['jobs']['lint-workflows']['steps'];step=steps[1]
                if mode=='missing': steps.pop(1)
                elif mode=='masked': step['if']='false'
                elif mode=='wrong version': step['with']['toolchain']='stable'
                elif mode=='components': step['with']['components']='clippy'
                elif mode=='duplicate': steps.append(copy.deepcopy(step))
                elif mode=='late': steps.append(steps.pop(1))
                self.assertTrue(policy.problems(candidate,roots),'invalid hosted lint toolchain accepted: '+mode)

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
