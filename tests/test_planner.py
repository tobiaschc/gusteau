from itertools import pairwise

from gusteau.cooklang import parse
from gusteau.planner import generate
from gusteau.store import Store

from .conftest import WEEK


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


def test_generate_finds_near_optimal_weeks(tmp_path):
    """Greedy restarts + hill-climb: with the bundled bank nearly every week has no conflicts."""
    from gusteau.planner import penalty

    store = Store(tmp_path)
    recipes = store.list_recipes()
    tags = {r.slug: r.tags for r in recipes}
    scores = [
        penalty(generate(store.get_plan(WEEK), recipes, keep=False, seed=seed)["days"], tags) for seed in range(8)
    ]
    assert max(scores) <= 4 and scores.count(0) >= 6, scores


def test_generate_favours_recipes_with_a_favorite_ingredient(tmp_path):
    store = Store(tmp_path)
    recipes = store.list_recipes()
    favorite = "pechuga de pollo"
    favored = {r.slug for r in recipes if any(i.name == favorite for i in r.ingredients)}
    assert favored  # the bundled bank has at least one recipe using it

    def mains_with_favorite(favorite_ingredients: list[str]) -> int:
        total = 0
        for seed in range(8):
            days = generate(
                store.get_plan(WEEK), recipes, keep=False, seed=seed, favorite_ingredients=favorite_ingredients
            )["days"].values()
            total += sum(d[s] in favored for d in days for s in ("comida", "cena"))
        return total

    assert mains_with_favorite([favorite]) > mains_with_favorite([])
