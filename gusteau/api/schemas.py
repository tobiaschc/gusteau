"""Request and response models: the API contract (also used to generate the frontend types)."""

from __future__ import annotations

import datetime as dt
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


class MealOutcome(Model):
    status: Literal["skipped", "swapped"]
    swap_slug: str | None = Field(description="recipe eaten instead (swapped)")
    swap_title: str | None = Field(description="title of what was eaten instead (swapped)")


class Plan(Model):
    week: str
    days: Days
    titles: dict[str, str | None] = Field(description="slug -> title for every recipe in the plan")
    outcomes: dict[str, dict[str, MealOutcome]] = Field(
        description="day -> slot -> what happened, only for meals NOT cooked as planned"
    )


class OutcomeIn(BaseModel):
    status: Literal["cooked", "skipped", "swapped"] = Field(description="cooked = as planned (the default)")
    swap_slug: str | None = Field(default=None, max_length=120, description="recipe eaten instead")
    swap_title: str | None = Field(default=None, max_length=200, description="or free text, e.g. 'pizza fuera'")


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
    pantry: bool = Field(default=False, description="usually already at home: asked instead of listed")
    in_cart: bool = False
    at_home: bool | None = Field(default=None, description="pantry answer: true = have it, false = buy it")


class Shopping(Model):
    week: str
    people: int
    meals: int
    items: list[ShoppingItem]
    total: float | None = None
    prices_error: str | None = None


class MarkIn(BaseModel):
    """Only the fields sent are changed."""

    in_cart: bool | None = None
    at_home: bool | None = Field(default=None, description="null = unanswered again")


class Mark(Model):
    ingredient: str
    in_cart: bool
    at_home: bool | None


class ProductIn(BaseModel):
    id: str | None = Field(default=None, max_length=20, description="null = not bought at Mercadona")


class ProductPick(Model):
    ingredient: str
    id: str | None


# ---- purchases ----


class PurchaseItem(Model):
    name: str
    amounts: list[Amount]
    product_id: str | None
    product: str | None
    packs: int | None
    cost: float | None
    pantry: bool


class Purchase(Model):
    id: int
    week: str
    created_at: dt.datetime
    people: int
    estimated_total: float | None = Field(description="Mercadona estimate when bought (None: no prices then)")
    actual_total: float | None = Field(description="receipt total, if entered")
    items: list[PurchaseItem]


class PurchasePatch(BaseModel):
    actual_total: float | None = Field(ge=0, le=10_000, description="receipt total; null clears it")


# ---- stats ----


class DishStat(Model):
    slug: str | None = Field(description="None: free text eaten instead of the plan")
    title: str
    count: int
    last: dt.date


class RecipeRef(Model):
    slug: str
    title: str


class WeekSpend(Model):
    week: str
    total: float
    exact: bool = Field(description="every purchase that week has its receipt total")
    purchases: int


class MonthSpend(Model):
    month: str = Field(examples=["2026-10"])
    total: float
    exact: bool


class Spending(Model):
    weeks: list[WeekSpend]
    months: list[MonthSpend]
    total: float | None
    average_week: float | None = Field(description="over weeks with a purchase")


class Stats(Model):
    since: str | None = Field(description="first ISO week included; None = all history")
    meals_eaten: int
    meals_skipped: int
    dishes: list[DishStat] = Field(description="lunches and dinners, most eaten first")
    breakfasts: list[DishStat]
    never_eaten: list[RecipeRef] = Field(description="lunch/dinner recipes not eaten in the period")
    spending: Spending


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
