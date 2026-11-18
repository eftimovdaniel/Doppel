from ebay import listings_for_name, listings_for_print, listings_like_image, photo_label, summaries_from_image
from models import Listing, Piece
from name import STYLE_WORDS, is_specific, name_from_titles, print_from_titles, style_name

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
    if is_specific(piece.name):
        return piece, listings_for_name(piece.name), [], True
    if piece.kind != "shoes" and piece.pattern:
        return piece, [], listings_for_print(piece.pattern), False
    if piece.label not in STYLE_WORDS:
        return piece, [], [], False
    return piece, [], listings_like_image(summaries, piece.label, piece.heel_mm), False
