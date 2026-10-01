from gusteau.cooklang import parse
from gusteau.shopping import format_amount, shopping_list


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
