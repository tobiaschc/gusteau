"""File-based storage: recipes are .cook files, plans and settings are JSON.

Layout under GUSTEAU_DATA (default ./data):
    recipes/<slug>.cook
    plans/<YYYY-Www>.json
    settings.json
    aisles.yml      ingredient -> supermarket aisle (optional)
    products.yml    your ingredient -> Mercadona product picks (override the bundled ones)
    .cache/         Mercadona responses
    .seeded.json    hashes of the bundled files last copied in (to sync app updates)
"""

from __future__ import annotations

import hashlib
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
DEFAULT_SETTINGS = {"people": 2, "slots": SLOTS, "prices": True, "warehouse": "mad1"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WEEK = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")
SEED = Path(__file__).resolve().parent.parent / "recipes"
SEED_AISLES = Path(__file__).resolve().parent.parent / "aisles.yml"
SEED_PRODUCTS = Path(__file__).resolve().parent.parent / "products.yml"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "receta"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _merge_aisles(local: Path, bundled: Path) -> None:
    """Add bundled ingredients missing from a user-edited aisles.yml, keeping their choices."""
    mine = yaml.safe_load(local.read_text(encoding="utf-8")) or {}
    known = {str(i).lower() for items in mine.values() for i in items or []}
    for aisle, items in (yaml.safe_load(bundled.read_text(encoding="utf-8")) or {}).items():
        missing = [i for i in items or [] if str(i).lower() not in known]
        if missing:
            mine.setdefault(aisle, [])
            mine[aisle] = list(mine[aisle] or []) + missing
    local.write_text(yaml.safe_dump(mine, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


class Store:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or os.environ.get("GUSTEAU_DATA", "data"))
        self.recipes_dir = self.root / "recipes"
        self.plans_dir = self.root / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.recipes_dir.mkdir(exist_ok=True)
        self.sync_seed()

    def sync_seed(self) -> None:
        """Bring bundled recipes and aisles into the data dir without clobbering user edits.

        - new bundled recipe -> copied in
        - bundled recipe changed, local copy untouched since last sync -> updated
        - local copy edited, or deleted by the user -> left alone
        - aisles.yml: replaced if untouched, otherwise new ingredients are appended to their aisle
        """
        state_path = self.root / ".seeded.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        recipes = state.setdefault("recipes", {})
        first_run = not state_path.exists() and not any(self.recipes_dir.glob("*.cook"))
        for src in sorted(SEED.glob("*.cook")) if SEED.is_dir() else []:
            bundled = _digest(src.read_bytes())
            dst = self.recipes_dir / src.name
            seeded = recipes.get(src.stem)
            if seeded is None:
                if not dst.exists() or first_run:
                    shutil.copy(src, dst)
                    recipes[src.stem] = bundled
                elif _digest(dst.read_bytes()) == bundled:
                    recipes[src.stem] = bundled  # already identical (install from before tracking)
                # else: same slug created by the user -> theirs
            elif seeded != bundled and dst.exists() and _digest(dst.read_bytes()) == seeded:
                shutil.copy(src, dst)
                recipes[src.stem] = bundled

        aisles = self.root / "aisles.yml"
        if SEED_AISLES.exists():
            bundled = _digest(SEED_AISLES.read_bytes())
            if not aisles.exists() or _digest(aisles.read_bytes()) in (state.get("aisles"), bundled):
                shutil.copy(SEED_AISLES, aisles)
                state["aisles"] = bundled
            elif state.get("aisles_bundle") != bundled:
                _merge_aisles(aisles, SEED_AISLES)
            state["aisles_bundle"] = bundled
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True))

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

    # ---- Mercadona products ----

    def products(self) -> dict[str, str | None]:
        """ingredient -> product id (None = not sold). User picks win over the bundled defaults."""
        merged: dict[str, str | None] = {}
        for path in (SEED_PRODUCTS, self.root / "products.yml"):
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                merged |= {str(k).lower(): (str(v) if v is not None else None) for k, v in data.items()}
        return merged

    def set_product(self, ingredient: str, product_id: str | None) -> None:
        path = self.root / "products.yml"
        data = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
        data[ingredient.lower()] = product_id
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")
