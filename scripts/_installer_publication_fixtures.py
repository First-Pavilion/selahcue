"""Synthetic installer evidence for isolated tests. No output is releasable."""

import hashlib
import json
import subprocess
from pathlib import Path

ARTIFACTS = {
    "windows": ("Operator Setup.exe", ["x64"], ["x86_64-pc-windows-msvc"]),
    "universalMac": ("Operator (Universal).dmg", ["arm64", "x64"],
                     ["aarch64-apple-darwin", "x86_64-apple-darwin"]),
    "ubuntu": ("operator+64.deb", ["x64"], ["x86_64-unknown-linux-gnu"]),
}
GATES = (
    "reviewed-source-profile", "build-artifact-custody", "windows-native",
    "macos-arm64-native", "macos-x64-native", "ubuntu-24.04-native",
    "package-secret-controls", "entitlement-key-enforcement", "cloud-transcription",
    "cloud-notes", "quota-provider-reconciliation", "presentation-offline-degradation",
)
VERSION = "1.2.3-rc.1+synthetic"
REPOSITORY = "First-Pavilion/selahcue"
VERSION_PATH = "implementation/desktop/crates/selahcue-operator/tauri.conf.json"
TRUST_PATH = "implementation/desktop/crates/selahcue-licensing/src/trust.rs"
WORKFLOW_PATH = ".github/workflows/windows-installer.yml"
PUBLIC_KEY = bytes(range(32))


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ReleaseFixture:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.original = self.directory / "original"
        self.input_path = self.original / "release.json"
        self.source_tree = self.directory / "source"
        self.output = self.directory / "release"
        self.original.mkdir()
        self.source_tree.mkdir()
        self.git("init", "--quiet")
        self.git("remote", "add", "origin", "git@github.com:First-Pavilion/selahcue.git")
        self.source(VERSION_PATH, json.dumps({"version": VERSION}).encode())
        self.source(TRUST_PATH, (
            "pub const PUBLIC_KEY_BYTES: usize = 32;\nconst PILOT_PUBLIC_KEY: [u8; PUBLIC_KEY_BYTES] = ["
            + ", ".join(f"0x{byte:02x}" for byte in PUBLIC_KEY) + ",];\n"
        ).encode())
        self.source(WORKFLOW_PATH, b"name: synthetic fixture workflow\n")
        self.commit = self.commit_source()
        self.data = {
            "schema_version": 1, "release_id": "synthetic-release", "version": VERSION,
            "source_commit": self.commit, "artifacts": [],
        }
        self.profile = self.make_profile()
        self.profile_digest = self.record("fixture-profile.json", self.profile)["sha256"]
        self.builds = {}
        self.inspections = {}
        self.inspection_versions = {}
        for artifact_id, (filename, architectures, _) in ARTIFACTS.items():
            raw = f"Synthetic fixture placeholder: {artifact_id}\n".encode()
            path = f"packages/{filename}"
            self.write(path, raw)
            artifact = {
                "id": artifact_id, "path": path, "filename": filename,
                "size_bytes": len(raw), "sha256": digest(raw),
            }
            custody = self.leaf(f"{artifact_id}-custody")
            build = {
                "schema_version": 1, "artifact_id": artifact_id, "source_commit": self.commit,
                "version": VERSION, "profile_sha256": self.profile_digest, "repository": REPOSITORY,
                "toolchain": self.leaf(f"{artifact_id}-toolchain"),
                "build_commands": [{"cwd": ".", "argv": ["never-execute-fixture-command"]}],
                "build_log": self.leaf(f"{artifact_id}-build-log"), "build_input_custody": custody,
                "package_metadata": self.leaf(f"{artifact_id}-package-metadata"),
                "filename": filename, "size_bytes": len(raw), "sha256": digest(raw),
            }
            if artifact_id == "windows":
                build.update(kind="ci", workflow_path=WORKFLOW_PATH, run_id=123,
                             run_attempt=1, artifact_id_in_ci="synthetic-ci-artifact",
                             workflow_sha256=digest(b"name: synthetic fixture workflow\n"))
            else:
                build.update(kind="local", build_id=f"synthetic-{artifact_id}",
                             operator="Synthetic operator", host_os=artifact_id,
                             host_arch="arm64" if artifact_id == "universalMac" else "x64")
            mac = artifact_id == "universalMac"
            inspection = {
                "schema_version": 1, "artifact_id": artifact_id, "package_sha256": digest(raw),
                "architectures": architectures.copy(), "app_signature": "ad_hoc" if mac else "unsigned",
                "package_signature": "unsigned", "notarization": "not_notarized" if mac else "not_applicable",
                "publisher": None, "build_input_custody": custody,
            }
            for field in (
                "architecture_evidence", "signature_evidence", "bundle_scan",
                "payload_scan", "development_key_scan", "scan_positive_controls",
            ):
                inspection[field] = self.leaf(f"{artifact_id}-{field}")
            self.inspection_versions[artifact_id] = {
                "schema_version": 1, "artifact_id": artifact_id, "package_sha256": digest(raw),
                "version": VERSION, "entitlement_key_id": digest(PUBLIC_KEY)[:8],
                "entitlement_public_key_sha256": digest(PUBLIC_KEY),
                "evidence": self.leaf(f"{artifact_id}-version-output"),
            }
            self.builds[artifact_id] = build
            self.inspections[artifact_id] = inspection
            self.data["artifacts"].append(artifact)
        self.acceptance = {
            "schema_version": 1, "source_commit": self.commit, "version": VERSION,
            "profile_sha256": self.profile_digest, "reviewer": "Synthetic reviewer",
            "reviewed_at": "2026-11-15T10:00:00Z", "decision": "accepted_for_publication",
            "artifacts": [{"id": row["id"], "sha256": row["sha256"]} for row in self.data["artifacts"]],
            "gates": [{"id": gate, "evidence": self.leaf(gate)} for gate in GATES],
        }
        self.save()

    def make_profile(self) -> dict:
        version, trust, workflow = (
            {
                "source_path": path,
                "evidence": self.raw_evidence(f"evidence/{name}", (self.source_tree / path).read_bytes()),
            }
            for path, name in ((VERSION_PATH, "tauri.json"), (TRUST_PATH, "trust.rs"), (WORKFLOW_PATH, "ci.yml"))
        )
        self.source_evidence = {
            "schema_version": 1, "version_config": version, "public_key_config": trust,
            "public_key_symbol": "PILOT_PUBLIC_KEY", "public_key": self.raw_evidence("evidence/key.bin", PUBLIC_KEY),
            "build_inputs": [version, trust, workflow],
        }
        return {
            "schema_version": 1, "source_commit": self.commit, "version": VERSION,
            "api_origin": "https://api.selahcueapp.com",
            "entitlement_key_id": digest(PUBLIC_KEY)[:8], "entitlement_public_key_sha256": digest(PUBLIC_KEY),
            "source_evidence": self.record("fixture-source.json", self.source_evidence),
            "builds": [
                {
                    "id": artifact_id, "target_triples": triples.copy(),
                    "command_argv": ["never-execute-fixture-command"], "default_features": False,
                    "selected_features": ["synthetic-feature"],
                    "resolved_features": self.leaf(f"{artifact_id}-features"),
                    "release_boundary_check": self.leaf(f"{artifact_id}-boundary"),
                }
                for artifact_id, (_, _, triples) in ARTIFACTS.items()
            ],
        }

    def git(self, *argv: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.source_tree), *argv], stderr=subprocess.PIPE, text=True,
        ).strip()

    def commit_source(self) -> str:
        self.git("add", "implementation", ".github")
        self.git("-c", "user.name=Synthetic", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Synthetic source")
        return self.git("rev-parse", "HEAD")

    def source(self, path: str, raw: bytes) -> None:
        destination = self.source_tree / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)

    def write(self, path: str, raw: bytes) -> Path:
        destination = self.original / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        return destination

    def leaf(self, name: str) -> dict:
        path = f"evidence/{name}.txt"
        raw = f"Synthetic fixture output: {name}\n".encode()
        return self.raw_evidence(path, raw)

    def raw_evidence(self, path: str, raw: bytes) -> dict:
        self.write(path, raw)
        return {"path": path, "sha256": digest(raw)}

    def record(self, path: str, value: dict) -> dict:
        raw = (json.dumps(value, indent=2) + "\n").encode()
        return self.raw_evidence(path, raw)

    def save(self) -> Path:
        self.profile["source_evidence"] = self.record("fixture-source.json", self.source_evidence)
        self.data["profile"] = self.record("fixture-profile.json", self.profile)
        self.acceptance["profile_sha256"] = self.data["profile"]["sha256"]
        self.data["acceptance"] = self.record("fixture-acceptance.json", self.acceptance)
        for artifact in self.data["artifacts"]:
            artifact_id = artifact["id"]
            self.builds[artifact_id]["profile_sha256"] = self.data["profile"]["sha256"]
            artifact["build"] = self.record(f"{artifact_id}-build.json", self.builds[artifact_id])
            self.inspections[artifact_id]["version_evidence"] = self.record(
                f"{artifact_id}-version.json", self.inspection_versions[artifact_id],
            )
            artifact["inspection"] = self.record(f"{artifact_id}-inspection.json", self.inspections[artifact_id])
        self.record(self.input_path.name, self.data)
        return self.input_path


