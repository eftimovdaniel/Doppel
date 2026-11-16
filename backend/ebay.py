import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from models import Listing
from name import title_has_model, title_has_print, title_is_clothes, title_matches_style

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
IMAGE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image"
ITEM_URL = "https://api.ebay.com/buy/browse/v1/item"
GROUP_URL = "https://api.ebay.com/buy/browse/v1/item/get_items_by_item_group"
SCOPE = "https://api.ebay.com/oauth/api_scope"

_token = ""
_token_until = 0.0

def env(name: str) -> str:
    found = os.environ.get(name, "").strip()
    if found:
        return found
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

class MissingItem(RuntimeError):
    pass

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
        if error.code == 404:
            raise MissingItem(f"eBay 404: {detail}") from error
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

def listing_url(item: dict, item_id: str) -> str:
    found = str(item.get("itemWebUrl") or "").strip()
    parsed = urllib.parse.urlparse(found)
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and (host == "ebay.com" or host.endswith(".ebay.com")):
        return found
    parts = item_id.split("|")
    number = parts[1] if len(parts) >= 2 else ""
    if number.isdigit():
        return f"https://www.ebay.com/itm/{number}"
    return ""

def listing_image(item: dict) -> str:
    image = item.get("image") or {}
    url = str(image.get("imageUrl") or "").strip()
    if not url:
        thumbs = item.get("thumbnailImages") or []
        if thumbs:
            url = str((thumbs[0] or {}).get("imageUrl") or "").strip()
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "ebayimg.com" or host.endswith(".ebayimg.com")):
        return ""
    return re.sub(r"/s-l\d+\.", "/s-l500.", url)

def listing_from_item(item: dict, condition: str, image: str = "") -> Listing | None:
    paid = paid_price(item)
    size = read_size(item.get("localizedAspects") or []) or str(item.get("size") or "").strip()
    item_id = str(item.get("itemId", ""))
    if paid is None or not size or not item_id:
        return None
    value, currency = paid
    condition_id = str(item.get("conditionId") or "")
    if condition_id:
        condition = "new" if condition_id == "1000" else "used"
    return Listing(id=item_id,price=value,currency=currency,condition=condition,size=size,where="eBay",url=listing_url(item, item_id),title=str(item.get("title") or "").strip(),image=listing_image(item) or image,)

def listings_from_summary(summary: dict, name: str = "") -> list[Listing]:
    if (summary.get("price") or {}).get("value") is None or not summary.get("itemId"):
        return []
    condition = "new" if str(summary.get("conditionId", "")) == "1000" else "used"
    href = summary.get("itemHref") or f"{ITEM_URL}/{urllib.parse.quote(str(summary['itemId']), safe='')}"
    try:
        item = ebay_json(str(href))
    except MissingItem:
        return []
    fallback = str(summary.get("title") or "")
    picture = listing_image(summary)

    def keep(listing: Listing | None, source_title: str) -> Listing | None:
        if listing is None:
            return None
        title = listing.title or source_title or fallback
        if name and not title_has_model(name, title):
            return None
        return listing

    group_id = str((item.get("primaryItemGroup") or {}).get("itemGroupId") or "")
    if group_id:
        try:
            grouped = ebay_json(f"{GROUP_URL}?item_group_id={urllib.parse.quote(group_id)}")
        except MissingItem:
            grouped = {}
        found = []
        seen = set()
        for child in grouped.get("items") or []:
            listing = keep(listing_from_item(child, condition, picture), str(child.get("title") or ""))
            if listing and listing.id not in seen:
                seen.add(listing.id)
                found.append(listing)
        if found:
            return found
    one = keep(listing_from_item(item, condition, picture), str(item.get("title") or fallback))
    return [one] if one else []

def summaries_from_image(image: str) -> list[dict]:
    data = ebay_json(IMAGE_URL, "POST", {"image": plain_base64(image)})
    found = []
    for summary in data.get("itemSummaries") or []:
        title = str(summary.get("title") or "").strip()
        if not title or not summary.get("itemId"):
            continue
        item = dict(summary)
        item["title"] = title
        found.append(item)
    return found

def titles_from_image(image: str) -> list[str]:
    return [item["title"] for item in summaries_from_image(image)]

def listings_for_name(name: str) -> list[Listing]:
    query = urllib.parse.urlencode({"q": name, "limit": "20"})
    data = ebay_json(f"{SEARCH_URL}?{query}")
    listings = []
    for summary in data.get("itemSummaries") or []:
        if not title_has_model(name, str(summary.get("title", ""))):
            continue
        listings.extend(listings_from_summary(summary, name))
    return listings

def listings_for_style(name: str, label: str, heel_mm: int = 0) -> list[Listing]:
    query_word = {
        "PUMP": "pump",
        "SANDAL": "sandal",
        "BOOT": "boot",
        "LOAFER": "loafer",
        "SNEAKER": "sneaker",
        "HEEL": "heel",
        "BAG": "handbag",
        "JACKET": "jacket",
        "COAT": "coat",
        "JEANS": "jeans",
    }.get(label, "")
    if not query_word:
        return []
    query_name = f"{query_word} {heel_mm}mm" if heel_mm else query_word
    query = urllib.parse.urlencode({"q": query_name, "limit": "20"})
    data = ebay_json(f"{SEARCH_URL}?{query}")
    listings = []
    seen = set()
    for summary in data.get("itemSummaries") or []:
        title = str(summary.get("title") or "")
        if not title_matches_style(title, label, heel_mm, ""):
            continue
        for listing in listings_from_summary(summary):
            if not title_matches_style(listing.title or title, label, heel_mm, ""):
                continue
            if listing.id in seen:
                continue
            seen.add(listing.id)
            listings.append(listing)
    return listings

def listings_for_print(pattern: str) -> list[Listing]:
    query_word = {
        "polka": "polka dot",
        "dot": "polka dot",
        "stripe": "striped",
        "leopard": "leopard print",
        "floral": "floral",
        "plaid": "plaid",
        "check": "checked",
        "spotted": "spotted",
    }.get(pattern, "")
    if not query_word:
        return []
    query = urllib.parse.urlencode({"q": query_word, "limit": "20"})
    data = ebay_json(f"{SEARCH_URL}?{query}")
    listings = []
    seen = set()
    checked = 0
    for summary in data.get("itemSummaries") or []:
        title = str(summary.get("title") or "")
        if not title_has_print(title, pattern) or not title_is_clothes(title):
            continue
        checked += 1
        if checked > 8:
            break
        for listing in listings_from_summary(summary):
            if not title_has_print(listing.title or title, pattern) or not title_is_clothes(listing.title or title):
                continue
            if listing.id in seen:
                continue
            seen.add(listing.id)
            listings.append(listing)
    return listings

def listings_like_image(summaries: list[dict], label: str, heel_mm: int = 0) -> list[Listing]:
    listings = []
    seen = set()
    checked = 0
    for summary in summaries:
        title = str(summary.get("title") or "")
        if not title_matches_style(title, label, heel_mm, ""):
            continue
        checked += 1
        if checked > 8:
            break
        for listing in listings_from_summary(summary):
            if not title_matches_style(listing.title or title, label, heel_mm, ""):
                continue
            if listing.id in seen:
                continue
            seen.add(listing.id)
            listings.append(listing)
    return listings