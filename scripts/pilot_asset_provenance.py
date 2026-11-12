"""Declared asset helper layer; not an authenticated build or extraction receipt.

Public help labels are not credential bytes. The legacy raw marker gate is untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from pilot_installer_scan import (MAGIC, PolicyError, development_inventory, file_digest,
                                  occurrences, verify_inventory, _positive_control, known_secret_probes, filesystem_boundary, source_root)


@dataclass(frozen=True)
class AssetSnapshot:
    root: Path = field(repr=False)
    inventory: tuple[tuple[str, str], ...] = field(repr=False)


@dataclass(frozen=True)
class FreshOutput:
    root: Path = field(repr=False)
    identity: tuple[int, int] = field(repr=False)


@dataclass(frozen=True)
class AssetChain:
    coverage: str = 'synthetic-helper-chain-only'
    actual_build_verified: bool = False
    actual_extraction_verified: bool = False


@filesystem_boundary
def scan_asset(path: Path, known_secrets: tuple[bytes, ...] = ()) -> None:
    if len(known_secrets) > 256:
        raise PolicyError('asset-secret-inventory') from None
    inventory = known_secrets + development_inventory(source_root(__file__))
    before = file_digest(path)
    if next(occurrences(path, (MAGIC, MAGIC.decode('ascii').encode('utf-16-le'))), None) is not None:
        raise PolicyError('asset-pilot-envelope') from None
    probes = known_secret_probes(inventory)
    if next(occurrences(path, probes), None) is not None:
        raise PolicyError('asset-known-secret') from None
    _positive_control(path, None, inventory)
    if file_digest(path) != before:
        raise PolicyError('asset-changed') from None


@filesystem_boundary
def capture_assets(root: Path, expected: dict[str, str], *, known_secrets: tuple[bytes, ...] = ()) -> AssetSnapshot:
    verify_inventory(root, expected)
    for name in sorted(expected):
        scan_asset(root / name, known_secrets)
    verify_inventory(root, expected)
    return AssetSnapshot(root, tuple(sorted(expected.items())))


@filesystem_boundary
def verify_unchanged(snapshot: AssetSnapshot) -> None:
    verify_inventory(snapshot.root, dict(snapshot.inventory))


@filesystem_boundary
def begin_codegen(output: Path) -> FreshOutput:
    """Observe an empty task-owned directory. Caller must actually control the build."""
    try:
        if output.is_symlink() or not output.is_dir() or any(output.iterdir()):
            raise PolicyError('asset-output-not-fresh') from None
        metadata = output.stat()
    except OSError:
        raise PolicyError('asset-output-not-fresh') from None
    return FreshOutput(output, (metadata.st_dev, metadata.st_ino))


@filesystem_boundary
def verify_build_contract(root: Path, pinned: dict[str, str], *, config_path: str,
                          frontend_dist: str, codegen_features: tuple[str, ...]) -> AssetSnapshot:
    """Verify explicit reviewed config/toolchain/codegen input hashes, not self-approval.

    The real driver must supply the reviewed complete inventory from its immutable
    checkout; this helper cannot establish that trust or inspect arbitrary build hooks.
    """
    required = {'Cargo.lock', 'rust-toolchain.toml', 'embedded_assets.rs', 'assets.rs'}
    if (codegen_features != ('compression',) or config_path not in pinned
            or not required.issubset({Path(name).name for name in pinned})):
        raise PolicyError('asset-build-contract') from None
    snapshot = capture_assets(root, pinned)
    try:
        config = json.loads((root / config_path).read_bytes())
    except (ValueError, OSError, RecursionError):
        raise PolicyError('asset-build-contract') from None
    if (not isinstance(config, dict) or not isinstance(config.get('build'), dict)
            or config['build'].get('frontendDist') != frontend_dist):
        raise PolicyError('asset-build-contract') from None
    return snapshot


@filesystem_boundary
def verify_cargo_output(messages: Path, operator: Path, expected_sha256: str) -> None:
    """Bind a selected release executable to supplied Cargo output; not log authenticity."""
    found = []
    try:
        if messages.is_symlink() or messages.stat().st_size > 8 * 1024 * 1024:
            raise PolicyError('asset-cargo-binding') from None
        for line in messages.read_bytes().splitlines():
            value = json.loads(line)
            if (not isinstance(value, dict) or not isinstance(value.get('target', {}), dict)
                    or not isinstance(value.get('profile', {}), dict)):
                raise PolicyError('asset-cargo-binding') from None
            if value.get('reason') == 'compiler-artifact' and value.get('target', {}).get('name') == 'selahcue-operator':
                found.append(value)
    except (OSError, ValueError, RecursionError):
        raise PolicyError('asset-cargo-binding') from None
    if (len(found) != 1 or found[0].get('executable') != str(operator)
            or found[0].get('profile', {}).get('debug_assertions') is not False
            or file_digest(operator)[1] != expected_sha256):
        raise PolicyError('asset-cargo-binding') from None


@filesystem_boundary
def finish_codegen(inputs: AssetSnapshot, output: FreshOutput, generated: dict[str, str], *,
                   emitted_operator: Path, emitted_sha256: str, packaged_sha256: str) -> AssetChain:
    verify_unchanged(inputs)
    try:
        if output.root.is_symlink() or not output.root.is_dir():
            raise PolicyError('asset-output-not-fresh') from None
        metadata = output.root.stat()
    except OSError:
        raise PolicyError('asset-output-not-fresh') from None
    if (metadata.st_dev, metadata.st_ino) != output.identity:
        raise PolicyError('asset-output-not-fresh') from None
    verify_inventory(output.root, generated)
    if (not re.fullmatch('[0-9a-f]{64}', emitted_sha256)
            or emitted_sha256 != packaged_sha256
            or file_digest(emitted_operator)[1] != emitted_sha256):
        raise PolicyError('asset-operator-binding') from None
    return AssetChain()
