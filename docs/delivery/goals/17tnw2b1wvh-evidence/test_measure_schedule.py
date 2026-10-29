"""Private-file regressions for the opt-in launcher study (no browser/build).

Run: python3 docs/delivery/goals/17tnw2b1wvh-evidence/test_measure_schedule.py
Every attacker path and synthetic victim lives beneath this test's private root.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).with_name('measure_schedule.py')
SENTINEL = 'PRECIOUS SYNTHETIC BYTES'


class PrivateControls(unittest.TestCase):
    def load(self, shared):
        with mock.patch.object(tempfile, 'tempdir', str(shared)):
            spec = importlib.util.spec_from_file_location('private_measurement_fixture', SOURCE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        if hasattr(module, '_CONTROL'):
            self.addCleanup(module._CONTROL.cleanup)
        return module

    def fixture(self):
        context = tempfile.TemporaryDirectory(prefix='measure-file-security-')
        self.addCleanup(context.cleanup)
        root = Path(context.name).resolve()
        shared = root / 'simulated-shared-temp'
        shared.mkdir(mode=0o777)
        shared.chmod(0o777)
        victim = root / 'synthetic-victim.txt'
        victim.write_text(SENTINEL)
        return root, shared, victim

    def pause_once(self, module):
        module.PAUSE.touch()
        with mock.patch.object(module.time, 'sleep', side_effect=lambda _: module.PAUSE.unlink()):
            module.pause_if_requested()

    def test_predictable_preplant_is_never_used(self):
        root, shared, victim = self.fixture()
        planted = shared / 'selahcue-launcher-schedule'
        planted.mkdir(mode=0o777)
        planted.chmod(0o777)
        status = planted / '17tnw2b1wvh-measurement-status.json'
        status.symlink_to(victim)
        pause = planted / '17tnw2b1wvh-measurement.pause'
        pause.touch()
        module = self.load(shared)
        with mock.patch.object(module.time, 'sleep', side_effect=lambda _: pause.unlink()):
            module.pause_if_requested()
        self.assertEqual(victim.read_text(), SENTINEL)
        self.assertTrue(status.is_symlink())
        self.assertNotEqual(module.OUT, planted)
        self.assertEqual(module.OUT.parent, shared)
        self.assertEqual(stat.S_IMODE(module.OUT.stat().st_mode), 0o700)
        self.assertEqual(module.OUT.stat().st_uid, os.getuid())

    def test_status_symlink_is_refused_without_touching_victim(self):
        _, shared, victim = self.fixture()
        module = self.load(shared)
        module.STATUS.symlink_to(victim)
        try:
            with self.assertRaises(OSError):
                self.pause_once(module)
        finally:
            self.assertEqual(victim.read_text(), SENTINEL)
        self.assertTrue(module.STATUS.is_symlink())

    def test_swapped_control_directory_cannot_redirect_status(self):
        root, shared, _ = self.fixture()
        module = self.load(shared)
        moved = root / 'moved-control'
        redirected = root / 'synthetic-victim-directory'
        redirected.mkdir()
        target = redirected / module.STATUS.name
        target.write_text(SENTINEL)
        (redirected / module.PAUSE.name).touch()
        module.OUT.rename(moved)
        module.OUT.symlink_to(redirected, target_is_directory=True)
        try:
            with self.assertRaises(OSError):
                self.pause_once(module)
            self.assertEqual(target.read_text(), SENTINEL)
        finally:
            module.OUT.unlink()
            moved.rename(module.OUT)

    def test_writable_by_others_control_directory_is_refused(self):
        _, shared, _ = self.fixture()
        module = self.load(shared)
        module.OUT.chmod(0o777)
        try:
            with self.assertRaises(OSError):
                self.pause_once(module)
            self.assertFalse(module.STATUS.exists())
        finally:
            module.OUT.chmod(0o700)

    def test_legitimate_pause_resumes_and_writes_private_complete_json(self):
        _, shared, _ = self.fixture()
        module = self.load(shared)
        seen = []
        module.PAUSE.touch()
        def resume(_):
            seen.append(json.loads(module.STATUS.read_text()))
            module.PAUSE.unlink()
        out = io.StringIO()
        with mock.patch.object(module.time, 'sleep', side_effect=resume), contextlib.redirect_stdout(out):
            module.pause_if_requested()
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]['state'], 'paused')
        self.assertEqual(seen[0]['pid'], os.getpid())
        self.assertIn('PAUSED:', out.getvalue())
        self.assertIn('RESUMED', out.getvalue())
        self.assertFalse(module.PAUSE.exists())
        self.assertFalse(module.STATUS.is_symlink())
        self.assertEqual(stat.S_IMODE(module.STATUS.stat().st_mode), 0o600)
        self.assertEqual({p.name for p in module.OUT.iterdir()}, {module.STATUS.name})

    def test_failed_atomic_publish_keeps_previous_status_and_cleans_temporary(self):
        _, shared, _ = self.fixture()
        module = self.load(shared)
        module.write_json(module.STATUS, {'state':'before'}, private=True)
        before = module.STATUS.read_bytes()
        with mock.patch.object(module.os, 'replace', side_effect=OSError('synthetic publish failure')):
            with self.assertRaises(OSError):
                module.write_json(module.STATUS, {'state':'after'}, private=True)
        self.assertEqual(module.STATUS.read_bytes(), before)
        self.assertEqual({p.name for p in module.OUT.iterdir()}, {module.STATUS.name})

    def test_leaf_swapped_after_check_is_replaced_without_following_it(self):
        _, shared, victim = self.fixture()
        module = self.load(shared)
        module.write_json(module.STATUS, {'state':'before'}, private=True)
        real_replace = module.os.replace
        def swap_then_replace(source, destination, **kwargs):
            module.STATUS.unlink()
            module.STATUS.symlink_to(victim)
            return real_replace(source, destination, **kwargs)
        with mock.patch.object(module.os, 'replace', side_effect=swap_then_replace):
            module.write_json(module.STATUS, {'state':'after'}, private=True)
        self.assertEqual(victim.read_text(), SENTINEL)
        self.assertFalse(module.STATUS.is_symlink())
        self.assertEqual(json.loads(module.STATUS.read_text()), {'state':'after'})
        self.assertEqual({p.name for p in module.OUT.iterdir()}, {module.STATUS.name})

    def test_output_symlink_is_refused_before_any_sample(self):
        root, shared, victim = self.fixture()
        module = self.load(shared)
        output = root / 'report.json'
        output.symlink_to(victim)
        try:
            # Sampling itself is deliberately outside this filesystem test. A
            # malicious output must be refused at the real CLI preflight first.
            with mock.patch.object(sys, 'argv', [str(SOURCE), '--controls', '--output', str(output)]), mock.patch.object(module, 'run_sample', side_effect=AssertionError('untrusted output reached sampling')):
                with self.assertRaises(OSError):
                    module.main()
        finally:
            self.assertEqual(victim.read_text(), SENTINEL)
        self.assertTrue(output.is_symlink())


if __name__ == '__main__':
    unittest.main()
