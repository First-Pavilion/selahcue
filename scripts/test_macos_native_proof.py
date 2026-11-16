"""Pure fixture gates. These tests never launch a native executable."""
import builtins
import copy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = importlib.import_module('scripts.macos_native_fixtures')

    def test_wire_preserves_insertion_unicode_and_terminal_lf(self):
        self.assertEqual(self.f.wire({'z': 'é🥁', 'a': 1}), '{"z":"é🥁","a":1}'.encode())
        self.assertEqual(self.f._batch('probe', [{'z': 1}, {'a': 2}]).stdin, b'{"z":1}\n{"a":2}\n')

    def test_exact_batch_counts_and_rejection_codes(self):
        batches, checks = self.f.prepare_batches()
        self.assertEqual([(b.name,len(b.frames)) for b in batches], [
            ('matrix',1024),('translations',8),('content',1),('helper scan',1),('Unicode',64),
            ('scalar caps',3),('list caps',2),('wrapper',3),('raw digest',2),('public cap',1),('combined scriptures',2)])
        self.assertEqual(len(checks),47)
        self.assertTrue(all(c.passed for c in checks))
        self.assertEqual(sum(c.name.endswith(':options_invalid') for c in checks),10)
        self.assertEqual(sum(c.name.endswith(':local_contract') for c in checks),36)
        self.assertEqual(sum(c.name.endswith(':byte_limit') for c in checks),1)
        self.assertLessEqual(sum(len(b.stdin) for b in batches),32*1024*1024)
        self.assertTrue(all(len(line)+1<=1100000 for b in batches for line in b.stdin.split(b'\n')[:-1]))

    def test_historical_matrix_and_wrapper_pins(self):
        batches,_ = self.f.prepare_batches(); by={b.name:b for b in batches}
        self.assertEqual(hashlib.sha256(by['matrix'].stdin).hexdigest(), 'bb4d75ea9bd6d18b42b5bc24eddfe1f4378f947aea6d572172828a9f226432d9')
        for frame,(size,digest) in zip(by['wrapper'].frames,[(524288,'dfdf3fb42fc1ce910f72c3662e1574ed9fe2c1824eb9afb838dd6e7169d920ef'),(524289,'a90bd62fcf791441a48eeb90b2440e7dcca2ab9386e7d2dc7c2b4e086c93710c'),(528326,'3d1a558349289d600fab3fcbf2a2492c074e9efbb53d2fefb688440f8fda5899')]):
            raw=frame['draft_json'].encode()
            self.assertEqual(len(raw),4238)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),'9596a90312891c2a348f0089bfff9f739f5e2dfcb82a8d54f532aea10fcbcba8')
            env=b'{"output":[{"content":[{"text":'+json.dumps(raw.decode(),ensure_ascii=False,separators=(',',':')).encode()+b',"type":"output_text"}]}]}' + b' '*frame['envelope_suffix_spaces']
            self.assertEqual((len(env),hashlib.sha256(env).hexdigest()),(size,digest))

    def test_public_cap_exact_selection_and_scalar_lengths(self):
        batches,_=self.f.prepare_batches();raw=next(b for b in batches if b.name=='public cap').frames[0]['draft_json'].encode()
        self.assertEqual(len(raw),262144);points=json.loads(raw)['points']
        texts=[s for p in points for s in [p['text'],*p['sub_points']]]
        self.assertEqual(len(points),32);self.assertEqual(len(points[0]['sub_points']),16)
        self.assertEqual(len(texts),96);self.assertTrue(all(len(s)==2000 for s in texts))

    def test_bundle_drift_missing_extra_symlink_and_forged_golden_rejected(self):
        self.assertEqual(self.f.verify_inputs()['payload_count'],29)
        for mutation in ('drift','missing','extra','extra-dir','root-extra','symlink','forged'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve()/'bundle';shutil.copytree(self.f.BUNDLE,root)
                with patch.object(self.f,'BUNDLE',root):self.assertEqual(self.f.verify_inputs()['payload_count'],29)
                victim=root/'payloads/fixtures/native/matrix-golden.json'
                if mutation=='drift':victim.write_bytes(victim.read_bytes()+b' ')
                if mutation=='missing':victim.unlink()
                if mutation=='extra':(root/'payloads/extra').write_text('extra')
                if mutation=='extra-dir':(root/'payloads/unapproved').mkdir()
                if mutation=='root-extra':(root/'unexpected.json').write_text('{}')
                if mutation=='symlink':victim.unlink();victim.symlink_to(root/'inputs.json')
                if mutation=='forged':
                    data=json.loads((root/'inputs.json').read_bytes());data['historical']['matrix_output']='0'*64
                    (root/'inputs.json').write_text(json.dumps(data))
                with patch.object(self.f,'BUNDLE',root),self.assertRaises(self.f.ProofError):self.f.verify_inputs()

    def test_mutable_manifest_cannot_replace_literal_historical_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()/'bundle';shutil.copytree(self.f.BUNDLE,root)
            manifest=json.loads((root/'inputs.json').read_bytes())
            manifest['historical']['matrix_output']='0'*64
            raw=json.dumps(manifest,indent=2).encode()+b'\n';(root/'inputs.json').write_bytes(raw)
            # Even after deliberately bypassing the outer manifest identity in
            # this unit test, expected observations remain literal source pins.
            with patch.object(self.f,'BUNDLE',root),patch.object(self.f,'INPUTS_SHA256',hashlib.sha256(raw).hexdigest()),self.assertRaisesRegex(self.f.ProofError,'historical oracle identity'):
                self.f.verify_inputs()

    def test_loader_ignores_ambient_coverage_modules(self):
        import sys
        from types import ModuleType
        poison=ModuleType('coverage_contract')
        poison.public_schema=lambda _: (_ for _ in ()).throw(AssertionError('ambient module imported'))
        with patch.dict(sys.modules,{'coverage_contract':poison}):
            modules=self.f._modules()
            self.assertEqual(set(modules),{'coverage_contract','coverage_json','coverage_index','coverage_compile','coverage_requests','coverage_response'})
            self.assertIsNot(modules['coverage_contract'],poison)
            expected=json.loads((self.f.BUNDLE/'payloads/fixtures/contract/baseline-public-schema.json').read_bytes())
            self.assertEqual(modules['coverage_contract'].public_schema(self.f.options()),expected)

    def test_observation_key_order_is_preserved_in_receipt_digest(self):
        batches,_=self.f.prepare_batches();batch=next(b for b in batches if b.name=='translations')
        rows=self._translation_rows(batch)
        forward=self.f.check_observations('translations',b''.join(self.f.wire(row)+b'\n' for row in rows))
        reverse=self.f.check_observations('translations',b''.join(self.f.wire(dict(reversed(list(row.items()))))+b'\n' for row in rows))
        self.assertNotEqual(forward['observations_sha256'],reverse['observations_sha256'])

    def test_frozen_manifest_identity_and_source_mutations_rejected(self):
        manifest=json.loads((self.f.BUNDLE/'frames.json').read_bytes())
        self.assertEqual(manifest['comparator']['sha256'],hashlib.sha256(Path(self.f.__file__).read_bytes()).hexdigest())
        for mutation in ('missing','symlink','bytes','batch-digest','count','rejection','oracle','source-pin','extra'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve()/'bundle';shutil.copytree(self.f.BUNDLE,root)
                with patch.object(self.f,'BUNDLE',root):self.assertEqual(self.f.verify_inputs()['payload_count'],29)
                path=root/'frames.json';data=json.loads(path.read_bytes())
                if mutation=='missing':path.unlink()
                elif mutation=='symlink':path.unlink();path.symlink_to(root/'inputs.json')
                elif mutation=='bytes':path.write_bytes(path.read_bytes()+b' ')
                else:
                    if mutation=='batch-digest':data['batches'][1]['sha256']='0'*64
                    if mutation=='count':data['batches'][1]['count']=9
                    if mutation=='rejection':data['pure_rejections'][0]='option-0:local_contract'
                    if mutation=='oracle':data['historical']['matrix_output']='0'*64
                    if mutation=='source-pin':data['comparator']['sha256']='0'*64
                    if mutation=='extra':data['extra']='unapproved'
                    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
                with patch.object(self.f,'BUNDLE',root),self.assertRaises(self.f.ProofError):self.f.verify_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp).resolve()/'macos_native_fixtures.py'
            source.write_bytes(Path(self.f.__file__).read_bytes())
            with patch.object(self.f,'__file__',str(source)):
                self.assertEqual(self.f.verify_inputs()['payload_count'],29)
                source.write_bytes(source.read_bytes()+b'\n# unreviewed change\n')
                with self.assertRaises(self.f.ProofError):self.f.verify_inputs()

    def test_independently_frozen_nonhistorical_batch_drift_rejected(self):
        original=self.f._batch
        def changed(name,frames):
            batch=original(name,frames)
            if name=='translations':return self.f.Batch(batch.name,batch.frames,batch.stdin+b' ')
            return batch
        with patch.object(self.f,'_batch',side_effect=changed),self.assertRaises(self.f.ProofError):
            self.f.prepare_batches()

    def test_manifest_outer_comparator_relocation_rejected_in_memory(self):
        original=self.f._regular
        path=self.f.BUNDLE/'frames.json'
        raw=original(path);manifest=json.loads(raw)
        moved={'comparator':manifest['comparator'],**{k:v for k,v in manifest.items() if k!='comparator'}}
        changed=(json.dumps(moved,ensure_ascii=False,indent=2)+'\n').encode()
        self.assertNotEqual(changed,raw)
        self.assertEqual(self.f.verify_inputs()['frames_sha256'],hashlib.sha256(raw).hexdigest())
        with patch.object(self.f,'_regular',side_effect=lambda p: changed if p==path else original(p)),self.assertRaises(self.f.ProofError):
            self.f.verify_inputs()

    def test_manifest_inner_comparator_key_reorder_rejected_in_memory(self):
        original=self.f._regular
        path=self.f.BUNDLE/'frames.json'
        raw=original(path);manifest=json.loads(raw)
        manifest['comparator']=dict(reversed(list(manifest['comparator'].items())))
        changed=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
        self.assertNotEqual(changed,raw)
        self.assertEqual(self.f.verify_inputs()['frames_sha256'],hashlib.sha256(raw).hexdigest())
        with patch.object(self.f,'_regular',side_effect=lambda p: changed if p==path else original(p)),self.assertRaises(self.f.ProofError):
            self.f.verify_inputs()

    def test_loader_rejects_each_producer_divergent_read_before_compile(self):
        original=self.f._regular
        for name in self.f.MODULES:
            with self.subTest(module=name):
                path=self.f.BUNDLE/'payloads'/(name+'.py')
                valid=original(path);reads=[]
                def divergent(p):
                    if p!=path:return original(p)
                    reads.append(p)
                    return valid if len(reads)==1 else valid+b'\n_UNVERIFIED_PRODUCER = True\n'
                with patch.object(self.f,'_regular',side_effect=divergent),patch.object(self.f,'compile',wraps=builtins.compile,create=True) as compiled:
                    with self.assertRaises(self.f.ProofError):self.f._modules()
                self.assertEqual(len(reads),2)
                approved={hashlib.sha256(original(self.f.BUNDLE/'payloads'/(module+'.py'))).hexdigest() for module in self.f.MODULES}
                self.assertTrue(all(hashlib.sha256(call.args[0]).hexdigest() in approved for call in compiled.call_args_list))

    def test_fixture_rejects_divergent_read_before_parsing(self):
        original=self.f._regular
        path=self.f.BUNDLE/'payloads/fixtures/native/content.json'
        valid=original(path);data=json.loads(valid);data['title']='unverified oracle'
        changed=json.dumps(data,ensure_ascii=False).encode();reads=[]
        def divergent(p):
            if p!=path:return original(p)
            reads.append(p)
            return valid if len(reads)==1 else changed
        with patch.object(self.f,'_regular',side_effect=divergent):
            self.f.verify_inputs()
            with patch.object(self.f,'_json',wraps=self.f._json) as parsed:
                with self.assertRaises(self.f.ProofError):self.f._fixture('native/content.json')
            self.assertNotIn(changed,[call.args[0] for call in parsed.call_args_list])
        self.assertEqual(len(reads),2)

    def _default_row(self, frame):
        """Hand-written expected default observation, never captured from native."""
        envelope = b'{"output":[{"content":[{"text":' + json.dumps(frame['draft_json'],ensure_ascii=False,separators=(',',':')).encode() + b',"type":"output_text"}]}]}' + b' '*frame.get('envelope_suffix_spaces',0)
        schema=json.loads((self.f.BUNDLE/'payloads/fixtures/contract/baseline-public-schema.json').read_bytes())
        return {
            'envelope_bytes':len(envelope),'envelope_sha256':hashlib.sha256(envelope).hexdigest(),
            'raw_bytes':len(frame['draft_json'].encode()),'raw_sha256':hashlib.sha256(frame['draft_json'].encode()).hexdigest(),
            'status':'parsed','clamped':False,'options':frame['options'],'schema':schema,
            'title':'Sermon notes','summary':None,'scriptures':[],
            'sections':[
                {'heading':'Main points','items':[],'points':[{'text':'Remain steady.','sub_points':[]}]},
                {'heading':'Introduction','items':[],'points':[]},
                {'heading':'Illustrations','items':[],'points':[]},
                {'heading':'Notable quotations','items':[],'points':[]},
                {'heading':'Prayer points','items':[],'points':[]},
                {'heading':'Calls to action','items':[],'points':[]},
                {'heading':'Key lessons','items':[],'points':[]},
                {'heading':'Chapter markers','items':[],'points':[]}],
            'caveats':['Summary','Scripture references','Introduction','Illustrations','Notable quotations',
                       'Prayer points','Calls to action','Key lessons','Chapter markers'],
            'attached_scripture_verdict_count':0,'attached_timestamp_count':0,
            'picker_translations':['KJV','WEB','ASV','WEBBE','DBY'],'persisted_translation':'KJV'}

    def _translation_rows(self, batch):
        parts=json.loads((self.f.BUNDLE/'payloads/fixtures/requests/native-prompt-parts.json').read_bytes())
        rows=[]
        for frame,persisted in zip(batch.frames,['KJV','WEB','ASV','WEBBE','DBY','x'*16,'é'*8,'a'*15],strict=True):
            row=self._default_row(frame);row['persisted_translation']=persisted
            row['legacy_build_body']={'transport_calls':0,'clamped':False,'schema':row['schema'],
                'developer':parts['introduction']+parts['translation'].format(frame['options']['preferred_translation'])+parts['full_outline_scriptures']}
            rows.append(row)
        return rows

    def _assert_row_mutations_fail(self,name,index,frame,row):
        contract=self.f._modules()['coverage_contract']
        self.f._check_row(name,index,frame,row,contract)
        # Every field, including nested status/type/count/order/content, must bite.
        def mutations(value,path=()):
            if isinstance(value,dict):
                for key,item in value.items():yield from mutations(item,path+(key,))
                yield path,None
            elif isinstance(value,list):
                yield path,[] if value else ['unexpected']
                if len(value)>1:yield path,list(reversed(value))
                for i,item in enumerate(value):yield from mutations(item,path+(i,))
            elif isinstance(value,bool):yield path,not value
            elif isinstance(value,int):yield path,value+1;yield path,bool(value)
            elif value is None:yield path,'unexpected'
            else:yield path,'corrupt'
        count=0
        for path,replacement in mutations(row):
            mutated=copy.deepcopy(row)
            if not path:mutated=replacement
            else:
                parent=mutated
                for part in path[:-1]:parent=parent[part]
                parent[path[-1]]=replacement
            if mutated==row:continue
            with self.subTest(batch=name,path=path),self.assertRaises((self.f.ProofError,TypeError)):
                self.f._check_row(name,index,frame,mutated,contract)
            count+=1
        self.assertGreater(count,40)

    def test_translation_semantics_and_each_observed_field_mutation(self):
        batches,_=self.f.prepare_batches();batch=next(b for b in batches if b.name=='translations')
        rows=self._translation_rows(batch)
        receipt=self.f.check_observations('translations',b''.join(self.f.wire(r)+b'\n' for r in rows))
        self.assertEqual(receipt['count'],8)
        self.assertNotIn('draft_json',receipt)
        self._assert_row_mutations_fail('translations',6,batch.frames[6],rows[6])

    def test_content_and_helper_semantics_with_fixed_rows(self):
        batches,_=self.f.prepare_batches();by={b.name:b for b in batches}
        fixture=json.loads((self.f.BUNDLE/'payloads/fixtures/native/content.json').read_bytes())
        row=self._default_row(by['content'].frames[0])
        row.update(title=fixture['title'],summary=fixture['summary'],
                   scriptures=[fixture['main_scripture'],*fixture['supporting_scriptures']],
                   caveats=['Introduction','Illustrations','Prayer points','Calls to action','Key lessons'],
                   helper_scripture_verdicts=fixture['scripture_verdicts'],helper_scripture_scan_truncated=False,
                   helper_timestamps=[
                       {'heading':'Main points','text':'Steady hands gather baskets.','offset_ms':1000},
                       {'heading':'Main points','text':'Share freely.','offset_ms':9000},
                       {'heading':'Chapter markers','text':'Steady hands gather baskets.','offset_ms':1000},
                       {'heading':'Chapter markers','text':'Interlude','offset_ms':5000},
                       {'heading':'Chapter markers','text':'Share freely.','offset_ms':9000}])
        row['sections'][0]['points']=fixture['points'];row['sections'][3]['items']=fixture['quotes']
        row['sections'][7]['items']=fixture['chapter_markers']
        self.assertEqual(self.f.check_observations('content',self.f.wire(row)+b'\n')['count'],1)
        self._assert_row_mutations_fail('content',0,by['content'].frames[0],row)
        helper=self._default_row(by['helper scan'].frames[0])
        helper['sections'][2]['items']=[' '.join(f'Psalms {i}:1' for i in range(1,66))]
        helper['caveats'].remove('Illustrations')
        helper.update(helper_scripture_scan_truncated=True,helper_timestamps=[],
                      helper_scripture_verdicts=[{'reference':f'Psalms {i}:1','verified':True} for i in range(1,65)])
        self.assertEqual(self.f.check_observations('helper scan',self.f.wire(helper)+b'\n')['count'],1)
        self._assert_row_mutations_fail('helper scan',0,by['helper scan'].frames[0],helper)

    def test_raw_digest_and_wrapper_exact_error_rows(self):
        batches,_=self.f.prepare_batches();by={b.name:b for b in batches}
        good=self._default_row(by['raw digest'].frames[1])
        self.assertEqual(self.f.check_observations('raw digest',self.f.wire({'status':'digest_mismatch'})+b'\n'+self.f.wire(good)+b'\n')['count'],2)
        contract=self.f._modules()['coverage_contract']
        for bad in ({'status':'parsed'},{'status':'digest_mismatch','extra':1}):
            with self.assertRaises(self.f.ProofError):self.f._check_row('raw digest',0,by['raw digest'].frames[0],bad,contract)
        rows=json.loads((self.f.BUNDLE/'payloads/fixtures/native/wrapper-golden.json').read_bytes())
        for index in (1,2):
            self.f._check_row('wrapper',index,by['wrapper'].frames[index],rows[index],contract)
            for key in rows[index]:
                changed=copy.deepcopy(rows[index]);changed[key]=None
                with self.subTest(key=key),self.assertRaises(self.f.ProofError):self.f._check_row('wrapper',index,by['wrapper'].frames[index],changed,contract)
        parsed=self._default_row(by['wrapper'].frames[0]);parsed['sections'][0]['points'][0]['text']='"\\'*1000
        self.assertEqual(self.f.check_observations('wrapper',b''.join(self.f.wire(r)+b'\n' for r in [parsed,*rows[1:]]))['count'],3)

    def test_matrix_historical_output_hash_is_an_independent_gate(self):
        batches,_=self.f.prepare_batches();matrix=batches[0]
        # Isolate the fixed hash gate after structural checks. This deliberately
        # fake row is never represented as a native observation or accepted pass.
        fake=self.f.wire({'status':'corrupt-observation'})+b'\n'
        with patch.object(self.f,'_check_row',return_value=[]),self.assertRaisesRegex(self.f.ProofError,'historical matrix observation mismatch'):
            self.f.check_observations('matrix',fake*len(matrix.frames))

    def test_preparation_has_zero_processes_and_rejects_frame_overflow(self):
        with patch('subprocess.Popen',side_effect=AssertionError('native invocation forbidden')) as process:
            self.f.prepare_batches()
            process.assert_not_called()
        with patch.object(self.f,'MAX_FRAME',8),self.assertRaises(self.f.ProofError):
            self.f._batch('oversized',[{'payload':'longer than eight'}])
        with patch.object(self.f,'MAX_STDIN',8),self.assertRaises(self.f.ProofError):
            self.f.prepare_batches()

    def test_output_framing_and_bounds_rejected(self):
        for raw in (b'',b'{}',b'{}\n\n',b'[]\n',b'not-json\n',b'{}\n'*3,b'{"status":"parsed","status":"digest_mismatch"}\n'):
            with self.subTest(raw=raw),self.assertRaises(self.f.ProofError):self.f.check_observations('raw digest',raw)
        with patch.object(self.f,'MAX_STDOUT',8),self.assertRaises(self.f.ProofError):self.f.check_observations('raw digest',b'123456789\n')
        with patch.object(self.f,'MAX_LINE',8),self.assertRaises(self.f.ProofError):self.f.check_observations('raw digest',b'123456789\n')


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.p = importlib.import_module('scripts.macos_native_proof')
        except ModuleNotFoundError:
            self.fail('Task2 orchestration module is absent')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_setup_metadata_closed_identity_and_regular_file(self):
        p = self.root/'toolchain.json'
        raw = self.p.TOOLCHAIN_FILE.read_bytes()
        p.write_bytes(raw)
        with patch.object(self.p, 'TOOLCHAIN_FILE', p):
            self.assertEqual(self.p.load_toolchain()['release'], '1.98.0')
            for bad in (raw+b' ', b'{}'):
                p.write_bytes(bad)
                with self.assertRaises(self.p.Failure): self.p.load_toolchain()
            p.unlink(); p.symlink_to(self.p.REPO/'scripts/fixtures/macos-native-toolchain.json')
            with self.assertRaises(self.p.Failure): self.p.load_toolchain()

    def test_hosted_guard_rejects_local_rerun_wrong_ref_or_untrusted_environment(self):
        good = {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted',
                'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40,
                'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/main',
                'GITHUB_REPOSITORY':'First-Pavilion/selahcue',
                'ImageOS':'macos26','ImageVersion':'20261116.1'}
        self.assertEqual(self.p.run_identity(good)['head'], 'a'*40)
        for key, value in [('GITHUB_ACTIONS','false'),('RUNNER_ENVIRONMENT','self-hosted'),
                           ('GITHUB_RUN_ATTEMPT','2'),('GITHUB_REF','refs/heads/dev'),
                           ('GITHUB_SHA','abc'),('GITHUB_EVENT_NAME','push'),('ImageVersion','')]:
            with self.subTest(key=key), self.assertRaises(self.p.Failure):
                self.p.run_identity(good | {key:value})

    def test_clean_environment_does_not_inherit_home_git_cargo_or_credentials(self):
        poison={'HOME':'/foreign','GIT_CONFIG_GLOBAL':'/evil','GIT_CONFIG_COUNT':'1',
                'CARGO_HOME':'/foreign','CARGO_CONFIG':'/evil','CARGO_REGISTRIES_CRATES_IO_TOKEN':'secret',
                'AWS_SECRET_ACCESS_KEY':'secret','RUSTC_WRAPPER':'/evil'}
        with patch.dict('os.environ',poison): env=self.p.setup_environment(self.root)
        self.assertEqual(env['HOME'],str(self.root/'home'))
        self.assertEqual(env['CARGO_HOME'],str(self.root/'cargo'))
        self.assertEqual(env['GIT_CONFIG_GLOBAL'],'/dev/null')
        self.assertFalse(any(value in ('/evil','/foreign','secret') for value in env.values()))
        self.assertEqual(env['CARGO_REGISTRIES_CRATES_IO_PROTOCOL'],'sparse')

    def test_resource_admission_and_two_rising_samples(self):
        good={'physical_bytes':7*1024**3,'disk_free_bytes':9*1024**3,
              'pressure':1,'pageouts':5,'swapouts':6,'free_bytes':4*1024**3,'swap':'total = 0'}
        self.p.admit_resources([good,good,good])
        for key,value in [('physical_bytes',5*1024**3),('disk_free_bytes',7*1024**3),('pressure',2)]:
            with self.subTest(key=key), self.assertRaises(self.p.Failure):
                self.p.admit_resources([good|{key:value}]*3)
        with self.assertRaises(self.p.Failure):self.p.admit_resources([good,good|{'pageouts':6},good])
        monitor=self.p.PagingMonitor()
        monitor.observe(good);monitor.observe(good|{'pageouts':6})
        with self.assertRaises(self.p.Failure):monitor.observe(good|{'pageouts':7})

    def test_exclusive_ownership_preserves_foreign_and_symlink_paths(self):
        journal=self.p.Ownership(self.root/'state', {'run_id':'123','head':'a'*40})
        journal.initialize()
        owned=self.root/'owned';journal.create(owned)
        (owned/'child').write_text('job output')
        foreign=self.root/'foreign';foreign.mkdir();(foreign/'keep').write_text('keep')
        with self.assertRaises(self.p.Failure):journal.create(foreign)
        link=self.root/'link';link.symlink_to(foreign,target_is_directory=True)
        with self.assertRaises(self.p.Failure):journal.create(link/'child')
        report=journal.cleanup()
        self.assertFalse(owned.exists());self.assertTrue((foreign/'keep').exists())
        self.assertEqual(report['removed'],[str(owned)])
        self.assertTrue(journal.state.exists())

    def test_cleanup_refuses_replaced_owner_or_symlink_descendant(self):
        for mutation in ('replace','symlink'):
            with self.subTest(mutation=mutation):
                base=self.root/mutation;base.mkdir()
                journal=self.p.Ownership(base/'state', {'run_id':'123','head':'a'*40});journal.initialize()
                owned=base/'owned';journal.create(owned)
                foreign=base/'foreign';foreign.mkdir();(foreign/'keep').write_text('keep')
                if mutation=='replace':owned.rename(base/'old');owned.mkdir()
                else:(owned/'link').symlink_to(foreign,target_is_directory=True)
                with self.assertRaises(self.p.Failure):journal.cleanup()
                self.assertTrue(owned.exists());self.assertTrue((foreign/'keep').exists())

    def test_early_cleanup_has_no_authority_and_stale_run_cannot_resume(self):
        journal=self.p.Ownership(self.root/'state', {'run_id':'123','head':'a'*40})
        foreign=self.root/'foreign';foreign.mkdir()
        self.assertEqual(journal.cleanup()['removed'],[])
        journal.initialize()
        stale=self.p.Ownership(journal.state, {'run_id':'124','head':'a'*40})
        with self.assertRaises(self.p.Failure):stale.load()
        self.assertTrue(foreign.exists())

    def test_process_pump_bounds_timeout_and_reaps_only_its_group(self):
        import sys
        runner=self.p.ProcessRunner()
        result=runner.run([sys.executable,'-I','-S','-c','import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())'],
                          cwd=self.root,env={'PATH':'/usr/bin:/bin'},timeout=2,stdin=b'bounded\n')
        self.assertEqual(result.stdout,b'bounded\n');self.assertEqual(result.returncode,0)
        for script, options in [
            ('print("x"*1000)',{'stdout_limit':100}),
            ('print("x"*1000)',{'line_limit':100}),
            ('import sys;sys.stderr.write("x"*1000)',{'stderr_limit':100}),
            ('import time;time.sleep(2)',{'timeout':0.05})]:
            with self.subTest(script=script),self.assertRaises(self.p.Failure):
                runner.run([sys.executable,'-I','-S','-c',script],cwd=self.root,env={'PATH':'/usr/bin:/bin'},
                           **({'timeout':2}|options))

    def test_registry_integrity_rejects_archive_file_and_tuple_drift(self):
        registry=self.root/'registry';source=registry/'src/index.crates.io-test/pkg-1.0.0'
        cache=registry/'cache/index.crates.io-test';source.mkdir(parents=True);cache.mkdir(parents=True)
        (registry/'index/index.crates.io-test').mkdir(parents=True)
        (registry/'index/index.crates.io-test/config.json').write_text('{"dl":"https://static.crates.io/crates","api":"https://crates.io"}')
        import io,tarfile
        with tarfile.open(cache/'pkg-1.0.0.crate','w:gz') as tar:
            member=tarfile.TarInfo('pkg-1.0.0/lib.rs');member.size=6;tar.addfile(member,io.BytesIO(b'public'))
        raw=(cache/'pkg-1.0.0.crate').read_bytes();digest=hashlib.sha256(raw).hexdigest()
        (source/'lib.rs').write_bytes(b'public')
        (source/'.cargo-checksum.json').write_text(json.dumps({'package':digest,'files':{'lib.rs':hashlib.sha256(b'public').hexdigest()}}))
        tuples=[['pkg','1.0.0','registry+https://github.com/rust-lang/crates.io-index',digest]]
        self.assertEqual(self.p.verify_registry(registry,tuples)['packages'],1)
        for mutation in ('archive','file','missing','extra'):
            with self.subTest(mutation=mutation):
                if mutation=='archive':(cache/'pkg-1.0.0.crate').write_bytes(b'bad')
                if mutation=='file':(source/'lib.rs').write_bytes(b'bad')
                if mutation=='missing':(source/'lib.rs').unlink()
                if mutation=='extra':(source/'unapproved').write_bytes(b'x')
                with self.assertRaises(self.p.Failure):self.p.verify_registry(registry,tuples)
                (cache/'pkg-1.0.0.crate').write_bytes(raw);(source/'lib.rs').write_bytes(b'public')

    def test_artifact_export_requires_exact_members_and_20mib_limit(self):
        stage=self.root/'receipts';stage.mkdir();target=self.root/'export'
        for name in self.p.RECEIPT_MEMBERS:(stage/name).write_bytes(b'{}\n' if name.endswith('.json') else b'features\n')
        manifest=self.p.export_members(stage,target)
        self.assertEqual(len(manifest['members']),8)
        self.assertEqual({p.name for p in target.iterdir()},set(self.p.RECEIPT_MEMBERS)|{'artifact-manifest.json'})
        for mutation in ('missing','extra','symlink','oversize'):
            with self.subTest(mutation=mutation):
                victim=stage/'proof.json'
                if mutation=='missing':victim.unlink()
                if mutation=='extra':(stage/'source.rs').write_text('private')
                if mutation=='symlink':victim.unlink();victim.symlink_to(stage/'run.json')
                if mutation=='oversize':victim.write_bytes(b'x'*(20*1024*1024))
                with self.assertRaises(self.p.Failure):self.p.export_members(stage,self.root/mutation)
                if victim.is_symlink():victim.unlink()
                victim.write_bytes(b'{}\n')
                if (stage/'source.rs').exists():(stage/'source.rs').unlink()


class StageTests(unittest.TestCase):
    def setUp(self):
        self.p=importlib.import_module('scripts.macos_native_proof')
        self.assertTrue(hasattr(self.p,'ProofRun'), 'Task2 stage orchestration is absent')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.env={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','GITHUB_RUN_ID':'123',
                  'GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40,'GITHUB_EVENT_NAME':'workflow_dispatch',
                  'GITHUB_REF':'refs/heads/main','GITHUB_REPOSITORY':'First-Pavilion/selahcue',
                  'ImageOS':'macos26','ImageVersion':'20261116.1'}
        # The real ownership/receipt machinery runs. Side-effectful host queries,
        # provisioning and subprocesses use an explicit inert backend. No fake
        # reads/stages application sources, runs Cargo or contacts the network.
        self.host=InertHost(self.p)
        self.run=self.p.ProofRun(self.host, self.root/'state', self.root/'export', self.env)
        self.addCleanup(patch.stopall)
        patch.object(self.run,'_inputs',return_value={'inputs_sha256':'b'*64,'frames_sha256':'c'*64,
                                                    'comparator_sha256':'d'*64,'native_executed':False}).start()
        patch.object(self.run,'_paths_absent',return_value=None).start()
        patch.object(self.run,'_source_check',return_value={'files':102}).start()
        patch.object(self.run,'_stage_inputs',return_value=None).start()
        patch.object(self.run,'_install',return_value={'verified':True}).start()
        patch.object(self.run,'_installed_check',return_value={'verified':True},create=True).start()
        patch.object(self.run,'_fetch',return_value={'packages':56}).start()
        patch.object(self.run,'_postcheck',return_value={'files':102}).start()
        patch.object(self.run,'_metadata',return_value={'tuples':[['fake']], 'local_features':self.p.FEATURES}).start()
        patch.object(self.run,'_build_receipt',side_effect=self.fake_build_receipt).start()
        from types import SimpleNamespace
        self.batches=[SimpleNamespace(name=name,frames=[{}]*count,stdin=b'{}\n'*count) for name,count in self.p.fixtures.BATCH_COUNTS]
        self.rejects=[SimpleNamespace(name='inert-reject-'+str(i),passed=True) for i in range(47)]
        patch.object(self.run,'_batches',return_value=(self.batches,self.rejects)).start()
        for name in ('O','BINARY','BUILDER','WORK'):
            patch.object(self.p,name,self.root/name).start()
        patch.object(self.p.fixtures,'check_observations',side_effect=lambda name,stdout: {'name':name,'count':dict(self.p.fixtures.BATCH_COUNTS)[name], 'stdout_bytes':len(stdout),'checks':['inert-comparator']}).start()

    def fake_build_receipt(self):
        # Explicit inert raw receipts; never claim actual compilation.
        self.run._receipt_bytes('build.json',b'{"inert":true}\n')
        self.run._receipt_bytes('feature-tree.txt',b'inert features\n')
        return {'binary_sha256':'e'*64}

    def test_each_admission_failure_prevents_builder_and_records_failure(self):
        for fault in ('platform','memory','paging','disk','clone','normative'):
            with self.subTest(fault=fault):
                self.host.fault=fault
                run=self.p.ProofRun(self.host,self.root/(fault+'-state'),self.root/(fault+'-export'),self.env)
                with patch.object(run,'_inputs',return_value=self.run._inputs()),patch.object(run,'_paths_absent'):
                    with self.assertRaises(self.p.Failure):run.admit_host()
                self.assertEqual(self.host.builder_calls,0)
                result=parse_test_receipt(run,'admission.json')
                self.assertEqual(result['status'],'failed');self.assertFalse(result['native_executed'])

    def test_setup_failures_stop_before_builder_and_stage_receipts_chain(self):
        self.run.admit_host()
        for method in ('_stage_inputs','_source_check','_install','_fetch','_metadata','_postcheck'):
            with self.subTest(method=method):
                # Every failure gets its own admitted run; failed setup is not
                # rerunnable against an old successful receipt.
                run=self.p.ProofRun(self.host,self.root/(method+'-state'),self.root/(method+'-export'),self.env)
                for name in ('_inputs','_paths_absent','_source_check','_stage_inputs','_install','_installed_check','_fetch','_postcheck','_metadata'):
                    patch.object(run,name,getattr(self.run,name)).start()
                run.admit_host()
                with patch.object(run,method,side_effect=self.p.Failure('injected '+method)):
                    with self.assertRaises(self.p.Failure):run.provision()
                with self.assertRaises(self.p.Failure):run.run_frozen()
                self.assertEqual(self.host.builder_calls,0)
                self.assertEqual(parse_test_receipt(run,'setup.json')['status'],'failed')

    def test_proof_requires_completed_setup_same_run_head_inputs(self):
        with self.assertRaises(self.p.Failure):self.run.run_frozen()
        self.run.admit_host();self.run.provision()
        changed=self.p.ProofRun(self.host,self.run.state,self.run.export,self.env|{'GITHUB_RUN_ID':'456'})
        with patch.object(changed,'_inputs',return_value=self.run._inputs()),self.assertRaises(self.p.Failure):changed.run_frozen()
        with patch.object(self.run,'_inputs',return_value={'inputs_sha256':'f'*64}):
            with self.assertRaises(self.p.Failure):self.run.run_frozen()
        self.assertEqual(self.host.builder_calls,0)

    def test_network_denial_failures_prevent_builder(self):
        self.run.admit_host();self.run.provision()
        self.host.fault='network'
        with self.assertRaises(self.p.Failure):self.run.run_frozen()
        self.assertEqual(self.host.builder_calls,0)
        self.assertEqual(parse_test_receipt(self.run,'proof.json')['status'],'failed')

    def test_builder_failure_is_once_only_and_receipts_never_claim_native_pass(self):
        self.run.admit_host();self.run.provision();self.host.fault='builder'
        with self.assertRaises(self.p.Failure):self.run.run_frozen()
        self.assertEqual(self.host.builder_calls,1)
        with self.assertRaises(self.p.Failure):self.run.run_frozen()
        self.assertEqual(self.host.builder_calls,1)
        proof=parse_test_receipt(self.run,'proof.json')
        self.assertEqual(proof['status'],'failed');self.assertFalse(proof['native_executed'])

    def test_inert_success_counts_and_postcheck_failure_are_not_native_evidence(self):
        self.run.admit_host();self.run.provision()
        # Empty fake batches must not become a successful 1111-frame proof.
        with patch.object(self.run,'_batches',return_value=([],[])),self.assertRaises(self.p.Failure):self.run.run_frozen()
        self.assertEqual(parse_test_receipt(self.run,'proof.json')['status'],'failed')
        self.assertFalse(parse_test_receipt(self.run,'proof.json')['native_executed'])

    def test_finalization_missing_build_outputs_and_interruption_fail_closed(self):
        self.run.admit_host()
        with self.assertRaises(self.p.Failure):self.run.export_receipts()
        self.assertFalse(self.run.export.exists())
        result=parse_test_receipt(self.run,'result.json')
        self.assertEqual(result['status'],'incomplete');self.assertFalse(result['native_executed'])
        with patch.object(self.run,'_postcheck',side_effect=KeyboardInterrupt):
            with self.assertRaises((self.p.Failure,KeyboardInterrupt)):self.run.export_receipts()
        self.assertFalse(self.run.export.exists())

    def test_cleanup_after_partial_setup_proof_or_upload_preserves_outcome_export(self):
        for phase in ('early','setup','proof','upload-failed','upload-success'):
            with self.subTest(phase=phase):
                run=self.p.ProofRun(self.host,self.root/(phase+'-state'),self.root/(phase+'-export'),self.env)
                if phase=='early':
                    self.assertEqual(run.cleanup()['removed'],[]);continue
                run._initialize(self.run._inputs())
                owned=self.root/(phase+'-owned');run.owner.create(owned)
                run._receipt('result.json',{'status':'failed','native_executed':False})
                run.export.mkdir();(run.export/'result.json').write_text('failed upload or proof')
                before=(run.export/'result.json').read_bytes()
                run.cleanup()
                self.assertFalse(owned.exists());self.assertEqual((run.export/'result.json').read_bytes(),before)
                self.assertEqual(parse_test_receipt(run,'result.json')['status'],'failed')


def parse_test_receipt(run,name):
    return json.loads((run.receipts/name).read_bytes())


class InertHost:
    native_executed=False
    def __init__(self,p):self.p=p;self.fault=None;self.builder_calls=0;self.commands=[]
    def clock(self):return 100.0
    def sleep(self,seconds):pass
    def facts(self):
        if self.fault=='platform':raise self.p.Failure('Darwin arm64 required')
        return {'system':'Darwin','machine':'arm64','python':[3,14],'macos':'26.0','xcode':'inert','sdk':'inert','clang':'inert'}
    def sample(self):
        good={'physical_bytes':7*1024**3,'disk_free_bytes':9*1024**3,'pressure':1,
              'pageouts':0,'swapouts':0,'free_bytes':4*1024**3,'swap':'total = 0'}
        if self.fault=='memory':good['physical_bytes']=1
        if self.fault=='disk':good['disk_free_bytes']=1
        if self.fault=='paging':good['pressure']=2
        return good
    def clone_probe(self,path):
        if self.fault=='clone':raise self.p.Failure('clone unavailable')
        return {'apfs_clone':True}
    def command(self,argv,**kwargs):
        self.commands.append(argv)
        if kwargs.get('on_start'):kwargs['on_start']()
        if 'merge-base' in argv and self.fault=='normative':raise self.p.Failure('missing normative commit')
        if argv[-1:] == ['HEAD']:out=b'a'*40+b'\n'
        else:out=b''
        if str(self.p.BUILDER) in argv and '--verify' not in argv:
            self.builder_calls+=1
            if self.fault=='builder':raise self.p.Failure('builder failed')
        return self.p.CommandResult(0,out,b'')
    def network_probe(self,**kwargs):
        if self.fault=='network':raise self.p.Failure('network denial unavailable')
        return {'denied':True}


class HardenedOrchestrationTests(unittest.TestCase):
    setUp = OrchestrationTests.setUp
    # Reuse only the import/temp-directory setup, not the earlier test methods.
    def test_registry_checksum_manifest_cannot_bless_changed_unpacked_bytes(self):
        import io,tarfile
        registry=self.root/'registry';source=registry/'src/index.crates.io-test/pkg-1.0.0'
        cache=registry/'cache/index.crates.io-test';source.mkdir(parents=True);cache.mkdir(parents=True)
        index=registry/'index/index.crates.io-test';index.mkdir(parents=True)
        (index/'config.json').write_text('{"dl":"https://static.crates.io/crates","api":"https://crates.io"}')
        archive=cache/'pkg-1.0.0.crate'
        with tarfile.open(archive,'w:gz') as tar:
            info=tarfile.TarInfo('pkg-1.0.0/lib.rs');info.size=6;tar.addfile(info,io.BytesIO(b'public'))
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        expected=[['pkg','1.0.0','registry+https://github.com/rust-lang/crates.io-index',digest]]
        (source/'lib.rs').write_bytes(b'evil')
        (source/'.cargo-checksum.json').write_text(json.dumps({'package':digest,'files':{'lib.rs':hashlib.sha256(b'evil').hexdigest()}}))
        with self.assertRaisesRegex(self.p.Failure,'archive.*unpacked|unpacked.*archive'):
            self.p.verify_registry(registry,expected)

    def test_exclusive_archive_extract_rejects_path_traversal_links_and_devices(self):
        import io,tarfile
        for kind in ('traversal','symlink','hardlink','device','duplicate'):
            archive=self.root/(kind+'.tar.xz')
            with tarfile.open(archive,'w:xz') as tar:
                info=tarfile.TarInfo('../escape' if kind=='traversal' else 'package/file')
                if kind=='symlink':info.type=tarfile.SYMTYPE;info.linkname='/foreign'
                elif kind=='hardlink':info.type=tarfile.LNKTYPE;info.linkname='/foreign'
                elif kind=='device':info.type=tarfile.CHRTYPE
                else:info.size=1
                tar.addfile(info,io.BytesIO(b'x') if info.isfile() else None)
                if kind=='duplicate':tar.addfile(info,io.BytesIO(b'x'))
            with self.subTest(kind=kind),self.assertRaises(self.p.Failure):
                self.p.extract_distribution(archive,self.root/kind,10,lambda:1)
        self.assertFalse((self.root/'escape').exists())

    def test_network_probe_must_observe_denial_not_connection_refusal_or_success(self):
        host=self.p.SystemHost()
        with patch.object(self.p.Path,'is_file',return_value=False),self.assertRaises(self.p.Failure):
            host.network_probe(cwd=self.root,env={},timeout=1)
        for result in (self.p.CommandResult(1,b'',b''),self.p.CommandResult(0,b'unexpected',b'')):
            with patch.object(self.p.Path,'is_file',return_value=True),patch.object(host,'command',return_value=result),self.assertRaises(self.p.Failure):
                host.network_probe(cwd=self.root,env={},timeout=1)

    def test_cleanup_does_not_adopt_forged_or_unrecorded_namespace(self):
        journal=self.p.Ownership(self.root/'state',{'run_id':'123','head':'a'*40})
        journal.initialize();foreign=self.root/'foreign';foreign.mkdir()
        raw=json.loads(journal.path.read_bytes())
        raw['entries']=[{'path':str(foreign),'identity':journal._id(foreign)}]
        journal.path.write_text(json.dumps(raw))
        with self.assertRaises(self.p.Failure):journal.cleanup()
        self.assertTrue(foreign.exists())


class ProofFailureTests(unittest.TestCase):
    setUp = StageTests.setUp
    fake_build_receipt = StageTests.fake_build_receipt
    def test_complete_inert_pipeline_retains_receipts_with_no_native_claim(self):
        self.run.admit_host();self.run.provision()
        proof=self.run.run_frozen()
        self.assertEqual(proof['status'],'passed');self.assertFalse(proof['native_executed'])
        self.assertEqual(len(proof['batches']),11);self.assertEqual(self.host.builder_calls,1)
        final=self.run.export_receipts()
        self.assertEqual(final['result']['status'],'inert-tests-only')
        self.assertEqual({p.name for p in self.run.export.iterdir()},set(self.p.RECEIPT_MEMBERS)|{'artifact-manifest.json'})
        self.run.cleanup()
        self.assertTrue((self.run.export/'artifact-manifest.json').exists())

    def test_failed_postcheck_never_exports_success_or_retries_builder(self):
        self.run.admit_host();self.run.provision()
        # Proof's precheck succeeds; its after-build check detects drift.
        with patch.object(self.run,'_postcheck',side_effect=[{'files':102},self.p.Failure('source drift')]):
            with self.assertRaises(self.p.Failure):self.run.run_frozen()
        self.assertEqual(self.host.builder_calls,1)
        self.assertEqual(parse_test_receipt(self.run,'proof.json')['status'],'failed')
        final=self.run.export_receipts()
        self.assertEqual(final['result']['status'],'incomplete')

    def test_compiler_fixture_and_direct_overflow_failures_stay_failed(self):
        for fault in ('compiler-timeout','fixture-timeout','fixture-extra-stdout','fixture-count','fixture-overflow','verify'):
            run=self.p.ProofRun(self.host,self.root/(fault+'-state'),self.root/(fault+'-export'),self.env)
            for name in ('_inputs','_paths_absent','_source_check','_stage_inputs','_install','_installed_check','_fetch','_postcheck','_metadata','_batches'):
                patch.object(run,name,getattr(self.run,name)).start()
            patch.object(run,'_build_receipt',return_value={'inert':True}).start()
            run.admit_host();run.provision()
            original=self.host.command
            def fail(argv,**kwargs):
                is_build=str(self.p.BUILDER) in argv and '--verify' not in argv
                is_fixture=str(self.p.BINARY) in argv
                if fault=='compiler-timeout' and is_build:raise self.p.Failure('command timeout')
                if fault=='verify' and '--verify' in argv:raise self.p.Failure('stale binary')
                if fault.startswith('fixture-') and is_fixture:raise self.p.Failure(fault)
                return original(argv,**kwargs)
            with self.subTest(fault=fault),patch.object(self.host,'command',side_effect=fail),self.assertRaises(self.p.Failure):
                run.run_frozen()
            self.assertEqual(parse_test_receipt(run,'proof.json')['status'],'failed')
            self.assertFalse(parse_test_receipt(run,'proof.json')['native_executed'])

    def test_changed_raw_receipt_breaks_the_next_stage(self):
        self.run.admit_host()
        (self.run.receipts/'admission.json').write_bytes((self.run.receipts/'admission.json').read_bytes()+b' ')
        with self.assertRaises(self.p.Failure):self.run.provision()
        self.assertEqual(self.host.builder_calls,0)

    def test_wrong_tool_version_or_target_and_metadata_graph_are_rejected(self):
        self.run.admit_host()
        prefix=self.root/'prefix';(prefix/'bin').mkdir(parents=True)
        for name in ('rustc','cargo'):(prefix/'bin'/name).write_bytes(b'inert executable')
        rust=b'rustc 1.98.0 (88d9e12ae 2026-08-15)\nhost: aarch64-apple-darwin\nrelease: 1.98.0\n'
        cargo=b'cargo 1.98.0 (797e8a9bc 2026-08-05)\n'
        with patch.object(self.p,'PREFIX',prefix):
            for output in (rust.replace(b'1.98.0',b'1.99.0'),rust.replace(b'aarch64',b'x86_64')):
                with patch.object(self.run,'_command',side_effect=[output,cargo]),self.assertRaises(self.p.Failure):
                    self.p.ProofRun._tool_versions(self.run)
        data={'resolve':{'nodes':[{'id':'local','features':[]}]},'packages':[{'name':'selahcue-cloud','id':'local','source':None}]}
        with patch.object(self.run,'_command',return_value=json.dumps(data).encode()),self.assertRaises(self.p.Failure):
            self.p.ProofRun._metadata(self.run)
        data={'resolve':{'nodes':[{'id':name,'features':features} for name,features in self.p.FEATURES.items()]},
              'packages':[{'name':name,'id':name,'source':None} for name in self.p.FEATURES] +
                         [{'name':'unexpected','version':'1.0','source':'registry+https://github.com/rust-lang/crates.io-index'}]}
        with patch.object(self.run,'_command',return_value=json.dumps(data).encode()),patch.object(self.run,'_expected_tuples',return_value=[]),self.assertRaises(self.p.Failure):
            self.p.ProofRun._metadata(self.run)

    def test_staged_lock_source_or_input_drift_is_rejected_before_builder(self):
        self.run.admit_host()
        staged=self.root/'staged';staged.write_bytes(b'unchanged')
        row={'destination':str(staged),'bytes':9,'sha256':hashlib.sha256(b'unchanged').hexdigest()}
        staged.write_bytes(b'changed')
        with patch.object(self.p.fixtures,'_input_manifest',return_value={'payloads':[row]}),patch.object(self.run,'_no_config'),self.assertRaises(self.p.Failure):
            self.p.ProofRun._postcheck(self.run)
        self.assertEqual(self.host.builder_calls,0)

    def test_missing_depinfo_generated_source_stale_binary_or_feature_tuple_receipt(self):
        self.run.admit_host()
        base=self.root/'O/fixtures/native';base.mkdir(parents=True)
        self.p.BINARY.write_bytes(b'inert binary')
        build={'registry_tuples':[],'local_features':self.p.FEATURES,'lock_sha256':self.p.LOCK_SHA256,
               'owning_lock_sha256':self.p.OWNER_LOCK_SHA256,'binary_path':str(self.p.BINARY),
               'binary_sha256':hashlib.sha256(b'inert binary').hexdigest(),
               'dep_info':{},'generated_file_sha256':{}}
        for fault in ('dep-info','binary','features','tuple'):
            data=copy.deepcopy(build)
            if fault=='binary':data['binary_sha256']='f'*64
            if fault=='features':data['local_features']['selahcue-cloud']=[]
            if fault=='tuple':data['registry_tuples']=[['unexpected']]
            (base/'build.json').write_text(json.dumps(data))
            with self.subTest(fault=fault),patch.object(self.run,'_expected_tuples',return_value=[]),self.assertRaises(self.p.Failure):
                self.p.ProofRun._build_receipt(self.run)

    def test_finalize_interruption_marks_incomplete_instead_of_leaving_success(self):
        self.run.admit_host();self.run.provision();self.run.run_frozen()
        with patch.object(self.run,'_postcheck',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):
            self.run.export_receipts()
        self.assertEqual(parse_test_receipt(self.run,'result.json')['status'],'incomplete')
        self.assertFalse(self.run.export.exists())


class FinalBoundaryTests(unittest.TestCase):
    setUp = StageTests.setUp
    fake_build_receipt = StageTests.fake_build_receipt

    def test_failed_command_is_incrementally_recorded(self):
        self.run.admit_host();self.run.provision();self.host.fault='builder'
        with self.assertRaises(self.p.Failure):self.run.run_frozen()
        attempts=parse_test_receipt(self.run,'proof.json')['commands']
        self.assertTrue(any(str(self.p.BUILDER) in a['argv'] and a.get('status')=='failed' for a in attempts))

    def test_build_and_fixture_invocation_limits_and_clean_environment(self):
        self.run.admit_host();self.run.provision()
        calls=[];original=self.host.command
        def capture(argv,**kwargs):calls.append((argv,kwargs));return original(argv,**kwargs)
        with patch.object(self.host,'command',side_effect=capture):self.run.run_frozen()
        builds=[(a,k) for a,k in calls if str(self.p.BUILDER) in a and '--verify' not in a]
        self.assertEqual(len(builds),1);argv,kwargs=builds[0]
        self.assertEqual(argv[-1],str(self.p.BUILDER));self.assertNotIn('--resolve',argv)
        self.assertEqual(kwargs['timeout'],600);self.assertEqual(kwargs['env'],self.p.builder_environment())
        native=[(a,k) for a,k in calls if str(self.p.BINARY) in a]
        self.assertEqual(len(native),11)
        self.assertTrue(all(k['timeout']==30 and k['env']=={'PATH':'/usr/bin:/bin'} and k['stderr_limit']==0 for a,k in native))
        self.assertEqual(sum(str(self.p.BUILDER) in a and '--verify' in a for a,k in calls),2)

    def test_installed_executable_or_registry_drift_is_a_prebuild_failure(self):
        self.run.admit_host();self.run.provision()
        setup=parse_test_receipt(self.run,'setup.json')
        setup['toolchain']['executables']={'rustc':{'bytes':1,'sha256':'a'*64},'cargo':{'bytes':1,'sha256':'b'*64}}
        self.run._receipt('setup.json',setup)
        prefix=self.root/'prefix';(prefix/'bin').mkdir(parents=True)
        (prefix/'bin/rustc').write_bytes(b'changed');(prefix/'bin/cargo').write_bytes(b'changed')
        with patch.object(self.p,'PREFIX',prefix),self.assertRaises(self.p.Failure):
            self.assertTrue(hasattr(self.p.ProofRun,'_installed_check'), 'installed tool verification is absent')
            self.p.ProofRun._installed_check(self.run)
        self.assertEqual(self.host.builder_calls,0)

    def test_fetch_lock_change_and_absent_cache_prevent_seeding(self):
        self.run.admit_host();self.run.deadline=400
        with patch.object(self.run,'_expected_tuples',side_effect=[[['expected']],[['changed']]]),patch.object(self.run,'_command',return_value=b''),self.assertRaises(self.p.Failure):
            self.p.ProofRun._fetch(self.run)
        with patch.object(self.run,'_expected_tuples',return_value=[]),patch.object(self.run,'_command',return_value=b''),self.assertRaises(self.p.Failure):
            self.p.ProofRun._fetch(self.run)
        self.assertEqual(self.host.builder_calls,0)

    def test_stage_cleanup_refuses_an_export_symlink_without_deleting_other_files(self):
        # Exports are retained, not cleanup authority. Any later export attempt
        # must still refuse a symlink rather than write into the target.
        self.run.admit_host();self.run.provision();self.run.run_frozen()
        foreign=self.root/'foreign';foreign.mkdir();(foreign/'keep').write_text('keep')
        self.run.export.symlink_to(foreign,target_is_directory=True)
        with self.assertRaises(self.p.Failure):self.run.export_receipts()
        self.assertEqual((foreign/'keep').read_text(),'keep')


class WorkflowIdentityTests(unittest.TestCase):
    setUp = OrchestrationTests.setUp

    def test_workflow_and_full_action_identities_are_in_run_binding(self):
        self.assertTrue(hasattr(self.p,'workflow_identity'),'runtime workflow/action identity gate is absent')
        path=self.root/'.github/workflows/macos-native-proof.yml';path.parent.mkdir(parents=True)
        raw=('steps:\n  - uses: actions/checkout@'+'a'*40+'\n  - uses: actions/upload-artifact@'+'b'*40+'\n').encode()
        path.write_bytes(raw)
        with patch.object(self.p,'REPO',self.root):
            observed=self.p.workflow_identity()
            self.assertEqual(observed['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(observed['actions'],['actions/checkout@'+'a'*40,'actions/upload-artifact@'+'b'*40])
            for body in (raw.replace(b'a'*40,b'v4'),raw+b'  - uses: unexpected/action@' + b'c'*40+b'\n'):
                path.write_bytes(body)
                with self.assertRaises(self.p.Failure):self.p.workflow_identity()


class ReceiptCompletenessTests(unittest.TestCase):
    setUp = StageTests.setUp
    fake_build_receipt = StageTests.fake_build_receipt

    def test_failed_admission_retains_actual_resource_observations(self):
        self.host.fault='memory'
        with self.assertRaises(self.p.Failure):self.run.admit_host()
        receipt=parse_test_receipt(self.run,'admission.json')
        self.assertEqual(len(receipt.get('resources',[])),3)
        self.assertEqual(receipt['resources'][0]['physical_bytes'],1)

    def test_final_run_receipt_carries_actual_host_toolchain_source_identities(self):
        self.run.admit_host();self.run.provision();self.run.run_frozen();self.run.export_receipts()
        run=parse_test_receipt(self.run,'run.json')
        self.assertEqual(run.get('host',{}).get('sdk'),'inert')
        self.assertEqual(run.get('source',{}).get('files'),102)
        self.assertEqual(run.get('toolchain',{}).get('verified'),True)
        self.assertEqual(run.get('stage_status',{}).get('proof.json'),'passed')

class ExecutionFlagTests(unittest.TestCase):
    setUp = StageTests.setUp
    fake_build_receipt = StageTests.fake_build_receipt

    def test_failed_builder_does_not_claim_native_adapter_execution(self):
        self.run.admit_host();self.run.provision()
        self.host.native_executed=True
        self.host.fault='builder'
        with self.assertRaises(self.p.Failure):self.run.run_frozen()
        result=parse_test_receipt(self.run,'proof.json')
        self.assertFalse(result['native_executed'])
        self.assertTrue(result.get('build_executed'))
        self.assertFalse(result.get('build_completed',False))

if __name__=='__main__':unittest.main()
