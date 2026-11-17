#!/usr/bin/env python3
"""Closed release-operator CLI for SelahCue installer publication."""

from collections.abc import Sequence
import errno
import os
from pathlib import Path
import sys

from installer_publication.contracts import PublicationError, require

_FLAGS = {
    "prepare": ("--input", "--source-tree", "--out-dir"),
    "upload": ("--release-dir",),
    "verify-public": ("--plan", "--out"),
    "emit-manifest": ("--release-dir", "--verification", "--out"),
}


def _paths(command: str, args: Sequence[str]) -> dict[str, Path]:
    flags = _FLAGS.get(command, ())
    require(bool(flags) and len(args) == 2 * len(flags), "Invalid installer publisher command or arguments")
    paths: dict[str, Path] = {}
    for flag, value in zip(args[::2], args[1::2], strict=True):
        require(flag in flags and flag not in paths and bool(value) and not value.startswith("--")
                and "\0" not in value, "Invalid installer publisher arguments")
        paths[flag] = Path(value)
    return paths


def _self_test() -> bool:
    import unittest

    names = tuple(f"test_installer_publication_{suite}" for suite in ("prepare", "verify", "upload", "cli"))
    return unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names)).wasSuccessful()


def _verify(plan_path: Path, out_path: Path) -> Path:
    from installer_publication.contracts import parse_public_plan, parse_verification, record_bytes
    from installer_publication.prepare import _absolute, _directory, _write_atomic, read_regular_file
    from installer_publication.public_verify import verify_public_plan

    raw_plan = read_regular_file(plan_path)
    plan = parse_public_plan(raw_plan)
    require(raw_plan == record_bytes(plan), "Public plan is not in its exact canonical format")
    out = _absolute(out_path)
    require(bool(out.name) and tuple(part.casefold() for part in out.parts[-3:])
            != ("public", "releases", "current.json"), "Expected a separate verification output file")
    try:
        with _directory(out.parent) as directory:
            try:
                os.stat(out.name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise PublicationError(2, "Verification output must not already exist")

            raw = record_bytes(verify_public_plan(plan))
            parse_verification(raw)
            try:
                _write_atomic(directory, out.name, raw)
            except FileExistsError:
                raise PublicationError(2, "Verification output must not already exist") from None
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
            raise PublicationError(2, "Verification output directory must be a contained directory") from None
        raise PublicationError(5, "Cannot write or sync the verification output") from None
    return out


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    try:
        if args == ["--self-test"]:
            if not _self_test():
                raise PublicationError(5, "Installer publication offline self-test failed")
            print("Installer publication offline self-test passed")
            return 0

        paths = _paths(command, args[1:])
        if command == "prepare":
            from installer_publication.prepare import prepare_release

            release = prepare_release(paths["--input"], paths["--source-tree"], paths["--out-dir"])
            receipt = release.root / "prepare-receipt.json"
        elif command == "upload":
            from installer_publication.upload import upload_release

            upload_release(paths["--release-dir"])
            receipt = paths["--release-dir"] / "upload-receipt.json"
        elif command == "verify-public":
            receipt = _verify(paths["--plan"], paths["--out"])
        else:
            from installer_publication.manifest import emit_manifest

            receipt = emit_manifest(paths["--release-dir"], paths["--verification"], paths["--out"])
        print(f"{command} completed {ascii(str(receipt))[:1024]}")
        return 0
    except PublicationError as error:
        print(f"Installer publisher: {error.reason[:4096]}", file=sys.stderr)
        return error.exit_code
    except (OSError, ValueError):
        print("Installer publisher: local storage or tool operation failed", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
