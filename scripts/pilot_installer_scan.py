#!/usr/bin/env python3
"""Pilot admission core. No CLI or workflow enablement; actual package evidence is separate.

Only two proven native JSON value spans can carry the intended credentials. All
errors use fixed public codes. Never pass secret bytes to the legacy reporting API.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import functools
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import struct
import tempfile
from typing import Iterator

from installer_secret_scan import CHUNK, ENCODINGS, MIN_ARTEFACT_BYTES, SIGNATURES

MAGIC = b'\x00SCUE-PILOT-PAYLOAD-V1\x00'
TRAILER = b'\x00SCUE-PILOT-END-V1\x00'
MAX_PAYLOAD = 16_384
CUTOFF = 1_809_129_599
ENDPOINTS = frozenset(('api.openai.com', 'api.deepgram.com'))
MAX_IMAGES = 2
MAX_MATCHES = 10_000


class PolicyError(Exception):
    """Fixed public reason only: no parser input, credential, path or context."""


def filesystem_boundary(function):
    """Sanitize filesystem refusals only; programming errors remain visible."""
    if inspect.isgeneratorfunction(function):
        @functools.wraps(function)
        def guarded_iterator(*args, **kwargs):
            try:
                yield from function(*args, **kwargs)
            except OSError:
                raise PolicyError('filesystem-refused') from None
        return guarded_iterator
    @functools.wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except OSError:
            raise PolicyError('filesystem-refused') from None
    return guarded


def source_root(module_file: str) -> Path:
    """Path.resolve's documented loop RuntimeError is confined to this operation."""
    try:
        return Path(module_file).resolve(strict=True).parents[1]
    except (OSError, RuntimeError):
        raise PolicyError('source-root-refused') from None


@dataclass(frozen=True)
class ExpectedPayload:
    raw: bytes = field(repr=False)
    credentials: tuple[bytes, bytes] = field(repr=False)
    spans: tuple[tuple[int, int], tuple[int, int]]


@dataclass(frozen=True)
class BuildEvidence:
    source_sha: str
    ref: str
    event: str
    operator_sha256: str
    architectures: tuple[str, ...]


@dataclass(frozen=True)
class ComponentResult:
    profile: str
    size: int
    sha256: str
    envelopes: int


def _fail(code: str):
    raise PolicyError(code) from None


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            _fail('payload-duplicate-field')
        out[key] = value
    return out


def _fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        _fail('payload-schema')


