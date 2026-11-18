"""Offline controls for the ordinary Linux operator's APT preference."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve()
REPO = SCRIPT.parents[2]
HELPER = SCRIPT.with_name("configure_operator_apt_mirror.py")
EC2 = b"http://us-east-2.ec2.archive.ubuntu.com/ubuntu/"
PUBLIC = b"https://archive.ubuntu.com/ubuntu/"
SECURITY = b"https://security.ubuntu.com/ubuntu/"
ORIGINAL = EC2 + b"\tpriority:1\n" + PUBLIC + b"\tpriority:2\n" + SECURITY + b"\tpriority:3\n"
PREFERRED = EC2 + b"\tpriority:2\n" + PUBLIC + b"\tpriority:1\n" + SECURITY + b"\tpriority:3\n"
AZURE = ORIGINAL.replace(EC2, b"http://azure.archive.ubuntu.com/ubuntu/")
ACTIVE = b"""Types: deb
URIs: mirror+file:/etc/apt/apt-mirrors.txt
Suites: resolute resolute-updates resolute-backports
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: http://security.ubuntu.com/ubuntu/
Suites: resolute-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
"""
APT_STEP = """sudo apt-get update
sudo apt-get install -y --no-install-recommends \\
  libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \\
  librsvg2-dev libx11-dev libxkbcommon-dev \\
  libasound2-dev poppler-utils
