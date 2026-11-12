from auth import set_sizes as save_sizes
from models import User

def size_for(user: User, kind: str) -> str:
    if kind == "shoes":
        return user.shoe_size.strip()
    return user.clothes_size.strip()

def set_sizes(user_id: str, clothes_size: str, shoe_size: str) -> User | None:
    return save_sizes(user_id, clothes_size, shoe_size)
