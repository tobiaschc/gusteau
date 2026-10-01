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
import tempfile
import threading
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


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` so readers see the old or the new file, never half of one.

    Temp file in the same directory + fsync + os.replace (atomic on POSIX). Protects
    against a crash or container stop mid-write; concurrent writers still need a lock.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


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
    atomic_write(local, yaml.safe_dump(mine, allow_unicode=True, sort_keys=False, width=120))


class Store:
    """All reads and writes of the data dir.

    Thread-safe within one process (FastAPI runs sync endpoints in a thread pool):
    read-modify-write operations hold `_lock`, and every write is atomic. Parsed
    recipes are cached and re-parsed only when their file changes (mtime/size), so
    listing the bank costs one directory scan. Returned Recipe objects are shared:
    treat them as read-only.
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or os.environ.get("GUSTEAU_DATA", "data"))
        self.recipes_dir = self.root / "recipes"
        self.plans_dir = self.root / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.recipes_dir.mkdir(exist_ok=True)
        self._lock = threading.RLock()
        self._recipes: dict[str, tuple[tuple[int, int], Recipe]] = {}
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
                    atomic_write(dst, src.read_text(encoding="utf-8"))
                    recipes[src.stem] = bundled
                elif _digest(dst.read_bytes()) == bundled:
                    recipes[src.stem] = bundled  # already identical (install from before tracking)
                # else: same slug created by the user -> theirs
            elif seeded != bundled and dst.exists() and _digest(dst.read_bytes()) == seeded:
                atomic_write(dst, src.read_text(encoding="utf-8"))
                recipes[src.stem] = bundled

        aisles = self.root / "aisles.yml"
        if SEED_AISLES.exists():
            bundled = _digest(SEED_AISLES.read_bytes())
            if not aisles.exists() or _digest(aisles.read_bytes()) in (state.get("aisles"), bundled):
                atomic_write(aisles, SEED_AISLES.read_text(encoding="utf-8"))
                state["aisles"] = bundled
            elif state.get("aisles_bundle") != bundled:
                _merge_aisles(aisles, SEED_AISLES)
            state["aisles_bundle"] = bundled
        atomic_write(state_path, json.dumps(state, indent=2, sort_keys=True))

    # ---- recipes ----

    def _recipe_path(self, slug: str) -> Path:
        if not SLUG.match(slug):
            raise KeyError(slug)
        return self.recipes_dir / f"{slug}.cook"

    def _cached(self, path: Path) -> Recipe:
        st = path.stat()
        key = (st.st_mtime_ns, st.st_size)
        hit = self._recipes.get(path.stem)
        if hit and hit[0] == key:
            return hit[1]
        recipe = parse(path.read_text(encoding="utf-8"), path.stem)
        self._recipes[path.stem] = (key, recipe)
        return recipe

    def list_recipes(self) -> list[Recipe]:
        paths = [p for p in self.recipes_dir.glob("*.cook") if SLUG.match(p.stem)]
        with self._lock:
            recipes = [self._cached(p) for p in paths]
            for gone in self._recipes.keys() - {p.stem for p in paths}:
                del self._recipes[gone]
        return sorted(recipes, key=lambda r: r.title.lower())

    def get_recipe(self, slug: str) -> Recipe:
        path = self._recipe_path(slug)
        try:
            with self._lock:
                return self._cached(path)
        except FileNotFoundError:
            raise KeyError(slug) from None

    def get_source(self, slug: str) -> str:
        path = self._recipe_path(slug)
        if not path.exists():
            raise KeyError(slug)
        return path.read_text(encoding="utf-8")

    def save_recipe(self, source: str, slug: str | None = None) -> Recipe:
        recipe = parse(source, slug or "")  # validate before touching disk
        with self._lock:  # slug allocation + write must not interleave with another create
            if slug is None:
                base = slug = slugify(recipe.title)
                n = 2
                while self._recipe_path(slug).exists():
                    slug, n = f"{base}-{n}", n + 1
            atomic_write(self._recipe_path(slug), source if source.endswith("\n") else source + "\n")
        recipe.slug = slug
        return recipe

    def delete_recipe(self, slug: str) -> None:
        path = self._recipe_path(slug)
        if not path.exists():
            raise KeyError(slug)
        with self._lock:
            path.unlink()
            self._recipes.pop(slug, None)

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
        atomic_write(self._plan_path(plan["week"]), json.dumps(plan, ensure_ascii=False, indent=2))
        return plan

    # ---- settings & aisles ----

    def settings(self) -> dict:
        path = self.root / "settings.json"
        stored = json.loads(path.read_text()) if path.exists() else {}
        return {**DEFAULT_SETTINGS, **stored}

    def save_settings(self, values: dict) -> dict:
        with self._lock:
            merged = {**self.settings(), **values}
            atomic_write(self.root / "settings.json", json.dumps(merged, ensure_ascii=False, indent=2))
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
        with self._lock:
            data = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
            data[ingredient.lower()] = product_id
            atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=True))
