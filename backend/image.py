from ebay import titles_from_image
from models import Piece
from name import name_from_titles

def piece_from_image(image: str) -> Piece:
    titles = titles_from_image(image)
    return name_from_titles(titles)