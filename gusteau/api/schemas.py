"""Request and response models: the API contract (also used to generate the frontend types)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    # response fields with defaults are still always present -> required in the generated TS types
    model_config = ConfigDict(from_attributes=True, json_schema_serialization_defaults_required=True)


# ---- recipes ----


class RecipeIn(BaseModel):
    source: str = Field(min_length=1, max_length=50_000, description="Cooklang text")


class RecipeSummary(Model):
    slug: str
    title: str
    tags: list[str]
    time: str | None
    servings: int
    ingredients: list[str] = Field(description="ingredient names")


class Ingredient(Model):
    name: str
    quantity: float | None
    unit: str


class TextSegment(Model):
    type: Literal["text"]
    value: str


class IngredientSegment(Model):
    type: Literal["ingredient"]
    name: str
    quantity: float | None
    unit: str


class CookwareSegment(Model):
    type: Literal["cookware"]
    name: str


class TimerSegment(Model):
    type: Literal["timer"]
    name: str
    quantity: float | None
    unit: str


Segment = Annotated[TextSegment | IngredientSegment | CookwareSegment | TimerSegment, Field(discriminator="type")]


class Recipe(Model):
    slug: str
    title: str
    servings: int
    tags: list[str]
    time: str | None
    ingredients: list[Ingredient]
    steps: list[list[Segment]]


class RecipeDetail(Recipe):
    source: str


# ---- plans ----

Days = dict[str, dict[str, str | None]]


class PlanIn(BaseModel):
    days: Days


class GenerateIn(BaseModel):
    keep: bool = Field(default=True, description="keep the slots already filled")
    seed: int | None = None


class Plan(Model):
    week: str
    days: Days
    titles: dict[str, str | None] = Field(description="slug -> title for every recipe in the plan")


# ---- shopping ----


class Amount(Model):
    unit: str
    quantity: float
    label: str


class Product(Model):
    id: str
    name: str
    price: float
    size: float | None
    size_format: str
    units: int | None
    approx: bool
    available: bool
    url: str
    thumbnail: str | None
    packaging: str | None


class PricedItem(Model):
    product: Product
    packs: int
    cost: float
    approx: bool
    pantry: bool = Field(description="uses a small share of a pack: probably already at home")
    auto: bool = Field(description="product picked automatically, not by the user")


class ShoppingItem(Model):
    name: str
    aisle: str
    recipes: list[str]
    amounts: list[Amount]
    mercadona: PricedItem | None = None


class Shopping(Model):
    week: str
    people: int
    meals: int
    items: list[ShoppingItem]
    total: float | None = None
    prices_error: str | None = None


class ProductIn(BaseModel):
    id: str | None = Field(default=None, max_length=20, description="null = not bought at Mercadona")


class ProductPick(Model):
    ingredient: str
    id: str | None


# ---- settings ----


class Settings(Model):
    people: int
    slots: list[str]
    prices: bool
    warehouse: str


class SettingsIn(BaseModel):
    people: int | None = Field(default=None, ge=1, le=20)
    prices: bool | None = None


class Health(Model):
    ok: bool
