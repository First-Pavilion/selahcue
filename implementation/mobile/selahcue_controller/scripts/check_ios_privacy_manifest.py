#!/usr/bin/env python3
"""Verify Runner actually copies its existing privacy manifest, rather than merely listing it.

Run on macOS from any directory. This checks the native project graph, not a
compiled archive or the accuracy of privacy declarations for bundled plugins.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def runner_manifest_path(project):
    objects = project['objects']
    runner = next(obj for obj in objects.values()
                  if obj.get('isa') == 'PBXNativeTarget' and obj.get('name') == 'Runner')
    runner_groups = [obj for obj in objects.values()
                     if obj.get('isa') == 'PBXGroup' and obj.get('path') == 'Runner']
    for phase_id in runner['buildPhases']:
        phase = objects[phase_id]
        if phase.get('isa') != 'PBXResourcesBuildPhase':
            continue
        for build_id in phase.get('files', []):
            reference_id = objects[build_id].get('fileRef')
            reference = objects.get(reference_id, {})
            if reference.get('path') != 'PrivacyInfo.xcprivacy':
                continue
            if reference.get('sourceTree') != '<group>':
                continue
            if any(reference_id in group.get('children', []) for group in runner_groups):
                return Path('Runner/PrivacyInfo.xcprivacy')
    raise ValueError('Runner Copy Bundle Resources does not include Runner/PrivacyInfo.xcprivacy')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1]
                        / 'ios/Runner.xcodeproj/project.pbxproj')
    args = parser.parse_args()
    converted = subprocess.run(['plutil', '-convert', 'json', '-o', '-', str(args.project)],
                               check=True, capture_output=True, text=True)
    path = runner_manifest_path(json.loads(converted.stdout))
    print(f'PASS: Runner Copy Bundle Resources includes {path}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, StopIteration, subprocess.CalledProcessError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
