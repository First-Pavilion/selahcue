#!/usr/bin/env python3
"""Verify all-root Rust CI auditing/policy and exercise real Cargo alias resolution.

The self-test uses real Cargo plus disposable sentinel audit/deny binaries, never
an advisory service, production artifact or live GitHub issue. Normal mode only
reads the committed workflow and git-derived Cargo roots.
"""
from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import yaml

from check_dependency_audit_coverage import discover_required_roots

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / '.github/workflows/ci.yml'
COMMANDS = {'audit': 'cargo-audit audit', 'supply-chain': 'cargo-deny check licenses sources bans'}


def load_workflow():
    return yaml.safe_load(CI.read_text())


def matching_steps(job, root, command):
    return [step for step in job.get('steps', [])
            if step.get('working-directory') == root and step.get('run', '').strip() == command]


def problems(workflow, roots):
    found = []
    jobs = workflow['jobs']
    for name, command in COMMANDS.items():
        job = jobs[name]
        if job.get('runs-on') != 'ubuntu-latest' or not 1 <= job.get('timeout-minutes', 0) <= 15:
            found.append(f'{name}: require bounded Ubuntu execution (1..15 minutes)')
        if job.get('permissions') != {'contents': 'read'}:
            found.append(f'{name}: require contents:read only')
        if job.get('continue-on-error') or job.get('if') != "needs.changes.outputs.desktop == 'true'":
            found.append(f'{name}: preserve desktop/weekly gate without masking failures')
        checkouts = [s for s in job['steps'] if str(s.get('uses', '')).split('@')[0] == 'actions/checkout']
        if len(checkouts) != 1 or checkouts[0].get('with', {}).get('persist-credentials') is not False:
            found.append(f'{name}: checkout must not persist credentials')
        for root in sorted(roots):
            steps = matching_steps(job, root, command)
            if len(steps) != 1 or any(key in steps[0] for key in ('if', 'continue-on-error')):
                found.append(f'{name}: {root} needs exactly one unmasked `{command}` step')
    events = workflow.get('on', workflow.get(True, {}))
    if events.get('schedule') != [{'cron': '17 3 * * 0'}]:
        found.append('weekly: preserve the existing Sunday03:17UTC schedule, do not duplicate it')
    alarm = jobs['ci-alarm']
    if not {'audit', 'supply-chain'} <= set(alarm.get('needs', [])):
        found.append('weekly: alarm must track audit and supply-chain outcomes')
    alarm_if = alarm.get('if', '')
    if 'always()' not in alarm_if or "github.event_name == 'schedule'" not in alarm_if:
        found.append('weekly: failures must reach the existing schedule/always alarm')
    return found


