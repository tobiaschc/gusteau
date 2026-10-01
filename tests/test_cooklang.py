import pytest
import yaml

from gusteau.cooklang import CooklangError, parse


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
