import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import asdict
from pathlib import Path
from models import User

PATH = Path(__file__).parent / "data" / "users.json"
SESSIONS = Path(__file__).parent / "data" / "sessions.json"

def load_users() -> list[User]:
    if not PATH.exists():
        return []
    raw = json.loads(PATH.read_text() or "[]")
    return [User(**item) for item in raw]

def save_users(users: list[User]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps([asdict(user) for user in users], indent=2))

def load_sessions() -> dict[str, str]:
    if not SESSIONS.exists():
        return {}
    raw = json.loads(SESSIONS.read_text() or "{}")
    return raw if isinstance(raw, dict) else {}

def save_sessions(sessions: dict[str, str]) -> None:
    SESSIONS.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS.write_text(json.dumps(sessions, indent=2))

def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return f"{salt}${digest.hex()}"

def check_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), stored)

def find_user(user_id: str) -> User | None:
    for user in load_users():
        if user.id == user_id:
            return user
    return None


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "clothes_size": user.clothes_size,
        "shoe_size": user.shoe_size,
    }


def register(name: str, email: str, password: str) -> User | None:
    users = load_users()
    email = email.strip().lower()
    if any(user.email == email for user in users):
        return None
    user = User(id=str(uuid.uuid4()),name=name.strip(),email=email,password_hash=hash_password(password),clothes_size="",shoe_size="",)
    users.append(user)
    save_users(users)
    return user

def login(email: str, password: str) -> User | None:
    email = email.strip().lower()
    for user in load_users():
        if user.email == email and check_password(password, user.password_hash):
            return user
    return None

def start_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    sessions = load_sessions()
    sessions[token] = user.id
    save_sessions(sessions)
    return token

def user_from_token(token: str) -> User | None:
    if not token:
        return None
    user_id = load_sessions().get(token)
    if not user_id:
        return None
    return find_user(user_id)