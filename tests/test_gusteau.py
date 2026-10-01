from itertools import pairwise

import pytest
import yaml
from fastapi.testclient import TestClient

from gusteau.app import create_app
from gusteau.cooklang import CooklangError, parse
from gusteau.mercadona import Mercadona, MercadonaError, Product, packs_needed
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
    from gusteau.store import SEED, SEED_AISLES

    known = {str(i) for items in yaml.safe_load(SEED_AISLES.read_text()).values() for i in items}
    missing = set()
    for path in SEED.glob("*.cook"):
        r = parse(path.read_text(), path.stem)
        assert r.ingredients and r.tags, path.name
        assert {"desayuno", "comida", "cena"} & set(r.tags), f"{path.name}: no slot tag"
        missing |= {i.name for i in r.ingredients} - known
    assert not missing, f"ingredients without aisle in aisles.yml: {sorted(missing)}"


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
    for slot in ("comida", "cena"):  # breakfasts may repeat on consecutive days
        seq = [d[slot] for d in days]
        assert all(x != y for x, y in pairwise(seq)), seq
    for d in days:
        assert d["comida"] != d["cena"]
    out2 = generate(out, recipes, keep=False, seed=2)
    assert all(v for d in out2["days"].values() for v in d.values())


def test_generate_balances_proteins_and_keeps_finde_for_weekend(tmp_path):
    from gusteau.planner import BALANCE

    store = Store(tmp_path)
    recipes = store.list_recipes()
    tags = {r.slug: r.tags for r in recipes}
    weekend_only = {r.slug for r in recipes if "finde" in r.tags}
    assert weekend_only  # the bundled bank has at least one long weekend recipe
    for seed in range(5):
        days = generate(store.get_plan(WEEK), recipes, keep=False, seed=seed)["days"]
        counts = {t: sum(t in tags[d[s]] for d in days.values() for s in ("comida", "cena")) for t in BALANCE}
        for tag, (lo, hi) in BALANCE.items():
            assert lo - 1 <= counts[tag] <= hi + 1, (seed, counts)
        for day, slots in days.items():
            if day not in ("sabado", "domingo"):
                assert not weekend_only & set(slots.values()), (seed, day)


def test_generate_favours_habitual_recipes(tmp_path):
    from gusteau.planner import HABITUAL_MAX_EACH

    store = Store(tmp_path)
    recipes = store.list_recipes()
    usual = {r.slug for r in recipes if "habitual" in r.tags}
    assert {"tortilla-francesa-pan", "solomillo-pure-patata", "burger-pollo-boniato"} <= usual
    for seed in range(5):
        days = generate(store.get_plan(WEEK), recipes, keep=False, seed=seed)["days"].values()
        assert 5 <= sum(d["desayuno"] in usual for d in days) <= 6, seed
        mains = [d[s] for d in days for s in ("comida", "cena")]
        assert 4 <= sum(m in usual for m in mains) <= 6, seed
        assert all(mains.count(m) <= HABITUAL_MAX_EACH for m in usual), seed


# ---------- Mercadona ----------


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


# ---------- store & API ----------


@pytest.fixture
def client(tmp_path):
    shop = Mercadona(tmp_path / "cache.json", fetch=fake_mercadona)
    return TestClient(create_app(Store(tmp_path), static_dir=tmp_path / "nostatic", shop=shop))


def test_seed_sync_adds_new_recipes_and_respects_user_changes(tmp_path, monkeypatch):
    import gusteau.store as st

    bundle = tmp_path / "bundle"
    (bundle / "recipes").mkdir(parents=True)
    (bundle / "aisles.yml").write_text("Frutería: [tomate]\n")
    monkeypatch.setattr(st, "SEED", bundle / "recipes")
    monkeypatch.setattr(st, "SEED_AISLES", bundle / "aisles.yml")

    def bundle_recipe(slug, qty):
        (bundle / "recipes" / f"{slug}.cook").write_text(f"---\ntitle: {slug}\ntags: [cena]\n---\n@tomate{{{qty}}}\n")

    bundle_recipe("a", 1)
    bundle_recipe("b", 1)
    bundle_recipe("c", 1)
    data = tmp_path / "data"
    store = Store(data)
    assert {r.slug for r in store.list_recipes()} == {"a", "b", "c"}

    # user edits b, deletes c; app update changes a, b, c and adds d + a new aisle item
    store.save_recipe("---\ntitle: mine\ntags: [cena]\n---\n@tomate{9}\n", "b")
    store.delete_recipe("c")
    (data / "aisles.yml").write_text("Mi pasillo: [tomate]\n")
    for slug in "abcd":
        bundle_recipe(slug, 2)
    (bundle / "aisles.yml").write_text("Frutería: [tomate, pepino]\n")

    store = Store(data)
    recipes = {r.slug: r for r in store.list_recipes()}
    assert set(recipes) == {"a", "b", "d"}  # c stays deleted
    assert recipes["a"].ingredients[0].quantity == 2  # untouched -> updated
    assert recipes["b"].title == "mine"  # edited -> kept
    assert store.aisles() == {"tomate": "Mi pasillo", "pepino": "Frutería"}  # user aisle kept, new item merged


def test_atomic_write_leaves_old_file_on_failure(tmp_path, monkeypatch):
    from gusteau import store as st

    target = tmp_path / "plan.json"
    target.write_text("old")

    def boom(*_):
        raise OSError("disk full")

    monkeypatch.setattr(st.os, "replace", boom)
    with pytest.raises(OSError):
        st.atomic_write(target, "new")
    assert target.read_text() == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["plan.json"]  # no temp file left behind


def test_recipe_cache_reparses_only_changed_files(tmp_path, monkeypatch):
    from gusteau import store as st

    store = Store(tmp_path)
    n = len(store.list_recipes())  # warm the cache
    calls = []
    real_parse = st.parse
    monkeypatch.setattr(st, "parse", lambda text, slug: calls.append(slug) or real_parse(text, slug))
    store.list_recipes()
    assert calls == []  # nothing changed -> nothing re-parsed
    store.save_recipe("---\ntitle: Nueva\ntags: [cena]\n---\n@tomate{1}\n", "nueva")
    store.save_recipe("---\ntitle: Cambiada\ntags: [cena]\n---\n@tomate{2}\n", "lentejas-con-verduras")
    calls.clear()
    recipes = {r.slug: r for r in store.list_recipes()}
    assert sorted(calls) == ["lentejas-con-verduras", "nueva"] and len(recipes) == n + 1
    assert recipes["lentejas-con-verduras"].title == "Cambiada"
    store.delete_recipe("nueva")
    assert "nueva" not in {r.slug for r in store.list_recipes()}


def test_concurrent_settings_writes_do_not_corrupt(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    store = Store(tmp_path)
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda n: store.save_settings({"people": n % 5 + 1}), range(200)))
    assert 1 <= store.settings()["people"] <= 5  # valid JSON, a value one of the writers set


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
