import math
import re

from models import Piece, PieceKind

STOP = {"size", "mens", "men", "menswear", "womens", "women", "womenswear","the", "a", "an", "with", "for", "and", "of", "in","new", "used", "nwt", "nwot", "preowned", 
        "pre", "owned", "authentic", "original", "fit", "pair", "free", "shipping","eu", "us", "uk", "vintage", "rare", "excellent", "good", "condition", }

COLORS = [ "dark blue", "light blue", "navy blue", "navy", "black", "white", "grey", "gray", "beige", "cream", "brown", "green", "red", "pink", "blue", "purple", "yellow", "orange",]

GARMENTS = [
    ("jacket", "JACKET", "clothes"), ("coat", "COAT", "clothes"),
    ("jeans", "JEANS", "clothes"), ("jean", "JEANS", "clothes"),("denim", "JEANS", "clothes"),
    ("hoodie", "HOODIE", "clothes"),("shirt", "SHIRT", "clothes"),("tee", "SHIRT", "clothes"),
    ("pants", "PANTS", "clothes"),("trousers", "PANTS", "clothes"),("trouser", "PANTS", "clothes"),
    ("dress", "DRESS", "clothes"),("skirt", "SKIRT", "clothes"),
    ("knit", "KNIT", "clothes"),("sweater", "KNIT", "clothes"),
    ("sneakers", "SNEAKER", "shoes"),("sneaker", "SNEAKER", "shoes"),("shoes", "SNEAKER", "shoes"),("shoe", "SNEAKER", "shoes"),("trainers", "SNEAKER", "shoes"),("trainer", "SNEAKER", "shoes"),
    ("boots", "BOOT", "shoes"),("boot", "BOOT", "shoes"),
    ("loafers", "LOAFER", "shoes"),("loafer", "LOAFER", "shoes"),("dunk", "SNEAKER", "shoes"),
]

def normalize(title: str) -> str:
    text = title.lower()
    text = re.sub(r"levi'?s", "levi's", text)
    text = re.sub(r"[^a-z0-9' ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def is_size_token(word: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}(\.\d)?", word) or re.fullmatch(r"[wl]\d{2}", word))

def tokens_of(title: str) -> list[str]:
    return [word for word in normalize(title).split(" ")
        if word and word not in STOP and not is_size_token(word)
    ]


def title_case(phrase: str) -> str:
    words = []
    for word in phrase.split(" "):
        if not word:
            continue
        words.append("Levi's" if word == "levi's" else word[0].upper() + word[1:])
    return " ".join(words)

def color_words() -> set[str]:
    found = set()
    for color in COLORS:
        found.update(color.split(" "))
    return found

def grams(words: list[str]) -> list[str]:
    found = []
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            found.append(" ".join(words[start:end]))
    return found

def agreed_phrase(docs: list[list[str]]) -> str:
    counts = {}
    for words in docs:
        for phrase in set(grams(words)):
            counts[phrase] = counts.get(phrase, 0) + 1
    need = math.ceil(len(docs) * 0.6)
    colors = color_words()
    best = ""
    for phrase, count in counts.items():
        if count < need:
            continue
        words = [word for word in phrase.split(" ") if word not in colors]
        cleaned = " ".join(words)
        if not cleaned:
            continue
        best_count = len(best.split(" ")) if best else 0
        if len(words) > best_count or (len(words) == best_count and len(cleaned) > len(best)):
            best = cleaned
    return best

def most_common(items: list[str]) -> str:
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    best = ""
    best_count = 0
    for item, count in counts.items():
        if count > best_count:
            best = item
            best_count = count
    return best

def detect_color(titles: list[str]) -> str:
    docs = [normalize(title) for title in titles]
    need = math.ceil(len(docs) * 0.5)
    for color in sorted(COLORS, key=len, reverse=True):
        count = sum(1 for doc in docs if color in doc)
        if count >= need:
            return color
    return ""

def name_from_titles(titles: list[str]) -> Piece:
    usable = [title.strip() for title in titles if title.strip()]
    docs = []
    for title in usable:
        tokens = tokens_of(title)
        if tokens:
            docs.append(tokens)
    hits = []
    for words in docs:
        for word in words:
            for token, label, kind in GARMENTS:
                if word == token:
                    hits.append((label, kind))
    kind: PieceKind = "shoes" if any(hit_kind == "shoes" for _, hit_kind in hits) else "clothes"
    labels = [label for label, hit_kind in hits if hit_kind == kind]
    label = most_common(labels) or ("SNEAKER" if kind == "shoes" else "PIECE")
    if not docs:
        return Piece(name="Unknown", kind=kind, label=label)
    phrase = agreed_phrase(docs)
    if len(phrase.split(" ")) >= 3:
        return Piece(name=title_case(phrase), kind=kind, label=label)
    colors = color_words()
    garment_tokens = {token for token, _, _ in GARMENTS}
    brand_tokens = [
        word
        for words in docs
        for word in words
        if word not in colors and not re.fullmatch(r"\d{3,4}", word) and word not in garment_tokens]
    brand = title_case(most_common(brand_tokens) or docs[0][0] or "Unknown")
    type_number = most_common([
        word
        for words in docs
        for word in words
        if re.fullmatch(r"\d{3,4}", word)])
    color = detect_color(usable)
    head = " ".join(part for part in (brand, type_number) if part)
    name = f"{head}, {color}" if color else head
    return Piece(name=name, kind=kind, label=label)