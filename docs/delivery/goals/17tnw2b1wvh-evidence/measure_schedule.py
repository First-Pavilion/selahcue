import argparse
import ast
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[4]
OUT = Path(tempfile.gettempdir()) / 'selahcue-launcher-schedule'
OUT.mkdir(exist_ok=True)
BASE = '8f7d610ef81efc4c7359e9b3cb6d9d44fb99c56e'
PAUSE = OUT / '17tnw2b1wvh-measurement.pause'
STATUS = OUT / '17tnw2b1wvh-measurement-status.json'
sys.path.insert(0, str(REPO / 'scripts'))
import headless_chrome as h


def pause_if_requested():
    announced = False
    while PAUSE.exists():
        if not announced:
            STATUS.write_text(json.dumps({'state': 'paused', 'pid': os.getpid(), 'time': time.time()}))
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
            STATUS.write_text(json.dumps({'state': 'running', 'label': label, 'pid': os.getpid(), 'time': time.time()}))
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
        Path(args.output).write_text(json.dumps(data, indent=2))
        STATUS.write_text(json.dumps({'state': 'finished', 'pid': os.getpid(), 'time': time.time()}))


if __name__ == '__main__':
    main()
