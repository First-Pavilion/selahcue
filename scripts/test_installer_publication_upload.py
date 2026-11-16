"""Offline authenticated-process and uncertain-write recovery controls."""
from contextlib import ExitStack
import fcntl
import io
import json
import os
from pathlib import Path
import tempfile
import time
import shutil
import unittest
from unittest.mock import patch

from _installer_publication_fixtures import ReleaseFixture, fake_aws_executable, digest
from installer_publication import prepare, upload
from installer_publication.contracts import PublicationError, ResponseHeaders, VerifiedObject, record_bytes, parse_upload_receipt, utc_now

_MARKER = 'synthetic-installer-secret'


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.fixture = ReleaseFixture(self.root)
        self.prepared = prepare.prepare_release(self.fixture.input_path, self.fixture.source_tree, self.fixture.output)
        self.executable, self.state = fake_aws_executable(self.root)
        self.stack.enter_context(patch.dict(os.environ, {
            'PATH':str(self.root) + os.pathsep + os.defpath,
            'INSTALLER_S3_ACCESS_KEY':'synthetic-access', 'INSTALLER_S3_SECRET_KEY':_MARKER,
            'AWS_SESSION_TOKEN':_MARKER, 'AWS_PROFILE':_MARKER, 'HTTPS_PROXY':_MARKER,
            'AWS_ENDPOINT_URL':_MARKER, 'PYTHONPATH':_MARKER,
        }, clear=True))
        self.readbacks = []
        self.stack.enter_context(patch.object(upload, 'verify_object_in_child', side_effect=self.verify))
        self.stack.enter_context(patch.object(upload.time, 'sleep', return_value=None))

    def state_data(self):
        return json.loads(self.state.read_bytes())

    def mode(self, mode):
        data = self.state_data(); data['mode'] = mode; self.state.write_text(json.dumps(data))

    def verify(self, obj, *, deadline):
        self.readbacks.append((obj.id, deadline))
        body = bytes.fromhex(self.state_data()['objects'][obj.key]['body'])
        if digest(body) != obj.sha256:
            raise PublicationError(3, 'Synthetic anonymous corruption')
        return VerifiedObject(obj.id, obj.url, 200, ResponseHeaders(obj.content_type, obj.content_disposition,
            obj.cache_control, len(body), None), len(body), digest(body), utc_now())

    def run_upload(self):
        return upload.upload_release(self.fixture.output)

    def assert_error(self, code):
        with self.assertRaises(PublicationError) as error:
            self.run_upload()
        self.assertEqual(error.exception.exit_code, code)
        self.assertNotIn(_MARKER, str(error.exception))
        return error.exception

    def test_all_puts_are_conditional_and_cli_retries_disabled(self):
        receipt = self.run_upload()
        self.assertEqual([row.put_outcome for row in receipt.objects], ['created'] * 3)
        self.assertEqual(parse_upload_receipt(record_bytes(receipt)), receipt)
        self.assertEqual(len(self.state_data()['puts']), 3)
        for call in self.state_data()['calls']:
            args, env = call['argv'], call['env']
            self.assertNotIn(_MARKER, str(args))
            self.assertEqual(env['AWS_SECRET_ACCESS_KEY'], _MARKER)
            self.assertEqual(env['AWS_MAX_ATTEMPTS'], '1')
            self.assertEqual(env['AWS_REQUEST_CHECKSUM_CALCULATION'], 'when_required')
            self.assertEqual(env['AWS_RESPONSE_CHECKSUM_VALIDATION'], 'when_required')
            self.assertTrue(set(env) <= {'PATH','LC_ALL','LC_CTYPE','__CF_USER_TEXT_ENCODING','HOME',
                'AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_DEFAULT_REGION','AWS_REGION',
                'AWS_EC2_METADATA_DISABLED','AWS_CLI_AUTO_PROMPT','AWS_PAGER','AWS_MAX_ATTEMPTS',
                'AWS_CONFIG_FILE','AWS_SHARED_CREDENTIALS_FILE',
                'AWS_REQUEST_CHECKSUM_CALCULATION','AWS_RESPONSE_CHECKSUM_VALIDATION'})
            if args[:2] == ['s3api','put-object'] and '--body' in args:
                self.assertEqual(args[args.index('--if-none-match')+1], '*')
                self.assertEqual(args[args.index('--acl')+1], 'public-read')
        for path in self.fixture.output.glob('upload*'):
            if path.is_file(): self.assertNotIn(_MARKER.encode(), path.read_bytes())
        self.assertEqual(len({deadline for _, deadline in self.readbacks}), 1)

    def test_412_reuses_only_matching_anonymous_bytes_and_headers(self):
        self.mode('race')
        receipt = self.run_upload()
        self.assertEqual([row.put_outcome for row in receipt.objects], ['reused_verified']*3)
        self.assertEqual(len(self.readbacks), 3)
        self.mode('wrong-header')
        self.assert_error(3)
        self.assertEqual(len(self.state_data()['puts']), 3)

    def test_lost_put_response_reconciles_before_retry(self):
        self.mode('lost')
        receipt = self.run_upload()
        self.assertEqual([row.put_outcome for row in receipt.objects], ['unknown_but_verified']*3)
        self.assertEqual(len(self.state_data()['puts']), 3)
        operations = [call['argv'][1] for call in self.state_data()['calls'] if '--key' in call['argv']]
        self.assertEqual(operations, ['head-object','put-object','head-object','get-object-acl']*3)

    def test_403_is_not_absence_and_private_object_is_not_repaired(self):
        self.mode('denied'); self.assert_error(3)
        self.assertEqual(self.state_data()['puts'], [])
        self.mode(''); self.run_upload(); self.mode('private'); self.assert_error(3)
        self.assertEqual(len(self.state_data()['puts']), 3)
        self.mode('public-write'); self.assert_error(3)

    def test_crash_after_put_before_receipt_recovers(self):
        original = upload.Journal.event
        def crash(journal, obj, event):
            if event == 'created': raise OSError('synthetic journal failure')
            return original(journal, obj, event)
        with patch.object(upload.Journal, 'event', crash): self.assert_error(5)
        self.assertEqual(len(self.state_data()['puts']), 1)
        self.assertFalse((self.fixture.output / 'upload-receipt.json').exists())
        receipt = self.run_upload()
        self.assertEqual(receipt.objects[0].put_outcome, 'reused_verified')
        self.assertEqual(len(self.state_data()['puts']), 3)
        self.assertEqual(len(self.readbacks), 3)

    def test_partial_release_and_concurrent_publishers_never_overwrite(self):
        original = self.verify
        def fail_second(obj, *, deadline):
            if obj.id == 'universalMac': raise PublicationError(4,'synthetic failure')
            return original(obj, deadline=deadline)
        with patch.object(upload, 'verify_object_in_child', side_effect=fail_second): self.assert_error(4)
        self.assertFalse((self.fixture.output / 'upload-receipt.json').exists())
        self.assertEqual(len(self.state_data()['puts']), 2)
        first = self.run_upload()
        second = self.run_upload()  # second publisher sees the first publisher's shared remote state
        self.assertEqual([o.put_outcome for o in first.objects], ['reused_verified','reused_verified','created'])
        self.assertEqual([o.put_outcome for o in second.objects], ['reused_verified']*3)
        self.assertEqual(len(self.state_data()['puts']), 3)

    def test_unknown_probe_and_exhaustion_do_not_authorize_more_writes(self):
        self.mode('probe-unknown'); self.assert_error(4)
        self.assertEqual(len(self.state_data()['puts']), 1)
        self.mode('conflict-before'); self.assert_error(4)
        self.assertEqual(len(self.state_data()['puts']), 4)
        self.assertEqual(self.readbacks, [])

    def test_unsupported_model_malformed_and_bounded_output_fail_closed(self):
        for mode, code in [('old-model',5),('malformed',5),('unrecognized',5),('flood',5),('stderr-flood',5)]:
            with self.subTest(mode=mode): self.mode(mode); self.assert_error(code)
        self.assertEqual(self.state_data()['puts'], [])

    def test_metadata_and_anonymous_corruption_are_conflicts(self):
        self.run_upload(); self.mode('metadata'); self.assert_error(3)
        self.mode('')
        data = self.state_data(); obj = self.prepared.public_plan.objects[0]
        data['objects'][obj.key]['body'] = (b'x' * obj.size_bytes).hex()
        self.state.write_text(json.dumps(data)); self.assert_error(3)
        self.assertEqual(len(self.state_data()['puts']), 3)

    def test_snapshot_change_after_put_prevents_success(self):
        real_put = upload.AwsCli.put
        def mutate(aws, obj, snapshot):
            result = real_put(aws,obj,snapshot)
            snapshot.chmod(0o600); snapshot.write_bytes(b'x' * obj.size_bytes)
            return result
        with patch.object(upload.AwsCli, 'put', mutate): self.assert_error(2)
        self.assertEqual(len(self.state_data()['puts']), 1)
        self.assertFalse((self.fixture.output/'upload-receipt.json').exists())

    def test_local_stream_deadline_stops_chunks(self):
        body = io.BytesIO(b'x'*20)
        calls = []
        def check():
            calls.append(body.tell())
            if body.tell() >= 4: raise PublicationError(4,'synthetic expiry')
        with patch.object(prepare, '_CHUNK', 4), self.assertRaises(PublicationError) as error:
            prepare._stream_hash(body,20,check=check)
        self.assertEqual(error.exception.exit_code,4)
        self.assertEqual(body.tell(),4)

    def test_deadline_includes_reload_model_hash_and_receipt_commit(self):
        now = [10.0]
        real_load = upload.load_prepared_release
        def load(path, *, check):
            now[0] += 100
            return real_load(path,check=check)
        real_validate = upload.AwsCli.validate
        def validate(aws):
            now[0] += 100
            return real_validate(aws)
        real_verify = self.verify
        def verify(obj, *, deadline):
            self.assertEqual(deadline,3610.0)
            result = real_verify(obj,deadline=deadline)
            if obj.id == 'ubuntu': now[0] = deadline
            return result
        with patch.object(upload.time,'monotonic',side_effect=lambda:now[0]), \
             patch.object(upload,'load_prepared_release',side_effect=load), \
             patch.object(upload.AwsCli,'validate',validate), \
             patch.object(upload,'verify_object_in_child',side_effect=verify), \
             patch.object(upload,'_commit_receipt',side_effect=AssertionError('late complete receipt')):
            self.assert_error(4)
        self.assertEqual(len(self.state_data()['puts']),3)
        self.assertFalse((self.fixture.output/'upload-receipt.json').exists())

    def test_expired_reload_and_retry_budget_stop_remote_work(self):
        now = [0.0]
        def expired_load(path, *, check): now[0]=3600.; check()
        with patch.object(upload.time,'monotonic',side_effect=lambda:now[0]), \
             patch.object(upload,'load_prepared_release',side_effect=expired_load): self.assert_error(4)
        self.assertEqual(self.state_data()['calls'],[])
        now[0]=0
        self.mode('unknown-before')
        real_put = upload.AwsCli.put
        def almost_expired(aws,obj,snapshot):
            result=real_put(aws,obj,snapshot); now[0]=3599.5; return result
        sleeps=[]
        def sleep(seconds): sleeps.append(seconds); now[0]+=seconds
        with patch.object(upload.time,'monotonic',side_effect=lambda:now[0]), \
             patch.object(upload.time,'sleep',side_effect=sleep), patch.object(upload.AwsCli,'put',almost_expired):
            self.assert_error(4)
        self.assertEqual(sleeps,[0.5])
        self.assertEqual(len(self.state_data()['puts']),1)


    def test_serialization_and_fsync_failure_after_put_preserve_unknown_recovery(self):
        original = upload.canonical_bytes
        def serialize(value):
            if value.get('event') == 'created': raise ValueError('synthetic serialization fault')
            return original(value)
        with patch.object(upload, 'canonical_bytes', side_effect=serialize): self.assert_error(5)
        self.assertEqual(len(self.state_data()['puts']), 1)
        events = b''.join(path.read_bytes() for path in self.fixture.output.glob('upload-journal-*'))
        self.assertIn(b'write_outcome_unknown', events)
        receipt = self.run_upload()
        self.assertEqual(receipt.objects[0].put_outcome, 'reused_verified')
        real_sync = os.fsync
        def sync(fd):
            if self.state_data()['puts'] and not (self.fixture.output/'upload-receipt.json').exists():
                raise OSError('synthetic fsync fault')
            return real_sync(fd)
        # New invocation over already public objects; complete persistence must fail closed.
        (self.fixture.output/'upload-receipt.json').unlink()
        with patch.object(upload.os, 'fsync', side_effect=sync): self.assert_error(5)
        self.assertFalse((self.fixture.output/'upload-receipt.json').exists())
        self.assertEqual(len(self.state_data()['puts']),3)

    def test_fsync_fails_immediately_after_successful_put_and_restart_reuses(self):
        original = os.fsync
        def fail_after_write(fd):
            if self.state_data()['puts']:
                raise OSError('synthetic post-PUT fsync failure')
            return original(fd)
        with patch.object(upload.os, 'fsync', side_effect=fail_after_write): self.assert_error(5)
        self.assertEqual(len(self.state_data()['puts']),1)
        self.assertFalse((self.fixture.output/'upload-receipt.json').exists())
        receipt=self.run_upload()
        self.assertEqual(receipt.objects[0].put_outcome,'reused_verified')
        self.assertEqual(len(self.state_data()['puts']),3)

    def test_lock_contention_refuses_without_any_cli_launch(self):
        with (self.fixture.output/'upload.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assert_error(4)
        self.assertEqual(self.state_data()['calls'],[])

    def test_two_publishers_interleave_between_missing_head_and_put(self):
        other = self.root/'other-release'
        shutil.copytree(self.fixture.output,other)
        real_put = upload.AwsCli.put
        intervened=[]
        def concurrent_put(aws,obj,snapshot):
            if not intervened:
                intervened.append(obj.id)
                with prepare._directory(other) as directory:
                    journal=upload.Journal(directory,aws.deadline)
                    try:
                        with patch.object(upload.AwsCli,'put',real_put):
                            winner = upload.reconcile_object(obj, other/self.prepared.prepare_receipt.packages[0].snapshot_path,
                                aws, lambda plan:self.verify(plan,deadline=aws.deadline), journal)
                        self.assertEqual(winner.put_outcome,'created')
                    finally: journal.close()
            return real_put(aws,obj,snapshot)
        with patch.object(upload.AwsCli,'put',concurrent_put): receipt=self.run_upload()
        self.assertEqual(receipt.objects[0].put_outcome,'reused_verified')
        self.assertEqual(len(self.state_data()['puts']),4)
        self.assertEqual(len(self.state_data()['objects']),3)

    def test_subprocess_timeout_kills_owned_child_and_never_probes_after_expiry(self):
        self.mode('hang')
        original = upload.subprocess.Popen
        children=[]
        def spawn(*args,**kwargs):
            child=original(*args,**kwargs); children.append(child); return child
        started=time.monotonic()
        with patch.object(upload,'_TOTAL_TIMEOUT',0.3), patch.object(upload.subprocess,'Popen',side_effect=spawn):
            self.assert_error(4)
        self.assertLess(time.monotonic()-started,2)
        self.assertTrue(children)
        self.assertTrue(all(child.returncode is not None for child in children))
        self.assertEqual(self.state_data()['puts'],[])

    def test_expiry_after_hash_or_model_prevents_remote_operation(self):
        for phase in ('model','hash'):
            now=[0.0]
            if phase == 'model':
                real=upload.AwsCli.validate
                def consume(aws): real(aws); now[0]=3600.0
                seam=patch.object(upload.AwsCli,'validate',consume)
            else:
                real_hash=upload.hash_regular_file
                def consume_hash(*args,**kwargs):
                    result=real_hash(*args,**kwargs); now[0]=3600.0; return result
                seam=patch.object(upload,'hash_regular_file',side_effect=consume_hash)
            with patch.object(upload.time,'monotonic',side_effect=lambda:now[0]), seam:
                self.assert_error(4)
        self.assertEqual(self.state_data()['puts'],[])
        self.assertEqual(self.readbacks,[])

    def test_expiry_during_late_receipt_fsync_retains_truth_but_does_not_succeed(self):
        now=[0.0]
        real_sync=os.fsync
        def late_sync(fd):
            result=real_sync(fd)
            if (self.fixture.output/'upload-receipt.json').exists(): now[0]=3600.0
            return result
        with patch.object(upload.time,'monotonic',side_effect=lambda:now[0]), patch.object(upload.os,'fsync',side_effect=late_sync):
            self.assert_error(4)
        self.assertEqual(len(self.state_data()['puts']),3)
        self.assertEqual(len(self.readbacks),3)
        receipt=parse_upload_receipt((self.fixture.output/'upload-receipt.json').read_bytes())
        self.assertEqual(len(receipt.objects),3)


if __name__ == '__main__': unittest.main()
