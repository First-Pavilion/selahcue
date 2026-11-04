#!/usr/bin/env python3
"""Check literal operator lint parity without executing repository workflow code.

CI is the baseline. The actual installer command adds its release/default-feature
configuration. The canary shell is intentionally a narrow, reviewable grammar;
unknown command spellings fail rather than silently deleting required coverage.
"""
from __future__ import annotations
import argparse
import copy
import re
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import tempfile
import os
import yaml

ROOT = Path(__file__).resolve().parent.parent
OPERATOR = PurePosixPath('implementation/desktop/crates/selahcue-operator')
# These are additional opt-in configurations, not substitutes for actual CI or
# the installer. No-default-features is deliberately not shipped: encryption is
# default-on. cloud-live is opt-in pending its desktop/server delivery slice.
NON_SHIPPED = {'cloud-live': 'Opt-in desktop cloud integration; not requested by the installer.',
               'pilot-credentials': 'Opt-in gated pilot package, absent from this installer/CI.',
               '--no-default-features': 'Not shipped; installer retains encryption defaults.'}


def configuration(command):
    args = shlex.split(command)
    if args[:2] != ['cargo', 'clippy']:
        raise ValueError('expected a literal cargo clippy command')
    if args[-3:] != ['--', '-D', 'warnings']:
        raise ValueError('clippy must deny warnings explicitly')
    features, profile, defaults = (), 'debug', True
    index = 2
    seen = set()
    while index < len(args) - 3:
        value = args[index]
        if value in seen:
            raise ValueError('duplicate clippy option: ' + value)
        seen.add(value)
        if value == '--features':
            index += 1
            features = tuple(sorted(set(args[index].split(','))))
        elif value == '--release':
            profile = 'release'
        elif value == '--no-default-features':
            defaults = False
        elif value not in {'--all-targets', '--locked'}:
            raise ValueError('unsupported clippy option: ' + value)
        index += 1
    if '--all-targets' not in args:
        raise ValueError('operator clippy must check all targets')
    return profile, defaults, features


def ci_configurations(ci):
    result = set()
    jobs_seen = set()
    for name, job in ci['jobs'].items():
        default = job.get('defaults', {}).get('run', {}).get('working-directory')
        for step in job.get('steps', []):
            directory = step.get('working-directory', default)
            if directory != str(OPERATOR):
                continue
            command = step.get('run', '').strip()
            executable = '\n'.join(line for line in command.splitlines() if not line.lstrip().startswith('#'))
            if re.search(r'\bcargo\s+clippy\b', executable) and not command.startswith('cargo clippy'):
                raise ValueError(name + ': wrapped clippy command needs explicit review')
            if command.startswith('cargo clippy'):
                result.add(configuration(command))
                jobs_seen.add(name)
    if not {'operator', 'operator-native'} <= jobs_seen:
        raise ValueError('missing the existing operator/operator-native literal lint jobs')
    return result


def gate_lines(gates):
    """Only fixed local directory/aggregate syntax and inert Cargo argv may execute in tests."""
    fixed = {'set -x', 'fail=0', 'exit $fail', 'cd implementation/desktop',
             'cd crates/selahcue-operator', 'cargo fmt --check || fail=1'}
    for raw in gates['run'].splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line not in fixed and not (line.startswith('cargo clippy ') and
                re.fullmatch(r'[A-Za-z0-9_,/ .-]+ \|\| fail=1', line)):
            raise ValueError('unsupported canary shell command; review before executing a fixture: ' + line)
        yield line


def canary_configurations(canary):
    job = canary['jobs']['canary']
    if job['env'].get('RUSTUP_TOOLCHAIN') != 'stable':
        raise ValueError('canary must float with RUSTUP_TOOLCHAIN=stable')
    gates = next(step for step in job['steps'] if step.get('id') == 'gates')
    if gates.get('continue-on-error') is not True:
        raise ValueError('canary must reach the existing report after lint failure')
    directory = PurePosixPath('.')
    configurations = set()
    for line in gate_lines(gates):
        if line.startswith('cd '):
            relative = PurePosixPath(shlex.split(line)[1])
            directory = relative if str(directory) == '.' else directory / relative
        if line.startswith('cargo clippy') and directory == OPERATOR:
            if not line.endswith(' || fail=1'):
                raise ValueError('every operator gate must preserve aggregate failure')
            configurations.add(configuration(line[:-10]))
    if 'exit $fail' not in gates['run'].splitlines():
        raise ValueError('canary must return the aggregate failure')
    return configurations


def shipping_configuration(installer):
    commands = [step['run'].strip() for job in installer['jobs'].values()
                for step in job.get('steps', []) if step.get('run', '').strip().startswith('cargo tauri build')]
    if len(commands) != 1:
        raise ValueError('expected one explicit Tauri installer command')
    args = shlex.split(commands[0])
    if args != ['cargo', 'tauri', 'build', '--features', 'stt']:
        raise ValueError('installer changed; review its feature/profile disposition')
    # cargo tauri build uses release unless --debug, absent in the verified command.
    return 'release', True, ('stt',)


