from __future__ import annotations

import argparse
from http.cookies import SimpleCookie
from copy import deepcopy
from datetime import datetime, timezone
import json
from mimetypes import guess_type
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from rent_watch.checker import DEFAULT_SOURCES, RentalChecker
from rent_watch.config import CITIES, COUNTRIES, DEFAULT_SOURCES_BY_COUNTRY, PROPERTY_TYPES, SOURCE_COUNTRIES, SOURCE_LABELS, city_by_id
from rent_watch.storage import ListingStore


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
SESSION_COOKIE_NAME = "rent_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def session_cookie(token: str) -> str:
    return f"{SESSION_COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax"


def clear_session_cookie() -> str:
    return f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"


def result_key(result: dict | None) -> str | None:
    if not result:
        return None
    return "|".join(
        [
            str(result.get("checkedAt", "")),
            str(result.get("fetched", 0)),
            ",".join(result.get("newListingIds", []) or []),
        ]
    )


class BackgroundWatcher:
    def __init__(self, state: "AppState") -> None:
        self.state = state
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._filters: dict = {}
        self._interval_seconds = 30
        self._checking = False
        self._last_started: str | None = None
        self._last_finished: str | None = None
        self._next_run_at: str | None = None
        self._last_result: dict | None = None
        self._last_error: str | None = None

    def start(self, filters: dict, interval_seconds: int = 30) -> dict:
        self.stop()
        interval_seconds = max(30, min(300, int(interval_seconds or 30)))
        with self._lock:
            self._filters = deepcopy(filters)
            self._interval_seconds = interval_seconds
            self._last_error = None
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run_loop, name="rental-watch", daemon=True)
            self._thread.start()
        return self.status(include_result=False)

    def stop(self, include_result: bool = False) -> dict:
        thread: threading.Thread | None
        with self._lock:
            thread = self._thread
            if thread and thread.is_alive():
                self._stop_event.set()
        if thread and thread.is_alive():
            thread.join(timeout=2)
        with self._lock:
            if self._thread is thread:
                self._thread = None
                self._checking = False
                self._next_run_at = None
        return self.status(include_result=include_result)

    def status(self, client_result_key: str | None = None, include_result: bool = True) -> dict:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            current_key = result_key(self._last_result)
            last_result = None
            if include_result and current_key != client_result_key:
                last_result = deepcopy(self._last_result)
            return {
                "running": running,
                "checking": self._checking,
                "intervalSeconds": self._interval_seconds,
                "filters": deepcopy(self._filters),
                "lastStarted": self._last_started,
                "lastFinished": self._last_finished,
                "nextRunAt": self._next_run_at,
                "lastError": self._last_error,
                "lastResultKey": current_key,
                "lastResult": last_result,
            }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                filters = deepcopy(self._filters)
                interval_seconds = self._interval_seconds
                self._checking = True
                self._last_started = utc_now()
                self._next_run_at = None
            try:
                result = self.state.run_check(filters)
                with self._lock:
                    self._last_result = result
                    self._last_error = None
            except Exception as exc:
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
            finally:
                next_run_timestamp = time.time() + interval_seconds
                with self._lock:
                    self._checking = False
                    self._last_finished = utc_now()
                    self._next_run_at = datetime.fromtimestamp(next_run_timestamp, timezone.utc).isoformat(timespec="seconds")
            if self._stop_event.wait(interval_seconds):
                break


class AccountSearchWatcher:
    def __init__(self, state: "AppState") -> None:
        self.state = state
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._checking = False
        self._last_error: str | None = None
        self._last_started: str | None = None
        self._last_finished: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run_loop, name="account-search-watch", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            if thread and thread.is_alive():
                self._stop_event.set()
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._thread is not None and self._thread.is_alive(),
                "checking": self._checking,
                "lastStarted": self._last_started,
                "lastFinished": self._last_finished,
                "lastError": self._last_error,
            }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            due_searches = self.state.store.due_saved_searches()
            for search in due_searches:
                if self._stop_event.is_set():
                    break
                with self._lock:
                    self._checking = True
                    self._last_started = utc_now()
                try:
                    self.state.run_saved_search(int(search["userId"]), int(search["id"]))
                    with self._lock:
                        self._last_error = None
                except Exception as exc:
                    with self._lock:
                        self._last_error = f"{type(exc).__name__}: {exc}"
                finally:
                    with self._lock:
                        self._checking = False
                        self._last_finished = utc_now()
            self._stop_event.wait(5)