def admit_payload(raw: bytes, *, cohort: str, openai_model: str, now: int) -> ExpectedPayload:
    """Admit explicit build-owned canonical bytes; never discover inputs or print them."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PAYLOAD:
        _fail('payload-size')
    try:
        obj = json.loads(raw.decode('ascii'), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        _fail('payload-json')
    _fields(obj, ('schema', 'cohort', 'cutoff', 'openai', 'deepgram'))
    if (type(now) is not int or now < 0 or type(obj['schema']) is not int
            or obj['schema'] != 1 or obj['cohort'] != cohort
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', cohort)
            or type(obj['cutoff']) is not int or obj['cutoff'] != CUTOFF):
        _fail('payload-policy')
    keys = []
    spans = []
    for name, model in (('openai', openai_model), ('deepgram', 'nova-3')):
        provider = obj[name]
        _fields(provider, ('key', 'expires_at', 'model'))
        if (not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', model)
                or provider['model'] != model or type(provider['expires_at']) is not int
                or not now < provider['expires_at'] <= CUTOFF):
            _fail('payload-provider-policy')
        key = provider['key']
        # Strict source admission deliberately narrower than runtime graphic ASCII.
        # This excludes JSON escaping and ambiguous byte-span transformations.
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{16,4096}', key):
            _fail('payload-credential-representation')
        value = key.encode('ascii')
        if any(marker.encode() in value or value in marker.encode() for marker, _ in SIGNATURES):
            _fail('payload-credential-collision')
        token = b'"' + value + b'"'
        if raw.count(token) != 1:
            _fail('payload-credential-ambiguity')
        start = raw.index(token) + 1
        spans.append((start, start + len(value)))
        keys.append(value)
    if keys[0] in keys[1] or keys[1] in keys[0]:
        _fail('payload-credential-collision')
    canonical = json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    if raw != canonical:
        _fail('payload-not-canonical')
    return ExpectedPayload(raw, tuple(keys), tuple(spans))


def frame_payload(raw: bytes) -> bytes:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PAYLOAD:
        _fail('payload-size')
    return MAGIC + struct.pack('<I', len(raw)) + raw + TRAILER


@filesystem_boundary
def file_digest(path: Path) -> tuple[int, str]:
    size = 0
    digest = hashlib.sha256()
    try:
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(CHUNK), b''):
                size += len(block)
                digest.update(block)
    except OSError:
        _fail('component-unreadable')
    return size, digest.hexdigest()


@filesystem_boundary
def occurrences(path: Path, needles: tuple[bytes, ...], *, chunk_size: int = CHUNK) -> Iterator[tuple[int, int]]:
    """Every overlapping occurrence, once, including chunk boundaries; bounded memory."""
    if not needles or any(not isinstance(n, bytes) or not n for n in needles) or type(chunk_size) is not int or not 1 <= chunk_size <= CHUNK:
        _fail('matcher-input')
    overlap = max(map(len, needles)) - 1
    if overlap > MAX_PAYLOAD * 4:
        _fail('matcher-needle-bound')
    tail = b''
    consumed = 0
    count = 0
    try:
        with path.open('rb') as stream:
            while True:
                block = stream.read(chunk_size)
                if not block:
                    break
                window = tail + block
                base = consumed - len(tail)
                for index, needle in enumerate(needles):
                    start = 0
                    while True:
                        position = window.find(needle, start)
                        if position < 0:
                            break
                        absolute = base + position
                        if absolute + len(needle) > consumed:
                            count += 1
                            if count > MAX_MATCHES:
                                _fail('matcher-hit-bound')
                            yield index, absolute
                        start = position + 1
                consumed += len(block)
                tail = window[-overlap:] if overlap else b''
    except OSError:
        _fail('component-unreadable')


@filesystem_boundary
def _read(path: Path, offset: int, size: int, limit: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > limit or size > MAX_PAYLOAD * 8:
        _fail('native-bounds')
    try:
        with path.open('rb') as stream:
            stream.seek(offset)
            value = stream.read(size)
    except OSError:
        _fail('component-unreadable')
    if len(value) != size:
        _fail('native-truncated')
    return value


def _thin_image(path: Path, start: int, size: int, file_size: int) -> str:
    """Validate executable native headers and all declared loader file ranges."""
    end = start + size
    head = _read(path, start, min(size, 64), file_size)
    if len(head) < 32:
        _fail('native-truncated')
    if head[:4] == b'\x7fELF':
        if len(head) < 64 or head[4:7] != b'\x02\x01\x01':
            _fail('native-elf')
        values = struct.unpack('<16sHHIQQQIHHHHHH', head)
        _, kind, machine, version, _, phoff, _, _, ehsize, phsize, phcount, _, _, _ = values
        if kind not in (2, 3) or machine != 62 or version != 1 or ehsize != 64 or phsize != 56 or not 0 < phcount <= 256:
            _fail('native-elf')
        ph = _read(path, start + phoff, phsize * phcount, end)
        loads = 0
        for index in range(phcount):
            row = struct.unpack_from('<IIQQQQQQ', ph, index * phsize)
            if row[0] == 1:
                if row[2] + row[5] > size or row[5] > row[6]:
                    _fail('native-bounds')
                loads += 1
        if not loads:
            _fail('native-elf')
        return 'x86_64'
    if head[:2] == b'MZ':
        if len(head) < 64:
            _fail('native-truncated')
        peoff = struct.unpack_from('<I', head, 60)[0]
        pe = _read(path, start + peoff, 24, end)
        if pe[:4] != b'PE\x00\x00':
            _fail('native-pe')
        machine, sections, _, _, _, optional_size, flags = struct.unpack_from('<HHIIIHH', pe, 4)
        if machine != 0x8664 or not 0 < sections <= 96 or optional_size < 112 or not flags & 2:
            _fail('native-pe')
        optional = _read(path, start + peoff + 24, optional_size, end)
        if optional[:2] != b'\x0b\x02':
            _fail('native-pe')
        rows = _read(path, start + peoff + 24 + optional_size, sections * 40, end)
        for index in range(sections):
            row = rows[index*40:(index+1)*40]
            raw_size, raw_offset = struct.unpack_from('<II', row, 16)
            if raw_offset + raw_size > size:
                _fail('native-bounds')
        return 'x86_64'
    if head[:4] == b'\xcf\xfa\xed\xfe':
        _, cpu, _, kind, count, command_bytes, _, _ = struct.unpack('<8I', head[:32])
        if cpu not in (0x01000007, 0x0100000C) or kind != 2 or not 0 < count <= 256 or command_bytes > MAX_PAYLOAD * 4:
            _fail('native-macho')
        commands = _read(path, start + 32, command_bytes, end)
        offset = 0
        segments = 0
        for _ in range(count):
            if offset + 8 > len(commands):
                _fail('native-macho')
            command, length = struct.unpack_from('<II', commands, offset)
            if length < 8 or offset + length > len(commands):
                _fail('native-macho')
            if command == 0x19:
                if length < 72:
                    _fail('native-macho')
                file_offset, file_bytes = struct.unpack_from('<QQ', commands, offset + 40)
                if file_offset + file_bytes > size:
                    _fail('native-bounds')
                segments += 1
            offset += length
        if offset != len(commands) or not segments:
            _fail('native-macho')
        return 'arm64' if cpu == 0x0100000C else 'x86_64'
    _fail('native-format')


@filesystem_boundary
def native_images(path: Path, expected_architectures: tuple[str, ...]) -> tuple[tuple[int, int, str], ...]:
    size = file_digest(path)[0]
    head = _read(path, 0, min(size, 8), size)
    images = []
    if head[:4] == b'\xca\xfe\xba\xbe':
        if len(head) < 8:
            _fail('native-truncated')
        count = struct.unpack_from('>I', head, 4)[0]
        if count != 2:
            _fail('native-fat-count')
        rows = _read(path, 8, count * 20, size)
        bounds = []
        for index in range(count):
            cpu, _, offset, length, alignment = struct.unpack_from('>5I', rows, index * 20)
            if cpu not in (0x01000007, 0x0100000C) or alignment > 30 or offset < 8+count*20 or offset % (1 << alignment) or not length or offset + length > size:
                _fail('native-fat-bounds')
            if any(offset < other_end and other_start < offset + length for other_start, other_end in bounds):
                _fail('native-fat-overlap')
            bounds.append((offset, offset + length))
            architecture = _thin_image(path, offset, length, size)
            if architecture != ('arm64' if cpu == 0x0100000C else 'x86_64'):
                _fail('native-fat-architecture')
            images.append((offset, offset + length, architecture))
    else:
        images.append((0, size, _thin_image(path, 0, size, size)))
    if len(images) > MAX_IMAGES or tuple(sorted(row[2] for row in images)) != tuple(sorted(expected_architectures)) or len(set(row[2] for row in images)) != len(images):
        _fail('native-architecture')
    return tuple(images)


@filesystem_boundary
def _envelopes(path: Path, images, expected: ExpectedPayload):
    size = file_digest(path)[0]
    spans = []
    counts = [0] * len(images)
    for _, offset in occurrences(path, (MAGIC,)):
        start = offset + len(MAGIC)
        if start + 4 > size:
            continue  # Runtime may retain a standalone public magic constant.
        length = struct.unpack('<I', _read(path, start, 4, size))[0]
        body = start + 4
        # Complete framing is a candidate even when its body is not an object.
        # Validation code may retain standalone MAGIC, without length/body/trailer.
        end = body + length + len(TRAILER)
        complete = end <= size and _read(path, body + length, len(TRAILER), size) == TRAILER
        object_start = body < size and _read(path, body, 1, size) == b'{'
        if not complete and not object_start:
            continue
        if not 0 < length <= MAX_PAYLOAD or not complete:
            _fail('envelope-malformed')
        raw = _read(path, body, length, size)
        owner = [index for index, (left, right, _) in enumerate(images) if left <= offset and body + length + len(TRAILER) <= right]
        if len(owner) != 1 or raw != expected.raw:
            _fail('envelope-binding')
        counts[owner[0]] += 1
        for index, (left, right) in enumerate(expected.spans):
            spans.append((index, body + left, body + right))
    if any(count != 1 for count in counts):
        _fail('envelope-count')
    return spans, len(images)


def _representations(value: bytes) -> tuple[bytes, ...]:
    return tuple(dict.fromkeys((value, value.decode('ascii').encode('utf-16-le'),
                               base64.b64encode(value), value.hex().encode('ascii'))))


@filesystem_boundary
def _scan_component(path: Path, *, minimum: int, profile: str = 'ordinary', operator: bool = False,
                   expected: ExpectedPayload | None = None, evidence: BuildEvidence | None = None,
                   expected_source_sha: str | None = None, known_secrets: tuple[bytes, ...] = ()) -> ComponentResult:
    """Read-only core. Caller must bind actual fresh package extraction and build provenance.

    This function is not an installer acceptance receipt or P01 issuer verification.
    """
    if profile not in ('ordinary', 'pilot') or path.is_symlink() or not path.is_file():
        _fail('component-policy')
    before = file_digest(path)
    if before[0] < minimum:
        _fail('component-size')
    allowed = []
    count = 0
    if profile == 'pilot' and operator:
        if (expected is None or evidence is None or expected_source_sha is None
                or not re.fullmatch(r'[0-9a-f]{40}', expected_source_sha)
                or evidence.source_sha != expected_source_sha or evidence.ref != 'refs/heads/main'
                or evidence.event != 'workflow_dispatch' or evidence.operator_sha256 != before[1]):
            _fail('provenance')
        images = native_images(path, evidence.architectures)
        allowed, count = _envelopes(path, images, expected)
    elif next(occurrences(path, (MAGIC, MAGIC.decode('ascii').encode('utf-16-le'))), None) is not None:
        _fail('pilot-in-ordinary' if profile == 'ordinary' else 'pilot-in-other-component')
    markers = tuple(marker.encode(encoding) for marker, _ in SIGNATURES
                    if not (profile == 'pilot' and operator and marker in ENDPOINTS)
                    for encoding in ENCODINGS)
    if next(occurrences(path, markers), None) is not None:
        _fail('forbidden-marker')
    if expected:
        for index, credential in enumerate(expected.credentials):
            representations = _representations(credential)
            for encoding, offset in occurrences(path, representations):
                if not (encoding == 0 and any(owner == index and left == offset and right == offset + len(credential)
                                               for owner, left, right in allowed)):
                    _fail('credential-outside-designation')
    inventory = development_inventory(source_root(__file__))
    if len(known_secrets) > 256:
        _fail('known-secret-inventory')
    probes = known_secret_probes(known_secrets + inventory)
    if next(occurrences(path, probes), None) is not None:
        _fail('known-secret')
    _positive_control(path, expected, known_secrets + inventory)
    if file_digest(path) != before:
        _fail('component-changed')
    return ComponentResult(profile, before[0], before[1], count)


@filesystem_boundary
def verify_inventory(root: Path, expected: dict[str, str], *, max_files: int = 1024,
                     max_bytes: int = 2 * 1024**3, max_depth: int = 16,
                     timeout: float = 30) -> tuple[str, ...]:
    """Closed read-only unpacked inventory, not proof of fresh/authoritative extraction.

    A platform admission driver must perform the actual bounded extraction itself
    and bind its input installer digest. A caller-provided old directory is insufficient.
    """
    if (root.is_symlink() or not root.is_dir() or not isinstance(expected, dict)
            or not expected or not 0 < len(expected) <= max_files <= 1024
            or not 0 < max_bytes <= 2 * 1024**3 or not 0 < max_depth <= 16
            or not 0 < timeout <= 30):
        _fail('package-policy')
    for name, digest in expected.items():
        if (not isinstance(name, str) or not name or '\\' in name or ':' in name
                or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts
                or PurePosixPath(name).as_posix() != name or len(PurePosixPath(name).parts) > max_depth
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            _fail('package-policy')
    deadline = time.monotonic() + timeout
    files = []
    total = 0
    def members(directory):
        # pathlib.rglob can suppress subtree PermissionError, hiding extra members.
        # Stream depth-first without buffering a directory and propagate every error.
        if time.monotonic() > deadline:
            _fail('package-time-bound')
        with os.scandir(directory) as entries:
            for entry in entries:
                member = Path(entry.path)
                yield member
                # The caller rejects symlinks/depth before advancing this generator.
                if entry.is_dir(follow_symlinks=False):
                    yield from members(member)
    try:
        for member in members(root):
            if time.monotonic() > deadline:
                _fail('package-time-bound')
            mode = member.lstat()
            if stat.S_ISLNK(mode.st_mode) or len(member.relative_to(root).parts) > max_depth:
                _fail('package-unsafe-member')
            if stat.S_ISDIR(mode.st_mode):
                continue
            if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
                _fail('package-unsafe-member')
            name = member.relative_to(root).as_posix()
            files.append(name)
            total += mode.st_size
            if len(files) > max_files or total > max_bytes:
                _fail('package-expansion-bound')
            if name not in expected:
                _fail('package-inventory')
            digest = hashlib.sha256()
            with member.open('rb') as stream:
                for block in iter(lambda: stream.read(CHUNK), b''):
                    if time.monotonic() > deadline:
                        _fail('package-time-bound')
                    digest.update(block)
            if digest.hexdigest() != expected[name]:
                _fail('package-hash')
            after = member.lstat()
            if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (mode.st_dev, mode.st_ino, mode.st_size, mode.st_mtime_ns):
                _fail('package-changed')
    except OSError:
        _fail('package-unreadable')
    if set(files) != set(expected):
        _fail('package-inventory')
    return tuple(sorted(files))


@filesystem_boundary
def development_inventory(root: Path) -> tuple[bytes, ...]:
    """Read only two exact committed, explicitly public development fixtures.

    No environment, keychain, arbitrary file glob or production signing key access.
    An unreadable/changed source format is a hard failure, never an empty inventory.
    """
    directory = root / 'implementation/desktop/crates/selahcue-licensing'
    try:
        seed_path = directory / 'dev-signing-key.NOT-A-SECRET'
        trust_path = directory / 'src/trust.rs'
        if seed_path.is_symlink() or trust_path.is_symlink() or seed_path.stat().st_size > 65536 or trust_path.stat().st_size > 65536:
            _fail('development-inventory')
        document = seed_path.read_text(encoding='utf-8')
        source = trust_path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        _fail('development-inventory')
    if 'DELIBERATELY PUBLIC, NEVER PRODUCTION' not in document:
        _fail('development-inventory')
    seed_match = re.search(r'^Ed25519 seed \(32 bytes, ASCII\):[ \t]+([^\r\n]+)$', document, re.M)
    public_match = re.search(r'const DEV_PUBLIC_KEY:\s*\[u8;\s*PUBLIC_KEY_BYTES\]\s*=\s*\[([0-9,\s]+)\];', source)
    documented = re.search(r'Public key  \(32 bytes, decimal\):\s*([0-9,\s]+)\nkey_id', document)
    if not seed_match or not public_match or not documented:
        _fail('development-inventory')
    try:
        seed = seed_match.group(1).encode('ascii')
        values = tuple(int(value) for value in re.findall(r'\d+', public_match.group(1)))
        reference = tuple(int(value) for value in re.findall(r'\d+', documented.group(1)))
        public = bytes(values)
    except (ValueError, UnicodeError):
        _fail('development-inventory')
    if len(seed) != 32 or len(public) != 32 or values != reference:
        _fail('development-inventory')
    return seed, public


@filesystem_boundary
def _positive_control(path: Path, expected: ExpectedPayload | None,
                      inventory: tuple[bytes, ...]) -> None:
    """Seed a private COPY from this artifact; no control bytes reach diagnostics."""
    probes = [marker.encode(encoding) for marker, _ in SIGNATURES for encoding in ENCODINGS]
    probes.append(MAGIC)
    if expected:
        for credential in expected.credentials:
            probes.extend(_representations(credential))
    for value in inventory:
        probes.extend((value, base64.b64encode(value), value.hex().encode()))
        try:
            probes.append(value.decode('ascii').encode('utf-16-le'))
        except UnicodeError:
            pass
    unique = tuple(dict.fromkeys(probes))
    try:
        with tempfile.TemporaryDirectory(prefix='selahcue-pilot-scan-control-') as directory:
            fixture = Path(directory) / 'control.bin'
            with path.open('rb') as source, fixture.open('wb') as target:
                target.write(source.read(1 << 20))
                for needle in unique:
                    target.write(bytes(32))
                    target.write(needle)
            found = {index for index, _ in occurrences(fixture, unique)}
            if found != set(range(len(unique))):
                _fail('positive-control')
    except OSError:
        _fail('positive-control-unreadable')


@filesystem_boundary
def scan_component(path: Path, *, profile: str = 'ordinary', operator: bool = False,
                   expected: ExpectedPayload | None = None, evidence: BuildEvidence | None = None,
                   expected_source_sha: str | None = None, known_secrets: tuple[bytes, ...] = ()) -> ComponentResult:
    """Native/installer target scan retaining the original real-artifact size floor."""
    return _scan_component(path, minimum=MIN_ARTEFACT_BYTES, profile=profile, operator=operator,
                           expected=expected, evidence=evidence, expected_source_sha=expected_source_sha,
                           known_secrets=known_secrets)


@filesystem_boundary
def scan_resource(path: Path, *, profile: str = 'ordinary', expected: ExpectedPayload | None = None,
                  known_secrets: tuple[bytes, ...] = ()) -> ComponentResult:
    """Deny-only scan for every closed-inventory resource; never grants a native exception.

    Package adapters must identify required real binary targets separately. This
    cannot serve as the operator/sidecar/installer acceptance scan.
    """
    return _scan_component(path, minimum=0, profile=profile, expected=expected,
                           known_secrets=known_secrets)


def known_secret_probes(inventory: tuple[bytes, ...]) -> tuple[bytes, ...]:
    """Validate/cap then deduplicate deny-only representations for one read pass."""
    if not 0 < len(inventory) <= 258:
        _fail('known-secret-inventory')
    probes = []
    for value in inventory:
        if not isinstance(value, bytes) or not 8 <= len(value) <= 4096:
            _fail('known-secret-inventory')
        probes.extend((value, base64.b64encode(value), value.hex().encode('ascii')))
        try:
            probes.append(value.decode('ascii').encode('utf-16-le'))
        except UnicodeError:
            pass
    return tuple(dict.fromkeys(probes))
