from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
import threading
from pathlib import Path

from .config import SOURCE_LABELS
from .sources import Listing, listing_matches_filters, title_is_bad


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
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_city_source ON listings(city_id, source)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings(last_seen DESC)")

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

    def query_listings(self, filters: dict, limit: int = 120) -> list[dict]:
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
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM listings {where_sql} ORDER BY last_seen DESC, first_seen DESC LIMIT ?",
                [*params, limit * 3],
            ).fetchall()
        results = [dict(row) for row in rows]
        filtered = [row for row in results if not is_parser_artifact(row) and listing_matches_filters(row, filters)]
        for row in filtered:
            row["source_label"] = SOURCE_LABELS.get(row["source"], row["source"])
        return filtered[:limit]

    def mark_seen(self, ids: list[str] | None = None) -> int:
        with self._lock, self._conn:
            if ids:
                placeholders = ",".join("?" for _ in ids)
                cursor = self._conn.execute(f"UPDATE listings SET seen = 1 WHERE id IN ({placeholders})", ids)
            else:
                cursor = self._conn.execute("UPDATE listings SET seen = 1")
        return cursor.rowcount
