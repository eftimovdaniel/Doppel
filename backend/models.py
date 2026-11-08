from dataclasses import dataclass
from typing import Literal

PieceKind = Literal["clothes", "shoes"] #golemina na obleka i obuvki
Condition = Literal["new", "used"]  # dali e novo ili ne

@dataclass
class User:
    id: str
    name: str
    email: str
    password_hash: str
    clothes_size: str
    shoe_size: str

@dataclass
class Piece:
    name: str   #ime: Nike, Levis....
    kind: PieceKind
    label: str

@dataclass
class Listing:
    id: str
    price: float
    currency: str
    condition: Condition
    size: str
    where: str

@dataclass
class Alert:
    id: str
    user_id: str
    model_name: str
    kind: PieceKind
    label: str
    size: str
    last_price: float
    last_checked_at: float
    dropped: bool
