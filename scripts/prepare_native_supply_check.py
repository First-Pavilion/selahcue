#!/usr/bin/env python3
"""Fixed audit-only mirror of the sealed native Cargo root; never build native code.

CLI: prepare, postcheck, cleanup. Only hosted preparation runs locked metadata.
The direct cargo-deny command remains visible in ci.yml, outside this helper.
"""
from __future__ import annotations

import argparse
from hashlib import sha1, sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path('scripts/fixtures/macos-native-proof/payloads/native-golden')
PIN = Path('scripts/fixtures/macos-native-proof/payloads/external/selahcue-notes-native-input-pin-20261115.json')
PIN_SHA = 'f3f6dbb0f33098d5e723701c3d1cdb7f0f9f157242fb0bd55a47b434d06b864f'
NORMATIVE = '1ea22e1ce6e52ab8aa2e0fd83fda1c9d90b094da'
SOURCE_SCOPE = ('implementation/desktop', 'rust-toolchain.toml')
SOURCE_TREE = 'b3ca85ff73f20e94ab9e95b3b5b3a1b5114506ad0b4153b669f7cf7aa0cfd9a9'
SOURCE_COUNT, SOURCE_BYTES = 497, 20137093  # Includes root rust-toolchain.toml: 2,256 bytes.
MAX_FILES, MAX_SOURCE_BYTES = 600, 32 * 1024**2
POLICY_SHA = '1178af0821a4d10221e516a5f5b170c5203e7064be88ac25743804110a99014d'
OWNER_SHA = '684937aa63ab251c37fd84d1cb863e0c0c8ff8e938df4c2cdce9871b5a0e9e97'
INPUT_PINS = {
    'Cargo.toml': (751, '71cd48fb470a9fe9cb3fef092b46878429a7f9e4fc985651bfe5cf0f15344ef3'),
    'Cargo.lock': (13676, 'a78dcb39e5e302086a11c214800ab6875a07d4d7413ce428e1e0d068ab3c0718'),
    'src/main.rs': (8490, 'fce22c69defa8cd1e98150f8791a1a6f3a9939d6f709043d2fb8eb38834b8da5'),
}
FEATURES = {'coverage-native-golden': [], 'selahcue-cloud': ['openai'],
            'selahcue-core': [], 'selahcue-scripture': []}
OLD_SOURCE = '/Users/m.oluwole/.codex/worktrees/selahcue-provider-qualification/scph/implementation/desktop/crates/'
METADATA_ARGS = ['cargo', 'metadata', '--locked', '--all-features', '--format-version', '1', '--manifest-path', 'Cargo.toml']


class Failure(ValueError):
    """Safe invariant diagnostic, never raw input/environment."""


def require(condition, label):
    if not condition:
        raise Failure(label)


def nofollow(path):
    path = Path(path)
    require(path.is_absolute(), 'absolute path required')
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            require(not p.is_symlink(), 'symlink path')


def regular(path, limit=MAX_SOURCE_BYTES):
    nofollow(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, 'regular bounded file required')
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'file size cap')
    return raw


