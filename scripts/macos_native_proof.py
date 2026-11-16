"""One disposable hosted measurement of the sealed native fixture adapter.

No public configuration surface: the five CLI commands use compiled-in paths.
Importing this module never imports/executes the frozen builder. Successful
injected tests are orchestration evidence only. Cargo's internal captured output
buffer is NOT bounded by this outer stream pump.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import io
import os
from pathlib import Path, PurePosixPath
import platform
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request
try:
    import tomllib
except ImportError:
    tomllib = None

if __package__:
    from . import macos_native_fixtures as fixtures
else:
    import macos_native_fixtures as fixtures

REPO = Path(__file__).absolute().parent.parent
TOOLCHAIN_FILE = REPO / 'scripts/fixtures/macos-native-toolchain.json'
TOOLCHAIN_SHA256 = '91eed188e1eb54de8138868f9c6c72082d4af31d9a0bb1b66706adbf6bb6f7b7'
O = Path('/private/tmp/selahcue-provider-spike-20261114/notes-coverage-v1-offline')
USER_ROOT = Path('/Users/m.oluwole')
S = USER_ROOT / '.codex/worktrees/selahcue-provider-qualification/scph'
PREFIX = USER_ROOT / '.rustup/toolchains/1.98.0-aarch64-apple-darwin'
REGISTRY = USER_ROOT / '.cargo/registry'
PIN = Path('/private/tmp/selahcue-notes-native-input-pin-20261115.json')
SPEC = Path('/private/tmp/selahcue-notes-coverage-spec-20261114.md')
NORMATIVE = '1ea22e1ce6e52ab8aa2e0fd83fda1c9d90b094da'
STATE = REPO / '.macos-native-proof-state'
EXPORT = REPO / '.macos-native-proof-receipts'
WORK = O / '.native-target'
BINARY = WORK / 'cargo-target/debug/coverage-native-golden'
BUILDER = O / 'native-golden/build_pinned.py'
SCRATCH_LOCK = O / 'native-golden/Cargo.lock'
OWNER_LOCK = S / 'implementation/desktop/Cargo.lock'
LOCK_SHA256 = 'a78dcb39e5e302086a11c214800ab6875a07d4d7413ce428e1e0d068ab3c0718'
OWNER_LOCK_SHA256 = '684937aa63ab251c37fd84d1cb863e0c0c8ff8e938df4c2cdce9871b5a0e9e97'
FEATURES = {'coverage-native-golden': [], 'selahcue-cloud': ['openai'],
            'selahcue-core': [], 'selahcue-scripture': []}
SCOPE = ('implementation/desktop/crates/selahcue-core',
         'implementation/desktop/crates/selahcue-cloud',
         'implementation/desktop/crates/selahcue-scripture',
         'implementation/desktop/Cargo.lock', 'implementation/desktop/Cargo.toml', 'rust-toolchain.toml')
RECEIPT_MEMBERS = ('run.json', 'inputs.json', 'admission.json', 'setup.json',
                   'build.json', 'feature-tree.txt', 'proof.json', 'result.json')
ARTIFACT_LIMIT = 20 * 1024 * 1024
PROFILE = '(version 1)(allow default)(deny network*)'
SAFE_PATH = '/usr/bin:/bin:/usr/sbin:/sbin'


class Failure(ValueError):
    """Invariant name only; never include a raw payload, environment or token."""


def require(condition, label):
    if not condition:
        raise Failure(label)


def identity(raw):
    return {'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}


def wire(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate receipt key')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(Failure('nonfinite JSON')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Failure('invalid receipt JSON') from exc


def nofollow(path):
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'symlink path')


def regular(path, limit=ARTIFACT_LIMIT):
    nofollow(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as reader:
            info = os.fstat(reader.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, 'nonregular/oversize file')
            raw = reader.read(limit + 1)
            require(len(raw) <= limit, 'oversize file')
            return raw
    except OSError as exc:
        raise Failure('missing/unreadable file') from exc


def exclusive(path, raw):
    nofollow(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as writer:
        writer.write(raw)
        writer.flush()
        os.fsync(writer.fileno())


def atomic(path, raw):
    nofollow(path)
    if path.exists():
        require(stat.S_ISREG(path.lstat().st_mode), 'nonregular receipt')
    tmp = path.with_name(path.name + '.pending')
    exclusive(tmp, raw)
    os.replace(tmp, path)


def load_toolchain():
    raw = regular(TOOLCHAIN_FILE)
    require(sha256(raw).hexdigest() == TOOLCHAIN_SHA256, 'toolchain metadata identity')
    data = parse(raw)
    require(set(data) == {'version', 'release', 'target', 'date', 'manifest', 'components'}, 'toolchain fields')
    require(data['version'] == 1 and data['release'] == '1.98.0' and
            data['target'] == 'aarch64-apple-darwin' and data['date'] == '2026-08-20', 'toolchain release')
    require(set(data['manifest']) == {'url', 'bytes', 'sha256'}, 'manifest fields')
    require(data['manifest']['url'] == 'https://static.rust-lang.org/dist/channel-rust-1.98.0.toml', 'manifest URL')
    require([p['name'] for p in data['components']] == ['rustc', 'cargo', 'rust-std'], 'component inventory')
    for part in data['components']:
        require(set(part) == {'name', 'url', 'bytes', 'sha256'}, 'component fields')
        require(part['url'] == 'https://static.rust-lang.org/dist/2026-08-20/' +
                part['name'] + '-1.98.0-aarch64-apple-darwin.tar.xz', 'component URL')
    for row in [data['manifest'], *data['components']]:
        require(type(row['bytes']) is int and 0 < row['bytes'] < 100 * 1024**2 and
                re.fullmatch('[0-9a-f]{64}', row['sha256']), 'component size/hash')
    return data


def workflow_identity():
    raw=regular(REPO/'.github/workflows/macos-native-proof.yml')
    actions=re.findall(r'^\s*-?\s*uses:\s*(\S+)\s*$',raw.decode('utf-8'),re.M)
    require(len(actions)==2 and re.fullmatch(r'actions/checkout@[0-9a-f]{40}',actions[0]) and
            re.fullmatch(r'actions/upload-artifact@[0-9a-f]{40}',actions[1]),'workflow action identity')
    return {'path':'.github/workflows/macos-native-proof.yml',**identity(raw),'actions':actions}


def run_identity(env):
    for key, value in {'GITHUB_ACTIONS':'true', 'RUNNER_ENVIRONMENT':'github-hosted',
                       'GITHUB_RUN_ATTEMPT':'1', 'GITHUB_EVENT_NAME':'workflow_dispatch',
                       'GITHUB_REF':'refs/heads/main', 'GITHUB_REPOSITORY':'First-Pavilion/selahcue',
                       'ImageOS':'macos26'}.items():
        require(env.get(key) == value, 'hosted main/manual/attempt identity')
    require(re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')), 'head identity')
    require(re.fullmatch('[0-9]+', env.get('GITHUB_RUN_ID', '')) and env.get('ImageVersion'), 'run/image identity')
    return {'run_id':env['GITHUB_RUN_ID'], 'attempt':1, 'head':env['GITHUB_SHA'],
            'image_os':env['ImageOS'], 'image_version':env['ImageVersion']}


def setup_environment(root):
    return {'PATH':SAFE_PATH, 'HOME':str(root/'home'), 'TMPDIR':str(root/'tmp'),
            'CARGO_HOME':str(root/'cargo'), 'CARGO_TARGET_DIR':str(root/'target'),
            'RUSTC':str(PREFIX/'bin/rustc'), 'GIT_CONFIG_NOSYSTEM':'1',
            'GIT_CONFIG_GLOBAL':'/dev/null', 'GIT_TERMINAL_PROMPT':'0', 'GIT_OPTIONAL_LOCKS':'0',
            'CARGO_REGISTRIES_CRATES_IO_PROTOCOL':'sparse'}


def builder_environment():
    return {'PATH':SAFE_PATH, 'HOME':str(WORK/'empty-home'), 'TMPDIR':str(WORK/'tmp'),
            'CARGO_HOME':str(WORK/'cargo-home'), 'CARGO_TARGET_DIR':str(WORK/'cargo-target'),
            'CARGO_NET_OFFLINE':'true', 'RUSTC':str(PREFIX/'bin/rustc'),
            'GIT_CONFIG_NOSYSTEM':'1', 'GIT_OPTIONAL_LOCKS':'0'}


def admit_resources(samples, disk_min=8*1024**3):
    require(len(samples) == 3, 'resource sample count')
    for item in samples:
        require(item['physical_bytes'] >= 6*1024**3, 'physical memory below 6GiB')
        require(item['disk_free_bytes'] >= disk_min, 'insufficient free disk')
        require(item['pressure'] == 1, 'memory pressure not normal')
    for before, after in zip(samples, samples[1:]):
        require(after['pageouts'] <= before['pageouts'] and after['swapouts'] <= before['swapouts'], 'active paging')


class PagingMonitor:
    def __init__(self):
        self.previous = None
        self.rises = 0
        self.samples = []

    def observe(self, sample):
        if self.previous:
            rising = any(sample[k] > self.previous[k] for k in ('pageouts','swapouts'))
            self.rises = self.rises + 1 if rising else 0
        self.previous = sample
        self.samples.append(sample)
        require(self.rises < 2, 'two consecutive paging increases')


@dataclass
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class CompletedCommandFailure(Failure):
    """A completed nonzero process whose bounded result remains observable."""
    def __init__(self, message, result):
        super().__init__(message)
        self.result = result


class ProcessRunner:
    """Bound directly captured streams; kill/reap only this new process group."""
    native_executed = True

    def run(self, argv, *, cwd, env, timeout, stdin=b'', stdout_limit=4*1024**2,
            stderr_limit=1024**2, line_limit=None, sample=None, on_start=None):
        require(timeout > 0, 'command deadline')
        deadline = time.monotonic() + timeout
        proc = subprocess.Popen([str(a) for a in argv], cwd=cwd, env=env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)
        selector = selectors.DefaultSelector()
        out, err = bytearray(), bytearray()
        offset, current_line, next_sample = 0, 0, time.monotonic()
        try:
            if on_start:on_start()
            for stream, events, label in ((proc.stdout, selectors.EVENT_READ, 'out'),
                                          (proc.stderr, selectors.EVENT_READ, 'err')):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, events, label)
            if stdin:
                os.set_blocking(proc.stdin.fileno(), False)
                selector.register(proc.stdin, selectors.EVENT_WRITE, 'in')
            else:
                proc.stdin.close()
            while selector.get_map() or proc.poll() is None:
                now = time.monotonic()
                require(now < deadline, 'command timeout')
                if sample and now >= next_sample:
                    sample()
                    next_sample = now + 5
                for key, _ in selector.select(min(0.1, max(0, deadline-now))):
                    if key.data == 'in':
                        try:
                            offset += os.write(key.fd, memoryview(stdin)[offset:offset+65536])
                        except BrokenPipeError:
                            offset = len(stdin)
                        if offset == len(stdin):
                            selector.unregister(key.fileobj);key.fileobj.close()
                        continue
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj);key.fileobj.close();continue
                    buffer, limit = (out, stdout_limit) if key.data == 'out' else (err, stderr_limit)
                    require(len(buffer)+len(chunk) <= limit, 'direct stream overflow')
                    if key.data == 'out' and line_limit is not None:
                        parts = chunk.split(b'\n')
                        require(current_line+len(parts[0]) <= line_limit and
                                all(len(p) <= line_limit for p in parts[1:]), 'direct line overflow')
                        current_line = len(parts[-1]) if len(parts)>1 else current_line+len(chunk)
                    buffer.extend(chunk)
            return CommandResult(proc.wait(timeout=max(0.01, deadline-time.monotonic())), bytes(out), bytes(err))
        except BaseException:
            # The leader may exit while descendants still hold our pipes; the
            # session belongs to us even then. Never signal an ambient process.
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait(timeout=5)
            raise
        finally:
            selector.close()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if not stream.closed: stream.close()


class Ownership:
    def __init__(self, state, binding):
        self.state, self.binding = state, binding
        self.path = state/'ownership.json'
        self.entries = []

    def initialize(self):
        nofollow(self.state)
        require(not self.state.exists(), 'preexisting state')
        self.state.mkdir(mode=0o700)
        (self.state/'owned-records').mkdir(mode=0o700)
        self._save()

    def _save(self):
        atomic(self.path, wire({'binding':self.binding, 'state_identity':self._id(self.state), 'entries':self.entries}))

    @staticmethod
    def _id(path):
        info = path.lstat()
        return {'device':info.st_dev,'inode':info.st_ino,'uid':info.st_uid,'mode':stat.S_IFMT(info.st_mode)}

    def load(self):
        data = parse(regular(self.path))
        require(set(data)=={'binding','state_identity','entries'} and data['binding']==self.binding,
                'foreign ownership run')
        require(data['state_identity']==self._id(self.state), 'replaced state')
        require(type(data['entries']) is list, 'ownership entries')
        for entry in data['entries']:
            require(set(entry)=={'path','identity'}, 'ownership entry fields')
            event=self.state/'owned-records'/(sha256(entry['path'].encode()).hexdigest()+'.json')
            require(parse(regular(event))=={'binding':self.binding,'entry':entry}, 'unrecorded ownership entry')
        self.entries = data['entries']
        return data

    def record(self, path):
        nofollow(path)
        require(not any(row['path']==str(path) for row in self.entries), 'duplicate ownership')
        entry={'path':str(path),'identity':self._id(path)}
        event=self.state/'owned-records'/(sha256(str(path).encode()).hexdigest()+'.json')
        exclusive(event,wire({'binding':self.binding,'entry':entry}))
        self.entries.append(entry)
        self._save()

    def create(self, path, *, directory=True, raw=b''):
        nofollow(path)
        require(not path.exists(), 'preexisting destination')
        if directory: path.mkdir(mode=0o700)
        else: exclusive(path, raw)
        self.record(path)

    def assert_owned(self, path):
        nofollow(path)
        rows = [r for r in self.entries if r['path']==str(path)]
        require(len(rows)==1 and rows[0]['identity']==self._id(path), 'replaced/unowned path')

    def cleanup(self):
        nofollow(self.state)
        if not self.state.exists(): return {'removed':[], 'state':'absent'}
        self.load()
        # Validate the complete removal set before deleting any of it.
        for row in self.entries:
            path = Path(row['path'])
            if not path.exists() and not path.is_symlink(): continue
            self.assert_owned(path)
            if path.is_dir():
                for member in path.rglob('*'):
                    nofollow(member)
                    require(member.lstat().st_uid==os.getuid() and
                            (member.is_dir() or stat.S_ISREG(member.lstat().st_mode)), 'foreign cleanup member')
        removed = []
        for row in reversed(self.entries):
            path = Path(row['path'])
            if not path.exists(): continue
            self.assert_owned(path)
            if path.is_dir(): shutil.rmtree(path)
            else: path.unlink()
            removed.append(str(path))
        return {'removed':removed, 'state':'retained'}


def tuples(raw):
    require(tomllib is not None, 'Python 3.11 required')
    rows = [[p['name'],p['version'],p['source'],p['checksum']]
            for p in tomllib.loads(raw.decode('utf-8'))['package'] if 'source' in p]
    require(len(rows)==len({tuple(p) for p in rows}), 'duplicate registry tuple')
    require(all(p[2]=='registry+https://github.com/rust-lang/crates.io-index' and
                re.fullmatch('[0-9a-f]{64}',p[3]) for p in rows), 'nonpublic registry tuple')
    return sorted(rows)


def verify_registry(root, expected):
    nofollow(root)
    for name in ('cache','index','src'):
        require((root/name).is_dir(), 'absent cache')
    for path in root.rglob('*'):
        nofollow(path)
        require(path.is_dir() or stat.S_ISREG(path.lstat().st_mode), 'nonregular registry member')
    stores = list((root/'cache').iterdir())
    require(len(stores)==1 and stores[0].name.startswith('index.crates.io-'), 'registry cache origin')
    origin = stores[0].name
    require({p.name for p in (root/'src').iterdir()}=={origin} and
            {p.name for p in (root/'index').iterdir()}=={origin}, 'registry origin mismatch')
    config = parse(regular(root/'index'/origin/'config.json'))
    require(config == {'dl':'https://static.crates.io/crates','api':'https://crates.io'}, 'registry endpoint')
    names = {name+'-'+version for name,version,_,_ in expected}
    require({p.name for p in stores[0].iterdir()}=={n+'.crate' for n in names}, 'registry archive inventory')
    require({p.name for p in (root/'src'/origin).iterdir()}==names, 'registry source inventory')
    for name,version,source,digest in expected:
        require(source=='registry+https://github.com/rust-lang/crates.io-index', 'registry source')
        package = name+'-'+version
        archive_raw=regular(stores[0]/(package+'.crate'),100*1024**2)
        require(sha256(archive_raw).hexdigest()==digest, 'crate archive checksum')
        unpacked = root/'src'/origin/package
        # Cargo797e8a9bc fetch generates only this fresh completion marker.
        # Its extracted registry tree has no vendor .cargo-checksum.json.
        require(regular(unpacked/'.cargo-ok',7)==b'{"v":1}', 'Cargo extraction marker')
        archive_files, archive_dirs, seen = {}, set(), set()
        # Derive expectations from the same bytes authenticated against the
        # lock, never an extracted checksum manifest or an unchecked reread.
        with tarfile.open(fileobj=io.BytesIO(archive_raw),mode='r:gz') as archive:
            for member in archive:
                path=PurePosixPath(member.name)
                require(not path.is_absolute() and '..' not in path.parts and path.parts and path.parts[0]==package,
                        'crate archive traversal')
                require(member.isdir() or member.isfile(), 'crate archive special member')
                relative=PurePosixPath(*path.parts[1:])
                name=relative.as_posix()
                require(name not in seen, 'crate archive duplicate')
                seen.add(name)
                require(name!='.cargo-ok' and not name.startswith('.cargo-ok/'), 'archive-supplied Cargo marker')
                if name=='.':
                    require(member.isdir(), 'crate archive root kind')
                    continue
                archive_dirs.update(str(parent) for parent in relative.parents if str(parent)!='.')
                if member.isdir():
                    archive_dirs.add(name)
                    continue
                require(member.size<=100*1024**2, 'crate archive file size')
                digest_file=sha256()
                with archive.extractfile(member) as reader:
                    while True:
                        chunk=reader.read(65536)
                        if not chunk:break
                        digest_file.update(chunk)
                archive_files[name]=digest_file.hexdigest()
        actual_files, actual_dirs = set(), set()
        for path in unpacked.rglob('*'):
            relative=path.relative_to(unpacked).as_posix()
            (actual_dirs if path.is_dir() else actual_files).add(relative)
        require(actual_files==set(archive_files)|{'.cargo-ok'}, 'unpacked file inventory')
        require(actual_dirs==archive_dirs, 'unpacked directory inventory')
        for relative,want in archive_files.items():
            require(sha256(regular(unpacked/relative,100*1024**2)).hexdigest()==want, 'unpacked file checksum')
    return {'packages':len(expected),'tuples':expected}


def export_members(stage, target):
    nofollow(stage);nofollow(target)
    require({p.name for p in stage.iterdir()}==set(RECEIPT_MEMBERS), 'missing/unapproved artifact member')
    members, total = [], 0
    for name in RECEIPT_MEMBERS:
        raw = regular(stage/name)
        total += len(raw)
        members.append({'path':name, **identity(raw)})
    manifest = {'version':1,'members':members}
    manifest_raw = wire(manifest)
    require(total+len(manifest_raw)<=ARTIFACT_LIMIT, 'artifact over 20MiB')
    require(not target.exists(), 'preexisting export')
    target.mkdir(mode=0o700)
    for row in members:
        raw=regular(stage/row['path'])
        require(identity(raw)=={k:row[k] for k in ('bytes','sha256')}, 'artifact changed during export')
        exclusive(target/row['path'],raw)
    exclusive(target/'artifact-manifest.json',manifest_raw)
    return manifest


class SystemHost:
    native_executed = True
    def __init__(self): self.process = ProcessRunner()
    def clock(self): return time.monotonic()
    def sleep(self, seconds): time.sleep(seconds)

    def command(self, argv, **kwargs):
        result = self.process.run(argv, **kwargs)
        if result.returncode != 0:
            raise CompletedCommandFailure('command failed: '+Path(str(argv[0])).name, result)
        return result

    def _query(self, *argv, timeout=10):
        return self.command(argv, cwd=REPO, env={'PATH':SAFE_PATH}, timeout=timeout).stdout.decode('utf-8').strip()

    def facts(self):
        require(platform.system()=='Darwin' and platform.machine()=='arm64', 'Darwin arm64 required')
        require(sys.version_info >= (3,11), 'Python 3.11 required')
        return {'system':platform.system(), 'machine':platform.machine(),
                'python':list(sys.version_info[:3]), 'python_executable':str(Path(sys.executable).resolve()),
                'python_identity':identity(regular(Path(sys.executable).resolve(),100*1024**2)),
                'macos':self._query('/usr/bin/sw_vers'),
                'xcode':self._query('/usr/bin/xcodebuild','-version'),
                'sdk':self._query('/usr/bin/xcrun','--sdk','macosx','--show-sdk-path'),
                'sdk_version':self._query('/usr/bin/xcrun','--sdk','macosx','--show-sdk-version'),
                'clang':self._query('/usr/bin/clang','--version')}

    def sample(self):
        deadline=self.clock()+4
        def query(*argv):
            return self._query(*argv,timeout=max(0.01,deadline-self.clock()))
        raw = query('/usr/bin/vm_stat')
        page = re.search(r'page size of (\d+) bytes',raw)
        require(page is not None, 'vm_stat page size')
        values = {key:int(value) for key,value in re.findall(r'^([^:\n]+):\s*(\d+)\.',raw,re.M)}
        require(all(k in values for k in ('Pageouts','Swapouts','Pages free','Pages inactive')), 'vm_stat fields')
        size = int(page.group(1))
        return {'physical_bytes':int(query('/usr/sbin/sysctl','-n','hw.memsize')),
                'disk_free_bytes':min(shutil.disk_usage('/Users').free,shutil.disk_usage('/private/tmp').free),
                'pressure':int(query('/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level')),
                'pageouts':values['Pageouts'], 'swapouts':values['Swapouts'],
                'free_bytes':values['Pages free']*size,
                'available_bytes':(values['Pages free']+values['Pages inactive'])*size,
                'swap':query('/usr/sbin/sysctl','-n','vm.swapusage')}

    def clone_probe(self, root):
        import ctypes
        import plistlib
        fs = plistlib.loads(self.command(['/usr/sbin/diskutil','info','-plist','/private/tmp'],
                             cwd=REPO,env={'PATH':SAFE_PATH},timeout=10).stdout)
        require(fs.get('FilesystemType')=='apfs', 'APFS required')
        original, clone = root/'clone-original', root/'clone-copy'
        exclusive(original,b'clone probe\n')
        library = ctypes.CDLL(None,use_errno=True)
        clonefile = library.clonefile
        clonefile.argtypes = (ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int)
        clonefile.restype = ctypes.c_int
        require(clonefile(os.fsencode(original),os.fsencode(clone),0)==0,'APFS clone unavailable')
        require(regular(clone)==b'clone probe\n','clone bytes')
        with clone.open('wb') as writer: writer.write(b'independent\n')
        require(regular(original)==b'clone probe\n','clone independence')
        original.unlink();clone.unlink()
        return {'apfs_clone':True,'filesystem':fs.get('FilesystemType')}

    def network_probe(self, *, cwd, env, timeout):
        require(Path('/usr/bin/sandbox-exec').is_file(), 'sandbox-exec unavailable')
        probe = ('import socket,errno,sys; s=socket.socket(); s.settimeout(1); '
                 'r=s.connect_ex(("127.0.0.1",9)); s.close(); '
                 'sys.exit(0 if r in (errno.EPERM,errno.EACCES) else 1)')
        result = self.command(['/usr/bin/sandbox-exec','-p',PROFILE,sys.executable,'-I','-S','-B','-c',probe],
                              cwd=cwd,env=env,timeout=timeout)
        require(result.returncode==0 and not result.stdout and not result.stderr, 'network denial probe failed/output')
        return {'denied':True,'profile_sha256':sha256(PROFILE.encode()).hexdigest()}

    def download(self, row, target, deadline):
        require(self.clock()<deadline, 'setup deadline')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(row['url'],timeout=max(0.1,min(20,deadline-self.clock()))) as response:
            require(response.status==200 and response.url==row['url'], 'official download response')
            fd = os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            digest, size = sha256(), 0
            with os.fdopen(fd,'wb') as writer:
                while True:
                    require(self.clock()<deadline, 'setup deadline')
                    chunk = response.read(65536)
                    if not chunk: break
                    size += len(chunk)
                    require(size<=row['bytes'], 'download length overflow')
                    writer.write(chunk);digest.update(chunk)
            require(size==row['bytes'] and digest.hexdigest()==row['sha256'], 'official download identity')


def extract_distribution(archive, destination, deadline, clock):
    """Extract only archive-contained regular files/directories, never devices.

    Rust distribution installers do not require archive symlinks. If the pinned
    distribution contains one, fail closed rather than follow it during setup.
    """
    destination.mkdir(mode=0o700)
    total, seen = 0, set()
    with tarfile.open(archive,'r:xz') as tar:
        for member in tar:
            require(clock()<deadline, 'setup deadline')
            relative = PurePosixPath(member.name)
            require(not relative.is_absolute() and '..' not in relative.parts and member.name not in seen,
                    'distribution traversal/duplicate')
            seen.add(member.name)
            require(member.isfile() or member.isdir(), 'distribution link/special member')
            target = destination/relative
            nofollow(target)
            if member.isdir(): target.mkdir(mode=0o700,parents=True,exist_ok=True);continue
            total += member.size
            require(total<=1024**3 and member.size<=300*1024**2, 'distribution expanded cap')
            target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with tar.extractfile(member) as reader:
                fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700 if member.mode&0o111 else 0o600)
                with os.fdopen(fd,'wb') as writer: shutil.copyfileobj(reader,writer,65536)
    return total


class ProofRun:
    """Internal injected backend/paths support inert tests; CLI supplies none."""
    def __init__(self, host=None, state=STATE, export=EXPORT, env=None):
        self.host = host or SystemHost()
        self.state, self.export = state, export
        self.receipts = state/'receipts'
        self.env = os.environ if env is None else env
        self.run = run_identity(self.env)
        self.binding = None
        self.owner = None
        self.deadline = None
        self.commands = []
        self.active_stage = None

    def _inputs(self):
        require(sys.version_info >= (3,11), 'Python 3.11 required')
        verified = fixtures.verify_inputs()
        load_toolchain()
        batches, rejects = fixtures.prepare_batches()
        require(len(rejects)==47 and all(c.passed for c in rejects), 'pure rejects')
        return verified | {'batches':fixtures.frame_inventory(batches),
                           'pure_rejections':[c.name for c in rejects],
                           'toolchain':identity(regular(TOOLCHAIN_FILE)),
                           'workflow':workflow_identity(),
                           'runner':identity(regular(Path(__file__).absolute()))}

    def _initialize(self, inputs):
        self.binding = self.run | {'inputs':inputs}
        self.owner = Ownership(self.state,self.binding)
        self.owner.initialize()
        self.receipts.mkdir(mode=0o700)
        self.started = self.host.clock()
        exclusive(self.state/'run-state.json',wire({'binding':self.binding,'started':self.started,
                                                   'receipts':{},'builder_started':False}))
        self._receipt('run.json', {'binding':self.binding,'started':self.started,
                                 'native_executed':False,'commands':[],
                                 'workflow':'.github/workflows/macos-native-proof.yml'})
        manifest = fixtures._input_manifest()
        self._receipt('inputs.json',{'binding':self.binding,'verification':inputs,
                                     'inventory':manifest})

    def _load(self):
        data = parse(regular(self.state/'run-state.json'))
        self.binding = self.run | {'inputs':self._inputs()}
        require(data['binding']==self.binding,'stage run/head/input mismatch')
        self.owner = Ownership(self.state,self.binding);self.owner.load()
        self.started = data['started']
        require(self.host.clock()-self.started<1200,'overall job deadline')
        return data

    def _receipt_bytes(self,name,raw):
        require(name in RECEIPT_MEMBERS,'unapproved receipt')
        atomic(self.receipts/name,raw)
        path = self.state/'run-state.json'
        if path.exists():
            data = parse(regular(path));data['receipts'][name]=identity(raw);atomic(path,wire(data))

    def _receipt(self,name,data): self._receipt_bytes(name,wire(data))

    def _prior(self,name):
        state = self._load()
        raw = regular(self.receipts/name)
        require(state['receipts'].get(name)==identity(raw),'previous receipt identity')
        receipt = parse(raw)
        require(receipt['binding']==self.binding and receipt['status']=='passed','previous stage incomplete')
        return receipt

    def _begin(self,name):
        require(not (self.receipts/name).exists(),'stage already attempted')
        value = {'binding':self.binding,'status':'running','native_executed':False,
                 'started':self.host.clock(),'commands':[]}
        self._receipt(name,value)
        self.active_stage = name
        return value

    def _finish(self,name,value,error=None):
        value.update(status='failed' if error else 'passed',finished=self.host.clock(),commands=self.commands)
        if error: value['error']=str(error) if isinstance(error,Failure) else type(error).__name__
        self._receipt(name,value)
        self.active_stage = None

    def _command(self,argv,*,env=None,cwd=None,timeout=30,**kwargs):
        if self.deadline is not None:
            timeout=min(timeout,self.deadline-self.host.clock())
        require(timeout>0,'phase deadline')
        attempt={'argv':[str(a) for a in argv],'status':'running'}
        self.commands.append(attempt)
        def persist():
            if self.active_stage:
                receipt=parse(regular(self.receipts/self.active_stage))
                receipt['commands']=self.commands
                self._receipt(self.active_stage,receipt)
        persist()
        try:
            result=self.host.command([str(a) for a in argv],cwd=cwd or self.state,
                                     env=env or setup_environment(self.state/'setup'),timeout=timeout,**kwargs)
            attempt.update(exit=result.returncode,stdout=identity(result.stdout),stderr=identity(result.stderr))
            require(result.returncode==0,'command nonzero exit')
            attempt['status']='passed'
            return result.stdout
        except BaseException as exc:
            if isinstance(exc,CompletedCommandFailure):
                result=exc.result
                attempt.update(exit=result.returncode,stdout=identity(result.stdout),stderr=identity(result.stderr))
            attempt.update(status='failed',error=str(exc) if isinstance(exc,Failure) else type(exc).__name__)
            raise
        finally: persist()

    def _paths_absent(self):
        for path in (USER_ROOT,O,PIN,SPEC,self.export):
            nofollow(path);require(not path.exists(),'preexisting fixed destination')
        self._no_config()

    def _no_config(self):
        for path in (REPO,O,S,self.state):
            for ancestor in (path,*path.parents):
                for name in ('.cargo/config','.cargo/config.toml'):
                    candidate=ancestor/name
                    nofollow(candidate)
                    require(not candidate.exists(),'ambient Cargo configuration')

    def admit_host(self):
        # Initialize diagnostic receipts before platform/resources; no staged
        # path is owned yet. Invalid hosted identity never creates anything.
        inputs=self._inputs();self._initialize(inputs)
        value=self._begin('admission.json')
        self.deadline=self.started+60
        try:
            self._paths_absent()
            value['host']=self.host.facts()
            require(value['host']['system']=='Darwin' and value['host']['machine']=='arm64', 'Darwin arm64 required')
            require(tuple(value['host']['python'])>=(3,11),'Python 3.11 required')
            head=self._command(['/usr/bin/git','rev-parse','HEAD'],cwd=REPO).decode().strip()
            require(head==self.run['head'],'checkout head mismatch')
            self._command(['/usr/bin/git','diff','--exit-code','HEAD','--',
                           'scripts/macos_native_proof.py','scripts/macos_native_fixtures.py',
                           'scripts/fixtures/macos-native-toolchain.json','scripts/fixtures/macos-native-proof',
                           '.github/workflows/macos-native-proof.yml'],cwd=REPO)
            self._command(['/usr/bin/git','merge-base','--is-ancestor',NORMATIVE,head],cwd=REPO)
            self._command(['/usr/bin/git','cat-file','-e',NORMATIVE+'^{commit}'],cwd=REPO)
            value['clone']=self.host.clone_probe(self.state)
            samples=[]
            for index in range(3):
                if index:self.host.sleep(5)
                samples.append(self.host.sample())
                value['resources']=samples
                self._receipt('admission.json',value)
            admit_resources(samples)
            require(self.host.clock()<self.deadline,'admission deadline')
            self._finish('admission.json',value);return value
        except BaseException as exc:
            self._finish('admission.json',value,exc);raise

    def _mkdir_under(self,path,root):
        require(path==root or path.is_relative_to(root),'directory outside owned root')
        nofollow(path)
        path.mkdir(parents=True,mode=0o700,exist_ok=True)

    def _stage_inputs(self):
        # Only this missing namespace creation may use sudo. No shell and no
        # privilege is used for downloads, installation, fetching or compiling.
        nofollow(USER_ROOT);require(not USER_ROOT.exists(),'preexisting namespace')
        self._command(['/usr/bin/sudo','-n','/bin/mkdir','-m','700',USER_ROOT])
        self._command(['/usr/bin/sudo','-n','/usr/sbin/chown',str(os.getuid())+':'+str(os.getgid()),USER_ROOT])
        self.owner.record(USER_ROOT)
        self._mkdir_under(S.parent,USER_ROOT)
        self._command(['/usr/bin/git','-c','core.hooksPath=/dev/null','worktree','add','--detach',S,NORMATIVE],cwd=REPO)
        # All later Git operates on this local worktree, without checkout token.
        parent=O.parent
        nofollow(parent)
        if not parent.exists():self.owner.create(parent)
        self.owner.create(O)
        for row in fixtures._input_manifest()['payloads']:
            dest=Path(row['destination']);raw=fixtures._verified_member(row)
            require(dest.is_relative_to(O) or dest in (PIN,SPEC),'unapproved staging destination')
            if dest in (PIN,SPEC):self.owner.create(dest,directory=False,raw=raw)
            else:
                self._mkdir_under(dest.parent,O);exclusive(dest,raw)
            require(identity(regular(dest))=={k:row[k] for k in ('bytes','sha256')},'staged input identity')
        require(not WORK.exists(),'stale native target')
        for name in ('home','tmp','cargo','target','downloads'):
            self._mkdir_under(self.state/'setup'/name,self.state)
        self._no_config()

    def _source_check(self):
        pins=parse(fixtures._payload_bytes('external/selahcue-notes-native-input-pin-20261115.json'))
        require(pins['normative_native_commit']==NORMATIVE and pins['source_root']==str(S),'source pin binding')
        expected=pins['file_sha256'];require(len(expected)==102,'102 source pins required')
        tree=self._command(['/usr/bin/git','ls-tree','-r',NORMATIVE,'--',*SCOPE],cwd=S)
        require(sha256(tree).hexdigest()=='d7b7e81581e721e0e6f623e05d481d59df3c6fee7a6f0a05df4efa1900c03529','scoped Git tree fingerprint')
        names={line.split('\t',1)[1] for line in tree.decode().splitlines()}
        require(names==set(expected),'source inventory')
        for relative,digest in expected.items():
            require(sha256(regular(S/relative)).hexdigest()==digest,'source hash drift')
        require(self._command(['/usr/bin/git','rev-parse','HEAD'],cwd=S).decode().strip()==NORMATIVE,'normative detached head')
        require(self._command(['/usr/bin/git','rev-parse','--abbrev-ref','HEAD'],cwd=S).decode().strip()=='HEAD','source is not detached')
        self._command(['/usr/bin/git','diff','--exit-code',NORMATIVE,'--',*SCOPE],cwd=S)
        require(not self._command(['/usr/bin/git','ls-files','--others','--',*SCOPE],cwd=S),'untracked scoped source')
        require(sha256(regular(OWNER_LOCK)).hexdigest()==OWNER_LOCK_SHA256,'owner lock drift')
        return {'files':102,'normative_commit':NORMATIVE,'tree_sha256':sha256(tree).hexdigest(),
                'file_sha256':expected}

    def _tool_versions(self):
        rust=self._command([PREFIX/'bin/rustc','-vV']).decode()
        cargo=self._command([PREFIX/'bin/cargo','--version']).decode().strip()
        require(rust.startswith('rustc 1.98.0 (88d9e12ae ') and '\nhost: aarch64-apple-darwin\n' in rust and
                '\nrelease: 1.98.0\n' in rust,'wrong rustc version/target')
        require(cargo.startswith('cargo 1.98.0 (797e8a9bc ') and cargo.endswith(')'),'wrong cargo version')
        return {'rustc':rust,'cargo':cargo,'executables':{
            name:identity(regular(PREFIX/'bin'/name,100*1024**2)) for name in ('rustc','cargo')}}

    def _install(self):
        metadata=load_toolchain();downloads=self.state/'setup/downloads'
        self.host.download(metadata['manifest'],downloads/'release.toml',self.deadline)
        manifest=tomllib.loads(regular(downloads/'release.toml').decode())
        require(manifest['date']==metadata['date'],'release date')
        for row in metadata['components']:
            record=manifest['pkg'][row['name']]['target']['aarch64-apple-darwin']
            require(record['available'] and record['xz_url']==row['url'] and record['xz_hash']==row['sha256'],
                    'official manifest component mismatch')
            archive=downloads/(row['name']+'.tar.xz')
            self.host.download(row,archive,self.deadline)
            extracted=downloads/row['name']
            extract_distribution(archive,extracted,self.deadline,self.host.clock)
            root=extracted/(row['name']+'-1.98.0-aarch64-apple-darwin')
            require({p.name for p in extracted.iterdir()}=={root.name},'distribution root')
            self._command(['/bin/sh',root/'install.sh','--prefix='+str(PREFIX),'--disable-ldconfig'],cwd=root,
                          timeout=self.deadline-self.host.clock())
        installed=[]
        for path in sorted(PREFIX.rglob('*')):
            nofollow(path)
            require(path.is_dir() or stat.S_ISREG(path.lstat().st_mode),'installed special member')
            if path.is_file():installed.append({'path':path.relative_to(PREFIX).as_posix(),'bytes':path.stat().st_size})
        return {'metadata':metadata,'metadata_identity':identity(regular(TOOLCHAIN_FILE)),
                'installed_inventory':installed,**self._tool_versions()}

    def _installed_check(self):
        setup=parse(regular(self.receipts/'setup.json'))
        expected=setup['toolchain']['executables']
        actual={name:identity(regular(PREFIX/'bin'/name,100*1024**2)) for name in ('rustc','cargo')}
        require(actual==expected,'installed executable drift')
        installed=[]
        for path in sorted(PREFIX.rglob('*')):
            nofollow(path)
            require(path.is_dir() or stat.S_ISREG(path.lstat().st_mode),'installed special member')
            if path.is_file():installed.append({'path':path.relative_to(PREFIX).as_posix(),'bytes':path.stat().st_size})
        require(installed==setup['toolchain']['installed_inventory'],'installed inventory drift')
        return {'executables':actual,'registry':verify_registry(REGISTRY,self._expected_tuples())}

    def _expected_tuples(self):
        raw=regular(SCRATCH_LOCK)
        require(sha256(raw).hexdigest()==LOCK_SHA256,'scratch lock drift')
        expected=tuples(raw)
        require(len(expected)==56 and set(map(tuple,expected))<=set(map(tuple,tuples(regular(OWNER_LOCK)))),
                '56 owner-subset registry tuples')
        return expected

    def _fetch(self):
        expected=self._expected_tuples()
        self._command([PREFIX/'bin/cargo','fetch','--locked','--manifest-path',O/'native-golden/Cargo.toml'],
                      timeout=self.deadline-self.host.clock())
        require(self._expected_tuples()==expected,'fetch changed lock/tuples')
        root=self.state/'setup/cargo/registry'
        receipt=verify_registry(root,expected)
        self._mkdir_under(REGISTRY.parent,USER_ROOT)
        require(not REGISTRY.exists(),'preexisting seeded registry')
        # Only three verified registry subtrees are staged, never credentials,
        # Cargo config, HOME or the entire setup Cargo directory.
        REGISTRY.mkdir(mode=0o700)
        for name in ('cache','index','src'):
            self._command(['/bin/cp','-cR',root/name,REGISTRY/name])
        require(verify_registry(REGISTRY,expected)==receipt,'seeded registry mismatch')
        return receipt

    def _metadata(self):
        env=setup_environment(self.state/'setup')|{'CARGO_NET_OFFLINE':'true'}
        raw=self._command(['/usr/bin/sandbox-exec','-p',PROFILE,PREFIX/'bin/cargo','metadata','--frozen',
                           '--format-version','1','--manifest-path',O/'native-golden/Cargo.toml'],env=env)
        data=parse(raw)
        features={n['id']:n['features'] for n in data['resolve']['nodes']}
        local={p['name']:features[p['id']] for p in data['packages'] if p['source'] is None}
        require(local==FEATURES,'local feature mismatch')
        expected=self._expected_tuples()
        resolved=sorted([p['name'],p['version'],p['source']] for p in data['packages'] if p['source'] is not None)
        require(resolved==[p[:3] for p in expected],'resolved registry tuple mismatch')
        return {'metadata':identity(raw),'local_features':local,'tuples':expected}

    def _postcheck(self):
        self._inputs();self._no_config()
        for row in fixtures._input_manifest()['payloads']:
            require(identity(regular(Path(row['destination'])))=={k:row[k] for k in ('bytes','sha256')},
                    'staged source/lock drift')
        source=self._source_check()
        self._expected_tuples()
        return source

    def provision(self):
        self._prior('admission.json')
        value=self._begin('setup.json');self.commands=[]
        self.deadline=min(self.host.clock()+300,self.started+1080)
        try:
            self._stage_inputs();value['source']=self._source_check()
            value['toolchain']=self._install();self._receipt('setup.json',value)
            value['registry']=self._fetch()
            value['network']=self.host.network_probe(cwd=self.state,env=setup_environment(self.state/'setup'),
                                                      timeout=min(5,self.deadline-self.host.clock()))
            value['metadata']=self._metadata();value['postcheck']=self._postcheck()
            require(self.host.clock()<self.deadline,'setup deadline')
            self._finish('setup.json',value);return value
        except BaseException as exc:
            self._finish('setup.json',value,exc);raise

    def _build_receipt(self):
        raw=regular(O/'fixtures/native/build.json')
        build=parse(raw)
        require(build['registry_tuples']==self._expected_tuples() and build['local_features']==FEATURES,
                'builder registry/features')
        require(build['lock_sha256']==LOCK_SHA256 and build['owning_lock_sha256']==OWNER_LOCK_SHA256,
                'builder lock identity')
        require(build['binary_path']==str(BINARY) and build['binary_sha256']==sha256(regular(BINARY,200*1024**2)).hexdigest(),
                'stale binary receipt')
        require(set(build['dep_info'])=={'core','cloud','scripture'} and build['generated_file_sha256'],
                'missing dep-info/generated source')
        for name,details in build['dep_info'].items():
            require('implementation/desktop/crates/selahcue-'+name+'/src/lib.rs' in details['paths'], 'missing compiled source')
        for name,digest in build['generated_file_sha256'].items():
            path=Path(name)
            require(path.is_relative_to(WORK/'cargo-target') and path.name=='verse_runs.rs','generated source path')
            require(sha256(regular(path)).hexdigest()==digest,'generated source drift')
        self._receipt_bytes('build.json',raw)
        self._receipt_bytes('feature-tree.txt',regular(O/'fixtures/native/feature-tree.txt'))
        return {'binary_sha256':build['binary_sha256'],'raw_receipt':identity(raw)}

    def _batches(self): return fixtures.prepare_batches()

    def run_frozen(self):
        self._prior('setup.json')
        value=self._begin('proof.json');self.commands=[]
        self.deadline=min(self.host.clock()+600,self.started+960)
        monitor=PagingMonitor()
        try:
            self._postcheck()
            value['installed']=self._installed_check()
            sample=self.host.sample();value['prebuild_resources']=sample
            self._receipt('proof.json',value)
            admit_resources([sample]*3,disk_min=6*1024**3)
            value['network']=self.host.network_probe(cwd=self.state,env=builder_environment(),timeout=5)
            value['metadata']=self._metadata()
            batches,rejects=self._batches()
            require(len(batches)==11 and sum(len(b.frames) for b in batches)==1111 and
                    len(rejects)==47 and all(r.passed for r in rejects),'proof fixture counts')
            value.update(pure_rejections=[r.name for r in rejects],batches=[])
            self._receipt('proof.json',value)
            require(not BINARY.exists() and not (O/'fixtures/native/build.json').exists(),'stale build output')
            state=parse(regular(self.state/'run-state.json'))
            require(not state['builder_started'],'builder already invoked')
            state['builder_started']=True;atomic(self.state/'run-state.json',wire(state))
            command=['/usr/bin/sandbox-exec','-p',PROFILE,sys.executable,'-I','-S','-B',BUILDER]
            value.update(build_executed=False,build_completed=False,native_executed=False)
            self._receipt('proof.json',value)
            def began(kind):
                value[kind]=bool(self.host.native_executed)
                self._receipt('proof.json',value)
            def resource_sample():
                try: monitor.observe(self.host.sample())
                finally:
                    value['resource_samples']=monitor.samples
                    self._receipt('proof.json',value)
            self._command(command,cwd=O,env=builder_environment(),timeout=600,sample=resource_sample,
                          on_start=lambda:began('build_executed'))
            value['build_completed']=bool(self.host.native_executed)
            self._command([*command,'--verify'],cwd=O,env=builder_environment())
            value['build']=self._build_receipt();value['resource_samples']=monitor.samples
            self._postcheck()
            require(self.host.clock()<self.deadline,'build deadline')
            # One shared deadline covers every comparator call and comparison,
            # not eleven independently renewable timeouts.
            self.deadline=min(self.host.clock()+120,self.started+1080)
            total=0
            for batch in batches:
                stdout=self._command(['/usr/bin/sandbox-exec','-p',PROFILE,BINARY],cwd=O,
                                     env={'PATH':'/usr/bin:/bin'},stdin=batch.stdin,timeout=30,
                                     stdout_limit=fixtures.MAX_STDOUT-total,stderr_limit=0,
                                     line_limit=fixtures.MAX_LINE,on_start=lambda:began('native_executed'))
                total+=len(stdout)
                checked=fixtures.check_observations(batch.name,stdout)
                value['batches'].append({'input':identity(batch.stdin),**checked})
                self._receipt('proof.json',value)
                require(self.host.clock()<self.deadline,'comparator deadline')
            self._command([*command,'--verify'],cwd=O,env=builder_environment())
            self._build_receipt();value['postcheck']=self._postcheck()
            value['installed_postcheck']=self._installed_check()
            value['post_resources']=self.host.sample()
            require(value['post_resources']['pressure']==1,'post-proof memory pressure')
            require(self.host.clock()<self.deadline,'proof deadline')
            self._finish('proof.json',value);return value
        except BaseException as exc:
            value['resource_samples']=monitor.samples
            self._finish('proof.json',value,exc);raise

    def export_receipts(self):
        # Missing stage state is a truthful incomplete finalization, never an
        # authority to claim staging or delete a fixed path.
        if not self.state.exists():
            self._initialize(self._inputs())
        state=self._load()
        result={'binding':self.binding,'status':'incomplete','native_executed':False,'stages':{}}
        try:
            for name in ('admission.json','setup.json','proof.json'):
                if (self.receipts/name).exists():
                    raw=regular(self.receipts/name)
                    require(state['receipts'].get(name)==identity(raw),'final receipt drift')
                    stage=parse(raw);result['stages'][name]=stage['status']
                    if name=='proof.json':result['native_executed']=stage.get('native_executed',False)
                else: result['stages'][name]='missing'
            if all(v=='passed' for v in result['stages'].values()):
                result['postcheck']=self._postcheck()
                self._build_receipt()
                result['status']='passed' if result['native_executed'] else 'inert-tests-only'
            self._receipt('result.json',result)
            run=parse(regular(self.receipts/'run.json'))
            run.update(finished=self.host.clock(),elapsed=self.host.clock()-self.started,
                       native_executed=result['native_executed'],stage_status=result['stages'])
            for name, fields in (('admission.json',('host',)),('setup.json',('source','toolchain'))):
                if (self.receipts/name).exists():
                    stage=parse(regular(self.receipts/name))
                    for field in fields:
                        if field in stage:run[field]=stage[field]
            self._receipt('run.json',run)
            # Export isn't a cleanup target: retain it after any upload attempt.
            manifest=export_members(self.receipts,self.export)
            exclusive(self.state/'export-ownership.json',wire({'binding':self.binding,
                'path':str(self.export),'identity':Ownership._id(self.export),'manifest':identity(regular(self.export/'artifact-manifest.json'))}))
            return {'result':result,'artifact_manifest':manifest}
        except BaseException as exc:
            result.update(status='incomplete',error=str(exc) if isinstance(exc,Failure) else type(exc).__name__)
            self._receipt('result.json',result)
            raise

    def cleanup(self):
        nofollow(self.state)
        if not self.state.exists():return {'removed':[],'state':'absent'}
        # Cleanup cannot depend on a successful input/postcheck after failure,
        # but still requires same hosted run/head and the authenticated journal.
        state=parse(regular(self.state/'run-state.json'))
        binding=state['binding']
        require(all(binding.get(k)==v for k,v in self.run.items()),'cleanup foreign run')
        owner=Ownership(self.state,binding)
        return owner.cleanup()


def admit_host() -> dict: return ProofRun().admit_host()
def provision() -> dict: return ProofRun().provision()
def run_frozen() -> dict: return ProofRun().run_frozen()
def export_receipts() -> dict: return ProofRun().export_receipts()
def cleanup() -> dict: return ProofRun().cleanup()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('admit','setup','prove','finalize','cleanup'))
    args=parser.parse_args()
    functions={'admit':admit_host,'setup':provision,'prove':run_frozen,
               'finalize':export_receipts,'cleanup':cleanup}
    try:
        result=functions[args.command]()
        print(json.dumps({'command':args.command,'completed':True,
                          'native_executed':result.get('native_executed',False)},sort_keys=True))
        return 0
    except (Failure,fixtures.ProofError,OSError,KeyError,ValueError) as exc:
        print('native proof '+args.command+' failed: '+(str(exc) if isinstance(exc,Failure) else type(exc).__name__),file=sys.stderr)
        return 1


if __name__=='__main__': raise SystemExit(main())
