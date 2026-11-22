"""TinyFish adapter: one read-only browser run per pinned catalog page.

Parses the run's SSE stream up to its terminal event, then checks every returned field on its
own. A field that cannot be verified is left empty; it is never filled from the saved catalog.
"""

import asyncio
import json
import math
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import NamedTuple
from urllib.parse import urlsplit

import httpx

from .catalog import ALLOWED_URLS

RUN_SSE = "https://agent.tinyfish.ai/v1/automation/run-sse"
ATTEMPT_TIMEOUT = 90
MAX_EVENT = 512_000
MAX_STREAM = 4_000_000

# The only wording about a failed run that leaves this service. Provider text is never forwarded.
MESSAGES = {
    "timeout": "the retailer check timed out.",
    "unreachable": "TinyFish could not be reached or the connection dropped.",
    "rejected": "TinyFish rejected the configured key.",
    "busy": "TinyFish was busy or unavailable.",
    "refused": "TinyFish did not accept the request.",
    "incomplete": "the browser run ended before reporting a result.",
    "run_failed": "the browser run did not complete.",
    "unusable": "the browser run returned no usable result.",
    "oversized": "the browser run returned too much data.",
    "mismatch": "the page did not match the catalog product, so nothing was recorded.",
}


class TinyFishError(Exception):
    def __init__(self, kind, safe_to_retry=False, run_id=None):
        super().__init__(MESSAGES[kind])
        self.kind = kind
        self.safe_to_retry = safe_to_retry
        self.run_id = run_id


class Extract(NamedTuple):
    result: dict
    run_id: str | None
    completed_at: str


def configured_key():
    return os.environ.get("TINYFISH_API_KEY", "").strip()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nullable(kind, description):
    return {"type": [kind, "null"], "description": description}


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "productName": {"type": "string", "description": "Product name exactly as the page heading shows it."},
        "articleNumber": _nullable("string", "Article or item number exactly as displayed."),
        "pageUrl": _nullable("string", "Address of the page the values were read from, after any redirect."),
        "priceCad": _nullable("number", "Current displayed price in Canadian dollars, for one unit."),
        "currency": _nullable("string", "Three-letter currency of the displayed price."),
        "priceQuote": _nullable("string", "Copy only the displayed current unit price, with its currency marker."),
        "priceConditions": _nullable("string", "Any displayed condition on the price, such as a sale end date or member price."),
        "widthMm": _nullable("integer", "Overall assembled width in millimetres."),
        "depthMm": _nullable("integer", "Overall assembled depth in millimetres."),
        "heightMm": _nullable("integer", "Overall assembled maximum height in millimetres."),
        "dimensionsQuote": _nullable("string", "Copy the overall assembled measurement lines, including axis labels and units."),
        "dimensionsConflict": {"type": "boolean", "description": "True when the page shows differing values for an overall dimension."},
        "stock": {"type": "string", "enum": ["in_stock", "out_of_stock", "unknown"]},
        "stockScope": _nullable("string", "Store or delivery area the availability text applies to."),
        "stockQuote": _nullable("string", "Copy the availability and the store or online channel it applies to together."),
    },
    "additionalProperties": False,
}
OUTPUT_SCHEMA["required"] = list(OUTPUT_SCHEMA["properties"])


def goal_for(entry, store_location):
    return (
        f"Read-only product check of this exact page, which should be the {entry['retailer']} {entry['name']} "
        f"{entry['category']}. Do not open other products, search, sign in, add to cart, start checkout, enter "
        "personal information or submit forms. You may expand the page's own measurement, product detail and "
        f"availability sections, and choose the store nearest \"{store_location}\" in the page's own store "
        "selector to view availability.\n"
        "Report the product name and article number exactly as displayed; the address of the page you read; the "
        "current price in Canadian dollars with the exact price text; the overall assembled width, depth and "
        "maximum height in millimetres with the exact measurement text (not package, seat-only or tabletop-only "
        "sizes); and availability with the exact text and the store or delivery area it applies to.\n"
        "Use null for anything the page does not clearly show. Never estimate, never use values from memory or "
        "from other websites. Set dimensionsConflict to true when the page shows differing values for an overall "
        "dimension. If the page is a different product, unavailable or blocked, report what it shows and null "
        "for the rest."
    )


