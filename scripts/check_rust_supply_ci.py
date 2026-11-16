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
import subprocess
import sys
import tempfile

import yaml

from check_dependency_audit_coverage import discover_required_roots

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / '.github/workflows/ci.yml'
NATIVE_ROOT = 'scripts/fixtures/macos-native-proof/payloads/native-golden'
NATIVE_STAGE = '${{ runner.temp }}/selahcue-native-supply/adapter'
NATIVE_DENY = 'cargo-deny --locked --manifest-path Cargo.toml --config deny.toml check licenses sources bans'
NATIVE_STEPS = [
    {'name': 'Prepare frozen native dependency mirror', 'id': 'native-supply-prepare', 'timeout-minutes': 3,
     'run': 'python3 scripts/prepare_native_supply_check.py prepare'},
    {'name': 'License / source / bans policy (frozen native adapter)', 'id': 'native-supply-deny', 'timeout-minutes': 5,
     'working-directory': NATIVE_STAGE,
     'env': {'CARGO_HOME': '${{ runner.temp }}/selahcue-native-supply/cargo',
             'CARGO_TARGET_DIR': '${{ runner.temp }}/selahcue-native-supply/target', 'RUSTUP_TOOLCHAIN': '1.98.0'},
     'run': NATIVE_DENY},
    {'name': 'Verify frozen native audit inputs after deny', 'id': 'native-supply-postcheck', 'timeout-minutes': 1,
     'run': 'python3 scripts/prepare_native_supply_check.py postcheck'},
    {'name': 'Clean owned native dependency mirror', 'id': 'native-supply-cleanup', 'if': '${{ always() }}',
     'timeout-minutes': 1, 'run': 'python3 scripts/prepare_native_supply_check.py cleanup'},
]
COMMANDS = {'audit': 'cargo-audit audit', 'supply-chain': 'cargo-deny check licenses sources bans'}


def load_workflow():
    return yaml.safe_load(CI.read_text())


def matching_steps(job, root, command):
    return [step for step in job.get('steps', [])
            if step.get('working-directory') == root and step.get('run', '').strip() == command]



def execution(name, root):
    if name == 'supply-chain' and root == NATIVE_ROOT:
        return NATIVE_STAGE, NATIVE_DENY
    return root, COMMANDS[name]


def native_mirror_problems(job):
    steps = job.get('steps', [])
    identifiers = {step['id'] for step in NATIVE_STEPS}
    candidates = [(index, step) for index, step in enumerate(steps)
                  if (step.get('id') in identifiers
                      or 'prepare_native_supply_check.py' in str(step.get('run', ''))
                      or 'selahcue-native-supply' in str(step.get('working-directory', ''))
                      or step.get('working-directory') == NATIVE_ROOT)]
    if (len(candidates) != 4 or [s for _, s in candidates] != NATIVE_STEPS
            or any(type(s.get('timeout-minutes')) is not int for _, s in candidates)):
        return ['native supply: require the exact unmasked prepare/direct-deny/postcheck/always-cleanup protocol']
    positions = [i for i, _ in candidates]
    if positions != list(range(positions[0], positions[0]+4)):
        return ['native supply: preparation, deny, postcheck and cleanup must be adjacent and ordered']
    checkouts = [i for i,s in enumerate(steps) if str(s.get('uses','')).startswith('actions/checkout@')]
    installs = [i for i,s in enumerate(steps) if (s.get('with') or {}).get('tool') == 'cargo-deny@0.20.2,cargo-cyclonedx']
    if len(checkouts) != 1 or len(installs) != 1 or not checkouts[0] < installs[0] < positions[0]:
        return ['native supply: full-history checkout and pinned tool installation must precede preparation']
    depth = steps[checkouts[0]].get('with', {}).get('fetch-depth')
    if type(depth) is not int or depth != 0:
        return ['native supply: full history required for normative revision']
    if any(k in steps[installs[0]] for k in ('if', 'continue-on-error')):
        return ['native supply: tool installation must not be masked']
    if any(k in job for k in ('env','defaults')):
        return ['native supply: inherited environment/working-directory overrides are forbidden']
    return []

