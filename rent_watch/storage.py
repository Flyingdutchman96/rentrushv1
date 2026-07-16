from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
from pathlib import Path

from .config import SOURCE_LABELS
from .sources import Listing, listing_matches_filters, title_is_bad


SESSION_DAYS = 30
PASSWORD_ITERATIONS = 220_000
ACCOUNT_LISTING_STATUSES = {"new", "interested", "contacted", "viewing", "applied", "rejected"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def configured_admin_emails() -> set[str]:
    raw = os.environ.get("RENT_WATCH_ADMIN_EMAILS", "")
    return {normalize_email(item) for item in raw.split(",") if normalize_email(item)}


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations, salt, expected = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def is_parser_artifact(row: sqlite3.Row | dict) -> bool:
    getter = row.get if isinstance(row, dict) else lambda key, default=None: row[key] if key in row.keys() else default
    source = str(getter("source", "") or "")
    title = str(getter("title", "") or "")
    url = str(getter("url", "") or "")
    if source == "wg_gesucht" and (
        "#collapse" in url
        or "asset_id=" in url
        or title.startswith("Anzeigenbild:")
        or title == "Hilfe / Kontakt"
    ):
        return True
    return title_is_bad(title)


class ListingStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS listings (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    city_id TEXT NOT NULL,
                    listing_type TEXT NOT NULL,
                    rent_eur INTEGER,
                    area_sqm REAL,
                    rooms REAL,
                    location TEXT,
                    image_url TEXT,
                    raw_text TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    seen INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            existing_columns = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(listings)").fetchall()
            }
            if "image_url" not in existing_columns:
                self._conn.execute("ALTER TABLE listings ADD COLUMN image_url TEXT")
            self._conn.execute(
                """
                DELETE FROM listings
                WHERE source = 'wg_gesucht'
                  AND (
                    url LIKE '%#collapse%'
                    OR url LIKE '%asset_id=%'
                    OR title LIKE 'Anzeigenbild:%'
                    OR title = 'Hilfe / Kontakt'
                  )
                """
            )
            artifact_ids = [
                row["id"]
                for row in self._conn.execute("SELECT id, source, title, url FROM listings").fetchall()
                if is_parser_artifact(row)
            ]
            if artifact_ids:
                placeholders = ",".join("?" for _ in artifact_ids)
                self._conn.execute(f"DELETE FROM listings WHERE id IN ({placeholders})", artifact_ids)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )
            existing_user_columns = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(users)").fetchall()
            }
            if "is_admin" not in existing_user_columns:
                self._conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    filters_json TEXT NOT NULL,
                    interval_seconds INTEGER NOT NULL DEFAULT 30,
                    notifications_enabled INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_checked TEXT,
                    last_new_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_results (
                    user_id INTEGER NOT NULL,
                    search_id INTEGER NOT NULL,
                    listing_id TEXT NOT NULL,
                    first_matched TEXT NOT NULL,
                    last_matched TEXT NOT NULL,
                    seen INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (search_id, listing_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (search_id) REFERENCES saved_searches(id) ON DELETE CASCADE,
                    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_listing_state (
                    user_id INTEGER NOT NULL,
                    listing_id TEXT NOT NULL,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    hidden INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'new',
                    note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, listing_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_city_source ON listings(city_id, source)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings(last_seen DESC)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_searches_active ON saved_searches(is_active, last_checked)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_search_results_user ON search_results(user_id, seen)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_search_results_listing ON search_results(listing_id)")
            self._sync_env_admins()
            self._ensure_one_admin()

    def upsert_listings(self, listings: list[Listing]) -> list[str]:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new_ids: list[str] = []
        with self._lock, self._conn:
            for listing in listings:
                listing_id = listing.id
                existed = self._conn.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,)).fetchone()
                if not existed:
                    new_ids.append(listing_id)
                self._conn.execute(
                    """
                    INSERT INTO listings (
                        id, source, title, url, city_id, listing_type, rent_eur,
                        area_sqm, rooms, location, image_url, raw_text, first_seen, last_seen, seen
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        listing_type=excluded.listing_type,
                        rent_eur=excluded.rent_eur,
                        area_sqm=excluded.area_sqm,
                        rooms=excluded.rooms,
                        location=excluded.location,
                        image_url=excluded.image_url,
                        raw_text=excluded.raw_text,
                        last_seen=excluded.last_seen
                    """,
                    (
                        listing_id,
                        listing.source,
                        listing.title,
                        listing.url,
                        listing.city_id,
                        listing.listing_type,
                        listing.rent_eur,
                        listing.area_sqm,
                        listing.rooms,
                        listing.location,
                        listing.image_url,
                        listing.raw_text,
                        now,
                        now,
                    ),
                )
        return new_ids

    def count_existing(self, city_id: str, sources: list[str]) -> int:
        if not sources:
            return 0
        placeholders = ",".join("?" for _ in sources)
        with self._lock:
            row = self._conn.execute(
                f"SELECT COUNT(*) AS count FROM listings WHERE city_id = ? AND source IN ({placeholders})",
                [city_id, *sources],
            ).fetchone()
        return int(row["count"] if row else 0)

    def query_listings(self, filters: dict, limit: int | None = None) -> list[dict]:
        city_id = filters.get("city")
        sources = filters.get("sources") or []
        params: list[object] = []
        clauses: list[str] = []
        if city_id:
            clauses.append("city_id = ?")
            params.append(city_id)
        if sources:
            placeholders = ",".join("?" for _ in sources)
            clauses.append(f"source IN ({placeholders})")
            params.extend(sources)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT ?"
            params.append(limit * 3)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM listings {where_sql} ORDER BY last_seen DESC, first_seen DESC{limit_sql}",
                params,
            ).fetchall()
        results = [dict(row) for row in rows]
        filtered = [row for row in results if not is_parser_artifact(row) and listing_matches_filters(row, filters)]
        for row in filtered:
            row["source_label"] = SOURCE_LABELS.get(row["source"], row["source"])
        return filtered[:limit] if limit is not None else filtered

    def mark_seen(self, ids: list[str] | None = None) -> int:
        with self._lock, self._conn:
            if ids:
                placeholders = ",".join("?" for _ in ids)
                cursor = self._conn.execute(f"UPDATE listings SET seen = 1 WHERE id IN ({placeholders})", ids)
            else:
                cursor = self._conn.execute("UPDATE listings SET seen = 1")
        return cursor.rowcount

    def create_user(self, email: str, password: str) -> dict:
        email = normalize_email(email)
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a valid email address.")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters.")
        created_at = now_iso()
        try:
            with self._lock, self._conn:
                user_count = self._conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
                is_admin = 1 if user_count == 0 or email in configured_admin_emails() else 0
                cursor = self._conn.execute(
                    "INSERT INTO users (email, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
                    (email, hash_password(password), is_admin, created_at),
                )
                user_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with that email already exists.") from exc
        return {"id": user_id, "email": email, "isAdmin": bool(is_admin), "createdAt": created_at}

    def authenticate_user(self, email: str, password: str) -> dict | None:
        email = normalize_email(email)
        with self._lock, self._conn:
            row = self._conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return None
            self._conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_iso(), row["id"]))
        return self._user_from_row(row)

    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        created_at = now_iso()
        expires_at = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + SESSION_DAYS * 86400, timezone.utc).isoformat(timespec="seconds")
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user_id, created_at, expires_at),
            )
        return token

    def get_user_by_session(self, token: str | None) -> dict | None:
        if not token:
            return None
        now = datetime.now(timezone.utc)
        with self._lock, self._conn:
            row = self._conn.execute(
                """
                SELECT users.id, users.email, users.created_at, sessions.expires_at
                , users.is_admin
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()
            if not row:
                return None
            expires_at = parse_iso(row["expires_at"])
            if expires_at is None or expires_at <= now:
                self._conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                return None
        return self._user_from_row(row)

    def delete_session(self, token: str | None) -> None:
        if not token:
            return
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def create_saved_search(self, user_id: int, name: str, filters: dict, interval_seconds: int = 30, notifications_enabled: bool = True) -> dict:
        name = (name or "").strip()[:90] or "Saved search"
        interval_seconds = max(30, min(3600, int(interval_seconds or 30)))
        timestamp = now_iso()
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO saved_searches (
                    user_id, name, filters_json, interval_seconds, notifications_enabled,
                    is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (user_id, name, json.dumps(filters, sort_keys=True), interval_seconds, 1 if notifications_enabled else 0, timestamp, timestamp),
            )
            search_id = int(cursor.lastrowid)
        return self.get_saved_search(user_id, search_id) or {}

    def get_saved_search(self, user_id: int, search_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM saved_searches WHERE user_id = ? AND id = ?",
                (user_id, search_id),
            ).fetchone()
        return self._saved_search_from_row(row) if row else None

    def list_saved_searches(self, user_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    saved_searches.*,
                    COUNT(search_results.listing_id) AS stored_count,
                    COALESCE(SUM(CASE WHEN search_results.seen = 0 THEN 1 ELSE 0 END), 0) AS unseen_count
                FROM saved_searches
                LEFT JOIN search_results ON search_results.search_id = saved_searches.id
                WHERE saved_searches.user_id = ?
                GROUP BY saved_searches.id
                ORDER BY saved_searches.updated_at DESC, saved_searches.created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._saved_search_from_row(row) for row in rows]

    def update_saved_search(self, user_id: int, search_id: int, updates: dict) -> dict:
        allowed = {
            "name": "name",
            "filters": "filters_json",
            "intervalSeconds": "interval_seconds",
            "notificationsEnabled": "notifications_enabled",
            "isActive": "is_active",
        }
        values: dict[str, object] = {}
        for key, column in allowed.items():
            if key not in updates:
                continue
            value = updates[key]
            if key == "name":
                value = (str(value or "").strip()[:90] or "Saved search")
            elif key == "filters":
                value = json.dumps(value or {}, sort_keys=True)
            elif key == "intervalSeconds":
                value = max(30, min(3600, int(value or 30)))
            elif key in {"notificationsEnabled", "isActive"}:
                value = 1 if value else 0
            values[column] = value
        if not values:
            existing = self.get_saved_search(user_id, search_id)
            if not existing:
                raise KeyError("Saved search not found.")
            return existing
        values["updated_at"] = now_iso()
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._lock, self._conn:
            cursor = self._conn.execute(
                f"UPDATE saved_searches SET {assignments} WHERE user_id = ? AND id = ?",
                [*values.values(), user_id, search_id],
            )
            if cursor.rowcount == 0:
                raise KeyError("Saved search not found.")
        return self.get_saved_search(user_id, search_id) or {}

    def delete_saved_search(self, user_id: int, search_id: int) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute("DELETE FROM saved_searches WHERE user_id = ? AND id = ?", (user_id, search_id))
        return cursor.rowcount

    def due_saved_searches(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        with self._lock:
            rows = self._conn.execute("SELECT * FROM saved_searches WHERE is_active = 1 ORDER BY last_checked ASC").fetchall()
        due: list[dict] = []
        for row in rows:
            last_checked = parse_iso(row["last_checked"])
            interval_seconds = max(30, int(row["interval_seconds"] or 30))
            if last_checked is None or (now - last_checked).total_seconds() >= interval_seconds:
                due.append(self._saved_search_from_row(row))
        return due

    def save_search_matches(self, user_id: int, search_id: int, listings: list[dict]) -> list[str]:
        timestamp = now_iso()
        new_ids: list[str] = []
        with self._lock, self._conn:
            for listing in listings:
                listing_id = listing.get("id")
                if not listing_id:
                    continue
                existed = self._conn.execute(
                    "SELECT 1 FROM search_results WHERE search_id = ? AND listing_id = ?",
                    (search_id, listing_id),
                ).fetchone()
                if not existed:
                    new_ids.append(str(listing_id))
                self._conn.execute(
                    """
                    INSERT INTO search_results (user_id, search_id, listing_id, first_matched, last_matched, seen)
                    VALUES (?, ?, ?, ?, ?, 0)
                    ON CONFLICT(search_id, listing_id) DO UPDATE SET
                        last_matched = excluded.last_matched
                    """,
                    (user_id, search_id, listing_id, timestamp, timestamp),
                )
            self._conn.execute(
                """
                UPDATE saved_searches
                SET last_checked = ?, last_new_count = ?, updated_at = ?
                WHERE user_id = ? AND id = ?
                """,
                (timestamp, len(new_ids), timestamp, user_id, search_id),
            )
        return new_ids

    def mark_saved_search_checked(self, user_id: int, search_id: int) -> None:
        timestamp = now_iso()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE saved_searches SET last_checked = ?, last_new_count = 0, updated_at = ? WHERE user_id = ? AND id = ?",
                (timestamp, timestamp, user_id, search_id),
            )

    def get_saved_search_results(self, user_id: int, search_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    listings.*,
                    search_results.first_matched AS matched_at,
                    search_results.last_matched AS last_matched,
                    search_results.seen AS search_seen,
                    COALESCE(user_listing_state.favorite, 0) AS favorite,
                    COALESCE(user_listing_state.hidden, 0) AS hidden,
                    COALESCE(user_listing_state.status, 'new') AS account_status,
                    COALESCE(user_listing_state.note, '') AS note
                FROM search_results
                JOIN listings ON listings.id = search_results.listing_id
                LEFT JOIN user_listing_state
                    ON user_listing_state.user_id = search_results.user_id
                    AND user_listing_state.listing_id = search_results.listing_id
                WHERE search_results.user_id = ? AND search_results.search_id = ?
                ORDER BY search_results.last_matched DESC, search_results.first_matched DESC
                """,
                (user_id, search_id),
            ).fetchall()
        results = [dict(row) for row in rows if not is_parser_artifact(row)]
        for row in results:
            row["source_label"] = SOURCE_LABELS.get(row["source"], row["source"])
            row["is_new"] = not bool(row.get("search_seen"))
        return results

    def mark_search_results_seen(self, user_id: int, search_id: int, listing_ids: list[str] | None = None) -> int:
        params: list[object] = [user_id, search_id]
        filter_sql = ""
        if listing_ids:
            placeholders = ",".join("?" for _ in listing_ids)
            filter_sql = f" AND listing_id IN ({placeholders})"
            params.extend(listing_ids)
        with self._lock, self._conn:
            cursor = self._conn.execute(
                f"UPDATE search_results SET seen = 1 WHERE user_id = ? AND search_id = ?{filter_sql}",
                params,
            )
        return cursor.rowcount

    def set_listing_state(self, user_id: int, listing_id: str, payload: dict) -> dict:
        favorite = 1 if payload.get("favorite") else 0
        hidden = 1 if payload.get("hidden") else 0
        status = str(payload.get("status") or "new")
        if status not in ACCOUNT_LISTING_STATUSES:
            status = "new"
        note = str(payload.get("note") or "")[:800]
        timestamp = now_iso()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO user_listing_state (user_id, listing_id, favorite, hidden, status, note, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, listing_id) DO UPDATE SET
                    favorite = excluded.favorite,
                    hidden = excluded.hidden,
                    status = excluded.status,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (user_id, listing_id, favorite, hidden, status, note, timestamp),
            )
        return {
            "listingId": listing_id,
            "favorite": bool(favorite),
            "hidden": bool(hidden),
            "status": status,
            "note": note,
            "updatedAt": timestamp,
        }

    def account_notifications(self, user_id: int, limit: int = 40) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    saved_searches.id AS search_id,
                    saved_searches.name AS search_name,
                    listings.id AS listing_id,
                    listings.title,
                    listings.url,
                    listings.source,
                    listings.rent_eur,
                    search_results.first_matched
                FROM search_results
                JOIN saved_searches ON saved_searches.id = search_results.search_id
                JOIN listings ON listings.id = search_results.listing_id
                WHERE search_results.user_id = ?
                  AND search_results.seen = 0
                  AND saved_searches.notifications_enabled = 1
                  AND saved_searches.is_active = 1
                ORDER BY search_results.first_matched DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [
            {
                "searchId": int(row["search_id"]),
                "searchName": row["search_name"],
                "listingId": row["listing_id"],
                "title": row["title"],
                "url": row["url"],
                "source": row["source"],
                "sourceLabel": SOURCE_LABELS.get(row["source"], row["source"]),
                "rentEur": row["rent_eur"],
                "firstMatched": row["first_matched"],
            }
            for row in rows
        ]

    def account_summary(self, user_id: int) -> dict:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    COUNT(DISTINCT saved_searches.id) AS saved_count,
                    COUNT(search_results.listing_id) AS stored_count,
                    COALESCE(SUM(CASE WHEN search_results.seen = 0 THEN 1 ELSE 0 END), 0) AS unseen_count,
                    COALESCE(SUM(CASE WHEN user_listing_state.favorite = 1 THEN 1 ELSE 0 END), 0) AS favorite_count
                FROM saved_searches
                LEFT JOIN search_results ON search_results.search_id = saved_searches.id
                LEFT JOIN user_listing_state
                    ON user_listing_state.user_id = saved_searches.user_id
                    AND user_listing_state.listing_id = search_results.listing_id
                WHERE saved_searches.user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return {
            "savedCount": int(row["saved_count"] or 0),
            "storedCount": int(row["stored_count"] or 0),
            "unseenCount": int(row["unseen_count"] or 0),
            "favoriteCount": int(row["favorite_count"] or 0),
        }

    def admin_overview(self) -> dict:
        with self._lock:
            counts = self._conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM users) AS users,
                    (SELECT COUNT(*) FROM saved_searches) AS saved_searches,
                    (SELECT COUNT(*) FROM saved_searches WHERE is_active = 1) AS active_searches,
                    (SELECT COUNT(*) FROM search_results) AS stored_matches,
                    (SELECT COUNT(*) FROM listings) AS listings
                """
            ).fetchone()
            users = self._conn.execute(
                """
                SELECT
                    users.id,
                    users.email,
                    users.is_admin,
                    users.created_at,
                    users.last_login_at,
                    COUNT(DISTINCT saved_searches.id) AS saved_count,
                    COUNT(search_results.listing_id) AS match_count
                FROM users
                LEFT JOIN saved_searches ON saved_searches.user_id = users.id
                LEFT JOIN search_results ON search_results.user_id = users.id
                GROUP BY users.id
                ORDER BY users.created_at DESC
                LIMIT 50
                """
            ).fetchall()
            searches = self._conn.execute(
                """
                SELECT
                    saved_searches.id,
                    saved_searches.name,
                    saved_searches.user_id,
                    users.email,
                    saved_searches.is_active,
                    saved_searches.notifications_enabled,
                    saved_searches.last_checked,
                    saved_searches.last_new_count,
                    COUNT(search_results.listing_id) AS stored_count
                FROM saved_searches
                JOIN users ON users.id = saved_searches.user_id
                LEFT JOIN search_results ON search_results.search_id = saved_searches.id
                GROUP BY saved_searches.id
                ORDER BY saved_searches.updated_at DESC
                LIMIT 80
                """
            ).fetchall()
            source_rows = self._conn.execute(
                """
                SELECT source, COUNT(*) AS count, MAX(last_seen) AS last_seen
                FROM listings
                GROUP BY source
                ORDER BY count DESC
                """
            ).fetchall()
        return {
            "counts": {
                "users": int(counts["users"] or 0),
                "savedSearches": int(counts["saved_searches"] or 0),
                "activeSearches": int(counts["active_searches"] or 0),
                "storedMatches": int(counts["stored_matches"] or 0),
                "listings": int(counts["listings"] or 0),
            },
            "users": [
                {
                    "id": int(row["id"]),
                    "email": row["email"],
                    "isAdmin": bool(row["is_admin"]),
                    "createdAt": row["created_at"],
                    "lastLoginAt": row["last_login_at"],
                    "savedCount": int(row["saved_count"] or 0),
                    "matchCount": int(row["match_count"] or 0),
                }
                for row in users
            ],
            "searches": [
                {
                    "id": int(row["id"]),
                    "name": row["name"],
                    "userId": int(row["user_id"]),
                    "email": row["email"],
                    "isActive": bool(row["is_active"]),
                    "notificationsEnabled": bool(row["notifications_enabled"]),
                    "lastChecked": row["last_checked"],
                    "lastNewCount": int(row["last_new_count"] or 0),
                    "storedCount": int(row["stored_count"] or 0),
                }
                for row in searches
            ],
            "sources": [
                {
                    "source": row["source"],
                    "sourceLabel": SOURCE_LABELS.get(row["source"], row["source"]),
                    "count": int(row["count"] or 0),
                    "lastSeen": row["last_seen"],
                }
                for row in source_rows
            ],
        }

    def _saved_search_from_row(self, row: sqlite3.Row) -> dict:
        try:
            filters = json.loads(row["filters_json"])
        except (TypeError, json.JSONDecodeError):
            filters = {}
        return {
            "id": int(row["id"]),
            "userId": int(row["user_id"]),
            "name": row["name"],
            "filters": filters,
            "intervalSeconds": int(row["interval_seconds"] or 30),
            "notificationsEnabled": bool(row["notifications_enabled"]),
            "isActive": bool(row["is_active"]),
            "lastChecked": row["last_checked"],
            "lastNewCount": int(row["last_new_count"] or 0),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "storedCount": int(row["stored_count"]) if "stored_count" in row.keys() else 0,
            "unseenCount": int(row["unseen_count"]) if "unseen_count" in row.keys() else 0,
        }

    def _user_from_row(self, row: sqlite3.Row) -> dict:
        return {
            "id": int(row["id"]),
            "email": row["email"],
            "isAdmin": bool(row["is_admin"]),
            "createdAt": row["created_at"],
        }

    def _sync_env_admins(self) -> None:
        emails = configured_admin_emails()
        if not emails:
            return
        placeholders = ",".join("?" for _ in emails)
        self._conn.execute(f"UPDATE users SET is_admin = 1 WHERE email IN ({placeholders})", list(emails))

    def _ensure_one_admin(self) -> None:
        row = self._conn.execute("SELECT COUNT(*) AS count FROM users WHERE is_admin = 1").fetchone()
        if int(row["count"] or 0) > 0:
            return
        first_user = self._conn.execute("SELECT id FROM users ORDER BY created_at ASC, id ASC LIMIT 1").fetchone()
        if first_user:
            self._conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (first_user["id"],))
