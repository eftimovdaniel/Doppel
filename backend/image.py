from ebay import listings_for_name, summaries_from_image
from models import Listing, Piece
from name import is_specific, name_from_titles

def from_image(image: str) -> tuple[Piece, list[Listing], bool]:
    summaries = summaries_from_image(image)
    piece = name_from_titles([item["title"] for item in summaries])
    if not is_specific(piece.name):
        return piece, [], False
    return piece, listings_for_name(piece.name), True
