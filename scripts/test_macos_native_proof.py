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

if __name__=='__main__':unittest.main()
