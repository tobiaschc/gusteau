"""Shopping list: add up the ingredients of a plan, scaled to the number of people."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .cooklang import Recipe

# unit -> (base unit, factor). Anything else is kept as-is and summed per unit.
UNITS = {
    "g": ("g", 1),
    "gr": ("g", 1),
    "kg": ("g", 1000),
    "ml": ("ml", 1),
    "cl": ("ml", 10),
    "dl": ("ml", 100),
    "l": ("ml", 1000),
    "": ("ud", 1),
    "ud": ("ud", 1),
    "uds": ("ud", 1),
    "unidad": ("ud", 1),
    "unidades": ("ud", 1),
}


@dataclass
class Item:
    name: str
    amounts: dict[str, float]  # base unit -> quantity; "" key = no quantity given ("al gusto")
    aisle: str
    recipes: list[str]


def _base(qty: float | None, unit: str) -> tuple[str, float | None]:
    base, factor = UNITS.get(unit, (unit, 1))
    return base, None if qty is None else qty * factor


def shopping_list(meals: list[Recipe], people: int, aisles: dict[str, str]) -> list[Item]:
    """`meals` has one entry per planned meal (repeats allowed)."""
    amounts: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    used_in: dict[str, list[str]] = defaultdict(list)
    for recipe in meals:
        scale = people / recipe.servings
        for ing in recipe.ingredients:
            base, qty = _base(ing.quantity, ing.unit)
            if qty is None:
                amounts[ing.name].setdefault("", 0)
            else:
                amounts[ing.name][base] += qty * scale
            if recipe.title not in used_in[ing.name]:
                used_in[ing.name].append(recipe.title)
    items = [
        Item(name, {u: round(q, 2) for u, q in amounts[name].items()}, aisles.get(name, "Otros"), used_in[name])
        for name in amounts
    ]
    order = {a: n for n, a in enumerate(dict.fromkeys(aisles.values()))}  # aisles.yml order = walk order
    return sorted(items, key=lambda i: (order.get(i.aisle, len(order)), i.name))


def _num(v: float) -> str:
    return f"{v:.3g}".replace(".", ",")  # Spanish decimal comma


def format_amount(base: str, qty: float) -> str:
    if base == "":
        return "al gusto"
    if base == "g" and qty >= 1000:
        return f"{_num(qty / 1000)} kg"
    if base == "ml" and qty >= 1000:
        return f"{_num(qty / 1000)} l"
    if base == "ud":
        return f"{int(-(-qty // 1))} ud"  # you buy whole items
    return f"{round(qty):g} {base}" if qty >= 10 else f"{_num(qty)} {base}"
