#!/usr/bin/env python3
"""Actual legal-browser fixture/failed-request controls; no production API or policy change."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import legal_pages_headless as legal

sys.path.insert(0, str(legal.MARKETING / 'tests'))
import catalogue_browser_fixture as catalogue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=['all', 'fixture', 'negative'], default='all')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    server, port = legal.serve()
    base = f'http://127.0.0.1:{port}'
    receipt = {'scope': 'synthetic actual legal browser; fixture and unchanged request-failure guard', 'checks': []}
    try:
        with sync_playwright() as pw:
            browser = legal.launch(pw)
            try:
                if args.only in ('all', 'fixture'):
                    errors = []
                    context, page = legal.new_page(browser, 1440, 900, errors)
                    try:
                        with page.expect_response(lambda response: response.url == base + '/v1/catalogue/plans') as pending:
                            page.goto(base + '/pricing', wait_until='networkidle')
                        response = pending.value
                        assert response.request.method == 'GET'
                        assert response.status == 200
                        assert response.headers.get('content-type', '').split(';')[0] == 'application/json', response.headers
                        assert response.json() == catalogue.PLANS
                        catalogue.wait(page)
                        assert not errors, errors
                        receipt['checks'].append({'fixture': 'exact anonymous GET JSON; actual cards ready; console/page/request guard clean', 'result': 'PASS'})
                    finally:
                        context.close()
                if args.only in ('all', 'negative'):
                    # A REAL unrelated aborted HTTP request at the transport boundary.
                    # Original listeners and the final navigation guard stay intact.
                    original = legal.new_page
                    def with_aborted_request(*args, **kwargs):
                        context, page = original(*args, **kwargs)
                        context.route('**/unrelated-request-negative', lambda route: route.abort('aborted'))
                        page.add_init_script("window.addEventListener('load', () => fetch('/unrelated-request-negative').catch(() => {}), {once:true})")
                        return context, page
                    try:
                        legal.new_page = with_aborted_request
                        before = len(legal.results)
                        legal.run_navigation(browser, base, 'privacy', legal.expectations())
                        failed = [row for row in legal.results[before:] if not row[1]]
                        assert len(failed) == 1 and failed[0][0] == 'privacy: navigation console clean', failed
                        assert 'requestfailed:' in failed[0][2] and '/unrelated-request-negative' in failed[0][2] and 'ERR_ABORTED' in failed[0][2], failed
                        receipt['checks'].append({'negative': 'actual unrelated net::ERR_ABORTED must fail original navigation console guard', 'observed': failed, 'result': 'EXPECTED_REJECTION'})
                        print('EXPECTED_NEGATIVE_REQUEST_GUARD_REJECTED: unrelated actual net::ERR_ABORTED', flush=True)
                    finally:
                        legal.new_page = original
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS legal catalogue fixture and strict request-failure controls', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
