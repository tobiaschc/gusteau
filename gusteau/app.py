"""Gusteau HTTP API."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import planner
from .cooklang import CooklangError
from .mercadona import Mercadona, MercadonaError, price_item
from .shopping import format_amount, shopping_list
from .store import WEEK, Store


class RecipeIn(BaseModel):
    source: str = Field(min_length=1, max_length=50_000)


class PlanIn(BaseModel):
    days: dict[str, dict[str, str | None]]


class GenerateIn(BaseModel):
    keep: bool = True
    seed: int | None = None


class SettingsIn(BaseModel):
    people: int | None = Field(default=None, ge=1, le=20)
    prices: bool | None = None


class ProductIn(BaseModel):
    id: str | None = Field(default=None, max_length=20)  # None = not sold at Mercadona


def current_week(today: dt.date | None = None) -> str:
    y, w, _ = (today or dt.datetime.now().astimezone().date()).isocalendar()
    return f"{y}-W{w:02d}"


def create_app(store: Store | None = None, static_dir: Path | None = None, shop: Mercadona | None = None) -> FastAPI:
    store = store or Store()
    shop = shop or Mercadona(store.root / ".cache" / "mercadona.json", store.settings()["warehouse"])
    app = FastAPI(title="Gusteau", docs_url="/api/docs", openapi_url="/api/openapi.json")

    def recipe_or_404(slug: str):
        try:
            return store.get_recipe(slug)
        except KeyError:
            raise HTTPException(404, f"receta '{slug}' no encontrada") from None

    def check_week(week: str) -> None:
        if not WEEK.match(week):
            raise HTTPException(422, "semana con formato YYYY-Www, p.ej. 2026-W40")

    # ---- recipes ----

    @app.get("/api/recipes")
    def list_recipes():
        return [
            {
                "slug": r.slug,
                "title": r.title,
                "tags": r.tags,
                "time": r.time,
                "servings": r.servings,
                "ingredients": [i.name for i in r.ingredients],
            }
            for r in store.list_recipes()
        ]

    @app.get("/api/recipes/{slug}")
    def get_recipe(slug: str):
        recipe = recipe_or_404(slug)
        return {**asdict(recipe), "source": store.get_source(slug)}

    @app.post("/api/recipes", status_code=201)
    def create_recipe(body: RecipeIn):
        try:
            return asdict(store.save_recipe(body.source))
        except CooklangError as e:
            raise HTTPException(422, str(e)) from None

    @app.put("/api/recipes/{slug}")
    def update_recipe(slug: str, body: RecipeIn):
        recipe_or_404(slug)
        try:
            return asdict(store.save_recipe(body.source, slug))
        except CooklangError as e:
            raise HTTPException(422, str(e)) from None

    @app.delete("/api/recipes/{slug}", status_code=204)
    def delete_recipe(slug: str):
        recipe_or_404(slug)
        store.delete_recipe(slug)

    # ---- plans ----

    def plan_view(plan: dict) -> dict:
        titles = {r.slug: r.title for r in store.list_recipes()}
        return {**plan, "titles": {s: titles.get(s) for d in plan["days"].values() for s in d.values() if s}}

    @app.get("/api/plans/current")
    def get_current_plan():
        return plan_view(store.get_plan(current_week()))

    @app.get("/api/plans/{week}")
    def get_plan(week: str):
        check_week(week)
        return plan_view(store.get_plan(week))

    @app.put("/api/plans/{week}")
    def put_plan(week: str, body: PlanIn):
        check_week(week)
        for slots in body.days.values():
            for slug in filter(None, slots.values()):
                recipe_or_404(slug)
        return plan_view(store.save_plan({"week": week, "days": body.days}))

    @app.post("/api/plans/{week}/generate")
    def generate_plan(week: str, body: GenerateIn):
        check_week(week)
        plan = planner.generate(store.get_plan(week), store.list_recipes(), keep=body.keep, seed=body.seed)
        return plan_view(store.save_plan(plan))

    @app.get("/api/plans/{week}/shopping")
    def get_shopping(week: str, people: int | None = None, prices: bool = True):
        check_week(week)
        plan = store.get_plan(week)
        people = people or store.settings()["people"]
        recipes = {r.slug: r for r in store.list_recipes()}
        meals = [recipes[s] for d in plan["days"].values() for s in d.values() if s in recipes]
        items = shopping_list(meals, people, store.aisles())
        out = [
            {
                "name": i.name,
                "aisle": i.aisle,
                "recipes": i.recipes,
                "amounts": [{"unit": u, "quantity": q, "label": format_amount(u, q)} for u, q in i.amounts.items()],
                "mercadona": None,
            }
            for i in items
        ]
        result = {
            "week": week,
            "people": people,
            "meals": len(meals),
            "items": out,
            "total": None,
            "prices_error": None,
        }
        if items and prices and store.settings()["prices"]:
            try:
                add_prices(items, out)
                priced = [o["mercadona"] for o in out if o["mercadona"] and not o["mercadona"]["pantry"]]
                result["total"] = round(sum(p["cost"] for p in priced), 2) if priced else None
            except MercadonaError as e:
                result["prices_error"] = str(e)
        return result

    def add_prices(items, out) -> None:
        mapping = store.products()
        ids = {}
        for i in items:
            pid = mapping[i.name] if i.name in mapping else shop.auto_pick(i.name)
            if pid:
                ids[i.name] = pid
        products = shop.products(list(ids.values()))
        for i, o in zip(items, out, strict=True):
            product = products.get(ids.get(i.name, ""))
            if product:
                o["mercadona"] = {**price_item(i.amounts, product), "auto": i.name not in mapping}

    # ---- Mercadona ----

    @app.get("/api/products/search")
    def search_products(q: str):
        try:
            return [asdict(p) for p in shop.search(q)]
        except MercadonaError as e:
            raise HTTPException(502, str(e)) from None

    @app.put("/api/products/{ingredient}")
    def set_product(ingredient: str, body: ProductIn):
        store.set_product(ingredient, body.id)
        return {"ingredient": ingredient.lower(), "id": body.id}

    @app.get("/api/plans/{week}/shopping.md", response_class=PlainTextResponse)
    def get_shopping_md(week: str, people: int | None = None):
        data = get_shopping(week, people, prices=False)
        lines = [f"# Lista de la compra · {week} · {data['people']} personas", ""]
        aisle = None
        for item in data["items"]:
            if item["aisle"] != aisle:
                aisle = item["aisle"]
                lines += ["", f"## {aisle}"]
            lines.append(f"- [ ] {item['name']} — " + " + ".join(a["label"] for a in item["amounts"]))
        return "\n".join(lines).replace("\n\n\n", "\n\n") + "\n"

    # ---- settings ----

    @app.get("/api/settings")
    def get_settings():
        return store.settings()

    @app.put("/api/settings")
    def put_settings(body: SettingsIn):
        return store.save_settings(body.model_dump(exclude_none=True))

    @app.get("/api/health")
    def health():
        return {"ok": True}

    # ---- frontend (built SPA) ----

    static_dir = static_dir or Path(os.environ.get("GUSTEAU_STATIC", Path(__file__).parent / "static"))
    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets", check_dir=False), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            file = (static_dir / path).resolve()
            if path and file.is_file() and static_dir.resolve() in file.parents:
                return FileResponse(file)
            return FileResponse(static_dir / "index.html")

    return app