def native_audit_order_problems(job):
    steps = job.get('steps', [])
    frozen = {'name': 'Audit frozen native adapter lock',
              'working-directory': NATIVE_ROOT, 'run': 'cargo-audit audit'}
    audit = [(i,s) for i,s in enumerate(steps)
             if s.get('working-directory') == NATIVE_ROOT or s.get('name') == frozen['name']]
    checkout = [(i,s) for i,s in enumerate(steps) if str(s.get('uses','')).startswith('actions/checkout@')]
    coverage = [(i,s) for i,s in enumerate(steps) if 'check_dependency_audit_coverage.py' in str(s.get('run',''))]
    install = [(i,s) for i,s in enumerate(steps) if (s.get('with') or {}).get('tool') == 'cargo-audit']
    if len(audit) != 1 or audit[0][1] != frozen or any(len(rows) != 1 for rows in (checkout, coverage, install)):
        return ['native audit: one exact audit and each prerequisite required']
    if coverage[0][1] != {'name': 'Verify dependency-audit coverage of every Cargo.lock in the repo',
                          'run': 'python3 scripts/check_dependency_audit_coverage.py'}:
        return ['native audit: exact unmasked coverage precheck required']
    if install[0][1] != {'uses': 'taiki-e/install-action@v2', 'with': {'tool': 'cargo-audit'}}:
        return ['native audit: exact unmasked auditor installation required']
    if any(key in checkout[0][1] for key in ('if', 'continue-on-error', 'env')):
        return ['native audit: checkout prerequisite must be unmasked']
    if not checkout[0][0] < coverage[0][0] < install[0][0] < audit[0][0]:
        return ['native audit: require checkout then coverage then installation before audit']
    return []


def native_lint_toolchain_problems(job):
    steps = job.get('steps', [])
    setups = [(i,s) for i,s in enumerate(steps) if str(s.get('uses','')).startswith('dtolnay/rust-toolchain@')]
    checkouts = [i for i,s in enumerate(steps) if str(s.get('uses','')).startswith('actions/checkout@')]
    controls = [i for i,s in enumerate(steps) if any(command in str(s.get('run',''))
                for command in ('check_rust_supply_ci.py', 'scripts.test_native_supply_check'))]
    expected = {'uses': 'dtolnay/rust-toolchain@stable', 'with': {'toolchain': '1.98.0'}}
    if (len(setups) != 1 or setups[0][1] != expected or len(checkouts) != 1 or not controls
            or not checkouts[0] < setups[0][0] < min(controls)):
        return ['native lint: exact hosted 1.98.0 setup required before alias controls']
    return []


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
            directory, actual_command = execution(name, root)
            steps = matching_steps(job, directory, actual_command)
            if len(steps) != 1 or any(key in steps[0] for key in ('if', 'continue-on-error')):
                found.append(f'{name}: {root} needs exactly one unmasked `{command}` step')
    if NATIVE_ROOT in roots:
        found += native_mirror_problems(jobs['supply-chain'])
        found += native_audit_order_problems(jobs['audit'])
        found += native_lint_toolchain_problems(jobs.get('lint-workflows', {}))
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
    # Resolve the installed toolchain independently of PATH proxy link style.
    rustup_home = Path(os.environ.get('RUSTUP_HOME', str(Path.home() / '.rustup')))
    installed = sorted((rustup_home / 'toolchains').glob('1.98.0-*/bin/cargo'))
    if (len(installed) != 1 or installed[0].is_symlink() or not installed[0].is_file()
            or not os.access(installed[0], os.X_OK)):
        raise AssertionError('one installed direct Cargo 1.98.0 required; no toolchain setup is permitted')
    cargo = str(installed[0].resolve())
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
                directory, selected_command = execution(name, root)
                candidates = [step for step in job['steps']
                              if step.get('working-directory') == directory
                              and str(step.get('run', '')).strip().startswith(('cargo audit', 'cargo-audit', 'cargo deny', 'cargo-deny'))]
                if len(candidates) != 1:
                    raise AssertionError(f'{name}/{root}: no unique actual CI command for alias probe')
                run = candidates[0]['run']
                working = fixture / ('selahcue-native-supply/adapter' if directory == NATIVE_STAGE else root)
                (working / '.cargo').mkdir(parents=True, exist_ok=True)
                config = working / '.cargo/config.toml'
                marker = fixture / 'calls.log'
                for mode in ('repository alias', 'environment alias', 'forged auditor identity'):
                    config.write_text('[alias]\n' + action + ' = "version"\n')
                    env = {'HOME': str(fixture), 'CARGO_HOME': str(cargo_home), 'PATH': str(binaries) + os.pathsep + os.defpath, 'RUST_CI_SENTINEL': str(marker)}
                    # Direct installed Cargo avoids rustup activity and inherited credentials.
                    version = subprocess.run([cargo, '--version'], cwd=working, env=env, capture_output=True, text=True, timeout=5)
                    if version.returncode or not version.stdout.startswith('cargo 1.98.0 '):
                        raise AssertionError('alias probes require the actual installed Cargo 1.98.0')
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
                        expected = str(binaries / selected_command.split()[0]) + ' ' + ' '.join(selected_command.split()[1:])
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
        job['steps'] = [s for s in job['steps'] if not (s.get('working-directory') in roots and s.get('working-directory') != NATIVE_ROOT and str(s.get('run', '')).startswith(('cargo audit', 'cargo-audit', 'cargo deny', 'cargo-deny')))]
        job['steps'] += [{'name': f'Fixture {root}', 'working-directory': root, 'run': command}
                         for root in sorted(roots) if root != NATIVE_ROOT]
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
    assert problems(workflow, roots) == [], problems(workflow, roots)
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
