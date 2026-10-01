import pytest

from gusteau.store import Store, slugify


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

    # next update retires a (untouched) and b (edited by the user)
    (bundle / "recipes" / "a.cook").unlink()
    (bundle / "recipes" / "b.cook").unlink()
    store = Store(data)
    assert {r.slug for r in store.list_recipes()} == {"b", "d"}  # a removed, b kept as the user's own
    bundle_recipe("b", 3)  # ...and a later bundled "b" doesn't overwrite it
    assert Store(data).get_recipe("b").title == "mine"


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
    assert 1 <= store.settings()["people"] <= 5  # a value one of the writers set


def test_concurrent_plan_saves_same_week(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    store = Store(tmp_path)
    slugs = ["lentejas-con-verduras", "tortilla-patatas"]

    def save(n):
        store.save_plan({"week": "2026-W41", "days": {"lunes": {"cena": slugs[n % 2]}}})

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(save, range(100)))
    assert store.get_plan("2026-W41")["days"]["lunes"]["cena"] in slugs


def test_slugify():
    assert slugify("Salmón con patata & ensalada!") == "salmon-con-patata-ensalada"


def test_imports_json_plans_and_settings_once(tmp_path):
    import json

    (tmp_path / "plans").mkdir()
    days = {"lunes": {"desayuno": None, "comida": "lentejas-con-verduras", "cena": None}}
    (tmp_path / "plans" / "2026-W39.json").write_text(json.dumps({"week": "2026-W39", "days": days}))
    (tmp_path / "settings.json").write_text(json.dumps({"people": 3}))

    store = Store(tmp_path)
    assert store.settings()["people"] == 3
    assert store.get_plan("2026-W39")["days"]["lunes"]["comida"] == "lentejas-con-verduras"
    assert not (tmp_path / "plans").exists() and (tmp_path / "plans.imported" / "2026-W39.json").exists()
    assert (tmp_path / "settings.json.imported").exists()

    store.save_settings({"people": 2})
    assert Store(tmp_path).settings()["people"] == 2  # restart doesn't re-import


def test_plan_keeps_title_of_deleted_recipe(tmp_path):
    store = Store(tmp_path)
    store.save_recipe("---\ntitle: Plato efímero\ntags: [cena]\n---\n@tomate{1}\n", "efimero")
    store.save_plan({"week": "2026-W40", "days": {"lunes": {"cena": "efimero"}}})
    store.delete_recipe("efimero")
    plan = store.get_plan("2026-W40")
    assert plan["days"]["lunes"]["cena"] == "efimero" and plan["titles"]["efimero"] == "Plato efímero"


def test_models_match_migrations(tmp_path):
    """A model change without a new Alembic migration fails here."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from gusteau.db import Base

    store = Store(tmp_path)
    with store.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []
