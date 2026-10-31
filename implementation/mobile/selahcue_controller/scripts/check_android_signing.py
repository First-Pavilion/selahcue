#!/usr/bin/env python3
"""Integration checks; requires Flutter/Android tools. Never uses owner signing secrets."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import secrets

APP = Path(__file__).resolve().parents[1]
NAMES = ('SELAHCUE_UPLOAD_STORE_FILE', 'SELAHCUE_UPLOAD_STORE_PASSWORD',
         'SELAHCUE_UPLOAD_KEY_ALIAS', 'SELAHCUE_UPLOAD_KEY_PASSWORD')


def run(command, env, success, marker=None):
    result = subprocess.run(command, cwd=APP, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for name in (NAMES[1], NAMES[3]):
        value = env.get(name)
        assert not value or value not in result.stdout, 'Signing password appeared in output'
    assert (result.returncode == 0) == success, 'Unexpected build result: ' + result.stdout[-4000:]
    assert marker is None or marker in result.stdout, 'Expected safe signing diagnostic absent: ' + result.stdout[-4000:]
    print('PASS:', ' '.join(command[:3]), marker or 'expected exit status', flush=True)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['missing', 'partial', 'malformed', 'wrong-password', 'debug', 'fixture'], required=True)
    args = parser.parse_args()
    env = dict(os.environ)
    for name in NAMES:
        env.pop(name, None)
    command = ['flutter', 'build', 'appbundle', '--release', '--no-pub']
    if args.case == 'missing':
        run(command, env, False, 'Upload signing configuration is incomplete')
    elif args.case == 'partial':
        env[NAMES[1]] = secrets.token_hex(20)
        run(command, env, False, 'Upload signing configuration is incomplete')
    elif args.case == 'debug':
        run(['flutter', 'build', 'apk', '--debug', '--no-pub'], env, True)
    else:
        with tempfile.TemporaryDirectory(prefix='selahcue-signing-test-') as folder:
            store = Path(folder) / 'fixture.jks'
            password = secrets.token_hex(20)
            env.update(dict(zip(NAMES, (str(store), password, 'fixture-upload', password))))
            if args.case == 'malformed':
                store.write_text('deliberately invalid test keystore')
                run(command, env, False, 'signReleaseBundle')
            else:
                java = Path(env['JAVA_HOME']) / 'bin'
                run([str(java / 'keytool'), '-genkeypair', '-noprompt', '-keystore', str(store),
                     '-storepass:env', NAMES[1], '-keypass:env', NAMES[3], '-alias', 'fixture-upload',
                     '-dname', 'CN=Disposable SelahCue Test Only', '-keyalg', 'RSA', '-validity', '2'], env, True)
                if args.case == 'wrong-password':
                    env[NAMES[3]] = secrets.token_hex(20)
                    run(command, env, False, 'signReleaseBundle')
                    return
                run(command, env, True)
                bundle = APP / 'build/app/outputs/bundle/release/app-release.aab'
                run([str(java / 'jarsigner'), '-verify', str(bundle)], env, True, 'jar verified.')
                certificate = run([str(java / 'keytool'), '-printcert', '-jarfile', str(bundle)], env, True)
                expected = run([str(java / 'keytool'), '-list', '-v', '-keystore', str(store),
                                '-storepass:env', NAMES[1]], env, True)
                actual_sha = next(line.strip() for line in certificate.splitlines() if 'SHA256:' in line)
                assert actual_sha in expected, 'Bundle certificate differs from fixture upload identity'
                assert 'CN=Disposable SelahCue Test Only' in certificate
                bundle.unlink()
                print('PASS: AAB certificate matches disposable upload key; test AAB removed')


if __name__ == '__main__':
    main()