class SSEParser:
    """Incremental server-sent-event reader that yields each event's JSON object."""

    def __init__(self):
        self._buffer = bytearray()
        self._data = []
        self._size = 0
        self._total = 0

    def feed(self, chunk):
        self._total += len(chunk)
        if self._total > MAX_STREAM:
            raise TinyFishError("oversized")
        self._buffer.extend(chunk)
        events = []
        while (end := self._buffer.find(b"\n")) >= 0:
            line = bytes(self._buffer[:end]).rstrip(b"\r")
            del self._buffer[:end + 1]
            if line:
                self._field(line)
            elif (event := self._dispatch()) is not None:
                events.append(event)
        if len(self._buffer) > MAX_EVENT:
            raise TinyFishError("oversized")
        return events

    def close(self):
        # A stream cut inside a line leaves only a fragment, which is never treated as an event.
        if self._buffer:
            self._buffer.clear()
            self._data = []
            return None
        return self._dispatch()

    def _field(self, line):
        name, _, value = line.partition(b":")
        if name != b"data":
            return
        self._size += len(value) + 1
        if self._size > MAX_EVENT:
            raise TinyFishError("oversized")
        self._data.append(value.removeprefix(b" "))

    def _dispatch(self):
        data, self._data, self._size = b"\n".join(self._data), [], 0
        if not data:
            return None
        try:
            event = json.loads(data)
        except ValueError:
            return None
        return event if isinstance(event, dict) else None


def terminal_result(event):
    """None until the run's terminal event, then its structured result."""
    kind = event.get("type")
    if kind == "ERROR":
        raise TinyFishError("run_failed")
    if kind != "COMPLETE":
        return None
    if event.get("status") != "COMPLETED":
        raise TinyFishError("run_failed")
    result = event.get("result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            result = None
    if not isinstance(result, dict):
        raise TinyFishError("unusable")
    return result


def _run_id(event):
    value = event.get("run_id", event.get("runId"))
    return value if isinstance(value, str) and 0 < len(value) <= 120 else None


async def run(key, url, goal, *, transport=None, timeout=ATTEMPT_TIMEOUT):
    """One attempt at one browser run. Returns the completed extract or raises TinyFishError."""
    if url not in ALLOWED_URLS.values():
        raise TinyFishError("refused")
    parser, run_id = SSEParser(), None
    response_received = False
    try:
        async with asyncio.timeout(timeout), httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10),
                                                               trust_env=False, transport=transport) as client:
            async with client.stream("POST", RUN_SSE, headers={"X-API-Key": key, "Accept": "text/event-stream"},
                                     json={"url": url, "goal": goal, "output_schema": OUTPUT_SCHEMA}) as response:
                response_received = True
                status = response.status_code
                if status in (401, 403):
                    raise TinyFishError("rejected")
                if status == 429 or status >= 500:
                    raise TinyFishError("busy", safe_to_retry=status == 429)
                if status != 200:
                    raise TinyFishError("refused")
                async for chunk in response.aiter_bytes():
                    for event in parser.feed(chunk):
                        run_id = _run_id(event) or run_id
                        if (result := terminal_result(event)) is not None:
                            return Extract(result, run_id, utc_now())
                if (event := parser.close()) is not None and (result := terminal_result(event)) is not None:
                    return Extract(result, _run_id(event) or run_id, utc_now())
    except TinyFishError as exc:
        exc.run_id = run_id
        raise
    except httpx.ConnectTimeout as exc:
        raise TinyFishError("timeout", safe_to_retry=not response_received, run_id=run_id) from exc
    except httpx.ConnectError as exc:
        raise TinyFishError("unreachable", safe_to_retry=not response_received, run_id=run_id) from exc
    except (httpx.TimeoutException, TimeoutError) as exc:
        raise TinyFishError("timeout", run_id=run_id) from exc
    except httpx.HTTPError as exc:
        raise TinyFishError("unreachable", run_id=run_id) from exc
    raise TinyFishError("incomplete", run_id=run_id)


CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
PRICE = re.compile(
    r"(?:(?:current |sale )?price\s*:?\s*)?(?P<prefix>CAD\s*\$?|CA\$|C\$|\$)?\s*"
    r"(?P<amount>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)\s*(?P<suffix>CAD)?", re.I)
DECIMAL = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
MEASUREMENT = (
    rf"(?:(?P<whole>\d+)[ \u00a0-](?P<top>\d+)/(?P<bottom>\d+)|(?P<plain>{DECIMAL}))"
    r"\s*(?P<unit>mm\b|cm\b|m\b|inch(?:es)?\b|in\b|\"|\u201d|\u2033|'')")
