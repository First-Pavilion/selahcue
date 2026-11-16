#!/usr/bin/env python3
"""Exercise the SQLCipher license exception with the actual cargo-deny executable.

Synthetic path dependencies test policy matching, never upstream package metadata.
No compilation, registry download, real data or provider access is needed.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = (
    ROOT / "implementation/desktop/deny.toml",
    ROOT / "implementation/desktop/crates/selahcue-operator/deny.toml",
)
CASES = (
    ("reviewed-package", "sqlcipher-src", "420.0.0", "MIT AND BSD-3-Clause AND blessing AND WTFPL", True),
    ("other-package-blessing", "unreviewed-probe", "420.0.0", "blessing", False),
    ("other-package-wtfpl", "unreviewed-probe", "420.0.0", "WTFPL", False),
    ("other-version-blessing", "sqlcipher-src", "420.0.1", "blessing", False),
    ("other-version-wtfpl", "sqlcipher-src", "420.0.1", "WTFPL", False),
    ("other-license", "sqlcipher-src", "420.0.0", "GPL-3.0-only", False),
    ("ordinary-mit", "unreviewed-probe", "1.0.0", "MIT", True),
)


def main():
    executable = shutil.which("cargo-deny")
    if executable is None:
        raise SystemExit("cargo-deny is required (use the same executable as CI)")
    failures = []
    with tempfile.TemporaryDirectory(prefix="selahcue-license-policy-") as directory:
        root = Path(directory)
        (root / "src").mkdir()
        (root / "src/lib.rs").write_text("")
        probe = root / "probe"
        (probe / "src").mkdir(parents=True)
        (probe / "src/lib.rs").write_text("")
        for policy in POLICIES:
            for case, name, version, license_expression, should_pass in CASES:
                # The workspace root is private, but the dependency deliberately is
                # NOT publish=false: the existing private-crate exemption must not
                # silently bypass the license assertion.
                (root / "Cargo.toml").write_text(
                    '[package]\nname = "license-policy-probe"\nversion = "0.1.0"\n'
                    'edition = "2021"\npublish = false\n[dependencies]\n'
                    f'probe = {{ package = "{name}", path = "probe" }}\n'
                )
                (probe / "Cargo.toml").write_text(
                    f'[package]\nname = "{name}"\nversion = "{version}"\n'
                    f'edition = "2021"\nlicense = "{license_expression}"\n'
                )
                # Changing the synthetic package identity requires regenerating only
                # this disposable fixture's lock, never any repository lockfile.
                (root / "Cargo.lock").unlink(missing_ok=True)
                result = subprocess.run(
                    [executable, "--color", "never", "--offline", "--manifest-path", str(root / "Cargo.toml"),
                     "--config", str(policy), "check", "licenses"],
                    cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    check=False,
                )
                output = result.stdout
                if should_pass:
                    correct = result.returncode == 0 and "licenses ok" in output
                else:
                    # A metadata/configuration error must never count as rejection.
                    correct = (result.returncode != 0 and "error[rejected]" in output
                               and "license is not explicitly allowed" in output
                               and license_expression in output)
                print(f"{policy.relative_to(ROOT)} {case}: exit {result.returncode} "
                      f"{'PASS' if correct else 'FAIL'}")
                if not correct:
                    failures.append(case)
                    print(output)
    if failures:
        raise SystemExit(f"License exception checks failed: {', '.join(failures)}")
    print(f"License exception checks: {len(POLICIES) * len(CASES)} passed")


if __name__ == "__main__":
    main()
