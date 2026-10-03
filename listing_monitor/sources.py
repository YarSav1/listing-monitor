from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
# Pages that only show an anti-bot check. We report them instead of trying to get around them.
BLOCK_MARKERS = ("cf-challenge", "challenge-platform", "<title>just a moment", "are you a robot")


class SourceBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class Listing:
    source: str
    item_id: str
    title: str
    url: str
    price: float | None = None
    currency: str = ""


def parse_price(text: str) -> float | None:
    """'£1,234.50', '1.234,50 €', '12,99', '1 200 ₽' -> float."""
    digits = re.sub(r"[^\d,.]", "", text or "")
    if not digits:
        return None
    if "," in digits and "." in digits:
        # whichever separator comes last is the decimal one
        if digits.rfind(".") > digits.rfind(","):
            digits = digits.replace(",", "")
        else:
            digits = digits.replace(".", "").replace(",", ".")
    elif "," in digits:
        decimals = digits.split(",")[-1]
        digits = digits.replace(",", ".") if len(decimals) <= 2 else digits.replace(",", "")
    try:
        return float(digits)
    except ValueError:
        return None


class CssSource:
    """A search results page parsed with CSS selectors."""

    def __init__(self, name, search_url, item, title, link, price=None, currency="", headers=None):
        self.name = name
        self.search_url = search_url
        self.currency = currency
        self.selectors = {"item": item, "title": title, "link": link, "price": price}
        self.http = httpx.Client(
            timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT, **(headers or {})}
        )

    def fetch_html(self, url: str) -> str:
        response = self.http.get(url)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, base_url: str) -> list[Listing]:
        sel = self.selectors
        listings = []
        for node in BeautifulSoup(html, "html.parser").select(sel["item"]):
            title, link = node.select_one(sel["title"]), node.select_one(sel["link"])
            if not title or not link or not link.get("href"):
                continue
            url = urljoin(base_url, link["href"])
            price_node = node.select_one(sel["price"]) if sel["price"] else None
            listings.append(Listing(
                source=self.name,
                item_id=url.split("?")[0],
                title=title.get_text(" ", strip=True),
                url=url,
                price=parse_price(price_node.get_text(" ", strip=True)) if price_node else None,
                currency=self.currency,
            ))
        return listings

    def search(self, query: str) -> list[Listing]:
        url = self.search_url.format(q=quote_plus(query))
        html = self.fetch_html(url)
        if any(marker in html[:20000].lower() for marker in BLOCK_MARKERS):
            raise SourceBlocked(f"{self.name} returned an anti-bot page")
        return self.parse(html, url)


class BrowserSource(CssSource):
    """Same parsing, but the page is rendered by Chromium (pip install playwright)."""

    def fetch_html(self, url: str) -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(2_000)
            html = page.content()
            browser.close()
        return html


class EbayApiSource:
    """eBay Browse API. eBay pages reject scripted requests, the official API does not."""

    TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    def __init__(self, client_id, client_secret, marketplace="EBAY_GB", category_ids="", name="ebay"):
        self.name = name
        self.marketplace = marketplace
        self.category_ids = category_ids
        self._basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        self._token, self._token_expires = "", 0.0
        self.http = httpx.Client(timeout=30)

    def _access_token(self) -> str:
        if time.time() < self._token_expires - 60:
            return self._token
        response = self.http.post(
            self.TOKEN_URL,
            headers={"Authorization": f"Basic {self._basic}"},
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
        )
        response.raise_for_status()
        body = response.json()
        self._token = body["access_token"]
        self._token_expires = time.time() + body["expires_in"]
        return self._token

    def search(self, query: str) -> list[Listing]:
        params = {"q": query, "sort": "newlyListed", "limit": 50}
        if self.category_ids:
            params["category_ids"] = self.category_ids
        response = self.http.get(self.SEARCH_URL, params=params, headers={
            "Authorization": f"Bearer {self._access_token()}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
        })
        response.raise_for_status()
        listings = []
        for item in response.json().get("itemSummaries", []):
            price = item.get("price") or {}
            listings.append(Listing(
                source=self.name,
                item_id=item["itemId"],
                title=item.get("title", ""),
                url=item.get("itemWebUrl", ""),
                price=float(price["value"]) if price.get("value") else None,
                currency=price.get("currency", ""),
            ))
        return listings


def build_source(config: dict):
    config = dict(config)
    kind = config.pop("type")
    if kind == "ebay_api":
        return EbayApiSource(**config)
    if kind == "browser":
        return BrowserSource(**config)
    if kind == "css":
        return CssSource(**config)
    raise ValueError(f"unknown source type: {kind}")
