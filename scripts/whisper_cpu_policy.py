#!/usr/bin/env python3
"""Require compiler evidence for the Windows and Ubuntu installer Whisper builds."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys


class PolicyError(RuntimeError):
    pass


OFF = (
    "GGML_NATIVE", "GGML_SSE42", "GGML_AVX", "GGML_AVX2", "GGML_BMI2", "GGML_FMA", "GGML_F16C",
    "GGML_AVX_VNNI", "GGML_AVX512", "GGML_AVX512_VBMI", "GGML_AVX512_VNNI", "GGML_AVX512_BF16",
    "GGML_AMX_TILE", "GGML_AMX_INT8", "GGML_AMX_BF16",
    "GGML_CPU_ALL_VARIANTS", "GGML_BACKEND_DL", "GGML_CCACHE",
)
GENERATORS = {"linux": "Unix Makefiles", "windows": "Ninja"}
# Translation units for the four static libraries in the locked Whisper CPU build.
REQUIRED_SOURCES = {"src/whisper.cpp"}
REQUIRED_SOURCES.update(
    f"ggml/src/{name}" for name in (
        "ggml.c", "ggml.cpp", "ggml-alloc.c", "ggml-backend.cpp", "ggml-backend-reg.cpp",
        "ggml-opt.cpp", "ggml-threading.cpp", "ggml-quants.c", "gguf.cpp",
    )
)
REQUIRED_SOURCES.update(
    f"ggml/src/ggml-cpu/{name}" for name in (
        "ggml-cpu.c", "ggml-cpu.cpp", "repack.cpp", "hbm.cpp", "quants.c", "traits.cpp",
        "amx/amx.cpp", "amx/mmq.cpp", "binary-ops.cpp", "unary-ops.cpp", "vec.cpp",
        "ops.cpp", "arch/x86/quants.c", "arch/x86/repack.cpp",
    )
)
ENV_EXACT = {
    "CL", "_CL_", "CC", "CXX", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS",
    "GCC_EXEC_PREFIX", "COMPILER_PATH", "CMAKE", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER",
    "RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "CARGO_BUILD_RUSTFLAGS", "CARGO_TARGET_DIR",
    "CARGO_BUILD_TARGET", "CARGO_BUILD_TARGET_DIR", "DOCS_RS", "TAURI_CONFIG",
}
ENV_PREFIXES = (
    "GGML_", "WHISPER_", "CMAKE_", "CC_", "CXX_", "CFLAGS_", "CXXFLAGS_", "CPPFLAGS_",
    "LDFLAGS_", "HOST_", "TARGET_", "CARGO_TARGET_", "CARGO_PROFILE_", "TAURI_",
)
CPU_DEFINE = re.compile(r"^(?:GGML_|__|_M_)(?:SSE[34]|SSSE|AVX|FMA|F16C|BMI|AMX|POPCNT|AES|PCLMUL|FSGSBASE)", re.I)
LINUX_COMPILER = re.compile(r"(?:cc|c\+\+|gcc|g\+\+)(?:-\d+)?")
WINDOWS_COMPILER = re.compile(r"(?:^|/)bin/hostx(?:64|86)/x64/cl\.exe$", re.I)


def policy_config(platform: str) -> dict[str, str]:
    result = dict.fromkeys(OFF, "OFF")
    result.update(CMAKE_EXPORT_COMPILE_COMMANDS="ON", CMAKE_GENERATOR=GENERATORS[platform])
    # GCC's default target can vary with how the distro built GCC. Pin the baseline.
    if platform == "linux":
        result.update(CFLAGS="-march=x86-64", CXXFLAGS="-march=x86-64")
    return result


def operator_environment(incoming, platform: str, target: Path) -> dict[str, str]:
    env = {key: value for key, value in incoming.items()
           if key.upper() not in ENV_EXACT and not key.upper().startswith(ENV_PREFIXES)}
    env.update(policy_config(platform), CARGO_TARGET_DIR=str(target))
    return env


def require_fresh_target(target: Path) -> None:
    if target.is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
        raise PolicyError("Portable Whisper requires an empty operator target directory")


def read_cache(path: Path, expected: dict[str, str]) -> None:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        field, _, value = line.partition("=")
        key, _, kind = field.partition(":")
        if key not in expected or not kind:
            continue
        if key in values:
            raise PolicyError("Whisper CMake cache contains duplicate policy entries")
        values[key] = value
    for key, value in expected.items():
        if values.get(key) != value:
            raise PolicyError(f"Whisper CMake cache does not prove {key} has the portable value")


def compiler_arguments(command: str, platform: str) -> list[str]:
    if platform == "windows":
        # CMake Ninja emits double-quoted MSVC paths. Preserve backslashes.
        lexer = shlex.shlex(command, posix=True)
        lexer.whitespace_split = True
        lexer.escape = ""
        lexer.quotes = '"'
        lexer.commenters = ""
        options = list(lexer)
    else:
        options = shlex.split(command)
    if not options:
        raise PolicyError("Whisper compile command is empty")
    return options


def verify_options(options: list[str], platform: str) -> None:
    compiler = options[0].replace("\\", "/")
    if platform == "windows":
        if not WINDOWS_COMPILER.search(compiler):
            raise PolicyError("Whisper compile command does not invoke the x64 MSVC compiler directly")
    elif not LINUX_COMPILER.fullmatch(compiler.rsplit("/", 1)[-1]):
        raise PolicyError("Whisper compile command does not invoke the expected GCC driver directly")

    expect_definition = False
    arch = []
    for option in options[1:]:
        lower = option.lower()
        if expect_definition:
            definition = option
            expect_definition = False
        elif option == "-D" or (platform == "windows" and lower in ("/d", "-d")):
            expect_definition = True
            continue
        elif option.startswith("-D") or (platform == "windows" and lower.startswith("/d")):
            definition = option[2:]
        else:
            definition = ""
        if CPU_DEFINE.match(definition):
            raise PolicyError("Whisper command has a nonportable compiler option")
        if lower.startswith("-m"):
            if platform == "linux" and lower in ("-march=x86-64", "-m64"):
                if lower.startswith("-march"):
                    arch.append(lower)
                continue
            raise PolicyError("Whisper command has a nonportable compiler option")
        if lower.startswith(("--target", "-target", "-xclang", "/clang:", "/favor", "-favor",
                             "/arch", "-arch", "-specs", "--specs", "-fplugin", "@")):
            raise PolicyError("Whisper command has an unsupported compiler option")
        if option in ("&&", "||", ";", "|", "&", "<", ">"):
            raise PolicyError("Whisper command has an unsupported compiler option")
    if expect_definition or (platform == "linux" and arch != ["-march=x86-64"]):
        raise PolicyError("Whisper command does not prove the expected baseline compiler option")


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def verify(target: Path, platform: str, *, target_triple: str | None = None) -> dict:
    """Read only the current operator target and its one locked Whisper CMake build."""
    target = target.resolve()
    profile = target / target_triple / "release" if target_triple else target / "release"
    outputs = sorted(profile.glob("build/whisper-rs-sys-*/out/build/CMakeCache.txt"))
    if len(outputs) != 1:
        raise PolicyError("Expected one Whisper CMake cache in the operator release target")
    cache = outputs[0]
    build = cache.parent
    if list(build.rglob("CMakeCache.txt")) != [cache]:
        raise PolicyError("Whisper CMake build contains ambiguous cache evidence")
    sources = build.parent / "whisper.cpp"
    if build != build.resolve() or sources != sources.resolve() or not sources.is_dir():
        raise PolicyError("Whisper compiler evidence is outside the operator release target")
    expected = dict.fromkeys(OFF, "OFF")
    expected.update(CMAKE_GENERATOR=GENERATORS[platform], CMAKE_EXPORT_COMPILE_COMMANDS="ON",
                    CMAKE_BUILD_TYPE="Release", CMAKE_HOME_DIRECTORY=sources.as_posix(),
                    BUILD_SHARED_LIBS="OFF", GGML_CPU="ON")
    read_cache(cache, expected)

    commands_path = build / "compile_commands.json"
    if commands_path.is_symlink() or cache.is_symlink():
        raise PolicyError("Whisper compiler evidence must come from the operator target")
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    sources = sources.resolve()
    if not isinstance(commands, list):
        raise PolicyError("Whisper compile database is not a list")
    actual = set()
    for row in commands:
        directory = Path(row["directory"]).resolve()
        source = (directory / row["file"]).resolve()
        if (not directory.is_relative_to(build) or not source.is_relative_to(sources)
                or not source.is_file() or source in actual):
            raise PolicyError("Whisper compile database has ambiguous source paths")
        options = compiler_arguments(row["command"], platform)
        verify_options(options, platform)
        compile_switch = {"-c", "/c"} if platform == "windows" else {"-c"}
        if not compile_switch.intersection(option.lower() for option in options[1:]):
            raise PolicyError("Whisper compiler command is missing the compile-only option")
        # A compile row must actually name its recorded translation unit.
        operands = [re.sub(r"^[-/]T[cp]", "", option) if platform == "windows" else option
                    for option in options[1:]]
        if not any(Path(operand).suffix.lower() in (".c", ".cpp") and (directory / operand).resolve() == source
                   for operand in operands):
            raise PolicyError("Whisper compiler command does not compile its recorded source")
        actual.add(source)
    if not REQUIRED_SOURCES <= {path.relative_to(sources).as_posix() for path in actual}:
        raise PolicyError("Whisper compile database is missing required x86 sources")

    hashes = {}
    for name in ("whisper", "ggml", "ggml-base", "ggml-cpu"):
        filename = f"{name}.lib" if platform == "windows" else f"lib{name}.a"
        archive = build / ("src" if name == "whisper" else "ggml/src") / filename
        if archive != archive.resolve() or not archive.is_file():
            raise PolicyError("Whisper static archive evidence is missing")
        with archive.open("rb") as stream:
            if stream.read(8) != b"!<arch>\n" or archive.stat().st_size <= 8:
                raise PolicyError("Whisper static archive evidence is invalid")
        hashes[name] = file_sha(archive)
    return {
        "architecture": "x86_64", "compiler": "MSVC" if platform == "windows" else "GCC",
        "generator": GENERATORS[platform], "compile_commands": len(actual),
        "baseline": "MSVC x64 default ISA" if platform == "windows" else "-march=x86-64",
        "disabled_options": list(OFF), "compile_database_sha256": file_sha(commands_path),
        "cmake_cache_sha256": file_sha(cache), "archive_sha256": hashes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare-windows", "verify-windows"))
    parser.add_argument("target", type=Path)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()
    target = args.target.resolve()
    if args.action == "prepare-windows":
        require_fresh_target(args.target)
        filtered = operator_environment(os.environ, "windows", target)
        print(json.dumps({"remove": sorted(set(os.environ).difference(filtered)),
                          "set": {**policy_config("windows"), "CARGO_TARGET_DIR": str(target)}}))
        return
    if args.metadata is None:
        parser.error("verify-windows requires --metadata")
    receipt = verify(target, "windows")
    installers = sorted((target / "release/bundle/nsis").glob("*-setup.exe"))
    if (len(installers) != 1 or installers[0].is_symlink() or not installers[0].is_file()
            or installers[0].stat().st_size == 0):
        raise PolicyError("Expected exactly one fresh NSIS installer for the Whisper receipt")
    artifact = installers[0]
    receipt["installer_sha256"] = file_sha(artifact)
    metadata = json.loads(args.metadata.read_text(encoding="utf-8-sig"))
    metadata["whisper_cpu_policy"] = receipt
    metadata["installer"] = artifact.name
    args.metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (PolicyError, OSError, ValueError, TypeError, KeyError) as error:
        message = str(error) if isinstance(error, PolicyError) else "Missing or malformed compiler evidence"
        print(f"Portable Whisper verification failed: {message}", file=sys.stderr)
        sys.exit(1)