def alias_probes(workflow, roots):
    cargo = shutil.which('cargo')
    if not cargo:
        raise AssertionError('real Cargo is required for the alias regression; refusing to skip')
    checks = 0
    with tempfile.TemporaryDirectory(prefix='rust-ci-alias-') as directory:
        fixture = Path(directory)
        binaries = fixture / 'bin'
        binaries.mkdir()
        cargo_home = fixture / 'cargo-home'
        cargo_home.mkdir()
        for binary in ('cargo-audit', 'cargo-deny'):
            path = binaries / binary
            path.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$RUST_CI_SENTINEL"\nexit "$RUST_CI_EXIT"\n')
            path.chmod(0o755)
        for name, command in COMMANDS.items():
            action = 'audit' if name == 'audit' else 'deny'
            job = workflow['jobs'][name]
            for root in sorted(roots):
                candidates = [step for step in job['steps']
                              if step.get('working-directory') == root
                              and str(step.get('run', '')).strip().startswith(('cargo audit', 'cargo-audit', 'cargo deny', 'cargo-deny'))]
                if len(candidates) != 1:
                    raise AssertionError(f'{name}/{root}: no unique actual CI command for alias probe')
                run = candidates[0]['run']
                working = fixture / root
                (working / '.cargo').mkdir(parents=True, exist_ok=True)
                config = working / '.cargo/config.toml'
                marker = fixture / 'calls.log'
                for mode in ('repository alias', 'environment alias', 'forged auditor identity'):
                    config.write_text('[alias]\n' + action + ' = "version"\n')
                    env = dict(os.environ, CARGO_HOME=str(cargo_home), PATH=str(binaries) + os.pathsep + os.environ['PATH'], RUST_CI_SENTINEL=str(marker))
                    env.pop('CARGO_ALIAS_AUDIT', None)
                    env.pop('CARGO_ALIAS_DENY', None)
                    if mode == 'environment alias':
                        config.unlink()
                        env['CARGO_ALIAS_' + action.upper()] = 'version'
                    elif mode == 'forged auditor identity':
                        config.write_text('[alias]\n' + action + ' = "!printf cargo-audit-fake"\n')
                    # Confirm an actual Cargo dispatch sees the configured alias. A future
                    # Cargo may reject shadowing; it must never invoke our sentinel here.
                    marker.unlink(missing_ok=True)
                    baseline = subprocess.run([cargo, action], cwd=working, env=dict(env, RUST_CI_EXIT='23'), capture_output=True, text=True, timeout=30)
                    if marker.exists() or 'alias' not in (baseline.stdout + baseline.stderr).lower():
                        raise AssertionError(f'{mode}: actual Cargo did not observe the alias: {baseline.stdout}{baseline.stderr}')
                    for status in (0, 23):
                        marker.unlink(missing_ok=True)
                        result = subprocess.run(['sh', '-ec', run], cwd=working, env=dict(env, RUST_CI_EXIT=str(status)), capture_output=True, text=True, timeout=30)
                        expected = str(binaries / command.split()[0]) + ' ' + ' '.join(command.split()[1:])
                        if result.returncode != status or not marker.exists() or marker.read_text().strip() != expected:
                            raise AssertionError(f'{name}/{root}/{mode}: alias replaced actual CI auditor or masked status {status}; exit {result.returncode}, invoked={marker.exists()}, output={result.stdout}{result.stderr}')
                        checks += 1
    return checks


def self_test(workflow, roots):
    # A positive policy fixture and actual command mutations prove the shape checker
    # rejects root removal, masking, token widening and scheduled-alarm loss.
    good = copy.deepcopy(workflow)
    for name, command in COMMANDS.items():
        job = good['jobs'][name]
        job.update(permissions={'contents': 'read'}, **{'timeout-minutes': 10})
        for checkout in [s for s in job['steps'] if str(s.get('uses', '')).startswith('actions/checkout@')]:
            checkout.setdefault('with', {})['persist-credentials'] = False
        job['steps'] = [s for s in job['steps'] if not (s.get('working-directory') in roots and str(s.get('run', '')).startswith(('cargo audit', 'cargo-audit', 'cargo deny', 'cargo-deny')))]
        job['steps'] += [{'name': f'Fixture {root}', 'working-directory': root, 'run': command} for root in sorted(roots)]
    assert problems(good, roots) == [], problems(good, roots)
    mutations = [
        ('restore cargo alias dispatch', lambda w: w['jobs']['audit']['steps'][-1].update(run='cargo audit')),
        ('mask audit failure', lambda w: w['jobs']['audit']['steps'][-1].update(run='cargo-audit audit || true')),
        ('drop required deny root', lambda w: w['jobs']['supply-chain']['steps'].pop()),
        ('skip policy', lambda w: w['jobs']['supply-chain']['steps'][-1].update(**{'if': 'false'})),
        ('widen token', lambda w: w['jobs']['audit'].update(permissions={'contents': 'write'})),
        ('unbounded job', lambda w: w['jobs']['audit'].pop('timeout-minutes')),
        ('drop schedule', lambda w: w.get('on', w.get(True)).pop('schedule')),
        ('hide audit from alarm', lambda w: w['jobs']['ci-alarm']['needs'].remove('audit')),
    ]
    for label, mutate in mutations:
        changed = copy.deepcopy(good)
        mutate(changed)
        assert problems(changed, roots), f'CI mutation passed: {label}'
    count = alias_probes(workflow, roots)
    print(f'Rust supply CI self-test: {len(mutations)} rejected policy mutations; {count} actual CI alias/status probes passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    roots = discover_required_roots(ROOT)
    workflow = load_workflow()
    if args.self_test:
        self_test(workflow, roots)
        return 0
    findings = problems(workflow, roots)
    for finding in findings:
        print(finding, file=sys.stderr)
    if not findings:
        print(f'Rust supply CI: all {len(roots)} roots use actual auditors and weekly alarm is preserved')
    return bool(findings)


if __name__ == '__main__':
    raise SystemExit(main())
