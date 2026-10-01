"""File-based storage: recipes are .cook files, plans and settings are JSON.

Layout under GUSTEAU_DATA (default ./data):
    recipes/<slug>.cook
    plans/<YYYY-Www>.json
    settings.json
    aisles.yml      ingredient -> supermarket aisle (optional)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

import yaml

from .cooklang import Recipe, parse

DAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
SLOTS = ["desayuno", "comida", "cena"]
DEFAULT_SETTINGS = {"people": 2, "slots": SLOTS}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WEEK = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")
SEED = Path(__file__).resolve().parent.parent / "recipes"
SEED_AISLES = Path(__file__).resolve().parent.parent / "aisles.yml"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "receta"


class Store:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or os.environ.get("GUSTEAU_DATA", "data"))
        self.recipes_dir = self.root / "recipes"
        self.plans_dir = self.root / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        if not self.recipes_dir.exists():
            # first run: start with the bundled recipe bank
            shutil.copytree(SEED, self.recipes_dir) if SEED.is_dir() else self.recipes_dir.mkdir(parents=True)
        aisles = self.root / "aisles.yml"
        if not aisles.exists() and SEED_AISLES.exists():
            shutil.copy(SEED_AISLES, aisles)

    # ---- recipes ----

    def _recipe_path(self, slug: str) -> Path:
        if not SLUG.match(slug):
            raise KeyError(slug)
        return self.recipes_dir / f"{slug}.cook"

    def list_recipes(self) -> list[Recipe]:
        return sorted((self.get_recipe(p.stem) for p in self.recipes_dir.glob("*.cook")), key=lambda r: r.title.lower())

    def get_recipe(self, slug: str) -> Recipe:
        path = self._recipe_path(slug)
        if not path.exists():
            raise KeyError(slug)
        return parse(path.read_text(encoding="utf-8"), slug)

    def get_source(self, slug: str) -> str:
        path = self._recipe_path(slug)
        if not path.exists():
            raise KeyError(slug)
        return path.read_text(encoding="utf-8")

    def save_recipe(self, source: str, slug: str | None = None) -> Recipe:
        recipe = parse(source, slug or "")  # validate before touching disk
        if slug is None:
            base = slug = slugify(recipe.title)
            n = 2
            while self._recipe_path(slug).exists():
                slug, n = f"{base}-{n}", n + 1
        path = self._recipe_path(slug)
        path.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
        recipe.slug = slug
        return recipe

    def delete_recipe(self, slug: str) -> None:
        path = self._recipe_path(slug)
        if not path.exists():
            raise KeyError(slug)
        path.unlink()

    # ---- plans ----

    def _plan_path(self, week: str) -> Path:
        if not WEEK.match(week):
            raise KeyError(week)
        return self.plans_dir / f"{week}.json"

    def get_plan(self, week: str) -> dict:
        path = self._plan_path(week)
        if path.exists():
            return json.loads(path.read_text())
        return {"week": week, "days": {d: {s: None for s in self.settings()["slots"]} for d in DAYS}}

    def save_plan(self, plan: dict) -> dict:
        self._plan_path(plan["week"]).write_text(json.dumps(plan, ensure_ascii=False, indent=2))
        return plan

    # ---- settings & aisles ----

    def settings(self) -> dict:
        path = self.root / "settings.json"
        stored = json.loads(path.read_text()) if path.exists() else {}
        return {**DEFAULT_SETTINGS, **stored}

    def save_settings(self, values: dict) -> dict:
        merged = {**self.settings(), **values}
        (self.root / "settings.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2))
        return merged

    def aisles(self) -> dict[str, str]:
        path = self.root / "aisles.yml"
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # file is grouped by aisle: {Frutería: [tomate, ...]} -> {tomate: Frutería}; dict order = shop order
        return {str(i).lower(): aisle for aisle, items in data.items() for i in items or []}