"""
WEBKIT_STEP = """python3 -m pip install --user --break-system-packages playwright==1.65.2
python3 -m playwright install --with-deps webkit
"""
GUARD_LINE = ('sudo /usr/bin/python3 -I '
              '"$GITHUB_WORKSPACE/.github/scripts/configure_operator_apt_mirror.py"\n')
PACKAGES = ["libwebkit2gtk-4.1-dev", "libgtk-3-dev", "libayatana-appindicator3-dev",
            "librsvg2-dev", "libx11-dev", "libxkbcommon-dev", "libasound2-dev", "poppler-utils"]
PIP = ["-m", "pip", "install", "--user", "--break-system-packages", "playwright==1.65.2"]
PLAYWRIGHT = ["-m", "playwright", "install", "--with-deps", "webkit"]
WEBKIT_CHILD = ["install", "-y", "fake-webkit-os-deps"]
STOCK_CONFIG = b"""directory='/'
etc='/etc/apt/'
sourcelist='/etc/apt/sources.list'
sourceparts='/etc/apt/sources.list.d/'
"""


def load_helper(path=HELPER):
    spec = importlib.util.spec_from_file_location("configure_operator_apt_mirror", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def no_attributes(fd):
    # listxattr(fd) is Linux-specific. The portable fixtures inject its observation.
    return []


def fake_command(name, args):
    root = Path(os.environ["APT_FIXTURE"])

    def record(command, argv, **values):
        with (root / "calls.jsonl").open("a") as log:
            print(json.dumps(dict(command=command, argv=argv, **values)), file=log)

    if name == "sudo" and args[0] == "apt-get":
        os.execvp(args[0], args)
    if name == "sudo" and args == ["/usr/bin/python3", "-I", str(HELPER)]:
        helper = load_helper(Path(args[2]))
        return helper.report(root, os.geteuid(), no_attributes,
                             lambda: helper.stock_paths((root / "apt-config.txt").read_bytes()))
    if name == "apt-get":
        lines = (root / "etc/apt/apt-mirrors.txt").read_bytes().splitlines()
        ordered = [line.split(b"\tpriority:") for line in lines]
        first = min(ordered, key=lambda entry: int(entry[1]))[0]
        record(name, args, first=first.decode())
        operation = "child" if args == WEBKIT_CHILD else args[0]
        if os.environ.get("APT_FIXTURE_FAIL") == operation:
            return {"update": 31, "install": 32, "child": 33}[operation]
        return 0
    if name == "python3":
        record(name, args)
        if args == PLAYWRIGHT:
            return subprocess.run(["sudo", "apt-get", *WEBKIT_CHILD], check=False).returncode
        if args == PIP:
            return 0
    raise ValueError(f"unexpected fixture command: {name} {args!r}")


class AptFiles(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.apt = self.root / "etc/apt"
        self.mirror = self.apt / "apt-mirrors.txt"
        self.source = self.apt / "sources.list.d/ubuntu.sources"
        self.source.parent.mkdir(parents=True)
        self.mirror.write_bytes(ORIGINAL)
        self.source.write_bytes(ACTIVE)
        self.mirror.chmod(0o640)

    def assert_no_staging(self):
        self.assertEqual(sorted(path.name for path in self.apt.iterdir()),
                         ["apt-mirrors.txt", "sources.list.d"])


class WorkflowFixture(AptFiles):
    @classmethod
    def setUpClass(cls):
        import yaml

        workflow = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
        cls.operator = workflow["jobs"]["operator"]
        cls.steps = {step["name"]: step for step in cls.operator["steps"] if "name" in step}

    def setUp(self):
        super().setUp()
        (self.root / "apt-config.txt").write_bytes(STOCK_CONFIG)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("sudo", "apt-get", "python3"):
            command = self.bin / name
            command.write_text("#!/bin/sh\nexec " + shlex.join([
                sys.executable, "-B", str(SCRIPT), "--fake", name,
            ]) + ' "$@"\n')
            command.chmod(0o700)

    def run_step(self, recipe, failure=""):
        if recipe == "apt":
            step = self.steps["Linux system deps (Tauri v2 webview + ALSA for cpal)"]
            self.assertEqual(step["if"], "runner.os == 'Linux'")
            self.assertEqual(step["run"], GUARD_LINE + APT_STEP)
        else:
            step = self.steps["Install Playwright WebKit (Linux)"]
            self.assertEqual(step["run"], WEBKIT_STEP)
        # Only the known recipes above may execute, with every command name resolved privately.
        return subprocess.run(["/bin/bash", "--noprofile", "--norc", "-e", "-c", step["run"]],
                              cwd=self.root, env={"PATH": str(self.bin), "GITHUB_WORKSPACE": str(REPO),
                                                  "APT_FIXTURE": str(self.root),
                                                  "APT_FIXTURE_FAIL": failure},
                              capture_output=True, text=True, check=False)

    def calls(self):
        return [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]

    def test_operator_and_playwright_child_prefer_existing_public_mirror(self):
        self.assertEqual(len(ORIGINAL), 152)
        for recipe in ("apt", "webkit"):
            result = self.run_step(recipe)
            self.assertEqual(result.returncode, 0, result.stderr)
            if recipe == "apt":
                self.assertEqual(result.stdout, "operator APT mirror: promoted\n")
        calls = self.calls()
        self.assertEqual([(call["command"], call["argv"]) for call in calls], [
            ("apt-get", ["update"]),
            ("apt-get", ["install", "-y", "--no-install-recommends", *PACKAGES]),
            ("python3", PIP), ("python3", PLAYWRIGHT), ("apt-get", WEBKIT_CHILD),
        ])
        self.assertEqual(self.source.read_bytes(), ACTIVE)
        self.assertEqual([call["first"] for call in calls if call["command"] == "apt-get"],
                         [PUBLIC.decode()] * 3, "explicit update/install and Playwright APT preference")
        self.assertEqual(self.mirror.read_bytes(), PREFERRED)
        self.assert_no_staging()

    def test_package_failures_exit_the_original_shell_steps(self):
        for failure, recipe, status, expected_tail in (
            ("update", "apt", 31, ["update"]),
            ("install", "apt", 32, ["install", "-y", "--no-install-recommends", *PACKAGES]),
            ("child", "webkit", 33, WEBKIT_CHILD),
        ):
            with self.subTest(failure=failure):
                result = self.run_step(recipe, failure)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(self.calls()[-1]["argv"], expected_tail)

    def test_unsupported_configuration_runs_stock_package_commands(self):
        (self.root / "apt-config.txt").write_bytes(STOCK_CONFIG + b"rootdir='/other'\n")
        result = self.run_step("apt")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "operator APT mirror: unsupported_configuration\n")
        self.assertEqual([call["first"] for call in self.calls()], [EC2.decode()] * 2)
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)

    def test_guard_failure_blocks_existing_update(self):
        # An unexpected configuration read error is a hard failure before apt-get.
        query = self.root / "apt-config.txt"
        query.unlink()
        result = self.run_step("apt")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "operator APT mirror: failed\n")
        self.assertFalse((self.root / "calls.jsonl").exists())
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)

    def test_generic_webkit_remains_required(self):
        self.assertEqual(self.operator["timeout-minutes"], 30)
        self.assertEqual(self.steps["Webview WebKit-engine smoke (Linux, Playwright WebKit)"]["env"]
                         ["SELAHCUE_WEBKIT_REQUIRE"], "1")


class GuardFixture(AptFiles):
    @classmethod
    def setUpClass(cls):
        cls.helper = load_helper()

    def configure(self, attributes=no_attributes, query=lambda: True):
        return self.helper.configure(self.root, os.geteuid(), attributes, query)

    def assert_guard_failure(self, attributes=no_attributes, query=lambda: True):
        with redirect_stdout(StringIO()) as out, redirect_stderr(StringIO()) as err:
            result = self.helper.report(self.root, os.geteuid(), attributes, query)
        self.assertEqual((result, out.getvalue(), err.getvalue()), (1, "", "operator APT mirror: failed\n"))
        self.assert_no_staging()

    @staticmethod
    def attributes(path):
        observed = path.stat()
        return observed.st_ino, observed.st_mtime_ns, observed.st_uid, observed.st_gid, observed.st_mode

    def test_preserves_uris_signing_bytes_and_metadata_and_does_not_rewrite_twice(self):
        before = self.attributes(self.mirror)
        original_source = self.attributes(self.source)
        self.assertEqual(self.configure(), "promoted")
        after = self.attributes(self.mirror)
        self.assertNotEqual(before[0], after[0])
        self.assertEqual(before[2:], after[2:])
        self.assertEqual(self.mirror.read_bytes(), PREFERRED)
        self.assertEqual([i for i, pair in enumerate(zip(ORIGINAL, PREFERRED, strict=True))
                          if pair[0] != pair[1]], [57, 103])
        self.assertEqual(self.source.read_bytes(), ACTIVE)
        self.assertEqual(self.attributes(self.source), original_source)
        self.assertEqual(self.configure(), "already_preferred")
        self.assertEqual(self.attributes(self.mirror), after)
        self.assert_no_staging()

    def test_stock_azure_and_unknown_mirror_layouts_are_untouched(self):
        for desired, contents in (
            ("azure", AZURE),
            ("unknown_mirror", ORIGINAL + ORIGINAL.splitlines(keepends=True)[0]),
            ("unknown_mirror", ORIGINAL.replace(b"priority:2", b"priority:1")),
            ("unknown_mirror", ORIGINAL.replace(b"priority:1", b"priority:1 arch:amd64")),
            ("unknown_mirror", ORIGINAL.replace(PUBLIC, b"http://archive.ubuntu.com/ubuntu/")),
            ("unknown_mirror", ORIGINAL.splitlines(keepends=True)[0]),
            ("unknown_mirror", ORIGINAL.replace(b"\n", b"\r\n")),
            ("unknown_mirror", ORIGINAL.replace(b"us-east-2.ec2", b"other-archive")),
        ):
            with self.subTest(contents=contents):
                self.mirror.write_bytes(contents)
                before = self.attributes(self.mirror)
                self.assertEqual(self.configure(), desired)
                self.assertEqual(self.mirror.read_bytes(), contents)
                self.assertEqual(self.attributes(self.mirror), before)
        self.assert_no_staging()

    def test_missing_source_or_mirror_skips(self):
        self.source.unlink()
        self.assertEqual(self.configure(), "missing")
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)
        self.source.write_bytes(ACTIVE)
        self.mirror.unlink()
        self.assertEqual(self.configure(), "missing")
        self.assertFalse(self.mirror.exists())

    def test_recognizes_enabled_deb822_binary_stanza(self):
        enabled = ACTIVE.replace(b"Types: deb\n", b"types: deb deb-src\nEnabled: yes\n", 1)
        self.source.write_bytes(enabled)
        self.assertEqual(self.configure(), "promoted")
        self.assertEqual(self.source.read_bytes(), enabled)

    def test_unreferenced_and_ambiguous_deb822_never_rewrite_mirror(self):
        uri = b"mirror+file:/etc/apt/apt-mirrors.txt"
        direct = ACTIVE.split(b"\n\n", 1)[1]
        for expected, source in (
            ("inactive_sources", b"# URIs: " + uri + b"\n" + direct),
            ("inactive_sources", ACTIVE.replace(b"Types: deb\n", b"Types: deb\nEnabled: no\n", 1)),
            ("inactive_sources", ACTIVE.replace(b"Types: deb\n", b"Types: deb-src\n", 1)),
            ("inactive_sources", ACTIVE.replace(uri, uri + b".alternate")),
            ("unsupported_sources", ACTIVE.replace(uri, uri + b" https://example.invalid/")),
            ("unsupported_sources", ACTIVE.replace(uri, b"\n " + uri)),
            ("unsupported_sources", ACTIVE.replace(b"\n\n", b"\n \n", 1)),
            ("unsupported_sources", ACTIVE.replace(b"Suites: resolute", b"Broken line\nSuites: resolute", 1)),
            ("unsupported_sources", ACTIVE.replace(b"Types: deb\n", b"Types: deb\nTyPeS: deb\n", 1)),
            ("unsupported_sources", ACTIVE.replace(b"Types: deb\n", b"Types: deb\nEnabled: maybe\n", 1)),
            ("unsupported_sources", ACTIVE.replace(b"Suites:", b"Unrelated:", 1)),
        ):
            with self.subTest(source=source):
                self.source.write_bytes(source)
                before = self.attributes(self.mirror)
                self.assertEqual(self.configure(), expected)
                self.assertEqual(self.mirror.read_bytes(), ORIGINAL)
                self.assertEqual(self.attributes(self.mirror), before)
                self.assertEqual(self.source.read_bytes(), source)
        self.assert_no_staging()

    def test_config_requires_only_resolved_stock_paths(self):
        self.assertTrue(self.helper.stock_paths(STOCK_CONFIG))
        self.assertTrue(self.helper.stock_paths(b"rootdir=''\n" + STOCK_CONFIG))
        self.assertTrue(self.helper.stock_paths(b"rootdir='/'\n" + STOCK_CONFIG))
        alternate_settings = (
            STOCK_CONFIG.replace(b"sourceparts='/etc/apt/sources.list.d/'", b"sourceparts='/alt/'"),
            STOCK_CONFIG.replace(b"sourcelist='/etc/apt/sources.list'", b"sourcelist='/alt'"),
            STOCK_CONFIG.replace(b"/etc/apt/sources.list.d/", b"/etc/apt/sources.list.d"),
            b"\n".join(STOCK_CONFIG.splitlines()[1:]) + b"\n",
            STOCK_CONFIG + b"rootdir='/alt'\n",
            STOCK_CONFIG + b"directory='/'\n",
            STOCK_CONFIG + b"other='/alt'\n",
            STOCK_CONFIG.replace(b"directory='/'", b'directory="/"'),
            STOCK_CONFIG.replace(b"directory='/'", b"directory='/\n'"),
            STOCK_CONFIG.replace(b"directory='/'", b"directory='/'$(command)"),
        )
        for candidate in alternate_settings:
            with self.subTest(config=candidate):
                self.assertEqual(self.configure(query=lambda: self.helper.stock_paths(candidate)),
                                 "unsupported_configuration")
                self.assertEqual(self.mirror.read_bytes(), ORIGINAL)
        with mock.patch.dict(os.environ, APT_CONFIG="unexpected"):
            with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("must skip before launch")):
                self.assertEqual(self.configure(query=self.helper.query_paths), "unsupported_configuration")

    def fake_config_runner(self, paths, overrides=None, status=0):
        real_popen = subprocess.Popen

        def launch(args, *, executable, shell, **kwargs):
            self.assertEqual(executable, "/usr/bin/apt-config")
            self.assertIs(shell, False)
            self.assertEqual(args, ["apt-get", "shell", "rootdir", "RootDir",
                                    "directory", "Dir/d", "etc", "Dir::Etc/d",
                                    "sourcelist", "Dir::Etc::sourcelist/f",
                                    "sourceparts", "Dir::Etc::sourceparts/d"])
            output = (overrides or {}).get(args[0], paths)
            return real_popen([
                sys.executable, "-I", "-S", "-B", "-c",
                "import sys; sys.stdout.buffer.write(bytes.fromhex(sys.argv[1])); sys.exit(int(sys.argv[2]))",
                output.hex(), str(status),
            ], **kwargs)

        return mock.patch.object(subprocess, "Popen", side_effect=launch)

    def test_query_uses_only_the_apt_get_namespace_at_each_observation(self):
        redirected = STOCK_CONFIG.replace(b"/etc/apt/sources.list.d/", b"/alternate/")
        for paths, overrides, decision, count in (
            (redirected, {"apt-config": STOCK_CONFIG}, "unsupported_configuration", 1),
            (STOCK_CONFIG, {"apt-get": redirected}, "unsupported_configuration", 1),
            (STOCK_CONFIG, {"apt-config": redirected}, "promoted", 2),
        ):
            with self.subTest(paths=paths, overrides=overrides):
                self.mirror.write_bytes(ORIGINAL)
                before = self.attributes(self.mirror)
                with mock.patch.dict(os.environ), self.fake_config_runner(paths, overrides) as launch:
                    os.environ.pop("APT_CONFIG", None)
                    self.assertEqual(self.configure(query=self.helper.query_paths), decision)
                self.assertEqual(launch.call_count, count)
                if decision == "promoted":
                    self.assertEqual(self.mirror.read_bytes(), PREFERRED)
                else:
                    self.assertEqual(self.mirror.read_bytes(), ORIGINAL)
                    self.assertEqual(self.attributes(self.mirror), before)
        self.assert_no_staging()

    def test_query_launch_nonzero_exit_and_capture_bound_fail_setup(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("APT_CONFIG", None)
            for runner in (
                mock.patch.object(subprocess, "Popen", side_effect=FileNotFoundError("fixture executable")),
                self.fake_config_runner(STOCK_CONFIG, status=23),
                self.fake_config_runner(b"x" * 8193),
            ):
                with runner:
                    self.assert_guard_failure(query=self.helper.query_paths)
                self.assertEqual(self.mirror.read_bytes(), ORIGINAL)

    def test_refuses_symlinked_paths_hardlinks_and_nonregular_targets(self):
        outside = self.root / "outside"
        self.mirror.rename(outside)
        self.mirror.symlink_to(outside)
        self.assertEqual(self.configure(), "unsafe_layout")
        self.assertTrue(self.mirror.is_symlink())
        self.mirror.unlink()

        self.mirror.hardlink_to(outside)
        self.assertEqual(self.configure(), "unsafe_layout")
        self.assertEqual(self.mirror.stat().st_nlink, 2)
        self.mirror.unlink()
        for create in (lambda: self.mirror.mkdir(), lambda: os.mkfifo(self.mirror)):
            with self.subTest(create=create):
                create()
                self.assertEqual(self.configure(), "unsafe_layout")
                (self.mirror.rmdir if self.mirror.is_dir() else self.mirror.unlink)()
        self.mirror.write_bytes(ORIGINAL)

        self.source.unlink()
        self.source.symlink_to(outside)
        self.assertEqual(self.configure(), "unsafe_layout")
        self.assertEqual(outside.read_bytes(), ORIGINAL)
        actual = self.root / "moved-apt"
        self.apt.rename(actual)
        self.apt.symlink_to(actual, target_is_directory=True)
        self.assertEqual(self.configure(), "unsafe_layout")
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)

    def test_refuses_unsafe_mode_owner_or_metadata(self):
        for path in (self.mirror, self.source, self.apt, self.source.parent):
            with self.subTest(path=path):
                mode = path.stat().st_mode
                path.chmod(mode | 0o020)
                try:
                    self.assertEqual(self.configure(), "unsafe_layout")
                finally:
                    path.chmod(mode)

        real_stat = os.stat

        def wrong_owner(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path == self.mirror.name and kwargs.get("dir_fd") is not None:
                return SimpleNamespace(st_mode=info.st_mode, st_nlink=info.st_nlink, st_uid=os.geteuid() + 1)
            return info

        with mock.patch.object(os, "stat", side_effect=wrong_owner):
            self.assertEqual(self.configure(), "unsafe_layout")
        target = self.mirror.stat().st_ino

        def extended_attributes(fd):
            return ["system.posix_acl_access"] if os.fstat(fd).st_ino == target else []

        self.assertEqual(self.configure(attributes=extended_attributes), "unsupported_metadata")
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)
        self.assert_no_staging()

    def test_reports_unexpected_read_failure(self):
        def denied_attributes(fd):
            raise PermissionError("fixture denies metadata read")

        self.assert_guard_failure(attributes=denied_attributes)
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)

    def test_staging_collision_preserves_the_existing_file(self):
        collision = self.apt / ".operator-apt-mirror-fixture"
        collision.write_bytes(b"preexisting")
        with mock.patch.object(self.helper.secrets, "token_hex", return_value="fixture"):
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                result = self.helper.report(self.root, os.geteuid(), no_attributes, lambda: True)
        self.assertEqual(result, 1)
        self.assertEqual(collision.read_bytes(), b"preexisting")
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)

    def test_write_attribute_sync_and_rename_errors_preserve_original(self):
        for operation in ("fchown", "fchmod", "fsync", "replace"):
            with self.subTest(operation=operation):
                before = self.attributes(self.mirror)
                with mock.patch.object(os, operation, side_effect=PermissionError(operation)):
                    self.assert_guard_failure()
                self.assertEqual(self.mirror.read_bytes(), ORIGINAL)
                self.assertEqual(self.attributes(self.mirror), before)

        real_write = os.write

        def with_partial_write(fd, data):
            return real_write(fd, data[:1])

        with mock.patch.object(os, "write", side_effect=with_partial_write):
            self.assert_guard_failure()
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)

    def test_drift_in_effective_roots_source_bytes_mirror_inode_or_mode_stops_publication(self):
        self.assert_guard_failure(query=mock.Mock(side_effect=(True, False)))
        for name, change in (
            ("source bytes", lambda: self.source.write_bytes(ACTIVE + b"# changed\n")),
            ("mirror bytes", lambda: self.mirror.write_bytes(ORIGINAL + b"# changed\n")),
            ("mirror mode", lambda: self.mirror.chmod(0o600)),
        ):
            with self.subTest(change=name):
                self.source.write_bytes(ACTIVE)
                self.mirror.write_bytes(ORIGINAL)
                self.mirror.chmod(0o640)

                def recheck():
                    change()
                    return True

                answers = iter((lambda: True, recheck))
                self.assert_guard_failure(query=lambda: next(answers)())
                self.assertNotEqual(self.mirror.read_bytes(), PREFERRED)

        fresh = self.root / "replacement"
        fresh.write_bytes(ORIGINAL)
        answers = iter((lambda: True, lambda: fresh.replace(self.mirror)))
        self.assert_guard_failure(query=lambda: bool(next(answers)()))
        self.assertEqual(self.mirror.read_bytes(), ORIGINAL)

    def test_readback_error_keeps_complete_promoted_file_and_fails(self):
        real_replace = os.replace
        replaced = False

        def mark_published(*args, **kwargs):
            nonlocal replaced
            real_replace(*args, **kwargs)
            replaced = True

        def readback(fd):
            if replaced and os.fstat(fd).st_ino == self.mirror.stat().st_ino:
                raise OSError("fixture denies final readback")
            return []

        with mock.patch.object(os, "replace", side_effect=mark_published):
            self.assert_guard_failure(attributes=readback)
        self.assertEqual(self.mirror.read_bytes(), PREFERRED)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--fake"]:
        raise SystemExit(fake_command(sys.argv[2], sys.argv[3:]))
    unittest.main(verbosity=2)
