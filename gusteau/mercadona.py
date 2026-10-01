"""Mercadona prices for the shopping list (unofficial, read-only).

Mercadona has no public API. tienda.mercadona.es searches its catalogue through Algolia
with a public, search-only key shipped in its JS bundle; we use the same index, read-only:
- `search`   full-text query (to auto-map ingredients and for the product picker)
- `products` batch lookup by id (one request for the whole list)
The index is per warehouse (prices/stock depend on the postal code; mad1 = Madrid).
Everything is cached on disk and failures are reported, never raised to the list:
if Mercadona changes or blocks this, the shopping list still works, just without prices.
"""

from __future__ import annotations

import json
import math
import time
import unicodedata
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

ALGOLIA_APP = "7UZJKL1DJ0"
ALGOLIA_KEY = "9d8f2e39e90df472b4f2e559a116fe17"  # public search-only key from tienda.mercadona.es
TIMEOUT = 8
PRICE_TTL = 24 * 3600  # prices / product data
AUTO_TTL = 7 * 24 * 3600  # automatic ingredient -> product picks
PANTRY_SHARE = 0.15  # using less than this share of one pack -> probably already at home

Fetch = Callable[[str, dict], dict]


class MercadonaError(Exception):
    pass


def _http_post(url: str, body: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "X-Algolia-Application-Id": ALGOLIA_APP,
            "X-Algolia-API-Key": ALGOLIA_KEY,
            "Content-Type": "application/json",
            "User-Agent": "gusteau/0.1 (personal meal planner)",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


@dataclass
class Product:
    id: str
    name: str
    price: float  # € per pack / piece as sold
    size: float | None  # pack size in `size_format` units
    size_format: str  # kg | l | ud
    units: int | None  # pieces inside the pack (e.g. 2 breads in a bag)
    approx: bool  # sold by weight / variable size: price is an estimate
    available: bool
    url: str
    thumbnail: str | None
    packaging: str | None

    @classmethod
    def from_hit(cls, h: dict) -> Product:
        pi = h.get("price_instructions") or {}
        price = float(pi.get("unit_price") or 0)
        size = pi.get("unit_size")
        if not size and pi.get("bulk_price"):  # e.g. frozen prawns: size missing, €/kg present
            size = round(price / float(pi["bulk_price"]), 3) or None
        return cls(
            id=str(h.get("id") or h.get("objectID")),
            name=h.get("display_name", "?"),
            price=price,
            size=float(size) if size else None,
            size_format=pi.get("size_format") or "ud",
            units=pi.get("total_units"),
            approx=bool(pi.get("approx_size")),
            available=bool(h.get("published", True)),
            url=h.get("share_url") or f"https://tienda.mercadona.es/product/{h.get('id')}",
            thumbnail=h.get("thumbnail"),
            packaging=h.get("packaging"),
        )


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


class Mercadona:
    def __init__(self, cache_path: Path, warehouse: str = "mad1", fetch: Fetch | None = None):
        self.cache_path = cache_path
        self.warehouse = warehouse
        self.fetch = fetch or _http_post
        self._cache: dict | None = None

    # ---- cache ----

    def _load(self) -> dict:
        if self._cache is None:
            try:
                self._cache = json.loads(self.cache_path.read_text())
            except (OSError, ValueError):
                self._cache = {}
        assert self._cache is not None
        return self._cache

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._load(), ensure_ascii=False))

    def _get(self, key: str, ttl: int):
        entry = self._load().get(f"{self.warehouse}:{key}")
        if entry and time.time() - entry["t"] < ttl:
            return entry["v"]
        return None

    def _put(self, key: str, value) -> None:
        self._load()[f"{self.warehouse}:{key}"] = {"t": time.time(), "v": value}

    # ---- API ----

    @property
    def _index(self) -> str:
        return f"products_prod_{self.warehouse}_es"

    def _call(self, path: str, body: dict) -> dict:
        try:
            return self.fetch(f"https://{ALGOLIA_APP.lower()}-dsn.algolia.net{path}", body)
        except Exception as e:  # network, HTTP, JSON: all mean "no prices right now"
            raise MercadonaError(f"Mercadona no responde ({e})") from e

    def search(self, query: str, hits: int = 8) -> list[Product]:
        query = query.strip()
        cached = self._get(f"q:{_norm(query)}", PRICE_TTL)
        if cached is None:
            data = self._call(
                f"/1/indexes/{self._index}/query", {"params": f"query={urllib.parse.quote(query)}&hitsPerPage={hits}"}
            )
            cached = data.get("hits", [])
            self._put(f"q:{_norm(query)}", cached)
            for h in cached:
                self._put(f"p:{h.get('id')}", h)
            self._save()
        return [Product.from_hit(h) for h in cached]

    def products(self, ids: list[str]) -> dict[str, Product]:
        ids = list(dict.fromkeys(str(i) for i in ids))
        hits = {i: self._get(f"p:{i}", PRICE_TTL) for i in ids}
        missing = [i for i, h in hits.items() if h is None]
        if missing:
            data = self._call(
                "/1/indexes/*/objects", {"requests": [{"indexName": self._index, "objectID": i} for i in missing]}
            )
            for i, h in zip(missing, data.get("results", []), strict=False):
                if h:
                    hits[i] = h
                    self._put(f"p:{i}", h)
            self._save()
        return {i: Product.from_hit(h) for i, h in hits.items() if h}

    def auto_pick(self, ingredient: str) -> str | None:
        """First available search hit that mentions the ingredient's first word; cached for a week."""
        cached = self._get(f"auto:{_norm(ingredient)}", AUTO_TTL)
        if cached is not None:
            return cached or None
        word = _norm(ingredient).split()[0][:5]  # crude stem: "lentejas" ~ "lenteja"
        pick = next((p.id for p in self.search(ingredient) if p.available and word in _norm(p.name)), "")
        self._put(f"auto:{_norm(ingredient)}", pick)
        self._save()
        return pick or None


# ---- packs ----

TO_PRODUCT = {"g": ("kg", 1e-3), "ml": ("l", 1e-3)}


def packs_needed(amounts: dict[str, float], product: Product) -> tuple[int, float | None]:
    """How many packs to buy for the summed `amounts` (base unit -> quantity).

    Returns (packs, share) where share is the fraction of packs actually used, or None
    if some amount could not be converted (e.g. "2 dientes" of garlic, or "al gusto").
    Mass and volume are treated as interchangeable (≈ water), which is fine for a list.
    """
    need = 0.0
    known = True
    for unit, qty in amounts.items():
        if unit in TO_PRODUCT and product.size and product.size_format in ("kg", "l"):
            need += qty * TO_PRODUCT[unit][1] / product.size
        elif unit == "ud" and product.size_format == "ud" and product.size:
            need += qty / product.size
        elif unit == "ud" and product.units:
            need += qty / product.units
        elif unit == "ud" and product.approx:  # loose piece (lemon, avocado...)
            need += qty
        else:
            known = False
    packs = max(1, math.ceil(need - 0.05)) if need else 1  # 5% slack: 1.03 packs -> 1
    return packs, (need if known and need else None)


def price_item(amounts: dict[str, float], product: Product) -> dict:
    packs, share = packs_needed(amounts, product)
    return {
        "product": asdict(product),
        "packs": packs,
        "cost": round(packs * product.price, 2),
        "approx": product.approx or share is None,
        # tiny share of a pack (a spoon of cumin) or no quantity at all: likely in the pantry already
        "pantry": share is None and all(u == "" for u in amounts) or (share is not None and share < PANTRY_SHARE),
    }