def completed_receipts(plan: dict) -> tuple[dict, dict]:
    """Synthetic successful observations; callers can mutate individual fields."""
    started = "2026-11-15T10:00:00Z"
    completed = "2026-11-15T10:01:00Z"
    finished = "2026-11-15T10:02:00Z"
    verified = []
    uploaded = []
    for obj in plan["objects"]:
        headers = {field: obj[field] for field in ("content_type", "content_disposition", "cache_control")}
        headers.update(content_length=obj["size_bytes"], content_encoding=None)
        observation = {
            "id": obj["id"], "url": obj["url"], "http_status": 200, "headers": headers,
            "observed_size_bytes": obj["size_bytes"], "observed_sha256": obj["sha256"], "completed_at": completed,
        }
        verified.append(observation)
        uploaded.append({
            "id": obj["id"], "key": obj["key"], "size_bytes": obj["size_bytes"], "sha256": obj["sha256"],
            "put_outcome": "unknown_but_verified", "head": {**headers, "request_id": None},
            "acl": {"owner_id": "synthetic-owner", "grants": [
                {"grantee_type": "CanonicalUser", "grantee_id": "synthetic-owner", "permission": "FULL_CONTROL"},
                {"grantee_type": "Group", "grantee_id": "http://acs.amazonaws.com/groups/global/AllUsers",
                 "permission": "READ"},
            ]},
            "anonymous_readback": observation,
        })
    common = {
        "schema_version": 1, "plan_sha256": digest((json.dumps(plan, separators=(",", ":"), sort_keys=True) + "\n").encode()),
        "started_at": started, "finished_at": finished,
    }
    return (
        {**common, "verifier_version": "synthetic-verifier", "objects": verified},
        {**common, "input_sha256": "1" * 64, "prepare_receipt_sha256": "2" * 64,
         "tool_version": "synthetic-aws-cli", "objects": uploaded},
    )


