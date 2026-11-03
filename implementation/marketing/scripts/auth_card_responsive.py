#!/usr/bin/env python3
"""Ticket 17tnw2b2gmm: real 375px and desktop auth-card validation.

Uses the production bundle and the same deterministic auth-state driver as test:states.
Playwright viewport emulation avoids Chrome CLI's 500px minimum window width.
Requires the existing responsive-sweep Playwright dependency and local Chrome.
"""
import socketserver
import threading

from playwright.sync_api import sync_playwright

import auth_pages_headless as auth


def main():
    stale = auth.check_bundle_is_current()
    if stale:
        raise RuntimeError(stale)
    failures = []
    with socketserver.TCPServer(("127.0.0.1", 0), auth.SpaHandler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=auth.find_chrome(), headless=True)
            try:
                for width in (375, 1440):
                    for scenario, path in (("signup-validation-focus", "/signup"), ("forgot-empty-focus", "/forgot-password"), ("forgot-bad-email", "/forgot-password")):
                        suffix = "-narrow" if width == 375 else ""
                        page = browser.new_page(viewport={"width": width, "height": 900})
                        page.goto(f"{base}{path}?__scenario={scenario}{suffix}")
                        page.wait_for_selector("#__results", state="attached")
                        result = page.locator("#__results").text_content()
                        print(f"VIEWPORT {width}: {scenario}\n{result}", flush=True)
                        failures.extend(line for line in result.splitlines() if line.startswith("FAIL"))
                        page.close()
            finally:
                browser.close()
                server.shutdown()
    print(f"Responsive auth-card result: {len(failures)} failures")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
