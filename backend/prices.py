from ebay import listings_for_name
from models import Listing

def same_size(listing_size: str, wanted: str) -> bool:
    def norm(value: str) -> str:
        words = []
        for word in value.strip().lower().replace("-", " ").split():
            if word in {"size", "eu", "us", "uk"}:
                continue
            if word.startswith(("eu", "us", "uk")) and word[2:].replace(".", "", 1).isdigit():
                word = word[2:]
            words.append(word)
        return "".join(words)

    left = norm(listing_size)
    right = norm(wanted)
    return bool(right) and left == right

def split_prices(listings: list[Listing], size: str) -> tuple[list[Listing], list[Listing]]:
    matched = [item for item in listings if item.size and same_size(item.size, size)]
    fresh = sorted((item for item in matched if item.condition == "new"), key=lambda item: item.price)
    used = sorted((item for item in matched if item.condition == "used"), key=lambda item: item.price)
    return fresh, used

def for_name(name: str, size: str) -> tuple[list[Listing], list[Listing]]:
    if not name.strip() or name == "Unknown" or not size.strip():
        return [], []
    return split_prices(listings_for_name(name), size)

def cheapest(fresh: list[Listing], used: list[Listing]) -> float | None:
    prices = [item.price for item in (*fresh, *used)]
    return min(prices) if prices else None