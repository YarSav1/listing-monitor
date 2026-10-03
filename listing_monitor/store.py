from __future__ import annotations

import sqlite3
import time

from .sources import Listing


class SeenStore:
    """Remembers which listings were already reported, per source and query."""

    def __init__(self, path: str = "seen.sqlite"):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS seen ("
            " source TEXT, query TEXT, item_id TEXT, first_seen REAL,"
            " PRIMARY KEY (source, query, item_id))"
        )

    def has_history(self, source: str, query: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM seen WHERE source = ? AND query = ? LIMIT 1", (source, query)
        ).fetchone()
        return row is not None

    def add_new(self, source: str, query: str, listings: list[Listing]) -> list[Listing]:
        new = []
        for listing in listings:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO seen VALUES (?, ?, ?, ?)",
                (source, query, listing.item_id, time.time()),
            )
            if cursor.rowcount:
                new.append(listing)
        self.db.commit()
        return new
