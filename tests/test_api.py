import pytest

from .conftest import WEEK


def test_seeded_recipes_listed(client):
    recipes = client.get("/api/recipes").json()
    assert len(recipes) >= 9
    assert client.get("/api/recipes/pollo-arroz-brocoli").json()["title"] == "Pollo con arroz y brócoli"


def test_recipe_crud(client):
    src = "---\ntitle: Gazpacho\ntags: [comida]\n---\nTritura @tomate{3} con @pepino{100%g}.\n"
    created = client.post("/api/recipes", json={"source": src}).json()
    assert created["slug"] == "gazpacho"
    assert client.post("/api/recipes", json={"source": src}).json()["slug"] == "gazpacho-2"
    r = client.put("/api/recipes/gazpacho", json={"source": src.replace("3", "4")})
    assert r.json()["ingredients"][0]["quantity"] == 4
    assert client.post("/api/recipes", json={"source": "@{1}"}).status_code == 422
    assert client.delete("/api/recipes/gazpacho").status_code == 204
    assert client.get("/api/recipes/gazpacho").status_code == 404
    assert client.get("/api/recipes/..%2Fsettings").status_code == 404


def test_plan_generate_and_shopping(client):
    assert client.get("/api/plans/bad-week").status_code == 422
    plan = client.post(f"/api/plans/{WEEK}/generate", json={"seed": 3}).json()
    assert all(v for d in plan["days"].values() for v in d.values())
    assert set(plan["titles"]) <= {r["slug"] for r in client.get("/api/recipes").json()}

    shop = client.get(f"/api/plans/{WEEK}/shopping").json()
    assert shop["people"] == 2 and shop["meals"] == 21
    assert any(i["aisle"] == "Frutería y verdura" for i in shop["items"])
    md = client.get(f"/api/plans/{WEEK}/shopping.md").text
    assert md.startswith(f"# Lista de la compra · {WEEK} · 2 personas") and "- [ ]" in md

    one = client.get(f"/api/plans/{WEEK}/shopping?people=1").json()
    oil2 = next(i for i in shop["items"] if i["name"] == "aceite de oliva virgen extra")["amounts"][0]["quantity"]
    oil1 = next(i for i in one["items"] if i["name"] == "aceite de oliva virgen extra")["amounts"][0]["quantity"]
    assert oil2 == pytest.approx(2 * oil1)


def test_plan_put_validates_recipes(client):
    days = {"lunes": {"comida": "no-existe"}}
    assert client.put(f"/api/plans/{WEEK}", json={"days": days}).status_code == 404
    days = {"lunes": {"comida": "pollo-arroz-brocoli", "cena": None}}
    assert client.put(f"/api/plans/{WEEK}", json={"days": days}).json()["titles"] == {
        "pollo-arroz-brocoli": "Pollo con arroz y brócoli"
    }


def test_settings(client):
    assert client.get("/api/settings").json()["people"] == 2
    assert client.put("/api/settings", json={"people": 3}).json()["people"] == 3
    assert client.put("/api/settings", json={"people": 0}).status_code == 422
