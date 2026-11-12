import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from models import Alert, User

PATH = Path(os.environ.get("DOPPEL_DB") or Path(__file__).parent / "data" / "doppel.db")
DATA = PATH.parent

def connect() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    fresh = not PATH.exists()
    con = sqlite3.connect(PATH)
    con.row_factory = sqlite3.Row
    if fresh:
        create(con)
        migrate(con)
    return con

@contextmanager
def db():
    con = connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def create(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            clothes_size TEXT NOT NULL DEFAULT '',
            shoe_size TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            kind TEXT NOT NULL,
            label TEXT NOT NULL,
            size TEXT NOT NULL,
            last_price REAL NOT NULL,
            last_checked_at REAL NOT NULL,
            dropped INTEGER NOT NULL,
            UNIQUE (user_id, model_name, size)
        );
    """)

def read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    raw = json.loads(path.read_text() or "")
    return raw if raw else fallback

def migrate(con: sqlite3.Connection) -> None:
    users = read_json(DATA / "users.json", [])
    sessions = read_json(DATA / "sessions.json", {})
    alerts = read_json(DATA / "alerts.json", [])
    if isinstance(users, list):
        for item in users:
            con.execute(
                "INSERT OR IGNORE INTO users (id, name, email, password_hash, clothes_size, shoe_size) VALUES (?, ?, ?, ?, ?, ?)",
                (item["id"], item["name"], item["email"], item["password_hash"], item.get("clothes_size", ""), item.get("shoe_size", "")),
            )
    if isinstance(sessions, dict):
        for token, user_id in sessions.items():
            con.execute("INSERT OR IGNORE INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    if isinstance(alerts, list):
        for item in alerts:
            con.execute(
                """INSERT OR IGNORE INTO alerts
                   (id, user_id, model_name, kind, label, size, last_price, last_checked_at, dropped)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item["id"], item["user_id"], item["model_name"], item["kind"], item.get("label", ""), item["size"], item["last_price"], item["last_checked_at"], int(bool(item.get("dropped")))),
            )
    con.commit()

def user_from_row(row: sqlite3.Row) -> User:
    return User(id=row["id"], name=row["name"], email=row["email"], password_hash=row["password_hash"], clothes_size=row["clothes_size"], shoe_size=row["shoe_size"])

def alert_from_row(row: sqlite3.Row) -> Alert:
    return Alert(id=row["id"], user_id=row["user_id"], model_name=row["model_name"], kind=row["kind"], label=row["label"], size=row["size"], last_price=row["last_price"], last_checked_at=row["last_checked_at"], dropped=bool(row["dropped"]))

def alert_values(alert: Alert) -> tuple:
    return (alert.id, alert.user_id, alert.model_name, alert.kind, alert.label, alert.size, alert.last_price, alert.last_checked_at, int(alert.dropped))
