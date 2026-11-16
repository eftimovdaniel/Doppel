from ebay import listings_for_name, listings_for_print, listings_like_image, summaries_from_image
from models import Listing, Piece
from name import STYLE_WORDS, is_specific, name_from_titles, print_from_titles

def from_image(image: str) -> tuple[Piece, list[Listing], list[Listing], bool]:
    summaries = summaries_from_image(image)
    titles = [item["title"] for item in summaries]
    piece = name_from_titles(titles)
    piece.pattern = print_from_titles(titles[:15])
    if titles:
        near = name_from_titles(titles[:8])
        if near.label in STYLE_WORDS:
            piece.kind = near.kind
            piece.label = near.label
            if near.heel_mm:
                piece.heel_mm = near.heel_mm
    if is_specific(piece.name):
        return piece, listings_for_name(piece.name), [], True
    if piece.kind != "shoes" and piece.pattern:
        return piece, [], listings_for_print(piece.pattern), False
    if piece.label not in STYLE_WORDS:
        return piece, [], [], False
    return piece, [], listings_like_image(summaries, piece.label, piece.heel_mm), False
