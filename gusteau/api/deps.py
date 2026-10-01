"""Shared dependencies and request validation helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request

from ..cooklang import Recipe
from ..mercadona import Mercadona
from ..store import WEEK, Store


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_shop(request: Request) -> Mercadona:
    return request.app.state.shop


StoreDep = Annotated[Store, Depends(get_store)]
ShopDep = Annotated[Mercadona, Depends(get_shop)]
Week = Annotated[str, Path(pattern=WEEK.pattern, examples=["2026-W40"], description="ISO week YYYY-Www")]


def recipe_or_404(store: Store, slug: str) -> Recipe:
    try:
        return store.get_recipe(slug)
    except KeyError:
        raise HTTPException(404, f"receta '{slug}' no encontrada") from None
