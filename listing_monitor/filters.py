from __future__ import annotations

from dataclasses import dataclass, field

from .sources import Listing


@dataclass
class Query:
    text: str
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    sources: list[str] = field(default_factory=list)

    def wants(self, source_name: str) -> bool:
        return not self.sources or source_name in self.sources

    def matches(self, listing: Listing) -> bool:
        title = listing.title.lower()
        if not all(word.lower() in title for word in self.include):
            return False
        if any(word.lower() in title for word in self.exclude):
            return False
        if listing.price is None:
            return True
        if self.min_price is not None and listing.price < self.min_price:
            return False
        if self.max_price is not None and listing.price > self.max_price:
            return False
        return True
