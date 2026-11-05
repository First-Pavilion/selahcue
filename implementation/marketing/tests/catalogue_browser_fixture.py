"""Synthetic public catalogue, intentionally different from catalogue seed rows."""
import json

PLANS = {"plans": [
    {"key": "HARBOUR", "name": "Harbour", "price_state": "unpriced", "offers": [], "cloud_transcript_minutes_per_week": 7, "sermon_notes_per_week": 11, "watermark": True},
    {"key": "GATHER", "name": "Gather", "price_state": "unpriced", "offers": [], "cloud_transcript_minutes_per_week": 13, "sermon_notes_per_week": 17, "watermark": False},
    {"key": "BEACON", "name": "Beacon", "price_state": "unpriced", "offers": [], "cloud_transcript_minutes_per_week": 19, "sermon_notes_per_week": 23, "watermark": False},
]}


def install(context):
    context.route("**/v1/catalogue/plans", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(PLANS)))


def wait(page):
    page.locator(".catalogue-plans[aria-busy='false']").wait_for()
    page.locator(".pricing-card").first.wait_for()


def card_copy(plan, interval=""):
    """Exact copy ledger derived from response data, independent of production formatters."""
    lines = [plan["name"]]
    offers = [o for o in plan["offers"] if not interval or o["interval"] == interval]
    period = {"WEEK": "week", "MONTH": "month", "YEAR": "year"}
    if not offers:
        lines.append("No price announced for this interval." if interval else "Price not announced yet")
    for offer in offers:
        suffix = " / " + period[offer["interval"]]
        if offer["amount_minor"] is None:
            lines.append(offer["currency"] + suffix + ": Price not announced yet")
        else:
            exponent = offer["minor_unit_exponent"]
            whole, fraction = divmod(int(offer["amount_minor"]), 10 ** exponent)
            amount = str(whole) + ("." + str(fraction).zfill(exponent) if exponent else "")
            lines.append(offer["currency"] + " " + amount + suffix)
    lines.extend(["Not available yet", "Not available yet", str(plan["cloud_transcript_minutes_per_week"]) + " cloud transcript minutes per week", str(plan["sermon_notes_per_week"]) + " sermon notes per week", "Watermark included" if plan["watermark"] else "No watermark"])
    return lines


def check_copy(page, plans, interval=""):
    """No arbitrary allow-listed region: every rendered card line must match response + approved labels."""
    cards = page.locator(".pricing-card")
    return cards.count() == len(plans) and all([line.strip() for line in cards.nth(i).inner_text().splitlines() if line.strip()] == card_copy(plan, interval) for i, plan in enumerate(plans))