def problems(ci, canary, installer):
    required = ci_configurations(ci) | {shipping_configuration(installer)}
    covered = canary_configurations(canary)
    result = [f'canary missing operator configuration: {item}' for item in sorted(required - covered)]
    job = canary['jobs']['canary']
    setup = '\n'.join(step.get('run', '') for step in job['steps'] if 'apt-get install' in step.get('run', ''))
    for package in ('cmake', 'libasound2-dev'):
        if package not in shlex.split(setup.replace('\\\n', ' ')):
            result.append('canary native setup missing ' + package)
    events = canary.get('on', canary.get(True))
    if set(events) != {'schedule', 'workflow_dispatch'}:
        result.append('canary must remain scheduled/manual only')
    if any(not item[1] or set(item[2]) & set(NON_SHIPPED) for item in covered):
        result.append('new opt-in canary configuration needs an explicit disposition')
    return result


def self_test(ci, canary, installer):
    assert problems(ci, canary, installer) == [], problems(ci, canary, installer)
    gates = next(step for step in canary['jobs']['canary']['steps'] if step.get('id') == 'gates')
    lines = [line for line in gates['run'].splitlines() if line.strip().startswith('cargo clippy')]
    operator_lines = lines[-len(canary_configurations(canary)):]
    count = 0
    for line in operator_lines:
        mutant = copy.deepcopy(canary)
        target = next(step for step in mutant['jobs']['canary']['steps'] if step.get('id') == 'gates')
        target['run'] = target['run'].replace(line + '\n', '', 1)
        assert problems(ci, mutant, installer), 'removed actual gate passed: ' + line
        count += 1
    for package in ('cmake', 'libasound2-dev'):
        mutant = copy.deepcopy(canary)
        for step in mutant['jobs']['canary']['steps']:
            if 'apt-get install' in step.get('run', ''):
                step['run'] = step['run'].replace(package, '')
        assert problems(ci, mutant, installer), 'missing native package passed'
        count += 1
    # Exercise profile/toolchain/continuation drift, not just labels.
    for old, new in (
        ('--features stt --release', '--features stt'),
        ('cargo clippy --features stt --all-targets -- -D warnings || fail=1',
         'cargo clippy --features stt --all-targets -- -D warnings'),
        ('exit $fail', 'exit 0'),
    ):
        mutant = copy.deepcopy(canary)
        target = next(step for step in mutant['jobs']['canary']['steps'] if step.get('id') == 'gates')
        assert old in target['run']
        target['run'] = target['run'].replace(old, new)
        try:
            refused = bool(problems(ci, mutant, installer))
        except ValueError:
            refused = True
        assert refused, 'unsafe profile/continuation mutation passed'
        count += 1
    mutant = copy.deepcopy(canary)
    mutant['jobs']['canary']['env']['RUSTUP_TOOLCHAIN'] = '1.98.0'
    try:
        problems(ci, mutant, installer)
    except ValueError:
        count += 1
    else:
        raise AssertionError('pinned canary passed')
    mutant = copy.deepcopy(canary)
    target = next(step for step in mutant['jobs']['canary']['steps'] if step.get('id') == 'gates')
    target['run'] = 'printf unexpected-command\n' + target['run']
    try:
        problems(ci, mutant, installer)
    except ValueError:
        count += 1
    else:
        raise AssertionError('arbitrary shell command reached fixture execution')
    mutant_ci = copy.deepcopy(ci)
    mutant_ci['jobs']['new-operator-profile'] = {
        'steps': [{'working-directory': str(OPERATOR),
                   'run': 'cargo clippy --features stt,dev-keys --all-targets -- -D warnings'}]}
    assert problems(mutant_ci, canary, installer), 'new CI operator job was invisible'
    count += 1
    # Execute the exact production gates block under a local sentinel cargo. This
    # checks real shell continuation/exit rather than matching a label or comment.
    with tempfile.TemporaryDirectory(prefix='canary-gates-') as directory:
        root = Path(directory)
        (root / OPERATOR).mkdir(parents=True)
        binary = root / 'cargo'
        binary.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CANARY_CALLS"\ncase "$*" in *"--features stt,cloud-stt"*) exit "$CANARY_FAIL";; esac\nexit 0\n')
        binary.chmod(0o755)
        for expected in (0, 23):
            calls = root / 'calls'
            calls.unlink(missing_ok=True)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'], CANARY_CALLS=str(calls), CANARY_FAIL=str(expected))
            result = subprocess.run(['sh', '-c', gates['run']], cwd=root, env=env, capture_output=True, text=True, timeout=30)
            assert result.returncode == (1 if expected else 0), result.stderr
            invoked = calls.read_text().splitlines()
            assert 'clippy --features stt --release --all-targets -- -D warnings' in invoked, 'a failed earlier gate hid shipped release STT'
            assert sum(line.startswith('clippy ') for line in invoked) == len(lines)
    print(f'canary coverage self-test: {count} actual configuration drift controls and 2 real shell outcome probes pass')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    documents = [yaml.safe_load((ROOT / '.github/workflows' / name).read_text()) for name in ('ci.yml', 'rust-canary.yml', 'windows-installer.yml')]
    if args.self_test:
        self_test(*documents)
        return 0
    try:
        findings = problems(*documents)
    except (ValueError, KeyError, StopIteration, IndexError) as error:
        print('canary coverage invalid: ' + str(error))
        return 1
    for finding in findings:
        print(finding)
    if not findings:
        print(f'canary covers {len(canary_configurations(documents[1]))} operator feature/profile configurations including shipped release STT')
    return bool(findings)


if __name__ == '__main__':
    raise SystemExit(main())