class AppState:
    def __init__(self, db_path: Path) -> None:
        self.store = ListingStore(db_path)
        self.checker = RentalChecker(self.store)
        self._check_lock = threading.Lock()
        self.watcher = BackgroundWatcher(self)
        self.account_watcher = AccountSearchWatcher(self)
        self.account_watcher.start()

    def run_check(self, filters: dict) -> dict:
        with self._check_lock:
            return self.checker.run(filters)

    def run_saved_search(self, user_id: int, search_id: int) -> dict:
        search = self.store.get_saved_search(user_id, search_id)
        if not search:
            raise KeyError("Saved search not found.")
        with self._check_lock:
            result = self.checker.run(search["filters"])
            account_new_ids = self.store.save_search_matches(user_id, search_id, result.get("listings", []))
        result["savedSearchId"] = search_id
        result["savedSearchName"] = search["name"]
        result["accountNewCount"] = len(account_new_ids)
        result["accountNewListingIds"] = account_new_ids
        return result

    def close(self) -> None:
        self.watcher.stop()
        self.account_watcher.stop()


class RentalWatchHandler(BaseHTTPRequestHandler):
    state: AppState

    server_version = "RentalWatch/0.1"

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, payload: dict, status: int = 200, headers: list[tuple[str, str]] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE_NAME)
        return morsel.value if morsel else None

    def current_user(self) -> dict | None:
        return self.state.store.get_user_by_session(self.session_token())

    def require_user(self) -> dict | None:
        user = self.current_user()
        if not user:
            self.send_json({"error": "Sign in required."}, 401)
            return None
        return user

    def require_admin(self) -> dict | None:
        user = self.require_user()
        if not user:
            return None
        if not user.get("isAdmin"):
            self.send_json({"error": "Admin access required."}, 403)
            return None
        return user

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self.send_json(
                {
                    "countries": [{"id": key, "name": value} for key, value in COUNTRIES.items()],
                    "cities": [
                        {
                            "id": city.id,
                            "country": city.country,
                            "name": city.name,
                            "pressureNote": city.pressure_note,
                        }
                        for city in CITIES
                    ],
                    "sources": [
                        {"id": key, "name": label, "country": SOURCE_COUNTRIES.get(key)}
                        for key, label in SOURCE_LABELS.items()
                    ],
                    "propertyTypes": [{"id": key, "name": label} for key, label in PROPERTY_TYPES.items()],
                    "defaults": {
                        "country": "de",
                        "city": "berlin",
                        "sources": DEFAULT_SOURCES_BY_COUNTRY,
                        "propertyType": "any",
                        "pollSeconds": 30,
                    },
                }
            )
            return
        if parsed.path == "/api/listings":
            params = parse_qs(parsed.query)
            city_id = params.get("city", ["berlin"])[0]
            try:
                city = city_by_id(city_id)
                default_sources = DEFAULT_SOURCES_BY_COUNTRY.get(city.country, DEFAULT_SOURCES)
            except KeyError:
                default_sources = DEFAULT_SOURCES
            filters = {
                "city": city_id,
                "sources": params.get("sources", [",".join(default_sources)])[0].split(","),
                "propertyType": params.get("propertyType", ["any"])[0],
                "maxRent": params.get("maxRent", [""])[0],
                "minRooms": params.get("minRooms", [""])[0],
                "minArea": params.get("minArea", [""])[0],
                "keyword": params.get("keyword", [""])[0],
            }
            self.send_json({"listings": self.state.store.query_listings(filters)})
            return
        if parsed.path == "/api/health":
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/me":
            user = self.current_user()
            self.send_json(
                {
                    "user": user,
                    "summary": self.state.store.account_summary(user["id"]) if user else None,
                    "accountWatcher": self.state.account_watcher.status(),
                }
            )
            return
        if parsed.path == "/api/account/searches":
            user = self.require_user()
            if not user:
                return
            self.send_json(
                {
                    "searches": self.state.store.list_saved_searches(user["id"]),
                    "summary": self.state.store.account_summary(user["id"]),
                    "watcher": self.state.account_watcher.status(),
                }
            )
            return
        if parsed.path == "/api/account/search-results":
            user = self.require_user()
            if not user:
                return
            params = parse_qs(parsed.query)
            search_id = int(params.get("searchId", ["0"])[0] or 0)
            if not self.state.store.get_saved_search(user["id"], search_id):
                self.send_json({"error": "Saved search not found."}, 404)
                return
            self.send_json({"results": self.state.store.get_saved_search_results(user["id"], search_id)})
            return
        if parsed.path == "/api/account/notifications":
            user = self.require_user()
            if not user:
                return
            self.send_json({"items": self.state.store.account_notifications(user["id"])})
            return
        if parsed.path == "/api/admin/overview":
            if not self.require_admin():
                return
            self.send_json(
                {
                    **self.state.store.admin_overview(),
                    "accountWatcher": self.state.account_watcher.status(),
                    "globalWatcher": self.state.watcher.status(include_result=False),
                }
            )
            return
        if parsed.path == "/api/watch/status":
            params = parse_qs(parsed.query)
            client_key = params.get("resultKey", [None])[0]
            self.send_json(self.state.watcher.status(client_result_key=client_key))
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = parse_json_body(self)
            if parsed.path == "/api/auth/register":
                user = self.state.store.create_user(payload.get("email", ""), payload.get("password", ""))
                token = self.state.store.create_session(user["id"])
                self.send_json({"user": user, "summary": self.state.store.account_summary(user["id"])}, headers=[("Set-Cookie", session_cookie(token))])
                return
            if parsed.path == "/api/auth/login":
                user = self.state.store.authenticate_user(payload.get("email", ""), payload.get("password", ""))
                if not user:
                    self.send_json({"error": "Invalid email or password."}, 401)
                    return
                token = self.state.store.create_session(user["id"])
                self.send_json({"user": user, "summary": self.state.store.account_summary(user["id"])}, headers=[("Set-Cookie", session_cookie(token))])
                return
            if parsed.path == "/api/auth/logout":
                self.state.store.delete_session(self.session_token())
                self.send_json({"ok": True}, headers=[("Set-Cookie", clear_session_cookie())])
                return
            if parsed.path == "/api/check":
                self.send_json(self.state.run_check(payload))
                return
            if parsed.path == "/api/watch/start":
                interval_seconds = int(payload.pop("intervalSeconds", 30) or 30)
                self.send_json(self.state.watcher.start(payload, interval_seconds))
                return
            if parsed.path == "/api/watch/stop":
                self.send_json(self.state.watcher.stop())
                return
            if parsed.path == "/api/seen":
                ids = payload.get("ids")
                self.send_json({"updated": self.state.store.mark_seen(ids)})
                return
            if parsed.path == "/api/account/searches":
                user = self.require_user()
                if not user:
                    return
                search = self.state.store.create_saved_search(
                    user["id"],
                    payload.get("name", ""),
                    payload.get("filters", {}),
                    int(payload.get("intervalSeconds", 30) or 30),
                    bool(payload.get("notificationsEnabled", True)),
                )
                self.send_json({"search": search, "summary": self.state.store.account_summary(user["id"])}, 201)
                return
            if parsed.path == "/api/account/searches/update":
                user = self.require_user()
                if not user:
                    return
                search = self.state.store.update_saved_search(user["id"], int(payload.get("id", 0) or 0), payload)
                self.send_json({"search": search, "summary": self.state.store.account_summary(user["id"])})
                return
            if parsed.path == "/api/account/searches/delete":
                user = self.require_user()
                if not user:
                    return
                deleted = self.state.store.delete_saved_search(user["id"], int(payload.get("id", 0) or 0))
                self.send_json({"deleted": deleted, "summary": self.state.store.account_summary(user["id"])})
                return
            if parsed.path == "/api/account/searches/run":
                user = self.require_user()
                if not user:
                    return
                result = self.state.run_saved_search(user["id"], int(payload.get("id", 0) or 0))
                self.send_json(result)
                return
            if parsed.path == "/api/account/search-results/seen":
                user = self.require_user()
                if not user:
                    return
                updated = self.state.store.mark_search_results_seen(
                    user["id"],
                    int(payload.get("searchId", 0) or 0),
                    payload.get("listingIds"),
                )
                self.send_json({"updated": updated, "summary": self.state.store.account_summary(user["id"])})
                return
            if parsed.path == "/api/account/listing-state":
                user = self.require_user()
                if not user:
                    return
                state = self.state.store.set_listing_state(user["id"], str(payload.get("listingId", "")), payload)
                self.send_json({"state": state, "summary": self.state.store.account_summary(user["id"])})
                return
            self.send_json({"error": "Not found"}, 404)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400)
        except KeyError as exc:
            self.send_json({"error": str(exc).strip("'")}, 404)
        except Exception as exc:
            self.send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def serve_static(self, request_path: str) -> None:
        if request_path in {"", "/"}:
            file_path = STATIC_DIR / "index.html"
        else:
            safe_path = request_path.lstrip("/")
            file_path = (STATIC_DIR / safe_path).resolve()
            if not str(file_path).startswith(str(STATIC_DIR.resolve())):
                self.send_error(403)
                return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return
        content_type = guess_type(file_path.name)[0] or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local German rental watcher.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db", type=Path, default=DATA_DIR / "rentals.sqlite3")
    args = parser.parse_args()

    state = AppState(args.db)
    RentalWatchHandler.state = state
    server = ThreadingHTTPServer((args.host, args.port), RentalWatchHandler)
    print(f"Rental Watch is running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Rental Watch.")
    finally:
        state.close()
        server.server_close()


if __name__ == "__main__":
    main()
