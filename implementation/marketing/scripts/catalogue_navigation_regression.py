#!/usr/bin/env python3
"""Actual WebKit768 helper restoration control; production styles/viewport stay untouched."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

MARKETING = Path(__file__).resolve().parent.parent
MATRIX = MARKETING / 'tests/catalogue_plans_headless.py'
VISIBLE = 'elif page.get_by_role("button", name="Menu", exact=True).is_visible():'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = MATRIX.read_text()
    assert source.count(VISIBLE) == 1, 'changed helper anchor; refusing vacuous restoration proof'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    prefix = args.output.parent / args.output.stem
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(MATRIX.parent) + (os.pathsep + environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
    def run(script, name):
        output = Path(str(prefix) + '-' + name + '.json')
        result = subprocess.run([sys.executable, str(script), '--engine', 'webkit', '--paths', '/', '--widths', '768', '--output', str(output)], cwd=MARKETING, env=environment, capture_output=True, text=True, timeout=120)
        Path(str(prefix) + '-' + name + '.log').write_text(result.stdout + result.stderr)
        return result, output
    with tempfile.TemporaryDirectory(prefix='catalogue-old-helper-') as directory:
        old = Path(directory) / 'old_helper_matrix.py'
        old.write_text(source.replace(VISIBLE, 'elif width < 768:'))
        rejected, negative_output = run(old, 'old-nominal')
    diagnostic = json.loads(negative_output.with_suffix('.diagnostic.json').read_text())
    assert rejected.returncode == 1, rejected.stdout + rejected.stderr
    assert diagnostic['scenario'] == 'webkit / 768px', diagnostic
    assert '.desktop-nav' in diagnostic['error'] and 'not visible' in diagnostic['error'], diagnostic
    assert diagnostic['requests'] == 1 and diagnostic['held'] == 0, diagnostic
    passed, positive_output = run(MATRIX, 'visible-controls')
    assert passed.returncode == 0, passed.stdout + passed.stderr
    positive = json.loads(positive_output.read_text())
    assert positive['result'] == 'PASS' and len(positive['scenarios']) == 1, positive
    assert MATRIX.read_text() == source, 'production matrix source changed during proof'
    args.output.write_text(json.dumps({'negative': {'result': 'EXPECTED_REJECTION', 'exit': rejected.returncode, 'scenario': diagnostic['scenario'], 'reason': 'restored nominal-width helper selects hidden desktop link after actual API cards are ready'}, 'positive': {'result': 'PASS', 'checks': positive['checks'], 'scenarios': positive['scenarios']}, 'scope': 'real unchanged production bundle/native UI; no force click, viewport/CSS/breakpoint/tolerance change'}, indent=2) + '\n')
    print('PASS actual WebKit768: old nominal helper rejected; visible native controls passed', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
