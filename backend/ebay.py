import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from models import Listing

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
IMAGE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image"
ITEM_URL = "https://api.ebay.com/buy/browse/v1/item"
GROUP_URL = "https://api.ebay.com/buy/browse/v1/item/get_items_by_item_group"
SCOPE = "https://api.ebay.com/oauth/api_scope"

_token = ""
_token_until = 0.0

def env(name: str) -> str:
    path = Path(__file__).parent / ".env"
    if not path.exists():
        return ""
    for line in path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        if key.strip() == name:
            return raw.strip()
    return ""

def access_token() -> str:
    global _token, _token_until
    now = time.time()
    if _token and now < _token_until:
        return _token
    client_id = env("EBAY_CLIENT_ID")
    client_secret = env("EBAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("EBAY_CLIENT_ID and EBAY_CLIENT_SECRET go in backend/.env")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials","scope": SCOPE,}).encode()
    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Authorization": f"Basic {basic}","Content-Type": "application/x-www-form-urlencoded",},
        method="POST",)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    _token = payload["access_token"]
    _token_until = now + float(payload.get("expires_in", 7200)) - 60
    return _token

def ebay_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {access_token()}",
        "X-EBAY-C-MARKETPLACE-ID": env("EBAY_MARKETPLACE_ID") or "EBAY_US",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"eBay {error.code}: {detail}") from error
    return json.loads(raw) if raw else {}

def plain_base64(image: str) -> str:
    text = image.strip()
    if text.startswith("data:") and "," in text:
        return text.split(",", 1)[1]
    return text

def read_size(aspects: list[dict]) -> str:
    ranked = []
    for aspect in aspects:
        name = str(aspect.get("name", "")).strip().lower()
        value = str(aspect.get("value", "")).strip()
        if not value or name == "size type":
            continue
        if name == "size":
            ranked.append((0, value))
        elif "size" in name:
            ranked.append((1, value))
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1] if ranked else ""

def paid_price(item: dict) -> tuple[float, str] | None:
    price = item.get("price") or {}
    value = price.get("value")
    if value is None:
        return None
    return float(value), str(price.get("currency") or "USD")

def listing_from_item(item: dict, condition: str) -> Listing | None:
    paid = paid_price(item)
    size = read_size(item.get("localizedAspects") or []) or str(item.get("size") or "").strip()
    item_id = str(item.get("itemId", ""))
    if paid is None or not size or not item_id:
        return None
    value, currency = paid
    condition_id = str(item.get("conditionId") or "")
    if condition_id:
        condition = "new" if condition_id == "1000" else "used"
    return Listing(id=item_id, price=value, currency=currency, condition=condition, size=size, where="eBay")

def listings_from_summary(summary: dict) -> list[Listing]:
    if (summary.get("price") or {}).get("value") is None or not summary.get("itemId"):
        return []
    condition = "new" if str(summary.get("conditionId", "")) == "1000" else "used"
    href = summary.get("itemHref") or f"{ITEM_URL}/{urllib.parse.quote(str(summary['itemId']), safe='')}"
    item = ebay_json(str(href))
    group_id = str((item.get("primaryItemGroup") or {}).get("itemGroupId") or "")
    if group_id:
        grouped = ebay_json(f"{GROUP_URL}?item_group_id={urllib.parse.quote(group_id)}")
        found = []
        seen = set()
        for child in grouped.get("items") or []:
            listing = listing_from_item(child, condition)
            if listing and listing.id not in seen:
                seen.add(listing.id)
                found.append(listing)
        if found:
            return found
    one = listing_from_item(item, condition)
    return [one] if one else []

def titles_from_image(image: str) -> list[str]:
    data = ebay_json(IMAGE_URL, "POST", {"image": plain_base64(image)})
    titles = []
    for summary in data.get("itemSummaries") or []:
        title = str(summary.get("title", "")).strip()
        if title:
            titles.append(title)
    return titles

def listings_for_name(name: str) -> list[Listing]:
    query = urllib.parse.urlencode({"q": name, "limit": "20"})
    data = ebay_json(f"{SEARCH_URL}?{query}")
    listings = []
    for summary in data.get("itemSummaries") or []:
        listings.extend(listings_from_summary(summary))
    return listings