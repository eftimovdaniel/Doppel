import re

from ebay import listings_for_name
from models import Listing

# Nike men's and women's charts. eBay US writes the US number.
MEN_US = {35: 3, 36: 4, 37: 4.5, 38: 5.5, 39: 6.5, 40: 7, 40.5: 7.5, 41: 8, 42: 8.5, 42.5: 9, 43: 9.5, 44: 10, 44.5: 10.5, 45: 11, 45.5: 11.5, 46: 12, 47: 13, 48: 14, 49: 15}
WOMEN_US = {35: 5, 36: 6, 37: 6.5, 38: 7.5, 39: 8.5, 40: 9, 41: 10, 42: 11, 43: 12, 44: 13, 45: 14, 46: 15}

def plain(value: str) -> str:
    words = []
    for word in value.strip().lower().replace("-", " ").split():
        if word in {"size", "eu", "us", "uk"}:
            continue
        if word.startswith(("eu", "us", "uk")) and word[2:].replace(".", "", 1).isdigit():
            word = word[2:]
        words.append(word)
    return "".join(words)

def size_numbers(value: str) -> set[float]:
    text = value.lower().replace("-", " ")
    text = re.sub(r"(\d+)\s+1/2", r"\1.5", text)
    return {float(token) for token in re.findall(r"\d+(?:\.\d+)?", text)}

def shoe_equivalents(number: float) -> set[float]:
    found = {number}
    for table in (MEN_US, WOMEN_US):
        if number in table:
            found.add(table[number])
        for eu, us in table.items():
            if us == number:
                found.add(float(eu))
    return found

def same_size(listing_size: str, wanted: str, shoes: bool = False) -> bool:
    left = plain(listing_size)
    right = plain(wanted)
    if right and left == right:
        return True
    if not shoes:
        return False
    wanted_numbers = size_numbers(wanted)
    if not wanted_numbers:
        return False
    accepted = set()
    for number in wanted_numbers:
        for match in shoe_equivalents(number):
            accepted.add(round(match, 2))
            if match < 20:
                accepted.add(round(match - 0.5, 2))
                accepted.add(round(match + 0.5, 2))
    return any(round(number, 2) in accepted for number in size_numbers(listing_size))

def split_prices(listings: list[Listing], size: str, shoes: bool = False) -> tuple[list[Listing], list[Listing]]:
    matched = [item for item in listings if item.size and same_size(item.size, size, shoes)]
    fresh = sorted((item for item in matched if item.condition == "new"), key=lambda item: item.price)
    used = sorted((item for item in matched if item.condition == "used"), key=lambda item: item.price)
    return fresh, used

def for_name(name: str, size: str, kind: str = "clothes") -> tuple[list[Listing], list[Listing]]:
    if not name.strip() or name == "Unknown" or not size.strip():
        return [], []
    return split_prices(listings_for_name(name), size, kind == "shoes")

def cheapest(fresh: list[Listing], used: list[Listing]) -> float | None:
    prices = [item.price for item in (*fresh, *used)]
    return min(prices) if prices else None