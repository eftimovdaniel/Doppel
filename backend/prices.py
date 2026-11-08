from models import Listing

def same_size(listing_size: str, wanted: str) -> bool:  
    def norm(value: str) -> str:
        text = value.strip().lower()
        for word in ("size", "eu", "us", "uk"):
            text = text.replace(word, " ")
        return "".join(text.split())
    left = norm(listing_size)
    right = norm(wanted)
    return bool(right) and left == right

def split_prices(listings: list[Listing], size: str) -> tuple[list[Listing], list[Listing]]:
    matched = [item for item in listings if item.size and same_size(item.size, size)]
    fresh = sorted((item for item in matched if item.condition == "new"), key=lambda item: item.price)
    used = sorted((item for item in matched if item.condition == "used"), key=lambda item: item.price)
    return fresh, used

def cheapest(fresh: list[Listing], used: list[Listing]) -> float | None:
    prices = [item.price for item in (*fresh, *used)]
    return min(prices) if prices else None