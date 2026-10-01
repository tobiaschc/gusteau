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
