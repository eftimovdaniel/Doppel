import time
import uuid
from models import Alert, Listing, Piece
from prices import cheapest, split_prices
from db import alert_from_row, alert_values, db

DAY = 24 * 60 * 60

def load() -> list[Alert]:
    with db() as con:
        rows = con.execute("SELECT * FROM alerts").fetchall()
    return [alert_from_row(row) for row in rows]

def save(alerts: list[Alert]) -> None:
    with db() as con:
        con.execute("DELETE FROM alerts")
        con.executemany(
            """INSERT INTO alerts
               (id, user_id, model_name, kind, label, size, last_price, last_checked_at, dropped)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [alert_values(alert) for alert in alerts],
        )

def arm(user_id: str, piece: Piece, size: str, fresh: list[Listing], used: list[Listing]) -> Alert | None:
    price = cheapest(fresh, used)
    if not size.strip() or price is None:
        return None
    alerts = load()
    now = time.time()
    for alert in alerts:
        if alert.user_id == user_id and alert.model_name == piece.name and alert.size == size:
            alert.last_price = price
            alert.last_checked_at = now
            alert.dropped = False
            alert.kind = piece.kind
            alert.label = piece.label
            save(alerts)
            return alert
    alert = Alert(id=str(uuid.uuid4()), user_id=user_id, model_name=piece.name, kind=piece.kind, label=piece.label, size=size, last_price=price, last_checked_at=now, dropped=False)
    alerts.append(alert)
    save(alerts)
    return alert

def apply_check(alert: Alert, fresh: list[Listing], used: list[Listing], now: float) -> bool:
    price = cheapest(fresh, used)
    alert.last_checked_at = now
    if price is None or price >= alert.last_price:
        return False
    alert.last_price = price
    alert.dropped = True
    return True

def check_due(fetch) -> list[Alert]:
    alerts = load()
    now = time.time()
    told = []
    changed = False
    for alert in alerts:
        if now - alert.last_checked_at < DAY:
            continue
        try:
            fresh, used = split_prices(fetch(alert.model_name), alert.size, alert.kind == "shoes")
        except Exception as error:
            print(error)
            continue
        if apply_check(alert, fresh, used, now):
            told.append(alert)
        changed = True
    if changed:
        save(alerts)
    return told
