from ebay import listings_for_category, listings_for_name, listings_for_print, listings_for_style, listings_like_image, photo_category, photo_label, summaries_from_image
from models import Listing, Piece
from name import STYLE_WORDS, is_specific, name_from_titles, print_from_titles, style_name, title_has_model

def without_same(items: list[Listing], same: list[Listing], name: str) -> list[Listing]:
    skip = {item.id for item in same}
    kept = []
    for item in items:
        if item.id in skip:
            continue
        if name and is_specific(name) and title_has_model(name, item.title):
            continue
        skip.add(item.id)
        kept.append(item)
    return kept

def from_image(image: str) -> tuple[Piece, list[Listing], list[Listing], bool]:
    summaries = summaries_from_image(image)
    titles = [item["title"] for item in summaries]
    piece = name_from_titles(titles)
    piece.pattern = print_from_titles(titles[:15])
    seen = photo_label(summaries)
    if seen in STYLE_WORDS and not is_specific(piece.name):
        piece.label = seen
        if seen in {"PUMP", "SANDAL", "BOOT", "LOAFER", "SNEAKER", "HEEL"}:
            piece.kind = "shoes"
        piece.name = style_name(piece.name, piece.label)
    if titles:
        near = name_from_titles(titles[:8])
        specific = {"PUMP", "SANDAL", "BOOT", "LOAFER"}
        if piece.label not in specific and near.label in specific:
            piece.kind = near.kind
            piece.label = near.label
        if not piece.heel_mm and near.heel_mm:
            piece.heel_mm = near.heel_mm
    if is_specific(piece.name) and piece.label != "BAG":
        same = listings_for_name(piece.name)
        alike = listings_for_style(piece.name, piece.label, piece.heel_mm) if piece.label in STYLE_WORDS else []
        return piece, same, without_same(alike, same, piece.name), True
    if piece.kind != "shoes" and piece.pattern:
        return piece, [], listings_for_print(piece.pattern), False
    if piece.label not in STYLE_WORDS:
        category = photo_category(summaries)
        if not category:
            return piece, [], [], False
        found = listings_for_category(summaries, category)
        piece.kind = "other"
        piece.label = category
        agreed = name_from_titles([item.title for item in found]) if found else None
        if agreed and is_specific(agreed.name):
            piece.name = agreed.name
            same = [item for item in found if title_has_model(piece.name, item.title)] or found
            return piece, same, without_same(found, same, piece.name), True
        piece.name = category
        return piece, [], found, False
    similar = listings_like_image(summaries, piece.label, piece.heel_mm)
    if similar:
        agreed = name_from_titles([item.title for item in similar])
        if is_specific(agreed.name) and piece.label != "BAG":
            piece.name = agreed.name
            if agreed.label in STYLE_WORDS:
                piece.label = agreed.label
            same = [item for item in similar if title_has_model(piece.name, item.title)]
            if not same:
                same = listings_for_name(piece.name)
            alike = listings_for_style(piece.name, piece.label, piece.heel_mm)
            return piece, same, without_same(similar + alike, same, piece.name), True
    return piece, [], similar, False
