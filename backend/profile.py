from auth import load_users, save_users
from models import User

def size_for(user: User, kind: str) -> str:
    if kind == "shoes":
        return user.shoe_size.strip()
    return user.clothes_size.strip()

def set_sizes(user_id: str, clothes_size: str, shoe_size: str) -> User | None:
    users = load_users()
    for user in users:
        if user.id == user_id:
            user.clothes_size = clothes_size.strip()
            user.shoe_size = shoe_size.strip()
            save_users(users)
            return user
    return None