def write(path, raw):
    nofollow(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def write_json(path, value):
    write(path, (json.dumps(value, sort_keys=True, indent=2)+'\n').encode())


def digest(raw):
    return sha256(raw).hexdigest()


def git_blob(raw):
    return sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def verify_fixture_inputs(data):
    require(set(data) == set(INPUT_PINS), 'exact three fixture inputs')
    for name, (size, hashed) in INPUT_PINS.items():
        require(len(data[name]) == size and digest(data[name]) == hashed, 'frozen fixture '+name)


def inputs(repo):
    data = {name: regular(repo/FIXTURE/name) for name in INPUT_PINS}
    verify_fixture_inputs(data)
    raw = regular(repo/PIN)
    require(digest(raw) == PIN_SHA, 'accepted source-pin identity')
    receipt = json.loads(raw)
    require(receipt['normative_native_commit'] == NORMATIVE, 'normative source revision')
    pins = receipt['file_sha256']
    require(len(pins) == 102 and pins['implementation/desktop/Cargo.lock'] == OWNER_SHA, '102 source pins/owner lock')
    return data, pins


def relocate_manifest(raw):
    require((len(raw), digest(raw)) == INPUT_PINS['Cargo.toml'], 'frozen manifest before relocation')
    text = raw.decode('utf-8')
    for name in ('selahcue-core', 'selahcue-cloud', 'selahcue-scripture'):
        before = 'path = "'+OLD_SOURCE+name+'"'
        require(text.count(before) == 1, 'exact path dependency')
        text = text.replace(before, 'path = "../source/implementation/desktop/crates/'+name+'"')
    require(OLD_SOURCE not in text, 'unexpected absolute dependency')
    return text.encode('utf-8')


def source_inventory(raw):
    require(digest(raw) == SOURCE_TREE, 'complete normative Git tree fingerprint')
    found = {}
    for line in raw.decode().splitlines():
        header, path = line.split('\t'); mode, kind, oid = header.split()
        require(mode in ('100644', '100755') and kind == 'blob', 'regular Git members only')
        rel = PurePosixPath(path)
        require(not rel.is_absolute() and '..' not in rel.parts and str(rel) == path, 'Git path confinement')
        require(path == 'rust-toolchain.toml' or path.startswith('implementation/desktop/'), 'fixed source scope')
        require('.cargo' not in rel.parts and not rel.name.startswith('.env') and rel.name not in ('credentials', 'credentials.toml'), 'no source config/credentials')
        require(path not in found and re.fullmatch('[0-9a-f]{40}', oid), 'unique Git blob')
        found[path] = oid
    require(len(found) == SOURCE_COUNT <= MAX_FILES, 'complete source file count')
    return found


def extract_source(raw, destination, expected):
    require(len(raw) <= MAX_SOURCE_BYTES + 2*1024**2 and len(expected) <= MAX_FILES, 'source archive cap')
    nofollow(destination);require(not destination.exists(), 'exclusive source destination')
    destination.mkdir()
    found, total = set(), 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            rel = PurePosixPath(member.name)
            require(not rel.is_absolute() and '..' not in rel.parts and str(rel) == member.name.rstrip('/'), 'archive path confinement')
            if member.isdir():
                require(any(p.startswith(str(rel)+'/') for p in expected), 'unapproved archive directory')
                continue
            require(member.isfile() and member.name in expected and member.name not in found, 'unique approved regular archive member')
            total += member.size
            require(0 <= member.size <= MAX_SOURCE_BYTES and total <= MAX_SOURCE_BYTES, 'source bytes cap')
            body = archive.extractfile(member).read(member.size+1)
            require(len(body) == member.size and git_blob(body) == expected[member.name], 'Git blob identity')
            write(destination/member.name, body);found.add(member.name)
    require(found == set(expected), 'complete source extraction')
    return total


def command(argv, *, cwd, env, deadline, cap=16*1024**2):
    """Bounded owned process group; metadata and Git only, no build interface."""
    require(time.monotonic() < deadline, 'preparation deadline')
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as error:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=output, stderr=error, start_new_session=True)
        try:
            while process.poll() is None:
                require(time.monotonic() < deadline, 'preparation deadline')
                require(os.fstat(output.fileno()).st_size <= cap and os.fstat(error.fileno()).st_size <= 1024**2, 'command output cap')
                time.sleep(.05)
            require(os.fstat(output.fileno()).st_size <= cap and os.fstat(error.fileno()).st_size <= 1024**2, 'command output cap')
            require(process.returncode == 0, 'command failed: '+Path(argv[0]).name+' exit '+str(process.returncode))
            output.seek(0);return output.read(cap+1)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def metadata_environment(stage, ambient):
    env = {'PATH': ambient.get('PATH', os.defpath), 'HOME': ambient['HOME'],
           'CARGO_HOME': str(stage/'cargo'), 'CARGO_TARGET_DIR': str(stage/'target'),
           'RUSTUP_TOOLCHAIN': '1.98.0', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
    if ambient.get('RUSTUP_HOME'):
        env['RUSTUP_HOME'] = ambient['RUSTUP_HOME']
    return env


def verify_metadata(data, stage, lock):
    locked = tomllib.loads(lock.decode())['package']
    by_identity = {(p['name'], p['version'], p.get('source')): p for p in locked}
    require(len(locked) == len(by_identity) == 60, '60 unique pinned packages')
    expected = {(p['name'], p['version'], p.get('source')) for p in locked}
    packages = data['packages']; nodes = data['resolve']['nodes']
    require(len(packages) == 60 and {(p['name'], p['version'], p['source']) for p in packages} == expected, '56 registry/4 local identities')
    by_id = {p['id']: p for p in packages}; node_map = {n['id']: n for n in nodes}
    require(len(by_id) == len(node_map) == len(nodes) == 60 and set(by_id) == set(node_map), 'complete unique resolution nodes')
    local = {}
    for package in packages:
        name = package['name']; node = node_map[package['id']]
        if package['source'] is None:
            expected_path = (stage/'adapter/Cargo.toml' if name == 'coverage-native-golden'
                             else stage/'source/implementation/desktop/crates'/name/'Cargo.toml')
            require(package['manifest_path'] == str(expected_path), 'local manifest identity')
            local[name] = node['features']
        wanted = set()
        identity = (name, package['version'], package['source'])
        for entry in by_identity[identity].get('dependencies', []):
            parts = entry.split()
            matches = [key for key in by_identity if key[0] == parts[0]
                       and (len(parts) < 2 or key[1] == parts[1])
                       and (len(parts) < 3 or key[2] == parts[2].strip('()'))]
            require(len(matches) == 1, 'unique locked dependency identity')
            wanted.add(matches[0])
        actual = node['dependencies']
        require(len(actual) == len(set(actual)) and all(p in by_id for p in actual), 'unique known graph edges')
        require({(by_id[p]['name'], by_id[p]['version'], by_id[p]['source']) for p in actual} == wanted, 'locked dependency edges')
    require(local == FEATURES, 'four local feature sets')
    root = next(p['id'] for p in packages if p['name'] == 'coverage-native-golden')
    require(data['resolve']['root'] == root and data['workspace_members'] == [root] and data['workspace_root'] == str(stage/'adapter'), 'adapter-only graph root')
    return {'registry_packages': 56, 'local_features': local, 'packages': 60, 'platform_filter': None}


def snapshot(root):
    """Authored inputs and metadata, excluding the mutable public Cargo cache."""
    values = {}
    for child in root.iterdir():
        require(child.name in ('source','adapter','cargo','target','metadata.json','ownership.json','prepared.json'), 'unapproved stage member')
        nofollow(child)
        if child.name in ('cargo','target','prepared.json'):
            continue
        paths = child.rglob('*') if child.is_dir() else [child]
        for path in paths:
            nofollow(path)
            if path.is_dir(): continue
            values[str(path.relative_to(root))] = digest(regular(path))
    return values


class Mirror:
    def __init__(self, repo, temp, binding):
        self.repo, self.temp, self.binding = repo, temp, binding
        nofollow(repo);nofollow(temp)
        require(temp.is_dir() and temp != Path('/') and not temp.is_relative_to(repo), 'external runner temp directory')
        self.root = temp/'selahcue-native-supply'
        self.adapter = self.root/'adapter'

    def initialize(self):
        nofollow(self.root)
        require(not self.root.exists(), 'preexisting audit mirror')
        self.root.mkdir(mode=0o700)
        info = self.root.stat()
        write_json(self.root/'ownership.json', {'binding': self.binding, 'device': info.st_dev,
                                               'inode': info.st_ino, 'uid': info.st_uid})

    def owned(self):
        nofollow(self.root)
        require((self.root/'ownership.json').is_file(), 'missing audit mirror ownership')
        record = json.loads(regular(self.root/'ownership.json', 4096));info=self.root.stat()
        require(record == {'binding': self.binding, 'device': info.st_dev, 'inode': info.st_ino, 'uid': info.st_uid}, 'foreign/replaced audit mirror')

    def canonical_check(self):
        self.owned();data,pins=inputs(self.repo)
        require(regular(self.adapter/'Cargo.lock') == data['Cargo.lock'] and regular(self.adapter/'src/main.rs') == data['src/main.rs'], 'unchanged mirrored lock/adapter')
        require(regular(self.adapter/'Cargo.toml') == relocate_manifest(data['Cargo.toml']), 'only three relocated paths')
        for path, wanted in pins.items():
            require(digest(regular(self.root/'source'/path)) == wanted, 'accepted source hash')
        policy=regular(self.root/'source/implementation/desktop/deny.toml')
        require(digest(policy) == POLICY_SHA and regular(self.adapter/'deny.toml') == policy, 'unchanged desktop deny policy')
        lock = tomllib.loads(data['Cargo.lock'].decode())['package']
        owner=tomllib.loads(regular(self.root/'source/implementation/desktop/Cargo.lock').decode())['package']
        def tuples(packages):
            return {(p['name'],p['version'],p['source'],p['checksum']) for p in packages if p.get('source')}
        require(len(tuples(lock)) == 56 and tuples(lock) <= tuples(owner), 'exact registry tuple subset of owner')

    def prepare(self):
        data,_=inputs(self.repo)  # Authenticate before creating any stage.
        self.initialize(); deadline=time.monotonic()+180
        env=metadata_environment(self.root, os.environ)
        # Neither Cargo nor deny may inherit an ancestor config/exception file.
        for parent in (self.root, *self.root.parents):
            for name in ('.cargo', 'Cargo.toml', 'deny.exceptions.toml', '.deny.exceptions.toml'):
                require(not (parent/name).exists() and not (parent/name).is_symlink(), 'ambient Cargo/deny configuration')
        git_env={'PATH':os.defpath,'HOME':str(self.root),'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull,'GIT_OPTIONAL_LOCKS':'0'}
        command(['git','merge-base','--is-ancestor',NORMATIVE,'HEAD'],cwd=self.repo,env=git_env,deadline=deadline)
        tree=command(['git','ls-tree','-r',NORMATIVE,'--',*SOURCE_SCOPE],cwd=self.repo,env=git_env,deadline=deadline)
        inventory=source_inventory(tree)
        archive=command(['git','-c','core.hooksPath='+os.devnull,'archive','--format=tar',NORMATIVE,'--',*SOURCE_SCOPE],cwd=self.repo,env=git_env,deadline=deadline,cap=MAX_SOURCE_BYTES+2*1024**2)
        require(extract_source(archive,self.root/'source',inventory) == SOURCE_BYTES, 'exact normative source byte count')
        for name, raw in data.items(): write(self.adapter/name, relocate_manifest(raw) if name=='Cargo.toml' else raw)
        write(self.adapter/'deny.toml', regular(self.root/'source/implementation/desktop/deny.toml'))
        (self.root/'cargo').mkdir();(self.root/'target').mkdir()
        self.canonical_check()
        version=command(['cargo-deny','--version'],cwd=self.adapter,env=env,deadline=deadline)
        require(version.strip() == b'cargo-deny 0.20.2', 'installed cargo-deny 0.20.2 required')
        metadata=command(METADATA_ARGS,cwd=self.adapter,env=env,deadline=min(deadline,time.monotonic()+120))
        observation=verify_metadata(json.loads(metadata),self.root,data['Cargo.lock'])
        self.canonical_check()
        write(self.root/'metadata.json',metadata)
        write_json(self.root/'prepared.json', {'binding':self.binding,'files':snapshot(self.root),
                   'source_commit':NORMATIVE,'source_tree':SOURCE_TREE,'source_files':SOURCE_COUNT,
                   'source_bytes':SOURCE_BYTES,'accepted_source_pins':102,'deny_version':version.decode().strip(),
                   'metadata_sha256':digest(metadata),'graph':observation,'native_executed':False})
        return observation

    def postcheck(self):
        self.owned()
        prepared=json.loads(regular(self.root/'prepared.json',1024**2))
        require(prepared['binding'] == self.binding and prepared['files'] == snapshot(self.root), 'post-deny source/lock/policy/metadata drift')
        self.canonical_check()
        return 'unchanged'

    def cleanup(self):
        nofollow(self.root)
        if not self.root.exists(): return 'absent'
        self.owned()
        count=0
        for path in self.root.rglob('*'):
            count+=1;require(count<=50000,'cleanup inventory bound');nofollow(path)
            require(path.is_dir() or stat.S_ISREG(path.lstat().st_mode), 'cleanup regular owned descendants only')
        # shutil.rmtree uses fd-based symlink attack resistance on supported CI Python.
        require(shutil.rmtree.avoids_symlink_attacks, 'safe cleanup unavailable')
        shutil.rmtree(self.root)
        return 'removed'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','postcheck','cleanup'))
    args=parser.parse_args()
    try:
        require(os.environ.get('GITHUB_ACTIONS') == 'true', 'hosted workflow required')
        binding={key:os.environ[value] for key,value in (('run','GITHUB_RUN_ID'),('attempt','GITHUB_RUN_ATTEMPT'),('head','GITHUB_SHA'))}
        require(binding['run'].isdigit() and binding['attempt'].isdigit() and re.fullmatch('[0-9a-f]{40}',binding['head']), 'run identity')
        mirror=Mirror(ROOT,Path(os.environ['RUNNER_TEMP']),binding)
        result=getattr(mirror,args.command)()
        print(json.dumps({'command':args.command,'result':result,'native_executed':False},sort_keys=True))
        return 0
    except (Failure,OSError,ValueError,KeyError,tarfile.TarError) as exc:
        print('native supply check failed: '+(str(exc) if isinstance(exc,Failure) else type(exc).__name__),file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
