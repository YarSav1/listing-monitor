from __future__ import annotations

import time
from html import escape

import httpx

from .sources import Listing


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id
        self.http = httpx.Client(timeout=20)

    def format(self, listing: Listing, query: str) -> str:
        lines = [f"<b>{escape(listing.title)}</b>"]
        if listing.price is not None:
            lines.append(f"{listing.price:g} {listing.currency}".strip())
        lines.append(f"{escape(query)} · {escape(listing.source)}")
        lines.append(escape(listing.url))
        return "\n".join(lines)

    def send(self, listing: Listing, query: str) -> None:
        payload = {"chat_id": self.chat_id, "text": self.format(listing, query), "parse_mode": "HTML"}
        response = self.http.post(self.url, json=payload)
        if response.status_code == 429:
            # Telegram tells us how long to back off
            time.sleep(response.json().get("parameters", {}).get("retry_after", 5))
            response = self.http.post(self.url, json=payload)
        response.raise_for_status()
