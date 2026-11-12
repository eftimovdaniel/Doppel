import hashlib
import hmac
import secrets
import sqlite3
import uuid
from models import User
from db import db, user_from_row

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
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return user_from_row(row) if row else None

def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "clothes_size": user.clothes_size,
        "shoe_size": user.shoe_size,
    }

def register(name: str, email: str, password: str) -> User | None:
    user = User(id=str(uuid.uuid4()), name=name.strip(), email=email.strip().lower(), password_hash=hash_password(password), clothes_size="", shoe_size="")
    try:
        with db() as con:
            con.execute(
                "INSERT INTO users (id, name, email, password_hash, clothes_size, shoe_size) VALUES (?, ?, ?, ?, ?, ?)",
                (user.id, user.name, user.email, user.password_hash, user.clothes_size, user.shoe_size),
            )
    except sqlite3.IntegrityError:
        return None
    return user

def login(email: str, password: str) -> User | None:
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if row is None or not check_password(password, row["password_hash"]):
        return None
    return user_from_row(row)

def start_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    with db() as con:
        con.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user.id))
    return token

def user_from_token(token: str) -> User | None:
    if not token:
        return None
    with db() as con:
        row = con.execute(
            "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token = ?",
            (token,),
        ).fetchone()
    return user_from_row(row) if row else None

def reset_password(email: str, password: str) -> bool:
    email = email.strip().lower()
    with db() as con:
        cur = con.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (hash_password(password), email),
        )
        if cur.rowcount == 0:
            return False
        con.execute("DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE email = ?)", (email,))
    return True

def set_sizes(user_id: str, clothes_size: str, shoe_size: str) -> User | None:
    with db() as con:
        cur = con.execute(
            "UPDATE users SET clothes_size = ?, shoe_size = ? WHERE id = ?",
            (clothes_size.strip(), shoe_size.strip(), user_id),
        )
        if cur.rowcount == 0:
            return None
        row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return user_from_row(row) if row else None
