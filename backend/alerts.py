import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from models import Alert, Listing, Piece
from prices import cheapest, split_prices

DAY = 24 * 60 * 60
PATH = Path(__file__).parent / "data" / "alerts.json"

def load() -> list[Alert]:
    if not PATH.exists():
        return []
    raw = json.loads(PATH.read_text() or "[]")
    return [Alert(**item) for item in raw]

def save(alerts: list[Alert]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps([asdict(alert) for alert in alerts], indent=2))

def arm(user_id: str,piece: Piece,size: str,fresh: list[Listing],used: list[Listing],) -> Alert | None:
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
    alert = Alert(id=str(uuid.uuid4()),user_id=user_id,model_name=piece.name,kind=piece.kind,label=piece.label,size=size,last_price=price,last_checked_at=now,dropped=False,)
    alerts.append(alert)
    save(alerts)
    return alert

def apply_check(alert: Alert, fresh: list[Listing], used: list[Listing], now: float) -> bool:
    price = cheapest(fresh, used)
    alert.last_checked_at = now
    if price is None or price >= alert.last_price:
        alert.dropped = False
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
            fresh, used = split_prices(fetch(alert.model_name), alert.size)
        except Exception as error:
            print(error)
            continue
        if apply_check(alert, fresh, used, now):
            told.append(alert)
        changed = True
    if changed:
        save(alerts)
    return told