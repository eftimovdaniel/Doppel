import json
import os
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from alerts import arm, check_due, load as load_alerts
from auth import login, public_user, register, start_session, user_from_token
from ebay import env, listings_for_name, titles_from_image
from models import Piece
from name import name_from_titles
from prices import split_prices
from profile import set_sizes, size_for

def watch() -> None:
    while True:
        try:
            check_due(listings_for_name)
        except Exception as error:
            print(error)
        threading.Event().wait(60 * 60)

class Handler(BaseHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 8_000_000:
            raise ValueError("too large")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        data = json.loads(raw.decode())
        if not isinstance(data, dict):
            raise ValueError("body must be an object")
        return data

    def bearer(self) -> str:
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header[7:].strip()
        return ""

    def current_user(self):
        user = user_from_token(self.bearer())
        if not user:
            self.send_json(401, {"error": "login"})
        return user

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path != "/alerts":
            self.send_json(404, {"error": "not found"})
            return
        user = self.current_user()
        if not user:
            return
        check_due(listings_for_name)
        mine = [asdict(alert) for alert in load_alerts() if alert.user_id == user.id]
        self.send_json(200, {"alerts": mine})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self.read_json()
        except (json.JSONDecodeError, ValueError):
            self.send_json(400, {"error": "bad json"})
            return
        if path == "/register":
            self.register(body)
        elif path == "/login":
            self.sign_in(body)
        elif path == "/profile":
            self.profile(body)
        elif path == "/recognize":
            self.recognize(body)
        elif path == "/alerts":
            self.create_alert(body)
        else:
            self.send_json(404, {"error": "not found"})

    def register(self, body: dict) -> None:
        name = str(body.get("name", "")).strip()
        email = str(body.get("email", "")).strip()
        password = str(body.get("password", ""))
        if not name or not email or not password:
            self.send_json(400, {"error": "name, email, password"})
            return
        user = register(name, email, password)
        if user is None:
            self.send_json(409, {"error": "email is taken"})
            return
        self.send_json(200, {"token": start_session(user), "user": public_user(user)})

    def sign_in(self, body: dict) -> None:
        user = login(str(body.get("email", "")), str(body.get("password", "")))
        if user is None:
            self.send_json(401, {"error": "login"})
            return
        self.send_json(200, {"token": start_session(user), "user": public_user(user)})

    def profile(self, body: dict) -> None:
        user = self.current_user()
        if not user:
            return
        updated = set_sizes(user.id,str(body.get("clothes_size", "")),str(body.get("shoe_size", "")),)
        self.send_json(200, {"user": public_user(updated)})

    def recognize(self, body: dict) -> None:
        user = self.current_user()
        if not user:
            return
        image = str(body.get("image", "")).strip()
        if not image:
            self.send_json(400, {"error": "image"})
            return
        try:
            titles = titles_from_image(image)
            piece = name_from_titles(titles)
            size = size_for(user, piece.kind)
            listings = [] if piece.name == "Unknown" else listings_for_name(piece.name)
            fresh, used = split_prices(listings, size)
        except RuntimeError as error:
            self.send_json(502, {"error": str(error)})
            return
        self.send_json(200, {"piece": {"name": piece.name, "kind": piece.kind, "label": piece.label},"size": size,"new": [asdict(item) for item in fresh],"used": [asdict(item) for item in used],})

    def create_alert(self, body: dict) -> None:
        user = self.current_user()
        if not user:
            return
        kind = body.get("kind")
        name = str(body.get("name", "")).strip()
        if kind not in ("clothes", "shoes") or not name:
            self.send_json(400, {"error": "name, kind"})
            return
        piece = Piece(name=name, kind=kind, label=str(body.get("label", "")).strip())
        size = size_for(user, piece.kind)
        try:
            fresh, used = split_prices(listings_for_name(piece.name), size)
        except RuntimeError as error:
            self.send_json(502, {"error": str(error)})
            return
        alert = arm(user.id, piece, size, fresh, used)
        if alert is None:
            self.send_json(400, {"error": "no price"})
            return
        self.send_json(200, asdict(alert))

def main() -> None:
    port = int(env("PORT") or os.environ.get("PORT") or "8787")
    threading.Thread(target=watch, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Doppel backend on http://127.0.0.1:{port}")
    server.serve_forever()

if __name__ == "__main__":
    main()