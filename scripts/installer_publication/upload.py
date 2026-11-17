"""Finite conditional installer publication. Local state never proves remote truth."""
from collections.abc import Callable
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import re
import selectors
import shutil
import stat
import subprocess
import tempfile
import time
from typing import Literal
from uuid import uuid4

from .contracts import (
    ALL_USERS, BUCKET, ENDPOINT, REGION, MAX_JSON_BYTES, MAX_STRING_BYTES,
    Grant, HeadObservation, ObjectAcl, ObjectPlan, PublicationError,
    UploadedObject, UploadReceipt, VerifiedObject, canonical_bytes, headers_match,
    parse_object_plan, parse_upload_receipt, read_json, record_bytes, utc_now,
)
from .prepare import _directory, hash_regular_file, load_prepared_release, read_regular_file
from .public_verify import verify_object_in_child

_TOTAL_TIMEOUT = 3600.0
_ERROR_LIMIT = 4096
_VERSION = re.compile(rb'aws-cli/(2\.[0-9]+\.[0-9]+)(?: [\x20-\x7e]+)?\r?\n?')
_SERVICE_ERROR = re.compile(
    rb'An error occurred \(([A-Za-z0-9]+)\) when calling the (HeadObject|GetObjectAcl|PutObject) operation: [^\r\n]*\r?\n?'
)
PutOutcome = Literal['created', 'exists', 'conflict', 'unknown']


class _Missing:
    pass


Missing = _Missing()


