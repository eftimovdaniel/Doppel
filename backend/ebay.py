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
from name import title_has_model, title_has_print, title_is_clothes, title_matches_style, tokens_of

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

CATEGORY_LABEL = {
    "Heels": "PUMP",
    "Sandals": "SANDAL",
    "Athletic Shoes": "SNEAKER",
    "Boots": "BOOT",
    "Coats, Jackets & Vests": "JACKET",
}

ASPECT_LABEL = {
    "pump": "PUMP",
    "pumps": "PUMP",
    "slingback": "SLING",
    "sling back": "SLING",
    "sandal": "SANDAL",
    "sandals": "SANDAL",
    "sneaker": "SNEAKER",
    "sneakers": "SNEAKER",
    "trainer": "SNEAKER",
    "boot": "BOOT",
    "boots": "BOOT",
    "loafer": "LOAFER",
    "mule": "MULE",
    "mules": "MULE",
    "peep toe": "PEEP",
}

def summary_label(summary: dict) -> str:
    found = []
    for category in summary.get("categories") or []:
        label = CATEGORY_LABEL.get(str(category.get("categoryName") or ""))
        if label and label not in found:
            found.append(label)
    if len(found) == 1:
        return found[0]
    return ""

def photo_label(summaries: list[dict]) -> str:
    counts: dict[str, int] = {}
    for summary in summaries:
        label = summary_label(summary)
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return ""
    best = max(counts, key=lambda label: counts[label])
    total = sum(counts.values())
    if counts[best] < 2 or counts[best] * 5 < total * 3:
        return ""
    return best

def aspect_style(item: dict) -> str:
    for aspect in item.get("localizedAspects") or []:
        if str(aspect.get("name", "")).strip().lower() == "style":
            return str(aspect.get("value", "")).strip().lower()
    return ""

def aspect_fits(item: dict, label: str) -> bool:
    if not label:
        return True
    mapped = ASPECT_LABEL.get(aspect_style(item), "")
    if not mapped:
        return True
    return mapped == label

def aspect_value(item: dict, name: str) -> str:
    for aspect in item.get("localizedAspects") or []:
        if str(aspect.get("name", "")).strip().lower() == name:
            return str(aspect.get("value") or "")
    return ""

def material_family(text: str) -> str:
    words = set(tokens_of(text))
    if words & {"satin", "silk"}:
        return "satin"
    if "patent" in words:
        return "patent"
    if words & {"glitter", "sequin", "sequins"}:
        return "glitter"
    if "suede" in words:
        return "suede"
    if words & {"lace", "fabric", "textile", "mesh", "cloth"}:
        return "fabric"
    if words & {"leather", "calf", "nappa"}:
        return "leather"
    return ""

def toe_family(text: str) -> str:
    words = set(tokens_of(text))
    if "peep" in words:
        return "peep"
    if words & {"pointed", "pointy"}:
        return "pointed"
    for name in ("almond", "square", "round", "open"):
        if name in words:
            return name
    return ""

def heel_family(text: str) -> str:
    words = set(tokens_of(text))
    for name in ("stiletto", "block", "kitten", "wedge", "cone", "platform"):
        if name in words:
            return name
    return ""

def stated_details(item: dict, title: str) -> dict:
    details = {
        "material": material_family(aspect_value(item, "upper material")),
        "toe": toe_family(aspect_value(item, "toe shape")),
        "heel": heel_family(aspect_value(item, "heel style")),
    }
    from_title = {
        "material": material_family(title),
        "toe": toe_family(title),
        "heel": heel_family(title),
    }
    for key, value in from_title.items():
        if not details[key] and value:
            details[key] = value
    if from_title["material"] in {"glitter", "satin", "patent", "suede"}:
        details["material"] = from_title["material"]
    return details

def majority_detail(rows: list[dict]) -> dict:
    profile = {"material": "", "toe": "", "heel": ""}
    for key in profile:
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get(key) or ""
            if value:
                counts[value] = counts.get(value, 0) + 1
        if not counts:
            continue
        best = max(counts, key=lambda value: counts[value])
        if counts[best] >= 2:
            profile[key] = best
    return profile

def contradicts(profile: dict, details: dict) -> bool:
    for key, wanted in profile.items():
        stated = details.get(key) or ""
        if wanted and stated and stated != wanted:
            return True
    return False

def odd_cut(title: str) -> str:
    text = title.lower().replace("'", "").replace("’", "")
    if "dorsay" in text:
        return "dorsay"
    if "high-low" in text or "high low" in text:
        return "highlow"
    return ""

def listings_from_summary(summary: dict, name: str = "", label: str = "", sink: list | None = None) -> list[Listing]:
    if (summary.get("price") or {}).get("value") is None or not summary.get("itemId"):
        return []
    condition = "new" if str(summary.get("conditionId", "")) == "1000" else "used"
    href = summary.get("itemHref") or f"{ITEM_URL}/{urllib.parse.quote(str(summary['itemId']), safe='')}"
    try:
        item = ebay_json(str(href))
    except MissingItem:
        return []
    if label and not aspect_fits(item, label):
        return []
    if sink is not None:
        sink.append(item)
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
            if label and not aspect_fits(child, label):
                continue
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
        for listing in listings_from_summary(summary, label=label):
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
    picked = []
    seen = set()
    checked = 0
    for summary in summaries:
        title = str(summary.get("title") or "")
        if summary_label(summary) not in ("", label):
            continue
        if not title_matches_style(title, label, heel_mm, ""):
            continue
        checked += 1
        if checked > 8:
            break
        found: list[dict] = []
        for listing in listings_from_summary(summary, label=label, sink=found):
            if not title_matches_style(listing.title or title, label, heel_mm, ""):
                continue
            if listing.id in seen:
                continue
            seen.add(listing.id)
            item = found[0] if found else {}
            picked.append((listing, stated_details(item, listing.title or title)))
    profile = majority_detail([details for _, details in picked]) if label == "PUMP" else {"material": "", "toe": "", "heel": ""}
    cuts: dict[str, int] = {}
    for listing, _details in picked:
        cut = odd_cut(listing.title)
        if cut:
            cuts[cut] = cuts.get(cut, 0) + 1
    listings = []
    for listing, details in picked:
        if contradicts(profile, details):
            continue
        cut = odd_cut(listing.title)
        if cut and cuts.get(cut, 0) < 2:
            continue
        listings.append(listing)
    if label == "PUMP":
        listings.sort(key=lambda item: 0 if {"lace", "pointed", "pointy"} & set(tokens_of(item.title)) else 1)
    return listings