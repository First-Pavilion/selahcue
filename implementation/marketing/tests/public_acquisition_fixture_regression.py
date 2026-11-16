#!/usr/bin/env python3
"""Exercise the real public acquisition HTTP handler with in-memory transport."""

import io
import json
import threading
import unittest
from http.client import HTTPResponse
from types import SimpleNamespace

import public_routes_headless as acquisition


TOKEN = 'SyntheticCsrfToken0123456789AbCd'
COOKIE = f'csrftoken={TOKEN}'
BOOTSTRAP = ('bootstrap', 200)
VERIFY_SUCCESS = ('verify-success', 200, True, True)
VERIFY_INVALID = ('verify-invalid', 200, True, True)


class InMemoryRequest:
    def __init__(self, request):
        self.request = io.BytesIO(request)
        self.response = io.BytesIO()

    def makefile(self, mode, *args):
        assert mode == 'rb'
        return self.request

    def sendall(self, data):
        self.response.write(data)


class AcquisitionFixtureTest(unittest.TestCase):
    def setUp(self):
        self.server = SimpleNamespace(receipts=[], receipt_lock=threading.Lock(), csrf_trace=None)

    def request(self, line, headers=(), body=b''):
        wire = '\r\n'.join((f'{line} HTTP/1.0', *headers, '', '')).encode('ascii') + body
        transport = InMemoryRequest(wire)
        acquisition.LocalSpaHandler(transport, ('127.0.0.1', 0), self.server)
        transport.request = transport.response
        transport.request.seek(0)
        response = HTTPResponse(transport)
        response.begin()
        return response

    def bootstrap(self):
        return self.request('GET /graphql/csrf')

    def verify(self, token, cookie=COOKIE, header=TOKEN, query=acquisition.VERIFY_QUERY):
        body = json.dumps({'query': query, 'variables': {'token': token}}).encode('ascii')
        return self.request('POST /graphql/account', (
            'Content-Type: application/json',
            f'Content-Length: {len(body)}',
            f'Cookie: {cookie}',
            f'X-CSRFToken: {header}',
        ), body)

    def test_idempotent_bootstrap_and_two_ordered_verifications(self):
        first = self.bootstrap()
        self.assertEqual(first.status, 200)
        # Use the handler's configured token here to isolate receipt ordering.
        configured_token = acquisition.SYNTHETIC_CSRF
        verified = self.verify('synthetic-success', f'csrftoken={configured_token}', configured_token)
        self.assertEqual(verified.status, 200)
        second = self.bootstrap()
        self.assertEqual(second.status, 200)
        self.assertEqual(self.verify('synthetic-invalid').status, 200)
        for response in (first, second):
            self.assertEqual(response.getheader('Set-Cookie'), f'{COOKIE}; Path=/; SameSite=Strict')
            self.assertEqual(response.getheader('X-CSRFToken'), TOKEN)
            self.assertEqual(response.getheader('Cache-Control'), 'no-store')
            self.assertEqual(json.loads(response.read()), {'ready': True})
        self.assertEqual(self.server.receipts, [BOOTSTRAP, VERIFY_SUCCESS, BOOTSTRAP, VERIFY_INVALID])
        acquisition.assert_acquisition_receipts(self.server.receipts)

    def test_post_without_bootstrap_is_rejected(self):
        self.assertEqual(self.verify('synthetic-success').status, 400)
        self.bootstrap()
        with self.assertRaises(AssertionError):
            acquisition.assert_acquisition_receipts(self.server.receipts)

    def test_duplicate_post_is_rejected(self):
        self.bootstrap()
        self.assertEqual(self.verify('synthetic-success').status, 200)
        self.assertEqual(self.verify('synthetic-invalid').status, 200)
        self.assertEqual(self.verify('synthetic-invalid').status, 400)
        with self.assertRaises(AssertionError):
            acquisition.assert_acquisition_receipts(self.server.receipts)

    def test_out_of_order_or_malformed_post_is_rejected(self):
        for token, fields, status in (
            ('synthetic-invalid', {}, 400),
            ('synthetic-success', {'query': 'mutation Wrong { logout { revoked } }'}, 400),
            ('synthetic-success', {'cookie': 'csrftoken=wrong'}, 403),
            ('synthetic-success', {'header': 'wrong'}, 403),
        ):
            with self.subTest(token=token, fields=fields):
                self.server.receipts.clear()
                self.bootstrap()
                self.assertEqual(self.verify(token, **fields).status, status)
                with self.assertRaises(AssertionError):
                    acquisition.assert_acquisition_receipts(self.server.receipts)

    def test_final_receipts_require_every_bootstrap_to_succeed(self):
        for receipts in (
            [VERIFY_SUCCESS, VERIFY_INVALID],
            [VERIFY_SUCCESS, BOOTSTRAP, VERIFY_INVALID],
            [BOOTSTRAP, VERIFY_SUCCESS, ('bootstrap', 409), VERIFY_INVALID],
            [BOOTSTRAP, VERIFY_SUCCESS],
        ):
            with self.subTest(receipts=receipts), self.assertRaises(AssertionError):
                acquisition.assert_acquisition_receipts(receipts)


if __name__ == '__main__':
    unittest.main()
