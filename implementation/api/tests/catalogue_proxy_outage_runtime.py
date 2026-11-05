#!/usr/bin/env python3
"""Actual nginx outage controls on a disposable Docker network (Linux CI).

Run from repository root. No application secrets or production endpoints are used.
The old-config DNS control preserves the original 30-second client deadline.
"""
import json
from pathlib import Path
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / 'implementation/marketing/nginx.conf'
IMAGE = 'nginx:alpine'  # Same base as the shipping marketing Dockerfile; record resolved ID.
TIMEOUTS = ('resolver_timeout 2s;', 'proxy_connect_timeout 2s;',
            'proxy_send_timeout 5s;', 'proxy_read_timeout 5s;')


def command(args, *, timeout=60):
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{args[:3]} exited {result.returncode}: {result.stderr[-2000:]}')
    return result.stdout.strip()


def fetch(url, *, timeout=30):
    started = time.monotonic()
    try:
        response = urllib.request.urlopen(url, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    except (TimeoutError, socket.timeout, urllib.error.URLError) as error:
        return dict(elapsed=time.monotonic()-started, error=type(error).__name__)
    with response:
        return dict(status=response.status, elapsed=time.monotonic()-started,
                    headers=dict(response.headers), body=response.read().decode())


def assert_unavailable(result):
    assert result.get('status') == 503, result
    assert json.loads(result['body']) == {'error': {'code': 'catalogue_unavailable'}}, result
    assert result['headers']['Cache-Control'] == 'no-store', result
    assert 'Content-Security-Policy' in result['headers'], result
    assert result['elapsed'] < 8, result


class SilentDNS(socketserver.ThreadingUDPServer):
    allow_reuse_address = True


class DropDNS(socketserver.BaseRequestHandler):
    def handle(self):
        pass  # Controlled resolver outage: receive a packet and deliberately never reply.


class StalledHTTP(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.recv(8192)
        time.sleep(7)


def main():
    suffix = uuid.uuid4().hex[:12]
    network = 'catalogue-outage-' + suffix
    containers = []
    results = {}
    dns = SilentDNS(('0.0.0.0', 0), DropDNS)
    stalled = socketserver.ThreadingTCPServer(('0.0.0.0', 0), StalledHTTP)
    dns.daemon_threads = stalled.daemon_threads = True
    for server in (dns, stalled):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    original = CONFIG.read_text()
    for directive in TIMEOUTS:
        assert original.count(directive) == 1, directive
    try:
        command(['docker', 'pull', IMAGE], timeout=120)
        results['nginx_image'] = command(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'])
        command(['docker', 'network', 'create', network])
        gateway = json.loads(command(['docker', 'network', 'inspect', network]))[0]['IPAM']['Config'][0]['Gateway']
        with tempfile.TemporaryDirectory(prefix='catalogue-outage-') as directory:
            directory = Path(directory)

            def start(name, config, *, alias=None):
                path = directory / (name + '.conf')
                path.write_text(config)
                full_name = 'catalogue-' + name + '-' + suffix
                args = ['docker', 'run', '-d', '--name', full_name, '--network', network,
                        '--label', 'selahcue.test=catalogue-outage', '-p', '127.0.0.1::80',
                        '--mount', f'type=bind,source={path},target=/etc/nginx/conf.d/default.conf,readonly']
                if alias:
                    args += ['--network-alias', alias]
                containers.append(full_name)
                command(args + [IMAGE])
                command(['docker', 'exec', full_name, 'nginx', '-t'])
                port = command(['docker', 'port', full_name, '80/tcp']).split(':')[-1]
                return full_name, 'http://127.0.0.1:' + port + '/v1/catalogue/plans'

            backend, _ = start('api', 'server { listen 8000; location / { default_type application/json; return 200 \'{"plans":[]}\'; } }', alias='api')
            _, url = start('shipping', original)
            # Wait only for this newly started server's listener, before the measured
            # outage. A startup refusal cannot be mistaken for the outage result.
            deadline = time.monotonic() + 5
            while True:
                try:
                    results['healthy'] = fetch(url, timeout=1)
                    if results['healthy'].get('status') == 200:
                        break
                except OSError:
                    pass
                assert time.monotonic() < deadline, results.get('healthy')
                time.sleep(0.1)
            command(['docker', 'stop', '-t', '1', backend])
            results['stopped_api'] = fetch(url)
            assert_unavailable(results['stopped_api'])

            # Replace only the external resolver address to model a silent DNS server.
            # The variable upstream, location and response controls are shipping bytes.
            assert original.count('resolver 127.0.0.11 ') == 1
            silent = original.replace('resolver 127.0.0.11 ', f'resolver {gateway}:{dns.server_address[1]} ')
            old = silent
            for directive in TIMEOUTS:
                old = old.replace(directive, '')
            _, old_url = start('old-dns', old)
            results['old_dns_control'] = fetch(old_url, timeout=30)
            assert results['old_dns_control']['elapsed'] >= 29, results['old_dns_control']
            _, fixed_url = start('fixed-dns', silent)
            results['fixed_dns'] = fetch(fixed_url)
            assert_unavailable(results['fixed_dns'])

            # A real TCP server accepts the upstream request but withholds its response.
            assert original.count('http://api:8000') == 2
            slow = original.replace('http://api:8000', f'http://{gateway}:{stalled.server_address[1]}')
            _, slow_url = start('stalled-read', slow)
            results['stalled_read'] = fetch(slow_url)
            assert_unavailable(results['stalled_read'])
        print(json.dumps(results, indent=2), flush=True)
    finally:
        cleanup_errors = []
        for container in reversed(containers):
            try:
                subprocess.run(['docker', 'logs', container], timeout=15, check=False)
                command(['docker', 'rm', '-f', container], timeout=30)
                check = subprocess.run(['docker', 'container', 'inspect', container], capture_output=True, timeout=15)
                assert check.returncode != 0, 'Owned container remains: ' + container
            except (RuntimeError, subprocess.TimeoutExpired, AssertionError) as error:
                cleanup_errors.append(str(error))
        try:
            command(['docker', 'network', 'rm', network], timeout=30)
            check = subprocess.run(['docker', 'network', 'inspect', network], capture_output=True, timeout=15)
            assert check.returncode != 0, 'Owned network remains: ' + network
        except (RuntimeError, subprocess.TimeoutExpired, AssertionError) as error:
            cleanup_errors.append(str(error))
        for server in (dns, stalled):
            server.shutdown()
            server.server_close()
        assert not cleanup_errors, cleanup_errors


if __name__ == '__main__':
    main()
