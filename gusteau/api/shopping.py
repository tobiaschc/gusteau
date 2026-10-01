from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from ..mercadona import Mercadona, MercadonaError, price_item
from ..shopping import Item, format_amount, shopping_list
from ..store import Store
from .deps import ShopDep, StoreDep, Week
from .schemas import (
    Amount,
    PricedItem,
    Product,
    ProductIn,
    ProductPick,
    Purchase,
    PurchasePatch,
    Shopping,
    ShoppingItem,
)

router = APIRouter(tags=["shopping"])


def build_shopping(store: Store, shop: Mercadona | None, week: str, people: int | None) -> Shopping:
    """The week's list; with `shop`, each item also gets its Mercadona product and price."""
    plan = store.get_plan(week)
    people = people or store.settings()["people"]
    recipes = {r.slug: r for r in store.list_recipes()}
    meals = [recipes[s] for day in plan["days"].values() for s in day.values() if s in recipes]
    items = shopping_list(meals, people, store.aisles())
    out = Shopping(
        week=week,
        people=people,
        meals=len(meals),
        items=[
            ShoppingItem(
                name=i.name,
                aisle=i.aisle,
                recipes=i.recipes,
                amounts=[Amount(unit=u, quantity=q, label=format_amount(u, q)) for u, q in i.amounts.items()],
            )
            for i in items
        ],
    )
    if items and shop and store.settings()["prices"]:
        try:
            _add_prices(store, shop, items, out)
        except MercadonaError as e:
            out.prices_error = str(e)
    return out


def _add_prices(store: Store, shop: Mercadona, items: list[Item], out: Shopping) -> None:
    mapping = store.products()
    ids = {}
    for i in items:
        pid = mapping[i.name] if i.name in mapping else shop.auto_pick(i.name)
        if pid:
            ids[i.name] = pid
    products = shop.products(list(ids.values()))
    for item, row in zip(items, out.items, strict=True):
        product = products.get(ids.get(item.name, ""))
        if product:
            row.mercadona = PricedItem.model_validate(
                {**price_item(item.amounts, product), "auto": item.name not in mapping}
            )
    priced = [row.mercadona for row in out.items if row.mercadona and not row.mercadona.pantry]
    out.total = round(sum(p.cost for p in priced), 2) if priced else None


@router.get("/plans/{week}/shopping", response_model=Shopping)
def get_shopping(week: Week, store: StoreDep, shop: ShopDep, people: int | None = None):
    return build_shopping(store, shop, week, people)


@router.get("/plans/{week}/shopping.md", response_class=PlainTextResponse)
def get_shopping_md(week: Week, store: StoreDep, people: int | None = None) -> str:
    data = build_shopping(store, None, week, people)
    lines = [f"# Lista de la compra · {week} · {data.people} personas", ""]
    aisle = None
    for item in data.items:
        if item.aisle != aisle:
            aisle = item.aisle
            lines += ["", f"## {aisle}"]
        lines.append(f"- [ ] {item.name} — " + " + ".join(a.label for a in item.amounts))
    return "\n".join(lines).replace("\n\n\n", "\n\n") + "\n"


@router.get("/products/search", response_model=list[Product], tags=["mercadona"])
def search_products(q: str, shop: ShopDep):
    try:
        return [asdict(p) for p in shop.search(q)]
    except MercadonaError as e:
        raise HTTPException(502, str(e)) from None


@router.put("/products/{ingredient}", response_model=ProductPick, tags=["mercadona"])
def set_product(ingredient: str, body: ProductIn, store: StoreDep):
    store.set_product(ingredient, body.id)
    return ProductPick(ingredient=ingredient.lower(), id=body.id)


# ---- purchases: the list frozen with that day's prices, for spending stats ----


@router.post("/plans/{week}/purchases", status_code=201, response_model=Purchase, tags=["purchases"])
def create_purchase(week: Week, store: StoreDep, shop: ShopDep, people: int | None = None):
    data = build_shopping(store, shop, week, people)
    if not data.items:
        raise HTTPException(409, "esta semana no tiene comidas planificadas")
    items = [
        {
            "name": i.name,
            "amounts": [a.model_dump() for a in i.amounts],
            "product_id": i.mercadona.product.id if i.mercadona else None,
            "product": i.mercadona.product.name if i.mercadona else None,
            "packs": i.mercadona.packs if i.mercadona else None,
            "cost": i.mercadona.cost if i.mercadona else None,
            "pantry": bool(i.mercadona and i.mercadona.pantry),
        }
        for i in data.items
    ]
    return store.add_purchase(week, data.people, data.total, items)


@router.get("/purchases", response_model=list[Purchase], tags=["purchases"])
def list_purchases(store: StoreDep, week: Week | None = None):
    return store.purchases(week)


@router.patch("/purchases/{purchase_id}", response_model=Purchase, tags=["purchases"])
def update_purchase(purchase_id: int, body: PurchasePatch, store: StoreDep):
    try:
        return store.update_purchase(purchase_id, body.actual_total)
    except KeyError:
        raise HTTPException(404, "compra no encontrada") from None


@router.delete("/purchases/{purchase_id}", status_code=204, tags=["purchases"])
def delete_purchase(purchase_id: int, store: StoreDep) -> None:
    try:
        store.delete_purchase(purchase_id)
    except KeyError:
        raise HTTPException(404, "compra no encontrada") from None