LABELED_LENGTH = re.compile(r"\b(?P<axis>width|depth|height|[wdh])\s*[:=]?\s*" + MEASUREMENT, re.I)
DESCRIBED_LENGTH = re.compile(r"(?<![\d.,/])" + MEASUREMENT + r"\s+(?P<axis>wide|deep|high|tall)\b", re.I)
SHARED_UNIT_LENGTHS = re.compile(
    rf"W\s*(?P<w>{DECIMAL})\s*[x×]\s*D\s*(?P<d>{DECIMAL})\s*[x×]\s*H\s*(?P<h>{DECIMAL})\s*(?P<unit>mm|cm|m)", re.I)
OTHER_DIMENSIONS = re.compile(r"\b(?:packag\w*|seat|table\s*top|drawer|minimum|min\.?)\b", re.I)
SCALE = {"mm": 1, "cm": 10, "m": 1000}
MIN_MM, MAX_MM = 100, 4000
MAX_CENTS = 1_000_000


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    value = " ".join(CONTROL.sub(" ", value).split())
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def _fold(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").upper()


def _same_page(found, expected):
    try:
        a, b = urlsplit(found.strip()), urlsplit(expected)
        return (a.scheme == "https" and a.hostname == b.hostname and a.port is None and not a.username
                and a.path.rstrip("/") == b.path.rstrip("/"))
    except ValueError:
        return False


def same_product(entry, result):
    """The extract must name the catalog product and locate it by article number or by the pinned page."""
    name = result.get("productName")
    if not isinstance(name, str) or len(name) > 300:
        return False
    words = set(re.findall(r"[A-Z0-9]+", _fold(name)))
    if not set(re.findall(r"[A-Z0-9]+", _fold(entry["name"]))) <= words:
        return False
    proofs = []
    digits = re.sub(r"\D", "", entry["sku"])
    article = result.get("articleNumber")
    if len(digits) >= 6 and article is not None:
        proofs.append(type(article) in (str, int) and re.sub(r"\D", "", str(article)) == digits)
    page = result.get("pageUrl")
    if page is not None:
        proofs.append(isinstance(page, str) and _same_page(page, entry["url"]))
    return bool(proofs) and all(proofs)


def _number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def checked_price(result):
    """Integer cents only when the amount is a whole-cent CAD price that the quoted page text also shows."""
    value, currency = result.get("priceCad"), result.get("currency")
    if not _number(value) or not 0 < value <= MAX_CENTS / 100:
        return None
    if currency is not None and (not isinstance(currency, str) or currency.strip().upper() != "CAD"):
        return None
    match = PRICE.fullmatch(_text(result.get("priceQuote"), 200))
    if not match:
        return None
    prefix = (match["prefix"] or "").strip().upper()
    if not prefix and not match["suffix"]:
        return None
    if currency is None and prefix in ("", "$") and not match["suffix"]:
        return None
    whole, _, fraction = match["amount"].replace(",", "").partition(".")
    quoted_cents = int(whole) * 100 + int(fraction.ljust(2, "0"))
    return quoted_cents if abs(value * 100 - quoted_cents) <= 1e-6 else None


def quoted_lengths(quote):
    """Measurements by labeled axis, in mm with metric or rounded-inch tolerance."""
    lengths = {"w": [], "d": [], "h": []}
    if OTHER_DIMENSIONS.search(quote):
        return lengths
    if triple := SHARED_UNIT_LENGTHS.fullmatch(quote):
        for axis in lengths:
            lengths[axis].append((float(triple[axis].replace(",", "")) * SCALE[triple["unit"].lower()], 0.5))
        return lengths
    for pattern in (LABELED_LENGTH, DESCRIBED_LENGTH):
        for match in pattern.finditer(quote):
            if match["whole"]:
                denominator = int(match["bottom"])
                if denominator == 0:
                    continue
                value = int(match["whole"]) + int(match["top"]) / denominator
            else:
                value = float(match["plain"].replace(",", ""))
            unit = match["unit"].lower()
            axis = match["axis"].lower()[0]
            if axis == "t":  # tall
                axis = "h"
            lengths[axis].append((value * SCALE.get(unit, 25.4), 0.5 if unit in SCALE else 1.0))
    return lengths


def checked_length(value, lengths):
    """Integer millimetres only when plausible for furniture and supported by the quoted page text."""
    if not _number(value) or not MIN_MM <= value <= MAX_MM or value != int(value):
        return None
    return int(value) if lengths and all(abs(value - stated) <= tolerance for stated, tolerance in lengths) else None


STOCK_WORDING = {
    "in_stock": r"(?:in stock|low stock|available|available for pick ?up|available for delivery)",
    "out_of_stock": r"(?:out of stock|not in stock|sold out|(?:temporarily )?unavailable|not available)",
}


def _words(text):
    return " ".join(re.findall(r"[a-z0-9]+", _fold(text).lower()))


def checked_stock(result, store_location, retailer):
    """The same quoted statement must tie the claimed status to the requested store or online channel."""
    stock = result.get("stock")
    scope, quote = _text(result.get("stockScope"), 120), _text(result.get("stockQuote"), 200)
    if not isinstance(stock, str) or stock not in STOCK_WORDING:
        return None
    place = _words(store_location.partition(",")[0])
    if not place:
        return None
    # Limit scope to the real requested locality or the retailer's generic online channel.
    locality = rf"(?:{re.escape(place)}|{re.escape(_words(store_location))})"
    local_scope = rf"(?:(?:{re.escape(_words(retailer))}|store in|delivery to) )?{locality}(?: store)?"
    if re.fullmatch(local_scope, _words(scope)):
        area = local_scope
    elif _words(scope) == "online":
        area = "online"
    else:
        return None
    status = STOCK_WORDING[stock]
    wording = rf"(?:{status} (?:(?:at|in|for|to) (?:the )?)?{area}|{area} {status})"
    return (stock, scope, quote) if re.fullmatch(wording, _words(quote)) else None


def build_offer(entry, result, store_location, checked_at):
    """One completed extract -> (OfferSnapshot, notes about fields left empty). Raises when it is not this product."""
    if not isinstance(result.get("productName"), str):
        raise TinyFishError("unusable")
    if not same_product(entry, result):
        raise TinyFishError("mismatch")
    notes, evidence = [], []

    price = checked_price(result)
    conditions = "Price was not confirmed by this check."
    if price is None:
        notes.append("price not confirmed")
    else:
        evidence.append(f"Price: “{_text(result.get('priceQuote'), 200)}”")
        conditions = "Advertised merchandise price on the retailer's Canadian page; tax and delivery excluded."
        if extra := _text(result.get("priceConditions"), 200):
            conditions += f" Page note: {extra}"

    dimensions_quote = _text(result.get("dimensionsQuote"), 300)
    lengths = quoted_lengths(dimensions_quote)
    sizes = {}
    for field, source in (("widthMM", "widthMm"), ("depthMM", "depthMm"), ("heightMM", "heightMm")):
        sizes[field] = checked_length(result.get(source), lengths[source[0]])
        if sizes[field] is None:
            notes.append(f"{field[:-2]} not confirmed")
    reported = any(result.get(k) is not None for k in ("widthMm", "depthMm", "heightMm"))
    flag = result.get("dimensionsConflict")
    contradictory_axis = any(values and max(v - tol for v, tol in values) > min(v + tol for v, tol in values)
                             for values in lengths.values())
    conflict = flag is True or (reported and flag is not False) or contradictory_axis
    if conflict:
        notes.append("page shows conflicting dimensions")
    if any(v is not None for v in sizes.values()):
        evidence.append(f"Dimensions: “{dimensions_quote}”")

    verified_stock = checked_stock(result, store_location, entry["retailer"])
    if verified_stock:
        stock, scope, stock_quote = verified_stock
        evidence.append(f"Availability: “{stock_quote}”")
    else:
        stock, scope = "unknown", f"{store_location} — availability not confirmed"
        notes.append("availability not confirmed")

    offer = {
        "id": entry["id"], "retailer": entry["retailer"], "sku": entry["sku"], "name": entry["name"],
        "category": entry["category"], **sizes, "priceCents": price, "currency": "CAD",
        "stock": stock, "stockScope": scope, "closedStorage": entry["closedStorage"], "url": entry["url"],
        "evidenceQuote": _text("; ".join(evidence), 700) or "The page was read but no value could be verified against its text.",
        "checkedAt": checked_at, "provenance": "live", "dimensionConflict": conflict, "priceConditions": conditions,
    }
    return offer, notes
