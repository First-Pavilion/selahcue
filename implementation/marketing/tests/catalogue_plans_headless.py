#!/usr/bin/env python3
"""Real production Home/Pricing public API states, both required engines; synthetic data only."""
from __future__ import annotations
import argparse
import copy
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright, Error as PlaywrightError

import catalogue_browser_fixture as fixture
import core_pages_headless as core
sys.path.insert(0, str(core.MARKETING / "scripts"))
import auth_pages_headless as auth


def offer(amount, currency="USD", interval="MONTH", exponent=2):
    return {"currency": currency, "interval": interval, "price_state": "unpriced" if amount is None else "priced", "amount_minor": amount, "minor_unit_exponent": exponent}


def navigate(page, target, width):
    if target == "/":
        page.locator(".navbar-header a.brand").click()
    elif page.get_by_role("button", name="Menu", exact=True).is_visible():
        page.get_by_role("button", name="Menu", exact=True).click()
        page.locator(f"#mobile-nav-sheet a[href='{target}']").first.click()
    else:
        page.locator(f".desktop-nav a[href='{target}']").first.click()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", choices=["chromium", "webkit", "both"], default="both")
    parser.add_argument("--widths", help="comma-separated diagnostic widths; default acceptance covers320,768,1440")
    parser.add_argument("--paths", help="comma-separated diagnostic paths; default acceptance coversHome andPricing")
    parser.add_argument("--old-baseline", action="store_true", help="only for proving the preimplementation bundle RED")
    args = parser.parse_args()
    if not args.old_baseline:
        stale = auth.check_bundle_is_current()
        if stale:
            raise RuntimeError(stale)
    results = []
    checks = 0
    scenario = "setup"

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            diagnostic = {"scenario": scenario, "failure": message}
            if "overflow" in message:
                diagnostic["layout"] = page.evaluate("""() => ({ iw: innerWidth, client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth, offenders: [...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth).map(e=>({tag:e.tagName, cls:e.className, right:e.getBoundingClientRect().right, width:e.getBoundingClientRect().width})).slice(0,30) })""")
            args.output.with_suffix('.failure.json').write_text(json.dumps(diagnostic, indent=2)+'\n')
            raise AssertionError(scenario + ": " + message)

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), core.SpaHandler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with sync_playwright() as pw:
                for engine in (["chromium", "webkit"] if args.engine == "both" else [args.engine]):
                    browser = getattr(pw, engine).launch()
                    try:
                        for path in (args.paths.split(",") if args.paths else ("/", "/pricing")):
                            for width in ([int(w) for w in args.widths.split(",")] if args.widths else (320, 768, 1440)):
                                scenario = f"{engine} {path} {width}px"
                                print("START", scenario, flush=True)
                                context = browser.new_context(viewport={"width": width, "height": 900})
                                context.add_init_script("""(() => {
                                  const original = window.fetch;
                                  window.catalogueAbortCount = 0;
                                  window.fetch = function(input, options) {
                                    if (input === '/v1/catalogue/plans' && options?.signal) {
                                      options.signal.addEventListener('abort', () => window.catalogueAbortCount++);
                                    }
                                    return original.call(this, input, options);
                                  };
                                })()""")
                                context.add_cookies([{ "name": "synthetic-session", "value": "must-not-be-sent", "url": base }])
                                context.route("https://**", lambda route: route.abort())
                                context.route("**/graphql/**", lambda route: route.fulfill(status=200, content_type="application/json", body='{"data":{"accountViewer":null}}'))
                                pending = []
                                requests = []
                                def hold(route):
                                    requests.append(route.request)
                                    pending.append(route)
                                context.route("**/v1/catalogue/plans", hold)
                                page = context.new_page()
                                try:
                                    page.goto(base + path, wait_until="load")
                                    page.locator(".catalogue-message[role=status]").filter(has_text="Loading plans…").wait_for()
                                    check(page.locator(".pricing-card").count() == 0, "pending must not invent cards")
                                    # Wait for an actual fetch instead of using a fixed sleep.
                                    page.wait_for_timeout(50)
                                    check(bool(pending), "public request missing")
                                    request = requests[-1]
                                    check(request.method == "GET" and request.url == base + "/v1/catalogue/plans", "exact relative GET required")
                                    check(not any(key.lower() in request.headers for key in ("cookie", "authorization")), "public fetch must omit credentials")
                                    pending.pop().fulfill(status=200, content_type="application/json", body=json.dumps(fixture.PLANS))
                                    fixture.wait(page)
                                    check(fixture.check_copy(page, fixture.PLANS["plans"]), "exact API-driven card copy ledger")
                                    planted = page.locator(".pricing-card").first.evaluate_handle("card => { const p=document.createElement('p'); p.textContent='Trusted by 5,000 churches.'; card.appendChild(p); return p; }")
                                    check(not fixture.check_copy(page, fixture.PLANS["plans"]), "CONTROL exact ledger must reject an invented claim")
                                    planted.evaluate("el => el.remove()")
                                    planted.dispose()
                                    check(page.locator(".plan-name").all_text_contents() == ["Harbour", "Gather", "Beacon"], "names must follow response")
                                    check(page.locator(".catalogue-unpriced").all_text_contents() == ["Price not announced yet"] * 3, "unpriced must not become zero")
                                    check("7 cloud transcript minutes per week" in page.locator(".pricing-card").first.inner_text(), "weekly API value missing")
                                    check("11 sermon notes per week" in page.locator(".pricing-card").first.inner_text(), "note allowance missing")
                                    check(page.locator(".catalogue-plans [role='radiogroup']").count() == 0, "unpriced data must omit billing toggle")
                                    check(page.locator(".catalogue-plans table").count() == 0, "no invented comparison table")
                                    check(page.locator(".pricing-card a").count() == 0, "no invented CTA destination")
                                    for button in page.locator(".pricing-card button").all():
                                        check(button.is_disabled() and button.inner_text() == "Not available yet", "unavailable CTA must be disabled")
                                        note = button.get_attribute("aria-describedby")
                                        check(bool(note) and page.locator(f"[id='{note}']").inner_text() == "Not available yet", "disabled CTA explanation missing")
                                    text = page.locator(".catalogue-plans").inner_text()
                                    check(not any(word in text.lower() for word in ("device", "ndi", "screen", "forever", "discount", "popular")), "private/invented claim")
                                    check(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "page overflow")
                                    before = len(core.FAILURES)
                                    core.headings_ok(page, "catalogue")
                                    check(len(core.FAILURES) == before, "heading outline skipped a level")
                                    # Route change and response update, without rebuilding/reloading the site.
                                    changed = copy.deepcopy(fixture.PLANS)
                                    changed["plans"][0].update(name="Changed <img src=x onerror=window.catalogueInjected=1>", cloud_transcript_minutes_per_week=29, sermon_notes_per_week=31, watermark=False, price_state="priced", offers=[offer("0"), offer("9223372036854775807", "CLF", "YEAR", 4), offer(None, "JPY", "WEEK", 0)])
                                    target = "/pricing" if path == "/" else "/"
                                    navigate(page, target, width)
                                    page.locator(".catalogue-message[role=status]").filter(has_text="Loading plans…").wait_for()
                                    check(page.locator(".pricing-card").count() == 0, "route entry must not reuse old data")
                                    check(bool(pending), "new route must fetch")
                                    pending.pop().fulfill(status=200, content_type="application/json", body=json.dumps(changed))
                                    fixture.wait(page)
                                    check(page.locator(".plan-name").first.inner_text() == changed["plans"][0]["name"], "changed API label must remain escaped text")
                                    check(page.locator(".plan-name img").count() == 0 and page.evaluate("window.catalogueInjected === undefined"), "response text executed")
                                    check(fixture.check_copy(page, changed["plans"]), "changed API copy ledger")
                                    prices = page.locator(".catalogue-offers").first.locator("li").all_text_contents()
                                    check(prices == ["USD 0.00 / month", "CLF 922337203685477.5807 / year", "JPY / week: Price not announced yet"], "all offers, exact64-bit and null must be preserved")
                                    radios = page.get_by_role("radiogroup", name="Billing interval")
                                    check(radios.get_by_role("radio", name="All intervals").get_attribute("aria-checked") == "true", "no arbitrary interval default")
                                    radios.get_by_role("radio", name="Per year").click()
                                    check(page.locator(".catalogue-offers").first.inner_text() == "CLF 922337203685477.5807 / year", "interval switching must follow actual offers")
                                    check(page.locator(".pricing-card").nth(1).locator(".catalogue-unpriced").inner_text() == "No price announced for this interval.", "missing interval cannot become a fake price")
                                    check(fixture.check_copy(page, changed["plans"], "YEAR"), "filtered API copy ledger")
                                    radios.get_by_role("radio", name="All intervals").click()
                                    check(page.locator(".catalogue-offers li").count() == 3, "all offers must recover")
                                    check(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "multi-offer/long name overflow")
                                    if width == 320:
                                        removed = page.add_style_tag(content=".plan-name { min-width: auto !important; overflow-wrap: normal !important; }")
                                        check(page.evaluate("document.documentElement.scrollWidth > innerWidth"), "CONTROL removing API-name wrapping must expose overflow")
                                        removed.evaluate("el => el.remove()")
                                        check(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "wrapping restoration must recover")
                                    # Actual failed response -> safe generic error -> explicit retry -> empty.
                                    navigate(page, path, width)
                                    page.locator(".catalogue-message[role=status]").filter(has_text="Loading plans…").wait_for()
                                    pending.pop().fulfill(status=503, content_type="text/html", body="<script>window.catalogueInjected=1</script>backend diagnostic sentinel")
                                    page.get_by_role("alert").wait_for()
                                    check(page.get_by_role("alert").inner_text() == "Plans could not be loaded. Please try again.", "generic unavailable state required")
                                    check(page.locator(".pricing-card").count() == 0 and "diagnostic sentinel" not in page.inner_text("body"), "error cannot retain old data or disclose server body")
                                    page.get_by_role("button", name="Retry loading plans").click()
                                    page.locator(".catalogue-message[role=status]").filter(has_text="Loading plans…").wait_for()
                                    pending.pop().fulfill(status=200, content_type="application/json", body='{"plans":[]}')
                                    page.locator(".catalogue-message[role=status]").filter(has_text="No plans have been published yet.").wait_for()
                                    check(page.locator(".pricing-card").count() == 0, "empty response must not fallback")
                                    # Leave while the real request is pending: the actual fetch signal must abort.
                                    navigate(page, target, width)
                                    page.locator(".catalogue-message[role=status]").filter(has_text="Loading plans…").wait_for()
                                    before_abort = page.evaluate("window.catalogueAbortCount")
                                    navigate(page, "/features", width)
                                    page.locator(".features-view h1").wait_for()
                                    check(page.evaluate("window.catalogueAbortCount") > before_abort, "unmount must abort the owned request")
                                    check(page.locator(".catalogue-plans").count() == 0, "late result must not update another route")
                                    print("PASS", scenario, flush=True)
                                    results.append({"engine": engine, "path": path, "width": width, "states": ["loading", "unpriced", "changed", "multi-offer", "escaped", "unavailable", "retry", "empty"], "result": "PASS"})
                                except Exception as error:
                                    args.output.with_suffix('.diagnostic.json').write_text(json.dumps({"scenario": scenario, "error": str(error), "url": page.url, "body": page.inner_text('body')[:3000], "catalogue": page.locator('.catalogue-plans').inner_html() if page.locator('.catalogue-plans').count() else None, "requests": len(requests), "held": len(pending), "completed_scenarios": results}, indent=2)+'\n')
                                    raise
                                finally:
                                    for route in pending:
                                        try:
                                            route.abort()
                                        except PlaywrightError as error:
                                            if "already" not in str(error).lower() and "closed" not in str(error).lower():
                                                raise
                                    pending.clear()
                                    context.unroute_all(behavior="ignoreErrors")
                                    context.close()
                    finally:
                        browser.close()
        finally:
            server.shutdown()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"checks": checks, "scenarios": results, "result": "PASS", "scope": "frontend synthetic HTTP boundary, not backend/admin E2E"}, indent=2) + "\n")
    print(f"catalogue: {checks} checks, {len(results)} engine/path/width scenarios PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
