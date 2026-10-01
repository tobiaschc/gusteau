import pytest
from fastapi.testclient import TestClient

from gusteau.api import create_app
from gusteau.mercadona import Mercadona
from gusteau.store import Store

WEEK = "2026-W40"


def hit(pid, name, price, size, fmt="kg", units=None, approx=False, published=True):
    return {
        "id": pid,
        "display_name": name,
        "published": published,
        "share_url": f"https://tienda.mercadona.es/product/{pid}/x",
        "price_instructions": {
            "unit_price": str(price),
            "unit_size": size,
            "size_format": fmt,
            "total_units": units,
            "approx_size": approx,
        },
    }


CATALOGUE = {
    "8934": hit("8934", "Lomo de vacuno añojo", 8.09, 0.337, approx=True),
    "60354": hit("60354", "Panes integrales 100% fino", 1.40, 0.165, units=2),
    "31504": hit("31504", "Huevos grandes L", 3.05, 12.0, fmt="ud"),
    "4740": hit("4740", "Aceite de oliva virgen extra Hacendado", 4.45, 1.0, fmt="l"),
    "1": hit("1", "Bebida de soja", 1.0, 1.0, fmt="l"),
    "2": hit("2", "Lenteja cocida Hacendado", 0.9, 0.57, published=False),
    "3": hit("3", "Lenteja cocida Hacendado", 0.75, 0.295),
}
CALLS = []


def fake_mercadona(url, body):
    CALLS.append(url)
    if url.endswith("/objects"):
        return {"results": [CATALOGUE.get(r["objectID"]) for r in body["requests"]]}
    query = body["params"].split("query=")[1].split("&")[0]
    return {"hits": [CATALOGUE["1"], CATALOGUE["2"], CATALOGUE["3"]] if "lentej" in query else []}


@pytest.fixture
def client(tmp_path):
    shop = Mercadona(tmp_path / "cache.json", fetch=fake_mercadona)
    return TestClient(create_app(Store(tmp_path), static_dir=tmp_path / "nostatic", shop=shop))
