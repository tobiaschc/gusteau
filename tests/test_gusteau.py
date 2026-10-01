from itertools import pairwise

import pytest
from fastapi.testclient import TestClient

from gusteau.app import create_app
from gusteau.cooklang import CooklangError, parse
from gusteau.planner import generate
from gusteau.shopping import format_amount, shopping_list
from gusteau.store import Store, slugify

WEEK = "2026-W40"


# ---------- cooklang ----------


def test_parse_front_matter_and_ingredients():
    r = parse(
        "---\ntitle: Test\nservings: 2\ntags: [cena, Rápida]\ntime: 10 min\n---\n"
        "Mezcla @pechuga de pollo{300%g} con @sal y @aceite{1 1/2%ml}.\n",
        "test",
    )
    assert (r.title, r.servings, r.tags, r.time) == ("Test", 2, ["cena", "rápida"], "10 min")
    assert [(i.name, i.quantity, i.unit) for i in r.ingredients] == [
        ("pechuga de pollo", 300, "g"),
        ("sal", None, ""),
        ("aceite", 1.5, "ml"),
    ]


def test_parse_steps_comments_cookware_timers():
    r = parse("Pon agua en #olla{} -- comentario\nhierve ~{10%minutos}.\n\n[- nota -]Sirve @tomate{1}.")
    assert len(r.steps) == 2
    kinds = [s["type"] for s in r.steps[0]]
    assert "cookware" in kinds and "timer" in kinds
    assert "comentario" not in str(r.steps) and "nota" not in str(r.steps)
    assert r.title == ""  # no slug, no title


def test_dashes_inside_body_are_not_front_matter():
    r = parse("---\ntitle: A\n---\nPaso uno.\n\n---\n\nPaso dos con @huevos{2}.")
    assert r.title == "A" and r.ingredients[0].name == "huevos"


@pytest.mark.parametrize("bad", ["@{2%g}", "@sal{abc%g}", "---\nservings: 0\n---\nx", "---\n- a\n---\nx"])
def test_parse_errors(bad):
    with pytest.raises(CooklangError):
        parse(bad)


def test_bundled_recipes_parse():
    from gusteau.store import SEED

    for path in SEED.glob("*.cook"):
        r = parse(path.read_text(), path.stem)
        assert r.ingredients and r.tags, path.name


# ---------- shopping ----------


def test_shopping_scales_and_merges_units():
    a = parse("---\nservings: 1\n---\n@arroz{75%g} @huevos{2} @leche{0.5%l}")
    b = parse("---\nservings: 2\n---\n@arroz{1%kg} @huevos{3} @sal")
    items = {i.name: i for i in shopping_list([a, a, b], people=2, aisles={"arroz": "Despensa"})}
    assert items["arroz"].amounts == {"g": 75 * 2 * 2 + 1000}
    assert items["arroz"].aisle == "Despensa"
    assert items["huevos"].amounts == {"ud": 2 * 2 * 2 + 3}
    assert items["leche"].amounts == {"ml": 2000}
    assert items["sal"].amounts == {"": 0}
    assert items["leche"].aisle == "Otros"
    assert next(iter(items)) == "arroz"  # known aisles first, "Otros" last


def test_format_amount():
    assert format_amount("g", 1300) == "1,3 kg"
    assert format_amount("ud", 2.5) == "3 ud"
    assert format_amount("ml", 250) == "250 ml"
    assert format_amount("", 0) == "al gusto"


# ---------- planner ----------


def test_generate_respects_slot_tags_and_avoids_consecutive_repeats():
    recipes = [
        parse(f"---\ntags: [{t}]\n---\n@x{{1}}", s)
        for s, t in [
            ("d1", "desayuno"),
            ("d2", "desayuno"),
            ("c1", "comida"),
            ("c2", "comida"),
            ("c3", "comida, cena"),
            ("n1", "cena"),
        ]
    ]
    plan = {"week": WEEK, "days": {d: {"desayuno": None, "comida": None, "cena": None} for d in "abcdefg"}}
    plan["days"]["a"]["comida"] = "c1"
    out = generate(plan, recipes, seed=1)
    days = list(out["days"].values())
    assert days[0]["comida"] == "c1"  # kept
    assert all(d["desayuno"] in {"d1", "d2"} for d in days)
    assert all(d["cena"] in {"c3", "n1"} for d in days)
    for slot in ("desayuno", "comida", "cena"):
        seq = [d[slot] for d in days]
        assert all(x != y for x, y in pairwise(seq)), seq
    for d in days:
        assert d["comida"] != d["cena"]
    out2 = generate(out, recipes, keep=False, seed=2)
    assert all(v for d in out2["days"].values() for v in d.values())


# ---------- store & API ----------


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Store(tmp_path), static_dir=tmp_path / "nostatic"))


def test_slugify():
    assert slugify("Salmón con patata & ensalada!") == "salmon-con-patata-ensalada"


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
