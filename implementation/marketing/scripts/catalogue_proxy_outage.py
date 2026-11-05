#!/usr/bin/env python3
"""Exercise the actual Vite catalogue proxy against a real stalled upstream socket."""
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'vite.config.ts'


class StalledRequest(socketserver.BaseRequestHandler):
    def handle(self):
        self.server.requests.append(self.request.recv(8192).decode('latin1'))
        time.sleep(12)


def available_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def probe(config, upstream, old):
    port = available_port()
    origin = 'http://127.0.0.1:' + str(port)
    with tempfile.TemporaryFile(mode='w+') as log:
        process = subprocess.Popen(
            ['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', str(port), '--strictPort', '--config', str(config)],
            cwd=ROOT, env={**os.environ, 'SELAHCUE_API_ORIGIN': upstream},
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                try:
                    with urllib.request.urlopen(origin, timeout=1) as ready:
                        if ready.status == 200:
                            break
                except (OSError, urllib.error.URLError):
                    pass
                if process.poll() is not None or time.monotonic() >= deadline:
                    log.seek(0)
                    raise AssertionError('Vite did not start: ' + log.read()[-3000:])
                time.sleep(0.1)
            request = urllib.request.Request(origin + '/v1/catalogue/plans', headers={
                'Cookie': 'private=synthetic', 'Authorization': 'Bearer synthetic', 'Referer': origin+'/private',
            })
            started = time.monotonic()
            response = None
            try:
                response = urllib.request.urlopen(request, timeout=10)
            except urllib.error.HTTPError as error:
                response = error
            except (TimeoutError, socket.timeout, urllib.error.URLError) as error:
                result = dict(error=type(error).__name__, elapsed=time.monotonic()-started)
            if response is not None:
                with response:
                    result = dict(status=response.status, elapsed=time.monotonic()-started,
                                  headers=dict(response.headers), body=response.read().decode())
            print(json.dumps({'case': 'old' if old else 'current', 'result': result}), flush=True)
            if old:
                assert result['elapsed'] >= 9, result
            else:
                assert result.get('status') == 503 and result['elapsed'] < 8, result
                assert json.loads(result['body']) == {'error': {'code': 'catalogue_unavailable'}}, result
                assert result['headers']['Cache-Control'] == 'no-store', result
            return result
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


def main():
    original = CONFIG.read_text()
    needle = '        proxyTimeout: 5000,\n'
    assert original.count(needle) == 1
    control = ROOT / ('.catalogue-timeout-control-' + uuid.uuid4().hex + '.ts')
    server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), StalledRequest)
    server.daemon_threads = True
    server.requests = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    upstream = 'http://127.0.0.1:' + str(server.server_address[1])
    try:
        control.write_text(original.replace(needle, ''))
        results = {'old_stalled_control': probe(control, upstream, True),
                   'current_stalled': probe(CONFIG, upstream, False)}
        assert len(server.requests) == 2, server.requests
        for request in server.requests:
            lowered = request.lower()
            assert '\r\ncookie:' not in lowered and '\r\nauthorization:' not in lowered and '\r\nreferer:' not in lowered, request
        assert CONFIG.read_text() == original
        print(json.dumps(results, indent=2), flush=True)
    finally:
        control.unlink(missing_ok=True)
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
