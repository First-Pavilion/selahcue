import argparse
import ast
import copy
import errno
import hashlib
import inspect
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import statistics
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[4]
# Match the launcher's private-temp pattern, never a predictable shared directory.
# Canonicalize the system temp root before allocation (macOS /var is a symlink).
_CONTROL = tempfile.TemporaryDirectory(prefix='selahcue-launcher-schedule-',
                                       dir=str(Path(tempfile.gettempdir()).resolve()))
OUT = Path(_CONTROL.name)
BASE = '8f7d610ef81efc4c7359e9b3cb6d9d44fb99c56e'
PAUSE = OUT / '17tnw2b1wvh-measurement.pause'
STATUS = OUT / '17tnw2b1wvh-measurement-status.json'
sys.path.insert(0, str(REPO / 'scripts'))
import headless_chrome as h


def _open_directory(path, private=False):
    """Anchor operations to a verified directory descriptor; no symlink component."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(os.path.sep, flags)
    try:
        for part in Path(os.path.abspath(path)).parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        info = os.fstat(descriptor)
        forbidden = 0o077 if private else 0o022
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & forbidden:
            raise PermissionError(errno.EACCES, 'measurement directory must be owned and protected from other writers', str(path))
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _check_target(directory, name):
    try:
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise OSError(errno.ELOOP, 'measurement target must be an owned regular file, not a link', name)
    return True


def validate_output(path):
    directory = _open_directory(path.parent)
    try:
        _check_target(directory, path.name)
    finally:
        os.close(directory)


def write_json(path, data, private=False):
    """Write a new0600 file and atomically replace only the anchored leaf name."""
    directory = _open_directory(path.parent, private=private)
    temporary = '.measurement-' + secrets.token_hex(16)
    created = False
    try:
        _check_target(directory, path.name)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        created = True
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        # Both names are relative to the same verified directory. Even a leaf
        # swapped after the check is replaced, never opened/followed/truncated.
        os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        try:
            if created:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
        finally:
            os.close(directory)


def pause_requested():
    directory = _open_directory(OUT, private=True)
    try:
        return _check_target(directory, PAUSE.name)
    finally:
        os.close(directory)


def pause_if_requested():
    announced = False
    while pause_requested():
        if not announced:
            write_json(STATUS, {'state': 'paused', 'pid': os.getpid(), 'time': time.time()}, private=True)
            print('PAUSED: no browser/helper remains in flight', flush=True)
            announced = True
        time.sleep(0.25)
    if announced:
        print('RESUMED', flush=True)


def extract(source):
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'self_test')
    found = []
    for parent in ast.walk(fn):
        for field in ('body', 'orelse', 'finalbody'):
            body = getattr(parent, field, None)
            if not isinstance(body, list):
                continue
            for i, node in enumerate(body):
                if isinstance(node, ast.For) and isinstance(node.iter, ast.Call) \
                        and isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'enumerate' \
                        and any(isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == '_Case'
                                and len(x.args) > 1 and isinstance(x.args[1], ast.Constant) and x.args[1].value == 'hang'
                                for x in ast.walk(node)):
                    assert isinstance(body[i + 1], ast.If)
                    found.append([node, body[i + 1]])
    assert len(found) == 1, 'hang controller must be uniquely identified from tracked source'
    definitions = [n for n in fn.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('code_of', 'expect_code', 'pids_of')]
    assert len(definitions) == 3
    nodes = definitions + found[0]
    code = compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(nodes), type_ignores=[])),
                   'exact-tracked-hang-controller', 'exec')
    schedule = ast.literal_eval(found[0][0].iter.args[0])
    digest = hashlib.sha256(ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False).encode()).hexdigest()
    return {'code': code, 'schedule': schedule, 'ast_sha256': digest}


def real_verdict():
    tree = ast.parse((REPO / 'scripts/operator_headless.py').read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('gate_verdict', '_print_chrome_stderr')]
    nodes += [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_RESULTS_RE' for t in n.targets)]
    assert len(nodes) == 3
    ns = dict(h.__dict__, headless_chrome=h)
    exec(compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(nodes), type_ignores=[])),
                 'exact-tracked-gate-verdict', 'exec'), ns)
    return ns['gate_verdict']


def run_sample(label, controller, verdict, delay=0, wrong_timeout=False):
    pause_if_requested()
    attempts = []
    root = tempfile.mkdtemp(prefix='headless-schedule-')
    started = time.perf_counter()
    ns = dict(h.__dict__, root=root, spawned=[], problems=[], expected_checks=3,
              verdict=verdict, name='hung browser')

    class MeasuredCase(h._Case):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if delay:
                src = h._FAKE_CHROME_SRC.replace('KIND = CFG["kind"]',
                                               'KIND = CFG["kind"]\ntime.sleep(%r)' % delay, 1)
                assert src != h._FAKE_CHROME_SRC
                Path(self.script).write_text(src)

        def run(self, *args, **kwargs):
            pause_if_requested()
            write_json(STATUS, {'state': 'running', 'label': label, 'pid': os.getpid(), 'time': time.time()}, private=True)
            before = time.perf_counter()
            result = super().run(*args, **kwargs)
            pids = {key: h._read_pid(self.pid_dir, key) for key in ('self', 'helper')}
            attempts.append({'timeout_s': kwargs['timeout'], 'wall_s': time.perf_counter() - before,
                             'run_elapsed_s': result.elapsed, 'timed_out': result.timed_out,
                             'complete_block': 'RESULTS' in result.stdout, 'pids': pids,
                             'leftovers': self.leftovers(),
                             'alive': {key: h._pid_alive(pid) for key, pid in pids.items() if pid is not None}})
            return result._replace(timed_out=False) if wrong_timeout else result

    ns['_Case'] = MeasuredCase
    try:
        exec(controller['code'], ns)
        sample = {'label': label, 'wall_s': time.perf_counter() - started,
                  'loadavg': list(os.getloadavg()), 'schedule_s': list(controller['schedule']),
                  'attempts': attempts, 'problems': list(ns['problems']),
                  'startup_retries': len(attempts) - 1,
                  'terminal_flake': bool(ns['problems']), 'synthetic_delay_s': delay,
                  'wrong_timeout_injected': wrong_timeout}
        assert all(not a['leftovers'] and not any(a['alive'].values()) for a in attempts), sample
        print(json.dumps(sample), flush=True)
        return sample
    finally:
        h._kill_recorded(ns['spawned'])
        shutil.rmtree(root, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs', type=int, default=20)
    parser.add_argument('--controls', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(os.path.abspath(args.output))
    validate_output(output)  # Refuse planted links/unsafe parents before any sample.
    print('CONTROL_DIRECTORY=' + str(OUT), flush=True)
    baseline_source = subprocess.check_output(['git', 'show', BASE + ':scripts/headless_chrome.py'], cwd=REPO, text=True)
    candidate_source = (REPO / 'scripts/headless_chrome.py').read_text()
    # The scoped before/after comparison may share the live implementation only when all
    # launcher/fixture/PID primitives are AST-identical to the frozen baseline.
    names = {'_Case', 'run_headless_chrome', '_kill_recorded', '_wait_dead', '_read_pid', '_pid_alive'}
    def primitives(source):
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(source).body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names}
    primitives_match = primitives(baseline_source) == primitives(candidate_source)
    if not args.controls:
        assert primitives_match, ('paired comparison requires launcher/fixture/PID primitives '
                                  'identical to the original baseline; use its frozen study revision')
    baseline, candidate = extract(baseline_source), extract(candidate_source)
    verdict = real_verdict()
    data = {'base': BASE, 'scope': 'exact source-linked hang controller, actual Case/launcher/PID/temp and real verdict checks; not full16CLI repeated',
            'baseline_ast': baseline['ast_sha256'], 'candidate_ast': candidate['ast_sha256'],
            'mode': 'current-source functional controls' if args.controls else 'paired original-baseline comparison',
            'candidate_source_sha256': hashlib.sha256(candidate_source.encode()).hexdigest(),
            'measurement_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'original_baseline_primitives_match': primitives_match,
            'pairs': [], 'controls': [], 'samples_started_at': time.time()}
    try:
        if args.controls:
            for delay, expected in ((1.5, [1, 3]), (4.0, [1, 3, 20])):
                sample = run_sample('forced-startup-delay', candidate, verdict, delay=delay)
                data['controls'].append(sample)
                assert not sample['problems'] and [a['timeout_s'] for a in sample['attempts']] == expected, sample
            wrong = run_sample('incorrect-timeout-verdict', candidate, verdict, wrong_timeout=True)
            data['controls'].append(wrong)
            assert wrong['problems'] and any('not reported as timed out' in p for p in wrong['problems']), wrong
            print('PASS forced3/20 fallbacks and expectedRED incorrect timeout result', flush=True)
        else:
            for i in range(args.pairs):
                samples = {}
                for label in (('baseline', 'candidate') if i % 2 == 0 else ('candidate', 'baseline')):
                    sample = run_sample(label, baseline if label == 'baseline' else candidate, verdict)
                    samples[label] = sample
                    assert not sample['problems'], sample
                samples['pair'] = i + 1
                samples['saving_s'] = samples['baseline']['wall_s'] - samples['candidate']['wall_s']
                data['pairs'].append(samples)
            data['median_paired_saving_s'] = statistics.median(p['saving_s'] for p in data['pairs'])
            assert data['median_paired_saving_s'] >= 1.5, data['median_paired_saving_s']
            print('PASS median paired saving %.3fs' % data['median_paired_saving_s'], flush=True)
    finally:
        data['samples_finished_at'] = time.time()
        write_json(output, data)
        write_json(STATUS, {'state': 'finished', 'pid': os.getpid(), 'time': time.time()}, private=True)


if __name__ == '__main__':
    main()