def fake_aws_executable(directory: Path):
    """Stateful subprocess fixture. Only temporary synthetic state is reachable."""
    import sys
    state = directory / 'fake-aws-state.json'
    state.write_text(json.dumps({'objects': {}, 'calls': [], 'puts': [], 'mode': ''}))
    executable = directory / 'aws'
    executable.write_text('#!' + sys.executable + '\n' + 'STATE = ' + repr(str(state)) + '\n' + r'''
import hashlib, json, os, sys, time
from pathlib import Path
path = Path(STATE)
s = json.loads(path.read_text())
args = sys.argv[1:]
s['calls'].append({'argv': args, 'env': dict(os.environ)})
def save(): path.write_text(json.dumps(s))
def output(value): save(); print(json.dumps(value)); raise SystemExit(0)
def error(code, operation):
    save()
    print(f'\nAn error occurred ({code}) when calling the {operation} operation: synthetic service detail', file=sys.stderr)
    raise SystemExit(254)
if args == ['--version']:
    save(); print('aws-cli/2.31.0 Python/3.13 synthetic/test'); raise SystemExit(0)
if '--generate-cli-skeleton' in args:
    keys = ['ACL','Bucket','Key','Body','ContentLength','IfNoneMatch','ContentType','ContentDisposition','CacheControl']
    if s['mode'] == 'old-model': keys.remove('IfNoneMatch')
    output(dict.fromkeys(keys, ''))
assert args[:1] == ['s3api']
op = args[1]
assert op in ('head-object','get-object-acl','put-object'), args
options = {}
i = 2
while i < len(args):
    name = args[i]
    if name == '--no-cli-pager': i += 1; continue
    options[name] = args[i+1]; i += 2
assert options['--bucket'] == 'selahcue-installers'
assert options['--endpoint-url'] == 'https://sfo3.digitaloceanspaces.com'
assert options['--region'] == 'sfo3'
assert options['--cli-connect-timeout'] == '30' and options['--cli-read-timeout'] == '120'
assert options['--output'] == 'json'
assert '--debug' not in args and '--no-verify-ssl' not in args
assert os.environ['AWS_MAX_ATTEMPTS'] == '1'
assert Path(os.environ['AWS_CONFIG_FILE']).read_bytes() == b''
assert Path(os.environ['AWS_SHARED_CREDENTIALS_FILE']).read_bytes() == b''
key = options['--key']
assert key.startswith('installers/1.2.3-rc.1+synthetic/')
obj = s['objects'].get(key)
if s['mode'] == 'flood':
    save(); sys.stdout.write('x' * (1024*1024+1)); sys.stdout.flush(); time.sleep(5)
if s['mode'] == 'stderr-flood':
    save(); sys.stderr.write('s' * 4097); sys.stderr.flush(); time.sleep(5)
if s['mode'] == 'hang': save(); time.sleep(5)
if s['mode'] == 'malformed': save(); print('{bad'); raise SystemExit(0)
if op == 'head-object':
    if s['mode'] == 'denied': error('403', 'HeadObject')
    if s['mode'] == 'unrecognized': error('Unexpected', 'HeadObject')
    if s['mode'] == 'probe-unknown' and s['puts']: error('503','HeadObject')
    if obj is None: error('404', 'HeadObject')
    result = dict(obj['head'])
    if s['mode'] == 'metadata': result['Metadata'] = {'sha256': obj['sha256']}
    if s['mode'] == 'wrong-header': result['CacheControl'] = 'private'
    output(result)
if op == 'get-object-acl':
    if obj is None: error('NoSuchKey','GetObjectAcl')
    result = {'Owner': {'ID':'fixture-owner'}, 'Grants': [
       {'Grantee': {'Type':'CanonicalUser','ID':'fixture-owner'},'Permission':'FULL_CONTROL'},
       {'Grantee': {'Type':'Group','URI':'http://acs.amazonaws.com/groups/global/AllUsers'},'Permission':'READ'}]}
    if s['mode'] == 'private': result['Grants'].pop()
    if s['mode'] == 'public-write': result['Grants'][1]['Permission'] = 'WRITE'
    output(result)
assert options['--if-none-match'] == '*' and options['--acl'] == 'public-read'
assert set(options) == {'--bucket','--key','--endpoint-url','--region','--output','--cli-connect-timeout',
    '--cli-read-timeout','--body','--content-length','--if-none-match','--acl','--content-type',
    '--content-disposition','--cache-control'}
body = Path(options['--body']).read_bytes()
assert len(body) == int(options['--content-length'])
assert hashlib.sha256(body).hexdigest() == key.split('/')[2]
s['puts'].append(key)
mode = s['mode']
if obj is not None: error('PreconditionFailed','PutObject')
if mode == 'conflict-before': error('ConditionalRequestConflict','PutObject')
if mode in ('unknown-before','probe-unknown'): error('503','PutObject')
s['objects'][key] = {'body':body.hex(), 'sha256':hashlib.sha256(body).hexdigest(), 'head':{
   'ContentLength':len(body), 'ContentType':options['--content-type'],
   'ContentDisposition':options['--content-disposition'], 'CacheControl':options['--cache-control'], 'Metadata':{}}}
if mode == 'lost': error('500','PutObject')
if mode == 'race': error('PreconditionFailed','PutObject')
output({'ETag':'"synthetic-not-a-content-proof"'})
''')
    executable.chmod(0o700)
    return executable, state
