import pytest
import yaml
from fastapi.testclient import TestClient

from gusteau.api import create_app
from gusteau.mercadona import Mercadona, MercadonaError, Product, packs_needed
from gusteau.store import Store

from .conftest import CALLS, CATALOGUE, WEEK, fake_mercadona


def test_packs_needed():
    beef = Product.from_hit(CATALOGUE["8934"])
    assert packs_needed({"g": 300}, beef) == (1, pytest.approx(0.89, abs=0.01))  # 2 × 150 g -> one ~337 g pack
    assert packs_needed({"g": 700}, beef)[0] == 3
    bread = Product.from_hit(CATALOGUE["60354"])
    assert packs_needed({"g": 560}, bread)[0] == 4  # 14 × 40 g half-breads -> 7 breads -> 4 bags
    eggs = Product.from_hit(CATALOGUE["31504"])
    assert packs_needed({"ud": 13}, eggs)[0] == 2
    assert packs_needed({"dientes": 2}, beef) == (1, None)  # unknown unit: 1 pack, unknown share


def test_auto_pick_skips_unpublished_and_unrelated(tmp_path):
    shop = Mercadona(tmp_path / "c.json", fetch=fake_mercadona)
    assert shop.auto_pick("lentejas cocidas") == "3"  # "soja" doesn't match, "2" is unpublished
    n = len(CALLS)
    assert Mercadona(tmp_path / "c.json", fetch=fake_mercadona).auto_pick("lentejas cocidas") == "3"
    assert len(CALLS) == n  # served from the disk cache


def test_shopping_prices_and_overrides(client, tmp_path):
    week = {d: {"desayuno": "tortilla-francesa-pan", "comida": None, "cena": None} for d in ("lunes", "martes")}
    week["lunes"]["cena"] = "solomillo-pure-patata"
    client.put(f"/api/plans/{WEEK}", json={"days": week})
    data = client.get(f"/api/plans/{WEEK}/shopping").json()
    items = {i["name"]: i["mercadona"] for i in data["items"]}
    assert data["prices_error"] is None
    assert items["lomo de vacuno añojo"]["product"]["id"] == "8934" and items["lomo de vacuno añojo"]["packs"] == 1
    assert items["pan integral"]["packs"] == 1 and not items["pan integral"]["auto"]
    assert items["aceite de oliva virgen extra"]["pantry"]  # a few ml of a 1 l bottle
    assert items["patata"] is None  # bundled id not in the fake catalogue -> no price, list still works
    assert data["total"] == pytest.approx(8.09 + 1.40 + 3.05)  # pantry items excluded

    client.put("/api/products/lomo de vacuno añojo", json={"id": None})
    items = {i["name"]: i["mercadona"] for i in client.get(f"/api/plans/{WEEK}/shopping").json()["items"]}
    assert items["lomo de vacuno añojo"] is None  # user said: not at Mercadona
    assert yaml.safe_load((tmp_path / "products.yml").read_text()) == {"lomo de vacuno añojo": None}


def test_shopping_without_mercadona(tmp_path):
    def down(url, body):
        raise OSError("connection refused")

    app = create_app(Store(tmp_path), static_dir=tmp_path / "x", shop=Mercadona(tmp_path / "c.json", fetch=down))
    c = TestClient(app)
    c.put(f"/api/plans/{WEEK}", json={"days": {"lunes": {"desayuno": "tortilla-francesa-pan"}}})
    data = c.get(f"/api/plans/{WEEK}/shopping").json()
    assert data["items"] and data["total"] is None and "no responde" in data["prices_error"]
    assert c.get("/api/products/search", params={"q": "pan"}).status_code == 502
    with pytest.raises(MercadonaError):
        Mercadona(tmp_path / "c2.json", fetch=down).search("pan")


def test_pantry_answers_and_cart_are_shared(client):
    week = {"lunes": {"desayuno": "tortilla-francesa-pan", "comida": None, "cena": "solomillo-pure-patata"}}
    client.put(f"/api/plans/{WEEK}", json={"days": week})
    url = f"/api/plans/{WEEK}/shopping"
    base = client.get(url).json()
    items = {i["name"]: i for i in base["items"]}
    oil = items["aceite de oliva virgen extra"]
    assert oil["pantry"] and oil["at_home"] is None and not oil["in_cart"]
    assert items["sal"]["pantry"]  # "al gusto", no product: still asked

    # "me falta": it joins the list and the total
    r = client.patch(f"{url}/Aceite de oliva virgen extra", json={"at_home": False})
    assert r.json() == {"ingredient": "aceite de oliva virgen extra", "in_cart": False, "at_home": False}
    after = client.get(url).json()
    assert after["total"] == pytest.approx(base["total"] + oil["mercadona"]["cost"])
    assert "aceite de oliva" in client.get(f"{url}.md").text
    assert "- [ ] sal" not in client.get(f"{url}.md").text  # unanswered pantry items stay out of the copy

    # "lo tengo" and ticking another line, then clearing the cart keeps the answers
    client.patch(f"{url}/aceite de oliva virgen extra", json={"at_home": True})
    client.patch(f"{url}/huevos", json={"in_cart": True})
    items = {i["name"]: i for i in client.get(url).json()["items"]}
    assert items["aceite de oliva virgen extra"]["at_home"] is True and items["huevos"]["in_cart"]
    assert client.get(url).json()["total"] == pytest.approx(base["total"])
    assert client.delete(f"{url}/cart").status_code == 204
    items = {i["name"]: i for i in client.get(url).json()["items"]}
    assert not items["huevos"]["in_cart"] and items["aceite de oliva virgen extra"]["at_home"] is True

    # undo: back to defaults leaves no row behind
    client.patch(f"{url}/aceite de oliva virgen extra", json={"at_home": None})
    assert client.app.state.store.shopping_marks(WEEK) == {}
    assert client.patch("/api/plans/2030-W01/shopping/sal", json={"in_cart": True}).status_code == 404
