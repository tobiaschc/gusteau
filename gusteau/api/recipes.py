from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..cooklang import CooklangError
from .deps import StoreDep, recipe_or_404
from .schemas import Recipe, RecipeDetail, RecipeIn, RecipeSummary

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeSummary])
def list_recipes(store: StoreDep):
    return [
        RecipeSummary(
            slug=r.slug,
            title=r.title,
            tags=r.tags,
            time=r.time,
            servings=r.servings,
            ingredients=[i.name for i in r.ingredients],
        )
        for r in store.list_recipes()
    ]


@router.get("/{slug}", response_model=RecipeDetail)
def get_recipe(slug: str, store: StoreDep):
    recipe = recipe_or_404(store, slug)
    return RecipeDetail.model_validate({**Recipe.model_validate(recipe).model_dump(), "source": store.get_source(slug)})


@router.post("", status_code=201, response_model=Recipe)
def create_recipe(body: RecipeIn, store: StoreDep):
    try:
        return store.save_recipe(body.source)
    except CooklangError as e:
        raise HTTPException(422, str(e)) from None


@router.put("/{slug}", response_model=Recipe)
def update_recipe(slug: str, body: RecipeIn, store: StoreDep):
    recipe_or_404(store, slug)
    try:
        return store.save_recipe(body.source, slug)
    except CooklangError as e:
        raise HTTPException(422, str(e)) from None


@router.delete("/{slug}", status_code=204)
def delete_recipe(slug: str, store: StoreDep) -> None:
    recipe_or_404(store, slug)
    store.delete_recipe(slug)