def _check(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise PublicationError(4, 'Upload invocation exceeded its deadline')


def _pause(seconds: float, deadline: float) -> None:
    _check(deadline)
    time.sleep(min(seconds, max(0, deadline - time.monotonic())))
    _check(deadline)


def _text(value: object) -> bool:
    try:
        return (isinstance(value, str) and 0 < len(value.encode('utf-8')) <= MAX_STRING_BYTES
                and all(ord(c) >= 32 and ord(c) != 127 for c in value))
    except UnicodeEncodeError:
        return False


class AwsCli:
    """Own the isolated CLI environment; expose exactly HEAD, ACL and conditional PUT."""
    def __init__(self, deadline: float):
        self.deadline = deadline
        self.tool_version = ''
        self._temporary = None

    def __enter__(self):
        _check(self.deadline)
        executable = shutil.which('aws')
        if not executable:
            raise PublicationError(5, 'AWS CLI v2 executable is required')
        access = os.environ.get('INSTALLER_S3_ACCESS_KEY')
        secret = os.environ.get('INSTALLER_S3_SECRET_KEY')
        if not access or not secret or any(c in access + secret for c in '\x00\r\n'):
            raise PublicationError(5, 'Installer upload credentials are required')
        self.executable = str(Path(executable).absolute())
        self._temporary = tempfile.TemporaryDirectory(prefix='installer-aws-')
        try:
            directory = Path(self._temporary.name)
            config, credentials = directory / 'config', directory / 'credentials'
            for path in (config, credentials):
                with path.open('xb') as file:
                    os.fchmod(file.fileno(), 0o600)
            self.env = {
                'PATH': os.defpath, 'LC_ALL': 'C', 'HOME': str(directory),
                'AWS_ACCESS_KEY_ID': access, 'AWS_SECRET_ACCESS_KEY': secret,
                'AWS_REGION': REGION, 'AWS_DEFAULT_REGION': REGION,
                'AWS_EC2_METADATA_DISABLED': 'true', 'AWS_CLI_AUTO_PROMPT': 'off', 'AWS_PAGER': '',
                'AWS_CONFIG_FILE': str(config), 'AWS_SHARED_CREDENTIALS_FILE': str(credentials),
                'AWS_MAX_ATTEMPTS': '1', 'AWS_REQUEST_CHECKSUM_CALCULATION': 'when_required',
                'AWS_RESPONSE_CHECKSUM_VALIDATION': 'when_required',
            }
            self.validate()
            _check(self.deadline)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
        self.env = {}

    def _run(self, args: list[str]) -> tuple[int, bytes, bytes] | None:
        """None means timed out, never that a write failed to occur. No raw diagnostics escape."""
        _check(self.deadline)
        buffers = [bytearray(), bytearray()]
        try:
            with subprocess.Popen([self.executable, *args], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env) as child:
                try:
                    with selectors.DefaultSelector() as selector:
                        for stream, index in ((child.stdout, 0), (child.stderr, 1)):
                            os.set_blocking(stream.fileno(), False)
                            selector.register(stream, selectors.EVENT_READ, index)
                        while selector.get_map():
                            _check(self.deadline)
                            for key, _ in selector.select(max(0, self.deadline - time.monotonic())):
                                _check(self.deadline)
                                index = key.data
                                limit = MAX_JSON_BYTES if index == 0 else _ERROR_LIMIT
                                chunk = os.read(key.fileobj.fileno(), min(65536, limit + 1 - len(buffers[index])))
                                if not chunk:
                                    selector.unregister(key.fileobj)
                                else:
                                    buffers[index].extend(chunk)
                                    if len(buffers[index]) > limit:
                                        raise PublicationError(5, 'AWS CLI output exceeded its byte limit')
                    status = child.wait(timeout=max(0, self.deadline - time.monotonic()))
                    _check(self.deadline)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait()
        except subprocess.TimeoutExpired:
            return None
        except OSError:
            raise PublicationError(5, 'AWS CLI process failed') from None
        return status, bytes(buffers[0]), bytes(buffers[1])

    def validate(self) -> None:
        version = self._run(['--version'])
        if version is None or version[0] != 0 or version[2] or not (match := _VERSION.fullmatch(version[1])):
            raise PublicationError(5, 'AWS CLI v2 version could not be validated')
        self.tool_version = 'aws-cli/' + match[1].decode('ascii')
        skeleton = self._run(['s3api', 'put-object', '--generate-cli-skeleton', 'input',
                              '--no-cli-pager', '--output', 'json'])
        if skeleton is None or skeleton[0] != 0 or skeleton[2]:
            raise PublicationError(5, 'AWS CLI offline PutObject model could not be validated')
        model = self._json(skeleton[1])
        if not {'Bucket','Key','Body','ContentLength','IfNoneMatch','ACL','ContentType',
                'ContentDisposition','CacheControl'} <= model.keys():
            raise PublicationError(5, 'AWS CLI lacks the required conditional PutObject model')
        _check(self.deadline)

    @staticmethod
    def _json(raw: bytes) -> dict:
        try:
            value = read_json(raw)
            if isinstance(value, dict):
                return value
        except PublicationError:
            pass
        raise PublicationError(5, 'Malformed AWS CLI JSON response')

    def _operation(self, operation: str, obj: ObjectPlan, extra: list[str] | None = None):
        # All callers pass the closed object contract before any process can start.
        parse_object_plan(record_bytes(obj))
        args = ['s3api', operation, '--bucket', BUCKET, '--key', obj.key,
                '--endpoint-url', ENDPOINT, '--region', REGION, '--no-cli-pager', '--output', 'json',
                '--cli-connect-timeout', '30', '--cli-read-timeout', '120', *(extra or [])]
        result = self._run(args)
        if result is None:
            if operation == 'put-object':
                return 'unknown'
            raise PublicationError(4, 'AWS CLI observation timed out')
        status, stdout, stderr = result
        if status == 0:
            if stderr:
                raise PublicationError(5, 'Unexpected AWS CLI diagnostic on success')
            return self._json(stdout)
        stderr = stderr.strip()
        match = _SERVICE_ERROR.fullmatch(stderr)
        expected_operation = {'head-object':'HeadObject','get-object-acl':'GetObjectAcl','put-object':'PutObject'}[operation]
        if match and match[2].decode('ascii') == expected_operation:
            code = match[1].decode('ascii')
            if code in ('AccessDenied','403','InvalidAccessKeyId','SignatureDoesNotMatch'):
                raise PublicationError(3, 'Remote installer access was denied')
            if operation == 'head-object' and code in ('404','NoSuchKey','NotFound'):
                return Missing
            if operation == 'put-object' and code in ('412','PreconditionFailed'):
                return 'exists'
            if operation == 'put-object' and code in ('409','ConditionalRequestConflict'):
                return 'conflict'
            if code in ('408','429','500','502','503','504','RequestTimeout','SlowDown','InternalError','ServiceUnavailable'):
                if operation == 'put-object':
                    return 'unknown'
                raise PublicationError(4, 'Remote installer observation is unknown')
        # Recognize the CLI's transport failures without displaying their request/URL detail.
        if stderr.startswith((b'Read timeout on endpoint URL:', b'Connect timeout on endpoint URL:',
                              b'Could not connect to the endpoint URL:', b'Connection was closed before we received a valid response')):
            if operation == 'put-object':
                return 'unknown'
            raise PublicationError(4, 'Remote installer observation is unknown')
        raise PublicationError(5, 'Unrecognized AWS CLI failure')

    def head(self, obj: ObjectPlan) -> HeadObservation | _Missing:
        value = self._operation('head-object', obj)
        if value is Missing:
            return Missing
        fields = ('ContentType', 'ContentDisposition', 'CacheControl')
        if (not isinstance(value, dict) or not all(_text(value.get(k)) for k in fields)
                or type(value.get('ContentLength')) is not int):
            raise PublicationError(5, 'Malformed remote object headers')
        if ('ContentEncoding' in value or 'WebsiteRedirectLocation' in value or value.get('Metadata', {}) != {}):
            raise PublicationError(3, 'Remote object has forbidden encoding, redirect or metadata')
        # s3api does not normally expose the HTTP request id. Never manufacture one.
        head = HeadObservation(*(value[k] for k in fields), value['ContentLength'], None, None)
        if not headers_match(head, obj, authenticated=True):
            raise PublicationError(3, 'Remote object headers differ from the accepted installer')
        return head

    def acl(self, obj: ObjectPlan) -> ObjectAcl:
        value = self._operation('get-object-acl', obj)
        try:
            owner = value['Owner']['ID']
            entries = value['Grants']
            if not _text(owner) or not isinstance(entries, list):
                raise ValueError
            grants = []
            for row in entries:
                grantee = row['Grantee']
                kind = grantee['Type']
                identifier = grantee.get('ID') if kind == 'CanonicalUser' else grantee.get('URI')
                permission = row['Permission']
                if not all(_text(item) for item in (kind, identifier, permission)):
                    raise ValueError
                grants.append(Grant(kind, identifier, permission))
        except (KeyError, TypeError, ValueError, AttributeError):
            raise PublicationError(5, 'Malformed remote object ACL') from None
        expected = (Grant('CanonicalUser', owner, 'FULL_CONTROL'), Grant('Group', ALL_USERS, 'READ'))
        if len(grants) != 2 or set(grants) != set(expected):
            raise PublicationError(3, 'Remote installer ACL differs; repair is forbidden')
        return ObjectAcl(owner, expected)

    def put(self, obj: ObjectPlan, snapshot: Path) -> PutOutcome:
        result = self._operation('put-object', obj, [
            '--body', str(snapshot), '--content-length', str(obj.size_bytes), '--if-none-match', '*',
            '--acl', 'public-read', '--content-type', obj.content_type,
            '--content-disposition', obj.content_disposition, '--cache-control', obj.cache_control,
        ])
        return 'created' if isinstance(result, dict) else result


class Journal:
    """One append-only, fsynced event stream per invocation. Never used to skip a probe."""
    def __init__(self, directory: int, deadline: float):
        self.deadline = deadline
        self.sequence = 0
        self.fd = os.open('upload-journal-' + uuid4().hex + '.jsonl',
                          os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            os.fsync(directory)
        except BaseException:
            os.close(self.fd)
            raise

    def check(self) -> None:
        _check(self.deadline)

    def event(self, obj: ObjectPlan, event: str) -> None:
        # Persistence of truthful partial state is allowed even after deadline expiry.
        self.sequence += 1
        try:
            raw = canonical_bytes({'sequence':self.sequence, 'id':obj.id, 'key':obj.key, 'event':event, 'at':utc_now()})
        except (TypeError, ValueError):
            raise PublicationError(5, 'Upload journal serialization failed') from None
        if len(raw) > _ERROR_LIMIT:
            raise PublicationError(5, 'Upload journal event exceeds its byte limit')
        if os.write(self.fd, raw) != len(raw):
            raise PublicationError(5, 'Short upload journal write')
        os.fsync(self.fd)

    def close(self) -> None:
        os.close(self.fd)


def _snapshot(obj: ObjectPlan, snapshot: Path, journal: Journal) -> None:
    if hash_regular_file(snapshot, obj.size_bytes, check=journal.check) != obj.sha256:
        raise PublicationError(2, 'Upload snapshot differs from its accepted digest')
    journal.check()


def reconcile_object(obj: ObjectPlan, snapshot: Path, aws: AwsCli,
                     verify: Callable[[ObjectPlan], VerifiedObject], journal: Journal) -> UploadedObject:
    attempts = 0
    outcome = 'reused_verified'
    while True:
        journal.check()
        head = aws.head(obj)
        journal.check()
        if head is not Missing:
            acl = aws.acl(obj)
            journal.check()
            verified = verify(obj)
            journal.check()
            _snapshot(obj, snapshot, journal)
            result = UploadedObject(obj.id, obj.key, obj.sha256, obj.size_bytes, outcome, head, acl, verified)
            journal.event(obj, 'verified')
            journal.check()
            return result
        journal.event(obj, 'missing')
        if attempts >= 3:
            raise PublicationError(4, 'Conditional upload attempts exhausted')
        if attempts:
            _pause((1.0, 3.0)[attempts - 1], journal.deadline)
        _snapshot(obj, snapshot, journal)
        # Persist the ambiguous state BEFORE launching the only remote mutation.
        journal.event(obj, 'write_outcome_unknown')
        journal.check()
        attempts += 1
        result = aws.put(obj, snapshot)
        journal.event(obj, result)
        _snapshot(obj, snapshot, journal)
        outcome = {'created':'created', 'exists':'reused_verified',
                   'conflict':'unknown_but_verified', 'unknown':'unknown_but_verified'}[result]
        # Even a successful CLI PUT requires new HEAD/ACL and full anonymous bytes.


@contextmanager
def _lock(directory: int, deadline: float):
    _check(deadline)
    fd = os.open('upload.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise PublicationError(2, 'Upload lock is not a regular file')
        # A busy local invocation is a bounded transient refusal, never a blocking wait.
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PublicationError(4, 'Another upload holds this release lock') from None
        _check(deadline)
        yield
    finally:
        os.close(fd)


def _commit_receipt(directory: int, raw: bytes, deadline: float) -> None:
    _check(deadline)
    temporary = '.upload-' + uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, 'wb') as file:
            if file.write(raw) != len(raw):
                raise PublicationError(5, 'Short upload receipt write')
            file.flush()
            os.fsync(file.fileno())
        _check(deadline)
        try:
            existing = os.stat('upload-receipt.json', dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None and not stat.S_ISREG(existing.st_mode):
            raise PublicationError(2, 'Upload receipt destination is not a regular file')
        os.replace(temporary, 'upload-receipt.json', src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
        _check(deadline)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def upload_release(release_dir: Path) -> UploadReceipt:
    deadline = time.monotonic() + _TOTAL_TIMEOUT
    started = utc_now()
    check = lambda: _check(deadline)
    journal = None
    current = None
    try:
        check()
        prepared = load_prepared_release(release_dir, check=check)
        check()
        with _directory(prepared.root) as directory, _lock(directory, deadline):
            check()
            journal = Journal(directory, deadline)
            try:
                with AwsCli(deadline) as aws:
                    check()
                    mappings = {row.id: row for row in prepared.prepare_receipt.packages}
                    results = []
                    for obj in prepared.public_plan.objects:
                        current = obj
                        check()
                        results.append(reconcile_object(obj, prepared.root / mappings[obj.id].snapshot_path, aws,
                            lambda plan: verify_object_in_child(plan, deadline=deadline), journal))
                    check()
                    prepared_hash = hashlib.sha256(read_regular_file(prepared.root / 'prepare-receipt.json')).hexdigest()
                    check()
                    receipt = UploadReceipt(1, prepared.prepare_receipt.plan_sha256,
                        prepared.prepare_receipt.input_sha256, prepared_hash, aws.tool_version,
                        started, utc_now(), tuple(results))
                    raw = record_bytes(receipt)
                    parse_upload_receipt(raw)
                    check()
                    _commit_receipt(directory, raw, deadline)
                    check()
                check()
            except (PublicationError, OSError):
                if current is not None:
                    try:
                        journal.event(current, 'stopped')
                    except (PublicationError, OSError):
                        pass  # The pre-PUT unknown event remains the recovery floor when persistence fails.
                raise
            finally:
                journal.close()
    except (OSError, TypeError, ValueError):
        raise PublicationError(5, 'Upload local storage or tool operation failed') from None
    check()
    return receipt
